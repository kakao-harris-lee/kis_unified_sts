# 레인 B 계획 «재심» — 계약 v2.22 에라타 52차+53차 + O-6 재결속 · 재심 #2 (head d8ee64dd)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: d8ee64dd82eb0537bc43de0c65a4a3ea0d92ae35
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 54b97e14c658de22761b22f9ba6fd68ab8a25ca636aba9994c757463a5cd1a9a
bound_set_digest: 4c65d626bb034263f66312426d3f1bde551baff8558718bb2ba0205525ad982c
job_id: review-mtmcoagb-uym46j
job_class: review
base: 26db89c92fedef044ddbfb1c7dc93545a6187033
scope: branch
prior_verdict: .omc/review/20260904-112156/verdict.md
completed_at_utc: 2026-09-04T02:48:58.941Z
```

**needs-attention · findings 1(high) · 재심 #1 finding = «부분 해소».** 심사 범위는 `git diff 26db89c9 d8ee64dd -- <두 결속 경로>`
(52차 +130/−9 · 53차 +93/−16 계약 · 개발계획 무접촉). Codex 가 확인한 것: HEAD · plan_scope_digest `54b97e14…` ·
bound_set_digest `4c65d626…` · C1′ decided_at_head 일치 · 옛 digest 는 이력에만 · `tos_contract_check` + self-test 145 rc 0 ·
`max_age_bound`·토큰화·C4 대조군은 보강됨.

## 수용검사 (오케스트레이터)

| # | sev | file:line 실재 | silenced | 비협상 배치 | 처분 |
|---|---|---|---|---|---|
| 1 | high | 실재 — 계약 :2843-2856 D-4 (나)(53차 · C1′ 97cfad8d). 후보 우주 = 우주 키 ∪ §7.1 사이트들의 D-5 선언 키 → 선언에서 키를 빼면 후보에서도 빠진다(선언-파생 순환). 재현 논리: resolver 선언에서 `max_age_bound` 를 제거하고 NONE 사이트 범위에 그 리터럴을 두면 후보 우주가 먼저 축소돼 NO_DEPENDENCY 가능 | 아니오 | 없음 | **채택** → 54차 |

기각 0 · 채택 1/1.

**오케스트레이터 대조 메모(판정 아님)**: Codex 가 든 «선언 삭제» 는 NONE 이 없어도 성립한다 — resolver 선언에서
`max_age_bound` 를 빼면 D-3 만으로 resolver 는 6 VALUED «판정됨» 이 되고 그 UNBOUND 와 §13 행은 사라진다. 이것은
계약이 **UNCHK-015**(공급된 K 의 적절성 · 의미 판정)로 이미 등재한 경계이며, «우주 밖 의존 키의 전수 집합» 은
저작자 독립적으로 열거할 수 없다(열거 가능한 것은 우주 키뿐). 따라서 54차는 열거를 확장하는 방향(또 다른 자기신고
파생)이 아니라 **우회의 이득을 제거**하는 방향으로 간다: `NO_DEPENDENCY` 는 `UNBOUND` 와 같은 급의 결론이므로 같은
§13 개별 등재 의무를 진다(U-6′ — 검사기 rc 결합). NONE 으로 바꿔도 등재를 피할 수 없으면 «UNBOUND+등재 → NONE+면제»
라는 우회의 동기가 없다. 53차의 후보 우주 스캔은 그대로 두되(선언 누락의 기계 검출), Codex 의 donor 삭제 시나리오는
C4 대조군으로 «관측 가능한 귀결»(등재 행 부재 시 rc≠0)을 고정한다. 이 처분이 정당한지는 다음 재심에서 Codex 가 판단한다.


---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 차단. 재심 #1 finding은 부분 해소다. `max_age_bound`·토큰화·C4 대조군은 보강됐지만, 후보 우주가 저작자 선언으로부터 파생되어 미선언 UNBOUND 키의 NONE 우회가 남는다. HEAD, plan_scope_digest, bound_set_digest, C1′ decided_at_head는 일치했고 옛 digest는 이력에만 남았다. 계약 검사와 self-test 145종은 rc 0이었다.",
  "findings": [
    {
      "severity": "high",
      "title": "자기신고로 후보 우주에서 키를 제거할 수 있어 NONE 우회가 남는다",
      "body": "재심 #1 finding은 «부분 해소»다. 현재 `max_age_bound`는 resolver의 D-5 선언 덕분에 합집합에 들어가지만, 후보 우주 자체가 같은 D-5 선언들에서 파생된다. 따라서 저작자가 우주 밖 키를 모든 선언에서 빼면 그 키는 docstring에 리터럴로 남아도 스캔 후보에서 사라진다. 계약은 미선언 프로파일 키만 UNDECIDED로 열거하고, 미선언 UNBOUND 키는 명시적으로 감지하지 않는다. 예컨대 resolver 선언에서 `max_age_bound`만 제거한 뒤 NONE 사이트 범위에 이를 두면 제시된 네 대조군과 달리 후보 우주가 먼저 축소되어 NO_DEPENDENCY가 가능하다. 이는 UNBOUND와 §13 등재를 NONE으로 바꾸던 원래 우회의 자기삭제 변형이다. 외부-helper 사례는 D-1 정의 축소로 경계를 정직하게 명시했지만, 이 선언-파생 순환은 문제를 정의로 없앤 것이 아니다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 2843,
      "line_end": 2856,
      "confidence": 0.98,
      "recommendation": "후보 우주를 사이트 저작자의 D-5 선언과 독립적으로 열거하거나, 독립 열거가 불가능하면 NONE을 완료값으로 쓰지 말고 미선언 UNBOUND 리터럴을 UNDECIDED로 차단하라. C4에는 `max_age_bound`의 donor 선언을 삭제한 상태에서 NONE 범위에 같은 리터럴을 두는 대조군을 추가하라. 계약 본문 추가 편집이므로 S-26 ⑥ 카운터 재리셋, O-6 재결속, 레인 B 재심 비용을 함께 기록해야 한다."
    }
  ],
  "next_steps": [
    "D-4 후보 우주의 선언-파생 순환을 제거하고 donor 선언 삭제 대조군을 C4 동일 커밋 계약에 추가한다.",
    "수정 후 plan_scope_digest와 bound_set_digest를 재계산하고 O-6를 다시 결속한 뒤 레인 B 재심을 반복한다."
  ]
}
```

원문 전체는 `.omc/review/20260904-114347/codex-result.json`(`parseError: null` · `adversarial-review` 구조화 출력).
디스패치 focus 는 `.omc/review/20260904-114347/focus.txt`, 심사 대상 diff 사본은 같은 스탬프의 `evidence/scope-diff.patch`
·`evidence/lockstep-diff.patch`.
