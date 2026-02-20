# Broker Position Verification — Design Document

**Date**: 2026-02-21
**Status**: Draft
**Author**: Claude (brainstorming session)
**Depends on**: [2026-02-20-position-recovery-design.md](2026-02-20-position-recovery-design.md)

---

## 1. Problem Statement

현재 시스템은 Redis를 포지션의 유일한 복구 소스로 사용합니다.
Redis 기반 복구는 잘 동작하지만, **브로커(KIS) 실제 잔고와의 교차 검증이 없습니다.**

### 위험 시나리오

| 시나리오 | 결과 | 현재 대응 |
|----------|------|----------|
| 주문 전송 후 응답 수신 전 크래시 | 브로커에 포지션 존재, Redis에 없음 | **미감지** — 고아 포지션 |
| Redis 데이터 손상 | 잘못된 수량/가격으로 복구 | **미감지** — 오류 청산 |
| 수동 매매 (HTS/MTS) | 브로커에 포지션 존재, 시스템 미인지 | **미감지** — EOD 미청산 |
| 부분 체결 후 크래시 | 브로커 체결 수량 ≠ Redis 수량 | **미감지** — 수량 불일치 |
| 실전 전환 시 모의 포지션 잔존 | 실전/모의 포지션 혼동 | **미감지** |

### 목표

프로세스 시작 시 **Redis 포지션 ↔ 브로커 실제 잔고를 비교**하여:
1. Redis에만 있는 포지션 → 경고 (브로커에서 청산됨?)
2. 브로커에만 있는 포지션 → 경고 + 자동 추적 옵션
3. 수량/가격 불일치 → 브로커 기준으로 보정

---

## 2. KIS API Endpoints

### 주식 잔고조회

| 항목 | 값 |
|------|-----|
| TR ID | `TTTC8434R` |
| Endpoint | `/uapi/domestic-stock/v1/trading/inquire-balance` |
| Method | GET |
| 실전/모의 | 모두 지원 |
| 인증 | `KIS_STOCK_APP_KEY` / `KIS_STOCK_APP_SECRET` |

**주요 응답 필드:**
- `pdno` — 종목코드
- `prdt_name` — 종목명
- `hldg_qty` — 보유수량
- `pchs_avg_pric` — 매입평균가
- `evlu_pfls_amt` — 평가손익
- `sll_rslt_qty` — 매도 체결 수량 (당일)

### 선물옵션 잔고조회

| 항목 | 값 |
|------|-----|
| TR ID | `CTFO6118R` |
| Endpoint | `/uapi/domestic-futureoption/v1/trading/inquire-balance` |
| Method | GET |
| 실전/모의 | 실전만 (KIS 모의서버 선물 미지원) |
| 인증 | `KIS_FUTURES_APP_KEY` / `KIS_FUTURES_APP_SECRET` |

**주요 응답 필드:**
- `pdno` — 종목코드
- `prdt_name` — 종목명
- `cblc_qty` — 잔고수량
- `pchs_avg_pric` — 매입평균가
- `sll_buy_dvsn_cd` — 매도매수구분 (01=매도, 02=매수)
- `evlu_pfls_amt` — 평가손익

### 야간 선물옵션 잔고조회

| 항목 | 값 |
|------|-----|
| TR ID | `CTFN6118R` |
| Endpoint | `/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance` |
| Method | GET |
| 용도 | 야간 세션 포지션 확인 (참고용) |

---

## 3. Architecture

### 실행 시점

```
Orchestrator Startup
    ↓
_recover_positions_from_redis()      ← 기존 (Redis 복구)
    ↓
_verify_positions_with_broker()      ← 신규 (브로커 검증)
    ↓
  ├─ Match: Redis ∩ Broker → 정상, 수량/가격 보정
  ├─ Redis only: Redis - Broker → 경고 (고아 포지션)
  └─ Broker only: Broker - Redis → 경고 + 자동 추적 옵션
    ↓
Trading Loop Start
```

### 모듈 구조

```
shared/kis/
├── client.py                 # 기존 KIS REST 클라이언트
│   ├── get_stock_balance()   # 신규: 주식 잔고조회
│   └── get_futures_balance() # 신규: 선물옵션 잔고조회
│
services/trading/
├── orchestrator.py
│   └── _verify_positions_with_broker()  # 신규: 브로커 검증 로직
│
shared/models/
├── broker_position.py        # 신규: 브로커 잔고 데이터 모델
```

---

## 4. Implementation Plan

### 4.1 BrokerPosition 모델 (`shared/models/broker_position.py`)

```python
@dataclass
class BrokerPosition:
    """KIS 브로커에서 조회한 실제 잔고."""
    code: str
    name: str
    side: PositionSide  # LONG or SHORT
    quantity: int
    avg_price: float
    current_price: float
    unrealized_pnl: float
    source: str = "broker"  # "broker" or "redis"
```

### 4.2 KIS 잔고조회 (`shared/kis/client.py`)

```python
async def get_stock_balance(self) -> list[BrokerPosition]:
    """주식 잔고조회 (TTTC8434R)."""
    url = f"{self._base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
    headers = {
        "tr_id": "TTTC8434R",
        "authorization": f"Bearer {self._token}",
        "appkey": self._app_key,
        "appsecret": self._app_secret,
    }
    params = {
        "CANO": self._account_no[:8],
        "ACNT_PRDT_CD": self._account_no[8:],
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "01",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    # ... 페이지네이션 + BrokerPosition 변환

async def get_futures_balance(self) -> list[BrokerPosition]:
    """선물옵션 잔고조회 (CTFO6118R).

    NOTE: 모의서버 미지원. is_real=True 필수.
    """
    url = f"{self._base_url}/uapi/domestic-futureoption/v1/trading/inquire-balance"
    headers = {
        "tr_id": "CTFO6118R",
        # ...
    }
    # ... 페이지네이션 + BrokerPosition 변환
```

### 4.3 브로커 검증 로직 (`services/trading/orchestrator.py`)

```python
async def _verify_positions_with_broker(self) -> None:
    """Redis 복구 포지션과 브로커 실제 잔고 비교.

    Paper 모드에서는 건너뛰기 (브로커 잔고 = 가상).
    """
    if self.config.paper_mode:
        logger.info("Paper mode: skipping broker position verification")
        return

    try:
        if self.config.asset_class == "stock":
            broker_positions = await self._kis_client.get_stock_balance()
        else:
            broker_positions = await self._kis_client.get_futures_balance()
    except Exception as e:
        logger.warning(f"Broker balance inquiry failed: {e}")
        return  # 실패 시 Redis 복구 결과만 사용

    redis_positions = {p.code: p for p in self._position_tracker.positions}
    broker_map = {p.code: p for p in broker_positions}

    # 1. Match: 양쪽 모두 존재
    for code in set(redis_positions) & set(broker_map):
        redis_pos = redis_positions[code]
        broker_pos = broker_map[code]

        # 수량 불일치 → 브로커 기준 보정
        if redis_pos.quantity != broker_pos.quantity:
            logger.warning(
                f"[{code}] Quantity mismatch: Redis={redis_pos.quantity}, "
                f"Broker={broker_pos.quantity}. Using broker value."
            )
            redis_pos.quantity = broker_pos.quantity

        # 방향 불일치 → 심각한 오류
        if redis_pos.side != broker_pos.side:
            logger.error(
                f"[{code}] SIDE MISMATCH: Redis={redis_pos.side}, "
                f"Broker={broker_pos.side}. Manual intervention required!"
            )
            # Telegram 알림
            await self._notify(
                f"⚠️ POSITION SIDE MISMATCH\n"
                f"{code}: Redis={redis_pos.side.value}, Broker={broker_pos.side.value}\n"
                f"Manual review required!"
            )

    # 2. Redis only: 브로커에서 이미 청산된 포지션
    redis_only = set(redis_positions) - set(broker_map)
    for code in redis_only:
        pos = redis_positions[code]
        logger.warning(
            f"[{code}] Orphan in Redis (not in broker). "
            f"May have been closed externally. Removing."
        )
        self._position_tracker.close_position(
            pos.id, pos.current_price, reason="BROKER_RECONCILIATION"
        )

    # 3. Broker only: 시스템 외부에서 생성된 포지션
    broker_only = set(broker_map) - set(redis_positions)
    for code in broker_only:
        bp = broker_map[code]
        logger.warning(
            f"[{code}] Found in broker but not in Redis. "
            f"qty={bp.quantity}, price={bp.avg_price}. "
            f"Auto-tracking enabled."
        )
        # 자동 추적 (선택적 — config으로 제어)
        if self.config.auto_track_broker_positions:
            # Position 생성 + PositionTracker에 추가
            ...
        else:
            await self._notify(
                f"⚠️ Untracked broker position: {code}\n"
                f"Qty: {bp.quantity}, Price: {bp.avg_price:,.0f}\n"
                f"Not managed by system."
            )
```

---

## 5. Paper Trading 고려사항

Paper 모드(모의투자)에서의 포지션 검증:

| 모드 | 주식 | 선물 |
|------|------|------|
| **Paper** | KIS 모의서버 잔고조회 가능 (VTTC8434R) | KIS 모의서버 선물 미지원 → 건너뛰기 |
| **Real** | KIS 실전서버 잔고조회 (TTTC8434R) | KIS 실전서버 잔고조회 (CTFO6118R) |

### Paper 주식의 경우

모의투자 TR ID는 `VTTC8434R` (실전: `TTTC8434R`).
현재 시스템은 `KIS_STOCK_MARKET=mock`일 때 모의서버 URL을 사용하므로,
같은 코드에서 TR ID만 분기하면 됩니다.

### Paper 선물의 경우

**KIS 모의서버는 선물을 지원하지 않습니다.**
선물 paper 모드에서는 브로커 검증을 건너뛰고 Redis만 사용합니다.

---

## 6. Configuration

```yaml
# config/execution.yaml
position_recovery:
  enabled: true
  max_position_age_days: 7
  clean_stale_on_startup: true

  # 브로커 검증 (실전 전환 시 활성화)
  broker_verification:
    enabled: false             # 기본 비활성 (paper 운용 중)
    auto_track_external: false # 외부 포지션 자동 추적 여부
    reconcile_quantity: true   # 수량 불일치 시 브로커 기준 보정
    notify_on_mismatch: true   # 불일치 시 Telegram 알림
```

---

## 7. File Changes

| # | 파일 | 변경 | 난이도 |
|---|------|------|--------|
| 1 | `shared/models/broker_position.py` | 신규: BrokerPosition dataclass | Low |
| 2 | `shared/kis/client.py` | `get_stock_balance()`, `get_futures_balance()` 추가 | Medium |
| 3 | `services/trading/orchestrator.py` | `_verify_positions_with_broker()` 메서드 추가 | Medium |
| 4 | `config/execution.yaml` | `broker_verification` 설정 블록 추가 | Low |
| 5 | `tests/unit/trading/test_broker_verification.py` | 유닛 테스트 | Medium |

### 변경하지 않는 파일

- `shared/streaming/trading_state.py` — 이미 완성
- `services/trading/position_tracker.py` — 이미 `add_recovered_position()` 있음
- `shared/backtest/` — 백테스트와 무관

---

## 8. Implementation Priority

### Phase 1: 현재 상태 유지 (이미 완료)
- Redis 기반 포지션 복구 ✅
- Clean shutdown flush ✅
- Freshness 필터 ✅
- 17개 유닛 테스트 ✅

### Phase 2: 브로커 검증 (이 문서)
- KIS 잔고조회 API 구현
- 포지션 비교/보정 로직
- Telegram 알림 연동
- **실전 전환 시 필수**

### Phase 3: 추가 안전장치 (향후)
- 주기적 브로커 검증 (매 30분마다 잔고 비교)
- 주문 체결 확인 (주문 후 잔고 변동 검증)
- ClickHouse 감사 트레일과 Redis 교차 검증

---

## 9. Risk Assessment

| 리스크 | 확률 | 영향 | 완화 |
|--------|------|------|------|
| KIS API rate limit (5 req/s) | Medium | 시작 지연 | 기존 `_RateLimiter` 사용 |
| 잔고조회 실패 | Low | 검증 건너뛰기 | Redis 복구만 사용 (fallback) |
| 선물 모의서버 미지원 | Certain | 검증 불가 | Paper 모드에서 건너뛰기 |
| 자동 보정 오류 | Low | 잘못된 수량 | 브로커 기준 사용 + 알림 |
| 외부 포지션 자동 추적 | Medium | 의도치 않은 관리 | `auto_track_external: false` 기본값 |

---

## 10. 현재 상태 요약

### 이미 구현됨 (2026-02-20)

| 기능 | 상태 |
|------|------|
| Redis 포지션 저장 (실시간) | ✅ TradingStatePublisher |
| Redis 포지션 복구 (재시작) | ✅ _recover_positions_from_redis() |
| Clean shutdown flush | ✅ stop() 메서드, throttle=0 |
| EOD intraday 강제 청산 | ✅ _close_intraday_positions() |
| Freshness 필터 (intraday/swing) | ✅ 전략별 분류 |
| Enhanced Redis 스키마 | ✅ highest_price, stop_price 등 |
| 유닛 테스트 17개 | ✅ test_position_recovery.py |
| Redis AOF 영속성 | ✅ appendonly yes |
| WebSocket 자동 재구독 | ✅ 복구 심볼 → config.symbols |

### 미구현 (이 문서의 범위)

| 기능 | 우선순위 |
|------|----------|
| KIS 주식 잔고조회 API | Phase 2 |
| KIS 선물 잔고조회 API | Phase 2 |
| Redis ↔ 브로커 비교/보정 | Phase 2 |
| 불일치 Telegram 알림 | Phase 2 |
| 주기적 브로커 검증 | Phase 3 |
| 주문 체결 확인 | Phase 3 |

---

## 11. Decision Summary

**현재 Redis 기반 복구 시스템은 paper 운용에 충분합니다.**

브로커 검증(Phase 2)은 **실전 전환 시 구현**이 적절합니다:
- Paper 모드에서는 브로커 잔고 = 시스템이 관리하는 가상 잔고이므로 불일치 발생 확률 극히 낮음
- 선물 모의서버가 잔고조회를 지원하지 않아 현재 검증 불가
- 구현 비용 대비 paper 모드에서의 효용이 낮음

**Phase 2 trigger**: `KIS_STOCK_MARKET=real` 또는 `KIS_FUTURES_MARKET=real`로 전환 시.
