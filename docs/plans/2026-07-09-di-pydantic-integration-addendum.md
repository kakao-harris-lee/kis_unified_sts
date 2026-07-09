# DI + Pydantic + Polars/DuckDB 통합 보강안 (2026-07-09)

> 지시서: [docs/2026-07-08_new_architencture.md](../2026-07-08_new_architencture.md)
> 근거 분석: [2026-07-08-new-architecture-gap-analysis.md](2026-07-08-new-architecture-gap-analysis.md)
> 상위 계획: [2026-07-08-new-architecture-refactoring-plan.md](2026-07-08-new-architecture-refactoring-plan.md)
> 조사 기준: main `6d9f1bf9` (2026-07-09), config/wiring 코드 실측.

## 0. 이 문서의 위치

지시서 본문은 라이브러리로 **TA-Lib / vectorbt / pandas / numpy / KIS Open API**만
지정한다. **dependency-injector · Pydantic · Polars · DuckDB는 지시서에 없는 별도 추가
요청**이며, 본 보강안은 이들을 상위 리팩토링 계획(P0~P6)에 **어떻게 얹을지**를 정의한다.
계획을 대체하지 않고 횡단(cross-cutting) 레인으로 보강한다.

**한 줄 판정**:
- **Pydantic**은 신규 도입이 아니라 **이미 진행 중인 마이그레이션의 완성**이다
  (65개 파일 사용, 전부 v2). 별도 Phase 불필요 — **P4와 config 위생 작업에 흡수**한다.
- **dependency-injector**는 repo에 **참조 0건**인 신규 프레임워크다. 이 repo는
  이미 손수 constructor-injection을 전면 실천하므로, 원하는 것은 "DI"가 아니라
  **"DI 컨테이너"**다. 지시서가 고른 디커플링 프리미티브(Registry+Adapter)와
  **역할이 겹치는 구간이 있어 범위 한정이 필수**다. **후행 별도 레인(P6.5)**으로 배치한다.
- **DuckDB**는 신규 도입이 아니라 **이미 프로덕션 채택 완료**다
  (`duckdb>=1.0` 정식 의존성, Parquet 질의 6개 사이트). 커넥션 재사용 최적화만 남았다.
- **Polars**는 신규 제안이 아니라 **기존 로드맵(WS-A2/A4)에 배정된 미도입 항목**이다.
  **P3(vectorbt)와 동일 워크스트림**이며 numpy 2.0 스윕이 공유 선행조건. 상세는 §8.

## 1. 현황 실측

### 1.1 Pydantic — 이미 표준

| 사실 | 근거 |
|---|---|
| 65개 파일이 pydantic 사용 | `grep -rl "BaseModel\|pydantic"` |
| 전부 v2 관용구 | `field_validator` 37건, 레거시 `@validator` **0건** |
| `BaseSettings`(pydantic-settings) 미사용 | grep 0건 — env override는 수제 `_extract_env_vars` |
| 표준 config 기반 존재 | `shared/config/base.py::ServiceConfigBase(BaseModel)` — `from_yaml`/`from_env`/DB명 검증 제공 |
| builder 스키마도 Pydantic | `shared/strategy_builder/schema.py::BuilderState` |

**충돌 지점은 딱 하나 — 이중 config 시스템**:
- **Pydantic 경로**: `ServiceConfigBase` (신규 표준)
- **dataclass 경로**: `shared/config/mixins.py::ConfigMixin.from_dict` — **이미
  `DeprecationWarning` 발령 중**이며 메시지가 "Use ServiceConfigBase"로 안내(:132-138).
- **동일 파일 내 공존 사례**: `shared/risk/config.py`에 dataclass `RiskConfig`(:376)와
  pydantic `FuturesRiskConfig`(:654)/`StockRiskConfig`(:739)가 나란히 존재.
  이는 gap analysis §4.2 "설정 스키마 2벌"과 정확히 일치하며, refactoring plan
  **P4가 이미 "config 스키마 pydantic으로 통일"로 계획**한 항목이다.
- **전략 config 경로**: 레거시 전략 YAML(주식 13 + 선물 12)은
  `StrategyFactory.create` → `registry CONFIG_CLASS.from_dict`(dataclass)로 흐른다.
  여기에 Pydantic을 밀면 **P2(builder_v1 선언형 승격)와 전선이 겹친다.**

### 1.2 dependency-injector — 미도입, 그러나 DI 자체는 이미 실천 중

repo 전체 `dependency.injector`/`dependency_injector` grep **0건**. 그러나 각 서비스
`main.py`는 **이미 명시적 constructor-injection**을 한다. 예 —
`services/order_router/main.py::_build_and_run`(:574):

```python
futures_feed  = KISFuturesPriceFeed(config=kis_auth)
kis_adapter   = PaperKISFuturesAdapter(...) | KISFuturesAdapter(...)   # mode 분기
passive_maker = PassiveMaker(kis_client=kis_adapter, fill_logger=fill_logger)
pseudo_oco    = PseudoOCO(fill_logger=..., runtime_state=..., close_executor=...)
daemon        = OrderRouterDaemon(redis=..., passive_maker=..., pseudo_oco=..., ...)
```

즉 **"의존성을 생성자로 주입"이라는 DI의 본질은 이미 성립**한다. 없는 것은 이 조립을
선언적으로 관리하는 **컨테이너**뿐이다.

**지시서와의 긴장 — 디커플링 수단이 이미 지정됨**:
지시서 마지막 문단은 *"의존성은 Registry와 Adapter 계층을 통해서만 연결"*을 명령한다.
그리고 그 Registry/Adapter는 실재한다:
- 전략: `EntryRegistry`/`ExitRegistry`/`SizerRegistry` + `@register` + `StrategyFactory`
- 지표: `IndicatorRegistry` (`shared/indicators/engine/registry.py`)
- 실행: duck-typed `kis_client` seam (`KISFuturesAdapter`/`PaperKISFuturesAdapter` 2구현)

**⇒ 결론**: DI 컨테이너를 **전략/지표 컴포넌트 조합에 넣으면 기존 registry와 중복**이다.
지시서 정신상 **DI 컨테이너는 registry를 대체하지 않는다.** DI가 순이익인 곳은
registry가 관장하지 않는 **서비스 조립 루트와 인프라 어댑터**다.

## 2. 권장안 (요약)

| 항목 | 결정 | 배치 |
|---|---|---|
| Pydantic 전략 YAML 검증 | builder_v1 스키마로 수렴 (컴포넌트 위 별도 층 신설 금지) | **P2 연동** |
| Pydantic risk config 통일 | dataclass `RiskConfig` → pydantic 단일화 | **P4 흡수** |
| `ConfigMixin` 폐기 | 잔존 dataclass config를 `ServiceConfigBase`로 이관 후 제거 | **위생 레인** (P0~P4 병행) |
| dependency-injector 범위 | **서비스 조립 루트 + KIS 데이터 파사드 한정.** 전략/지표 registry 불가침 | **신규 P6.5** |
| dependency-injector 시점 | **후행.** order_router 1개 서비스 PoC로 3대 리스크 검증 후 확산 | **P6.5 (P3·P4 안정화 후)** |
| 컨테이너 config provider | 기존 `ServiceConfigBase` 인스턴스를 컨테이너에 수동 주입 (pydantic-settings 신규 도입 회피) | P6.5 |

## 3. Pydantic 작업 (신규 Phase 없음 — 흡수)

### 3.1 P4 흡수 — Risk config 단일화
- gap analysis §4.2의 "설정 스키마 2벌"을 pydantic으로 통일. dataclass
  `shared/risk/config.py::RiskConfig`(:376)를 `ServiceConfigBase` 기반으로 이관하고
  `FuturesRiskConfig`/`StockRiskConfig`와 키 중복(`max_consecutive_losses` vs
  `consecutive_loss_hard_threshold`) 정리. **이는 P4의 기존 항목이므로 신규 작업 아님.**
- `RiskState` 2벌(`models.py:222` dataclass vs `state.py:62` Redis HASH) 단일화도 P4 소속.

### 3.2 P2 연동 — 전략 config 검증 수렴
- 레거시 전략 YAML 검증을 **builder_v1 Pydantic 스키마로 수렴**한다. 컴포넌트
  dataclass 위에 별도 Pydantic 층을 새로 얹지 **않는다** (표면적 2배 증가 회피).
- 표현 불가로 레거시 컴포넌트에 존치되는 전략은 기존 `CONFIG_CLASS.from_dict`
  경로를 유지하되, **신규 전략은 선언형(Pydantic BuilderState) 기본** 원칙 적용
  (refactoring plan P2-c와 동일 규율).

### 3.3 위생 레인 — `ConfigMixin` 폐기
- `ConfigMixin.from_dict`는 이미 `DeprecationWarning` 상태. 잔존 소비자를
  `ServiceConfigBase.from_yaml`/`from_dict`로 이관 후 mixin 제거.
- **각 Phase에 얹혀 점진 진행** — 별도 대규모 PR 불필요. 소비자 grep으로 스윕.

### 3.4 Pydantic 게이트/주의
- v1↔v2 혼용 금지 (현재 v2 순수 — 유지). `pydantic-settings`는 DI 결정(§4)과
  묶어서만 도입 검토.
- config 검증 실패는 **기동 시점 fail-fast**여야 함(런타임 중 조용한 default 대체 금지).

## 4. dependency-injector 작업 — 신규 P6.5 (횡단, 후행)

### 4.1 원칙 (범위 가드)
1. **registry 불가침**: 전략(entry/exit/sizer)·지표 조합은 기존 registry가 유일한
   조립 메커니즘으로 남는다. DI 컨테이너로 재구현/대체하지 않는다.
2. **조립 루트에만 적용**: 각 서비스 `main.py::_build_and_run`의 인프라 배선
   (redis/config/KIS auth/feed/adapter/executor/ledger)이 대상.
3. **paper/live 스왑 표준화**: 현재 `if mode == "paper"` 분기(order_router:655)를
   DI provider override/selector로 표현 — 지시서 §9 "동일 전략, 실행계층만 상이"
   불변식을 컨테이너가 구조적으로 강제.
4. **KIS 데이터 파사드 (P6 연동)**: `KISClient` 직접 import ~7곳
   (`unified_trading_analyzer`, `screener`, `stock_strategy/main`,
   `market_structure_collector/main`, `market_ingest/main`,
   `trading/market_data_bootstrap`)을 어댑터 인터페이스 뒤로 넣고 DI provider로 주입.
   gap analysis §6.2 / plan P6 "KIS 데이터 파사드"의 실현 수단.

### 4.2 PoC 먼저 — order_router 1개 서비스
확산 전에 **order_router `_build_and_run` 하나**를 컨테이너로 전환해 아래 **3대
호환 리스크를 실측**한다. PoC 실패 시 DI 도입 자체를 재검토(계획 전체는 영향 없음).

| 리스크 | 내용 | 검증 방법 |
|---|---|---|
| **Pydantic v2 호환** | `providers.Configuration.from_pydantic()`은 `pydantic-settings` 기반 — v2 초기 파손 이력. 이 repo는 `BaseSettings` 미사용 | 컨테이너에 `ServiceConfigBase` 인스턴스를 **직접 주입**(from_pydantic 우회)하는 배선이 되는지 확인 |
| **lazy import 충돌** | `_build_and_run`은 사이클/무게 회피용 함수 내부 지연 import. `wire()`+`Provide[...]`는 import-time 결합 증가 | `wire()` 스코프를 서비스 패키지로 한정하고 사이클 재발 여부를 import 스모크로 확인 |
| **asyncio 자원** | `await futures_feed.start()`, `await order_executor.initialize()` 등 async 초기화 | `providers.Resource` async init/shutdown 패턴으로 감싸 정상 기동/종료 확인 |

### 4.3 확산 순서
- PoC(order_router) 통과 → 디커플 선물 서비스군(risk_filter/decision_engine/
  market_ingest) → 디커플 주식 파이프라인 → KIS 데이터 파사드(P6).
- **모놀리식 오케스트레이터(`services/trading`, 17K LOC)는 대상 제외** — F-9 컷오버로
  은퇴 예정이라 DI 배선은 낭비. plan P6/F-9와 동일 규율.

### 4.4 게이트
- 각 서비스 전환은 **기동/종료 동등성**(전환 전후 동일 프로세스 그래프·로그) 확인.
- paper 스택 무중단. live 게이트/kill-switch sentinel 동작 불변.
- import 스모크 + 기존 서비스 통합 테스트 green.

## 5. 순서/의존성 (상위 계획에 얹기)

```
P0 ─▶ P1 ─▶ P2 ─────────▶ P3(주식) ─▶ P3-d(선물)
       │      ╲ (Pydantic 전략검증 수렴)
       ├────▶ P4 (Pydantic risk config 통일 흡수)
       └────▶ P5
                              ↓ (P3·P4 안정화 후)
                        P6 ─▶ P6.5 (dependency-injector: PoC→확산)
   [위생 레인] ConfigMixin 폐기 — P0~P4에 점진 병행
```

- **Pydantic**: 병렬 흡수 — 신규 임계경로 추가 없음.
- **dependency-injector**: P6.5로 후행. 이유 — DI가 가장 자연스러운 자리(조립 루트 +
  P6 파사드)가 후반부라, 선도입 시 P1~P5가 다시 쓸 wiring을 두 번 건드리는
  **rework 위험**. 후행이 rework 최소.

## 6. 결정 로그 (사용자 승인 사항, 2026-07-09)

1. dependency-injector 범위 = **조립 루트 + KIS 데이터 파사드 한정** (전략/지표
   registry 확대 안 함).
2. dependency-injector 시점 = **후행(P6.5)**, order_router PoC 선행.
3. 전략 YAML의 Pydantic화 = **builder_v1 스키마로 수렴** (P2 연동, 별도 층 신설 안 함).
4. 컨테이너 config provider = **기존 `ServiceConfigBase` 수동 주입** (pydantic-settings
   신규 도입은 PoC에서 필요성 확인 후 재검토).
5. DuckDB = **채택 완료로 간주** — 신규 Phase 없이 커넥션 재사용/캐시 최적화만 (§8).
6. Polars = **P3(vectorbt)와 묶어 도입**, numpy 2.0 스윕 선행, 고아 `test_data_engine.py`
   정리가 첫 관문. pandas **전면 대체 아님** — 배치/백테스트 경로 한정 (§8).

## 7. 비목표 (Non-goals)

- DI 컨테이너로 전략/지표 registry 대체 — **금지** (지시서 Registry/Adapter 원칙 위반).
- 모놀리식 오케스트레이터 DI 배선 — 제외 (F-9 은퇴 예정).
- Pydantic 위해 기존 v2 코드를 pydantic-settings로 일괄 전환 — 불필요.
- 라이브 position/ledger 경계 변경 — 본 보강안 범위 밖(상위 계획 §3.5 유지).

## 8. Polars / DuckDB 정합 (데이터 처리 레인)

지시서는 데이터 처리로 pandas/numpy만 지정하나, 사용자가 **Polars(대용량 DataFrame
엔진)와 DuckDB(Parquet 전용 SQL 엔진)** 추가를 요청. 실측 결과 **둘 다 신규 제안이
아니라 이미 채택됐거나 로드맵에 배정된 항목**이므로, 여기서는 상위 계획 및 기존
로드맵과의 정합만 정의한다. (근거 로드맵:
[2026-07-05-indicator-engine-and-stream-schema-roadmap.md](2026-07-05-indicator-engine-and-stream-schema-roadmap.md)
Track A / WS-A2 / WS-A4.)

### 8.1 현황 실측

| 도구 | 상태 | 근거 |
|---|---|---|
| **DuckDB** | **프로덕션 채택 완료** | `pyproject.toml:53` `duckdb>=1.0` 정식 의존성. Parquet 질의 6개 사이트: `market_data_store.py`(:79/:195/:252 `read_parquet` + WHERE 푸시다운), `market_structure_store.py`(:344/:457/:465), `daily_futures.py`(:539), `krx_daily_futures.py`(:512). CLAUDE.md 스토리지 규칙이 표준으로 명문화. |
| **Polars** | **로드맵 배정, 미도입** | 코드 import 0건. `pyproject.toml:60-66` 주석이 보류 사유 명시. 로드맵 WS-A2(캐시엔진 팬아웃 `group_by(symbol)`)·WS-A4(대용량 배치+vectorbt 프리컴퓨트)에 배정. |
| **pandas** | 44개 파일, 라이브 지표 hot-path + 백테스트 전반 | Polars **전면 대체 대상 아님** (§8.4). |

### 8.2 DuckDB — 채택 완료, 최적화만

DuckDB는 사용자가 원하는 "Parquet 전용 SQL 엔진" 역할로 **이미 작동 중**이다
(`read_parquet(..., hive_partitioning=true)` + `code`/`datetime` 술어 푸시다운).
남은 것은 신규 도입이 아니라 최적화다:

- [ ] 매 질의 `duckdb.connect(database=":memory:")` 신규 오픈(`market_data_store.py:195/:252`,
  `market_structure_store.py:344/…`) → 백테스트/스윕에서 반복 질의 시 커넥션 재사용
  또는 영속 캐시 검토. **기능 변화 0, 성능만.**
- [ ] Optuna 스윕·다심볼 백테스트 등 반복 질의 경로에서 측정 후 적용(측정 없는 선최적화 금지).
- **비목표**: 런타임(Redis/KIS fallback) 경로를 DuckDB로 바꾸지 않는다 —
  DuckDB는 과거 데이터(backtest/배치) 전용이라는 CLAUDE.md 경계 유지.

### 8.3 Polars — P3(vectorbt)와 묶어 도입

Polars의 실익 지점은 로드맵/상위 계획이 이미 지정: **다심볼 배치 + 백테스트
프리컴퓨트**로, 신규 아키텍처 계획 **P3(vectorbt)와 같은 워크스트림**이다.

- [ ] **numpy 2.0 스윕(공유 선행조건)**: 로드맵 명시 — Polars/vectorbt/numba가 동일
  numpy 게이트 공유. 현재 `pyproject.toml:50` `numpy>=1.26`. Polars를 P3와 별개로
  먼저 넣으면 numpy 스윕을 두 번 하게 되므로 **P3와 한 번에** 승격.
- [ ] **고아 테스트 정리(첫 관문)**: `tests/unit/core/test_data_engine.py`가 참조하는
  `core.data_engine` 모듈은 **repo에 존재하지 않음**(`shared`/`services` 부재). 지금은
  `pytest.importorskip("polars")`로 스킵되나 polars 설치 시 import 에러로 깨진다.
  **Polars 설치의 실제 첫 차단막은 이 죽은 테스트** — 대규모 마이그레이션이 아니라
  삭제 한 건이 진입장벽. (P0 dead-code 정리 레인에 편입 가능.)
- [ ] **적용 범위**: `market_data_store`(Parquet) → Polars lazy feature build →
  vectorbt `from_signals` 입력(로드맵 WS-A4 = P3-a). `shared/backtest/` 프리컴퓨트와
  `shared/indicators` 캐시엔진 배치 팬아웃(WS-A2)에 한정.

### 8.4 범위 제약 — "pandas 대체"의 실제 의미

사용자 표현 *"Pandas를 대체하는 DataFrame 엔진"*은 이 시스템에서 **전면 대체가 아니다**:

- **라이브 지표 hot-path 유지**: `shared/indicators/momentum.py`·`daily.py`·
  `engine/reference_backend.py` 등은 shadow-parity 계약(gap analysis §8·§1.2)상
  값이 수제 관례와 bit-identical해야 함 → **무단 엔진 교체 금지.** Polars 전환은
  parity 게이트 없이는 불가.
- **Polars = 배치/백테스트 레인 한정**: 44개 pandas 파일 중 백테스트 프리컴퓨트 +
  캐시엔진 팬아웃 경로만 대상. 나머지 pandas는 존치.
- **런타임 이미지 무게**: 로드맵대로 Polars는 런타임 의존, numba는 `[performance]`
  optional extra 유지. `backtest`/배치 격리 원칙(상위 계획 §9 리스크 표)과 정합.

### 8.5 순서 (§5 그래프에 편입)

```
P0(고아 test_data_engine.py 정리) ─▶ … ─▶ P3(주식)
                                          ├─ numpy 2.0 스윕 (Polars/vectorbt/numba 공유)
                                          └─ Polars lazy feature build → vectorbt from_signals
DuckDB 커넥션 재사용 최적화 — P3 배치 경로에서 측정 후 (독립, 저위험)
```

**게이트**: Polars 전환 경로는 P3-b parity 게이트(총수익/샤프/MDD/트레이드 수 일치)에
종속 — 상위 계획 P3와 동일 머지 조건. DuckDB 최적화는 질의 결과 동등성 + 성능 측정.
