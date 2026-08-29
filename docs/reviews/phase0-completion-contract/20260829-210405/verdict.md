# 레인 B 계획 «재심» — 46차 처분 판 (재심 #7)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 4fe90b43
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: b32a333cc915aca2a70b225559d8cd9470abc8a8495fe2138d5a4d7e1ec69be0
job_id: review-mtec1erb-ah6x54
job_class: review
base: b924b509
scope: branch
elapsed: 3m 50s
prior_verdict: docs/reviews/phase0-completion-contract/20260829-205123/verdict.md
```

**게이트 판정: 통과 아님.**  findings **2 → 1**.

**심판이 확인한 것**: 46차의 두 처분(셀 이어붙임 · 괄호 닫기)과 **교정한 대조군이 실측상
작동**한다.  그리고 **「명시 잔여 다섯의 단순 재확인은 finding 으로 세지 않았다」** — 잔여
등재가 판정에서 실제로 «(b)» 로 취급된 첫 자리다.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 불가. 46차의 두 명시 처분과 교정된 대조군은 실측상 작동하지만, (a) 신규 material 우회 1건이 남아 S-26 ②의 신규-material-0 카운터를 시작할 수 없다. 명시 잔여 다섯의 단순 재확인은 finding으로 세지 않았다.",
  "findings": [
    {
      "severity": "high",
      "title": "(a) HTML 주석 속 식별자가 비면제 규범 셀 전체를 면제한다",
      "body": "`_scan_chunks`는 HTML 주석을 제거하기 전에 원문 셀에서 `CONTROL_ID_RE.search(c)`를 수행한다. 실제 T-84 행에 `신규 규범 <!-- (ㅎ-4) --> total_count > 1000 → PREVENTION_UNVERIFIABLE` 셀을 붙이자 식별자는 렌더링되지 않는데도 셀 전체가 제거되어 `_cap_guard_sites`의 T-84 발화가 0건이었다. 미닫힘 `(ㅎ-4x` 대조는 정상적으로 발화했다. 이는 잔여 1의 ‘대조군 식별자를 가진 셀 안’이 아니라, 검사기 자신이 비가시 HTML 주석을 식별자로 승격해 면제를 문언보다 넓힌 신규 직접 주입 우회다. 132종 대조군에도 이 경계가 없다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2372,
      "line_end": 2373,
      "confidence": 0.99,
      "recommendation": "식별자 판정 전에 HTML 주석을 제거하고, 남은 가시 셀 텍스트에서만 닫힌 식별자 형상을 인정하라. 실제 T-84 행에 `<!-- (ㅎ-4) -->`와 규범 술어를 함께 붙이는 mutation이 `TOS-CC-RULE-MISSING` red인지 고정하고 정상 가시 식별자 셀은 silent인지 역방향도 유지하라."
    }
  ],
  "next_steps": [
    "HTML 주석 기반 면제 우회를 수정하고 대조군에 추가한다.",
    "새 계약 blob을 동결·재결속한 뒤 재심한다.",
    "이번 판은 (a) 신규 material 1건이므로 S-26 ② 카운터를 0으로 유지한다."
  ]
}
```

---

## 수용검사 (오케스트레이터 = Claude)

**채택 1 · 기각 0 · 팬텀 0.**  독립 재현: 픽스처 행에
`신규 규범 <!-- (ㅎ-4) --> ...` 셀을 붙이자 **탈출(green)** 이었다.

**원인은 한 줄 — 순서**다.  식별자 탐색이 **주석 제거 «전»** 에 원문 셀에서 일어나,
렌더링되지 «않는» 식별자가 셀 전체를 면제로 승격시켰다.
**비가시 문자열은 정체를 부여하지 못한다.**

**비협상 규칙 대조**: 배치 0(21판 연속).
