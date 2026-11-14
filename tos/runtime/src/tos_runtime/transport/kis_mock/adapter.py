"""``KisMockTransport`` — the KIS 모의투자(paper) stock ``Transport`` implementation"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from tos.canonical import CanonicalDecimal
from tos.egressgw import SendSeal
from tos.engine import (
    AttemptRequest,
    EgressResultKind,
    EgressResultPayload,
    InstrumentKey,
)
from tos.ordering import OrderingEvent

from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.client import (
    KisMockConnectionError,
    KisMockHttpClient,
    KisMockTimeoutError,
    RawResponse,
)
from tos_runtime.transport.kis_mock.codec import KisOrderWireCodec
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSession
from tos_runtime.transport.kis_mock.pacer import KisPacing, KisPacingRefused
from tos_runtime.transport.kis_mock.token import TokenStale

__all__ = [
    "EvidenceRecorder",
    "KisMockAdapterError",
    "KisMockTransport",
    "SealLookup",
    "SendRefused",
    "TokenStale",
]


class KisMockAdapterError(Exception):
    """A structural fault in this adapter's own configuration/wiring (e.g. an unrecognized"""


class SendRefused(Exception):
    """This attempt is refused before any network call — either no sealed outbound exists for"""


@runtime_checkable
class SealLookup(Protocol):
    """Resolves one attempt's :class:`~tos.egressgw.SendSeal` (built by the gateway before the"""

    def __call__(self, attempt_id: str) -> SendSeal | None:
        """Return the sealed outbound for ``attempt_id``, or ``None`` if none exists."""
        ...


@runtime_checkable
class EvidenceRecorder(Protocol):
    """Records one evidence entry. The compose root adapts this to the real evidence store in"""

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        """Durably (from the caller's perspective) record one evidence entry."""
        ...


class KisMockTransport:
    """The KIS 모의투자 stock-order ``Transport`` (see module docstring for the full contract)."""

    def __init__(
        self,
        *,
        config: KisMockTransportConfig,
        client: KisMockHttpClient,
        monotonic: MonotonicSource,
        seal_lookup: SealLookup,
        evidence_sink: EvidenceRecorder,
        custody: CredentialCustody | None = None,
        app_key_scope: str | None = None,
        app_secret_scope: str | None = None,
        trading_date_now: Callable[[], str | None] | None = None,
        credential_session: KisCredentialSession | None = None,
    ) -> None:
        """Wire this transport's dependencies (all injected — no ambient state)."""
        self._config = config
        self._client = client
        self._monotonic = monotonic
        self._seal_lookup = seal_lookup
        self._evidence = evidence_sink
        self._trading_date_now = trading_date_now
        if credential_session is None:
            if custody is None or app_key_scope is None or app_secret_scope is None:
                raise KisMockAdapterError(
                    "KisMockTransport: supply credential_session, or custody + app_key_scope "
                    "+ app_secret_scope to build a private one"
                )
            credential_session = KisCredentialSession(
                client=client,
                custody=custody,
                app_key_scope=app_key_scope,
                app_secret_scope=app_secret_scope,
                monotonic=monotonic,
                token_path=config.token_path,
                token_reissue_min_interval_s=config.token_reissue_min_interval_s,
                evidence_sink=evidence_sink,
                pacing=KisPacing(
                    min_interval_ms=config.min_send_interval_ms,
                    wait_budget_ms=config.app_key_request_wait_budget_ms,
                ),
            )
        self._credential_session = credential_session

    def send_once(
        self,
        attempt: AttemptRequest,
        *,
        instrument_key: InstrumentKey,  # noqa: ARG002
        coordinates: tuple[tuple[str, str | None], ...],  # noqa: ARG002
        quantity: CanonicalDecimal | None = None,  # noqa: ARG002
        price: CanonicalDecimal | None = None,  # noqa: ARG002
        side: str | None = None,  # noqa: ARG002
        reference: OrderingEvent = OrderingEvent(),  # noqa: ARG002
        seal_digest: str | None = None,  # noqa: ARG002
    ) -> EgressResultPayload:
        """Transmit ``attempt`` exactly once (or refuse before ever reaching the network)."""
        seal, tr_id, body_bytes = self._prepare_send(attempt)
        if self._config.mode == "dry_run":
            return self._dry_run_result(attempt.attempt_id, seal, tr_id, body_bytes)
        trading_date = self._stamp_trading_date()
        return self._perform_live_send(
            attempt.attempt_id, seal, tr_id, body_bytes, trading_date=trading_date
        )

    def _prepare_send(self, attempt: AttemptRequest) -> tuple[SendSeal, str, bytes]:
        """Resolve the seal, pick the TR id, and verify the digest binding (decision 3)."""
        seal = self._seal_lookup(attempt.attempt_id)
        if seal is None:
            self._evidence(
                "TRANSPORT_SEND_REFUSED_NO_SEAL", {"attempt_id": attempt.attempt_id}
            )
            raise SendRefused(
                f"KisMockTransport.send_once: no SendSeal available for attempt "
                f"{attempt.attempt_id!r} — zero network"
            )

        tr_id = self._tr_id_for_side(seal.outbound_side)
        body_bytes = KisOrderWireCodec.encode(
            seal,
            field_map=self._config.field_map,
            static_body_fields=self._config.static_body_fields,
            price_scale=self._config.price_scale,
        )
        computed_digest = KisOrderWireCodec.digest(body_bytes)

        if computed_digest != seal.request_bytes_digest:
            self._evidence(
                "TRANSPORT_BINDING_MISMATCH",
                {
                    "attempt_id": attempt.attempt_id,
                    "seal_digest": seal.seal_digest,
                    "computed_request_bytes_digest": computed_digest,
                    "sealed_request_bytes_digest": seal.request_bytes_digest,
                },
            )
            raise SendRefused(
                f"KisMockTransport.send_once: request_bytes_digest mismatch for attempt "
                f"{attempt.attempt_id!r} — zero network (decision 3)"
            )
        return seal, tr_id, body_bytes

    def _dry_run_result(
        self, attempt_id: str, seal: SendSeal, tr_id: str, body_bytes: bytes
    ) -> EgressResultPayload:
        """decision 9 — zero network; the request bytes were already built and digest-verified"""
        self._evidence(
            "TRANSPORT_DRY_RUN",
            {
                "attempt_id": attempt_id,
                "seal_digest": seal.seal_digest,
                "request_bytes_digest": KisOrderWireCodec.digest(body_bytes),
                "tr_id": tr_id,
            },
        )
        return EgressResultPayload(
            instrument_key=seal.instrument_key,
            attempt_id=attempt_id,
            kind=EgressResultKind.UNKNOWN,
            broker_execution_id=None,
            reference=seal.reference,
        )

    def _perform_live_send(
        self,
        attempt_id: str,
        seal: SendSeal,
        tr_id: str,
        body_bytes: bytes,
        *,
        trading_date: str | None,
    ) -> EgressResultPayload:
        """decision 2/6 — exactly one POST, paced by the app key's pacer, with typed-fault"""
        try:
            access_token = self._ensure_token_string()
        except KisPacingRefused as exc:
            return self._pacing_refused(
                attempt_id, seal, exc, trading_date=trading_date
            )
        try:
            with self._credential_session.app_credentials() as credentials:
                t0 = self._monotonic.now_ms()
                response = self._client.post_order(
                    tr_id,
                    body_bytes,
                    access_token=access_token,
                    app_key=credentials.app_key(),
                    app_secret=credentials.app_secret(),
                    path=self._config.order_path,
                )
        except KisPacingRefused as exc:
            return self._pacing_refused(
                attempt_id, seal, exc, trading_date=trading_date
            )
        except KisMockTimeoutError:
            return self._finish(
                attempt_id=attempt_id,
                seal=seal,
                kind=EgressResultKind.TIMEOUT,
                broker_execution_id=None,
                t0=t0,
                extra={"reason": "socket_timeout"},
                status=None,
                trading_date=trading_date,
            )
        except KisMockConnectionError:
            return self._finish(
                attempt_id=attempt_id,
                seal=seal,
                kind=EgressResultKind.UNKNOWN,
                broker_execution_id=None,
                t0=t0,
                extra={"reason": "connection_error"},
                status=None,
                trading_date=trading_date,
            )
        kind, broker_execution_id, extra = self._map_response(response)
        return self._finish(
            attempt_id=attempt_id,
            seal=seal,
            kind=kind,
            broker_execution_id=broker_execution_id,
            t0=t0,
            extra=extra,
            status=response.status,
            trading_date=trading_date,
        )

    def _pacing_refused(
        self,
        attempt_id: str,
        seal: SendSeal,
        exc: KisPacingRefused,
        *,
        trading_date: str | None,
    ) -> EgressResultPayload:
        """The app key's pacer refused this attempt's slot: nothing was sent, so ``REJECT``"""
        return self._finish(
            attempt_id=attempt_id,
            seal=seal,
            kind=EgressResultKind.REJECT,
            broker_execution_id=None,
            t0=self._monotonic.now_ms(),
            extra={
                "reason": "throttled",
                "throttle_source": "app_key_pacer",
                "sent": False,
                "detail": str(exc),
            },
            status=None,
            trading_date=trading_date,
        )

    def _tr_id_for_side(self, side: str) -> str:
        if side == "BUY":
            return self._config.tr_id_buy
        if side == "SELL":
            return self._config.tr_id_sell
        raise KisMockAdapterError(
            f"KisMockTransport: unrecognized side {side!r} — expected 'BUY' or 'SELL'"
        )

    def _ensure_token_string(self) -> str:
        """Return the bearer access token string for the send about to happen."""
        return self._credential_session.ensure_token_string()

    def _map_response(
        self, response: RawResponse
    ) -> tuple[EgressResultKind, str | None, dict[str, Any]]:
        """Map one KIS HTTP response to ``(kind, broker_execution_id, evidence_extra)``."""
        if response.status >= 500:
            return EgressResultKind.UNKNOWN, None, {"reason": "server_error"}
        if response.json is None:
            return EgressResultKind.UNKNOWN, None, {"reason": "malformed_json"}
        if "rt_cd" not in response.json:
            return EgressResultKind.UNKNOWN, None, {"reason": "rt_cd_absent"}
        rt_cd = response.json.get("rt_cd")
        if rt_cd == "0":
            output = response.json.get("output")
            odno = output.get("ODNO") if isinstance(output, dict) else None
            if not odno:
                return EgressResultKind.UNKNOWN, None, {"reason": "ack_missing_odno"}
            return EgressResultKind.ACK, odno, {}
        msg_cd = response.json.get("msg_cd")
        extra: dict[str, Any] = {"msg_cd": msg_cd, "msg1": response.json.get("msg1")}
        if msg_cd == "EGW00201":
            extra["reason"] = "throttled"
        return EgressResultKind.REJECT, None, extra

    def _finish(
        self,
        *,
        attempt_id: str,
        seal: SendSeal,
        kind: EgressResultKind,
        broker_execution_id: str | None,
        t0: int,
        extra: Mapping[str, Any],
        status: int | None,
        trading_date: str | None,
    ) -> EgressResultPayload:
        latency_ms = self._monotonic.now_ms() - t0
        self._evidence(
            "TRANSPORT_SEND",
            {
                "attempt_id": attempt_id,
                "seal_digest": seal.seal_digest,
                "kind": kind.value,
                "status": status,
                "latency_ms": latency_ms,
                **extra,
            },
        )
        return EgressResultPayload(
            instrument_key=seal.instrument_key,
            attempt_id=attempt_id,
            kind=kind,
            broker_execution_id=broker_execution_id,
            reference=seal.reference,
            trading_date=(trading_date if broker_execution_id is not None else None),
        )

    def _stamp_trading_date(self) -> str | None:
        """The injected trading date, or ``None``. Called at send start, so a failure here must"""
        if self._trading_date_now is None:
            return None
        try:
            return self._trading_date_now()
        except Exception:  # noqa: BLE001 - the ACK must reach the inbox regardless
            return None
