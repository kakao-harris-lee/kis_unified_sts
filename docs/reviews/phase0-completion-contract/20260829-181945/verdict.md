# 레인 B 계획 «재심» — 42차 처분 판 (현행 버전 재심 #3)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: a9b87e4da38c7ce6aa8a272499f88ee144cdb38a
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: d8eeb116caa8e45c45055c5c59370cc98731af451e320d4ca5c39c8f2fd49e3b
job_id: review-mte66otn-rtbpzk
job_class: review            # adversarial-review = 게이트 적격 유일 경로
base: 606781af
scope: branch
elapsed: 3m 19s
prior_verdict: docs/reviews/phase0-completion-contract/20260829-152144/verdict.md
bound_set_digest_at_review: 4d8c4ae3c296b363223b41c01d819b07a3dfca0b0663638dfec0d5ce31873f0b
```

**게이트 판정: 통과 아님.**  findings **2 → 3**(high 2 / medium 1).

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "출하 불가. 42차는 직전 4개 예시만 red로 만들었을 뿐 CAP-2와 C4C 모집단을 닫지 못했다. CAP-2 F1은 회피, C4C F2는 부분해소다. R-3의 살아 있는 SHA 핀 10곳은 1817c9ef…로 일치했고, §S-26은 이론상 동일 입력을 동결하면 수렴 가능하지만 현재 ‘세 판 연속 0’은 진전이 아니라 매 편집마다 리셋됐다는 뜻이다.",
  "findings": [
    {
      "severity": "high",
      "title": "CAP-2가 여전히 같은 행·백틱·최근 3개 스팬이라는 표기에 의존한다",
      "body": "결과 토큰에서 시작한다는 주장과 달리 분류기는 화살표와 같은 행에 있는 백틱 코드스팬 중 마지막 3개만 검사한다. 현행 문서에 `total_count > 1000 → PREVENTION_UNVERIFIABLE`(백틱 없는 선행항), 줄바꿈 코드스팬, 또는 임계항 뒤 `a`·`b`·`c` 스팬을 주입한 세 경우 모두 CAP 사이트가 4→4, RULE-MISSING 0→0으로 조용히 통과했다. 반면 전각 숫자와 ≥는 정상적으로 red였다. 따라서 신규 상한 술어가 구조 파생 항 없이 추가되어도 검사기가 전수 적용을 거짓으로 보증할 수 있다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2284,
      "line_end": 2291,
      "confidence": 0.99,
      "recommendation": "임의의 최근 3개 코드스팬을 읽지 말고 Markdown 구조를 파싱해 결과 토큰의 전체 선행식을 추출하라. 파싱되지 않는 살아 있는 PREVENTION_UNVERIFIABLE 자리는 모집단 밖으로 버리지 말고 fail-closed PARSE 위반으로 처리하며 위 세 변이를 self-test에 추가하라."
    },
    {
      "severity": "high",
      "title": "표 행 전면 배제가 규범 술어에 무료 우회키를 준다",
      "body": "`line.lstrip().startswith('|')`이면 표의 종류나 의미를 확인하지 않고 CAP-2 우주에서 제외한다. 실제로 `| 신규 규범 | total_count > 1000 → PREVENTION_UNVERIFIABLE |` 형태의 규범 행을 주입했을 때 CAP 사이트와 RULE-MISSING이 모두 불변이었다. 이 계약은 규범 표를 광범위하게 사용하므로 ‘표는 픽스처 자리’라는 가정은 구조적 배제가 아니다. 상한 규범을 표로 이동하거나 새 표 규범으로 추가하면 구조 파생 항 의무가 사라진다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2281,
      "line_end": 2283,
      "confidence": 0.99,
      "recommendation": "모든 표 행을 면제하지 말고 닫힌 이력표 및 명시적으로 식별된 픽스처 셀만 구조적으로 제외하라. 일반 표의 규범 셀은 CAP-2 모집단에 포함하고 규범 표 주입 뮤턴트를 red로 고정하라."
    },
    {
      "severity": "medium",
      "title": "C4C 확장은 구분자 뒤 공백 하나에도 의존해 즉시 우회된다",
      "body": "정규식의 `[=:]\\s`가 구분자 뒤 공백을 필수로 요구한다. 자연스러운 `다음 단계=42차 → addendum-9 → O-6 재결속 → 재심`을 주입하자 C4C가 0→0으로 통과했다. 전각 콜론 `：`과 줄바꿈 열거도 동일했다. 이는 인정한 ‘형제 표기 목록 밖’ 잔여보다 더 좁은 문제로, 이번에 지원한다고 명시한 `다음 단계`와 `=` 조합 자체가 공백 하나로 탈출한다. 미래 단계를 stale 회차로 고정해도 green이므로 F2는 해소되지 않았다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 1932,
      "line_end": 1936,
      "confidence": 0.99,
      "recommendation": "구분자 주변 공백을 선택적으로 처리하고 Unicode 구분자·줄바꿈을 정규화하라. 더 근본적으로는 유한한 한국어 접두 목록 대신 문서가 선언한 미래 지향 필드와 단계열거 구조에서 모집단을 파생하고, 무공백·전각 구분자·개행 변이를 self-test에 추가하라."
    }
  ],
  "next_steps": [
    "CAP-2 파서를 fail-closed 구조 파생으로 교체하고 백틱 없음·개행·4번째 스팬·규범 표 변이를 모두 red로 만든다.",
    "C4C에 무공백·전각 구분자·개행 및 목록 밖 미래 지향 필드 변이를 추가한다.",
    "수정 후 문서를 동결한 채 서로 다른 심판 잡에서 material finding 0을 두 번 받아야 §S-26 카운터가 실제로 0→1→2로 진행한다."
  ]
}
```

---

## 수용검사 (오케스트레이터 = Claude)

**채택 3 · 기각 0 · 팬텀 0.**  세 건 모두 **독립 재현**했다 — 주입 여섯 형상 중 **여섯 전부
green(탈출)** 이었고 전각 숫자만 이미 red 였다(심판 서술과 일치).

| finding | 재현 결과 | 처분 |
| --- | --- | --- |
| **F1**(high) CAP-2 가 «같은 행·백틱·마지막 3스팬» 표기에 의존 | ✔ 백틱 없는 선행항 · 임계 뒤 스팬 셋 · 줄바꿈 분리 **3/3 탈출** | **채택** |
| **F2**(high) 표 행 전면 배제가 무료 우회키 | ✔ 규범 표 행 주입 **탈출** | **채택** |
| **F3**(medium) C4C 가 구분자 뒤 공백에 의존 | ✔ 무공백 · 전각 콜론 **2/2 탈출**(개행 열거도) | **채택** |

**심판이 확인해 준 것(비-차단)**: R-3 의 **살아 있는 sha 핀 10곳이 `1817c9ef…` 로 일치** ·
§S-26 은 **동일 입력을 동결하면 이론상 수렴 가능**하며 «세 판 연속 0» 은 진전이 아니라
**매 편집마다 리셋됐다는 뜻**이다(정확한 독법).

**비협상 규칙 대조**: 세 권고 어느 것도 `CLAUDE.md` 비협상 8항과 배치되지 않는다. **배치 0**(17판 연속).

## 이 재심의 요지

**표기 의존은 한 번 걷어내서 끝나지 않는다.**  42차는 «표기 → 구조»를 주장했지만 그 «구조»가
다시 (같은 행·백틱·스팬 위치·표 행 배제)라는 **더 작은 표기 가정** 위에 서 있었다.
심판이 그 가정을 하나씩 밟아 여섯 개를 통과시켰다.
