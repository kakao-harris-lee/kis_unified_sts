# 레인 B 계획 «재심 #8» — 계약 v2.22 에라타 57차+58차 + O-6 재결속 · needs-attention (head 3e8931e8)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 3e8931e89954870d7a0784de5b80c02c280b06b0
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 0a2e079bebf20e7c02a60c30d8979651f3fb7c00a45bb354ad18a25a3f046489
bound_set_digest: 045f3ae7565860df6e0c38d3c7ee49c76f3a4d3784d646279cd1be2727dbb429
decided_at_head: 1db8f9b8b96880d1e92154b92ea8197466588ae3
contract_blob: 6f94dfbbafd48fa3d1b4c73266fdfda19da9bce5
job_id: review-mtnydobs-g6hrlt
job_class: review
base: 5fd23a6cbdbe567b3decbb0eca10d1b13ac7ce3f
scope: branch
prior_verdict: .omc/review/20260905-142639/verdict.md
completed_at_utc: 2026-09-05T05:45:00Z
operator_directive: 2026-09-05 「배타 문법 계약 명문화 진행」
```

**needs-attention · findings 1 (medium · O-6 재결속 기록의 currency 태그 과소 계수 · 계약 본문 아님 · 재결속 불필요).**
재심 #7 finding 1 = **«해소»** — 58차가 ASCII U+0020 만 · 양측 0개 이상 · 중점 전용 · `;`/LF 무공백 · 빈 구획 = 길이 0 을 명시하고 직접 호출이 검사기와
일치. 결속 digest 전부 일치 · contract check + self-test 145 rc 0. 신규: OQ-11 재결속 기록이 `현행(58차 이후)` 태그를 3곳이라 적었으나 실측 4곳
(:110 · :5660 · :5661 · :5871).

## 수용검사 (오케스트레이터)

- **finding 1 채택.** file:line 실재(OQ-11 :1143-1145). 실측: `grep -n "58차 이후"` → 110 5660 5661 5871 — 4곳. 원인: 57차·58차 태그 갱신을
  replace_all 로 했고 계수를 이전 사이클(56차 기록의 «3곳»이 아니라 «4곳»이었음)을 보지 않고 적었다 — :110 은 8차 currency 산문 안에 있는 자리다.
  57차 기록의 같은 계수(:1103)도 틀렸다. 처분 = OQ-11 두 자리 정정(58차 기록 3→4 + 좌표 명시 · 57차 기록은 마커로 정정 · S-12). OQ-11 은 결속
  경로가 아니므로 bound_set_digest 불변 · S-26 ⑥ 리셋 없음 · O-6 재결속 없음; plan_scope_digest 는 HEAD 를 포함하므로 재포착 후 재심 #9.
- 비협상 배치 없음 · silenced 아님 · 변경 범위 안(C2/C2′ 저작 문장).
- **착지 규율**: needs-attention 이라 `docs/reviews/phase0-completion-contract/` 착지 금지 — 후속 approve 와 함께 이력 착지.

---

## Codex 판정 (verbatim — 손대지 않음)

```
Target: branch diff against 5fd23a6c
Verdict: needs-attention

NO-SHIP. 재심 #7 finding 1은 «해소»다: 58차는 ASCII U+0020만, 양측 각각 0개 이상, 중점 전용, 세미콜론/LF 무공백, 길이 0의 빈 구획을 명시했고 직접 호출 결과가 검사기와 일치했다. 그러나 O-6 재결속 기록은 58차 currency 태그를 3곳이라고 잘못 계수한다. 결속 digest들은 일치했고 contract check 및 self-test 145종은 rc 0이었다. `tos_completion_status.py --check`는 샌드박스의 사용 가능한 임시 디렉터리 부재로 rc 2여서 예상된 두 상태는 이번 환경에서 재확인하지 못했다.

Findings:
- [medium] O-6 재결속 기록이 currency 태그 수를 과소 계수한다 (tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md:1143-1145)
  재결속 기록은 계약 blob에 `현행(58차 이후)` 태그가 3곳 있다고 주장하지만, 58차 델타는 실제로 네 곳을 57차에서 58차로 갱신했다: 계약 HEAD의 110, 5660, 5661, 5871행이다. 따라서 결속 해시 자체는 유효해도 이를 설명하는 동결 실측 기록은 실제 diff와 불일치한다. 이 오계수는 요청된 lockstep 및 S-22 전파 검산을 통과하지 못하며 이후 감사자가 네 번째 갱신 지점을 누락된 범위로 오판하게 만든다.
  Recommendation: 재결속 기록의 `커런시 태그 3곳`을 `4곳`으로 정정하고 네 좌표를 명시적으로 대조한 뒤 revision의 HEAD/plan_scope_digest를 다시 포착해 재심하라. 계약 본문 편집은 필요 없으므로 이 정정 자체는 S-26 ⑥ 리셋이나 새로운 O-6 재결속을 요구하지 않는다.

Next steps:
- OQ-11 재결속 기록의 태그 계수를 4로 정정하고 네 실제 위치를 검산한다.
- 새 HEAD에 대해 plan_scope_digest를 재포착한 뒤 레인 B 재심을 반복한다.
- 쓰기 가능한 임시 디렉터리가 있는 환경에서 `tos_completion_status.py --check`의 예상 두 건만 발생하는지 확인한다.
```

원문·실행 로그: `.omc/review/20260905-143827/codex-wait.out` · `codex-result.json` · `focus.txt` · `revision.txt` · `evidence/`.
