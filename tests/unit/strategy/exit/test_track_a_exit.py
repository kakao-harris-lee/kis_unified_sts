"""Unit tests for TrackAExit pure math helpers and generator."""
from __future__ import annotations
from datetime import UTC, datetime, timedelta, timezone
import pytest
from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.track_a_exit import (
    TrackAExit, TrackAExitConfig,
    catastrophic_stop_hit, crash_triggered, trail_activated, trail_stop_price,
    max_adverse_move_in_window,
)

def test_trail_stop_long():
    assert trail_stop_price(PositionSide.LONG, favorable_extreme=105.0, atr=2.0, trail_atr_mult=3.0) == pytest.approx(99.0)
def test_trail_stop_short():
    assert trail_stop_price(PositionSide.SHORT, favorable_extreme=95.0, atr=2.0, trail_atr_mult=3.0) == pytest.approx(101.0)
def test_trail_not_activated_at_entry_long():
    assert trail_activated(PositionSide.LONG, entry_price=100.0, favorable_extreme=100.0, atr=2.0, trail_activate_atr_mult=1.0) is False
def test_trail_activated_long():
    assert trail_activated(PositionSide.LONG, entry_price=100.0, favorable_extreme=102.5, atr=2.0, trail_activate_atr_mult=1.0) is True
def test_trail_not_activated_long_below_threshold():
    assert trail_activated(PositionSide.LONG, entry_price=100.0, favorable_extreme=101.5, atr=2.0, trail_activate_atr_mult=1.0) is False
def test_trail_activated_short():
    assert trail_activated(PositionSide.SHORT, entry_price=100.0, favorable_extreme=97.5, atr=2.0, trail_activate_atr_mult=1.0) is True
def test_trail_not_activated_short_adverse():
    assert trail_activated(PositionSide.SHORT, entry_price=100.0, favorable_extreme=102.0, atr=2.0, trail_activate_atr_mult=1.0) is False
def test_crash_triggered_long():
    assert crash_triggered(PositionSide.LONG, current_price=93.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is True
def test_crash_not_triggered_long_small_move():
    assert crash_triggered(PositionSide.LONG, current_price=97.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is False
def test_crash_triggered_short():
    assert crash_triggered(PositionSide.SHORT, current_price=107.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is True
def test_crash_not_triggered_on_favorable_spike_long():
    assert crash_triggered(PositionSide.LONG, current_price=103.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is False
def test_catastrophic_long():
    assert catastrophic_stop_hit(PositionSide.LONG, entry_price=100.0, current_price=88.0, atr=2.0, catastrophic_atr_mult=6.0) is True
def test_catastrophic_short():
    assert catastrophic_stop_hit(PositionSide.SHORT, entry_price=100.0, current_price=112.0, atr=2.0, catastrophic_atr_mult=6.0) is True
def test_catastrophic_not_triggered_within_threshold():
    assert catastrophic_stop_hit(PositionSide.LONG, entry_price=100.0, current_price=90.0, atr=2.0, catastrophic_atr_mult=6.0) is False


# ---------------------------------------------------------------------------
# Generator tests (Task 2)
# ---------------------------------------------------------------------------

_FIXED_ENTRY_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _long_position(entry_price=100.0, highest_price=None, stop_price=0.0, **md):
    meta = {"entry_atr": 2.0, "prev_price": entry_price, **md}
    return Position(id="pos-long-1", code="A05603", name="KOSPI200 Mini", side=PositionSide.LONG,
        quantity=1, entry_price=entry_price, entry_time=_FIXED_ENTRY_TIME,
        current_price=entry_price, stop_price=stop_price,
        highest_price=highest_price if highest_price is not None else entry_price, metadata=meta)

def _short_position(entry_price=100.0, lowest_price=None, stop_price=0.0, **md):
    meta = {"entry_atr": 2.0, "prev_price": entry_price, **md}
    return Position(id="pos-short-1", code="A05603", name="KOSPI200 Mini", side=PositionSide.SHORT,
        quantity=1, entry_price=entry_price, entry_time=_FIXED_ENTRY_TIME,
        current_price=entry_price, stop_price=stop_price,
        lowest_price=lowest_price if lowest_price is not None else entry_price, metadata=meta)

def _cfg(**kw):
    d = dict(trail_atr_mult=3.0, trail_activate_atr_mult=1.0, crash_atr_mult=3.5, crash_cooldown_minutes=30,
        catastrophic_atr_mult=6.0, eod_close_enabled=False, default_exit_confidence=0.9, enabled=True)
    d.update(kw)
    return TrackAExitConfig(**d)

def _ctx(position, close, atr=2.0):
    return ExitContext(position=position, market_data={"close": close, "atr": atr}, timestamp=datetime.now(UTC))

@pytest.mark.asyncio
async def test_crash_guard_long_fires():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(prev_price=100.0), close=92.0))
    assert fired and sig.reason == ExitReason.FORCE_CLOSE and sig.priority == 1 and sig.metadata.get("exit_type") == "crash_guard"

@pytest.mark.asyncio
async def test_crash_guard_short_fires():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_short_position(prev_price=100.0), close=108.0))
    assert fired and sig.reason == ExitReason.FORCE_CLOSE

@pytest.mark.asyncio
async def test_crash_guard_no_trigger_on_favorable_spike():
    fired, _ = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(prev_price=100.0), close=108.0))
    assert fired is False

@pytest.mark.asyncio
async def test_catastrophic_stop_long():
    # prev_price close to close (1pt drop) so crash guard does not fire (threshold=7),
    # but total loss from entry (100→88 = 12 = 6×atr) triggers catastrophic backstop.
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(prev_price=89.0), close=88.0))
    assert fired and sig.reason == ExitReason.STOP_LOSS and sig.priority == 2 and sig.metadata.get("exit_type") == "catastrophic_stop"

@pytest.mark.asyncio
async def test_catastrophic_stop_short():
    # prev_price close to close (1pt rise) so crash guard does not fire (threshold=7),
    # but total loss from entry (100→112 = 12 = 6×atr) triggers catastrophic backstop.
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_short_position(prev_price=111.0), close=112.0))
    assert fired and sig.reason == ExitReason.STOP_LOSS

@pytest.mark.asyncio
async def test_trail_not_activated_before_threshold():
    fired, _ = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(highest_price=101.0, prev_price=101.0), close=99.5))
    assert fired is False

@pytest.mark.asyncio
async def test_trail_fires_after_activation_long():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(highest_price=106.0, prev_price=105.0), close=99.0))
    assert fired and sig.reason == ExitReason.TRAILING_STOP and sig.priority == 3 and sig.metadata.get("exit_type") == "trail_stop"

@pytest.mark.asyncio
async def test_trail_does_not_fire_above_trail_long():
    fired, _ = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(highest_price=106.0, prev_price=105.0), close=100.5))
    assert fired is False

@pytest.mark.asyncio
async def test_trail_fires_short():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_short_position(lowest_price=94.0, prev_price=95.0), close=101.0))
    assert fired and sig.reason == ExitReason.TRAILING_STOP

@pytest.mark.asyncio
async def test_crash_takes_precedence_over_catastrophic():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(prev_price=100.0), close=86.0))
    assert fired and sig.reason == ExitReason.FORCE_CLOSE and sig.priority == 1

@pytest.mark.asyncio
async def test_catastrophic_beats_trail():
    # prev_price close to close (1pt drop) so crash guard does not fire;
    # total loss 100→88=12=6×atr triggers catastrophic (p2) which beats trail (p3).
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(highest_price=110.0, prev_price=89.0), close=88.0))
    assert fired and sig.reason == ExitReason.STOP_LOSS and sig.priority == 2

@pytest.mark.asyncio
async def test_no_atr_skips_all_atr_exits():
    pos = _long_position(prev_price=70.0); pos.metadata.pop("entry_atr", None)
    fired, _ = await TrackAExit(_cfg(eod_close_enabled=False)).should_exit(_ctx(pos, close=70.0, atr=0.0))
    assert fired is False

@pytest.mark.asyncio
async def test_scan_positions_returns_signals_for_triggered():
    signals = await TrackAExit(_cfg()).scan_positions(positions=[_long_position(prev_price=100.0)], market_data={"A05603": {"close": 92.0, "atr": 2.0}})
    assert len(signals) == 1 and signals[0].reason == ExitReason.FORCE_CLOSE


@pytest.mark.asyncio
async def test_eod_fires_when_atr_zero(monkeypatch):
    """I1: ATR=0 skips ATR-based exits but EOD_CLOSE must still fire."""
    from zoneinfo import ZoneInfo
    import shared.strategy.exit.track_a_exit as _mod

    KST = ZoneInfo("Asia/Seoul")
    # Monday 2026-06-22 at 15:20 KST — well past 15:15 EOD cutoff.
    fixed_now = datetime(2026, 6, 22, 15, 20, 0, tzinfo=KST)

    monkeypatch.setattr(_mod, "now_kst", lambda: fixed_now)
    monkeypatch.setattr(_mod, "is_trading_day_kst", lambda dt: True)
    monkeypatch.setattr(_mod, "effective_close_time", lambda cfg_close: cfg_close)

    # Position with no entry_atr and snapshot atr=0 → _get_atr returns 0.0.
    pos = _long_position(prev_price=100.0)
    pos.metadata.pop("entry_atr", None)

    cfg = _cfg(eod_close_enabled=True, eod_close_hour=15, eod_close_minute=15)
    ctx = ExitContext(position=pos, market_data={"close": 100.0, "atr": 0.0}, timestamp=fixed_now)

    fired, sig = await TrackAExit(cfg).should_exit(ctx)
    assert fired
    assert sig.reason == ExitReason.EOD_CLOSE
    assert sig.metadata["exit_type"] == "eod_close"


# ---------------------------------------------------------------------------
# I1: windowed crash guard (max adverse move over ~60s window)
# ---------------------------------------------------------------------------

def _ts(seconds_ago: float = 0.0) -> datetime:
    """Return a KST-aware datetime offset seconds_ago from a fixed reference."""
    from zoneinfo import ZoneInfo
    ref = datetime(2026, 6, 22, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    return ref - timedelta(seconds=seconds_ago)


def test_max_adverse_move_long_gradual_crash():
    """Gradual 1-min crash (spread across 4 ticks) is detected by windowed helper."""
    # LONG position: price dropped from 100 → 93 over 60s (adverse = 7 pts).
    history = [
        (_ts(60.0), 100.0),  # oldest
        (_ts(45.0), 98.0),
        (_ts(30.0), 96.0),
        (_ts(15.0), 93.0),  # latest
    ]
    current_ts = _ts(0.0)
    # Max adverse move for LONG = worst recent price - oldest price in window.
    move = max_adverse_move_in_window(
        side=PositionSide.LONG,
        current_price=93.0,
        history=history,
        window_seconds=60.0,
        current_ts=current_ts,
    )
    # Oldest price in window is 100.0; current=93 → adverse move = 7.0.
    assert move == pytest.approx(7.0)


def test_max_adverse_move_short_gradual_rally():
    """Gradual 1-min adverse rally for SHORT is detected."""
    # SHORT position: price rose from 100 → 107 over 60s.
    history = [
        (_ts(60.0), 100.0),
        (_ts(45.0), 103.0),
        (_ts(30.0), 105.0),
        (_ts(15.0), 107.0),
    ]
    move = max_adverse_move_in_window(
        side=PositionSide.SHORT,
        current_price=107.0,
        history=history,
        window_seconds=60.0,
        current_ts=_ts(0.0),
    )
    assert move == pytest.approx(7.0)


def test_max_adverse_move_favorable_spike_long():
    """A favorable spike (price UP for LONG) returns 0 or negative."""
    history = [(_ts(30.0), 100.0)]
    move = max_adverse_move_in_window(
        side=PositionSide.LONG,
        current_price=105.0,
        history=history,
        window_seconds=60.0,
        current_ts=_ts(0.0),
    )
    assert move <= 0.0


def test_max_adverse_move_ignores_stale_ticks():
    """Ticks older than crash_window_seconds are excluded from the max adverse calculation."""
    history = [
        (_ts(120.0), 90.0),   # stale: 120s ago, outside 60s window
        (_ts(50.0), 99.0),    # in window
        (_ts(10.0), 97.0),    # in window
    ]
    move = max_adverse_move_in_window(
        side=PositionSide.LONG,
        current_price=97.0,
        history=history,
        window_seconds=60.0,
        current_ts=_ts(0.0),
    )
    # Only the in-window ticks matter: oldest=99.0, current=97.0 → adverse=2.0.
    # The stale tick at 90.0 would have given adverse=7 but must be ignored.
    assert move == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_windowed_crash_triggers_on_gradual_drop():
    """Gradual 1-min drop that does NOT trip single-tick guard DOES trip windowed guard."""
    from zoneinfo import ZoneInfo
    # Each tick drops ~1.5 pts: gradual enough that single-tick (1.5 < 7 = 3.5×2) does NOT fire.
    # But across 60s the total drop is 6 pts, which equals crash_atr_mult×ATR (3.5×2=7)... just short.
    # Use 8pt cumulative drop (well over 7) to guarantee window fires.
    entry_ts = datetime(2026, 6, 22, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    pos = _long_position(entry_price=100.0, prev_price=100.0)
    # Seed crash_price_history in metadata: 60s ago price was 100; single prev was 98.5 (drop=1.5<7).
    pos.metadata["crash_price_history"] = [
        [entry_ts.isoformat(), 100.0],
        [(entry_ts + timedelta(seconds=15)).isoformat(), 98.5],
        [(entry_ts + timedelta(seconds=30)).isoformat(), 96.0],
        [(entry_ts + timedelta(seconds=45)).isoformat(), 93.0],
    ]
    pos.metadata["prev_price"] = 93.0  # small single-tick move (93→92=1 < 7)

    cfg = _cfg(crash_atr_mult=3.5, crash_window_seconds=60.0)
    # current_price=92: single-tick drop = 1.0 (not enough); windowed worst = 100→92=8 > 7.
    ctx = ExitContext(position=pos, market_data={"close": 92.0, "atr": 2.0}, timestamp=entry_ts + timedelta(seconds=60))
    fired, sig = await TrackAExit(cfg).should_exit(ctx)
    assert fired, "Windowed crash guard should have fired"
    assert sig.reason == ExitReason.FORCE_CLOSE
    assert sig.metadata["exit_type"] == "crash_guard"


@pytest.mark.asyncio
async def test_single_tick_spike_still_fires():
    """Single-tick spike path still works (fast path preserved alongside windowed)."""
    pos = _long_position(prev_price=100.0)
    cfg = _cfg(crash_atr_mult=3.5, crash_window_seconds=60.0)
    # 100 → 92: single-tick drop = 8 > 7 = 3.5×2 → should fire immediately.
    ctx = ExitContext(position=pos, market_data={"close": 92.0, "atr": 2.0}, timestamp=datetime.now(UTC))
    fired, sig = await TrackAExit(cfg).should_exit(ctx)
    assert fired
    assert sig.reason == ExitReason.FORCE_CLOSE


@pytest.mark.asyncio
async def test_favorable_move_in_window_does_not_trigger_long():
    """Windowed check on a rising market (favorable for LONG) never fires crash guard."""
    from zoneinfo import ZoneInfo
    entry_ts = datetime(2026, 6, 22, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    pos = _long_position(entry_price=100.0, prev_price=105.0)
    # History shows prices rising (favorable for long).
    pos.metadata["crash_price_history"] = [
        [entry_ts.isoformat(), 100.0],
        [(entry_ts + timedelta(seconds=30)).isoformat(), 103.0],
        [(entry_ts + timedelta(seconds=55)).isoformat(), 105.0],
    ]
    cfg = _cfg(crash_atr_mult=3.5, crash_window_seconds=60.0)
    ctx = ExitContext(position=pos, market_data={"close": 107.0, "atr": 2.0}, timestamp=entry_ts + timedelta(seconds=60))
    fired, _ = await TrackAExit(cfg).should_exit(ctx)
    assert not fired


@pytest.mark.asyncio
async def test_windowed_crash_short_fires():
    """Windowed crash guard works symmetrically for SHORT positions."""
    from zoneinfo import ZoneInfo
    entry_ts = datetime(2026, 6, 22, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    pos = _short_position(entry_price=100.0, prev_price=100.0)
    # History shows prices rising (adverse for short): 100 → 108 over 60s.
    pos.metadata["crash_price_history"] = [
        [entry_ts.isoformat(), 100.0],
        [(entry_ts + timedelta(seconds=20)).isoformat(), 103.0],
        [(entry_ts + timedelta(seconds=40)).isoformat(), 106.0],
        [(entry_ts + timedelta(seconds=55)).isoformat(), 108.0],
    ]
    pos.metadata["prev_price"] = 108.0  # single-tick small move
    cfg = _cfg(crash_atr_mult=3.5, crash_window_seconds=60.0)
    ctx = ExitContext(position=pos, market_data={"close": 109.0, "atr": 2.0}, timestamp=entry_ts + timedelta(seconds=60))
    fired, sig = await TrackAExit(cfg).should_exit(ctx)
    assert fired
    assert sig.reason == ExitReason.FORCE_CLOSE
