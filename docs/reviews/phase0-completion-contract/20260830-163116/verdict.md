# 레인 B 계획 «재심» — 50차 판 두 번째 독립 심사 (재심 #12)

```yaml
adjudicator: codex
verdict: approve
reviewed_at_head: 0fc2fba7
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: feaa42a07193cc305c0f39c0d09281f152f318b2fd1ce4a24cf269456eaf2521
bound_set_digest: daaba47b1c4b2b31717c098c8d761d9fd2b0cd1eb7e0d55b48d46a4e059f1c3b
job_id: review-mtfhrjoi-tou562
job_class: review
base: 169414b8
scope: branch
prior_verdicts:
  - docs/reviews/phase0-completion-contract/20260830-093036/verdict.md   # #10 needs-attention
  - docs/reviews/phase0-completion-contract/20260830-131640/verdict.md   # #11 approve
```

**findings 0 · 신규 material 0.  S-26 ② 카운터 = 2 — 이 아크 최초의 «2회 연속»이다.**

**그러나 종결은 주장할 수 없다.**  S-26 은 ①~⑥ 의 **AND** 이고 **⑤ 가 두 회 모두
독립 검증되지 않았다**.  심판이 스스로 그렇게 적었다(next_steps 두 번째).

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "approve",
  "summary": "신규 material을 확인하지 못했다. 일곱 주장 중 기본값 False, allow_mutable=True 단일 호출, worktree의 C2UP·CAP2 red, NOTICE 경로 제거, 측정 출력의 measured_against 부재, 141종 정의, c8beea93 재핀을 독립 확인했다. 기본 검사는 rc 0이며 67/32/17도 일치한다. 다만 임시 디렉터리를 만들 수 없어 self-test는 rc 2로 중단됐으므로 141종 전건 판별·죽은 검사 0은 독립 검증하지 못했다. 계약 본문의 오래된 심사 상태·재결속 위치와 closed_table_rows의 provenance 미보호는 S-26 ⑧ 및 기존 등재 잔여이므로 (b)로 분리하며 finding으로 세지 않는다.",
  "findings": [],
  "next_steps": [
    "쓰기 가능한 임시 디렉터리에서 `.venv/bin/python tools/tos_contract_check.py --self-test`를 실행해 141종 전건 판별·죽은 검사 0·과잉 차단 0을 독립 확인한다.",
    "배터리 독립 실행이 완료되기 전에는 이번 판을 S-26 ⑤까지 충족한 두 번째 청정 사이클로 간주하지 않는다.",
    "(b) S-26 ⑧의 헤더 심사 상태·절차표 현재 위치와 `closed_table_rows` provenance 잔여를 기존 열린 요건으로 계속 추적한다."
  ]
}
```

원문 전체는 `.omc/review/20260830-163116/codex-raw.json`.

---

## 수용검사 (오케스트레이터 = Claude)

**채택 0 · 기각 0 · 팬텀 0** (findings 0).

### 결속·무편집 대조 — 전건 성립

| 검사 | 결과 |
|---|---|
| `plan_scope_digest` 포착 == 재계산 | `feaa42a0…` **일치** — 심사 중 편집 0 |
| `bound_set_digest` OQ-11 == 재계산 | `daaba47b…` **일치** — 결속 유효 |
| **S-26 ①ⓑ 이력 술어** `git rev-list --full-history 2cdf2541..HEAD -- <계약 문서>` | **공집합** |
| 같은 술어 · 둘째 결속 문서 | **공집합** |
| 계약 blob (t=`2cdf2541` vs 주장 시점) | `ecbd478e…` **불변** |
| 그 사이 커밋 | `0fc2fba7` 하나 — `docs/reviews/` 이므로 **계약 본문 아님** |

**⑥ 리셋은 발화하지 않았다.**  blob 대조가 아니라 **이력 술어**로 쟀다 —
20차 ⓑ 가 정정한 대로 「편집 `E` → 심사 → `revert(E)`」 창은 상태 비교로는 닫히지 않는다.

### (b) 분류 검증 — 심판이 under-count 하지 않았는가

심판이 (b) 로 분리한 둘 중 **내가 몰랐던 항목**(`closed_table_rows` provenance 미보호)이
실제로 계약에 **등재**되어 있는지 실측했다.

> `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3899`
> 「다만 그 보호는 **키별**이라 33차가 얹은 `closed_table_rows` 에는 **없다** — 세 번째 키를
> 얹으면 그것도 **보호 없는 쪽**에 선다.  **등재**(초안과 함께 죽지 않는 잔여이며, 닫는 자리는
> `C2UP` 의 우주다).」

**등재 확인.**  심판의 (b) 는 정확하고 신규 material 을 잔여로 접은 것이 아니다.
헤더 심사 상태·절차표 현재 위치도 S-26 ⑧ (반증 4 ⓐ · 28차 ⓷)에 등재돼 있다.

**부수 관측 — 그 등재의 예측이 «좋은 방향으로» 반증됐다**: :3899 는 「세 번째 키를 얹으면
그것도 보호 없는 쪽에 선다」고 적었다.  그 세 번째 키가 49차의 `fixture_row_cells` 이고,
**49·50차가 그 키에 보호를 붙였다**(출처 blob 재측정 + 불변-출처-only 기본값).  예측은
빗나갔고 남은 미보호 키는 **`closed_table_rows` 하나**다 — 잔여의 폭이 줄었다.

### S-26 축별 상태 (이 판정 시점)

| 축 | 요건 | 상태 |
|---|---|---|
| ① 동결 | t·t+1·주장 시점 계약 blob 불변 (이력 술어) | **충족** — 위 표 |
| ② 독립 재심 2회 연속 material 0 | 서로 다른 심판 잡 | **충족 — 카운터 2** (`review-mtfbo7h2-47vquv` · `review-mtfhrjoi-tou562`) |
| ③ 두 회 모두 validator rc 0 | | **충족** — 두 회 모두 심판이 rc 0 확인 |
| ④ 두 회 모두 CUR/CIT/VER/CARD/RULE 위반 0 | | **충족** — rc 0 이 그 정의다 |
| ⑤ 두 회 모두 배터리 전건 red · 죽은 검사 0 · 과잉 차단 0 | | **미충족(미검증)** — 두 회 모두 심판이 `--self-test` rc 2 로 중단 |
| ⑥ 카운터 리셋 | 계약 본문 편집 | **발화 안 함** |
| ⑧ 도달 가능성 | 헤더 심사 상태 · 절차표 현재 위치 · `closed_table_rows` provenance | **열림 (등재)** |

**AND 이므로 종결 주장 불가.**  D0/P-0 착수 금지 불변.

### 이번 판정의 «강도» — #11 보다 강하다

#11 의 approve 는 두 번의 매달림 뒤 **범위를 축소한 focus** 위에서 났다.  #12 는 그 약점을
의도적으로 보정했다: ⓐ focus 에 **「#11 의 판정을 인용하지 말고 독립적으로 다시 판단하라」**
를 명시했고 ⓑ **#11 이 스스로 승인하지 않은 레그**를 지목해 닫을 수 있는지 물었으며
ⓒ **계약 본문의 현행성**을 별도 축으로 세우고 「등재되어 있다는 사실만으로 면제되지 않는다 —
등재 문언이 실제 상태와 어긋나면 신규다」를 (b) 규칙에 못박았다.  ⑧ 노출을 숨기지 않았다.

심판은 그 축에서 **일곱 주장을 개별 재검증**했고(요약이 항목별로 열거한다) (b) 판단도
스스로 내렸다.  즉 이 approve 는 #11 의 반복이 아니라 **독립 판단**이다.

### 비협상 규칙 대조

**배치 0 — 26판 연속.**  findings 0 이므로 기각 대상 없음.

### S-26 ② 카운터

**2 — 이 아크 최초.**  궤적: findings 4 → 2 → 3 → 2 → 1 → 2 → 1 → 1 → 1 → 1 → **0 → 0**.

---

## 오케스트레이터 관측 (판정 아님)

1. **남은 단일 차단축은 ⑤ 이고, 그것은 «계약 본문을 건드리지 않고» 닫을 수 있다.**
   배터리가 임시 디렉터리 없이 돌면 심판이 독립 검증할 수 있다.  ⑥ 은 **계약 본문 편집**만
   리셋하므로 `tools/` 전용 변경은 카운터 2 를 죽이지 않는다.  다만 그 변경은 50차가 방금
   잠근 기준선 리더 표면에 닿으므로 **회귀 위험이 실재**하고, 오케스트레이터는 심판이 부딪힌
   샌드박스 제약을 **로컬에서 재현하지 못했다**(`TMPDIR` 을 쓰기 불가로 두면 `tempfile` 이
   폴백해 141종 그대로 PASS).  **재현되지 않은 결함 위에 처분을 세우는 것**이 되므로,
   착수 여부는 판정이 아니라 결정 사항이다.
2. **⑧ 은 여전히 열려 있고 그것이 종결의 상한이다.**  처방 초안이 **다섯 연속 기각**된 자리다.
   ② 가 2 에 도달한 지금도 ⑧ 이 열려 있는 한 「종결」은 주장할 수 없다.
3. **`closed_table_rows` 가 마지막 미보호 키다.**  `C2UP` 의 우주를 그 키까지 넓히는 것이
   등재된 «닫는 자리»이고, 그것도 `tools/` 전용 변경이다.

---

## 운영 기록 (정직)

**이 회차는 잡 1건 · 완주 2분 53초 · 중복 0 · 매달림 0.**  직전 회차(#11)가 세 번 띄워
둘이 매달렸던 것과 대조된다 — 달라진 것은 focus 크기이며, 그 상관은 **관측이지 인과 증명이
아니다**(대조 실험을 하지 않았다).

**절차 이탈(계속)**: `codex-plan-reviewer` 포워더를 거치지 않고 오케스트레이터가 companion 을
직접 호출했다(#11 과 동일).  사유·성질은 #11 판정문에 적은 것과 같다 — 심판자는 Codex 이고
verbatim 은 `result --json` 원문을 보존했으므로 독립성은 유지되나, 하네스 계약의 이탈이다.
**네 회차 연속 포워더 실패 뒤 두 회차 연속 직접 호출이 무사고**라는 사실도 함께 적는다.
