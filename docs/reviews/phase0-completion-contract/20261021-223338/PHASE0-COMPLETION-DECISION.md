# Phase 0 완료 판정 — 결정 기록 (재기록 초안 · 운영자 countersign 대기 · 2026-10-21 작성 · 10-22 갱신)

> **Document class**: 완료 판단 **결정 기록 초안**. 서명 전에는 아무 효력이 없다. 이 기록이 담으려는
> 것은 «계약 §11 종료 조건이 판정 대상 head `371051f4` 에서 충족됐다» 는 운영자 판단 하나다.
> 기계 상태·계약·상위 계획·`tos-spec/`·`tools/` 는 이 기록으로 바뀌지 않으며, G1~G3 를 부여하지
> 않고 `restricted_live`/`production` `NOT_AUTHORIZED` 는 불변이다.
>
> 직전 결정 `docs/reviews/phase0-completion-contract/20260904-171004/PHASE0-COMPLETION-DECISION.md`
> (`PHASE0_SECTION11_COMPLETE_ACCEPTED_AT_JUDGMENT`, `judged_head: d07646c2`)는 그 head 에만
> 결속된다. 그 뒤 계약이 편집됐으므로(에라타 57·58차, 2026-09-05) 현행 계약에 대한 판단은 이 기록이
> 따로 담는다. 직전 결정은 이 기록으로 철회되거나 바뀌지 않는다.
>
> 이력: 초판(10-21)은 `b15069fd` 를 판정 대상으로 썼고 그 측정이 레인 A 재심 #7 의 high finding 을
> 드러냈다(`20261021-223338/PHASE0-COMPLETION-JUDGMENT-LIVE.md`). 수정 PR #910 이 착지한 `371051f4`
> 를 다시 재어 판정 대상을 옮겼다(`20261021-235425/PHASE0-COMPLETION-JUDGMENT-LIVE.md`).

```yaml
decision: PENDING_OPERATOR_COUNTERSIGN
judged_head: 371051f478583f5bab0d5bed2f02df2facdde22f
contract_blob: 6f94dfbbafd48fa3d1b4c73266fdfda19da9bce5
bound_set_digest: 045f3ae7565860df6e0c38d3c7ee49c76f3a4d3784d646279cd1be2727dbb429
expected_code_digest: ba1de6b28ef1d961b3e77de1c65eef490efaac284041d8ee6c0f42261fd41b6e
measurement_record: docs/reviews/phase0-completion-contract/20261021-235425/PHASE0-COMPLETION-JUDGMENT-LIVE.md
superseded_measurement_record: docs/reviews/phase0-completion-contract/20261021-223338/PHASE0-COMPLETION-JUDGMENT-LIVE.md   # b15069fd · 레인 A #7 증거로 보존
lane_a_record: docs/reviews/phase0-codex-records/20261021-232321/verdict.md   # 재심 #8 · approve
prior_decision: docs/reviews/phase0-completion-contract/20260904-171004/PHASE0-COMPLETION-DECISION.md
drafted_on: 2026-10-21
authority: 운영자 (this repository's corpus owner)
operator_countersign: ""   # 계약 :8738 형식(blob 6f94dfbb · grep -n '^operator_countersign: "<' 로 재확인 — 1건) "<운영자 식별> <ISO-8601 UTC>" — 아래 «서명 전 열린 항목» 처분 뒤에만 기입
```

---

## §11 조건표 — 측정값과 출처

각 행은 측정 기록(`measurement_record`)의 해당 절을 가리킨다. 재판정하지 않는다.

| 계약 §11 항 | 측정값 | 측정 기록 출처 |
| --- | --- | --- |
| `K-1`~`K-14` (11항) | 전부 `MET` | §2 (생성물 `TOS-COMPLETION-STATUS.md:118-128`) |
| `U-14` · `U-12` · `U-13` · `U-15` · `U-16` · `U-1a` · `U-4` · `U-5` · `U-8` · `U-9` | 전부 `MET` | §2 (`:129-138`) |
| `D0-1` · `A-1` · `A-2` · `A-3` · `D-1` | 전부 `MET` | §2 (`:139-143`) |
| `D0-5` | `MET` — 7/7 판정, resolver·marketfeed `VALUED` | §2 (`:144`, `completion-check.log:14-37`) |
| `RES-1` | `MET` — `STATE-EV-004` 가 U-13-e 근거로 FWD-a 에서 제외 | §2 (`:146`) |
| `U-17` | 기계 상태 `PREVENTION_UNVERIFIED_REVISION` — **MET 아님**. 발화 2건: (b)② 삼중값(직전 수용 범위와 일치) + **α 연속성 `PREVENTION_CONTINUITY_UNVERIFIABLE`(수용 범위 밖)** | §1 (`u17-live.log:239-245`) |
| §11 추가 — `tos/tests` 전량 green | 9,657 · rc 0 | §3 |
| §11 추가 — ruff 0 · black/mypy 기준선 무증가 | ruff 0 · black 0(26.1.0) · mypy 0 | §3 |
| §11 추가 — `tos_spec_status.py --check` | PASS | §3 |
| §12.3 절차표 9행 — 레인 A | **`approve` · findings 0** (재심 #8, `reviewed_at_head` `9c6e15e6` — `judged_head` 와 트리 동일) | §5 |

---

## 서명 전 열린 항목

### 1. 레인 A high finding — **닫힘 (2026-10-22)**

재심 #7 의 high(`tos/src/tos/position/predicates.py:131-140`, 끝나지 않은 결과 뒤 남은 노출 소실)는 PR #910 이
고쳤다 — 커널 술어와, 손실 맵을 만들던 유일한 생산자인 런타임 리더(`tos_runtime/riskstate/position.py`)를 함께
바꿨고 `expected_code_digest` 를 `b06d01f9…` 에서 `ba1de6b2…` 로 재도출했다.

- 레인 A 재심 #8(운영자 범위·비용 승인 · 범위 = 커널 경로 + 런타임 리더·그 테스트·digest 파일): `approve` ·
  findings 0 · 「Resolved.」(`lane_a_record`).
- 결속: `git diff 9c6e15e6 371051f4` 공집합 — 재심 #8 의 approve 가 `judged_head` 의 트리에 결속된다
  (측정 기록 §5).
- 이 PR 범위 밖으로 남긴 같은 클래스의 잔여는 이슈 #911(`RESULT_UNMATCHED` 버킷)·#912(종결 뒤 늦은 체결)로
  분리했다. 둘 다 레인 A 재심 #8 이 판정한 대상이 아니다.

### 2. U-17 α 연속성 발화 (운영자 처분 필요 — 서명을 막는다)

계약은 이 발화를 «차단이되 운영자 재심사 경로»로 정한다 — 「정당한 정책 강화는 운영자가 감사 로그로 확인해
해제(재심사)한다」(계약 `:8721-8725`). `U17-B2-DEVIATION-ACCEPTANCE.md` 의 수용은 (b)② 삼중값에 **한정**
되므로(`:51`) 이 발화를 덮지 않는다.

**관측 (2026-10-22 · GitHub 룰셋 이력 API · GET 만)** — 처분 판단의 재료이며 처분이 아니다:

- `GET repos/kakao-harris-lee/kis_unified_sts/rulesets/21886181/history` → 버전 5개. `t_land`
  (`2026-09-02T08:57:41Z`) 뒤 버전은 `48823346`(`2026-09-07T00:21:13.825+09:00`) **하나뿐**, 직전은
  `48411683`(`2026-09-02T17:57:40.797+09:00`). 작성자 모두 User `130432481`.
- 두 버전 `.state` 비교: 차이는 필수 상태 체크 배열에 `{"context": "ruff", "integration_id": 15368}` 추가 **한 항목뿐**.
- `48823346` 상태: `enforcement: active` · `bypass_actors: []` · 대상 `refs/heads/main`.
- `t_land` 뒤 버전이 하나라 off→on 토글(두 버전을 만든다)은 이력에 없다.
- 한계: 계약 문언의 «감사 로그»(org/enterprise 소관)가 아니라 룰셋 버전 이력이다. 룰셋을 바꾸지 않는 우회는
  여기에 보이지 않는다 — 계약 (β)·`UNCHK-008` 의 기존 경계이며 이 처분으로 새로 생기지 않는다.
- 처분 선택지(운영자): (a) 위 관측을 근거로 재심사 기록을 남겨 해제 · (b) 해제하지 않음(이 초안은 서명 불가로 남는다).
  이 초안은 어느 쪽도 선언하지 않는다.

### 3. S-26 (별개 축 — 서명을 막지 않는다)

계약 §11.1 이 §11 과 S-26 을 분리한다. 측정 기록 §6: 계약 편집·신규 재심 0, ⑤·⑧ 열림. 계약은 «종결»을
주장할 수 없으며, 그 사실은 §11 완료 판단을 막지 않는다(직전 결정과 같은 처리).

---

## 표준 이탈(standing deviation)

1. **U-17 (b)② 편차** — 직전 결정과 같은 수용(`U17-B2-DEVIATION-ACCEPTANCE.md`, 2026-09-02)이
   그대로 적용된다. 측정 기록 §1 이 같은 삼중값(`28475ca1…` / `21c47e42…` / `100181808552`)을
   재확인했다. 기계 상태는 수용으로 바뀌지 않는다.
2. **S-26 미충족** — 위 3.

## 측정 환경 부기

이 호스트의 `gh 2.45.0` 으로는 U-17 live 가 항상 `PREVENTION_UNVERIFIABLE` 로 나온다(`--slurp` 미지원).
`yq` 도 없다. 측정은 스크래치 전용 standalone 바이너리(gh 2.63.2 · yq v4.48.1)로 했다(측정 기록 §0). 서명
시점에 U-17 을 다시 잴 때 같은 전제가 필요하다.

## 효력

`decision` 이 `PHASE0_SECTION11_COMPLETE_ACCEPTED_AT_JUDGMENT` 로 바뀌고 `operator_countersign` 이 실제
식별값·ISO-8601 UTC 시각으로 기입돼 커밋된 시점에만 발효한다. 서명 전 main 이 `judged_head` 에서 진행하면
(특히 `tos/`·`tools/`·`tos-spec/`·`.github/` 변경) 결속을 다시 확인한다. 발효가 바꾸지 «않는» 것: 기계
상태 · 계약 S-26 종결 자격 · G1~G3 · `restricted_live`/`production` 권한 · 직전 결정(`d07646c2`).
