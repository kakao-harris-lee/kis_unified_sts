# U-17 (b)② 편차 수용 — 운영자 결정 기록

> **Document class**: 비규범 결정 기록(운영자 처분의 축자 전사). 계약
> `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md` §12.3.4 U-17 을
> 개정하지 않으며, `tools/u17-verify.sh` 의 판정 논리·출력값을 바꾸지 않는다.
> `D0A-PREVENTION-CONTROL.md` 의 `operator_countersign` 은 실행기가 «정확히 1회»로
> 강제하는 서명이라 이 기록은 그 파일에 손대지 않는다.

```yaml
decision: U17_B2_DEVIATION_ACCEPTED_AT_COMPLETION_JUDGMENT
authority: 운영자 (this repository's corpus owner)
decided_on: 2026-09-02
instruction_verbatim: "U-17 (b)② 완료 판단 시점 수용으로 처분해줘"
basis_record: docs/reviews/phase0-completion-contract/20260902-215717/U17-PREVENTION-CHECK-V222-ADDENDUM-7.md
scope:
  d: 28475ca1ca82fe99054a2cc04cf1b58e4550097a          # D0A-FIRST (config/tos_completion.yaml 도입 커밋)
  landing_pr: 638
  landing_head: 21c47e42ff1487282ce2f9da0df11756ff146a3a
  check_run_id: 100181808552                             # tos-gate · conclusion=failure
  repaired_by: d56785ab                                  # PR #639 병합 커밋 (§12.3.4-R 재핀 · 하니스 sha 059e13f2…)
  independent_readjudication: docs/reviews/phase0-completion-contract/20260902-195656/verdict.md
machine_state_after_this_record: PREVENTION_UNVERIFIED_REVISION   # 불변 — 아래 «효력» 참조
```

## 결정 내용

운영자는 U-17 (b)② «4단계 ∀-success» 의 다음 편차를 **완료 판단 시점에 수용**한다.

- 편차: D0A-FIRST `28475ca1` 의 착지 PR #638 head `21c47e42` 위 `tos-gate` check-run
  `100181808552` 이 `failure` 로 기록돼 있어, (b)② 가 요구하는 «현행 집합 C 전부 success»
  가 그 head 에 대해 영구히 성립하지 않는다.
- 원인: 그 run 은 수정 전 하니스(sha `1817c9ef…`)로 실행됐고, 그 하니스는 gawk 에서
  `yaml_list` 의 awk 조기 `exit` → printf EPIPE → `pipefail` 로 `HARNESS_ABORTED` 를 냈다
  («awk 구현이 판정을 결정»하는 결정성 결함).
- 수리: 계약 §12.3.4-R 재핀(PR #639, 병합 `d56785ab`) 으로 결함이 제거됐고, 같은 gawk
  러너에서 `tos-gate` 가 처음으로 통과했다(run `33623414512`). 수리는 Codex 레인 B 재심
  (`20260902-195656`, approve · findings 0)으로 독립 재승인됐다.
- 실측·계약 근거는 전부 `basis_record`(addendum-7)에 원문으로 있다 — 이 기록은 그것을
  재기술하지 않는다.

## 효력 (정직하게)

1. **기계 상태는 바뀌지 않는다.** `bash tools/u17-verify.sh` 는 이 기록 뒤에도
   `prevention_control_state=PREVENTION_UNVERIFIED_REVISION` 을 낸다. 계약 (b)② 에는
   α 와 달리 «운영자 재심사 경로» 조항이 없고, PR #638 head 의 서버 기록은 소급 변경되지
   않기 때문이다.
2. **이 기록의 소비처는 «완료 판단»(사람)뿐이다.** 생성물 `TOS-COMPLETION-STATUS.md` 의
   §11 U-17 행은 «완료 판정 시점의 live 평가가 필요하며 미평가는 미충족» 이라고 적고
   있다. 완료 판단자는 그 live 평가 결과(위 상태값)와 **이 기록을 함께** 읽고, (b)② 의
   이 편차를 «수정 전 하니스로 검증된 과거 착지 — 결함은 식별·수리·독립 재승인 완료»
   로 수용한다. 다른 편차·다른 리비전에는 적용되지 않는다(`scope` 한정).
3. **계약 개정이 아니다.** (b)② 의 범위·문언은 그대로다. 같은 형상이 다시 생기면 그때의
   운영자 결정이 별도로 필요하다.
4. **countersign 이 아니다.** `D0A-PREVENTION-CONTROL.md` 의 `operator_countersign` 은
   불변이며, 이 기록은 서명 형식을 흉내 내지 않는다.

## 전사 주체

오케스트레이터가 운영자의 지시 문언을 그대로 옮겼다(`instruction_verbatim`). 결정의
권위는 운영자에게 있고, 전사자는 판정 어휘를 저작하지 않았다.
