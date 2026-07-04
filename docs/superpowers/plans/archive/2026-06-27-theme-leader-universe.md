# Theme Leader Universe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paper-safe theme-leader screening layer that promotes timely theme-backed stock candidates into the existing stock paper pipeline.

**Architecture:** Add shared theme candidate/scoring contracts, a read-only Redis producer for theme targets, fusion-ranker integration, a shared stock-universe cap selector, and coverage diagnostics. The existing stream path remains intact: theme targets feed `system:trade_targets:latest`, which already drives WebSocket subscriptions, strategy evaluation, paper fills, and dashboard state.

**Tech Stack:** Python 3.11, Redis DB1, Pydantic/service config patterns already used in this repo, pytest/fakeredis-style unit tests, existing dashboard FastAPI route tests.

---

## File Structure

- Create `shared/theme_universe/__init__.py`: package exports.
- Create `shared/theme_universe/models.py`: JSON-friendly dataclasses and parsing helpers.
- Create `shared/theme_universe/scoring.py`: deterministic leader scoring and state classification.
- Create `services/theme_discovery.py`: read-only Redis producer for `system:theme_targets:latest`.
- Create `config/theme_discovery.yaml`: keys, intervals, TTLs, keyword maps, thresholds.
- Create `shared/stock_universe/selection.py`: shared ordered cap helper for ingest and strategy.
- Modify `services/fusion_ranker.py`: load theme targets, apply theme score/metadata, publish through existing `system:trade_targets:latest`.
- Modify `config/fusion_ranker.yaml`: add theme target key and theme weight/config.
- Modify `services/market_ingest/main.py`: use shared cap helper.
- Modify `services/stock_strategy/universe.py`: use same cap helper while preserving watchlist-shaped payload.
- Modify `services/dashboard/routes/coverage.py`: expose `theme_targets` source.
- Add/update tests under `tests/unit/theme_universe/`, `tests/unit/services/`, `tests/unit/stock_strategy/`, and `tests/unit/dashboard/`.

## Parallel Work Ownership

- Worker A owns `shared/theme_universe/*` and `tests/unit/theme_universe/*`.
- Worker B owns `services/theme_discovery.py`, `config/theme_discovery.yaml`, and `tests/unit/services/test_theme_discovery.py`.
- Worker C owns `shared/stock_universe/selection.py`, `services/market_ingest/main.py`, `services/stock_strategy/universe.py`, and related tests.
- Worker D owns `services/fusion_ranker.py`, `config/fusion_ranker.yaml`, and fusion-ranker tests.
- Worker E owns `services/dashboard/routes/coverage.py` and dashboard coverage tests.

Workers are not alone in the codebase. They must not revert changes made by
others. They should keep edits to their assigned ownership set and report any
necessary cross-file dependency instead of touching another worker's files.

---

### Task 1: Shared Theme Candidate Contract and Scoring

**Files:**
- Create: `shared/theme_universe/__init__.py`
- Create: `shared/theme_universe/models.py`
- Create: `shared/theme_universe/scoring.py`
- Test: `tests/unit/theme_universe/test_scoring.py`

- [ ] **Step 1: Write failing scorer tests**

Create `tests/unit/theme_universe/test_scoring.py` with tests for active,
watch, and quarantine states:

```python
from shared.theme_universe.scoring import ThemeScoreInput, classify_theme_candidate


def test_classifies_active_theme_leader():
    result = classify_theme_candidate(
        ThemeScoreInput(
            relative_strength=0.9,
            trading_value_score=0.8,
            volume_surge_score=0.8,
            catalyst_score=0.9,
            theme_breadth_score=0.7,
            intraday_persistence=0.8,
            freshness_score=1.0,
            market_signal_count=2,
            catalyst_signal_count=1,
            risk_flags=[],
        )
    )

    assert result.state == "active"
    assert result.leader_score >= 0.7
    assert result.hard_blocked is False


def test_quarantines_hard_risk_flags():
    result = classify_theme_candidate(
        ThemeScoreInput(
            relative_strength=1.0,
            trading_value_score=1.0,
            volume_surge_score=1.0,
            catalyst_score=1.0,
            theme_breadth_score=1.0,
            intraday_persistence=1.0,
            freshness_score=1.0,
            market_signal_count=3,
            catalyst_signal_count=2,
            risk_flags=["investment_warning"],
        )
    )

    assert result.state == "quarantine"
    assert result.hard_blocked is True


def test_requires_market_and_catalyst_evidence_for_active():
    result = classify_theme_candidate(
        ThemeScoreInput(
            relative_strength=0.9,
            trading_value_score=0.9,
            volume_surge_score=0.9,
            catalyst_score=0.0,
            theme_breadth_score=0.9,
            intraday_persistence=0.9,
            freshness_score=1.0,
            market_signal_count=3,
            catalyst_signal_count=0,
            risk_flags=[],
        )
    )

    assert result.state == "watch"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/unit/theme_universe/test_scoring.py -q
```

Expected: import failure because `shared.theme_universe` does not exist.

- [ ] **Step 3: Implement minimal model and scorer**

Create `shared/theme_universe/scoring.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass


HARD_RISK_FLAGS = {
    "investment_warning",
    "investment_risk",
    "trading_halt",
    "administrative_issue",
    "preferred_share",
}


@dataclass(frozen=True)
class ThemeScoreInput:
    relative_strength: float = 0.0
    trading_value_score: float = 0.0
    volume_surge_score: float = 0.0
    catalyst_score: float = 0.0
    theme_breadth_score: float = 0.0
    intraday_persistence: float = 0.0
    freshness_score: float = 0.0
    market_signal_count: int = 0
    catalyst_signal_count: int = 0
    risk_flags: list[str] | None = None


@dataclass(frozen=True)
class ThemeScoreResult:
    leader_score: float
    state: str
    hard_blocked: bool
    risk_penalty: float


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value or 0.0)))


def classify_theme_candidate(score_input: ThemeScoreInput) -> ThemeScoreResult:
    risk_flags = {str(flag) for flag in (score_input.risk_flags or [])}
    hard_blocked = bool(risk_flags & HARD_RISK_FLAGS)
    soft_penalty = min(0.35, 0.08 * len(risk_flags))
    risk_penalty = 1.0 if hard_blocked else soft_penalty
    raw = (
        0.25 * _clamp01(score_input.relative_strength)
        + 0.20 * _clamp01(score_input.trading_value_score)
        + 0.15 * _clamp01(score_input.volume_surge_score)
        + 0.15 * _clamp01(score_input.catalyst_score)
        + 0.10 * _clamp01(score_input.theme_breadth_score)
        + 0.10 * _clamp01(score_input.intraday_persistence)
        + 0.05 * _clamp01(score_input.freshness_score)
    )
    leader_score = round(max(0.0, min(1.0, raw - risk_penalty)), 6)
    has_required_evidence = (
        score_input.market_signal_count > 0 and score_input.catalyst_signal_count > 0
    )
    if hard_blocked:
        state = "quarantine"
    elif leader_score >= 0.70 and has_required_evidence:
        state = "active"
    else:
        state = "watch"
    return ThemeScoreResult(
        leader_score=leader_score,
        state=state,
        hard_blocked=hard_blocked,
        risk_penalty=round(risk_penalty, 6),
    )
```

Create `shared/theme_universe/models.py` with JSON helpers for candidate payloads.

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/unit/theme_universe/test_scoring.py -q
```

Expected: all tests pass.

---

### Task 2: Theme Discovery Producer

**Files:**
- Create: `services/theme_discovery.py`
- Create: `config/theme_discovery.yaml`
- Test: `tests/unit/services/test_theme_discovery.py`

- [ ] **Step 1: Write tests for payload production**

Test that a screener payload with AI/HBM keywords produces
`system:theme_targets:latest` shape containing `codes`, `metadata`,
`themes`, and `state_counts`.

- [ ] **Step 2: Implement producer**

Implement a synchronous `ThemeDiscoveryService.run_once()` that:

- reads `system:universe:latest`
- maps keyword/theme hits from `config/theme_discovery.yaml`
- scores with `classify_theme_candidate`
- publishes to configured latest key with TTL
- publishes to configured stream with `StreamPublisher`

The implementation must tolerate missing optional inputs and malformed JSON.

- [ ] **Step 3: Run tests**

Run:

```bash
pytest tests/unit/services/test_theme_discovery.py -q
```

Expected: all tests pass.

---

### Task 3: Shared Stock Universe Cap Selection

**Files:**
- Create: `shared/stock_universe/selection.py`
- Modify: `services/market_ingest/main.py`
- Modify: `services/stock_strategy/universe.py`
- Test: `tests/unit/services/test_market_ingest.py`
- Test: `tests/unit/stock_strategy/test_universe.py`

- [ ] **Step 1: Write tests for priority order**

Test that the selected universe orders active trade targets first, then remaining
trade targets, then daily watchlist symbols, capped at `max_symbols`.

- [ ] **Step 2: Implement shared helper**

Create:

```python
def select_stock_universe(
    *,
    trade_targets: list[str],
    watchlist: list[str],
    max_symbols: int,
    existing: list[str] | None = None,
) -> list[str]:
    ...
```

Use ordered de-duplication.

- [ ] **Step 3: Wire helper into ingest and strategy universe merge**

`services/market_ingest/main.py` and `services/stock_strategy/universe.py` must
use the same helper so WebSocket subscription and strategy evaluation cannot
diverge under the 40-symbol cap.

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/unit/services/test_market_ingest.py tests/unit/stock_strategy/test_universe.py -q
```

Expected: all tests pass.

---

### Task 4: Fusion Ranker Theme Input

**Files:**
- Modify: `services/fusion_ranker.py`
- Modify: `config/fusion_ranker.yaml`
- Test: existing or new fusion-ranker unit tests under `tests/unit/`

- [ ] **Step 1: Add tests for theme score contribution**

Test that a symbol only present in `system:theme_targets:latest` can enter the
fused `codes` when it is `active`, has daily indicator coverage, and is not
quarantined.

- [ ] **Step 2: Implement theme extraction**

Add config fields for `theme_targets_key`, `weight_theme`, and theme settings.
Parse theme payload shape:

```json
{
  "codes": ["000660"],
  "scores": {"000660": 0.87},
  "metadata": {"000660": {"theme_id": "ai_hbm", "state": "active"}},
  "themes": {"ai_hbm": {"label": "AI/HBM"}}
}
```

- [ ] **Step 3: Merge metadata and scoring**

Theme score should contribute to final fusion score and theme metadata must be
preserved in `system:trade_targets:latest`.

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/unit -q -k 'fusion_ranker or theme'
```

Expected: relevant tests pass.

---

### Task 5: Dashboard Coverage Diagnostics

**Files:**
- Modify: `services/dashboard/routes/coverage.py`
- Test: `tests/unit/dashboard/test_coverage.py`

- [ ] **Step 1: Add failing coverage test**

Add a fixture with `system:theme_targets:latest` and assert the response
includes source `theme_targets`, count, symbols, and daily missing symbols.

- [ ] **Step 2: Implement coverage source**

Add `_THEME_TARGETS_KEY` with env override
`THEME_TARGETS_LATEST_KEY`, read it beside `screener_universe`,
`trade_targets`, and `daily_indicators`.

- [ ] **Step 3: Run tests**

Run:

```bash
pytest tests/unit/dashboard/test_coverage.py -q
```

Expected: all tests pass.

---

### Task 6: Integration Gate and Review

**Files:**
- No new feature files unless review finds defects.

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
pytest \
  tests/unit/theme_universe \
  tests/unit/services/test_theme_discovery.py \
  tests/unit/services/test_market_ingest.py \
  tests/unit/stock_strategy/test_universe.py \
  tests/unit/dashboard/test_coverage.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Run stream/paper flow tests**

Run:

```bash
docker compose --profile test run --rm tests pytest \
  tests/unit/streaming/test_stream_stage.py \
  tests/unit/streaming/test_multi_stream_stage.py \
  tests/unit/trading/test_orchestrator_stream_cutover.py \
  tests/integration/test_signal_to_fill_e2e.py \
  tests/integration/test_stock_execution_pipeline.py \
  tests/integration/test_stock_monitor_bridge.py \
  tests/unit/stock_strategy/test_daemon.py \
  tests/unit/stock_risk_filter/test_daemon.py \
  tests/unit/stock_order_router/test_daemon.py \
  tests/unit/stock_monitor/test_daemon.py \
  tests/unit/dashboard -q
```

Expected: all tests pass or only documented existing skips.

- [ ] **Step 3: Run lint/format checks**

Run:

```bash
ruff check shared/theme_universe shared/stock_universe services/theme_discovery.py services/fusion_ranker.py services/market_ingest/main.py services/stock_strategy/universe.py services/dashboard/routes/coverage.py tests/unit/theme_universe tests/unit/services tests/unit/stock_strategy tests/unit/dashboard
black --check shared/theme_universe shared/stock_universe services/theme_discovery.py services/fusion_ranker.py services/market_ingest/main.py services/stock_strategy/universe.py services/dashboard/routes/coverage.py tests/unit/theme_universe tests/unit/services tests/unit/stock_strategy tests/unit/dashboard
```

Expected: both pass.

- [ ] **Step 4: Code review**

Dispatch a review agent with a code-review stance. Findings must lead, ordered
by severity, and must focus on data-flow breaks, late-entry regressions,
pipeline contract mismatches, Redis key/TTL issues, and missing tests.
