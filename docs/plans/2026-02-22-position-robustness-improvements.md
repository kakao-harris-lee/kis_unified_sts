# Position Recovery Robustness Improvements

**Date**: 2026-02-22
**Status**: Implemented (2026-02-23, commit 6b320cd)
**Depends on**: [2026-02-20-position-recovery-design.md](2026-02-20-position-recovery-design.md) (Phase 1, implemented)

---

## 1. Problem Statement

Phase 1 Redis 포지션 복구 시스템이 구현되었지만, **비정상 종료 시 포지션 유실 가능성**이 남아있습니다.

### 발견된 구조적 문제

#### Issue 1: Signal Handler 부재 (P0)

```
# Cron script stop 동작 (rl_paper.sh, stock_trading.sh):
kill "$PID" 2>/dev/null || true    # SIGTERM 전송
sleep 2
kill -9 "$PID" 2>/dev/null || true  # SIGKILL 전송
```

Python 프로세스에 SIGTERM 핸들러가 없어 `orchestrator.stop()`이 호출되지 않습니다:
- **SIGTERM** → 핸들러 없음 → 프로세스 즉시 종료 → `stop()` 미호출
- **SIGINT** (Ctrl+C) → `KeyboardInterrupt` catch만 → `stop()` 미호출
- `asyncio.run()`이 SIGINT에 대해 task cancellation을 하지만, `stop()` 호출을 보장하지 않음

**결과**: Redis에 최대 2초간의 stale 데이터 잔존.

#### Issue 2: KeyboardInterrupt에서 stop() 미호출 (P0)

```python
# cli/main.py (line 1060-1066, 1667-1672)
asyncio.run(run())
# ...
except KeyboardInterrupt:
    click.echo("\nTrading stopped")  # stop() 호출 없이 메시지만 출력!
```

Ctrl+C 시 `orchestrator.stop()`이 호출되지 않아:
- 인트라데이 포지션 강제 청산 생략
- Redis 최종 플러시 생략
- Telegram 종료 알림 전송 생략

#### Issue 3: 2초 Throttle Window (P1)

```python
# orchestrator.py (line 2330)
self._state_publisher.publish_positions_update(positions, throttle=2.0)
```

크래시 시 최대 2초간의 position state 변경이 유실됩니다:
- `SURVIVAL → BREAKEVEN` 전환 직후 크래시 → 복구 시 `SURVIVAL`로 롤백
- 가격 변동 → `highest_price`/`lowest_price` 부정확 → trailing stop 오차

---

## 2. Solution Design

### 2.1 Graceful Shutdown via Signal Handlers (P0)

**CLI 레벨에서 signal handler를 등록**하여 SIGTERM/SIGINT 수신 시 `orchestrator.stop()`을 호출합니다.

#### 변경 파일: `cli/main.py`

```python
# sts trade start 명령어 (line ~1054)
async def run():
    loop = asyncio.get_running_loop()

    # SIGTERM handler (cron stop scripts)
    def _handle_signal():
        logger.info("Received shutdown signal, stopping gracefully...")
        asyncio.ensure_future(orchestrator.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    try:
        if daemon:
            await orchestrator.run()
        else:
            await orchestrator.run_session()
    finally:
        await orchestrator.stop()

asyncio.run(run())
```

동일한 패턴을 `sts rl paper` 명령어에도 적용합니다.

**핵심 포인트**:
- `loop.add_signal_handler()` 사용 (asyncio 이벤트 루프와 안전하게 통합)
- `finally` 블록으로 예외 시에도 `stop()` 보장
- `stop()`은 idempotent (`if self.state == TradingState.STOPPED: return`)

#### 변경 파일: Cron 스크립트

Cron 스크립트의 `sleep 2`를 `sleep 5`로 증가 (graceful shutdown 시간 확보):

```bash
stop_trading() {
    kill "$PID" 2>/dev/null || true
    sleep 5      # 기존 2 → 5 (graceful shutdown 대기)
    kill -9 "$PID" 2>/dev/null || true
}
```

### 2.2 State Transition Immediate Flush (P1)

Position state 전환 시 즉시 Redis 플러시하여 throttle window를 줄입니다.

#### 변경 파일: `services/trading/orchestrator.py`

Position state 전환(SURVIVAL→BREAKEVEN→MAXIMIZE) 발생 시 throttle=0으로 즉시 플러시:

```python
# _update_position_states() 또는 exit handler에서
if state_changed:
    # Immediate flush for state transitions (no throttle)
    self._state_publisher.publish_positions_update(
        [position], throttle=0,
    )
```

이렇게 하면:
- 일반 가격 업데이트: 기존 2초 throttle 유지 (성능 보존)
- 상태 전환: 즉시 플러시 (크래시 시 상태 유실 방지)

### 2.3 Shutdown Timeout Configuration (P2)

`stop()` 실행에 타임아웃을 추가하여 stuck shutdown 방지:

```python
async def stop(self, timeout: float = 10.0):
    """거래 종료 (타임아웃 포함)"""
    try:
        await asyncio.wait_for(self._stop_impl(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Graceful shutdown timed out after {timeout}s, forcing...")
        # 최소한 Redis flush만이라도 실행
        if self._position_tracker and self._state_publisher:
            self._state_publisher.publish_positions_update(
                list(self._position_tracker.positions), throttle=0,
            )
        self.state = TradingState.STOPPED
        self._running = False
```

---

## 3. Implementation Plan

| # | 파일 | 변경 | 난이도 | 우선순위 |
|---|------|------|--------|----------|
| 1 | `cli/main.py` | `sts trade start` — signal handler + finally stop() | Low | P0 |
| 2 | `cli/main.py` | `sts rl paper` — signal handler + finally stop() | Low | P0 |
| 3 | `scripts/cron/rl_paper.sh` | `sleep 2` → `sleep 5` | Low | P0 |
| 4 | `scripts/cron/stock_trading.sh` | `sleep 2` → `sleep 5` | Low | P0 |
| 5 | `scripts/cron/futures_trading.sh` | `sleep 2` → `sleep 5` | Low | P0 |
| 6 | `services/trading/orchestrator.py` | State transition immediate flush | Medium | P1 |
| 7 | `services/trading/orchestrator.py` | `stop()` timeout wrapper | Low | P2 |

### 상세 구현

#### Step 1: CLI Signal Handlers (`cli/main.py`)

`sts trade start` (line ~1050):

```python
import signal

@trade.command("start")
# ... 기존 옵션들 ...
def start(strategy, asset, capital, paper, daemon):
    # ... 기존 config/orchestrator 생성 ...

    async def run():
        loop = asyncio.get_running_loop()
        shutdown_requested = False

        def _request_shutdown():
            nonlocal shutdown_requested
            if shutdown_requested:
                return
            shutdown_requested = True
            logger.info("Shutdown signal received, stopping gracefully...")
            asyncio.ensure_future(orchestrator.stop())

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _request_shutdown)

        try:
            if daemon:
                await orchestrator.run()
            else:
                await orchestrator.run_session()
        finally:
            if not shutdown_requested:
                await orchestrator.stop()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass  # Signal handler already initiated shutdown
```

`sts rl paper` (line ~1660) — 동일 패턴 적용.

#### Step 2: Cron Script Timeout 증가

```bash
# rl_paper.sh, stock_trading.sh, futures_trading.sh
stop_trading() {
    # ... PID 찾기 ...
    kill "$PID" 2>/dev/null || true
    sleep 5      # graceful shutdown 대기 (기존 2초)
    # 여전히 살아있다면 강제 종료
    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID" 2>/dev/null || true
        log "Force killed (SIGKILL)"
    else
        log "Graceful shutdown completed"
    fi
}
```

#### Step 3: State Transition Flush (`orchestrator.py`)

exit handler에서 position 상태가 변경될 때 즉시 플러시:

```python
# check_exit 결과 처리 후 (현재 throttle=2.0 update 위치 근처)
async def _handle_exit(self, ...):
    # ... 기존 exit 처리 ...

    # State transition → immediate flush
    positions_with_state_change = [
        p for p in self._position_tracker.positions
        if p._state_changed  # 또는 별도 tracking
    ]
    if positions_with_state_change and self._state_publisher:
        self._state_publisher.publish_positions_update(
            positions_with_state_change, throttle=0,
        )
```

대안 (더 간단): throttle를 2.0 → 0.5로 줄이기. 성능 영향 미미 (Redis HSET은 ~0.1ms).

---

## 4. 영향 범위

### 변경되는 동작

| Before | After |
|--------|-------|
| SIGTERM → 즉시 종료 | SIGTERM → graceful stop() → 종료 |
| Ctrl+C → "Trading stopped" 출력만 | Ctrl+C → graceful stop() → 종료 |
| Cron stop → 2초 대기 → SIGKILL | Cron stop → 5초 대기 → SIGKILL (if needed) |
| State 전환 → 2초 내 Redis 반영 | State 전환 → 즉시 Redis 반영 |

### 변경되지 않는 동작

- 포지션 복구 로직 (`_recover_positions_from_redis()`) — 변경 없음
- Redis 직렬화 스키마 — 변경 없음
- Freshness 필터 — 변경 없음
- 백테스트 — 영향 없음

---

## 5. Testing Plan

### Unit Tests

1. **test_signal_handler_calls_stop** — SIGTERM mock → `stop()` called
2. **test_stop_idempotent** — 이중 호출 시 에러 없음 (이미 구현됨)
3. **test_state_transition_flush** — SURVIVAL→BREAKEVEN → throttle=0 flush 확인

### Manual Verification

```bash
# 1. Signal handler 테스트
sts trade start --asset stock --paper &
PID=$!
sleep 10
kill $PID           # SIGTERM
# → 로그에 "Stopping trading..." + "Positions flushed" 확인

# 2. Cron stop 테스트
scripts/cron/stock_trading.sh stop
# → 로그에 graceful shutdown 메시지 확인
```

---

## 6. Risk Assessment

| 리스크 | 확률 | 영향 | 완화 |
|--------|------|------|------|
| `stop()` timeout (10s 초과) | Low | Cron SIGKILL → 기존과 동일 동작 | timeout wrapper가 최소 Redis flush 보장 |
| Signal handler 중복 호출 | Low | 이중 stop() | `shutdown_requested` flag로 방어 |
| asyncio.run() 내 signal handler 충돌 | Very Low | event loop 에러 | `loop.add_signal_handler()` 는 asyncio 공식 API |

---

## 7. Summary

**변경 규모**: 3개 Python 파일 + 3개 cron 스크립트 (각 ~10줄 변경)
**핵심 개선**: SIGTERM/SIGINT 시 graceful shutdown 보장
**위험도**: 매우 낮음 (기존 `stop()` 재활용, 새 로직 최소)
**즉시 효과**: 매일 cron stop 시 position flush 보장 → stale data 제거
