# Futures Strategy Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing stock no-code strategy builder so operators can build **long-only, indicator-based futures strategies** in `/builder` and register them to **paper** trading, while sharing one indicator catalog across both asset classes.

**Architecture:** Two sequential PRs. **PR 1** fixes a pre-existing latent bug — the frontend sends a camelCase `BuilderState` but the Python schema only accepts snake_case (`extra="forbid"`), so register-paper currently 400s on any real strategy. We add camelCase aliases to the builder schema so the API accepts both casings; internal `model_dump` stays snake_case, so the materialized YAML and runtime are unaffected. **PR 2** adds futures support on top: gate whitelist, futures long entry, auto-enforced EOD/hard-stop exit safety, an asset-class toggle, advisory indicator warnings, and futures position sizing.

**Tech Stack:** Python 3.11 + Pydantic v2 (`pydantic.alias_generators.to_camel`), FastAPI, pytest (run via `.venv/bin/pytest`). Frontend: Next.js + React + TypeScript (Tailwind).

**Branch strategy:**
- PR 1 → branch `fix/builder-paper-serialization` (off `main`).
- PR 2 → branch `feat/futures-strategy-builder` (off PR 1's branch, or off `main` and rebase after PR 1 merges). PR 2 depends on PR 1's camelCase acceptance.

**Spec:** `docs/superpowers/specs/2026-06-01-futures-strategy-builder-design.md`

---

## Key facts (verified)

- Python schema `shared/strategy_builder/schema.py` uses snake_case + `extra="forbid"`, **no** alias generator → rejects the frontend's camelCase payload (empirically confirmed: `CAMEL: REJECTED`, `SNAKE: ACCEPTED`).
- `pydantic.alias_generators.to_camel` maps `asset_class→assetClass`, `indicator_id→indicatorId`, `stop_loss→stopLoss`, `name_ko→nameKo` (confirmed in the installed pydantic 2.12).
- `_validate_builder_state` (`kis_builder.py:667`) returns `state.model_dump(mode="json")` — default `by_alias=False` → snake keys → YAML/runtime unchanged.
- `FixedSizerConfig` already supports `fixed_quantity` (contract count) via `from_dict` (`sizers.py:62`); `FixedSizer.calculate` returns it directly when `> 0` (`sizers.py:105`). Futures sizing = `fixed_quantity`.
- `ExitReason.EOD_CLOSE = "eod_close"` exists; `ExitContext.timestamp` exists.
- The existing test `tests/unit/strategy/test_builder_strategy.py::test_entry_skips_non_stock_asset` asserts futures no-ops — it must be **flipped** in PR 2.
- IndicatorSelector already renders an amber `leanUnsupported` badge (`IndicatorSelector.tsx:198`) — the futures advisory badge mirrors it.

---

# PR 1 — Builder→Paper serialization fix

**Why first:** Without this, register-paper 400s on any real strategy (stock or futures), so no registration acceptance criterion can pass.

## Task 1.1: Schema accepts camelCase (failing test)

**Files:**
- Test: `tests/unit/strategy_builder/test_schema_camel_alias.py` (create)

- [ ] **Step 1: Write the failing test**

```python
"""BuilderState must accept the frontend's camelCase payload (and still
accept snake_case), while dumping snake_case for the runtime/YAML."""
from __future__ import annotations

from shared.strategy_builder.schema import BuilderState


def _camel_payload() -> dict:
    return {
        "metadata": {
            "id": "t_strat",
            "name": "T",
            "description": "",
            "category": "custom",
            "tags": ["x"],
            "author": "u",
        },
        "assetClass": "stock",
        "indicators": [
            {
                "id": "i1",
                "indicatorId": "rsi",
                "alias": "rsi",
                "displayName": "RSI",
                "params": {},
                "output": "value",
            }
        ],
        "entry": {
            "logic": "AND",
            "conditions": [
                {
                    "id": "c1",
                    "left": {
                        "type": "indicator",
                        "indicatorAlias": "rsi",
                        "indicatorOutput": "value",
                    },
                    "operator": "greater_than",
                    "right": {"type": "value", "value": 30.0},
                }
            ],
        },
        "exit": {"logic": "AND", "conditions": []},
        "risk": {
            "stopLoss": {"enabled": True, "percent": 5.0},
            "takeProfit": {"enabled": False, "percent": 10.0},
            "trailingStop": {"enabled": False, "percent": 3.0},
        },
    }


def test_camelcase_payload_is_accepted() -> None:
    state = BuilderState.model_validate(_camel_payload())
    assert state.asset_class == "stock"
    assert state.indicators[0].indicator_id == "rsi"
    assert state.entry.conditions[0].left.indicator_alias == "rsi"


def test_snakecase_payload_still_accepted() -> None:
    state = BuilderState.model_validate(
        {
            "metadata": {"id": "s", "name": "S"},
            "asset_class": "futures",
            "indicators": [
                {"indicator_id": "rsi", "alias": "rsi", "params": {}, "output": "value"}
            ],
            "entry": {
                "logic": "AND",
                "conditions": [
                    {
                        "left": {"type": "indicator", "indicator_alias": "rsi"},
                        "operator": "greater_than",
                        "right": {"type": "value", "value": 30.0},
                    }
                ],
            },
            "exit": {"logic": "AND", "conditions": []},
            "risk": {"stop_loss": {"enabled": True, "percent": 5.0}},
        }
    )
    assert state.asset_class == "futures"


def test_model_dump_is_snake_case() -> None:
    state = BuilderState.model_validate(_camel_payload())
    dumped = state.model_dump(mode="json")
    assert "asset_class" in dumped
    assert "assetClass" not in dumped
    assert "indicator_id" in dumped["indicators"][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/strategy_builder/test_schema_camel_alias.py -v`
Expected: FAIL — `test_camelcase_payload_is_accepted` raises ValidationError (`indicatorId` extra / `indicator_id` missing).

## Task 1.2: Add camelCase aliases to the builder input models

**Files:**
- Modify: `shared/strategy_builder/schema.py`

- [ ] **Step 1: Add the import and a shared model config**

At the top of the file, change the pydantic import line (currently `from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator`) to also import the alias generator, and add a shared config constant right after the imports (before `class IndicatorCategory`):

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

# Builder input models accept BOTH the frontend's camelCase payload (via the
# generated alias) and snake_case (populate_by_name) used by tests / the
# materialized YAML. model_dump(by_alias=False, the default) keeps snake_case
# so the runtime + YAML are unaffected.
_BUILDER_MODEL_CONFIG = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    extra="forbid",
)
```

- [ ] **Step 2: Apply the shared config to every model in the register-paper input tree**

Set `model_config = _BUILDER_MODEL_CONFIG` on these 8 models. For models that already have `model_config = ConfigDict(extra="forbid")`, replace that line. For `BuilderMetadata` (which currently has no `model_config`), add the line after its fields.

- `BuilderMetadata` — add (after the `author` field, before `@field_validator`):
  ```python
      model_config = _BUILDER_MODEL_CONFIG
  ```
- `BuilderIndicator` — replace `model_config = ConfigDict(extra="forbid")` with `model_config = _BUILDER_MODEL_CONFIG`
- `ConditionOperand` — replace `model_config = ConfigDict(extra="forbid")` with `model_config = _BUILDER_MODEL_CONFIG`
- `BuilderCondition` — replace `model_config = ConfigDict(extra="forbid")` with `model_config = _BUILDER_MODEL_CONFIG`
- `BuilderConditionGroup` — replace `model_config = ConfigDict(extra="forbid")` with `model_config = _BUILDER_MODEL_CONFIG`
- `RiskToggle` — add `model_config = _BUILDER_MODEL_CONFIG` (after its `percent` field)
- `RiskManagement` — add `model_config = _BUILDER_MODEL_CONFIG` (after its `trailing_stop` field)
- `BuilderState` — replace `model_config = ConfigDict(extra="forbid")` with `model_config = _BUILDER_MODEL_CONFIG`

> Do NOT touch `IndicatorParam`, `IndicatorOutput`, `IndicatorDefinition` (catalog models, not part of the register input) or `SymbolSeries`/`BuilderSignal` (response models). Limiting the blast radius keeps `load_capabilities()` (which reads snake_case `indicators.yaml`) unchanged.

- [ ] **Step 3: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/strategy_builder/test_schema_camel_alias.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 4: Run the existing builder/schema suites for regressions**

Run: `.venv/bin/pytest tests/unit/strategy_builder/ tests/unit/strategy/test_builder_strategy.py tests/unit/dashboard/test_strategy_builder.py -v`
Expected: PASS (snake_case paths still validate via `populate_by_name`).

- [ ] **Step 5: Commit**

```bash
git add shared/strategy_builder/schema.py tests/unit/strategy_builder/test_schema_camel_alias.py
git commit -m "fix(builder): accept camelCase BuilderState at the builder→paper API

The Next.js builder serializes a camelCase BuilderState but the schema was
snake_case + extra=forbid, so /api/kis-builder/register-paper rejected every
real strategy with HTTP 400. Add to_camel aliases (populate_by_name) to the
register-paper input models; model_dump stays snake_case so YAML/runtime are
unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 1.3: Route-level regression — register-paper accepts a camelCase state

**Files:**
- Modify: `tests/unit/dashboard/test_strategy_builder.py`

- [ ] **Step 1: Write the failing test**

Append to the file:

```python
@pytest.mark.asyncio
async def test_register_paper_accepts_camelcase_state(tmp_path, monkeypatch) -> None:
    from services.dashboard.routes import kis_builder

    monkeypatch.setattr(kis_builder, "_BUILT_STRATEGIES_DIR", tmp_path)

    camel = {
        "metadata": {
            "id": "camel_reg_test",
            "name": "Camel Reg",
            "description": "",
            "category": "custom",
            "tags": ["t"],
            "author": "u",
        },
        "assetClass": "stock",
        "indicators": [
            {"id": "i1", "indicatorId": "rsi", "alias": "rsi", "params": {}, "output": "value"}
        ],
        "entry": {
            "logic": "AND",
            "conditions": [
                {
                    "id": "c1",
                    "left": {"type": "indicator", "indicatorAlias": "rsi", "indicatorOutput": "value"},
                    "operator": "greater_than",
                    "right": {"type": "value", "value": 30.0},
                }
            ],
        },
        "exit": {"logic": "AND", "conditions": []},
        "risk": {
            "stopLoss": {"enabled": True, "percent": 5.0},
            "takeProfit": {"enabled": False, "percent": 10.0},
            "trailingStop": {"enabled": False, "percent": 3.0},
        },
    }

    result = await kis_builder.register_paper_strategy(
        kis_builder.RegisterPaperRequest(builder_state=camel)
    )
    assert result.asset_class == "stock"
    assert (tmp_path / "camel_reg_test.yaml").exists()
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/pytest tests/unit/dashboard/test_strategy_builder.py::test_register_paper_accepts_camelcase_state -v`
Expected: PASS (was previously impossible — 400 before Task 1.2).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/dashboard/test_strategy_builder.py
git commit -m "test(builder): register-paper accepts camelCase state end-to-end

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: Push & open PR 1**

```bash
git push -u origin fix/builder-paper-serialization
gh pr create --base main --title "fix(builder): accept camelCase BuilderState at register-paper" \
  --body "Fixes the latent camelCase/snake_case mismatch that made builder→paper registration 400 on any real strategy. Prereq for the futures builder (#spec 2026-06-01)."
```

---

# PR 2 — Futures strategy builder

> Branch `feat/futures-strategy-builder` based on PR 1. Verify backend with `.venv/bin/pytest`, frontend with `npm run lint` + `npm run build` from `strategy-builder-ui/`.

## Task 2.1: builder_v1 entry — emit long signals for futures

**Files:**
- Modify: `shared/strategy/entry/builder_strategy.py`
- Test: `tests/unit/strategy/test_builder_strategy.py:129` (flip the existing test)

- [ ] **Step 1: Flip the existing test to expect a long signal**

Replace `test_entry_skips_non_stock_asset` (lines 128-138) with:

```python
@pytest.mark.asyncio
async def test_entry_emits_long_signal_for_futures() -> None:
    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=_make_state(asset_class="futures"))
    )
    ctx = EntryContext(
        market_data={"code": "101S6000", "close": 1000.0},
        indicators={"rsi.value": 50.0},  # rsi > 30 → entry condition passes
        timestamp=datetime.now(UTC),
    )
    signal = await entry.generate(ctx)
    assert signal is not None
    assert signal.signal_type == SignalType.ENTRY
    assert signal.metadata["signal_direction"] == "long"  # Phase 1: long-only
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/unit/strategy/test_builder_strategy.py::test_entry_emits_long_signal_for_futures -v`
Expected: FAIL — `signal is None` (the no-op guard still fires).

- [ ] **Step 3: Remove the futures no-op guard**

In `shared/strategy/entry/builder_strategy.py`:

(a) Delete the guard in `generate` (lines 111-118):

```python
        if self._state.asset_class != "stock":
            if not self._asset_mismatch_warned:
                logger.warning(
                    "builder_v1 entry skipping: asset_class=%s (stock-only in Phase 1)",
                    self._state.asset_class,
                )
                self._asset_mismatch_warned = True
            return None
```

So that `generate` reads:

```python
    async def generate(self, context: EntryContext) -> Signal | None:
        if self._state is None:
            return None

        data = context.market_data or {}
```

(b) Delete the now-unused flag in `__init__` (line 76): remove `self._asset_mismatch_warned = False`.

(c) Update the docstring (lines 8-11) — replace the "Stock-only by design" paragraph with:

```python
Entry is long-only (Phase 1). Stock and futures both emit
``signal_direction="long"``; short selling is a Phase-2 follow-up. The
platform's short capability is unaffected (Setup A/C still trade both
directions) — only the builder UI is long-only for now.
```

- [ ] **Step 4: Run the full builder_strategy suite**

Run: `.venv/bin/pytest tests/unit/strategy/test_builder_strategy.py -v`
Expected: PASS (futures now emits a long signal; stock tests unchanged).

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/entry/builder_strategy.py tests/unit/strategy/test_builder_strategy.py
git commit -m "feat(builder): emit long entries for futures builder strategies

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 2.2: Futures exit safety (EOD close + hard-stop cap)

**Files:**
- Create: `config/strategy_builder/futures_safety.yaml`
- Create: `shared/strategy_builder/futures_safety.py`
- Modify: `shared/strategy/exit/builder_strategy_exit.py`
- Test: `tests/unit/strategy/test_builder_strategy.py`

- [ ] **Step 1: Create the safety config**

`config/strategy_builder/futures_safety.yaml`:

```yaml
# Auto-enforced safety guards for builder-generated FUTURES strategies.
# Applied by builder_v1_exit regardless of the user's risk settings.
futures_safety:
  hard_stop_pct: 3.0        # max allowable loss (percent) before a forced exit
  eod_close_time: "15:15"   # KST; force-close builder futures positions at/after this time
```

- [ ] **Step 2: Create the loader**

`shared/strategy_builder/futures_safety.py`:

```python
"""Auto-enforced safety guards for builder-generated futures strategies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time as dt_time
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("config/strategy_builder/futures_safety.yaml")


@dataclass(frozen=True)
class FuturesSafety:
    """Hard limits that builder futures strategies cannot disable."""

    hard_stop_pct: float
    eod_close_time: dt_time


@lru_cache(maxsize=1)
def load_futures_safety(path: str | Path = DEFAULT_CONFIG_PATH) -> FuturesSafety:
    cfg_path = Path(path)
    data: dict = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        data = raw.get("futures_safety", {}) or {}
    hard_stop = float(data.get("hard_stop_pct", 3.0))
    raw_time = str(data.get("eod_close_time", "15:15"))
    hh, mm = (int(part) for part in raw_time.split(":")[:2])
    return FuturesSafety(hard_stop_pct=hard_stop, eod_close_time=dt_time(hh, mm))
```

- [ ] **Step 3: Write failing tests for the exit safety**

Append to `tests/unit/strategy/test_builder_strategy.py`:

```python
def _futures_state() -> dict:
    state = _make_state(asset_class="futures")
    state["exit"]["conditions"] = []  # isolate SL/EOD behavior from conditions
    return state


@pytest.mark.asyncio
async def test_futures_exit_hard_stop_caps_loose_user_stop() -> None:
    # User sets a loose 10% stop; futures cap (3%) must trigger earlier.
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_futures_state(), stop_loss_pct=10.0)
    )
    ctx = ExitContext(
        position=_Pos("101S6000", entry_price=400.0),
        market_data={"close": 384.0},  # -4% → beyond the 3% cap, within user's 10%
        indicators={},
        timestamp=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),  # 10:00 KST (intraday)
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS


@pytest.mark.asyncio
async def test_futures_exit_hard_stop_applies_when_user_disables() -> None:
    # User disables the stop (0); futures still enforces the cap.
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_futures_state(), stop_loss_pct=0.0)
    )
    ctx = ExitContext(
        position=_Pos("101S6000", entry_price=400.0),
        market_data={"close": 386.0},  # -3.5%
        indicators={},
        timestamp=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),  # 10:00 KST
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS


@pytest.mark.asyncio
async def test_futures_exit_eod_close_after_cutoff() -> None:
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_futures_state(), stop_loss_pct=5.0)
    )
    ctx = ExitContext(
        position=_Pos("101S6000", entry_price=400.0),
        market_data={"close": 401.0},  # +0.25% — no SL/TP
        indicators={},
        timestamp=datetime(2026, 6, 1, 6, 20, tzinfo=UTC),  # 15:20 KST ≥ 15:15
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.EOD_CLOSE


@pytest.mark.asyncio
async def test_stock_exit_unaffected_by_futures_safety() -> None:
    # Stock with a 10% stop at -4% must NOT exit (no futures cap applies).
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_make_state(), stop_loss_pct=10.0)
    )
    state_no_cond = exit_strat.config.builder_state
    state_no_cond["exit"]["conditions"] = []
    ctx = ExitContext(
        position=_Pos("005930", entry_price=10000.0),
        market_data={"close": 9600.0},  # -4%
        indicators={},
        timestamp=datetime(2026, 6, 1, 6, 20, tzinfo=UTC),
    )
    triggered, _ = await exit_strat.should_exit(ctx)
    assert not triggered
```

- [ ] **Step 4: Run to verify they fail**

Run: `.venv/bin/pytest tests/unit/strategy/test_builder_strategy.py -k futures_exit -v`
Expected: FAIL — futures cap/EOD not implemented yet (e.g. `-4%` doesn't trigger a 10% stop).

- [ ] **Step 5: Implement the futures exit safety**

In `shared/strategy/exit/builder_strategy_exit.py`:

(a) Add the import near the top (after the existing `from shared.strategy_builder.schema import ...`):

```python
from shared.strategy_builder.futures_safety import FuturesSafety, load_futures_safety
```

(b) In `__init__`, after `self._parse_state()`, cache the futures flag + safety limits:

```python
    def __init__(self, config: BuilderStrategyExitConfig):
        super().__init__(config)
        self._evaluator = StrategyBuilderEvaluator()
        self._state: BuilderState | None = None
        self._parse_state()
        self._is_futures = self._state is not None and self._state.asset_class == "futures"
        self._safety: FuturesSafety | None = load_futures_safety() if self._is_futures else None
```

(c) In `should_exit`, after computing `pnl_pct` (line 93) and BEFORE the existing "1) Hard stop loss" block, insert the futures-forced checks:

```python
        # Futures auto-enforced safety (cannot be disabled by the user).
        if self._is_futures and self._safety is not None:
            # EOD time close (KST) — highest priority.
            now = context.timestamp
            now_kst = (
                now.astimezone(_KST) if now.tzinfo is not None else now.replace(tzinfo=_KST)
            )
            if now_kst.time() >= self._safety.eod_close_time:
                return True, self._make_signal(
                    position=position,
                    current_price=current_price,
                    entry_price=entry_price,
                    pnl_pct=pnl_pct,
                    reason=ExitReason.EOD_CLOSE,
                    confidence=1.0,
                    note="futures_eod_close",
                )
            # Hard-stop cap: take the tighter of the user's stop and the cap;
            # the cap also applies when the user disabled their stop (<= 0).
            cap = self._safety.hard_stop_pct
            user_stop = self.config.stop_loss_pct
            effective_stop = cap if user_stop <= 0 else min(user_stop, cap)
            if pnl_pct <= -effective_stop:
                return True, self._make_signal(
                    position=position,
                    current_price=current_price,
                    entry_price=entry_price,
                    pnl_pct=pnl_pct,
                    reason=ExitReason.STOP_LOSS,
                    confidence=1.0,
                    note="futures_hard_stop",
                )
```

(The existing stock SL/TP/condition blocks remain unchanged below this insert.)

- [ ] **Step 6: Run the exit tests**

Run: `.venv/bin/pytest tests/unit/strategy/test_builder_strategy.py -v`
Expected: PASS (futures cap/EOD fire; stock behavior unchanged).

- [ ] **Step 7: Commit**

```bash
git add config/strategy_builder/futures_safety.yaml shared/strategy_builder/futures_safety.py \
        shared/strategy/exit/builder_strategy_exit.py tests/unit/strategy/test_builder_strategy.py
git commit -m "feat(builder): auto-enforce EOD close + hard-stop cap for futures exits

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 2.3: Backend gate whitelist + futures position sizing

**Files:**
- Modify: `services/dashboard/routes/kis_builder.py`
- Test: `tests/unit/dashboard/test_strategy_builder.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/dashboard/test_strategy_builder.py`:

```python
def _futures_register_state(strategy_id: str = "fut_reg_test") -> dict:
    return {
        "metadata": {
            "id": strategy_id,
            "name": "Fut Reg",
            "description": "",
            "category": "custom",
            "tags": ["t"],
            "author": "u",
        },
        "asset_class": "futures",
        "indicators": [
            {"indicator_id": "rsi", "alias": "rsi", "params": {}, "output": "value"}
        ],
        "entry": {
            "logic": "AND",
            "conditions": [
                {
                    "left": {"type": "indicator", "indicator_alias": "rsi", "indicator_output": "value"},
                    "operator": "greater_than",
                    "right": {"type": "value", "value": 30.0},
                }
            ],
        },
        "exit": {"logic": "AND", "conditions": []},
        "risk": {"stop_loss": {"enabled": True, "percent": 5.0}},
    }


@pytest.mark.asyncio
async def test_register_paper_accepts_futures_and_uses_contract_sizing(tmp_path, monkeypatch):
    import yaml as _yaml

    from services.dashboard.routes import kis_builder

    monkeypatch.setattr(kis_builder, "_BUILT_STRATEGIES_DIR", tmp_path)

    result = await kis_builder.register_paper_strategy(
        kis_builder.RegisterPaperRequest(
            builder_state=_futures_register_state(), contracts=2
        )
    )
    assert result.asset_class == "futures"

    doc = _yaml.safe_load((tmp_path / "fut_reg_test.yaml").read_text(encoding="utf-8"))
    position = doc["strategy"]["position"]
    assert position["type"] == "fixed"
    assert position["params"]["fixed_quantity"] == 2
    assert "order_amount_per_stock" not in position["params"]


@pytest.mark.asyncio
async def test_register_paper_rejects_unknown_asset_class(tmp_path, monkeypatch):
    from fastapi import HTTPException

    from services.dashboard.routes import kis_builder

    monkeypatch.setattr(kis_builder, "_BUILT_STRATEGIES_DIR", tmp_path)
    bad = _futures_register_state("bad_asset")
    bad["asset_class"] = "options"

    with pytest.raises(HTTPException) as exc:
        await kis_builder.register_paper_strategy(
            kis_builder.RegisterPaperRequest(builder_state=bad)
        )
    assert exc.value.status_code == 400
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/unit/dashboard/test_strategy_builder.py -k "futures or unknown_asset" -v`
Expected: FAIL — futures rejected by the current stock-only gate; `contracts` arg unknown.

- [ ] **Step 3: Relax the gate (`_validate_builder_state`, lines 681-689)**

Replace:

```python
    if state.asset_class != "stock":
        raise HTTPException(
            status_code=400,
            detail=(
                "builder→paper registration is stock-only in Phase 1. "
                "Futures strategies stay on the dedicated entry classes "
                "(setup_a/setup_c/bb_reversion_15m)."
            ),
        )
```

with:

```python
    # Builder→paper supports stock and (long-only, paper) futures. Futures
    # live activation stays behind config/futures_live.yaml + the Redis
    # suspend flag — registration only materializes a paper YAML.
    if state.asset_class not in ("stock", "futures"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported asset_class: {state.asset_class!r} "
                "(expected 'stock' or 'futures')."
            ),
        )
```

- [ ] **Step 4: Add a `contracts` field to `RegisterPaperRequest` (after line 616)**

```python
    order_amount: int = Field(default=1_000_000, ge=0)
    contracts: int = Field(default=1, ge=1, description="Futures contract count (futures only)")
    cooldown_seconds: int = Field(default=0, ge=0)
```

- [ ] **Step 5: Thread `contracts` through `register_paper_strategy` → `_build_strategy_yaml`**

In `register_paper_strategy` (the `_build_strategy_yaml(...)` call, ~line 755), add the `contracts` kwarg:

```python
    yaml_doc = _build_strategy_yaml(
        state=state,
        stop_loss_pct=body.stop_loss_pct,
        take_profit_pct=body.take_profit_pct,
        order_amount=body.order_amount,
        contracts=body.contracts,
        cooldown_seconds=body.cooldown_seconds,
        min_confidence=body.min_confidence,
        enabled=False,  # Phase-1 safe default
    )
```

- [ ] **Step 6: Branch position sizing in `_build_strategy_yaml`**

(a) Add `contracts: int = 1` to the signature (after `order_amount: int,`).

(b) Replace the hardcoded `"position"` block (currently `{"type": "fixed", "params": {"order_amount_per_stock": order_amount}}`) by computing it from `asset_class`. Just before the `return {...}`, add:

```python
    asset_class = state.get("asset_class", "stock")
    if asset_class == "futures":
        position = {"type": "fixed", "params": {"fixed_quantity": contracts}}
    else:
        position = {"type": "fixed", "params": {"order_amount_per_stock": order_amount}}
```

and use `"position": position,` in the returned dict in place of the inline literal.

- [ ] **Step 7: Run the tests**

Run: `.venv/bin/pytest tests/unit/dashboard/test_strategy_builder.py -v`
Expected: PASS (futures registers with `fixed_quantity`; unknown asset → 400; stock path unchanged).

- [ ] **Step 8: Commit**

```bash
git add services/dashboard/routes/kis_builder.py tests/unit/dashboard/test_strategy_builder.py
git commit -m "feat(builder): allow futures register-paper with contract sizing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 2.4: Frontend types — assetClass, futuresApplicability, action

**Files:**
- Modify: `strategy-builder-ui/src/types/builder.ts`

- [ ] **Step 1: Add `assetClass` to `BuilderState`** (interface at lines 124-130):

```typescript
export interface BuilderState {
  metadata: BuilderMetadata;
  assetClass: "stock" | "futures";
  indicators: BuilderIndicator[];
  entry: BuilderConditionGroup;
  exit: BuilderConditionGroup;
  risk: RiskManagement;
}
```

- [ ] **Step 2: Add `futuresApplicability` to `IndicatorDefinition`** (after `leanUnsupported?` at line 44):

```typescript
  leanUnsupported?: boolean; // true면 Lean 백테스트 미지원 (p1 자체 실행은 가능)
  /** "degraded": 코스피200 미니의 낮은 유동성에서 신뢰도 저하 (선물 모드 자문 경고용, 차단 아님) */
  futuresApplicability?: "ok" | "degraded";
```

- [ ] **Step 3: Add the `SET_ASSET_CLASS` action** (in the `BuilderAction` union, after `SET_METADATA` at line 208):

```typescript
  | { type: "SET_ASSET_CLASS"; payload: "stock" | "futures" }
```

- [ ] **Step 4: Commit**

```bash
git add strategy-builder-ui/src/types/builder.ts
git commit -m "feat(builder-ui): add assetClass + futuresApplicability types

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 2.5: Reducer/hook — INITIAL_STATE + setAssetClass

**Files:**
- Modify: `strategy-builder-ui/src/hooks/useStrategyBuilder.ts`

- [ ] **Step 1: Add `assetClass` to `INITIAL_STATE`** (after the `metadata` block, line 476):

```typescript
export const INITIAL_STATE: BuilderState = {
  metadata: {
    id: "",
    name: "custom_strategy",
    description: "직접 만든 전략입니다",
    category: "custom",
    tags: [],
    author: "user",
  },
  assetClass: "stock",
  indicators: [],
```

- [ ] **Step 2: Add the reducer case** (after the `SET_METADATA` case, line 503):

```typescript
    case "SET_ASSET_CLASS":
      return { ...state, assetClass: action.payload };
```

- [ ] **Step 3: Default `assetClass` when loading external states**

Find the `LOAD_STATE` case (it currently returns `action.payload`). Replace its body with a default-coalescing return so presets/imported YAML lacking `assetClass` stay valid:

```typescript
    case "LOAD_STATE":
      return { ...action.payload, assetClass: action.payload.assetClass ?? "stock" };
```

- [ ] **Step 4: Expose `setAssetClass` from the hook**

Locate the existing dispatch wrappers (e.g. `setMetadata`) returned by `useStrategyBuilder`. Add a sibling, mirroring `setMetadata`'s definition and include it in the returned object:

```typescript
  const setAssetClass = useCallback(
    (assetClass: "stock" | "futures") =>
      dispatch({ type: "SET_ASSET_CLASS", payload: assetClass }),
    [],
  );
```

(Add `setAssetClass` to the object the hook returns, next to `setMetadata`/`loadState`.)

- [ ] **Step 5: Typecheck**

Run: `cd strategy-builder-ui && npx tsc --noEmit`
Expected: no errors. (If `BuilderState` literals elsewhere now error for missing `assetClass`, add `assetClass: "stock"` to them — e.g. any test/mocks/presets defaults.)

- [ ] **Step 6: Commit**

```bash
git add strategy-builder-ui/src/hooks/useStrategyBuilder.ts
git commit -m "feat(builder-ui): assetClass in initial state + setAssetClass action

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 2.6: Asset-class toggle in the builder header

**Files:**
- Modify: `strategy-builder-ui/src/app/builder/page.tsx`

- [ ] **Step 1: Render a segmented toggle above the STEPS navigation**

`useStrategyBuilder()` is already destructured as `builder` (`page.tsx:66`). In the main builder panel, immediately above the STEPS nav (the element rendering the `STEPS` array), add:

```tsx
<div className="mb-4 flex items-center gap-2">
  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">자산군</span>
  <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700 p-0.5">
    {(["stock", "futures"] as const).map((ac) => (
      <button
        key={ac}
        type="button"
        onClick={() => builder.setAssetClass(ac)}
        className={cn(
          "px-3 py-1 text-sm rounded-md transition-colors",
          builder.state.assetClass === ac
            ? "bg-blue-600 text-white"
            : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800",
        )}
      >
        {ac === "stock" ? "주식" : "선물"}
      </button>
    ))}
  </div>
  {builder.state.assetClass === "futures" && (
    <span className="text-xs text-amber-600 dark:text-amber-400">
      선물은 long-only (Phase 1) · EOD 15:15·하드스톱 자동 적용
    </span>
  )}
</div>
```

(`cn` is already imported at `page.tsx:17`.)

- [ ] **Step 2: Typecheck + lint**

Run: `cd strategy-builder-ui && npx tsc --noEmit && npm run lint`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add strategy-builder-ui/src/app/builder/page.tsx
git commit -m "feat(builder-ui): asset-class toggle in builder header

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 2.7: Mark volume-dependent indicators as degraded for futures

**Files:**
- Modify: `strategy-builder-ui/src/lib/builder/constants.ts`

- [ ] **Step 1: Add `futuresApplicability: "degraded"` to volume-magnitude-dependent indicators**

These rely on reliable intraday volume, which KOSPI200 mini futures lack (1/9–1/42 of F200 liquidity). Edit the `vwap` (line 686), `vwma` (line 695), `eom` (line 705), and `obv` (line 626) entries, adding the field after `defaultOutput`. Example for `vwap`:

```typescript
  {
    id: "vwap",
    name: "VWAP",
    nameKo: "VWAP",
    category: "volume",
    description: "거래량 가중 평균가",
    params: [{ name: "period", type: "number", default: 14, min: 1, max: 500 }],
    outputs: [{ id: "value", name: "값" }],
    defaultOutput: "value",
    futuresApplicability: "degraded",
  },
```

Apply the same one-line addition to `vwma`, `eom`, and `obv`.

- [ ] **Step 2: Typecheck**

Run: `cd strategy-builder-ui && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add strategy-builder-ui/src/lib/builder/constants.ts
git commit -m "feat(builder-ui): tag volume indicators as futures-degraded

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 2.8: Advisory badge in IndicatorSelector

**Files:**
- Modify: `strategy-builder-ui/src/components/builder/IndicatorSelector.tsx`
- Modify: `strategy-builder-ui/src/app/builder/page.tsx`

- [ ] **Step 1: Add `assetClass` to the props** (interface at lines 16-22 + destructure at 35-41):

```typescript
interface IndicatorSelectorProps {
  selectedIndicators: BuilderIndicator[];
  onAddIndicator: (indicator: BuilderIndicator) => void;
  onUpdateIndicator: (id: string, updates: Partial<BuilderIndicator>) => void;
  onRemoveIndicator: (id: string) => void;
  createIndicator: (indicatorId: string, alias?: string) => BuilderIndicator | null;
  assetClass: "stock" | "futures";
}
```

```typescript
export function IndicatorSelector({
  selectedIndicators,
  onAddIndicator,
  onUpdateIndicator,
  onRemoveIndicator,
  createIndicator,
  assetClass,
}: IndicatorSelectorProps) {
```

- [ ] **Step 2: Render the advisory badge in the add-list**

In the add-panel list (the `filteredIndicators.slice(0, 20).map((def) => {` block at line 399), beside the existing `def.leanUnsupported` branch (~line 439), add a futures-degraded badge. Mirror the `leanUnsupported` amber span:

```tsx
                    {assetClass === "futures" && def.futuresApplicability === "degraded" && (
                      <span
                        className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 rounded"
                        title="코스피200 미니의 낮은 유동성에서 신뢰도 저하 — 선물 권장 안 함"
                      >
                        선물 권장 안 함
                      </span>
                    )}
```

(Insert it adjacent to where each indicator's name/label renders so it shows in the picker. It is advisory only — do NOT disable the add button.)

- [ ] **Step 3: Pass `assetClass` from page.tsx**

Find where `<IndicatorSelector ... />` is rendered in `page.tsx` and add the prop:

```tsx
              assetClass={builder.state.assetClass}
```

- [ ] **Step 4: Typecheck + lint**

Run: `cd strategy-builder-ui && npx tsc --noEmit && npm run lint`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add strategy-builder-ui/src/components/builder/IndicatorSelector.tsx strategy-builder-ui/src/app/builder/page.tsx
git commit -m "feat(builder-ui): advisory badge for futures-degraded indicators

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 2.9: Registration client — send assetClass, drop stale comment

**Files:**
- Modify: `strategy-builder-ui/src/lib/api/strategies.ts`
- Modify: `strategy-builder-ui/src/components/builder/CustomStrategyList.tsx`

- [ ] **Step 1: Add `contracts` to `RegisterPaperRequest`** (`strategies.ts`, in the interface around line 140):

```typescript
export interface RegisterPaperRequest {
  builder_state: BuilderState;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  order_amount?: number;
  contracts?: number;
  cooldown_seconds?: number;
  min_confidence?: number;
}
```

- [ ] **Step 2: Update the stale comment + register call in `CustomStrategyList.tsx`** (lines 64-74)

`strategy.state` now carries `assetClass`, so the backend routes futures correctly. Replace the comment block (lines 64-67) and the `registerPaperStrategy` call:

```typescript
      // builder_state now carries assetClass (stock/futures); the backend
      // routes futures to contract sizing + auto-enforced exit safety. Phase 1
      // futures registers as 1 contract (backend default).
      setRegisteringId(strategy.id);
      try {
        await registerPaperStrategy({
          builder_state: strategy.state,
        });
```

- [ ] **Step 3: Typecheck + lint + build**

Run: `cd strategy-builder-ui && npx tsc --noEmit && npm run lint && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add strategy-builder-ui/src/lib/api/strategies.ts strategy-builder-ui/src/components/builder/CustomStrategyList.tsx
git commit -m "feat(builder-ui): send assetClass on register; add contracts field

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task 2.10: Full verification + PR 2

- [ ] **Step 1: Backend suite**

Run: `.venv/bin/pytest tests/unit/strategy/test_builder_strategy.py tests/unit/strategy_builder/ tests/unit/dashboard/test_strategy_builder.py -v`
Expected: PASS.

- [ ] **Step 2: Lint/format the backend changes**

Run: `black shared/strategy_builder/futures_safety.py shared/strategy/exit/builder_strategy_exit.py shared/strategy/entry/builder_strategy.py services/dashboard/routes/kis_builder.py shared/strategy_builder/schema.py && ruff check --fix shared/ services/`
Expected: clean.

- [ ] **Step 3: Frontend build**

Run: `cd strategy-builder-ui && npm run lint && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Manual smoke (optional, requires dashboard running)**

Build a futures RSI strategy in `/builder`, register to paper, confirm `config/strategies/built/<id>.yaml` has `asset_class: futures`, `entry.type: builder_v1`, `exit.type: builder_v1_exit`, `position.params.fixed_quantity`.

- [ ] **Step 5: Push & open PR 2**

```bash
git push -u origin feat/futures-strategy-builder
gh pr create --base main --title "feat: futures strategy builder (Phase 1, long-only paper)" \
  --body "Extends the no-code builder to long-only indicator-based futures strategies (paper). Depends on the serialization fix PR. Spec: docs/superpowers/specs/2026-06-01-futures-strategy-builder-design.md"
```

---

## Acceptance criteria mapping (from spec §8)

| Spec criterion | Task |
|---|---|
| `/builder` 자산군 선물 전환 + `assetClass: "futures"` 반영 | 2.4, 2.5, 2.6 |
| 미니 부적합 지표 자문 배지 (차단 없음) | 2.7, 2.8 |
| 선물 register-paper 400 없이 `built/<id>.yaml` 생성 | 1.1–1.3 (serialization), 2.3 |
| 등록된 선물 전략이 `load_all_strategies("futures")`로 픽업 | 2.3 (asset_class tagging — loader already filters built/) |
| 하드스톱 상한 + EOD 15:15 강제 (테스트 증명) | 2.2 |
| 선물 진입 long-only + 표기 | 2.1, 2.6 |
| 주식 빌더 회귀 없음 | 1.2 step 4, 2.1 step 4, 2.2 (`test_stock_exit_unaffected`), 2.3 |
| 선물 live 미활성화 (게이트 불변) | 2.3 (gate comment; no futures_live.yaml change) |
| `.venv/bin/pytest tests/ -v` 그린 | 2.10 |

## Notes / deferred (Phase 2)

- Short selling (direction selector, bidirectional evaluator/exit math).
- Per-strategy contract-count UI input (Phase 1 uses backend default = 1 contract).
- Candlestick conditions in register-paper remain unsupported (frontend candlestick fields are not in the snake_case `extra="forbid"` ConditionOperand tree).
- UI symbol/contract selector + UI backtest button.
