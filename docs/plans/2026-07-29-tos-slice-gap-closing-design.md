# 설계 문서 #35 — 수직 슬라이스 #1 갭-closing 계약 (cross-lane addendum, provisional·닫는 EV 0건) (2026-07-29, v1.1)

> **⚖ 비준 기록**: **2026-07-29 운영자 위임 자동 비준(v1.1)** — 오케스트레이터가 게이트 조건을 검증하고
> 기록함: 독립 비평 REVISE(CRITICAL 0·MAJOR 3 — 역방향 canary 사냥이 egressgw submodule canary 누락을
> 적발[#32 결함 클래스 재발의 리뷰-단계 차단]·GAP-3 dsl-edge와 GAP-4 RCL 경계 논증은 "흠결 0" 판정) →
> v1.1(644행) 전건 처방 반영: MAJOR-1 배치 확정(신규 심볼 전부 기존 submodule — 어댑터→backtest/fills.py·
> factory→egressgw/records.py·투영→egressgw/construction.py·신규 .py 0·canary 표 18→21행) · MAJOR-2
> factory 생산 시그니처(4 flow 산출+6 주입 묶음·verify-item 소스 표) · MAJOR-3 §4.4 4-경로 grep 증거
> 사슬+내부 비정합 정직 이연 · MINOR-2 FLAT presence-가드 우회 계약화 · **NIT-1은 저작자 grep 반론 승**
> (pipeline.py:323 정확 — 오케스트레이터 원문 판정 확정: value_view는 :312 주석·:323 kwarg뿐). 오케스트레이터
> 재실측(C19~C21·배치·증거 사슬 원문 대조) 통과. 품질 파이프라인 잔여(구현 → 적대적 코드 리뷰) 유지.
> ADR acceptance·live authorization과 무관. 효력: 갭-closing 구현 착수(backtest·egressgw·engine additive·
> 슬라이스 갭 테스트 6건 closure 전환).

> **v1.1 개정(2026-07-29)**: 독립 비평 REVISE(CRITICAL 0·MAJOR 3·MINOR 3·NIT 2; GAP-3 dsl-edge·
> GAP-4 RCL 경계 "흠결 0"·공격 8종 불발) 전건 처방. **MAJOR-1** 신규 심볼 배치를 기존 submodule로
> 확정(어댑터→backtest/fills.py·factory→egressgw/records.py·투영→egressgw/construction.py) +
> egressgw submodule canary 행 추가(C3를 WIDEN→**GREEN**으로 강등). **MAJOR-2** factory 생산
> 시그니처 명세(파생 vs 주입 분리·verify-item→그룹→소스 표·§3.1) + lazy resolver 부분-적용 패턴.
> **MAJOR-3** GAP-3 e2e GREEN을 grep 증거 사슬(4 verify 경로)로 결속 + shape/coordinates 값-표면
> 비정합 정직 명기·§12 이연. MINOR/NIT: FLIP 5→6 정정·FLAT 분기 presence-가드 우회 계약화·package
> canary 2행 추가·GAP-1 handoffs 의미 명세. **NIT-1은 재grep으로 기각**(pipeline value_view는
> :323·§14). 개정 처분 전수는 §14.
>
> **비준 대상 배너.** 본 문서는 저작(authoring) 산출물이다. 파이프라인: 저작 → 1차 심사 →
> 독립 비평 → 개정 → **운영자 위임 자동 비준(2026-07-29 연장 지시)** → 구현 → 적대적 코드
> 리뷰. 본 산출은 **provisional**이며 **닫는 EV/AC 0건**(§1.1). acceptance는 비준 4설계
> (#31~#34)의 후속 게이트와 동일 소관이다.
>
> **성격: cross-lane addendum.** 본 계약은 신규 패키지를 만들지 않는다. 슬라이스 #1
> end-to-end 통합(`afe44101`·`tos/tests/slice/` 31 tests GREEN)이 발굴한 **레인 교차 seam 4건**
> (GAP-1~4)을 닫는, 비준된 4개 설계에 대한 통합 addendum이다. 각 갭은 어느 한 레인의 **내부
> 결함이 아니다** — 각 레인은 내부적으로 정합하며 각자 seam을 **정직한 forward seam으로 명시
> 이연**했다. 없는 것은 **접합부(joint)**다(`test_slice_gaps.py:12-13`).

---

## 0. 전제·규율

### 0.1 갭 레지스터 (실행 가능한 관측·prose 아님)

슬라이스 #1은 갭을 산문이 아니라 **실행 가능한 관측**으로 봉인했다(`tos/tests/slice/test_slice_gaps.py`,
285행·6 tests). 각 테스트는 (a) 출하 코드에 대해 갭을 실증하고 (b) 그 접합부를 소유해야 할
레인을 지목한다. **한 레인이 갭을 닫으면 대응 테스트가 시끄럽게 실패한다 — 그것이 의도된 실패
모드다**(`test_slice_gaps.py:8-10`). 이 addendum의 §7은 각 갭 테스트가 closure 후 어떤 단언으로
대체되는지의 전환 계약을 명세한다.

임시 우회의 실물은 `tos/tests/slice/_slice_fixtures.py`의 `SendBoundarySlot`(:1012-1113)이다.
이 단일 객체가 **두 역할을 겸한다**: (i) D-E1의 `Transmit` 포트(`__call__` — 게이트에 위임 전
context 바인딩; GAP-2의 우회) 와 (ii) D-E3 드라이버가 배수(drain)하는 fill-model 표면
(`bind_settlement_context`/`settle_due`/`records`/`unsettled_records`/`handoffs` — 게이트의 보유
결과를 재주입; GAP-1의 우회). 이 겸직이 **어느 출하 패키지도 소유하지 않은** 배선의 정확한 실물이다
(`_slice_fixtures.py:1015-1017`).

### 0.2 addendum의 범위·비범위

- **범위**: 4개 seam의 **출하 배선**(shipped wiring)을 만들어 슬라이스가 `SendBoundarySlot`
  로컬 브리지 없이 돌게 하고, 각 갭 테스트를 대체 단언으로 전환한다.
- **비범위(명시 이연·§10)**: 실 RCL release/round-trip·reduce-only capacity 의미론·완전
  Evidence Store·값⟺digest 상류 완전 enforcement(Context Integrity Service)·numeric 차등 오라클·
  실 KIS transport. 전부 비준 4설계가 이미 명시 이연한 것이며 본 addendum이 재확인한다.
- **커널 잠식 금지**: `tos.egress`(ADR-002-013 QCC 커널)·`tos.engine` 코어의 권위 표면을
  잠식하지 않는다. GAP-4의 held-position 관측조차 **read-only**이며 mutation/release가 아니다(§5).

### 0.3 firewall·closure 준수 + 한 건의 §0.3 개정 (egressgw→dsl 직접 edge)

네 레인의 firewall·closure는 모두 유지된다. **단 하나의 형식적 개정**이 필요하다:

- **egressgw §0.3 직접-import allowlist에 `tos.dsl` 추가**(GAP-3). 근거: `AdmittedPriceObservation`
  이 D-E2 `ContextValueView`(`tos.dsl`)에서 가격을 파생하려면 egressgw 소스가 `ContextValueView`
  를 이름으로 참조해야 한다. **이는 신규 런타임-closure 멤버가 아니다** — `tos.dsl`은 이미
  egressgw의 런타임 closure에 있다(egressgw→`tos.engine`→`tos.dsl`; `test_egressgw_import_closure.py:
  352-365`의 `bound = declared ∪ closure(tos.engine)`가 `tos.dsl`을 이미 포함). 개정은 **직접
  naming 허가의 확대**일 뿐이다(전이 의존을 직접 선언 edge로 승격). 상세 canary 영향은 §6-C9.
- **backtest는 egressgw를 import하지 않는다**(GAP-1 상호 closure 배제 유지·§2.4). 게이트 결과
  재주입 어댑터는 게이트를 **구조적으로**(`.results` 속성) 소비하고 `tos.egressgw`를 절대
  import하지 않는다 — D-E1이 gateway를 통해 `SendTransport`를 구조 소비하는 것과 동형.
- 네 패키지 전부 network/RNG/wall-clock/dynamic-escape 부재 canary는 무저촉이다(신규 코드도 동일
  규율 준수).

### 0.5 anti-phantom 규율 (FD #27 §0.5·시리즈 상속 — 부재·존재 주장 양방향 grep)

- 본 문서의 **모든 file:line 인용은 2026-07-29 자체 grep/read 실측값**이다. 부재 주장도 존재
  주장과 동일하게 grep으로 증명한다(존재 grep·부재 negative-grep).
- **부재 주장 negative-grep 병기**: (1) `grep -rn "import" tos/src/tos/backtest/*.py | grep -iE
  "egressgw|brokeradapter"` → 0 (backtest는 D-E4를 import 안 함). (2) 동 `tos/src/tos/egressgw/*.py
  | grep -iE "backtest"` → 0 (상호 배제). (3) `grep -rn "ContextValueView"
  tos/src/tos/egressgw/` → 0 (GAP-3 미착지 — 닫으면 존재로 전환). (4) `ProvisionalReservationLedger`
  에 `release`/`free`/`clear`/`reset` → 0 (`state.py:22` — GAP-4 무저촉 유지).
- **committed canary 전수-grep(#32 v1.2 교훈·필수 이행)**: 비준 전제 "committed 테스트 파괴 0"은
  터치 표면의 **모든** committed canary(시그니처·closure·drift anchor)를 전수 grep해야 성립한다.
  #32 v1.1은 engine closure만 실측하고 dsl 시그니처 canary를 놓쳐 v1.2 에라타를 유발했다. §6이 그
  전수 목록과 호환 판정을 표로 제시한다.

---

## 1. 갭 → 설계 이연 뿌리 지도 (§별 인용·실측)

각 갭은 비준 설계의 **명시된 forward seam**에 뿌리를 둔다. 갭은 그 seam들이 **교차하는 지점**에
접합부가 없다는 사실이다.

| 갭 | 소유 레인 | 뿌리(설계 §·명시 이연) | 실측 코드 증거 |
|---|---|---|---|
| **GAP-1** 게이트→드라이버 결과 재주입 seam 부재 | D-E3 `tos.backtest`(+D-E4 shape 소비) | #33 §7.4 (c) "실 `Transmit`(D-E4 paper sender — 동일 seam·다른 주입)"·#33 §5.3 "동기 반환·EGRESS_RESULT 재주입"·#34 §5.2 "fill 대역은 D-E3와 Transport Protocol 공유" | 드라이버는 `DeterministicFillModel.settle_due`(driver.py:233)로 배수·게이트는 `.results`에 **보유만**(gateway.py:1574)·양쪽을 잇는 것 부재 |
| **GAP-2** send-boundary context가 step-12 이전 부재 attempt_id로 키잉 | D-E4 `tos.egressgw` | #34 §4.1 "verify list 입력 표면·attempt_id 키잉"·#31 §4.3 "attempt-id는 step 12 content-addressed"·#33 §3.4 "reference 좌표=드라이버 yield-order·bar_index 탈결합" | 게이트는 `contexts.get(attempt.attempt_id)`(gateway.py:1420)·attempt_id는 (proof digest, permit, 좌표 digest)로 step 12 파생·사전 populate 불가 |
| **GAP-3** Order Construction 가격이 주입값·값 표면 미소비 | D-E4 `tos.egressgw`(D-E2 shape 소비) | #34 §3.1 (iii) "admitted Critical Input 가격=D-E2 값 표면·값은 P0-1/D-E2 이연"·#31 §3.2 D1 "시장값은 admitted Critical Input·capsule 소스로만"·#32 §2.2 `ContextValueView`(착지) | `derive_order_size`는 주입 `AdmittedPriceObservation`(3필드) 소비(construction.py:145,209-223)·`ContextValueView`→price 경로 부재(§0.5-3) |
| **GAP-4** Explicit-Flat의 Order Construction 경로 부재 | D-E4 `tos.egressgw`(+배후 RCL release 부재) | #34 §3.1 "risk_budget/per_unit_risk·held position 미참조"·#31 §4.4/§9-2 "release 경로 부재·round-trip 실 RCL 이연"·#33 §11-3/§2.2 | `derive_order_size`는 `risk_budget/per_unit_risk`만(construction.py:273)·`FLAT_QUANTITY_BASIS`(proposal.py:49) 소비 경로 없음·`ProvisionalReservationLedger` release 부재(state.py:22) |

**교차 진단**: GAP-1은 D-E3↔D-E4 재주입 접합, GAP-2는 D-E4가 D-E1 step-12 산출을 소비하는 접합,
GAP-3은 D-E4가 D-E2 값 표면을 소비하는 접합, GAP-4는 D-E4 사이징이 D-E1 projection을 관측하는
접합이다. 네 갭 전부 **D-E4를 한쪽 끝으로** 갖는다 — D-E4가 시리즈 최후 착지 레인이기 때문이다.

---

## 2. GAP-1 계약 — `EgressResultSource` (드라이버 재주입 포트)

### 2.1 판정: D-E3측 구조 포트 + 게이트 결과 어댑터 (Transport 이중-선언 선례 적용)

**드라이버가 fill_model에서 소비하는 전 표면(실측 5멤버)**:

| # | 표면 | 드라이버 사용처 | 의미 |
|---|---|---|---|
| 1 | `bind_settlement_context(bar) -> None` | driver.py:225 (tick yield 前) | 정산 컨텍스트 바인딩(fill-model 개념·게이트는 no-op) |
| 2 | `settle_due(bar) -> Iterable[<has .payload: EgressResultPayload>]` | driver.py:233 | 정산 도래분 배수(재주입 원천) |
| 3 | `records -> tuple[...]` | driver.py:309 | D-E3-로컬 fill 레코드 |
| 4 | `unsettled_records() -> tuple[...]` | driver.py:310 | 미정산 fill 레코드 |
| 5 | `handoffs -> tuple[...]` | driver.py:311 (`handoff_count=len(...)`) | hand-off 수 (**NIT-2: 드라이버는 `len`만 소비** — Protocol은 sized iterable[`__len__`]만 요구·요소 타입 무관) |

**계약**:
1. **`tos.backtest`에 `EgressResultSource` Protocol 선언** — 위 5멤버가 정확한 소비 표면.
   `DeterministicFillModel`이 이를 직접 충족(기존 참조 satisfier). `BacktestDriver.__init__`의
   `fill_model` 파라미터를 `DeterministicFillModel` 고정 타이핑에서 `EgressResultSource`로 **재타이핑**
   (파라미터명 `fill_model` 유지·타입만 상위-Protocol로 확대).
2. **게이트 결과 어댑터를 기존 submodule `tos/backtest/fills.py`에 출하**(MAJOR-1 배치 확정) —
   `SendBoundarySlot`의 결과-절반을 홈으로 이관한 얇은 D-E3 어댑터(예: `GatewayResultReinjector`) +
   `EgressResultSource` Protocol + 로컬 `RetainedEgressResults` Protocol을 **전부 fills.py에 배치**
   (`DeterministicFillModel`과 동거 — fills.py가 "재주입 원천"을 소유·driver.py는 fills에서
   `EgressResultSource` import·기존 driver.py:61 `from tos.backtest.fills import ...` 확장). **신규
   .py 파일 0** → backtest submodule-drift canary(`test_backtest_import_closure.py:562-576`) GREEN
   유지·C3 재판정(§6). 동기 게이트의 `.results`를 `settle_due` 같은-bar 배수·`bind_settlement_context`
   no-op·`records`/`unsettled_records` 空·`handoffs`로 제시. **게이트를 구조적으로 소비**(로컬
   `RetainedEgressResults` Protocol — `.results` 프로퍼티만 요구·`tos.egressgw` 미import). fills.py
   vars()는 `EngineCore`·금지 mutation 심볼 미명명(backtest closure :579-604/:607 GREEN).
3. **drift canary(Transport 선례 적용)** — 슬라이스 seam 테스트(양쪽 import 가능)에서 로컬
   `RetainedEgressResults`가 게이트의 실 `.results` 표면과 시그니처 일치함을 단언. 이는 D-E4가
   `SendTransport`(egressgw)/`Transport`(brokeradapter)를 **이중 선언·구조 충족·drift canary로 봉인**
   하는 `test_seam_engine_brokeradapter.py:380-389`와 **동형**이다.

### 2.2 검토·기각한 대안

- **(A) 게이트가 `EgressResultSource`를 직접 충족(게이트에 `settle_due(bar)` 추가)** — 기각.
  `settle_due(bar: Bar)`의 `Bar`는 `tos.backtest` 타입이다. 게이트가 이를 참조하면 egressgw가
  backtest를 import해야 해 **상호 closure 배제 위반**(`test_egressgw_import_closure.py:88`
  `tos.backtest` in `_FORBIDDEN_SIBLINGS`). 게이트에 backtest의 bar/정산 어휘를 끌어들이는
  over-realization. **주의: `test_slice_gaps.py:73-75`는 "게이트가 이 메서드를 노출하면 GAP-1
  closed"를 하나의 신호로 두지만**, 그 경로는 firewall을 깬다 — 본 계약은 다른 두 신호(드라이버
  annotation·`__all__` 토큰)로 갭을 닫으며 그 `not hasattr` 단언은 **여전히 GREEN으로 유지**된다
  (방어적 잉여로 남고, 게이트-메서드 경로도 커버).
- **(B) `EgressResultSource`를 좁은 drain-only(`drain_results()`)로 재설계·드라이버 루프 개조** —
  기각(비확대). 드라이버의 interleaving generator는 #33 §4.1의 하중 콘텐츠이며 fill-model NEXT_BAR
  정산에 `bind_settlement_context`/`settle_due(bar)`가 본질적이다. 루프 개조는 비준된 #33 §4.1을
  건드리는 비-additive 변경. 5멤버 표면 유지가 additive.
- **(C) 게이트 어댑터를 egressgw에 두기** — 기각. 어댑터가 `settle_due(bar)`를 제시하려면 `Bar`가
  필요→backtest import→상호 배제 위반. 어댑터는 D-E3에 산다.

### 2.3 하위호환

`EgressResultSource`는 `DeterministicFillModel`의 **구조적 상위 타입**이다(5멤버 전부 보유). 재타이핑은
안전한 확대: `fill_model=DeterministicFillModel(...)`을 넘기는 기존 backtest 테스트는 전부 GREEN 유지.
mypy 구조 타이핑으로 satisfier 판정. 상세 canary 영향은 §6-C1~C4.

---

## 3. GAP-2 계약 — lazy context resolver (`Mapping | Callable` 유니온)

### 3.1 판정: 유니온 확대(Mapping 경로 하위호환 유지) + 출하 factory

**뿌리**: attempt_id는 step 12에서 (proof digest, permit identity, reference-coordinate digest)로
**content-addressed**(sequencer.py:220-230)되고, reference 좌표는 드라이버의 전역 yield-order
카운터로 `bar_index`와 **탈결합**(driver.py:130-143·#33 §3.4)이다. 그래서 호출자는 런 이전에
`contexts`를 populate할 수 없다 — 드라이버의 yield 순서를 예측해야 하기 때문. 슬라이스는 `Transmit`
호출 내부에서 attempt로부터 context를 바인딩해 우회한다(`_slice_fixtures.py:1062-1073`).

**계약**:
1. **게이트 `contexts` 파라미터를 유니온으로 확대**:
   `Mapping[str, SendBoundaryContext] | Callable[[AttemptRequest], SendBoundaryContext | None]`.
   게이트 `__call__`은 callable이면 `resolver(attempt)`로, 아니면 `contexts.get(attempt_id)`로 해소.
   **`None` 반환은 기존 `CONTEXT_MISSING` halt와 동일**(gateway.py:1421-1430·fail-closed·RFC-002
   §10.8:761) — "missing context stays the same recorded stop it is today"(`test_slice_gaps.py:128`).
2. **출하 factory(생산 시그니처 명세·MAJOR-2)** — 기존 submodule `tos/egressgw/records.py`에 배치
   (`SendBoundaryContext`와 동거·records.py가 이미 전 sub-record 타입 import·신규 .py 0 →
   egressgw submodule canary GREEN·§6). 슬라이스 `send_boundary_context`(`_slice_fixtures.py:884-947`,
   4파라미터 + 모듈 fixture ~25 하드코딩)의 **hand-wave "홈 이관"을 정직 시그니처로 대체**한다.

   **핵심 관찰(MAJOR-2 해소)**: 25 필드가 전부 주입되는 게 아니다 — **약 10 필드는 flow 산출물에서
   파생**되고, 나머지 주입 사실은 **이미 존재하는 합성 sub-record 단위로 그룹핑**된다. 생산 시그니처 =
   `send_boundary_context(*, attempt, construction, conformance_proof, reference, <주입 묶음들>)`.
   nonce/environment 등은 하드코딩 불가이므로 전부 주입 묶음으로 들어온다.

   | verify item(s) | SendBoundaryContext 필드 | 소스 |
   |---|---|---|
   | item 2 (Realize) | reservation_attempt_id·reservation_conformance_proof_digest·reservation_action_flow_permit_identity | **파생**(attempt·`_slice_fixtures.py:914-916`) |
   | item 13 (Realize) | construction·conformance_proof·approval_intent_binding_digest | **파생**(flow 스테이지·:929-932) |
   | item 17 (Realize) | egress_request·quorum_commit_certificate | **파생**(construction.command.canonical_digest·:939-940) |
   | step 18 | outbound_quantity·outbound_price | **파생**(construction.derivation·:943-944) |
   | item 1 | transmission_capability·capability_nonce·action_flow_permit_nonce·principal·request_digest·prior_claims | **주입** capability/permit 묶음 |
   | items 2·11 | venue_snapshot·venue_policy·venue_decision·observed_session_phase·action_class·order_shape·venue_shape_constraints | **주입** venue 묶음 |
   | item 16 | egress_currentness_proof·egress_currentness_result·restrictive_latch_state·worst_credible_capacity | **주입** currentness 묶음 |
   | item 17 | authorized_coordinates·capsule_egress_request_digest | **주입** coordinates 묶음 |
   | §4.2/§4.7 | transport_nature·environment 토큰(3)·environment_inherited·credential_route_inventory | **주입** transport/env 묶음 |
   | items 3·6·12·14·15 | commitment_epoch_current·broker_*·approval_*·action_flow_* provisional 플래그 | **주입** provisional stand-in 묶음 |
   | step 18 | outbound_side·reference | **주입**(side는 command SIDE 축과 대조·§4.4) |

   **판정**: factory는 25 flat 파라미터가 아니라 **4 flow 산출물 + 6 주입 묶음**을 받는다. 묶음은
   기존 합성 record 타입(`TransportNature`·`TransmissionCapability`·`VenueConstraintSnapshot`·
   `EgressCurrentnessProof`·`EgressCoordinateSet` 등)을 그대로 단위로 쓴다 — 신규 bundle 타입 발명은
   **선택적·구현 이연**(계약 불요). scalar 토큰(nonce·environment·principal)은 진짜 scalar이므로
   개별 주입. `tos.egressgw.__all__`에 factory 노출(phantom-resolve canary GREEN·§6).
3. **lazy resolver 부분-적용 패턴(§3.1)**: resolver = factory를 **주입 묶음들에 부분-적용**한 closure
   `(attempt) -> SendBoundaryContext`. construction/proof는 flow 스테이지에서 호출 시점 조회(step-2/
   step-11 스테이지의 `.construction`/`.proof` 프로퍼티)·attempt는 게이트가 전달. 즉 resolver는
   "주입 묶음은 런 전 고정·flow 산출물은 attempt에서 파생"을 합성한다. 슬라이스 `SendBoundarySlot.
   __call__`(`_slice_fixtures.py:1056-1073`)의 context 조립 로직이 이 resolver로 홈 이관된다.

### 3.2 하위호환 판정 (committed 실측)

**Mapping 경로 반드시 유지**(REPLACE 아님·유니온). 근거(실측): committed egressgw 테스트가 dict를
게이트에 넘기는 사이트 **28건** — 직접 `contexts={...}` **7건**(`test_egressgw_gateway.py:152,315,
335,472,478,520,537`; 315는 `contexts={}` 空-dict → CONTEXT_MISSING 경로) + `build_gateway(...)`
호출 **21건**(각각 내부에서 `contexts={attempt.attempt_id: context}`·`_egressgw_fixtures.py:551`).
REPLACE는 이 전부를 파괴한다. 유니온은 **additive**: 기존 dict 사이트 전부 GREEN 유지. `test_slice_gaps.py:131`
의 `"Mapping" in annotation`은 유니온이 Mapping을 포함하므로 **TRUE 유지**, `"Callable" not in
annotation`(:132)은 **FLIP**(의도된 loud 실패). 상세 §6-C5·C6.

### 3.3 리스크

- **resolver 부작용 금지**: resolver는 순수 조회여야 한다(부작용·capacity mutation 0). factory는
  이미 순수(context 조립만). 구현 시 canary: resolver 호출이 ledger/sink를 변경하지 않음.
- **동일 attempt 반복 조회**: 게이트는 attempt당 1회 `__call__`(sequencer.py 재주입 구조)이므로
  resolver도 attempt당 1회 호출. idempotent해야 함(같은 attempt→같은 context).

---

## 4. GAP-3 계약 — 값 표면 소싱 가격 (`ContextValueView` → `AdmittedPriceObservation`)

### 4.1 실측된 결함: 결정 수치 ≠ 사이징 수치

슬라이스의 밴드-reversion 정책은 `close < lower_band → LONG/OPEN`을 **두 capsule-소스 값 operand**
로 결정한다(`_slice_fixtures.py:489-500`·field_key `"close"`). 교차 bar(index 1)의 close =
**4,499,000**(정수 minor 단위·`_slice_fixtures.py:185,193`; `LOWER_BAND=4,500,000`). 그러나 사이징이
소비하는 `AdmittedPriceObservation.value` = **4,200**(주입 상수 `PRICE`·`_slice_fixtures.py:176,656`).
**전략이 결정한 수치(4,499,000)와 주문이 사이징된 수치(4,200)는 다른 두 수치**이며, 유일한 끈은
호출자가 공급한 `snapshot_digest` 문자열뿐이다(construction.py:220·`test_slice_gaps.py:170`).

`AdmittedPriceObservation`(records.py:154-173)은 `source`가 capsule 소스여야 함을 요구해(construction.py
:214-219) **config-재라벨 가격은 구조 차단**하지만, 값을 **획득**할 수는 없다 — `ContextValueView`
에서 이 레코드로의 출하 경로가 없다.

**착지 사실**: 값 표면은 이미 흐른다. `DecisionTickPayload.value_view: ContextValueView | None`
(engine/records.py:187·#32 §3.2 (3))이 tick에 실려 있고, 파이프라인이 이미 `resolved_context=
payload.value_view`로 소비한다(pipeline.py:323). GAP-3은 **동일 값 표면을 사이징이 소비하지 않는다**
는 접합 부재다.

### 4.2 계약: 투영 함수 + step-2 스레딩 + 계보 필드

1. **투영 함수(egressgw 소유·D-E2 shape 소비·기존 submodule `construction.py` 배치·MAJOR-1)**:
   `admitted_price_from_view(view: ContextValueView, *, field_key: str) -> AdmittedPriceObservation`.
   `derive_order_size`와 동거(construction.py가 이미 `AdmittedPriceObservation` import·:46)·신규 .py
   0 → egressgw submodule canary GREEN(§6).
   - `view.values`에서 `field_key` 일치 `ContextValue`를 찾음. **부재 시 fail-closed**(∅ 규율·
     construction.py:209-213 미러 — "unknown price is a no-send").
   - 산출: `source = CAPSULE_CONTEXT_SOURCE`, `value = cv.value`, `snapshot_digest =
     view.snapshot_canonical_digest`, **`value_payload_digest = cv.payload_digest`(신규 필드)**.
   - **view digest 대조**: `view.canonical_digest`/`snapshot_canonical_digest`가 concrete임을 확인
     (ContextValueView가 발행 시 이미 강제·context_value.py:172-200). 값⟺digest 검증은 **생산 시점**
     (D-E2 marketfeed)이 소유하고 소비측은 재검증 안 함 — #32 §2.3 trust seam 상속(over-claim 금지).
2. **`AdmittedPriceObservation`에 `value_payload_digest: str | None = None` 추가** — 값의 per-value
   provenance(`ContextValue.payload_digest`·context_value.py:120)를 실어, 끈이 **호출자 약속이 아니라
   digest**가 되게 함. 직접 주입(provisional) 경로는 `None` 유지(하위호환).
3. **step-2 스레딩(engine·additive)**: `StageRequest`에 `value_view: ContextValueView | None = None`
   추가(engine/records.py:371-387). `run_commitment_flow`에 `value_view` 파라미터 추가(sequencer.py
   :278)·코어가 `payload.value_view`를 전달(core.py:383)·시퀀서가 `StageRequest.value_view` 채움
   (sequencer.py:417). `OrderConstructionStage`가 `request.value_view` 존재 시 `field_key`로 투영해
   주입 가격을 **override**(부재 시 주입 provisional 가격으로 fallback).
4. **field_key는 주입 config**(사이징 정책이 가격 field_key 지정·하드코딩 0). `OrderConstructionStage`
   `__init__`에 `price_field_key: str | None` 추가(additive).

### 4.3 검토·기각한 대안

- **투영을 engine/marketfeed에 두기** — 기각. `AdmittedPriceObservation`은 egressgw 타입이다. engine
  /marketfeed가 이를 생산하려면 egressgw를 import해야 함(engine은 egressgw 미import·계층 역전).
  gap 테스트가 GAP-3 owner를 "D-E4 tos.egressgw, consuming a D-E2 shape"로 명시(`test_slice_gaps.py:158`).
- **value_view를 `DecisionTickPayload` 대신 `StageRequest`로 새로 싣기** — 채택. `DecisionTickPayload`
  는 `test_engine_value_view.py:150`가 `model_fields` **정확 집합 잠금**이라 변경 시 canary 파괴.
  `StageRequest`는 정확-집합 잠금 canary 부재(실측·§6-C11) → additive 안전.
- **`snapshot_digest` 재사용(신규 필드 없이)** — 기각. snapshot digest는 coarse(스냅샷 단위)이고
  per-value 계보(`ContextValue.payload_digest`)를 잃는다. 신규 필드가 "값⟺digest" 계보 보존
  (gap 테스트 제안 shape·`test_slice_gaps.py:172-174`).

### 4.4 하위호환 + 리스크

- **egressgw→dsl §0.3 개정**(§0.3·§6-C9) — GAP-3의 가장 무거운 canary 영향. 신규 런타임-closure
  멤버 아님(dsl ∈ closure(engine))·직접 naming 허가 확대. 설계 §0.3 텍스트 개정 + allowlist 테스트
  동시 갱신 필수.
- **가격 4,499,000로 사이징**: `derive_order_size`의 파생 수량은 `risk_budget/per_unit_risk=20`으로
  **가격 무관**(construction.py:273). 가격은 `notional = quantity * price.value` 검사에만 영향
  (construction.py:307)이고 슬라이스 `max_notional=None`(검사 skip). ⇒ 수량 20 불변, `derivation.price`
  만 4,499,000로 전환.

- **⚠ e2e 25 GREEN 증거 사슬(MAJOR-3·grep 실증)**: 투영 후 `derivation.price=4,499,000`인데
  `venue_shape().price=4,200`(`_slice_fixtures.py:719-721`)·`authorized_coordinates()` endpoint
  (`:795-810`)는 **고정 fixture 잔존** — 같은 주문에 두 가격. e2e GREEN이 유지되는 이유는 **어떤
  verify 경로도 command 가격을 venue_shape 가격에 대조하지 않기 때문**이며, 이를 4 경로 전수 실증한다:
  1. **item 11 (venue admissibility)**: `order_shape_admissible`은 `context.order_shape`(shape.price
     4,200)를 venue 제약(price_min=1000/price_max=9000·`:737-738`)에 대조 — 4,200∈범위 통과. **command
     가격 4,499,000는 이 경로에서 미검사**. venue는 shape fixture로 admit, command 가격 독립.
  2. **item 13 (construction)**: construction이 CONFORMANT(command 존재·DERIVED)임만 검증·가격을
     shape에 재대조 안 함.
  3. **item 17 (coordinates)**: `exact_binding_holds`(gateway.py:1169-1174)는 egress 좌표(route
     endpoint)·QCC command digest·capsule terminus·ioc verdict를 대조 — **가격 직접 대조 0**.
     `authorized_coordinates` endpoint는 route이지 가격 아님·command digest는 가격 반영(양쪽 재계산).
  4. **outbound_binding_mismatch (gateway.py:1302-1337)**: outbound_quantity/price를 `derivation.
     quantity/price`에만 대조(:1303-1306)·outbound_side를 command SIDE 축에(:1318)·egress_request의
     command digest를 compiled command digest에(:1331-1337). 슬라이스가 `outbound_price=construction.
     derivation.price`(:944)로 설정하므로 양쪽 4,499,000 동시 전환. **GREEN**.
- **⚠ 슬라이스 내부 비정합 정직 명기(MAJOR-3·숨기지 않기)**: 위 증거는 "무해"를 증명하나, 슬라이스는
  **venue가 4,200-가격 shape를 admit하는데 command는 4,499,000**인 내부 비정합을 갖는다. GAP-3은
  **사이징/command 가격**만 값-표면 재-소싱하고 **venue_shape.price·authorized_coordinates는 재-소싱
  하지 않는다**. 이 비정합은 어떤 verify 경로에도 걸리지 않으나(위 4 경로), **정직상 §10-3에 shape/
  coordinates 값-표면 재-소싱을 명시 이연 항목으로 등재**한다(단위 일관성과 함께)·§12 리스크에도 병기.
  `test_slice_end_to_
  end.py:257`(`request.price == context.outbound_price`)은 양쪽 동시 전환이라 GREEN. GAP-3은 값을
  계보와 함께 흘릴 뿐, shape/coordinate 가격 정합이나 단위 정합(minor-unit 4,499,000 vs 4,200·#32
  §2.5)을 주장하지 않는다.
- **AdmittedPriceObservation 필드 추가**: `extra="forbid"` frozen 모델에 default-`None` 필드 추가는
  additive(기존 생성자 무영향·gap 테스트의 `model_fields==[3]`만 의도 FLIP).

---

## 5. GAP-4 계약 — Explicit-Flat 사이징(보유 포지션 구조 파생) + RCL 경계 엄수

### 5.1 실측된 결함: 두 관측

dsl Explicit Flat은 `quantity_basis == FLAT_QUANTITY_BASIS`("ZERO_POSITION"·proposal.py:49)를
**구조적으로** 반드시 갖는다(FLAT은 반드시 사용·ACTION은 금지·proposal.py:159-175). `derive_order_size`
는 `risk_budget/per_unit_risk`로 크기를 렌더하고 **보유 포지션을 읽지 않아**(construction.py:273):

- 기본 admitted set(`frozenset({"RISK"})`·`_slice_fixtures.py:609})에서 flat은 **step 2에서 denied**
  (basis가 admitted set 밖·construction.py:204-208) — 슬라이스가 관측하는 바.
- ZERO_POSITION을 set에 넣어도 도움 안 됨: 파생 크기가 **entry 크기와 동일**(risk_budget/per_unit_risk
  는 basis 무관) — exit basis를 걸친 entry-크기 주문(`test_slice_gaps.py:220-221`).

즉 밴드-reversion 전략의 exit 절반이 **DSL에서 표현 가능하나 send 경계에서 구성 불가**다.

### 5.2 계약: 구조 파생 사이징 경로(보유 magnitude 소싱)

1. **engine projection 신규 read 접근자(read-only·mutation/release 아님)**:
   `ProvisionalReservationLedger.outstanding_consumed_magnitude(key) -> Decimal | None`. outstanding
   reservation의 이미-기록된 `filled_quantity`(state.py:330-332·records.py:424)를 반환. **접근자명은
   `release`/`free`/`clear`/`reset` 4종을 피함**(`test_slice_gaps.py:281`·GAP-4 companion 무저촉).
2. **step-2 스레딩(engine·additive)**: `StageRequest`에 `held_position_magnitude: CanonicalDecimal |
   None = None` 추가(GAP-3의 value_view와 동일 additive slot). 시퀀서가 접근자로 채움(sequencer.py
   :417·항상 관측 제공·파생은 basis별 소비).
3. **`derive_order_size`에 FLAT 분기 추가 + presence-가드 재구조화(MINOR-2)**: keyword-only
   `held_position: CanonicalDecimal | None = None` 추가(additive·기존 keyword-only 시그니처
   construction.py:141-147). **핵심 재구조화(MINOR-2·오케스트레이터 재정 채택)**: 현재 risk_budget/
   per_unit_risk presence 가드(construction.py:224-230)는 **무조건** 실행되어, 순수-close 정책(risk
   예산 미보유)에서 flat에 **latent deny**를 유발한다("값 미독"과 "존재 불요"의 혼동). 이를 해소:
   - **basis별 raw 산출 분기(삽입점 construction.py:273)**: risk_budget/per_unit_risk presence 가드
     (:224-230)를 **비-FLAT basis 조건 안으로 이동**. `raw` 산출을 분기 — FLAT → `raw = held_position`,
     비-FLAT → `raw = risk_budget / per_unit_risk`(현 :273). FLAT은 risk_budget/per_unit_risk를
     **읽지도 요구하지도 않는다**(순수-close 정책이 risk 예산 없이도 사이징 통과).
   - `held_position` 부재(FLAT) → **DENY**(fail-closed·"no held position to close"). `held_position=0`
     (명시 zero — 닫을 것 없음) → **DENY**(사유 구분·∅ 양방향·§8).
   - 존재 → magnitude = `held_position`(구조 파생·**`risk_budget`/`per_unit_risk` 미참조**). 이후
     lot/min/max/venue/notional 유계 검사는 **전 basis 공통 유지**(construction.py:276-312 — raw가
     held든 risk-derived든 동일 봉인 통과). 가격 checks(:209-223)도 flat 공통(flat도 price 기록·
     notional 검사에 필요).
   - `FLAT_QUANTITY_BASIS`는 `tos.dsl`에서 import(GAP-3의 dsl edge 공유·단일 진리원·중복 상수 금지).
   - **§7-5(d)·§9-5 canary 보강**: risk_budget/per_unit_risk를 flat 경로에서 요구하도록 되돌리는
     뮤테이션(presence-가드 우회 무효화)도 KILLED 되게 — flat이 risk 예산 없이 사이징 통과함을 canary가
     양성 실증.
4. **슬라이스 config**: 슬라이스 sizing_bound의 `admitted_quantity_bases`에 `FLAT_QUANTITY_BASIS`
   추가(envelope config 변경). 그러면 flat이 step 2에서 **사이징 통과**하고 step 8에서 capacity deny.

### 5.3 경계 엄수 — RCL release 발명 금지 (§5의 핵심 논증)

GAP-4의 **닫는 범위 = "사이징 경로 존재 + 구조 파생"**. capacity admission은 **명시 이연**. 논증:

- **held-position 관측은 RFC-002 §9.1:557-558 무저촉.** 접근자는 이미-기록된 `filled_quantity`를
  **읽을** 뿐이다 — headroom 생성 0(§9.1:558 "producer-local counters SHALL NOT create headroom"),
  mutation 0, release 0. 읽기는 serialization도 mutation도 아니므로 §9.1:557(RCL 유일 writer)
  무저촉. egressgw는 ledger를 직접 만지지 않는다 — `StageRequest.held_position_magnitude`(engine이
  채운 값)만 소비. projection 소유권은 engine에 남는다.
- **flat은 여전히 capacity-stage에서 deny된다(정직 기록).** step 2(CANDIDATE_COMMAND_CONSTRUCTION·
  vocabulary.py:168)가 step 8(LEDGER_VERIFICATION·:175)보다 **먼저** 실행되므로(실측), flat이 step 2
  에서 사이징 통과해도 step 8에서 at-most-one으로 deny된다: outstanding reservation(entry 체결로
  POSITION_CONSUMED·미해소)이 `admits_new_exposure`를 False로 만듦(sequencer.py:382-401). **halt가
  step 2(사이징 규칙)에서 step 8(capacity seal)로 이동** — 정확히 "the reason it stops is now the
  capacity seal, not the sizing rule, and the two should not be conflated"(`test_slice_gaps.py:225-227`).
- **reduce-only capacity 의미론은 이연.** flat/reduce-only가 at-most-one을 통과하도록 하는 것(포지션
  축소는 노출 추가 아님)은 **실 RCL/protective 소관 명시 이연**이다. GAP-4는 flat을 사이징만 하고
  capacity를 통과시키지 않는다. reduce-only는 실 RCL이 착지할 때.
- **release 무발명.** round-trip(flat 체결 → scope 해방)은 실 RCL release 경로를 기다린다(RFC-002
  §9.1:557·#31 §9-2). projection의 no-release 성질(state.py:22-30) 보존. companion test(`test_slice_gaps.py
  :272-285`) GREEN 유지.
- **held magnitude의 정직한 범위**: 접근자가 반환하는 것은 outstanding reservation의 **capacity-소비
  magnitude**(filled_quantity)다. 단일-entry 슬라이스에서 이는 보유 포지션과 같다. **완전 net-position
  ledger(multi-leg·평단)는 이연** — engine은 의도적으로 position ledger가 아니다(#33 B4 "코어는
  capacity/commitment 머신이지 포지션 원장 아님"). GAP-4는 단일-entry 범위에서 held=filled_quantity를
  사이징 원천으로 쓰고, multi-leg 일반화를 명시 이연한다.

### 5.4 하위호환

`derive_order_size`는 keyword-only 시그니처(construction.py:141)이므로 `held_position` 추가는
additive(default None). FLAT 분기는 non-FLAT basis 경로 무영향(RISK entry 사이징 불변). 접근자 추가는
projection의 기존 표면 무영향. StageRequest 필드는 additive. 상세 §6-C10~C12.

---

## 6. committed canary 전수 목록 + 호환 판정 (필수 이행·#32 v1.2 교훈)

터치 표면의 committed 시그니처/closure/drift canary를 전수 열거한다. **판정 범례**: FLIP=갭 closure로
의도된 loud 실패(전환 계약 §7)·GREEN=무영향·WIDEN=additive 확대(canary 갱신 필요)·REGREP=구현 시점
정확-잠금 재실측 필수.

| # | 터치 표면(file:line) | committed canary(file:line) | 변경 | 판정 |
|---|---|---|---|---|
| **C1** | backtest/driver.py:161 `fill_model: DeterministicFillModel` | `test_slice_gaps.py:66-68` (`"DeterministicFillModel" in annotation`) | `EgressResultSource`로 재타이핑 | **FLIP** (§7-1); 기존 backtest 테스트는 satisfier 넘김→GREEN |
| **C2** | backtest/`__init__.py` `__all__` | `test_slice_gaps.py:83-87` (`resultsource`/`egressresultsource` 토큰 부재) | `EgressResultSource`(+어댑터) 추가 | **FLIP** (§7-1) |
| **C3** | backtest 어댑터 배치 = 기존 submodule `fills.py`(MAJOR-1 확정) | `test_backtest_import_closure.py:201-228,562-576` (`_BACKTEST_SUBMODULES`/on-disk drift) | 기존 파일에 심볼 추가·신규 .py **0** | **GREEN** — submodule 집합 불변(어댑터·`EgressResultSource`·`RetainedEgressResults`가 fills.py 동거) |
| **C4** | backtest 신규 모듈 namespace | `test_backtest_import_closure.py:579-604` (엔진/sibling mutation 심볼 부재)·:607-626 (`EngineCore`는 driver.py에서만) | 어댑터가 `EngineCore`·금지 심볼 미명명 | **GREEN** (구성상; 어댑터는 `.results` 구조 소비만) |
| **C5** | egressgw/gateway.py:1363 `contexts: Mapping[...]` | `test_slice_gaps.py:130-132` (`"Callable" not in annotation`); dict 사이트 28건(직접 7·build_gateway 21) | `Mapping | Callable` 유니온 | **FLIP**(Callable 단언); Mapping 단언 GREEN(유니온 포함)·dict 28사이트 GREEN |
| **C6** | egressgw/`__init__.py` `__all__` | `test_slice_gaps.py:136-141` (`send_boundary_context` factory 부재) | `send_boundary_context` factory 노출 | **FLIP** (§7-2) |
| **C7** | egressgw/records.py:154-173 `AdmittedPriceObservation`(3필드) | `test_slice_gaps.py:176-180` (`model_fields == ["source","value","snapshot_digest"]`) | `value_payload_digest` 추가 | **FLIP** (§7-3) |
| **C8** | egressgw construction/records/gateway 소스 | `test_slice_gaps.py:182-193` (anti-phantom: `ContextValueView`·`value_view` 부재) | `ContextValueView` 참조 | **FLIP** (§7-3) |
| **C9** | egressgw §0.3 direct-import allowlist | `test_egressgw_import_closure.py:62-76` (`_ALLOWED_TOS_PACKAGES`)·:306-320 (source 밖-allowlist import 금지)·:323-349 (every declared edge taken) | `tos.dsl` 추가 | **WIDEN** — 설계 §0.3 텍스트 + allowlist 동시 갱신; 신규 런타임 멤버 아님(dsl ∈ closure(engine)·:352-365 bound 무변); edge 실제 taken 확인 |
| **C10** | egressgw/construction.py:141 `derive_order_size` 시그니처 | 정확-잠금 canary **부재**(실측; construction 테스트 :407 등은 타 타입 iterate) | keyword-only `held_position` 추가 | **GREEN**/REGREP — additive(default None); 구현 시 시그니처 잠금 재grep |
| **C11** | engine/records.py:371 `StageRequest` 필드 | 정확-집합 잠금 canary **부재**(실측; `test_engine_value_view.py:150`은 `DecisionTickPayload` 잠금, StageRequest 아님) | `value_view`·`held_position_magnitude` 추가 | **GREEN**/REGREP — additive; StageRequest 필드-수 canary 재grep |
| **C12** | engine/state.py:111 `ProvisionalReservationLedger` | `test_slice_gaps.py:281-282` (`release`/`free`/`clear`/`reset` 부재)·`test_backtest_import_closure.py:588` (backtest ns에 `ProvisionalReservationLedger` 부재) | read 접근자 추가(4금지명 회피) | **GREEN** — companion test 유지; 접근자는 engine 클래스에·backtest ns 무영향 |
| **C13** | engine/sequencer.py:278 `run_commitment_flow` 시그니처 | seam 테스트가 kwargs로 호출(`test_seam_engine_brokeradapter.py:239-249)·정확 시그니처 잠금 부재(실측) | `value_view` 파라미터 추가 | **GREEN**/REGREP — additive(default None); 구현 시 재grep |
| **C14** | engine/core.py:383 (value_view 전달) | 내부 배선·표면 canary 없음 | `payload.value_view` 스레딩 | **GREEN** |
| **C15** | engine/pipeline.py:323 | 이미 `resolved_context=payload.value_view` 소비 | 무변경 | **GREEN** (변경 불요) |
| **C16** | Transport drift canary | `test_seam_engine_brokeradapter.py:380-389` (`SendTransport`/`Transport` 시그니처 동일) | **무저촉** — GAP-1은 병렬 `EgressResultSource` pair 신설·`SendTransport` 미변경 | **GREEN** + GAP-1이 신규 pair용 drift canary **추가** |
| **C17** | dsl/proposal.py:49 `FLAT_QUANTITY_BASIS` | dsl 시그니처 canary(#32 v1.2 교훈) | **참조만·무변경** | **GREEN** (불변 확인) |
| **C18** | slice/_slice_fixtures.py `SendBoundarySlot`·admitted_price | 슬라이스 자체(테스트 파일) | 브리지 해체·출하 배선으로 대체 | 슬라이스 재배선(§7)·31 tests 중 6 gap FLIP·나머지 GREEN 유지 목표 |
| **C19** | egressgw factory·투영 배치(records.py·construction.py) | `test_egressgw_import_closure.py:531-540` (`test_every_submodule_is_covered_by_the_closure_child`·`_SUBMODULES`:189·`_LOADED_SUBMODULES`:198·child:233-238) | 기존 submodule에 심볼 추가·신규 .py **0** | **GREEN** (MAJOR-1) — egressgw submodule 집합 불변; backtest C3의 정확한 쌍둥이 canary |
| **C20** | egressgw `__all__`(+`send_boundary_context`·`admitted_price_from_view`) | `test_egressgw_package.py:35` (`test_every_exported_name_resolves`·phantom __all__) | __all__ 추가 | **GREEN** — 추가 이름 전부 실 export(hasattr 통과) |
| **C21** | engine `__all__`(GAP-3/4는 필드·메서드·파라미터 추가·신규 export 0) | `test_engine_package.py:75` (`test_the_export_list_has_no_duplicates`) | 무변경(dedup 대상 0) | **GREEN** — 접근자=메서드·필드=모델 속성·파라미터=시그니처(전부 non-__all__) |

**요약**: FLIP **6**(C1·C2·C5·C6·C7·C8 — 의도된 gap-테스트 실패·MINOR-1 정정) · WIDEN **1**
(C9 dsl edge만) · GREEN/REGREP 나머지. **비-additive canary 파괴 0** — 모든 변경은 additive이거나
의도된 gap-테스트 FLIP이다. **MAJOR-1 배치 확정으로 두 submodule-drift canary(backtest C3·egressgw
C19)는 GREEN**(신규 .py 0). WIDEN 1건(C9)만 security-relevant canary의 신중한 확대이며 설계 #34
§0.3 텍스트·테스트 lockstep 갱신을 요한다. backtest 패키지는 전용 phantom canary 부재(실측 —
`test_backtest_package.py` 없음)이나 추가 __all__ 이름은 실 export(구현 확인·REGREP).

---

## 7. 슬라이스 갭 테스트 전환 계약 (6 tests → 대체 단언)

각 갭 관측 테스트가 closure 후 무엇으로 대체되는지 명세. 이 전환은 구현의 **완료 판정**이다.

1. **`test_gap_1_no_shipped_seam_re_injects...`(50-88)** → 대체:
   (a) `BacktestDriver.__init__`의 `fill_model` annotation이 `EgressResultSource`를 명명;
   (b) `EgressResultSource`가 `tos.backtest.__all__`에 존재·`DeterministicFillModel`과 게이트-어댑터
   **둘 다 `isinstance(..., EgressResultSource)`**; (c) anti-phantom 유지(driver.py 소스에 "egressgw"
   부재·게이트 소스에 "backtest" 부재 — 어댑터 구조 소비).
2. **`test_gap_1_the_local_adapter_adds_no_judgement...`(90-103)** → 대체: **출하** 어댑터
   (`GatewayResultReinjector`)가 게이트 `.results`를 **불변 전달**·자체 판정 0·D-E3-로컬 fill 레코드
   미보유(`records == ()`·`unsettled_records() == ()`). 슬라이스 판정은 전부 출하 패키지 소유.
3. **`test_gap_2_no_shipped_builder...`(111-149)** → 대체:
   (a) 게이트 `contexts` annotation에 `Callable` 포함; (b) `send_boundary_context` factory가
   `egressgw.__all__`에 존재; (c) lazy resolver가 **live attempt로부터** context 바인딩
   (`bound.reservation_attempt_id == attempt.attempt_id`); (d) resolver `None` → `CONTEXT_MISSING`
   halt 보존(음성 경로 정직).
4. **`test_gap_3_the_construction_price_is_injected...`(157-202)** → 대체:
   (a) `AdmittedPriceObservation`에 `value_payload_digest` 존재; (b) `ContextValueView`가
   egressgw construction에서 참조됨; (c) **핵심**: `outbound_price == Decimal(crossing_close)`
   (4,499,000) **이고** `value_payload_digest == <교차 bar의 close ContextValue.payload_digest>`
   — 즉 **결정 수치 == 사이징 수치 + 계보 digest 일치**. "the number the strategy decided on and the
   number the order was sized against are [now] the same number, tied by a digest"(현 :170 반전).
5. **`test_gap_4_the_explicit_flat_basis...`(210-269)** → 대체:
   (a) FLAT + `held_position=None` → **DENIED**(`denial_reason`에 "held position"); (b) FLAT +
   `held_position=H` → **DERIVED**·`quantity == H`; (c) **`flat_size.quantity != entry_size.quantity`**
   (구조 파생·risk-budget 무관); (d) canary: `risk_budget`/`per_unit_risk` 뮤테이션이 flat 크기를
   바꾸지 않음(사이징 SOURCE가 held position임을 증명); (e) **presence-가드 우회 실증(MINOR-2)**:
   FLAT + `risk_budget=None`/`per_unit_risk=None` **이면서** `held_position=H` → **여전히 DERIVED**·
   `quantity == H`(순수-close 정책이 risk 예산 없이 사이징 통과). flat 경로가 risk_budget/per_unit_risk를
   다시 요구하게 하는 뮤테이션(presence-가드 우회 무효화) → KILLED.
6. **`test_gap_4_the_scope_stays_occupied...`(272-285)** → **GREEN 유지**(변경 없음): ledger는 여전히
   `release`/`free`/`clear`/`reset` 부재·`RELEASED` projection 밖·outstanding 유지·`admits_new_exposure
   is False`. read 접근자는 이 중 어느 것도 아니다. **companion test가 GREEN 유지됨이 GAP-4 경계
   (RCL 무접촉)의 실행 가능한 증거다.**

**슬라이스 재배선**: closure 후 `SendBoundarySlot`(브리지)은 대부분 해체된다 — 게이트(lazy resolver
동반)가 `Transmit`, 출하 `GatewayResultReinjector`가 `EgressResultSource`/fill_model, resolver는
construction/proof 스테이지 closure. `run_slice`(:1146-1201)가 출하 심볼로 배선. e2e·conformant 25
tests는 배선 변경에도 **동일 관측(GREEN) 유지** 목표(가격 값 전환은 §4.4대로 동시-전환이라 무해).

---

## 8. fail-closed·극성 규율 (시리즈 규율의 addendum 적용)

- **양성 identity(positive)**: `EgressResultSource` satisfier 판정·resolver context 해소·held
  position 관측 전부 양성 술어. `SendHandoff.accepted_for_transmission`은 **positive polarity**
  (`is True`만·records.py:402·gateway.py:1355-1357) — 무변경.
- **음극성 `is False`만**(시리즈 교훈·`is not True` 금지): 신규 코드에 음극성 bool|None 도입 시
  `is False`만. GAP-4 held-position은 bool 아님(magnitude)·해당 없음.
- **∅ 양방향**: 값 표면 투영에서 `field_key` 미매칭 → fail-closed(missing)·`view.values == ()`
  (explicit-empty·context_value.py:157-158) → 별개 처리. held_position `None`(부재) vs `0`
  (명시 zero — flat이 닫을 것 없음)은 별개: 둘 다 DENY이나 사유 구분(정직 기록).
- **구조 파생 > 자기신고**: 가격(값 표면 digest)·flat 크기(held magnitude 구조)·attempt-id
  (content-addressed) 전부 파생. resolver·투영·접근자는 자체 판정 0.
- **UNKNOWN-restrictive**: value_view `None`(value-free tick) → 주입 provisional 가격 fallback
  (missing이지 "no price" 아님)·held None → flat DENY(사이징 stop). 전부 보수.

---

## 9. property test 타깃 (저작 증거·acceptance 아님)

닫는 EV 0이므로 저작 증거다(RFC-010 §6:183-185). 타깃:

1. **GAP-1 재주입 무판정**: 출하 어댑터가 게이트 `.results`를 불변 전달·자체 fill 레코드 0. 어댑터가
   결과를 변조/추가하는 뮤테이션 → KILLED. `DeterministicFillModel`·어댑터 **둘 다 satisfier** isinstance.
2. **GAP-1 drift canary**: 로컬 `RetainedEgressResults` ≡ 게이트 `.results` 표면(Transport 선례
   `test_seam_engine_brokeradapter.py:380` 동형). 표면 drift 뮤테이션 → 실패.
3. **GAP-2 lazy 해소**: resolver가 live attempt로 context 바인딩·`None` → CONTEXT_MISSING halt.
   Mapping 경로 30+ 사이트 GREEN 회귀(하위호환 실증). resolver 부작용(ledger/sink mutation) 뮤테이션
   → 검출.
4. **GAP-3 값⟺digest 계보**: 투영 산출 `value == view의 field_key ContextValue.value` **및**
   `value_payload_digest == 그 ContextValue.payload_digest`. field_key 미매칭 → DENY. digest를 상수로
   대체하는 뮤테이션 → KILLED(계보 위조 검출). 결정 수치 == 사이징 수치(4,499,000) 실증.
5. **GAP-4 구조 파생 + presence-가드 우회(MINOR-2)**: flat 크기 == held magnitude·risk_budget/
   per_unit_risk 무관(그 필드 뮤테이션이 flat 크기 불변) → risk-budget 소싱 뮤테이션 KILLED. held
   None/0 → DENY(사유 구분). **risk_budget=None인 순수-close 정책도 held_position 있으면 DERIVED**
   (presence-가드가 flat을 latent-deny하지 않음) → flat 경로에 risk-예산 요구를 되살리는 뮤테이션 KILLED.
6. **GAP-4 RCL 경계**: ledger release/free/clear/reset 부재 유지·flat이 capacity-stage deny(step 8)·
   halt가 step 2→step 8 이동. 접근자가 mutation을 유발하는 뮤테이션 → 검출.
7. **closure canary**: egressgw 소스가 `tos.dsl`만 신규 참조(그 외 밖-allowlist import 0)·backtest
   소스가 egressgw/brokeradapter 미참조(상호 배제)·신규 코드 network/RNG/wall-clock 0.
8. **additive 회귀**: 비준 4설계의 기존 테스트 전수 GREEN(파괴 0)·슬라이스 e2e/conformant 25 GREEN·
   gap 6 FLIP(§7).

---

## 10. not-slice-1 / 명시 이연 (닫지 않음·접합 위치만 표기)

1. **실 RCL release·round-trip·reduce-only capacity 의미론** — RFC-002 §9.1:557·#31 §9-2. flat이
   capacity를 통과해 scope를 해방하는 것은 실 RCL/protective 소관.
2. **완전 net-position ledger(multi-leg·평단)** — engine은 position ledger 아님(#33 B4). GAP-4는
   단일-entry held=filled_quantity 범위.
3. **값 표면 단위 일관성(minor-unit vs 실가격)·deterministic-float 투영·venue_shape.price 및
   authorized_coordinates의 값-표면 재-소싱(MAJOR-3)** — GAP-3은 사이징/command 가격만 값-표면 재-소싱
   하고, venue admissibility의 shape 가격(`venue_shape().price=4,200`)과 egress 좌표는 fixture 잔존
   한다(어떤 verify 경로에도 무저촉 — §4.4 4-경로 grep 실증). 전부 D-E2 marketfeed 값-표면 소관
   (#32 §2.5)·명시 이연.
4. **값⟺digest 상류 완전 enforcement** — Context Integrity Service(#32 §0.2-4·§2.3 trust seam).
   투영은 생산-시점 검증을 신뢰·재검증 안 함(over-claim 금지).
5. **완전 Evidence Store 런타임**(ADR-002-016)·**실 SEND_STARTED durable** — #34 §4.6·provisional sink.
6. **실 KIS transport·비동기 I/O** — #34 §5.1(tos/ 밖 경계 뒤).
7. **numeric 차등 오라클** — #33 §6.2(D-E2 값 표면 gated).
8. **정식 EV-L2 PASS** — P0-1 bounds·P0-3 독립 리뷰어·독립 서명(#33 §11-1·#34 §1.1). 본 산출 provisional.

---

## 11. 리뷰어 공격 지점 (선제 반론)

1. **"egressgw→dsl edge는 §0.3 위반 아닌가."** — 반론: 신규 **런타임** closure 멤버가 아니다.
   `tos.dsl`은 이미 egressgw 런타임 closure에 있다(egressgw→engine→dsl·`test_egressgw_import_closure.py
   :352-365` bound 무변). 개정은 직접 naming 허가의 신중한 확대이며, gap 테스트 anti-phantom FLIP
   (`ContextValueView not in getsource` 반전)이 이 edge를 **의도된 것으로 지목**한다. 설계 §0.3
   텍스트·allowlist lockstep 갱신으로 phantom-edge 0.
2. **"GAP-4가 engine을 position ledger로 over-realize한다."** — 반론: 접근자는 이미-기록된
   `filled_quantity`를 **읽을** 뿐(mutation/release 0·headroom 0·§9.1:558 무저촉). engine은 position
   ledger가 아니며(§5.3·#33 B4), multi-leg net-position은 명시 이연. 단일-entry held=filled_quantity는
   정직한 관측이다.
3. **"flat이 사이징돼도 capacity deny면 GAP-4가 무의미."** — 반론: 정확히 그 **halt 이동**(step 2
   사이징 규칙 → step 8 capacity seal)이 가치다. "두 이유를 conflate하지 말라"(`test_slice_gaps.py
   :225-227`)가 요구한 정직. reduce-only 통과는 실 RCL 이연(명시 분리·§10-1).
4. **"게이트가 `EgressResultSource`를 직접 충족하게 하면 어댑터 불요."** — 반론: `settle_due(bar)`의
   `Bar`가 backtest 타입이라 egressgw→backtest import→상호 배제 위반(§2.2 (A)). 어댑터는 firewall이
   강제하는 구조다(Transport 선례 동형).
5. **"Mapping을 Callable로 교체가 깔끔하지 유니온은 지저분."** — 반론: committed 30+ dict 사이트를
   파괴한다(§3.2). 유니온이 하위호환·additive. "additive-only·기존 테스트 파괴 0"이 비준 전제.
6. **"가격을 4,499,000로 바꾸면 다른 슬라이스 단언이 깨진다."** — 반론: 파생 수량은 가격 무관(20 불변)·
   `request.price == outbound_price`는 동시 전환(GREEN)·venue_shape는 별개 fixture(§4.4). 단위 일관성은
   D-E2 이연이며 GAP-3은 값+계보만 흘린다.
7. **"차등 오라클/numeric은 왜 안 닫나."** — 반론: 스코프 밖(#33 §6.2·D-E2 gated·§10-7). 본 addendum은
   구조 배선 접합 4건만.

---

## 12. 미결·리스크 (구현 게이트)

- **REGREP 게이트(C10·C11·C13)**: `derive_order_size`·`StageRequest`·`run_commitment_flow`의
  정확-시그니처/필드-수 잠금 canary는 실측상 부재했으나, 구현 시점 **재grep 필수**(#32 v1.2 교훈 —
  터치 표면 전 canary 실측). 잠금 발견 시 additive 확장이 canary와 충돌하면 #32/WDR 선례대로 "구현이
  더 충실하면 canary 무력화 아닌 설계-정합" 판정.
- **배치 규율(MAJOR-1 해소)**: 신규 심볼은 **전부 기존 submodule에 배치**(어댑터→backtest/fills.py·
  factory→egressgw/records.py·투영→egressgw/construction.py) → 두 submodule-drift canary GREEN.
  **신규 .py 파일을 만들면** 두 canary(`test_backtest_import_closure.py:562-576`·
  `test_egressgw_import_closure.py:531-540`)가 loud FAIL하므로, 배치 규율을 벗어나지 말 것(구현 게이트).
- **shape/coordinates 비정합(MAJOR-3·리스크)**: 슬라이스는 venue가 4,200-shape를 admit하는데 command는
  4,499,000인 내부 비정합을 갖는다(어떤 verify 경로에도 무저촉·§4.4 4-경로 실증·§10-3 이연). 미래
  slice가 venue admissibility를 값-표면 gated로 강화하면 이 fixture 재-소싱이 접합점이다.
- **C9 §0.3 텍스트 개정**: egressgw 설계 #34 §0.3의 closure 선언에 `tos.dsl`을 명문화해야 allowlist
  테스트 갱신이 phantom-exemption이 아닌 정직한 edge가 된다.
- **value_view 스레딩의 core 경로**: `run_commitment_flow` 호출부(core.py:383)가 `payload.value_view`
  를 전달하도록 배선. core가 payload를 보유함은 실측(core.py:322-383)이나, 정확 호출 시그니처는
  구현 시 재확인.
- **field_key 소싱**: GAP-3 투영의 `price_field_key`는 사이징 정책이 지정(주입 config·하드코딩 0).
  슬라이스는 `"close"`(밴드 결정 field_key). 실 정책의 가격 field_key 규약은 D-E2/P0-1 소관.
- **held magnitude 부호/방향**: flat은 반대 방향으로 보유 magnitude를 닫는다. GAP-4는 magnitude만
  구조 파생하고 direction/side는 dsl FLAT proposal(direction="SHORT"/position_effect="CLOSE"·
  `_slice_fixtures.py`)이 이미 owns. side/direction 파생은 GAP-4 범위 밖(기존 envelope axis).

---

## 13. 명명·번호

- **문서 번호 #35** — 수직 슬라이스 #1 갭-closing addendum. 비준 4설계 #31(engine-event-core·D-E1)·
  #32(marketfeed·D-E2)·#33(backtest·D-E3)·#34(egressgw-brokeradapter·D-E4)에 대한 통합 addendum.
- **신규 심볼**(구현 확정 대상): `tos.backtest.EgressResultSource`(Protocol)·`GatewayResultReinjector`
  (어댑터)·`RetainedEgressResults`(로컬 구조 Protocol)·`tos.egressgw.send_boundary_context`(factory)·
  `admitted_price_from_view`(투영)·`AdmittedPriceObservation.value_payload_digest`(필드)·
  `derive_order_size(held_position=...)`·`ProvisionalReservationLedger.outstanding_consumed_magnitude`·
  `StageRequest.value_view`/`held_position_magnitude`. 명명은 gap 테스트 토큰 규약(`resultsource`/
  `send_boundary_context`)과 정합(closure 신호). negative-grep 충돌 0(구현 시 재확인).
- **신규 패키지 0** — addendum은 기존 4패키지의 seam만 채운다.

---

## 14. 개정 로그

- **v1.1 (2026-07-29)**: 독립 비평 REVISE 전건 처분. finding별:

  | finding | 처분 | 변경 위치 |
  |---|---|---|
  | **MAJOR-1** (egressgw submodule canary 누락·배치 미지정) | **채택 (a)+(b)** | 배치 확정: 어댑터→fills.py·factory→records.py·투영→construction.py(§2.1·§3.1·§4.2); §6 C19 행 추가·C3 WIDEN→GREEN; §12 배치 규율 |
  | **MAJOR-2** (factory 시그니처 폭발 은폐) | **채택** | §3.1 생산 시그니처 명세(파생 vs 주입·verify-item→그룹→소스 표)·lazy resolver 부분-적용 패턴 |
  | **MAJOR-3** (e2e GREEN 미증명·divergence) | **채택 (a)+확장** | §4.4 4-verify-경로 grep 증거 사슬(item 11/13/17·outbound_binding_mismatch:1302-1337)·내부 비정합 정직 명기; §10-3·§12 이연 등재 |
  | **MINOR-1** (FLIP 5→6) | 채택 | §6 요약 정정(C1·C2·C5·C6·C7·C8) |
  | **MINOR-2** (FLAT presence-가드 우회) | 채택 | §5.2 raw 산출 basis별 분기·presence-가드 비-FLAT 조건 이동(삽입점 :273); §7-5(e)·§9-5 canary 보강 |
  | **MINOR-3** (package canary 2건) | 채택 | §6 C20(egressgw phantom :35)·C21(engine dedup :75) GREEN 행 |
  | **NIT-1** (pipeline :323→:325) | **기각·재grep 실증** | `resolved_context=payload.value_view`는 pipeline.py:**323**(라인 325=`outcome = select_outcome`)·2 occurrence(:312 주석·:323 kwarg)·원 인용 :323 정확·유지. 비평 :325는 실측 불일치 |
  | **NIT-2** (handoffs 의미) | 채택 | §2.1 5멤버 표(driver는 `len`만 소비·driver.py:311·sized iterable) |

  수정 인용 전부 재grep(2026-07-29): gateway.py:1169-1174(exact_binding_holds)·1302-1337(outbound_binding_mismatch)·
  vocabulary.py:168/175(step 2/8)·pipeline.py:323·test_egressgw_import_closure.py:531-540·
  test_egressgw_package.py:35·test_engine_package.py:75·construction.py:224-273·_slice_fixtures.py:719-721/914-944.
- **v1.0-draft (2026-07-29)**: 최초 저작. 슬라이스 통합(`afe44101`·31 tests) 발굴 4갭의 통합 계약.
  1차 심사·독립 비평 대기.

<!-- 저작 증거·닫는 EV 0. 비준 전 파이프라인: 1차 심사 → 독립 비평 → 개정 → 운영자 위임 자동 비준
(2026-07-29 연장) → 구현 → 적대적 코드 리뷰. -->
