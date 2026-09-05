# 레인 B 계획 «재심» — S-26 ② 재개 3회차 (구획 문법 처분 후 · 계약 편집 없음) · needs-attention (head 0140b866)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 0140b86658896e24292fd46f6164e306e6afff0c
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: e15a6cc3ddb1850103713660c18d2bd77fb9b0f4189ca87bb8fd5d86ea06058c
bound_set_digest: 4e6c975f794696066a25abe4ee827594afa18f8fac8bfb5e7bf31d43508b3c2f
decided_at_head: 8923aab2188b5de7eb7a8c5fc282cde636ca969a
contract_blob: 899689fccdf7bed1705e927e2745ad839dc63875
job_id: review-mtnby9g3-rkrbdd
job_class: review
base: 48243cd2e07c1357a389e670cf2f23af479d1595
scope: branch
prior_verdict: .omc/review/20260905-033432/verdict.md
completed_at_utc: 2026-09-04T19:20:00Z
operator_directive: 2026-09-04 「S-26 재심 재개」
```

**needs-attention · findings 1 (medium · 검사기 `tools/tos_completion_status.py:4018-4035` · 계약 본문 아님).**
직전 finding 1 = **«부분 해소»** — 세 기존 공격(미끼 scope · 경로 접미 · 동일 구획 두 번째 경로)은 False 가 됐으나, 정확 구획과 모순 구획을
**별개 구획으로 병기**하면 True(존재 양화자 · 유일성 미검사).
S-26 항별(Codex 독립 측정): ① 성립 · **② 불성립 0/2** · ③④⑤⑥ 성립 · ⑦ 권한 불변 · 결속값 4종 일치 · ⑧ 교착 그대로. `--check` 는 샌드박스
rc 2 → HEAD 생성물 대체 확인(오케스트레이터 직접 실행 GREEN · ENTRY_OK). 0140b866 은 동결 문언을 stale 로 만들지 않았고, 구획 문법 자체는
현 호출자의 정본 형상에서 과잉 차단 없음.

## 수용검사 (오케스트레이터)

- **finding 1 채택.** file:line 실재(0140b866 의 `_d1_u6prime_row_state` (2)(4) 존재 검사). 처분 = 구획 종류별 카디널리티 정확히 1 + 그 유일
  구획의 정본 동일성(권고 그대로 · 계약 무접촉 → ⑥ 리셋 없음). 비협상 배치 없음 · silenced 아님 · 변경 범위 안. 실코퍼스 NONE 사이트 0 → 현행
  D0-5 값·생성물 불변.
- **S-26 ② 카운터**: 0/2. 세 판 연속 material 1 — 매 판 직전 수리 코드에서 다음 결함이 나오는 «수정→재심→finding» 형상(2026-08-30 정지 지시의
  사유와 같은 궤적)이 재현되고 있다. 이번 finding 은 문법 정의의 논리적 잔여(∃ → ∃!)로 좁고, 그 다음 후보가 보이지 않는다 — 그러나 이것은
  저작자의 판단이고 심판의 판단이 아니다. 4회차 이후에도 material 이 이어지면 운영자에게 루프 한도를 묻는다.
- **착지 규율**: needs-attention verdict 는 후속 approve 와 같은 커밋에 이력으로 착지(단독 착지는 R-3 을 깨뜨림).

---

## Codex 판정 (verbatim — 손대지 않음)

```
Target: branch diff against 48243cd2
Verdict: needs-attention

출하 보류. 직전 finding 1은 «부분 해소»: 세 기존 공격(미끼 scope·경로 접미·동일 구획의 두 번째 경로)은 모두 False가 됐지만, 정확 구획과 모순 구획을 각각 병기하면 여전히 True다. S-26 ① 성립(결속 문서 이력 공집합, blobs 899689fc/ec3464c0) · ② 불성립 0/2(material 1) · ③ 성립(validator rc 0) · ④ 성립(CUR/CIT/VER/CARD/RULE 위반 0) · ⑤ 성립(self-test rc 0, 145종 전건 판별·죽은 검사 0·역방향 과잉 차단 0) · ⑥ 성립(계약 편집 없음) · ⑦ 권한 불변 · ⑧ 기존 교착 그대로이며 종료 요구가 아니다. HEAD·plan_scope_digest·bound_set_digest·decided_at_head는 결속값과 일치했다. completion-status는 임시 디렉터리 부재로 rc 2였고 HEAD 생성물에서 ENTRY_OK와 resolver/marketfeed의 VALUED+BLOCKED를 대체 확인했다. 0140b866은 동결 문언을 stale로 만들지 않았으며, 검사기 구획 문법 자체는 현 호출자가 생성하는 정본 형상에서 별도 material 과잉 차단을 보이지 않았다.

Findings:
- [medium] 모순되는 두 번째 scope·기록 구획을 병기해도 U-6′ 검사가 통과한다 (tools/tos_completion_status.py:4018-4035)
  `segments`에서 기대 구획의 존재만 검사하고 같은 종류 구획의 유일성은 검사하지 않는다. 직접 대조군에서 정확한 스캔 결과 구획 뒤에 `스캔 결과: 후보 우주 9개, 스캔 범위 other_pkg, 파일 8개`를 별도 구획으로 추가하고, 정확한 기록 구획 뒤에 다른 `독립 리뷰 기록:` 경로를 별도 구획으로 추가해도 함수가 `True`를 반환했다. 따라서 정확값을 미끼로 하나 남기고 실제 공시에 모순되는 scope나 미선택 기록을 함께 쓰면서 NO_DEPENDENCY 완료 판정을 얻을 수 있다. 이는 직전 부분문자열 fail-open을 구획 단위의 존재 양화자로 옮긴 것이어서 finding 1의 완전한 해소가 아니다.
  Recommendation: 계약은 편집하지 말고, `스캔 결과:` 및 `독립 리뷰 기록:` 구획을 각각 분류해 정확히 1개만 허용하고 그 유일한 구획이 정본 문자열과 동일한지 검사하라. 정확 구획과 상충 구획을 서로 다른 ` · `, `;`, 개행 구획에 함께 둔 대조군을 각각 red로 추가하라.

Next steps:
- 구획 종류별 카디널리티 검사를 추가해 별도 구획 병기를 fail-closed로 막는다.
- 수정 후 직접 모순 병기 대조군, 기존 ⑪-a~⑪-e, validator, 145종 self-test를 재실행한다.
```

원문·실행 로그: `.omc/review/20260905-041033/codex-wait.out` · `codex-result.json` · `focus.txt` · `revision.txt` · `evidence/`.
