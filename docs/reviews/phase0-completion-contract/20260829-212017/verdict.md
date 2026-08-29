# 레인 B 계획 «재심» — 47차 처분 판 (재심 #8)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: a45fecc3
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 9a963be07352f66b55b48a1f8af43a4d26d3d6c6e73798d8360937fffec78ae5
job_id: review-mtecm8t5-5nkjva
job_class: review
base: 6929430b
scope: branch
prior_verdict: docs/reviews/phase0-completion-contract/20260829-210405/verdict.md
```

**게이트 판정: 통과 아님.**  findings **1** — (a) 신규 material.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 불가. (a) 신규 material 1건: 47차는 HTML 주석 한 형상만 고쳤을 뿐인데 모든 비가시 문자열이 정체를 부여하지 못한다고 과대 선언했다. S-26 ② 카운터는 시작할 수 없다.",
  "findings": [
    {
      "severity": "high",
      "title": "(a) 숨김 HTML 식별자가 여전히 규범 셀 전체를 면제한다",
      "body": "`_scan_chunks`는 `HTML_COMMENT_RE`만 제거한 뒤 나머지 원문 HTML에서 식별자를 찾는다. 실제 T-84 행에 `<span hidden>(ㅎ-4)</span> total_count > 1000 → PREVENTION_UNVERIFIABLE` 또는 `<template>(ㅎ-4)</template> ...` 셀을 직접 주입하자 셀 전체가 제외되어 `TOS-CC-RULE-MISSING`이 0건이었다. 같은 위치의 47차 `<!-- (ㅎ-4) -->` 뮤턴트는 정상적으로 red였다. 이는 명시 잔여 1의 가시 대조군 식별자 셀이 아니라 비가시 문자열을 정체로 승격하는 동일 직접 우회이며, 계약의 “비가시 문자열은 정체를 부여하지 못한다”는 문언이 실제 능력보다 넓으므로 신규 material이다. 133번째 뮤턴트도 HTML 주석 한 형상만 시험해 이 경계를 검증하지 않는다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2376,
      "line_end": 2379,
      "confidence": 0.99,
      "recommendation": "식별자 판정 전에 허용된 렌더링 모델에 따라 모든 비가시 HTML 내용을 제거하거나, 픽스처 식별자 셀에서 raw HTML을 금지하라. `hidden`, `display:none`, `template` 식별자 주입이 각각 `TOS-CC-RULE-MISSING` red이고 가시 식별자 셀은 silent인 양극성 뮤턴트를 추가하라."
    }
  ],
  "next_steps": [
    "비가시 HTML 기반 면제 우회와 대조군 공백을 수정한다.",
    "새 계약 blob을 동결·재결속한 뒤 재심한다.",
    "이번 판은 신규 material 1건이므로 S-26 ② 카운터를 0으로 유지한다."
  ]
}
```

---

## 수용검사 (오케스트레이터 = Claude)

**채택 1 · 기각 0 · 팬텀 0.**  독립 재현: `<span hidden>(ㅎ-4)</span>` · `<template>(ㅎ-4)</template>`
둘 다 **탈출(green)**, 47차가 고친 주석 형상만 red.

**지적의 본질**: 47차 문언은 「**비가시 문자열은** 정체를 부여하지 못한다」였는데 구현은
**주석 한 형상**만 고쳤다 — **문언이 능력보다 넓었다.**  이 아크에서 같은 규율이 세 번째로
발화한 자리다.

**오케스트레이터 운영 실패 1건(기록)**: 이 회차의 판정을 처음 읽을 때 잡 id 추출이 빈 값이 되어
`result` 가 **직전 완료 잡(#7)의 결과**를 돌려줬고, 그것을 #8 로 읽어 보고했다.  구조 관측
(`running` 목록)으로 정정했다.  **자기신고가 아니라 구조로 확인하라**는 이 아크의 규율이
도구 사용에도 그대로 적용된다.

**비협상 규칙 대조**: 배치 0(22판 연속).
