# 설계 문서 #36 — venue_shape.price 값-표면 재-소싱 계약 (deferral ① 아크, provisional·닫는 EV 0건) (2026-08-06, v1.2)

> **v1.2 개정(2026-08-06)**: 델타 재검증 REVISE(신규 MAJOR-N1·MINOR 3) 반영 — §10-2 register 목적지
> 1건 정정으로 비준 승급(M1-M4·MINOR 7·WM 4는 전건 해소 실측 확인). **MAJOR-N1**: register §8-1
> (=VERIFICATION-PROFILE-002.yaml·P0-1 Bounds-Approver 트랙) 지목은 프로파일 혼동 — venue #19 §8.0 비준
> 판정(tick/lot/band=`VenueConstraintPolicy` policy content·VERIFICATION-PROFILE 신규 키 0)과 상충하므로
> **1차 등재처를 register §8-2 Candidate(brokercap INSTANCE bound family·`brokercap:1176-1181`)로 정정**
> + KIS 초안 dimension 17(`:88`)·§7 item 3/4(`:273-274`) cross-ref·전방 입력(policy-content 소관
> 재정밀화) 등재. 판정 provenance = **본 계약 §10-2 자체가 정본**(외부 커밋 아티팩트 인용 아님). MINOR:
> 앵커 이중개념 역할 분리(테스트 리터럴 `:184-186`/이관 문단 `:182-186`)·§9-4 `venue_stage` 이름 잔재·
> V19-V22 4행 추가(전수 census 전칭 성립). 개정 처분 전수는 §14.
>
> **v1.1 개정(2026-08-06)**: 독립 비평 REVISE(MAJOR 5·MINOR 7·What's Missing 4) 전건 반영 —
> 재설계 아님·정직성/census 개정. **MAJOR-1** 터치 파일 소스-텍스트 canary 2건(`test_slice_gaps.py:291`
> ContextValueView 양성·`:296` marketfeed 부재) V-row 추가 + §12 저작 제약. **MAJOR-2** P2 공유-코어
> 추출이 하드코딩 앵커(테스트 리터럴 `construction.py:211`·`:184-186`; 이관 문단 `:182-186`) 무효화 → V3 REGREP 승격·앵커 재조준 의무·bool≠1
> 문단 보존처 지정. **MAJOR-3** "이중 주입 붕괴" 과잉 주장 축소(item-11 fold 6입력 중 5개 이중 주입 —
> shape+constraints만 수렴[가격 대조 경로]·snapshot/policy/decision 정직 잔존 등재). **MAJOR-4** freshness
> 전칭 주장 반증 3건 교정(submodule-drift `:541-550`·`_Request`(not `_StageRequest`)`:620-641`·allowlist
> `:71-86`) + 헤더 freshness 하향. **MAJOR-5** register 아티팩트 명명(§8-1 신설 누락 키·행 추가 구현 커밋
> 범위·교체 트리거 — **⚠ v1.2 MAJOR-N1이 §8-1→§8-2 Candidate로 정정**). MINOR 7·What's Missing 4 §별
> 반영. 개정 처분 전수는 §14.
>
> **성격**: 저작(authoring) 산출물. 파이프라인: 저작 → 1차 심사 → 독립 비평 → 개정 →
> 운영자 위임 자동 비준(ADR-002 Part-2/3 연장) → 구현 → 적대적 코드 리뷰. 본 산출은
> **provisional**이며 **닫는 EV/AC 0건**(§0.4). acceptance는 비준 5설계(#31~#35)의
> 후속 게이트와 동일 소관이다. 신규 패키지 0·신규 .py 0.
>
> **입력물**: 스코핑 서베이 `docs/plans/2026-08-05-tos-deferral-closure-scoping-survey.md`
> (이연 ① 절 A/B/C·§D·§E 1편·말미 오케스트레이터 판정 3건 — **구속력 있는 저작 입력**) +
> #35 슬라이스 갭-closing 계약(형식·규율 템플릿) + #34 §9·#32 §2.5 원문.
> 베이스라인: HEAD `5ebc61f8`(서베이 기준). 본 계약의 file:line 인용은 **서베이 교정을 반영**하고
> v1.1 독립 비평이 적발한 freshness 반증 3건(MAJOR-4)을 교정한 값이나, **전칭 freshness는 주장하지
> 않는다** — 구현 착수 시 §12 REGREP 게이트로 전건 재확정한다.

---

## 0. 전제·규율

### 0.1 이 계약이 닫는 것 (한 문장)

수직 슬라이스 #1의 **유일 잔존 내부 비정합** — venue가 4,200-shape를 admit하는데 command는
값-표면 4,499,000(#35 §4.4 MAJOR-3) — 을, venue_shape.price를 GAP-3와 **동형의 값-표면 seam**으로
확장하고, 슬라이스가 shape·제약을 두 번 주입하는 **가격 대조 경로**(step-3 fold + item-11 fold의
`order_shape_admissible(shape, constraints)`)를 **스테이지 단일 소유의 한 소스로 수렴**시켜 닫는다.
(item-11 fold 6입력 중 snapshot/policy/decision은 결정론적 생성이라 이중 주입이 잔존하며 정직 등재 —
§2.2·§3.3·§11-5. 붕괴하는 것은 **가격 대조 경로 한 축**이지 전 입력이 아니다.) 결과:
`venue_shape.price == command.derivation.price == 값-표면(field_key) 정수`.

### 0.2 범위·비범위

**범위**:

1. venue admissibility의 shape 가격(`OrderShapeFields.price`)을 `ContextValueView`에서 **정수 exact
   투영**으로 재-소싱하는 배선. 투영 함수 + step-3 `VenueConstraintStage`의 값-표면 스레딩.
2. step-3 스테이지 fold와 gateway item 11 fold(`gateway.py:825-832`)가 **동일 shape·동일 제약
   객체**를 소비하도록 슬라이스의 두 주입 지점을 스테이지-보유(stage-retained) 단일 소스로 수렴.
3. 제약 대조 경로(band/tick)의 **메커니즘**만 설계. 슬라이스 제약 수치(`price_min`/`price_max`/
   `tick_size`)는 P0-2 소관이므로 provisional 라벨 + 미결 등재(§10-2·오케스트레이터 판정 iii).

**비범위(명시 이연·§10, 침묵 드롭 금지)**:

- **좌표(`authorized_coordinates`·item 17) 재-소싱** — 오케스트레이터 판정 ii로 **스코프 제외**.
  §0.5에 #35 §10-3 원문 인용 + transport/route-inventory 재프레이밍(D-E4·P0-2 후속) 이연 정제로 기록.
- **제약 수치의 실 승인값**(broker-specific bound) — P0-2 Broker Capability Profile INSTANCE 소관
  (#34 §9 broker-specific bound 행). 계약은 provisional stand-in의 **충족 조건**만 정의.
- **shape.quantity ⟺ derivation.quantity 수렴** — quantity는 시장 값이 아니라 사이징(derivation)
  산출이며, 이는 "값-표면 재-소싱"이 아니라 별개 seam(derivation 재-소싱)이다. §10-3 인접 이연.
- **deterministic-float 투영** — #32 §2.5 미비준. 분수/비정수 가격은 fail-closed 유지.
- **다심볼/다-send per-attempt 보유 키잉** — 스테이지 단일-보유(single-retention) 모델은 GAP-3
  `OrderConstructionStage.construction`을 상속하며 #37(다심볼) 소관. §10-4.

**커널 잠식 금지**: `tos.venue` 커널(`order_shape_admissible`·`fold_venue_admissibility` 로직)·
`tos.engine` 코어를 잠식하지 않는다. venue 술어는 **미수정**(shape를 소비만). 엔진은 **무변경**(§5.1).

### 0.3 발명 금지 (서베이 §E 1편 (a)-(e) 전사 + (c) 인용 정밀화·구속)

> (a) `price_min/price_max/tick_size`를 "4,499,000이 통과하도록" **임의 선택** — P0-2 소관 사실이며
>     승인 없이 정한 값은 **반드시 provisional 표기 + register 미결 등재**(#34 §9 `:718`).
> (b) 좌표(`EgressCoordinateSet`)를 "값-표면"에서 유도하는 것 — 좌표는 route/credential 사실이지
>     시장 값이 아니다(#35 §4.4 item 17 `:319-321` "가격 직접 대조 0"). 좌표 건은
>     **transport/route inventory 파생**으로 재프레이밍하거나 이연 유지가 정직.
> (c) 반올림/정규화 도입 — `order_shape_admissible`의 무-반올림 계약(venue `predicates.py:227-231`·
>     `:252-254` "silently_rounded is not False → INADMISSIBLE") 위반.
> (d) `AdmittedPriceObservation` 필드 추가 시 C11(`test_slice_gaps.py:283-288`) FLIP을 계약에 명시
>     하지 않고 진행하는 것.
> (e) `send_boundary_context`에서 `order_shape` 파라미터 제거(C1 목록 확대) — 하위호환 파괴이므로
>     별도 판정 없이 금지.

**인용 정밀화(v1.1·MINOR-4)**: (c)의 서베이 원문은 `predicates.py:230-231`만 지목했으나, 무-반올림
계약은 docstring(`:227-231`)과 코드(`:252-254` `silently_rounded is not False → INADMISSIBLE`) 두 곳에
걸쳐 있어 fresh read로 정밀화했다. (a)·(b)·(d)·(e)는 서베이 원문 그대로 전사.

**이 계약의 처분**: (a) §3.4·§10-2에서 provisional stand-in의 충족 조건만 정의하고 실값은 미결 등재.
(b) §0.5에서 좌표를 스코프 제외·transport/route-inventory 재프레이밍으로 정제. (c) §4는 **정수 exact
투영만** — 반올림/정규화/silent float 전면 금지. (d) 본 계약은 `AdmittedPriceObservation`에 **필드를
추가하지 않는다** — 투영 산출은 raw `int`이지 신규 관측 필드가 아니므로 **C11은 GREEN 유지·FLIP 없음**
(§6). (e) `send_boundary_context` 팩토리는 **완전 무변경** — `order_shape`(records.py:610) 파라미터
보존, 슬라이스가 그 파라미터에 넣는 **값**만 바뀐다(§3.3·§5.2).

### 0.4 정직 서술 (닫는 EV 0·acceptance 아님)

본 계약은 **어떤 EV도 닫지 않고** acceptance가 아니다. 슬라이스 e2e·conformant 관측이 배선 변경 후에도
**동일 GREEN**을 유지하는 것이 완료 판정이며(§7), 그것은 저작 증거이지 EV PASS가 아니다(#35 §1.1 상속).
sizing bound(P0-1)·broker-specific bound(P0-2)는 여전히 미승인·provisional(#34 §9).

### 0.5 오케스트레이터 판정 ② — 좌표 스코프 제외 (원문 인용 + 이연 정제)

**#35 §10-3 원문**(`docs/plans/2026-07-29-tos-slice-gap-closing-design.md:553-557`):

> 3. **값 표면 단위 일관성(minor-unit vs 실가격)·deterministic-float 투영·venue_shape.price 및
>    authorized_coordinates의 값-표면 재-소싱(MAJOR-3)** — GAP-3은 사이징/command 가격만 값-표면 재-소싱
>    하고, venue admissibility의 shape 가격(`venue_shape().price=4,200`)과 egress 좌표는 fixture 잔존
>    한다(어떤 verify 경로에도 무저촉 — §4.4 4-경로 grep 실증). 전부 D-E2 marketfeed 값-표면 소관
>    (#32 §2.5)·명시 이연.

**서베이 오케스트레이터 판정 ②**(`2026-08-05-...survey.md:459-461`):

> **①의 좌표 절반**: 값-표면 재-소싱 대상에서 **제외**한다. 좌표는 시장 값이 아니라 route/credential
> 사실이므로 "값-표면 재-소싱"의 원문 스코프 모호는 transport/route-inventory 소관(D-E4·P0-2 후속)
> 재프레이밍으로 해소하고, #36 §0에 원문 인용과 함께 이연 정제(refinement)로 기록한다 — 침묵 드롭 금지.

**이연 정제(refinement)**: #35 §10-3은 "venue_shape.price **및** authorized_coordinates"를 한 이연 항목에
묶었다. #36은 그 항목을 **둘로 분리**한다 — (i) venue_shape.price = **본 계약이 닫음**(시장 값·값-표면
소관), (ii) authorized_coordinates = **이연 잔존**(route/credential 사실). `exact_binding_holds`
(`gateway.py:1169-1174`)는 좌표를 endpoint/route/credential-generation/egress-generation으로 대조하며
**가격을 직접 대조하지 않는다**(#35 §4.4 경로 3 실증). 따라서 좌표는 값-표면이 아니라 **transport/route
inventory**(D-E4 `Transport` 경계·#34 §5.1)와 **P0-2 route 사실**의 파생이며, 그 재-소싱은 실 KIS
transport(P0-2 후속) 착지 시 `EgressCoordinateSet` 소싱 계약으로 다룬다. `authorized_coordinates`
파라미터(`records.py:618`)·fixture(`_slice_fixtures.py:804-817`)는 **#36에서 무변경**.

### 0.6 소관 원문 인용 (구속 입력)

- **#32 §2.5**(`docs/plans/2026-07-29-tos-marketfeed-design.md:333-343`): "수치 순서비교 값은 정수
  tick-scale로 노출한다(우선) … **분수 수량이 불가피하면 deterministic float 투영만** … canonical 값이
  exact 정수/deterministic-float로 투영 불가면 값을 **노출 안 함**(구조적 UNKNOWN·fail-closed) — silent
  `float()` 강제 금지." + `:275`("`value` | `ScalarValue`(=bool|int|float|str) … **정수 tick-scale
  우선·Decimal 금지**").
- **#34 §9**(`docs/plans/2026-07-29-tos-egressgw-brokeradapter-design.md:715-718`): "| broker-specific
  bound(rate/admission·detection/containment·late-event window) | P0-2(Broker Capability Profile) |
  **미결**(KIS 초안 §7 item3 `hard_limits: {}`·null 다수)·provisional |". ⇒ `price_min/price_max/
  tick_size`는 이 행의 broker-specific bound이며 임의 조정은 인간 게이트(P0-2) 밖 발명.

---

## 1. 이연 → 본 계약 뿌리 지도 (§별 인용·실측)

| 뿌리(설계 §·명시 이연) | file:line | 본 계약의 처분 |
|---|---|---|
| #35 §10-3 "venue_shape.price 재-소싱" | `2026-07-29-tos-slice-gap-closing-design.md:553-557` | §3~§4 값-표면 seam으로 닫음 |
| #35 §4.4 "슬라이스 내부 비정합 정직 명기(MAJOR-3)" | `:326-334`, 4-경로 실증 `:310-325` | §2에서 뒤집을 전제로 재확인; §7 e2e가 정합 실증 |
| #35 §12 "shape/coordinates 비정합(리스크)" | `:604-606` "미래 slice가 venue admissibility를 값-표면 gated로 강화하면 이 fixture 재-소싱이 접합점" | **본 계약이 그 접합점** |
| #35 §11-6 선제 반론 | `:586-588` "venue_shape는 별개 fixture … GAP-3은 값+계보만 흘린다" | shape도 이제 값+계보(정수)로 흘림 |
| GAP-3 선례(닫힌 seam) | `construction.py:149-218`(`admitted_price_from_view`)·`:896-907`(`_price_for`) | **동형 확장**(step 2 → step 3/item 11) |

**교차 진단**: GAP-3은 D-E4 **사이징**이 D-E2 값-표면을 소비하는 접합을 닫았다. #36은 D-E4 **venue
admissibility**(step 3 + item 11)가 **같은 값-표면**을 소비하는 접합을 닫는다 — 동일 seam의 두 번째 뻗음.
①은 ②(CIS)가 아니라 **GAP-3 구현 자체에 의존**하며 그 의존은 이미 충족(서베이 §D `:336-339`).

---

## 2. 현재-상태 실측 (재-소싱 "전" 배선·2026-08-05 fresh grep)

### 2.1 타입 사실

| 표면 | 타입 | file:line |
|---|---|---|
| `OrderShapeFields.price` | **`int \| None`** | `tos/src/tos/venue/records.py:153` |
| `VenueShapeConstraints.price_min/price_max/tick_size` | **`int \| None`** | `venue/records.py:126-129` |
| `ContextValue.value` | **`ScalarValue = bool \| int \| float \| str`** | `tos/src/tos/dsl/context_value.py:118`·`vocabulary.py:93` |
| `AdmittedPriceObservation.value` | `CanonicalDecimal \| None` | `egressgw/records.py:173` |
| `QuantityDerivation.price` | `CanonicalDecimal \| None` | `egressgw/records.py:276` |

**귀결**: 값-표면은 `int`(정수 minor-unit·서베이 B.1 `LOWER_BAND=4_500_000`), shape 목적지도 `int`.
GAP-3의 `admitted_price_from_view`는 `Decimal(magnitude)`로 감쌌으나(`construction.py:215`), shape는
**int→int 항등 투영**이라 Decimal 왕복이 없다 — 더 단순하며 `#32 §2.5` "Decimal 직접 노출 금지"와 정합.
`ScalarValue`가 `float`/`bool`을 포함하므로 정수 exact 체크는 **방어가 아니라 load-bearing**(§4).

### 2.2 이중 주입 실태 (수렴 대상의 정직 경계·MAJOR-3)

item-11 fold(`gateway.py:825-832`)는 **6입력**을 받는다: observed_session_phase·action_class·
venue_snapshot·venue_policy·**order_shape**·**venue_shape_constraints**. 이 중 슬라이스는 **5개**를
스테이지 생성과 item-11 컨텍스트 두 곳에서 각각 만든다:

| fold 입력 | step-3 스테이지 생성 | item-11 컨텍스트 | 성격 |
|---|---|---|---|
| snapshot | `_slice_fixtures.py:977` | `:935` | 결정론 생성·구조 동일 |
| policy | `:978` | `:936` | 결정론 생성·구조 동일 |
| decision | `:981` | `:937` | 결정론 생성·구조 동일 |
| **shape** | `:979`(`venue_shape()`→price=4200) | `:940` | **런타임 값-표면 값을 실음** |
| **constraints** | `:980`(1000/9000/25) | `:941` | shape와 함께 가격 대조되는 짝 |

**#36의 수렴 스코프(정직 경계)**: `order_shape_admissible(shape, constraints)`(`predicates.py:280-291`)가
**가격을 대조하는 쌍**은 shape·constraints 둘뿐이다. #36은 이 **가격 대조 경로**만 스테이지 단일 소유로
수렴하고(§3.3), snapshot/policy/decision(session-phase 경로·gateway 별개 admit 체크)은 **결정론 생성이라
값을 실지 않으므로 이중 주입을 정직 잔존으로 등재**한다 — 이들까지 수렴시키면 "venue_shape.price 값-표면
재-소싱" 밖의 scope creep이다(§11-5). shape는 런타임 값(4,499,000)을 실으므로 **수렴 필수**, constraints는
그 shape가 대조되는 짝이라 스테이지-보유 번들로 동반한다(§9-4 뮤테이션의 double-failure 논증이 제약 이동에
의존하므로 constraints 수렴은 드롭하지 않는다·§11-5).

### 2.3 두 fold 소비 지점

| fold | 소비 | file:line |
|---|---|---|
| step 3 스테이지 | `fold_venue_admissibility(shape=self._shape, constraints=self._constraints, …)` | `construction.py:967-977`(`VenueConstraintStage.__call__`) |
| gateway item 11 | `fold_venue_admissibility(shape=context.order_shape, constraints=context.venue_shape_constraints, …)` | `gateway.py:825-832`(`_check_venue`) |

`_check_venue`(`gateway.py:804-868`)는 "step 3 *produces*, gateway *enforces* the exact current result"
(`:811-815`)로 **재-fold**한다. `fold_venue_admissibility`(`construction.py:775-827`)는
`order_shape_admissible`(`predicates.py:221-301`)을 부른다: `shape.price`를 `constraints.price_min/
price_max`(band·`:280`)·`tick_size`(grid·`:282`)에 대조. **어떤 fold도 command 가격을 shape 가격에
대조하지 않는다** — 이것이 #35 §4.4가 "무해"로 실증한 비정합의 통로다.

### 2.4 재-소싱 시 실측 마찰 (닫으면서 다뤄야 할 것)

1. **투영 목적지 int** — `admitted_price_from_view`는 Decimal 반환. shape용 int 투영 함수 필요(§4).
2. **제약 fixture 강제 이동** — shape.price가 4,499,000이 되면 현 제약(1000/9000/25)은
   `order_shape_admissible`에서 `4,499,000 > 9000` → **INADMISSIBLE**(`predicates.py:280`) → item 11
   DENIED → **e2e FAIL**. ⇒ `price_min/price_max/tick_size` **동반 이동 강제**, 그 수치가 P0-2 소관
   (§0.6·§3.4). quantity(20)·lot(2)·qty band(2/100)는 **불변**(가격만 값-소싱).
3. **StageRequest.value_view는 이미 step 3에 도달** — 시퀀서가 `for step in SEQUENCED_STEPS` 루프
   (`sequencer.py:319`)에서 **모든** step의 `StageRequest`에 `value_view=value_view`를 채운다
   (`:428`, docstring `:304-305` "carried onto **every** StageRequest"). ⇒ **#36은 엔진 무변경**
   (§5.1). GAP-3이 신설한 `StageRequest.value_view`(`test_gap_3` `:293` 실측)를 재사용만 한다.

---

## 3. 설계 결정 (대안 검토·기각 포함)

### 3.1 판정 요약

| # | 결정 | 배치 | 대안·기각 |
|---|---|---|---|
| D1 | 정수 exact 투영 함수 `admitted_shape_price_from_view` 신설 + `admitted_price_from_view`와 **공유 코어** `_exact_admitted_int_value` 추출 | `construction.py`(기존 submodule) | §3.2 |
| D2 | `VenueConstraintStage`에 `shape_price_field_key`(additive kw-only) + `_shape_for(request)` 값-표면 우선/주입 폴백 + `resolved_shape` 보유 | `construction.py` | §3.3 |
| D3 | 수렴 = 스테이지가 (resolved_shape, 제약)의 **단일 소유자**; resolver가 스테이지에서 읽음 | `_slice_fixtures.py` | §3.3 |
| D4 | 제약 수치 = provisional stand-in(충족 조건만 정의) + 미결 등재 | `_slice_fixtures.py` | §3.4·§10-2 |

**신규 .py 0**(C5·§6 submodule-drift canary). 신규 심볼 전부 기존 `construction.py`에.

### 3.2 D1 — 투영 함수 (GAP-3 `_price_for` 선호 패턴 동형)

**신설(public·`construction.py`)**:

```python
def admitted_shape_price_from_view(view: ContextValueView, *, field_key: str) -> int | None:
    """Project one admitted Critical Input value onto an integer venue-shape price (design #36 §4).

    OrderShapeFields.price is int, and D-E2 exposes numeric order-comparison values as integer
    minor / tick units (design #32 §2.5), so this is an exact int→int projection — no Decimal
    round-trip, no rounding, no normalization. An absent / non-unique / non-integer value yields
    None: an unknown shape price is a structural UNKNOWN at order_shape_admissible, never a
    last-known injected default. The exact-int / bool≠1 admission rule lives once in
    :func:`_exact_admitted_int_value` (design #36 §3.2), so this projection cannot drift from the
    price projection's.
    """
    magnitude, _cv = _exact_admitted_int_value(view, field_key=field_key)
    return magnitude
```

**공유 코어(private·behavior-preserving 추출·배치 = `admitted_price_from_view` 직전·MAJOR-2)**:

```python
# ★ 배치: admitted_price_from_view (현 construction.py:149) 직전에 정의 — 공유 코어를 먼저 두어
#   앵커 이동 방향을 하향 단일화(구현 시 정확 라인 REGREP·§12).
def _exact_admitted_int_value(
    view: ContextValueView, *, field_key: str
) -> tuple[int | None, ContextValue | None]:
    """The single #32 §2.5 exact-integer admission predicate both projections share.

    Returns (magnitude, ContextValue) when exactly one value carries field_key and its value is an
    exact int; otherwise (None, None). This is the sole definition of "an exact-integer admitted
    value", so admitted_price_from_view and admitted_shape_price_from_view cannot drift in what
    they admit (design #36 §3.2).

    ★ bool≠1 계약 (construction.py:182-186 문단에서 이관·MAJOR-2): ``ScalarValue`` is
    ``bool | int | float | str`` (``dsl/vocabulary.py:93``), so a ``bool``-valued ``ContextValue``
    is reachable, and ``bool`` is an ``int`` subclass in Python — refused by the **exact**
    ``type(magnitude) is not int`` check, never by an ``isinstance`` that would silently admit
    ``True`` as ``1`` (design #32 §2.5 order-comparison excludes bool). This is the exact line
    test_egressgw_construction.py's bool canary mutates; its docstring anchor moves here (§6 V3).
    """
    if not view.values:
        return (None, None)
    matched = [value for value in view.values if value.field_key == field_key]
    if len(matched) != 1:
        # ★ ==1 양성 멤버십 (construction.py:205-207에서 이관·MINOR-3): ContextValueView already
        #   rejects duplicate field keys, so the only reachable non-unique case is zero matches;
        #   the positive ``== 1`` keeps a future relaxation from falling open here.
        return (None, None)
    cv = matched[0]
    magnitude = cv.value
    if type(magnitude) is not int:
        return (None, None)
    return (magnitude, cv)
```

**`admitted_price_from_view` 재작성(behavior-preserving)** — 관측-특유의 ∅ 구분(explicit-empty=no-source
vs missing=lineage-only)은 그대로 유지하고 match+int 코어만 위임:

```python
def admitted_price_from_view(view, *, field_key):
    if not view.values:
        return AdmittedPriceObservation()                       # explicit-empty → no source (불변)
    lineage = AdmittedPriceObservation(
        source=CAPSULE_CONTEXT_SOURCE, snapshot_digest=view.snapshot_canonical_digest)
    magnitude, cv = _exact_admitted_int_value(view, field_key=field_key)
    if magnitude is None or cv is None:
        return lineage                                          # missing/non-int → lineage-only (불변)
    return AdmittedPriceObservation(
        source=CAPSULE_CONTEXT_SOURCE, value=Decimal(magnitude),
        snapshot_digest=view.snapshot_canonical_digest, value_payload_digest=cv.payload_digest)
```

네 반환 shape(bare / lineage-only / valued / — )가 **전부 불변**이므로 GAP-3 테스트
(`test_gap_3_*`·`test_gap_3_a_value_the_view_does_not_carry_is_a_no_send`
`test_slice_gaps.py:320-346`)는 GREEN 유지(§6·§7 회귀 게이트).

**docstring 보존 + 앵커 이관 (MINOR-3·MAJOR-2·완료 기준)**: `admitted_price_from_view`는 **본문만 위임**
하고 타입 어노테이션·Args/Returns·∅ both-ways 문단은 **보존**한다. 단 (i) exact-int/bool≠1 계약 문단
(현 `construction.py:182-186`)은 검사가 옮겨간 `_exact_admitted_int_value` docstring으로 **이관**(포인터
한 줄만 잔존), (ii) `==1` 양성 멤버십 주석(현 `:205-207`)도 공유 코어로 이관(위 스니펫). **하드코딩 앵커
재조준 의무**: `test_egressgw_construction.py:750-752`가 `construction.py:211`(type 검사)·`:184-186`
(bool docstring 문단)을 **리터럴 인용**하는데, P2가 검사·문단을 이동하면 둘 다 오조준되고 egressgw엔
anchor-drift 테스트가 없어 **loud FAIL 없이 misaim**한다(#32 v1.2류 silent drift). ⇒ **같은 커밋에서**
두 인용을 `_exact_admitted_int_value`의 새 라인으로 재조준할 것을 완료 기준으로 지정(§6 V3 REGREP·§12).
검사가 shape 투영 경로에서도 도는 만큼, 재조준 문구는 "both projections" 정합으로 확장 가능(선택).

**검토·기각한 대안**:

- **(P1) standalone — `admitted_shape_price_from_view`가 match+int 로직을 독립 재구현** — 기각.
  shipped `admitted_price_from_view`를 무저촉으로 두어 GAP-3 seam 안정성엔 유리하나, `#32 §2.5`의
  "exact int only·bool 거부·float fail-closed" 계약이 **두 곳에 산문화**되어 미래 완화가 한쪽에만
  도달하는 **drift class**(MEMORY: "저작-레벨 잠금"·"하드코딩 census는 신규 항목을 영원히 못 찾음")를
  연다. P2(공유 코어)는 계약을 **한 정의**로 잠근다. drift 위험 > seam 재작성 위험(후자는 behavior-
  preserving·GAP-3 suite가 게이트).
- **(P3) `admitted_shape_price_from_view`가 `admitted_price_from_view(...).value`를 int로 캐스팅** —
  기각. `int(Decimal)`은 truncate 가능(무결성 왕복 발명). shape는 int-공간에 머무는 것이 정직.
- **(P4) `AdmittedPriceObservation`을 shape 투영에 재사용** — 기각. 관측 타입은 source/snapshot/
  payload_digest 계보를 실으나 shape.price는 raw int이며 계보 필드가 없다. 억지로 실으면 필드 추가 →
  C11 FLIP(§0.3 (d)). raw int 투영은 필드 추가 0.

### 3.3 D2·D3 — `VenueConstraintStage` 값-표면 스레딩 + 스테이지-보유 수렴 (additive)

**현 시그니처**(`construction.py:947-965`, fresh):

```python
class VenueConstraintStage:
    def __init__(self, *, observed_session_phase, action_class, snapshot, policy,
                 shape, constraints, decision=None) -> None: ...
    def __call__(self, request) -> StageVerdict:                     # :967-977
        result = fold_venue_admissibility(..., shape=self._shape, constraints=self._constraints)
        return venue_admissibility_verdict(result, self._decision, step=request.step)
```

**#36 후(additive·GAP-3 `OrderConstructionStage`와 동형)**:

```python
class VenueConstraintStage:
    def __init__(self, *, observed_session_phase, action_class, snapshot, policy,
                 shape, constraints, decision=None,
                 shape_price_field_key: str | None = None) -> None:   # ★ 신규 kw-only (default None)
        ...
        self._shape_price_field_key = shape_price_field_key
        self.resolved_shape: OrderShapeFields | None = None           # ★ 보유 (init None·fail-closed)

    @property
    def shape_constraints(self) -> VenueShapeConstraints | None:      # ★ 단일-소유자 read 접근자
        """The injected constraints, exposed so the item-11 context reads the same object the
        step-3 fold used (design #36 §3.3 convergence)."""
        return self._constraints

    def _shape_for(self, request: StageRequest) -> OrderShapeFields | None:  # ★ GAP-3 _price_for 동형
        """The shape this step folds and the item-11 context reuses (design #36 §3.3).

        The value surface wins when both a governed shape_price_field_key and a published view are
        present — that is the number the decision was actually priced on. A tick that carried no
        view is value-free, not "no price": the injected shape stands in unchanged. When the field
        is governed but the value is unprojectable, the price becomes None (fail-closed) — an
        unknown shape price is a structural UNKNOWN at order_shape_admissible, not the stale
        injected 4,200.

        ⚠ Under #36's moved provisional constraints (§3.4) the injected fallback price 4,200 is
        itself INADMISSIBLE — (4,200 − 1,000) mod 1,000 ≠ 0 — so a value-free tick reaching step 3
        fails admissibility rather than silently passing. The slice's crossing tick always carries
        a view, so this fallback path is unexercised on the happy path; but §9-4's mutation
        detection relies on exactly this (reverting the item-11 shape to 4,200 is caught here).
        """
        view = request.value_view
        if self._shape_price_field_key is None or view is None:
            return self._shape                                       # 값-소싱 미배선/value-free tick → 주입 폴백
        if self._shape is None:
            return None
        projected = admitted_shape_price_from_view(view, field_key=self._shape_price_field_key)
        return self._shape.model_copy(update={"price": projected})   # price만 override·나머지 필드 주입 유지

    def __call__(self, request) -> StageVerdict:
        resolved_shape = self._shape_for(request)
        self.resolved_shape = resolved_shape                         # ★ 보유 (수렴 소스)
        result = fold_venue_admissibility(
            observed_session_phase=self._observed_session_phase,
            action_class=self._action_class, snapshot=self._snapshot, policy=self._policy,
            shape=resolved_shape, constraints=self._constraints)     # was self._shape
        return venue_admissibility_verdict(result, self._decision, step=request.step)
```

**수렴 메커니즘(closure의 실체·MAJOR-3 정직 경계)**: 스테이지가 `resolved_shape`(가격=값-표면)와
`shape_constraints`를 **단일 소유**한다 — 이 둘이 `order_shape_admissible`이 대조하는 **가격 대조 쌍**이다.
슬라이스 resolver가 `venue_shape()`/`venue_shape_constraints()`를 **재호출하지 않고** 스테이지에서 읽는다
(§7 배선). step-3 fold와 gateway item-11 re-fold가 이 **동일 객체 2개**를 소비 → **가격 대조 경로 한 축이
한 소스로 수렴**한다(전 입력 붕괴가 아님 — snapshot/policy/decision 이중 주입은 §2.2대로 정직 잔존).
`resolved_shape`는 `OrderConstructionStage.construction`(`construction.py:889` init None)과 **동일 보유
모델**: step 3에서 set, resolver는 step 12+ Transmit 시점에 읽으므로 admit 경로에서 항상 populated;
pre-step-3 read는 None(fail-closed).

**resolver의 `resolved_shape` None 정책(What's Missing 반영)**: `resolved_shape`가 None이거나 price=None이
되는 경우 — (i) `self._shape is None`, (ii) 값-소싱 중 비투영 → price None — 는 **step 3 fold를
`UNKNOWN`으로 만들어 스테이지 자신이 flow를 halt**한다(`venue_admissibility_verdict(UNKNOWN)`). Transmit/
resolver는 step 12+에만 도달하므로 **step 3이 admit한 경우에만** 호출된다 ⇒ resolver가 관측하는
`resolved_shape`는 **항상 투영 완료된 admissible shape**(step 3이 게이트). 방어적으로 None이 새더라도
resolver는 **None-guard를 추가하지 않는다** — `order_shape=None`이 item 11로 흘러 `_check_venue`가
`UNKNOWN`("venue admissibility is UNKNOWN — restrictive"·`gateway.py:833-840`)을 기록한다. 이는
`CONTEXT_MISSING`이 **아니다**: 증거는 "부재한 실제 사실"(venue 결과 UNKNOWN)을 명명하며, 빈 컨텍스트로
치환해 다른 사실을 오보하지 않는다(`test_slice_gaps.py:262-266` 규율 보존). resolver가 shape-None을
context-None으로 격상하면 그 오보를 범하므로 guard를 두지 않는다.

**`model_copy(update={"price": projected})` 안전성**: `projected`는 투영 경계에서 `int | None` 보증
(§4의 `type() is int` 체크). 필드 타입도 `int | None`이라 미검증 시장값이 실릴 수 없음 — validation-
bypass copy가 안전. `silently_rounded`(주입 `False`·`records.py:161`)는 override 대상 아님이며, 투영이
**exact**(무-반올림)이므로 witness `False`가 정직하게 유지된다(§4).

**검토·기각한 대안**:

- **(A) 파생 전환 — `order_shape`를 `send_boundary_context` 팩토리 안에서 파생 필드로** — 기각.
  (i) 팩토리 `order_shape` 파라미터 제거/변경 → **C1 위반**(§0.3 (e)). (ii) 팩토리는 `value_view`를
  받지 않으므로 view를 팩토리로 스레딩해야 → **factory 시그니처 폭발**(#35 MAJOR-2 결함 클래스 재발).
  (iii) additive-우선 원칙(#35 §3.2·GAP-3 `_price_for`) 위배. GAP-3의 `_price_for`는 값-표면 존재 시
  우선·부재 시 주입 폴백을 **스테이지에서** 했고 팩토리는 불변으로 뒀다 — #36은 그 선례를 정확히 답습.
- **(B) resolver가 `request.value_view`로 독립 투영** — 기각. resolver(`RecordingContextResolver.
  __call__`·`_slice_fixtures.py:1039-1057`)는 `StageRequest`를 받지 않고 `attempt` + 스테이지 아티팩트
  만 읽는다(`construction_stage.construction`·`proof_stage.proof`). 별도 view 스레딩은 표면 확대이고,
  "두 계산이 일치"는 "한 소스"보다 약하다. 스테이지-보유(D3)가 GAP-3 `construction` 보유와 동형인
  **단일 객체 수렴**.
- **(C) 스테이지가 `EgressResultSource`처럼 게이트에 메서드 노출** — 해당 없음(GAP-1 문제). 무관.

### 3.4 D4 — 제약 수치 provisional (메커니즘만·P0-2 미결 등재)

`venue_shape_constraints()`(`_slice_fixtures.py:740-753`)의 `price_min/price_max/tick_size`는
**provisional stand-in**으로 이동하며, 계약은 실값이 아니라 **충족 조건**만 정의한다:

> 값-표면 shape 가격 `V`(슬라이스에서 crossing close = 4,499,000)에 대해 provisional (price_min,
> price_max, tick_size)를 다음을 만족하도록 선택: `price_min ≤ V ≤ price_max` **且** `(V − price_min)
> mod tick_size == 0`. 한 admissible stand-in: `(1000, 9_000_000, 1000)` — `(4,499,000−1000) mod 1000
> = 0`. 실 (price_min, price_max, tick_size)는 **P0-2 Broker Capability Profile INSTANCE 소관**
> (#34 §9 broker-specific bound 행)이며 §10-2 미결 등재.

**quantity band 불변**: `lot_size=2, min_quantity=2, max_quantity=100`(`:746-748`) 무변경 —
shape.quantity=20은 값-소싱 아님(`20 ∈ [2,100]`·`20 mod 2 = 0`). enum set(`allowed_*`) 무변경.

**두 provisional 제약 세트 공존(What's Missing 반영)**: `_egressgw_fixtures.venue_shape_constraints()`
(`test_egressgw/_egressgw_fixtures.py:303-…`·1000/9000/25)는 **이동하지 않는다** — egressgw 단위 테스트는
값-소싱을 켜지 않아(`shape_price_field_key` 미주입) shape가 4,200에 머물고, 4,200은 (1000/9000/25) 하에
admissible이다(`1000 ≤ 4,200 ≤ 9,000`·`(4,200−1,000) mod 25 = 0`). ⇒ 슬라이스 fixture만 provisional
이동하며 **provisional 주석 의무는 슬라이스 `_slice_fixtures.py:740-753`에만** 부착(egressgw 단위 fixture는
자기-정합·불변). 두 세트가 서로 다른 provisional 수치로 공존함을 정직 명기(둘 다 P0-2 소관이나 이동 범위는
값-소싱을 켠 슬라이스에 국한).

---

## 4. 정수 minor-unit 투영 규율 (#32 §2.5 준수)

- **정수 exact 투영만** — `type(magnitude) is not int → (None, None)`. `bool`은 int 서브클래스이나
  `type() is int`가 `True/False`를 거부(`isinstance` 아님·#32 §2.5 "순서비교는 int/float 전용·bool
  제외"·vocabulary.py:366-368). `float`/`str`/`Decimal`은 미투영(deterministic-float 규칙 미비준).
- **투영 불가 = 값 미노출** — 부재/비유일/비정수 → `None` → `_shape_for`가 `price=None` shape 산출 →
  `order_shape_admissible`(`predicates.py:257`) → `UNKNOWN`(fail-closed) → item 11 restrictive.
  **주입 4,200으로 폴백하지 않는다**(값-소싱 모드에서 unprojectable은 no-send).
- **반올림·정규화 발명 금지** — 투영은 int 항등. `order_shape_admissible`의 무-반올림 계약
  (`predicates.py:227-231`·`:252-254`)·`OrderShapeFields.silently_rounded` witness(`records.py:159-161`)
  보존. 투영이 exact이므로 `silently_rounded=False`가 정직 유지.
- **값⟺digest 계보** — shape.price는 raw int(계보 필드 없음)이나 투영 소스는 command 가격과 **동일
  `ContextValue`**(같은 field_key)다. §7 수렴 canary가 `shape.price == command.derivation.price ==
  view의 field_key ContextValue.value`를 실증해 계보 동일성을 관측. 검증은 **생산 시점**(D-E2·#32 §2.3
  trust seam) 소관, 소비측 재검증 안 함(over-claim 금지).

---

## 5. 하위호환 판정

### 5.1 엔진 무변경 (실측)

#36은 `StageRequest`/`sequencer`/`core`/`engine`을 **무변경**. GAP-3이 신설한 `StageRequest.value_view`
(`sequencer.py:428`이 모든 step에 채움·§2.4)를 재사용만 한다. GAP-4의 `held_position_magnitude`처럼
신규 필드/스레딩 **0건**. 터치는 `egressgw/construction.py` + `egressgw/__init__.py`(export) + 슬라이스
fixture + 테스트로 국한.

### 5.2 팩토리·컨텍스트 무변경 (C1 보존)

`send_boundary_context`(`records.py:577-635`) **완전 무변경** — `order_shape`(:610)·
`venue_shape_constraints`(:611)·`authorized_coordinates`(:618) 파라미터 전부 보존. C1 negative-list
(`test_egressgw_gateway.py:748-758`)에 `order_shape` 부재 유지 → GREEN. `SendBoundaryContext`
(`records.py:450-553`) 필드 무변경 → `test_gap_3` `"value_view" not in SendBoundaryContext.model_fields`
(`:294`) GREEN. `AdmittedPriceObservation` 필드 무변경 → C11 GREEN(§0.3 (d)).

### 5.3 스테이지 시그니처 additive

`VenueConstraintStage.__init__`에 `shape_price_field_key: str | None = None` **1개 kw-only**(default
None). 기존 생성부(슬라이스 `:974-982`·egressgw 단위 `test_egressgw_construction.py:692-704`)는 인자
미지정 → `_shape_for`가 `self._shape` 반환(값-소싱 off) → **행동 불변**. GAP-3 `OrderConstructionStage.
__init__`의 `price_field_key` 추가(`construction.py:865`)와 정확히 동형. C10-류 REGREP(§12).

---

## 6. committed canary 전수 census + 호환 판정 (필수 이행·#32 v1.2 교훈)

**범례**: FLIP=의도된 loud 실패·GREEN=무영향·WIDEN=additive 확대(canary 갱신)·REGREP=구현 시점 재실측·
앵커 재조준. 서베이 C1-C11은 **시작점**이며, 아래는 터치 표면 committed canary **직접 전수 재-grep**
(v1.1 freshness 교정 반영·MAJOR-4).

| # | 터치 표면(file:line) | committed canary(file:line) | 변경 | 판정 |
|---|---|---|---|---|
| **V1** | `AdmittedPriceObservation`(4필드) | `test_slice_gaps.py:283-288`(`model_fields == [source,value,snapshot_digest,value_payload_digest]`) | **필드 추가 0** | **GREEN**(§0.3 (d)·no-FLIP 명시) |
| **V2** | `admitted_price_from_view` 재작성(P2·본문만 위임) | `test_slice_gaps.py:274-317`(`test_gap_3_*`)·`:320-346`(∅ both-ways) | behavior-preserving 추출 | **GREEN**/REGREP — 4 반환 shape 불변; 전 GAP-3 test 재실행 게이트 |
| **V3** | bool≠1 exact-int 검사 + docstring **이동**(P2) | `test_egressgw_construction.py:743-744`(`test_a_bool_valued_context_value_is_never_projected_as_a_price`) + docstring **하드코딩 앵커** `:750-752`(테스트 리터럴 `construction.py:211`[test :750]·`:184-186`[test :751]; **이관 문단** `:182-186`) | 검사→공유 코어·docstring 문단 이관 | **REGREP(앵커 재조준 의무·MAJOR-2)** — 행동 GREEN(bool→None 불변)이나 두 리터럴 앵커를 `_exact_admitted_int_value` 새 라인으로 **같은 커밋 재조준** 필수; egressgw anchor-drift 테스트 부재로 loud FAIL 없음 |
| **V4** | `SendBoundaryContext` 필드 | `test_slice_gaps.py:294`(`value_view not in SendBoundaryContext.model_fields`) | 필드 추가 0 | **GREEN** |
| **V5** | 팩토리 negative-list + KEYWORD_ONLY | `test_egressgw_gateway.py:736-758`(C1·derived list `:748-758`) | 팩토리 무변경·`order_shape` 주입 유지 | **GREEN** — `order_shape` derived-list 부재 유지(파생 아님) |
| **V6** | 팩토리 ∅ item-17(무-command) | `test_egressgw_gateway.py:801-823` | 무변경 | **GREEN** |
| **V7** | e2e 17항목 SATISFIED(6 deferred N/A) | `test_slice_end_to_end.py:208-247`(C8) | shape 값-소싱 후 item 11 **SATISFIED 유지 목표** | **GREEN**(회귀 관문) — provisional 제약이 `V` admit |
| **V8** | 전송 스칼라 결속 | `test_slice_end_to_end.py:250-261`(C9·`request.price==context.outbound_price`) | shape만 변경·outbound 불변 | **GREEN** |
| **V9** | egressgw `__all__` phantom | `test_egressgw_package.py:35`(`test_every_exported_name_resolves`) | `admitted_shape_price_from_view` 추가(§7.4.1 정렬 규칙) | **WIDEN** — 실 export(hasattr 통과)·`__all__` 갱신 |
| **V10** | egressgw submodule drift(신규 .py 0) | `test_egressgw_import_closure.py:541-550`(`test_every_submodule_is_covered_by_the_closure_child`·`_SUBMODULES:199`·`_LOADED_SUBMODULES:208`) | 기존 `construction.py`에 심볼 추가 | **GREEN** — submodule 집합 불변 |
| **V11** | egressgw direct-import allowlist(`tos.dsl` edge) | `test_egressgw_import_closure.py:71-86`(`_ALLOWED_TOS_PACKAGES`) + edge-taken 체크(`:340-358` 부근) | `ContextValueView` 신규 참조 0(GAP-3이 이미 도입) | **GREEN** — 신규 edge 없음(`admitted_shape_price_from_view`가 이미 allowed한 dsl·venue만 참조) |
| **V12** | `VenueConstraintStage.__init__` 시그니처 | 정확-잠금 canary **부재**(`_Request` stand-in `test_egressgw_construction.py:620-641`가 kwargs 호출) | `shape_price_field_key` kw-only 추가 | **GREEN**/REGREP — additive(default None); 구현 시 재grep |
| **V13** | step-3 스테이지 fold 행동 | `test_egressgw_construction.py:553-568`(fold)·`:692-704`(protective-only deny)·`:199-326`(violation) | value-소싱 off default → 불변 | **GREEN** |
| **V14** | venue 커널(`order_shape_admissible` 등) | `test_venue_order_shape.py:*`·`test_venue_predicate_only.py:*` | venue 미수정 | **GREEN** — 커널 무저촉 |
| **V15** | brokeradapter 전송 fixture | `test_brokeradapter_transport.py:59`(price=4200) | 슬라이스 밖·별개 fixture | **GREEN** |
| **V16** | 슬라이스 shape/제약 fixture | `_slice_fixtures.py:730`(price=4200)·`:743-745`(제약) | shape.price=주입 base(런타임 override)·제약=provisional 이동 | 재배선(§7)·e2e GREEN 유지 목표 |
| **V17** | `construction.py` 소스에 `ContextValueView` 명명(**양성** 소스-텍스트 canary·MAJOR-1) | `test_slice_gaps.py:291`(`ContextValueView.__name__ in inspect.getsource(egressgw_package.construction)`) | 신규 함수도 `ContextValueView` 참조 | **GREEN** — 참조 유지·강화 |
| **V18** | `construction.py` 소스에 `marketfeed` 부재(**부재** 소스-텍스트 canary·MAJOR-1) | `test_slice_gaps.py:296`(`"marketfeed" not in inspect.getsource(egressgw_package.construction)`) | 신규 docstring·주석·코드 | **GREEN-조건부** — `construction.py` 신규 코드·docstring·주석에 토큰 `marketfeed` **사용 금지**(D-E2/#32 §2.5/값-표면으로 지칭)·§12 저작 제약 |
| **V19** | `construction.py` 모듈의 sibling-kernel 생산 심볼 부재(vars 스윕·MINOR-3) | `test_egressgw_package.py:62-88`(`test_no_module_exposes_a_sibling_kernel_production_symbol`·`_MODULES`에 construction 포함·`:82` vars 스윕) | 신규 심볼 2개 | **GREEN** — `admitted_shape_price_from_view`/`_exact_admitted_int_value`는 sibling-kernel 생산 심볼 아님 |
| **V20** | `construction.py` 모듈의 credential/transport fragment 부재 | `test_egressgw_package.py:90-101`(`test_no_module_defines_a_transmit_or_credential_holder`·forbidden=`app_key/app_secret/access_token/connect/socket`) | 신규 심볼명 | **GREEN** — 신규 심볼명에 금지 fragment 0 |
| **V21** | egressgw 패키지 정직 scope docstring(서베이 C6) | `test_egressgw_package.py:41-51`(`test_the_package_declares_its_honest_scope_in_its_own_docstring`) | 패키지 docstring 무변경 | **GREEN** |
| **V22** | egressgw 6/5/6 verify 분할 문구(서베이 C7) | `test_egressgw_package.py:54-59`(`test_the_package_states_the_six_five_six_split`) | 무변경 | **GREEN** |

**요약**: FLIP **0**(뒤집을 committed canary 부재 — 서베이 C-census 실측: shape가 "값-표면에서 오지
않음"을 단언하는 테스트 없음) · WIDEN **1**(V9 `__all__`) · **REGREP 앵커 재조준 1**(V3·MAJOR-2) ·
GREEN/조건부 나머지. **비-additive canary 파괴 0** — 모든 변경은 additive·fixture 이동·앵커 재조준이다.
V2(P2 추출)만 shipped seam 재작성이며 behavior-preserving + GAP-3 suite 게이트 + V3 앵커 재조준으로 봉인.
**V17·V18은 MAJOR-1이 적발한, 코드를 추가할 바로 그 파일(`construction.py`)에 대한 소스-텍스트 canary**
(V18의 `marketfeed` 토큰 금지가 저작 제약·§12). **V19-V22(v1.2 추가)**는 `test_egressgw_package.py`의
모듈-vars 스윕(`_MODULES`에 construction 포함)·패키지 docstring·6/5/6 분할 canary로, 신규 심볼 6개 전부
GREEN 실측 확인 → 전수 census 전칭 성립(델타 재검증 MINOR-3).

**anti-phantom(부재 주장 negative-grep·v1.1)**: (1) `grep -rn "admitted_shape\|shape_price\|
resolved_shape" tos/src/tos/egressgw/` → 0(신규·닫으면 존재로 전환). (2) `grep -rn "4200\|4,200" tos/`
→ 전부 fixture 상수/docstring(`_slice_fixtures.py:177/730`·`_egressgw_fixtures.py:85/291`·
`test_brokeradapter_transport.py:59`·`test_slice_gaps.py:279`) — **단언 0**. (3) shape가 값-표면에서
오지 않음을 단언하는 테스트 = 0 ⇒ FLIP 대상 없음. (4) `grep -n "marketfeed" tos/src/tos/egressgw/
construction.py` → **0**(V18 부재 canary 현 상태 GREEN — 신규 저작이 이를 깨지 않아야 함).

---

## 7. 슬라이스 배선 + 테스트 전환 계약 (완료 판정)

### 7.1 슬라이스 재배선(`_slice_fixtures.py`)

1. `venue_shape_constraints()`(`:740-753`) — `price_min/price_max/tick_size` provisional stand-in
   이동(§3.4) + `# ⚠ provisional (P0-2·register §8-2 candidate·#36 §10-2)` 주석(§8-1 함의 금지).
2. `construction_stages`(`:955-1003`) — `step3 = VenueConstraintStage(…, shape_price_field_key=
   PRICE_FIELD_KEY)`(§3.3). 반환 튜플에 `step3` 추가(`return stages, step2, step3, step11`) + **반환
   타입 어노테이션**(`:957`)도 4-튜플로 갱신(`tuple[dict[CommitmentStep, Stage], OrderConstructionStage,
   VenueConstraintStage, ConformanceProofStage]`·MINOR-5). 호출부는 `run_slice:1112` **1곳**(실측·안전).
3. `bind_send_boundary_context`(`:893-952`) — 시그니처에 `order_shape`·`venue_shape_constraints`
   파라미터 추가(fixture-level), `send_boundary_context(order_shape=order_shape,
   venue_shape_constraints=venue_shape_constraints, …)`로 전달. 인라인 `venue_shape()`(`:940`)·
   `venue_shape_constraints()`(`:941`) **호출 제거**.
4. `RecordingContextResolver`(`:1011-1057`) — `__init__`에 `venue_stage: VenueConstraintStage` 추가;
   `__call__`이 `bind_send_boundary_context(order_shape=self._venue_stage.resolved_shape,
   venue_shape_constraints=self._venue_stage.shape_constraints, …)`.
5. `run_slice`(`:1091-1151`) — `stages, step2, step3, step11 = construction_stages(book)`(`:1112`);
   `RecordingContextResolver(construction_stage=step2, proof_stage=step11, venue_stage=step3)`(`:1118`).

→ `venue_shape()`·`venue_shape_constraints()`는 이제 **step-3 스테이지의 주입 base로만 1회** 소비(가격은
런타임 override). item-11 컨텍스트는 스테이지 보유 소스를 읽음 → **한 소스 수렴**.

### 7.2 신규 테스트(`test_egressgw_construction.py` — 단위)

기존 `_single_value_view(value)`(`:723`)·`_Request` stand-in(`test_egressgw_construction.py:620-641`·
`step`/`proposal`/`value_view`/`held_position_magnitude` 보유·MAJOR-4: `_StageRequest` 아님) 재사용.

- `test_admitted_shape_price_from_view_projects_an_exact_integer` — `_single_value_view(4_499_000)` →
  투영 == `4_499_000`(int·not Decimal). (mirror `:785`)
- `test_admitted_shape_price_from_view_refuses_a_bool_or_float` — hypothesis over `st.booleans() |
  st.floats(allow_nan=False, allow_infinity=False)`(FrozenModel이 `allow_inf_nan=False` 핀·
  `canonical/_base.py:87`·코퍼스 선례 동형·MINOR-1); 투영 → `None`(#32 §2.5·M5 극성). (mirror
  `test_a_bool_valued_context_value_is_never_projected_as_a_price` `:743-744`)
- `test_the_two_projections_admit_and_refuse_the_same_values` — 임의 `ScalarValue`에 대해
  `admitted_shape_price_from_view(v) is not None` ⟺ `admitted_price_from_view(v).value is not None`.
  **공유 코어 계약 잠금**(drift 방지·anti-P1).
- `test_the_step3_stage_prefers_the_value_surface_price` — `VenueConstraintStage(shape=venue_shape(),
  …, shape_price_field_key="close")` + `stage(_Request(step=…, value_view=_single_value_view(4_499_000)))`
  → `stage.resolved_shape.price == 4_499_000` **且** `!= 4200`(주입 base와 다름).
- `test_the_step3_stage_falls_back_to_the_injected_shape_without_a_field_key` —
  `shape_price_field_key=None` **또는** `value_view=None` → `stage.resolved_shape is stage._shape`.
- `test_the_step3_stage_is_fail_closed_when_the_shape_price_is_unprojectable` —
  `shape_price_field_key="close"` + view가 non-int/missing 운반 → `resolved_shape.price is None` →
  fold `UNKNOWN` → verdict restrictive(주입 4,200으로 폴백하지 않음).

### 7.3 신규 테스트(`test_slice_end_to_end.py` — e2e 수렴)

- `test_the_venue_shape_price_is_value_sourced_and_converged` —
  ```python
  sliced = run_slice()
  crossing_close = sliced.book.context_for(CROSSING_BAR_INDEX).close
  (bound,) = sliced.resolver.contexts
  # ★ 값-소싱 (주입 4,200 아님)
  assert bound.order_shape is not None
  assert bound.order_shape.price == crossing_close
  assert bound.order_shape.price != 4200
  # ★ 한 소스 수렴: item-11 컨텍스트 shape == step-3 스테이지 보유 shape (객체 동일)
  assert bound.order_shape is sliced.venue_stage.resolved_shape   # SliceRun.venue_stage (신규 필드)
  assert bound.venue_shape_constraints is sliced.venue_stage.shape_constraints
  # ★ command 가격과 정합 (닫히는 비정합)
  assert bound.order_shape.price == int(bound.construction.derivation.price)
  # ★ item 11 여전히 SATISFIED (C8 회귀 관문·§6 V7)
  verification = sliced.gateway.verifications[0]
  item11 = next(v for v in verification.verdicts
                if v.item is SendVerifyItem.VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION)
  assert item11.outcome is VerifyOutcome.SATISFIED
  ```
  (`SliceRun` 데이터클래스에 신규 필드 **`venue_stage: VenueConstraintStage`** 1개 노출 — additive·
  MINOR-2로 이름 단일화[`step3`/venue_stage 병기 해소·§12].)

### 7.3.1 배치 주의 (category)

`test_slice_gaps.py`는 "the four seams slice #1 had to bridge"(4 GAP) 전용 모듈이다. #36은 그 4 GAP이
아니라 **#35 §12가 명시한 후속 접합점**이므로 신규 수렴 테스트는 `test_slice_end_to_end.py`(venue
admissibility는 e2e 관심사)에 배치하고, `test_slice_gaps.py`는 **무저촉**(C11·gap-3 GREEN 회귀만).

### 7.4 회귀 게이트(GREEN 유지 필수)

`test_slice_end_to_end.py:208-247`(C8)·`:250-261`(C9)·`test_slice_gaps.py:274-346`(gap-3·∅)·
`:283-288`(C11)·`:291`(V17)·`:296`(V18)·`test_egressgw_gateway.py:736-758`(C1)·
`test_egressgw_construction.py:199-326/553-704/743-785`·venue 커널 전체.

### 7.4.1 `__all__` 삽입 위치 (V9 WIDEN·What's Missing)

`admitted_shape_price_from_view`를 **알파벳 순서 유지**하며 `admitted_price_from_view` **직후**에 삽입:
(i) `construction.py __all__`(현 `:100-112`·`admitted_price_from_view`는 `:105`), (ii)
`egressgw/__init__.py`의 import 블록(`:81` 부근)과 `__all__`(construction 그룹·`admitted_price_from_view`
현 `:183`). 두 곳 lockstep. `_exact_admitted_int_value`는 **private → 미export**.

---

## 8. fail-closed·극성 규율 (시리즈 규율 적용)

- **양성 술어**: 투영 성공·`_shape_for` 값-소싱은 양성. `order_shape_admissible`은
  `ADMISSIBLE`만 양성(`predicates.py:301`)·그 외 `INADMISSIBLE`/`UNKNOWN`.
- **∅ 양방향**: 투영에서 `field_key` 미매칭·비정수 → `None` → shape.price None → `UNKNOWN`.
  `view.values == ()`(explicit-empty)도 → `None`. shape는 둘을 collapse(계보 필드 없음·venue fold는
  둘 다 `UNKNOWN`) — `admitted_price_from_view`가 관측용으로 둘을 구분하는 것과 대비(정직·§3.2).
- **음극성**: `silently_rounded`는 positive witness(`is not False → INADMISSIBLE`·`predicates.py:253`).
  #36은 이를 **무변경**(override 대상 아님)·투영 exact라 `False` 유지.
- **구조 파생 > 자기신고**: shape.price(값-표면 digest 소스)·수렴(스테이지 단일 보유 객체) 전부 파생.
  `_shape_for`·투영은 자체 판정 0.
- **UNKNOWN-restrictive**: value_view None(value-free tick) → 주입 shape 폴백(missing이지 "no price"
  아님); field_key 지정 + 비투영 → price None → `UNKNOWN`(no-send). 전부 보수.
- **value-free 폴백의 정직 명기(MINOR-7)**: 위 폴백이 반환하는 주입 shape(price=4,200)는 #36의 이동된
  provisional 제약(tick=1000·§3.4) 하에서 **자체가 INADMISSIBLE**이다(`(4,200−1,000) mod 1,000 ≠ 0`) —
  value-free tick이 step 3에 도달하면 조용히 통과하지 않고 admissibility에서 걸린다. 슬라이스 crossing tick은
  항상 view를 실어 이 경로가 happy-path에서 미실행이나, §9-4 뮤테이션(item-11 shape를 4,200으로 되돌림)의
  검출이 정확히 이 성질에 의존한다.

---

## 9. property/mutation test 타깃 (저작 증거·acceptance 아님)

닫는 EV 0이므로 저작 증거(RFC-010 §6). 타깃:

1. **투영 exactness** — `admitted_shape_price_from_view(v) == v.value`(정수). 투영을 round/truncate/
   offset하는 뮤테이션 → KILLED.
2. **bool/float fail-closed(#32 §2.5)** — `type() is int`를 `isinstance(x, int)`로 바꾸는 뮤테이션이
   `True`를 `1`로 admit → hypothesis M5 canary가 KILL. float admit 뮤테이션도 KILL.
3. **공유 코어 무-drift** — `_exact_admitted_int_value`를 두 투영이 공유. 한쪽 투영에 별도 int-체크를
   심는 뮤테이션 → `test_the_two_projections_admit_and_refuse_the_same_values` KILL.
4. **수렴(단일 소스)** — resolver가 `venue_shape()`를 재호출(별개 4,200 객체)하도록 되돌리는 뮤테이션
   → `bound.order_shape is venue_stage.resolved_shape` 실패 **且** provisional tick 하에 4,200이 off-grid
   (`(4200−1000) mod 1000 ≠ 0`)라 item 11 DENIED → e2e FAIL. **이중 실패로 수렴을 load-bearing 관측**.
5. **값-소싱 우선/폴백** — `_shape_for`가 view 존재 시 주입 shape를 반환하도록(우선순위 반전) 뮤테이션
   → `resolved_shape.price == 4200 ≠ crossing_close` KILL. field_key None인데 투영하는 뮤테이션 →
   value-free tick 폴백 canary KILL.
6. **fail-closed** — 비투영 시 4,200 폴백하도록 뮤테이션 → `resolved_shape.price is None` 기대 실패 KILL.
7. **provisional 제약이 V를 admit** — e2e item 11 SATISFIED. 제약을 원 (1000/9000/25)로 되돌리는
   뮤테이션 → `4,499,000 > 9000` INADMISSIBLE → KILLED.
8. **additive 회귀** — 비준 5설계 기존 테스트 전수 GREEN·GAP-3 suite GREEN·엔진 무변경 실증.

---

## 10. 명시 이연·미결 레지스터 (닫지 않음·접합 위치만)

1. **좌표(`authorized_coordinates`·item 17) 값-표면 재-소싱** — 스코프 제외(§0.5). route/credential
   사실·`exact_binding_holds` 가격 무대조. transport/route inventory(D-E4 `Transport`·#34 §5.1) +
   P0-2 route 사실 파생, 실 KIS transport 착지 시 `EgressCoordinateSet` 소싱 계약 소관. **접합점**:
   `records.py:618`·`_slice_fixtures.py:804-817`(무변경).
2. **제약 수치 실 승인값**(price_min/price_max/tick_size) — provisional. #36은 stand-in 충족 조건만 정의
   (§3.4). **register 목적지 판정 (오케스트레이터 신규 판정 2026-08-06 · MAJOR-N1 — 본 계약 §10-2의 이
   기록 자체가 정본이며 외부 커밋 아티팩트 인용이 아니다)**:
   - **(i) 1차 등재처 = register `§8-2 Candidate`**(`docs/plans/2026-07-29-tos-phase0-human-gate-register.md:225-228`),
     기존 `brokercap INSTANCE bound family(brokercap:1176-1181)` 군에 **병기**. + **KIS 초안 dimension 17**
     (`2026-07-29-tos-broker-capability-profile-kis-draft.md:88` `MARKET_INSTRUMENT_CONSTRAINTS`·status
     **UNKNOWN**)과 **§7 item 3/4 게이트**(`:273-274` — Broker Capability Profile INSTANCE bound family
     값·키 승인 / capability 값·conformance class 할당) **cross-ref**.
   - **(ii) ⚠ register §8-1은 아니다 (v1.1 정정)**: §8 전체가 **P0-1 Bounds-Approver 트랙의
     `VERIFICATION-PROFILE-002.yaml`** 키(§3 `:84`·G1 `:131`)이고, #36의 broker-specific band/tick는 그
     프로파일 키가 아니다. v1.1이 §8-1을 지목하며 인용한 `broker_capability_profiles: []`(P0-2 행 `:50`)는
     §8-1(VP)과 **다른 프로파일**이라 혼동이었다.
   - **(iii) venue #19 §8.1 정합 선언**: venue #19 §8.0(`2026-07-26-tos-venue-tradability-design.md:1001`)
     비준 판정 = "tick/lot/band는 policy content(§2.4 `VenueConstraintPolicy`) 주입이지 코드 상수 아님 —
     하드코딩 0"·§8.1 = **VERIFICATION-PROFILE 신규 키 0건**. ⇒ **#36은 VERIFICATION-PROFILE 신설 키를
     요구하지 않는다** — §8-1 행 추가는 이 비준 판정을 문서상 뒤집으므로 금지. #36 stand-in은 VP 키가 아니라
     brokercap INSTANCE bound family(§8-2 Candidate) 후보다.
   - **(iv) 행 추가 = #36 구현 커밋 범위**(비규범 register·구현 코드 리뷰에서 재검출 가능). provenance =
     "오케스트레이터 판정 2026-08-06, **본 계약 비준 기록이 정본**". 행 내용 = {키 = brokercap venue shape
     constraint bound(band/tick per scope) · 슬라이스 provisional stand-in · 소유 = P0-2 Broker Capability
     Profile INSTANCE · 아래 트리거}.
   - **(v) 교체 트리거 (v1.1 유지·인용 실측 정확 판정)**: 슬라이스 scope의 Broker Capability Profile
     INSTANCE가 **측정된 venue shape 제약으로 승인**되어 dimension 17이 UNKNOWN→VERIFIED로 승격되는 관측
     시(register PASS 규율·독립 리뷰어 서명·"bounds were measured"·register `:60/:97`), 슬라이스 fixture
     stand-in을 프로파일-유도 값으로 교체.
   - **(vi) 전방 입력 등재 (비평 open question)**: `VenueConstraintPolicy` policy-content 경로(venue #19
     §8.0)가 슬라이스 fixture 제약의 **진짜 상류**일 가능성 — P0-2(broker INSTANCE)가 아니라 **policy
     아티팩트 거버넌스**(spg·§27 q1) 소관일 수 있다. #36 provisional 라벨은 유지하되, **소관 재정밀화
     (P0-2 vs policy-content)를 후속 계약 입력물**로 남긴다.
3. **shape.quantity ⟺ derivation.quantity 수렴** — quantity는 사이징 산출(시장 값 아님)이며 값-표면
   재-소싱이 아닌 별개 seam(derivation 재-소싱). shape.quantity=20이 우연히 derivation.quantity=20과
   일치. **접합점**: `_slice_fixtures.py:731`(shape.quantity)·`construction.py:453`(derivation.quantity).
4. **다심볼/다-send per-attempt 보유 키잉** — `VenueConstraintStage.resolved_shape` 단일-보유는 GAP-3
   `OrderConstructionStage.construction` 단일-보유 모델 상속(순차 단일-attempt flow 안전). 동시/다심볼
   에서는 per-attempt 키잉 필요 — **#37(다심볼) 소관**. 발명 금지.
5. **deterministic-float 투영** — #32 §2.5 미비준. 분수/비정수 shape 가격은 fail-closed 유지(§4).
6. **값⟺digest 상류 완전 enforcement** — Context Integrity Service(#38·②). 투영은 생산-시점 검증 신뢰·
   재검증 안 함(over-claim 금지).

---

## 11. 리뷰어 공격 지점 (선제 반론 — #35 REVISE MAJOR 3 결함류 정면 처리)

1. **"배치 미지정(MAJOR-1 재발)."** — 반론: §3.1·§6 V10에 **심볼별 배치 명시** — `_exact_admitted_int_value`
   (`admitted_price_from_view` 직전)·`admitted_shape_price_from_view`·`VenueConstraintStage` 변경 전부
   **기존 `construction.py`**, export만 `egressgw/__init__.py __all__`(`:183`). **신규 .py 0** →
   submodule-drift canary(`test_egressgw_import_closure.py:541-550`) GREEN. 슬라이스 변경 파일·행은 §7.1.
2. **"canary 누락(MAJOR-1)."** — 반론: §6이 터치 표면 committed canary를 **직접 전수 재-grep**(V1-V22)
   하고 anti-phantom negative-grep 4건 병기. 서베이 C1-C11을 시작점으로 하되 완결로 삼지 않았다 — v1.1이
   **코드를 추가할 파일 자신의 소스-텍스트 canary 2건**(V17 `ContextValueView` 양성·V18 `marketfeed` 부재)을
   추가 발굴(MAJOR-1 처방·V18 토큰 금지는 §12 저작 제약).
3. **"factory 시그니처 은폐(MAJOR-2)."** — 반론: `send_boundary_context` 팩토리 **완전 무변경**(§5.2).
   유일 시그니처 변경은 `VenueConstraintStage.__init__`의 `shape_price_field_key` **1개 kw-only(default
   None)**이며 §3.3에 before/after 전문 제시. GAP-3 `price_field_key` 추가와 동형. 슬라이스 `bind_send_
   boundary_context`의 파라미터 2개 추가는 fixture-level(shipped 아님)이며 §7.1에 명시.
4. **"e2e GREEN 미증명(MAJOR-3)."** — 반론: §6 V7·V8·§7.3 canary가 **item 11 SATISFIED 유지**를 명시
   회귀 관문으로 지정. shape.price가 4,499,000이 되면 provisional 제약(§3.4)이 admit하도록 stand-in
   충족 조건을 정의; command 가격과의 정합(`shape.price == int(derivation.price)`)을 §7.3이 실증. C9
   (outbound 스칼라)는 shape 무관이라 GREEN. #35 §4.4의 4-경로 비정합은 **이 계약이 닫는 대상**.
5. **"이중 주입 붕괴 과잉 주장(MAJOR-3)."** — 반론(오케스트레이터 판정 (a) 채택): item-11 fold는 **6입력**
   이고 슬라이스는 그중 **5개**를 두 번 만든다(§2.2). #36이 수렴시키는 것은 **가격 대조 쌍(shape+constraints)
   한 축뿐**이며, snapshot/policy/decision은 **결정론 생성이라 런타임 값을 실지 않으므로 이중 주입을 정직
   잔존으로 등재**한다(§0.1·§2.2·§3.3) — 이들까지 수렴시키면 "venue_shape.price 값-표면 재-소싱" 밖의 scope
   creep. shape는 런타임 값(4,499,000)을 실어 **수렴 필수**, constraints는 그 shape가 대조되는 짝이라 동반
   수렴한다. **(b) 제약 수렴 드롭은 택하지 않는다**: §9-4 뮤테이션(item-11 shape 4,200 되돌림)의 double-
   failure 검출이 **이동된 제약(tick=1000) 하 4,200-off-grid**에 의존하므로, 제약을 이동/수렴하지 않으면 그
   canary가 약해진다(§8 value-free 폴백 정직 명기·§9-4).
6. **"좌표를 왜 안 닫나(스코프 누락)."** — 반론: 오케스트레이터 판정 ②(§0.5)·발명 금지 (b)(§0.3).
   좌표는 시장 값이 아니라 route/credential이며 `exact_binding_holds` 가격 무대조. **침묵 드롭 아님** —
   §0.5에 #35 §10-3 원문 인용 + transport/route-inventory 재프레이밍으로 이연 정제·§10-1 등재.
7. **"P2 추출이 ratified GAP-3 seam을 흔든다."** — 반론: `admitted_price_from_view` 추출은 **behavior-
   preserving**(4 반환 shape 불변·§3.2)이며 GAP-3 suite 전체(V2·`test_gap_3_*`·∅ both-ways·정수 투영·
   bool M5)를 게이트로 봉인. 대안 P1(standalone)의 drift class(§3.2)가 더 큰 위험. 구현 시 GAP-3 suite
   재실행 필수(§12).
8. **"엔진 변경 숨겼나."** — 반론: §5.1·§2.4 — 시퀀서가 **모든** step의 StageRequest에 value_view를
   채움(`sequencer.py:319/428`, docstring `:304-305`) 실측. #36 엔진 무변경(신규 필드 0·GAP-3의
   value_view 재사용만). GAP-4류 `held_position_magnitude` 스레딩 없음.

---

## 12. 미결·리스크 (구현 게이트)

- **REGREP 게이트(구현 착수 시 재-grep 필수·#32 v1.2 교훈)**: v1.1이 freshness 반증 3건을 교정했으나
  (MAJOR-4: submodule-drift `:541-550`·`_Request`(not `_StageRequest`) `:620-641`·allowlist `:71-86`),
  **전칭 freshness는 주장하지 않는다** — 구현 착수 시 **재-grep을 게이트로** 재확정: (i) `construction.py`
  `admitted_price_from_view` :149(**P2 후 helper가 그 직전 삽입 → :149 이후 라인 하향 이동·이관 문단
  :182-186[테스트 리터럴 :184-186]·==1 주석 :205-207·check :211 앵커 재계산**)·`_price_for` :896·
  `VenueConstraintStage.__init__` :947·`__call__` :967·
  `__all__` :100-112; (ii) `records.py` factory `order_shape` :610·`SendBoundaryContext.order_shape` :518;
  (iii) `_slice_fixtures.py` venue_shape :727·constraints :740·bind :893-952·construction_stages :955-1003
  (반환 어노테이션 :957)·resolver :1011-1057·run_slice :1091-1151; (iv) `sequencer.py:428`(value_view 모든
  step); (v) `VenueConstraintStage.__init__` 정확-잠금 canary 부재 재확인(V12); (vi) **v1.1 적발 표면**:
  `test_egressgw_construction.py:743-744`+`:750-752`(V3 앵커)·`test_slice_gaps.py:291`(V17)·`:296`(V18)·
  `test_egressgw_import_closure.py:541`(V10)·`:71`(V11 allowlist).
- **배치 규율(구현 게이트)**: 신규 심볼 전부 기존 `construction.py`. **신규 .py 생성 시** submodule-drift
  canary(`test_egressgw_import_closure.py:541-550`) loud FAIL — 배치 규율 이탈 금지.
- **V3 앵커 재조준(MAJOR-2·완료 기준·MINOR-1 역할 분리)**: 테스트가 **리터럴 인용하는 앵커**(재조준 대상)
  = `construction.py:211`(test `:750`·exact-int check)·`:184-186`(test `:751`·bool 문장); **이관 문단** =
  `:182-186`(그 안 bool 문장이 :184-186). 이 두 리터럴 앵커는 P2가 검사·문단을 `_exact_admitted_int_value`로
  이동하므로 **같은 커밋에서** helper 새 라인으로 재조준(anchor-drift 테스트 부재로 loud FAIL 없음·§3.2·
  §6 V3). bool≠1 계약 문단의 보존처 = **공유 코어 docstring**(§3.2 확정).
- **`marketfeed` 토큰 저작 제약(V18·MAJOR-1)**: `construction.py` 신규 코드·docstring·주석에 토큰
  `marketfeed` **금지**(`test_slice_gaps.py:296` 부재 canary). D-E2/#32 §2.5/값-표면으로 지칭.
- **provisional 제약 stand-in**: §3.4 충족 조건(`price_min ≤ V ≤ price_max` ∧ `(V−price_min) mod tick
  = 0`)을 만족하도록 선택. 실값 임의 확정 금지(§0.3 (a))·미결 등재(§10-2)·fixture 주석 의무.
- **`SliceRun`/`run_slice` `venue_stage` 노출(MINOR-2·이름 단일화)**: §7.3 수렴 canary가
  `sliced.venue_stage.resolved_shape`/`.shape_constraints` 접근을 요구 → `SliceRun`에 신규 필드
  **`venue_stage: VenueConstraintStage`** 1개 additive 추가(`step3` 병기 폐기).
- **value_view 도달 확인**: §2.4 실측(sequencer 모든 step)이나, `VenueConstraintStage.__call__`의 실제
  `request.value_view` populated 여부를 구현 시 e2e로 재확인(step-3 request가 step-2와 동일 채움인지).
- **shape/제약 수렴 분리 가능성**: 리뷰어가 제약 수렴을 scope creep으로 판정하면 §3.3 D3의 제약-접근자
  (`shape_constraints`)만 드롭하고 shape 수렴만 유지(§11-5).

---

## 13. 명명·번호

- **문서 번호 #36** — deferral ① venue_shape.price 값-표면 재-소싱. 비준 5설계 #31~#35에 대한 아크
  (서베이 §E 권고 1편·오케스트레이터 판정 ①). #37=③ 다심볼·#38=②(a) CIS 주입 포트는 별개 계약.
- **신규 심볼**(구현 확정 대상): `tos.egressgw.admitted_shape_price_from_view`(public 투영)·
  `_exact_admitted_int_value`(private 공유 코어)·`VenueConstraintStage.shape_price_field_key`(init
  kw-only)·`VenueConstraintStage.resolved_shape`(보유 속성)·`VenueConstraintStage.shape_constraints`
  (read 접근자)·`VenueConstraintStage._shape_for`(메서드). 명명 negative-grep 충돌 0(§6 anti-phantom).
- **신규 패키지 0·신규 .py 0·엔진 변경 0**.

---

## 14. 개정 로그

- **v1.2 (2026-08-06)**: 델타 재검증 REVISE(신규 MAJOR-N1·MINOR 3) 반영 — §10-2 register 목적지 정정으로
  비준 승급(M1-M4·MINOR 7·WM 4는 전건 해소 실측 확인). finding별:

  | finding | 처분 | 변경 위치 |
  |---|---|---|
  | **MAJOR-N1** (register 목적지 오지정 — §8-1=VERIFICATION-PROFILE·P0-1 트랙 혼동) | 채택 | §10-2 전면 교체: 1차 등재처 **§8-2 Candidate**(brokercap INSTANCE bound family `brokercap:1176-1181`) + KIS draft dim 17(`:88`)·§7 item 3/4(`:273-274`) cross-ref · venue #19 §8.0/§8.1 정합 선언(VP 신규 키 0) · 전방 입력(policy-content 소관) 등재 · provenance=본 계약 §10-2 정본. §3.4/§7.1-1/§12 fixture 주석·cross-ref 정합화 |
  | **MINOR-1** (앵커 이중개념 혼용) | 채택 | 헤더·§3.2·§6 V3·§12에서 테스트 리터럴 앵커(`:211`/`:184-186`) vs 이관 문단(`:182-186`) 역할 분리 |
  | **MINOR-2** (§9-4 `step3` 이름 잔재) | 채택 | §9-4 `venue_stage.resolved_shape` |
  | **MINOR-3** (전수 census 전칭) | 채택 | §6 V19-V22 추가(`test_egressgw_package.py:62-88`/`:90-101`·서베이 C6 `:41-51`/C7 `:54-59`·전부 GREEN) |

  ⚠ v1.1 §14의 **MAJOR-5 처분("register §8-1")은 v1.2 MAJOR-N1으로 정정**(§8-1=VERIFICATION-PROFILE 혼동
  → §8-2 Candidate). 아래 v1.1 기록은 이력 보존을 위해 원문 유지.

- **v1.1 (2026-08-06)**: 독립 비평 REVISE(MAJOR 5·MINOR 7·What's Missing 4) 전건 반영. finding별:

  | finding | 처분 | 변경 위치 |
  |---|---|---|
  | **MAJOR-1** (소스-텍스트 canary 2건 census 누락) | 채택 | §6 V17(`test_slice_gaps.py:291` ContextValueView 양성)·V18(`:296` marketfeed 부재) 행 추가 + §12 `marketfeed` 토큰 저작 제약 |
  | **MAJOR-2** (P2 추출이 하드코딩 앵커 무효화) | 채택 | §6 V3 GREEN→**REGREP**(앵커 재조준 의무)·§3.2 bool≠1 문단·==1 주석을 공유 코어로 이관·placement 확정·§12 완료 기준 |
  | **MAJOR-3** ("이중 주입 붕괴" 과잉 주장) | 채택 (a) | §0.1·§2.2(6입력/5중복 표)·§3.3 "가격 대조 경로 한 축 수렴"으로 축소·snapshot/policy/decision 정직 잔존 등재·§11-5 (b)드롭 기각 근거(§9-4 의존) |
  | **MAJOR-4** (freshness 전칭 주장 반증 3건) | 채택 | submodule-drift `:531-540`→`:541-550`·`_StageRequest`→`_Request`(`:620-641`)·allowlist `:62-76`→`:71-86` 교정(§6·§11-1·§12) + 헤더·§12 freshness 하향 |
  | **MAJOR-5** (provisional register 아티팩트 미명명) | 채택 (interpretation B) | §10-2 = register §8-1(신설 누락 키)·행 추가 구현 커밋 범위·교체 트리거 정의 |
  | **MINOR-1** (`st.floats` inf/nan) | 채택 | §7.2 `allow_nan=False, allow_infinity=False`(`canonical/_base.py:87` 핀) |
  | **MINOR-2** (`<step3>` 플레이스홀더) | 채택 | §7.3·§12 `SliceRun.venue_stage` 단일 필드명 확정 |
  | **MINOR-3** (P2 스니펫 위임 명시) | 채택 | §3.2 "docstring/어노테이션 보존·본문만 위임" + ==1 주석 공유 코어 이관 |
  | **MINOR-4** ((a)-(e) 전사 정정) | 채택 | §0.3 "전사 + (c) 인용 정밀화" + 정밀화 note |
  | **MINOR-5** (`construction_stages` 반환 어노테이션) | 채택 | §7.1 4-튜플 어노테이션(`:957`)·호출부 `:1112` 명시 |
  | **MINOR-6** (V13 인용 축소) | 채택 | §6 V13 `:692-707`→`:692-704` |
  | **MINOR-7** (value-free 폴백 INADMISSIBLE) | 채택 | §3.3 `_shape_for` docstring + §8 정직 명기(§9-4 의존 병기) |
  | **WM** (resolver None 정책·egressgw fixture 미이동·REGREP 표면·`__all__` 위치) | 채택 | §3.3 resolver None 정책·§3.4 두 provisional 세트 공존·§12 REGREP (vi)·§7.4.1 `__all__` 정렬 |

- **v1.0-draft (2026-08-05)**: 최초 저작. 서베이 이연 ① + 오케스트레이터 판정 3건 입력. GAP-3 `_price_for`
  동형 additive 설계(값-표면 우선·주입 폴백)·정수 exact 투영(공유 코어 P2)·스테이지 단일-보유 수렴·좌표
  스코프 제외 정제·제약 provisional. 1차 심사·독립 비평 대기.

<!-- 저작 증거·닫는 EV 0. 비준 전 파이프라인: 1차 심사 → 독립 비평 → 개정 → 운영자 위임 자동 비준
(ADR-002 Part-2/3 연장) → 구현 → 적대적 코드 리뷰. acceptance·live authorization과 무관. -->
