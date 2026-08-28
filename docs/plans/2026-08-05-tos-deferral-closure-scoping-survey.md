# TOS 이연 3건 closure 아크 — 스코핑 서베이 (2026-08-05)

**목적**: 수직 슬라이스 #1 완결 시점(#31~#35)에 비준·기록된 정직 이연 중, 세션 A
증거 트랙(EV-L1 실행·EV-L2 fault injection·P0-2)과 겹치지 않는 3건 —
① venue_shape/coordinates 값-표면 재-소싱, ② D-E2 Context Integrity Service,
③ 다심볼(per-scope last-reference) — 의 closure 설계 계약(#36~#38) 저작 입력물.

**성격**: 비규범 서베이. 어떤 EV도 닫지 않고 어떤 비준도 구성하지 않는다.
읽기 전용 조사(파일 수정 0건), 테스트 실행 1회
(`PYTHONPATH=tos/src .venv/bin/python -m pytest tos/tests/slice tos/tests/marketfeed -p no:cacheprovider -q`
— 206 passed, exit 0).

**베이스라인**: HEAD `5ebc61f8`, 워킹트리 clean. 갭-closing 구현은 INDEX 기재
`f859b3ba` → 실제 트리에서는 `5e26f47d`
(feat(tos): close vertical-slice gaps 1-4 (design #35) + #34 §0.3 lockstep).
이후 tos/ 를 건드린 커밋은 세션 A 레인(`eb92ea46` EV-L2)과 코퍼스 리마디에이션
(`0ba03639`/`15d48f72`/`00972702`/`a1a92b9f`)뿐.

---

## 이연 ①: venue_shape / coordinates 값-표면 재-소싱

### A. 이연 정의 원문

**#35 §10-3** — `docs/plans/2026-07-29-tos-slice-gap-closing-design.md:553-557`:

> 3. **값 표면 단위 일관성(minor-unit vs 실가격)·deterministic-float 투영·venue_shape.price 및
>    authorized_coordinates의 값-표면 재-소싱(MAJOR-3)** — GAP-3은 사이징/command 가격만 값-표면 재-소싱
>    하고, venue admissibility의 shape 가격(`venue_shape().price=4,200`)과 egress 좌표는 fixture 잔존
>    한다(어떤 verify 경로에도 무저촉 — §4.4 4-경로 grep 실증). 전부 D-E2 marketfeed 값-표면 소관
>    (#32 §2.5)·명시 이연.

**부착된 경계 지시** (`:326-334`, §4.4):

> **⚠ 슬라이스 내부 비정합 정직 명기(MAJOR-3·숨기지 않기)**: … GAP-3은
> **사이징/command 가격**만 값-표면 재-소싱하고 **venue_shape.price·authorized_coordinates는 재-소싱
> 하지 않는다**. … GAP-3은 값을 계보와 함께 흘릴 뿐, shape/coordinate 가격 정합이나 단위 정합
> (minor-unit 4,499,000 vs 4,200·#32 §2.5)을 **주장하지 않는다**.

**접합점 지정** (`:604-606`, §12 리스크):

> **shape/coordinates 비정합(MAJOR-3·리스크)**: 슬라이스는 venue가 4,200-shape를 admit하는데 command는
> 4,499,000인 내부 비정합을 갖는다(… §10-3 이연). **미래 slice가 venue admissibility를 값-표면 gated로
> 강화하면 이 fixture 재-소싱이 접합점이다.**

**선제 반론에서의 재확인** (`:586-588`, §11-6): "venue_shape는 별개 fixture(§4.4). 단위 일관성은
D-E2 이연이며 GAP-3은 값+계보만 흘린다."

**무해성의 4-경로 실증**(`:310-325`) — closure 시 뒤집어야 할 전제: item 11은
`context.order_shape`만 venue 제약에 대조(command 가격 미검사)·item 13은 CONFORMANT만·item 17
`exact_binding_holds`는 가격 직접 대조 0·`outbound_binding_mismatch`는 `derivation.quantity/price`에만 대조.

**"발명 금지" 형태의 명시 금지 지시는 이 건에 없다** — GAP-4의 "RCL release 발명 금지·capacity deny
유지"(`:549-550`, `:386-412`)에 상당하는 문장은 ①에 부착되어 있지 않다. 대신 **수치 소유권 게이트**가
경계 역할을 한다: #34 §9(`docs/plans/2026-07-29-tos-egressgw-brokeradapter-design.md:718`) —
"broker-specific bound … **미결**(KIS 초안 §7 item3 `hard_limits: {}`·null 다수)·provisional",
`:717` sizing bound = P0-1 미승인. 즉 `price_min/price_max/tick_size`는 **P0-2(Broker Capability
Profile INSTANCE) 소관 사실**이며 임의 조정은 인간 게이트 밖 발명이 된다.

**#32 §2.5 제약**(`docs/plans/2026-07-29-tos-marketfeed-design.md:341-343`): "**분수 수량이 불가피하면
deterministic float 투영만** … canonical 값이 exact 정수/deterministic-float로 투영 불가면 값을
**노출 안 함**(구조적 UNKNOWN·fail-closed)".

### B. 현재 코드 상태 (재-소싱 "전" 실제 배선)

| 표면 | 현재 값의 출처 |
|---|---|
| `SendBoundaryContext.order_shape: OrderShapeFields \| None` | `tos/src/tos/egressgw/records.py:518` — **전량 호출자 주입**. 팩토리 파라미터 `records.py:610`, 통과 대입 `records.py:760` |
| `SendBoundaryContext.venue_shape_constraints` | `records.py:519` / `:611` / `:761` — 동일하게 주입 |
| `SendBoundaryContext.authorized_coordinates: EgressCoordinateSet \| None` | `records.py:546` / `:618` / `:776` — 동일하게 주입 |
| 게이트웨이 소비 | `gateway.py:830-831`(item 11 fold에 `shape=context.order_shape`, `constraints=context.venue_shape_constraints`), `gateway.py:1172`·`:1255`(item 17 좌표) |
| 슬라이스 실제 값 | `tos/tests/slice/_slice_fixtures.py:727-737` `venue_shape()` → `price=4200, quantity=20`; `:740-753` 제약 `price_min=1000, price_max=9000, tick_size=25`; `:804-817` `authorized_coordinates()` → `endpoint="synthetic://paper/order"` 하드 리터럴 |
| 주입 지점 | `_slice_fixtures.py:940-941`(item 11), `:949`(item 17), 그리고 **step 3 스테이지에도 별도로** `:979-980` (`VenueConstraintStage(shape=venue_shape(), constraints=venue_shape_constraints())`) |

**대비되는 GAP-3 배선(닫힌 쪽)**: `tos/src/tos/egressgw/construction.py:149-218`
`admitted_price_from_view`가 `ContextValueView`에서 값+`payload_digest`를 뽑고, `:896-907`
`OrderConstructionStage._price_for`가 `request.value_view`+주입 `price_field_key`가 둘 다 있을 때
값-표면을 우선한다. **즉 값-표면 경로는 step 2에만 배선되어 있고, step 3(venue)·item 11·item 17에는
배선이 존재하지 않는다.**

**재-소싱 시 실측 마찰 3건**:

1. `OrderShapeFields.price: int | None`(`tos/src/tos/venue/records.py:153`)은 **int**,
   `QuantityDerivation.price`는 `CanonicalDecimal`. D-E2 값은 이미 정수 minor-unit
   (`_slice_fixtures.py:188-192` `LOWER_BAND=4_500_000`)이라 정수 투영은 가능하나 **별도 투영 함수가
   필요**(현 `admitted_price_from_view`는 `Decimal` 반환, `construction.py:215`).
2. `order_shape_admissible`(`tos/src/tos/venue/predicates.py:280-283`)은
   `price < price_min or price > price_max` → INADMISSIBLE,
   `(price - price_min) % tick_size != 0` → INADMISSIBLE. 현 제약(1000/9000/25)은 4,499,000을
   **즉시 INADMISSIBLE로 만든다** ⇒ 제약 fixture 동반 이동이 강제되며, 그 수치가 P0-2 소관이라는 점이
   이 이연의 실질 블로커.
3. 수량 무영향 확인(실측): `max_notional`은 `records.py:149`에서 `None` 기본이고 슬라이스 fixture는
   이를 설정하지 않으므로 `construction.py:440-444` notional 검사는 skip — 가격 변경이 수량 20을 흔들지
   않는다는 §4.4 논증은 현 코드에서 유효.

**인용 드리프트(보고)**: #35가 인용한 `_slice_fixtures.py:719-721`(venue_shape)·`:795-810`
(authorized_coordinates)·`:914-944`는 구현 후 각각 **`:727-737`·`:804-817`·`:893-952`로 이동**했다.
`construction.py:273`/`:307`(가격 무관·notional) 인용도 현재 `:221` 시작 함수 안에서 이동. 설계 인용은
구현 전 시점 기준 — closure 계약 저작 시 **전건 재grep 필수**(#35 §12 REGREP 게이트가 이미 요구).

### C. 이연-고정 canary 전수 census

**이연 상태를 단언하는 executable canary: 확인 결과 0건.** `tos/tests/slice/test_slice_gaps.py`는
GAP 1-4 전부 *closure*를 단언하는 형태로 전환되어 있고(:8-19), 유일한 부재-단언은 GAP-4의 RCL release
건(`test_slice_gaps.py:480-495`)으로 ①과 무관. "4,200이 값-표면에서 오지 않음"을 단언하는 테스트는
존재하지 않는다(양방향 grep: `grep -rn "4200\|4,200" tos/` → `test_slice_gaps.py:279`(docstring 서술),
`_slice_fixtures.py:177/730`, `_egressgw_fixtures.py:85/291`, `test_brokeradapter_transport.py:59` —
전부 fixture 상수/설명이며 단언 아님).

⇒ **closure 시 의도적으로 뒤집어야 할 테스트: 없음.** 대신 **깨지 말아야 할 canary**가 터치 표면에
다음과 같이 전수 존재한다:

| # | canary | 위치 | closure 영향 |
|---|---|---|---|
| C1 | 팩토리 "파생 필드는 주입 불가" 음성 목록 + 전 파라미터 KEYWORD_ONLY | `tos/tests/egressgw/test_egressgw_gateway.py:736-758` | `order_shape`/`authorized_coordinates`를 **파생으로 옮기면 파라미터 제거가 필요** → 이 목록에 추가는 additive지만 기존 호출부(`_slice_fixtures.py:940/949`, `test_egressgw_gateway.py:771-778`) 파괴. **하위호환 판정 필요 지점** |
| C2 | 무-command 시 item 17 아티팩트 부재(∅ 양방향) | `test_egressgw_gateway.py:801-823` | 좌표 파생화 시 같은 ∅ 규율을 재현해야 |
| C3 | egressgw import-closure allowlist(12 항목, `tos.dsl` 포함) | `test_egressgw_import_closure.py:71-86` | `tos.venue`는 이미 포함(`:77`) ⇒ 신규 edge 불필요 |
| C4 | "선언한 edge는 전부 실제로 taken"(phantom 금지) + `_DECLARED_BUT_NOT_TAKEN={tos.capsule, tos.evidence}` | `test_egressgw_import_closure.py:333-360`, `:88-90` | capsule을 직접 naming하면 `:355` 단언이 loud FAIL |
| C5 | submodule drift(신규 .py 금지) | `test_egressgw_import_closure.py:541-550` | #35 §12 배치 규율 유지 필요 — 신규 파일 0 |
| C6 | 패키지 docstring 정직 문구 5종 | `test_egressgw_package.py:41-51` | "closes no EV"/"P0-2" 등 유지 |
| C7 | 6/5/6 verify 분할 문구 | `test_egressgw_package.py:54-59`, `test_egressgw_verify_list.py:76-118` | item 11은 Realize 6 안에 있음 — 분류 변경 금지 |
| C8 | e2e 17항목 전건 SATISFIED + 6 deferred만 N/A | `tos/tests/slice/test_slice_end_to_end.py:208-247` | shape/제약 이동이 item 11을 UNKNOWN으로 떨어뜨리면 **여기서 loud FAIL** (이것이 사실상 closure의 회귀 관문) |
| C9 | 전송 스칼라 결속 `request.price == context.outbound_price` | `test_slice_end_to_end.py:250-261` | shape만 바꾸면 무영향(양쪽은 derivation 유래) |
| C10 | venue 술어 자체의 canary-b 계열 | `tos/tests/venue/test_venue_order_shape.py:21`, `test_venue_predicate_only.py:69/108/…` | venue 커널은 미수정 대상 |
| C11 | `AdmittedPriceObservation.model_fields == [source, value, snapshot_digest, value_payload_digest]` | `test_slice_gaps.py:283-288` | 정수 shape 투영을 위해 필드를 추가하면 **여기가 FLIP** |

**특기**: 슬라이스는 shape를 **두 곳**에 주입한다(step 3 스테이지 `_slice_fixtures.py:979-980`,
item 11 컨텍스트 `:940`). 재-소싱은 두 경로를 **한 소스로 수렴**시켜야 하며, 수렴 자체가 §12가 말한
"값-표면 gated 강화"의 실체다.

---

## 이연 ②: D-E2 Context Integrity Service

### A. 이연 정의 원문

**#35 §10-4** — `docs/plans/2026-07-29-tos-slice-gap-closing-design.md:558-559`:

> 4. **값⟺digest 상류 완전 enforcement** — Context Integrity Service(#32 §0.2-4·§2.3 trust seam).
>    투영은 생산-시점 검증을 신뢰·재검증 안 함(**over-claim 금지**).

**#32 §0.2-4** — `docs/plans/2026-07-29-tos-marketfeed-design.md:125-126`:

> 4. **실 Context Integrity Service 런타임 미구현.** 관측 수집·조립·snapshot 발행의 런타임 경로는
>    비-scope(설계 #2 §0.2). D-E2는 그 산출물(admitted snapshot)을 **소비·해소(resolve)**하는 계약과
>    값 표면만.

**#32 §1.1-3** (`:210-212`): "실 관측 수집·snapshot 조립·발행은 Context Integrity Service 런타임
(설계 #2 §0.2 비-scope). 본 슬라이스는 **admitted snapshot을 소비해 값을 §10-conformant로 노출하는
계약**을 실증하지, 그 조립의 acceptance를 산출하지 않는다."

**#32 §2.3 신뢰 seam**(`:314-320`) — 경계 지시가 가장 명시적인 곳:

> **⚠ 신뢰 seam 정직 명기(v1.1 MAJOR-2b·Gap-1)**: 이 검증은 **marketfeed 생산 시점**에 일어난다.
> **env-주입 지점(`build_environment`)은 값⟺digest를 재검증하지 않고** 발행된 `ContextValueView`를
> 신뢰한다. … (c) 완전 강제는 상류 Context Integrity Service(§0.2). **over-claim 금지**: 구조 바인딩은
> 생산자 검증 + 서명 검출을 주지 env-주입 지점의 재검증을 주지 않는다.

**#32 §9-2/§9-6**(`:656`, `:660`) — 두 갈래로 분리 등재:

> 2. **실 Context Integrity Service 런타임**(관측 수집·조립·발행·설계 #2 §0.2) — 슬라이스는 소비만.
> 6. **완전 side-channel/look-ahead 강제·env-주입 재검증**(dishonest producer·신뢰 seam) — 상류
>    정직·§2.3·§4.3·§5.4.

**#32 §12.5 소유권 분할표**(`:766`): "| snapshot 조립·발행 런타임 | — | Context Integrity Service
(설계 #2 §0.2) |"

**원천 이연(설계 #2)** — `docs/plans/2026-07-20-tos-decision-context-capsule-snapshot-design.md:74-77`:

> - **런타임 Context Integrity Service를 구현하지 않는다.** ADR-002-018 §7 표는 "Validate and
>   assemble Snapshot/Capsule"의 소유자를 Context Integrity Service로 두지만, Phase 1은 그
>   서비스가 산출할 **아티팩트의 순수 데이터 모델**과 그 불변식만 저작한다. 관측 수집·조립·
>   발행의 런타임 경로는 비-scope다.

**부착된 경계 지시(①과 달리 명확히 존재)**: (i) **over-claim 금지**(§10-4, §2.3); (ii) **capsule 모델
변경 금지 원칙** — #32 §0.2-1(`:117-120`) "본 설계는 어떤 capsule 모델 필드도 추가/변경/제거하지 않는다
… 불가피 판정 시 그 항목은 설계하지 않고 미결 보고(§15) — 에라타는 오케스트레이터 소관"; (iii)
**estimator/window 미구현**(§0.2-3); (iv) **네트워크 I/O = D-E4/상류**(§0.2-5).

### B. 현재 코드 상태

`tos/src/tos/marketfeed/` 4모듈(`_base.py, records.py, resolver.py, value.py`)이 현재 무결성 처리의 전부:

- **발행 시점 값⟺digest 검증**: `value.py:562` `publish_context_value_view`, digest 산출 `value.py:408`
  `context_value_view_digest`, 자기-digest 검증 `value.py:455`.
- **재검증 부재의 자기-선언**(코드에 박힌 정직 문구):
  - `tos/src/tos/marketfeed/__init__.py:59-63` — "The value ⟺ digest check runs at publication;
    **the environment-injection point does not repeat it.** … Each of those is a producer-honesty
    boundary this layer **detects rather than enforces**, and none of them is claimed as closed."
  - `tos/src/tos/marketfeed/value.py:36` — "not re-verify it (design #32 §2.3/§4.3 trust seam)"
  - `tos/src/tos/dsl/context_value.py:28-29` — "does **not** re-verify it — it consumes the published view."
  - `tos/src/tos/dsl/determinism.py:399` — 동일 취지
  - `tos/src/tos/marketfeed/resolver.py:26` — "environment-injection time (design #32 §2.3 trust seam)"
- **CIS 부재의 자기-선언**: `tos/src/tos/marketfeed/__init__.py:52-57` — "(c) this is a *model plus
  properties*, **not the Context Integrity Service runtime that collects, assembles, and issues
  snapshots** — that runtime is explicitly out of scope (design #2 §0.2), and this package only
  **consumes** its output."
- **구조적 봉인**: `__init__.py:9-15` — "opens no socket, subscribes to nothing, and holds no
  credential … enforced two ways: the import-closure canary … and the record-level **fetch-surface
  seal** in `tos.marketfeed._base`."
- **엔진 측 소비 슬롯**: `resolver.py:159` `resolve(capsule, *, instrument_key) -> ResolvedTick`,
  `:214` `DecisionContextResolver` 시그니처 충족. 엔진은 `pipeline.py:323
  resolved_context=payload.value_view`로만 소비.

**⇒ 실측 판정**: "무결성 처리"는 (a) 발행 게이트(값⟺covered digest·VALID gate·중복 field_key 거부·
정수 전용) + (b) 서명 append 검출(`test_dsl_context_value.py:394-420`) 두 겹이며, **상류 조립/발행
런타임은 코드에 존재하지 않고, 부재가 docstring·firewall·seal 3중으로 고정되어 있다.**

### C. 이연-고정 canary 전수 census

**이 건은 3건 중 유일하게 executable 한계-단언을 갖는다.**

| # | canary | 위치 | closure 시 처분 |
|---|---|---|---|
| K1 | **한계 단언** — 생산자가 as-of를 재사용하면 사슬이 붕괴한다(같은 digest 2회) | `tos/tests/marketfeed/test_marketfeed_distinctness.py:236-247` — docstring: "This test asserts the *limit*, not a guarantee … **Complete enforcement is upstream (the Context Integrity Service)** plus the signature append's detectability." | ⚠ **직접 FLIP 대상이 아님**: 테스트는 게이트에 직접 두 관측을 먹여 붕괴를 보이므로, CIS를 상류에 두는 설계대로 닫아도 이 단언은 GREEN 유지. **게이트에 as-of 재사용 거부를 넣는 순간에만 FLIP.** 계약 저작 시 이 구분을 명시해야 함 |
| K2 | 패키지 docstring 정직 선언("closes no EV", "Provisional") | `tos/tests/marketfeed/test_marketfeed_package.py:232-236` | docstring `:52-57`의 "(c) … not the Context Integrity Service runtime" 문장을 수정하면 **여기 통과 여부 재검토 필요**(현 단언은 두 문구만 검사 — 실질 FLIP 아님) |
| K3 | fetch-surface seal(전 모델 필드에 transport/credential 이름 금지, 생성 시 자동 실행) | `test_marketfeed_package.py:91-95`, `:97-100`; 구현 `marketfeed/_base.py` | **CIS 런타임을 marketfeed 안에 넣으면 loud FAIL** — 가장 강한 구조 경계 |
| K4 | marketfeed import-closure: socket/urllib/os.environ/importlib 부재 + allowlist | `test_marketfeed_import_closure.py:291-337`, `:555-575`, `:617-626` | 동일 |
| K5 | submodule drift(신규 .py는 child import 목록과 lockstep) + 순수 모듈 파일 목록이 디스크와 일치 | `test_marketfeed_import_closure.py:627-643`, `:644-650` | 신규 모듈 추가 시 **두 곳 동시 갱신 필수** |
| K6 | 엔진 allowlist에 marketfeed 부재(14패키지) — 양방향 | `test_marketfeed_import_closure.py:406-431`, `tos/tests/engine/test_engine_value_view.py:161-170`(`len==14` + `"tos.marketfeed" not in`) | 엔진→marketfeed edge 발명 금지의 실행 가능 형태 |
| K7 | dsl 진입점 시그니처 잠금: `evaluate` 5-파라미터 고정 / `evaluate_resolved`는 정확히 +1 | `tos/tests/dsl/test_dsl_context_value.py:316-326`, `:327-362`, `:363-370` | env-주입 재검증을 넣으려면 여기를 통과해야 — **재검증은 시그니처 확대 없이 해야 함** |
| K8 | `build_environment.resolved_context`가 keyword-only | `test_dsl_context_value.py:263-269` | 유지 |
| K9 | 서명 append mutation canary(제거하면 두 서명이 동일해짐) | `test_dsl_context_value.py:394-420`, `:409-445` | 검출 메커니즘의 유일 보증 — 유지 |
| K10 | `DecisionTickPayload.model_fields == {instrument_key, capsule, time, reference, value_view}` | `tos/tests/engine/test_engine_value_view.py:148-158` | payload에 필드를 더하면 **FLIP** |
| K11 | resolver mutation canary(다른 snapshot body 대체 불가) | `test_marketfeed_resolver.py:94` | 유지 |
| K12 | 리포지토리 방화벽 TOS-FW-A/B/C/D/R | `tools/tos_firewall_check.py:17-27`, `:69-83`(socket/ssl/http/urllib.request 금지), `:96-108`(`shared.config` 배제) | **CIS 런타임의 근본 제약**: tos/ 안에 수집 런타임은 구조적으로 불가, 동시에 TOS-FW-R("tos/ 밖 파일은 `import tos` 금지")이 밖에서의 구현도 막는다 ⇒ **D-E4 transport 선례대로 주입 Protocol 경계로만 닫힐 수 있음** |

---

## 이연 ③: 다심볼 (per-scope last-reference)

### A. 이연 정의 원문

**원천 — 수직 슬라이스 서베이 OUT-5** (`docs/plans/2026-07-29-tos-engine-vertical-slice-scoping-survey.md:99-100`):

> 5. **다심볼 portfolio vector·all-or-none 상호의존.** RFC-003 §9.1:333-337·RFC-008 outcome
>    `PortfolioVector`(tos.dsl 기구현이나 슬라이스 미사용).

같은 문서 IN-1(`:81-83`): "portfolio vector(다심볼 set)는 이연."

**#31 §0.2-9** (`docs/plans/2026-07-29-tos-engine-event-core-design.md:96`): "9. **통계적 edge 증명·
multi-symbol portfolio vector.** 서베이 §1 OUT-4/5."

**#31 §3.1-3 (VECTOR 처분 + 경계 지시)** (`:300-303`):

> **`DecisionKind.VECTOR`(다심볼·:143) outcome 도래 시 fail-closed**(슬라이스 per-instrument 전제 위반 —
> 무진행·restrictive no-action·기록; **VECTOR 접기 규칙은 후속 다심볼 사이클 소유**·MINOR-1).

**#31 §3.3 (확장 형태 + 발명 금지)** (`:372-376`):

> - 슬라이스 #1: 레지스트리 1-entry. 다심볼은 N-entry로 **인터페이스 무변경** 확장.
> - **검토·기각 대안**: (A) per-symbol 전략 인스턴스 리스트 순회(키 없음) — 기각 … (B) **와일드카드
>   전략(1개가 N심볼) — 기각**: `TargetSpec` 구조가 금지(G4 하드코딩)·Proposal 와일드카드 금지
>   (RFC-003 §9:279-283 "SHALL NOT use wildcard account, instrument …").

**#33 §0.2-7/-10** (`docs/plans/2026-07-29-tos-backtest-design.md:96`, `:100`): "라이브 실주문·비동기
I/O·**다피드 동시성**", "**통계적 edge·multi-symbol portfolio vector.**"

**#35 §10-2** (`docs/plans/2026-07-29-tos-slice-gap-closing-design.md:551-552`): "**완전 net-position
ledger(multi-leg·평단)** — engine은 position ledger 아님(#33 B4). GAP-4는 단일-entry
held=filled_quantity 범위." — 다심볼과 짝을 이루는 인접 경계.

**"per-scope last-reference" 문구 자체의 출처**: 설계 4편 어디에도 없다. **`docs/plans/INDEX.md:25`의
#31 사이클 완결 기록**에만 존재 — "NIT 3 기록(**per-scope last-reference는 다심볼 시점**·NIT-3:
무해제→슬라이스 백테스트 scope당 1주문 — D-E3 설계 인지 필수)". #31 적대적 코드 리뷰 산출물의 별도
파일은 리포에서 **찾지 못했다**(docs/·.omc/ 전수 grep 결과 INDEX.md 1행뿐). ⇒ **이 이연의 원문 근거는
INDEX 한 줄이 전부**이며, 계약 저작 시 이 사실을 정직하게 기재해야 한다.

**부착된 경계 지시**: (i) 와일드카드 전략 금지(RFC-003 §9:279-283, #31 §3.3 (B) 기각); (ii) 인터페이스
무변경 확장 원칙; (iii) VECTOR 접기 규칙은 이 사이클 소유(= 변경이 허가된 유일한 fail-closed 지점);
(iv) net-position ledger 발명 금지(#35 §10-2).

### B. 현재 코드 상태 (단일 스코프 고정의 실제 형태)

| 지점 | 현 상태 | 다심볼 시 성격 |
|---|---|---|
| `EngineCore._last_reference` | `tos/src/tos/engine/core.py:246` **단일 전역** `OrderingEvent \| None`; 비교 `:280`; **모든 non-REVERSED 이벤트마다 갱신** `:301` | **핵심 결함 후보** — 아래 참조 |
| `ordering_admission` | `core.py:160-181` — `BEFORE`→REVERSED, `AFTER`→MONOTONE, 그 외 **AMBIGUOUS(수용)** | 교차-continuity는 AMBIGUOUS |
| `compare_order` 교차-continuity | `tos/src/tos/ordering/_ordering.py:113-126` — `same_continuity`일 때만 `source_native_sequence`/`local_monotonic_value` 비교 | 심볼별 continuity면 순서 근거 소멸 |
| `ProvisionalReservationLedger` | `tos/src/tos/engine/state.py:137` `dict[tuple[str,str], ...]` — **이미 per-scope 키잉**; `:146/:150/:165/:195` 전부 `key` 파라미터 | **변경 불요** |
| `StrategyRegistry` | `tos/src/tos/engine/registry.py:56-71` — `dict[(account,instrument), list]`; docstring `:59` "Slice #1 holds one entry; **a multi-symbol universe is N entries with no interface change**" | **변경 불요** |
| `derive_instrument_key` | `tos/src/tos/engine/admission.py:181-209` — 2개 이상 스코프 선언 전략 거부(`:206-209`), wildcard `None` 거부 | **유지 대상**(전략당 1스코프는 다심볼에서도 정본) |
| VECTOR fail-closed | `tos/src/tos/engine/pipeline.py:329-340` — `HaltReason.VECTOR_OUTCOME_UNSUPPORTED`, 사유 문자열에 "the vector folding rule belongs to a later multi-symbol cycle" | 이 사이클이 여는 유일한 문 |
| `CausalBarConverter` | `tos/src/tos/backtest/converter.py:71-95` — `instrument_key` 1개("The single dispatch scope this slice replays"), `:119` resolver 호출에 그 키 고정 | N-스코프 확장 필요 |
| `BacktestDriver` | `tos/src/tos/backtest/driver.py:186-188` "The single scope this driver replays"; `:179` `YieldOrderCounter(continuity_id=...)` **1개**; `:88-142` 전역 monotone 카운터, **reset/rewind 없음**(`:134-135`) | N-스코프 확장 필요 |
| `MarketFeedContextResolver` | `tos/src/tos/marketfeed/resolver.py:159`/`:201` — `(capsule, *, instrument_key)` 파라미터화 | **변경 불요** |

**실측 기반 메커니즘 판정(핵심)**: 심볼별로 별도 `source_continuity_id`를 쓰면, 심볼 B 이벤트를 심볼
A의 마지막 좌표와 비교할 때 `compare_order`는 `same_continuity=False`(`_ordering.py:113-116`)라 native
sequence를 **비교하지 않고**, 백테스트는 `time_lo/hi`를 순서에 쓰지 않으므로(#33 §3.4 `:348-350`)
결과는 AMBIGUOUS. AMBIGUOUS는 `core.py:280-301`에서 **halt 없이 수용되고 `_last_reference`가
덮어써진다**. ⇒ 심볼 A의 진짜 역행 이벤트가 심볼 B의 좌표와 비교되어 REVERSED 검출을 **놓칠 수 있다**.
이것이 "per-scope last-reference" NIT의 실체이며, **다심볼 도입 시 신규로 발생하는 fail-open**이다
(단일 스코프에서는 발생 불가 — 현재 결함 아님). 반대로 전 심볼을 단일 continuity + 단일 카운터로
묶으면 전역 `_last_reference`가 그대로 옳다 ⇒ **설계 판정 지점**: 스트림 모델(단일 continuity vs
심볼별 continuity)이 먼저 결정되어야 last-reference 형태가 결정된다.

### C. 이연-고정 canary 전수 census

**이연 상태를 executable로 단언하는 것: 1건(VECTOR)뿐.**

| # | canary | 위치 | closure 시 처분 |
|---|---|---|---|
| M1 | **VECTOR outcome은 무진행·기록** | `tos/tests/engine/test_engine_pipeline.py:223-236`(`HaltReason.VECTOR_OUTCOME_UNSUPPORTED`, `outcome_type == "PortfolioVector"`), 모듈 docstring `:11-13` "The vector folding rule belongs to a later multi-symbol cycle" | **유일한 의도적 FLIP 후보.** 단, VECTOR 접기를 실제로 여는 경우에만 — 다심볼을 "N개 per-instrument 전략"으로만 구현하면 **FLIP 불요**(이 편이 #31 §3.3 "인터페이스 무변경"과 정합) |
| M2 | 전략 1개가 2스코프 선언 시 키 불가 + 등록 거부 | `tos/tests/engine/test_engine_dispatch.py:100-111` | **유지**(다심볼 = N전략, 1전략 N스코프 아님) |
| M3 | wildcard(None/토큰) 스코프 거부 | `test_engine_dispatch.py:83-98` | **유지**(RFC-003 §9:279-283) |
| M4 | 타 instrument 이벤트/캡슐은 무평가 | `test_engine_dispatch.py:124-135`, `:164-183` | 다심볼에서 더 중요해짐 — 유지 |
| M5 | MISSING vs EXPLICIT_EMPTY 구분(∅ 양방향) | `test_engine_dispatch.py:136-163`, `:184-` | 유지 |
| M6 | AMBIGUOUS는 수용, REVERSED만 거부 | `tos/tests/engine/test_engine_event_vocabulary.py:207-229` | **유지**(과잉거부 금지) — 단 위 §B 메커니즘 때문에 다심볼에서는 이 성질이 검출 공백의 통로가 된다. 계약이 정면 처리해야 |
| M7 | **전역 단일 `_last_reference` 전제의 서술 canary** | `tos/tests/backtest/test_backtest_ordering.py:1-18`(docstring: "the core holds **one** global `_last_reference` (core.py:246)"), 본문 `:110-189`(기각된 bar-coupled 스킴이 허위 REVERSED를 실제로 만든다), `:190-234`, `test_backtest_converter.py:113`, `test_backtest_scenarios.py:278` | last-reference를 per-scope로 바꾸면 **본문 단언은 단일 스코프에서 동치라 GREEN 유지**, 그러나 **docstring 전제가 stale prose가 된다** ⇒ 문서 lockstep 대상. 구조를 `hasattr`로 잠근 canary는 **부재 확인**(grep `_last_reference` → src 3행 + 테스트 docstring 3행뿐) |
| M8 | 카운터 되돌리기 불가·연속 실행 간 계속 전진 | `test_backtest_ordering.py:80-89`, `:317-334` | 유지 |
| M9 | 무명 continuity 거부 | `test_backtest_ordering.py:99-109` | 다심볼 continuity 배정 시 유지 |
| M10 | trace 좌표 순서 == 처리 순서, 등가 좌표 unconstructable | `test_backtest_ordering.py:257-316` | **다심볼 인터리빙 설계의 직접 제약** |
| M11 | 엔진 패키지 docstring 정직 문구 6종("reproducibility, not distinctness", "release: impossible here" 등) | `tos/tests/engine/test_engine_package.py:87-104`, 모듈별 `:107-120` | 유지 |
| M12 | backtest import-closure(엔진 closure의 부분집합) + submodule drift + "core는 typing-only 참조" | `test_backtest_import_closure.py:328-336`, `:562-576`, `:607-` | 신규 .py 배치 규율 |
| M13 | ledger에 release/free/clear/reset 부재 | `tos/tests/slice/test_slice_gaps.py:480-495`, `tos/src/tos/engine/state.py:22`, `:175-176` | **③에서 절대 건드리면 안 되는 인접 경계** |
| M14 | `outstanding_consumed_magnitude` 정직 스코프 = 1엔트리 | `tos/src/tos/engine/state.py:178-182` docstring("A full net-position ledger — multi-leg, averaged — is **not** this … deferred") | 다심볼과 혼동 금지 |

---

## D. 의존·순서 (실측)

**① ↔ ②**: **부분 의존.** #35 §10-3(`:556`)이 ①을 "전부 D-E2 marketfeed 값-표면 소관(#32 §2.5)"으로
귀속시킨다. 다만 실측상 ①이 필요로 하는 D-E2 산출물(`ContextValueView` + 정수 minor-unit 값 +
`payload_digest`)은 **이미 출하되어 있고**(`construction.py:149-218`이 그 위에서 돈다), ②(CIS 런타임)는
**그 위쪽**이다. ⇒ **①은 ②를 기다리지 않는다.** ①이 실제로 대기하는 것은 (a) #32 §2.5
deterministic-float 투영 규칙(정수만 쓰면 회피 가능)과 (b) **P0-2 Broker Capability Profile INSTANCE**
(price_min/max/tick가 이 사실) — 후자가 진짜 게이트.

**② ↔ ③**: 독립. 다심볼은 `resolve(capsule, *, instrument_key)`(`marketfeed/resolver.py:159`)가 이미
파라미터화되어 있어 D-E2 표면 변경을 요구하지 않는다.

**① ↔ ③**: 독립. 다만 다심볼이 먼저 착지하면 ①의 fixture 재-소싱을 N-스코프로 두 번 해야 하므로
**① 먼저가 저렴**.

**GAP-3 선례의 정확한 형태**: #35 §4.2/§4.4의 closure는 "가격 값-표면 파생(D-E4 ← D-E2 lineage)"이었고,
실제 배선은 `StageRequest.value_view`(`engine/records.py:392`) → `OrderConstructionStage._price_for`
(`construction.py:896-907`) → `admitted_price_from_view`. ①은 **같은 seam을 step 3/item 11로 한 번 더
뻗는 작업**이다. 즉 ①은 ②가 아니라 **GAP-3 구현 자체에 의존**(이미 충족).

**세션 A 트랙과의 표면 겹침 — 실측**:

| 세션 A 산출 | 터치 파일 | ①②③와 겹침 |
|---|---|---|
| `eb92ea46` EV-L2 fault suite + L1 하드닝 | `tools/tos_evidence_run.py`, `tests/tools/test_tos_evidence_run.py`, **`tos/pyproject.toml`**, **`tos/src/tos/canonical/_base.py`·`canonicalization.py`**, `tos/src/tos/spg/*`, **`tos/tests/conftest.py`**, `tos/tests/orthostate/test_orthostate_l2_fault.py`, `tos/tests/spg/*`, `tos/tests/test_digest_binding.py` | **겹침 3건**: `tos/tests/conftest.py`(전 tos 테스트 공용 — `--l2-fault-timeline` 옵션 소유), `tos/pyproject.toml`(rootdir/의존성), `tos/src/tos/canonical/*`(marketfeed·egressgw·engine이 전부 `get_scheme`/digest로 소비). **단, 셋 다 ①②③가 *수정*할 이유는 없음 — 읽기 소비만.** 파일 수정 충돌 위험은 낮으나 canonical 시맨틱 변경이 digest 단언에 파급 가능 |
| 코퍼스 리마디에이션(`acd45c43`/`15d48f72`/`00972702`/`0ba03639`/`a1a92b9f`) | `tools/tos_spec_status.py`, `tests/tools/test_tos_spec_status.py`, `tos-spec/src/**`, `docs/**` | **겹침 0** (tos/src·tos/tests 무터치) |
| P0-2 / 브로커 프로브(`tools/kis_*`, P-R5/P-BAL 등) | `tools/**`, `docs/broker-profiles/**` | **간접 겹침 1**: ①의 `price_min/price_max/tick_size`가 **P0-2 산출물(Broker Capability Profile INSTANCE)에 의존**. 파일 겹침은 아니지만 **의사결정 의존** |
| `executor.py` blind-retry | `shared/execution/executor.py` | **겹침 0**(tos/ 밖, TOS-FW-R로 격리) |
| EV-L1/EV-L2 harness 노드 지정 | `tools/tos_evidence_run.py`는 node id를 인자로 받음(`:1787`), 소스에 `marketfeed`/`egressgw`/`backtest`/`engine` **문자열 0건**(grep 실측) | **겹침 0** — 세 이연의 테스트는 현재 어떤 EV 행에도 결속되어 있지 않다 |

---

## E. 패키징 권고

### 권고: **분리 2편 + 1건 재분해** (통합 1편 비권고)

**근거**: 세 건은 소유 패키지(D-E4 / D-E2·dsl / D-E1·D-E3)·차단 게이트(P0-2 / firewall 구조 / 스트림
모델 판정)·canary 표면이 전부 다르다. 통합하면 #35에서 리뷰어가 지적했던 "배치 미지정"류 결함이 3배로
재발한다. 다만 ①과 ③은 성격상 각각 소형/중형이라 두 편으로 충분.

**권고 순서**:

**1편 — ① venue_shape/coordinates 값-표면 재-소싱 (소형·즉시 착수 가능)**

- 터치 모듈 추정 **4~6**: `egressgw/construction.py`(정수 shape 투영 + `VenueConstraintStage`에
  `price_field_key`/`value_view` 스레딩), `egressgw/records.py`(선택: 파생화 여부 판정),
  `tests/slice/_slice_fixtures.py`, `tests/egressgw/_egressgw_fixtures.py`, (제약 이동 시)
  `tests/egressgw/test_egressgw_construction.py`, `tests/slice/test_slice_end_to_end.py`.
  **신규 .py 0**(C5/§12 배치 규율).
- 신규 테스트 규모 추정 **8~14**(정수 투영 정확·비정수 fail-closed·∅ 양방향·shape==command 동일수치
  실증·제약 이동의 provisional 라벨링·item 11 SATISFIED 회귀).
- **발명 금지 목록**: (a) `price_min/price_max/tick_size`를 "4,499,000이 통과하도록" 임의 선택 —
  P0-2 소관 사실이며 승인 없이 정한 값은 **반드시 provisional 표기 + register 미결 등재**(#34 §9
  `:718`); (b) 좌표(`EgressCoordinateSet`)를 "값-표면"에서 유도하는 것 — 좌표는 route/credential
  사실이지 시장 값이 아니다(#35 §4.4 item 17 `:319-321` "가격 직접 대조 0"). 좌표 건은
  **transport/route inventory 파생**으로 재프레이밍하거나 이연 유지가 정직; (c) 반올림/정규화 도입 —
  `order_shape_admissible`의 무-반올림 계약(venue `predicates.py:230-231`) 위반; (d)
  `AdmittedPriceObservation` 필드 추가 시 C11(`test_slice_gaps.py:283-288`) FLIP을 계약에 명시하지
  않고 진행하는 것; (e) `send_boundary_context`에서 `order_shape` 파라미터 제거(C1 목록 확대) —
  하위호환 파괴이므로 별도 판정 없이 금지.
- **선결**: #35 §12 REGREP 게이트 이행(설계 인용 line 3건 이미 드리프트 확인됨).

**2편 — ③ 다심볼 (중~대형·설계 판정 선행 필요)**

- **선행 판정 1건(계약이 먼저 결정해야 함)**: 스트림 모델 = 단일 continuity + 단일 yield 카운터
  **vs** 심볼별 continuity. 전자면 `_last_reference` 전역 유지가 정답(NIT 불성립), 후자면
  per-scope/per-continuity 전환이 **fail-open 봉인으로 필수**(§B 메커니즘). 이 판정 없이 "per-scope
  last-reference"를 착수하면 근거 없는 구조 변경이 된다.
- 터치 모듈 추정 **5~8**: `engine/core.py`(last-reference 형태), `backtest/driver.py`+`converter.py`
  (N-스코프·카운터/continuity 배정), `backtest/_base.py`/`results.py`(trace의 per-scope 표현),
  선택적으로 `engine/pipeline.py`(VECTOR — 열 경우에만). 레지스트리·ledger·marketfeed resolver는
  **무변경**.
- 신규 테스트 규모 추정 **20~35**(심볼별 monotone 유지·교차 심볼 AMBIGUOUS가 검출 공백을 만들지
  않음의 양성 실증·심볼 A 역행이 심볼 B 좌표 뒤에서도 REVERSED로 잡힘의 뮤테이션·N-entry 레지스트리
  디스패치·per-scope at-most-one 독립성·trace 순서).
- **발명 금지 목록**: (a) 와일드카드 전략(1전략 N심볼) — #31 §3.3 (B) 기각·RFC-003 §9:279-283;
  (b) net-position ledger / 평단 / multi-leg — #35 §10-2·`state.py:178-182`; (c) RCL release·capacity
  해방 — M13(`test_slice_gaps.py:480-495`)이 loud FAIL로 잡음; (d) AMBIGUOUS를 REVERSED로 승격
  (과잉거부) — M6 FLIP; (e) 카운터 reset/rewind — `driver.py:134-135`·M8; (f) VECTOR 접기 규칙을
  "다심볼 = N per-instrument"로 충분한데도 함께 여는 것 — 스코프 확대.

**3편(재분해) — ② Context Integrity Service**

- **이 건은 지금 "구현 계약"으로 열 수 없다는 것이 실측 판정이다.** 이유: CIS 런타임은 관측 수집·
  조립·발행(네트워크/상태)인데, `tools/tos_firewall_check.py`가 (i) tos/ 안에서
  socket/ssl/http/urllib.request/subprocess를 금지(TOS-FW-B, `:69-83`), (ii) `os.environ`/`getenv`
  금지(TOS-FW-C), (iii) **tos/ 밖 파일의 `import tos`를 금지**(TOS-FW-R, `:24-26`). ⇒ 안에도 밖에도
  놓을 수 없다. 유일한 정합 경로는 **D-E4 `Transport` 선례와 동형인 주입 Protocol 경계**(#34 §5.1)이며,
  그것은 "CIS를 구현한다"가 아니라 "CIS 산출물의 주입 포트를 확정한다"는 **별개의 더 작은 계약**이다.
- 따라서 권고: ②는 **(a) 주입 포트 계약(소형, 터치 2~3모듈: `marketfeed/resolver.py`의
  `SnapshotStore`/`ValueCandidateSource` 확장 + 포트 선언)** 과 **(b) env-주입 재검증(#32 §9-6, 별개
  이연)** 두 조각으로 **재분해**한 뒤, (a)만 3편으로 착수하고 (b)는 K7 시그니처 잠금
  (`test_dsl_context_value.py:316-370`)과의 정합을 먼저 판정하는 것이 정직하다. **"CIS 런타임 구현"
  이라는 형태로는 착수 불가**를 계약 §0에 명기해야 한다.
- 신규 테스트 규모 추정 (a) **6~10**, (b) **10~18**.
- **발명 금지 목록**: (a) capsule 모델 필드 추가/변경 — #32 §0.2-1(`:117-120`), 불가피 시 **설계하지
  말고 미결 보고**; (b) `evaluate`/`evaluate_resolved` 시그니처 확대 — K7; (c) marketfeed 레코드에
  transport/credential 이름 필드 — K3 seal이 생성 시점에 터짐; (d) 엔진→marketfeed edge — K6 양방향
  canary; (e) 발행 게이트가 "완전 강제"를 주장하는 문구로 docstring 개정 — §10-4 over-claim 금지;
  (f) as-of 재사용 거부를 게이트에 넣으면서 K1을 조용히 갱신하는 것 — FLIP이면 FLIP으로 계약에 등재.

### 전 편 공통 이행 사항

1. **터치 표면 committed canary 전수-grep**(closure allowlist만으로 불충분 — #35 MAJOR-1이 egressgw
   submodule canary 누락을 적발한 선례). 위 C1-C11 / K1-K12 / M1-M14가 시작점이지 완결 목록이 아니다.
2. **신규 .py 0 규율** — 세 패키지 전부 submodule drift canary 보유
   (`test_egressgw_import_closure.py:541-550`, `test_backtest_import_closure.py:562-576`,
   `test_marketfeed_import_closure.py:627-650`).
3. **인용 재grep** — 설계 4편의 fixture/구현 line 인용은 구현 커밋 이후 드리프트했음을 실측 확인
   (§①-B 참조).

---

## 확인하지 못한 것 (정직 보고)

- **"per-scope last-reference" NIT의 원문**: `docs/plans/INDEX.md:25` 한 줄 외에 어떤 설계 문서·리뷰
  아티팩트에서도 발견하지 못했다(docs/·.omc/ 전수 grep). #31 적대적 코드 리뷰의 원 산출물 파일은
  리포에 커밋되어 있지 않은 것으로 보인다.
- **세션 A의 미커밋 in-flight 작업**: 워킹트리가 clean이므로 진행 중 편집 내용은 관측할 수 없었다.
  겹침 판정은 커밋된 것 기준.
- **전체 스위트 실행 안 함**: `tos/tests/slice` + `tos/tests/marketfeed`(206 passed)만 실행. 8560 전체
  GREEN 여부는 이 세션에서 재확인하지 않았다.
- **①의 좌표(coordinates) 부분**: "값-표면 재-소싱"이라는 표현이 좌표에도 적용 가능한지는 설계 원문
  (`:553-557`)이 "egress 좌표는 fixture 잔존"으로만 서술하고 재-소싱 대상 소스를 지정하지 않는다.
  좌표는 시장 값이 아니므로 **이 이연 항목의 좌표 절반은 원문상 스코프가 모호**하다 — 계약 저작 시
  운영자/오케스트레이터 확인 지점.
- **P0-2 Broker Capability Profile INSTANCE의 현재 승인 상태**:
  `docs/plans/2026-07-29-tos-broker-capability-profile-kis-draft.md`가 비규범 초안이라는 것까지만
  확인했고, ① 착수 가능 여부를 좌우하는 승인 진행도는 이 서베이에서 추적하지 않았다.

---

## 오케스트레이터 판정 (2026-08-05, 계약 저작 입력)

서베이 권고를 채택하며, 저작 전 판정 3건을 부착한다:

1. **패키징**: 분리 3편 — #36 = ① 재-소싱, #37 = ③ 다심볼, #38 = ②(a) CIS 주입 포트 계약.
   ②(b) env-주입 재검증은 이번 아크에서 착수하지 않고 정직 이연으로 잔존(K7 정합 선행 판정 필요).
2. **①의 좌표 절반**: 값-표면 재-소싱 대상에서 **제외**한다. 좌표는 시장 값이 아니라 route/credential
   사실이므로 "값-표면 재-소싱"의 원문 스코프 모호는 transport/route-inventory 소관(D-E4·P0-2 후속)
   재프레이밍으로 해소하고, #36 §0에 원문 인용과 함께 이연 정제(refinement)로 기록한다 — 침묵 드롭 금지.
3. **①의 제약 수치**: P0-2 소관이므로 #36은 메커니즘(값-표면 스레딩·정수 투영·수렴)만 설계하고,
   fixture 제약 수치는 provisional 라벨 + 미결 등재를 의무화한다.
