# Futures Paradigm — Phase 3 Decision Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implement Setup A (gap reversion) + Setup C (event reaction) entry signal generators, an 8-filter `RiskFilterLayer`, and a contract-aware `FixedFractionalFuturesSizer`. Drive them end-to-end through `MarketContext → Setup.check() → RiskFilterLayer → Signal` and persist results to `signals_all` for backtest validation. Phase 3 is backtest-only — no order placement, no live paper. Phase 4 turns this into a runtime daemon.

**Architecture:** signal pipeline is a composable chain: `MarketContext` (live data aggregator) → `SignalGenerator` (Setup A/C entry rules) → `stream:signal.candidate` / in-process candidate → `RiskFilterLayer` (8 sequential filters) → `stream:signal.final` / `signals_all`. Filter rejections log to `signals_all` too with `skip_reason`. Every numeric threshold lives in YAML; no hardcoded contract multipliers or tick sizes. Existing `shared/backtest/engine.py` gains a `MarketContext` replay adapter so the same Setup code runs in backtest + (future) live.

**Tech Stack:** Python 3.11+, asyncio, `redis.asyncio`, `aiochclient`, `pydantic v2`, `pytest` + `pytest-asyncio` + `fakeredis`, `yfinance` for retroactive macro backfill in backtests. Reuses Phase 1/2 shared modules.

**Parent spec:** `docs/plans/2026-04-20-futures-paradigm-phase3-decision-engine.md`
**Depends on:** `feat/futures-paradigm-phase2` merged to main (Phase 2 48h gate passed or explicitly waived). Currently branched from post-Phase-2 main.

---

## File Structure

**Create (new files):**

```
config/
├── decision_engine.yaml                  # Setup A / C params + trading windows
├── risk.yaml                             # RiskFilterLayer + account params
└── scheduled_events.yaml                 # macro event calendar (manual)

shared/decision/
├── __init__.py
├── context.py                            # MarketContext + ScheduledEvent
├── signal.py                             # Signal dataclass + stream serialization
├── setup_base.py                         # Setup ABC
└── setups/
    ├── __init__.py
    ├── gap_reversion.py                  # SetupAGapReversion
    └── event_reaction.py                 # SetupCEventReaction

shared/risk/
├── filters/
│   ├── __init__.py
│   ├── base.py                           # RiskFilter ABC + FilterResult
│   ├── trading_hours.py
│   ├── daily_mdd.py
│   ├── weekly_mdd.py
│   ├── consecutive_loss.py
│   ├── daily_trade_count.py
│   ├── volatility.py
│   ├── spread.py
│   └── open_position.py
├── state.py                              # RiskState (Redis-backed)
└── layer.py                              # RiskFilterLayer (orchestrator)

shared/execution/
└── contract_spec.py                      # ContractSpec + resolve_contract_spec

shared/strategy/position/
└── sizers.py                             # MODIFY: register FixedFractionalFuturesSizer

shared/backtest/
├── market_context_replay.py              # historical MarketContext factory
└── decision_harness.py                   # backtest harness for Phase 3

scripts/
├── optimize_decision_engine.py           # Optuna TPE harness per Setup
└── walk_forward_phase3.py                # walk-forward analysis runner

docs/runbooks/
└── phase3-verification.md                # completion gate checklist

tests/unit/decision/
├── __init__.py
├── test_signal.py
├── test_market_context.py
├── test_setup_a_gap_reversion.py
├── test_setup_c_event_reaction.py
└── test_scheduled_events_loader.py

tests/unit/risk/
├── __init__.py
├── test_risk_state.py
├── test_filter_trading_hours.py
├── test_filter_daily_mdd.py
├── test_filter_weekly_mdd.py
├── test_filter_consecutive_loss.py
├── test_filter_daily_trade_count.py
├── test_filter_volatility.py
├── test_filter_spread.py
├── test_filter_open_position.py
└── test_risk_filter_layer.py

tests/unit/execution/
└── test_contract_spec.py

tests/unit/strategy/position/
└── test_fixed_fractional_futures_sizer.py

tests/integration/
├── test_decision_pipeline_e2e.py         # MarketContext → Setup → Filter → signals_all
└── test_backtest_harness.py
```

**Modify (existing files):**

- `config/execution.yaml` — add `futures_contract_spec` section
- `shared/arbitrage/config.py` — remove hardcoded `multiplier: int = 50000`
- `shared/trend/config.py` — remove hardcoded `multiplier: int = 50000`
- `shared/strategy/position/sizers.py` — append `FixedFractionalFuturesSizer`
- `services/monitoring/metrics.py` — add 6 decision-engine metric families
- `shared/backtest/engine.py` — hook `MarketContext` replay

---

## Conventions Reminder (applies to all tasks)

- **Feature branch:** work on `feat/futures-paradigm-phase3` (already checked out). Never commit to main.
- **Test runner:** `source .venv/bin/activate && pytest ...` — NOT system pytest.
- **Redis DB:** always `REDIS_DB=1`.
- **Test isolation:** `fakeredis` for Redis, `AsyncMock()` for ClickHouse, fixture-level `tmp_path` for YAML configs.
- **Formatting:** `black <files> && ruff check --fix <files>` on **modified files only** — never `black .` on the tree.
- **Commit style:** `feat(decision): ...`, `feat(risk): ...`, `test(decision): ...`, `chore(config): ...`.
- **Contract spec:** every `multiplier_krw_per_point` / `tick_size_points` reference must come from `config/execution.yaml` via `ContractSpec`. No literals.
- **No backtest shortcuts:** the backtest harness must use the same `Setup.check()` code path the runtime will use (Phase 4). Do not duplicate Setup logic for historical replay.
- **Lessons carried forward from Phase 1/2:**
  - `ClickHouseConfig.from_env(database="kospi")` explicit pass-through
  - `.replace(tzinfo=None)` before `DateTime64('UTC')` writes
  - `await redis.expire(stream, 86400)` after every XADD
  - ServiceConfigBase for any new service-level config class
  - Publishers must re-raise on CH failure (no silent swallow)

---

## Task 1: Scaffold branch + dependency check

**Files:** possibly `pyproject.toml`.

- [ ] **Step 1: Branch already exists (`feat/futures-paradigm-phase3`).** Confirm:
  ```bash
  git branch --show-current
  ```
- [ ] **Step 2: Verify `yfinance` is available** (used by retroactive macro backfill):
  ```bash
  source .venv/bin/activate
  python -c "import yfinance; print(yfinance.__version__)"
  ```
- [ ] **Step 3: No commit unless pyproject.toml actually changed.**

---

## Task 2: `futures_contract_spec` config section + ContractSpec resolver

**Files:**
- Modify: `config/execution.yaml`
- Create: `shared/execution/contract_spec.py`
- Create: `tests/unit/execution/test_contract_spec.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/execution/test_contract_spec.py
import pytest

from shared.execution.contract_spec import (
    ContractSpec,
    ContractSpecRegistry,
    resolve_contract_spec,
)


def test_contract_spec_exposes_multiplier_tick_value():
    spec = ContractSpec(
        name="kospi200_mini",
        multiplier_krw_per_point=50000,
        tick_size_points=0.02,
        tick_value_krw=1000,
        commission_rate=0.00003,
        symbol_prefix="A05",
    )
    assert spec.multiplier_krw_per_point == 50000
    assert spec.tick_value_krw == 1000


def test_resolve_by_symbol_prefix():
    registry = ContractSpecRegistry(specs={
        "kospi200_mini": ContractSpec(
            name="kospi200_mini",
            multiplier_krw_per_point=50000,
            tick_size_points=0.02,
            tick_value_krw=1000,
            commission_rate=0.00003,
            symbol_prefix="A05",
        ),
        "kospi200_full": ContractSpec(
            name="kospi200_full",
            multiplier_krw_per_point=250000,
            tick_size_points=0.05,
            tick_value_krw=12500,
            commission_rate=0.00003,
            symbol_prefix="101",
        ),
    })
    assert resolve_contract_spec("A05603", registry).name == "kospi200_mini"
    assert resolve_contract_spec("101S6000", registry).name == "kospi200_full"


def test_resolve_unknown_symbol_raises():
    registry = ContractSpecRegistry(specs={})
    with pytest.raises(ValueError, match="no contract spec"):
        resolve_contract_spec("XXX000", registry)


def test_registry_loads_from_yaml(tmp_path):
    y = tmp_path / "execution.yaml"
    y.write_text(
        "futures_contract_spec:\n"
        "  kospi200_mini:\n"
        "    multiplier_krw_per_point: 50000\n"
        "    tick_size_points: 0.02\n"
        "    tick_value_krw: 1000\n"
        "    commission_rate: 0.00003\n"
        "    symbol_prefix: A05\n"
    )
    registry = ContractSpecRegistry.from_yaml(str(y))
    assert registry.specs["kospi200_mini"].multiplier_krw_per_point == 50000
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
# shared/execution/contract_spec.py
"""Contract-spec registry for Korean index futures."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ContractSpec:
    name: str
    multiplier_krw_per_point: int
    tick_size_points: float
    tick_value_krw: int
    commission_rate: float
    symbol_prefix: str


@dataclass
class ContractSpecRegistry:
    specs: dict[str, ContractSpec] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "ContractSpecRegistry":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        raw = data.get("futures_contract_spec", {})
        return cls(
            specs={
                name: ContractSpec(name=name, **fields) for name, fields in raw.items()
            }
        )


def resolve_contract_spec(symbol: str, registry: ContractSpecRegistry) -> ContractSpec:
    for spec in registry.specs.values():
        if symbol.startswith(spec.symbol_prefix):
            return spec
    raise ValueError(f"no contract spec for symbol={symbol}")
```

- [ ] **Step 4: Append `futures_contract_spec` section to `config/execution.yaml`** (exactly as in spec §7.2).

- [ ] **Step 5: Run — expect PASS & Commit**

```bash
pytest tests/unit/execution/test_contract_spec.py -v
git add config/execution.yaml shared/execution/contract_spec.py tests/unit/execution/
git commit -m "feat(execution): futures_contract_spec registry + YAML section"
```

---

## Task 3: `Signal` dataclass

**Files:**
- Create: `shared/decision/__init__.py`, `shared/decision/signal.py`
- Create: `tests/unit/decision/__init__.py`, `tests/unit/decision/test_signal.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/decision/test_signal.py
from datetime import UTC, datetime, timedelta

import pytest

from shared.decision.signal import Signal


def _kwargs(**overrides):
    base = dict(
        setup_type="A_gap_reversion",
        direction="long",
        symbol="A05603",
        entry_price=350.25,
        stop_loss=349.25,
        take_profit=352.00,
        confidence=0.7,
        reason_tags=["sp500_gap_+1.20%"],
        valid_until=datetime.now(UTC) + timedelta(minutes=10),
        generated_at=datetime.now(UTC),
    )
    base.update(overrides)
    return base


def test_signal_valid_construction():
    s = Signal(**_kwargs())
    assert s.setup_type == "A_gap_reversion"
    assert s.direction == "long"


@pytest.mark.parametrize("direction", ["up", "buy", "", None])
def test_signal_rejects_bad_direction(direction):
    with pytest.raises(ValueError):
        Signal(**_kwargs(direction=direction))


def test_signal_to_stream_dict_roundtrip():
    s = Signal(**_kwargs())
    fields = s.to_stream_dict()
    assert fields["setup_type"] == "A_gap_reversion"
    assert fields["direction"] == "long"
    # reason_tags serialized as JSON
    import json
    assert json.loads(fields["reason_tags_json"]) == ["sp500_gap_+1.20%"]


def test_signal_risk_reward_ratio():
    s = Signal(**_kwargs(entry_price=100.0, stop_loss=99.0, take_profit=102.0))
    assert s.risk_reward_ratio() == pytest.approx(2.0)
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement `shared/decision/signal.py`** — frozen dataclass with validation in `__post_init__`, `to_stream_dict()` producing scalar-string fields (tz-stripped `generated_at_ms`, `reason_tags` as `reason_tags_json`), and `risk_reward_ratio()` helper.

- [ ] **Step 4: Run — expect PASS & Commit.**

---

## Task 4: `MarketContext` + `ScheduledEvent` + scheduled events loader

**Files:**
- Create: `shared/decision/context.py`, `config/scheduled_events.yaml`
- Create: `tests/unit/decision/test_market_context.py`, `tests/unit/decision/test_scheduled_events_loader.py`

- [ ] **Step 1: Write tests**

```python
# tests/unit/decision/test_market_context.py
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.decision.context import MarketContext, ScheduledEvent

KST = ZoneInfo("Asia/Seoul")


def _ctx(**overrides):
    base = dict(
        now=datetime(2026, 4, 23, 9, 30, tzinfo=KST),
        symbol="A05603",
        current_price=350.25,
        prev_close=348.00,
        today_open=352.50,
        vwap=351.10,
        atr_14=0.85,
        atr_90th_percentile=1.20,
        last_15min_high=351.00,
        last_15min_low=349.20,
        current_spread_ticks=1.0,
        macro_overnight=None,
        scheduled_events=[],
    )
    base.update(overrides)
    return MarketContext(**base)


def test_market_open_time_returns_kst_900():
    ctx = _ctx()
    assert ctx.market_open_time() == datetime(2026, 4, 23, 9, 0, tzinfo=KST)


def test_minutes_since_open():
    ctx = _ctx(now=datetime(2026, 4, 23, 10, 15, tzinfo=KST))
    assert abs(ctx.minutes_since_open() - 75) < 0.01


def test_find_recent_event_within_window():
    evt = ScheduledEvent(
        event_id="us_cpi",
        event_type="US_CPI",
        scheduled_at=datetime(2026, 4, 23, 9, 20, tzinfo=KST),
        impact_tier=1,
    )
    ctx = _ctx(now=datetime(2026, 4, 23, 9, 30, tzinfo=KST), scheduled_events=[evt])
    recent = ctx.find_recent_event(window_minutes=15, min_tier=2)
    assert recent is evt


def test_find_recent_event_outside_window():
    evt = ScheduledEvent(
        event_id="us_cpi",
        event_type="US_CPI",
        scheduled_at=datetime(2026, 4, 23, 9, 10, tzinfo=KST),
        impact_tier=1,
    )
    ctx = _ctx(now=datetime(2026, 4, 23, 9, 30, tzinfo=KST), scheduled_events=[evt])
    assert ctx.find_recent_event(window_minutes=15, min_tier=2) is None


def test_find_recent_event_tier_filter():
    evt = ScheduledEvent(
        event_id="x",
        event_type="minor",
        scheduled_at=datetime(2026, 4, 23, 9, 25, tzinfo=KST),
        impact_tier=3,
    )
    ctx = _ctx(now=datetime(2026, 4, 23, 9, 30, tzinfo=KST), scheduled_events=[evt])
    assert ctx.find_recent_event(window_minutes=15, min_tier=2) is None
```

```python
# tests/unit/decision/test_scheduled_events_loader.py
from shared.decision.context import load_scheduled_events


def test_load_from_yaml_round_trips(tmp_path):
    y = tmp_path / "scheduled_events.yaml"
    y.write_text(
        "events:\n"
        "  - event_id: fomc_2026_may\n"
        "    event_type: FOMC_rate_decision\n"
        "    scheduled_at: '2026-05-01T03:00:00Z'\n"
        "    impact_tier: 1\n"
    )
    events = load_scheduled_events(str(y))
    assert len(events) == 1
    assert events[0].event_type == "FOMC_rate_decision"
    assert events[0].impact_tier == 1
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** `shared/decision/context.py`:
  - `ScheduledEvent` frozen dataclass (`event_id`, `event_type`, `scheduled_at: datetime` with tz, `impact_tier: int`)
  - `MarketContext` frozen dataclass (per spec §3.1) with helpers `market_open_time()`, `minutes_since_open()`, `find_recent_event(window_minutes, min_tier)`
  - `load_scheduled_events(path) -> list[ScheduledEvent]` parsing the YAML

- [ ] **Step 4: Create `config/scheduled_events.yaml`** with 3 placeholder events (FOMC + US CPI + BOK).

- [ ] **Step 5: Run — expect PASS & Commit.**

---

## Task 5: `SetupAGapReversion`

**Files:**
- Create: `shared/decision/setup_base.py`, `shared/decision/setups/__init__.py`, `shared/decision/setups/gap_reversion.py`
- Create: `tests/unit/decision/test_setup_a_gap_reversion.py`

- [ ] **Step 1: Write tests** covering: (a) happy path gap-down → long reversion, (b) outside valid minutes → None, (c) SP500 gap too small → None, (d) KR gap too small → None, (e) direction mismatch → None, (f) retrace out of band → None, (g) confidence in [0.5, 1.0].

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** `setup_base.py` (Setup ABC with `CONFIG_CLASS` + `check()` signature) and `gap_reversion.py` matching spec §4.1. `SetupAConfig` is a Pydantic model reading from `config/decision_engine.yaml::setup_a_gap_reversion`. Use `ServiceConfigBase` with `_default_config_file="decision_engine.yaml"`, `_default_section="setup_a_gap_reversion"`.

- [ ] **Step 4: Run — expect PASS & Commit.**

---

## Task 6: `SetupCEventReaction` + dedupe state tracker

**Files:**
- Create: `shared/decision/setups/event_reaction.py`
- Create: `tests/unit/decision/test_setup_c_event_reaction.py`

- [ ] **Step 1: Write tests** covering: (a) event in window → breakout → signal, (b) no event in window → None, (c) duplicate event_id already traded → None, (d) breakout buffer exceeded → None, (e) event tier below `min_impact_tier` → None, (f) confidence formula `0.65 + 0.1*(3-tier)/2`.

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** `event_reaction.py`. State tracker is a simple in-memory `set[event_id]` injected via constructor; Phase 3 backtest doesn't need Redis persistence — persistence lands in Phase 4.

- [ ] **Step 4: Run — expect PASS & Commit.**

---

## Task 7: `config/decision_engine.yaml`

**Files:**
- Create: `config/decision_engine.yaml` (exactly per spec §4.2 + §5.2)

- [ ] **Step 1:** Write YAML with `setup_a_gap_reversion` + `setup_c_event_reaction` sections.
- [ ] **Step 2: Commit** — no test needed; covered by Tasks 5 & 6 via `from_yaml()` tests.

---

## Task 8: `RiskState` + Redis persistence

**Files:**
- Create: `shared/risk/state.py`, `tests/unit/risk/test_risk_state.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/risk/test_risk_state.py
import fakeredis.aioredis
import pytest

from shared.risk.state import RiskState


@pytest.mark.asyncio
async def test_state_defaults_are_zero():
    r = fakeredis.aioredis.FakeRedis()
    s = RiskState(redis=r, asset_class="futures")
    snap = await s.load()
    assert snap.daily_pnl_krw == 0.0
    assert snap.consecutive_losses == 0
    assert snap.daily_trade_count == 0


@pytest.mark.asyncio
async def test_persist_then_load():
    r = fakeredis.aioredis.FakeRedis()
    s = RiskState(redis=r, asset_class="futures")
    snap = await s.load()
    snap.consecutive_losses = 3
    snap.daily_trade_count = 2
    snap.daily_pnl_krw = -15000.0
    await s.save(snap)

    s2 = RiskState(redis=r, asset_class="futures")
    reloaded = await s2.load()
    assert reloaded.consecutive_losses == 3
    assert reloaded.daily_trade_count == 2
    assert reloaded.daily_pnl_krw == -15000.0


@pytest.mark.asyncio
async def test_ttl_set_on_save():
    r = fakeredis.aioredis.FakeRedis()
    s = RiskState(redis=r, asset_class="futures")
    snap = await s.load()
    snap.daily_trade_count = 1
    await s.save(snap)
    ttl = await r.ttl("risk:state:futures")
    assert 0 < ttl <= 86400
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** `RiskState` using Redis HASH at `risk:state:{asset_class}`. `load()` returns a mutable `RiskStateSnapshot` dataclass; `save(snap)` writes fields + sets 24h TTL.

- [ ] **Step 4: Run — expect PASS & Commit.**

---

## Task 9: `RiskFilter` ABC + `FilterResult`

**Files:**
- Create: `shared/risk/filters/__init__.py`, `shared/risk/filters/base.py`
- Create: `tests/unit/risk/test_filter_base.py` (folded into this task)

- [ ] **Step 1: Write test**

```python
# tests/unit/risk/test_filter_base.py
from shared.risk.filters.base import FilterResult


def test_filter_result_pass():
    r = FilterResult(passed=True, filter_name="t", skip_reason=None)
    assert r.passed
    assert r.skip_reason is None


def test_filter_result_reject():
    r = FilterResult(passed=False, filter_name="t", skip_reason="reason_tag")
    assert not r.passed
    assert r.skip_reason == "reason_tag"
```

- [ ] **Step 2: Implement** ABC + `FilterResult` frozen dataclass.

- [ ] **Step 3: Run — expect PASS & Commit.**

---

## Task 10: Filter #1–#3 — TradingHours / DailyMDD / WeeklyMDD

**Files:**
- Create: `shared/risk/filters/{trading_hours,daily_mdd,weekly_mdd}.py`
- Create: `tests/unit/risk/test_filter_{trading_hours,daily_mdd,weekly_mdd}.py`

- [ ] For each filter: TDD (test → fail → impl → pass). Each filter reads its parameter from an injected `RiskConfig` (or dict), consults `RiskStateSnapshot`, returns `FilterResult`. Trading-hours parses `config/risk.yaml::trading_windows` list-of-strings `"HH:MM-HH:MM"` KST.

- [ ] **Commit:** `feat(risk): TradingHours / DailyMDD / WeeklyMDD filters`

---

## Task 11: Filter #4–#6 — ConsecutiveLoss / DailyTradeCount / Volatility

- [ ] Same TDD pattern. `ConsecutiveLossFilter` is special: it can signal "reduce size" without rejecting (filter returns `FilterResult(passed=True, size_multiplier=0.5)`). Update `FilterResult` to carry an optional `size_multiplier: float = 1.0`.
- [ ] `VolatilityFilter` reads `ctx.atr_14 > ctx.atr_90th_percentile` — pure computation, no config.
- [ ] **Commit:** `feat(risk): ConsecutiveLoss / DailyTradeCount / Volatility filters`

---

## Task 12: Filter #7–#8 — Spread / OpenPosition

- [ ] `SpreadFilter` reads `ctx.current_spread_ticks` vs `risk.max_spread_ticks`.
- [ ] `OpenPositionFilter` queries a `PositionTracker`-like callable injected via constructor (Phase 3 backtest passes a stub; Phase 4 wires the real tracker).
- [ ] **Commit:** `feat(risk): Spread + OpenPosition filters`

---

## Task 13: `RiskFilterLayer` orchestrator

**Files:**
- Create: `shared/risk/layer.py`, `tests/unit/risk/test_risk_filter_layer.py`

- [ ] **Step 1: Test** the layer runs filters in order, short-circuits on first reject, returns first rejection's `skip_reason`, applies size reductions from non-rejecting filters, and integrates with `RiskState`.

- [ ] **Step 2: Implement** `RiskFilterLayer` with `async def evaluate(signal, ctx, state_snapshot) -> LayerResult`. `LayerResult` carries `passed`, `skip_reason`, `size_multiplier`, and a list of filter outcomes for observability.

- [ ] **Step 3: Commit.**

---

## Task 14: `config/risk.yaml`

**Files:**
- Create: `config/risk.yaml` (exactly per spec §6.2)
- Create: `shared/risk/config.py` (`RiskConfig(ServiceConfigBase)` + nested section models)
- Create: `tests/unit/risk/test_risk_config.py`

- [ ] TDD for Pydantic load + YAML override. `_default_config_file="risk.yaml"`, `_default_section="risk"` plus `trading_windows` at top level.

- [ ] **Commit:** `feat(risk): RiskConfig + config/risk.yaml`

---

## Task 15: `FixedFractionalFuturesSizer` + registration

**Files:**
- Modify: `shared/strategy/position/sizers.py` — append sizer class + `@SizerRegistry.register("fixed_fractional_futures")`
- Create: `tests/unit/strategy/position/test_fixed_fractional_futures_sizer.py`

- [ ] Tests cover: (a) size from points×multiplier + risk budget, (b) clamp to `max_position_size_contracts`, (c) minimum 1 contract, (d) soft-reduce on consecutive losses ≥ threshold halves size.

- [ ] **Commit:** `feat(strategy): FixedFractionalFuturesSizer with contract spec`

---

## Task 16: Remove hardcoded `multiplier: int = 50000` from arbitrage/trend

**Files:**
- Modify: `shared/arbitrage/config.py`, `shared/trend/config.py`
- No new tests — existing tests continue passing.

- [ ] **Step 1:** Replace `multiplier: int = 50000` with a factory that calls `ContractSpecRegistry.from_yaml().specs["kospi200_mini"].multiplier_krw_per_point`. Keep the field; just populate default via `Field(default_factory=_default_mini_multiplier)`.

- [ ] **Step 2:** Grep verify no literal `50000` remains in the changed files:
  ```bash
  grep -n "50000" shared/arbitrage/config.py shared/trend/config.py
  ```
  Expected: no matches.

- [ ] **Step 3:** Full test suite for arbitrage + trend:
  ```bash
  pytest tests/unit/arbitrage tests/unit/trend -v
  ```
  All pass.

- [ ] **Commit:** `refactor(futures): remove hardcoded contract multiplier (delegate to ContractSpec)`

---

## Task 17: Prometheus metrics for decision engine

**Files:**
- Modify: `services/monitoring/metrics.py` — append 6 metric families from spec §10.1 (+ `record_*` helpers)
- Create: `tests/unit/monitoring/test_decision_metrics.py`

- [ ] TDD for metric existence + helper invocation (no exception).
- [ ] **Commit:** `feat(monitoring): decision-engine Prometheus metric families`

---

## Task 18: Backtest harness extension

**Files:**
- Create: `shared/backtest/market_context_replay.py`, `shared/backtest/decision_harness.py`
- Create: `tests/integration/test_backtest_harness.py`

- [ ] **Step 1: Write integration test** that runs the harness on a short synthetic 1-day 1-min CSV + a stub `ScheduledEvent` list + a stub macro snapshot, asserts ≥1 candidate generated and at least one pass through `RiskFilterLayer` → `signals_all` write.

- [ ] **Step 2: Implement `market_context_replay.py`** — `MarketContextReplay(df, macro_series, scheduled_events, contract_spec)` with `iter_contexts() -> Iterator[MarketContext]` that yields one context per minute, computing `atr_14` / `vwap` incrementally.

- [ ] **Step 3: Implement `decision_harness.py`** — `BacktestDecisionHarness(setups, filter_layer, ch_writer_or_buffer)` that:
  - iterates `MarketContextReplay.iter_contexts()`
  - for each ctx: runs all Setups → candidates → filter layer → accepted/rejected
  - records every outcome to an in-memory list (or optional CH writer); `executed=0` for all Phase 3 runs
  - returns a summary: `{setup_type: {trades, win_rate, ev_ticks, rr_ratio}}` (wins/losses from a simple forward-looking fill simulation at next bar's open with slippage = `0.3 × tick_size_points`)

- [ ] **Step 4: Commit.**

---

## Task 19: Signal persistence to `signals_all`

**Files:**
- Create: `shared/backtest/signals_writer.py` (wraps `AsyncClickHouseClient.execute` for `kospi.signals_all`)
- Create: `tests/integration/test_decision_pipeline_e2e.py`

- [ ] **Step 1: Write e2e test** — full pipeline end-to-end with `fakeredis` + `AsyncMock` CH:
  - Synthetic minute bars
  - Setup A fires at the right minute
  - Filter layer accepts
  - `SignalsAllWriter` batches the row
  - Verify `ch.execute` called with expected SQL shape

- [ ] **Step 2: Implement** writer (mirror `ClickHouseNewsWriter` pattern: batch + re-raise on CH failure — carry the lesson from Phase 2 code review).

- [ ] **Step 3: Commit.**

---

## Task 20: Walk-forward harness + 6-month backtest

**Files:**
- Create: `scripts/walk_forward_phase3.py`
- Create: `scripts/optimize_decision_engine.py` (Optuna TPE per Setup)
- Add smoke test only (full run is manual during 48h gate).

- [ ] **Step 1:** Implement the two scripts following the existing `scripts/optimize_strategies.py` pattern. The WF harness splits a DataFrame by a configurable `is_months` / `oos_months` window, runs the harness from Task 18 on each fold, reports per-fold OOS Sharpe + IS Sharpe.

- [ ] **Step 2:** Manual sanity run on `data/kospi200f_1m_clean.csv` — note results in the runbook.

- [ ] **Step 3:** Commit scripts without run artifacts.

---

## Task 21: Full test sweep + runbook + draft PR

**Files:**
- Create: `docs/runbooks/phase3-verification.md`

- [ ] **Step 1: Full sweep**

```bash
source .venv/bin/activate
pytest tests/unit/decision tests/unit/risk tests/unit/execution \
       tests/unit/strategy/position/test_fixed_fractional_futures_sizer.py \
       tests/unit/monitoring/test_decision_metrics.py \
       tests/integration/test_decision_pipeline_e2e.py \
       tests/integration/test_backtest_harness.py \
       --cov=shared/decision --cov=shared/risk --cov=shared/execution/contract_spec \
       --cov-report=term-missing
```
Expected: all tests pass, Setup A/C coverage ≥ 90%, filters ≥ 85%.

- [ ] **Step 2: Write `docs/runbooks/phase3-verification.md`** mirroring Phase 2 runbook structure:
  - Backtest 6-month: ≥30 trades/setup, EV > 0.5 tick (post-slippage)
  - WF OOS ≥ 0.5 × IS Sharpe
  - `signals_all` populated in backtest runs
  - Hardcoding removal verified (grep `50000` in arbitrage/trend)
  - `rl_mppo` unaffected
  - Prometheus metrics emit during `scripts/walk_forward_phase3.py`
  - Rollback: N/A (Phase 3 is backtest-only; nothing to roll back)

- [ ] **Step 3: Push + draft PR**

```bash
git push -u origin feat/futures-paradigm-phase3
gh pr create --draft --title "feat(phase3): decision engine — Setup A/C + RiskFilterLayer" \
  --body "Implements docs/plans/2026-04-20-futures-paradigm-phase3-decision-engine.md.
Backtest-only; no live paper in this PR (Phase 4 handles runtime).
Gate: docs/runbooks/phase3-verification.md."
```

- [ ] **Step 4: Final commit (runbook).**

---

## Self-Review

**1. Spec coverage (phase3-decision-engine.md §2–§10):**

| Spec item | Tasks |
|-----------|-------|
| ContractSpec + registry | 2 |
| Signal dataclass | 3 |
| MarketContext + ScheduledEvent | 4 |
| SetupA + config | 5, 7 |
| SetupC + state tracker + config | 6, 7 |
| RiskState + Redis persistence | 8 |
| RiskFilter ABC | 9 |
| 8 filters | 10, 11, 12 |
| RiskFilterLayer orchestrator | 13 |
| RiskConfig + YAML | 14 |
| FixedFractionalFuturesSizer | 15 |
| Hardcoding removal (arbitrage/trend) | 16 |
| Prometheus metrics | 17 |
| Backtest harness | 18 |
| signals_all writer | 19 |
| Walk-forward + Optuna | 20 |
| Runbook + PR | 21 |

Grafana dashboard JSON (spec §10.2) is intentionally NOT in this plan — low-risk ops config, composed during 48h observation window.

**2. Type consistency:**
- `Signal` fields used across Tasks 3, 5, 6, 13, 18, 19 match.
- `MarketContext` consumed by Tasks 5, 6, 10–12, 18 — field list identical to spec §3.1.
- `FilterResult` from Task 9 is the single return type for all filters in Tasks 10–13.
- `ContractSpec.multiplier_krw_per_point` used by sizer (Task 15) + hardcoding removal (Task 16) + existing RL env — all same field name.

✓ No type/name mismatches.

**3. Placeholder scan:**
- `config/scheduled_events.yaml` is deliberately seeded with 3 placeholder events — operator updates monthly. Noted in spec §3.3.
- Walk-forward actual run is manual (Task 20 Step 2) — not automated in CI because it consumes 6 months of data.
- `atr_90th_percentile` requires a 60-day warmup; the harness (Task 18) must start replay 60 days before the first evaluated signal. Captured as a TODO in the harness docstring.

**4. Risks flagged in spec + mitigations:**
- Backtest-live divergence: same `Setup.check()` path used in both (Task 5/6 tests run against the same classes the backtest instantiates).
- Hardcoded multipliers: Task 16 explicitly greps for literal `50000`.
- Consumer-group vs backtest: Phase 3 runs in-process, no Redis streams. The `stream:signal.*` pipeline is Phase 4.
- `rl_mppo` unaffected: no modifications to `shared/ml/rl/` or `services/trading/`.

---

## Execution Handoff

**Two execution options (same as Phase 1/2):**

1. **Subagent-Driven (recommended):** dispatch one fresh subagent per task. Each task has its own test-first boundary. Batch reviews between dependency groups.
2. **Inline:** execute tasks in-session with `superpowers:executing-plans`; checkpoint every 3–4 tasks.

Run `/review docs/plans/2026-04-20-futures-paradigm-phase3-implementation-plan.md` with Momus before starting if you want a critic pass on the plan itself.
