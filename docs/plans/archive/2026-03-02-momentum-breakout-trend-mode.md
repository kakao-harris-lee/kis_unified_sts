# Momentum Breakout Trend Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add regime-aware trend mode to `momentum_breakout` strategy with EMA pullback trigger for bull market entries.

**Architecture:** Extend existing `MomentumBreakoutConfig` with trend mode fields. When regime is BULL/SIDEWAYS_UP, entry conditions relax (lower RVOL, zero breakout buffer) and a new EMA pullback trigger activates. Exit parameters are passed via position.metadata overrides to `ATRDynamicExit`.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio, dataclasses, YAML config

**Design Doc:** `docs/plans/2026-03-02-momentum-breakout-trend-mode-design.md`

---

### Task 1: Add EMA indicators to IndicatorEngine

**Files:**
- Modify: `services/trading/indicator_engine.py` (after line 687, inside `_compute_indicators`)
- Test: `tests/unit/trading/test_indicator_engine_ema.py` (create)

**Step 1: Write the failing test**

Create `tests/unit/trading/test_indicator_engine_ema.py`:

```python
"""Test EMA indicator additions to StreamingIndicatorEngine."""

import pytest
from datetime import datetime, timezone, timedelta
from services.trading.indicator_engine import StreamingIndicatorEngine

KST = timezone(timedelta(hours=9))


def _feed_candles(engine: StreamingIndicatorEngine, symbol: str, prices: list[float]):
    """Feed a list of close prices as synthetic candles."""
    base = datetime(2026, 3, 2, 9, 0, tzinfo=KST)
    for i, price in enumerate(prices):
        tick_time = base + timedelta(minutes=i)
        # Each price becomes one candle (open=high=low=close for simplicity)
        engine.on_tick(
            symbol,
            {"close": price, "high": price * 1.005, "low": price * 0.995,
             "open": price, "volume": 10000 + i},
            tick_time,
        )
        # Advance to next minute to finalize candle
        engine.on_tick(
            symbol,
            {"close": price, "high": price * 1.005, "low": price * 0.995,
             "open": price, "volume": 10000 + i},
            tick_time + timedelta(seconds=61),
        )


def test_ema_values_present_after_warmup():
    """EMA 5/20/60 absolute values appear in indicators after sufficient candles."""
    engine = StreamingIndicatorEngine(bb_period=20)
    # Feed 65 candles (enough for EMA60)
    prices = [50000 + i * 10 for i in range(65)]  # gentle uptrend
    _feed_candles(engine, "005930", prices)

    indicators = engine.get_indicators("005930")
    assert indicators is not None
    assert "ema_5" in indicators
    assert "ema_20" in indicators
    assert "ema_60" in indicators
    assert indicators["ema_5"] > 0
    assert indicators["ema_20"] > 0
    assert indicators["ema_60"] > 0


def test_ema_aligned_true_in_uptrend():
    """ema_aligned is True when EMA5 > EMA20 > EMA60 (uptrend)."""
    engine = StreamingIndicatorEngine(bb_period=20)
    # Strong uptrend: prices rising steadily
    prices = [50000 + i * 50 for i in range(65)]
    _feed_candles(engine, "005930", prices)

    indicators = engine.get_indicators("005930")
    assert indicators is not None
    assert indicators.get("ema_aligned") is True
    assert indicators["ema_5"] > indicators["ema_20"] > indicators["ema_60"]


def test_ema_aligned_false_in_downtrend():
    """ema_aligned is False when prices are falling (EMA5 < EMA20 < EMA60)."""
    engine = StreamingIndicatorEngine(bb_period=20)
    # Downtrend: prices falling
    prices = [55000 - i * 50 for i in range(65)]
    _feed_candles(engine, "005930", prices)

    indicators = engine.get_indicators("005930")
    assert indicators is not None
    assert indicators.get("ema_aligned") is False


def test_ema_60_zero_when_insufficient_candles():
    """ema_60 is 0 when fewer than 60 candles available."""
    engine = StreamingIndicatorEngine(bb_period=20)
    # Only 25 candles — enough for bb_period but not EMA60
    prices = [50000 + i * 10 for i in range(25)]
    _feed_candles(engine, "005930", prices)

    indicators = engine.get_indicators("005930")
    assert indicators is not None
    # EMA5 and EMA20 should work
    assert indicators["ema_5"] > 0
    assert indicators["ema_20"] > 0
    # EMA60 should be 0 (insufficient data)
    assert indicators["ema_60"] == 0.0
    assert indicators["ema_aligned"] is False
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/trading/test_indicator_engine_ema.py -v`
Expected: FAIL — `ema_5`, `ema_20`, `ema_60`, `ema_aligned` keys not found

**Step 3: Implement EMA indicators**

In `services/trading/indicator_engine.py`, inside `_compute_indicators()`, after line 687 (after `ema_ratio_*` block), add:

```python
        # EMA absolute values for trend mode (5, 20, 60)
        result["ema_5"] = self._ema_last(closes, 5)
        result["ema_20"] = self._ema_last(closes, 20)
        if n >= 60:
            result["ema_60"] = self._ema_last(closes, 60)
        else:
            result["ema_60"] = 0.0
        # EMA alignment: EMA5 > EMA20 > EMA60 (confirmed uptrend)
        result["ema_aligned"] = (
            result["ema_60"] > 0
            and result["ema_5"] > result["ema_20"] > result["ema_60"]
        )
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/trading/test_indicator_engine_ema.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add services/trading/indicator_engine.py tests/unit/trading/test_indicator_engine_ema.py
git commit -m "feat: add EMA 5/20/60 absolute values and ema_aligned to IndicatorEngine"
```

---

### Task 2: Add trend mode config fields to MomentumBreakoutConfig

**Files:**
- Modify: `shared/strategy/entry/momentum_breakout.py` (MomentumBreakoutConfig dataclass)
- Test: `tests/unit/strategy/test_momentum_breakout_entry.py` (add config test)

**Step 1: Write the failing test**

Append to `tests/unit/strategy/test_momentum_breakout_entry.py`:

```python
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
    """Trend mode fields load correctly from dict (YAML simulation)."""
    raw = {
        "params": {
            "trend_mode_enabled": True,
            "trend_rvol_threshold": 1.2,
            "trend_exit_max_hold_days": 20,
        }
    }
    cfg = MomentumBreakoutConfig.from_dict(raw)
    assert cfg.trend_mode_enabled is True
    assert cfg.trend_rvol_threshold == 1.2
    assert cfg.trend_exit_max_hold_days == 20
    # Other trend defaults unchanged
    assert cfg.trend_ema_pullback_enabled is True
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/strategy/test_momentum_breakout_entry.py::test_trend_mode_config_defaults -v`
Expected: FAIL — `MomentumBreakoutConfig` has no attribute `trend_mode_enabled`

**Step 3: Add config fields**

In `shared/strategy/entry/momentum_breakout.py`, add to `MomentumBreakoutConfig` dataclass (after `confidence_base`):

```python
    # Trend mode (activated when regime matches trend_mode_regimes)
    trend_mode_enabled: bool = False
    trend_mode_regimes: list[str] = field(default_factory=lambda: ["BULL", "SIDEWAYS_UP"])
    trend_rvol_threshold: float = 1.0
    trend_breakout_buffer_pct: float = 0.0
    trend_signal_cooldown_seconds: int = 60
    # EMA pullback trigger (trend_mode only)
    trend_ema_pullback_enabled: bool = True
    trend_ema_fast: int = 5
    trend_ema_mid: int = 20
    trend_ema_slow: int = 60
    trend_ema_touch_buffer_atr: float = 1.0
    trend_rsi_min: float = 40.0
    # Trend mode exit overrides (passed via signal.metadata → position.metadata)
    trend_exit_stop_atr_multiplier: float = 2.5
    trend_exit_trail_activation_atr: float = 1.5
    trend_exit_trail_atr_multiplier: float = 2.5
    trend_exit_max_hold_days: int = 15
```

Also add `from dataclasses import dataclass, field` import (replace existing `from dataclasses import dataclass`).

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/strategy/test_momentum_breakout_entry.py::test_trend_mode_config_defaults tests/unit/strategy/test_momentum_breakout_entry.py::test_trend_mode_config_from_dict -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/strategy/entry/momentum_breakout.py tests/unit/strategy/test_momentum_breakout_entry.py
git commit -m "feat: add trend mode config fields to MomentumBreakoutConfig"
```

---

### Task 3: Implement trend mode entry logic with EMA pullback

**Files:**
- Modify: `shared/strategy/entry/momentum_breakout.py` (MomentumBreakoutEntry.generate + _check_ema_pullback)
- Test: `tests/unit/strategy/test_momentum_breakout_entry.py` (add trend mode tests)

**Step 1: Write the failing tests**

Append to `tests/unit/strategy/test_momentum_breakout_entry.py`:

```python
# ---------------------------------------------------------------------------
# Trend mode entry logic
# ---------------------------------------------------------------------------


def _make_trend_context(
    code="005930",
    close=50000.0,
    high=None,
    high_5=49900.0,
    rvol=1.2,
    volume=150000.0,
    volume_ma=100000.0,
    atr=600.0,
    rsi=50.0,
    ema_5=50100.0,
    ema_20=49800.0,
    ema_60=49500.0,
    ema_aligned=True,
    regime="BULL",
    hour=10,
    minute=30,
    watchlist_codes=("005930",),
) -> EntryContext:
    """Helper: build EntryContext for trend mode tests."""
    now = datetime(2026, 2, 26, hour, minute, tzinfo=KST)
    watchlist = {"strategies": {"momentum_breakout": list(watchlist_codes)}}
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
        indicators={
            "rsi": rsi,
            "ema_5": ema_5,
            "ema_20": ema_20,
            "ema_60": ema_60,
            "ema_aligned": ema_aligned,
        },
        timestamp=now,
        metadata={
            "daily_watchlist": watchlist,
            "regime": regime,
        },
    )


@pytest.fixture
def trend_entry():
    """Entry strategy with trend_mode_enabled."""
    cfg = MomentumBreakoutConfig(
        breakout_buffer_pct=0.1,
        rvol_threshold=1.5,
        volume_threshold=1.0,
        min_atr_cost_ratio=0.01,
        round_trip_cost=0.005,
        skip_market_open_minutes=30,
        skip_market_close_minutes=15,
        signal_cooldown_seconds=120,
        confidence_base=0.65,
        # Trend mode ON
        trend_mode_enabled=True,
        trend_rvol_threshold=1.0,
        trend_breakout_buffer_pct=0.0,
        trend_signal_cooldown_seconds=60,
        trend_ema_pullback_enabled=True,
        trend_ema_touch_buffer_atr=1.0,
        trend_rsi_min=40.0,
    )
    return MomentumBreakoutEntry(cfg)


@pytest.mark.asyncio
async def test_trend_mode_ema_pullback_generates_signal(trend_entry):
    """EMA pullback generates signal in BULL regime without N-day breakout."""
    ctx = _make_trend_context(
        close=49850.0,    # NOT breaking high_5 (49900) — no breakout
        high_5=49900.0,
        rvol=1.2,         # below normal threshold (1.5) but above trend threshold (1.0)
        atr=600.0,
        rsi=50.0,
        ema_5=49900.0,    # close > ema_5? No: 49850 < 49900 — need close > ema_5
        ema_20=49600.0,
        ema_60=49200.0,
        ema_aligned=True,
        regime="BULL",
    )
    # close (49850) < ema_5 (49900) → bounce check fails
    signal = await trend_entry.generate(ctx)
    assert signal is None

    # Fix: close > ema_5 (bounce confirmed)
    trend_entry._last_signal_time.clear()
    ctx2 = _make_trend_context(
        close=49950.0,    # > ema_5 (49900) ✓, near ema_20 (49600, |350| < ATR 600) ✓
        high_5=50500.0,   # high_5 far above → no breakout
        rvol=1.2,
        atr=600.0,
        rsi=50.0,
        ema_5=49900.0,
        ema_20=49600.0,
        ema_60=49200.0,
        ema_aligned=True,
        regime="BULL",
    )
    signal2 = await trend_entry.generate(ctx2)
    assert signal2 is not None
    assert signal2.metadata["trend_mode"] is True
    assert signal2.metadata["trigger"] == "ema_pullback"


@pytest.mark.asyncio
async def test_trend_mode_relaxed_breakout(trend_entry):
    """Breakout with lower RVOL (1.2) succeeds in BULL regime."""
    ctx = _make_trend_context(
        close=50000.0,    # > high_5 (49900) → breakout
        high_5=49900.0,
        rvol=1.2,         # passes trend threshold (1.0) but not normal (1.5)
        regime="BULL",
    )
    signal = await trend_entry.generate(ctx)
    assert signal is not None
    assert signal.metadata["trend_mode"] is True
    assert signal.metadata["breakout_type"] == "close"


@pytest.mark.asyncio
async def test_trend_mode_inactive_in_bear(trend_entry):
    """Trend mode does not activate in BEAR regime."""
    ctx = _make_trend_context(
        close=50000.0,
        high_5=49900.0,
        rvol=1.2,   # would pass trend threshold but not normal
        regime="BEAR",
    )
    signal = await trend_entry.generate(ctx)
    assert signal is None  # RVOL 1.2 < normal 1.5


@pytest.mark.asyncio
async def test_trend_mode_ema_pullback_requires_alignment(trend_entry):
    """EMA pullback trigger requires ema_aligned=True."""
    ctx = _make_trend_context(
        close=49950.0,
        high_5=50500.0,   # no breakout
        rvol=1.2,
        atr=600.0,
        rsi=50.0,
        ema_5=49900.0,
        ema_20=49600.0,
        ema_60=49200.0,
        ema_aligned=False,  # NOT aligned
        regime="BULL",
    )
    signal = await trend_entry.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_trend_mode_ema_pullback_requires_rsi_above_min(trend_entry):
    """EMA pullback trigger requires RSI > trend_rsi_min (40)."""
    ctx = _make_trend_context(
        close=49950.0,
        high_5=50500.0,
        rvol=1.2,
        atr=600.0,
        rsi=35.0,   # below trend_rsi_min (40)
        ema_5=49900.0,
        ema_20=49600.0,
        ema_60=49200.0,
        ema_aligned=True,
        regime="BULL",
    )
    signal = await trend_entry.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_trend_mode_exit_overrides_in_metadata(trend_entry):
    """Trend mode signal includes exit parameter overrides in metadata."""
    ctx = _make_trend_context(
        close=50000.0,
        high_5=49900.0,
        rvol=1.2,
        regime="BULL",
    )
    signal = await trend_entry.generate(ctx)
    assert signal is not None
    assert signal.metadata["exit_stop_atr_multiplier"] == 2.5
    assert signal.metadata["exit_trail_activation_atr"] == 1.5
    assert signal.metadata["exit_trail_atr_multiplier"] == 2.5
    assert signal.metadata["exit_max_hold_days"] == 15
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/strategy/test_momentum_breakout_entry.py -k "trend_mode" -v`
Expected: FAIL — no trend_mode logic in generate()

**Step 3: Implement trend mode entry logic**

In `shared/strategy/entry/momentum_breakout.py`, modify `MomentumBreakoutEntry`:

1. Update `required_indicators` to include EMA fields:
```python
    @property
    def required_indicators(self) -> list[str]:
        return ["close", "high_5", "rvol", "volume", "volume_ma", "atr",
                "ema_5", "ema_20", "ema_60", "ema_aligned", "rsi"]
```

2. In `generate()`, after the cooldown check and minimum edge filter, add trend mode detection:
```python
        # --- Detect trend mode ---
        is_trend_mode = (
            self.config.trend_mode_enabled
            and context.metadata.get("regime") in self.config.trend_mode_regimes
        )
```

3. Replace the hardcoded RVOL/buffer/cooldown values with trend-mode-aware versions. Before the breakout trigger section:
```python
        # --- Effective parameters (trend mode overrides) ---
        if is_trend_mode:
            effective_rvol_threshold = self.config.trend_rvol_threshold
            effective_breakout_buffer = self.config.trend_breakout_buffer_pct
            effective_cooldown = self.config.trend_signal_cooldown_seconds
        else:
            effective_rvol_threshold = self.config.rvol_threshold
            effective_breakout_buffer = self.config.breakout_buffer_pct
            effective_cooldown = self.config.signal_cooldown_seconds
```

4. Update cooldown check to use `effective_cooldown` (move the trend mode detection before cooldown, or apply effective_cooldown in the cooldown section).

5. Update breakout threshold to use `effective_breakout_buffer`.

6. Update RVOL check to use `effective_rvol_threshold`.

7. After the breakout trigger section (where `trigger_type` is determined), add EMA pullback:
```python
        # --- EMA pullback trigger (trend mode only) ---
        if (
            is_trend_mode
            and trigger_type is None
            and self.config.trend_ema_pullback_enabled
        ):
            trigger_type = self._check_ema_pullback(close, atr, indicators)
```

8. Add exit overrides to signal metadata when in trend mode:
```python
        metadata = {
            "signal_direction": "long",
            "stop_loss": stop_loss_price,
            "atr": atr,
            "rvol": rvol,
            "high_5": high_5,
            "breakout_pct": breakout_pct,
            "breakout_type": breakout_type if trigger_type != "ema_pullback" else "ema_pullback",
            "trigger": trigger_type,
            "trend_mode": is_trend_mode,
        }
        if is_trend_mode:
            metadata.update({
                "exit_stop_atr_multiplier": self.config.trend_exit_stop_atr_multiplier,
                "exit_trail_activation_atr": self.config.trend_exit_trail_activation_atr,
                "exit_trail_atr_multiplier": self.config.trend_exit_trail_atr_multiplier,
                "exit_max_hold_days": self.config.trend_exit_max_hold_days,
            })
```

9. Add `_check_ema_pullback` method:
```python
    def _check_ema_pullback(
        self, close: float, atr: float, indicators: dict
    ) -> Optional[str]:
        """Check EMA pullback trigger conditions.

        Returns "ema_pullback" if all conditions met, else None.
        Conditions:
        1. ema_aligned = True (EMA5 > EMA20 > EMA60)
        2. close near EMA20: |close - ema_20| <= ATR * ema_touch_buffer_atr
        3. close > ema_5 (bounce confirmed)
        4. RSI > trend_rsi_min
        """
        ema_aligned = indicators.get("ema_aligned", False)
        if not ema_aligned:
            return None

        ema_mid = float(indicators.get(f"ema_{self.config.trend_ema_mid}", 0) or 0)
        ema_fast = float(indicators.get(f"ema_{self.config.trend_ema_fast}", 0) or 0)
        if ema_mid <= 0 or ema_fast <= 0:
            return None

        # Pullback location: close near EMA20
        if atr > 0 and abs(close - ema_mid) > atr * self.config.trend_ema_touch_buffer_atr:
            return None

        # Bounce confirmation: close > EMA5
        if close <= ema_fast:
            return None

        # RSI health check
        rsi = float(indicators.get("rsi", 50) or 50)
        if rsi < self.config.trend_rsi_min:
            return None

        return "ema_pullback"
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/strategy/test_momentum_breakout_entry.py -v`
Expected: All tests PASS (existing + new trend mode tests)

**Step 5: Commit**

```bash
git add shared/strategy/entry/momentum_breakout.py tests/unit/strategy/test_momentum_breakout_entry.py
git commit -m "feat: implement trend mode entry logic with EMA pullback trigger"
```

---

### Task 4: Add position.metadata exit overrides to ATRDynamicExit

**Files:**
- Modify: `shared/strategy/exit/atr_dynamic.py` (_check_position method)
- Test: `tests/unit/strategy/test_atr_dynamic_exit_overrides.py` (create)

**Step 1: Write the failing test**

Create `tests/unit/strategy/test_atr_dynamic_exit_overrides.py`:

```python
"""Test ATRDynamicExit position.metadata overrides for trend mode."""

import pytest
from datetime import datetime, timedelta, timezone
from shared.models.position import Position, PositionSide, PositionState
from shared.strategy.exit.atr_dynamic import ATRDynamicExit, ATRDynamicExitConfig

KST = timezone(timedelta(hours=9))


def _make_position(
    entry_price=50000.0,
    current_price=50000.0,
    highest_price=50000.0,
    metadata=None,
    entry_minutes_ago=60,
) -> Position:
    now = datetime(2026, 3, 2, 11, 0, tzinfo=KST)
    return Position(
        id="test-pos-1",
        code="005930",
        name="삼성전자",
        side=PositionSide.LONG,
        quantity=10,
        entry_price=entry_price,
        entry_time=now - timedelta(minutes=entry_minutes_ago),
        current_price=current_price,
        highest_price=highest_price,
        lowest_price=entry_price * 0.98,
        stop_price=entry_price * 0.95,
        state=PositionState.SURVIVAL,
        metadata=metadata or {},
    )


def test_exit_uses_metadata_stop_override():
    """ATRDynamicExit uses exit_stop_atr_multiplier from position.metadata."""
    config = ATRDynamicExitConfig(stop_atr_multiplier=2.0)
    exit_strategy = ATRDynamicExit(config)

    # Position with trend mode exit override: wider stop (3.0 instead of 2.0)
    pos = _make_position(
        entry_price=50000.0,
        current_price=49000.0,  # -2% loss
        metadata={"exit_stop_atr_multiplier": 3.0},
    )
    # ATR = 500 (1% of 50000, delivered as normalized 0.01 or absolute)
    snapshot = {"close": 49000.0, "atr": 500.0}
    now = datetime(2026, 3, 2, 11, 0, tzinfo=KST)

    # With config stop (2.0): stop_distance = 500*2.0 = 1000, stop_pct = -2%
    # loss = -2% exactly at stop → triggers
    # With metadata override (3.0): stop_distance = 500*3.0 = 1500, stop_pct = -3%
    # loss = -2% < 3% → does NOT trigger
    signal = exit_strategy._check_position(pos, snapshot, now)
    assert signal is None  # wider stop from metadata prevents exit


def test_exit_uses_metadata_trail_override():
    """ATRDynamicExit uses exit_trail_atr_multiplier from position.metadata."""
    config = ATRDynamicExitConfig(
        trail_activation_atr=1.0,
        trail_atr_multiplier=1.5,
        stop_atr_multiplier=5.0,  # wide stop so it doesn't interfere
    )
    exit_strategy = ATRDynamicExit(config)

    # Position peaked at 51000, now at 50200 (trailing from peak)
    pos = _make_position(
        entry_price=50000.0,
        current_price=50200.0,
        highest_price=51000.0,
        # Override: wider trail (3.0 instead of 1.5)
        metadata={"exit_trail_atr_multiplier": 3.0},
    )
    snapshot = {"close": 50200.0, "atr": 500.0}
    now = datetime(2026, 3, 2, 11, 0, tzinfo=KST)

    # Trail activated: peak (51000) >= entry (50000) + 500*1.0 = 50500 ✓
    # Config trail stop: 51000 - 500*1.5 = 50250 → current 50200 < 50250 → TRIGGERS
    # Metadata trail stop: 51000 - 500*3.0 = 49500 → current 50200 > 49500 → NO TRIGGER
    signal = exit_strategy._check_position(pos, snapshot, now)
    assert signal is None  # wider trail from metadata prevents exit


def test_exit_uses_metadata_max_hold_override():
    """ATRDynamicExit uses exit_max_hold_days from position.metadata."""
    config = ATRDynamicExitConfig(
        max_hold_days=8,
        stop_atr_multiplier=5.0,
    )
    exit_strategy = ATRDynamicExit(config)

    # Position held for 10 days
    pos = _make_position(
        entry_price=50000.0,
        current_price=50500.0,
        highest_price=50500.0,
        entry_minutes_ago=10 * 24 * 60,  # 10 days
        metadata={"exit_max_hold_days": 15},
    )
    snapshot = {"close": 50500.0, "atr": 500.0}
    now = datetime(2026, 3, 2, 11, 0, tzinfo=KST)

    # Config max_hold=8 → 10 days > 8 → TRIGGERS
    # Metadata max_hold=15 → 10 days < 15 → NO TRIGGER
    signal = exit_strategy._check_position(pos, snapshot, now)
    assert signal is None  # extended hold from metadata


def test_exit_falls_back_to_config_without_metadata():
    """Without metadata overrides, ATRDynamicExit uses config values."""
    config = ATRDynamicExitConfig(stop_atr_multiplier=2.0)
    exit_strategy = ATRDynamicExit(config)

    # No metadata override
    pos = _make_position(
        entry_price=50000.0,
        current_price=49000.0,  # -2% loss
        metadata={},
    )
    snapshot = {"close": 49000.0, "atr": 500.0}
    now = datetime(2026, 3, 2, 11, 0, tzinfo=KST)

    # stop_distance = 500*2.0 = 1000, stop_pct = -2%
    # loss = -2% at stop → triggers
    signal = exit_strategy._check_position(pos, snapshot, now)
    assert signal is not None
    assert signal.reason.value == "stop_loss"
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/strategy/test_atr_dynamic_exit_overrides.py -v`
Expected: First test FAILS (metadata override not read, uses config stop → triggers exit)

**Step 3: Implement metadata overrides**

In `shared/strategy/exit/atr_dynamic.py`, modify `_check_position()`. At the top of the method (after getting `high_since_entry`), add:

```python
        # Read per-position exit parameter overrides (from trend mode entry signal)
        pos_meta = position.metadata or {}
        stop_mult = pos_meta.get("exit_stop_atr_multiplier", self.config.stop_atr_multiplier)
        trail_act = pos_meta.get("exit_trail_activation_atr", self.config.trail_activation_atr)
        trail_mult = pos_meta.get("exit_trail_atr_multiplier", self.config.trail_atr_multiplier)
        max_hold = pos_meta.get("exit_max_hold_days", self.config.max_hold_days)
```

Then replace all references in the method:
- `self.config.stop_atr_multiplier` → `stop_mult`
- `self.config.trail_activation_atr` → `trail_act`
- `self.config.trail_atr_multiplier` → `trail_mult`
- `self.config.max_hold_days` → `max_hold`

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/strategy/test_atr_dynamic_exit_overrides.py -v`
Expected: All 4 tests PASS

**Step 5: Run all existing tests to verify no regressions**

Run: `.venv/bin/pytest tests/ -v --timeout=60 -x`
Expected: All PASS

**Step 6: Commit**

```bash
git add shared/strategy/exit/atr_dynamic.py tests/unit/strategy/test_atr_dynamic_exit_overrides.py
git commit -m "feat: add position.metadata exit parameter overrides to ATRDynamicExit"
```

---

### Task 5: Update YAML config and run full test suite

**Files:**
- Modify: `config/strategies/stock/momentum_breakout.yaml`
- Run: Full test suite

**Step 1: Update YAML config**

Add trend mode section to `config/strategies/stock/momentum_breakout.yaml` under `entry.params`:

```yaml
      # Trend mode (activated when regime in BULL/SIDEWAYS_UP)
      trend_mode_enabled: true
      trend_mode_regimes: ["BULL", "SIDEWAYS_UP"]
      trend_rvol_threshold: 1.0
      trend_breakout_buffer_pct: 0.0
      trend_signal_cooldown_seconds: 60
      # EMA pullback trigger
      trend_ema_pullback_enabled: true
      trend_ema_fast: 5
      trend_ema_mid: 20
      trend_ema_slow: 60
      trend_ema_touch_buffer_atr: 1.0
      trend_rsi_min: 40.0
      # Exit overrides for trend mode positions
      trend_exit_stop_atr_multiplier: 2.5
      trend_exit_trail_activation_atr: 1.5
      trend_exit_trail_atr_multiplier: 2.5
      trend_exit_max_hold_days: 15
```

**Step 2: Run full test suite**

Run: `.venv/bin/pytest tests/ -v --timeout=60`
Expected: All PASS

**Step 3: Commit**

```bash
git add config/strategies/stock/momentum_breakout.yaml
git commit -m "feat: enable trend mode in momentum_breakout YAML config"
```

---

### Task 6: Create feature branch and PR

**Step 1: Verify all changes**

Run: `git log --oneline -5` to review commits.

**Step 2: Push and create PR**

```bash
git push -u origin feat/momentum-breakout-trend-mode
gh pr create --title "feat: momentum_breakout trend mode for bull markets" --body "..."
```

Note: All work should be on a feature branch per project rules (never commit directly to main).
