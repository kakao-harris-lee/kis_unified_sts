# Daily Risk Reset Cron (M5c) — Design

- Date: 2026-06-06
- Status: Design (pending implementation plan)
- Parent effort: `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md` (M5 cutover)
- Predecessors merged: M5a stock monitor bridge (#419), M5b LLM context cron (#420)
- Scope: **M5c — the third M5 sub-project.** A small idempotent cron that calls the existing `RuntimeRiskState.reset_daily()` for stock + futures at the KST session boundary, so the decoupled M4 pipeline's daily risk counters actually reset each trading day.

## 1. Goal & scope

The decoupled pipeline's risk state — `RuntimeRiskState` (Redis `risk:state:{asset}`) — accumulates daily counters (`daily_trade_count`, `daily_pnl_krw`) that M4-X writes (`record_trade`) and M4-R reads for gating (`DailyTradeCountFilter`, `DailyMDDFilter`). The class already has `reset_daily()` + `should_reset_daily()`, **but nothing calls them** — so the daily counters never reset, and after N trades the M4-R daily-cap / daily-MDD filters block all entries permanently. M5c provides the missing scheduled reset.

**Success criterion:** A single-shot cron (`scripts/maintenance/daily_risk_reset.py`) that, at ~08:59 KST Mon–Fri (1 min before the 09:00 session open), resets the daily risk counters for **stock + futures** by calling the **unchanged** `RuntimeRiskState.reset_daily()`, guarded by `should_reset_daily()` so a mid-day re-run never wipes the session's accumulated counters. `RuntimeRiskState`, the M4 daemons, and the orchestrator are **unchanged** — M5c is a thin standalone caller.

비목표(out of scope): any change to `RuntimeRiskState`/the M4 daemons/the orchestrator; resetting `consecutive_losses` or `weekly_pnl_krw` (preserved by design); a shadow/live mode gate (see §4 — no live-key conflict exists); snapshot/rollover of yesterday's daily stats (the SQLite trade ledger already records per-trade history); a long-running daemon / Prometheus pull endpoint (cron is short-lived; see §6).

## 2. Locked decisions (브레인스토밍 2026-06-06)

| 결정 | 선택 | 근거 |
|---|---|---|
| 배치 | **Cron 스크립트** (not a daemon) | 하루 1회 멱등 리셋 = cron 교과서. M5b와 동일 패턴 |
| 자산 범위 | **stock + futures 둘 다** | 양쪽 decoupled 데몬(M4-R/M4-X stock; risk_filter/kill_switch futures)이 `RuntimeRiskState`를 쓰고 동일 daily 리셋 필요. futures 미가동 시 리셋은 멱등·무해 no-op |
| mode 게이트 | **없음** | `risk:state:{asset}`는 decoupled 파이프라인 전용(orchestrator 무관) → live-key 충돌 없음. shadow/live 동일 키 → mode-agnostic. crontab 설치가 opt-in |
| 리셋 시맨틱 | **`reset_daily`/`should_reset_daily` 무변경 재사용** | 시맨틱 이미 구현·테스트됨; M5c는 스케줄 호출만 |
| 멱등 가드 | **`should_reset_daily` 필수** | 장중 우발 재실행이 누적 카운터를 0으로 날리는 것 방지 |

## 3. Current state (감사 2026-06-06)

- **`RuntimeRiskState`** (`shared/risk/runtime_state.py:31`): `__init__(*, redis, asset_class="futures")` (async redis). Daily 필드 `daily_pnl_krw`/`daily_trade_count`(리셋 대상), 보존 `consecutive_losses`/`weekly_pnl_krw`. `async reset_daily(*, now_kst)` → daily 2필드 0 + `risk:state:{asset}:meta` HASH의 `last_reset_date_kst`=오늘 + meta TTL 7d. `async should_reset_daily(*, now_kst) -> bool` → meta의 last_reset != today.
- **호출자 없음 (핵심 갭)**: `reset_daily`/`should_reset_daily`는 런타임 어디서도 호출되지 않음(grep 확정). orchestrator도, 어떤 cron도 호출 안 함 → decoupled 리스크 카운터가 누적만 됨.
- **쓰기**: M4-X (`services/stock_exit/daemon.py:150` `record_trade`/`record_win`/`record_loss`). **읽기**: M4-R stock(`services/stock_risk_filter/`), futures(`services/risk_filter/`), `services/kill_switch/`. **모두 `RuntimeRiskState(redis, asset_class=...)`로 unsuffixed `risk:state:{asset}` 사용**.
- **orchestrator 무관 (검증)**: `grep RuntimeRiskState services/trading/orchestrator.py` → 없음. orchestrator는 레거시 in-memory `shared/risk/manager.py::RiskManager`(sync `reset_daily`)를 쓰며 `risk:state:{asset}` Redis 키를 건드리지 않음. → M5c 리셋이 orchestrator를 clobber하지 않음.
- **M4-R 게이팅 소비**: `DailyTradeCountFilter`(daily_trade_count ≥ max → 차단), `DailyMDDFilter`(daily_pnl_krw 손실 한도 → 차단), `ConsecutiveLossFilter`(보존), `WeeklyMDDFilter`(보존). → daily 2필드의 매일 0 리셋이 정확히 필요.
- **redis**: async client (RuntimeRiskState가 `await`). decoupled 데몬은 `redis.asyncio.from_url(REDIS_URL, db=1)`(M4 main.py 패턴). DB 1 필수.
- **스크립트 위치**: `scripts/cron/`는 gitignore(shell). committed Python은 `scripts/maintenance/`(존재, `tests/unit/scripts/maintenance/`도 존재) — implicit namespace package.

## 4. Why no shadow/live mode

M5a/M5b는 standalone 발행이 orchestrator의 **live 키를 clobber할 수 있어** `TRADING_STATE_KEY_SUFFIX` 격리가 필요했다. M5c의 `risk:state:{asset}`는 **decoupled M4 파이프라인 전용**(§3 — orchestrator는 in-memory RiskManager 사용)이라 clobber할 live 카운터파트가 없다. decoupled 파이프라인은 shadow/live 둘 다 같은 `risk:state:{asset}`를 쓰므로 M5c는 **mode-agnostic** — 그냥 리셋한다. crontab 항목 설치가 opt-in(M5b와 동일). → 코드 mode 게이트 없음.

또한 M5c는 **컷오버 전부터 필요**하다: M4 shadow 파이프라인이 가동되면 `daily_trade_count`가 무한 누적돼 며칠 뒤 M4-R 게이팅이 영구 차단된다. M5c를 지금(M4 shadow와 함께) 설치해야 shadow 검증이 다일 단위로 정상 작동한다 — 단순 컷오버 prep 이상의 prerequisite다.

## 5. Target architecture

### 5.1 컴포넌트
신규 `scripts/maintenance/daily_risk_reset.py` — 단발 cron. 기존 `RuntimeRiskState.reset_daily`/`should_reset_daily` 무변경 재사용.

### 5.2 흐름 (1회 실행, 08:59 KST)
```
now_kst = datetime.now(ZoneInfo("Asia/Seoul"))   # 주입 가능(테스트)
redis = redis.asyncio.from_url(REDIS_URL, db=1)
rc = 0
for asset in _assets():                            # ("stock", "futures")
    try:
        rs = RuntimeRiskState(redis=redis, asset_class=asset)
        if await rs.should_reset_daily(now_kst=now_kst):   # 멱등 가드(핵심)
            await rs.reset_daily(now_kst=now_kst)           # daily_pnl/trade_count -> 0
            logger.info("reset %s daily risk counters (date=%s)", asset, now_kst.date())
        else:
            logger.info("%s already reset today; skipping", asset)
    except Exception:
        logger.exception("daily risk reset failed asset=%s", asset)
        rc = 1
await redis.aclose()
return rc
```

### 5.3 멱등 가드 (안전의 핵심)
`should_reset_daily`(meta `last_reset_date_kst != today`)로 가드 → 08:59 첫 실행만 리셋, 같은 날 재실행(우발 cron·수동·재시작)은 skip → **장중 누적 카운터를 0으로 날리지 않음**. 가드 없는 무조건 reset은 위험.

### 5.4 구조 (테스트 가능)
- `_assets() -> tuple[str, ...]` — `("stock", "futures")` (하드코딩; 멱등·무해라 config 불필요, YAGNI)
- `async reset_asset(redis, asset, *, now_kst) -> bool` — RuntimeRiskState 생성, should_reset→reset; 리셋 여부 반환
- `async run_reset(*, now_kst=None) -> int` — redis 빌드, 자산 루프(per-asset try/except), aclose, rc 반환
- `main() -> int` — logging.basicConfig + asyncio.run(run_reset())

### 5.5 crontab 스케줄 (KST native, `CRON_TZ=Asia/Seoul` — 운영자 관리, 스크립트는 repo)
```cron
# 개장 1분 전 — daily 리스크 카운터 리셋 (09:00 세션 시작 전)
59 8 * * 1-5  /home/deploy/project/kis_unified_sts/.venv/bin/python -m scripts.maintenance.daily_risk_reset
```

## 6. Error handling · cost · observability

### 6.1 에러처리
| 상황 | 정책 |
|------|------|
| 자산별 리셋 성공 | log |
| 자산 1개 실패(Redis 등) | log.exception + **rc=1**, 나머지 자산은 계속 시도(per-asset 격리) |
| 전체 연결 실패 | uncaught/rc=1 → **exit 1 (cron-mail)** |
| 같은 날 재실행 | should_reset_daily=False → skip(카운터 보존) |

리셋 실패는 운영상 중대(다음 세션 M4-R 게이팅 오작동: 실거래 차단 or 한도 미적용) → **exit 1**(M5b의 transient→exit 0과 다름).

### 6.2 cost
자명 — Redis HASH load/save + hset/expire(자산당 ~3 ops), OpenAI/외부 없음. 무시 가능.

### 6.3 관측성
단발 cron → Prometheus pull 불가(M5b §6.4와 동일). 관측 = **로그 + `risk:state:{asset}:meta`의 `last_reset_date_kst`**(ops-monitor가 오늘 리셋 확인). cheap freshness.

## 7. Testing (fakeredis async — 외부 의존 없음)
- **단위**: should_reset True(신규일) → daily_pnl_krw·daily_trade_count **0**, meta=today, **consecutive_losses·weekly_pnl_krw 보존** · should_reset False(오늘 이미) → 카운터 **미변경**(장중 재실행 안전) · stock+futures 둘 다 리셋 · 자산 1개 redis 실패 → rc=1 + 나머지 리셋(격리) · now_kst 주입 결정성.
- **통합**(선택): run_reset(now_kst) over fakeredis async + 사전 누적 카운터 → 실행 후 daily 0 / 보존 필드 유지 / meta=today.
- **회귀**: `RuntimeRiskState`/M4 데몬 무변경 → 기존 `tests/unit/risk/test_runtime_state.py` 등 green. full gate.

## 8. Acceptance criteria
- [ ] stock+futures의 `daily_pnl_krw`·`daily_trade_count`를 0으로 리셋, `risk:state:{asset}:meta` `last_reset_date_kst`=today.
- [ ] `consecutive_losses`·`weekly_pnl_krw` **보존**.
- [ ] 멱등(`should_reset_daily` 가드) — 장중 재실행은 no-op(누적 카운터 미손상).
- [ ] per-asset 에러 격리; 어느 자산이든 실패 시 **exit 1**(cron-mail).
- [ ] `RuntimeRiskState`/M4 데몬/orchestrator **무변경**(순수 신규 스크립트).
- [ ] crontab 문서화(`59 8 * * 1-5` KST, `CRON_TZ=Asia/Seoul`).
- [ ] 외부(OpenAI 등) 호출 없음 — Redis만. now_kst 주입으로 테스트 결정적.

### 운영 검증
실행 후 `redis-cli -n 1 hget risk:state:stock:meta last_reset_date_kst` = today, `hget risk:state:stock daily_trade_count` = 0(또는 미존재).

## 9. Open questions (구현 계획에서 확정)
- crontab 정확 시각(08:59 vs 08:58 — 09:00 세션·M4 데몬 기동 08:55와의 순서). 08:59 권장(데몬 기동 후, 개장 전).
- 스크립트 테스트 위치(`tests/unit/scripts/maintenance/` — 디렉토리 존재 확인됨).
- `_assets()` env override 여부(default `("stock","futures")`; YAGNI로 하드코딩 권장).
- 도큐: crontab 권장 항목을 어느 runbook에 기록할지(M5b와 함께 ops runbook follow-up).
