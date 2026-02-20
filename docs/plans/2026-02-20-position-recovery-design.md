# Position Recovery via Redis — Design Document

**Date**: 2026-02-20
**Status**: Draft
**Author**: Claude (brainstorming session)

---

## 1. Problem Statement

프로세스 재시작(수동/크래시) 시 열린 포지션이 유실됩니다.

### 근본 원인 3가지

1. **ClickHouse 인증 실패 (Code: 516)** — `swing_positions` 테이블 save/load 전부 실패 (2026-02-20 하루 종일)
   - `CLICKHOUSE_URL=clickhouse://localhost:9000/default` (비밀번호 미포함)
   - `CLICKHOUSE_PASSWORD=@1tidh6ls6ls` (별도 변수, URL에 미반영)

2. **`SWING_STRATEGIES` 게이트** — `rl_mppo`가 미포함되어 선물 포지션은 ClickHouse가 정상이어도 복구 불가
   ```python
   SWING_STRATEGIES = frozenset({"volume_accumulation", "bb_reversion"})  # rl_mppo 없음
   ```

3. **In-memory 전용 구조** — `PositionTracker._positions`가 유일한 런타임 저장소. 프로세스 종료 = 데이터 유실

### 2026-02-20 실제 사례

- 14:14 — 003530 한화투자증권 진입 (BUY 1,083 @ 9,239)
- 14:32 — 코드 업데이트 위해 프로세스 재시작
- 14:32 — 포지션 유실 (ClickHouse load 실패, Redis에는 데이터 존재)
- 15:30 — 장 마감. 포지션 미청산 상태로 방치

---

## 2. Architecture Decision

### 저장소 역할 분리

| 저장소 | 역할 | 근거 |
|--------|------|------|
| **Redis** | 포지션 복구 (유일한 소스) | 이미 실시간 publish 중, 빠르고 단순 |
| **모의투자 계좌** (KIS Mock) | 매매 이력 원본 | 실전 전환 시 코드 재활용 |
| **ClickHouse** | 감사/정합성 검증 | Mock 계좌와 교차 검증용 |

### 핵심 변경 원칙

1. **Redis = 포지션의 유일한 복구 소스** (ClickHouse 의존성 제거)
2. **`SWING_STRATEGIES` 게이트 제거** — 모든 전략에 동일한 복구 경로
3. **전략별 freshness 필터** — Intraday(당일만) vs Swing(7일 이내)
4. **Clean shutdown 시 Redis 정리** — 청산된 포지션 HASH 삭제
5. **직렬화 보강** — `highest_price`, `lowest_price`, `fee_rate` 추가

---

## 3. Data Flow

### 현재 (깨진 구조)

```
Startup → _load_swing_positions()
           ├─ SWING_STRATEGIES 게이트 → rl_mppo 차단
           └─ ClickHouse load_from_db() → Code: 516 인증 실패
           → 포지션 0개
```

### 변경 후

```
Startup → _recover_positions_from_redis()
           ├─ TradingStateReader.read_open_positions()    ← Redis HASH 전체 읽기
           ├─ Freshness filter (전략별)
           │   ├─ Intraday: entry_time.date() == today만
           │   └─ Swing: age <= max_position_age_days (config, default=7)
           ├─ Position 객체 재구성 → PositionTracker.add_recovered_position()
           ├─ Exit 전략 재초기화 (state 복원: SURVIVAL/BREAKEVEN/MAXIMIZE)
           ├─ 복구 심볼 → config.symbols에 추가 (WebSocket 구독)
           └─ Stale 포지션 → Redis HDEL + 로깅
           → N개 포지션 복구
```

---

## 4. Redis Position Schema (Enhanced)

현재 직렬화 (`_serialize_position`):
```json
{
  "id": "650c3111-...",
  "code": "003530",
  "name": "한화투자증권",
  "side": "long",
  "quantity": 1083,
  "entry_price": 9239.23,
  "current_price": 9320.0,
  "unrealized_pnl": 87473.91,
  "pnl_pct": 0.874,
  "entry_time": "2026-02-20T14:14:24.915366",
  "strategy": "bb_reversion",
  "state": "survival"
}
```

**추가 필드** (복구 정확도 향상):
```json
{
  "highest_price": 9350.0,    // trailing stop 계산에 필수
  "lowest_price": 9200.0,     // short 포지션 trailing에 필요
  "fee_rate": 0.00015,        // 수수료율
  "stop_price": 8777.27       // 현재 stop 가격 (재계산 가능하지만 저장이 더 정확)
}
```

### Position → Redis 필드 매핑

| Position 필드 | Redis 필드 | 복구 시 처리 |
|---------------|-----------|-------------|
| `id` | `id` | 그대로 사용 |
| `code` | `code` | 그대로 사용 |
| `name` | `name` | 그대로 사용 |
| `side` | `side` (str) | → `PositionSide(side)` |
| `quantity` | `quantity` | 그대로 사용 |
| `entry_price` | `entry_price` | 그대로 사용 |
| `entry_time` | `entry_time` (ISO str) | → `datetime.fromisoformat()` |
| `current_price` | `current_price` | 그대로 사용 |
| `highest_price` | `highest_price` (**신규**) | fallback: `max(entry, current)` |
| `lowest_price` | `lowest_price` (**신규**) | fallback: `min(entry, current)` |
| `stop_price` | `stop_price` (**신규**) | fallback: exit 전략 재계산 |
| `state` | `state` (str) | → `PositionState(state.upper())` |
| `strategy` | `strategy` | 그대로 사용 |
| `fee_rate` | `fee_rate` (**신규**) | fallback: `config.default_fee_rate` |
| `metadata` | — | 빈 dict |

---

## 5. Strategy Classification

```python
# 전략 분류 (orchestrator.py)
INTRADAY_STRATEGIES = frozenset({
    "opening_volume_surge",
    "trix_golden",
    "rl_mppo",           # 선물 RL은 인트라데이
})

# Swing = INTRADAY가 아닌 모든 전략
# bb_reversion, volume_accumulation 등
```

### Freshness Rules

| 전략 유형 | 복구 조건 | 스테일 포지션 처리 |
|----------|----------|-----------------|
| Intraday | `entry_time.date() == today` | Redis HDEL + orphan 로깅 |
| Swing | `age_days <= max_position_age_days` (config, default=7) | Redis HDEL + orphan 로깅 |

---

## 6. Implementation Plan

### File Changes

| # | 파일 | 변경 내용 | 난이도 |
|---|------|----------|--------|
| 1 | `shared/streaming/trading_state.py` | `TradingStateReader.read_open_positions()`, `remove_position()`, `clear_positions()` 추가 | Low |
| 2 | `shared/streaming/trading_state.py` | `_serialize_position()`에 `highest_price`, `lowest_price`, `fee_rate`, `stop_price` 추가 | Low |
| 3 | `services/trading/orchestrator.py` | `_recover_positions_from_redis()` 메서드 추가 | Medium |
| 4 | `services/trading/orchestrator.py` | `_initialize_components()`에서 `_load_swing_positions()` → `_recover_positions_from_redis()` 교체 | Low |
| 5 | `services/trading/orchestrator.py` | `SWING_STRATEGIES` → `INTRADAY_STRATEGIES` 로 전환 (의미 반전) | Low |
| 6 | `services/trading/position_tracker.py` | `add_recovered_position()` 메서드 추가 (기존 add_position 기반, ID 보존) | Medium |
| 7 | `services/trading/position_tracker.py` | `save_to_db()`/`load_from_db()` 포지션 복구 용도 제거 (ClickHouse는 trade 기록용만 유지) | Low |
| 8 | `tests/unit/trading/test_position_recovery.py` | Redis 복구 유닛 테스트 (mock Redis) | Medium |

### Step-by-Step

#### Step 1: Redis 직렬화 보강 (`shared/streaming/trading_state.py`)

`_serialize_position()`에 4개 필드 추가:
```python
@staticmethod
def _serialize_position(pos: Any) -> dict:
    return {
        # ... 기존 필드 ...
        "highest_price": getattr(pos, "highest_price", pos.entry_price),
        "lowest_price": getattr(pos, "lowest_price", pos.entry_price),
        "fee_rate": getattr(pos, "fee_rate", 0.0),
        "stop_price": getattr(pos, "stop_price", None),
    }
```

#### Step 2: Reader 확장 (`shared/streaming/trading_state.py`)

```python
class TradingStateReader:
    def read_open_positions(self) -> list[dict]:
        """Read all open positions from Redis HASH for recovery."""
        r = _get_redis()
        key = _key(_KEY_POSITIONS, self._asset)
        raw = r.hgetall(key)
        positions = []
        for pid, data_str in raw.items():
            try:
                pos = json.loads(data_str if isinstance(data_str, str) else data_str.decode())
                positions.append(pos)
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning(f"Invalid position data in Redis: {pid}")
        return positions

    def remove_position(self, position_id: str) -> None:
        """Remove a single stale position from Redis."""
        r = _get_redis()
        key = _key(_KEY_POSITIONS, self._asset)
        r.hdel(key, position_id)
```

#### Step 3: PositionTracker 확장 (`services/trading/position_tracker.py`)

```python
def add_recovered_position(self, position: Position) -> bool:
    """Add a position recovered from Redis (preserves original ID and state)."""
    if position.id in self._positions:
        logger.warning(f"Duplicate position ID on recovery: {position.id}")
        return False

    self._positions[position.id] = position

    # Update indices
    if position.code not in self._by_symbol:
        self._by_symbol[position.code] = []
    self._by_symbol[position.code].append(position.id)

    if position.strategy not in self._by_strategy:
        self._by_strategy[position.strategy] = []
    self._by_strategy[position.strategy].append(position.id)

    self._record_event("recovered", position.id, {
        "code": position.code,
        "entry_price": position.entry_price,
        "quantity": position.quantity,
        "strategy": position.strategy,
        "state": position.state.value,
    })

    logger.info(
        f"Position recovered: {position.code} @ {position.entry_price:,.0f} x {position.quantity} "
        f"(strategy={position.strategy}, state={position.state.value}, id={position.id[:8]})"
    )
    return True
```

#### Step 4: Orchestrator 복구 로직 (`services/trading/orchestrator.py`)

```python
INTRADAY_STRATEGIES = frozenset({"opening_volume_surge", "trix_golden", "rl_mppo"})

async def _recover_positions_from_redis(self) -> int:
    """Recover open positions from Redis on startup."""
    if not self._position_tracker:
        return 0

    reader = TradingStateReader(self.config.asset_class)
    positions = reader.read_open_positions()
    if not positions:
        logger.info("No positions to recover from Redis")
        return 0

    today = datetime.now().date()
    max_age = self.config.max_position_age_days  # YAML config, default=7
    recovered = 0
    stale = 0

    for pos_data in positions:
        strategy = pos_data.get("strategy", "")
        try:
            entry_time_str = pos_data.get("entry_time", "")
            entry_time = datetime.fromisoformat(entry_time_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid entry_time in Redis position: {pos_data.get('id')}")
            reader.remove_position(pos_data.get("id", ""))
            stale += 1
            continue

        # Freshness filter
        age_days = (today - entry_time.date()).days
        if strategy in self.INTRADAY_STRATEGIES:
            if entry_time.date() != today:
                logger.debug(f"Skipping stale intraday position: {pos_data.get('code')} (age={age_days}d)")
                reader.remove_position(pos_data["id"])
                stale += 1
                continue
        else:  # Swing
            if age_days > max_age:
                logger.debug(f"Skipping stale swing position: {pos_data.get('code')} (age={age_days}d)")
                reader.remove_position(pos_data["id"])
                stale += 1
                continue

        # Reconstruct Position
        side = PositionSide(pos_data.get("side", "long"))
        entry_price = float(pos_data["entry_price"])
        current_price = float(pos_data.get("current_price", entry_price))

        position = Position(
            id=pos_data["id"],
            code=pos_data["code"],
            name=pos_data.get("name", ""),
            side=side,
            quantity=int(pos_data["quantity"]),
            entry_price=entry_price,
            entry_time=entry_time,
            current_price=current_price,
            highest_price=float(pos_data.get("highest_price", max(entry_price, current_price))),
            lowest_price=float(pos_data.get("lowest_price", min(entry_price, current_price))),
            state=PositionState(pos_data.get("state", "survival").upper()),
            strategy=strategy,
            fee_rate=float(pos_data.get("fee_rate", self.config.default_fee_rate)),
        )

        if pos_data.get("stop_price") is not None:
            position.stop_price = float(pos_data["stop_price"])

        if self._position_tracker.add_recovered_position(position):
            recovered += 1
            # Ensure symbol is in WebSocket subscription
            if position.code not in (self.config.symbols or []):
                if self.config.symbols is None:
                    self.config.symbols = []
                self.config.symbols.append(position.code)

    if stale > 0:
        logger.info(f"Cleaned {stale} stale positions from Redis")
    if recovered > 0:
        logger.info(f"Recovered {recovered} positions from Redis ({self.config.asset_class})")
    return recovered
```

#### Step 5: ClickHouse 포지션 복구 코드 제거

`_load_swing_positions()` → `_recover_positions_from_redis()` 로 교체:
- `_ensure_db_schema()` 호출 제거 (포지션 복구용)
- `load_from_db()` 호출 제거
- `save_to_db()` 호출은 유지 가능 (trade 기록 목적) 또는 제거

#### Step 6: Clean Shutdown 보강

`_shutdown()` 또는 `_cleanup()` 메서드에서:
```python
# Ensure final position state is flushed to Redis before exit
if self._state_publisher and self._position_tracker:
    open_positions = self._position_tracker.get_all_positions()
    if open_positions:
        self._state_publisher.publish_positions_update(open_positions, throttle=0)
        logger.info(f"Flushed {len(open_positions)} positions to Redis before shutdown")
```

---

## 7. Configuration

`config/execution.yaml` (또는 기존 설정 파일에 추가):

```yaml
position_recovery:
  enabled: true
  max_position_age_days: 7     # Swing 포지션 최대 보존 기간
  clean_stale_on_startup: true  # 스테일 포지션 자동 삭제
```

---

## 8. Testing Plan

### Unit Tests (`tests/unit/trading/test_position_recovery.py`)

1. **test_recover_stock_positions** — Redis에서 bb_reversion 포지션 복구
2. **test_recover_futures_short** — SHORT 포지션 복구 (side=short, rl_mppo)
3. **test_filter_stale_intraday** — 전일 intraday 포지션 필터링
4. **test_filter_stale_swing** — 7일 초과 swing 포지션 필터링
5. **test_recover_with_missing_fields** — highest_price 등 없는 레거시 데이터 처리
6. **test_duplicate_position_id** — 중복 ID 방어
7. **test_empty_redis** — Redis 비어있을 때 graceful 처리
8. **test_websocket_subscription** — 복구 심볼 config.symbols에 추가 확인

### Integration Test

1. 포지션 열기 → 프로세스 stop → 프로세스 start → 포지션 복구 확인
2. Redis `trading:stock:positions` HASH 확인

---

## 9. Migration Notes

### 기존 Redis 데이터 정리

현재 Redis에는 스테일 포지션이 남아있습니다:
- 주식: 2/13일 포지션 9개 (1주일 전)
- 선물: 2/19일 포지션 10개 (어제)

**첫 배포 시**: `clean_stale_on_startup: true`로 자동 정리됩니다.

### ClickHouse `swing_positions` 테이블

- **삭제하지 않음** — 기존 데이터 보존
- 포지션 복구 용도에서만 제거
- 추후 trade 기록/감사 용도로 재활용 가능

---

## 10. Risk Assessment

| 리스크 | 영향 | 완화 |
|--------|------|------|
| Redis 다운 시 복구 불가 | 포지션 유실 | Redis는 이미 인프라 핵심. 다운 시 대시보드도 불가 |
| 잘못된 포지션 복구 | 이중 진입 | `add_recovered_position()`에 중복 ID 체크 |
| Highest_price 부정확 | Trailing stop 오차 | 직렬화에 추가하되, fallback 로직 구현 |
| Exit 전략 state 불일치 | 잘못된 청산 | state 필드 (SURVIVAL/BREAKEVEN/MAXIMIZE) 직접 복원 |

---

## 11. Summary

**변경 규모**: 4개 파일, ~150줄 코드
**테스트**: 8개 유닛 테스트
**의존성 변경**: ClickHouse sync client 의존성 제거 (포지션 복구 한정)
**배포**: 프로세스 재시작으로 즉시 적용. 기존 Redis 스테일 데이터 자동 정리.
