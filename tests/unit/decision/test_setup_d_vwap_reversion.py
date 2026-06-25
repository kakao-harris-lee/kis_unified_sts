"""Tests for SetupDVWAPReversion (Setup D — high-vol intraday VWAP reversion).

Coverage
--------
- Symmetry: an up-spike fades SHORT and the mirror down-spike fades LONG with
  mirrored entry/stop/target.
- High-vol regime gate: a quiet (low-ATR) bar is rejected; the same extension on
  a high-vol bar fires.
- Chop / dead-day behavior: price near VWAP (small extension) → no signal.
- Trend-day guard: a spike that has blown clean through the 15-min extreme
  (still trending) is rejected.
- Session window: before valid_minutes_min and after the cutoff → rejected.
- ATR-scaled risk bracket arithmetic.
- last_reject_reason observability (set on reject, cleared on a fired signal).
- Confidence in [0.5, 1.0] and monotone in extension and vol regime.

All tests are hermetic: SetupDConfig() defaults only, no YAML / Redis / network.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import MarketContext
from shared.decision.setups.vwap_reversion import SetupDConfig, SetupDVWAPReversion

KST = ZoneInfo("Asia/Seoul")


def _ctx(
    *,
    now_hhmm: tuple[int, int] = (11, 0),  # 120 min after open → in window
    current_price: float,
    vwap: float,
    atr_14: float = 2.0,
    atr_90th_percentile: float = 2.0,
    last_15min_high: float | None = None,
    last_15min_low: float | None = None,
) -> MarketContext:
    """Build a MarketContext for Setup D tests.

    By default the 15-min extreme is placed so the stall guard passes (the spike
    price sits within the buffer of the relevant 15-min edge).
    """
    h, m = now_hhmm
    if last_15min_high is None:
        last_15min_high = current_price + 0.1
    if last_15min_low is None:
        last_15min_low = current_price - 0.1
    return MarketContext(
        now=datetime(2026, 3, 10, h, m, tzinfo=KST),
        symbol="101S6000",
        current_price=current_price,
        prev_close=vwap,  # unused by Setup D
        today_open=vwap,  # unused by Setup D
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


# ---------------------------------------------------------------------------
# Symmetry
# ---------------------------------------------------------------------------


def test_up_spike_fades_short():
    """price 2.0 ATR above VWAP on a high-vol bar → SHORT."""
    setup = _setup()
    # vwap=100, atr=2 → z=(104-100)/2=2.0 >= extreme trigger 1.8 → fires
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
    # entry = current_price; stop = entry + 1.5*atr; target toward vwap
    assert sig.entry_price == pytest.approx(104.0)
    assert sig.stop_loss == pytest.approx(104.0 + 1.5 * 2.0)  # 107.0
    # vwap_distance = 4.0 > min_rr*risk(=3.0) → target = entry - 4.0 = 100.0
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
    assert sig.stop_loss == pytest.approx(96.0 - 1.5 * 2.0)  # 93.0
    # vwap_distance = 4.0 > 3.0 → target = entry + 4.0 = 100.0
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


# ---------------------------------------------------------------------------
# High-vol regime gate
# ---------------------------------------------------------------------------


def test_quiet_bar_below_vol_gate_returns_none():
    """Same extension but ATR below the high-vol gate → rejected."""
    setup = _setup()
    # atr_14=1.0, atr_90th=2.0 → vol_ratio=0.5 < min_atr_ratio(0.7) → reject
    ctx = _ctx(current_price=103.6, vwap=100.0, atr_14=1.0, atr_90th_percentile=2.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("vol_below_gate")


def test_high_vol_bar_passes_gate():
    """ATR at/above the gate fires (boundary at vol_ratio == min_atr_ratio)."""
    setup = _setup()
    # atr_14=1.4, atr_90th=2.0 → vol_ratio=0.7 == gate → passes.
    # extension trigger at z>=1.8 → price >= 100 + 1.8*1.4 = 102.52
    ctx = _ctx(
        current_price=102.6,
        vwap=100.0,
        atr_14=1.4,
        atr_90th_percentile=2.0,
        last_15min_high=102.5,
    )
    sig = setup.check(ctx)
    assert sig is not None
    assert sig.direction == "short"


def test_vol_gate_disabled_when_ratio_zero():
    """min_atr_ratio=0 disables the high-vol gate."""
    setup = SetupDVWAPReversion(config=SetupDConfig(min_atr_ratio=0.0))
    ctx = _ctx(
        current_price=103.6,
        vwap=100.0,
        atr_14=0.5,
        atr_90th_percentile=2.0,
        last_15min_high=103.5,
    )
    sig = setup.check(ctx)
    assert sig is not None  # vol gate off → fires on the extension alone


# ---------------------------------------------------------------------------
# Chop / dead-day behavior
# ---------------------------------------------------------------------------


def test_price_near_vwap_no_signal():
    """Small VWAP extension (not extreme) → no signal (the chop/quiet case)."""
    setup = _setup()
    # z = (101 - 100)/2 = 0.5 < 1.8
    ctx = _ctx(current_price=101.0, vwap=100.0, atr_14=2.0, atr_90th_percentile=2.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("not_extreme")


# ---------------------------------------------------------------------------
# Trend-day guard
# ---------------------------------------------------------------------------


def test_still_trending_up_rejected():
    """Up-spike that blew clean THROUGH the 15-min high (still trending) → reject."""
    setup = _setup()
    # price extreme above vwap, but 15-min high far below price (>1 ATR away) →
    # the move is still extending, not stalling → skip.
    ctx = _ctx(
        current_price=104.0,
        vwap=100.0,
        atr_14=2.0,
        atr_90th_percentile=2.0,
        last_15min_high=101.0,
    )  # 104 - 101 = 3.0 > stall_buffer(2.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("still_trending_up")


def test_still_trending_down_rejected():
    """Mirror: down-spike still trending below the 15-min low → reject."""
    setup = _setup()
    ctx = _ctx(
        current_price=96.0,
        vwap=100.0,
        atr_14=2.0,
        atr_90th_percentile=2.0,
        last_15min_low=99.0,
    )  # 99 - 96 = 3.0 > 2.0
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("still_trending_down")


# ---------------------------------------------------------------------------
# Session window
# ---------------------------------------------------------------------------


def test_before_window_returns_none():
    setup = _setup()
    ctx = _ctx(
        now_hhmm=(9, 5), current_price=103.6, vwap=100.0, last_15min_high=103.5
    )  # 5 min after open < 15
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("before_window")


def test_after_cutoff_returns_none():
    setup = _setup()
    ctx = _ctx(
        now_hhmm=(15, 0), current_price=103.6, vwap=100.0, last_15min_high=103.5
    )  # 360 min > 345 cutoff
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("after_cutoff")


# ---------------------------------------------------------------------------
# Risk bracket arithmetic / target floor
# ---------------------------------------------------------------------------


def test_target_floor_min_reward_risk():
    """When the VWAP distance is small, target is floored at min_reward_risk × risk."""
    setup = SetupDVWAPReversion(
        config=SetupDConfig(
            extreme_atr_mult=1.0, min_reward_risk=1.0, stop_atr_mult=1.5
        )
    )
    # z = (102.1 - 100)/2 = 1.05 >= trigger 1.0; vwap_distance = 2.1; risk = 1.5*2 = 3.0
    # target_distance = max(2.1, 1.0*3.0) = 3.0 → target = 102.1 - 3.0 = 99.1
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


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


def test_last_reject_reason_cleared_on_fire():
    setup = _setup()
    # first a reject
    assert setup.check(_ctx(current_price=101.0, vwap=100.0)) is None
    assert setup.last_reject_reason is not None
    # then a fire clears it
    fired = setup.check(_ctx(current_price=104.0, vwap=100.0, last_15min_high=103.9))
    assert fired is not None
    assert setup.last_reject_reason is None


def test_no_atr_rejected():
    setup = _setup()
    ctx = _ctx(current_price=103.6, vwap=100.0, atr_14=0.0, atr_90th_percentile=2.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason == "no_atr"


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


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
    """Higher vol_ratio (same extension in ATR units) → higher confidence."""
    setup = _setup()
    # Both have z=2.0 (clear of the 1.8 boundary) but different vol regimes.
    # low vol regime: atr=1.5, atr_90th=2.0 → ratio 0.75; price=100+2.0*1.5=103.0
    low = setup.check(
        _ctx(
            current_price=103.0,
            vwap=100.0,
            atr_14=1.5,
            atr_90th_percentile=2.0,
            last_15min_high=102.9,
        )
    )
    # high vol regime: atr=2.0, atr_90th=2.0 → ratio 1.0; price=100+2.0*2.0=104.0
    high = setup.check(
        _ctx(
            current_price=104.0,
            vwap=100.0,
            atr_14=2.0,
            atr_90th_percentile=2.0,
            last_15min_high=103.9,
        )
    )
    assert low is not None and high is not None
    assert high.confidence > low.confidence


def test_config_defaults():
    cfg = SetupDConfig()
    assert cfg.enabled is True
    assert cfg.valid_minutes_min == 15
    assert cfg.no_entry_after_minutes_since_open == 345
    assert cfg.min_atr_ratio == pytest.approx(0.7)
    assert cfg.extreme_atr_mult == pytest.approx(1.8)
    assert cfg.stall_buffer_atr_mult == pytest.approx(1.0)
    assert cfg.stop_atr_mult == pytest.approx(1.5)
    assert cfg.min_reward_risk == pytest.approx(1.0)
    assert cfg.signal_ttl_minutes == 10
