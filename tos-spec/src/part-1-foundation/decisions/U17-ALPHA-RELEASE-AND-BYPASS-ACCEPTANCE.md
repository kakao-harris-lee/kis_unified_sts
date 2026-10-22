# U-17 α 연속성 해제 · 09-02 관리자 우회 창 수용 — 운영자 결정 기록

> **Document class**: 비규범 결정 기록(운영자 처분의 축자 전사). 계약
> `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md` §12.3.4 U-17 을 개정하지 않으며,
> `tools/u17-verify.sh` 의 판정 논리·출력값을 바꾸지 않는다. 형식은 `U17-B2-DEVIATION-ACCEPTANCE.md`
> (2026-09-02) 선례를 따른다.

```yaml
decision:
  - U17_ALPHA_CONTINUITY_RELEASED_AFTER_OPERATOR_REVIEW
  - U17_PRE_LANDING_BYPASS_WINDOW_ACCEPTED
authority: 운영자 (this repository's corpus owner)
decided_on: 2026-10-22
instruction_verbatim: "U-17 α 해제하고 우회 창은 수용해"
basis_record: docs/reviews/phase0-completion-contract/20261021-223338/PHASE0-COMPLETION-DECISION.md   # «서명 전 열린 항목» 2
scope:
  alpha_release:
    ruleset_id: 21886181
    history_version: 48823346                       # updated_at(이력) 2026-09-07T00:21:13.825+09:00
    resource_updated_at: "2026-09-06T15:21:13.608000+00:00"   # u17-verify 가 읽는 값
    change: 'required_status_checks 에 {"context": "ruff", "integration_id": 15368} 추가 — 그 외 상태 동일'
  bypass_window_acceptance:
    ruleset_id: 21886181
    added_in: 48411657                              # 2026-09-02T17:57:36.774+09:00 · bypass_actors=[{actor_id:5, RepositoryRole, always}]
    removed_in: 48411683                            # 2026-09-02T17:57:40.797+09:00 · bypass_actors=[]
    landing_pr: 638                                 # mergedAt 2026-09-02T08:57:41Z · merge f49c3728
machine_state_after_this_record: PREVENTION_UNVERIFIED_REVISION   # 불변 — 아래 «효력»
```

## 결정 내용

1. **α 연속성 해제.** 운영자는 룰셋 `21886181` 의 착지 후 변경(버전 `48823346`)을 **정책 강화**로 확인하고, 그로
   인한 `PREVENTION_CONTINUITY_UNVERIFIABLE` 발화를 계약이 정한 «운영자 재심사 경로»(계약 `:8721`)로 해제한다.
   - 근거 관측(2026-10-22, `GET rulesets/21886181/history` · `history/<version>`): `t_land`(`2026-09-02T08:57:41Z`)
     뒤 버전은 `48823346` 하나뿐이고, 직전 버전 `48411683` 대비 차이는 필수 체크 `ruff` 추가 한 항목이다.
     `48823346` 은 `enforcement: active` · `bypass_actors: []` · 대상 `refs/heads/main`.
   - 계약 문언의 «감사 로그»(org/enterprise 소관)가 아니라 룰셋 버전 이력을 근거로 썼다. 운영자는 그 차이를 알고 해제했다.
2. **09-02 관리자 우회 창 수용.** 운영자는 PR #638 머지(`mergedAt 2026-09-02T08:57:41Z`) 직전 약 4초
   (`08:57:36.774Z`~`08:57:40.797Z`) 동안 저장소 역할 `actor_id 5` 에 `bypass_mode: always` 가 걸려 있었던 사실을
   알고, 그것이 `U17-B2-DEVIATION-ACCEPTANCE.md` 의 (b)② 수용을 무효로 만들지 않는다고 판단한다.
   - 머지 요청이 우회 창 안에서 일어났는지는 이력(초 단위 `mergedAt`)만으로 정해지지 않으며, 이 기록도 정하지 않는다.
   - 이 사실은 2026-10-21 재판정 리뷰에서 처음 드러났다 — 그 전 기록에는 없었다.

## 효력 (정직하게)

1. **기계 상태는 바뀌지 않는다.** `bash tools/u17-verify.sh` 는 이 기록 뒤에도 α 발화를 내고
   `prevention_control_state=PREVENTION_UNVERIFIED_REVISION` 을 방출한다. 룰셋의 서버 타임스탬프는 소급되지 않는다.
2. **소비처는 «완료 판단»(사람)뿐이다.** 완료 판단자는 live 평가 결과와 이 기록, `U17-B2-DEVIATION-ACCEPTANCE.md`
   를 함께 읽는다.
3. **범위 한정.** 해제는 버전 `48823346` 에만, 수용은 위 우회 창(`48411657`→`48411683`)에만 적용된다. 룰셋이 다시
   바뀌면 α 는 다시 발화하고, 그때 운영자 결정이 별도로 필요하다.
4. **계약 개정도 countersign 도 아니다.** `D0A-PREVENTION-CONTROL.md` 의 `operator_countersign` 은 불변이다.

## 전사 주체

오케스트레이터가 운영자의 지시 문언을 그대로 옮겼다(`instruction_verbatim`). 결정의 권위는 운영자에게 있다.
