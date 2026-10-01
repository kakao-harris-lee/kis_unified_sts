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
- ~~참조조회(`--reference-check`)가 기록만 하고 `divi_pay_dt` 를 t0 와 대조하지 않는 것, 그리고
  ksdinfo 질의 창이 실행 시각에만 고정된 것~~ → **#830 으로 착지(§7.14)**. 이 PR 범위 밖이었다.

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
| `tests/tools/test_broker_probes_ca.py` | 새 테스트 55건 — 라운드 1 25건(§7.3) + 라운드 2 처분 19건(§7.6) + 라운드 3 처분 11건(§7.8), 강화 8건 |

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
  P-8 3~5회차 재개 조건으로 남는다. (참조 전용 모드·지급일 대조는 §4 에서 빠져 #830 으로
  착지했다 — §7.14.)
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

### 7.8 리뷰 처분 (PR #825 라운드 2 · 9건 · 기각 0)

| # | 지적 | 처분 |
|---|---|---|
| F1 | 러너가 `$REPO/.venv/bin/python` 을 고정으로 쓰는데 새 분리 워크트리에는 `.venv` 가 없다 — README 대로 하면 **매번** ABORT. 테스트가 가짜 `.venv` 를 심어 이를 가렸다 | **수정.** `PCA_PYTHON` 필수 env + **모듈 출처 가드** |
| F2 | 보유 점검과 프로브가 별도 프로세스라 페이서가 따로 논다 — 프로브 첫 GET 이 점검 마지막 GET 에 붙는다(2026-09-17 `EGW00201` 의 그 모양) | **수정.** 사이에 `sleep "$PCA_PACE_S"` |
| F3 | `PCA_EFFECTIVE` 조건부 필수 검사가 **자격증명 소싱과 보유 조회 뒤**에 있다 | **수정.** env 검증 단계로 이동 |
| F4 | `_BAL_CAPPED` 의 `parsed` 는 마지막 **성공** 페이지라 `CAPPED:<성공 msg_cd>` 가 찍힌다 | **수정.** `page_cap:<n>`, `msg_cd` 는 `rt_cd≠0` 일 때만 |
| F5 | 폴 루프의 재시도가 창 마감을 안 본다 — 마지막 폴의 일시 오류가 창 **밖** 폴을 만든다 | **수정.** `can_retry` 로 마감 확인 |
| F6 | `check_holding` 이 `probe_pca` 의 부트스트랩을 복제했고 이미 `warn_shared_token_cache()` 가 빠져 있었다 | **수정.** `_open_broker_session` 하나 |
| F7 | 두 docstring 이 존재하지 않는 `_read_balance_retrying` 를 가리킨다 | **수정.** `_retry_once` 로 |
| F8 | 네 단계가 전부 `poll_retry_evidence` 키에 기록된다 | **수정.** `retry_evidence` + `phase` |
| F9 | 폴마다 클로저 두 개를 새로 만든다 | **수정.** 루프 밖으로 |

**F1 이 드러낸 더 큰 것.** 지적은 「README 대로 하면 못 돈다」였는데, 고치는 쪽을
확인하다 보니 `repo_commit` 과 results 디렉터리가 **둘 다 로드된 `common.py.__file__`**
을 따른다(`common.py:70,506,512`). 즉 인터프리터를 메인 체크아웃의 venv 로 바꾸면,
그 venv 의 editable 설치가 메인 체크아웃 코드를 해석할 때 러너의 clean·분리·조상 가드가
**돌지도 않은 트리를 보증**하게 된다(#793 의 정확히 반대 방향). 그래서 `PCA_PYTHON` 만
받는 것으로 끝내지 않고, `PYTHONPATH=$REPO` 로 모듈을 import 해 `__file__` 이 `$REPO`
아래인지 **증명**한 뒤에야 진행한다. 이 가드가 없으면 F1 의 수정이 새 결함이 된다.

**F5 는 리뷰 서술보다 한 칸 더 나빴다.** 리뷰는 「CENSORED 판정이 창 밖 폴에 기댄다」로
적었는데, 수정 전 코드로 실측하니 창(60 s) 밖 110 s 에서 돌아온 폴이 변화를 보고
**OBSERVED 를 만들어냈다**(`assert 'OBSERVED' == 'CENSORED'`). 값이 생기는 쪽이라 더
위험하다. 처분: 창이 이미 지났으면 재시도를 거부하고 루프는 원래대로 끝난다 —
`stop_reason` 은 `None`(창은 진짜로 다 흘렀고 그것이 CENSORED 가 주장하는 것) 이며,
일시 오류 자체는 `retry_evidence`(`retried: false`)로 남는다.

**F8 과 함께 「전송량」과 「본 것」을 분리했다.** 이제 `_retry_once` 는 **모든** 일시
오류를 기록하고(재시도한 것 · 두 번째라 못 한 것 · 창이 지나 거부된 것),
`measurements.retries` 는 **실제로 쓴 재시도**만 센다. 둘을 같은 수로 세면 「이 런이
추가로 얼마나 기다렸나」라는 질문에 답할 수 없다.

**라운드 3 red 증명.** 새/강화 테스트 19건 전부 라운드-2 HEAD(`e1a8ee85`)에서 red.
특기할 것 셋: F4 는 옛 코드가 실제로 `HOLDING_QUERY_FAILED=CAPPED:MCA00000` 을 찍었고
(성공 코드를 실패 사유로), F5 는 `assert 'OBSERVED' == 'CENSORED'` 로 위의 더 나쁜
형태가 확인됐으며, F1 은 옛 러너가 `ABORT: no python at …/repo/.venv/bin/python` 으로
죽어 README 레시피가 애초에 불가능했음을 보였다.

### 7.9 라운드 3 게이트

```
.venv/bin/pytest (같은 3파일) -q -p no:cacheprovider
  → 179 passed, 1 skipped (shellcheck 미설치)
ruff check tools/broker_probes tests/tools → All checks passed!
black --check (변경 파일 2건)               → 2 files would be left unchanged
bash -n tools/broker_probes/runners/run_p_ca.sh → OK
```

### 7.10 CI red 처분 (`test` 잡, run 36725449907 · 36728739404)

**원인 1건, 내 검증 구멍 1건.** 두 실행 모두 실패한 테스트는 하나뿐이었다 —
`test_runner_template_passes_shellcheck_when_it_is_available`, 사유 SC1007:

```
run_p_ca.sh line 48:
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) || exit 2
                    ^-- SC1007 (warning): Remove space after = if trying to assign a value
```

`CDPATH= cd` 는 유효한 POSIX 일회성 환경 할당이지만 shellcheck 에게는 「빈 값을
할당하려다 만 것」으로 보인다. SC1007 문서가 권하는 형태 그대로 `CDPATH=''` 로 고쳤다.

**구멍이 더 중요하다.** 이 호스트에는 shellcheck 가 없어서 그 테스트는 **매번 skip**
됐고, 로컬 게이트는 계속 「179 passed, 1 skipped」로 초록이었다. 즉 이 lint 게이트의
첫 실전 실행이 브랜치를 red 로 만든 CI 잡이었다. 처분 둘:

1. `CI` 환경변수가 있는데 shellcheck 가 없으면 **skip 이 아니라 fail** 한다. 게이트는
   어딘가에서는 반드시 돌아야 하고, 그 「어딘가」는 도구가 보장되는 유일한 기계다.
   양방향 확인: `CI=true` 로 red, 없으면 skip.
2. 이번 수정은 믿고 미는 대신 **컨테이너로 실측**했다
   (`docker run --rm koalaman/shellcheck:stable --severity=warning`) → rc 0.
   같은 스캔에서 함께 고친 둘: 지시문 뒤 산문이 붙어 SC1107 을 부를 수 있던
   `# shellcheck disable=SC1090  # …` 를 두 줄로 분리, `exit $rc` 인용.
   남은 것은 info 레벨 SC2012 2건(`ls -t`)뿐이고 게이트(`--severity=warning`) 밖이다 —
   파일명이 하네스가 만드는 `P-CA-<UTC>Z.json` 고정 패턴이라 `find | sort` 쪽이 오히려
   더 깨지기 쉬워 주석으로 남기고 그대로 둔다.

리뷰어가 의심한 나머지 후보는 해당 없음이었다: xdist 순서 의존도, 실제 `~/.config`
접근도 없다(러너 테스트는 `HOME` 을 `tmp_path` 로 두고 env 를 통째로 넘긴다), 두 실행의
실패 목록에 다른 테스트는 없었다.

### 7.11 운영자 지시 2026-10-01 — 워크트리에 자격증명이 없으면 기본 체크아웃에서 복사

> 「워크트리에 .env가 없으면 기본 디렉토리에서 복사해」

`git worktree add` 로 갓 만든 워크트리에는 `.env.*` 가 하나도 없다(전부 gitignore).
러너는 이제 자격증명 파일을 두 갈래로 읽는다:

- **상대 경로**(문서화된 기본, `.env.mock`) — 워크트리 기준으로 푼다. 없으면
  **기본 체크아웃**에서 복사한다. 기본 체크아웃 위치는 하드코딩하지 않고
  `git worktree list --porcelain` 의 **첫 항목**에서 얻는다(체크아웃이 옮겨져도 계속
  동작한다). 복사는 `install -m 600`, 로그 한 줄은 **경로만** 적는다(내용 한 바이트도
  안 적는다). 양쪽 다 없으면 **두 경로를 모두 대며** 거부한다.
- **절대 경로**(예: 09-15 자격증명 백업 `~/.config/...`) — 준 그대로 쓰고 **복사하지
  않는다**.

변수명은 지시가 부르는 대로 `PCA_ENV_FILE` → **`PCA_CREDENTIAL_FILE`** 로 바꿨다
(템플릿은 이 PR 에서 처음 생기므로 마이그레이션 비용 0).

복사본은 워크트리에 **남는다**. `.env.*` 가 gitignore 라 다음 실행의 clean 가드를
깨지 않는다는 것을 테스트로 고정했다 — 이 전제가 틀리면 복사가 다음 실행을 막는다.

**테스트 5건**, 실제 `git worktree` 쌍(기본 체크아웃 + 분리 워크트리)으로:
복사되고 mode 600 이며 로그가 두 경로를 대고 **내용은 안 샌다** · 복사 뒤에도
워크트리가 clean · 양쪽에 없으면 두 경로를 대며 ABORT 하고 프로브는 돌지 않는다 ·
절대 경로는 그대로 쓰고 복사하지 않는다 · 읽을 수 없는 절대 경로는 그렇게 말한다.
전부 `fa799a55` 에서 red. 원본 파일은 일부러 644 로 두어 600 이 `install -m 600` 의
결과임을 증명한다.

**부수**: 자기참조 가드 테스트를 `"$0"`(셸) 기준으로 좁혔다 — `git worktree list` 파싱에
쓰는 awk 의 `$0`(입력 레코드 전체)은 다른 언어의 다른 변수이고 이 파일을 가리키지 않는다.

### 7.12 리뷰 처분 (PR #825 라운드 3 · 7건 · 기각 0)

| # | 지적 | 처분 |
|---|---|---|
| F1 | `PCA_LOG` 의 디렉터리를 검사하지 않는다 — 없으면 step 6 리다이렉션이 실패해 **프로브가 아예 안 돌고**, step 7 은 그래도 crontab 엔트리를 지운다 | **수정.** `mkdir -p`+`touch` 선검사, 그리고 crontab 제거를 「프로브가 실제로 시작됨」에 게이트 |
| F2 | 복사가 기대는 「`.env.*` 는 gitignore」가 **사실이 아니다** — 저장소는 정확한 이름만 무시한다. 그 속성을 「증명」하던 테스트는 자기 `.gitignore` 를 날조했다 | **수정.** 쓰기 전에 `git check-ignore` 로 거부, 테스트는 **실제** `.gitignore` 사용 |
| F3 | 자기삭제 가드를 `"$0"` 로 좁혀서 `unlink $0`·`mv $0`·`shred $0`·`: > $0` 가 전부 통과한다 | **수정.** 넓은 `$0` + awk 줄만 제외, 동사 집합 확장, **뮤테이션 테스트 7종** |
| F4 | `run.credentials` 가 세션 생성 **뒤**로 옮겨져, 부트스트랩이 비-ProbeError 로 죽으면 salvage 아티팩트에 자격증명 블록이 없다 | **수정.** `on_credentials` 콜백으로 `require_account` 직후 기록 |
| F5 | `_holding_failure_detail` 이 브로커 본문을 **무제한·개행 포함**으로 앵커 줄에 찍는다 | **수정.** `_one_line()` — 300자 상한 + 한 줄로 접기 |
| F6 | 전처리 재시도가 `--pace-s`(1.5 s)만 기다린다 — 방금 스로틀을 유발한 바로 그 초당 간격 | **수정.** `--retry-wait-ms`, 러너가 `PCA_POLL_MS` 를 넘긴다 |
| F7 | 「필요한 수정이 있나」 게이트가 소스 **문자열 grep** 이다 — 언급과 수정을 구분 못 하고 rename 에 깨진다 | **수정.** `POLICY_VERSION` 핸드셰이크 |

**F2 가 유일한 보안 건이고, 지적이 옳았다.** 실측: `git check-ignore` 는 `.env.mock` 을
무시하지만 `.env.mock.bak-20260915`(README 가 거론하던 이름) · `.env.probe` 는 **무시하지
않는다**. 저장소에는 `.env.*` 글롭이 없고 정확한 이름 목록만 있다. 그런데 그 속성을
지키던 테스트가 자기 `.gitignore` 에 `.env.*` 를 **날조**해 넣고 통과하고 있었다 — 가드가
자기가 막는다고 말한 것을 허용하는, 이 저장소가 네 번 겪은 바로 그 형태다. 처분은
**복사 전 거부**(`git check-ignore -q`, 존재하지 않는 경로에도 답하므로 아무것도 쓰이지
않는다)이고, 테스트는 실제 `.gitignore` 를 복사해 쓴다. 음성 테스트 1건 추가:
`.env.mock.bak-x` → 거부, 워크트리에 아무것도 남지 않음.

**F3 은 내가 라운드 2 에서 좁혀 만든 구멍이다.** awk 의 `$0` 을 피하려고 셸 `"$0"` 로
좁혔고, 그 결과 `unlink $0` 류가 전부 통과하게 됐다. 되돌려 넓게 보되 awk 줄만 이름으로
제외하고, 동사도 `rm|unlink|mv|shred|truncate|: >` 로 넓혔다. **이 가드는 미래의 편집을
막는 것이라 오늘 코드가 green 이어도 아무것도 증명하지 못하므로**, 일부러 망가뜨린 사본
7종에 대해 가드가 실제로 red 가 되는지 확인하는 뮤테이션 테스트를 붙였다.

**라운드 4 red 증명.** 새 테스트 14건 중 **11건이 `22e9747a` 에서 red**. red 가 아닌 3건과
그 이유를 그대로 적는다 — 셋 다 의도된 것이다:

- `test_the_repo_ignores_exact_env_names_not_a_glob` — 실제 `.gitignore` 를 **측정**하는
  전제 확인 테스트다. 코드가 바뀐 게 아니므로 전후가 같아야 맞다.
- `test_the_preflight_falls_back_to_pace_when_no_interval_is_given` — 바뀌지 **않아야**
  하는 기본값을 고정하는 핀(`EGW00201` 핀과 같은 성격).
- `test_runner_template_never_removes_itself` — 오늘 파일은 전후 모두 깨끗하다. 효력은
  위의 뮤테이션 테스트 7종이 증명한다(그쪽은 좁은 가드에서 4종이 통과해 red).

### 7.13 라운드 4 게이트

```
.venv/bin/pytest (같은 3파일) -q -p no:cacheprovider
  → 203 passed, 1 skipped (로컬 shellcheck 없음; CI 가 돌린다)
ruff check tools/broker_probes tests/tools → All checks passed!
black --check (변경 파일 2건)               → unchanged
bash -n run_p_ca.sh                        → OK
docker koalaman/shellcheck:stable --severity=warning → rc 0
```

**CI 비고**: `22e9747a` 에서 `test` pass(6m38s) · `performance` fail(+236.5%).
후자는 이 PR 과 무관한 기존 상태다 — 메모리 `ci-gating-reality` 의 「baseline 이
2026-05-30 생성 후 미갱신이고 현재값이 일관되게 ~2.6배」와 수치가 일치하고, 이 PR 은
`tools/broker_probes/**` 와 `tests/tools/**` 밖을 건드리지 않는다. **baseline 재생성은
하지 않는다** — 먼저 재생성하면 진짜 회귀가 영구히 안 보이게 된다(같은 메모리 경고).

### 7.14 후속 착지 — #830 참조 전용 모드와 러너의 지급일 대조 (2026-10-01)

§4 에 적지 못했던 결합 하나가 10-01 에 두 가지 형태로 동시에 드러났고(캠페인 README
2026-10-01 블록), 별도 PR 로 닫았다. 이 절은 그 착지 기록이다.

**관측된 결함 둘.**

1. 다음 대상 058610 의 **사전 참조조회가 거부됐다**(rc 4, 아티팩트 없음, 로그
   `~/.config/kis-probes/p-ca-20261001-058610-refcheck.log`): `--payable-time is in the
   future ('2026-10-22T00:00:00+09:00' > 2026-10-01T08:04:53Z)`. 그 거부는 **폴링 경로를
   위한 규칙**이다(미래 t0 는 음수 지연을 기록한다). 참조조회는 아무것도 페어링하지 않으므로
   해당되지 않는데, `--reference-check` 가 폴링 인자에 묶여 있어 함께 막혔다.
2. 같은 날 000660 재관측의 `reference_dates=[]` — ksdinfo 질의 창이 **실행 시각** 기준
   −30d…+180d 라서 10-01 실행의 `F_DT=20260901` 이 됐고, 09-30 에 돌아왔던 행의
   `record_date=20260831` 이 **하루 차이로 창 밖**이었다. 행이 사라진 게 아니라 창이 지나갔다.

그리고 둘을 합치면 더 나쁜 것이 남아 있었다: `_do_reference_check` 는 행을 **기록만** 하고
`divi_pay_dt` 를 t0 로 되먹이지 않았고, 러너도 대조하지 않았다. 브로커 지급일이 하루만
달라도 프로브는 **틀린 t0 로 16 h 창을 다 쓰고 CENSORED 를 쓴 뒤에야** 아티팩트 안에서
불일치가 드러난다.

**처분.**

| 무엇 | 어디 |
|---|---|
| `--reference-only` — ksdinfo GET 하나, 잔고 호출·보유 요구·폴링 전부 없음. 미래 t0 허용(페어링하지 않으므로). leg 은 `REFERENCE_ONLY` 로 명시 skip — CENSORED/ABORTED 아님 | `probes_ca.py::_do_reference_only` |
| ksdinfo 창을 **t0 와 실행 시각을 모두 포함**하도록 앵커링(`min(…)−30d … max(…)+180d`). 마진은 그대로이고, 기준일↔지급일 간격이 발행사마다 달라 `--reference-from/--reference-to` 로 직접 지정할 수 있다. 창은 아티팩트 `observations.reference_window` 에 남는다 | `probes_ca.py::_ksdinfo_window` |
| 러너가 폴링 **전에** `divi_pay_dt` 를 `PCA_PAYABLE` 과 대조하고 불일치면 ABORT. 행 선택은 `PCA_RECORD_DATE`, 없으면 최신 기준일. 우회는 `PCA_ALLOW_PAYDATE_MISMATCH=1`(로그 남김), 행 없음을 차단하려면 `PCA_REQUIRE_REFERENCE_ROW=1` | `runners/run_p_ca.sh` 5b |
| `POLICY_VERSION` `p-ca-retry-policy/1` → `/2` (양쪽). 러너 계약이 바뀌었고 `/1` 러너는 대조를 **조용히 건너뛴다** | 양쪽 |

**계획과 다른 점.** (a) 러너가 아티팩트 JSON 을 파싱하지 않는다 — 프로브가 `REFERENCE_WINDOW=`
/`REFERENCE_STATUS=`/`REFERENCE_ROWS=`/`REFERENCE_ROW=<record_date>|<divi_pay_dt>` 앵커 줄을
찍고 러너는 그것만 읽는다(`HELD=` 와 같은 규율). 덕분에 선택·대조 로직은 bash 몇 줄이고,
줄을 만드는 쪽은 Python 테스트로 실측된다. 행 값은 **숫자와 구분자만 남기고 전부 버린다** —
브로커 문자열이 줄을 하나 더 만들어 내지 못하도록. (b) 아티팩트 복사를 `copy_new_artifact`
한 곳으로 모아 참조 전용 실행의 아티팩트도 `PCA_EVIDENCE_DIR` 로 남긴다(수용 기준 1).
(c) `--reference-from/--reference-to` 는 「싸면 추가」 항목이었고 실제로 쌌다 — 그리고 30일
룩백이 **경계값**이라는 걸 10-01 사례가 보여줬으므로(09-30 − 30d = 08-31, 하루만 어긋나도
놓친다) 운영자 탈출구가 필요했다.

**수정 전 red 증명.** 두 번 나눠 측정했다.

- **프로브 쪽**(`probes_ca.py` 를 `origin/main` 판으로): 새 테스트 18건 전부 red.
  `--reference-only` 가 잔고 TR 을 먼저 친다(`assert '/ksdinfo/dividend' in '…/inquire-balance'`) ·
  미래 t0 가 그대로 거부된다(10-01 의 그 문장 축자) · 앵커 없는 창이 10-01 reproduction 을
  0행으로 만든다(`IndexError`, ksdinfo 호출 자체가 없다) · `_REFERENCE_*` 접두사 부재 ·
  `--reference-from` 이 무시된다 · `--window-s must be > 0`.
- **러너 쪽**(러너만 `origin/main` 판, `EXPECT_POLICY_VERSION` 만 `/2` 로 맞춰 핸드셰이크
  abort 가 행동을 가리지 않게 함): #830 러너 테스트 16건 중 **12건 red**. 불일치 입력에
  `assert 0 != 0`(즉 **창을 그대로 폴링했다** — 이 이슈의 결함 그 자체) · 확인 로그 부재 ·
  `(reference-only)` 복사 없음 · pacing sleep 이 2회가 아니라 1회.
  red 가 아닌 4건과 이유: `test_runner_template_carries_no_instance_defaults`(옛 템플릿을
  **측정**하는 전제 확인) · `test_the_pay_date_check_is_skipped_for_a_quantity_leg_class` ·
  `test_no_pay_date_check_runs_when_the_reference_check_is_not_asked`(둘 다 「대조가 돌지
  **않아야** 하는」 핀이라 옛 코드에서도 참) · `test_runner_refuses_a_quantity_leg_class_without_an_effective_time`(기존 테스트).
  ⚠ 프로브만 되돌린 1차 측정에서는 러너 테스트가 공유 헬퍼의 `AttributeError` 로 죽어
  **행동을 증명하지 못했다** — 그래서 러너만 되돌린 2차 측정을 따로 했다.

**게이트.**

```
.venv/bin/pytest tests/tools/test_broker_probes_ca.py \
  tests/tools/test_broker_probes_pacing.py \
  tests/tools/test_broker_probes_balance.py -p no:cacheprovider
  → 236 passed, 1 skipped (로컬 shellcheck 없음; CI 가 돌린다)
ruff check tools/broker_probes tests/tools → All checks passed!
black --check (변경 .py 2건)               → unchanged
bash -n tools/broker_probes/runners/run_p_ca.sh → OK
docker koalaman/shellcheck:stable --severity=warning → rc 0 (필터 없이도 rc 0)
```

**운영자가 해야 할 것 — 10-22 무인 래퍼.** `~/.config/kis-probes/run-p-ca-20261022.sh` 는
`PCA_REFERENCE_CHECK=1` 을 이미 넣으므로, 이 PR 이 머지되면 10-22 슬롯은 **대조를 하게 된다**.
058610 의 기준일을 알면 `PCA_RECORD_DATE` 를 넣는 편이 낫고(모르면 최신 행), 지급일이
DART 출처라 ksdinfo 와 다를 가능성을 감안해 **불일치 시 슬롯을 포기할지**(기본) **경고만
남기고 돌릴지**(`PCA_ALLOW_PAYDATE_MISMATCH=1`) 를 미리 정해 둬야 한다. 아무 행도 안 오면
기본값은 「경고 후 진행」이다.

#### 7.14.1 리뷰 처분 (PR #831 라운드 1 · high · 10건 · 기각 0)

| # | 지적 | 처분 |
|---|---|---|
| F1 | 참조 전용 아티팩트가 `PCA_EVIDENCE_DIR` 에 같은 이름·같은 종목·`errors=[]` 로 떨어져, 10-22 래퍼의 재무장 가드가 **완료 관측으로 읽고 남은 슬롯을 해제**한다 | **수정.** 복사 목적지를 `$PCA_EVIDENCE_DIR/reference-only/` 로 분리 + leg 을 `legs.<class>.<leg>` 키에 `REFERENCE_ONLY` 로 명시 skip + 래퍼 가드 계약을 테스트로 고정 |
| F2 | 기본 행 선택(`sort -r | head -1` = 최신 기준일)이 **다음 분기 배당 행**을 비교해 거짓 불일치 ABORT | **수정.** 「**어느** 행이든 `divi_pay_dt == WANT_PAY` 면 확인」, 행이 있는데 전부 불일치일 때만 ABORT |
| F3 | `WANT_PAY` 가 운영자가 적은 오프셋 그대로의 앞 10자 — 비-KST 오프셋이면 거짓 불일치 (CLAUDE.md 비협상 위반) | **수정.** `TZ=Asia/Seoul date -d` 로 KST 변환 후 날짜. 파싱 불가도 여기서 ABORT |
| F4 | 룩백 30일이 **지급일** 기준이라 기준일→지급일 간격에 맞지 않는다 — 058610 은 경계 정확히, 연배당은 **항상** 창 밖 → 조용히 0행 | **수정.** 룩백 120일 + `PCA_RECORD_DATE` 를 알면 러너가 `--reference-from = 기준일−1d` 를 넘긴다 |
| F5 | 참조조회가 **건강하지 않은 경로** 때문에 멈춘 것과 「행 없음」이 러너에게 구분 불가(그 경로에 16 h 폴링을 건다) | **수정.** 상태 토큰 5종을 **모든 경로에서 정확히 한 줄**; `OK`/`NO_ROWS`/`UNSUPPORTED` 외는 전부 하드 ABORT(줄 자체가 없어도) |
| F6 | 5b 와 본 시행이 **같은 GET 을 두 번** 보낸다 | **수정.** 5b 가 돌면 본 시행에서 `--reference-check` 를 뺀다. 행은 `--note` 에 싣는다 |
| F7 | `record_date` 는 구분자를 남기고 `divi_pay_dt` 만 숫자화 — 계약의 양쪽이 다르게 정규화된다 | **수정.** `_reference_field` 가 **둘 다 숫자만**. 계약은 `REFERENCE_ROW=YYYYMMDD|YYYYMMDD`, 러너의 `tr -cd` 는 제거 |
| F8 | 같은 기준일의 형제 행(현금/주식) 중 `tail -1` 이 **빈 지급일 쪽**을 집는다 | **수정.** F2 와 같은 처분 — 후보 전체를 본다 |
| F9 | `--reference-from`/`--reference-to` 역전 쌍이 그대로 나간다 | **수정.** 사전조건 거부(`is after --reference-to`) |
| F10 | 복사 실패가 **로그 한 줄도 없이** `ART_BEFORE` 를 전진시킨다 | **수정.** 성공했을 때만 전진, 실패는 WARN |

**F1 이 가장 위험했다.** 지적이 옳았고, 범위도 리뷰가 적은 것보다 넓다: 래퍼의
`done_already` 는 OBSERVED 를 `measurements["legs.cash_dividend.cash"]` 로 판정하는데,
그 키는 `_poll_loop` 이 쓰고 `_finalize` 가 쓰지 않는다 — 즉 **아티팩트 모양과 가드 계약이
서로 다른 파일에 있고 아무도 둘을 함께 검사하지 않았다**. 처분은 세 겹이다: 복사 분리(글롭이
닿지 않는다) · `args.reference_only`(래퍼가 읽는다) · leg 별 `REFERENCE_ONLY` skip(사람이
읽는다). 그리고 래퍼의 술어를 **테스트에 그대로 옮겨** 네 가지 모양(참조 전용 · CENSORED ·
OBSERVED · ABORTED)에 대해 판정을 고정했다. 이게 없으면 둘은 조용히 어긋나고, 어긋난 것을
아는 날은 10-22 하루뿐이다.

**F5 의 교훈은 「침묵은 상태가 아니다」.** 수정 전 참조조회는 두 전송 오류로 멈출 때 **아무
것도 찍지 않았고**, 러너는 그것을 「행 없음」으로 읽어 경고 후 16 h 창을 시작했다 —
`_do_reference_check` 의 docstring 이 「폴링 루프는 같은 경로를 훨씬 멀리 걷는다」고 적어둔
바로 그 일이다. 가드가 자기가 막는다고 적은 것을 통과시키는 형태.

**라운드 2 red 증명.** 새/변경 테스트 45건 중 **32건이 라운드-1 HEAD(`d9435432`)에서 red**.
행동 red 의 예: 불일치 입력에 `assert 0 != 0`(창을 그대로 폴링) · `'20260831' == '20260602'`
(룩백) · `'2026/09/30' == '20260930'`(F7) · `--reference-check not in argv`(F6) ·
`[PosixPath('…20261022T000000Z.json')] == []`(F1, 아티팩트가 증거 디렉터리 루트에 떨어짐) ·
`'no candidate row carries a divi_pay_dt'` 부재.
red 가 아닌 13건은 전부 **핀**이다(바뀌지 말아야 할 것): 래퍼 계약 4종 중 3종은 기존 시행
모양이 이미 맞았음을 고정하고, `reference_only` 로 거르는 것도 라운드 1 에서 이미 참이었다 ·
`_reference_field` 의 숫자-입력 3건 · 깨끗한 상태 3종이 시행을 막지 **않는다** · 기준일을
모를 때 override 를 보내지 **않는다** · 5b 가 안 돌면 `--reference-check` 가 **남는다** ·
역전이 아닌 동일 쌍은 허용.
⚠ 처음에 상태 토큰을 `@pytest.mark.parametrize` 안에서 `pc._REF_*` 로 읽었더니 수정 전
코드에서 **수집 오류**가 나 파일 전체가 죽었다 — 그러면 어느 테스트도 증명하지 못한다.
데코레이터는 리터럴로 바꾸고, 리터럴과 모듈 상수를 잇는 핀 1건을 따로 뒀다.

#### 7.14.2 라운드 2 게이트

```
.venv/bin/pytest (같은 3파일) -p no:cacheprovider
  → 269 passed, 1 skipped (로컬 shellcheck 없음; CI 가 돌린다)
ruff check tools/broker_probes tests/tools → All checks passed!
black --check (변경 .py 2건)               → unchanged
bash -n tools/broker_probes/runners/run_p_ca.sh → OK
docker koalaman/shellcheck:stable --severity=warning → rc 0
```
