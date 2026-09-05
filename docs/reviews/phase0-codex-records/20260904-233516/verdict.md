# 레인 B 계획 «재심» — S-26 ② 재개 회차 (계약 편집 없음 · 계약 밖 16커밋 currency) · needs-attention (head 11ac075d)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: 11ac075d1ce7ca679397f9b80d4e27d127cfe68d
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 84a96db339a5c00caa6da1bbc9a47126558beafcefa02266ec0d01d1cc10751e
bound_set_digest: 4e6c975f794696066a25abe4ee827594afa18f8fac8bfb5e7bf31d43508b3c2f
decided_at_head: 8923aab2188b5de7eb7a8c5fc282cde636ca969a
contract_blob: 899689fccdf7bed1705e927e2745ad839dc63875
job_id: review-mtn25kq7-vv0bgv
job_class: review
base: 48243cd2e07c1357a389e670cf2f23af479d1595
scope: branch
prior_verdict: .omc/review/20260904-133500/verdict.md
completed_at_utc: 2026-09-04T14:52:00Z
operator_directive: 2026-09-04 「S-26 재심 재개」 (2026-08-30 정지 지시를 이 회차에 한해 해제)
```

**needs-attention · findings 1 (medium · 검사기 `tools/tos_completion_status.py:3948-3958` · 계약 본문 아님).**
S-26 항별 독립 측정(Codex 자체 실행): ② **불성립**(이 판에 material 1) · ③ 성립(validator rc 0) · ④ 성립(CUR/CIT/VER/CARD/RULE 0) ·
⑤ 성립(self-test 145종 전건 판별 · 죽은 검사 0 · 역방향 과잉 차단 0) · ⑥ 성립(`48243cd2..HEAD` 두 결속 경로 이력·diff 공집합 · blob
899689fc/ec3464c0 불변) · 결속값 4종(head · plan_scope_digest · bound_set_digest · decided_at_head) 재계산 일치 · R-3 보존소 오염 없음 ·
ENTRY_OK · ⑧ 은 기존 교착 그대로(이 판의 종료 요구 아님). `--check` 재파생은 Codex 샌드박스에 임시 디렉터리가 없어 rc 2 로 미실행 —
오케스트레이터가 같은 HEAD 에서 직접 실행한 결과는 RESULT GREEN · ENTRY_OK 다(디스패치 전 실측).

## 수용검사 (오케스트레이터)

- **finding 1 채택.** `file:line` 실재(`_d1_u6prime_row_state` :3911-3961). 계약 U-6′ (ㄹ) 원문(:3194-3205)과 대조:
  (2) 「검사기 스캔 결과 — 후보 우주의 크기와 **스캔 범위**(파일 수 포함)」 — 구현은 `scope_desc` 인자를 받고서 **소비하지 않는다**
  (:3948-3953 은 «후보 우주» 토큰과 두 숫자의 존재만 본다). (4) 「독립 리뷰 기록의 **경로**」 — 구현은 `docs/reviews/d1-no-dependency/<site_id>/`
  **접두사**만 본다(:3956-3958). 둘 다 문언보다 검사가 약하다(fail-open). 현행 D0-5 값은 NONE 사이트 0 이라 불변이나 다음 NONE 사이트에서
  거짓 공시가 rc 0 을 얻는다. 비협상 규칙 배치 없음 · silenced 아님 · 변경 범위 안(C4 `7bf83226` 도입 코드).
- **처분 경로**: 검사기 + 테스트만 수정(권고 그대로) — `reason` 에 실제 `scope_desc`·`file_count` 를 결속하고 (4)는 실제 선택·검증한
  `verdict.md` 의 정확한 repo-relative 경로와 일치 요구; 범위 설명 삭제·다른 범위 대체·같은-prefix 부재 기록·최신 기록과 다른 경로를
  각각 red 로 고정하는 대조군 테스트 추가. **계약 본문 무접촉** → S-26 ⑥ 리셋 없음 · O-6 재결속 없음.
- **S-26 ② 카운터 귀결**: 직전 approve(#5 · 133500 · material 0)에 이어 이 판이 material 0 이었다면 ② 가 섰다. 이 판은 material 1 이므로
  **② 는 다시 0 에서 시작** — 수리 후 서로 다른 심판 잡 2회 연속 material 0 이 필요하다. ⑧(도달 가능성 교착 · 초안 1~6 기각)은 운영자
  결정 축으로 열려 있어 ②가 서도 종결 주장은 별개다.
- **착지 규율**: 이 needs-attention verdict 는 `docs/reviews/phase0-completion-contract/` 에 **단독으로 착지시키지 않는다** — R-3 은 그
  디렉터리의 사전순 마지막 verdict 를 읽으므로 단독 착지는 ENTRY_OK 를 깨뜨린다. 후속 approve 와 같은 커밋에 이력으로 착지한다(재심 #1~#4 선례).

---

## Codex 판정 (verbatim — 손대지 않음)

```
Target: branch diff against 48243cd2
Verdict: needs-attention

출하 보류. S-26 ② 불성립: 이번 독립 재심에서 신규 material finding 1건(medium)이 확인되어 material-0 2회 연속이 아니다. ③ 성립: 직전 판과 이번 판의 tos_contract_check가 rc 0이다. ④ 성립: 이번 validator는 CUR/CIT/VER/CARD/RULE 위반 0으로 PASS했다. ⑤ 성립: self-test rc 0, 145종 전건 판별·죽은 검사 0·역방향 과잉 차단 0이다. ⑥ 성립: 48243cd2..HEAD의 두 결속 경로 이력과 diff가 공집합이고 blob 899689fc/ec3464c0가 불변이다. 결속 HEAD·plan_scope_digest·bound_set_digest·decided_at_head도 제시값과 일치하며 R-3은 보존소에 오염되지 않고 ENTRY_OK를 냈다. ⑧은 기존대로 열린 교착이며 이번 판의 종료 요구가 아니다. 별도 상태 검사는 읽기 전용 실행환경에 임시 디렉터리가 없어 rc 2로 재파생 검증하지 못했지만, HEAD 생성물은 d0a_entry_state=ENTRY_OK 및 §11 상태를 보유한다.

Findings:
- [medium] U-6′ 검사기가 실제 스캔 범위와 독립 기록 경로가 빠진 공시 행을 승인한다 (tools/tos_completion_status.py:3948-3958)
  계약 §7.4 U-6′은 reason에 후보 우주 크기와 실제 스캔 범위(파일 수 포함), 그리고 사용한 D-4 독립 리뷰 기록의 경로를 요구한다. 그러나 구현은 '후보 우주'와 두 숫자가 어디엔가 나타나는지만 확인하고 scope_desc를 전혀 소비하지 않으며, 기록도 site_id 디렉터리 접두사만 찾는다. 직접 호출에서 실제 범위 문자열을 완전히 생략하고 임의의 미래 verdict 경로를 적은 행도 ok=True가 됐다. 이후 기록 검증은 별도로 최신 verdict를 선택하므로 reason이 가리킨 기록과 실제 승인 기록이 달라도 통과할 수 있다. 현재 NONE 사이트가 0이라 현행 D0-5 값은 바뀌지 않지만, 다음 NONE 사이트에서는 불완전하거나 거짓인 감사 공시가 rc 0과 NO_DEPENDENCY를 얻어 C4~C6이 구현했다고 주장한 동결 계약과 갈린다.
  Recommendation: 계약 본문은 편집하지 말고 검사기를 고쳐 reason에 정확한 scope_desc와 file_count를 결속하고, (4)는 실제 선택·검증한 verdict.md의 정확한 repo-relative 경로와 일치시키라. 범위 설명 삭제·다른 범위 대체·존재하지 않는 같은-prefix 기록·최신 기록과 다른 경로를 각각 red로 만드는 테스트를 추가하라.

Next steps:
- tools/tos_completion_status.py와 관련 테스트만 수정해 U-6′ reason의 스캔 범위 및 실제 기록 경로를 정확 결속한다.
- 수정 후 tos_contract_check, 145종 self-test, tos_completion_status.py --check를 쓰기 가능한 임시 디렉터리가 있는 환경에서 다시 실행한다.
- 도구 수정은 결속된 두 계획 경로를 건드리지 않으므로 계약 편집·S-26 ⑥ 리셋·O-6 재결속 없이 처분할 수 있다.
```

원문 전체·실행 로그: `.omc/review/20260904-233516/codex-wait.out` · 잡 메타 `codex-result.json` · 디스패치 focus `focus.txt` ·
결속 포착 `revision.txt` · 증거 `evidence/commits.txt`, `evidence/scope-diff.patch`.
