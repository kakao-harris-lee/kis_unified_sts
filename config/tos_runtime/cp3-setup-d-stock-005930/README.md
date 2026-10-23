# config/tos_runtime/cp3-setup-d-stock-005930/

CP-3 **주식 tenant** 설정 트리 — rescope 계획 §3 M2(`docs/plans/2026-10-22-tos-rescope-plan.md`).
운영자 결정 2026-10-22: **종목 005930(삼성전자) · 규칙 Setup D VWAP 되돌림 LONG 그대로 ·
수량 1주 고정 · 주식 정규장 09:00~15:30 KST.**

이 트리는 `cp3-setup-d-long/` 에서 파생됐고, 운영 방식(렌더 · 러너 · 증거)은 그 트리의
README 가 정본이다. 여기에는 **다른 것만** 적는다.

## LONG 트리와 다른 것

| 파일 | 다른 값 | 이유 |
| --- | --- | --- |
| `RENDER.yaml` | `tree_id` · `account.env_key: KIS_STOCK_ACCOUNT_NO` | 계좌 좌표는 **주식** 모의 계좌 (band 슬롯 3개는 LONG 과 같다) |
| `construction.yaml` · `marketfeed.yaml` | `instrument_class: krx-stock` · `unit: SHARES` | 이 트리 `calendar.yaml` 의 `krx-stock` 세션(CONTINUOUS 09:00-15:30)을 쓴다 |
| `venue_constraint_policy.yaml` | 호가단위 `price_band_ticks` 사다리(`tick_size` null) · `max_quantity` 1 · `KRX_STOCK` · `SHARES` | 파일 헤더 참조(출처·등급·실패 방향). band 원천은 LONG 과 같은 `producer_journal` |
| `broker_scopes.yaml` · `coordinator_preconditions.yaml` · `egress_coordinates.yaml` | `active_scope: MOCK_STOCK_ORDER` · `profile_evidence_ok: true` · `nonlive_broker_consuming.admitted: true` · MOCK 주문 엔드포인트 | PR-3a(운영자 결정 2026-10-23) — **이 트리만** MOCK 주문 트리다 |
| `broker_facts.yaml` (이 트리에만 있음) | item 12 의 GET 전용 모의 계좌·거래 가능 사실(VTTC8434R · FHKST01010100) | PR-3a option (a) "K" |
| `fill_observer.yaml` (이 트리에만 있음) | ACK 뒤 체결 관찰(VTTC0081R) · 주식 KIS witness(VTTC8434R + VTTC0081R) TR·경로 · 폴링 간격 · overdue 한계 | PR-3b |
| `order_construction_policy.yaml` · `aggregate_risk_policy.yaml` · `safety_envelope.yaml` · `safety_profile.yaml` | 수량 단위 `SHARES` | 주식 |
| `action_flow_policy.yaml` · `aggregate_risk_policy.yaml` · `order_construction_policy.yaml` · `critical_input_policy.yaml` | `policy_id` | 내용이 달라졌으니 id 도 다르다(LONG VCP 헤더의 규칙) |

나머지 파일은 LONG 과 **바이트 동일**이다(전략 파일 포함 — 규칙 재사용). 이 분류는
`tos/runtime/tests/compose/test_tenant_tree_stock.py` 가 파일·키 경로 단위로 고정한다.

## 무엇을 하고 무엇을 하지 않는가 (PR-3a, 2026-10-23)

- `broker_scopes.yaml::active_scope` 는 **`MOCK_STOCK_ORDER`** — 모든 verify 항목이 충족되면
  KIS **모의투자** 주문 엔드포인트로 송신한다. 이 scope 의 튜플은 BROKER_SIMULATION × MOCK_ORDER ×
  BROKER_RESOURCE_ONLY × STOCK 뿐이라 REAL 주문 경로가 없다. LONG/SHORT/상주 paper 트리는
  `SYNTHETIC_FUTURES_ORDER` 그대로다.
- 부팅은 `--transport kis-mock` 이어야 한다(브로커 도달 scope 는 합성 전송과 짝이 맞지 않아
  거부된다). `kis_mock_transport.yaml` 은 배포 시점 파일이고 커밋하지 않는다.
- band 는 러너가 띄우는 band 프로브가 주식현재가 GET 으로 쓴 줄 하나다. 줄이 없으면
  (프로브 실패 · 브로커 `aspr_unit` 이 호가 사다리와 다름) 그 세션은 venue 단계 UNKNOWN 이다.
- item 12 의 계좌·거래 가능·브로커 제약 세대는 `broker_facts.yaml` 의 GET 두 개(모의 호스트)가
  만든다. 읽기 실패·거래정지·`max_age_ms` 초과는 송신 거부다.
- 체결·완결(PR-3b): ACK 뒤 `runtime.fill_observer` 가 주식일별주문체결조회(VTTC0081R, 모의 호스트
  GET)를 ACK 의 ODNO·거래일로 읽어 `PARTIAL_FILL`/`FULL_FILL`/`CANCEL_ACK` 를 엔진 결과 경로로 넣는다.
  이상한 행(수량 불일치·거부 수량·체결 뒤 취소·같은 ODNO 두 줄·원주문번호로 걸린 줄)은 `UNKNOWN`.
  모르는 ODNO 의 체결은 `FILL_OBSERVER_UNATTRIBUTED_ORDER` 로 기록만 하고 귀속하지 않는다 — 같은 종목에
  그런 주문이 있으면 해제 대조가 orphan 으로 보고 해제를 보류한다.
- 완결 증명은 `BrokerFinalityProducer`(`BROKER_ORDER_FQP`, `broker-fqp-*`) 이고, 해제·부팅 복구 대조는
  `SyntheticLedgerWitness` 가 아니라 `KisStockBrokerWitness` 다. 둘 다 **이 트리만**(kis-mock +
  `MOCK_STOCK_ORDER`) — LONG/SHORT/상주 paper 는 합성 그대로다.
- 해제가 커밋되지 않은 종결 결과(finality 전 크래시 · 대조 일시 불가 · CAS 보류)는 기록된 결과로
  `finality_retry_interval_ms` 마다 다시 시도한다 — RCL 에 `release-{attempt}` 가 생길 때까지.
- **ACK 뒤 재기동 사이의 체결은 해제하지 않는다.** 엔진의 예약 투영은 부팅 때 재구성되지 않아서(J3),
  그 결과를 엔진에 넣으면 다음 부팅 replay 가 갈라진다. 관찰자는 `FILL_OBSERVER_ENGINE_RESERVATION_ABSENT`
  를 기록하고 예약을 그대로 둔다(운영자 확인 대상). 미결 ACK 는 자기 거래일로 조회한다.
- **취소는 해제하지 않는다(issue #948).** 원주문 행의 `cncl_yn=Y` 든, `orgn_odno` 가 우리 주문을 가리키는 별도
  행이든 `FILL_OBSERVER_CANCEL_UNSUPPORTED` 1회 기록 · 예약 유지 · 재시도 없음. 모의 취소 프로브로 행 모양을
  잰 뒤에 만든다.
- 전일 미결 ACK 는 자기 거래일로 `prior_day_poll_interval_ms`(10분)마다 다시 읽는다 — overdue 는 경고일 뿐
  끝이 아니다.
- 관찰자 호출 주기(`poll_if_due()`)는 러너가 정한다(PR-3c). 이 PR 은 부르지 않는다.
- LONG 과 바이트 동일한 파일 몇 개(`construction.yaml` · `finality.yaml` · `monitor_coverage.yaml`)의
  주석은 `SYNTHETIC_FUTURES_ORDER` 를 말한다 — 바이트 동일 고정 때문에 그대로 두었다. 이 트리에서는
  이 README 와 `broker_scopes.yaml` 이 정본이다.
- 시세는 `config/tos_probes/cp3-live-producer-stock-005930.yaml` 의 생산자(주식일별분봉조회
  FHKST03010230, GET 전용)가 만든다.
