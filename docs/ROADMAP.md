# Roadmap — KIS Unified Trading Platform

> **Authoritative roadmap — supersedes scattered plan docs. Last updated 2026-06-25 KST.**

This is the single per-asset roadmap. For the live runtime snapshot see
[PROJECT_STATUS.md](PROJECT_STATUS.md); for the plan catalogue see
[plans/INDEX.md](plans/INDEX.md). Status legend: **done** ✅ · **in-progress** 🔄 ·
**planned** ⏳.

Trusted current sources cited below:
[PROJECT_STATUS.md](PROJECT_STATUS.md),
[plans/INDEX.md](plans/INDEX.md),
[plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md](plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md),
[plans/2026-06-22-quant-ops-workbench-uiux.md](plans/2026-06-22-quant-ops-workbench-uiux.md),
[runbooks/futures-pipeline-cutover-f9.md](runbooks/futures-pipeline-cutover-f9.md),
[runbooks/stock-pipeline-cutover-m5d.md](runbooks/stock-pipeline-cutover-m5d.md).

All times are KST (Asia/Seoul). Strategy `enabled` flags in
`config/strategies/{stock,futures}/*.yaml` are the single source of truth for
active/disabled state.

---

## UI/UX — Quant Ops Workbench

### North Star

Turn the existing dashboard and Strategy Lab into a **Quant Ops Workbench**:
one operator surface that answers, in order, whether the system is healthy,
why a signal happened or was rejected, how risk/exposure changed, whether paper
behavior matches backtest evidence, and what gate is needed before promotion.

The product model follows the standard quant workflow:

```text
Universe / data quality -> signal decision trace -> portfolio/risk ->
execution lifecycle -> backtest-vs-paper comparison -> promotion gate
```

### Current operating state

- Existing Next.js UI (`strategy-builder-ui/`) has Cockpit, positions, signals,
  trades, experiments, builder, and execute pages.
- Dashboard APIs already expose parts of the required state: health/process,
  data freshness, kill switch, forecasting, positions, signals, trades/fills,
  Strategy Lab preview/order-ticket endpoints, and stock experiment reports.
- The main gap is not raw data availability. The gap is decision UX: current
  pages do not yet merge health, data quality, risk, signal reasons, order/fill
  lifecycle, backtest evidence, and promotion gates into operator workflows.

### Phases

| Phase / Milestone | Status | Gate / Owner |
|---|---|---|
| Quant Ops Workbench plan (multi-agent implementation lanes, contracts, gates) | ✅ done | [plans/2026-06-22-quant-ops-workbench-uiux.md](plans/2026-06-22-quant-ops-workbench-uiux.md) |
| P0 Ops Cockpit 2.0 | ✅ done | `/api/health/summary` now exposes ops summary DTO with process/data freshness/scheduler/producers/forecasting/pipeline/mode |
| P0 Signal Decision Trace | ✅ done | `/signals` shows trace summary, reject/orderability fields, and linked order/fill/position/trade ids when present |
| P0 Risk & Exposure Board | ✅ done | `/risk` shows portfolio totals, strategy exposure, symbol exposure, daily loss, and futures long/short signed exposure |
| P0 Backtest-vs-Paper Comparator | ✅ done | `/experiments` compares latest stock experiment evidence against RuntimeLedger paper trades |
| P1 Signal -> Order -> Fill lifecycle blotter | ✅ done | `/api/trades/lifecycle` and `/trades` timeline panel show partial signal/order/fill/position/trade lineage |
| P1 Strategy Promotion Kanban | ✅ done | `/builder` includes read-only Draft -> Live Gated board with explicit present/missing/not-available evidence |
| P1 Universe & Data Coverage Explorer | ✅ done | `/coverage` and `/api/coverage` show screener universe, trade targets, daily indicator gaps, and latest experiment coverage |
| P2 Setup C / Event Context diagnostics | ✅ done | `/event-context` and `/api/event-context/diagnostics` show Setup C latest eval, event-score freshness/sparsity, source timeline, config mismatch warnings, and no-signal root cause |
| P2 Workbench UI/UX QA pass | ✅ done | Vitest/Testing Library smoke coverage plus Playwright fallback desktop/mobile screenshots cover `/risk`, `/coverage`, `/trades`, `/builder`, `/event-context`; evidence: [testing/quant-ops-workbench-2026-06-25.md](testing/quant-ops-workbench-2026-06-25.md) |

### Open next-steps

- Refresh and retain desktop/mobile screenshot/accessibility QA artifacts when
  Workbench routes change, especially `/risk`, `/coverage`, `/trades`,
  `/builder`, and `/event-context`.
- Keep all new work paper-safe. UI may inspect paper order tickets, but must not
  introduce live order controls or bypass futures live gates.

---

## Cross-Cutting Code Quality

### Current operating state

- Shared entry-session/cooldown gates now live in
  `shared/strategy/entry/gates.py`; `mean_reversion`, `williams_r`,
  `momentum_breakout`, and the compatible `opening_volume_surge` open gate use
  the shared path with behavior-level regression coverage.
- Builtin strategy registration is table-driven in `shared/strategy/registry.py`
  and covered for idempotency plus restored entry/exit/sizer keys.
- Runtime defaults are centralized in `shared/config/runtime_defaults.py`;
  service entrypoints use Redis DB 1 by default, and operator docs now state
  `DASHBOARD_HOST_PORT=5081` for paper/local while Caddy remains internal `:5080`.
- Workbench frontend refresh intervals are centralized in
  `strategy-builder-ui/src/lib/dashboard/queryIntervals.ts`.
- Strategy Builder state logic is split into pure reducer and YAML serializer
  modules with focused tests.
- `/trades` is split into a shell, tab list, live/history tab components, and
  query hooks without changing query keys, polling, or tab accessibility behavior.
- Futures broker/ledger reconciliation is extracted from the 8k-line
  orchestrator into `services/trading/broker_verification.py` with isolated unit
  tests.
- `LLMConfig.from_yaml` is split into private YAML loading/section/config-dict
  helpers with characterization tests for absolute/relative loading, legacy
  stock/futures fallbacks, and env overrides.

### Completed maintainability milestones

| Milestone | Status | Gate / Owner |
|---|---|---|
| Dead/stale docs and unused-code cleanup | ✅ done | `b8cec3d`; stale docs archived, dashboard host-port drift audited |
| Multi-agent code-quality cleanup plan | ✅ done | [superpowers/plans/2026-06-25-code-quality-cleanup-multi-agent.md](superpowers/plans/2026-06-25-code-quality-cleanup-multi-agent.md) |
| Shared strategy entry gates + behavior tests | ✅ done | `shared/strategy/entry/gates.py`, `tests/unit/strategy/entry/` |
| Strategy registry table-driven registration | ✅ done | `tests/unit/strategy/test_registry_builtin_components.py` |
| Runtime defaults centralization | ✅ done | `shared/config/runtime_defaults.py`, `CLAUDE.md` |
| Builder state/YAML serializer extraction | ✅ done | `strategy-builder-ui/src/lib/builder/` |
| Trades page component/hook split | ✅ done | `strategy-builder-ui/src/app/trades/` |
| Broker verification extraction | ✅ done | `services/trading/broker_verification.py` |
| LLM YAML loader helper split | ✅ done | `tests/unit/llm/test_config_yaml_loading.py` |

### Open next-steps

- Continue decomposing `services/trading/orchestrator.py`; broker verification
  is extracted, but initialization, recovery, execution setup, and metrics
  remain high-complexity regions.
- Add a narrow orchestrator delegation test that locks the
  `_verify_positions_with_broker` dependency handoff to `BrokerPositionVerifier`.
- Add optional guardrail tests for `momentum_breakout` trend-mode cooldown and
  `opening_volume_surge` post-close behavior so the no-new-close-window contract
  remains explicit at the strategy level.
- Keep extracting shared runtime defaults from remaining large runtime modules
  only when it does not blur ownership or change live/paper behavior.
- Run browser/screenshot QA again after `/trades` changes are deployed or when
  the Workbench visual surface changes materially.

---

## Stock

### North Star

Cost-adjusted positive absolute return — after a ~0.50% round-trip cost,
Sharpe > 1.0 with positive monthly expected value — plus a visual **Strategy Lab**
that shortens the design → backtest → paper → feedback loop.

### Current operating state

- **Paper only.** No live trading: the real accounts lack margin/education
  approval. A real KIS key supplies market data; orders go through the
  `VirtualBroker` (`KIS_REAL_TRADING=false`).
- **Pipeline (decoupled Compose):** screener/universe → M4-P (strategy) →
  M4-R (risk) → M4-O (order) → M4-X (three-stage, signal-driven exit; **no
  blanket EOD liquidation**) → M5a (monitor). The monolithic stock orchestrator
  is blocked after cutover (`STOCK_ORCHESTRATOR_ENABLED=false`).
- **Enabled strategies (2026-06-25):** `momentum_breakout` (re-enabled for paper
  observation, #443), `pattern_pullback`, `williams_r`.
- **Disabled:** `bb_reversion`, `opening_volume_surge` (+variants),
  `volume_accumulation`, `trend_pullback`, `vr_composite`,
  `technical_consensus` (0% win 2026-06-02), `trend_continuation_vwap`,
  `daily_pullback`, `trix_golden`, `llm_adaptive_sizing_example`,
  `opening_volume_surge_combo_balanced`, `opening_volume_surge_score_1p8`,
  `trend_pullback_consensus_exit`.

### Phases

| Phase / Milestone | Status | Gate / Owner |
|---|---|---|
| Decoupled Compose pipeline (M5d cutover: `stock-ingest` + 5 services; monolith blocked) | ✅ done | [runbooks/stock-pipeline-cutover-m5d.md](runbooks/stock-pipeline-cutover-m5d.md) |
| Host-cron → Compose scheduler/producers migration | ✅ done | operator |
| Bear-exit regime wiring (#458: M4-P publishes regime → M4-X bear-exit gate) | ✅ done | — |
| Experiment runner Phase 1–5 (#473–#477: `sts experiment run` + nightly 16:40 KST + `/api/experiments` + `/experiments` UI + 30-day minute backfill) | ✅ done | — |
| HAR-RV log-RV forecast transition | 🔄 in-progress | model JSON preserves RV history after reload; local CSV/Parquet refit and raw-vs-log validation CLIs exist; real-data refit/backtest + ~1wk shadow still required before switching config from `rv_target: raw` |
| `technical_consensus` reactivation | 🔄 in-progress | strong long-horizon backtest vs recent ~3wk live loss → regime-verify, then small |
| `momentum_breakout` redesign / retune | 🔄 in-progress | retune still negative (recent Sharpe ≈ −5.24); observe in paper |
| Strategy Lab Phase 1–7 (visual design → backtest → paper → feedback) | 🔄 in-progress | design done ([plans/2026-05-26-strategy-lab-extension-design.md](plans/2026-05-26-strategy-lab-extension-design.md)); Quant Ops Workbench UI/UX expansion complete ([plans/2026-06-22-quant-ops-workbench-uiux.md](plans/2026-06-22-quant-ops-workbench-uiux.md)); remaining Strategy Lab work is non-Workbench backtest/paper workflow depth |
| Position-recovery drill + Redis/SQLite E2E smoke | ⏳ planned | after each cutover / process restart |
| MLflow restart (localhost:5000 down) | ⏳ planned | ops |
| Stock live trading | ⏳ planned (blocked) | requires margin/education approval on real accounts; separate promotion tier |

### Open next-steps

- Validate HAR-RV log-RV against real data with
  `scripts/forecasting/validate_har_rv.py` (local file-backed raw-vs-log report),
  then backtest + 1-week shadow before cutting the forecast model over. Model
  serialization preserves RV history and the log-RV/refit code path exists, but
  default config remains `rv_target: raw` until the validation gate passes. See
  [runbooks/har-rv-log-rv-validation.md](runbooks/har-rv-log-rv-validation.md) and
  [plans/2026-06-02-stock-reopt-har-rv-followups.md](plans/2026-06-02-stock-reopt-har-rv-followups.md).
- Decide `technical_consensus` reactivation after regime verification (small size
  first); use `scripts/ops/stock_strategy_readiness.py` with real backtest/paper
  evidence before any YAML change.
- Continue non-Workbench Strategy Lab build-out for deeper design, backtest,
  paper feedback, and reactivation-gate workflows.
- Run the position-recovery drill and the Redis + SQLite E2E smoke; use
  `scripts/ops/ops_readiness_check.py` as the offline checklist before/after cutovers.
- Restart MLflow for experiment tracking.

---

## Futures

### North Star

The **LLM interprets market context** (veto / risk-mode / size / threshold), and
an **indicator + rule strategy (Setup A/C) owns entry/exit timing**. Thresholds
live in YAML; runtime state is Redis DB 1 + the SQLite ledger. RL/TFT prediction
paths are removed and must not be reintroduced
([plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md](plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md)).

### Current operating state

- **Paper, live-gated.** Live is guarded by `config/futures_live.yaml::enabled`
  (= false) plus the Redis flag `futures:live:suspended`
  (`shared/execution/live_mode_guard.py`).
- Runs the monolithic `trader-futures` orchestrator. The decoupled chain is
  **dormant** (pre-F-9): profiles `futures-ingest`, `futures-pipeline`,
  `futures-killswitch` exist with a double-trade guard, but the daemons are not
  registered in the running Compose stack.
- **Enabled strategies (2026-06-25):** `setup_a_gap_reversion` (fires live
  signals), `setup_c_event_reaction` (coded but ~0 signals — event scores need
  real production/observation; bounded history is now retained for diagnostics).
- **Disabled / deprecated:** `williams_r_15m` (reference), `bb_reversion_15m`
  (disabled — triggered a stock BEAR_EXIT, #479), `macd_ema_crossover_15m`,
  `momentum_breakout_futures`, `trend_pullback_futures`,
  `trix_golden_futures`; `llm_directed_indicator` deprecated.
  `track_a_exit.yaml` is a reusable exit config, not a top-level strategy. All
  trend strategies collapse in walk-forward (intraday futures are mean-reverting)
  — do not enable.

### Phases

| Phase / Milestone | Status | Gate / Owner |
|---|---|---|
| Phase 1–4 paradigm shift (data infra, scoring, decision engine, execution) | ✅ done | — |
| Phase 2 cutover (LLM-primary + Setup A/C; RL shadow → off, 2026-05-11) | ✅ done | — |
| RL/TFT fully removed (#402, 2026-06-03) | ✅ done | [plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md](plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md) |
| F-1..F-8 decoupled chain implemented + double-trade guard (#424–#431) | ✅ done | — |
| RegimeGate P2-③ injected (#330) | ✅ done | ClickHouse audit table best-effort → PERMISSIVE on miss (no behavior change) |
| Over-trading / fast stop-out fixes (#479) | ✅ done | — |
| Reject-reason observability (#483) + throttled setup-eval logging (#484) | ✅ done | — |
| F-9 shadow validation (Gate 1: `--profile futures-pipeline`, 3–5 trading days) | 🔄 in-progress | operator-gated; [runbooks/futures-pipeline-cutover-f9.md](runbooks/futures-pipeline-cutover-f9.md) |
| F-9 Gate 2 → decoupled cutover (replace orchestrator path) | ⏳ planned | operator written approval; `trader` flag false + daemon-mode env |
| Phase 5 Gate 1–3 → small live (100 signals + backtest ±20% + MDD/slippage + kill-switch drill) | ⏳ planned | [plans/2026-04-20-futures-paradigm-phase5-rollout.md](plans/2026-04-20-futures-paradigm-phase5-rollout.md) (procedure; RL/systemd/ClickHouse refs there are historical) |
| Setup C activation | 🔄 in-progress | runtime enforces configured event-score minimum; `ForecastPublisher` keeps bounded Redis event-score history; `/event-context` and `scripts/ops/setup_c_event_score_observe.py` surface readiness; needs real scored-event production/observation to prove eligible signals |
| Kill-switch sentinel → shared-volume path | ✅ done | default is `/app/data/runtime/kis_kill_switch.tripped`, shared by kill-switch/order-router containers |
| Futures cutover verify/rollback automation script (stock analogue exists) | ✅ done | `scripts/ops/futures_cutover_verify.py` read-only audit/strict gate rejects placeholder evidence; `scripts/ops/futures_evidence_bundle.py` compiles F-9/Phase 5 evidence; env examples expose `FUTURES_ORCHESTRATOR_ENABLED`; rollback helper is dry-run-first |
| HAR-RV log-RV validation (futures side) | 🔄 in-progress | log-RV model target, RV-history serialization, KST regular-session RV, and local file-backed refit/validation CLIs exist; real-data validation/shadow remains open |

### Open next-steps

- Run F-9 Gate 1 shadow (`docker compose --profile futures-pipeline ...`,
  3–5 trading days), then Gate 2, then operator-gated cutover —
  [runbooks/futures-pipeline-cutover-f9.md](runbooks/futures-pipeline-cutover-f9.md).
  Use `scripts/ops/futures_evidence_bundle.py` to reject incomplete or placeholder
  F-9/Phase 5 evidence before operator review.
- Drive Phase 5 Gate 1–3 toward a small live allocation (procedure in the
  archived master is superseded; use the phase5-rollout doc's gate procedure).
- Run/observe real event scoring so Setup C has enough fresh score history to
  evaluate eligible signals; use `scripts/ops/setup_c_event_score_observe.py` to
  produce the readiness report.
- Run `scripts/ops/futures_cutover_verify.py --strict` with Gate 1 evidence and
  written approval before cutover; repo-local sentinel/env checks are wired, so
  the remaining blockers are operator-supplied shadow evidence and approval.
