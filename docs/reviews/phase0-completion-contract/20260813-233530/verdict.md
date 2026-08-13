# verdict — 레인 B (계획 심판) · v2.6 재심

```yaml
adjudicator: codex
verdict: needs-attention
gate_status: NOT_PASSED
reviewed_at_head: 843ecd02355271d17e21b535c962086c9367a9ea
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 8af4b54b5fa7081e119acb42cbb3ee6fc73f093e7e7419e747023edf2deeea8e
reviewed_version: v2.6 (4,404행) — 동결 c8373de2 · 6e′ 재결속 843ecd02 이후 심사
findings: 3                        # high 3
prior_verdict: .omc/review/20260813-205553/verdict.md   # v2.5 (레인 B, NOT_PASSED)
mode: A (adversarial-review, --scope working-tree), write=false
lane: B (계획) — plan_scope_digest 로 계획 문서 2건에만 결속
job: review-msrn0m13-1ea1cj   # 재디스패치 잡의 유일한 최종 결과
```

리비전 결속: 디스패치 직전 = 심사 종료 후 재계산 **일치** (HEAD·digest 양쪽 불변 —
심사 중 문서 정지 확인). 부수 실측: `bound_set_digest` 재계산 `328713aa…` ==
`OQ-11-DISPOSITION.md:10` 보유값 — **오케스트레이터·Codex 독립 실측 동일 결론.**

**인프라 기록**: 최초 잡 `review-msrmhatj-jnj7gs` 는 디스패치를 파이프로 포어그라운드에
붙잡아 둔 오케스트레이션 실수로 Bash 타임아웃 SIGTERM 에 함께 사망(판정 미산출·
status 만 running 인 좀비 → cancel). 완전 분리 재디스패치의 최종 결과만이 이 판정이다.
중간 preview 아님.

## 처분

**직전 6건: F#1 해소 · F#2 부분해소 · F#3 해소 · F#4 부분해소(보호 본체 미해소·회피
유지) · F#5 부분해소 · F#6 해소. "문구만" 0건.**
`CLAUDE.md` 비협상 규칙 직접 충돌 **없음** (`:21-36`·`:85-105` 대조).
신규 high 3건 — 중심은 **F#1 의 교정이 만든 순서 결함**: 승인 직후 첫 작업 P-0 가
상위 계획(bound_paths 의 하나)을 개정해 방금 취득한 결속을 스스로 깨는데,
D0-A 진입 전 재동결·재결속·재심을 요구하는 소비자가 없다.

## Codex 출력 (verbatim)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

NO-SHIP. 실측 결과 현재 digest 328713aa20532b80aaaf9b1fdbdf5f6ca352036f20a135f0dc36e95c61b7d6f6은 OQ-11 아티팩트와 일치하고, c8373de2→843ecd02 사이에는 재결속 아티팩트만 변경됐으며, 보존된 판정 22건은 운영 원본과 모두 byte-identical이다. 직전 finding 처분은 F#1 해소됨, F#2 부분해소, F#3 해소됨, F#4 부분해소(보호 본체는 미해소·회피 유지), F#5 부분해소(실제 U-14/T-80 절차는 생겼으나 문서 사본은 범위에서 제외되고 T-71은 ATTESTED), F#6 해소됨이다. 문구만 바뀐 항목은 없다. 7항목 판정: 1 단계·의존성 needs-attention, 2 숨은 가정 needs-attention, 3 검증 가능성 needs-attention, 4 실패·rollback 부분충족이나 재진입 경로 미폐쇄, 5 범위 이탈·과잉설계 해당 없음, 6 CLAUDE.md:21-36·85-105 비협상 규칙과 직접 충돌 해당 없음, 7 인접 영향 needs-attention. 현행 tos_spec_status PASS는 코퍼스 상태만 증명하며 아래 계획 결함을 해소하지 않는다.

Findings:
- [high] 최초 P-0가 방금 취득한 OQ-11 결속을 즉시 무효화하지만 재결속·재심 재진입 단계가 없다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3193-3207)
  P-0는 상위 계획의 §1·§6·§8을 반드시 먼저 수정한다. 그런데 같은 상위 계획은 OQ-11의 정확한 두 bound_paths 중 하나이고, §12.3의 7단계는 현행 6e와 계획 심사 승인을 P-0 착수 조건으로 둔다. 따라서 승인 후 첫 작업이 bound_set_digest를 깨고 검토된 계획 내용도 변경한다. 8단계 D0-A 전에 새 동결·재결속·재심을 요구하는 단계나 소비자는 없다. 구현이 stale 권위로 계속되거나 완료 시점에 뒤늦게 차단되는 순서 결함이다.
  Recommendation: P-0 변경 후 유효한 bound_set_digest와 갱신된 계획 심사 결속을 D0-A 진입 소비자가 실제로 요구하게 하고, P-0가 상위 계획을 바꾼 상태에서 이전 승인으로 D0-A에 진입하는 변이가 실패함을 증명하라.
- [high] U-12의 durable 시계는 트리거가 아니라 원장 행 생성 시각에 묶여 영구대기를 재개할 수 있다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3544-3557)
  객관적 트리거는 정의됐지만 raised_at_effective는 기재값과 '원장 행을 도입한 커밋'의 author date 중 최솟값이다. 트리거가 커밋 A에서 발생해도 운영자가 원장 행을 커밋 B까지 만들지 않으면 A와 B 사이 시간은 사라지고 B부터 PENDING_WITHIN이 다시 시작된다. trigger_at_head는 스키마에만 있고 기산점 계산이나 검증에 소비되지 않는다. T-78도 원장 누락을 RAISE_MISSING으로만 검사하며 '늦게 행을 추가해 deadline을 재시작'하는 변이를 다루지 않는다. 따라서 실제 검증 절차가 추가된 점은 문구-only 수정이 아니지만, 직전 IND-1의 핵심인 NO_RESPONSE 도달 보장은 부분해소에 그친다.
  Recommendation: 기산점이 최초 객관적 트리거 커밋에 결속되는지를 검증하고, 트리거 후 원장 행 생성을 지연했다가 추가하는 변이가 이미 경과한 시간을 보존하며 --check를 red 또는 NO_RESPONSE로 만드는 증명을 추가하라.
- [high] F7의 YES→NO 소유·게이트 우회는 여전히 Phase 0 완료 경로에서 활성이다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3832)
  UNCHK-021은 closable=YES 행을 무관한 실재 절과 함께 NO로 바꾸면 U-1a, 철회된 U-9/U-9a, gate findings를 모두 벗어난다고 직접 인정한다. v2.6은 owner_track 불일치를 Phase 2-5로 정리하고 F7을 미해소로 재분류했지만, 독립 review provenance 소비자는 Phase 1의 비차단 리뷰 표면일 뿐이며 현재 Phase 0 전이 가드는 아니다. 남는 closable_no_rows도 비차단이다. 따라서 허위 Phase 0 완료와 owner 의무 제거가 가능한 핵심 회피는 그대로다.
  Recommendation: 독립 provenance를 실제 YES→NO 전이 소비자가 강제하고 무승인 전이를 거부하는 검증이 존재하기 전까지 F7을 승인 차단 결함으로 유지하라.

Next steps:
- Lane B와 P-0/D0 착수를 NOT_PASSED로 유지한다.
- 재심에서는 P-0 후 결속 재진입, 지연된 U-12 원장 생성 변이, F7 실제 전이 소비자의 실패 증거를 확인한다.
```

**스키마 기록**: `verdict` 필드 실재(`needs-attention`) — fail-closed 처리 불요.
findings 3건 전부 `severity: high`, `file`/`line_start`/`line_end`/`confidence`(0.97~0.99)/
`recommendation` 완비. `next_steps` 3번째 원소는 빈 문자열(`""`) — 원문 그대로 보존.

---

# 수용검사 (오케스트레이터) — **채택 3 / 기각 0**

기각 사유 3가지(팬텀 file:line / 의도적 silenced / 비협상 배치) 중 해당 없음. 전건 실측.

| # | sev | 실측 | 처분 |
|---|---|---|---|
| 1 | high | `:3193-3207` 실재 — P-0 표가 상위 계획 §1·§6·§8 개정을 명시, 상위 계획은 `bound_paths` 2건 중 하나. §12.3 에 P-0 후·D0-A 전 재동결·재결속·재심 단계 부재 확인 | 채택 |
| 2 | high | `:3544-3557` 실재 — `raised_at_effective = min(기재값, 도입 커밋 author date)`. `trigger_at_head` 는 행 스키마에만 있고 파생·검증에 미소비. 지연 도입 시 A→B 경과 소실 확인 | 채택 |
| 3 | high | `:3832` 실재 — UNCHK-021 이 우회를 자인하고 `blocks_gate` 없음(Phase 0 비차단). v2.6 의 미해소 재분류는 정직했으나 차단은 아니었음 | 채택 |

## 관측 (finding 아님)

- 신규 3건 중 #1 은 **F#1 교정의 2차 귀결**이다 — 재결속 규율을 세우자 그 규율이
  P-0 자신에게도 적용되어야 함이 드러났다. 결함의 이동이지 퇴행이 아니다.
- #3 의 처분 선택지는 둘이다: (a) UNCHK-021 을 Phase 0 차단으로 승격 + YES→NO 전이
  provenance 소비 계약 저작(fail-closed 기본값·저작 가능) (b) 운영자 위험 수용 선언
  (운영자 게이트). v2.6 이 "위험 수용은 운영자 소관"으로 남긴 것과 정합.

## 게이트

```
통과 = adjudicator:codex AND verdict:approve AND plan_scope_digest 일치
현재 = codex AND needs-attention AND 일치      → 불성립
```

**레인 B NOT_PASSED 유지. P-0/D0 착수 불가.**
