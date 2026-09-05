# 레인 B 계획 «재심 #6» — 계약 v2.22 에라타 57차(U-6′ (ㅁ) reason 배타 문법) + O-6 재결속 · needs-attention (head 3201484f)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 3201484f092b9f76ffed4b3adcaf6beea0a89f18
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 9b9a713716be8e1934b5d05fbb08c85d81d6bf573d2638ccdbd12a85e531f89d
bound_set_digest: 16e97f44e9b32882d03c7d9327a2d088ef5f4b385e6b3823aa2e92fb59cf4f46
decided_at_head: 5dfcb236b2f5849086985fb3d2a227739657b1b6
contract_blob: 3411f241803f6e1586f3d9fbfdf17b5fe4c76d02
job_id: review-mtnx7eix-0bq0s8
job_class: review
base: 5fd23a6cbdbe567b3decbb0eca10d1b13ac7ce3f
scope: branch
prior_verdict: .omc/review/20260905-133502/verdict.md
completed_at_utc: 2026-09-05T05:13:00Z
operator_directive: 2026-09-05 「배타 문법 계약 명문화 진행」
```

**needs-attention · findings 1 (medium · 검사기 구분자 강도 ≠ (ㅁ) 문언 · 계약 편집 «불필요»).**
직전 finding 1(재개 아크 5회차 · 닫힌 세계 과잉 차단) = **«해소»** — 운영자가 계약층 결정을 내렸고 4종 우회 실측이 배타 선택의 근거이므로
회피가 아니다. 결속값 4종(head · plan digest · O-6 digest · decided_at_head) 일치 · contract check + self-test 145 rc 0 · control_14 10건 통과 ·
v2.23 리터럴 0 · 개발계획·이력 무접촉 · 57차 S-26 ⑥/② 0 기록 · 좌표 정정·currency 태그 확인. `--check` 는 샌드박스 rc 2(C3 전 예상 2건 외 미확인).

## 수용검사 (오케스트레이터)

- **finding 1 채택.** file:line 실재(계약 :3253-3265 (ㅁ) 구분자 문장 · 검사기 `_D1_U6PRIME_SEGMENT_SPLIT_RE`). (ㅁ)은 구분자를 U+00B7(앞뒤
  공백 허용)·`;`·LF 로 열거하고 빈 구획만 무시하는데 구현 정규식 `\s*·\s*|\s*;\s*|\n` 은 CR·유니코드 공백을 `;`·`·` 주변에서 흡수하고 LF 사이
  공백-only 구획을 뒤따르는 `·` 의 `\s*` 에 합쳐 숨긴다(직접 호출 `\r;\r` · `\n \n·` 결합 → True). 문언이 구현보다 **좁고** 방향은 구현이
  fail-open. **처분 = 검사기를 문언 강도로 좁힌다**(` *· *|;|\n` · ASCII space 만 · 공백-only 구획은 외부 구획 → red) + 대조군 ⑮(CR+`;` ·
  NBSP+`·` · LF 사이 공백-only · 탭+`;` red · 공백 변형 green). **계약 무접촉** → S-26 ⑥ 리셋 없음 · O-6 재결속 없음 · 재심 #7 은 같은 계약
  blob 에 대해 돈다. 비협상 배치 없음 · silenced 아님 · 변경 범위 안(1fd98450 도입 정규식).
- 「공백」의 해석 모호성(ASCII vs Unicode · 중점에만 적용되는지)은 (ㅁ) 문언이 「중점 `·`(U+00B7 · 앞뒤 공백 허용)」로 중점에만 붙였고 다른 두
  구분자에는 붙이지 않았으므로 **중점 전용 · ASCII space** 로 읽는다 — 구현이 그 해석을 코드 포인트로 못박고 docstring 에 (ㅁ) 을 인용한다.
  계약 본문 추가 편집은 하지 않는다(권고의 두 갈래 중 검사기 쪽).
- **S-26**: 이 판은 57차 «에라타 diff» 심사이고 재개 아크(종료됨)의 회차가 아니다. ② 카운터는 57차 편집으로 0 리셋된 상태이며 이 판의
  material 1 은 계약이 아니라 검사기 결함이다 — 그래도 ② 의 정의(신규 material 0)상 이 판은 0 이다. 종결 주장 없음 · ⑧ 교착 그대로.
- **착지 규율**: needs-attention 이라 `docs/reviews/phase0-completion-contract/` 착지 금지. 재심 #7 approve 와 함께 이력으로 착지(C3).

---

## Codex 판정 (verbatim — 손대지 않음)

```
Target: branch diff against 5fd23a6c
Verdict: needs-attention

직전 finding 1은 «해소»다. 운영자가 요구된 계약층 결정을 내렸고, 4종 우회 실측은 포함 문법 대신 배타 문법을 선택할 근거가 되므로 심판 지적을 문언으로 지운 회피가 아니다. 그러나 새 문언과 불변 검사기의 구분자 강도가 아직 다르다. HEAD·plan digest·O-6 digest·decided_at_head는 모두 결속값과 일치했다. 계약 검사와 145종 self-test는 rc 0, control_14 10건은 통과했다. completion-status는 read-only sandbox의 임시 디렉터리 부재로 rc 2여서 예상된 두 위반 외 여부는 확인하지 못했다. 신규 v2.23 리터럴 0, 개발계획·닫힌 심사 이력 무접촉, 57차 S-26 ⑥/②=0 기록, 좌표 정정과 currency 태그도 확인했다.

Findings:
- [medium] 검사기가 계약에 없는 공백까지 구분자로 흡수한다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3253-3265)
  (ㅁ)은 구분자를 U+00B7(앞뒤 공백 허용), 세미콜론, LF로 열거하고 빈 구획만 무시하며 나머지 구획 0과 byte-exact를 요구한다. 반면 불변 구현은 `\s*·\s*|\s*;\s*|\n`이라 세미콜론 주변의 CR과 모든 Unicode whitespace까지 흡수하고, LF 사이의 공백-only 구획도 뒤따르는 중점의 `\s*`에 합쳐 숨긴다. 직접 `_d1_u6prime_row_state`를 호출하면 정본 넷을 `\r;\r` 또는 `\n \n·`로 연결한 reason이 모두 True였다. 전자는 계약이 허용한 LF가 아니고, 후자는 외부 공백 구획이 있는데도 사라지므로 장래 NONE 사이트가 비정본 공시로 D0-5를 통과할 수 있다. 또한 «공백»이 ASCII space인지 Unicode whitespace인지, 중점에만 적용되는지에 두 해석이 가능해 C4 구현 모호성도 남는다. 기존 ⑧-d/⑧-e/⑧-f 대응 control_14g/control_14a~f/control_14j는 실재하고 통과하지만 이 경계는 다루지 않는다.
  Recommendation: 검사기 구분자를 문언 그대로 ASCII space만 허용하는 ` *· *|;|\n` 수준으로 좁히고, CR+세미콜론·NBSP+중점·LF 사이 공백-only 구획 대조군을 추가하라. Unicode `\s`를 의도했다면 계약에 허용 code point와 적용 구분자를 축자로 명시해야 한다. 그 계약 본문 추가 편집을 택하면 S-26 ⑥ 카운터 리셋, O-6 재결속, 레인 B 재심 비용이 다시 발생한다.

Next steps:
- 구분자 구현과 문언 중 하나를 단일한 문법으로 확정하고 새 음성 대조군을 추가한다.
- 수정 후 contract check, self-test, control_14 배터리를 재실행한다.
- 쓰기 가능한 임시 디렉터리가 있는 환경에서 completion-status를 다시 실행해 APPROVAL_STALE와 생성물 불일치 2건 외 위반이 없는지 확인한다.
```

원문·실행 로그: `.omc/review/20260905-140531/codex-wait.out` · `codex-result.json` · `focus.txt` · `revision.txt` · `evidence/`.
