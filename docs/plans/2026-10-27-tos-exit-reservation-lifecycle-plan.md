# TOS — 청산 attempt 의 RCL 예약 수명주기 (#966)

- 날짜: 2026-10-27 (개정 10-28: §2.1 ID 출처, §2.5, §2.6 — 구현 전 측정으로) · 저자: 세션 모델 단독 · 이슈: #966 (선행 #960 / PR #965)
- 리뷰 등급: **A** — 리스크 한도·원장(RCL) 경로. Claude 측 독립 리뷰 1회 + Codex(운영자 승인 2026-10-27, 범위 = #966 diff 만).
- 완료 조건 (TOS_PAPER_READY 의 해당 문장): 한 프로세스에서 **진입 → 청산 → 브로커 포지션 0**, 실주문 0(paper/mock).

## 1. 사실 (코드에서 측정)

| # | 사실 | 위치 |
|---|---|---|
| F1 | 예약 ID 는 scope 당 하나: `resv-{account}-{instrument}` ("one reservation per scope, not per attempt") | `tos_runtime/rcl/reservation_identity.py:23` |
| F2 | 그 ID 를 scope 에서 재계산하는 소비자 6곳: step 9 `reservation_id_provider`, step 13 바인딩, engine `reservation_id_resolver`, riskstate `economic_ref`, recovery reconciliation, posttrade release consumer | `compose/_wiring.py:764,828` · `_engine_wiring.py:544` · `riskstate/service.py:605` · `recovery/reconciliation.py:279` · `posttrade/release_consumer.py:337` · `compose/context.py:628` |
| F3 | step 8 은 scope 에 예약 행이 **하나라도** 있으면 DENY (상태 무관 — RELEASED 포함) | `risk/ledger_stages.py:373-390` |
| F4 | projection `instrument_state`/`instrument_last_seq` 는 scope 의 **첫 행** 하나만 돌려준다 | `rcl/projection.py:133-143` |
| F5 | 같은 단일 읽기를 쓰는 곳: ARE 스냅샷(사용량 벡터), step 10 재확인, 안전 latch(미해제 개수 0/1) | `risk/aggregate.py:341` · `ledger_stages.py:560` · `safety/latch.py:176` |
| F6 | FULL_FILL → `POSITION_CONSUMED`; `RELEASED` 는 finality witness(`is True`) 필수, 자동 re-arm 없음 | `tos/engine/state.py:209` · `tos/rcl/commitlog.py:467-490` |
| F7 | `POSITION_CONSUMED → RELEASED` 로 가는 운영 경로는 없다 (release consumer 는 non-execution 만 RELEASED) | `posttrade/release_consumer.py` 모듈 docstring |
| F8 | ADR-002-012 은 scope 당 예약 1개를 요구하지 않는다. 요구는 forward-only·witness-gated release·no re-arm | ADR-002-012 §5, :37, :151, :175 |

결론: 거부는 step 8 한 줄의 문제가 아니라 **"scope = 예약 1개" 가정** 이 6곳에 퍼진 결과다. 같은 프로세스든 재시작 뒤든, 진입 체결 뒤 그 scope 에는 어떤 주문도 다시 나갈 수 없다(fail-closed).

## 2. 설계

### 2.1 예약 ID 를 attempt 단위로 (F1, F2) — 개정 2026-10-28

- **개정 사유(측정):** `attempt_id` 는 step 12 에서야 만들어진다 — step 9 의 permit identity 와 step 11 의 conformance digest 로부터(`tos/engine/sequencer.py` step 12; `StageRequest.attempt` 는 "step 13 onward", `tos/engine/records.py`). 그래서 첫 판의 `attempt_reservation_id(…, attempt_id)` 는 step 9 커밋 시점에 정의되지 않는다.
- **예약 ID = step 9 의 Action Flow Permit identity 로 만든다:** `permit_reservation_id(account, instrument, permit_identity) -> f"resv-{account}-{instrument}-{permit_identity}"`. step 9 는 permit 을 이미 쥐고 있고, step 10 은 step-9 verdict 의 `bound_identity`, step 13/14·`compose/context.py` 는 `AttemptRequest.action_flow_permit_identity` 에서 같은 값을 얻는다 — 새 배선 없음.
- **체결 이후 3곳**(release consumer, recovery reconciliation, engine `reservation_id_resolver`)은 `attempt_id` 만 쥔다. `attempt_id → permit_identity` 는 **이미 durable 한 증거 조인**으로 푼다: 같은 `event_id` 의 `FLOW_STEP_ADMITTED`(step `ATOMIC_COMMIT`, `bound_identity` = permit identity) 와 `ATTEMPT_REQUEST_CREATED`(`attempt_id`) — 이 조인이 바로 이 용도라고 `records.py` 필드 docstring 이 적고 있다. 판독 함수 하나, 새 쓰기 없음, 커널 변경 없음. 조인이 비면(증거 없음) 그 attempt 는 UNKNOWN/HOLD — 추측 ID 를 만들지 않는다.
- step 7 의 `economic_ref`(riskstate)는 permit 이전이라 scope 값으로 남긴다. 단 그것이 예약 행 ID 와 **비교·조인되는 곳이 없음**을 구현 1단계에서 확인하고, 있으면 멈추고 보고.
- 기존 `scope_reservation_id` 는 남긴다 — **기존 원장 행**(`resv-{acct}-{instr}`) 판독용. 새 커밋은 만들지 않는다. 마이그레이션 없음.
- 버린 안: 새 `RESERVATION_ATTEMPT_BOUND` 증거 행(같은 사실을 두 번 쓴다), 커널에서 step 12 를 9 앞으로(범위 밖).

### 2.2 scope 판독은 "행 하나" 가 아니라 "행 집합" (F4, F5)

- projection 에 `scope_reservations(key) -> tuple[(reservation_id, state, last_seq), ...]` 추가. `instrument_state` 는 제거하지 않고 호출부를 옮긴 뒤 삭제(같은 PR).
- ARE 스냅샷: 사용량 = scope 의 **미해제(≠RELEASED) 예약 벡터 합**. 측정(10-28): runtime 은 `CapacityReservationTransition.committed_vector` 를 어디서도 쓰지 않아 오늘은 항상 빈 벡터다 — 합산은 맞는 규칙이지만 관측 가능한 변화는 없고 2.3 의 선행조건이 아니다. 같은 PR 에서 합산으로 바꾸되 벡터 기록 자체는 범위 밖(별도 이슈).
- step 10: scope 첫 행이 아니라 **이번 attempt 의 예약 ID** 행을 재확인.
- 안전 latch: 미해제 예약 **개수**(0/1 → 0..n). 반환형 int 는 그대로.

### 2.3 step 8 규칙 (F3) — position_effect 별

| attempt | scope 의 미해제 예약 | 판정 |
|---|---|---|
| OPEN | 0 | ADMIT |
| OPEN | ≥1 | DENY (지금과 같음 — 피라미딩 금지 유지) |
| CLOSE | 정확히 1, 상태 `POSITION_CONSUMED` | ADMIT |
| CLOSE | 0, 또는 ≥2, 또는 1 이지만 다른 상태(진행 중 주문·QUARANTINED 등) | DENY, 사유에 상태 목록 |
| 판독 실패 | — | UNKNOWN (지금과 같음) |

- RELEASED 행은 집계에서 빠진다 → 청산 완료 뒤 새 진입이 다시 가능 (F3 의 "RELEASED 도 거부" 해소).
- position_effect 는 #965 의 `attempt_arm` 에서 읽는다 (step 2 가 고른 arm; 없으면 DENY).

### 2.4 청산 체결 뒤 진입 예약 해제 (F6, F7)

- 청산 예약 자신: FULL_FILL → `POSITION_CONSUMED` 가 아니라 **청산 attempt 는 `RELEASED`** 로 간다 — 새 포지션을 만들지 않으므로. 이 분기는 release consumer 에 `position_effect` 를 넘겨 결정(엔진 projection 매핑은 건드리지 않고 consumer 의 목표 상태만).
- 진입 예약: 청산 체결 + **recon 이 브로커 잔고 0 을 확인**(기존 `ReconciliationService` 결과)했을 때만 `POSITION_CONSUMED → RELEASED` (cause·witness 는 아래 측정 결과). 부분 청산이면 진입 예약은 그대로(보수적). witness 없으면 `CAPACITY_RELEASE_HELD` 기록 후 전이 없음 — 기존 consumer 규율 그대로.
- 커널(`tos/src/tos/rcl`) 변경 없음 — **측정 완료(2026-10-27)**: `transition_allowed` 는 `RELEASED` 로의 전이를 cause `FINAL_QUANTITY_PROOF` 일 때만 허용하고(`tos/rcl/predicates.py` `transition_allowed`), 출발 상태는 묻지 않는다; 커밋 로그는 추가로 finality witness `is True` 를 요구한다. 따라서 진입 예약 해제는 cause = `FINAL_QUANTITY_PROOF`(청산 attempt 의 최종 누적 체결 = 진입 수량, 잔량 0) + witness = 청산 finality proof 와 recon 잔고 0 이 **둘 다** 양성일 때. `RECONCILIATION_PROOF` 단독으로는 RELEASED 에 못 간다 — recon 은 witness 의 한 조건일 뿐 cause 가 아니다.

### 2.5 청산 attempt 의 리스크 판정 — 개정 2026-10-28

- 측정(cp3-setup-d-long): ARE `INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL` 한도 1 CONTRACT, AFG `afg.ORDER` 한도 1, `CLOSE → ORDINARY_REDUCE_OR_EXIT`, OCP 수량 1. compose 하네스에서 step 6 은 진입 위의 CLOSE 를 GRANT 했다(하네스 한도 기준 — 실제 트리 한도로는 미측정: 트리의 account/instrument 가 `TBD` 라 커밋 상태로는 부팅 불가).
- CLOSE 를 `ORDINARY_REDUCE_OR_EXIT` 로 판정하는 것은 **production riskstate 경로**뿐이다. compose e2e 하네스는 AFG 입력에 `NORMAL_NEW_RISK` 를 고정해 넣는다(`tests/compose/test_compose_root.py`). e2e 에서 action class 를 단언하려면 하네스 입력을 attempt 의 arm 에서 읽게 바꾼다(테스트 측).
- 한도 때문에 청산이 막히면 그 수치를 보고하고 YAML 정책 결정으로 올린다(코드 예외 분기 없음).

### 2.6 테스트 하네스 (신규 — 이것 없이는 한 프로세스 e2e 가 불가)

- 측정: 하네스의 ARE/AFG 입력이 `decision_generation=1` 을 고정해, 첫 흐름의 커밋으로 RCL tip 이 1 을 넘으면 **두 번째 흐름은 OPEN·CLOSE 모두 step 7 UNKNOWN** 으로 멈춘다(`compose/_risk_attestations.py` `generation_fenced`). production 은 두 세대 모두 live tip 이라 무관(`riskstate/service.py`).
- 하네스가 세대를 RCL tip 에서 읽게 고친다(테스트 코드만). #965 e2e 의 "CLOSE 를 첫 커밋으로" 우회는 step 8 과 이것 두 가지를 피하고 있었다.
- 참고(측정): 커널의 at-most-one 게이트는 진입 체결 뒤 이미 다시 열린다(`engine/finality_projection.py` 가 `ledger.release` 호출, RELEASED 는 outstanding 에서 빠짐) — 남은 차단은 runtime step 8 과 scope 단위 예약 ID 뿐이다.

## 3. 버린 대안

| 대안 | 버린 이유 |
|---|---|
| step 8 만 고쳐 CLOSE 가 같은 scope 예약을 재사용 | 같은 `reservation_id` 로 두 번째 `COMMIT_RESERVATION` → DUPLICATE/forward-only 위반. RCL 에 POSITION_CONSUMED → ATTEMPT_BOUND 역전이 없다(no re-arm) |
| 진입 예약을 먼저 RELEASED 로 만든 뒤 청산 | 포지션이 열린 동안 사용량 0 으로 보이게 된다 — ADR-002-012 :179 "cannot release … committed consumption" 위반 |
| 커널에 "exit reservation" 상태 추가 | 커널 변경·스펙 개정이 필요, 런타임만으로 풀린다 |
| scope 당 1개 유지 + 청산은 RCL 밖에서 전송 | 청산이 리스크 원장·permit 바인딩을 우회 — 등급 A 경로에서 받아들일 수 없다 |

## 4. 구현 순서 (한 PR, 커밋 단위)

1. 측정: 전이 허용(완료 — §2.4) · CLOSE envelope 크기와 한도(§2.5) — 결과를 PR 본문 표로. 한도에 막히면 중단·보고.
2. `attempt_reservation_id` + F2 6곳 전환 + 기존 scope ID 행 판독 유지.
3. projection `scope_reservations` + ARE 합산 · step 10 · latch 전환, `instrument_state` 삭제.
4. step 8 표(2.3).
5. release consumer: 청산 예약 RELEASED, 진입 예약 witness 해제(2.4).
6. 테스트:
   - e2e (`test_close_proposal_e2e.py` 확장): **한 프로세스** 진입 → 체결 → 청산 → 체결 → recon 0 → 진입 예약 RELEASED → 다시 진입 ADMIT. #965 의 "CLOSE 를 첫 commit 으로 몰기" 우회를 걷어낸다.
   - step 8 표의 각 행 단위 테스트(OPEN 2번째 DENY 포함).
   - ARE 합산: 미해제 2개 → 벡터 합, RELEASED 제외.
   - permit→예약 ID: step 9/10/13 이 같은 ID; 증거 조인으로 attempt→permit 복원; 조인이 비면 HOLD(추측 ID 없음).
   - 하네스: 두 번째 흐름이 step 7 을 통과(세대 = tip).
   - 재시작: 기존 `resv-{acct}-{instr}` 행이 있는 원장을 replay → 같은 판정.
   - 부분 청산 → 진입 예약 유지.
7. `expected_code_digest` 재도출(트리 4개) 마지막.

## 5. 범위 밖 / 조율

- 커널 `tos/src/tos/rcl` 변경, 양방향 트리(LOW-3), 피라미딩.
- `posttrade/` 를 건드리므로 **#950 (af 세션, `_broker_posttrade_wiring.py`) 과 조율** — 착수 전 af 에 파일 목록 통지, 나중 머지 쪽이 rebase.
- 운영: 머지 전까지 청산은 계속 HTS 수동(#960 운영 지시 유지).
