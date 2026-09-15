# F-9 Gate 1 파리티 갭 폐쇄 계획 (2026-09-10)

**상태**: 작성 완료 · 구현 진행 중 (운영자 지시 2026-09-10 "후속 작업 모두 진행")
**저자**: 세션 모델 단독 (CLAUDE.md Development Discipline)
**선행**: `docs/plans/2026-09-09-order-router-stream-feed.md`(#661/#662),
`docs/plans/2026-09-08-setup-d-decoupled-port.md`(#659/#660),
`docs/runbooks/futures-pipeline-cutover-f9.md` Gate 1 / Gate 1b.

## 0. 왜 지금

2026-09-10 F-9 섀도 3일차 실측(order-router stream 모드 첫 세션)에서 DUAL-WS 해소와
첫 체결(09:39:50 long → 09:41:21 stop)은 확인됐지만, Gate 1 판독을 오염시키는 갭 3건과
관측성 결함 1건이 드러났다. 전부 런북·계획에 없던 것이다.

| # | 갭 | 실측 | 영향 |
|---|---|---|---|
| G1 | Setup A 섀도 영구 맹목 | `daily_reference.prev_close()` 가 parquet daily(`A01609`)를 읽는데 `data/market/futures/daily` 에는 `101S6000`·`krx_kospi200f_continuous` 만 있고 그마저 2026-06-25 에서 정지. 매분 `prev_close: no daily bar data` WARNING(09-09 411건, 09-10 830건), setup_eval 항상 `no_prev_close`. orchestrator 는 REST `FHMIF10000000.futs_prdy_clpr` 를 세션 시작 시 prefetch 해 08:55/08:59 Setup A short 발화 | Setup A 방향 파리티 검증 불가 |
| G2 | risk-filter 거부 사유 무기록 | `shared/risk/layer.py:82` "Signal rejected" 는 docstring 예시. `services/risk_filter/main.py::handle_message` 는 거부 시 로그 없이 ACK. `SignalsAllWriter` 는 `shared/backtest` no-op 스텁(`archive_client=None`). 메트릭 없음. 09-10 후보 30건 중 29건 거부, 사유 로그 0 | Gate 1b "CLOSED = 섀도 거부 증거" 를 생산할 수 없음 |
| G3 | LeverageFilter 가 orchestrator 포지션을 교차 참조 | `_build_leverage_wiring` → `TradingStateReader("futures").get_positions` → `trading:futures:positions`(무접미). risk-filter 프로세스는 `TRADING_STATE_KEY_SUFFIX` 를 설정하지 않아(monitor 는 `main.py:32-36` 에서 설정) orchestrator 의 1계약 보유(≈275M/50M = 5.5x > cap 3.0)가 섀도 진입을 거부. 09-10 유일 통과(09:39:22)는 orchestrator flat 창(09:38:03~09:43:17)에만 떨어짐 | 섀도 후보 통과율이 orchestrator 상태에 종속 |
| G4 | equity 분모 불일치 → 1회 stop 으로 당일 락아웃 | `DailyMDDFilter` 는 `risk.account_equity_krw`=5,000,000 × 3% = 150,000원 한도. kospi200 1계약 stop 1회(−588,839원)로 락아웃. LeverageFilter 는 `FuturesMarginConfig.fallback_account_equity_krw`=50,000,000 사용 | 섀도가 orchestrator 재진입(당일 D 11건)을 재현 못 함 |
| G5 (기록만) | vol 게이트 창 cadence | `vwap_reversion.py::_vol_reference` 780-bar 창을 orchestrator 는 틱마다(≈10분), 디커플은 60s(≈2세션) 로 채움. 11:02 orchestrator 0.89 vs 섀도 0.66→0.37 `vol_below_gate`. 오후 orchestrator short 6건(전부 stop) 섀도 0건 | 설계 정본은 디커플 60s(#659). 코드 변경 없음, Gate 1b ACCEPTED 후보 행으로 등재 |

## 1. 재사용 대상 (먼저 있는 것)

- prev_close 소스: `services/trading/orchestrator.py::_prefetch_futures_daily_reference`
  (`KISClient._get_futures_price(symbol)["prev_close"]`, 세션 시작 1회). 이 값을 그대로
  발행한다.
- 읽기 모델 키 관례: `futures:contract:latest`, `futures:context:latest`,
  `risk:volatility:reference:futures` — 해시 + TTL + `asof_ts`.
- 키 접미 메커니즘: `shared/streaming/trading_state.py::_key` 가 호출 시점의
  `TRADING_STATE_KEY_SUFFIX` 를 읽음. `services/futures_monitor/main.py:32-36` 이 shadow
  모드에서 env 를 설정하는 선례.
- 로그 스로틀: `shared/risk/log_throttle.py`(`setup_eval_reason_kind`), context_provider 의
  VWAP 가용성 래치.
- equity 단일 소스: `services/futures_margin_risk/config.py::fallback_account_equity_krw`
  (`config/futures_margin.yaml` `${FUTURES_MARGIN_FALLBACK_EQUITY:50000000}`).

## 2. 기각한 대안

- **A01609 → 101S6000 parquet daily 매핑**: daily 파티션이 2026-06-25 에서 정지(백필 잡이
  minute 만 갱신). 정지 데이터에 의존하는 소스는 조용히 틀린 prev_close 를 만든다.
- **decision-engine 이 KIS REST 직접 호출**: 데몬에 자격증명이 없고(컨테이너 env 에
  `KIS_FUTURES_APP_KEY` 없음) 계약상 "MarketDataProvider 없음"이 F-9 설계. 자격증명 표면을
  넓히지 않는다.
- **tick 스트림에 `prev_close` 필드 추가**: `MarketTickMessage` 계약 변경 + producer 2곳 +
  consumer 전부 영향. 하루 1값을 위해 틱마다 실어 나르는 것은 과함.
- **스케줄러 08:00 잡으로만 발행**: 잡 1회 실패 = 하루 맹목. producer(세션 시작 prefetch)
  발행이 정본이고 스케줄러는 쓰지 않는다.
- **DailyMDD 를 shadow 에서 끄기**: 파리티 검증 대상 필터를 끄는 것은 갭을 숨기는 것.
  분모를 맞추는 것이 옳다.

## 3. 변경 (최소 표면)

### PR-A — prev_close 읽기 모델 (`feat/f9-futures-daily-reference`)

1. `shared/streaming/daily_reference.py` (신규, 작음)
   - `FUTURES_DAILY_REFERENCE_KEY = "futures:daily_reference:{symbol}"` 상수.
   - `publish_futures_daily_reference(redis, *, symbol, prev_close, source, asof, ttl_seconds)`
     → HSET {prev_close, source, asof_ts(KST ISO), producer} + EXPIRE.
   - `read_futures_daily_reference(redis, symbol) -> dict | None`.
   - TTL 은 YAML 값(24h 기본 운영 TTL) — `config/futures_contract.yaml` 또는 가장 가까운
     읽기 모델 YAML 에 `daily_reference.ttl_seconds: 86400` 로 두고 두 발행자가 같은 값을
     읽는다. 두 번째 하드코딩 상한 금지.
2. 발행자 2곳
   - `services/trading/orchestrator.py::_prefetch_futures_daily_reference`: 캐시 직후 발행
     (실패는 WARNING, 거래 경로 무영향).
   - `services/market_ingest/main.py`: futures 자산일 때 세션 시작·심볼 적용 시 같은 REST
     조회로 prefetch → 발행 (컷오버 후 producer). 조회 함수는 orchestrator 와 공유(헬퍼로
     추출, 동작 불변).
3. 소비자 `services/decision_engine/daily_reference.py::FuturesDailyReference.prev_close`
   - 1순위 Redis 읽기 모델(KST 당일 캐시, `asof_ts` 가 오늘 이전이면 무시), 2순위 기존
     parquet 경로(변경 없음), 둘 다 없으면 0.0.
   - 로그: 소스 확정 시 INFO 1회/일, 부재 시 WARNING 1회/일(래치) — 매분 WARNING 제거.
4. 테스트: 헬퍼 round-trip(fakeredis), 소비자 3분기(redis hit / stale asof → parquet /
   both miss), orchestrator prefetch 가 발행하는지(mock client), ingest prefetch.

### PR-B — risk-filter 관측성·키 접미·equity (`fix/f9-risk-filter-parity`)

1. `services/risk_filter/main.py::main`: mode==shadow 이고 `TRADING_STATE_KEY_SUFFIX` 미설정이면
   `"shadow"` 설정, live 면 비움(monitor 와 동일 문형). `_build_leverage_wiring` 전에 실행.
   기동 로그에 해석된 positions 키(`trading:futures:positions[:shadow]`) 출력.
2. `handle_message`: `result.passed` 여부와 무관하게 INFO 1줄 —
   `risk_filter verdict=passed|rejected signal_id= setup_type= direction= symbol= filter=<거부 필터>
   reason=<skip_reason> size_multiplier= outcomes=<name:pass|fail,...>`. 스로틀 없음(후보는
   분당 최대 1건).
3. equity 분모 단일화: `config/risk.yaml` `risk.account_equity_krw` 를
   `${FUTURES_MARGIN_FALLBACK_EQUITY:50000000}` 로 바꾸고 주석에 근거(G4·LeverageFilter 와
   동일 분모). `risk_stock` 은 손대지 않는다. 사전 확인: 모놀리식이 `risk.account_equity_krw`
   를 사이징에 쓰지 않는지(`FuturesRiskConfig` 소비처 grep) — 쓰면 계획을 멈추고 보고.
4. 테스트: suffix 설정 분기, verdict 로그(caplog) passed/rejected, config 값 해석.

### PR-C — 런북/문서 (`docs/f9-gate1-day3-evidence`)

- Gate 1 절: 09-10 실측 요약 + "decision-engine 로그는 재부팅 경계 손상 시 `--tail` 로만"
  + prev_close 읽기 모델 점검 명령.
- Gate 1b 표: 행 추가 — Setup A prev_close 소스(G1), LeverageFilter 포지션 소스(G3),
  MDD equity 분모(G4), vol 창 cadence(G5, ACCEPTED 후보), risk-filter verdict 관측성(G2).
  `:469` "LeverageFilter is inert" 문구 정정(실제 armed, 2026-07-12 enforce).
- 서명 블록에 제안 처분을 **초안**으로 채움(서명은 운영자).

## 4. 배포·검증

- 머지 후 paper: `scripts/deploy_paper.sh` 로 `futures-decision-engine`·`futures-risk-filter`
  (PR-B/A 소비자)·`trader-futures`(PR-A 발행자, **장외**). market-ingest 는 paper 에서 dormant.
- 검증(다음 세션 08:45~): `HGETALL futures:daily_reference:A016xx` 존재·`asof_ts` 당일,
  setup_eval Setup A 가 `no_prev_close` 가 아닌 사유로 전이, risk-filter `verdict=` 로그가
  후보 수와 일치, LeverageFilter 가 orchestrator 포지션에 반응하지 않음(orchestrator 보유
  중 섀도 통과 존재), DailyMDD 락아웃이 1회 stop 에 발생하지 않음.

## 5. 범위 밖

- vol 게이트 cadence 동기화(모놀리식 변경) — 은퇴 대상 코드.
- `SignalsAllWriter` 실체화(ClickHouse 비활성) — 로그로 충분.
- Setup A regime_gate·Setup D adapter 방향 차단 이식 — 기존 Gate 1b 행(운영자 결정 ②).
