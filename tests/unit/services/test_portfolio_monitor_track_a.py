"""Track A manual-ledger equity integration in services.portfolio_monitor.

Phase 5A: when ``run_snapshot(core_holdings=...)`` carries a provisioned
manual ledger, ``track_a_equity`` publishes ``Σ(shares × valuation) + cash``
into the FIXED 3D-UI Redis contract; empty/unvalued ledgers keep the
pre-Phase 5 shape ("" + ``track_a`` coverage marker); stale valuations
publish the value plus the ``track_a_valuation_stale`` marker.

Hermetic: fakeredis + tmp_path SQLite ledger + in-memory CoreHoldings.
"""

from __future__ import annotations

import json
from datetime import date, datetime

import fakeredis
import pytest

from services.portfolio_monitor.main import run_snapshot
from shared.portfolio.config import TRACK_FUTURES, TRACK_STOCK, PortfolioConfig
from shared.portfolio.core_holdings import CoreHoldings
from shared.storage.runtime_ledger import SQLiteRuntimeLedger

DAY1 = date(2026, 7, 6)  # Monday
NOW1 = datetime(2026, 7, 6, 19, 0)
LATEST_KEY = "portfolio:equity:latest"


class _AlwaysOpenCalendar:
    def is_market_day(self, _day: date) -> bool:
        return True


@pytest.fixture
def redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def ledger(tmp_path):
    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
    yield ledger
    ledger.close()


def _holding(**overrides) -> dict:
    holding = {
        "symbol": "012450",
        "name": "한화에어로스페이스",
        "sector": "defense",
        "thesis": "수주잔고 확정형",
        "kill_criteria": ["수주잔고 감소"],
        "shares": 10,
        "avg_price": 900_000,
        "last_valuation": {"date": "2026-07-01", "price": 1_000_000},
    }
    holding.update(overrides)
    return holding


def _run(ledger, redis, core_holdings=None, day=DAY1, now=NOW1):
    return run_snapshot(
        config=PortfolioConfig(),  # defaults: B=10M, C=5M, A=None, shadow
        ledger=ledger,
        redis=redis,
        positions_providers={TRACK_STOCK: lambda: [], TRACK_FUTURES: lambda: []},
        calendar=_AlwaysOpenCalendar(),
        trade_date=day,
        now=now,
        sentinel_path="/nonexistent/never-written",
        core_holdings=core_holdings,
    )


class TestTrackAEquityIntegration:
    def test_valued_ledger_publishes_track_a_equity(self, ledger, redis):
        core = CoreHoldings(cash_krw=1_500_000, holdings=[_holding()])
        assert _run(ledger, redis, core_holdings=core) == 0

        raw = redis.hgetall(LATEST_KEY)
        assert float(raw["track_a_equity"]) == pytest.approx(11_500_000.0)
        # total = A 11.5M + B 10M + C 5M
        assert float(raw["total_equity"]) == pytest.approx(26_500_000.0)
        missing = json.loads(raw["missing_components"])
        assert "track_a" not in missing
        assert raw["degraded"] == "false"

    def test_track_a_row_persisted(self, ledger, redis):
        core = CoreHoldings(cash_krw=1_500_000, holdings=[_holding()])
        _run(ledger, redis, core_holdings=core)
        rows = ledger.query_portfolio_equity_daily()
        assert len(rows) == 1
        assert rows[0]["track_a_equity"] == pytest.approx(11_500_000.0)

    def test_empty_ledger_keeps_missing_shape(self, ledger, redis):
        assert _run(ledger, redis, core_holdings=CoreHoldings()) == 0
        raw = redis.hgetall(LATEST_KEY)
        assert raw["track_a_equity"] == ""
        assert "track_a" in json.loads(raw["missing_components"])
        assert float(raw["total_equity"]) == pytest.approx(15_000_000.0)

    def test_none_core_holdings_keeps_legacy_shape(self, ledger, redis):
        assert _run(ledger, redis, core_holdings=None) == 0
        raw = redis.hgetall(LATEST_KEY)
        assert raw["track_a_equity"] == ""
        assert "track_a" in json.loads(raw["missing_components"])

    def test_unvalued_holding_reads_missing(self, ledger, redis):
        core = CoreHoldings(
            holdings=[_holding(last_valuation={"date": None, "price": None})]
        )
        _run(ledger, redis, core_holdings=core)
        raw = redis.hgetall(LATEST_KEY)
        assert raw["track_a_equity"] == ""
        assert "track_a" in json.loads(raw["missing_components"])

    def test_stale_valuation_publishes_value_with_marker(self, ledger, redis):
        core = CoreHoldings(
            holdings=[
                _holding(last_valuation={"date": "2026-04-01", "price": 1_000_000})
            ]
        )
        _run(ledger, redis, core_holdings=core)
        raw = redis.hgetall(LATEST_KEY)
        assert float(raw["track_a_equity"]) == pytest.approx(10_000_000.0)
        missing = json.loads(raw["missing_components"])
        assert "track_a_valuation_stale" in missing
        assert "track_a" not in missing
        # stale is expected drift on a manual quarterly track, not degradation
        assert raw["degraded"] == "false"

    def test_stale_threshold_is_config_driven(self, ledger, redis):
        config = PortfolioConfig()
        config.monitor.track_a.valuation_stale_days = 2  # 5-day-old valuation
        core = CoreHoldings(cash_krw=0, holdings=[_holding()])
        run_snapshot(
            config=config,
            ledger=ledger,
            redis=redis,
            positions_providers={TRACK_STOCK: lambda: [], TRACK_FUTURES: lambda: []},
            calendar=_AlwaysOpenCalendar(),
            trade_date=DAY1,
            now=NOW1,
            sentinel_path="/nonexistent/never-written",
            core_holdings=core,
        )
        missing = json.loads(redis.hgetall(LATEST_KEY)["missing_components"])
        assert "track_a_valuation_stale" in missing
