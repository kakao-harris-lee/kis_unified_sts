# 레인 B 계획 «재심» — S-26 ② 재개 5회차 · 최종 (닫힌 세계 문법 처분 후 · 계약 편집 없음) · needs-attention (head 1fd98450)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 1fd98450cbc1a0967c723d102b388f7c694e239e
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: c54629787e3d60331b43ca15d4577c86d228bb9ce1f46679c35ae1fda589befb
bound_set_digest: 4e6c975f794696066a25abe4ee827594afa18f8fac8bfb5e7bf31d43508b3c2f
decided_at_head: 8923aab2188b5de7eb7a8c5fc282cde636ca969a
contract_blob: 899689fccdf7bed1705e927e2745ad839dc63875
job_id: review-mtnw4hor-zdytup
job_class: review
base: 48243cd2e07c1357a389e670cf2f23af479d1595
scope: branch
prior_verdict: .omc/review/20260905-091036/verdict.md
completed_at_utc: 2026-09-05T04:43:00Z
operator_directive: 2026-09-04 「S-26 재심 재개」 · 2026-09-05 「5회차 결과 무관하게 종료하고 잔여는 UNCHK 등재로 처분」
loop_terminal: true
```

**needs-attention · findings 1 (medium · 검사기 `tools/tos_completion_status.py:4121-4125` · 계약 본문 아님) · 운영자 지시로 이 판이 마지막.**
직전 finding 1 = **«회피»** — 원래 우회(선행 공백·NBSP·ZWSP·동형이의 콜론·braille·결합문자·VS16 병기)는 전부 red 가 되어 닫혔으나, 계약 U-6′ (ㄹ)
이 요구한 «네 사실의 동일행 **포함**»을 계약에 없는 **닫힌 허용집합**으로 바꿔 역방향 과잉 차단을 만들었다(정본 넷 + `부수 설명: …` 한 구획 → False).
S-26 항별(Codex 독립 측정): ① 성립 · **② 불성립 0/2** · ③④ 성립 · **⑤ 불성립**(self-test 145 PASS 이나 직접 역방향 대조군 실패) · ⑥ 성립 ·
⑦ 권한 불변 · 결속값 4종 일치 · ⑧ 교착 그대로. `--check` 샌드박스 rc 2 → HEAD 생성물 대체 확인(오케스트레이터 직접 GREEN · ENTRY_OK).
직접 대조표: baseline true · 공격 스크립트 전건 false · CR/U+2028/2029/전각 세미콜론/유사 중점 false · 정본 내부 삽입 false · 순서 변경·`;`/개행 혼용 true ·
정본 중복 false · 빈 구획만 true · 공백 구획 false · scope_desc/record_path 구분자 포함 false(fail-closed) · **정본 넷 뒤 부수 설명 false(과잉 차단)**.

## 수용검사 (오케스트레이터)

- **finding 1 채택.** file:line 실재(1fd98450 의 닫힌 세계 비교). 계약 (ㄹ) 문언은 포함 요구이고 배타를 말하지 않는다 — 검사기가 문언보다 강하다.
  비협상 배치 없음 · silenced 아님 · 변경 범위 안. 실코퍼스 NONE 사이트 0 → 현행 값·생성물 불변.
- **처분 = 잔여 등재(운영자 지시 2026-09-05).** 수리·재심 없음. §13 UNCHECKABLE 레지스터에 Codex 권고 문안대로 등재한다:
  축 「U-6′ reason 닫힌-세계 검사기/동결 계약 불일치」 · 사유 「계약은 정본 네 사실의 동일행 포함만 요구하지만 검사기는 모든 부수 reason 구획을
  금지하여 계약 충족 행도 red」 · blocked_by 「운영자 승인 아래 U-6′ 배타 문법을 명문화(계약 편집 = S-26 ⑥ 리셋·O-6 재결속·재심)하거나 검사기의
  과잉 차단을 제거하는 결속 결정」 · owner_track 「Phase 0 completion-contract/checker lockstep」.
- **왜 이것이 정직한 종착인가.** 다섯 판의 궤적: 포함-검사(부분문자열)는 모순 구획 병기를 못 막고(1~4회차 · 4종 우회), 배타-검사(닫힌 세계)는
  우회를 구조적으로 닫지만 계약 문언보다 강하다(5회차). **포함이냐 배타냐는 검사기가 정할 수 없는 계약 층의 결정**이다 — 그것이 UNCHK 등재의
  사유이며 결정자는 운영자다. 오케스트레이터의 판단: 배타 문법을 계약에 명문화하는 쪽이 옳다(포함-only 로 되돌리면 1~4회차의 우회가 전부 되살아난다) —
  그러나 그 편집은 S-26 ⑥ 리셋을 일으키므로 운영자 결정 없이 하지 않는다. 그때까지 검사기는 **fail-closed 쪽(닫힌 세계)** 에 둔다.
- **S-26 ② 카운터**: 0/2 로 종결(재개 아크 5판 전부 material 1). ⑤ 도 이 판에서 불성립. ⑧ 교착은 별개 운영자 축.
- **착지 규율**: 재개 아크 verdict 5건(233516 · 033432 · 041033 · 091036 · 133502)은 전부 needs-attention 이라 `docs/reviews/phase0-completion-contract/`
  에 넣지 않는다(R-3 최신 판독 → ENTRY 파괴). 보존소 `docs/reviews/phase0-codex-records/` 에 byte 복사 + README 색인.

---

## Codex 판정 (verbatim — 손대지 않음)

```
Target: branch diff against 48243cd2
Verdict: needs-attention

출하 보류. 직전 finding 1은 «회피»: 선행 공백·NBSP·ZWSP 및 U+0589/U+A789/U+2236·U+2800·U+0301·U+FE0F 병기는 모두 red가 되어 원래 우회는 닫혔지만, 계약이 요구한 네 사실의 포함·동일행 검증을 계약에 없는 닫힌 허용집합으로 바꿔 역방향 과잉 차단을 만들었다. 그 결과 계약 밖 변경이 동결 문언을 실질적으로 거짓으로 만들었다.
S-26: ① 성립(이력 공집합, blobs 899689fc/ec3464c0) · ② 불성립 0/2(material medium 1) · ③ 성립(직전·현재 validator rc 0) · ④ 성립(CUR/CIT/VER/CARD/RULE 위반 0) · ⑤ 불성립(self-test rc 0·145종 PASS이나 직접 역방향 대조군이 실패) · ⑥ 성립(결속 문서 byte 불변) · ⑦ 권한 불변 · ⑧ 기존 도달 가능성 교착 그대로.
결속 재계산: HEAD 1fd98450cbc1a0967c723d102b388f7c694e239e, plan digest c54629787e3d60331b43ca15d4577c86d228bb9ce1f46679c35ae1fda589befb, bound digest 4e6c975f794696066a25abe4ee827594afa18f8fac8bfb5e7bf31d43508b3c2f, decided head 8923aab2 모두 일치. completion-status는 임시 디렉터리 부재로 rc 2였고 HEAD 생성물에서 ENTRY_OK, D0-5 MET, resolver/marketfeed VALUED를 확인했다.
직접 대조: baseline=true; 공격 스크립트의 동형이의·보이지 않는 문자·결합문자·variation-selector 전부=false; CR/U+2028/U+2029/전각 세미콜론/유사 중점=false; 정본 내부 삽입=false; 순서 변경 및 ;/개행 혼용=true; 정본 중복=false; 빈 구획만 추가=true; 공백 구획=false; scope_desc·record_path 구분자 포함=false(fail-closed); 정본 넷 뒤 부수 설명=false.

Findings:
- [medium] 계약에 없는 닫힌 세계가 정당한 reason 확장을 차단한다 (tools/tos_completion_status.py:4121-4125)
  계약은 U-6′ (ㄹ)에서 네 사실이 «그 한 행의 reason 안에» 있어야 한다고 정하고 네 항목을 열거하지만, reason 전체가 그 네 구획과 정확히 같아야 한다거나 다른 설명을 금지하지 않는다. 반면 이 코드는 정본 넷에 속하지 않는 모든 구획을 거부한다. 직접 시험에서 정본 넷을 모두 유지한 채 `부수 설명: 범위 산정 근거`를 추가하자 False가 됐다. 따라서 계약을 충족하는 공시 행도 NO_DEPENDENCY 완료를 차단할 수 있으며, 테스트 ⑭-g는 이 과잉 차단을 의도된 동작으로 고정한다. U-4의 blocked_by와 U-5의 owner_track은 별도 열이므로 그 두 규칙과의 충돌은 아니지만, S-26 ⑤의 «역방향 과잉 차단 0»은 성립하지 않는다. 현재 NONE 사이트가 0이라 즉시 생성물 값은 바뀌지 않으나 장래 NONE 사이트에서 D0-5를 부당하게 막는 잠복 결함이다.
  Recommendation: §13 UNCHK 잔여 등재 문안 — 축: `U-6′ reason 닫힌-세계 검사기/동결 계약 불일치`; 사유: `계약은 정본 네 사실의 동일행 포함만 요구하지만 검사기는 모든 부수 reason 구획을 금지하여 계약 충족 행도 red`; blocked_by: `운영자 승인 아래 U-6′ 배타 문법을 명문화하거나 검사기의 과잉 차단을 제거하는 결속 결정`; owner_track 후보: `Phase-0 completion-contract/checker lockstep`.

Next steps:
- 이 finding을 권고 문안대로 §13 UNCHECKABLE 레지스터의 잔여로 등재한다.
- 운영자 지시에 따라 5회차를 ②=0/2, ⑤ 불성립으로 종결하고 추가 수리·재심을 시작하지 않는다.
- D0/P-0 착수 금지, restricted_live 및 production 권한 불변을 유지한다.
```

원문·실행 로그: `.omc/review/20260905-133502/codex-wait.out` · `codex-result.json` · `focus.txt` · `revision.txt` · `evidence/`.
