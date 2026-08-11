# CLAUDE.md - KIS Unified STS Operational Guide

This file is the compact operational source of truth for coding agents in this
repo. Keep historical rationale in `docs/plans/` or `docs/superpowers/`; keep
this file focused on current runtime rules.

If the deploy-host memory file exists at
`/home/deploy/.claude/projects/-home-deploy-project-kis-unified-sts/memory/MEMORY.md`,
read it as supplemental operational memory. Local checkouts may not have it.

## Core Objective

Optimize trading entry and exit timing through a configuration-driven loop:

```text
strategy config -> backtest -> tracking/optimization -> paper/live validation -> feedback
```

## Non-Negotiable Rules

- Configuration-driven only: thresholds, symbols, risk values, ports, Redis DBs,
  schedules, and feature gates belong in YAML/env/config files, not hardcoded
  branches.
- DRY: shared behavior belongs in `shared/`; avoid duplicating logic in
  per-asset service code.
- Redis: use DB 1 for this project (`redis://localhost:6379/1` unless an env file
  intentionally overrides it). New Redis keys need TTLs; default operational TTL
  is 24h, accumulation snapshots use 48h.
- Timezone: trading/session logic and cron schedules are KST-native. Convert
  timestamps to KST before comparing against Korean market hours.
- Secrets: never commit real credentials, `.kis_token_*`, or filled `.env` files.
  Reference secrets through env vars and `${VAR}` in YAML.
- Stock swing exits are signal-driven. Do not add blanket EOD liquidation.
- Futures must preserve long/short symmetry. Entry/exit direction follows
  `signal_direction`.
- The real futures account is never funded with margin (operator directive): dev-stage mis-orders plus fast-compounding futures losses make real margin unacceptable. Never propose, script, or gate work on depositing margin. Real-money futures order paths — the P-R5 stage-2 probe and anything that emits real futures orders — are permanently blocked by policy; a zero-deposit preflight ABORT is a terminal verdict, not "pending funding". GET-only real reads are fine; measurements needing a real fill use the mock-derived bound.

## Current Runtime Architecture

- `shared/`: reusable strategy, execution, indicators, streaming, storage,
  forecasting, risk, models, and config logic.
- `services/`: runtime processes.
  - `services/trading/`: monolithic orchestrator, still used for futures paper/live
    unless a decoupled futures cutover is explicitly performed.
  - `services/stock_strategy`, `stock_risk_filter`, `stock_order_router`,
    `stock_exit`, `stock_monitor`: decoupled stock M4/M5 pipeline.
  - `services/market_ingest`, `decision_engine`, `risk_filter`, `order_router`,
    `futures_monitor`, `kill_switch`: decoupled futures pipeline services.
  - `services/dashboard`: the single FastAPI API/metrics app behind Caddy.
- `strategy-builder-ui/`: the only frontend. It serves Cockpit, positions,
  signals, trades, experiments, strategy builder, and executor pages.
- `config/`: YAML strategy/risk/execution/storage/infra config.
- `cli/main.py`: `sts` command entrypoint.

## Web/API Surface

- Caddy is the only host-published web entry. Default host port is
  `DASHBOARD_HOST_PORT=5081`; local/operator env files may override it. Caddy
  still listens on container/internal `:5080`.
- Internal Docker ports stay private: `dashboard:8001` and
  `strategy-builder-ui:3100`.
- Do not resurrect the old `services/api` REST gateway or host `:8000` route.
  New API routes go under `services/dashboard`.
- Host port 3000 belongs to another local project and is not used here.

## Trading Runtime Rules

### Stock

- Standard stock paper flow is the decoupled Compose pipeline:
  `stock-ingest` + `stock-pipeline`.
- After stock cutover, block the monolithic stock orchestrator with
  `STOCK_ORCHESTRATOR_ENABLED=false`.
- Rollback path: restore `STOCK_ORCHESTRATOR_ENABLED=true` and follow
  `docs/runbooks/stock-pipeline-cutover-m5d.md`.
- Active stock behavior is screener/universe driven plus configured strategies
  such as `bb_reversion`, `opening_volume_surge`, `volume_accumulation`, and
  newer registry strategies as enabled in YAML.
- Three-stage exit is stock-only unless a future design explicitly generalizes it.

### Futures

- Current primary futures strategy path is Setup A/C:
  `setup_a_gap_reversion` and `setup_c_event_reaction`.
- Futures ML/RL/TFT runtime paths are removed. Do not reintroduce `sts rl *`,
  `sts tft *`, `shared/ml/rl`, `shared/ml/tft`, `RLMPPOEntry`, `RLMPPOExit`, or
  RL/TFT config profiles.
- Futures strategy expansion should use LLM market context plus explicit
  indicator/strategy-native rules such as Williams %R, RSI, MACD, ATR, momentum
  decay, or Setup target exits.
- Live futures is guarded by `config/futures_live.yaml::enabled` plus Redis flag
  `futures:live:suspended`. See `shared/execution/live_mode_guard.py`.
- Decoupled futures services are available through Compose profiles
  `futures-ingest`, `futures-pipeline`, and `futures-killswitch`; perform cutover
  only via `docs/runbooks/futures-pipeline-cutover-f9.md`.
- Real futures account is never funded — see Non-Negotiable Rules. Real-money order probes (P-R5 stage 2) are policy-blocked; paper stays VirtualBroker (real orders 0).

## Storage And Data

- Runtime ledger: SQLite WAL via `shared/storage/runtime_ledger.py`.
- Runtime streams/state: Redis DB 1.
- Historical market data: Parquet/DuckDB through
  `shared/storage/market_data_store.py`.
- ClickHouse is not an active runtime, collection, backtest, or compose
  dependency. Do not add new direct ClickHouse usage.
- Backtests must avoid look-ahead bias. Use `LookaheadGuard` and keep indicator
  inputs bounded by the current context timestamp.

## Strategy Implementation Pattern

- Strategy components register through `shared/strategy/registry.py`.
- Entry generators, exit generators, and position sizers are composed through
  `TradingStrategy`; keep asset-specific code thin.
- New strategy work should include:
  1. YAML config under `config/strategies/{stock,futures}/`.
  2. Shared implementation under `shared/strategy/...`.
  3. Registry wiring and focused unit tests.
  4. Backtest or paper validation artifacts when behavior changes materially.

## Development Commands

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov=shared --cov=services
ruff check .
black --check .
mypy shared/ --ignore-missing-imports --no-error-summary
docker compose up -d
sts --help
```

Frontend:

```bash
cd strategy-builder-ui
npm run dev
npm run build
npm run lint
```

## Harness: Trading Platform Agent Team

**Goal:** Route platform work to specialist agents, and keep adjudication (code and
plan review) in an independent model lane.

**Triggers:**

- Platform work (strategy, ops, frontend, DevX, data, execution) → use the
  `trading-harness` skill.
- Any review, merge-gate, blocking verdict, or plan critique → use the `codex-gate`
  skill. Codex is the reviewer of record; Claude agents produce evidence, not
  verdicts.
- Plan *authoring* is unchanged and stays on the existing Claude path. Only plan
  *adjudication* moved to Codex.
- Simple questions can be answered directly without the harness.

**Adjudication override:** A Codex verdict never overrides the Non-Negotiable Rules
above. Reject any finding that would violate them and record the reason.

Agent roster, skill list, directory layout, and execution detail live under
`.claude/` — not here.

### Harness Change Log

| Date | Change | Scope | Reason |
| --- | --- | --- | --- |
| 2026-03-12 | Initial harness setup (commit `531ec227`) | all | - |
| 2026-08-11 | Adjudication moved to Codex — added `codex-reviewer` / `codex-plan-reviewer` / `codex-gate`; demoted `code-reviewer` and `review-synthesizer` to fallback-only; replaced the `code-audit` fan-in | `agents/`, `skills/` | Prevent self-approval and secure cross-model independent adjudication |

## Documentation Map

- Project snapshot: `docs/PROJECT_STATUS.md`
- Documentation index: `docs/INDEX.md`
- Plan index: `docs/plans/INDEX.md`
- Superpowers plan archive/index: `docs/superpowers/plans/INDEX.md`
- Port policy: `docs/ports.md`
- Runtime storage: `docs/runtime_storage_architecture.md`
- Stock cutover: `docs/runbooks/stock-pipeline-cutover-m5d.md`
- Futures cutover: `docs/runbooks/futures-pipeline-cutover-f9.md`
- Paper/live source separation: `docs/runbooks/paper-live-code-separation.md`
