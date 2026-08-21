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
    --exclude=U17-PREVENTION-CHECK-V219-ADDENDUM-3.md --exclude=U17-PREVENTION-CHECK-V219-ADDENDUM-4.md \
    --exclude=U17-PREVENTION-CHECK-V219-ADDENDUM-5.md --exclude=U17-PREVENTION-CHECK-V219-ADDENDUM-6.md \
    --exclude=U17-PREVENTION-CHECK-V219-ADDENDUM-7.md --exclude=U17-PREVENTION-CHECK-V219-ADDENDUM-8.md \
    --exclude=U17-PREVENTION-CHECK-V220.md --exclude=U16-LEDGER-CHECK-V220.md \
    --exclude=U17-PREVENTION-CHECK-V220-ADDENDUM.md --exclude=U17-PREVENTION-CHECK-V221.md \
    --exclude=U17-PREVENTION-CHECK-V221-ADDENDUM.md --exclude=U17-PREVENTION-CHECK-V221-ADDENDUM-2.md \
    --exclude=U17-PREVENTION-CHECK-V221-ADDENDUM-3.md --exclude=U17-PREVENTION-CHECK-V222.md \
    .omc/review docs/reviews/phase0-completion-contract
  ```

  (`U15-ENTRY-CHECK.md`·`U16-LEDGER-CHECK.md`·`U15-ENTRY-CHECK-ADDENDUM.md`·
  `U17-PREVENTION-CHECK.md`·`U15-ENTRY-CHECK-V216.md`·`U17-PREVENTION-CHECK-V217.md`·
  `U17-PREVENTION-CHECK-V218.md`·`U17-PREVENTION-CHECK-V218-ADDENDUM.md`·
  `U17-PREVENTION-CHECK-V219.md`·`U16-LEDGER-CHECK-V219.md`·`U17-PREVENTION-CHECK-V219-ADDENDUM.md`·
  `U17-PREVENTION-CHECK-V219-ADDENDUM-2.md`·`U17-PREVENTION-CHECK-V219-ADDENDUM-3.md`·
  `U17-PREVENTION-CHECK-V219-ADDENDUM-4.md`·`U17-PREVENTION-CHECK-V219-ADDENDUM-5.md`·
  `U17-PREVENTION-CHECK-V219-ADDENDUM-6.md`·`U17-PREVENTION-CHECK-V219-ADDENDUM-7.md`·
  `U17-PREVENTION-CHECK-V219-ADDENDUM-8.md`·`U17-PREVENTION-CHECK-V220.md`·`U16-LEDGER-CHECK-V220.md`·
  `U17-PREVENTION-CHECK-V220-ADDENDUM.md`·`U17-PREVENTION-CHECK-V221.md`·
  `U17-PREVENTION-CHECK-V221-ADDENDUM.md`·`U17-PREVENTION-CHECK-V221-ADDENDUM-2.md`·
  `U17-PREVENTION-CHECK-V221-ADDENDUM-3.md`·`U17-PREVENTION-CHECK-V222.md` 는
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

## 수록 범위 (34건)

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
- `20260819-135916` — 레인 B v2.19 재심 (`needs-attention`·`NOT_PASSED`, 재결속 `be0cbc95`
  [v2.19 6차 에라타 `359f5bc5` 내용] 후 심사. 직전 6건 = **F1 부분·#2 host 해소·F2 해소·F4
  부분·F5 해소(계약 수준)·#6 미해소(운영자 게이트) — 아크 누적 해소 8·회피 0**. 신규 high 3:
  U-17 (b)③ 워크플로 blob 두 리터럴 grep 은 «문자열 존재» 인증(주석/미사용 값 통과 — Codex
  픽스처 재현) · U-16-a2 «(g1~g5)» 닫힌 열거가 g6 제외(S-22 — v2.13 g6 신설 시 미전파) ·
  [PARENTS-UNTRUSTED] ㉡ 1회 관측 vs 조상성 소비 TOCTOU(후보 밖 grafts interleaving — ㉡ 이
  유일 완화라 계약이 자인). medium 2: T-82 ⑯ 여전히 edge_seq 1·2 지시(같은 셀 ⑱만 고침 — S-22)
  · #6 개발계획 :289-297 vs 계약 (D) — verbatim 제안은 결속 문서를 안 바꿈(회피 아님·미해소
  blocker·운영자 게이트). high 3·medium 2 전건 채택. 다음 개정(v2.20)의 입력. `evidence/focus.txt`
  동일 규칙으로 보존)
- `20260819-193235` — 레인 B v2.20 재심 (`needs-attention`·`NOT_PASSED`, 재결속 `c00d808e`
  [계약 에라타 `ae842cce` + 개발계획 (D) 적용 `3d17ea66` — 두 문서 모두 개정] 후 심사. 직전 5건
  = **#1 회피**(구조 파서+서버 스텝 대조는 토큰 존재·이름/conclusion 만 — `|| true`·`set +e`·
  `false && bash …` 도달 불가 호출이 ACTIVE; 계약 자신이 정직 경계로 자인했으나 실행·실패 전파 미인증은
  #1 본질과 같은 클래스)·**#2 a2 g6·#3 격리 스냅샷·#4 ⑯ 해소 — 아크 누적 해소 11**·#5/#6 부분
  (개발계획 (D) 적용은 맞춰졌으나 UNCHK-008 `owner_track` 이 `Phase 1` 잔존·U-17 하니스 경로 «D0-A
  산출물» 표기 → 누가 산출·폐쇄하는지 비순환 순서 부재 — S-22 형제 소비처 미전파). high 1·medium 1
  전건 채택·신규 클래스 0. 다음 개정(v2.21)의 입력. `evidence/focus.txt` 동일 규칙으로 보존)
- `20260820-082830` — 레인 B v2.21 재심 (`needs-attention`·`NOT_PASSED`, 재결속 `93522c09`
  [계약 에라타 3차 `c4d97118` + 개발계획 `0528a919` — 두 문서 모두 개정] 후 심사. 직전 2건
  = **#1 회피(2연속)**(정본 대조가 `⑬c`/`⑬g` 리터럴 변종은 거부하나 **정본 스텝 순서가
  «체크아웃 → 하니스 실행 → sha 검증»** 이라 미승인 하니스가 **실행된 뒤 자기 파일을 정본
  바이트로 덮고 exit 0** → 후행 checksum 은 `957bf49d…` 를 보고 `OK`/0·두 스텝 success·정적
  blob 정본 유지 → `PREVENTION_ACTIVE`. **잡 «안» 반례라 계약이 선언한 잔여 경계(«잡 «밖»»)에
  미포섭**)·**#2 부분해소(3연속)**(개발계획 선행조건이 룰셋·워크플로·하니스 «파일»은 실체화하나
  가드 체인 3단이 요구하는 **별도 실행기 `u17-verify` 는 누락** — 계약 자신이 `:5757-5767` 에서
  하니스와 구별되는 별도 산출물로 규정·소비자는 `:5368-5370` «리뷰어 / D0-A 이후의 검사기» ·
  인용된 순서 실증은 `D=∅` 라 `(b)(c)` 가 vacuous 인 채 ACTIVE 도달 = 하니스 바이트에 대해
  아무것도 증명 안 함). **신규 해소 0 · 아크 누적 해소 11 불변.** 신규 high 1 = **검증 두 층의
  객체 식별 분열**(blob 층 `jobs[GATE_JOB]` = YAML **잡 id** vs 서버 층 `hit[0]` = **표시 이름**·
  유일성 검사 없음 — **에라타 3차의 R-3 완화가 잡 `name` 을 자유 문자열로 허용**하면서 두 키
  분리 가능·형제 잡 개수 제약 문언 부재 = **신규 결함 클래스**) · 신규 medium 1 = **R-1 재발
  클래스**(«닫힌 집합»·«핀»이라 적고 값 미고정: `permissions` «예»·`runs-on` «등»·체크아웃
  `with[fetch-depth]` 존재/값 미검사·YAML 파서 미고정 4자리). high 2·medium 2 **전건 채택·기각 0**
  (#2 하위 인용 `fbc0d9b5…` 1건은 팬텀 — V221 전문 grep 0건·finding 자신의 `file:line` 은 실재라
  기각 사유 불성립, 다음 재심에 병기). S-20 종수 14 일관·`CLAUDE.md` 비협상 충돌 0(14판 연속).
  다음 개정(v2.22)의 입력. `evidence/focus.txt` 동일 규칙으로 보존)

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
- `20260819-074621/U17-PREVENTION-CHECK-V219-ADDENDUM-4.md` — **v2.19 에라타 4차 `db6ce918` S-24
  addendum**(§0 결속 HEAD==`db6ce918`·하니스 :4620-4720 `957bf49d…`==`f6493d23`:4614-4714 · §1
  `s24-proof-4.sh`: hunk 6개 사이 ∅ / 명명 절 닿지 않음 ∅ 23건(하니스·T 행·(a)(b)(α)·C6·U-17-c·[E11] P·
  U-17-d·D/C_R 참조·c_APP 수식·U-16-d 12단/선-검사/g-단락·a2·h·U-16-b·CORR) / 닿음 4건([E12·E13]
  [PARENTS-UNTRUSTED] 블록·(B)·이력) — 4차는 판별 «절차»만 · §4: E13 자기점검 `.git/` 리터럴 u17/u16/
  하니스 0건 · 파생 프로브 3배치(일반 상대·separate-git-dir 절대·얕은 클론 `--git-path shallow`==HEAD) ·
  **[E13] separate-git-dir+grafts: 파생 UNVERIFIABLE vs 리터럴 대조군 ACTIVE/0·NO_ROWS_CLEAR/0(샘)** ·
  [E12] depth-1 ㉢ 3건·전역 0건 → UNVERIFIABLE · 얕은 경계∧replace 병리 = 미검사 창 없음(㉢ 배제→
  |P_first|=0 fail-closed + ㉡ 독립 전역, 두 겹) · ⑳ⓑ 안 2/대조군 3·밖 NO_ROWS_CLEAR/0(「전역」 대조군 2)
  · [K-4] `merge-base --is-ancestor` 는 grafts 를 기본·`--no-replace-objects`·env 3종 모두 따름(잔여
  확증)·replace 는 꺼짐 · 정상 회귀 불변. **신규 결함 후보**: **L-1 [fail-open 잔존] `git rev-parse
  --git-path` 는 일반 배치에서 상대 경로 반환 — E13 이 결합 기준(cwd=저장소 루트 또는 `--absolute-git-dir`
  결합)을 적지 않아 저장소 밖 cwd 에서 `[ -f ]` 거짓 ABSENT → ㉡ 통과**(실행기는 cd/gitpath 결합으로 회피)
  · L-2 K-4 잔여를 완화하는 유일 항이 ㉡ 인데 L-1 로 새면 곱해짐 · L-3 하니스 예외 조항 덮는 것 0건 ·
  L-5 `U17-PU㉢`/`U17-PU㉠` 분리 방출로 절차 감사 가능. 서버 쓰기 0·본 저장소 ㉠㉡㉢ 통과)
- `20260819-074621/U17-PREVENTION-CHECK-V219-ADDENDUM-5.md` — **v2.19 에라타 5차·최종 `eddbd241` S-24
  addendum**(§0 결속 HEAD==`eddbd241`·하니스 :4625-4725 `957bf49d…`==`db6ce918`:4620-4720 — 5판 연속
  byte-동일 · §1 `s24-proof-5.sh`: hunk 4개 사이 ∅ / 명명 절 닿지 않음 ∅ 23건 / 닿음 4건([E14]
  [PARENTS-UNTRUSTED] 블록·(B)·이력) · §4: 파생·결합 프로브(`--git-path info/grafts` 상대 반환·저장소 밖
  cwd 거짓 ABSENT·루트 결합 present = L-1 재현) · **[E14] 저장소 밖 cwd+grafts: 대조군 PREVENTION_ACTIVE/0·
  NO_ROWS_CLEAR/0(fail-open) vs 판정기 PREVENTION_UNVERIFIABLE/PROVENANCE_UNVERIFIABLE(차단)** ·
  `--separate-git-dir`(파생 절대) 이중 결합 없이 정확 · 정상 회귀 cwd 밖/루트 불변 · 본 저장소 live
  PREVENTION_ABSENT. **[fail-open/차단] 신규 0건 — 에라타 아크 종결.** 관측: N-1 결합 대상은 «저장소
  루트(`--show-toplevel`)»뿐(`--absolute-git-dir` 에 `.git/info/grafts` 를 붙이면 이중 — 극성은 fail-closed·
  문언 한 줄로 오독 제거 가능, 다음 사이클 입력) · N-3 최종 상태 본 저장소 [PARENTS-UNTRUSTED] 통과.
  서버 쓰기 0)
- `20260819-074621/U17-PREVENTION-CHECK-V219-ADDENDUM-6.md` — **v2.19 에라타 6차 `359f5bc5` S-24
  addendum — stop-time Codex BLOCK #4 대응**(E14 가 허용한 «상대 `--git-path` + `--absolute-git-dir` 결합»
  = `<root>/.git/.git/info/grafts` → 거짓 ABSENT → ㉡ 통과 = **fail-open** — addendum-5 N-1 이 «fail-closed»
  로 오분류한 것을 M-0 으로 자기 정정). §0 결속 HEAD==`359f5bc5`·하니스 :4631-4731 `957bf49d…`(6판
  연속) · §1 `s24-proof-6.sh`: hunk 4개 ∅ / 명명 절 닿지 않음 ∅ 23건 / 닿음 4건([E15] 블록·(B)·이력) ·
  §4 **옛 허용 분기 뮤테이션(Codex 요구)**: 경로 원문 `AGD+상대 = <root>/.git/.git/info/grafts → ABSENT(거짓)`
  vs `--show-toplevel 결합 = <root>/.git/info/grafts → present` — 대조군 PREVENTION_ACTIVE/0·NO_ROWS_CLEAR/0
  (fail-open 재현) vs E15 PREVENTION_UNVERIFIABLE/PROVENANCE_UNVERIFIABLE(차단)·동등 대안(cwd=루트) 동일 차단 ·
  separate-git-dir 절대 그대로 차단 · **linked worktree: `--git-path` 는 common-dir 기준 절대 → 공유 grafts
  정확 지시(결함 아님)** · 정상 회귀 cwd 무관 · 부재 판정 극성 감사표(«부재→차단» 6항 / «부재→통과» 3항 —
  ㉡ replace -l·㉡ grafts·㉢ shallow 목록 — 만 거짓 부재가 fail-open = E15 대상 정확). **⚠ §4 «fail-open
  재현»·§5 «신규 0건/아크 종결» 은 stop-time Codex BLOCK #5 로 철회** — 뮤테이션이 2변수(나쁜 결합 + ㉠ 실패
  제거)라 나쁜 결합 «만으로» green 이 실증되지 않았음(자체 픽스처가 ㉠ 불일치 보고). 재실증은 addendum-7.
  서버 쓰기 0)
- `20260819-074621/U17-PREVENTION-CHECK-V219-ADDENDUM-7.md` — **addendum-6 §4 대체 — 단일 변수 뮤턴트
  (stop-time Codex BLOCK #5 채택)**. 계약 무변경(`359f5bc5` 결속 유지·하니스 :4631-4731 `957bf49d…`).
  **㉠ 자연 침묵 픽스처**: grafts 로 후보 우주 «밖» 커밋(U-17 워크플로만 있는 `W`·U-16 리뷰어/원장 없는
  `H0`)의 부모만 재작성 → ㉠ 대상 집합 원문(cat-file 부모 == %P 전건 일치·«남는» 전역 불일치 0) → ㉡ 이
  유일 가드(K-4/L-2 자리) · **단일 변수 diff 1행**(`--show-toplevel` → `--absolute-git-dir` 결합 base 만) ·
  **결과**: 정직 이력 U-17 LATE(6)/U-16 PROVENANCE_UNVERIFIABLE(2, C_R=∅) → grafts+뮤턴트 **PREVENTION_
  ACTIVE/0 · NO_ROWS_CLEAR/0(도달 가능한 fail-open 실증)** → grafts+E15 판정기 PREVENTION_UNVERIFIABLE/
  PROVENANCE_UNVERIFIABLE(차단) · 조상성 뒤집힘 실측(`merge-base --is-ancestor` rc 1→0·`--no-replace-
  objects` 하에서도 0 = K-4 잔여). §0 에서 addendum-6 §4 «fail-open reproduced»·§5 «신규 0건/arc closed»
  철회 명시(addendum-6 은 (4d) 불변). 이 파일은 «아크 종결·신규 0» 을 주장하지 않는다. **⚠ U-16 축 ㉠ 침묵
  증명이 graft «전» 후보 집합(`C_R=[]`)을 기록 — stop-time BLOCK #6 → addendum-8 이 graft «후» 실행기 실호출
  추적으로 대체(6de2472 포함 전건 일치·결론 유지).** 서버 쓰기 0)
- `20260819-074621/U17-PREVENTION-CHECK-V219-ADDENDUM-8.md` — **addendum-7 ㉠ 침묵 증명 대체 — graft «후»
  실행기 실호출 추적(stop-time Codex BLOCK #6 채택)**. 계약 무변경(`359f5bc5`·하니스 :4631-4731 `957bf49d…`).
  addendum-7 U-16 축이 후보 집합을 graft «전» 에 드라이버 독립 재계산으로 기록(`C_R=[]`)했으나 실제 뮤턴트는
  `C_R={6de2472…}` 를 소비 — 결함 시인·철회. 대체: PATH shim 으로 실행기가 실제 호출한 `git cat-file commit
  <x>` 를 추적(addendum-7 픽스처 사본 `fx82k/silent`·HEAD 동일·grafts 원문 동일) → U-16 뮤턴트 graft 후 고유
  x 4(`6de2472` R 리뷰어 도입·`76f2cad9` CN·`cc9f2dbb` A·`f05cb2b0` M) **cat-file 부모 == %P 전건 일치** ·
  U-17 도 같은 결함이라 재실행(3건 전건 일치) · 신규 픽스처 재실행 graft 전==후 집합·전건 일치. `6de2472`
  경위: C_R 은 간선별이라 정직 이력에서도 edge#2(M)는 이미 `C_R={6de2472}` — addendum-7 의 `[]` 는 graft
  효과가 아니라 드라이버 `rev-list CN` 단일 열거 범위 오류. 상태값(정직/뮤턴트/판정기): U-16 PROVENANCE_
  UNVERIFIABLE/1 → **NO_ROWS_CLEAR/0(fail-open)** → PROVENANCE_UNVERIFIABLE/1 · U-17 LATE/1 → **ACTIVE/0** →
  UNVERIFIABLE/1(a7 사본·신규 픽스처 양쪽). **결론 (a): ㉠ 자연 침묵 성립 → 뮤턴트 green 은 결합 base 한 줄
  단일 변수 효과 — R-1(옛 결합 = 도달 가능한 fail-open) 유지·존재 증명이며 전칭 아님·«아크 종결» 주장 없음.**
  부수: grafts 는 ㉠ 대상 집합을 바꾸지 않고 조상성만 뒤집음(K-4/L-2 직접 실측) · git 2.38 `info/grafts` 폐기
  예고(향후 `replace --convert-graft-file`) · 교훈 «실행기가 소비한 집합 주장은 실행기 관측으로 — 검증자
  독립 재계산은 대조군이지 근거 아님». live 조회 0·서버 쓰기 0)
- `20260819-135916/U17-PREVENTION-CHECK-V220.md` — **v2.20 T-84 ⑬abc·⑭ + (b)③ 구조 파싱 8픽스처 + 서버
  steps[] mock 5종 + 회귀 ⑤⑨⑩⑪⑫** 실행 기록(v2.19 재심 스탬프 sibling·비규범 부속·**S-24 결속 동결
  `3d17ea66`**[계약·개발계획 blob==동결·후속 커밋 0·하니스 :4654-4754 `957bf49d…`]. 실행기 `u17-verify-v220.sh`
  `67d636ce…`+`wfstruct-v220.py` `792aaa1e…`(YAML→steps[].run→셸 토크나이즈→명령 위치/대조 피연산자·서버
  `actions/runs/{run_id}/jobs` steps[] 이름·conclusion). ⑬ 기준선 ACTIVE/0 · **⑬a echo 인자·⑬b trailing 주석
  → UNVERIFIED_REVISION(v2.19 실행기는 ACTIVE/0 = 닫은 자리)** · ⑬c `|| true` 미검출=ACTIVE(계약 정직 경계
  대로) · ⑭ 서버 verify 스텝 부재/failure/잡 failure → UNVERIFIED_REVISION(v2.19 는 ACTIVE/0) · (b)③ 8/8·
  mock 5/5 · 회귀 전건 일치 · 본 저장소 live PREVENTION_ABSENT(아티팩트 부재). **관측(에라타 후보)**: M-3
  «명령 위치(첫 단어)» 문언이 관용 `bash tools/tos_entry_harness.sh` 를 배제 → 정상 워크플로 과잉 차단(문언·
  fail-closed 극성) · M-1 스냅샷 진입 후 «캐시된 결합 base» 재사용 = 거짓 ABSENT(실행기 계보 — 계약 :7115-7119
  에 «스냅샷 안 재파생» 명시 제안) · M-5 스텝 «이름» 층은 name 위조에 열림(계약 자인). 서버 쓰기 0)
- `20260819-135916/U16-LEDGER-CHECK-V220.md` — **v2.20 격리 스냅샷 기층 위 전 규칙 실행기 — T-82 ⑮⑯⑱⑳ⓐⓑⓒ +
  회귀 ⑰ⓐⓑⓒ⑲⑪ + U-17 축 스냅샷** 손 실행 기록(비규범 부속·S-24 결속 `3d17ea66`. `u16-full-exec-v220.py`
  `b90920bd…`: `git clone --no-local --no-hardlinks`+GIT_NO_REPLACE_OBJECTS=1·청정성 canary(refs/replace ∅·grafts
  부재·㉠ 일치) 방출·rules_missing=∅. **⑮ R∥A ORDER_INVALID / g6 생략 대조군 NO_ROWS_CLEAR·0(실패 실증)** ·
  ⑯ 선형·⑱ 병렬 NO_ROWS_CLEAR/0(edge_seq 소비 대조군 MALFORMED 영구 차단) · ⑳ⓐ MALFORMED(v2.15 사전순 최소
  대조군 통과) · ⑳ⓑ PROVENANCE_UNVERIFIABLE(g1-first 대조군 3) · **⑳ⓒ TOCTOU: 스냅샷 없음 NO_ROWS_CLEAR·0
  (fail-open 재현) / 스냅샷 PROVENANCE_UNVERIFIABLE·1 = 정직 기준선 동일** · 정직 경계 (a) grafts orphan → clone
  rc=128 → UNVERIFIABLE · U-17 축 원본 graft `P⋠d` rc 1→0(--no-replace-objects 로도 0) vs 스냅샷 rc=1 유지·
  canary 청정 · 회귀 5/5. **관측**: N-1 :7124-7125 «㉠==%P 항상 성립 canary» vs E12(얕은 원본은 스냅샷도
  얕음 상속 → 문자 구현 대조군이 참 사유 |c_APP|=0 을 «기층 오염»으로 덮음 — 양쪽 fail-closed) · M-2 스냅샷
  비용 본 저장소 151초(.git 89M·2,228커밋). 계약 문언 fail-open 신규 0. 서버 쓰기 0)
- `20260819-135916/U17-PREVENTION-CHECK-V220-ADDENDUM.md` — **v2.20 에라타 `ae842cce` S-24 addendum**(§0
  결속 HEAD==`ae842cce`·계약 blob==ae842cce·개발계획 blob==3d17ea66 무변경·하니스 :4654-4754 `957bf49d…` · §1
  `s24-proof-ae.py`: hunk 7개(+7/-7 인라인) 여집합 8구간 자동 sha 대조 ∅ / 명명 절 닿음 7[(b)③ 실행 위치·⑬
  행·스냅샷 정직 경계 (b)·canary ㉢·심사/변경 이력·(B) 주] / 닿지 않음 13[하니스·T-82/T-81 종수·U-17-c·(a)·
  c_APP 수식·스냅샷 단일 방법·서버 스텝 대조·㉠ 주 판별·E12·U-16-d·⑬c] → 비영향 변이 `d101eb63` 그대로 ·
  §2: **ⓐ** `bash tools/…`·`./tools/…`·`env bash`·`/bin/bash`·`sh -e` 전부 BLOB_OK·e2e PREVENTION_ACTIVE/0 /
  echo·printf·cat 인자 red(⑬a) / `python tools/…`(집합 밖) red · **ⓑ** 스냅샷 안에만 grafts 심는 shim — 캐시
  base 는 canary `no`(거짓 ABSENT)·㉠-불가시 오염에서 LATE(정직값·오염 신호 상실) vs 재파생 판정기 canary `yes`
  → UNVERIFIABLE(㉡ 단독 발화) — U-17/U-16 동형 · **ⓒ** 얕은 원본→스냅샷에서 ㉠ 불일치 ㉢ 국소 귀속(사유
  |c_APP|=0) vs 문자 구현 «기층 오염» 오귀속 실증 · 회귀 ⑬a·⑭·⑮·⑯ 불변. **관측**: A-1 M-1 «fail-open»
  정밀화 — 유효 오염은 ㉠가 독립 검출하므로 종단 fail-open 은 ㉡ 유일 검출자 케이스(㉠-불가시)에서만 · A-2
  `--git-path` 는 `git -C <절대>` 에서도 상대 반환(ⓑ 문언이 둘 다 덮음). **fail-open/차단·문언 신규 0.**
  GET 1회(`x-github-request-id` 병기)·서버 쓰기 0)
- `20260819-193235/U17-PREVENTION-CHECK-V221.md` — **v2.21 T-84 ⑬(정본 불일치 클래스 a~g + 양성 + 정규화
  대조군)·⑭ + 회귀 ⑤⑨⑩⑪⑫ + #2 실측**(v2.20 재심 스탬프 sibling·비규범 부속·**S-24 결속 동결 `0528a919`**
  [계약·개발계획 blob==동결·후속 커밋 0·하니스 :4664-4764 `957bf49d…`]. 실행기 `u17-verify-v221.sh` `5410519e…`
  (v2.20 대비 술어 교체 1건)·`wfcanon-v221.py` `a5430e1a…` — **YAML 파싱=`yq`·대조=byte 비교뿐(자작 토크나이저
  폐기·운영자 지침 이행)**. 정본 A/B 는 계약 코드펜스에서 리터럴 앵커 추출 == 술어 상수 byte 동일. blob 22종
  기대 불일치 0: 양성·정규화 대조군 5(주석+빈 줄·trailing·CRLF·folded `>`·BOM) BLOB_OK / ⑬a~⑬g(echo·trailing
  주석·`|| true`·`false && …`·continue-on-error/if: always()/추가 메타 키·set +e/trap·**exit 0/exec true/가드
  exit**) 전부 UNVERIFIED_REVISION / NBSP red(ASCII 핀) / inline `;`·`env bash`·shell-no-set red. e2e: 양성
  ACTIVE/0 · **⑬g·⑬c UNVERIFIED_REVISION/1 ↔ 같은 seam v2.20 실행기 ACTIVE/0(심판 «회피» 자리 실증)** ·
  ⑭ UR/1 · 서버 mock 5종 일치 · 정본 B 런타임 OK/0·FAILED/1(두 칸 공백) · 회귀 전건. #2: UNCHK-008 owner_track
  `Phase 0`(:6228)·산문 2곳·U-17 «pre-D0-A 실체화»(:5480)·개발계획 :270-275 하니스 실체화 원문 병기 · 본 저장소
  실물(아티팩트·tos-gate.yml·하니스 파일·config) 전부 부재 · SIMULATED 순서 실증(하니스→아티팩트→워크플로+룰셋
  캡처 → D=∅ PREVENTION_ACTIVE/0 — 순서 무모순만). **관측(에라타 후보)**: P-2 정규화 규칙이 YAML 스칼라 표기
  (`|`/`>`)를 미언급 — 스텝 B(파이프라인 한 줄)를 folded 로 쓰면 정직 워크플로도 red(과잉 차단·fail-closed) →
  «정본은 literal block `|` 전제» 한 줄 제안. fail-open 신규 0. 본 저장소 PREVENTION_ABSENT. 서버 쓰기 0)
- `20260819-193235/U17-PREVENTION-CHECK-V221-ADDENDUM.md` — **v2.21 에라타 `65cf2635` S-24 addendum**(§0 결속
  HEAD==`65cf2635`·계약 blob==65cf2635·개발계획 blob==0528a919 무변경·하니스 :4664-4764 `957bf49d…` · §1
  `s24-proof-e1.py`: hunk 5개(+5/-5) 여집합 6구간 sha ∅ / 명명 절 닿음 5[정규화 규칙 :5497·⑬ 행·심사/변경
  이력·(B) 주] / 닿지 않음 14[정본 대조 도입 문장·서버 스텝·하니스·T-82/T-81·U-17-c·(a)(α)·c_APP·스냅샷 단일
  방법·UNCHK-008 Phase 0·pre-D0-A 실체화] · 정본 A/B 코드펜스 byte 동일 → 비영향 변이 `3e0f2429` 그대로 · §2:
  A `|`/folded+빈 줄 BLOB_OK(우연 일치 문언대로) · B `|` BLOB_OK · **B folded `>` → 접힘(`set -euo pipefail
  printf …` 한 줄) → UNVERIFIED_REVISION(계약 E1 대로 red)** · B folded+빈 줄 → 개행 보존 우연 일치 BLOB_OK(Q-1
  관측 — fail-open 아님: 관측량은 정본 byte) · B 인라인 `;` red · e2e ACTIVE/0·UR/1·UR/1 · 회귀 7종+⑬g 불변.
  판정 실행기·술어 sha 는 V221 과 동일(변경 0). **fail-open/문언 신규 0.** GET 1회·서버 쓰기 0)
- `20260819-193235/U17-PREVENTION-CHECK-V221-ADDENDUM-2.md` — **v2.21 에라타 2차 `7adc1246` S-24 addendum —
  stop-time Codex BLOCK #7 대응**(«스텝만 정본 대조 → `defaults.run.shell: "true {0}"` 가 정본 스텝 보존·미실행·
  success; V221 실행기가 defaults 미검사»). §0 결속 HEAD==`7adc1246`·하니스 `957bf49d…` · §1 hunk 5개 무변경
  ∅ / 닿음 6[(b)③ 잡 템플릿·정직 경계·⑬ 행·이력·(B)] / 닿지 않음 15 · 정본 A/B 펜스 byte 동일 → 비영향
  `3e0f2429`·`83f12afd` 그대로 · **실행기 `u17-verify-v221b.sh`/`wfcanon-v221b.py` — `job_template()` 신설**
  (ALLOWED_JOB_KEYS {runs-on, steps}·RUNS_ON_OK·ON_OK {pull_request, push}·PERM_OK {contents: read}·워크플로
  defaults/env 부재·steps 정확히 3·checkout 40-hex) · blob 18종 0 불일치: **⑬h defaults.run.shell 워크플로/잡/
  working-directory → UR ×3(V221 스텝만 술어는 BLOB_OK ×3)** · ⑬i 선행 GITHUB_PATH 스텝·후행 스텝·순서·checkout
  @v4·checkout 누락 → UR ×5 · ⑬j container/self-hosted/잡 env/워크플로 env/matrix/잡 uses/permissions write-all/
  on workflow_dispatch → UR ×8 · **e2e: ⑬h v221b UR/1 ↔ 같은 seam V221 실행기 PREVENTION_ACTIVE/0(BLOCK 실행
  재현)** · 회귀 7종·⑭ mock 불변. **신규 결함 후보 R-1 [fail-open 표면]**: 계약 :5482 «checkout@<40-hex SHA 핀 —
  계약 리터럴»인데 본문에 값 부재 → 형식만 검사 = 임의 포크 커밋 통과 → 에라타 3차 대상 · R-3 잡 키 집합이
  `name` 배제(과잉 차단 방향). 서버 쓰기 0)
- `20260819-193235/U17-PREVENTION-CHECK-V221-ADDENDUM-3.md` — **v2.21 에라타 3차 `c4d97118` S-24 addendum**
  (R-1 checkout SHA 핀). §0 결속 HEAD==`c4d97118`·하니스 `957bf49d…` · §1 hunk 6개 무변경 ∅ / 닿음 6[잡 허용 키·
  템플릿 step ①·⑬ 행·이력·(B)] / 닿지 않음 16 · 정본 A/B 펜스 byte 동일 → 비영향 그대로 · `wfcanon-v221c.py`
  (`CHECKOUT_SHA_OK={3d3c42e5…}`·`name` 허용) — **핀 SHA 양성 BLOB_OK·e2e ACTIVE/0 · 비-핀 40-hex(임의 포크 형식
  유효) UR ↔ v221b 대조군 BLOB_OK·e2e ACTIVE/0(R-1 fail-open 실증→닫힘)** · `@v7`/`@main` UR · 잡 `name:` 양성
  (R-3) · **핀 SHA live 재검증 GET 1회: `repos/actions/checkout/git/ref/tags/v7.0.1` → commit `3d3c42e5…` 계약
  리터럴과 직접 일치** · 회귀(2차 배터리 18·이식 7·⑭ 5) 불변. 관측 T-3 핀 1원소 = checkout 갱신 시 계약 개정·
  O-6(의도된 비용). **fail-open/문언 신규 0.** 서버 쓰기 0)
- `20260820-184748/U17-PREVENTION-CHECK-V222.md` — **v2.22 동결 `8ec22754` T-84 실행 증거**(5,214행).
  S-24 결속 실측(두 blob == 동결·후속 커밋 ∅·하니스 `957bf49d…`) · **추출 충실성 4/4 첫 시도 일치**
  (선행 판 §11 펜스 → v2.21 네 스크립트 sha 동일 = 이 판 «v2.21 대조군» 주장의 근거) · **blob 배터리 83
  픽스처 기대(사전 기입)≠실측 0건**(양성 12·차단 71 · v2.21 이 `BLOB_OK` 를 내던 자리 55 · v2.22 신규
  폐쇄 43 · ⑬a~g·NBSP·inline 회귀 0) · 9항 전건 실행: per-d 결속 반례·진입 `D=∅` 비-vacuity 음양쌍·
  C-1 두 순서/시퀀스 내부/정직 워크플로 발산 0(`construct` 대조군은 오검출)·F#1 3축 + **자기수복 하니스
  런타임 반사실(부작용 관측)**·anchor·`<<`·파서 버전·값 핀 3종·**동명 decoy 3케이스 = 케이스 ② 를
  `PREVENTION_ACTIVE` 로 «잔여» 실증(닫힘 표기 0)** · **역방향 fail-open 사냥 뮤테이션 25종 → 뒤집힘 19/
  불변 7(전건 이중·삼중 무력화로 벨트 귀속) = 죽은 검사 0·신규 fail-open 0** · T-84 **14종 불변**
  (`4+2+4+2+2` · 이번 대조군은 전부 ⑬⑭ 하위) · 잔여 15건 등재 · **에라타 후보 12건(high 4: EC-1 `if:`
  허용 분기가 닫힌 키 집합과 충돌해 도달 불가[v2.14 `G4` 사코드 분기 클래스] · EC-7 정직한
  `on: [pull_request, push]` 이 (b)② «정확히 1» 과 충돌해 과잉 차단 · EC-8 «정본 잡 템플릿» 에 코드펜스
  부재 = 비교 피연산자가 재-파생 · EC-9 순환 alias 순회에 종료 보장·«미종료» 상태값 부재[방문집합 없는
  순회 12초 미종료 실측·`yq` 자신 stack overflow·v2.21 은 우연한 fail-closed])** · GET-only·서버 쓰기 0)

- `20260820-184748/U17-PREVENTION-CHECK-V222-ADDENDUM.md` (기록 커밋 `4f3cb99d` 시점 7,548행 → 부속 에라타 v1.1 `a57c0f4d` · v1.2 `79576670` 후 **8,198행**) — **v2.22 에라타 1차~4차 재동결 `11e138a5`
  + 5차 `fd13ca26` S-24 addendum**. §0 결속(HEAD==`fd13ca26`·두 문서 워킹트리 blob == 동결본·후속
  커밋 ∅·하니스 `957bf49d…` 세 리비전 동일·개발계획 592행 무변경) · **§1 S-24 ① 3층 rc 0**:
  ① 여집합 증명(hunk 자동 추출 · 체인 36/1차~4차 34/5차 16 → **닿지 않은 구간 차이 0/0/0**;
  초판이 순수-삽입 hunk 경계 규칙 오류로 22/22/4 를 낸 것도 기록) · ② 명명 절 4부류 사전 선언
  (닿음/**신설**/닿지 않음/부재) **기대 불일치 0** — **5차의 «1·2·4단계 무접촉» 을 행 sha256 으로
  검증**(1·2·4단계 byte 동일 · 3단계만 상이 · blob 축 `yaml.parse()`·`ON_FILTER_OK` byte 동일) ·
  ③ 불변식(정본 A/B 두 digest 규약 모두 동일·펜스 324·상태값 10·T-84 14·파이프 3/3/14 ·
  `jobs:` 펜스 **0 → 1** = EC-8 실체화) · **§2 S-24 ②**: [신설] 15절을 계약이 지정한 대조군 문자와
  짝지어 실행 — **레인 1 실행기 3세대**(gen-0 동결본 / gen-1 1차~4차 / gen-2 5차 · 파생기가 **gen-1↔gen-2
  실행기 diff 를 6행으로 단언**) e2e **불일치 0** · **동결본 fail-open 4자리 실증**(L8 `completed_at:null`
  → `ACTIVE` · P5 `total_count` 불일치 → `ACTIVE` · P6 1페이지 독자[AMB-06] → `ACTIVE` · PU4 열거
  불완전 → `ACTIVE`) · **gen-1 과잉 차단 1자리 = stop-time BLOCK 재현**(L4 = ⑭(ㅍ-1) 실측 형상
  `044ef629…` 핀) → **gen-2 A** · ⓧ «두 독법이 다 결함» 을 strict(→ `ACTIVE` 영구 도달 불가)/loose(→
  발화 불가) 로 **각각 실행** · 계약이 이름 지어 놓은 **판별력 뮤테이션 전건 · 죽은 검사 0**
  (부수: **E-불변 canary 가 정의역 축소를 독립으로 잡는다** · (ㅍ-2)는 4단계 «와» 층 (2)로 **두 번**
  방어 = 계약 문언 정밀화 · (ㅎ)(iii)은 상태가 아니라 **transcript** 로 갈린다) · **레인 2 술어 2세대**
  (훅 37 · ⓟ/ⓠ 가 문언 정밀화가 아니라 **fail-open 3자리 폐쇄**였음을 실증[단독 anchor·anchor+alias·
  `on` 집합 밖 키가 동결본에서 전부 `BLOB_OK`] · 이동 셀 21 전건 인가 · 기존 83픽스처 이동 **0** ·
  차단값 방출점 22 → U-17-c 다섯 축 **전수 사상·비인가 0** · 뮤테이션 23 / 죽은 검사 0) ·
  **레인 3 GET-only 재측정**(계약이 «실측»이라 적은 값 전건 재현 — suite↔run 1:1·`filter=latest` 가
  run 은 접지 않음·`--slurp` `pages 2 counts [100,9]`·종단 `[]`·배수 경계·헤더/본문 동시 불가 ·
  PR #562 close→reopen→run `run_attempt 1` 까지 재현) · **§5 관측 10건**(문언 minor 4 = T-2 «`E` 불변»
  문장은 행이 편집됨[의미 무접촉·행 무접촉 구별] · T-3 `--include` 0회 계수 범위 비대칭 · T-4 «41블록»
  인용에 엔드포인트 부재 · T-5 (ㅍ-2) 이중 방어 → 판별력(iv) 층 한정 필요 / **이 부속 자신의 결함 3건**
  = T-6 술어 timeout ERE 를 파싱값에 걸어 `010`·`+5`·hex·`1_0` 통과[fail-open → 훅 H20/H21 폐쇄] ·
  T-7 검사기 라벨 naive grep 위양성 · **T-10 §1 증거기가 불일치를 찍고도 rc 0**[Codex stop-time 지적 —
  층 ③ 전체가 print-only · fail-closed 전환 후 재실행 rc 0 불변 · 개발계획 1행 주입 대조군으로 도달
  가능성 실증] / 위생 1 = T-9 / **철회 1 = T-8**[`SHELL_OK` 형제 쌍은 `:224` 의 «[2차 ⓢ] 파생·비지배»
  표시로 이미 닫혀 있었다 — 부속이 과대 계상] · 자기 적용 1 = T-1) · 부기 = 하지 않은 것
  (SIMULATED seam·ⓩ `queued` 미실측·페이지 경계 삽입/삭제 GET-only 불가·동일 모델 계열 한계).
  **판정이 아니다** — O-6 재결속 후 레인 B 재심. **서버 쓰기 0 · GET-only · 실 저장소 파일 생성 0.**

- `20260821-0150/U17-PREVENTION-CHECK-V222-ADDENDUM-2.md` — **v2.22 에라타 6차 동결 `5e96512e` S-24
  addendum**(기록 커밋 `44aa4aeb` 시점 640행 → 요약 계수 정정 `3b7dad09` 후 **647행**). §0 결속(계약 blob `29a08e5e3c83…` == **심판 3라운드가 approve 한 blob** · 개발계획
  `b2985a05215b…` 무변경 · 8,552행 · numstat 39/12 · `-U0` hunk 8 / `-U6` 6) · **§1 rc 0 — 네 층 전부 0**(결속 · 여집합 ·
  명명 절[닿음 8·닿지 않음 21·부분문자열 불변 9] · 불변식 «핀 대조» 포함) — **「문언 전용」을 소비 자리
  전건 byte 동일로 고정**(사다리 1·2·3·4단계·`E` 문장·스텝 메타·`yaml.parse()`·`ON_FILTER_OK`·`SHELL_OK`
  정의·정본 A/B·하니스 · T-84 행 «안» (ㅍ)(ㅎ)(ㅌ)(ㅋ)(ㅈ) 기대 문자열 불변) · **§2 분류 = 문언 3(ⓐⓑⓒ) +
  검증 실행 계약 1(ⓓ)** — ⓓ 는 **동결 후 재수행**을 결속했다(재인용 금지): **사다리 단위 실행** 정본
  `PREVENTION_UNVERIFIED_REVISION` ↔ 뮤턴트 `LADDER_OK` · **L3j 격리** 정본 UR ↔ 뮤턴트 A · **대조로 L3
  e2e 는 둘 다 UR = 판별력 미관측**(이 문언이 필요한 이유) · 판별력 뮤테이션 전건 **죽은 검사 0** ·
  §2-3 **동결 시점 계수 결속**(계약이 더는 적지 않는 값 — raw `--include` 7회/6행 · 명령 자리 **0 / `gh api`
  34행**) · §2-4 **ⓒ live 재측정**(심판이 네트워크 차단으로 못 채운 값 — `--paginate -i` 헤더 2블록·배열 2 ↔
  `--paginate` 헤더 0·병합 109원소 · `--slurp` `pages 2 counts [100,9]` · `?page=3` `[]`) · **§5 교훈 2**:
  자기참조 계수는 «값을 고치는» 방향으로 닫히지 않는다(3회 → 8회/7행 → 7회/6행) · «문언 전용» 분류는
  **소비 표면**을 봐야 결정된다(생산 술어 불변 ≠ 문언 전용). **계약 신규 fail-open 후보 0 · 이 부속 자신의
  결함 0.** 독립 심판 = Codex 3라운드(`needs-attention` → `needs-attention` → **`approve` findings 0**,
  드리프트 없음). 서버 쓰기 0 · GET-only.

## 향후 관행

**색인 항목의 «행수»는 «기록 커밋 시점» 값으로 결속해 적는다.** 증거 문서는 부속 에라타로 자라므로
커밋에 결속하지 않은 절대 행수는 후속 편집이 곧 반증한다(v2.22 6차 addendum 에서 `640행` 이 정정
커밋 하나로 stale 이 된 사례 · 같은 클래스로 5차 addendum 의 `7,548행` 도 v1.1/v1.2 후 8,198행).
**규약을 고정하는 것이 값을 고치는 것보다 먼저다** — 자기참조 계수는 값을 갱신하는 방향으로 닫히지
않는다(에라타 6차 ⓑ 의 일반형).

판정은 종전대로 `.omc/review/` 에 기록되고(digest 범위 밖 기록 원리·재심 체인
유지), **판정 방출 후** byte-동일 사본을 이 디렉터리에 추가해 커밋한다.
사본 추가는 편집을 동반하지 않는다.
