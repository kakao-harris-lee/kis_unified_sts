# 레인 B 계획 «재심» — 44차 처분 판 (동결 트랙 재시작 1회차 · 재심 #5)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 79abf3c9
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: ca3be9c64d065442f4d0442329c37ba3e5d460aa7962417f8f35f554e9a29f96
job_id: review-mteatd2f-md8uuq
job_class: review
base: d4356235
scope: branch
elapsed: 2m 44s
prior_verdict: docs/reviews/phase0-completion-contract/20260829-192101/verdict.md
freeze_track_round: "재시작 1회차 (계약 blob 51129374b8f2)"
```

**게이트 판정: 통과 아님.**  findings **2 → 1**.

**이 판정이 인정한 것 — 아크에서 두 번째다.**  44차의 **주장 축소**(폐쇄 증명 → 회귀 탐지기)를
**「표기 공간에 대해서는 정직한 한계 진술」** 로 판정하고 **「그 축소만으로는 blocker 를 세우지
않는다」** 고 명시했다.  (u17 실행기 축소가 «정직한 미해소»로 인정받은 것이 첫 번째다.)
다만 u17 선례와 **완전히 같지는 않다**는 단서를 달았다 — u17 은 미해소 조건을 완료 게이트에
남겼고, 이번엔 **검사기의 목적 자체**를 축소했다.

**그러나 카운터는 시작되지 않았다**: 남은 1건이 명시 등재한 네 잔여가 아니라 **(a) 신규
material finding** 이기 때문이다.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 불가. (e)는 표기 공간에 대해서는 정직한 한계 진술이지만 u17 선례와 완전히 같지는 않다. u17은 미해소 조건을 완료 게이트에 남겼고, 이번에는 검사기의 목적 자체를 회귀 탐지로 축소했다. 그 축소만으로는 blocker를 세우지 않지만, 아래 우회는 명시된 네 잔여가 아닌 (a) 신규 material finding이므로 S-26 ② 카운터는 시작할 수 없다.",
  "findings": [
    {
      "severity": "high",
      "title": "fixture_rows가 행 정체가 아니라 전체 행을 면제하는 접두 우회키다",
      "body": "`startswith(anchor)`는 manifest의 `| **T-84**`와 정확히 같은 행만 식별하지 않는다. 직접 주입한 `| **T-84**-NORM | 신규 규범: total_count > 1000 → PREVENTION_UNVERIFIABLE |`와 실제 T-84 행에 같은 규범 셀을 추가한 변형 모두 전체 검사 0→0이었고 CAP-2 모집단은 해당 행을 제외했다. 따라서 규범을 픽스처 접두 네임스페이스나 T-84의 새 셀에 넣으면 구조 파생 항 없이도 통과한다. self-test의 `CAP2-fixture-marker-is-silent`도 T-84 행 앵커를 사용하지 않아 이 경계를 검증하지 않는다. 이는 펜스 위양성·이름 상수·접두 목록 밖 표기·미관측 표기와 다른 구조적 면제 결함이므로 (a) 신규 material finding이다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2350,
      "line_end": 2351,
      "confidence": 0.99,
      "recommendation": "Markdown 표를 파싱해 fixture ID의 완전일치와 고유성을 검증하고, 행 전체가 아니라 manifest가 지정한 정확한 픽스처 셀만 제외하라. T-84 접두 충돌과 T-84 새 규범 셀 주입이 모두 RULE-MISSING red가 되는 self-test를 추가하라."
    }
  ],
  "next_steps": [
    "CAP-2 픽스처 면제를 정확한 표 셀 정체로 제한한다.",
    "두 재현 변형을 self-test에 고정하고 전체 배터리에서 red를 확인한다.",
    "수정 후 새 blob을 동결하고 S-26의 2회 연속 신규 material 0 카운터를 다시 시작한다."
  ]
}
```

---

## 수용검사 (오케스트레이터 = Claude)

**채택 1 · 기각 0 · 팬텀 0.**  두 변형 모두 독립 재현했다.

| 주입 | 재현 |
| --- | --- |
| `| **T-84**-NORM |` 접두 네임스페이스 | **탈출(green)** — `startswith` 가 접두를 같은 행으로 읽었다 |
| 픽스처 행에 **새 규범 셀** 추가 | **탈출(green)** — 행 전체가 면제됐다 |

**비협상 규칙 대조**: 배치 0(19판 연속).

## 이 재심의 의미

**축소는 통과했고, 면제가 걸렸다.**  44차가 «떠다니는 표식»을 «행 정체»로 옮긴 것은 방향이
맞았으나 그 «정체»가 `startswith` 였다 — 정체가 아니라 **접두**였다.  45차는 그것을
**첫 셀 완전일치 + 대조군 식별자를 가진 «셀»** 로 좁혔다.
