"""Momentum Breakout Entry Strategy Tests."""

import pytest
from datetime import datetime, timedelta, timezone

from shared.strategy.base import EntryContext
from shared.strategy.entry.momentum_breakout import MomentumBreakoutConfig, MomentumBreakoutEntry

KST = timezone(timedelta(hours=9))


@pytest.fixture
def config():
    return MomentumBreakoutConfig(
        daily_high_period=20,
        breakout_buffer_pct=0.1,
        rvol_threshold=1.5,
        volume_threshold=1.0,
        accumulation_score_min=60,
        min_atr_cost_ratio=2.0,
        round_trip_cost=0.005,
        skip_market_open_minutes=30,
        skip_market_close_minutes=15,
        signal_cooldown_seconds=600,
        confidence_base=0.65,
    )


@pytest.fixture
def entry(config):
    return MomentumBreakoutEntry(config)


def _make_context(
    code="005930",
    close=50000.0,
    high=None,
    high_5=49900.0,
    rvol=2.0,
    volume=150000.0,
    volume_ma=100000.0,
    atr=600.0,  # atr/close = 600/50000 = 0.012 > 0.01 (min_edge), safely passes
    hour=10,
    minute=30,
    watchlist_codes=("005930",),
    accumulation_candidates=None,
) -> EntryContext:
    """Helper: build EntryContext with sensible defaults."""
    now = datetime(2026, 2, 26, hour, minute, tzinfo=KST)
    # Build daily_watchlist
    watchlist = {"strategies": {"momentum_breakout": list(watchlist_codes)}}
    metadata = {"daily_watchlist": watchlist}
    if accumulation_candidates is not None:
        metadata["accumulation_candidates"] = accumulation_candidates
    if high is None:
        high = close

    return EntryContext(
        market_data={
            "code": code,
            "name": "삼성전자",
            "close": close,
            "high": high,
            "high_5": high_5,
            "rvol": rvol,
            "volume": volume,
            "volume_ma": volume_ma,
            "atr": atr,
        },
        indicators={},
        timestamp=now,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Core signal generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generates_signal_on_breakout(entry):
    """Generates LONG signal when all conditions pass."""
    ctx = _make_context(
        close=50100.0,   # > high_5 * 1.001 = 49950.0
        high_5=49900.0,
        rvol=2.0,
        volume=150000.0,
        volume_ma=100000.0,
        atr=600.0,  # atr/close = 600/50100 ≈ 0.012 >= min_edge 0.01
    )
    signal = await entry.generate(ctx)
    assert signal is not None
    assert signal.code == "005930"
    assert signal.strategy == "momentum_breakout"
    assert signal.metadata["signal_direction"] == "long"
    assert signal.metadata["stop_loss"] == pytest.approx(50100.0 - 600.0 * 1.5, rel=1e-4)
    assert 0.0 < signal.confidence <= 1.0


@pytest.mark.asyncio
async def test_rejects_not_in_watchlist(entry):
    """Returns None when code is not in daily_watchlist."""
    ctx = _make_context(
        code="000660",  # not in watchlist
        watchlist_codes=("005930",),  # watchlist has 005930 only
        close=50100.0,
        high_5=49900.0,
    )
    signal = await entry.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_rejects_no_breakout(entry):
    """Returns None when close <= breakout threshold."""
    ctx = _make_context(
        close=49900.0,   # exactly at high_5, no breakout
        high=49900.0,
        high_5=49900.0,
    )
    signal = await entry.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_rejects_low_rvol(entry):
    """Returns None when RVOL is below threshold."""
    ctx = _make_context(
        close=50100.0,
        high_5=49900.0,
        rvol=1.2,  # below threshold 1.5
    )
    signal = await entry.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_rejects_low_volume(entry):
    """Returns None when volume < volume_ma * volume_threshold."""
    ctx = _make_context(
        close=50100.0,
        high_5=49900.0,
        rvol=2.0,
        volume=80000.0,   # below 100000 * 1.0
        volume_ma=100000.0,
    )
    signal = await entry.generate(ctx)
    assert signal is None


# ---------------------------------------------------------------------------
# Minimum edge filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_minimum_edge_filter(entry):
    """Returns None when ATR/close < round_trip_cost * min_atr_cost_ratio."""
    # atr/close = 50/50000 = 0.001 < 0.005 * 2.0 = 0.01
    ctx = _make_context(
        close=50000.0,
        high_5=49900.0,
        rvol=2.0,
        atr=50.0,  # tiny ATR → fails edge filter
    )
    signal = await entry.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_minimum_edge_filter_passes(entry):
    """Signal when ATR/close clearly above minimum edge boundary."""
    # min_edge = 0.005 * 2.0 = 0.01; atr/close = 600/50100 ≈ 0.012 >= 0.01
    ctx = _make_context(
        close=50100.0,
        high_5=49900.0,
        rvol=2.0,
        atr=600.0,
    )
    signal = await entry.generate(ctx)
    assert signal is not None


# ---------------------------------------------------------------------------
# Time filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_market_open(entry):
    """Returns None during first 30 minutes after market open."""
    ctx = _make_context(
        close=50100.0,
        high_5=49900.0,
        hour=9,
        minute=15,  # 9:15 < 9:30
    )
    signal = await entry.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_skip_market_close(entry):
    """Returns None in last 15 minutes before market close."""
    ctx = _make_context(
        close=50100.0,
        high_5=49900.0,
        hour=15,
        minute=5,  # 15:05 >= 15:00 (15:15 - 15min)
    )
    signal = await entry.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_signal_in_valid_time_window(entry):
    """Signal generated in valid time window (10:30)."""
    ctx = _make_context(
        close=50100.0,
        high_5=49900.0,
        hour=10,
        minute=30,
    )
    signal = await entry.generate(ctx)
    assert signal is not None


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cooldown(entry):
    """Second signal within 600s is rejected."""
    ctx1 = _make_context(close=50100.0, high_5=49900.0, hour=10, minute=0)
    sig1 = await entry.generate(ctx1)
    assert sig1 is not None

    # 300 seconds later — still within cooldown
    ctx2 = _make_context(close=50200.0, high_5=49900.0, hour=10, minute=5)
    sig2 = await entry.generate(ctx2)
    assert sig2 is None


@pytest.mark.asyncio
async def test_cooldown_expired(entry):
    """Second signal after cooldown expires is accepted."""
    ctx1 = _make_context(close=50100.0, high_5=49900.0, hour=10, minute=0)
    sig1 = await entry.generate(ctx1)
    assert sig1 is not None

    # 11 minutes later — cooldown (600s) expired
    ctx2 = _make_context(close=50200.0, high_5=49900.0, hour=10, minute=11)
    sig2 = await entry.generate(ctx2)
    assert sig2 is not None


# ---------------------------------------------------------------------------
# Accumulation score → confidence boost
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accumulation_score_boosts_confidence(entry):
    """Confidence is higher when accumulation score meets minimum."""
    ctx_no_accum = _make_context(close=50100.0, high_5=49900.0)
    sig_no_accum = await entry.generate(ctx_no_accum)

    # Reset cooldown
    entry._last_signal_time.pop("005930", None)

    ctx_with_accum = _make_context(
        close=50100.0,
        high_5=49900.0,
        accumulation_candidates={"005930": 75},  # >= 60
    )
    sig_with_accum = await entry.generate(ctx_with_accum)

    assert sig_no_accum is not None
    assert sig_with_accum is not None
    assert sig_with_accum.confidence > sig_no_accum.confidence


@pytest.mark.asyncio
async def test_low_accumulation_score_no_boost(entry):
    """Below-threshold accumulation score does not boost confidence."""
    ctx_no_accum = _make_context(close=50100.0, high_5=49900.0)
    sig_no_accum = await entry.generate(ctx_no_accum)

    entry._last_signal_time.pop("005930", None)

    ctx_low_accum = _make_context(
        close=50100.0,
        high_5=49900.0,
        accumulation_candidates={"005930": 40},  # < 60 → no boost
    )
    sig_low_accum = await entry.generate(ctx_low_accum)

    assert sig_no_accum is not None
    assert sig_low_accum is not None
    # Confidence should be equal (no boost applied)
    assert sig_low_accum.confidence == pytest.approx(sig_no_accum.confidence, rel=1e-4)


# ---------------------------------------------------------------------------
# Intrabar breakout path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_intrabar_breakout_with_reclaim_generates_signal():
    """Signal generated when high breaks out and close reclaims near high_5."""
    cfg = MomentumBreakoutConfig(
        breakout_buffer_pct=0.1,
        intrabar_breakout_enabled=True,
        intrabar_reclaim_pct=0.05,
        intrabar_min_rvol=1.8,
        rvol_threshold=1.5,
        volume_threshold=1.0,
        min_atr_cost_ratio=2.0,
        round_trip_cost=0.005,
        skip_market_open_minutes=30,
        skip_market_close_minutes=15,
        signal_cooldown_seconds=600,
    )
    entry = MomentumBreakoutEntry(cfg)
    # threshold=49949.9, close below threshold, high above threshold.
    # reclaim floor=49900*(1-0.0005)=49875.05; close=49920 passes.
    ctx = _make_context(
        close=49920.0,
        high=50020.0,
        high_5=49900.0,
        rvol=2.0,
    )
    signal = await entry.generate(ctx)
    assert signal is not None
    assert signal.metadata["breakout_type"] == "intrabar_reclaim"


@pytest.mark.asyncio
async def test_intrabar_breakout_rejects_without_reclaim():
    """No signal when intrabar breakout occurs but close fails reclaim floor."""
    cfg = MomentumBreakoutConfig(
        breakout_buffer_pct=0.1,
        intrabar_breakout_enabled=True,
        intrabar_reclaim_pct=0.05,
        intrabar_min_rvol=1.8,
        rvol_threshold=1.5,
        volume_threshold=1.0,
        min_atr_cost_ratio=2.0,
        round_trip_cost=0.005,
        skip_market_open_minutes=30,
        skip_market_close_minutes=15,
        signal_cooldown_seconds=600,
    )
    entry = MomentumBreakoutEntry(cfg)
    # reclaim floor=49875.05; close=49850 fails.
    ctx = _make_context(
        close=49850.0,
        high=50020.0,
        high_5=49900.0,
        rvol=2.0,
    )
    signal = await entry.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_intrabar_breakout_respects_intrabar_rvol_threshold():
    """Intrabar breakout requires intrabar_min_rvol when enabled."""
    cfg = MomentumBreakoutConfig(
        breakout_buffer_pct=0.1,
        intrabar_breakout_enabled=True,
        intrabar_reclaim_pct=0.05,
        intrabar_min_rvol=2.2,
        rvol_threshold=1.5,
        volume_threshold=1.0,
        min_atr_cost_ratio=2.0,
        round_trip_cost=0.005,
        skip_market_open_minutes=30,
        skip_market_close_minutes=15,
        signal_cooldown_seconds=600,
    )
    entry = MomentumBreakoutEntry(cfg)
    # rvol passes base (1.5) but fails intrabar_min_rvol (2.2).
    ctx = _make_context(
        close=49920.0,
        high=50020.0,
        high_5=49900.0,
        rvol=2.0,
    )
    signal = await entry.generate(ctx)
    assert signal is None


# ---------------------------------------------------------------------------
# Config defaults and metadata
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Config default values are correct."""
    cfg = MomentumBreakoutConfig()
    assert cfg.daily_high_period == 20
    assert cfg.breakout_buffer_pct == 0.1
    assert cfg.intrabar_breakout_enabled is False
    assert cfg.intrabar_reclaim_pct == 0.05
    assert cfg.intrabar_min_rvol == 1.8
    assert cfg.rvol_threshold == 1.5
    assert cfg.accumulation_score_min == 60
    assert cfg.volume_threshold == 1.0
    assert cfg.min_atr_cost_ratio == 2.0
    assert cfg.round_trip_cost == 0.005
    assert cfg.skip_market_open_minutes == 30
    assert cfg.skip_market_close_minutes == 15
    assert cfg.signal_cooldown_seconds == 600
    assert cfg.allow_short is False
    assert cfg.confidence_base == 0.65


def test_required_indicators(entry):
    """required_indicators returns expected list."""
    indicators = entry.required_indicators
    assert "close" in indicators
    assert "high_5" in indicators
    assert "rvol" in indicators
    assert "volume" in indicators
    assert "volume_ma" in indicators
    assert "atr" in indicators


def test_strategy_name(entry):
    """name property returns 'momentum_breakout'."""
    assert entry.name == "momentum_breakout"


def test_config_from_dict():
    """MomentumBreakoutConfig.from_dict works with params key."""
    raw = {
        "params": {
            "breakout_buffer_pct": 0.2,
            "rvol_threshold": 2.0,
            "unknown_field": "ignored",
        }
    }
    cfg = MomentumBreakoutConfig.from_dict(raw)
    assert cfg.breakout_buffer_pct == 0.2
    assert cfg.rvol_threshold == 2.0
    # unchanged defaults
    assert cfg.daily_high_period == 20


@pytest.mark.asyncio
async def test_bypasses_watchlist_in_dynamic_mode(entry):
    """In dynamic mode (empty daily_watchlist), watchlist gate is bypassed."""
    now = datetime(2026, 2, 26, 10, 30, tzinfo=KST)
    ctx = EntryContext(
        market_data={
            "code": "005930",
            "name": "삼성전자",
            "close": 50100.0,
            "high_5": 49900.0,
            "rvol": 2.0,
            "volume": 150000.0,
            "volume_ma": 100000.0,
            "atr": 600.0,
        },
        indicators={},
        timestamp=now,
        metadata={"daily_watchlist": {}},  # empty = dynamic mode
    )
    signal = await entry.generate(ctx)
    assert signal is not None
    assert signal.code == "005930"


# ---------------------------------------------------------------------------
# Trend mode config
# ---------------------------------------------------------------------------

def test_trend_mode_config_defaults():
    """Trend mode config fields have correct defaults."""
    cfg = MomentumBreakoutConfig()
    assert cfg.trend_mode_enabled is False
    assert cfg.trend_mode_regimes == ["BULL", "SIDEWAYS_UP"]
    assert cfg.trend_rvol_threshold == 1.0
    assert cfg.trend_breakout_buffer_pct == 0.0
    assert cfg.trend_signal_cooldown_seconds == 60
    assert cfg.trend_ema_pullback_enabled is True
    assert cfg.trend_ema_fast == 5
    assert cfg.trend_ema_mid == 20
    assert cfg.trend_ema_slow == 60
    assert cfg.trend_ema_touch_buffer_atr == 1.0
    assert cfg.trend_rsi_min == 40.0
    assert cfg.trend_exit_stop_atr_multiplier == 2.5
    assert cfg.trend_exit_trail_activation_atr == 1.5
    assert cfg.trend_exit_trail_atr_multiplier == 2.5
    assert cfg.trend_exit_max_hold_days == 15

def test_trend_mode_config_from_dict():
    """Trend mode fields load correctly from dict."""
    raw = {"params": {"trend_mode_enabled": True, "trend_rvol_threshold": 1.2, "trend_exit_max_hold_days": 20}}
    cfg = MomentumBreakoutConfig.from_dict(raw)
    assert cfg.trend_mode_enabled is True
    assert cfg.trend_rvol_threshold == 1.2
    assert cfg.trend_exit_max_hold_days == 20
    assert cfg.trend_ema_pullback_enabled is True
