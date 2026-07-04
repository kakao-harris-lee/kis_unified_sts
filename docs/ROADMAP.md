# Roadmap — KIS Unified Trading Platform

> **Authoritative roadmap — supersedes scattered plan docs. Last updated 2026-07-04 KST.**

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
[runbooks/stock-pipeline-cutover-m5d.md](runbooks/stock-pipeline-cutover-m5d.md),
[superpowers/specs/2026-06-27-signals-decision-trace-design.md](superpowers/specs/2026-06-27-signals-decision-trace-design.md),
[testing/quant-ops-workbench-2026-06-27.md](testing/quant-ops-workbench-2026-06-27.md),
[investigations/2026-06-28-quant-system-gap-research.md](investigations/2026-06-28-quant-system-gap-research.md),
[plans/2026-07-04-runtime-refactoring-roadmap.md](plans/2026-07-04-runtime-refactoring-roadmap.md),
[plans/2026-07-02-unified-investment-system-roadmap.md](plans/2026-07-02-unified-investment-system-roadmap.md).

All times are KST (Asia/Seoul). Strategy `enabled` flags in
`config/strategies/{stock,futures}/*.yaml` are the single source of truth for
active/disabled state.

---

## Cross-Asset — Unified Investment System & Market Risk

### North Star

Operate stock + futures (+ a manual long-term core portfolio) under **one
market view**: a config-driven Market Risk Score (0–100) built from futures
market structure (foreign futures flow, open interest, program trading, basis)
plus macro inputs (USD/KRW, overseas futures, volatility), driving a unified
RISK_ON / NEUTRAL / RISK_OFF regime, per-track reaction rules (score ≥ 70 →
no new longs + hedge review), an integrated whole-asset MDD circuit breaker,
and full dashboard transparency.

Master strategy doc: [통합_투자_시스템_전략_설계서.md](통합_투자_시스템_전략_설계서.md).
Implementation roadmap (authoritative for this track, includes design-doc ↔
codebase reconciliation):
[plans/2026-07-02-unified-investment-system-roadmap.md](plans/2026-07-02-unified-investment-system-roadmap.md).

### Current operating state (2026-07-03)

- **Phases 0–6 are merged to main.** The composite Market Risk Score, unified
  regime, `/market` dashboard, track gates, whole-asset MDD circuit breaker,
  mini-KOSPI200 hedge advisor, Track A ledger, and feedback reports now exist —
  the pre-Phase-0 gaps (collected-but-unused market structure, no composite
  score, no `/market` page) are closed.
- **Every risk-bearing gate defaults to `mode: shadow`.** Track gates (P2) and
  the MDD circuit breaker (P3) annotate/log but do not block, resize, or trip;
  the pre-existing regime mechanisms (HAR-RV `RegimeGate`, stock median-MFI
  bear-exit, LLM `risk_mode`) are unchanged and the new Market Risk Score layers
  on top rather than replacing them.
- The remaining work is **operator gates**: backfill + scheduler image rebuild
  to activate the new crontab entries, the shadow→enforce flips, the
  circuit-breaker `--execute` drill, and Track A holdings registration. See the
  cross-asset plan doc for the full checklist and open items O11–O17.

### Phases

| Phase / Milestone | Status | Gate / Owner |
|---|---|---|
| P0 Market-structure data foundation (KIS TR spike, collectors for foreign futures flow / OI / program / basis / FX / overseas futures / KRX night-session close, Parquet daily history + backfill) | ✅ code merged | Merged 2026-07-02. Operator gate: live-key probes, night tr_key, KRX CSV backfill, scheduler image rebuild, 10 clean trading days + data-quality report |
| P1 Market Risk Score + unified regime engine (0–100 composite, bands, hysteresis, shadow-only) + `/market` page v1 + alerts | ✅ code merged | Merged 2026-07-03. Operator gate: backfill hindcast shows score ≥ 70 discriminates forward returns; ≥10-day shadow; operator review |
| P2 Track enforcement (stock M4-P long-block ≥ 70, futures size/direction modulation via reaction matrix YAML; trace integration) | ✅ code merged (shadow) | Merged 2026-07-03. `market_risk_gate.yaml::mode: shadow`. Operator gate: shadow → enforce flip is operator-approved; 2-week block/allow review |
| P3 Integrated risk budget (whole-asset MDD −5/−8/−12 circuit breaker, `track_id` ledger tagging, track capital caps) | ✅ code merged (shadow) | Merged 2026-07-03. Offline drill 11/11. Operator gate: `--execute` drill + kill-switch drill on paper server before enforce |
| P4 Hedge advisor (net β-exposure vs futures, mini-KOSPI200 contract recommendation — advisory only, no auto orders) | ✅ code merged | Merged 2026-07-03. Mini KOSPI200 (O4). Operator gate: recommendation-quality review on a real HIGH-band episode before any separate auto-hedge plan |
| P5 Track A (core portfolio) ledger, Kill Criteria YAML, Tier 3 watch, quarterly rebalancing runbook | ✅ code merged | Merged 2026-07-03. Empty ledger (rules no-op). Operator gate: register holdings, first quarterly rebalancing record |
| P6 Integrated feedback loop (weekly slippage/edge, monthly equity curve, quarterly track verdicts) | ✅ code merged | Merged 2026-07-03. Read-only. Operator gate: first 6-month integrated evaluation |

### Open next-steps

- P0 operator items before daily operation: run the 3 remaining live-key KIS
  probes (program-trade daily row cap, SOX symbol notation, night-code REST
  response), confirm the active near-month night tr_key in
  `config/night_futures.yaml`, export the KRX login CSV for foreign-futures
  history (`--from-csv` backfill path), and rebuild the scheduler image to
  activate the new crontab entries (07:45 / 05:48 / 08:00 / 18:40 KST).
- Resolve the non-blocking review findings recorded as O11 in the plan doc
  (backfill FX alignment before the Phase 1 hindcast, missing-vs-flat OI
  signal masking, weekend night-close TTL policy) and start the 10-trading-day
  clean-collection observation.
- Keep every new gate fail-open (shadow → counterfactual → enforcement),
  following the RegimeGate P2-③ precedent; never source the risk score from the
  synthetic (`np.random`) LLM analyzer paths.
- This track layers on top of the per-asset roadmaps below; it does not change
  F-9, Phase 5 live, or Setup C/D gates.

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
- Decision transparency has moved from compact list fields to an enriched
  signal-level trace: LLM context, strategy inputs, thresholds, risk/orderability
  state, lifecycle lineage, scorecard, and degraded evidence gaps are visible.
- The current gap is strategy/asset-level evidence governance: operators need
  Setup A/C/D and stock-strategy evidence slices that connect traces to
  paper-vs-backtest performance, promotion gates, and market-structure policy.

### Phases

| Phase / Milestone | Status | Gate / Owner |
|---|---|---|
| Quant Ops Workbench plan (multi-agent implementation lanes, contracts, gates) | ✅ done | [plans/2026-06-22-quant-ops-workbench-uiux.md](plans/2026-06-22-quant-ops-workbench-uiux.md) |
| P0 Ops Cockpit 2.0 | ✅ done | `/api/health/summary` now exposes ops summary DTO with process/data freshness/scheduler/producers/forecasting/pipeline/mode |
| P0 Signal Decision Trace | ✅ done | `/signals` and `GET /api/signals/{signal_id}/trace` show LLM context, strategy inputs, thresholds, risk/orderability detail, lifecycle lineage, scorecard, and evidence gaps |
| P0 Risk & Exposure Board | ✅ done | `/risk` shows portfolio totals, strategy exposure, symbol exposure, daily loss, and futures long/short signed exposure |
| P0 Backtest-vs-Paper Comparator | ✅ done | `/experiments` compares latest stock experiment evidence against RuntimeLedger paper trades |
| P1 Signal -> Order -> Fill lifecycle blotter | ✅ done | `/api/trades/lifecycle` and `/trades` timeline panel show partial signal/order/fill/position/trade lineage |
| P1 Strategy Promotion Kanban | ✅ done | `/builder` includes read-only Draft -> Live Gated board with explicit present/missing/not-available evidence |
| P1 Universe & Data Coverage Explorer | ✅ done | `/coverage` and `/api/coverage` show screener universe, trade targets, daily indicator gaps, and latest experiment coverage |
| P2 Setup C / Event Context diagnostics | ✅ done | `/event-context` and `/api/event-context/diagnostics` show Setup C latest eval, event-score freshness/sparsity, source timeline, config mismatch warnings, and no-signal root cause |
| P2 Workbench UI/UX QA pass | ✅ done | Vitest/Testing Library smoke coverage plus Playwright fallback desktop/mobile screenshots cover `/risk`, `/coverage`, `/trades`, `/builder`, `/event-context`, and `/signals`; evidence: [testing/quant-ops-workbench-2026-06-25.md](testing/quant-ops-workbench-2026-06-25.md), [testing/quant-ops-workbench-2026-06-27.md](testing/quant-ops-workbench-2026-06-27.md) |

### Open next-steps

- Refresh and retain desktop/mobile screenshot/accessibility QA artifacts when
  Workbench routes change, especially `/risk`, `/coverage`, `/trades`,
  `/builder`, `/event-context`, and `/signals`.
- Add per-asset and per-strategy evidence dashboards so individual signal traces
  roll up into Setup A/C/D, stock-strategy, paper-vs-backtest, and promotion-gate
  decisions.
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
- Open-position metrics synchronization is extracted into
  `services/trading/metrics_sync.py`; the helper preserves the existing
  `position_count` contract and falls back to list-style open-position counting.
- `_verify_positions_with_broker` now has a focused delegation test that locks
  the dependency handoff to `BrokerPositionVerifier`.
- `LLMConfig.from_yaml` is split into private YAML loading/section/config-dict
  helpers with characterization tests for absolute/relative loading, legacy
  stock/futures fallbacks, and env overrides.
- Strategy-level guardrail tests now lock `momentum_breakout` trend-mode
  cooldown behavior and `opening_volume_surge` post-close behavior when no
  explicit cutoff is configured.
- The active runtime refactoring plan is
  [plans/2026-07-04-runtime-refactoring-roadmap.md](plans/2026-07-04-runtime-refactoring-roadmap.md):
  add thin Interface/Decorator/Factory surfaces first, then split high-cost
  modules while preserving stream contracts and runtime behavior.
- Runtime large-file refactoring priority 3 is merged. The public import
  surfaces remain compatible, while position tracking, indicator streaming,
  market-data provider, stock strategy daemon, and SQLite runtime-ledger
  behavior are split into focused model/mixin/helper modules.

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
| Orchestrator metrics sync helper | ✅ done | `services/trading/metrics_sync.py` |
| Broker verifier delegation guard | ✅ done | `tests/unit/trading/test_orchestrator_broker_verifier_delegation.py` |
| Strategy close/cooldown guardrails | ✅ done | `tests/unit/strategy/entry/test_entry_gate_integration_momentum_opening.py` |
| `/trades` screenshot/interaction QA refresh | ✅ done | [testing/quant-ops-workbench-2026-06-25.md](testing/quant-ops-workbench-2026-06-25.md) |
| LLM YAML loader helper split | ✅ done | `tests/unit/llm/test_config_yaml_loading.py` |
| Runtime large-file split priority 3 | ✅ done | `83e94681`; `position_tracker`, `indicator_engine`, `data_provider`, `stock_strategy/daemon`, `runtime_ledger` split with targeted pytest/ruff/black/py_compile |

### Refactoring roadmap

| Milestone | Status | Gate / Owner |
|---|---|---|
| Runtime large-file split priority 3 | ✅ done | `services/trading/position_tracker.py`, `indicator_engine.py`, `data_provider.py`, `services/stock_strategy/daemon.py`, and `shared/storage/runtime_ledger.py` reduced to focused shells plus extracted modules |
| Thin strategy/context interfaces | 🟡 branch implemented | `shared/decision/interfaces.py`, `shared/strategy/interfaces.py`, `shared/portfolio/interfaces.py`; existing dataclasses/classes remain compatible |
| Retry decorator surface | 🟡 branch implemented | `shared/resilience/retry.py::retry_on_disconnect`; default retries are limited to disconnect/timeout exceptions |
| Strategy factory split | 🟡 branch implemented | `shared/strategy/factory.py`, `shared/strategy/builtin_components.py`; `shared/strategy/registry.py` remains the backward-compatible facade |
| Setup adapter decomposition | 🟡 branch implemented | Split `shared/strategy/entry/setup_adapters.py` into config, context-builder, signal-mapper, setup-eval publisher, and LLM-gate modules while keeping adapter classes on the compatibility facade |
| Orchestrator runtime config extraction | 🟡 branch implemented | `services/trading/runtime_config.py`; `services/trading/orchestrator.py` keeps facade exports for existing imports |
| Trading package lazy facade | 🟡 branch implemented | `services/trading/__init__.py` resolves top-level exports lazily so config/module imports do not eagerly load the monolithic orchestrator |
| Re-entry guard helper split | 🟡 branch implemented | `services/trading/reentry_guard.py`; orchestrator keeps compatibility methods while cooldown key/record/block logic lives in owner helpers |
| Execution helper split | 🟡 branch implemented | `services/trading/execution_facade.py`; orchestrator keeps compatibility methods while pure order-result/direction helpers live in an owner module |
| Recovery helper split | 🟡 branch implemented | `services/trading/recovery.py`; Redis recovery keeps orchestrator side effects while freshness and reconstruction logic lives in an owner module |
| Market-data bootstrap split | 🟡 branch implemented | `services/trading/market_data_bootstrap.py`; orchestrator facades assign KIS client, price feed, data provider, and tick publisher results |
| Orchestrator decomposition | ⏳ planned | Continue extracting initialization, recovery, execution setup, position transitions, and guard hooks from `services/trading/orchestrator.py` behind delegation tests |
| Event-driven futures primary runtime | ⏳ planned | Keep F-9 as the only approved replacement path for the monolithic futures runtime; validate shadow chain and O13 kill-switch coverage before cutover |

### Open next-steps

- Follow the active runtime refactoring plan: thin contracts, retry decoration,
  setup adapter decomposition, registry/factory split, and runtime config
  extraction are branch-implemented; the trading package facade now resolves
  exports lazily, and re-entry guard/execution helper logic have owner modules,
  so next split the remaining high-complexity regions of
  `services/trading/orchestrator.py`.
- Treat the monolithic futures path as a compatibility runtime until F-9
  cutover. New decomposition should move toward the existing event-driven
  chain (`market_ingest -> decision_engine -> risk_filter -> order_router ->
  futures_monitor`) rather than adding direct side channels.
- Keep extracting shared runtime defaults from remaining large runtime modules
  only when it does not blur ownership or change live/paper behavior.
- Refresh browser/screenshot QA whenever the Workbench visual surface changes
  materially.

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
- **Enabled strategies (2026-06-28):** `momentum_breakout` (re-enabled for paper
  observation, #443), `pattern_pullback`, `williams_r`.
- ATS/SOR support is not active. `config/execution.yaml` and
  `shared/execution/venue_router.py` contain ATS routing primitives and tests,
  but `ats_routing.enabled=false` and the current `stock_order_router` daemon is
  KRX-only. Treat multi-venue execution as a planned readiness track unless the
  operator explicitly decides to keep KRX-only as v1 policy.
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
| Nextrade/ATS best-execution readiness | ⏳ planned | follow [runbooks/market-structure-policy.md](runbooks/market-structure-policy.md); decide KRX-only v1 vs ATS/SOR track; if SOR, add venue quote ingestion, best-execution audit logs, midpoint/stop-limit policy, schedule guards, and paper simulator calibration |
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
- Decide the stock market-structure policy. If the system remains KRX-only,
  document that explicitly; if it moves toward Nextrade/ATS, update schedule
  config, venue quote ingestion, SOR audit evidence, order-type handling, and
  Workbench venue transparency before enabling routing.
- Add theme leader/fusion evidence review: theme target freshness, active and
  quarantined counts, false-positive examples, per-theme hit quality, and
  rollback thresholds.
- Run the position-recovery drill and the Redis + SQLite E2E smoke; use
  `scripts/ops/ops_readiness_check.py` as the offline checklist before/after cutovers.
- Restart MLflow for experiment tracking.

---

## Futures

### North Star

The **LLM interprets market context** (veto / risk-mode / size / threshold), and
an **indicator + rule strategy (Setup A/C/D) owns entry/exit timing**. Thresholds
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
- **Enabled strategies (2026-06-28):** `setup_a_gap_reversion` (fires live
  signals), `setup_c_event_reaction` (coded but ~0 signals — event scores need
  real production/observation; bounded history is now retained for diagnostics),
  and `setup_d_vwap_reversion` (paper rollout activated 2026-06-26; needs
  paper validation before any live consideration).
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
| Setup D high-vol VWAP reversion paper validation | 🔄 in-progress | `setup_d_vwap_reversion` is enabled in paper only; validate signal count, long/short split, volatility-event attribution, paper PnL, and backtest-vs-paper delta before any promotion |
| Kill-switch sentinel → shared-volume path | ✅ done | default is `/app/data/runtime/kis_kill_switch.tripped`, shared by kill-switch/order-router containers |
| Futures cutover verify/rollback automation script (stock analogue exists) | ✅ done | `scripts/ops/futures_cutover_verify.py` read-only audit/strict gate rejects placeholder evidence; `scripts/ops/futures_evidence_bundle.py` compiles F-9/Phase 5 evidence; env examples expose `FUTURES_ORCHESTRATOR_ENABLED`; rollback helper is dry-run-first |
| HAR-RV log-RV validation (futures side) | 🔄 in-progress | log-RV model target, RV-history serialization, KST regular-session RV, and local file-backed refit/validation CLIs exist; real-data validation/shadow remains open |
| Futures product/session governance | ⏳ planned | reconcile `FUTURES_TRADING_PRODUCT`, tick size, multiplier, expiry/roll, regular 08:45 open, disabled night-session policy, and quote/session limits before changing runtime windows |

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
- Observe Setup D in paper before promotion: accepted/rejected signals, long/short
  balance, stop/target quality, volatility-event concentration, and
  paper-vs-backtest drift.
- Reconcile futures product/session policy against current KRX rules. The repo
  defaults to Mini semantics in several execution guards, while full KOSPI 200
  uses 0.05 tick / KRW 12,500 tick value; do not change live windows until the
  operator decides how to handle 08:45 regular open and disabled 18:00-06:00
  night trading.
- Run `scripts/ops/futures_cutover_verify.py --strict` with Gate 1 evidence and
  written approval before cutover; repo-local sentinel/env checks are wired, so
  the remaining blockers are operator-supplied shadow evidence and approval.
