# LLM Market-Context Cron (M5b) — Design

- Date: 2026-06-06
- Status: Design (pending implementation plan)
- Parent effort: `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md` (M5 cutover)
- Predecessor merged: M5a stock monitor bridge (#419)
- Scope: **M5b — the second M5 sub-project.** A market-hours-gated cron that runs the existing `LLMContextPublisher` standalone (extracted from the orchestrator's 60-min loop) so `trading:stock:market_context` keeps being published once the monolithic orchestrator's stock path is cut over.

## 1. Goal & scope

The decoupled stock strategy daemon (M4-P) already **consumes** LLM market context: `StrategyManager` owns an `LLMContextProvider` that reads `trading:stock:market_context` from Redis and injects it into the entry/exit context (used by `mean_reversion`'s regime filter and `williams_r`'s market_state). But the only runtime **producer** of that key is the orchestrator's in-loop `LLMContextPublisher` (a 60-min background task). M5b extracts that producer into a standalone, market-hours-gated cron so the context survives the M5 cutover — the prerequisite "brain feed" for the decoupled stock pipeline.

**Success criterion:** A shadow-first, default-off single-shot cron (`scripts/analysis/llm_market_context.py`) that, per invocation, runs the reused `LLMContextPublisher("stock")` once and publishes `trading:stock:market_context` — to an **isolated** `:shadow` key in shadow mode (so it never clobbers the still-live orchestrator's key) and to the live key in live mode (M5d). Market-hours gating is handled by the crontab schedule (08:30 pre-market + hourly 09:00–15:00 KST), not in code. `LLMContextPublisher`, the orchestrator, and the consumer (`StrategyManager`/`LLMContextProvider`) are **unchanged** — M5b is a thin standalone wrapper.

비목표(out of scope): the M5d cutover flip (crontab → live + orchestrator publisher gate-off), futures market context (separate Phase-5 orchestrator path), on-demand `request_refresh()` (no stock caller — periodic-only), a long-running daemon / Prometheus pull endpoint (cron is short-lived; see §6), consumer changes (already works), a Pushgateway integration.

## 2. Locked decisions (브레인스토밍 2026-06-06)

| 결정 | 선택 | 근거 |
|---|---|---|
| 배치 | **Cron 스크립트** (not a systemd daemon) | 주기적·상태없는·시간-게이팅 LLM 작업 = cron 교과서 용례. 기존 LLM 작업(브리핑 3종)이 전부 cron. market-hours 게이팅을 crontab expression이 무료 제공 |
| 분석 게이팅 | **market-hours** (08:30 장전 1회 + 09:00–15:00 매시 KST) | orchestrator의 24/7 무게이팅 대비 OpenAI ~65% 절감, 컨텍스트는 거래 시간에만 의미 |
| 자산 범위 | **stock 전용** | M5는 stock 컷오버 대상; 선물 컨텍스트는 Phase-5 별도 orchestrator 경로 유지 |
| 소비자 | **무변경** | M4-P `StrategyManager`의 `LLMContextProvider`가 이미 `trading:stock:market_context` 읽음 — M5b는 producer만 |
| shadow 격리 | **`TRADING_STATE_KEY_SUFFIX`** (M5a와 동일) | publish_market_context가 `_key` 통해 per-call lazy read → shadow=`:shadow` 키, live 키 무충돌 |

## 3. Current state (감사 2026-06-06)

- **Producer**: `services/trading/llm_context_publisher.py::LLMContextPublisher`. `run_analysis(mode="all") -> MarketContext | None`(UnifiedMarketAnalyzer = OpenAI 호출, ~15–45s, fire-and-forget→None on failure). `publish_to_redis(context)` → `TradingStatePublisher.publish_market_context()`(`trading:{asset}:market_context` STRING, TTL 24h) + best-effort SQLite ledger `record_market_context`(forward history). `request_refresh()`(on-demand, lock-serialised — **프로덕션 미호출**).
- **주기 루프는 orchestrator 소유**: `services/trading/orchestrator.py:4891` `_llm_context_publisher_loop(interval_minutes)` — `asyncio.create_task`, 60분마다 `run_analysis()`+`publish_to_redis()`, **market-hours 게이팅 없음(24/7)**. config gate `config/llm.yaml::market_context_publisher.enabled`(orchestrator.py:1544), `analysis_interval_minutes: 60`, `run_on_startup: true`.
- **Consumer (이미 작동)**: `services/trading/strategy_manager.py:273` `LLMContextProvider(asset_class)`; `check_entries`(457–463)/`check_exits`가 `provider.get_context()`(60s 캐시 + `TradingStateReader.get_market_context()` Redis read, graceful None)를 `EntryContext.market_context`에 주입. **M4-P StockStrategyDaemon도 StrategyManager를 쓰므로 이미 읽음** — M4-P shadow는 현재 orchestrator 발행 컨텍스트 소비.
- **stock 사용처**: `mean_reversion`(STRONG_BEARISH long 차단), `williams_r`(market_state) — stock에 load-bearing. 나머지 전략은 self-contained.
- **기존 LLM cron**: `scripts/analysis/llm_nightly_analysis.py`(21:00)/`llm_premarket_briefing.py`(06:30)/`llm_market_close_briefing.py`(15:30) — **브리핑(Telegram)만**, `trading:stock:market_context` **미발행**. → orchestrator만이 유일 런타임 소스.
- **shadow 격리 메커니즘**: `shared/streaming/trading_state.py::_key`가 `TRADING_STATE_KEY_SUFFIX` env를 per-call lazy read(M5a 검증).

## 4. Target architecture (Approach A — cron)

### 4.1 컴포넌트
신규 `scripts/analysis/llm_market_context.py` — 단발 cron 스크립트(기존 LLM cron들과 동일 위치/패턴).

### 4.2 흐름 (1회 실행)
```
mode = STOCK_LLM_CONTEXT (off 기본 | shadow | live)
if mode not in (shadow, live): log + return 0     # off: inert (no OpenAI/Redis)
_ensure_shadow_isolation(mode)                     # shadow → TRADING_STATE_KEY_SUFFIX=shadow (fail-safe)
pub = LLMContextPublisher("stock")                 # 기존 클래스 무변경 재사용
ctx = await pub.run_analysis()                     # OpenAI ~15-45s; None on failure
if ctx is not None:
    pub.publish_to_redis(ctx)                      # trading:stock:market_context[:shadow] + SQLite ledger
    log(regime, confidence)
else:
    log("analysis returned None; skipping publish")
return 0
```
asyncio 루프·systemd·게이팅 코드 **없음** — cron이 스케줄·게이팅 담당.

### 4.3 구조 (테스트 가능)
- `_resolve_mode() -> str` (env `STOCK_LLM_CONTEXT`, 기본 "off")
- `_ensure_shadow_isolation(mode)` (shadow + suffix 미설정 → `os.environ["TRADING_STATE_KEY_SUFFIX"]="shadow"`; live → 무변경)
- `async def run_once(mode) -> int` (off→0 inert; else publisher 생성→run_analysis→publish; 0 반환)
- `main() -> int` (asyncio.run(run_once(_resolve_mode())))

### 4.4 crontab 스케줄 (KST native, `CRON_TZ=Asia/Seoul` — 운영자 관리, 스크립트만 repo)
```cron
# 장전 1회 (개장 전 컨텍스트 준비)
30 8  * * 1-5  STOCK_LLM_CONTEXT=shadow  /home/deploy/project/kis_unified_sts/.venv/bin/python -m scripts.analysis.llm_market_context
# 장중 매시 정각
0 9-15 * * 1-5 STOCK_LLM_CONTEXT=shadow  /home/deploy/project/kis_unified_sts/.venv/bin/python -m scripts.analysis.llm_market_context
```
→ 평일 8회/일(장전 1 + 장중 7). 24/7(~24회) 대비 OpenAI ~65% 절감.

### 4.5 자산 범위
**stock 전용**. 선물 `trading:futures:market_context`는 Phase-5 별도 orchestrator 경로 유지(별도 M5b-futures 가능, 범위 밖).

## 5. Shadow 격리 · 컷오버 · 소비자/staleness

### 5.1 shadow 격리 (M5a와 동일)
`_ensure_shadow_isolation(shadow)` → `TRADING_STATE_KEY_SUFFIX=shadow` 강제(fail-safe) → `publish_market_context`가 `trading:stock:market_context:shadow`에 발행. orchestrator(가동 중)는 live 키 → **무충돌**. live(M5d): suffix 없음 → live 키.

### 5.2 소비자 무변경
M4-P `LLMContextProvider`는 **unsuffixed** `trading:stock:market_context` 읽음(M4-P는 suffix 미설정) → shadow의 M5b는 전략 동작에 **무영향**(M4-P는 orchestrator live 컨텍스트 계속 읽음, 순수 검증). M5d에서 orchestrator off + M5b live → M4-P가 M5b 컨텍스트 읽음.

### 5.3 SQLite ledger
`publish_to_redis`는 Redis + SQLite ledger(forward history) 둘 다 기록. shadow도 append(idempotency_key=`llm_market_context:stock:<generated_at>`, 시점 다르면 별도 레코드) → 검증 창 동안 history 약간 중복(라이브 경로 무영향). `publish_to_redis` 무변경.

### 5.4 컷오버 훅 (M5d 소유)
M5d 시 flip: crontab `STOCK_LLM_CONTEXT=live`(suffix 없음→live 키) + orchestrator `config/llm.yaml::market_context_publisher.enabled: false`(orchestrator 발행 중단) → M5b 단독 발행. M5b v1은 off/shadow/live 지원만, 실제 flip은 M5d.

### 5.5 staleness / TTL
`publish_market_context` TTL=24h. cron 중단 시 24h 후 만료 → reader None → `LLMContextProvider` graceful None → `mean_reversion`/`williams_r` graceful degrade(regime 필터 무효). 장중 매시 발행 → 컨텍스트 최대 ~60분 stale(regime 힌트라 무방, 현 orchestrator 60분과 동일 — 회귀 없음). 장 외엔 거래 없어 무관.

## 6. Error handling · cost · idempotency · 관측성

### 6.1 에러처리 (cron-friendly)
| 상황 | 정책 |
|------|------|
| `run_analysis()` None | log + return 0 (직전 컨텍스트 잔존, 다음 cron 재시도) |
| `publish_to_redis` 실패 | fire-and-forget(log, never raise) → return 0 |
| 일시 OpenAI/Redis hiccup | return 0 (cron mail 노이즈 방지) |
| setup/config/import 실패(분석 전) | uncaught → exit 1 (cron mail로 실 misconfig 감지) |
| off 모드 | 완전 inert(호출 0, return 0) |

### 6.2 cost
1회 = OpenAI 1콜(저가 모델 ~1500토큰). 평일 8회/일. 컷오버 후 M5b 8/일이 orchestrator 24/7(~24/일) 대체 → **순감소**. shadow 검증 창 동안만 일시 2배(짧음, 수용).

### 6.3 멱등성/동시성
단발 cron, 1회 내 동시성 없음. 60분 간격 ≫ 분석 ~15-45s → overlap 없음(겹쳐도 last-wins + ledger distinct → 무해). **lock 불필요**.

### 6.4 관측성 한계 (cron 트레이드오프, 명시)
`LLMContextPublisher`의 Prometheus 카운터는 **장시간 pull `/metrics` 전제** — cron은 즉시 종료라 scrape 불가(무용). → M5b 관측성 = **명료한 로그 + SQLite ledger 최신 `generated_at`(staleness 지표; ops-monitor가 체크)**. Pushgateway 연동은 follow-up.

## 7. Testing (OpenAI는 mock — 실 API 호출 없음)
- **단위**: `_resolve_mode` 기본 off · `_ensure_shadow_isolation`(shadow→suffix 강제 / live→미설정; **M5a env-leak 교훈** — `monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX","")`로 키 추적) · `run_once(off)`→0 inert, LLMContextPublisher 미생성 · `run_once(shadow)`: `LLMContextPublisher.run_analysis` mock→MarketContext → `publish_to_redis` 호출, 0 · run_analysis→None → publish 미호출, 0. (`scripts.analysis.llm_market_context.LLMContextPublisher` patch로 OpenAI 회피.)
- **통합**: `_get_redis`→fakeredis + run_analysis mock→MarketContext, `run_once(shadow)` → `TradingStateReader(suffix=shadow).get_market_context()` read-back = 컨텍스트 / live 키 무손상.
- **회귀**: orchestrator/`LLMContextPublisher`/`trading_state` 무변경(M5b=신규 스크립트만) → 기존 테스트 green. full gate.

## 8. Acceptance criteria
- [ ] `scripts/analysis/llm_market_context.py` 단발: mode 게이트 → run_analysis → publish_to_redis → return 0.
- [ ] off=inert(OpenAI/Redis 0), shadow=`:shadow` 키(fail-safe suffix), live=live 키.
- [ ] None 분석 → publish 안 함, return 0(graceful).
- [ ] `LLMContextPublisher` 무변경 재사용, 소비자(M4-P StrategyManager) 무변경.
- [ ] crontab 스케줄 문서화(08:30 + 09:00–15:00 매시, `CRON_TZ=Asia/Seoul`).
- [ ] 테스트서 OpenAI mock(실 API 0), market-hours 게이팅은 crontab(코드 아님).
- [ ] shadow 격리로 live `trading:stock:market_context` 절대 clobber 안 함.

### 운영 검증 (머지 후, M5d 선행)
shadow crontab 활성화 → `…:market_context:shadow`(M5b) vs orchestrator live 키 regime/confidence 비교 → M5d 디리스킹.

## 9. Open questions (구현 계획에서 확정)
- crontab 정확 시각(08:30 + 09:00–15:00 매시) — 운영자 확인.
- 스크립트 테스트 위치(`tests/unit/scripts/` vs `tests/scripts/` — 기존 LLM cron 테스트 위치 따름).
- `--mode` CLI 인자 추가 여부(env-only 권장, YAGNI).
- 도큐: crontab 권장 항목을 어느 runbook/문서에 기록할지.
