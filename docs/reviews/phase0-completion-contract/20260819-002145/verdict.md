# verdict — 레인 B (계획 심판) · v2.14 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: 79d9cb07cb58adf672c23c387cabbff6ee2c687e
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 69d6076f3aac009c4e8bfcf8b3caaa82dda7e3dadf642728cc269c708f30dc78
reviewed_version: v2.14 (6,464행) — 동결 db19a0e8 · 증거 c5359c74 · 에라타 재동결 e9cc3ba4 · 재결속 79d9cb07
findings: 5                        # high 3 / medium 2 — 직전 #1 부분해소 · #2 부분해소 · #3 회피 · 신규 2
prior_verdict: .omc/review/20260818-224729/verdict.md   # v2.13 재심
mode: A (adversarial-review, --scope working-tree, --wait), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-msytcti6-6zu3mz / codex thread 01a01579-6bc4-7f00-bca0-395563617524
     # 1회 디스패치 정상 완료(7m 38s) — 재시도 불요
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **불변**(HEAD·plan_scope_digest·
내용-only digest `99118a90…` == 아티팩트 보유값 `OQ-11-DISPOSITION.md:10`). Codex 도
결속 일치와 `db19a0e8→c5359c74→e9cc3ba4→79d9cb07` 순서를 독립 확인.

## 처분

**직전 3건: #1 부분해소 · #2 부분해소 · #3 회피** — 신규 해소 0(아크 누적 4 유지).
`CLAUDE.md` 비협상 직접 충돌 **없음**(10판 연속). **아크 최초 "회피" 판정 1건**(#3):
supersedes 재부여 행 Z1/Z2 는 머지 후 도입이라 **U-16-c 조상성**(c_APP ⊰ 간선 커밋)에서
`APPROVAL_AFTER` — 손 실행 부속이 tombstone-graph 만 실행하고 조상성 소비를 제외한
채 양성을 주장했다(부분 표면 축소). 신규 2건: 복수 D0A-FIRST 도입(merge-DAG)에서
U-15-g-1 "있으면 1건" 가정 붕괴(high) · `row_ref` 의 c_APP 가 병렬 다중 도입에서
단수 아님(medium). #1 은 정직 경계 자체를 "과장 철회일 뿐 해소 아님"으로 계수 —
그리고 **처분표 :4256-4267 이 마감 전 초안 문구("닫고"·"전칭"·"증거 없음")를
그대로 들고 있어 문서 내부 주장이 갈린다**(S-22 미전파 실재). #2 는 digest
**선배치** 변종(H0 빈 운반자에 digest → B 에서 실제 내용 작성·digest 유지 ∥ A
승인 → M): C_R 이 digest 토큰 도입만 추적해 `C_R={H0}` ⊰ A 통과.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

출하 불가. HEAD `79d9cb07`, plan_scope_digest `69d6076f…`, bound_set_digest `99118a90…` 및 커밋 순서는 일치하고 CLAUDE.md 비협상 직접 충돌은 없다. 그러나 직전 판정은 #1 부분해소, #2 부분해소, #3 회피로 판단된다. CORR은 여전히 거짓 green을 허용하고, C_R은 digest 운반자를 실제 리뷰 내용으로 오인하며, 병렬 원장 복구는 전체 U-16 순서 계약에서 불가능하다. 추가로 복수 D0A-FIRST 및 복수 row 도입에 대한 결정성도 빠져 있다.

Findings:
- [high] 직전 #1 — 부분해소: 정직 경계는 사후 세탁을 인정하지만 Phase 0 green을 계속 허용한다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4838-4875)
  문서는 비가드 `d`를 만든 뒤 `parent(d)`에서 하니스를 재실행하고 amend로 트레일러를 붙이면 네 CORR 조건과 `ENTRY_PROVENANCE_CLEAR`/rc=0이 모두 성립한다고 직접 입증한다. 그럼에도 §11은 CLEAR를 완료 허용값으로 소비하고(:3371), 예방은 Phase 1의 UNCHK-008로 미룬다(:4872-4875, :5377). 상위 계획도 required branch-protection 증거를 Phase 1 종료조건에 둔다(`2026-08-11-tos-completion-development-plan.md:275-298`). 따라서 보호 장치보다 먼저 실행되는 Phase 0 진입을 사후 세탁해 정상 완료로 표시할 수 있다. 한계를 정직하게 적은 것은 과장 철회일 뿐 기존 위험의 해소가 아니며, 앞선 처분표는 여전히 두 축을 '닫았다'고 적어(:4256-4267) 문서 내부 주장도 갈린다.
  Recommendation: #1을 부분해소로 유지하고, 서버측 예방 통제가 최초 D0A-FIRST보다 먼저 활성화됐다는 증거 없이는 P-0/D0-A 착수를 허용하지 않는다.
- [high] 신규: 복수 D0A-FIRST 도입에서는 7값 판정이 전순서가 아니며 비가드 커밋을 무시할 수 있다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4791-4793)
  U-15-g-1은 `git log --diff-filter=A` 결과를 판정 우주로 삼으면서 곧바로 도입 커밋이 '있으면 1건'이라고 가정한다. 그러나 두 브랜치가 config를 독립 추가한 뒤 merge하면 도입 커밋은 둘이다. 정의에는 이 cardinality를 차단하는 상태나 모든 `d`를 평가하는 양화가 없다. 따라서 guarded `d1`과 unguarded `d2`가 함께 존재할 때 구현이 임의의 한 커밋만 선택해 CLEAR를 내고 다른 도입을 누락할 수 있다. 이는 diligent amend 경계와 달리 저장소 안에서 검출 가능한 입력이며, 현재 7값/6단 우선순위가 모든 입력에 결정적이라는 주장도 깨진다.
  Recommendation: 복수 도입 merge-DAG가 실제 소비자에서 명시적으로 차단되는 실행 증거가 나오기 전까지 U-15의 전순서·유일 성공 주장을 인정하지 않는다.
- [high] 직전 #2 — 부분해소: C_R은 digest 토큰의 도입만 추적해 실제 리뷰 변경을 다시 놓친다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:6174-6215)
  구조 정의는 reviewer blob 전체가 아니라 `row_content_digest` 리터럴의 존재 전이만 C_R에 넣고, 하나의 도입점만 c_APP의 조상이면 충분하다고 한다. H0에서 digest를 담은 빈/미완성 리뷰 운반자를 먼저 만들고, H0에서 갈라진 B에서 실제 리뷰 내용을 작성하되 같은 digest를 유지하며, 형제 A에 `approved_at_head=B` 승인 행을 만든 뒤 M에서 merge할 수 있다. B의 부모 H0에도 digest가 있으므로 B는 C_R 원소가 아니고 `C_R={H0}`; H0는 A의 조상이어서 g6가 통과한다. 동시에 g3와 h는 B가 M의 조상이고 B blob에 digest가 있으므로 통과하지만 실제 리뷰 내용 B는 A의 조상이 아니다. 문서가 digest 보유 지점을 곧 '리뷰 내용'이라고 동일시하는 설명은 이 차이를 숨긴다.
  Recommendation: #2를 부분해소로 유지하고, digest 선배치 후 reviewer 내용만 B에서 변경하는 H0→B∥A→M 변이가 실제 소비자에서 `APPROVAL_ORDER_INVALID`가 되기 전에는 통과시키지 않는다.
- [medium] 직전 #3 — 회피: 머지 후 재부여 행은 이미 발생한 간선의 승인 행이 될 수 없다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:6097-6103)
  복구 예시는 merge 뒤 Z1/Z2를 append하고 이를 LEDGER_EFF의 유효 승인 행으로 삼아 NO_ROWS_CLEAR를 주장한다. 그러나 변경되지 않은 U-16-c는 각 간선을 덮는 승인 행의 `c_APP`가 해당 `→NO` 커밋의 진조상이어야 하며(:6246-6253), 조상이 아니면 `APPROVAL_AFTER`로 차단한다(:6260-6263). 머지 후 도입되는 Z1/Z2는 과거 간선의 조상이 될 수 없으므로 전체 계약에서는 green이 불가능하다. 제시된 손 실행기는 tombstone graph만 실행하고 이 조상성 소비를 제외했기 때문에, 양성 대조군을 부분 표면으로 축소해 통과시킨 것이다. 정상 병렬 작업의 영구 차단이라는 직전 실패·롤백 결함이 그대로 남는다.
  Recommendation: #3을 회피로 판정하고, U-16-c의 조상성까지 포함한 전체 실제 소비자가 동일 픽스처에서 NO_ROWS_CLEAR를 방출하기 전까지 복구 가능 주장을 인정하지 않는다.
- [medium] 신규: row_ref의 c_APP가 merge-DAG에서 단수가 아닐 수 있어 LEDGER_EFF가 결정되지 않는다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:6063-6079)
  row_ref는 `(c_APP(row), row_digest(row))`로 정의되지만, 동일한 정규형 행이 두 형제 브랜치에서 독립 도입되고 merge 해소가 한 줄만 보존하면 그 현재 행에는 도입 지점이 둘이다. C_R은 바로 이 상황 때문에 집합으로 정의됐지만 row_ref는 singular c_APP 선택 규칙이나 다중 도입 차단을 두지 않는다. H5-②는 같은 c_APP 안의 중복만 막으므로 적용되지 않는다. 구현이 어느 도입점을 고르느냐에 따라 supersedes 참조가 실재 행을 가리키거나 부재 행이 되어 LEDGER_EFF와 MALFORMED 판정이 달라질 수 있다.
  Recommendation: 동일 행의 병렬 다중 도입을 포함한 변이에서 row_ref와 상태가 단일하게 파생되거나 명시적으로 차단됨을 실제 소비자로 증명하기 전까지 LEDGER_EFF 결정성 주장을 보류한다.

Next steps:
- 레인 B를 NOT_PASSED로 유지하고 P-0/D0-A 착수를 차단한다.
- 재심 증거는 손 실행기의 부분 판정이 아니라 실제 status 소비자에서 복수 D0A-FIRST, digest 선배치 B∥A, 전체 U-16 병렬 복구, 동일 행 다중 도입을 실행해야 한다.
- 두 계획 문서가 변경되면 현재 plan_scope_digest를 무효화하고 새 리비전에 결속해 재심한다.
```

---

# 수용검사 (오케스트레이터) — **채택 5 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high | `:4838-4875` 정직 경계 절 실재. `:3371` §11 이 CLEAR 를 비차단으로 소비 확인. `:5377` UNCHK-008 = Phase 1·저장소 밖 강제 표면 확인. 개발계획 `:275-298` Phase 1 종료조건에 branch protection 증거 확인. **`:4256-4267` 처분표(B) 가 마감 전 초안 문구 유지** — "두 미검사 축을 한 트레일러 조건으로 동시에 닫고"·"모든 원소가 c_APP 진 조상(전칭)"·"실행 증거 없음(미실행)" — 마감(G1 철회·∃ 전환)·증거 `c5359c74`·에라타 재동결 어느 단계에서도 미전파(S-22 클래스, 실재) | 채택 |
| 2 | high (신규) | `:4791-4793` U-15-g-1 "있으면 1건, 없으면 ∅" 리터럴 실재 — 복수 도입 카디널리티 상태·양화 부재 확인. 검증자 픽스처(scratchpad/A)도 단일 d 만 다룸 | 채택 |
| 3 | high | `:6174-6180` C_R = digest 리터럴 존재 전이 정의 확인. 선배치 변종(H0 에 digest 운반자 → B 내용 변경·digest 유지 ∥ A → M): B 부모 H0 에 digest 있으므로 B ∉ C_R, C_R={H0} ⊰ A → g6 통과, h(`git show B:` 에 digest) 통과 — 검산 일치. **U-16-h 가 approved_at_head 시점 blob 을 고정하므로 C_R 은 «그 blob 의 도입 지점»으로 정의돼야 함**이 자연스러운 교정 경로 | 채택 |
| 4 | medium (회피) | `:6097-6103` 복구 예시 실재. `:6246-6253` U-16-c c_APP(a) ⊰ 간선 커밋 요구·`:6260-6263` APPROVAL_AFTER 실재. Z1/Z2 는 머지 후 도입 → 과거 간선 e_a/e_b 커밋의 조상 불가 → APPROVAL_AFTER. 손 실행 부속(`U16-LEDGER-CHECK.md`)은 tombstone-graph 만 실행·조상성 미소비 확인. "회피" 판정 근거 정당 — 부분 표면 양성으로 전체 계약 green 을 주장 | 채택 |
| 5 | medium (신규) | `:6063-6079` row_ref=(c_APP(행), row_digest) 정의 실재. 동일 정규형 행의 병렬 독립 도입 + 머지 한 줄 보존 시 c_APP 비단수 — C_R 은 집합인데 row_ref 는 단수 선택 규칙 부재 확인. H5-② 는 같은 c_APP 내 중복만 | 채택 |

## 관측 (finding 아님)

- **판정 성격**: 아크 최초 "회피" 1건 — 손 실행 부속이 계약의 **일부 규칙만** 실행하고
  양성을 주장한 것이 원인. 교훈: **부분 표면 실행기의 green 은 전체 계약의 green 이
  아니다** — 실행기는 그 상태값을 산출하는 **모든 소비 규칙**을 실행하거나, 실행하지
  않은 규칙을 명시하고 green 을 주장하지 말아야 한다.
- **S-22 7회차**: 처분표(B) `:4256-4267` — 마감 재작성 후 "저작 요약" 표면 미전파.
  검증자 2라운드·저작자 자가검증·증거 실행 어느 것도 이 표를 안 읽었다(§0/§8/§11
  만 sweep). **sweep 대상에 "개정 처분표"를 명시 추가**해야 한다.
- #1 저작 경로: 정직 경계는 유지하되 (a) 처분표 정합 (b) **UNCHK-008 을 Phase 1 이
  아니라 D0-A 착수의 선행 조건**으로 승격하는 선택지(§12.3 P-0 재진입 계약에
  "서버측 required check 활성 증거"를 착수 전제로 — Codex Recommendation 이 그
  방향) — 운영자/저작자 판단.
- 신규 high 저작 경로: U-15-g-1 판정 우주 = 도입 커밋 **집합** D; |D|=0 → NOT_STARTED
  · |D|>1 → 신규 차단값(예: `MULTIPLE_INTRODUCTIONS`) 또는 ∀d 평가 후 최악값 —
  전순서에 편입 + T-81 ⑲ 병렬 도입 머지 변이.
- #2 저작 경로: C_R 을 digest 토큰이 아니라 **approved_at_head 시점 blob 의 도입
  지점** 으로 — `C_R(c) = { x ⊑ c : blob(x:ref) == blob(approved_at_head:ref) ∧ ∀p:
  blob(p:ref) ≠ 그 blob }` (h 와 정합·선배치 변종 red) + T-82 ⑲.
- #3 저작 경로: 재부여 행의 조상성은 **원 승인 행의 c_APP 를 승계**(supersede 체인의
  최초 c_APP 로 U-16-c 판정) 또는 병렬 충돌을 U-12 전순서로 소비자가 결정적
  재번호(append 없음) — 후자면 supersedes 자체가 불필요해짐. 전체 규칙 실행 필수.
- 신규 medium: row_ref 의 c_APP 를 집합으로 정의하고 |c_APP|>1 → MALFORMED
  (병렬 동일 행 도입 금지) 또는 row_ref = row_digest 단독 + 동일 digest 다중 도입
  MALFORMED.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
