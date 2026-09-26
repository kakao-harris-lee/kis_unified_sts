# 주기적 시간 건강 평가 + KIS 증인 배선 — 후속 계획

- 작성: 2026-09-26 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `f3856576`(#805 머지 직후)
- 요청: 운영자 2026-09-26 「do it」 — #805 §8.1 이 남긴 두 후속(주기 평가 · KIS 증인 배선)의 계획.
- 성격: 계획 + 구현(같은 PR). 운영자 처분 §6.1 · 착지 §7.

## 0. 요약 — 조사가 계획을 바꿨다

1. **주기 평가는 위생이 아니라 결함 수정이다.** `evaluate()` 는 부팅 때 두 번만 돈다(`compose/_wiring.py:388-389`,
   주석 :381-387 「ONGOING health-check cycles ... remain the caller's own job」). `wall_clock_now()` 는 마지막 평가의
   관측치를 돌려주므로(`time/service.py:697-711`) `run` 의 모든 시각이 **부팅 시각에 멈춘다.** 틱 스케줄러는 그 값을
   쓰고(`marketfeed/scheduler.py:347`), `now_ms - last_tick_wall_clock_ms < poll_interval_ms` 이면
   `SKIPPED_INTERVAL`(`:174-178`) — 멈춘 시계에서 그 차는 늘 0 이다. **paper `run` 은 첫 틱 하나만 소비하고 이후 전부
   건너뛴다.** 세션 위상(`calendar/owner.py`)도 같은 값을 읽으므로 **닫힌 시각에 부팅하면 세션이 영영 열리지 않는다.**
   런북 §5 의 「주입 시계로 TICKED」 실측은 주입 시계라서 이 결함을 가렸다.
2. **KIS 증인은 지금 paper 에 배선하면 해롭다.** paper 는 `krx-index-futures` + `SYNTHETIC_FUTURES_ORDER`(주문이 KIS 에
   가지 않음)인데 증인은 주식 전용이다(`recon/witness_kis_config.py:97-115`). 설령 선물 증인이 있어도 합성 주문은
   브로커에 없으니 **모든 시도가 `STALE_RESERVATION`** 이 되어 복구 해제·캐파시티 해제가 **영구 차단**된다
   (`recovery/reconciliation.py:313`, `posttrade/release_consumer.py:640`). 증인 배선은 **주문이 실제로 모의 서버에
   가는 단계(kis-mock 전송 + `nonlive_broker_consuming.admitted`)** 와 함께여야 한다.

→ 이 후속의 착수 범위는 **W1 주기 평가** 와 **W2 C-2 자격증명 단일 소유자(결정됨·미착수)** 이고, 증인 배선(W3)은
전제가 채워질 때까지 **보류**를 제안한다.

## 1. 실측 (main `f3856576`)

| 무엇 | 어디 | 상태 |
|---|---|---|
| 평가 호출 | 부팅 2회뿐(`_wiring.py:388-389`, `rearm` CLI `cli.py:740-741`) | 주기 호출 **없음** |
| 실행 루프 | `dispatch_run`(`compose/_run_dispatch.py:134`) → `TickScheduler.run_forever`(`scheduler.py:392-408`: `while not stop(): tick_once(); sleep(poll_interval)`) | 패스별 훅 없음. `EngineDriver.bind_after_turn` 은 **단일 슬롯**이고 처리된 턴에서만 불리며 이미 exporter 가 점유(`_operations_wiring.py:469-470`) — 평가 자리로 부적합 |
| 평가 1회의 일 | 참조 원천 읽기 — 운영은 `LocalSystemClockReader`(`time/sources.py:118-134`, 로컬 시계만 · 네트워크 없음) · 커널 술어 · **매 사이클 `TIME_HEALTH_SNAPSHOT` 증거 1행**(`service.py:651-655`, 「영수증 없으면 일어나지 않았다」 계약 :647-650) | 비용 작음 · 증거는 매번 쌓임 |
| 증거 크기 | 로컬 부팅 실측: `TIME_HEALTH_SNAPSHOT` 행당 약 **1.8 KB**(페이로드+digest) | 1 s 주기면 86,400 행/일 ≈ **158 MB/일** |
| 중단(suspension) 판정 | `max(0, Δwall − Δmono)`(`service.py:330-356`) — **사이클 간격은 중단이 아니다** | 주기는 자유롭게 정할 수 있음(조사 보고의 「2 s 넘으면 중단」은 틀림) |
| 틱과 평가의 관계 | 틱 간격 판정이 평가 시각으로 계산되므로 **틱 주기 ≥ 평가 주기** | 1 s 틱을 원하면 1 s 평가가 필요 |
| 거래일 신선도 | `MAX_time_conservative_freshness_age_ms: 1000`(paper `time.yaml:32`) · #805 의 `wall_clock_now_if_fresh` | 평가가 틱마다 돌면 ACK 직후 날짜가 대체로 신선 |
| C-2 | `docs/plans/2026-09-23-tos-kis-credential-ownership-decision-c2.md` §4 — 운영자 (C) 확정 2026-09-23, **「구현: 미착수」**(:189) · `tos/runtime/src` 에 `KisCredentialSession` 0건 | 밀폐 테스트로 구현 가능 |
| 증인 설정 | `tos/runtime/config/kis_witness.example.yaml` 만 · paper `kis_witness.yaml` 없음 · 운영 토큰 세션 없음 | W3 전제 |
| 선물 증인 | 체결조회 `VTTO5201R`(`/uapi/domestic-futureoption/v1/trading/inquire-ccnl`) — 프로필 `:770-775` CODE-EVIDENCED · 측정 아티팩트 **0건** · 모의 선물 잔고 TR 은 공식문서(`VTFO6118R`)와 레거시 클라이언트(「모의 미지원」)가 **모순** | 측정 먼저 |

## 2. 결정

### W1 — 주기 평가 (착수)

1. **자리: `TickScheduler.run_forever` 의 매 패스 앞.** `run_forever` 에 주입 인자 `before_pass: Callable[[], None] | None`
   을 추가하고, 컴포즈가 `time_service.evaluate` 를 넘긴다(스케줄러는 시간 서비스를 이미 주입받음 — 새 결합 없음).
   `tick_once` 는 그대로 순수하게 두고 테스트에서 가짜로 몰 수 있게 한다.
2. **주기: §6 운영자 결정 1.** 권고안 **(나)**:
   - (가) 매 패스(= `poll_interval_ms`, paper 1 s) 무조건 — 단순 · 약 158 MB/일.
   - **(나) 세션이 열려 있으면 매 패스, 닫혀 있으면 `time_evaluate_closed_interval_ms`(time.yaml 신설, 권고 60000)** —
     틱은 열린 세션에서만 일어나므로 정확성은 (가)와 같고, 증거는 약 **46 MB/일**(선물 주간 7 h 기준) + 닫힌 시간 약 1천 행.
     닫힌 상태에서 개장을 알아채는 지연은 최대 그 간격. 세션 판정 자체가 평가 시각을 쓰므로, 닫힌 동안에도 평가가
     돌아야 개장을 본다(그래서 「닫히면 멈춤」은 불가).
   - (다) 단일 설정값 `time_evaluate_interval_ms` — 운영자가 한 값으로 고름. 틱 주기가 그 값 이상으로 늘어난다.
3. **평가 실패는 루프를 멈추지 않는다.** 증거 추가 실패 등으로 `evaluate()` 가 던지면 그 패스의 `tick_once` 는 건너뛰고
   (낡은 시각으로 틱하지 않음) 다음 패스에 재시도 — 실패는 기존 비상 로그 관례로 기록. 연속 실패 시 상태는 시간 서비스가
   이미 강등 규칙으로 처리한다(새 판정 없음).
4. **증거 보존(퍼지)은 이 작업이 아니다.** 되돌리기 어려운 데이터 파기라 별도 계획·승인. W1 은 증가율을 문서에 적는다.

### W2 — C-2 `KisCredentialSession` (착수, 결정대로)

C-2 문서 §4 그대로: `transport/kis_mock` 옆에 앱키당 단일 소유자 `KisCredentialSession` 을 두고 주문 전송·시세 인입·
증인에 주입, 증인 Protocol 을 `request_credentials()` 컨텍스트 하나로. **증인 배선 자체는 C-2 문서도 범위 밖**으로
명시했다 — 여기서도 그대로.

### W3 — KIS 증인 배선 (보류 제안)

전제: ① 주문이 모의 서버에 실제로 간다(kis-mock 전송 + `nonlive_broker_consuming.admitted` — 별도 승인) ② 배포 자산에
맞는 증인(선물이면 `VTTO5201R` GET-only 실측 → 선물 증인 구현) ③ W2 ④ paper 좌표(`account`/`instrument` 렌더).
전제 없이 배선하면 §0-2 대로 해제 경로가 영구 차단된다.

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| `bind_after_turn` 에 평가 연결 | 단일 슬롯(exporter 가 점유) · 처리된 턴에서만 불림 — 유휴 패스에서 시계가 다시 멈춘다 |
| 평가를 백그라운드 스레드로 | 이 런타임은 단일 스레드 루프 규율(sqlite 연결 공유) — 경쟁 조건만 늘린다 |
| `wall_clock_now()` 가 단조시계로 외삽 | 신뢰 판정 없이 시각을 만들어 내는 것 — 시간 서비스의 「관측만 노출」 원칙 위반 |
| 스냅샷 증거를 상태 전이 때만 기록 | 「영수증 없으면 일어나지 않았다」(`service.py:647-650`) 계약을 깨고 관측 가능한 상태를 영수증 없이 노출 |
| 합성 전송 그대로 KIS 증인 배선 | §0-2 — 모든 시도 STALE → 해제 영구 차단 |

## 4. 작업

| # | 내용 | 종료 조건 |
|---|---|---|
| T-1 | `run_forever(before_pass=...)` + 세션 상태별 주기(§6 결정 1) + 평가 실패 시 그 패스 틱 생략 | 가짜 시계로: 두 번째 패스에서 **TICKED**(현 결함 재현 테스트가 먼저 red) · 닫힘→열림을 간격 안에 감지 · 평가 실패 패스에서 틱 0 |
| T-2 | `time.yaml` 키 신설(결정 (나)/(다)일 때) · 로더·예시·paper 값·`_VALUE_PINS` | 설정값 없으면 부팅 거부(기존 named-TBD 규율) |
| T-3 | 컴포즈 배선 + 런북 §5 정정(「주입 시계라서 가려진 결함」) + 실제 시계로 N 초 부팅해 TICKED ≥ 2 실측 | 실 시계 부팅에서 틱이 계속 소비됨 |
| T-4 | C-2 `KisCredentialSession` + 세 소비자 주입 + 증인 Protocol 교체 | C-2 문서의 종료 조건 그대로 |
| T-5 | digest 재도출 · 상위 계획 착지 기록 | 통상 |

**뮤테이션**: `before_pass` 호출 제거 → 두 번째 틱 테스트 red · 닫힌 주기 무시 → 개장 감지 테스트 red · 평가 실패인데도
틱 → red.

## 5. 위험

- **증거 증가**: 권고 (나)로도 약 46 MB/일이 쌓인다. 퍼지 계획 전까지 디스크 여유를 운영자가 확인.
- **T-1 은 틱 소비를 실제로 켠다** — 지금까지 사실상 한 틱만 돌던 paper 가 매 초 틱한다. 합성 주문 경로라 브로커 도달은
  0 이지만, 전략·위험 경로가 처음으로 연속 가동된다(실측 부팅 T-3 에서 확인).

## 6. 운영자 확인

1. **평가 주기**: (가) 매 패스 / **(나) 열림 매 패스 · 닫힘 60 s (권고)** / (다) 단일 값.
2. **범위**: W1 + W2 착수, **W3 증인 배선 보류**(전제 미충족) — 동의 여부.
3. **증거 퍼지**는 별도 계획(데이터 파기 — 되돌리기 어려운 경로)으로 — 동의 여부.

### 6.1 운영자 처분 (2026-09-26)

1. **평가 주기 = (나)** — 세션 열림 매 패스 · 닫힘 60 s.
2. **범위 = W1 + W2 착수, W3 보류** — 동의.
3. **증거 퍼지 = 별도 계획** — 동의.

## 7. 착지 기록 (2026-09-26, 브랜치 `claude/kis-tos-project-covm64` · PR #806)

### 7.1 W1 — 주기 평가 (처분 (나))

- `marketfeed/time_pacer.py::TimeEvaluationPacer` 신설 — 패스 앞에서 열림이면 매번, 닫힘이면
  `time_evaluate_closed_interval_ms` 마다 `evaluate()`. 평가가 던지면 그 패스 틱 생략(stderr 한 줄) · 다음 패스 재시도.
  닫힘 간격 시계는 프로세스 단조시계(루프 보폭용 — 신뢰 시각·증거·커널에 닿지 않음).
- `TickScheduler(before_pass=...)` — 생성자 주입, `run_forever` 가 매 패스 호출. `tick_once` 는 그대로 순수.
  §2 W1-1 의 「`run_forever(before_pass=...)` 인자」 대신 생성자로 둔 이유: `dispatch_run` 이 `run_forever(stop=...)`
  만 부르므로 호출부 무변경으로 배선된다.
- **계획과 다른 점(설정 위치)**: 키를 `time.yaml` 이 아니라 **`marketfeed.yaml::time_evaluate_closed_interval_ms`**
  에 뒀다. 루프를 소유한 것이 marketfeed 이고, `time.yaml` 로더는 시간 서비스 전체가 공유한다. 필수 · 양의 정수 ·
  예시 `null`(부팅 거부) · paper `60000` · `_VALUE_PINS` 고정.
- **조사 중 추가 발견·수정**: `SessionFactsOwner.observe` 캐시가 **틱 세대만** 키로 썼다 — 닫힌 동안에는 틱이 없어
  세대가 안 바뀌므로, 평가가 시각을 개장 안으로 옮겨도 「닫힘」을 영원히 돌려줬을 것이다. 벽시계 판독값도 키에 넣었다
  (`calendar/owner.py`). `SESSION_FACTS_OBSERVED` 는 여전히 위상 변화 때만 기록된다.
- `test_run_e2e.py` 의 수동 `runtime.time_service.evaluate()` 우회(멈춘 시계를 인정하던 주석) 제거 — 이제 루프가 한다.
- 뮤테이션(전부 red 확인): 배선 제거(`before_pass=None`) → e2e 두 번째 틱 red · 닫힘 간격 무시 → pacer red ·
  실패인데 틱 → pacer red · `before_pass` 응답 무시 → scheduler red · 열림 판정 제거 → pacer red ·
  owner 캐시를 세대만으로 → owner red.
- **실측 (T-3)** — 렌더한 paper 설정 그대로(의존성 digest 만 스크래치 사본에서 컨테이너 값으로):
  - 실 `run`, 닫힌 세션(2026-09-26 토 21:11 KST), 150 s 후 SIGTERM → 종료코드 0. `TIME_HEALTH_SNAPSHOT` 5행 =
    부팅 2 + 패스 평가 **+0.1 s · +60.2 s · +120.2 s** — 닫힘 60 s 주기 그대로.
  - 세션 시계만 개장 시각(2026-09-28 10:00 KST, 런북 §5 ④ 진단)으로 주입하고 `run_forever` 를 실 `time.sleep`
    으로 8 패스 · 4번째 패스에 더 새 관측을 저널에 추가 → **스냅샷 2 (TICKED ×2)** · 평가 10행(부팅 2 + 매 패스 8).
  - 같은 조건에서 pacer 만 떼면(`_before_pass = None`) **스냅샷 1** · 평가 2행 — 수정 전 결함 재현.

### 7.2 W2 — C-2 `KisCredentialSession`

- `transport/kis_mock/credential_session.py`: `KisCredentialSession`(수명주기 + custody 로드의 유일한 소유자 ·
  `ensure_token_string()` · `app_credentials()` · `request_credentials()`) + `KisCredentialSessions`(앱키당 하나 —
  두 번째 소비자의 토큰 엔드포인트(host·path)·재발급 간격이 다르면 `KisCredentialSessionConflict` 로 거부).
- compose: `compose/_kis_credential_wiring.py`(scope 상수 한 벌 + 레지스트리 빌더 — 시세 배선의 「주문 전송 배선
  비의존」 성질을 지키는 중립 모듈) → `_finalize` 가 부팅당 하나 생성 → 주문 전송이 받고 `ComposedRuntime
  .kis_credential_sessions` 로 실어 `build_tick_scheduler` 의 `kis_quote` 인입이 **같은 세션**을 받는다.
- 증인: `KisWitnessTokenSession`(평문 `str` 반환 3종) → **`KisWitnessCredentialSession.request_credentials()`** 하나.
  GET 한 번마다 블록 하나. 증인 배선 자체는 범위 밖(W3 보류 그대로).
- **C-2 스케치와 다른 점**: (1) 세션이 수명주기를 **주입받지 않고 스스로 만든다** — scope 가 한 곳에서만 정해지게
  (주입형이면 수명주기와 세션의 scope 가 어긋날 수 있다). (2) 두 어댑터는 `credential_session` 이 없을 때 자기
  세션을 만드는 **대체 경로**를 남겼다 — C-2 §4.2 「어댑터 기존 테스트 스위트 무변경 통과」를 지키기 위해서다. 그래서
  scope 문자열 사본은 compose 1 + custody 허용 목록 1 + **시세 어댑터 대체 경로 1 = 3**(C-2 §3 의 목표 2 가 아님).
  로드 지점은 목표대로 1(세션 · 그 안의 수명주기).
- 핀(C-2 §4.3, 전부 뮤테이션 red 확인): 같은 밀리초 두 소비자 → `issue_token` **1회**(레지스트리 공유 끊으면 2) ·
  compose 전 스택에서 주문 전송과 시세 인입의 세션 **동일 객체**(`root.py` 에서 레지스트리 전달 끊으면 red) ·
  AST 핀 — 세션·수명주기 밖 `*custody.load(` 0건(어댑터에 인라인 로드 복원 시 red) · 블록 밖 `app_key()` →
  `CustodyError` · 낡은 토큰은 custody 로드 전에 거부 · 증인 GET 수 = 블록 수, 남은 블록 0.
- 어댑터 스위트(`tests/transport/kis_mock`, `tests/transport/kis_quote`) **무변경 통과**. 바뀐 테스트는 compose
  `test_transport_wiring.py` 의 scope 핀 1곳(속성이 세션으로 이동)과 증인 fakes/호출부(Protocol 교체)뿐.

### 7.3 공통

- digest: `expected_code_digest` `fe72348e…` → `b430dc27…`(W1) → **`b176ff65…`**(W2). 의존성 digest 는 배포 호스트 값 유지.
- 크기 예산: `build_tick_scheduler` 는 헬퍼(`_build_time_pacer`) 분리로 100 줄 안 · 재등재 3건
  (`wire_engine_and_driver` 151→155 · `_finalize` 105→108 · `compose_paper_runtime` 420→421).
- 게이트: 방화벽 PASS · lint-imports 3 kept · completion GREEN · spec PASS · contract PASS(+self-test) · citation PASS ·
  size budget PASS · black/ruff/mypy(src·tests) 통과.
- 리뷰: Codex 는 클라우드 환경 제외(운영자 2026-09-26) — Claude 쪽 `code-reviewer` 폴백 레인.
