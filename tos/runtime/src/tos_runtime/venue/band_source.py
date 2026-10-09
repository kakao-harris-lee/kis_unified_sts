"""tos_runtime.venue.band_source — the declared broker price-band source (CP-3 band 원천
웨이브, ``docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md`` §4.1/§4.2/§4.5).

**What this module is.** One GET against the KIS 모의투자 quotations TR the active venue
policy's own ``_runtime.band_source`` block declares (``FHMIF10000000``'s ``futs_mxpr``/
``futs_llam``), validated into a :class:`BandObservation` the venue service folds into the
EFFECTIVE shape constraints' ``price_min``/``price_max``. Every failure — transport, broker
rejection, scaling, ordering, tick grid, trading-date stamp — returns ``None`` plus an evidence
row, never a partially trusted band (plan §4.6: "모든 실패는 band None → 커널 UNKNOWN → 송신
0", so the worst case of this wave is exactly today's behaviour).

**Reused, never re-built (plan §4.2).** The host seal and the token lifecycle are the
``kis_quote`` transport's own: this module takes an already-loaded, already-host-sealed
:class:`~tos_runtime.transport.kis_quote.config.KisQuoteTransportConfig` for the REST base /
quote path / market-div code / plaintext flag, builds its client through
:func:`build_band_client` (the same ``KisMockHttpClient`` the quote intake uses), and
authenticates through the boot's one
:class:`~tos_runtime.transport.kis_mock.credential_session.KisCredentialSession` (C-2 decision
(C) — one app key, one token lifecycle). It opens no second HTTP client class, provisions no
second credential path, and reads no ``os.environ``.

**The one thing that is NOT the transport's.** ``request_timeout_s`` comes from
``band_source.timeout_ms``, not from the transport document's own ``request_timeout_s``: the
band GET is a boot-path call whose stall budget is a venue-policy decision (plan §4.1's
``timeout_ms`` paragraph — a named-TBD the enabling deployment's operator adopts), while the
intake's timeout governs a per-tick poll. :func:`build_band_client` is the only place that
conversion happens.

**The trading date is a LOCAL STAMP, not a response field (plan §4.2 ⚠).** The response body
carries no business date (``docs/broker-profiles/evidence/2026-10-08-cp3-venue-limits/`` —
``futs_sdpr == futs_prdy_clpr``, so even the basis cannot distinguish the day). The
``trading_date`` on an observation is this runtime's own
:meth:`~tos_runtime.calendar.owner.SessionFactsOwner.trading_date_now` reading taken at the GET
instant. It therefore catches "a band held in memory across a trading date" (the §4.4a bond the
venue service applies) and does NOT catch "a stale RESPONSE" — plan §2's unmeasured premise,
registered there as residual risk, not closed here. A read whose stamp is ``None`` (the calendar
cannot say which trading date this instant belongs to) is REFUSED outright rather than stamped
with a guess: a band that cannot be bound to a date cannot be invalidated when the date turns.

**``symmetric_about_basis`` names exactly what it measures — it does NOT identify stage 1.**
시행세칙 제56조의2's stage-1 band is ``기준가격 × (1 ± r)``, which is symmetric about the basis;
so is stage 2 and so is stage 3, because every stage uses the same ± form with a larger ``r``.
Symmetry is therefore a NECESSARY condition of the stage-1 formula and not a sufficient one, and
calling the field ``stage_hint`` (as this module first did, and as plan §4.5 originally
worded it — corrected there 2026-10-09 with an implementation-time note)
claimed a discrimination it cannot make. The field records the measurement and nothing more: the
observed band is symmetric about the observed basis (the 2026-10-08 모의 measurement satisfies
it — basis 1073.32, band 987.46/1159.18, both legs 85.86 wide). **The stage-1 judgement is made
OFFLINE**, from the raw ``basis``/``price_min``/``price_max`` the same evidence row carries, once
an approved source for ``r`` exists (plan §9 4); this module has none and inventing one would be
the hardcoded-threshold defect this repo's CLAUDE.md forbids. A ``False`` (or ``None``, when the
basis did not scale exactly) value NEVER drops a band: plan §4.4a's residual-risk paragraph says
the response-side check waits until the first enabled session's rows are measured.

**Source continuity (ADR-002-019 §9: 재시작·재접속·자격 교체는 새 연속성).** The continuity id is
``<boot_continuity_seed>:<token_epoch>``. The seed is minted once per reader construction (so a
restart is a new continuity by construction), and ``token_epoch`` advances whenever the bearer
token this reader is handed differs from the previous read's — a reissue, which is exactly the
"자격 교체" case. The token itself is never stored, compared, or recorded: only a SHA-256 digest
of it is held in memory for that comparison, and that digest never reaches an evidence row.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.*`` only —
no ``shared.*``, no ``os.environ``.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.client import (
    KisMockClientError,
    KisMockHttpClient,
    RawResponse,
)
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSession
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
    "BandObservation",
    "BandReader",
    "BandSourceConfig",
    "KisBandSourceReader",
    "band_source_digest",
    "build_band_client",
]

#: Evidence kind string (runtime vocabulary — never a kernel ``EvidenceKind`` member, the same
#: idiom :mod:`tos_runtime.venue.service` already uses for ``VENUE_POLICY_BOUND`` &c).
VENUE_BAND_OBSERVED_KIND = "VENUE_BAND_OBSERVED"

#: The one ``band_source.kind`` this package can actually read (plan §4.1's YAML block). A
#: document naming anything else is refused by the loader rather than silently ignored — an
#: unreadable source declaration would otherwise boot as "band_source declared, band always
#: None", indistinguishable from a transport outage.
BAND_SOURCE_KIND_KIS_QUOTE_GET = "kis_quote_get"

#: The one implemented ``band_source.bound`` (plan §4.4a — the venue service's trading-date
#: bond is the only invalidation this wave implements).
BAND_SOURCE_BOUND_TRADING_DATE_KST = "trading_date_kst"

#: The one admitted ``band_source.failure`` (plan §4.1/§4.6 — every failure is ``band None`` and
#: therefore kernel ``UNKNOWN``; no other failure response exists to declare).
BAND_SOURCE_FAILURE_UNKNOWN = "unknown"

#: The two admitted ``band_source.read_on`` tokens (plan §4.3 "읽는 시점"). A document naming a
#: third token would declare a read instant nothing implements.
BAND_SOURCE_READ_ON_TOKENS: frozenset[str] = frozenset({"boot", "phase_change"})


@dataclass(frozen=True)
class BandSourceConfig:
    """The venue policy's own ``_runtime.band_source`` block, parsed and fail-closed-validated
    by :func:`~tos_runtime.venue.config.load_venue_constraint_policy` (plan §4.1).

    Attributes:
        kind: :data:`BAND_SOURCE_KIND_KIS_QUOTE_GET`.
        tr_id: The KIS quotations TR id to GET (``FHMIF10000000``).
        instrument: The ``FID_INPUT_ISCD`` this GET asks for — the SINGLE source of the
            requested contract (plan §4.1 "GET 의 종목은 한 출처에서만 온다"). The loader binds
            it to the policy's own ``scope.instruments`` sole element (§4.4b).
        upper_field: The response ``output`` key carrying the upper limit (``futs_mxpr``).
        lower_field: The response ``output`` key carrying the lower limit (``futs_llam``).
        basis_field: The response ``output`` key carrying the reference price (``futs_sdpr``) —
            recorded as evidence and used for
            :attr:`BandObservation.symmetric_about_basis` only, NEVER for admissibility.
        price_scale: The exact integer multiplier from the broker's quoted index points to the
            kernel's opaque scaled ints. Must equal ``_runtime.price_scale`` (plan §4.1's price
            scale paragraph — the loader refuses a mismatch).
        timeout_ms: The band GET's own per-request stall budget (module docstring).
        bound: :data:`BAND_SOURCE_BOUND_TRADING_DATE_KST`.
        read_on: A subset of :data:`BAND_SOURCE_READ_ON_TOKENS`.
        failure: :data:`BAND_SOURCE_FAILURE_UNKNOWN`.
    """

    kind: str
    tr_id: str
    instrument: str
    upper_field: str
    lower_field: str
    basis_field: str
    price_scale: int
    timeout_ms: int
    bound: str
    read_on: tuple[str, ...]
    failure: str


@dataclass(frozen=True)
class BandObservation:
    """One validated band reading (plan §4.2).

    Attributes:
        instrument: The contract this band was requested for (``BandSourceConfig.instrument``
            — the request's own ``FID_INPUT_ISCD``, never a response echo: the body carries no
            contract identifier, which is why the contract bond is a LOADER rule, plan §4.4b).
        price_min: The lower limit, scaled to the kernel's opaque int by an EXACT
            :class:`~decimal.Decimal` multiply.
        price_max: The upper limit, same scaling.
        trading_date: The LOCAL ``YYYYMMDD`` KST stamp taken at the GET instant (module
            docstring) — never a response field, never ``None`` on a successful observation.
        raw_payload_digest: SHA-256 over the response body's RAW bytes, exactly as received —
            the runtime's own direct binding to what the broker sent (plan §6 (A): this is the
            reason the GET lives in the runtime at all). Deliberately not a digest of the
            PARSED ``output`` block: any re-serialization is a digest of this runtime's
            rendering, not of the broker's bytes, and an earlier cut that stringified the
            parsed values made ``"1159.18"`` and ``1159.18`` collide.
        source_continuity_id: Module docstring's "source continuity".
        as_of_ms: The monotonic reading taken immediately before the request went out.
        basis: The scaled reference price, or ``None`` when the basis field was absent or did
            not scale exactly (evidence only — never admissibility).
        symmetric_about_basis: Module docstring's own section — ``None`` when :attr:`basis`
            is ``None`` (nothing to be symmetric about), never a judgement about which
            price-limit stage is in force.
    """

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
        """The canonical digest of this observation record — what the venue service binds into
        the snapshot's ``critical_input_snapshot_digest`` STAND-IN slot (plan §4.3 M3: the
        kernel field is capsule-owned; what goes in is this runtime record's digest, and both
        the policy header and every evidence row say so)."""
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


#: What :class:`~tos_runtime.venue.service.VenueConstraintService` is injected with — the
#: narrowest possible surface over :meth:`KisBandSourceReader.read` (one zero-arg call), so a
#: test double is a plain lambda and the service never depends on the transport package.
BandReader = Callable[[], BandObservation | None]


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    """SHA-256 over a key-sorted, separator-pinned JSON serialization — the same
    order-independence discipline :meth:`~tos_runtime.transport.kis_quote.adapter
    .KisQuoteObservationIntake._content_digest` already applies, so declaration order never
    changes a digest."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def band_source_digest(config: BandSourceConfig) -> str:
    """The canonical digest of a declared ``band_source`` block — recorded on
    ``VENUE_POLICY_BOUND`` (plan §4.5 / §6 (B)).

    Activation compares the kernel ``canonical_digest``, which covers ``_model_view`` only, so a
    ``_runtime`` block is outside it. The operator's 2026-10-08 disposition on §6 (B) was
    "증거 digest + GOV-001 후보 등재만" — this function is the evidence half.
    """
    return _canonical_digest(
        {
            "kind": config.kind,
            "tr_id": config.tr_id,
            "instrument": config.instrument,
            "upper_field": config.upper_field,
            "lower_field": config.lower_field,
            "basis_field": config.basis_field,
            "price_scale": config.price_scale,
            "timeout_ms": config.timeout_ms,
            "bound": config.bound,
            "read_on": sorted(config.read_on),
            "failure": config.failure,
        }
    )


def build_band_client(
    transport_config: KisQuoteTransportConfig, band_source: BandSourceConfig
) -> KisMockHttpClient:
    """The one sanctioned way to build the band GET's client (mirrors
    :func:`~tos_runtime.transport.kis_quote.adapter.build_quote_client`'s own "one sanctioned
    construction path" discipline).

    The host and the plaintext escape hatch come from ``transport_config`` — the document whose
    loader already proved the REST base byte-matches the INSTANCE MOCK_VTS ``rest_base`` and is
    not the REAL one. This function never takes a URL, so a band reader cannot be pointed
    anywhere that seal did not already validate. The timeout is the ONE value that comes from
    the policy instead (module docstring).
    """
    return KisMockHttpClient(
        rest_base=transport_config.endpoint_rest_base,
        request_timeout_s=band_source.timeout_ms / 1000,
        allow_plaintext_for_tests=transport_config.allow_plaintext_for_tests,
    )


class KisBandSourceReader:
    """Reads the declared band source once per call, validates it completely, and records one
    ``VENUE_BAND_OBSERVED`` row either way (module docstring; plan §4.2/§4.5)."""

    def __init__(
        self,
        *,
        band_source: BandSourceConfig,
        transport_config: KisQuoteTransportConfig,
        client: KisMockHttpClient,
        credential_session: KisCredentialSession,
        monotonic: MonotonicSource,
        evidence_sink: EvidenceRecorder,
        trading_date_reader: Callable[[], str | None],
        tick_size: int | None,
    ) -> None:
        """Wire this reader's dependencies (all injected — no ambient state).

        Args:
            band_source: The policy's own declared source block.
            transport_config: The host-sealed ``kis_quote`` transport document (module
                docstring — host/path/market-div/plaintext only; its own timeout is NOT used).
            client: Build it with :func:`build_band_client` for real use.
            credential_session: The boot's one ``kis_mock.*`` session (C-2 decision (C)).
            monotonic: The process's monotonic source — :attr:`BandObservation.as_of_ms`.
            evidence_sink: Records ``VENUE_BAND_OBSERVED``.
            trading_date_reader: The calendar owner's own KST trading-date reading (module
                docstring's "LOCAL STAMP" note).
            tick_size: The ACTIVE policy's ``shape_constraints.tick_size`` — the grid both
                bounds must sit on (plan §4.2: a tree still carrying ``tick_size: 5`` is caught
                HERE, which is why the §3 tick correction is a precondition of enabling).
                ``None`` (a policy with no tick source) refuses every read: an ungridded band
                cannot be validated, and the kernel would answer ``UNKNOWN`` on the tick check
                anyway.
        """
        self._band_source = band_source
        self._transport_config = transport_config
        self._client = client
        self._credential_session = credential_session
        self._monotonic = monotonic
        self._evidence = evidence_sink
        self._trading_date_reader = trading_date_reader
        self._tick_size = tick_size
        #: Minted once per reader — a restart is a new continuity by construction (module
        #: docstring). ``secrets.token_hex`` rather than a counter: two processes booting in the
        #: same millisecond must not claim the same continuity.
        self._boot_continuity_seed = secrets.token_hex(16)
        self._token_epoch = 0
        #: SHA-256 of the bearer token the previous read used — never the token itself, never
        #: recorded (module docstring).
        self._token_digest: str | None = None
        #: The previous SUCCESSFUL observation, for the same-trading-date narrowing flag
        #: (plan §4.5 / §8 8).
        self._last_observation: BandObservation | None = None

    def read(self) -> BandObservation | None:
        """One GET + full validation. ``None`` on ANY failure, always with one
        ``VENUE_BAND_OBSERVED`` row naming the reason (plan §4.2's validation set)."""
        as_of_ms = self._monotonic.now_ms()
        trading_date = self._trading_date_reader()
        if trading_date is None:
            self._refuse("trading_date_unavailable")
            return None
        # The token step has THREE distinct failure modes, not one (independent review M1):
        # the held token is stale and the cooldown has not elapsed (`TokenStale`), the token
        # endpoint answered with an unusable body (`TokenResponseError`), or the token request
        # never completed (`KisMockClientError` — `KisTokenLifecycle._issue_token` calls the
        # same HTTP client this module does). Letting the last two propagate would carry a
        # transport fault out through `snapshot()`/`decide()` instead of into band `None`,
        # which is the one outcome plan §4.6 promises.
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
        continuity_id = self._continuity_for(access_token)
        try:
            response = self._fetch(access_token)
        except KisMockClientError as exc:
            self._refuse("transport_error", detail=str(exc))
            return None
        output = self._parse_output(response)
        if output is None:
            return None  # _parse_output already recorded its own refusal
        return self._validate(
            output,
            raw_text=response.text,
            trading_date=trading_date,
            continuity_id=continuity_id,
            as_of_ms=as_of_ms,
        )

    # -- request -------------------------------------------------------------

    def _fetch(self, access_token: str) -> RawResponse:
        """(mirrors ``KisQuoteObservationIntake._fetch_quote``) The app key/secret are loaded
        inside the narrowest possible ``with`` block, wrapped directly around the one GET.
        """
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

    # -- validation ----------------------------------------------------------

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
        """Plan §4.2's validation set, in order. A refusal here has already passed ``rt_cd``,
        so the band exists and is merely unusable — each reason names which clause rejected it.
        """
        scale = self._band_source.price_scale
        lower = _scaled(output.get(self._band_source.lower_field), scale)
        upper = _scaled(output.get(self._band_source.upper_field), scale)
        if lower is None or upper is None:
            self._refuse(
                "non_integral_scale",
                detail=(
                    f"{self._band_source.lower_field}="
                    f"{output.get(self._band_source.lower_field)!r} "
                    f"{self._band_source.upper_field}="
                    f"{output.get(self._band_source.upper_field)!r} scale={scale}"
                ),
            )
            return None
        if not 0 < lower < upper:
            self._refuse("band_not_ordered", detail=f"min={lower} max={upper}")
            return None
        if self._tick_size is None or self._tick_size <= 0:
            self._refuse("tick_size_absent", detail=f"tick_size={self._tick_size!r}")
            return None
        off_grid = [value for value in (lower, upper) if value % self._tick_size != 0]
        if off_grid:
            self._refuse(
                "off_tick_grid",
                detail=f"tick_size={self._tick_size} off_grid={off_grid}",
            )
            return None
        basis = _scaled(output.get(self._band_source.basis_field), scale)
        observation = BandObservation(
            instrument=self._band_source.instrument,
            price_min=lower,
            price_max=upper,
            trading_date=trading_date,
            raw_payload_digest=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            source_continuity_id=continuity_id,
            as_of_ms=as_of_ms,
            basis=basis,
            symmetric_about_basis=(
                None if basis is None else (upper - basis) == (basis - lower)
            ),
        )
        self._record_observed(observation)
        self._last_observation = observation
        return observation

    # -- evidence ------------------------------------------------------------

    def _narrowed_intraday(self, observation: BandObservation) -> bool:
        """Plan §4.5 / §2's 단서: a band that NARROWS within one trading date contradicts the
        monotonicity this wave's "boot-once is safe all day" argument rests on. It is recorded,
        never acted on — the band is still used, because a narrower band is the conservative
        direction; what matters is that the counter-observation leaves a row."""
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
                # Plan §4.3 M3 / §4.5: the stand-in label travels with the row, in the same
                # idiom `egress_coordinates.yaml::capsule_terminus_fields` uses.
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
    """``raw × scale`` as an EXACT integer, or ``None``.

    Never rounds (plan §4.2: "반올림 금지 — 커널 §12 'silent rounding' 원칙과 같은 이유"). A
    value that is absent, unparseable as a decimal, or whose scaled form is not a whole number
    is ``None`` — the caller turns that into a named refusal, never into a nearby integer.
    """
    if raw is None or isinstance(raw, bool):
        return None
    try:
        parsed = Decimal(str(raw))
    except (InvalidOperation, ValueError, ArithmeticError):
        return None
    # `Decimal` accepts "Infinity"/"-Infinity"/"NaN" (independent review M1): they survive the
    # multiply and the integral comparison, and only blow up at `int()` with an OverflowError
    # that would escape `read()` entirely. Refused here, as a named reason like any other
    # unusable value.
    if not parsed.is_finite():
        return None
    value = parsed * scale
    if value != value.to_integral_value():
        return None
    return int(value)
