# TOS 주식 MOCK 트리 활성화 기록 — 승인 · 적합성 확약 (2026-10-24)

`config/tos_runtime/cp3-setup-d-stock-005930/safety_activation.yaml` 의 두 id 가 가리키는 기록이다.
B4(2026-10-24 오프라인 드라이런): 두 목록이 비어 SPG `activation_atomic` 이 DEFERRED → mesh 보류 → kis-mock 틱이 1단계 전에 `LIVE_SCOPE_NOT_AUTHORIZED` 로 멈췄다.

## ⚠ 이 기록의 무게

런타임은 두 목록이 **비어 있지 않은지만** 본다(`tos_runtime/safety/profile.py` `_activation_inputs`: `staging_complete = bool(approval_ids)`, `attestation_complete = bool(compatibility_attestation_refs)`). id 를 기록으로 풀거나, 유효기간·서명을 검증하는 코드는 없다. ADR-002-014 §13 의 3단계(기한 있는 독립 승인)·7단계(인증된 적합성 확약)·8단계(Safety Commit Log 커밋)는 이 저장소에 구현돼 있지 않다 — 활성화는 「문서 + digest 일치」 수준이다(2026-09-15 venue plan §1 공시). **따라서 이 기록의 무결성은 이 PR 의 리뷰에만 기댄다.**

## §1 승인 — `op-approval-20261024-stock-005930-activation-g1`

| 항목 | 값 |
| --- | --- |
| 승인자 · 날짜 | operator (System Owner) · 2026-10-24 |
| 트리 · 활성화 | `cp3-setup-d-stock-005930` · `tos-paper-stock-005930-activation-g1` (profile_generation 1, predecessor 없음) |
| 범위 | `MOCK_STOCK_ORDER` 만 (KIS 모의투자 주식 주문 · REAL 경로 없음). paper / LONG / SHORT 는 `[]` 그대로 |
| 묶음 | envelope `tos-paper-envelope-g1`@1 · profile `tos-paper-profile-g1`@1 · 정책 다섯(VENUE / ORDER_CONSTRUCTION gen 4 / AGGREGATE_RISK / ACTION_FLOW / CRITICAL_INPUT) — 세션마다 렌더가 `members:` 로 채운다 |
| 유효 | envelope · profile · 이 활성화의 다음 세대 또는 철회 중 먼저 오는 때까지 |

## §2 적합성 확약 — `compat-20261024-stock-005930-g1`

| 항목 | 값 |
| --- | --- |
| 소비자 | `tos_runtime`, release `expected_code_digest` = 렌더 시점의 `release.yaml` 핀(`tools/tos_redigest.py --check` 가 측정 트리와 같음을 보장) |
| 근거 | #956 의 렌더 트리 kis-mock 부팅 시험(`tests/unit/scripts/test_render_stock_tenant_mock_boot.py`) — 이 트리의 실제 렌더를 이 런타임이 부팅해 17 항목을 평가 |
| 빠진 것 | 계좌가 채워진 정책 digest 는 적지 않는다 — 10자리 계좌가 든 템플릿의 sha256 은 역산 가능하다. 세션별 digest 는 호스트의 `RENDERED.json` 에 있다 |

## 되돌림

두 목록을 `[]` 로 되돌리면 B4 상태(1단계 전 거부)로 돌아간다. 다음 세대(정책·프로필 변경)는 새 id 로 새로 승인한다.
