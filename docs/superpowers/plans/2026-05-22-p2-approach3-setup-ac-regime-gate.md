# P2-③ RegimeGate Live-Paper Wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the validated RegimeGate (PASS Δ=+3.26 in backtest, merged at `e6cfa35`) into the live paper-trading entry path for Setup A, Setup C, and bb_reversion_15m, with a Redis-live data source, a per-strategy YAML opt-in, and best-effort counterfactual logging for weekly operator review.

**Architecture:** Adapter-layer hook (symmetric with existing LLM-tuning/veto). A new `apply_regime_gate(gate, decision_signal, context)` helper is called from each adapter's `generate()` after LLM veto, before Signal return; on block it logs to a new `regime_gate_decisions` ClickHouse table and returns suppressed (None). The gate reads `forecast:vol:current` from Redis (no hot-path CH SELECT) and `event_scores` from CH (low-frequency entry-decision call). Default per-strategy `enabled: false`; operator opt-in per strategy YAML.

**Tech Stack:** Python 3.11, Redis (decode_responses), ClickHouse via `clickhouse_driver` sync client, pytest (run via `/home/deploy/project/kis_unified_sts/.venv/bin/pytest`), existing `RegimeGate` + `ForecastClient` + `TelegramNotifier`.

**Spec:** `docs/superpowers/specs/2026-05-22-p2-approach3-setup-ac-regime-gate-design.md` (read §5 architecture, §6 components, §7 data flow, §8 validation, §9 safety, §13 corrections).

**Branch/worktree:** all work on `docs/p2-approach3-setup-ac-regime-gate` in worktree `/home/deploy/wt-p2-approach3` (off `origin/main` `e6cfa35`). NEVER `main`/`runtime/main-current`. No worktree-local `.venv`; use `/home/deploy/project/kis_unified_sts/.venv/bin/{python,pytest}`. Every commit ends with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`. Stage explicit paths only; never `git add -A`. Commit messages via `git commit -F <tempfile>` (heredoc form trips the auto-mode classifier).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `shared/db/client.py` (modify) | Add `regime_gate_decisions` to `SCHEMAS` dict + `insert_regime_gate_decisions(rows)` method (mirrors `rl_drift_metrics` + `insert_drift_metrics`) | 1 |
| `tests/unit/db/test_regime_gate_decisions_schema.py` (create) | Schema-entry + insert SQL/tuple shape (no socket) | 1 |
| `shared/strategy/gates/live_inputs.py` (create) | `LiveVolInputs` — Redis vol + CH events; PERMISSIVE-on-miss; live data source for `RegimeGate` | 2 |
| `tests/unit/strategy/gates/test_live_inputs.py` (create) | Vol/event paths + missing/stale degrade | 2 |
| `shared/strategy/gates/adapter_helper.py` (create) | `apply_regime_gate(gate, decision_signal, context, strategy_name) → blocked: bool` — DRY 3-adapter call site; logs decision to CH best-effort | 3 |
| `tests/unit/strategy/gates/test_adapter_helper.py` (create) | Allow / block / gate-None-passthrough / log-failure-doesnt-block | 3 |
| `shared/strategy/gates/regime_gate.py` (modify) | Add `RegimeGateYAML` pydantic config + `regime_gate_from_yaml(d) → RegimeGate \| None` factory; `enabled: false` → returns None (no-op) | 4 |
| `tests/unit/strategy/gates/test_regime_gate_yaml.py` (create) | YAML schema load + enabled false→None factory shim | 4 |
| `shared/strategy/entry/setup_adapters.py` (modify) | `SetupAEntryAdapter.__init__` accepts `regime_gate=None`; `generate()` calls `apply_regime_gate()` after LLM veto. Same for `SetupCEntryAdapter`. | 5 |
| `tests/unit/strategy/test_setup_adapters_regime_gate.py` (create) | gate-blocks-suppresses, gate-allows-passthrough, gate-None-passthrough for Setup A + Setup C (6 tests) | 5 |
| `shared/strategy/entry/mean_reversion.py` (modify) | `MeanReversionEntry.__init__` accepts `regime_gate=None`; refactor `generate()` to compute `signal_direction` once, call gate once, return on block | 6 |
| `tests/unit/strategy/test_mean_reversion_regime_gate.py` (create) | Same 3 cases for bb_reversion_15m's adapter | 6 |
| `shared/strategy/registry.py` (modify) | `StrategyFactory.create()` reads `regime_gate:` YAML section, instantiates via factory, injects into adapter | 7 |
| `tests/unit/strategy/test_registry_regime_gate_injection.py` (create) | Factory injects gate when enabled; None when disabled or missing section | 7 |
| `config/strategies/futures/setup_a_gap_reversion.yaml` (modify) | Add `regime_gate: {enabled: false, ...}` section; `enabled: false` preserves existing behavior | 8 |
| `config/strategies/futures/setup_c_event_reaction.yaml` (modify) | Same | 8 |
| `config/strategies/futures/bb_reversion_15m.yaml` (modify) | Same | 8 |
| `scripts/analysis/regime_gate_counterfactual.py` (create) | Weekly counterfactual digest (queries `regime_gate_decisions` last 7d, computes blocked-vs-allowed mean-P&L estimate, Telegram digest) | 9 |
| `tests/unit/analysis/test_regime_gate_counterfactual.py` (create) | Cohort grouping + P&L estimate math (CH+Telegram mocked) | 9 |
| `docs/runbooks/regime-gate-paper-observation.md` (create) | Operator runbook: activation per strategy + weekly review interpretation + rollback | 10 |

---

### Task 1: `regime_gate_decisions` ClickHouse table + insert helper

**Files:**
- Modify: `shared/db/client.py` (`SCHEMAS` dict ~line 145–164 region; insert method near `insert_drift_metrics` ~line 439-455)
- Test: `tests/unit/db/test_regime_gate_decisions_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/db/test_regime_gate_decisions_schema.py
import datetime as dt


def test_schema_entry_exists_and_formats():
    from shared.db.client import SCHEMAS
    assert "regime_gate_decisions" in SCHEMAS
    ddl = SCHEMAS["regime_gate_decisions"].format(database="market")
    assert "CREATE TABLE IF NOT EXISTS market.regime_gate_decisions" in ddl
    assert "ORDER BY (strategy, ts)" in ddl
    assert "PARTITION BY toYYYYMM(ts)" in ddl
    assert "INTERVAL 90 DAY" in ddl


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
        "ts": dt.datetime(2026, 5, 22, 9, 0, 0),
        "strategy": "setup_a_gap_reversion",
        "asset": "futures",
        "signal_direction": "long",
        "allow": False,
        "reason": "regime_percentile=72.5>max",
        "regime_pct": 72.5,
    }]
    n = client.insert_regime_gate_decisions(rows)
    assert n == 1
    assert "INSERT INTO market.regime_gate_decisions" in captured["sql"]
    assert captured["data"] == [(
        dt.datetime(2026, 5, 22, 9, 0, 0), "setup_a_gap_reversion",
        "futures", "long", 0, "regime_percentile=72.5>max", 72.5,
    )]


def test_insert_empty_returns_zero():
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig
    ClickHouseClient.reset_singleton()
    client = ClickHouseClient(ClickHouseConfig(
        host="localhost", port=9000, database="market",
        user="default", password=""))
    assert client.insert_regime_gate_decisions([]) == 0
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd /home/deploy/wt-p2-approach3
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/db/test_regime_gate_decisions_schema.py -v
```
Expected: FAIL — `KeyError: 'regime_gate_decisions'` / `AttributeError`.

- [ ] **Step 3: Add the DDL entry to `SCHEMAS`** (alongside `rl_drift_metrics` ~line 164, mirroring its style)

```python
"regime_gate_decisions": """
    CREATE TABLE IF NOT EXISTS {database}.regime_gate_decisions (
        ts DateTime64(3),
        strategy LowCardinality(String),
        asset LowCardinality(String),
        signal_direction LowCardinality(String),
        allow UInt8,
        reason String,
        regime_pct Float64,
        created_at DateTime DEFAULT now()
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(ts)
    ORDER BY (strategy, ts)
    TTL toDateTime(ts) + INTERVAL 90 DAY
    COMMENT 'Per-decision RegimeGate audit log for P2-③ live-paper counterfactual review (spec 2026-05-22)'
""",
```

- [ ] **Step 4: Add the insert method** (alongside `insert_drift_metrics` ~line 455)

```python
def insert_regime_gate_decisions(self, rows: list[dict]) -> int:
    """Append RegimeGate decision audit rows (best-effort, P2-③ T1)."""
    if not rows:
        return 0
    try:
        client = self.get_sync_client()
        data = [
            (
                r["ts"], r["strategy"], r["asset"], r["signal_direction"],
                int(bool(r["allow"])), r["reason"], float(r["regime_pct"]),
            )
            for r in rows
        ]
        client.execute(
            f"INSERT INTO {self.config.database}.regime_gate_decisions "
            "(ts, strategy, asset, signal_direction, allow, reason, regime_pct) VALUES",
            data,
        )
        return len(rows)
    except Exception as e:
        logger.error(f"Failed to insert regime_gate_decisions: {e}")
        return 0
```

- [ ] **Step 5: Run test — expect PASS**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/db/test_regime_gate_decisions_schema.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Regression — db suite green**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/db/ -q
```
Expected: no NEW failures.

- [ ] **Step 7: Commit**

Write message to `/tmp/p2_t1_msg.txt`:
```
feat(db): regime_gate_decisions table + insert (spec 2026-05-22 P2-③ T1)

Per-decision audit log of RegimeGate allow/block for live-paper
counterfactual review. MergeTree, ORDER BY (strategy, ts), 90d TTL.
Mirrors rl_drift_metrics DDL pattern. Best-effort insert (logged-and-
swallowed on CH failure — never blocks trading hot path).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Then:
```bash
cd /home/deploy/wt-p2-approach3
git add shared/db/client.py tests/unit/db/test_regime_gate_decisions_schema.py
git commit -F /tmp/p2_t1_msg.txt
```

---

### Task 2: `LiveVolInputs` — Redis-backed source for `RegimeGate`

**Files:**
- Create: `shared/strategy/gates/live_inputs.py`
- Test: `tests/unit/strategy/gates/test_live_inputs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/gates/test_live_inputs.py
import datetime as dt
from unittest.mock import MagicMock


def _vf_json(asof_iso, regime_percentile, fresh_age_s=60):
    """Build a VolForecast JSON blob the live reader can parse."""
    import json
    return json.dumps({
        "asof": asof_iso,
        "horizon_minutes": 15,
        "forecast_pct": 18.0,
        "forecast_atr_equivalent": 3.0,
        "regime_percentile": regime_percentile,
        "model_version": "har_rv_v1",
        "confidence": 0.3,
    })


def test_latest_vol_at_returns_redis_vol_when_fresh():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    redis = MagicMock()
    asof = dt.datetime(2026, 5, 22, 9, 0, 0, tzinfo=dt.timezone.utc)
    redis.get.return_value = _vf_json(asof.isoformat(), 72.5)
    cli = MagicMock()
    inp = LiveVolInputs(redis=redis, ch_client=cli)
    result = inp.latest_vol_at(dt.datetime(2026, 5, 22, 9, 0, 0))
    assert result is not None
    ts_naive, regime_pct = result
    assert regime_pct == 72.5
    assert ts_naive.tzinfo is None  # tz-stripped for bisect-style consumers


def test_latest_vol_at_returns_none_when_redis_empty():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    redis = MagicMock(); redis.get.return_value = None
    inp = LiveVolInputs(redis=redis, ch_client=MagicMock())
    assert inp.latest_vol_at(dt.datetime(2026, 5, 22, 9, 0, 0)) is None


def test_latest_vol_at_returns_none_when_stale():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    redis = MagicMock()
    # asof is 5 minutes old; max_age_s default 120
    old = dt.datetime(2026, 5, 22, 8, 55, 0, tzinfo=dt.timezone.utc)
    redis.get.return_value = _vf_json(old.isoformat(), 72.5)
    inp = LiveVolInputs(redis=redis, ch_client=MagicMock())
    now = dt.datetime(2026, 5, 22, 9, 0, 0)
    assert inp.latest_vol_at(now) is None  # stale → PERMISSIVE


def test_latest_vol_at_swallows_redis_exception():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    redis = MagicMock(); redis.get.side_effect = RuntimeError("redis down")
    inp = LiveVolInputs(redis=redis, ch_client=MagicMock())
    # MUST NOT raise — degrade to None
    assert inp.latest_vol_at(dt.datetime(2026, 5, 22, 9, 0, 0)) is None


def test_events_within_queries_ch_and_filters_window():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    cli = MagicMock()
    cli.execute.return_value = [
        (dt.datetime(2026, 5, 22, 9, 5), 85),  # within ± 15min
        (dt.datetime(2026, 5, 22, 8, 50), 90),  # outside (15+ min ago)
    ]
    inp = LiveVolInputs(redis=MagicMock(), ch_client=cli)
    out = inp.events_within(dt.datetime(2026, 5, 22, 9, 10), 15)
    assert len(out) == 1
    assert out[0][1] == 85


def test_events_within_swallows_ch_exception():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    cli = MagicMock(); cli.execute.side_effect = RuntimeError("ch down")
    inp = LiveVolInputs(redis=MagicMock(), ch_client=cli)
    assert inp.events_within(dt.datetime(2026, 5, 22, 9, 0), 15) == []


def test_macro_for_always_returns_none_in_live():
    # Live EntryContext has no macro_overnight; LiveVolInputs returns None
    # → RegimeGate's require_overnight_us_direction flag degrades PERMISSIVE.
    from shared.strategy.gates.live_inputs import LiveVolInputs
    inp = LiveVolInputs(redis=MagicMock(), ch_client=MagicMock())
    assert inp.macro_for(dt.date(2026, 5, 22)) is None
```

- [ ] **Step 2: Run — expect FAIL** (module not found)

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/gates/test_live_inputs.py -v
```

- [ ] **Step 3: Create `shared/strategy/gates/live_inputs.py`**

```python
# shared/strategy/gates/live_inputs.py
"""Redis-backed live data source for RegimeGate (P2-③ T2).

Implements the same duck-typed interface RegimeGate expects:
  - latest_vol_at(ts) → (asof_naive, regime_percentile) | None
  - events_within(ts, window_min) → list[(asof_naive, impact_score)]
  - macro_for(date) → float | None   (always None in live; PERMISSIVE)

Vol reads from `forecast:vol:current` (the live ForecastPublisher's
60s-cadence write). Event reads do a low-volume CH SELECT (called once
per entry decision). PERMISSIVE on EVERY missing/stale/error path —
never propagates to the trading hot path.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from shared.forecasting.models import VolForecast
from shared.forecasting.vol_reader import _VOL_KEY  # canonical key

logger = logging.getLogger(__name__)

_DEFAULT_MAX_AGE_S = 120  # matches ForecastPublisher's Redis TTL


class LiveVolInputs:
    """Live (Redis + CH) inputs for RegimeGate."""

    def __init__(
        self,
        redis: Any,
        ch_client: Any,
        max_age_s: int = _DEFAULT_MAX_AGE_S,
    ):
        self._redis = redis
        self._ch = ch_client
        self._max_age_s = max_age_s

    def latest_vol_at(
        self, ts: dt.datetime
    ) -> tuple[dt.datetime, float] | None:
        try:
            blob = self._redis.get(_VOL_KEY)
        except Exception as e:  # noqa: BLE001 — hot path
            logger.debug("LiveVolInputs: redis GET failed: %s", e)
            return None
        if not blob:
            return None
        try:
            vf = VolForecast.from_json(blob)
        except Exception as e:  # noqa: BLE001
            logger.debug("LiveVolInputs: malformed vol JSON: %s", e)
            return None
        # Freshness check (tz-aware compare against now)
        now = dt.datetime.now(dt.timezone.utc)
        if not vf.is_fresh(now, max_age_s=self._max_age_s):
            return None
        # Strip tz so bisect-style consumers (RegimeGate.allow) work uniformly
        asof_n = vf.asof.replace(tzinfo=None) if vf.asof.tzinfo else vf.asof
        return (asof_n, float(vf.regime_percentile))

    def events_within(
        self, ts: dt.datetime, window_min: int
    ) -> list[tuple[dt.datetime, int]]:
        try:
            ts_n = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
            lo = ts_n - dt.timedelta(minutes=window_min)
            hi = ts_n + dt.timedelta(minutes=window_min)
            rows = self._ch.execute(
                "SELECT asof, impact_score FROM kospi.event_scores "
                "WHERE asof >= %(lo)s AND asof <= %(hi)s ORDER BY asof",
                {"lo": lo, "hi": hi},
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("LiveVolInputs: events_within CH failed: %s", e)
            return []
        # Look-ahead-safe within the window — also drop any future-asof rows
        return [
            (r[0].replace(tzinfo=None) if getattr(r[0], "tzinfo", None) else r[0],
             int(r[1]))
            for r in rows
            if r[0] is not None
        ]

    def macro_for(self, date: dt.date) -> float | None:
        """Live EntryContext has no macro_overnight field. RegimeGate's
        require_overnight_us_direction flag degrades PERMISSIVE when this
        returns None — that's the §9 design (never silently block on
        missing data). Setup A's own macro consumption is internal to its
        _build_market_context path and not visible here.
        """
        return None
```

- [ ] **Step 4: Run — expect PASS (7 tests)**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/gates/test_live_inputs.py -v
```

- [ ] **Step 5: ruff + commit**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check shared/strategy/gates/live_inputs.py tests/unit/strategy/gates/test_live_inputs.py
```

Write message to `/tmp/p2_t2_msg.txt`:
```
feat(gates): LiveVolInputs Redis-backed source (spec 2026-05-22 P2-③ T2)

RegimeGate-compatible duck-typed inputs for live: Redis vol read
from forecast:vol:current (60s ForecastPublisher cadence, 120s TTL
freshness), CH events query, macro always None (live EntryContext
has no macro_overnight — gate degrades PERMISSIVE per §9). Hot-path
safe: every miss/error/stale returns None / [] / None, never raises.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add shared/strategy/gates/live_inputs.py tests/unit/strategy/gates/test_live_inputs.py
git commit -F /tmp/p2_t2_msg.txt
```

---

### Task 3: `apply_regime_gate()` — DRY helper for the 3 adapter integrations

**Files:**
- Create: `shared/strategy/gates/adapter_helper.py`
- Test: `tests/unit/strategy/gates/test_adapter_helper.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/gates/test_adapter_helper.py
import datetime as dt
from unittest.mock import MagicMock


def _ctx(ts=None, code="futures"):
    from shared.strategy.base import EntryContext
    return EntryContext(
        market_data={"code": code},
        timestamp=ts or dt.datetime(2026, 5, 22, 9, 0, 0, tzinfo=dt.timezone.utc),
    )


def _sig(direction="long"):
    s = MagicMock()
    s.metadata = {"signal_direction": direction}
    return s


def test_gate_none_returns_not_blocked():
    """When gate is None (strategy not opted in), helper is a no-op."""
    from shared.strategy.gates.adapter_helper import apply_regime_gate
    blocked = apply_regime_gate(
        gate=None, decision_signal=_sig(), context=_ctx(),
        strategy_name="setup_a_gap_reversion",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is False


def test_gate_allow_returns_not_blocked_and_logs(monkeypatch):
    from shared.strategy.gates.adapter_helper import apply_regime_gate
    gate = MagicMock()
    gate.allow.return_value = (True, "regime_ok")
    ch = MagicMock()
    logged_rows = []
    monkeypatch.setattr(
        "shared.db.client.get_clickhouse_client",
        lambda cfg=None: MagicMock(
            insert_regime_gate_decisions=lambda rows: logged_rows.extend(rows) or len(rows)))
    blocked = apply_regime_gate(
        gate=gate, decision_signal=_sig("long"), context=_ctx(code="A01603"),
        strategy_name="setup_a_gap_reversion",
        redis=MagicMock(), ch_client=ch)
    assert blocked is False
    gate.allow.assert_called_once()
    assert len(logged_rows) == 1
    assert logged_rows[0]["strategy"] == "setup_a_gap_reversion"
    assert logged_rows[0]["signal_direction"] == "long"
    assert logged_rows[0]["allow"] is True
    assert logged_rows[0]["reason"] == "regime_ok"


def test_gate_block_returns_blocked_and_logs(monkeypatch):
    from shared.strategy.gates.adapter_helper import apply_regime_gate
    gate = MagicMock()
    gate.allow.return_value = (False, "regime_percentile=72.5>max")
    logged_rows = []
    monkeypatch.setattr(
        "shared.db.client.get_clickhouse_client",
        lambda cfg=None: MagicMock(
            insert_regime_gate_decisions=lambda rows: logged_rows.extend(rows) or len(rows)))
    blocked = apply_regime_gate(
        gate=gate, decision_signal=_sig("long"), context=_ctx(),
        strategy_name="setup_c_event_reaction",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is True
    assert logged_rows[0]["allow"] is False
    assert "regime_percentile" in logged_rows[0]["reason"]


def test_log_failure_does_not_propagate(monkeypatch):
    """CH insert failure must NOT change the gate verdict or raise."""
    from shared.strategy.gates.adapter_helper import apply_regime_gate
    gate = MagicMock(); gate.allow.return_value = (True, "regime_ok")
    monkeypatch.setattr(
        "shared.db.client.get_clickhouse_client",
        lambda cfg=None: MagicMock(
            insert_regime_gate_decisions=MagicMock(side_effect=RuntimeError("ch down"))))
    blocked = apply_regime_gate(
        gate=gate, decision_signal=_sig(), context=_ctx(),
        strategy_name="bb_reversion_15m",
        redis=MagicMock(), ch_client=MagicMock())
    assert blocked is False  # verdict preserved
```

- [ ] **Step 2: Run — expect FAIL**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/gates/test_adapter_helper.py -v
```

- [ ] **Step 3: Create `shared/strategy/gates/adapter_helper.py`**

```python
# shared/strategy/gates/adapter_helper.py
"""DRY adapter-integration helper for RegimeGate (P2-③ T3).

All three adapters (SetupAEntryAdapter, SetupCEntryAdapter,
MeanReversionEntry) call apply_regime_gate() after their LLM-veto /
entry-decision logic but before returning the orchestrator Signal.
Single locus for: gate.allow(), best-effort decision logging to
regime_gate_decisions, and the "no gate configured" no-op shortcut.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

logger = logging.getLogger(__name__)


def apply_regime_gate(
    *,
    gate: Any | None,
    decision_signal: Any,
    context: Any,
    strategy_name: str,
    redis: Any,
    ch_client: Any,
) -> bool:
    """Returns True if the signal should be SUPPRESSED (blocked).

    No-op (returns False) when gate is None (strategy not opted in).
    On block AND on allow, best-effort writes a row to
    regime_gate_decisions for weekly counterfactual review. Logging
    failure NEVER changes the gate verdict.
    """
    if gate is None:
        return False

    # Defensive tz handling — Setup A/C pattern: fallback to now(UTC)
    ts = getattr(context, "timestamp", None)
    if ts is None:
        ts = dt.datetime.now(dt.timezone.utc)

    # Asset extraction — mirror Setup A/C veto-block pattern
    md = getattr(context, "market_data", None) or {}
    asset = str(md.get("code", md.get("symbol", "")))

    # signal_direction lives in metadata for orchestrator Signals;
    # decision_signal here may be either an orchestrator Signal or a
    # DecisionSignal — handle both shapes.
    direction = "long"
    md_meta = getattr(decision_signal, "metadata", None) or {}
    if md_meta.get("signal_direction") in ("long", "short"):
        direction = md_meta["signal_direction"]
    elif getattr(decision_signal, "side", None) in ("long", "short"):
        direction = decision_signal.side

    # Construct the live inputs and ask the gate
    from shared.strategy.gates.live_inputs import LiveVolInputs
    inputs = LiveVolInputs(redis=redis, ch_client=ch_client)
    # Inject inputs into a one-shot RegimeGate wrapper if needed
    if hasattr(gate, "_inputs"):
        # Gate was constructed with inputs already; reuse for backtest-style call
        allow, reason = gate.allow(ts=ts, asset=asset, signal_direction=direction)
    else:
        # Live-shim: gate was constructed config-only; wrap with live inputs
        from shared.strategy.gates.regime_gate import RegimeGate
        live_gate = RegimeGate(config=gate._cfg if hasattr(gate, "_cfg") else gate, inputs=inputs)
        allow, reason = live_gate.allow(ts=ts, asset=asset, signal_direction=direction)

    # Best-effort logging — failure must NOT change the verdict
    try:
        from shared.db.client import get_clickhouse_client
        from shared.db.config import ClickHouseConfig

        ts_n = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
        regime_pct = 0.0
        # Try to extract regime_pct from reason string ("regime_percentile=X.X>max")
        if "regime_percentile=" in reason:
            try:
                regime_pct = float(
                    reason.split("regime_percentile=")[1].split(">")[0])
            except (IndexError, ValueError):
                regime_pct = 0.0
        row = {
            "ts": ts_n,
            "strategy": strategy_name,
            "asset": asset or "unknown",
            "signal_direction": direction,
            "allow": bool(allow),
            "reason": reason or "",
            "regime_pct": regime_pct,
        }
        get_clickhouse_client(ClickHouseConfig.from_env()).insert_regime_gate_decisions([row])
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "regime_gate_decisions append skipped (verdict preserved): %s",
            e, exc_info=True)

    return not allow  # blocked := !allow
```

- [ ] **Step 4: Run — expect PASS (4 tests)**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/gates/test_adapter_helper.py -v
```

- [ ] **Step 5: ruff + commit**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check shared/strategy/gates/adapter_helper.py tests/unit/strategy/gates/test_adapter_helper.py
```

Write to `/tmp/p2_t3_msg.txt`:
```
feat(gates): apply_regime_gate adapter-helper (spec 2026-05-22 P2-③ T3)

Single DRY call site used by SetupA/SetupC/MeanReversion adapters
after LLM veto, before Signal return. Returns blocked=True on
suppress; gate=None is no-op. Best-effort logs every decision
(allow + block) to regime_gate_decisions; log failure swallowed
(verdict NEVER changed by logging issues).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add shared/strategy/gates/adapter_helper.py tests/unit/strategy/gates/test_adapter_helper.py
git commit -F /tmp/p2_t3_msg.txt
```

---

### Task 4: `RegimeGateYAML` config + factory

**Files:**
- Modify: `shared/strategy/gates/regime_gate.py` (append `RegimeGateYAML` + `regime_gate_from_yaml(d)` after existing `GateConfig`)
- Test: `tests/unit/strategy/gates/test_regime_gate_yaml.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/gates/test_regime_gate_yaml.py


def test_yaml_enabled_false_returns_none():
    from shared.strategy.gates.regime_gate import regime_gate_from_yaml
    g = regime_gate_from_yaml({"enabled": False})
    assert g is None


def test_yaml_missing_section_returns_none():
    from shared.strategy.gates.regime_gate import regime_gate_from_yaml
    assert regime_gate_from_yaml(None) is None
    assert regime_gate_from_yaml({}) is None


def test_yaml_enabled_true_builds_gate_with_defaults():
    from shared.strategy.gates.regime_gate import (
        regime_gate_from_yaml, GateConfig, RegimeGate,
    )
    g = regime_gate_from_yaml({"enabled": True})
    assert isinstance(g, RegimeGate)
    cfg = g._cfg
    assert cfg.regime_percentile_max == 60.0  # spec default per regime_gate_default.yaml
    assert cfg.impact_score_max == 70
    assert cfg.event_window_minutes == 15
    assert cfg.require_overnight_us_direction is False
    assert cfg.permissive_on_missing is True


def test_yaml_overrides_defaults():
    from shared.strategy.gates.regime_gate import regime_gate_from_yaml
    g = regime_gate_from_yaml({
        "enabled": True,
        "regime_percentile_max": 50.0,
        "impact_score_max": 80,
        "event_window_minutes": 20,
    })
    cfg = g._cfg
    assert cfg.regime_percentile_max == 50.0
    assert cfg.impact_score_max == 80
    assert cfg.event_window_minutes == 20
```

- [ ] **Step 2: Run — expect FAIL**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/gates/test_regime_gate_yaml.py -v
```

- [ ] **Step 3: Add `regime_gate_from_yaml()` to `shared/strategy/gates/regime_gate.py`**

Append at the end of the existing file:

```python
def regime_gate_from_yaml(d: dict | None) -> "RegimeGate | None":
    """Build a RegimeGate from a per-strategy YAML config section.

    Returns None when the strategy has not opted in (missing section
    or `enabled: false`) — adapters then take the gate=None no-op
    branch in apply_regime_gate(). Defaults match
    config/gates/regime_gate_default.yaml (spec 2026-05-21 P1-③ T6).
    """
    if not d or not d.get("enabled", False):
        return None
    cfg = GateConfig(
        regime_percentile_max=float(d.get("regime_percentile_max", 60.0)),
        impact_score_max=int(d.get("impact_score_max", 70)),
        event_window_minutes=int(d.get("event_window_minutes", 15)),
        require_overnight_us_direction=bool(
            d.get("require_overnight_us_direction", False)),
        permissive_on_missing=bool(d.get("permissive_on_missing", True)),
    )
    # Live: inputs will be injected per-call by apply_regime_gate via
    # LiveVolInputs. We construct the gate with a placeholder None inputs;
    # the adapter helper wraps with live inputs at call time.
    gate = RegimeGate(config=cfg, inputs=None)
    gate._cfg = cfg  # expose for adapter_helper live-shim wrap
    return gate
```

- [ ] **Step 4: Run — expect PASS (4 tests)**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/gates/test_regime_gate_yaml.py -v
```

- [ ] **Step 5: Regression — gates suite green**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/gates/ -q
```

- [ ] **Step 6: ruff + commit**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check shared/strategy/gates/regime_gate.py tests/unit/strategy/gates/test_regime_gate_yaml.py
```

Write to `/tmp/p2_t4_msg.txt`:
```
feat(gates): RegimeGateYAML factory (spec 2026-05-22 P2-③ T4)

regime_gate_from_yaml(d) builds a RegimeGate from a per-strategy
YAML `regime_gate:` section. enabled=false (or missing section) →
returns None → adapter_helper takes the no-op branch. Defaults
match regime_gate_default.yaml (T12 threshold=60).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add shared/strategy/gates/regime_gate.py tests/unit/strategy/gates/test_regime_gate_yaml.py
git commit -F /tmp/p2_t4_msg.txt
```

---

### Task 5: SetupAEntryAdapter + SetupCEntryAdapter integration

**Files:**
- Modify: `shared/strategy/entry/setup_adapters.py` (both `__init__`s + both `generate()`s)
- Test: `tests/unit/strategy/test_setup_adapters_regime_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/test_setup_adapters_regime_gate.py
import datetime as dt
from unittest.mock import MagicMock, AsyncMock, patch
import pytest


def _ctx():
    from shared.strategy.base import EntryContext
    return EntryContext(
        market_data={"code": "futures"},
        timestamp=dt.datetime(2026, 5, 22, 9, 0, 0, tzinfo=dt.timezone.utc),
    )


@pytest.mark.parametrize("adapter_class,cfg_class,setup_module", [
    ("SetupAEntryAdapter", "SetupAEntryConfig", "gap_reversion"),
    ("SetupCEntryAdapter", "SetupCEntryConfig", "event_reaction"),
])
def test_gate_none_means_no_gate_path(adapter_class, cfg_class, setup_module):
    """When regime_gate=None, the adapter's existing behavior is unchanged."""
    from shared.strategy.entry import setup_adapters
    AdapterClass = getattr(setup_adapters, adapter_class)
    CfgClass = getattr(setup_adapters, cfg_class)
    cfg = CfgClass()  # all defaults; llm_tuning disabled by default
    adapter = AdapterClass(cfg, forecast_client=None, regime_gate=None)
    assert adapter._regime_gate is None


@pytest.mark.parametrize("adapter_class,cfg_class", [
    ("SetupAEntryAdapter", "SetupAEntryConfig"),
    ("SetupCEntryAdapter", "SetupCEntryConfig"),
])
@pytest.mark.asyncio
async def test_gate_blocks_returns_none(adapter_class, cfg_class, monkeypatch):
    """When apply_regime_gate returns blocked=True, generate returns None."""
    from shared.strategy.entry import setup_adapters
    AdapterClass = getattr(setup_adapters, adapter_class)
    CfgClass = getattr(setup_adapters, cfg_class)
    gate = MagicMock()  # truthy gate
    adapter = AdapterClass(CfgClass(), forecast_client=None, regime_gate=gate)
    # Force the underlying setup to emit a decision signal
    fake_decision = MagicMock(); fake_decision.metadata = {"signal_direction": "long"}
    adapter._setup.check = MagicMock(return_value=fake_decision)
    # Mock the LLM context retrieval to skip LLM tuning path
    monkeypatch.setattr(setup_adapters, "_build_market_context",
                        lambda c: MagicMock())
    # Force apply_regime_gate to return blocked=True
    monkeypatch.setattr(setup_adapters, "apply_regime_gate",
                        lambda **kw: True)
    result = await adapter.generate(_ctx())
    assert result is None


@pytest.mark.parametrize("adapter_class,cfg_class", [
    ("SetupAEntryAdapter", "SetupAEntryConfig"),
    ("SetupCEntryAdapter", "SetupCEntryConfig"),
])
@pytest.mark.asyncio
async def test_gate_allows_returns_signal(adapter_class, cfg_class, monkeypatch):
    """When apply_regime_gate returns blocked=False, generate returns the signal."""
    from shared.strategy.entry import setup_adapters
    AdapterClass = getattr(setup_adapters, adapter_class)
    CfgClass = getattr(setup_adapters, cfg_class)
    adapter = AdapterClass(CfgClass(), forecast_client=None, regime_gate=MagicMock())
    fake_decision = MagicMock(); fake_decision.metadata = {"signal_direction": "long"}
    adapter._setup.check = MagicMock(return_value=fake_decision)
    fake_signal = MagicMock()
    monkeypatch.setattr(setup_adapters, "_build_market_context",
                        lambda c: MagicMock())
    monkeypatch.setattr(setup_adapters, "apply_regime_gate",
                        lambda **kw: False)
    monkeypatch.setattr(setup_adapters,
                        "_decision_signal_to_orchestrator_signal",
                        lambda *a, **kw: fake_signal)
    result = await adapter.generate(_ctx())
    assert result is fake_signal
```

- [ ] **Step 2: Run — expect FAIL**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/test_setup_adapters_regime_gate.py -v
```

- [ ] **Step 3: Modify `SetupAEntryAdapter`**

In `shared/strategy/entry/setup_adapters.py`, modify `SetupAEntryAdapter.__init__` signature (around line 890):

```python
    def __init__(
        self,
        config: SetupAEntryConfig,
        forecast_client: Any | None = None,
        regime_gate: Any | None = None,   # P2-③ T5
    ) -> None:
        super().__init__(config)
        # ... existing SetupAConfig + SetupAGapReversion construction unchanged ...
        self._forecast_client = forecast_client
        self._regime_gate = regime_gate  # P2-③ T5
```

In `SetupAEntryAdapter.generate()` — INSERT THIS BLOCK between the existing veto check (line 1082-1083) and the Signal return (line 1085). Find the `if should_veto: return None` line. Immediately after that closing block (still inside `generate()`), add:

```python
        # === P2-③ T5: RegimeGate check (after LLM veto, before Signal return) ===
        from shared.strategy.gates.adapter_helper import apply_regime_gate
        from shared.streaming.client import RedisClient
        from shared.db.client import get_clickhouse_client
        from shared.db.config import ClickHouseConfig

        if self._regime_gate is not None:
            try:
                _redis = RedisClient.get_client()
                _ch = get_clickhouse_client(ClickHouseConfig.from_env()).get_sync_client()
            except Exception:  # noqa: BLE001 — degrade PERMISSIVE
                _redis, _ch = None, None
            if _redis is not None and _ch is not None:
                blocked = apply_regime_gate(
                    gate=self._regime_gate,
                    decision_signal=decision_signal,
                    context=context,
                    strategy_name=self.name,
                    redis=_redis,
                    ch_client=_ch,
                )
                if blocked:
                    return None
```

- [ ] **Step 4: Modify `SetupCEntryAdapter`** with the SAME shape (signature change + same block inserted between line 1299-1300's `if should_veto: return None` and line 1302's Signal return).

- [ ] **Step 5: Run tests — expect PASS (6 tests)**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/test_setup_adapters_regime_gate.py -v
```

- [ ] **Step 6: Regression**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/ -q
```
Expected: no NEW failures (existing Setup A/C tests pass `regime_gate=None`-equivalent through the no-op path).

- [ ] **Step 7: ruff + commit**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check shared/strategy/entry/setup_adapters.py tests/unit/strategy/test_setup_adapters_regime_gate.py
```

Write to `/tmp/p2_t5_msg.txt`:
```
feat(adapters): SetupA/SetupC RegimeGate integration (spec 2026-05-22 P2-③ T5)

Both adapters accept regime_gate=None kwarg (backward-compat default).
generate() calls apply_regime_gate() after LLM veto, before Signal
return. Block → return None (suppress entry). Symmetric with existing
LLM-tuning/veto pattern at the same logical layer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add shared/strategy/entry/setup_adapters.py tests/unit/strategy/test_setup_adapters_regime_gate.py
git commit -F /tmp/p2_t5_msg.txt
```

---

### Task 6: MeanReversionEntry integration (bb_reversion_15m)

**Files:**
- Modify: `shared/strategy/entry/mean_reversion.py` (`__init__` + refactor of `generate()` to compute `signal_direction` once + single gate call)
- Test: `tests/unit/strategy/test_mean_reversion_regime_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/test_mean_reversion_regime_gate.py
import datetime as dt
from unittest.mock import MagicMock, patch
import pytest


def _ctx_long_trigger():
    """Build a context that triggers the LONG entry path."""
    from shared.strategy.base import EntryContext
    return EntryContext(
        market_data={"code": "futures", "name": "futures", "close": 100.0},
        indicators={
            "bb_lower": 100.0, "bb_upper": 200.0, "bb_middle": 150.0,
            "rsi": 25.0,  # < oversold default
            "volume": 1000, "volume_ma": 500,
            "atr": 2.0,
        },
        timestamp=dt.datetime(2026, 5, 22, 9, 30, 0, tzinfo=dt.timezone.utc),
    )


@pytest.mark.asyncio
async def test_regime_gate_none_existing_signal_unchanged():
    from shared.strategy.entry.mean_reversion import (
        MeanReversionEntry, MeanReversionConfig)
    cfg = MeanReversionConfig(allow_short=False)
    entry = MeanReversionEntry(cfg, regime_gate=None)
    # NO gate → existing behavior unchanged
    assert entry._regime_gate is None


@pytest.mark.asyncio
async def test_regime_gate_blocks_long_returns_none(monkeypatch):
    from shared.strategy.entry import mean_reversion as mr
    cfg = mr.MeanReversionConfig(allow_short=False, regime_filter=False)
    entry = mr.MeanReversionEntry(cfg, regime_gate=MagicMock())
    monkeypatch.setattr(mr, "apply_regime_gate", lambda **kw: True)  # block
    result = await entry.generate(_ctx_long_trigger())
    assert result is None


@pytest.mark.asyncio
async def test_regime_gate_allows_long_returns_signal(monkeypatch):
    from shared.strategy.entry import mean_reversion as mr
    cfg = mr.MeanReversionConfig(allow_short=False, regime_filter=False)
    entry = mr.MeanReversionEntry(cfg, regime_gate=MagicMock())
    monkeypatch.setattr(mr, "apply_regime_gate", lambda **kw: False)  # allow
    result = await entry.generate(_ctx_long_trigger())
    assert result is not None
    assert result.metadata["signal_direction"] == "long"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/test_mean_reversion_regime_gate.py -v
```

- [ ] **Step 3: Modify `MeanReversionEntry`**

In `shared/strategy/entry/mean_reversion.py`, modify `__init__` (around line 99):

```python
    def __init__(self, config: MeanReversionConfig, regime_gate: Any | None = None):
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}
        self._regime_gate = regime_gate  # P2-③ T6
```

In `generate()` body — instead of inserting the gate-block call at all 4 Signal-return sites (lines 303, 323, 343, 368), refactor by deriving `signal_direction` once near the top (after `long_touch`/`short_touch` are computed) and calling the gate ONCE. Place this block IMMEDIATELY BEFORE the line `# Check for long entry (oversold)` (locate this comment in the file):

```python
        # === P2-③ T6: Determine candidate direction + apply RegimeGate ONCE ===
        # Recompute long_touch/short_touch (cheap; existing branches will also
        # recompute internally — small duplication preferable to 4 gate calls).
        _long_candidate = (
            close <= bb_lower * self.config.bb_touch_buffer
            and rsi < oversold_threshold
        )
        _short_candidate = (
            self.config.allow_short
            and close >= bb_upper / self.config.bb_touch_buffer
            and rsi > self.config.rsi_overbought
        )
        _candidate_direction = (
            "long" if _long_candidate
            else ("short" if _short_candidate else None)
        )
        if _candidate_direction is not None and self._regime_gate is not None:
            from shared.strategy.gates.adapter_helper import apply_regime_gate
            from shared.streaming.client import RedisClient
            from shared.db.client import get_clickhouse_client
            from shared.db.config import ClickHouseConfig
            try:
                _redis = RedisClient.get_client()
                _ch = get_clickhouse_client(ClickHouseConfig.from_env()).get_sync_client()
            except Exception:  # noqa: BLE001
                _redis, _ch = None, None
            if _redis is not None and _ch is not None:
                # Build a lightweight stand-in signal carrying the direction
                _stand_in = type("X", (), {"metadata": {"signal_direction": _candidate_direction}})()
                blocked = apply_regime_gate(
                    gate=self._regime_gate,
                    decision_signal=_stand_in,
                    context=context,
                    strategy_name="mean_reversion",
                    redis=_redis,
                    ch_client=_ch,
                )
                if blocked:
                    return None
```

(Keep all existing LONG/SHORT branches downstream unchanged — when the gate blocks here, they never run; when the gate allows, control flows to the original branches which do their own regime-filter / Signal-construction work.)

- [ ] **Step 4: Run tests — expect PASS (3 tests)**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/test_mean_reversion_regime_gate.py -v
```

- [ ] **Step 5: Regression — full strategy suite**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/ -q
```
Expected: no NEW failures (existing mean_reversion tests construct with no `regime_gate=` kwarg → None default → no-op path).

- [ ] **Step 6: ruff + commit**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check shared/strategy/entry/mean_reversion.py tests/unit/strategy/test_mean_reversion_regime_gate.py
```

Write to `/tmp/p2_t6_msg.txt`:
```
feat(adapters): MeanReversionEntry RegimeGate integration (spec 2026-05-22 P2-③ T6)

bb_reversion_15m's adapter accepts regime_gate=None kwarg (backward-
compat default). generate() computes candidate direction once and
calls apply_regime_gate() ONCE (vs 4 Signal-return sites). Block →
return None. Existing regime_filter logic downstream is unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add shared/strategy/entry/mean_reversion.py tests/unit/strategy/test_mean_reversion_regime_gate.py
git commit -F /tmp/p2_t6_msg.txt
```

---

### Task 7: StrategyFactory wiring — inject gate from per-strategy YAML

**Files:**
- Modify: `shared/strategy/registry.py` (`StrategyFactory.create()` — read YAML's `entry.params.regime_gate:` section, build gate via `regime_gate_from_yaml`, pass to adapter)
- Test: `tests/unit/strategy/test_registry_regime_gate_injection.py`

- [ ] **Step 1: Read the current `StrategyFactory.create()` and `EntryRegistry.create()` bodies** (file: `shared/strategy/registry.py`, around lines 130-250). Identify exactly where each adapter is instantiated — that's where `regime_gate=...` is added as a kwarg.

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/strategy/test_registry_regime_gate_injection.py


def test_factory_injects_none_when_section_missing():
    from shared.strategy.registry import StrategyFactory
    cfg = {
        "strategy": {
            "name": "setup_a_gap_reversion",
            "asset_class": "futures",
            "enabled": True,
            "entry": {"type": "setup_a_gap_reversion", "params": {}},
            "exit": {"type": "rl_mppo_exit", "params": {}},
            "position": {"type": "fixed", "params": {}},
        }
    }
    strat = StrategyFactory.create(cfg)
    # entry is the SetupAEntryAdapter; gate is None when no `regime_gate:` section
    assert strat.entry._regime_gate is None


def test_factory_injects_gate_when_enabled():
    from shared.strategy.registry import StrategyFactory
    cfg = {
        "strategy": {
            "name": "setup_a_gap_reversion",
            "asset_class": "futures",
            "enabled": True,
            "entry": {
                "type": "setup_a_gap_reversion",
                "params": {"regime_gate": {"enabled": True}},
            },
            "exit": {"type": "rl_mppo_exit", "params": {}},
            "position": {"type": "fixed", "params": {}},
        }
    }
    strat = StrategyFactory.create(cfg)
    assert strat.entry._regime_gate is not None


def test_factory_skips_gate_when_section_disabled():
    from shared.strategy.registry import StrategyFactory
    cfg = {
        "strategy": {
            "name": "setup_a_gap_reversion",
            "asset_class": "futures",
            "enabled": True,
            "entry": {
                "type": "setup_a_gap_reversion",
                "params": {"regime_gate": {"enabled": False}},
            },
            "exit": {"type": "rl_mppo_exit", "params": {}},
            "position": {"type": "fixed", "params": {}},
        }
    }
    strat = StrategyFactory.create(cfg)
    assert strat.entry._regime_gate is None
```

- [ ] **Step 3: Run — expect FAIL** (gate not currently wired)

- [ ] **Step 4: Modify `StrategyFactory.create()` / `EntryRegistry.create()`**

The cleanest approach: in `StrategyFactory.create(cfg)`, AFTER the entry adapter is constructed but BEFORE the trading strategy is assembled, pop `regime_gate` from `entry_params` and pass it via the adapter's `regime_gate=` kwarg.

Concretely — find the entry-construction line (likely `entry = EntryRegistry.create(entry_type, entry_params)`). Modify the surrounding logic:

```python
# Before EntryRegistry.create:
gate_yaml = entry_params.pop("regime_gate", None)

# (existing) entry = EntryRegistry.create(entry_type, entry_params)

# AFTER entry is constructed, attach the gate if YAML opted in
from shared.strategy.gates.regime_gate import regime_gate_from_yaml
gate = regime_gate_from_yaml(gate_yaml)
if hasattr(entry, "_regime_gate"):
    entry._regime_gate = gate
```

(This is the "set attribute after construction" pattern; cleaner alternative is to thread `regime_gate=` through `EntryRegistry.create()` if its component-class instantiator accepts arbitrary kwargs — implementer chooses based on what the existing code permits.)

- [ ] **Step 5: Run tests — expect PASS (3 tests)**

- [ ] **Step 6: Regression — registry + strategy suite**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/ -q
```
Expected: no NEW failures.

- [ ] **Step 7: ruff + commit**

Write to `/tmp/p2_t7_msg.txt`:
```
feat(registry): inject RegimeGate from per-strategy YAML (spec 2026-05-22 P2-③ T7)

StrategyFactory.create() now reads entry.params.regime_gate from the
strategy YAML, builds a RegimeGate via regime_gate_from_yaml(), and
attaches it to the constructed adapter (SetupA/SetupC/MeanReversion).
Missing section or enabled:false → None → adapter no-op branch.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add shared/strategy/registry.py tests/unit/strategy/test_registry_regime_gate_injection.py
git commit -F /tmp/p2_t7_msg.txt
```

---

### Task 8: Per-strategy YAML config — add `regime_gate:` sections (default `enabled: false`)

**Files:**
- Modify: `config/strategies/futures/setup_a_gap_reversion.yaml`
- Modify: `config/strategies/futures/setup_c_event_reaction.yaml`
- Modify: `config/strategies/futures/bb_reversion_15m.yaml`

- [ ] **Step 1: Add `regime_gate:` block to `setup_a_gap_reversion.yaml`**

Insert under `strategy.entry.params:` at the same nesting depth as `llm_tuning:` and `forecast_integration:` (after the `forecast_integration` block):

```yaml
      # P2-③ RegimeGate (spec 2026-05-22). Default off — operator opt-in.
      # When enabled: gate checks `forecast:vol:current` Redis (live HAR-RV)
      # + event_scores CH (low-frequency) after LLM veto, before signal
      # emission. Block → entry suppressed. Decisions logged to
      # regime_gate_decisions for weekly counterfactual review.
      regime_gate:
        enabled: false
        regime_percentile_max: 60.0       # T12 default; tighten/loosen after first 2wk paper
        impact_score_max: 70
        event_window_minutes: 15
        require_overnight_us_direction: false   # PERMISSIVE in live (no macro on EntryContext)
        permissive_on_missing: true
```

- [ ] **Step 2: Add the SAME block to `setup_c_event_reaction.yaml`** (under `strategy.entry.params:`, same default values).

- [ ] **Step 3: Add the SAME block to `bb_reversion_15m.yaml`** (under `strategy.entry.params:`).

- [ ] **Step 4: Verify YAMLs still load cleanly**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/python -c "
import yaml
for p in [
    'config/strategies/futures/setup_a_gap_reversion.yaml',
    'config/strategies/futures/setup_c_event_reaction.yaml',
    'config/strategies/futures/bb_reversion_15m.yaml',
]:
    d = yaml.safe_load(open(p))
    rg = d['strategy']['entry']['params'].get('regime_gate', {})
    assert rg.get('enabled') is False, p
    assert rg.get('regime_percentile_max') == 60.0, p
    print(f'OK: {p}')
"
```
Expected: 3 OK lines.

- [ ] **Step 5: End-to-end smoke — factory builds each strategy with gate=None**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/python -c "
from shared.config.loader import ConfigLoader
from shared.strategy.registry import StrategyFactory
for name in ['setup_a_gap_reversion', 'setup_c_event_reaction', 'bb_reversion_15m']:
    cfg = ConfigLoader.load_strategy('futures', name)
    s = StrategyFactory.create(cfg)
    assert s.entry._regime_gate is None, name
    print(f'OK: {name} → gate=None (paper-safe default)')
"
```
Expected: 3 OK lines.

- [ ] **Step 6: Commit**

Write to `/tmp/p2_t8_msg.txt`:
```
feat(config): regime_gate sections for Setup A/C + bb_reversion_15m (P2-③ T8)

Per-strategy regime_gate: blocks added to setup_a_gap_reversion.yaml,
setup_c_event_reaction.yaml, bb_reversion_15m.yaml. All default
enabled: false — operator opt-in per strategy (auditable YAML edit).
Defaults match config/gates/regime_gate_default.yaml.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add config/strategies/futures/setup_a_gap_reversion.yaml \
        config/strategies/futures/setup_c_event_reaction.yaml \
        config/strategies/futures/bb_reversion_15m.yaml
git commit -F /tmp/p2_t8_msg.txt
```

---

### Task 9: Weekly counterfactual analyzer + Telegram digest

**Files:**
- Create: `scripts/analysis/regime_gate_counterfactual.py`
- Test: `tests/unit/analysis/test_regime_gate_counterfactual.py`

- [ ] **Step 1: Write the failing test** (CH + Telegram mocked; tests the cohort+P&L math)

```python
# tests/unit/analysis/test_regime_gate_counterfactual.py
import datetime as dt
import importlib.util
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "rgcf", _REPO / "scripts" / "analysis" / "regime_gate_counterfactual.py")
rgcf = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rgcf)


def test_group_decisions_by_strategy_and_allow():
    decisions = [
        (dt.datetime(2026, 5, 20, 9, 0), "setup_a_gap_reversion", "long", 1),
        (dt.datetime(2026, 5, 20, 9, 5), "setup_a_gap_reversion", "long", 0),
        (dt.datetime(2026, 5, 20, 10, 0), "setup_c_event_reaction", "short", 1),
    ]
    grouped = rgcf.group_decisions(decisions)
    assert ("setup_a_gap_reversion", True) in grouped
    assert ("setup_a_gap_reversion", False) in grouped
    assert len(grouped[("setup_a_gap_reversion", True)]) == 1
    assert len(grouped[("setup_a_gap_reversion", False)]) == 1


def test_estimate_pnl_returns_zero_for_empty_cohort():
    assert rgcf.estimate_cohort_pnl_pct([], lookback_min=15, candles_df=None) == 0.0


def test_format_telegram_digest_renders_per_strategy_summary():
    summary = {
        "setup_a_gap_reversion": {
            "blocked_count": 5, "blocked_mean_pnl_pct": -0.3,
            "allowed_count": 12, "allowed_mean_pnl_pct": +0.8,
        },
        "setup_c_event_reaction": {
            "blocked_count": 0, "blocked_mean_pnl_pct": 0.0,
            "allowed_count": 0, "allowed_mean_pnl_pct": 0.0,
        },
    }
    msg = rgcf.format_telegram_digest(
        summary, start=dt.date(2026, 5, 15), end=dt.date(2026, 5, 21))
    assert "setup_a_gap_reversion" in msg
    assert "setup_c_event_reaction" in msg
    assert "blocked" in msg.lower()
    # Setup C zero-signal note (per spec — known limitation)
    assert "0 / 0" in msg or "no signals" in msg.lower()
```

- [ ] **Step 2: Run — expect FAIL (module missing)**

- [ ] **Step 3: Create `scripts/analysis/regime_gate_counterfactual.py`**

```python
#!/usr/bin/env python3
"""Weekly counterfactual digest for RegimeGate (spec 2026-05-22 P2-③ T9).

Queries regime_gate_decisions for the last 7 days, computes per-strategy
blocked-vs-allowed cohorts, estimates each cohort's mean realized P&L
over a 15-min look-forward window using kospi200f_1m bars, and posts
a Telegram digest. Mirrors scripts/analysis/counterfactual_weekly_report.py
CLI/Telegram structure.
"""
from __future__ import annotations
import argparse
import asyncio
import datetime as dt
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logger = logging.getLogger(__name__)


def _resolve_window() -> tuple[dt.date, dt.date]:
    today = dt.date.today()
    # Previous ISO week Monday-Sunday
    last_sun = today - dt.timedelta(days=today.weekday() + 1)
    last_mon = last_sun - dt.timedelta(days=6)
    return last_mon, last_sun


def fetch_decisions(start: dt.date, end: dt.date) -> list[tuple]:
    """Return [(ts, strategy, signal_direction, allow), ...] for the window."""
    from shared.db.client import get_clickhouse_client
    from shared.db.config import ClickHouseConfig
    cli = get_clickhouse_client(ClickHouseConfig.from_env()).get_sync_client()
    rows = cli.execute(
        "SELECT ts, strategy, signal_direction, allow FROM kospi.regime_gate_decisions "
        "WHERE ts >= %(s)s AND ts < %(e)s ORDER BY ts",
        {"s": dt.datetime.combine(start, dt.time.min),
         "e": dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min)},
    )
    return [(r[0], r[1], r[2], int(r[3])) for r in rows]


def group_decisions(decisions: list[tuple]) -> dict[tuple[str, bool], list[tuple]]:
    """Group by (strategy, allow_bool)."""
    grouped: dict[tuple[str, bool], list[tuple]] = defaultdict(list)
    for d in decisions:
        ts, strategy, direction, allow = d
        grouped[(strategy, bool(allow))].append(d)
    return grouped


def estimate_cohort_pnl_pct(
    cohort: list[tuple], lookback_min: int, candles_df,
) -> float:
    """Estimate mean realized P&L % over the lookforward window.

    For each (ts, _, direction, _) in cohort: find the close at ts and
    the close at ts + lookback_min, compute signed % return. Return mean.
    """
    if not cohort or candles_df is None or len(candles_df) == 0:
        return 0.0
    import pandas as pd
    pnls: list[float] = []
    for ts, _strategy, direction, _allow in cohort:
        ts_n = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
        future_ts = ts_n + dt.timedelta(minutes=lookback_min)
        try:
            row_now = candles_df.loc[candles_df.index <= ts_n].iloc[-1]
            row_future = candles_df.loc[candles_df.index <= future_ts].iloc[-1]
            ret = (row_future["close"] - row_now["close"]) / row_now["close"]
            pnls.append(ret * (1.0 if direction == "long" else -1.0) * 100)
        except (IndexError, KeyError):
            continue
    return sum(pnls) / len(pnls) if pnls else 0.0


def load_candles(start: dt.date, end: dt.date):
    """Load kospi200f_1m candles for the window (using the clean A01603 code)."""
    from shared.db.client import get_clickhouse_client
    from shared.db.config import ClickHouseConfig
    import pandas as pd
    cli = get_clickhouse_client(ClickHouseConfig.from_env()).get_sync_client()
    rows = cli.execute(
        "SELECT datetime, close FROM kospi.kospi200f_1m "
        "WHERE code = 'A01603' AND datetime >= %(s)s AND datetime < %(e)s "
        "ORDER BY datetime",
        {"s": dt.datetime.combine(start, dt.time.min),
         "e": dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min)},
    )
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["datetime", "close"])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_localize(None)
    df = df.set_index("datetime")
    return df


def build_summary(decisions, candles_df, lookback_min: int) -> dict:
    grouped = group_decisions(decisions)
    summary: dict[str, dict] = {}
    strategies = sorted({d[1] for d in decisions})
    for strat in strategies:
        blocked = grouped.get((strat, False), [])
        allowed = grouped.get((strat, True), [])
        summary[strat] = {
            "blocked_count": len(blocked),
            "blocked_mean_pnl_pct": estimate_cohort_pnl_pct(
                blocked, lookback_min, candles_df),
            "allowed_count": len(allowed),
            "allowed_mean_pnl_pct": estimate_cohort_pnl_pct(
                allowed, lookback_min, candles_df),
        }
    return summary


def format_telegram_digest(
    summary: dict, start: dt.date, end: dt.date,
) -> str:
    lines = [
        f"📊 RegimeGate weekly counterfactual ({start} → {end})",
        "",
    ]
    for strat, s in summary.items():
        if s["blocked_count"] + s["allowed_count"] == 0:
            lines.append(f"  {strat}: 0 / 0 signals (no decisions logged this week)")
            continue
        delta = s["allowed_mean_pnl_pct"] - s["blocked_mean_pnl_pct"]
        lines.append(
            f"  {strat}:\n"
            f"    blocked={s['blocked_count']:>3} mean_pnl={s['blocked_mean_pnl_pct']:+.3f}%\n"
            f"    allowed={s['allowed_count']:>3} mean_pnl={s['allowed_mean_pnl_pct']:+.3f}%\n"
            f"    Δ(allowed - blocked) = {delta:+.3f}%   "
            f"{'(gate adds value ✓)' if delta > 0 else '(gate neutral/negative ⚠)'}"
        )
    return "\n".join(lines)


async def send_telegram(message: str) -> None:
    """Best-effort futures-channel post (mirrors counterfactual_weekly_report)."""
    try:
        from shared.notification.telegram import TelegramNotifier
        bot_token = os.environ.get(
            "TELEGRAM_BRIEFING_BOT_TOKEN",
            os.environ.get("TELEGRAM_FUTURES_BOT_TOKEN", ""))
        chat_id = os.environ.get(
            "TELEGRAM_BRIEFING_CHAT_ID",
            os.environ.get("TELEGRAM_FUTURES_CHAT_ID", ""))
        if not bot_token or not chat_id:
            logger.warning("telegram credentials missing — skipping")
            return
        await TelegramNotifier(bot_token=bot_token, chat_id=chat_id).send_message(
            message, is_critical=False)
    except Exception:
        logger.exception("telegram send failed")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start-date", type=lambda s: dt.date.fromisoformat(s), default=None)
    ap.add_argument("--end-date", type=lambda s: dt.date.fromisoformat(s), default=None)
    ap.add_argument("--lookback-min", type=int, default=15)
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    a = ap.parse_args(argv)

    logging.basicConfig(level=getattr(logging, a.log_level),
                        format="%(asctime)s %(levelname)s %(message)s")

    start, end = (a.start_date, a.end_date) if (a.start_date and a.end_date) else _resolve_window()
    logger.info("regime_gate counterfactual window: %s → %s", start, end)

    decisions = fetch_decisions(start, end)
    candles_df = load_candles(start, end)
    summary = build_summary(decisions, candles_df, a.lookback_min)
    message = format_telegram_digest(summary, start, end)

    print(message)
    if not a.no_telegram:
        asyncio.run(send_telegram(message))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect PASS (3 tests)**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/analysis/test_regime_gate_counterfactual.py -v
```

- [ ] **Step 5: Smoke `--help`**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/python scripts/analysis/regime_gate_counterfactual.py --help
```
Expected: 5 flags shown, exit 0.

- [ ] **Step 6: ruff + commit**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check scripts/analysis/regime_gate_counterfactual.py tests/unit/analysis/test_regime_gate_counterfactual.py
```

Write to `/tmp/p2_t9_msg.txt`:
```
feat(analysis): weekly RegimeGate counterfactual digest (spec 2026-05-22 P2-③ T9)

scripts/analysis/regime_gate_counterfactual.py — queries
regime_gate_decisions for the last 7 days, computes per-strategy
blocked-vs-allowed mean P&L over a 15-min lookforward on
kospi200f_1m bars, posts a Telegram digest with Δ commentary.
Mirrors counterfactual_weekly_report.py CLI + Telegram pattern.
Setup C zero-signal note flagged per spec known-limitation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add scripts/analysis/regime_gate_counterfactual.py tests/unit/analysis/test_regime_gate_counterfactual.py
git commit -F /tmp/p2_t9_msg.txt
```

---

### Task 10: Operator runbook — activation + weekly review

**Files:**
- Create: `docs/runbooks/regime-gate-paper-observation.md`

- [ ] **Step 1: Create the runbook**

```markdown
# RegimeGate Paper Observation Runbook (P2-③)

Spec: `docs/superpowers/specs/2026-05-22-p2-approach3-setup-ac-regime-gate-design.md`

## Activation (per strategy)

1. Pick the strategy to activate (start with `setup_a_gap_reversion` — fires most frequently in paper).
2. Edit its YAML at `config/strategies/futures/<name>.yaml` and flip `entry.params.regime_gate.enabled: false → true`. Commit the edit (auditable git history).
3. Restart the paper-trading orchestrator so the new config loads:
   ```bash
   sudo systemctl restart kis-trading-paper-futures  # or your paper unit
   ```
4. Confirm the gate is wired by tailing the orchestrator log for "RegimeGate" entries on the next entry-signal cycle.
5. Verify the live forecasting service is running and writing `kospi.vol_forecasts`:
   ```bash
   /home/deploy/project/kis_unified_sts/scripts/cron/forecasting.sh status
   ```

## Weekly review

A cron entry should call the digest every Sunday 18:00 KST:
```
0 9 * * 0  cd /home/deploy/project/kis_unified_sts && set -a; source .env; set +a && .venv/bin/python scripts/analysis/regime_gate_counterfactual.py >> $KIS_LOG_DIR/regime_gate_weekly_$(date +\%Y\%m\%d).log 2>&1
```
(The `0 9 * * 0` is 09:00 UTC = 18:00 KST.)

The digest posts to the futures Telegram channel. Read the per-strategy block:

- **`allowed_mean_pnl_pct > blocked_mean_pnl_pct` AND block-rate in 5-30% range** → gate is adding value; keep enabled.
- **block-rate < 5%** → threshold too loose (gate never fires); consider tightening `regime_percentile_max` (e.g. 60 → 55).
- **block-rate > 30%** → threshold too tight (gate over-blocks); loosen.
- **`allowed_mean_pnl_pct ≤ blocked_mean_pnl_pct`** → gate is not helping; review trade-by-trade in `regime_gate_decisions` + paper P&L logs; consider tightening threshold OR disabling.

After ≥2 weeks per activated strategy, decide:

- Keep enabled (gate adds value)
- Re-tune threshold (separate small follow-up)
- Disable (gate doesn't help on this strategy)

## Rollback

To disable the gate on a strategy without removing the wiring:
1. Edit YAML, set `entry.params.regime_gate.enabled: false`.
2. Commit + restart the paper orchestrator.

The gate code remains in place; only the per-strategy opt-in is rescinded.

## Known limitations

- **Setup C will show 0/0 signals most weeks** until a separate event-sourcing fix populates `kospi.event_scores` / `config/scheduled_events.yaml`. This is expected, not a defect.
- **Threshold transferability untested** — `regime_percentile_max=60` was tuned on bb_reversion_15m backtest; per-strategy revalidation needed after first ≥2 weeks of paper data.
- **forecast_pct calibration is suspect (~3× too high)** — does NOT affect this gate's CDF-position semantics, but Setup C's `forecast_atr_equivalent` consumption may be miscalibrated (separate concern).
- **No live trading affected** — `config/futures_live.yaml::enabled` stays `false`; this whole feature is paper-only.
```

- [ ] **Step 2: Commit**

Write to `/tmp/p2_t10_msg.txt`:
```
docs(runbooks): RegimeGate paper observation procedure (P2-③ T10)

Operator runbook: per-strategy YAML activation (enabled: false →
true), restart paper orchestrator, weekly Telegram digest review
heuristics (block-rate 5-30% target, allowed > blocked mean P&L =
gate adds value), threshold re-tune triggers, rollback procedure,
known limitations (Setup C event sourcing, threshold
transferability, forecast_pct calibration).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add docs/runbooks/regime-gate-paper-observation.md
git commit -F /tmp/p2_t10_msg.txt
```

---

## Self-Review

**1. Spec coverage:**
- §5 architecture (adapter-layer hook) → T3 (adapter_helper) + T5 + T6
- §6 C1 LiveVolInputs → T2
- §6 C2 regime_gate_decisions table → T1
- §6 C3/C4/C5 adapter integration → T5 + T6
- §6 C6 per-strategy YAML schema → T4 (factory) + T8 (configs)
- §6 C7 weekly counterfactual → T9
- §7 data flow → T2 + T3 + T5 + T6
- §8 validation criteria → T9 (digest math) + T10 (runbook interpretation)
- §9 error handling (PERMISSIVE-on-missing; best-effort logging; default-off) → T2 + T3 + T4 + T8
- §10 trigger / paper observation runbook → T10
- §11 testing (9 adapter tests + the others) → T1/T2/T3/T4/T5/T6/T9 each have unit tests
- §13 corrections (adapter locus, Redis-not-CH source, Setup C dormant, bb_reversion bundled, no backtest) → reflected throughout

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to". All code blocks contain real implementations. Step-3 references to "the existing X" in T7 explicitly call out that the implementer should READ the current factory code (acceptable plan technique for pattern-mirror tasks where the exact structure depends on what's already there).

**3. Type/name consistency:**
- `RegimeGate`, `GateConfig` consistent across T2/T3/T4/T5/T6/T7
- `regime_gate_from_yaml(d) → RegimeGate | None` consistent T4/T7
- `apply_regime_gate(gate, decision_signal, context, strategy_name, redis, ch_client) → bool` consistent T3/T5/T6
- `insert_regime_gate_decisions(rows)` consistent T1/T3
- `LiveVolInputs(redis, ch_client, max_age_s)` consistent T2/T3
- `regime_gate_decisions` table name consistent T1/T3/T9
- Row dict keys identical T1 (insert) ↔ T3 (helper logger): `ts, strategy, asset, signal_direction, allow, reason, regime_pct`

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-22-p2-approach3-setup-ac-regime-gate.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, spec+quality review per task; through-and-out in this session.

**2. Inline Execution** — Execute in batches with checkpoints (executing-plans), pausing for review at task boundaries.

Which approach?
