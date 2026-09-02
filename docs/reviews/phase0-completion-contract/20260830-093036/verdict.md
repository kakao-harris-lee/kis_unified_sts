# 레인 B 계획 «재심» — 49차 처분 판 (재심 #10)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 85327ee1
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 86de6bf61212a58010e1d211342cbeac5ac239123b1e1dc19af2ae5834b8a892
bound_set_digest: 66b34272f82e28b213b22a1847b3eece77e7bec663889b1752cc74b3fdf93432
job_id: review-mtf2teyn-c9ofbu
job_class: review
base: 2b4bafb0
scope: branch
prior_verdict: docs/reviews/phase0-completion-contract/20260829-213929/verdict.md
cancelled_job: review-mtf2rtfq-3dikow   # 중복 디스패치 — 아래 «운영 기록»
```

**게이트 판정: 통과 아님.**  findings **1** — (a) 신규 material.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 불가. (a) 신규 material 1건: 49차는 두 커밋의 순서, 단일 측정 함수, blob 대비 기입값·워킹트리 양쪽 검사, 부재·재측정 실패·비단수 red, paired mutant를 구현했지만 `measured_against.kind=worktree`를 여전히 green으로 허용해 핵심인 «불변 blob» 결속을 우회한다. 인메모리 반례에서 문서 셀 17→18, 기준값 18, 출처 worktree를 함께 적용하자 위반 0건이었다. (b) 핀을 이미 셀이 늘어난 커밋으로 옮기는 세탁과 기존 셀 안 숨기기는 명시 잔여이므로 finding에서 제외했다. 기본 검사는 rc 0이었고 배터리는 137종 존재를 확인했으나, 읽기 전용 환경의 임시 디렉터리 부재로 self-test 완주는 재검증하지 못했다. 나머지 계획 기준인 단계 순서·의존성, 실패/롤백, 범위, 비협상 규칙, 설정·운영 누락에서는 별도 material finding을 확인하지 못했다.",
  "findings": [
    {
      "severity": "high",
      "title": "(a) `worktree` provenance가 불변 blob 결속을 다시 가변 기준으로 만든다",
      "body": "`read_baseline_source`는 `kind == worktree`이면 커밋 blob 대신 현재 계약 파일을 읽으며, `check_c2up`도 이를 위반이 아닌 NOTICE로만 처리한다. 따라서 공격자가 픽스처 행에 셀을 추가하면서 `fixture_row_cells`를 올리고 `measured_against.kind`를 `worktree`로 바꾸면, 기입값·출처·검사 대상이 모두 같은 가변 문서를 가리켜 통과한다. 실제 검사 함수를 대상으로 이 구성을 모사하자 18셀에서 `check_fixture_row_shape` 위반이 0건이었다. 이는 계약의 “기준은 measured_against가 가리키는 불변 blob” 및 재측정 실패는 red라는 선언보다 기계 능력이 좁고, 현재 137종 배터리에도 이 paired worktree 대조군이 없다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 1620,
      "line_end": 1629,
      "confidence": 0.99,
      "recommendation": "정상 검사 경로에서는 `measured_against.kind`를 `commit`으로만 허용하고 `worktree`를 red로 처리하라. 커밋 전 측정 편의가 필요하면 `--measure-baseline worktree`의 출력 기능만 유지하되 그 결과는 게이트를 통과하지 못하게 분리하고, 문서 셀 추가 + 기준값 갱신 + `kind=worktree`를 함께 적용한 뮤턴트가 반드시 red인지 배터리에 추가하라."
    }
  ],
  "next_steps": [
    "`check_c2up` 또는 공통 provenance 파서에서 `kind=worktree`를 게이트 위반으로 승격한다.",
    "가변 worktree 출처를 사용한 paired mutant와 정직한 commit 출처의 역방향 대조군을 추가한다.",
    "쓰기 가능한 임시 디렉터리가 있는 환경에서 `.venv/bin/python tools/tos_contract_check.py --self-test`를 다시 실행해 138종 이상 전건 판별·죽은 검사 0을 확인한다.",
    "(b) 두 명시 잔여는 이번 신규 finding과 분리해 계속 잔여로 추적한다."
  ]
}
```

원문 전체(잡 메타 포함)는 `.omc/review/20260830-093036/codex-raw.json`.

---

## 수용검사 (오케스트레이터 = Claude)

**채택 1 · 기각 0 · 팬텀 0.**

### 결속 대조

`bound_set_digest` 재계산 = `66b34272…` — O-6(`85327ee1`) 기입값과 **일치**.  결속 유효.
`plan_scope_digest` = `86de6bf6…` (심판 디스패치 직전 포착 · 심사 중 편집 0).

### 동결 실측 (재심 이전에 오케스트레이터가 먼저 돌린 것)

| 실측 | 결과 |
|---|---|
| 추적 트리 clean @ `9f31605e` · 계약 blob | `8b54e1bc…` |
| **핀 blob == HEAD blob** (49차가 문서·검사기를 두 커밋으로 가른 근거) | **일치** |
| 검사기 `tools/tos_contract_check.py` | **rc 0 · PASS** |
| `--self-test` (`.venv/bin/python`) | **PASS — 137종 전건 판별 · 죽은 검사 0** |
| 래칫 3축 | 미앵커 **67** · 닫힌 표 **32** · 픽스처 셀 **17** — 전부 불변 |

### 독립 재현 — 직전 지적(#9)은 «해소»다

| 실측 | 결과 |
|---|---|
| #9 우회 재주입: 문서 **+1 셀**(17→18) **AND** 기준값 17→18 (`measured_against` 불변) | **red · `TOS-CC-CAP2-FIXTURE` 2건** — 두 다리가 각각 발화 |
| ⑴ 기입값 다리 | 「기준선의 자기 주장이 거짓이다 — 18 이지만 `5fc3ac00:…` 를 다시 재면 17」 |
| ⑵ 워킹트리 행 다리 | 「픽스처 행 셀 수가 측정 출처와 다르다 (출처 17 · 실측 18)」 |
| **대조군**: 같은 뮤턴트를 **48차 구판 검사기**로 | `TOS-CC-CAP2-FIXTURE` **0건** — 그 판에선 보이지 않는다 |
| 배터리 신규 대조군 실재 | `CAP2-escape-new-cell-with-baseline-bumped`(1→2) · `CAP2-FIXTURE-baseline-disagrees-with-blob` |
| 등재 잔여 (b): 기존 셀 «안»에 숨기기(셀 수 17 불변) | **green** — 계약이 등재한 자리와 일치 |

**#9 의 finding (a)는 회피가 아니라 해소다.**  49차가 주장한 여섯 다리 중 ①~⑥ 이 실측으로 성립한다.

### 독립 재현 — 그러나 심판의 신규 지적도 **성립한다**

심판은 **인메모리 모사**로 주장했으므로 오케스트레이터가 **검사기 실행**으로 다시 쟀다.

| 구성 | `TOS-CC-CAP2-FIXTURE` |
|---|---|
| 문서 +1 셀(18) · 기준값 18 · `kind: **commit**`(핀 `5fc3ac00`) | **2건 (red)** |
| 문서 +1 셀(18) · 기준값 18 · **`kind: worktree`** | **0건 (통과)** — 기계가 내는 것은 위반이 아니라 **NOTICE** 하나뿐 |

NOTICE 전문: 「기준선 측정 출처가 «worktree»(커밋 전)다. 워킹트리는 불변이 아니므로 이 결속은
**잠정이다** — 계약 편집을 커밋한 뒤 `--measure-baseline <sha>` 로 재측정해 `'kind': 'commit'` 로
승격하라.」  **NOTICE 는 rc 를 올리지 않는다.**

구조 관측 둘:

- `--self-test` 이름 중 `worktree` 를 쓰는 대조군 **0종** — 「배터리에 없다」는 심판 주장 **확인**.
- 현재 실기준선의 `kind` 는 **`commit`** 이다 — 그러므로 **오늘의 CI 는 정직하고 green 이다.**
  이 지적은 «현재 red 인 것»이 아니라 **열려 있는 우회로**다.  그 구별을 판정문에 남긴다.

### 지적의 본질 — 문언이 능력보다 넓다 (다섯 번째)

49차 문언은 「기준은 `measured_against` 가 가리키는 **불변 blob**」이다.  그러나
`measured_against.kind` 는 두 값을 받고 그 중 `worktree` 는 **불변이 아니다** —
`read_baseline_source`(`tools/tos_contract_check.py:1620-1629`)가 그 경우 커밋 blob 이 아니라
**현재 워킹트리 파일**을 읽는다.  즉 계약이 «불변» 이라 부른 자리에 **가변 값이 합법으로 들어간다.**

층은 이렇게 내려왔다: 면제의 단위 → 판별 순서 → 운반체 → 정체의 종류 → 정체의 «출처» →
**출처의 «불변성» 자체**.

### 기각 사유 대조

| 검사 | 결과 |
|---|---|
| `file:line` 실재 (`tools/tos_contract_check.py:1620-1629`) | **실재** — `read_baseline_source` 의 `BASELINE_KIND_WORKTREE` 분기 |
| 의도적으로 silenced 인가 | **아니다.**  NOTICE 는 실재하지만 **계약 문언이 그 잠정성을 등재하지 않았다** — 계약은 정반대(「불변 blob」)를 주장한다.  기계가 낮춘 것을 산문이 도로 올려 적은 형태다 |
| 비협상 규칙 배치 | **없음** (배치 0 — **24판 연속**) |
| 범위 밖 기존 부채인가 | **부분적으로만.**  `worktree` 어포던스 자체는 `60c76134`(2026-08-26, C2U/C2UP 축)로 **선행**한다.  그러나 **그 리더에 의존하면서 «불변 blob» 을 주장한 축을 신설한 것은 49차**다 → **범위 안** |

### S-26 ② 카운터

**0 — 열한 판 연속 0.**  이번 판은 material 1 이므로 카운터가 서지 않는다.
궤적: findings 4 → 2 → 3 → 2 → 1 → 2 → 1 → 1 → 1 → **1**.

---

## 오케스트레이터 관측 (판정 아님 — 이 verdict 로 처분되지 않는다)

1. **자기 문서에도 같은 과대 문언이 실려 있다.**  O-6 재결속 기록(`85327ee1`)과 49차 에라타
   (`5fc3ac00`)가 둘 다 「기준은 `measured_against` 가 가리키는 **불변 blob**」이라 적었다.
   50차 처분은 **검사기와 이 두 자리를 한 단위로** 봐야 한다 — 「규칙 신설 = 전수 적용까지가
   한 단위」가 이 아크에서 깨진 여섯 번째 자리가 되지 않게.
2. **심판이 배터리를 또 완주하지 못했다.**  #9 는 PyYAML 부재(`exit 2`), #10 은 읽기 전용
   샌드박스의 임시 디렉터리 부재다.  **두 회차 연속 «배터리 관련 주장이 실행이 아니라 독해에
   근거»**했다.  이번에는 그 주장(대조군 0종)이 **참으로 확인**됐지만, 확인한 것은
   오케스트레이터이지 심판이 아니다 — 심판 레인의 실행 표면은 구조적 제약으로 남아 있다.
3. **`--measure-baseline worktree` 는 게이트를 통과하는 출력물을 낸다.**  그 출력을 그대로
   기준선에 붙여넣으면 `kind: worktree` 가 들어가고, 위 표대로 픽스처 축이 조용해진다.
   즉 «편의 경로»가 «우회 경로»와 같은 산출물을 낸다.

---

## 운영 기록 (정직)

심판 잡이 **둘 디스패치**됐다 — `review-mtf2rtfq-3dikow`(00:32:27Z) 와
`review-mtf2teyn-c9ofbu`(00:33:42Z), 둘 다 `base 2b4bafb0` · 같은 세션.
완주한 것은 후자이고 전자는 오케스트레이터가 **취소**했다(`turnInterruptAttempted: true`).
판정은 완주한 한 잡에서만 왔고 두 산출물을 섞지 않았다.

**잡 id 추적 실패가 세 회차 연속**이다 — #8 은 id 추출 실패로 직전 판정문을 오독했고,
#9 는 매달린 잡을 구조 관측으로 판별해 재디스패치했으며, #10 은 중복 디스패치다.
매번 다른 형태지만 원인은 같다: **디스패치와 회수 사이에 id 를 구조로 붙들지 않는다.**
이번엔 오케스트레이터가 `status --all --json` 으로 잡 목록을 **직접** 관측해 중복을 적발했다.
