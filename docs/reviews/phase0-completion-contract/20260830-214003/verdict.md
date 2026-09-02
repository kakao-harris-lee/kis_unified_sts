# 레인 B 계획 «재심» — 57차 판 (재심 #19)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 87e25cb8
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 8ccc94785fcbf7afd699e9b464713e7cd537944cf13427550e762c16e22386fc
bound_set_digest: daaba47b1c4b2b31717c098c8d761d9fd2b0cd1eb7e0d55b48d46a4e059f1c3b
job_id: review-mtfssjti-zfb1xv
job_class: review
base: 95adb2ca
scope: branch
prior_verdict: docs/reviews/phase0-completion-contract/20260830-212813/verdict.md
```

**게이트 판정: 통과 아님.**  findings **3 (medium 3)** — 전부 신규 material · 전부 저작 산문.
**S-26 ② 카운터 0 유지** (일곱 회차 연속 needs-attention).

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 보류. 신규 material (a) 3건이다: C1의 다섯 번째 술어 불일치, 픽스처 정규화에 관한 거짓 주장, 선행 창 식에서 누락된 공백이다. 기본 검사는 rc 0·경고 0이며 미앵커 67·닫힌 표 32·픽스처 셀 17을 재현했다. `--self-test`는 쓰기 가능한 임시 디렉터리가 없어 rc 2였으므로 145종 배터리는 독립 검증하지 못했다. 50·51차 회귀 축에서 추가 결함은 발견하지 못했다(없음을 증명한 것은 아님).",
  "findings": [
    {
      "severity": "medium",
      "title": "C1의 «아라비아 숫자만»이라는 새 설명은 Python의 Unicode 숫자 술어와 다르다",
      "body": "`CARDINALITY_TOKEN_RE`의 `\\d+`는 ASCII 아라비아 숫자만이 아니라 Unicode 십진 숫자도 받는다. 계약 6799행의 유일한 `아래 9개`를 정확히 `아래 ८개`(Devanagari 숫자 8)로 바꾸자 `check_c1`은 해당 행에 `TOS-CC-C1`을 발화했다. 따라서 새 문언이 주장하는 모집단보다 실제 모집단이 넓으며, 이는 #18 뒤의 다섯 번째 C1 의미 불일치다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 988,
      "line_end": 991,
      "confidence": 1.0
    },
    {
      "severity": "medium",
      "title": "픽스처 첫 셀은 정규화되지 않고 원문을 trim한 뒤 비교된다",
      "body": "`_fixture_row_id`는 `_split_cells(...)[1][1].strip()`을 manifest 앵커의 `strip()` 결과와 직접 비교하며 `_normalize`나 NFKC를 호출하지 않는다. 계약 2943행 첫 셀의 `| **T-84** |`를 정확히 `| **Ｔ-８４** |`로 바꾼 인메모리 탐침에서 두 셀은 `_normalize` 기준으로 모두 `T-84`였지만 `_fixture_row_id`는 false였고 CAP 모집단은 4→5가 됐다. 접두 5·완전일치 4라는 수치는 맞지만, «정규화한 첫 셀»이라는 새 사실 주장은 거짓이다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2454,
      "line_end": 2457,
      "confidence": 1.0
    },
    {
      "severity": "medium",
      "title": "새 판정 창 식이 구현의 결합 공백 한 자를 누락한다",
      "body": "문언은 `(prev + cur[:m.start()])[-GUARD_WINDOW:]`라고 적지만 구현은 `(prev + \" \" + cur[:m.start()])[-GUARD_WINDOW:]`이다. 계약 끝 10108행 뒤에 10109행 `| v2.22 | >=1000`, 10110행 `x` 294개 뒤 `→ PREVENTION_UNVERIFIABLE`을 주입했다. 문언의 식이면 300자 창이 `>=1000`부터 시작해 비교식과 수치를 모두 보지만, 실제 식은 삽입 공백 때문에 `=1000 x…`부터 시작하여 비교식을 잃고 모집단은 4로 불변이었다. 따라서 새 «필요조건이지 충분조건이 아니다» 설명은 실제 경계 조건을 온전히 기술하지 못한다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2466,
      "line_end": 2468,
      "confidence": 1.0
    }
  ],
  "next_steps": [
    "세 산문을 실제 정규식·완전일치·창 결합식에 맞춰 수정한다.",
    "쓰기 가능한 환경에서 `--self-test`를 실행해 145종 전건 판별·죽은 검사 0·과잉 차단 0을 확인한다.",
    "C1 Unicode 숫자, 픽스처 NFKC 변형, 선행 창 293/294/295자 경계를 실행 가능한 회귀 대조군으로 추가한다."
  ]
}
```

원문 전체는 `.omc/review/20260830-214003/codex-raw.json`.

---

## 수용검사 (오케스트레이터 = Claude)

**채택 3 · 기각 0 · 팬텀 0.**

### 결속 대조

`plan_scope_digest` 포착 == 재계산 `8ccc9478…` · `bound_set_digest` == `daaba47b…`
(결속 문서 무변경 → **O-6 재결속 불요**) · 계약 blob `ecbd478e…` 불변 ·
S-26 ①ⓑ 이력 술어 **공집합** — ⑥ 미발화.

### 세 건 전부 소스로 확정

| finding | 실측 |
|---|---|
| ① `\d` 가 유니코드 십진 | `CARDINALITY_TOKEN_RE.search` 가 `'9개'`·`'८개'`·`'９개'` **전부 True** — 「아라비아 숫자」는 능력보다 **좁은** 서술 |
| ② 정규화 안 함 | `:2412` `first = cells[1][1].strip()` · `first == anchor.lstrip("\| ").strip()` — **`_normalize`·NFKC 호출 없음**.  `_fixture_row_id('\| **Ｔ-８４** \| x \|')` = **False** |
| ③ 결합 공백 | `:2505` 구현은 `(prev + " " + cur[: m.start()])[-GUARD_WINDOW:]` — 내 문언은 `+ " " +` 를 빠뜨렸다 |

기각 사유 대조: `file:line` 실재 **확인** · 의도적 silenced **아니다** ·
비협상 규칙 배치 **없음**(33판 연속) · 범위 밖 부채 **아니다**(셋 다 57차가 쓴 문장).

### 정밀도가 한 단계씩 내려가고 있다

식별자 이름(#16) → 배제 계수(#17) → 조건 집합(#18) → **정규식 의미·정규화 유무·식 안의 공백
한 자**(#19).  지적이 «틀린 주장»에서 «덜 정확한 주장»으로 옮겨 갔고, 매번 참이다.

### S-26 축별 상태

| 축 | 상태 |
|---|---|
| ① 동결 (이력 술어) | 충족 |
| ② 2회 연속 material 0 | **0** — 일곱 회차 연속 material |
| ③ validator rc 0 | 충족 (경고 0) |
| ④ CUR/CIT/VER/CARD/RULE 0 | 충족 |
| ⑤ 배터리 독립 검증 | **미검증 — 열 회차 연속** |
| ⑥ 리셋 | 미발화 |
| ⑧ 도달 가능성 | 열림 (등재) |

**궤적: 1 → 1 → 2 → 2 → 3 → 3.**

---

## 오케스트레이터 관측 (판정 아님) — 이 루프는 수렴하지 않는다

**실측 근거**: 51~57차 = **일곱 판 연속 수리**, 재심 #13~#19 = **일곱 회차 연속 material**,
누계 **14건**, 전부 산문.  findings 는 줄지 않고 **늘었다**(1,1,2,2,3,3).
카운터는 여섯 회차 연속 0 이다.

**구조적 진단**: 결함이 난 자리는 전부 **«구현의 요약»** 이다.  요약은 필연적으로 전칭이나
계수를 부르고(모든·셋·하나뿐·통째·아라비아 숫자·필요충분), 나는 매번 **읽은 범위 안에서만**
그것을 세운다.  더 정확히 쓰려는 시도가 더 미세한 반례를 부르는 구조다.

**그리고 이 산문에는 기계 소비자가 없다.**  계약 자신의 K-10 이 「산문 선언은 소비자가 없으면
산문이다」라고 적는다.  검사기의 docstring·주석은 어느 게이트도 읽지 않는다.  즉 일곱 회차를
**게이트가 보지 않는 표면**에 썼고, 그동안 종결의 실제 상한인 **⑤(열 회차 연속 미검증)와
⑧(초안 1~5 기각)** 은 한 발도 움직이지 않았다.

**58차가 방식을 바꿨다**: 구현을 **요약하지 않고 정본을 가리킨다**(정규식·창 식을 옮겨 적지
않고 `CARDINALITY_TOKEN_RE`·`win = ...` 을 지목).  이것이 궤적을 꺾는지는 **다음 재심이
판별한다** — 지금은 가설이다.

---

## 운영 기록 (정직)

잡 1건 · 완주 3분 55초 · 중복 0 · 매달림 0.  포워더 우회 9회차 연속 무사고.

**보고 규율 결함(자기 적발)**: 오케스트레이터가 상태 보고에 적어 온 「미푸시 N」이 틀렸다.
오래전 한 번 11 을 측정한 뒤 **재측정 없이 숫자를 늘려** 적었다(17→19→…→41).
운영자 지적으로 실측: 원격 실물(`ls-remote`) `501f8fe2`(54차) · 실제 미푸시 **6**.
**구조 관측을 자기신고 위에 둔다는 이 아크의 규율을 판정 밖 보고에서 스스로 어겼다.**
