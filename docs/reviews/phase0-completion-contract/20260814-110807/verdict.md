# verdict — 레인 B (계획 심판) · v2.7 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: 5bd097d791c8d52069c66fdb10c81801a9590eb8
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: e270f98707e11deeb2aacf6f07fe32b996d1d3d57edb49b070f84c5ccd89f964
reviewed_version: v2.7 (4,916행) — 동결 c645f7c6 · 6e″ 재결속 5bd097d7 이후 심사
findings: 3                        # high 3
prior_verdict: .omc/review/20260813-233530/verdict.md   # v2.6 재심 (NOT_PASSED)
mode: A (adversarial-review, --scope working-tree), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: thread 019ffe09-33ec-79c3-8b45-255ca80fc64a / turn 019ffe09-3537-7682-9631-e1798782e109
     # registry job-id 미발급(status --all → jobs: 0) — detached(nohup) 실행, pid 정상 종료 455s
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **3값 전부 불변**(HEAD·plan_scope_digest·
아티팩트 content digest `ac515d85…`). 두 문서 diff 없음 — 심사 중 문서 정지 확인.
Codex 도 동결→재결속 순서·digest 일치를 독립 확인했다.

**포워더 고지**: 심사 대상 2건이 커밋돼 working-tree diff 에 없으므로, "변경 없음"
종결을 막기 위해 두 경로를 직접 읽으라는 **범위 안내 문단만** focus 앞에 덧붙였다
(심사 기준 무변경). 직전 재심의 좀비 잡 함정은 detached 실행으로 회피됐다.

## 처분

**직전 3건: #1 부분해소 · #2 부분해소 · #3 부분해소 — 전건 "문구-only 아님" 명시,
전건 잔여 우회 지목.** `CLAUDE.md` 비협상 규칙 직접 충돌 **없음**(설정/Redis/KST/EOD/
선물 대칭·실주문/RL·TFT/ClickHouse 전 조항 대조). 신규 high 3건 = 잔여 우회 3종:
부트스트랩 순환 · merge DAG 비유일성 · 승인-내용 미결속.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

NO-SHIP. 동결 c645f7c6 → 재결속 5bd097d7 순서, 두 문서의 정지 상태, digest ac515d85… 일치는 확인됐다. 직전 findings 처분: #1 부분해소—7b·7c/U-15/T-81/O-6은 추가됐지만 진입 소비자가 순환한다. #2 부분해소—min 3항·trigger_at_head 소비·T-78 ⑥·⑦은 실제 검증 절차라 문구-only는 아니지만 merge DAG에서 트리거가 결정되지 않는다. #3 부분해소—Phase 0 차단/U-16/T-82는 실재하지만 승인 내용이 전이에 결속되지 않아 2커밋 우회가 남는다. 7항목: ① needs-attention(부트스트랩 순환), ② needs-attention(git DAG와 UNCHK-023 신뢰 가정), ③ needs-attention(사전 소비자 및 승인 결속 증명 부재), ④ 해당 없음—커밋별 역순 rollback이 명시됨, ⑤ 해당 없음, ⑥ 해당 없음—CLAUDE.md:21-36·85-105의 설정/Redis/KST/EOD/선물 대칭·실주문/RL·TFT/ClickHouse 규칙과 직접 충돌 없음, ⑦ needs-attention(merge topology와 stale·무관 승인 변이 누락). 현재 tos_spec_status PASS는 이 계획 결함을 해소하지 않는다.

Findings:
- [high] D0-A 진입을 막아야 할 U-15 소비자가 D0-A 안에서야 생성된다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4048-4074)
  D0-A가 검사기와 강제 지점을 생성하는 단계다(:3199-3229). 그런데 단계 8은 D0-A에 들어가기 전에 U-15-c를 기계 평가하도록 요구하고(:3427), U-15의 유일한 강제 지점은 바로 그 미생성 `tools/tos_completion_status.py --check`다. 문서도 현재 검사기 부재를 인정한다. 따라서 P-0 후 재결속·재심을 마쳐도 실제 진입 명령을 차단할 실행 표면이 없으며, T-81 역시 D0-A를 시작하기 전에는 실행할 수 없다. `검사기 부재 = red`라는 산문은 호출 주체가 없어서 직전 finding의 stale 승인 진입 변이를 실제로 막지 못한다.
  Recommendation: D0-A 착수 전에 이미 실행 가능한 독립 진입 소비자를 특정하고, 그 실제 진입 명령이 P-0 이후의 이전 승인을 거부한다는 T-81 증거를 요구하라.
- [high] U-12의 최초 True 커밋 파생은 merge DAG에서 단일값이 아니다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3631-3638)
  계획은 HEAD에서 '조상 방향으로 내려가며 처음 False가 되는 커밋의 자식'을 trigger_commit으로 삼지만 parent 선택, first-parent 규칙, 모든 부모 결합 규칙을 정의하지 않는다. 이 저장소에는 실제 merge commit이 다수 존재한다. 한 merge의 한 부모가 False이고 다른 부모가 이미 True이면 '처음 False의 자식'과 True-run의 최초 커밋이 여러 개가 될 수 있어 탐색 순서에 따라 기산점이 branch 커밋 또는 merge 커밋으로 달라진다. 그 결과 deadline이 연장되거나 조기 만료될 수 있다. T-78 ⑥·⑦은 선형 T→지연 도입과 필드 위조만 다루며 이 위상을 검증하지 않는다.
  Recommendation: merge 부모 간 술어값이 갈리는 DAG에서 trigger_commit을 유일하게 만드는 규칙과 해당 2-parent 변이를 검증 대상으로 요구하라.
- [high] U-16 승인 원장은 전이 내용과 결속되지 않아 2커밋 F7 우회가 통과한다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:4782-4790)
  승인 행은 `approved_at_head`, `reviewer_ref`, `rationale_ref`를 선언하지만, 기계 검사는 reviewer_ref의 실재·해석만 확인하고 U-16-c는 행 도입 커밋이 NO 커밋의 진 조상인지만 본다. 문서 전체에서 `approved_at_head`와 `rationale_ref`의 소비 규칙이 없고, 승인 산출물이 해당 row의 제안된 내용이나 YES→NO 변경을 검토했다는 digest/identity 결속도 없다. 따라서 작성자가 무관한 기존 리뷰를 가리키는 승인 행을 먼저 커밋한 뒤 owner를 제거하고 NO로 바꾸면 `NO_ROWS_CLEAR`를 얻는다. 문서도 이 순서를 통과로 인정한다(:4821, :4834-4840). T-82는 stale·무관 reviewer_ref, approved_at_head 위조, 승인 후 전이 내용 변경을 뮤테이션하지 않아 '실제 provenance 소비자'라는 주장을 증명하지 못한다.
  Recommendation: 승인 기록과 reviewer 산출물이 정확한 row 내용·전이·기준 HEAD에 결속되는지를 소비하고, 무관·stale 승인 및 승인 후 내용 변경 변이가 실패하는 증거를 요구하라.

Next steps:
- Lane B 및 P-0/D0 착수를 NOT_PASSED로 유지한다.
- U-15가 D0-A 구현 전에 실제 진입을 거부하는 실행 증거를 확인한다.
- U-12 merge-DAG 변이와 U-16 stale·무관 승인 변이가 fail-closed임을 확인한다.
```

---

# 수용검사 (오케스트레이터) — **채택 3 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high | `:4048-4056` 실재 — U-15 강제 지점 = `tools/tos_completion_status.py --check` **단일**(미생성·D0-A 산출) · `:3427` 단계 8 진입 조건 = U-15-c. **순환 확인**: 진입을 막을 검사기가 진입 후에야 생긴다 | 채택 |
| 2 | high | `:3631-3638` 실재 — "조상 방향으로 내려가며 처음 False 가 되는 커밋의 자식". **merge 부모 선택 규칙 부재 확인.** 이 저장소에 merge 커밋 다수 실재 | 채택 |
| 3 | high | `:4782-4790` 실재 — 행 스키마에 `approved_at_head`·`rationale_ref` 가 있으나 기계 검사는 `reviewer_ref` 실재·해석 + U-16-c 조상성뿐. **내용 결속 부재 확인** — 무관 승인 선커밋 + 후속 NO 전이 = 2커밋 우회 | 채택 |

## 관측 (finding 아님)

- **수렴 신호**: findings 6(v2.5) → 3(v2.6) → 3(v2.7)이나, 이번 3건은 전부
  **직전 반영분의 잔여 우회**이며 새 결함 클래스가 아니다. "문구-only 아님"이
  3판 연속 유지됐다.
- #1 의 핵심 관측: `approval_currency`(git log 공집합)와 `oq11_rebinding_required`
  (digest 재계산)는 **검사기 없이 오늘 실행 가능한 명령**이다 — 소비자 순환의
  해소 경로는 "미래 검사기"가 아니라 **지금 실행 가능한 명령 레시피에의 결속**이다
  (저작 가능).
- #2·#3 도 저작 가능: first-parent 또는 전-부모 결합 규칙 + 2-parent 변이(T-78),
  승인 행에 row 내용 digest·전이 명세·기준 HEAD 결속 + stale/무관/사후 변경
  변이(T-82).

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
