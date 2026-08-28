# 설계 문서 #21 — Corporate Actions·Non-Trade State Changes 계약 (2026-07-26, v1.1)

> **문서 번호 규약 각주(#21 확정)**: 세션 A가 #19 VTG(venue)·#20 HAG(human-authority)를 선점했고(메모리 조율
> 완료), 본 문서는 **#21**이다. 시리즈 순번은 착수 순서가 아니라 비준·선점 순서를 따른다(#16 AFG v1.0 "#15"→v1.1
> "#16" 개번 선례·#18 "잠정 #18" 확정 선례). naming/번호는 load-bearing이 아니다.
>
> **대상 ADR**: ADR-002-010 — Corporate Actions and Non-Trade State Changes ("NT"). 515줄. Status **Proposed**,
> Date 2026-07-13. Decision Type: Safety-Critical Architecture Decision. **Amends**: RFC-002 §14.7 External and
> Non-Trade State Changes·§15 Reconciliation·§10/§19/§21/§23 capacity/recovery/protection/instrument-identity
> prerequisites(ADR line 8). **Depends On**(ADR line 9): RFC-000 constitutional safe state; RFC-001
> SAFE-002/004/011/013/015/020/022/023/024/025/030/032/035/040/041/044/048/050/051/052; **ADR-002-001 through
> ADR-002-009 and ADR-002-011**. ADR-002-011(#18 Protective Replacement)은 비준·구현 완료로 인용 가능하다(사전
> 브리핑·project memory `tos-spec-reuse-analysis-verdict`).
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며 스펙 텍스트
> (RFC/ADR/템플릿/프로파일)를 **변경하지 않는다**. **broker-agnostic 원칙(project memory
> `tos-spec-broker-agnostic`)**: 본 문서의 규범 텍스트는 **어떤 구체 broker(KIS 포함)도 명명하지 않는다.** corporate
> action·transformation·transition envelope·correction/reversal idempotency 불변식은 전부 broker-agnostic이며, broker
> 제약은 capability class(Broker Capability Profile, #10)로만 표현한다.
>
> **자체 시리즈(실측·앵커)**: ADR-002-010은 **자체 `NT-INV` 번호 시리즈를 정의하지 않는다**(grep 실측: `NT-INV`
> 0건; §21에 `NT-AC-001..012` 12종만, line 402–413). 매핑 대상 EV: `verification/EVIDENCE-REGISTER-002.csv`의
> **`NT-EV-001..012` 12행**(domain "Non-Trade Events", primary_adr ADR-002-010). ⇒ 본 계약은 모델 불변식·술어를
> **`NT-EV-001..012` · `NT-AC-001..012`(§21) · §-clause · `SAFE-###`(§24 traceability line 472–483)**에 앵커하고
> **새 INV/AC/EV 시리즈를 창작하지 않는다**(§0.4f). #9(ADR-002-006 자체 INV 부재)·#11 protective·#18 PR(둘 다 자체
> INV 부재) 동형이며, #6(`SA-INV`)·#10(`BC-INV`)·#16(`AFG-INV`)·#19(`VTG-INV`)이 자체 INV에 앵커한 것과는 상황이 다르다.
>
> **선행 문서(의존·형제)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 전용 top-level 패키지에 놓이고 §3.2 허용목록 안에서만 의존한다(§0.3). line 164 "naming은
>   load-bearing이 아니다 — 내부 세분화는 후속 설계 문서가 정의한다"에 따라 본 문서가 신규 패키지 내부를 정의한다.
> - [설계 #18 — Protective Replacement·Protection-Gap Control 계약 (v1.2, 비준·구현)](2026-07-26-tos-protective-replacement-design.md)
>   + 코드 `tos/src/tos/replacement/`. **본 문서의 시리즈 규율 4종 신설본이자 최인접 상류 중 하나다.** replacement는
>   ADR-002-011 §6.2/§9 overlap-first reservation completeness·no-netting·§12 partial-fill re-eval·§7 authorization·
>   §5 workflow lifecycle을 **이미 소유·구현**한다: `overlap_first_reservation_complete`(`predicates.py:152`)·
>   `overlap_first_sequencing_valid`(`predicates.py:199`)·`cancel_first_admission_gate`(`predicates.py:467`)·
>   `netting_absent`(`predicates.py:103`)·`ReplacementMode`(`vocabulary.py:74`)·`ReplacementWorkflowState`
>   (`vocabulary.py:115`)·`CredibleIntermediateOutcomeKind`(`vocabulary.py:158`). **결정적 실측(소유권 경계)**:
>   ADR-002-011 §16 recovery step 5(`ADR-002-011...md:367` verbatim) "**reconcile current exposure and recognized
>   non-trade changes**"가 **명시 NT seam**이다 — replacement(recovery)가 recognized non-trade change를 본 ADR-002-010
>   으로 **이연**한다. 역으로 NT §13 line 272 "**If protective coverage must be changed, ADR-002-011 governs
>   cancellation, replacement, gap, overlap, and capacity**"가 protective-order replacement를 replacement로 **이연**
>   한다 — 상호 명시 경계로 중복 0. NT-EV-006(Broker Open-Order Adjustment, `EV-L3/5`)이 이 접점이며 **본 Phase-1
>   비저작·주입 소비**다(§3.5). **`tos.replacement`는 import하지 않는다**(형제; produced-bool/주입 좌표로만).
> - [설계 #13 — Aggregate Risk Projection 계약 (v1.1, 비준·구현)](2026-07-25-tos-aggregate-risk-projection-design.md)
>   + 코드 `tos/src/tos/are/`. **두 번째 최인접 상류이자 최대 소유권 인접 지대다.** are는 §9 conservative transition
>   envelope의 **aggregate-risk 투영**을 **이미 소유·구현**한다: `worst_intermediate_risk`(`predicates.py:186`)·
>   `credible_space_bounded`(`predicates.py:196`)·`envelope_bound_not_enlarged`(`predicates.py:557`, ARE-INV-007
>   line 178 "Neither runtime policy, strategy, human approval, broker result, nor model output may enlarge the
>   Hard Safety Envelope")·`no_credible_intermediate_increases_exceedance`(`predicates.py:207`)·**`AdverseScenarioKind.
>   EXTERNAL_TRAPPED_NONTRADE_CONCURRENT`(`vocabulary.py:115`)**·`RiskDimensionKind.OPTION_GREEKS_EXERCISE_ASSIGNMENT`
>   (`vocabulary.py:64`)·`RiskDimensionKind.SETTLEMENT_CASH_CURRENCY`(`vocabulary.py:65`)·`RiskScopeKind.{UNDERLYING,
>   ISSUER}`(`vocabulary.py:87/88`). **결정적 소유권 증거**: are가 **비-거래 동시 trapped 시나리오를 aggregate-risk
>   축의 first-class 시나리오 kind로 이미 소유**하므로(`EXTERNAL_TRAPPED_NONTRADE_CONCURRENT`), 본 ADR §9 "maximum
>   aggregate risk across the envelope"의 **risk 산출은 are 소유**이고 NT는 **event·leg 열거 완전성**을 소유한다
>   (§0.4d — #18 §0.4d 이중 계상 정합 동형). **`tos.are`는 import하지 않는다**(형제; 주입 값으로만).
> - [설계 #5 — Risk Capacity Ledger 계약 (v1.1, 비준·구현)](2026-07-21-tos-risk-capacity-ledger-design.md) + 코드
>   `tos/src/tos/rcl/`. **세 번째 소유권 인접 지대다.** rcl은 capacity 산술·commit·release를 **이미 소유·구현**한다:
>   **`TransitionCause.RECOGNIZED_EXTERNAL_CHANGE`(`vocabulary.py:92`)**·`CommandType.{CREATE_EXTERNAL_QUARANTINE,
>   MARK_TRAPPED_EXPOSURE}`(`vocabulary.py:74/75`)·`credible_union_capacity`(`predicates.py:739`, "worst credible
>   union ... without last-write-wins merge ... Empty input is fail-closed")·`CapacityState.{TRAPPED_CONSUMED,
>   QUARANTINED_UNKNOWN}`(`vocabulary.py:30/29`)·`WEAK_CAUSES`(TIMEOUT/ABSENCE/OPERATOR_ASSUMPTION는 **conservatism만
>   증가** — `vocabulary.py`). **결정적 증거**: recognized non-trade change는 rcl의 **capacity-transition CAUSE**
>   (`RECOGNIZED_EXTERNAL_CHANGE`)이며 ADR §10 line 217 "**Only the Risk Capacity Ledger may mutate capacity. The
>   event processor ... may propose a remap but SHALL NOT update capacity independently**"가 NT(event processor)를
>   **capacity-non-mutating**으로 봉인한다. **`tos.rcl`은 import하지 않는다**(형제; 주입 좌표로만).
> - [설계 #9 — Reconciliation Confidence 계약 (비준·구현)](2026-07-25-tos-reconciliation-confidence-design.md) + 코드
>   `tos/src/tos/recon/`. §7 per-field evidence·§5 confidence/contradiction는 recon 소관이다: `classify_field`
>   (`predicates.py:107`; 0-path⇒UNKNOWN·1⇒SINGLE_SOURCE·≥2 독립 동의⇒CORROBORATED·불일치⇒CONFLICTED·stale⇒STALE)·
>   `FieldConfidenceClass`(`vocabulary.py:26`)·**`SafetyRelevantField.{INSTRUMENT_IDENTITY, EXTERNAL_UNATTRIBUTED_
>   ACTIVITY}`(`vocabulary.py:81/83`, non-closed minimum set)**·`ConservativeBound`·`merge_conservative`
>   (`predicates.py:218`)·`any_field_conflicted`(`predicates.py:400`). NT §7 "evaluate each material field
>   independently"·§5 "evidence confidence and contradiction status per field"의 **per-field 신뢰도 분류 = recon**.
>   NT는 recon `classify_field`/`FieldConfidenceClass`를 **주입 소비**한다. **`tos.recon`은 import하지 않는다**(형제).
> - [설계 #8 — Orthogonal Trading State 계약 (비준·구현)](2026-07-25-tos-orthogonal-state-design.md) + 코드
>   `tos/src/tos/orthostate/`. §6 orthogonality("Non-trade event state SHALL remain orthogonal to order, exposure,
>   capacity, authority, and evidence-confidence state", NT line 123)의 order/transmission/knowledge/capacity 축은
>   orthostate 소관이다: `KnowledgeState`(`vocabulary.py:121`)·`BrokerOrderState`(`vocabulary.py:92`)·
>   `no_coupling_violation`(`predicates.py:206`, "no violation **detected** ... never certified fully legal")·
>   `reconstruct_conservative`(`predicates.py:688`, RECONCILED/CONSISTENT⇒CONFLICTED downgrade). NT의 event-workflow
>   축(§2.2-2 `NonTradeEventWorkflowState`)은 **별개 축**이며 orthostate 축과 붕괴하지 않는다(§2.2-5). **미import**(형제).
> - [설계 #19 (세션 A) — Venue Constraint·Order Admissibility 계약 (비준·구현)](2026-07-26-tos-venue-tradability-design.md)
>   + 코드 `tos/src/tos/venue/`. **NT §10 line 221의 명시 seam.** venue는 admissibility·material-change invalidation을
>   **이미 소유·구현**한다: **`material_change_closure`(`predicates.py:361`; §18 "any material change ... fences the
>   affected unconsumed decisions ... Invalidation SHALL reach approval, authority issuance, unconsumed
>   capabilities, and every final egress")**·`OrderAdmissibilityResult`(4토큰 truthy-untestable, `vocabulary.py:91`)·
>   `InstrumentRouteFields`(`records.py:83`; `canonical_instrument_id`·`multiplier`·`contract_month`·`expiration`·
>   `settlement_method`·`currency`)·`stale_decision_rejected_at_egress`(`predicates.py:529`). NT §10 line 221 "Every
>   material event, correction, or reversal SHALL invalidate affected ADR-002-019 ... requires a fresh exact order
>   decision"의 **invalidation closure = venue**. NT의 corporate action은 venue `material_change_closure`의 **change
>   trigger 입력**이다. **`tos.venue`는 import하지 않는다**(형제; NT-EV-003 주입 소비).
> - [설계 #10 Broker Capability (비준·구현)](2026-07-25-tos-broker-capability-design.md) + `tos/src/tos/brokercap/`.
>   §13 broker adjustment/open-order semantics는 brokercap 소관이다: **`CapabilityDimension.{CORPORATE_ADMINISTRATIVE_
>   EVENTS, OPEN_ORDER_QUERY}`(`vocabulary.py:81/74`)**·`ReplaceSemantics`(`vocabulary.py:202`)·`broker_capability_
>   sufficient`(`predicates.py:206`)·`external_detection_ok`(`predicates.py:412`; `B_external_detect`/`B_external_
>   contain` 주입). NT는 broker capability를 판정하지 않고 **주입 소비**한다(broker-agnostic). **미import**(형제).
> - [설계 #6 Safety Authority (비준·구현)](2026-07-23-tos-safety-authority-design.md)·[설계 #7 Live Authorization
>   (비준·구현)]·[설계 #17 Startup/Recovery (SBR, 비준·구현, 커밋 `9eb13bba`)]·[설계 #8 time(ADR-002-008)]. §17
>   authority invalidation·no-auto-re-arm = authority(`rearm_gate`)·liveauth(`no_automatic_rearm` `predicates.py:606`
>   "automatic re-arm prevented — always"·`authorization_revived_by_nothing` `predicates.py:777`); §19 recovery
>   obligations = sbr(`RecoveryObligation`·`recovery_inventory_complete` `predicates.py:136`·`restore_worst_credible_
>   union` `predicates.py:741`·`unknown_stays_conservative` `predicates.py:314`); §8 effective-time = time
>   (`freshness_verdict`·`effective_snapshot_age_bound`·`source_disagreement_within_bound`·`recovery_generation_
>   revives_nothing`·`snapshot_grants_no_authority`). NT는 전부 **주입 소비**한다. **미import**(형제).
> - **인접 비-소비 형제(명제 상이·phantom 방지 §0.4e)**: [설계 #? iap(ADR-002-023 Intent Authorization Provenance,
>   비준·구현)] `tos/src/tos/iap/`의 `ConsumptionOutcome.IDEMPOTENT_REPLAY`(`vocabulary.py:165`)는 **authorization-
>   token single-use consumption** idempotency(§12 line 313 "a duplicate **identical command** against an already-
>   ``CONSUMED`` **decision**")로 NT-EV-010의 **correction/reversal ECONOMIC-EVENT 재적용 무해성**과 **명제가 다르다**
>   (defect-class #3). NT는 iap를 **소비하지 않고** 자신의 event-idempotency를 canonical `classify_record_pair`에
>   앵커한다(§4.3·§0.4e). rcl `ApplyReason.IDEMPOTENT_REPLAY`(capacity-command idempotency)와도 별개 축이다 —
>   세 술어(iap authorization / rcl capacity-command / NT economic-event)는 **canonical `classify_record_pair`
>   원시의 세 하류**이며 상호 import하지 않는다.
>
> **비준 상태**: **2026-07-26 운영자 위임 자동 비준(v1.1) — 효력 발생**(표준지시 2026-07-25 + 본 세션 운영자
> "NT 사이클도 이어서 끝까지 진행" 지시). 경위: v1.0 저작 → 오케스트레이터 1차 심사 통과(소유권 3대 증거·상호
> 이연·NT-AC 12·VP 3키 실측) → **독립 비평 리뷰 REVISE(CRITICAL 2·MAJOR 8·MINOR 4·Gap 6** — C1 ∅-vacuous+
> disposition 생산자 부재·C2 APPLIED_ONCE 도달 불가+DIVERGENT_EMISSION 미매핑; 아키텍처 골격은 지지) → **v1.1
> 개정 전건 반영(§10.1)** — 개정 중 저작자 세션 한도 중단, 신규 에이전트가 디스크 상태 실측 후 잔여 완결(신설
> §6.3에서 자체 fail-open 검출·수정 포함) → 오케스트레이터 스팟체크 통과(disposition 생산자·구조 파생·3분기
> 접기·phantom 0 확인). **§10.3 판단 지점 전건 승인** — 핵심: edge 0·`tos.nontrade`·split 극성 구조 파생 승격·
> idempotency canonical 직접 앵커(5멤버 전수 매핑). 효력: `tos/src/tos/nontrade/` Phase 1(EV-L1) 착수 승인.
> 본 문서는 어떤 NT-EV·ADR acceptance·restricted-live·production도 승인하지 않는다(§0.2). ADR acceptance는
> 오직 *실행된* evidence로만 온다(project memory `tos-spec-rfc-authoring-track`; ADR §18 line 392·§26 line
> 502–514; VER-002-001 §5 "Registration is not execution").
>
> **리뷰 이력(선제 봉합 defect class)**: 시리즈 축적 REJECT/REVISE — #6 v1.0 REJECT(fail-open seam: vacuous-True)·
> #8 v1.0 REJECT(cross-section 혼동)·#10 v1.0 REVISE(seam 실측 오명명)·#13 ARE(사전 6→실측 5 core 정정)·#16 AFG
> v1.0 REVISE(CRITICAL 1[방향 반전]·MAJOR 9)·#18 PR v1.0 REVISE(CRITICAL 2[netting 극성·sufficiency 조달원 category-
> error]·MAJOR 6)·**#21 NT v1.0 REVISE(CRITICAL 2[`transition_envelope_complete` ∅ 무주 위임 = vacuous-True 경로·
> `RecordPairKind` 반전 매핑]·MAJOR 8·MINOR 4 — v1.1에서 전건 봉합, §10.1)**. **자기 사례가 시리즈에 편입됐다**:
> #6 v1.0의 vacuous-True와 #16 v1.0의 방향 반전이 본 문서 v1.0에서 각각 ∅-위임·kind-매핑 형태로 재발했다 —
> "선제 봉합 목록에 적어 두는 것"과 "술어 본문에서 강제하는 것"은 다르다는 교훈(v1.1 C1/C2). 본 문서가 **선제
> 봉합**한 defect class: (a) §1 core-tier 판정(NT-EV **3행** L1 슬라이스 보유·닫는
> NT-EV 0). (b) 소유권 중복 구조적 배제(§3.5 코드 실측 소유권 분할표). (c) fail-open seam 방지(중앙 술어 본질적
> fail-closed·양성 identity 증명·both-ways canary). (d) fixture clean-vs-illegal 정합. (e) cross-section
> self-consistency pass(§1↔§4/§5/§6↔§7). (f) verbatim 전사 + ADR line 병기(에라타 방지). (g) 실측-원천 결함 방지
> (모든 seam을 코드 실측 signature+라인; 인용 전 grep). (h) **방향 극성 검산**(split/reverse-split 수량·가격 배수
> 반대 방향 진리표 §4.5 — 본 ADR 후보). (i) **전사 완전성**(§5 13식별필드·§6 11워크플로상태·§9 10엔벨로프·§11 6구분·
> §13 7주문평가·§14 8파생레그·§17 8무효화경계·§18 8단계·§19 8복구의무 원문 항목 수 전수 대조 — #18 M3 확장). (j)
> **truthy-sentinel 극성 분기**: 양극성 bool|None(안전값=True)은 `is True`·음극성(안전값=False)은 `is False`만;
> StrEnum result는 identity(`is NONTRADE_ADMISSIBLE`); GRANT/complete류는 양성 conjunction identity로만 도달. (k)
> **∅-공허 양방향**(금지+허용 canary 둘 다). (l) **idempotency-중심 진리표·중복 적용 canary**(NT-EV-010 — 시리즈
> 최초의 idempotency-중심 L1 슬라이스 §4.6·§5.3, defect-class #9).
>
> **시리즈 규율 4건(#18 v1.1 신설 — 본 문서 전부 상속)**: (1) **truthy-sentinel 극성 분기**(음극성 필드에 `is False`
> 강제); (2) **카운트 대조 전수화**(모든 열거 리스트에 항목 수 병기·개별 계수); (3) **§3.4 seam 표에 "형제 술어
> docstring 명제 ↔ ADR 조항 명제 동일성" 열**(명제 상이 시 좌표-의존 이연으로 강등 — iap idempotency exemplar §0.4e);
> (4) **§-row 매핑을 normative 문장 단위로**(NT §10 line 217/219/221이 한 조항에 3규범을 담은 사례).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-010 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). **core(L1 슬라이스) / predicate-only / not-Phase-1(형제
   소유·런타임 이연) 3분류.** **결정적 사실(register 실측·CSV-aware 파싱)**: `NT-EV` 12행 중 **3행(001·002·010)이
   register 최소 레벨에 `EV-L1` 슬라이스 보유** — 001(`EV-L1/3+Broker`, "Split and Reverse-Split Transition")·002
   (`EV-L1/3`, "Multi-Leg Merger and Spin-Off")·010(`EV-L1/3`, "Correction and Reversal Idempotency"). **오케스트
   레이터 사전 카운트 "L1 슬라이스 3행 = 001·002·010"은 실측 결과 정확**하다(정정 없음). 나머지 9행: 003
   (`EV-L2/3`)·004·005·008(`EV-L3+Broker`)·006(`EV-L3/5`)·007(`EV-L2/3`)·009·011·012(`EV-L3`) — 전부 L1 슬라이스
   부재. **닫는 NT-EV = 0건**(L1 슬라이스 저작 ≠ EV closure: `/3`·`+Broker` 잔여). "**EV-L1-complete 주장 금지**".
   **주의(sibling 서사 상속 금지 defect-class #3)**: NT의 L1 집합 {001·002·010}은 #18 PR의 L1 집합 {001·005}과
   **다르다** — NT-EV-005(Futures Expiry/Settlement)는 `EV-L3+Broker`로 L1 슬라이스 부재이며 PR-EV-005(partial-fill,
   L1)와 **좌표가 무관**하다.
2. **non-trade 5-어휘 + 워크플로 데이터 모델**(§2, **core substrate**): `NonTradeEventClass`(§4, 5종:
   `CORPORATE_ACTION`·`LIFECYCLE`·`ADMINISTRATIVE_BROKER`·`INSTRUMENT_TRADABILITY`·`UNRECOGNIZED_EXTERNAL`)·
   `NonTradeEventWorkflowState`(§6, 8 linear + 3 branch = 11종 verbatim)·`CredibleTransitionLegKind`(§9, 10종
   verbatim)·`SplitTransformationKind`(§11, 2종 `FORWARD_SPLIT`/`REVERSE_SPLIT`)·`TransformationDirection`(3종
   `AMPLIFY`/`ATTENUATE`/`IDENTITY` — NT-local 극성 축)·`CorrectionReversalOutcome`(6종)·`NonTradeDisposition`(로컬
   결과 StrEnum, truthy-untestable) 어휘 + digest-bound `NonTradeEventRecord`(§5 IndependentIdArtifact)·
   `CorrectionReversalRecord`(§10 IndependentIdArtifact)·`TransitionEnvelope`(§9 value)·`SplitTransformationSpec`
   (§11 value) + all-false `NonTradeAuthorityEffect`(§6 line 144). Generation은 `tos.ordering` 좌표(§3.2 — #13/#16/#18
   동형, 별도 heavy 아티팩트 아님).
3. **transition-envelope completeness + no-netting 중앙 불변식**(§4.1/§5.1, **NT-EV-002 core L1 슬라이스** — ADR §9·
   NT-AC-002): `transition_envelope_complete(...) -> bool`. **모든 credible transition leg(§9 line 185–194, 10종)이
   envelope에 포함**되고 **old와 new economic effect가 둘 다 계상(favorable netting 부재)**될 때만 True. ADR §9 line
   196 verbatim "Favorable effects SHALL NOT be netted against uncertain adverse effects." merger/spin-off multi-leg
   worst-credible-envelope의 완전성 지점(§0.4d 이중 계상 정합). **∅은 caller 위임이 아니라 술어 내부 구조 가드다
   (C1)**: `if not required_legs: return False` — 빈 required set은 "증명할 것이 없다"가 아니라 "무엇을 증명해야
   하는지 모른다"이므로 vacuous-True로 흐르지 않는다(rcl `credible_union_capacity` empty⇒`ValueError` 선례,
   `rcl/predicates.py:768`).
4. **split/reverse-split 방향 극성 coherence 중앙 불변식**(§4.2/§4.5/§5.2, **NT-EV-001 core L1 슬라이스** — ADR §11·
   NT-AC-001): `split_polarity_coherent(...) -> bool` + `transformation_residual_conservative(...) -> bool` +
   **`transformation_units_and_rounding_explicit(...) -> bool`(M1 신설)**. **quantity 방향과 price/basis 방향이 서로
   reciprocal(반대)**이고 declared kind와 일치할 때만 coherent(§4.5 진리표); fractional entitlement·cash-in-lieu
   residual이 explicit·present·capacity-consuming(§11 line 240)일 때만 conservative; **exact unit spec·rounding
   rule이 둘 다 not-None**일 때만 explicit(§11 line 227 verbatim "Every transformation SHALL specify exact units and
   rounding rules"). **방향 극성 함정(사전 브리핑 후보)**: 분할/역분할의 수량·가격 배수가 **같은 방향**이면 부호 오류
   (fail-open) — 진리표로 검산(§4.5). **극성 입력은 caller 선언 flag가 아니라 구조 파생(M2)**: `SplitTransformation
   Spec`이 `pre_quantity`/`post_quantity`·`pre_basis`/`post_basis`(`CanonicalDecimal|None`)를 담고 각 방향을
   **multiplicative identity 대비 비교**로 파생한 뒤(post > pre ⇒ `AMPLIFY`·< ⇒ `ATTENUATE`·= ⇒ `IDENTITY`; 특정
   배수 하드코딩 0) declared kind와 대조하므로, caller가 direction enum을 위조해도 pre/post magnitude와 어긋나면
   fail-closed다. 어느 magnitude든 None ⇒ 파생 불가 ⇒ fail-closed(§4.7).
5. **correction/reversal idempotency + lineage 중앙 불변식**(§4.3/§4.6/§5.3, **NT-EV-010 core L1 슬라이스** — ADR
   §10 line 219·§16 line 313·NT-AC-010): `correction_reversal_idempotent(...) -> CorrectionReversalOutcome`.
   **supersedes lineage present** + **history preserved(append-only; `original_retained is True` 양극성)** +
   **at-most-once application**일 때만 정당 적용. **canonical `classify_record_pair` 실측 매핑(C2)** — 시그니처는
   **4-positional + 2-keyword**(`(a_identity, a_digest, b_identity, b_digest, *, a_idempotency_id,
   b_idempotency_id)`, `canonical/record_pair.py:52`)이고 반환 매핑은: same id/key·**same** bytes ⇒
   `IDEMPOTENT_DUP`(:94/:101) no-op · same **primary** id·**diff** bytes ⇒ `CRITICAL_CONFLICT`(:96) reject ·
   same **idempotency** id·**diff** bytes ⇒ `DIVERGENT_EMISSION`(:103) reject — **두 위조 축은 별개 kind이며 둘 다
   `REJECTED_CONFLICT`로 접힌다** · `DISTINCT`(:105)/`NOT_COMPARABLE`(digest None, :87) ⇒ `REJECTED_UNKNOWN` ·
   **`prior is None`(첫 정정)은 classify 선행 게이트**로 `APPLIED_ONCE`(§5.3). **시리즈 최초 idempotency-중심 L1
   슬라이스**: 재적용 무해성·중복 적용 canary(§4.6 진리표·§7).
6. **workflow label-grants-nothing 불변식**(§4.4/§5.4, core substrate — ADR §6 line 144): "No workflow state by
   itself releases capacity, closes an instrument, proves final quantity, or grants authority." all-false
   `NonTradeAuthorityEffect` + orthogonality 규율(§6 line 123 "SHALL remain orthogonal to order, exposure, capacity,
   authority, and evidence-confidence state").
7. **NT ↔ 12-생산자 형제 경계(중심 아키텍처)**: NT는 **sibling edge 0건**을 유지한다(§0.4b/§3.4; protective #11·
   replacement #18 동형). NT는 (i) envelope-completeness/polarity-coherence/idempotency **결정을 생산**하고 미래
   Reconciliation Service/rcl-remap-admission/venue-invalidation/final-egress 런타임이 소비하며, (ii) rcl
   `RECOGNIZED_EXTERNAL_CHANGE`/`credible_union_capacity`/`CapacityState`·are `worst_intermediate_risk`/`credible_
   space_bounded`/`EXTERNAL_TRAPPED_NONTRADE_CONCURRENT`·venue `material_change_closure`/`OrderAdmissibilityResult`·
   recon `classify_field`/`FieldConfidenceClass`·orthostate `KnowledgeState`/`no_coupling_violation`·brokercap
   `CORPORATE_ADMINISTRATIVE_EVENTS`/`external_detection_ok`·replacement `overlap_first_reservation_complete`·
   authority/liveauth `no_automatic_rearm`·sbr `restore_worst_credible_union`·time `freshness_verdict`를 **주입
   좌표/produced-bool로 소비**한다. **`tos.canonical`·`tos.ordering`(둘 다 core)만 import**한다(§0.3). **PROMOTE
   0건. sibling edge 0건. `CapacityVector`/`ProjectedCell` REUSE 미채택**(§0.4c 검토 후 기각).
8. **fail-closed 규율 + named both-ways canary**(§4): 미포함 leg ⇒ incomplete; **favorable netting 미증명(구조적
   magnitude 병존 부재) ⇒ False**; 극성 non-reciprocal ⇒ 부호오류·INVALID; unit/rounding 미명시 ⇒ INVALID(§11 line
   227); residual absent ⇒ incomplete; lineage absent ⇒ REJECTED_NO_LINEAGE; **same-primary-id·diff-bytes
   (`CRITICAL_CONFLICT`) 및 same-idempotency-key·diff-bytes(`DIVERGENT_EMISSION`) 둘 다 ⇒ REJECTED_CONFLICT**
   (double-apply 금지); `original_retained is not True`(overwrite) ⇒ REJECTED_OVERWRITE; capacity
   release-on-transformation ⇒ **판정 자체가 구조적 부재**(NT에 release 필드·술어 없음 — rcl-only §10 line 217);
   UNKNOWN/CONFLICTED field ⇒ block new risk; **빈 leg set·빈 required set·빈 change-trigger set·None magnitude·
   None direction ⇒ 보수적 UNKNOWN/BLOCK/TRAPPED**(∅-공허, §4.7 — **양방향** 명시). 각 가드에 both-ways canary.
   **truthy-sentinel 극성 분기(시리즈 규율 1)**: `NonTradeDisposition`/`CorrectionReversalOutcome`/venue
   `OrderAdmissibilityResult`/recon `FieldConfidenceClass`는 **identity 게이트**; **양극성 bool|None(안전값=True)은
   `is True`만** — Phase-1 NT 양극성 필드 = `original_retained`·`identity_transition_final`·(주입)
   `source_disagreement_bounded`·`credible_space_bounded`·`protective_action_may_proceed`; **완화-분기 조건 필드
   (안전값=True인 materiality)**: `event_is_material`은 **미지(None)를 material로 취급**하고 면제(완화)는 오직
   `is False`(non-materiality의 positive 증명)로만 얻는다(§6.3 — venue §5.8 "Unknown materiality is material",
   `venue/predicates.py:379`); **음극성 bool|None
   (안전값=False)은 `is False`만**(음극성에 `is not True` 금지)이나 **Phase-1 NT 모델의 음극성 필드는 0건이다(정직
   공개, M7)** — no-netting·overwrite·release는 flag가 아니라 각각 **구조적 magnitude 병존 파생**(§0.4d)·**양극성
   `original_retained`**(§5.3)·**필드 부재**(§4.2-3)로 실현되므로 음극성 규율은 상속하되 본 문서에서 vacuous하게
   성립한다. **완료/허용 결과는 잔여 fall-through가 아니라 양성 conjunction identity 증명으로만 도달**(#16 CRITICAL
   교훈). 단 **no-netting·polarity·unit/rounding은 flag 극성이 아니라 구조적 파생**으로 증명한다(§0.4d — #18
   no-netting 선례).
9. **property-test 하네스 타깃**(§7, §1 분류 정렬) + import-closure 검증(§7.1, **allowlist 형식**) + run manifest
   7항목(§7.2) + fixture clean-vs-illegal 정합(#8 교훈) + seam cross-check(test-only, §3.4) + **hypothesis 전략에
   forgery/∅/double-application 케이스 명시 포함**(§7).
10. **bounds 주입 계약 + Phase-0 이관**(§8): NT decision 구조에는 numeric bound 부재(전부 enum·boolean·집합 논리·
    주입 `CanonicalDecimal`); ADR §8/§15가 요하는 timing bound는 **VP-002에 3 NT-전용 키 실재·null**(`B_non_trade_
    event_detect` line 646·`B_non_trade_transition_apply` line 653·`B_non_trade_reconcile` line 660 — §8.1 실측)이며
    **confirmed candidate 신규 키 0건**(#10/#13/#16/#18형); per-source/per-broker 수치는 Broker Capability Profile·
    reference-source INSTANCE(§7 line 163·VP 주석 "APPROVE per source and broker capability profile"). 값 승인은
    Bounds-Approver 게이트(3키 전부 `owner: TBD` — VP-002 line 649/656/663 실측).
11. **단일 disposition 생산 술어**(§5.5, **C1 신설**): `nontrade_disposition(...) -> NonTradeDisposition`. §4.7
    ∅-공허 표의 **모든 행이 이 술어의 반환값으로 재매핑**되어 "빈 입력은 별도 처리에 위임"이라는 미결 위임이
    사라진다. 5-member 전순서 우선순위(`NONTRADE_CONFLICTED` > `NONTRADE_QUARANTINED_UNKNOWN` > `NONTRADE_TRAPPED`
    > `NONTRADE_BLOCK_NEW_RISK` > `NONTRADE_ADMISSIBLE`)로 결정적이며, `NONTRADE_ADMISSIBLE`은 잔여 fall-through가
    아니라 **양성 conjunction identity 증명**으로만 도달한다(§5.5).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §26 line 502 "This ADR
  SHALL remain **Proposed** until all of the following are complete"·line 514 "Authorship of this ADR does not
  prove non-trade-event safety and does not authorize restricted-live or production operation"·§18 line 392
  "Written cases, event catalogs, and successful replay are not completed evidence. Acceptance requires registered,
  executed, retained, and independently reviewed evidence under VER-002-001." **닫는 NT-EV = 0건.**
- **capacity 산술(commit/consume/release·remap·transfer·aggregate envelope·credible union)을 저작하지 않는다.**
  그것은 **rcl(#5, ADR-002-002/012)이 이미 소유·구현**했다 — `credible_union_capacity`·`CapacityState`·`Transition
  Cause.RECOGNIZED_EXTERNAL_CHANGE`·`CommandType.{CREATE_EXTERNAL_QUARANTINE,MARK_TRAPPED_EXPOSURE}`·`WEAK_CAUSES`.
  ADR §1 line 19 verbatim "The Risk Capacity Ledger remains the sole authority that reserves, commits, releases,
  transfers, or remaps capacity"·§10 line 217 "Only the Risk Capacity Ledger may mutate capacity. The event
  processor, instrument master, projection, reconciliation, or recovery components may propose a remap but SHALL NOT
  update capacity independently." NT은 event·leg 완전성을 판정하고 rcl이 capacity를 remap/commit한다(§0.4d).
- **aggregate-risk 투영·Adverse Scenario Set·credible-state-space risk를 산출하지 않는다.** 그것은 **are(#13,
  ADR-002-021)가 이미 소유·구현**했다 — `worst_intermediate_risk`·`credible_space_bounded`·`envelope_bound_not_
  enlarged`·**`AdverseScenarioKind.EXTERNAL_TRAPPED_NONTRADE_CONCURRENT`**·`RiskDimensionKind.{OPTION_GREEKS_EXERCISE_
  ASSIGNMENT,SETTLEMENT_CASH_CURRENCY}`. ADR §9 line 196 "Risk capacity SHALL cover the maximum aggregate risk across
  the envelope"의 **risk 수치 = are 주입**(§0.4d). NT은 envelope leg 열거만 소유한다.
- **material-change invalidation·order admissibility·instrument-route 재평가를 저작하지 않는다.** 그것은 **venue
  (#19, ADR-002-019)가 이미 소유·구현**했다 — `material_change_closure`·`OrderAdmissibilityResult`·`InstrumentRoute
  Fields`·`stale_decision_rejected_at_egress`. ADR §10 line 221 "Every material event, correction, or reversal SHALL
  invalidate affected ADR-002-019 Venue Constraint Snapshots and Order Admissibility Decisions ... requires a fresh
  exact order decision before future transmission." NT의 corporate action은 venue `material_change_closure`의 change
  trigger **입력**이다(NT-EV-003 주입 소비).
- **per-field evidence 신뢰도 분류·reconciliation confidence를 재저작하지 않는다.** 그것은 **recon(#9, ADR-002-006)
  이 이미 소유·구현**했다 — `classify_field`·`FieldConfidenceClass`·`SafetyRelevantField.{INSTRUMENT_IDENTITY,
  EXTERNAL_UNATTRIBUTED_ACTIVITY}`·`ConservativeBound`·`any_field_conflicted`. NT §7 "The Reconciliation Service
  SHALL evaluate each material field independently"이 명시적으로 **Reconciliation Service(recon)**로 이연한다. NT은
  field-confidence를 **주입 소비**한다.
- **order/transmission/knowledge/capacity 상태 축·orthogonality를 재저작하지 않는다.** 그것은 **orthostate(#8,
  ADR-002-005)가 이미 소유**했다 — `KnowledgeState`·`BrokerOrderState`·`no_coupling_violation`·`reconstruct_
  conservative`. NT의 `NonTradeEventWorkflowState`(§6)는 **별개 축**이며 orthostate 축을 **주입 좌표**로 소비한다
  (좌표 비붕괴 §2.2-5). ADR §6 line 123이 명시 orthogonality를 요구한다.
- **protective-order cancel/replace·gap/overlap 메커니즘을 저작하지 않는다.** 그것은 **replacement(#18, ADR-002-011)
  이 이미 소유·구현**했고 NT §13 line 272가 명시 이연했다 — "**If protective coverage must be changed, ADR-002-011
  governs cancellation, replacement, gap, overlap, and capacity.**" NT-EV-006(Broker Open-Order Adjustment, L3/5)이
  접점이며 NT은 replacement `overlap_first_reservation_complete`·brokercap `ReplaceSemantics`·orthostate
  `BrokerOrderState`를 **주입 소비**한다(§3.5).
- **authority invalidation·re-arm·recovery obligation·trustworthy-time·obligation-lifecycle을 저작하지 않는다.**
  §17 authority/re-arm = authority/liveauth(`no_automatic_rearm`·`authorization_revived_by_nothing`), §19 recovery
  = sbr(`RecoveryObligation`·`restore_worst_credible_union`), §8 time = time(ADR-002-008), §16 line 309 **obligation-
  lifecycle serialization = ADR-002-030(PTOL)**. ADR §16 line 309 verbatim "This ADR owns the **non-trade event and
  transformation identity**; ADR-002-030 owns the **obligation-lifecycle serialization**." NT은 event·transformation
  identity만 소유하고 PTOL을 저작하지 않는다.
- **final egress·transmission·election instruction·containment 실행을 저작하지 않는다.** ADR §1 line 19 "The Broker
  Adapter/Egress Gateway remains the final enforcement point"·§15 line 299 "An operator selection, UI action, or
  reference-data flag SHALL NOT itself transmit an instruction." NT은 결정 bool·완전성 판정·workflow 레코드만 반환
  하며 **전송·capacity mutate·admissibility 발급·containment 실행을 하지 않는다**(§4.4; label-grants-nothing).
- **numeric event/freshness/reconciliation/settlement bound를 승인하지 않는다.** ADR §25 line 493 "Which numeric
  pre-event, reconciliation, settlement, and evidence-freshness bounds will be approved?"는 Open Question이다. 전부
  주입 `CanonicalDecimal`로 담고 **어떤 숫자도 하드코딩하지 않는다**(CLAUDE.md). 값 부재 ⇒ fail-closed. 값 승인은
  Bounds-Approver 게이트(§8·§9.2).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

신규 NT 패키지 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도 import하지
  않는다** — non-trade 결정 규칙은 StrEnum·boolean·집합 논리이고 수치는 `CanonicalDecimal` 산술(비교·`is_finite`·
  scale-normalize·multiplicative-identity 대조)뿐이며, 모든 event/freshness/settlement bound·broker limit·aggregate-
  risk 값은 주입 파라미터이고 YAML 파싱은 하네스(설계 #3) 소관이다(closure 최소화 — #5–#19 §0.3 동형).
- tos 자기 자신: `tos.canonical`(`FrozenModel`·`DigestBoundArtifact`·**이미 core인 `IndependentIdArtifact`**·
  **이미 core인 `classify_record_pair`**·`RecordPairKind`·`ArtifactStatus`·**이미 core인 `CanonicalDecimal`**),
  `tos.ordering`(non-trade event·correction·reversal append-only 순서 — §3.2), 자기 자신 모듈. **canonical/ordering
  외 모든 현재·미래 tos 형제(현재 committed 22개: canonical·capsule·evidence·time·ordering·dsl·rcl·authority·
  liveauth·orthostate·recon·brokercap·spg·protective·are·ioc·iap·sbr·venue·afg·replacement·**hag**[커밋
  `873744b3` — 21→22])를 import하지 않는다** (default-deny — 규칙을 열거가 아닌 "canonical·ordering 외 전부 금지"로
  서술; produced-bool·주입 좌표로만 참조 — §3.4/§3.5). **`tos/src/tos/hag/`(ADR-002-015 Human Safety Authority,
  세션 A, 커밋 `873744b3`)는 이제 committed 형제이나 import하지 않는다**(sibling edge 0; NT은 hag를 소비·생산하지
  않음). **PROMOTE 0건. sibling edge 0건.**
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이 `shared.config.secrets`
  (→ `os.environ`)를 무조건 전이 import한다. NT 패키지는 어떤 `shared.*`도 필요로 하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`, `shared.storage`,
  `shared.backtest`, `services.*`, `cli.*`(`.importlinter` forbidden set).
- **firewall 구조 확인(실측 — #11/#16/#18 §0.3 상속)**: `.importlinter`는 `[importlinter:contract:tos-operational-
  firewall]` type=forbidden·source_modules=`tos` 단일 계약이며 `layered`가 아니다 — intra-tos sibling→sibling edge는
  구조적으로 금지되지 않고 설계 #1 §3.2 "자기 자신 `tos.*`" 허용 조항이 커버한다. **신규 NT 패키지는 firewall 도구
  무수정 자동 포섭**된다(forbidden 계약이 source=tos 전체를 덮으므로). 본 문서는 그럼에도 **sibling edge 0건**을
  **설계 규율**로 유지한다(§0.4b) — protective #11·replacement #18 동형.
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(**allowlist 형식** — `import` 후 `sys.modules`의
  top-level `tos.*` ⊆ {`tos.canonical`, `tos.ordering`, 자기 자신} assert + `shared.config`·`os.environ`·numpy/
  pandas/yaml 부재 assert). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST +
  `.importlinter` layer-② 전이)와 함께 green이어야 §0.3 선언이 능동 성립.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/nontrade/`.** register domain(EVIDENCE-REGISTER-002 "**Non-Trade Events**")·
prefix `NT`(`NT-EV`/`NT-AC`)·ADR 제목 변별 토큰 "**Non-Trade**"를 명명 근거로 삼는다. 명명 대안 비교(#11 §0.4a·#16
§0.4a·#18 §0.4a 형식):

- **`tos.nt`(register prefix 직결)(고려·차점)**: `NT-EV` prefix와 직접 일치하고 대부분 형제가 register 두문자
  (rcl/spg/are/afg/ioc/iap/sbr)이므로 정합적이다. 그러나 "NT"는 Windows NT 통용으로 **mildly cryptic**하며, #18이
  `pr`(pull request/public relations)을 정확히 "cryptic" 이유로 기각한 선례와 방향이 같다. `nt`의 외부 충돌 심각도는
  `pr`보다 낮으나 semantic 명료성은 `nontrade`가 우월하다. **운영자 치환 가능**(load-bearing 아님).
- **`tos.corpaction`(기각·좁음)**: ADR 제목 첫 절 "Corporate Actions"만 명명해 지나치게 좁다 — 본 ADR은 corporate
  action뿐 아니라 lifecycle(§4.2)·administrative/broker(§4.3)·instrument/tradability(§4.4)·unrecognized external(§4.5)
  까지 5종 event class(§4)를 포함한다.
- **`tos.event`(기각·generic collision)**: "event"는 generic하고 ordering/evidence의 append-only "event"와 의미 충돌.
- **`tos.external`(기각·좁음/모호)**: unrecognized external change(§4.5)만 강조해 corporate action/lifecycle을 누락한
  인상을 준다.
- **선택 `tos.nontrade`**: **ADR 변별 토큰 "Non-Trade" + register domain "Non-Trade Events" 직접 명명**, non-cryptic,
  명사형. #18이 register prefix(`pr`)를 semantic 토큰(`replacement`)으로 교체한 것과 동형 판정 — semantic 토큰 우선.
  terse 관행(canonical/capsule/rcl/recon/spg/are/afg/venue)보다 다소 길지만 orthostate/brokercap/liveauth/replacement
  선례로 수용 가능. **naming은 load-bearing이 아니다**(설계 #1 line 164) — 운영자가 `tos.nt`로 치환 가능. 실측:
  `tos/src/tos/nontrade`·`tos/src/tos/nt`·`tos/src/tos/corpaction` 부재(ls exit 1; git ls-files 0건 — 충돌 없음).
  내부 module(`_base.py`·`vocabulary.py`·`records.py`·`predicates.py`·`state.py`)은 recon/orthostate/venue/replacement
  선례 동형.

**(b) nontrade = produced-bool producer, sibling edge 0건 (중심 결정 — protective #11·replacement #18 동형, 코드
실측).** NT은 미래 소비자(Reconciliation Service·rcl remap-admission·venue material-change-invalidation·final-egress
런타임)의 **상류**다 — envelope-completeness/polarity-coherence/idempotency **결정을 생산**하고, 상류 형제(rcl·are·
venue·recon·orthostate·brokercap·replacement·authority·liveauth·sbr·time)가 생산한 값을 **주입 소비**한다. seam 대안
비교(#11 §0.4b·#18 §0.4b 형식):

- **대안 A — NT이 소비자(rcl)를 import해 remap을 직접 커밋**: **기각**. ADR §10 line 217 "the event processor ...
  may propose a remap but SHALL NOT update capacity independently." NT은 remap을 **제안(propose)**할 뿐 capacity를
  mutate하지 않는다. NT 산출물은 completeness/coherence/idempotency **bool·`NonTradeDisposition`**이며 rcl
  `RECOGNIZED_EXTERNAL_CHANGE` transition이 그것을 소비한다(are/afg가 GRANT decision을 rcl로 흘린 것과 방향은 유사
  하나 NT은 decision-ref slot이 아니라 completeness 가문 — 아래 (c)). ⇒ rcl import 불요.
- **대안 B — 소비자가 NT을 import**: rcl/venue/replacement가 NT을 직접 호출. **기각**: 이 형제들은 **이미 비준·구현**
  됐고 non-trade 조건을 주입 슬롯(rcl `TransitionCause.RECOGNIZED_EXTERNAL_CHANGE`·venue `material_change_closure`의
  change-trigger 인자·replacement `overlap_first_...`의 주입 좌표)으로 이미 봉인했다. ratified 패키지를 NT 의존으로
  바꾸면 침습이며 acyclic이 깨진다.
- **선택 — decoupled, plain-bool producer(edge 0건)**: NT은 자신의 어휘·워크플로 모델·결정 술어를 저작하고, 출력은
  plain `bool`/StrEnum(`NonTradeDisposition`·`CorrectionReversalOutcome`)으로 미래 소비자 signature와 타입 일치;
  소비 방향도 rcl/are/venue/recon/orthostate/brokercap/replacement 산출을 **주입 `bool|None`/StrEnum/`CanonicalDecimal`**
  로 소비하고 형제를 import하지 않는다. 근거: (i) **최인접 상류 protective #11·replacement #18이 정확히 이 형태**
  (produced-bool·edge 0)이며 본 ADR과 소유권이 인접하다 — 일관성. (ii) ADR §10 line 217이 NT을 capacity-non-mutating
  으로 봉인 — NT은 remap-proposer이지 committer가 아니다. (iii) edge 0·cycle 원천 차단. (iv) **compose seam-sealing**:
  타입 일치 + fail-closed 정합, **test-only** 모듈이 NT·(각 상대)를 둘 다 import해 polarity·fail-closed 대조(테스트
  import는 §7.1 package closure 불계상).

**(c) `CapacityVector`/`ProjectedCell` REUSE(edge-1) 검토 후 기각 — edge 0 (핵심 아키텍처, 사전 브리핑 "이중 계상·
split 극성" 응답).** transition envelope(§9)이 rcl `CapacityVector`(`vector.py:74`) 또는 are `ProjectedCell`
(`records.py:135`)를 REUSE해야 하는지 검토:

- **REUSE 찬성 근거**: ADR §9 line 196 "Risk capacity SHALL cover the maximum aggregate risk across the envelope" —
  are `worst_intermediate_risk`가 envelope risk를 투영하고 rcl `credible_union_capacity`가 capacity union을 커밋하므로,
  NT이 envelope leg를 `ProjectedCell`/`CredibleHistory`로 조립해 넘긴다고 볼 수 있다.
- **기각 근거(edge 0)**: (i) **NT의 L1-decidable 핵심은 vector/cell 산술이 아니다** — leg-completeness(10종 set 논리)·
  **no-netting(구조적 magnitude 병존 파생, §0.4d)**·**polarity-coherence(reciprocal 방향 enum 관계, §4.5)**·
  idempotency(canonical `classify_record_pair`)이며, worst-intermediate-risk 투영·credible-union 합산은 are/rcl
  소유이고 NT은 그 verdict/scalar를 **주입 소비**한다(§5.1). L1 결정에 rcl `CapacityVector`·are `ProjectedCell`
  **타입 자체가 불필요**하다. (ii) **are는 이미 non-trade 시나리오 축을 소유**한다 — `AdverseScenarioKind.EXTERNAL_
  TRAPPED_NONTRADE_CONCURRENT`(`vocabulary.py:115`) — NT이 `ProjectedCell`을 REUSE하면 are scenario/dimension
  namespace와 좌표 충돌(§2.2-5). (iii) **rcl `credible_union_capacity`가 empty-fail-closed·no-last-write-wins를 이미
  구현**(`predicates.py:739`) — NT이 union 산술을 재저작하면 권위 중복. (iv) **최인접 상류 protective #11·replacement
  #18이 edge 0**(reservation/envelope를 다루면서도 `CapacityVector` 미REUSE) — NT도 동형. ⇒ **edge 0·PROMOTE 0·
  sibling edge 0**. **운영자 판단 지점(§10.3-1)**: (a) `ProjectedCell`/`CapacityVector` REUSE(edge-1) vs **(b) plain-
  type leg-record producer(edge-0, 채택)** — 미래 런타임에서 NT이 cell/vector를 직접 조립해야 하면 (a)로 승격 가능
  하나 Phase-1은 (b)로 충분하다. NT의 leg magnitude는 `CredibleTransitionLegKind→CanonicalDecimal|None` 매핑 value로
  로컬 표현한다(are/rcl 좌표 미충돌).

**(d) transition-envelope "old+new 동시 계상" ↔ rcl/are 이중 계상 정합 (핵심 설계 판정 — #18 §0.4d 동형).** 사전
브리핑이 지목한 "split 배수 방향 극성·이중 계상" 핵심 지점. 판정:

- **이중 계상은 결함이 아니라 보수적 요구다.** transition 중 old instrument와 new instrument는 identity transition이
  final이 되기 전까지 **둘 다 active**하며(§9 line 187 "both old and new instruments when identity transition is not
  final"·§12 line 248 "Both identities remain active in the transition envelope until broker and reference-data
  evidence establish the final mapping"), worst credible state는 **둘 다 exposure**를 포함한다. 순진한 회계는 old를
  new로 **netting**(상쇄)하지만, transition envelope에서는 **netting 금지** — ADR §9 line 196 verbatim "Favorable
  effects SHALL NOT be netted against uncertain adverse effects."
- **정합 메커니즘 — no-netting을 구조적 magnitude로 파생(edge-0 유지, #18 M6 처방(b) 동형)**: `TransitionEnvelope`은
  leg별 **주입 `CanonicalDecimal|None` magnitude**를 담는다(`pre_event_exposure`·`post_event_credible_exposure`·
  `fractional_residual`·`cash_in_lieu` 등 §9 10 leg). **no-netting은 flag가 아니라 파생 성질**이다: `favorable_
  netting_absent`는 **pre_event_exposure·post_event_credible_exposure가 둘 다 present(not None)·비음수로 별개 병존**
  할 때만 True — netting을 적용하면 old를 new로 상쇄해 둘 중 하나가 소거되므로, 둘이 **별개 비음수 magnitude로 병존**
  하면 netting은 구조적으로 불가능하다(caller가 flag로 위조 불가). 하나라도 None/음수 ⇒ netting 의심/incomplete ⇒
  fail-closed. **NT의 소유**: (i) envelope이 **10종 credible leg 전부 포함**(`transition_envelope_complete` — set
  완전성), (ii) **구조적 no-netting 파생**(pre+post magnitude 병존·비음수). **NT이 소유하지 않는 것**: 합산 산술·
  hard-envelope 비교(rcl `credible_union_capacity`)·aggregate-risk 투영(are `worst_intermediate_risk`). "conservatively
  account all credible old and new economic effects"(§1 line 26)는 **구조적으로 이중 계상된(netting-불가) envelope이
  rcl union·are risk로 흐름**을 의미한다 — NT은 completeness+구조적-no-netting을 강제하고 rcl/are가 합산·risk를 강제
  한다. **split 배수 방향 극성(§4.5)**: `split_polarity_coherent`가 quantity/basis 방향의 reciprocal 관계를 enum-
  구조로 검산하되(부호 오류 fail-open 차단), 실제 배수 arithmetic 적용은 rcl remap 런타임이며 NT은 방향 coherence·
  residual explicitness만 판정한다. **좌표: NT leg magnitude(transition 축) → rcl이 dimension별 union·commit·are가
  risk 투영** (§0.4c 좌표 충돌 회피로 NT은 `CapacityVector`/`ProjectedCell` 타입 미REUSE).
- **좌표 비붕괴**: NT `CredibleTransitionLegKind`(transition 축) ≠ are `RiskDimensionKind`/`AdverseScenarioKind`
  (aggregate-risk 축) ≠ rcl `CapacityVector.dimension_id`(경제 capacity 축) ≠ replacement `CredibleIntermediate
  OutcomeKind`(replacement-order 축). 토큰 겹칠 수 있으나 별개 타입(§2.2-5).

**(e) event-idempotency 명제 = NT 고유, iap/rcl과 별개 (phantom-edge 방지 — defect-class #3).** NT-EV-010의
correction/reversal idempotency가 iap `ConsumptionOutcome.IDEMPOTENT_REPLAY`를 소비하는지 판정:

- **iap 명제(실측 docstring)**: `ConsumptionOutcome.IDEMPOTENT_REPLAY`(`iap/vocabulary.py:165`, ADR-002-023 §12
  line 313) = "a duplicate **identical command** against an already-``CONSUMED`` **decision**: the same record is
  returned, no new Intent" — **authorization-token single-use consumption** idempotency.
- **NT 명제**: NT-EV-010(ADR §10 line 219·§16 line 313·NT-AC-010) = correction/reversal **ECONOMIC-EVENT 재적용
  무해성**(동일 correction event를 2회+ 적용해도 economic effect가 1회만 발생·history 보존).
- **판정**: **명제가 다르다**(authorization-consumption ≠ economic-event-application). ⇒ NT은 iap를 **소비하지 않고**
  자신의 `correction_reversal_idempotent`를 **canonical `classify_record_pair`(`RecordPairKind.IDEMPOTENT_DUP`/
  `CRITICAL_CONFLICT`, `record_pair.py:31/41/43`)에 앵커**한다. iap(authorization)·rcl `ApplyReason.IDEMPOTENT_REPLAY`
  (capacity-command)·NT(economic-event)는 **canonical `classify_record_pair` 원시의 세 독립 하류**이며 상호 import
  하지 않는다 — 구조 동형(isomorphic)이나 좌표 상이. 이 판정이 phantom edge(iap import)를 차단한다.

**(f) `id=f(digest)` 미채택 (canonical REUSE).** `NonTradeEventRecord`·`CorrectionReversalRecord`는 **event/
correction identity**(source event id·version·supersedes ref·idempotency key §5 line 114–115)를 가지며, 위조·
contradictory event·double-commit correction 탐지에 `classify_record_pair`(**same primary id·diff bytes ⇒
`RecordPairKind.CRITICAL_CONFLICT`** / **same idempotency key·diff bytes ⇒ `RecordPairKind.DIVERGENT_EMISSION`** —
두 축 모두 id⊥digest를 전제)를 쓰려면 id⊥digest여야 한다(#4–#18 §3.1 동형). ⇒ `IndependentIdArtifact` 채택, `IdDerived
Artifact`(capsule content-addressed) 미채택. 각 correction/reversal은 immutable append-only이며 정당한 정정(§10
line 219 "A correction or reversal is a new event linked to the event it supersedes")은 **새 versioned event**이지
in-place mutation이 아니다. **`tos.nontrade._base`**: canonical 원시타입(`FrozenModel`·`DigestBoundArtifact`·
`IndependentIdArtifact`·`CanonicalDecimal`)의 thin re-export + all-false `NonTradeAuthorityEffect`(label-grants-
nothing §6 line 144)의 로컬 fresh 정의(rcl `AllFalseAuthority`·are/afg/iap `_base` 동형).

**(g) 앵커 규약 — NT-EV/NT-AC/§-clause/SAFE 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-010은 `NT-AC-001..012`
(§21 line 402–413, 12종)·`NT-EV-001..012`(register 12행)만 정의하고 **자체 `NT-INV` 시리즈가 없다**(grep 0건). ⇒
본 계약은 모델 불변식·술어를 **`NT-EV-###` / `NT-AC-###` / §-clause / `SAFE-###`(§24)**에 앵커하고 **새 INV/AC/EV
시리즈를 창작하지 않는다**. #9/#11/#18 동형.

---

## 1. 범위 매핑 — ADR-002-010 조항별 EV-L1 도달성 (닫는 NT-EV 0건)

EV-level 정의(VER-002-001 line 142–164): **EV-L1 = Model and Property Verification**(state-machine exploration,
model checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integrated System Fault Test**, **+Broker = Broker Capability Profile evidence**, **+Security = independent
security-boundary assessment**. Phase 1은 EV-L1만이다. 합성표기: `EV-Ln/Lm`은 staged scope — EV-Ln이 **earliest
non-live stage**, EV-Lm이 통합/broker 수용 전 추가 요구. `+X`는 EV-Ln을 대체·인하하지 않는다.

> **결정적 사실 1 — NT-EV ↔ NT-AC 1:1, 최소 레벨 실측(오케스트레이터 사전 카운트 확인)**: `NT-EV-001..012`(register)는
> ADR §21 `NT-AC-001..012`(line 402–413)와 제목·번호가 **1:1**. register 최소 레벨 실측(EVIDENCE-REGISTER-002.csv
> **CSV-aware 파싱 — title 필드 쉼표 포함, naive grep/awk 금지**; 12행 전수, python `csv` reader):
> **`EV-L1` 슬라이스 보유(3행)** = 001(`EV-L1/3+Broker`, "Split and Reverse-Split Transition")·002(`EV-L1/3`,
> "Multi-Leg Merger and Spin-Off")·010(`EV-L1/3`, "Correction and Reversal Idempotency"); **`EV-L1` 슬라이스
> 부재(9행)** = 003(`EV-L2/3` "Instrument Identity Change")·004(`EV-L3+Broker` "Option Exercise and Assignment")·
> 005(`EV-L3+Broker` "Futures Expiry and Settlement")·006(`EV-L3/5` "Broker Open-Order Adjustment")·007(`EV-L2/3`
> "Conflicting Effective-Time Window")·008(`EV-L3+Broker` "Unattributed Correction and Transfer")·009(`EV-L3`
> "Non-Permissive Partial Local Application")·011(`EV-L3` "Non-Trade Restart and Replay")·012(`EV-L3` "Event
> Completion Cannot Re-arm"). ⇒ **core tier 3행**(#11 protective·#18 PR형 소수 core; NT은 3), not-Phase-1 9행.
> **오케스트레이터 사전 실측("L1 슬라이스 3행 = 001·002·010")과 일치 — 정정 없음.**
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 NT-EV = 0건)**: Phase 1은 core 3행의 **L1-decidable predicate/model
> substrate**를 저작하나 **어떤 NT-EV도 닫지 않는다.** (a) core 3행조차 `/3` 잔여(integration fault·adversarial
> interleaving)이고 001은 `+Broker` 잔여, (b) 9행은 최소 ≥ L2(+Broker/+L3/+L5), (c) VER-002-001 §5 "Registration is
> not execution"·ADR §18 line 392·§26 line 502–514. ⇒ **"EV-L1-complete 주장 금지"**. Owner/Reviewer는 register상 TBD.

**규율 태그(모든 주장에 부착)**: "**predicate/coordinate substrate only; NT-EV-001..012 전부 NOT_IMPLEMENTED —
core 3행(001·002·010)은 `/3`(및 001 `+Broker`) 통합·독립 리뷰 대기, 나머지 9행은 EV-L2/L3 fault injection·adversarial·
+Broker evidence 대기. EV-L1-complete 주장 금지. 닫는 NT-EV = 0건.**"

**ADR-002-010 조항 → Phase-1 분류(core / predicate-only / not-Phase-1[형제 소유·런타임 이연])** — **전 조항 §1–§26
매핑(§-row 완전성 #16 M8·#18 M1 교훈, normative 문장 단위)**. **v1.1 m1**: §2(Context)·§3(Decision Drivers) narrative
행을 추가해 §1–§26 **전수** 매핑을 실제로 실현했다(v1.0은 두 행 누락 — "전 조항" 주장과 표가 불일치).

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | NT-EV |
|---|---|---|---|---|
| **§9** (line 179–198) | Conservative Transition Envelope (all credible states·no-netting) | **core (L1 슬라이스)** | `transition_envelope_complete`(§5.1) — 10종 credible leg 완전성·구조적 no-netting(§9 line 196). 합산은 rcl·risk는 are 주입(§0.4d). `/3` 잔여. | **002** |
| **§11** (line 225–240) | Quantity/Price/Multiplier/Currency Transformation (**6 구분** — line 231·232·233·234·235·236 개별 계수, §2.2-7 전사) | **core (L1 슬라이스)** | `split_polarity_coherent`+`transformation_residual_conservative`+`transformation_units_and_rounding_explicit`(§5.2) — 방향 극성 reciprocal(§4.5)·residual explicit(§11 line 240)·exact unit/rounding(§11 line 227). `/3`·`+Broker` 잔여. | **001** |
| **§10** line 219·**§16** line 313 | 정정=versioned linked event·history 보존·no-destructive-overwrite | **core (L1 슬라이스)** | `correction_reversal_idempotent`(§5.3) — lineage+history+at-most-once(canonical `classify_record_pair`; §4.6). `/3` 잔여. | **010** |
| **§5** (line 99–117) | Non-Trade Event Identity (13 필드) | **core substrate(분산)** | `NonTradeEventRecord`(digest-bound·IndependentIdArtifact, §2.2·§5.4) — 13 identity 필드·source-id 보존(§5 line 117). | 001–012 공통 |
| **§6** (line 121–144) | Event Knowledge and Workflow State (orthogonal) | **core substrate(분산)** | `NonTradeEventWorkflowState`(11종, §2.2)·orthogonality(line 123)·label-grants-nothing(line 144)(§4.4·§5.4). order/knowledge는 orthostate·capacity는 rcl(주입). | 001–012 공통 |
| **§12** (line 244–252) | Instrument Identity and Lineage | **predicate-only (venue 소비)** | `instrument_lineage_preserved`(§6.1) — old/new 병존·no-silent-reassign(§12 line 250). venue `material_change_closure`·`InstrumentRouteFields`·`OrderAdmissibilityResult` 주입. 최소 `EV-L2/3`. | **003** |
| **§8** (line 167–175) | Effective-Time Model (earliest-to-latest window) | **predicate-only (time 소비)** | `effective_window_blocks_new_risk`(§6.2) — earliest credible boundary 전 block·latest completion까지 restricted(§8 line 173)·clock-recovery≠authority(§8 line 175). time `freshness_verdict`/`source_disagreement_within_bound` 주입. 최소 `EV-L2/3`. | **007** |
| **§14** (line 276–291) | Derivative Expiry/Exercise/Assignment/Settlement | **not-Phase-1** | are `OPTION_GREEKS_EXERCISE_ASSIGNMENT`·brokercap·orthostate 주입. "absence of report ≠ no assignment"(§14 line 289). 최소 `EV-L3+Broker`. | **004** |
| **§14** line 282·**§4.2** | Futures Expiry/Delivery/Cash-Settlement (expired≠zero-risk) | **not-Phase-1** | are `SETTLEMENT_CASH_CURRENCY`·rcl `TRAPPED_CONSUMED` 주입. §22.4 line 431 "Expired or delisted means no risk" 기각. 최소 `EV-L3+Broker`. | **005** |
| **§13** (line 256–272) | Open Orders and Protective Coverage | **not-Phase-1 (replacement 소비)** | replacement `overlap_first_reservation_complete`·brokercap `ReplaceSemantics`·`OPEN_ORDER_QUERY`·orthostate `BrokerOrderState` 주입. §13 line 272 "ADR-002-011 governs"(§3.5). 최소 `EV-L3/5`. | **006** |
| **§16** (line 305–315) | Broker Corrections/Transfers/Administrative (unattributed) | **not-Phase-1 (recon/rcl 소비)** | recon `EXTERNAL_UNATTRIBUTED_ACTIVITY`/`FieldConfidenceClass.UNKNOWN`·rcl `QUARANTINED_UNKNOWN`/`CREATE_EXTERNAL_QUARANTINE` 주입. §16 line 311 no-relabel. 최소 `EV-L3+Broker`. | **008** |
| **§10** (line 202–215) | Atomic State Transition (no more-permissive partial) | **not-Phase-1 (rcl 소비)** | rcl 원자 remap·durable protocol(§10 line 215 "cannot expose a more permissive partial state") 런타임. NT은 pre/post envelope 주입. 최소 `EV-L3`. | **009** |
| **§19** (line 355–372) | Startup, Recovery, and Replay (**8 복구 의무** — line 363·364·365·366·367·368·369·370 개별 계수) | **not-Phase-1 (sbr 소비)** | sbr `RecoveryObligation`·`recovery_inventory_complete`·`restore_worst_credible_union`·`unknown_stays_conservative` 주입. §19 line 359 "mandatory ADR-002-017 Recovery Obligations". 최소 `EV-L3`. | **011** |
| **§17** (line 319–334) | Authority Invalidation and Pre-Event Controls (**8 경계** — line 323·324·325·326·327·328·329·330 개별 계수) | **not-Phase-1 (authority/liveauth 소비)** | authority `rearm_gate`·liveauth `no_automatic_rearm`/`authorization_revived_by_nothing` 주입. §17 line 334 "SHALL NOT automatically re-arm ... ADR-002-007 applies". 최소 `EV-L3`. | **012** |
| **§1** (line 13–28) | Decision (central) | **core substrate(분산)** | first-class versioned event·UNKNOWN-consumes-capacity·no-fabricated-fill·conservative-old-and-new → §2 어휘·§4 불변식 전반. capacity mutate는 rcl(line 19). | 001–012 공통 |
| **§4** (line 71–95) | Scope and Classification (5 event class) | **core substrate(분산)** | `NonTradeEventClass` 5종(§2.2; §4.1–§4.5). §4.5 unrecognized ⇒ `QUARANTINED_UNKNOWN`/`TRAPPED_CONSUMED`(line 95, rcl 주입). | 001–012 공통 |
| **§7** (line 148–164) | Source and Evidence Requirements | **predicate-only (recon 소비)** | recon `classify_field`/`FieldConfidenceClass`·common-mode(§7 line 159)·majority-vote 금지(§7 line 161) 주입. NT은 field-confidence 소비. 최소 `EV-L2/3`. | 003/007/008 (consumed) |
| **§15** (line 295–301) | Voluntary Actions and Elections | **not-Phase-1 (런타임)** | election instruction transmit는 governed intent·final egress 런타임(§15 line 299 "SHALL NOT itself transmit"). NT은 event identity만. 최소 `EV-L3`. | 004 (consumed) |
| **§18** (line 338–351) | Unknown and Conflicting Events (8 단계) | **core substrate(분산) + rcl 소비** | 8 단계(§18 line 342–349)의 mark-UNKNOWN/block-new-risk 판정 substrate; max-credible-exposure·capacity는 rcl/are 주입. §18 line 351 operator-label≠removal. | 008 (consumed) |
| **§20** (line 376–392) | Evidence and Observability (**9 보존 항목** — line 380–388 개별 계수) | **core substrate (재구성)** | frozen digest-bound 레코드 재구성(§5.6). replay ENGINE=ADR-002-016(런타임). §20 line 392 "successful replay are not completed evidence". | 001–012 공통 |
| **§21** (line 396–413) | Acceptance Cases (NT-AC-001..012) | **앵커** | §0.4g — NT-AC ↔ NT-EV 1:1 앵커. Registration ≠ execution. | 001–012 |
| **§2** (line 32–54) | Context (non-trade 경제효과 예시 11항목 line 38–48·영향 축 line 50·source 불일치 축 line 52) | **narrative 앵커** | 규범 동사 0(SHALL 부재) — 어휘 범위 근거로만 사용(§2.2-1 `NonTradeEventClass` 5종의 예시 출처; stock-dividend는 line 38). Phase-1 술어 없음. | — |
| **§3** (line 58–67) | Decision Drivers (**8 driver** — line 60·61·62·63·64·65·66·67 개별 계수) | **narrative 앵커 (무소유 driver 0)** | d1 fill-구별→§4.4·d2 no-release-without-proof→§4.2-3(rcl)·d3 pre-event authority 축소→§17(authority/liveauth)·d4 broker 조정 reconcile→§13/§16(brokercap/recon)·d5 transformation risk 보존→§4.2/§4.5(core)·d6 effective-time·recovery≠revive→§6.2(time)·d7 replay/correction/reversal idempotent→§4.3/§4.6(core)·d8 unrecognized→quarantine·block→§2.2-6/§18(rcl/recon). **8/8 매핑 — 소유자 미지정 driver 0건.** | — (narrative) |
| **§22** (line 417–445) | Rejected Alternatives (7) | **narrative/금지동사 앵커** | §22.1 fill-fabrication·§22.2 ref-data-mutation·§22.3 broker-adjusts-correctly·§22.4 expired=no-risk·§22.5 most-likely-ratio·§22.6 net-favorable-adverse(§0.4d)·§22.7 recovery-re-arm(§4.7 금지동사). | — |
| **§23/§24** (line 449–483) | Consequences / Traceability | **narrative/SAFE 앵커** | SAFE-002/004/013(unmanaged exposure·envelope)·011(egress)·015(RCL-only)·020(lineage)·022/023/024(reconciliation·field·attribution)·025(partial/delayed)·030/032/035(profile·session·time)·040/041/044(protection·authority·recovery)·048/050(partition·stale-writer)·051/052(evidence·replay). | — |
| **§25/§26** (line 487–514) | Open Questions / Approval Gate | **Phase-0/non-acceptance** | §25 6 OQ → §9.2(numeric bound·source-authority·initial scope). §26 approval gate → §0.2 비-acceptance. | — |
| **§10 rcl remap·§16 PTOL(ADR-002-030)·§19 fence 런타임** | 원자 remap commit·obligation-lifecycle·hard fence enforce | **not-Phase-1 (런타임 EV-L2/L3)** | rcl 원자 remap(§10 line 217)·ADR-002-030 PTOL serialization(§16 line 309)·sbr/rcl fence(§19 line 367). NT은 완전성/coherence/idempotency 술어만. | 001–012 (런타임) |

**Phase-1 분류 요약**: **core(L1 슬라이스)** = {§9 envelope [NT-EV-002], §11 transformation polarity [NT-EV-001],
§10/§16 correction idempotency [NT-EV-010]} — **3 NT-EV의 L1 슬라이스뿐, 닫는 NT-EV = 0건.** **predicate-only(EV
주장 금지)** = {§12 instrument lineage [NT-EV-003 venue-소비], §8 effective-time window [NT-EV-007 time-소비], §7
source/evidence [recon-소비]}. **not-Phase-1(형제 소유·런타임 이연)** = {§14→are/brokercap [004], §14/§4.2→are/rcl
[005], §13→replacement/brokercap/orthostate [006], §16→recon/rcl [008], §10 atomic→rcl [009], §19→sbr [011],
§17→authority/liveauth [012], §15 election→런타임, §16 PTOL→ADR-002-030, §25 수치→Phase-0}. (self-consistency:
core 3 + predicate-only 2 NT-EV(003·007) + not-Phase-1 7(004·005·006·008·009·011·012) + substrate 분산 — §3.5
소유권 분할과 정합; 12 NT-EV 전수 = 3+2+7.)

---

## 2. 데이터 모델 계약

**핵심 난제**: non-trade event를 **first-class versioned economic event**로 표현하되(ADR §1 line 15 "SHALL NOT be
fabricated as fills, silently folded into position corrections, or treated as harmless reference-data changes"),
capacity·risk·admissibility·field-confidence는 **형제가 소유**하므로 NT은 event identity·transition envelope
completeness·transformation polarity·correction idempotency만 **순수·비전송·fail-closed**로 모델링한다.

### 2.0 소유권 골격 — nontrade는 canonical의 하류, 11개 형제의 하류(주입 소비)·미래 런타임의 상류(produced-bool)

```text
        canonical (core)                         ordering (core)
   FrozenModel·DigestBoundArtifact          non-trade event / correction /
   IndependentIdArtifact·CanonicalDecimal   reversal append-only 순서
   classify_record_pair·RecordPairKind
              │  (import)                              │  (import)
              ▼                                         ▼
   ┌───────────────────────────── tos.nontrade (본 문서) ─────────────────────────────┐
   │  vocabulary: NonTradeEventClass(5)·NonTradeEventWorkflowState(11)·                │
   │              CredibleTransitionLegKind(10)·SplitTransformationKind(2)·            │
   │              TransformationDirection(3)·CorrectionReversalOutcome(6)·             │
   │              NonTradeDisposition(result)                                          │
   │  records:    NonTradeEventRecord·CorrectionReversalRecord·TransitionEnvelope·     │
   │              SplitTransformationSpec(pre/post qty·basis·unit_spec·rounding_rule)· │
   │              NonTradeAuthorityEffect(all-false)                                   │
   │  predicates: transition_envelope_complete·favorable_netting_absent·               │
   │              split_polarity_coherent·transformation_residual_conservative·        │
   │              transformation_units_and_rounding_explicit·nontrade_disposition·     │
   │              correction_reversal_idempotent·nontrade_authority_effect_all_false·  │
   │              instrument_lineage_preserved·effective_window_blocks_new_risk·       │
   │              material_change_trigger_nonempty            (11 predicates, §9.1)    │
   └──────────────────────────────────────────────────────────────────────────────────┘
        ▲ (주입 소비 — import 아님; produced-bool/StrEnum/CanonicalDecimal 좌표)
        │  rcl(RECOGNIZED_EXTERNAL_CHANGE·credible_union_capacity·CapacityState)·
        │  are(worst_intermediate_risk·EXTERNAL_TRAPPED_NONTRADE_CONCURRENT)·
        │  venue(material_change_closure·OrderAdmissibilityResult·InstrumentRouteFields)·
        │  recon(classify_field·FieldConfidenceClass)·orthostate(KnowledgeState·no_coupling_violation)·
        │  brokercap(CORPORATE_ADMINISTRATIVE_EVENTS·external_detection_ok)·replacement(overlap_first_*)·
        │  authority/liveauth(no_automatic_rearm)·sbr(restore_worst_credible_union)·time(freshness_verdict)
        ▼ (produced-bool/StrEnum 생산 — 미래 소비자 배선은 런타임 §9.1)
   미래: Reconciliation Service·rcl remap-admission·venue invalidation·final-egress 런타임
```

**sibling edge 0건**(§0.4b·§3.4): NT은 canonical·ordering만 import한다. 11개 상류 형제(rcl·are·venue·recon·orthostate·
brokercap·replacement·authority·liveauth·sbr·time)는 **주입 좌표**로만 소비하고 import하지 않는다.

### 2.1 digest-bound / plain-frozen / value / reference 분류 (총괄)

| 모델 | 종류 | id ⊥ digest | 근거 |
|---|---|---|---|
| `NonTradeEventRecord` | **digest-bound + IndependentIdArtifact** | ✅ (source event id·version·workflow generation §5 line 114) | 위조·contradictory event 탐지 `classify_record_pair`(§0.4f) |
| `CorrectionReversalRecord` | **digest-bound + IndependentIdArtifact** | ✅ (correction id·supersedes ref·idempotency key §5 line 115) | double-commit correction·same-key-diff-bytes 탐지(§4.6) |
| `TransitionEnvelope` | **plain-frozen value** | — | leg별 magnitude·flag(§9); 개별 identity 불요 |
| `SplitTransformationSpec` | **plain-frozen value** | — | `pre_quantity`/`post_quantity`·`pre_basis`/`post_basis`(방향 **구조 파생** 입력 §2.2-4)·`kind`·residual·`unit_spec`·`rounding_rule`(§11 line 227); 값 객체 |
| `NonTradeAuthorityEffect` | **all-false frozen** | — | label-grants-nothing(§6 line 144); 어떤 True도 unconstructable |
| `NonTradeDisposition`·`CorrectionReversalOutcome`·enum 5종 | **StrEnum** | — | 결정 결과·어휘 (truthy-untestable result는 §2.2-6) |

### 2.2 어휘 (verbatim 전사 — 에라타 defect class 주의·항목 수 대조 #18 M3)

> **전사 규율**: 아래 enum member는 ADR 원문 리스트를 개념(문자열 아님) 기준으로 전사하며 **항목 수를 병기·개별
> 계수**한다(defect-class #4 카운트 대조 전수화). ADR 원문이 "at least"/"where applicable"로 열면 **non-closed
> minimum set**임을 명시한다(recon `SafetyRelevantField` 선례).

**2.2-1 `NonTradeEventClass`(StrEnum, 5종 — ADR §4 line 71–95 전수, closed)**:

| member | ADR §-line | 개념 |
|---|---|---|
| `CORPORATE_ACTION` | §4.1 line 73–75 | issuer/exchange/clearing event가 instrument·entitlement·cash flow·holder obligation을 transform |
| `LIFECYCLE` | §4.2 line 77–81 | expiry·exercise·assignment·delivery·settlement·conversion·redemption·termination·rollover (strategy-initiated rollover trade는 trade — line 81) |
| `ADMINISTRATIVE_BROKER` | §4.3 line 83–85 | transfer·journal·correction·bust consequence·fee·tax·interest·collateral·margin·broker-applied adjustment |
| `INSTRUMENT_TRADABILITY` | §4.4 line 87–89 | symbol·identifier·venue·contract-spec·tick·lot·multiplier·currency·listing·delisting·suspension·session-eligibility change |
| `UNRECOGNIZED_EXTERNAL` | §4.5 line 91–95 | 충분한 confidence로 trade/recognized event에 attribute 불가 ⇒ `QUARANTINED_UNKNOWN`/`TRAPPED_CONSUMED`(line 95, rcl 주입) |

**항목 수 = 5**(§4.1–§4.5 5절 1:1).

**2.2-2 `NonTradeEventWorkflowState`(StrEnum, 8 linear + 3 branch = 11종 — ADR §6 line 127–140 verbatim, orthogonal)**:

- linear(8): `OBSERVED` → `CORROBORATING` → `VALIDATED` → `TRANSITION_PREPARED` → `EFFECT_PENDING` → `APPLIED_LOCAL`
  → `RECONCILING` → `RECONCILED`.
- branch(3): `CONFLICTED`(Any state →)·`QUARANTINED_UNKNOWN`(Any state →)·`CORRECTION_PENDING`(Any applied state →).

**항목 수 = 8 + 3 = 11.** **불변식 앵커(§6 line 142–144 verbatim)**: "`APPLIED_LOCAL` is not proof that the broker or
venue applied the same effect"·"`RECONCILED` requires evidence sufficient under ADR-002-006"(recon 주입)·"**No
workflow state by itself releases capacity, closes an instrument, proves final quantity, or grants authority**"
(label-grants-nothing §4.4). **orthogonality(§6 line 123)**: 이 축은 orthostate order/transmission/knowledge/capacity
축과 **별개**이며 붕괴 금지(§2.2-5).

**2.2-3 `CredibleTransitionLegKind`(StrEnum, 10종 — ADR §9 line 185–194 verbatim, "where applicable" non-closed
minimum set)**:

| member | ADR §9-line | leg |
|---|---|---|
| `PRE_EVENT_POSITION_AND_ORDER` | line 185 | full pre-event position and order state |
| `POST_EVENT_QUANTITY_INSTRUMENT_MULTIPLIER_CURRENCY_CASH` | line 186 | every plausible post-event quantity, instrument, multiplier, currency, cash leg |
| `OLD_AND_NEW_INSTRUMENT_BOTH` | line 187 | both old and new instruments when identity transition is not final |
| `FRACTIONAL_QUANTITY_AND_CASH_IN_LIEU` | line 188 | fractional quantity and cash-in-lieu outcomes |
| `EXERCISE_ASSIGNMENT_DELIVERY_SETTLEMENT_CONVERSION` | line 189 | exercise, assignment, delivery, settlement, or conversion obligations |
| `BROKER_OPEN_ORDER_CANCEL_ADJUST_DUPLICATE_RECREATE` | line 190 | broker-side open-order cancellation, adjustment, duplication, or recreation |
| `DELAYED_PARTIAL_REVERSED_CORRECTED_APPLICATION` | line 191 | delayed, partial, reversed, or corrected application |
| `PRICE_MARGIN_SETTLEMENT_MARKET_MOVEMENT_BOUNDS` | line 192 | price, margin, settlement, and market-movement bounds |
| `PROTECTIVE_ORDER_GAP_OVERLAP` | line 193 | protective-order gaps and overlaps (replacement 주입) |
| `SOURCE_DISAGREEMENT_AND_TIME_UNCERTAINTY` | line 194 | source disagreement and time uncertainty |

**항목 수 = 10**(§9 line 185–194 10개 bullet). **non-closed**: §9 line 183 "SHALL include **where applicable**" —
required set은 event-class-parametric(§5.1 caller가 applicable subset 주입); NT predicate는 **exhaustive-closure
assertion을 하지 않는다**(recon `SafetyRelevantField` non-closed 선례).

**2.2-4 `SplitTransformationKind`(StrEnum, 2종) + `TransformationDirection`(StrEnum, 3종) — ADR §11 극성 축**:

- `SplitTransformationKind`: `FORWARD_SPLIT`(quantity AMPLIFY·basis ATTENUATE)·`REVERSE_SPLIT`(quantity ATTENUATE·
  basis AMPLIFY). **항목 수 = 2.** stock-dividend는 forward-like(주석; §2 line 38 예시). 이 최소 2종이 NT-EV-001 L1
  슬라이스 범위이며 merger/spin-off(NT-EV-002)는 `TransitionEnvelope` multi-leg(§2.2-3)로 다룬다.
- `TransformationDirection`: `AMPLIFY`(배수 > multiplicative identity)·`ATTENUATE`(< identity)·`IDENTITY`(= identity).
  **항목 수 = 3.** **극성 대수(algebra)는 이 enum의 reciprocal 관계로 수행**(§4.5 진리표 — 특정 배수 하드코딩 0).
- **방향은 선언이 아니라 구조 파생이다(M2, v1.1)**: `SplitTransformationSpec`은 `pre_quantity`/`post_quantity`·
  `pre_basis`/`post_basis`(`CanonicalDecimal|None`)를 담고, 각 축의 `TransformationDirection`을 **multiplicative
  identity 대비 비교**로 **파생**한다 — `post > pre` ⇒ `AMPLIFY`·`post < pre` ⇒ `ATTENUATE`·`post == pre` ⇒
  `IDENTITY`(scale-normalize 후 비교; 어떤 배수도 하드코딩하지 않음). 파생된 두 방향을 **declared
  `SplitTransformationKind`와 대조**하므로(§4.5 진리표 B) caller가 direction을 위조해도 pre/post magnitude와
  어긋나면 fail-closed다. **v1.0은 direction을 caller 선언 enum으로 받아 극성이 flag-신뢰였다** — v1.1은 §0.4d
  구조-파생 규율(no-netting 선례)을 극성 축에도 적용한다. 네 magnitude 중 어느 하나라도 None ⇒ 방향 파생 불가 ⇒
  fail-closed(§4.7). magnitude는 극성 **파생 입력**과 residual/envelope 표현에만 쓰이고 극성 **대수**는 여전히 enum
  관계다(§4.5 진리표 유지 — 입력만 구조 파생으로 승격).

**2.2-5 `CorrectionReversalOutcome`(StrEnum, 6종 — NT-local, canonical `classify_record_pair` 하류) + 좌표 비붕괴**:

- `APPLIED_ONCE`(lineage+retained+**`prior is None`**(첫 정정, classify **선행 게이트** §5.3) ⇒ effect count→1)·
  `IDEMPOTENT_REPLAY`(`RecordPairKind.IDEMPOTENT_DUP`: same primary/idempotency id·same bytes ⇒ no-op)·`REJECTED_
  CONFLICT`(**두 conflict kind 병합**: `CRITICAL_CONFLICT`[same **primary** id·diff bytes — 레코드 위조] **∪**
  `DIVERGENT_EMISSION`[same **idempotency** id·diff bytes — divergent emission] ⇒ contain-both·no-double-apply)·
  `REJECTED_NO_LINEAGE`(supersedes 부재 ⇒ §16 line 311 no-relabel)·`REJECTED_OVERWRITE`(destructive overwrite ⇒ §10
  line 219 위반)·`REJECTED_UNKNOWN`(`NOT_COMPARABLE`[digest None] ∪ `DISTINCT`[계약 위반 — prior가 key 미공유] ⇒
  fail-closed). **항목 수 = 6(outcome).**
- **RecordPairKind 5-member 전수 매핑(C2 — 실측 `canonical/record_pair.py:52–105`)**: `IDEMPOTENT_DUP`(:94)→
  `IDEMPOTENT_REPLAY` · `CRITICAL_CONFLICT`(same **primary** id·diff bytes, :96)→`REJECTED_CONFLICT` · `DIVERGENT_
  EMISSION`(same **idempotency** id·diff bytes, :103)→`REJECTED_CONFLICT` · `DISTINCT`(:105)→`REJECTED_UNKNOWN` ·
  `NOT_COMPARABLE`(digest None, :87)→`REJECTED_UNKNOWN`; **`prior is None`은 classify 선행 게이트**로 `APPLIED_ONCE`
  (§5.3). classify는 **4-positional+2-keyword** 시그니처(`a_identity, a_digest, b_identity, b_digest, *,
  a_idempotency_id, b_idempotency_id`)다.
- **좌표 비붕괴(§2.2-5 규율)**: NT enum 값이 형제 enum 값과 문자열이 겹쳐도 **별개 타입**이다 —
  `NonTradeEventWorkflowState.QUARANTINED_UNKNOWN`(NT event 축) ≠ rcl `CapacityState.QUARANTINED_UNKNOWN`(capacity
  축) ≠ recon `FieldConfidenceClass`(field 축); `CredibleTransitionLegKind.PROTECTIVE_ORDER_GAP_OVERLAP`(transition
  축) ≠ replacement `CredibleIntermediateOutcomeKind`(replacement-order 축); `IDEMPOTENT_REPLAY`(NT economic-event)
  ≠ iap `ConsumptionOutcome.IDEMPOTENT_REPLAY`(authorization-token) ≠ rcl `ApplyReason.IDEMPOTENT_REPLAY`(capacity-
  command)(§0.4e). property 회귀로 별개-타입 assert(§7).

**2.2-6 `NonTradeDisposition`(StrEnum, result — truthy-untestable, `_NonTruthyStrEnum` 패턴)**:

- `NONTRADE_ADMISSIBLE`(전 credible leg 완전·polarity coherent·evidence sufficient ⇒ conservative transition 진행
  허용)·`NONTRADE_BLOCK_NEW_RISK`(§1 line 26 "UNKNOWN consumes capacity and blocks new risk")·`NONTRADE_QUARANTINED_
  UNKNOWN`(§4.5·§18 line 344)·`NONTRADE_TRAPPED`(§12 line 252 "inability to exit SHALL be represented as trapped
  exposure ... not zero risk")·`NONTRADE_CONFLICTED`(§18 line 344 CONFLICTED). **항목 수 = 5.** venue/sbr/iap의
  `_NonTruthyStrEnum`(`__bool__` ⇒ `TypeError`) 동형 — truthy-sentinel 오용(`if disposition:`) 봉인, identity 게이트
  (`is NONTRADE_ADMISSIBLE`)만 허용(§4 truthy-sentinel 극성 분기).

**2.2-7 ADR §11 6 구분(line 231–236) 개별 전사 + 소유 귀속 (M1, v1.1 — 카운트 대조 전수화 시리즈 규율 2)**:

> **소유 귀속 근거(실측 verbatim)**: ADR §16 line 309 "This ADR owns the **non-trade event and transformation
> identity**; ADR-002-030 owns the obligation-lifecycle serialization" + §5 line 109 "transformation legs, ratios,
> multipliers, prices, cash values, and **rounding rules**" ⇒ **NT은 6구분을 "구별해 선언할 의무"를 소유**하고,
> 각 구분의 실제 값·재평가·의무 생성은 형제 소유다. 아래 표가 6/6 귀속을 고정한다(**무소유 구분 0건**).

| # | ADR §11 line | 구분(개념) | Phase-1 귀속 |
|---|---|---|---|
| 1 | line 231 | position quantity ↔ executable order quantity | **NT 소유(선언)** — `SplitTransformationSpec.unit_spec`이 두 수량 단위를 분리 선언(§5.2); executable order quantity 재평가는 venue admissibility 주입(§10 line 221) |
| 2 | line 232 | raw ratio ↔ broker-applied rounded quantity | **NT 소유(선언)** — `rounding_rule` not-None 요구 + `fractional_residual` explicit(§5.2); broker 실적용 값 대조는 brokercap/recon 주입(EV-L2/3) |
| 3 | line 233 | fractional entitlement ↔ tradable whole quantity | **NT 소유(술어)** — `transformation_residual_conservative`(§5.2·§11 line 240) |
| 4 | line 234 | reference price ↔ cost basis·settlement price·trigger price·limit price | **NT 부분 소유(basis 축만)** — `pre_basis`/`post_basis`가 cost-basis 극성 파생만 담당(§2.2-4); trigger/limit price는 replacement·venue 소유(§3.5) |
| 5 | line 235 | instrument multiplier ↔ contract quantity | **미소유(venue)** — `InstrumentRouteFields.multiplier`(`venue/records.py:83`) 주입 소비; NT은 old/new 병존만(§6.1) |
| 6 | line 236 | trade currency ↔ settlement·collateral·reporting currency | **미소유(venue/are/PTOL)** — `InstrumentRouteFields.currency`·are `SETTLEMENT_CASH_CURRENCY`(`are/vocabulary.py:65`)·ADR-002-030 obligation(§16 line 309) |

**항목 수 = 6**(§11 line 231·232·233·234·235·236 개별 계수). **NT 소유 3(1·2·3) + 부분 소유 1(4) + 형제 소유 2(5·6)
= 6/6.** §11 line 227 verbatim "Every transformation SHALL specify exact units and rounding rules"는 6구분 전체의
전제이며 `transformation_units_and_rounding_explicit`(§5.2)가 이를 강제한다.

**2.2-8 ADR §5 13 identity 필드(line 103–115) 개별 행 전사 (M8, v1.1) — `NonTradeEventRecord` 실현 대조**:

> §5 line 101 "Every event SHALL have a durable **Non-Trade Event ID** and contain **at least**:" ⇒ **non-closed
> minimum set**(recon `SafetyRelevantField` 선례) — 13은 하한이지 폐집합이 아니다.

| # | ADR §5 line | identity 필드(개념) | `NonTradeEventRecord` 실현(§5.4) |
|---|---|---|---|
| 1 | 103 | event class and subtype | `NonTradeEventClass`(§2.2-1) + subtype 토큰 |
| 2 | 104 | issuer·venue·broker·clearing·administrative source identities | source-identity 집합(§5 line 117 source-id 보존) |
| 3 | 105 | source event identifiers and versions | **primary identity 축**(`IndependentIdArtifact` — `classify_record_pair` `CRITICAL_CONFLICT` 대상, §4.6) |
| 4 | 106 | announcement·observation·record·ex·effective·payable·settlement times *where applicable* | 시각 축 개별 보존(붕괴 금지 §8 line 171); trust/freshness는 time 주입(§6.2) |
| 5 | 107 | affected account·portfolio·instrument·currency·broker scopes | 영향 scope 집합; risk scope 투영은 are 주입(§0.4d) |
| 6 | 108 | old and new instrument identities | old/new 병존(§6.1 `instrument_lineage_preserved`); route 필드는 venue 주입 |
| 7 | 109 | transformation legs·ratios·multipliers·prices·cash values·rounding rules | `SplitTransformationSpec`(§2.2-4·§2.2-7)·`TransitionEnvelope` leg magnitude(§2.2-3) |
| 8 | 110 | eligibility and election conditions | election 조건 값만 보유 — **transmit 금지**(§15 line 299·§0.2) |
| 9 | 111 | broker-treatment profile and expected open-order behavior | brokercap `CORPORATE_ADMINISTRATIVE_EVENTS`/`OPEN_ORDER_QUERY`·`ReplaceSemantics` 주입 좌표(§3.4) |
| 10 | 112 | evidence confidence and contradiction status **per field** | recon `classify_field`/`FieldConfidenceClass` 주입(§3.5 — NT 미소유) |
| 11 | 113 | Safety Profile·Broker Capability Profile·Verification Profile·calendar·instrument-master versions | 프로파일 버전 좌표(spg/brokercap/VP-002 주입; §8.1) |
| 12 | 114 | workflow generation and idempotency key | `tos.ordering` generation 좌표(§3.2) + **idempotency 축**(`classify_record_pair` `DIVERGENT_EMISSION` 대상, §4.6) |
| 13 | 115 | supersession·correction·reversal·lineage references | `CorrectionReversalRecord.supersedes_ref`(§5.3 lineage 선행 게이트) |

**항목 수 = 13**(line 103–115 13 bullet 개별 계수). **id⊥digest 필수 근거**: 3(primary id)과 12(idempotency key)가
**서로 다른 두 identity 축**이며 canonical `classify_record_pair`가 이 둘을 각각 `CRITICAL_CONFLICT`/
`DIVERGENT_EMISSION`으로 분리 탐지한다(§0.4f·§4.6).

### 2.3 아티팩트 covered + self-exclusion (설계 #4 §3.3 상속)

`NonTradeEventRecord`·`CorrectionReversalRecord`는 `DigestBoundArtifact` covered-field 규율을 따른다(canonical §3.3):
digest는 **covered 필드 전수**를 bind하고, `NonTradeAuthorityEffect`(all-false)·재구성 파생 필드는 self-exclude
(digest 자기 포함 방지). same-id/diff-covered-bytes ⇒ `classify_record_pair` `CRITICAL_CONFLICT`(§4.6). **NT은
capsule content-addressed(`IdDerivedArtifact`)를 쓰지 않는다**(§0.4f — id⊥digest 필요).

---

## 3. canonical / ordering REUSE + 11-생산자 주입 seam + 형제 경계

### 3.1 canonical REUSE + `id=f(digest)` 미채택

NT은 canonical 원시타입만 REUSE한다(§0.4f): `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·
`CanonicalDecimal`·`classify_record_pair`·`RecordPairKind`·`ArtifactStatus`. `NonTradeEventRecord`·`CorrectionReversal
Record`는 **거버넌스/워크플로 identity**(id⊥digest)를 가져 위조·contradictory-event·double-commit-correction 탐지에
`classify_record_pair` `CRITICAL_CONFLICT`를 쓴다. **`_base.py`는 canonical thin re-export + `NonTradeAuthorityEffect`
(all-false) 로컬 fresh 정의**(rcl `AllFalseAuthority` 동형 — 어떤 True도 unconstructable).

### 3.2 ordering REUSE (non-trade event / correction / reversal append-only 순서)

non-trade event·correction·reversal의 **workflow generation·supersession lineage**(§5 line 114–115)는 `tos.ordering`
append-only 순서 좌표로 표현한다(#13 ARE·#16 AFG·#18 PR 동형 — 별도 heavy 아티팩트 아님). ADR §10 line 219 "A
correction or reversal is a **new event linked to** the event it supersedes"·§20 line 380 "every event version"는
append-only versioned 순서를 요구하며 ordering이 그 순서·generation·fencing 좌표를 제공한다. NT은 순서 산술을 재저작
하지 않고 ordering 좌표를 소비한다.

### 3.3 REUSE 요약 표

| REUSE 대상 | 출처 | 방식 | 근거 |
|---|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`CanonicalDecimal` | `tos.canonical` | **import** (core) | §0.3 allowlist; frozen 모델·digest·id⊥digest·decimal 산술 |
| `classify_record_pair`·`RecordPairKind` | `tos.canonical` | **import** (core) | correction/reversal idempotency(§4.6·§5.3) |
| append-only generation / supersession 순서 | `tos.ordering` | **import** (core) | event/correction versioned 순서(§3.2) |
| capacity union / remap / release·`CapacityState`·`RECOGNIZED_EXTERNAL_CHANGE` | `tos.rcl` | **주입 좌표** (sibling edge 0) | §0.2·§0.4c — capacity는 rcl 소유 |
| aggregate-risk 투영·`EXTERNAL_TRAPPED_NONTRADE_CONCURRENT` | `tos.are` | **주입 값** (sibling edge 0) | §0.2·§0.4d — risk는 are 소유 |
| material-change invalidation·admissibility | `tos.venue` | **주입 좌표** (sibling edge 0) | §0.2 — §10 line 221 venue 소유 |
| per-field confidence | `tos.recon` | **주입 좌표** (sibling edge 0) | §0.2 — §7 recon 소유 |
| order/knowledge 상태 축 | `tos.orthostate` | **주입 좌표** (sibling edge 0) | §0.2 — §6 line 123 orthostate 소유 |
| broker corporate/open-order capability | `tos.brokercap` | **주입 좌표** (sibling edge 0) | §0.2 — §13 brokercap 소유 |
| protective cancel/replace·gap/overlap | `tos.replacement` | **주입 좌표** (sibling edge 0) | §0.2 — §13 line 272 replacement 소유 |
| authority/re-arm·recovery·time | `tos.{authority,liveauth,sbr,time}` | **주입 좌표** (sibling edge 0) | §0.2 — §17/§19/§8 각 형제 소유 |

**PROMOTE 0건**(canonical/ordering 외 어떤 형제도 core로 승격 요구 안 함). **REUSE edge = canonical·ordering 2개
(import), sibling edge 0개**(주입).

### 3.4 11-생산자 주입 seam(edge 0) — produced-bool/좌표 소비 (중심, 코드 실측)

**(a) nontrade = 주입 소비자 + produced-bool 생산자(§0.4b).** NT은 형제를 **import하지 않고** 그들이 생산한 bool/
StrEnum/scalar를 주입 소비하며 미래 소비자가 소비할 completeness/coherence/idempotency 결정을 생산한다. **코드 실측
seam**(sibling 서사 아님 — #10 MAJOR-1·#18 C2 교훈; 전 인용 grep 실측):

| nontrade 소비/생산 (§4/§5/§6) | 타입 | 상대 (이미 비준·구현) | signature(실측 file:line) |
|---|---|---|---|
| **[소비]** recognized-external-change ⇒ capacity remap cause | StrEnum | rcl `TransitionCause.RECOGNIZED_EXTERNAL_CHANGE` | NT은 remap을 **propose**만; rcl이 transition(`rcl/vocabulary.py:92`; §10 line 217 "SHALL NOT update capacity independently"). `WEAK_CAUSES`(TIMEOUT/ABSENCE/OPERATOR_ASSUMPTION)는 conservatism만 증가 — §8 line 175 clock-recovery≠authority와 정합 |
| **[소비]** credible-union capacity / trapped / quarantine | value·StrEnum | rcl `credible_union_capacity`·`CapacityState.{TRAPPED_CONSUMED,QUARANTINED_UNKNOWN}` | NT envelope leg ⊆ rcl union 입력(`rcl/predicates.py:739` "worst credible union ... Empty input is fail-closed"·`vocabulary.py:30/29`); None⇒UNKNOWN 전파 |
| **[소비]** aggregate-risk 투영 / credible-space bounded | `Decimal\|None`·`bool\|None` | are `worst_intermediate_risk`·`credible_space_bounded`·`AdverseScenarioKind.EXTERNAL_TRAPPED_NONTRADE_CONCURRENT` | NT envelope risk 주입(`are/predicates.py:186/196`·`vocabulary.py:115`; §9 line 196; **docstring 명제 = "worst credible intermediate-state risk"·"unbounded ⇒ None/False ... trapped exposure/containment, not permission"** — NT §9 envelope 명제와 동일 축) |
| **[소비]** envelope-bound-not-enlarged | `bool` | are `envelope_bound_not_enlarged` | are ARE-INV-007(`are/predicates.py:557`; docstring 명제 = "Neither runtime policy, strategy, human approval, broker result, nor model output may **enlarge** the Hard Safety Envelope or single-action bound") — **명제-동일 대상 = ADR §9 line 196**("Risk capacity SHALL **cover the maximum aggregate risk across the envelope**. Favorable effects SHALL NOT be netted against uncertain adverse effects"), 즉 **한도 확대 금지 축**이다. **v1.1 M4 정정**: v1.0은 이를 §10 line 221 후단("neither the event nor a favorable projection **releases** capacity")에 걸었으나 그것은 **release 축(rcl 소유)**이고 are 술어의 enlarge 축과 명제가 다르다(§3.4(b) 명제 동일성 검사 위반) — 재지정함. `limit_source_is_injected_envelope is not True ⇒ False`(are 내부 양극성 게이트) |
| **[소비]** material-change invalidation closure | `frozenset[str]` | venue `material_change_closure` | NT corporate action = change trigger 입력(`venue/predicates.py:361`; **docstring 명제 = "any material change ... fences the affected unconsumed decisions ... Invalidation SHALL reach approval, authority issuance, unconsumed capabilities, and every final egress"** — NT §10 line 221 "invalidate affected ADR-002-019 ... fresh exact order decision"과 **명제 동일**; unproven edge expanded=보수) |
| **[소비]** order admissibility (fresh exact decision) | **`OrderAdmissibilityResult` 4토큰 + None → 3분기 접기** | venue `OrderAdmissibilityResult`(`vocabulary.py:91`, members `:114`–`:117`) + venue `protective_label_no_bypass`(`predicates.py:599`) | 4토큰 truthy-untestable(`__bool__` ⇒ `TypeError`). **접기 규칙 = 3분기(v1.1 M6 — v1.0의 "나머지 3토큰 일괄 trapped"는 `RESTRICTED_PROTECTIVE_ONLY`를 오분류)**: **(i)** `is ADMISSIBLE` ⇒ 통상 fresh-decision-present(ordinary new risk conjunct 충족); **(ii)** `is RESTRICTED_PROTECTIVE_ONLY` ⇒ **통상 신규 위험은 block**하되(`NONTRADE_BLOCK_NEW_RISK`) **protective action은 venue `protective_label_no_bypass` 경유로 허용** — NT은 그 4-조건 판정을 하지 않고 산출 `bool`을 `protective_action_may_proceed` **주입 좌표**로 소비한다(venue docstring: "the RESTRICTED_PROTECTIVE_ONLY path may proceed" only on label·exact admissibility·**separate** protective authority·intermediate-effect capacity coverage); **(iii)** `is INADMISSIBLE` / `is UNKNOWN` / `None` ⇒ not-fresh ⇒ `NONTRADE_TRAPPED`(§12 line 252). §18 line 348 "permit **only newly authorized recovery or protective action**"과 정합. NT remap ⇒ **fresh 재결정 요구**(NT은 재결정 안 함 — venue 소유·§10 line 221) |
| **[소비]** instrument route fields (old/new identity) | value | venue `InstrumentRouteFields` | old/new `canonical_instrument_id`·`multiplier`·`contract_month`·`expiration`·`settlement_method`·`currency`(`venue/records.py:83`; §12 line 246 "Symbol text is not instrument identity") 좌표 소비 |
| **[소비]** per-field evidence confidence | StrEnum | recon `classify_field`·`FieldConfidenceClass` | §7 field-independent 평가(`recon/predicates.py:107`; **docstring 명제 = "0-path⇒UNKNOWN·1⇒SINGLE_SOURCE·≥2 독립 동의⇒CORROBORATED·불일치⇒CONFLICTED·stale⇒STALE"** — NT §5 line 112 "evidence confidence and contradiction status per field"·§7 line 161 "Majority vote SHALL NOT resolve conflicting semantics"와 **명제 동일**; common-mode≠corroboration §7 line 159); `SafetyRelevantField.{INSTRUMENT_IDENTITY,EXTERNAL_UNATTRIBUTED_ACTIVITY}` non-closed |
| **[소비]** order/knowledge 상태 축 (orthogonality) | StrEnum·`bool` | orthostate `KnowledgeState`·`BrokerOrderState`·`no_coupling_violation`·`reconstruct_conservative` | §6 line 123 orthogonality(`orthostate/vocabulary.py:121/92`·`predicates.py:206/688`; **`no_coupling_violation` 명제 = "no violation DETECTED, never certified fully legal"** — necessary-not-sufficient); NT workflow 축은 별개(§2.2-5) |
| **[소비]** broker corporate/open-order/external-detect capability | StrEnum·`bool` | brokercap `CapabilityDimension.{CORPORATE_ADMINISTRATIVE_EVENTS,OPEN_ORDER_QUERY}`·`external_detection_ok`·`ReplaceSemantics` | §7/§13 broker treatment(`brokercap/vocabulary.py:81/74/202`·`predicates.py:412` `B_external_detect`/`B_external_contain` 주입; broker-agnostic) |
| **[소비]** protective coverage change (open-order adjustment) | `bool`·StrEnum | replacement `overlap_first_reservation_complete`·brokercap `ReplaceSemantics`·orthostate `BrokerOrderState` | §13 line 272 "ADR-002-011 governs"(`replacement/predicates.py:152`); NT-EV-006 주입 소비(§3.5) |
| **[소비]** authority invalidation / no-auto-re-arm | `bool`·StrEnum | authority `rearm_gate`·`AuthorityState.HALTED`·liveauth `no_automatic_rearm`·`authorization_revived_by_nothing` | §17 line 334(`authority/predicates.py:749`·`liveauth/predicates.py:606` "automatic re-arm prevented — always"·`:777`); NT-EV-012 주입 |
| **[소비]** recovery obligation / worst-credible-union restore | value·`bool` | sbr `RecoveryObligation`·`recovery_inventory_complete`·`restore_worst_credible_union`·`unknown_stays_conservative` | §19 line 359 "mandatory ADR-002-017 Recovery Obligations"(`sbr/predicates.py:136/741/314`); NT-EV-011 주입 |
| **[소비]** trustworthy time / effective-boundary freshness | StrEnum·`int\|None` | time `freshness_verdict`·`effective_snapshot_age_bound`·`source_disagreement_within_bound`·`snapshot_grants_no_authority` | §8 line 173(`time/predicates.py:375/218/709/538`); NT-EV-007 주입 |
| **[생산]** envelope/polarity/idempotency completeness | `bool`·`NonTradeDisposition`·`CorrectionReversalOutcome` | 미래 Reconciliation Service·rcl remap-admission·venue invalidation·final-egress 런타임 | NT 술어 산출(§5/§6); 소비자 배선은 런타임(§9.1) |
| **[생산]** all-false authority block | (all-false) | 미래 런타임 (label-grants-nothing) | `NonTradeAuthorityEffect`(로컬 fresh, `_base`; 어떤 True도 unconstructable) |

**(b) 정직 공개 — 전용 술어 실재 vs 좌표-의존 구분 (under-realization 봉합 #18 C2)**: 전용 술어가 **실재**하는 상대
(주입 결과를 정의된 NT 술어로 소비): rcl(`credible_union_capacity`·`RECOGNIZED_EXTERNAL_CHANGE`)·are(`worst_
intermediate_risk`·`credible_space_bounded`·`envelope_bound_not_enlarged`)·venue(`material_change_closure`·`Order
AdmissibilityResult`·**`protective_label_no_bypass`**)·recon(`classify_field`)·brokercap(`external_detection_ok`)·
liveauth(`no_automatic_rearm`)·sbr(`restore_worst_credible_union`)·time(`freshness_verdict`) — 이들은 §3.4 표에서
**produced-bool/StrEnum 전용 슬롯**으로 소비되고 §7에 전용 seam 테스트를 둔다. 반면 아래 seam은 **전용
nontrade-bool 슬롯이 부재한 좌표-의존**이라 정직 이연:
- **orthostate**: order/knowledge 상태는 NT 술어가 **좌표 소비**(주입 StrEnum)하나 orthostate records에 전용
  nontrade-bool 필드는 **부재**(#13 are-orthostate·#18 replacement-orthostate 동형 정직 이연).
- **rcl `CapacityState`/capacity value**: 주입 verdict/value. NT는 rcl capacity를 판정·mutate하지 않는다(§0.2).
- **authority/replacement**: 전부 주입 opaque flag/bool. NT는 이들을 판정하지 않는다.
- **NT leg-set ↔ are cell-set 커버리지 결속 = Phase-1 미실현(M5 정직 공개, v1.1)**: §0.4d는 "NT이 10-leg
  completeness를 판정하고 are가 그 envelope의 risk를 투영한다"고 분업하지만, **NT의 `CredibleTransitionLegKind`
  집합이 are `worst_intermediate_risk`에 입력된 `ProjectedCell` 집합을 실제로 **모두** 덮는지**를 검증하는 결속
  술어는 **Phase-1에 존재하지 않는다**. 즉 caller가 leg 10종을 완비했더라도 are에 넘긴 cell-set이 그중 일부만
  반영했으면 NT도 are도 그 누락을 탐지하지 못한다(각자 자기 집합 안에서만 fail-closed). **판정(택1 명시)**: Phase-1은
  **결속 술어를 신설하지 않고**(대안 `envelope_legs_covered(legs, projected_cell_ids)` 주입 대조 술어는 **미채택**)
  **런타임(EV-L2/3) 잔여로 정직 이연**한다 — 근거: 결속은 are `ProjectedCell` 좌표를 NT이 알아야 성립하는데 그것은
  §0.4c에서 기각한 edge-1(좌표 REUSE)을 되살리거나 opaque id 문자열 대조라는 약한 대리(proxy)에 의존하며, 후자는
  **증명 없이 증명된 척하는 fail-open 서사**가 되기 때문이다. 이 잔여는 §10.4 **G6**에 독립 리뷰어 공격 지점으로
  승격해 명시한다. Phase-1 주장 범위: "NT은 **자신의 leg 집합 안에서** 완전성을 강제한다"이며 "NT leg ≡ are cell"은
  **주장하지 않는다**.

> **명제 동일성 검사(시리즈 규율 개선 3 — #18 C2 category-error 재발 방지)**: 형제 술어를 주입 슬롯으로 소비하기 전,
> **형제 술어 docstring 명제 ↔ 소비하려는 ADR 조항 명제**가 **동일한지** 대조한다. 다르면 좌표-의존 이연/별개
> 슬롯으로 강등한다. **본 사이클 적용(iap exemplar §0.4e)**: NT-EV-010 correction/reversal idempotency를 iap
> `ConsumptionOutcome.IDEMPOTENT_REPLAY`(명제="authorization-token single-use consumption")로 조달하려다 **명제 상이**
> (economic-event-application ≠ authorization-token-consumption) 확인 ⇒ **iap 미소비·canonical `classify_record_pair`
> 직접 앵커**(§4.6). **양성 대조(명제 동일 확인)**: are `worst_intermediate_risk`/`credible_space_bounded`·venue
> `material_change_closure`·recon `classify_field`·are `envelope_bound_not_enlarged`는 위 표에서 docstring 명제 ↔ NT
> ADR 조항 명제가 **동일함을 실측 확인**했으므로 전용 슬롯으로 소비(category-error 없음).

**(c) nontrade는 mutate/transmit/remap-commit/issue하지 않는다(§1 line 19·§10 line 217·§15 line 299·§6 line 144).**
NT은 completeness/coherence/idempotency bool·`NonTradeDisposition`·워크플로 레코드만 생산하고 capacity mutation·egress
transmit·admissibility issue·remap commit·live-scope set 메서드가 **부재**하다(§4.4). 소비 authority(rcl remap
serialize·venue invalidation·final egress)가 실제 action을 gate한다.

**(d) seam cross-check = MANDATED(test-only).** Phase 1은 **test-only** 모듈(`tos/tests/nontrade/test_seam_rcl.py`·
`test_seam_are.py`·`test_seam_venue.py`·`test_seam_recon.py`·`test_seam_orthostate.py`·`test_seam_canonical.py`)에서
nontrade·(각 상대)를 **둘 다 import**해 (i) NT envelope leg ↔ rcl `credible_union_capacity`(empty⇒ValueError·None⇒
UNKNOWN)·are `worst_intermediate_risk`(None⇒None) 정합, (ii) NT material-change ↔ venue `material_change_closure`
(change-trigger⇒closure·unproven expanded)·`OrderAdmissibilityResult` 4토큰+None 전수 접기(`is ADMISSIBLE`만), (iii)
NT correction ↔ canonical `classify_record_pair`(same-bytes⇒IDEMPOTENT_DUP·diff-bytes⇒CRITICAL_CONFLICT), (iv) NT
field-gate ↔ recon `classify_field`(0-path⇒UNKNOWN·common-mode≠corroboration)를 assert한다. **이 테스트는 package
edge가 아니다** — 테스트 import는 §7.1 package-closure 불계상(#11/#13/#16/#18 동형). **acyclic**: nontrade↛{11 형제}
∧ 그들↛nontrade(전부 non-trade 조건을 주입 flag/trigger로 소비·생산; rcl `RECOGNIZED_EXTERNAL_CHANGE` transition이
NT 결정을 주입 슬롯으로 소비 — NT이 상류).

### 3.5 소유권 분할표 — nontrade가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11/#16/#18 §3.5 상속)

> **소유권 분할 명시(#8 C1·#18 교훈 — cross-section 혼동 선제 봉합)**: ADR-002-010은 **non-trade event identity·
> transformation identity·transition-envelope leg 완전성·split 방향 극성·correction/reversal idempotency·event
> workflow lifecycle**만 결정하며 capacity 산술/remap-commit/credible-union(rcl)·aggregate-risk 투영(are)·material-
> change invalidation/admissibility(venue)·per-field confidence(recon)·order/knowledge 상태 축(orthostate)·broker
> capability(brokercap)·protective cancel/replace(replacement)·authority/re-arm(authority/liveauth)·recovery
> obligation(sbr)·trustworthy time(time)·**obligation-lifecycle serialization(ADR-002-030 PTOL)**을 **소유하지
> 않는다**. 함정: NT이 rcl의 `credible_union_capacity`·are의 `worst_intermediate_risk`·venue의 `material_change_
> closure`·recon의 `classify_field`를 재저작하면 권위 중복(#8 lesson). 아래 표가 경계를 코드 실측으로 고정한다.
> 인용은 전부 **코드 실측 signature+라인**(sibling 설계 서사 아님).

| ADR 조항/개념 | nontrade 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향(실측) |
|---|---|---|---|
| §9 transition envelope (10 leg·no-netting) | `transition_envelope_complete`·`CredibleTransitionLegKind`·구조적 no-netting(§5.1) | rcl `credible_union_capacity` 합산(`predicates.py:739`)·are `worst_intermediate_risk` 투영(`predicates.py:186`) | NT이 10-leg 완전성·구조적 no-netting 판정 → rcl union·are risk(주입) — §0.4d 이중 계상 정합 |
| §11 transformation (**6구분 선언**·split 극성·unit/rounding·residual) | `split_polarity_coherent`·**`transformation_units_and_rounding_explicit`**·`transformation_residual_conservative`·`TransformationDirection`(구조 파생, §5.2·§4.5·§2.2-4) + **6구분 선언 의무**(§2.2-7 — 1·2·3 소유, 4 부분, 5·6 형제) | rcl remap arithmetic(배수 적용)·are risk 재투영·venue `InstrumentRouteFields.multiplier`/`currency`·ADR-002-030 obligation | NT이 방향 reciprocal(파생)·unit/rounding explicit·residual explicit 판정 → rcl이 실 배수 remap(주입 소비); "economic equivalence ≠ theoretical ratio"(§11 line 238)·"Every transformation SHALL specify exact units and rounding rules"(§11 line 227) |
| §10 line 219·§16 line 313 correction/reversal | `correction_reversal_idempotent`·`CorrectionReversalOutcome`(§5.3) | canonical `classify_record_pair`(원시, import)·rcl recompute-from-corrected-envelope(§16 line 313) | NT이 lineage+history+at-most-once 판정(canonical 소비) → rcl이 capacity 재계산(주입) |
| §12 instrument lineage + §10 line 221 change-trigger | `instrument_lineage_preserved`(old/new 병존, §6.1)·**`material_change_trigger_nonempty`**(trigger 집합 비공허, §6.3) | **venue `material_change_closure`·`InstrumentRouteFields`·`OrderAdmissibilityResult`·`protective_label_no_bypass`**(`predicates.py:361`/`:599`·`records.py:83`·`vocabulary.py:91`) | venue material-change **closure 계산**·admissibility 발급·protective 4-조건 판정은 전부 venue 소유 → NT은 **change-trigger 생산 + 비공허성만 판정**하고 결과를 주입 소비(§10 line 221); NT은 admissibility·protective 판정 재결정 안 함 |
| §8 effective-time window | `effective_window_blocks_new_risk`(earliest-latest, §6.2) | **time `freshness_verdict`·`source_disagreement_within_bound`·`recovery_generation_revives_nothing`**(`predicates.py:375/709/499`) | time trust/disagreement → NT window block 판정 주입 소비; clock-recovery≠authority(§8 line 175) |
| §7 source/evidence (per-field) | (미소유) NT gate가 소비만 | **recon `classify_field`·`FieldConfidenceClass`**(`predicates.py:107`) | recon field-confidence → NT 주입 소비(§0.2 — 재저작 금지) |
| §9 aggregate-risk / envelope-bound | (미소유) leg 완전성이 소비만 | **are `worst_intermediate_risk`·`credible_space_bounded`·`envelope_bound_not_enlarged`·`EXTERNAL_TRAPPED_NONTRADE_CONCURRENT`**(`predicates.py:186/196/557`·`vocabulary.py:115`) | are aggregate-risk 투영 → NT 주입 소비(§0.4d); NT leg magnitude ≠ are `RiskDimensionKind`(§2.2-5) |
| §1 line 19·§10 line 217 capacity | (미소유) remap propose만 | **rcl `credible_union_capacity`·`CapacityState`·`RECOGNIZED_EXTERNAL_CHANGE`·`CREATE_EXTERNAL_QUARANTINE`·`MARK_TRAPPED_EXPOSURE`** | rcl-only capacity(§10 line 217 "SHALL NOT update capacity independently") → NT propose·주입 소비 |
| §13 open orders / protective coverage | (미소유) 좌표 소비만 | **replacement `overlap_first_reservation_complete`**·brokercap `ReplaceSemantics`·`OPEN_ORDER_QUERY`·orthostate `BrokerOrderState` | replacement/brokercap/orthostate → NT 주입 소비(§13 line 272 "ADR-002-011 governs"·NT-EV-006 L3/5) |
| §14 derivative lifecycle | (미소유) 좌표 소비만 | **are `OPTION_GREEKS_EXERCISE_ASSIGNMENT`·`SETTLEMENT_CASH_CURRENCY`**·brokercap·orthostate | are/brokercap → NT 주입 소비(§14 line 289 "absence ≠ no assignment"·NT-EV-004/005 +Broker) |
| §16 unattributed correction/transfer | (미소유) event identity만 | **recon `EXTERNAL_UNATTRIBUTED_ACTIVITY`·`FieldConfidenceClass.UNKNOWN`**·rcl `QUARANTINED_UNKNOWN`·**ADR-002-030 PTOL** | recon/rcl → NT 주입 소비(§16 line 311 no-relabel·NT-EV-008); §16 line 309 obligation-lifecycle=ADR-002-030 |
| §6 workflow lifecycle | `NonTradeEventWorkflowState`·no-collapse·label-grants-nothing(§4.4·§5.4) | orthostate order/knowledge/capacity(별개 축, `vocabulary.py:121/92`)·rcl capacity state | NT이 event-workflow 축 소유; order/knowledge/capacity는 주입 좌표(§2.2-5 비붕괴) |
| §17 authority invalidation / re-arm | (미소유) 소비만 | **authority `rearm_gate`·liveauth `no_automatic_rearm`·`authorization_revived_by_nothing`** | authority/liveauth → NT 주입 소비(§17 line 334 "SHALL NOT automatically re-arm"·NT-EV-012) |
| §19 startup/recovery/replay | (미소유) recovery obligation 생산만 | **sbr `RecoveryObligation`·`recovery_inventory_complete`·`restore_worst_credible_union`** | sbr → NT 주입 소비; NT event가 sbr recovery obligation 입력(§19 line 359·NT-EV-011) |
| §10 atomic transition / §18 containment | pre/post envelope value | rcl 원자 remap·durable protocol(§10 line 215)·authority containment(런타임) | NT은 pre/post envelope·workflow 상태만; 원자 remap·containment enforce는 런타임(NT-EV-009) |
| §20 evidence | frozen digest-bound 레코드 재구성(§5.6) | ADR-002-016 replay ENGINE(런타임) | NT 레코드; replay engine 런타임(§20 line 392 "successful replay are not completed evidence") |

> **핵심 소유권 판정 3건(사전 브리핑 응답)**:
> 1. **replacement ↔ nontrade 분할(NT-EV-006)**: replacement가 protective-order cancel/replace·gap/overlap·overlap-
>    first reservation을 소유하고, nontrade는 그것을 **트리거하는 non-trade EVENT identity·transformation**을 소유
>    한다. **분할 축 = 인과**: nontrade = 원인(corporate action이 open order를 바꿔야 함을 인식), replacement = 결과
>    (cancel/replace 메커니즘). ADR-002-011 §16 line 367이 recovery에서 "recognized non-trade changes"를 nontrade로
>    **명시 이연**하고 ADR-002-010 §13 line 272가 protective replacement를 replacement로 **명시 이연** — 상호 명시
>    경계로 중복 0. NT-EV-006은 L3/5(닫지 않음).
> 2. **are ↔ nontrade 분할(envelope risk, §0.4d 상술)**: nontrade가 10-leg completeness+구조적 no-netting을 소유
>    하고, are가 `worst_intermediate_risk` 투영·credible-space-bounded를 소유한다. **결정적 증거**: are가 이미
>    `AdverseScenarioKind.EXTERNAL_TRAPPED_NONTRADE_CONCURRENT`(`vocabulary.py:115`)로 non-trade 동시 trapped 시나리오
>    를 aggregate-risk 축에 first-class로 소유한다 — nontrade가 risk를 재투영하면 좌표 충돌·권위 중복. 중복 아님 —
>    다른 좌표축(§2.2-5).
> 3. **idempotency 3-술어 분할(§0.4e 상술)**: NT economic-event-application idempotency(`correction_reversal_
>    idempotent`)·iap authorization-token single-use(`ConsumptionOutcome.IDEMPOTENT_REPLAY`)·rcl capacity-command
>    (`ApplyReason.IDEMPOTENT_REPLAY`)는 **canonical `classify_record_pair` 원시의 세 독립 하류**다 — 명제 상이·상호
>    import 없음. NT은 iap/rcl idempotency를 재저작·소비하지 않고 canonical 원시를 직접 앵커한다. phantom edge 차단.

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 NT-EV-001..012·NT-AC-001..012
(§21)·§-clause·SAFE-###(§24)**이며 **새 시리즈를 창작하지 않는다**(§0.4g). **fail-closed discipline**: 미포함/미증명/
netting/None/stale/non-reciprocal/no-lineage/overwrite/label에 대한 술어는 절대 vacuous permissive가 되지 않으며,
`NONTRADE_ADMISSIBLE`/complete는 *양성 conjunction identity 증명*을 요구하고(잔여 fall-through 금지 — #16 CRITICAL),
각 가드에 **both-ways canary**(가드가 실제로 발화함 ∧ 정당한 통과를 막지 않음)를 붙인다.

### 4.1 transition-envelope completeness + no-netting 중앙 불변식 (ADR §9; NT-EV-002; NT-AC-002)

**중앙 결정**: transition envelope은 event 중 **모든 credible economic state**를 담아야 하며(§9 line 181 "containing
all credible economic states during the event"), favorable effect를 uncertain adverse effect에 netting 금지다(§9
line 196 verbatim "Favorable effects SHALL NOT be netted against uncertain adverse effects"). 실현(구조적):

1. **`transition_envelope_complete`에 permissive 기본값 부재**: 오직 applicable한 `CredibleTransitionLegKind`(§2.2-3,
   §9 line 185–194 10종의 event-class-applicable subset)가 전부 envelope에 포함(`required ⊆ present`)될 때만 True.
   missing leg ⇒ incomplete ⇒ False(§9 line 183 "SHALL include where applicable"·NT-AC-002 "worst credible transition
   envelope"). **∅ 빈 leg set ⇒ "no risk" 아님 ⇒ `NONTRADE_BLOCK_NEW_RISK`**(§4.7).
2. **구조적 no-netting 파생(flag 아님, §0.4d)**: `favorable_netting_absent`는 `pre_event_exposure`·`post_event_
   credible_exposure`가 **둘 다 present(not None)·비음수로 별개 병존**할 때만 True — netting을 적용하면 old를 new로
   상쇄해 하나가 소거되므로, 둘이 별개 비음수 magnitude로 병존하면 netting은 **구조적으로 불가능**하다(caller가 flag로
   위조 불가). 하나라도 None/음수 ⇒ netting 의심·incomplete ⇒ False. **`favorable_netted` 같은 음극성 flag 필드는
   모델에 존재하지 않는다(M7)** — no-netting은 **오직 magnitude 병존 파생**으로만 증명되며, flag 게이트 문구
   (`is False` 통과 규칙)를 no-netting에 적용하는 서술은 v1.1에서 제거했다(§0.1(8)·§0.4d 구조-파생 서술로 통일).
3. **capacity/risk 미산출**: envelope leg magnitude(`CanonicalDecimal|None`)는 담되 **합산·headroom·risk 투영은 하지
   않는다** — rcl `credible_union_capacity`(union·empty-fail-closed)·are `worst_intermediate_risk`가 주입 verdict로
   소비된다(§0.4c 좌표 충돌 회피). NT은 completeness+no-netting만.

**canary(both-ways)**: (a) leg 누락·netting(pre 또는 post None)·favorable 상쇄 시도 ⇒ incomplete/False(가드 발화);
(b) 10-applicable-leg 전부 present + pre/post 병존·비음수 ⇒ `envelope_complete is True`(양성 side). **NT-EV-002 좌표·
`/3` 잔여 — 닫지 않음.** [SAFE-002·SAFE-004·SAFE-013 unmanaged exposure·envelope]

### 4.2 split/reverse-split 방향 극성 coherence + residual 중앙 불변식 (ADR §11; NT-EV-001; NT-AC-001)

**중앙 결정**: 모든 transformation은 exact unit·rounding rule을 명시하고(§11 line 227) theoretical ratio로 economic
equivalence를 가정 금지다(§11 line 238 verbatim "Economic equivalence SHALL NOT be assumed from a theoretical
ratio"). transformed state를 exact 표현 불가면 residual은 explicit·capacity-consuming(§11 line 240). 실현(구조적):

1. **`split_polarity_coherent`는 구조-파생 방향의 reciprocal 관계(M2)**: `SplitTransformationSpec`은
   `pre_quantity`/`post_quantity`·`pre_basis`/`post_basis`(`CanonicalDecimal|None`)를 담고, 각 축의
   `TransformationDirection`을 **multiplicative identity 대비 비교로 파생**한다(post > pre ⇒ `AMPLIFY`·< ⇒
   `ATTENUATE`·= ⇒ `IDENTITY`; 어떤 배수도 하드코딩하지 않음). coherent는 (i) **파생된** 두 방향이 **reciprocal**
   (`AMPLIFY`↔`ATTENUATE` 또는 `IDENTITY`↔`IDENTITY`)이고 (ii) declared `SplitTransformationKind`와 **파생 방향**이
   일치(`FORWARD_SPLIT`⇒quantity `AMPLIFY`·basis `ATTENUATE`; `REVERSE_SPLIT`⇒quantity `ATTENUATE`·basis `AMPLIFY`)할
   때만 True(§4.5 진리표 A ∧ B). **극성 대수는 여전히 enum 관계이고(§4.5 진리표 불변) 입력만 caller 선언 flag에서
   구조 파생으로 승격**했다 — v1.0은 direction enum을 caller가 그대로 선언했으므로 mis-declared direction이
   진리표를 통과할 수 있었다(#18 no-netting 구조-파생 선례 §0.4d 미적용 지대). 네 magnitude 중 하나라도 None ⇒
   파생 불가 ⇒ fail-closed(§4.7 행 3).
2. **`transformation_units_and_rounding_explicit`(M1 신설)**: `spec.unit_spec`·`spec.rounding_rule`이 **둘 다
   not-None**일 때만 True. ADR §11 line 227 verbatim "**Every** transformation SHALL specify exact units and rounding
   rules" — v1.0은 이 문장을 §4.2 서두에 인용만 하고 강제하는 conjunct가 없었다. 이 술어는
   `split_polarity_coherent`·`transformation_residual_conservative`와 **별도 conjunct**이며(fall-through 승격 금지)
   §2.2-7 6구분 중 1·2를 실현한다. 어느 하나라도 None ⇒ False(§4.7 행 4).
3. **`transformation_residual_conservative`**: fractional entitlement·cash-in-lieu가 **explicit·present(not None)·
   비음수**일 때만 True(§11 line 240·§11 line 233 "fractional entitlement from tradable whole quantity"). residual
   absent/netted ⇒ incomplete ⇒ False. broker rounding·cash-in-lieu·fee·tax·margin이 risk를 바꿀 수 있음(§11 line
   238)을 residual explicitness로 보존.
4. **no capacity-release-on-transformation(구조적 부재)**: NT은 transformation이 capacity를 release한다고 판정하지
   않는다 — §10 line 221 "neither the event nor a favorable projection releases capacity"·§1 line 28. release는 rcl
   proof 소유. **실현 방식(M7)**: `released_on_transformation` 같은 음극성 flag 필드를 두고 `is False`를 요구하는
   것이 **아니라**, NT 모델·술어에 **release를 표현할 필드도 판정할 술어도 존재하지 않는다**(unconstructable —
   `NonTradeAuthorityEffect` all-false와 동형). flag 부재가 곧 강제다.

**canary(both-ways)**: (a) 같은 방향 배수(both AMPLIFY/both ATTENUATE)·kind-direction 불일치·pre/post magnitude
None·`unit_spec`/`rounding_rule` None·residual None ⇒ INVALID/incomplete(가드 발화, 부호오류 차단); (b) reciprocal +
kind 일치 + unit/rounding explicit + residual explicit ⇒ `polarity_coherent is True` ∧ `units_and_rounding_explicit
is True` ∧ `residual_conservative is True`(양성 side). **NT-EV-001 좌표·`/3`·`+Broker` 잔여 — 닫지 않음.**
[SAFE-015 RCL-only·SAFE-025 partial/delayed]

### 4.3 correction/reversal idempotency + lineage 중앙 불변식 (ADR §10 line 219·§16 line 313; NT-EV-010; NT-AC-010)

**중앙 결정(시리즈 최초 idempotency-중심 L1 슬라이스)**: history는 destructive overwrite가 아니라 new versioned fact로
정정하며(§10 line 219 verbatim "History SHALL be corrected by new versioned facts, not destructive overwrite. A
correction or reversal is a new event linked to the event it supersedes") 원본+정정 이벤트를 둘 다 보존한다(§16 line
313 "local history SHALL preserve both the original observation and correcting event"). 재적용은 idempotent version
check로만(§19 line 366 "reapply events only through idempotent version checks"). 실현(구조적):

1. **`correction_reversal_idempotent -> CorrectionReversalOutcome`(6종, §2.2-5)**: 선행 게이트 3 + classify 매핑 —
   (i) **lineage present**(`supersedes_ref` not None; 부재 ⇒ `REJECTED_NO_LINEAGE`, §16 line 311 "SHALL not relabel
   an unexplained position change as a correction merely to make reconciliation pass"), (ii) **history preserved**
   (원본 append-only retained·not overwritten; overwrite ⇒ `REJECTED_OVERWRITE`, §10 line 219), (iii) **`prior is
   None`(첫 정정) ⇒ `APPLIED_ONCE`**(C2 선행 게이트 — prior 부재를 classify 호출 전에 분리, 없으면 NOT_COMPARABLE로
   정당 최초 정정 영구 거부), (iv) **at-most-once application**(canonical `classify_record_pair(incoming.id,
   incoming.digest, prior.id, prior.digest, a_idempotency_id=incoming.key, b_idempotency_id=prior.key)` 실측 4-pos+2-kw:
   `IDEMPOTENT_DUP`⇒`IDEMPOTENT_REPLAY` no-op·`CRITICAL_CONFLICT`(same **primary** id·diff bytes)⇒`REJECTED_CONFLICT`·
   `DIVERGENT_EMISSION`(same **idempotency** id·diff bytes)⇒`REJECTED_CONFLICT`·`DISTINCT`/`NOT_COMPARABLE`⇒`REJECTED_
   UNKNOWN`).
2. **at-most-once = economic effect 1회**: 정당 적용(`APPLIED_ONCE`)은 effect count를 1로 만들고, 재적용(`IDEMPOTENT_
   REPLAY`)은 **no-op**(effect count 불변). **위조는 두 축이며 서로 다른 `RecordPairKind`다(C2 — v1.0 반전 매핑
   정정)**: (a) **same primary id·diff bytes ⇒ `CRITICAL_CONFLICT`**(`record_pair.py:96` — 동일 레코드 identity를
   주장하는 상이 bytes = 레코드 위조), (b) **same idempotency key·diff bytes ⇒ `DIVERGENT_EMISSION`**
   (`record_pair.py:103` — 상이한 두 correction이 같은 idempotency key를 주장 = divergent emission). **둘 다
   `REJECTED_CONFLICT`로 접히며**(contain-both·no last-write-wins — canonical `record_pair.py:68` "no last-write-wins
   merge") **어느 쪽도 silent double-apply되지 않는다**. "same-key-diff-bytes ⇒ `CRITICAL_CONFLICT`"라는 v1.0 서술은
   두 축을 뒤바꾼 것이었다.
3. **canonical 원시 직접 앵커(§0.4e)**: iap `IDEMPOTENT_REPLAY`(authorization-token)·rcl `ApplyReason.IDEMPOTENT_
   REPLAY`(capacity-command)와 별개 축 — NT은 canonical `classify_record_pair`를 직접 소비(형제 import 없음).

**canary(both-ways)**: (a) lineage 부재/overwrite/same-key-diff-bytes ⇒ REJECTED_*(가드 발화); (b) lineage+history+
distinct ⇒ `APPLIED_ONCE`(정당 정정, 양성 side). **double-application canary(§7)**: 동일 correction event를 N≥2회
적용 ⇒ effect count == 1(2회+ `IDEMPOTENT_REPLAY`). **NT-EV-010 좌표·`/3` 잔여 — 닫지 않음.** [SAFE-020 lineage·
SAFE-051/052 evidence·replay]

### 4.4 representation ≠ enforcement / workflow-label-grants-nothing (ADR §1 line 15·§6 line 144·§10 line 217; core substrate)

**중앙 결정**: non-trade event는 fill로 fabricate·correction으로 silent fold·harmless reference-data change로 취급
금지다(§1 line 15). 어떤 workflow state도 그 자체로 capacity release·instrument close·final quantity proof·authority
grant를 하지 않는다(§6 line 144 verbatim). 실현:

1. **`NonTradeAuthorityEffect` all-false**: 어떤 True도 unconstructable(rcl `AllFalseAuthority`·are/afg/iap `_base`
   동형). workflow lifecycle state 무엇이든 authority effect는 all-false(`APPLIED_LOCAL`도, `RECONCILED`도).
2. **orthogonality(§6 line 123)**: `NonTradeEventWorkflowState`는 order/exposure/capacity/authority/evidence-
   confidence 축과 별개 — collapse 금지(§2.2-5; orthostate `no_coupling_violation` 좌표 소비).
3. **`APPLIED_LOCAL` ≠ broker-applied**(§6 line 142)·**`RECONCILED` requires evidence(recon)**(§6 line 143): NT은
   label로 broker truth를 주장하지 않고 recon evidence 주입을 요구.

**canary(both-ways)**: (a) 어떤 workflow state로도 authority effect True 시도 ⇒ 구성 불가(가드 발화); (b) label은
결코 authority 부여 안 함 — 양성 side 없음(#18 §4.4 동형). [SAFE-011 egress·SAFE-041 authority]

### 4.5 방향 극성 검산 — split/reverse-split 수량·가격 배수 진리표 (ADR §11; 사전 브리핑 지목 함정·#16 C1 방향-반전 교훈 선제 봉합)

**forward split(수량↑·가격↓)과 reverse split(수량↓·가격↑)은 반대 방향 규칙**이므로 진리표로 검산한다(#16이 §1:25
smallest vs §10:276 largest를 혼동한 CRITICAL 교훈 동형 — split 수량·가격 배수가 **같은 방향**이면 부호오류·fail-open).
극성 **대수**는 `TransformationDirection`(`AMPLIFY`/`ATTENUATE`/`IDENTITY`) enum reciprocal로 판정한다.

> **v1.1 M2 — 진리표는 그대로, 입력만 구조 파생으로 승격**: 아래 두 진리표의 cell·판정은 **변경 없다**. 달라진 것은
> `quantity_direction`·`basis_direction`이 **caller 선언 enum이 아니라 `SplitTransformationSpec`의
> `pre_quantity`/`post_quantity`·`pre_basis`/`post_basis`에서 multiplicative identity 대비 비교로 파생된 값**이라는
> 점뿐이다(§2.2-4·§4.2-1). 따라서 표의 행/열 좌표는 **파생 방향**이고, 표 B의 "declared kind"만 caller 선언이며
> 표 B가 곧 **선언 ↔ 파생 대조**다. 특정 배수(2-for-1의 2 등)는 여전히 어디에도 하드코딩되지 않는다 — 비교는
> `CanonicalDecimal` scale-normalize 후 `>`/`<`/`==` 3분기뿐이다.

**진리표 A — quantity_direction × basis_direction reciprocal 검산(3×3 = 9 cell; 두 방향 모두 파생값)**:

| quantity ＼ basis | `AMPLIFY` | `ATTENUATE` | `IDENTITY` |
|---|---|---|---|
| **`AMPLIFY`** | ✗ both-amplify(부호오류·notional N² 과대 or 과소 — 방향불명·reject) | ✓ **`FORWARD_SPLIT`**(수량↑·가격↓) | ✗ 비대칭(가격 미변경인데 수량↑ — mis-spec·reject) |
| **`ATTENUATE`** | ✓ **`REVERSE_SPLIT`**(수량↓·가격↑) | ✗ both-attenuate(부호오류·fail-open 방향 — reject) | ✗ 비대칭(reject) |
| **`IDENTITY`** | ✗ 비대칭(reject) | ✗ 비대칭(reject) | ✓ no-op(identity transform — 무변경) |

**reciprocal True cell = 3**(FORWARD·REVERSE·no-op); **incoherent False cell = 6**(3 + 6 = 9 전수). 파생 불가
(네 magnitude 중 어느 하나라도 None) ⇒ fail-closed(표 밖 — §4.7 행 3).

**진리표 B — declared kind × derived direction 일치 검산(kind-direction match)**:

| declared `SplitTransformationKind` | 요구 quantity_direction | 요구 basis_direction | 불일치 시 |
|---|---|---|---|
| `FORWARD_SPLIT` | `AMPLIFY` | `ATTENUATE` | mis-labeled(reverse를 forward로 오표기) ⇒ INVALID·fail-closed |
| `REVERSE_SPLIT` | `ATTENUATE` | `AMPLIFY` | mis-labeled ⇒ INVALID·fail-closed |

**검산 규칙**: `split_polarity_coherent`는 **진리표 A(reciprocal) ∧ 진리표 B(kind-match)** 양쪽을 별도 conjunction으로
검사(fall-through로 coherent 승격 금지 — #16 CRITICAL). **fail-open 함정 명시**: forward split을 (quantity `ATTENUATE`,
basis `ATTENUATE`)로 잘못 모델링하면 notional이 과소평가되어(under-estimate) risk를 놓친다 — 진리표 A의 both-attenuate
cell이 이를 reject. 반대로 both-amplify는 과대평가(보수적)이나 방향불명이므로 역시 reject(mis-spec은 어느 방향이든
차단). **magnitude(`CanonicalDecimal`)의 역할(v1.1 M2 정정)**: 극성 **대수**는 direction enum 관계이되, 그 enum 값의
**출처**는 `pre_*`/`post_*` magnitude의 identity-대비 3분기 비교(구조 파생)이고, magnitude는 그 외 residual/envelope
표현에도 쓰인다. **특정 배수(2-for-1의 2 등)는 어디에도 하드코딩하지 않는다** — 비교 연산 3종만 사용한다.
[SAFE-015 RCL-only remap·SAFE-025 rounding/partial]

### 4.6 correction/reversal idempotency·중복 적용 진리표 (ADR §10 line 219·§16 line 313; NT-EV-010; 시리즈 최초 idempotency-중심 슬라이스)

**correction/reversal 재적용은 idempotent version check로만 정당**하며(§19 line 366), same-**idempotency**-key·diff-
bytes는 double-apply가 아니라 conflict(`DIVERGENT_EMISSION`)다(canonical `classify_record_pair` 실측). 진리표로 중복
적용 canary를 검산한다. **선행 게이트(classify 이전, 순서)**: `supersedes_ref` 부재 ⇒ `REJECTED_NO_LINEAGE`(§16 line
311); `original_retained is not True`(overwrite) ⇒ `REJECTED_OVERWRITE`(§10 line 219); **`prior is None`(첫 정정) ⇒
`APPLIED_ONCE`**(C2 — prior 부재 시 classify는 NOT_COMPARABLE를 반환하므로 정당한 최초 정정이 영구 거부되지 않도록
선행 분기). 그 다음 `classify_record_pair(incoming.id, incoming.digest, prior.id, prior.digest, a_idempotency_id=
incoming.key, b_idempotency_id=prior.key)`(실측 4-positional+2-keyword) 호출:

**진리표 — 선행 게이트 통과 후 `classify_record_pair(...)` (실측 `record_pair.py`) → `CorrectionReversalOutcome`**:

| classify 반환 (실측 라인) | → `CorrectionReversalOutcome` | economic effect count |
|---|---|---|
| `IDEMPOTENT_DUP` (same primary/idempotency id·same bytes, :94) | `IDEMPOTENT_REPLAY` | **+0 (no-op, 무해)** |
| `CRITICAL_CONFLICT` (same **primary** id·diff bytes, :96) | `REJECTED_CONFLICT` | **+0 (레코드 위조·contain-both·no LWW)** |
| `DIVERGENT_EMISSION` (same **idempotency** id·diff bytes, :103) | `REJECTED_CONFLICT` | **+0 (divergent emission·contain-both)** |
| `DISTINCT` (id·key 둘 다 상이 — 계약상 prior가 key 미공유, :105) | `REJECTED_UNKNOWN` | +0 (fail-closed) |
| `NOT_COMPARABLE` (digest None, :87) | `REJECTED_UNKNOWN` | +0 (fail-closed) |

(선행 게이트 outcome: `REJECTED_NO_LINEAGE`·`REJECTED_OVERWRITE` +0; `APPLIED_ONCE`(prior None) +1.) **RecordPairKind
5-member 전수 매핑** — DIVERGENT_EMISSION 미매핑·APPLIED_ONCE 구조적 도달불가 결함(v1.0)을 봉합.

**중복 적용 canary(§7 명시)**: (a) **double-application**: 동일 correction event(same idempotency key·same bytes)를
N≥2회 적용 ⇒ 첫 회 prior=None ⇒ `APPLIED_ONCE`(effect+1)·2회+ prior 존재·same bytes ⇒ `IDEMPOTENT_DUP` ⇒
`IDEMPOTENT_REPLAY`(effect+0) ⇒ 총 effect count == 1(재적용 무해성). (b) **forgery 2종 분리(C2-c)**: (b1) same
**primary** id·diff canonical digest ⇒ `CRITICAL_CONFLICT` ⇒ `REJECTED_CONFLICT`(레코드 위조·양쪽 보존·no LWW);
(b2) same **idempotency** key·diff canonical digest ⇒ `DIVERGENT_EMISSION` ⇒ `REJECTED_CONFLICT`(두 상이 correction이
같은 key 주장) — 어느 위조도 silent double-apply되지 않음. (c) **both-ways 정당 통과**: prior=None인 서로 다른 정당
correction은 각각 `APPLIED_ONCE`(availability side — 정정 자체는 막지 않음). [SAFE-020 lineage·SAFE-051
executed evidence·SAFE-052 reconstructable replay]

### 4.7 ∅-공허 fail-closed (양방향 명시 — #10/#11/#16/#18 code-review MAJOR 교훈)

빈 입력의 **모든 방향**을 명문화한다(표의 방향이 하나뿐이면 불변식의 전 금지 동사와 대조해 커버리지 명시). NT 금지
동사(**ADR 전 조항 스윕 §1–§22 — 개별 번호 계수**): (1) **fabricate-fill**(§1 line 15·§22.1) · (2)
**fold-into-correction**(§1 line 15) · (3) **net-favorable-against-adverse**(§9 line 196·§22.6) · (4)
**assume-equivalence-from-ratio**(§11 line 238·§22.5) · (5) **same-direction-split-multiplier**(§4.5 부호오류) ·
(6) **omit-units-or-rounding**(§11 line 227, M1) · (7) **release-on-transformation**(§10 line 221·§1 line 28) ·
(8) **relabel-unexplained-as-correction**(§16 line 311) · (9) **destructive-overwrite-history**(§10 line 219) ·
(10) **double-apply-correction**(§4.6) · (11) **update-capacity-independently**(§10 line 217) · (12)
**treat-reference-data-as-mutation**(§22.2) · (13) **assume-broker-adjusts-correctly**(§22.3) · (14)
**treat-expired-as-zero-risk**(§12 line 252·§22.4) · (15) **silently-reassign-instrument**(§12 line 250) · (16)
**skip-invalidation-on-material-change**(§10 line 221, M3) · (17) **auto-re-arm-on-completion**(§17 line 334·§22.7) ·
(18) **remove-UNKNOWN-by-operator-label**(§18 line 351) · (19) **collapse-effective-times**(§8 line 171).
**금지 동사 = 19개**(v1.0 17개 + M1 `omit-units-or-rounding` + M3 `skip-invalidation-on-material-change`).

**C1 재매핑(v1.1)**: 아래 표의 **모든 행이 `nontrade_disposition(...) -> NonTradeDisposition`(§5.5)의 반환값으로
재매핑**된다 — v1.0의 "∅ ⇒ **별도 처리**에서 `NONTRADE_BLOCK_NEW_RISK`"라는 무주(無主) 위임은 제거되었다. 각 행의
"금지 방향" 셀은 개별 술어의 `bool`/outcome을, 마지막 열은 그것이 접히는 **최종 disposition**을 명시한다. disposition
우선순위(전순서·결정적): `NONTRADE_CONFLICTED` > `NONTRADE_QUARANTINED_UNKNOWN` > `NONTRADE_TRAPPED` >
`NONTRADE_BLOCK_NEW_RISK` > `NONTRADE_ADMISSIBLE`.

| # | 빈/미증명 입력 | 금지 방향(vacuous permissive 차단) | 허용 방향(양성 side) | `nontrade_disposition` 반환(§5.5) | 근거 |
|---|---|---|---|---|---|
| 1 | **빈 `required_legs` set** | 평가 leg 부재 ⇒ "no risk" 아님 ⇒ completeness 증명 불가 ⇒ **술어 내부 구조 가드** `if not required_legs: return False`(C1 — caller 위임 아님) | applicable 10-leg subset 전부 포함 + no-netting ⇒ `transition_envelope_complete is True` | `NONTRADE_BLOCK_NEW_RISK` | §9 line 183–194; NT-AC-002; rcl `credible_union_capacity` empty⇒`ValueError` 선례(`rcl/predicates.py:768`) |
| 2 | **pre/post exposure 중 None/음수**(구조적 no-netting) | 하나라도 None/음수 ⇒ netting 의심·미증명 ⇒ `favorable_netting_absent` `False`(**flag가 아니라 magnitude 병존 파생**) | pre·post 둘 다 present·비음수 ⇒ 구조적 no-netting ⇒ 통과 | `NONTRADE_BLOCK_NEW_RISK` | §9 line 196; §4.1 (2) |
| 3 | **pre/post quantity·basis magnitude 중 None**(극성 파생 입력, M2) | 네 magnitude 중 하나라도 None ⇒ `TransformationDirection` **파생 불가** ⇒ `split_polarity_coherent` `False`(INVALID) | 네 magnitude 전부 present ⇒ 방향 파생 ⇒ reciprocal + kind-match ⇒ `True` | `NONTRADE_BLOCK_NEW_RISK` | §11; §4.5; §2.2-4 |
| 4 | **`unit_spec` / `rounding_rule` = None**(M1) | 둘 중 하나라도 None ⇒ `transformation_units_and_rounding_explicit` `False` — "exact units and rounding rules" 미명시 transformation은 진행 불가 | 둘 다 not-None ⇒ `True` | `NONTRADE_BLOCK_NEW_RISK` | §11 line 227 verbatim |
| 5 | **residual absent(None)** | fractional/cash-in-lieu None ⇒ `transformation_residual_conservative` `False`(residual 은닉 금지) | 둘 다 present·비음수 ⇒ `True` | `NONTRADE_BLOCK_NEW_RISK` | §11 line 240; §4.2 (2) |
| 6 | **빈 change-trigger set**(M3, venue seam) | **`event_is_material is not False`**(즉 `True` **또는 `None`** — "Unknown materiality is material", `venue/predicates.py:379`)인데 trigger set이 ∅ ⇒ venue `material_change_closure`가 **∅ 반환**(= 아무것도 무효화 안 됨) ⇒ stale admissibility가 살아남는 **fail-open** ⇒ `material_change_trigger_nonempty` `False` ⇒ block | **`event_is_material is False`**(non-material임이 **적극 증명**된 경우)에만 ∅ trigger가 **정당** — venue docstring "An **empty** ``change_triggers`` yields the empty set — no change, nothing invalidated (the availability side)" ⇒ 술어 면제·다른 conjunct로 진행 | material 또는 미지 ⇒ `NONTRADE_BLOCK_NEW_RISK` / `is False` ⇒ 불변(다른 conjunct 결정) | §10 line 221; venue `predicates.py:361`/`:379` docstring 실측 |
| 7 | **`supersedes_ref` 부재** | lineage 부재 ⇒ `REJECTED_NO_LINEAGE`(no-relabel) | supersedes present + retained + prior None/동일 bytes ⇒ `APPLIED_ONCE`/`IDEMPOTENT_REPLAY` | `NONTRADE_BLOCK_NEW_RISK` | §16 line 311; §4.6 |
| 8 | **`classify_record_pair` = `CRITICAL_CONFLICT`**(same **primary** id·diff bytes, `record_pair.py:96`) | 레코드 위조 ⇒ `REJECTED_CONFLICT`(contain-both·no LWW·double-apply 금지) | same primary id·**same** bytes ⇒ `IDEMPOTENT_DUP`(:94) ⇒ `IDEMPOTENT_REPLAY`(no-op) | `NONTRADE_CONFLICTED` | §4.6; canonical `record_pair.py:43/68/96` |
| 9 | **`classify_record_pair` = `DIVERGENT_EMISSION`**(same **idempotency** id·diff bytes, `record_pair.py:103`) | 두 상이 correction이 같은 key 주장 ⇒ `REJECTED_CONFLICT`(contain-both) | same idempotency id·**same** bytes ⇒ `IDEMPOTENT_DUP`(:101) ⇒ `IDEMPOTENT_REPLAY`(no-op) | `NONTRADE_CONFLICTED` | §4.6; canonical `record_pair.py:45/103` |
| 10 | **`classify_record_pair` = `DISTINCT`(:105) / `NOT_COMPARABLE`(digest None, :87)** | key 미공유(계약 위반)·pre-issuance digest ⇒ 판정 불가 ⇒ `REJECTED_UNKNOWN` | (해당 없음 — 정당한 최초 정정은 `prior is None` **선행 게이트**로 `APPLIED_ONCE`, classify에 도달하지 않음) | `NONTRADE_QUARANTINED_UNKNOWN` | §4.6; canonical `record_pair.py:47/49/87/105` |
| 11 | **None aggregate-risk / capacity**(are·rcl 주입) | are `worst_intermediate_risk` None / `credible_space_bounded` None·False / rcl union UNKNOWN ⇒ 비교 불가 | finite risk + `credible_space_bounded is True` ⇒ 비교 가능 | `NONTRADE_BLOCK_NEW_RISK` | §9; §0.4d; `are/predicates.py:186/196` |
| 12 | **`OrderAdmissibilityResult` = `RESTRICTED_PROTECTIVE_ONLY`**(venue 주입, M6) | **통상 신규 위험은 block** — `is ADMISSIBLE`가 아니므로 ordinary fresh-decision conjunct 미충족(`if result:` truthy 오독 시 protective-only를 full permission으로 읽는 치명적 fail-open, venue `vocabulary.py:91` docstring) | **protective action은 허용** — venue `protective_label_no_bypass`(`predicates.py:599`) 산출 `bool`을 `protective_action_may_proceed is True`로 주입받은 경우에 한해 protective/recovery action만 진행(NT은 그 4-조건을 판정하지 않음) | `NONTRADE_BLOCK_NEW_RISK`(protective 경로는 별도 주입 좌표로 허용) | §10 line 221; §18 line 348 "permit only newly authorized recovery or protective action"; §3.4 |
| 13 | **`OrderAdmissibilityResult` = `INADMISSIBLE` / `UNKNOWN` / `None`**(venue 주입, M6) | fresh exact decision 부재 ⇒ 청산 불가 = trapped(zero-risk 아님). **무조건** — `protective_action_may_proceed`가 `True`로 주입돼도 완화되지 않는다(불일치 주입 fail-open 차단, §5.5) | (해당 없음 — `is ADMISSIBLE` 또는 `is RESTRICTED_PROTECTIVE_ONLY`만 양성 side) | `NONTRADE_TRAPPED` | §12 line 252; §10 line 221; §22.4 |
| 14 | **`FieldConfidenceClass` = `UNKNOWN` / `CONFLICTED`**(recon 주입) | UNKNOWN ⇒ 미귀속 quarantine / CONFLICTED ⇒ 모순 | 전 material field `CORROBORATED` + fresh ⇒ field gate 통과 | UNKNOWN ⇒ `NONTRADE_QUARANTINED_UNKNOWN` / CONFLICTED ⇒ `NONTRADE_CONFLICTED` | §7 line 163; §18 line 344; `recon/predicates.py:107` |
| 15 | **빈 workflow state / 어떤 label** | 상태 부재·어떤 label ⇒ label-grants-nothing ⇒ 어떤 authority도 없음(`NonTradeAuthorityEffect` all-false) | (양성 side 없음 — label은 결코 authority 부여 안 함) | **disposition 불변** — 어떤 workflow label도 disposition을 상향시키지 못한다 | §6 line 144 verbatim |

**행 수 = 15**(개별 계수 1–15). **§7 ∅-공허 회귀 목록과 1:1**(§7 "∅ 케이스" 15항목).

**양방향 규율**: 각 빈-입력 가드는 (a) 금지 방향(가드 발화 canary)과 (b) 허용 방향(정당 통과 canary)을 **둘 다**
property로 검증한다(§7). vacuous-admissible도 vacuous-block도 결함이다 — 전자는 안전 위반, 후자는 가용성 위반. **동사별
전용 canary**: net-favorable(§5.1 구조적 magnitude)·same-direction-split(§5.2 극성 §4.5)·omit-units-or-rounding
(§5.2)·double-apply-correction(§5.3 §4.6)·relabel-unexplained(§5.3)·release-on-transformation(§5.2 — **필드·술어
자체가 부재**)·skip-invalidation-on-material-change(§6.3 `material_change_trigger_nonempty`)·auto-re-arm(§6.4
consumed)·treat-expired-as-zero(§6.4 consumed)·label-authority(§5.4)가 각 절에 전용 named canary를 갖는다.

---

## 5. core 술어 — envelope · split-polarity · correction-idempotency · workflow (NT-EV-001/002/010 substrate)

**핵심 난제**: transition-envelope completeness의 no-netting·split transformation의 방향 극성·correction/reversal의
재적용 무해성을 **순수·비전송·fail-closed**로 실현하되 capacity/risk/admissibility/confidence를 형제에 이연한다.

### 5.1 transition-envelope completeness + no-netting (§9; NT-EV-002 substrate, core L1 슬라이스)

```text
transition_envelope_complete(
    envelope: TransitionEnvelope,           # leg별 magnitude
    required_legs: frozenset[CredibleTransitionLegKind],  # caller가 event-class-applicable subset 주입
) -> bool

favorable_netting_absent(envelope: TransitionEnvelope) -> bool
```

- **∅ 구조 가드(C1 — v1.1 핵심 정정)**: 술어 **내부 첫 줄**이 `if not required_legs: return False`다.
  v1.0은 "`required_legs` 빈 집합 ⇒ **별도 처리**에서 `NONTRADE_BLOCK_NEW_RISK`"라고 **소유자 없는 하류에 위임**
  했다 — 그 "별도 처리"는 문서 어디에도 정의되지 않았고, 그 사이 `required_legs ⊆ present_legs`는 **∅ ⊆ 무엇이든
  True**이므로 술어 자체는 **vacuous-True**를 반환했다. 이는 시리즈가 반복 지적해 온 fail-open seam(#6 v1.0 REJECT
  vacuous-True)과 동형이다. v1.1은 이를 **술어 내부 구조 가드**로 끌어들인다: 빈 required set은 "증명할 것이 없다"가
  아니라 "**무엇을 증명해야 하는지 모른다**"이므로 완전성 증명이 성립할 수 없다. **선례**: rcl
  `credible_union_capacity`는 빈 입력을 `ValueError`로 **거부**한다(`rcl/predicates.py:768-773` verbatim: "an empty
  history set must not be read as zero capacity to cover (fail-closed)"). NT은 순수 bool 술어이므로 예외 대신
  `False`를 반환하되 **동일한 fail-closed 명제**를 취한다(bool 반환 술어에서 `ValueError`는 caller에게 예외 처리
  부담을 지우고 disposition 접기를 깨뜨리므로 채택하지 않는다 — 판단 근거 명시).
- **completeness**: (∅ 가드 통과 후) `required_legs ⊆ envelope.present_legs`(누락 ⇒ False).
- **구조적 no-netting**: `favorable_netting_absent(envelope)` — `envelope.pre_event_exposure`·`post_event_credible_
  exposure` 둘 다 not-None·비음수 병존일 때만 True(§0.4d). **음극성 flag 게이트가 아니다(M7)**: `favorable_netted`
  같은 필드는 모델에 없고, netting 부재는 **두 magnitude의 병존**으로만 증명된다.
- **미산출**: capacity union·risk 투영·headroom은 rcl `credible_union_capacity`/are `worst_intermediate_risk` 주입
  verdict 소비(§0.2). NT은 leg magnitude를 `CredibleTransitionLegKind → CanonicalDecimal|None` value로만 로컬 보유.
  **NT leg 집합이 are cell 집합을 덮는지는 Phase-1이 검증하지 않는다**(§3.4(b) M5 정직 공개·§10.4 G6).
- **property**: 무작위 leg subset·pre/post magnitude(None/음수/비음수 조합) 생성 ⇒ (i) **`required_legs` = ∅ ⇒
  False**(vacuous-True 회귀 봉인), (ii) required 미포함⇒False, (iii) pre 또는 post None/음수⇒False, (iv) 완비+병존⇒
  True(§7). **canary**: net-favorable(pre를 post로 상쇄해 하나를 소거하려는 시도)⇒False.

### 5.2 split/reverse-split 방향 극성 + residual (§11; NT-EV-001 substrate, core L1 슬라이스)

```text
split_polarity_coherent(spec: SplitTransformationSpec) -> bool
transformation_residual_conservative(spec: SplitTransformationSpec) -> bool
transformation_units_and_rounding_explicit(spec: SplitTransformationSpec) -> bool   # M1 신설

# SplitTransformationSpec (plain-frozen value, §2.1) — v1.1 필드
#   kind:            SplitTransformationKind                 # declared (대조 대상)
#   pre_quantity:    CanonicalDecimal | None                 # M2 방향 파생 입력
#   post_quantity:   CanonicalDecimal | None                 # M2 방향 파생 입력
#   pre_basis:       CanonicalDecimal | None                 # M2 방향 파생 입력
#   post_basis:      CanonicalDecimal | None                 # M2 방향 파생 입력
#   unit_spec:       ... | None                              # M1 — not None 요구 (§11 line 227)
#   rounding_rule:   ... | None                              # M1 — not None 요구 (§11 line 227)
#   fractional_residual: CanonicalDecimal | None
#   cash_in_lieu:        CanonicalDecimal | None
```

- **polarity(구조 파생, M2)**: `quantity_direction := derive(spec.pre_quantity, spec.post_quantity)`·
  `basis_direction := derive(spec.pre_basis, spec.post_basis)` — `derive`는 scale-normalize 후 identity 대비 3분기
  (`>`⇒`AMPLIFY`·`<`⇒`ATTENUATE`·`==`⇒`IDENTITY`; 어느 입력이든 None ⇒ 파생 불가 ⇒ 술어 False). coherent = **진리표
  A(reciprocal, 파생 방향) ∧ 진리표 B(declared `spec.kind` ↔ 파생 방향 match)**(§4.5) **별도 conjunction**.
  fall-through로 coherent 승격 금지(#16 CRITICAL). caller는 direction을 직접 선언하지 않으므로 **direction 위조
  경로가 구조적으로 제거**된다.
- **units/rounding(M1)**: `transformation_units_and_rounding_explicit` — `spec.unit_spec`·`spec.rounding_rule` 둘 다
  not-None ⇒ True(§11 line 227 verbatim "Every transformation SHALL specify exact units and rounding rules").
  **별도 conjunct**(polarity·residual과 독립).
- **residual**: `spec.fractional_residual`·`spec.cash_in_lieu` 둘 다 not-None·비음수 ⇒ True(§11 line 240). None ⇒
  incomplete⇒False(residual 은닉 금지).
- **no release(구조적 부재, M7)**: NT은 transformation이 capacity를 release한다고 판정하지 않는다(§10 line 221; rcl
  소유). 실현은 `released_on_transformation` 음극성 flag가 **아니라** — 그런 필드는 `SplitTransformationSpec`에도
  `TransitionEnvelope`에도 **없다** — release를 표현·판정할 수단의 부재 그 자체다(unconstructable).
- **property**: pre/post magnitude 조합(None/동일/증가/감소)로 3×3 파생 direction 전수·2 kind·`unit_spec`/
  `rounding_rule` None/present·residual None/비음수 생성 ⇒ (i) reciprocal True cell 3개만 polarity 후보, (ii)
  kind-direction 불일치⇒False, (iii) pre/post 중 None⇒`polarity_coherent` False, (iv) unit/rounding None⇒
  `units_and_rounding_explicit` False, (v) residual None⇒`residual_conservative` False(§7). **canary**: same-direction
  (both AMPLIFY/ATTENUATE)⇒False(부호오류 발화); reverse를 forward로 오표기⇒False; **magnitude는 forward인데 kind를
  `REVERSE_SPLIT`로 선언⇒False**(M2 위조 canary).

### 5.3 correction/reversal idempotency + lineage (§10 line 219·§16 line 313; NT-EV-010 substrate, core L1 슬라이스)

```text
correction_reversal_idempotent(
    incoming: CorrectionReversalRecord,
    prior: CorrectionReversalRecord | None,   # incoming의 idempotency-key를 공유하는 기존 레코드(첫 정정이면 None)
    original_retained: bool | None,           # 원본 append-only 보존 여부(양극성: not-True ⇒ overwrite ⇒ reject)
) -> CorrectionReversalOutcome
```

- **선행 게이트(순서, §4.6)**: (i) `incoming.supersedes_ref` None ⇒ `REJECTED_NO_LINEAGE`(§16 line 311); (ii)
  `original_retained is not True` ⇒ `REJECTED_OVERWRITE`(§10 line 219 — retained는 **양극성**이므로 `is True`만 통과,
  None/False=overwrite⇒reject); (iii) **`prior is None`(첫 정정) ⇒ `APPLIED_ONCE`**(C2 — classify 호출 전 선행 분기;
  없으면 prior=None이 NOT_COMPARABLE로 흘러 정당한 최초 정정이 영구 거부됨).
- **classify(선행 게이트 후, 실측 4-pos+2-kw)**: `classify_record_pair(incoming.id, incoming.digest, prior.id,
  prior.digest, a_idempotency_id=incoming.key, b_idempotency_id=prior.key)`(canonical `record_pair.py:52`) →
  **RecordPairKind 5-member 전수 매핑**: `IDEMPOTENT_DUP`⇒`IDEMPOTENT_REPLAY` · `CRITICAL_CONFLICT`(same **primary**
  id·diff bytes)⇒`REJECTED_CONFLICT` · `DIVERGENT_EMISSION`(same **idempotency** id·diff bytes)⇒`REJECTED_CONFLICT` ·
  `DISTINCT`⇒`REJECTED_UNKNOWN` · `NOT_COMPARABLE`(digest None)⇒`REJECTED_UNKNOWN`.
- **at-most-once**: `APPLIED_ONCE`만 effect+1; `IDEMPOTENT_REPLAY`/`REJECTED_*`는 effect+0.
- **canonical 직접 앵커(§0.4e)**: iap/rcl idempotency 미소비.
- **property**: prior None(⇒`APPLIED_ONCE`)/same-bytes(⇒`IDEMPOTENT_REPLAY`)/same-primary-id·diff-bytes(⇒`REJECTED_
  CONFLICT` via CRITICAL_CONFLICT)/same-key·diff-bytes(⇒`REJECTED_CONFLICT` via DIVERGENT_EMISSION)·supersedes
  present/absent·retained True/False 생성 ⇒ §4.6 진리표 전 cell 재현(§7). **double-application canary**: 동일 event
  N회 ⇒ effect count==1(첫 회 prior=None `APPLIED_ONCE`·이후 `IDEMPOTENT_REPLAY`). **forgery canary 2종**: same-
  primary-id·diff-digest⇒`CRITICAL_CONFLICT`·same-key·diff-digest⇒`DIVERGENT_EMISSION`, 둘 다 `REJECTED_CONFLICT`.

### 5.4 workflow lifecycle + label-grants-nothing + event-identity substrate (§5/§6; core substrate)

- **`NonTradeEventWorkflowState`(11종, §2.2-2)**: OBSERVED→...→RECONCILED + CONFLICTED/QUARANTINED_UNKNOWN/CORRECTION_
  PENDING. **orthogonal**(§6 line 123) — orthostate 축과 별개(§2.2-5). 전이 규칙은 workflow-internal(order/knowledge/
  capacity 상태는 주입 좌표).
- **`nontrade_authority_effect_all_false(effect) -> bool`**: `NonTradeAuthorityEffect` 모든 필드 False 검증(§6 line
  144). 어떤 workflow state에서도 authority effect all-false(#18 §5.3 동형).
- **`NonTradeEventRecord`(digest-bound·IndependentIdArtifact)**: **13 identity 필드**(§5 line 103–115 — 개별 행 전사
  §2.2-8)·source-id 보존(§5 line 117 "A locally generated ID SHALL NOT erase source identity or make conflicting
  events identical"). same **primary** id·diff-bytes ⇒ `classify_record_pair` `CRITICAL_CONFLICT`(`record_pair.py:96`);
  same **idempotency** key·diff-bytes ⇒ `DIVERGENT_EMISSION`(:103) — **두 축 모두 탐지**(§4.6).
- **property**: 모든 workflow state에서 authority effect all-false; same-primary-id/diff-covered-digest event 쌍⇒
  `CRITICAL_CONFLICT`; same-idempotency-key/diff-covered-digest 쌍⇒`DIVERGENT_EMISSION`(§7).

### 5.5 `nontrade_disposition` — 단일 disposition 생산 술어 (C1 신설, v1.1; §1/§18; core substrate)

**존재 이유**: v1.0은 §4.7 ∅-공허 표의 모든 행이 `NONTRADE_BLOCK_NEW_RISK`/`NONTRADE_TRAPPED`/`NONTRADE_QUARANTINED_
UNKNOWN`으로 **접힌다고 서술만 하고 그 접기를 수행하는 술어를 정의하지 않았다** — `NonTradeDisposition`(§2.2-6, 5종)은
어휘로만 존재하고 **어떤 술어도 그것을 반환하지 않았다**(생산자 부재 = 미결 위임). `transition_envelope_complete`의
"∅ ⇒ 별도 처리" 위임도 같은 구멍의 한 사례였다. §5.5가 그 유일한 생산자다.

```text
nontrade_disposition(
    *,
    # --- NT 자체 술어 산출 (§5.1–§5.3) ---
    envelope_complete: bool,                    # transition_envelope_complete(...)
    netting_absent: bool,                       # favorable_netting_absent(...)
    polarity_coherent: bool | None,             # split_polarity_coherent(...)  (transformation 부재 시 None)
    units_and_rounding_explicit: bool | None,   # transformation_units_and_rounding_explicit(...)
    residual_conservative: bool | None,         # transformation_residual_conservative(...)
    correction_outcome: CorrectionReversalOutcome | None,   # correction_reversal_idempotent(...) (정정 부재 시 None)
    lineage_preserved: bool | None,             # instrument_lineage_preserved(...)   §6.1
    effective_window_blocks: bool | None,       # effective_window_blocks_new_risk(...) §6.2
    material_change_triggers_present: bool | None,  # material_change_trigger_nonempty(...) §6.3
    event_is_material: bool | None,             # §6.3 면제 판정용; None = 미지 ⇒ material 취급(면제 없음)
    # --- 형제 주입 좌표 (import 아님, §3.4) ---
    field_confidences: frozenset[FieldConfidenceClass],   # recon classify_field 산출 집합
    admissibility: OrderAdmissibilityResult | None,       # venue
    protective_action_may_proceed: bool | None,           # venue protective_label_no_bypass 산출
    injected_worst_intermediate_risk: CanonicalDecimal | None,   # are
    injected_credible_space_bounded: bool | None,                # are
    injected_union_capacity_known: bool | None,                  # rcl
) -> NonTradeDisposition
```

**결정 규칙(전순서·결정적·양성 conjunction identity)** — 위에서부터 첫 일치가 반환값이다:

| 순위 | 조건 | 반환 | §4.7 행 |
|---|---|---|---|
| 1 | `FieldConfidenceClass.CONFLICTED ∈ field_confidences` **또는** `correction_outcome is REJECTED_CONFLICT` | `NONTRADE_CONFLICTED` | 8·9·14 |
| 2 | `FieldConfidenceClass.UNKNOWN ∈ field_confidences` **또는** `correction_outcome is REJECTED_UNKNOWN` | `NONTRADE_QUARANTINED_UNKNOWN` | 10·14 |
| 3 | `admissibility` ∈ {`INADMISSIBLE`, `UNKNOWN`, `None`} (**무조건** — `protective_action_may_proceed`로 완화되지 않음) | `NONTRADE_TRAPPED` | 13 |
| 4 | 아래 **양성 conjunction**이 하나라도 미성립 | `NONTRADE_BLOCK_NEW_RISK` | 1–7·11·12·15 |
| 5 | 양성 conjunction 전부 성립 **∧** `admissibility is OrderAdmissibilityResult.ADMISSIBLE` | `NONTRADE_ADMISSIBLE` | (양성 side) |

**양성 conjunction(순위 5 도달 조건 — 전부 identity/`is True` 증명)**: `envelope_complete is True` ∧
`netting_absent is True` ∧ (transformation 동반 시 `polarity_coherent is True` ∧ `units_and_rounding_explicit is
True` ∧ `residual_conservative is True`) ∧ (정정 동반 시 `correction_outcome is APPLIED_ONCE` 또는
`is IDEMPOTENT_REPLAY`) ∧ `lineage_preserved is True` ∧ `effective_window_blocks is True` ∧
(**`event_is_material is False`가 아닌 한** — 즉 material 또는 미지이면 — `material_change_triggers_present is True`;
면제는 non-materiality의 positive 증명으로만, §6.3) ∧ `injected_credible_space_bounded is True` ∧
`injected_worst_intermediate_risk is not None` ∧ `injected_union_capacity_known is True` ∧
`field_confidences ⊆ {CORROBORATED}`.

- **fall-through 금지**: `NONTRADE_ADMISSIBLE`은 "아무 가드도 걸리지 않음"의 잔여가 아니라 **위 conjunction 전체의
  양성 증명 + `admissibility is ADMISSIBLE` identity**로만 도달한다(#16 CRITICAL 교훈). 새 입력이 추가되면
  conjunction에 명시적으로 편입되어야 하며, 편입 전까지는 `None` 기본값이 순위 4로 흘러 **보수적으로** 막힌다.
- **protective 예외의 좁은 범위(M6)**: `admissibility is RESTRICTED_PROTECTIVE_ONLY`는 순위 3에 **해당하지 않고**
  순위 4(`NONTRADE_BLOCK_NEW_RISK`)로 간다 — 통상 신규 위험은 막히되, `protective_action_may_proceed is True`인
  경우 소비자(런타임)가 **protective/recovery action만** 진행할 수 있다. NT은 그 판정을 하지 않고 venue
  `protective_label_no_bypass` 산출을 주입 소비할 뿐이다(§3.4). **disposition 자체는 결코 protective action을
  허가하지 않는다**(§4.4 label-grants-nothing).
- **순위 3이 무조건인 이유(불일치 주입 fail-open 차단)**: 순위 3을 "`INADMISSIBLE`/`UNKNOWN`/`None` **∧**
  `protective_action_may_proceed is not True`"로 두면, caller가 **불일치 조합**(`INADMISSIBLE` + `True`)을 주입할 때
  `NONTRADE_TRAPPED`가 `NONTRADE_BLOCK_NEW_RISK`로 **완화**되는 fail-open이 생긴다. venue
  `protective_label_no_bypass`(`venue/predicates.py:599`)는 실측상 `exact_admissibility`가 `ADMISSIBLE` 또는
  `RESTRICTED_PROTECTIVE_ONLY`일 때만 `True`를 반환하므로 그 조합은 venue를 정상 경유하면 **발생할 수 없지만**,
  NT은 형제를 import하지 않고 주입값을 신뢰하지 않으므로 **주입 불일치를 보수적으로 흡수**한다. ⇒ 순위 3은
  admissibility 토큰만으로 무조건 발화한다.
- **truthy-untestable**: 반환 `NonTradeDisposition`은 `_NonTruthyStrEnum`이므로 `if disposition:`는 `TypeError`.
  소비 게이트는 `disposition is NonTradeDisposition.NONTRADE_ADMISSIBLE`만이다(§2.2-6).
- **property**: §4.7 15행 전수 ⇒ 각 행의 "반환" 열과 일치(1:1 회귀); 우선순위 교차 케이스(CONFLICTED ∧ trapped ∧
  incomplete 동시) ⇒ 항상 **더 보수적인 상위 순위** 반환; 전 입력 양성 + `is ADMISSIBLE` ⇒ `NONTRADE_ADMISSIBLE`
  (가용성 side, vacuous-block 아님); 임의의 한 conjunct를 `None`으로 낮추면 즉시 `NONTRADE_BLOCK_NEW_RISK`(§7).

### 5.6 evidence 재구성 substrate (§20; NT-EV-001..012 공통)

- **frozen digest-bound 레코드**: `NonTradeEventRecord`·`CorrectionReversalRecord`·`TransitionEnvelope`·`Split
  TransformationSpec`는 전부 immutable·digest-bound로 event version·source·field-confidence·time-boundary·pre/post
  envelope·lineage를 재구성 가능하게 보존(**§20 line 378–388 = 9 항목** — line 380·381·382·383·384·385·386·387·388
  개별 계수; **v1.0의 "10항목"은 오계수, M8 정정**).
- **replay ≠ authority**: §20 line 392 "Written cases, event catalogs, and successful replay are not completed
  evidence." NT은 레코드만 생산; replay ENGINE·acceptance는 ADR-002-016·VER-002-001(런타임·§0.2).
- **property**: 레코드 round-trip(construct→digest→verify) 결정론(§7).

---

## 6. predicate-only + consumed 술어 — instrument-lineage · effective-time · material-change-trigger (+ consumed 좌표) (NT-EV-003/007 substrate + 004/005/006/008/009/011/012 consumed, 최소 ≥ L2·닫지 않음)

### 6.1 instrument identity lineage (§12; NT-EV-003 substrate, predicate-only — venue 소비)

```text
instrument_lineage_preserved(
    old_route: InstrumentRouteFields | None,   # venue 주입
    new_route: InstrumentRouteFields | None,   # venue 주입
    admissibility: OrderAdmissibilityResult | None,  # venue 주입 — fresh 재결정
    protective_action_may_proceed: bool | None,      # venue protective_label_no_bypass 산출 주입 (M6)
    identity_transition_final: bool | None,
) -> bool
```

- **old/new 병존**(§12 line 248 "Both identities remain active in the transition envelope until ... final mapping"):
  `identity_transition_final is not True`이면 old·new 둘 다 present 요구(하나만 present ⇒ silent-reassign 위험⇒False,
  §12 line 250 "SHALL not be silently reassigned").
- **fresh exact decision — 4토큰+None을 3분기로 접는다(M6, v1.1)**(§10 line 221): (i)
  `admissibility is OrderAdmissibilityResult.ADMISSIBLE` ⇒ 통상 fresh-decision 성립 ⇒ 본 conjunct 통과; (ii)
  `is RESTRICTED_PROTECTIVE_ONLY` ⇒ **통상 conjunct는 미통과(신규 위험 block)**이나 `protective_action_may_proceed
  is True`이면 protective/recovery action 경로가 열려 있음을 disposition에 전달(§5.5 순위 4 — trapped로 강등하지
  않는다); (iii) `is INADMISSIBLE` / `is UNKNOWN` / `None` ⇒ trapped. **v1.0은 (ii)를 (iii)에 합쳐 "나머지 3토큰·
  None ⇒ trapped/block"으로 일괄 접었고**, 이는 ADR §18 line 348 "permit **only newly authorized recovery or
  protective action**"·venue `OrderAdmissibilityResult` docstring(protective-only는 별도 authorized protective
  action이 진행 가능한 상태)과 어긋나 **가용성 위반(vacuous-block)** 이었다. **NT은 admissibility도
  protective 4-조건도 재결정하지 않는다** — venue `material_change_closure`/`protective_label_no_bypass`가 소유하고
  NT은 change-trigger 생산(§6.3)·결과 주입 소비만 한다(§3.5).
- **trapped**(§12 line 252): 미거래·delisted·expired ∧ protective 경로도 없음 ⇒ `NONTRADE_TRAPPED`(zero-risk 아님).
- **최소 `EV-L2/3` — 닫지 않음.** [SAFE-020 lineage·SAFE-030/032 tradability]

### 6.2 effective-time window blocks new risk (§8; NT-EV-007 substrate, predicate-only — time 소비)

```text
effective_window_blocks_new_risk(
    earliest_credible_boundary: ... | None,   # time 주입
    latest_completion_boundary: ... | None,   # time 주입
    time_freshness: FreshnessVerdict | None,  # time 주입
    source_disagreement_bounded: bool | None, # time 주입
) -> bool
```

- **earliest-to-latest block**(§8 line 173 "block new risk before the earliest credible effective boundary and
  remain restricted through the latest credible completion boundary"): 두 boundary·freshness가 positive일 때만
  window 확정; None/미확립 ⇒ 전 구간 block(보수).
- **no collapse**(§8 line 171 "SHALL NOT collapse them into one 'corporate action date'"): announcement/observation/
  record/ex/effective/payable/settlement time을 별개로 보존(§8 line 169).
- **clock-recovery ≠ authority**(§8 line 175): 시계 복구·later source update가 uncertainty interval 중 denied된
  action에 retroactive authority 부여 금지 — time `recovery_generation_revives_nothing` 주입.
- **최소 `EV-L2/3` — 닫지 않음.** [SAFE-035 calendar/time·SAFE-023 reconciliation]

### 6.3 material-change trigger 비공허 (§10 line 221; NT-EV-003 보조, predicate-only — venue 소비) — M3 신설, v1.1

```text
material_change_trigger_nonempty(
    event_is_material: bool | None,          # NT event-class 판정(§2.2-1); None = 미지 ⇒ **material로 취급**
    change_triggers: frozenset[str],         # NT이 venue material_change_closure에 넘길 trigger 노드 집합
) -> bool
```

**존재 이유(∅ 방향 누락 봉합)**: §3.4는 "NT의 corporate action이 venue `material_change_closure`의 **change trigger
입력**"이라고 seam을 고정하지만, v1.0은 **그 입력이 비어 있을 때의 방향을 §4.7에 두지 않았다**. venue 실측
docstring(`venue/predicates.py:361`)은 "An **empty** ``change_triggers`` yields the empty set — no change, nothing
invalidated (the availability side)"이므로, **NT이 material event를 인식하고도 trigger set을 ∅로 넘기면 venue는
아무것도 무효화하지 않고** stale한 Venue Constraint Snapshot·Order Admissibility Decision이 그대로 살아남는다 —
ADR §10 line 221 "Every material event, correction, or reversal SHALL invalidate affected ADR-002-019 ... requires a
fresh exact order decision"의 **정면 fail-open**이다. 이 ∅는 venue 쪽에서는 정당(가용성 side)이므로 **NT 쪽이
비공허를 증명해야 하는 방향**이다.

- **판정(극성 — "unknown materiality is material")**: **면제는 positive `is False`로만 얻는다.**
  `event_is_material is False`(**non-material임이 적극 증명된** 경우)일 때만 본 술어가 disposition conjunction에서
  **면제**되고 ∅ trigger가 정당하다(허용 방향). 그 외 **전부**(`is True` **및 `None`**)는 **material로 취급**되어
  `change_triggers`가 **비공허**일 때만 True이고 ∅이면 **False**(§4.7 행 6 금지 방향). 근거: venue
  `material_change_closure` docstring이 인용하는 VTG **§5.8 "Unknown materiality is material"**(실측
  `venue/predicates.py:379`; 동일 문구 `:137`) — materiality 미지를 non-material로 읽으면 무효화가 통째로
  건너뛰어진다.
  **`is not True`로 면제하지 않는다**: 면제(완화) 분기는 **positive 증명(`is False`)** 을 요구하며, 이는 시리즈
  규율 1(양극성 `is True`·음극성 `is False`)의 "완화는 항상 양성 증명" 원칙과 동형이다. `event_is_material`은
  **안전값이 True인 조건 필드**이므로 §0.1(8)의 음극성 필드(안전값=False) 범주가 아니며 "음극성 0건" 선언과
  모순되지 않는다.
- **NT은 closure를 계산하지 않는다**: 무효화 도달 범위·unproven-edge 확장은 전부 venue 소유(`material_change_
  closure`). NT은 **trigger 집합의 비공허성**만 판정하고 closure 결과는 주입 소비한다(§3.5 권위 중복 배제).
- **seam 양방향 canary(§7 `test_seam_venue`)**: (a) **금지 방향** — `event_is_material is True` + ∅ trigger를
  `material_change_closure`에 넘기면 반환이 `frozenset()`임을 **실제 호출로 확인**하고, 같은 입력에서
  `material_change_trigger_nonempty`가 `False`임을 assert(즉 NT 가드가 venue의 정당한 ∅ 응답을 fail-open으로
  소비하지 않음); (a') **미지 방향(중요)** — `event_is_material is None` + ∅ trigger도 **(a)와 동일하게 `False`**
  임을 assert("unknown materiality is material" 회귀 — 미지를 면제로 읽으면 fail-open); (b) **허용 방향** —
  `event_is_material is False` + ∅ trigger ⇒ 술어 면제 ∧ closure ∅가 **정당**하며 유효 decision이 부당하게
  무효화되지 않음을 assert(venue §18 canary b와 정합).
- **최소 `EV-L2/3` — 닫지 않음.** [SAFE-020 lineage·SAFE-030/032 tradability]

### 6.4 consumed 좌표 술어 (NT-EV-004/005/006/008/009/011/012 — not-Phase-1, 형제 L1 소비·닫지 않음)

각 EV는 형제 L1/런타임 술어를 **주입 소비**하며 NT은 형제 L1을 재저작하지 않는다(권위 중복 배제 §0.2). seam test로만
polarity 검증(§7).

| NT-EV | 요지 | 소비 (형제, 재저작 금지) | NT 좌표 | 최소 레벨 |
|---|---|---|---|---|
| **004** | Option Exercise/Assignment (absence≠no-assignment) | are `OPTION_GREEKS_EXERCISE_ASSIGNMENT`·brokercap·orthostate `BrokerOrderState` | event identity·envelope leg(`EXERCISE_ASSIGNMENT_...`) | `EV-L3+Broker` |
| **005** | Futures Expiry/Settlement (expired≠zero-risk) | are `SETTLEMENT_CASH_CURRENCY`·rcl `TRAPPED_CONSUMED` | event identity·`NONTRADE_TRAPPED` | `EV-L3+Broker` |
| **006** | Broker Open-Order Adjustment | replacement `overlap_first_reservation_complete`·brokercap `ReplaceSemantics`·`OPEN_ORDER_QUERY`·orthostate `BrokerOrderState` | event identity·envelope leg(`BROKER_OPEN_ORDER_...`) | `EV-L3/5` |
| **008** | Unattributed Correction/Transfer | recon `EXTERNAL_UNATTRIBUTED_ACTIVITY`·`FieldConfidenceClass.UNKNOWN`·rcl `QUARANTINED_UNKNOWN`·`CREATE_EXTERNAL_QUARANTINE` | `NONTRADE_QUARANTINED_UNKNOWN`(§16 line 311 no-relabel) | `EV-L3+Broker` |
| **009** | Non-Permissive Partial Local Application | rcl 원자 remap·durable protocol(§10 line 215) | pre/post envelope value | `EV-L3` |
| **011** | Non-Trade Restart/Replay | sbr `RecoveryObligation`·`recovery_inventory_complete`·`restore_worst_credible_union`·orthostate `reconstruct_conservative` | event가 recovery obligation 입력 | `EV-L3` |
| **012** | Event Completion Cannot Re-arm | liveauth `no_automatic_rearm`·`authorization_revived_by_nothing`·authority `rearm_gate` | workflow completion≠authority(§17 line 334) | `EV-L3` |

---

## 7. property-test 하네스 타깃

§1 분류에 정렬한다. **닫는 NT-EV = 0건** — 어떤 test-target도 NT-EV closure·acceptance를 주장하지 않는다(규율 태그
부착). 각 술어에 **both-ways canary**(§4·§5·§6)와 **fixture clean-vs-illegal 정합**(#8 교훈)을 건다. **hypothesis
전략은 forgery/∅/double-application 케이스를 명시 포함**한다(아래).

- **core(L1 슬라이스, NT-EV-001/002/010 substrate)**: `transition_envelope_complete`+`favorable_netting_absent`(§5.1);
  `split_polarity_coherent`+`transformation_units_and_rounding_explicit`+`transformation_residual_conservative`(§5.2);
  `correction_reversal_idempotent`(§5.3); `NonTradeEventWorkflowState`+`nontrade_authority_effect_all_false`+frozen
  digest-bound 레코드 재구성·`classify_record_pair` 5-member 전수(§5.4); **`nontrade_disposition`(§5.5 — C1 신설,
  §4.7 15행 1:1 회귀)**.
  **hypothesis property**: `TransitionEnvelope`(per-leg magnitude 포함)/`SplitTransformationSpec`(pre/post
  quantity·basis·unit_spec·rounding_rule 포함)/`CorrectionReversalRecord`/`NonTradeEventRecord`/leg-set를 무작위
  생성해 (i) **envelope completeness**(applicable 10-leg 부분집합 관계·미포함⇒False; **`required_legs` = ∅ ⇒ False**
  — vacuous-True 봉인), (ii) **구조적 no-netting**(`pre_event_exposure`·`post_event_credible_exposure` magnitude를
  None/음수/비음수 조합 생성; 둘 다 not-None·비음수일 때만 `favorable_netting_absent`; 하나라도 None/음수⇒False),
  (iii) **split 방향 극성**(pre/post magnitude에서 **파생**한 방향으로 §4.5 진리표 A 3×3 = 9 cell + 진리표 B
  kind-match 전수; reciprocal 3 cell·kind 일치만 coherent; both-amplify/both-attenuate/kind-mismatch⇒False;
  **magnitude와 declared kind 불일치⇒False** — M2 위조 canary), (iv) **unit/rounding**(`unit_spec`·`rounding_rule`
  중 하나라도 None⇒False), (v) **residual**(fractional/cash-in-lieu None⇒False), (vi) **correction idempotency**
  (§4.6 진리표 전 cell — prior None/same-bytes/diff-bytes·supersedes present/absent·retained True/False), (vii)
  **label-grants-nothing**(모든 workflow state에서 authority effect all-false), (viii) **disposition 접기**
  (`nontrade_disposition` 5-member 우선순위 전순서·identity 게이트)를 검사.
  - **forgery 케이스(명시, 2종 분리 — C2)**: (a) **same primary id·diff canonical digest** `NonTradeEventRecord`·
    `CorrectionReversalRecord` 쌍 ⇒ `classify_record_pair` **`CRITICAL_CONFLICT`**(`record_pair.py:96`) 회귀;
    (b) **same idempotency key·diff canonical digest**(primary id는 상이) 쌍 ⇒ **`DIVERGENT_EMISSION`**(:103) 회귀.
    **둘 다 `REJECTED_CONFLICT`로 접히고**(§4.6) `nontrade_disposition`은 `NONTRADE_CONFLICTED`를 반환하며, 양쪽
    레코드가 보존되고 last-write-wins가 발생하지 않음을 assert.
  - **double-application 케이스(명시, 시리즈 최초 idempotency-중심 슬라이스)**: 동일 correction event를 N≥2회 적용 ⇒
    첫 회 `APPLIED_ONCE`·2회+ `IDEMPOTENT_REPLAY` ⇒ 누적 economic effect count == 1(재적용 무해성 회귀). same-key
    diff-digest ⇒ `REJECTED_CONFLICT`(effect+0).
  - **∅ 케이스(명시, §4.7 표 15행과 1:1 — 번호 대응)**: (1) 빈 `required_legs`⇒`transition_envelope_complete` False
    ∧ disposition `NONTRADE_BLOCK_NEW_RISK`; (2) pre/post exposure None/음수⇒`favorable_netting_absent` False⇒block;
    (3) pre/post quantity·basis 중 None⇒`split_polarity_coherent` False⇒block; (4) `unit_spec`/`rounding_rule`
    None⇒`transformation_units_and_rounding_explicit` False⇒block; (5) residual None⇒`transformation_residual_
    conservative` False⇒block; (6) `event_is_material` **`True` 또는 `None`** + ∅ change-trigger⇒`material_change_
    trigger_nonempty` False⇒block(미지 케이스 별도 assert) **∧** `is False` + ∅⇒면제(허용 방향);
    (7) supersedes 부재⇒`REJECTED_NO_LINEAGE`⇒block; (8) `CRITICAL_
    CONFLICT`⇒`REJECTED_CONFLICT`⇒`NONTRADE_CONFLICTED`; (9) `DIVERGENT_EMISSION`⇒`REJECTED_CONFLICT`⇒
    `NONTRADE_CONFLICTED`; (10) `DISTINCT`/`NOT_COMPARABLE`⇒`REJECTED_UNKNOWN`⇒`NONTRADE_QUARANTINED_UNKNOWN`;
    (11) None risk/capacity·`credible_space_bounded` None/False⇒block; (12) `RESTRICTED_PROTECTIVE_ONLY`⇒block
    **∧** `protective_action_may_proceed is True`면 protective 경로 유지(trapped 아님); (13) `INADMISSIBLE`/
    `UNKNOWN`/`None` admissibility⇒`NONTRADE_TRAPPED`; (14) field `UNKNOWN`⇒`NONTRADE_QUARANTINED_UNKNOWN`·
    `CONFLICTED`⇒`NONTRADE_CONFLICTED`; (15) 빈 workflow state/어떤 label⇒authority all-false ∧ disposition 불변.
    **각 항목은 금지 방향 + 허용 방향 둘 다**(§4.7 양방향 규율).
  - **truthy-sentinel property(양축·극성 분기)**: `NonTradeDisposition` 게이트 `is NONTRADE_ADMISSIBLE`만·`Correction
    ReversalOutcome` 게이트 `is APPLIED_ONCE`/`is IDEMPOTENT_REPLAY`만·venue `OrderAdmissibilityResult` 게이트 `is
    ADMISSIBLE`만 통과(나머지 토큰·None 관통 시 실패; `bool(token)` ⇒ `TypeError` 확인). **양극성 필드
    (`original_retained`·`identity_transition_final`·주입 `source_disagreement_bounded`·`credible_space_bounded`·
    `protective_action_may_proceed`)는 `is True`만·None 관통 시 실패.** **음극성 필드는 Phase-1 NT 모델에 0건이며
    (M7), 그 사실 자체를 회귀로 고정한다** — `SplitTransformationSpec`·`TransitionEnvelope`·`CorrectionReversal
    Record`의 필드명 집합에 `favorable_netted`·`destructive_overwrite`·`released_on_transformation`이 **부재**함을
    assert(phantom 필드 재유입 방지). 향후 음극성 필드를 도입한다면 `is False`만 통과해야 하며 `is not True`는
    금지다(시리즈 규율 1 유지).
  - **좌표 비붕괴 property(§2.2-5)**: `NonTradeEventWorkflowState.QUARANTINED_UNKNOWN` ∩ rcl `CapacityState.
    QUARANTINED_UNKNOWN`·`CorrectionReversalOutcome.IDEMPOTENT_REPLAY` ∩ iap `ConsumptionOutcome.IDEMPOTENT_REPLAY`
    ∩ rcl `ApplyReason.IDEMPOTENT_REPLAY`·`CredibleTransitionLegKind` ∩ replacement `CredibleIntermediateOutcomeKind`
    가 별개 타입임(토큰 겹침 무관) 회귀.
- **predicate-only(NT-EV-003/007 substrate, EV 미주장)**: `instrument_lineage_preserved`(§6.1, old/new 병존·
  **admissibility 3분기 접기**(ADMISSIBLE / RESTRICTED_PROTECTIVE_ONLY+protective 경로 / INADMISSIBLE·UNKNOWN·None⇒
  trapped)); `effective_window_blocks_new_risk`(§6.2, earliest-latest·no-collapse·clock-recovery≠authority);
  **`material_change_trigger_nonempty`(§6.3, `is not False`(material·미지)+∅⇒False / `is False`+∅⇒면제)**.
- **consumed 좌표(NT-EV-004/005/006/008/009/011/012, EV 미주장·seam test로만)**: 형제 술어 주입 소비 polarity만 검증
  (§6.4) — 형제 L1을 재검증하지 않는다(권위 중복 배제).
- **seam cross-check(test-only, MANDATED §3.4)**: `test_seam_rcl`(NT envelope leg ↔ `credible_union_capacity`
  empty⇒`ValueError`(`rcl/predicates.py:768`)·None⇒UNKNOWN·`RECOGNIZED_EXTERNAL_CHANGE`·`WEAK_CAUSES`
  conservatism-only; **NT `transition_envelope_complete`의 ∅⇒False가 rcl의 ∅⇒ValueError와 동일 명제(fail-closed)
  임을 대조**)·`test_seam_are`(NT envelope risk ↔ `worst_intermediate_risk` None⇒None·`credible_space_bounded`
  None/False⇒trapped·`EXTERNAL_TRAPPED_NONTRADE_CONCURRENT` 좌표·`envelope_bound_not_enlarged`
  `limit_source_is_injected_envelope is not True`⇒False; **명제-동일 대상이 ADR §9 line 196(한도 확대 금지)임을 주석
  고정** — M4)·`test_seam_venue`(**(a)** NT change-trigger ↔ `material_change_closure`: material+∅ trigger⇒반환
  `frozenset()` ∧ `material_change_trigger_nonempty` False(금지 방향), non-material+∅⇒정당·유효 decision 미무효화
  (허용 방향) — **M3 양방향**; **(b)** unproven-edge expanded 보수; **(c)** `OrderAdmissibilityResult` 4토큰+None
  **전수 3분기** 접기(`is ADMISSIBLE`⇒ordinary / `is RESTRICTED_PROTECTIVE_ONLY`⇒block+`protective_label_no_bypass`
  (`venue/predicates.py:599`) 산출 주입 경로 / `INADMISSIBLE`·`UNKNOWN`·`None`⇒trapped) — **M6**; **(d)**
  `bool(token)` **TypeError 봉인 확인**)·`test_seam_recon`(NT field-gate ↔ `classify_field` 0-path⇒UNKNOWN·common-
  mode≠corroboration·`SafetyRelevantField.{INSTRUMENT_IDENTITY,EXTERNAL_UNATTRIBUTED_ACTIVITY}`)·`test_seam_orthostate`
  (NT workflow 축 ↔ orthostate `no_coupling_violation`·`reconstruct_conservative` RECONCILED⇒CONFLICTED downgrade·
  좌표 비붕괴)·`test_seam_canonical`(correction ↔ `classify_record_pair` **5-member 전수**: same-bytes⇒
  `IDEMPOTENT_DUP`·same-primary-id·diff-bytes⇒`CRITICAL_CONFLICT`·same-idempotency-key·diff-bytes⇒
  `DIVERGENT_EMISSION`·id/key 미공유⇒`DISTINCT`·digest None⇒`NOT_COMPARABLE`). 테스트 import는 package closure
  불계상(§7.1).
- **∅-공허 회귀(양방향, §4.7 표 15행 ↔ 본 §7 "∅ 케이스" 15항목 1:1)**: 각 빈-입력의 금지 방향 + 완비 입력의 정당
  통과 canary **둘 다**.

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#5..#18 §7.1 상속)

**allowlist 형식(denylist 열거 금지 — #16 M9 교훈)**: `import` 후 `{m for m in sys.modules if m.startswith("tos.")}`
의 top-level 패키지 ⊆ **{`tos.canonical`, `tos.ordering`, 자기 자신}** assert(그 외 모든 tos 형제 — rcl/are/venue/
recon/orthostate/brokercap/replacement/authority/liveauth/sbr/time/protective/afg/spg/ioc/iap/capsule/evidence/dsl
및 미래 형제[hag 포함] — 등장 시 실패) + `shared.config`·`os.environ` 흔적·`numpy`/`pandas`/`yaml` 부재 assert.
**allowlist가 미래-견고**(신규 형제 추가에 자동 방어). required check(`tos-firewall`, `tools/tos_firewall_check.py`
layer-① AST + `.importlinter` layer-② 전이)와 함께 green이어야 §0.3 선언이 능동 성립.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: nontrade Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `PYTHONPATH=tos/src .venv/bin/python -m pytest
tos/tests/nontrade/ -v`(pyenv=mypy 전용 — project memory). (3) 격리: hermetic(`.env` 비주입·clock 미접근·네트워크
없음). (4) 결정론: hypothesis 시드 고정·`CanonicalDecimal` scale-normalize·NaN/infinity 구성-거부·multiplicative-
identity 대조. (5) 산출물: property test 결과(EV closure 아님 — 규율 태그). (6) 게이트: `tos-firewall` required
green. (7) 비-acceptance: 어떤 NT-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 nontrade decision 구조에 numeric bound 부재**: 전부 enum(`NonTradeEventClass`/`NonTradeEventWorkflowState`/
`CredibleTransitionLegKind`/`SplitTransformationKind`/`TransformationDirection`/`CorrectionReversalOutcome`/
`NonTradeDisposition`)·boolean·집합 논리·주입 `CanonicalDecimal`(leg magnitude·residual·**pre/post quantity·basis** —
비교·`is_finite`·scale-normalize·multiplicative-identity 대조뿐, 어떤 배수·threshold도 하드코딩 없음). **split 극성은
`TransformationDirection` enum reciprocal 대수로 판정하고 그 enum 값은 pre/post magnitude의 identity-대비 3분기
비교로 파생**하므로(M2) 특정 배수(2-for-1의 2 등)를 요구하지 않는다(§4.5·§0.4d).

**§8.1 VP-002 실측 — 3 NT-전용 키 실재·null(신규 키 0건)**: ADR §8/§15가 요하는 timing bound는 VERIFICATION-PROFILE-
002.yaml에 **이미 3키 실재·`value_ms: null`**(confirmed candidate 신규 키 0건 — #10/#13/#16/#18형):

| VP-002 키 (line) | semantics | owner (line) | failure_response | measurement_source | rationale (요지) |
|---|---|---|---|---|---|
| `B_non_trade_event_detect` (646) | `source_and_broker_specific` | **`TBD` (649)** | `CONTAIN` | `reference_source_and_broker_capability_profile` | externally effective non-trade change → authoritative detection 최대 interval; 그 구간 내내 entry limit 안전 유지(§8) |
| `B_non_trade_transition_apply` (653) | `hard_maximum` | **`TBD` (656)** | `REMAIN_HALTED` | `non_trade_transition_and_ledger_log` | local instrument/projection/RCL/protection/authority가 complete non-permissive transition·containment 도달 최대 interval(§10) |
| `B_non_trade_reconcile` (660) | `source_and_broker_specific` | **`TBD` (663)** | `QUARANTINE_UNKNOWN` | `reconciliation_and_broker_capability_profile` | non-trade event 후 old·new effect가 conservatively capacity-covered 유지되는 최대 unreconciled interval(§16) |

**3키 전부 `value_ms: null`이며 APPROVE 주석은 키마다 다르다(m4 에라타 정정)** — line 647 `# APPROVE per source and
broker capability profile` · line 654 `# APPROVE after conservative transition protocol is selected` · line 661
`# APPROVE per event/instrument/broker scope`. v1.0은 세 키 모두 첫 번째 주석 문구를 갖는 것처럼 서술했으나
실측(VP-002 line 647/654/661)은 위와 같다. **`owner`도 3키 전부 `TBD`**(line 649/656/663) — 즉 **값도 소유자도
미승인**이며, 두 축 모두 Bounds-Approver/Phase-0 게이트다(§9.2-1). per-source/per-broker 수치는 Broker Capability
Profile·reference-source INSTANCE(§7 line 163). **NT Phase-1 코드는 이 3 bound를 주입 파라미터로만 받고 값을
하드코딩·기본값 부여하지 않는다**(값 부재 ⇒ fail-closed — `external_detection_ok` 형 brokercap
`B_external_detect`/`B_external_contain` None⇒False 동형).

**§8.2 confirmed candidate 신규 키 0건**: NT decision 술어는 completeness(set)·polarity(enum reciprocal)·idempotency
(`classify_record_pair`)·lineage(boolean)로 L1-decidable하며 **numeric bound를 결정 내부에 두지 않는다** — 3 VP 키는
전부 런타임 latency 측정(detect/apply/reconcile interval)이라 EV-L2/L3 통합 단계 소비이고 Phase-1 순수 커널 밖이다.
**어떤 숫자도 하드코딩하지 않는다**(CLAUDE.md·§0.2).

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. **`tos/src/tos/nontrade/` 패키지 구현**(EV-L1): `_base.py`(canonical re-export + `NonTradeAuthorityEffect`
   all-false)·`vocabulary.py`(**7 enum** — `NonTradeEventClass`·`NonTradeEventWorkflowState`·`CredibleTransitionLeg
   Kind`·`SplitTransformationKind`·`TransformationDirection`·`CorrectionReversalOutcome`·`NonTradeDisposition`,
   개별 계수)·`records.py`(`NonTradeEventRecord`·`CorrectionReversalRecord`·`TransitionEnvelope`·`SplitTransformation
   Spec`)·`predicates.py`(**11 술어** — v1.1 재정정)·`state.py`(workflow lifecycle).

   **술어 11종 개별 계수(M8 — v1.0 "6 core/predicate-only 술어"는 오계수였고, v1.1 신설분 3종을 반영해 재정정)**:
   **core 8** = (1) `transition_envelope_complete`(§5.1) · (2) `favorable_netting_absent`(§5.1) · (3)
   `split_polarity_coherent`(§5.2) · (4) **`transformation_units_and_rounding_explicit`(§5.2 — M1 신설)** · (5)
   `transformation_residual_conservative`(§5.2) · (6) `correction_reversal_idempotent`(§5.3) · (7)
   `nontrade_authority_effect_all_false`(§5.4) · (8) **`nontrade_disposition`(§5.5 — C1 신설)**; **predicate-only 3**
   = (9) `instrument_lineage_preserved`(§6.1) · (10) `effective_window_blocks_new_risk`(§6.2) · (11)
   **`material_change_trigger_nonempty`(§6.3 — M3 신설)**. **8 + 3 = 11**(§2.0 다이어그램·§7 목록과 일치).
2. **property test 하네스**(§7): `tos/tests/nontrade/` — core 8 + predicate-only 3 + ∅ 양방향 15행 + forgery 2종 +
   double-application + truthy-sentinel 극성(음극성 필드 **부재 assert** 포함) + 좌표 비붕괴 + seam cross-check 6종.
3. **import-closure 테스트**(§7.1) + `tos-firewall` required green.
4. **구현 단계 예고 반영(#18 defect-class #7 상속)**: (a) **enum member→value 바인딩 단언**(`NonTradeEventWorkflow
   State.OBSERVED.value == "OBSERVED"` 등 — value drift lock); (b) **`_ID_FIELD` drift lock**(digest covered-field
   set 고정, self-exclusion 검증); (c) **forgery 전략 명시**(§7 same-id/diff-digest hypothesis 전략); (d) **§7.1
   allowlist**(자기 자신+canonical+ordering ⊆ 형식 — rcl은 불필요, NT은 rcl import 안 함).
5. **적대적 코드 리뷰 → 게이트**(품질 파이프라인, 운영자 표준지시 2026-07-25).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §25 Open Questions(line 489–494) ↔ Phase-0:

1. **numeric bound**(§8·ADR §25 q5 line 493): `B_non_trade_event_detect`/`B_non_trade_transition_apply`/`B_non_trade_
   reconcile` 값 + reconciliation/settlement/evidence-freshness bound — Bounds-Approver.
2. **source-authority rules**(ADR §25 q1 line 489): 각 first-live instrument class의 approved event source·source-
   authority rule(§7 line 161 "Majority vote SHALL NOT resolve conflicting semantics without source-authority
   rules") — reference-source INSTANCE.
3. **broker open-order adjustment semantics**(ADR §25 q2 line 490): 증명 가능한 per-broker adjustment 의미 —
   Broker Capability Profile INSTANCE(brokercap).
4. **initial restricted-live scope**(ADR §25 q3 line 491): 어떤 voluntary action·derivative lifecycle·delivery
   obligation이 초기 범위인지 — 인간 scope 승인.
5. **transition protocol**(ADR §25 q4 line 492): projection/instrument/capacity/authority store 간 conservative
   상태 보존 protocol 선택 — 아키텍처 승인(rcl 원자 remap·durable protocol §10 line 215).
6. **residual risk 인간 수용**(ADR §25 q6 line 494): 명시적 인간 수용이 필요한 corporate-action·non-trade residual
   risk — 인간 acceptance.

ADR §25 line 496 "Open questions may only narrow instrument or event scope or block acceptance. They SHALL NOT
permit optimistic transformation." — 본 계약도 동일(§0.2 fail-closed).

---

## 10. 개정 로그 + 비준 체크리스트 + 판단 지점

### 10.1 개정 로그

- **v1.0 (2026-07-26)**: 최초 저작. ADR-002-010(515줄) 전독 → EVIDENCE-REGISTER-002.csv CSV-aware 실측(NT-EV 12행·
  L1 슬라이스 3행 001·002·010) → VP-002 3 NT 키 실측(646/653/660 null) → 11 형제 패키지 public surface 코드 실측 →
  §0–§10 저작. 핵심 판정: (a) 패키지 `tos.nontrade`(nt 차점), (b) produced-bool·sibling edge 0, (c) `CapacityVector`/
  `ProjectedCell` REUSE 기각(edge-0), (d) transition-envelope 이중 계상 정합(구조적 no-netting·are/rcl 이연), (e)
  event-idempotency 명제 = NT 고유(iap/rcl과 canonical 원시의 세 독립 하류·phantom edge 차단), (f) split 방향 극성
  §4.5 진리표(enum reciprocal·수치 미사용), (g) idempotency·중복 적용 §4.6 진리표(시리즈 최초 idempotency-중심 슬라이스).
- **v1.1 (2026-07-26)**: **독립 비평 리뷰(REVISE — CRITICAL 2·MAJOR 8·MINOR 4) 전건 반영.** 경위: v1.1 개정 중
  **저작자 세션이 한도로 중단**되어(착지분 = C2 부분 — `DIVERGENT_EMISSION` 매핑 9개소·`prior is None` classify
  선행 게이트) **신규 에이전트가 잔여 전건을 완결**했다. 항목별:
  - **C1(∅ 위임 제거 + disposition 생산자 신설)**: `transition_envelope_complete`의 "빈 `required_legs` ⇒ 별도
    처리" 무주 위임을 제거하고 **술어 내부 구조 가드**(`if not required_legs: return False`)로 승격(§0.1(3)·§5.1;
    rcl `credible_union_capacity` empty⇒`ValueError` 선례 `rcl/predicates.py:768` 인용). `NonTradeDisposition`의
    **유일한 생산자 `nontrade_disposition(...)`를 §5.5에 신설**(시그니처·전순서 5-우선순위·양성 conjunction 명시)
    하고 **§4.7 표 전 행을 그 반환값으로 재매핑**. §9.1 술어 수 정정.
  - **C2 잔여 전파(반전 매핑 정정)**: §0.1(5)·§0.4f·§4.1(2)·§4.3(2)·§4.6·§4.7·§5.4·§7의 forgery 서술을
    **2행 분리**(same **primary** id·diff digest ⇒ `CRITICAL_CONFLICT` / same **idempotency** key·diff digest ⇒
    `DIVERGENT_EMISSION`, 둘 다 `REJECTED_CONFLICT`)로 통일하고, `RecordPairKind` **5-member 전수 매핑**을 §2.2-5·
    §4.6·§4.7·§7 seam에서 정합화, `classify_record_pair` 표기를 **실측 4-positional+2-keyword 시그니처**로 전
    등장점 통일(실측 `canonical/record_pair.py:31/41/43/45/47/49/52/68/87/94/96/101/103/105`).
  - **M1**: `SplitTransformationSpec`에 `unit_spec`·`rounding_rule`(not-None 요구) 추가 +
    `transformation_units_and_rounding_explicit` 별도 conjunct 신설(§5.2) + **ADR §11 line 231–236 6구분 개별 전사·
    소유 귀속표 §2.2-7 신설**(근거 ADR §16 line 309·§5 line 109; 무소유 구분 0건).
  - **M2**: `SplitTransformationSpec`에 `pre_quantity`/`post_quantity`·`pre_basis`/`post_basis` 추가,
    `TransformationDirection`을 **multiplicative identity 대비 비교로 파생**(post>pre⇒`AMPLIFY`; 배수 하드코딩 0)한
    뒤 declared kind와 대조 — §4.5 두 진리표는 **불변**, 입력만 caller 선언 flag에서 구조 파생으로 승격.
    None ⇒ fail-closed를 §4.7 행 3에 흡수.
  - **M3**: §4.7에 **빈 change-trigger set 행(행 6)** 추가(material 인식+∅⇒`NONTRADE_BLOCK_NEW_RISK` /
    non-material+∅⇒정당) + **`material_change_trigger_nonempty` §6.3 신설**(기존 §6.3 consumed → **§6.4** 개번) +
    §7 `test_seam_venue` **양방향 canary**(venue `predicates.py:361` docstring 실측 "empty ⇒ empty set" 인용).
    **materiality 극성 확정**: `event_is_material`의 **미지(None)는 material로 취급**하고 면제는 `is False`의
    positive 증명으로만 — venue §5.8 "Unknown materiality is material"(`venue/predicates.py:379`) 실측 준거.
    (초안에서 `is not True`로 면제하려던 fail-open을 자체 검증 패스에서 발견·수정.)
  - **M4**: are `envelope_bound_not_enlarged`의 명제-동일 대상을 ADR §10 line 221 후단(**release** — rcl 소유)에서
    **ADR §9 line 196(한도 확대 금지 축)**으로 재지정(§3.4 표·§7 seam 주석).
  - **M5**: §3.4(b)에 **"NT leg-set ↔ are cell-set 커버리지 결속 = Phase-1 미실현·런타임(EV-L2/3) 잔여"** 정직
    공개 추가. **택1 명시**: `envelope_legs_covered` 주입 대조 술어 **미채택**(edge-1 부활 또는 약한 id-proxy가
    되어 fail-open 서사가 됨) — **§10.4 G6으로 승격**해 독립 리뷰어 공격 지점으로 노출.
  - **M6**: `RESTRICTED_PROTECTIVE_ONLY` 접기를 **3분기로 재작성**(§3.4 표·§4.7 행 12/13·§6.1·§7): ADMISSIBLE⇒통상
    fresh / RESTRICTED_PROTECTIVE_ONLY⇒통상 신규위험 block **이되 venue `protective_label_no_bypass`
    (`venue/predicates.py:599`) 경유 protective action 허용**(주입 좌표 `protective_action_may_proceed`) /
    INADMISSIBLE·UNKNOWN·None⇒trapped. v1.0의 일괄 trapped 접기는 ADR §18 line 348과 어긋난 가용성 위반이었다.
  - **M7**: phantom 음극성 필드 `destructive_overwrite`·`released_on_transformation`을 **삭제**(§0.1(8)·§7) —
    history 보존은 §5.3의 **양극성 `original_retained`**로 이미 실현되고 release는 **필드·술어 부재**(§4.2-4)로
    실현되므로 실필드 신설은 불요. `favorable_netted` flag 게이트 문구(§4.1(2)·§5.1)도 제거하고 **§0.4d 구조
    magnitude 병존 파생** 서술로 통일. **Phase-1 NT 음극성 필드 = 0건**을 정직 공개하고 §7에 **필드 부재 assert**로
    고정.
  - **M8(카운트)**: §5.6 "§20 10항목"→**9**(line 380–388 개별 계수) 정정; §1 표에 §11 **6구분**·§17 **8경계**·§19
    **8의무** 개별 계수 병기; **§5 13 identity 필드 개별 행 전사 §2.2-8 신설**; §9.1 술어 수 **6→11** 재정정
    (개별 계수 포함); §4.7 금지동사 **19개** 개별 번호 계수(v1.0 17 + M1/M3 신설 2).
  - **MINOR/에라타(m1–m4)**: m1 — §1 표에 **§2(Context)·§3(Decision Drivers 8 driver·무소유 0)** 행 추가로
    "전 조항 §1–§26 매핑" 주장을 실제로 실현. m2 — 라인 에라타(§8 line 176→175 ×4·§9 line 188→187·§2 line 39→38·
    hag ADR-002-014→**ADR-002-015**·"21개"→"22개 tracked")는 **직전 세션에서 이미 착지**됨을 재실측으로 확인
    (본 세션 재적용 0 — 이중 적용 방지). m4 — §8.1에 **`owner: TBD`(VP-002 line 649/656/663)** 병기 + 3키의
    APPROVE 주석이 서로 다름(line 647/654/661)을 정정.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] **register 실측 재확인**: NT-EV 12행·L1 슬라이스 3행(001 `EV-L1/3+Broker`·002 `EV-L1/3`·010 `EV-L1/3`)·닫는
      NT-EV 0건(CSV-aware 파싱 — 제목 쉼표). 사전 카운트 일치·정정 없음.
- [ ] **앵커 규약**: NT-EV/NT-AC/§-clause/SAFE만 앵커·새 INV/AC/EV 시리즈 창작 0(§0.4g grep 실측).
- [ ] **sibling edge 0·canonical/ordering만 import**(§0.3 allowlist·§7.1)·PROMOTE 0·`CapacityVector`/`ProjectedCell`
      REUSE 0(§0.4c).
- [ ] **소유권 분할표(§3.5)**: 11 형제 소유 vs NT 소유 코드 실측 signature+라인 정확·권위 중복 0(rcl capacity·are
      risk·venue admissibility·recon confidence·replacement replace·PTOL ADR-002-030 이연).
- [ ] **명제 동일성(§3.4 시리즈 규율 3)**: 소비 형제 술어 docstring 명제 ↔ ADR 조항 명제 대조·iap idempotency 명제
      상이로 미소비 확인(§0.4e — phantom edge 0).
- [ ] **방향 극성 진리표(§4.5)**: split/reverse-split reciprocal·kind-match 양방향 검산·부호오류 both-direction cell
      reject·수치 하드코딩 0·**방향이 caller 선언이 아니라 pre/post magnitude 구조 파생임(M2)**.
- [ ] **idempotency 진리표·중복 적용 canary(§4.6)**: lineage×classification×history 6-outcome·`RecordPairKind`
      **5-member 전수 매핑**·double-application effect count==1·**forgery 2종 분리**(same-primary-id⇒
      `CRITICAL_CONFLICT` / same-idempotency-key⇒`DIVERGENT_EMISSION`, 둘 다 `REJECTED_CONFLICT`).
- [ ] **disposition 생산자 실재(§5.5, C1)**: `nontrade_disposition`이 `NonTradeDisposition`의 **유일한 생산자**·
      전순서 5-우선순위 결정적·`NONTRADE_ADMISSIBLE`이 양성 conjunction identity로만 도달·§4.7 15행 1:1.
- [ ] **∅ 구조 가드(§5.1, C1)**: 빈 `required_legs`가 **술어 내부에서** `False`(하류 "별도 처리" 위임 0건)·rcl
      `credible_union_capacity` empty⇒`ValueError` 선례와 동일 명제.
- [ ] **truthy-sentinel 극성 분기(§4·§7)**: 양극성 `is True`·result identity(`is NONTRADE_ADMISSIBLE`)·fall-through
      승격 0·**음극성 필드 0건 정직 공개 + phantom 필드(`favorable_netted`·`destructive_overwrite`·
      `released_on_transformation`) 부재 assert**(M7).
- [ ] **∅-공허 양방향(§4.7)**: 금지+허용 canary 둘 다·**15행 ↔ §7 15항목 1:1**·금지동사 **19개**(개별 번호 계수).
- [ ] **카운트 대조 전수화(§2.2 defect-class #4)**: 5 event class·11 workflow·10 leg·6 outcome·**13 identity 필드
      개별 행(§2.2-8)**·**§11 6구분 개별 행(§2.2-7)**·**§20 9 보존항목**·8 §18 단계·8 §14 leg·7 §13 assessment·
      8 §17 경계·8 §19 의무·8 §3 driver·**11 술어(§9.1)** 원문 항목 수 병기·개별 계수.
- [ ] **M5 정직 공개 확인(§3.4(b)·§10.4 G6)**: "NT leg-set ↔ are cell-set 커버리지 결속"이 **Phase-1 미실현**임이
      명시되어 있고 그 미실현을 감춘 주장(예: "NT이 are envelope 완전성을 보증")이 문서 어디에도 없는지.
- [ ] **broker-agnostic·수치 하드코딩 0**(§0.3·§8): 어떤 broker 명명 0·3 VP 키 `value_ms: null` ∧ `owner: TBD`
      (line 647/654/661·649/656/663) 주입.
- [ ] **비-acceptance**: 닫는 NT-EV 0·EV-L1-complete 주장 0·restricted-live/production 미승인(§0.2).

### 10.3 운영자 판단 지점 (요약)

1. **`ProjectedCell`/`CapacityVector` REUSE(edge-1) vs plain-type leg-record producer(edge-0, 채택)**(§0.4c): Phase-1은
   leg-completeness·no-netting·polarity·idempotency가 L1 핵심이고 cell/vector 산술은 are/rcl 소유이므로 **edge-0**
   채택. 미래 런타임에서 NT이 cell/vector를 직접 조립해야 하면 edge-1 승격 가능. **권장: edge-0**(protective #11·
   replacement #18 동형).
2. **패키지 명명 `tos.nontrade` vs `tos.nt`**(§0.4a): semantic 토큰 우선(#18 `pr`→`replacement` 선례)으로 `nontrade`
   채택. register 두문자 정합·terse 선호 시 `tos.nt` 치환 가능(load-bearing 아님). **권장: `nontrade`**.
3. **iap idempotency 소비 여부**(§0.4e): 명제 상이(authorization-token ≠ economic-event) ⇒ **미소비·canonical 직접
   앵커**. 운영자가 향후 통합 idempotency layer를 원하면 재검토 가능하나 Phase-1은 분리 유지. **권장: 미소비**.
4. **split 극성 판정 방식 — 선언 enum vs 구조 파생(v1.1 M2로 갱신)**(§4.5·§2.2-4): 극성 **대수**는
   `TransformationDirection` enum reciprocal을 유지하되, **enum 값의 출처를 caller 선언에서 `pre_*`/`post_*`
   magnitude의 identity-대비 3분기 비교로 승격**했다(배수 하드코딩 0 유지·direction 위조 경로 제거). 대안(v1.0의
   caller 선언 direction)은 mis-declared direction이 진리표를 그대로 통과시켰다. **권장: 구조 파생 + enum 대수**.
5. **NT leg-set ↔ are cell-set 커버리지 결속 술어 신설 여부(M5)**(§3.4(b)·§10.4 G6): `envelope_legs_covered` 주입
   대조 술어 **미채택** — 결속을 성립시키려면 are `ProjectedCell` 좌표 REUSE(§0.4c에서 기각한 edge-1)로 돌아가거나
   opaque id 문자열 대조라는 약한 proxy에 기대야 하고, 후자는 증명 없이 증명된 척하는 fail-open 서사가 된다.
   Phase-1은 **런타임(EV-L2/3) 잔여로 정직 이연**한다. 운영자가 edge-1을 수용하면 재검토 가능. **권장: 미채택 +
   정직 공개**.

### 10.4 독립 리뷰어 공격 지점 (open questions)

- **G1 — envelope leg non-closed vs closed**: `CredibleTransitionLegKind` 10종을 §9 "where applicable" non-closed
  minimum set으로 두었다(§2.2-3). 리뷰어는 caller가 applicable subset을 잘못 좁혀 leg를 누락하면 `transition_
  envelope_complete`가 vacuous-True가 되는지 공격할 것 — **방어(v1.1 C1로 강화)**: required subset이 빈 집합이면
  **술어 내부 구조 가드가 즉시 `False`**를 반환하고(§5.1 — v1.0의 "별도 처리 위임"은 실제로 vacuous-True 경로였고
  이는 C1로 제거됨) disposition은 `NONTRADE_BLOCK_NEW_RISK`(§4.7 행 1). 다만 **비어 있지 않되 잘못 좁혀진** subset의
  under-count는 여전히 caller 책임(event-class 매핑·recon field-confidence 주입)이며 Phase-1이 구조적으로 막지
  못한다 — 이것이 non-closed set의 남은 잔여다(§4.7·§7 both-ways가 subset **내부**만 봉합함을 확인 요망).
- **G2 — split 극성 진리표의 IDENTITY cell**: (`IDENTITY`,`IDENTITY`)=no-op을 coherent True로 두었다(§4.5 진리표 A).
  리뷰어는 no-op transformation이 실제로는 다른 corporate action(예: 명칭만 변경)인데 극성만 통과시키는지 공격할 것 —
  **방어**: no-op 극성 통과는 `split_polarity_coherent`만 True로 하고, event-class·envelope completeness·admissibility
  (venue)는 별개 conjunct(§5.2 "no release"·§6.1)이므로 no-op 극성이 단독으로 `NONTRADE_ADMISSIBLE`을 만들지 않음을
  검증 요망.
- **G3 — correction/reversal의 `original_retained` 주입 신뢰**: `original_retained: bool|None`을 caller 주입으로 두어
  (§5.3), append-only 보존을 구조적으로 강제하지 않고 flag로 받는다. 리뷰어는 caller가 overwrite 후 `True`를 위조
  하는지 공격할 것 — **방어(정직 공개)**: Phase-1은 이를 주입 flag로 두되 **양극성** 취급(`is True`만 통과·overwrite=
  `is not True`⇒reject)하고, 실제 append-only 강제는 ordering append-only 순서(런타임 EV-L3)가 소유한다(§3.2).
  **v1.1 M7 주석**: v1.0은 여기에 더해 `destructive_overwrite`라는 **음극성 phantom 필드**를 §0.1(8)·§7에 서술했으나
  모델 어디에도 그런 필드는 정의되지 않았다 — 삭제했고, history 보존은 **오직** 이 양극성 `original_retained`로
  실현된다. 구조적 파생(#18 M6 no-netting 선례)으로 강화할지는 여전히 판단 지점 — 현재는 ordering 좌표 이연.
- **G4 — 11-생산자 주입의 under-realization**: §3.4 표가 11 형제를 나열하나 전용 nontrade-bool 슬롯이 실재하는 상대와
  좌표-의존 상대를 §3.4(b)에서 구분했다. 리뷰어는 좌표-의존(orthostate·authority·replacement) 상대가 실제로는 phantom
  seam인지 공격할 것 — **방어**: 좌표-의존은 주입 StrEnum/bool로 소비하고 seam test(§7)로 polarity만 검증하며 NT은
  이들을 판정하지 않음을 명시(정직 이연).
- **G5 — NT-EV-002 core인데 002가 multi-leg merger**: §1이 002(merger/spin-off)를 `transition_envelope_complete`의
  L1 슬라이스로 두었다. 리뷰어는 merger multi-leg 완전성이 정말 L1-decidable인지(broker leg 증거 필요 아닌지) 공격할
  것 — **방어**: 002는 `EV-L1/3`(L1 슬라이스 + `/3` 통합 잔여)이며 L1은 leg-set completeness·no-netting의 model/
  property 검증만이고 실 broker leg 증거·capacity commit은 `/3`·rcl 런타임(닫지 않음·§1 결정적 사실 2).
- **G6 — NT leg-set ↔ are cell-set 커버리지 결속 미실현(M5 승격, v1.1)**: §0.4d는 "NT이 10-leg completeness를
  소유하고 are가 그 envelope의 worst-intermediate risk를 투영한다"는 분업을 선언하지만, **NT의
  `CredibleTransitionLegKind` 집합이 are `worst_intermediate_risk`에 실제로 입력된 `ProjectedCell` 집합을 덮는지를
  검증하는 결속 술어가 Phase-1에 존재하지 않는다**(§3.4(b) 정직 공개). 리뷰어는 "각자 자기 집합 안에서만 fail-closed
  이므로 leg를 완비하고도 are에 일부 cell만 넘기면 두 술어 모두 통과하는 **분업 이음매의 fail-open**"을 공격할 것 —
  **방어(정직 공개·미방어 인정)**: 이 잔여는 **막지 못한다**. Phase-1 주장 범위는 "NT은 자신의 leg 집합 안에서
  완전성을 강제한다"뿐이며 "NT leg ≡ are cell"은 **주장하지 않는다**. 결속 술어(`envelope_legs_covered`)를 신설
  하려면 are `ProjectedCell` 좌표를 알아야 하므로 §0.4c에서 기각한 edge-1을 부활시키거나 opaque id 문자열 대조라는
  약한 proxy에 기대야 하고, 후자는 증명 없이 증명된 척하는 더 나쁜 결함이다 — 그래서 **런타임(EV-L2/3) 잔여로
  이연**했다(§10.3-5 판단 지점). 리뷰어는 (a) 이 미실현이 문서 전체에서 일관되게 공개되어 있는지, (b) 어디에도
  "NT이 aggregate envelope 완전성을 보증한다"는 과대 주장이 없는지를 검증 요망.

---

**본 문서는 어떤 NT-EV·ADR acceptance·restricted-live·production도 승인하지 않는다.** ADR acceptance는 오직 *실행된*
evidence로만 온다(ADR §18 line 392·§26 line 502–514; VER-002-001 §5). 닫는 NT-EV = 0건. EV-L1-complete 주장 금지.
