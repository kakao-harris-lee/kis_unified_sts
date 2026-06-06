# Orchestrator Futures Live-Mode Guard (F-7) — Design

- Date: 2026-06-06
- Status: Design (pending implementation plan)
- Parent effort: futures decoupling assessment ([[futures-decoupling-state]]); the F-1..F-9 roadmap's **F-7** (highest-priority, decoupling-independent safety fix)
- Scope: **F-7 — wire `LiveModeGuard` into the monolithic orchestrator's futures real-order path** so a real futures order can never be placed unless `futures_live.enabled` is true AND not runtime-suspended. Closes the gap where the path that actually trades futures today ignores the live-money gate.

## 1. Goal & scope

**The gap (verified).** Futures trades today exclusively via the monolithic `TradingOrchestrator` (in-process). Its real-order path (`OrderExecutor`) has **zero** references to `LiveModeGuard` / `futures_live.enabled` / `futures:live:suspended` — the two-layer live-money gate the project relies on is checked **only** in the dormant `order_router` daemon (`services/order_router/main.py:184-185`), which is NOT the active futures trade path. So if the orchestrator is run with real KIS credentials and `paper_trading=False`, neither the YAML gate nor the Redis suspend flag stops it from placing real orders.

**The fix.** Insert a `LiveModeGuard` check in the orchestrator's real-order **entry** branch for futures, before `OrderExecutor.execute_order`. When live is suspended (the default — `futures_live.enabled=false`), the real entry is blocked (no order placed, logged + alerted, returns not-filled). This enforces the already-intended Phase-5 state ("futures paper-only until Gate 3") in the path that actually trades, and makes the operator's futures-paper model (real WS market data + `VirtualBroker` local fills + zero real orders) safe against a misconfigured real run.

**Success criterion:** the orchestrator never places a real futures **entry** order while `LiveModeGuard.is_live_suspended` is true (config-disabled, Redis-suspended, or fail-closed on Redis error); real entries are allowed only when explicitly enabled + not suspended; `paper_trading=True` (VirtualBroker) and non-futures paths are unaffected; default config blocks all real futures entries.

비목표(out of scope): the local-DB orderbook / paper-engine changes (the existing real-WS-orderbook + VirtualBroker + SQLite-ledger already satisfies the operator's "real data + local virtual fills" model — confirmed); gating **exit** real orders (see §4 — exits close existing real risk and cannot fire without a guarded entry); the order_router daemon (already gated); the broader futures decoupling (F-1/F-3/etc.); position-size/daily-trade limits (LiveModeGuard has fields for these but order_router owns them — F-7 only uses `is_live_suspended`).

## 2. Locked decisions (브레인스토밍 2026-06-06)

| 결정 | 선택 | 근거 |
|---|---|---|
| F-7 형태 | **LiveModeGuard 안전 배선만** (paper/오더북 변경 없음) | 실데이터+VirtualBroker+SQLite ledger 모델은 이미 동작; F-7은 실주문 차단 가드만 |
| 가드 범위 | **실주문 진입 분기만** (청산 비가드) | 진입 가드되면 실포지션 미생성→청산 분기 발화 불가; 청산은 risk-reduction이라 차단 안 함 |
| 자산 | **futures 전용** | LiveModeGuard는 선물 config(`futures_live.yaml`); stock은 paper·M5e 차단 |
| 기본값 | **차단(enabled=false 기본)** + fail-closed | 현 Phase-5 paper-only 상태를 orchestrator에 강제; redis 오류→suspended |
| 머지 안전 | **지금 머지 가능** | 기본 차단 = 현 실태(선물 paper-only)와 일치, paper 모델 무영향 |

## 3. Current state (감사 2026-06-06)

- **`LiveModeGuard`** (`shared/execution/live_mode_guard.py`): `ServiceConfigBase` from `futures_live.yaml::futures_live`. `enabled: bool=False`, `suspend_key="futures:live:suspended"`. `async is_live_suspended(redis) -> bool` → True(차단) if `not enabled` OR redis suspend_key truthy OR redis 오류(fail-closed).
- **order_router 참조 패턴**: `LiveModeGuard.from_yaml()` (`order_router/main.py:338`) → `await self.live_mode_guard.is_live_suspended(self.redis)` 전 주문 (184-185).
- **orchestrator 주문 경로**: `_place_entry_order` (`orchestrator.py:6789`): paper 분기 `if self.config.paper_trading and self._paper_broker` (6800, VirtualBroker) / 실 분기 `if self._order_executor is not None` (6838, `await self._order_executor.execute_order` 6858). exit `_place_exit_order` 동일 구조(paper 7334 / 실 7353). **LiveModeGuard 참조 0건**(grep).
- **async redis**: orchestrator는 `self._stream_redis = aioredis.from_url(...)` (1363, 스트림 모드 시 생성). sync `RedisClient.get_client()`도 사용. `is_live_suspended`는 `await redis.get` → **async redis 필요**.
- **선물 is_real 하드코딩**: `_init_kis_client`가 선물은 항상 `is_real=True`(주석 "모의서버는 선물 시세 미지원"). `paper_trading`은 별개(VirtualBroker 선택). 즉 실데이터+VirtualBroker가 현 paper 모델.
- **Phase-5**: `config/futures_live.yaml::enabled: false`, futures paper-only until Gate 3.

## 4. Why entries-only (not exits)

LiveModeGuard의 목적은 **신규 실리스크 차단**이다. 실 진입을 차단하면 실포지션이 생성되지 않으므로 실 청산 분기는 발화할 일이 없다(청산은 기존 포지션에만 발화). 반대로 청산을 차단하면 (운영자가 라이브 중 suspend한 엣지에서) 실포지션이 고립될 수 있다. 따라서 **진입 차단 + 청산 허용**이 "신규 리스크 차단 + 기존 리스크 축소 허용"으로 가장 안전하다. order_router도 진입/bracket을 가드한다. 비상 청산은 kill-switch flatten 경로가 별도로 담당한다.

## 5. Components & flow

### 5.1 LiveModeGuard + redis 주입 (orchestrator init)
- orchestrator init에서 `self._live_mode_guard = LiveModeGuard.from_yaml()` **항상 생성**(`from_yaml` 저렴·무I/O; config 없으면 enabled=False 기본 → 차단). guard None일 fail-open 경로 제거.
- 가드용 async redis 핸들 확보: `self._stream_redis`(있으면) 재사용, 없으면 가드 전용 경량 `redis.asyncio` 클라이언트를 init에서 1회 생성(`REDIS_URL`). 핸들 누락 시 차단(fail-closed) 취급.

### 5.2 테스트 가능 헬퍼
```python
async def _live_order_suspended(self) -> bool:
    """True if a real futures order must be refused (live disabled/suspended).

    Always fail-closed: a missing guard or redis handle, or a redis error,
    returns True (block). Only meaningful for the real-execution branch.
    """
    guard = self._live_mode_guard
    if guard is None:
        return True
    redis = self._guard_redis  # _stream_redis or dedicated async client
    if redis is None:
        return True
    return await guard.is_live_suspended(redis)
```

### 5.3 가드 배치 (진입 실주문 분기)
`_place_entry_order` 실 분기(6838, `if self._order_executor is not None`), `execute_order`(6858) **직전**:
```python
    if self._order_executor is not None:
        if self.config.asset_class == "futures" and await self._live_order_suspended():
            logger.warning(
                "futures live suspended — real ENTRY blocked "
                "(futures_live.enabled=%s, set true + clear %s to enable)",
                getattr(self._live_mode_guard, "enabled", None),
                getattr(self._live_mode_guard, "suspend_key", "futures:live:suspended"),
            )
            self._notify_live_blocked(code)   # best-effort Telegram (fire-and-forget)
            return False, 0.0, 0, None        # not-filled; NO real order placed
        # ... existing real execution (venue select, execute_order) ...
```
- 미체결 반환은 orchestrator의 기존 미체결 처리 경로를 그대로 탄다(신규 분기 불필요).
- **청산 분기(7353)는 변경 없음**(§4).

### 5.4 동작
- 기본 `futures_live.enabled=false` → 모든 실 선물 진입 차단.
- `paper_trading=True` → VirtualBroker 분기(6800)만 → 가드 unreached → paper 모델 무영향.
- `asset_class != "futures"` → 가드 미적용.
- 라이브 전환: `futures_live.enabled=true` + `redis-cli -n 1 del futures:live:suspended` → 허용(order_router와 동일 게이트).

## 6. Error handling · cost
- **fail-closed**: guard/redis 누락·오류 → 차단(§5.2). fail-open 경로 없음.
- 비용: 실 진입당 redis GET 1회(실행 모드에서만; paper·non-futures는 0).
- 차단 = 미체결 반환 + log(WARNING) + best-effort Telegram(알림 실패가 차단을 방해하지 않음).

## 7. Testing
- **단위 `_live_order_suspended`**(fakeredis async + `LiveModeGuard`):
  - enabled=True + redis 미suspend(get→None) → False(허용)
  - enabled=False → True(차단)
  - enabled=True + suspend_key truthy → True
  - enabled=True + redis 오류 → True(fail-closed)
  - guard None / redis None → True(fail-closed)
- **가드 준수(진입 실분기)**: asset=futures·paper_trading=False·mock `order_executor`·`_live_mode_guard=LiveModeGuard(enabled=False)`+fakeredis → `_place_entry_order` → **execute_order 미호출 + (False,0.0,..) 반환**. enabled=True+미suspend → execute_order 호출(가드 비차단). (full path 의존 최소화 위해 필요한 부분만 mock.)
- **paper 무영향**: paper_trading=True → VirtualBroker, 가드 미consult.
- **선물 전용**: asset=stock 실분기 → 가드 미적용(execute_order 호출).
- **회귀**: 기존 orchestrator 테스트 green. full gate.

## 8. Acceptance criteria
- [ ] 실 선물 **진입** 차단: enabled=false / suspended / redis 오류(fail-closed); enabled+미suspend면 허용.
- [ ] **청산 비가드**(7353 변경 없음).
- [ ] `paper_trading=True`·`asset != futures` 무영향.
- [ ] 차단 시 execute_order 미호출 + 미체결 반환 + WARNING 로그 + best-effort Telegram.
- [ ] `LiveModeGuard` 항상 생성(기본 enabled=False), guard/redis 누락→차단(fail-open 경로 없음).
- [ ] 단위(`_live_order_suspended` 매트릭스 + 진입 가드 준수 + paper/stock 무영향) + 회귀 green.
- [ ] order_router/`LiveModeGuard`/`futures_live.yaml` 로직 무변경(orchestrator 배선만).

### 운영 검증
`futures_live.enabled=false`(기본)에서 orchestrator를 `paper_trading=False`로 기동 → 실 선물 진입 시그널이 "live suspended — blocked" 로그 + 미체결. `enabled=true` + suspend 해제 시 정상 진입.

## 9. Open questions (구현 계획에서 확정)
- 가드용 redis: `_stream_redis` 재사용 vs 전용 async client(스트림 모드 아닐 때도 가드 필요하므로 **전용 생성 또는 항상 생성** 권장).
- `_notify_live_blocked` 구현: 기존 orchestrator notifier 재사용(중복 알림 방지 위해 per-code/throttle 고려, 또는 단순 WARNING+1회 알림).
- 테스트 위치: 기존 orchestrator 테스트 파일(`tests/unit/trading/test_orchestrator*.py`) 추가 vs 신규 `test_orchestrator_live_guard.py`(신규 권장 — 격리).
- exit 가드를 **명시적으로 비대상**으로 둘지(§4) 코멘트로 코드에 남길지(권장 — 의도 문서화).
