# Phase 4 — Execution & Slippage Control (Week 5-6)

**Status:** Draft
**Parent:** `docs/plans/2026-04-20-futures-paradigm-master.md`
**Target branch:** `feat/futures-paradigm-phase4`
**Depends on:** Phase 3 완료 게이트 통과
**Blocks:** Phase 5

---

## 1. 목표

Phase 3 엔진이 생성한 `stream:signal.final`을 **페이퍼 트레이딩** 으로 실행하고, Passive Maker + OCO + 슬리피지 로깅 + Kill Switch를 갖춘 주문 파이프라인을 완성한다.

**Phase 4 완료 시:**
- 새 페이퍼 계정에서 Setup A/C 시그널이 자동 페이퍼 체결됨
- 모든 체결의 requested vs filled price가 `kospi.order_fills`에 기록됨
- 일일 MDD / 주간 MDD / 연속 손실 / API 에러율 / 파이프라인 lag 6개 조건 중 하나라도 위반 시 자동 kill switch 작동
- 기존 `rl_mppo` 운용은 계속 (다른 계정에서 병행)

**완료 정의:**
- 2주 페이퍼 연속 운영, 최소 20회 체결
- 평균 실 슬리피지 ≤ 0.4 tick (mini는 1 tick = 0.02 pt)
- Kill switch 드릴 테스트 6개 조건 모두 통과
- 백테스트 예상 PnL과 실 페이퍼 PnL 괴리 < 20%

---

## 2. 실시간 파이프라인 활성화

Phase 3까지는 in-process 호출로 백테스트 검증만 했다. Phase 4에서 **실시간 데몬 체인** 을 활성화한다.

```
news_collector ──> stream:news.raw ──> news_scorer ──> stream:news.scored
                                                            │
macro_overnight ──> stream:macro.overnight ─────────────────┤
                                                            ↓
                                              ┌─> decision_engine 데몬
                                              │    (MarketContext 재생성,
                                              │    Setup A/C check 매 1분)
                                              ↓
                                    stream:signal.candidate
                                              ↓
                                     risk_filter 데몬 (Phase 3 필터 8종)
                                              ↓
                                    stream:signal.final  ──> order_router 데몬
                                                                ↓
                                                        stream:order.request
                                                                ↓
                                                          KIS Paper Broker
                                                                ↓
                                                        stream:order.fill
                                                                ↓
                                                          kospi.order_fills
```

### 2.1 신규 데몬 (서비스)

```
services/
├── decision_engine/main.py          # MarketContext 재생성, Setup 체크 매 1분
├── risk_filter/main.py              # stream:signal.candidate consumer
├── order_router/main.py             # stream:signal.final consumer → 주문 전송
└── kill_switch/main.py              # 6개 조건 모니터 + 강제 정지
```

각 데몬은 `ServiceConfigBase` + Prometheus + systemd.

---

## 3. Passive Maker 라우터

### 3.1 기본 정책

- **시장가 주문 금지.** 모든 엔트리는 지정가.
- 매수: 최우선 매수호가(bid[0])에 걸기 (passive maker)
- 매도: 최우선 매도호가(ask[0])
- **쫓아가지 않는다** — 30초 타임아웃 후 미체결이면 취소, 시그널 포기

### 3.2 구현

기존 `shared/execution/executor.py` 확장 — 새 메서드 `place_passive_limit_futures()`. 기존 `_send_kis_futures_order()`의 시장가 경로(`ORD_DVSN_CD="02"`)는 유지(다른 호출자 보호).

```python
class OrderExecutor:
    async def place_passive_limit_futures(
        self,
        signal: Signal,
        spec: ContractSpec,
        timeout_seconds: int = 30,
    ) -> OrderResult:
        orderbook = await self.kis.get_futures_orderbook(signal.symbol)
        limit_price = orderbook.bid[0].price if signal.direction == "long" else orderbook.ask[0].price
        limit_price = self._round_to_tick(limit_price, spec.tick_size_points)

        requested_at_ms = now_ms()
        order_id = await self._send_kis_futures_order(
            symbol=signal.symbol,
            side=signal.direction,
            quantity=signal.position_size,
            order_type="limit",                # ORD_DVSN_CD="01"
            price=limit_price,
        )
        filled = await self._wait_for_fill(order_id, timeout_seconds)
        if filled is None:
            await self._cancel_order(order_id)
            return OrderResult.missed(reason="passive_not_filled")

        slippage_ticks = self._compute_slippage_ticks(
            requested=limit_price,
            filled=filled.price,
            direction=signal.direction,
            tick_size=spec.tick_size_points,
        )
        await self.fill_logger.log_fill(
            signal_id=signal.signal_id,
            order_id=order_id,
            requested=limit_price,
            filled=filled,
            slippage_ticks=slippage_ticks,
            requested_at_ms=requested_at_ms,
            order_type="limit_passive",
        )
        return OrderResult.filled(filled, slippage_ticks=slippage_ticks)
```

### 3.3 Mini 틱 처리 (Q4 확정 값 반영)

```python
def _round_to_tick(price: float, tick_size: float) -> float:
    # 부동소수 안전하게 반올림
    return round(round(price / tick_size) * tick_size, 4)

def _compute_slippage_ticks(requested, filled, direction, tick_size):
    raw = (filled - requested) / tick_size
    # long은 filled > requested면 손해(+slippage), short은 반대
    return raw if direction == "long" else -raw
```

**기존 `executor.py:803`의 `/ 0.05` 하드코딩은 F200 전용**. 미니는 `0.02` 분기 처리 — `spec.tick_size_points`로 파라미터화.

---

## 4. OCO (One-Cancels-Other) 브래킷

### 4.1 KIS API 한계

KIS 선물 OCO 네이티브 지원은 **제한적**. 다음 중 하나로 구현:
- **4-A. Server-side OCO** (KIS 브래킷 TR 있으면 사용)
- **4-B. Client-side pseudo-OCO** — 별도 stop 주문 + target 주문을 페이퍼에서 시뮬레이션, 체결 감지 시 반대 취소

**현재 코드베이스 상태:** `VirtualBroker` (`shared/paper/broker.py`)는 single 주문만 처리. Phase 4 범위에서는 **Client-side pseudo-OCO** 구현 → 페이퍼 검증 후 실계좌 전환 시 server-side 검토.

### 4.2 구현 (페이퍼 전용)

```python
class PseudoOCO:
    async def register_bracket(self, filled_entry: Fill, signal: Signal) -> OCOHandle:
        stop_order = await self.broker.place_stop_order(
            symbol=signal.symbol, side=opposite(signal.direction),
            quantity=filled_entry.quantity, trigger_price=signal.stop_loss,
        )
        target_order = await self.broker.place_limit_order(
            symbol=signal.symbol, side=opposite(signal.direction),
            quantity=filled_entry.quantity, price=signal.take_profit,
        )
        handle = OCOHandle(stop_order.id, target_order.id, signal.signal_id)
        await self._start_watcher(handle)     # 한쪽 체결 감지 → 다른쪽 취소
        # 강제 청산 타이머 (signal.valid_until) 등록
        asyncio.create_task(self._force_close_at(signal.valid_until, handle))
        return handle
```

### 4.3 Force-Close

- **시그널 만료:** `signal.valid_until` 도래 시 market close로 포지션 청산 (이 경우에만 시장가 허용)
- **세션 마감 임박:** 15:10 KST 이후 모든 오픈 포지션 강제 청산 (선물 장 마감 15:45 기준, 여유 확보)
- **Kill switch:** 즉시 시장가 청산

**시장가 사용은 위 3가지 조건에 한정.** 그 외 모든 주문은 passive.

---

## 5. 슬리피지 로깅

### 5.1 ClickHouse 테이블 (`V3__create_order_fills.sql`)

```sql
CREATE TABLE IF NOT EXISTS kospi.order_fills (
    signal_id String,
    order_id String,
    symbol LowCardinality(String),
    side LowCardinality(String),
    order_type LowCardinality(String),      -- limit_passive|limit_aggressive|stop|market
    requested_price Float64,
    filled_price Float64,
    tick_size_points Float32,               -- 계약별 (mini=0.02)
    slippage_ticks Float32,
    quantity UInt32,
    requested_at DateTime64(3, 'UTC'),
    filled_at DateTime64(3, 'UTC'),
    latency_ms UInt32,
    venue LowCardinality(String),           -- "KRX"
    trade_role LowCardinality(String),      -- "entry"|"stop_loss"|"take_profit"|"force_close"
    broker_error_code String
) ENGINE = MergeTree()
ORDER BY (filled_at, order_id)
PARTITION BY toYYYYMM(filled_at)
TTL toDateTime(filled_at) + INTERVAL 5 YEAR;
```

### 5.2 FillLogger

```python
# shared/execution/fill_logger.py
class FillLogger:
    async def log_fill(self, *, signal_id, order_id, symbol, requested, filled, ...):
        # 1. stream:order.fill XADD
        # 2. kospi.order_fills batch INSERT (10s flush)
        # 3. Prometheus histogram update
```

### 5.3 주간 Edge Review 연동

`jobs/weekly_edge_review.py` 신설 — 매주 월 05:00 KST cron. 원본 §10.2 쿼리 기반:

```sql
SELECT
  s.setup_type,
  count() AS n,
  avg(o.slippage_ticks) AS avg_slip,
  quantile(0.95)(o.slippage_ticks) AS p95_slip,
  sum(if(... realized_pnl ...)) AS pnl
FROM kospi.signals_all s
JOIN kospi.order_fills o ON s.signal_id = o.signal_id
WHERE s.generated_at >= now() - INTERVAL 7 DAY
GROUP BY s.setup_type;
```

경고:
- Setup EV 음수 → Telegram
- 평균 슬리피지 > 0.5 tick → Telegram
- Setup A/C 중 하나가 2주 연속 trades = 0 → 체크 알림

---

## 6. Kill Switch (자동 정지)

### 6.1 조건 (6개, YAML 로드)

```yaml
# config/kill_switch.yaml
kill_switch:
  enabled: true
  check_interval_seconds: 30
  force_flat_on_trigger: true
  conditions:
    daily_loss:
      enabled: true
      limit_pct: 0.03
    weekly_loss:
      enabled: true
      limit_pct: 0.07
    consecutive_losses:
      enabled: true
      threshold: 6
    api_error_rate_5min:
      enabled: true
      threshold: 0.2
    news_pipeline_lag_seconds:
      enabled: true
      threshold: 300
    clickhouse_insert_fail_rate:
      enabled: true
      threshold: 0.1
```

### 6.2 동작

```python
class KillSwitchDaemon:
    async def run(self):
        while True:
            for cond in self.conditions:
                if cond.check(self.state_snapshot):
                    await self._trigger(cond.name, cond.details)
                    return     # 데몬 종료 후 재시작은 수동
            await asyncio.sleep(self.config.check_interval_seconds)

    async def _trigger(self, reason: str, details: dict):
        # 1. stream:risk.event XADD
        # 2. order_router 데몬에 shutdown signal → 신규 주문 차단
        # 3. force-flat 모든 오픈 포지션 (시장가)
        # 4. Telegram 긴급 알림 (TELEGRAM_FUTURES_* + TELEGRAM_BRIEFING_*)
        # 5. systemd unit 정지 — 재시작 전 수동 승인 필요
```

### 6.3 재개 프로세스

- Kill switch 작동 후 **당일 재개 금지**
- `scripts/kill_switch_clear.sh` 수동 실행 + 사용자 확인 플래그 필요
- Telegram에 원인 로그 + 클리어 커맨드 안내

### 6.4 드릴 테스트

`tests/integration/test_kill_switch_drill.py` — 6개 조건을 각각 수동 트리거해 force-flat + alert + systemd stop이 모두 동작하는지 검증. CI에서 실행.

---

## 7. 모니터링

### 7.1 Prometheus 메트릭 (신규)

```
order_placed_total{setup, order_type}                Counter
order_filled_total{setup, order_type, venue}         Counter
order_missed_total{setup, reason}                    Counter
order_slippage_ticks{setup}                          Histogram (buckets: 0, 0.1, 0.2, 0.5, 1, 2, 5)
order_latency_ms{setup, stage}                       Histogram (stage: request, fill)
kill_switch_triggered_total{reason}                  Counter
kill_switch_condition_value{name}                    Gauge
risk_state_daily_pnl_krw                             Gauge
risk_state_weekly_pnl_krw                            Gauge
```

### 7.2 Grafana 대시보드 (`futures-execution`)

- 실시간 PnL 곡선 (당일, 주간)
- 시그널 발생 vs 체결 비율 (fill rate)
- 슬리피지 distribution (히스토그램)
- Kill switch 조건 현황 (6개 조건 게이지, 임계값 대비)
- KIS API 에러율 + 파이프라인 lag

---

## 8. 기존 시스템 영향

| 기존 컴포넌트 | Phase 4 상호작용 |
|--------------|-----------------|
| `TradingOrchestrator` | 직접 수정 없음 — 신 파이프라인은 별도 데몬으로 구동 |
| `rl_mppo` paper | 별도 계정에서 계속 운용, 동일 계약 동시 진입 금지 (`risk_filter`에서 symbol lock 추가) |
| `shared/execution/executor.py` | `place_passive_limit_futures()` 신규 메서드 추가, 기존 경로 보호 |
| `shared/paper/broker.py` | pseudo-OCO 지원 위해 stop 주문 시뮬레이션 추가 |
| `shared/risk/manager.py` | `RiskFilterLayer`(Phase 3)와 중복되는 부분 정리, 기존 manager는 주식 전용으로 명시 |

---

## 9. Phase 4 완료 게이트

- [ ] 4개 신규 데몬(decision_engine, risk_filter, order_router, kill_switch) 2주 연속 가동
- [ ] `V3__create_order_fills.sql` 적용
- [ ] 최소 20회 체결 누적
- [ ] 평균 슬리피지 ≤ 0.4 tick
- [ ] Kill switch 드릴 테스트 6개 조건 통과
- [ ] Weekly Edge Review 1회 실행, 리포트 확인
- [ ] 백테스트 PnL vs 실 페이퍼 PnL 괴리 < 20% (Setup A + C 합산)
- [ ] `rl_mppo` 운용 영향 없음 (독립 계정 확인)
- [ ] Grafana `futures-execution` 대시보드 구축
- [ ] 종합 failure mode 문서화 (`docs/runbooks/futures-paradigm-failure-modes.md`)

---

## 10. 명시적 비범위

- 실계좌 소액 실전 (Phase 5)
- Server-side OCO (페이퍼 검증 이후 실계좌 전환 시 검토)
- 다계약 포지션 (Phase 5 이후, 먼저 1계약 검증)
- ATS 라우팅 (선물 미지원)
- RL 보조 필터 편입 (RL spec)
