# verdict — 레인 B (계획 심판) · v2.10 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: ed5ce7ee4e1acb37cbd2b095deb11eb40bb38e67
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: eccf1a8887a9ec81fedfb1acc5c0c0c623a5ac09695217c17bc2cfd820dc5b5a
reviewed_version: v2.10 (5,674행) — 동결 4fb03470 · 증거 2f88f49b · 6e⁗ 재결속 ed5ce7ee 이후 심사
findings: 2                        # high 2
prior_verdict: .omc/review/20260814-160239/verdict.md   # v2.8 재심 (v2.9는 동결 직후 stop-time 적발로 심사 미도달)
mode: A (adversarial-review, --scope working-tree), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-mstbjny1-g7ld72   # detached(nohup) 실행 · 8m 3s 정상 종료
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **3값 전부 불변**(HEAD·plan_scope_digest·
아티팩트 content digest `b0edb769…` == 보유값). 문서 정지 확인.

## 처분

**직전 2건: U-15 부분해소 · U-16 해소됨(아크 두 번째 해소 — 시점 blob 결속·행 불변성·
T-82 ⑫⑬을 "실제 검증 절차"로 인정).** "문구만" 0건. `CLAUDE.md` 비협상 직접 충돌 **없음**.
신규 2건 = ① U-15 잔여: 하니스는 거부하지만 **실제 D0-A 착수를 억제하는 소비자에
미결속**(transcript 생략 경로 — 문서 자신이 :4741 에서 자인) ② U-16 신규 잔여:
`c_NO`/`c_APP` 파생이 **merge DAG 에서 비유일** — U-12 가 경계 집합·유일화로 이미 푼
클래스의 U-16 판이며 T-82 에 대응 위상 변이가 없다.

## Codex 출력 (verbatim — JSON)

```json
{"verdict":"needs-attention","summary":"출하 불가. 직전 U-15 finding은 부분해소(문구만 변경된 것은 아님): 실행 가능한 상태 판정과 비정상 종료는 추가됐지만 실제 D0-A 진입 결속은 증명되지 않았다. 직전 U-16 historical-blob finding은 해소됨: 시점 blob 소비, 승인 행 불변성, T-82 ⑫·⑬이 실제 검증 절차로 추가됐다. 다만 별도의 merge-DAG 모호성이 남는다. 커밋 순서와 b0edb769… digest 재결속은 확인했다. 1) 단계 순서·의존성: 불충족—U-15 선행 검사를 건너뛴 D0-A 착수가 가능하며 U-16 전이 커밋 선택이 비유일하다. 2) 숨은 가정: 불충족—오케스트레이터가 항상 하니스 rc를 소비하고, c_APP/c_NO가 DAG에서 유일하다고 가정한다. 3) 검증 가능성: 불충족—하니스 거부는 검증됐지만 실제 착수 억제와 U-16 2-parent 위상은 검증되지 않았다. 4) 실패·롤백: 해당 없음—단계별 역순 revert와 durable-state 주의가 명시돼 있다. 5) 범위 이탈·과잉 설계: 해당 없음. 6) CLAUDE.md 비협상 충돌: 해당 없음—설정, Redis, KST, 주식 EOD, 선물 대칭·REAL 주문, RL/TFT, ClickHouse 규칙과의 직접 충돌을 찾지 못했다. 7) 누락: 있음—실제 진입 소비자 거부 증거와 U-16 merge-DAG 대조군이 누락됐다.","findings":[{"severity":"high","title":"U-15 하니스는 비정상 종료하지만 실제 D0-A 착수를 차단하는 소비자에 결속되지 않는다","body":"직전 U-15 finding은 부분해소다. 하니스가 상태를 프로그램으로 산출하고 ENTRY_OK 외에는 비정상 종료하며, Run D도 미커밋 위조를 FREEZE_VIOLATED/rc=1로 검출했다. 그러나 계획은 1단이 절차 규율일 뿐 transcript 없이 진입하는 경로를 막지 못한다고 직접 인정한다(docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4741-4749). '실제 진입 명령' 검증으로 제시된 T-81도 `bash recipe.sh`만 실행할 뿐 D0-A 착수 명령이나 작업 억제를 실행하지 않는다(:4523-4545). transcript 역시 하니스 rc만 기록한다(U15-ENTRY-CHECK.md:149-155,400-405). 따라서 이 증거는 검출기의 판정과 종료 코드를 증명하지만, 하니스를 생략하거나 rc를 무시했을 때 stale·미승인 상태로 D0-A가 시작되지 않는다는 핵심 의존성은 증명하지 못한다.","file":"docs/plans/2026-08-12-tos-phase0-completion-contract-design.md","line_start":4741,"line_end":4749,"confidence":0.99,"recommendation":"실제 pre-D0-A 착수 표면에서 하니스 비정상 종료 또는 transcript 부재 시 D0-A 작업이 실행되지 않는 결과가 나오기 전까지 직전 U-15 finding과 Lane B를 통과로 계산하지 않는다."},{"severity":"high","title":"U-16의 c_NO·c_APP 파생은 merge DAG에서 비유일해 승인 순서를 유리한 커밋으로 판정할 수 있다","body":"직전 reviewer historical-blob 우회 자체는 해소됐다: g3/h가 `approved_at_head`의 본문을 소비하고 g5와 T-82 ⑫·⑬이 reviewer·원장 사후변조를 검사한다(:5471-5510,5539-5543). 하지만 U-16-a는 모든 `→ NO` 간선을 대상으로 선언하면서도 각 행의 `c_NO(r)`을 단수로 파생할 뿐 후보가 여러 개인 merge DAG의 선택 규칙이나 모호성 차단을 정의하지 않는다(:5439-5442). 예를 들어 G(YES)에서 X가 승인 없이 NO로 바꾸고, 다른 브랜치에서 승인 행 A를 만든 뒤 M에서 합치면 X와 M의 YES 부모 간선 모두 `→ NO` 후보가 된다. A는 M의 조상이지만 X의 조상은 아니므로 M을 고르면 통과하고 X를 고르면 차단된다. 동일한 모호성은 승인 행의 병렬 도입에도 생긴다. 이 문서는 U-12에서 바로 이 merge-DAG 문제를 경계 집합·유일화와 T-78 2-parent 변이로 처리했다(:3705-3741,3900-3903), 반면 T-82 13종에는 대응 위상이 없다(:2812). 구현이 유리한 후보를 고르면 선승인되지 않은 NO 변경이 `NO_ROWS_CLEAR`로 오판되어 Phase 0 의무를 약화시킬 수 있다.","file":"docs/plans/2026-08-12-tos-phase0-completion-contract-design.md","line_start":5439,"line_end":5442,"confidence":0.94,"recommendation":"다중 c_NO/c_APP 후보가 있는 모든-parent merge 위상에서 판정이 유일하거나 fail-closed임을 정의하고, 승인 없는 브랜치 전이가 merge 후 통과하지 못하는 2-parent T-82 실행 증거가 나오기 전까지 U-16을 완료 계약으로 인정하지 않는다."}],"next_steps":["Lane B와 P-0/D0 착수를 NOT_PASSED로 유지한다.","실제 D0-A 착수 억제와 U-16 2-parent merge 위상에 대한 독립 실행 증거만 재심한다."]}
```

---

# 수용검사 (오케스트레이터) — **채택 2 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high | `:4741-4749` 실재 — "transcript 를 만들지 않고 진입하는 경로는 … **막지는 못한다**" 문서 자인. T-81(:4523-4545)은 하니스만 실행하고 착수 명령·작업 억제를 실행하지 않음 확인 | 채택 |
| 2 | high | `:5439-5442` 실재 — `c_NO(r)` 단수 파생·merge 선택 규칙 부재. `:2812` T-82 13종에 "2-parent/위상" 무출력(대응 변이 부재) 확인. U-12 의 동일 클래스 해법(:3705-3741) 실재 | 채택 |

## 관측 (finding 아님)

- **해소 2번째**: 직전 U-16 시점-blob 결함 "해소됨" — 시점 blob 소비·행 불변성·⑫⑬을
  "실제 검증 절차"로 심판이 인정. 수렴: 6→3→3→2→2, 해소 누적 2(U-12 merge-DAG·
  U-16 시점 blob), 새 결함 클래스 0, 비협상 충돌 0 **6판 연속**.
- 신규 2건의 공통 방향: **"계약·검출기를 실제 실행 표면에 결속하라"** — #1 은 착수
  표면(가드된 착수 명령 계약 + 억제 실행 증거가 저작 가능), #2 는 U-12 해법의
  U-16 이식(경계 집합·유일화 또는 다중 후보 fail-closed + T-82 위상 변이).
- **인접 미결(레인 밖 stop-time 적발, 실측 확정)**: OQ-11 승인 매핑이 `VER-002-001`
  §5 가 정의하는 **EV-L6**(:164, Continuous Production Conformance)을 누락 —
  인용 도출 범위(:136-179) 안의 레벨이다. 완화: 레지스터 사용 0건(잠재)·T-76 이
  값 우주를 앵커. 처분 분할: 계획의 매핑-부재 레벨 fail-closed 규칙 + 한계 등재는
  저작 가능 / **매핑표 확장 또는 승인 도메인 명시 한정은 운영자 게이트**(매핑
  내용은 ①②③ 무변경 불변식이 지켜온 운영자 승인 해석). 다음 개정 입력.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
