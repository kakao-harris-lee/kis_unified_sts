# Futures Paradigm — Phase 5 Rollout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** promote Phase 4's paper system to **1-contract live**, install the weekly Edge Review cron + 3 new Grafana dashboards + rollback drill, and lock in the parallel-`rl_mppo` operational contract.

**Architecture:** Phase 5 is **operational** rather than architectural — almost no new daemons or ClickHouse tables. It's gates, cron jobs, dashboards, runbooks, and a CLAUDE.md sync. The one non-trivial code item is `scripts/trading/recover_positions.py` (startup reconciliation for open live positions), which Phase 4 did not build for the paper account.

**Tech stack:** Python 3.11+, existing scripts infra (`scripts/cron/`), Grafana JSON + provisioning config, `shared/notification/telegram.py` (reuse for Edge Review delivery).

**Parent spec:** `docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md`
**Depends on:** Phase 4 completion gate passed (2-week paper uptime + 20 fills + slippage ≤ 0.4 tick + kill-switch drill green).
**Blocks:** none — last phase of the futures paradigm except optional RL repurposing.

---

## File Structure

**Create (new files):**

```
scripts/
├── cron/weekly_edge_review.sh              # Mon 05:00 KST wrapper
├── analysis/weekly_edge_review.py          # full report (extends Phase 4 Task 15 smoke)
├── trading/
│   ├── recover_positions.py                # startup reconciliation for live
│   └── flatten_all.py                      # emergency flat-all (CLI entrypoint)
└── drills/
    └── rollback_drill.sh                   # weekend mock rollback harness

reports/weekly/                             # .gitignored — output directory for HTML reports

config/
└── futures_live.yaml                       # live-account overrides (increment cadence, max_position_size_contracts, symbol_lock_enabled, ...)

docs/runbooks/
├── futures-paradigm-operations.md          # daily ops checklist
├── futures-paradigm-rollback.md            # spec §6.2
├── futures-legal-review.md                 # Gate 2 legal/tax deliverable
└── phase5-verification.md                  # gate checklist (Gate 1-3)

grafana/dashboards/
├── futures-paradigm-overview.json          # 당일 PnL, 포지션, 시그널
├── futures-paradigm-risk.json              # MDD, 연속손실, VaR, kill switch 상태
└── futures-paradigm-live-ladder.json       # Gate 3 진행 상황 (1→2→5 계약)
```

**Modify (existing files):**

- `CLAUDE.md` — update §선물 section (Setup A/C added, `rl_mppo` role change, contract spec link)
- `config/risk.yaml` — add `live_mode_guard` section that enforces `max_position_size_contracts` stepping + `max_daily_trades` stricter caps during Gate 3
- `services/order_router/main.py` (from Phase 4) — add `live_mode: bool` gate that consumes `futures_live.yaml` + rejects orders when `live_guard.suspended` flag is set in Redis
- `scripts/cron/install_phase1_crontab.sh` — append weekly Edge Review entry (installer is already in the project for phase-1 cron)

---

## Conventions Reminder (applies to all tasks)

- **Feature branch:** `feat/futures-paradigm-phase5`. Never commit to main.
- **Redis DB 1** throughout. Every new stream XADD followed by `expire(stream, 86400)`.
- **ClickHouse writes:** tz-strip, re-raise on failure — same pattern as Phase 1-4.
- **ServiceConfigBase** for any new config class. No plain `BaseModel` for service configs.
- **No destructive live-account actions without user confirmation.** Even the rollback script must require `--confirm` flags — match the project convention used by `sts futures flatten-all --confirm` referenced in spec §6.2.
- **Format/lint:** `black <files> && ruff check --fix <files>` on modified files only.
- **rl_mppo unchanged:** no edits to `services/trading/orchestrator.py` or `shared/ml/rl/`. Symbol-lock isolation is enforced by reading the Redis positions HASH, not by touching rl_mppo's code.

---

## Task 1: Scaffold branch

- [ ] **Step 1** Confirm Phase 4 merged + gate closed. If not, branch from `feat/futures-paradigm-phase4` and rebase onto main post-merge.
- [ ] **Step 2** Create `feat/futures-paradigm-phase5`.
- [ ] **Step 3** No commit yet (scaffolding only).

---

## Task 2: Weekly Edge Review — full report

**Files:**
- Create: `scripts/analysis/weekly_edge_review.py`, `scripts/cron/weekly_edge_review.sh`
- Create: `tests/unit/analysis/test_weekly_edge_review.py`

**Scope:** Phase 4 Task 15 ships a smoke version of the SQL query. Phase 5 extends it into the 5-section report per spec §3.2.

- [ ] **Step 1** Write test: seed synthetic rows into mock CH + stub Telegram, assert each of the 5 report sections renders and the Telegram summary fires.
- [ ] **Step 2** Implement:
  - Query `kospi.signals_all JOIN kospi.order_fills` (Phase 4 tables)
  - Aggregate per Setup: trades, win_rate, avg_RR, EV, avg_slip, cumulative PnL
  - Compare vs backtest baseline (loads from `results/` JSON)
  - Risk events count (kill-switch triggers, consecutive-loss tripped, spread-filter rejects)
  - Data-quality metrics (news volume, macro gaps, fallback ratio — from Phase 1/2 streams)
  - Recommendation section: mark Setups with EV < 0 last 2 weeks as "paused" candidates
  - Persist HTML to `reports/weekly/YYYY-WW.html`
  - Telegram summary to `TELEGRAM_BRIEFING_*`
- [ ] **Step 3** Cron wrapper:
  ```bash
  # scripts/cron/weekly_edge_review.sh
  #!/usr/bin/env bash
  set -euo pipefail
  cd "$(dirname "$0")/../.."
  source .venv/bin/activate
  set -a && source .env && set +a
  exec python -m scripts.analysis.weekly_edge_review
  ```
- [ ] **Step 4** Append crontab entry:
  ```
  0 6 * * 1 /home/deploy/project/kis_unified_sts/scripts/cron/weekly_edge_review.sh >> $KIS_LOG_DIR/weekly_edge_review.log 2>&1
  ```
- [ ] **Step 5** Commit: `feat(analysis): weekly Edge Review full report + cron`.

---

## Task 3: `scripts/trading/recover_positions.py`

Startup reconciliation — reads broker open-position list via KIS API and compares to Redis `trading:futures:positions`. On mismatch, logs + alerts via Telegram + refuses to start the order_router daemon (sentinel file). Phase 4's paper broker didn't need this (`VirtualBroker` is in-memory). Live needs it.

- [ ] **Step 1** Test with AsyncMock KIS + seeded Redis: (a) match path — no-op, (b) broker-only position — logs + sentinel, (c) Redis-only position — logs + sentinel.
- [ ] **Step 2** Implement. Sentinel file at `/var/lib/kis-futures-paradigm/recover-block` (or project-local if `/var/lib` not writable — follow phase-1 log-path lesson).
- [ ] **Step 3** Wire into `services/order_router/main.py` startup: if sentinel present, log + exit with code 3 (don't start).
- [ ] **Step 4** Commit.

---

## Task 4: `scripts/trading/flatten_all.py`

CLI entrypoint for spec §6.2 step 1: `sts futures flatten-all --confirm`.

- [ ] **Step 1** Test: default (no `--confirm`) → dry-run report only; with `--confirm` → actually issues market-close orders for every open futures position.
- [ ] **Step 2** Implement. Reuses Phase 4's `force_close` paths.
- [ ] **Step 3** Add Click command to `cli/main.py` so `sts futures flatten-all` works.
- [ ] **Step 4** Commit.

---

## Task 5: `config/futures_live.yaml` + `LiveModeGuard`

Live-account configuration + a small runtime guard that order_router consults before submitting orders.

- [ ] **Step 1** Write YAML:
  ```yaml
  futures_live:
    enabled: false                  # must be true AND Gate 2 checklist complete
    max_position_size_contracts: 1  # Gate 3 starts here
    max_daily_trades: 2             # stricter than Phase 3's risk.yaml
    symbol_lock_enabled: true
    account_suffix: "_live"          # env-var suffix convention
    suspend_key: "futures:live:suspended"  # Redis flag for manual pause
  ```
- [ ] **Step 2** `shared/execution/live_mode_guard.py` — `ServiceConfigBase` subclass + `is_live_suspended(redis) -> bool` helper.
- [ ] **Step 3** Test: enabled=false → always suspended; enabled=true + flag absent → not suspended; flag=1 in Redis → suspended.
- [ ] **Step 4** Wire into `order_router/main.py` before each order submission.
- [ ] **Step 5** Commit.

---

## Task 6: Grafana dashboards (3 new)

**Scope:** JSON + provisioning entries only. Match existing dashboards at `grafana/dashboards/` (infra convention from Phase 1/4).

- [ ] **Step 1** `futures-paradigm-overview.json` — panels: today PnL (stat), open positions (table), signal count by setup (timeseries 24h), fills count by setup.
- [ ] **Step 2** `futures-paradigm-risk.json` — panels: daily MDD gauge vs limit, weekly MDD gauge, consecutive-loss counter, kill-switch condition state (6 gauges with threshold line).
- [ ] **Step 3** `futures-paradigm-live-ladder.json` — panels: current contract size, Gate 3 progress bar (days completed / 14), cumulative net PnL, cumulative slippage, API error rate.
- [ ] **Step 4** No tests (JSON is declarative + reviewed by ops). Commit with a brief README in `grafana/dashboards/phase5-readme.md`.

---

## Task 7: Runbooks (4 new)

Each follows the project convention (Phase 1/2/3 runbook format — checkbox gate items + rollback steps).

- [ ] **Step 1** `docs/runbooks/futures-paradigm-operations.md` — daily checklist (09:00 status check, noon signal review, 15:30 EOD flat, overnight macro ready-check).
- [ ] **Step 2** `docs/runbooks/futures-paradigm-rollback.md` — spec §6.2 steps + runbook-style command block + 24-hour cooldown rule + re-validation requirement.
- [ ] **Step 3** `docs/runbooks/futures-legal-review.md` — Gate 2 §2.2 deliverable. Template with sections for broker ToS review, tax (파생상품 양도세), KIS real-TR-ID transition, session-time compliance.
- [ ] **Step 4** `docs/runbooks/phase5-verification.md` — Gate 1-3 checklists matching spec §2.
- [ ] **Step 5** Commit: `docs(runbooks): Phase 5 operations / rollback / legal / gate`.

---

## Task 8: Rollback drill script

Spec §6.3 — weekend drill.

- [ ] **Step 1** `scripts/drills/rollback_drill.sh` — automates spec §6.2 steps 1-7 in a dry-run mode with timing output.
- [ ] **Step 2** Drill report written to `reports/drills/rollback_YYYYMMDD.txt` (committed) with step durations and any errors.
- [ ] **Step 3** Calendar reminder: 6-month cadence (note in operations runbook).
- [ ] **Step 4** Commit.

---

## Task 9: CLAUDE.md sync

Spec §7.2 — update the root CLAUDE.md's `선물 (Futures)` section.

- [ ] **Step 1** Add Setup A/C to "현재 운용 전략" list alongside `rl_mppo`.
- [ ] **Step 2** Update `rl_mppo` description: "메인 → 병행 (별도 계좌)".
- [ ] **Step 3** Link `futures_contract_spec` section of `config/execution.yaml`.
- [ ] **Step 4** Add pointer to Phase 5 runbooks.
- [ ] **Step 5** Commit: `docs(claude): Phase 5 futures-paradigm ops note`.

---

## Task 10: Full sweep + push + draft PR

- [ ] **Step 1** `pytest tests/ -v` — full sweep, no regressions.
- [ ] **Step 2** Format modified files only.
- [ ] **Step 3** Push `feat/futures-paradigm-phase5` + draft PR.
- [ ] **Step 4** PR body lists Gate 1-3 progression + links to runbooks.
- [ ] **Step 5** Merge gated on:
    - Gate 1 passed (Phase 4 paper → Phase 5 Gate 1 is a ≥2-week paper extension per §2.1)
    - Gate 2 checklist complete (legal + tax + KIS real-TR-ID smoke test + position-recovery drill)
    - Gate 3 passed (1-contract live 2 weeks, MDD -3% 0 events, net+ after slip+fees)
    - Weekly Edge Review 8 consecutive weeks published (counted from Phase 4 mid-point)
    - Rollback drill completed once with acceptable step-timings

---

## Self-Review

**Spec coverage (phase5-rollout.md §2-§7):**

| Spec item | Tasks |
|-----------|-------|
| Gate 1 paper extension | operational — no task (just runtime observation) |
| Gate 2 prep (legal/tax/recover_positions) | 3, 7 |
| Gate 3 1-contract live | 5 (live_mode_guard enforces), 6 (monitoring) |
| Gate 4 increment | out of scope for code — spec says user-approved step |
| Weekly Edge Review cron | 2 |
| Grafana dashboards | 6 |
| `rl_mppo` parallel + symbol lock | reuses Phase 4's risk_filter `has_open_position_provider` |
| Rollback drill | 4, 8 |
| Runbooks | 7 |
| CLAUDE.md sync | 9 |

Grafana and runbook content is deliberately light on prescriptive JSON/text in this plan — operators will adapt during the 2-week live window. Task 6 lists the panel set; final JSON is composed during execution.

**Carried-forward lessons:**
- ServiceConfigBase for every new config (Task 5)
- No dead YAML (live_mode_guard has a real caller in order_router)
- Graceful shutdown on daemons (not applicable — Phase 5 adds no daemons)
- Format/lint modified files only

**Risks flagged + mitigations:**
- Live KIS API different from paper (TR IDs, rate limits, error codes). Gate 2 item catches this via smoke test.
- Position recovery misfire (broker has position that Redis doesn't). Task 3's sentinel file prevents silent double-entry.
- Increment pressure (1→2 contracts). Spec explicitly requires user approval; live_mode_guard enforces stepping via YAML.
- `rl_mppo` accidental double-entry on same symbol. `has_open_position_provider` (Phase 4 Task 12) queries both `trading:futures:positions` (rl_mppo's hash) and the Phase 4 runtime state; either hit → reject.

**Placeholder scan:**
- `config/futures_live.yaml::account_suffix: "_live"` is a convention — the actual KIS env-var mapping needs a one-line verification during Gate 2 (RUN checklist item).

---

## Execution Handoff

Two execution options (Phase 1-4 pattern):

1. **Subagent-Driven** — 10 tasks; but several (Grafana JSON, runbooks, CLAUDE.md) are content work better done inline by a single writer for consistency. Recommended split: dispatch Tasks 2, 3, 4, 5 to subagents; do Tasks 6, 7, 9 inline.
2. **Inline** — straight through; Phase 5 is ~40% the code volume of Phase 4 so a single-session pass is realistic.

Phase 5 completion doesn't trigger a new phase — RL repurposing spec is the only optional follow-up. Master plan §3 marks Phase 5 as the "terminal" phase of the paradigm.
