# TOS (a′) 잔여 웨이브 계획 — `envelope` · `order_shape` 원천화 (`run` 마지막 차단)

- **상위**: `compose/cli.py` 차단 (a′) 「Still no production source: `envelope`(needs IAP authoring) · `order_shape`(needs a strategy-carried shape) + `_wiring.py` 의 `intent_id`/`intent_version`/`envelope_id`/`command_id`/`generation` 리터럴」 · 운영자 2026-09-16 「다음 = (a′) 잔여 먼저」(틱 원천 계획 §6 ⑥).
- **선행**: 틱 원천 웨이브 전건 MERGED → main `24f6c217`/`9577e947`(2206 tests). (c) 해소로 **(a′) 의 `price` 항은 이미 구조 해소**됨 — 남은 것은 `envelope` 과 `order_shape`.
- **저작**: 세션 모델 단독 · 커널 diff 0 목표.
- **브랜치**: `feat/tos-aprime-plan`(워크트리 `../kis_unified_sts-aprime`).

## 0. 서베이 실측 (요지)

| 항목 | 실측 (`file:line`) | 함의 |
|---|---|---|
| 체인은 이미 결선돼 있다 | `construct_candidate_command` 가 **이미** `ApprovedIntentContract` 를 만든다(`construction.intent`) · step 4 의 `_envelope_equivalent_provider`(`_wiring.py:613-635`)가 운영자 결정의 `approved_intent_envelope_digest` 를 그 **실제** intent digest 와 `exact_binding_holds` 로 대조 | **(a′) 는 「없는 기구를 만드는」 일이 아니다** — 기구는 있고 **입력이 리터럴**이다 |
| 리터럴 위치 | `_wiring.py:539-546`: `intent_id=f"intent-{account}-{instrument}"` · `intent_version="intent-v1"` · `envelope_id="compose-envelope"` · `command_id=f"cmd-{account}-{instrument}"` · `generation=1` | 정체성이 **제안에서 파생되지 않고 날조**된다 |
| IAP 런타임 | `IntentRegistry`(propose/approve/consume·`authority/iap.py:533`) · 운영자 승인 파일 로더(`:333` · 0600+owner+환경라벨 byte-exact · **zero auto-approval**) 전부 실물 | IAP 쪽은 **이미 프로덕션** — (c) 의 CIS 부재와 다르다 |
| `ApprovedIntentContract` 발행자 | 프로덕션 **0건**. 커널 테스트와 `runtime/tests/compose/conftest.py` 뿐 | 런타임이 «권한 축의 landing point»를 직접 채운 적이 없다 |
| 권한 축의 정본 | `ApprovedIntentContract` 독스트링: 「ADR-002-020 §8 필드 집합의 **landing point**」 · 「구체 authorized-axis 값은 Phase-0 주입이라 `_REQUIRED_COVERED` 에서 제외 — **없는 축은 소비 술어에서 fail-closed**」 | 축을 비워둬도 ISSUED 는 되지만 **소비 시점에 막힌다** |
| `sizing_bound` 의 소유자 | `SizingBound` 독스트링: 「RFC-002 §9.1:553 이 **Order Construction Policy 거버넌스**를 construction rule 공급자로 만든다」 · 「저자가 수량을 건네줄 수 없다 — **quantity 필드가 없다**」 | 수량은 선언이 아니라 **경계값에서 파생**되어야 한다(구조적 봉인) |
| 그런데 OCP 실파일에 값이 없다 | `config/tos_runtime/paper/order_construction_policy.yaml` — 규칙이 **산문 문자열**(`direction_side_and_position_effect_rules: ["NEW_LONG↔BUY/OPEN, …"]` · `price_tick_lot_quantity_and_rounding_rules: ["no silent rounding …"]`) · `_runtime` 블록은 `canonicalization_version`/`wire_codec` 뿐 · **risk_budget/per_unit_risk/lot_size/min·max_quantity/max_notional 어디에도 없음**(DR-0002 §2.3 v1 coverage = policy_id/generation/version ONLY) | **거버넌스 문서가 산문으로 선언한 것을 기계가 읽지 못한다** — 이 웨이브의 본체 |
| `order_shape` 의 실제 잔여 | `_shape_for`(`egressgw/construction.py:1074-1098`)는 **`price` 만** value surface 로 덮는다. `quantity`·`order_type`·`tif`·`side`·`position_effect`·`silently_rounded` 는 주입값 그대로 | price 는 (c) 가 해소 · 나머지 6필드가 잔여 |
| ★ **커널 자신의 원칙이 shape 에는 적용되지 않는다** | 커널은 `DERIVED_AXES = {QUANTITY, PRICE, UNIT}`(`egressgw/records.py:267-269`)를 **파생 소유**로 못박고, 봉투가 그 축을 선언하면 **「어느 값이 이기는지 모호해진다」는 이유로 거부**한다(`_no_derived_axis_is_pre_declared` · ADR-002-020 §10:284 「ambiguity is denial」). 그런데 **`OrderShapeFields.quantity` 는 같은 축인데 호출자가 선언**하고, 아무도 파생값과 대조하지 않는다 — venue 결정은 `candidate_command` 를 **식별자 결속에만** 쓰고(`venue/service.py:330-350`) `tos/src/tos/venue/predicates.py` 는 이를 **아예 참조하지 않는다**(grep 0건) | **venue 게이트가 검사하는 수량과 실제 보낼 수량이 갈릴 수 있다.** 커널이 봉투에 대해 막은 바로 그 모호성이 shape 경로로 열려 있다 |
| 수량을 읽을 수 있는가 | `CanonicalBrokerCommand.axis_value(ConformanceAxis.QUANTITY)` 가 공개 접근자(`ioc/records.py:349`) · `VenueConstraintStage` 는 `shape` 를 **생성자 인자**로 받는다 | **커널 편집 없이** 런타임이 fold #2 에 파생 수량을 실은 shape 를 넘길 수 있다 — §6 ② 는 저작 중 실측으로 해소 |
| 시점은 맞는다 | `VenueServiceStage.__call__`(`_venue_wiring.py:390-424`)이 fold #1 뒤에 `self._construction_stage.construction` 을 읽는다 — step 2 가 step 3 보다 먼저 돈다 | **파생 수량을 shape 에 흘려넣을 데이터가 이미 그 시점에 있다** |
| 크기 제약 | `_wiring.py` **1122행**(예산 1000 초과 · 등재 예외 `decomposition_order: 30`) · `cli.py` 정확히 **1000행**(헤드룸 0) | 두 파일 모두 **증설 불가** — 새 모듈로 빼야 한다 |

## 1. 목표 · 범위 · 비범위

**목표**: `envelope` 과 `order_shape` 를 **거버넌스 문서와 파생에서 원천화**한다. 한 문장으로: **기계가 OCP 가 이미 산문으로 선언한 것을 읽게 하고, 파생이 이미 계산한 것을 선언으로 중복하지 않게 한다.**

**범위**: OCP 에 기계가 읽는 `_runtime` 구성 규칙 추가(**새 policy generation**) · OCP 로더 확장 · `ProposedConstructionEnvelope` 발행자(런타임 신규) · `ApprovedIntentContract` 정체성 파생 · `order_shape` 6필드 원천화(특히 **수량 = 파생값**) · `_wiring.py` 리터럴 5종 제거 · compose 결선 + e2e · `cli.py` (a′) 문언.

**비범위**: 커널 편집 · IAP 승인 **정책** 변경(운영자 파일 흐름은 이미 프로덕션이고 건드리지 않는다) · (b′) 잔여(단일 원천 포지션·명목/마진 차원) · (c2) 실 시세 어댑터 · 다심볼 · **`run` 의 데몬화**(차단 해소와 데몬 루프는 다른 일 — §2 결정 8).

## 2. 결정 (초안 — 레인 저작 전 운영자 확인 대상은 §6)

1. **OCP 가 정본이다. 새 필드가 아니라 새 세대다.** 산문 규칙을 기계가 읽는 값으로 옮기되 **기존 산문은 남긴다**(사람이 읽는 근거). `_runtime` 블록에 `construction:` 하위로 `sizing`(risk_budget·per_unit_risk·lot_size·lot_rounding·min_quantity·max_quantity·max_notional·admitted_quantity_bases) · `axes`(order_type·tif·environment) · `action_class_map`(NEW_LONG→side/position_effect …) · `effect_dimensions` 를 추가. **policy_generation 2 · canonical_digest 재계산 · `safety_activation.yaml` members 재기입** — 운영자 작업이 끼는 지점(§6 ①).
2. **`order_shape.quantity` 는 선언하지 않고 파생에서 받는다 — 커널 편집 없이 가능함을 실측했다.** 런타임 `VenueServiceStage` 가 fold #1 뒤에 `construction.command.axis_value(ConformanceAxis.QUANTITY)` 를 읽어 그 수량을 실은 shape 를 fold #2 의 `VenueConstraintStage(shape=...)` 에 넘긴다. `VenueConstraintStage` 가 shape 를 생성자로 받으므로 **커널 diff 0**. 근거는 커널 자신의 원칙이다 — `DERIVED_AXES` 가 QUANTITY 를 파생 소유로 지정하고 봉투의 중복 선언을 「ambiguity is denial」로 거부하는데, shape 만 예외일 이유가 없다. 파생이 수량을 내지 못한 attempt 는 shape 수량을 **`None`**(구조적 UNKNOWN)으로 두고 주입 리터럴로 되돌아가지 않는다.
3. **정체성은 파생한다.** `intent_id`/`envelope_id`/`command_id` 는 제안·capsule·attempt 에서 결정적으로 파생(예: proposal digest + attempt 좌표). `intent_version`/`generation` 은 OCP 세대에 결속. 날조 리터럴 0.
4. **`silently_rounded` 는 attestation 이 아니라 관측이어야 한다.** OCP 가 「no silent rounding — 구성은 off-grid shape 를 반올림하지 않고 거부한다」를 선언한다. 런타임이 **그 사실을 관측**해 채운다(틱 그리드 대조). 관측 불가면 `None`(제한적) — `False` 를 찍지 않는다.
5. **새 모듈.** `_wiring.py`(1122) 와 `cli.py`(1000) 둘 다 증설 불가 → `compose/_envelope_wiring.py` 신설. 크기 예외 신규 등재 금지.
6. **e2e 는 (c) 의 방식을 따른다.** 「실 step-2 가 주입 리터럴이 아니라 거버넌스 값을 썼다」를 실 스테이지 상태로 실증 — (c) 의 `derivation.price` 단언과 같은 형태.
7. **`run` 차단 문언.** (a′) 해소를 기록하되 **데몬 루프 부재**를 별도 항목으로 남긴다. 「(a′) 해소」와 「`run` 가동」을 같은 문장에 쓰지 않는다 — (c) 웨이브의 규율 계승.
8. **범위 경계**: 이 웨이브는 `run` 의 **차단 목록**을 비우는 것까지다. `run` 이 실제 데몬으로 도는 것(`run_forever` 결선 · 신호 처리 · 종료 규약)은 **후속**.

## 3. 기각 대안 (초안)

| 대안 | 기각 사유 |
|---|---|
| `envelope` 을 새 YAML 로 분리 | `SizingBound` 독스트링이 OCP 거버넌스를 공급자로 지목(RFC-002 §9.1:553) — 두 번째 문서는 정본을 쪼갠다 |
| OCP 를 in-place 편집 | 정책은 세대 불변 — digest 가 바뀌면 새 세대다(OCP 자신의 주석이 wire_codec 예로 같은 말을 한다) |
| `order_shape.quantity` 를 계속 선언 | venue 게이트가 **보내지 않을 수량**을 검사한다 — 서베이 ★ 항목 |
| 수량 불일치를 로그만 남기고 통과 | 「ambiguity is denial」(ADR-002-020 §10:284) 과 정면 충돌 |
| `silently_rounded=False` 를 계속 주입 | 관측 가능한 사실을 선언으로 두는 것 — 틱 원천 웨이브가 필드 상태에서 이미 겪은 부류 |

## 4. 레인 (초안)

| 레인 | 파일(배타) | 의존 |
|---|---|---|
| 계약 | `compose/_envelope_wiring.py` 시그니처 + 계획 | 없음 |
| A | OCP 템플릿/실파일 세대 2 · OCP 로더 확장 · 대응 tests | 계약 |
| B | `ProposedConstructionEnvelope` 발행자 + 정체성 파생 · tests | 계약 |
| C | `order_shape` 6필드 원천화(수량 대조 포함) · tests | 계약 |
| D | compose 결선 · `cli.py` 문언 · e2e | A∧B∧C |
| 리뷰 | 전 PR `code-reviewer`(sonnet) · **A 는 `contract-keeper`** (거버넌스 문서 계약 변경) | PR 별 |

## 5. 종료 조건 · 뮤테이션 (초안)

- 실증: (1) `ConstructionConfig.envelope` 주입 없이 부팅 — 봉투가 **OCP 에서** 구성됨 (2) e2e 에서 실 step-2 의 sizing 이 OCP 값과 일치(리터럴 아님) (3) **shape 수량 == 명령 수량**, 불일치를 심으면 거부 (4) `side`/`position_effect` 가 OCP `action_class_map` 에서 나옴 — 미러(NEW_SHORT) 동일 (5) `silently_rounded` 가 관측에서 나오고 관측 불가 시 `None` (6) 정체성 5종에 날조 리터럴 0(AST 핀) (7) OCP 세대 불일치 → 부팅 거부.
- 뮤테이션: M1 수량 대조 제거 → (3) red · M2 `action_class_map` 무시하고 리터럴 복원 → (4) red · M3 `silently_rounded=False` 하드코딩 → (5) red · M4 정체성 리터럴 복원 → (6) red · M5 OCP 세대 검증 제거 → (7) red.
- 게이트: firewall · size budget(**신규 예외 0**) · ruff/black/mypy · 런타임+커널 스위트 · **커널 diff 0**.

## 6. 운영자 확인

1. **OCP 세대 2 로의 이행** — 기계가 읽는 구성 규칙을 담으려면 `policy_generation: 2` + `canonical_digest` 재계산 + `safety_activation.yaml` `members:` 재기입이 필요하다(운영자 손작업). 값 자체(risk_budget·per_unit_risk·lot_size·min/max_quantity·max_notional)는 **승인된 적이 없다** — `SizingBound` 독스트링이 「VERIFICATION-PROFILE-002 키가 아니므로 P0-1 사안이 아니고, OCP 가 아직 아무것도 비준하지 않았다」고 명시. **제안표를 만들어 올릴지, 운영자가 직접 채울지** 결정 필요.
2. ~~수량 경로가 커널 편집을 요구하는가~~ — **불요로 판명(저작 중 실측)**. `CanonicalBrokerCommand.axis_value(ConformanceAxis.QUANTITY)` 가 공개 접근자이고 `VenueConstraintStage` 가 shape 를 생성자로 받으므로 런타임만으로 된다. 운영자 조치 없음.
3. **웨이브 분할** — `envelope`(레인 A·B)과 `order_shape`(레인 C)은 OCP 를 공유하지만 독립 착지가 가능하다. 한 웨이브로 갈지, 둘로 쪼갤지.
4. 다음 순서(잔여): `run` 데몬화 → (c2) 실 시세 어댑터 → 브로커 증인(P-BAL)/band 원천 → 실 HSE 인스턴스 → 커널 라운드 #4.

## 7. 착지 기록

(웨이브 완료 후 채움)
