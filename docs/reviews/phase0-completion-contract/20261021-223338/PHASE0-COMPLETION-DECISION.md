# Phase 0 완료 판정 — 결정 기록 (재기록 초안 · 운영자 countersign 대기 · 2026-10-21)

> **Document class**: 완료 판단 **결정 기록 초안**. 서명 전에는 아무 효력이 없다. 이 기록이 담으려는
> 것은 «계약 §11 종료 조건이 판정 대상 head `b15069fd` 에서 충족됐다» 는 운영자 판단 하나다.
> 기계 상태·계약·상위 계획·`tos-spec/`·`tools/` 는 이 기록으로 바뀌지 않으며, G1~G3 를 부여하지
> 않고 `restricted_live`/`production` `NOT_AUTHORIZED` 는 불변이다.
>
> 직전 결정 `docs/reviews/phase0-completion-contract/20260904-171004/PHASE0-COMPLETION-DECISION.md`
> (`PHASE0_SECTION11_COMPLETE_ACCEPTED_AT_JUDGMENT`, `judged_head: d07646c2`)는 그 head 에만
> 결속된다. 그 뒤 계약이 편집됐으므로(에라타 57·58차, 2026-09-05) 현행 계약에 대한 판단은 이 기록이
> 따로 담는다. 직전 결정은 이 기록으로 철회되거나 바뀌지 않는다.

```yaml
decision: PENDING_OPERATOR_COUNTERSIGN
judged_head: b15069fd1737962d92766e73648b0c2128957d32
contract_blob: 6f94dfbbafd48fa3d1b4c73266fdfda19da9bce5
bound_set_digest: 045f3ae7565860df6e0c38d3c7ee49c76f3a4d3784d646279cd1be2727dbb429
measurement_record: docs/reviews/phase0-completion-contract/20261021-223338/PHASE0-COMPLETION-JUDGMENT-LIVE.md
lane_a_record: docs/reviews/phase0-codex-records/20261021-224521/verdict.md
prior_decision: docs/reviews/phase0-completion-contract/20260904-171004/PHASE0-COMPLETION-DECISION.md
drafted_on: 2026-10-21
authority: 운영자 (this repository's corpus owner)
operator_countersign: ""   # 계약 :8738 형식(blob 6f94dfbb · grep -n 'operator_countersign: "<' 로 재확인) "<운영자 식별> <ISO-8601 UTC>" — 아래 «서명 전 열린 항목» 처분 뒤에만 기입
```

---

## §11 조건표 — 측정값과 출처

각 행은 측정 기록(`measurement_record`)의 해당 절을 가리킨다. 재판정하지 않는다.

| 계약 §11 항 | 측정값 | 측정 기록 출처 |
| --- | --- | --- |
| `K-1`~`K-14` (11항) | 전부 `MET` | §2 (생성물 `status-doc.log:118-128`) |
| `U-14` · `U-12` · `U-13` · `U-15` · `U-16` · `U-1a` · `U-4` · `U-5` · `U-8` · `U-9` | 전부 `MET` | §2 (`:129-138`) |
| `D0-1` · `A-1` · `A-2` · `A-3` · `D-1` | 전부 `MET` | §2 (`:139-143`) |
| `D0-5` | `MET` — 7/7 판정, resolver·marketfeed 가 `VALUED+UNBOUND` → `VALUED` 로 바뀜 | §2 (`:144`, `completion-check.log:32,37`) |
| `RES-1` | `MET` — `STATE-EV-004` 가 U-13-e 근거로 FWD-a 에서 제외 | §2 (`:146`) |
| `U-17` | 기계 상태 `PREVENTION_UNVERIFIED_REVISION` — **MET 아님**. 발화 2건: (b)② 삼중값(직전 수용 범위와 일치) + **α 연속성 `PREVENTION_CONTINUITY_UNVERIFIABLE`(수용 범위 밖, 신규)** | §1 (`u17-live2.log:225-231`) |
| §11 추가 — `tos/tests` 전량 green | 9,616 · rc 0 | §3 |
| §11 추가 — ruff 0 · black/mypy 기준선 무증가 | ruff 0 · black 0(26.1.0) · mypy 0 | §3 |
| §11 추가 — `tos_spec_status.py --check` | PASS | §3 |
| §12.3 절차표 9행 — 레인 A | **`needs-attention` · high 1건** (재심 #7) | §5 |

---

## 서명 전 열린 항목 — 처분 없이는 서명할 수 없다

### 1. 레인 A high finding (차단)

`tos/src/tos/position/predicates.py:131-140` — 끝나지 않은 결과(ACK·TIMEOUT·UNKNOWN·부분 체결)도
`EGRESS_RESULT_CONSUMED` 로 기록되는데, 분류기는 그런 시도를 체결 수량만으로 확정 처리해 남은 수량을
미결·in-flight 노출에서 뺀다. 측정 기록 §5 의 수용검사로 코드 구조가 지적과 맞음을 확인했고, finding 은
기각되지 않았다. 레인 A 게이트는 `approve` 로만 열린다.

- 처분 경로: 커널 분류기 수정 PR(결과 종류와 `remaining_quantity` 를 분류에 넣고, 종결 전까지 남은
  수량을 미결·in-flight 에 유지, ACK·TIMEOUT·UNKNOWN·부분 체결 양방향 회귀 테스트) → 레인 A 재심 #8
  `approve` → 이 초안의 `judged_head`·측정 기록 갱신.
- 손실 맵(`consumed_by_attempt`, 체결 수량만)을 만드는 것은 런타임 리더
  `tos/runtime/src/tos_runtime/riskstate/position.py:280-289` 하나다 — `1e84ac14` 는 순수 술어만 커널로
  옮겼고 증거 읽기는 런타임에 남았다. 그래서 수정은 커널 술어와 런타임 리더 **둘 다**를 바꾼다.
- `tos/runtime` 은 레인 A 재심 #7 범위 밖이었다. 런타임 쪽 변경이 레인 A 를 거치지 않고 착지하지 않도록,
  **재심 #8 의 범위는 커널 경로 + 이 리더(`tos_runtime/riskstate/position.py`)와 그 테스트를 포함**한다.
- 이 경로는 리스크 한도 계산이라 CLAUDE.md 의 «되돌리기 어려운 경로» 에 들어간다 — 수정 PR 의 Codex
  리뷰는 운영자의 범위·비용 승인 대상이다.

### 2. U-17 α 연속성 발화 (운영자 처분 필요)

룰셋 `21886181` 이 `2026-09-06T15:21:13Z` 에 서버에서 수정돼 `t_land`(`2026-09-02T08:57:41Z`) 뒤가
됐다. 실행기는 이를 benign/malign 으로 가르지 못한다고 적고 「운영자 재심사 경로(영구 차단 아님)」로
분류한다. `U17-B2-DEVIATION-ACCEPTANCE.md` 의 수용은 (b)② 삼중값에 **한정**되므로 이 발화를 덮지 않는다.

- 처분 선택지(운영자): (a) 09-06 룰셋 변경 내용을 확인해 별도 수용 기록을 남김 · (b) 수용하지 않고
  보호 설정 연속성을 다시 세움. 이 초안은 어느 쪽도 선언하지 않는다.

### 3. S-26 (별개 축 — 서명을 막지 않는다)

계약 §11.1 이 §11 과 S-26 을 분리한다. 측정 기록 §6: ② 는 material-0 재심 2건이나 그중 #10 은
스스로 「계약 내용 재심 아님 — 결속 head 갱신」이다. ⑤·⑧ 은 열려 있다. 계약은 «종결»을 주장할 수
없으며, 그 사실은 §11 완료 판단을 막지 않는다(직전 결정과 같은 처리).

---

## 표준 이탈(standing deviation)

1. **U-17 (b)② 편차** — 직전 결정과 같은 수용(`U17-B2-DEVIATION-ACCEPTANCE.md`, 2026-09-02)이
   그대로 적용된다. 측정 기록 §1 이 같은 삼중값(`28475ca1…` / `21c47e42…` / `100181808552`)을
   재확인했다. 기계 상태는 수용으로 바뀌지 않는다.
2. **S-26 미충족** — 위 3.

## 측정 환경 부기

이 호스트의 `gh 2.45.0` 으로는 U-17 live 가 항상 `PREVENTION_UNVERIFIABLE` 로 나온다(`--slurp` 미지원).
`yq` 도 없다. 측정은 스크래치 전용 standalone 바이너리로 했다(측정 기록 §0). 서명 시점에 U-17 을 다시
잴 때 같은 전제가 필요하다.

## 효력

`decision` 이 `PHASE0_SECTION11_COMPLETE_ACCEPTED_AT_JUDGMENT` 로 바뀌고 `operator_countersign` 이 실제
식별값·ISO-8601 UTC 시각으로 기입돼 커밋된 시점에만 발효한다. 열린 항목 1 이 처분되면 `judged_head` 가
그 수정이 착지한 head 로 바뀌어야 하며, 그때 측정 기록도 다시 잰다. 발효가 바꾸지 «않는» 것: 기계
상태 · 계약 S-26 종결 자격 · G1~G3 · `restricted_live`/`production` 권한 · 직전 결정(`d07646c2`).
