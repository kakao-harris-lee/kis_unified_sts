# egress 결과 증거에 거래일 기록 — C-1 조인 활성화 계획

- 작성: 2026-09-26 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `9434c280`(#804 머지 직후)
- 요청: 운영자 2026-09-26 「plan the change」 — #804 의 C-1 `broker_execution_id` 조인이 **발화하지 않는** 원인
  (egress-result 증거에 거래일이 없다)을 닫는 계획.
- 상위: `docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` §7.9 C-1 행.
- 성격: **계획 문서다. 코드는 넣지 않았다.** 착수는 운영자 검토 후.
- 되돌리기 어려운 경로: 재무장·캐파시티 해제(리스크 한도) — 구현 PR 은 운영자가 승인하면 `codex-gate` 대상(CLAUDE.md 2026-09-11).

## 0. 한 줄 요약

영수증(`EGRESS_RESULT_CONSUMED`/`RESULT_UNMATCHED`)에 **ACK 시점의 신뢰 시각으로 계산한 KST 거래일**을 싣고,
증인은 조회일 대신 **행마다 브로커가 돌려준 `ord_dt`** 를 쓴다. 날짜는 커널 레코드의 주입 토큰(`str | None`)으로
들어가므로 커널은 시계를 갖지 않고, 인박스 페이로드에 실리므로 재생이 결정적이다. 신뢰 시각이 없거나 날짜 규칙이
측정되지 않은 세션(자정을 넘는 야간 세션)에서는 `None` — 조인이 일어나지 않는 fail-closed 가 기본이다.

## 1. 실측 (main `9434c280`)

| 무엇 | 어디 | 상태 |
|---|---|---|
| 조인 가드 | `recon/service.py` `_join_orders_by_execution_id` — `receipt.trading_date == snapshot.order_inquiry_date` 일 때만 | #804 착지 |
| 영수증 날짜 | `EgressReceiptObservation.trading_date` — `SqliteEvidenceReceiptReader` 가 채우지 않음(항상 `None`) | **여기가 비어 있다** |
| 증거 쓰기 경로 | KIS 어댑터 `_map_response`(`transport/kis_mock/adapter.py:432-461`) → `_finish`(`:463-492`) → `EgressResultPayload`(`tos/src/tos/engine/records.py:242-249`, 날짜 필드 없음) → 드라이버 인박스(`engine/driver.py:925-939`) → 커널 `core.py:709-758` 이 `EngineEvidenceRecord` 로 복사 → `EngineEvidenceSinkAdapter`(`evidence/sinks.py:111-123`) → 스토어(`evidence/store.py`, 시각은 `appended_at_monotonic_ns` 뿐) | 쓰는 경로 어디에도 벽시계가 없다 — **사후에 날짜를 도출할 수 없다** |
| ACK 응답 | KIS 주문 응답 `output` 에는 `ODNO`(와 주문시각)가 있고 **날짜는 없다** | 영수증 쪽 날짜는 런타임 시계에서 와야 한다 |
| 신뢰 시각 | `TrustworthyTimeService.wall_clock_now()` — `TRUSTED` 일 때만 unix ms, 아니면 `None`(`time/service.py:697-711`) · `TrustedWallClockReference` 가 세션 사실 소유자에 이미 배선됨(`compose/_session_wiring.py:131-190`) | 재사용 |
| 세션·달력 | `calendar/phase.py` `_active_window_at`(:50-81)은 자정을 넘는 창을 전날 시작으로 해석하지만 `session_phase_at`(:109-) 이 그 시작을 버리고, `PhaseFact`(`calendar/model.py:20-38`)에 **거래일 개념이 없다** | 신설 필요 |
| 증인 날짜 | `KisStockBrokerWitness` 가 `SystemKstDateSource.today()`(날것의 `datetime.now(Asia/Seoul)`, 신뢰 게이트 없음 — `recon/witness_kis.py:191-213`)로 조회하고 `order_inquiry_date` 를 보고 | 교체 대상 |
| 증인 행 날짜 | KIS 주식일별주문체결조회 행에 `ord_dt`(주문일자)가 있다 — 프로필 `KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:1005` · 실측 `P-11-20260805T000501Z.json:measurements.fill_case.execution_inquiry.row.ord_dt=20260805` (같은 행 `ord_tmd=090512`) | 사용 가능 · `WitnessOrder` 에 필드 없음 |
| 증인 배선 | 컴포즈에 `KisStockBrokerWitness` 배선 **없음** — 복구 경로는 `SyntheticLedgerWitness`(`recovery/reconciliation.py:7-12`) | 이 계획의 효과는 증인이 배선될 때 나타난다 |
| 커널 규약 | 커널은 시계 없음(패키지 docstring 관례) · 날짜는 주입 토큰 선례 `posttrade/records.py:441-451`(`trade_date: str | None`) · `FrozenModel` 은 `extra="forbid"`(`canonical/_base.py:87`) — 런타임이 페이로드에 **미선언 키**를 넣으면 `backtest/calibration_report.py:172` 의 `model_validate` 가 그 행을 거부 | 필드는 커널에 **선언**해야 한다 |
| digest | `EngineEvidenceRecord` 는 covered set 없는 `FrozenModel`(`records.py:774-780`) — 필드 추가가 content digest 에 영향 없음(KW3-EV 선례). `.py` 변경이므로 `expected_code_digest` 재도출은 필요 | 통상 절차 |

**날짜 규칙의 근거.** 주식 정규장(09:00~15:30 KST)은 UTC 00:00~06:30 이라 KST 날짜와 UTC 날짜가 늘 같다 —
위 실측 1건(`ord_dt` 20260805 · `ord_tmd` 090512)은 「주식 주문일자 = 주문 시각의 KST 날짜」와 **정합하지만
그것을 구별해 증명하지는 못한다**(UTC 로 읽어도 같다). 주식에서는 둘이 갈리지 않으므로 이 계획에 충분하다.
**자정을 넘는 선물 야간 세션**에서 KIS 가 주문일자를 달력일로 줄지 다음 영업일로 줄지는 **측정된 적이 없다** —
그래서 그 세션에는 날짜를 주지 않는다(§2 결정 3).

## 2. 결정

1. **커널: 주입 토큰 필드 두 개.** `EgressResultPayload.trading_date: str | None = None` ·
   `EngineEvidenceRecord.trading_date: str | None = None`(`YYYYMMDD`). `core.py` 의 두 복사 지점(`RESULT_UNMATCHED`
   `:709-725` · `EGRESS_RESULT_CONSUMED` `:738-758`)이 그대로 복사한다. 커널은 값을 만들지도 검증하지도 않는다
   (형식 검증만: 8자리 숫자 또는 `None`). 중복제거 서명(`engine/state.py:850-857`)에는 **넣지 않는다** — 같은 결과가
   날짜만 달리 두 번 오는 것은 같은 결과다.
2. **런타임: 날짜를 찍는 곳은 어댑터의 ACK 순간.** KIS 어댑터 `_finish` 가 `EgressResultPayload` 를 만들 때 주입된
   `TradingDateSource.trading_date_now(instrument_class)` 값을 싣는다. 결과가 인박스를 거쳐 커널로 가므로 재생은
   인박스 페이로드를 다시 읽을 뿐 시계를 다시 읽지 않는다(결정적). 합성 전송(커널 코드)은 `None` — 합성 증인은
   `attempt_id` 로 이미 조인하므로 손실이 없다.
3. **거래일 함수: 달력 쪽에 하나, 신뢰 시각 뒤에.** `calendar/phase.py` 에 `trading_date_at(unix_ms, instrument_class,
   cfg) -> str | None` 신설. 규칙:
   - 신뢰 시각이 없으면(`wall_clock_now() is None`) `None`.
   - 그 순간이 **자정을 넘지 않는** 세션 창 안이면 그 순간의 KST 날짜.
   - 자정을 넘는 창(`SessionWindow.crosses_midnight`) 안이거나 어떤 창 밖이면 `None` — 규칙이 측정되지 않았다(§1).
   `TradingDateSource` 는 이 함수를 `TrustedWallClockReference` 와 묶은 얇은 포트다.
4. **증인: 행의 `ord_dt` 를 주문 단위로.** `WitnessOrder.order_date: str | None` 신설, `KisStockBrokerWitness` 가 행의
   `ord_dt` 를 싣는다(8자리 숫자가 아니면 `None`). 조인 가드를 `receipt.trading_date == order.order_date` 로 바꾸고,
   `snapshot.order_inquiry_date` 는 「조회 범위」 기록으로 남기되 조인에는 쓰지 않는다 — 날짜의 출처가 우리 시계가
   아니라 브로커 자신이 된다. `SystemKstDateSource` 는 조회 파라미터용으로만 남기고, 신뢰 시각이 없을 때 조회를
   거부(`WitnessUnavailable`)하도록 같은 `TradingDateSource` 로 교체한다.
5. **판독기.** `SqliteEvidenceReceiptReader` 가 페이로드의 `trading_date` 를 읽는다(8자리 숫자가 아니면 `None`).
   이 변경 이전에 쓰인 영수증은 키가 없으므로 `None` → 조인 안 함(fail-closed, 과거 증거를 소급하지 않는다).

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| (B) 런타임만: 어댑터의 `TRANSPORT_SEND` 증거 행에 날짜(와 ODNO)를 넣고 판독기가 `attempt_id` 로 두 종류를 잇는다 | 커널 변경은 없지만 한 사실(이 결과가 어느 날의 것인가)을 두 행에 쪼갠다. 판독기에 종류 간 조인이 새로 생기고, 합성 경로와 재생 경로에는 날짜가 영영 없다 |
| 싱크에서 벽시계로 찍기(`EngineEvidenceSinkAdapter.record`) | 싱크 시각 ≠ ACK 시각(자정 경계에서 틀린다) · 재생 때 다시 찍으면 값이 바뀐다(비결정) · 미선언 키면 `extra="forbid"` 에 걸린다 |
| `appended_at_monotonic_ns` 에서 날짜 도출 | 단조 시계는 벽시계가 아니다 — 부팅마다 원점이 다르다 |
| 조회일(`order_inquiry_date`)만으로 계속 조인 | 증인 쪽 날짜가 우리 시계다. 행의 `ord_dt` 는 브로커가 준 사실이라 더 강하고, 다일 조회로 넓혀도 그대로 성립한다 |
| 야간 세션에 「다음 영업일」 규칙을 가정 | 측정 없음 — 틀리면 조인이 fail-open(§1). 측정 전에는 `None` |

## 4. 작업 (PR 하나, 커밋 단위)

| # | 내용 | 파일 |
|---|---|---|
| T-1 | 커널 필드 2개 + 복사 2곳 + 형식 검증 + 테스트(복사됨 · 서명 불변 · 형식 위반 거부) | `tos/src/tos/engine/records.py` · `core.py` · `tos/tests/engine/` |
| T-2 | `trading_date_at` + `TradingDateSource` 포트/구현 + 테스트(신뢰 없음 → `None` · 창 안 → KST 날짜 · 자정 횡단 창 → `None` · 창 밖 → `None` · UTC 자정 직후 KST 날짜) | `tos_runtime/calendar/phase.py` · `calendar/ports.py` |
| T-3 | KIS 어댑터가 ACK 결과에 날짜를 실음 · 컴포즈 배선(기존 `TrustedWallClockReference` 재사용) | `transport/kis_mock/adapter.py` · `compose/_transport_wiring.py` |
| T-4 | 판독기가 `trading_date` 를 읽음 · 증인 `WitnessOrder.order_date` ← `ord_dt` · 조인 가드를 주문 단위 날짜로 · `SystemKstDateSource` 교체 | `recon/evidence_reader.py` · `ports.py` · `witness_kis.py` · `service.py` |
| T-5 | 종단 테스트: 실 `SqliteEvidenceReceiptReader` + 실 `KisStockBrokerWitness`(가짜 GET 서버) + 날짜 실린 영수증 → **MATCHED** · `test_witness_kis_reconciliation_pin.py` (b) 가 「아직 조인 안 됨」에서 「조인됨」으로 뒤집힌다 | `tos/runtime/tests/recon/` |
| T-6 | `expected_code_digest` 재도출(`release.yaml` + `_VALUE_PINS`) · 상위 계획 착지 기록 | config · docs |

## 5. 종료 조건 · 뮤테이션

- **실 클래스 종단에서 조인이 발화한다**: T-5 에서 MATCHED · `permits_rearm=True`(FQP 없으면 `permits_capacity_release=False`).
- **fail-closed 가 유지된다** — 각각 테스트로 핀:
  - 신뢰 시각 없음 → 영수증 날짜 `None` → 조인 없음
  - 자정 횡단 세션의 ACK → `None` → 조인 없음
  - 이 변경 이전 영수증(키 없음) → 조인 없음
  - 영수증 날짜 ≠ 행 `ord_dt` → 조인 없음(#804 S2 시나리오를 실 클래스로)
  - #804 의 기존 가드 6종 무회귀
- **재생 결정성**: 같은 인박스를 두 번 재생해 같은 `trading_date` 가 나오고, 재생 중 시계를 다른 값으로 바꿔도 불변.
- **뮤테이션**(각각 red 여야 함): M1 복사 지점 제거 · M2 신뢰 게이트 제거 · M3 자정 횡단 `None` 제거 · M4 증인 `ord_dt`
  대신 조회일 사용 · M5 판독기에서 형식 검증 제거.

## 6. 운영자 확인

1. **야간 세션 규칙은 측정 전까지 `None`** 이다. 선물 증인은 아직 없고(모의 선물 잔고 TR 부재), 주식은 자정을 넘지
   않으므로 지금 잃는 것은 없다. 선물 증인이 생길 때 야간 `ord_dt` 를 GET-only 로 측정해 규칙을 정한다 — 동의 여부.
2. **커널 레코드 필드 추가**(주입 토큰, 시계 없음) — 동의 여부. 대안 (B)는 커널을 건드리지 않지만 §3 이유로 기각했다.
3. **Codex 리뷰**: 구현 PR 은 재무장·캐파시티 경로이므로 승인 시 `codex-gate` 1회. 이 환경에는 Codex 가 없으므로
   운영자 호스트에서 실행하거나 폴백 레인으로 대체할지 미리 정해 두면 머지가 막히지 않는다.

## 7. 위험

- **증인이 아직 배선되지 않았다** — 이 계획을 다 해도 복구 경로는 합성 증인을 쓴다. 조인은 **KIS 증인이 배선되는
  순간** 효과를 낸다. 증인 배선은 별도 작업이다(이 계획의 범위 밖).
- **ODNO 일별 재시작은 가정이다** — 근거는 작은 ODNO 값(`0000003663` 09:05)과 일별 조회 TR 의 형태뿐이다. 날짜 가드는
  이 가정이 틀려도 안전한 쪽이다(같은 날 안에서만 조인하므로 조인 기회가 줄 뿐 잘못 잇지 않는다).
