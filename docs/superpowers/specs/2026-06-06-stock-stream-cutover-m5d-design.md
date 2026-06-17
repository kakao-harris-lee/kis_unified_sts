# Stock Stream Cutover (M5d) — Design

- Date: 2026-06-06
- Status: Design (pending implementation plan)
- Parent effort: `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md` (M5 cutover)
- Predecessors merged: M5a monitor bridge (#419), M5b LLM context cron (#420), M5c daily risk reset cron (#421)
- Scope: **M5d — the fourth M5 sub-project, the live cutover.** The operator runbook + a verification script + a rollback script that flip stock paper trading from the monolithic orchestrator to the decoupled M4 pipeline (M4-P → M4-R → M4-O → M4-X) + M5a/M5b/M5c.

> 2026-06-06 update: the implementation target moved from host `systemd` units
> to Docker Compose profiles. Treat the `systemctl` command examples below as
> historical design context; the active operator runbook is
> `docs/runbooks/stock-pipeline-cutover-m5d.md`, and the compose migration plan is
> `docs/plans/archive/2026-06-06-compose-pipeline-services.md`.

## 1. Goal & scope

The decoupled stock pipeline (M4-P/R/O/X) and its supporting cutover infra (M5a monitor, M5b LLM context cron, M5c daily risk reset cron) are all built, merged, and running default-off/shadow. M5d makes the decoupled pipeline the LIVE stock path: stop the orchestrator's stock process, flip each daemon shadow→live (which switches it from `.shadow` to unsuffixed streams), and document a gated, reversible procedure with health verification and a one-command rollback.

**Critical framing — paper→paper, no real-money risk.** Stock trading is paper (CLAUDE.md). M4-O executes via `VirtualBroker` (`shared/paper/broker.py`, in-memory) in **both** shadow and live — the only difference between shadow and live is the **stream suffix** (`.shadow` vs unsuffixed), which is the isolation boundary. So the cutover carries no real-money risk; the risks are **operational**: silent stop (decoupled pipeline trades nothing and nobody notices), double-trading (orchestrator + decoupled both active), and no halt mechanism for a misbehaving decoupled pipeline.

**Success criterion:** (a) a Phase-5-style runbook (`docs/runbooks/stock-pipeline-cutover-m5d.md`) with prerequisites → shadow-validation gate → operator approval → cutover sequence → post-cutover verification → rollback; (b) a read-only, mode-aware verification script (`scripts/ops/stock_cutover_verify.py`) that confirms decoupled-pipeline health in shadow (pre-cutover gate) and live (post-cutover check); (c) a rollback script (`scripts/ops/stock_cutover_rollback.sh`) that stops the decoupled daemons and restores the orchestrator. **No new trading code** — M4/orchestrator are unchanged; verify.py is read-only; rollback.sh is operational.

비목표(out of scope): any change to the M4 daemons / orchestrator / RuntimeRiskState; a kill-switch consumer for the decoupled stock pipeline (manual `docker compose stop stock-*` is the paper-grade halt — deferred); migrating the orchestrator's open positions (operator decision: flatten + abandon, see §4); cleaning up residual paper-account positions (documented follow-up); M5e (orchestrator reduction to supervisor/health — separate, after the cutover proves stable).

## 2. Locked decisions (브레인스토밍 2026-06-06)

| 결정 | 선택 | 근거 |
|---|---|---|
| 산출물 | **런북 + 검증 스크립트 + 롤백 스크립트** | flag-flip + Compose 중심 운영. 검증/롤백 스크립트가 반복·안전성 부여. 신규 트레이딩 코드 없음 |
| 포지션 연속성 | **전부 청산 + decoupled fresh 시작** (마이그레이션 없음) | 운영자: "현 모의투자 데이터 무의미, 잔여 계좌 포지션은 후속 정리". M4-X가 orchestrator 레코드를 skip(포맷 상이)하는 문제를 클린 슬레이트로 회피 |
| kill-switch 소비자 | **defer** | paper라 수동 `docker compose stop stock-*`이 사실상 halt. 별도 prerequisite |
| orchestrator 정지 | **전체 정지** (stock_trading.sh stop + cron 비활성) | stock orchestrator는 stock 전용 별도 크론(futures와 독립) → 전체 정지 깔끔, 이중거래 방지 |
| 검증 스크립트 | **Python, read-only, mode-aware** | Redis 헬스 로직 → 테스트 가능(fakeredis). shadow/live 양쪽 재사용 |
| 롤백 | **shell 스크립트 + 런북** | compose/process 오케스트레이션 → shell(promote_live.sh 스타일), `--dry-run` |

## 3. Current state (감사 2026-06-06)

- **Orchestrator stock 경로**: `scripts/cron/stock_trading.sh` — `sts trade start --asset stock --paper --daemon`(long-running setsid, PID `pids/stock_trading.pid`). cron: 08:55 start / 16:00 stop / 5분 watchdog(09:00–15:55). **stock 전용**(futures는 `futures_trading.sh` 별도 프로세스). 정지=`stock_trading.sh stop`(SIGTERM→5s→SIGKILL).
- **M4 데몬 flag**: `STOCK_STRATEGY_DAEMON`(M4-P) / `STOCK_RISK_FILTER`(M4-R) / `STOCK_ORDER_ROUTER`(M4-O) / `STOCK_EXIT_DAEMON`(M4-X) = off(기본)/shadow/live. 각 `main.py`의 `_resolve_mode()` + `_streams_for(mode)`(shadow→`.shadow`, 그 외→unsuffixed). **flag 1개 flip(shadow→live)으로 unsuffixed 스트림 전환.**
- **M4-O 실행**: `VirtualBroker`(`shared/paper/broker.py`, in-memory paper) — **shadow·live 동일**. 차이는 스트림 suffix뿐. FillLogger/RuntimeLedger 동일.
- **systemd**: `deploy/systemd/kis-stock-{strategy-daemon,risk-filter,order-router,exit-daemon}.service` + `kis-stock-monitor-daemon.service`(M5a) — DISABLED 배포, `Environment=STOCK_*_DAEMON=shadow`.
- **M5a**: `STOCK_MONITOR_DAEMON`(off/shadow/live), `services/stock_monitor/main.py`. **M5b**: `STOCK_LLM_CONTEXT`(crontab) + orchestrator `config/llm.yaml::market_context_publisher.enabled`(true). **M5c**: `scripts/maintenance/daily_risk_reset.py`(crontab, mode 무관).
- **스트림/키**(stock): `signal.candidate.stock[.shadow]`, `signal.final.stock[.shadow]`, `order.fill.stock[.shadow]`, `stock:daemon:positions`(M4 working-store hash), `trading:stock:positions[:shadow]`(dashboard hash), `trading:stock:market_context[:shadow]`, `risk:state:stock`+`:meta`. consumer groups: `stock_risk_filter`, `stock_order_router`, `stock_monitor`; M4-X polls the daemon positions hash.
- **flatten 스크립트**: `scripts/trading/flatten_all.py`(오픈 포지션 청산 — 런북에서 선택적 사용).
- **kill_switch**: `services/kill_switch/`(futures 경로). decoupled stock halt 소비자 미배선 → 수동 systemctl stop으로 대체(범위 밖).
- **기존 런북 패턴**: `docs/runbooks/futures-paradigm-{operations,rollback}.md`, `phase5-verification.md`(게이트). M5d 런북이 미러링.
- **scripts/ops/**: `live_preflight.sh`, `promote_live.sh` 등 — 컷오버 스크립트 위치.

## 4. Position handling at cutover (운영자 결정)

stock은 EOD 청산 안 함(다일 보유) → 컷오버 시 orchestrator가 오픈 paper 포지션 보유 가능. M4-X는 `stock:daemon:positions`를 읽고 dashboard `trading:stock:positions`와 분리된다. **운영자 결정**: 현 모의투자 데이터는 무의미하므로 **마이그레이션·보존 없이 전부 청산하고 decoupled를 fresh 시작**. 잔여 모의투자 계좌 포지션은 **후속 정리**(M5d 범위 밖).

→ 컷오버 시: (선택)`flatten_all.py`로 orchestrator 포지션 청산 → orchestrator 정지 → **`del stock:daemon:positions trading:stock:positions`**(daemon working-store + live dashboard snapshot clean) → decoupled fresh 시작.

## 5. Components

### 5.1 검증 스크립트 `scripts/ops/stock_cutover_verify.py`
read-only, mode-aware(`--mode shadow|live` → suffix `.shadow`/``), pass/fail + per-check 리포트, exit 0(healthy)/1(critical fail). 테스트 가능(fakeredis async).

체크(suffix 적용):
| 체크 | 내용 | critical |
|------|------|:---:|
| 스트림 + consumer group | `signal.candidate.stock{sfx}`/`signal.final.stock{sfx}`/`order.fill.stock{sfx}` 존재 + 기대 group(`stock_risk_filter`/`stock_order_router`/`stock_monitor`) XINFO GROUPS 연결. M4-X는 positions hash polling daemon이라 systemd liveness로 확인 | ✅ |
| 리스크 상태 신선도 | `risk:state:stock` 존재 + `:meta` `last_reset_date_kst`==today(M5c) | ✅ |
| 시장 컨텍스트 | `trading:stock:market_context{sfx}` 존재 + `generated_at` 파싱 | ⚠️(warn) |
| 포지션 해시 | `stock:daemon:positions` + `trading:stock:positions{sfx}` 개수(informational) | — |
| (옵션 `--strict`) 스트림 recency | 장중 last-id ms가 N분 내(장 외 면제) | ⚠️ |

구조: `_suffix(mode)` / `async check_streams(redis, sfx)` / `check_risk_freshness(redis, now_kst)` / `check_market_context(redis, sfx)` / `check_positions(redis, sfx)` / `async run_verify(*, mode, now_kst=None, redis_client=None) -> int` / `main()`. process liveness(`systemctl is-active`)는 런북이 별도.

### 5.2 롤백 스크립트 `scripts/ops/stock_cutover_rollback.sh`
shell(promote_live.sh 스타일), `--dry-run`(명령 echo만), shellcheck 통과, idempotent:
```
① systemctl stop kis-stock-{strategy-daemon,risk-filter,order-router,exit-daemon,monitor-daemon}
   + live drop-in 제거 (또는 shadow 복귀)
② redis-cli -n 1 del stock:daemon:positions trading:stock:positions   (decoupled live 포지션 폐기 — paper)
③ config/llm.yaml::market_context_publisher.enabled=true + M5b crontab shadow 복귀(주석/안내)
④ orchestrator cron 재활성 + scripts/cron/stock_trading.sh start
⑤ 검증: stock_trading.pid 존재 + 프로세스 up
```

### 5.3 런북 `docs/runbooks/stock-pipeline-cutover-m5d.md`
§6의 게이트/시퀀스/롤백을 Phase-5 패턴으로 문서화.

## 6. Runbook: gates, cutover, rollback

### Gate 0 — 전제
M4-P/R/O/X + M5a + M5b/M5c cron 전부 shadow 가동 / stock orchestrator 정상(현 live paper) / 운영자 런북·롤백 숙지.

### Gate 1 — shadow 검증 (≥3–5 거래일)
- 매일 `python -m scripts.ops.stock_cutover_verify --mode shadow` 통과(스트림+group 연결, M5c 리셋, M5b 컨텍스트).
- M5a 대시보드(`:shadow` 키)에 decoupled positions·fills·signals 흐름.
- backlog 무한 증가·데몬 크래시 없음(`systemctl status kis-stock-*`).
- (옵션) decoupled shadow vs orchestrator live paper 방향성 sanity(정확 일치 아님 — 브로커/타이밍 상이).

### Gate 2 — 운영자 서면 승인
날짜 + shadow 검증 요약 기록.

### 컷오버 시퀀스 (장 외 실행 — 16:00 후/주말)
```
① 청산+클리어: (선택)scripts/trading/flatten_all.py --asset stock
   → scripts/cron/stock_trading.sh stop → orchestrator cron 비활성(watchdog 부활 방지)
   → redis-cli -n 1 del stock:daemon:positions trading:stock:positions
② M4 4데몬: /etc/systemd/system/kis-stock-*.service.d/live.conf
   (Environment=STOCK_*_DAEMON=live) → systemctl daemon-reload → enable --now
③ M5a drop-in STOCK_MONITOR_DAEMON=live → restart
   M5b crontab STOCK_LLM_CONTEXT=live + config/llm.yaml market_context_publisher.enabled:false
   M5c crontab(무관 — 그대로)
④ python -m scripts.ops.stock_cutover_verify --mode live 통과
   + systemctl is-active 5유닛 + 첫 09:00 세션 M5a 관찰
```

### 롤백 트리거
live verify 실패 / 장중 X분 fills 무흐름(시그널 있는데 M5a 무활동) / backlog 무한 증가 / 데몬 크래시 루프 / M5a 헬스 알림.

### 롤백
`bash scripts/ops/stock_cutover_rollback.sh`(필요시 `--dry-run` 선검토) → §5.2 시퀀스 → orchestrator 정상 검증.

### 안전
가역적(롤백이 orchestrator 복원) · paper-only(실손실 0, 최악=한 세션 불량 paper + 롤백) · 잔여 모의투자 계좌 포지션=후속 정리.

## 7. Testing
- **verify.py 단위**(fakeredis async): shadow 셋업(스트림+group+키) → `run_verify(mode="shadow")`==0; 스트림 누락 → 1; risk:state:meta stale(어제) → 1; market_context 누락 → warn(비critical, 0 유지 or 정의대로); live 셋업 → `run_verify(mode="live")`==0; suffix 분기(shadow는 `.shadow`만 봄, live 키 안 봄) 검증. now_kst 주입.
- **rollback.sh**: `--dry-run`이 명령을 실행 없이 echo(파괴적 동작 0) 검증(bats 또는 간단 grep 테스트) + `shellcheck` 통과. 실제 systemctl/start는 런북 운영 검증(테스트서 미실행).
- **회귀**: M4/orchestrator 무변경 → 기존 테스트 green. full gate.
- 런북은 문서(코드 테스트 대상 아님) — verify.py가 게이트 자동화.

## 8. Acceptance criteria
- [ ] `scripts/ops/stock_cutover_verify.py` — mode-aware read-only, 스트림+group/risk신선도/market_context/positions 체크, critical fail → exit 1, now_kst 주입 가능, OpenAI/외부 없음(Redis만).
- [ ] `scripts/ops/stock_cutover_rollback.sh` — `--dry-run` 무파괴, shellcheck 통과, idempotent stop+restore 시퀀스.
- [ ] `docs/runbooks/stock-pipeline-cutover-m5d.md` — Gate 0–2 + 컷오버 시퀀스 + 롤백(트리거/절차) + 포지션 청산 처리 명시.
- [ ] 포지션: 컷오버 시 `del stock:daemon:positions trading:stock:positions`(fresh 시작), 잔여 계좌=후속 follow-up 명시.
- [ ] M4 데몬/orchestrator/RuntimeRiskState **무변경**(신규 트레이딩 코드 0).
- [ ] verify.py 단위 테스트(fakeredis) + rollback.sh `--dry-run`/shellcheck.

### 운영 검증 (머지 후, 실제 컷오버 시)
Gate 1 shadow N일 → verify --mode shadow 통과 → 승인 → 컷오버 → verify --mode live 통과 → 첫 세션 관찰.

## 9. Open questions (구현 계획에서 확정)
- verify.py 위치/이름(`scripts/ops/stock_cutover_verify.py` — ops 디렉토리 존재 확인됨), 테스트 위치(`tests/unit/scripts/ops/` 신규 vs 기존).
- market_context 체크 critical vs warn(M5b 미설치 환경에서 false fail 방지 → warn 권장).
- `--strict` 스트림 recency 게이트 포함 여부(장중 전용 — 복잡, v1은 옵션/생략 가능).
- live drop-in vs 유닛 파일 직접 편집(drop-in 권장 — repo-tracked 유닛 무수정).
- 롤백 시 live drop-in 완전 제거 vs shadow 복귀(shadow 복귀 권장 — 재컷오버 용이).
