# 브로커 프로브 일시 오류 정책 — P-CA 2차 관측 실패의 원인과 수정 (2026-09-30)

- 성격: 계획 + 구현(같은 PR). 대상은 `tools/broker_probes/`(레거시 도구, tos 범위 밖).
- 배경 아티팩트: `docs/broker-profiles/evidence/2026-09-11-p02-t3-campaign/` 의
  `P-CA-20260930T015946Z.json` · `P-CA-20260930T022735Z.json` · `P-CA-20260930T034727Z.json`,
  러너 로그 `~/.config/kis-probes/p-ca-20260930.log`(README 09-30 블록에 전사).

## 0. 요약

2026-09-30 SK하이닉스 000660 현금배당(지급일 당일) 관측은 **네 번 시도해 네 번 중단**됐고
현금 leg 은 관측되지 않았다. 네 번 중 브로커가 한 말은 두 종류뿐이다 — 전송 timeout 2회
(`ReadTimeout … read timeout=20.0`), 원장 스로틀 1회(`EGW00215` "원장에서 허용 가능한 초당
거래건수를 초과"). 나머지 1회는 러너의 가드 결함(공유 체크아웃 dirty). 프로브 하네스는
이 셋을 전부 「즉시 중단, 재시도 없음」으로 다뤘다. 그 규칙은 2026-09-17 의 **우리 쪽 pacing
결함**(EGW00201 을 우리가 유발)을 겨냥한 것이었고, 오늘의 오류는 전부 **우리 호출률과 무관**
했다(같은 계좌를 쓰는 동거 프로세스 없음 — README 09-30 블록 「제거 논증」).

수정은 두 층이다.

1. **하네스(`probes_ca.py`)** — 일시 오류 두 종류(전송 예외 · `EGW00215`)에 한해 **한 폴링
   간격을 통째로 기다린 뒤 한 번만 재시도**하고, 연속 2회면 지금처럼 중단한다. 재시도는 전부
   아티팩트에 남긴다(관측 `poll_retry_evidence`, 측정 `retries`). `EGW00201`/HTTP 429 의
   「재시도 없이 중단」 규칙은 **그대로 둔다**(§3).
2. **러너** — 저장소에 추적되는 템플릿 `tools/broker_probes/runners/run_p_ca.sh` 를 두고
   (a) 자기 위치의 체크아웃을 검사한다(공유 체크아웃이 아니라 **분리 워크트리**, `HEAD` 가
   `origin/main` 의 조상이어야 함 — [#793 규칙]), (b) 보유 수량 조회의 **실패와 0 을 분리**해
   기록하며, (c) 자기 삭제를 하지 않는다(crontab 엔트리만 제거). 운영자별 값(종목·지급시각·
   지문·자격증명 파일)은 전부 env 로 받는다.

## 1. 실측 — 무엇이 창을 죽였나

| 시도 | 시작(KST) | 종료 사유 | 폴링 | 하네스 판정 |
|---|---|---|---|---|
| 1 (cron) | 00:20:01 | `ABORT: worktree dirty` — 메인 체크아웃의 untracked 백업 파일 | 0 (GET 없음) | 러너 가드 |
| 1b | 10:58:04 | `held qty=0` — 실제로는 잔고 조회 실패(32 s, 원문 없음). 11:00 직접 GET 은 20행·qty 1 | 0 | 러너가 실패와 0 을 합침 |
| 2 | 10:59:46 | 폴링 #14 `EGW00215` HTTP 500 | 13 완료 | `ABORTED(rejected)` |
| 3 | 11:27:35 | 폴링 #8 `ReadTimeout` 20 s | 7 완료 | 예외 → `run.py` rc 5 |
| 4 | 12:47:27 | 첫 조회에서 `ReadTimeout` | 0 | 예외 → rc 5 |

관측된 사실은 11:00–11:31 KST 20폴링 동안 `dnca_tot_amt` 6,686,725 불변(hldg 1)뿐이다.
`is_rate_limited` 는 HTTP 429 와 `EGW00201` 만 본다(`common.py:416`) — `EGW00215` 는
일반 거부(`_BAL_REJECTED`)로 떨어져 중단됐고, 전송 예외는 `_read_balance` 밖으로 새어
`run.py` 의 포괄 `except` 가 아티팩트를 쓰고 rc 5 로 끝냈다.

## 2. 수정

### 2.1 하네스 — 일시 오류 분류와 1회 재시도

- 새 분류 `_BAL_TRANSIENT`: (a) `_get` 이 던지는 전송 예외(`requests`/`aiohttp` 의 timeout ·
  connection error — `_get` 의 실제 예외 타입을 확인해 그 집합만), (b) 응답 본문의 `EGW00215`.
- `_poll_loop`: `_BAL_TRANSIENT` 이면 `poll_retry_evidence`(poll_index · 종류 · 원문 발췌 —
  기존 `_call_evidence` 형식, payload 게이트 동일)를 관측에 남기고 **`poll_pacer` 로 한 폴링
  간격을 기다린 뒤** 같은 폴링을 한 번 더 한다. 두 번째도 일시 오류면 `stop_reason` 을
  `_STOP_TRANSIENT`(전송) / `_STOP_RATE_LIMITED`(`EGW00215`) 로 지금처럼 중단한다.
  재시도 뒤 정상이면 `polls_used` 는 시도 수대로 늘고 `polls_completed` 는 1 만 는다.
- 기준선(`_do_baseline`) · 참조조회(`_do_reference_check`)에도 같은 1회 재시도를 적용한다
  (시도 4 는 첫 조회에서 죽었다).
- 측정에 `retries: {transport: n, ledger_throttle: n}` 를 추가한다. 재시도가 0 이 아닌 실행의
  CENSORED/OBSERVED 라벨은 그대로 두되 `retries` 가 붙어 있으므로 판독자가 구분할 수 있다.
- 새 상수는 만들지 않는다 — 대기 길이는 이미 있는 `effective_poll_ms`(폴링 간격)다.

### 2.2 러너 템플릿 (`tools/broker_probes/runners/run_p_ca.sh`, 추적됨)

- `REPO` 는 `$(git -C "$(dirname "$0")" rev-parse --show-toplevel)`. 가드:
  `git status --short` 비어 있음 · `git rev-parse --abbrev-ref HEAD` 가 `HEAD`(분리) ·
  `git merge-base --is-ancestor HEAD origin/main`. 실패 시 어느 검사가 왜 막았는지 로그.
- 보유 수량 조회는 `HELD=<n>` 만 파싱하고, 파싱 실패는 `ABORT: balance query failed: <마지막
  stderr 한 줄>` 로 따로 적는다.
- 자격증명 파일 · 기대 지문 · 종목 · 지급시각 · 창 · 폴링 · 페이스는 env 필수값(기본값 없음).
  기존 `run-p-ca-20260930.sh` 의 키 지문 · 계좌 지문 · `pacer.derive(` 존재 가드는 유지.
- 끝나면 아티팩트를 `PCA_EVIDENCE_DIR` 로 복사하고, `PCA_CRON_MARK` 가 있으면 그 엔트리만
  crontab 에서 지운다. 자기 삭제 없음.

### 2.3 테스트 (`tests/tools/test_broker_probes_ca.py` 확장)

- 가짜 세션으로: 전송 예외 1회 → 재시도 → 정상(`retries.transport == 1`, `polls_completed`
  정확) · 전송 예외 2연속 → `_STOP_TRANSIENT` · `EGW00215` 1회 → 재시도 · 2연속 →
  `_STOP_RATE_LIMITED` · `EGW00201`/429 → **여전히 재시도 없이 즉시 중단**(회귀 방지).
- 재시도 사이 대기가 `effective_poll_ms` 와 같음을 pacer 호출로 확인.
- 새 테스트는 수정 전 코드에서 red 여야 한다(가드 규율).
- 러너 템플릿: `bash -n` + shellcheck(있으면) + 분리 워크트리가 아닐 때 ABORT 하는 것을 임시
  git 저장소로 확인하는 테스트 1건.

## 3. 기각한 대안

- **`EGW00201`/429 도 재시도** — 2026-09-17 의 원인은 우리 pacing 이었고 그 규칙은 계좌 보호
  장치다. 오늘 근거는 `EGW00215` 와 전송 예외뿐이므로 근거 없는 범위 확장은 하지 않는다.
- **지수 백오프·N회 재시도** — 새 상수가 생기고 증거의 「언제 몇 번」 이 흐려진다. 한 폴링
  간격 1회면 오늘의 세 중단은 전부 통과했을 것이다(각각 단발).
- **러너를 `~/.config` 에만 두기** — 오늘 러너가 자기 삭제돼 3·4차는 사본으로 돌렸고, 리뷰가
  「어떤 스크립트였는지 복구 불가」를 지적했다. 템플릿은 추적하고 인스턴스 값만 env 로.

## 4. 범위 밖

- P-8 러너의 「전송 오류 → STOP」 전이(README 09-30 블록, 리뷰 F4): P-8 재개 전 같은 분류를
  `probes_order.py` 공존 폴링에 적용해야 하나 이 PR 은 P-CA 경로만 고친다. P-8 3~5회차 재개
  조건으로 남긴다.
- `EGW00215` 의 원인 규명(모의 서버 공용 스로틀 가설) — 관측만 남기고 단정하지 않는다.

## 5. 위험

- 재시도가 「관측 없음」 창을 30 s 늘린다 — CENSORED 판정의 시간 오차 ≤ 1 폴링 간격. 아티팩트에
  `retries` 가 있으니 판독자가 보정할 수 있다.
- 템플릿 가드가 너무 엄격하면(분리 워크트리 강제) 운영자가 급히 돌릴 때 막힌다 — 의도된
  것이고, 우회는 env `PCA_ALLOW_SHARED_CHECKOUT=1` 로만, 로그에 남긴다.

## 6. 운영자 확인

- 2026-09-30 사용자 지시 「관측 실패 사유 확인하고 수정 진행」 → 계획대로 진행한다.
- 남은 처분: 3차 관측 대상(058610 에스피지, 지급일 2026-10-22 로 README 표에 기재 — 재확인 필요)
  을 이 템플릿으로 예약할지.

## 7. 착지 기록

### 7.1 바뀐 파일

| 파일 | 무엇 |
|---|---|
| `tools/broker_probes/probes_ca.py` | `_BAL_TRANSIENT` 분류 · 단일 분류기 `_get_classified` · 단일 재시도 `_retry_once` · `_Pacer.defer` · `_Outcome` · `_Retries` · `_STOP_TRANSIENT` · `_StopRun` · 전처리 진입점 `check_holding` |
| `tools/broker_probes/runners/run_p_ca.sh` | 추적되는 러너 템플릿(신규) |
| `tools/broker_probes/runners/README.md` | 분리 워크트리에서 인스턴스화하는 법(신규) |
| `tests/tools/test_broker_probes_ca.py` | 새 테스트 44건 — 라운드 1 25건(§7.3) + 리뷰 처분 19건(§7.6) |

라운드 1 의 `_read_balance_retrying` / `_ksdinfo_get_retrying` 두 벌은 리뷰 F4·F5 처분으로
`_get_classified` + `_retry_once` 한 벌로 합쳐졌다(§7.6).

### 7.2 구현이 계획과 다른 점

- **분류를 한 상수가 아니라 두 상태 문자열로 넣었다.** `_BAL_TRANSIENT` 는 접두사로 남기고
  `_read_balance` 는 `TRANSIENT:transport` / `TRANSIENT:ledger_throttle` 을 돌려준다. 이유는
  기존 6-튜플의 arity 를 그대로 두기 위해서다 — 7번째 원소를 붙이면 기존 호출부와 기존
  테스트가 전부 손을 타고, 「`EGW00201`/429 는 바이트 단위로 그대로」라는 이 PR 의 회귀
  조건을 검사할 기준 자체가 흔들린다.
- **대기는 `_Pacer.defer(effective_poll_ms)`** 로 넣었다. `wait()` 만으로는 부족하다:
  실패한 시도가 **나가기 전에** 이미 간격을 예약해 두므로, 20 s read timeout 이 끝난 시점에
  pacer 가 남겨둔 빚은 30 s 간격 중 10 s 뿐이다(09-30 3차의 실제 모양). `defer` 는 지금
  시점에서 한 간격을 다시 잰다. 새 상수는 0 — 길이는 `effective_poll_ms` 이고, 잠은
  여전히 `wait()` 한 곳에서만 잔다. 기준선·참조조회도 같은 길이를 쓴다(세 단계가 같은
  「한 폴링 간격」이어야 판독자가 보정할 수 있다).
- **전송 예외 발췌에서 query string 을 지운다.** `requests` 의 `ConnectionError` 는 실패한
  URL 을 통째로 렌더링하고 그 URL 에는 `CANO`(계좌번호)가 들어 있다. `redact()` 는 필드
  **이름**으로 동작해 raw 문자열 안으로 못 들어가고, 발췌 상한은 길이만 자른다 — 그대로
  두면 커밋되는 증거 말뭉치에 계좌번호가 들어간다. 계획에 없던 조치이고, 테스트
  `test_a_transport_excerpt_never_carries_the_request_query_string` 가 지킨다.
- **참조조회의 2연속 일시 오류는 런을 멈춘다.** 계획은 「지금처럼 중단」이라고만 했는데
  참조조회의 「지금」은 전송 예외가 프로브 밖으로 새어 `run.py` rc 5 로 끝나는 것이었다.
  `_StopRun` 으로 정중히 멈춰 아티팩트를 남긴다.
- **러너 템플릿에 계획에 없던 것 둘.** (a) `PCA_EVENT_CLASS` 가 `cash_dividend` 가 아니면
  `PCA_EFFECTIVE` 를 요구한다 — 없으면 수량 leg 이 조용히 추적되지 않는다. (b) 실행 전
  results 디렉터리의 최신 아티팩트를 기억해 두고, 실행 뒤에도 그것이 최신이면 **복사하지
  않는다** — `ls -t | head -1` 은 프로브가 아무것도 안 썼을 때 남의 시행을 증거로 복사한다.

### 7.3 테스트와 수정 전 red 증명

새 테스트 25건(+ shellcheck 미설치 시 skip 1건). 전부 **수정 전 코드에서 red** 임을 실측했다
— `probes_ca.py` 를 `origin/main` 판으로 되돌리고 러너 템플릿을 치운 뒤 한 번 돌린 결과:

| 테스트 | 수정 전 실패 |
|---|---|
| 전송 timeout 1회 → 재시도 → OBSERVED | `requests.exceptions.ReadTimeout` 이 프로브 밖으로 탈출 |
| 전송 timeout 2연속 → `_STOP_TRANSIENT` | 같음(탈출) |
| 기준선 전송 timeout 1회/2연속 | 같음(탈출) |
| 참조조회 전송 timeout 1회/2연속 | 같음(탈출) |
| 재시도 대기 = 한 폴링 간격 | 같음(탈출) |
| query string 미기록 | 같음(탈출, 그리고 계좌번호가 메시지에 있다) |
| `EGW00215` 1회 → 재시도 | `assert ["poll #1 rejected: … msg_cd='EGW00215'"] == []` |
| `EGW00215` 2연속 → `_STOP_RATE_LIMITED` | `assert 'rejected' == 'rate_limited'` |
| 「재시도 0」도 명시한다 | `KeyError: 'retries'` |
| 일시 집합은 timeout·connection 뿐 | `AttributeError: … no attribute '_transport_transient_types'` |
| `defer` 는 지금부터 재고 줄이지 않는다 | `AttributeError: '_Pacer' object has no attribute 'defer'` |
| 러너 템플릿 10건 | 파일 부재(`FileNotFoundError` / `No such file or directory`) |

**정직하게 적어둘 것 하나**: `EGW00201`/429 회귀 핀 2건도 수정 전에 red 지만, 사유는
`KeyError: 'retries'` 다 — 즉 「재시도하지 않는다」는 **행동** 자체는 수정 전에도 옳았다.
이 두 건은 결함을 잡는 테스트가 아니라 **바뀌지 말아야 할 것을 고정하는 핀**이고, 그것이
이 핀의 용도다(정책이 넓어지면 `len(session.calls) == 2` 와 `_retry_records(run) == []` 가
먼저 깨진다).

러너 가드는 **양방향**으로 확인한다: dirty · 비분리 · `origin/main` 비조상 · 수정 누락이
각각 ABORT 하고(그리고 **자격증명 파일을 source 하기 전에** 그렇게 한다 — 센티널 문자열로
확인), clean·분리·조상 체크아웃은 세 가드를 **통과**해 다음 게이트에서 멈춘다.

### 7.4 게이트

```
.venv/bin/pytest tests/tools/test_broker_probes_ca.py \
  tests/tools/test_broker_probes_pacing.py \
  tests/tools/test_broker_probes_balance.py -q -p no:cacheprovider
  → 156 passed, 1 skipped (shellcheck 미설치)

ruff check tools/broker_probes tests/tools     → All checks passed!
black --check (변경 파일 2건)                   → 2 files would be left unchanged
```

`mypy tools/broker_probes` 는 **CI 게이트가 아니다** — `.github/workflows/test.yml` 의
`type-check` 잡은 `mypy shared/` 만 돌리고 그나마 `continue-on-error: true` 다. 참고로
`probes_ca.py` 단독 검사는 수정 전후 모두 무오류였다(`tools/` 에 `__init__.py` 가 없어
디렉터리 단위 실행은 수정과 무관하게 모듈 경로 충돌로 실패한다).

### 7.5 남은 것

- §4 그대로: P-8 공존 폴링(`probes_order.py`)의 「전송 오류 → STOP」 전이는 이 PR 범위 밖.
  P-8 3~5회차 재개 조건으로 남는다.
- `EGW00215` 의 원인(모의 서버 공용 스로틀 가설)은 여전히 관측만 있고 단정하지 않는다.
- 3차 관측 대상(058610 에스피지, 지급일 재확인 필요)을 이 템플릿으로 예약할지는 운영자 결정.

### 7.6 리뷰 처분 (PR #825 라운드 1 · 독립 리뷰 high · 6건 · 기각 0)

| # | 지적 | 처분 |
|---|---|---|
| F1 | 러너의 「실패는 0 이 아니다」 가드가 작동하지 않는다 — `KISClient.get_stock_balance()` 는 비-200 · 비-JSON · `rt_cd≠0` · 포괄 `except Exception` 전부를 `[]` 로 되돌린다 | **수정.** 게이트를 프로브 자신의 판독기로 옮겼다 |
| F2 | 같은 함수가 `CTX_AREA_*` 를 비운 채 **1페이지만** 읽는다 — 2페이지 보유는 「미보유」 | **수정.** 같은 이동으로 함께 닫힘 |
| F3 | `ChunkedEncodingError` 가 일시 집합에서 빠져 있고 「설정 결함」으로 문서화돼 있다 — 실제로는 `response.text` 가 던지는 전송 실패 | **수정.** 전제 자체를 고쳤다 |
| F4 | `_ksdinfo_get_retrying` 이 원장 스로틀을 `is_rate_limited` **앞에서** 본다 — 잔고 경로와 우선순위가 반대 | **수정.** 분류를 한 곳으로 |
| F5 | 재시도 정책이 두 벌 — 이미 F4 로 갈라졌다 | **수정.** `_retry_once` 하나 |
| F6 | `--effective-time $PCA_EFFECTIVE` 무인용 전개 — 공백 구분 ISO 가 argv 두 개로 쪼개진다 | **수정.** bash 배열 |

**F1·F2 — 게이트를 프로브의 판독기로.** 확인부터: `shared/kis/client.py:910-1029` 를 읽어
지적을 실측했다 — 실패 경로 네 갈래가 전부 `return []` 이고(`status != 200` · `data is None` ·
`rt_cd != '0'` · `except Exception`), `CTX_AREA_FK100/NK100` 은 빈 문자열 고정에 연속조회
루프가 없다. **즉 러너는 자신이 고쳤다고 주장한 바로 그 결함 위에 세워져 있었다.**
새 진입점 `probes_ca.check_holding`
(`python -m tools.broker_probes.probes_ca --check-holding`)은 `_read_balance` 를 쓰므로
페이지를 걷고 분류하며, 두 줄 중 하나만 찍는다 — `HELD=<n>`(종료 0) 또는
`HOLDING_QUERY_FAILED=<종류>:<상세>`(종료 비-0). 러너는 그 두 형태만 파싱하고, 숫자를
찍었더라도 종료코드가 0 이 아니면 그 숫자를 **믿지 않는다**. 일시 오류에는 프로브와 같은
1회 재시도가 붙는다(전처리 한 번의 timeout 이 시행 창 전체를 먹지 않도록).

**F3 — 전제 정정.** `_get` 은 두 곳에서 던진다: `session.request`(timeout · connection)와
**본문 읽기** `response.text`(`ChunkedEncodingError` · `ContentDecodingError`). 둘 다
「완전한 응답이 오지 않았다」이고 read timeout 이 몇 바이트 늦게 온 것과 같은 실패다.
리뷰가 지목한 `ChunkedEncodingError` 에 더해 `ContentDecodingError` 도 넣었다 — 같은
경로·같은 성질이고, 하나만 넣으면 다음 리뷰가 나머지를 지적한다. `TooManyRedirects` ·
`InvalidURL` · `MissingSchema` · `URLRequired` 는 여전히 제외(우리 결함이고, 재시도해 봐야
같은 실패가 두 번 날 뿐이다).

**F4·F5 — 분류 한 곳, 재시도 한 곳.** `_get_classified` 가 유일한 우선순위 소유자다:
①응답 없음 ⇒ 일시 · ②`is_rate_limited`(429·`EGW00201`) ⇒ **중단, 재시도 없음** ·
③`EGW00215` ⇒ 일시. ②가 ③보다 앞인 것이 핵심이다 — 한 응답이 두 신호를 다 담을 수 있고
계좌 보호 규칙이 이겨야 한다. 재시도는 `_retry_once` 하나이고 `on_transient` 콜백으로
단계가 기록처를 정한다(프로브는 관측+계수, 전처리는 stderr 한 줄). `_read_balance` 의
6-튜플 시그니처와 기존 테스트는 그대로다.

**추가 red 증명 (라운드 2).** 새 테스트 19건 전부 **리뷰 시점 HEAD(`fb3e77fa`)에서 red**:
`AttributeError: … no attribute 'check_holding'`(보유 게이트 8건) ·
`AttributeError: … no attribute '_get_classified'` · `AssertionError:
<class 'requests.exceptions.ChunkedEncodingError'>` · 러너 6건은 옛 러너가 다른 문장으로
ABORT 한다. **단서 하나**: 러너 end-to-end 테스트는 가짜 `python` 을 쓰므로 옛 러너에서의
red 는 F1 의 **재현**이 아니라 옛 문장과의 불일치다. F1·F2 자체는 위처럼
`shared/kis/client.py` 를 직접 읽어 확인했다.

### 7.7 라운드 2 게이트

```
.venv/bin/pytest (같은 3파일) -q -p no:cacheprovider
  → 174 passed, 1 skipped (shellcheck 미설치)
ruff check tools/broker_probes tests/tools → All checks passed!
black --check (변경 파일 2건)               → 2 files would be left unchanged
bash -n tools/broker_probes/runners/run_p_ca.sh → OK
```
