# verdict — 레인 B (계획 심판) · v2.11 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: 3a53edb6f3dce462dad5e25c009ce2c171b64f79
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 72cf902fe29a9c3e069d2fd1039569ef7ce7138beddf303d1fe28e387b475eac
reviewed_version: v2.11 (5,909행) — 매핑 확장 ac38a89a · 동결 e582c01a · 억제 증거 c9b6dc0d · 재결속 3a53edb6 이후 심사
findings: 3                        # high 2 / medium 1
prior_verdict: .omc/review/20260815-040451/verdict.md   # v2.10 재심 (NOT_PASSED)
mode: A (adversarial-review, --scope working-tree), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-mstmukl2-qtxlvo / codex session 01a002cd-7425-7162-bf15-57e86846ecd8
     # detached(nohup) 실행 · ~9분 정상 종료
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **불변**(HEAD·plan_scope_digest·
아티팩트 content digest `06cd99c1…` == 보유값). 문서 정지 확인. Codex 도
`ac38a89a → e582c01a → c9b6dc0d → 3a53edb6` 순서·EV-L0~L6 매핑 전역화를 독립 확인.

## 처분

**직전 2건: #1 부분해소 · #2 부분해소 — 양건 "문구만 아님" 명시.**
`CLAUDE.md` 비협상 직접 충돌 **없음**(7판 연속). 신규 3건:
① 가드가 억제한 것은 **대리 행위**(`touch D0A-STARTED`)이지 실제 D0-A 최초 행위가
아니며, 비가드 실제 착수는 여전히 차단되지 않는다 ② U-16-a2 전칭과 **U-16-c 의
단수 `c_NO` 본체가 병존** — 통과 상태(U-16-d)·§11 종료조건이 여전히 단수 계약을
소비해, 그 본체를 따르는 구현이 유리한 `c_NO` 를 고를 수 있다 ③ K-14 의 실패
조건에 대조군 부재 — T-48 은 문법-외 값만 주입하며, **문법상 유효하되 매핑에 없는
레벨**(EV-L7 류)은 별도 실패 축.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

NOT_PASSED. 직전 finding 1은 부분해소, finding 2도 부분해소다. 전자는 실제 양방향 `&&` 억제 실험을 추가했지만 대리 행위만 검증했고 비가드 실제 착수를 막지 않는다. 후자는 EDGES 전칭 절차와 T-82 ⑭를 추가했지만 통과 상태·종료조건에는 단수 `c_NO` 계약이 남았다. 현행 digest `06cd99c1…`와 아티팩트 값, `ac38a89a → e582c01a → c9b6dc0d → 3a53edb6` 순서, EV-L0~L6 매핑 전역화는 확인했다. 7항 판정: (1) needs-attention—U-15/U-16 소비 의존성 불완전, (2) needs-attention—가드 준수와 단수 계약 무시를 가정, (3) needs-attention—실제 D0-A 및 K-14 검증 공백, (4) 해당 없음—새로운 비가역 선행 단계나 롤백 결함 없음, (5) 해당 없음—중대한 범위 이탈 근거 없음, (6) 해당 없음—CLAUDE.md:21-36,85-87,104-105의 비협상 규칙과 직접 충돌 없음, (7) needs-attention—실제 착수 소비자와 미매핑 레벨 대조군 누락.

Findings:
- [high] 직전 finding 1 — 부분해소: 실제 D0-A 착수 우회는 여전히 차단되지 않는다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4608-4610)
  U-15-f는 다른 착수 형식을 "기계로 막지 않는다"고 명시한다. 따라서 호출자가 하니스를 생략하거나 `&&` 밖에서 실제 D0-A 최초 행위를 실행하면 차단 상태에서도 구현이 시작될 수 있다. §12.3.4-G와 제출 transcript가 증명한 것은 `touch D0A-STARTED`라는 "착수 대리 행위"의 억제·도달뿐이다(U15-ENTRY-CHECK.md:360-364). 이는 단순 문구 변경은 아니지만, 직전 finding의 핵심인 실제 소비자 결속은 해결하지 못한다. 실패는 transcript 부재로 사후 노출될 뿐이고, stale 승인 아래 이미 발생한 D0-A 변경을 예방하지 못한다.
  Recommendation: 실제 D0-A 최초 실행 표면에서 하니스 생략·비가드 호출 자체가 거부되고 그 정확한 경로의 억제 증거가 확인될 때까지 이 finding을 해소로 계수하지 않는다.
- [high] 직전 finding 2 — 부분해소: 전칭 EDGES와 단수 c_NO 본체가 동시에 규범화되어 있다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5729-5739)
  U-16-a2는 모든 →NO 간선을 전칭 판정하고 T-82 ⑭도 단수 선택 구현을 실패시키도록 구체화했으므로 문구만 바뀐 것은 아니다. 그러나 뒤의 "이 계약의 본체" U-16-c는 다시 단수 `c_NO(r)`를 정의하고, U-16-d의 유일 통과 상태도 "모든 r이 U-16-c 충족"으로 규정한다. §11 종료조건도 같은 단수 표현을 유지한다(3311행). 구현자가 이 본체와 상태 정의를 따르면 merge `M`을 유리한 `c_NO`로 골라 `NO_ROWS_CLEAR`를 만들 수 있어, 새 전칭 규칙 및 T-82와 상충한다. 결과적으로 무승인 브랜치의 NO 전이가 merge에서 승인된 것처럼 통과할 수 있다.
  Recommendation: 통과 상태와 §11 종료조건이 EDGES(r) 전칭 결과만 소비하고 T-82 ⑭가 그 실제 소비자를 실패시키는 증거가 확인되기 전에는 직전 finding 2를 해소로 판정하지 않는다.
- [medium] K-14의 새 실패 조건이 실제 대조군으로 구체화되지 않았다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:2821)
  K-14는 승인 매핑 도메인 밖 레벨을 차단하고 T-48의 우주에 매핑 도메인을 추가했다고 선언한다(1492-1497행). 하지만 실제 T-48 절차는 여전히 단지 "문법 밖 값" 주입만 명시한다. `EV-L7`처럼 정규화 문법으로는 파싱되지만 승인 매핑에 없는 값은 별도 실패 축이다. 구현이 malformed 값만 거부하고 미매핑 정수를 빈 floor나 기본값으로 접어도 현행 T-48 문언을 통과할 수 있으며, 그 경우 evidence 쌍이 축소되어 완료 판정이 fail-open 된다. 따라서 EV-L6 현재 매핑은 해소됐어도 재발 방지 검증은 문장 수준에 머문다.
  Recommendation: 문법상 유효하지만 승인 매핑에 없는 레벨이 `--check`를 실제로 실패시키는 대조군 증거가 없으면 K-14를 검증 완료로 계수하지 않는다.

Next steps:
- 레인 B 판정과 P-0/D0-A 착수를 차단 상태로 유지한다.
- 재심 범위는 실제 D0-A 소비자 결속, U-16 전칭 결과의 종료조건 소비, K-14 미매핑 레벨 대조군 증거로 한정한다.

Codex session ID: 01a002cd-7425-7162-bf15-57e86846ecd8
Resume in Codex: codex resume 01a002cd-7425-7162-bf15-57e86846ecd8
```

---

# 수용검사 (오케스트레이터) — **채택 3 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high | `:4608-4610` 실재 — U-15-f-2 가 "기계로 막지 않으나 기록 부재로 드러난다" 자인. 증거의 우변이 `touch`(대리 행위)였음도 사실 | 채택 |
| 2 | high | `:5729-5739` 실재 — U-16-c 가 단수 `c_NO(r)` 을 "이 계약의 본체"로 유지, U-16-d 통과 상태 = "모든 r 이 U-16-c 충족", §11 `:3311` 동일 단수 서술. a2 전칭과 병존 확인 | 채택 |
| 3 | medium | `:2821` 실재 — T-48 절차가 "문법 밖 값 주입"만 명시. 문법-유효·미매핑 레벨 변이 부재 확인 | 채택 |

## 관측 (finding 아님)

- 수렴: 6→3→3→2→2→3(medium 1 포함— 신규 축이 아니라 K-14 의 대조군 구체화 요구).
  해소 누적 2 유지, 새 결함 클래스 0, 비협상 충돌 0 **7판 연속**, "문구만" 0 유지.
- #2 는 **전칭 신설이 구 본체를 대체하지 않고 병존시킨** S-9/S-20 계열의 의미 판 —
  a2 를 만들며 c 를 재작성하지 않았다. 해소 경로 명확(본체·상태·§11 을 EDGES
  전칭 소비로 통일).
- #1 의 잔여는 구조적 한계의 정면 — "실제 D0-A 최초 행위"가 계약에 **명명**되지
  않아 대리 행위 증거가 됐다. 해소 방향: D0-A 최초 행위를 계약으로 명명(§12.1
  D0-A 산출 목록의 첫 항 생성)하고 §12.3.4-G 증거의 우변을 그 실제 행위로 교체.
- #3 은 T-48 확장 + K-14 소비 결속(검사기 이전에는 절차·대조군 저작까지).

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
