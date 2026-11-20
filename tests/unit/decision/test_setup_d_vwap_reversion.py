"""Tests for SetupDVWAPReversion (Setup D — high-vol intraday VWAP reversion)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import MarketContext
from shared.decision.setups.vwap_reversion import SetupDConfig, SetupDVWAPReversion

KST = ZoneInfo("Asia/Seoul")


def _ctx(
    *,
    now_hhmm: tuple[int, int] = (11, 0),
    current_price: float,
    vwap: float,
    atr_14: float = 2.0,
    atr_90th_percentile: float = 2.0,
    last_15min_high: float | None = None,
    last_15min_low: float | None = None,
) -> MarketContext:
    """Build a MarketContext for Setup D tests."""
    h, m = now_hhmm
    if last_15min_high is None:
        last_15min_high = current_price
    if last_15min_low is None:
        last_15min_low = current_price
    return MarketContext(
        now=datetime(2026, 3, 10, h, m, tzinfo=KST),
        symbol="101S6000",
        current_price=current_price,
        prev_close=vwap,
        today_open=vwap,
        vwap=vwap,
        atr_14=atr_14,
        atr_90th_percentile=atr_90th_percentile,
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        current_spread_ticks=1.0,
        macro_overnight=None,
        scheduled_events=[],
    )


def _setup() -> SetupDVWAPReversion:
    return SetupDVWAPReversion(config=SetupDConfig())


def _warm(
    setup: SetupDVWAPReversion, atr: float, n: int, *, close: float = 100.0
) -> None:
    """Feed ``n`` calm bars at a fixed ATR to populate BOTH the causal vol window"""
    for _i in range(n):
        setup.check(_ctx(current_price=close, vwap=100.0, atr_14=atr))


def _warm_ramp(
    setup: SetupDVWAPReversion, atr: float, start: float, stop: float, n: int
) -> None:
    """Feed ``n`` bars whose close ramps linearly start→stop, seeding the close"""
    step = (stop - start) / max(n - 1, 1)
    for i in range(n):
        px = start + step * i
        setup.check(_ctx(current_price=px, vwap=100.0, atr_14=atr))


def test_up_spike_fades_short():
    """price 2.0 ATR above VWAP on a high-vol bar → SHORT."""
    setup = _setup()
    ctx = _ctx(
        current_price=104.0,
        vwap=100.0,
        atr_14=2.0,
        atr_90th_percentile=2.0,
        last_15min_high=103.9,
    )
    sig = setup.check(ctx)
    assert sig is not None
    assert sig.direction == "short"
    assert sig.setup_type == "D_vwap_reversion"
    assert sig.symbol == "101S6000"
    assert sig.entry_price == pytest.approx(104.0)
    assert sig.stop_loss == pytest.approx(104.0 + 1.5 * 2.0)
    assert sig.take_profit == pytest.approx(100.0)


def test_down_spike_fades_long_mirror():
    """The exact mirror of the up-spike fades LONG with mirrored bracket."""
    setup = _setup()
    ctx = _ctx(
        current_price=96.0,
        vwap=100.0,
        atr_14=2.0,
        atr_90th_percentile=2.0,
        last_15min_low=96.1,
    )
    sig = setup.check(ctx)
    assert sig is not None
    assert sig.direction == "long"
    assert sig.entry_price == pytest.approx(96.0)
    assert sig.stop_loss == pytest.approx(96.0 - 1.5 * 2.0)
    assert sig.take_profit == pytest.approx(100.0)


def test_long_short_bracket_is_symmetric():
    """Long and short of equal extension produce mirror-symmetric R:R."""
    setup = _setup()
    short = setup.check(_ctx(current_price=104.0, vwap=100.0, last_15min_high=103.9))
    long = setup.check(_ctx(current_price=96.0, vwap=100.0, last_15min_low=96.1))
    assert short is not None and long is not None
    short_risk = abs(short.entry_price - short.stop_loss)
    long_risk = abs(long.entry_price - long.stop_loss)
    short_reward = abs(short.take_profit - short.entry_price)
    long_reward = abs(long.take_profit - long.entry_price)
    assert short_risk == pytest.approx(long_risk)
    assert short_reward == pytest.approx(long_reward)


def test_quiet_bar_below_vol_gate_returns_none():
    """After warmup, an extreme on a LOW-vol bar (ATR below the causal"""
    setup = SetupDVWAPReversion(config=SetupDConfig(vol_warmup_bars=30))
    _warm(setup, atr=2.0, n=30)
    ctx = _ctx(current_price=101.8, vwap=100.0, atr_14=1.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("vol_below_gate")


def test_high_vol_bar_passes_gate():
    """After warmup, an extreme on a HIGH-vol bar (ATR at/above the causal"""
    setup = SetupDVWAPReversion(
        config=SetupDConfig(vol_warmup_bars=30, stall_buffer_atr_mult=10.0)
    )
    _warm(setup, atr=1.0, n=30)
    ctx = _ctx(current_price=104.0, vwap=100.0, atr_14=2.0)
    sig = setup.check(ctx)
    assert sig is not None
    assert sig.direction == "short"


def test_gate_permissive_during_warmup():
    """Before vol_warmup_bars observations, the gate does not block (the setup is"""
    setup = SetupDVWAPReversion(config=SetupDConfig(vol_warmup_bars=30))
    ctx = _ctx(current_price=104.0, vwap=100.0, atr_14=2.0, last_15min_high=103.9)
    sig = setup.check(ctx)
    assert sig is not None
    assert sig.direction == "short"


def test_vol_gate_disabled_when_ratio_zero():
    """min_atr_ratio=0 disables the high-vol gate (fires regardless of vol)."""
    setup = SetupDVWAPReversion(
        config=SetupDConfig(
            min_atr_ratio=0.0, vol_warmup_bars=30, stall_buffer_atr_mult=10.0
        )
    )
    _warm(setup, atr=5.0, n=30)
    ctx = _ctx(current_price=104.0, vwap=100.0, atr_14=2.0)
    sig = setup.check(ctx)
    assert sig is not None


def test_price_near_vwap_no_signal():
    """Small VWAP extension (not extreme) → no signal (the chop/quiet case)."""
    setup = _setup()
    ctx = _ctx(current_price=101.0, vwap=100.0, atr_14=2.0, atr_90th_percentile=2.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("not_extreme")


def test_still_trending_up_rejected():
    """Up-spike that blew clean THROUGH the self-computed recent high (still"""
    setup = _setup()
    _warm(setup, atr=2.0, n=10, close=100.0)
    ctx = _ctx(current_price=104.0, vwap=100.0, atr_14=2.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("still_trending_up")


def test_still_trending_down_rejected():
    """Mirror: down-spike still trending below the self-computed recent low → reject."""
    setup = _setup()
    _warm(setup, atr=2.0, n=10, close=100.0)
    ctx = _ctx(current_price=96.0, vwap=100.0, atr_14=2.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("still_trending_down")


def test_stalling_spike_passes_guard():
    """A spike that BUILT UP over recent bars (recent high near the price) is a"""
    setup = _setup()
    _warm_ramp(setup, atr=2.0, start=100.0, stop=103.5, n=10)
    sig = setup.check(_ctx(current_price=104.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.direction == "short"


def test_stall_guard_permissive_during_warmup():
    """Before range_warmup_bars prior closes exist, the stall guard is permissive"""
    setup = SetupDVWAPReversion(config=SetupDConfig(range_warmup_bars=5))
    sig = setup.check(_ctx(current_price=104.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.direction == "short"


def test_reversal_confirmation_waits_for_pullback_then_fires():
    """With reversal confirmation enabled, a fresh extension arms but does not"""
    setup = SetupDVWAPReversion(
        config=SetupDConfig(
            reversal_confirm_enabled=True,
            reversal_confirm_atr_mult=0.2,
            stall_buffer_atr_mult=10.0,
        )
    )
    _warm(setup, atr=2.0, n=10, close=100.0)

    first = setup.check(_ctx(current_price=104.5, vwap=100.0, atr_14=2.0))
    assert first is None
    assert setup.last_reject_reason is not None
    assert setup.last_reject_reason.startswith("awaiting_reversal_confirm")

    confirmed = setup.check(_ctx(current_price=103.8, vwap=100.0, atr_14=2.0))
    assert confirmed is not None
    assert confirmed.direction == "short"
    assert "reversal_confirmed" in confirmed.reason_tags


def test_signal_details_recorded_for_observability():
    setup = _setup()
    sig = setup.check(_ctx(current_price=104.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    details = setup.last_signal_details
    assert details["z"] == pytest.approx(2.0)
    assert details["target_rr"] == pytest.approx(sig.risk_reward_ratio())
    assert details["risk_points"] == pytest.approx(3.0)


def test_before_window_returns_none():
    setup = _setup()
    ctx = _ctx(now_hhmm=(8, 55), current_price=103.6, vwap=100.0, last_15min_high=103.5)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("before_window")


def test_after_cutoff_returns_none():
    setup = _setup()
    ctx = _ctx(
        now_hhmm=(14, 50), current_price=103.6, vwap=100.0, last_15min_high=103.5
    )
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("after_cutoff")


def test_target_floor_min_reward_risk():
    """When the VWAP distance is small, target is floored at min_reward_risk × risk."""
    setup = SetupDVWAPReversion(
        config=SetupDConfig(
            extreme_atr_mult=1.0, min_reward_risk=1.0, stop_atr_mult=1.5
        )
    )
    ctx = _ctx(
        current_price=102.1,
        vwap=100.0,
        atr_14=2.0,
        atr_90th_percentile=2.0,
        last_15min_high=102.0,
    )
    sig = setup.check(ctx)
    assert sig is not None
    assert sig.take_profit == pytest.approx(99.1)
    assert sig.risk_reward_ratio() == pytest.approx(1.0)


def test_last_reject_reason_cleared_on_fire():
    setup = _setup()
    assert setup.check(_ctx(current_price=101.0, vwap=100.0)) is None
    assert setup.last_reject_reason is not None
    fired = setup.check(_ctx(current_price=104.0, vwap=100.0, last_15min_high=103.9))
    assert fired is not None
    assert setup.last_reject_reason is None


def test_no_atr_rejected():
    setup = _setup()
    ctx = _ctx(current_price=103.6, vwap=100.0, atr_14=0.0, atr_90th_percentile=2.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason == "no_atr"


def test_confidence_in_valid_range():
    setup = _setup()
    sig = setup.check(_ctx(current_price=104.0, vwap=100.0, last_15min_high=103.9))
    assert sig is not None
    assert 0.5 <= sig.confidence <= 1.0


def test_confidence_increases_with_extension():
    setup = _setup()
    near = setup.check(_ctx(current_price=104.0, vwap=100.0, last_15min_high=103.9))
    far = setup.check(_ctx(current_price=105.5, vwap=100.0, last_15min_high=105.4))
    assert near is not None and far is not None
    assert far.confidence > near.confidence


def test_confidence_increases_with_vol_regime():
    """Higher vol_ratio (same z extension) → higher confidence."""
    cfg = SetupDConfig(vol_warmup_bars=30, stall_buffer_atr_mult=10.0)
    low = SetupDVWAPReversion(config=cfg)
    _warm(low, atr=1.0, n=30)
    sig_low = low.check(_ctx(current_price=103.0, vwap=100.0, atr_14=1.5))

    high = SetupDVWAPReversion(config=cfg)
    _warm(high, atr=1.0, n=30)
    sig_high = high.check(_ctx(current_price=104.0, vwap=100.0, atr_14=2.0))
    assert sig_low is not None and sig_high is not None
    assert sig_high.confidence > sig_low.confidence


def test_config_defaults():
    cfg = SetupDConfig()
    assert cfg.enabled is True
    assert cfg.valid_minutes_min == 15
    assert cfg.no_entry_after_minutes_since_open == 360
    assert cfg.min_atr_ratio == pytest.approx(0.9)
    assert cfg.vol_window_bars == 780
    assert cfg.vol_warmup_bars == 120
    assert cfg.vol_percentile == pytest.approx(90.0)
    assert cfg.extreme_atr_mult == pytest.approx(1.8)
    assert cfg.stall_buffer_atr_mult == pytest.approx(1.0)
    assert cfg.stop_atr_mult == pytest.approx(1.5)
    assert cfg.min_reward_risk == pytest.approx(1.0)
    assert cfg.signal_ttl_minutes == 10
    assert cfg.range_window_bars == 15
    assert cfg.range_warmup_bars == 5
    assert cfg.min_confidence == pytest.approx(0.0)
    assert cfg.reversal_confirm_enabled is False
    assert cfg.reversal_confirm_atr_mult == pytest.approx(0.2)
    assert cfg.reversal_confirm_requires_price_turn is True


def test_min_confidence_disabled_by_default():
    """Default min_confidence=0.0 never gates any signal."""
    setup = SetupDVWAPReversion(
        config=SetupDConfig(vol_warmup_bars=30, stall_buffer_atr_mult=10.0)
    )
    _warm(setup, atr=2.0, n=30)
    sig = setup.check(_ctx(current_price=103.7, vwap=100.0, atr_14=2.0))
    assert sig is not None, "default min_confidence=0.0 must not gate any signal"


def test_min_confidence_rejects_low_confidence_signal():
    """min_confidence=0.8 drops a barely-extreme signal (confidence ≈ 0.5)."""
    cfg = SetupDConfig(
        vol_warmup_bars=30, stall_buffer_atr_mult=10.0, min_confidence=0.8
    )
    setup = SetupDVWAPReversion(config=cfg)
    _warm(setup, atr=2.0, n=30)
    sig = setup.check(_ctx(current_price=103.7, vwap=100.0, atr_14=2.0))
    assert sig is None
    assert setup.last_reject_reason is not None
    assert "low_confidence" in setup.last_reject_reason


def test_min_confidence_passes_strong_signal():
    """min_confidence=0.6 passes a deeply-extreme high-vol signal."""
    cfg = SetupDConfig(
        vol_warmup_bars=30, stall_buffer_atr_mult=10.0, min_confidence=0.6
    )
    setup = SetupDVWAPReversion(config=cfg)
    _warm(setup, atr=1.0, n=30)
    sig = setup.check(_ctx(current_price=104.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.confidence >= 0.6
