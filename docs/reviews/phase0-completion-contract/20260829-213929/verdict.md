# 레인 B 계획 «재심» — 48차 처분 판 (재심 #9)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 898ad0ce
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 99fe3c45b811f7d7d47a2df03aefd3c9f24e9e0d5537568f67fefcca6cdc0ca0
bound_set_digest: 6f5cfce11bf16757f1e8dddf495448de1302cce90cc08c965a547131f1ad097e
job_id: review-mtee16mk-x95d7q
job_class: review
base: e27a3a44
scope: branch
prior_verdict: docs/reviews/phase0-completion-contract/20260829-212017/verdict.md
cancelled_job: review-mtedd9t6-czbz7p   # 매달림 — 아래 «운영 기록»
```

**게이트 판정: 통과 아님.**  findings **1** — (a) 신규 material.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 불가. 직전 hidden/template 우회는 고정 기준선에서는 red가 되어 해소됐지만, (a) 신규 material 1건이 확인됐다. 셀 추가와 기준값 갱신을 함께 하면 검사 결과가 0건으로 돌아간다. 기존 셀 내용을 같은 수로 바꾸는 경로는 계약의 명시 잔여이므로 (b)로 재확인만 했고 finding으로 세지 않았다. material 0이 아니므로 S-26 ② 카운터는 0이며 열 판 연속 0이다.",
  "findings": [
    {
      "severity": "high",
      "title": "(a) 셀 추가와 기준값 동시 갱신이 새 래칫을 완전히 우회한다",
      "body": "`check_fixture_row_shape`는 저장소에서 함께 편집 가능한 JSON의 정수와 현재 행의 셀 수가 같은지만 검사하며, 그 값이 어떤 불변 문서 blob에서 측정됐는지는 결속하지 않는다. T-84에 규범 셀을 추가하면 17→18로 red였지만 `read_fixture_row_baseline`이 18을 반환하도록 동일 기준값 갱신을 모사하자 전체 검사 위반이 0건이었다. 기준파일의 기존 `measured_against`를 그대로 둬도 통과한다. 따라서 계약의 “기준선 갱신은 사람의 기록 행위”는 구현된 통제가 아니며, “수는 위조되지 않는다”는 주장도 실제 능력보다 넓다. 현재 배터리는 문서와 기준값을 함께 바꾸는 대조군이 없어 이 우회를 검증하지 않는다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2481,
      "line_end": 2513,
      "confidence": 0.99,
      "recommendation": "`fixture_row_cells`를 `measured_against`가 지목한 불변 commit blob에서 구조적으로 재측정해 값과 결속하고, 계약 행에 셀을 추가하면서 기준값도 같은 수로 갱신하는 paired mutant가 반드시 red가 되도록 추가하라. 정당한 기준선 이전이 필요하면 별도의 명시적 승인·provenance 전이로만 허용하라."
    }
  ],
  "next_steps": [
    "결속된 blob에서 픽스처 셀 수를 재파생하도록 래칫 provenance를 보강한다.",
    "문서와 기준값의 동시 변경 뮤턴트를 추가해 fail-closed를 실측한다.",
    "수정 후 새 계약 blob을 동결·O-6 재결속하고 재심한다."
  ]
}
```

---

## 수용검사 (오케스트레이터 = Claude)

**채택 1 · 기각 0 · 팬텀 0.**

### 결속 대조

`bound_set_digest` 재계산 = `6f5cfce1…` — OQ-11 기입값과 **일치**.  결속 유효.

### 독립 재현 (구조 관측 — 자기신고 아님)

| 실측 | 결과 |
|---|---|
| 직전 #8 우회 재주입: T-84 에 `<span hidden>(ㅎ-4)</span>` 셀 추가 | **red** `TOS-CC-CAP2-FIXTURE` (기준선 17 · 실측 18) — **해소 확인** |
| 등재 잔여: 기존 셀 «안»에 규범 술어를 덧붙여 셀 수 17 유지 | **green** — 계약이 «잔여 1» 로 등재한 자리와 일치 → **(b)** |
| **본 finding**: 문서 +1 셀 **AND** 기준값 17→18 (`measured_against` 불변) | **PASS — 위반 0건.  우회 성립** |
| `--self-test` (`.venv/bin/python`) | **PASS — 135종 전건 판별 · 죽은 검사 0** |

Codex 는 `--self-test` 를 `python`(PyYAML 부재)으로 돌려 **exit 2 로 실패**했다 — 즉 「배터리에
대조군이 없다」는 그쪽 주장은 **실행이 아니라 독해**에 근거한다.  오케스트레이터가 배터리를
실제로 돌려(135 PASS) **구조로** 그 주장을 검증했다:

- `TOS-CC-CAP2-FIXTURE` 대조군 **7종 · 그 중 기준선을 변형하는 것 0종**.
- 기준선을 변형하는 대조군은 **다른 축에 10종 실재**한다
  (`C2U-*` 6 · `C2UP-count-disagrees-with-blob` 등 3 · `CLOSED-TABLE-baseline-entry-gone`).
  **기계는 이미 있고, 새 축이 그것을 쓰지 않았다.**

### 지적의 본질 — 「C2U 래칫과 같은 규율」이 참이 아니다

48차 문언은 「기준선 갱신은 «사람의 기록 행위»여야 한다(**C2U 래칫과 같은 규율**)」이다.
그러나 C2U 는 그 규율을 **산문이 아니라 기계**로 진다: `check_c2up`(PROVENANCE-1,
`tools/tos_contract_check.py:1668`)이 `git show <commit>:<path>` 로 **blob 을 다시 재어**
기입값과 대조하고, 불일치면 red 이며, 움직이는 ref 는 거부한다.
`read_unanchored_baseline` 의 주석이 그 분업을 명시한다 — 「측정 출처는 여기서 «형태»만 본다.
그 주장이 참인지는 `check_c2up` 이 실제 blob 을 다시 재어 판정한다」.

`fixture_row_cells` 에는 그 두 번째 다리가 **없다**.  그러므로 48차가 인용한 «같은 규율»은
성립하지 않고, **문언이 능력보다 넓다** — 이 아크에서 **네 번째로** 발화한 같은 결함 클래스다.
45~48차의 층은 이렇게 내려왔다: 면제의 단위 → 판별 순서 → 운반체 → 정체의 종류 → **정체의 «출처»**.

### 기각 사유 대조

| 검사 | 결과 |
|---|---|
| `file:line` 실재 (`tools/tos_contract_check.py:2481-2513`) | **실재** — `check_fixture_row_shape` 본문 |
| 의도적으로 silenced 인가 | **아니다** — 계약은 정반대(「정당한 대조군 추가도 red 다」)를 주장한다 |
| 비협상 규칙 배치 | **없음** (배치 0 — 23판 연속) |
| 범위 밖 기존 부채 | **아니다** — 48차가 이 판에서 신설한 축이다 |

### S-26 ② 카운터

**0 — 열 판 연속 0.**  이번 판은 material 1 이므로 카운터가 서지 않는다.
궤적: findings 4 → 2 → 3 → 2 → 1 → 2 → 1 → 1 → **1**.

---

## 오케스트레이터 관측 (판정 아님 — 이 verdict 로 처분되지 않는다)

심판이 내지 않은 항목이므로 **finding 이 아니고 카운터에도 영향이 없다.**  저작자 참고용.

1. `tools/tos_contract_check.py:2305` `HTML_TAG_RE` — 48차가 도입했으나 **어디서도 쓰이지 않는다**
   (`grep` 결과 정의 1회뿐).  그 주석은 「**면제 판별에서만** 태그를 벗긴다」고 적었는데
   코드는 벗기지 않는다 — 폐기한 방향의 잔해다.
2. `tools/tos_contract_check.py:2364` `_scan_chunks` 의 요약 문언·`Returns` 가 여전히
   「픽스처 행이면 **대조군 셀만 빼고** 셀 단위로 돌려준다」인데 구현은 `return []` 이다.
   **같은 함수 안에** 문언/능력 불일치가 남아 있다.
3. (비차단) `_rule_baseline_path()` 가 `--baseline` 을 무시하고 항상 기본 경로를 쓴다.
   그 docstring 은 「C2U 와 같은 파일」이라 적었지만 `--baseline` 을 주면 두 축이 갈린다.
   CI(`.github/workflows/tos-firewall.yml:90`)는 플래그 없이 호출하므로 **현재 실효는 없다.**

---

## 운영 기록 (정직)

최초 디스패치 `review-mtedd9t6-czbz7p` 은 **매달려 취소**했다.  `--background` 를 줬는데도
companion 이 스트리밍했고 foreground Bash 2분 타임아웃의 SIGTERM 이 부모를 끊었다.
잡 레코드는 18분간 `status: running` 을 자기신고했으나 **progress 는 2분 지점 이후 한 줄도
늘지 않았다** — `cancel` 판단은 그 **구조 관측**으로 내렸다.  재디스패치
(`review-mtee16mk-x95d7q`)는 프로세스를 살려 둔 채 돌려 정상 완료했다.
직전 회차의 «잡 id 오독» 과 같은 계열이다: **도구의 자기신고를 상태로 읽지 마라.**
