# 설계 문서 #26 — Safety-Waiver / Deviation / Residual-Risk Governance 계약 (2026-07-27, v1.1)

> **v1.1 개정(2026-07-27, 독립 비평 REVISE 반영 — CRITICAL 0·MAJOR 2·MINOR 2)**: ① §5.5a item 1·§4.4·§10 결함-클래스 표의 ∅ 가드를
> ADR §13 line 364 "explicit empty Active Deviation Set" 명시 허용과 정합화(applicable=∅+members=∅+is_complete=True
> 는 유효 — 무조건 거부하던 v1.0 과잉 봉합 제거·MAJOR-1); ② 지지 seam 인용 정정(MAJOR-2): spg records.py:284,707
> →:284 prose/:293 필드(707은 591행 파일 EOF 초과 phantom)·rlp records.py:177,278,501,551→:278,552 필드(+177 prose)·
> spg predicates.py:146→:142 def·"a newer generation SHALL restrict future authority monotonically" 귀속 §14:398→
> **§1:29**(§14:398은 "SHALL advance a restrictive floor" — 병기로 정정). 극성 표·verbatim 부록 A~D·register 분류·
> edge-0·seam 소유권 결론은 비평이 전 축 실측 통과 판정(변경 없음).

> **문서 번호 규약**: 세션 A 잔여 조정(MEMORY 2026-07-27)에 따라 본 WDR(ADR-002-026) 문서는 **설계 문서
> #26**다. #24=PTF(세션 B)·#25=RLP(세션 A 완결)로 확정된 뒤 다음 순번.

> ADR-002-026 (Safety Waiver, Deviation, and Residual-Risk Governance — "WDR")를 Phase 1(EV-L1) 설계
> 계약으로 실현한다. **이 문서가 실현하는 것은 시리즈의 "greenfield content owner(피이연 없음)"**다: RLP(#25)는
> egress/cur가 `tos.rlp`를 **이름까지 명시해 내용 검증을 이연**한 피이연자(deferee)였으나, **WDR은 어떤 착지
> 형제도 `tos.wdr`로 내용을 이연하지 않는다**(실측 §0.4b). `tos.wdr`라는 이름은 오직 두 firewall
> allowlist-배제 목록(`cur/__init__.py:51`·`rlp/__init__.py:39`이 "미래 형제 `tos.wdr` … 는 §7.1 allowlist가
> 자동 배제"로만 열거)에 의해 고정된다. 따라서 **naming은 RLP보다 약한 soft load-bearing**이며(기능 참조를
> orphan화하지 않고 목록 주석의 명명만 부정확해질 뿐), 본 계약은 이 차이를 정직하게 명문화한다(§0.4a — RLP와의
> 최대 대비점).
>
> **이 문서의 두 최대 위험은 서로 반대 방향이다(#22/#23/#25 선례).** (1) **over-realization(주 위험)**: WDR은
> 시리즈에서 가장 "거버넌스 순수"한 ADR이라 *인간 절차*(independent effective-person review·quorum·residual-risk
> acceptance)와 *런타임*(per-action final-egress currentness binding·revocation send-race·worst-credible-effect
> 계산·compensating-control 실효성·break-before-make configuration activation)의 색채가 압도적이다. 이들을
> L1으로 오주장하면 안 된다 — 전부 인간/런타임/+Security/+Broker/형제-owned. **L1-decidable 슬라이스는 5개 core
> 구조/극성 술어 + 6개 얇은 predicate-only substrate + 1개 not-Phase-1 race 모델 뿐**이며 **이 정직한 경계가
> 본 문서의 최대 규율**이다. (2) **duplication/over-reach**: 형제 소유(spg Hard Safety Envelope/`bundle_complete`/
> `residual_risk_ceiling`·hag effective-principal collapse/quorum·rcl CapacityVector/worst-credible-effect·
> egress final-egress enforcement·cur Safety Currentness Vector·evidence custody/gap/causal-chain·liveauth Live
> Authorization·iap single-use consumption·authority epoch/non-revival)의 *비즈니스 내용*을 WDR이 재판정하는 것.
> 각 owner verdict/generation/digest를 **주입 소비**만 하고 재저작하지 않는다(§3.5 SoD 표).
>
> **비준 기록: 2026-07-27 운영자 위임 자동 비준 대상(v1.0 초안; 2026-07-25 표준지시 — "남은 ADR 구현 자동 비준
> 승인으로 계속 진행"). 게이트: 독립 비평 리뷰 통과 + upgrade 조건 충족을 오케스트레이터가 검증 후 "운영자 위임
> 자동 비준(2026-07-25 지시)"으로 기록·집행. 품질 파이프라인[저작→1차 심사→독립 비평→개정→구현→적대적 코드
> 리뷰→게이트] 전량 유지.** 본 문서는 GOV-001의 세 거버넌스 행위(비준 / ADR acceptance / live authorization)
> 중 어느 것도 수행하지 않는다. tos-spec을 수정하지 않으며 어떤 WDR-EV/WDR-AC/acceptance/비준도 선언하지 않는다.
> 기존 `docs/plans/**` 무수정. 미착지 상류(-027 SIR·-028 STM·-029 SCI·-030 PTF) 코드 인용 없음(전부 ADR 원문만).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. **패키지 명명** `tos.wdr`(register prefix `WDR` 소문자 1:1·terse-lowercase 관행; §0.4a). **naming이 RLP보다
   약한 soft load-bearing**: `tos.wdr`는 두 firewall allowlist-배제 목록(`cur/__init__.py:51`·`rlp/__init__.py:39`)이
   "미래 형제"로만 열거 — RLP처럼 내용을 이연한 참조가 아니므로 다른 이름을 써도 기능 orphan은 없고 목록 명명만
   부정확해진다. 그럼에도 register prefix 1:1(WDR-INV/WDR-AC/WDR-EV)과 관행 정합·운영자 "변경 불가" 지시로
   `tos.wdr` 확정. runner-up `tos.waiver`·`tos.deviation`(기각·§10.1).
2. **핵심 아키텍처 판정 — WDR = greenfield deviation-governance content owner·피이연 없음(본 문서 최대 판정·
   §0.4b).** RLP(#25)와의 결정적 대비: RLP는 egress `state.py:196`·cur `state.py:140`이 `tos.rlp`를 이름까지
   명시해 trial-content를 이연받은 피이연자였다. **WDR은 그런 inbound 이연 seam이 실측상 0건**(§0.4b grep 결과).
   WDR은 5개 immutable 아티팩트(`SafetyDeviationPolicy`·`SafetyDeviationRequest`·`SafetyDeviationDecision`·
   `ResidualRiskAcceptanceRecord`·`ActiveDeviationSet` — gate-status line 793 "the **five** deviation templates")를
   저작하고, 그 `Deviation Generation` 좌표가 §14에 따라 **cur Safety Currentness Vector로 하류에 흘러갈 예정**
   이나 cur는 현재 그 차원을 소유·이연하지 않는다(cur 미착지 forward 관계·§3.5). **WDR은 형제를 import하지 않으며**
   (sibling edge 0·§3.4) 형제 boundary/verdict를 재저작하지 않는다.
3. **EV 3분류(행별 정직)** — **core(L1 슬라이스) 5행 {WDR-EV-001 Non-Waivable Boundary `EV-L1/3+Security`·002
   Exact Scope and Dependency Closure `EV-L1/3`·007 UNKNOWN, Capacity, and Protective Confinement `EV-L1/3+Broker`·
   010 Evidence and Status Honesty `EV-L1/3`·012 Combined Deviations and Gate Separation `EV-L1/3+Security`}**
   (거버넌스 6부작 중 L1 접근성 **공동 최대**·survey line 21/420) / **predicate-only 6행 {003·004·005·009
   `EV-L2/3+Security`·008 `EV-L2/3+Broker`·011 `EV-L2/3+Broker+Security`}** / **not-Phase-1 1행 {006 Currentness,
   Revocation, and Send Race `EV-L3+Security`}**. **닫는 WDR-EV = 0건**(§1). "EV-L1-complete 주장 금지".
   **RLP와의 대비**: RLP core 4행은 전부 순수 `EV-L1/3`(좌표 태그 0)였으나 **WDR core 5행 중 3행(001·007·012)은
   `+Security`/`+Broker` 잔여 태그를 보유** — L1 슬라이스는 존재하나 그 행의 closing은 Phase-1 밖임을 행별로 명기.
4. **중심 L1 술어(§5·5 노른자)** — `boundary_denies_non_waivable`(WDR-EV-001·노른자 1·§8 15-item 경계)·
   `scope_exact_and_complete`(WDR-EV-002·노른자 2·§10 exact scope + §5.10 dependency closure)·
   `unknown_denies_and_confines`(WDR-EV-007·노른자 3·§16 UNKNOWN⇒deny + budget≠capacity + protective label≠bypass)·
   `evidence_status_honest`(WDR-EV-010·노른자 4·§19 non-PASS 유지·approval≠verification)·`combined_set_no_permissive_union`
   + `gate_states_separated`(WDR-EV-012·노른자 5·§13 canonical set no-union + §26 AC-012 상태 분리). 전부 순수·
   fail-closed·전 owner verdict/generation/digest는 주입.
5. **over-realization + duplication 이중 경계 명시(§1·§6c·§3.5)** — independent effective-person review + quorum
   (§12·hag)·per-action final-egress currentness binding(§14·egress)·revocation/expiry send-race(§14·+Security)·
   worst-credible-effect 계산(§11·rcl + +Broker)·compensating-control 실효성 검증(§11·+Security)·break-before-make
   configuration activation(§13·spg/ADR-002-014)·Hard Safety Envelope 봉입(§8·§11·spg)·evidence 조립/custody
   무결성(§19·evidence)·Live Authorization 발급(§7·liveauth)은 **전부 인간/런타임/+Security/+Broker/형제-owned**.
   L1은 **boundary 판정·scope 완전성·UNKNOWN 극성 confinement·status 정직성·combined-set no-union·gate 분리**
   구조 판정만.
6. **소유권/seam 분할표(§3.5) — 본 문서 최대 함정.** spg(Hard Safety Envelope/`bundle_complete`/
   `residual_risk_ceiling`/break-before-make·소유)·hag(effective-principal collapse + quorum·소유)·rcl(CapacityVector
   + worst-credible-effect + `within_limits`·소유)·egress(final-egress enforcement·소유)·cur(Safety Currentness
   Vector·소유)·evidence(custody/gap/causal-chain·소유)·liveauth(Live Authorization·소유)·iap(single-use consumption
   *shape* 선례)·authority(epoch floor + non-revival 선례)를 **WDR이 재저작하지 않는다**. **sibling edge 0**(§3.4).
7. **선제 봉합** — ∅ 양방향(boundary/mandated-scope/dependency-closure set 부재 ⇒ deny)·집합 양방향(present ⊇
   mandated 양방향·closure ⊇ affected 양방향)·truthy-sentinel 구조 봉인(`DecisionResult`·`NonWaivableClassification`·
   `RequestState`·`ActiveDeviationState`·`WaivedEvidenceStatus` `__bool__ ⇒ TypeError`)·all-false deviation
   authority·malformed-model 자기방어(positive-claim + incomplete-scope coexistence seal — RLP `ExactTrialPlan`/
   egress QCC 동형)·**극성 규율 전 적용(음극성 소비는 `is False`만·`is not True` 금지·#18/#22/#23/#25 재발 방지)**·
   **그룹 reconcile(combined Active Deviation Set 전-entry 보수·no-permissive-union·#22 MAJOR-1 재발 방지·WDR-INV-006)**·
   **manually-transcribed regression anchor**(§8 15-item boundary·§5.7 21-dimension scope·§21 상태 집합 — enum-drift
   정직화·§0.4h)·금지 동사 canary(§4).

### 0.2 하지 않는 것 (경계·NO 목록)

- **형제 소유 로직 재저작 금지(duplication 경계·본 문서 특유 최대 위험).** spg `bundle_complete`/Hard Safety
  Envelope/`profile_within_envelope`/`residual_risk_ceiling`/break-before-make·hag `effective_principal_collapse`/
  `quorum_independence_satisfied`·rcl `CapacityVector`/worst-credible-effect/`within_limits`·egress final-egress
  enforcement·cur Safety Currentness Vector completeness·evidence `SegmentCommitmentScheme`/`causal_chain_complete`/
  gap machine·liveauth Live Authorization·authority epoch/HALT/revocation을 **재판정하지 않는다** — 각 owner verdict/
  generation/digest를 **주입 좌표**로만 소비(§3.5 SoD).
- **deviation 실행·per-action enforcement runtime 재구현 금지(over-realization 경계).** §14 per-action final-egress
  currentness binding(exact policy/Deviation Generation/active-set/scope 검증·cache-free)·§14 revocation/expiry
  send-race·§13 break-before-make activation·§11 worst-credible-effect 계산·§12 independent review quorum counting은
  **전부 런타임/egress-owned/spg-owned/hag-owned/+Security/+Broker**. L1은 **주입된 좌표 위의 순수 boundary/
  completeness/polarity/separation** 술어만.
- **spg Hard Safety Envelope / `bundle_complete` / break-before-make 재저작 금지(§0.4c).** spg(#12·ADR-002-014)가
  Hard Safety Envelope·Runtime Safety Profile·`profile_within_envelope`·`bundle_complete`·break-before-make·
  `residual_risk_ceiling`(profile envelope 필드)를 **소유**한다. WDR의 residual-risk는 *per-deviation accepted risk
  record*(§5.4)이며 spg의 *profile-level ceiling*과 다른 축이다. WDR은 "combined residual risk within Hard Safety
  Envelope"(§11 line 333·§13 item 3)를 **주입 verdict**로 소비하고 envelope 봉입을 재저작하지 않는다.
- **hag effective-principal/quorum 재저작 금지(§0.4e).** WDR-INV-007·§12 independent effective-person approval은
  hag(ADR-002-015)-owned. WDR은 hag verdict를 주입 소비. Governed Single-Operator Re-Arm Variant(§7·§12·
  ADR-002-015 §17.1·RFC-001 SAFE-053)도 hag/liveauth 소유·WDR 주입.
- **rcl CapacityVector 재판정 금지 + edge 0(§0.4g·측정 3 판정).** worst-credible-effect *계산*·capacity
  reservation·`within_limits`는 rcl + +Broker. WDR budget/accepted-risk는 **capacity가 아니다**(§7 line 217
  "deviation budget or accepted risk is never capacity"·WDR-INV-013). **WDR은 rcl을 import하지 않는다** — worst-credible
  economic-effect envelope는 **주입 opaque 좌표**(RLP `credible_economic_effect_envelope` 선례). are/ioc/afg가
  CapacityVector 타입을 import한 것과 달리 WDR L1은 capacity 산술을 하지 않으므로 edge 불필요(§0.4g 상세 판정).
- **evidence custody / register-status 재저작 금지 — 단, register-status *정직성* 어휘는 WDR-owned(§0.4d).**
  evidence(ADR-002-016)가 custody(`SegmentCommitmentScheme`)·gap·causal-chain·receipt를 소유. **실측: tos.evidence는
  `WAIVED_WITH_RESIDUAL_RISK`/register verification-status enum을 소유하지 않는다**(`GapStatus`·`ReceiptVerificationStatus`
  만 존재). 따라서 §19 verification-item status honesty 어휘(`WaivedEvidenceStatus`)는 **WDR이 로컬 저작**(seam
  충돌 0·§5.4 노른자 4). WDR은 custody/gap/causal-chain을 주입 소비.
- **수치 하드코딩 금지(§8)** — `B_deviation_revoke_to_authority`·`B_deviation_revoke_to_egress`·
  `B_deviation_generation_fence`·`MAX_deviation_duration_ms`·`MAX_deviation_decision_age_ms`·
  `MAX_residual_risk_review_interval_ms`(§27 item 12) 전부 Profile INSTANCE 측정/승인·주입(현재 전부 `null`/`TBD`·§8).
- **미착지 상류 코드 인용 금지** — SIR(-027)·STM(-028)·SCI(-029)·PTF(-030) 미착지(`tos/src/tos/` 하 부재 실측).
  §17의 incident(-027·ADR line 457) generation 차원은 **ADR 원문만·generation 주입·코드 인용 0**(phantom 봉합·§0.4f).
- **EV/acceptance/비준 선언 금지.** tos-spec 수정 금지·기존 docs/plans 무수정. 미비준 문서 인용 없음.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.wdr`는 **순수 모델·술어 패키지**다: `pydantic` + stdlib + `tos.canonical`(digest substrate) +
`tos.ordering`(generation 순서)만 import. `shared.*`·`services.*`·`cli.*`·`numpy`/`pandas`/`yaml`·`os.environ`·
동적 escape(`exec`/`eval`/`importlib`/`__import__`) **전면 부재**. **형제 tos 패키지(canonical·ordering 제외
전부: rcl·egress·cur·spg·hag·iap·evidence·liveauth·authority·time·ioc·are·afg·sbr·capsule·venue·protective·recon·
brokercap·orthostate·dsl·nontrade·replacement·posttrade·rlp + 미래 sir/stm/sci/ptf) 전부 import 부재** — 형제
상호작용은 **주입 scalar/digest/bool/verdict/enum-token**으로만(sibling edge 0·§3.4). clock·network·egress·
persistence 미접근. `tos/tests/wdr/test_wdr_import_closure.py`가 import-closure를 allowlist(`closure ⊆ {canonical,
ordering, wdr}`)로 강제하고 `tools/tos_firewall_check.py`(§3.2 ratified allowlist·default-deny) required check와
함께 green이어야 본 선언이 능동 성립(§7.1). **`tos.wdr`를 §3.2 allowlist에 추가하는 것은 본 설계 문서 §3.2를
편집하는 PR을 요구**(firewall check "Changing the allowlist requires a PR editing that doc").

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 명명 = `tos.wdr` (register-prefix 1:1·naming = RLP보다 약한 soft load-bearing).**

- **선택(확정) `tos.wdr`** — 근거:
  1. **register prefix 1:1**: 시리즈가 `WDR-INV`/`WDR-AC`/`WDR-EV`를 사용(register 실측 md line 336-347·
     ADR §6/§25/§26). terse-lowercase 관행(rcl·spg·iap·hag·are·ioc·afg·sbr·cur·egress·rlp)과 정합.
  2. **firewall 배제 목록이 이름을 이미 지명(약한 load-bearing)**: `cur/__init__.py:51`·`rlp/__init__.py:39`이
     "미래 형제 `tos.wdr`"를 §7.1 allowlist 자동 배제 대상으로 열거. **RLP와의 대비**: RLP는 egress/cur가
     trial-content를 `tos.rlp`로 **이연**(기능 참조)했으나, wdr은 firewall **배제 목록의 명명**일 뿐이라 다른
     이름 선택 시 기능 orphan은 없고 목록 주석만 부정확 — 그래서 naming을 **약한 soft load-bearing**으로 정직 표기.
  3. **충돌 없음**: `wdr`은 미점유(현 30패키지 실측). 운영자 "변경 불가" 지시.
- **runner-up `tos.waiver`/`tos.deviation`(기각)** — full-word 관행(liveauth·brokercap·orthostate·protective·
  replacement·nontrade·posttrade)도 존재하나 register-prefix 1:1(egress/hag/sbr/cur/rlp 최근 선례)이 더 강하고
  운영자 지시가 `tos.wdr`를 못박았다. **§10.1 운영자 판단 지점**: `tos.wdr` 채택.

**(b) WDR = greenfield deviation-governance content owner·피이연 없음 (본 문서 최대 판정·RLP와의 결정적 대비).**

- **실측(inbound 이연 seam 0건)**: `grep -rn "waiver|deviation|ADR-002-026|WDR|residual.risk|Non-Waivable"
  tos/src/tos/{spg,cur,replacement,rlp,egress}/` 결과 —
  1. `spg/records.py:356,370` `residual_risk_ceiling: CanonicalDecimal | None` — **spg 소유** profile envelope 필드
     (WDR 이연 아님·§0.4c seam).
  2. `spg/vocabulary.py:134`·`spg/predicates.py:372,434,490` "§5.2 deviation" — **spg 자체 설계 #12 §5.2의 "예외
     처리"** 의미(ADR-002-026 safety deviation 아님·phantom 함정·인용 금지).
  3. `replacement/vocabulary.py:238`·`protective/vocabulary.py:197` "deviation" — **일반 명사**(WDR 아님).
  4. `rlp/records.py:278,552` `residual_risks` 필드(+:177은 prose 언급) — **RLP 자체** §9 line 273 필드(WDR 이연 아님).
  5. `cur/__init__.py:51`·`rlp/__init__.py:39`의 `tos.wdr` — **firewall 배제 목록 명명만**(내용 이연 아님).
- **⇒ 판정**: 어떤 착지 형제도 deviation-content를 `tos.wdr`로 이연하지 않는다. WDR은 **RLP와 달리 피이연자가
  아니라 순수 greenfield 생산자**다. WDR이 소유하는 잔여 = **deviation-governance 계약 전체**:
  1. **§8 Non-Waivable Boundary 판정**(WDR-EV-001·노른자 1) — 15-item boundary anchor에 대한 deterministic denial +
     unresolved⇒non-waivable(§8 line 252).
  2. **§10 Exact Scope + §5.10 Dependency Closure 완전성**(WDR-EV-002·노른자 2) — 21-dimension exact scope +
     closure 완전성·no-wildcard/patch/widen/stale/conflict.
  3. **§16 UNKNOWN Confinement**(WDR-EV-007·노른자 3) — UNKNOWN⇒deny + budget≠capacity + protective≠bypass.
  4. **§19 Evidence Status Honesty**(WDR-EV-010·노른자 4) — non-PASS 유지·approval≠verification·`WaivedEvidenceStatus`
     로컬 어휘(evidence 미소유).
  5. **§13 Active Deviation Set no-union + §26 AC-012 Gate Separation**(WDR-EV-012·노른자 5).
- **재저작 금지 경계(엄격)**: WDR은 spg/hag/rcl/egress/cur/evidence/liveauth/authority verdict를 **재저작·import
  하지 않는다**(§3.5). **리뷰어 공격 지점(§10.2-①)**: "WDR이 RLP처럼 피이연자 미러" — 반론: 실측상 inbound 이연
  0건·WDR은 순수 생산자·naming은 firewall 배제 목록의 약한 load-bearing(정직 명기).

**(c) spg = Hard Safety Envelope / bundle_complete / break-before-make / residual_risk_ceiling 소유; WDR = 주입
소비 (§8/§11/§13 경계·재저작 금지).**
**실측**: spg(#12·착지)가 `Hard Safety Envelope`(records.py:321)·`Runtime Safety Profile`·`profile_within_envelope`
(predicates.py:142 def·docstring :146 "`... <= active Runtime Safety Profile <= active Hard Safety Envelope`")·`bundle_complete`
(predicates.py 완전성)·break-before-make(records.py:284 prose·:293 필드)·`residual_risk_ceiling`(records.py:370 profile envelope
필드)를 저작.

- **판정: profile-level envelope/ceiling/activation은 spg(ADR-002-014)-owned**. WDR §11 line 333 verbatim: "If the
  combined residual risk cannot be bounded inside the **Hard Safety Envelope** under loss of the compensating
  control, the request is denied." + §13 item 3 "combined residual risk remains inside the Hard Safety Envelope"
  ⇒ envelope 봉입 판정 = spg 주입 verdict. §13 item 7 "activation is break-before-make under ADR-002-014"·§9 line
  275 "Policy activation follows ADR-002-014" ⇒ activation = spg. WDR은 `ResidualRiskAcceptanceRecord`(per-deviation
  accepted risk·§5.4)를 소유하되 spg `residual_risk_ceiling`(profile ceiling)을 재저작하지 않는다. **리뷰어 공격
  지점(§10.2-②)**: "WDR residual-risk = spg residual_risk_ceiling 중복" — 반론: WDR = per-deviation accepted-risk
  record(§5.4), spg = profile-level ceiling·envelope 봉입은 spg 주입 verdict·edge 0.

**(d) evidence = custody/gap/causal-chain 소유; WDR = register verification-status *정직성* 어휘 소유 (§19 경계·
실측 evidence 미소유이므로 seam 충돌 0).**
**실측**: evidence(착지)가 `GapStatus`(gap.py:38)·`ReceiptVerificationStatus`(receipt.py:47)·`INCONCLUSIVE`
(replay.py:55)를 소유하나 **§19의 verification-item status(NOT_IMPLEMENTED/FAIL/BLOCKED/EXPIRED/
WAIVED_WITH_RESIDUAL_RISK/PASS) enum은 tos.evidence에 부재**(grep 확인).

- **판정: custody + 무결성은 evidence(ADR-002-016)-owned, verification-item status 정직성 어휘는 WDR-owned**.
  §19 line 488 verbatim: "`WAIVED_WITH_RESIDUAL_RISK` **only** when RFC-001 explicitly permits it and the exact
  current decision, reduced scope, compensation, and review record exist"·line 490 "It SHALL NOT be relabeled
  `PASS`, `ACCEPTED`, or completed merely because a deviation exists." ⇒ WDR이 `WaivedEvidenceStatus`
  `_NonTruthyStrEnum`과 `evidence_status_honest` 술어를 저작한다(§5.4). evidence `causal_chain_complete`/gap-status는
  **주입 verdict**로 소비. **경계 분할**: **evidence 소유** = custody/`SegmentCommitmentScheme`/gap/causal-chain.
  **WDR 소유** = verification-item status 정직성 vocabulary + honesty 술어. **리뷰어 공격 지점(§10.2-③)**:
  "WaivedEvidenceStatus = evidence status 중복" — 반론: 실측 tos.evidence 미소유·§19 register-status는 evidence
  custody와 다른 축·seam 충돌 0.

**(e) hag = effective-principal collapse + quorum 소유; WDR = 주입 verdict 소비 (§12/§7 independence 경계·재저작
금지).** WDR-INV-007·§12 independent effective-person approval·§7 authority separation이 **hag 재저작 함정**.

- **판정: 인간 authority 일반 모델은 hag(ADR-002-015)-owned**. WDR-INV-007 line 170-172 verbatim: "The requester,
  control owner, performance beneficiary, implementer, evidence producer, and live armer cannot collectively
  satisfy approval through one Effective Principal or shared administrative control." ⇒ effective-principal collapse
  판정 = hag. WDR은 hag verdict(`effective_principal_collapse` 결과·quorum satisfied)를 **주입 소비**. Governed
  Single-Operator Re-Arm Variant(§7 line 226·§12 line 352·ADR-002-015 §17.1)도 hag/liveauth 소유·WDR 주입.
- **⇒ WDR는 `effective_principal_collapse`·`quorum_independence_satisfied`를 재저작·import하지 않는다.** WDR는
  `all_false_deviation_authority` + SoD 구조 선언(deviation 컴포넌트는 RCL/egress authority·live-order credential/
  route 무보유·§7 line 224)만 L1으로 저작하고, 실 independence는 hag verdict + +Security(WDR-EV-004 `EV-L2/3+Security`).
  **리뷰어 공격 지점(§10.2-④)**: "WDR가 quorum 재저작" — 반론: quorum/collapse = hag·WDR = 주입 소비·edge 0.

**(f) 미착지 상류 027/028/029/030 차원 (phantom 봉합).** **실측**: `tos/src/tos/` 하 sir·stm·sci·ptf **부재**(ls
확인). §17 line 457이 incident(-027 ADR-002-027) generation 상호작용을 참조.

- **판정: WDR는 이를 주입 generation/digest 좌표로만 소비.** ADR 원문(§17 line 457)만 참조하고 **코드 인용 0**
  (미착지 — phantom 금지). Incident(-027) generation은 opaque 주입 scalar로 수용하고 내용 검증은 -027 ADR 이연.
  **리뷰어 공격 지점(§10.2-⑤)**: "미착지 차원 substrate 오인용" — 반론: ADR 원문만·코드 0·주입 좌표·§0.2 NO-list.

**(g) rcl edge 판정 = 0 (측정 3 핵심 판정·are/ioc/afg 선례와의 명시적 대비).**

- **실측 edge 선례**: `are -> rcl`(`records.py:61` `from tos.rcl import CapacityVector` — AdverseIncrement type)·
  `ioc -> rcl`(`records.py:69` `EconomicEffectEnvelope = CapacityVector` **별칭**)·`afg -> rcl`(`predicates.py:76`
  `from tos.rcl import CapacityVector, aggregate_usage, effective_limit`). 셋 다 **CapacityVector 타입을 import해
  실제 vector 산술/비교(`within_limits`·`aggregate_usage`·`effective_limit`)를 수행**하기 위한 단일 edge.
- **WDR ADR 텍스트 판정**: WDR은 **capacity가 아니다** — §7 line 217 "deviation budget or accepted risk is **never
  capacity**"·WDR-INV-013 line 194-196 "**Only RCL** mutates and serializes capacity … Deviation services hold
  neither authority"·§11 line 331 "Capacity reservation may bound an already permitted credible effect. It cannot
  turn UNKNOWN into permission"·§16 line 431 "Unknown exposure consumes the worst credible **RCL** capacity"(RCL이
  소비·WDR 아님). **WDR-EV-007 = `EV-L1/3+Broker`**(worst-credible 정량화가 +Broker·L1 아님).
- **⇒ 판정: edge 0**(RLP·iap 선례). WDR L1 술어는 **capacity 산술을 하지 않는다** — UNKNOWN⇒deny(극성)·budget≠capacity
  (all-false)·protective≠bypass(all-false)의 **구조/극성 판정만**. worst-credible economic-effect envelope는 rcl이
  나중에 소비할 **주입 opaque 좌표**(str digest·RLP `credible_economic_effect_envelope` 선례)로 나르되 **CapacityVector
  타입으로 타이핑하지 않는다**. are/ioc/afg가 edge를 취한 이유(vector 산술 comparability)가 WDR L1에는 부재하므로
  최소주의 원칙상 edge 불필요. **리뷰어 공격 지점(§10.2-⑥)**: "worst-credible을 위해 CapacityVector alias 필요" —
  반론: WDR L1은 vector 비교 미수행·정량화 +Broker/rcl-owned·§7 "never capacity"·edge 0이 ADR 정합.

**(h) rcl·liveauth·authority·time·iap·ordering 경계 (전부 verdict 주입 소비 / shape REUSE·§3.5 표).**

- **rcl(ADR-002-002/012)**: `CapacityVector`·`within_limits`·worst-credible-effect·commit-proof 소유. WDR budget은
  capacity 아님(§0.4g)·주입 좌표·계산 +Broker.
- **liveauth(ADR-002-007)**: Live Authorization 발급(§7 line 219). WDR 주입 소비·발급 안 함(WDR-INV-001).
- **authority(ADR-002-003)**: `authority_epoch_current`(`>=` floor)·`recovery_generation_revives_nothing` — floor `>=`
  shape + non-revival 선례(WDR `recovery_revives_nothing`이 REUSE via `tos.ordering`·재저작 아님).
- **time(ADR-002-008)**: `freshness_verdict` — expiry/review-interval(§15)의 Trustworthy Time generation은 WDR 주입
  좌표. `MAX_deviation_*_ms` wall-clock age는 secondary +Security/INSTANCE.
- **iap(ADR-002-023)**: `single_use`/`exact_intent_only`·consume gate `result is ApprovalResult.APPROVE`
  (predicates.py:176/230). **single-use consumption *shape* 선례** — WDR `decision_single_use_non_authorizing`가 이
  shape을 로컬 재표현(import 아님). §13 line 368 "consumed exactly once"·WDR-INV-008과 동형.
- **ordering(REUSE import)**: Deviation Generation monotonic fence(§5.8)·predecessor floor(§10 line 284)·authority
  epoch `>=` shape.

---

## 1. 범위 매핑 — ADR-002-026 조항별 EV-L1 도달성 (닫는 WDR-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **+Security = 독립 security-boundary assessment**, **+Broker = broker-capability
실측**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — WDR-EV core 5행(거버넌스 6부작 중 L1 공동 최대)**: register 실측(md line 336-347):
> **core(L1 슬라이스) 5행 = {001 Non-Waivable Boundary `EV-L1/3+Security`·002 Exact Scope and Dependency
> Closure `EV-L1/3`·007 UNKNOWN, Capacity, and Protective Confinement `EV-L1/3+Broker`·010 Evidence and Status
> Honesty `EV-L1/3`·012 Combined Deviations and Gate Separation `EV-L1/3+Security`}**. **predicate-only(≥ L2)
> 6행 = {003 Compensating-Control Effectiveness·004 Independent Effective-Person Approval·005 Non-Authorizing
> Single-Use Activation·009 Expiry/Renewal/Recovery [`EV-L2/3+Security`]·008 Broker Finality/Economic Continuity
> [`EV-L2/3+Broker`]·011 Security/Alternate-Route/Emergency [`EV-L2/3+Broker+Security`]}**. **not-Phase-1(L3+) 1행 =
> {006 Currentness, Revocation, and Send Race [`EV-L3+Security`]}**. **닫는 WDR-EV = 0건**. survey(§4.2 line
> 247-258) 판정과 정확 정합.
>
> **결정적 사실 2 — core 5행 중 3행이 좌표 잔여 태그 보유(RLP와의 대비·정직성 핵심)**: RLP core 4행은 전부
> 순수 `EV-L1/3`(태그 0)였으나 **WDR core 5행 중 002·010만 순수 `EV-L1/3`이고 001은 `+Security`·007은
> `+Broker`·012는 `+Security` 잔여**. 즉 001/007/012는 **L1 슬라이스가 존재하나 그 행의 최종 closing에
> +Security/+Broker 축이 남는다** — L1 술어는 저작하되 그 행을 **닫지 못한다**(§5.1/5.3/5.5 각 행별 명기).
>
> **결정적 사실 3 — authoring ≠ acceptance (닫는 WDR-EV = 0건)**: (a) core 5행 전부 `/3`(integration/
> adversarial) 잔여 + 3행은 +Security/+Broker 추가 잔여, (b) predicate-only 6행은 최소 ≥ L2(+Broker/+Security),
> (c) not-Phase-1 1행은 L3+ 런타임 race, (d) VER-002-001 §5 "Registration is not execution"·ADR §25 line 639
> "Written cases are not completed evidence"·§28 line 754 "Authorship … does not satisfy these gates. This ADR
> authorizes architecture and implementation planning only"·gate-status line 793 "All 363 registered items remain
> `NOT_IMPLEMENTED` … The review creates no … evidence `PASS` …". ⇒ **"EV-L1-complete 주장 금지"**(#12–#25 §1 규율
> 상속). Owner/Reviewer는 register상 TBD·status NOT_IMPLEMENTED(전 12행).

**규율 태그(모든 주장에 부착)**: "**boundary/completeness/polarity/separation predicate substrate only;
WDR-EV-001..012 전부 NOT_IMPLEMENTED — core 5행(001·002·007·010·012)은 `/3` 통합·adversarial 대기 + 001/007/012는
+Security/+Broker 추가 잔여, predicate-only 6행은 component-fault L2·+Security/+Broker 대기, not-Phase-1 1행(006)은
런타임 revocation send-race(+Security). EV-L1-complete 주장 금지·independent review·quorum·per-action egress
binding·worst-credible-effect 계산·break-before-make activation·compensating-control 실효성·Live Authorization
발급은 재저작/런타임/인간/+Security/+Broker. L1은 boundary/scope/UNKNOWN/status/set/gate 구조 판정만.**"

**WDR-EV core 5행 ↔ AC(1:1) ↔ ADR 조항 매핑(실측)**:

| WDR-EV | register 제목(verbatim, md line) | 최소 레벨 | WDR-AC(1:1) | ADR 조항 앵커 | L1 substrate 술어(§5) |
|---|---|---|---|---|---|
| **001** | Non-Waivable Boundary (336) | `EV-L1/3+Security` | AC-001(§25 line 641) | §8 Non-Waivable Boundary·WDR-INV-002 | `boundary_denies_non_waivable`(노른자 1) + `unresolved_is_non_waivable`·`boundary_is_union_only`(§5.1) |
| **002** | Exact Scope and Dependency Closure (337) | `EV-L1/3` | AC-002(§25 line 645) | §10 Exact Request·§5.10 Closure·WDR-INV-003 | `scope_exact_and_complete`(노른자 2) + `no_wildcard_scope`·`dependency_closure_complete`·`no_scope_drift`(§5.2) |
| **007** | UNKNOWN, Capacity, and Protective Confinement (342) | `EV-L1/3+Broker` | AC-007(§25 line 665) | §16 UNKNOWN·§11·WDR-INV-010 | `unknown_denies_and_confines`(노른자 3) + `budget_is_not_capacity`·`protective_label_no_bypass`(§5.3) |
| **010** | Evidence and Status Honesty (345) | `EV-L1/3` | AC-010(§25 line 677) | §19 Evidence Honesty·WDR-INV-004 | `evidence_status_honest`(노른자 4) + `approval_is_not_verification`·`waived_requires_exact_current`(§5.4) |
| **012** | Combined Deviations and Gate Separation (347) | `EV-L1/3+Security` | AC-012(§25 line 685) | §13 Active Set·§26 AC-012·WDR-INV-006 | `combined_set_no_permissive_union`(노른자 5a) + `gate_states_separated`(노른자 5b)·`omitted_deviation_invalidates`(§5.5) |

**ADR-002-026 조항 → Phase-1 분류(core / predicate-only / not-Phase-1)**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | WDR-EV |
|---|---|---|---|---|
| **§8** (line 230-252) | Non-Waivable Boundary 15-item union·unresolved⇒non-waivable | **core (L1)·+Security 잔여** | `boundary_denies_non_waivable`(§5.1) — 15-item anchor에 대한 deterministic denial·`UNRESOLVED`⇒non-waivable·boundary는 UNION-only(정책은 추가만). 실 classification manipulation 저항은 +Security. | **001** |
| **§10** (line 279-302)·**§5.10** (138-140) | Exact request·scope·dependency closure·no patch/widen/stale | **core (L1 슬라이스)** | `scope_exact_and_complete`(§5.2) — 21-dimension exact scope + closure present·concrete·no-wildcard/patch/widen/stale/conflict. 가장 깨끗한 L1(RLP `plan_scope_exact_and_complete` 동형). | **002** |
| **§16** (line 423-436)·**§11** (305-333) | UNKNOWN⇒deny·budget≠capacity·protective≠permission | **core (L1)·+Broker 잔여** | `unknown_denies_and_confines`(§5.3) — 전 UNKNOWN 극성 필드 `is not False`⇒deny + `budget_is_not_capacity`(all-false·§7 "never capacity") + `protective_label_no_bypass`(§11 line 331). worst-credible 정량화는 rcl + +Broker. | **007** |
| **§19** (line 480-492) | Evidence honesty·non-PASS 유지·approval≠verification | **core (L1 슬라이스)** | `evidence_status_honest`(§5.4) — deviation 존재가 PASS로 flip 불가·failed/missing 가시·`WAIVED_WITH_RESIDUAL_RISK`는 exact-current 조건에서만. `WaivedEvidenceStatus` WDR-owned(evidence 미소유·§0.4d). | **010** |
| **§13** (line 362-380)·**§26 AC-012** (685-687)·**§28** (732-754) | Active set no-union·gate 상태 distinct | **core (L1)·+Security 잔여** | `combined_set_no_permissive_union`(§5.5·no-union·any-narrow-wins·omitted⇒invalid) + `gate_states_separated`(ADR-acceptance/eligibility/activation/Live-Auth/restricted-live/production distinct). 실 combined-risk manipulation은 +Security. | **012** |
| **§11** (line 305-333) | Compensating-control 실효성·observation 불가 | **predicate-only (+Security)** | `compensating_control_not_observation`(§6.1·all-false — docs/monitoring/alerting/operator/priority/expected-rejection/common-mode ≠ preventive/containment·§11 8-point 구조). 실 independence 검증은 +Security. | **003** |
| **§12** (line 337-358)·**§7** (208-227) | Independent effective-person approval·role separation | **predicate-only (+Security)** | `independent_effective_person_approval`(§6.2·`all_false_deviation_authority` + SoD 구조 선언 + hag `effective_principal_verdict` 주입). collapse/quorum은 hag-owned(§0.4e). | **004** |
| **§13** (line 362-380)·**§7·§17** | Non-authorizing single-use activation | **predicate-only (+Security)** | `deviation_single_use_non_authorizing`(§6.3·iap consumption shape REUSE — `single_use_consumed is False`⇒consume once·`result is ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`·no widening/partial/replay + all-false). 실 registry replay는 +Security. | **005** |
| **§16** (line 423-434)·**§11** (312) | Broker finality·economic continuity | **predicate-only (+Broker)** | `broker_finality_unchanged`(§6.4·missing-ACK ≠ non-acceptance·Cancel-ACK ≠ FQP·구조 token) + `economic_effect_persists`(음극성·expiry/rollback ≠ erase/release·afg/are shape). 실 broker-finality는 +Broker. | **008** |
| **§15** (line 404-419)·**§18** (463-476) | Expiry·no-renewal·recovery·non-revival | **predicate-only (+Security)** | `expiry_recovery_revives_nothing`(§6.5·expiry no-auto-renewal + recovery revives nothing + restriction no-self-revert·WDR-INV-014/015·authority/cur shape). 실 hard-fence는 +Security. | **009** |
| **§17** (line 440-459)·**§20** (496-510)·**§7** | Break-glass·alternate route·deviation service no-route | **predicate-only (+Broker+Security)** | `break_glass_no_authority`(§6.6·all-false — HALT/deny/narrow만·approve/activate/mutate-capacity/classify-protective/credential/transmit/clear-HALT/re-arm 불가·§17 line 444-453) + `deviation_service_no_route`(§7 line 224·WDR-INV-013). 실 security boundary는 +Broker+Security. | **011** |
| **§14** (line 384-401) | Currentness·revocation·send-race·first-byte | **not-Phase-1 (런타임 race)** | 얇은 순서 permutation model(§6b·`REVOKE<SEND`⇒deny·`SEND<REVOKE<FIRST_BYTE`⇒potentially-live + capacity-covered·ambiguous⇒potentially-live·no-blind-retry·§14 line 400). 실 cache-free currentness·`B_deviation_revoke_to_egress`·deny-first latch는 +Security 런타임. | **006** |
| **§9·§12·§13·§14·§27·§28** | Policy activation·quorum counting·break-before-make·per-action binding·수치·acceptance | **not-Phase-1 (Phase-0/INSTANCE·런타임/형제)** | policy activation=spg 주입·quorum counting=hag·break-before-make=spg·per-action currentness=egress 런타임. 수치·acceptance는 §9.2 Phase-0. | (전 행 분산) |

---

## 2. 데이터 모델 계약

### 2.1 digest-bound / value / reference 분류

| 분류 | 모델 | 근거 |
|---|---|---|
| **digest-bound `IndependentIdArtifact`** (id ⊥ digest) | `SafetyDeviationPolicy`(§5.1/§9)·`SafetyDeviationRequest`(§5.2/§10)·`SafetyDeviationDecision`(§5.3/§12)·`ResidualRiskAcceptanceRecord`(§5.4/§11)·`ActiveDeviationSet`(§5.9/§13) — gate-status line 793 "the **five** deviation templates" | append-only ledger citizen(§19 line 482 "SHALL be retained under ADR-002-016"·§10 line 284 "canonical digest, and predecessor"·§5.2/5.3/5.4/5.9 "immutable"). id 서비스 부여(≠ `f(digest)`·canonical `IndependentIdArtifact` — rcl/dsl/authority/rlp/egress/cur 선례). same-id/different-bytes 위조/replay를 `classify_record_pair` CRITICAL_CONFLICT로 탐지(§3.1). |
| **value (frozen, id 없음)** | `DeviationScope`(§5.7 21-dimension exact scope)·`CompensatingControl`(§5.5 preventive/containment 서술)·`DeviationDependencyClosure`(§5.10 affected closure set)·`NonWaivableBoundaryAnchor`(§5.6/§8 15-item union anchor)·`WaivedEvidenceItem`(§19 status honesty view)·`GateSeparationLadder`(§26 AC-012 distinct 상태)·`DeviationClassification`(§8 classification input) | id 미도출·mutate 없음. `NonWaivableBoundaryAnchor`·`DeviationScope`의 dimension 집합은 §8/§5.7 조항을 손전사한 **manually-transcribed anchor**(§0.4h·§7.2 drift property). |
| **enum-token (`_NonTruthyStrEnum`)** | `DecisionResult`{DENY/HOLD/ELIGIBLE_FOR_RESTRICTED_CONFIGURATION}·`NonWaivableClassification`{NON_WAIVABLE/WAIVABLE_ELIGIBLE/UNRESOLVED}·`RequestState`{DRAFT..EXPIRED 10-state}·`ActiveDeviationState`{NOT_ACTIVE..SUPERSEDED 7-state}·`WaivedEvidenceStatus`{NOT_IMPLEMENTED/FAIL/INCONCLUSIVE/BLOCKED/EXPIRED/WAIVED_WITH_RESIDUAL_RISK/PASS} | 어휘(§2.2). `__bool__ ⇒ TypeError`(truthy 봉인·비-clear 멤버가 non-empty string). |
| **reference (scalar/digest only, 주입)** | spg Hard Safety Envelope 봉입 verdict + `residual_risk_ceiling` + break-before-make generation·hag effective-principal collapse verdict + quorum satisfied·rcl CapacityVector + worst-credible-effect 좌표·egress final-egress currentness verdict·cur Safety Currentness Vector generation·evidence causal_chain_complete + gap-status·liveauth Live Authorization generation·authority epoch/HALT/revocation gen·time Trustworthy Time gen·**Deviation Generation**(WDR 생산·§5.8)·**027 incident generation(미착지·주입)** | 형제/미착지 소유 — 주입 scalar/digest/verdict로만 참조(§3.4/§3.5). WDR는 이들을 저작·import하지 않음(Deviation Generation은 WDR 생산이나 cur 하류 소비는 cur 소유). **-027은 미착지 — ADR 원문만·코드 인용 0(§0.4f).** |

### 2.2 어휘 (verbatim 전사 + truthy 봉인)

**(1) `DecisionResult` (§5.3 line 110-112, non-truthy StrEnum — 핵심 truthy 봉인).** `DENY`·`HOLD`·
`ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`. **`_NonTruthyStrEnum` 로컬 재표현**(iap `ApprovalResult`·cur `ProofResult`
동형·**import 아님**·`__bool__ ⇒ TypeError`). **근거**: §5.3 verbatim: "An immutable independent result of `DENY`,
`HOLD`, or `ELIGIBLE_FOR_RESTRICTED_CONFIGURATION` for one exact request digest." §12 line 356 "An
`ELIGIBLE_FOR_RESTRICTED_CONFIGURATION` decision SHALL bind … one allowed configuration-request consumption."
`DENY`/`HOLD`는 non-empty string이라 `if result:`가 **거부를 truthy로 오독하는 치명적 fail-open**. 소비 게이트는
**`result is DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION` 명시 비교 강제**(§4.2·§7 회귀). ELIGIBLE 자체도
authority 아님(§1 line 25 "It does not activate configuration or satisfy the affected requirement"·all-false·§6.3).

**(2) `NonWaivableClassification` (§8 line 252, non-truthy StrEnum — unresolved⇒non-waivable 봉인).** `NON_WAIVABLE`·
`WAIVABLE_ELIGIBLE`·`UNRESOLVED`. **`_NonTruthyStrEnum`**. **근거**: §8 line 252 verbatim: "If requirement identity
or applicability is unresolved, it is treated as **non-waivable** until positively classified otherwise by the
current policy and independent review." ⇒ `UNRESOLVED`와 `NON_WAIVABLE` 둘 다 deny로 수렴. 소비 게이트는
**`classification is NonWaivableClassification.WAIVABLE_ELIGIBLE` 명시**(다른 모든 값 deny·§5.1). `if classification:`
오용이 `NON_WAIVABLE`/`UNRESOLVED`(non-empty string)를 truthy "go"로 오독하는 fail-open 방지.

**(3) `RequestState` (§21 line 518-524, non-truthy StrEnum — 10-state).** `DRAFT`·`SUBMITTED`·`UNDER_REVIEW`·
`DENIED`·`HOLD`·`ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`·`CONSUMED`·`SUPERSEDED`·`REVOKED`·`EXPIRED`.
**`_NonTruthyStrEnum`**(비-permissive 상태가 non-empty string이라 `if state:`가 terminal/revoked를 truthy "go"로
오독하는 fail-open). **근거**: §21 line 518-524 verbatim 전사(§부록 D). 어떤 상태도 authority 무부여(§6.2 all-false).

**(4) `ActiveDeviationState` (§21 line 528-534, non-truthy StrEnum — 7-state).** `NOT_ACTIVE`·`CONFIGURATION_STAGED`·
`ACTIVE_RESTRICTED`·`RESTRICTION_PENDING`·`REVOKED`·`EXPIRED`·`SUPERSEDED`. **`_NonTruthyStrEnum`**. **근거**:
§21 line 536 "Only ADR-002-014 activation may move `CONFIGURATION_STAGED` to `ACTIVE_RESTRICTED`, and that state
still creates **no live authority**"·line 538 "No transition from `REVOKED`, `EXPIRED`, or `SUPERSEDED` returns to
`ACTIVE_RESTRICTED`." `ACTIVE_RESTRICTED`조차 all-false authority(§6.2). 활성화 전이는 spg/ADR-002-014 주입(§0.4c).

**(5) `WaivedEvidenceStatus` (§19 line 484-490, non-truthy StrEnum — status honesty 어휘·WDR-owned).**
`NOT_IMPLEMENTED`·`FAIL`·`INCONCLUSIVE`·`BLOCKED`·`EXPIRED`·`WAIVED_WITH_RESIDUAL_RISK`·`PASS`. **`_NonTruthyStrEnum`**.
**근거**: §19 line 484-488 verbatim: "An evidence item covered by an allowed deviation SHALL remain one of:
`NOT_IMPLEMENTED` … `FAIL`, `INCONCLUSIVE`, `BLOCKED`, or `EXPIRED` … `WAIVED_WITH_RESIDUAL_RISK` **only** when
RFC-001 explicitly permits it and the exact current decision, reduced scope, compensation, and review record
exist." + line 490 "It SHALL NOT be relabeled `PASS`, `ACCEPTED`, or completed merely because a deviation exists."
`PASS`는 멤버이나(정직 측정 PASS 표현) **deviation 존재⇒PASS flip은 술어가 금지**(§5.4). **실측: tos.evidence
미소유이므로 WDR 로컬 저작**(§0.4d·seam 충돌 0).

### 2.3 아티팩트 covered + self-exclusion + malformed-model 자기방어 (설계 #4 §3.3·#20 §2.3·#22/#23/#25 §2.3 상속)

- 모든 digest-bound 아티팩트는 `IndependentIdArtifact`(canonical `_base.py:328`)를 상속 — `_ID_FIELD`(독립 id·
  digest preimage self-exclusion)·`_COVERED_FIELDS`(digest cover)·`_REQUIRED_COVERED`(구조 identity 최소 필수)를
  선언(spg·ioc·rcl·egress·cur·rlp 선례).
- **coordinate 비붕괴(설계 #4 §4.4)**: mutable lifecycle 좌표(decision `single_use_consumed`·request/active-set
  state·주입 verdict[hag/spg/evidence/egress])는 covered digest에 **미포함** — 정당한 전이(consume/revoke/expire)가
  digest를 바꿔 same-id/different-bytes CRITICAL_CONFLICT로 오탐되지 않도록. 현재 상태는 술어에 주입·별도 append-only
  record.
- **malformed-model 자기방어 — positive-claim + incomplete-scope coexistence seal(RLP `ExactTrialPlan`·egress QCC
  `_trial_claim_completeness` 동형·본 문서 핵심 seal)**: `SafetyDeviationRequest`/`SafetyDeviationDecision`
  `model_validator`가 **불완전 scope와 "eligible" 주장의 공존을 구조로 봉인**. `result is
  DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`인데 §10 mandated scope 차원 중 하나라도 `None`/wildcard이면
  **`ArtifactIntegrityError` at construction** — 즉 "eligible"을 주장하면서 exact scope가 비는 decision은 **애초에
  구성 불가**. 동일하게 `SafetyDeviationRequest`(non-waivable classification `WAIVABLE_ELIGIBLE` 주장 + boundary-hit
  차원 공존 ⇒ unconstructable)·`ResidualRiskAcceptanceRecord`(accepted 주장 + compensating-control 부재 ⇒
  unconstructable). 술어 층에서 validator 통과 후 재확인(defense-in-depth·`model_construct` 우회 대비·2층).
  **리뷰어 공격 지점(§10.2-⑦)**: `model_construct`로 malformed request 구성 → validator + 술어 2층 봉인.
- **`_REQUIRED_COVERED`는 구조 identity/generation/digest만** — duration·decision-age·quorum N·review-interval 같은
  numeric bound은 제외(Phase-1 null profile 하에서 아티팩트 구성 가능하도록·§8); 누락 numeric claim은 fail-closed(§4.2).

### 2.4 핵심 모델 필드 골격 (§ref·형제 seam·all-false)

**`SafetyDeviationPolicy`(§5.1/§9)** — immutable ADR-002-014 governed policy content model. 필드: `policy_id`(독립
id)·`policy_generation`·`policy_digest`·`eligible_deviation_classes: frozenset[str]`·`prohibited_deviation_classes:
frozenset[str]`·`non_waivable_boundary: NonWaivableBoundaryAnchor`(§8 15-item·정책은 추가만·§5.6 "cannot remove")·
`scope_dimensions: frozenset[ScopeDimension]`(§5.7 21-dimension catalogue)·`required_compensating_control_classes`·
`required_evidence_levels`·`effective_principal_quorum_rule`(hag 참조)·`max_duration`·`max_decision_age`·
`max_review_interval`·`compatibility_manifest_digest`·`authority_effect: AllFalseDeviationAuthority`. **활성화/generation은
spg/014 주입**(§0.4c·§9 line 275). `_REQUIRED_COVERED` = {policy_id·policy_generation·policy_digest}.

**`SafetyDeviationRequest`(§5.2/§10)** — immutable proposal(§10 line 281-297 전 필드군). 필드(전부 주입·검증 대상):
- **identity/policy**: `request_id`(독립 id)·`request_version`·`request_digest`·`predecessor_request_id`·`policy_id`·
  `policy_generation`·`policy_digest`·`compatibility_manifest_digest`(§10 line 283-284).
- **requirement/hazard**(§10 line 285): `requirement_ids: tuple[str, ...]`·`hazard_ids: tuple[str, ...]`·
  `adr_rfc_citations`·`verification_ids`·`non_waivable_classification: NonWaivableClassification`(§8 판정 결과).
- **status(no relabel)**(§10 line 286): `current_requirement_status: WaivedEvidenceStatus`·`current_evidence_status:
  WaivedEvidenceStatus`(§19 non-PASS 유지).
- **scope/closure**(§10 line 287): `deviation_scope: DeviationScope`·`dependency_closure: DeviationDependencyClosure`.
- **cause/remediation**(§10 line 288): `technical_cause`·`why_control_unavailable`·`remediation_plan`.
- **time**(§10 line 289·time 주입): `requested_start`·`hard_expiry`·`review_interval`·`trustworthy_time_basis`.
- **worst-credible risk**(§10 line 290): `worst_credible_effect_envelope`(rcl worst-effect 좌표·주입 opaque·§0.4g·
  **CapacityVector 타입 아님**)·`common_mode_risk`.
- **assumptions**(§10 line 291): `assumptions`·`uncertainties`·`unsupported_semantics`·`failure_modes`.
- **compensating controls**(§10 line 292): `compensating_controls: tuple[CompensatingControl, ...]`·`control_owners`·
  `control_evidence`·`control_independence`·`control_currentness`.
- **envelope/profile**(§10 line 293·spg 주입): `hard_safety_envelope_ref`·`requested_reduced_profile`.
- **constraints**(§10 line 294): `capacity_constraints`·`protective_constraints`·`action_flow_constraints`·
  `supervision_constraints`·`evidence_constraints`·`recovery_constraints`.
- **behavior**(§10 line 295): `revocation_behavior`·`halt_behavior`·`egress_deny_behavior`·`rollback_behavior`·
  `reconciliation_behavior`·`trapped_exposure_behavior`.
- **principals**(§10 line 296): `requester`·`implementer`·`beneficiaries`·`evidence_owners`·`reviewers`·`conflict_graph`.
- **inferences**(§10 line 297): `prohibited_inferences`·`non_waivable_classification_result`.
- **polarity 필드**(§4.3): `applicability_resolved: bool | None`(양극성)·`scope_wildcard: bool | None`(음극성)·
  `scope_patched`/`scope_widened`/`scope_stale`/`scope_conflicting: bool | None`(음극성)·`materiality_unknown:
  bool | None`(음극성 — §9 line 273 "Unknown materiality is material").
- `authority_effect: AllFalseDeviationAuthority`. `_REQUIRED_COVERED` = {request_id·request_version·request_digest·
  policy_id·policy_generation}. malformed-model validator: `WAIVABLE_ELIGIBLE` + boundary-hit/incomplete scope ⇒
  `ArtifactIntegrityError`(§2.3).

**`DeviationScope`(value·§5.7)** — exact scope tuple(§5.7 line 128 전 21 차원): `environment`·`safety_cell`·
`capacity_domain`·`legal_portfolio`·`account`·`broker`·`venue`·`instrument`·`strategy`·`action_class`·`software`·
`configuration`·`identity`·`route`·`session`·`failure_domain`·`time_interval`·`evidence`·`requirement`·`hazard`·
`dependency_closure`. 각 `str | None`; `None`/wildcard ⇒ `no_wildcard_scope` 실패(§5.2). **`ScopeDimension` enum
(closed StrEnum)**은 이 차원의 식별자군(manually-transcribed anchor·§5.7 line 128 = 참조집합·§7.2 drift property·
cur `DimensionKey` 선례). **숫자 하드코딩 아님**(구조 dimension identifier).

**`SafetyDeviationDecision`(§5.3/§12)** — immutable single-use. 필드: `decision_id`(독립 id)·`decision_generation`·
`decision_digest`·`request_id`·`request_digest`(§12 line 356 "bind the exact request digest")·`deviation_generation`·
`accepted_residual_risk_id`·`reduced_scope: DeviationScope`·`compensating_controls`·`evidence_refs`·`reviewer_quorum`
(hag 주입)·`effective_principal_verdict: bool | None`(hag 주입·양극성)·`expiry`·`policy_id`·`result: DecisionResult`·
`single_use_consumed: bool | None`(음극성·§13 line 368 "consumed exactly once")·`authority_effect:
AllFalseDeviationAuthority`. `_REQUIRED_COVERED` = {decision_id·decision_generation·request_id·request_digest·
deviation_generation}. malformed-model validator: `result is ELIGIBLE` + incomplete reduced_scope ⇒ error(§2.3).

**`ResidualRiskAcceptanceRecord`(§5.4/§11)** — immutable accepted-risk record. 필드: `acceptance_id`(독립 id)·
`acceptance_generation`·`acceptance_digest`·`request_id`·`bounded_risk`·`assumptions`·`compensating_controls:
tuple[CompensatingControl, ...]`·`reviewers`(hag 주입)·`expiry`·`evidence_status: WaivedEvidenceStatus`·
`explicit_scope: DeviationScope`·`within_hard_safety_envelope: bool | None`(spg 주입·양극성·§11 line 333)·
`authority_effect: AllFalseDeviationAuthority`. **§5.4 verbatim "It is not proof that the underlying requirement
passed and grants no authority"**·all-false. `_REQUIRED_COVERED` = {acceptance_id·acceptance_generation·request_id}.
malformed-model validator: accepted 주장 + compensating_controls ∅ ⇒ error(§2.3).

**`CompensatingControl`(value·§5.5/§11)**: `control_id`·`kind: CompensatingControlKind`·`is_preventive_or_containment:
bool | None`(양극성·§11 item 1)·`owner`·`scope`·`state_machine`·`currentness_rule`·`failure_response`·
`objective_evidence: bool | None`(양극성·§11 item 3)·`fails_closed: bool | None`(양극성·§11 item 4)·
`independent_of_failed_control: bool | None`(양극성·§11 item 5)·`observation_only: bool | None`(음극성·§11 item 8
"not rely solely on documentation, alerting, replay, operator attention, expected broker rejection, or priority").
§5.5 verbatim "A document, alert, dashboard, audit, replay, priority label, or operator promise is **not by
itself** a compensating control." `compensating_control_not_observation`(§6.1)이 소비.

**`ActiveDeviationSet`(§5.9/§13)** — immutable canonical combined set. 필드: `active_set_id`(독립 id)·
`active_set_generation`·`active_set_digest`·`configuration_bundle_digest`·`deviation_generation`·`member_decisions:
tuple[str, ...]`(전 applicable decision id)·`member_digests: tuple[str, ...]`·`is_complete: bool | None`(양극성·§13
line 364 "one complete canonical set")·`combined_within_envelope: bool | None`(spg 주입·양극성·§13 item 3)·
`state: ActiveDeviationState`·`authority_effect: AllFalseDeviationAuthority`. §13 line 364 "Absence of the set, an
omitted applicable deviation, mixed generation, or conflicting digest is **invalid configuration**"·§13 line 380
"No consumer may locally combine decisions … or choose a more permissive interpretation"(WDR-INV-006 no-union).
`_REQUIRED_COVERED` = {active_set_id·active_set_generation·deviation_generation·configuration_bundle_digest}.

**`NonWaivableBoundaryAnchor`(value·§5.6/§8)** — 15-item union anchor(§8 line 234-248 손전사). 필드:
`rfc_000_constitutional`·`rfc_001_no_waiver_set`·`fail_closed_unknown`·`rcl_exclusivity`·`egress_final_enforcement`·
`generation_fencing`·`broker_finality_semantics`·`economic_continuity`·`hard_safety_envelope`·`independent_halt`·
`live_nonlive_segregation`·`priority_not_capacity`·`docs_not_prevention`·`no_auto_rearm`·`this_adr_rules` — 전부
frozenset[str] 또는 bool 참조집합. **§5.6 "Policy may add prohibitions but cannot remove them"** ⇒ boundary는
UNION-only(§5.1 `boundary_is_union_only`). **manually-transcribed anchor**: 15-item 집합은 §8 line 234-248 verbatim
전사(§7.2 drift property·§부록 C).

**`GateSeparationLadder`(value·§26 AC-012/§28)** — distinct explicit 상태(§26 line 685-687·§28 gate 목록):
`adr_accepted: bool | None`·`deviation_eligible: bool | None`·`configuration_activated: bool | None`·
`live_authorized: bool | None`·`restricted_live_ready: bool | None`·`production_ready: bool | None` +
`authority_effect: AllFalseDeviationAuthority`. 각 독립 bool(주입) — 상호 함의 없음(§5.5). §26 AC-012 line 687
verbatim: "ADR acceptance, deviation eligibility, configuration activation, Live Authorization, restricted-live
readiness, and production readiness remain **distinct states**." **manually-transcribed anchor**(§7.2 drift).

**`AllFalseDeviationAuthority`(all-false·§6.2·WDR-INV-001/§7)**: `creates_capacity: bool = False`·`creates_protection:
bool = False`·`creates_safety_authority: bool = False`·`issues_live_authorization: bool = False`·`creates_capability:
bool = False`·`transmits: bool = False`·`clears_halt: bool = False`·`creates_production_scope: bool = False`·
`re_arms: bool = False`·`grants_broker_permission: bool = False`·`classifies_protection: bool = False`.
`model_validator` any-True ⇒ `ArtifactIntegrityError`(rcl `AllFalseAuthority`·egress `AllFalseEgressAuthority`·cur
`AllFalseCurrentnessAuthority`·rlp `AllFalseTrialAuthority` 동형·**로컬 재표현·import 아님**). **근거**: WDR-INV-001
line 148 verbatim: "Policy, request, decision, acceptance, review, ticket, evidence, and active-set artifacts create
**no** capacity, protection, Safety Authority, Live Authorization, capability, transmission, HALT clear, production
scope, or re-arm authority." + §1 line 21 "broker permission, protective classification" 추가.

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계

### 3.1 canonical REUSE

`tos.canonical` **REUSE**(import): `IndependentIdArtifact`(id ⊥ digest base·`_base.py:328`)·`classify_record_pair`+
`RecordPairKind`{IDEMPOTENT_DUP/CRITICAL_CONFLICT/DIVERGENT_EMISSION/DISTINCT/NOT_COMPARABLE}(`record_pair.py:31/52`·
policy/request/decision/acceptance/active-set의 append-only 무결성·same-id/different-bytes 탐지)·`CanonicalDecimal`
(worst-credible envelope digest용·필요 시)·`FrozenModel`·`EVL1ProvisionalCanonicalizer`(digest 결정론). **canonical만이
base 의존**(rcl/ioc/evidence/capsule/egress/cur/rlp 선례 동형). **주의**: pre-issuance(digest None) 아티팩트는
`classify_record_pair`가 `NOT_COMPARABLE`로 분류(false conflict 방지·canonical MINOR-1 discipline·`record_pair.py`
"either digest None … => NOT_COMPARABLE"). revocation-vs-send 런타임 race 탐지는 +Security(WDR-EV-006).

### 3.2 ordering REUSE (Deviation Generation·generation floor)

`tos.ordering` **REUSE**(import·`compare_order`): policy/request/decision/acceptance/active-set generation 순서·
**Deviation Generation** monotonic fence(§5.8·§14 line 386)·predecessor floor(§10 line 284)·authority epoch `>=`
shape REUSE(§0.4h·non-revival). **PROMOTE 0**(신규 core 승격 없음 — canonical/ordering이 충분·cur/rlp 선례).
Deviation Generation(§5.8)은 ordering identity이지 wall-clock 아님 — WDR는 clock-free(`MAX_deviation_*_ms`
wall-clock age는 secondary +Security/INSTANCE·§8).

### 3.3 REUSE 요약 표

| 대상 | 결정 | 근거 |
|---|---|---|
| `tos.canonical`(IndependentIdArtifact·classify_record_pair·RecordPairKind·CanonicalDecimal·FrozenModel·EVL1ProvisionalCanonicalizer) | **REUSE (import)** | base digest substrate·replay/substitution 구조 분류·전 시리즈 선례 |
| `tos.ordering`(compare_order·Ordering·OrderingEvent) | **REUSE (import)** | Deviation Generation floor·predecessor·monotonic fence·authority 선례 |
| 형제 tos 패키지 전부(rcl·spg·hag·iap·egress·cur·evidence·liveauth·authority·time·ioc·are·afg·sbr·capsule·venue·protective·recon·brokercap·orthostate·dsl·nontrade·replacement·posttrade·rlp + 미래 sir/stm/sci/ptf) | **NO import (sibling edge 0)** | 형제 상호작용은 주입 scalar/digest/bool/verdict/enum-token으로만(§3.4). **rcl edge 0 판정: §0.4g**(WDR은 capacity 산술 미수행) |
| `_NonTruthyStrEnum` | **로컬 재표현 (import 아님)** | iap `ApprovalResult`(vocabulary.py:50)·cur `ProofResult` 선례 — 각 패키지 로컬 정의 |
| `AllFalseDeviationAuthority` | **로컬 재표현 (import 아님)** | rcl/egress/cur/rlp `AllFalse*Authority` 선례 |
| iap single-use consumption *shape* | **로컬 재표현 (import 아님)** | `deviation_single_use_non_authorizing`가 iap shape REUSE(§0.4h·§6.3) |
| `WaivedEvidenceStatus` (register verification-status honesty) | **WDR 로컬 저작** | **실측 tos.evidence 미소유**(§0.4d·seam 충돌 0) |

### 3.4 sibling edge 0 정책

WDR는 **어떤 형제 tos 패키지도 import하지 않는다.** 형제/미착지 owner의 verdict/generation/digest는 전부 **주입
좌표**(scalar/digest/bool/verdict/enum-token). 이는 (a) **계층 분리**: WDR content 생산 → cur/egress boundary 소비
(향후·§3.5), (b) firewall allowlist(`closure ⊆ {canonical, ordering, wdr}`·§7.1), (c) **rcl edge 회피**(§0.4g —
WDR은 capacity 산술 미수행·worst-credible envelope는 주입 opaque·are/ioc/afg가 CapacityVector 타입 산술을 위해
edge를 취한 것과 대비)를 강제한다. **PROMOTE 0**(canonical/ordering 외 신규 core 없음).

### 3.5 소유권 / seam 분할표 (본 문서 최대 함정 — 코드 실측)

| deviation/governance 관련 아티팩트/술어 | 소유 (실측) | WDR 관계 (재저작 금지) |
|---|---|---|
| spg Hard Safety Envelope·Runtime Safety Profile·`profile_within_envelope`(`predicates.py:142`)·`bundle_complete`·break-before-make(`records.py:284,293`)·`residual_risk_ceiling`(`records.py:370`) | **spg (#12·ADR-002-014)** | spg = **profile-level envelope/ceiling/activation**. WDR = per-deviation `ResidualRiskAcceptanceRecord`(§5.4)·envelope 봉입은 spg 주입 verdict·재저작 안 함(§0.4c) |
| hag `effective_principal_collapse`·`quorum_independence_satisfied`·`quorum_for` | **hag (#20·ADR-002-015)** | human-authority 일반 모델. WDR = collapse/quorum verdict **주입 소비**·WDR-EV-004 L2+(§0.4e) |
| rcl `CapacityVector`·`within_limits`·worst-credible-effect·commit-proof(`vector.py:74`·`predicates.py:78`) | **rcl** | §7 "RCL only"·§7 line 217 "never capacity". WDR budget/accepted-risk ≠ capacity·worst-effect envelope는 **주입 opaque 좌표**·**edge 0**(§0.4g)·계산 +Broker |
| egress final-egress enforcement·per-action currentness verification | **egress (#22)** | §14 final egress·WDR-INV-013 "deviation services hold neither authority". WDR 주입·재저작 안 함·deviation service no-route(§6.6) |
| cur Safety Currentness Vector completeness·`DimensionKey` | **cur (#23·ADR-002-024)** | §14 line 386 "Deviation Generation … SHALL be owner facts in the ADR-002-024 Safety Currentness Vector". WDR = **Deviation Generation 생산**(하류 cur 소비·forward 관계)·cur vector-completeness 재저작 안 함. **cur는 현재 deviation 차원 미소유**(RLP와 대비·이연 seam 0·§0.4b) |
| evidence `SegmentCommitmentScheme`·`causal_chain_complete`·gap machine·`GapStatus`·`ReceiptVerificationStatus` | **evidence (ADR-002-016)** | custody + 무결성. WDR = causal_chain_complete/gap-status **주입 소비**. **단 register verification-status honesty 어휘(`WaivedEvidenceStatus`)는 WDR-owned**(evidence 미소유·§0.4d) |
| liveauth Live Authorization generation | **liveauth (ADR-002-007)** | §7 line 219 Live Auth. WDR 주입 소비·발급 안 함(WDR-INV-001) |
| iap `single_use`/`exact_intent_only`·consume gate(`predicates.py:176/230`) | **iap (#15)** | **single-use consumption shape 선례**. `deviation_single_use_non_authorizing`가 REUSE(재저작 아님·§6.3) |
| authority `authority_epoch_current`(`>=`)·`recovery_generation_revives_nothing` | **authority (ADR-002-003)** | floor `>=` shape·non-revival 선례(compare_order REUSE·§0.4h) |
| 027 incident generation(미착지) | **미착지 owner (-027)** | WDR = generation/digest 좌표 주입 소비·**내용 재판정 금지(phantom·§0.4f)** |

---

## 4. 술어 규율 (canary·극성·reconcile·집합)

### 4.1 금지 동사 canary (`test_wdr_void_canaries.py`)

WDR 모듈은 **순수·비전송·비변이·clock-free**임을 정적 회귀로 봉인한다: `tos/src/tos/wdr/**`에 `send`/`transmit`/
`emit`/`sign`/`arm`/`rearm`(실행)·`mutate`/`reserve`/`release`/`transfer`/`commit_capacity`(capacity)·`approve`/
`authorize`/`activate`(실행 승인·**WDR는 deviation *구조 판정*만·실 승인/활성화 아님**)·`clear_halt`·`open`/`connect`/
`socket`·`time.time`/`datetime.now`/`monotonic`(clock)·`os.environ`·`exec`/`eval`/`importlib`/`__import__` 문자열이
**부재**함을 grep 회귀로 확인(egress/cur/rlp `test_*_void_canaries.py` 동형). deviation artifact가 authority를
생성하지 않음을 코드 수준에서 증언(WDR-INV-001).

### 4.2 truthy-sentinel 봉인 (`test_wdr_truthy_sentinel.py`)

`DecisionResult`·`NonWaivableClassification`·`RequestState`·`ActiveDeviationState`·`WaivedEvidenceStatus`는
`_NonTruthyStrEnum`(`__bool__ ⇒ TypeError`). 회귀: 각 멤버에 `bool(x)`가 `TypeError`; 소비 게이트는 `result is
DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`·`classification is NonWaivableClassification.WAIVABLE_ELIGIBLE`
명시 비교만 사용(`if result:`/`if classification:` 부재 grep). `DENY`/`HOLD`/`NON_WAIVABLE`/`UNRESOLVED`/`REVOKED`/
`FAIL`을 truthy로 오독하는 fail-open 방지. **`WaivedEvidenceStatus.PASS`는 멤버이나 truthy-untestable** — deviation
존재⇒PASS flip은 술어(`evidence_status_honest`)가 금지(§5.4).

### 4.3 극성 규율 (§4.2 — #18/#22/#23/#25 재발 방지·전수 점검)

**핵심 교훈(#18/#22 MAJOR-2·#23/#25 상속)**: `bool | None` 필드에 `if field:`/`if not field:`를 쓰면 `None`이
극성에 따라 **fail-open**한다. 모든 필드는 **극성을 명시**하고 정규화한다. **규율(task 명시)**: **음극성 소비의
allow/clear 조건은 `is False`만 사용하고 `is not True`를 절대 쓰지 않는다**(`x is not True`는 `None`을 clear로
오독하는 fail-open — #18/#22/#23/#25 재발 결함). 양극성 allow는 `is True`. `None`은 **양쪽 극성 모두에서 UNKNOWN
⇒ deny**로 수렴. deny 정규화: 양극성 `is not True`·음극성 `is not False`(둘 다 None ⇒ deny).

| 필드 | 극성 | clear(allow) 조건 | deny 조건 | deny 정규화 | 근거 |
|---|---|---|---|---|---|
| `applicability_resolved` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §8 line 252·§9 line 273 "Unknown applicability … denies" |
| `independently_reviewed`(hag) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §12·WDR-INV-007 |
| `effective_principal_verdict`(hag 주입) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §12·WDR-INV-007(hag 소유) |
| `within_hard_safety_envelope`(spg 주입) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §11 line 333·§13 item 3(spg 소유) |
| `is_preventive_or_containment` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §11 item 1·§5.5 |
| `objective_evidence` / `fails_closed` / `independent_of_failed_control` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §11 item 3/4/5 |
| `causal_chain_complete`(evidence 주입) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §19(evidence 소유) |
| `exact_current_decision_present` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ non-waived` | §19 line 488(WAIVED 게이트) |
| `is_complete`(active set) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ invalid config` | §13 line 364 |
| `single_use_consumed` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ reject reuse` | §13 line 368·WDR-INV-008 "consumed exactly once" |
| `is_expired` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ future-use deny`(capacity 불변·§6.5) | §15·WDR-INV-009/012 |
| `is_revoked` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §14·§15·WDR-INV-009 |
| `scope_wildcard` / `scope_patched` / `scope_widened` / `scope_stale` / `scope_conflicting` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §10 line 299·WDR-INV-003 |
| `common_mode_present` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §11·§12·WDR-INV-006 |
| `materiality_unknown` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ material(deny)` | §9 line 273 "Unknown materiality is material" |
| `broker_state_unknown` / `order_state_unknown` / `exposure_unknown` / `residual_risk_unknown` / `control_state_unknown` / `evidence_unknown` / `scope_unknown` / `currentness_unknown` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny + confine` | §16 line 423-431·WDR-INV-010 |
| `observation_only`(compensating) | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ not-a-control` | §5.5·§11 item 8 |
| `re_armed` / `self_reverted` / `recovered_without_fresh_chain` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny`(non-revival) | §18·WDR-INV-014/015 |

**전수 점검 회귀(`test_wdr_polarity.py`)**: 모든 음극성 필드에 대해 `None` 입력이 **restricted/deny로 수렴**함을
property test(hypothesis)로 확인 — `single_use_consumed=None`이 "not consumed"로 fail-open하거나 `is_expired=None`이
"not expired"로 fail-open하거나 `broker_state_unknown=None`이 "known"으로 fail-open하는 #18/#22 MAJOR-2 재발을 구조적
봉인. **`is not True`가 음극성 필드 소비에 나타나지 않음을 grep 회귀로 강제**(task 명시 규율). 모든 양극성 필드에
대해 `None`/`False`가 deny로 수렴.

### 4.4 그룹 reconcile 규율 (#22 MAJOR-1 재발 방지 — 전-entry 보수·no-permissive-union·WDR-INV-006)

**핵심 교훈(#22 MAJOR-1)**: 여러 entry가 한 그룹/set에 매핑될 때 판정은 **첫-entry가 아니라 전-entry를 보수적으로
reconcile**해야 한다. WDR의 reconcile 지점(§13 combined Active Deviation Set이 특히 강·WDR-INV-006):

- **`combined_set_no_permissive_union`(§5.5·§13 line 380·WDR-INV-006 line 166-168)**: 여러 개별 승인된 deviation을
  **union하지 않음**(§13 line 380 verbatim: "No consumer may locally combine decisions, ignore an active deviation,
  restore a predecessor set, or **choose a more permissive interpretation**"·WDR-INV-006 "Separate approvals cannot
  be unioned to create broader permission"). 결합은 교집합/최협(any-narrow-wins) 방향만·첫-decision 채택 아님.
- **`omitted_deviation_invalidates`(§13 line 364)**: applicable deviation 하나라도 누락 ⇒ **invalid configuration**
  (§13 line 364 "an omitted applicable deviation, mixed generation, or conflicting digest is invalid
  configuration"). entry 순서 무관·누락 하나라도 ⇒ deny.
- **Deviation Generation floor(§5.8·§14)**: 여러 generation entry ⇒ **MAX(최신 fence)** 채택(§1 line 29 "a newer
  generation SHALL restrict future authority monotonically"·§14 line 398 "SHALL advance a restrictive floor for
  the complete affected dependency closure")·첫-generation 아님.
- **`boundary_is_union_only`(§5.6·§8 line 250)**: Non-Waivable Boundary는 **정책이 추가만** 가능(§8 line 250 "It
  cannot make this list smaller")·boundary 축소 방향 union은 금지(any-add-wins).

**회귀(`test_wdr_reconcile.py`)**: entry/decision 순서 permutation에 대해 verdict 불변(순서 독립) + 가장 restrictive
(any-narrow-wins·omitted⇒invalid·MAX-generation·boundary union-only) 지배를 property test로 확인. **∅ 가드(v1.1·
§13 line 364 정합)**: member_decisions ∅ + applicable_decision_ids **비-∅** + is_complete 주장 ⇒ invalid(누락
차단); **applicable=∅ + members=∅ + is_complete=True ⇒ 유효**(explicit empty Active Deviation Set — 이를
거부하는 구현/테스트는 결함); applicable=∅ + members 비-∅ ⇒ invalid(surplus).

---

## 5. 핵심 L1 술어 (§5 — 5 노른자 + 지지)

> 전 술어 규율 태그: **boundary/completeness/polarity/separation predicate substrate only; WDR-EV-001/002/007/010/012
> 전부 NOT_IMPLEMENTED(001/007/012는 +Security/+Broker 잔여·전 행 `/3` 통합·adversarial 대기). 전 owner verdict/
> generation/digest는 주입. L1은 boundary/scope/UNKNOWN/status/set/gate 구조 판정만.**

### 5.1 `boundary_denies_non_waivable` (WDR-EV-001 노른자·§8·+Security 잔여)

**시그니처(계약)**: `boundary_denies_non_waivable(request: SafetyDeviationRequest | None, boundary:
NonWaivableBoundaryAnchor | None) -> bool` — **`True` = 요청이 boundary 밖이라 진행 가능**, `False` = deny(boundary
내부 또는 판정 불가).

**판정(전부 AND·fail-closed)**:
1. **∅-seal 양방향**: `request is None` 또는 `boundary is None` 또는 boundary의 15-item 참조집합이 anchor 미달
   (∅) ⇒ `False`(**absent boundary에 대해 진행을 vacuously 허용하지 않음**·§8 line 234 "At minimum, no deviation
   may waive …"). boundary가 15-item anchor 미달이면 ⇒ `False`(축소된 boundary는 위조).
2. **classification admissible(truthy 봉인)**: `request.non_waivable_classification is
   NonWaivableClassification.WAIVABLE_ELIGIBLE`(§4.2). `NON_WAIVABLE`/`UNRESOLVED` ⇒ deny(§8 line 252 "unresolved …
   treated as non-waivable").
3. **applicability resolved(양극성)**: `request.applicability_resolved is True`(§4.3). `None`/`False` ⇒ deny
   (§9 line 273 "Unknown applicability … denies").
4. **boundary hit 부재**: request의 targeted requirement가 15-item anchor 중 어느 것에도 hit하지 않음. 하나라도
   hit(RFC-000·RFC-001 no-waiver set·fail-closed·RCL exclusivity·egress final·fencing·broker-finality·economic
   continuity·Hard Safety Envelope·independent HALT·live/non-live segregation·priority≠capacity·docs≠prevention·
   no-auto-rearm·this-ADR rules) ⇒ deny(§8 line 234-248·WDR-INV-002).
5. **`boundary_is_union_only`(§5.6·§8 line 250)**: 정책이 anchor를 축소하지 않았음(정책 추가는 허용·축소는 위조·
   any-add-wins·§4.4). 축소 감지 ⇒ deny.

**반환**: 위 전부 성립시에만 `True`. **WDR-EV-001을 닫지 않음**(`/3` 통합 + **+Security classification-manipulation
저항** 잔여 — 실 "한 사람 두 계정" 류 boundary 우회 저항은 +Security 런타임·hag). enum-drift: 15-item anchor ==
`NonWaivableBoundaryAnchor` 필드집합(§7.2 drift property·§부록 C).

### 5.2 `scope_exact_and_complete` (WDR-EV-002 노른자·§10·§5.10·가장 깨끗한 L1)

**`mandated_scope` floor 고정(cur v1.1 MINOR-1·RLP §5.1 선례)**: `mandated_scope` 파라미터는 자유 주입이 아니라
**전 `ScopeDimension` 멤버(= §5.7 21-dimension floor)를 기본 하한**으로 하며 caller는 이보다 좁힐 수 없다(policy는
위로 추가만·"at least" 방향·cur `MANDATED_DIMENSION_FLOOR` 동형).

**시그니처**: `scope_exact_and_complete(request: SafetyDeviationRequest | None, mandated_scope:
frozenset[ScopeDimension]) -> bool`. **가장 깨끗한 L1 슬라이스**(pure `EV-L1/3`·좌표 태그 0·survey line 248).

**판정(전부 AND·fail-closed)**:
1. **∅-seal 양방향**: `request is None` 또는 `mandated_scope` ∅ ⇒ `False`. request scope 차원 ∅인데 mandated
   비어있지 않으면 ⇒ `False`(§10 line 299 "A request with missing … fields is ineligible").
2. **전 scope 차원 present + concrete**: `mandated_scope ⊆ {d for d in request.deviation_scope if concrete(d)}`
   (§5.7). **집합 양방향**: mandated ⊄ present ⇒ deny(§5.7 21-dimension floor 미달). 미표현 차원 ⇒ incomplete ⇒
   deny(egress QCC coexistence seal·spg `bundle_complete` 동형·vacuous-True 차단).
3. **no wildcard/inferred/patched/widened/stale/conflicting(음극성 전수)**: `request.scope_wildcard is False` AND
   `scope_patched is False` AND `scope_widened is False` AND `scope_stale is False` AND `scope_conflicting is
   False`(§4.3·§10 line 299 "missing, wildcard, inferred, stale, conflicting, unbounded, wrong-environment, or
   post-review fields is ineligible"·WDR-INV-003). **음극성 소비는 `is False`만**(task 규율·None ⇒ deny).
4. **dependency closure complete**: `dependency_closure_complete(request)` — §5.10 전 affected component/artifact/
   account/limit/authority/capacity/credential/route/failure-domain/economic-effect/verification/downstream이 closure에
   present(§10 line 287·§5.10 line 138-140). ∅ closure인데 scope non-trivial ⇒ deny.
5. **materiality/applicability 보수**: `materiality_unknown is False`(음극성·§9 line 273 "Unknown materiality is
   material") AND `applicability_resolved is True`(양극성).

**반환**: 위 전부 성립시에만 `True`. **WDR-EV-002를 닫지 않음**(`/3` 잔여·순수 `EV-L1/3`이나 integration은 Phase-1
밖). **exactness 정직 명기(#25 MAJOR-1 교훈)**: 문자열 scope denylist(`scope_wildcard` 감지 등)는 **비전수**임을
정직 표기 — `no_wildcard_scope`는 `*`/`latest`/null-as-scope/알려진 inferred sentinel만 거부하며 strip+casefold
정규화·메타문자 거부 후에도 **신종 wildcard 표기는 +Security/런타임 소유**(§10.2-⑧).

### 5.3 `unknown_denies_and_confines` (WDR-EV-007 노른자·§16·+Broker 잔여·극성 봉합)

**시그니처**: `unknown_denies_and_confines(request: SafetyDeviationRequest | None, budget_authority:
AllFalseDeviationAuthority | None) -> bool` — **`True` = 진행 가능(전 상태 known + budget≠capacity + no protective
bypass)**, `False` = deny + confine.

**판정(전부 AND·fail-closed)**:
1. **∅-seal**: `request is None` 또는 `budget_authority is None` ⇒ `False`.
2. **UNKNOWN 전수 극성(음극성·핵심)**: `broker_state_unknown`·`order_state_unknown`·`exposure_unknown`·
   `residual_risk_unknown`·`control_state_unknown`·`evidence_unknown`·`scope_unknown`·`currentness_unknown`·
   `materiality_unknown` 전부 `is False`(§4.3·§16 line 423-431·WDR-INV-010 line 182 "Unknown applicability, broker
   state, order state, exposure, residual risk, compensating-control state, evidence, scope, or currentness blocks
   new risk"). **하나라도 `is not False`(True 또는 None) ⇒ deny + confine**(worst-credible capacity-covered·주입).
   **음극성 소비는 `is False`만**(task 규율).
3. **`budget_is_not_capacity`(all-false·§7 line 217)**: `budget_authority`의 `creates_capacity is False` AND
   전 all-false 필드 False(§6.2). deviation budget/accepted-risk는 capacity 불변(§10 대응·§16 line 434 "accepted
   residual risk cannot free UNKNOWN capacity"). worst-credible-effect envelope는 주입 opaque 좌표(§0.4g·CapacityVector
   타입 아님)·**계산은 rcl + +Broker**.
4. **`protective_label_no_bypass`(§11 line 331·§17 line 442)**: protective/exit/hedge/close/cancel/replace/recovery/
   emergency 라벨이 Non-Waivable Boundary·venue·broker·economic·capacity·authority·final-egress 검사를 bypass하지
   않음(§17 line 442). protective priority가 broker/RCL protective capacity를 create하지 않음(§11 line 331 "Protective
   priority does not create broker or RCL protective capacity").

**반환**: 위 전부 성립시에만 `True`. **WDR-EV-007을 닫지 않음**(`/3` 통합 + **+Broker worst-credible 정량화** 잔여 —
실 worst-credible-effect 계산·RCL capacity 소비는 rcl + +Broker·§28 gate 8). UNKNOWN⇒capacity-covered의 실 소비는
rcl 주입.

### 5.4 `evidence_status_honest` (WDR-EV-010 노른자·§19·approval≠verification·WDR-owned 어휘)

**시그니처**: `evidence_status_honest(item: WaivedEvidenceItem | None) -> bool` — **`True` = status가 정직**(deviation
존재가 PASS를 조작하지 않음), `False` = 부정직/판정 불가. `WaivedEvidenceItem`은 `measured_status:
WaivedEvidenceStatus`·`deviation_exists: bool | None`·`exact_current_decision_present: bool | None`(양극성)·
`reduced_scope_present`·`compensation_present`·`review_record_present: bool | None`(양극성)·`relabeled_status:
WaivedEvidenceStatus | None`을 담는 value view.

**판정(전부 AND·fail-closed)**:
1. **∅-seal**: `item is None` ⇒ `False`.
2. **no PASS relabel via deviation(핵심·WDR-INV-004)**: `item.deviation_exists`가 `is not False`(존재 또는 None)
   인데 `item.relabeled_status is WaivedEvidenceStatus.PASS`(또는 ACCEPTED) ⇒ **deny**(§19 line 490 "It SHALL NOT
   be relabeled `PASS`, `ACCEPTED`, or completed merely because a deviation exists"·WDR-INV-004 line 158 "An
   accepted residual risk does not convert an unmet, failed, missing, inconclusive, or expired verification item
   to `PASS`").
3. **measured status 가시성 유지**: `measured_status`가 {NOT_IMPLEMENTED·FAIL·INCONCLUSIVE·BLOCKED·EXPIRED} 중
   하나이면 relabel은 그 값을 벗어날 수 없음(historical failure 가시·§19 line 490 "Historical failures … remain
   visible"). measured=FAIL인데 relabeled≠FAIL/WAIVED ⇒ deny.
4. **`WAIVED_WITH_RESIDUAL_RISK`는 exact-current 조건에서만(§19 line 488)**: `measured_status is
   WaivedEvidenceStatus.WAIVED_WITH_RESIDUAL_RISK` ⇒ `item.exact_current_decision_present is True` AND
   `reduced_scope_present is True` AND `compensation_present is True` AND `review_record_present is True`(전 양극성·
   `is not True` ⇒ deny). 하나라도 미달 ⇒ deny(WAIVED 주장 무효).
5. **truthy 봉인**: 모든 status 비교는 `is` 명시(§4.2·`WaivedEvidenceStatus.PASS` truthy-untestable).

**반환**: 위 전부 성립시에만 `True`. **WDR-EV-010을 닫지 않음**(`/3` 잔여). **지지 술어 `approval_is_not_verification`**:
decision `ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`이 verification item을 `PASS`로 만들지 않음(§1 line 25 "The affected
verification item remains visibly incomplete or `WAIVED_WITH_RESIDUAL_RISK`; it never becomes `PASS`"·WDR-INV-004).

### 5.5 `combined_set_no_permissive_union` + `gate_states_separated` (WDR-EV-012 노른자·§13/§26 AC-012·+Security 잔여)

**5.5a `combined_set_no_permissive_union`** — **시그니처**: `combined_set_no_permissive_union(active_set:
ActiveDeviationSet | None, applicable_decision_ids: frozenset[str], member_within_envelope: bool | None) -> bool`.

**판정(전부 AND·fail-closed)**:
1. **∅-seal 양방향(v1.1·§13 line 364 explicit-empty 정합)**: `active_set is None` ⇒ `False`(§13 "Absence of the
   set … is invalid"). `member_decisions` ∅ **이고 `applicable_decision_ids` 비-∅**인데 `is_complete is True`
   주장 ⇒ `False`(applicable 누락 차단). **`applicable_decision_ids` ∅ + `member_decisions` ∅ + `is_complete
   is True`는 유효한 explicit empty Active Deviation Set**(§13 line 364 "SHALL bind either an explicit empty
   Active Deviation Set or one complete canonical set" — 무-deviation 정상 번들의 명시 표현이며 거부는 결함).
   `applicable_decision_ids` ∅인데 `member_decisions` 비-∅ ⇒ `False`(surplus/conflicting 방향 차단·both-ways).
2. **completeness both-ways(§13 line 364)**: `applicable_decision_ids ⊆ set(active_set.member_decisions)` AND
   역방향 — 누락된 applicable deviation 하나라도 ⇒ **invalid**(`omitted_deviation_invalidates`·§13 line 364).
   set에만 있고 applicable 아닌 원소도 conflicting ⇒ deny.
3. **no permissive union(WDR-INV-006 핵심)**: 결합 판정은 any-narrow-wins — 어떤 member decision이라도 더 좁은
   scope/제약을 요구하면 그것이 지배(§13 line 380 "choose a more permissive interpretation" 금지·§4.4). 순서 독립.
4. **combined within envelope(spg 주입·양극성)**: `member_within_envelope is True`(§13 item 3·spg verdict). `None`/
   `False` ⇒ deny(§4.3). **spg 재저작 아님**(주입).
5. **generation 정합**: `active_set.deviation_generation`이 mixed 아님(§13 line 364 "mixed generation … is invalid")·
   MAX-generation floor(§4.4).

**5.5b `gate_states_separated`** — **시그니처**: `gate_states_separated(ladder: GateSeparationLadder | None) -> bool`.

**판정(전부 AND·fail-closed)**:
1. **∅-seal**: `ladder is None` ⇒ `False`.
2. **6-stage present(manually-transcribed anchor)**: `adr_accepted`·`deviation_eligible`·`configuration_activated`·
   `live_authorized`·`restricted_live_ready`·`production_ready` 전 stage 독립 표현(§26 AC-012 line 687 "remain
   distinct states"). anchor 집합 == 모델 필드(§7.2 drift).
3. **no implication(핵심)**: `no_status_implication(ladder)` — 어떤 stage positive가 다른 stage를 함의하지 않음.
   특히 `deviation_eligible is True`가 `configuration_activated`/`live_authorized`를 함의하지 않고(§12 line 358
   "It does not mean … the deviation is active, or live operation is authorized"), `configuration_activated is
   True`가 `live_authorized`를 함의하지 않음(§13 line 378 "does not make the deviation active or authorize trading").
   각 stage는 독립 주입 bool·파생 코드 경로 부재를 술어가 강제.
4. **readiness ≠ authority**: `readiness_not_authority(ladder)` — `restricted_live_ready`/`production_ready`가 True
   여도 `ladder.authority_effect`는 all-false(sbr readiness≠re-arm 선례·§28 line 752 "Acceptance of this governance
   mechanism accepts no specific deviation").

**반환**: 5.5a·5.5b 각각 전부 성립시 `True`. **WDR-EV-012를 닫지 않음**(`/3` 통합 + **+Security combined-risk
manipulation 저항** 잔여). 이는 all-false-authority를 **combined-set no-union + 상태 분리**로 확장한 것이다.

---

## 6. predicate-only substrate (§6 — 닫지 않음) + not-Phase-1 (§6b) + 순수 런타임/인간 (§6c)

> 전 술어 규율 태그: **predicate substrate only; 해당 WDR-EV 전부 NOT_IMPLEMENTED(≥ L2 component-fault +
> +Security/+Broker 대기). L1-decidable 순수 판정을 저작하되 어떤 WDR-EV도 닫지 않는다.**

### 6.1 `compensating_control_not_observation` (§11·§5.5·WDR-EV-003 substrate·+Security)
`compensating_control_not_observation(control: CompensatingControl | None) -> bool`: `control.observation_only is
False`(음극성·명시 False에서만) AND `is_preventive_or_containment is True`(양극성) AND `objective_evidence is True`
AND `fails_closed is True` AND `independent_of_failed_control is True`(전 양극성·§11 item 1-8). docs/monitoring/
alerting/operator/priority/expected-rejection/common-mode은 **compensation 무자격**(§5.5·§11 item 8·WDR-INV-005
line 162 "Observation alone is insufficient"). 실 independence 검증은 +Security. `EV-L2/3+Security`.

### 6.2 `independent_effective_person_approval` (§12·§7·WDR-EV-004 substrate·+Security)
`all_false_deviation_authority`(전 필드 `is False` + model_validator any-True ⇒ error) + SoD 구조 선언(requester/
control-owner/beneficiary/implementer/evidence-producer/live-armer는 RCL/egress authority·live-order credential/
route 무보유·§7 line 224) + `effective_principal_verdict is True`(hag 주입·양극성). effective-principal collapse/
quorum은 **hag-owned 주입**(§0.4e·WDR-INV-007 line 170). `common_mode_present is False`(음극성). 실 independence는
hag verdict + +Security. `EV-L2/3+Security`.

### 6.3 `deviation_single_use_non_authorizing` (§13·§7·WDR-EV-005 substrate·+Security·iap shape REUSE)
`deviation_single_use_non_authorizing(decision) -> bool`: `decision.single_use_consumed is False`(음극성 — 명시
False에서만·consumed ⇒ reject reuse·§13 line 368) AND `decision.result is
DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`(§4.2) AND no-widening(reduced_scope ⊆ requested)·no-partial·
no-replay(§12 line 356 "Decisions cannot be unioned, partially consumed, widened, renewed in place, or replayed")
AND `all_false_deviation_authority`(§6.2·activation/capacity/authority/transmit/re-arm 무부여). **iap `single_use`/
`exact_intent_only` consumption shape REUSE**(재저작 아님·§0.4h). 실 registry replay/generation-fence는 +Security.
`EV-L2/3+Security`.

### 6.4 `broker_finality_unchanged` + `economic_effect_persists` (§16·WDR-EV-008 substrate·+Broker·극성 봉합)
`broker_finality_unchanged`: missing-ACK은 non-acceptance **아님**(potentially-live 유지)·Cancel-ACK은 Final
Quantity Proof **아님**(§16 line 428-429·WDR-INV-011 line 186 "Missing ACK is not proof of non-acceptance. Cancel
ACK is not Final Quantity Proof"). 구조 token 판정. `economic_effect_persists`: `is_expired is not False` ⇒
future-use deny·**capacity/economic effect 불변**(WDR-INV-012 line 190 "Request withdrawal, decision expiry,
revocation, active-set change, profile rollback, or authorization expiry **cannot erase** positions, orders,
attempts, fills, external activity, obligations, or capacity"). afg/are/capsule `terminal_release_proven` shape.
**음극성 함정 봉합**: `is_expired`/`is_revoked`가 `None`이면 "not expired/revoked" fail-open 없이 deny(§4.3·`is
False`만 clear). 실 broker-finality 정량화는 +Broker. `EV-L2/3+Broker`.

### 6.5 `expiry_recovery_revives_nothing` (§15·§18·WDR-EV-009 substrate·+Security·authority 선례)
expiry no-auto-renewal(§15 line 417 "There is no automatic renewal, grace-period permission, rolling extension,
silent predecessor restoration") + recovery revives nothing(§18 line 469-476·WDR-INV-014 line 198) + restriction
does not self-revert(WDR-INV-015 line 202 "It never automatically restores a predecessor configuration"). `re_armed
is False` AND `self_reverted is False` AND `recovered_without_fresh_chain is False`(전 음극성·`is False`만·None ⇒
deny). prior decision/profile/active-set ⇒ INVALIDATED·fresh full governance chain 요구(§15 line 415·§18 line 473).
authority `recovery_generation_revives_nothing`·cur `recovery_revives_nothing` 동형(재저작 아님·§0.4h). 실 hard-fence는
+Security. `EV-L2/3+Security`.

### 6.6 `break_glass_no_authority` + `deviation_service_no_route` (§17·§20·§7·WDR-EV-011 substrate·+Broker+Security)
`break_glass_no_authority`: break-glass는 HALT/deny/narrow/separately-authorized-containment 요청만 가능·**approve/
activate deviation·expand profile scope·mutate/release capacity·classify protective·obtain broker credential·transmit·
clear UNKNOWN/HALT·re-arm 전부 불가**(§17 line 444-453 8-item all-false). `deviation_service_no_route`: deviation
registry/evaluator/workflow/dashboard/ticketing/residual-risk service는 usable live-order credential/signer/session/
route 무보유(§7 line 224·WDR-INV-013 line 194 "Deviation services hold neither authority"). all-false 축. 실 security
boundary(alternate route·external portal)는 +Broker+Security. `EV-L2/3+Broker+Security`.

### 6b. not-Phase-1 얇은 모델 property (WDR-EV-006 — 닫지 않음·런타임 race)
- **currentness/revocation send-race(§14·WDR-EV-006·`EV-L3+Security`)**: 순서 permutation model(`REVOKE<SEND ⇒
  deny`·`SEND<REVOKE<FIRST_BYTE ⇒ potentially-live + capacity-covered`·unknown ⇒ potentially-live·no-blind-retry·
  §14 line 400 "If a restrictive event races an authority claim, `SEND_STARTED`, or first broker byte and ordering
  cannot be proved, the attempt remains potentially live, capacity-covered, and non-retriable"). 실 cache-free
  currentness 검증(§14 line 388-396 "positively verify, without a permissive cache")·`B_deviation_revoke_to_egress`/
  `B_deviation_revoke_to_authority` bound·deny-first latch·restrictive floor(§14 line 398)는 **전부 +Security
  런타임**. RLP-EV-004(abort race)·CUR-EV-005(first-byte race)와 동형 계층.

### 6c. 순수 런타임 / 인간 절차 (L1 model property 없음)
independent effective-person review + quorum counting(§12·hag/인간)·per-action final-egress currentness binding(§14·
egress 런타임)·break-before-make configuration activation(§13 item 7·spg/ADR-002-014)·worst-credible-effect 계산 +
RCL capacity binding(§11·rcl + +Broker)·Hard Safety Envelope 봉입 판정(§8·§11·spg)·compensating-control 실 independence
검증(§11·+Security)·evidence 조립 + custody 무결성(§19·evidence `SegmentCommitmentScheme`)·Live Authorization 발급(§7·
liveauth)·Governed Single-Operator Re-Arm(§7·§12·hag/liveauth)·policy activation generation advance(§9·spg). 전부
런타임/인간/+Security/+Broker/형제-owned — §9.2 Phase-0.

---

## 7. firewall allowlist + 회귀

### 7.1 import-closure allowlist (`test_wdr_import_closure.py`)

`tos.wdr`의 전이 import closure는 **`{canonical, ordering, wdr}`에 국한**되어야 한다(egress/cur/rlp
`test_*_import_closure.py` 동형). `tools/tos_firewall_check.py`(§3.2 ratified allowlist·default-deny)가
`shared.*`/`services.*`/`cli.*`/외부 수치 라이브러리/동적 escape/**형제 tos 패키지 import(특히 rcl — §0.4g edge 0)**를
**차단**. 이 required check가 green이어야 §0.3 firewall 선언이 능동 성립. **naming(§0.4a)은 약한 soft load-bearing**
(firewall 배제 목록 명명) — 미래 형제 sir/stm/sci/ptf는 allowlist가 자동 배제. **`tos.wdr`를 §3.2 allowlist에
추가하려면 본 설계 문서 §3.2를 편집하는 PR 필요**.

### 7.2 회귀 스위트 (예정 — `tos/tests/wdr/`)

`test_wdr_boundary.py`(boundary_denies_non_waivable 노른자 1·∅/unresolved/boundary-hit/union-only property +
**15-item anchor drift property**[§8 line 234-248 == `NonWaivableBoundaryAnchor` 필드집합·manually-transcribed
anchor·§0.4h])·`test_wdr_scope.py`(scope_exact_and_complete 노른자 2·∅/미표현/wildcard/closure 양방향 + **21-dimension
anchor drift**[§5.7 line 128 == `ScopeDimension`])·`test_wdr_unknown.py`(unknown_denies_and_confines 노른자 3·전
UNKNOWN 극성 None⇒deny·budget≠capacity·protective≠bypass)·`test_wdr_evidence_status.py`(evidence_status_honest 노른자
4·PASS-relabel 금지·WAIVED exact-current·measured 가시)·`test_wdr_combined_gate.py`(combined_set_no_union + gate
separation 노른자 5·no-implication·6-stage anchor)·`test_wdr_polarity.py`(극성 전수·§4.3·**`is not True` 음극성
부재 grep**)·`test_wdr_reconcile.py`(그룹 reconcile 순서독립·no-union·omitted⇒invalid·§4.4)·
`test_wdr_truthy_sentinel.py`(§4.2·5 enum)·`test_wdr_void_canaries.py`(§4.1)·`test_wdr_authority.py`(all-false·
model_validator any-True⇒error)·`test_wdr_malformed_model.py`(positive-claim + incomplete-scope coexistence seal·
model_construct 우회 2층·§2.3)·`test_wdr_predicate_only.py`(§6 substrate)·`test_wdr_import_closure.py`(§7.1).
**property-based(hypothesis)** 중심(EV-L1 = model/property). **anchor drift property가 최우선**(15-item boundary·
21-dimension scope·6-stage gate가 손전사 anchor와 일치·cur v1.1 §7.2 교훈). **양방향 canary**: 각 노른자에 대해
"모든 조건 충족 ⇒ True" 및 "각 조건 개별 위반 ⇒ False"를 property로 확인(단방향 seal 방지).

---

## 8. 수치 → Phase-0 / INSTANCE (숫자 하드코딩 0)

WDR 소유 numeric은 **전부 Profile INSTANCE 측정/승인·주입**(현재 전부 `null`/`TBD`·ADR §27 item 12·`VERIFICATION-
PROFILE-002.yaml` INSTANCE):

| 키 (ADR §27 item 12) | 소유 | 상태 | 근거 |
|---|---|---|---|
| `B_deviation_revoke_to_authority` | **WDR** | MEASURE·null | §14 revocation→authority revoke(런타임·WDR-EV-006) |
| `B_deviation_revoke_to_egress` | **WDR** | MEASURE·null | §14 revocation→egress deny(런타임·WDR-EV-006) |
| `B_deviation_generation_fence` | **WDR** | MEASURE·null | §5.8/§14 Deviation Generation→predecessor 무능 증명 |
| `MAX_deviation_duration_ms` | **WDR** | APPROVE·null | §15 hard expiry(economic 불변·wall-clock secondary·+Security) |
| `MAX_deviation_decision_age_ms` | **WDR** | APPROVE·null | §12/§15 stale decision ⇒ deny(wall-clock secondary) |
| `MAX_residual_risk_review_interval_ms` | **WDR** | APPROVE·null | §15 review interval(trustworthy time 주입·§0.4h time) |

**주의**: worst-credible-effect *계산*(§11)은 rcl + +Broker(§28 gate 8)·WDR는 envelope를 주입 opaque 좌표로 소비
(§0.4g). **L1 아티팩트는 전 numeric이 `null` 상태에서 구성 가능**해야 하며(§2.3 `_REQUIRED_COVERED` numeric 제외),
누락 numeric claim은 fail-closed(§4.2). broker proper noun/KIS 특정값 부재(broker-agnostic·정규 텍스트).

---

## 9. Phase-0 / not-Phase-1 체크리스트

### 9.1 Phase-1(EV-L1) 산출물 (본 계약이 실현 지침을 제공)
1. `tos.wdr` 패키지(canonical/ordering만 의존·firewall green·**rcl edge 0**).
2. 모델: `SafetyDeviationPolicy`·`SafetyDeviationRequest`·`SafetyDeviationDecision`·`ResidualRiskAcceptanceRecord`·
   `ActiveDeviationSet`(5 digest-bound) + value(`DeviationScope`·`CompensatingControl`·`DeviationDependencyClosure`·
   `NonWaivableBoundaryAnchor`·`WaivedEvidenceItem`·`GateSeparationLadder`·`DeviationClassification`) +
   `AllFalseDeviationAuthority` + enum(`DecisionResult`·`NonWaivableClassification`·`RequestState`·
   `ActiveDeviationState`·`WaivedEvidenceStatus`·`ScopeDimension`·`CompensatingControlKind`).
3. 노른자 술어 5종(§5) + 지지 + predicate-only substrate 6종(§6) + 얇은 not-Phase-1 model 1종(§6b).
4. malformed-model validator(positive-claim + incomplete-scope seal)·truthy 봉인·극성(음극성 `is False`만)·reconcile·
   all-false·canary·**anchor drift**(15-item boundary·21-dimension scope·6-stage gate) 회귀(§4·§7.2).

### 9.2 Phase-0 / 미착지 / +Security / 런타임 / 인간 (닫지 않음 — 20 항목)
1. Policy/Request/Decision/Residual-Risk/Active-Set canonical schema **승인**(§28.1·거버넌스).
2. requirement/hazard registry + Non-Waivable Boundary classifier 독립 리뷰(§28.2·+Security).
3. exact scope·dependency closure·combined-risk·materiality·common-mode deterministic 평가(§28.3·런타임).
4. compensating-control eligibility·independence·evidence·currentness·failure behavior(§28.4·**+Security**).
5. Effective Principal quorum·conflict·delegation·single-use consumption·role separation(§28.5·**hag-owned·인간·+Security**).
6. ADR-002-014 break-before-make activation·complete Active Deviation Set(§28.6·**spg-owned 런타임**).
7. Deviation Generation·revocation·expiry·restrictive ingress·local latch·final-egress active currentness(§28.7·
   **egress 런타임·+Security·cache-free·WDR-EV-006**).
8. UNKNOWN·broker finality·economic continuity·capacity·protective·emergency fault injection(§28.8·**+Broker·rcl**).
9. restart/failover/restore/rollback/replay/workflow/time/evidence recovery·renewal non-revival(§28.9·**런타임·+Security**).
10. deviation/workflow/registry/evidence/reviewer identity가 unauthorized broker effect 미도달(§28.10·**+Security·failure-domain**).
11. WDR-EV-001..012 required-level pass + 독립 review(§28.11·**전 EV**).
12. numeric bound 측정/승인(§8·§28.12·**INSTANCE·+Broker·+Security**).
13. 전 security/failure-domain/currentness/configuration/authority/evidence/recovery review(§28.13·**+Security**).
14. Critical/Major finding 0 + RFC/ADR/VER/Evidence Register traceability(§28.14).
15. ARCHITECTURE-GATE-STATUS 명시 ADR acceptance(§28.15·거버넌스).
16. worst-credible-effect 계산 + RCL/action-flow binding(§11·**rcl-owned·+Broker**).
17. Hard Safety Envelope 봉입 판정(§8·§11·**spg-owned**).
18. Live Authorization 발급(§7·**liveauth-owned·ADR-002-007**).
19. Governed Single-Operator Re-Arm Variant(§7·§12·**hag/liveauth-owned·인간**).
20. 027 incident generation 차원 owner(-027 SIR) 착지 후 실 좌표 배선(현재 주입 opaque·미착지·§0.4f).

**cross-EV 의존(§28.11)**: WDR-EV closure는 spg/hag/rcl/egress/cur/evidence/liveauth/iap/authority/time 및 -027
evidence가 required level에서 pass해야 성립 — Phase-1 범위 밖.

---

## 10. 명명 결정 + 리뷰어 공격 지점

### 10.1 운영자 판단 지점
- **패키지 명명 `tos.wdr`**(§0.4a) — register-prefix 1:1·firewall 배제 목록이 이름 지명(cur:51·rlp:39)·운영자
  "변경 불가" 지시. **naming = RLP보다 약한 soft load-bearing**(RLP는 내용 이연·wdr은 firewall 목록 명명·정직 명기).
  runner-up `tos.waiver`/`tos.deviation` 기각.
- **WDR = greenfield content owner·피이연 없음**(§0.4b) — RLP(#25)와의 최대 대비. RLP는 egress/cur가 `tos.rlp`로
  trial-content를 이연한 피이연자였으나 **WDR은 inbound 이연 실측 0건**. **독립 리뷰어가 재검토할 지점**(RLP 미러
  구조를 WDR에 잘못 적용하지 않았는지).
- **rcl edge 0 판정**(§0.4g·측정 3) — are/ioc/afg는 CapacityVector 타입 산술을 위해 edge를 취했으나 WDR L1은
  capacity 산술 미수행·worst-credible envelope 주입 opaque·§7 "never capacity". **독립 리뷰어가 재검토할 지점**
  (alias vs edge 0 판단).
- **not-Phase-1 vs predicate-only 세분**(§1) — 006만 not-Phase-1(L3 floor·유일 `EV-L3+` 행)·003/004/005/008/009/011은
  predicate-only(L2 floor·얇은 substrate 존재)·register EV-level과 정합하는 증거기반 세분.

### 10.2 리뷰어 공격 지점 (선제 반론)
1. **"WDR가 RLP처럼 피이연자 미러여야"** — 반론: 실측 inbound 이연 0건(§0.4b grep)·WDR은 순수 greenfield 생산자·
   naming은 firewall 배제 목록의 약한 load-bearing·RLP 미러 오적용 회피.
2. **"WDR residual-risk = spg residual_risk_ceiling 중복"** — 반론: WDR = per-deviation accepted-risk record(§5.4)·
   spg = profile-level ceiling·envelope 봉입은 spg 주입 verdict·edge 0(§0.4c).
3. **"WaivedEvidenceStatus = evidence status 중복"** — 반론: 실측 tos.evidence 미소유(GapStatus/ReceiptVerificationStatus
   만)·§19 register-status는 custody와 다른 축·WDR 로컬 저작·seam 충돌 0(§0.4d).
4. **"WDR가 hag quorum/effective-principal 재저작"** — 반론: collapse/quorum = hag(ADR-002-015)·WDR verdict 주입
   소비·WDR-EV-004 `EV-L2/3+Security`·edge 0(§0.4e).
5. **"미착지 027 차원 phantom 인용"** — 반론: ADR 원문만·코드 인용 0·주입 opaque generation(§0.4f·§0.2).
6. **"rcl CapacityVector alias 필요(worst-credible)"** — 반론: WDR L1은 vector 비교 미수행·정량화 +Broker/rcl-owned·
   §7 line 217 "never capacity"·edge 0이 ADR 정합(§0.4g·are/ioc/afg와 대비).
7. **"model_construct로 malformed request/decision 통과"** — 반론: positive-claim + incomplete-scope validator +
   술어 2층(§2.3·RLP `ExactTrialPlan`·egress QCC 동형·#20 상속).
8. **"scope wildcard denylist가 비전수"** — 반론: **정직 명기**(§5.2·#25 MAJOR-1 교훈) — strip+casefold 정규화·
   메타문자 거부 후에도 신종 표기는 +Security/런타임 소유·denylist 비전수임을 문서화.
9. **"음극성 필드 `is not True` 사용"** — 반론: **task 규율 전 적용**(§4.3) — 음극성 allow는 `is False`만·`is not
   True` 부재를 grep 회귀로 강제·#18/#22/#23/#25 재발 봉인.
10. **"over-realization: independent review/per-action binding/worst-effect를 L1 주장"** — 반론: 닫는 WDR-EV 0·006
    not-Phase-1·§6c 순수 런타임/인간 명시(§1·§9.2)·core 5행 중 3행 +Security/+Broker 잔여 정직 명기.
11. **"combined set이 permissive union 허용"** — 반론: §13 line 380 "choose a more permissive interpretation" 금지·
    WDR-INV-006·`combined_set_no_permissive_union` any-narrow-wins·omitted⇒invalid·순서독립(§5.5a·§4.4).
12. **"deviation budget이 capacity headroom 생성"** — 반론: §7 line 217 "never capacity"·§16 line 434 "accepted
    residual risk cannot free UNKNOWN capacity"·`budget_is_not_capacity` all-false·WDR-INV-013.

---

## 11. 선제 defect-class 봉합 (전 시리즈 교훈)

| defect class | 출처 | WDR 봉합 |
|---|---|---|
| grep head 절단 카운트 오류 | #12 | register 전수 파싱(md line 336-347 직접·§1·naive grep 금지) |
| RLP 미러 오적용(피이연 가정) | **본 문서 신규** | inbound 이연 실측 0건 명기·WDR=greenfield 생산자(§0.4b·§10.2-①) |
| truthy-sentinel fail-open | #13·#14 M1 | `_NonTruthyStrEnum` 5종 처음부터(§2.2·§4.2·PASS 멤버도 truthy-untestable) |
| ∅ 단방향 seal | #8·#15 | boundary/mandated-scope/closure/member-set ∅ 양방향(§5.1-5.5·∅ 가드는 §13:364 explicit-empty 예외 반영·v1.1) |
| 집합 단방향 | #10 | mandated ⊆ present·applicable ⊆ member 양방향(§5.2·§5.5) |
| malformed-model model_construct 우회 | #20 | positive-claim + incomplete-scope validator + 술어 2층(§2.3) |
| 미표현 요소 vacuous pass | #20·#23 | 미표현 scope 차원/member deviation ⇒ incomplete(§5.2·§5.5) |
| phantom id/코드 인용 | #17·#20·#23 | 인용 전 grep·미착지 027 코드 0(§0.4f)·seam은 실측 코드 line 인용·"§5.2 deviation"(spg 자체) phantom 함정 회피(§0.4b) |
| **극성 fail-open(consumed/expired/unknown None)** | **#18·#22 MAJOR-2** | **극성 전수 표 + 음극성 `is False`만·`is not True` 금지·None ⇒ deny 수렴 회귀(§4.3·다수 필드)** |
| **그룹 첫-entry/permissive union 판정** | **#22 MAJOR-1** | **combined Active Deviation Set 전-entry 보수·no-union·any-narrow-wins·omitted⇒invalid·MAX-generation·boundary union-only(§4.4·§5.5)** |
| **enum-drift 참조집합 부정직** | **#14 anchor·cur v1.1 §7.2** | **manually-transcribed regression anchor 명시(15-item boundary·21-dimension scope·6-stage gate·§0.4h·§7.2 drift)** |
| seam 재저작(거버넌스 내용 중복) | #19·#22·#23·#25 | spg/hag/rcl/egress/cur/evidence/liveauth/iap/authority 소유 실측·주입 소비(§3.5·§10.2) |
| rcl edge 과잉(불필요 import) | **본 문서 신규** | WDR L1 capacity 산술 미수행·edge 0·are/ioc/afg 대비(§0.4g·§10.2-⑥) |
| 과대 주장(authoring=acceptance) | 전 시리즈 | 닫는 WDR-EV 0·"EV-L1-complete 주장 금지"·core 5행 중 3행 +태그 잔여 명기(§1) |

---

## 12. 요약

`tos.wdr`는 시리즈의 **safety-deviation governance greenfield content owner(피이연 없음)**를 실현한다. RLP(#25)와의
결정적 대비: RLP는 egress/cur가 `tos.rlp`를 **이름까지 명시해 trial-content를 이연**한 피이연자였으나, **WDR은
어떤 착지 형제도 `tos.wdr`로 deviation-content를 이연하지 않는다**(inbound 이연 실측 0건·§0.4b). `tos.wdr` naming은
firewall 배제 목록(cur:51·rlp:39)의 **약한 soft load-bearing**일 뿐이다. 본 계약의 core는 **5행(WDR-EV-001
Non-Waivable Boundary·002 Exact Scope and Dependency Closure·007 UNKNOWN/Capacity/Protective Confinement·010
Evidence and Status Honesty·012 Combined Deviations and Gate Separation·거버넌스 6부작 중 L1 공동 최대)**이며,
노른자 술어 5종(`boundary_denies_non_waivable`·`scope_exact_and_complete`·`unknown_denies_and_confines`·
`evidence_status_honest`·`combined_set_no_permissive_union`+`gate_states_separated`)으로 저작한다. **닫는 WDR-EV = 0**
(authoring ≠ acceptance). **RLP와 달리 core 5행 중 3행(001·007·012)이 +Security/+Broker 잔여 태그를 보유**함을
행별로 정직 명기한다.

거버넌스 ADR의 본질(인간 절차·런타임)을 정직하게 경계 짓는 것이 **본 문서의 최대 규율**이다: independent
effective-person review·quorum·per-action final-egress currentness binding·revocation send-race·worst-credible-effect
계산·break-before-make configuration activation·Hard Safety Envelope 봉입·evidence 조립 무결성·Live Authorization
발급은 **전부 인간/런타임/+Security/+Broker/형제-owned**이며 L1이 아니다(over-realization 경계·§1·§6c). 동시에 spg
Hard Safety Envelope/residual_risk_ceiling·hag quorum·rcl CapacityVector·egress final-egress·cur Safety Currentness
Vector·evidence custody·liveauth Live Authorization은 **전부 주입 소비**이며 WDR가 재저작하지 않는다(duplication
경계·§3.5). **rcl edge = 0**(WDR L1 capacity 산술 미수행·are/ioc/afg와 대비·§0.4g). #18/#22 MAJOR-2(극성 `is
False`만)·#22 MAJOR-1(reconcile/no-union)·cur v1.1(enum-drift anchor)를 §4.3-4.4·§7.2로 선제 봉합한다.

**비준 기록: 2026-07-27 운영자 위임 자동 비준 대상(v1.0 초안 — 상세는 문서 헤더 비준 기록 블록).**

---

## 부록 A — §5 정의 10종 verbatim 전사 (ADR line 100-140·過/不 양방향 계수)

**계수: 정확히 10종(5.1~5.10). 過(초과 창작) 0·不(누락) 0.** 각 정의는 ADR 원문 손전사.

- **§5.1 Safety Deviation Policy** (line 102-104): "An immutable ADR-002-014 governed policy defining eligible
  deviation classes, the non-waivable boundary, scope and dependency rules, compensating-control requirements,
  approval independence, duration, currentness, invalidation, evidence, and failure behavior." → `SafetyDeviationPolicy`(§2.4).
- **§5.2 Safety Deviation Request** (line 106-108): "An immutable proposal to accept one identified unmet or
  degraded requirement for one exact reduced scope and duration under specified compensating controls. **It grants
  no authority**." → `SafetyDeviationRequest`(§2.4·all-false).
- **§5.3 Safety Deviation Decision** (line 110-112): "An immutable independent result of `DENY`, `HOLD`, or
  `ELIGIBLE_FOR_RESTRICTED_CONFIGURATION` for one exact request digest. Eligibility permits only a single request
  to the separate safety-configuration workflow." → `SafetyDeviationDecision` + `DecisionResult`(§2.2).
- **§5.4 Residual-Risk Acceptance Record** (line 114-116): "An immutable record of the bounded risk, assumptions,
  compensating controls, reviewers, expiry, evidence status, and explicit scope accepted by the authorized quorum.
  **It is not proof that the underlying requirement passed and grants no authority**." → `ResidualRiskAcceptanceRecord`(§2.4).
- **§5.5 Compensating Control** (line 118-120): "An independently governed, enforceable preventive or containment
  mechanism that reduces the exact added risk of an allowed deviation. A document, alert, dashboard, audit, replay,
  priority label, or operator promise is **not by itself** a compensating control." → `CompensatingControl`(§2.4·§6.1).
- **§5.6 Non-Waivable Boundary** (line 122-124): "The union of RFC-000, RFC-001's explicit no-waiver set, this ADR's
  §8 prohibitions, and any stricter active Safety Deviation Policy rule. **Policy may add prohibitions but cannot
  remove them**." → `NonWaivableBoundaryAnchor`(§2.4·`boundary_is_union_only`·§5.1).
- **§5.7 Deviation Scope** (line 126-128): "The complete environment, Safety Cell, Capacity Domain, legal portfolio,
  account, broker, venue, instrument, strategy, action class, software, configuration, identity, route, session,
  failure-domain, time, evidence, requirement, hazard, and dependency closure to which one decision applies." →
  `DeviationScope`/`ScopeDimension`(§2.4·**21 dimension**·anchor 부록 B).
- **§5.8 Deviation Generation** (line 130-132): "A monotonic generation fencing previous policies, active sets,
  decisions, acceptance records, configuration requests, authority requests, and consumers after any material
  deviation, scope, control, evidence, reviewer, policy, or recovery change." → ordering REUSE(§3.2·§5.8 fence).
- **§5.9 Active Deviation Set** (line 134-136): "One immutable canonical set of every deviation and residual risk
  applicable to an exact Safety Configuration Bundle. It is evaluated as a combined risk set and **cannot be
  assembled by permissive union at a consumer**." → `ActiveDeviationSet`(§2.4·§5.5·WDR-INV-006).
- **§5.10 Deviation Dependency Closure** (line 138-140): "Every component, artifact, account, shared limit,
  authority, capacity, credential, route, failure domain, economic effect, verification claim, and downstream
  consumer that may be affected by the missing control or its compensating controls." → `DeviationDependencyClosure`(§2.4·§5.2).

## 부록 B — §5.7 Deviation Scope 21-dimension anchor (manually-transcribed·過/不 양방향)

**계수: 정확히 21 dimension(§5.7 line 128 손전사). 過 0·不 0.** `ScopeDimension` closed StrEnum == 이 집합
(§7.2 drift property가 강제):
1. environment · 2. safety_cell · 3. capacity_domain · 4. legal_portfolio · 5. account · 6. broker · 7. venue ·
8. instrument · 9. strategy · 10. action_class · 11. software · 12. configuration · 13. identity · 14. route ·
15. session · 16. failure_domain · 17. time_interval · 18. evidence · 19. requirement · 20. hazard · 21. dependency_closure.

## 부록 C — §8 Non-Waivable Boundary 15-item anchor verbatim (ADR line 234-248·過/不 양방향)

**계수: 정확히 15 item(§8 line 234-248). 過 0·不 0.** `NonWaivableBoundaryAnchor` 필드 == 이 집합(§7.2 drift).
"At minimum, no deviation may waive, reinterpret, or bypass:"
1. (234) "any RFC-000 constitutional requirement";
2. (235) "RFC-001's explicit no-waiver set: independent halt authority, live/non-live segregation, a valid Safety
   Profile, reconciled authoritative position state, bounded single-action risk, bounded aggregate risk, the Hard
   Safety Envelope (SAFE-004), and prevention of known duplicate-exposure paths" (v0.3 8-item mirror);
3. (236) "fail-closed treatment of missing, stale, conflicting, unverifiable, or UNKNOWN safety state";
4. (237) "Risk Capacity Ledger exclusivity for capacity mutation and serialization";
5. (238) "Broker Adapter / Egress Gateway final enforcement and broker-route confinement";
6. (239) "stale writer, authority, profile, recovery, currentness, deviation, and egress generation fencing";
7. (240) "missing ACK and Cancel ACK broker-finality semantics";
8. (241) "economic-effect and capacity continuity after artifact or authority expiry";
9. (242) "exact current Hard Safety Envelope and Runtime Safety Profile enforcement";
10. (243) "independent Human HALT and restrictive break-glass behavior";
11. (244) "live/non-live identity, credential, route, and environment segregation";
12. (245) "the rule that priority is not reserved protective capacity";
13. (246) "the rule that documentation, monitoring, audit, replay, and incident reconstruction do not substitute
    for prevention";
14. (247) "the prohibition on automatic re-arm or recovery-based authority revival";
15. (248) "this ADR's policy, independence, currentness, evidence-honesty, and non-authority rules".
- (250) "The Safety Deviation Policy may declare additional requirements non-waivable … It cannot make this list
  smaller." → `boundary_is_union_only`.
- (252) "If requirement identity or applicability is unresolved, it is treated as non-waivable until positively
  classified otherwise" → `NonWaivableClassification.UNRESOLVED` ⇒ deny.

## 부록 D — §6 WDR-INV 15종 + §21 상태 verbatim (ADR line 146-204 / 514-538·過/不 양방향)

**INV 계수: 정확히 15종(WDR-INV-001~015·line 146-204). 過 0·不 0.**
- **WDR-INV-001** (148) Deviation Artifacts Are Not Authority — all-false(§2.4·§6.2).
- **WDR-INV-002** (152) Non-Waivable Means Prohibited — `boundary_denies_non_waivable`(§5.1).
- **WDR-INV-003** (156) Exact Reduced Scope Only — `scope_exact_and_complete`(§5.2).
- **WDR-INV-004** (160) Approval Does Not Equal Verification — `evidence_status_honest`/`approval_is_not_verification`(§5.4).
- **WDR-INV-005** (164) Enforceable Compensation — `compensating_control_not_observation`(§6.1).
- **WDR-INV-006** (168) Combined Risk, No Permissive Union — `combined_set_no_permissive_union`(§5.5·§4.4).
- **WDR-INV-007** (172) Independent Effective-Person Approval — hag 주입(§6.2·§0.4e·Single-Operator Variant 포함).
- **WDR-INV-008** (176) Configuration and Re-arm Remain Separate — `deviation_single_use_non_authorizing`(§6.3)·`gate_states_separated`(§5.5b).
- **WDR-INV-009** (180) Revocation Dominates Permission — `is_revoked`/`is_expired` 음극성(§4.3·§6.4)·"Ambiguity is denial".
- **WDR-INV-010** (184) UNKNOWN Never Becomes Permission — `unknown_denies_and_confines`(§5.3).
- **WDR-INV-011** (188) Broker Finality Is Unchanged — `broker_finality_unchanged`(§6.4).
- **WDR-INV-012** (192) Economic Effect Outlives Deviation State — `economic_effect_persists`(§6.4).
- **WDR-INV-013** (196) RCL and Egress Exclusivity — `deviation_service_no_route`(§6.6)·**rcl edge 0**(§0.4g).
- **WDR-INV-014** (200) Recovery Does Not Revive — `expiry_recovery_revives_nothing`(§6.5).
- **WDR-INV-015** (204) Restriction Does Not Self-Revert — `expiry_recovery_revives_nothing`/`self_reverted`(§6.5).

**§21 Request state 계수: 10-token flow(line 518-524). 過 0·不 0.** `RequestState`(§2.2):
`DRAFT → SUBMITTED → UNDER_REVIEW → DENIED | HOLD | ELIGIBLE_FOR_RESTRICTED_CONFIGURATION → CONSUMED | SUPERSEDED |
REVOKED | EXPIRED`.

**§21 Active deviation applicability 계수: 7-token(line 528-534). 過 0·不 0.** `ActiveDeviationState`(§2.2):
`NOT_ACTIVE → CONFIGURATION_STAGED → ACTIVE_RESTRICTED → RESTRICTION_PENDING → REVOKED | EXPIRED | SUPERSEDED`.
- (536) "Only ADR-002-014 activation may move `CONFIGURATION_STAGED` to `ACTIVE_RESTRICTED`, and that state still
  creates **no live authority**." → spg 주입·all-false 유지.
- (538) "No transition from `REVOKED`, `EXPIRED`, or `SUPERSEDED` returns to `ACTIVE_RESTRICTED`." → non-revival(§6.5).

**§5.3 / §12 Decision result 계수: 3-token(line 112). 過 0·不 0.** `DecisionResult`(§2.2): `DENY` | `HOLD` |
`ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`.

**§19 verification-item status 계수: 6 허용 + PASS/ACCEPTED 금지-flip(line 484-490). 過 0·不 0.**
`WaivedEvidenceStatus`(§2.2): {NOT_IMPLEMENTED · FAIL · INCONCLUSIVE · BLOCKED · EXPIRED · WAIVED_WITH_RESIDUAL_RISK}
허용 + PASS 멤버(정직 측정용·deviation⇒flip 금지·§5.4).

---
*문서 끝. 본 설계는 EV 행을 0개 닫으며 어떤 EV 수용도 주장하지 않는다(§1·§28 gate·gate-status line 793 "All 363
registered items remain NOT_IMPLEMENTED"). tos-spec 무수정·기존 docs/plans 무수정·커밋 없음.*
