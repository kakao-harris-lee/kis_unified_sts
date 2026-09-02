# 레인 B 계획 «재심» — 41차 처분 판 (현행 버전 재심 #2)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 4831da3b22462f233bd2c3f2a6dbe2a4d7cab87f
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: f34ab815dafcda9dc0e9acd3b04c29e5cef78bbd2c81d689dee9effe839eefba
job_id: review-mtdztsx7-5h74t0
job_class: review            # adversarial-review = 게이트 적격 유일 경로
base: fc473f84
scope: branch
prior_verdict: docs/reviews/phase0-completion-contract/20260829-145254/verdict.md
bound_set_digest_at_review: c76f27ce7cb3bd7933bd041fef1be45ea17096b734aa4d0a43342a1e95eccdea
```

**게이트 판정: 통과 아님.**  `approve` 가 아니다 — D0/P-0 착수 불가 유지.
**findings 4 → 2 로 줄었다**(high 2/medium 2 → high 1/medium 1).

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "NO-SHIP. F4는 재현상 해소됐고 F1은 선례와 같은 정직한 미해소이며 S-26 카운터 0 진술도 맞다. 그러나 F2/F3은 여전히 회피에 가깝다. CAP-2와 C4C 모두 제공된 대조군은 red지만, 동등한 신규 표기를 우주 밖으로 빼면 검사기 rc 0이다.",
  "findings": [
    {
      "severity": "high",
      "title": "CAP-2 우주가 고정된 표기 자체에 의존해 신규 차단 자리를 놓친다",
      "body": "GUARD_RE는 한 줄 안에 축자 `1000`과 정확한 `PREVENTION_UNVERIFIABLE` 화살표가 모두 있는 식만 우주로 편입한다. 기존 구조 항 제거 4종과 새 `total_count > 1000` 자리는 직접 재현해 RULE-MISSING red였지만, 의미가 같은 `total_count > 1_000 → PREVENTION_UNVERIFIABLE` 신규 차단 자리를 주입하면 전체 check_document가 위반 0으로 green이었다. 즉 모집단 전체가 사라질 때만 PARSE가 나고, 신규 자리가 정규식 형상 밖이면 기존 네 자리 덕분에 조용히 누락된다. 향후 상한 차단을 추가하거나 표기만 정리해도 자기신고 전용 판정이 CAP-2를 우회할 수 있다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2244,
      "line_end": 2253,
      "confidence": 1,
      "recommendation": "축자 `1000`을 우주 식별자로 쓰지 말고 모든 살아 있는 상한 차단문을 구조적으로 먼저 파생한 뒤 상한·구조 항을 분류하라. 분류 불가능한 후보도 PARSE red로 처리하고 `1_000`, 줄바꿈, 상한 상수 참조 신규 자리 대조군을 추가하라."
    },
    {
      "severity": "medium",
      "title": "C4C가 계약이 금지한 형제 단계 표기를 검사하지 않는다",
      "body": "계약은 `다음 =` 형태와 그 형제 표기의 회차 리터럴을 금지한다고 선언하지만, STEP_ENUM_RE는 정확히 `다음 =` 또는 `현재 위치 =`만 인식한다. 직접 mutation에서 `다음 = 42차 → addendum-9`는 C4C red이고 술어형은 silent였으나, 같은 미래 지향 지시를 `다음 단계 = 42차 → addendum-9` 또는 `다음: 42차 → addendum-9`로 쓰면 전체 검사 결과가 위반 0이었다. 따라서 과잉 차단은 확인되지 않았지만 원래 F3의 stale 운영 순서를 단순 문구 변형으로 재도입할 수 있다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 1926,
      "line_end": 1930,
      "confidence": 0.99,
      "recommendation": "미래 지향 단계 필드의 형제 어휘를 선언적 정본에서 파생하거나, 회차/addendum 리터럴과 단계 화살표의 구조적 공존을 검사하라. 두 우회 표기를 필수 red mutation으로 추가하라."
    }
  ],
  "next_steps": [
    "CAP-2와 C4C의 모집단 밖 mutation을 먼저 red로 만든다.",
    "수정 후 기존 4개 CAP-2 대조군, C4C 양방향 대조군, R-3 60718de8 재현을 다시 실행한다.",
    "F1은 해소로 계상하지 말고 u17 의미 정합과 PREVENTION_ACTIVE 완료 전까지 D0/P-0 차단을 유지한다."
  ]
}
```

---

## 수용검사 (오케스트레이터 = Claude)

**채택 2 · 기각 0 · 팬텀 0.**  두 건 모두 **오케스트레이터가 독립 재현**했다.

| finding | 실측 재현 | 처분 |
| --- | --- | --- |
| **F1** (high) CAP-2 우주가 표기에 의존 | ✔ `total_count > 1_000` · `total_count > 1,000` 신규 차단 자리 주입 → **둘 다 위반 0(탈출 확인)** | **채택** |
| **F2** (medium) C4C 형제 표기 미검사 | ✔ «다음 단계 = 42차 → addendum-9» · «다음: 42차 →» 주입 → **둘 다 위반 0(탈출 확인)** | **채택** |

**직전 4건에 대한 심판 판정**: **F4 = 해소**(R-3 정밀화가 재현으로 확인됨) ·
**F1 = 정직한 미해소**(「선례와 같은 형식」 — 40차 판의 R-F1 처분 형식을 인정) ·
**S-26 카운터 0 진술 = 맞다** · **F2·F3 = 여전히 회피에 가깝다**(위 두 건이 그 사유).

**비협상 규칙 대조**: 두 권고 어느 것도 `CLAUDE.md` 비협상 8항과 배치되지 않는다. **배치 0**(16판 연속).

## 이 재심의 요지

**「대조군이 red 인 것」과 「모집단이 닫힌 것」은 다른 주장이다.**  41차는 앞의 것을 증명하고
뒤의 것을 주장했다 — 대조군 넷·둘이 전부 red 였는데도 **모집단 밖 신규 표기**가 조용히 통과했다.
이것은 이 아크가 이미 아는 결함 클래스(**census 는 어휘 축도 폐쇄를 증명해야 한다**)가
**새로 만든 축 «안»에서 재발**한 것이다.
