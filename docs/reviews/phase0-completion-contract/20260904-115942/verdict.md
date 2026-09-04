# 레인 B 계획 «재심» — 계약 v2.22 에라타 52차+53차+54차 + O-6 재결속 · 재심 #3 (head a311eac1)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: a311eac1f9c6fbb816230cc7e89b21daafdb7642
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 1c1616aa56439560bf8ecb94ce7e194f497cb33de31ba06951e7a6d91320446d
bound_set_digest: 8988849e7673a02001d11b4cadff8b65e1b7ac78c9ef2cbbaa0dd454809b730a
job_id: review-mtmd8qat-c1u166
job_class: review
base: 26db89c92fedef044ddbfb1c7dc93545a6187033
scope: branch
prior_verdict: .omc/review/20260904-114347/verdict.md
completed_at_utc: 2026-09-04T03:04:45.700Z
```

**needs-attention · findings 1(high) · 재심 #2 finding = «회피» 판정.** 심사 범위 `git diff 26db89c9 a311eac1 -- <두 결속 경로>`
(52차 +130/−9 · 53차 +93/−16 · 54차 +114/−20 · 개발계획 무접촉). Codex 가 확인한 것: HEAD · plan_scope_digest `1c1616aa…` ·
bound_set_digest `8988849e…` · C1″ decided_at_head · blob/행수 · diff 사본 일치 · `tos_contract_check` + self-test 145 rc 0 ·
53차의 후보 우주·토큰화·전이 귀속은 되돌려지지 않음.

## 수용검사 (오케스트레이터)

| # | sev | file:line 실재 | silenced | 비협상 배치 | 처분 |
|---|---|---|---|---|---|
| 1 | high | 실재 — 계약 :3001-3038(54차 블록 + U-6/U-6′ 펜스 · C1″ ab495780). 두 축: (ㄱ) UNBOUND 행은 «실제 키 + 소관 아티팩트» 를 공개하는데 NONE 행(U-6′ (1)(2)(3))은 후보 우주 크기·스캔 범위·일반적 사각지대만 적으므로 «특정 의존과 소관 분석을 숨기는» 이득이 남는다 · 대조군 ⑤는 행 «부재» 만 red 라 행이 있는 자기삭제와 정직한 marketfeed 를 구별 못 한다 (ㄴ) U-6′ 행 판정 문법 미정의(부분문자열/정확 일치 · 행 유일성 · 한 행의 복수 사이트 · (1)~(3) 동일 행 여부) → catch-all 행 우회 | 아니오 | 없음 | **채택** — 처분 방향은 운영자 결정(아래) |

기각 0 · 채택 1/1.

**오케스트레이터 대조 메모(판정 아님)**: (ㄴ)은 문법 명시로 닫히는 기계적 결함이다(사이트별 정확히 한 행 · 행별 최대 한 사이트 · (1)~(3) 동일 행 · site_id 정확 일치). (ㄱ)은 설계 결정이다 — Codex 권고는 «NONE 완료 = canonical site_id + 소스 리비전(사이트 범위 파일 blob)에 결속된 **독립 리뷰 provenance**(저작자 아닌 심판/운영자가 «의미상 의존 없음» 을 검토했다는 기록)» 이며, 그 전까지 NONE 은 차단 상태. 이는 이 아크의 원리(저작-심판 분리 · 자기신고를 리뷰 표면으로)와 정합하지만 **새 아티팩트 종류와 서명 주체**를 도입한다 → 4번째 에라타 라운드를 자동으로 돌리지 않고 운영자 결정을 받는다. 그때까지 계약은 54차 상태(NO_DEPENDENCY 는 텍스트상 완료값이나 검사기 미구현 = 완료값 창 없음), `d0a_entry_state=APPROVAL_STALE`(레인 B approve 미착지), D0-5 NOT_MET 그대로다.


---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 차단. 재심 #2 finding은 «회피»다. 54차는 후보 우주의 자기삭제를 막지 않고 일반적 공시로 허용했으며, UNBOUND가 공개하는 실제 키·소관 아티팩트를 NONE에서는 숨길 이득이 남는다. 대조군 ⑤는 행 부재 시 rc≠0만 고정한다. 반면 53차의 후보 우주·토큰화·전이 귀속은 되돌려지지 않았고, HEAD·scope digest·bound digest·C1″ decided_at_head·blob/행수·diff 사본은 일치했다. 계약 검사와 self-test 145종도 rc 0이었다.",
  "findings": [
    {
      "severity": "high",
      "title": "U-6′는 자기삭제 우회의 정보 이득을 제거하지 못하고 행 판정도 불명확하다",
      "body": "54차는 열거 불가능성과 UNCHK-015 경계를 정직하게 인정하지만, 이를 완료 가능한 NO_DEPENDENCY로 재정의해 재심 #2 문제를 회피한다. donor에서 `max_age_bound`를 삭제한 시나리오에서 UNBOUND 행은 실제 키와 소관 아티팩트를 공개하지만, NONE 행은 후보 우주 크기·스캔 범위·일반적 사각지대만 기록한다. 따라서 특정 의존과 소관 분석을 숨기는 실질적 이득이 남는다. 대조군 ⑤도 행을 제거한 경우만 red로 만들므로, 행이 존재하는 자기삭제 사례와 정직한 marketfeed 사례를 구별하지 못한다. 또한 U-6′는 사이트 토큰의 부분문자열/정확 일치, 후보 행의 유일성, 한 행의 복수 사이트 충족 가능성, (1)~(3)이 동일 행에 있어야 하는지를 정의하지 않는다. C4가 포괄 axis/reason 문자열에서 존재만 검사하면 하나의 catch-all 행이나 우연한 토큰으로 여러 사이트가 완료될 수 있다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 3001,
      "line_end": 3038,
      "confidence": 0.98,
      "recommendation": "열린 세계 이름의 전수 열거를 요구하지 말고, NONE 완료를 정확한 canonical site_id와 소스 리비전에 결속된 독립 리뷰 provenance에 걸어 의미상 의존 없음이 검토됐음을 요구하라. 또한 사이트별 정확히 한 행, 행별 최대 한 사이트, 동일 행 안의 (1)~(3), 정확 일치 문법을 규정하고 catch-all·부분문자열·분할 reason·중복 행 변이를 red로 고정하라. 이 보강 전에는 NONE을 완료값이 아닌 차단 상태로 유지한다. 계약 본문 편집이므로 S-26 ⑥을 다시 리셋하고 O-6 재결속과 레인 B 재심 비용을 함께 기록해야 한다."
    }
  ],
  "next_steps": [
    "U-6′의 독립 provenance와 1:1 행 결속 계약을 명확히 한 뒤 대조군 ⑤를 행 존재 상태의 자기삭제도 차단하도록 확장한다.",
    "S-26 ⑥ 재적용, O-6 재결속, 두 digest 재계산 후 레인 B 재심을 반복한다."
  ]
}
```

원문 전체는 `.omc/review/20260904-115942/codex-result.json`(`parseError: null` · `adversarial-review` 구조화 출력).
디스패치 focus 는 `.omc/review/20260904-115942/focus.txt`, 심사 대상 diff 사본은 같은 스탬프의 `evidence/scope-diff.patch`
·`evidence/lockstep-diff.patch`.
