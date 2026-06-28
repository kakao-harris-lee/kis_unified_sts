# Project Status - KIS Unified Trading Platform

**Last updated**: 2026-06-28

> Phased roadmap (Stock + Futures): [ROADMAP.md](ROADMAP.md) — authoritative.

## Current Runtime

- Frontend/API is consolidated behind Caddy. Paper/local host entrypoint is
  `DASHBOARD_HOST_PORT=5081`, with `dashboard:8001` and
  `strategy-builder-ui:3100` kept internal.
- Stock paper flow uses the decoupled Compose pipeline:
  `stock-ingest` + `stock-pipeline`. The monolithic stock orchestrator is blocked
  after cutover with `STOCK_ORCHESTRATOR_ENABLED=false`.
- Futures primary strategy path is Setup A/C/D with LLM market context and
  explicit indicator/strategy-native exits. Decoupled futures services exist
  behind `futures-ingest`, `futures-pipeline`, and `futures-killswitch` profiles
  and should be cut over only through the F9 runbook.
- Scheduler/producers have been migrated into Compose profiles
  `scheduler` and `producers`.
- Dashboard `/experiments` now supports stock strategy experiment reports and
  on-demand jobs backed by `shared/backtest/experiment_runner.py`.
- Quant Ops Workbench P0/P1 UI is in place: `/risk`, `/coverage`, `/trades`
  lifecycle timelines, `/builder` promotion Kanban, enriched signal decision
  trace details, and backtest-vs-paper comparison panels are read-only or
  paper-safe. `GET /api/signals/{signal_id}/trace` exposes LLM context, strategy
  inputs, thresholds, risk/orderability detail, lifecycle lineage, scorecard,
  and degraded evidence gaps.
- Quant Ops Workbench P2 Event Context is in place: `/event-context` and
  `/api/event-context/diagnostics` expose Setup C latest eval, event-score
  freshness plus bounded history, news/macro source timelines, and no-signal
  root causes. Workbench UI/UX QA now has committed Vitest smoke coverage plus
  desktop/mobile
  Playwright fallback screenshot evidence for degraded empty-state render paths:
  [testing/quant-ops-workbench-2026-06-25.md](testing/quant-ops-workbench-2026-06-25.md).
  `/signals` trace QA was refreshed on 2026-06-27:
  [testing/quant-ops-workbench-2026-06-27.md](testing/quant-ops-workbench-2026-06-27.md).

## Storage And Runtime Decisions

- Redis DB 1 is the runtime stream/state store.
- SQLite `RuntimeLedger` is the durable runtime ledger.
- Parquet/DuckDB is the historical market-data backend.
- ClickHouse is removed from active runtime, collection, backtest, and compose
  service paths.
- Futures ML/RL/TFT prediction paths have been removed. MLflow remains only as
  optional backtest/optimization experiment tracking.

## Active Strategies

Verified 2026-06-28 against `config/strategies/{stock,futures}/*.yaml`
(`enabled` flag is the single source of truth).

| Asset | Strategy | Mode | Note |
|---|---|---|---|
| Stock | `momentum_breakout`, `pattern_pullback`, `williams_r` | Paper (enabled) | `momentum_breakout` re-enabled for paper observation (#443). Swing exits are signal-driven (three-stage); no blanket EOD liquidation. |
| Stock | `bb_reversion`, `opening_volume_surge`, `volume_accumulation`, `trend_pullback`, `vr_composite`, `technical_consensus`, `trend_continuation_vwap`, `daily_pullback`, `trix_golden`, `llm_adaptive_sizing_example`, `opening_volume_surge_combo_balanced`, `opening_volume_surge_score_1p8`, `trend_pullback_consensus_exit` | Disabled | `enabled: false`. `technical_consensus` disabled after 0% win (2026-06-02); reactivation under review (see ROADMAP). |
| Futures | `setup_a_gap_reversion`, `setup_c_event_reaction`, `setup_d_vwap_reversion` | Paper primary (enabled) | Setup A fires live signals; Setup C coded but ~0 signals (needs real event-score production/observation; bounded history is now retained for diagnostics). Setup D high-vol VWAP reversion is paper-enabled from 2026-06-26 and needs validation before promotion. Uses Setup target exits, LLM context/veto/risk hooks, live-mode guards. |
| Futures | `williams_r_15m`, `bb_reversion_15m`, `macd_ema_crossover_15m`, `momentum_breakout_futures`, `trend_pullback_futures`, `trix_golden_futures` | Disabled | `enabled: false`. Trend strategies collapse in walk-forward; `bb_reversion_15m` disabled (triggered stock BEAR_EXIT, #479). `track_a_exit.yaml` is an exit config, not a strategy. |
| Futures | `llm_directed_indicator` | Deprecated | Not an active path without a separate redefinition gate. |

## Recent Decisions

**2026-06-28** - Roadmap and quant-system gap research refreshed.
Roadmap/status docs now reflect Setup D paper enablement, the enriched Signal
Decision Trace endpoint, PR #547 hardening, and the split gap list for KOSPI 200
futures vs stock trading. Research note:
[investigations/2026-06-28-quant-system-gap-research.md](investigations/2026-06-28-quant-system-gap-research.md).
The main new roadmap decisions are: collect futures F-9/Setup C/Setup D evidence
before cutover/live gates, and explicitly choose KRX-only stock v1 vs a
Nextrade/ATS smart-order-routing readiness track.

**2026-06-27 to 2026-06-28** - Signal Decision Trace and theme/fusion
transparency hardened.
The `/signals` UX and `GET /api/signals/{signal_id}/trace` route now expose
decision evidence across LLM context, strategy inputs, thresholds,
risk/orderability, lifecycle lineage, and scorecard fields. Follow-up hardening
fixed trace lineage/reuse edge cases, moved reusable payload and KST formatting
helpers into shared/frontend libraries, made theme discovery/fusion scoring more
config-driven, and tightened stale snapshot handling.

**2026-06-25** - Roadmap/codebase consistency check.
Static audit refreshed the exact strategy roster and Workbench QA evidence
language. Enabled strategies still match config. Disabled stock variants and
futures `_futures` strategy names are now listed explicitly, and Workbench QA no
longer claims committed browser/screenshot evidence. Audit note:
[investigations/2026-06-25-roadmap-codebase-consistency.md](investigations/2026-06-25-roadmap-codebase-consistency.md).

**2026-06-25** - Multi-agent code-quality cleanup completed.
Implemented the high-priority cleanup plan in
[superpowers/plans/2026-06-25-code-quality-cleanup-multi-agent.md](superpowers/plans/2026-06-25-code-quality-cleanup-multi-agent.md):
shared strategy entry gates, table-driven registry registration, centralized
runtime defaults, centralized dashboard query intervals, Strategy Builder
reducer/YAML serializer extraction, `/trades` page componentization, broker
position verification extraction, and `LLMConfig.from_yaml` helper extraction.
Focused backend and frontend tests were added for each extracted surface. At
that checkpoint, the remaining high-value maintainability work was further
orchestrator decomposition, one broker-verifier delegation guard test, optional
strategy-level cooldown/close guardrail tests, and refreshed Workbench
screenshot/accessibility evidence after the `/trades` refactor was running.

**2026-06-25** - Follow-up code-quality roadmap priorities completed.
The remaining high-priority follow-ups from the Cross-Cutting Code Quality
section are implemented: open-position metric synchronization moved to
`services/trading/metrics_sync.py` while preserving the `position_count`
contract, `_verify_positions_with_broker` now has a delegation guard test,
`momentum_breakout` trend-mode cooldown and `opening_volume_surge` post-close
behavior are covered by strategy-level guardrail tests, and `/trades`
desktop/mobile Playwright screenshots were refreshed after the component/hook
split. The remaining maintainability backlog is further decomposition of the
orchestrator initialization, recovery, and execution setup regions plus careful
runtime-default extraction only where ownership and paper/live behavior remain
unchanged.

**2026-06-25** - Quant Ops Workbench UI/UX QA evidence captured.
Playwright fallback verification covered `/risk`, `/coverage`, `/trades`,
`/builder`, and `/event-context` at desktop `1440x1100` and mobile `390x844`.
The pass checked route headings, degraded empty states, refresh/tab
interactions, console errors, visible interactive overlap, and retained
screenshots under
[testing/quant-ops-workbench-2026-06-25.md](testing/quant-ops-workbench-2026-06-25.md).

**2026-06-25** - High-priority roadmap implementation slices.
F-9 now has a read-only verifier and dry-run-first rollback helper:
`scripts/ops/futures_cutover_verify.py` and
`scripts/ops/futures_cutover_rollback.sh`; the verifier rejects placeholder Gate
1 evidence, the kill-switch sentinel defaults to the shared
`/app/data/runtime/kis_kill_switch.tripped` path, and paper/live env examples
expose `FUTURES_ORCHESTRATOR_ENABLED` for the Gate 2 double-trade guard. Setup C
now suppresses entries when forecast integration is enabled but event scores are
missing or below the configured minimum, retains bounded event-score history in
Redis, and surfaces that history in Event Context diagnostics. HAR-RV model JSON
preserves RV history, supports log-RV fitting with bias correction, filters daily
RV to the KST regular session by default, and has a local CSV/Parquet refit CLI;
real-data refit/backtest + shadow validation remains open before config cutover.

**2026-06-25** - Parallel readiness automation for remaining gates.
Added offline/read-only gate helpers for the remaining high-priority development
tracks: `scripts/forecasting/validate_har_rv.py` for raw-vs-log HAR-RV reports,
`scripts/ops/setup_c_event_score_observe.py` for Setup C event-score readiness,
`scripts/ops/futures_evidence_bundle.py` for F-9/Phase 5 evidence bundles,
`scripts/ops/stock_strategy_readiness.py` for `technical_consensus` and
`momentum_breakout` evidence review, and
`scripts/ops/ops_readiness_check.py` for common Redis/SQLite, MLflow,
position-recovery, Workbench QA, and Strategy Lab readiness checks. These tools
do not replace real market data, shadow trading days, paper observation, or
operator approval.

**2026-06-22** - Quant Ops Workbench P0/P1 implementation.
Multi-agent lanes implemented the ops summary DTO, signal trace UI, risk and
exposure board, backtest-vs-paper comparator, lifecycle blotter, strategy
promotion Kanban, and universe/data coverage explorer. New read-only or
paper-safe surfaces include `/risk`, `/coverage`, `/trades` lifecycle panels,
and `/builder` promotion evidence. Backend additions include
`/api/trading/risk-exposure`, `/api/trades/lifecycle`, `/api/coverage`, enriched
`/api/signals`, `/api/health/summary`, and experiment paper comparison.

**2026-06-22** - Quant Ops Workbench P2 Event Context diagnostics.
`/api/event-context/diagnostics` and `/event-context` separate Setup C selectivity
from missing event-source causes using `trading:futures:setup_eval`,
`forecast:event:latest`, news/scored/macro streams, scheduled events, and Setup C
config mismatch warnings. The UI is read-only and paper-safe.

**2026-06-22** - Documentation cleanup and UI/UX roadmap update.
Pre-decoupled stock paper guides, historical backtest-review placeholders,
host-crontab registration docs, and obsolete RL/ClickHouse-era plans were
archived or de-indexed. The roadmap now includes a cross-asset Quant Ops
Workbench track with a multi-agent implementation plan:
[plans/2026-06-22-quant-ops-workbench-uiux.md](plans/2026-06-22-quant-ops-workbench-uiux.md).
Current operators should start from [ROADMAP.md](ROADMAP.md), this status page,
and runbooks.

**2026-06-20** - Documentation cleanup (this PR). Superseded RL/paradigm plans
and the synthetic-data stock validation summary were archived with SUPERSEDED
banners and de-indexed; a single authoritative [ROADMAP.md](ROADMAP.md) (Stock +
Futures) was added; `strategies.md` and Phase-5/Strategy-Lab/RegimeGate specs
were corrected for current state (no RL, no ClickHouse, Next.js UI).

**2026-06-17** - Documentation cleanup. `CLAUDE.md` was compacted, `AGENTS.md`
became a thin pointer, completed plan records moved to archive, and plan indexes
were refreshed.

**2026-06-14** - Stock experiment feature implemented. The runner, CLI,
scheduler entry, dashboard API, and `/experiments` UI are in place.

**2026-06-09** - Cron-to-Compose scheduler migration implemented. KIS one-shot
jobs run through the `scheduler` service and market-hours producers run through
the `producers` profile.

**2026-06-06 to 2026-06-08** - Stock and futures decoupled pipeline Compose
wiring and runbooks completed.

**2026-06-03** - ML/RL removal. `sts rl *`, `sts tft *`, `shared/ml/rl`,
`shared/ml/tft`, RL/TFT configs, RL shadow/counterfactual cron, and RL strategy
entry/exit components are removed.

**2026-06-03** - Runtime storage decoupling. Runtime writes default to Redis DB
1 + SQLite WAL, market-data collection/backtest/prewarm uses Parquet/DuckDB, and
default Python dependencies no longer include ClickHouse drivers.

## Open Validation

Full per-asset open list with owners/gates is in [ROADMAP.md](ROADMAP.md). Top items:

- **Stock:** HAR-RV log-RV transition (forecast model stale since 2026-05-31,
  daily refit failing — RV-history serialization and local file-backed log-RV
  refit/validation paths are implemented, but real-data refit/backtest + ~1wk
  shadow are still needed before switching default config from `rv_target: raw`);
  `technical_consensus` reactivation decision (strong long-horizon backtest vs
  recent live loss; use `scripts/ops/stock_strategy_readiness.py` with real
  evidence); `momentum_breakout` redesign (retune still negative);
  non-Workbench Strategy Lab build-out; decide KRX-only stock v1 vs Nextrade/ATS
  SOR readiness before enabling `ats_routing`. See
  [plans/2026-06-02-stock-reopt-har-rv-followups.md](plans/2026-06-02-stock-reopt-har-rv-followups.md).
- **Futures:** F9 decoupled cutover gates (shadow → Gate 2 → operator-gated
  cutover) before replacing the orchestrator path; Phase 5 Gate 1–3 to small
  live; run the F-9 verifier and evidence-bundle compiler with real Gate 1/Phase
  5 evidence and written approval; Setup C activation still needs scored-event
  production/observation even though the runtime min-score gate, bounded
  history, and readiness observer are in place; Setup D needs paper observation
  and paper-vs-backtest drift review; product/session policy needs reconciliation
  for full vs Mini KOSPI 200, tick size, expiry/roll, 08:45 regular open, and
  disabled 18:00-06:00 night trading.
- **Both:** Paper/live E2E smoke with Redis + SQLite only after each cutover;
  position-recovery drill after process restart; MLflow restart
  (`localhost:5000` down); refresh Workbench desktop/mobile screenshot/accessibility
  QA artifacts when those routes change; continue decomposing the orchestrator
  initialization, recovery, and execution setup regions after the
  broker-verification and metrics-sync extractions. Use
  `scripts/ops/ops_readiness_check.py` as the offline checklist; live service
  confirmation remains external.
