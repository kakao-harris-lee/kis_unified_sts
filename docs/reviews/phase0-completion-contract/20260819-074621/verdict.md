# verdict — 레인 B (계획 심판) · v2.18 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: 81d532ffb3ef379be48e1ae5c1163c45ae13d1cb
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: ec8324e2af4fc4110be4cf6051179263c0bc2ba162aeb4b136cb016149ae7585
reviewed_version: v2.18 (6,998행) — 동결 5f4b7cfd · 증거 7a146466 · 에라타 재동결 feb91d60 · S-24 addendum 540ff0e3 · INDEX 47bb7966 · 재결속 81d532ff
findings: 6                        # high 3 / medium 3 — 직전 F1 부분해소 · F2 부분해소 · F3 해소됨(계약 수준) · F4 부분해소 · F5 회피 · 신규 2 (GH_HOST host 미결속 high · 두 결속 계획 Phase 0/1 선행관계 충돌 medium)
prior_verdict: .omc/review/20260819-002145/verdict.md   # v2.14 재심
mode: A (adversarial-review, --scope working-tree, --wait), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-msz98lpw-xgn5t8 / codex thread 01a01710-7b5e-76d0-838a-ff8f04ebf5a2 (turn 01a01710-7cac-7fc2-ae3f-5ed6f0eae8e3)
     # 1회 디스패치 정상 완료(8m 19s) — 재시도 불요 · parseError null · companion 1.0.6
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **불변**(HEAD·plan_scope_digest·
내용-only digest `c037e48c…` == 아티팩트 보유값 `OQ-11-DISPOSITION.md:10`). Codex 도
결속 일치와 `5f4b7cfd→7a146466→feb91d60→540ff0e3→47bb7966→81d532ff` 순서를 독립 확인
(stderr 추적: 두 경로 shasum 재계산·`OQ-11-DISPOSITION.md` 직접 조회). 재결속은
v2.18 에라타 재동결 내용에 대해 1회(`81d532ff`); v2.15~v2.17 은 승인 표면을 가진 적 없음.

## 처분

**직전 5건: F1 부분해소 · F2 부분해소 · F3 해소됨(계약 수준) · F4 부분해소 · F5 회피**
— **아크 누적 해소 5**(F3 = 다섯 번째). `CLAUDE.md` 비협상 직접 충돌 **없음**(11판 연속).
"회피" 판정 1건(F5): `row_ref` 를 없앴으나 같은 비단수 원시값 `c_APP(a)` 가 U-16-c·g5·g6
소비처에 단수 정의로 남아 동일 raw 승인 행의 형제 브랜치 독립 도입에서 선택 규칙 부재 —
증거 실행기가 «복수면 사전순 최소»로 임의 보충(U16-LEDGER-CHECK.md:37) → «원인째 소멸»은
표면 이동. F1 은 계약 자신이 :5305-5325 에서 «보호 off → 체크 통과 → 머지 → 재활성» 창을
**닫지 못한다**고 적으면서 (B) 표 :4326 이 «완료 가능성 자체를 막는다»고 주장 — 진입·완료
두 live 조회 사이의 창에서 양쪽 ACTIVE 이므로 주장 불성립. F2 는 활성 D0A-FIRST 절
:3539/:3549 가 «모호 없이 한 커밋»·`git log --diff-filter=A` 를 여전히 규범으로 두어
U-15-g-1 구조 정의 D(:4858)와 병존(S-22 클래스 — 에라타 E1 이 배격한 명령이 앞선 절에
잔존). F4 는 T-82 ⑱ 행 :2918 이 폐지된 `edge_seq` 기재(«각각 seq=1 부여»)를 입력으로
지시하고 손 실행기가 계약 밖 규칙(사전순 최소·상태 우선순위)을 자체 선언. 신규 high:
live 조회가 host 없는 `gh api repos/...`(:5120-5126)라 GH_HOST override 로 타 host
응답이 PREVENTION_ACTIVE 를 만들 수 있음(Codex 가 `GH_HOST=example.invalid` 프로브
실측·T-84 ⑩은 remote URL 만 검사). 신규 medium: 개발계획 :275-297 Phase 1 작업 7·종료조건
(required CI jobs·branch protection 증거) vs 계약의 D0-A 착수 선행조건 승격 — 두 결속
문서가 같은 조건의 단계 소유자를 다르게 규정(계약이 «별도 사이클·운영자 소관»으로
정직 표기한 그 항목).

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

NO-SHIP. HEAD 81d532ff, commit order, clean target-plan diff, and independently recomputed bound_set_digest c037e48c… all match. Prior findings: F1 부분해소, F2 부분해소, F3 해소됨(계약 수준), F4 부분해소, F5 회피. S-24 is adequate only for its declared errata; U-17’s nine-state ordering itself is deterministic. Criteria: (1) 단계·의존성 불충족, (2) 숨은 가정 불충족, (3) 검증 가능성 불충족, (4) 실패·롤백 불충족, (5) 범위 이탈·과잉 설계 해당 없음, (6) CLAUDE.md 비협상 직접 충돌 해당 없음, (7) 누락 불충족.

Findings:
- [high] F1 부분해소 — 보호 해제 창이 여전히 정상 완료로 세탁된다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5305-5325)
  계약은 보호를 끈 채 tos-gate를 성공시켜 merge한 뒤 다시 켜면 정상 check-run과 merged PR이 남고, U-17이 merge 시점의 강제를 증명하지 못한다고 명시한다. 진입·완료 시점의 두 live 조회 사이에 이 창을 만들면 양쪽 조회는 ACTIVE이고 리비전 검사도 성공하므로 §4326의 ‘완료 가능성 자체를 막는다’는 주장은 성립하지 않는다. 공격·운영 실수 모두 Phase 0 완료로 오인될 수 있다.
  Recommendation: 이 정확한 protection-off/merge/re-enable 변이가 권위 있는 연속성 소비자에서 fail-closed 되기 전에는 F1을 해소로 계수하거나 Phase 0 완료를 허용하지 말라.
- [high] 정본 host 핀이 실제 gh API 조회 host를 결속하지 않는다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5120-5126)
  계약은 github.com 대상을 핀하지만 모든 live 호출을 hostname 없는 `gh api repos/...` 및 `gh api apps/github-actions`로 규정한다. 로컬 검증에서 GH_HOST를 바꾸면 같은 명령이 지정된 다른 host의 `/api/v3`를 호출했다. 따라서 github.com remote가 존재해도 환경 설정이나 래퍼가 다른 GitHub Enterprise/mock host의 보호·앱 응답을 제공해 PREVENTION_ACTIVE를 만들 수 있다. 이는 단순 악의적 소비자뿐 아니라 drift한 CI 환경에서도 발생하는 인증·trust-boundary 결함이며 T-84 ⑩은 remote URL 불일치만 검사한다.
  Recommendation: 판정 API host가 계약 핀과 일치함을 소비자가 검증하고, GH_HOST override 변이가 PREVENTION_TARGET_MISMATCH 또는 UNVERIFIABLE로 실패하는 증거가 생길 때까지 승인하지 말라.
- [high] F2 부분해소 — 폐기된 단수 D0A-FIRST 파생 규범이 활성 본문에 남아 있다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3521-3550)
  U-15-g는 구조적 집합 D와 `|D|>1` 차단을 정의하지만, 앞선 활성 D0A-FIRST 절은 여전히 ‘모호 없이 한 커밋’이라고 단정하고 `git log --diff-filter=A`를 기계 파생법으로 지정한다. 바로 그 명령은 후속 절이 byte-identical 병렬 추가·merge에서 한 도입만 반환해 CLEAR 우회를 만든다고 배격한다. 구현자가 먼저 나오는 규범을 따르면 MULTIPLE_INTRODUCTIONS가 사라진다.
  Recommendation: 모든 활성 소비 표면이 동일한 구조적 D를 사용하고 gg/gu/uu 변이가 실제 전체 소비자를 차단한다는 증거가 없으면 F2를 해소로 계수하지 말라.
- [medium] F4 부분해소 — 양성 증거가 현행 정본 테스트와 계약 밖 규칙에 의존한다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:2918)
  현행 T-82 ⑱은 edge_seq 필드를 제거한 스키마와 달리 두 브랜치가 각각 seq=1을 부여한다고 계속 지시한다. 실행 부속은 이를 ‘edge_seq 필드 없음’으로 바꾸고, 계약에 없는 복수 c_APP 사전순 최소 선택과 상태 우선순위를 자체 선언한 손 실행기다(U16-LEDGER-CHECK.md:34-48). 전 규칙을 열거했다는 사실만으로 입력 의미와 결과 선택이 규범에 결속되지는 않는다. 따라서 기존 부분-표면 green은 개선됐지만 현행 계약의 실제 소비 증명은 아니다.
  Recommendation: 정본 T-82 입력과 현행 스키마가 일치하고, 추가 해석 규칙 없는 실제 소비자가 ⑱을 NO_ROWS_CLEAR로 판정할 때까지 F4는 부분해소로 유지하라.
- [medium] F5 회피 — row_ref 삭제 후에도 단수 c_APP 선택 문제가 판정 경로에 남아 있다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:6777-6784)
  계약은 `c_APP(a)`를 여전히 단수 ‘승인 행을 도입한 커밋’으로 정의하고 U-16-c·g5·g6에서 소비하지만, 동일 raw 승인 행이 형제 브랜치에서 독립 도입된 경우의 선택·집합 양화·복수 차단 규칙이 없다. 한 도입은 전이의 조상이고 다른 도입은 형제인 DAG에서는 선택에 따라 NO_ROWS_CLEAR와 APPROVAL_AFTER/ORDER_INVALID가 갈린다. 증거 실행기는 이 빈자리를 사전순 최소로 임의 보충했다. row_ref만 없애고 같은 비단수 원시값을 다른 소비처에 남겼으므로 ‘원인째 소멸’은 표면 이동이다.
  Recommendation: 동일 승인 행의 복수 구조 도입을 결정적으로 차단하거나 모든 관련 소비 규칙에 일관된 집합 의미가 검증되기 전에는 F5를 해소로 세지 말라.
- [medium] 두 결속 계획의 Phase 0→Phase 1 선행관계가 서로 충돌한다 (docs/plans/2026-08-11-tos-completion-development-plan.md:275-297)
  개발계획은 Phase 0 종료 후 Phase 1 작업 7에서 required CI jobs를 추가하고 Phase 1 종료 때 branch-protection TOS gate 증거를 요구한다. 반면 계약은 그 조건을 Phase 0 D0-A 착수 전 PREVENTION_ACTIVE로 승격했고, 현재 main에 tos-gate job이 없어 INSUFFICIENT라고 확인하면서 개발계획 개정은 별도 운영자 사이클로 남겼다. 두 문서를 함께 실행하면 한 문서는 Phase 1 산출물로 배치한 조건을 다른 문서가 Phase 0 착수 조건으로 소비하므로 현재 계획 집합은 그대로 착수 가능하지 않다.
  Recommendation: 두 결속 문서가 동일한 단계 소유자와 선행 순서를 규정하고 그 조건이 현재 실행 가능하다는 증거가 생길 때까지 Phase 0 착수를 승인하지 말라.

Next steps:
- F1 연속성 창과 GH_HOST override를 실제 권위 소비자에 대한 필수 음성 변이로 검증한다.
- 구조적 D, 복수 c_APP, T-82 ⑱을 현행 전체 소비 경로 하나에서 함께 재검증한다.
- 두 결속 계획의 Phase 0/Phase 1 선행관계가 일치한 새 리비전에 다시 결속해 재심한다.
```

### 구조화 JSON 원문 (`result review-msz98lpw-xgn5t8 --json` · `confidence` 포함 · verbatim)

```json
{
  "verdict": "needs-attention",
  "summary": "NO-SHIP. HEAD 81d532ff, commit order, clean target-plan diff, and independently recomputed bound_set_digest c037e48c… all match. Prior findings: F1 부분해소, F2 부분해소, F3 해소됨(계약 수준), F4 부분해소, F5 회피. S-24 is adequate only for its declared errata; U-17’s nine-state ordering itself is deterministic. Criteria: (1) 단계·의존성 불충족, (2) 숨은 가정 불충족, (3) 검증 가능성 불충족, (4) 실패·롤백 불충족, (5) 범위 이탈·과잉 설계 해당 없음, (6) CLAUDE.md 비협상 직접 충돌 해당 없음, (7) 누락 불충족.",
  "findings": [
    {
      "severity": "high",
      "title": "F1 부분해소 — 보호 해제 창이 여전히 정상 완료로 세탁된다",
      "body": "계약은 보호를 끈 채 tos-gate를 성공시켜 merge한 뒤 다시 켜면 정상 check-run과 merged PR이 남고, U-17이 merge 시점의 강제를 증명하지 못한다고 명시한다. 진입·완료 시점의 두 live 조회 사이에 이 창을 만들면 양쪽 조회는 ACTIVE이고 리비전 검사도 성공하므로 §4326의 ‘완료 가능성 자체를 막는다’는 주장은 성립하지 않는다. 공격·운영 실수 모두 Phase 0 완료로 오인될 수 있다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 5305,
      "line_end": 5325,
      "confidence": 0.99,
      "recommendation": "이 정확한 protection-off/merge/re-enable 변이가 권위 있는 연속성 소비자에서 fail-closed 되기 전에는 F1을 해소로 계수하거나 Phase 0 완료를 허용하지 말라."
    },
    {
      "severity": "high",
      "title": "정본 host 핀이 실제 gh API 조회 host를 결속하지 않는다",
      "body": "계약은 github.com 대상을 핀하지만 모든 live 호출을 hostname 없는 `gh api repos/...` 및 `gh api apps/github-actions`로 규정한다. 로컬 검증에서 GH_HOST를 바꾸면 같은 명령이 지정된 다른 host의 `/api/v3`를 호출했다. 따라서 github.com remote가 존재해도 환경 설정이나 래퍼가 다른 GitHub Enterprise/mock host의 보호·앱 응답을 제공해 PREVENTION_ACTIVE를 만들 수 있다. 이는 단순 악의적 소비자뿐 아니라 drift한 CI 환경에서도 발생하는 인증·trust-boundary 결함이며 T-84 ⑩은 remote URL 불일치만 검사한다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 5120,
      "line_end": 5126,
      "confidence": 0.98,
      "recommendation": "판정 API host가 계약 핀과 일치함을 소비자가 검증하고, GH_HOST override 변이가 PREVENTION_TARGET_MISMATCH 또는 UNVERIFIABLE로 실패하는 증거가 생길 때까지 승인하지 말라."
    },
    {
      "severity": "high",
      "title": "F2 부분해소 — 폐기된 단수 D0A-FIRST 파생 규범이 활성 본문에 남아 있다",
      "body": "U-15-g는 구조적 집합 D와 `|D|>1` 차단을 정의하지만, 앞선 활성 D0A-FIRST 절은 여전히 ‘모호 없이 한 커밋’이라고 단정하고 `git log --diff-filter=A`를 기계 파생법으로 지정한다. 바로 그 명령은 후속 절이 byte-identical 병렬 추가·merge에서 한 도입만 반환해 CLEAR 우회를 만든다고 배격한다. 구현자가 먼저 나오는 규범을 따르면 MULTIPLE_INTRODUCTIONS가 사라진다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 3521,
      "line_end": 3550,
      "confidence": 0.99,
      "recommendation": "모든 활성 소비 표면이 동일한 구조적 D를 사용하고 gg/gu/uu 변이가 실제 전체 소비자를 차단한다는 증거가 없으면 F2를 해소로 계수하지 말라."
    },
    {
      "severity": "medium",
      "title": "F4 부분해소 — 양성 증거가 현행 정본 테스트와 계약 밖 규칙에 의존한다",
      "body": "현행 T-82 ⑱은 edge_seq 필드를 제거한 스키마와 달리 두 브랜치가 각각 seq=1을 부여한다고 계속 지시한다. 실행 부속은 이를 ‘edge_seq 필드 없음’으로 바꾸고, 계약에 없는 복수 c_APP 사전순 최소 선택과 상태 우선순위를 자체 선언한 손 실행기다(U16-LEDGER-CHECK.md:34-48). 전 규칙을 열거했다는 사실만으로 입력 의미와 결과 선택이 규범에 결속되지는 않는다. 따라서 기존 부분-표면 green은 개선됐지만 현행 계약의 실제 소비 증명은 아니다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 2918,
      "line_end": 2918,
      "confidence": 0.96,
      "recommendation": "정본 T-82 입력과 현행 스키마가 일치하고, 추가 해석 규칙 없는 실제 소비자가 ⑱을 NO_ROWS_CLEAR로 판정할 때까지 F4는 부분해소로 유지하라."
    },
    {
      "severity": "medium",
      "title": "F5 회피 — row_ref 삭제 후에도 단수 c_APP 선택 문제가 판정 경로에 남아 있다",
      "body": "계약은 `c_APP(a)`를 여전히 단수 ‘승인 행을 도입한 커밋’으로 정의하고 U-16-c·g5·g6에서 소비하지만, 동일 raw 승인 행이 형제 브랜치에서 독립 도입된 경우의 선택·집합 양화·복수 차단 규칙이 없다. 한 도입은 전이의 조상이고 다른 도입은 형제인 DAG에서는 선택에 따라 NO_ROWS_CLEAR와 APPROVAL_AFTER/ORDER_INVALID가 갈린다. 증거 실행기는 이 빈자리를 사전순 최소로 임의 보충했다. row_ref만 없애고 같은 비단수 원시값을 다른 소비처에 남겼으므로 ‘원인째 소멸’은 표면 이동이다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 6777,
      "line_end": 6784,
      "confidence": 0.94,
      "recommendation": "동일 승인 행의 복수 구조 도입을 결정적으로 차단하거나 모든 관련 소비 규칙에 일관된 집합 의미가 검증되기 전에는 F5를 해소로 세지 말라."
    },
    {
      "severity": "medium",
      "title": "두 결속 계획의 Phase 0→Phase 1 선행관계가 서로 충돌한다",
      "body": "개발계획은 Phase 0 종료 후 Phase 1 작업 7에서 required CI jobs를 추가하고 Phase 1 종료 때 branch-protection TOS gate 증거를 요구한다. 반면 계약은 그 조건을 Phase 0 D0-A 착수 전 PREVENTION_ACTIVE로 승격했고, 현재 main에 tos-gate job이 없어 INSUFFICIENT라고 확인하면서 개발계획 개정은 별도 운영자 사이클로 남겼다. 두 문서를 함께 실행하면 한 문서는 Phase 1 산출물로 배치한 조건을 다른 문서가 Phase 0 착수 조건으로 소비하므로 현재 계획 집합은 그대로 착수 가능하지 않다.",
      "file": "docs/plans/2026-08-11-tos-completion-development-plan.md",
      "line_start": 275,
      "line_end": 297,
      "confidence": 0.97,
      "recommendation": "두 결속 문서가 동일한 단계 소유자와 선행 순서를 규정하고 그 조건이 현재 실행 가능하다는 증거가 생길 때까지 Phase 0 착수를 승인하지 말라."
    }
  ],
  "next_steps": [
    "F1 연속성 창과 GH_HOST override를 실제 권위 소비자에 대한 필수 음성 변이로 검증한다.",
    "구조적 D, 복수 c_APP, T-82 ⑱을 현행 전체 소비 경로 하나에서 함께 재검증한다.",
    "두 결속 계획의 Phase 0/Phase 1 선행관계가 일치한 새 리비전에 다시 결속해 재심한다.",
    ""
  ]
}
```

> 포워더 전달 사항(판정 무개입): JSON `next_steps` 4번째 원소는 빈 문자열 `""` — 렌더 텍스트가
> 생략했을 뿐 내용 손실 없음. Finding #2(GH_HOST)는 Codex 가 stderr 추적상 실제 프로브
> (`GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api gh api repos/a/b…`, exit 1)로
> 뒷받침. 결속값 독립 재계산 실측. 에러·재시도 0.

---

# 수용검사 (오케스트레이터) — **채택 6 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high (F1 부분해소) | `:5305-5325` [B2 — v2.17] «보호 꺼진 창» 철회 절 실재 — «보호 off 상태에서 체크는 통과한 리비전 착지 … **닫지 못한다**»(:5321-5324) 리터럴 확인. `:4326` (B) 표 F1 행 «**완료 가능성 자체를 막는다**» 리터럴 확인 — 두 진술이 문서 내부에서 갈린다. U-17 (a) 는 진입 시점 live·§11 은 완료 판정 시점 live(:3422) — 두 조회 사이 창은 계약 어느 술어도 소비하지 않음 확인 | 채택 |
| 2 | high (신규) | `:5120-5126` (a) 조회 4종 전부 host 없는 `gh api repos/{owner}/{repo}/…` 리터럴 확인. 계약 핀은 host+owner/repo 인데 조회 명령은 host 를 `gh` 환경(`GH_HOST`)에 위임 — T-84 ⑩(타 원격·타 호스트)은 `git remote -v` 대조만. Codex 실측 프로브(GH_HOST override → 타 host `/api/v3` 호출) 재현 가능한 클래스 | 채택 |
| 3 | high (F2 부분해소) | `:3521-3550` D0A-FIRST 명명 절(v2.12 신설) 실재 — `:3539` «**모호 없이 한 커밋**으로 관측된다»·`:3549` «파일 도입 커밋은 `git log --diff-filter=A -- <path>` 로 파생되고» 리터럴 확인. `:4858` U-15-g-1 «`D` = **구조 정의**»·`:4872` 에라타 E1 이 그 명령을 배격 — **S-22 클래스**(폐기 정의가 앞선 활성 절에 잔존; 토큰 `diff-filter=A` 는 :5501/:5529/:5534/:5574 하니스·T 절에도 잔존 — 그중 :5503 은 «부재 확인용 편의 표기» 주석 있음, 나머지는 심판 재판정 대상) | 채택 |
| 4 | medium (F4 부분해소) | `:2918` T-82 행 ⑱ «두 브랜치가 각각 `seq=1` 을 부여한 상태로 merge 해 MALFORMED 를 만든 뒤» 리터럴 확인 vs `:6575` «`edge_seq` 기재 필드를 «스키마에서 제거»한다» — 입력 지시가 폐지 스키마 전제. `U16-LEDGER-CHECK.md:34-48` «독해 선언(계약이 리터럴로 고정하지 않은 자리)» — `:37` c_APP «복수면 사전순 최소»·`:43-45` 상태 우선순위 «실행기 선언 — 계약 U-16-d 는 전순서를 두지 않는다» 확인 | 채택 |
| 5 | medium (F5 회피) | `:6777-6784` U-16-c «c_APP(a) = 승인 행 a 를 **도입한 커밋**» 단수 정의 실재·U-16-c/g5/g6 소비 확인. 동일 raw 행 형제 브랜치 독립 도입 시 집합/선택/차단 규칙 부재 — 증거 실행기 :37 이 «사전순 최소»로 보충한 것이 그 빈자리의 증거. F5 처분 «원인째 소멸»(:4330)은 row_ref 축만 소멸 | 채택 |
| 6 | medium (신규) | 개발계획 `:275-297` Phase 1 작업 7 «CI required job에 … TOS tests …» · 종료 조건 «GitHub branch protection에서 TOS gate required 상태 증거 보존» 실재. 계약 U-17 은 같은 조건을 D0-A 착수 선행조건으로 승격(v2.15 변경 이력 :196 «개발계획 개정은 별도 사이클·운영자 소관으로 정직 표기»). 두 결속 문서 간 단계 소유자 불일치 실재 — 직전 세션 운영자 판단 항목 ③과 동일 | 채택 (**운영자 게이트** — 개발계획 개정은 저작자가 계약 측에서 선언만 할 수 있고 정식 개정은 운영자 소관) |

비협상 대조: 선물 대칭·실계좌 증거금·EOD 청산·ClickHouse·RL/TFT·하드코딩·Redis DB/TTL·비KST — 6건 어느 것도 배치 권고 아님.

## 관측 (finding 아님)

- **F3 = 아크 5번째 «해소됨»**(계약 수준) — C_R 을 approved_at_head blob 도입 지점으로 정의한 것이 인정됐다. 실제 소비자 실행 증거는 여전히 D0-A 이후.
- **S-22 클래스가 두 곳에서 또 재발**(#3 D0A-FIRST 절·#4 T-82 ⑱ 행): 폐기한 정의(`diff-filter=A` 리터럴 파생·`edge_seq` 기재)의 **앞선 활성 절**을 sweep 이 못 봤다. 이번 판 focus 가 (f) 로 지목한 (B) 표 «실행 증거 없음» 열은 Codex 가 finding 으로 올리지 않았다(별도 확인: :4324-4330 «없음/미실행» 문구는 v2.15 저작 시점 그대로 — S-22 후보로 저작자 스윕 대상).
- **F1 저작 경로(심판 Recommendation)**: protection-off → 체크 통과 → 머지 → 재활성 창을 **연속성 소비자**가 fail-closed 로 잡아야 한다 — 후보: (i) 룰셋/보호 `updated_at` 관측을 진입 시점 값과 완료 판정 시점 값으로 결속(변경 시 → 재심사)·(ii) D0A-FIRST 이후 착지한 모든 정본 브랜치 커밋의 PR/check-run 리비전 검증(전 커밋 순회, 성능 주 :4864)·(iii) 공개 REST 로 증명 불가한 «머지 시점 강제»는 정직 경계로 남기되 §11 완료 허용값에서 그 창의 존재를 **UNVERIFIABLE** 로 접어 완료 차단. 어느 쪽이든 «완료 가능성 자체를 막는다» 주장은 철회.
- **#2 저작 경로**: 조회 host 를 계약 핀에서 파생해 명령에 명시(`gh api --hostname github.com …` 또는 `GH_HOST` 를 핀 host 로 강제 설정 후 `gh api` — 응답 헤더/`X-GitHub-Request-Id`·`gh auth status --hostname` 대조)·`GH_HOST`/`GH_ENTERPRISE_TOKEN` override 변이를 T-84 ⑪로(TARGET_MISMATCH 또는 UNVERIFIABLE).
- **#3 저작 경로**: D0A-FIRST 절 :3539/:3549 를 U-15-g-1 구조 정의 참조로 전환(«재기술은 stale 원천 — 참조로 바꿔라» v2.17 교훈의 적용)·`diff-filter=A` 리터럴 잔존 전수 스윕(:5501/:5529/:5534/:5574 — 편의 표기와 판정 소비를 구별해 명시).
- **#4 저작 경로**: T-82 ⑱ 입력을 현행 스키마(`edge_seq` 기재 없음·소비자 파생)로 재기술 — 픽스처는 «두 브랜치가 각각 승인 행 도입 후 머지». 상태 전순서(U-16-d)와 c_APP 복수 규칙은 #5 와 함께 계약에 고정.
- **#5 저작 경로**: `c_APP(a)` 를 집합 구조 정의(C_R·D 와 동형 — «플래그 의존 클래스는 동형 정의마다 재발» 교훈)로 두고 |c_APP|>1 → MALFORMED(동일 승인 행 병렬 도입 차단) 또는 ∀/∃ 양화를 U-16-c/g5/g6 각각에 명시.
- **#6**: 운영자 게이트 — 개발계획 Phase 1 작업 7·종료조건 항목을 D0-A 착수 선행조건으로 이관하는 정식 개정(bound_paths 안이라 O-6 재결속 동반).

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
