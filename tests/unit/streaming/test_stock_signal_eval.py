"""Contract tests for the stock signal-eval observability module.

Mirrors the futures ``trading:futures:setup_eval`` reject-reason pattern for the
decoupled stock M4-P daemon: per-(symbol, strategy) entry-evaluation outcomes
aggregated into a publishable hash so "why 0 signals" is answerable live.

The collector is pure (no Redis): it accumulates per-strategy outcomes and
renders the aggregate payload. Publishing/throttling is exercised in the daemon
tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from shared.streaming.stock_signal_eval import (
    REJECT_COLD,
    REJECT_CONDITIONS_NOT_MET,
    REJECT_NO_DAILY_WATCHLIST,
    REJECT_NO_MARKET_DATA,
    REJECT_NO_SMA_200,
    SignalEvalCollector,
    StockSignalEvalConfig,
)

_NOW = datetime(2026, 6, 24, 1, 42, tzinfo=UTC)  # 10:42 KST


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_config_defaults_enabled_with_ttl_and_key():
    cfg = StockSignalEvalConfig()
    assert cfg.enabled is True
    assert cfg.redis_key == "stock:daemon:signal_eval"
    # Repo convention: new operational keys carry a 24h TTL.
    assert cfg.publish_ttl_seconds == 86_400


def test_config_load_falls_back_to_defaults_on_missing_file():
    # No config/stock_signal_eval.yaml section required — load() must be safe.
    cfg = StockSignalEvalConfig.load()
    assert isinstance(cfg, StockSignalEvalConfig)
    assert cfg.redis_key == "stock:daemon:signal_eval"


# ---------------------------------------------------------------------------
# Collector: aggregation shape
# ---------------------------------------------------------------------------


def test_collector_records_signal_outcome():
    c = SignalEvalCollector()
    c.record("momentum_breakout", "005930", "signal", "long")
    payload = c.to_payload(now=_NOW)

    assert "momentum_breakout" in payload
    entry = json.loads(payload["momentum_breakout"])
    assert entry["strategy"] == "momentum_breakout"
    assert entry["evaluated"] == 1
    assert entry["signals"] == 1
    assert entry["rejects"] == 0
    # A firing strategy's outcome is "signal" so the operator sees it traded.
    assert entry["outcome"] == "signal"
    # KST-native timestamp.
    assert entry["ts_kst"].startswith("2026-06-24T10:42")


def test_collector_aggregates_reject_reasons_with_dominant():
    c = SignalEvalCollector()
    # 3 symbols rejected for no_sma_200, 1 for conditions_not_met.
    c.record("pattern_pullback", "005930", "reject", REJECT_NO_SMA_200)
    c.record("pattern_pullback", "000660", "reject", REJECT_NO_SMA_200)
    c.record("pattern_pullback", "035720", "reject", REJECT_NO_SMA_200)
    c.record("pattern_pullback", "051910", "reject", REJECT_CONDITIONS_NOT_MET)
    payload = c.to_payload(now=_NOW)

    entry = json.loads(payload["pattern_pullback"])
    assert entry["evaluated"] == 4
    assert entry["signals"] == 0
    assert entry["rejects"] == 4
    assert entry["outcome"] == "reject"
    # Dominant reason = the modal reject, with its count, so the operator reads
    # "for each strategy, how many symbols rejected and the dominant reason."
    assert entry["reason"] == REJECT_NO_SMA_200
    assert entry["reason_counts"][REJECT_NO_SMA_200] == 3
    assert entry["reason_counts"][REJECT_CONDITIONS_NOT_MET] == 1


def test_collector_signal_outcome_wins_over_rejects():
    """If a strategy fired for ANY symbol the aggregate outcome is 'signal'."""
    c = SignalEvalCollector()
    c.record("williams_r", "005930", "reject", REJECT_CONDITIONS_NOT_MET)
    c.record("williams_r", "000660", "signal", "long")
    entry = json.loads(c.to_payload(now=_NOW)["williams_r"])
    assert entry["outcome"] == "signal"
    assert entry["signals"] == 1
    assert entry["rejects"] == 1


def test_collector_distinguishes_cold_and_daily_missing_and_watchlist():
    """Warmth dead-zone vs no_sma_200 vs daily-gate must be distinguishable.

    The diagnosis showed these three looked identical to "no setup"; they must
    surface as distinct reasons.
    """
    c = SignalEvalCollector()
    c.record("golden_cross", "005930", "reject", REJECT_COLD)
    c.record("golden_cross", "000660", "reject", REJECT_NO_SMA_200)
    c.record("golden_cross", "035720", "reject", REJECT_NO_DAILY_WATCHLIST)
    c.record("golden_cross", "051910", "reject", REJECT_NO_MARKET_DATA)
    entry = json.loads(c.to_payload(now=_NOW)["golden_cross"])
    assert set(entry["reason_counts"]) == {
        REJECT_COLD,
        REJECT_NO_SMA_200,
        REJECT_NO_DAILY_WATCHLIST,
        REJECT_NO_MARKET_DATA,
    }


def test_collector_empty_payload_when_nothing_recorded():
    c = SignalEvalCollector()
    assert c.to_payload(now=_NOW) == {}


def test_collector_multiple_strategies_isolated():
    c = SignalEvalCollector()
    c.record("momentum_breakout", "005930", "signal", "long")
    c.record("pattern_pullback", "005930", "reject", REJECT_NO_SMA_200)
    payload = c.to_payload(now=_NOW)
    assert json.loads(payload["momentum_breakout"])["outcome"] == "signal"
    assert json.loads(payload["pattern_pullback"])["outcome"] == "reject"


@pytest.mark.parametrize("naive", [True, False])
def test_collector_timestamp_is_kst(naive):
    """now is normalized to KST regardless of incoming tz (UTC or naive)."""
    c = SignalEvalCollector()
    c.record("s", "005930", "signal", "long")
    # naive datetimes are assumed KST (container TZ=Asia/Seoul);
    # _NOW is UTC 01:42 -> KST 10:42.
    now = datetime(2026, 6, 24, 10, 42) if naive else _NOW
    entry = json.loads(c.to_payload(now=now)["s"])
    assert entry["ts_kst"].startswith("2026-06-24T10:42")
