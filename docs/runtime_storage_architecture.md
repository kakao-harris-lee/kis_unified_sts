# Runtime Storage Architecture

- 작성일: 2026-06-03
- 상태: ClickHouse 제거 반영 완료
- 관련 계획:
  - [plans/2026-06-03-runtime-storage-decoupling-implementation.md](plans/2026-06-03-runtime-storage-decoupling-implementation.md)
  - [plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md](plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md)

## 요약

ClickHouse는 더 이상 신규 시장데이터 수집, 백테스트, prewarm, runtime ledger, dashboard 조회의 데이터 소스로 사용하지 않는다. 개발/모의투자/실전투자 runtime과 백테스트는 Parquet/DuckDB 파일 및 SQLite RuntimeLedger를 기준으로 동작해야 한다.

목표 구조는 다음과 같다.

| 계층 | 기본 저장소 | 역할 |
|------|-------------|------|
| Runtime event bus | Redis Streams | decision/risk/order/news/scoring 이벤트 전달 |
| Runtime state | Redis DB 1 + TTL | 현재 포지션, kill switch, watchlist, risk state, 최신 context |
| Runtime durable ledger | SQLite WAL | orders, fills, trades, position snapshots, risk events, audit history |
| Backtest/research data lake | Parquet + DuckDB | 백테스트, 장기 시계열 분석, prewarm fixture |

핵심 결정은 OHLCV의 active source of truth를 Parquet 파일로 고정하는 것이다. Redis Streams와 SQLite RuntimeLedger는 그대로 유지한다.

## 배경

이전 구조에서는 과거 OHLCV, 운영 영구 기록, 대시보드/통계 조회가 서버 DB 경로에 섞여 있었다. 현재 구조에서는 KIS historical collection과 backtest/prewarm은 Parquet를 사용하고, 주문/체결/포지션/감사성 runtime 기록은 SQLite RuntimeLedger를 사용한다.

## 요구사항

1. `docker compose`와 repo 파일만으로 dev/test/paper/live 환경을 올릴 수 있어야 한다.
2. 같은 물리 서버에서 dev, paper, live를 동시에 운용할 수 있어야 한다.
3. paper/live runtime은 서버 DB 없이 시작하고 주문/체결/포지션 기록을 보존해야 한다.
4. Redis는 DB 1 정책을 유지하되 환경별 컨테이너/볼륨/네트워크를 분리한다.
5. 백테스트와 운영 분석은 서버 DB 없이도 Parquet/DuckDB 데이터셋으로 실행 가능해야 한다.
6. 신규 수집과 백필은 Parquet 파일에 직접 기록한다.
7. 실전투자 감사 가능성을 위해 runtime ledger는 append-friendly하고 복구 가능해야 한다.

## 비목표

- Redis Streams 대체.
- 신규 KIS historical collection을 서버 DB로 저장.
- Prometheus, dashboard UI 재설계.
- ML/RL runtime 또는 training stack 개선. ML/RL 제거는 별도 plan에서 추적한다.
- 실전 주문 경로를 한 번에 대규모 변경.

## 환경 모델

환경은 `COMPOSE_PROJECT_NAME`과 별도 `.env` 파일로 분리한다.

| 환경 | 예시 project name | 목적 | 기본 storage |
|------|-------------------|------|--------------|
| dev | `kis_dev` | 개발, 로컬 수동 테스트 | Redis + SQLite + sample Parquet |
| test | `kis_test` | pytest/integration | temp Redis 또는 fakeredis + temp SQLite |
| paper | `kis_paper` | 모의투자 | Redis AOF + `data/runtime/paper/runtime.db` |
| live | `kis_live` | 실전투자 | Redis AOF + `data/runtime/live/runtime.db` |
| research | `kis_research` | 백테스트/대용량 분석 | Parquet/DuckDB |

Redis DB 번호로 환경을 나누는 방식은 피한다. 이 repo의 운영 규칙은 Redis DB 1을 표준으로 두고 있으므로, 환경별로 Redis 컨테이너와 volume 자체를 분리하는 편이 안전하다.

## Target Architecture

```
KIS websocket / REST
        |
        v
Runtime services
        |
        +--> Redis Streams / Redis state
        |
        +--> RuntimeLedger interface
        |       +--> SQLiteLedger (default dev/paper/live)
        |       +--> NullLedger (tests that do not verify persistence)
        |
        +--> MarketDataStore interface
                +--> Redis candle cache
                +--> Parquet/DuckDB historical store
                +--> KIS REST fallback
```

Runtime services must not import server DB drivers for market data or ledger persistence. Application code should request a `RuntimeLedger` or `MarketDataStore` from a factory configured by YAML/env.

## Storage Interfaces

### RuntimeLedger

Responsible for durable operational records.

Minimum operations:

- `record_order(order)`
- `record_fill(fill)`
- `record_trade(trade)`
- `record_position_snapshot(snapshot)`
- `record_risk_event(event)`
- `record_signal_decision(decision)`
- `load_open_positions(asset_class)`
- `query_trades(filters)`
- `flush()`

Default backend: SQLite WAL.

### MarketDataStore

Responsible for historical OHLCV and derived data used by prewarm, backtest, and operational analysis.

Minimum operations:

- `get_minute_bars(symbol, start, end, limit)`
- `get_daily_bars(symbol, start, end, limit)`
- `append_minute_bars(rows)`
- `append_daily_bars(rows)`
- `dataset_manifest()`

Default dev/research backend: Parquet + DuckDB.

### AuditLogStore

Responsible for append-only operational audit events that are not necessarily trades.

Examples:

- kill switch changes
- live-mode suspension changes
- RegimeGate decisions
- LLM veto / shadow decision records
- manual dashboard commands

This can be implemented as part of `RuntimeLedger` initially. Separate it only if query volume or schema ownership diverges.

## SQLite Runtime Ledger

SQLite is sufficient for paper/live runtime because this project is single-host and low-write-rate compared with DB OLAP workloads. Use WAL mode.

Recommended file layout:

```
data/
  runtime/
    dev/runtime.db
    paper/runtime.db
    live/runtime.db
  market/
    stock/daily/*.parquet
    stock/minute/*.parquet
    futures/minute/*.parquet
```

Recommended SQLite settings:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;
```

Core tables:

| Table | Purpose |
|-------|---------|
| `orders` | submitted orders and router decisions |
| `fills` | broker/mock fills |
| `trades` | closed trade summary |
| `position_snapshots` | open/closed position state snapshots |
| `risk_events` | risk limit changes, blocks, manual actions |
| `signal_decisions` | generated/filtered/vetoed signal history |
| `market_context_history` | LLM market context snapshots for replay |
| `ledger_metadata` | schema version, environment, boot id |

Runtime recovery order:

1. Broker/KIS account state is source of truth for live holdings.
2. Redis state restores fast in-process runtime context.
3. SQLite ledger fills audit gaps and recovers last known metadata.

## Parquet + DuckDB Research Store

Parquet gives portable, file-based historical datasets. DuckDB gives SQL over those files without running a server. This matches the requirement that files plus compose are enough to move between servers.

Recommended partitioning:

```
data/market/stock/minute/code=005930/year=2026/month=06/part.parquet
data/market/stock/daily/code=005930/year=2026/part.parquet
data/market/futures/minute/code=101S6000/year=2026/month=06/part.parquet
```

Recommended metadata:

```
data/market/manifest.yaml
```

Manifest should include:

- dataset version
- source
- asset class
- symbol/code mapping
- timezone
- row count
- min/max timestamp
- quality flags
- generation command

Backtest and research configs should support:

```yaml
data:
  source: parquet
  root: data/market
```

Server DB configs are not valid for new backtest or prewarm market-data sources.

## Runtime DB Dependency Policy

Runtime-facing code must not import ClickHouse drivers or legacy client wrappers directly. The compatibility modules under `shared/db/` remain only to raise an explicit removal error for stale call sites.

Runtime-facing roots covered by the policy guard:

- `services/`
- `core/`
- `cli/`
- `shared/strategy/gates/`

The guard test is `tests/unit/storage/test_clickhouse_policy.py`. It fails if
those roots import `clickhouse_driver` or
`shared.db.client.ClickHouseClient` / `AsyncClickHouseClient` /
`get_clickhouse_client` directly.

## Compose Strategy

Use compose profiles.

- Base compose: app, dashboard, forecasting, strategy-builder UI, Redis, Prometheus, stream exporter.
- Trading profile: optional `trader` daemon service that runs `sts trade start` from compose.
- Runtime storage: SQLite file volume mounted into app/dashboard/forecasting.
- `.env.dev`, `.env.paper.example`, `.env.live.example` carry `COMPOSE_PROJECT_NAME`, unique host ports, Redis DB 1, and runtime SQLite paths.

Example:

```bash
docker compose --env-file .env.dev up -d

cp .env.paper.example .env.paper
docker compose --env-file .env.paper up -d

cp .env.live.example .env.live
docker compose --env-file .env.live up -d

docker compose --env-file .env.paper --profile trading up -d trader

TRADING_LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING \
  docker compose --env-file .env.live --profile trading up -d trader

docker compose --env-file .env.dev --profile research up -d mlflow
```

The base compose should not require any ClickHouse host or port.
The `trader` profile is excluded from the base service set, so paper/live dashboards can run without starting the trading loop. Live trader startup also requires both `KIS_REAL_TRADING=true` and `TRADING_LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING`.

## Configuration

Add storage config under a dedicated file, for example `config/storage.yaml`.

```yaml
runtime_storage:
  backend: sqlite
  sqlite:
    path: data/runtime/${ENVIRONMENT}/runtime.db
    wal: true
market_data:
  source: parquet
  parquet:
    root: data/market

dashboard:
  trade_stats_source: runtime_ledger
```

Do not use database env vars as implicit feature flags. Storage behavior is controlled by `config/storage.yaml` and the explicit `RUNTIME_STORAGE_*` / `MARKET_DATA_*` env vars.

## Current Implementation Notes

`feat/runtime-storage-ledger` implements the first runtime storage slice:

- `shared.storage.RuntimeLedger` + `SQLiteRuntimeLedger` for orders/fills/trades/position snapshots/risk events/signal decisions/market context history.
- `PositionTracker` can use `runtime_ledger_backend=sqlite|null`; orchestrator passes `config/storage.yaml` defaults.
- dashboard trades/stats/health PnL read SQLite RuntimeLedger and Redis state.
- news/scoring/forecasting/order fill writers publish to Redis and/or RuntimeLedger; server DB archive writes are disabled.
- `shared.storage.MarketDataStore` + `ParquetMarketDataStore` provide the active market-data abstraction.
- `sts data validate-parquet` validates the dataset root.
- `sts backfill` and `sts stock-backfill` accept only `--sink parquet`. They write KIS historical candles directly to `ParquetMarketDataStore` with code/day replace-write semantics and track resume/status in `data/market/_metadata/backfill_state.sqlite3`.
- `sts backtest run --symbol` and strategy backtest scripts load from Parquet market data. `MARKET_DATA_SOURCE=clickhouse` is invalid.
- `docker-compose.yml` injects Redis DB 1 and storage env into runtime services and mounts `./data/runtime:/app/data/runtime`. MLflow is optional experiment tracking for backtests, not an ML/RL runtime requirement.
- `docker-compose.yml` includes a `profiles: ["trading"]` `trader` service for compose-managed paper/live trading loops. It uses the same runtime storage mounts and requires an explicit live confirmation token before non-interactive live mode.
- `.env.dev`, `.env.paper.example`, `.env.live.example`, and `.env.production.example` separate dev/paper/live by project name, host ports, Redis volume, and SQLite ledger path rather than Redis DB number.
- Runtime-facing code has no active ClickHouse client construction; a unit policy guard prevents regressions.

## Migration Principles

1. Runtime storage defaults to SQLite in dev/paper/live.
2. New KIS backfill writes to Parquet only.
3. Tests that touch live Redis stay behind `KIS_RUN_LIVE_INFRA_TESTS=1`.

## Acceptance Criteria

Runtime is decoupled when all of the following are true.

- `docker compose up -d` can start dev/paper runtime without ClickHouse installed.
- `sts trade start --asset stock --paper` and futures paper startup can run with Redis + SQLite only.
- closed trades and open position snapshots survive process restart through SQLite.
- dashboard positions/trades/stats are usable with Redis + SQLite only.
- backtest/research commands run against Parquet/DuckDB data without ClickHouse. ML/RL commands are decommissioned under the ML/RL removal plan.
- market-data collection commands reject ClickHouse sink selection.
- pytest default run does not connect to Redis/ClickHouse live infra.

## Risks

| Risk | Mitigation |
|------|------------|
| Ledger schema drift | versioned migrations and schema tests |
| SQLite write contention | single writer queue, WAL, busy timeout |
| Loss of legacy server DB analytics during transition | regenerate required datasets as Parquet and query through DuckDB |
| Paper/live confusion | separate `.env`, compose project names, runtime DB paths |
| Incomplete recovery semantics | broker-first recovery tests and restart drills |

## Decision

Adopt Redis Streams + Redis state + SQLite runtime ledger as the default runtime stack. Adopt Parquet/DuckDB as the active historical market-data backend for collection, prewarm, backtesting, and research. Do not add new ClickHouse-backed runtime, collection, or backtest paths.
