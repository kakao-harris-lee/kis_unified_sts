# 레인 B 계획 «재심» — 51차 판 (재심 #13)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 8c0f1533
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 6f7fc91fe39c1e5864e7992c1202bf584b6c4aebc14cce5a35f4c18661227024
bound_set_digest: daaba47b1c4b2b31717c098c8d761d9fd2b0cd1eb7e0d55b48d46a4e059f1c3b
job_id: review-mtfkbqk5-zcfaxp
job_class: review
base: f5dc76bc
scope: branch
prior_verdict: docs/reviews/phase0-completion-contract/20260830-163116/verdict.md
```

**게이트 판정: 통과 아님.**  findings **1 (medium)** — 신규 material.
**S-26 ② 카운터는 2 → 0 으로 리셋된다.**  원인은 저작 쪽 **부분 스윕**이다.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 보류. 두 다리 blob 대조, 불변 출처 기본값, 단일 파생 경로, 145개 mutation 정의(메타 2종 제외), 기존 CLOSED-TABLE 8종과 신규 4종은 코드상 유지됐다. 기본 검사는 rc 0, 측정값은 67/32/17이었다. 다만 `--self-test`는 임시 디렉터리 생성 실패로 rc 2여서 전건 판별 결과는 독립 검증하지 못했다. 계약 :3899의 stale은 능력을 축소 서술하고 코드·커밋에 공개된 이연이므로 신규 material로 보지 않지만, 검사기 내부 CLI 문구에는 처분 후 거짓이 된 부분이 남았다.",
  "findings": [
    {
      "severity": "medium",
      "title": "`--measure-baseline` 도움말이 새 세 번째 측정 키를 누락한다",
      "file": "tools/tos_contract_check.py",
      "line_start": 7118,
      "line_end": 7121,
      "confidence": 0.99
    }
  ],
  "next_steps": [
    "CLI 도움말 stale을 수정한 뒤 기본 검사와 `--measure-baseline <sha>`를 다시 실행한다.",
    "쓰기 가능한 임시 디렉터리에서 `--self-test`를 실행해 145종 전건 판별, 죽은 검사 0, 과잉 차단 0을 독립 확인한다.",
    "(b) 계약 :3899의 능력보다 좁은 stale 등재는 S-26 카운터 사이클 밖 계약 갱신 대상으로 계속 추적한다."
  ]
}
```

원문 전체는 `.omc/review/20260830-174303/codex-raw.json`.

---

## 수용검사 (오케스트레이터 = Claude)

**채택 1 · 기각 0 · 팬텀 0.**

### 결속 대조

`plan_scope_digest` 포착 == 재계산 `6f7fc91f…` · `bound_set_digest` OQ-11 == 재계산
`daaba47b…`(결속 문서 내용 무변경이라 **O-6 재결속 불요**) · 계약 blob `ecbd478e…` 불변 ·
S-26 ①ⓑ 이력 술어 **공집합** — ⑥ 은 발화하지 않았다.

### finding 실측 — 실재한다

| 검사 | 결과 |
|---|---|
| `file:line` (`tools/tos_contract_check.py:7118-7121`) | **실재** — argparse `--measure-baseline` 의 `help` |
| 문언 | 「미앵커 좌표**와** 픽스처 행 셀 수를 재어」 = **둘** |
| 실제 능력 | 51차 이후 **셋**(닫힌 표 행 수 추가) |
| 의도적 silenced 인가 | **아니다** — 같은 파일 `:6945` 의 `measure_baseline` docstring 은 이미 「**셋**」이라 적어 **자기모순**이다 |
| 비협상 규칙 배치 | 없음 (배치 0 — 27판 연속) |
| 범위 밖 기존 부채 | **아니다** — 51차가 이 판에서 만든 것이다 |

### 지적의 본질 — 이 아크의 «부분 스윕» 이 저작 쪽에서 재발했다

51차는 처분 문언 스윕을 지시받았고 후보를 셋 열거했다(`check_closed_tables` docstring ·
위반 메시지 · `measure_baseline` docstring).  **argparse `help` 문자열이 그 모집단에 없었다.**
같은 사실을 적는 자리가 넷인데 셋만 고쳤다 — 「규칙 신설 = 전수 적용까지가 한 단위」의
위반이고, 이 아크가 여섯 번 적발한 형상이다.  **이번에는 심판이 아니라 저작자가 냈다.**

### (b) 판단 검증 — 심판이 저작자의 자기 등재를 그대로 받았는가

focus 에 「저작자의 자기 등재를 그대로 처분으로 받아들이지 마라」를 명시해 계약 `:3899`
stale 을 **판단 대상으로** 올렸다.  심판은 그것을 **(b)** 로 분류하며 두 근거를 댔다 —
① **능력을 축소 서술**하는 방향이고 ② **코드·커밋에 공개된 이연**이다.  두 근거 모두
실측과 일치한다(방향은 fail-closed 쪽 · 공개는 `check_closed_tables` 주석과 `8c0f1533`
커밋 메시지에 실재).  **자동 승인이 아니라 근거를 댄 분류**이므로 채택한다.

### S-26 축별 상태

| 축 | 상태 |
|---|---|
| ① 동결 (이력 술어) | 충족 — 계약 blob 불변 |
| ② 2회 연속 material 0 | **0 으로 리셋** — 이번 판 material 1 |
| ③ validator rc 0 | 충족 |
| ④ CUR/CIT/VER/CARD/RULE 0 | 충족 |
| ⑤ 배터리 전건 red·죽은 검사 0 | **미검증** — 심판 `--self-test` rc 2, **네 회차 연속** |
| ⑥ 카운터 리셋(계약 본문 편집) | 미발화 — 리셋은 ⑥ 이 아니라 **②의 실패**로 왔다 |
| ⑧ 도달 가능성 | 열림 (등재) |

**리셋의 귀속을 정직하게**: 카운터가 죽은 것은 계약 본문을 건드려서가 아니라
**신규 material 이 나왔기 때문**이다.  `tools/` 전용 전략은 ⑥ 을 피하는 데는 성공했고,
실패한 것은 **저작 품질**이다.

### S-26 ② 카운터

**0.**  궤적: findings … → 1 → 1 → 1 → **0 → 0 → 1**.

---

## 오케스트레이터 관측 (판정 아님)

1. **심판이 놓친 같은 형상이 하나 더 있었다.**  `tools/tos_contract_check.py:313` 의
   「가변 출처는 이 리더에 매달린 **모든** 축(C2UP · CAP-2 셀 수)에서 함께 red 다」 —
   51차가 세 번째 축을 매달았으므로 이 괄호도 stale 이다.  심판은 CLI 도움말만 냈다.
   **리터럴 grep 이 아니라 «의미»로 훑어야 나오는 자리**이고, 52차가 함께 고친다.
   심판의 finding 이 아니므로 카운터에는 영향이 없다.
2. **⑤ 가 네 회차 연속 비어 있다.**  #10·#11·#12·#13 전부 임시 디렉터리 부재로 막혔다.
   S-26 은 AND 이므로 ② 를 다시 세워도 ⑤ 가 열려 있는 한 종결은 주장할 수 없다.
   이제 이 축은 «심판 레인의 제약»이 아니라 **종결의 실질적 상한** 둘 중 하나다(다른 하나는 ⑧).

---

## 운영 기록 (정직)

잡 1건 · 완주 2분 29초 · 중복 0 · 매달림 0.  포워더 우회 3회차 연속 무사고.
base 를 `f5dc76bc` 로 좁혀 diff 를 한 파일로 만든 것이 완주에 기여했을 수 있으나
**대조 실험을 하지 않았으므로 인과가 아니라 관측**이다.
