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
    .omc/review docs/reviews/phase0-completion-contract
  ```

  (`U15-ENTRY-CHECK.md` 는 **추적 전용 실행 증거**라 운영 원본이 없다 — 아래
  "실행 증거 아티팩트" 절. 제외 목록은 이 README 가 유일 소스다.)

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

## 수록 범위 (26건)

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
  직후 stop-time 적발로 심사 미도달. 다음 개정의 입력)

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

## 향후 관행

판정은 종전대로 `.omc/review/` 에 기록되고(digest 범위 밖 기록 원리·재심 체인
유지), **판정 방출 후** byte-동일 사본을 이 디렉터리에 추가해 커밋한다.
사본 추가는 편집을 동반하지 않는다.
