# 레인 B 계획 «재심 #7» — 계약 v2.22 에라타 57차 + O-6 재결속 (C4-a 검사기 구분자 정합 후) · needs-attention (head 038c2227)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 038c2227de30e6945b7ca1d16317f403a72acf47
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 0aa465a5d9e12b598470cdf5ab716b2e4e34a1721f4871bb8fa1b4b6b37c162a
bound_set_digest: 16e97f44e9b32882d03c7d9327a2d088ef5f4b385e6b3823aa2e92fb59cf4f46
decided_at_head: 5dfcb236b2f5849086985fb3d2a227739657b1b6
contract_blob: 3411f241803f6e1586f3d9fbfdf17b5fe4c76d02
job_id: review-mtnxyiaq-1bfaf7
job_class: review
base: 5fd23a6cbdbe567b3decbb0eca10d1b13ac7ce3f
scope: branch
prior_verdict: .omc/review/20260905-140531/verdict.md
completed_at_utc: 2026-09-05T05:32:00Z
operator_directive: 2026-09-05 「배타 문법 계약 명문화 진행」
```

**needs-attention · findings 1 (medium · 계약 (ㅁ) :3254-3255 「공백」의 코드 포인트 미특정).**
재심 #6 finding 1 = **«부분 해소»** — 구현은 중점에만 ASCII 공백을 허용하고 두 공격(`\r;\r` · `\n \n·`)을 막았으나, 계약의 「공백」이 U+0020 만인지
유니코드 공백인지 문언만으로 결정되지 않아 독립 구현이 상반된 판정을 낼 수 있다. 결속값 전부 일치 · contract check + self-test 145 rc 0 ·
UNCHK-027 은 U-4/U-5 정합. 직접 호출표: 공격 둘 False · 정본 결합·중점 공백 0/다수·연속 구분자·선두/말미 빈 구획 True · 내부 공백 변형·NBSP·CRLF False.

## 수용검사 (오케스트레이터)

- **finding 1 채택.** file:line 실재. 재심 #6 수용검사에서 오케스트레이터가 「ASCII space 로 읽는다」고 해석을 적어 두었지만, 심판의 지적이 옳다 —
  그 해석은 계약 밖(verdict.md)에 있고 계약 문언은 두 독해를 허용한다(S-19 · 계약문의 형식 용어는 문자 그대로 읽혀 검산된다). 처분 = **에라타 58차**
  (ㅁ)에 「ASCII 공백 U+0020 만 · 0개 이상 · 중점 전용 · 세미콜론/LF 는 무공백 · 빈 구획 = 길이 0」을 축자로 특정 + S-26 58차 항. 계약 편집이므로
  S-26 ⑥ 리셋(이미 0) · O-6 재결속 · 레인 B 재심 #8. 검사기 `038c2227` 은 이미 그 문언의 실체화라 코드 변경 0.
- 비협상 배치 없음 · silenced 아님 · 변경 범위 안(57차 저작 문장).
- **착지 규율**: needs-attention 이라 `docs/reviews/phase0-completion-contract/` 착지 금지 — 후속 approve 와 함께 이력 착지.

---

## Codex 판정 (verbatim — 손대지 않음)

```
Target: branch diff against 5fd23a6c
Verdict: needs-attention

NO-SHIP. 재심 #6 finding 1은 «부분 해소»다. 구현은 중점에만 공백을 허용하며 기존 두 공격을 막았지만, 계약의 `공백`이 ASCII U+0020만 뜻한다는 해석은 유일하지 않다. 직접 호출표: `\r;\r`=False, `\n \n·`=False, 정본 ` · `/`;`/LF 결합=True, 중점 공백 0개·다수=True, 연속·인접 구분자와 선두·말미 빈 구획=True, 정본 내부 공백 변형·NBSP·CRLF=False. HEAD·plan_scope_digest·contract blob·O-6 digest·decided_at_head는 모두 결속값과 일치했다. contract check와 self-test 145종은 rc 0. completion-status와 focused pytest는 사용 가능한 임시 디렉터리 부재로 rc 2여서 예상 2건 외 위반은 확인하지 못했다. UNCHK-027은 blocked_by가 비어 있지 않고 owner_track=`Phase 0`이라 U-4/U-5와 정합한다.

Findings:
- [medium] ASCII 공백 한정이 계약 문언에 존재하지 않는다 (docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:3254-3255)
  (ㅁ)은 중점 U+00B7과 LF를 코드 포인트 수준으로 특정하면서 중점 주변에는 단지 `공백`을 허용한다고 쓴다. 중점에만 수식된다는 점은 명확하지만, `공백`이 U+0020만인지 Unicode whitespace인지 문언만으로 결정되지 않는다. `byte-for-byte 동일`과 `정규화 없음`은 분할 후 구획 비교 규칙이지 어떤 문자가 구분자에 흡수되는지를 정의하지 않으므로 이 모호성을 해소하지 못한다. 반면 검사기는 ` *· *|;|\n`으로 U+0020만 허용하여 NBSP를 거부한다. 따라서 기존 CR 및 공백-only 은닉 공격은 닫혔어도, 계약과 구현이 같은 강도라는 결론은 특정 해석을 전제한다. 다른 독립 구현이나 재심이 Unicode 공백 해석을 택하면 동일한 계약 행에 상반된 완료 판정을 내릴 수 있다.
  Recommendation: `앞뒤 ASCII 공백 U+0020 0개 이상 허용`처럼 허용 코드 포인트와 수량을 계약에 축자로 명시하라. 계약 본문 편집이므로 S-26 ⑥ 카운터를 리셋하고 O-6를 재결속한 뒤 레인 B 재심 비용을 다시 부담해야 한다.

Next steps:
- 계약의 `공백`을 U+0020으로 정밀화하고 S-26 ⑥ 리셋·O-6 재결속·재심을 수행한다.
- 쓰기 가능한 임시 디렉터리가 있는 환경에서 completion-status와 control_14/control_15 테스트를 재실행해 예상된 APPROVAL_STALE·생성물 불일치 외 위반이 없는지 확인한다.
```

원문·실행 로그: `.omc/review/20260905-142639/codex-wait.out` · `codex-result.json` · `focus.txt` · `revision.txt` · `evidence/`.
