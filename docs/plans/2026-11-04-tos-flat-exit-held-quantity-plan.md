# TOS — 청산(FLAT) 제안의 보유 수량을 durable 원천에서 (#1025)

- 날짜: 2026-11-04 · 저자: 세션 모델 단독 · 이슈: #1025
- 리뷰 등급(구현 PR): **A** — 주문 구성 정책(청산 허용) + 청산 수량 경로. Claude 측 독립 리뷰 1회.
- 상태: **운영자 승인 2026-11-03**(안 A — step 6 과 같은 원천을 step 2 에 준다). 커널 `tos/src` 변경 **없음**(§2 참고).
- 완료 조건: 진입이 POSITION_CONSUMED 인 scope 에서 Setup D 의 실제 FLAT 제안이 step 2→14·송신·체결·해제까지 간다.
  주식(kis-mock)과 synthetic(venue 원장 ON) 둘 다, 한 프로세스와 재기동 뒤 모두. 실주문 0.

## 1. 사실 (main `44360c8a`, 11-03 실측 · 레인 probe)

| # | 사실 | 위치 |
|---|---|---|
| F1 | 세 CP-3 트리의 OCP 는 `admitted_quantity_bases: ["RISK"]` 만 허용한다 → FLAT(`ZERO_POSITION`)은 step 2 규칙 2 에서 거부된다. 실측 거부: LONG 295 · SHORT 251 · 주식 30 | `config/tos_runtime/cp3-setup-d-{long:192,short:192,stock-005930:221}/order_construction_policy.yaml` |
| F2 | `ZERO_POSITION` 을 넣어도 step 2 규칙 4 가 거부한다 — `held_position` 이 None | `tos/src/tos/egressgw/construction.py:419-431` |
| F3 | step 2 의 `held_position` 은 커널 메모리 원장 읽기다: `ledger.outstanding_consumed_magnitude` | `tos/src/tos/engine/sequencer.py:467` · `state.py:428-455` |
| F4 | 진입 체결 때 런타임이 메모리 원장 예약을 release 한다(RCL 은 POSITION_CONSUMED). 커널 at-most-one 사전검사가 CLOSE 를 통과시키려면 이 release 가 필요하다(#966) | `posttrade/release_consumer.py:419-426,789-795` · `engine/finality_projection.py:228` · `state.py:437` |
| F5 | 그래서 step 2(메모리)와 step 8(durable RCL)이 «보유 포지션 있음»을 서로 다르게 본다 | `risk/ledger_stages.py:403-430` |
| F6 | step 2 는 런타임 래퍼 `ProposalShapedConstructionStage` 가 커널 `OrderConstructionStage` 를 불러 실행한다 — 런타임이 `StageRequest` 를 넘기는 자리에 있다 | `compose/_attempt_shape.py:167-` · `compose/_wiring.py:554` |
| F7 | step 6 의 CLOSE 상한은 이미 durable 원천을 쓴다: 진입 잔량 `DurableEntryCloseBoundReader.read().remaining`(#1015), 주식은 KIS 보유 증명과 `min`(#1012 L3) | `riskstate/close_bound.py:109-211` · `riskstate/service.py:507-540` |
| F8 | held 를 stand-in 으로 주면 step 3–14·송신·체결·해제가 두 전송 모두 통과한다. LONG 청산 = SELL, SHORT 청산 = BUY. 주식 step 4 는 기존 상시 승인 `CLOSE-SHORT-SELL` 행으로 통과(승인 변경 불필요) | 레인 probe `issue1025_flat_exit_probe.py` |

## 2. 설계

**step 2 의 FLAT 보유 수량 = step 6 과 같은 durable 진입 잔량.**

- `ProposalShapedConstructionStage.__call__` 에서 제안이 FLAT(`quantity_basis == FLAT_QUANTITY_BASIS`)일 때만
  `request.held_position_magnitude` 를 `DurableEntryCloseBoundReader.read().remaining` 으로 바꾼 사본을 커널 stage 에 넘긴다
  (`StageRequest` 는 frozen — `model_copy(update=…)`). ACTION 제안의 요청은 손대지 않는다.
- reader 가 거부하면(진입 증명 없음 · 해제되지 않은 CLOSE 진행 중 · 모호) `None` 을 넘긴다 → 커널 규칙 4 가 지금처럼 거부한다
  (fail-closed, 메시지 그대로).
- 주식 트리: step 2 는 진입 잔량으로 수량을 정하고, step 6 이 KIS 보유 증명과 `min` 으로 다시 막는다(#1012 L3).
  브로커 보유가 잔량보다 적으면 step 6 이 거부한다 — 수량을 줄여서 보내지 않는다(더 작은 청산은 새 제안의 몫).
- 커널 변경 없음. 커널은 «offered to every step, consumed only by the bases that need it»(sequencer.py:463-466)
  관측을 받는 쪽이고, 그 관측을 런타임 stage 가 더 강한(durable) 원천으로 대신한다. 메모리 원장은 바꾸지 않는다.
- 비용: reader 는 FLAT 제안이 step 1 을 통과할 때만 불린다(드물다). #1008 처럼 패스마다 돌지 않는다.

**설정:** LONG·SHORT·주식 OCP 의 `admitted_quantity_bases` 를 `["RISK", "ZERO_POSITION"]` 으로 바꾼다.
`paper` 는 FLAT 규칙이 없으므로 넣지 않는다(소비자 없는 확장). `_runtime` 내용이라 activation digest 는 움직이지 않는다
(OCP 헤더: canonical_digest = policy_id/generation/version). 파일 규칙대로 `policy_generation` 을 손으로 올린다.

**덤:** `write-standing-approval` 의 «exit row cannot match until #960» 안내를 지운다(#960 머지됨, 행은 맞는다 — F8)
(`authority/standing_cli.py:314`, 시험 `test_standing_cli.py:105`).

## 3. 시험

1. 레인 probe 를 회귀 시험으로: stand-in 없이 주식·synthetic LONG·synthetic SHORT 에서 FLAT → 체결 → 두 예약 RELEASED.
2. 주식 step 6 을 실제 `BROKER_HELD_PROOF` 상한으로 한 번 측정(probe 는 주입 provider 였다): 보유 = 잔량 → 통과 · 보유 < 잔량 → 거부.
3. reader 거부 세 가지(진입 증명 없음 · CLOSE 진행 중 · 미증명 이전 청산) → step 2 거부, 송신 0.
4. ACTION 제안은 `held_position_magnitude` 가 바뀌지 않는다.
5. 재기동: 진입 체결 뒤 재부팅 → FLAT 이 같은 수량으로 통과(메모리 원장에 의존하지 않는다는 증거).
6. 포지션 없음(평탄)에서 FLAT → step 2 거부(오늘과 같은 결과, 사유만 «no held position»).

## 4. 순서·목표

PR 하나(A): 런타임 래퍼 + 설정 세 파일 + 시험 + CLI 문구. 목표 = 주식 트리 첫 진입 전(가능한 빨리).
venue 원장 켜기(11-13 이후)는 이 PR 뒤로 둔다 — 켜는 순간 synthetic 진입이 POSITION_CONSUMED 에 가고, 이 PR 이 없으면 청산이 막힌다.

## 5. 하지 않는 것

- 커널 메모리 원장을 포지션 원장으로 만들기(안 B, design #35 §5.3 보류).
- 브로커 보유가 잔량보다 적을 때 줄여서 청산하기.
- `paper` 트리 확장.
