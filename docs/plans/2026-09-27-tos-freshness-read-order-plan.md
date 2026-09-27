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
