# Futures RL_mppo Replacement — P0+P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the infrastructure + decisive harness that lets a futures indicator candidate be *trustworthily* validated — durable LLM-context history, a strategy-agnostic robust-gate runner, williams_r wired to a genuine 15-min contract, and a recorded gate verdict.

**Architecture:** P0 = forward-only `llm_market_context` ClickHouse write-through (unblocks honest LLM-bias replay later). P1 = extract the re-scoped robust gate into a shared module (DRY), expose it as a generalized CLI, wire williams_r to a true 15-min timeframe (mirroring the bb_reversion_15m `momentum_<tf>`/`mtf_base_<tf>`/`DecisionCadenceGate` pattern), then run the gate and record a terminal PASS/FAIL verdict.

**Tech Stack:** Python 3.11, `clickhouse_driver` (sync, native port 9000), Optuna TPE, existing `BacktestEngine`/`BacktestStrategyAdapter`, pytest (run via `.venv/bin/pytest`).

**Spec:** `docs/superpowers/specs/2026-05-19-futures-rlmppo-replacement-indicator-research-design.md` (read §7 gate, §8 safety, §12 corrections).

**Branch/worktree:** all work on `docs/futures-rlmppo-replacement-research` in worktree `/home/deploy/wt-futures-rlmppo-research`. NEVER commit to `main` or `runtime/main-current`. Every commit ends with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`. Stage explicit paths only (never `git add -A`).

**Test invocation (mandatory):** `cd /home/deploy/wt-futures-rlmppo-research && .venv/bin/pytest <path> -v` (system pytest lacks `pytest-mock` → `mocker not found`; the venv is required — project memory).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `shared/db/client.py` (modify) | Add `llm_market_context` DDL to `SCHEMAS` + `insert_llm_market_context()` | 1 |
| `tests/unit/db/test_llm_market_context_schema.py` (create) | Schema-entry + insert-SQL shape (no socket) | 1 |
| `services/trading/llm_context_publisher.py` (modify) | Best-effort CH write-through after Redis publish | 2 |
| `tests/unit/trading/test_llm_context_writethrough.py` (create) | Redis-always + CH-failure-isolated | 2 |
| `shared/backtest/robust_gate.py` (create) | DRY home of `rescoped_gate` + `objective_value` + floor constants | 3 |
| `scripts/optimize_llm_directed_indicator.py` (modify) | Import from the shared module (delete local copies) | 3 |
| `tests/unit/backtest/test_robust_gate.py` (create) | a/b/c gate logic + min-trades floor | 3 |
| `scripts/gate_futures_strategy.py` (create) | Strategy-agnostic robust-gate CLI | 4 |
| `config/optuna/futures/williams_r_15m.yaml` (create) | williams_r search space + holdout/min-trades | 4 |
| `tests/unit/backtest/test_gate_cli_paramspace.py` (create) | param-space load + dotted-path apply | 4 |
| `shared/strategy/entry/williams_r.py` (modify) | `timeframe_minutes` → `momentum_<tf>m`+`mtf_base_<tf>m` | 5 |
| `config/strategies/futures/williams_r_15m.yaml` (modify) | real `timeframe_minutes: 15` + `backtest` block | 5 |
| `tests/unit/strategy/test_williams_r_timeframe.py` (create) | contract changes by tf; cadence no-op @tf=1 | 5 |
| `reports/optuna/WILLIAMS_R_15M_GATE.md` (create) | Recorded terminal verdict (PASS→P2 / FAIL→§③) | 6 |

---

### Task 1: `llm_market_context` ClickHouse schema + insert

**Files:**
- Modify: `shared/db/client.py` (`SCHEMAS` dict ~32-180; add method near `insert_daily_candles` ~387-402)
- Test: `tests/unit/db/test_llm_market_context_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/db/test_llm_market_context_schema.py
import datetime as dt
import pytest


def test_schema_entry_exists_and_formats():
    from shared.db.client import SCHEMAS
    assert "llm_market_context" in SCHEMAS
    ddl = SCHEMAS["llm_market_context"].format(database="market")
    assert "CREATE TABLE IF NOT EXISTS market.llm_market_context" in ddl
    assert "ORDER BY (asset, ts)" in ddl
    assert "PARTITION BY toYYYYMM(ts)" in ddl


def test_insert_builds_expected_sql_and_tuples(monkeypatch):
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    ClickHouseClient.reset_singleton()
    client = ClickHouseClient(ClickHouseConfig(
        host="localhost", port=9000, database="market",
        user="default", password=""))

    captured = {}

    class FakeSync:
        def execute(self, sql, data=None):
            captured["sql"] = sql
            captured["data"] = data
            return len(data) if data else 0

    monkeypatch.setattr(client, "get_sync_client", lambda: FakeSync())

    rows = [{
        "ts": dt.datetime(2026, 5, 19, 1, 0, 0),
        "asset": "futures", "regime": "NEUTRAL",
        "overall_signal": "NEUTRAL", "risk_mode": "NEUTRAL",
        "risk_score": 50.0, "confidence": 0.5,
        "generated_at": dt.datetime(2026, 5, 19, 0, 59, 0),
        "metadata_json": "{}",
    }]
    n = client.insert_llm_market_context(rows)
    assert n == 1
    assert "INSERT INTO market.llm_market_context" in captured["sql"]
    assert captured["data"] == [(
        dt.datetime(2026, 5, 19, 1, 0, 0), "futures", "NEUTRAL",
        "NEUTRAL", "NEUTRAL", 50.0, 0.5,
        dt.datetime(2026, 5, 19, 0, 59, 0), "{}",
    )]


def test_insert_empty_returns_zero():
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig
    ClickHouseClient.reset_singleton()
    client = ClickHouseClient(ClickHouseConfig(
        host="localhost", port=9000, database="market",
        user="default", password=""))
    assert client.insert_llm_market_context([]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/db/test_llm_market_context_schema.py -v`
Expected: FAIL — `KeyError: 'llm_market_context'` / `AttributeError: ... insert_llm_market_context`.

- [ ] **Step 3: Add the DDL to `SCHEMAS`**

Add this entry inside the `SCHEMAS` dict in `shared/db/client.py` (alongside `"rl_trades"`), keeping the existing `{database}` format convention:

```python
"llm_market_context": """
    CREATE TABLE IF NOT EXISTS {database}.llm_market_context (
        ts DateTime64(3),
        asset LowCardinality(String),
        regime LowCardinality(String),
        overall_signal LowCardinality(String),
        risk_mode LowCardinality(String),
        risk_score Float64,
        confidence Float64,
        generated_at DateTime64(3),
        metadata_json String,
        created_at DateTime DEFAULT now()
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(ts)
    ORDER BY (asset, ts)
    TTL toDateTime(ts) + INTERVAL 2 YEAR
    COMMENT 'Durable forward-only LLM market_context history for backtest replay (spec 2026-05-19 P0)'
""",
```

- [ ] **Step 4: Add the insert method**

Add directly below `insert_daily_candles` in `shared/db/client.py`, mirroring its exact shape (sync client, list-of-tuples, broad except → log + return 0):

```python
def insert_llm_market_context(self, rows: list[dict]) -> int:
    """Append LLM market_context snapshots (best-effort durable history)."""
    if not rows:
        return 0
    try:
        client = self.get_sync_client()
        data = [
            (
                r["ts"], r["asset"], r["regime"], r["overall_signal"],
                r["risk_mode"], float(r["risk_score"]),
                float(r["confidence"]), r["generated_at"],
                r["metadata_json"],
            )
            for r in rows
        ]
        client.execute(
            f"INSERT INTO {self.config.database}.llm_market_context "
            "(ts, asset, regime, overall_signal, risk_mode, "
            "risk_score, confidence, generated_at, metadata_json) VALUES",
            data,
        )
        return len(rows)
    except Exception as e:
        logger.error(f"Failed to insert llm_market_context: {e}")
        return 0
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/db/test_llm_market_context_schema.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Regression — DB client suite still green**

Run: `.venv/bin/pytest tests/unit/db/ -v`
Expected: PASS (no regressions in `test_client_thread_safety.py` etc.).

- [ ] **Step 7: Commit**

```bash
cd /home/deploy/wt-futures-rlmppo-research
git add shared/db/client.py tests/unit/db/test_llm_market_context_schema.py
git commit -m "$(cat <<'EOF'
feat(db): llm_market_context table + insert (spec 2026-05-19 P0)

Forward-only durable history of LLM market_context for future
backtest replay. MergeTree, ORDER BY (asset, ts), 2y TTL.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: LLMContextPublisher write-through (Redis unchanged; CH best-effort)

**Files:**
- Modify: `services/trading/llm_context_publisher.py` (`publish_to_redis` ~416-438)
- Test: `tests/unit/trading/test_llm_context_writethrough.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/trading/test_llm_context_writethrough.py
import datetime as dt
import pytest
from shared.llm.market_context import MarketContext


def _ctx():
    return MarketContext()  # defaults: NEUTRAL / 50.0 / 0.5


def test_redis_published_and_history_appended(monkeypatch):
    from services.trading import llm_context_publisher as mod

    redis_calls, ch_rows = [], []

    class FakePublisher:
        def __init__(self, asset): self.asset = asset
        def publish_market_context(self, ctx): redis_calls.append(ctx)

    class FakeCH:
        def insert_llm_market_context(self, rows): ch_rows.extend(rows); return len(rows)

    monkeypatch.setattr(
        "shared.streaming.trading_state.TradingStatePublisher", FakePublisher)
    monkeypatch.setattr(
        "shared.db.client.get_clickhouse_client", lambda cfg=None: FakeCH())

    pub = mod.LLMContextPublisher.__new__(mod.LLMContextPublisher)
    pub.asset_class = "futures"
    pub.publish_to_redis(_ctx())

    assert len(redis_calls) == 1
    assert len(ch_rows) == 1
    assert ch_rows[0]["asset"] == "futures"
    assert ch_rows[0]["overall_signal"] == "NEUTRAL"
    assert ch_rows[0]["confidence"] == 0.5


def test_clickhouse_failure_does_not_break_redis(monkeypatch):
    from services.trading import llm_context_publisher as mod
    redis_calls = []

    class FakePublisher:
        def __init__(self, asset): pass
        def publish_market_context(self, ctx): redis_calls.append(ctx)

    class BoomCH:
        def insert_llm_market_context(self, rows): raise RuntimeError("CH down")

    monkeypatch.setattr(
        "shared.streaming.trading_state.TradingStatePublisher", FakePublisher)
    monkeypatch.setattr(
        "shared.db.client.get_clickhouse_client", lambda cfg=None: BoomCH())

    pub = mod.LLMContextPublisher.__new__(mod.LLMContextPublisher)
    pub.asset_class = "futures"
    pub.publish_to_redis(_ctx())  # must NOT raise

    assert len(redis_calls) == 1  # Redis still happened
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/trading/test_llm_context_writethrough.py -v`
Expected: FAIL — `test_redis_published_and_history_appended` fails (`ch_rows` empty: no write-through yet).

- [ ] **Step 3: Implement the write-through**

In `services/trading/llm_context_publisher.py`, replace the body of `publish_to_redis` so the Redis publish is unchanged and a best-effort history append runs *after* it (its own isolated try/except — ClickHouse failure must never propagate):

```python
def publish_to_redis(self, context: MarketContext) -> None:
    try:
        from shared.streaming.trading_state import TradingStatePublisher
        publisher = TradingStatePublisher(self.asset_class)
        publisher.publish_market_context(context)
        logger.debug(
            "Published LLM market context to Redis: asset=%s regime=%s confidence=%.2f",
            self.asset_class, context.regime, context.confidence,
        )
    except Exception as e:
        logger.debug(
            "Failed to publish LLM market context to Redis: %s", e, exc_info=True)
    # Durable forward-only history for future backtest replay
    # (spec 2026-05-19 P0). Best-effort: CH failure must not affect live.
    self._append_market_context_history(context)

def _append_market_context_history(self, context: MarketContext) -> None:
    try:
        import json as _json
        from datetime import datetime, timezone
        from shared.db.client import get_clickhouse_client
        from shared.db.config import ClickHouseConfig

        gen = context.generated_at
        if getattr(gen, "tzinfo", None) is not None:
            gen = gen.replace(tzinfo=None)
        row = {
            "ts": datetime.now(timezone.utc).replace(tzinfo=None),
            "asset": self.asset_class,
            "regime": str(context.regime),
            "overall_signal": getattr(
                context.overall_signal, "value", str(context.overall_signal)),
            "risk_mode": getattr(
                context.risk_mode, "value", str(context.risk_mode)),
            "risk_score": float(context.risk_score),
            "confidence": float(context.confidence),
            "generated_at": gen,
            "metadata_json": _json.dumps(
                context.metadata or {}, ensure_ascii=False),
        }
        get_clickhouse_client(ClickHouseConfig.from_env()).insert_llm_market_context([row])
    except Exception as e:
        logger.debug(
            "llm_market_context history append skipped: %s", e, exc_info=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/trading/test_llm_context_writethrough.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Regression — publisher import path**

Run: `.venv/bin/pytest tests/unit/trading/ -v -k "llm_context or publisher"`
Expected: PASS (no regressions).

- [ ] **Step 6: Commit**

```bash
cd /home/deploy/wt-futures-rlmppo-research
git add services/trading/llm_context_publisher.py tests/unit/trading/test_llm_context_writethrough.py
git commit -m "$(cat <<'EOF'
feat(trading): LLM context CH write-through (spec 2026-05-19 P0)

publish_to_redis() now also appends to llm_market_context
(forward-only history). Best-effort: ClickHouse failure is
isolated and never affects the live Redis path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Extract the re-scoped gate into a DRY shared module

**Files:**
- Create: `shared/backtest/robust_gate.py`
- Modify: `scripts/optimize_llm_directed_indicator.py` (delete local `_rescoped_gate` ~228-275 and `_objective_value` ~183-208; import from the module; keep aliases so the rest of the script is untouched)
- Test: `tests/unit/backtest/test_robust_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/backtest/test_robust_gate.py
from shared.backtest.robust_gate import (
    rescoped_gate, objective_value,
    FLOOR_SHARPE, FLOOR_PF, FLOOR_BASIN_FRAC, SENTINEL,
)


class _T:
    def __init__(self, value, pf):
        self.value = value
        self.user_attrs = {"profit_factor": pf}


class _Study:
    def __init__(self, trials): self.trials = trials


def test_pass_when_distribution_robust_and_oos_ok():
    trials = [_T(1.0, 1.5)] * 8 + [_T(-0.2, 0.9)] * 2  # 80% clear floor
    oos = {"sharpe_ratio": 1.2, "profit_factor": 1.4,
           "max_drawdown_pct": 10.0, "total_return_pct": 30.0}
    r = rescoped_gate(_Study(trials), oos)
    assert r["a"] and r["b"] and r["c"] and r["pass"]


def test_fail_single_lucky_outlier():
    trials = [_T(5.0, 4.0)] + [_T(-2.0, 0.7)] * 39  # 1/40 basin
    oos = {"sharpe_ratio": 8.0, "profit_factor": 3.0,
           "max_drawdown_pct": 7.0, "total_return_pct": 100.0}
    r = rescoped_gate(_Study(trials), oos)
    assert r["a"] is False and r["b"] is False and r["pass"] is False


def test_objective_value_min_trades_floor():
    assert objective_value(
        {"total_trades": 10, "sharpe_ratio": 3.0}, 50) <= SENTINEL + 0.1
    assert objective_value(
        {"total_trades": 80, "sharpe_ratio": 1.4}, 50) == 1.4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/backtest/test_robust_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: shared.backtest.robust_gate`.

- [ ] **Step 3: Create the shared module — move the gate VERBATIM**

Create `shared/backtest/robust_gate.py`. Cut `_rescoped_gate` (currently `scripts/optimize_llm_directed_indicator.py:228-275`) and `_objective_value` (`:183-208`) **verbatim** into it (rename to public `rescoped_gate` / `objective_value`; keep the constants). Use exactly the function bodies as they exist in the script — do not paraphrase. Skeleton with the verified `rescoped_gate` body:

```python
"""Re-scoped robust non-catastrophic gate (spec 2026-05-16 §6 / 2026-05-19 §7).

Single DRY home shared by scripts/optimize_llm_directed_indicator.py and
scripts/gate_futures_strategy.py. Logic moved verbatim 2026-05-19.
"""
from __future__ import annotations
import statistics as _st

SENTINEL = -10.0
FLOOR_SHARPE = 0.0
FLOOR_PF = 1.0
FLOOR_BASIN_FRAC = 0.25
OOS_MDD_MAX = 25.0
OOS_RET_MIN = 0.0


def rescoped_gate(study, oos_m: dict[str, float]) -> dict[str, object]:
    valid = [
        t for t in study.trials
        if t.value is not None and t.value > SENTINEL + 0.1
    ]
    n = len(valid)
    sh = [t.value for t in valid]
    pf = [float(t.user_attrs.get("profit_factor", 0.0)) for t in valid]
    pf_finite = [p for p in pf if p == p and p != float("inf")]
    med_s = _st.median(sh) if sh else float("nan")
    med_pf = _st.median(pf_finite) if pf_finite else float("nan")
    a = (n > 0) and med_s >= FLOOR_SHARPE and med_pf >= FLOOR_PF
    cleared = sum(
        1 for t in valid
        if t.value >= FLOOR_SHARPE
        and float(t.user_attrs.get("profit_factor", 0.0)) >= FLOOR_PF
    )
    frac = (cleared / n) if n else 0.0
    b = frac >= FLOOR_BASIN_FRAC
    c = bool(oos_m) and (
        oos_m.get("sharpe_ratio", -99) >= FLOOR_SHARPE
        and oos_m.get("profit_factor", 0.0) >= FLOOR_PF
        and oos_m.get("max_drawdown_pct", 1e9) <= OOS_MDD_MAX
        and oos_m.get("total_return_pct", -1e9) >= OOS_RET_MIN
    )
    return {
        "n_valid": n, "median_sharpe": med_s, "median_pf": med_pf,
        "basin_frac": frac, "basin_cleared": cleared,
        "a": a, "b": b, "c": c, "pass": bool(a and b and c),
    }


def objective_value(metrics: dict, min_trades: int) -> float:
    """Optuna objective with the mandatory min-trades floor.

    MOVE VERBATIM from scripts/optimize_llm_directed_indicator.py:183-208
    (`_objective_value`). Preserve its exact behaviour: reject with SENTINEL
    when no trades / trades < max(1, min_trades) / NaN / abs(sharpe) > 100;
    otherwise return float(sharpe).
    """
    trades = int(metrics.get("total_trades", 0) or 0)
    sharpe = metrics.get("sharpe_ratio", None)
    if not trades or trades < max(1, min_trades):
        return SENTINEL
    if sharpe is None or sharpe != sharpe or abs(float(sharpe)) > 100:
        return SENTINEL
    return float(sharpe)
```

> Implementer: open `scripts/optimize_llm_directed_indicator.py:183-208` and confirm the `objective_value` body matches the script's `_objective_value` exactly (the script is the source of truth); reconcile any divergence in favour of the script's behaviour before proceeding.

- [ ] **Step 4: Retrofit the script to import the module (DRY)**

In `scripts/optimize_llm_directed_indicator.py`: delete the local `_rescoped_gate` and `_objective_value` definitions and the now-duplicated floor constants; add near the top:

```python
from shared.backtest.robust_gate import (
    rescoped_gate as _rescoped_gate,
    objective_value as _objective_value,
    SENTINEL as _SENTINEL,
    FLOOR_SHARPE as _FLOOR_SHARPE,
    FLOOR_PF as _FLOOR_PF,
    FLOOR_BASIN_FRAC as _FLOOR_BASIN_FRAC,
    OOS_MDD_MAX as _OOS_MDD_MAX,
    OOS_RET_MIN as _OOS_RET_MIN,
)
```

Leave every other call site (`_rescoped_gate(study, oos_m)`, `_objective_value(metrics, min_trades)`) unchanged — the aliases preserve them.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/backtest/test_robust_gate.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Smoke-check the retrofitted script still imports & parses**

Run: `.venv/bin/python -c "import ast,sys; ast.parse(open('scripts/optimize_llm_directed_indicator.py').read()); import importlib.util as u; s=u.spec_from_file_location('o','scripts/optimize_llm_directed_indicator.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print('import OK', m._rescoped_gate, m._objective_value)"`
Expected: prints `import OK <function rescoped_gate ...> <function objective_value ...>` (aliases resolve to the shared module).

- [ ] **Step 7: Commit**

```bash
cd /home/deploy/wt-futures-rlmppo-research
git add shared/backtest/robust_gate.py scripts/optimize_llm_directed_indicator.py tests/unit/backtest/test_robust_gate.py
git commit -m "$(cat <<'EOF'
refactor(backtest): extract robust_gate to shared module (DRY)

rescoped_gate/objective_value moved verbatim out of the
llm_directed_indicator script so the generalized futures gate
CLI (Task 4) reuses the identical, tested logic.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Generalized robust-gate CLI (`gate_futures_strategy.py`)

**Files:**
- Create: `scripts/gate_futures_strategy.py`
- Create: `config/optuna/futures/williams_r_15m.yaml`
- Test: `tests/unit/backtest/test_gate_cli_paramspace.py`

- [ ] **Step 1: Write the failing test (param-space loader + dotted-path apply)**

```python
# tests/unit/backtest/test_gate_cli_paramspace.py
import importlib.util, pathlib

_spec = importlib.util.spec_from_file_location(
    "gfs", pathlib.Path("scripts/gate_futures_strategy.py"))
gfs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gfs)


def test_apply_dotted_params_deepcopies_and_sets_nested():
    base = {"strategy": {"entry": {"params": {"a": 1}},
                         "exit": {"params": {}}}}
    out = gfs.apply_params(base, {"entry.params.a": 9,
                                  "exit.params.b": 2.5})
    assert out["strategy"]["entry"]["params"]["a"] == 9
    assert out["strategy"]["exit"]["params"]["b"] == 2.5
    assert base["strategy"]["entry"]["params"]["a"] == 1  # deep-copied


class _Trial:
    def __init__(self): self.calls = []
    def suggest_float(self, name, low, high):
        self.calls.append((name, "f", low, high)); return (low + high) / 2
    def suggest_int(self, name, low, high):
        self.calls.append((name, "i", low, high)); return int((low + high) // 2)


def test_suggest_from_space():
    space = {
        "entry.params.oversold_threshold": {"type": "float", "low": -95, "high": -60},
        "entry.params.williams_r_period": {"type": "int", "low": 7, "high": 28},
    }
    t = _Trial()
    params = gfs.suggest_params(t, space)
    assert params["entry.params.oversold_threshold"] == -77.5
    assert params["entry.params.williams_r_period"] == 17
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/backtest/test_gate_cli_paramspace.py -v`
Expected: FAIL — file `scripts/gate_futures_strategy.py` does not exist.

- [ ] **Step 3: Create the CLI**

Create `scripts/gate_futures_strategy.py`. The backtest/Optuna/OOS/gate machinery is copied from `scripts/optimize_llm_directed_indicator.py` (verified shapes in the spec extraction) but strategy-agnostic — the search space comes from a YAML file instead of a hardcoded `_suggest_params`:

```python
#!/usr/bin/env python3
"""Generalized re-scoped robust-gate runner for ANY futures strategy.

Spec 2026-05-19 §7. Reuses shared.backtest.robust_gate (DRY).
Usage:
  python scripts/gate_futures_strategy.py --strategy williams_r_15m \
    --data data/kospi200f_1m_ch_101S6000.csv \
    --space config/optuna/futures/williams_r_15m.yaml \
    --holdout-split 2026-02-01 --min-trades 50 --trials 70
"""
from __future__ import annotations
import argparse, copy, sys
import pandas as pd
import optuna
from optuna.samplers import TPESampler

from shared.config.loader import ConfigLoader
from shared.backtest.config import BacktestConfig
from shared.backtest.engine import BacktestEngine
from shared.backtest.adapter import BacktestStrategyAdapter
from shared.strategy.registry import StrategyFactory
from shared.backtest.robust_gate import rescoped_gate, objective_value

_DEFAULT_DATA = "data/kospi200f_1m_ch_101S6000.csv"


def apply_params(base_cfg: dict, params: dict) -> dict:
    cfg = copy.deepcopy(base_cfg)
    for dotted, val in params.items():
        node = cfg["strategy"]
        parts = dotted.split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = val
    return cfg


def suggest_params(trial, space: dict) -> dict:
    out = {}
    for name, spec in space.items():
        if spec["type"] == "int":
            out[name] = trial.suggest_int(name, spec["low"], spec["high"])
        else:
            out[name] = trial.suggest_float(name, spec["low"], spec["high"])
    return out


def _run_backtest(cfg: dict, df, bt_config: BacktestConfig) -> dict:
    strategy = StrategyFactory.create(cfg)
    adapter = BacktestStrategyAdapter(strategy, cfg)
    engine = BacktestEngine(adapter, bt_config)
    return engine.run(df.copy()).to_metrics_dict()


def _load_data(path: str) -> pd.DataFrame:
    from shared.backtest.csv_loader import validate_csv_file
    return validate_csv_file(
        path, reject_duplicate_datetime=True,
        require_monotonic_datetime=True,
        max_zero_volume_ratio=0.95,
        max_zero_volume_price_move_ratio=0.20,
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--asset", default="futures")
    ap.add_argument("--data", "-d", default=_DEFAULT_DATA)
    ap.add_argument("--space", required=True)
    ap.add_argument("--trials", "-n", type=int, default=70)
    ap.add_argument("--holdout-split", "-H", default=None)
    ap.add_argument("--min-trades", "-M", type=int, default=50)
    a = ap.parse_args(argv)

    base_cfg = ConfigLoader.load_strategy(a.asset, a.strategy)
    space = ConfigLoader.load(a.space)["search_space"]
    bt_over = base_cfg.get("strategy", {}).get("backtest", {}) or {}
    bt_config = BacktestConfig.futures(
        initial_capital=bt_over.get("initial_capital", 10_000_000),
        point_value=bt_over.get("point_value", 50_000),
    )

    df = _load_data(a.data)
    opt_df, oos_df = df, None
    if a.holdout_split:
        split = pd.Timestamp(a.holdout_split)
        tz = df["datetime"].dt.tz
        if tz is not None and split.tzinfo is None:
            split = split.tz_localize(tz)
        opt_df = df[df["datetime"] < split].reset_index(drop=True)
        oos_df = df[df["datetime"] >= split].reset_index(drop=True)
        if len(opt_df) < 500 or len(oos_df) < 500:
            print("ERROR: split leaves too few bars on one side.")
            return 2

    def objective(trial):
        params = suggest_params(trial, space)
        cfg = apply_params(base_cfg, params)
        m = _run_backtest(cfg, opt_df, bt_config)
        for k in ("profit_factor", "total_trades", "win_rate",
                  "total_return_pct", "max_drawdown_pct"):
            trial.set_user_attr(k, float(m.get(k, 0.0)))
        return objective_value(m, a.min_trades)

    study = optuna.create_study(
        direction="maximize", sampler=TPESampler(seed=42),
        study_name=f"{a.strategy}_gate")
    study.optimize(objective, n_trials=a.trials)

    oos_m = {}
    if oos_df is not None:
        best_cfg = apply_params(base_cfg, study.best_params)
        oos_m = _run_backtest(best_cfg, oos_df, bt_config)

    rg = rescoped_gate(study, oos_m)
    verdict = "PASS" if rg["pass"] else "FAIL"
    print(
        f">>> RE-SCOPED GATE: {verdict} "
        f"(a={rg['a']} b={rg['b']} c={rg['c']} | "
        f"median_sharpe={rg['median_sharpe']:.2f} "
        f"basin={rg['basin_frac']:.1%} n_valid={rg['n_valid']})")
    return 0 if rg["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
```

> Implementer: confirm the `validate_csv_file` import path against `cli/main.py` (spec extraction F shows it is used there as `validate_csv_file(data, **kwargs)`); match the module it is imported from in `cli/main.py` exactly.

- [ ] **Step 4: Create the williams_r search-space config**

Create `config/optuna/futures/williams_r_15m.yaml`:

```yaml
# Robust-gate search space for williams_r_15m (spec 2026-05-19 P1).
# Dotted keys are applied under `strategy.` by gate_futures_strategy.apply_params.
search_space:
  entry.params.oversold_threshold:    {type: float, low: -95.0, high: -60.0}
  entry.params.reversal_threshold:    {type: float, low: -92.0, high: -55.0}
  entry.params.overbought_threshold:  {type: float, low: -40.0, high: -5.0}
  entry.params.williams_r_period:     {type: int,   low: 7,     high: 28}
  entry.params.volume_threshold:      {type: float, low: 0.8,   high: 2.0}
  entry.params.confidence_reversal_scale: {type: float, low: 20.0, high: 80.0}
holdout_split: "2026-02-01"
min_trades: 50
```

- [ ] **Step 5: Run param-space tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/backtest/test_gate_cli_paramspace.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
cd /home/deploy/wt-futures-rlmppo-research
git add scripts/gate_futures_strategy.py config/optuna/futures/williams_r_15m.yaml tests/unit/backtest/test_gate_cli_paramspace.py
git commit -m "$(cat <<'EOF'
feat(backtest): generalized robust-gate CLI (spec 2026-05-19 P1)

gate_futures_strategy.py runs the §7 robust gate for any futures
strategy via a YAML search space; reuses shared robust_gate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Wire williams_r to a genuine 15-minute contract

**Context (read first — this is a pattern-mirror task):** `williams_r_15m.yaml` is currently 1-min in disguise (spec §12 correction 1). Mirror the bb_reversion_15m precedent built this session.

**Files:**
- Modify: `shared/strategy/entry/williams_r.py` (`WilliamsRConfig`; `required_indicators`; the Williams %R read site)
- Modify: `config/strategies/futures/williams_r_15m.yaml`
- Test: `tests/unit/strategy/test_williams_r_timeframe.py`

- [ ] **Step 0: Read the precedent + the target (no edits)**

Read these in full before changing anything:
- `shared/strategy/entry/williams_r.py` (the whole file — current `WilliamsRConfig`, `required_indicators` ~95-99, the `momentum_5m` read).
- `shared/strategy/entry/mean_reversion.py` — find the `timeframe_minutes` field + how it appends `mtf_base_<tf>m` to `required_indicators` (added this session for bb_reversion_15m).
- `shared/indicators/contracts.py` — `from_required_keys`, `momentum_requests`, `mtf_base_requests` (the `momentum_<tf>` / `mtf_base_<tf>` token mapping).
- `shared/strategy/decision_cadence.py` — `DecisionCadenceGate` (no-op when `timeframe_minutes <= 1`).
- `services/trading/indicator_engine.py` — `get_momentum_indicators` and `get_indicators_tf` (the bundle keys williams_r will request at tf).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/test_williams_r_timeframe.py
from shared.strategy.entry.williams_r import WilliamsREntry, WilliamsRConfig


def test_default_is_1m_and_uses_momentum_5m():
    e = WilliamsREntry(WilliamsRConfig())
    req = list(e.required_indicators)
    assert "momentum_5m" in req
    assert not any(r.startswith("mtf_base_") for r in req)


def test_timeframe_15_requests_15m_bundles():
    e = WilliamsREntry(WilliamsRConfig(timeframe_minutes=15))
    req = list(e.required_indicators)
    assert "momentum_15m" in req
    assert "mtf_base_15m" in req
    assert "momentum_5m" not in req


def test_config_default_timeframe_is_one():
    assert WilliamsRConfig().timeframe_minutes == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/strategy/test_williams_r_timeframe.py -v`
Expected: FAIL — `WilliamsRConfig` has no `timeframe_minutes` (and `momentum_15m`/`mtf_base_15m` not requested).

- [ ] **Step 3: Add `timeframe_minutes` to `WilliamsRConfig`**

In `shared/strategy/entry/williams_r.py`, add to `WilliamsRConfig` (Pydantic), defaulting to the no-op value:

```python
timeframe_minutes: int = 1  # >1 → decide on closed N-min bars (bb_reversion_15m pattern)
```

- [ ] **Step 4: Make `required_indicators` timeframe-aware**

In `WilliamsREntry`, where `required_indicators` is built (currently the fixed `["momentum_5m", "bb_middle", ...]`), select the momentum bundle by timeframe and add the MTF base when `>1`, mirroring `mean_reversion.py`:

```python
@property
def required_indicators(self) -> list[str]:
    tf = self.config.timeframe_minutes
    mom = "momentum_5m" if tf <= 1 else f"momentum_{tf}m"
    req = [mom, "bb_middle"]
    if tf > 1:
        req.append(f"mtf_base_{tf}m")
    if self.config.volume_confirm:
        req += ["rvol", "volume", "volume_ma"]
    return req
```

> Match the exact return type/shape `williams_r.py` uses today (list vs tuple, property vs attribute, and the precise momentum-bundle key the engine emits — `get_momentum_indicators` from Step 0). The Williams %R value read site must read from the *selected* `mom` bundle key, not a hardcoded `momentum_5m`.

- [ ] **Step 5: Read Williams %R from the selected bundle + add the cadence gate**

At the Williams %R read site, dereference the timeframe-selected bundle key (the same `mom` string from Step 4) rather than literal `"momentum_5m"`. Construct a `DecisionCadenceGate(self.config.timeframe_minutes)` exactly as `mean_reversion.py` does for bb_reversion_15m so live/backtest decisions land only on closed N-min bars (the gate is a no-op at `tf<=1`, preserving current 1-min behaviour).

- [ ] **Step 6: Run unit test to verify it passes**

Run: `.venv/bin/pytest tests/unit/strategy/test_williams_r_timeframe.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Update `williams_r_15m.yaml` to a real 15-min config**

Edit `config/strategies/futures/williams_r_15m.yaml`: add `timeframe_minutes: 15` under `entry.params` and a `backtest` block; keep `enabled: false`:

```yaml
strategy:
  name: williams_r_15m
  asset_class: futures
  enabled: false
  description: "Williams %R 양방향 반전 — 진짜 15분봉 (spec 2026-05-19 P1)"
  backtest:
    initial_capital: 10000000
    point_value: 50000
  entry:
    type: williams_r
    params:
      timeframe_minutes: 15
      williams_r_period: 14
      oversold_threshold: -80.0
      reversal_threshold: -80.0
      overbought_threshold: -20.0
      overbought_reversal_threshold: -20.0
      allow_short: true
      trend_filter: true
      volume_confirm: true
      volume_threshold: 1.0
      stop_loss_pct: 3.0
      signal_cooldown_seconds: 180
      skip_market_open_minutes: 15
      skip_market_close_minutes: 30
      market_open_hour: 9
      market_open_minute: 0
      market_close_hour: 15
      market_close_minute: 45
      confidence_reversal_scale: 50.0
      confidence_trend_scale: 10.0
  exit:
    type: williams_r_exit
    params:
      overbought_threshold: -20.0
      oversold_exit_threshold: -80.0
      max_stop_loss_pct: -0.03
      time_cut_minutes: 120
      eod_close_hour: 15
      eod_close_minute: 45
      default_exit_confidence: 0.8
  position:
    type: fixed
    params:
      max_positions: 1
      order_amount_per_stock: 1000000
```

- [ ] **Step 8: Regression — williams_r + adapter + strategy suites green**

Run: `.venv/bin/pytest tests/unit/strategy/ tests/unit/backtest/ -v -k "williams or adapter or cadence or mtf"`
Expected: PASS (existing williams_r tests, the cadence/MTF parity tests, and the new test all green; the `tf<=1` no-op keeps legacy behaviour identical).

- [ ] **Step 9: Commit**

```bash
cd /home/deploy/wt-futures-rlmppo-research
git add shared/strategy/entry/williams_r.py config/strategies/futures/williams_r_15m.yaml tests/unit/strategy/test_williams_r_timeframe.py
git commit -m "$(cat <<'EOF'
feat(futures): williams_r genuine 15m contract (spec 2026-05-19 P1)

timeframe_minutes>1 → momentum_<tf>m + mtf_base_<tf>m + closed-bar
DecisionCadenceGate (bb_reversion_15m pattern). williams_r_15m.yaml
is now actually 15m. tf<=1 unchanged (no-op).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Run the gate on williams_r_15m and record a terminal verdict

**Files:**
- Create: `reports/optuna/WILLIAMS_R_15M_GATE.md`

- [ ] **Step 1: Run the generalized gate**

```bash
cd /home/deploy/wt-futures-rlmppo-research
.venv/bin/python scripts/gate_futures_strategy.py \
  --strategy williams_r_15m \
  --data data/kospi200f_1m_ch_101S6000.csv \
  --space config/optuna/futures/williams_r_15m.yaml \
  --holdout-split 2026-02-01 --min-trades 50 --trials 70 \
  2>&1 | tee /tmp/wr15_gate.log
```
Expected: a final line `>>> RE-SCOPED GATE: PASS|FAIL (a=.. b=.. c=.. | median_sharpe=.. basin=..% n_valid=..)`. (If `data/kospi200f_1m_ch_101S6000.csv` is absent in the worktree, copy it from the main checkout `/home/deploy/project/kis_unified_sts/data/` — read-only — before running.)

- [ ] **Step 2: Record the verdict (terminal, per spec §8)**

Create `reports/optuna/WILLIAMS_R_15M_GATE.md` capturing: the exact command, the full `>>> RE-SCOPED GATE` line, `study.best_params`, the (a)/(b)/(c) sub-results, and the **decision**:
- **PASS** → williams_r_15m is the surviving P1 candidate; the P2 trigger (spec §9) fires — LLM-directed entry via the Setup A/C tuning/veto pattern is the next spec/plan. Do **not** flip `enabled: true` here (operator sign-off + paper-only gate is a separate step).
- **FAIL** → terminal for this candidate. Record as reproducible negative evidence (RL_mppo / llm_directed_indicator precedent): `enabled:false` stays; the price-indicator timeframe axis on this family is exhausted; the §9 trigger to Approach ③ (microstructure/cross-asset, new spec) fires. Append a one-paragraph cross-reference to `reports/optuna/FINDINGS.md`.

Use this skeleton (fill the bracketed values from the actual run — these are run outputs to capture, not placeholders to invent):

```markdown
# williams_r_15m — re-scoped robust §6 gate verdict (2026-05-19)

Spec: docs/superpowers/specs/2026-05-19-futures-rlmppo-replacement-indicator-research-design.md §7
Tool: scripts/gate_futures_strategy.py (shared.backtest.robust_gate)
Data: data/kospi200f_1m_ch_101S6000.csv | holdout 2026-02-01 | min-trades 50 | 70 trials

## VERDICT: <PASS|FAIL>

`<paste the full >>> RE-SCOPED GATE line>`

| Check | Requirement | Result | |
|---|---|---|---|
| (a) median valid trial (train) | Sharpe ≥ 0 & PF ≥ 1.0 | `<med_sharpe> / <med_pf>` | <pass/FAIL> |
| (b) broad basin | ≥ 25% clear (a) | `<basin%> (<cleared>/<n_valid>)` | <pass/FAIL> |
| (c) selected cfg OOS | Sh≥0,PF≥1,MDD≤25,ret≥0 | `<oos numbers>` | <pass/FAIL> |

best_params: `<study.best_params>`

## Decision
<PASS: P2 trigger — LLM-directed entry (Setup A/C tuning/veto) next spec.>
<FAIL: terminal; enabled:false stays; timeframe axis on this family
 exhausted → Approach ③ (new spec). FINDINGS.md cross-ref appended.>
```

- [ ] **Step 3: Commit**

```bash
cd /home/deploy/wt-futures-rlmppo-research
git add reports/optuna/WILLIAMS_R_15M_GATE.md
# if FAIL and FINDINGS cross-ref was appended, also: git add reports/optuna/FINDINGS.md
git commit -m "$(cat <<'EOF'
docs(optuna): williams_r_15m robust-gate verdict (spec 2026-05-19 P1)

Terminal recorded verdict from the generalized gate runner.
PASS→P2 trigger / FAIL→Approach ③ trigger (spec §9).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

**1. Spec coverage:**
- §4 P0 `llm_market_context` persistence → Tasks 1+2. ✅
- §4 P0 ATR fix → removed (spec §12 correction 2); no task, by design. ✅ (documented, not a gap)
- §4/§7 generalized robust gate → Tasks 3+4. ✅
- §12 correction 1 williams_r true-15m wiring → Task 5. ✅
- §7 gate-from-scratch + §8 terminal-FAIL-recorded → Task 6. ✅
- §9 P2/③ triggers → encoded as the Task 6 decision branch. ✅
- §12 correction 3 (no new candidates in P1) → honoured (no candidate-build tasks). ✅

**2. Placeholder scan:** No "TBD/handle errors/similar to". The two "Implementer: confirm against source" notes (Task 3 `objective_value`, Task 5 shapes) are explicit verbatim-source-of-truth instructions with exact file:line, not placeholders — required because those exact bodies live in code, not in this plan, and must not be paraphrased. Task 6 bracketed values are *run outputs to capture*, called out as such.

**3. Type/name consistency:** `rescoped_gate`/`objective_value` + constants (`SENTINEL`, `FLOOR_SHARPE`, `FLOOR_PF`, `FLOOR_BASIN_FRAC`, `OOS_MDD_MAX`, `OOS_RET_MIN`) named identically in Task 3 module, Task 3 script aliases, Task 4 import. `apply_params`/`suggest_params` consistent between Task 4 code and its test. `timeframe_minutes` consistent across Task 5 config/code/test and matches the bb_reversion_15m precedent name. `insert_llm_market_context` consistent Task 1↔2. Row dict keys identical Task 1 test ↔ Task 2 builder ↔ Task 1 method. ✅

---

## Execution Handoff

This plan is P0+P1 only. P2 (LLM-directed entry on a survivor) and P3 (agile exit) are trigger-gated in the spec and are out of scope here — Task 6's verdict decides whether P2's trigger fires.
