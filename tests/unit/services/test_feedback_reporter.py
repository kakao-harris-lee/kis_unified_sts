"""Hermetic tests for the Phase 6A unified feedback report engine + runner.

Hermetic: tmp_path SQLite ledger seeded with synthetic track-tagged trades /
fills / equity / hedge rows, a tmp reports dir, fakeredis, and in-memory
market-structure + backtest-expectation providers. No .env, no Parquet/DuckDB,
no Redis server, no Telegram.

Coverage:
* weekly metric correctness (win rate / EV / payoff ratio) on a known fixture;
* slippage from real fill prices AND explicit missing when prices are absent;
* monthly equity summary / track contribution / risk-band residency / hedge;
* quarterly §8.2 verdict paths (meets / below / insufficient / deferred / C);
* empty-ledger graceful degradation (no crash, explicit missing markers);
* file idempotency, the FIXED 6B Redis pointer contract + TTL, dry-run no-op;
* the engine references slippage from fill payloads only — no shared.execution.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import fakeredis
import pytest

from services.feedback_reporter.main import resolve_period, run_report
from shared.portfolio.config import TRACK_CORE, TRACK_FUTURES, TRACK_STOCK
from shared.reports.config import FeedbackReportsConfig
from shared.reports.feedback import (
    compute_slippage,
    compute_trade_metrics,
)
from shared.storage.runtime_ledger import SQLiteRuntimeLedger

NOW = datetime(2026, 7, 4, 9, 0)  # Saturday


@pytest.fixture
def redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def ledger(tmp_path):
    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
    yield ledger
    ledger.close()


@pytest.fixture
def config(tmp_path):
    cfg = FeedbackReportsConfig()
    cfg.reports_root = str(tmp_path / "reports" / "feedback")
    return cfg


class _Notifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send_message(self, message: str, **_kwargs) -> None:
        self.messages.append(message)


def _seed_trade(ledger, track_id, pnl, day, *, seq=0, strategy="bb_reversion"):
    ledger.record_trade(
        {
            "trade_id": f"{track_id}-{day}-{seq}",
            "asset_class": "stock" if track_id == TRACK_STOCK else "futures",
            "symbol": "TEST",
            "strategy": strategy,
            "side": "sell",
            "pnl": pnl,
            "exit_time": f"{day}T15:30:00",
        },
        track_id=track_id,
    )


def _seed_fill(ledger, track_id, day, *, seq, side, requested, filled, qty):
    payload = {
        "fill_id": f"{track_id}-fill-{day}-{seq}",
        "idempotency_key": f"{track_id}-fill-{day}-{seq}",
        "asset_class": "stock" if track_id == TRACK_STOCK else "futures",
        "symbol": "TEST",
        "side": side,
        "quantity": qty,
        "price": filled,
        "filled_price": filled,
        "requested_price": requested,
        "filled_at": f"{day}T15:30:00",
    }
    ledger.record_fill(payload, track_id=track_id)


def _seed_fill_no_price(ledger, track_id, day, seq):
    ledger.record_fill(
        {
            "fill_id": f"{track_id}-nofill-{day}-{seq}",
            "idempotency_key": f"{track_id}-nofill-{day}-{seq}",
            "asset_class": "futures",
            "symbol": "TEST",
            "side": "sell",
            "quantity": 1,
            "price": 300.0,
            "filled_at": f"{day}T15:30:00",
        },
        track_id=track_id,
    )


# ---------------------------------------------------------------------------
# Pure engine — metric correctness
# ---------------------------------------------------------------------------


def test_trade_metrics_known_fixture():
    trades = [{"pnl": p} for p in (100, -50, 100, -50, 100)]
    metrics = compute_trade_metrics(trades)
    assert metrics["trades"] == 5
    assert metrics["win_rate"] == 0.6
    assert metrics["avg_win_loss"] == 2.0  # avg_win 100 / avg_loss 50
    assert metrics["expectancy"] == 40.0  # 200 / 5
    assert metrics["realized_pnl"] == 200.0


def test_trade_metrics_empty():
    metrics = compute_trade_metrics([])
    assert metrics["trades"] == 0
    assert metrics["win_rate"] is None
    assert metrics["realized_pnl"] == 0.0


def test_slippage_from_prices():
    fills = [
        {
            "payload": {
                "side": "buy",
                "requested_price": 100.0,
                "filled_price": 100.5,
                "quantity": 10,
            }
        },
        {
            "payload": {
                "side": "sell",
                "requested_price": 200.0,
                "filled_price": 199.0,
                "quantity": 10,
            }
        },
    ]
    slip = compute_slippage(fills)
    assert slip is not None
    assert slip["avg_bps"] == 50.0  # both 50 bps adverse
    assert slip["total_cost"] == 15.0  # 0.5*10 + 1.0*10
    assert slip["fills"] == 2
    assert slip["coverage"] == 1.0


def test_slippage_missing_when_no_prices():
    assert compute_slippage([{"payload": {"side": "sell", "price": 300.0}}]) is None
    assert compute_slippage([]) is None


# ---------------------------------------------------------------------------
# Weekly
# ---------------------------------------------------------------------------


def test_weekly_end_to_end(ledger, redis, config):
    day = "2026-07-01"
    for seq, pnl in enumerate((100, -50, 100, -50, 100)):
        _seed_trade(ledger, TRACK_STOCK, pnl, day, seq=seq)
    _seed_fill(
        ledger,
        TRACK_STOCK,
        day,
        seq=0,
        side="buy",
        requested=100.0,
        filled=100.5,
        qty=10,
    )
    _seed_fill(
        ledger,
        TRACK_STOCK,
        day,
        seq=1,
        side="sell",
        requested=200.0,
        filled=199.0,
        qty=10,
    )
    notifier = _Notifier()

    run = run_report(
        kind="weekly",
        config=config,
        ledger=ledger,
        redis=redis,
        period="2026-07-03",
        now=NOW,
        notifier=notifier,
    )

    b = run.report["tracks"][TRACK_STOCK]
    assert b["trades"] == 5
    assert b["win_rate"] == 0.6
    assert b["avg_win_loss"] == 2.0
    assert b["expectancy"] == 40.0
    assert b["realized_pnl"] == 200.0
    assert b["slippage"]["avg_bps"] == 50.0
    assert b["by_strategy"]["bb_reversion"]["trades"] == 5

    # Files written at the fixed 6B path.
    assert run.json_path == Path(config.reports_root) / "weekly" / "2026-07-03.json"
    assert run.md_path.exists()
    on_disk = json.loads(run.json_path.read_text())
    assert on_disk["period_label"] == "2026-07-03"

    # One Telegram headline sent.
    assert len(notifier.messages) == 1
    assert "트랙 B" in notifier.messages[0]


def test_weekly_slippage_missing_marker(ledger, redis, config):
    day = "2026-07-01"
    _seed_trade(ledger, TRACK_FUTURES, 25.0, day, seq=0, strategy="setup_a")
    _seed_fill_no_price(ledger, TRACK_FUTURES, day, 0)

    run = run_report(
        kind="weekly",
        config=config,
        ledger=ledger,
        redis=redis,
        period="2026-07-03",
        now=NOW,
    )
    assert run.report["tracks"][TRACK_FUTURES]["slippage"] is None
    assert "track_c_slippage" in run.report["missing"]


# ---------------------------------------------------------------------------
# Monthly
# ---------------------------------------------------------------------------


def _market_provider(rows):
    def _read(_start, _end):
        return rows

    return _read


def test_monthly_end_to_end(ledger, redis, config):
    _seed_trade(ledger, TRACK_STOCK, 200_000.0, "2026-06-15", seq=0)
    _seed_trade(
        ledger, TRACK_FUTURES, -50_000.0, "2026-06-16", seq=0, strategy="setup_c"
    )
    ledger.record_portfolio_equity_daily(
        {
            "trade_date": "2026-06-01",
            "total_equity": 15_000_000,
            "month_start_equity": 15_000_000,
            "month_peak_equity": 15_000_000,
            "monthly_mdd_pct": 0.0,
            "stage": "NORMAL",
            "mode": "shadow",
        }
    )
    ledger.record_portfolio_equity_daily(
        {
            "trade_date": "2026-06-30",
            "total_equity": 14_000_000,
            "month_start_equity": 15_000_000,
            "month_peak_equity": 15_000_000,
            "monthly_mdd_pct": -0.0667,
            "stage": "REDUCE",
            "mode": "shadow",
        }
    )
    ledger.record_hedge_advice(
        {
            "trade_date": "2026-06-20",
            "asof_ts": "2026-06-20T18:45:00",
            "product": "101S06",
            "advisory_active": True,
            "recommended_short_contracts": 3,
            "band": "CAUTION",
        }
    )
    market_rows = [
        {
            "trade_date": "2026-06-01",
            "risk_band": "RISK_ON",
            "risk_score": 20.0,
            "k200_close": 350.0,
        },
        {
            "trade_date": "2026-06-02",
            "risk_band": "RISK_ON",
            "risk_score": 25.0,
            "k200_close": 351.0,
        },
        {
            "trade_date": "2026-06-30",
            "risk_band": "NEUTRAL",
            "risk_score": 50.0,
            "k200_close": 340.0,
        },
    ]

    run = run_report(
        kind="monthly",
        config=config,
        ledger=ledger,
        redis=redis,
        period="2026-06",
        now=NOW,
        market_rows_provider=_market_provider(market_rows),
    )
    report = run.report

    eq = report["equity"]
    assert eq["month_start"] == 15_000_000
    assert eq["month_end"] == 14_000_000
    assert eq["stage_reached"] == "REDUCE"
    assert eq["monthly_return_pct"] == pytest.approx(-6.6667, abs=1e-3)

    contrib = report["contribution"]
    assert contrib["total_pnl"] == 150_000.0
    assert contrib[TRACK_STOCK]["contribution_pct"] == pytest.approx(133.3333, abs=1e-3)
    assert contrib[TRACK_FUTURES]["contribution_pct"] == pytest.approx(
        -33.3333, abs=1e-3
    )

    assert report["risk_bands"]["days_in_band"] == {"NEUTRAL": 1, "RISK_ON": 2}
    assert report["hedge"]["advisory_active_events"] == 1
    assert report["hedge"]["max_recommended_short_contracts"] == 3


def test_monthly_empty_missing_markers(ledger, redis, config):
    run = run_report(
        kind="monthly",
        config=config,
        ledger=ledger,
        redis=redis,
        period="2026-06",
        now=NOW,
        market_rows_provider=_market_provider([]),
    )
    missing = run.report["missing"]
    assert "equity_curve" in missing
    assert "market_risk_bands" in missing
    assert "hedge_advice" in missing
    assert run.report["equity"] is None
    assert run.json_path.exists()  # still writes a valid (empty) report


# ---------------------------------------------------------------------------
# Quarterly §8.2
# ---------------------------------------------------------------------------


def _quarterly(ledger, redis, config, *, expectation, capital_base_b=10_000_000.0):
    return run_report(
        kind="quarterly",
        config=config,
        ledger=ledger,
        redis=redis,
        period="2026-Q2",
        now=NOW,
        market_rows_provider=_market_provider([]),
        expectation_loader=lambda _dir: expectation,
        capital_base_b=capital_base_b,
    )


def test_quarterly_track_b_meets(ledger, redis, config):
    # 3.0% realized vs threshold (4.0 - 0) * 0.6 = 2.4% → meets.
    _seed_trade(ledger, TRACK_STOCK, 300_000.0, "2026-05-10", seq=0)
    run = _quarterly(
        ledger, redis, config, expectation={"expectation_pct": 4.0, "source": "e.json"}
    )
    tb = run.report["quarterly"]["track_b"]
    assert tb["realized_return_pct"] == 3.0
    assert tb["threshold_pct"] == 2.4
    assert tb["verdict"] == "meets"


def test_quarterly_track_b_below(ledger, redis, config):
    _seed_trade(ledger, TRACK_STOCK, 100_000.0, "2026-05-10", seq=0)  # 1.0% < 2.4%
    run = _quarterly(
        ledger, redis, config, expectation={"expectation_pct": 4.0, "source": "e.json"}
    )
    assert run.report["quarterly"]["track_b"]["verdict"] == "below"


def test_quarterly_track_b_insufficient(ledger, redis, config):
    _seed_trade(ledger, TRACK_STOCK, 300_000.0, "2026-05-10", seq=0)
    run = _quarterly(ledger, redis, config, expectation=None)
    assert run.report["quarterly"]["track_b"]["verdict"] == "insufficient_evidence"
    assert "backtest_expectation" in run.report["missing"]


def test_quarterly_track_c_review_termination(ledger, redis, config):
    # Inception 18 months before quarter end, cumulative negative → terminate.
    _seed_trade(ledger, TRACK_FUTURES, -100.0, "2024-12-01", seq=0, strategy="setup_a")
    _seed_trade(ledger, TRACK_FUTURES, -50.0, "2026-05-01", seq=1, strategy="setup_a")
    run = _quarterly(
        ledger, redis, config, expectation={"expectation_pct": 4.0, "source": "e.json"}
    )
    tc = run.report["quarterly"]["track_c"]
    assert tc["verdict"] == "review_termination"
    assert tc["ev_positive"] is False
    assert tc["checkpoints"]["ev_final"] is True


def test_quarterly_track_c_on_track(ledger, redis, config):
    _seed_trade(ledger, TRACK_FUTURES, 500.0, "2026-04-01", seq=0, strategy="setup_a")
    run = _quarterly(
        ledger, redis, config, expectation={"expectation_pct": 4.0, "source": "e.json"}
    )
    assert run.report["quarterly"]["track_c"]["verdict"] == "on_track"


def test_quarterly_track_c_insufficient(ledger, redis, config):
    run = _quarterly(
        ledger, redis, config, expectation={"expectation_pct": 4.0, "source": "e.json"}
    )
    assert run.report["quarterly"]["track_c"]["verdict"] == "insufficient_evidence"
    assert "track_c_history" in run.report["missing"]


def test_quarterly_track_a_deferred(ledger, redis, config):
    # Track A equity exists but < 3 years of history → deferred.
    ledger.record_portfolio_equity_daily(
        {
            "trade_date": "2026-01-02",
            "total_equity": 50_000_000,
            "track_a_equity": 33_000_000,
            "month_start_equity": 50_000_000,
            "month_peak_equity": 50_000_000,
            "monthly_mdd_pct": 0.0,
            "stage": "NORMAL",
            "mode": "shadow",
        }
    )
    run = _quarterly(
        ledger, redis, config, expectation={"expectation_pct": 4.0, "source": "e.json"}
    )
    ta = run.report["quarterly"]["track_a"]
    assert ta["verdict"] == "deferred"
    assert ta["history_years"] is not None and ta["history_years"] < 3


def test_quarterly_track_a_insufficient(ledger, redis, config):
    run = _quarterly(
        ledger, redis, config, expectation={"expectation_pct": 4.0, "source": "e.json"}
    )
    assert run.report["quarterly"]["track_a"]["verdict"] == "insufficient_evidence"
    assert "track_a_history" in run.report["missing"]


# ---------------------------------------------------------------------------
# Redis pointer contract, idempotency, dry-run, empty
# ---------------------------------------------------------------------------

_POINTER_FIELDS = {
    "kind",
    "period_label",
    "generated_at",
    "json_path",
    "md_path",
    "headline",
}


def test_redis_pointer_contract_and_ttl(ledger, redis, config):
    run_report(
        kind="weekly",
        config=config,
        ledger=ledger,
        redis=redis,
        period="2026-07-03",
        now=NOW,
    )
    key = config.redis.latest_key
    stored = redis.hgetall(key)
    assert set(stored) == _POINTER_FIELDS
    assert stored["kind"] == "weekly"
    assert stored["period_label"] == "2026-07-03"
    headline = json.loads(stored["headline"])
    assert headline["kind"] == "weekly"
    ttl = redis.ttl(key)
    assert 0 < ttl <= config.redis.latest_ttl_seconds


def test_file_idempotency(ledger, redis, config):
    _seed_trade(ledger, TRACK_STOCK, 100.0, "2026-07-01", seq=0)
    first = run_report(
        kind="weekly",
        config=config,
        ledger=ledger,
        redis=redis,
        period="2026-07-03",
        now=NOW,
    )
    content1 = first.json_path.read_text()
    second = run_report(
        kind="weekly",
        config=config,
        ledger=ledger,
        redis=redis,
        period="2026-07-03",
        now=NOW,
    )
    assert second.json_path == first.json_path  # same path — overwrite
    # generated_at is identical (fixed now) so content is byte-stable.
    assert second.json_path.read_text() == content1


def test_dry_run_writes_nothing(ledger, redis, config):
    _seed_trade(ledger, TRACK_STOCK, 100.0, "2026-07-01", seq=0)
    run = run_report(
        kind="weekly",
        config=config,
        ledger=ledger,
        redis=redis,
        period="2026-07-03",
        now=NOW,
        dry_run=True,
    )
    assert run.json_path is None and run.md_path is None
    assert not Path(config.reports_root).exists()
    assert redis.hgetall(config.redis.latest_key) == {}


def test_empty_ledger_all_kinds(ledger, redis, config):
    for kind, period in (
        ("weekly", "2026-07-03"),
        ("monthly", "2026-06"),
        ("quarterly", "2026-Q2"),
    ):
        run = run_report(
            kind=kind,
            config=config,
            ledger=ledger,
            redis=redis,
            period=period,
            now=NOW,
            market_rows_provider=_market_provider([]),
            expectation_loader=lambda _d: None,
            capital_base_b=10_000_000.0,
        )
        assert run.report["kind"] == kind
        assert run.json_path.exists()
        # every track block present with zero trades
        for track_id in (TRACK_STOCK, TRACK_FUTURES, TRACK_CORE):
            assert run.report["tracks"][track_id]["trades"] == 0


# ---------------------------------------------------------------------------
# Period resolution + no shared.execution pollution
# ---------------------------------------------------------------------------


def test_resolve_period_defaults():
    now = datetime(2026, 7, 4, 9, 0)  # Saturday
    weekly = resolve_period("weekly", None, now)
    assert weekly.label == "2026-07-03"  # previous Friday
    monthly = resolve_period("monthly", None, now)
    assert monthly.label == "2026-06"
    assert monthly.start == date(2026, 6, 1) and monthly.end == date(2026, 6, 30)
    quarterly = resolve_period("quarterly", None, now)
    assert quarterly.label == "2026-Q2"  # previous quarter
    assert quarterly.start == date(2026, 4, 1) and quarterly.end == date(2026, 6, 30)


def test_no_shared_execution_pollution():
    source = Path("shared/reports/feedback.py").read_text()
    assert "shared.execution" not in source
    assert "import shared.execution" not in source
