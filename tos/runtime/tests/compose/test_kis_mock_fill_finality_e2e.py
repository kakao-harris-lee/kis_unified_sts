"""KIS MOCK fill → finality → release e2e, against the fake KIS server, NO verify item patched
(PR-3b, rescope plan §3 M2).

Order → ACK (PR-3a's real gateway) → the post-ACK observer polls ``VTTC0081R`` → ``PARTIAL_FILL``
→ ``FULL_FILL`` → broker-sourced finality proof → reconciliation against the real
``KisStockBrokerWitness`` → RCL ``POSITION_CONSUMED``, with every evidence row naming the one
attempt. Also pinned:

* the same execution observed twice is reported once;
* an execution for an ODNO this runtime never ACKed is flagged and never attributed — and, being an
  orphan broker order, it blocks release;
* odd broker rows become ``UNKNOWN``, never a fill;
* a kill/restart between ACK and fill: the boot replay rebuilds the engine's reservation
  projection (#944), so the rebooted runtime's observer feeds the fill and it is applied and
  releases the durable RCL reservation exactly once, reconciled against the KIS witness.

Hermetic: the fake server binds ``127.0.0.1``; the only production patch is PR-3a's INSTANCE
``rest_base`` → fake server (infrastructure, not a verify item).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
from tos.engine.vocabulary import EgressResultKind, ResultDisposition
from tos.rcl import CapacityState, CommandType
from tos_runtime.compose._broker_posttrade_wiring import DeferredKisWitness
from tos_runtime.posttrade.broker_finality import BrokerFinalityProducer
from tos_runtime.posttrade.fill_observer import (
    FILL_OBSERVER_CONFIG_NAME,
    load_fill_observer_config,
)
from tos_runtime.posttrade.release_consumer import release_command_id

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from .test_kis_mock_e2e_honesty import (
    _ORDER_PATH,
    _boot,
    _drive_crossing_tick,
    _sealed_mock_deployment,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: The measured 모의 stock encoding — the ACK's ``output.ODNO`` and the inquiry row's ``odno`` are
#: the same zero-padded 10 digits (P-11 2026-08-05, ``queried_odno``/``row.odno``).
_ODNO = "0000004470"
_FOREIGN_ODNO = "0000009999"


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


# ===========================================================================
# helpers
# ===========================================================================


def _deploy(config_dir, custody_root, server, monkeypatch) -> None:
    _sealed_mock_deployment(config_dir, custody_root, server, monkeypatch)
    server.set_response(
        _ORDER_PATH,
        status=200,
        body={"rt_cd": "0", "msg_cd": "APBK0013", "output": {"ODNO": _ODNO}},
    )


def _rows(runtime, kind: str) -> list[dict[str, Any]]:
    rows = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq", (kind,)
    ).fetchall()
    return [json.loads(row[0])["payload"] for row in rows]


def _ack(runtime) -> dict[str, Any]:
    (ack,) = [
        r
        for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
        if r["egress_result_kind"] == "ACK"
    ]
    return ack


def _sealed_quantity(runtime) -> Decimal:
    (seal,) = _rows(runtime, "SEND_SEALED")
    return Decimal(seal["send_seal"]["outbound_quantity"])


def _witness_paths(config_dir: Path, date: str) -> tuple[str, str]:
    """The two GET paths ``KisStockBrokerWitness`` builds — wire params as that module sends them
    (``probes_balance``/``probes_order`` mirrors), the paths from the shipped config."""
    config = load_fill_observer_config(config_dir / FILL_OBSERVER_CONFIG_NAME)
    fields = config.witness_fields
    digits = fx.ACCOUNT.replace("-", "")
    cano, prdt = digits[:8], digits[8:]
    balance = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "01",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    orders = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "INQR_STRT_DT": date,
        "INQR_END_DT": date,
        "SLL_BUY_DVSN_CD": "00",
        "PDNO": fx.INSTRUMENT,
        "CCLD_DVSN": "00",
        "INQR_DVSN": "00",
        "INQR_DVSN_3": "00",
        "ORD_GNO_BRNO": "",
        "ODNO": "",
        "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
        "EXCG_ID_DVSN_CD": "KRX",
    }
    return (
        f"{fields['balance_path']}?{urlencode(balance)}",
        f"{fields['order_inquiry_path']}?{urlencode(orders)}",
    )


def _row(
    *,
    odno: str = _ODNO,
    date: str,
    ord_qty: Decimal,
    filled: Decimal,
    remaining: Decimal,
    cancelled: str = "N",
    rjct: str = "0",
    orgn_odno: str = "0000000000",
) -> dict[str, str]:
    """One ``VTTC0081R`` ``output1`` row, in the measured wire shape (all strings)."""
    return {
        "ord_dt": date,
        "odno": odno,
        "orgn_odno": orgn_odno,
        "pdno": fx.INSTRUMENT,
        "ord_qty": format(ord_qty, "f"),
        "tot_ccld_qty": format(filled, "f"),
        "rmn_qty": format(remaining, "f"),
        "cncl_yn": cancelled,
        "rjct_qty": rjct,
    }


class _Unset:
    """A distinguishable "no override given" sentinel for ``_script_broker``'s
    ``holdings_container`` — the same pattern ``_fixtures.write_kis_mock_transport_config``
    uses, and needed for the same reason: a plain ``None`` default cannot be told apart from a
    test that wants a literal ``output1: null`` on the wire (review-973 round 2)."""


class _OmitKey:
    """``holdings_container=_OMIT_OUTPUT1`` leaves the ``output1`` key OUT of the balance body
    entirely — distinct from writing it as ``null``, and a case review-973 round 2 asks for in
    its own right (``body.get`` answers ``None`` for both, so only the wire differs)."""


_UNSET_CONTAINER = _Unset()
_OMIT_OUTPUT1 = _OmitKey()


def _script_broker(
    server,
    config_dir,
    date: str,
    rows: list[Any],
    *,
    holdings: tuple[tuple[str, Decimal], ...] = (),
    raw_holdings: list[dict[str, Any]] | None = None,
    holdings_container: Any = _UNSET_CONTAINER,
) -> str:
    """Script both witness GETs for ``date``: the order inquiry from ``rows``, the balance
    inquiry from ``holdings`` (default: a flat account with NO rows, the shape every test here
    had before ``holdings`` existed).

    ``rows`` is written to the order ``output1`` verbatim, so a test can put an element there
    that is not an order row at all (issue #981's unreadable row).

    ``raw_holdings`` writes the balance ``output1`` rows verbatim instead, so a test can send
    a quantity the production parser cannot read (``hldg_qty: ""``) or a ``pdno`` that is not a
    string (issue #981) and observe what ``KisStockBrokerWitness`` actually does with it —
    #966 review round 1 needs that exact input, and building it from ``Decimal`` cannot
    express it.

    ``holdings_container`` replaces the whole ``output1`` VALUE, including with a non-list
    (``None``, a dict), which review-973 round 2 needs: a malformed container is not an empty
    page."""
    balance, orders = _witness_paths(config_dir, date)
    balance_body: dict[str, Any] = {
        "rt_cd": "0",
        "output2": [{"dnca_tot_amt": "1000000"}],
    }
    if not isinstance(holdings_container, _OmitKey):
        balance_body["output1"] = (
            holdings_container
            if not isinstance(holdings_container, _Unset)
            else (
                raw_holdings
                if raw_holdings is not None
                else [
                    {"pdno": symbol, "hldg_qty": format(quantity, "f")}
                    for symbol, quantity in holdings
                ]
            )
        )
    server.set_response(balance, status=200, body=balance_body)
    server.set_response(
        orders, status=200, body={"rt_cd": "0", "output1": rows, "output2": {}}
    )
    return orders


def _rcl_state(runtime) -> CapacityState:
    ((_rid, state, _seq, _scope),) = runtime.rcl_log.reservation_rows()
    assert isinstance(state, CapacityState)
    return state


def _rcl_releases(runtime, *, attempt_id: str | None = None) -> int:
    """Committed RCL release transitions — the durable fact, not the pre-mutation intent row.

    ``attempt_id`` narrows the count to the release THAT attempt's own fill drove, by the
    command id the release consumer keys it on. A test whose fixture seeds an earlier,
    already-discharged attempt (``test_kis_mock_fill_finality_r2``) needs that narrowing —
    since #966 each attempt has its own reservation, so the log legitimately carries one
    release command per completed attempt rather than one per scope.
    """
    return sum(
        1
        for entry in runtime.rcl_log.replay()
        if entry.kind == CommandType.RELEASE_RESERVATION.value
        and (attempt_id is None or entry.command_id == release_command_id(attempt_id))
    )


def _close(runtime) -> None:
    # Issue #950: stop the observer's FETCH worker before the stores it reports into.
    if runtime.fill_observer is not None:
        runtime.fill_observer.close()
    runtime.rcl_log.close()
    runtime.evidence_store.close()


def _acked(tmp_path, config_dir, data_dir, custody_root, server, monkeypatch):
    _deploy(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handed_off is True
    ack = _ack(runtime)
    assert ack["broker_execution_id"] == _ODNO and ack["trading_date"] is not None
    return runtime, ack["trading_date"], _sealed_quantity(runtime)


# ===========================================================================
# 1. ACK -> partial -> full -> finality -> release
# ===========================================================================


def test_partial_then_full_fill_releases_once_with_connected_evidence(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    assert qty >= 2, "a partial fill needs at least 2 sealed units"
    assert runtime.broker_witness_provenance == "kis-mock-stock"
    observer = runtime.fill_observer
    assert observer is not None

    orders_path = _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=Decimal(1), remaining=qty - 1)],
    )
    report = observer.poll_once()
    assert report.emitted == (
        (
            _ack(runtime)["attempt_id"],
            EgressResultKind.PARTIAL_FILL,
            ResultDisposition.APPLIED,
        ),
    )
    # Cadence comes from fill_observer.yaml: an immediate second poll_if_due does not poll.
    assert observer.poll_if_due().polled is False
    # The same execution observed again is not reported again.
    assert observer.poll_once().emitted == ()
    assert len(_rows(runtime, "FILL_OBSERVED")) == 1

    _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )
    report = observer.poll_once()
    assert [(k, d) for _a, k, d in report.emitted] == [
        (EgressResultKind.FULL_FILL, ResultDisposition.APPLIED)
    ]

    # Finality: a broker proof, never SYNTHETIC; release committed once, to POSITION_CONSUMED.
    attempt_id = _ack(runtime)["attempt_id"]
    (proof,) = _rows(runtime, "POSTTRADE_FINALITY_PROOF")
    assert proof["idempotency_key"] == f"broker-fqp-proof:{attempt_id}"
    (obligation,) = _rows(runtime, "ECONOMIC_OBLIGATION")
    assert obligation["obligation_type"] == "BROKER_ORDER_FQP"
    assert "SYNTHETIC" not in json.dumps([proof, obligation])
    (intent,) = _rows(runtime, "CAPACITY_RELEASE_INTENT")
    assert intent["destination"] == "POSITION_CONSUMED"
    assert intent["proof_id"] == proof["proof_id"]
    assert _rows(runtime, "CAPACITY_RELEASE_HELD") == []
    assert _rcl_state(runtime) is CapacityState.POSITION_CONSUMED
    assert _rcl_releases(runtime) == 1

    # Every result row names the one attempt and the one broker order.
    results = _rows(runtime, "EGRESS_RESULT_CONSUMED")
    assert [r["egress_result_kind"] for r in results] == [
        "ACK",
        "PARTIAL_FILL",
        "FULL_FILL",
    ]
    assert {
        (r["attempt_id"], r["broker_execution_id"], r["trading_date"]) for r in results
    } == {(attempt_id, _ODNO, date)}
    assert {r["attempt_id"] for r in _rows(runtime, "FILL_OBSERVED")} == {attempt_id}

    # Terminal: a held-position proof may still read broker holdings and order rows after the
    # entry has transitioned to POSITION_CONSUMED. Those risk-only GETs must not reproject the
    # already released fill.
    before = len(server.all_requests)
    terminal_results = _rows(runtime, "EGRESS_RESULT_CONSUMED")
    observed_fills = _rows(runtime, "FILL_OBSERVED")
    repeat_report = observer.poll_once()
    assert repeat_report.emitted == ()
    assert repeat_report.reprojected == ()
    assert _rows(runtime, "EGRESS_RESULT_CONSUMED") == terminal_results
    assert _rows(runtime, "FILL_OBSERVED") == observed_fills
    assert _rcl_releases(runtime) == 1
    # Any new GET belongs to the independent held-position proof; order submission stays once.
    assert all(
        request.method == "GET"
        for request in server.all_requests[before:]
        if request.path != "/oauth2/tokenP"
    )
    assert len(server.requests_for(_ORDER_PATH)) == 1
    assert {r.method for r in server.all_requests if r.path != "/oauth2/tokenP"} == {
        "GET",
        "POST",
    }
    assert [
        r.method
        for r in server.all_requests
        if r.method == "POST" and r.path != "/oauth2/tokenP"
    ] == ["POST"]
    assert len(server.requests_for(orders_path)) >= 3
    _close(runtime)


# ===========================================================================
# 2. an execution for an unknown ODNO is flagged, never attributed
# ===========================================================================


def test_unknown_odno_is_flagged_and_blocks_release(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    observer = runtime.fill_observer
    assert observer is not None

    # Only a foreign execution: flagged once, nothing enqueued.
    foreign = _row(
        odno=_FOREIGN_ODNO, date=date, ord_qty=qty, filled=qty, remaining=Decimal(0)
    )
    _script_broker(server, config_dir, date, [foreign])
    report = observer.poll_once()
    assert report.emitted == ()
    assert report.unattributed == (f"{_FOREIGN_ODNO}@{date}",)
    observer.poll_once()
    (flag,) = _rows(runtime, "FILL_OBSERVER_UNATTRIBUTED_ORDER")
    assert flag["broker_execution_id"] == _FOREIGN_ODNO
    assert [
        r["egress_result_kind"] for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
    ] == ["ACK"]

    # Our order then fills. Ours is attributed; the foreign one is still an orphan broker order
    # in the same scope, so reconciliation does not corroborate and nothing is released.
    _script_broker(
        server,
        config_dir,
        date,
        [foreign, _row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )
    report = observer.poll_once()
    assert [k for _a, k, _d in report.emitted] == [EgressResultKind.FULL_FILL]
    (held,) = _rows(runtime, "CAPACITY_RELEASE_HELD")
    assert held["reason"] == "NOT_CORROBORATED"
    assert _rows(runtime, "CAPACITY_RELEASE_INTENT") == []
    assert _rcl_state(runtime) is not CapacityState.POSITION_CONSUMED
    _close(runtime)


# ===========================================================================
# 3. odd broker rows -> UNKNOWN, never a fill
# ===========================================================================


@pytest.mark.parametrize(
    "odd",
    [
        "ordered_quantity_mismatch",
        "quantity_inconsistent",
        "rejected_quantity",
        "ambiguous_rows",
    ],
)
def test_odd_rows_become_unknown_never_a_fill(
    odd, config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    one, zero = Decimal(1), Decimal(0)
    rows = {
        "ordered_quantity_mismatch": [
            _row(date=date, ord_qty=qty + 1, filled=qty + 1, remaining=zero)
        ],
        "quantity_inconsistent": [
            _row(date=date, ord_qty=qty, filled=one, remaining=zero)
        ],
        "rejected_quantity": [
            _row(date=date, ord_qty=qty, filled=zero, remaining=qty, rjct="1")
        ],
        "ambiguous_rows": [
            _row(date=date, ord_qty=qty, filled=qty, remaining=zero),
            _row(date=date, ord_qty=qty, filled=qty, remaining=zero),
        ],
    }[odd]
    _script_broker(server, config_dir, date, rows)
    observer = runtime.fill_observer
    assert observer is not None
    report = observer.poll_once()
    assert [k for _a, k, _d in report.emitted] == [EgressResultKind.UNKNOWN]
    (observed,) = _rows(runtime, "FILL_OBSERVED")
    assert observed["reason"] == odd
    assert _rows(runtime, "POSTTRADE_FINALITY_PROOF") == []
    assert runtime.core.ledger.outstanding(fx.instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )
    # Reported once.
    assert observer.poll_once().emitted == ()
    _close(runtime)


# ===========================================================================
# 4. kill/restart between ACK and fill
# ===========================================================================


def test_restart_between_ack_and_fill_releases_once_and_keeps_every_later_boot_sound(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """The boot replay rebuilds the engine's reservation projection (#944), so a fill that lands
    while the runtime is down is fed to the rebooted engine, applied, and released exactly once.
    Before #944 the restarted engine held no pre-restart attempt: the observer could only record
    what the broker showed (``FILL_OBSERVER_ENGINE_RESERVATION_ABSENT``) and the capacity stayed
    reserved forever. Every later boot re-derives the same APPLIED fill and the same single
    release, so no later boot's replay diverges.
    """
    runtime, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    attempt_id = _ack(runtime)["attempt_id"]
    _close(runtime)  # the process dies after the ACK was consumed; the fill comes later

    runtime2 = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert runtime2.recovery is not None and runtime2.recovery.ready is True
    held = runtime2.core.ledger.outstanding(fx.instrument_key())
    assert held is not None and held.attempt_id == attempt_id  # rebuilt at boot
    observer = runtime2.fill_observer
    assert observer is not None
    _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )

    report = observer.poll_once()
    assert [(a, k, d) for a, k, d in report.emitted] == [
        (attempt_id, EgressResultKind.FULL_FILL, ResultDisposition.APPLIED)
    ]
    assert report.held == ()
    assert _rows(runtime2, "FILL_OBSERVER_ENGINE_RESERVATION_ABSENT") == []
    # The fill reached the engine, was proven against the broker, and released once.
    assert [r["egress_result_kind"] for r in _rows(runtime2, "RESULT_UNMATCHED")] == []
    (proof,) = _rows(runtime2, "POSTTRADE_FINALITY_PROOF")
    assert proof["idempotency_key"] == f"broker-fqp-proof:{attempt_id}"
    assert _rcl_releases(runtime2) == 1
    assert _rcl_state(runtime2) is CapacityState.POSITION_CONSUMED

    # The same execution observed again is not reported again.
    assert observer.poll_once().emitted == ()
    _close(runtime2)

    # The next boot re-derives the same APPLIED fill and the same one release.
    runtime3 = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert runtime3.recovery is not None and runtime3.recovery.ready is True
    assert runtime3.core.ledger.outstanding(fx.instrument_key()) is None
    assert runtime3.fill_observer is not None
    report3 = runtime3.fill_observer.poll_once()
    assert report3.emitted == () and report3.reprojected == ()
    assert _rcl_releases(runtime3) == 1
    assert len(server.requests_for(_ORDER_PATH)) == 1  # nothing re-sent across restarts
    _close(runtime3)


# ===========================================================================
# 5. which witness each boot reconciles against
# ===========================================================================


def test_stock_mock_boot_reconciles_against_the_kis_witness(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    _deploy(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    consumer = runtime.driver._release_consumer  # noqa: SLF001
    assert isinstance(
        consumer.recon_service._witness, DeferredKisWitness
    )  # noqa: SLF001
    assert isinstance(consumer.finality_producer, BrokerFinalityProducer)
    assert isinstance(
        runtime.driver._finality_producer, BrokerFinalityProducer
    )  # noqa: SLF001
    _close(runtime)
