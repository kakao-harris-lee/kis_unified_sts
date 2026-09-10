"""``KisMockTransport`` tests — ACK/REJECT/UNKNOWN/TIMEOUT mapping, digest binding, pacing,
token lifecycle, dry-run, and negative-greps (plan §4 슬라이스 T1)."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from tos.brokeradapter import Transport
from tos.engine import EgressResultKind
from tos_runtime.transport.kis_mock.adapter import (
    KisMockAdapterError,
    KisMockTransport,
    SendRefused,
    TokenStale,
)
from tos_runtime.transport.kis_mock.client import KisMockHttpClient
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig

from ._fake_kis_server import FakeKisServer
from ._fakes import (
    FakeMonotonicSource,
    InMemoryCredentialCustody,
    RecordingEvidenceSink,
    make_seal_lookup,
)
from ._seal_fixtures import (
    ACCOUNT,
    DEFAULT_FIELD_MAP,
    DEFAULT_STATIC_BODY_FIELDS,
    build_seal,
)

ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
TOKEN_PATH = "/oauth2/tokenP"
FIELD_MAP = DEFAULT_FIELD_MAP
STATIC_BODY_FIELDS = DEFAULT_STATIC_BODY_FIELDS
APP_KEY_SCOPE = "kis_mock.app_key"
APP_SECRET_SCOPE = "kis_mock.app_secret"


@pytest.fixture
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _config(server: FakeKisServer, **overrides: Any) -> KisMockTransportConfig:
    base = {
        "mode": "live",
        "endpoint_rest_base": server.rest_base,
        "order_path": ORDER_PATH,
        "token_path": TOKEN_PATH,
        "tr_id_buy": "VTTC0012U",
        "tr_id_sell": "VTTC0011U",
        "field_map": FIELD_MAP,
        "static_body_fields": STATIC_BODY_FIELDS,
        "min_send_interval_ms": 1000,
        "token_reissue_min_interval_s": 60,
        "request_timeout_s": 2.0,
        "allow_plaintext_for_tests": True,
    }
    base.update(overrides)
    return KisMockTransportConfig(**base)


def _build_transport(
    server: FakeKisServer,
    *,
    config: KisMockTransportConfig | None = None,
    monotonic: FakeMonotonicSource | None = None,
    custody: InMemoryCredentialCustody | None = None,
    evidence: RecordingEvidenceSink | None = None,
    seals: dict[str, Any] | None = None,
) -> tuple[
    KisMockTransport,
    RecordingEvidenceSink,
    InMemoryCredentialCustody,
    FakeMonotonicSource,
]:
    cfg = config or _config(server)
    client = KisMockHttpClient(
        rest_base=cfg.endpoint_rest_base,
        request_timeout_s=cfg.request_timeout_s,
        allow_plaintext_for_tests=cfg.allow_plaintext_for_tests,
    )
    mono = monotonic or FakeMonotonicSource()
    # (review F2) No "account" custody scope — the account number is sourced exclusively from
    # the sealed outbound coordinate (SendSeal.account), never custody.
    cust = custody or InMemoryCredentialCustody(
        {
            APP_KEY_SCOPE: b"app-key-value",
            APP_SECRET_SCOPE: b"app-secret-value",
        }
    )
    ev = evidence or RecordingEvidenceSink()
    seal_map = seals if seals is not None else {}
    transport = KisMockTransport(
        config=cfg,
        client=client,
        custody=cust,
        app_key_scope=APP_KEY_SCOPE,
        app_secret_scope=APP_SECRET_SCOPE,
        monotonic=mono,
        seal_lookup=make_seal_lookup(seal_map),
        evidence_sink=ev,
    )
    return transport, ev, cust, mono


def _attempt(attempt_id: str = "attempt-1"):
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
    from tos.engine import build_attempt_request
    from tos.ordering import OrderingEvent

    scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
    return build_attempt_request(
        conformance_proof_digest=f"proof-{attempt_id}",
        action_flow_permit_identity=f"permit-{attempt_id}",
        reference=OrderingEvent(event_id=f"ev-{attempt_id}", quorum_commit_index=1),
        scheme=scheme,
    )


def _send(transport: KisMockTransport, attempt):
    """Call ``send_once`` with placeholder Protocol arguments — the adapter reads only the
    seal, never these (module docstring), so their exact values are immaterial here."""
    from tos.engine import InstrumentKey

    return transport.send_once(
        attempt,
        instrument_key=InstrumentKey(account="unused", instrument="unused"),
        coordinates=(),
        quantity=None,
        price=None,
        side=None,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_the_adapter_satisfies_the_transport_protocol_structurally(
    server: FakeKisServer,
) -> None:
    transport, *_ = _build_transport(server)
    assert isinstance(transport, Transport)


# ---------------------------------------------------------------------------
# missing seal
# ---------------------------------------------------------------------------


def test_a_missing_seal_raises_send_refused_with_zero_network(
    server: FakeKisServer,
) -> None:
    transport, evidence, _, _ = _build_transport(server, seals={})
    attempt = _attempt("no-seal")
    with pytest.raises(SendRefused):
        _send(transport, attempt)
    assert server.all_requests == []
    assert evidence.of_kind("TRANSPORT_SEND_REFUSED_NO_SEAL") == [
        {"attempt_id": attempt.attempt_id}
    ]


# ---------------------------------------------------------------------------
# digest binding (decision 3)
# ---------------------------------------------------------------------------


def test_a_digest_mismatch_raises_send_refused_with_zero_network(
    server: FakeKisServer,
) -> None:
    attempt = _attempt("mismatch-1")
    seal = build_seal(attempt_id=attempt.attempt_id, request_bytes_digest="0" * 64)
    transport, evidence, _, _ = _build_transport(
        server, seals={attempt.attempt_id: seal}
    )
    with pytest.raises(SendRefused):
        _send(transport, attempt)
    assert server.all_requests == []
    (record,) = evidence.of_kind("TRANSPORT_BINDING_MISMATCH")
    assert record["sealed_request_bytes_digest"] == "0" * 64
    assert record["computed_request_bytes_digest"] != "0" * 64


def test_a_matching_digest_proceeds_to_dry_run(server: FakeKisServer) -> None:
    attempt = _attempt("match-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    cfg = _config(server, mode="dry_run")
    transport, evidence, _, _ = _build_transport(
        server, config=cfg, seals={attempt.attempt_id: seal}
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.UNKNOWN
    assert server.all_requests == []
    assert len(evidence.of_kind("TRANSPORT_DRY_RUN")) == 1


# ---------------------------------------------------------------------------
# dry_run (decision 9)
# ---------------------------------------------------------------------------


def test_dry_run_never_touches_the_network(server: FakeKisServer) -> None:
    attempt = _attempt("dry-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    cfg = _config(server, mode="dry_run")
    transport, evidence, custody, _ = _build_transport(
        server, config=cfg, seals={attempt.attempt_id: seal}
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.UNKNOWN
    assert result.broker_execution_id is None
    assert server.all_requests == []
    (record,) = evidence.of_kind("TRANSPORT_DRY_RUN")
    assert record["attempt_id"] == attempt.attempt_id
    assert record["tr_id"] == "VTTC0012U"
    # (review F2) the account number is sourced from the seal, never custody — and dry_run
    # never reaches token issuance either — so NO custody scope is loaded at all.
    assert custody.load_calls == []


# ---------------------------------------------------------------------------
# live path — response mapping (decision 2)
# ---------------------------------------------------------------------------


def _live_ack_setup(server: FakeKisServer, *, side: str = "BUY"):
    attempt = _attempt(f"ack-{side}")
    seal = build_seal(attempt_id=attempt.attempt_id, side=side)
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(
        ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "msg_cd": "APBK0013",
            "msg1": "정상처리",
            "output": {"ODNO": "ODNO-1"},
        },
    )
    return attempt, seal


def test_ack_path(server: FakeKisServer) -> None:
    attempt, seal = _live_ack_setup(server)
    transport, evidence, _, _ = _build_transport(
        server, seals={attempt.attempt_id: seal}
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.ACK
    assert result.broker_execution_id == "ODNO-1"
    assert len(server.requests_for(ORDER_PATH)) == 1
    (record,) = evidence.of_kind("TRANSPORT_SEND")
    assert record["kind"] == "ACK"
    assert record["seal_digest"] == seal.seal_digest


def test_sell_side_selects_the_sell_tr_id(server: FakeKisServer) -> None:
    attempt, seal = _live_ack_setup(server, side="SELL")
    transport, _, _, _ = _build_transport(server, seals={attempt.attempt_id: seal})
    _send(transport, attempt)
    (request,) = server.requests_for(ORDER_PATH)
    assert request.headers["tr_id"] == "VTTC0011U"


def test_an_unrecognized_side_raises_adapter_error(server: FakeKisServer) -> None:
    attempt = _attempt("bad-side")
    seal = build_seal(attempt_id=attempt.attempt_id, side="HOLD")
    transport, _, _, _ = _build_transport(server, seals={attempt.attempt_id: seal})
    with pytest.raises(KisMockAdapterError):
        _send(transport, attempt)
    assert server.all_requests == []


def test_reject_path_with_msg_cd(server: FakeKisServer) -> None:
    attempt = _attempt("reject-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(
        ORDER_PATH,
        status=200,
        body={"rt_cd": "1", "msg_cd": "APBK0919", "msg1": "주문가능금액 부족"},
    )
    transport, evidence, _, _ = _build_transport(
        server, seals={attempt.attempt_id: seal}
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.REJECT
    assert result.broker_execution_id is None
    (record,) = evidence.of_kind("TRANSPORT_SEND")
    assert record["kind"] == "REJECT"
    assert record["msg_cd"] == "APBK0919"


def test_throttle_reject_carries_a_throttled_reason(server: FakeKisServer) -> None:
    attempt = _attempt("throttle-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(
        ORDER_PATH,
        status=200,
        body={"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "초당 거래건수를 초과"},
    )
    transport, evidence, _, _ = _build_transport(
        server,
        config=_config(server, min_send_interval_ms=1),
        seals={attempt.attempt_id: seal},
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.REJECT
    (record,) = evidence.of_kind("TRANSPORT_SEND")
    assert record["reason"] == "throttled"


def test_5xx_maps_to_unknown_never_reject(server: FakeKisServer) -> None:
    attempt = _attempt("5xx-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(ORDER_PATH, status=503, body={"msg1": "internal error"})
    transport, evidence, _, _ = _build_transport(
        server, seals={attempt.attempt_id: seal}
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.UNKNOWN
    (record,) = evidence.of_kind("TRANSPORT_SEND")
    assert record["status"] == 503


def test_connection_reset_maps_to_unknown(server: FakeKisServer) -> None:
    attempt = _attempt("reset-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(ORDER_PATH, status=200, body=None, reset=True)
    transport, evidence, _, _ = _build_transport(
        server, seals={attempt.attempt_id: seal}
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.UNKNOWN
    (record,) = evidence.of_kind("TRANSPORT_SEND")
    assert record["reason"] == "connection_error"


def test_socket_timeout_maps_to_timeout(server: FakeKisServer) -> None:
    attempt = _attempt("timeout-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(ORDER_PATH, status=200, body={"rt_cd": "0"}, delay_s=0.3)
    cfg = _config(server, request_timeout_s=0.05)
    transport, evidence, _, _ = _build_transport(
        server, config=cfg, seals={attempt.attempt_id: seal}
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.TIMEOUT
    (record,) = evidence.of_kind("TRANSPORT_SEND")
    assert record["kind"] == "TIMEOUT"


def test_malformed_json_maps_to_unknown(server: FakeKisServer) -> None:
    attempt = _attempt("malformed-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(ORDER_PATH, status=200, body=None)
    transport, evidence, _, _ = _build_transport(
        server, seals={attempt.attempt_id: seal}
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.UNKNOWN
    (record,) = evidence.of_kind("TRANSPORT_SEND")
    assert record["reason"] == "malformed_json"


def test_rt_cd_absent_maps_to_unknown_never_reject(server: FakeKisServer) -> None:
    """(review F4) A 200 response whose JSON body is a well-formed dict but carries no
    ``rt_cd`` key at all must be UNKNOWN, never REJECT — absence is not non-acceptance
    (RFC-005 §11:322-323). Before this fix, an absent ``rt_cd`` fell through to
    ``rt_cd == "0"`` being False and was mis-mapped to REJECT."""
    attempt = _attempt("no-rtcd-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(ORDER_PATH, status=200, body={"some_other_field": "x"})
    transport, evidence, _, _ = _build_transport(
        server, seals={attempt.attempt_id: seal}
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.UNKNOWN
    (record,) = evidence.of_kind("TRANSPORT_SEND")
    assert record["reason"] == "rt_cd_absent"


def test_an_empty_dict_body_maps_to_unknown_never_reject(server: FakeKisServer) -> None:
    """(review F4) ``{}`` is a well-formed dict with no ``rt_cd`` key — same rule as above."""
    attempt = _attempt("empty-dict-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(ORDER_PATH, status=200, body={})
    transport, evidence, _, _ = _build_transport(
        server, seals={attempt.attempt_id: seal}
    )
    result = _send(transport, attempt)
    assert result.kind is EgressResultKind.UNKNOWN
    (record,) = evidence.of_kind("TRANSPORT_SEND")
    assert record["reason"] == "rt_cd_absent"


# ---------------------------------------------------------------------------
# account sourcing (review F2) — CANO comes from the sealed outbound coordinate, never custody
# ---------------------------------------------------------------------------


def test_account_field_is_sourced_from_the_seal_never_custody(
    server: FakeKisServer,
) -> None:
    attempt, seal = _live_ack_setup(server)
    assert seal.account == ACCOUNT
    # A custody double that does NOT provision any "account"-shaped scope at all — if the
    # adapter tried to load one, this would raise CustodyScopeNotProvisioned.
    custody = InMemoryCredentialCustody(
        {
            APP_KEY_SCOPE: b"app-key-value",
            APP_SECRET_SCOPE: b"app-secret-value",
        }
    )
    transport, _, cust, _ = _build_transport(
        server, custody=custody, seals={attempt.attempt_id: seal}
    )
    _send(transport, attempt)
    (request,) = server.requests_for(ORDER_PATH)
    import json as _json

    body = _json.loads(request.body)
    assert body["CANO"] == seal.account
    # Only app_key/app_secret are ever loaded (once for token issuance, once for the order
    # call itself — review F5's narrow with-block discipline reloads fresh each network call)
    # — never anything account-shaped.
    assert set(cust.load_calls) == {APP_KEY_SCOPE, APP_SECRET_SCOPE}
    assert not any("account" in scope for scope in cust.load_calls)


def test_a_different_custody_bound_value_never_leaks_into_the_body(
    server: FakeKisServer,
) -> None:
    """A custody double bound to a DIFFERENT (unrelated) value than the seal's own account must
    never leak into the body — because the adapter never even asks custody about it."""
    attempt, seal = _live_ack_setup(server)
    custody = InMemoryCredentialCustody(
        {
            APP_KEY_SCOPE: b"app-key-value",
            APP_SECRET_SCOPE: b"app-secret-value",
            "some.other.scope": b"a-completely-different-account-value",
        }
    )
    transport, _, _, _ = _build_transport(
        server, custody=custody, seals={attempt.attempt_id: seal}
    )
    _send(transport, attempt)
    (request,) = server.requests_for(ORDER_PATH)
    assert b"a-completely-different-account-value" not in request.body


# ---------------------------------------------------------------------------
# pacing (decision 6)
# ---------------------------------------------------------------------------


def test_pacing_waits_before_the_second_send_and_t0_is_taken_after_the_wait(
    server: FakeKisServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tos_runtime.transport.kis_mock.adapter as adapter_module

    sleeps: list[float] = []

    mono = FakeMonotonicSource(start_ms=0)

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        # Simulate real elapsed time passing during the (patched-out) sleep.
        mono.advance(int(seconds * 1000))

    monkeypatch.setattr(adapter_module.time, "sleep", fake_sleep)

    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(
        ORDER_PATH, status=200, body={"rt_cd": "0", "output": {"ODNO": "1"}}
    )

    cfg = _config(server, min_send_interval_ms=1000)
    transport, _, _, _ = _build_transport(server, config=cfg, monotonic=mono)

    attempt1 = _attempt("pace-1")
    seal1 = build_seal(attempt_id=attempt1.attempt_id)
    transport._seal_lookup = make_seal_lookup({attempt1.attempt_id: seal1})  # type: ignore[attr-defined]
    _send(transport, attempt1)
    assert sleeps == []  # first send never waits

    mono.advance(200)  # only 200ms have passed — well under the 1000ms floor

    attempt2 = _attempt("pace-2")
    seal2 = build_seal(attempt_id=attempt2.attempt_id)
    transport._seal_lookup = make_seal_lookup({attempt2.attempt_id: seal2})  # type: ignore[attr-defined]
    before_second_send_wall = mono.now_ms()
    _send(transport, attempt2)

    assert sleeps == [
        pytest.approx(0.8, abs=0.01)
    ]  # waited ~800ms to reach the 1000ms floor
    assert mono.now_ms() >= before_second_send_wall + 800


def test_no_pacing_wait_when_the_interval_has_already_elapsed(
    server: FakeKisServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tos_runtime.transport.kis_mock.adapter as adapter_module

    sleeps: list[float] = []
    monkeypatch.setattr(adapter_module.time, "sleep", lambda s: sleeps.append(s))

    mono = FakeMonotonicSource(start_ms=0)
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(
        ORDER_PATH, status=200, body={"rt_cd": "0", "output": {"ODNO": "1"}}
    )
    cfg = _config(server, min_send_interval_ms=1000)
    transport, _, _, _ = _build_transport(server, config=cfg, monotonic=mono)

    attempt1 = _attempt("nopace-1")
    transport._seal_lookup = make_seal_lookup(  # type: ignore[attr-defined]
        {attempt1.attempt_id: build_seal(attempt_id=attempt1.attempt_id)}
    )
    _send(transport, attempt1)

    mono.advance(1500)  # more than the floor has already elapsed

    attempt2 = _attempt("nopace-2")
    transport._seal_lookup = make_seal_lookup(  # type: ignore[attr-defined]
        {attempt2.attempt_id: build_seal(attempt_id=attempt2.attempt_id)}
    )
    _send(transport, attempt2)

    assert sleeps == []


# ---------------------------------------------------------------------------
# token lifecycle (decision 4)
# ---------------------------------------------------------------------------


def test_token_is_issued_once_and_reused_while_fresh(server: FakeKisServer) -> None:
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(
        ORDER_PATH, status=200, body={"rt_cd": "0", "output": {"ODNO": "1"}}
    )
    mono = FakeMonotonicSource()
    transport, _, _, _ = _build_transport(
        server, config=_config(server, min_send_interval_ms=1), monotonic=mono
    )
    for i in range(2):
        attempt = _attempt(f"reuse-{i}")
        transport._seal_lookup = make_seal_lookup(  # type: ignore[attr-defined]
            {attempt.attempt_id: build_seal(attempt_id=attempt.attempt_id)}
        )
        mono.advance(10)
        _send(transport, attempt)
    assert len(server.requests_for(TOKEN_PATH)) == 1
    assert len(server.requests_for(ORDER_PATH)) == 2


def test_an_expired_token_within_the_reissue_cooldown_raises_token_stale_with_zero_requests(
    server: FakeKisServer,
) -> None:
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 1}
    )
    server.set_response(
        ORDER_PATH, status=200, body={"rt_cd": "0", "output": {"ODNO": "1"}}
    )
    mono = FakeMonotonicSource()
    cfg = _config(server, min_send_interval_ms=1, token_reissue_min_interval_s=300)
    transport, evidence, _, _ = _build_transport(server, config=cfg, monotonic=mono)

    attempt1 = _attempt("stale-1")
    transport._seal_lookup = make_seal_lookup(  # type: ignore[attr-defined]
        {attempt1.attempt_id: build_seal(attempt_id=attempt1.attempt_id)}
    )
    _send(transport, attempt1)
    assert len(server.requests_for(TOKEN_PATH)) == 1
    assert len(server.requests_for(ORDER_PATH)) == 1

    mono.advance(
        2000
    )  # token (expires_in=1s) is now stale; cooldown (300s) has not elapsed

    attempt2 = _attempt("stale-2")
    transport._seal_lookup = make_seal_lookup(  # type: ignore[attr-defined]
        {attempt2.attempt_id: build_seal(attempt_id=attempt2.attempt_id)}
    )
    with pytest.raises(TokenStale):
        _send(transport, attempt2)

    # no NEW requests were made for the second, refused attempt
    assert len(server.requests_for(TOKEN_PATH)) == 1
    assert len(server.requests_for(ORDER_PATH)) == 1
    (stale_record,) = evidence.of_kind("TRANSPORT_TOKEN_STALE")
    # (review F8) the burned attempt's evidence explains how much cooldown remained, so an
    # operator reading the record understands why this attempt was refused.
    assert stale_record["cooldown_remaining_ms"] > 0
    assert stale_record["cooldown_remaining_ms"] == (
        cfg.token_reissue_min_interval_s * 1000 - stale_record["elapsed_ms"]
    )


def test_a_later_attempt_after_the_cooldown_reissues_the_token(
    server: FakeKisServer,
) -> None:
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 1}
    )
    server.set_response(
        ORDER_PATH, status=200, body={"rt_cd": "0", "output": {"ODNO": "1"}}
    )
    mono = FakeMonotonicSource()
    cfg = _config(server, min_send_interval_ms=1, token_reissue_min_interval_s=1)
    transport, _, _, _ = _build_transport(server, config=cfg, monotonic=mono)

    attempt1 = _attempt("recover-1")
    transport._seal_lookup = make_seal_lookup(  # type: ignore[attr-defined]
        {attempt1.attempt_id: build_seal(attempt_id=attempt1.attempt_id)}
    )
    _send(transport, attempt1)

    mono.advance(
        5000
    )  # both the token's own expiry (1s) and the reissue cooldown (1s) elapse

    attempt2 = _attempt("recover-2")
    transport._seal_lookup = make_seal_lookup(  # type: ignore[attr-defined]
        {attempt2.attempt_id: build_seal(attempt_id=attempt2.attempt_id)}
    )
    result = _send(transport, attempt2)
    assert result.kind is EgressResultKind.ACK
    assert len(server.requests_for(TOKEN_PATH)) == 2


# ---------------------------------------------------------------------------
# secrets never in evidence / on the wire
# ---------------------------------------------------------------------------


def test_the_app_secret_never_appears_in_any_evidence_record(
    server: FakeKisServer,
) -> None:
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(
        ORDER_PATH, status=200, body={"rt_cd": "0", "output": {"ODNO": "1"}}
    )
    custody = InMemoryCredentialCustody(
        {
            APP_KEY_SCOPE: b"app-key-value",
            APP_SECRET_SCOPE: b"unmistakable-secret-marker",
        }
    )
    transport, evidence, _, _ = _build_transport(server, custody=custody)
    attempt = _attempt("secret-1")
    transport._seal_lookup = make_seal_lookup(  # type: ignore[attr-defined]
        {attempt.attempt_id: build_seal(attempt_id=attempt.attempt_id)}
    )
    _send(transport, attempt)
    dump = repr(evidence.records)
    assert "unmistakable-secret-marker" not in dump
    assert "tok-1" not in dump  # the bearer token itself is also never surfaced


def test_the_adapter_holds_no_persistent_raw_credential_attribute(
    server: FakeKisServer,
) -> None:
    """(review F5) After a live send, the adapter instance itself must not be holding any raw
    credential-shaped ``bytes``/``bytearray`` attribute — credentials are loaded, used inside the
    narrowest possible scope, and dropped; only the (non-secret) bearer token string and
    bookkeeping timestamps persist across calls. This does not prove every transient copy was
    scrubbed from process memory (Python ``bytes``/``str`` are immutable and cannot themselves
    be zeroed — the module docstring says so honestly) — it proves the adapter does not
    deliberately retain one as instance state."""
    attempt, seal = _live_ack_setup(server)
    transport, _, _, _ = _build_transport(server, seals={attempt.attempt_id: seal})
    _send(transport, attempt)
    for name, value in vars(transport).items():
        assert not isinstance(
            value, (bytes, bytearray)
        ), f"adapter holds a raw bytes-shaped attribute {name!r} after send_once returned"


def test_the_seal_digest_never_appears_on_the_wire(server: FakeKisServer) -> None:
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )
    server.set_response(
        ORDER_PATH, status=200, body={"rt_cd": "0", "output": {"ODNO": "1"}}
    )
    attempt = _attempt("wire-1")
    seal = build_seal(attempt_id=attempt.attempt_id)
    transport, _, _, _ = _build_transport(server, seals={attempt.attempt_id: seal})
    _send(transport, attempt)
    for request in server.all_requests:
        assert seal.seal_digest.encode() not in request.body
        assert all(seal.seal_digest not in v for v in request.headers.values())


# ---------------------------------------------------------------------------
# negative-greps over the whole kis_mock package
# ---------------------------------------------------------------------------


def _package_files() -> list[Path]:
    import tos_runtime.transport.kis_mock as pkg

    return list(Path(pkg.__file__).parent.glob("*.py"))


def _retry_primitive_offenders_excluding_pacing(source: str, path: Path) -> list[str]:
    tree = ast.parse(source)
    pacing_lines: set[int] = set()
    if path.name == "adapter.py":
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_enforce_pacing":
                pacing_lines = set(
                    range(node.lineno, (node.end_lineno or node.lineno) + 1)
                )
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            if isinstance(func, ast.Attribute):
                name = func.attr
            if name == "sleep" and node.lineno not in pacing_lines:
                offenders.append(
                    f"{path.name}:{node.lineno}: sleep() call outside _enforce_pacing"
                )
        elif isinstance(node, ast.Name) and "retry" in node.id.lower():
            offenders.append(
                f"{path.name}:{node.lineno}: retry-named identifier {node.id!r}"
            )
        elif isinstance(node, ast.arg) and "retry" in node.arg.lower():
            offenders.append(
                f"{path.name}:{node.lineno}: retry-named argument {node.arg!r}"
            )
        elif isinstance(node, ast.While):
            offenders.append(f"{path.name}:{node.lineno}: while loop")
        elif (
            isinstance(node, ast.For)
            and isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == "range"
        ):
            offenders.append(f"{path.name}:{node.lineno}: 'for ... in range(...)' loop")
    return offenders


def test_no_retry_primitive_anywhere_in_the_package_except_the_pacing_helper() -> None:
    all_offenders: list[str] = []
    for path in _package_files():
        source = path.read_text(encoding="utf-8")
        all_offenders.extend(_retry_primitive_offenders_excluding_pacing(source, path))
    assert all_offenders == [], f"retry/resend primitives found: {all_offenders}"


def _code_only(source: str) -> str:
    """Blank out every module/class/function docstring so a negative-grep does not trip on this
    package's own prose (which, by design, names every one of the forbidden literals it is
    itself refusing)."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    for node in ast.walk(tree):
        if (
            isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            doc_node = node.body[0]
            start = doc_node.lineno - 1
            end = (doc_node.end_lineno or doc_node.lineno) - 1
            for i in range(start, end + 1):
                lines[i] = "\n"
    return "".join(lines)


def test_no_forbidden_literals_anywhere_in_the_package() -> None:
    # Full real-order TR id literals (never a bare prefix fragment — config.py legitimately
    # carries the *prefixes* ``"T"``/``"STTN"``/``"CTF"`` as refusal-check constants; what must
    # never appear anywhere in this package is an actual real-order TR id value).
    forbidden = (
        "os.environ",
        "os.getenv",
        "import requests",
        "import httpx",
        "openapi.koreainvestment.com",
        "localhost",
        "TTTC0011U",
        "TTTC0012U",
        "TTTC0013U",
        "STTN1101U",
        "STTN1103U",
        "STTN5201R",
        "CTFO6118R",
        "CTFN6118R",
    )
    offenders: list[str] = []
    for path in _package_files():
        code_only = _code_only(path.read_text(encoding="utf-8"))
        for token in forbidden:
            if token in code_only:
                offenders.append(f"{path.name}: forbidden token {token!r}")
    assert offenders == [], offenders


def test_the_planted_violation_scan_actually_catches_something() -> None:
    """The negative-grep above is not vacuously green (mirrors the kernel suite's own
    'detects a planted violation' control test)."""
    planted = (
        "import time\n"
        "def send_once(self, attempt):\n"
        "    retry_count = 0\n"
        "    while retry_count < 3:\n"
        "        time.sleep(1)\n"
        "        retry_count += 1\n"
        "    return None\n"
    )
    offenders = _retry_primitive_offenders_excluding_pacing(planted, Path("planted.py"))
    joined = " ".join(offenders)
    assert "sleep() call" in joined
    assert "retry-named identifier" in joined
    assert "while loop" in joined
