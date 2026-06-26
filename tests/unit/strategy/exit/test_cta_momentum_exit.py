"""Unit tests for CTAMomentumExit (daily swing exit).

Hermetic: synthetic Position + snapshot. Verifies precedence
(catastrophic > trail > flip > time), long/short symmetry, and that there is NO
EOD liquidation.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.cta_momentum_exit import (
    CTAMomentumExit,
    CTAMomentumExitConfig,
    catastrophic_hit,
    chandelier_stop,
    trail_activated,
)


def _run(coro):
    return asyncio.run(coro)


def _position(
    side: PositionSide,
    entry: float,
    *,
    highest: float,
    lowest: float,
    entry_atr: float = 2.0,
    entry_time: datetime | None = None,
) -> Position:
    return Position(
        id="p1",
        code="krx_kospi200f_continuous",
        name="kospi200f",
        side=side,
        quantity=1,
        entry_price=entry,
        current_price=entry,
        highest_price=highest,
        lowest_price=lowest,
        entry_time=entry_time or datetime(2020, 1, 1, tzinfo=UTC),
        metadata={"entry_atr": entry_atr},
    )


def _config(**kw) -> CTAMomentumExitConfig:
    base = {
        "trail_atr_mult": 4.0,
        "trail_activate_atr_mult": 1.0,
        "catastrophic_atr_mult": 5.0,
        "use_momentum_flip": False,  # off unless a test supplies a series
        "max_holding_days": 60,
    }
    base.update(kw)
    return CTAMomentumExitConfig(**base)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_chandelier_stop_symmetry():
    assert chandelier_stop(PositionSide.LONG, 320.0, 2.0, 4.0) == pytest.approx(312.0)
    assert chandelier_stop(PositionSide.SHORT, 280.0, 2.0, 4.0) == pytest.approx(288.0)


def test_trail_activated_threshold():
    # Long: needs (extreme-entry) >= activate*atr.
    assert trail_activated(PositionSide.LONG, 300.0, 302.0, 2.0, 1.0)  # +2 >= 2
    assert not trail_activated(PositionSide.LONG, 300.0, 301.0, 2.0, 1.0)  # +1 < 2
    # Short: needs (entry-extreme) >= activate*atr.
    assert trail_activated(PositionSide.SHORT, 300.0, 298.0, 2.0, 1.0)
    assert not trail_activated(PositionSide.SHORT, 300.0, 299.0, 2.0, 1.0)


def test_catastrophic_hit_symmetry():
    assert catastrophic_hit(PositionSide.LONG, 300.0, 289.0, 2.0, 5.0)  # -11 <= -10
    assert not catastrophic_hit(PositionSide.LONG, 300.0, 291.0, 2.0, 5.0)
    assert catastrophic_hit(PositionSide.SHORT, 300.0, 311.0, 2.0, 5.0)
    assert not catastrophic_hit(PositionSide.SHORT, 300.0, 309.0, 2.0, 5.0)


# ---------------------------------------------------------------------------
# should_exit precedence
# ---------------------------------------------------------------------------


def test_catastrophic_fires_first_long():
    ex = CTAMomentumExit(_config())
    pos = _position(
        PositionSide.LONG, 300.0, highest=300.0, lowest=300.0, entry_atr=2.0
    )
    # price 289 → loss 11 >= 5*2=10 → catastrophic
    ctx = ExitContext(
        position=pos,
        market_data={"price": 289.0},
        timestamp=datetime(2020, 2, 1, tzinfo=UTC),
    )
    fired, sig = _run(ex.should_exit(ctx))
    assert fired and sig.reason == ExitReason.STOP_LOSS and sig.priority == 1


def test_trail_fires_after_activation_long():
    ex = CTAMomentumExit(_config(trail_atr_mult=4.0, trail_activate_atr_mult=1.0))
    # extreme 320 (activated: +20 >= 2), stop = 320 - 4*2 = 312; price 310 <= 312 → trail
    pos = _position(
        PositionSide.LONG, 300.0, highest=320.0, lowest=300.0, entry_atr=2.0
    )
    ctx = ExitContext(
        position=pos,
        market_data={"price": 310.0},
        timestamp=datetime(2020, 2, 1, tzinfo=UTC),
    )
    fired, sig = _run(ex.should_exit(ctx))
    assert fired and sig.reason == ExitReason.TRAILING_STOP and sig.priority == 2


def test_trail_does_not_fire_before_activation():
    ex = CTAMomentumExit(_config(trail_activate_atr_mult=5.0, max_holding_days=999))
    # extreme only +2 over entry; activation needs +5*2=10 → not activated, no trail
    pos = _position(
        PositionSide.LONG, 300.0, highest=302.0, lowest=300.0, entry_atr=2.0
    )
    ctx = ExitContext(
        position=pos,
        market_data={"price": 295.0},
        timestamp=datetime(2020, 1, 2, tzinfo=UTC),
    )
    fired, _ = _run(ex.should_exit(ctx))
    assert not fired


def test_trail_fires_short_symmetric():
    ex = CTAMomentumExit(_config(trail_atr_mult=4.0, trail_activate_atr_mult=1.0))
    # short extreme 280 (activated: 300-280=20>=2); stop = 280 + 8 = 288; price 290 >= 288 → trail
    pos = _position(
        PositionSide.SHORT, 300.0, highest=300.0, lowest=280.0, entry_atr=2.0
    )
    ctx = ExitContext(
        position=pos,
        market_data={"price": 290.0},
        timestamp=datetime(2020, 2, 1, tzinfo=UTC),
    )
    fired, sig = _run(ex.should_exit(ctx))
    assert fired and sig.reason == ExitReason.TRAILING_STOP


def test_time_cap_fires():
    ex = CTAMomentumExit(_config(max_holding_days=30, trail_activate_atr_mult=99.0))
    pos = _position(
        PositionSide.LONG,
        300.0,
        highest=301.0,
        lowest=300.0,
        entry_atr=2.0,
        entry_time=datetime(2020, 1, 1, tzinfo=UTC),
    )
    # 40 calendar days later, no trail/catastrophe → time cut
    ctx = ExitContext(
        position=pos,
        market_data={"price": 300.5},
        timestamp=datetime(2020, 2, 10, tzinfo=UTC),
    )
    fired, sig = _run(ex.should_exit(ctx))
    assert fired and sig.reason == ExitReason.TIME_CUT and sig.priority == 4


def test_no_exit_when_quiet():
    ex = CTAMomentumExit(_config(max_holding_days=999, trail_activate_atr_mult=99.0))
    pos = _position(
        PositionSide.LONG, 300.0, highest=301.0, lowest=300.0, entry_atr=2.0
    )
    ctx = ExitContext(
        position=pos,
        market_data={"price": 300.5},
        timestamp=datetime(2020, 1, 3, tzinfo=UTC),
    )
    fired, sig = _run(ex.should_exit(ctx))
    assert not fired and sig is None


def test_no_eod_liquidation():
    # Swing exit must NOT flatten purely because of time-of-day. A quiet position
    # late in the day stays open (only the day-count time cap or ATR/flip fire).
    ex = CTAMomentumExit(_config(max_holding_days=999, trail_activate_atr_mult=99.0))
    pos = _position(
        PositionSide.LONG, 300.0, highest=301.0, lowest=300.0, entry_atr=2.0
    )
    ctx = ExitContext(
        position=pos,
        market_data={"price": 300.2},
        timestamp=datetime(2020, 1, 1, 15, 30, tzinfo=UTC),
    )
    fired, _ = _run(ex.should_exit(ctx))
    assert not fired


# ---------------------------------------------------------------------------
# Momentum-flip
# ---------------------------------------------------------------------------


def test_momentum_flip_exits_long_when_trend_reverses():
    from datetime import date as _date

    cfg = _config(
        use_momentum_flip=True,
        momentum_lookback=20,
        max_holding_days=999,
        trail_activate_atr_mult=99.0,
    )
    ex = CTAMomentumExit(cfg)
    pos = _position(
        PositionSide.LONG, 300.0, highest=305.0, lowest=300.0, entry_atr=2.0
    )
    # Downward close series → roll-aware momentum negative → flip vs LONG.
    n = 40
    closes = [600.0 - i * 2.0 for i in range(n)]
    dates = [_date(2021, 1, 1) + timedelta(days=i) for i in range(n)]
    dates = [d for d in dates if d.month not in (3, 6, 9, 12)]
    closes = closes[: len(dates)]
    snapshot = {"price": 295.0, "daily_closes": closes, "daily_dates": dates}
    ctx = ExitContext(
        position=pos, market_data=snapshot, timestamp=datetime(2021, 2, 15, tzinfo=UTC)
    )
    fired, sig = _run(ex.should_exit(ctx))
    assert fired and sig.reason == ExitReason.STRATEGY_EXIT


def test_momentum_flip_silent_without_series():
    cfg = _config(
        use_momentum_flip=True,
        momentum_lookback=20,
        max_holding_days=999,
        trail_activate_atr_mult=99.0,
    )
    ex = CTAMomentumExit(cfg)
    pos = _position(
        PositionSide.LONG, 300.0, highest=301.0, lowest=300.0, entry_atr=2.0
    )
    ctx = ExitContext(
        position=pos,
        market_data={"price": 300.5},
        timestamp=datetime(2020, 1, 3, tzinfo=UTC),
    )
    fired, _ = _run(ex.should_exit(ctx))
    assert not fired  # no series → no flip, no spurious exit


# ---------------------------------------------------------------------------
# scan_positions + disabled guard
# ---------------------------------------------------------------------------


def test_scan_positions_uses_per_symbol_snapshot():
    ex = CTAMomentumExit(_config())
    pos = _position(
        PositionSide.LONG, 300.0, highest=300.0, lowest=300.0, entry_atr=2.0
    )
    market_data = {pos.code: {"price": 289.0}}  # catastrophic
    signals = _run(ex.scan_positions([pos], market_data))
    assert len(signals) == 1 and signals[0].reason == ExitReason.STOP_LOSS


def test_disabled_exit_never_fires():
    ex = CTAMomentumExit(_config(enabled=False))
    pos = _position(
        PositionSide.LONG, 300.0, highest=300.0, lowest=300.0, entry_atr=2.0
    )
    ctx = ExitContext(
        position=pos,
        market_data={"price": 200.0},
        timestamp=datetime(2020, 2, 1, tzinfo=UTC),
    )
    fired, sig = _run(ex.should_exit(ctx))
    assert not fired and sig is None


def test_config_validation_rejects_bad_values():
    with pytest.raises(ValueError):
        CTAMomentumExitConfig(trail_atr_mult=0).validate()
    with pytest.raises(ValueError):
        CTAMomentumExitConfig(max_holding_days=0).validate()
