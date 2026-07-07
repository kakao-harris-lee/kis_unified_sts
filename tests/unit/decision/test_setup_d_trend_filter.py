"""Tests for the Setup D trend filter (causal session-VWAP-slope trend gate).

The trend filter blocks *shallow* counter-trend fades on a strongly trending
session (e.g. buying a 1.8-ATR dip while the session VWAP is grinding down) while
still allowing *climactic* counter-trend flushes (|z| >= against_trend_extreme_
atr_mult), which are the mean-reversion edge the setup is built to capture.

Motivated by 2026-07-07: Setup D entered long 13 straight times fading a -4.9%
one-way downtrend (11 stop-outs). See
docs/superpowers/specs/2026-07-07-setup-d-trend-filter-design.md.

All tests are hermetic: SetupDConfig() only, no YAML / Redis / network. The
trend metric is self-computed from ``ctx.vwap`` / ``ctx.atr_14`` and reset per
KST date, so these tests drive it purely by the vwap path and the bar date.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import MarketContext
from shared.decision.setups.vwap_reversion import SetupDConfig, SetupDVWAPReversion

KST = ZoneInfo("Asia/Seoul")


def _ctx(
    *,
    current_price: float,
    vwap: float,
    atr_14: float = 2.0,
    on_date: date = date(2026, 3, 10),
    now_hhmm: tuple[int, int] = (11, 0),  # 135 min after 08:45 open → in window
) -> MarketContext:
    """Build a MarketContext with an explicit vwap and bar date.

    ``last_15min_high/low`` are set to ``current_price`` (ignored by the setup —
    it self-computes ranges). The trend gate is exercised via the ``vwap`` path
    and ``on_date`` only.
    """
    h, m = now_hhmm
    return MarketContext(
        now=datetime(on_date.year, on_date.month, on_date.day, h, m, tzinfo=KST),
        symbol="101S6000",
        current_price=current_price,
        prev_close=vwap,
        today_open=vwap,
        vwap=vwap,
        atr_14=atr_14,
        atr_90th_percentile=atr_14,
        last_15min_high=current_price,
        last_15min_low=current_price,
        current_spread_ticks=1.0,
        macro_overnight=None,
        scheduled_events=[],
    )


def _cfg(**overrides: object) -> SetupDConfig:
    """Config that isolates the trend gate: vol gate off, stall guard off.

    Trend filter ON, warmup 10, window 30, block threshold 1.0 ATR, climax
    override 2.6 ATR (defaults) unless overridden.
    """
    base: dict[str, object] = {
        "trend_filter_enabled": True,
        "min_atr_ratio": 0.0,  # disable high-vol gate
        "stall_buffer_atr_mult": 100.0,  # disable stall guard
        "trend_warmup_bars": 10,
        "trend_window_bars": 30,
    }
    base.update(overrides)
    return SetupDConfig(**base)


def _warm_trend(
    setup: SetupDVWAPReversion,
    *,
    vwap_start: float,
    vwap_stop: float,
    n: int = 30,
    atr: float = 2.0,
    on_date: date = date(2026, 3, 10),
) -> None:
    """Feed ``n`` non-firing bars whose vwap ramps ``vwap_start`` → ``vwap_stop``.

    Each bar sits at price == vwap (z == 0 → 'not_extreme', never fires) so it
    only seeds the causal VWAP window that the trend metric reads. After this,
    ``trend_score`` at the next bar reflects the ramp direction.
    """
    step = (vwap_stop - vwap_start) / max(n - 1, 1)
    for i in range(n):
        v = vwap_start + step * i
        setup.check(_ctx(current_price=v, vwap=v, atr_14=atr, on_date=on_date))


# ---------------------------------------------------------------------------
# Core: shallow counter-trend blocked, climax allowed
# ---------------------------------------------------------------------------


def test_shallow_counter_trend_long_blocked_on_downtrend():
    """A 1.8-ATR dip-buy (shallow long) into a grinding-down VWAP is blocked."""
    setup = SetupDVWAPReversion(config=_cfg())
    _warm_trend(setup, vwap_start=130.0, vwap_stop=101.0)  # strong downtrend
    # vwap=100, atr=2, price=96.0 → z=(96.0-100)/2 = -2.0 (past 1.8 trigger, below 2.6 climax, long)
    sig = setup.check(_ctx(current_price=96.0, vwap=100.0, atr_14=2.0))
    assert sig is None
    assert setup.last_reject_reason is not None
    assert setup.last_reject_reason.startswith("against_trend")


def test_climax_counter_trend_long_fires_on_downtrend():
    """A 3.0-ATR climactic flush (|z| >= 2.6 override) still fires long."""
    setup = SetupDVWAPReversion(config=_cfg())
    _warm_trend(setup, vwap_start=130.0, vwap_stop=101.0)  # strong downtrend
    # price=94.0 → z=(94-100)/2 = -3.0 >= 2.6 climax override → fires
    sig = setup.check(_ctx(current_price=94.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.direction == "long"


def test_shallow_counter_trend_short_blocked_on_uptrend_mirror():
    """Mirror: a shallow short fade into a grinding-up VWAP is blocked."""
    setup = SetupDVWAPReversion(config=_cfg())
    _warm_trend(setup, vwap_start=70.0, vwap_stop=99.0)  # strong uptrend
    # price=104.0 → z=(104.0-100)/2 = +2.0 (short), counter-trend, shallow → block
    sig = setup.check(_ctx(current_price=104.0, vwap=100.0, atr_14=2.0))
    assert sig is None
    assert setup.last_reject_reason.startswith("against_trend")


def test_climax_counter_trend_short_fires_on_uptrend_mirror():
    """Mirror: a climactic short flush (|z| >= 2.6) still fires short."""
    setup = SetupDVWAPReversion(config=_cfg())
    _warm_trend(setup, vwap_start=70.0, vwap_stop=99.0)  # strong uptrend
    # price=106.0 → z=(106-100)/2 = +3.0 >= 2.6 → fires
    sig = setup.check(_ctx(current_price=106.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.direction == "short"


# ---------------------------------------------------------------------------
# With-trend fades are never blocked
# ---------------------------------------------------------------------------


def test_with_trend_short_not_blocked_on_downtrend():
    """A short (fading an up-poke) while the trend is DOWN is with-trend → fires."""
    setup = SetupDVWAPReversion(config=_cfg())
    _warm_trend(setup, vwap_start=130.0, vwap_stop=101.0)  # downtrend
    # short at z=+2.0 (price above vwap) is WITH the down-trend → not blocked
    sig = setup.check(_ctx(current_price=104.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.direction == "short"


# ---------------------------------------------------------------------------
# Opt-in / warmup / session-reset
# ---------------------------------------------------------------------------


def test_filter_disabled_lets_shallow_counter_trend_fire():
    """trend_filter_enabled=False ⇒ the shallow dip-buy fires (current behavior)."""
    setup = SetupDVWAPReversion(config=_cfg(trend_filter_enabled=False))
    _warm_trend(setup, vwap_start=130.0, vwap_stop=101.0)
    sig = setup.check(_ctx(current_price=96.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.direction == "long"


def test_trend_gate_permissive_during_warmup():
    """Fewer than trend_warmup_bars observations ⇒ gate permissive (fires)."""
    setup = SetupDVWAPReversion(config=_cfg(trend_warmup_bars=10))
    _warm_trend(setup, vwap_start=130.0, vwap_stop=118.0, n=5)  # only 5 < 10
    sig = setup.check(_ctx(current_price=96.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.direction == "long"


def test_session_reset_clears_trend_window_next_day():
    """A new KST date clears the VWAP window → the trend gate is permissive again."""
    setup = SetupDVWAPReversion(config=_cfg())
    _warm_trend(setup, vwap_start=130.0, vwap_stop=101.0, on_date=date(2026, 3, 10))
    # Same shallow long, but on the NEXT session → window cleared → permissive → fires
    sig = setup.check(
        _ctx(current_price=96.0, vwap=100.0, atr_14=2.0, on_date=date(2026, 3, 11))
    )
    assert sig is not None
    assert sig.direction == "long"


# ---------------------------------------------------------------------------
# Threshold behavior
# ---------------------------------------------------------------------------


def test_weak_trend_below_threshold_does_not_block():
    """A weak VWAP drift (< trend_block_threshold ATR) does not block a fade."""
    setup = SetupDVWAPReversion(config=_cfg(trend_block_threshold=1.0))
    # Drift only 0.5 ATR over the window: vwap 100.5 → 100.0 (|score|=0.25 < 1.0)
    _warm_trend(setup, vwap_start=100.5, vwap_stop=100.0)
    sig = setup.check(_ctx(current_price=96.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    assert sig.direction == "long"


# ---------------------------------------------------------------------------
# Observability + config defaults
# ---------------------------------------------------------------------------


def test_climax_override_recorded_in_signal_details():
    setup = SetupDVWAPReversion(config=_cfg())
    _warm_trend(setup, vwap_start=130.0, vwap_stop=101.0)
    sig = setup.check(_ctx(current_price=94.0, vwap=100.0, atr_14=2.0))
    assert sig is not None
    d = setup.last_signal_details
    assert d["against_trend_override"] is True
    assert d["trend_score"] < 0  # downtrend
    assert d["trend_filter_active"] is True


def test_trend_filter_config_defaults():
    cfg = SetupDConfig()
    assert cfg.trend_filter_enabled is False
    assert cfg.trend_window_bars == 30
    assert cfg.trend_warmup_bars == 10
    assert cfg.trend_block_threshold == pytest.approx(1.0)
    assert cfg.against_trend_extreme_atr_mult == pytest.approx(2.6)
