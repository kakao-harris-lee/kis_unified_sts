# Runtime Storage Architecture

- 작성일: 2026-06-03
- 상태: 설계 결정 초안
- 관련 계획: [plans/2026-06-03-runtime-storage-decoupling-implementation.md](plans/2026-06-03-runtime-storage-decoupling-implementation.md)

## 요약

ClickHouse는 백테스트, ML 학습, 장기 시계열 분석에는 유용하지만 개발/모의투자/실전투자 runtime의 필수 인프라로 두기에는 과하다. 현재 `docker-compose.yml`은 Redis만 컨테이너로 띄우고 ClickHouse는 `host.docker.internal`의 외부 설치를 기대한다. 그 결과 프로젝트가 ClickHouse 설치 서버에 묶이고, 개발 서버 이동과 paper/live 환경 분리가 어려워진다.

목표 구조는 다음과 같다.

| 계층 | 기본 저장소 | 역할 |
|------|-------------|------|
| Runtime event bus | Redis Streams | decision/risk/order/news/scoring 이벤트 전달 |
| Runtime state | Redis DB 1 + TTL | 현재 포지션, kill switch, watchlist, risk state, 최신 context |
| Runtime durable ledger | SQLite WAL | orders, fills, trades, position snapshots, risk events, audit history |
| Research data lake | Parquet + DuckDB | 백테스트, ML 학습, 서버 없는 로컬 분석 |
| Optional analytics DB | ClickHouse | 대용량 중앙 분석, 장기 shared research, optional mirror |

핵심 결정은 ClickHouse를 "runtime prerequisite"에서 "optional analytics/research backend"로 내리는 것이다. Redis Streams는 그대로 유지한다.

## 배경

현재 ClickHouse 사용은 세 용도로 섞여 있다.

| 용도 | 예시 | 필수성 |
|------|------|--------|
| 과거 OHLCV 소스 | backtest, RL/TFT 학습, prewarm | research에는 중요, runtime에는 fallback 가능 |
| 운영 영구 기록 | `swing_positions`, `stock_trades`, `rl_trades`, `llm_market_context` | 영구성은 필요하지만 ClickHouse일 필요는 없음 |
| 대시보드/통계 조회 | 오늘 PnL, trade stats, health metrics | optional degrade 가능 |

이미 일부 hot path는 ClickHouse 장애에 내성이 있다. 예를 들어 orchestrator prewarm은 Redis candle cache -> ClickHouse -> KIS REST 순서로 동작하고 ClickHouse 실패 시 빈 리스트를 반환한다. 반면 `PositionTracker`, news/scoring/forecasting, dashboard routes 일부는 ClickHouse client를 직접 만들기 때문에 환경에 따라 runtime이 외부 DB 설치에 묶인다.

## 요구사항

1. `docker compose`와 repo 파일만으로 dev/test/paper/live 환경을 올릴 수 있어야 한다.
2. 같은 물리 서버에서 dev, paper, live를 동시에 운용할 수 있어야 한다.
3. paper/live runtime은 ClickHouse가 없어도 시작하고 주문/체결/포지션 기록을 보존해야 한다.
4. Redis는 DB 1 정책을 유지하되 환경별 컨테이너/볼륨/네트워크를 분리한다.
5. 백테스트/ML 학습은 서버 DB 없이도 Parquet/DuckDB 데이터셋으로 실행 가능해야 한다.
6. ClickHouse는 필요 시 research profile 또는 async mirror로 사용할 수 있어야 한다.
7. 실전투자 감사 가능성을 위해 runtime ledger는 append-friendly하고 복구 가능해야 한다.

## 비목표

- Redis Streams 대체.
- 모든 historical data를 즉시 ClickHouse 밖으로 migration.
- MLflow, Prometheus, dashboard UI 재설계.
- 실전 주문 경로를 한 번에 대규모 변경.

## 환경 모델

환경은 `COMPOSE_PROJECT_NAME`과 별도 `.env` 파일로 분리한다.

| 환경 | 예시 project name | 목적 | 기본 storage |
|------|-------------------|------|--------------|
| dev | `kis_dev` | 개발, 로컬 수동 테스트 | Redis + SQLite + sample Parquet |
| test | `kis_test` | pytest/integration | temp Redis 또는 fakeredis + temp SQLite |
| paper | `kis_paper` | 모의투자 | Redis AOF + `data/runtime/paper/runtime.db` |
| live | `kis_live` | 실전투자 | Redis AOF + `data/runtime/live/runtime.db` |
| research | `kis_research` | 백테스트/학습/대용량 분석 | Parquet/DuckDB + optional ClickHouse |

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
        |       +--> ClickHouseLedger (optional mirror/research)
        |       +--> NullLedger (tests that do not verify persistence)
        |
        +--> MarketDataStore interface
                +--> Redis candle cache
                +--> Parquet/DuckDB historical store
                +--> ClickHouse historical store (optional)
                +--> KIS REST fallback
```

Runtime services should not import `clickhouse_driver` directly except behind a storage backend implementation. Application code should request a `RuntimeLedger` or `MarketDataStore` from a factory configured by YAML/env.

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

ClickHouse backend is optional. If enabled as mirror, failures must be best-effort and must not block order submission or position tracking.

### MarketDataStore

Responsible for historical OHLCV and derived data used by prewarm, backtest, and ML.

Minimum operations:

- `get_minute_bars(symbol, start, end, limit)`
- `get_daily_bars(symbol, start, end, limit)`
- `append_minute_bars(rows)`
- `append_daily_bars(rows)`
- `dataset_manifest()`

Default dev/research backend: Parquet + DuckDB.

ClickHouse backend remains useful for very large central datasets, but code should choose it explicitly.

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
4. ClickHouse, if configured, is analysis-only and not needed for recovery.

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

Backtest and ML configs should support:

```yaml
data:
  source: parquet
  root: data/market
```

ClickHouse configs can remain:

```yaml
data:
  source: clickhouse
  database: kospi
```

## ClickHouse Role After Decoupling

ClickHouse remains valuable when one of these is true:

- multiple machines need a shared research database
- datasets are too large for comfortable local Parquet operations
- long-running analytic dashboards need server-side aggregation
- historical ingestion/backfill is centralized

It should not be required for:

- starting paper/live trading
- preserving orders/fills/trades
- restoring open positions
- running normal local unit/integration tests
- serving the primary cockpit when SQLite/Redis has sufficient data

## Compose Strategy

Use compose profiles.

- Base compose: app, dashboard, strategy-builder UI, Redis, Prometheus, stream exporter.
- Runtime storage: SQLite file volume mounted into app/dashboard.
- Research profile: optional ClickHouse + MLflow + dataset tooling.

Example:

```bash
COMPOSE_PROJECT_NAME=kis_paper docker compose --env-file .env.paper up -d
COMPOSE_PROJECT_NAME=kis_live docker compose --env-file .env.live up -d
COMPOSE_PROJECT_NAME=kis_research docker compose --profile research up -d clickhouse
```

The base compose should not require `CLICKHOUSE_HOST` to be reachable.

## Configuration

Add storage config under a dedicated file, for example `config/storage.yaml`.

```yaml
runtime_storage:
  backend: sqlite
  sqlite:
    path: data/runtime/${ENVIRONMENT}/runtime.db
    wal: true
  clickhouse_mirror:
    enabled: false
    database: ${CLICKHOUSE_STOCK_DATABASE:market}

market_data:
  source: parquet
  parquet:
    root: data/market
  clickhouse:
    enabled: false
    stock_database: market
    futures_database: kospi

dashboard:
  trade_stats_source: runtime_ledger
```

Avoid using ClickHouse env vars as implicit feature flags. Use explicit `enabled` flags.

## Current Implementation Notes

`feat/runtime-storage-ledger` implements the first runtime storage slice:

- `shared.storage.RuntimeLedger` + `SQLiteRuntimeLedger` for orders/fills/trades/position snapshots/risk events/signal decisions/market context history.
- `PositionTracker` can use `runtime_ledger_backend=sqlite|clickhouse|null`; orchestrator passes `config/storage.yaml` defaults.
- dashboard trades/stats/health PnL prefer SQLite RuntimeLedger and degrade without ClickHouse.
- news/scoring/forecasting/order fill writers only instantiate ClickHouse clients when `runtime_storage.clickhouse_mirror.enabled=true`.
- `shared.storage.MarketDataStore` + `ParquetMarketDataStore` + `ClickHouseMarketDataStore` provide the initial Phase 4 market-data abstraction.
- `sts data export-clickhouse` exports standard OHLCV rows into the Parquet layout, and `sts data validate-parquet` validates the dataset root.
- `sts backtest run --symbol` uses `config/storage.yaml::market_data.source`, so `market_data.source=parquet` can run without ClickHouse for symbol-based backtests.

## Migration Principles

1. Preserve current ClickHouse schema and paths until replacement backends are verified.
2. Introduce interfaces first, then move call sites behind the interfaces.
3. Default new runtime storage to SQLite in dev/paper, not ClickHouse.
4. Make ClickHouse mirror best-effort. It may log warnings, but it must not change live decision behavior.
5. Keep data export/import commands so ClickHouse datasets can be converted to Parquet.
6. Tests that touch live Redis/ClickHouse stay behind `KIS_RUN_LIVE_INFRA_TESTS=1`.

## Acceptance Criteria

Runtime is decoupled when all of the following are true.

- `docker compose up -d` can start dev/paper runtime without ClickHouse installed.
- `sts trade start --asset stock --paper` and futures paper startup can run with Redis + SQLite only.
- closed trades and open position snapshots survive process restart through SQLite.
- dashboard positions/trades/stats are usable with Redis + SQLite only.
- backtest/ML commands can run against Parquet/DuckDB data without ClickHouse.
- ClickHouse profile can still be enabled for research and mirror writes.
- pytest default run does not connect to Redis/ClickHouse live infra.

## Risks

| Risk | Mitigation |
|------|------------|
| Ledger schema drift | versioned migrations and schema tests |
| SQLite write contention | single writer queue, WAL, busy timeout |
| Loss of ClickHouse analytics during transition | mirror mode and export/import commands |
| Paper/live confusion | separate `.env`, compose project names, runtime DB paths |
| Incomplete recovery semantics | broker-first recovery tests and restart drills |

## Decision

Adopt Redis Streams + Redis state + SQLite runtime ledger as the default runtime stack. Adopt Parquet/DuckDB as the default serverless research data backend. Keep ClickHouse as an optional research profile and best-effort analytics mirror, not as a mandatory runtime dependency.
