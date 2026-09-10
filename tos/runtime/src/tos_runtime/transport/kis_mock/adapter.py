"""``KisMockTransport`` — the KIS 모의투자(paper) stock ``Transport`` implementation
(plan §2 결정 2/3/4/6/7(구조)/9).

**What this is not.** Wiring this adapter into the compose root, granting it a live
``nonlive_broker_consuming`` admission, and INSTANCE capability promotion are all explicitly out
of this slice (T1) — see the plan's §1 scope table and §4 slice table. Today, in this repo, a
send routed through the real gateway is refused three different ways before this class is ever
reached (plan §0 "핵심 귀결"): the Coordinator's live-scope precondition, the gateway's
``BROKER_RESOURCE_CONSUMING`` deferred-item gate, and the INSTANCE capability being
``PROHIBITED``. Nothing in this module changes any of that — it only makes sure that **when**
those three gates eventually open (Phase 5 / P0-2), the first MOCK order goes out through a
transport that already satisfies every structural contract the kernel's ``Transport`` boundary
demands, with zero code change on that day.

**Structural conformance with the kernel seam (design #34 §5.1).** ``send_once`` has EXACTLY the
:class:`tos.brokeradapter.Transport` Protocol's signature — this class is a genuine
``isinstance(..., Transport)`` (the Protocol is ``@runtime_checkable``) — and, like the
synthetic transport, holds no retry loop over its own ``send_once``.

**The seal is the sole input source (decision 3).** Every field this class reads to build the
outbound KIS request comes from the :class:`~tos.egressgw.SendSeal` the injected ``seal_lookup``
returns for this exact ``attempt_id`` — never a second, independent read of anything the caller
passed to ``send_once`` itself (``instrument_key``/``coordinates``/``quantity``/``price``/
``side``/``reference`` are accepted, per the Protocol's fixed signature, but this implementation
does not read them — only ``seal_digest`` is cross-checked, as a defence-in-depth echo check).
This mirrors the gateway's own step-18 discipline (``tos/src/tos/egressgw/gateway.py``): the
seal, not a second look at mutable state, is what step 18 hands the transport.

**A raised exception from this class is read by the gateway as ``TRANSPORT_RAISED``** (a
conservative halt — "a missing acknowledgement is not a non-acceptance", RFC-005 §11:322-323),
**never** as the gateway's own ``SEND_REFUSED``/binding-mismatch outcome — that gateway-level
halt reason is for the *gateway's own* pre-send checks, and this class is downstream of all of
them. Every one of this class's own raised exceptions (:class:`SendRefused`,
:class:`TokenStale`) is therefore, from the driver's perspective, an honest "unknown, try a new
attempt later" outcome — exactly the disposition decision 2/6 call for.

**Credential handling.** Every custody scope is loaded inside a ``with`` block and its bytes are
zeroed the moment this class is done needing them (:class:`~tos_runtime.custody.ports.
CredentialHandle`'s own zero-on-close discipline) — this class holds the account number
(``kis_mock.account``) only long enough to build one request body, and holds the app
key/secret (``kis_mock.app_key``/``kis_mock.app_secret``) only long enough to issue or use one
token. Neither ever appears in an evidence payload or an exception message (test suite scans
every evidence record this class emits for the literal secret bytes).

**Token lifecycle (decision 4).** ``token_reissue_min_interval_s`` governs the *token endpoint's
own* pacing — the minimum spacing between two ``issue_token`` calls (N-15's own finding: "토큰
1분 재발급 제한", a reissue-rate limit, not a token lifetime). Token *expiry* is instead read off
each token response's own ``expires_in`` seconds field. When a held token has expired **and**
the reissue cooldown has not yet elapsed since the last issuance attempt, this class raises
:class:`TokenStale` rather than reissuing inside the same attempt (decision 4: "재발급하지 않고
UNKNOWN") — a *later*, separate ``send_once`` call, once the cooldown has since elapsed, is free
to issue a fresh token.

Firewall: stdlib (``hashlib``, ``json``, ``time``) + ``tos.*`` (``tos.brokeradapter``,
``tos.egressgw``, ``tos.engine``, ``tos.ordering``) + ``tos_runtime.custody``/``tos_runtime.
time`` + this package's own sibling modules only. No third-party import, no ``os.environ``.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from decimal import Decimal
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
    KisMockClientError,
    KisMockConnectionError,
    KisMockHttpClient,
    KisMockTimeoutError,
    RawResponse,
)
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig

__all__ = [
    "EvidenceRecorder",
    "KisMockAdapterError",
    "KisMockTransport",
    "SealLookup",
    "SendRefused",
    "TokenStale",
]


class KisMockAdapterError(Exception):
    """A structural fault in this adapter's own configuration/wiring (e.g. an unrecognized
    ``side`` token) — distinct from :class:`SendRefused`/:class:`TokenStale`, which are the two
    *expected*, designed-for refusal paths."""


class SendRefused(Exception):
    """This attempt is refused before any network call — either no sealed outbound exists for
    it, or the freshly-built request bytes do not match ``SendSeal.request_bytes_digest``
    (decision 3). Zero network in either case. The gateway reads this as ``TRANSPORT_RAISED``
    (conservative, non-rejecting) — see the module docstring."""


class TokenStale(Exception):
    """The held token has expired and the reissue cooldown has not yet elapsed — this attempt
    does not reissue (decision 4). A later attempt, once the cooldown has elapsed, may.
    """


@runtime_checkable
class SealLookup(Protocol):
    """Resolves one attempt's :class:`~tos.egressgw.SendSeal` (built by the gateway before the
    step-16 claim, decision 3). The compose root supplies the real implementation in T2 — this
    package only depends on the shape."""

    def __call__(self, attempt_id: str) -> SendSeal | None:
        """Return the sealed outbound for ``attempt_id``, or ``None`` if none exists."""
        ...


@runtime_checkable
class EvidenceRecorder(Protocol):
    """Records one evidence entry. The compose root adapts this to the real evidence store in
    T2 — this package only depends on the shape (``record(kind, fields)``)."""

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        """Durably (from the caller's perspective) record one evidence entry.

        Args:
            kind: This adapter's own evidence-kind vocabulary (``TRANSPORT_SEND_REFUSED_NO_SEAL``
                / ``TRANSPORT_BINDING_MISMATCH`` / ``TRANSPORT_DRY_RUN`` / ``TRANSPORT_SEND`` /
                ``TRANSPORT_TOKEN_STALE``).
            fields: The record's own fields — never the secret bytes of any loaded credential,
                and never a bearer access token (module docstring).
        """
        ...


def _decimal_to_kis_string(value: CanonicalDecimal) -> str:
    """KIS requires numeric body fields as plain (non-scientific) decimal strings (N-17 memo:
    "ORD_QTY, ORD_UNPR 등을 String 으로 전달")."""
    return format(Decimal(value), "f")


def _canonical_json_bytes(fields: Mapping[str, str]) -> bytes:
    """Deterministic body-bytes serialization: sorted keys, no incidental whitespace."""
    return json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


class KisMockTransport:
    """The KIS 모의투자 stock-order ``Transport`` (see module docstring for the full contract)."""

    def __init__(
        self,
        *,
        config: KisMockTransportConfig,
        client: KisMockHttpClient,
        custody: CredentialCustody,
        app_key_scope: str,
        app_secret_scope: str,
        account_scope: str,
        monotonic: MonotonicSource,
        seal_lookup: SealLookup,
        evidence_sink: EvidenceRecorder,
    ) -> None:
        """Wire this transport's dependencies (all injected — no ambient state).

        Args:
            config: The fail-closed-loaded :class:`KisMockTransportConfig`.
            client: The stdlib HTTP shim.
            custody: The credential source (Phase 2's ``CredentialCustody`` Protocol) —
                scope-provisioning (whether ``app_key_scope``/etc. are actually loadable) is a
                compose-root/T2 concern; this class only calls ``custody.load(scope)``.
            app_key_scope: The custody scope name for the KIS app key.
            app_secret_scope: The custody scope name for the KIS app secret.
            account_scope: The custody scope name for the KIS account number (never sourced
                from the sealed authorization coordinates — the real account number is
                custody-loaded like any other credential, module docstring).
            monotonic: The injected monotonic clock (pacing + token bookkeeping — never
                ``time.time()``).
            seal_lookup: Resolves an attempt's :class:`~tos.egressgw.SendSeal`.
            evidence_sink: Records this adapter's own evidence entries.
        """
        self._config = config
        self._client = client
        self._custody = custody
        self._app_key_scope = app_key_scope
        self._app_secret_scope = app_secret_scope
        self._account_scope = account_scope
        self._monotonic = monotonic
        self._seal_lookup = seal_lookup
        self._evidence = evidence_sink

        self._access_token: str | None = None
        self._token_issued_at_ms: int | None = None
        self._token_expires_in_s: int | None = None
        self._last_token_issue_attempt_ms: int | None = None
        self._last_send_started_at_ms: int | None = None

    # -- send_once — the kernel Transport seam ----------------------------------------------

    def send_once(
        self,
        attempt: AttemptRequest,
        *,
        # Every kwarg below is accepted only to satisfy the kernel Transport Protocol's fixed
        # signature — this implementation reads its own outbound facts from the sealed
        # SendSeal instead (module docstring "the seal is the sole input source"), hence the
        # per-line ARG002 suppressions.
        instrument_key: InstrumentKey,  # noqa: ARG002
        coordinates: tuple[tuple[str, str | None], ...],  # noqa: ARG002
        quantity: CanonicalDecimal | None = None,  # noqa: ARG002
        price: CanonicalDecimal | None = None,  # noqa: ARG002
        side: str | None = None,  # noqa: ARG002
        reference: OrderingEvent = OrderingEvent(),  # noqa: ARG002
        seal_digest: str | None = None,  # noqa: ARG002
    ) -> EgressResultPayload:
        """Transmit ``attempt`` exactly once (or refuse before ever reaching the network).

        Every argument other than ``attempt`` is accepted only to satisfy the kernel
        ``Transport`` Protocol's fixed signature — this implementation reads its own outbound
        facts from the sealed :class:`~tos.egressgw.SendSeal`, never from these parameters
        (module docstring "the seal is the sole input source").

        Raises:
            SendRefused: No seal exists for ``attempt.attempt_id``, or the freshly-built request
                bytes do not match the seal's own ``request_bytes_digest`` — zero network either
                way.
            TokenStale: (live mode only) The held token has expired and the reissue cooldown has
                not elapsed since the last issuance attempt.
            KisMockAdapterError: The seal's ``outbound_side`` is not a recognized side token.
        """
        seal, tr_id, body_bytes = self._prepare_send(attempt)
        if self._config.mode == "dry_run":
            return self._dry_run_result(attempt.attempt_id, seal, tr_id, body_bytes)
        return self._perform_live_send(attempt.attempt_id, seal, tr_id, body_bytes)

    def _prepare_send(self, attempt: AttemptRequest) -> tuple[SendSeal, str, bytes]:
        """Resolve the seal, pick the TR id, and verify the digest binding (decision 3).

        Raises:
            SendRefused: No seal exists for this attempt, or the digest does not match — zero
                network either way.
        """
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
        body_fields = self._build_body_fields(seal)
        body_bytes = _canonical_json_bytes(body_fields)
        computed_digest = hashlib.sha256(body_bytes).hexdigest()

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
        """decision 9 — zero network; the request bytes were already built and digest-verified
        by :meth:`_prepare_send`."""
        self._evidence(
            "TRANSPORT_DRY_RUN",
            {
                "attempt_id": attempt_id,
                "seal_digest": seal.seal_digest,
                "request_bytes_digest": hashlib.sha256(body_bytes).hexdigest(),
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
        self, attempt_id: str, seal: SendSeal, tr_id: str, body_bytes: bytes
    ) -> EgressResultPayload:
        """decision 2/6 — exactly one POST, paced, with typed-fault mapping."""
        access_token, app_key, app_secret = self._ensure_token()
        self._enforce_pacing()
        t0 = self._monotonic.now_ms()
        try:
            response = self._client.post_order(
                tr_id,
                body_bytes,
                access_token=access_token,
                app_key=app_key,
                app_secret=app_secret,
                path=self._config.order_path,
            )
        except KisMockTimeoutError:
            self._last_send_started_at_ms = t0
            return self._finish(
                attempt_id=attempt_id,
                seal=seal,
                kind=EgressResultKind.TIMEOUT,
                broker_execution_id=None,
                t0=t0,
                extra={"reason": "socket_timeout"},
                status=None,
            )
        except KisMockConnectionError:
            self._last_send_started_at_ms = t0
            return self._finish(
                attempt_id=attempt_id,
                seal=seal,
                kind=EgressResultKind.UNKNOWN,
                broker_execution_id=None,
                t0=t0,
                extra={"reason": "connection_error"},
                status=None,
            )
        self._last_send_started_at_ms = t0
        kind, broker_execution_id, extra = self._map_response(response)
        return self._finish(
            attempt_id=attempt_id,
            seal=seal,
            kind=kind,
            broker_execution_id=broker_execution_id,
            t0=t0,
            extra=extra,
            status=response.status,
        )

    # -- body construction (decision 3) ------------------------------------------------------

    def _build_body_fields(self, seal: SendSeal) -> dict[str, str]:
        """Build the KIS wire body from the seal's own fields + custody's account number —
        never from a code literal (module docstring's "known T1 gap" in
        :mod:`tos_runtime.transport.kis_mock.config` lists which of the nine ``order_cash``
        fields this can populate today)."""
        with self._custody.load(self._account_scope) as handle:
            account_value = handle.value().decode("utf-8").strip()
        dynamic_sources: dict[str, str] = {
            "account": account_value,
            "instrument": seal.instrument_key.instrument,
            "quantity": _decimal_to_kis_string(seal.outbound_quantity),
            "price": _decimal_to_kis_string(seal.outbound_price),
        }
        fields: dict[str, str] = {}
        for source_name, wire_name in self._config.field_map.items():
            if source_name not in dynamic_sources:
                raise KisMockAdapterError(
                    f"KisMockTransport: field_map source {source_name!r} is not a recognized "
                    "dynamic value — the config loader should have refused this at boot"
                )
            fields[wire_name] = dynamic_sources[source_name]
        return fields

    def _tr_id_for_side(self, side: str) -> str:
        if side == "BUY":
            return self._config.tr_id_buy
        if side == "SELL":
            return self._config.tr_id_sell
        raise KisMockAdapterError(
            f"KisMockTransport: unrecognized side {side!r} — expected 'BUY' or 'SELL'"
        )

    # -- token lifecycle (decision 4) --------------------------------------------------------

    def _ensure_token(self) -> tuple[str, bytes, bytes]:
        """Return ``(access_token, app_key, app_secret)`` for the send about to happen.

        Raises:
            TokenStale: The held token (or the absence of one) is stale and the reissue cooldown
                has not elapsed since the last issuance attempt.
        """
        now = self._monotonic.now_ms()
        needs_fresh = self._access_token is None or (
            self._token_issued_at_ms is not None
            and self._token_expires_in_s is not None
            and (now - self._token_issued_at_ms) >= self._token_expires_in_s * 1000
        )
        if not needs_fresh:
            assert self._access_token is not None
            with (
                self._custody.load(self._app_key_scope) as key_handle,
                self._custody.load(self._app_secret_scope) as secret_handle,
            ):
                return self._access_token, key_handle.value(), secret_handle.value()

        if (
            self._last_token_issue_attempt_ms is not None
            and (now - self._last_token_issue_attempt_ms)
            < self._config.token_reissue_min_interval_s * 1000
        ):
            self._evidence(
                "TRANSPORT_TOKEN_STALE",
                {
                    "reissue_cooldown_s": self._config.token_reissue_min_interval_s,
                    "elapsed_ms": now - self._last_token_issue_attempt_ms,
                },
            )
            raise TokenStale(
                "KisMockTransport: token is stale/absent and the reissue cooldown "
                f"({self._config.token_reissue_min_interval_s}s) has not elapsed since the "
                "last issuance attempt — refusing to reissue within this attempt (decision 4)"
            )

        self._last_token_issue_attempt_ms = now
        with (
            self._custody.load(self._app_key_scope) as key_handle,
            self._custody.load(self._app_secret_scope) as secret_handle,
        ):
            app_key = key_handle.value()
            app_secret = secret_handle.value()
            body = self._client.issue_token(
                app_key, app_secret, path=self._config.token_path
            )
            access_token = body.get("access_token")
            expires_in = body.get("expires_in")
            if not isinstance(access_token, str) or not access_token:
                raise KisMockClientError(
                    "KisMockTransport: token response missing a usable access_token"
                )
            if (
                not isinstance(expires_in, int)
                or isinstance(expires_in, bool)
                or expires_in <= 0
            ):
                raise KisMockClientError(
                    "KisMockTransport: token response missing a usable expires_in"
                )
            self._access_token = access_token
            self._token_expires_in_s = expires_in
            self._token_issued_at_ms = self._monotonic.now_ms()
            return self._access_token, app_key, app_secret

    # -- pacing (decision 6) -----------------------------------------------------------------

    def _enforce_pacing(self) -> None:
        """Block, if needed, so two order transmissions are at least ``min_send_interval_ms``
        apart on the injected monotonic clock — measured from the START of the previous send,
        never from a wall clock. The wait ends BEFORE ``t0`` is taken by the caller, so a
        transmission's own recorded start instant never absorbs the pacing delay (decision 6:
        "대기는 전송 직전 종료, t0 오염 0")."""
        if self._last_send_started_at_ms is None:
            return
        elapsed = self._monotonic.now_ms() - self._last_send_started_at_ms
        remaining_ms = self._config.min_send_interval_ms - elapsed
        if remaining_ms > 0:
            time.sleep(remaining_ms / 1000.0)

    # -- response mapping (decision 2) -------------------------------------------------------

    def _map_response(
        self, response: RawResponse
    ) -> tuple[EgressResultKind, str | None, dict[str, Any]]:
        """Map one KIS HTTP response to ``(kind, broker_execution_id, evidence_extra)``.

        5xx and an unparseable body are ``UNKNOWN`` (never a rejection — RFC-005 §11:322-323);
        ``rt_cd == "0"`` with a present ``ODNO`` is ``ACK``; anything else with a parseable body
        is ``REJECT`` (a throttle response, KIS's own ``EGW00201``, is still a ``REJECT`` — this
        adapter never retries it, decision 6 — but its evidence carries ``reason=throttled``).
        """
        if response.status >= 500:
            return EgressResultKind.UNKNOWN, None, {"reason": "server_error"}
        if response.json is None:
            return EgressResultKind.UNKNOWN, None, {"reason": "malformed_json"}
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
        )
