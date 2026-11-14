"""KIS MOCK transport e2e — the option (a) "K" send path, with NO verify item patched (PR-3a)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
import yaml
from tos.rcl import CapacityState
from tos_runtime.brokercap.instance import load_instance_documents
from tos_runtime.brokercap.scopes import BrokerScopeConfigError
from tos_runtime.compose._transport_wiring import TransportKind, TransportWiringError
from tos_runtime.transport.kis_mock.adapter import KisMockTransport
from tos_runtime.transport.kis_mock.broker_facts import (
    BROKER_FACTS_CONFIG_NAME,
    load_broker_facts_config,
)
from tos_runtime.transport.kis_mock.client import KisMockHttpClient
from tos_runtime.transport.kis_mock.config import KisMockTransportConfigError

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from ..transport.kis_mock.test_adapter import (
    _retry_primitive_offenders_excluding_pacing,
)
from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted
from .test_transport_wiring import _activate_mock_stock_order

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_ENVIRONMENT_LABEL = "non-live-test"
_ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
_TOKEN_PATH = "/oauth2/tokenP"
_APP_KEY_SECRET_BYTES = b"test-secret-kis_mock.app_key"
_APP_SECRET_SECRET_BYTES = b"test-secret-kis_mock.app_secret"
_FAKE_BEARER_TOKEN = "t3-fake-bearer-token-never-in-evidence"
_ODNO = "PR3A-ODNO-1"


def _activate_and_admit(config_dir: Path, custody_root: Path) -> None:
    """MOCK_STOCK_ORDER active (``profile_evidence_ok: true``) + the Coordinator's own non-live"""
    _activate_mock_stock_order(config_dir)
    fx.provision_kis_mock_custody(custody_root)
    (config_dir / "coordinator_preconditions.yaml").write_text(
        yaml.safe_dump(
            {
                "live_authorization_state": "NOT_AUTHORIZED",
                "nonlive_broker_consuming": {"admitted": True},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _seal_egress_to(config_dir: Path, rest_base: str) -> None:
    """The egress endpoint the deployment is sealed to: the mock host's order URL (item 5)."""
    path = config_dir / "egress_coordinates.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["endpoint"]["value"] = rest_base + _ORDER_PATH
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _broker_fact_paths(config_dir: Path) -> tuple[str, str]:
    """The two GET paths (query included) the broker-facts source builds for the fixture"""
    config = load_broker_facts_config(config_dir / BROKER_FACTS_CONFIG_NAME)
    digits = fx.ACCOUNT.replace("-", "")
    balance = (
        config.balance_path
        + "?"
        + urlencode(
            {
                "CANO": digits[:8],
                "ACNT_PRDT_CD": digits[8:],
                **dict(config.balance_params),
            }
        )
    )
    quote = (
        config.quote_path
        + "?"
        + urlencode(
            {
                "FID_COND_MRKT_DIV_CODE": config.quote_market_div_code,
                "FID_INPUT_ISCD": fx.INSTRUMENT,
            }
        )
    )
    return balance, quote


def _sealed_mock_deployment(
    config_dir: Path,
    custody_root: Path,
    server: FakeKisServer,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "live",
    temp_stop_yn: str = "N",
    balance_rt_cd: str = "0",
    seal_egress: bool = True,
) -> None:
    """A complete MOCK deployment against the fake server: token, order, and both GETs."""
    server.set_response(
        _TOKEN_PATH,
        status=200,
        body={"access_token": _FAKE_BEARER_TOKEN, "expires_in": 86400},
    )
    server.set_response(
        _ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "msg_cd": "APBK0013",
            "msg1": "정상처리",
            "output": {"ODNO": _ODNO},
        },
    )
    server.require_account(fx.ACCOUNT[:8], fx.ACCOUNT[-2:])
    _patch_instance_documents_to_host(monkeypatch, mock_rest_base=server.rest_base)
    _activate_and_admit(config_dir, custody_root)
    fx.write_kis_mock_transport_config(
        config_dir,
        mode=mode,
        endpoint_rest_base=server.rest_base,
        allow_plaintext_for_tests=True,
    )
    if seal_egress:
        _seal_egress_to(config_dir, server.rest_base)
    balance, quote = _broker_fact_paths(config_dir)
    server.set_response(
        balance, status=200, body={"rt_cd": balance_rt_cd, "msg1": "-", "output1": []}
    )
    server.set_response(
        quote,
        status=200,
        body={"rt_cd": "0", "output": {"temp_stop_yn": temp_stop_yn}},
    )


def _drive_crossing_tick(runtime, custody_root: Path):
    """proposal -> write approval -> re-drive to the gateway; returns the second result."""
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label=_ENVIRONMENT_LABEL,
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    results2 = runtime.run_once((event,))
    return results2[0]


def _boot(tmp_path, config_dir, data_dir, custody_root):
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)
    return runtime


def _outcomes(runtime) -> dict[str, str]:
    return {v["item"]: v["outcome"] for v in _verify_item_payloads(runtime)}


def _verify_item_payloads(runtime) -> list[dict[str, Any]]:
    rows = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'VERIFY_ITEM' ORDER BY rowid"
    ).fetchall()
    return [json.loads(row[0])["payload"] for row in rows]


def _evidence_kind_count(runtime, kind: str) -> int:
    row = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()
    count = row[0]
    assert isinstance(count, int), f"COUNT(*) returned {type(count).__name__}"
    return count


def _evidence_kind_like_count(runtime, pattern: str) -> int:
    row = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind LIKE ?", (pattern,)
    ).fetchone()
    count = row[0]
    assert isinstance(count, int), f"COUNT(*) returned {type(count).__name__}"
    return count


def _evidence_row_order(runtime, kind: str) -> int | None:
    """The (0-based) position of the FIRST ``entries`` row with this ``kind`` in rowid order, or"""
    rows = runtime.evidence_store.connection.execute(
        "SELECT rowid, kind FROM entries ORDER BY rowid"
    ).fetchall()
    for index, (_rowid, row_kind) in enumerate(rows):
        if row_kind == kind:
            return index
    return None


def _all_evidence_text(runtime) -> str:
    rows = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries"
    ).fetchall()
    return " ".join(row[0] for row in rows)


def _independent_wire_digest(
    *, account: str, instrument: str, quantity: str, price: str
) -> str:
    """A GENUINELY independent oracle for the KIS ``order_cash`` wire-body digest — hand-built"""
    cano, acnt_prdt_cd = account[:8], account[-2:]
    assert account == f"{cano}-{acnt_prdt_cd}", account
    fields = {
        "CANO": cano,
        "PDNO": instrument,
        "ORD_QTY": format(Decimal(quantity), "f"),
        "ORD_UNPR": format(Decimal(price) / Decimal(100), "f"),
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "ORD_DVSN": "00",
        "EXCG_ID_DVSN_CD": "KRX",
        "SLL_TYPE": "",
        "CNDT_PRIC": "",
    }
    body = json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _assert_byte_seal_identity_and_result_ordering(
    runtime, order_request: Any, seal_payload: dict[str, Any]
) -> None:
    """Counterfactual B's own byte-seal-identity block, extracted (review LOW: keep"""
    received_digest = hashlib.sha256(order_request.body).hexdigest()
    assert received_digest == seal_payload["request_bytes_digest"]
    independent_digest = _independent_wire_digest(
        account=seal_payload["account"],
        instrument=seal_payload["instrument_key"]["instrument"],
        quantity=seal_payload["outbound_quantity"],
        price=seal_payload["outbound_price"],
    )
    assert received_digest == independent_digest
    wire = json.loads(order_request.body)
    sealed = Decimal(seal_payload["outbound_price"])
    assert Decimal(wire["ORD_UNPR"]) * 100 == sealed
    assert Decimal(wire["ORD_UNPR"]) != sealed
    assert seal_payload["account"] == f"{wire['CANO']}-{wire['ACNT_PRDT_CD']}"
    assert len(wire["CANO"]) == 8 and len(wire["ACNT_PRDT_CD"]) == 2

    assert _evidence_kind_count(runtime, "EGRESS_RESULT_RECORDED") == 1
    network_call_entered_order = _evidence_row_order(runtime, "NETWORK_CALL_ENTERED")
    egress_result_recorded_order = _evidence_row_order(
        runtime, "EGRESS_RESULT_RECORDED"
    )
    assert network_call_entered_order is not None
    assert egress_result_recorded_order is not None
    assert network_call_entered_order < egress_result_recorded_order


def _spy_send_once(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Spy on every :class:`KisMockTransport` instance's ``send_once`` (class-level patch, the"""
    calls: list[Any] = []
    original = KisMockTransport.send_once

    def _spying(self: KisMockTransport, attempt: Any, **kwargs: Any) -> Any:
        result = original(self, attempt, **kwargs)
        calls.append(result)
        return result

    monkeypatch.setattr(KisMockTransport, "send_once", _spying)
    return calls


def _spy_do_request(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Spy on ``KisMockHttpClient._do_request`` — the ONE call site that ever opens a socket"""
    calls: list[Any] = []
    original = KisMockHttpClient._do_request

    def _spying(self: KisMockHttpClient, method: str, path: str, **kwargs: Any) -> Any:
        calls.append((method, path))
        return original(self, method, path, **kwargs)

    monkeypatch.setattr(KisMockHttpClient, "_do_request", _spying)
    return calls


def _patch_instance_documents_to_host(
    monkeypatch: pytest.MonkeyPatch, *, mock_rest_base: str
) -> None:
    """Substitute the MOCK_VTS INSTANCE document's own ``rest_base`` for ``mock_rest_base``"""

    def _patched(path: Path, **kwargs: Any) -> tuple[Any, ...]:
        documents = load_instance_documents(path, **kwargs)
        return tuple(
            (
                dataclasses.replace(document, rest_base=mock_rest_base)
                if document.environment == "MOCK_VTS"
                else document
            )
            for document in documents
        )

    monkeypatch.setattr(
        "tos_runtime.compose._transport_wiring.load_instance_documents", _patched
    )


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def test_dry_run_reaches_the_adapter_with_every_verify_item_satisfied(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """``mode: dry_run``: every item SATISFIED with no lift; ``SEND_SEALED`` before"""
    _sealed_mock_deployment(
        config_dir, custody_root, server, monkeypatch, mode="dry_run"
    )
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is True

    outcomes = _outcomes(runtime)
    assert len(outcomes) == 7
    assert set(outcomes.values()) == {"SATISFIED"}, outcomes

    sealed = _evidence_row_order(runtime, "SEND_SEALED")
    entered = _evidence_row_order(runtime, "NETWORK_CALL_ENTERED")
    assert sealed is not None and entered is not None and sealed < entered

    (dry_run_row,) = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'TRANSPORT_DRY_RUN'"
    ).fetchall()
    dry_run_payload = json.loads(dry_run_row[0])["payload"]
    (seal_row,) = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'SEND_SEALED'"
    ).fetchall()
    seal_payload = json.loads(seal_row[0])["payload"]["send_seal"]
    assert (
        dry_run_payload["request_bytes_digest"] == seal_payload["request_bytes_digest"]
    )
    assert dry_run_payload["request_bytes_digest"] == _independent_wire_digest(
        account=seal_payload["account"],
        instrument=seal_payload["instrument_key"]["instrument"],
        quantity=seal_payload["outbound_quantity"],
        price=seal_payload["outbound_price"],
    )

    reservation = runtime.core.ledger.outstanding(fx.instrument_key())
    assert reservation is not None
    assert reservation.capacity_state is CapacityState.QUARANTINED_UNKNOWN

    assert server.requests_for(_ORDER_PATH) == []
    assert {r.method for r in server.all_requests} == {
        "GET",
        "POST",
    }
    assert _evidence_kind_count(runtime, "BROKER_FACTS_OBSERVED") >= 1

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_live_order_reaches_ack_against_the_fake_server(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """``mode: live``: exactly one order POST whose body sha256 is the seal's"""
    _sealed_mock_deployment(config_dir, custody_root, server, monkeypatch)
    send_once_calls = _spy_send_once(monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is True
    assert set(_outcomes(runtime).values()) == {"SATISFIED"}

    (order_request,) = server.requests_for(_ORDER_PATH)
    (seal_row,) = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'SEND_SEALED'"
    ).fetchall()
    seal_payload = json.loads(seal_row[0])["payload"]["send_seal"]
    _assert_byte_seal_identity_and_result_ordering(runtime, order_request, seal_payload)

    (result_payload,) = send_once_calls
    assert result_payload.kind.value == "ACK"
    assert result_payload.broker_execution_id == _ODNO

    evidence_text = _all_evidence_text(runtime)
    assert _APP_KEY_SECRET_BYTES.decode() not in evidence_text
    assert _APP_SECRET_SECRET_BYTES.decode() not in evidence_text
    assert _FAKE_BEARER_TOKEN not in evidence_text
    assert fx.ACCOUNT.replace("-", "")[:8] not in json.dumps(
        [
            json.loads(row[0])
            for row in runtime.evidence_store.connection.execute(
                "SELECT payload_json FROM entries WHERE kind = 'BROKER_FACTS_OBSERVED'"
            )
        ]
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()


@pytest.mark.parametrize(
    ("setup", "item", "outcomes"),
    [
        ({"seal_egress": False}, "VALID_LIVE_SCOPE", {"DENIED"}),
        (
            {"temp_stop_yn": "Y"},
            "VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION",
            {"DENIED", "UNKNOWN"},
        ),
        (
            {"balance_rt_cd": "1"},
            "VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION",
            {"DENIED", "UNKNOWN"},
        ),
    ],
)
def test_a_missing_fact_refuses_the_send_with_zero_order_posts(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
    setup: dict[str, Any],
    item: str,
    outcomes: set[str],
) -> None:
    _sealed_mock_deployment(config_dir, custody_root, server, monkeypatch, **setup)
    send_once_calls = _spy_send_once(monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is not True

    observed = _outcomes(runtime)
    assert observed[item] in outcomes
    assert observed["ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY"] == "SATISFIED"
    assert send_once_calls == []
    assert server.requests_for(_ORDER_PATH) == []
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 0

    runtime.rcl_log.close()
    runtime.evidence_store.close()


@pytest.mark.parametrize("active_scope", ["REAL_ORDER", "REAL_READ"])
def test_a_real_scope_with_the_kis_mock_transport_refuses_to_boot(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    active_scope: str,
) -> None:
    """MOCK -> REAL fallback (``REAL_ORDER``) and a read-only principal reaching the order"""
    _activate_and_admit(config_dir, custody_root)
    path = config_dir / "broker_scopes.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["active_scope"] = active_scope
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    fx.write_kis_mock_transport_config(config_dir)
    with pytest.raises(
        (BrokerScopeConfigError, TransportWiringError, KisMockTransportConfigError)
    ):
        _boot(tmp_path, config_dir, data_dir, custody_root)


def test_mutation_a_retry_loop_would_be_caught_by_the_existing_negative_grep() -> None:
    """(a) Add a retry loop to a scratch COPY of the real adapter.py source (never written to"""
    adapter_path = Path(
        Path(__file__).resolve().parents[2]
        / "src"
        / "tos_runtime"
        / "transport"
        / "kis_mock"
        / "adapter.py"
    )
    real_source = adapter_path.read_text(encoding="utf-8")
    mutated_source = real_source + (
        "\n\n"
        "def _t3_planted_retry(client):\n"
        "    for _attempt in range(3):\n"
        "        client.post_order()\n"
    )
    offenders = _retry_primitive_offenders_excluding_pacing(
        mutated_source, adapter_path
    )
    assert offenders != []
    assert any("for ... in range(...)" in offender for offender in offenders)

    assert _retry_primitive_offenders_excluding_pacing(real_source, adapter_path) == []


def test_mutation_b_a_digest_mismatch_is_refused_before_any_order_post(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """(b) Corrupt the seal the adapter reads (the narrowest seam standing in for "the adapter's"""
    _sealed_mock_deployment(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)

    real_seal_lookup = runtime.transport._seal_lookup  # noqa: SLF001

    def _corrupting_lookup(attempt_id: str) -> Any:
        seal = real_seal_lookup(attempt_id)
        if seal is None:
            return None
        return seal.model_copy(
            update={"request_bytes_digest": "t3-mutation-pin-deliberately-mismatched"}
        )

    monkeypatch.setattr(runtime.transport, "_seal_lookup", _corrupting_lookup)

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    assert result.flow.handoff.accepted_for_transmission is not True

    (mismatch_row,) = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'TRANSPORT_BINDING_MISMATCH'"
    ).fetchall()
    assert json.loads(mismatch_row[0])["payload"]["sealed_request_bytes_digest"] == (
        "t3-mutation-pin-deliberately-mismatched"
    )
    (send_refused_row,) = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'SEND_REFUSED' "
        "AND payload_json LIKE '%TRANSPORT_RAISED%'"
    ).fetchall()
    assert send_refused_row is not None
    assert server.requests_for(_ORDER_PATH) == []

    runtime.rcl_log.close()
    runtime.evidence_store.close()
