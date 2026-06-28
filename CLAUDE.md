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
  `domains/` or per-asset service code.
- Keep new/changed code small and delegated. If a file, class, or function grows
  enough that one concern is no longer obvious, extract focused helpers instead
  of appending more branches to the same unit.
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

## Storage And Data

- Runtime ledger: SQLite WAL via `shared/storage/runtime_ledger.py`.
- Runtime streams/state: Redis DB 1.
- Historical market data: Parquet/DuckDB through
  `shared/storage/market_data_store.py`.
- ClickHouse is not an active runtime, collection, backtest, or compose
  dependency. Do not add new direct ClickHouse usage.
- Backtests must avoid look-ahead bias. Use `LookaheadGuard` and keep indicator
  inputs bounded by the current context timestamp.

## Code Structure And Pipeline Rules

- New or heavily edited files should usually stay below about 500 lines; new or
  heavily edited functions should usually stay below about 60 lines. Treat these
  as review triggers, not as a mandate to churn historical modules.
- Delegate responsibilities by layer: service daemons orchestrate, while parsing,
  codecs, validation, state reduction, signal conversion, logging/audit helpers,
  and reusable calculations live in focused service-local modules or `shared/`.
- Prefer established local patterns before inventing new abstractions:
  `StreamStage` / Redis consumer groups for stream processors, serializers and
  codecs for stream payloads, registry/table-driven wiring for strategies,
  config loaders/YAML for behavior, and `TradingStatePublisher` for dashboard
  read models.
- Preserve the event-driven architecture. Runtime services should communicate by
  durable events/Redis Streams and consumer groups; avoid direct cross-service
  synchronous calls or hidden shared mutable state for trading decisions.
- Keep stream data pipelines explicit: producers emit bounded payloads with TTLs,
  processors validate/transform/ACK with audit logs, and read-model publishers
  expose operator state. Do not bypass this chain for convenience unless a
  runbook or design doc explicitly approves it.
- When adding a new trading workflow, first look for an existing stream,
  serializer, codec, registry, or state-publisher pattern to extend. New paths
  should be introduced only when the existing pipeline cannot model the contract.

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
pytest tests/ -v --cov=shared --cov=services --cov=domains
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
