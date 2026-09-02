# 레인 B 계획 «재심» — 45차 처분 판 (재심 #6)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: e3e5a372
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 75167314a15863b8d1b1c01d3337fa5885fcca7459b34249177babb3781cdaa5
job_id: review-mtebl31q-tqm1uz
job_class: review
base: 316ac952
scope: branch
elapsed: 2m 54s
prior_verdict: docs/reviews/phase0-completion-contract/20260829-202950/verdict.md
freeze_track_round: "1회차 (계약 blob 2e77dfc8bd54)"
```

**게이트 판정: 통과 아님.**  findings **2** — 심판이 **둘 다 (a) 신규 material** 로 분류했으므로
**§S-26 ② 카운터는 시작되지 않았다**.  다만 **44차의 주장 축소 판정은 유지**된다고 명시했다.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 불가. 44차의 주장 축소 판정은 유지하지만, 45차가 새로 만든 셀 단위 검사에서 (a) 신규 material finding 2건이 실측됐다. 둘 다 명시된 잔여 다섯의 재확인(b)이 아니므로 S-26 ②의 신규-material-0 카운터는 시작할 수 없다.",
  "findings": [
    {
      "severity": "high",
      "title": "(a) 셀별 스캔이 식별자 없는 두 셀에 걸친 규범 술어를 놓친다",
      "body": "`_scan_chunks`가 픽스처 행의 비면제 셀을 각각 독립 문자열로 반환하므로 비교식과 결과 토큰이 서로 다른 셀에 있으면 `_cap_guard_sites`가 결합하지 않는다. T-84 행에 식별자 없는 두 셀로 `total_count > 1000`과 `→ PREVENTION_UNVERIFIABLE`을 나눠 직접 주입했을 때 기준선 0건 그대로 통과했다. 이는 45차 문언의 '식별자 없는 셀은 규범 술어로 읽힌다'보다 실제 능력이 좁고, 행 단위 스캔을 셀 단위로 바꾸며 새로 생긴 우회이므로 (a) 신규 material이다. 또한 `CAP2-escape-new-cell-in-fixture-row`는 실제 T-84 행에 셀을 추가하지 않고 별도 비픽스처 행을 삽입해 이 경계를 검증하지 않는다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2354,
      "line_end": 2366,
      "confidence": 0.99,
      "recommendation": "픽스처 행에서 식별자 셀만 마스킹한 뒤 나머지 셀을 행 순서대로 결합해 검사하라. mutation도 T-84의 동일 행에 실제 셀을 추가하도록 고치고, 비교식과 결과 토큰을 두 비면제 셀에 분할한 변형이 RULE-MISSING red인지 고정하라."
    },
    {
      "severity": "medium",
      "title": "(a) 닫히지 않은 식별자 접두도 셀 전체 면제키가 된다",
      "body": "문언이 정의한 식별자 형상은 `(ㅎ-4)`처럼 닫힌 형태지만 `CONTROL_ID_RE`는 닫는 괄호를 요구하지 않는다. T-84의 새 셀에 `(ㅎ-4x 신규 규범: total_count > 1000 → PREVENTION_UNVERIFIABLE`을 직접 주입하자 위반 0건으로 통과했다. 이 셀에는 등재된 잔여 1의 '대조군 식별자'가 없으므로 그 잔여의 재확인(b)이 아니라, 면제 범위가 문언보다 넓은 (a) 신규 material finding이다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2328,
      "line_end": 2331,
      "confidence": 0.99,
      "recommendation": "식별자를 `\\([ㄱ-ㅎ]-\\d+\\)`처럼 닫힌 전체 형상으로 인식하고, `(ㅎ-4x`, `(ㅎ-4`, `(ㅎ-4)-suffix` 같은 근접 비식별자 셀에 규범 술어를 넣은 변형이 모두 red인지 추가하라."
    }
  ],
  "next_steps": [
    "두 신규 우회를 수정하고 실제 동일 T-84 행 기반 mutation으로 재검증한다.",
    "새 blob을 다시 동결·재결속한 뒤 재심한다.",
    "이번 판은 신규 material 2건이므로 S-26 ② 카운터를 0으로 유지한다."
  ]
}
```

---

## 수용검사 (오케스트레이터 = Claude)

**채택 2 · 기각 0 · 팬텀 0.**  두 건 모두 독립 재현했다 — **둘 다 45차가 «행»에서 «셀»로
내려가며 새로 만든 자리**다.

| 주입 | 재현 |
| --- | --- |
| 픽스처 행의 **식별자 없는 두 셀**에 비교식과 결과 토큰을 나눠 둠 | **탈출(green)** |
| 미닫힘 식별자 접두 `(ㅎ-4x` 로 셀 면제 | **탈출(green)** |

**심판이 저작 측 «대조군의 결함»을 짚었다**: `CAP2-escape-new-cell-in-fixture-row` 가 실제
픽스처 행에 셀을 추가하지 않고 별도 행을 삽입해 그 경계를 검증하지 못했다.  **정확하다** —
교정했다(46차).  이 아크에서 **심판이 저작자의 대조군 자체를 검사한 첫 자리**다.

**비협상 규칙 대조**: 배치 0(20판 연속).
