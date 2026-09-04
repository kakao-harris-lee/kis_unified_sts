# Phase 0 완료 판정 — 결정 기록 (운영자 countersign 기입 · 2026-09-04)

> **Document class**: 완료 판단 **결정 기록**(운영자 서명). 이 기록이 담는 것은 «계약 §11 종료 조건이
> 판정 대상 head 에서 충족됐다» 는 운영자 판단 하나다. 기계 상태(`prevention_control_state`·
> `d0a_entry_state`·§11 overview)·계약·상위 계획·`tos-spec/`·`tools/` 는 이 기록으로 바뀌지 않으며,
> G1~G3 를 부여하지 않고 `restricted_live`/`production` `NOT_AUTHORIZED` 는 불변이다. 초안 단계
> (`decision: PENDING_OPERATOR_COUNTERSIGN`)는 커밋 `b99be174` 에 이력으로 남아 있다.

```yaml
decision: PHASE0_SECTION11_COMPLETE_ACCEPTED_AT_JUDGMENT
judged_head: d07646c2923784e90ace718d98511a80c2d2fef7
measurement_record: docs/reviews/phase0-completion-contract/20260904-171004/PHASE0-COMPLETION-JUDGMENT-LIVE.md
decided_on: 2026-09-04
authority: 운영자 (this repository's corpus owner)
operator_countersign: "chihun,lee 2026-09-04T08:26:30Z"   # 계약 :8637 형식 · D0A-PREVENTION-CONTROL.md 와 같은 식별자 표기
```

`operator_countersign`의 형식·자리표시자 문언은
`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:8637`
(`operator_countersign: "<운영자 식별> <ISO-8601 UTC>"   # 예: "operator 2026-08-19T00:00:00Z"`)
에서 그대로 옮긴 것이다(`grep -n "operator_countersign:" docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`
재확인).

---

## §11 조건표 — 측정값과 출처

각 행은 측정 기록(`PHASE0-COMPLETION-JUDGMENT-LIVE.md`, 위 `measurement_record`)의 해당
줄을 가리킨다. 이 표는 그 파일이 이미 인용한 생성물(`tos-spec/src/TOS-COMPLETION-STATUS.md`)의
값을 다시 옮긴 것이며, 별도로 재판정하지 않는다.

| 계약 §11 항 | 측정값 | 측정 기록 출처 |
| --- | --- | --- |
| `K-1` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:163` |
| `K-2` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:164` |
| `K-3` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:165` |
| `K-4` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:166` |
| `K-5/FWD-METRICS` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:167` |
| `K-6` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:168` |
| `K-9` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:169` |
| `K-11` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:170` |
| `K-12` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:171` |
| `K-13` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:172` |
| `K-14` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:173` |
| `U-14` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:174` |
| `U-12` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:175` |
| `U-13` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:176` |
| `U-15` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:177` |
| `U-16` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:178` |
| `U-1a` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:179` |
| `U-4` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:180` |
| `U-5` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:181` |
| `U-8` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:182` |
| `U-9` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:183` |
| `D0-1` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:184` |
| `A-1` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:185` |
| `A-2` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:186` |
| `A-3` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:187` |
| `D-1` | `MET` | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:188` |
| `D0-5` | `MET`(7/7 판정 · 5 UNBOUND · resolver/marketfeed `VALUED+UNBOUND`) | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:189`(생성물 표기) · 하위 셀 근거는 `:113-119`(§2 `--check` 출력) |
| `U-17` | 생성물 자신은 미평가(「requires a live evaluation at completion-judgment time」) — 그 평가가 §1이다: **`prevention_control_state=PREVENTION_UNVERIFIED_REVISION`**, 사유 `(b)② d=28475ca1… head=21c47e42… check-run 100181808552 failure`. 이 삼중값은 `U17-B2-DEVIATION-ACCEPTANCE.md`의 `scope:`와 일치하며, 그 문서는 이 편차를 「완료 판단 시점에 수용」 처분했다(범위 한정). α·β 두 축은 통과. **기계 상태 자체는 MET이 아니다 — 수용은 사람의 처분이지 상태값의 변경이 아니다.** | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:190`(생성물 문언) · `:53-58`(fire/reason/rc 전사) · `:64-68`((b)② 삼중값-scope 일치 진술) |
| `RES-1` | `MET`(checker 파생 제외 목록 — `STATE-EV-004`가 `FWD-a` 종료조건에서 U-13-e 근거로 제외) | `PHASE0-COMPLETION-JUDGMENT-LIVE.md:191` |

---

## 표준 이탈(standing deviation) 두 건 — §11과 별도 축

이 결정 초안은 아래 두 이탈을 **§11 표의 값을 바꾸지 않고** 별도로 명시한다. 계약 §11.1이
정한 대로, §11(종료 조건)과 계약 자신의 종결 자격(S-26)은 별개 축이며, 이 두 이탈 중 하나는
전자(U-17 (b)②의 편차 수용), 하나는 후자(S-26 미충족)에 속한다.

1. **U-17 (b)② 편차 — 운영자 완료 판단 시점 수용**: 근거
   `tos-spec/src/part-1-foundation/decisions/U17-B2-DEVIATION-ACCEPTANCE.md`
   (`decision: U17_B2_DEVIATION_ACCEPTED_AT_COMPLETION_JUDGMENT`, `decided_on: 2026-09-02`,
   `authority: 운영자`). 그 문서 자신이 명시하는 대로 (i) 기계 상태는 이 수용으로 바뀌지
   않는다 — `tools/u17-verify.sh`는 이 기록 이후에도 `PREVENTION_UNVERIFIED_REVISION`을
   낸다. (ii) 이 수용의 소비처는 완료 판단(사람)뿐이다. (iii) 계약 개정이 아니다. (iv)
   `D0A-PREVENTION-CONTROL.md`의 `operator_countersign`과는 별개다 — 그 서명은 불변이며
   이 결정의 `operator_countersign`(위 yaml)과는 다른 서명이다. 범위는 `scope:`에 기재된
   `d=28475ca1…`/`landing_head=21c47e42…`/`check_run_id=100181808552` 삼중값에 **한정**되며,
   이 측정 기록(§1)의 live 실측이 정확히 같은 삼중값을 재확인했다.

2. **S-26 계약-종결 자격 — 미충족(별개 축, §11.1)**: 계약 §11.1은 §11 표를 만족해도 계약
   자신의 «종결»(S-26)은 자동으로 성립하지 않는다고 명시한다(`§11.1 은 포인터일 뿐 —
   S-26 이 유일 정본`). 측정 기록 §6이 진술하듯 (a) 계약 blob 최종 편집(`8923aab2`) 이후
   material-0 독립 재심은 1건(`20260904-133500`)뿐이라 S-26 ②의 «연속 2회» 요건이
   미충족이고, (b) S-26 ⑤·⑧은 계약 본문에 열린 상태로 남아 있다. 따라서 계약은 아직
   «종결»을 주장할 수 없다 — **이 사실은 §11 Phase 0 종료 조건의 충족 여부와는 무관한
   별개 축**이며, 이 결정 초안이 Phase 0 §11 완료를 다루는 것을 막지 않는다(계약
   §11.1이 그 분리를 명시적으로 허용한다).

---

## 효력

이 결정은 위 yaml 의 `operator_countersign` 이 실제 식별값과 ISO-8601 UTC 시각으로 기입되고
그 변경이 커밋된 시점(운영자 지시 2026-09-04 «countersign 기입 후 커밋»)에 발효했다. 발효의
범위는 «판정 대상 head `d07646c2` 에서 계약 §11 종료 조건이 충족됐다는 운영자 판단» 이다.
발효가 바꾸지 «않는» 것: 기계 상태(`tools/u17-verify.sh` 는 여전히
`PREVENTION_UNVERIFIED_REVISION` 을 내고 `--check` 의 상태값은 그대로다) · 계약 S-26 종결 자격
(미충족 · 별개 축) · G1~G3 · `restricted_live`/`production` 권한. 초안 단계의 문면은 커밋
`b99be174` 에 이력으로 보존된다.
