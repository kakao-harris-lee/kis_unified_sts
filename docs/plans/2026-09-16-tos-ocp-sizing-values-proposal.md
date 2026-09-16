# OCP sizing 값 제안표 — 운영자 승인 요청 ((a′) 웨이브 §6 ①)

- **요청**: `config/tos_runtime/paper/order_construction_policy.yaml` 에 `SizingBound` 7필드 + `admitted_quantity_bases` 를 기계가 읽는 값으로 채우는 **policy_generation 2** 를 승인해 주십시오.
- **근거**: (a′) 계획(`docs/plans/2026-09-16-tos-aprime-envelope-order-shape-plan.md`) §6 ① · `SizingBound` 독스트링이 「RFC-002 §9.1:553 이 **Order Construction Policy 거버넌스**를 construction rule 의 공급자로 만든다」고 지목하는데, **공급 경로가 없다**(현 OCP 인스턴스에 sizing 값 0건).
- **선례**: venue 웨이브 §6 ② 제안표(2026-09-16 채택) 와 같은 형식·같은 등급 체계.

## 0. 이 승인이 **하지 않는** 것 — 먼저 읽어 주십시오

제안표의 값어치는 「무엇을 열어주는가」가 아니라 「무엇을 열어주지 **않는가**」가 분명한 데 있습니다.

| 오해할 수 있는 것 | 실제 |
|---|---|
| 「값을 채우면 주문이 나가기 시작한다」 | **아니오.** `venue_constraint_policy.yaml` 의 `price_min`/`price_max`/`max_quantity` 가 **원천 부재로 null** 이고(P0-2 `price_band_tick_lot_and_quantity_semantics: UNKNOWN`), `derive_order_size` 규칙 6/8 이 그 불완전한 venue 제약에서 **거부**합니다. 송신은 여전히 0 입니다. |
| 「이걸로 D0-5 UNBOUND 가 해소된다」 | **아니오.** 검사기 실측: `D0-5[construction]=UNBOUND (risk_budget:UNBOUND; …)` · `D0-5[records]=UNBOUND (…)`. 이는 **VERIFICATION-PROFILE-002 키 등록** 문제이고 OCP 인스턴스 값과 별개입니다(§3 발견 2). 현재 `RESULT: GREEN (violations=0)` — UNBOUND 는 위반이 아니라 추적 상태입니다. |
| 「Bounds-Approver 라운드가 필요하다」 | **아니오.** 일곱 이름 전부 VERIFICATION-PROFILE-002 에 **0건**(실측). `SizingBound` 프로즈도 「VER-002 키가 아니므로 P0-1 사안이 아니다」라고 명시 — **OCP 거버넌스가 승인 주체**입니다. |
| 「실전 리스크 계산을 승인하는 것이다」 | **아니오.** `risk_budget`/`per_unit_risk` 는 아래에서 **구조 인코딩**(비율 = 1 계약)으로 제안합니다. 경제적 캘리브레이션은 별도 결정입니다(§4 ①). |

## 1. 등급 체계 (venue 웨이브와 동일)

- **A** — 이 저장소에서 **이미 승인된 인스턴스**에서 파생. 새 판단 0.
- **B** — 거래소 공식 계약 사양(대조 가능한 외부 사실).
- **C** — 레거시 로컬 설정값 또는 구조적 placeholder. 브로커 조회 원천 없음.

## 2. 제안표

| 필드 | 제안값 | 등급 | 근거 | 틀렸을 때 |
|---|---|---|---|---|
| `max_quantity` | **1** | **A** | `config/tos_runtime/paper/aggregate_risk_policy.yaml` 이 이미 승인한 유효 한도 — 「paper trades one contract」, `INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL` in CONTRACTS, effective limit **1**. 이보다 큰 값을 넣으면 step 2 가 만든 것을 step 6 이 거부하므로 **불일치가 낭비**가 됩니다 | 1 초과 → 총량 게이트에서 거부(안전 방향) · 1 미만 불가(min 1) |
| `min_quantity` | **1** | **B** | 계약 단위 1. `venue_constraint_policy.yaml:126` 이 이미 `min_quantity: 1` | 0 이하는 `SizingBound` 가 거부 |
| `lot_size` | **1** | **B** | 계약 단위 1. `venue_constraint_policy.yaml:125` 가 이미 `lot_size: 1`(등급 B 로 표기) | venue lot 과 어긋나면 규칙 8 에서 거부 |
| `lot_rounding` | **`EXACT_MULTIPLE_REQUIRED`** | **A** | OCP **자신의 산문**이 이미 선언: `price_tick_lot_quantity_and_rounding_rules: ["no silent rounding — construction denies an off-grid shape rather than rounding it"]`. 커널 열거형의 두 멤버 중 이 문장에 대응하는 것은 `EXACT_MULTIPLE_REQUIRED` 뿐(`FLOOR_TO_LOT` 은 「정책이 명시한 내림」) | `FLOOR_TO_LOT` 을 고르면 OCP 산문과 모순 — 같은 문서가 두 말을 하게 됨 |
| `risk_budget` | **1** | **C** | 구조 인코딩. `raw = risk_budget / per_unit_risk`(`construction.py:321`)이고 `lot_rounding=EXACT_MULTIPLE_REQUIRED`·`lot_size=1` 이므로 **비율이 정확히 1이어야** 승인된 1계약 한도와 일치. 경제적 캘리브레이션 아님 | 비율 ≠ 1 → 파생 수량이 1 이 아니게 되고 §2 `max_quantity` 와 어긋나 거부 |
| `per_unit_risk` | **1** | **C** | 위와 한 쌍. 단위는 「계약 환산」으로 선언 | 위와 동일 |
| `max_notional` | **null** | — | **선택적 상한**입니다(`construction.py:525` 이 `is not None` 일 때만 검사 — §3 발견 1). 승인된 명목 원천이 없고, 구속 제약은 `max_quantity: 1` 입니다. 없는 근거로 숫자를 만들지 않습니다 | null 은 「명목 상한 없음」 — 계약 수 1 이 구속하므로 실효 무제한은 아니나, **명목 자체를 독립으로 막지는 않음**(공시 대상) |
| `admitted_quantity_bases` | **`["RISK", "ZERO_POSITION"]`** | **C** | `ZERO_POSITION` 은 커널 예약 토큰(`dsl/proposal.py:49` `FLAT_QUANTITY_BASIS`). `RISK` 는 현재 픽스처가 쓰는 진입 basis. **주의**: 실제 값은 배포된 전략 파일이 무엇을 내는지에 달렸고, `tos/runtime/config/strategies/example.strategy.yaml:55` 의 `quantity_basis` 는 아직 **named-TBD `null`** 입니다 | 빈 집합은 **아무것도 승인하지 않음**(∅ fail-closed) · 전략이 내는 토큰이 집합 밖이면 규칙 2 에서 거부 |

## 3. 준비 중 발견한 것 2건 (커널 문서 문제 — 이 웨이브 범위 밖, 기록만)

1. **`SizingBound` 독스트링이 과잉 진술합니다.** 「A `None` on any field is a denial at `derive_order_size` — never a default」(`records.py:136-137`)라고 하지만, `max_notional` 은 `is not None` 가드 안에서만 검사되므로(`construction.py:525`) **`None` 이 denial 이 아닙니다.** 위 표에서 `max_notional: null` 을 제안할 수 있는 근거이며, 독스트링 쪽이 부정확합니다.
2. **같은 독스트링이 스스로와 모순되고, 그 모순을 기계가 읽습니다.** 프로즈는 「이 이름들은 VERIFICATION-PROFILE-002 키가 **아니다** — P0-1 사안이 아니다」(`:130-134`)라고 하는데, 같은 독스트링의 `VER-002-KEYS:` 줄(`:143`)이 그 일곱 이름을 **의존 키로 선언**합니다. 이 줄은 `tools/tos_completion_status.py`(D-1 선언 파서, `:3656`)가 읽고, 그래서 `D0-5[construction]`/`[records]` 가 `UNBOUND` 로 뜹니다. 실측으로 프로즈가 맞습니다 — 일곱 이름 전부 프로파일에 **0건**. 따라서 `VER-002-KEYS:` 선언 쪽이 잘못입니다(선언을 `NONE` 으로 정정하거나 키를 실제 등록하거나). **현재 GREEN 이므로 급하지 않으나, 이 승인이 그것을 해소한다고 오해하지 않도록 기록합니다.**

## 4. 운영자 선택지

1. **`risk_budget`/`per_unit_risk` 의 성격** — (a) 제안대로 **구조 인코딩**(1/1, 「정확히 1계약」의 기계 표현, 경제 모델 아님을 OCP 주석에 명시) · (b) **실제 KRW 캘리브레이션**(계약당 리스크 = 스톱 거리 × 승수). (b) 는 스톱 거리와 계약 승수의 **승인된 원천이 필요**합니다 — `config/arbitrage.yaml:11` 의 `multiplier: 50000` 은 레거시 로컬 설정(등급 C)이고 같은 파일의 `tick_size: 0.05` 와 조합하면 KOSPI200 표준/미니 사양이 섞여 있어 **어느 계약인지 단정할 수 없습니다.** 추천은 (a) — 없는 원천으로 숫자를 만들지 않고, 나중에 원천이 생기면 새 세대로 올립니다.
2. **`admitted_quantity_bases`** — 배포 전략 파일이 확정되면 그 토큰으로 맞춰야 합니다. 지금 `["RISK", "ZERO_POSITION"]` 로 두고 전략 확정 시 재검토할지, 전략 파일을 먼저 채울지.
3. **세대 이행 절차 확인** — 승인 시 제가 수행할 것: `policy_generation: 2` · `_runtime.construction` 블록 추가 · `canonical_digest` 재계산 → `tos-runtime print-policy-digests --config-dir …` 출력 → **`safety_activation.yaml` `members:` 는 운영자 손으로 기입**(기존 관례). 이 마지막 단계만 운영자 작업입니다.

## 5. 승인 후 즉시 착수할 것

(a′) 웨이브 레인 A(OCP 세대 2 + 로더 확장) → B(봉투 발행자) · C(order_shape 원천화) 병렬 → D(결선·e2e). 한 웨이브로 진행(운영자 2026-09-16 결정).
