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

    ``last_15min_high/low`` are accepted for back-compat but are IGNORED by the
    setup (it self-computes the recent range from prior closes — see
    ``_self_range``). The MarketContext requires them, so they default to
    ``current_price`` (the same value the live orchestrator path would default
    to). The stall guard is exercised by warming the close window, not by these
    fields.
    """
    h, m = now_hhmm
    if last_15min_high is None:
        last_15min_high = current_price
    if last_15min_low is None:
        last_15min_low = current_price
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


def _warm(
    setup: SetupDVWAPReversion, atr: float, n: int, *, close: float = 100.0
) -> None:
    """Feed ``n`` calm bars at a fixed ATR to populate BOTH the causal vol window
    and the causal close (recent-range) window.

    Each bar sits at ``close`` (default = VWAP, z≈0) so it does not fire — it only
    seeds the windows. After warming, the recent range is ~``close``; a fire-test
    bar whose price is within ``stall_buffer_atr_mult × atr`` of ``close`` passes
    the stall guard, and a runaway far beyond it is rejected.
    """
    for _i in range(n):
        setup.check(_ctx(current_price=close, vwap=100.0, atr_14=atr))


def _warm_ramp(
    setup: SetupDVWAPReversion, atr: float, start: float, stop: float, n: int
) -> None:
    """Feed ``n`` bars whose close ramps linearly start→stop, seeding the close
    window so the recent high tracks just below a building spike (the realistic
    'spike built up over ~15 bars, now stalling near its high' shape)."""
    step = (stop - start) / max(n - 1, 1)
    for i in range(n):
        px = start + step * i
        setup.check(_ctx(current_price=px, vwap=100.0, atr_14=atr))


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
    """After warmup, an extreme on a LOW-vol bar (ATR below the causal
    reference) is gated out."""
    setup = SetupDVWAPReversion(config=SetupDConfig(vol_warmup_bars=30))
    # Seed the causal window with high ATRs (reference ≈ 2.0), then present an
    # extreme on a low-ATR bar: vol_ratio = 1.0/2.0 = 0.5 < min_atr_ratio(0.9).
    _warm(setup, atr=2.0, n=30)
    ctx = _ctx(current_price=101.8, vwap=100.0, atr_14=1.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("vol_below_gate")


def test_high_vol_bar_passes_gate():
    """After warmup, an extreme on a HIGH-vol bar (ATR at/above the causal
    reference) fires."""
    # stall_buffer high → isolate the VOL gate (the stall guard is tested
    # separately; the flat warm closes would otherwise trip it here).
    setup = SetupDVWAPReversion(
        config=SetupDConfig(vol_warmup_bars=30, stall_buffer_atr_mult=10.0)
    )
    # Seed with low ATRs (reference ≈ 1.0), then an extreme on a high-ATR bar:
    # vol_ratio = 2.0/1.0 = 2.0 >= 0.9. z = (104-100)/2 = 2.0 >= 1.8.
    _warm(setup, atr=1.0, n=30)
    ctx = _ctx(current_price=104.0, vwap=100.0, atr_14=2.0)
    sig = setup.check(ctx)
    assert sig is not None
    assert sig.direction == "short"


def test_gate_permissive_during_warmup():
    """Before vol_warmup_bars observations, the gate does not block (the setup is
    not silently dead) — an extreme fires even though the reference is unknown."""
    setup = SetupDVWAPReversion(config=SetupDConfig(vol_warmup_bars=30))
    # First call ever (window empty < warmup) → permissive; extreme fires.
    ctx = _ctx(current_price=104.0, vwap=100.0, atr_14=2.0, last_15min_high=103.9)
    sig = setup.check(ctx)
    assert sig is not None
    assert sig.direction == "short"


def test_vol_gate_disabled_when_ratio_zero():
    """min_atr_ratio=0 disables the high-vol gate (fires regardless of vol)."""
    # stall_buffer high → isolate the vol gate from the stall guard.
    setup = SetupDVWAPReversion(
        config=SetupDConfig(
            min_atr_ratio=0.0, vol_warmup_bars=30, stall_buffer_atr_mult=10.0
        )
    )
    _warm(setup, atr=5.0, n=30)  # high reference, but gate disabled
    ctx = _ctx(current_price=104.0, vwap=100.0, atr_14=2.0)
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
    """Up-spike that blew clean THROUGH the self-computed recent high (still
    trending) → reject. The recent range is self-computed from prior closes."""
    setup = _setup()
    # Seed flat closes at 100 → recent high ≈ 100. Then a bar at 104 (z=2.0,
    # atr=2.0): 104 - 100 = 4.0 > stall_buffer(1.0×2.0=2.0) → still trending.
    _warm(setup, atr=2.0, n=10, close=100.0)
    ctx = _ctx(current_price=104.0, vwap=100.0, atr_14=2.0)
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("still_trending_up")


def test_still_trending_down_rejected():
    """Mirror: down-spike still trending below the self-computed recent low → reject."""
    setup = _setup()
    _warm(setup, atr=2.0, n=10, close=100.0)  # recent low ≈ 100
    ctx = _ctx(current_price=96.0, vwap=100.0, atr_14=2.0)  # 100 - 96 = 4.0 > 2.0
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("still_trending_down")


def test_stalling_spike_passes_guard():
    """A spike that BUILT UP over recent bars (recent high near the price) is a
    stalling spike → passes the guard and fires."""
    setup = _setup()
    # Ramp closes 100 → 103.5 (recent high ≈ 103.5), then a bar at 104 (z=2.0):
    # 104 - 103.5 = 0.5 < stall_buffer(2.0) → not still trending → fires short.
    _warm_ramp(setup, atr=2.0, start=100.0, stop=103.5, n=10)
    sig = setup.check(_ctx(current_price=104.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.direction == "short"


def test_stall_guard_permissive_during_warmup():
    """Before range_warmup_bars prior closes exist, the stall guard is permissive
    (no meaningful recent range yet) — a fresh setup fires on the first extreme."""
    setup = SetupDVWAPReversion(config=SetupDConfig(range_warmup_bars=5))
    # First call ever (close window empty < warmup) → guard permissive.
    sig = setup.check(_ctx(current_price=104.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.direction == "short"


# ---------------------------------------------------------------------------
# Session window
# ---------------------------------------------------------------------------


def test_before_window_returns_none():
    setup = _setup()
    ctx = _ctx(
        now_hhmm=(8, 55), current_price=103.6, vwap=100.0, last_15min_high=103.5
    )  # 10 min after 08:45 open < valid_minutes_min=15
    assert setup.check(ctx) is None
    assert setup.last_reject_reason.startswith("before_window")


def test_after_cutoff_returns_none():
    setup = _setup()
    ctx = _ctx(
        now_hhmm=(14, 50), current_price=103.6, vwap=100.0, last_15min_high=103.5
    )  # 365 min since 08:45 open > no_entry_after=360 (14:45 KST)
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
    """Higher vol_ratio (same z extension) → higher confidence.

    Both fire with z=2.0 but at different ATRs relative to the same causal
    reference (seeded ≈ 1.0). The higher-ATR bar has the larger vol_ratio.
    """
    # stall_buffer high → isolate the vol-driven confidence from the stall guard.
    cfg = SetupDConfig(vol_warmup_bars=30, stall_buffer_atr_mult=10.0)
    low = SetupDVWAPReversion(config=cfg)
    _warm(low, atr=1.0, n=30)  # reference ≈ 1.0
    # atr=1.5 → vol_ratio 1.5; z=2.0 → price=100+2.0*1.5=103.0
    sig_low = low.check(_ctx(current_price=103.0, vwap=100.0, atr_14=1.5))

    high = SetupDVWAPReversion(config=cfg)
    _warm(high, atr=1.0, n=30)  # same reference ≈ 1.0
    # atr=2.0 → vol_ratio 2.0; z=2.0 → price=100+2.0*2.0=104.0
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


# ---------------------------------------------------------------------------
# min_confidence gate
# ---------------------------------------------------------------------------


def test_min_confidence_disabled_by_default():
    """Default min_confidence=0.0 never gates any signal."""
    setup = SetupDVWAPReversion(config=SetupDConfig(vol_warmup_bars=30, stall_buffer_atr_mult=10.0))
    _warm(setup, atr=2.0, n=30)
    # Edge-of-band signal: z barely > 1.8 → low confidence ~0.5
    sig = setup.check(_ctx(current_price=103.7, vwap=100.0, atr_14=2.0))
    assert sig is not None, "default min_confidence=0.0 must not gate any signal"


def test_min_confidence_rejects_low_confidence_signal():
    """min_confidence=0.8 drops a barely-extreme signal (confidence ≈ 0.5)."""
    cfg = SetupDConfig(vol_warmup_bars=30, stall_buffer_atr_mult=10.0, min_confidence=0.8)
    setup = SetupDVWAPReversion(config=cfg)
    _warm(setup, atr=2.0, n=30)
    # z ≈ 1.85 → extension_bonus ≈ (1.85-1.8)*0.3=0.015
    # vol_ratio=2.0/2.0=1.0, min_atr_ratio=0.9 → vol_bonus=(1.0-0.9)*0.3=0.03
    # confidence ≈ 0.5+0.015+0.03=0.545 < 0.8 → reject
    sig = setup.check(_ctx(current_price=103.7, vwap=100.0, atr_14=2.0))
    assert sig is None
    assert setup.last_reject_reason is not None
    assert "low_confidence" in setup.last_reject_reason


def test_min_confidence_passes_strong_signal():
    """min_confidence=0.6 passes a deeply-extreme high-vol signal."""
    cfg = SetupDConfig(vol_warmup_bars=30, stall_buffer_atr_mult=10.0, min_confidence=0.6)
    setup = SetupDVWAPReversion(config=cfg)
    _warm(setup, atr=1.0, n=30)  # reference ≈ 1.0
    # atr=2.0 → vol_ratio=2.0 → vol_bonus=min((2.0-0.9)*0.3,0.2)=0.2
    # z=2.0 → extension_bonus=min((2.0-1.8)*0.3,0.3)=0.06
    # confidence = 0.5+0.06+0.2 = 0.76 > 0.6 → passes
    sig = setup.check(_ctx(current_price=104.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.confidence >= 0.6
