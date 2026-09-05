# 레인 B 계획 «재심» — S-26 ② 재개 4회차 (카디널리티 처분 후 · 계약 편집 없음) · needs-attention (head 9f80f6a1)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 9f80f6a131174df099da4b7137de79047305c50b
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: ea4ea16c17f2ebf572251071bdb6395b9f238e83329379df7ef6a93c5f0ed43f
bound_set_digest: 4e6c975f794696066a25abe4ee827594afa18f8fac8bfb5e7bf31d43508b3c2f
decided_at_head: 8923aab2188b5de7eb7a8c5fc282cde636ca969a
contract_blob: 899689fccdf7bed1705e927e2745ad839dc63875
job_id: review-mtnmo7fu-vfu543
job_class: review
base: 48243cd2e07c1357a389e670cf2f23af479d1595
scope: branch
prior_verdict: .omc/review/20260905-041033/verdict.md
completed_at_utc: 2026-09-05T00:25:00Z
operator_directive: 2026-09-04 「S-26 재심 재개」
```

**needs-attention · findings 1 (medium · 검사기 `tools/tos_completion_status.py:4039-4060` · 계약 본문 아님).**
직전 finding 1 = **«부분 해소»** — 무공백 라벨의 세 구분자 병기·기록 경로 중복은 False 가 됐으나, 개행 뒤 선행 공백·탭·NBSP·zero-width space 가
붙은 모순 구획은 `startswith` 분류에서 빠져 정확 구획과 함께 True.
S-26 항별(Codex 독립 측정): ① 성립 · **② 불성립 0/2** · ③④⑤⑥ 성립 · 결속값 4종 일치 · ⑧ 교착 그대로. `--check` 는 샌드박스 rc 2 → HEAD 생성물
대체 확인(오케스트레이터 직접 실행 GREEN · ENTRY_OK). 8e14069a(값 승인)는 §7.4 VALUED·§11 행과 정합, 역사 문언은 S-12 기록 — 동결 계약을 stale 로
만들지 않음.

## 수용검사 (오케스트레이터)

- **finding 1 채택.** file:line 실재(9f80f6a1 의 라벨 분류 `startswith`). Claude 측 리뷰어가 같은 자리를 «비차단 nit(과잉 차단 방향)»로 적었는데,
  Codex 는 그것이 **모순 구획을 카디널리티에서 빼는 우회**(fail-open)임을 실증했다 — 심판이 옳고 리뷰어 판단이 틀렸다(한 자리의 두 극성:
  정본 구획에 붙으면 과잉 차단, 모순 구획에 붙으면 우회). 처분 = 분류는 NFKC·Cf-제거 정규화 후 라벨 부분문자열(느슨), 정본 수용은 byte-exact
  (엄격) — 두 층 규칙(권고 그대로 · 계약 무접촉 → ⑥ 리셋 없음). 비협상 배치 없음 · silenced 아님 · 변경 범위 안. 실코퍼스 NONE 사이트 0 →
  현행 값·생성물 불변.
- **S-26 ② 카운터**: 0/2. **네 판 연속 material 1**(경로 결속 → 부분문자열 → 존재/유일성 → 라벨 분류). 각 판의 결함은 직전 수리가 새로 도입한
  표면에서 나왔고 폭은 매 판 좁아졌다(함수 하나 · 조건 한 줄). 그러나 이것은 2026-08-30 정지 지시가 지목한 «수정→재심→finding» 형상과 같다.
  오케스트레이터는 이 처분과 5회차까지 진행하고, 5회차 결과와 무관하게 **운영자에게 루프 한도(회차 상한 또는 «잔여 등재로 종결»)를 묻는다.**
- **착지 규율**: needs-attention verdict 는 후속 approve 와 같은 커밋에 이력으로 착지(단독 착지는 R-3 을 깨뜨림). 현재 미착지 verdict 4건
  (233516 · 033432 · 041033 · 091036).

---

## Codex 판정 (verbatim — 손대지 않음)

```
Target: branch diff against 48243cd2
Verdict: needs-attention

출하 보류. 직전 finding 1은 «부분 해소»: 무공백 라벨의 ` · `/`;`/개행 병기와 기록 경로 중복은 이제 False지만, 개행 뒤 선행 공백·탭·NBSP·zero-width space가 붙은 모순 구획은 라벨 카디널리티에서 제외되어 정확 구획과 함께 True다. S-26 ① 성립(결속 문서 이력 공집합, blobs 899689fc/ec3464c0) · ② 불성립 0/2(신규 medium 1) · ③ 성립(직전·현재 validator rc 0) · ④ 성립(CUR/CIT/VER/CARD/RULE 위반 0) · ⑤ 성립(self-test rc 0, 145종 전건 판별·죽은 검사 0·역방향 과잉 차단 0) · ⑥ 성립(계약 본문 byte 불변). 결속값 HEAD 9f80f6a1, plan digest ea4ea16c…, bound digest 4e6c975f…, decided head 8923aab2가 모두 일치했다. completion-status는 임시 디렉터리 부재로 rc 2였고 HEAD 생성물에서 ENTRY_OK 및 resolver/marketfeed VALUED를 대체 확인했다. 8e14069a의 비-null 값은 §7.4 VALUED 및 §11 행과 정합하며, 지정된 역사 문언은 S-12 기록이므로 동결 계약을 새로 stale·거짓으로 만들지 않았다. ⑧은 기존 도달 가능성 교착 그대로이며 이 판의 종료 요구가 아니다.

Findings:
- [medium] 선행 공백을 붙인 모순 구획이 U-6′ 카디널리티 검사를 우회한다 (tools/tos_completion_status.py:4039-4060)
  구획 분할 후 `startswith("스캔 결과:")`와 `startswith("독립 리뷰 기록:")`만 세므로, 개행 뒤 공백이나 탭이 붙은 구획은 같은 라벨을 명백히 표시해도 종류별 개수에서 빠진다. 직접 대조에서 정본 구획 하나 뒤에 `\n  스캔 결과: 후보 우주 99개, ...` 또는 `\n\t독립 리뷰 기록: .../99990101-000000/verdict.md`를 병기했을 때 함수가 모두 True를 반환했다. NBSP와 zero-width-space 접두도 True였다. 따라서 정본을 미끼로 남기고 상충하는 스캔 범위나 기록 경로를 사람이 읽을 수 있는 별도 구획에 공시하면서 NO_DEPENDENCY 문법 충족을 얻을 수 있다. 현재 NONE 사이트가 0이라 즉시 상태값을 바꾸지는 않지만, 장래 NONE 사이트에 적용될 U-6′의 fail-open이므로 직전 finding은 완전히 해소되지 않았다.
  Recommendation: 계약은 편집하지 말고, 보호 라벨을 카디널리티용으로 분류할 때 선행 Unicode 공백과 default-ignorable 문자를 포함한 변형 및 다른 구획 안의 라벨 출현을 fail-closed로 포착하되, 유일 구획의 정본 비교는 계속 byte-exact로 유지하라. 공백·탭·NBSP·zero-width-space가 붙은 모순 스캔/기록 구획 병기를 각각 red 대조군으로 추가하라.

Next steps:
- 라벨 분류 우회를 검사기와 대조군만 수정해 닫는다. 계약 무편집이므로 S-26 ⑥ 리셋과 O-6 재결속은 불필요하다.
- 수정 후 새 공백·유니코드 병기 대조군, 기존 ⑩~⑫, validator, 145종 self-test를 재실행한다.
- 다음 material 0 독립 재심에서 S-26 ② 카운터를 1/2로 다시 시작한다.
```

원문·실행 로그: `.omc/review/20260905-091036/codex-wait.out` · `codex-result.json` · `focus.txt` · `revision.txt` · `evidence/`.
