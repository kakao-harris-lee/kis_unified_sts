# Runtime Storage Decoupling Implementation Plan

- 작성일: 2026-06-03
- 상태: Implementation in progress — Phase 0-3/5-7 implemented, Phase 4 backtest/research and E2E acceptance remain
- 설계 문서: [../runtime_storage_architecture.md](../runtime_storage_architecture.md)
- 관련 결정: [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md)

## 목표

ClickHouse 설치 여부와 무관하게 개발, 테스트, 모의투자, 실전투자 runtime을 실행할 수 있도록 storage 의존을 분리한다.

최종 목표:

- Redis Streams는 유지한다.
- Redis DB 1은 runtime state와 streams에 계속 사용한다.
- paper/live 영구 ledger는 SQLite WAL을 기본으로 사용한다.
- 백테스트 및 운영 분석 historical data는 Parquet + DuckDB를 기본으로 지원한다.
- ClickHouse는 optional research profile 또는 best-effort mirror로만 사용한다.

## 현재 문제

현재 코드에는 ClickHouse 의존이 직접 흩어져 있다.

| 영역 | 현재 의존 |
|------|-----------|
| `PositionTracker` | open positions, closed trades를 ClickHouse `swing_positions`, `stock_trades`, `rl_trades`에 저장/복구 |
| `TradingOrchestrator` | prewarm candles, shadow logger flush, closed-position persistence |
| Dashboard routes | trade stats, today PnL, health/metrics 조회 |
| News/scoring/forecasting | Redis stream fan-out과 동시에 ClickHouse batch write |
| Backtest/research CLI | ClickHouse를 historical data source로 가정하는 경로 다수 |
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

상태: 구현 완료 (`feat/runtime-storage-ledger`)

작업:

- `rg` 기반으로 ClickHouse direct imports/calls inventory 작성.
- 각 call site를 아래 분류로 태깅한다.
  - runtime critical
  - runtime best-effort
  - dashboard read
  - research/backtest
  - legacy ML/RL removal target
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

상태: 구현 완료 (`feat/runtime-storage-ledger`)

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

상태: 구현 완료 (`feat/runtime-storage-ledger`)

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

상태: 핵심 구현 완료, 잔여 cleanup 있음 (`feat/runtime-storage-ledger`)

남은 항목:

- orchestrator shadow logger / prewarm historical reads는 아직 optional ClickHouse helper 경로가 남아 있다.
  - shadow logger는 ClickHouse init 실패 시 graceful degrade하지만 `runtime_storage.clickhouse_mirror.enabled`로 게이트되지 않는다.
  - prewarm historical reads는 Redis cache → ClickHouse → KIS REST 순서이며 `MarketDataStore`/Parquet source로 아직 분리되지 않았다.

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

상태: 부분 구현 (`feat/runtime-storage-ledger`)

현재 구현:

- `shared/storage/market_data_store.py` 추가.
- `MarketDataStore` protocol, `ParquetMarketDataStore`, `ClickHouseMarketDataStore` adapter 추가.
- `sts data validate-parquet`, `sts data export-clickhouse` 추가.
- `sts backtest run --symbol`이 `config/storage.yaml::market_data.source`를 사용하도록 변경.
- `duckdb` / `pyarrow` 의존성 추가.

남은 항목:

- 주요 backtest/tier runner 전체를 Parquet source로 확장.
- ML/RL training loader 지원은 제거 계획으로 이관. runtime-storage acceptance에서는 더 이상 추적하지 않는다.
- ClickHouse sample vs Parquet sample parity test.
- `manifest.yaml` schema/validation 고도화.

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
- ML/RL training path는 runtime-storage acceptance가 아니라 제거 계획에서 archive/decommission으로 정리된다.

## Phase 5 — Compose Profiles and Environment Separation

상태: 구현 완료 (`feat/runtime-storage-ledger`)

작업:

- base `docker-compose.yml`에서 Redis DB 1, runtime storage, market-data env를 runtime services에 명시.
- `profiles: ["research"]`로 ClickHouse와 MLflow 서비스 분리.
- `./data/runtime:/app/data/runtime` volume을 app/dashboard/forecasting에 추가.
- `.env.dev`, `.env.paper.example`, `.env.live.example` 템플릿 추가.
- `COMPOSE_PROJECT_NAME`, unique host ports, Redis volume 분리 사용법 문서화.

예:

```bash
docker compose --env-file .env.dev up -d

cp .env.paper.example .env.paper
docker compose --env-file .env.paper up -d

cp .env.live.example .env.live
docker compose --env-file .env.live up -d

docker compose --env-file .env.dev --profile research up -d clickhouse mlflow
```

검증:

- `docker compose --env-file .env.dev config --services` excludes ClickHouse/MLflow.
- `docker compose --env-file .env.dev --profile research config --services` includes ClickHouse/MLflow.
- `docker compose --env-file .env.paper.example config` renders `kis_paper`, Redis DB 1, and `data/runtime/paper/runtime.db`.
- `docker compose --env-file .env.live.example config` renders `kis_live`, Redis DB 1, and `data/runtime/live/runtime.db`.
- Runtime `up -d` health smoke remains a deployment validation step to avoid disturbing an existing long-running stack.

완료 기준:

- ClickHouse 설치가 없는 서버에서 dev/paper compose config가 렌더링된다.
- research profile만 ClickHouse와 MLflow를 compose service set에 포함한다.

## Phase 6 — Cleanup and Policy

상태: 구현 완료 (`feat/runtime-storage-ledger`)

작업:

- direct ClickHouse imports 금지 규칙 문서화.
- runtime-facing roots allowlist 작성:
  - covered: `services/`, `core/`, `cli/`, `shared/strategy/gates/`
  - allowed backend locations: `shared/db/*`, `shared/storage/clickhouse_*`, `shared/storage/market_data_store.py`
  - research/maintenance: `scripts/`, `jobs/`, analysis docs
- `tests/unit/storage/test_clickhouse_policy.py` guard 추가.
- runtime services의 ClickHouse client 생성 경로를 `shared.storage.clickhouse_backend` helper로 이동.
- docs index/runtime architecture에 policy 반영.

검증:

- direct import allowlist test: `tests/unit/storage/test_clickhouse_policy.py`.
- default storage config keeps ClickHouse mirror disabled and market-data source `parquet`.
- docs index updated.

완료 기준:

- runtime package에서 direct ClickHouse dependency가 storage backend 외에는 없다.
- 운영 문서가 SQLite runtime ledger와 ClickHouse optional profile을 기준으로 정렬된다.

## Phase 7 — Direct Import Guard PR

상태: 구현 완료 (`feat/runtime-storage-ledger`)

작업:

- `shared/storage/clickhouse_backend.py` 추가.
- `services/trading/orchestrator.py`, dashboard routes, news/scoring/forecasting/order/macro services, `daily_scanner`, `llm_context_publisher`, `core/state_manager`, `cli/main.py`, `shared/strategy/gates/adapter_helper.py`의 direct ClickHouse client construction 제거.
- policy guard가 runtime-facing roots에서 `clickhouse_driver`, `ClickHouseClient`, `AsyncClickHouseClient`, `get_clickhouse_client` direct import를 차단하도록 고정.

검증:

- policy guard unit test.
- affected storage/CLI/orchestrator tests.
- ruff focused check.

## Suggested PR Breakdown

| PR | Scope | Risk | Status |
|----|-------|------|--------|
| 1 | storage config + RuntimeLedger protocol + SQLite implementation | low | implemented |
| 2 | PositionTracker SQLite backend + tests | medium | implemented |
| 3 | dashboard reads from RuntimeLedger | medium | implemented |
| 4 | LLM/news/scoring/forecasting mirror optionalization | medium | implemented |
| 5 | Parquet/DuckDB MarketDataStore + export commands | medium | partial |
| 6 | compose profiles + env templates | medium | implemented |
| 7 | direct ClickHouse import cleanup + policy tests | low | implemented |

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

확인일: 2026-06-03 (PR #402)

검증 근거:

- PR checks: `lint`, `type-check`, `performance`, `test` pass.
- Targeted local tests: runtime ledger / position tracker / dashboard trades+health / market data store / CLI data commands / ClickHouse policy / storage config, 51 passed.
- Compose config smoke:
  - `docker compose --env-file .env.dev config --services` excludes ClickHouse/MLflow.
  - `docker compose --env-file .env.dev --profile research config --services` includes ClickHouse/MLflow.
  - `.env.paper.example` renders `kis_paper`, Redis DB 1, and `data/runtime/paper/runtime.db`.
  - `.env.live.example` renders `kis_live`, Redis DB 1, and `data/runtime/live/runtime.db`.

- [ ] `docker compose up -d` works without ClickHouse installed.
  - 미검증: existing runtime stack 방해를 피하려고 실제 `up -d` smoke는 수행하지 않았다. Compose config render는 통과.
- [x] dev/paper/live compose config renders without ClickHouse service.
- [ ] `sts trade start --asset stock --paper` works with Redis + SQLite only.
  - 미완료/미검증: stock paper E2E smoke가 필요하다.
- [ ] futures paper flow works with Redis + SQLite only.
  - 미완료/미검증: order fill durable write path는 RuntimeLedger로 연결됐지만 futures paper E2E smoke는 아직 필요하다.
- [x] dashboard trades/stats do not require ClickHouse.
  - RuntimeLedger trades/stats/fills/health PnL tests가 temp SQLite로 통과.
- [ ] position recovery drill passes after process restart.
  - 부분 완료: SQLite ledger restart unit test와 PositionTracker runtime-ledger tests는 통과. 실제 paper process restart drill은 아직 필요하다.
- [x] `sts backtest run --symbol` supports `market_data.source=parquet`.
- [ ] full backtest/tier runners support `data.source=parquet`.
  - 미완료: `_run_tier_backtest`가 여전히 `load_stock_minute_from_clickhouse` / `load_stock_daily_from_clickhouse`를 직접 사용한다.
- [x] ML/RL training support is removed from runtime-storage acceptance and tracked by [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md).
  - 변경: RL/ML CLI와 training scripts는 Parquet/DuckDB 지원 대상이 아니라 decommission/archive 대상이다.
- [x] ClickHouse research profile renders optional ClickHouse/MLflow services.
- [x] default pytest does not touch live Redis/ClickHouse.
  - `tests/conftest.py`가 live-infra tests를 `KIS_RUN_LIVE_INFRA_TESTS=1` opt-in으로 스킵한다. CI는 isolated Redis/ClickHouse services를 사용한다.
