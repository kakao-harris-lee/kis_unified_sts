"""Regression + parity tests for Setup C's 15-minute breakout-range wiring.

Background
----------
Setup C (``setup_c_event_reaction``) detects a breakout with the strict
inequality ``current_price > last_15min_high`` (and the symmetric low for
shorts).  The orchestrator entry path collects indicators via
:class:`shared.indicators.resolver.StreamingIndicatorResolver`, which — prior to
the fix — never populated ``last_15min_high`` / ``last_15min_low``.  When those
keys are absent the adapter's MarketContext builder defaults BOTH to
``current_price`` (``setup_adapters._build_market_context``), collapsing the
range so ``current_price > last_15min_high`` can never be true.  Result: Setup C
could NEVER detect a breakout live, while the backtest replay
(:class:`shared.backtest.market_context_replay.MarketContextReplay`) populated
the range causally and DID detect breakouts — a backtest/live parity break.

The fix wires ``StreamingIndicatorEngine.get_recent_range`` into the resolver
(driven by the strategy's declared ``required_indicators``) so the live
MarketContext carries the same causal ``[i-15, i-1]`` range the replay computes.

These tests assert:
1. A genuine breakout IS detected through the real live wiring
   (resolver + engine + Setup C adapter), proving the fix.
2. A non-breakout bar is still rejected (no over-correction / spurious firing).
3. The live ``get_recent_range`` window equals the backtest replay's
   ``highs[i-15:i]`` / ``lows[i-15:i]`` window exactly (parity, causal — current
   bar excluded, no look-ahead).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from services.trading.indicator_engine import StreamingIndicatorEngine
from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.context import ScheduledEvent
from shared.execution.contract_spec import ContractSpec
from shared.indicators.resolver import StreamingIndicatorResolver
from shared.strategy.base import EntryContext
from shared.strategy.entry.setup_adapters import (
    LLMTuningConfig,
    SetupCEntryAdapter,
    SetupCEntryConfig,
)

KST = ZoneInfo("Asia/Seoul")
SYMBOL = "A05603"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed(engine: StreamingIndicatorEngine, candles: list[dict]) -> None:
    """Seed COMPLETED 1-min candles into the engine (chronological order)."""
    engine.seed_candles(SYMBOL, candles)


def _setup_c_adapter() -> SetupCEntryAdapter:
    """Build a Setup C adapter with LLM tuning + daily bias OFF.

    Isolates the breakout logic so the test exercises ONLY the 15-min-range
    gate (the path the wiring fix repairs), not LLM/regime side-effects.
    """
    cfg = SetupCEntryConfig(
        enabled=True,
        llm_tuning=LLMTuningConfig(enabled=False),
        daily_bias_filter_enabled=False,
    )
    return SetupCEntryAdapter(config=cfg)


def _entry_context(
    *,
    current_price: float,
    indicators: dict,
    now: datetime,
    event: ScheduledEvent,
) -> EntryContext:
    """Build a live-style EntryContext.

    Mirrors the orchestrator: ``enriched`` (market_data) is updated with the
    resolver-collected ``indicators`` so the range keys reach the adapter via
    either dict (``_build_market_context`` reads both).
    """
    market_data = {
        "code": SYMBOL,
        "close": current_price,
        "current_price": current_price,
        "prev_close": current_price - 1.0,
        "open": current_price - 1.0,
    }
    market_data.update(indicators)
    return EntryContext(
        market_data=market_data,
        indicators=indicators,
        current_positions={},
        timestamp=now,
        metadata={"scheduled_events": [event]},
    )


def _tier1_event(now: datetime) -> ScheduledEvent:
    """A tier-1 event 5 minutes before ``now`` (inside Setup C's 15-min window)."""
    return ScheduledEvent(
        event_id="evt-fomc-1",
        event_type="fomc",
        scheduled_at=now - timedelta(minutes=5),
        impact_tier=1,
    )


# ---------------------------------------------------------------------------
# Regression: breakout detection through the real live wiring
# ---------------------------------------------------------------------------


def test_live_wiring_detects_genuine_breakout():
    """End-to-end: resolver + engine populate the range → Setup C fires.

    Without the wiring fix the resolver would not inject ``last_15min_high/low``
    and this breakout would be UNDETECTABLE live.
    """
    engine = StreamingIndicatorEngine()
    # 20 completed bars forming a flat ~100 range (highs ~100.0, lows ~99.0),
    # plus enough history for ATR. The current (in-progress) bar is the breakout.
    base_ts = datetime(2026, 6, 26, 9, 30, tzinfo=KST)
    candles = []
    for i in range(20):
        candles.append(
            {
                "open": 99.5,
                "high": 100.0,
                "low": 99.0,
                "close": 99.5,
                "volume": 100,
                "datetime": base_ts + timedelta(minutes=i),
            }
        )
    _seed(engine, candles)

    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=("atr", "last_15min_high", "last_15min_low"),
    )
    indicators = resolver.collect_entry_indicators(SYMBOL)
    # The resolver MUST now supply the range (this is the fix).
    assert indicators["last_15min_high"] == 100.0
    assert indicators["last_15min_low"] == 99.0
    # Provide ATR explicitly (seeded flat bars yield ~0 ATR otherwise).
    indicators["atr"] = 1.0
    indicators["atr_14"] = 1.0

    now = datetime(2026, 6, 26, 10, 0, tzinfo=KST)  # 60 min since open, in-window
    # Breakout: 100.3 > prior high 100.0, within 0.5*ATR (=0.5) buffer.
    ctx = _entry_context(
        current_price=100.3, indicators=indicators, now=now, event=_tier1_event(now)
    )

    adapter = _setup_c_adapter()
    signal = asyncio.run(adapter.generate(ctx))

    assert signal is not None, (
        "Setup C failed to detect a genuine breakout through live wiring — "
        f"reject_reason={adapter._setup.last_reject_reason!r}"
    )
    assert signal.metadata["direction"] == "long"
    assert signal.metadata["setup_type"] == "C_event_reaction"


def test_live_wiring_short_breakdown_detected():
    """Symmetry: a downside breakdown fires a short (long/short symmetric)."""
    engine = StreamingIndicatorEngine()
    base_ts = datetime(2026, 6, 26, 9, 30, tzinfo=KST)
    candles = [
        {
            "open": 99.5,
            "high": 100.0,
            "low": 99.0,
            "close": 99.5,
            "volume": 100,
            "datetime": base_ts + timedelta(minutes=i),
        }
        for i in range(20)
    ]
    _seed(engine, candles)

    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=("atr", "last_15min_high", "last_15min_low"),
    )
    indicators = resolver.collect_entry_indicators(SYMBOL)
    indicators["atr"] = 1.0
    indicators["atr_14"] = 1.0

    now = datetime(2026, 6, 26, 10, 0, tzinfo=KST)
    # Breakdown: 98.7 < prior low 99.0, within 0.5*ATR buffer.
    ctx = _entry_context(
        current_price=98.7, indicators=indicators, now=now, event=_tier1_event(now)
    )

    adapter = _setup_c_adapter()
    signal = asyncio.run(adapter.generate(ctx))

    assert signal is not None
    assert signal.metadata["direction"] == "short"


def test_live_wiring_does_not_fire_inside_range():
    """No over-correction: a price INSIDE the range is still rejected.

    Confirms the wiring fix did not make Setup C fire spuriously — only a real
    breakout beyond the prior 15-min high/low produces a signal.
    """
    engine = StreamingIndicatorEngine()
    base_ts = datetime(2026, 6, 26, 9, 30, tzinfo=KST)
    candles = [
        {
            "open": 99.5,
            "high": 100.0,
            "low": 99.0,
            "close": 99.5,
            "volume": 100,
            "datetime": base_ts + timedelta(minutes=i),
        }
        for i in range(20)
    ]
    _seed(engine, candles)

    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=("atr", "last_15min_high", "last_15min_low"),
    )
    indicators = resolver.collect_entry_indicators(SYMBOL)
    indicators["atr"] = 1.0
    indicators["atr_14"] = 1.0

    now = datetime(2026, 6, 26, 10, 0, tzinfo=KST)
    # 99.5 is strictly inside [99.0, 100.0] → no breakout.
    ctx = _entry_context(
        current_price=99.5, indicators=indicators, now=now, event=_tier1_event(now)
    )

    adapter = _setup_c_adapter()
    signal = asyncio.run(adapter.generate(ctx))

    assert signal is None
    assert "no_breakout" in (adapter._setup.last_reject_reason or "")


# ---------------------------------------------------------------------------
# Parity: live get_recent_range window == backtest replay [i-15, i-1] window
# ---------------------------------------------------------------------------


def _two_session_frame(seed: int = 42) -> list[dict]:
    """Two trading sessions of synthetic 1-min OHLCV bars.

    The replay needs a previous session to derive ``prev_close`` before it
    yields any context.
    """
    rng = np.random.default_rng(seed)

    def gen(day: int, n: int, start_price: float) -> list[dict]:
        out: list[dict] = []
        price = start_price
        start = datetime(2026, 6, day, 9, 0, tzinfo=KST)
        for i in range(n):
            o = price
            h = o + abs(rng.normal(0, 0.5))
            low = o - abs(rng.normal(0, 0.5))
            c = low + rng.random() * (h - low)
            out.append(
                {
                    "timestamp": start + timedelta(minutes=i),
                    "open": o,
                    "high": h,
                    "low": low,
                    "close": c,
                    "volume": 100,
                }
            )
            price = c
        return out

    day1 = gen(25, 30, 100.0)
    day2 = gen(26, 80, day1[-1]["close"])
    return day1 + day2


def test_live_range_matches_backtest_replay_window():
    """The live and backtest 15-min ranges are bit-for-bit identical.

    The backtest replay computes ``highs[i-15:i]`` / ``lows[i-15:i]`` (current
    bar EXCLUDED).  The live engine's ``get_recent_range`` reads only COMPLETED
    candles — equivalent to the same causal window — so for identical bar data
    the two must agree exactly (no look-ahead, no off-by-one).
    """
    rows = _two_session_frame()
    df = pd.DataFrame(rows)

    spec = ContractSpec(
        name=SYMBOL,
        multiplier_krw_per_point=250000,
        tick_size_points=0.05,
        tick_value_krw=12500,
        commission_rate=0.0,
        symbol_prefix="A05",
    )
    replay = MarketContextReplay(
        df=df,
        symbol=SYMBOL,
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=spec,
    )
    replay_ranges: dict[int, tuple[float, float]] = {
        int(ctx.now.timestamp()): (ctx.last_15min_high, ctx.last_15min_low)
        for ctx in replay.iter_contexts()
    }
    assert replay_ranges, "replay yielded no contexts — fixture too short"

    checked = 0
    for i, row in enumerate(rows):
        key = int(row["timestamp"].timestamp())
        if key not in replay_ranges:
            continue
        engine = StreamingIndicatorEngine()
        # Completed history is rows[0..i-1]; bar i is the current/in-progress bar.
        engine.seed_candles(
            SYMBOL,
            [
                {
                    "open": r["open"],
                    "high": r["high"],
                    "low": r["low"],
                    "close": r["close"],
                    "volume": r["volume"],
                }
                for r in rows[:i]
            ],
        )
        live = engine.get_recent_range(SYMBOL, 15)
        assert live is not None
        live_hi, live_lo = live
        rep_hi, rep_lo = replay_ranges[key]
        assert live_hi == rep_hi, f"high mismatch at bar {i}: {live_hi} != {rep_hi}"
        assert live_lo == rep_lo, f"low mismatch at bar {i}: {live_lo} != {rep_lo}"
        checked += 1

    assert checked > 0, "no overlapping bars compared"
