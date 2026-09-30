# paper 틱 폴링 주기를 신선도 예산 안으로 — 계획 (#807 선택지 1)

- 작성: 2026-09-27 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `f6348b19`(#806 머지 직후)
- 요청: 운영자 2026-09-27 「1번으로 가자, 폴링 주기 줄이는 계획 써줘」 — 이슈 #807 선택지 1.
- 성격: 계획 + 구현(같은 PR). 운영자 처분 §6.1.

## 0. 요약

1. **결함**: `journal` 인입에서 관측이 읽히는 나이의 최악값은 `수집기 지연 + poll_interval_ms + 패스 소요`인데,
   예산은 `MAX_time_conservative_freshness_age_ms − Σ지연 한도 = 1000 − 200 = 800 ms`다. 지금 paper 는
   `poll_interval_ms: 1000` 이라 **패스 직후 도착한 관측은 항상 STALE** 이고, 거부된 관측은 소비 처리되어
   재시도되지 않는다. 리허설 18 건 중 7 건(39 %) 거부(#807).
2. **고치는 것**: paper `poll_interval_ms` 를 **1000 → 400**(권고)으로 줄이고, 이 결합이 다시 조용히 어긋나지
   않게 **`journal` 인입 한정 부팅 거부 가드**를 넣는다 — `poll_interval_ms + journal_pass_allowance_ms` 가 예산을
   넘으면 부팅하지 않는다. 승인값(`time.yaml`)은 건드리지 않는다.
3. **`kis_quote` 는 범위 밖이며 가드도 적용하지 않는다.** 그 어댑터는 `as_of_ms` 를 패스의 신선한 시각 판독값으로
   찍으므로(`transport/kis_quote/adapter.py:43-65, 381`) 위상 문제가 없고, 같은 키가 HTTP 요청 속도를 정하는데 모의
   시세 한도는 **1.0 rps clean · 2.0 rps 스로틀**(P-13, `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:1840-1846`)이라
   800 ms 미만으로 줄이면 스로틀된다.

## 1. 실측 (main `f6348b19`, 호스트 로컬 · 2026-09-27)

| 무엇 | 값 | 출처 |
|---|---|---|
| 신선도 판정 | `source_age + Σdelay_bounds > max_age_bound` → STALE (같으면 FRESH) | `tos/src/tos/time/predicates.py:375` `freshness_verdict` |
| `source_age` | 패스 앞 평가의 `wall_clock_now()` − `as_of` | `marketfeed/time_projection.py:220-238` |
| Σ지연 한도 | 4 키 × 50 = 200 (`_DELAY_BOUND_FIELDS`) | `time_projection.py:109-114` · `config/tos_runtime/paper/time.yaml:22-27` |
| `max_age_bound` | 1000 (VER-002 L1078 · APPROVED 2026-09-04) | `time.yaml:32` |
| 루프 | 패스 → `sleep(poll_interval_ms)` — 주기는 `poll + 패스 소요` | `marketfeed/scheduler.py:418-420` |
| `poll_interval_ms` 의 두 역할 | 루프 sleep(`:420`) + 최소 틱 간격(`SKIPPED_INTERVAL`, `:176`) — `kis_quote` 에게는 HTTP 요청 간격(`transport/kis_quote/config.py:41-51`) | — |
| 패스 소요(40 패스) | `evaluate()` p50 7.8 / max 12.3 ms · `tick_once` TICKED p50 27.0 / max 66.3 ms · 유휴 p50 1.0 / max 1.4 ms | 런북 §5 ④ 진단 + 실 `sleep` |
| 위상 효과 | 추가 0.1 s 후 틱 → 4/4 admitted · 1.2 s 후 틱 → 5/5 STALE | 같은 진단 |
| 90 s `run_forever`, 5 s 마다 관측(`as_of = now − 200`) | 18 소비 · **STALE 7** · NoAction 5 · Proposal 6(전부 `STAGE_DENIED` — venue `max_quantity` null, 의도된 fail-closed) | 같은 진단 |
| 렌더 부팅 증명 관측 | `_JOURNAL_AGE_MS = 1000`(`scripts/tos/render_paper_config.py:160-163`) — 렌더 순간부터 이미 1000 + 200 > 1000 | — |

## 2. 결정

### 2.1 예산식 (journal 인입)

```text
수집기 지연 + poll_interval_ms + 패스 소요  ≤  max_age_bound − Σdelay_bounds   (= 800)
```

런타임이 아는 것은 `poll_interval_ms` 와 (측정된) 패스 소요뿐이다. 그래서 가드는 **런타임 몫**만 강제하고, 남는 폭을
**수집기 여유**로 명시한다:

```text
수집기 여유 = 800 − poll_interval_ms − journal_pass_allowance_ms
```

### 2.2 값 (§6 운영자 확인 1·2)

| 안 | `poll_interval_ms` | 수집기 여유 (allowance 100) | 장중 `TIME_HEALTH_SNAPSHOT` | 비고 |
|---|---|---|---|---|
| 현행 | 1000 | **−300** (가드가 거부) | ≈ 25 k 행 ≈ 45 MB/일 | 결함 |
| **(가) 400 — 권고** | 400 | 300 | ≈ 61 k 행 ≈ **110 MB/일** | 리허설 드라이버(지연 200)를 여유 있게 수용 |
| (나) 250 | 250 | 450 | ≈ 97 k 행 ≈ 175 MB/일 | 여유 크지만 증거 1.6 배 |
| (다) 700 | 700 | 0 | ≈ 36 k 행 ≈ 64 MB/일 | 수집기 지연이 1 ms 만 있어도 STALE — 기각 |

행 수 = 장중 7 h(08:45–15:45) × 1000 / (poll + 유휴 패스 ≈ 10 ms), 행당 ≈ 1.8 KB(#806 계획 §1).

`journal_pass_allowance_ms: 100` — 측정 최악 패스(12.3 + 66.3 = 78.6 ms) 위의 올림. **새 필수 키**(`journal` 일 때만),
예시 파일 `null`(부팅 거부) · paper `100` · `_VALUE_PINS` 고정.

### 2.3 가드

- 위치: `compose/_marketfeed_wiring.py::build_tick_scheduler` — `MarketFeedConfig` 와 `TrustworthyTimeConfig` 를
  **둘 다** 받는 유일한 지점(`:481-486`). 크기 예산(100 줄)을 지키려고 헬퍼 하나로 분리.
- **같은 설정값을 읽는다**: Σ지연은 `time_projection._DELAY_BOUND_FIELDS` 튜플을 그대로 순회한다 — 두 번째 사본을
  만들지 않는다(CLAUDE.md Redis TTL 규칙과 같은 원칙: 신선도 판정과 그 가드가 다른 수치를 읽으면 안 된다).
- 조건: `intake_kind == "journal"` 이고 `poll_interval_ms + journal_pass_allowance_ms > max_age − Σdelay` →
  `MarketFeedConfigError`(세 항과 수집기 여유를 메시지에 적는다).
- **이 가드가 실패하는 구체적 입력**(memory 「가드가 자기가 막는다고 말한 것을 허용한다」 대응):
  - 현 paper: 1000 + 100 = 1100 > 800 → **거부**.
  - 경계: 700 + 100 = 800 → 허용(판정식이 `>` 이므로 같음은 FRESH) · 701 + 100 → 거부.
  - 지연 키 하나를 50 → 150 으로 바꾸면 예산 700 → 400 + 100 은 허용, 650 + 100 은 거부 — Σ 에 네 항이 **모두**
    들어가는지 이것으로 핀.
  - `journal_pass_allowance_ms` 누락 · `null` · `"TBD"` · 0 이하 → 거부.
  - `kis_quote` + 1000 → **허용**(가드 비적용 — §0-3).

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| allowance 없이 `poll ≤ 800` 만 검사 | 800 을 허용하지만 800 에서도 패스 소요만큼 STALE 이 남는다 — 가드가 막는다고 말한 것을 허용 |
| 고정 주기 루프(`sleep(max(0, poll − 패스))`) | `run_forever` 계약·스케줄러 테스트 변경, 패스 초과 시 여전히 allowance 필요 — 이득 수십 ms |
| 저널 파일 변경 감시(이벤트 구동) | #807 선택지 3 — 설계 변경, 이번 범위 아님 |
| 신선도 한도 상향 | VER-002 승인값 — 별도 승인 경로(#807 선택지 4) |
| `kis_quote` 에도 가드 적용 | `as_of` 가 패스 판독값이라 위상 문제가 없고, 800 미만 강제 시 모의 시세 한도(1–2 rps) 초과 |
| 렌더 부팅 증명 관측을 신선하게 | 렌더와 부팅 사이 수 초가 이미 예산 초과 — 고칠 수 없다. 첫 관측은 **TICKED 증명**이지 결정 증명이 아니라고 런북에 적는다 |
| 장중 평가 빈도를 폴링과 분리 | `source_age` 기준점이 마지막 평가라 평가 주기도 예산 안이어야 한다 — 증거는 줄지 않고 복잡도만 는다(#807 선택지 2) |

## 4. 작업

| # | 내용 | 종료 조건 |
|---|---|---|
| T-1 | 가드 헬퍼 + `journal_pass_allowance_ms` 로더(journal 필수 · named-TBD 거부) | §2.3 입력 전부 테스트 · 뮤테이션 red: 가드 제거 / `>`→`>=` / Σ 에서 항 하나 누락 / `kis_quote` 에 적용 |
| T-2 | paper `marketfeed.yaml` `poll_interval_ms` 400 · `journal_pass_allowance_ms` 100 (주석에 이 계획 인용) · 예시 `null` · `_VALUE_PINS` | 현행 값(1000)이면 부팅 거부되는 것을 테스트로 확인 |
| T-3 | 리허설 재측정 — 같은 진단 + 실 `run_forever` 90 s + 5 s 관측(지연 200) | STALE **0** / N, 평가 행 수 ≈ 패스 수 |
| T-4 | 런북 §4·§5 ④(첫 관측은 항상 STALE — TICKED 증명), `expected_code_digest` 재도출(runtime 소스 변경 — 머지 직전 재확인), INDEX 행, #807 링크 | 통상 게이트(방화벽·lint-imports·completion·spec·contract·citation·size budget·black/ruff/mypy) |

## 5. 위험

- **증거 2.4 배**(45 → 110 MB/일). 디스크 여유 344 GB(2026-09-27) — 수년 치지만 퍼지 계획(별도·미착수)의 입력이 된다.
- CPU: 400 ms 마다 평가 ≈ 8 ms + 유휴 틱 1 ms ≈ 2 %.
- 런타임 패스가 allowance 를 넘는 순간(GC·디스크 정지)의 관측은 STALE — fail-closed 이고 재시도는 없다. 측정은 T-3.
- **2026-09-28 장중 cron 실측은 `f6348b19`(poll 1000)로 돈다** — 수정 전 실시계 기준선이 되고, T-3 과 비교한다.
- `kis_quote` 로 전환하는 배포는 이 값(400)을 물려받으면 안 된다 — 예시 파일과 이 키의 주석에 적는다.

## 6. 운영자 확인

1. **`poll_interval_ms`**: **(가) 400 (권고)** / (나) 250 / 기타.
2. **`journal_pass_allowance_ms: 100`** 신설과 `journal` 인입 한정 부팅 거부 가드 — 동의 여부.
3. 구현은 이 브랜치에서 처분 후 진행 — 동의 여부.

### 6.1 운영자 처분 (2026-09-27)

1. **`poll_interval_ms` = (가) 400.**
2. **`journal_pass_allowance_ms: 100` 신설 + `journal` 한정 부팅 거부 가드** — 동의.
3. **구현은 이 브랜치(PR #808)에서** — 동의.

## 7. 착지 기록 (2026-09-27)

### 7.1 무엇이 들어갔나

| # | 커밋 | 내용 |
|---|---|---|
| T-1 | `010ccecd` | `compose/_marketfeed_wiring.py` — 새 키 `journal_pass_allowance_ms`(`journal` 필수·양수 · 다른 인입에서는 있으면 거부, `journal_path` 와 같은 XOR 규칙) + 헬퍼 `_load_config_within_freshness_budget`. 예시 파일 `null` · 예시 필수키 레지스트리 · 새 테스트 모듈 `test_marketfeed_pacing_budget.py`(26 케이스) |
| T-2 | `548a5bc6` | paper `poll_interval_ms` 1000 → **400** · `journal_pass_allowance_ms: 100` · `_VALUE_PINS` 2행 · 승인값 교차검사 테스트 2건 |
| T-3 | — | 리허설 재측정(§7.3) |
| T-4 | 아래 | 런북 §4·§5 ④ · 이 기록 · `expected_code_digest` 재도출 |

가드는 `build_tick_scheduler` 가 부르는 헬퍼 하나다(§2.3 대로). 그 함수는 정확히 **100 줄**이라
(`function_max_lines: 100`) 한 줄도 늘릴 수 없어서, 로드 호출을 헬퍼 호출로 **1:1 교체**하고
`store = SqliteSnapshotStore(...)` 지역변수를 호출 인자로 인라인해 docstring 증가분을 상쇄했다 —
**크기 예산 예외 등재는 하지 않았다**(`--check` 0 위반 유지).

Σ지연은 `time_projection._DELAY_BOUND_FIELDS` 를 그대로 순회한다 — 두 번째 사본 없음(§2.3).

### 7.2 뮤테이션 (§2.3 입력 전부 · 각각 원복함)

| 뮤테이션 | red 로 바뀐 테스트 |
|---|---|
| 가드 제거(`intake_kind` 분기를 무조건 return 으로) | **9건** — 1000+100 · 701+100 · 지연키 4종 × 650+100 · 메시지 · 부팅 거부 · 승인값 1000 거부 |
| `>` → `>=` | **1건** — 700+100 경계 허용(등호는 FRESH) |
| Σ 에서 항 하나 누락(`_DELAY_BOUND_FIELDS[1:]`) | **6건** — 701+100 · 지연키 4종 × 650+100 · 메시지 |
| `kis_quote` 에도 가드 적용(분기 제거 + `allowance or 0`) | **2건** — `kis_quote` 로더·부팅 비적용 테스트 |

### 7.3 실측 — 같은 진단, 수정 후 (호스트 로컬 · 2026-09-27 14:50/14:52 KST · 실주문 0 · 네트워크 없음)

`compose_paper_runtime`(세션 시계만 2026-09-28 10:00 KST 주입) + 실 `run_forever` 90 s +
5 s 마다 관측 1건(`as_of = now − 200 ms`). 렌더는 부팅 직전(`source_revision 548a5bc6`).

| | **수정 전** (main `f6348b19`, poll 1000) | **수정 후 1회차** (poll 400) | **수정 후 2회차** |
|---|---|---|---|
| 소비(`EVENT_CONSUMED`) | 18 | 18 | 19 |
| 드라이버가 추가한 관측 중 **STALE** | **7 / 18 (39 %)** | **0 / 17** | **0 / 18** |
| `DECISION_WITHHELD` | 7 (전부 STALE) | 2 (STALE 1 · CONFLICTED 1) | 1 (STALE 1) |
| 그 STALE 1건의 정체 | — | **렌더 부팅 증명 관측**(소비 #1) — §3 대로 고칠 수 없는 것 | 같음 |
| `TIME_HEALTH_SNAPSHOT` | — | 216 / 90.3 s = **2.39 /s** | 220 / 90.6 s = **2.43 /s** |
| 결정 결과 | NoAction 5 · Proposal 6 | NoAction 9 · Proposal 7 | NoAction 9 · Proposal 9 |
| `FLOW_HALTED` | — | 7 | 9 |
| data dir | — | 2.39 MB / 90 s | 2.49 MB / 90 s |

- **목표(STALE 0/N) 달성.** 남은 STALE 1건은 두 회차 모두 **첫 관측 = 렌더가 만든 부팅 증명
  관측**이다(소비 순서로 확인). 렌더와 부팅 사이 수 분이 이미 예산을 넘으므로 §3 의 「고칠 수
  없다」가 그대로다 — 런북 §5 ④ 에 적었다.
- `FLOW_HALTED` 는 전건 `STAGE_DENIED | the venue / broker quantity constraint is incomplete`
  — venue `max_quantity` 가 null 인 **의도된 fail-closed** 로, 수정 전과 같은 사유다.
- **1회차의 `CONFLICTED` 1건(소비 #17)은 새 관측이고, 이 예산의 반대편 끝이다.**
  `source_age = wall_clock_now() − as_of` 가 **음수**이고 `MAX_future_timestamp_tolerance_ms`
  (50)를 넘으면 CONFLICTED 다(`tos/src/tos/time/predicates.py` `freshness_verdict`). 즉 패스의
  시간 평가와 그 패스의 저널 판독 사이가 200 ms 넘게 벌어지면, 200 ms 전으로 찍힌 관측이
  **미래로** 보인다. 2회차에서는 재현되지 않았다(추가 관측 35건 중 1건). 이 측정 하네스는
  수집기를 **같은 프로세스의 스레드**로 돌리므로(실 배포는 별도 프로세스) 하네스 쪽 경합일
  수 있다 — 단정하지 않는다. 별도 관측 항목으로 남긴다.
- 증거량: 장중 7 h 환산 ≈ 61 k `TIME_HEALTH_SNAPSHOT` 행 — §2.2 표의 추정(≈61 k)과 일치한다.

### 7.4 `expected_code_digest` 재도출

런타임 소스(`compose/_marketfeed_wiring.py`)가 바뀌었으므로 재도출했다.

```text
48b07d22412ea4d5d0f6e7e7164f9e3c432edf5746d7851e6a024ee5c4de9d52   (이전 · #806 머지 · main f6348b19)
045ecf5aace6140aed5d1b51ccc08f35668229e0958c459a93c941e29fe4159f   (현재)
```

`print-digests` 와 `observe_source_tree_digest()` 두 경로 일치. `config/tos_runtime/paper/release.yaml`
(값 + 이력 주석)과 `test_deploy_approved_values.py::_VALUE_PINS` **두 곳 모두** 갱신.
`expected_dependency_set_digest` 는 **바꾸지 않았다** — 같은 배포 호스트 루트 `.venv` 에서 찍은
출력이 커밋된 값과 바이트 동일했다.

### 7.5 게이트

방화벽 PASS · `lint-imports` 3 contracts kept · completion GREEN(위반 0) · spec PASS ·
contract PASS + self-test PASS(뮤테이션 145종) · citation PASS(8) · named-TBD guard PASS(46 파일) ·
size budget PASS(위반 0 · 등재 39) · black/ruff 통과 · mypy 는 런타임 `src` 27건 / `tests` 116건으로
**main `f6348b19` 와 같은 수**(이 호스트 `.venv` 의 기존 baseline, 신규 0). 테스트: `tos/tests`
9601 passed · `tos/runtime/tests` **3119 passed**(신규 26 + 승인값 2 포함) · `tests/tools/test_tos_*`
+ `tests/tos_l3` + `tests/unit/scripts/test_render_paper_config.py` 838 passed(기존 로컬 실패
`test_u17_verify.py` 3건은 `yq` 미설치 — CI 는 `--ignore`).

### 7.6 리뷰 처분 (`code-reviewer`, 같은 모델 계열 — 잠정)

PR #808 · 판정 **approve** · MEDIUM 2 · LOW 3. Codex 는 이 범위(되돌리기 어려운 경로 아님)에서
제외이므로 같은 모델 계열의 Claude 쪽 폴백 레인이고, 그래서 **잠정**이다.

| # | 지적 | 처분 |
|---|---|---|
| MEDIUM-1 | 가드가 `MAX_time_conservative_freshness_age_ms` 와 Σ지연에 **설계상 민감**하다 — time.yaml 쪽 값이 바뀌면 marketfeed 쪽이 조용히 예산 밖으로 나갈 수 있고, 두 파일이 CONFLICTED 상태로 갈라질 여지 | **이슈 #809** 로 분리. 이 PR 의 가드는 부팅 시점 결합을 만들 뿐 값 변경의 조정까지는 다루지 않는다 |
| MEDIUM-2 | `kis_quote` 가 «패스 안에서 새로 읽은» 시각으로 `as_of_ms` 를 찍는다는 서술이 **거짓** | 문구 수정(`331e55ab`) + **이슈 #810** |
| LOW-1 | `journal_pass_allowance_ms` 가 강제되지 않는다는 사실이 어디에도 없음 | 독스트링·YAML 주석에 명시(`331e55ab`). 런타임 관측은 **후속 과제로 유보** |
| LOW-2 | `load_marketfeed_config` 가 예산을 검사하지 않는데 그 사실이 안 적혀 있음 | 독스트링에 명시(`331e55ab`) |
| LOW-3 | `store = SqliteSnapshotStore(...)` 를 인자로 인라인한 것이 크기 예산 때문 | **변경 없음** (아래 근거) |

**MEDIUM-2 의 실체.** `TrustworthyTimeService.wall_clock_now()`
(`tos/runtime/src/tos_runtime/time/service.py:697-711`)는 마지막 `evaluate()` 가 캐시한
스냅샷(`self._snapshot.wall_clock_observation`)을 돌려준다 — 새로 읽지 않는다. 따라서 어댑터가
찍는 `as_of_ms` 는 **스케줄러의 `now_ms` 와 같은, 패스 이전의 그 순간**이고 `source_age` 는
**항상 0** 이다. 위상 항이 적용되지 않는 이유는 «더 신선해서» 가 아니라 **공유 캐시** 때문이고,
실제 HTTP 왕복은 아예 측정되지 않는다. 가드가 `kis_quote` 를 제외하는 결론 자체는 유지되지만
**근거가 달라서** 네 곳의 문구를 «패스 이전 캐시 판독값을 그대로 쓰므로 `source_age` 는 항상 0 이고
위상 항이 적용되지 않는다» 로 고쳤다 — 모듈 독스트링 · `marketfeed.example.yaml` ·
`config/tos_runtime/paper/marketfeed.yaml` · `test_marketfeed_pacing_budget.py`.
`transport/kis_quote/adapter.py` 자체는 **손대지 않았다**: 그 독스트링의 «응답 이후에 읽는다»
주장과 그 뒤의 미측정 레이턴시는 **#810 의 수정 대상**이지 이 PR 의 것이 아니다.

**LOW-3 근거.** 인라인의 동기는 크기 예산이 맞지만, 관측 가능한 차이는 실패 경로에서만 나고 그
방향이 **개선**이다. 이전에는 `store` 가 `_build_intake` 와 `RuntimeTimeProjection` **앞에서**
생성됐으므로, 인입 구성 거부(`KisQuoteTransportConfigError`)·`MultiInstrumentRefused`·
`TimeProjectionConfigError` 로 부팅이 거부되는 경우에도 sqlite 파일은 이미 만들어진 뒤였다. 지금은
인자 평가 순서상 그 셋이 모두 성공한 뒤에야 생성되므로 **거부된 부팅이 잔여 파일을 남기지 않는다**.
성공 경로는 같은 객체·같은 인자로 완전히 동일하다. 되돌릴 이유가 없어 그대로 둔다.

**디제스트.** 이 라운드가 런타임 `*.py`(`compose/_marketfeed_wiring.py` 독스트링)를 건드리므로
`expected_code_digest` 를 다시 도출했다(§7.4 의 9차).

```text
045ecf5aace6140aed5d1b51ccc08f35668229e0958c459a93c941e29fe4159f   (8차 · 이 브랜치 e401a6d1)
06508a5d85305a23f034624b330178bff10e3d89046e5ff3c1748866ddc0eed3   (9차 · 현재)
```

`print-digests` 와 `observe_source_tree_digest()` 두 경로 일치. `release.yaml`(값 + 9차 이력
주석)과 `_VALUE_PINS` 두 곳 모두 갱신. `expected_dependency_set_digest` 는 **바꾸지 않았다**
(같은 배포 호스트 루트 `.venv` · python 3.12.12 / sqlite 3.45.1 · 출력 바이트 동일).
