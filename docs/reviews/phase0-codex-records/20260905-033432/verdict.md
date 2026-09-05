# 레인 B 계획 «재심» — S-26 ② 재개 2회차 (finding 1 처분 후 · 계약 편집 없음) · needs-attention (head fbb1a364)

```yaml
adjudicator: codex
verdict: needs-attention
reviewed_at_head: fbb1a36461161683887451fbacbc8dc518a918dd
reviewed_plan_paths:
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
reviewed_scope_digest: 41d967596b4c4757ada5ddb73945eff6199184659586043a22c0406f230313e7
bound_set_digest: 4e6c975f794696066a25abe4ee827594afa18f8fac8bfb5e7bf31d43508b3c2f
decided_at_head: 8923aab2188b5de7eb7a8c5fc282cde636ca969a
contract_blob: 899689fccdf7bed1705e927e2745ad839dc63875
job_id: review-mtnao2oh-wio0nf
job_class: review
base: 48243cd2e07c1357a389e670cf2f23af479d1595
scope: branch
prior_verdict: .omc/review/20260904-233516/verdict.md
completed_at_utc: 2026-09-04T18:41:00Z
operator_directive: 2026-09-04 「S-26 재심 재개」
```

**needs-attention · findings 1 (medium · 검사기 `tools/tos_completion_status.py:3961-3971` · 계약 본문 아님).**
직전 finding 1 = **«부분 해소»** — 단일 stamp 선택·공유는 고쳐졌으나 reason 검사가 비구조적 부분문자열 대조라, 기대 scope 를 무관한
문맥에 두고 실제 공시는 다른 범위를 적어도, 선택 경로 뒤에 접미를 붙여도 `True` 가 난다.
S-26 항별(Codex 독립 측정): ① 성립(결속 문서 이력 공집합 · blob 899689fc/ec3464c0) · **② 불성립 0/2**(이 판 material 1) · ③ 성립(validator rc 0) ·
④ 성립(CUR/CIT/VER/CARD/RULE 0) · ⑤ 성립(self-test 145종 · 죽은 검사 0 · 역방향 과잉 차단 0) · ⑥ 성립(계약 편집 없음) · 결속값 4종 재계산 일치 ·
⑧ 교착 그대로(이 판의 종료 요구 아님). `--check` 는 샌드박스 임시 디렉터리 부재로 rc 2 → HEAD 생성물에서 ENTRY_OK · D0-5 두 행 `VALUED+BLOCKED` 대체 확인
(오케스트레이터 직접 실행은 RESULT GREEN · ENTRY_OK).
부수 판정(채택): 93f4f6bd(UNCHK-024 키 등록)는 동결 계약을 stale 로 만들지 않는다 — :2974-2979 「UNCHK-024 무영향」은 당시 D-3/D-4 변경의
무영향 기록으로 S-12 정합 · §11 은 키별 BLOCKED 를 완료 처분 어휘로 허용. `tos_spec_status` 의 163/16→164/17 경고는 비정본 기준선 경고라
non-blocking 이 정합하며 결속 계획 편집은 권고하지 않는다(편집 시 ⑥ 리셋·O-6 재결속·재심 2회 비용).

## 수용검사 (오케스트레이터)

- **finding 1 채택.** `file:line` 실재(fbb1a364 의 `_d1_u6prime_row_state` (2)(4) 조건). 계약 U-6′ (ㄹ) 는 넷을 «적는다»고만 하고 reason 의
  문법을 못박지 않으므로, 권고대로 **검사기 층에서 구획 문법을 정의해 구조 파싱**한다(계약 무접촉 → S-26 ⑥ 리셋 없음 · O-6 재결속 없음).
  비협상 규칙 배치 없음 · silenced 아님 · 변경 범위 안. 실코퍼스 NONE 사이트 0 → 현행 D0-5 값·생성물 불변.
- **S-26 ② 카운터**: 0/2. 수리 후 서로 다른 심판 잡 2회 연속 material 0 이 필요하다. ⑧ 은 운영자 결정 축으로 열려 있다.
- **착지 규율**: 이 needs-attention verdict 는 `docs/reviews/phase0-completion-contract/` 에 단독 착지시키지 않는다(R-3 은 사전순 마지막 verdict 를
  읽는다). 후속 approve 와 같은 커밋에 이력으로 착지한다(직전 판 20260904-233516 도 동일).

---

## Codex 판정 (verbatim — 손대지 않음)

```
Target: branch diff against 48243cd2
Verdict: needs-attention

출하 보류. 직전 finding 1은 «부분 해소»: 단일 stamp 선택·공유는 고쳐졌지만 reason 검사가 여전히 비구조적 부분문자열 대조라 허위 scope·경로가 통과한다. S-26 ① 성립(결속 문서 이력 공집합, blobs 899689fc/ec3464c0) · ② 불성립, 0/2(이번 판 material 1) · ③ 성립(contract validator rc 0) · ④ 성립(CUR/CIT/VER/CARD/RULE 0) · ⑤ 성립(self-test rc 0, 145종 전건 판별·죽은 검사 0·역방향 과잉 차단 0) · ⑥ 성립(계약 편집·리셋 없음). 결속 HEAD·scope digest·bound digest·decided_at_head도 일치했다. ⑧은 기존 교착 그대로이며 이번 판의 종료 요구가 아니다. completion-status --check는 임시 디렉터리 부재로 rc 2였고 HEAD 생성물에서 ENTRY_OK와 두 D0-5 VALUED+BLOCKED 행을 대체 확인했다. 93f4f6bd는 동결 계약을 stale로 만들지 않는다: UNCHK-024 문장은 당시 D-3/D-4 변경의 무영향 기록으로 S-12와 정합하고, §11은 키별 BLOCKED를 완료 처분 어휘로 허용한다. spec-status rc 0의 163/16→164/17 경고도 비정본 기준선 경고라 non-blocking이다.

Findings:
- [medium] U-6′ reason의 scope와 기록 경로를 다른 문맥에 숨겨도 통과한다 (tools/tos_completion_status.py:3961-3971)
  검사는 scope_desc와 record_path가 reason 어디엔가 부분문자열로 존재하는지만 본다. 직접 대조군에서 실제 공시는 `other_pkg 1개 파일 스캔`으로 쓰고 기대 scope `d1_none_pkg`는 무관한 주석에 넣었으며, 선택된 경로 뒤에 `.not-the-selected-record`를 붙였는데도 함수가 `True`를 반환했다. 이후 기록 검증은 실제 stamp_dir의 verdict.md를 열므로 전체 파이프라인도 허위 공시와 유효 기록을 조합해 NO_DEPENDENCY를 얻을 수 있다. 이는 U-6′ (ㄹ)(2)의 실제 스캔 결과와 (4)의 선택된 기록 경로 결속을 아직 우회한다.
  Recommendation: 계약은 편집하지 말고 reason의 정해진 구획을 구조적으로 파싱하라. 후보 우주·scope·file_count를 하나의 스캔 결과 구획에서 정확히 대조하고, `독립 리뷰 기록:` 값은 구획 전체가 record_path와 같게 검증하라. 기대 scope를 다른 구획에 둔 경우와 `verdict.md` 뒤에 suffix를 붙인 경우가 red인 통합 대조군을 추가하라.

Next steps:
- tools/tos_completion_status.py와 관련 테스트만 수정해 남은 부분문자열 fail-open을 닫는다.
- 수정 후 contract validator, 145종 self-test, focused U-6′ 대조군, completion-status --check를 쓰기 가능한 임시 디렉터리 환경에서 다시 실행한다.
- 163/16 기준선 경고를 닫기 위한 결속 계획 편집은 권고하지 않는다. 편집한다면 S-26 ⑥ 리셋, O-6 재결속, 독립 재심 2회 비용이 발생한다.
```

원문·실행 로그: `.omc/review/20260905-033432/codex-wait.out` · `codex-result.json` · `focus.txt` · `revision.txt` · `evidence/`.
