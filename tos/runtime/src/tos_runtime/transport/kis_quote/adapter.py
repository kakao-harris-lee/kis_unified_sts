"""KIS quote intake implementing the runtime observation port."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from tos.dsl import ScalarValue

from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.marketfeed.ports import MonotonicAnchoredObservation, ObservationIntake
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.client import KisMockHttpClient, RawResponse
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSession
from tos_runtime.transport.kis_mock.pacer import KisPacing, KisPacingRefused
from tos_runtime.transport.kis_mock.token import (
    EvidenceRecorder,
    TokenIssuingClient,
    TokenStale,
)
from tos_runtime.transport.kis_quote.config import KisQuoteTransportConfig

KIS_QUOTE_PACING_REFUSED_KIND = "KIS_QUOTE_PACING_REFUSED"

__all__ = [
    "KIS_QUOTE_PACING_REFUSED_KIND",
    "KisQuoteAdapterError",
    "KisQuoteMalformedResponse",
    "KisQuoteObservationIntake",
    "KisQuoteRejected",
    "TokenStale",
    "build_quote_client",
]

_KIS_MOCK_APP_KEY_SCOPE = "kis_mock.app_key"
_KIS_MOCK_APP_SECRET_SCOPE = "kis_mock.app_secret"

_SCALAR_FIELD_TYPES: tuple[type, ...] = (bool, int, float, str)


class KisQuoteAdapterError(Exception):
    """A structural fault in this adapter's own configuration/wiring — e.g. ``poll`` was called"""


class KisQuoteRejected(Exception):
    """The broker's own response carried ``rt_cd != "0"`` — a business-layer rejection, not a"""


class KisQuoteMalformedResponse(Exception):
    """The response body did not parse as JSON, was not an object, or its ``output`` block was"""


def build_quote_client(config: KisQuoteTransportConfig) -> KisMockHttpClient:
    """The one sanctioned way to build a client for a real KIS quote poll (mirrors"""
    return KisMockHttpClient(
        rest_base=config.endpoint_rest_base,
        request_timeout_s=config.request_timeout_s,
        allow_plaintext_for_tests=config.allow_plaintext_for_tests,
    )


class KisQuoteObservationIntake:
    """The KIS 모의투자 quote :class:`~tos_runtime.marketfeed.ports.ObservationIntake` (module"""

    def __init__(
        self,
        *,
        config: KisQuoteTransportConfig,
        client: KisMockHttpClient,
        monotonic: MonotonicSource,
        evidence_sink: EvidenceRecorder,
        custody: CredentialCustody | None = None,
        credential_session: KisCredentialSession | None = None,
    ) -> None:
        """Wire this intake's dependencies (all injected — no ambient state)."""
        self._config = config
        self._client = client
        self._monotonic = monotonic
        self._evidence = evidence_sink
        if credential_session is None:
            if custody is None:
                raise KisQuoteAdapterError(
                    "KisQuoteObservationIntake: supply credential_session, or custody to build "
                    "a private one"
                )
            credential_session = KisCredentialSession(
                client=_TokenIssuingClientAdapter(client),
                custody=custody,
                app_key_scope=_KIS_MOCK_APP_KEY_SCOPE,
                app_secret_scope=_KIS_MOCK_APP_SECRET_SCOPE,
                monotonic=monotonic,
                token_path=config.token_path,
                token_reissue_min_interval_s=config.token_reissue_min_interval_s,
                evidence_sink=evidence_sink,
                pacing=KisPacing(
                    min_interval_ms=config.app_key_min_request_interval_ms,
                    wait_budget_ms=config.app_key_request_wait_budget_ms,
                ),
            )
        self._credential_session = credential_session
        self._last_content_digest: str | None = None
        self._pending_digest: str | None = None
        self._polled_once = False
        self._previous_after_as_of_ms: int | None = None

    def _commit_pending_if_consumed(self, after_as_of_ms: int | None) -> None:
        """Promote a pending digest to :attr:`_last_content_digest` iff the store's high-water"""
        advanced = (
            self._polled_once
            and after_as_of_ms is not None
            and (
                self._previous_after_as_of_ms is None
                or after_as_of_ms > self._previous_after_as_of_ms
            )
        )
        if advanced and self._pending_digest is not None:
            self._last_content_digest = self._pending_digest
            self._pending_digest = None
        self._polled_once = True
        self._previous_after_as_of_ms = after_as_of_ms

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> Sequence[MonotonicAnchoredObservation]:
        """Return a single fresh, not-yet-anchored observation for ``instrument``, or none"""
        if instrument != self._config.instrument:
            raise KisQuoteAdapterError(
                f"KisQuoteObservationIntake: poll() called for instrument {instrument!r} but "
                f"this config is scoped to {self._config.instrument!r} — refusing to serve the "
                "wrong instrument's quote"
            )
        self._commit_pending_if_consumed(after_as_of_ms)

        try:
            access_token = self._credential_session.ensure_token_string()
            requested_monotonic_ms, response = self._fetch_quote(access_token)
        except KisPacingRefused as exc:
            self._evidence(
                KIS_QUOTE_PACING_REFUSED_KIND,
                {"instrument": instrument, "detail": str(exc)},
            )
            return ()
        received_monotonic_ms = self._monotonic.now_ms()
        output = self._parse_output(response)
        fields = self._map_fields(output)

        content_digest = self._content_digest(fields)
        if content_digest == self._last_content_digest:
            return ()

        self._pending_digest = content_digest
        return (
            MonotonicAnchoredObservation(
                instrument=instrument,
                fields=fields,
                source_id=self._config.source_id,
                content_digest=content_digest,
                requested_monotonic_ms=requested_monotonic_ms,
                received_monotonic_ms=received_monotonic_ms,
            ),
        )

    def _fetch_quote(self, access_token: str) -> tuple[int, RawResponse]:
        """(mirrors ``KisMockTransport._send_order_with_credentials``'s own discipline) The app"""
        query = (
            f"FID_COND_MRKT_DIV_CODE={self._config.market_div_code}"
            f"&FID_INPUT_ISCD={self._config.instrument}"
        )
        with self._credential_session.app_credentials() as credentials:
            requested_monotonic_ms = self._monotonic.now_ms()
            return requested_monotonic_ms, self._client.get_quote(
                self._config.tr_id,
                query,
                access_token=access_token,
                app_key=credentials.app_key(),
                app_secret=credentials.app_secret(),
                path=self._config.quote_path,
            )

    def _parse_output(self, response: RawResponse) -> dict[str, object]:
        if response.json is None:
            raise KisQuoteMalformedResponse(
                f"KisQuoteObservationIntake: response body did not parse as a JSON object "
                f"(status={response.status})"
            )
        rt_cd = response.json.get("rt_cd")
        if rt_cd != "0":
            msg = response.json.get("msg1", "unknown error")
            raise KisQuoteRejected(
                f"KisQuoteObservationIntake: broker rejected the quote poll "
                f"(rt_cd={rt_cd!r}, msg1={msg!r})"
            )
        output = response.json.get("output")
        if not isinstance(output, dict):
            raise KisQuoteMalformedResponse(
                f"KisQuoteObservationIntake: response 'output' is not a JSON object "
                f"(got {type(output).__name__})"
            )
        return output

    def _map_fields(
        self, output: dict[str, object]
    ) -> tuple[tuple[str, ScalarValue], ...]:
        entries: list[tuple[str, Any]] = []
        for wire_key, field_key in self._config.field_mapping.items():
            if wire_key not in output:
                raise KisQuoteMalformedResponse(
                    f"KisQuoteObservationIntake: response 'output' is missing mapped field "
                    f"{wire_key!r} (-> {field_key!r})"
                )
            value = output[wire_key]
            if isinstance(value, _SCALAR_FIELD_TYPES):
                entries.append((field_key, value))
                continue
            raise KisQuoteMalformedResponse(
                f"KisQuoteObservationIntake: output[{wire_key!r}] has unsupported type "
                f"{type(value).__name__} (must be bool|int|float|str)"
            )
        return tuple(entries)

    @staticmethod
    def _content_digest(fields: tuple[tuple[str, ScalarValue], ...]) -> str:
        """A stable digest over the mapped field tuple — key-sorted so declaration order in"""
        canonical = json.dumps(sorted(fields), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _TokenIssuingClientAdapter:
    """Adapts :class:`~tos_runtime.transport.kis_mock.client.KisMockHttpClient` onto"""

    def __init__(self, client: KisMockHttpClient) -> None:
        self._client = client

    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str
    ) -> dict[str, object]:
        return self._client.issue_token(app_key, app_secret, path=path)


_conforms_to_observation_intake: type[ObservationIntake] = KisQuoteObservationIntake
_conforms_to_token_issuing_client: type[TokenIssuingClient] = _TokenIssuingClientAdapter
