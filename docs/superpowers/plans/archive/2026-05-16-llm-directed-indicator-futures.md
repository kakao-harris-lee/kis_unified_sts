# LLM-Directed Indicator Futures Strategy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single composite futures strategy where a periodic LLM directional bias gates a fast 3-family indicator ensemble for entry, with a composite indicator exit — succeeding RL_mppo's primary role.

**Architecture:** Approach A from `docs/superpowers/specs/2026-05-16-llm-directed-indicator-futures-design.md`. LLM `market_context` (already injected by strategy_manager) → bias mapper → directional mask. 3 directional family scorers (momentum-reversal, trend/breakout, volume/microstructure) → weighted ensemble; 1 volatility-regime modulator raises the effective threshold. Composite exit reuses `ATRDynamicExit` + `MomentumDecayExit`. Only hard gate = high-confidence LLM mask; every missing input degrades to a *reduced* signal, never zero (this session's #249/#252/#257/#258 failure-mode lessons).

**Tech Stack:** Python 3.11, existing `shared/strategy` registry + `EntrySignalGenerator`/`ExitSignalGenerator` ABCs, `ConfigMixin` dataclass config, pytest, Redis (`shared.streaming.client.RedisClient`), forecasting `VolForecast`.

---

## File Structure

**Create:**
- `shared/strategy/signals/__init__.py` — new package marker
- `shared/strategy/signals/indicator_families.py` — 4 pure scorer functions
- `shared/forecasting/vol_reader.py` — `read_latest_vol_forecast()` (mirrors macro reader)
- `shared/strategy/entry/llm_directed_indicator.py` — `LLMDirectedIndicatorConfig`, `_map_llm_bias`, `LLMDirectedIndicatorEntry`
- `shared/strategy/exit/llm_directed_indicator_exit.py` — `LLMDirectedIndicatorExitConfig`, `LLMDirectedIndicatorExit`
- `config/strategies/futures/llm_directed_indicator.yaml` — strategy config, `enabled: false`
- `tests/unit/strategy/signals/__init__.py`
- `tests/unit/strategy/signals/test_indicator_families.py`
- `tests/unit/forecasting/test_vol_reader.py`
- `tests/unit/strategy/entry/test_llm_directed_indicator.py`
- `tests/unit/strategy/exit/test_llm_directed_indicator_exit.py`

**Modify:**
- `shared/strategy/registry.py` — register entry + exit in `register_builtin_components()`

---

## Task 1: Volatility forecast reader

**Files:**
- Create: `shared/forecasting/vol_reader.py`
- Test: `tests/unit/forecasting/test_vol_reader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/forecasting/test_vol_reader.py
from datetime import UTC, datetime

from shared.forecasting.models import VolForecast
from shared.forecasting.vol_reader import read_latest_vol_forecast


class _FakeRedis:
    def __init__(self, value):
        self._value = value

    def get(self, key):  # noqa: ARG002
        return self._value


def _vf_json() -> str:
    return VolForecast(
        asof=datetime(2026, 5, 16, 0, 0, tzinfo=UTC),
        horizon_minutes=15,
        forecast_pct=18.5,
        forecast_atr_equivalent=1.2,
        regime_percentile=72.0,
        model_version="har_rv_v1",
        confidence=0.4,
    ).to_json()


def test_returns_none_when_key_absent():
    assert read_latest_vol_forecast(_FakeRedis(None)) is None


def test_returns_none_on_garbage():
    assert read_latest_vol_forecast(_FakeRedis("not-json")) is None


def test_parses_vol_forecast():
    vf = read_latest_vol_forecast(_FakeRedis(_vf_json()))
    assert vf is not None
    assert vf.regime_percentile == 72.0
    assert vf.forecast_atr_equivalent == 1.2


def test_redis_error_returns_none():
    class _Boom:
        def get(self, key):  # noqa: ARG002
            raise RuntimeError("redis down")

    assert read_latest_vol_forecast(_Boom()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/forecasting/test_vol_reader.py -q`
Expected: FAIL with `ModuleNotFoundError: shared.forecasting.vol_reader`

- [ ] **Step 3: Write minimal implementation**

```python
# shared/forecasting/vol_reader.py
"""Read the latest VolForecast from Redis (inverse of forecast_publisher).

Mirrors shared.macro.base.read_latest_macro_snapshot: never raises, returns
None on absent/garbage/redis-error so trading hot paths degrade gracefully.
"""
from __future__ import annotations

import logging
from typing import Any

from shared.forecasting.models import VolForecast

logger = logging.getLogger(__name__)

# Must match shared.forecasting.forecast_publisher._VOL_KEY.
_VOL_KEY = "forecast:vol:current"


def read_latest_vol_forecast(redis_client: Any) -> VolForecast | None:
    try:
        blob = redis_client.get(_VOL_KEY)
    except Exception as exc:  # noqa: BLE001 — hot path, never propagate
        logger.debug("vol forecast read failed: %s", exc)
        return None
    if not blob:
        return None
    try:
        return VolForecast.from_json(blob)
    except Exception as exc:  # noqa: BLE001
        logger.debug("vol forecast parse failed: %s", exc)
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/forecasting/test_vol_reader.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add shared/forecasting/vol_reader.py tests/unit/forecasting/test_vol_reader.py
git commit -m "feat(forecasting): read_latest_vol_forecast Redis reader"
```

---

## Task 2: Indicator family scorers

**Files:**
- Create: `shared/strategy/signals/__init__.py`, `shared/strategy/signals/indicator_families.py`
- Test: `tests/unit/strategy/signals/__init__.py`, `tests/unit/strategy/signals/test_indicator_families.py`

Scorers are pure: `(indicators: dict) -> float`. Inputs reuse existing
indicator-engine keys. Missing/invalid input → neutral (0.0) contribution,
never raises (failure-mode policy §5).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/signals/test_indicator_families.py
from shared.strategy.signals.indicator_families import (
    momentum_reversal_score,
    trend_breakout_score,
    volatility_regime_magnitude,
    volume_microstructure_score,
)


def test_momentum_missing_inputs_neutral():
    assert momentum_reversal_score({}) == 0.0


def test_momentum_oversold_is_long_positive():
    ind = {"momentum_5m": {"rsi": 10.0, "williams_r": -95.0, "sto_k": 5.0}}
    s = momentum_reversal_score(ind)
    assert 0.5 < s <= 1.0  # deep oversold → strong long-reversal


def test_momentum_overbought_is_short_negative():
    ind = {"momentum_5m": {"rsi": 90.0, "williams_r": -5.0, "sto_k": 95.0}}
    assert -1.0 <= momentum_reversal_score(ind) < -0.5


def test_trend_missing_neutral():
    assert trend_breakout_score({}) == 0.0


def test_trend_up_alignment_positive():
    ind = {"ema_5": 102.0, "ema_20": 100.0, "adx": 40.0,
           "vwap": 99.0, "close": 103.0}
    assert trend_breakout_score(ind) > 0.4


def test_trend_down_alignment_negative():
    ind = {"ema_5": 98.0, "ema_20": 100.0, "adx": 40.0,
           "vwap": 101.0, "close": 97.0}
    assert trend_breakout_score(ind) < -0.4


def test_trend_weak_adx_damped():
    strong = {"ema_5": 102.0, "ema_20": 100.0, "adx": 50.0,
              "vwap": 99.0, "close": 103.0}
    weak = {"ema_5": 102.0, "ema_20": 100.0, "adx": 5.0,
            "vwap": 99.0, "close": 103.0}
    assert abs(trend_breakout_score(weak)) < abs(trend_breakout_score(strong))


def test_volume_missing_neutral():
    assert volume_microstructure_score({}) == 0.0


def test_volume_up_flow_positive():
    ind = {"volume_velocity": 0.8, "rvol": 2.0, "vwap": 100.0,
           "close": 101.0}
    assert volume_microstructure_score(ind) > 0.3


def test_volume_low_rvol_damped():
    hi = {"volume_velocity": 0.8, "rvol": 2.0, "vwap": 100.0, "close": 101.0}
    lo = {"volume_velocity": 0.8, "rvol": 0.2, "vwap": 100.0, "close": 101.0}
    assert abs(volume_microstructure_score(lo)) < abs(
        volume_microstructure_score(hi))


def test_vol_regime_missing_is_zero():
    assert volatility_regime_magnitude({}, None) == 0.0


def test_vol_regime_from_forecast_percentile():
    class _VF:
        regime_percentile = 80.0

    assert volatility_regime_magnitude({}, _VF()) == 0.8


def test_vol_regime_atr_fallback_when_no_forecast():
    ind = {"atr": 2.0, "close": 100.0}  # atr/close = 2% → high
    m = volatility_regime_magnitude(ind, None)
    assert 0.0 < m <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/signals/test_indicator_families.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# shared/strategy/signals/__init__.py
```

```python
# shared/strategy/signals/indicator_families.py
"""Pure indicator-family scorers for LLMDirectedIndicatorEntry.

3 directional scorers → float in [-1, +1] (+ = long bias, - = short bias).
1 volatility scorer → magnitude in [0, 1] (regime selectivity modulator).

Contract: every scorer returns 0.0 (neutral) on missing/invalid input and
never raises — the entry strategy must degrade to a reduced signal, never
to a structural zero (design spec §5).
"""
from __future__ import annotations

from typing import Any


def _f(d: dict, key: str) -> float | None:
    try:
        v = d.get(key)
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _clip(x: float) -> float:
    return max(-1.0, min(1.0, x))


def momentum_reversal_score(indicators: dict[str, Any]) -> float:
    """Oversold → +1 (long reversal), overbought → -1. Avg of available
    RSI / Williams %R / Stochastic %K, each mapped so midpoint = 0."""
    mom = indicators.get("momentum_5m")
    if not isinstance(mom, dict):
        return 0.0
    parts: list[float] = []
    rsi = _f(mom, "rsi")
    if rsi is not None:
        parts.append((50.0 - rsi) / 50.0)
    wr = _f(mom, "williams_r")  # range -100..0; -50 = midpoint
    if wr is not None:
        parts.append((-50.0 - wr) / 50.0)
    k = _f(mom, "sto_k")
    if k is not None:
        parts.append((50.0 - k) / 50.0)
    if not parts:
        return 0.0
    return _clip(sum(parts) / len(parts))


def trend_breakout_score(indicators: dict[str, Any]) -> float:
    """EMA fast/slow alignment scaled by ADX strength, VWAP-side confirm."""
    ema_f = _f(indicators, "ema_5")
    ema_s = _f(indicators, "ema_20")
    if ema_f is None or ema_s is None or ema_s == 0.0:
        return 0.0
    raw = (ema_f - ema_s) / abs(ema_s)            # signed trend
    direction = _clip(raw * 50.0)                 # ~2% spread saturates
    adx = _f(indicators, "adx")
    strength = min(1.0, (adx or 0.0) / 40.0)      # ADX>=40 → full
    score = direction * strength
    vwap = _f(indicators, "vwap")
    close = _f(indicators, "close")
    if vwap is not None and close is not None and vwap != 0.0:
        confirm = 0.2 if (close > vwap) == (score >= 0) else -0.2
        score = _clip(score + confirm)
    return _clip(score)


def volume_microstructure_score(indicators: dict[str, Any]) -> float:
    """Volume-velocity direction, damped by rvol, VWAP-deviation confirm."""
    vel = _f(indicators, "volume_velocity")
    if vel is None:
        return 0.0
    rvol = _f(indicators, "rvol")
    gate = min(1.0, (rvol if rvol is not None else 1.0))  # rvol<1 damps
    base = _clip(vel) * gate
    vwap = _f(indicators, "vwap")
    close = _f(indicators, "close")
    if vwap is not None and close is not None and vwap != 0.0:
        dev = _clip(((close - vwap) / abs(vwap)) * 50.0)
        base = _clip(0.5 * base + 0.5 * dev * gate)
    return _clip(base)


def volatility_regime_magnitude(
    indicators: dict[str, Any], vol_forecast: Any | None
) -> float:
    """Non-directional [0,1]. Prefer HAR-RV regime_percentile; else ATR/close
    (2%+ intraday ATR ≈ high-vol regime)."""
    if vol_forecast is not None:
        try:
            pct = float(vol_forecast.regime_percentile)
            return max(0.0, min(1.0, pct / 100.0))
        except (TypeError, ValueError, AttributeError):
            pass
    atr = _f(indicators, "atr")
    close = _f(indicators, "close")
    if atr is None or close is None or close == 0.0:
        return 0.0
    return max(0.0, min(1.0, (atr / close) / 0.02))
```

```python
# tests/unit/strategy/signals/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/signals/test_indicator_families.py -q`
Expected: PASS (13 passed)

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/signals tests/unit/strategy/signals
git commit -m "feat(signals): 4 indicator-family scorers (3 directional + 1 vol modulator)"
```

---

## Task 3: Bias mapper + entry config

**Files:**
- Create: `shared/strategy/entry/llm_directed_indicator.py` (config + `_map_llm_bias` only this task)
- Test: `tests/unit/strategy/entry/test_llm_directed_indicator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/entry/test_llm_directed_indicator.py
from shared.llm.data_classes import MarketSignal
from shared.llm.market_context import MarketContext
from shared.strategy.entry.llm_directed_indicator import (
    LLMDirectedIndicatorConfig,
    _map_llm_bias,
)


def _cfg(**kw) -> LLMDirectedIndicatorConfig:
    base = dict(bias_confidence_min=0.6)
    base.update(kw)
    return LLMDirectedIndicatorConfig(**base)


def test_none_context_is_flat():
    assert _map_llm_bias(None, _cfg()) == "FLAT"


def test_low_confidence_is_flat():
    mc = MarketContext(overall_signal=MarketSignal.STRONG_BULLISH,
                        confidence=0.3)
    assert _map_llm_bias(mc, _cfg()) == "FLAT"


def test_confident_bullish_is_long_bias():
    mc = MarketContext(overall_signal=MarketSignal.BULLISH, confidence=0.8)
    assert _map_llm_bias(mc, _cfg()) == "LONG_BIAS"


def test_confident_bearish_is_short_bias():
    mc = MarketContext(overall_signal=MarketSignal.STRONG_BEARISH,
                        confidence=0.9)
    assert _map_llm_bias(mc, _cfg()) == "SHORT_BIAS"


def test_confident_neutral_is_flat():
    mc = MarketContext(overall_signal=MarketSignal.NEUTRAL, confidence=0.9)
    assert _map_llm_bias(mc, _cfg()) == "FLAT"


def test_mask_mode_defaults_hard():
    # spec §7: ship the switch (hard only implemented; soft = future Path B)
    assert _cfg().mask_mode == "hard"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_llm_directed_indicator.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# shared/strategy/entry/llm_directed_indicator.py
"""LLM-directed indicator composite entry (futures) — succeeds RL_mppo.

Design: docs/superpowers/specs/2026-05-16-llm-directed-indicator-futures-design.md
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from shared.config.mixins import ConfigMixin

logger = logging.getLogger(__name__)


@dataclass
class LLMDirectedIndicatorConfig(ConfigMixin):
    """Config for LLMDirectedIndicatorEntry."""

    # Bias mapper
    bias_confidence_min: float = 0.6  # LLM confidence below → FLAT
    # Evolution hook (spec §7 Path B). "hard" = directional mask (Approach
    # A, the only behavior implemented here). "soft" is reserved for the
    # future soft-modulation path and is NOT implemented in this plan —
    # the switch is shipped so Path B needs no schema change later.
    mask_mode: str = "hard"

    # Ensemble weights (3 directional families)
    w_momentum: float = 0.34
    w_trend: float = 0.33
    w_volume: float = 0.33
    entry_threshold: float = 0.30          # |ensemble| floor
    vol_threshold_mult: float = 0.5        # eff_thr = thr*(1+mult*vol_mag)

    # Market-hours (futures, KST)
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 45
    skip_market_open_minutes: int = 15
    skip_market_close_minutes: int = 30
    signal_cooldown_seconds: int = 180

    # Risk
    stop_loss_pct: float = 3.0


def _map_llm_bias(
    market_context: Any | None, config: LLMDirectedIndicatorConfig
) -> str:
    """Map LLM MarketContext → 'LONG_BIAS' | 'SHORT_BIAS' | 'FLAT'.

    None / low-confidence / non-directional → FLAT (indicators run
    standalone — NEVER no-trade; design spec §2 decision #2).
    """
    if market_context is None:
        return "FLAT"
    try:
        conf = float(getattr(market_context, "confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return "FLAT"
    if conf < config.bias_confidence_min:
        return "FLAT"
    is_bull = getattr(market_context, "is_bullish", None)
    is_bear = getattr(market_context, "is_bearish", None)
    if callable(is_bull) and is_bull():
        return "LONG_BIAS"
    if callable(is_bear) and is_bear():
        return "SHORT_BIAS"
    return "FLAT"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_llm_directed_indicator.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/entry/llm_directed_indicator.py tests/unit/strategy/entry/test_llm_directed_indicator.py
git commit -m "feat(entry): LLMDirectedIndicatorConfig + _map_llm_bias"
```

---

## Task 4: Entry strategy generate()

**Files:**
- Modify: `shared/strategy/entry/llm_directed_indicator.py` (add `LLMDirectedIndicatorEntry`)
- Test: `tests/unit/strategy/entry/test_llm_directed_indicator.py` (append)

- [ ] **Step 1: Write the failing test (append to existing test file)**

```python
# append to tests/unit/strategy/entry/test_llm_directed_indicator.py
import pytest
from datetime import datetime, timedelta, timezone

from shared.strategy.base import EntryContext
from shared.strategy.entry.llm_directed_indicator import (
    LLMDirectedIndicatorEntry,
)

KST = timezone(timedelta(hours=9))


def _entry(**kw):
    return LLMDirectedIndicatorEntry(_cfg(signal_cooldown_seconds=0, **kw))


def _ctx(*, mom_rsi=10.0, ema_f=103.0, ema_s=100.0, adx=45.0,
         vwap=99.0, close=103.0, vel=0.8, rvol=2.0, atr=0.5,
         mc=None, hour=10, minute=30):
    now = datetime(2026, 5, 18, hour, minute, tzinfo=KST)
    return EntryContext(
        market_data={"code": "101S6000", "name": "KF", "close": close},
        indicators={
            "momentum_5m": {"rsi": mom_rsi, "williams_r": -95.0,
                            "sto_k": 5.0},
            "ema_5": ema_f, "ema_20": ema_s, "adx": adx,
            "vwap": vwap, "close": close,
            "volume_velocity": vel, "rvol": rvol, "atr": atr,
        },
        timestamp=now,
        market_context=mc,
    )


@pytest.mark.asyncio
async def test_flat_bias_long_signal_fires():
    sig = await _entry().generate(_ctx())   # bullish indicators, FLAT bias
    assert sig is not None
    assert sig.metadata["signal_direction"] == "long"


@pytest.mark.asyncio
async def test_long_bias_blocks_short_signal():
    from shared.llm.data_classes import MarketSignal
    from shared.llm.market_context import MarketContext
    mc = MarketContext(overall_signal=MarketSignal.STRONG_BULLISH,
                        confidence=0.9)
    # bearish indicators (overbought + downtrend) → would be short
    sig = await _entry().generate(_ctx(
        mom_rsi=90.0, ema_f=97.0, ema_s=100.0, vwap=101.0, close=97.0,
        vel=-0.8, mc=mc))
    assert sig is None  # LONG_BIAS masks the short


@pytest.mark.asyncio
async def test_below_threshold_no_signal():
    # flat-ish indicators → |ensemble| < entry_threshold
    sig = await _entry(entry_threshold=0.95).generate(_ctx())
    assert sig is None


@pytest.mark.asyncio
async def test_outside_market_hours_no_signal():
    sig = await _entry().generate(_ctx(hour=8, minute=0))
    assert sig is None


@pytest.mark.asyncio
async def test_missing_indicators_degrades_not_raises():
    now = datetime(2026, 5, 18, 10, 30, tzinfo=KST)
    ctx = EntryContext(market_data={"code": "X", "close": 100.0},
                       indicators={}, timestamp=now)
    sig = await _entry().generate(ctx)  # all scores 0 → no signal, no raise
    assert sig is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_llm_directed_indicator.py -q`
Expected: FAIL with `ImportError: cannot import name 'LLMDirectedIndicatorEntry'`

- [ ] **Step 3: Add implementation (append to llm_directed_indicator.py)**

```python
# append to shared/strategy/entry/llm_directed_indicator.py
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.signals.indicator_families import (
    momentum_reversal_score,
    trend_breakout_score,
    volatility_regime_magnitude,
    volume_microstructure_score,
)

_KST = ZoneInfo("Asia/Seoul")


class LLMDirectedIndicatorEntry(EntrySignalGenerator[LLMDirectedIndicatorConfig]):
    """LLM bias-masked 3-family indicator ensemble entry (futures)."""

    CONFIG_CLASS = LLMDirectedIndicatorConfig

    def __init__(self, config: LLMDirectedIndicatorConfig):
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}
        self._vol_cache: Any = None
        self._vol_cache_mono: float = 0.0

    def _validate_config(self):
        assert self.config.entry_threshold > 0, "entry_threshold > 0"
        assert 0.0 <= self.config.bias_confidence_min <= 1.0

    @property
    def name(self) -> str:
        return "llm_directed_indicator"

    @property
    def required_indicators(self) -> list[str]:
        return ["momentum_5m", "ema_5", "ema_20", "adx", "vwap",
                "volume_velocity", "rvol", "atr"]

    def _get_vol_forecast(self) -> Any | None:
        import time as _t
        now = _t.monotonic()
        if self._vol_cache is not None and now - self._vol_cache_mono < 60.0:
            return self._vol_cache
        try:
            from shared.forecasting.vol_reader import read_latest_vol_forecast
            from shared.streaming.client import RedisClient

            vf = read_latest_vol_forecast(RedisClient.get_client())
        except Exception as exc:  # noqa: BLE001 — never break entry loop
            logger.debug("vol forecast fetch failed: %s", exc)
            vf = None
        self._vol_cache = vf
        self._vol_cache_mono = now
        return vf

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        data = context.market_data or {}
        ind = context.indicators or {}
        code = str(data.get("code", "") or "BACKTEST")
        close = float(data.get("close", ind.get("close", 0)) or 0)
        if close <= 0:
            return None

        now = context.timestamp
        now_kst = (now.astimezone(_KST) if now.tzinfo is not None
                   else now.replace(tzinfo=_KST))
        c = self.config
        open_dt = datetime.combine(
            now_kst.date(), time(c.market_open_hour, c.market_open_minute),
            tzinfo=_KST)
        close_dt = datetime.combine(
            now_kst.date(), time(c.market_close_hour, c.market_close_minute),
            tzinfo=_KST)
        if now_kst < open_dt + timedelta(minutes=c.skip_market_open_minutes):
            return None
        if now_kst >= close_dt - timedelta(
                minutes=c.skip_market_close_minutes):
            return None
        if c.signal_cooldown_seconds > 0:
            last = self._last_signal_at.get(code)
            if last and (now - last).total_seconds() < (
                    c.signal_cooldown_seconds):
                return None

        bias = _map_llm_bias(context.market_context, c)

        ind_for_score = dict(ind)
        ind_for_score.setdefault("close", close)
        m = momentum_reversal_score(ind_for_score)
        t = trend_breakout_score(ind_for_score)
        v = volume_microstructure_score(ind_for_score)
        vol_mag = volatility_regime_magnitude(
            ind_for_score, self._get_vol_forecast())

        ensemble = c.w_momentum * m + c.w_trend * t + c.w_volume * v
        eff_threshold = c.entry_threshold * (1.0 + c.vol_threshold_mult
                                             * vol_mag)
        direction = "long" if ensemble > 0 else "short"

        trace = (f"bias={bias} m={m:.2f} t={t:.2f} v={v:.2f} "
                 f"vol={vol_mag:.2f} ens={ensemble:.3f} "
                 f"eff_thr={eff_threshold:.3f} dir={direction}")

        if bias == "LONG_BIAS" and direction == "short":
            logger.info("[llm_directed] masked short | %s", trace)
            return None
        if bias == "SHORT_BIAS" and direction == "long":
            logger.info("[llm_directed] masked long | %s", trace)
            return None
        if abs(ensemble) < eff_threshold:
            logger.info("[llm_directed] below thr | %s", trace)
            return None

        llm_conf = 0.5
        if context.market_context is not None:
            try:
                llm_conf = float(getattr(
                    context.market_context, "confidence", 0.5) or 0.5)
            except (TypeError, ValueError):
                llm_conf = 0.5
        confidence = max(0.1, min(1.0,
                                  0.5 * min(1.0, abs(ensemble))
                                  + 0.5 * llm_conf))

        logger.info("[llm_directed] ENTER %s | %s", direction.upper(), trace)
        self._last_signal_at[code] = now
        return Signal(
            code=code,
            name=str(data.get("name", "") or ""),
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy="llm_directed_indicator",
            confidence=confidence,
            metadata={
                "signal_direction": direction,
                "stop_loss_pct": float(c.stop_loss_pct),
                "ensemble": ensemble,
                "llm_bias": bias,
            },
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_llm_directed_indicator.py -q`
Expected: PASS (11 passed — 6 prior + 5 new)

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/entry/llm_directed_indicator.py tests/unit/strategy/entry/test_llm_directed_indicator.py
git commit -m "feat(entry): LLMDirectedIndicatorEntry generate() with bias mask + ensemble"
```

---

## Task 5: Composite exit

**Files:**
- Create: `shared/strategy/exit/llm_directed_indicator_exit.py`
- Test: `tests/unit/strategy/exit/test_llm_directed_indicator_exit.py`

Composite reuses `ATRDynamicExit` (trailing + hard-stop + EOD) and
`MomentumDecayExit` (momentum exhaustion). Evaluate both per position;
return the higher-priority fire (lower `priority` int wins, matching the
existing exit convention).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/exit/test_llm_directed_indicator_exit.py
import pytest
from datetime import datetime, timedelta, timezone

from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.llm_directed_indicator_exit import (
    LLMDirectedIndicatorExit,
    LLMDirectedIndicatorExitConfig,
)

KST = timezone(timedelta(hours=9))


def _pos(side=PositionSide.LONG, entry=300.0):
    return Position(
        id="p1", code="101S6000", name="KF", side=side, quantity=1,
        entry_price=entry, entry_time=datetime(2026, 5, 18, 10, 0,
                                               tzinfo=KST),
        current_price=entry, highest_price=entry, lowest_price=entry,
        state=PositionState.SURVIVAL, strategy="llm_directed_indicator")


def _exit():
    return LLMDirectedIndicatorExit(LLMDirectedIndicatorExitConfig())


def _ctx(pos, price, hour=10, minute=30):
    now = datetime(2026, 5, 18, hour, minute, tzinfo=KST)
    return ExitContext(
        position=pos,
        market_data={pos.code: {"close": price, "price": price}},
        indicators={"momentum_5m": {"williams_r": -50.0}},
        timestamp=now, metadata={"is_backtest": True})


@pytest.mark.asyncio
async def test_hard_stop_fires():
    p = _pos(entry=300.0)
    should, sig = await _exit().should_exit(_ctx(p, 285.0))  # -5%
    assert should is True
    assert sig.reason == ExitReason.STOP_LOSS


@pytest.mark.asyncio
async def test_no_exit_when_flat_and_in_range():
    p = _pos(entry=300.0)
    should, _ = await _exit().should_exit(_ctx(p, 300.5, hour=10,
                                               minute=30))
    assert should is False


@pytest.mark.asyncio
async def test_scan_positions_returns_list():
    p = _pos(entry=300.0)
    sigs = await _exit().scan_positions(
        [p], {p.code: {"close": 285.0, "price": 285.0}})
    assert isinstance(sigs, list)
    assert len(sigs) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/exit/test_llm_directed_indicator_exit.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# shared/strategy/exit/llm_directed_indicator_exit.py
"""Composite exit for the LLM-directed indicator strategy.

Reuses ATRDynamicExit (trailing + hard-stop + EOD) and MomentumDecayExit
(momentum exhaustion). Both are evaluated per position; the highest
priority signal (lowest priority int) is returned. Hard-stop + EOD are
inherent to ATRDynamicExit and are independent safety nets the composite
never suppresses (design spec §5).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from shared.config.mixins import ConfigMixin
from shared.models.position import Position
from shared.models.signal import ExitSignal
from shared.strategy.base import (
    ExitContext,
    ExitSignalGenerator,
    MarketStateProtocol,
)
from shared.strategy.exit.atr_dynamic import (
    ATRDynamicExit,
    ATRDynamicExitConfig,
)
from shared.strategy.exit.momentum_decay import (
    MomentumDecayConfig,
    MomentumDecayExit,
)

logger = logging.getLogger(__name__)


@dataclass
class LLMDirectedIndicatorExitConfig(ConfigMixin):
    """Sub-exit configs (defaults mirror each exit's own defaults)."""

    atr: dict[str, Any] = field(default_factory=dict)
    momentum_decay: dict[str, Any] = field(default_factory=dict)


class LLMDirectedIndicatorExit(
    ExitSignalGenerator[LLMDirectedIndicatorExitConfig]
):
    CONFIG_CLASS = LLMDirectedIndicatorExitConfig
    NAME = "LLM_DIRECTED_INDICATOR_EXIT"

    def __init__(self, config: LLMDirectedIndicatorExitConfig):
        super().__init__(config)
        self._atr = ATRDynamicExit(
            ATRDynamicExitConfig(**(config.atr or {})))
        self._mom = MomentumDecayExit(
            MomentumDecayConfig(**(config.momentum_decay or {})))

    def _validate_config(self):
        pass

    @property
    def name(self) -> str:
        return "llm_directed_indicator_exit"

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, Optional[ExitSignal]]:
        candidates: list[ExitSignal] = []
        for sub in (self._atr, self._mom):
            try:
                fired, sig = await sub.should_exit(context)
                if fired and sig is not None:
                    candidates.append(sig)
            except Exception as exc:  # noqa: BLE001 — isolate sub-exit
                logger.debug("sub-exit %s raised: %s", sub.name, exc)
        if not candidates:
            return (False, None)
        best = min(candidates, key=lambda s: getattr(s, "priority", 99))
        return (True, best)

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: Optional[MarketStateProtocol] = None,
    ) -> list[ExitSignal]:
        from shared.strategy.market_data import get_symbol_snapshot
        from shared.strategy.market_time import now_kst

        out: list[ExitSignal] = []
        now = now_kst()
        for p in positions:
            snap = get_symbol_snapshot(market_data, p.code)
            ctx = ExitContext(position=p, market_data=snap,
                              indicators=snap, timestamp=now,
                              market_state=market_state)
            fired, sig = await self.should_exit(ctx)
            if fired and sig is not None:
                out.append(sig)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/exit/test_llm_directed_indicator_exit.py -q`
Expected: PASS (3 passed). If `ATRDynamicExitConfig`/`MomentumDecayConfig` kwargs differ, inspect each config dataclass and align the test's expectation; the composite logic itself is config-agnostic.

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/exit/llm_directed_indicator_exit.py tests/unit/strategy/exit/test_llm_directed_indicator_exit.py
git commit -m "feat(exit): LLMDirectedIndicatorExit composite (ATR + momentum_decay)"
```

---

## Task 6: Registry registration

**Files:**
- Modify: `shared/strategy/registry.py` (in `register_builtin_components()`, near the `williams_r` registration ~line 382 / exit ~line 457)
- Test: `tests/unit/strategy/entry/test_llm_directed_indicator.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
# append to tests/unit/strategy/entry/test_llm_directed_indicator.py
def test_registered_in_registry():
    from shared.strategy.registry import (
        EntryRegistry,
        ExitRegistry,
        register_builtin_components,
    )
    register_builtin_components()
    assert "llm_directed_indicator" in EntryRegistry.available()
    assert "llm_directed_indicator_exit" in ExitRegistry.available()
```

(If `EntryRegistry.available()` does not exist, use the registry's actual
introspection method — check `shared/strategy/registry.py` for the
public listing API, e.g. `_registry` keys or `is_registered`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_llm_directed_indicator.py::test_registered_in_registry -q`
Expected: FAIL (not registered)

- [ ] **Step 3: Add registration**

In `shared/strategy/registry.py`, inside `register_builtin_components()`,
add next to the existing `williams_r` entry registration block:

```python
        try:
            from shared.strategy.entry.llm_directed_indicator import (
                LLMDirectedIndicatorEntry,
            )

            EntryRegistry.register_class(
                "llm_directed_indicator", LLMDirectedIndicatorEntry)
        except ImportError:
            logger.debug("LLMDirectedIndicatorEntry not available")
```

and next to the existing `williams_r_exit` registration block:

```python
        try:
            from shared.strategy.exit.llm_directed_indicator_exit import (
                LLMDirectedIndicatorExit,
            )

            ExitRegistry.register_class(
                "llm_directed_indicator_exit", LLMDirectedIndicatorExit)
        except ImportError:
            logger.debug("LLMDirectedIndicatorExit not available")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_llm_directed_indicator.py -q`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/registry.py tests/unit/strategy/entry/test_llm_directed_indicator.py
git commit -m "feat(registry): register llm_directed_indicator entry + exit"
```

---

## Task 7: Strategy YAML config + factory load

**Files:**
- Create: `config/strategies/futures/llm_directed_indicator.yaml`
- Test: `tests/unit/strategy/entry/test_llm_directed_indicator.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
# append to tests/unit/strategy/entry/test_llm_directed_indicator.py
def test_yaml_loads_via_factory():
    from shared.strategy.registry import (
        StrategyFactory,
        register_builtin_components,
    )
    register_builtin_components()
    s = StrategyFactory.create_from_file("futures",
                                         "llm_directed_indicator")
    assert s.name == "llm_directed_indicator"
    assert s.entry.config.bias_confidence_min == 0.6
    assert s.exit.config is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_llm_directed_indicator.py::test_yaml_loads_via_factory -q`
Expected: FAIL (`FileNotFoundError` strategy yaml)

- [ ] **Step 3: Write the config**

```yaml
# config/strategies/futures/llm_directed_indicator.yaml
# LLM-directed indicator composite (futures) — succeeds RL_mppo.
# Design: docs/superpowers/specs/2026-05-16-llm-directed-indicator-futures-design.md
# enabled: false until backtest Sharpe>1.0/PF>1.2 gate passes (spec §6).

strategy:
  name: llm_directed_indicator
  asset_class: futures
  enabled: false
  description: >
    Periodic LLM directional bias masks a 3-family fast indicator
    ensemble (momentum-reversal / trend-breakout / volume-microstructure);
    a volatility-regime modulator raises the entry threshold. Composite
    exit reuses ATR-dynamic + momentum-decay. Succeeds RL_mppo primary.

  entry:
    type: llm_directed_indicator
    params:
      bias_confidence_min: 0.6
      w_momentum: 0.34
      w_trend: 0.33
      w_volume: 0.33
      entry_threshold: 0.30
      vol_threshold_mult: 0.5
      market_open_hour: 9
      market_open_minute: 0
      market_close_hour: 15
      market_close_minute: 45
      skip_market_open_minutes: 15
      skip_market_close_minutes: 30
      signal_cooldown_seconds: 180
      stop_loss_pct: 3.0

  exit:
    type: llm_directed_indicator_exit
    params:
      atr: {}
      momentum_decay: {}

  position:
    type: fixed
    params:
      max_positions: 1
      order_amount_per_stock: 1000000
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_llm_directed_indicator.py -q`
Expected: PASS (13 passed). If `StrategyFactory.create_from_file` signature differs, mirror `tests/unit/strategy/test_williams_r_futures.py::TestFuturesConfigLoads`.

- [ ] **Step 5: Commit**

```bash
git add config/strategies/futures/llm_directed_indicator.yaml tests/unit/strategy/entry/test_llm_directed_indicator.py
git commit -m "feat(config): llm_directed_indicator futures strategy yaml (enabled=false)"
```

---

## Task 8: Backtest FLAT-bias contract verification + regression

**Files:**
- Test: `tests/unit/strategy/entry/test_llm_directed_indicator.py` (append)

The backtest contract (spec §4(a)): with `market_context=None` the mask is
FLAT, so the strategy runs indicators-only — exactly the backtest path
(BacktestStrategyAdapter does not inject `market_context`). This task
verifies that contract and runs the regression suite.

- [ ] **Step 1: Write the failing test (append)**

```python
# append to tests/unit/strategy/entry/test_llm_directed_indicator.py
@pytest.mark.asyncio
async def test_backtest_flat_contract_indicators_only():
    """No market_context (backtest) → FLAT → indicators alone decide.
    Bullish indicators must still produce a long (no LLM gate)."""
    e = _entry()
    sig = await e.generate(_ctx(mc=None))
    assert sig is not None
    assert sig.metadata["llm_bias"] == "FLAT"
    assert sig.metadata["signal_direction"] == "long"
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_llm_directed_indicator.py::test_backtest_flat_contract_indicators_only -q`
Expected: PASS (the FLAT contract is already implemented in Task 4; this
test pins it as a regression guard).

- [ ] **Step 3: Run the full affected regression suite**

Run:
```bash
source .venv/bin/activate && pytest \
  tests/unit/strategy/signals/ \
  tests/unit/forecasting/test_vol_reader.py \
  tests/unit/strategy/entry/test_llm_directed_indicator.py \
  tests/unit/strategy/exit/test_llm_directed_indicator_exit.py \
  tests/unit/test_williams_r_entry.py tests/unit/test_williams_r_exit.py \
  tests/integration/test_orchestrator_flow.py -p no:warnings -q
```
Expected: all PASS, no regressions in williams_r / orchestrator.

- [ ] **Step 4: Run a smoke backtest (manual verification, not a unit test)**

Run:
```bash
source .venv/bin/activate && timeout 280 sts backtest run \
  -s llm_directed_indicator -a futures \
  -d data/kospi200f_1m_ch_101S6000.csv --no-track 2>&1 | tail -30
```
Expected: backtest completes; **trades > 0** (FLAT-bias indicators-only
path produces signals — confirms no structural-zero defect). Record
Sharpe/PF/MDD for the Optuna baseline. (Performance tuning is the next,
separate effort — this plan only delivers a *functioning* strategy.)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/strategy/entry/test_llm_directed_indicator.py
git commit -m "test(entry): pin backtest FLAT-bias indicators-only contract"
```

---

## Task 9: Documentation update

**Files:**
- Modify: `CLAUDE.md` (등록된 진입/청산 전략 tables), `docs/PROJECT_STATUS.md` (Active Strategies note)

- [ ] **Step 1: Update CLAUDE.md strategy tables**

Add to the "등록된 진입 전략" table:

```markdown
| `llm_directed_indicator` | `LLMDirectedIndicatorEntry` | LLM 주기 방향 마스크 + 3지표군 앙상블 (선물, RL_mppo 승계, enabled=false 백테스트 게이트 전) |
```

Add to the "등록된 청산 전략" table:

```markdown
| `llm_directed_indicator_exit` | `LLMDirectedIndicatorExit` | ATR-dynamic + momentum_decay 합성 (선물) |
```

- [ ] **Step 2: Update docs/PROJECT_STATUS.md Active Strategies**

In the Futures rows, add:

```markdown
| Futures | `llm_directed_indicator` | **설계 완료, 미활성** | enabled=false. 백테스트 Sharpe>1.0/PF>1.2 게이트 → paper-primary. RL_mppo 승계. spec: 2026-05-16-llm-directed-indicator-futures-design.md |
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/PROJECT_STATUS.md
git commit -m "docs: register llm_directed_indicator in CLAUDE.md + PROJECT_STATUS"
```

---

## Done Criteria

- All unit suites pass (signals, vol_reader, entry, exit, registry, yaml).
- williams_r / orchestrator regression green.
- Smoke backtest on 101S6000 produces **> 0 trades** (no structural zero).
- `enabled: false` — activation is a separate Optuna+gate effort (spec §6).
- CLAUDE.md / PROJECT_STATUS updated.

## Out of Scope (separate efforts, per spec)

- Optuna parameter optimization + the Sharpe>1.0/PF>1.2 gate decision.
- Flipping `enabled: true` / paper-primary cutover.
- Approach B (`mask_mode: soft`) / Approach C (hierarchical) — spec §7.
- Backtest LLM-bias replay (spec §4(b) future fidelity upgrade).
