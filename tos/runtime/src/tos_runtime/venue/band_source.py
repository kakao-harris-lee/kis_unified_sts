"""tos_runtime.venue.band_source — the declared broker price-band source (CP-3 band 원천"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from decimal import Decimal, DecimalException, InvalidOperation
from typing import Any

from tos.venue import PriceBandTick

from tos_runtime.custody.ports import CustodyError
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.client import (
    KisMockClientError,
    KisMockHttpClient,
    RawResponse,
)
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSession
from tos_runtime.transport.kis_mock.pacer import KisPacingRefused
from tos_runtime.transport.kis_mock.token import (
    EvidenceRecorder,
    TokenResponseError,
    TokenStale,
)
from tos_runtime.transport.kis_quote.config import KisQuoteTransportConfig

__all__ = [
    "BAND_SOURCE_BOUND_TRADING_DATE_KST",
    "BAND_SOURCE_FAILURE_UNKNOWN",
    "BAND_SOURCE_KIND_KIS_QUOTE_GET",
    "BAND_SOURCE_READ_ON_TOKENS",
    "VENUE_BAND_OBSERVED_KIND",
    "BandBounds",
    "BandObservation",
    "BandReader",
    "BandRefusal",
    "BandSourceConfig",
    "KisBandSourceReader",
    "KisQuoteGetBandSource",
    "band_source_digest",
    "build_band_client",
    "validate_band_values",
]

VENUE_BAND_OBSERVED_KIND = "VENUE_BAND_OBSERVED"

BAND_SOURCE_KIND_KIS_QUOTE_GET = "kis_quote_get"

BAND_SOURCE_BOUND_TRADING_DATE_KST = "trading_date_kst"

BAND_SOURCE_FAILURE_UNKNOWN = "unknown"

BAND_SOURCE_READ_ON_TOKENS: frozenset[str] = frozenset({"boot", "phase_change"})


@dataclass(frozen=True)
class BandSourceConfig:
    """What EVERY ``_runtime.band_source`` kind declares, parsed and fail-closed-validated by"""

    kind: str
    instrument: str
    price_scale: int
    bound: str
    read_on: tuple[str, ...]
    failure: str


@dataclass(frozen=True)
class KisQuoteGetBandSource(BandSourceConfig):
    """``kind: "kis_quote_get"`` — the runtime does the GET itself (plan §4.1's YAML block)."""

    tr_id: str
    upper_field: str
    lower_field: str
    basis_field: str
    timeout_ms: int


@dataclass(frozen=True)
class BandObservation:
    """One validated band reading (plan §4.2)."""

    instrument: str
    price_min: int
    price_max: int
    trading_date: str
    raw_payload_digest: str
    source_continuity_id: str
    as_of_ms: int
    basis: int | None
    symmetric_about_basis: bool | None

    @property
    def record_digest(self) -> str:
        """The canonical digest of this observation record — what the venue service binds into"""
        return _canonical_digest(
            {
                "instrument": self.instrument,
                "price_min": self.price_min,
                "price_max": self.price_max,
                "trading_date": self.trading_date,
                "raw_payload_digest": self.raw_payload_digest,
                "source_continuity_id": self.source_continuity_id,
                "basis": self.basis,
                "symmetric_about_basis": self.symmetric_about_basis,
            }
        )


BandReader = Callable[[], BandObservation | None]


@dataclass(frozen=True)
class BandBounds:
    """The scaled, ordered, on-grid band :func:`validate_band_values` produced."""

    price_min: int
    price_max: int
    basis: int | None
    symmetric_about_basis: bool | None


@dataclass(frozen=True)
class BandRefusal:
    """Which clause of :func:`validate_band_values` rejected the values, and with what."""

    reason: str
    detail: str


def _rung_tick(price: int, table: tuple[PriceBandTick, ...]) -> int | None:
    """The tick of the row whose inclusive band covers ``price`` — the same absolute lookup"""
    for row in table:
        if row.band_min <= price <= row.band_max:
            return row.tick
    return None


def validate_band_values(
    *,
    lower_raw: Any,
    upper_raw: Any,
    basis_raw: Any,
    price_scale: int,
    tick_size: int | None,
    lower_label: str,
    upper_label: str,
    price_band_ticks: tuple[PriceBandTick, ...] | None = None,
) -> BandBounds | BandRefusal:
    """Plan §4.2's validation set, in order — the ONE place it exists."""
    lower = _scaled(lower_raw, price_scale)
    upper = _scaled(upper_raw, price_scale)
    if lower is None or upper is None:
        return BandRefusal(
            "non_integral_scale",
            f"{lower_label}={lower_raw!r} {upper_label}={upper_raw!r} "
            f"scale={price_scale}",
        )
    if not 0 < lower < upper:
        return BandRefusal("band_not_ordered", f"min={lower} max={upper}")
    if price_band_ticks:
        ticks = {value: _rung_tick(value, price_band_ticks) for value in (lower, upper)}
        unresolved = [value for value, tick in ticks.items() if tick is None]
        if unresolved:
            return BandRefusal("tick_unresolved", f"no rung covers {unresolved}")
        off_grid = [
            value for value, tick in ticks.items() if tick is not None and value % tick
        ]
        if off_grid:
            return BandRefusal("off_tick_grid", f"price_band_ticks off_grid={off_grid}")
    else:
        if tick_size is None or tick_size <= 0:
            return BandRefusal("tick_size_absent", f"tick_size={tick_size!r}")
        off_grid = [value for value in (lower, upper) if value % tick_size != 0]
        if off_grid:
            return BandRefusal(
                "off_tick_grid", f"tick_size={tick_size} off_grid={off_grid}"
            )
    basis = _scaled(basis_raw, price_scale)
    return BandBounds(
        price_min=lower,
        price_max=upper,
        basis=basis,
        symmetric_about_basis=(
            None if basis is None else (upper - basis) == (basis - lower)
        ),
    )


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    """SHA-256 over a key-sorted, separator-pinned JSON serialization — the same"""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def band_source_digest(config: BandSourceConfig) -> str:
    """The canonical digest of a declared ``band_source`` block — recorded on"""
    payload: dict[str, Any] = {}
    for field in fields(config):
        value = getattr(config, field.name)
        if field.name == "read_on":
            value = sorted(value)
        elif isinstance(value, tuple):
            value = list(value)
        payload[field.name] = value
    return _canonical_digest(payload)


def build_band_client(
    transport_config: KisQuoteTransportConfig, band_source: KisQuoteGetBandSource
) -> KisMockHttpClient:
    """The one sanctioned way to build the band GET's client (mirrors"""
    return KisMockHttpClient(
        rest_base=transport_config.endpoint_rest_base,
        request_timeout_s=band_source.timeout_ms / 1000,
        allow_plaintext_for_tests=transport_config.allow_plaintext_for_tests,
    )


class KisBandSourceReader:
    """Reads the declared band source once per call, validates it completely, and records one"""

    def __init__(
        self,
        *,
        band_source: KisQuoteGetBandSource,
        transport_config: KisQuoteTransportConfig,
        client: KisMockHttpClient,
        credential_session: KisCredentialSession,
        monotonic: MonotonicSource,
        evidence_sink: EvidenceRecorder,
        trading_date_reader: Callable[[], str | None],
        tick_size: int | None,
        price_band_ticks: tuple[PriceBandTick, ...] | None = None,
    ) -> None:
        """Wire this reader's dependencies (all injected — no ambient state)."""
        self._band_source = band_source
        self._transport_config = transport_config
        self._client = client
        self._credential_session = credential_session
        self._monotonic = monotonic
        self._evidence = evidence_sink
        self._trading_date_reader = trading_date_reader
        self._tick_size = tick_size
        self._price_band_ticks = price_band_ticks
        self._boot_continuity_seed = secrets.token_hex(16)
        self._token_epoch = 0
        self._token_digest: str | None = None
        self._last_observation: BandObservation | None = None

    def read(self) -> BandObservation | None:
        """One GET + full validation. ``None`` on ANY failure, always with one"""
        as_of_ms = self._monotonic.now_ms()
        trading_date = self._trading_date_reader()
        if trading_date is None:
            self._refuse("trading_date_unavailable")
            return None
        try:
            access_token = self._credential_session.ensure_token_string()
        except TokenStale as exc:
            self._refuse("token_stale", detail=str(exc))
            return None
        except TokenResponseError as exc:
            self._refuse("token_response_invalid", detail=str(exc))
            return None
        except KisMockClientError as exc:
            self._refuse("token_transport_error", detail=str(exc))
            return None
        except CustodyError as exc:
            self._refuse("token_custody_error", detail=str(exc))
            return None
        except KisPacingRefused as exc:
            self._refuse("token_pacing_refused", detail=str(exc))
            return None
        continuity_id = self._continuity_for(access_token)
        try:
            response = self._fetch(access_token)
        except KisMockClientError as exc:
            self._refuse("transport_error", detail=str(exc))
            return None
        except CustodyError as exc:
            self._refuse("custody_error", detail=str(exc))
            return None
        except KisPacingRefused as exc:
            self._refuse("pacing_refused", detail=str(exc))
            return None
        output = self._parse_output(response)
        if output is None:
            return None
        return self._validate(
            output,
            raw_text=response.text,
            trading_date=trading_date,
            continuity_id=continuity_id,
            as_of_ms=as_of_ms,
        )

    def _fetch(self, access_token: str) -> RawResponse:
        """(mirrors ``KisQuoteObservationIntake._fetch_quote``) The app key/secret are loaded"""
        query = (
            f"FID_COND_MRKT_DIV_CODE={self._transport_config.market_div_code}"
            f"&FID_INPUT_ISCD={self._band_source.instrument}"
        )
        with self._credential_session.app_credentials() as credentials:
            return self._client.get_quote(
                self._band_source.tr_id,
                query,
                access_token=access_token,
                app_key=credentials.app_key(),
                app_secret=credentials.app_secret(),
                path=self._transport_config.quote_path,
            )

    def _continuity_for(self, access_token: str) -> str:
        digest = hashlib.sha256(access_token.encode("utf-8")).hexdigest()
        if self._token_digest is not None and digest != self._token_digest:
            self._token_epoch += 1
        self._token_digest = digest
        return f"{self._boot_continuity_seed}:{self._token_epoch}"

    def _parse_output(self, response: RawResponse) -> dict[str, Any] | None:
        if response.json is None:
            self._refuse("malformed_response", detail=f"status={response.status}")
            return None
        rt_cd = response.json.get("rt_cd")
        if rt_cd != "0":
            self._refuse(
                "rt_cd_not_ok",
                detail=f"rt_cd={rt_cd!r} msg1={response.json.get('msg1')!r}",
            )
            return None
        output = response.json.get("output")
        if not isinstance(output, dict):
            self._refuse(
                "malformed_output", detail=f"output_type={type(output).__name__}"
            )
            return None
        return output

    def _validate(
        self,
        output: dict[str, Any],
        *,
        raw_text: str,
        trading_date: str,
        continuity_id: str,
        as_of_ms: int,
    ) -> BandObservation | None:
        """Plan §4.2's validation set, in order. A refusal here has already passed ``rt_cd``,"""
        outcome = validate_band_values(
            lower_raw=output.get(self._band_source.lower_field),
            upper_raw=output.get(self._band_source.upper_field),
            basis_raw=output.get(self._band_source.basis_field),
            price_scale=self._band_source.price_scale,
            tick_size=self._tick_size,
            price_band_ticks=self._price_band_ticks,
            lower_label=self._band_source.lower_field,
            upper_label=self._band_source.upper_field,
        )
        if isinstance(outcome, BandRefusal):
            self._refuse(outcome.reason, detail=outcome.detail)
            return None
        observation = BandObservation(
            instrument=self._band_source.instrument,
            price_min=outcome.price_min,
            price_max=outcome.price_max,
            trading_date=trading_date,
            raw_payload_digest=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            source_continuity_id=continuity_id,
            as_of_ms=as_of_ms,
            basis=outcome.basis,
            symmetric_about_basis=outcome.symmetric_about_basis,
        )
        self._record_observed(observation)
        self._last_observation = observation
        return observation

    def _narrowed_intraday(self, observation: BandObservation) -> bool:
        """Plan §4.5 / §2's 단서: a band that NARROWS within one trading date contradicts the"""
        previous = self._last_observation
        if previous is None or previous.trading_date != observation.trading_date:
            return False
        return (
            observation.price_min > previous.price_min
            or observation.price_max < previous.price_max
        )

    def _record_observed(self, observation: BandObservation) -> None:
        self._evidence(
            VENUE_BAND_OBSERVED_KIND,
            {
                "outcome": "OBSERVED",
                "instrument": observation.instrument,
                "price_min": observation.price_min,
                "price_max": observation.price_max,
                "basis": observation.basis,
                "trading_date": observation.trading_date,
                "raw_payload_digest": observation.raw_payload_digest,
                "continuity": observation.source_continuity_id,
                "band_digest": observation.record_digest,
                "symmetric_about_basis": observation.symmetric_about_basis,
                "narrowed_intraday": self._narrowed_intraday(observation),
                "critical_input_snapshot_digest_role": "stand-in",
            },
        )

    def _refuse(self, reason: str, *, detail: str | None = None) -> None:
        self._evidence(
            VENUE_BAND_OBSERVED_KIND,
            {
                "outcome": "REFUSED",
                "instrument": self._band_source.instrument,
                "reason": reason,
                "detail": detail,
            },
        )
        return None


def _scaled(raw: Any, scale: int) -> int | None:
    """``raw × scale`` as an EXACT integer, or ``None``."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        parsed = Decimal(str(raw))
    except (InvalidOperation, ValueError, ArithmeticError):
        return None
    if not parsed.is_finite():
        return None
    try:
        value = parsed * scale
    except DecimalException:
        return None
    if value != value.to_integral_value():
        return None
    return int(value)
