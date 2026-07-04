# Stock Exit Daemon (M4-X) — Design

- Date: 2026-06-06
- Status: Design (pending implementation plan)
- Parent effort: `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md` (M4)
- Predecessor: `docs/superpowers/specs/2026-06-05-stock-execution-pipeline-m4ro-design.md` (M4-R/O, merged PR #416)
- Scope: **M4-X — the stock exit daemon.** A self-contained timer-loop daemon that scans open stock positions (written by M4-O), runs `ThreeStageExit`, paper-executes sells, closes positions, and feeds realized PnL back to `RuntimeRiskState` (activating M4-R's PnL-dependent filters). Shadow-first, default-off.

## 1. Goal & scope

M4-R/O built the stock entry-execution path (candidate → risk → final → order → fill + position record) but **entry-only**: open positions accumulate with no exit. M4-X closes the lifecycle — it owns the **exit** half (open ↔ close symmetry with M4-O).

**Success criterion:** A shadow-first, default-off daemon that, per decision cadence, reconstructs open stock positions from `stock:daemon:positions`, tracks each position's running high, runs `ThreeStageExit` (stop/breakeven/trailing/time_cut/EOD), paper-executes full-position sells with slippage, publishes exit fills to `order.fill.stock.shadow`, closes positions (HDEL), and feeds realized PnL to `RuntimeRiskState` — **activating M4-R's currently-inert MDD/consecutive-loss filters** (the key value). Heavy logic (`ThreeStageExit` / `VirtualBroker` / `FillLogger` / `StreamConsumerFeed` / `RuntimeRiskState`) is reused; the only shared-code change is one additive, backward-compatible `ThreeStageExitConfig` flag.

비목표(이번 spec out of scope): BEAR_EXIT / regime / `market_state` wiring (deferred — `enable_bear_exit=false`), per-strategy exit configs (v1 single config; needs M4-O to persist `strategy`), partial exits (full-close only), real KIS sell execution + stock live guard, stock short exit, `FillLogger` exit_reason/pnl fields, orchestrator adopting `eod_exempt_maximize`, M5 monolithic-orchestrator cutover.

## 2. Locked decisions (브레인스토밍 2026-06-06)

| 결정 | 선택 | 근거 |
|---|---|---|
| EOD 정책 | **no-flatten — MAXIMIZE는 EOD_CLOSE 면제** (SURVIVAL/BREAKEVEN만 EOD 청산) | CLAUDE.md "MAXIMIZE 추세 종목 EOD 강제청산 금지" — M4-X가 이 문서화된 정책을 실제 구현하는 지점. parity보다 정책 정확성 우선 |
| BEAR_EXIT 범위 | **v1 연기** (`enable_bear_exit=false`, `market_state=None`) | regime 소스(orchestrator `_current_regime`/MFI MarketClassifier)는 교차 의존 — 핵심 청산+PnL 피드백은 regime 불필요. 핵심 검증 후 별도 증분 |
| 배치 | **자기완결 StockExitDaemon** (타이머 루프, M4-P 구조) | 청산이 평가→SELL→close→PnL피드백 전 생명주기를 소유, risk_filter 없음(청산은 무조건 발동). M4-P 피드+루프 패턴 재사용 |
| EOD 면제 구현 | **`ThreeStageExitConfig`에 `eod_exempt_maximize: bool=False` 추가** (additive, config-driven) | 프로젝트 config-driven 원칙 부합, 하위호환(기본 False=현 동작), orchestrator 향후 opt-in 가능 |

## 3. Current state (감사 2026-06-06)

- **청산 평가 엔진**: `shared/strategy/exit/three_stage.py::ThreeStageExit.scan_positions(positions, market_data, market_state) -> list[ExitSignal]`. `_check_position` 우선순위: EOD_CLOSE → BEAR_EXIT → stage(STOP_LOSS/BREAKEVEN_STOP/TRAILING_STOP) → TIME_CUT. stage는 매 호출 `profit_pct`로 재계산(sticky 아님). **`position.highest_price`를 읽지만 갱신은 호출자 책임** (`Position.update_price`는 호출자가 호출). 지표 불필요 — `current_price`만 사용.
- **`ThreeStageExitConfig`**(`three_stage.py:63`): stop/breakeven/maximize/trailing/overshoot/time_cut/eod_close_hour·minute/fee_rate/enable_bear_exit. **`enable_eod_close`/`eod_exempt` 류 플래그 없음** — EOD_CLOSE가 `eod_close_time`(기본 15:15)에 모든 stage 무조건 발동.
- **EOD 모순**: `config/exit/three_stage.yaml` = 15:15. `vr_composite`는 기본값 사용→15:15 강제청산. `bb_reversion`만 23:59로 override. CLAUDE.md no-flatten 정책은 **현 코드 미적용**.
- **`Position`**(`shared/models/position.py`): `id/code/name/side/quantity/entry_price/entry_time/current_price/highest_price/lowest_price/stop_price/state/strategy/fee_rate/metadata`. `update_price(price)`가 high/low 갱신. `__post_init__`가 high/low/current를 entry_price로 초기화.
- **M4-O 포지션 레코드**(consumer 입력): `stock:daemon:positions` hash, **field=code**, value JSON `{code, entry_price, quantity, opened_at_ms, state, signal_id}`. **`strategy`/`name`/`highest_price` 미저장**.
- **realized PnL 경로(orchestrator)**: 청산 시 `RiskManager.record_realized_pnl(pnl)`(`shared/risk/manager.py`) — daily_realized_pnl 누적. **이는 M4-R이 읽는 `RuntimeRiskState`(`shared/risk/runtime_state.py`)와 다른 객체.** `RuntimeRiskState`: `record_trade(pnl_krw)` / `record_win()` / `record_loss()` / `snapshot()`, `risk:state:{asset}` 네임스페이스. M4-R `RiskFilterLayer.evaluate(signal, snapshot)`가 이 snapshot의 daily/weekly PnL·consecutive_losses를 읽음.
- **Dashboard key 분리**: `TradingStatePublisher`가 쓰는 `trading:stock:positions[:shadow]`와 M4-O/X working-store를 분리해 monitor live publish가 exit working-store를 덮어쓰지 않게 한다.
- **재사용 컴포넌트**: `StreamConsumerFeed`(M1b, `services/trading/stream_consumer_feed.py` — market:ticks XREAD → price 캐시, `get_current_price`), `VirtualBroker`(`shared/paper/broker.py` — `submit_order(side=SELL,...)`), `FillLogger`, `SQLiteRuntimeLedger`.

## 4. Target architecture (Approach A — self-contained timer-loop daemon)

### 4.1 모듈 (M4-P `services/stock_strategy/` 구조 차용)
```
services/stock_exit/
  __init__.py
  daemon.py   # StockExitDaemon — decision-cadence loop
  main.py     # flag-gated entrypoint (_resolve_mode / _build_and_run / main)
```
`StockExitDaemon`은 **StreamStage가 아님**(청산 후보 상위 스트림 없음) — M4-P `StockStrategyDaemon`처럼 피드 + 주기 루프.

### 4.2 사이클당 데이터 흐름
```
1. stock:daemon:positions(hash) 읽기 → opened_at_ms 시그니처 가진 레코드만 채택(§4.6 가드)
2. feed.update_symbols(보유 codes); code별 current = feed.get_current_price(code)
3. Position 재구성/갱신(in-memory): position.update_price(current) → highest/lowest 갱신
4. 갱신된 highest/lowest를 hash 레코드(high_water/low_water)에 영속 — running-high 재시작 복구
5. market_data = {code: {"close": current}} 빌드 (current 없는 code는 제외)
6. ThreeStageExit.scan_positions(positions, market_data, market_state=None) → ExitSignals
7. 각 ExitSignal → §5 실행
```

### 4.3 Position 재구성 (M4-O 레코드 → Position)
`Position(id=signal_id, code=code, name="", side=PositionSide.LONG, quantity=quantity, entry_price=entry_price, entry_time=<opened_at_ms→datetime UTC>, state=<record state>, fee_rate=<config>)`.
- `highest_price`/`lowest_price`: 레코드에 `high_water`/`low_water` 있으면 복원, 없으면 `Position.__post_init__`가 entry_price로 초기화.
- 매 사이클 `update_price(current)` 후 `high_water`/`low_water`를 레코드에 다시 영속.

### 4.4 청산 평가 — ThreeStageExit 재사용 + EOD 면제
청산 수학 무변경 재사용. **유일한 shared 변경 (additive, 하위호환)**:
- `ThreeStageExitConfig`에 `eod_exempt_maximize: bool = False` 추가 (+ `from_dict`/`to_dict`/docstring).
- `_check_position` EOD 블록(L388–401): stage는 L386에서 이미 계산됨 → 조건 보강:
  ```python
  if (is_trading_day_kst(now) and to_kst(now).time() >= close_time
          and not (self.config.eod_exempt_maximize and stage == PositionState.MAXIMIZE)):
      return self._create_exit_signal(reason=ExitReason.EOD_CLOSE, ...)
  ```
- **기본 False = 현 동작 보존** → orchestrator/backtest 무영향.

### 4.5 M4-X 청산 config (config-driven, 단일 stock config v1)
신규 `config/exit/stock_exit.yaml`(또는 `three_stage.yaml`의 `stock_exit:` 섹션) → `ThreeStageExitConfig.from_dict`:
```yaml
stock_exit:
  stop_loss_pct: -0.015
  breakeven_threshold_pct: 0.015
  maximize_threshold_pct: 0.03
  trailing_stop_pct: -0.03
  overshoot_threshold_pct: 0.07
  overshoot_trailing_pct: -0.015
  time_cut_minutes: 20
  eod_close_hour: 15
  eod_close_minute: 15
  eod_exempt_maximize: true     # MAXIMIZE는 EOD 면제 (no-flatten)
  enable_bear_exit: false       # v1: regime 미배선
  fee_rate: 0.003
```
**per-strategy 청산 config는 follow-up**(M4-O가 position 레코드에 `strategy` 영속 필요). v1 shadow 검증엔 단일 config로 충분.

### 4.6 포지션 키 공존 가드 (orchestrator 충돌)
M4-O/R/X는 `stock:daemon:positions`를 사용하고 dashboard-native positions key와 섞지 않는다. M4-X는 방어적으로 **`opened_at_ms` 시그니처를 가진 레코드만 처리**한다.

### 4.7 캐던스
`STOCK_EXIT_INTERVAL`초마다 스캔(기본값은 config). 포지션 변경 시 `feed.update_symbols` 갱신.

## 5. Execution · close · PnL feedback

ExitSignal당 (paper SELL, KRX, 전량 청산):
```
current = feed.get_current_price(code)
order = await broker.submit_order(symbol=code, side=OrderSide.SELL, quantity=quantity,
          price=current, order_type=OrderType.MARKET, market_price=current)
if not order.filled: log + skip (다음 사이클 재시도, HDEL 안 함)
filled = float(order.fill_price or current)
gross = (filled - entry_price) * quantity
round_trip_fee = (entry_price + filled) * quantity * (fee_rate / 2)
realized_pnl = gross - round_trip_fee
# 실행 순서: SELL → HDEL(권위적 close) → record_trade(+win/loss) → log_fill(best-effort)
await redis.hdel(positions_key, code)
await runtime_state.record_trade(pnl_krw=realized_pnl)
if realized_pnl > 0: await runtime_state.record_win()
else:                await runtime_state.record_loss()
await fill_logger.log_fill(signal_id=pos.signal_id, order_id=order.order_id, symbol=code,
      side="SELL", order_type="market", requested_price=current, filled_price=filled,
      tick_size_points=0.0, slippage_ticks=abs(filled - current), quantity=quantity,
      requested_at_ms=now_ms, filled_at_ms=now_ms, venue="KRX", trade_role="exit")
```

핵심:
- **side=SELL**(LONG 청산), **전량**(ThreeStageExit는 full-close; `signal.quantity == position.quantity`). 부분청산 v1 제외.
- **실현 PnL을 M4-X가 자체 계산**(entry_price=레코드, filled=sell, round-trip fee 차감). 교차프로세스라 VirtualBroker 내부 commission 무시(M4-X broker는 entry 미보유) → 명시적 fee 차감으로 이중계산 방지.
- **HDEL = 권위적 생명주기 종료** → M4-R `OpenPositionFilter`가 해당 code 재진입 허용 (M4-O 오픈 ↔ M4-X close 대칭). 실행 순서에서 HDEL을 PnL/fill보다 먼저 — 재처리/이중매도 방지.
- **🔑 RuntimeRiskState 피드백** = M4-X 핵심 가치: M4-R DailyMDD/Weekly/ConsecutiveLoss 필터가 비로소 활성화(현재 inert). `risk:state:stock` 공유.
- **관측성 갭**: `FillLogger.log_fill`은 고정 스키마(선물 공유) — exit_reason/realized_pnl 필드 없음. exit fill은 `trade_role=exit`로만 구분, reason/PnL은 로그 + `RuntimeRiskState` daily_pnl 누적. FillLogger 확장은 안 함(follow-up).

## 6. 플래그 · systemd · DRY

- 플래그 `STOCK_EXIT_DAEMON` = `off`(기본, inert) / `shadow` / `live`. systemd `kis-stock-exit-daemon.service` **disabled**, `Environment=STOCK_EXIT_DAEMON=shadow`, ExecStart `-m services.stock_exit.main` (M4-P/R/O 유닛 템플릿).
- Env 오버라이드: `STOCK_POSITIONS_KEY`(기본 `stock:daemon:positions`) · `STOCK_FILL_STREAM`(기본 `order.fill.stock.shadow`) · `STOCK_TICK_STREAM`(기본 `market:ticks`) · `STOCK_EXIT_INTERVAL`.
- DRY: `StreamConsumerFeed`·`ThreeStageExit`·`VirtualBroker`·`FillLogger`·`RuntimeRiskState`·`ConfigLoader` 재사용. 엔트리포인트 boilerplate는 M4-P/R/O와 동일 — `shared/streaming/daemon_entrypoint.py` 추출은 **4번째 반복**으로 근거 강화되나 여전히 deferred follow-up.

## 7. Error handling (사이클 회복성)
| 상황 | 정책 |
|------|------|
| 포지션 레코드 파싱 실패 / `opened_at_ms` 없음 | 해당 레코드 skip(orchestrator 이종 엔트리 포함), 사이클 계속 |
| 보유 code 현재가 없음(틱 미수신) | ThreeStageExit None 반환 → 청산 없음, 다음 사이클 |
| SELL 미체결 | HDEL 안 함 → 다음 사이클 재시도 |
| 실행 순서 | SELL → HDEL → record_trade(+win/loss) → log_fill(best-effort). HDEL 실패 시 PnL/fill skip + 다음 사이클 재시도(드문 paper 이중매도 수용) |
| Redis/feed 일시 오류 | 사이클 단위 catch+log+계속(데몬 생존) |
| SIGTERM/SIGINT | 루프 중단 → feed/redis close |

## 8. Testing
- **단위**: Position 재구성(high_water 복구 / 없으면 entry 초기화) · `opened_at_ms` 가드(orchestrator `entry_time` 레코드 skip) · **`eod_exempt_maximize`**(MAXIMIZE@EOD→EOD_CLOSE 없음, SURVIVAL/BREAKEVEN@EOD→EOD_CLOSE) · running-high 영속 · 청산 실행(STOP_LOSS→SELL→HDEL+record_loss+fill(trade_role=exit) / TRAILING_STOP 수익→record_win) · PnL 계산(gross−round-trip fee) · 미체결→HDEL 없음 · 플래그 off=inert.
- **통합(핵심)**: hash에 포지션 seed(M4-O 모사) + stop 유발 틱 → 데몬 사이클 → `order.fill.stock.shadow`(exit) + 포지션 HDEL + `risk:state:stock` daily_pnl 갱신. **루프 클로징 증명**: M4-X가 loss 기록 후 M4-R ConsecutiveLoss/DailyMDD 스냅샷 반영.
- **회귀**: orchestrator/backtest ThreeStageExit 무영향(`eod_exempt_maximize` 기본 False) — 기존 `tests/.../test_three_stage*` green. full `tests/` 게이트(병렬+직렬), ruff/black/mypy.

## 9. Acceptance criteria
- [ ] StockExitDaemon이 `stock:daemon:positions`(opened_at_ms 가드) 읽어 Position 재구성 + running high 추적·영속.
- [ ] `ThreeStageExit`에 하위호환 `eod_exempt_maximize` 추가; 기본 False는 orchestrator 동작 보존(기존 테스트 green).
- [ ] MAXIMIZE는 EOD 면제, SURVIVAL/BREAKEVEN은 EOD 청산.
- [ ] 청산 → paper SELL → `order.fill.stock.shadow`(trade_role=exit) + HDEL close + `RuntimeRiskState` PnL 피드백.
- [ ] close 후 재진입 재허용(M4-R OpenPositionFilter가 code 없음 확인) — e2e.
- [ ] PnL 피드백이 M4-R MDD/연속손실 활성화(`risk:state:stock` 갱신).
- [ ] default-off, systemd disabled, 실거래 없음, ClickHouse-free(parquet+SQLite), `enable_bear_exit=false`.

## 10. Open questions (구현 계획에서 확정)
- 스캔 캐던스 기본 interval 값.
- M4-X→M4-R 루프 활성화 통합테스트를 이 증분에 포함할지(권장 포함 — 핵심 가치 증명).
- fee 모델 정확도(gross−round-trip vs VirtualBroker commission 의존).
- `eod_exempt_maximize`를 `_check_position`에 인라인 vs `_check_position` 직전 stage 계산 재사용(이미 L386에서 계산됨 — 인라인 가능).
