# 시간 판독을 인입 판독 뒤로 — #809 수정 계획

- 작성: 2026-09-27 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `4b1144d3`(#808 머지 직후)
- 요청: 운영자 2026-09-27 「#809 수정 계획 써줘」.
- 성격: 계획 + 구현(같은 PR). 운영자 처분 §6.1.

## 0. 요약

1. **결함 (#809)**: 한 패스는 **시간 평가(S) → 저널 판독(R)** 순서로 돈다. 그래서 S 와 R 사이에 추가된 관측은
   판독 시각보다 늦게 찍혀 있을 수 있다.
   - `R − S > 수집기 지연 + 50 ms`(`MAX_future_timestamp_tolerance_ms`)이면 그 관측은 미래 시각 → **CONFLICTED**
     로 판정되어, 결정 없이 소비된다(재시도 없음).
   - 수집기 지연이 작을수록(실제 시세 수집기) 필요한 정지가 짧다. 예: 지연 20 ms 면 약 70 ms 정지로 충분하다.
2. **수정 — 순서를 바꾼다**: **저널 판독(R) → 시간 평가(S') → 결정.**
   - 제정신인 수집기라면 모든 관측은 `as_of ≤ R < S'` 이다. 그러면 `source_age ≥ 0` 이 되고, CONFLICTED 는
     **진짜 시계 어긋남(수집기 시계가 50 ms 넘게 앞섬)** 에서만 난다.
   - 커널의 미래 시각 방어는 좁히지도 넓히지도 않는다.
   - 평가 횟수(= 증거 행)는 **그대로** 패스당 1회다.
3. **대가 — `kis_quote` 가 fail-open 에서 fail-closed 로 바뀐다(#810 과 결합)**: 그 어댑터는 poll 안에서
   `wall_clock_now()`(캐시값)로 `as_of` 를 찍는다. 순서가 바뀌면 그 캐시값은 **직전 패스**의 판독이다. 그러면
   `source_age ≈ 패스 간격` 이 되고, 모의 시세 한도 때문에 poll 을 1000 ms 미만으로 못 줄이므로 **항상 STALE** 이다.
   - paper 는 `journal` 로 핀돼 있어 운영 영향은 0 이다.
   - 이 순서가 오히려 #810 의 올바른 수정(응답 뒤 판독으로 `as_of` 찍기)을 **가능하게** 한다 — §2.4.

## 1. 실측·코드 (main `4b1144d3`)

| 무엇 | 위치 |
|---|---|
| `wall_clock_now()` = 마지막 `evaluate()` 의 캐시값 | `tos/runtime/src/tos_runtime/time/service.py:697-711` |
| 평가는 패스 앞 훅이다 — `run_forever` 가 `before_pass()` 다음에 `tick_once()` 를 부른다 | `marketfeed/scheduler.py:418-419` · `marketfeed/time_pacer.py:89` `before_pass` |
| `tick_once` 순서: `now_ms = wall_clock_now()` → 세션 맥락 → `latest_as_of` → `intake.poll` → `decide_tick` | `marketfeed/scheduler.py:355-367` |
| `source_age = wall_clock_now() − as_of` (같은 캐시값) | `marketfeed/time_projection.py:218-224` |
| CONFLICTED 조건 `−source_age > future_tolerance` | `tos/src/tos/time/predicates.py:375` |
| `future_tolerance = 50` (VER-002 L1074 · APPROVED) | `config/tos_runtime/paper/time.yaml:26` |
| 관측 1건 CONFLICTED / 추가 35건 | #808 계획 §7.3(하네스: 같은 프로세스 스레드, 수집기 지연 200) |
| 소비 = `store.put` 이 `latest_as_of` 를 전진시킨다 → 재시도 없음 | `scheduler.py:375` |
| `kis_quote` 는 poll 안에서 `wall_clock_now()` 로 `as_of` 를 찍는다 | `transport/kis_quote/adapter.py:363` |
| compose 가 pacer 를 `before_pass` 로 주입한다 | `compose/_marketfeed_wiring.py:494`(`_time_pacer_pass`) · `:745` |

## 2. 결정

### 2.1 패스 순서

```text
현재:  [pacer 평가 S] → tick_once{ now=S · 세션 · latest · poll(R) · decide · issue }
수정:  tick_once{ latest · poll(R) · [pacer 평가 S'] · now=S' · 세션 · decide · issue }
```

- `TickScheduler` 의 주입 훅을 **poll 뒤·결정 앞**에서 부른다. 이름은 `before_pass` → `before_decide` 로 바꾼다
  (이름이 위치를 말하게). `tick_once` 는 여전히 평가를 **직접 하지 않는다** — 생성자 주입 훅을 부를 뿐이다(#806 의
  「`tick_once` 는 순수」 원칙 유지). `run_forever` 는 `tick_once` 만 부른다.
- pacer 는 **변경 없음**. 판단 규칙(열림 매번 · 닫힘 60 s · 미확정은 열림처럼 · 실패는 그 패스 틱 생략)이 그대로다.
  호출 위치만 옮긴다.
- 평가 실패 시: 새 이름 붙은 결과 **`TickOutcome.SKIPPED_TIME_NOT_EVALUATED`** 를 반환한다. `store.put` 이 없으므로
  `latest_as_of` 가 전진하지 않는다 → 다음 패스가 **같은 관측을 다시 읽는다(손실 없음)**.
  지금처럼 `tick_once` 자체를 건너뛰면 결과가 없으니, 이름 붙은 부재로 만든다(`TickOutcome` 독스트링의 ∅ 양방향 규율).

### 2.2 예산에 미치는 영향 — 없음

`source_age` 의 기준점이 R 앞에서 R 뒤(S')로 옮겨가지만, 최악 나이는 여전히 「직전 패스 직후 추가 → 다음 패스의
평가」 사이다. 곧 `poll_interval_ms + 패스 소요` 로 **같다**. #808 의 가드
(`poll + journal_pass_allowance_ms ≤ 800`)가 그대로 유효하고, allowance 100 은 평가 소요(최대 12.3 ms)를 이미 포함한다.

### 2.3 남는 CONFLICTED

수정 뒤에는 `as_of > S' + 50` 일 때만 난다. 저널 줄은 poll 이전에 쓰였으므로 `as_of` 는 수집기 시계 기준 R 이전이다.
그러므로 이것은 **수집기 시계가 50 ms 넘게 앞섰다**는 뜻이고, 커널이 잡아야 하는 바로 그 사실이다.

### 2.4 `kis_quote` (#810) — 이번 범위 밖, 방향만 확정

- 수정 뒤 `kis_quote` 의 `as_of` = 직전 패스 판독이 된다 → `source_age` ≈ 패스 간격 → poll ≥ 1000 ms 에서 **항상
  STALE**. 지금의 「항상 0 · HTTP 지연 무시」(fail-open)에서 **보수 과대추정**(fail-closed)으로 바뀐다.
- #810 의 수정은 이 순서 위에서 쉬워진다. 응답 뒤의 평가 S' 가 바로 어댑터 docstring 이 원하던 「응답 수신 뒤 판독」
  이기 때문이다. 수신 시각을 기준으로 삼는 인입(`receipt_anchored`)은 `as_of` 를 S' 로 찍게 한다 — 구체 설계는 #810.
- paper 는 `intake_kind: journal` 이 `_VALUE_PINS` 로 핀돼 있어, 이 전이 동안 운영 영향은 없다. 예시 파일과
  `kis_quote` 어댑터 docstring 에 「#810 전까지 STALE」 을 적는다.

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| `decide_tick` 이 `as_of > now + tolerance` 인 관측을 발행하지 않고 다음 패스로 미룬다(리뷰 제안) | **진짜 시계 어긋남을 숨긴다.** X ms 앞선 수집기의 관측은 X ms 뒤 판독에서 FRESH 로 통과한다. 커널의 미래 시각 방어가 무력해진다 |
| 미루되 allowance 만큼만 | 어긋남을 ≤ 150 ms 숨기고, 두 번째 허용치 개념을 만든다 |
| poll 뒤에 평가를 한 번 **더** 한다 | 증거 2 배(110 → 220 MB/일) · CPU 2 배. 순서 변경으로 같은 효과를 평가 1회로 얻는다 |
| 캐시값 + 단조시계 경과분 | #806 계획 §3 에서 이미 기각 — 신뢰 판정 없이 시각을 만들어 낸다 |
| 미래 허용치 상향 | VER-002 승인값이고, 어긋남 수용 폭만 넓힌다 |
| `kis_quote` 를 같은 PR 에서 수정 | 수신 시각 기준 설계는 별도 결정(`RawObservation` 계약·어댑터 계약) — #810 |

## 4. 작업

| # | 내용 | 종료 조건 |
|---|---|---|
| T-1 | `TickScheduler`: 훅을 poll 뒤·결정 앞으로(`before_decide`) · `SKIPPED_TIME_NOT_EVALUATED` · `run_forever` 는 `tick_once` 만 | 결정적 테스트: 가짜 시간 서비스로 「S 뒤·R 앞에 `as_of = S + 200` 관측 추가」 → **수정 전 CONFLICTED 재현(먼저 red)**, 수정 후 FRESH · 평가 실패 패스는 `store.put` 0 이고 다음 패스가 같은 관측을 TICKED · 닫힘 60 s 주기 테스트 무변경 통과 |
| T-2 | compose 배선(`_marketfeed_wiring.py:745`) · pacer 호출부 이름 · `kis_quote` 예시·어댑터 docstring 에 #810 전이 문구 | compose e2e(`test_run_e2e.py`) 통과 · `kis_quote` STALE 전이를 테스트로 **명시**(숨기지 않는다) |
| T-3 | 리허설 재측정 — #808 과 같은 진단에 **정지 주입**(평가가 끝난 뒤 80 ms sleep) · 수집기 지연 0 · 0.5 s 마다 관측 · 90 s | 수정 전(main `4b1144d3`) CONFLICTED > 0, **수정 후 0**, STALE 0 (정지 80 ms < allowance 100) |
| T-4 | `expected_code_digest` 재도출(마지막 커밋) · 런북 §5 ④ 한 줄 · INDEX 행 · 이 계획 §7 착지 기록 · #809 링크 | 통상 게이트 전부 |

**뮤테이션**(red 확인): 훅을 다시 poll 앞으로 → CONFLICTED 재현 테스트 red · 평가 실패 시 `store.put` 수행 → 손실
테스트 red · `SKIPPED_TIME_NOT_EVALUATED` 대신 `SKIPPED_NO_OBSERVATION` 반환 → 결과 이름 테스트 red.

## 5. 위험

- **패스당 poll 이 평가보다 먼저 일어난다.** 닫힘 구간에서도 poll 은 지금과 같은 빈도다(현재도 pacer 가 due 가
  아니면 `tick_once` 가 poll 한다). `journal` 은 파일 읽기다.
- `kis_quote` 는 #810 전까지 항상 STALE 이다(§2.4). 배포 영향 0 · 명시적 테스트로 고정한다.
- 세션 맥락이 S' 기준으로 바뀐다 — 경계 시각(개장 08:45 직전·직후)에서 판정이 poll 소요만큼 늦게 바뀐다(수 ms).
- 소스 변경 → digest 재도출. 병행 소스 PR 이 먼저 머지되면 rebase 뒤 다시 도출한다(메모리 함정 ①).

## 6. 운영자 확인

1. **순서 변경(§2.1)** 과 새 결과 이름 `SKIPPED_TIME_NOT_EVALUATED` — 동의 여부.
2. **`kis_quote` 가 #810 전까지 항상 STALE**(fail-open → fail-closed) — 수용 여부. 아니면 #810 을 같은 PR 에 묶는다.
3. 구현은 이 브랜치에서 처분 뒤 진행 — 동의 여부.

### 6.1 운영자 처분 (2026-09-27)

1. **순서 변경 + `SKIPPED_TIME_NOT_EVALUATED`** — 동의.
2. **`kis_quote` 가 #810 전까지 항상 STALE** — 수용. #809 만 구현하고, #810 은 별도로 처리한다.
3. **구현은 이 브랜치(PR #811)에서** — 동의.

## 7. 착지 기록 (2026-09-27)

### 7.1 무엇이 들어갔나

| # | 커밋 | 내용 |
|---|---|---|
| T-1 | `36e2f354` | `marketfeed/scheduler.py` 순서 변경(판독 → 훅 → 판독값·세션 → 결정) · 훅 이름 `before_pass` → `before_decide`(생성자 인자 · pacer 메서드 · compose 배선) · `marketfeed/ports.py` 에 `TickOutcome.SKIPPED_TIME_NOT_EVALUATED` · `run_forever` 는 `tick_once` + `sleep` 만 · 테스트 3건 신규 |
| T-2 | `97c1bd77` | `kis_quote` 가 #810 전까지 **항상 STALE** 임을 테스트로 고정(실 어댑터 + 실 커널 `freshness_verdict` + 배포 `time.yaml` 승인값) · 어댑터/배선 독스트링 · `marketfeed.example.yaml` · `config/tos_runtime/paper/marketfeed.yaml` 문구 |
| T-3 | — | 리허설 재측정(§7.3) |
| T-4 | 아래 | 런북 §5 ④ · INDEX 행 · 이 기록 · `expected_code_digest` 재도출 |

`tick_once` 는 여전히 시간을 **직접 평가하지 않는다** — 주입 훅을 부를 뿐이다(§2.1). pacer 의
판단 규칙(열림 매 패스 · 닫힘 60 s · 미확정은 열림처럼 · 실패는 그 패스 결정 생략)은 **한 줄도
바뀌지 않았고**, 호출 위치와 이름만 옮겼다. `build_tick_scheduler` 는 인자 1:1 개명이라 100 줄
예산 안에 그대로 남는다(`--check` 위반 0 유지).

### 7.2 회귀 테스트와 뮤테이션

회귀 테스트(`tos/runtime/tests/marketfeed/test_scheduler.py`
`test_an_observation_appended_since_the_last_evaluation_reads_fresh_not_conflicted`): `evaluate()`
가 판독값을 500 ms 전진시키는 가짜 시간 서비스 + poll 때 `as_of = wall_clock_now() + 200` 으로
찍는 인입. 실 `SqliteSnapshotStore`·실 발행기·실 커널 resolver 를 지나 드라이버가 받은 페이로드의
`TimeAdmissionInputs` 를 **커널 술어로** 판정한다. 수정 후 `source_age = +300` · `FRESH` ·
`time_admits` 허용. 순서를 되돌리면 `source_age = -200` → 커널 `freshness_verdict` **CONFLICTED**
(실측 확인: `freshness_verdict(-200, (50,)*4, 1000, 50) = CONFLICTED`).

| 뮤테이션 | red 로 바뀐 테스트 |
|---|---|
| 훅을 다시 poll **앞**으로 | **3건** — 회귀(`source_age == -200`) · `SKIPPED_TIME_NOT_EVALUATED` 순서(poll 미호출) · 미소비 재판독(`polls == [None]`) |
| 평가 실패 시 `store.put` 수행 | **2건** — 미소비 재판독(고수위가 전진) · `store.put` 미호출 |
| `SKIPPED_NO_OBSERVATION` 반환 | **2건** — 결과 이름 2건 |

각 뮤테이션은 적용 → red 확인 → 원복했다. 루프 쪽은
`test_run_forever_calls_nothing_but_tick_once_and_sleep` 이 「훅을 루프에 되돌리면 red」를 잡는다.
닫힘 60 s 주기 테스트(`test_time_pacer.py`)는 **메서드 이름만** 바뀐 채 전건 통과한다.

### 7.3 실측 — 정지 주입 리허설 (호스트 로컬 · 2026-09-27 19:10/19:12 KST · 실주문 0 · 네트워크 없음)

`compose_paper_runtime`(세션 시계만 2026-09-28 10:00 KST 주입) + 실 `run_forever` 90 s ·
0.5 s 마다 관측 1건(`as_of = now`, 수집기 지연 **0**) · **정지 주입**: `TrustworthyTimeService
.evaluate` 를 감싸 실 평가가 돌아온 **뒤** 80 ms sleep. 렌더는 각 워크트리에서 부팅 직전에.
정지는 클래스 속성에 걸었다 — compose 가 pacer 에 `time_service.evaluate` 를 **바운드 메서드로**
넘기므로 인스턴스 속성 패치는 pacer 에 보이지 않는다.

| | **수정 전** (분리 워크트리 `4b1144d3`) | **수정 후** (`97c1bd77`) |
|---|---|---|
| 소비(`EVENT_CONSUMED`) | 162 | 166 |
| **CONFLICTED** | **15** | **0** |
| STALE | 1 | 1 |
| 그 STALE 1건의 정체 | **렌더 부팅 증명 관측**(소비 #1 — `withheld_sequence` 첫 항목) | 같음 |
| 추가 관측 중 CONFLICTED·STALE | 15 / 161 · 0 / 161 | **0 / 165 · 0 / 165** |
| `DECISION_WITHHELD` | 16 | 1 |
| 결정 결과 | NoAction 74 · Proposal 72 | NoAction 84 · Proposal 81 |
| `TIME_HEALTH_SNAPSHOT` | 164 / 90.7 s | 168 / 90.7 s |
| `FLOW_HALTED` | 72 | 81 |
| data dir | 10.73 MB / 90.7 s | 10.78 MB / 90.7 s |

- **목표 달성.** 수정 전 CONFLICTED 15 > 0 · 수정 후 추가 관측 중 CONFLICTED **0** · STALE **0**.
- 남은 STALE 1건은 두 회차 모두 **첫 소비 = 렌더가 만든 부팅 증명 관측**이다(소비 순서로 확인).
  §3 의 「고칠 수 없다」가 그대로고 런북 §5 ④ 에 이미 적혀 있다.
- 평가 1회당 80 ms 정지에도 평가 횟수·증거량은 두 회차가 같은 자릿수다 — 순서 변경은 평가를
  늘리지 않는다(§2.2).
- `FLOW_HALTED` 는 전건 `STAGE_DENIED | the venue / broker quantity constraint is incomplete`
  — venue `max_quantity` 가 null 인 **의도된 fail-closed** 로, #808 리허설과 같은 사유다.
- 증거 페이로드에서 읽은 필드는 `kind`/`halt_reason`/`detail`/`outcome_type` 뿐이다(모의 계좌
  좌표가 들어 있는 다른 필드는 조회하지 않았다).

### 7.4 `kis_quote` 전이 — 숨기지 않고 고정했다

수정 뒤 이 인입의 `as_of` 는 **직전 패스**의 캐시 판독값이므로 `source_age ≈ 패스 간격`이다.
모의 시세 한도(1.0 rps clean · 프로브 P-13)가 실질 하한으로 두는 간격 1000 ms 는 승인 예산
1000 − 4×50 = 800 ms 를 넘으므로 **브로커가 허용하는 어떤 간격에서도 FRESH 가 아니다**. 즉
fail-open(항상 0)에서 fail-closed(그 간격대에서 STALE)로 바뀐다 — 운영자 처분 §6.1-2 로 수용된
전이다.

> ⚠ **그 1000 ms 하한은 설정이 강제하지 않는다**(§7.8 LOW-2). `kis_quote` 에 더 짧은
> `poll_interval_ms` 를 적는 배포를 거부하는 로더 코드는 없고, 그때는 `source_age` 가 800 ms
> 예산 안에 들어와 **FRESH 로 읽힐 수도 있다**(대신 브로커가 스로틀한다). 그래서 「항상 STALE」
> 은 **허용 가능한 간격에서의 산술**이지 코드가 보장하는 불변식이 아니다.

테스트(`tos/runtime/tests/transport/kis_quote/test_adapter.py`
`test_the_previous_pass_stamp_exceeds_the_budget_at_every_admissible_spacing` — 이름은 §7.8 에서
「스케줄러 순서」가 아니라 **허용 간격에서의 산술**을 고정한다는 뜻으로 개명했다)는 실
어댑터를 가짜 KIS 서버에 물려 stamp 가 poll 이전 판독값임을 확인하고, 배포
`config/tos_runtime/paper/time.yaml` 에서 읽은 승인 한계로 커널 `freshness_verdict` 가 STALE
임을 판정한다. 숫자를 테스트에 다시 적지 않는다(가드가 자기가 지키는 값의 사본을 읽으면 안
된다는 이 저장소의 반복 결함 형태). paper 는 `intake_kind: journal` 이라 배포 영향 0 이고,
#810 은 **구현하지 않았다**.

### 7.5 `expected_code_digest` 재도출

런타임 소스(`marketfeed/{scheduler,ports,time_pacer}.py` · `compose/_marketfeed_wiring.py` ·
`transport/kis_quote/adapter.py`)가 바뀌었으므로 재도출했다.

```text
06508a5d85305a23f034624b330178bff10e3d89046e5ff3c1748866ddc0eed3   (이전 · #808 머지 · main 4b1144d3)
1f4f5ae52343da004d341a93febb87e487b7ffb6a24ab0a99def8d88a1d18462   (현재)
```

`print-digests` 와 `observe_source_tree_digest()` 두 경로 일치. `config/tos_runtime/paper/release.yaml`
(값 + 헤더 + 10차 이력 주석)과 `test_deploy_approved_values.py::_VALUE_PINS` **두 곳 모두** 갱신.
`expected_dependency_set_digest` 는 **바꾸지 않았다** — 같은 배포 호스트 루트 `.venv`
(python 3.12.12 / sqlite 3.45.1)에서 출력이 커밋된 값과 바이트 동일했다.

### 7.6 편차

1. **§4 T-2 가 지정하지 않은 파일 한 곳을 더 고쳤다** — `config/tos_runtime/paper/marketfeed.yaml`
   의 주석. 그 파일은 `kis_quote` 의 `source_age` 가 「항상 0」이라고 적고 있었고 이 변경이 그
   문장을 **거짓으로** 만든다. 값은 한 줄도 바꾸지 않았다(주석만) — `_FIXTURE_VALUE_PINS` 전건
   통과.
2. **T-1 커밋에 `compose/_marketfeed_wiring.py` 의 `kis_quote` 문단 정정이 함께 들어갔다.**
   같은 파일의 인자 개명이 T-1 에서 필요했고, 그 파일의 문단은 순서 변경이 직접 거짓으로 만드는
   서술이라 같은 커밋에서 고쳤다. 나머지 전이 서술과 테스트는 T-2 커밋이다.
3. **회귀 테스트는 계획이 말한 「수정 전 CONFLICTED 재현」을 테스트 2개로 나누지 않았다.**
   한 테스트가 FRESH 를 주장하고, 순서를 되돌리는 뮤테이션으로 CONFLICTED 재현을 확인했다
   (§7.2). 코드베이스에 CONFLICTED 를 주장하는 테스트를 남기면 수정된 코드에서 red 가 된다.

### 7.7 게이트

방화벽 PASS · `lint-imports` 3 contracts kept / 0 broken · completion **GREEN(위반 0)** ·
spec PASS(문서 13 · ADR 45 · baseline-plan WARNING 은 기존 비차단) · contract PASS +
self-test PASS(뮤테이션 145종) · citation PASS(README 3개 8건) · named-TBD guard PASS(46 파일
스캔 · 위반 0) · size budget PASS(위반 0 · 등재 39 — `build_tick_scheduler` 는 인자 1:1 개명이라
100 줄 그대로) · ruff PASS · black: **이 브랜치가 바꾼 `.py` 11건 전건 통과**(저장소 전체
`tos/ scripts/` 의 32건 미포맷은 분리 워크트리 `4b1144d3` 에서도 **같은 32건** — 기존 baseline).

테스트: `tos/runtime/tests` **3123 passed**(#808 머지 시점 3119 + 신규 4) · `tos/tests` 커널
**9601 passed**(`tos/src` 는 손대지 않았고 확인용으로 돌렸다) · `tests/tools` + `tests/tos_l3` +
`tests/unit/scripts/test_render_paper_config.py` **1394 passed**(기존 로컬 실패
`tests/tools/test_u17_verify.py` 3건은 `yq` 미설치 — CI 는 `--ignore`).

### 7.8 리뷰 처분 (`code-reviewer`, 같은 모델 계열 — 잠정)

PR #811 · 판정 **needs-attention → 대응 완료** · MEDIUM 1 · LOW 3. Codex 는 이 범위(되돌리기
어려운 경로 아님)에서 제외이므로 같은 모델 계열의 Claude 쪽 폴백 레인이고, 그래서 **잠정**이다.

| # | 지적 | 처분 |
|---|---|---|
| MEDIUM | 「관측을 소비하지 않으므로 **다음 패스가 다시 읽는다**」가 `kis_quote` 에서 **거짓** — 그 어댑터는 `after_as_of_ms` 를 무시하고 `_last_content_digest` 를 poll 안에서 커밋하므로(`transport/kis_quote/adapter.py:385-388`), 소비되지 않은 관측이 **버려진다**. 순서 변경이 만든 새 결함 | **문구 한정**(4곳) + **고정 테스트 추가**. 어댑터 코드는 **손대지 않았다** — #810 범위 (`7ea6433b`) |
| LOW-1 | 성공 경로가 `now_ms` 를 훅 **뒤**로 고정하지 않는다 — 회귀 테스트가 `now_ms` 를 위로 올려도 green | 회귀 테스트에 `_last_tick_wall_clock_ms` 단언 추가 + **세션 경계 행동 테스트 신규**. 뮤테이션 red 확인 (`04a23a2b`) |
| LOW-2 | 「항상 STALE」이 **아무도 강제하지 않는 간격 하한**에 의존한다 | 6곳 문구 한정 + 테스트 개명 (`116c5321`) |
| LOW-3 | 시간 미신뢰 시 `kis_quote` poll 이 **터진다** — 순서 변경으로 도달 가능해졌다 | **#810 노트로 이관 · 코드 변경 없음**(아래 근거) |

**MEDIUM 의 실체.** `SKIPPED_TIME_NOT_EVALUATED` 가 보장하는 것은 **소비하지 않는 것**뿐이고,
「다음 패스가 다시 본다」는 **인입의 성질**이다. `poll` 이 `after_as_of_ms` 의 순수 함수인 인입
(`ObservationIntake` 의 계약이고 `JsonLinesObservationJournal` 이 그렇다)에서만 성립한다.
`KisQuoteObservationIntake` 는 그 인자를 `del` 하고 내용 digest 로 dedup 하며 그 digest 를
**반환 전에** 커밋하므로, 평가 실패로 소비되지 않은 시세는 **가격이 바뀔 때까지** 사라진다 —
다음 패스는 `SKIPPED_NO_OBSERVATION` 을 본다. 순서 변경 이전에는 평가 실패가 패스 전체(poll 포함)를
건너뛰었으므로 도달할 수 없던 상태다. 문구를 `marketfeed/ports.py` ·`marketfeed/scheduler.py`
(모듈 + `tick_once`) · `marketfeed/time_pacer.py` 네 곳에서 한정하고, 실 어댑터 + 가짜 KIS 서버로
`test_an_unconsumed_quote_is_dropped_by_this_intake_not_re_read_next_pass` 를 추가했다(같은 마크로
두 번째 poll → `()`, GET 은 실제로 나갔음을 요청 수로 확인, 가격 변경 뒤 세 번째 poll 은 부활).
#810 이 앵커를 고치면 이 테스트는 **뒤집힌다**.

**LOW-1 의 실체.** 회귀 테스트가 판정하는 `source_age` 는 `RuntimeTimeProjection` 이 resolve 시점에
**자기 `wall_clock_now()`** 로 계산한다 — 그 지점은 어떤 순서에서도 훅 뒤다. 패스 자신의 `now_ms`
(스냅샷 발행 + 다음 틱 간격)는 **별개의 판독**이고 호출 밖으로 남는 유일한 사본이
`_last_tick_wall_clock_ms` 다. 실측: `now_ms`/`session_context` 를 poll 위로 올려도 그 테스트는
FRESH 로 green 이었다. 새 행동 테스트는 세션 개장을 패스 시작 판독 +1 ms 에 두고(§5 의 08:45 경계),
실 `SessionFactsOwner` 와 같은 모양(현재 판독으로 답하는 더블, `calendar/owner.py:269-277`)으로
TICKED 를 주장한다.

| 뮤테이션 (`now_ms` + `session_context` 를 poll 위로 · 훅은 뒤에 유지) | red |
|---|---|
| `test_an_observation_appended_since_the_last_evaluation_reads_fresh_not_conflicted` | `_last_tick_wall_clock_ms` 가 평가 **전** 판독(`+500` 없음) |
| `test_a_session_that_opens_during_the_pass_is_seen_by_that_pass_not_the_next` | `SKIPPED_SESSION_CLOSED` · 이벤트 0 |
| `test_tick_once_reports_time_not_evaluated_after_polling_and_consumes_nothing` | 기존 순서 테스트 |

적용 → red 확인 → **원복**했다.

**LOW-3 근거 — #810 으로 넘긴 이유.** 지적 자체는 맞다. `wall_clock_now()` 는 `HealthState`
가 `TRUSTED` 가 아니면 `None` 이고(`time/service.py:697-711`), `KisQuoteObservationIntake.poll` 은
그때 `KisQuoteWallClockUntrusted` 를 **던진다**. 순서 변경 전에는 `run_forever` 가 `before_pass()`
False 에서 `tick_once()` 자체를 부르지 않았으므로 그 raise 에 닿지 않았고, 지금은 poll 이 먼저라 닿는다.
그럼에도 이 PR 에서 코드를 바꾸지 않는다:

1. 그 raise 는 어댑터가 **의도적으로 정한 거부**다(시간을 꾸며내거나 「새 게 없다」로 위장하지
   않는다 — 모듈 독스트링). 이 PR 이 만든 것이 아니라 도달 경로가 생긴 것이다.
2. paper 는 `intake_kind: journal` 로 `_VALUE_PINS` 에 핀돼 있고 `JsonLinesObservationJournal.poll`
   은 시계를 아예 읽지 않는다 — 배포된 경로에는 이 raise 가 없다.
3. 올바른 수정은 poll 안에서 `wall_clock_now()` 에 의존하는 것을 없애는 것이고, 그것이 정확히
   #810 의 receipt-anchored 재설계다(§2.4). 여기서 `try/except` 를 두르면 **#810 이 지울 코드**를
   더하는 것이고, 미신뢰 상태를 조용히 삼키는 쪽으로 기울 위험이 있다.

→ #810 에 노트로 남기고, 이 PR 에서는 회귀로 취급하지 않는다.

**디제스트.** 이 라운드가 런타임 `*.py`(`marketfeed/{ports,scheduler,time_pacer}.py` ·
`compose/_marketfeed_wiring.py` · `transport/kis_quote/adapter.py` 독스트링)를 건드리므로
`expected_code_digest` 를 다시 도출했다(§7.5 의 10차에 이은 **11차**).

```text
DIGEST_PLACEHOLDER
```
