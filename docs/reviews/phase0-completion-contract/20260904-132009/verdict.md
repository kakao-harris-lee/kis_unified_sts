# 레인 B 계획 «재심» — 계약 v2.22 에라타 52~55차 + O-6 재결속 · 재심 #4 (head c8209c34)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: c8209c34af581e899b9f07418909dde27a605931
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 02e852f1db13cdf9abe3623d659ff4a73cb55e7df675832b9b3dcc8224551e1f
bound_set_digest: e260c339f63bb0bbcbb56dfc0d6b58b6058976f2e52a8f6f7bdd3aecc6d2691b
job_id: review-mtmg49a4-g8ab13
job_class: review
base: 26db89c92fedef044ddbfb1c7dc93545a6187033
scope: branch
prior_verdict: .omc/review/20260904-115942/verdict.md
completed_at_utc: 2026-09-04T04:25:13.956Z
```

**needs-attention · findings 1(high) · 재심 #3 finding: (ㄱ) 정보 이득 = «해소» · (ㄴ) U-6′ 문법 = «부분 해소».** 심사 범위
`git diff 26db89c9 c8209c34 -- <두 결속 경로>`(52~55차). Codex 가 확인한 것: NONE 완료가 허용된 독립 심판·파생 범위 파일 집합·HEAD blob
재계산 digest 에 결속됨 · O-6 digest `e260c339…`·plan_scope_digest `02e852f1…` 일치 · `tos_contract_check` + self-test 145 rc 0.

## 수용검사 (오케스트레이터)

| # | sev | file:line 실재 | silenced | 비협상 배치 | 처분 |
|---|---|---|---|---|---|
| 1 | high | 실재 — 계약 :3148-3154 U-6′ (ㄱ) «axis 는 `D0-5 NONE: <site_id>` 로 시작» — `startswith` 구현이면 `D0-5 NONE: resolver_x`·`D0-5 NONE: resolver / marketfeed` 가 통과해 바로 뒤의 정확 일치·행당 1사이트·⑧ 부분문자열 red 와 모순 · ⑧ 이 접미/복수-site 변이를 별도 고정하지 않음 | 아니오 | 없음 | **채택** → 56차: axis 필드 «전체» 가 정규화 없이 `D0-5 NONE: <canonical_site_id>` 와 byte-for-byte 동일 · ⑧ 에 «유효 prefix + 임의 접미»·«두 번째 site_id 부가» 를 각각 red 대조군으로 추가 |

기각 0 · 채택 1/1. 부수 사실(계약 밖): 병행한 marketfeed 독립 확인(`review-mtmg2lz7-88qdyb`)이 NONE claim 을 거짓으로 판정해 실코퍼스의
NONE 사이트는 0 이 될 예정이다 — D-4/U-6′ 는 장래 사이트를 위한 어휘로 남으며, 이 finding 의 해소 가치는 그 어휘의 결정성에 있다.


---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 불가. 재심 #3 (ㄱ) 정보 이득 축은 해소됐다: NONE 완료는 허용된 독립 심판, 파생 범위 파일 집합, HEAD blob 재계산 digest에 결속된다. 그러나 (ㄴ) U-6′ 문법 축은 부분 해소에 그쳤다. O-6·plan_scope_digest는 일치했고 계약 검사와 self-test 145종은 rc 0이었다.",
  "findings": [
    {
      "severity": "high",
      "title": "U-6′의 prefix 규칙이 exact-axis 계약과 충돌한다",
      "body": "(ㄴ) 부분 해소. 규칙은 axis가 `D0-5 NONE: <site_id>`로 “시작”하면 된다고 규정한다. 따라서 구현이 문언 그대로 `startswith`를 사용하면 `D0-5 NONE: resolver_x` 또는 `D0-5 NONE: resolver / marketfeed` 같은 접미·복수-site 변이가 resolver 행으로 통과할 수 있다. 바로 뒤의 site_id 정확 일치·행당 한 사이트 선언 및 ⑧의 부분문자열 red 요구와 모순되어 C4 구현에 하나의 해석만 남기지 않는다. ⑧도 catch-all·중복·부분문자열만 열거해 유효 prefix 뒤 접미/복수-site 변이를 별도로 고정하지 않는다. 이 상태에서는 검사기 구현에 따라 D0-5 완료 판정이 달라질 수 있다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 3148,
      "line_end": 3154,
      "confidence": 0.99,
      "recommendation": "`axis` 필드 전체가 정규화 없이 `D0-5 NONE: <canonical_site_id>`와 byte-for-byte 동일해야 한다고 바꾸고, 유효 prefix 뒤 임의 접미 및 두 번째 site_id를 붙인 변이를 각각 red 대조군으로 추가하라. 계약 본문 추가 편집이므로 S-26 ⑥ 카운터를 다시 0으로 리셋하고 O-6를 재결속한 뒤 레인 B 재심을 다시 수행해야 한다."
    }
  ],
  "next_steps": [
    "U-6′의 “시작”을 필드 전체 exact equality로 교체한다.",
    "suffix와 복수-site axis 변이를 독립 red 대조군으로 명시한다.",
    "S-26 ⑥ 리셋, O-6 재결속, 갱신된 범위 digest 검증 후 레인 B 재심을 다시 실행한다."
  ]
}
```

원문 전체는 `.omc/review/20260904-132009/codex-result.json`(`parseError: null` · `adversarial-review` 구조화 출력).
디스패치 focus 는 `.omc/review/20260904-132009/focus.txt`, 심사 대상 diff 사본은 같은 스탬프의 `evidence/scope-diff.patch`
·`evidence/lockstep-diff.patch`.
