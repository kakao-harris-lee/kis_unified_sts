# 레인 B 계획 심판 — 현행 버전 재심 (v2.22 · 에라타 40차 이후)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 60718de843681738c911a6c69b1ed0f7f343b7f7
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 004bccec36ce55ffd39c82306a9e0295f685c228f2922b19e1bac74952b81324
job_id: review-mtdyszln-v809id
job_class: review            # adversarial-review = 게이트 적격 유일 경로
base: 082028e1
scope: branch
elapsed: 3m 32s
bound_set_digest_at_review: 44baa49d21876593a9d785b488e565345b354e054b1cd3b41f4073dd4ff344b5   # O-6 재결속 60718de8
```

**게이트 판정: 통과 아님.** `adjudicator: codex` ✔ · 결속 3자(HEAD·경로 집합·digest) 기록 ✔ ·
그러나 `verdict: approve` 가 아니다 — 세 조건은 AND 이므로 **D0/P-0 착수 불가 유지**.
이 아크의 approve 는 여전히 **0건**이다.

---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "NO-SHIP. R-F1은 의도적으로 차단된 미해소 상태이고 R-F4도 카운터 0을 정직하게 밝힌 미종결 상태다. 그러나 R-F2와 R-F3은 회피다: 완료됐다고 적은 실행기는 폐기 대상 경로를 그대로 사용하고, validator는 새 구조 파생 항을 삭제해도 green이다. 6e⁗ 술어화와 R-3 관행 규칙도 전수·기계 강제가 끝나지 않았다.",
  "findings": [
    {
      "severity": "high",
      "title": "완료됐다고 선언한 u17 실행기가 R-F2의 새 판정 경로를 구현하지 않는다",
      "body": "개발계획은 u17-verify 파일의 착지를 완료로 기록하지만, 현행 tools/u17-verify.sh:497-519는 계약이 vacuous green 때문에 제거한다고 명시한 commits/{sha}/check-runs를 계속 열거한다. 새 actions/workflows/.../runs → suite별 check-runs 경로와 |R| 상한은 실행기에 없고 이번 diff도 해당 파일을 변경하지 않았다. 따라서 실제 PREVENTION_ACTIVE 판정은 R-F2 처분 전 동작이며 1,000-suite 잘림을 놓칠 수 있다. 문서 검사 green은 실행기 의미를 검증하지 않는다.",
      "file": "docs/plans/2026-08-11-tos-completion-development-plan.md",
      "line_start": 292,
      "line_end": 294,
      "confidence": 1,
      "recommendation": "u17-verify를 계약의 ①-R→②-S→③-C 경로로 수정하고 실제 응답 픽스처로 세 상한과 suite별 소비를 검증한 뒤에만 파일 3종을 완료로 표기하라."
    },
    {
      "severity": "high",
      "title": "R-F3 validator가 40차 핵심 술어의 전수 적용을 검사하지 않는다",
      "body": "RULE 축은 엔드포인트가 우주·소비처 블록 양쪽에 등장하는지만 대조하고 각 소비처가 |collection| >= 1000 항을 실제로 갖는지는 검사하지 않는다. 실측으로 계약의 유일한 `|R| >= 1000 ∨ total_count > 1000`에서 구조 파생 항을 제거한 메모리상 변이에 check_document를 실행해도 위반 0이었다. 즉 보고된 102종 mutation green에는 바로 이번 변경을 되돌리는 mutation이 없으며, 세 소비처 중 하나가 다시 자기신고 전용으로 퇴행해도 gate가 green이다.",
      "file": "tools/tos_contract_check.py",
      "line_start": 2079,
      "line_end": 2084,
      "confidence": 1,
      "recommendation": "CAP-1과 별도로 구조 파생 상한 규칙을 manifest에 등재하고 세 소비처의 실제 술어를 파생·대조하라. |S|, |R_s|, |R| 항을 각각 제거하는 mutation이 해당 RULE 위반으로 red여야 한다."
    },
    {
      "severity": "medium",
      "title": "6e⁗ 술어화가 문서 전수로 적용되지 않아 이미 지난 단계가 여전히 '다음'이다",
      "body": "6e⁗ 셀에서는 회차별 단계 열거를 술어로 바꿨지만 머리말 currency 문장은 현행을 40차 이후로 갱신하면서도 다음 단계를 `10차 → addendum-6 → O-6 재결속`으로 남겼다. 10차와 addendum-6은 이미 완료된 이력이므로 운영 순서를 잘못 지시하는 stale 현재형이다. validator rc 0은 회차 태그만 보며 이 단계 열거의 의미적 stale을 검출하지 못한다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 110,
      "line_end": 110,
      "confidence": 0.99,
      "recommendation": "이 자리도 구체 회차·addendum 열거를 제거하고 6e⁗와 동일한 동결→재결속→현행 재심 술어를 참조하게 하며, 같은 현재형 패턴을 전역 검사하라."
    },
    {
      "severity": "medium",
      "title": "R-3 재봉쇄 방지가 강제되지 않아 승인 후 required check를 다시 영구 red로 만들 수 있다",
      "body": "39차의 전칭을 철회한 것은 맞지만 대체 처분은 'addendum은 새 스탬프 디렉터리를 만들지 않는다'는 관행뿐이다. 실제로 과거에 판정 뒤 verdict 없는 디렉터리를 만든 이력이 있고, R-3은 내용이 아니라 사전순 마지막 디렉터리를 고르므로 동일 행위가 재발하면 최신 approve가 있어도 APPROVAL_ABSENT가 되어 모든 PR이 막힌다. 대조군 형식이 다르다는 이유는 기계 강제를 생략할 근거가 아니며, 룰셋 활성화 뒤에는 보호 해제 없이는 복구 PR 자체가 막힐 수 있다.",
      "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md",
      "line_start": 4544,
      "line_end": 4551,
      "confidence": 0.96,
      "recommendation": "판정과 addendum 네임스페이스를 구조적으로 분리하고 HEAD 트리 mutation으로 재발을 red 처리하라. 또는 R-3이 검증된 verdict 스키마를 가진 판정 스탬프만 선택하도록 정밀화하고 stale approve 선택 대조군도 추가하라."
    }
  ],
  "next_steps": [
    "D0/P-0 착수와 룰셋 활성화를 계속 차단한다.",
    "u17 실행기와 계약을 동일 변경 단위로 맞춘 뒤 R-F2 경계 픽스처를 실제 실행한다.",
    "구조 파생 항별 mutation과 스탬프 트리 mutation을 필수 gate에 추가한다.",
    "stale 단계 열거를 전역 제거한 뒤 S-26 기준으로 동결된 독립 재심 2회를 새로 시작한다."
  ]
}
```

---

## 수용검사 (오케스트레이터 = Claude)

**채택 4 · 기각 0 · 팬텀 0 · pre-existing 분리 0.**

| finding | `file:line` 실재 | 의도적 silence | 비협상 배치 | 처분 |
| --- | --- | --- | --- | --- |
| **F1** (high) u17 실행기가 R-F2 새 경로 미구현 | ✔ 개발계획 `:292-294` = 40차가 «완료»로 적은 그 자리 · `tools/u17-verify.sh:497-519` 가 `commits/{sha}/check-runs` 를 **실제로 열거**(계약이 판정 경로에서 «제거»한 그 엔드포인트) | 아님 | 없음 | **채택** |
| **F2** (high) validator 가 40차 핵심 술어의 전수 적용을 검사 안 함 | ✔ **오케스트레이터가 독립 재현**: 세 자리(`\|S\|`·`\|R_s\|`·`\|R\|`)의 구조 파생 항을 각각 지운 변이에 `check_document` 를 돌려 **3/3 위반 0** — 죽은 검사 | 아님 | 없음 | **채택** |
| **F3** (medium) 6e⁗ 술어화가 전수가 아니다 | ✔ 계약 `:110` 머리말 currency 문장이 여전히 «다음 = N차 → addendum-M → 재결속» 회차 열거를 현재형으로 지시 | 아님 | 없음 | **채택** |
| **F4** (medium) R-3 재봉쇄 방지가 강제되지 않음 | ✔ 계약 `:4544-4551` = 40차 ⓓ 의 «관행 규칙 + 기계 강제 없음» 등재 | 아님 | 없음 | **채택** |

**팬텀 finding 0건.** 네 인용 좌표를 전부 원문에서 실측했고 내용이 서술과 일치한다.
**F2 는 심판 주장을 그대로 받지 않고 재현했다** — 대조군 없는 주장은 이 아크에서 증거가 아니다.

**비협상 규칙 대조(`CLAUDE.md`)**: 네 권고 어느 것도 선물 long/short 대칭 훼손 · 실계좌 증거금 ·
주식 EOD 일괄청산 · ClickHouse 신규 사용 · RL/TFT 부활 · 임계값/포트/Redis DB 하드코딩 ·
Redis DB 1 이탈 · 비-KST 세션 판정을 요구하지 않는다. **배치 0건 — 기각 사유 없음.**
(F1 권고의 «실제 응답 픽스처»는 GitHub REST GET 이며 KIS 실주문과 무관하다.)

## 1순위 과업의 답 — 직전 4건(R-F1~R-F4)의 해소 vs 회피

| 직전 판정 | Codex 판정 |
| --- | --- |
| **R-F1** D0-A 착수 불가 | **의도적 차단 · 미해소**(회피 아님) — 착수 금지가 유지되므로 정합 |
| **R-F2** 1,000-suite | **회피** — 계약 문언은 고쳤으나 **실행기가 폐기 대상 경로를 그대로 쓴다**(F1) |
| **R-F3** 규칙 전수 적용 기계 강제 | **회피** — validator 가 새 술어의 전수 적용을 **검사하지 않는다**(F2) |
| **R-F4** 수렴 | **미종결**(정직) — 카운터 0 을 스스로 밝힌 것은 회피가 아니다 |

**이 재심의 핵심**: 40차는 «문서에서 닫았다»를 «닫혔다»로 읽을 수 없다는 것을 두 자리에서
보여준다 — **소비자(실행기)와 측정자(validator)가 따라오지 않은 처분은 처분이 아니다.**
이것은 이 아크가 반복해 온 결함 클래스의 재발이며, 40차가 스스로 세운
「규칙 신설 = 전수 적용까지가 한 단위」를 **자기 처분에 적용하지 못했다**는 뜻이다.
