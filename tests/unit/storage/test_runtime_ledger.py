"""SQLite runtime ledger tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest


def test_sqlite_runtime_ledger_records_core_tables(tmp_path):
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    ledger = SQLiteRuntimeLedger(db_path)

    order_id = ledger.record_order(
        {
            "id": "order-1",
            "asset_class": "stock",
            "code": "005930",
            "side": "BUY",
            "order_type": "01",
            "quantity": 10,
            "price": 71000.0,
            "strategy": "bb_reversion",
            "client_order_id": "coid-1",
        }
    )
    fill_id = ledger.record_fill(
        {
            "id": "fill-1",
            "order_id": order_id,
            "asset_class": "stock",
            "code": "005930",
            "side": "BUY",
            "filled_qty": 10,
            "filled_price": 71010.0,
            "venue": "KRX",
        }
    )
    trade_id = ledger.record_trade(
        {
            "id": "trade-1",
            "asset_class": "stock",
            "code": "005930",
            "side": "long",
            "strategy": "bb_reversion",
            "entry_time": "2026-06-03T09:00:00+09:00",
            "entry_price": 71000.0,
            "exit_time": "2026-06-03T10:00:00+09:00",
            "exit_price": 72000.0,
            "quantity": 10,
            "exit_reason": "signal_exit",
        }
    )
    risk_id = ledger.record_risk_event(
        {
            "event_id": "risk-1",
            "event_type": "kill_switch_changed",
            "severity": "warning",
        }
    )
    decision_id = ledger.record_signal_decision(
        {
            "decision_id": "decision-1",
            "signal_id": "signal-1",
            "code": "005930",
            "decision": "accepted",
        }
    )
    context_id = ledger.record_market_context(
        {
            "context_id": "ctx-1",
            "asset_class": "stock",
            "context_type": "llm_market_context",
        }
    )

    assert order_id == "order-1"
    assert fill_id == "fill-1"
    assert trade_id == "trade-1"
    assert risk_id == "risk-1"
    assert decision_id == "decision-1"
    assert context_id == "ctx-1"

    trades = ledger.query_trades({"asset_class": "stock", "code": "005930"})
    assert len(trades) == 1
    assert trades[0]["id"] == "trade-1"
    assert trades[0]["pnl"] == 10000.0
    assert trades[0]["pnl_pct"] == pytest.approx(1.40845, rel=1e-4)
    assert trades[0]["hold_seconds"] == 3600
    assert trades[0]["payload"]["exit_reason"] == "signal_exit"
    ledger.close()


def test_sqlite_runtime_ledger_recovers_latest_open_position_after_restart(tmp_path):
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    entry_time = datetime(2026, 6, 3, 9, 0, tzinfo=UTC)

    ledger = SQLiteRuntimeLedger(db_path)
    ledger.record_position_snapshot(
        {
            "id": "pos-1",
            "asset_class": "stock",
            "code": "005930",
            "name": "Samsung",
            "side": "long",
            "strategy": "bb_reversion",
            "quantity": 10,
            "entry_time": entry_time,
            "entry_price": 71000.0,
            "current_price": 71500.0,
            "highest_price": 71600.0,
            "lowest_price": 70900.0,
            "state": "survival",
        }
    )
    ledger.close()

    reopened = SQLiteRuntimeLedger(db_path)
    open_positions = reopened.load_open_positions("stock")

    assert len(open_positions) == 1
    assert open_positions[0]["position_id"] == "pos-1"
    assert open_positions[0]["symbol"] == "005930"
    assert open_positions[0]["is_open"] == 1

    reopened.record_position_snapshot(
        {
            "id": "pos-1",
            "asset_class": "stock",
            "code": "005930",
            "side": "long",
            "quantity": 10,
            "entry_time": entry_time,
            "entry_price": 71000.0,
            "exit_time": entry_time + timedelta(hours=1),
            "exit_price": 72000.0,
            "exit_reason": "signal_exit",
        }
    )

    assert reopened.load_open_positions("stock") == []
    reopened.close()


def test_sqlite_runtime_ledger_idempotent_trade_upsert(tmp_path):
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
    first = {
        "id": "trade-1",
        "idempotency_key": "position-1-close",
        "asset_class": "stock",
        "code": "005930",
        "entry_price": 100.0,
        "exit_price": 105.0,
        "quantity": 10,
    }
    second = {**first, "exit_price": 107.0}

    assert ledger.record_trade(first) == "trade-1"
    assert ledger.record_trade(second) == "trade-1"

    trades = ledger.query_trades({"limit": 10})
    assert len(trades) == 1
    assert trades[0]["exit_price"] == 107.0
    assert trades[0]["pnl"] == 70.0
    ledger.close()


def test_sqlite_runtime_ledger_handles_concurrent_writes(tmp_path):
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")

    def write_trade(i: int) -> str:
        return ledger.record_trade(
            {
                "id": f"trade-{i}",
                "asset_class": "stock",
                "code": "005930",
                "entry_price": 100.0,
                "exit_price": 100.0 + i,
                "quantity": 1,
            }
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(write_trade, range(25)))

    assert len(ids) == 25
    assert len(ledger.query_trades({"limit": 100})) == 25
    ledger.close()


def test_sqlite_runtime_ledger_rejects_directory_path(tmp_path):
    from shared.storage.runtime_ledger import RuntimeLedgerError, SQLiteRuntimeLedger

    with pytest.raises(RuntimeLedgerError, match="path is a directory"):
        SQLiteRuntimeLedger(tmp_path)
