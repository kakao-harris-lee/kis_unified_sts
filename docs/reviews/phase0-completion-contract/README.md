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
    --exclude=U16-LEDGER-CHECK.md --exclude=U15-ENTRY-CHECK-ADDENDUM.md \
    --exclude=U17-PREVENTION-CHECK.md --exclude=U15-ENTRY-CHECK-V216.md \
    --exclude=U17-PREVENTION-CHECK-V217.md --exclude=U17-PREVENTION-CHECK-V218.md \
    --exclude=U17-PREVENTION-CHECK-V218-ADDENDUM.md \
    --exclude=U17-PREVENTION-CHECK-V219.md --exclude=U16-LEDGER-CHECK-V219.md \
    --exclude=U17-PREVENTION-CHECK-V219-ADDENDUM.md --exclude=U17-PREVENTION-CHECK-V219-ADDENDUM-2.md \
    --exclude=U17-PREVENTION-CHECK-V219-ADDENDUM-3.md \
    .omc/review docs/reviews/phase0-completion-contract
  ```

  (`U15-ENTRY-CHECK.md`·`U16-LEDGER-CHECK.md`·`U15-ENTRY-CHECK-ADDENDUM.md`·
  `U17-PREVENTION-CHECK.md`·`U15-ENTRY-CHECK-V216.md`·`U17-PREVENTION-CHECK-V217.md`·
  `U17-PREVENTION-CHECK-V218.md`·`U17-PREVENTION-CHECK-V218-ADDENDUM.md`·
  `U17-PREVENTION-CHECK-V219.md`·`U16-LEDGER-CHECK-V219.md`·`U17-PREVENTION-CHECK-V219-ADDENDUM.md`·
  `U17-PREVENTION-CHECK-V219-ADDENDUM-2.md`·`U17-PREVENTION-CHECK-V219-ADDENDUM-3.md` 는
  **추적 전용 실행 증거**라 운영 원본이 없다 — 아래 "실행 증거 아티팩트" 절. 제외 목록은 이 README 가 유일 소스다.)

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

## 수록 범위 (32건)

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
- `20260819-074621` — 레인 B v2.18 재심 (`needs-attention`·`NOT_PASSED`,
  재결속 `81d532ff` 후 첫 심사 — v2.15~v2.17 은 stop-time BLOCK 반영판으로 승인
  표면 없음. 직전 5건 = F1 부분해소·F2 부분해소·**F3 해소됨(계약 수준 — 아크 누적
  해소 5)**·F4 부분해소·**F5 회피**(row_ref 소거 후에도 단수 `c_APP(a)` 가 U-16-c/g5/g6
  에 잔존 — 증거 실행기가 «사전순 최소»로 임의 보충); 신규 high 1(live 조회가 host 없는
  `gh api repos/…` 라 GH_HOST override 로 타 host 응답이 ACTIVE — Codex 실측 프로브)·
  medium 1(개발계획 Phase 1 작업 7/종료조건 vs 계약 D0-A 선행조건 — 두 결속 문서 충돌·
  운영자 게이트). F1 = 계약 :5305-5325 «닫지 못한다» vs (B) :4326 «완료 가능성 자체를
  막는다» 내부 불일치 · F2 = D0A-FIRST 절 :3539/:3549 «한 커밋»·`diff-filter=A` 규범
  잔존(S-22) · F4 = T-82 ⑱ 행이 폐지 `edge_seq` 기재를 입력으로 지시. high 3·medium 3
  전건 채택. 다음 개정(v2.19)의 입력. `evidence/focus.txt` 동일 규칙으로 보존)

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
- `20260819-002145/U15-ENTRY-CHECK-ADDENDUM.md` — **v2.15 에라타 `837c35ef` 후 재실행**
  보충 증거 (비규범 부속 — 본 transcript 는 (4d) 불변이라 별도 파일. E1 **구조 정의 D**
  실행기로 T-81 **⑲ gg → MULTIPLE_INTRODUCTIONS/1 로 red 전환**(리터럴 `--diff-filter=A`
  1건 병기) · gu/uu 불변 · ⑫ 양성 CLEAR/0 회귀 / E3 `operator_countersign: "<식별> <ISO-8601
  UTC>"` 형식 반영 U-17 실행기로 T-84 ① ABSENT · ②(i 부재·ii 비인용/비ISO·iii 날짜만·iv 키
  2회) UNSIGNED · ③ ACTIVE/0 · ④ LATE + 부속(D=∅ ACTIVE · |D|=2 LATE) / E2 ⑰ⓑ 는 실행
  결과 불변(APPROVAL_UNBOUND = 정정된 기대). 하니스 == `837c35ef` byte-동일(`957bf49d…`).
  본 저장소 NOT_STARTED/0 · PREVENTION_ABSENT/1 · REBINDING_REQUIRED/1 · 모의 커밋
  unreachable 0/10(+본 실행 14건 bash 재검 0/14). 신규 결함 후보 없음)
- `20260819-002145/U17-PREVENTION-CHECK.md` — **v2.16 T-84 ①②③④** 실행 기록
  (비규범 부속 — 계약이 U-17 증거 경로를 규정하지 않아 sibling. `u17-verify` 실행기:
  4 엔드포인트 verbatim 캡처+UTC·술어→7값/전순서 7단·`responder` seam(`gh`/`file:`/`mixed:`)·
  단일 성공 경로·trap EXIT. **① live 음성(인증 gh)**: `main` → PREVENTION_INSUFFICIENT
  (contexts [test]·strict false·enforce_admins false·PR reviews 부재) · 작업 브랜치 → 404
  PREVENTION_ABSENT · 룰셋 protect_main enforcement disabled / **② seam SIMULATED**:
  ACTIVE(0)·INSUFFICIENT·UNVERIFIABLE(500·무응답) — 양성은 운영자가 보호를 설정하기 전엔
  실측 불가 정직 표기 / **③ 리비전**: live 병기(미푸시 HEAD 422·푸시 무-PR []·origin/main
  PR#636 head 7656259d check-runs 5건 tos-gate 없음)·mixed (a)seam+(b)live 422 →
  UNVERIFIABLE·seam (b) 양성 ACTIVE·check 부재/PR 부재/open → UNVERIFIED_REVISION / **④
  stub 시퀀스** ACTIVE → 해제 ABSENT → 약화 INSUFFICIENT → live INSUFFICIENT + 부속 LATE·
  UNSIGNED·본 저장소 ABSENT. **결함 후보**: E3 countersign 형식 리터럴이 v2.16 본문에서
  소실 · «머지 커밋 check-runs 0건» 은 origin/main 11e382fc 에서 15건(push 트리거) —
  근거 교체 필요(결론은 유지). GET-only·서버 설정 무변경 사후 재조회)
- `20260819-002145/U15-ENTRY-CHECK-V216.md` — **v2.16 U-15-f-1 3단 가드** 실행 transcript
  (비규범 부속·기존 transcript 는 (4d) 불변. `bash 하니스 && bash u17-verify && D0A-FIRST`:
  **G-음성-1** 하니스 차단 → u17 미실행(`U17-0 target=` 부재)·산물 부재 / **G-음성-2 live**
  전제 모의 ENTRY_OK + u17 인증 live INSUFFICIENT → `+ eval` 미도달·`config/tos_completion.yaml`
  미생성 — 두 번째 억제 지점 실증 / **T-81 ⑫ 양성** u17 seam ACTIVE(SIMULATED) →
  ENTRY_PROVENANCE_CLEAR/0(G-부모 일치) / ⑬ PARENT_MISMATCH · ⑯ TRAILER_MALFORMED ·
  ⑲gg MULTIPLE_INTRODUCTIONS(구조 D). 하니스 == `eb2805a9` :4504-4604 byte-동일
  `957bf49d…`. (4c-2) 10 run 각 상태 1. 본 저장소 NOT_STARTED/0·PREVENTION_ABSENT/1·
  REBINDING_REQUIRED/1·모의 커밋 unreachable 0/5)
- `20260819-002145/U17-PREVENTION-CHECK-V217.md` — **v2.17 T-84 ①~⑥** 실행 기록
  (비규범 부속. u17-verify v2.17: owner_repo=`git remote get-url origin` 파생·target=
  `.default_branch` 파생·선언값 대조 → `PREVENTION_TARGET_MISMATCH`(8값/8단)·(b) app.id
  15368·head_sha·check_suite 귀속·(α) 룰셋 시각 관측. **① live** 선언=파생 → INSUFFICIENT /
  **⑤ live** 비-default 브랜치 선언·타 repo 선언 → **TARGET_MISMATCH(D=∅ 에서도)**·seam ACTIVE
  여도 MISMATCH / ② seam ACTIVE·INSUFFICIENT·UNVERIFIABLE(500·무응답→`@UNRESOLVED`) /
  ③ live 병기(422·[]·PR#636 head 5건 app.id 15368·suite 귀속·tos-gate 없음)·mixed 422
  UNVERIFIABLE·seam (b) 양성 ACTIVE / **⑥ seam app.id=99999 위조 → UNVERIFIED_REVISION**
  (이름만 보는 구현은 PASS 대조 병기)·head_sha 불일치·suite 귀속 불일치 red / ④ 시퀀스
  ACTIVE→ABSENT→INSUFFICIENT→live INSUFFICIENT · LATE·UNSIGNED·본 저장소 ABSENT.
  **결함 후보**: §8 T-84 ① 의 «작업 브랜치 → ABSENT» 는 파생 target 하에서 실행기로 재현
  불가(⑤ 와 같은 구성 = TARGET_MISMATCH) — 문언 미전파(S-22). U-15 3단 가드는 델타 0
  (V216 유효). GET-only·서버 설정 무변경 재조회·worktree 미사용)
- `20260819-002145/U17-PREVENTION-CHECK-V218.md` — **v2.18 T-84 ①~⑩** 실행 기록
  (비규범 부속 · **S-24: 최종 동결 `5f4b7cfd` 결속** — 워킹트리 계약 blob == 5f4b7cfd·후속
  계약 커밋 0·하니스 `957bf49d…` byte-동일 수록. u17-verify v2.18: 계약 핀
  `github.com/kakao-harris-lee/kis_unified_sts`·host 보존 정규화·`git remote -v` 일치
  «존재» 대조·target=핀 repo default_branch·Actions app id `apps/github-actions` 서버
  파생·(a) `checks[tos-gate].app_id`·(b) suite.head_sha + `actions/runs?check_suite_id`
  path==`.github/workflows/tos-gate.yml` + 로컬 `git show <head>:tos-gate.yml` 두 리터럴
  grep·P_first/P_last(LATE/ARTIFACT_MUTATED 분리)·9값/9단·수집 후 전순서 최소 방출.
  **① live** INSUFFICIENT / **⑤ live** 비-default·타 repo 선언 → TARGET_MISMATCH(D=∅) /
  **⑩ live** gitlab.com 동일 경로·타 owner 원격 → TARGET_MISMATCH(host-drop 이면 통과 대조)·
  핀 원격 공존 시 통과 / ② seam ACTIVE·INSUFFICIENT·UNVERIFIABLE / **⑦ seam**
  checks[tos-gate].app_id=99999 → INSUFFICIENT(D=∅·name-only 는 prot_ok 대조) / ③ live
  병기(422·[]·PR#636 head 5 run app 15368·actions/runs path=test.yml·로컬 head 미보유) +
  mixed 422 UNVERIFIABLE + seam (b) 양성 ACTIVE(픽스처 W 에 tos-gate.yml 두 리터럴) /
  ⑥ app 99999 · **⑧ path=test.yml → UNVERIFIED_REVISION**(app-id-only 는 PASS 대조) ·
  R2 blob 부재/리터럴 부재 red / **⑨ 아티팩트 편집·편집 후 원복 → ARTIFACT_MUTATED**
  (P_first-only 는 ACTIVE 대조)·P_first⋠d → LATE / ④ 시퀀스 · UNSIGNED · 본 저장소 ABSENT.
  GET-only·서버 설정 무변경·worktree 미사용. 정밀화 후보: 선언 키 필수 여부(C3 «선언하지
  않는다» vs ⑤)·비-핀 원격 공존·R2 의 «PR head 로컬 보유» 전제)
- `20260819-002145/U17-PREVENTION-CHECK-V218-ADDENDUM.md` — **v2.18 에라타 `feb91d60` S-24
  addendum** (비규범 부속. ① `git diff 5f4b7cfd..feb91d60` 전문 + 절 범위 diff 기계 증명 —
  닿는 절 = 변경 이력 :193·E2 선언 키 선택(+7)·E3 원격 공존(+4)·E1 R2 ③ 서버 blob
  (5237-5239→5248-5261); 닿지 않는 절 ∅ = 하니스 블록 4528-4628(`957bf49d…`)·§8 T-84 행·(a)
  술어·(c) P_first/P_last·U-17-c 상태표/전순서 등 행 범위 명시 → ①②④⑥⑦⑨·UNSIGNED·ABSENT 는
  `7a146466` 증거 그대로 결속 선언 ② 영향 변이 재실행(`u17-verify-v218e.sh`: R2 ③ 을
  `contents/…?ref=<PR head>` 서버 조회·base64 decode·404/HTTP → UNVERIFIED_REVISION·네트워크
  → UNVERIFIABLE·로컬 git show 는 보조 기록만): **E1 live 병기** PR#636 head 로컬 미보유인데
  `contents/test.yml?ref=` 200·`tos-gate.yml?ref=` 404 / ③-b seam 양성 ACTIVE(contents 200
  base64 두 리터럴) · R2-a 404 · R2-b 리터럴 부재 · R2-c 네트워크 UNVERIFIABLE · ⑧ path 불일치 ·
  **R2-d PR head 미보유 판정 저장소에서 서버 blob 만으로 ACTIVE**(E1 동기 실증) / **E2 live**:
  선언 키 부재 → ① INSUFFICIENT(핀 유일 소스)·gitlab 원격 → 원격 축 TARGET_MISMATCH·선언 있음
  비-default → MISMATCH 불변 / 본 저장소 ABSENT. 하니스 == feb91d60 byte-동일·GET-only·서버
  설정 무변경. 신규 결함 후보 없음(contents >1MB `content` 부재 처리 독해 1건))
- `20260819-074621/U17-PREVENTION-CHECK-V219.md` — **v2.19 T-84 ⑪·⑫ + 연속성 소비자 (a)~(f)
  + 회귀 ③⑤⑨⑩** 실행 기록 (비규범 부속 — v2.18 재심 스탬프 sibling. **S-24 결속: 동결
  `d5a8302a`**[워킹트리 blob == 동결 blob·계약 후속 커밋 0·하니스 :4589-4689 `957bf49d…`].
  실행기 `u17-verify-v219.sh` = v2.18e 파생: 모든 `gh api` 에 `--hostname github.com`(핀 파생)
  + `GH_HOST` 재핀 + `gh auth status --hostname` 사전 확인 · 연속성 소비자(룰셋 created/updated_at
  vs `t_land`=min merged_at·classic-only·삭제-재생성) · U-17-c 10값/10단. **⑫ live**:
  `GH_HOST=example.invalid` 전체 실행 → 상태 문자열까지 기준선과 동일 `PREVENTION_INSUFFICIENT`,
  GH_DEBUG 요청 host 6/6 `api.github.com` / 대조군(`--hostname` 제거·diff 4행) → `example.invalid`
  `/api/v3/…` → `PREVENTION_UNVERIFIABLE`. **⑪ SIMULATED**(캡처 seam): (a) 정상 ACTIVE/0 ·
  (b) off→merge→on CONTINUITY_UNVERIFIABLE[직전 판 실행기는 ACTIVE 통과 = 닫힌 자리] ·
  (c) 삭제-재생성 · (d) classic-only[직전 판 통과] · (e) direct-push UNVERIFIED_REVISION 선발화 ·
  (f) committer-date 무시. 회귀 ③ ACTIVE seam·⑤/⑩ live TARGET_MISMATCH ×4·⑨ ARTIFACT_MUTATED
  전건 일치. 본 저장소 live `PREVENTION_ABSENT`/1(±override 동일). **관측 보고(에라타 후보)**:
  D-1 classic 보호를 룰셋과 동등 disjunct 로 둔 :5220-5236 이 :5443(classic-only 판정 불가)+
  :5504(ACTIVE 논리곱)와 충돌 → `D≠∅` 이면 classic 경로 ACTIVE 도달 불가(死분기 — v2.18 ③-b
  classic 양성이 red 로 뒤집힘) · D-2 `t_land` 가 (b) 실패 시 미정의 · D-3 본 저장소 룰셋 1건
  disabled = 적용 0 · D-4 타 host ACTIVE 위조는 GET-only 라 직접 실증 불가 · D-5~7 gh 2.93.0
  에서 `--hostname` 이 `GH_HOST` 를 이김(이중 결속 구별 불가)·`responder=file:` auth 전제·아티팩트
  `host` 키 처분 미규정. 서버 쓰기 0(사후 재조회 동일))
- `20260819-074621/U16-LEDGER-CHECK-V219.md` — **v2.19 T-82 ⑱(현행 스키마)·⑳ⓐⓑ + 회귀
  ⑯⑰ⓐⓑⓒ⑲⑮⑪·자인 잔여** 손 실행 기록 (비규범 부속 — S-24 결속 동결 `d5a8302a`. **S-23 전 규칙
  실행기** `u16-full-exec-v219.py`: U-16-d 12단 전순서 + 선-검사 1~4 → g-단락 5~11 문자 구현 ·
  `rules_executed=` 13 규칙 전 run `rules_missing=∅` · c_APP 구조 집합(capp) 실행. ⑱-1 현행
  스키마(같은 row_id·다른 승인 행·형제 도입→merge) NO_ROWS_CLEAR/0·두 행 |c_APP|=1 · **⑱-2 계약
  :2927 리터럴 «별개 row_id» 픽스처는 APPROVAL_MALFORMED/1 — 기대와 정반대(에라타 후보 D-1)** ·
  ⑳ⓐ 형제 동일 행 |c_APP|=2 → APPROVAL_MALFORMED / 대조군(v2.15 «사전순 최소») NO_ROWS_CLEAR
  = 통과=실패 실증 · ⑳ⓑ 얕은 클론 |c_APP|=0∧g1 위배 → PROVENANCE_UNVERIFIABLE(2) / 대조군
  («g1 먼저»·diff 1행) APPROVAL_MALFORMED(3) = 2 vs 3 발산 실증 · 회귀 전건 동일(⑰ⓑ UNBOUND=E2).
  **관측 보고(에라타 후보)**: D-2 :6917-6920 «루트(부모 없음) 공허참 자동 포함»이 얕은 클론
  경계와 진짜 루트를 구별하지 않아 리터럴 파생에서 `--depth 1` 이 |c_APP|=1 → ⑳ⓑ 전제 불성립
  (경계=«부모 미상»으로 읽어야 0; **동형 정의 C_R·D·P_first/P_last 전부 같은 단서 필요**) ·
  D-3 선-검사 2 «얕은 클론»을 전역 단축으로 읽으면 ⑳ⓑ 대조군이 둘 다 2 → 구별력 상실(두 읽기
  미구별) · D-4/5 한 간선 다수 후보 상태 귀속·«고아» 구조 정의 미정의. 픽스처 = scratchpad 독립
  git 저장소 20개·push/fetch 0)
- `20260819-074621/U17-PREVENTION-CHECK-V219-ADDENDUM.md` — **v2.19 에라타 `e3ed4e78` S-24
  addendum**(U-17·U-16 양축 한 파일. §0 결속: HEAD==`e3ed4e78`·워킹트리 blob==에라타 blob·하니스
  :4598-4698 `957bf49d…`==`d5a8302a`:4589-4689 byte-동일 · §1 `s24-proof.sh` 2층 증명 — ① `git diff
  -U0 d5a8302a..e3ed4e78` hunk 20개 사이 전 무변경 구간 자동 sha 대조 ∅ ② 리터럴 grep 파생 명명 절
  대조: 닿지 않음 ∅ 12건[하니스·T-84 행·T-81 행·(b) 전문·(α) 판정 본체·(c) 기계 조건·U-17-c
  상태표/10단/U-17-d·c_APP 수식·U-16-d 12단·g-단락·a2·h] / 닿음 13건[E1 (a)·E3 C6·E2 (α) 입력우주·
  [SHALLOW] 4곳·E6 선-검사·E7 U-16-b·E4 T-82 행·심사/변경 이력·(B)] → 비영향 변이는 `90a5ce7d` 그대로
  결속 · §4 영향 변이 재실행: [E1] 룰셋 양성 ACTIVE/0·classic-only D=∅ ACTIVE/0·**classic-only D≠∅
  CONTINUITY_UNVERIFIABLE = fail-closed terminal(死분기 아님)** · [E4] ⑱ 정정 문언 NO_ROWS_CLEAR/0 ·
  [SHALLOW] depth-1 경계에서 D/P_first/P_last→PREVENTION_UNVERIFIABLE·c_APP→PROVENANCE_UNVERIFIABLE(2,
  대조군 3)·**C_R→PROVENANCE_UNVERIFIABLE(직전 실행기는 NO_ROWS_CLEAR/0 = 신설 축)**·판별 3수단
  (`--is-shallow-repository`·`.git/shallow`·부모 객체 조회 실패) 기록 · [E3] host 키 일치 불변/불일치
  **TARGET_MISMATCH**(직전 실행기는 무시)/부재 핀 유일·GET-only 경계 재확인 · [E6] 얕지만 후보 우주 밖
  → 접지 않음(ACTIVE/NO_ROWS_CLEAR) · [E7] 고아 구조 정의(g6 단독 탈락 → ORDER_INVALID·고아 0)·
  다수 후보 → 전순서 최소(HEAD_INVALID 8 vs 10 중 8). 전 run rules_missing=∅. **신규 결함 후보**:
  **N-1 `git replace --graft` 가 [SHALLOW] 판별 3수단을 전부 통과**(`--is-shallow-repository`=false·
  `.git/shallow` 부재·부모 객체 present)하면서 `%P` 는 가짜 부모 반환 → 같은 seam 에서 LATE(6)→
  ACTIVE(10) 뒤집힘 = fail-open(제안: `git replace -l` 공집합 또는 `--no-replace-objects` 고정) ·
  **N-2 `P_last` 다부모 의미(∧/∨) 미규정** — 2-부모 graft 구성에서 ARTIFACT_MUTATED(7) vs ACTIVE(10)
  극성 갈림(c_APP·C_R·D 는 ∀-부모 명시·P_last 만 비대칭) · N-3~5 관측(전순서 최소 3층 미명시 등).
  서버 쓰기 0(사후 재조회 동일)·본 저장소 replace ref 0·shallow=false)
- `20260819-074621/U17-PREVENTION-CHECK-V219-ADDENDUM-2.md` — **v2.19 에라타 2차 `ad5be1a3` S-24
  addendum**(§0 결속 HEAD==`ad5be1a3`·하니스 :4608-4708 `957bf49d…`==`e3ed4e78`:4598-4698 · §1
  `s24-proof-2.sh` 2층 증명: hunk 14개 사이 무변경 구간 ∅ / 명명 절 닿지 않음 ∅ 17건[하니스·T-84/T-82/
  T-81 행·(a)(b)(α) 전문·C6·U-17-c 전순서 10단·U-17-d·c_APP 수식·U-16-d 12단·g-단락·a2·h·U-16-b·CORR] /
  닿음 10건[[E8] [PARENTS-UNTRUSTED] 유일 소스·참조 4곳(D·C_R·P·선-검사)·[E9] U-17-c 상태표 조건·U-16-d
  머리·(B)·이력] → 비영향 변이는 `90a5ce7d`·`197f4fe4` 그대로 결속 · §4 영향 변이: **[E8] graft** —
  직전 실행기 ACTIVE/0(fail-open 재현) / CTRL(②무력화만) LATE 유지 / v2.19-2(①+②) UNVERIFIABLE ·
  `.git/info/grafts` 는 `--no-replace-objects` 로 안 꺼짐 실측 → ① 관측(부재 요구)이 잡음 · U-16 c_APP/
  C_R(증인 위조) 각각 진실/직전/CTRL/v2.19-2 4뷰 전건 일치 · 정상 회귀 불변(⑳ⓑ 2 vs 3 발산 유지) ·
  **[E9]** 머지 blob==한 부모 → ∀ ACTIVE vs 직전 ∨ ARTIFACT_MUTATED(극성 차이 실증) · 둘 다 다름 → 머지
  도입 |P_last|=1 · 형제 동일 blob → |P_last|=2 MUTATED · 2-부모 graft 재실행 결정적(MUTATED→LATE→
  UNVERIFIABLE) · T-84 ⑨ 유지 · 상보성 4종 정확히 하나. **신규 결함 후보**: **M-1 E8 ① «얕은 클론
  아님» 항(전역)이 E6 국소 판정과 문언 충돌** — 문자대로면 ⑳ⓑ 판별력·«얕지만 후보 밖» 대조 붕괴(실행기는
  replace/grafts 전역·얕음 국소로 읽어 회귀 유지) · M-2 ②가 ①을 가리지 않음(무간섭) · M-3 [PARENTS-
  UNTRUSTED] 판별이 열거형(열린-세계) — 부모 집합 독립 재파생(커밋 객체 parent 헤더 vs %P)이면 닫힘 ·
  M-4 graft 는 새 커밋 객체(약한 관측) · **M-5 `P_first` 카디널리티 처분 부재**(|P_first|=2 실측·=0 이면
  ∀ 공허참으로 LATE — fail-closed 이나 문언 자리 없음). 서버 쓰기 0(U-16 축 GitHub 조회 0)·본 저장소
  replace 0/grafts 부재/shallow=false)
- `20260819-074621/U17-PREVENTION-CHECK-V219-ADDENDUM-3.md` — **v2.19 에라타 3차 `f6493d23` S-24
  addendum**(§0 결속 HEAD==`f6493d23`·하니스 :4614-4714 `957bf49d…`==`ad5be1a3`:4608-4708 · §1
  `s24-proof-3.sh`: hunk 5개 사이 무변경 구간 ∅ / 명명 절 닿지 않음 ∅ 22건(하니스·T-84/T-82/T-81 행·
  (a)(b)(α)·C6·U-17-c 전순서/상태표/(c)·U-17-d·D/C_R 참조 자리·c_APP 수식·U-16-d 12단/선-검사/g-단락·
  a2·h·U-16-b·CORR) / 닿음 5건([E10] [PARENTS-UNTRUSTED] 유일 소스·[E11] P 카디널리티·(B)·이력) · §4:
  ㉠ 원시 프로브 5구성(평시 일치 / replace·grafts·`GIT_REPLACE_REF_BASE`·`--separate-git-dir` 불일치 —
  grafts 는 커밋 객체 미변경이라 `cat-file`=진짜·`%P`=가짜 실측) · [E10] replace/grafts/제3 표면
  REF_BASE 전부 ㉠ 불일치 → UNVERIFIABLE · **separate-git-dir+grafts: v2.19-3 UNVERIFIABLE vs ㉡ 리터럴
  대조군 PREVENTION_ACTIVE/0·NO_ROWS_CLEAR/0 = 샌다(㉠ 주 판별 실증)** · ⑳ⓑ 후보 우주 안 2/대조군 3 ·
  얕지만 후보 밖 NO_ROWS_CLEAR/0(「얕음=전역」 대조군 2 = 실패) · 회귀 불변 · [E11] |P_first|=0 부재
  ABSENT(본 저장소 live)/존재 UNVERIFIABLE · |P_first|=2 ACTIVE·LATE 양방향 결정적 · 상보성 4종.
  **신규 결함 후보**: **K-1 ㉠(전역)/㉢(국소) 관할 미명시** — 얕은 경계에서도 ㉠ 불일치(재파생 [parent] vs
  %P []) 성립 → 문자대로 전역 적용하면 E6 국소화·⑳ⓑ 판별력이 다른 경로로 재발(실행기는 «얕은 경계 유래
  불일치는 ㉢ 소관»으로 읽음) · **K-2 ㉡ «`.git/info/grafts` 부재» 리터럴이 `--separate-git-dir` 에서
  항상 통과(fail-open)** → `git rev-parse --absolute-git-dir` 파생 필요 · K-3 REF_BASE 실재(㉠ 환경
  무관·㉡ 은 같은 env 만) · K-4 ㉠ 은 후보 우주에만(후보 밖 grafts 는 무력화로 안 꺼져 잔여 실재 — 정직
  경계). 서버 쓰기 0·본 저장소 ㉠㉡㉢ 전부 통과)

## 향후 관행

판정은 종전대로 `.omc/review/` 에 기록되고(digest 범위 밖 기록 원리·재심 체인
유지), **판정 방출 후** byte-동일 사본을 이 디렉터리에 추가해 커밋한다.
사본 추가는 편집을 동반하지 않는다.
