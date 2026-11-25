# TOS — 송신 전 halt 된 예약의 해제 (#974)

- 날짜: 2026-11-01 · 저자: 세션 모델 단독 · 이슈: #974 (출처 #973 리뷰 M1 · 10-29 측정·운영자 «보류, 첫 발생 때 수정»)
- 리뷰 등급(구현 PR): **A** — RCL 용량 해제 경로 + 커널 `tos/src` 변경. Claude 측 독립 리뷰 1회. Codex 는 운영자 승인 시.
- 상태: **운영자 승인 2026-11-01** — §6 결정 1 지금 구현(10-29 보류 결정 대체) · 2 커널 변경 승인 · 3 Codex 없음, Claude 측 1회(추천대로).
- 완료 조건: 진입 POSITION_CONSUMED 뒤 CLOSE 가 step 9 커밋 후 송신 전에 halt 되어도, 다음 CLOSE 가 step 8 을 통과한다.
  한 프로세스와 재기동 뒤 모두. 실주문 0.

## 1. 사실 (main `cbb8dce0`, 2026-11-01 측정)

| # | 사실 | 위치 |
|---|---|---|
| F1 | step 9 ATOMIC_COMMIT 뒤 송신 봉인(SEND_SEALED) 전까지 halt 가능한 단계: 10 COMMITMENT_UNAVAILABILITY · 11 ORDER_CONFORMANCE_PROOF · 12–14 attempt 결속 | `tos/src/tos/engine/vocabulary.py:198-` |
| F2 | 그렇게 남은 예약은 엔진 원장에서 `COMMITTED_UNBOUND`(또는 ATTEMPT_BOUND)·`NOT_SENT` 이다 | `tos/src/tos/engine/state.py:579 commit_unbound`, `:608` |
| F3 | 엔진 `release()` 는 `_RELEASABLE_KNOWLEDGE`(종결 결과의 knowledge)만 받는다 — `NOT_SENT` 는 없다 | `state.py:226`, `:459-497` |
| F4 | 엔진은 step 8 런타임 단계보다 **먼저** 자기 원장으로 «미해제 예약이 있으면 거부» 한다(`AT_MOST_ONE_EXPOSURE_HELD`) | `tos/src/tos/engine/sequencer.py:426-440` |
| F5 | RCL 은 `RELEASED` 로 가는 전이에 `finality_witness is True` 를 요구하고, `FINAL_QUANTITY_PROOF` 가 RELEASED 에 닿는 원인이다 | `tos/src/tos/rcl/commitlog.py:467-500` · `rcl/vocabulary.py:89-104` |
| F6 | 해제는 지금 release consumer 만 부르고, 그것은 egress 결과(체결·non-execution)가 있을 때만 돈다 | `tos_runtime/posttrade/release_consumer.py` |
| F7 | 부팅 replay(#944/#994)가 같은 원장 상태를 매번 재구성한다 → 재기동으로 풀리지 않는다 | #994 |
| F8 | **실측(11-01, 읽기 전용 `scan_halts2.py`, 증거 저장소 66개):** step-9 커밋 0 · 미해제 >1 scope 0. 10-29(57개)와 같다 — **아직 발생 0** | #974 코멘트의 스크립트 |

**10-29 이후 바뀐 것.** 운영 대응 «HTS 수동 청산»은 주식 MOCK 트리에만 있다. 선물·paper 트리는 synthetic 이라
손으로 청산할 곳이 없다. #1011 의 venue 원장을 **11-13 이후 켜면**(운영자 결정 10-31) synthetic 트리에서 처음으로
CLOSE 가 step 9 에 닿는다. 그때 한 번 halt 되면 그 scope 는 월물 잎이 바뀔 때까지 봉인되고, 되돌릴 수단은
새 잎(genesis)뿐이다. M4(11-30~12-11) 창 안이면 §2-1 연속 10 거래일이 끊긴다.

## 2. 선택지

| 안 | 내용 | 판단 |
|---|---|---|
| **A (추천, 10-29 준비안)** | 송신 안 된 것이 **증거로 증명된** 예약만 RELEASED: 커널 `discard_unsent` + 런타임 결합 술어 + RCL `FINAL_QUANTITY_PROOF`(수량 0) | 커널 약 40줄 · 런타임 약 250줄 |
| B | 보류 유지(R5) — 첫 발생 때 A 착수 | synthetic 트리에는 발생 뒤 복구 수단이 없다(새 잎뿐) |
| C | step 9 커밋을 step 14 뒤로 미룬다 | ADR-002-002 §11 순서 변경 — RFC-005 §7 이 금지. **기각** |
| D | halt 되면 CLOSE 예약을 POTENTIALLY_LIVE 로 두고 운영자가 푼다 | 자동 re-arm 은 아니지만 운영자 수작업이 무인 운용(§2-1)과 충돌. **기각** |

## 3. 설계 (안 A)

### 3.1 무엇을 «송신 안 됨»의 증거로 보나 — 결합 술어(모두 참이어야)

같은 flow(event_id)·같은 proposal 에 대해:
1. `FLOW_STEP_ADMITTED(step=ATOMIC_COMMIT)` 가 있다(예약이 이 flow 의 것).
2. 그 뒤 `FLOW_HALTED` 가 있고 그 step 이 10–14 중 하나다(송신 단계 이전).
3. `SEND_HANDED_OFF`·`SEND_SEALED`·`TRANSPORT_SEND`·`TRANSPORT_DRY_RUN` 이 **하나도 없다**.
4. 처리 중 중단 표시가 없다 — `EVENT_CONSUMED` 의 `halt_reason` 이 `HANDLING_INTERRUPTED_*` 가 아니고
   `HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND` 행도 없다(`tos_runtime/engine/driver.py:171-179`). 중단은 «송신했는지 모름»이다.
5. `EVENT_CONSUMED` 가 있다 — flow 가 끝까지 기록됐다.
어느 하나라도 읽을 수 없거나 모호하면 **해제하지 않는다**(그대로 봉인, fail-closed).

### 3.2 커널 (`tos/src`)

- `ProvisionalReservationLedger.discard_unsent(ref) -> bool`: proposal_id 로 찾은 예약이 `NOT_SENT` 이고
  `COMMITTED_UNBOUND`/`ATTEMPT_BOUND` 일 때만 제거한다. `POTENTIALLY_LIVE` 이상, 또는 attempt 에 egress 결과가
  하나라도 붙었으면 거부. 반환값으로 거부를 알린다(예외 아님).
- replay 가 같은 판단을 재현하도록 엔진 증거 행(`RESERVATION_DISCARDED_UNSENT`, proposal·사유)을 남기고,
  replay 는 그 행을 만나면 같은 호출을 한다. 커널 술어는 순수 함수로 둔다(증거 저장소를 읽지 않는다).

### 3.3 런타임

- 새 모듈 `posttrade/unsent_release.py`: §3.1 술어(증거 저장소 읽기 전용) → 참이면
  ① 엔진 `discard_unsent` ② RCL `ReleaseReservation`(원인 `FINAL_QUANTITY_PROOF`, 수량 0, `finality_witness=True` 는 이 술어의 결과)
  ③ 증거 `CAPACITY_RELEASE_INTENT`(원인 `UNSENT_FLOW_NON_EXECUTION`).
- 실행 시점: flow 가 halt 로 끝난 직후(같은 루프 패스) + 부팅 복구 1회. 둘 다 **같은 술어**를 부른다.
- 순서와 충돌: RCL 해제가 먼저 커밋되고, 엔진 discard 는 그 뒤. 중간에 죽으면 부팅이 RCL 상태(RELEASED)를
  보고 엔진 쪽만 다시 한다. 반대 순서(엔진만 지움)는 만들지 않는다.

### 3.4 하지 않는 것

- `POTENTIALLY_LIVE`(송신했을 수도 있음) 해제 — 그것은 broker 증명(#948/#980) 영역이다.
- 운영자 수동 해제 명령.
- 새 checker·레지스터(R5): 이것은 판정 장치가 아니라 해제 경로다.

## 4. 순서

| PR | 내용 | 등급 |
|---|---|---|
| Q1 | 커널 `discard_unsent` + replay 행 + 커널 시험 | A |
| Q2 | 런타임 술어 + 해제 배선(halt 직후·부팅) + compose e2e + digest 재도출 | A |

목표: Q1·Q2 머지 **11-12 이전**(venue 원장 켜기 11-13 이후보다 먼저). 켜기와 같은 날 배포하지 않는다.

## 5. 시험

1. 커널: NOT_SENT+COMMITTED_UNBOUND → 제거 · ATTEMPT_BOUND → 제거 · POTENTIALLY_LIVE → 거부 · 결과 붙은 attempt → 거부 · replay 재현.
2. 술어: 다섯 조건 각각 하나만 빠진 다섯 입력 → 해제 안 함. 증거 읽기 실패 → 해제 안 함.
3. compose e2e(synthetic, venue 원장 ON): 진입 → CLOSE 가 step 14 에서 halt(currentness stale 주입) → 예약 RELEASED → 다음 CLOSE 가 step 8 통과 → 체결.
4. 재기동: RCL 해제 커밋 직후 `kill -9` → 부팅 → 엔진 원장에 그 예약 없음 · 중복 해제 0.
5. 송신 뒤 halt(SEND_SEALED 있음) → 해제 안 함(봉인 유지).

## 6. 운영자 결정

1. **10-29 «보류, 첫 발생 때 수정»을 이것으로 바꾸는가.** 바꿀 근거는 F8 이 아니라 §1 끝의 «synthetic 트리는
   발생 뒤 복구 수단이 없다»이다. R5 는 새 가드(판정 장치)에 대한 규칙이고 이 변경은 해제 경로라 직접
   걸리지 않지만, 10-29 에 운영자가 R5 정신으로 보류를 정했으므로 다시 묻는다.
2. 커널 `tos/src` 변경(약 40줄) 승인 — firewall·kernel 시험·digest 가 바뀐다.
3. Codex 리뷰를 붙일지(A 등급, 비용 승인 필요) — 추천: 붙이지 않는다(Claude 측 1회로 충분, 실주문 경로 아님).
