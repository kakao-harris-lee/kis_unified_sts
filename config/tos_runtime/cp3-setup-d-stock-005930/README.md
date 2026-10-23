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
- 체결·완결(fill/finality)은 아직 이 트리에 없다 — PR-3b. 오늘 송신은 ACK 까지 기록되고
  예약은 그 다음 사실을 기다린다.
- LONG 과 바이트 동일한 파일 몇 개(`construction.yaml` · `finality.yaml` · `monitor_coverage.yaml`)의
  주석은 `SYNTHETIC_FUTURES_ORDER` 를 말한다 — 바이트 동일 고정 때문에 그대로 두었다. 이 트리에서는
  이 README 와 `broker_scopes.yaml` 이 정본이다.
- 시세는 `config/tos_probes/cp3-live-producer-stock-005930.yaml` 의 생산자(주식일별분봉조회
  FHKST03010230, GET 전용)가 만든다.
