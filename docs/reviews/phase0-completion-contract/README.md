# Phase 0 완료 계약 — 심판 판정 기록 (추적 보존 정본)

이 디렉터리는 `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`
(및 결속 문서 `2026-08-11-tos-completion-development-plan.md`) 심사 아크의
**판정 기록 보존 정본**이다.

## 출처와 보존 근거

- 판정 기록의 운영 홈은 `.omc/review/<timestamp>/` — codex-gate 가 판정을
  **기록하고 재심 체인(직전 스탬프 탐색·`prior_verdict` 해석)을 잇는** 위치다.
  `.omc/` 가 digest 범위 밖인 것은 의도된 설계다(기록 행위가 심사 대상 digest 를
  바꾸면 기록하는 순간 자기 자신을 무효화한다).
- 그러나 `.omc/` 는 `.gitignore` 대상이라 **clean checkout 과 다른 운영자에게
  전달되지 않는다** — 레인 B v2.5 판정 finding #6 (medium, 채택)이 이것을
  "기록 보존 방식의 결함"으로 등재했고, 운영자가 2026-08-13 추적되는 위치
  보존으로 처분했다.
- 이에 따라 아크 전체 기록(레인 B 계획 심판 + 레인 A 코드 심판)의
  **byte-동일 사본**을 이 위치에 커밋한다. 내용 편집 없음.
- **사본이지 이동이 아니다** — 초판 처분은 이동이었으나, 이동이 `.omc/review/`
  의 재심 체인(codex-gate 의 직전 스탬프 탐색과 기존 판정문의 `prior_verdict`
  경로 해석)을 끊는다는 stop-time 심판 지적으로 **운영 원본 유지 + 추적 사본
  보존**으로 교정했다. 두 사본은 byte-동일하며, 검증은:

  ```bash
  diff -r --exclude=README.md --exclude=U15-ENTRY-CHECK.md \
    --exclude=U16-LEDGER-CHECK.md \
    .omc/review docs/reviews/phase0-completion-contract
  ```

  (`U15-ENTRY-CHECK.md`·`U16-LEDGER-CHECK.md` 는 **추적 전용 실행 증거**라 운영
  원본이 없다 — 아래 "실행 증거 아티팩트" 절. 제외 목록은 이 README 가 유일 소스다.)

## 두 위치의 역할

| 위치 | 역할 | 추적 |
|---|---|---|
| `.omc/review/<ts>/` | 운영 체인 — codex-gate 기록·재심 연속성 | gitignore (의도) |
| `docs/reviews/phase0-completion-contract/<ts>/` | **보존 정본 — 문서가 인용하는 추적 경로** | git |

문서·계획의 **활성 포인터는 추적 경로를 인용**한다. 기록은 불변이므로 두 위치가
갈라질 수 없고, 갈라졌다면 그것 자체가 결함이다(위 diff 로 판별).

## 경로 사상 규칙

기록 본문·계획 문서 이력이 인용하는 `.omc/review/<ts>/…` 는 전부

```
.omc/review/<ts>/…  ↔  docs/reviews/phase0-completion-contract/<ts>/…
```

로 상호 해석한다. 판정 파일 내부의 상호 참조(`prior_verdict` 등)는 **역사적
사실이므로 고치지 않는다** — 운영 위치에서는 그대로 해석되고, clean checkout
에서는 이 사상 규칙이 해석을 담당한다.

## 수록 범위 (31건)

- `20260812-055252` … `20260812-231234` — 레인 B 계획 심판 v1.0~v2.3
  (055252 는 판정 불능 fail-closed 기록 — 게이트를 열지 않는 기록도 보존한다)
- `20260813-075200` … `20260813-180752` — 레인 A 코드 심판 (프로토타입,
  게이트 미통과로 종결 — 정본 `20260813-180752/verdict.md`)
- `20260813-205553` — 레인 B v2.5 판정 (`needs-attention`·`NOT_PASSED`,
  findings 6 전건 채택 — v2.6 개정의 입력)
- `20260813-233530` — 레인 B v2.6 재심 (`needs-attention`·`NOT_PASSED`,
  직전 6건 해소 3·부분해소 3·"문구만" 0, 신규 high 3 전건 채택 — v2.7 개정의 입력)
- `20260814-110807` — 레인 B v2.7 재심 (`needs-attention`·`NOT_PASSED`,
  직전 3건 전건 부분해소·"문구-only 아님" 명시, 잔여 우회 high 3 전건 채택 —
  부트스트랩 순환·merge DAG 비유일성·승인-내용 미결속. v2.8 개정의 입력.
  U-15 실행 증거 `U15-ENTRY-CHECK.md` 가 이 스탬프에 귀속)
- `20260814-160239` — 레인 B v2.8 재심 (`needs-attention`·`NOT_PASSED`,
  직전 3건 = **해소 1(#2 merge-DAG — 아크 최초)**·부분해소 2, 잔여 high 2
  전건 채택 — 레시피의 판정 기계화 부재·reviewer 시점 blob 미결속.
  v2.9/v2.10 개정의 입력. v2.10 하니스 실행 증거 `U15-ENTRY-CHECK.md` 귀속)
- `20260815-040451` — 레인 B v2.10 재심 (`needs-attention`·`NOT_PASSED`,
  직전 2건 = **U-16 시점-blob 해소됨(아크 두 번째)**·U-15 부분해소, 잔여
  high 2 전건 채택 — 착수 표면 미결속·U-16 merge-DAG 비유일. v2.9는 동결
  직후 stop-time 적발로 심사 미도달. v2.11 개정의 입력. v2.11 가드 억제
  실행 증거 `U15-ENTRY-CHECK.md` 귀속)
- `20260815-092111` — 레인 B v2.11 재심 (`needs-attention`·`NOT_PASSED`,
  직전 2건 전건 부분해소·"문구만 아님", 신규 high 2·medium 1 전건 채택 —
  대리 행위 억제(실제 D0-A 최초 행위 미명명)·U-16-c 단수 본체와 a2 전칭의
  병존·K-14 미매핑 레벨 대조군 부재. v2.12 개정의 입력. v2.12 실제-행위
  억제 실행 증거 `U15-ENTRY-CHECK.md` 귀속)
- `20260815-102037` — 레인 B v2.12 재심 **시도 — 판정 불능 fail-closed 기록**
  (`adjudicator: null`·`verdict: null`. Codex 계정 쿼터 소진 — 1차·범위축소
  2차 동일 실패, 리셋 2026-08-20 12:33. 리비전 결속값은 포착·불변 확정 —
  쿼터 회복 후 동일 digest 로 재심 재개 가능. 055252 선례와 같은 "게이트를
  열지 않는 기록")
- `20260815-144959` — 레인 B v2.12 재심 (**크레딧 충전 후 재개** —
  `needs-attention`·`NOT_PASSED`, 직전 3건 = **해소 2(U-16 전칭 통일·
  K-14/T-83 — 누적 4)**·#1 부분해소, 신규 high 2·medium 1 전건 채택 —
  비가드 착수+HEAD 동시성·reviewer→승인 조상 순서 미강제·원장 스키마의
  간선 결정성 부재. 다음 개정의 입력)
- `20260818-224729` — 레인 B v2.13 재심 (`needs-attention`·`NOT_PASSED`,
  직전 3건 = **전건 부분해소**(신규 해소 0·회피 0·신규 결함 클래스 0), high 2·
  medium 1 전건 채택 — CORR(d) 사후 transcript 세탁(d 동일성·생성 순서 미검사)
  +§11 행 ENTRY_OK 미전파·g6 `c_R` 이 경로 최초 도입이라 기존-경로 B∥A 변종
  누락·edge_seq 병렬 충돌 재부여 append 가 자기 MALFORMED 규칙과 모순. 세 축
  전부 "소비 규칙 정밀도 + 실제 소비자 실행 증거" 로 수렴. 다음 개정의 입력.
  `evidence/focus.txt` 는 포워더가 남긴 **심판 입력물**(focus text)의 byte-동일
  사본 — 판정이 아니라 심판이 읽은 지시문이며 diff 불변식 유지를 위해 함께 보존)
- `20260819-002145` — 레인 B v2.14 재심 (`needs-attention`·`NOT_PASSED`,
  직전 3건 = #1 부분해소·#2 부분해소·**#3 회피(아크 최초)** — 손 실행 부속이
  U-16-c 조상성을 빼고 tombstone-graph 만 실행해 양성을 주장(머지 후 재부여 행은
  과거 간선의 조상이 될 수 없어 APPROVAL_AFTER); 신규 high 1(복수 D0A-FIRST 도입
  카디널리티 미규정)·medium 1(row_ref 의 c_APP 비단수). high 3·medium 2 전건 채택.
  #1 은 정직 경계를 "과장 철회일 뿐 해소 아님"으로 계수 + 처분표 :4256-4267 초안
  문구 미전파(S-22 7회차) · #2 는 digest 선배치 변종(C_R 이 토큰 도입만 추적).
  다음 개정의 입력. `evidence/focus.txt` 동일 규칙으로 보존)

## 실행 증거 아티팩트 (추적 전용 — 스탬프 내 sibling)

계약 문서 §12.3.4 가 규정한 실행 증거(`U15-ENTRY-CHECK.md` 등)는 **그 증거가
소비한 verdict 의 스탬프 디렉터리 안에**(이 추적 디렉터리 쪽) verdict.md 의
sibling 으로 둔다 — 계약의 `<ts>/U15-ENTRY-CHECK.md` 경로 그대로이며, verdict.md
는 불변이고 sibling 추가만 허용된다.

**`.omc/review/` 쪽에는 미러하지 않는다 — `.omc` 스탬프는 불가침이다.**
codex-gate 의 직전 판정 탐색이 `ls -1dt`(mtime 순)라 스탬프 디렉터리에의
사후 쓰기는 탐색 순서 자료를 오염시킨다(옛 스탬프에 쓰면 그것이 "직전 판정"으로
승격된다). 이 규칙은 stop-time 심판 2회 적발(경로 이탈 → 미러 오염)의 산출물이며,
연대기는 transcript 말미 관측에 있다. 따라서 diff 불변식은 증거 파일명을
명명 제외한다(위 검증 명령).

- `20260814-110807/U15-ENTRY-CHECK.md` — U-15 «진입 점검 레시피» 실행 증거
  (v2.7 재심 next_steps "실제 진입을 거부하는 실행 증거"의 이행 —
  FREEZE_VIOLATED·T-81-① 양성/음성 쌍·REBINDING_REQUIRED 3-run transcript.
  RH 를 이 스탬프의 verdict 에서 소비했으므로 여기에 귀속.
  **상태값은 사람 해석·exit 0** — v2.8 재심이 이를 결함으로 적발했고
  다음 항이 그 교정의 증거다)
- `20260814-160239/U15-ENTRY-CHECK.md` — **v2.10 판정 하니스** 실행 증거
  (v2.8 재심 Recommendation "비정상 종료로 진입을 차단한 실행 결과"의 이행 —
  4-run 전부 **프로그램 산출 상태값 + rc=1**: 양성 REBINDING_REQUIRED ·
  음성-1 변이[우선순위 차폐] · 음성-2 전제 충족 모의 후 **APPROVAL_STALE**
  [커밋-전용 읽기 하에서도 R-7 비-사코드] · **음성-3 봉합 실증** — v2.9
  하니스라면 ENTRY_OK/rc=0이었을 미커밋 권위 위조가 FREEZE_VIOLATED/rc=1로
  차단[위조물 2건 열거]. 하니스 실행본 == 동결본 `4fb03470` byte-동일 결속.
  **구판(v2.9 하니스 3-run)은 커밋 `2b6f5eeb`에 보존** — stop-time 적발된
  미커밋 권위 위조 결함으로 대체, supersession 헤더 수록)

- `20260815-040451/U15-ENTRY-CHECK.md` — **v2.11 가드 억제** 실행 증거
  (v2.10 재심 Recommendation "하니스 비정상 종료 시 D0-A 작업이 실행되지
  않는 결과"의 이행 — U-15-e (5) 첫 수록: **G-음성** 차단 상태에서
  `guard_rc=1`·`D0A-STARTED` 부재(`+ touch` 미도달 트레이스) / **G-양성**
  SIMULATED 2-커밋 모의 후 `ENTRY_OK`·`guard_rc=0`·파일 존재. «전제 차이»
  규칙 첫 적용(현 상태 R-2 미충족 실측 → 1-커밋 최소 전제 불성립 → 2-커밋
  정정 구성) 기록. 하니스 == 동결본 `e582c01a` byte-동일 결속)

- `20260815-092111/U15-ENTRY-CHECK.md` — **v2.12 실제-행위(D0A-FIRST) 억제**
  실행 증거 (v2.11 재심 Recommendation "실제 D0-A 최초 실행 표면에서의 억제
  증거"의 이행 — 우변이 대리(`touch`)가 아니라 **`config/tos_completion.yaml`
  도입 커밋 그 자체**: G-음성 차단 상태에서 `guard_rc=1`·파일 및 `--diff-filter=A`
  도입 커밋 **양쪽 부재**(`+ eval` 미도달) / G-양성 post-freeze 2-커밋 모의 후
  `ENTRY_OK`·`guard_rc=0`·실제 도입 커밋 생성[worktree 한정·무참조].
  «전제 차이» 동결-상대화 표의 post-freeze 예측 첫 검증. 하니스 == 동결본
  `cf9b0295` byte-동일 결속. 본 저장소 D0-A 미착수 불변 확인 포함)

- `20260815-144959/U15-ENTRY-CHECK.md` — **v2.13 T-81 ⑬⑭⑮** 실행 증거
  (v2.12 재심 next_steps "비가드·HEAD 변경 억제를 실제 소비자 대조군으로"의
  이행 — **⑬** 하니스 ENTRY_OK 후 HEAD 이동 → `parent(d) ≠ R-0 head` =
  PARENT_MISMATCH 기계 관측 / **⑭** 비가드 착수 → CORR(d) 공집합 =
  **TRANSCRIPT_MISSING 실제 도달**(초안 반증 ① 봉합) / **⑮** 전진-머지 우회
  재현 → 기존 transcript의 기록 상태가 REBINDING_REQUIRED라 조건 (3) 불충족 =
  **차단**(초안이라면 ENTRY_PROVENANCE_CLEAR 통과였을 구성 — 반증 ② 봉합).
  CORR 손 실행 전문·하니스 == 동결본 `8a25c3c0` byte-동일 결속)

- `20260818-224729/U15-ENTRY-CHECK.md` — **v2.14 T-81 ⑫⑬⑭⑮⑯⑰⑱** 실행 증거
  (v2.13 재심 소비 스탬프 귀속. U-15-g-4b 사양 손 실행기 — 7값 프로그램 방출·rc
  극성·trap EXIT·(4c)(4c-2) 형식 검증·(파일,run) 쌍 — 로 **⑫ 양성** 트레일러 3줄
  포함 D0A-FIRST → `ENTRY_PROVENANCE_CLEAR`/0 실제 도달 / **⑬** PARENT_MISMATCH /
  **⑯⑰ⓐⓑⓒ** ENTRY_TRAILER_MALFORMED / **⑱** TRANSCRIPT_NOT_ENTRY_OK / H6 경계 2종
  TRANSCRIPT_MISSING / ⑭⑮ v2.14 회귀 = ENTRY_TRAILER_MALFORMED[§8 ⑭ 행 리터럴
  `TRANSCRIPT_MISSING` 과의 불일치 보고 수록]. 하니스 == 동결본 `db19a0e8`
  byte-동일(`957bf49d…`). 본 저장소 손 실행기 적용 `NOT_STARTED`/0)
- `20260818-224729/U16-LEDGER-CHECK.md` — **v2.14 T-82 ⑮·⑰ⓐⓑⓒ·⑱ + (iii)(v)(H5-②)**
  손 실행 기록 (**비규범 부속** — 계약이 U-16 증거 아티팩트 경로를 규정하지 않아
  같은 스탬프에 sibling 으로 둠. g6 구조 `C_R(c)`+존재 증인 실행기: ⑰ⓐ `C_R={B}` red ·
  ⑰ⓑ 머지 해소 도입 `C_R={M}` red · ⑰ⓒ 양성 `C_R={B1,B2}` 증인 B1 green · ⑮ 회귀 red /
  tombstone-graph 원장 실행기: ⑱ 병렬 seq=1 MALFORMED → Z1/Z2 supersedes append →
  NO_ROWS_CLEAR·구 행 잔존·g5 동일 · (v) 경쟁 재부여 MALFORMED → Zc 재-supersede 복구 ·
  (iii) 순환 시도 → 부재 행 지목 MALFORMED · H5-② 비단사 MALFORMED. 픽스처는 scratchpad
  독립 git 저장소)

- `20260819-002145/U15-ENTRY-CHECK.md` — **v2.15 T-81 ⑫⑬⑭⑮⑯⑰⑱⑲ + T-84 ①②③④** 실행 증거
  (v2.14 재심 소비 스탬프 귀속. U-15-g-4b **8값·전순서 7단** 손 실행기 — 판정 우주 = 집합
  `D`·`|D|>1 → MULTIPLE_INTRODUCTIONS` CORR 이전 방출 — 로 **⑲ gu/uu** 병렬 도입 머지 →
  `MULTIPLE_INTRODUCTIONS`/1 · **⑫ 양성** CLEAR/0 · ⑬ PARENT_MISMATCH · ⑭⑮⑯⑰ⓐⓑⓒ
  ENTRY_TRAILER_MALFORMED · ⑱ TRANSCRIPT_NOT_ENTRY_OK · H6 2종 TRANSCRIPT_MISSING /
  **U-17 실행기**(4값·`∀d∈D: P ⊰ d`·D=∅ 명시 통과) T-84 ① ABSENT · ②(i·ii) UNSIGNED ·
  ③ ACTIVE/0 · ④ LATE + 부속(D=∅ ACTIVE · |D|=2 한쪽만 앞섬 LATE). **관측 보고**: ⑲ gg
  (guarded∥guarded·byte-동일 내용) 는 `--diff-filter=A` 이력 단순화가 `|D|=1` 로 접어
  **CLEAR/0** — `--full-history` 대조 2건 → U-15-g-1 `D` 우주의 플래그 의존 = 계약 결함
  후보(고치지 않고 보고). 하니스 == 동결본 `11a56d3e` byte-동일(`957bf49d…`). 본 저장소
  NOT_STARTED/0 · PREVENTION_ABSENT/1 · 현행 하니스 REBINDING_REQUIRED/1)
- `20260819-002145/U16-LEDGER-CHECK.md` — **v2.15 T-82 ⑱(전 규칙)·⑯·⑰ⓐⓑⓒ·⑲·⑮ + 자인 잔여**
  손 실행 기록 (**비규범 부속** — sibling. **S-23 전 규칙 실행기**: `rules_executed=` 11 규칙
  방출·차집합 비면 green 금지 잠금. ⑱ edge_seq 필드 없이 X∥Y → **NO_ROWS_CLEAR**/0(append 0·
  v2.14 «회피» 자리 재실증) · ⑯ green · ⑰ⓐ blob `C_R={B}` ORDER_INVALID · ⑰ⓑ **h 선발화
  APPROVAL_UNBOUND**(g6 단독 뷰 `C_R={M}` ORDER_INVALID — 행 서술 `C_R={M}` 은 토큰 정의
  잔존, 보고) · ⑰ⓒ green · ⑲ 선배치 blob `C_R={B}` ORDER_INVALID(v2.14 토큰 대조 = 우회
  통과였음) · ⑮ red · 자인 잔여 단일 행 두 간선 덮음 NO_ROWS_CLEAR(계약 정직 표기 정합).
  픽스처는 scratchpad 독립 git 저장소)

## 향후 관행

판정은 종전대로 `.omc/review/` 에 기록되고(digest 범위 밖 기록 원리·재심 체인
유지), **판정 방출 후** byte-동일 사본을 이 디렉터리에 추가해 커밋한다.
사본 추가는 편집을 동반하지 않는다.
