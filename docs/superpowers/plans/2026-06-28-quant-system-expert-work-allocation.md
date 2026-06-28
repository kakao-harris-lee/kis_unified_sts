# Quant System Expert Work Allocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the 2026-06-28 roadmap and gap research into parallel expert work packages for KOSPI 200 futures, stock trading, market-structure policy, and Quant Ops Workbench transparency.

**Architecture:** Split the work by ownership boundary, not by file type. Policy decisions produce docs/config contracts first; futures and stock specialists then implement bounded changes behind existing YAML/env gates; Workbench specialists expose evidence without adding live controls. Each lane must leave a reviewable artifact and a focused verification command.

**Tech Stack:** Python, FastAPI dashboard (`services/dashboard`), Redis DB 1, SQLite `RuntimeLedger`, YAML config, Next.js/React (`strategy-builder-ui`), pytest, Vitest, Playwright fallback QA.

---

## Source Documents

- `docs/investigations/2026-06-28-quant-system-gap-research.md`
- `docs/ROADMAP.md`
- `docs/PROJECT_STATUS.md`
- `docs/api.md`
- `CLAUDE.md`

## Expert Lane Map

| Lane | Expert | Primary Outcome | Can Run In Parallel |
|---|---|---|---|
| 0 | Program lead / quant PM | Decision board, dependency tracking, review cadence | Starts first |
| 1 | Market-structure policy expert | Explicit KRX-only vs ATS and futures session/product policy | After Lane 0 board |
| 2 | Futures platform engineer | Product/session contract hardening and F-9 cutover evidence contract | After Lane 1 policy draft |
| 3 | Futures strategy researcher | Setup C/D observation and promotion evidence | Parallel after Lane 0 |
| 4 | Stock venue / ATS engineer | Stock KRX-only or ATS/SOR implementation path | After Lane 1 stock decision |
| 5 | Stock strategy + theme researcher | Theme/fusion quality evidence and stock strategy readiness | Parallel after Lane 0 |
| 6 | Workbench UX/observability engineer | Per-asset/per-strategy evidence dashboards | Parallel after Lanes 3/5 define report schemas |
| 7 | Ops/QA lead | Smoke, screenshots, docs, final gate review | Last |

## Global Rules For Every Lane

- Keep runtime behavior configuration-driven. Thresholds, schedules, symbols,
  product choice, routing flags, and gates belong in YAML/env/config.
- Preserve stock swing behavior: no blanket EOD liquidation.
- Preserve futures long/short symmetry and `signal_direction`.
- Keep live controls out of the Workbench unless a separate approved live gate
  exists.
- Do not reintroduce removed ML/RL/TFT or ClickHouse runtime paths.
- Use Redis DB 1 and TTLs for any new Redis keys.
- Every lane must end with an evidence note under `reports/` or `docs/testing/`
  and a short update to `docs/PROJECT_STATUS.md` or `docs/ROADMAP.md` if the
  source-of-truth state changed.

---

### Task 0: Program Lead - Execution Board And Dependency Control

**Expert:** Program lead / quant PM

**Files:**
- Create: `reports/quant-gap/2026-06-28-execution-board.md`
- Modify: `docs/PROJECT_STATUS.md`
- Read: `docs/investigations/2026-06-28-quant-system-gap-research.md`
- Read: `docs/ROADMAP.md`

**Purpose:** Create one working board that experts can use without re-reading the full roadmap every day.

- [ ] **Step 1: Create the execution board skeleton**

Create `reports/quant-gap/2026-06-28-execution-board.md` with this structure:

```markdown
# Quant Gap Execution Board - 2026-06-28

## Review Cadence

- Daily review: 08:20 KST before futures/stock regular sessions.
- End-of-day evidence review: 16:30 KST after stock close and futures regular close.
- Live-gate decisions require explicit operator approval in writing.

## Decision Gates

| Gate | Owner | Required Input | Decision | Status |
|---|---|---|---|---|
| G0 Stock venue policy | Market-structure policy expert | KRX-only vs ATS/SOR memo | Pending | Open |
| G1 Futures session policy | Market-structure policy expert | 08:45 regular + night session policy | Pending | Open |
| G2 Futures product policy | Futures platform engineer | Mini vs full KOSPI 200 contract policy | Pending | Open |
| G3 Setup C/D promotion evidence | Futures strategy researcher | Paper evidence reports | Pending | Open |
| G4 Stock strategy/theme evidence | Stock strategy + theme researcher | Readiness and theme quality reports | Pending | Open |

## Active Lanes

| Lane | Expert | Status | Blocked By | Next Evidence |
|---|---|---|---|---|
| 1 Market structure policy | Unassigned | Open | None | Policy memo |
| 2 Futures platform | Unassigned | Open | G1, G2 | Contract tests |
| 3 Futures strategy evidence | Unassigned | Open | None | Setup C/D reports |
| 4 Stock venue / ATS | Unassigned | Open | G0 | SOR or KRX-only implementation note |
| 5 Stock strategy / theme | Unassigned | Open | None | Strategy and theme quality reports |
| 6 Workbench evidence UX | Unassigned | Open | Report schemas from lanes 3/5 | Dashboard contract |
| 7 Ops/QA | Unassigned | Open | Lanes 1-6 | Verification bundle |

## Evidence Links

- Gap research: `docs/investigations/2026-06-28-quant-system-gap-research.md`
- Roadmap: `docs/ROADMAP.md`
- Runtime status: `docs/PROJECT_STATUS.md`
```

- [ ] **Step 2: Add board creation to project status**

Add a short bullet under `docs/PROJECT_STATUS.md` `Recent Decisions`:

```markdown
**2026-06-28** - Expert execution board opened.
Created `reports/quant-gap/2026-06-28-execution-board.md` to coordinate market-structure,
futures, stock, Workbench, and QA expert lanes from the 2026-06-28 gap research.
```

- [ ] **Step 3: Verify docs formatting**

Run:

```bash
git diff --check
rg -n '[ \t]+$' reports/quant-gap/2026-06-28-execution-board.md docs/PROJECT_STATUS.md
```

Expected:

- `git diff --check` exits 0.
- `rg` exits 1 with no output, meaning no trailing whitespace was found.

- [ ] **Step 4: Commit**

```bash
git add reports/quant-gap/2026-06-28-execution-board.md docs/PROJECT_STATUS.md
git commit -m "docs: open quant gap expert execution board"
```

---

### Task 1: Market-Structure Policy Expert - Stock Venue And Futures Session Policy

**Expert:** Market-structure policy / compliance-aware quant specialist

**Files:**
- Create: `docs/runbooks/market-structure-policy.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/ROADMAP.md`
- Read: `config/market_schedule.yaml`
- Read: `config/execution.yaml`
- Read: `services/stock_order_router/main.py`
- Read: `shared/execution/executor.py`

**Purpose:** Make the current product policy explicit before engineers change session windows or venue routing.

- [ ] **Step 1: Write the policy runbook**

Create `docs/runbooks/market-structure-policy.md`:

```markdown
# Market Structure Policy

Last updated: 2026-06-28 KST.

## Scope

This runbook records operator policy for stock venue routing, KOSPI 200 futures
product/session handling, and what must be true before changing runtime windows.

## Current Policy

| Area | Policy | Runtime Setting |
|---|---|---|
| Stock venue | KRX-only until operator approves ATS/SOR readiness | `ats_routing.enabled=false`; `stock_order_router` remains KRX-only |
| Stock extended hours | No automated extended-hours trading until ATS feed/routing evidence exists | `market_schedule.stock.extended` is non-authoritative for automation |
| Futures regular session | Current runtime keeps conservative configured session until 08:45 policy is implemented and tested | `market_schedule.futures.regular.open` currently `09:00` |
| Futures night session | Disabled fail-closed | `market_schedule.futures.night.enabled=false` |
| Futures product | Product must be explicit in env and evidence reports before promotion | `FUTURES_TRADING_PRODUCT`, `FUTURES_STRATEGY_SYMBOL`, `FUTURES_SLIPPAGE_TICK_SIZE` |

## Change Gates

### Stock ATS/SOR Gate

Before enabling `ats_routing.enabled=true`, all of these must be present:

- KRX and ATS quote ingestion for the same symbol and timestamp window.
- Routing decision audit persisted with venue, price improvement, spread, depth,
  fill estimate, and reason.
- Paper simulator calibrated for ATS fill rate and price improvement.
- Workbench venue evidence panel.
- Integration test proving KRX fallback when ATS quote is missing.

### Futures 08:45 Regular Session Gate

Before changing `market_schedule.futures.regular.open` from `09:00` to `08:45`:

- Strategy entry windows must be reviewed for Setup A/C/D.
- Slippage blocked windows must be reviewed for 08:45-09:00.
- Backtest/session filters must state whether 08:45-09:00 is included.
- Paper evidence must compare 09:00-only vs 08:45-inclusive behavior.

### Futures Night Session Gate

Before enabling night trading:

- Separate feed and order API behavior must be verified.
- Night order validity and quote limits must be reflected in risk/order guards.
- Kill-switch, position recovery, and settlement assumptions must be tested.
- Operator approval must explicitly name the allowed products and max exposure.
```

- [ ] **Step 2: Link the runbook**

Add a row in `docs/INDEX.md` under Strategy & paper trading or Operations:

```markdown
| [runbooks/market-structure-policy.md](runbooks/market-structure-policy.md) | Operator policy for stock ATS/SOR, futures 08:45 regular session, night session, and KOSPI 200 product governance. |
```

- [ ] **Step 3: Update the roadmap policy line**

In `docs/ROADMAP.md`, keep `Nextrade/ATS best-execution readiness` planned and add a reference to the runbook in that row's gate text.

- [ ] **Step 4: Verify**

Run:

```bash
git diff --check
rg -n 'market-structure-policy|ats_routing.enabled=false|futures.night.enabled=false' docs/runbooks/market-structure-policy.md docs/INDEX.md docs/ROADMAP.md
```

Expected:

- `git diff --check` exits 0.
- `rg` shows the new runbook link and the two policy guard strings.

- [ ] **Step 5: Commit**

```bash
git add docs/runbooks/market-structure-policy.md docs/INDEX.md docs/ROADMAP.md
git commit -m "docs: define market structure policy gates"
```

---

### Task 2: Futures Platform Engineer - Product And Session Contract Hardening

**Expert:** Futures platform engineer

**Files:**
- Modify: `shared/execution/futures_instrument.py`
- Modify: `config/execution.yaml`
- Modify: `config/market_schedule.yaml`
- Modify: `shared/execution/executor.py`
- Modify: `services/trading/orchestrator.py`
- Test: `tests/unit/execution/test_futures_instrument_config.py`
- Test: `tests/unit/trading/test_futures_product_selection.py`
- Test: `tests/unit/execution/test_executor.py`

**Purpose:** Prevent Mini/full KOSPI 200, tick-size, symbol, and session-window drift from silently corrupting entries or risk.

- [ ] **Step 1: Add failing tests for full vs Mini contract metadata**

Extend `tests/unit/execution/test_futures_instrument_config.py` with:

```python
def test_resolved_futures_product_requires_matching_slippage_tick(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "kospi200")
    monkeypatch.setenv("FUTURES_SLIPPAGE_TICK_SIZE", "0.02")

    from shared.execution.futures_instrument import (
        validate_futures_runtime_product_contract,
    )

    result = validate_futures_runtime_product_contract()

    assert result.ok is False
    assert result.product == "kospi200"
    assert result.expected_tick_size == 0.05
    assert result.actual_tick_size == 0.02
    assert "FUTURES_SLIPPAGE_TICK_SIZE=0.05" in result.message


def test_resolved_mini_product_accepts_default_slippage_tick(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "mini")
    monkeypatch.delenv("FUTURES_SLIPPAGE_TICK_SIZE", raising=False)

    from shared.execution.futures_instrument import (
        validate_futures_runtime_product_contract,
    )

    result = validate_futures_runtime_product_contract()

    assert result.ok is True
    assert result.product == "mini"
    assert result.expected_tick_size == 0.02
```

- [ ] **Step 2: Run the new tests and verify failure**

Run:

```bash
pytest tests/unit/execution/test_futures_instrument_config.py -q
```

Expected: FAIL because `validate_futures_runtime_product_contract` is not defined.

- [ ] **Step 3: Implement the contract validator**

Add a dataclass and validator in `shared/execution/futures_instrument.py`:

```python
@dataclass(frozen=True)
class FuturesProductContractValidation:
    ok: bool
    product: str
    expected_tick_size: float
    actual_tick_size: float
    message: str


_PRODUCT_TICK_SIZE = {
    "mini": 0.02,
    "kospi200": 0.05,
}


def _env_float(value: str | None, default: float) -> float:
    if value is None or not str(value).strip():
        return default
    try:
        return float(str(value).strip())
    except ValueError:
        return default


def validate_futures_runtime_product_contract(
    *,
    environ: Mapping[str, str] | None = None,
) -> FuturesProductContractValidation:
    env = os.environ if environ is None else environ
    product = normalize_futures_product(env.get("FUTURES_TRADING_PRODUCT"))
    expected_tick = _PRODUCT_TICK_SIZE[product]
    actual_tick = _env_float(env.get("FUTURES_SLIPPAGE_TICK_SIZE"), 0.02)
    ok = abs(actual_tick - expected_tick) < 1e-9
    message = (
        "futures product contract ok"
        if ok
        else (
            f"{product} requires FUTURES_SLIPPAGE_TICK_SIZE={expected_tick:.2f}; "
            f"got {actual_tick:.2f}"
        )
    )
    return FuturesProductContractValidation(
        ok=ok,
        product=product,
        expected_tick_size=expected_tick,
        actual_tick_size=actual_tick,
        message=message,
    )
```

- [ ] **Step 4: Add fail-fast logging at futures startup**

In the futures startup path used by `services/trading/orchestrator.py`, call the validator and log a warning in paper mode. Do not block paper until operator policy decides. For live mode, fail closed before submitting futures orders.

- [ ] **Step 5: Keep session changes policy-gated**

Do not change `config/market_schedule.yaml` to 08:45 in this task unless Task 1 explicitly changed the policy. Instead, update the comments to say the 08:45 gate is tracked in `docs/runbooks/market-structure-policy.md`.

- [ ] **Step 6: Verify**

Run:

```bash
pytest tests/unit/execution/test_futures_instrument_config.py tests/unit/trading/test_futures_product_selection.py tests/unit/execution/test_executor.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add shared/execution/futures_instrument.py config/market_schedule.yaml services/trading/orchestrator.py tests/unit/execution/test_futures_instrument_config.py
git commit -m "fix: validate futures product contract"
```

---

### Task 3: Futures Strategy Researcher - Setup C And Setup D Evidence

**Expert:** Futures strategy researcher

**Files:**
- Create: `scripts/ops/setup_d_paper_observe.py`
- Create: `tests/unit/scripts/ops/test_setup_d_paper_observe.py`
- Modify: `scripts/ops/futures_evidence_bundle.py`
- Modify: `tests/unit/scripts/ops/test_futures_evidence_bundle.py`
- Read: `config/strategies/futures/setup_c_event_reaction.yaml`
- Read: `config/strategies/futures/setup_d_vwap_reversion.yaml`
- Read: `scripts/ops/setup_c_event_score_observe.py`

**Purpose:** Convert Setup C/D from "enabled but not proven" into daily evidence that can support or block promotion.

- [ ] **Step 1: Write failing tests for a Setup D paper observer**

Create `tests/unit/scripts/ops/test_setup_d_paper_observe.py`:

```python
from __future__ import annotations

from pathlib import Path

from scripts.ops.setup_d_paper_observe import build_setup_d_report


def test_build_setup_d_report_summarizes_long_short_and_rejections(tmp_path: Path):
    ledger = tmp_path / "signals.jsonl"
    ledger.write_text(
        "\n".join(
            [
                '{"strategy":"setup_d_vwap_reversion","side":"BUY","status":"accepted","pnl":12000,"reason":"vwap_revert"}',
                '{"strategy":"setup_d_vwap_reversion","side":"SELL","status":"accepted","pnl":-3000,"reason":"stop_loss"}',
                '{"strategy":"setup_d_vwap_reversion","side":"BUY","status":"rejected","reject_stage":"risk","reject_reason":"spread"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_setup_d_report(ledger)

    assert report["strategy"] == "setup_d_vwap_reversion"
    assert report["accepted"] == 2
    assert report["rejected"] == 1
    assert report["long_signals"] == 2
    assert report["short_signals"] == 1
    assert report["total_pnl"] == 9000
    assert report["top_reject_reasons"] == {"risk:spread": 1}
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
pytest tests/unit/scripts/ops/test_setup_d_paper_observe.py -q
```

Expected: FAIL because `scripts.ops.setup_d_paper_observe` does not exist.

- [ ] **Step 3: Implement the observer**

Create `scripts/ops/setup_d_paper_observe.py`:

```python
#!/usr/bin/env python3
"""Build a paper evidence report for Setup D VWAP reversion."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


STRATEGY_ID = "setup_d_vwap_reversion"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def build_setup_d_report(path: Path) -> dict[str, Any]:
    rows = [row for row in _load_jsonl(path) if row.get("strategy") == STRATEGY_ID]
    accepted = [row for row in rows if row.get("status") == "accepted"]
    rejected = [row for row in rows if row.get("status") == "rejected"]
    reject_reasons = Counter(
        f"{row.get('reject_stage') or 'unknown'}:{row.get('reject_reason') or 'unknown'}"
        for row in rejected
    )
    return {
        "strategy": STRATEGY_ID,
        "signals": len(rows),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "long_signals": sum(1 for row in rows if str(row.get("side")).upper() == "BUY"),
        "short_signals": sum(1 for row in rows if str(row.get("side")).upper() == "SELL"),
        "total_pnl": sum(float(row.get("pnl") or 0.0) for row in accepted),
        "top_reject_reasons": dict(reject_reasons.most_common(10)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_setup_d_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Include Setup D in futures evidence bundles**

Modify `scripts/ops/futures_evidence_bundle.py` so the bundle records:

```python
"setup_d_observation": {
    "required": True,
    "path": "reports/futures/setup_d/latest.json",
}
```

The strict bundle gate should fail if `setup_d_vwap_reversion` is enabled and the report is missing.

- [ ] **Step 5: Verify**

Run:

```bash
pytest tests/unit/scripts/ops/test_setup_d_paper_observe.py tests/unit/scripts/ops/test_futures_evidence_bundle.py tests/unit/scripts/ops/test_setup_c_event_score_observe.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/ops/setup_d_paper_observe.py tests/unit/scripts/ops/test_setup_d_paper_observe.py scripts/ops/futures_evidence_bundle.py tests/unit/scripts/ops/test_futures_evidence_bundle.py
git commit -m "feat: add setup d paper evidence observer"
```

---

### Task 4: Stock Venue / ATS Engineer - KRX-Only V1 Or ATS/SOR Track

**Expert:** Stock execution and market microstructure engineer

**Files:**
- Modify: `config/execution.yaml`
- Modify: `services/stock_order_router/main.py`
- Modify: `shared/execution/venue_router.py`
- Modify: `tests/integration/test_ats_routing.py`
- Read: `shared/execution/config.py`
- Read: `shared/execution/models.py`
- Read: `docs/runbooks/market-structure-policy.md`

**Purpose:** Remove ambiguity around partial ATS support. The default implementation path is KRX-only v1 unless Task 1 explicitly approves ATS/SOR.

- [ ] **Step 1: Add an explicit KRX-only policy test**

Extend `tests/integration/test_ats_routing.py` with:

```python
def test_stock_order_router_policy_defaults_to_krx_only():
    from shared.execution.config import ATSRoutingConfig
    from shared.execution.models import ExecutionVenue, OrderRequest, OrderSide, OrderType
    from shared.execution.venue_router import MarketData, VenueRouter

    router = VenueRouter(ATSRoutingConfig(enabled=False, default_venue="KRX"))
    order = OrderRequest(
        code="005930",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.LIMIT,
        price=70000,
        asset_class="stock",
    )
    data = MarketData(
        symbol="005930",
        krx_bid=69900,
        krx_ask=70000,
        krx_bid_qty=1000,
        krx_ask_qty=1000,
        ats_bid=69950,
        ats_ask=69980,
        ats_bid_qty=2000,
        ats_ask_qty=2000,
    )

    decision = router.select_venue(order, data)

    assert decision.venue == ExecutionVenue.KRX
    assert decision.reason == "ATS routing disabled"
```

- [ ] **Step 2: Run the policy test**

Run:

```bash
pytest tests/integration/test_ats_routing.py -q
```

Expected: pass if current disabled fallback is intact.

- [ ] **Step 3: If Task 1 chooses KRX-only v1, document the daemon boundary**

Add a concise comment near the stock order routing entrypoint in `services/stock_order_router/main.py`:

```python
# Policy: stock order routing is KRX-only for v1. ATS/SOR code remains behind
# config/execution.yaml::ats_routing.enabled and must not be enabled until the
# market-structure policy runbook gates are satisfied.
```

- [ ] **Step 4: If Task 1 chooses ATS/SOR, add a failing venue-audit test instead**

Only if ATS/SOR is approved, add a test that asserts every ATS decision records:

- venue
- reason
- price improvement bps
- KRX spread bps
- ATS spread bps
- liquidity check
- time preference

Do not enable `ats_routing.enabled=true` without this test and a paper simulator update.

- [ ] **Step 5: Verify**

Run:

```bash
pytest tests/integration/test_ats_routing.py -q
git diff --check
```

Expected: test passes and diff check exits 0.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_ats_routing.py services/stock_order_router/main.py config/execution.yaml
git commit -m "docs: clarify stock venue routing policy"
```

---

### Task 5: Stock Strategy And Theme Researcher - Theme/Fusion Quality Evidence

**Expert:** Stock strategy researcher with LLM/theme QA focus

**Files:**
- Create: `scripts/ops/theme_fusion_quality_report.py`
- Create: `tests/unit/scripts/ops/test_theme_fusion_quality_report.py`
- Modify: `config/theme_discovery.yaml`
- Modify: `config/fusion_ranker.yaml`
- Read: `services/theme_discovery.py`
- Read: `services/fusion_ranker.py`
- Read: `shared/theme_universe/scoring.py`
- Read: `scripts/ops/stock_strategy_readiness.py`

**Purpose:** Give operators evidence that theme leader and fusion outputs are useful, fresh, and not dominated by false-positive keyword matches.

- [ ] **Step 1: Write a failing test for theme/fusion quality summaries**

Create `tests/unit/scripts/ops/test_theme_fusion_quality_report.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from scripts.ops.theme_fusion_quality_report import build_theme_fusion_quality_report


def test_theme_quality_report_counts_active_quarantined_and_false_positive_examples(tmp_path: Path):
    snapshot = tmp_path / "theme_targets.json"
    snapshot.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-28T09:00:00+09:00",
                "targets": [
                    {"code": "000001", "theme_id": "ai_hbm", "state": "active", "leader_score": 0.91, "label": "AI HBM"},
                    {"code": "000002", "theme_id": "ai_hbm", "state": "quarantined", "leader_score": 0.21, "label": "AI HBM"},
                    {"code": "000003", "theme_id": "shipbuilding_defense", "state": "active", "leader_score": 0.77, "label": "Shipbuilding Defense"},
                ],
                "false_positive_examples": [
                    {"code": "000002", "theme_id": "ai_hbm", "reason": "generic keyword"}
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_theme_fusion_quality_report(snapshot)

    assert report["target_count"] == 3
    assert report["state_counts"] == {"active": 2, "quarantined": 1}
    assert report["theme_counts"]["ai_hbm"] == 2
    assert report["false_positive_examples"][0]["reason"] == "generic keyword"
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
pytest tests/unit/scripts/ops/test_theme_fusion_quality_report.py -q
```

Expected: FAIL because the report script does not exist.

- [ ] **Step 3: Implement the report script**

Create `scripts/ops/theme_fusion_quality_report.py`:

```python
#!/usr/bin/env python3
"""Summarize theme target and fusion quality evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def build_theme_fusion_quality_report(snapshot_path: Path) -> dict[str, Any]:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    targets = data.get("targets") or []
    state_counts = Counter(str(target.get("state") or "unknown") for target in targets)
    theme_counts = Counter(str(target.get("theme_id") or "unknown") for target in targets)
    scores = [
        float(target.get("leader_score"))
        for target in targets
        if target.get("leader_score") is not None
    ]
    return {
        "generated_at": data.get("generated_at"),
        "target_count": len(targets),
        "state_counts": dict(state_counts),
        "theme_counts": dict(theme_counts),
        "min_leader_score": min(scores) if scores else None,
        "max_leader_score": max(scores) if scores else None,
        "false_positive_examples": data.get("false_positive_examples") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_theme_fusion_quality_report(args.snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add false-positive review fields to config comments**

In `config/theme_discovery.yaml`, add comments near broad keywords explaining that generic terms require review evidence in the quality report before raising weights.

- [ ] **Step 5: Verify**

Run:

```bash
pytest tests/unit/scripts/ops/test_theme_fusion_quality_report.py tests/unit/theme_universe/test_scoring.py tests/unit/services/test_theme_discovery.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/ops/theme_fusion_quality_report.py tests/unit/scripts/ops/test_theme_fusion_quality_report.py config/theme_discovery.yaml
git commit -m "feat: add theme fusion quality report"
```

---

### Task 6: Workbench UX/Observability Engineer - Per-Asset Evidence Dashboard

**Expert:** Frontend/backend observability engineer

**Files:**
- Create: `services/dashboard/routes/evidence.py`
- Create: `tests/unit/dashboard/test_evidence.py`
- Create: `strategy-builder-ui/src/lib/dashboard/evidence.ts`
- Create: `strategy-builder-ui/src/app/evidence/page.tsx`
- Create: `strategy-builder-ui/src/app/evidence/page.test.tsx`
- Modify: `services/dashboard/app.py`
- Modify: `strategy-builder-ui/src/lib/dashboard/api.ts`
- Modify: `strategy-builder-ui/src/components/dashboard/HeaderBar.tsx`

**Purpose:** Roll individual decision traces up into strategy/asset evidence that an operator can scan before promotion.

- [ ] **Step 1: Write backend route tests**

Create `tests/unit/dashboard/test_evidence.py`:

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from services.dashboard.app import create_app


def test_evidence_summary_returns_asset_and_strategy_groups(monkeypatch):
    monkeypatch.setenv("DASHBOARD_DEV_MODE", "true")
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/evidence/summary?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["asset_class"] == "futures"
    assert "strategies" in body
    assert "generated_at" in body
```

- [ ] **Step 2: Run the backend test and verify failure**

Run:

```bash
pytest tests/unit/dashboard/test_evidence.py -q
```

Expected: FAIL with 404 for `/api/evidence/summary`.

- [ ] **Step 3: Implement a read-only backend summary**

Create `services/dashboard/routes/evidence.py` with a route that returns:

```python
{
    "asset_class": asset_class,
    "generated_at": now_kst.isoformat(),
    "strategies": [],
    "evidence_gaps": [
        {
            "code": "NO_RUNTIME_EVIDENCE",
            "severity": "warning",
            "message": "No evidence report has been connected yet.",
        }
    ],
}
```

Then register the router in `services/dashboard/app.py`.

- [ ] **Step 4: Add frontend API client**

Create `strategy-builder-ui/src/lib/dashboard/evidence.ts`:

```typescript
import { apiClient } from './client';

export interface EvidenceGap {
  code: string;
  severity: string;
  message: string;
}

export interface StrategyEvidenceSummary {
  strategy: string;
  accepted: number;
  rejected: number;
  paperPnl?: number | null;
  backtestPaperDelta?: number | null;
  status: string;
}

export interface EvidenceSummaryResponse {
  asset_class: string;
  generated_at: string;
  strategies: StrategyEvidenceSummary[];
  evidence_gaps: EvidenceGap[];
}

export const evidenceApi = {
  getSummary: (assetClass: string) =>
    apiClient.get<EvidenceSummaryResponse>('/api/evidence/summary', {
      params: { asset_class: assetClass },
    }),
};
```

- [ ] **Step 5: Implement `/evidence` page**

Create `strategy-builder-ui/src/app/evidence/page.tsx` as a read-only operational page:

- Use `useAssetClass()` for stock/futures filter.
- Show generated time, strategy rows, and evidence gaps.
- Do not include any order or live-control button.
- Use compact operational layout, not a marketing-style landing page.

- [ ] **Step 6: Verify**

Run:

```bash
pytest tests/unit/dashboard/test_evidence.py -q
npm --prefix strategy-builder-ui run build
```

Expected:

- Backend route test passes.
- Frontend build exits 0.

- [ ] **Step 7: Commit**

```bash
git add services/dashboard/routes/evidence.py services/dashboard/app.py tests/unit/dashboard/test_evidence.py strategy-builder-ui/src/lib/dashboard/evidence.ts strategy-builder-ui/src/app/evidence/page.tsx strategy-builder-ui/src/app/evidence/page.test.tsx strategy-builder-ui/src/lib/dashboard/api.ts strategy-builder-ui/src/components/dashboard/HeaderBar.tsx
git commit -m "feat: add evidence summary workbench page"
```

---

### Task 7: Ops/QA Lead - Final Verification Bundle

**Expert:** Ops/QA lead

**Files:**
- Create: `docs/testing/quant-gap-execution-2026-06-28.md`
- Modify: `docs/PROJECT_STATUS.md`
- Read: `reports/quant-gap/2026-06-28-execution-board.md`
- Read: lane evidence reports under `reports/`

**Purpose:** Ensure every lane produced evidence and did not weaken paper/live safety.

- [ ] **Step 1: Create final QA evidence note**

Create `docs/testing/quant-gap-execution-2026-06-28.md`:

```markdown
# Quant Gap Execution QA - 2026-06-28

## Scope

This note verifies expert-lane outputs from
`docs/superpowers/plans/2026-06-28-quant-system-expert-work-allocation.md`.

## Lane Evidence

| Lane | Evidence | Status | Notes |
|---|---|---|---|
| Program board | `reports/quant-gap/2026-06-28-execution-board.md` | Pending | |
| Market structure policy | `docs/runbooks/market-structure-policy.md` | Pending | |
| Futures platform | pytest output | Pending | |
| Futures strategy evidence | Setup C/D reports | Pending | |
| Stock venue | ATS/KRX policy test output | Pending | |
| Stock strategy/theme | theme/fusion and readiness reports | Pending | |
| Workbench evidence UX | backend/frontend test output | Pending | |

## Safety Checks

- Stock no-blanket-EOD behavior preserved:
- Futures long/short symmetry preserved:
- Live controls not added to Workbench:
- `ats_routing.enabled` remains false unless explicitly approved:
- `futures.night.enabled` remains false unless explicitly approved:
```

- [ ] **Step 2: Run focused verification suite**

Run:

```bash
pytest tests/unit/execution/test_futures_instrument_config.py tests/unit/trading/test_futures_product_selection.py tests/unit/execution/test_executor.py tests/unit/scripts/ops/test_setup_c_event_score_observe.py tests/unit/scripts/ops/test_futures_evidence_bundle.py tests/integration/test_ats_routing.py tests/unit/theme_universe/test_scoring.py tests/unit/services/test_theme_discovery.py tests/unit/dashboard/test_signals_trace.py -q
npm --prefix strategy-builder-ui run build
git diff --check
```

Expected:

- All selected pytest tests pass.
- Frontend build exits 0.
- `git diff --check` exits 0.

- [ ] **Step 3: Update Project Status**

Only after verification passes, add a `Recent Decisions` note to
`docs/PROJECT_STATUS.md` with:

```markdown
**2026-06-28** - Quant gap expert lanes verified.
Completed the focused verification bundle for market-structure policy, futures
product/session contract, Setup C/D evidence, stock venue policy, theme/fusion
quality, and Workbench evidence UX. Evidence:
[testing/quant-gap-execution-2026-06-28.md](testing/quant-gap-execution-2026-06-28.md).
```

- [ ] **Step 4: Commit**

```bash
git add docs/testing/quant-gap-execution-2026-06-28.md docs/PROJECT_STATUS.md
git commit -m "test: capture quant gap execution evidence"
```

---

## Dependency And Parallelization Plan

1. Run Task 0 first.
2. Task 1 starts immediately after Task 0 and must publish policy before Tasks 2 and 4 make behavior changes.
3. Tasks 3 and 5 can start after Task 0 because they are evidence/reporting work and do not depend on venue/session decisions.
4. Task 6 can start with a stub backend response, then connect real reports after Tasks 3 and 5 define report shapes.
5. Task 7 runs last and must not mark completion until it has fresh command output.

## Review Checklist

- Spec coverage: Every gap from `docs/investigations/2026-06-28-quant-system-gap-research.md` maps to at least one expert lane.
- No live-control regression: Workbench changes are read-only or paper-safe.
- No runtime policy ambiguity: stock ATS and futures night/08:45 decisions are explicit before behavior changes.
- No source-of-truth drift: `docs/ROADMAP.md` and `docs/PROJECT_STATUS.md` are updated when a lane changes state.
- Verification before completion: each lane records exact commands and outcomes before handoff.
