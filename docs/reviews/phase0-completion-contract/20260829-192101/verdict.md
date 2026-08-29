# 레인 B 계획 «재심» — 43차 처분 판 (동결 트랙 1회차 · 재심 #4)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 5f33c80be737d3e01184bb0c88215ea4de834508
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 3405ddb2b4c917089cdc6f4add3340bcb42457a88784d06f76190ac0c7d51739
job_id: review-mte8cvk9-t5wkmn
job_class: review
base: cb70c939
scope: branch
elapsed: 3m 6s
prior_verdict: docs/reviews/phase0-completion-contract/20260829-181945/verdict.md
freeze_track_round: 1
```

**게이트 판정: 통과 아님.**  findings **2 — 심판이 «둘 다 (a) 신규 material finding» 으로 명시**했다.
따라서 **§S-26 ② 의 «2회 연속» 카운터는 시작되지 않았다.**

**심판이 확인해 준 것**: 동결 주장(계약 blob `f9facf8f28b1` · 개발계획 `98d8660f44f8` ·
43차 이후 편집 0)은 **실측과 일치**한다.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 불가. 동결 blob과 61691fb3 이후 무편집 주장은 실측과 일치하지만, 43차의 핵심 두 분류기 모두 새 우회 입력을 조용히 통과한다. 아래는 모두 (a) 신규 material finding이며, 이미 정직하게 «미확인»으로 등재한 이름 상수·접두 목록 밖 표기의 단순 재확인이 아니다.",
  "findings": [
    {
      "severity": "high",
      "title": "픽스처 표식이 규범 술어를 숨기는 새 무료 우회키다",
      "body": "분류기는 구조적 픽스처 신원이 아니라 300자 선행 창에 `[대조군]` 부분문자열이 있는지만 보고 사이트를 제외한다. 실제로 `신규 규범 [대조군]: total_count > 1000 → PREVENTION_UNVERIFIABLE`와 직전 행에만 `[대조군]`을 둔 변형 모두 RULE-MISSING 0→0으로 통과했다. `total_count ＞ 1000`도 비교 연산자 미인식으로 0→0이었다. 반대로 표식 없는 HTML 주석·코드펜스 예시는 0→1로 과잉 차단됐다. 따라서 주장한 극성 반전은 성립하지 않고, 규범 술어가 구조 파생 항 없이 추가돼도 통과할 수 있다. 이는 (a) 신규 material finding이며, 등재된 `> CAP_MAX` 잔여와 다른 우회다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2274,
      "line_end": 2329,
      "confidence": 0.99,
      "recommendation": "Markdown 구조를 파싱해 manifest가 식별한 정확한 픽스처 행·셀만 제외하고, 주변 문자열로 면제하지 말라. 결과 토큰을 찾았지만 선행식을 해석하지 못한 자리는 fail-closed PARSE 위반으로 처리하고 표식 오용·직전 행 오염·전각 연산자·주석·코드펜스 변이를 양방향 self-test에 추가하라."
    },
    {
      "severity": "medium",
      "title": "C4C의 개행·마크업 정규화 주장이 다시 표기 의존으로 탈출한다",
      "body": "실제 주입에서 `다음 단계<!-- 렌더링 비표시 -->=44차 → …`, `다음 단계 =`/`44차`/`→ …`의 3행 분리, 그리고 `다음 단계=44차 ⇒ …`가 모두 C4C 0→0으로 통과했다. 첫 입력은 manifest 안의 정확한 접두와 지원한다고 선언한 `=`을 그대로 사용하므로 «접두 목록 밖 표기» 잔여가 아니다. 구현은 접두와 구분자의 문자상 연접, 바로 다음 한 행, 축자 `→`에 의존한다. stale 미래 단계가 렌더링상 같은 의미를 유지하면서 검사 우주 밖으로 빠질 수 있으므로 이는 (a) 신규 material finding이다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 1940,
      "line_end": 1978,
      "confidence": 0.98,
      "recommendation": "Markdown 토큰/렌더링 구조에서 주석을 제거하고 논리적 문단을 합친 뒤 단계 열거를 판별하라. 또는 접두가 발견됐지만 구조를 완전히 해석하지 못한 경우 fail-closed로 처리하라. HTML 주석 삽입·3행 이상 래핑·지원 단계 화살표 변형을 red 대조군으로 고정하라."
    }
  ],
  "next_steps": [
    "CAP-2 픽스처 면제를 구조적 신원으로 제한하고 해석 실패를 fail-closed로 바꾼다.",
    "C4C를 논리적 Markdown 문단 기준으로 파싱하고 위 실측 변이를 self-test에 추가한다.",
    "수정하면 동결 카운터가 다시 시작되므로, 새 blob을 동결한 뒤 편집 없이 두 번 재심한다."
  ]
}
```

---

## 수용검사 (오케스트레이터 = Claude)

**채택 2 · 기각 0 · 팬텀 0.**  **여덟 형상 전부 독립 재현** — 우회 6종은 조용했고,
**주석·펜스 안 예시는 위양성 red** 였다(양쪽 극성이 다 깨져 있었다).

| 주입 | 재현 |
| --- | --- |
| `[대조군]` 표식을 규범 문장에 오용 / 직전 행에 둠 | **탈출(green)** |
| 전각 연산자 `＞` | **탈출(green)** |
| `다음 단계<!--…-->=44차` · 3행 분리 · `⇒` 화살표 | **탈출(green)** |
| HTML 주석 안 예시 · 코드펜스 안 예시 | **위양성 red** |

**비협상 규칙 대조**: 배치 0(18판 연속).

## 이 재심이 확정한 것

세 판 연속 같은 패턴이다 — **축을 좁히면 새 표기로 빠져나간다.**  이번엔 반대 극성까지
드러났다(정직한 예시가 red).  이것이 44차의 처분 방향을 결정했다: **새 기계를 더 만들지 않고,
표기 정규화는 표준(NFKC)에 위임하고, 축의 «주장»을 실제 능력(회귀 탐지기)까지 낮춘다.**
