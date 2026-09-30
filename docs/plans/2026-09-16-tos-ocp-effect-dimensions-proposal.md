# OCP `effect_dimensions` 값 제안표 — 운영자 승인 요청 ((a′) 웨이브)

- **일자**: 2026-09-16 · **상위**: `2026-09-16-tos-aprime-envelope-order-shape-plan.md`
- **선례**: `2026-09-16-tos-ocp-sizing-values-proposal.md`(PR #717, 채택) — 같은 경로를 따른다.

## 0. 이 승인이 하지 않는 것

- 새 리스크 한도를 만들지 않는다. 아래 값은 **이미 승인된 한도를 참조**할 뿐이다.
- 경제적 판단을 하지 않는다. notional 차원은 **제안하지 않는다**(§3).
- 실거래를 열지 않는다. 실선물 계좌 무증거금·실주문 영구 차단은 그대로다.

## 1. 왜 지금 필요한가 — 실측

레인 B 가 봉투를 거버넌스에서 소싱하자 **e2e 47건이 실패**했다. 근본 원인 하나:

| 지점 | 실측 |
|---|---|
| OCP 산문 | `economic_effect_and_capacity_rules: []` · `economic_effect_envelope_schema_versions: []` (`order_construction_policy.yaml:68,89`) |
| 기계 판독형 | `effect_dimensions: []` — **문서에 충실**. 레인 A 는 지어내지 않았다 |
| 커널 | 빈 components → `StageOutcome.UNKNOWN`(`engine/adapters.py:385-391`) |
| 시퀀서 | 「오직 명시적 ADMIT 만 전진」 → `HaltReason.STAGE_UNKNOWN` **정지**(`engine/sequencer.py:502`) |

**47건이 green 이던 유일한 이유는 픽스처(`tests/compose/_fixtures.py:387-399`)가 문서에 없는 값 둘을 주입했기 때문이다.**

### 1.1 주입값은 두 겹으로 팬텀이었다

픽스처는 `dimension_id="notional"` 과 `"units"` 를 썼다. 그런데 RCL 은 효과 벡터를
**`dimension_id` 로 조회한다**(`rcl/predicates.py:104-105` — `effect.magnitude(dimension_id)`),
그리고 ARP 가 관장하는 id 는 `INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL`
(`aggregate_risk_policy.yaml:58,107`)이다. **둘 다 맞지 않는다.**

즉 주입값은 step 5 를 ADMIT 로 통과시키면서도 **용량 조회에서는 아무것도 찾지 못했을**
값이었다. 「통과했다」가 「작동했다」가 아니었던 사례가 하나 더 있었던 셈이다.

## 2. 제안 — 단일 차원, 전부 기존 승인 문서에서 파생

```yaml
effect_dimensions:
  - dimension_id: "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"
    basis: "QUANTITY"
    unit: "CONTRACTS"
    scale: "1"
```

| 필드 | 값 | 등급 | 파생 근거 |
|---|---|---|---|
| `dimension_id` | `INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL` | **A** | ARP 가 이미 관장하는 **유일한** 차원(`aggregate_risk_policy.yaml:58`). RCL 이 이 id 로 조회하므로(`rcl/predicates.py:105`) 다른 값은 용량을 못 찾는다. 새 판단 0 |
| `basis` | `QUANTITY` | **A** | `EffectBasis` 는 `QUANTITY`/`NOTIONAL` 둘뿐이고, ARP 차원의 단위가 CONTRACTS 이므로 QUANTITY 가 유일하게 정합. `derive_economic_effect_envelope`(`construction.py:793-795`)가 QUANTITY 에 파생 수량을 그대로 넣는다 |
| `unit` | `CONTRACTS` | **A** | ARP `unit CONTRACTS`(`:58`) · VCP `_runtime.quantity_unit: "CONTRACTS"`(`venue_constraint_policy.yaml:136`). 세 번째 사본이 아니라 **같은 승인값 참조** |
| `scale` | `"1"` | **A** | 계약은 개수로 센다. 배율 없음 |

**등급 A = 이미 승인된 문서에서 파생, 새 판단 없음.** sizing 제안표의 A/B/C 척도와 동일.

### 2.1 ⚠ 저작 전 실측 필요 (레인 A 몫)

ARP 가 같은 차원을 **두 가지 표기**로 적는다 — `governed_dimensions: ["LONG_SHORT_DELTA_DIRECTIONAL"]`(`:99`, 접두사 없음)와 `dimension_ids: "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"`(`:107`, 접두사 있음). **RCL 조회에 실제로 쓰이는 쪽을 실측해 그 철자를 쓸 것.** 추정 금지 — 틀리면 §1.1 의 팬텀을 그대로 재생산한다.

## 3. 기각 — notional 차원

**제안하지 않는다.** 두 이유:

1. **승인된 notional 원천이 없다.** sizing 제안표가 `max_notional: null` 을 채택한 근거와 같다 — mark 원천 부재.
2. **선언하면 오히려 다시 막힌다.** `derive_economic_effect_envelope:796-797` 이 NOTIONAL 의 magnitude 를 `quantity * price` 로 계산하는데 `price is None` 이면 `None` 을 넣고, 그 경우 어댑터가 `unknown_dimensions` 로 **다시 UNKNOWN** 을 낸다. 가격이 항상 있다는 보장이 없는 한 notional 선언은 step 5 정지를 되살린다.

## 4. 운영자 결정

| # | 항목 | 추천 |
|---|---|---|
| ① | 위 단일 차원 채택 | **채택** — 전 필드 등급 A |
| ② | notional 차원 | **미선언 유지** (§3) |
| ③ | 47 e2e 기대값 | 픽스처 주입 제거 후 **실 거버넌스 값으로 통과**하는지 실측. 여전히 실패하면 그 사유를 §7 에 정직 등재 |

## 5. 이 표가 보장하지 않는 것

- step 5 가 ADMIT 로 바뀐다는 보장이 **아니다.** `derive_economic_effect_envelope` 는 `outcome is DERIVED` 이고 `quantity is not None` 일 때만 magnitude 를 채운다(`construction.py:791-795`). 파생이 거부되면 magnitude 는 `None` 이고 어댑터는 여전히 UNKNOWN 이다.
- 따라서 이 표의 채택은 **필요조건이지 충분조건이 아니다.** `run` 구동 여부는 레인 D e2e 실측으로만 말할 수 있다.
