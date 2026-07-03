"""portfolio_equity_daily table tests (Phase 3B ledger migration).

Hermetic: tmp_path SQLite files only.
"""

from __future__ import annotations

import json

import pytest

from shared.storage.runtime_ledger import RuntimeLedgerError, SQLiteRuntimeLedger


@pytest.fixture
def ledger(tmp_path):
    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
    yield ledger
    ledger.close()


def _row(trade_date: str = "2026-07-06", **kwargs) -> dict:
    row = {
        "trade_date": trade_date,
        "track_a_equity": None,
        "track_b_equity": 10_050_000.0,
        "track_c_equity": 4_950_000.0,
        "total_equity": 15_000_000.0,
        "month_start_equity": 15_100_000.0,
        "month_peak_equity": 15_200_000.0,
        "monthly_mdd_pct": -0.0132,
        "stage": "NORMAL",
        "mode": "shadow",
        "degraded": False,
        "missing_components": ["track_a"],
    }
    row.update(kwargs)
    return row


class TestMigration:
    def test_migration_is_idempotent_across_reopens(self, tmp_path):
        path = tmp_path / "runtime.db"
        first = SQLiteRuntimeLedger(path)
        first.record_portfolio_equity_daily(_row())
        first.close()

        # Re-opening runs _migrate() again on an existing DB — must not fail
        # and must preserve stored rows (3A idempotent-migration pattern).
        second = SQLiteRuntimeLedger(path)
        rows = second.query_portfolio_equity_daily()
        assert len(rows) == 1
        assert rows[0]["trade_date"] == "2026-07-06"
        second.close()

    def test_schema_version_bumped(self, ledger):
        value = (
            ledger._require_conn()
            .execute("SELECT value FROM ledger_metadata WHERE key='schema_version'")
            .fetchone()[0]
        )
        # v4 added the hedge_advice table (Phase 4A) on top of v3's
        # portfolio_equity_daily — the metadata always tracks the constant.
        assert value == SQLiteRuntimeLedger.SCHEMA_VERSION == "4"


class TestUpsert:
    def test_same_day_rerun_replaces_row(self, ledger):
        ledger.record_portfolio_equity_daily(_row(total_equity=15_000_000.0))
        ledger.record_portfolio_equity_daily(
            _row(total_equity=14_500_000.0, stage="REDUCE")
        )
        rows = ledger.query_portfolio_equity_daily()
        assert len(rows) == 1
        assert rows[0]["total_equity"] == pytest.approx(14_500_000.0)
        assert rows[0]["stage"] == "REDUCE"

    def test_nullable_track_equities_roundtrip(self, ledger):
        ledger.record_portfolio_equity_daily(_row())
        row = ledger.query_portfolio_equity_daily()[0]
        assert row["track_a_equity"] is None
        assert row["track_b_equity"] == pytest.approx(10_050_000.0)
        assert json.loads(row["missing_components"]) == ["track_a"]

    def test_missing_trade_date_rejected(self, ledger):
        with pytest.raises(RuntimeLedgerError):
            ledger.record_portfolio_equity_daily({"total_equity": 1.0})


class TestQuery:
    def _seed(self, ledger):
        for day, total in [
            ("2026-06-30", 15_500_000.0),
            ("2026-07-01", 15_200_000.0),
            ("2026-07-02", 15_000_000.0),
            ("2026-07-03", 14_800_000.0),
        ]:
            ledger.record_portfolio_equity_daily(_row(day, total_equity=total))

    def test_month_filter(self, ledger):
        self._seed(ledger)
        rows = ledger.query_portfolio_equity_daily({"month": "2026-07"})
        assert [row["trade_date"] for row in rows] == [
            "2026-07-01",
            "2026-07-02",
            "2026-07-03",
        ]

    def test_range_and_order_ascending(self, ledger):
        self._seed(ledger)
        rows = ledger.query_portfolio_equity_daily(
            {"start": "2026-07-01", "end": "2026-07-02"}
        )
        assert [row["trade_date"] for row in rows] == ["2026-07-01", "2026-07-02"]

    def test_limit_zero_returns_all(self, ledger):
        self._seed(ledger)
        assert len(ledger.query_portfolio_equity_daily({"limit": 0})) == 4

    def test_limit_applies(self, ledger):
        self._seed(ledger)
        assert len(ledger.query_portfolio_equity_daily({"limit": 2})) == 2
