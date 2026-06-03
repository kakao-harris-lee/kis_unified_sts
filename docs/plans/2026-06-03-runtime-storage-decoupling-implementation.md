# Runtime Storage Decoupling Implementation Plan

- 작성일: 2026-06-03
- 상태: Active proposal
- 설계 문서: [../runtime_storage_architecture.md](../runtime_storage_architecture.md)

## 목표

ClickHouse 설치 여부와 무관하게 개발, 테스트, 모의투자, 실전투자 runtime을 실행할 수 있도록 storage 의존을 분리한다.

최종 목표:

- Redis Streams는 유지한다.
- Redis DB 1은 runtime state와 streams에 계속 사용한다.
- paper/live 영구 ledger는 SQLite WAL을 기본으로 사용한다.
- 백테스트/ML historical data는 Parquet + DuckDB를 기본으로 지원한다.
- ClickHouse는 optional research profile 또는 best-effort mirror로만 사용한다.

## 현재 문제

현재 코드에는 ClickHouse 의존이 직접 흩어져 있다.

| 영역 | 현재 의존 |
|------|-----------|
| `PositionTracker` | open positions, closed trades를 ClickHouse `swing_positions`, `stock_trades`, `rl_trades`에 저장/복구 |
| `TradingOrchestrator` | prewarm candles, shadow logger flush, closed-position persistence |
| Dashboard routes | trade stats, today PnL, health/metrics 조회 |
| News/scoring/forecasting | Redis stream fan-out과 동시에 ClickHouse batch write |
| Backtest/ML CLI | ClickHouse를 historical data source로 가정하는 경로 다수 |
| Compose | Redis는 포함하지만 ClickHouse는 외부 host 설치를 기대 |

이 때문에 ClickHouse가 없는 서버에서는 runtime 일부가 degraded 또는 실패하고, paper/live 환경 이동성이 낮다.

## 구현 원칙

1. 먼저 추상화 계층을 만든다. call site를 한 번에 바꾸지 않는다.
2. runtime write path는 SQLite를 기본값으로 한다.
3. ClickHouse mirror 실패는 live decision/order path에 영향을 주지 않는다.
4. 환경 분리는 Redis DB 번호가 아니라 compose project/volume/env 파일로 한다.
5. ClickHouse historical data는 Parquet export를 통해 점진적으로 이관한다.
6. live infra 테스트는 계속 `KIS_RUN_LIVE_INFRA_TESTS=1` opt-in 뒤에 둔다.

## Phase 0 — Inventory and Switches

상태: 준비

작업:

- `rg` 기반으로 ClickHouse direct imports/calls inventory 작성.
- 각 call site를 아래 분류로 태깅한다.
  - runtime critical
  - runtime best-effort
  - dashboard read
  - research/backtest/ML
  - maintenance/script only
- `config/storage.yaml` 추가.
- `RuntimeStorageConfig`, `MarketDataStorageConfig` 추가.
- `.env.example`에 runtime storage env var 추가.

초기 설정 예:

```yaml
runtime_storage:
  backend: sqlite
  sqlite:
    path: data/runtime/${ENVIRONMENT}/runtime.db
    wal: true
  clickhouse_mirror:
    enabled: false

market_data:
  source: parquet
  parquet:
    root: data/market
  clickhouse:
    enabled: false
```

검증:

- config unit tests.
- ClickHouse env var가 없어도 config load가 통과.

## Phase 1 — SQLite Runtime Ledger

상태: 구현 예정

작업:

- `shared/storage/runtime_ledger.py` 생성.
- `RuntimeLedger` protocol 정의.
- `SQLiteRuntimeLedger` 구현.
- migration runner 추가.
- table schema 추가.

초기 테이블:

- `orders`
- `fills`
- `trades`
- `position_snapshots`
- `risk_events`
- `signal_decisions`
- `market_context_history`
- `ledger_metadata`

구현 세부:

- SQLite `journal_mode=WAL`.
- write는 가능하면 단일 async queue 또는 `asyncio.to_thread` wrapper로 직렬화.
- `busy_timeout=5000`.
- inserts는 idempotency key를 둔다.
- closed trade id는 기존 `Position.id` 또는 fill/order id와 연결한다.

검증:

- temp dir 기반 unit tests.
- restart simulation: write -> close client -> reopen -> load open positions.
- concurrent write smoke test.
- malformed DB path handling.

완료 기준:

- SQLite만으로 orders/fills/trades/position snapshots가 저장된다.
- ClickHouse 미설치 환경에서 ledger unit tests가 통과한다.

## Phase 2 — PositionTracker Decoupling

상태: 구현 예정

작업:

- `PositionTrackerConfig`에 `runtime_ledger_backend` 또는 ledger injection 추가.
- `save_to_db`, `save_closed_to_db`, `load_from_db`를 `RuntimeLedger` 호출로 교체.
- 기존 ClickHouse 구현은 `ClickHouseRuntimeLedger` 또는 `ClickHouseMirrorLedger`로 이동.
- open position recovery 순서 정리.

권장 recovery 순서:

1. broker/KIS account state
2. Redis runtime state
3. SQLite `position_snapshots`
4. ClickHouse mirror, enabled일 때만

검증:

- 기존 `PositionTracker` unit tests를 SQLite backend로 확장.
- ClickHouse backend tests는 mocked client 또는 live_infra opt-in으로 유지.
- paper restart integration test에서 ClickHouse 없이 open positions 복구.

완료 기준:

- `PositionTracker`가 ClickHouse client를 직접 import하지 않는다.
- ClickHouse 없이 paper position tracking이 동작한다.

## Phase 3 — Dashboard and Runtime Writers

상태: 구현 예정

작업:

- dashboard trades/stat routes가 `RuntimeLedger`를 우선 조회하도록 변경.
- 오늘 PnL 계산을 SQLite trades 기반으로 제공.
- ClickHouse stats는 optional analytics endpoint로 이동.
- `llm_context_publisher`의 ClickHouse history append를 `RuntimeLedger.record_market_context`로 교체.
- news/scoring/forecasting ClickHouse batch writer는 optional mirror로 변경.
- ClickHouse insert fail kill-switch condition은 mirror가 enabled일 때만 활성화.

검증:

- dashboard API tests with temp SQLite.
- ClickHouse disabled 상태에서 cockpit/trades/health endpoint가 200 또는 graceful degraded response.
- mirror enabled mocked test.

완료 기준:

- dashboard 주요 화면은 ClickHouse 없이 표시된다.
- live/paper signal/order flow에서 ClickHouse import가 필요하지 않다.

## Phase 4 — Parquet/DuckDB MarketDataStore

상태: 구현 예정

작업:

- `shared/storage/market_data_store.py` 생성.
- `MarketDataStore` protocol 정의.
- `ParquetMarketDataStore` 구현.
- DuckDB query adapter 추가.
- ClickHouse historical adapter는 기존 쿼리를 backend로 이동.
- KIS REST fallback은 runtime prewarm에서 유지.
- export command 추가.

명령 예:

```bash
sts data export-clickhouse \
  --asset futures \
  --database kospi \
  --table kospi200f_1m \
  --out data/market/futures/minute

sts data validate-parquet --root data/market
```

검증:

- sample parquet fixture tests.
- backtest loader parity test: ClickHouse sample vs Parquet sample.
- manifest validation.

완료 기준:

- 주요 backtest command가 `data.source=parquet`으로 실행된다.
- ML training loader가 Parquet/DuckDB source를 지원한다.

## Phase 5 — Compose Profiles and Environment Separation

상태: 구현 예정

작업:

- base `docker-compose.yml`에서 ClickHouse env가 runtime 필수처럼 보이는 부분 정리.
- `docker-compose.research.yml` 또는 `profiles: ["research"]`로 ClickHouse 서비스 추가.
- `data/runtime:/app/data/runtime` volume 추가.
- `.env.dev`, `.env.paper.example`, `.env.live.example` 템플릿 추가.
- `COMPOSE_PROJECT_NAME` 사용법 문서화.

예:

```bash
COMPOSE_PROJECT_NAME=kis_dev docker compose --env-file .env.dev up -d
COMPOSE_PROJECT_NAME=kis_paper docker compose --env-file .env.paper up -d
COMPOSE_PROJECT_NAME=kis_live docker compose --env-file .env.live up -d
COMPOSE_PROJECT_NAME=kis_research docker compose --profile research up -d clickhouse
```

검증:

- ClickHouse 없는 host에서 base compose health.
- paper/live project name 별 Redis volume 분리 확인.
- dashboard 5080 route 확인.

완료 기준:

- ClickHouse 설치가 없는 서버에서 dev/paper compose가 올라온다.
- research profile만 ClickHouse를 띄운다.

## Phase 6 — Cleanup and Policy

상태: 구현 예정

작업:

- direct ClickHouse imports 금지 규칙 문서화.
- `rg "clickhouse_driver|ClickHouseClient|AsyncClickHouseClient"` allowlist 작성.
- lint 또는 test guard 추가.
- old scripts는 research/maintenance category로 정리.
- ClickHouse TLS docs는 optional research/backend docs로 위치 조정.

검증:

- direct import allowlist test.
- default pytest does not connect to live Redis/ClickHouse.
- docs index updated.

완료 기준:

- runtime package에서 direct ClickHouse dependency가 storage backend 외에는 없다.
- 운영 문서가 SQLite runtime ledger와 ClickHouse optional profile을 기준으로 정렬된다.

## Suggested PR Breakdown

| PR | Scope | Risk |
|----|-------|------|
| 1 | storage config + RuntimeLedger protocol + SQLite implementation | low |
| 2 | PositionTracker SQLite backend + tests | medium |
| 3 | dashboard reads from RuntimeLedger | medium |
| 4 | LLM/news/scoring/forecasting mirror optionalization | medium |
| 5 | Parquet/DuckDB MarketDataStore + export commands | medium |
| 6 | compose profiles + env templates | medium |
| 7 | direct ClickHouse import cleanup + policy tests | low |

## Test Matrix

| Test | ClickHouse | Redis | Expected |
|------|------------|-------|----------|
| unit storage | off | off | pass with temp SQLite |
| default pytest | off | off | no live infra connections |
| paper startup | off | on | starts and records to SQLite |
| paper restart | off | on | recovers positions from broker/Redis/SQLite |
| dashboard cockpit | off | on | usable with Redis/SQLite stats |
| backtest parquet | off | off | loads Parquet/DuckDB data |
| research clickhouse | on | optional | historical query/export works |
| mirror failure | broken | on | live path continues, warning logged |

## Rollback Strategy

- Keep ClickHouse backend available during migration.
- Add config flag `runtime_storage.backend=clickhouse` for temporary rollback.
- Do not delete ClickHouse tables or migrations.
- Keep export commands idempotent.
- For live rollout, first run SQLite in mirror mode while ClickHouse remains primary, then switch primary to SQLite after restart drill passes.

## Acceptance Checklist

- [ ] `docker compose up -d` works without ClickHouse installed.
- [ ] `sts trade start --asset stock --paper` works with Redis + SQLite only.
- [ ] futures paper flow works with Redis + SQLite only.
- [ ] dashboard trades/stats do not require ClickHouse.
- [ ] position recovery drill passes after process restart.
- [ ] backtest supports `data.source=parquet`.
- [ ] ML training supports Parquet/DuckDB source or has documented ClickHouse-only exception.
- [ ] ClickHouse profile still supports existing research workflows.
- [ ] default pytest does not touch live Redis/ClickHouse.
