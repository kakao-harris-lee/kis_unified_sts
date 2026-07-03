"""RuntimeLedger track_id column, migration, and query-filter tests (Phase 3A)."""

import sqlite3

import pytest

from shared.storage.runtime_ledger import SQLiteRuntimeLedger

_TAGGED_TABLES = ("orders", "fills", "trades", "signal_decisions")

# Schema v1 DDL (pre-track_id) for the tagged tables — used to simulate an
# existing production database that must be migrated in place.
_V1_SCHEMA = """
    CREATE TABLE orders (
        id TEXT PRIMARY KEY,
        idempotency_key TEXT UNIQUE,
        asset_class TEXT,
        symbol TEXT,
        side TEXT,
        order_type TEXT,
        quantity INTEGER,
        price REAL,
        status TEXT,
        strategy TEXT,
        broker_order_id TEXT,
        client_order_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE fills (
        id TEXT PRIMARY KEY,
        idempotency_key TEXT UNIQUE,
        order_id TEXT,
        asset_class TEXT,
        symbol TEXT,
        side TEXT,
        quantity INTEGER,
        price REAL,
        filled_at TEXT NOT NULL,
        broker_fill_id TEXT,
        venue TEXT,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE trades (
        id TEXT PRIMARY KEY,
        idempotency_key TEXT UNIQUE,
        asset_class TEXT,
        symbol TEXT,
        name TEXT,
        side TEXT,
        strategy TEXT,
        entry_time TEXT,
        entry_price REAL,
        exit_time TEXT,
        exit_price REAL,
        quantity INTEGER,
        pnl REAL,
        pnl_pct REAL,
        hold_seconds INTEGER,
        exit_reason TEXT,
        payload_json TEXT NOT NULL
    );
    CREATE TABLE signal_decisions (
        id TEXT PRIMARY KEY,
        idempotency_key TEXT UNIQUE,
        signal_id TEXT,
        asset_class TEXT,
        symbol TEXT,
        strategy TEXT,
        decision TEXT,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL
    );
"""


def _columns(db_path, table: str) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]


def _scalar(db_path, sql: str, params=()):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(sql, params).fetchone()[0]


def _trade(trade_id: str, **overrides) -> dict:
    base = {
        "id": trade_id,
        "asset_class": "stock",
        "code": "005930",
        "side": "long",
        "strategy": "bb_reversion",
        "entry_time": "2026-07-02T09:10:00+09:00",
        "entry_price": 71000.0,
        "exit_time": "2026-07-02T10:10:00+09:00",
        "exit_price": 72000.0,
        "quantity": 10,
        "exit_reason": "signal_exit",
    }
    base.update(overrides)
    return base


class TestMigration:
    def test_existing_v1_db_gains_track_id_without_retroactive_tagging(self, tmp_path):
        db_path = tmp_path / "runtime.db"
        with sqlite3.connect(db_path) as conn:
            conn.executescript(_V1_SCHEMA)
            conn.execute(
                "INSERT INTO trades (id, idempotency_key, asset_class, symbol,"
                " pnl, payload_json) VALUES ('old-1', 'old-1', 'stock',"
                " '005930', 1000.0, '{}')"
            )

        ledger = SQLiteRuntimeLedger(db_path)
        try:
            for table in _TAGGED_TABLES:
                assert "track_id" in _columns(db_path, table), table
            # Pre-migration rows stay NULL — no retroactive tagging.
            assert (
                _scalar(db_path, "SELECT track_id FROM trades WHERE id='old-1'") is None
            )
            # New writes on the migrated DB can tag immediately.
            ledger.record_trade(_trade("new-1"), track_id="B")
            ledger.flush()
            assert (
                _scalar(db_path, "SELECT track_id FROM trades WHERE id='new-1'") == "B"
            )
        finally:
            ledger.close()

    def test_migration_is_idempotent_across_two_boots(self, tmp_path):
        db_path = tmp_path / "runtime.db"
        for _ in range(2):
            ledger = SQLiteRuntimeLedger(db_path)
            ledger.close()

        for table in _TAGGED_TABLES:
            cols = _columns(db_path, table)
            assert cols.count("track_id") == 1, table
        assert (
            _scalar(
                db_path,
                "SELECT value FROM ledger_metadata WHERE key='schema_version'",
            )
            == SQLiteRuntimeLedger.SCHEMA_VERSION
        )

    def test_fresh_db_has_track_id_columns(self, tmp_path):
        db_path = tmp_path / "runtime.db"
        SQLiteRuntimeLedger(db_path).close()
        for table in _TAGGED_TABLES:
            assert "track_id" in _columns(db_path, table), table


class TestRecordingApis:
    def test_explicit_track_id_parameter_lands_in_each_table(self, tmp_path):
        db_path = tmp_path / "runtime.db"
        with SQLiteRuntimeLedger(db_path) as ledger:
            ledger.record_order(
                {"id": "o-1", "asset_class": "stock", "code": "005930"},
                track_id="B",
            )
            ledger.record_fill(
                {"id": "f-1", "asset_class": "futures", "code": "A05606"},
                track_id="C",
            )
            ledger.record_trade(_trade("t-1"), track_id="B")
            ledger.record_signal_decision(
                {"decision_id": "d-1", "signal_id": "s-1", "decision": "accepted"},
                track_id="C",
            )

        assert _scalar(db_path, "SELECT track_id FROM orders WHERE id='o-1'") == "B"
        assert _scalar(db_path, "SELECT track_id FROM fills WHERE id='f-1'") == "C"
        assert _scalar(db_path, "SELECT track_id FROM trades WHERE id='t-1'") == "B"
        assert (
            _scalar(db_path, "SELECT track_id FROM signal_decisions WHERE id='d-1'")
            == "C"
        )

    def test_track_id_in_payload_mapping_is_used_when_param_absent(self, tmp_path):
        db_path = tmp_path / "runtime.db"
        with SQLiteRuntimeLedger(db_path) as ledger:
            ledger.record_fill(
                {"id": "f-map", "asset_class": "futures", "track_id": "C"}
            )
        assert _scalar(db_path, "SELECT track_id FROM fills WHERE id='f-map'") == "C"

    def test_explicit_parameter_wins_over_payload_mapping(self, tmp_path):
        db_path = tmp_path / "runtime.db"
        with SQLiteRuntimeLedger(db_path) as ledger:
            ledger.record_trade(_trade("t-both", track_id="C"), track_id="B")
        assert _scalar(db_path, "SELECT track_id FROM trades WHERE id='t-both'") == "B"

    def test_untagged_legacy_calls_remain_null(self, tmp_path):
        db_path = tmp_path / "runtime.db"
        with SQLiteRuntimeLedger(db_path) as ledger:
            ledger.record_order({"id": "o-plain", "code": "005930"})
            ledger.record_trade(_trade("t-plain"))
        assert _scalar(db_path, "SELECT track_id FROM orders WHERE id='o-plain'") is (
            None
        )
        assert _scalar(db_path, "SELECT track_id FROM trades WHERE id='t-plain'") is (
            None
        )

    def test_untagged_upsert_retry_preserves_existing_track_id(self, tmp_path):
        db_path = tmp_path / "runtime.db"
        with SQLiteRuntimeLedger(db_path) as ledger:
            ledger.record_trade(_trade("t-retry"), track_id="B")
            # Retry of the same idempotency key without a tag (legacy caller)
            # must not NULL-out the existing tag.
            ledger.record_trade(_trade("t-retry", exit_reason="retry"))

            ledger.record_signal_decision(
                {"decision_id": "d-retry", "decision": "accepted"}, track_id="C"
            )
            ledger.record_signal_decision(
                {"decision_id": "d-retry", "decision": "accepted"}
            )
        assert _scalar(db_path, "SELECT track_id FROM trades WHERE id='t-retry'") == (
            "B"
        )
        assert (
            _scalar(db_path, "SELECT track_id FROM signal_decisions WHERE id='d-retry'")
            == "C"
        )
        assert (
            _scalar(db_path, "SELECT exit_reason FROM trades WHERE id='t-retry'")
            == "retry"
        )


class TestQueryFilters:
    def _seed(self, ledger: SQLiteRuntimeLedger) -> None:
        ledger.record_trade(_trade("b-1", pnl=100.0), track_id="B")
        ledger.record_trade(_trade("b-2", pnl=-40.0), track_id="B")
        ledger.record_trade(
            _trade("c-1", asset_class="futures", code="A05606", pnl=7.5),
            track_id="C",
        )
        ledger.record_trade(_trade("untagged-1", pnl=5.0))
        ledger.record_fill(
            {"id": "fb-1", "asset_class": "stock", "code": "005930"}, track_id="B"
        )
        ledger.record_fill(
            {"id": "fc-1", "asset_class": "futures", "code": "A05606"}, track_id="C"
        )
        ledger.record_fill({"id": "f-untagged", "code": "005930"})

    def test_per_track_realized_pnl_aggregation(self, tmp_path):
        with SQLiteRuntimeLedger(tmp_path / "runtime.db") as ledger:
            self._seed(ledger)

            track_b = ledger.query_trades({"track_id": "B"})
            track_c = ledger.query_trades({"track": "C"})  # alias key

            assert {t["id"] for t in track_b} == {"b-1", "b-2"}
            assert sum(t["pnl"] for t in track_b) == pytest.approx(60.0)
            assert [t["id"] for t in track_c] == ["c-1"]
            assert track_c[0]["pnl"] == pytest.approx(7.5)

    def test_fills_filter_by_track(self, tmp_path):
        with SQLiteRuntimeLedger(tmp_path / "runtime.db") as ledger:
            self._seed(ledger)

            assert [f["id"] for f in ledger.query_fills({"track_id": "B"})] == ["fb-1"]
            assert [f["id"] for f in ledger.query_fills({"track_id": "C"})] == ["fc-1"]

    def test_unfiltered_queries_keep_backward_compat(self, tmp_path):
        with SQLiteRuntimeLedger(tmp_path / "runtime.db") as ledger:
            self._seed(ledger)

            all_trades = ledger.query_trades()
            all_fills = ledger.query_fills()

            assert {t["id"] for t in all_trades} == {"b-1", "b-2", "c-1", "untagged-1"}
            assert {f["id"] for f in all_fills} == {"fb-1", "fc-1", "f-untagged"}
            untagged = next(t for t in all_trades if t["id"] == "untagged-1")
            assert untagged["track_id"] is None

    def test_track_filter_combines_with_existing_filters(self, tmp_path):
        with SQLiteRuntimeLedger(tmp_path / "runtime.db") as ledger:
            self._seed(ledger)

            rows = ledger.query_trades({"track_id": "B", "symbol": "005930"})
            assert {t["id"] for t in rows} == {"b-1", "b-2"}
            assert ledger.query_trades({"track_id": "B", "symbol": "A05606"}) == []
