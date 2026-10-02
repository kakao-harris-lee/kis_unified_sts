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

- ~~P-8 러너의 「전송 오류 → STOP」 전이(README 09-30 블록, 리뷰 F4): P-8 재개 전 같은 분류를
  `probes_order.py` 공존 폴링에 적용해야 하나 이 PR 은 P-CA 경로만 고친다. P-8 3~5회차 재개
  조건으로 남긴다.~~ → **#841 로 착지(§7.15)**. 같은 분류·재시도를 `probes_order.py` 에
  적용하고 추적 러너 `run_p8.sh` 를 두었다. 조사 중 계획에 없던 결함 하나가 더 나왔다 —
  수정 전 폴 루프가 거부 응답을 「공존 종료」로 읽어 `coexistence_ms` 를 **만들어내고
  있었다**(§7.15.2).
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

- ~~§4 그대로: P-8 공존 폴링(`probes_order.py`)의 「전송 오류 → STOP」 전이는 이 PR 범위 밖.
  P-8 3~5회차 재개 조건으로 남는다.~~ → **#841 로 착지(§7.15)**. (참조 전용 모드·지급일
  대조는 §4 에서 빠져 #830 으로 착지했다 — §7.14.)
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
| 러너가 폴링 **전에** `divi_pay_dt` 를 `PCA_PAYABLE` 과 대조하고 불일치면 ABORT. 행은 `PCA_RECORD_DATE` 로 좁히되 **필수가 아니고**, 없으면 돌아온 **모든 행**이 후보다(어느 하나라도 맞으면 확인). 우회는 `PCA_ALLOW_PAYDATE_MISMATCH=1`(로그 남김), 행 없음을 차단하려면 `PCA_REQUIRE_REFERENCE_ROW=1` | `runners/run_p_ca.sh` 5b |
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

#### 7.14.3 리뷰 처분 (PR #831 라운드 2 · high · 10건 · 기각 0)

| # | 지적 | 처분 |
|---|---|---|
| F1 | `UNSUPPORTED` 가 **HTTP 500·비-JSON 본문까지** 덮어서, 러너가 「깨끗한 답」으로 통과시킨다 — F5 게이트가 정작 중요한 곳에서 샌다 | **수정.** `ERROR` 토큰 분리. 기준은 **브로커가 답했는가**: HTTP 200 + `rt_cd` 있는 봉투 ⇒ `UNSUPPORTED`(경로 건강, TR 미지원), 그 외 ⇒ `ERROR`(러너 ABORT) |
| F2 | 5b 가 `--poll-ms` 를 안 넘겨 원장 스로틀 재시도가 `--pace-s` 만 기다린다 — 방금 스로틀을 유발한 그 초당 간격 | **수정.** `--poll-ms "$PCA_POLL_MS"` 전달. 「`--poll-ms` 는 무시된다」는 프로브 주석도 정정(무시되지 않는다 — 재시도 대기다) |
| F3 | `ref_rc` 를 **게이트하지 않는다** — 깨끗한 상태 줄을 찍고 rc 5 로 죽은 전처리를 건강하다고 본다 | **수정.** 보유 점검과 같은 규칙: 비-0 종료면 숫자(여기선 상태)를 믿지 않고 ABORT |
| F4 | 역전 검사가 **override 끼리만** 비교한다 — 한쪽만 준 경우(파생된 반대쪽과의 역전)는 그대로 빈 창 | **수정.** 검사를 **파생 후** 창(`_ksdinfo_window`)에 대해 수행. 단일 override 두 형태 + 쌍 역전 전부 사전조건 거부 |
| F5 | 5b 가 돌면 본 시행 아티팩트에서 `reference_dates`/`mock_reference_support` 가 **사라진다**(런북이 기록한다고 적은 관측). `--note` 대체는 8행·2필드로 손실 | **수정.** `--reference-rows-from <5b 아티팩트>` — 그 관측들을 **축자 입양**. GET 0회, 형식 불변, 출처 관측 1건 추가 |
| F6 | 복사가 실패하면 `ART_BEFORE` 가 그대로라, 본 시행이 아티팩트를 안 쓴 경우 step 8 이 **참조 전용 아티팩트를 증거 루트로** 복사한다 | **수정.** `REF_ART` 로 신원 기록, 본 시행 복사에서 **이름이 아니라 신원으로** 제외 |
| F7 | 보유가 필요 없는 5b 가 **페이지네이션 보유 조회 뒤**에 있다 — 지급일 불일치 슬롯마다 잔고 조회를 통째로 버린다 | **수정.** 5b 를 자격증명 가드 직후, 보유 점검 **앞**으로 옮겼다(step 5). 단계 번호 재배치 |
| F8 | `_do_reference_only` 가 `_StopRun` 을 삼키고 **leg skip 전에** 반환 — 멈춘 조회는 `legs.<class>.<leg>` 가 **없는** 아티팩트를 쓴다 | **수정.** `finally` 로 모든 경로에서 leg skip + `leg_provenance_class` |
| F9 | 「없으면 최신 기준일」이 러너 주석·계획·PR 본문에 남아 코드(어느 행이든)와 모순 | **수정.** 러너 주석·계획 §7.14 정정. ⚠ **PR 본문은 `gh pr edit` 금지 규칙상 내가 못 고친다 — 운영자 반영 필요** |
| F10 | `REFERENCE_ROWS` 는 `output1` 전체를, `REFERENCE_ROW=` 는 dict 행만 센다 | **수정.** 실제 **방출한 행**만 센다. 방출 0이면 상태도 `NO_ROWS` |

**F1 과 F8 은 같은 형태다 — 가드가 자기가 막는다고 적은 것을 통과시킨다.** F1 은 「건강하지
않은 경로엔 창을 걸지 않는다」는 게이트가 500 을 통과시켰고, F8 은 「leg 질문을 비워두지
않는다」는 F1 처분이 **오류 경로에서만** 비워뒀다. 둘 다 정상 경로만 보면 초록이다.

**F1 의 처분은 리뷰 문구와 한 군데 다르다.** 리뷰·지시는 「알려진 `msg_cd` 허용목록」을
제안했는데, **모의 ksdinfo 미지원 응답의 msg_cd 는 이 저장소에 한 건도 측정돼 있지 않다**
(관측은 전부 `SUPPORTED`). 지금 허용목록을 만들면 목록이 비어 있어서, `UNSUPPORTED` 팔이
**존재 이유인 바로 그 경우를 ABORT 로 바꾼다** — 가드가 자기가 허용한다고 적은 것을 막는
형태다. 그래서 지시가 함께 제시한 「documented shape」 쪽을 택했다: **브로커가 답했는지**
(HTTP 200 + `rt_cd` 봉투)로 가른다. 리뷰의 실패 시나리오(500 + HTML)는 그대로 `ERROR` 로
떨어지고, 코드는 상태 줄에 찍히므로 운영자가 **측정 뒤에** 더 좁힐 수 있다.

**라운드 3 red 증명.** 새/변경 테스트 32건 중 **26건이 라운드-2 HEAD(`5608aa62`)에서 red**.
행동 red: `the trial re-sent the reference GET`(F5) · `the holding walk was spent anyway`(F7) ·
`the holding walk ran before the pre-check`(F7 역방향) · `assert 0 != 0`(ERROR 가 ABORT 를
안 만든다, F1) · `REFERENCE_ROWS=3` 에 행 1줄(F10) · `probe contacted the broker when it must
not`(F4 단일 override) · `--poll-ms not in argv`(F2) · `reference check exited 5` 부재(F3) ·
`is this run's reference-only lookup` 부재(F6) · 멈춘 조회의 `skips == []`(F8).
red 가 아닌 6건은 핀이다: 깨끗한 봉투의 거부가 `UNSUPPORTED` 로 남는 것(F1 역방향) ·
파생 창 안쪽 단일 override 허용(F4 역방향) · 입양 시행도 완료 관측으로 세어지는 것 ·
`OK`/`NO_ROWS`/`UNSUPPORTED` 3종이 시행을 막지 않는 것.

#### 7.14.4 라운드 3 게이트

```
.venv/bin/pytest (같은 3파일) -p no:cacheprovider
  → 294 passed, 1 skipped (로컬 shellcheck 없음; CI 가 돌린다)
ruff check tools/broker_probes tests/tools → All checks passed!
black --check (변경 .py 2건)               → unchanged
bash -n tools/broker_probes/runners/run_p_ca.sh → OK
docker koalaman/shellcheck:stable --severity=warning → rc 0
```

라운드 2 CI(`5608aa62`): `test` pass(6m18s) · `tos-gate`·`tos-firewall`·`ruff`·`lint`·
`type-check`·`backtest-extra` pass · `performance` fail — 메모리 `ci-gating-reality` 의
기존 baseline 미갱신 건이고 이 PR 은 `tools/broker_probes/**`·`tests/tools/**` 밖을 건드리지
않는다. **baseline 재생성 안 함.**

### 7.15 후속 착지 — P-8 의 전송 오류/브로커 거부 분리와 추적 러너 (PR #841, 2026-10-02)

§4 가 「범위 밖」으로 남긴 단 하나의 항목이자 README 가 **P-8 3~5회차 재개의 선결
조건**으로 적어둔 것이다(캠페인 README 09-30·10-01 블록). 이 절이 그 착지 기록이다.

#### 7.15.1 무엇이 트라이얼 3~5 를 죽였나

2026-09-28 09:05 KST 호스트 cron, 분리 워크트리(`repo_commit=ac2efb0f`). 1회차는
MEASURED(`P-8-20260928T000506Z`). 2회차는 제출·정정이 **둘 다 통과**했고(ODNO 558 →
560, `amend_rt_cd=0`) 공존 폴링도 최소 1회 돌았는데 그 폴에서

```
ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed
connection without response'))
```

가 나 예외가 `probe_p8` 밖으로 탈출했다. `run.py` 가 부분 run 을 salvage 해 rc 5 로
끝냈고, `P-8-20260928T000658Z` 에는 `coexistence_ms`·`replace_issues_new_odno`·
`poll_granularity_ms` 가 **없다**. 전송은 수 초 만에 회복했다 — 바로 뒤 `finally` 의
정리 취소가 `rt_cd=0` 으로 성공했다. 그런데 러너는 이렇게 적었다.

```
VERDICT: STOP: P-8 2/5 오류 1건(브로커 거부 포함) — 1/5 성공 후 중단(재시도 금지)
```

거부된 것은 아무것도 없었다. **3~5회차는 브로커가 막아서가 아니라 러너가 전송 오류를
브로커 거부와 한데 묶어서 실행되지 않았고**, `capabilities.replace_semantics.mode` 는
아직도 N≥5 가 없다. 같은 캠페인 09-23 절은 `ReadTimeout` 을 정반대로 분류했다.

#### 7.15.2 조사 중 드러난 더 나쁜 것 — 폴 루프가 값을 **만들어내고 있었다**

수정 전 공존 폴 루프는 `rt_cd` 를 **전혀 보지 않았다**. 거부 응답에는 `output1` 이
없으므로 `rows=[]` → `live=∅` → `both=False` 가 되고, 그것은 이 루프에서 「공존이
끝났다」는 신호다. `origin/main` 판으로 실측한 결과:

| 폴 #2 의 응답 | 수정 전 결과 |
|---|---|
| HTTP 429 | `coexistence_ms: 0.17` · `errors: []` · `provenance_class: MEASURED` |
| `EGW00201` | `coexistence_ms: 0.16` · 같음 |
| `EGW00215` | `coexistence_ms: 0.29` · 같음 |

즉 **거부·스로틀 응답 하나가 「공존 구간이 끝났다」로 읽혀 아무도 관측하지 않은
`coexistence_ms` 를 MEASURED 아티팩트에 써 넣고 있었다.** 방향은 작은 값 = 「원자적
교체」 쪽이고, 그것이 `B_protective_request_complete` 에 대해 fail-open 이다. 계획에
없던 발견이며, 이 PR 이 함께 닫는다.

**나머지 절반 — `classify_answer` 가 잡지 않는 거부.** 위 셋은 429/`EGW00201`/
`EGW00215` 라 분류기가 잡지만, **평범한 `rt_cd≠0` 은 그 셋 중 아무것도 아니다**.
이 브로커는 빈 결과 집합을 거부 모양으로 답한다 — `rt_cd='7'` + `msg_cd='KIOK0560'`
(「조회할 내용이 없습니다」, `P-BAL-20260731T114344Z`) — 그리고 `_live_odno_keys` 는
정리 소비자에 대해 **이미** 그것을 「아무것도 live 가 아니다」로 읽기를 거부한다.
폴 루프만 읽고 있었다. 즉 분류기만 붙였다면 가드가 자기가 막는다고 적은 것을 그대로
통과시켰을 것이다(이 저장소가 네 번 겪은 그 형태).

**처분은 일부러 「중단」이 아니다.** 이 표면이 책이 비면 거부 모양으로 바뀌는지는
여기서 측정된 적이 없고, 첫 거부에 멈추면 **정상적인 공존 종료를 중단으로 바꿔** 오늘
돌아가는 측정을 근거 없는 추측으로 깨뜨린다. 그래서 답하지 않은 폴은 **기록하고
건너뛴다** — 공존 마크를 세우지도 지우지도 않고 루프는 계속한다. 창 전체에서
**하나도** 답하지 않았을 때만 `stop_reason=query_unanswered` 다. 그 경우만이
「아무것도 관측하지 못했다」를 증명하기 때문이다. 아티팩트에
`coexistence_polls_answered`·`coexistence_polls_not_answered` 가 남는다.

고정하는 테스트: 429/`EGW00201`/`EGW00215` 는 `"coexistence_ms" not in
run.measurements` · `no_rows` 한 번은 구간을 **끊지 않는다**(`coexistence_ms > 0`,
`polls_not_answered == 1`) · 전부 `no_rows` 면 `query_unanswered` 이고 측정 없음.

**이 수정을 실측하다 결함 둘이 더 나왔고, 같이 고쳤다.**

1. **멈춤 사유 문구가 거짓을 말했다.** 2분기 삼항식이라 `query_unanswered` 에
   「The stop is our own call rate (HTTP 429 / EGW00201)」가 붙었다 — 일어나지
   않은 원인을 지목하는 문장이고, 이 하네스가 반복해서 값을 치르는 바로 그
   형태다. 그리고 skip 사유는 `--visibility-timeout-s …s did NOT elapse` 라고
   적었는데 **`query_unanswered` 는 창을 끝까지 쓴다**(표면이 답하지 않았을 뿐).
   창이 흘렀는데 안 흘렀다고 적는 것은 2026-09-17 P-CA 오류 그 자체다. 처분:
   `_P8_STOP_NARRATION` 조회표 — 사유별로 (문구, 창 문구) 쌍을 명시하고,
   「다른 게 아니니까」로 추론하지 않는다. 세 사유가 다 들어 있는지 테스트가
   고정한다(없는 키는 `KeyError` 다).
2. **답하지 않은 폴의 증거가 무한했다.** 실측: `--pace-s 0` · 0.3 s 창에서
   **폴 12,265회**, 관측 12,268건. 그만한 리스트가 커밋되는 아티팩트에 들어간다.
   처분: **distinct `msg_cd` 당 축자 기록 1건**, 횟수는 전부
   `coexistence_not_answered_codes` 에 센다. 반복은 첫 건이 담지 않은 정보를
   담지 않는다.
3. **같은 형태가 한 군데 더 있었다.** 전송 중단 메시지가 세 phase 에 공통
   문장 하나를 썼는데 — 「an order-mutating call is never retried (a resent
   submit is the duplicate-order hazard P-2 measures)」 — `quote` 는 GET 이다.
   `_P8_NO_RETRY_REASON` 으로 phase 별 사유를 적는다. 이 셋은 전부 「다른 게
   아니니까 이것」으로 문장을 고르던 자리였고, 조회표가 그 추론을 없앤다.

#### 7.15.3 바뀐 파일

| 파일 | 무엇 |
|---|---|
| `tools/broker_probes/common.py` | 일시 오류 정책 **한 벌**: `TRANSIENT_*`/`STATUS_*` · `is_ledger_throttled` · `transport_transient_types` · `transport_excerpt` · `transient_kind` · `classify_answer` · `call_evidence` · `retry_evidence` · `Outcome` · `Pacer`(`wait`+`defer`) · `Retries` · `record_retry` · `retry_once` |
| `tools/broker_probes/probes_ca.py` | 그 한 벌을 **쓴다**. 로컬 이름은 전부 별칭(`_retry_once = retry_once` …)이라 6-튜플 시그니처와 기존 테스트 전부 그대로 |
| `tools/broker_probes/probes_order.py` | `POLICY_VERSION` · `_CallPacer(Pacer)` · `inquire_futures_classified` · `_poll_coexistence`(재시도·창 마감·분류·`rt_cd≠0` 는 끊지 않고 기록) · 제출/정정의 전송 오류 분류(재시도 없음) · `_live_odno_keys` 재시도 · `P8_STOP=`/`P8_COEXISTENCE=` 앵커 줄 · `measurements.stop_reason`·`coexistence_polls_used` |
| `tools/broker_probes/runners/_common.sh` | 두 러너가 **source** 하는 공유 가드(신규) |
| `tools/broker_probes/runners/run_p_ca.sh` | 그 가드를 쓰도록 축약. 로그 문구는 한 글자도 바꾸지 않았다 |
| `tools/broker_probes/runners/run_p8.sh` | 추적되는 P-8 러너 템플릿(신규) |
| `tools/broker_probes/runners/README.md` | `_common.sh` · `run_p8.sh` 인스턴스화 레시피와 STOP 규칙 표 |
| `tests/tools/test_broker_probes_p8_transient.py` | 새 테스트 62건(수집 기준, `parametrize` 전개 포함; shellcheck 미설치 시 그중 1건 skip) |
| `tests/tools/test_broker_probes_ca.py` · `test_broker_probes_pacing.py` | 공유 파일을 따라가는 수정(아래 7.15.6) |

#### 7.15.4 정책 — P-CA 와 같은 것, 그리고 다른 것

**같은 것.** 분류 우선순위 ①응답 없음 ⇒ 일시 · ②`is_rate_limited`(429·`EGW00201`)
⇒ 중단, 재시도 없음 · ③`EGW00215` ⇒ 일시. ②가 ③보다 앞인 것까지 그대로다. 재시도는
**한 번**, **한 폴링 간격**(`effective_interval_ms(--poll-ms, --pace-s)`) 뒤이며
`Pacer.defer` 로 지금부터 다시 잰다. 창이 이미 지났으면 재시도를 거부한다(`can_retry`).
모든 일시 오류는 `retry_evidence` 에 남고(`phase`·`retried`), `measurements.retries` 는
**실제로 쓴 재시도**만 센다.

**다른 것 셋.**

1. **단발 호출(`quote`·`submit`·`amend`)은 분류만 하고 재시도하지 않는다.** 제출을
   다시 보내는 것은 P-2 가 측정하는 바로 그 중복주문 위험이고, 정정을 다시 보내면
   수량을 두 번 먹을 수 있다. 시세 조회는 GET 이지만 재시도해 봐야 트라이얼의 시계만
   밀 뿐이다 — 아직 아무것도 걸려 있지 않고, 가격 조회에 답하지 못하는 브로커에
   주문을 넣기 시작할 이유가 없다. `_record_write_transport_stop` 이 셋 다
   `retry_evidence(retried=False)` 를 남기고 `transient:transport` 로 끝낸다 —
   **분류는 러너가 필요로 하는 것이고, 09-28 에 없던 것도 그것**이다. `phase` 는 셋을
   구분한다: 시세 실패와 제출 실패는 「주문이 걸려 있는가」가 다르다.
2. **일시 중단은 `run.error` 를 남긴다**(P-CA 는 `run.skip` 만 남긴다). 이유: P-8
   아티팩트의 소비자는 `coexistence_ms` 를 읽는데, `provenance_class: MEASURED` 인
   아티팩트에서 그 키가 **없는** 것을 `.get(key, 0.0)` 으로 읽으면 0.0 = 「원자적
   교체」가 된다 — 7.15.2 가 보여준 그 fail-open 방향이다. 09-28 2회차도 NOT_MEASURED
   였으므로 이 PR 은 그 판정을 바꾸지 않는다. `run.skip` 도 함께 남겨 「왜 없는지」를
   적는다.
3. **앵커 줄 2개**(`P8_STOP=`·`P8_COEXISTENCE=`). P-CA 는 러너가 아티팩트 JSON 을
   파싱하지 않는다는 규율을 `HELD=`·`REFERENCE_ROW=` 로 세웠고, P-8 도 같다.
   `finally` 안에서 찍으므로 예외가 빠져나가는 경로에도 반드시 한 줄씩 나온다.
   기본값은 `unknown` — 분류하지 못한 경로는 러너가 **멈춘다**(fail-closed).

#### 7.15.5 러너 — 두 수를 절대 더하지 않는다

`run_p8.sh` 의 VERDICT 는 네 개의 **별도 필드**다. 09-28 의 「오류 1건(브로커 거부
포함)」이라는 문장을 쓸 수 있는 필드가 존재하지 않는다.

```
VERDICT: <reason> | trials_run=n/N measured=n broker_rejections=n rate_limit_stops=n query_unanswered_stops=n transport_stops=n
```

- `rejected` · `rate_limited` · `query_unanswered` · rc≠0 · 분류 불가(줄 없음 포함)
  ⇒ **시리즈 중단**.
- `transient:*` ⇒ **계속**. `P8_MAX_TRANSIENT_STOPS`(기본값 없는 필수 env)를 넘으면
  그때 멈추고, 그 문구는 「링크가 측정할 만큼 건강하지 않다」이지 「발견」이 아니다.
- `none` + `not_measured` 는 중단도 표본도 **아니다** — WARN 한 줄로 말한다. 그걸
  표본으로 세는 것이 N≥5 게이트를 네 번으로 통과시키는 방법이다.
- 끝에 N≥5 충족 여부를 명시한다. 러너만이 그 슬롯의 개수를 안다.

#### 7.15.6 `_common.sh` — 공유로 간 이유와 그 대가

가드를 복제하지 않은 이유는 이 저장소가 이미 한 번 값을 치렀기 때문이다. 일시 오류
우선순위가 두 벌이던 동안 둘은 **이미 갈라져 있었다**(§7.6 F4). 러너 가드도 같은
종류의 정책이다. `_common.sh` 는 `PCA_*`·`P8_*` 를 **한 글자도 읽지 않는다** —
인스턴스 값은 전부 인자로 받고, 메시지가 인용할 변수 **이름**까지 인자다. 테스트가
그 속성을 고정한다(`_common.sh` 에 `PCA_|P8_` 가 나타나면 red).

대가 셋, 전부 테스트로 메웠다.

- `run_p_ca.sh` 를 축약했다. **로그 문구는 한 글자도 바꾸지 않았고** P-CA 테스트
  전부(295건) 그대로 green 이다. 캠페인 README 가 축자 인용하는 문구가 있다.
- P-CA 의 임시 체크아웃 픽스처 2개가 `_common.sh` 도 복사해야 한다(`_runner_repo`,
  `_worktree_pair`). 복사하지 않으면 함수가 없어 `set -u` 가 엉뚱한 줄에서 죽는다 —
  실제로 그렇게 죽는 것을 보고 고쳤다.
- 자기삭제 가드가 **sourced 파일에도** 걸려야 한다. 거기 있는 파괴적 명령은 러너의
  프로세스에서 돌고, 파일별 검사는 그것을 보지 못한다. `_common.sh` 쪽은 `$0` 이
  awk 줄 하나뿐임을 함께 고정한다(sourced 파일에는 지킬 자기 경로가 없다).
- `_CallPacer` 가 `common.Pacer` 를 상속하면서 페이서의 시계가 `common` 으로 옮겨갔고,
  `test_broker_probes_pacing.py` 의 가짜 시계는 `probes_order` 만 패치하고 있었다.
  **조용히 틀렸다**: 페이서가 진짜 시계를 쓰는 바람에 레이턴시 단언이 아홉 자리 음수가
  됐다. 픽스처가 `common` 도 패치하도록 고치고, 그 이유를 독스트링에 적었다.

#### 7.15.7 수정 전 red 증명

`git archive origin/main` 으로 깨끗한 main 트리를 뽑고 새 테스트 파일만 얹어 돌렸다
(워크트리는 건드리지 않는다). **커밋된 최종 파일로 재측정: 수집 62건 중 61건 red
(FAILED 59 + ERROR 2), pass 0건, skip 1건**(로컬 shellcheck 없음). 즉 **main 에서
초록인 테스트는 하나도 없다**.

⚠ **한 가지 밝혀둘 것**: main 에는 `_P8_STOP_PREFIX`·`_P8_COEXISTENCE_PREFIX`·
`POLICY_VERSION` 이 없어 **import 자체가 수집 오류**가 되고, 그러면 파일 전체가 죽어
아무것도 증명하지 못한다(§7.14.1 이 겪은 그 형태). 그래서 red 측정판에서는 그 세
이름만 `getattr(..., <수정 후 값>)` 으로 바꿨다. 그 외에는 커밋된 파일과 동일하다.

대표적인 red 사유:

| 테스트 | 수정 전 실패 |
|---|---|
| 전송 오류 1회 → 재시도 → 완료 | `requests.exceptions.ReadTimeout` 이 프로브 밖으로 탈출 |
| 전송 오류 2연속 → `transient:transport` | `ConnectionError` 탈출 |
| 제출의 전송 오류는 분류하되 재전송 않음 | `ConnectionError` 탈출(그리고 메시지에 `CANO=1234567890`) |
| 정리 liveness 걷기가 전송 오류 1회를 견딘다 | `assert [] == [True]` — 재시도 기록 0 |
| 429/`EGW00201` 는 여전히 즉시 중단 | `KeyError: 'stop_reason'` + (위 7.15.2 의) 만들어낸 `coexistence_ms` |
| `EGW00215` 2연속 → `transient:ledger_throttle` | `KeyError: 'stop_reason'` + 같은 제조된 값 |
| 창이 지난 뒤의 일시 오류는 재시도 없음 | `KeyError: 'retries'` |
| dry-run 이 자기를 이름 붙인다 | `assert [] == ['dry_run']` |
| 러너 템플릿·시리즈 STOP 규칙 23건 | 파일 부재(`FileNotFoundError`) |

**정직하게**: 429/`EGW00201`·제출 거부 테스트가 red 인 1차 사유는 `stop_reason` 키
부재이고, 「재시도하지 않는다」·「거부는 거부다」라는 **행동 자체는 수정 전에도
옳았다**. 그 두 건은 바뀌지 말아야 할 것을 고정하는 핀이다 — 다만 7.15.2 때문에
완전한 핀은 아니다: `"coexistence_ms" not in measurements` 단언은 실제 결함을 잡는다.

#### 7.15.8 게이트

```
.venv/bin/pytest tests/tools/test_broker_probes_p8_transient.py \
  tests/tools/test_broker_probes_p8_cleanup.py \
  tests/tools/test_broker_probes_ca.py tests/tools/test_broker_probes_pacing.py \
  tests/tools/test_broker_probes_balance.py tests/tools/test_broker_probes_odno.py \
  tests/tools/test_broker_probes_p11_fill.py tests/tools/test_broker_probes_nmpr.py \
  tests/tools/test_broker_probes_tick.py tests/tools/test_broker_probes_real_order.py \
  tests/tools/test_broker_probes_n15_blackout.py \
  tests/tools/test_broker_probes_nontrade_registry.py \
  tests/tools/test_broker_probes_token_cache.py -p no:cacheprovider
  → 680 passed, 2 skipped (로컬 shellcheck 없음; CI 가 돌린다)

ruff check tools/broker_probes tests/tools          → All checks passed!
black --check (변경 .py 전부)                        → unchanged
bash -n run_p8.sh / run_p_ca.sh / _common.sh         → OK
docker koalaman/shellcheck:stable --severity=warning
  다섯 조합(각 파일 단독 3 + 러너별 쌍 2)             → 전부 rc 0  (§7.15.10)
```

#### 7.15.9 남은 것

- **P-8 3~5회차는 이제 선결 조건을 만족한다.** 이 PR 은 **돌리지 않는다** — 실행은
  운영자 결정이고, `P8_SYMBOL` 은 돌리는 날의 근월물이어야 한다.
- `EGW00215` 의 원인(모의 서버 공용 스로틀 가설)은 여전히 관측만 있고 단정하지 않는다.
- **7.15.2 가 과거 아티팩트에 미치는 범위 — 전수 확인했고, 완전히 걷히지는 않는다.**
  커밋된 P-8 아티팩트 10건(07-31 ×5 · 09-11 ×2 · 09-16 ×1 · 09-28 ×2)의
  `coexistence_ms` 는 전부 `0.0`(6건) 또는 키 자체가 없음(4건)이다. **양수는 0건**이므로
  「공존 구간이 거부 응답에 끊겨 잘린 값이 기록된」 형태는 **어느 아티팩트에도 없다**
  (그 형태는 반드시 양수다).

  그러나 `0.0` 이 무죄의 증거는 아니다. 폴 #1 이 거부되면 `coexist_last` 가 끝까지
  `None` 이고 수정 전 코드는 `coexistence_ms: 0.0` — 즉 「원자적 교체를 관측했다」를
  쓴다. 같은 fail-open 방향이고, **아티팩트에 폴별 `rt_cd` 가 없어 이것은 아티팩트만으로는
  판정할 수 없다**. 적어둘 수 있는 것은 두 가지다. (a) 07-31 5건과 09-28 1회차는
  `replace_issues_new_odno=true` 이고 원 주문의 정리 취소가 「정정/취소할 수량이 없습니다」로
  거부됐다 — 그것은 **폴이 아니라 취소 표면**에서 온 독립 증거이고, 09-28 1회차는
  `original_not_cancellable_after_amend=true` 로 그것을 명시한다(07-31 5건은 그 필드가
  `#732` 이전이라 `None`). (b) 새 코드는 멈춘 폴에 값을 쓰지 않고
  `coexistence_polls_used` 를 남기므로, **재개 실측부터는 아티팩트만으로 판정된다**.
  과거 10건의 전수 재판정은 이 PR 범위 밖이며, N≥5 는 어차피 재개 실측으로 채워진다.

#### 7.15.10 CI red 처분 (`test` 잡, run 36953671524) — 그리고 재실행 전원 green

**원인 1건, 그리고 그것이 드러낸 게이트 결함 1건.** 실패한 테스트는 하나뿐이었다 —
`test_runner_template_passes_shellcheck`, 사유 SC2034:

```
run_p8.sh line 51:
PROBE_LOG_FILE=${P8_LOG:-}
^------------^ SC2034 (warning): PROBE_LOG_FILE appears unused.
```

러너가 **쓰고** `_common.sh` 의 `log()` 가 **읽는** 변수다. shellcheck 는 `source` 를
따라가지 않으므로 러너를 혼자 분석하면 읽는 쪽을 못 보고 쓰기를 미사용으로 신고한다.

**게이트 결함이 더 중요하다.** 로컬에서 나는 세 파일을 **한꺼번에** 넘겨 rc 0 을 받았고,
CI 의 P-8 테스트는 **한 파일**만 넘겨 red 가 됐다. 실측해 보니 `run_p_ca.sh` 도 혼자
돌리면 같은 SC2034 로 red 였다 — P-CA 테스트가 두 파일을 함께 넘기고 있어서 가려져
있었을 뿐이다. **입력 파일 수에 따라 판정이 달라지는 것은 게이트가 아니다.**

처분 둘:

1. **교차 파일 변수를 없앴다.** `_common.sh` 가 `set_log_file()` 세터를 제공하고
   전역은 `_PROBE_LOG_FILE` 로 자기 파일 안에만 산다. 억제(`disable=SC2034`)가 아니라
   결합 자체를 제거한 것이고, 결과적으로 「러너가 공유 파일의 전역을 직접 쓴다」는
   숨은 계약도 사라진다.
2. **두 테스트 모두 파일을 하나씩 **그리고** 함께 검사한다**(세 조합). 컨테이너로
   다섯 조합 전부 rc 0 을 실측했다: `run_p8.sh` 단독 · `_common.sh` 단독 · 둘 함께 ·
   `run_p_ca.sh` 단독 · `run_p_ca.sh`+`_common.sh`.

**같은 실행의 `performance` fail 은 이 PR 과 무관했고, 재실행에서 pass 했다.**
유일한 error 는 `test_orchestrator_hot_path_benchmark.py::test_entry_path_100_symbols`
(baseline 0.1329 s → current 0.3055 s, 정규화 +112.7 %). 근거 셋:

1. 그 파일의 import 는 `time`·`sys`·`pytest` 뿐이고, `tests/performance/` ·
   `scripts/performance/` 어디에도 `broker_probes` 참조는 **0건**이다. 이 PR 의 변경
   파일은 전부 `tools/broker_probes/**` · `tests/tools/**` · `docs/**` 다.
2. 같은 잡이 #825(§7.13) · #831(§7.14.4)에서도 fail 했고, main 에서는 아예 **skip**
   된다(잡 조건이 PR 또는 schedule).
3. 결정적으로, **같은 테스트가 이 브랜치에서 fail 과 pass 를 오갔다**. 그 사이
   `tests/performance/` 도 `shared/` 도 한 줄 바뀌지 않았다 — 오간 구간의 변경은
   셸 한 줄과 마크다운뿐이다. fail 쪽 측정값은 baseline 0.1329 s 에 대해
   0.3055 s(+112.7 %)와 0.4784 s(+252.6 %). 즉 이 임계값은 공유 러너의 편차 안에
   있고, **편차의 폭이 임계값(+100 %)보다 크다**.

메모리 `ci-gating-reality` 의 경고대로 **baseline 재생성은 하지 않는다** — 먼저
재생성하면 진짜 회귀가 영구히 안 보이게 된다. 3의 「한 번 fail 한 번 pass」는 baseline
이 현재 러너 편차보다 빡빡하다는 관측이지 회귀의 부재 증명이 아니다.

**CI (`60378385`)**: 8개 전부 pass.

**CI (`31fae3b0`, 라운드 1 처분)**: `performance` 외 7개 pass — 그 하나는 위 3번의
한 데이터 포인트다. **CI (`ecf255c7`)**: 8개 전부 pass. 어느 쪽이든 **실 게이트는
`test` 뿐이고 그것은 두 실행 모두 green 이다**(메모리 `ci-gating-reality`).

#### 7.15.11 리뷰 처분 (PR #841 라운드 1 · 7건 · 기각 0)

| # | 지적 | 처분 |
|---|---|---|
| F1 | 제출·정정 POST 의 전송 실패를 `transient:transport`(시리즈 계속)로 분류하는데 **주문 상태는 알 수 없다**. 책 조사도 없고 `_cleanup` 은 프로브가 본 ODNO 만 취소하므로, 브로커가 실제로 접수한 주문이 고아로 남은 채 러너가 계속 주문을 넣는다 | **수정.** 새 토큰 `order_state_unknown` 으로 **시리즈 중단** + 중단 전 책 전체 조사·미식별 live 행 취소 |
| F2 | 폴이 **0회**인 창도 `stop=none`·`measured=True`·`coexistence_ms: 0.0` 으로 끝난다 — 이 PR 이 닫았다고 말한 바로 그 제조된 0 | **수정.** 측정 게이트를 `answered > 0` 으로 |
| F3 | 정정이 **거부**돼도(새 ODNO 없음) `measured=True`·`coexistence_ms: 0.0` 이고 러너가 N≥5 에 센다 | **수정.** `replace_rejected` 또는 새 ODNO 없음이면 측정 없음·`measured=False` |
| F4 | `transient` 서술이 「창이 안 흘렀다」고 단정하는데 **`can_retry` 가 존재하는 이유인 늦은 전송 오류**에서는 거짓이고, 커밋된 테스트는 그 경로를 타지 않는다(창 0 s) | **수정.** 창 문구를 **사실**에서 뽑고, `not_retried_because` 로 두 거절을 가르고, 실제 늦은-창 테스트 추가 |
| F5 | 레이트리밋 중단은 브로커 증거를 **하나도** 안 남기는데 서술은 「retry_evidence 를 보라」고 한다. `_live_odno_keys` 도 같은 회귀 | **수정.** `coexistence_poll_rate_limited` 기록 + 걷기 증거에 `rt_cd`/`msg_cd`/`msg1`/`http_status` 복원 |
| F6 | 새 폴 루프의 `rt_cd` 검사가 `str(x or '')` — 같은 PR 의 `call_evidence` 가 명시적으로 피한 falsy-zero 오분류 | **수정.** `common.rt_cd_of()` 한 벌, `call_evidence` 도 그것을 쓴다 |
| F7 | `P8_INTER_TRIAL_S` 만 검증되지 않아 나쁜 값이면 `sleep` 이 실패하고 다음 트라이얼이 간격 없이 바로 나간다 | **수정.** 다른 수치와 같은 자리에서 검증 |

**F1 이 가장 위험했고, 지적이 옳았다.** 수정 전 코드는 「POST 는 재시도하지 않는다」를
**안전 조치**로 적었는데, 재시도하지 않는 것과 **결과를 모르는 것**은 다른 문제였다.
`ReadTimeout` 이 말하는 것은 답이 오지 않았다는 것뿐이고, 브로커는 주문을 접수해 지금
걸어두고 있을 수 있다 — 프로브가 본 적 없는 ODNO 로. 그러면 `odnos` 는 비어 있고
`_cleanup` 은 아무것도 취소하지 않으며, 러너는 `transient:transport` 를 읽고 그 위에
다음 주문을 올린다. **이 PR 이전에는 예외가 새어 rc 5 로 시리즈가 멈췄으므로, 이
지점에 한해 내 수정이 원래 코드보다 느슨했다.**

경계는 「POST 인가」가 아니라 **「주문의 상태를 모르는가」**다. 시세 조회는 GET 이고
그 시점엔 아무것도 걸려 있지 않으므로 여전히 `transient:transport`(계속)다. 제출·정정은
`order_state_unknown`(중단) 이고, 중단 **전에** `_cleanup_unaccounted` 가 `_cleanup`
뒤에 돌아 책 전체를 걷고 이 시행이 설명할 수 없는 live 행을 취소한다. 세 결과를 전부
`measurements.unaccounted_live_orders` 에 적는다 — `FOUND` · `NONE_FOUND` ·
`UNDETERMINED`. 「걷기가 돌았고 책이 깨끗했다」와 「걷기가 없었다」는 다른 사실이고,
전자만이 운영자에게 그만 찾아도 된다고 말한다. 답하지 못한 걷기는 **아무것도 취소하지
않는다**(`_CLEANUP_LIVENESS_NOTE` 와 같은 극성).

**F1 이 끌고 나온 것 하나 더 — 취소 ODNO 의 형태.** 고아 행은 **조회 표면**에서만
보이는데, 조회는 공백 패딩이고 취소가 받아들여진 것으로 **측정된** 형태는 접수 응답의
0 패딩이다(`P-8-20260928T000506Z:odno_wire_format`, 양쪽 길이 10). 접수 응답이 없는
행이므로 `_cancellable_odno()` 가 행의 폭에 맞춰 0 으로 **재구성**하고, 관측된 형태와
보낸 형태를 **둘 다** 아티팩트에 적는다 — 재구성이지 관측이 아니기 때문이다. 틀리면
`_cancel_one` 이 `REJECTED_AND_STILL_LIVE` 로 시끄럽게 실패한다. ⚠ 이 과정에서
**테스트 fake 가 조회 행을 11자로 패딩하고 있던 것**을 발견해 아티팩트대로 10자로
고쳤다 — 폭이 틀린 fake 위에서는 재구성이 통과해도 아무것도 증명하지 못한다.

**F2·F3 은 같은 구멍의 두 입구다.** 「멈추지 않았다」를 「측정했다」로 읽고 있었다.
이제 셋 중 하나라도 해당하면 측정을 쓰지 않는다: 정정 거부 · 새 ODNO 없음 ·
`answered == 0`. 그리고 셋 다 `stop=none` 이므로 **시리즈는 계속**한다 — 멈출 이유는
아니고, 셀 이유도 아니다. 러너는 이미 `none`+`not_measured` 를 WARN 으로 말한다.

**F4 는 §7.15.10 이 고친 것과 같은 형태가 한 겹 아래 남아 있던 것이다.** 창 문구를
사유별 상수로 묶었더니 **같은 사유 안에서 사실이 갈리는 경우**를 놓쳤다. 이제 창 문구는
`_window_note(elapsed, window_s)` 가 **런타임 사실**에서 뽑는다. 덤으로 `retry_once` 가
`not_retried_because` 를 남겨 「두 번 연속 실패」와 「창이 이미 닫혀 거절」을 가른다 —
둘 다 `retried: false` 였고, 링크 건강도를 세는 판독자가 그 둘을 더하면 안 된다.

**수정 전 red 증명.** 리뷰 시점 HEAD(`a3f39ede`)에 새 테스트 파일만 얹어 돌렸다:
**18건 red**. 일곱 지적 전부 최소 1건씩 덮는다.

| 테스트 | `a3f39ede` 에서의 실패 |
|---|---|
| 잃어버린 제출이 시리즈를 멈추고 고아를 취소한다 | `assert 'transient:transport' == 'order_state_unknown'` |
| 잃어버린 정정이 알려진 원본을 고아로 세지 않는다 | 같음 |
| 답 못한 걷기는 취소 0 + 「손으로 확인」 | `KeyError: 'unaccounted_live_orders'` |
| 열리지 않은 창은 아무것도 측정하지 않는다 | `assert 'coexistence_ms' not in {…}` |
| 거부된 정정은 공존을 측정하지 않는다 | 같음 |
| 늦은 전송 오류는 「창이 흘렀다」고 적는다 | skip 사유가 `did NOT elapse` |
| 레이트리밋 중단이 가리키는 봉투를 남긴다 | `assert 0 == 1`(기록 0건) |
| 숫자 `0` 인 `rt_cd` 는 건강한 답이다 | `assert 1 == 0`(답을 거부로 셈) |
| `order_state_unknown` 이 시리즈를 멈춘다 | VERDICT 에 그 필드 없음 |
| `P8_INTER_TRIAL_S` 검증 4건 | 가드 부재 |

red 가 **아닌** 것 둘과 이유: `test_the_quote_phase_still_continues_because_nothing_is_resting`
(시세 경로는 의도적으로 안 바뀐다 — 경계가 「POST 인가」가 아님을 고정하는 핀) ·
`test_runner_accepts_a_plain_inter_trial_gap`(가드가 정상 값을 막지 않는지 보는 역방향).
`test_a_transport_stop_is_still_the_one_that_continues` 는 red 지만 사유는 새 VERDICT
필드의 부재이고, **「폴 전송 중단은 계속한다」는 행동 자체는 수정 전에도 옳았다** —
F1 이 그것을 삼키지 않았는지 보는 핀이다.

**라운드 1 게이트.**

```
.venv/bin/pytest (브로커 프로브 13파일) -p no:cacheprovider
  → 701 passed, 2 skipped (로컬 shellcheck 없음; CI 가 돌린다)
ruff check tools/broker_probes tests/tools → All checks passed!
black --check                              → unchanged
bash -n ×3                                 → OK
docker koalaman/shellcheck:stable --severity=warning, 각 파일 단독 3 + 쌍 2 → 전부 rc 0
```

#### 7.15.12 리뷰 처분 (PR #841 라운드 2 · 8건 · 기각 0)

| # | 지적 | 처분 |
|---|---|---|
| F1 | `P8_COEXISTENCE=measured` 를 로컬 플래그에서 찍고 `run.errors` 와 대조하지 않아, 아티팩트가 NOT_MEASURED 인 시행을 러너가 N≥5 에 센다 | **수정.** `measured and not run.errors` |
| F2 | 제출·정정 응답이 `classify_answer` 를 안 탄다 — 정정의 레이트리밋은 **보이지 않고**(폴링 계속, 다음 주문 발사), 제출의 레이트리밋은 **브로커 거부로 서술**된다 | **수정.** verbose 변형으로 status·text 를 받아 분류. 429/`EGW00201` ⇒ `rate_limited` 중단, `EGW00215` ⇒ `order_state_unknown`(책 조사) |
| F3 | 창이 닫혀 거절된 **단발** 일시 오류를 2연속과 같은 `transient:<kind>` 로 돌려줘, 다 쓴 창을 무효화하고 링크 건강 예산에 청구한다 | **수정.** `attempts == 1` 이면 자연 종료(`stop=None`), 표본이 있으면 유지 |
| F4 | 러너가 `query_unanswered` 에 시리즈를 멈추는데, 프로브가 단발 `rt_cd≠0` 에 안 멈추는 **바로 그 근거**가 「빈 장부 표기일 수 있다」였다 | **수정.** 창 전체가 빈-장부 코드(`KIOK0560`)뿐이면 자연 종료, 다른 코드가 하나라도 섞이면 중단 |
| F5 | `_cleanup_unaccounted` 가 이 시행이 놓지 않은 **모든** qty>0 행을 취소한다 — 공유 모의 계좌에서 다른 프로브나 운영자의 주문을 지운다 | **수정.** 본문 대조 + 옵트인. 아래 |
| F6 | `_record_write_transport_stop` 가 `retried=False` 만 적고 `not_retried_because` 가 없다 — 새 필드가 없애려던 바로 그 모호한 기록 | **수정.** `REFUSED_SINGLE_SHOT` |
| F7 | README 토큰 집합에 `order_state_unknown`·`query_unanswered` 가 빠졌다 | **수정.** 코드펜스·표·`P8_CANCEL_UNACCOUNTED` 모두 |
| F8 | `_cancel_one` 의 `live_keys` 주석이 `set[str] | None` 인데 실제는 dict — 주석이 거짓말이고 mypy 가 잡는다 | **수정.** 행 전체를 담도록 `dict[str, dict[str, Any]] | None` |

**F5 가 가장 위험했고, 내가 라운드 1 에서 만든 것이다.** F1 을 고치면서 「고아를
치운다」를 **「설명되지 않는 live 행을 전부 취소한다」**로 썼다. 이 모의 계좌는 캠페인
전체가 공유한다 — P-5·P-11·P-EXT 나 운영자 MTS 주문이 같은 종목에 걸려 있으면 그것을
지우고 「잃어버린 호출이 남긴 주문」이라고 적었을 것이다. **다른 측정을 조용히
파괴하는 코드를 안전 조치라고 불렀다.**

처분은 두 겹이고 둘 다 되돌릴 수 없는 쪽을 막는다.

1. **본문 대조.** 이 시행의 주문 본문과 맞지 않는 행은 `foreign_live_rows_present` 로
   **기록만** 하고 손대지 않는다 — 플래그로도 못 넘는다.
2. **옵트인.** 맞는 행조차 `--cancel-unaccounted`(러너의 `P8_CANCEL_UNACCOUNTED=1`)
   없이는 취소하지 않는다. 기본은 기록하고 멈추기이고, 아티팩트에
   `cancel_odno_would_send` 가 남아 운영자가 손으로 한다. **운영자가 아는 고아는 한정된
   문제이고, 취소된 남의 주문은 아니다.**

**대조 기준을 정직하게 적는다.** 이 표면에서 런타임이 실제로 읽는 필드는
`odno`·`ord_qty`·`qty`·`tot_ccld_qty`·`avg_idx` 뿐이고(`executor.py` 의 행 파싱,
`probes_real_order.classify_fill` 이 같은 집합을 인용), **주문 가격과 매도매수구분의
필드명은 이 저장소 어디에도 측정돼 있지 않다**. 그래서 매처는 행이 그 이름을 **가지고
있을 때만** 검사하고, 무엇을 검사했고 무엇을 행이 안 실어왔는지를
`match_criteria` 에 적는다. 이름을 **추측**하는 것이 더 나빴을 것이다 — 대조가 조용히
한 번도 성립하지 않고, 아무것도 막지 않는 가드가 된다(이 저장소가 네 번 겪은 형태).

**F2 는 내가 「POST 는 분류만 한다」고 쓰면서 분류를 안 한 것이다.** 라운드 1 의 문장은
「분류야말로 09-28 에 없던 것」이었는데, 정작 `classify_answer` 는 폴에만 걸려 있었다.
이제 두 POST 다 탄다. `EGW00215` 를 `order_state_unknown` 으로 보내는 것은 한 칸 보수적인
선택이다 — 스로틀은 **답**이므로 엄밀히는 접수되지 않았지만, 틀렸을 때 live 주문이 남는
유일한 표면에서 「엄밀히」에 기대지 않는다. 책 조사 한 번이 싸다.

**F3·F4 는 같은 질문의 두 형태다 — 「이것이 정말 중단인가」.** 창이 닫혀 거절된 단발
전송 오류는 **창이 끝난 것**이고(루프는 다음 바퀴에 어차피 끝났다), 창 전체가 빈-장부
코드인 것은 **장부가 빈 것**이다(체결이거나 터치에 너무 가까운 지정가). 둘 다 멈출
이유가 아니고, 멈추면 이 PR 이 없애려던 과잉 중단을 새로 만든다.

**수정 전 red 증명.** 라운드 1 HEAD(`c2e68a30`)에 새 테스트 파일만 얹어 돌렸다:
**16건 red**. 여덟 지적 전부 최소 1건씩 덮는다.

| 테스트 | `c2e68a30` 에서의 실패 | 지적 |
|---|---|---|
| 옵트인 없이는 취소하지 않는다 | `assert 'FOUND' == 'FOUND_NOT_CANCELLED'` | F5 |
| 남의 행은 플래그로도 안 건드린다 ×3(수량·방향·가격) | `KeyError: 'foreign_live_rows_present'` | F5 |
| 적용한 대조 기준을 적는다 | `KeyError: 'match_criteria'` | F5 |
| 옵트인이 요청될 때만 프로브에 닿는다 | `--cancel-unaccounted` 미전달 | F5 |
| 잃어버린 제출/정정 보고 ×2 | 같은 `FOUND` vs `FOUND_NOT_CANCELLED`, `KeyError: 'not_retried_because'` | F5·F6 |
| 정리 오류가 N≥5 계수를 막는다 | `assert ['measured'] == ['not_measured']` | F1 |
| 레이트리밋 제출이 거부로 서술되지 않는다 | `assert 'rejected' == 'rate_limited'` | F2 |
| 레이트리밋 정정이 폴링하지 않고 멈춘다 | 같은 계열 | F2 |
| 원장 스로틀 정정이 책을 걷는다 | 같은 계열 | F2 |
| 늦은 단발 전송 오류는 자연 종료 | `assert 'transient:transport' == 'none'` | F3 |
| 빈 장부 창은 시리즈를 멈추지 않는다 | `assert 'query_unanswered' == 'none'` | F4 |
| 러너가 분기하는 토큰이 README 계약에 있다 | 코드펜스에 두 토큰 없음 | F7 |
| liveness 걷기가 행을 돌려준다 | `assert 'dict[str, dict[str, Any]] \| None' in 'tuple[dict[str, str] …'` | F8 |

⚠ F7 은 **처음 쓴 테스트가 결함을 못 잡았다**. 토큰이 README 어딘가에 있으면 통과하도록
썼는데, 라운드 1 에서 **표**에는 이미 두 토큰이 있었고 빠진 것은 그 위의
`P8_STOP=<…>` **코드펜스**였다 — 운영자가 먼저 읽는 쪽이다. 펜스를 파싱해 러너의 case
arm 과 대조하도록 좁히고 나서야 red 가 됐다. 가드가 자기가 막는다고 말한 것을 통과시키는
형태를 또 한 번, 이번엔 테스트에서 했다.

**라운드 2 게이트.**

```
.venv/bin/pytest (브로커 프로브 13파일) -p no:cacheprovider
  → 716 passed, 2 skipped (로컬 shellcheck 없음; CI 가 돌린다)
ruff check tools/broker_probes tests/tools → All checks passed!
black --check                              → unchanged
mypy tools/broker_probes/probes_order.py --ignore-missing-imports
  --explicit-package-bases                 → 16 (origin/main 기준 18; 남은 것은 전부
                                             다른 프로브의 기존 `output1` Any 패턴)
bash -n ×3 · docker shellcheck 각 파일 단독 3 + 쌍 2 → 전부 rc 0
```
