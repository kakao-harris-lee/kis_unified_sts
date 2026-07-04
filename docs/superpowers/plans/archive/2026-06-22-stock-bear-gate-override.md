# Stock Bear-Gate Per-Symbol Override Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let individually-strong stocks bypass the blanket market bear gate on both sides (M4-P entry skip + M4-X BEAR_EXIT), via a per-symbol "strong" set M4-P publishes to Redis and both sides consult (staleness-gated, fail-safe).

**Architecture:** New pure strength module + a Redis override contract mirroring `shared/streaming/stock_regime.py`. M4-P computes the strong set from `system:daily_indicators:latest`, publishes it, and in a bear cycle evaluates only strong+warm symbols (capped). M4-X loads the set (staleness-gated) and skips BEAR_EXIT for strong symbols.

**Tech Stack:** Python 3.12, asyncio, pytest. Spec: `docs/superpowers/specs/2026-06-22-stock-bear-gate-per-symbol-override-design.md`.

**Branch:** `feat/stock-bear-gate-override` (spec committed at 7328443).

## Global Constraints
- Config-driven: thresholds/limits in `config/stock_bear_override.yaml`; none hardcoded in branches.
- Fail-safe to normal bear behavior: strength-compute/publish failure or stale/missing/malformed override → empty strong set → entry stays blocked AND M4-X bear-exit fires normally. Never exempt on bad/stale data. Positive-form age bound (`if not 0 <= age <= max: return set()`) rejects NaN — same invariant as `parse_market_state`.
- `enabled` code-default **False** ⇒ zero behavior change vs main; paper YAML enables.
- Override only acts in BEAR regime; non-bear cycles unchanged. Long-only preserved; no new EOD liquidation.
- KST trading logic preserved (epoch-ms timestamps, tz-agnostic). Redis DB 1; new key gets a TTL.
- Best-effort: M4-P override path never raises out of `evaluate_once`. DRY, YAGNI, TDD, frequent commits. Tests via `.venv/bin/pytest`. Feature branch only.

## File Structure
- `shared/strategy/symbol_strength.py` (NEW) — pure strength predicate/set.
- `shared/streaming/stock_bear_override.py` (NEW) — `BearOverrideConfig` + publish/parse (staleness), mirrors `stock_regime.py`.
- `config/stock_bear_override.yaml` (NEW).
- `services/stock_strategy/daemon.py` (MODIFY) — compute+publish strong set; bear branch evaluates strong+warm, capped, tagged.
- `shared/strategy/exit/three_stage.py` (MODIFY) — `scan_positions`/`_check_position` accept `bear_override_symbols`; skip BEAR_EXIT for those.
- `services/stock_exit/daemon.py` + `main.py` (MODIFY) — `_load_bear_override` + wire into `scan_positions`.

---

### Task 1: `symbol_strength.py` — pure strength predicate

**Files:**
- Create: `shared/strategy/symbol_strength.py`
- Test: `tests/unit/strategy/test_symbol_strength.py`

**Interfaces:**
- Produces: `StrengthCriteria` (frozen dataclass: `rsi_min: float=55.0`, `require_above_sma20: bool=True`, `require_rsi_rising: bool=True`, `require_macd_positive: bool=True`); `is_strong(daily: dict, criteria) -> bool`; `compute_strong_symbols(indicators_by_code: dict[str, dict], criteria) -> set[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/test_symbol_strength.py
from shared.strategy.symbol_strength import (
    StrengthCriteria, compute_strong_symbols, is_strong,
)

_STRONG = {  # SK하이닉스-like
    "daily_close": 100.0, "daily_sma_20": 90.0,
    "daily_rsi_14": 74.0, "daily_prev_rsi_14": 70.0, "daily_macd_hist": 120.0,
}

def test_all_conditions_met_is_strong():
    assert is_strong(_STRONG, StrengthCriteria()) is True

def test_below_sma20_not_strong():
    assert is_strong({**_STRONG, "daily_close": 80.0}, StrengthCriteria()) is False

def test_rsi_below_min_not_strong():
    assert is_strong({**_STRONG, "daily_rsi_14": 50.0}, StrengthCriteria()) is False

def test_rsi_not_rising_not_strong():
    assert is_strong({**_STRONG, "daily_rsi_14": 60.0, "daily_prev_rsi_14": 65.0}, StrengthCriteria()) is False

def test_macd_not_positive_not_strong():
    assert is_strong({**_STRONG, "daily_macd_hist": -1.0}, StrengthCriteria()) is False

def test_missing_field_not_strong():
    assert is_strong({"daily_close": 100.0}, StrengthCriteria()) is False

def test_nan_field_not_strong():
    assert is_strong({**_STRONG, "daily_rsi_14": float("nan")}, StrengthCriteria()) is False

def test_compute_strong_symbols_filters():
    weak = {**_STRONG, "daily_close": 80.0}
    out = compute_strong_symbols({"AAA": _STRONG, "BBB": weak}, StrengthCriteria())
    assert out == {"AAA"}

def test_criteria_toggles_relax():
    # disabling RSI-rising lets a non-rising-but-otherwise-strong symbol pass
    c = StrengthCriteria(require_rsi_rising=False)
    s = {**_STRONG, "daily_rsi_14": 60.0, "daily_prev_rsi_14": 65.0}
    assert is_strong(s, c) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/strategy/test_symbol_strength.py -v`
Expected: FAIL `ImportError: cannot import name 'StrengthCriteria'`.

- [ ] **Step 3: Write minimal implementation**

```python
# shared/strategy/symbol_strength.py
"""Per-symbol trend-strength predicate for the bear-gate override.

A symbol is "strong" (worth evaluating / exempt from blanket bear logic) when
its daily trend is confirmed-up by a multi-factor AND. Inputs are the
``system:daily_indicators:latest`` per-symbol fields. Pure + side-effect-free.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class StrengthCriteria:
    rsi_min: float = 55.0
    require_above_sma20: bool = True
    require_rsi_rising: bool = True
    require_macd_positive: bool = True


def _finite(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def is_strong(daily: dict, criteria: StrengthCriteria) -> bool:
    """True iff all enabled trend conditions hold. Missing/NaN field → False."""
    close = _finite(daily.get("daily_close"))
    sma20 = _finite(daily.get("daily_sma_20"))
    rsi = _finite(daily.get("daily_rsi_14"))
    prev_rsi = _finite(daily.get("daily_prev_rsi_14"))
    macd = _finite(daily.get("daily_macd_hist"))

    if rsi is None or rsi < criteria.rsi_min:
        return False
    if criteria.require_above_sma20 and (close is None or sma20 is None or close <= sma20):
        return False
    if criteria.require_rsi_rising and (prev_rsi is None or rsi <= prev_rsi):
        return False
    if criteria.require_macd_positive and (macd is None or macd <= 0):
        return False
    return True


def compute_strong_symbols(
    indicators_by_code: dict[str, dict], criteria: StrengthCriteria
) -> set[str]:
    """Return the set of codes whose daily indicators satisfy ``is_strong``."""
    return {
        code
        for code, daily in (indicators_by_code or {}).items()
        if isinstance(daily, dict) and is_strong(daily, criteria)
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/strategy/test_symbol_strength.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/symbol_strength.py tests/unit/strategy/test_symbol_strength.py
git commit -m "feat(bear-override): per-symbol trend-strength predicate"
```

---

### Task 2: `stock_bear_override.py` contract + config

**Files:**
- Create: `shared/streaming/stock_bear_override.py`
- Create: `config/stock_bear_override.yaml`
- Test: `tests/unit/streaming/test_stock_bear_override.py`

**Interfaces:**
- Consumes: `StrengthCriteria` (Task 1).
- Produces: `BearOverrideConfig` (frozen: `enabled=False`, `redis_key="stock:daemon:bear_override"`, `publish_ttl_seconds=900`, `max_age_seconds=300.0`, `max_override_positions=3`, `daily_indicators_key="system:daily_indicators:latest"`, + criteria fields `rsi_min/require_above_sma20/require_rsi_rising/require_macd_positive`; `load()` defaults-on-failure; `.criteria` property → `StrengthCriteria`); `compute_override_payload(strong: set[str], *, now_ms: int) -> dict`; `parse_strong_set(raw, *, config, now_ms) -> set[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/streaming/test_stock_bear_override.py
import json
from shared.streaming.stock_bear_override import (
    BearOverrideConfig, compute_override_payload, parse_strong_set,
)

def test_defaults():
    c = BearOverrideConfig()
    assert c.enabled is False
    assert c.redis_key == "stock:daemon:bear_override"
    assert c.max_age_seconds == 300.0
    assert c.max_override_positions == 3
    assert c.criteria.rsi_min == 55.0

def test_payload_round_trip_fresh():
    cfg = BearOverrideConfig()
    payload = compute_override_payload({"AAA", "BBB"}, now_ms=1_000_000)
    raw = json.dumps(payload)
    out = parse_strong_set(raw, config=cfg, now_ms=1_000_000 + 1000)  # 1s old
    assert out == {"AAA", "BBB"}

def test_stale_payload_returns_empty():
    cfg = BearOverrideConfig()
    payload = compute_override_payload({"AAA"}, now_ms=1_000_000)
    raw = json.dumps(payload)
    out = parse_strong_set(raw, config=cfg, now_ms=1_000_000 + 400_000)  # 400s > 300
    assert out == set()

def test_missing_or_malformed_returns_empty():
    cfg = BearOverrideConfig()
    assert parse_strong_set(None, config=cfg, now_ms=1) == set()
    assert parse_strong_set("not json", config=cfg, now_ms=1) == set()
    assert parse_strong_set(json.dumps({"strong": ["A"]}), config=cfg, now_ms=1) == set()  # no computed_at_ms

def test_nan_age_returns_empty():
    cfg = BearOverrideConfig()
    raw = json.dumps({"strong": ["A"], "computed_at_ms": float("nan")})
    assert parse_strong_set(raw, config=cfg, now_ms=1_000) == set()

def test_load_defaults_on_missing(monkeypatch):
    from shared.config import loader as loader_mod
    monkeypatch.setattr(loader_mod.ConfigLoader, "load", staticmethod(lambda _f: {}))
    assert BearOverrideConfig.load().enabled is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/streaming/test_stock_bear_override.py -v`
Expected: FAIL `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
# shared/streaming/stock_bear_override.py
"""Per-symbol bear-gate override contract (M4-P → Redis → M4-X).

Mirrors shared/streaming/stock_regime.py: M4-P computes the set of individually
strong symbols and publishes it; M4-P's entry skip and M4-X's BEAR_EXIT both
consume it with staleness gating. Stale/missing/malformed/NaN → empty set, so
the system fails safe to normal blanket-bear behavior (never exempt on bad data).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from shared.strategy.symbol_strength import StrengthCriteria

logger = logging.getLogger(__name__)

_CONFIG_FILE = "stock_bear_override.yaml"
_CONFIG_SECTION = "stock_bear_override"


@dataclass(frozen=True)
class BearOverrideConfig:
    enabled: bool = False
    redis_key: str = "stock:daemon:bear_override"
    publish_ttl_seconds: int = 900
    max_age_seconds: float = 300.0
    max_override_positions: int = 3
    daily_indicators_key: str = "system:daily_indicators:latest"
    rsi_min: float = 55.0
    require_above_sma20: bool = True
    require_rsi_rising: bool = True
    require_macd_positive: bool = True

    @property
    def criteria(self) -> StrengthCriteria:
        return StrengthCriteria(
            rsi_min=self.rsi_min,
            require_above_sma20=self.require_above_sma20,
            require_rsi_rising=self.require_rsi_rising,
            require_macd_positive=self.require_macd_positive,
        )

    @classmethod
    def load(cls) -> "BearOverrideConfig":
        try:
            from shared.config.loader import ConfigLoader

            raw = ConfigLoader.load(_CONFIG_FILE).get(_CONFIG_SECTION, {})
            return cls(
                enabled=bool(raw.get("enabled", cls.enabled)),
                redis_key=str(raw.get("redis_key", cls.redis_key)),
                publish_ttl_seconds=int(raw.get("publish_ttl_seconds", cls.publish_ttl_seconds)),
                max_age_seconds=float(raw.get("max_age_seconds", cls.max_age_seconds)),
                max_override_positions=int(raw.get("max_override_positions", cls.max_override_positions)),
                daily_indicators_key=str(raw.get("daily_indicators_key", cls.daily_indicators_key)),
                rsi_min=float(raw.get("rsi_min", cls.rsi_min)),
                require_above_sma20=bool(raw.get("require_above_sma20", cls.require_above_sma20)),
                require_rsi_rising=bool(raw.get("require_rsi_rising", cls.require_rsi_rising)),
                require_macd_positive=bool(raw.get("require_macd_positive", cls.require_macd_positive)),
            )
        except Exception:
            logger.warning("stock_bear_override.yaml load failed; using defaults")
            return cls()


def compute_override_payload(strong: set[str], *, now_ms: int) -> dict[str, Any]:
    codes = sorted(strong)
    return {"strong": codes, "count": len(codes), "computed_at_ms": now_ms}


def parse_strong_set(raw: Any, *, config: BearOverrideConfig, now_ms: int) -> set[str]:
    """Decode a published payload to a strong-symbol set, or ∅ on any problem.

    Positive-form staleness bound rejects NaN, stale, and future timestamps.
    """
    if raw is None:
        return set()
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return set()
    if not isinstance(payload, dict):
        return set()
    computed_at_ms = payload.get("computed_at_ms")
    strong = payload.get("strong")
    if not isinstance(computed_at_ms, (int, float)) or not isinstance(strong, list):
        return set()
    age_seconds = (now_ms - float(computed_at_ms)) / 1000.0
    if not 0.0 <= age_seconds <= config.max_age_seconds:
        return set()
    return {str(c) for c in strong}
```

```yaml
# config/stock_bear_override.yaml
stock_bear_override:
  enabled: false              # paper env enables; code default off = no behavior change
  redis_key: "stock:daemon:bear_override"
  publish_ttl_seconds: 900
  max_age_seconds: 300.0      # staleness gate (consumer); stale → normal bear behavior
  max_override_positions: 3   # cap on concurrent override-eligible open positions
  daily_indicators_key: "system:daily_indicators:latest"
  rsi_min: 55.0
  require_above_sma20: true
  require_rsi_rising: true
  require_macd_positive: true
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/streaming/test_stock_bear_override.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/streaming/stock_bear_override.py config/stock_bear_override.yaml tests/unit/streaming/test_stock_bear_override.py
git commit -m "feat(bear-override): Redis override contract + config (mirrors stock_regime)"
```

---

### Task 3: M4-P — compute/publish strong set + bear-branch override entries

**Files:**
- Modify: `services/stock_strategy/daemon.py`
- Test: `tests/unit/stock_strategy/test_daemon.py` (append)

**Interfaces:**
- Consumes: `BearOverrideConfig` (Task 2), `compute_strong_symbols` (Task 1), `compute_override_payload` (Task 2), `stock_daemon_positions_key` (existing).
- Produces: in a bear cycle with override enabled + non-empty strong set, `evaluate_once` evaluates only `strong ∩ warm` symbols (≤ cap), tags signals `metadata["bear_override"]=True`, and publishes the strong set. Non-bear and disabled → unchanged.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/stock_strategy/test_daemon.py
import json as _json
import pytest
from shared.streaming.stock_bear_override import BearOverrideConfig


def _bear_payload():
    return _json.dumps({"regime": "BEAR_STRONG", "mfi": 28.0, "mfi_symbols": 9,
                        "computed_at_ms": 1, "low_confidence": False})


@pytest.mark.asyncio
async def test_bear_cycle_evaluates_only_strong_when_override_enabled(monkeypatch):
    # regime publish returns BEAR; daily indicators make only 005930 strong
    daily = {"indicators": {
        "005930": {"daily_close": 100, "daily_sma_20": 90, "daily_rsi_14": 70,
                   "daily_prev_rsi_14": 65, "daily_macd_hist": 5},
        "066570": {"daily_close": 80, "daily_sma_20": 90, "daily_rsi_14": 40,
                   "daily_prev_rsi_14": 45, "daily_macd_hist": -3},
    }}
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = _json.dumps(daily)
    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930", "066570")),
        manager=_FakeManager(fire_for=("005930", "066570")),
        regime_config=StockRegimeConfig(),
        bear_override_config=BearOverrideConfig(enabled=True),
    )
    daemon._universe = ["005930", "066570"]
    # force bear regime
    monkeypatch.setattr(daemon, "_publish_regime", _async_return(_json.loads(_bear_payload())))
    published = await daemon.evaluate_once()
    # only the strong symbol (005930) was evaluated/published, not 066570
    assert published == 1
    codes = [f.get("code") for _s, f in redis.added]
    assert codes == ["005930"]
    # strong set published
    assert "stock:daemon:bear_override" in redis.kv


@pytest.mark.asyncio
async def test_bear_cycle_disabled_override_still_blocks(monkeypatch):
    daemon = _daemon(regime_config=StockRegimeConfig(), bear_override_config=BearOverrideConfig(enabled=False))
    daemon._universe = ["005930"]
    monkeypatch.setattr(daemon, "_publish_regime", _async_return(_json.loads(_bear_payload())))
    assert await daemon.evaluate_once() == 0  # unchanged blanket block
```

(Add a tiny `_async_return(value)` helper at top of the test module: `def _async_return(v):\n    async def _f(*a, **k): return v\n    return _f`. Reuse the existing `_FakeRedis`/`_FakeEngine`/`_FakeManager`; `_FakeRedis.get` must return `self.kv.get(key)`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_strategy/test_daemon.py -k override -v`
Expected: FAIL — `__init__` has no `bear_override_config`.

- [ ] **Step 3: Write minimal implementation**

In `services/stock_strategy/daemon.py`:
- Imports:
```python
from shared.streaming.stock_bear_override import (
    BearOverrideConfig, compute_override_payload,
)
from shared.strategy.symbol_strength import compute_strong_symbols
from shared.streaming.stock_keys import stock_daemon_positions_key
```
- `__init__`: add `bear_override_config: BearOverrideConfig | None = None`; store `self._bear_override_config = bear_override_config`.
- New helper `async def _publish_strong_set(self, now) -> set[str]`:
```python
    async def _publish_strong_set(self, now: datetime) -> set[str]:
        cfg = self._bear_override_config
        if cfg is None or not cfg.enabled:
            return set()
        try:
            raw = await self.redis.get(cfg.daily_indicators_key)
            indicators = json.loads(raw).get("indicators", {}) if raw else {}
            strong = compute_strong_symbols(indicators, cfg.criteria)
        except Exception:
            logger.exception("strong-set compute failed")
            return set()
        try:
            payload = compute_override_payload(strong, now_ms=int(now.timestamp() * 1000))
            await self.redis.set(cfg.redis_key, json.dumps(payload), ex=cfg.publish_ttl_seconds)
        except Exception:
            logger.exception("strong-set publish failed")
        return strong
```
- New helper `async def _override_count(self, strong) -> int` (open positions in strong set):
```python
    async def _override_count(self, strong: set[str]) -> int:
        try:
            open_codes = await self.redis.hkeys(stock_daemon_positions_key())
        except Exception:
            logger.exception("positions hash read failed; treating cap as reached")
            return 1 << 30  # force cap-reached → no new override entries (conservative)
        decoded = {(c.decode() if isinstance(c, (bytes, bytearray)) else str(c)) for c in (open_codes or [])}
        return len(decoded & strong)
```
- In `evaluate_once`, replace the bear branch (`return 0`) with:
```python
        is_bear = (
            regime_payload is not None
            and self._regime_config is not None
            and self._regime_config.block_entries_in_bear
            and is_bear_regime(regime_payload.get("regime"))
        )
        strong = await self._publish_strong_set(now) if (
            self._bear_override_config and self._bear_override_config.enabled
        ) else set()
        override_codes: set[str] = set()
        if is_bear:
            if not strong:
                logger.info("bear regime %s — skipping entry evaluation",
                            regime_payload.get("regime"))
                return 0
            cap = self._bear_override_config.max_override_positions
            if await self._override_count(strong) >= cap:
                logger.info("bear override: cap %d reached — no new override entries", cap)
                return 0
            override_codes = strong
            logger.info("bear override: %d strong — evaluating %s",
                        len(strong), sorted(strong))
        # symbol loop:
        for symbol in list(self._universe):
            if is_bear and symbol not in override_codes:
                continue
            ...  # existing is_warm / market_data / check_entries body unchanged
            #     when is_bear, tag each emitted signal: sig.metadata["bear_override"]=True (best-effort)
```
Tagging: before `await self._publish(sig)`, if `is_bear` and the Signal supports metadata, set the flag; otherwise skip (best-effort; the tag is observability only).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_strategy/test_daemon.py -v`
Expected: PASS (existing + new). Confirm `_FakeRedis` has `get`, `hkeys`, `set` (add `async def hkeys(self,k): return []` and `async def get(self,k): return self.kv.get(k)` if missing).

- [ ] **Step 5: Commit**

```bash
git add services/stock_strategy/daemon.py tests/unit/stock_strategy/test_daemon.py
git commit -m "feat(bear-override): M4-P publishes strong set + evaluates strong-only in bear (capped)"
```

---

### Task 4: M4-X — `ThreeStageExit` skips BEAR_EXIT for override symbols

**Files:**
- Modify: `shared/strategy/exit/three_stage.py`
- Test: `tests/unit/stock_exit/` or existing three_stage test (append)

**Interfaces:**
- Produces: `scan_positions(..., bear_override_symbols: set[str] | None = None)` threads the set to `_check_position(..., bear_override_symbols)`, which skips the BEAR_EXIT branch when `position.code in bear_override_symbols`. Default `None` → today's behavior.

- [ ] **Step 1: Write the failing test** — locate the existing three_stage bear-exit test first:

Run: `grep -rln "BEAR_EXIT\|enable_bear_exit\|scan_positions" tests/ | head`. Add a test in that file:
```python
def test_bear_exit_skipped_for_override_symbol(...):
    # position in a bear market that IS in bear_override_symbols → NOT BEAR_EXIT;
    # falls through to normal stage/stop. A non-override position in the same
    # scan → BEAR_EXIT. (Construct two positions; assert reasons.)
```
Mirror the existing bear-exit test's setup (market_state bear, enable_bear_exit=True). Use the real `ThreeStageExit` with two positions, pass `bear_override_symbols={strong_code}`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest <that test file> -k override -v`
Expected: FAIL — `scan_positions`/`_check_position` has no `bear_override_symbols`.

- [ ] **Step 3: Write minimal implementation**

In `shared/strategy/exit/three_stage.py`:
- `scan_positions(self, positions, market_data, *, market_state=None, bear_override_symbols=None)` — pass it through to each `_check_position` call. (Match the existing signature; add the keyword param with default None.)
- `_check_position(..., bear_override_symbols: set[str] | None = None)` — change the bear branch (line ~418):
```python
        # 2. BEAR 시장 체크 (per-symbol override 면제)
        overridden = bool(bear_override_symbols) and position.code in bear_override_symbols
        if self.config.enable_bear_exit and self._is_bear_market(market_state) and not overridden:
            return self._create_exit_signal(... reason=ExitReason.BEAR_EXIT ...)
```
(Leave EOD priority-1 check above it unchanged; override does NOT exempt EOD.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest <that test file> -v`
Expected: PASS. Confirm existing three_stage tests still green (default None path unchanged).

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/exit/three_stage.py tests/<that test file>
git commit -m "feat(bear-override): ThreeStageExit skips BEAR_EXIT for override symbols"
```

---

### Task 5: M4-X daemon/main — load override set + wire into scan_positions

**Files:**
- Modify: `services/stock_exit/daemon.py`, `services/stock_exit/main.py`
- Test: `tests/unit/stock_exit/test_daemon.py` (or the daemon test that exists)

**Interfaces:**
- Consumes: `BearOverrideConfig`, `parse_strong_set` (Task 2); `ThreeStageExit.scan_positions(bear_override_symbols=)` (Task 4).
- Produces: `StockExitDaemon._load_bear_override() -> set[str]` (staleness-gated, ∅ on any problem), passed into `scan_positions`.

- [ ] **Step 1: Write the failing test**

```python
# append to the stock_exit daemon test
@pytest.mark.asyncio
async def test_load_bear_override_fresh_and_stale(...):
    # fresh payload → set; stale/missing → empty set (fail-safe)
```
Mirror the existing `_load_market_state` test if present (same staleness shape).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_exit/test_daemon.py -k override -v`
Expected: FAIL — no `_load_bear_override`.

- [ ] **Step 3: Write minimal implementation**

In `services/stock_exit/daemon.py`:
- Import `from shared.streaming.stock_bear_override import BearOverrideConfig, parse_strong_set`.
- `__init__`: add `bear_override_config: BearOverrideConfig | None = None`.
- New:
```python
    async def _load_bear_override(self) -> set[str]:
        cfg = self._bear_override_config
        if cfg is None or not cfg.enabled:
            return set()
        try:
            raw = await self.redis.get(cfg.redis_key)
        except Exception:
            logger.exception("bear override read failed")
            return set()
        now_ms = int(self._now_fn().timestamp() * 1000)
        return parse_strong_set(raw, config=cfg, now_ms=now_ms)
```
- In the scan body (line ~136-138): `override = await self._load_bear_override()` then `scan_positions(priced_positions, market_data, market_state=market_state, bear_override_symbols=override)`.
- In `main.py`: `bear_override_config = BearOverrideConfig.load()` (None-equivalent when disabled) and pass to the daemon.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_exit/test_daemon.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/stock_exit/daemon.py services/stock_exit/main.py tests/unit/stock_exit/test_daemon.py
git commit -m "feat(bear-override): M4-X loads strong set + exempts override symbols from bear-exit"
```

---

### Task 6: Full-suite regression + final review

- [ ] **Step 1:** `.venv/bin/pytest -n auto -m "not serial" -q` then `.venv/bin/pytest -m "serial" -q` — both exit 0. (Full suite — async-signature changes in three_stage/scan_positions may touch integration tests; this catches them, per the Component B lesson.)
- [ ] **Step 2:** `.venv/bin/ruff check` + `.venv/bin/black --check` on all changed files.
- [ ] **Step 3:** Document paper enablement: set `stock_bear_override.enabled: true` in the paper config; deploy = rebuild `stock-strategy` + `stock-exit`, `up -d --no-deps` (never `down`).
- [ ] **Step 4:** Commit any cleanup; then the controller runs the final whole-branch review.

---

## Self-Review

**Spec coverage:** strength predicate → Task 1; Redis override contract + config → Task 2; M4-P compute/publish + bear-branch override entries + cap → Task 3; M4-X three_stage exemption → Task 4; M4-X daemon/main wiring → Task 5; regression → Task 6. All spec sections covered.

**Placeholder scan:** Tasks 1-2 carry complete code. Tasks 3-5 modify existing files and give the exact diffs/anchors with surrounding context; the few "locate the existing test" pointers are because the controller must hand the implementer the right existing test file (its exact path is found at execution, not invented) — concrete, not vague.

**Type consistency:** `StrengthCriteria`/`compute_strong_symbols` (Task 1) used by `BearOverrideConfig.criteria` + Task 3. `BearOverrideConfig`/`parse_strong_set`/`compute_override_payload` (Task 2) used by Tasks 3 & 5. `bear_override_symbols: set[str] | None` consistent across Tasks 4 & 5. Redis key `stock:daemon:bear_override` consistent.

**Note for executor:** Tasks 3-5 touch live decoupled stock entry/exit — keep `enabled` default False (zero behavior change) and verify the fail-safe paths (stale/empty → normal bear) in review. Run the FULL suite in Task 6 (the Component B lesson: an integration test called the async-changed method synchronously and only CI caught it).
