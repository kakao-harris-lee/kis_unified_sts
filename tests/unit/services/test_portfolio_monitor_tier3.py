"""Unit tests for services.portfolio_monitor.tier3_watch (Phase 5A).

Pins the FIXED 5E-UI Redis contract on ``portfolio:tier3:watch`` (exact field
names, drawdown as a FRACTION, TTL), the inclusive −15% trigger boundary, the
rolling-peak window + no-look-ahead evaluation, the rising-edge one-shot
Telegram advisory ("발동 판단·집행은 수동"), and the insufficient-data
no-publish path. Hermetic: fakeredis + injected closes provider.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import fakeredis
import pytest

from services.portfolio_monitor.main import run_snapshot
from services.portfolio_monitor.tier3_watch import (
    Tier3RunContext,
    evaluate_tier3_watch,
    run_tier3_watch,
)
from shared.portfolio.config import TRACK_FUTURES, TRACK_STOCK, PortfolioConfig
from shared.storage.runtime_ledger import SQLiteRuntimeLedger

DAY = date(2026, 7, 6)  # Monday
NOW = datetime(2026, 7, 6, 19, 0)
WATCH_KEY = "portfolio:tier3:watch"

# Fixed contract with the 5E UI lane — exact field-name set.
_CONTRACT_FIELDS = {
    "kospi_close",
    "kospi_peak",
    "drawdown",
    "trigger_threshold",
    "triggered",
    "asof_ts",
}


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send_message(self, message: str, **_kwargs) -> None:
        self.messages.append(message)


@pytest.fixture
def redis():
    return fakeredis.FakeRedis(decode_responses=True)


def _closes(latest_close: float, peak: float = 400.0) -> list[tuple[date, float]]:
    """Simple history: 10 days at ``peak`` then today's ``latest_close``."""
    rows = [(DAY - timedelta(days=offset), peak) for offset in range(10, 0, -1)]
    rows.append((DAY, latest_close))
    return rows


def _context(closes, notifier=None, config=None) -> Tier3RunContext:
    return Tier3RunContext(
        config=config or PortfolioConfig(),
        closes_provider=lambda _start, _end: closes,
        notifier=notifier,
    )


def _run(redis, closes, notifier=None, config=None):
    return run_tier3_watch(
        context=_context(closes, notifier=notifier, config=config),
        redis=redis,
        trade_date=DAY,
        now=NOW,
    )


# ---------------------------------------------------------------------------
# Redis contract
# ---------------------------------------------------------------------------


class TestRedisContract:
    def test_hash_fields_ttl_and_fraction_unit(self, redis):
        watch = _run(redis, _closes(latest_close=336.0))  # -16% from 400

        raw = redis.hgetall(WATCH_KEY)
        assert set(raw) == _CONTRACT_FIELDS
        assert raw["kospi_close"] == "336.0000"
        assert raw["kospi_peak"] == "400.0000"
        assert raw["drawdown"] == "-0.1600"  # FRACTION — Phase 3 unit decision
        assert raw["trigger_threshold"] == "-0.1500"
        assert raw["triggered"] == "true"
        assert datetime.fromisoformat(raw["asof_ts"]) == NOW
        assert 0 < redis.ttl(WATCH_KEY) <= 86400
        assert watch is not None and watch.triggered

    def test_not_triggered_above_threshold(self, redis):
        _run(redis, _closes(latest_close=380.0))  # -5%
        raw = redis.hgetall(WATCH_KEY)
        assert raw["triggered"] == "false"
        assert raw["drawdown"] == "-0.0500"

    def test_stale_fields_never_linger(self, redis):
        redis.hset(WATCH_KEY, mapping={"legacy_field": "1"})
        _run(redis, _closes(latest_close=380.0))
        assert "legacy_field" not in redis.hgetall(WATCH_KEY)

    def test_threshold_comes_from_fund_movement_config(self, redis):
        config = PortfolioConfig()
        config.fund_movement.tier3_activation.kospi_drawdown_from_peak = -0.10
        _run(redis, _closes(latest_close=356.0), config=config)  # -11%
        raw = redis.hgetall(WATCH_KEY)
        assert raw["trigger_threshold"] == "-0.1000"
        assert raw["triggered"] == "true"


# ---------------------------------------------------------------------------
# Drawdown math (boundary / window / look-ahead)
# ---------------------------------------------------------------------------


class TestEvaluation:
    def test_exactly_minus_15_pct_triggers(self, redis):
        # 설계서 §1.2 "고점 대비 -15% 이상 하락" — inclusive boundary.
        _run(redis, _closes(latest_close=340.0))  # (340-400)/400 == -0.15
        raw = redis.hgetall(WATCH_KEY)
        assert raw["drawdown"] == "-0.1500"
        assert raw["triggered"] == "true"

    def test_just_above_threshold_does_not_trigger(self, redis):
        _run(redis, _closes(latest_close=340.5))
        assert redis.hgetall(WATCH_KEY)["triggered"] == "false"

    def test_peak_window_excludes_older_highs(self):
        closes = [(DAY - timedelta(days=30), 500.0)]  # ancient high
        closes += [(DAY - timedelta(days=5 - i), 400.0) for i in range(5)]
        closes.append((DAY, 380.0))
        watch = evaluate_tier3_watch(
            closes,
            trade_date=DAY,
            peak_window_days=6,  # 5×400 + today's 380 — the 500 falls out
            trigger_threshold=-0.15,
            asof_ts=NOW,
        )
        assert watch is not None
        assert watch.kospi_peak == pytest.approx(400.0)
        assert watch.drawdown == pytest.approx(-0.05)

    def test_rows_after_trade_date_are_excluded(self):
        closes = _closes(latest_close=380.0)
        closes.append((DAY + timedelta(days=1), 100.0))  # future row: ignored
        watch = evaluate_tier3_watch(
            closes,
            trade_date=DAY,
            peak_window_days=252,
            trigger_threshold=-0.15,
            asof_ts=NOW,
        )
        assert watch is not None
        assert watch.kospi_close == pytest.approx(380.0)

    def test_peak_includes_latest_close(self):
        closes = [(DAY - timedelta(days=1), 390.0), (DAY, 400.0)]
        watch = evaluate_tier3_watch(
            closes,
            trade_date=DAY,
            peak_window_days=252,
            trigger_threshold=-0.15,
            asof_ts=NOW,
        )
        assert watch is not None
        assert watch.kospi_peak == pytest.approx(400.0)
        assert watch.drawdown == pytest.approx(0.0)

    def test_unordered_history_is_sorted(self):
        closes = [(DAY, 336.0), (DAY - timedelta(days=3), 400.0)]
        watch = evaluate_tier3_watch(
            closes,
            trade_date=DAY,
            peak_window_days=252,
            trigger_threshold=-0.15,
            asof_ts=NOW,
        )
        assert watch is not None
        assert watch.kospi_close == pytest.approx(336.0)
        assert watch.triggered


# ---------------------------------------------------------------------------
# Insufficient data / disabled
# ---------------------------------------------------------------------------


class TestDegradedPaths:
    def test_no_history_publishes_nothing(self, redis, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            watch = _run(redis, [])
        assert watch is None
        assert redis.hgetall(WATCH_KEY) == {}
        assert any("nothing published" in record.message for record in caplog.records)

    def test_broken_provider_publishes_nothing(self, redis):
        def _boom(_start, _end):
            raise RuntimeError("store down")

        context = Tier3RunContext(
            config=PortfolioConfig(), closes_provider=_boom, notifier=None
        )
        watch = run_tier3_watch(context=context, redis=redis, trade_date=DAY, now=NOW)
        assert watch is None
        assert redis.hgetall(WATCH_KEY) == {}

    def test_disabled_watch_skips(self, redis):
        config = PortfolioConfig()
        config.monitor.tier3_watch.enabled = False
        watch = _run(redis, _closes(latest_close=336.0), config=config)
        assert watch is None
        assert redis.hgetall(WATCH_KEY) == {}


# ---------------------------------------------------------------------------
# Rising-edge alert (Telegram once, manual-execution wording)
# ---------------------------------------------------------------------------


class TestRisingEdgeAlert:
    def test_alert_fires_once_on_rising_edge(self, redis):
        notifier = FakeNotifier()
        _run(redis, _closes(latest_close=336.0), notifier=notifier)
        assert len(notifier.messages) == 1
        assert "수동" in notifier.messages[0]
        assert "자동 매수는 존재하지 않습니다" in notifier.messages[0]

        # still triggered next run → no repeat while the hash persists
        _run(redis, _closes(latest_close=330.0), notifier=notifier)
        assert len(notifier.messages) == 1

    def test_no_alert_below_trigger(self, redis):
        notifier = FakeNotifier()
        _run(redis, _closes(latest_close=380.0), notifier=notifier)
        assert notifier.messages == []

    def test_recovery_then_retrigger_alerts_again(self, redis):
        notifier = FakeNotifier()
        _run(redis, _closes(latest_close=336.0), notifier=notifier)  # edge 1
        _run(redis, _closes(latest_close=390.0), notifier=notifier)  # recovered
        _run(redis, _closes(latest_close=335.0), notifier=notifier)  # edge 2
        assert len(notifier.messages) == 2

    def test_alerts_disabled_publishes_without_message(self, redis):
        notifier = FakeNotifier()
        config = PortfolioConfig()
        config.monitor.tier3_watch.alerts_enabled = False
        _run(redis, _closes(latest_close=336.0), notifier=notifier, config=config)
        assert redis.hgetall(WATCH_KEY)["triggered"] == "true"
        assert notifier.messages == []


# ---------------------------------------------------------------------------
# run_snapshot wiring (watch failure never fails the equity run)
# ---------------------------------------------------------------------------


class _AlwaysOpenCalendar:
    def is_market_day(self, _day: date) -> bool:
        return True


class TestSnapshotWiring:
    def _snapshot(self, ledger, redis, tier3, dry_run=False):
        return run_snapshot(
            config=PortfolioConfig(),
            ledger=ledger,
            redis=redis,
            positions_providers={TRACK_STOCK: lambda: [], TRACK_FUTURES: lambda: []},
            calendar=_AlwaysOpenCalendar(),
            trade_date=DAY,
            now=NOW,
            sentinel_path="/nonexistent/never-written",
            tier3=tier3,
            dry_run=dry_run,
        )

    @pytest.fixture
    def ledger(self, tmp_path):
        ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
        yield ledger
        ledger.close()

    def test_snapshot_publishes_watch(self, ledger, redis):
        tier3 = _context(_closes(latest_close=336.0))
        assert self._snapshot(ledger, redis, tier3) == 0
        assert redis.hgetall(WATCH_KEY)["triggered"] == "true"
        assert redis.hgetall("portfolio:equity:latest") != {}

    def test_watch_crash_never_fails_equity_run(self, ledger, redis, monkeypatch):
        import services.portfolio_monitor.main as monitor_main

        def _boom(**_kwargs):
            raise RuntimeError("tier3 exploded")

        monkeypatch.setattr(monitor_main, "run_tier3_watch", _boom)
        tier3 = _context(_closes(latest_close=336.0))
        assert self._snapshot(ledger, redis, tier3) == 0
        assert redis.hgetall("portfolio:equity:latest") != {}  # equity intact

    def test_dry_run_skips_watch(self, ledger, redis):
        tier3 = _context(_closes(latest_close=336.0))
        assert self._snapshot(ledger, redis, tier3, dry_run=True) == 0
        assert redis.hgetall(WATCH_KEY) == {}
