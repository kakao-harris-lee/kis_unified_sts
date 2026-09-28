# kis_quote 관측 시각을 요청 시작에 묶기 — #810 수정 계획

- 작성: 2026-09-28 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `ac2efb0f`(#811 머지 직후)
- 요청: 운영자 2026-09-28 「#810 수정 계획 써줘」.
- 성격: 계획 + 구현(같은 PR). 운영자 처분 §6.1.
- 배포 영향: paper 는 `intake_kind: journal` 로 핀돼 있다(`_VALUE_PINS`). 이 수정은 **`kis_quote` 인입을 쓸 수 있게 만드는 것**이고, paper 설정값은 바뀌지 않는다.

## 0. 요약 — #810 의 세 결함과 한 가지 수정

| # | 결함 (main `ac2efb0f`) | 원인 |
|---|---|---|
| D-1 | `as_of` 가 **직전 패스의 캐시 판독** — 간격 ≥ 1000 ms(모의 시세 한도)에서 **항상 STALE**. #811 전에는 반대로 **나이 0 · HTTP 지연 무시(fail-open)** 였다 | 어댑터가 poll 안에서 `wall_clock_now()`(마지막 `evaluate()` 의 캐시값)를 찍는다 |
| D-2 | poll 뒤 평가가 실패하면 **관측 유실**(가격이 바뀔 때까지) | 중복 판별 digest 를 소비 전(poll 안)에 기록한다 |
| D-3 | 시각을 신뢰할 수 없으면 **루프가 죽는다**. 그 예외를 잡아도 평가가 poll 뒤에 있어 회복하지 못한다 | 어댑터가 poll 안에서 벽시계를 읽고 `KisQuoteWallClockUntrusted` 를 던진다 |

**수정은 하나다 — 어댑터는 벽시계를 읽지 않고 단조시계만 찍는다.**

1. 어댑터는 **요청 시작 · 응답 수신 순간의 단조시계 값**을 싣는 「미확정 관측」을 돌려준다.
2. 스케줄러가 **poll 뒤 평가(S')** 다음에 그 단조시계 값을 신뢰 판독에 사상해 `as_of`/`received_ms` 를 찍는다.
   - `as_of` = 요청 시작 → `source_age` ≥ HTTP 왕복. **지연이 신선도에 들어간다**(D-1).
3. 중복 판별 digest 는 **저장소 고수위(`after_as_of_ms`)가 전진했을 때만** 기록한다 → 소비되지 않은 시세는 다음 패스가 다시 낸다(D-2).
4. 어댑터가 벽시계를 읽지 않으므로 poll 은 더 이상 `KisQuoteWallClockUntrusted` 를 던지지 않는다. 신뢰할 수 없는 시각은 평가 뒤에 **이름 붙은 결과**로 다뤄진다(D-3).

## 1. 실측·코드 (main `ac2efb0f`)

| 무엇 | 위치 |
|---|---|
| 어댑터의 poll: 토큰 → `_fetch_quote` → 파싱 → `wall_clock_now()` → 중복 판별 → digest 기록 → `RawObservation` | `tos/runtime/src/tos_runtime/transport/kis_quote/adapter.py:342-412` |
| `raw_event_id = {source_id}:{instrument}:{as_of_ms}:{content_digest}` | `adapter.py:400-402` |
| 응답 본문에서 시각을 읽지 않는 것은 **구조적 사실**(모든 허용 TR) | `adapter.py:40-60` |
| `wall_clock_now()` = 마지막 평가의 캐시값 · 스냅샷은 `issue_monotonic_value` 를 가진다 | `time/service.py:697-711` · `:713-731`(`wall_clock_now_if_fresh`) |
| 평가 주기 사이 중단 관측 `max(0, Δwall − Δmono)` | `time/service.py:330-356` · `:622` |
| 패스 순서: 판독 → `before_decide`(평가) → `wall_clock_now()` → 결정 | `marketfeed/scheduler.py` `tick_once`(#811) |
| pacer·kis_quote 인입이 `build_tick_scheduler` 의 같은 `monotonic` 을 받는다 — 시간 서비스와 같은 원천이라는 것은 #806 리뷰 조치의 진술이고, **객체 동일성은 T-5 에서 테스트로 핀한다** | `compose/_marketfeed_wiring.py:509-526 · :654 · :725 · :758` |
| `RawObservation.as_of_ms` 는 필수 int · 「receipt 나 wrap 시각이 아니다」 | `marketfeed/ports.py:66-102` |
| 모의 시세 한도 1.0 rps clean · 2.0 rps 스로틀 | `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:1840-1846` |

## 2. 결정

### 2.1 포트 — `MonotonicAnchoredObservation`

`marketfeed/ports.py` 에 새 불변 타입을 둔다. 필드는 `instrument` · `fields` · `source_id` · `content_digest` ·
`requested_monotonic_ms` · `received_monotonic_ms` 이다. 그리고 순수 함수
`anchor_observation(pending, *, as_of_ms, received_ms) -> RawObservation` 을 둔다.

- `raw_event_id` 형식은 **오늘과 바이트 동일**하다(`{source_id}:{instrument}:{as_of_ms}:{content_digest}`). 도출
  위치만 어댑터에서 이 함수로 옮긴다.
- `ObservationIntake.poll` 의 반환형은 `Sequence[RawObservation | MonotonicAnchoredObservation]` 가 된다.
  `journal` 은 그대로 `RawObservation` 을 돌려준다.

### 2.2 시간 서비스 — 과거 단조시계 순간의 신뢰 판독

`TrustworthyTimeService.wall_clock_at_monotonic(mono_ms) -> int | None` 을 추가한다:

```text
S'_wall − (S'_mono − mono_ms) − 이번 주기에 관측된 중단(suspension)
```

- **정의역은 이번 주기로 한정한다**: `직전 평가의 mono ≤ mono_ms ≤ S'_mono`. 벗어나면 `None` 이다.
- TRUSTED 가 아니면 `None` 이다.
- 이것은 「지금」을 만들어 내는 외삽이 아니다(#806 계획 §3 의 기각 대상과 다르다). 이미 신뢰 판정을 받은 S' 에서
  **과거 방향으로만** 사상한다. 중단분을 빼는 것은 `as_of` 를 **더 이르게** 만드는 방향 — 나이를 키우는 보수
  방향이다.

### 2.3 스케줄러 — 훅 뒤에 찍기

`tick_once` 에서 `before_decide` 가 참을 돌려준 뒤, `decide_tick` 앞에서 미확정 관측을 `anchor_observation` 으로 확정한다.

- `as_of_ms = wall_clock_at_monotonic(requested_monotonic_ms)` · `received_ms = wall_clock_at_monotonic(received_monotonic_ms)`
- 사상이 `None`(신뢰 없음 · 정의역 밖)이면 새 결과 **`TickOutcome.SKIPPED_TIME_UNANCHORED`** 를 돌려준다. 소비는 없고
  루프는 계속된다(D-3).

### 2.4 어댑터

- `wall_clock_now()` 호출과 `KisQuoteWallClockUntrusted` 를 **제거**한다. 요청 직전·응답 직후에
  `monotonic.now_ms()` 를 찍어 `MonotonicAnchoredObservation` 을 돌려준다.
- 이 단조시계는 어댑터가 토큰 수명주기에 이미 쓰는 것과 같은 주입 원천이다.
- **중복 판별 digest (D-2)**: 확정하지 않은 digest 를 `_pending_digest` 로 들고 있는다. 다음 poll 에서
  `after_as_of_ms` 가 직전 poll 때보다 **전진했으면** 소비된 것으로 보고 기록한다. 전진하지 않았으면 미소비로
  보고 같은 시세를 다시 낸다.
  - 이 저장소에 이 종목을 쓰는 것은 이 스케줄러 하나뿐이다. 그래서 고수위 전진 = 소비다.
- 모듈 docstring 의 「Receipt-time anchor」 문단을 「요청 시작 anchor(단조시계) — 스케줄러가 평가 뒤에 찍는다」로
  다시 쓴다.

### 2.5 여전히 알 수 없는 것 (docstring 에 적는다)

KIS 응답에는 이벤트 시각이 없다. 그래서 서버 쪽에서 데이터가 이미 얼마나 낡았는지는 모른다. `as_of = 요청 시작`
은 **나이의 하한을 HTTP 왕복만큼 올릴 뿐**, 참 나이를 주지 않는다. 지금의 「하한 0」보다 엄격하지만 완전하지
않다고 명시한다.

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| `as_of` = 응답 뒤 S'(수신 시각) | 나이 ≈ 0 — 지연을 무시하는 원래의 fail-open 그대로 |
| `as_of` = 직전 패스 판독(현 상태) | 간격 ≥ 1000 ms 에서 항상 STALE — 인입을 쓸 수 없다 |
| kis_quote 일 때만 poll **앞에서도** 평가 | 증거 행 2 배 · 앞 판독과 poll 사이 간격이 다시 생긴다 |
| 응답 본문의 시각 필드 사용 | 허용 TR 전부에 대해 신뢰할 시각 필드가 확인되지 않았다(`adapter.py:40-60`) |
| 포트에 `acknowledge(observation)` 추가 | 모든 인입의 프로토콜 변경. `after_as_of_ms` 가 이미 소비 신호를 싣는다 |
| `run_forever` 에서 `KisQuoteWallClockUntrusted` 를 잡는다 | 신뢰할 수 없는 시각을 삼키는 쪽. 어댑터가 벽시계를 안 읽으면 예외 자체가 사라진다 |
| 단조시계 사상에서 중단분을 무시 | 중단이 끼면 `as_of` 가 늦어져 나이가 과소 — fail-open 방향 |

## 4. 작업

| # | 내용 | 종료 조건 |
|---|---|---|
| T-1 | 포트: `MonotonicAnchoredObservation` + `anchor_observation` · `wall_clock_at_monotonic` | `raw_event_id` 가 현 형식과 바이트 동일(같은 입력) · 사상 단위 테스트: 정의역 경계 둘 · 중단분 차감 · non-TRUSTED `None` |
| T-2 | 스케줄러: 훅 뒤 확정 · `SKIPPED_TIME_UNANCHORED` | 신뢰 없음 → 이름 붙은 결과 · `store.put` 0 · 다음 패스 회복 |
| T-3 | 어댑터: 단조시계 anchor · 벽시계·예외 제거 · 지연 digest 기록 · docstring | **가짜 전송 지연 주입**: 지연 L 이면 `source_age ≥ L`, `L > 800 − Σ` 이면 STALE, 작으면 FRESH · 평가 실패 뒤 다음 패스가 같은 시세를 TICKED · TICKED 뒤 같은 시세는 `SKIPPED_NO_OBSERVATION`(유령 반복 방지 유지) |
| T-4 | #811 이 남긴 고정 테스트 **뒤집기** — 「항상 STALE」 → 지연 의존 · 「평가 실패 뒤 유실」 → 재출력 · 예시·paper 주석의 「#810 전까지」 문구 제거 | 두 테스트 이름·단정 교체 |
| T-5 | compose: 인입과 시간 서비스가 **같은 `MonotonicSource` 객체**인지 핀 | 배선을 끊으면 red |
| T-6 | digest 재도출(마지막 커밋) · 계획 §7 착지 · INDEX · 런북 영향 없음 확인 | 통상 게이트 + **CI 와 같은 mypy `tos/runtime/tests`** |

**뮤테이션**(red 확인):
- 사상에서 중단분 빼기 제거 → 중단 테스트 red
- `as_of` 에 수신 시각을 사용 → 지연 테스트 red
- digest 를 poll 에서 즉시 기록 → 재출력 테스트 red
- 사상 `None` 인데 확정 진행 → D-3 테스트 red
- 정의역 하한 제거 → 경계 테스트 red

## 5. 위험

- **포트 반환형 확장**: `ObservationIntake` 구현이 둘뿐(`journal`·`kis_quote`)이라 영향 범위가 작다. 가짜 인입을
  쓰는 테스트는 그대로 `RawObservation` 을 돌려준다.
- **중단 차감은 직전 주기의 관측에 기댄다**: 중단이 `MAX_process_suspension_ms`(2000)를 넘으면 시간 상태가
  TRUSTED 를 잃어 사상이 `None` 이 된다(fail-closed). 그 아래의 중단은 차감되어 보수 쪽으로 간다.
- **실측은 가짜 KIS 서버 안에서만 한다.** 모의 서버 GET 실측(1 rps 이하 · 수 분)은 커스터디에 모의 앱 키 scope 가
  필요한 별도 단계다 — §6-2.
- 런타임 소스 변경 → digest 재도출 · 병행 소스 PR 이 있으면 rebase 뒤 재도출.

## 6. 운영자 확인

1. **설계(§2)** — 단조시계 anchor · `wall_clock_at_monotonic` · `SKIPPED_TIME_UNANCHORED` · 지연 digest 기록에 동의하는지.
2. **모의 서버 GET-only 실측** — 이번 PR 에 포함 / **별도 단계로 미룸(권고)**.
3. 구현은 이 브랜치에서 처분 뒤 진행 — 동의 여부.

### 6.1 운영자 처분 (2026-09-28)

1. **설계(§2)** — 동의.
2. **모의 서버 GET-only 실측** — 별도 단계로 미룬다. 이번 PR 은 가짜 KIS 서버 안에서만 검증한다.
3. **구현은 이 브랜치(PR #812)에서** — 동의.

## 7. 착지 기록 (2026-09-28 · 브랜치 `fix/tos-kis-quote-request-anchor` · PR #812)

기준 main `ac2efb0f`. 운영자 처분 §6.1 대로 **가짜 KIS 서버 안에서만** 검증했다(모의 서버 GET 실측은 별도 단계).

### 7.1 무엇이 어디로 갔나

| 작업 | 착지 |
|---|---|
| T-1 | `marketfeed/ports.py`: `MonotonicAnchoredObservation` · `anchor_observation` · `ObservationIntake.poll` 반환형 확장 · `TickOutcome.SKIPPED_TIME_UNANCHORED` · `time/service.py`: `wall_clock_at_monotonic` + `_capture_cycle` |
| T-2 | `marketfeed/scheduler.py`: `TickScheduler._anchor_polled` — `before_decide` 뒤 · `decide_tick` 앞 |
| T-3 | `transport/kis_quote/adapter.py`: 단조시계 2회 스탬프 · 벽시계 판독 전면 제거 · `_pending_digest` 지연 기록 |
| T-4 | #811 이 남긴 두 고정 테스트 교체 · `#810 전까지 …` 문구 전건 제거(`ports.py`·`scheduler.py`·`time_pacer.py`·`compose/_marketfeed_wiring.py`·예시/paper `marketfeed.yaml` 주석·`tests/compose/test_marketfeed_pacing_budget.py`) |
| T-5 | `tests/compose/test_marketfeed_intake_kind_wiring.py`: 인입과 시간 서비스가 **같은 `MonotonicSource` 객체**임을 `is` 로 핀 |
| T-6 | digest 재도출 · 이 절 |

kis_quote 인입이 저널 pacing 가드에서 면제되는 것은 유지하되 **이유를 정정**했다: 「그 예산은 상류 저널 수집기 몫이고 그 인입에는 그런 수집기가 없다 — 그 인입의 나이는 **패스마다 실측되는 요청 왕복**이지 poll 위상에서 파생되지 않는다」.

### 7.2 실측 (가짜 KIS 서버 · 배포된 `config/tos_runtime/paper/time.yaml`)

예산 = `MAX_time_conservative_freshness_age_ms`(1000) − Σdelay_bounds(4×50) = **800 ms**.

| 주입 지연 L | 실측 `source_age` | 판정 |
|---|---|---|
| 1000 ms | **1002 ms** | STALE (1002 + 200 > 1000) |
| 0 ms (loopback) | **1 ms** | FRESH |

`source_age ≥ L` 이 성립한다 — #809 이후의 「≈ 패스 간격」도, #809 이전의 「0(왕복 미측정)」도 아니다.

### 7.3 뮤테이션 (전건 red 확인 후 복구)

| # | 뮤테이션 | red |
|---|---|---|
| 1 | 사상에서 중단분 차감 제거 (`time/service.py`) | `test_mapping_subtracts_the_suspension_this_cycle_observed` |
| 2 | `as_of` 에 수신 시각 사용 (스케줄러) + 요청 스탬프를 응답 뒤로 이동 (어댑터) | `test_tick_once_anchors_a_pending_observation_on_the_request_instant` · `test_an_injected_transport_delay_lands_in_source_age_and_reads_stale` |
| 3 | digest 를 poll 안에서 즉시 기록 | 어댑터 재출력 2건 + 체인 4건 (계 6건) |
| 4 | 사상이 `None` 인데 대체값으로 확정 진행 | 스케줄러 2건 + 체인 3건 (계 5건) |
| 5 | 정의역 하한 제거 | `test_mapping_refuses_one_millisecond_below_the_domain_floor` · `test_the_domain_floor_advances_with_each_cycle` |

T-5 배선 끊기(인입에 사설 `ProcessMonotonicSource` 주입)도 red 확인 후 복구했다.

### 7.4 계획에서 벗어난 것 (전건 사유 포함)

1. **어댑터에서 `time_service` 주입 자체를 제거**했다(`WallClockSource` 프로토콜 · `KisQuoteWallClockUntrusted` · `_build_intake` 의 인자까지). 계획은 「poll 안의 호출과 예외 제거」만 요구했지만, 벽시계 판독이 사라지면 그 의존성은 **아무도 읽지 않는 채로 남는다** — 나중에 잘못 문서화되는 바로 그 형태다. 사전 확인: 두 이름을 쓰는 곳은 이 패키지 `__init__` 재수출과 이 스위트뿐이었고, 둘 다 같이 정리했다(deprecation 경로 없음 — 외부 소비자 0).
2. **`TrustworthyTimeService.evaluate` 가 100줄 예산을 넘겼다**(103). 예외 등재가 아니라 `_capture_cycle` 로 분해했다.
3. **중단 관측이 없는 주기(`suspension_ms is None`)는 사상이 `None`**이다. 계획의 식에는 그 항의 값이 없다 — 미지를 0 으로 접지 않는다(첫 `evaluate()`, 또는 양쪽 주기 중 하나에 벽시계 판독이 없는 경우).
4. **미확정 관측이 하나라도 사상 불가면 배치 전체를 보류**한다. 살아남은 것만 추리면 `decide_tick` 이 「생존자 중 최신」을 최신으로 고른다.
5. 어댑터에 `_polled_once` 를 별도로 둔다 — `after_as_of_ms` 의 `None` 은 「이전 poll 없음」과 「이전 mark 가 None」 두 사실을 겸할 수 없다.
6. **스케줄러 레벨 체인 테스트는 새 모듈** `tests/marketfeed/test_scheduler_kis_quote_anchor.py` 에 둔다(실 저장소·실 정책·실 스케줄러가 필요해 어댑터 스위트 범위를 넘는다). 지연 실측 2건은 어댑터 스위트에 남는다.
7. 지연 실측은 **진짜 `TrustworthyTimeService`**(실 프로세스 단조시계 + `LocalSystemClockReader`)로 사상한다 — 가짜 사상은 「검사가 검사 대상의 사본을 읽는」 형태가 된다.
8. `tests/marketfeed/test_scheduler.py::_build_scheduler` 에 `time_projection` 오버라이드를 추가했다 — `MagicMock` 투영으로는 실제 커널 리졸버가 TICKED 경로를 거부한다.
9. `wall_clock_at_monotonic` 안에서 `issue_mono_ms: int | None` 로 **명시 주석**을 달았다. 이 호스트 venv 는 스텁이 더 있어 그 줄이 `no-any-return` 하나를 새로 냈고, 주석으로 전수 카운트를 main 과 같게 맞췄다(§7.5).

### 7.5 게이트 / 테스트

| 항목 | 결과 |
|---|---|
| `tos_firewall_check.py` · `lint-imports` | PASS · 3 contracts kept |
| `tos_contract_check.py` (+ `--self-test`) | PASS · 뮤테이션 145종 전건 판별 |
| `tos_completion_status.py --check` | GREEN (violations=0) |
| `tos_spec_status.py --check` | PASS (비차단 baseline-plan 경고는 기존) |
| `tos_evidence_citation_check.py` · `tos_named_tbd_guard.py` | PASS · PASS (0 violations) |
| `tos_size_budget.py --check` | PASS (0 violations) |
| black · ruff | 1293 files unchanged · all checks passed |
| mypy `tos/src` | Success (265 files) |
| mypy `tos/runtime/src` | 27 errors — **main 기준선과 동일**(전건 기존 `no-any-return`; 이 호스트 스텁 탓) |
| mypy `tos/runtime/tests` (CI 와 같은 `--disable-error-code=no-untyped-def`) | 122 errors in 45 files — **main 기준선과 동일**, 검사 파일은 233 → 235 (신규 2건 0 errors) |
| `pytest tos/runtime/tests` | **3150 passed** |
| `pytest tests/unit/scripts/test_render_paper_config.py tests/tools` | 1399 passed · 3 failed — `tests/tools/test_u17_verify.py` 기존 로컬 실패(`yq` 미설치, CI 는 `--ignore`) |

main 기준선은 `git archive origin/main` 로 추출한 트리에서 같은 명령으로 측정했다(이 호스트 venv 는 스텁이 더 있어 CI 와 절대 수치가 다르다 — 그래서 절대값이 아니라 **차이**를 본다).

### 7.6 배포 영향

없다. paper 는 `intake_kind: journal` 로 핀돼 있고 값은 바뀌지 않았다(주석만). `config/tos_runtime/paper/time.yaml` 승인값 무변경. 런타임 소스가 바뀌었으므로 `expected_code_digest` 는 재도출했다(마지막 커밋 · `release.yaml` 12차 + `_VALUE_PINS` 동시 갱신).
