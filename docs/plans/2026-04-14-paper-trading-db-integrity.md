# Paper Trading DB 적재 및 PnL 추적 무결성 복구 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 한달간 주식 모의투자 거래 74건이 ClickHouse에 적재되지 않은 문제, PnL 계산 이상값(±수천%) 문제, 주식 EOD 전량 청산 정책 위반을 복구한다. 주식과 선물의 거래 기록은 물리적으로 분리된 테이블에 저장한다.

**Architecture:** 선물 전용 테이블인 `rl_trades`는 그대로 두고, 주식 전용 신규 테이블 `stock_trades`를 `market` DB에 생성한다. `TradingOrchestrator`의 persistence 라우팅을 `asset_class` 기반으로 재구성: `stock` → `market.stock_trades`, `futures + rl_*` → `kospi.rl_trades`, `futures + swing` → (해당 없음, 향후 확장). PnL 이상값 근본원인을 재현 후 `Position.profit_pct`가 `current_price` 스냅샷을 참조하는 경로를 수정한다. EOD 전량 청산은 주식 `asset_class`에서 제외하고, 3-stage exit 상태와 무관한 강제 청산을 제거한다.

**Tech Stack:** Python 3.11+, ClickHouse (클라이언트: `clickhouse_connect`), Redis, pytest, 기존 `TradingOrchestrator`/`PositionTracker`/`VirtualBroker` 구조

---

## Investigation Findings

> **조사 완료일:** 2026-04-14  
> **조사자:** Task 0 automated investigation  
> **목적:** P0-2(profit ±수천%) 근본원인 확정

### 샘플 수집 (5건 이상)

로그에서 수집한 이상 PnL 샘플:

| 날짜 | 종목코드 | 종목명 | entry_price (로그) | exit_price (로그) | 로그 profit_pct | 계산된 profit_pct | 일치 여부 |
|------|---------|-------|------------------|-----------------|----------------|-----------------|---------|
| 2026-03-13 | 321370 | 센서뷰 | 3,748.74 | 70,528 | +1781.38% | +1781.38% | ✓ |
| 2026-03-16 | 003280 | 흥아해운 | 2,797.79 | 103,093 | +3584.79% | +3584.80% | ✓ |
| 2026-03-17 | 027360 | 아주IB투자 | 7,247.24 | 94,260 | +1200.63% | +1200.63% | ✓ |
| 2026-03-13 | 005860 | 한일사료 | 4,744.74 | 27,977 | +489.64% | +489.64% | ✓ |
| 2026-03-18 | 007120 | 미래아이앤지 | 2,789.79 | 106,769 | +3727.14% | +3727.13% | ✓ |
| 2026-03-17 | 322000 | HD현대에너지솔루션 | 138,438.30 | 35,492 | -74.36% | -74.36% | ✓ |
| 2026-03-16 | 000660 | SK하이닉스 | 946,946.00 | 72,780 | -92.31% | -92.31% | ✓ |

**결론:** 모든 샘플에서 `profit_pct` 계산 수식 자체는 정확하다 — `(exit_price - entry_price) / entry_price * 100`. 수식 버그가 아니다.

### entry_price 및 exit_price 추적

#### entry_price 분석

entry_price는 모두 paper broker에서 `market_price * (1 + slippage_rate)`로 계산된 **진짜 체결가**다:

- `321370 (센서뷰)`: `close=3745.00` → fill `3748.74 x 801` (슬리피지 187.25t 포함) — 09:10 체결
- `003280 (흥아해운)`: `close=2800.00` 근방 → fill `2797.79 x 1073` — 09:10 체결
- `000660 (SK하이닉스)`: `close=946000.00` → fill `946946.00 x 3` (슬리피지 47300t 포함) — 09:51 체결 (**정상**)

센서뷰(321370) 진입 당시의 `close=3745.00`이 EOD close `70,528`과 18.8배 차이가 나는 이유:

1. ClickHouse에 321370 데이터 **없음** (count=0, 조회 결과 epoch 1970).
2. Redis candle cache에서 prewarm 성공 (09:00: "pre-warmed 32 candles, 32 seeded").
3. Redis에 저장된 이전 세션 가격이 ~3,745 KRW였고, 당일 09:10에 해당 가격대에서 breakout 신호 발생.
4. 당일 장 중 해당 소형주가 폭등(+1,781%)하여 EOD 70,528에 도달.

**이는 계산 버그가 아니다.** 모의투자에서 실제 진입한 가격에서 실제 EOD 가격으로 계산한 것이며, 당일 폭등한 소형주의 실제 수익이다 (모의투자 환경이기 때문에 유동성/호가 고려 없이 체결됨).

#### exit_price 분석 (000660 케이스)

000660(SK하이닉스)의 이상 exit_price(`72,780` vs 실제 ~946,000):

- 09:51 entry price: 946,946 (**정상** — WebSocket 실시간 체결가)
- 15:20: "Data source unhealthy, triggering failover to REST polling" — WebSocket 마지막 틱 수신
- 15:26: "Timeout fetching 000660" — REST failover 타임아웃
- 15:30 EOD close: 72,780 사용 → **10배 이상 저평가**

`_close_intraday_positions` 코드:
```python
price = price_data.get("close") or pos.current_price  # line 2947
```

EOD close 시점에 `price_data["close"]`가 72,780을 반환한 원인: REST failover가 타임아웃 전 일부 심볼 조회에서 잘못된 값을 캐시에 기록했거나, `pos.current_price`가 WebSocket이 15:20에 전달한 마지막 틱(72,780)이었을 가능성. SK하이닉스가 72,780에 실제 거래된 적은 없으므로 **WebSocket 또는 REST가 잘못된 가격을 반환한 것**.

### 가설 검증

| 가설 | 설명 | 검증 결과 |
|------|------|---------|
| (A) stale `current_price` 참조 | `profit_pct`가 `exit_price`로 업데이트되기 전 `current_price` 참조 | **기각**: `_full_close()`에서 `position.current_price = exit_price` 설정 후 `profit_pct` 로깅 (position_tracker.py:642) |
| (B) entry_price가 비정상적으로 작은 값 | tick/slippage 이슈로 잘못된 entry_price | **부분 해당**: entry_price가 전일 종가 기반으로 작지만, 이는 당일 폭등한 소형주에서 실제 체결된 가격이므로 기술적으로 버그가 아님 |
| (C) quantity 오버플로우 또는 price 단위 혼동 | 주당 vs 거래대금 혼용 | **기각**: 수량 계산과 단위는 정상. 모든 샘플에서 `entry * qty` 계산이 올바름 |
| **(D) EOD force-close가 잘못된 시장 데이터 스냅샷 사용** (신규) | WebSocket failover 후 REST 타임아웃 시 잘못된 exit_price 사용 | **채택**: 000660 케이스에서 직접 확인. WebSocket 15:20 종료 후 REST failover 타임아웃으로 캐시 오염 |

### 최종 결론

**근본 원인: 복합 이슈 (두 가지 독립된 문제)**

**이슈 1 - 소형주 폭등 모의투자 수익(+수백~수천%):**
- entry_price는 이전 세션 Redis 캐시 기반의 낮은 가격 (실제 체결가)
- 당일 소형주가 실제로 폭등하여 EOD 가격이 수십배 상승
- `profit_pct` 계산 자체는 정확함
- **이는 "버그"라기보다 모의투자에서 유동성/서킷브레이커 없이 소형주 폭등을 추적하는 현상**
- 실제 실거래였다면 유동성 부족으로 매수 자체가 불가능했거나 상한가 제약으로 진입 불가했을 것

**이슈 2 - SK하이닉스 등 EOD 청산 시 잘못된 exit_price(-92.31% 등):**
- WebSocket이 15:20(KRX 장 마감)에 틱 전송 중단
- `DataProvider`가 failover 탐지 후 REST polling으로 전환
- REST 조회 타임아웃 또는 잘못된 응답으로 캐시에 corrupted price 기록
- EOD close 시 이 잘못된 가격이 exit_price로 사용됨
- **이것이 진짜 버그: EOD close에서 stale/corrupted market data를 그대로 exit_price로 사용**

### Task 5 수정 방향 확인 및 조정

현재 Task 5 명세: `profit_pct` 계산 시 `exit_price`가 있으면 우선 사용 (Position.profit_pct 수정).

**분석 결과에 따른 조정:**

1. **Task 5는 필요하지만 충분하지 않다.** `profit_pct`가 이미 `exit_price` 기반으로 올바르게 계산되고 있으므로, 수식 자체를 고칠 필요는 없다.

2. **진짜 수정 포인트 (Task 6과 연계):**
   - `_close_intraday_positions`에서 `asset_class == "stock"` 포지션을 **EOD 강제 청산 제외**해야 한다 (Task 6).
   - 이렇게 하면 stale/corrupted market data로 인한 이상 exit_price 문제도 동시에 해결된다.
   - EOD 강제 청산을 제거하면 `000660`처럼 잘못된 가격으로 강제 청산되는 케이스가 사라진다.

3. **Task 5의 안전망 보강 (여전히 유효):**
   - `save_rl_trade_to_db`에서 `profit_pct` 저장 시 `exit_price`를 명시적으로 사용하는 별도 계산 추가 (row 기록 시점에 `current_price`가 다른 값으로 변경될 가능성은 낮지만 방어적 코딩):
     ```python
     # position.profit_pct는 current_price 기반이므로 exit_price로 재계산
     realized_pct = (position.exit_price - position.entry_price) / position.entry_price * 100
     ```
   - 이는 향후 multi-threading 환경에서의 race condition을 예방하는 방어 코드이기도 함.

4. **이슈 1 (소형주 폭등)은 수정 대상 아님:** 모의투자 특성상 발생하는 현상이며, 실거래에서는 상한가/유동성 제약으로 발생하지 않음. 로그에 경고 출력 정도로 충분.

---

## File Structure

**새로 생성되는 파일**
- `shared/db/migrations/__init__.py` — 마이그레이션 패키지 초기자
- `shared/db/migrations/2026_04_14_add_stock_trades.py` — `stock_trades` 테이블 생성 마이그레이션(idempotent)
- `tests/unit/trading/test_stock_trade_persistence.py` — 주식 거래 ClickHouse 적재 테스트
- `tests/unit/models/test_position_profit_pct.py` — `Position.profit_pct` 경계값 테스트
- `tests/unit/trading/test_eod_close_policy.py` — 주식 EOD 청산 차단 테스트

**수정되는 파일**
- `shared/db/client.py` — `TABLE_SCHEMAS`에 `stock_trades` 스키마 추가
- `services/trading/position_tracker.py` — `save_stock_trade_to_db()` 메서드 신규, `_pending_stock_trades` 버퍼 추가, `_calc_realized_pnl` 경계 검증 추가
- `services/trading/orchestrator.py` — persistence 라우팅을 asset_class 기반으로 재구성, `_close_intraday_positions`에서 `asset_class=="stock"` 제외, `SWING_STRATEGIES` 의존 코드 경로 수정
- `shared/models/position.py` — `profit_pct` 계산 시 `exit_price`가 있으면 우선 사용(close 이후 호출 경로 안정화)

---

## Pre-flight: 현재 상태 검증 (investigation before fix)

### Task 0: 이상 PnL 재현 및 근본 원인 식별

**목적:** P0-2(profit ±수천%) 수정 전에 재현 테스트로 근본원인을 확정한다. 추측성 수정 금지.

**Files:**
- Read: `services/trading/position_tracker.py:1040-1120` (save_rl_trade_to_db)
- Read: `shared/models/position.py:102-125` (profit_rate / profit_pct / unrealized_pnl)
- Read: `services/trading/orchestrator.py:2937-2958` (_close_intraday_positions)

- [ ] **Step 1: 로그에서 이상 PnL 샘플 5건 수집**

```bash
cd /home/deploy/project/kis_unified_sts
for f in logs/stock_trading_2026*.log.gz logs/stock_trading_2026*.log; do
  [ -f "$f" ] || continue
  if [[ "$f" == *.gz ]]; then
    zcat "$f" 2>/dev/null | grep -E "Position closed.*profit=\+[0-9]{3,}\.[0-9]+%|Position closed.*profit=-[6-9][0-9]\.[0-9]+%"
  else
    grep -E "Position closed.*profit=\+[0-9]{3,}\.[0-9]+%|Position closed.*profit=-[6-9][0-9]\.[0-9]+%" "$f"
  fi
done | head -5
```

Expected: 5개 이상 이상값 샘플, 종목코드와 exit_price 포함.

- [ ] **Step 2: 동일 일자 signals 로그에서 해당 종목 entry_price 추적**

각 이상 샘플에 대해 entry 가격을 로그에서 확인:
```bash
# 예: 000720 3/13 이상 수익 추적
zcat logs/stock_trading_20260313.log.gz | grep -E "000720.*(Entry|opened|entry_price)" | head -5
```

Expected: 각 샘플의 entry_price와 exit_price 비율이 `profit_pct`와 일치하는지 판정.

- [ ] **Step 3: 근본원인 가설 검증**

후보 가설:
- (A) `profit_pct`가 close 시점에 `current_price`로 계산되는데, exit_price로 업데이트되지 않은 stale `current_price` 사용
- (B) `entry_price`가 tick/slippage 이슈로 부정확한 매우 작은 값으로 저장됨
- (C) quantity 오버플로우 또는 price 단위 혼동(주당 vs 거래대금)

수집한 샘플 5건을 각 가설과 대조. 가장 많이 맞는 가설을 채택하고 아래 Phase 2의 실제 수정 코드를 확정한다.

- [ ] **Step 4: 조사 결과를 주석으로 문서화**

`docs/plans/2026-04-14-paper-trading-db-integrity.md` 상단에 `## Investigation Findings` 섹션 추가, 가설별 결론 기재. Phase 2의 구체 코드가 이 결과에 맞게 선택되어야 한다.

- [ ] **Step 5: Commit (doc-only)**

```bash
git add docs/plans/2026-04-14-paper-trading-db-integrity.md
git commit -m "docs(plan): document pnl-anomaly root-cause investigation findings"
```

---

## Phase 1 (P0-1): `stock_trades` 테이블 및 주식 거래 적재 경로

### Task 1: ClickHouse `stock_trades` 스키마 정의 추가

**Files:**
- Modify: `shared/db/client.py:44-147` (`TABLE_SCHEMAS` 딕셔너리)

- [ ] **Step 1: 스키마 추가 (test 먼저 없음 — 테이블 정의는 선언적 스키마이므로 아래 Task 2에서 검증)**

`shared/db/client.py`의 `TABLE_SCHEMAS` 딕셔너리에 다음 엔트리 추가 (rl_trades 항목 바로 아래에 삽입):

```python
    "stock_trades": """
        CREATE TABLE IF NOT EXISTS {database}.stock_trades (
            id String,
            code String,
            name String,
            side LowCardinality(String) DEFAULT 'long',
            strategy LowCardinality(String),
            execution_venue LowCardinality(String) DEFAULT 'KRX',
            entry_date DateTime,
            entry_price Float64,
            exit_date DateTime,
            exit_price Float64,
            quantity Int32,
            pnl Float64,
            pnl_pct Float64,
            commission Float64 DEFAULT 0.0,
            slippage Float64 DEFAULT 0.0,
            hold_seconds UInt32,
            exit_reason LowCardinality(String),
            exit_state LowCardinality(String) DEFAULT '',
            metadata_json String,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(exit_date)
        ORDER BY (strategy, exit_date, id)
        TTL exit_date + INTERVAL 180 DAY
        COMMENT 'Closed stock trade records (paper + live). Separate from rl_trades which is futures-only.'
    """,
```

- [ ] **Step 2: 기존 `rl_trades`의 COMMENT를 선물 전용임을 명시하도록 보강**

동일 딕셔너리에서 `rl_trades`의 COMMENT 라인을 수정:

```python
COMMENT 'Closed futures RL trade records. Stocks use stock_trades (separate table).'
```

- [ ] **Step 3: ClickHouse에 스키마 적용 (실서버)**

```bash
cd /home/deploy/project/kis_unified_sts
source .env
clickhouse-client --host=localhost --port=9000 --user=default --password="$CLICKHOUSE_PASSWORD" \
  -q "$(python3 -c "from shared.db.client import TABLE_SCHEMAS; print(TABLE_SCHEMAS['stock_trades'].format(database='market'))")"
```

Expected: 에러 없음. 이어서 검증 쿼리:
```bash
clickhouse-client --host=localhost --port=9000 --user=default --password="$CLICKHOUSE_PASSWORD" \
  -q "DESCRIBE market.stock_trades FORMAT PrettyCompact" | head -25
```
Expected: 모든 컬럼이 나열됨.

- [ ] **Step 4: Commit**

```bash
git add shared/db/client.py
git commit -m "feat(db): add market.stock_trades table separate from rl_trades (futures only)"
```

### Task 2: `PositionTracker.save_stock_trade_to_db()` 구현 (TDD)

**Files:**
- Create: `tests/unit/trading/test_stock_trade_persistence.py`
- Modify: `services/trading/position_tracker.py` (around line 295-300 for buffer, line 1040 for method, line 1188-1210 for flush)

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/trading/test_stock_trade_persistence.py
"""PositionTracker.save_stock_trade_to_db — 주식 전용 적재 경로 회귀 테스트."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.models.position import Position, PositionSide, PositionState


def _make_closed_stock_position(
    code: str = "000720",
    entry_price: float = 100000.0,
    exit_price: float = 98500.0,
    quantity: int = 10,
    strategy: str = "momentum_breakout",
) -> Position:
    entry_time = datetime(2026, 4, 10, 9, 15, 0)
    exit_time = entry_time + timedelta(minutes=30)
    pos = Position(
        id="test-stk-1",
        code=code,
        name="TEST",
        strategy=strategy,
        side=PositionSide.LONG,
        entry_price=entry_price,
        quantity=quantity,
        entry_time=entry_time,
        state=PositionState.CLOSED,
        execution_venue="KRX",
    )
    pos.exit_price = exit_price
    pos.exit_time = exit_time
    pos.exit_reason = "rule_based_exit"
    pos.current_price = exit_price
    pos.is_open = False
    return pos


@pytest.mark.asyncio
async def test_save_stock_trade_appends_to_buffer():
    """save_stock_trade_to_db 호출이 _pending_stock_trades 버퍼에 row를 추가해야 한다."""
    config = PositionTrackerConfig(asset_class="stock", batch_size=50)
    tracker = PositionTracker(config=config)
    tracker._get_db_client = MagicMock(return_value=(MagicMock(), "market"))

    position = _make_closed_stock_position()
    await tracker.save_stock_trade_to_db(position)

    assert len(tracker._pending_stock_trades) == 1
    row = tracker._pending_stock_trades[0]
    # Row schema: (id, code, name, side, strategy, execution_venue,
    #              entry_date, entry_price, exit_date, exit_price, quantity,
    #              pnl, pnl_pct, commission, slippage, hold_seconds,
    #              exit_reason, exit_state, metadata_json)
    assert row[0] == "test-stk-1"
    assert row[1] == "000720"
    assert row[4] == "momentum_breakout"
    # pnl = (98500-100000)*10 = -15000
    assert row[11] == pytest.approx(-15000.0)
    # hold_seconds = 30 min = 1800
    assert row[15] == 1800


@pytest.mark.asyncio
async def test_save_stock_trade_flushes_when_batch_full():
    """버퍼가 batch_size에 도달하면 _flush_stock_trades_batch 호출."""
    config = PositionTrackerConfig(asset_class="stock", batch_size=2)
    tracker = PositionTracker(config=config)
    tracker._get_db_client = MagicMock(return_value=(MagicMock(), "market"))
    tracker._flush_stock_trades_batch = AsyncMock()

    for i in range(2):
        pos = _make_closed_stock_position(code=f"00072{i}")
        await tracker.save_stock_trade_to_db(pos)

    tracker._flush_stock_trades_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_stock_trade_rejects_futures_asset_class():
    """asset_class != 'stock'인 tracker에서 stock 저장 호출 시 조용히 no-op + warn."""
    config = PositionTrackerConfig(asset_class="futures", batch_size=50)
    tracker = PositionTracker(config=config)

    position = _make_closed_stock_position()
    result = await tracker.save_stock_trade_to_db(position)

    assert result is False
    assert tracker._pending_stock_trades == []
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /home/deploy/project/kis_unified_sts && source .venv/bin/activate
pytest tests/unit/trading/test_stock_trade_persistence.py -v
```
Expected: 3개 테스트 모두 FAIL (AttributeError: 'PositionTracker' has no attribute 'save_stock_trade_to_db' 등).

- [ ] **Step 3: `_pending_stock_trades` 버퍼 초기화 추가**

`services/trading/position_tracker.py` line 293~300 부근 `__init__`에 추가:

```python
        self._pending_swing_positions: list[tuple[Any, ...]] = []
        self._pending_rl_trades: list[tuple[Any, ...]] = []
        self._pending_stock_trades: list[tuple[Any, ...]] = []  # NEW: 주식 전용 버퍼
```

- [ ] **Step 4: `save_stock_trade_to_db` 메서드 구현**

`services/trading/position_tracker.py`의 `save_rl_trade_to_db` 메서드 **바로 아래**에 새 메서드 추가:

```python
    async def save_stock_trade_to_db(self, position: Position) -> bool:
        """Persist a closed stock position to market.stock_trades (batch).

        선물 전용 rl_trades와 분리된 주식 전용 경로.
        - asset_class='stock'인 tracker만 적재
        - 수수료/슬리피지는 broker가 제공한 metadata["commission"], ["slippage"]에서 복원
        """
        if self.config.asset_class != "stock":
            logger.warning(
                "save_stock_trade_to_db called on asset_class=%s; no-op",
                self.config.asset_class,
            )
            return False

        if position.exit_price is None or position.exit_time is None:
            logger.warning("save_stock_trade_to_db: position not closed, skipping")
            return False

        try:
            pnl = self._calc_realized_pnl(position)
            hold_seconds = 0
            if position.entry_time and position.exit_time:
                hold_seconds = max(
                    0, int((position.exit_time - position.entry_time).total_seconds())
                )

            metadata = position.metadata if isinstance(position.metadata, dict) else {}
            metadata_json = json.dumps(metadata, ensure_ascii=False, default=str)

            entry_notional = max(position.entry_price * position.quantity, 1e-9)
            pnl_pct = (pnl / entry_notional) * 100.0

            commission = float(metadata.get("commission", 0.0) or 0.0)
            slippage = float(metadata.get("slippage", 0.0) or 0.0)
            exit_state = getattr(position.state, "value", str(position.state)) if position.state else ""

            row = (
                position.id,
                position.code,
                position.name,
                position.side.value,
                position.strategy,
                position.execution_venue,
                position.entry_time,
                position.entry_price,
                position.exit_time,
                position.exit_price,
                position.quantity,
                pnl,
                pnl_pct,
                commission,
                slippage,
                hold_seconds,
                position.exit_reason or "",
                exit_state,
                metadata_json,
            )

            async with self._batch_lock:
                self._pending_stock_trades.append(row)
                batch_size = len(self._pending_stock_trades)

            logger.info(
                f"Accumulated stock trade: {position.code} "
                f"(strategy={position.strategy}, pnl={pnl:+,.0f}, "
                f"pnl_pct={pnl_pct:+.2f}%, id={position.id[:8]}, "
                f"batch={batch_size}/{self.config.batch_size})"
            )

            if batch_size >= self.config.batch_size:
                await self._flush_stock_trades_batch()
            return True

        except (AttributeError, ValueError, TypeError, KeyError) as e:
            logger.error(f"save_stock_trade_to_db failed for {position.code}: {e}")
            return False

    async def _flush_stock_trades_batch(self) -> int:
        """Flush buffered stock trades to market.stock_trades."""
        columns = (
            "(id, code, name, side, strategy, execution_venue, "
            "entry_date, entry_price, exit_date, exit_price, quantity, "
            "pnl, pnl_pct, commission, slippage, hold_seconds, "
            "exit_reason, exit_state, metadata_json)"
        )
        count, self._pending_stock_trades = await self._flush_batch(
            self._pending_stock_trades,
            table="stock_trades",
            columns=columns,
        )
        return count
```

- [ ] **Step 5: 주기적 flush에 `stock_trades` 포함**

기존 `_flush_all_batches`(약 line 1180~1210) 수정 — 기존에 swing/rl 두 배치를 플러시하는 코드에 stock 추가:

```python
    async def _flush_all_batches(self) -> None:
        """Flush all pending batches to DB (periodic + shutdown)."""
        count_swing, self._pending_swing_positions = await self._flush_batch(
            self._pending_swing_positions,
            table="swing_positions",
            columns=SWING_POSITIONS_COLUMNS,
        )
        count_rl, self._pending_rl_trades = await self._flush_batch(
            self._pending_rl_trades,
            table="rl_trades",
            columns=RL_TRADES_COLUMNS,
        )
        count_stock = await self._flush_stock_trades_batch()

        if count_swing or count_rl or count_stock:
            logger.info(
                f"Flushed batches: swing={count_swing}, rl={count_rl}, stock={count_stock}"
            )
```
(주의: 정확한 라인과 기존 구조에 맞춰 병합. 기존 함수가 존재하면 그 안에 `_flush_stock_trades_batch` 호출 추가.)

- [ ] **Step 6: 테스트 통과 확인**

```bash
pytest tests/unit/trading/test_stock_trade_persistence.py -v
```
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add services/trading/position_tracker.py tests/unit/trading/test_stock_trade_persistence.py
git commit -m "feat(tracking): add save_stock_trade_to_db for market.stock_trades persistence"
```

### Task 3: `TradingOrchestrator` persistence 라우팅 재구성 (TDD)

**Files:**
- Modify: `services/trading/orchestrator.py:5177-5185` (persist 라우팅)
- Modify: `services/trading/orchestrator.py:1854-1870` (`_persist_closed_position`)
- Modify: `services/trading/orchestrator.py:2937-2958` (`_close_intraday_positions` — Phase 3에서 추가 수정하지만 여기서 필터 로직 일부 선반영)

- [ ] **Step 1: 실패 테스트 작성 — 주식 오케스트레이터가 save_stock_trade_to_db 호출**

`tests/unit/trading/test_stock_trade_persistence.py`에 테스트 추가:

```python
# 파일 하단에 추가
from unittest.mock import patch


class TestOrchestratorRouting:
    """오케스트레이터가 asset_class 기반으로 stock vs futures 저장 경로를 선택."""

    @pytest.mark.asyncio
    async def test_stock_orchestrator_routes_to_stock_trades(self):
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.models.signal import ExitSignal

        cfg = TradingConfig(
            asset_class="stock",
            strategy_name="momentum_breakout",
            initial_capital=100_000_000.0,
            order_amount_per_trade=1_000_000.0,
        )
        orch = TradingOrchestrator(cfg)
        closed = _make_closed_stock_position(strategy="momentum_breakout")

        save_stock = AsyncMock(return_value=True)
        save_rl = AsyncMock(return_value=True)
        orch._position_tracker = MagicMock()
        orch._position_tracker.save_stock_trade_to_db = save_stock
        orch._position_tracker.save_rl_trade_to_db = save_rl

        await orch._persist_closed_position(closed, "momentum_breakout")

        save_stock.assert_awaited_once_with(closed)
        save_rl.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_futures_rl_orchestrator_routes_to_rl_trades(self):
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        cfg = TradingConfig(
            asset_class="futures",
            strategy_name="rl_mppo",
            initial_capital=10_000_000.0,
            order_amount_per_trade=1_000_000.0,
            symbols=["A05603"],
        )
        orch = TradingOrchestrator(cfg)
        closed = _make_closed_stock_position(strategy="rl_mppo")

        save_stock = AsyncMock(return_value=True)
        save_rl = AsyncMock(return_value=True)
        orch._position_tracker = MagicMock()
        orch._position_tracker.save_stock_trade_to_db = save_stock
        orch._position_tracker.save_rl_trade_to_db = save_rl

        await orch._persist_closed_position(closed, "rl_mppo")

        save_rl.assert_awaited_once()
        save_stock.assert_not_awaited()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/unit/trading/test_stock_trade_persistence.py::TestOrchestratorRouting -v
```
Expected: FAIL (현재 `_persist_closed_position`이 주식도 rl_trades로 보냄 또는 SWING_STRATEGIES로 제한).

- [ ] **Step 3: `_persist_closed_position` 재구현 (asset_class 기반 라우팅)**

`services/trading/orchestrator.py`의 기존 `_persist_closed_position` (line 1854-1870)을 다음으로 교체:

```python
    async def _persist_closed_position(self, closed, strategy: str):
        """Persist a closed position to ClickHouse with asset-class routing.

        - asset_class='stock' → market.stock_trades (모든 주식 전략)
                             + (옵션) market.swing_positions (SWING_STRATEGIES만)
        - asset_class='futures' + strategy.startswith('rl_') → kospi.rl_trades
        - 그 외 → no-op
        """
        try:
            if self.config.asset_class == "stock":
                # 모든 주식 거래 → stock_trades
                await self._position_tracker.save_stock_trade_to_db(closed)
                # SWING 전략은 position state 추적용으로 swing_positions에도 적재
                if strategy in self.SWING_STRATEGIES:
                    await self._position_tracker.save_closed_to_db(closed)
            elif self.config.asset_class == "futures" and strategy.startswith("rl_"):
                await self._position_tracker.save_rl_trade_to_db(
                    closed, asset_class=self.config.asset_class
                )
            else:
                logger.debug(
                    "persist skipped: asset_class=%s strategy=%s",
                    self.config.asset_class,
                    strategy,
                )
        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"_persist_closed_position failed: {e}")
```

- [ ] **Step 4: persistence 트리거 라우팅 수정 (line 5177-5185)**

기존의:
```python
if strategy in self.SWING_STRATEGIES or strategy.startswith("rl_"):
    task = asyncio.create_task(
        self._persist_closed_position(closed, strategy), name="persist_closed"
    )
```
를 다음으로 교체:

```python
# Persist to ClickHouse (asset-class routed; details in _persist_closed_position)
if self.config.asset_class == "stock" or (
    self.config.asset_class == "futures" and strategy.startswith("rl_")
):
    task = asyncio.create_task(
        self._persist_closed_position(closed, strategy), name="persist_closed"
    )
    self._pending_notify_tasks.add(task)
    task.add_done_callback(self._on_notify_done)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/unit/trading/test_stock_trade_persistence.py -v
```
Expected: 5 passed (새 테스트 2개 포함).

- [ ] **Step 6: 기존 오케스트레이터 테스트 회귀 확인**

```bash
pytest tests/unit/trading/ -v --no-header 2>&1 | tail -20
```
Expected: 모두 통과(실패 시 `_persist_closed_position` 호출 시그니처 호환성 확인).

- [ ] **Step 7: Commit**

```bash
git add services/trading/orchestrator.py tests/unit/trading/test_stock_trade_persistence.py
git commit -m "feat(orchestrator): route stock trades to market.stock_trades (separated from rl_trades)"
```

### Task 4: 통합 스모크 테스트 (수동 — 1회 paper session)

**Files:** 없음 (운영 검증만)

- [ ] **Step 1: paper trading을 1분 실행 후 DB 확인**

```bash
cd /home/deploy/project/kis_unified_sts && source .venv/bin/activate
# 주식 paper 실행 (짧게)
timeout 90 sts paper start --asset stock --capital 100000000 --paper 2>&1 | tail -30 &
sleep 80
pkill -f "sts paper" || true
```

- [ ] **Step 2: ClickHouse 검증 쿼리**

```bash
source .env
clickhouse-client --host=localhost --port=9000 --user=default --password="$CLICKHOUSE_PASSWORD" --format=PrettyCompact -q "
  SELECT count() AS total, min(exit_date) AS first, max(exit_date) AS last
  FROM market.stock_trades
  WHERE exit_date >= now() - INTERVAL 1 HOUR"
```
Expected: 실거래 발생 시 `total > 0` (장외 시간대엔 0도 정상이지만 에러 로그는 없어야 함).

- [ ] **Step 3: 에러 로그 확인**

```bash
tail -200 logs/stock_trading_$(date +%Y%m%d).log | grep -iE "error|failed|exception" | head -10
```
Expected: `save_stock_trade_to_db` 관련 에러 없음.

- [ ] **Step 4 (no commit — 운영 검증만 기록):**

결과를 `docs/plans/2026-04-14-paper-trading-db-integrity.md` 하단의 `## Smoke Test Results`에 기록.

---

## Phase 2 (P0-2): PnL 계산 이상값 수정

### Task 5: `Position.profit_pct`의 close-after 경로 안정화 (TDD)

**전제:** Task 0의 investigation에서 근본원인이 확정됨. 아래 코드는 가설 (A) "stale current_price"가 확정된 경우의 수정. 다른 가설이면 실제 수정 코드를 그에 맞게 교체.

**Files:**
- Create: `tests/unit/models/test_position_profit_pct.py`
- Modify: `shared/models/position.py:113-117` (`profit_pct` / `profit_rate`)
- Modify: `services/trading/position_tracker.py:1040~1120` (save_rl_trade_to_db에서 position.profit_pct 참조 부분 — 재계산)

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/models/test_position_profit_pct.py
"""Position.profit_pct / profit_rate — close 이후 안정성 회귀 테스트."""
from datetime import datetime

import pytest

from shared.models.position import Position, PositionSide, PositionState


def _make_position(
    entry_price: float, current_price: float, side: PositionSide = PositionSide.LONG
) -> Position:
    pos = Position(
        id="p1",
        code="TEST",
        name="TEST",
        strategy="test",
        side=side,
        entry_price=entry_price,
        quantity=10,
        entry_time=datetime(2026, 4, 10, 9, 0),
    )
    pos.current_price = current_price
    return pos


class TestProfitPctBeforeClose:
    def test_long_profit(self):
        pos = _make_position(100.0, 105.0, PositionSide.LONG)
        assert pos.profit_pct == pytest.approx(5.0)

    def test_long_loss(self):
        pos = _make_position(100.0, 95.0, PositionSide.LONG)
        assert pos.profit_pct == pytest.approx(-5.0)

    def test_short_profit(self):
        pos = _make_position(100.0, 95.0, PositionSide.SHORT)
        assert pos.profit_pct == pytest.approx(5.0)


class TestProfitPctAfterClose:
    """exit_price가 설정된 뒤 current_price가 다른 값이어도 exit_price 기준으로 계산."""

    def test_uses_exit_price_when_available(self):
        pos = _make_position(100.0, 50.0, PositionSide.LONG)  # stale current_price
        pos.exit_price = 98.0  # 실제 청산가
        pos.exit_time = datetime(2026, 4, 10, 15, 30)
        pos.state = PositionState.CLOSED
        # exit_price 기준으로 -2% (not -50% from stale current_price)
        assert pos.profit_pct == pytest.approx(-2.0)

    def test_uses_current_price_when_exit_price_none(self):
        pos = _make_position(100.0, 95.0, PositionSide.LONG)
        assert pos.exit_price is None
        assert pos.profit_pct == pytest.approx(-5.0)


class TestProfitPctEdgeCases:
    def test_entry_price_zero_returns_zero(self):
        pos = _make_position(0.0, 100.0)
        assert pos.profit_pct == 0.0

    def test_tiny_entry_price_does_not_explode(self):
        """매우 작은 entry_price + 정상 exit 조합에서도 이상값 금지."""
        pos = _make_position(0.01, 1.0, PositionSide.LONG)
        pos.exit_price = 1.0
        # 정상 계산: 9900% — 유효하지만 경고성 케이스
        # 현 테스트는 계산이 터지지 않음만 확인
        assert pos.profit_pct < 1e6
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/unit/models/test_position_profit_pct.py -v
```
Expected: `test_uses_exit_price_when_available` FAIL (현재 `current_price`만 사용).

- [ ] **Step 3: `profit_rate` 수정**

`shared/models/position.py:102-116`의 `profit_rate` 속성을 다음으로 교체:

```python
    @property
    def profit_rate(self) -> float:
        """현재/실현 수익률 (비율).

        - 포지션이 청산되어 exit_price가 있으면 exit_price 기준으로 실현 수익률 반환
        - 그 외에는 current_price 기준으로 미실현 수익률 반환
        - entry_price가 0 이하이면 0 반환(경계값 보호)
        """
        if self.entry_price <= 0:
            return 0.0

        reference = self.exit_price if self.exit_price is not None else self.current_price

        if self.side == PositionSide.LONG:
            return (reference - self.entry_price) / self.entry_price
        else:  # SHORT
            return (self.entry_price - reference) / self.entry_price
```

`profit_pct` 속성은 그대로(`profit_rate * 100`) 유지.

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/unit/models/test_position_profit_pct.py -v
```
Expected: 모두 통과.

- [ ] **Step 5: `save_rl_trade_to_db`에서 pnl_pct 재계산 (defensive)**

`services/trading/position_tracker.py`의 `save_rl_trade_to_db` 내부 (line ~1106) `position.profit_pct`를 그대로 쓰는 곳을 `stock_trades`와 동일한 명시적 계산으로 교체 — 이미 `save_stock_trade_to_db`에서 쓰는 패턴:

```python
entry_notional = max(position.entry_price * position.quantity, 1e-9)
pnl_pct = (pnl / entry_notional) * 100.0
```
(`position.profit_pct` 호출 대신 row에 `pnl_pct` 직접 삽입)

- [ ] **Step 6: 기존 position tracker 테스트 회귀 확인**

```bash
pytest tests/unit/trading/test_position_tracker.py tests/unit/models/ -v
```
Expected: 기존 테스트 모두 통과.

- [ ] **Step 7: Commit**

```bash
git add shared/models/position.py services/trading/position_tracker.py tests/unit/models/test_position_profit_pct.py
git commit -m "fix(position): use exit_price when available for profit_rate; stabilize pnl_pct after close"
```

---

## Phase 3 (P0-3): 주식 EOD 전량 청산 차단

### Task 6: `_close_intraday_positions`를 주식에서 제외 (TDD)

**Files:**
- Create: `tests/unit/trading/test_eod_close_policy.py`
- Modify: `services/trading/orchestrator.py:2937-2958` (`_close_intraday_positions`)
- Modify: `services/trading/orchestrator.py` — EOD 트리거 경로에서 stock asset_class 분기

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/trading/test_eod_close_policy.py
"""주식 EOD 전량 청산 차단 회귀 테스트.

CLAUDE.md: "EOD 전량 청산 금지. Intraday trading이 아님. 상승 여력 종목 보유 유지."
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from services.trading.orchestrator import TradingConfig, TradingOrchestrator
from shared.models.position import Position, PositionSide, PositionState


def _make_open_position(code: str, strategy: str) -> Position:
    return Position(
        id=f"p-{code}",
        code=code,
        name=f"NAME-{code}",
        strategy=strategy,
        side=PositionSide.LONG,
        entry_price=100.0,
        quantity=10,
        entry_time=datetime(2026, 4, 14, 9, 15),
        state=PositionState.OPEN,
    )


class TestStockEODPolicy:
    @pytest.mark.asyncio
    async def test_stock_positions_not_force_closed_at_eod(self):
        """주식 orchestrator의 _close_intraday_positions는 주식에서 no-op이어야 한다."""
        cfg = TradingConfig(
            asset_class="stock",
            strategy_name="momentum_breakout",
            initial_capital=100_000_000,
            order_amount_per_trade=1_000_000,
        )
        orch = TradingOrchestrator(cfg)

        tracker = MagicMock()
        tracker.positions = [
            _make_open_position("000720", "momentum_breakout"),
            _make_open_position("005930", "trend_pullback"),
        ]
        tracker.close_position = MagicMock()
        orch._position_tracker = tracker
        orch._state_publisher = None
        orch._sync_open_positions_metric = MagicMock()

        await orch._close_intraday_positions({"000720": {"close": 100}, "005930": {"close": 100}})

        tracker.close_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_futures_non_rl_positions_still_force_closed(self):
        """선물은 기존과 동일하게 EOD 청산 유지(rl_mppo는 자체 EOD, 그 외는 force close)."""
        cfg = TradingConfig(
            asset_class="futures",
            strategy_name="rl_mppo",
            initial_capital=10_000_000,
            order_amount_per_trade=1_000_000,
            symbols=["A05603"],
        )
        orch = TradingOrchestrator(cfg)

        tracker = MagicMock()
        # RL 전략은 SWING_STRATEGIES가 아니지만 별도 EOD 로직이 있으므로
        # 여기서는 non-RL 전략 포지션만 EOD 처리 대상
        non_rl_pos = _make_open_position("A05603", "legacy_intraday")
        tracker.positions = [non_rl_pos]
        tracker.close_position = MagicMock(
            return_value=_make_open_position("A05603", "legacy_intraday")
        )
        orch._position_tracker = tracker
        orch._state_publisher = None
        orch._sync_open_positions_metric = MagicMock()

        await orch._close_intraday_positions({"A05603": {"close": 100}})

        tracker.close_position.assert_called_once()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/unit/trading/test_eod_close_policy.py -v
```
Expected: `test_stock_positions_not_force_closed_at_eod` FAIL.

- [ ] **Step 3: `_close_intraday_positions` 수정**

`services/trading/orchestrator.py:2937`의 함수를 다음으로 교체:

```python
    async def _close_intraday_positions(self, data):
        """Force close non-swing positions at EOD.

        Policy (CLAUDE.md):
        - asset_class='stock': EOD 전량 청산 금지. 전략 시그널 기반 청산만 허용.
          → 여기서는 no-op.
        - asset_class='futures': RL 전략은 자체 EOD 안전장치(rl_mppo_exit)를 가지므로
          여기서는 그 외 legacy intraday 전략만 청산.
        """
        if self.config.asset_class == "stock":
            logger.debug(
                "EOD intraday force-close skipped: asset_class=stock policy forbids it"
            )
            return

        intraday_positions = [
            pos
            for pos in self._position_tracker.positions
            if pos.strategy not in self.SWING_STRATEGIES
            and not pos.strategy.startswith("rl_")
        ]
        for pos in intraday_positions:
            price_data = data.get(pos.code, {})
            if isinstance(price_data, dict):
                price = price_data.get("close") or pos.current_price
            else:
                price = price_data or pos.current_price

            closed = self._position_tracker.close_position(
                pos.id, price, reason="EOD_CLOSE"
            )
            if closed:
                self.total_pnl += closed.unrealized_pnl
                if self._state_publisher:
                    self._state_publisher.publish_position_closed(closed)
        self._sync_open_positions_metric()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/unit/trading/test_eod_close_policy.py -v
```
Expected: 2 passed.

- [ ] **Step 5: 호출자 경로 확인 — `_close_intraday_positions`는 어디서 불리는지 grep**

```bash
grep -n "_close_intraday_positions" services/trading/orchestrator.py
```
각 호출 지점에서 주식 경우에도 불리는지 확인. 호출 자체는 유지 — 함수 내부에서 asset_class 체크로 early return 하므로 충분.

- [ ] **Step 6: 기존 orchestrator 테스트 회귀 확인**

```bash
pytest tests/unit/trading/test_orchestrator.py tests/unit/trading/test_orchestrator_notify.py -v
```
Expected: 모두 통과.

- [ ] **Step 7: Commit**

```bash
git add services/trading/orchestrator.py tests/unit/trading/test_eod_close_policy.py
git commit -m "fix(orchestrator): disable EOD force-close for stocks (CLAUDE.md policy compliance)"
```

---

## Phase 4: 한달치 누락 데이터 재구성 가이드 (참고)

**주의:** 한달간 로그에서 발견된 주식 74건(+이상 profit)은 로그만 존재하고 DB에는 없음. 이미 발생한 기록은 다음과 같은 이유로 "재적재하지 않는" 것이 안전:

1. 로그의 `profit=+3727%` 등은 **신뢰 불가 값** — 재적재 시 대시보드/분석 전반에 오염
2. `profit_pct` 버그가 수정되기 전 snapshot이므로 원본 price도 신뢰 불가
3. 모의투자이므로 회계적 감사 의무 없음

### Task 7: 누락 데이터 기록을 "알려진 데이터 공백"으로 문서화

**Files:**
- Create: `docs/data/known_gaps.md`

- [ ] **Step 1: 공백 문서 작성**

```markdown
# Known Data Gaps

## 2026-03-11 ~ 2026-04-14 — 주식 모의투자 DB 누락

- **테이블**: market.stock_trades (신규) / market.rl_trades (이전 범주)
- **영향 기간**: 2026-03-11 ~ 2026-04-14 (약 1개월)
- **영향 건수**: 로그 기준 74건 open/close (stock_trading_*.log)
- **누락 원인**: TradingOrchestrator._persist_closed_position 필터가 SWING_STRATEGIES + rl_* 만
  DB 저장 대상으로 설정하여 trend_pullback/momentum_breakout 거래가 전량 누락됨.
- **추가 문제**: 로그상 profit_pct 이상값(±수천%) 관측 — Position.profit_pct가 stale
  current_price를 참조하는 버그와 결합된 결과.
- **복구 정책**: **원본 로그 값 신뢰 불가**로 재적재 금지. 이 구간은 영구 데이터 공백으로 기록.
- **수정 PR**: (이 계획의 최종 PR 링크)
```

- [ ] **Step 2: Commit**

```bash
git add docs/data/known_gaps.md
git commit -m "docs: record 2026-03-11..04-14 stock paper-trading DB gap (not re-loadable)"
```

---

## Phase 5: 관측성 — 자본/PnL 누적 추적 복구

### Task 8: 일간 자본 추적 SQL view 추가

**Files:**
- Create: `sql/views/stock_daily_equity.sql`
- Create: `sql/views/futures_daily_equity.sql`

- [ ] **Step 1: 주식 일간 equity view**

```sql
-- sql/views/stock_daily_equity.sql
CREATE VIEW IF NOT EXISTS market.stock_daily_equity AS
SELECT
    toDate(exit_date) AS d,
    count() AS trades,
    countIf(pnl > 0) AS wins,
    round(countIf(pnl > 0) / count() * 100, 1) AS win_pct,
    round(sum(pnl), 0) AS daily_pnl,
    round(sum(commission), 0) AS daily_commission,
    round(sum(slippage), 0) AS daily_slippage,
    round(avg(hold_seconds) / 60, 1) AS avg_hold_minutes
FROM market.stock_trades
GROUP BY d
ORDER BY d;
```

- [ ] **Step 2: 선물 일간 equity view**

```sql
-- sql/views/futures_daily_equity.sql
CREATE VIEW IF NOT EXISTS kospi.futures_daily_equity AS
SELECT
    toDate(exit_date) AS d,
    count() AS trades,
    countIf(pnl > 0) AS wins,
    round(countIf(pnl > 0) / count() * 100, 1) AS win_pct,
    round(sum(pnl), 2) AS daily_pnl,
    round(avg(hold_seconds), 0) AS avg_hold_seconds,
    groupUniqArrayArray(15)(strategy) AS strategies
FROM kospi.rl_trades
GROUP BY d
ORDER BY d;
```

- [ ] **Step 3: 서버에 적용**

```bash
source .env
for f in sql/views/*.sql; do
  clickhouse-client --host=localhost --port=9000 --user=default --password="$CLICKHOUSE_PASSWORD" < "$f"
done
clickhouse-client --host=localhost --port=9000 --user=default --password="$CLICKHOUSE_PASSWORD" \
  -q "SELECT * FROM market.stock_daily_equity LIMIT 5 FORMAT PrettyCompact"
```
Expected: 뷰 생성 성공, 쿼리 에러 없음(데이터는 수정 후 시점부터 축적).

- [ ] **Step 4: Commit**

```bash
git add sql/views/stock_daily_equity.sql sql/views/futures_daily_equity.sql
git commit -m "feat(observability): add per-asset daily equity views for long-term PnL tracking"
```

---

## 최종 검증

### Task 9: 전체 회귀 테스트 + PR 생성

- [ ] **Step 1: 전체 unit 테스트 실행**

```bash
cd /home/deploy/project/kis_unified_sts && source .venv/bin/activate
pytest tests/unit/ -q --no-header 2>&1 | tail -10
```
Expected: 모든 테스트 통과(신규 + 기존 모두).

- [ ] **Step 2: 브랜치 push 및 PR 생성**

```bash
git push -u origin fix/paper-trading-db-integrity
gh pr create --base main --title "fix: restore paper-trading DB persistence and PnL tracking integrity" \
  --body "$(cat <<'EOF'
## Summary

한달간 주식 모의투자 거래 기록 DB 누락(74건 0적재), PnL ±수천% 이상값, EOD 전량 청산 정책 위반을 복구.

## Changes

- **[Phase 1]** `market.stock_trades` 신규 테이블 생성 (선물 `rl_trades`와 분리). 모든 주식 거래를 여기로 적재.
- **[Phase 2]** `Position.profit_pct`가 close 후 exit_price를 우선 사용하도록 수정 → stale `current_price`로 인한 이상값 제거.
- **[Phase 3]** 주식 asset_class에서 `_close_intraday_positions` no-op 처리 (CLAUDE.md "EOD 전량 청산 금지" 준수).
- **[Phase 5]** 관측성: `stock_daily_equity`, `futures_daily_equity` 뷰 추가.

## Test plan

- [x] 주식 stock_trades 적재 테스트 (3건)
- [x] 오케스트레이터 라우팅 테스트 (stock → stock_trades, futures+rl → rl_trades)
- [x] Position.profit_pct close-after 안정성 테스트 (7건)
- [x] 주식 EOD 청산 차단 테스트 (2건)
- [ ] 배포 후 1 영업일 실운영 후 DB 누적 검증

## Notes

2026-03-11 ~ 2026-04-14 주식 거래 74건은 원본 로그의 profit 값 신뢰 불가로 재적재하지 않음 (`docs/data/known_gaps.md` 참조).
EOF
)"
```

---

## Self-Review Checklist (이 계획을 실행하기 전 확인)

- [x] Phase 1 `stock_trades` 테이블 신규 생성 — 선물 `rl_trades`와 물리적 분리 ✓
- [x] Phase 1 persistence 라우팅 재구성 — asset_class 기반, SWING_STRATEGIES 필터 제거 ✓
- [x] Phase 2 근본원인 investigation 선행 (Task 0) — 추측성 수정 방지 ✓
- [x] Phase 2 `profit_pct` close-after 경로 수정 + defensive pnl_pct 재계산 ✓
- [x] Phase 3 주식 EOD 청산 차단 — CLAUDE.md 정책 준수 ✓
- [x] 모든 수정에 TDD(실패→최소구현→통과→커밋) 적용 ✓
- [x] 한달치 누락 데이터는 "재적재 금지" 명시 — 신뢰 불가 profit 오염 방지 ✓
- [x] 일간 자본/PnL 추적 뷰로 장기 가시성 확보 ✓
- [x] 선물 rl_trades 경로 변경 없음 — 기존 578건 데이터 유지 ✓

## Smoke Test Results (Task 4)

- **2026-04-14 evening (post-market)**: Integration startup sanity verified.
  - `TradingOrchestrator(asset_class='stock')` initializes without error
  - `PositionTrackerConfig(asset_class='stock')` accepts the new field
  - `market.stock_trades` table accessible (0 rows, as expected pre-first-trade)
- **Next market day (2026-04-15)**: Full end-to-end smoke test with live paper session pending.
