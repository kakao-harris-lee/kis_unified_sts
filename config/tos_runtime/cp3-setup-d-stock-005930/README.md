# config/tos_runtime/cp3-setup-d-stock-005930/

CP-3 **주식 tenant** 설정 트리 — rescope 계획 §3 M2(`docs/plans/2026-10-22-tos-rescope-plan.md`).
운영자 결정 2026-10-22: **종목 005930(삼성전자) · 규칙 Setup D VWAP 되돌림 LONG 그대로 ·
수량 1주 고정 · 주식 정규장 09:00~15:30 KST.**

이 트리는 `cp3-setup-d-long/` 에서 파생됐고, 운영 방식(렌더 · 러너 · 증거)은 그 트리의
README 가 정본이다. 여기에는 **다른 것만** 적는다.

## LONG 트리와 다른 것

| 파일 | 다른 값 | 이유 |
| --- | --- | --- |
| `RENDER.yaml` | `tree_id` · `account.env_key: KIS_STOCK_ACCOUNT_NO` · band 슬롯 3개 없음 | 계좌 좌표는 **주식** 모의 계좌. band 원천 없음 |
| `construction.yaml` · `marketfeed.yaml` | `instrument_class: krx-stock` · `unit: SHARES` | 이 트리 `calendar.yaml` 의 `krx-stock` 세션(CONTINUOUS 09:00-15:30)을 쓴다 |
| `venue_constraint_policy.yaml` | 호가단위 `price_band_ticks` 사다리(`tick_size` null) · `max_quantity` 1 · `KRX_STOCK` · `SHARES` · band 없음 | 파일 헤더 참조(출처·등급·실패 방향) |
| `order_construction_policy.yaml` · `aggregate_risk_policy.yaml` · `safety_envelope.yaml` · `safety_profile.yaml` | 수량 단위 `SHARES` | 주식 |
| `action_flow_policy.yaml` · `aggregate_risk_policy.yaml` · `order_construction_policy.yaml` · `critical_input_policy.yaml` | `policy_id` | 내용이 달라졌으니 id 도 다르다(LONG VCP 헤더의 규칙) |

나머지 파일은 LONG 과 **바이트 동일**이다(전략 파일 포함 — 규칙 재사용). 이 분류는
`tos/runtime/tests/compose/test_tenant_tree_stock.py` 가 파일·키 경로 단위로 고정한다.

## 오늘 무엇을 하고 무엇을 하지 않는가

- `broker_scopes.yaml::active_scope` 는 **`SYNTHETIC_FUTURES_ORDER` 그대로** — 이 트리는 아무것도
  송신하지 않는다. `MOCK_STOCK_ORDER` 활성화는 별도 승인(위험 등급 A)이다.
- **band(가격제한폭) 원천이 없다** → 모든 시도는 venue 단계에서 UNKNOWN 으로 끝난다.
  주식 band 원천은 M2 의 남은 일이다.
- 호가단위는 사다리 한 칸(500원, 200,000~500,000원 구간)만 표현한다. 가격이 그 구간을
  벗어나면 닫힘 쪽으로 실패한다(VCP 헤더).
- 시세는 `config/tos_probes/cp3-live-producer-stock-005930.yaml` 의 생산자(주식일별분봉조회
  FHKST03010230, GET 전용)가 만든다.
