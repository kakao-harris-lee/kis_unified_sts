# verdict — 레인 B (계획 심판) · v2.19 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: be0cbc954f984a1e95869cac0463f401c7979003
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: dbfec7bcc57612c49646de505100812284a13719b3b6d9f2914ee22cf0da83f0
reviewed_version: v2.19 (7,403행) — 동결 d5a8302a · 증거 90a5ce7d · 에라타 6회(최종 359f5bc5) · S-24 addendum 8회(최종 a54676db) · 재결속 be0cbc95
findings: 5                        # high 3 / medium 2 — 직전 F1 부분해소 · #2 host 해소됨 · F2 해소됨 · F4 부분해소 · F5 해소됨(계약 수준) · #6 미해소(운영자 게이트) · 회피 0 · 신규 high 3
prior_verdict: .omc/review/20260819-074621/verdict.md   # v2.18 재심
mode: A (adversarial-review, --scope working-tree, --wait), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-mszmjz25-x6gnn4 / codex thread 01a01865-c0c1-7cb0-8bf5-2891dbe60ea0 (turn 01a01865-c223-7e83-a036-30992f2f945c)
     # 1회 디스패치 정상 완료(9m 36s) — 재시도 불요 · parseError null · companion 1.0.6
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **불변**(HEAD·plan_scope_digest·
내용-only digest `6817421a…` == 아티팩트 보유값 `OQ-11-DISPOSITION.md:10`). Codex 도
HEAD 와 두 digest 를 독립 재계산해 일치 확인. 재결속은 v2.19 6차 에라타 재동결
`359f5bc5` 내용에 대해 1회(`be0cbc95`).

## 처분

**직전 6건: F1 부분해소 · #2 host 해소됨 · F2 해소됨 · F4 부분해소 · F5 해소됨(계약
수준) · #6 미해소** — **아크 누적 해소 8**(host·F2·F5 = 6·7·8번째). 회피 0.
`CLAUDE.md` 비협상 직접 충돌 **없음**(12판 연속). 종수(T-81 19/T-82 20/T-84 12·U-17-c
10값·U-16-d 12단) 일치하나 «의미 정합 실패» 3곳(신규 high 3): ① U-17 (b)③ 워크플로
blob 검증이 두 리터럴 grep 이라 주석/미사용 값에 심어도 통과 — 하니스 «실행»이 아니라
«문자열 존재»를 인증(Codex 가 메모리 픽스처로 grep rc=0 ∧ 주석 밖 호출 0 재현) ②
U-16-a2 :6760-6762 «U-16-g 전 항(g1~g5)» 닫힌 열거가 현행 g6(:6928~)를 제외 — 바로 뒤
S-6 전칭 규율 문단과 자기모순(v2.13 g6 신설 시 a2 미전파 = S-22) ③ [PARENTS-UNTRUSTED]
㉡ 관측이 1회이고 이후 `%P`·`merge-base` 조상성 소비와 같은 스냅샷에 결속되지 않음 →
㉡ 통과 후 후보 밖 graft 설치·조상성 조회·제거 interleaving 이 LATE/ORDER_INVALID 를
ACTIVE/NO_ROWS_CLEAR 로 뒤집을 수 있음(계약 :7104-7108 이 ㉡ 을 유일 완화로 자인 —
addendum-8 은 정적 픽스처만). medium ④ F4 부분: T-82 ⑯ 이 여전히 «두 간선 각각에
`edge_seq` 1·2 승인 행» 지시 — ⑱만 고침(S-22 재발) ⑤ #6 미해소: 개발계획 :289-297
Phase 1 작업 7/종료조건 vs 계약 (D) — verbatim 제안은 결속 문서를 바꾸지 않음 → 두
문서가 같은 선행관계를 규정한 상태로 재결속·재심 전까지 레인 B/D0-A 차단(회피 아님·
운영자 게이트).

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

NO-SHIP. HEAD be0cbc95와 두 digest를 재계산해 제시값과 일치함을 확인했다. 직전 6건 판정: #1 F1 부분해소(5491-5536: 관측 가능한 off/on은 차단하지만 완전 강제 증명은 아님), #2 host 해소됨(5241-5269), #3 F2 해소됨(3548-3562), #4 F4 부분해소(⑱·전순서는 고쳤지만 T-82 ⑯과 U-16-a2에 stale 규범 잔존), #5 F5 해소됨—계약 수준(7030-7137), #6 미해소(개발계획 289-297 대 계약 4423-4464). 회피로 재분류할 항목은 없다. T-81 19/T-82 20/T-84 12, U-17-c 10값, U-16-d 12단의 종수는 일치하지만 의미 정합은 실패했다. addendum-8은 -7의 잘못된 후보집합 증명을 적절히 철회·대체하고 존재 증명으로 한정했으나 정적 픽스처일 뿐 아래 TOCTOU를 닫지 않는다. 7기준: (1) 단계·의존성 불충족—#6, (2) 숨은 가정 불충족—문자열 grep과 불변 git 메타데이터 가정, (3) 검증 가능성 불충족—해당 우회 변이 부재, (4) 실패·롤백 불충족—거짓 green에 대한 차단 신호 없음, (5) 범위 이탈·과잉설계 해당 없음, (6) CLAUDE.md 비협상 규칙 충돌 해당 없음, (7) 누락 불충족—현행 스키마·g6·계획 선행조건 전파 누락.

Findings:
- [high] U-17은 하니스 검증 실행이 아니라 비활성 문자열 두 개를 인증한다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5422-5431)
  5422-5431은 워크플로 blob에서 경로와 digest를 각각 grep한 뒤 이를 sha256 검증 스텝의 존재로 간주한다. 같은 경로의 워크플로가 두 문자열을 주석이나 미사용 값에 넣고 실제 job은 `true`만 실행해도 두 grep은 성공한다. 이 형태를 메모리 내 픽스처로 실행해 두 grep rc=0이면서 주석 밖 하니스 호출은 없음을 재현했다. run path, head SHA, Actions app, success 결속도 모두 충족할 수 있으므로 실제 동결 하니스를 실행하지 않은 gate가 PREVENTION_ACTIVE로 승인된다. 5356-5362의 GitHub 내부 실행 한계와 달리 이는 서버가 아니라 계약의 blob 판정 자체에서 발생한다.
  Recommendation: 동일 path/app/head의 성공 워크플로에 두 리터럴을 비활성 위치로만 심은 변이가 권위 U-17 소비자와 T-84에서 차단된다는 증거가 생기기 전에는 출하하지 말라.
- [high] U-16-a2의 폐쇄 범위가 현행 g6를 제외한다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:6758-6774)
  6758-6764는 모든 U-16-g 항을 요구하면서 이를 명시적으로 `g1~g5`로 한정한다. 바로 뒤 6766-6774는 번호 열거가 미래 규칙을 누락하므로 전 항을 자동 포섭해야 한다고 설명하지만, 현행 g6는 6928-6970에 실재하며 reviewer가 승인보다 선행했는지 강제한다. 다른 표면은 g6를 포함하므로 서로 다른 합리적 소비자가 상반된 계약을 구현할 수 있다. 닫힌 범위를 따르는 소비자는 R∥A를 승인해 APPROVAL_ORDER_INVALID를 우회할 수 있다.
  Recommendation: g6를 생략한 단일변이 소비자가 T-82 ⑮와 전체 U-16 판정에서 반드시 실패한다는 증거와 모든 규범 표면의 단일 해석이 확보되기 전에는 출하하지 말라.
- [high] PARENTS-UNTRUSTED의 graft 부재 관측과 조상성 소비 사이에 TOCTOU가 남는다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:7059-7063)
  7059-7063의 ㉡은 replace/grafts 부재를 한 번 관측할 뿐, 이후 `%P`·`merge-base --is-ancestor` 소비와 같은 불변 스냅샷에 결속하지 않는다. 문서도 7104-7108에서 후보 우주 밖 graft가 ㉠을 피하고 `--no-replace-objects`로도 무력화되지 않아 ㉡이 유일한 완화라고 인정한다. 따라서 ㉡ 통과 후 후보 밖 graft를 설치하고 조상성 조회 뒤 제거하는 동시 프로세스는 구조 대조와 부재 검사를 모두 통과하면서 LATE/ORDER_INVALID를 ACTIVE/NO_ROWS_CLEAR로 뒤집을 수 있다. addendum-8은 정적 graft 존재 픽스처만 증명해 이 시간축을 검사하지 않는다.
  Recommendation: ㉡ 검사와 조상성 조회 사이에 graft를 삽입·제거하는 interleaving 변이가 전체 U-16/U-17 소비자에서 fail-closed임을 입증하기 전에는 부모 신뢰 계약을 통과시키지 말라.
- [medium] F4는 부분해소다: T-82 ⑯이 폐지된 edge_seq 입력을 계속 요구한다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:2927)
  T-82 ⑯은 반복 이력의 두 승인 행에 `edge_seq` 1·2를 둔다고 여전히 지시한다. 같은 T-82 행의 ⑱과 현행 스키마(6821-6824)는 edge_seq 필드가 없고 소비자만 표시값을 파생한다고 규정한다. 따라서 ⑱만 고친 v2.19 증거는 전체 T-82 표면을 정합하게 만들지 못했다. ⑯을 문자대로 구현하면 존재하지 않는 필드를 다시 소비하거나 정상 반복 이력을 영구 차단하므로 S-22 재발이다.
  Recommendation: 현행 무-edge_seq 스키마로 ⑯ 양성을 전체 U-16 소비자에서 실행하고, 폐지 필드를 요구하거나 판정에 소비하는 변형이 실패함을 입증할 때까지 F4를 해소로 세지 말라.
- [medium] #6은 정직하게 기록됐지만 실제 계획 의존성은 여전히 미해소다 (docs/plans/2026-08-11-tos-completion-development-plan.md:289-297)
  개발계획은 required CI job 도입과 branch-protection 증거를 Phase 1 작업·종료조건으로 유지한다. 반면 계약은 이를 D0-A 전 선행조건으로 소비하며 4425-4464에서 현재 두 문서로는 착수 불가라고 스스로 인정한다. 계약 안의 verbatim 제안은 결속된 개발계획을 변경하지 않으며 plan_scope_digest는 미래 변경을 관측할 뿐 현재의 순환 의존성을 해소하지 않는다. 따라서 이는 회피는 아니지만 명백한 미해소 blocker다.
  Recommendation: 두 결속 문서가 실제로 같은 선행관계를 규정한 상태로 재결속·재심되기 전까지 레인 B와 D0-A를 차단하라.

Next steps:
- U-17 동일-path 비활성 리터럴 변이를 권위 소비자에 실행한다.
- T-82 ⑯ 무-edge_seq 양성과 g6 생략 음성 변이를 전체 U-16 소비자에 실행한다.
- grafts TOCTOU interleaving을 U-16/U-17 양쪽에서 재현해 차단 여부를 확인한다.
- 개발계획의 실제 결속 내용이 변경·재결속된 뒤 두 계획을 함께 재심한다.
```

### 구조화 JSON 원문 (`result review-mszmjz25-x6gnn4 --json` · `confidence` 포함 · verbatim)

```json
{
  "verdict": "needs-attention",
  "summary": "NO-SHIP. HEAD be0cbc95와 두 digest를 재계산해 제시값과 일치함을 확인했다. 직전 6건 판정: #1 F1 부분해소(5491-5536: 관측 가능한 off/on은 차단하지만 완전 강제 증명은 아님), #2 host 해소됨(5241-5269), #3 F2 해소됨(3548-3562), #4 F4 부분해소(⑱·전순서는 고쳤지만 T-82 ⑯과 U-16-a2에 stale 규범 잔존), #5 F5 해소됨—계약 수준(7030-7137), #6 미해소(개발계획 289-297 대 계약 4423-4464). 회피로 재분류할 항목은 없다. T-81 19/T-82 20/T-84 12, U-17-c 10값, U-16-d 12단의 종수는 일치하지만 의미 정합은 실패했다. addendum-8은 -7의 잘못된 후보집합 증명을 적절히 철회·대체하고 존재 증명으로 한정했으나 정적 픽스처일 뿐 아래 TOCTOU를 닫지 않는다. 7기준: (1) 단계·의존성 불충족—#6, (2) 숨은 가정 불충족—문자열 grep과 불변 git 메타데이터 가정, (3) 검증 가능성 불충족—해당 우회 변이 부재, (4) 실패·롤백 불충족—거짓 green에 대한 차단 신호 없음, (5) 범위 이탈·과잉설계 해당 없음, (6) CLAUDE.md 비협상 규칙 충돌 해당 없음, (7) 누락 불충족—현행 스키마·g6·계획 선행조건 전파 누락.",
  "findings": [
    {"severity": "high", "title": "U-17은 하니스 검증 실행이 아니라 비활성 문자열 두 개를 인증한다", "body": "5422-5431은 워크플로 blob에서 경로와 digest를 각각 grep한 뒤 이를 sha256 검증 스텝의 존재로 간주한다. 같은 경로의 워크플로가 두 문자열을 주석이나 미사용 값에 넣고 실제 job은 `true`만 실행해도 두 grep은 성공한다. 이 형태를 메모리 내 픽스처로 실행해 두 grep rc=0이면서 주석 밖 하니스 호출은 없음을 재현했다. run path, head SHA, Actions app, success 결속도 모두 충족할 수 있으므로 실제 동결 하니스를 실행하지 않은 gate가 PREVENTION_ACTIVE로 승인된다. 5356-5362의 GitHub 내부 실행 한계와 달리 이는 서버가 아니라 계약의 blob 판정 자체에서 발생한다.", "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md", "line_start": 5422, "line_end": 5431, "confidence": 0.99, "recommendation": "동일 path/app/head의 성공 워크플로에 두 리터럴을 비활성 위치로만 심은 변이가 권위 U-17 소비자와 T-84에서 차단된다는 증거가 생기기 전에는 출하하지 말라."},
    {"severity": "medium", "title": "F4는 부분해소다: T-82 ⑯이 폐지된 edge_seq 입력을 계속 요구한다", "body": "T-82 ⑯은 반복 이력의 두 승인 행에 `edge_seq` 1·2를 둔다고 여전히 지시한다. 같은 T-82 행의 ⑱과 현행 스키마(6821-6824)는 edge_seq 필드가 없고 소비자만 표시값을 파생한다고 규정한다. 따라서 ⑱만 고친 v2.19 증거는 전체 T-82 표면을 정합하게 만들지 못했다. ⑯을 문자대로 구현하면 존재하지 않는 필드를 다시 소비하거나 정상 반복 이력을 영구 차단하므로 S-22 재발이다.", "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md", "line_start": 2927, "line_end": 2927, "confidence": 0.99, "recommendation": "현행 무-edge_seq 스키마로 ⑯ 양성을 전체 U-16 소비자에서 실행하고, 폐지 필드를 요구하거나 판정에 소비하는 변형이 실패함을 입증할 때까지 F4를 해소로 세지 말라."},
    {"severity": "high", "title": "U-16-a2의 폐쇄 범위가 현행 g6를 제외한다", "body": "6758-6764는 모든 U-16-g 항을 요구하면서 이를 명시적으로 `g1~g5`로 한정한다. 바로 뒤 6766-6774는 번호 열거가 미래 규칙을 누락하므로 전 항을 자동 포섭해야 한다고 설명하지만, 현행 g6는 6928-6970에 실재하며 reviewer가 승인보다 선행했는지 강제한다. 다른 표면은 g6를 포함하므로 서로 다른 합리적 소비자가 상반된 계약을 구현할 수 있다. 닫힌 범위를 따르는 소비자는 R∥A를 승인해 APPROVAL_ORDER_INVALID를 우회할 수 있다.", "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md", "line_start": 6758, "line_end": 6774, "confidence": 0.99, "recommendation": "g6를 생략한 단일변이 소비자가 T-82 ⑮와 전체 U-16 판정에서 반드시 실패한다는 증거와 모든 규범 표면의 단일 해석이 확보되기 전에는 출하하지 말라."},
    {"severity": "high", "title": "PARENTS-UNTRUSTED의 graft 부재 관측과 조상성 소비 사이에 TOCTOU가 남는다", "body": "7059-7063의 ㉡은 replace/grafts 부재를 한 번 관측할 뿐, 이후 `%P`·`merge-base --is-ancestor` 소비와 같은 불변 스냅샷에 결속하지 않는다. 문서도 7104-7108에서 후보 우주 밖 graft가 ㉠을 피하고 `--no-replace-objects`로도 무력화되지 않아 ㉡이 유일한 완화라고 인정한다. 따라서 ㉡ 통과 후 후보 밖 graft를 설치하고 조상성 조회 뒤 제거하는 동시 프로세스는 구조 대조와 부재 검사를 모두 통과하면서 LATE/ORDER_INVALID를 ACTIVE/NO_ROWS_CLEAR로 뒤집을 수 있다. addendum-8은 정적 graft 존재 픽스처만 증명해 이 시간축을 검사하지 않는다.", "file": "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md", "line_start": 7059, "line_end": 7063, "confidence": 0.91, "recommendation": "㉡ 검사와 조상성 조회 사이에 graft를 삽입·제거하는 interleaving 변이가 전체 U-16/U-17 소비자에서 fail-closed임을 입증하기 전에는 부모 신뢰 계약을 통과시키지 말라."},
    {"severity": "medium", "title": "#6은 정직하게 기록됐지만 실제 계획 의존성은 여전히 미해소다", "body": "개발계획은 required CI job 도입과 branch-protection 증거를 Phase 1 작업·종료조건으로 유지한다. 반면 계약은 이를 D0-A 전 선행조건으로 소비하며 4425-4464에서 현재 두 문서로는 착수 불가라고 스스로 인정한다. 계약 안의 verbatim 제안은 결속된 개발계획을 변경하지 않으며 plan_scope_digest는 미래 변경을 관측할 뿐 현재의 순환 의존성을 해소하지 않는다. 따라서 이는 회피는 아니지만 명백한 미해소 blocker다.", "file": "docs/plans/2026-08-11-tos-completion-development-plan.md", "line_start": 289, "line_end": 297, "confidence": 1, "recommendation": "두 결속 문서가 실제로 같은 선행관계를 규정한 상태로 재결속·재심되기 전까지 레인 B와 D0-A를 차단하라."}
  ],
  "next_steps": [
    "U-17 동일-path 비활성 리터럴 변이를 권위 소비자에 실행한다.",
    "T-82 ⑯ 무-edge_seq 양성과 g6 생략 음성 변이를 전체 U-16 소비자에 실행한다.",
    "grafts TOCTOU interleaving을 U-16/U-17 양쪽에서 재현해 차단 여부를 확인한다.",
    "개발계획의 실제 결속 내용이 변경·재결속된 뒤 두 계획을 함께 재심한다."
  ]
}
```

> 포워더 전달: parseError null·target working-tree explicit·codex.status 0·write false·에러/재시도 0.
> Codex 가 두 문서를 `nl -ba`/`rg`/`git blame` 으로 직접 읽음(로그상 종수 대조·6758-6768 blame).

---

# 수용검사 (오케스트레이터) — **채택 5 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high (신규) | `:5422-5431` (b)③ «파일 텍스트가 두 리터럴을 포함(grep 2회) … 두 리터럴 grep 이므로 결정적» 리터럴 확인 — 검증 스텝 «존재»를 문자열 포함으로 간주. 주석/미사용 값에 두 문자열을 두고 job 은 `true` 인 워크플로가 통과함은 술어 형태에서 자명(Codex 픽스처 재현). 정직 경계 :5356-5362(«서버가 그 파일을 그대로 실행했다» 증명 불가)와는 다른 층 — blob 판정 자체의 결함 | 채택 |
| 2 | high (신규) | `:6760-6762` U-16-a2 «U-16-g 전 항(g1~g5) 과 U-16-h» 리터럴 확인 · `:6766-6774` S-6 «번호로 열거하지 않는다 … 전 항 전칭 … g 계열이 늘면 자동 포섭» 문단 확인 · g6 `:6928~` 실재(v2.13 신설) — 괄호 «(g1~g5)» 가 v2.13 g6 신설 시 미전파(S-22). 닫힌 열거 소비자는 g6 (reviewer ⊰ 승인) 을 빼고 R∥A 승인 가능 | 채택 |
| 3 | high (신규) | `:7059-7063` ㉡ «전역 관측(보조)» 1회 관측 리터럴 확인 · `:7104-7108` K-4 «㉡ 의 grafts 파생 부재 요구가 이 잔여를 저장소 전역으로 완화하나 닫지는 못한다» 자인 확인. ㉡ 관측 시점과 이후 `%P`/`merge-base --is-ancestor` 소비 사이 동일 스냅샷 결속 규정 없음 — 판정기 자신의 파일시스템에서 동시 프로세스가 grafts 를 삽입·제거하는 interleaving 이 계약 문언상 미검사. addendum-8 은 정적 픽스처(존재 증명)라 시간축 미검사 | 채택 |
| 4 | medium (F4 부분) | `:2927` T-82 ⑯ «두 간선 각각에 `edge_seq` 1·2 승인 행을 둔다» 리터럴 확인 vs `:6821-6824` 스키마 «`edge_seq` 없음» — v2.19 E4 가 ⑱만 재기술하고 같은 행의 ⑯ 은 미전파(S-22 재발·같은 셀 안) | 채택 |
| 5 | medium (#6 미해소) | 개발계획 `:289-290` 작업 7 required CI job·`:297` 종료조건 branch protection 증거 실재 · 계약 (D) `:4425-4430` «두 문서를 함께 실행하면 … 착수 가능하지 않다. 정확하다» 자인 확인. v2.19 는 개정안 verbatim 만 수록(개발계획 무편집) — 회피 아님·**운영자 게이트**(개발계획 개정 적용은 운영자 결정; 적용 시 bound_paths 편집 → 재동결·재결속) | 채택 (운영자 게이트) |

비협상 대조: 선물 대칭·실계좌 증거금·EOD 청산·ClickHouse·RL/TFT·하드코딩·Redis DB/TTL·비KST — 5건 어느 것도 배치 권고 아님.

## 관측 (finding 아님)

- **해소 3(host·F2·F5) = 아크 누적 8** — 구조 정의(c_APP 집합·D 참조)·명령형 host 결속이 인정. 회피 0.
- **S-22 재발 2**(#2 a2 «(g1~g5)»·#4 ⑯ edge_seq) — 둘 다 «같은 셀/절 안의 인접 항목»을 sweep 이 못 봄(⑱ 고치며 ⑯ 안 봄·g6 신설 시 a2 안 봄). 교훈: **같은 표 셀·같은 절의 형제 항목을 «전건 재독»**.
- #1 저작 경로: 두 리터럴 «존재» → 워크플로 YAML 을 **구조 파싱**해 `jobs.<gate job>.steps[]` 중 `run:` 스텝이 하니스 경로를 실행 인자로 포함하고 sha256 검증이 실행문(주석 아님)에 있는지 — 그래도 «서버가 그 스텝을 실행했다»는 (b) 정직 경계 유지(check-run 의 step 로그/annotation 은 API 로 조회 가능: `actions/jobs/{job_id}` steps[] name/conclusion — 스텝 «이름»을 계약 리터럴로 고정하면 실행 여부를 서버 잡 로그로 대조 가능). T-84 ⑬(비활성 리터럴 변이).
- #2 저작 경로: a2 괄호를 «U-16-g 전 항(현행 g1~g6 — 열거는 예시이며 규범은 전칭)» 또는 괄호 제거 + T-82 ⑮ 에 «g6 생략 소비자 실패» 대조 명시.
- #3 저작 경로: ㉡ 관측을 «조상성 조회 직전·직후 2회»(사전/사후 동일 요구 — 다르면 UNVERIFIABLE) + grafts 파일 내용 스냅샷 sha 대조 + 정직 경계(파일시스템 동시성은 판정기 밖 — 사후 관측은 «창을 좁힘»이지 «닫음»이 아님; 완전 폐쇄는 read-only 스냅샷(예: `git worktree`/`git bundle` 로 격리 복제 후 판정) 이 필요) — 극성 논증 후 선택. T-82/T-84 interleaving 변이(SIMULATED — 실행기 훅으로 조상성 조회 사이에 grafts 삽입).
- #4 저작 경로: ⑯ 을 현행 스키마(«두 간선 각각에 승인 행 — edge_seq 기재 없음·소비자 파생»)로 재기술 + 같은 셀 ⑮~⑳ 전건 재독.
- #5(#6): **운영자 게이트** — 개발계획 개정안 적용 여부. 적용 시 계약 (D) 의 verbatim diff 를 개발계획에 그대로 반영 → 두 문서 재동결 → 재결속 → 재심. 미적용이면 레인 B 는 이 축에서 영구 NOT_PASSED.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
