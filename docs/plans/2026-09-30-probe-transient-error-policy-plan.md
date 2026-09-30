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

(구현 PR 에서 채운다.)
