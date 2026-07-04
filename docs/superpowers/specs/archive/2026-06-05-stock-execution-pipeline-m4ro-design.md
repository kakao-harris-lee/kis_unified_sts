# Stock Execution Pipeline (M4-R + M4-O) — Design

- Date: 2026-06-05
- Status: Design (pending implementation plan)
- Parent effort: `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md` (M4)
- Scope: **M4-R (stock risk_filter) + M4-O (stock order_router)** — the stock entry-execution tail of the decoupled stream pipeline. **M4-X (stock exit) is deferred to its own spec.**

## 1. Goal & scope

Stream-pipeline-decoupling 로드맵의 M4는 "risk_filter + order_router 주식 일반화"다. 이 spec은 그중 **진입 실행 경로**만 다룬다: M4-P가 발행하는 stock 진입 후보를 소비해 리스크 필터 → paper 집행 → fill까지 잇는 자산별(주식) 데몬 2개를 신설한다.

**성공 기준:** `signal.candidate.stock.shadow` → risk → `signal.final.stock.shadow` → order → `order.fill.stock.shadow` 경로가 shadow-first/default-off로 동작하고, 무거운 로직(RiskFilterLayer / PaperBroker / FillLogger / RuntimeLedger / StreamStage)은 무변경 재사용하며, **머지된 선물 live 경로에 회귀가 없다.**

비목표(이번 spec out of scope): M4-X(청산, ThreeStageExit producer + 포지션 close), ATS/VenueRouter 배선, 실거래 KIS 주식 주문 + stock live guard, 주식 short 진입, 선물 무접미사 스트림의 `.futures` 리네임, candidate 스키마 통합(Signal asset_class), M5 모놀리식 orchestrator 컷오버.

## 2. Locked decisions (브레인스토밍 2026-06-05)

| 결정 | 선택 | 근거 |
|---|---|---|
| 증분 범위 | **R+O 먼저, X는 별도 spec** | 진입 실행(R/O)은 기계적이나 청산(X)은 신규 producer + 포지션 상태 모델이라 난이도 질적 차이 |
| shadow 집행 의미 | **전체 경로 paper 집행 + `order.fill.stock.shadow` 발행** | 모놀리식 orchestrator는 M5에서 제거 대상 → 이중집행 방지용 특수 격리 불필요; default-off + 자산별 flag 상호배제로 충분 |
| ATS 라우팅 | **KRX-only 먼저, ATS는 flag 뒤 후속** | `ats_routing.enabled` 기본 false와 정합, YAGNI, 증분 초점 유지 |
| 데몬 구조 | **주식 전용 데몬 모듈 신설** (`services/stock_risk_filter/`, `services/stock_order_router/`) | M4-P가 `services/decision_engine`(선물)을 일반화 않고 `services/stock_strategy/` 신설한 선례; 머지된 선물 경로 무변경(회귀 0); 무거운 로직은 `shared/` 공유 |

## 3. Current state (감사 2026-06-05)

- **M4-R 대상**: `services/risk_filter/main.py` `RiskFilterDaemon(StreamStage)` — `stream:signal.candidate` → `stream:signal.final`. **futures 하드코딩**(`RuntimeRiskState(asset_class="futures")`, `FuturesRiskConfig.from_yaml()`). 파서 `_signal_from_stream_fields`가 **futures 후보**(setup_type/stop_loss/take_profit/reason_tags) 형태를 기대.
- **M4-O 대상**: `services/order_router/main.py` `OrderRouterDaemon(StreamStage)` — `stream:signal.final` → `stream:order.fill`. **futures/KRX 전용**(`KISFuturesAdapter`, `ContractSpec`, `PseudoOCO`, `locked_symbol`, `live_mode_guard`). `VenueRouter`(ATS)는 존재하나 order_router 미배선(orchestrator/backtest 경로에만). `FillLogger`/`RuntimeLedger`는 이미 asset-generic.
- **M4-P 산출(입력 소스)**: `services/stock_strategy/` `StockStrategyDaemon` → `signal.candidate.stock.shadow`. 직렬화 `services/stock_strategy/candidate.py::stock_signal_to_stream_dict`. 필드: `signal_id, code, name, strategy, direction, price, quantity, confidence, generated_at_ms, metadata_json` (stop/target/setup_type **없음**). 현재 **소비자 없음**(M4-R/O가 빌드).
- **공유 자산(무변경 재사용 대상)**: `shared/streaming/stage.py::StreamStage`(consumer-group 루프/XREADGROUP/XACK/poison-pill drop/NO-XACK retry/graceful shutdown/metrics), `shared/risk/layer.py::RiskFilterLayer`(8필터), `shared/risk/runtime_state.py::RuntimeRiskState`, `shared/paper`의 `PaperBroker`(슬리피지 집행), `shared/execution/fill_logger.py::FillLogger`, `shared/storage/runtime_ledger.py`(SQLite).

## 4. Target architecture

### 4.1 Stream topology (주식 진입 실행 경로, 전부 `.stock.shadow` 접미사)
```
signal.candidate.stock.shadow        ← M4-P producer (이미 존재)
   │
   ▼  [M4-R] StockRiskFilterDaemon(StreamStage)   group=stock_risk_filter
   │        stock candidate codec → RiskFilterLayer.evaluate → size_multiplier
   ▼
signal.final.stock.shadow            ← 신규
   │
   ▼  [M4-O] StockOrderRouterDaemon(StreamStage)  group=stock_order_router
   │        PaperBroker 집행(slippage) → FillLogger(asset_class="stock") → 포지션 오픈 기록
   ▼
order.fill.stock.shadow              ← 신규 (+ SQLite RuntimeLedger 기록)
```

각 데몬이 자기 스트림만 소유. **단계별 단일 ordered consumer**(주식 universe 수십 종목; Stage0에서 per-tick·전략 비용 μs 검증 → 샤딩 불필요·YAGNI).

**스트림 키 범위 결정:** 선물 무접미사 스트림(`stream:signal.candidate`/`final`/`order.fill`)의 `.futures` 리네임은 **이번 증분에서 하지 않는다**(머지된 선물 live 경로 회귀 리스크). 이번엔 주식 `.stock.shadow` 신규 스트림만 추가하고, 리네임은 M5 컷오버/별도 정리로 연기한다.

### 4.2 메시지 스키마

**입력 (M4-P 고정, 변경 안 함)** — `signal.candidate.stock.shadow`
`signal_id, code, name, strategy, direction, price, quantity, confidence, generated_at_ms, metadata_json`

**M4-R 출력** — `signal.final.stock.shadow` = candidate 전체 + 2필드 (선물 risk_filter가 final에 size_multiplier/filtered_at_ms 부착하는 것과 동형)
- `+ size_multiplier` (str, LayerResult, [0,1])
- `+ filtered_at_ms` (str, epoch ms)

**M4-O 출력** — `order.fill.stock.shadow` = `FillLogger.log_fill` 스키마 (이미 asset-generic)
`signal_id, order_id, symbol(=code), side, order_type, requested_price, filled_price, slippage_ticks, quantity, requested_at_ms, filled_at_ms, latency_ms, venue=KRX, trade_role=entry, asset_class=stock, broker_error_code`

### 4.3 내부 정규화 (stock codec)
stock candidate는 선물 `Signal`(setup_type/entry_price/stop_loss/take_profit)과 형태가 달라 그대로 `RiskFilterLayer.evaluate`에 못 먹인다. **stock codec**(`_stock_signal_from_stream_fields`, M4-P 직렬화의 역방향)이 candidate 필드를 `RiskFilterLayer.evaluate`가 받는 입력(direction, symbol=code, intended notional=price×quantity, confidence)으로 매핑하는 얇은 어댑터를 둔다. **RiskFilterLayer 자체는 무변경**.

## 5. M4-R — StockRiskFilterDaemon

### 5.1 모듈 & 골격
- 신규 `services/stock_risk_filter/main.py`, `StockRiskFilterDaemon(StreamStage)`
- group `stock_risk_filter`, in `signal.candidate.stock.shadow` → out `signal.final.stock.shadow`
- 플래그 `STOCK_RISK_FILTER` (`off` 기본=inert exit 0 / `shadow`=shadow wiring / `live`=unsuffixed live wiring)
- systemd `kis-stock-risk-filter.service` **disabled**
- StreamStage 상속으로 루프/그룹/XACK/poison-pill drop/NO-XACK retry/graceful shutdown/metrics **전부 상속**(재구현 0)

### 5.2 재사용 vs 신규
| 요소 | 처리 |
|------|------|
| `RiskFilterLayer` (8필터 오케스트레이션) | **무변경 재사용** |
| `RuntimeRiskState` | 재사용, `asset_class="stock"` → Redis `risk:state:stock` 격리 |
| stock candidate 파서 | **신규** `_stock_signal_from_stream_fields` (§4.3 codec) |
| 리스크 config | **신규** `StockRiskConfig`(ServiceConfigBase, `config/risk.yaml`의 `risk_stock:` 섹션, `_env_prefix="STOCK_RISK_"`) |

### 5.3 8필터의 주식 적용 (RiskFilterLayer 그대로, config/provider만 주식용)
| 필터 | 주식 동작 | shadow(entry-only) 유효성 |
|------|----------|--------------------------|
| TradingHours | **주식 세션 윈도우**(09:00–15:30 KST), 선물 윈도우 아님 → `risk_stock.trading_windows` | 유효 |
| DailyTradeCount | 일일 진입 횟수 cap | 유효 |
| OpenPosition | **주식 핵심** — 이미 보유 종목 재진입 차단(멀티종목); provider가 shadow ledger 포지션 read | 유효 |
| Volatility (ATR) | pluggable provider | provider 미주입 시 fail-open |
| Spread | pluggable provider | 미주입 시 fail-open |
| DailyMDD / WeeklyMDD / ConsecutiveLoss | 실현손익 기반 | **X(청산) 전까지 사실상 inert**(실현 PnL 미유입) |

### 5.4 정직한 shadow 한계 (M4-P warmup 한계 문서화와 동형)
- entry-only + X 미구현이라 **PnL 의존 필터(MDD/연속손실)는 X 랜딩 전까지 무력**. 활성 필터 = TradingHours / DailyTradeCount / OpenPosition.
- OpenPosition provider는 shadow order_router(M4-O)가 연 포지션을 read → 청산이 없으니 포지션 누적. shadow 검증 단계에선 수용, 이 한계를 명기한다.

### 5.5 size_multiplier
LayerResult의 `size_multiplier`([0,1])를 final에 부착만 한다. 실제 수량 곱(`quantity×size_multiplier`)은 M4-O가 수행.

### 5.6 카운터 (선물과 동형, stock 네임스페이스)
`daily_trade_count / daily_pnl_krw / weekly_pnl_krw / consecutive_losses` → `risk:state:stock`, 일일 리셋(`RuntimeRiskState.should_reset_daily`/`reset_daily`).

## 6. M4-O — StockOrderRouterDaemon

### 6.1 모듈 & 골격
- 신규 `services/stock_order_router/main.py`, `StockOrderRouterDaemon(StreamStage)`
- group `stock_order_router`, in `signal.final.stock.shadow` → out `order.fill.stock.shadow`
- 플래그 `STOCK_ORDER_ROUTER` (`off` 기본 / `shadow` / `live`)
- systemd `kis-stock-order-router.service` **disabled**
- StreamStage 상속(루프/XACK/에러정책/shutdown)

### 6.2 집행 경로 (shadow = paper, KRX-only)
```
final.stock.shadow 파싱
  → quantity = candidate.quantity × size_multiplier (floor to shares)
  → side = buy (long 진입; 주식 short은 범위 밖)
  → PaperBroker.submit_order(code, buy, qty, price)   ← shared/paper 재사용, 슬리피지 적용(필수)
  → FillLogger.log_fill(asset_class="stock", venue="KRX", trade_role="entry")
       → XADD order.fill.stock.shadow  +  RuntimeLedger.record_fill (SQLite)
  → 포지션 오픈 기록 → stock:daemon:positions + ledger
```

### 6.3 재사용 vs 신규/제외
| 요소 | 처리 |
|------|------|
| `PaperBroker` (슬리피지 집행) | **무변경 재사용**(orchestrator stock paper와 동일 엔진) |
| `FillLogger` / `RuntimeLedger` | **재사용**(이미 asset-generic, `asset_class="stock"`만 전달) |
| `ContractSpec`(multiplier/tick) | **제외** — 주식은 share 단위·decimal 가격 |
| `PseudoOCO` 브라켓 | **제외** — 주식은 진입시점 stop/target 없음(X가 소유, 연기) |
| `locked_symbol` 단일종목 잠금 | **제외** — 멀티종목 포트폴리오 |
| `KISFuturesAdapter` / futures live guard | **제외** — 주식 paper-only |

### 6.4 핵심 통합점 — 포지션 오픈 기록
M4-O가 fill 시 **포지션을 shadow ledger + `stock:daemon:positions`에 오픈 기록**한다. 이게:
- **(a)** M4-R `OpenPositionFilter`가 read하는 소스(재진입 차단)
- **(b)** 나중에 **X(청산)가 소비할 포지션 상태**의 생성 지점(entry_price/quantity/state=SURVIVAL 초깃값)

→ 진입 데몬이 포지션 lifecycle의 "오픈"을 소유하고, X가 "클로즈"를 소유하는 경계. X spec은 이 포지션 레코드를 입력 계약으로 받는다.

### 6.5 범위 밖 seam (후속 flag/사이클)
- **실거래(real KIS 주식 주문) + VenueRouter(ATS)** — paper 검증 후 `ats_routing.enabled`/stock-live flag 뒤 배선. 집행 함수 경계에 seam만 남긴다.
- **주식 short 진입** — 현 주식 전략 long-only, KIS 리테일 공매도 제약 → 범위 밖.
- **stock live guard** — 주식은 paper 운용이라 이번 증분 불필요. live 전환 시 선물 `live_mode_guard` 대응물 추가.

## 7. 공유점 & DRY

### 7.1 플래그 (M4-P `STOCK_STRATEGY_DAEMON` 패턴 동형)
| 데몬 | env | 값 |
|------|-----|----|
| M4-R | `STOCK_RISK_FILTER` | `off`(기본, inert) / `shadow` / `live` |
| M4-O | `STOCK_ORDER_ROUTER` | `off`(기본) / `shadow` / `live` |

스트림 키는 선택적 env 오버라이드(`STOCK_CANDIDATE_STREAM`/`STOCK_FINAL_STREAM`/`STOCK_FILL_STREAM`)로 테스트 격리 — M4-P `STOCK_TICK_STREAM` 선례.

### 7.2 systemd (둘 다 disabled, `deploy/systemd/`)
`kis-stock-risk-filter.service`, `kis-stock-order-router.service` — M4-P 유닛 템플릿 복제(`Type=simple, User=deploy, WorkDir=repo, EnvironmentFile=.env, Environment=STOCK_*=shadow, Restart=on-failure, RestartSec=10, TimeoutStopSec=30, KillSignal=SIGTERM`). 운영자가 shadow 검증 게이트 통과 후 `systemctl enable`.

### 7.3 타깃 DRY 개선 (선택, plan에서 포함/연기 판단)
shadow-first 엔트리포인트 boilerplate(`_resolve_mode`/`_candidate_stream_for`/시그널핸들러 `_build_and_run`/`main`)가 이미 M4-P + M2+M3에서 3중복, M4-R/O 추가 시 5중복. → 얇은 `shared/streaming/daemon_entrypoint.py`(`resolve_mode()`, `run_with_signal_handlers()`) 추출 제안. scope creep 방지를 위해 **plan에서 "포함 vs 연기" 결정**(강제 아님).

### 7.4 설정 터치포인트
- `config/risk.yaml`에 `risk_stock:` 섹션 신설(주식 세션 윈도우 + cap)
- 집행/슬리피지는 기존 주식 paper 설정 재사용(`PaperBroker` config)

## 8. 에러처리 (StreamStage 상속 + 주식 특이 케이스)
| 상황 | 정책 |
|------|------|
| candidate 파싱 실패(필드 누락/깨짐) | **poison-pill → XACK drop**(스트림 안 막음) + `parse_errors` 카운터 |
| 리스크 평가/handle 실패 | **NO-XACK retry** |
| XADD(final/fill) 발행 실패 | **NO-XACK**(시그널 보존) |
| provider 미주입(ATR/spread) | **fail-open**(pass) — 선물과 동형 |
| PaperBroker 집행 실패(희박) | NO-XACK retry → N회 후 drop+카운터 |
| RuntimeLedger write 실패 | **best-effort**(fill 스트림은 발행), ledger 실패가 시그널 소실로 이어지지 않음 |
| SIGTERM/SIGINT | stop event → in-flight 완료 → redis aclose(상속) |

메트릭/heartbeat: 데몬별 카운터(`candidates_processed`, `rejected_by_filter{filter}`, `fills_published`, `parse_errors`) → StreamStage 경로로 Prometheus.

## 9. Testing

- **M4-R 단위**: stock candidate parse round-trip · 활성 필터(TradingHours 주식윈도우/DailyTradeCount/OpenPosition) · size_multiplier passthrough · poison-pill drop · 플래그 off=inert · `risk:state:stock` 네임스페이스 격리.
- **M4-O 단위**: final parse · `qty=quantity×size_multiplier` floor · PaperBroker fill+슬리피지 · FillLogger 스키마(asset_class=stock/venue=KRX/trade_role=entry) · **포지션 오픈 기록**(`stock:daemon:positions`) · 플래그 off=inert.
- **통합(핵심)**: `candidate.stock.shadow → M4-R → final.stock.shadow → M4-O → fill.stock.shadow` e2e + 페이로드 정합 + **OpenPositionFilter가 오픈된 포지션 인식**(같은 code 2차 candidate 재진입 차단).
- **회귀**: full `tests/` 게이트(병렬+직렬) green, ruff/black/mypy clean. **선물 데몬 무변경 → 선물 테스트 그대로 green = 회귀 0 증명**. 기존 RiskFilterLayer/PaperBroker 테스트 재사용.

## 10. Acceptance criteria

- [ ] `signal.candidate.stock.shadow` → M4-R(StockRiskFilterDaemon) → `signal.final.stock.shadow` 동작.
- [ ] M4-R가 RiskFilterLayer/RuntimeRiskState/StreamStage 무변경 재사용, stock 파서 + StockRiskConfig만 신규.
- [ ] M4-O가 PaperBroker 집행(슬리피지) → `order.fill.stock.shadow` + RuntimeLedger 기록.
- [ ] M4-O가 포지션 오픈 기록 → OpenPositionFilter 재진입 차단 e2e 통과.
- [ ] 둘 다 default-off, systemd disabled, **선물 경로 무변경(회귀 0)**.
- [ ] warmup·기록 경로에 ClickHouse 없음(parquet+SQLite).
- [ ] PnL 의존 필터의 entry-only 무력 한계 문서화.

## 11. Open questions (구현 계획에서 확정)

- PR 분할: R·O 2 PR 순차(R→O) vs 1 PR(R+O). 둘 다 shared 재사용으로 소형 — writing-plans에서 결정.
- §7.3 daemon_entrypoint DRY 추출을 이 증분에 포함할지 vs 별도 chore.
- `StockRiskConfig` 필터 파라미터 기본값(주식 세션 윈도우, daily trade cap) 초깃값 — 기존 stock paper 운용 설정에서 가져온다.
- OpenPosition provider가 read하는 포지션 소스 키(`stock:daemon:positions`) 정확한 형식 — M4-O 포지션 오픈 기록 스키마와 정합 확정.
