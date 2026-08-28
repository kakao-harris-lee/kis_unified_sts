# 설계 문서 #24 — Post-Trade Economic Obligations·Settlement Finality·Conservative Account-State Governance 계약 (2026-07-27, v1.2 에라타)

> **문서 번호 규약 각주(#24 확정)**: 세션 A의 #23 CUR(currentness-fencing, ADR-002-024)은 본 문서보다 앞서고, 본 문서는
> **#24**다. 시리즈 순번은 착수 순서가 아니라 비준·선점 순서를 따른다(#16 AFG v1.0 "#15"→v1.1 "#16" 개번 선례·#18
> "잠정 #18" 확정 선례·#21 세션 A #19/#20 선점 반영 선례). naming/번호는 load-bearing이 아니다. **v1.1 정정(리뷰
> M5)**: v1.0 저작 시점에 cur은 세션 A WIP·미커밋이었으나 **이후 커밋됐다**(`1390ef9d` "feat(tos/cur): Phase 1
> (EV-L1) Currentness-Fencing models + property tests"; 디스크 `tos/src/tos/cur/` 실재). ⇒ 본 v1.1은 **cur 패키지
> 코드를 실측 인용**하고(특히 `DimensionKey.POST_TRADE` `cur/vocabulary.py:146` — cur이 이미 소유하는 post-trade
> currentness 차원, §3.5 §22), **cur을 committed 형제로 계상**한다(§0.3). ADR-002-024 **원문**(§22 currentness 이연
> 대상)도 계속 인용한다.
>
> **대상 ADR**: ADR-002-030 — Post-Trade Economic Obligations, Settlement Finality, and Conservative Account-State
> Governance ("PTF"). 739줄. Status **Proposed**, Date 2026-07-14. Decision Type: Safety-Critical Architecture
> Decision. **Refines**(ADR line 8): RFC-001 SAFE-004·010–015·020–025·030–035·040–044·048·050·051·052; RFC-002
> §§3.1·9.1·10.4–10.10·11–15·17·20·22–24·29; VER-002-001 §§5·362–373·374·377–381. **Depends On**(ADR line 9):
> RFC-000·RFC-001·**ADR-002-001 through ADR-002-029**. 의존 ADR 중 tos/에 **committed·구현된 인접 형제**만 인용한다
> (canonical·ordering·rcl·are·recon·brokercap·egress·orthostate·nontrade·liveauth·authority·sbr·time — §0.4·§3).
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며 스펙 텍스트
> (RFC/ADR/템플릿/프로파일)를 **변경하지 않는다**. **broker-agnostic 원칙(project memory `tos-spec-broker-agnostic`)**:
> 본 문서의 규범 텍스트는 **어떤 구체 broker·clearing·custodian·bank(KIS 포함)도 명명하지 않는다.** 이 ADR은
> `+Broker` 12/12(전 PTF-EV) 지배 문서이므로 특히 엄격히 — obligation/settlement/finality/statement 불변식은 전부
> broker-agnostic이며, broker·custodian·clearing·banking 제약은 **capability class(Broker/Clearing/Custodian/Banking
> Capability Profile, #10 brokercap)로만 표현하고 주입 좌표로만 소비**한다.
>
> **자체 시리즈(실측·앵커)**: ADR-002-030은 **자체 `PTF-INV-001..018` 불변식 시리즈(§6 line 150–220, 18종)** ·
> **`PTF-AC-001..012`(§27 line 635–681, 12종)** · **`PTF-EV-001..012`**(register `verification/EVIDENCE-REGISTER-
> 002.csv` domain "Post-Trade Economic Obligations and Finality", 12행)를 정의한다. ⇒ 본 계약은 모델 불변식·술어를
> **`PTF-INV-###` / `PTF-AC-###` / `PTF-EV-###` / §-clause / `SAFE-###`(§28 traceability line 689–697)**에 앵커하고
> **새 INV/AC/EV 시리즈를 창작하지 않는다**(§0.4g). #6(`SA-INV`)·#10(`BC-INV`)·#16(`AFG-INV`)·#19(`VTG-INV`)이 자체
> INV에 앵커한 것과 동형이며(PTF는 자체 INV 시리즈 **보유**), #9/#11/#18/#21(자체 INV 부재로 EV/AC 앵커)과는 상황이
> 다르다.
>
> **선행 문서(의존·형제)** — 전부 **committed·구현**(코드 실측):
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 전용 top-level 패키지에 놓이고 §3.2 허용목록 안에서만 의존한다(§0.3). line 164 "naming은
>   load-bearing이 아니다 — 내부 세분화는 후속 설계 문서가 정의한다"에 따라 본 문서가 신규 패키지 내부를 정의한다.
> - [설계 #21 — Corporate Actions·Non-Trade State Changes 계약 (v1.1, 비준·구현)](2026-07-26-tos-non-trade-design.md)
>   + 코드 `tos/src/tos/nontrade/`. **본 문서의 최인접 상류이자 최대 소유권 인접 지대다 — 상호 명시 경계로 중복 0.**
>   **결정적 실측(소유권 경계 — 상호 이연)**: ADR-002-010 §16 line 309 verbatim "This ADR owns the **non-trade event
>   and transformation identity**; **ADR-002-030 owns the obligation-lifecycle serialization**"(`tos/src/tos/nontrade/
>   __init__.py:34` 재인용)가 nontrade→PTF **명시 이연**이고, 역으로 본 ADR §17 line 414 verbatim "**ADR-002-010 owns
>   lifecycle and non-trade event identity and transformation. This ADR owns the resulting obligation legs and their
>   finality**"가 PTF→nontrade **명시 이연**이다. nontrade는 event·transformation identity + **event workflow
>   lifecycle**(`NonTradeEventWorkflowState`, `vocabulary.py:165`)을 소유하고, PTF는 **obligation-lifecycle
>   serialization**(PTOL)·**obligation legs**·**finality**를 소유한다. **"lifecycle"이라는 명칭이 양쪽에 등장하나
>   지칭이 다르다**(nontrade=event workflow / PTF=obligation lifecycle — §3.5 명제-동일성 함정). PTF-EV-006(Exercise/
>   Assignment/Delivery/Corporate-Action Obligations)이 접점이며 **본 Phase-1의 L1 슬라이스**다 — nontrade가 event를
>   생산(NT-EV-004 Option Exercise·NT-EV-005 Futures Expiry, 둘 다 `EV-L3+Broker` — nontrade측 미Phase-1)하고, PTF가
>   그 event로부터의 obligation leg·finality를 소유한다. **`tos.nontrade`는 import하지 않는다**(형제; event-state
>   주입 좌표/produced-token으로만 소비 — §3.4/§3.5).
> - [설계 #13 — Aggregate Risk Projection 계약 (v1.1, 비준·구현)](2026-07-25-tos-aggregate-risk-projection-design.md)
>   + 코드 `tos/src/tos/are/`. **두 번째 최인접 상류이자 소유권 인접 지대.** are는 §21 aggregate-risk 투영을 **이미
>   소유·구현**한다: **`RiskDimensionKind.{SETTLEMENT_CASH_CURRENCY(`vocabulary.py:65`), LEVERAGE_MARGIN_COLLATERAL
>   (`:61`), OPTION_GREEKS_EXERCISE_ASSIGNMENT(`:64`)}`** · **`AdverseScenarioKind.{MARGIN_COLLATERAL_BORROW_FX_SETTLE_
>   ASSIGN(`vocabulary.py:112`), MISSING_ACK_RECEIPT_AMBIGUITY(`:108`), EXTERNAL_TRAPPED_NONTRADE_CONCURRENT(`:115`)}`**
>   · **`BenefitKind.NETTING(`vocabulary.py:131`)`** · `worst_intermediate_risk`·`credible_space_bounded`·`envelope_
>   bound_not_enlarged`. **결정적 소유권 증거**: are가 이미 settlement/cash·margin/collateral·exercise/assignment를
>   aggregate-risk **축의 first-class dimension**으로, margin/collateral/borrow/FX/settle/assign 및 missing-ACK
>   ambiguity를 **first-class scenario**로, netting을 **benefit-kind**로 소유하므로 — 본 ADR §21 "Aggregate Risk State
>   Snapshot SHALL include every ... post-trade obligation"의 **risk 산출은 are 소유**이고 PTF는 **obligation-set
>   열거 완전성 + no-favorable-default**를 소유한다(§0.4d — #21 §0.4d 이중 계상 정합 동형). **`tos.are`는 import하지
>   않는다**(형제; 주입 verdict/scalar로만).
> - [설계 #5 — Risk Capacity Ledger 계약 (v1.1, 비준·구현)](2026-07-21-tos-risk-capacity-ledger-design.md) + 코드
>   `tos/src/tos/rcl/`. **세 번째 소유권 인접 지대이자 본 ADR의 최강 봉인 경계.** rcl은 capacity 산술·commit·release·
>   transfer·quarantine을 **이미 소유·구현**한다: **`TransitionCause.{FINAL_QUANTITY_PROOF(`vocabulary.py:94`),
>   RECOGNIZED_EXTERNAL_CHANGE(`:92`)}`**(FQP만 `RELEASED` 도달 가능 — §5 INV-007) · **`CommandType.{APPLY_FINAL_
>   QUANTITY_PROOF, RECORD_FILL_AND_TRANSFER_USAGE, RELEASE_RESERVATION, TRANSFER_ORDER_TO_POSITION_USAGE, CREATE_
>   EXTERNAL_QUARANTINE, MARK_TRAPPED_EXPOSURE}`** · `credible_union_capacity`·`CapacityState.{TRAPPED_CONSUMED,
>   QUARANTINED_UNKNOWN}`·`WEAK_CAUSES`(TIMEOUT/ABSENCE/OPERATOR_ASSUMPTION는 conservatism만 증가). **결정적 증거**:
>   본 ADR §1 line 21 verbatim "The Risk Capacity Ledger remains the sole capacity mutation and serialization
>   authority ... PTOL state may support an evidence-bound RCL command, but only the RCL may perform the transition"
>   ·PTF-INV-008 이 PTF(PTOL·obligation compiler·finality proof)를 **capacity-non-mutating**으로 봉인한다.
>   결정적으로 — **rcl의 `FINAL_QUANTITY_PROOF` cause/`APPLY_FINAL_QUANTITY_PROOF` command는 order capacity의
>   proof-gated release이지 post-trade obligation finality가 아니다**(PTF-INV-002 "FQP ... do not prove any post-trade
>   obligation final", ADR §1 line 23). **`tos.rcl`은 import하지 않는다**(형제; obligation-set을 produce하고 rcl이
>   commit — 주입 방향).
> - [설계 #9 — Reconciliation Confidence 계약 (비준·구현)](2026-07-25-tos-reconciliation-confidence-design.md) + 코드
>   `tos/src/tos/recon/`. §11 per-field confidence·§19 statement per-field evidence는 recon 소관이다: `classify_field`
>   (`predicates.py:107`; 0-path⇒UNKNOWN·1⇒SINGLE_SOURCE·≥2 **독립** 동의⇒CORROBORATED·불일치⇒CONFLICTED·stale⇒STALE;
>   **`common-mode paths (shared independence_class) cannot corroborate each other` — RECON-EV-001**, `predicates.py:
>   127`)·`FieldConfidenceClass`(5종, `vocabulary.py:26`)·**`SafetyRelevantField.{POST_TRADE_OBLIGATION_IDENTITY_AND_
>   VERSION(`vocabulary.py:85`), SETTLEMENT_CASH_AVAILABILITY_COLLATERAL_ELIGIBILITY(`:89`), CASH_MARGIN_COLLATERAL
>   (`:78`)}`**(non-closed minimum set)·`ConservativeBound`·`merge_conservative`·`any_field_conflicted`. **결정적 증거**:
>   recon이 이미 **post-trade obligation·settlement/cash/collateral 필드의 per-field confidence를 소유**하므로 —
>   본 ADR §11 "per-field confidence"·PTF-INV-005 "**confidence score ... cannot replace exact per-field proof**"의
>   경계는 명확하다: **recon = per-field evidence confidence(신뢰도) / PTF = field-specific finality proof(최종성)** —
>   **명제 상이(confidence ≠ finality)**. PTF는 recon `FieldConfidenceClass`를 주입 소비하고 그 위에 finality-proof
>   binding을 얹는다. **`tos.recon`은 import하지 않는다**(형제).
> - [설계 #10 Broker Capability (비준·구현)](2026-07-25-tos-broker-capability-design.md) + `tos/src/tos/brokercap/`.
>   §11/§19 broker·clearing·custodian·banking capability·FQP·statement common-mode는 brokercap 소관이다:
>   **`CapabilityDimension.{POSITIONS_BALANCES_MARGIN(`vocabulary.py:79`), CORPORATE_ADMINISTRATIVE_EVENTS(`:81`),
>   FILL_EVENTS(`:73`), ACKNOWLEDGEMENT_SEMANTICS(`:72`), ACCOUNT_EVENT_PUSH(`:80`)}`** · `fqp_adequate`(`predicates.
>   py:595`) · `broker_capability_sufficient`(`:206`) · `CapabilityStatus`(7종, `vocabulary.py:29`). **`+Broker` 12/12는 brokercap
>   주입으로 discharge**한다 — PTF는 broker capability를 판정하지 않고 **주입 소비**한다(broker-agnostic). **주의(정직
>   공개)**: brokercap에는 전용 `SETTLEMENT`/`CUSTODIAN`/`STATEMENT_COVERAGE` capability dimension이 **없다**(실측 —
>   `POSITIONS_BALANCES_MARGIN`·`CORPORATE_ADMINISTRATIVE_EVENTS`·`FILL_EVENTS`가 최인접) — settlement/custodian/
>   statement-coverage capability는 **Phase-0 open question**(ADR §29 Q2/Q5)이며 본 Phase-1은 기존 dimension을 주입
>   소비한다. **미import**(형제).
> - [설계 #22 Egress Commit-Proof (비준·구현)](2026-07-26-tos-egress-commit-proof-design.md) + `tos/src/tos/egress/`.
>   §16/§22 external economic instruction transmission·final egress boundary·§23 credential/route는 egress(ADR-002-013)
>   소관이다: `EgressAdmission`(ADMIT/DENY)·`CommitProofValidity`(VALID/INVALID/UNKNOWN)·`credential_route_authority_
>   disjoint`(`egress/predicates.py:405`)·`capability_and_permit_single_use`·`generation_monotone`·`stale_principal_structurally_
>   rejected`·`monotonic_denial_no_revival`. ADR §1 line 31·PTF-INV-016 verbatim "PTOL, reconciliation, statement,
>   evidence, dashboard, recovery, and operator identities SHALL NOT hold a usable external-economic credential and
>   route". PTF는 external economic instruction을 **구성·전송하지 않는다**(구조적 부재 — §4.4). **`tos.egress`는
>   import하지 않는다**(형제; §16/§22 egress coupling은 EV-L2/3 런타임 잔여).
> - [설계 #8 Orthogonal Trading State (비준·구현)](2026-07-25-tos-orthogonal-state-design.md) + `tos/src/tos/orthostate/`.
>   §10 obligation lifecycle orthogonality의 order/knowledge/capacity 축은 orthostate 소관이다: `KnowledgeState`(7종,
>   `RECONCILED` 포함, `vocabulary.py:121`)·`IntentState`(7종, `CLOSED` 포함, `:32`)·`BrokerOrderState`(9종, `FILLED`
>   포함, `:92`)·`no_coupling_violation`·`reconstruct_conservative`. **결정적 좌표 비붕괴**: PTF **obligation-lifecycle**
>   축(POTENTIAL→...→`CLOSED`→`FINALITY_PROVEN`)은 orthostate 5 축과 **별개 6번째 축**이며(ADR §10 line 305 "orthogonal
>   to ADR-002-006 Knowledge/Evidence State"), 토큰이 겹쳐도(`CLOSED`·`RECONCILED`류) 별개 타입이다(§2.2-5). **미import**
>   (형제; 주입 좌표).
> - [설계 #7 Live Authorization (비준·구현)]·[설계 #6 Safety Authority (비준·구현)]·[설계 #17 Startup/Recovery (SBR,
>   비준·구현)]·[설계 #8 time(ADR-002-008)]. §22 account-state가 live authorization에 미치는 영향 = liveauth/authority
>   (`no_automatic_rearm`·`authorization_revived_by_nothing`); §24 recovery inventory·obligation graph = sbr(`recovery_
>   inventory_complete`·`restore_worst_credible_union`·`unknown_stays_conservative`); §22 trustworthy-time/snapshot age
>   = time(`freshness_verdict`·`effective_snapshot_age_bound`·`snapshot_grants_no_authority`). PTF-INV-017/018(economic
>   effect outlives artifacts·evidence/recovery do not revive)은 이 형제들이 소유한 no-revival을 **주입 소비**한다.
>   전부 **미import**(형제).
> - **인접 비-소비 형제(명제 상이·phantom 방지 §0.4e)**: iap(ADR-002-023) `ConsumptionOutcome.IDEMPOTENT_REPLAY`
>   (`iap/vocabulary.py:165`, authorization-token single-use)·rcl `ApplyReason.IDEMPOTENT_REPLAY`(capacity-command)·
>   nontrade `CorrectionReversalOutcome.IDEMPOTENT_REPLAY`(economic-event-application)는 PTF `ObligationCommitOutcome.
>   IDEMPOTENT_REPLAY`(**fill-to-obligation commit**)와 **명제가 다르다**(defect-class #3). 네 술어는 **canonical
>   `classify_record_pair` 원시의 네 독립 하류**이며 상호 import하지 않는다(§0.4e). PTF는 canonical 원시를 직접 앵커한다.
> - **evidence(ADR-002-016)**: §24 evidence custody·replay는 evidence 소관 런타임(EV-L2/3). PTF-INV-018 "A statement,
>   registered item, dashboard, successful replay ... is not executed verification evidence"(ADR §24 line 548) —
>   PTF는 frozen digest-bound 레코드만 재구성하고 replay ENGINE은 evidence 런타임이다. **미import**.
>
> **v1.2 에라타 고지(2026-07-27, 비준 효력 유지)**: 본 개정은 **의미 변경이 아니라 안전-방향 정합 에라타**다(#18 v1.2
> [venue producer 실측 정정] 선례 동형). 발견 경로 = **구현 후 적대적 코드 리뷰 MAJOR**(판정 ACCEPT-WITH-MINOR;
> CRITICAL 0·구현 fail-open 0 — 즉 구현은 v1.1 계약에 **충실**했고 결함은 **계약 텍스트 측**에 있었다). 내용:
> §5.7 `finality_proof_non_transferable`가 `ObligationLegScope` **6성분만** 대조하는데, 그 6성분(leg·account·
> currency·value-date·source-revision·finality-class)에는 **obligation 식별자가 없다**. 서로 다른 두 obligation이
> 동일 scope를 정당하게 공유할 수 있으므로(같은 account가 같은 통화를 같은 value-date에 결제) **한 obligation의
> finality proof가 다른 obligation의 동일 leg를 덮는 것으로 판정**되고, §4.8 행 10 rank 1이 미발화해
> `POST_TRADE_ADMISSIBLE` 도달이 가능했다. 정정: **ADR §11 line 320 "exact obligation identity"** 근거로 술어에
> **keyword-only `target_obligation_ref` / `target_obligation_version`**을 추가하고, 제공 시 `proof.obligation_ref` ·
> `proof.obligation_version`과의 일치를 **추가 요구**한다(§5.7·§9.1). **미제공 시 기존 scope-only 거동 유지**
> (하위호환 — 리뷰어가 호환성 실증). **보수 방향**: 인자 제공은 판정을 **좁히기만** 하므로 `True`를 `False`로 바꿀
> 수 있을 뿐 어떤 허용도 넓히지 않는다 ⇒ v1.1 비준 효력·§0.2 비-acceptance·**닫는 PTF-EV = 0건** 규율 전부
> **불변**. 술어 개수 **19 불변**(시그니처 확장이며 신규 술어 아님). 에라타 승인 = 오케스트레이터 위임 비준
> (2026-07-25 표준지시).
>
> **비준 상태**: **2026-07-27 운영자 위임 자동 비준(v1.1) — 효력 발생**(표준지시 2026-07-25 + 본 세션 운영자 "계속"
> 지시). 경위: v1.0 저작 → 오케스트레이터 1차 심사 통과(상호 이연 양방향·PTF-INV-013·PLAN:221 실측) → 독립 비평
> 리뷰 **REVISE(CRITICAL 1·MAJOR 8·MINOR 7·Gap 6** — C1 disposition 시그니처 8/17 수용[#21 C1 동형이 방지
> 메커니즘 내부에서 재발]·M2 reopen 미봉인; 소싱은 시리즈 최고 평가[62 인용 중 55 정확·공격 3건 "주장 정확" 불발]) →
> **v1.1 전건 반영(반론 0)**: 시그니처 8→19 입력·§4.8 16→22행 문자 1:1·`finality_proof_current` 신설(reopen 9행)·
> `cash_kind_matches_requirement` 단일 명제·CUR 완결 반영(`test_seam_cur`·drift-lock 19)·PTF-AC 12/12 커버리지 표
> §1.1 신설 → 오케스트레이터 스팟체크 통과(잔존=개정 로그 문맥만). **§10.3 판단 지점 전건 승인** — 핵심: edge 0·
> `tos.posttrade`·finality 4-성분 monotone(+proof_current 실현)·canonical 4번째 idempotency 하류. 효력:
> `tos/src/tos/posttrade/` Phase 1(EV-L1) 착수 승인.
> 본 문서는 **어떤 PTF-EV·ADR acceptance·restricted-live·production도 승인하지 않는다**(§0.2). ADR acceptance는 오직
> *실행된* evidence로만 온다(project memory `tos-spec-rfc-authoring-track`; ADR §30 line 738 "Authorship ... does not
> satisfy these gates"·§27 line 633 "Written cases define obligations only. They are not completed evidence"; VER-002-
> 001 §5 "Registration is not execution").
>
> **리뷰 이력(선제 봉합 defect class)**: 시리즈 축적 REJECT/REVISE — #6 v1.0 REJECT(fail-open seam: vacuous-True)·
> #8 v1.0 REJECT(cross-section 혼동)·#10 v1.0 REVISE(seam 실측 오명명)·#13 ARE(사전 6→실측 5 core 정정)·#16 AFG
> v1.0 REVISE(CRITICAL 1[방향 반전])·#18 PR v1.0 REVISE(CRITICAL 2[netting 극성·sufficiency 조달원 category-error])·
> **#21 NT v1.0 REVISE(CRITICAL 2[`transition_envelope_complete` ∅ 무주 위임 = vacuous-True·`RecordPairKind` 반전
> 매핑]·MAJOR 8·MINOR 4)**. 본 문서(#24)가 **선제 봉합**한 defect class: (a) §1 L1 슬라이스 판정(PTF-EV **5행** L1
> 슬라이스 = 001·002·004·006·008·닫는 PTF-EV 0). (b) 소유권 중복 구조적 배제(§3.5 코드 실측 소유권 분할표 — 명제-동일성
> 열). (c) fail-open seam 방지(중앙 술어 본질적 fail-closed·양성 identity 증명·both-ways canary). (d) staged EV 정직
> 분리(§1·§6 — L1 슬라이스만 저작, `/2`·`/3`·`+Broker`·`+Security` 잔여 명시). (e) cross-section self-consistency
> pass(§1↔§4/§5↔§7). (f) verbatim 전사 + ADR line 병기(에라타 방지). (g) 실측-원천 결함 방지(모든 seam 코드 실측
> signature+라인; 인용 전 grep). (h) **방향 극성 검산**(settlement-direction/finality-monotonicity 진리표 §4.5 — 본
> ADR 후보). (i) **전사 완전성**(§6 18불변식·§10 12상태·§14 9구분·§15 8상태·§17 9leg·§19 7manifest·§22 7currentness
> 원문 항목 수 전수 대조). (j) **truthy-sentinel 극성 분기**(양극성 `is True`·음극성 `is False`·result identity). (k)
> **∅-공허 양방향**. (l) **canonical `classify_record_pair` 5멤버 전수 매핑**(fill-commit idempotency — #21 C2 교훈).
>
> **시리즈 규율 4건(#18 v1.1 신설·#21 상속 — 본 문서 전부 상속)**: (1) **truthy-sentinel 극성 분기**(음극성 필드에
> `is False` 강제·`is not True` 금지); (2) **카운트 대조 전수화**(모든 열거 리스트에 항목 수 병기·개별 계수); (3)
> **§3.4/§3.5 seam 표에 "형제 술어 docstring 명제 ↔ ADR 조항 명제 동일성" 열**(명제 상이 시 좌표-의존 이연으로 강등 —
> confidence≠finality·event-lifecycle≠obligation-lifecycle·FQP≠post-trade-finality·nontrade-netting≠obligation-netting≠
> are-netting-benefit exemplar); (4) **§-row 매핑을 normative 문장 단위로**(PTF §12 line 336/338/347이 한 조항에 3규범을
> 담은 사례·§21 line 21이 sole-authority+support-command+only-RCL 3규범).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-030 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). **core(L1 슬라이스) / predicate-only(substrate) / not-
   Phase-1(형제 소유·런타임 이연) 3분류.** **결정적 사실(register 실측·CSV-aware 파싱 — 제목 쉼표 주의)**: `PTF-EV`
   12행 중 **5행(001·002·004·006·008)이 register 최소 레벨에 `EV-L1` 슬라이스 보유** — 001(`EV-L1/2/3+Broker`,
   "Fill/FQP vs Post-Trade Obligation Separation")·002(`EV-L1/2/3+Broker`, "Fee/Tax/Interest/Financing Legs and
   Corrections")·004(`EV-L1/2/3+Broker`, "Margin/Collateral/Encumbrance/Haircut/Double-Use")·006(`EV-L1/2/3+Broker`,
   "Exercise/Assignment/Delivery/Corporate-Action Obligations")·008(`EV-L1/2/3+Broker+Security`, "Statement Coverage,
   Provenance, Conflict/Common-Mode"). **오케스트레이터 재검증 카운트 "L1 슬라이스 5행 = 001·002·004·006·008"은 실측
   결과 정확**하다(정정 없음). 나머지 7행 전부 L1 슬라이스 부재: 003(`EV-L2/3+Broker`)·005(`EV-L2/3+Broker`)·007
   (`EV-L2/3+Broker+Security`)·009(`EV-L2/3+Broker+Security`)·010(`EV-L2/3+Broker+Security`)·011(`EV-L3+Broker+
   Security`)·012(`EV-L2/3+Broker+Security`). **`+Broker`는 12/12 전수**(전 PTF-EV) — 이는 **not-Phase-1 대량**이며
   staged-L1 슬라이스는 각 행 `EV-L1/...`의 **L1 부분만**이다(VER-002-001 line 171 "EV-Ln is the earliest non-live
   evidence stage"·`EV-L1/2/3` = staged EV-L1/EV-L2/EV-L3). **닫는 PTF-EV = 0건**(L1 슬라이스 저작 ≠ EV closure:
   `/2`·`/3`·`+Broker`·(008)`+Security` 잔여). "**EV-L1-complete 주장 금지**". **`+Security`는 008에서 L1 슬라이스와
   공존하나 security-boundary assessment 자체는 EV-L1이 아니다**(VER-002-001 line 170 "independent security-boundary
   assessment") — 008의 L1 슬라이스는 statement-coverage completeness·common-mode 구조 property이고 credential/route/
   bypass security assessment는 잔여다.
2. **post-trade 어휘 + obligation 데이터 모델**(§2, **core substrate**): `PostTradeObligationLifecycleState`(§10,
   8 linear + 4 branch = 12종 verbatim)·`FinalityDimensionKind`(§6 PTF-INV-002, 10종 — orthogonal finality 축)·
   `ObligationLegDirection`(§9 line 273, 8종 debit/credit/delivery/receipt/encumbrance/release/return/contingent)·
   `CashKind`(§6 PTF-INV-010, 6종 — non-substitution 축)·`MarginCollateralState`(§15 line 385, 8종)·`StatementClass`
   (§19, 3종 preliminary/final/revised)·`ObligationCommitOutcome`(6종 — canonical `classify_record_pair` 하류)·
   `PostTradeDisposition`(로컬 결과 StrEnum, truthy-untestable, 5종) 어휘 + digest-bound `EconomicObligationRecord`
   (§9 IndependentIdArtifact)·`PostTradeFinalityProof`(§11 IndependentIdArtifact)·`StatementCoverageManifest`(§9.9/§19
   IndependentIdArtifact) + value `ObligationLeg`·`MonetaryLeg`·`CollateralAllocation` + all-false `AllFalsePostTrade
   Consequence`(§10 line 312 finality-grants-nothing). Post-Trade Obligation Generation은 `tos.ordering` 좌표(§3.2 —
   #13/#16/#18/#21 동형, 별도 heavy 아티팩트 아님).
3. **finality-dimension orthogonality 중앙 불변식**(§4.1/§5.1, **PTF-EV-001 core L1 슬라이스 — IMPLEMENTATION-PLAN-002
   line 221이 명시 지목한 유일 property test** — ADR §12·PTF-INV-002·PTF-AC-001): `finality_dimensions_orthogonal(...)
   -> bool`. **Final Quantity Proof는 final cumulative filled quantity + zero remaining executable quantity만 증명**
   하고(ADR §12 line 338·§1 line 23) **settlement·cash·fee·custody·borrow·delivery·title finality를 증명하지 않는다**
   (§12 line 340–345, 6 non-implication + PTF-INV-002 10-dimension 상호 non-implication). **10 finality dimension은
   서로 함의하지 않는다**(PTF-INV-002 line 156 verbatim "do not imply one another"). 이것이 defect-class #2가 지목한
   **finality 단조/역전 금지 축의 실현**이다(§4.5-B): 어떤 dimension도 UNKNOWN→PROVEN을 **positive proof 없이** 넘지
   못하고, 한 dimension의 PROVEN이 다른 dimension을 PROVEN으로 만들지 못한다.
4. **fill-to-obligation commit idempotency 중앙 불변식**(§4.2/§4.6/§5.2, **PTF-EV-001 core L1 슬라이스** — ADR §12
   line 336·PTF-AC-001): `obligation_commit_idempotent(...) -> ObligationCommitOutcome`. **fill-to-obligation commit은
   idempotent이고 originating Intent·attempt·broker order·fill revision·position transfer·RCL allocation에 causally
   linked**(§12 line 336)이며, **claimed terminal outcome 이후 발견된 fill은 idempotently 적용·obligation 생성/정정·
   generation advance·capacity 보존**(§12 line 347). **canonical `classify_record_pair` 실측 5-member 전수 매핑(#21 C2
   교훈)**: `IDEMPOTENT_DUP`(same primary/idempotency id·same bytes, `record_pair.py:94/101`)⇒`IDEMPOTENT_REPLAY`
   no-op · `CRITICAL_CONFLICT`(same **primary** id·diff bytes, :96)⇒`REJECTED_CONFLICT` · `DIVERGENT_EMISSION`(same
   **idempotency** id·diff bytes, :103)⇒`REJECTED_CONFLICT` · `DISTINCT`(:105)/`NOT_COMPARABLE`(digest None, :87)⇒
   `REJECTED_UNKNOWN` · **`prior is None`(첫 commit)은 classify 선행 게이트**로 `COMMITTED_ONCE`(§5.2). **두 위조 축은
   별개 kind이며 둘 다 `REJECTED_CONFLICT`로 접힌다**(contain-both·no last-write-wins — `record_pair.py:68`).
5. **no-favorable-default·no-unproven-netting 중앙 불변식**(§4.3/§4.5-A/§5.3, **PTF-EV-002 core L1 슬라이스** — ADR §13·
   §9 line 279·PTF-INV-004/007·PTF-AC-002): 세 구조적 파생 술어 — (i) `monetary_leg_conservative(...)`(**absence ≠
   zero**: missing line item·zero estimate는 zero의 proof가 아니다 — §13 line 355 verbatim "A missing line item or
   zero estimate is not proof of zero"; None/absent ⇒ UNKNOWN/greatest-credible, favorable-zero 아님), (ii)
   `netting_requires_positive_proof(...)`(uncertain receivable는 payable를 fund 못 한다 — PTF-INV-007; netting은 both
   legs present ∧ same scope(account/currency/value-date/legal-entity/settlement-system) ∧ **injected enforceable-
   netting proof**일 때만 valid, 하나라도 부재 ⇒ 둘 다 gross), (iii) `missing_counterleg_is_adverse(...)`(balanced
   accounting leg를 positively establish 못하면 missing counterleg는 explicit·greatest-credible-adverse-union이고
   consumer는 **local favorable balancing entry를 construct 못 한다** — §9 line 279 verbatim). **극성 함정(§4.5-A)**:
   불확실 receivable(credit)를 payable(debit)에 netting해 unproven headroom을 만드는 fail-open. **구조적 파생**:
   netting-absent는 flag가 아니라 **both legs가 gross magnitude로 병존 + proof-token 부재**로 파생(#18/#21 no-netting
   구조-파생 선례).
6. **collateral no-double-use + cash-kind non-substitution 중앙 불변식**(§4.4/§5.4, **PTF-EV-004 core L1 슬라이스** —
   ADR §15·§14·PTF-INV-010/011·PTF-AC-004): (i) `collateral_no_double_use(...)`(**same collateral unit은 free+encumbered
   동시 계상·two-obligation pledge·confirmed-release 전 reuse 금지** — §15 line 386 verbatim·PTF-INV-011; 구조적 보존:
   한 unit의 allocation state는 상호배타(free XOR encumbered)이고 pledge 합 ≤ available), (ii) `margin_collateral_states
   _distinct(...)`(**margin observation·call·request·acknowledgement·pledged·accepted·available-excess·confirmed-release
   8상태 non-implication** — §15 line 385; broker favorable margin/buying-power figure는 Critical Input·ceiling이지
   unconditional proof 아님, §15 line 387), (iii) `cash_kind_matches_requirement(...)`(**ledger/pending/settled/
   withdrawable/buying-power/collateral-eligible 6 cash kind는 silent substitution 금지** — PTF-INV-010·§14 line 363–
   373; **substrate — settlement/cash availability PROOF은 PTF-EV-003 `EV-L2/3` 잔여**, §1). **buying power ≠ available
   cash**(§25.4 rejected)는 cash-kind 타입 구분으로 구조 실현.
7. **exercise/assignment/CA obligation leg completeness + event-state ≠ obligation-finality 중앙 불변식**(§4.5-B/§5.5,
   **PTF-EV-006 core L1 슬라이스 · 최대 소유권 인접(nontrade)** — ADR §17·PTF-INV-002/006·PTF-AC-006): (i) `obligation_
   legs_from_event_complete(...)`(exercise·assignment·expiry·delivery·cash-settlement·conversion·redemption·
   distribution·tender·rights·corporate-action event의 **every credible asset·cash·fee·tax·financing·margin·borrow·
   custody·delivery leg 모델링** — §17 line 416, 9 leg 축), (ii) **`event_state_not_obligation_finality(...)`**(nontrade
   event state `APPLIED_LOCAL`/`RECONCILED`(주입 토큰)은 resulting obligation을 final로 증명하지 않는다 — §17 line 418
   verbatim "An ADR-002-010 event state such as ``APPLIED_LOCAL`` or ``RECONCILED`` does not prove its resulting
   obligations final"; local deadline의 exercise/assignment/delivery/CA report 부재는 obligation 부재의 proof 아님 —
   §17 line 418·PTF-INV-004). **소유권 경계(§3.5 핵심)**: nontrade = event·transformation identity + event workflow
   lifecycle / PTF = **resulting obligation leg + finality**(ADR-002-010 §16 line 309 ↔ ADR-002-030 §17 line 414 상호 이연). PTF는 nontrade
   event-state를 **주입 토큰**으로 소비하고 re-classify하지 않는다.
8. **statement coverage completeness + source common-mode independence 중앙 불변식**(§4.6-B/§5.6, **PTF-EV-008 core L1
   슬라이스(+Security 잔여)** — ADR §19·PTF-INV-014·PTF-AC-008): (i) `statement_coverage_complete(...)`(**expected ⊆
   received**: pages/files/sections/cursors/checksums/record-counts 전부 수신 ∧ missing interval ∅ ∧ revision·cutoff·
   period boundary present — §19 line 443; set-completeness, ∅ 구조 가드), (ii) `statement_sources_independent(...)`
   (**broker API + broker statement, 또는 broker + custodian이 one book/parser/administrator/transport 공유 시 independent
   path 아님** — §19 line 445·PTF-INV-014 verbatim; 구조: 두 source의 shared-dependency set disjoint일 때만 corroborate —
   **명제 상이: recon `classify_field`의 per-field independence_class 소비가 아니라 statement-SOURCE grain의 PTF-local
   구조 property**, §3.5), (iii) `absence_is_negative_evidence_only(...)`(**line item 부재는 exact coverage·correction
   semantics·source capability가 positively support할 때만 negative evidence** — §19 line 448 verbatim; 그 외 absence ⇒
   UNKNOWN). **`FINAL`/signed/independently-delivered statement도 approved proof recipe 밖에서는 unconditional truth
   아님**(§19 line 448). **+Security(credential/route/bypass) 잔여 명시.**
9. **finality-proof 구조 + finality-grants-nothing 불변식**(§4.7/§5.7, core substrate — ADR §11·§10 line 312·PTF-INV-
   005/009): (i) `finality_proof_class_specific(...)`(proof는 exact obligation identity·version·leg·scope·amount·
   account·currency·value-date·generation·finality-class + **"what it does not prove"**를 bind — §11 line 320–326;
   one global `SETTLED`/`CLOSED`/confidence-score/statement-flag/operator-decision는 per-field proof를 대체 못 함 —
   PTF-INV-005), (ii) `finality_proof_non_transferable(...)`(one leg/account/currency/value-date/source-revision/
   finality-class의 proof는 다른 것에 patch·reuse 불가 — §11 line 328 verbatim "non-transferable and non-unionable"),
   (iii) **`post_trade_consequence_all_false(...)`**(어떤 lifecycle state도·`FINALITY_PROVEN`도 capacity release·
   available cash·legal title·permission을 create하지 않는다 — §10 line 312 verbatim·PTF-INV-009; all-false
   `AllFalsePostTradeConsequence` — 어떤 True도 unconstructable, rcl `AllFalseAuthority`·nontrade `AllFalseNonTrade
   Authority` 동형). **finality proves the LEG, not the CONSEQUENCE** — 본 ADR의 최핵심 안전 성질.
10. **PTF ↔ 12+ 생산자 형제 경계(중심 아키텍처)**: PTF는 **sibling edge 0건**을 유지한다(§0.4b/§3.4; nontrade #21·
    replacement #18 동형). PTF는 (i) obligation-set-completeness/finality-orthogonality/no-netting/no-double-use/
    statement-coverage/idempotency **결정을 생산**하고 미래 rcl-capacity-commit/are-risk-projection/currentness-egress-
    fence 런타임이 소비하며, (ii) rcl `FINAL_QUANTITY_PROOF`/`credible_union_capacity`/`CapacityState`·are `SETTLEMENT_
    CASH_CURRENCY`/`MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN`/`BenefitKind.NETTING`·recon `classify_field`/`Field
    ConfidenceClass`/`POST_TRADE_OBLIGATION_IDENTITY_AND_VERSION`·brokercap `fqp_adequate`/`POSITIONS_BALANCES_MARGIN`·
    nontrade `NonTradeEventWorkflowState`(APPLIED_LOCAL/RECONCILED)·egress `EgressAdmission`/`credential_route_authority_
    disjoint`·orthostate `KnowledgeState`·authority/liveauth `no_automatic_rearm`·sbr `restore_worst_credible_union`·
    time `freshness_verdict`를 **주입 좌표/produced-token으로 소비**한다. **`tos.canonical`·`tos.ordering`(둘 다 core)만
    import**한다(§0.3). **PROMOTE 0건. sibling edge 0건. `CapacityVector`/`ProjectedCell`/`FieldConfidence` REUSE
    미채택**(§0.4c 검토 후 기각).
11. **fail-closed 규율 + named both-ways canary**(§4): 미포함 leg ⇒ incomplete; **finality dimension 상호 함의 시도 ⇒
    False**; missing line item ⇒ UNKNOWN(favorable-zero 아님); netting proof 부재 ⇒ gross(no netting); collateral
    double-use ⇒ 보존 위반·False; event-state로 obligation-finality 주장 ⇒ 구조적 부재(non-implication); statement
    coverage 미완 ⇒ incomplete; common-mode source ⇒ not-independent; finality proof cross-leg reuse ⇒ False; capacity-
    release-on-finality ⇒ **판정 자체가 구조적 부재**(PTF에 release 필드·술어 없음 — rcl-only §1 line 21); **빈 leg set·
    빈 required set·None magnitude·None dimension·빈 coverage set ⇒ 보수적 BLOCK/QUARANTINED/TRAPPED**(∅-공허, §4.8 —
    **양방향** 명시). 각 가드에 both-ways canary. **truthy-sentinel 극성 분기(시리즈 규율 1)**: `PostTradeDisposition`/
    `ObligationCommitOutcome`는 **identity 게이트**(`is POST_TRADE_ADMISSIBLE`/`is COMMITTED_ONCE`); **양극성 bool|None
    (안전값=True)은 `is True`만**; **음극성 bool|None(안전값=False)은 `is False`만**(`is not True` 금지); **완료/허용
    결과는 잔여 fall-through가 아니라 양성 conjunction identity 증명으로만 도달**(#16 CRITICAL 교훈).
12. **단일 disposition 생산 술어**(§5.8, **C1-style — #21 §5.5 상속**): `post_trade_disposition(...) -> PostTrade
    Disposition`. §4.8 ∅-공허 표의 **모든 행이 이 술어의 반환값으로 재매핑**되어 "빈 입력은 별도 처리에 위임"이라는
    미결 위임이 사라진다. 5-member 전순서 우선순위(`POST_TRADE_CONFLICTED` > `POST_TRADE_QUARANTINED_UNKNOWN` >
    `POST_TRADE_TRAPPED` > `POST_TRADE_BLOCK_NEW_RISK` > `POST_TRADE_ADMISSIBLE`)로 결정적이며, `POST_TRADE_ADMISSIBLE`
    은 잔여 fall-through가 아니라 **양성 conjunction identity 증명**으로만 도달한다(§5.8).
13. **property-test 하네스 타깃**(§7, §1 분류 정렬) + import-closure 검증(§7.1, **allowlist 형식**) + run manifest
    7항목(§7.2) + fixture clean-vs-illegal 정합(#8 교훈) + seam cross-check(test-only, §3.4) + **hypothesis 전략에
    forgery/∅/finality-implication/double-use 케이스 명시 포함**(§7).
14. **bounds 주입 계약 + Phase-0 이관**(§8): PTF decision 구조에는 numeric bound 부재(전부 enum·boolean·집합 논리·
    주입 `CanonicalDecimal`); ADR §29 Q9/Q10이 요하는 timing/age bound는 **VP-002에 6 `B_*` + 5 `MAX_*` + 8 currentness
    identity slot = 19 PTF-전용 키 실재·null/TBD**(§8.1 실측)이며 **confirmed candidate 신규 키 0건**; per-source/per-
    broker 수치는 Broker/Clearing/Custodian/Banking Capability Profile INSTANCE. 값 승인은 Bounds-Approver 게이트.

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §30 line 722 "ADR-002-030
  remains ``Proposed`` until all of the following are satisfied"·line 738 "This ADR authorizes architecture and
  implementation planning only. It does not authorize live operation, capacity release, external economic
  transmission, scope promotion, production use, or automatic re-arm"·§27 line 633 "Written cases define obligations
  only. They are not completed evidence." **닫는 PTF-EV = 0건.**
- **capacity 산술(commit/consume/release·transfer·quarantine·aggregate envelope·credible union)을 저작하지 않는다.**
  그것은 **rcl(#5, ADR-002-002/012)이 이미 소유·구현**했다 — `credible_union_capacity`·`CapacityState`·`TransitionCause.
  {FINAL_QUANTITY_PROOF,RECOGNIZED_EXTERNAL_CHANGE}`·`CommandType.{APPLY_FINAL_QUANTITY_PROOF,RELEASE_RESERVATION,
  CREATE_EXTERNAL_QUARANTINE,MARK_TRAPPED_EXPOSURE}`. ADR §1 line 21 verbatim "The Risk Capacity Ledger remains the
  sole capacity mutation and serialization authority. An obligation compiler, Reconciliation Service, PTOL, position
  or cash projection, statement processor, evidence service, recovery workflow, operator, or finality proof SHALL NOT
  create, change, quarantine, transfer, remap, or release capacity"·PTF-INV-008·§21. PTF는 obligation-set completeness·
  no-favorable-default를 판정하고 rcl이 capacity를 commit/transfer/quarantine한다(§0.4d). **obligation closure는
  capacity를 release가 아니라 transfer**한다(PTF-INV-009 — rcl 소유).
- **aggregate-risk 투영·Adverse Scenario·credible-state-space risk를 산출하지 않는다.** 그것은 **are(#13, ADR-002-021)
  가 이미 소유·구현**했다 — `worst_intermediate_risk`·`SETTLEMENT_CASH_CURRENCY`·`LEVERAGE_MARGIN_COLLATERAL`·
  `OPTION_GREEKS_EXERCISE_ASSIGNMENT`·`MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN`·`MISSING_ACK_RECEIPT_AMBIGUITY`·
  `BenefitKind.NETTING`. ADR §21 line 468 "The ... Aggregate Risk State Snapshot SHALL include every ... post-trade
  obligation"의 **risk 수치 = are 주입**(§0.4d). PTF는 obligation-set 열거 완전성·no-favorable-default만 소유한다.
  **are의 netting BENEFIT(aggregate-risk 축)과 PTF의 obligation-leg no-netting(obligation 축)은 별개 명제**(§3.5).
- **event·transformation identity·event workflow lifecycle을 저작하지 않는다.** 그것은 **nontrade(#21, ADR-002-010)이
  이미 소유·구현**했고 **상호 명시 이연**했다 — ADR §17 line 414 verbatim "ADR-002-010 owns lifecycle and non-trade
  event identity and transformation. This ADR owns the resulting obligation legs and their finality." nontrade
  `NonTradeEventClass`·`NonTradeEventWorkflowState`·`CredibleTransitionLegKind`·`SplitTransformationKind`·`correction_
  reversal_idempotent`. PTF는 nontrade event-state를 **주입 토큰**으로 소비하고 그로부터의 **obligation leg·finality**
  만 소유한다(§3.5 — nontrade "leg"[transition-envelope 완전성 좌표] ≠ PTF "leg"[obligation record with finality],
  명제 상이).
- **per-field evidence 신뢰도 분류·reconciliation confidence를 재저작하지 않는다.** 그것은 **recon(#9, ADR-002-006)이
  이미 소유·구현**했다 — `classify_field`·`FieldConfidenceClass`·`POST_TRADE_OBLIGATION_IDENTITY_AND_VERSION`·
  `SETTLEMENT_CASH_AVAILABILITY_COLLATERAL_ELIGIBILITY`·common-mode RECON-EV-001. PTF-INV-005 "confidence score ...
  cannot replace exact per-field proof"이 **confidence(recon) ≠ finality(PTF)** 명제 상이를 고정한다. PTF는 field-
  confidence를 **주입 소비**하고 그 위에 finality-proof binding을 얹는다.
- **broker·clearing·custodian·banking capability·FQP adequacy를 판정하지 않는다.** 그것은 **brokercap(#10, ADR-002-018)
  이 이미 소유·구현**했다 — `fqp_adequate`·`broker_capability_sufficient`·`CapabilityDimension`·`CapabilityStatus`.
  `+Broker` 12/12는 brokercap **주입**으로 discharge하며 PTF는 broker-agnostic이다. settlement/custodian/statement-
  coverage capability dimension은 brokercap에 부재 ⇒ Phase-0 open question(§0.4·§9.2).
- **external economic instruction transmission·final egress·credential/route를 저작하지 않는다.** 그것은 **egress(#22,
  ADR-002-013)이 이미 소유·구현**했다 — `EgressAdmission`·`credential_route_authority_disjoint`·`capability_and_permit_
  single_use`. ADR §1 line 31·PTF-INV-016 "PTOL ... SHALL NOT hold a usable external-economic credential and route".
  PTF는 settlement/transfer/election instruction을 **구성·전송하지 않는다**(구조적 부재 — §4.4; `AllFalsePostTrade
  Consequence.grants_permission=False` + credential/route/send 필드 부재). §16/§22 egress coupling은 EV-L2/3 런타임.
- **order/transmission/knowledge/capacity 상태 축·obligation-lifecycle과의 orthogonality 붕괴를 재저작하지 않는다.**
  orthostate(#8, ADR-002-005)가 `KnowledgeState`·`IntentState`·`BrokerOrderState`를 소유한다. PTF `PostTradeObligation
  LifecycleState`(obligation 축)는 orthostate 5 축과 **별개 6번째 축**이며(§10 line 305) 주입 좌표로 소비한다(§2.2-5
  비붕괴). PTF `FINALITY_PROVEN` ≠ orthostate `KnowledgeState.RECONCILED` ≠ nontrade `RECONCILED`.
- **currentness vector·active-generation fencing·authority/re-arm·recovery inventory·evidence custody/replay를 저작하지
  않는다.** §22 currentness = **cur(ADR-002-024, committed `1390ef9d`)** — cur이 `DimensionKey.POST_TRADE`(`cur/
  vocabulary.py:146`)·`ProofResult`(CURRENT/RESTRICTED/UNKNOWN, `:96–98`)·`CurrentnessAdmission`(ADMIT/DENY, `:113–114`)
  로 post-trade currentness 차원을 **이미 소유**하며 PTF는 currentness identity 좌표를 주입한다(§3.5 §22); §22 authority/
  re-arm = authority/liveauth(`no_automatic_rearm`); §24 recovery = sbr(`restore_worst_credible_union`); §24 evidence/
  replay = ADR-002-016 evidence 런타임; §22 time = time. 전부 **주입 소비**하며 본 Phase-1 미저작(EV-L2/3 잔여).
- **settlement completion·cash availability·borrow discharge·custody chain·legal-title finality의 PROOF을 저작하지
  않는다.** §14 settlement/cash(PTF-EV-003 `EV-L2/3`)·§16 borrow(PTF-EV-005 `EV-L2/3`)·§18 custody/transfer(PTF-EV-007
  `EV-L2/3+Sec`)은 **not-Phase-1**이다 — 본 Phase-1은 cash-kind·margin-state·borrow-lifecycle **어휘(substrate)**만
  두고 실제 availability/discharge/title PROOF은 broker/integrated 단계(EV-L2/3+Broker) 잔여로 명시 이연한다(§1·§6.4).
- **break-to-restrict propagation·RCL coupling·generation fencing runtime을 저작하지 않는다.** §20 breaks(PTF-EV-009
  `EV-L2/3+Sec`)·§21 RCL coupling·§22 generation fence(PTF-EV-010 `EV-L2/3+Sec`)·§23 partition(PTF-EV-011 `EV-L3+Sec`)
  는 **not-Phase-1**이다 — 본 Phase-1은 append-only-no-overwrite·obligation-set-enumeration **substrate**만 두고
  break-to-RCL-restrict·PTOL-to-RCL ordered-transfer runtime은 EV-L2/3 잔여로 명시 이연한다(§6.4).
- **numeric obligation/finality/statement/settlement bound를 승인하지 않는다.** ADR §29 Q9/Q10(line 711–712)은 Open
  Question이다. 전부 주입 `CanonicalDecimal`로 담고 **어떤 숫자도 하드코딩하지 않는다**(CLAUDE.md). 값 부재 ⇒
  fail-closed. 값 승인은 Bounds-Approver 게이트(§8·§9.2).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

신규 PTF 패키지 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도 import하지 않는다**
  — post-trade 결정 규칙은 StrEnum·boolean·집합 논리이고 수치는 `CanonicalDecimal` 산술(비교·`is_finite`·scale-
  normalize·비음수 검사·보존 합)뿐이며, 모든 obligation/finality/statement/settlement bound·broker limit·aggregate-risk
  값은 주입 파라미터이고 YAML 파싱은 하네스(설계 #3) 소관이다(closure 최소화 — #5–#22 §0.3 동형).
- tos 자기 자신: `tos.canonical`(`FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`classify_record_pair`·
  `RecordPairKind`·`ArtifactStatus`·`CanonicalDecimal`), `tos.ordering`(obligation/finality/statement/correction
  append-only 순서 — §3.2), 자기 자신 모듈. **canonical/ordering 외 모든 현재·미래 tos 형제(현재 committed 25개:
  canonical·capsule·evidence·time·ordering·dsl·rcl·authority·liveauth·orthostate·recon·brokercap·spg·protective·are·
  ioc·iap·sbr·venue·afg·hag·egress·replacement·nontrade·**cur**)를 import하지 않는다**(default-deny — 규칙을 열거가
  아닌 "canonical·ordering 외 전부 금지"로 서술; produced-token·주입 좌표로만 참조 — §3.4/§3.5). PTF는 **26번째
  패키지**다(**v1.1 정정**: cur[#23]은 v1.0 저작 후 커밋 `1390ef9d` — 이제 committed 형제이나 import하지 않는다;
  sibling edge 0). **PROMOTE 0건. sibling edge 0건.**
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이 `shared.config.secrets`
  (→ `os.environ`)를 무조건 전이 import한다. PTF 패키지는 어떤 `shared.*`도 필요로 하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`·`shared.kis`·`shared.streaming`·`shared.llm`·`shared.storage`·
  `shared.backtest`·`services.*`·`cli.*`(`.importlinter` forbidden set).
- **firewall 구조 확인(실측 — #11/#16/#18/#21 §0.3 상속)**: `.importlinter`는 `[importlinter:contract:tos-operational-
  firewall]` type=forbidden·source_modules=`tos` 단일 계약이며 `layered`가 아니다 — intra-tos sibling→sibling edge는
  구조적으로 금지되지 않고 설계 #1 §3.2 "자기 자신 `tos.*`" 허용 조항이 커버한다. **신규 PTF 패키지는 firewall 도구
  무수정 자동 포섭**된다. 본 문서는 그럼에도 **sibling edge 0건**을 **설계 규율**로 유지한다(§0.4b).
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(**allowlist 형식** — `import` 후 `sys.modules`의
  top-level `tos.*` ⊆ {`tos.canonical`, `tos.ordering`, 자기 자신} assert + `shared.config`·`os.environ`·numpy/pandas/
  yaml 부재 assert). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter`
  layer-② 전이)와 함께 green이어야 §0.3 선언이 능동 성립.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/posttrade/`.** register domain("**Post-Trade Economic Obligations and
Finality**")·prefix `PTF`(`PTF-EV`/`PTF-AC`/`PTF-INV`)·ADR 제목 변별 토큰 "**Post-Trade**"를 명명 근거로 삼는다. 명명
대안 비교(#18 §0.4a·#21 §0.4a 형식):

- **`tos.ptf`(register prefix 직결)(고려·차점)**: `PTF-EV` prefix와 직접 일치하고 대부분 형제가 register 두문자
  (rcl/spg/are/afg/ioc/iap/sbr)이므로 정합적이다. 그러나 "PTF"는 **cryptic**(portfolio? post-trade-fee?)하며, #18이
  `pr`(pull request/public relations)을, #21이 `nt`(Windows NT)를 정확히 "cryptic" 이유로 차점 처리한 선례와 방향이
  같다 — semantic 명료성은 `posttrade`가 우월하다. **운영자 치환 가능**(load-bearing 아님).
- **`tos.obligation`(기각·generic)**: "obligation"은 generic하고 core 개념 하나(Economic Obligation)만 명명해 finality/
  statement/settlement/account-state governance 전체(§10–§24)를 좁게 표현한다.
- **`tos.settlement`(기각·좁음)**: settlement(§14)만 명명해 fee/margin/collateral/borrow/custody/statement를 누락한
  인상을 준다 — 본 ADR은 settlement가 여러 obligation class 중 하나일 뿐이다.
- **`tos.ptol`(기각·좁음)**: PTOL(ledger)은 serialization 컴포넌트 하나이며 policy/proof/statement/coupling 전체가 아니다.
- **선택 `tos.posttrade`**: **ADR 변별 토큰 "Post-Trade" + register domain 직접 명명**, non-cryptic, 명사형. #18/#21이
  register prefix(`pr`/`nt`)를 semantic 토큰(`replacement`/`nontrade`)으로 교체한 것과 **동형 판정** — semantic 토큰
  우선, 그리고 `nontrade`와 **정확히 평행한 hyphenated-ADR-token 연접**(Non-Trade→nontrade / Post-Trade→posttrade)으로
  최인접 형제와의 명명 일관성이 강하다. terse 관행보다 다소 길지만 orthostate/brokercap/liveauth/replacement/nontrade
  선례로 수용 가능. **naming은 load-bearing이 아니다**(설계 #1 line 164) — 운영자가 `tos.ptf`로 치환 가능. 실측:
  `tos/src/tos/posttrade`·`tos/src/tos/ptf` 부재(ls exit 1 — 충돌 없음). 내부 module(`_base.py`·`vocabulary.py`·
  `records.py`·`predicates.py`·`state.py`)은 nontrade/recon/venue 선례 동형.

**(b) posttrade = produced-token producer, sibling edge 0건, capacity-non-mutating (중심 결정 — nontrade #21·
replacement #18 동형, 코드 실측).** PTF는 미래 소비자(rcl capacity-commit·are risk-projection·currentness-egress-fence
런타임)의 **상류**다 — obligation-set-completeness/finality-orthogonality/no-netting/no-double-use/statement-coverage/
idempotency **결정을 생산**하고, 상류 형제(rcl·are·recon·brokercap·nontrade·egress·orthostate·authority·liveauth·sbr·
time)가 생산한 값을 **주입 소비**한다. seam 대안 비교(#21 §0.4b 형식):

- **대안 A — PTF가 소비자(rcl)를 import해 capacity release/transfer를 직접 커밋**: **기각**. ADR §1 line 21·PTF-INV-008
  "only the RCL may perform the transition." PTF는 obligation-set·finality-proof-verdict를 **생산**할 뿐 capacity를
  mutate하지 않는다. **결정적**: `FINALITY_PROVEN`조차 release를 만들지 못한다(PTF-INV-009 "It does not release usage
  while any resulting economic effect or uncertainty remains"; §21 line 492 "It may transfer consumption rather than
  release it"). ⇒ rcl import 불요.
- **대안 B — 소비자가 PTF를 import**: rcl/are/egress가 PTF를 직접 호출. **기각**: 이 형제들은 **이미 비준·구현**됐고
  post-trade 조건을 주입 슬롯(rcl `TransitionCause.FINAL_QUANTITY_PROOF`·are `SETTLEMENT_CASH_CURRENCY` dimension·
  recon `POST_TRADE_OBLIGATION_IDENTITY_AND_VERSION` field·nontrade event-state)으로 이미 봉인했다. ratified 패키지를
  PTF 의존으로 바꾸면 침습이며 acyclic이 깨진다.
- **선택 — decoupled, plain-token producer(edge 0건)**: PTF은 자신의 어휘·obligation 모델·결정 술어를 저작하고, 출력은
  plain `bool`/StrEnum(`PostTradeDisposition`·`ObligationCommitOutcome`)으로 미래 소비자 signature와 타입 일치; 소비
  방향도 rcl/are/recon/brokercap/nontrade/egress/orthostate 산출을 **주입 `bool|None`/StrEnum/`CanonicalDecimal`**로
  소비하고 형제를 import하지 않는다. 근거: (i) **최인접 상류 nontrade #21·replacement #18이 정확히 이 형태**이며 본
  ADR과 소유권이 인접하다 — 일관성. (ii) ADR §1 line 21이 PTF을 capacity-non-mutating으로 봉인. (iii) edge 0·cycle
  원천 차단. (iv) **compose seam-sealing**: 타입 일치 + fail-closed 정합, **test-only** 모듈이 PTF·(각 상대)를 둘 다
  import해 대조(테스트 import는 §7.1 package closure 불계상).

**(c) `CapacityVector`/`ProjectedCell`/`FieldConfidence` REUSE(edge-1) 검토 후 기각 — edge 0 (핵심 아키텍처).**
obligation leg magnitude·finality dimension·per-field confidence가 rcl `CapacityVector`(`vector.py`)·are `ProjectedCell`
(`records.py`)·recon `FieldConfidence`(`records.py`)를 REUSE해야 하는지 검토:

- **REUSE 찬성 근거**: obligation leg가 aggregate risk로 흐르고(§21) per-field confidence가 finality의 입력(§11)이므로,
  PTF가 leg를 `ProjectedCell`/`FieldConfidence`로 조립해 넘긴다고 볼 수 있다.
- **기각 근거(edge 0)**: (i) **PTF의 L1-decidable 핵심은 vector/cell/confidence 산술이 아니다** — finality-dimension
  non-implication(10×10 관계)·fill-commit idempotency(`classify_record_pair`)·leg-set completeness(set 논리)·
  no-favorable-default(구조적 magnitude 병존·proof-token 부재)·collateral 보존(합 ≤ available)·statement coverage
  completeness(set)이며, worst-intermediate-risk 투영·per-field confidence 분류는 are/recon 소유이고 PTF는 그 verdict/
  class를 **주입 소비**한다. L1 결정에 rcl `CapacityVector`·are `ProjectedCell`·recon `FieldConfidence` **타입 자체가
  불필요**하다. (ii) **are/recon은 이미 post-trade 좌표를 소유**한다 — are `SETTLEMENT_CASH_CURRENCY`·recon `POST_TRADE_
  OBLIGATION_IDENTITY_AND_VERSION`·`SETTLEMENT_CASH_AVAILABILITY_COLLATERAL_ELIGIBILITY` — PTF가 그 타입을 REUSE하면
  namespace/좌표 충돌(§2.2-5). (iii) **rcl `credible_union_capacity`가 empty-fail-closed·no-last-write-wins를 이미
  구현** — PTF가 union 산술을 재저작하면 권위 중복. (iv) **최인접 상류 nontrade #21·replacement #18이 edge 0**. ⇒
  **edge 0·PROMOTE 0·sibling edge 0**. **운영자 판단 지점(§10.3-1)**: (a) 타입 REUSE(edge-1) vs **(b) plain-type
  obligation-record producer(edge-0, 채택)** — 미래 런타임에서 PTF이 cell/vector를 직접 조립해야 하면 (a)로 승격 가능
  하나 Phase-1은 (b)로 충분하다. PTF의 leg magnitude는 `ObligationLegDirection→CanonicalDecimal|None` 매핑 value로
  로컬 표현한다(are/rcl/recon 좌표 미충돌).

**(d) obligation-set "old+new 동시 계상·no-favorable-netting" ↔ rcl/are 이중 계상 정합 (핵심 설계 판정 — #21 §0.4d
동형).** 판정:

- **이중 계상·gross 병존은 결함이 아니라 보수적 요구다.** obligation 중 receivable(credit)와 payable(debit)는 enforceable
  netting이 positively 증명되기 전까지 **둘 다 gross**로 계상되며(PTF-INV-007·§9 line 279 "the missing counterleg
  remains explicit and the greatest credible adverse union is used"), worst credible state는 **둘 다 exposure**를
  포함한다. 순진한 회계는 receivable를 payable로 **netting**(상쇄)하지만, obligation 축에서는 **netting 금지** — 오직
  exact enforceable netting proof(주입)일 때만.
- **정합 메커니즘 — no-netting을 구조적으로 파생(edge-0 유지, #21 §0.4d 동형)**: obligation leg는 direction별 **주입
  `CanonicalDecimal|None` magnitude**를 담는다. **netting-absent는 flag가 아니라 파생 성질**이다: `netting_requires_
  positive_proof`는 receivable·payable가 **둘 다 present(not None)·비음수로 gross 병존** ∧ same scope ∧ **injected
  enforceable-netting proof token present**일 때만 netting valid; 하나라도 부재 ⇒ 둘 다 gross(netting 불가). caller가
  flag로 netting을 위조 불가. **PTF의 소유**: (i) obligation-set이 **모든 credible leg 포함**(`obligation_leg_set_
  complete`), (ii) **구조적 no-favorable-default**(missing counterleg adverse·missing line item UNKNOWN·netting proof
  요구). **PTF이 소유하지 않는 것**: 합산 산술·hard-envelope 비교(rcl `credible_union_capacity`)·aggregate-risk 투영
  (are `worst_intermediate_risk`)·netting **benefit** 판정(are `BenefitKind.NETTING` — aggregate-risk 축). "conservatively
  account all credible effects"(§1 line 27)는 **구조적으로 gross-병존된(netting-불가) obligation-set이 rcl union·are
  risk로 흐름**을 의미한다 — PTF은 completeness+구조적-no-favorable-default를 강제하고 rcl/are가 합산·risk·benefit을
  강제한다. **좌표: PTF leg magnitude(obligation 축) → rcl이 dimension별 union·commit·are가 risk 투영/netting benefit**
  (§0.4c 좌표 충돌 회피로 PTF은 `CapacityVector`/`ProjectedCell` 타입 미REUSE).
- **좌표 비붕괴**: PTF `ObligationLegDirection`(obligation 축) ≠ are `RiskDimensionKind`/`BenefitKind`(aggregate-risk
  축) ≠ rcl `CapacityVector.dimension_id`(경제 capacity 축) ≠ nontrade `CredibleTransitionLegKind`(transition 축).
  **3중 netting 명제 분리**: nontrade transition-envelope no-netting(old/new instrument exposure) ≠ PTF obligation-leg
  no-netting(receivable/payable gross) ≠ are aggregate-risk netting-benefit(proof 요구). 토큰 겹칠 수 있으나 별개 타입.

**(e) fill-commit-idempotency 명제 = PTF 고유, iap/rcl/nontrade와 별개 (phantom-edge 방지 — defect-class #3).**
PTF-EV-001의 fill-to-obligation commit idempotency가 형제 idempotency를 소비하는지 판정:

- **iap 명제(실측)**: `ConsumptionOutcome.IDEMPOTENT_REPLAY`(`iap/vocabulary.py:165`) = authorization-token single-use
  consumption. **rcl 명제**: `ApplyReason.IDEMPOTENT_REPLAY`(`rcl/vocabulary.py:115`) = capacity-command idempotency.
  **nontrade 명제**: `CorrectionReversalOutcome.IDEMPOTENT_REPLAY`(`nontrade/vocabulary.py:381`) = correction/reversal
  economic-event 재적용 무해성.
- **PTF 명제**: PTF-EV-001(§12 line 336·PTF-AC-001) = **fill-to-obligation commit 재적용 무해성**(동일 fill·late fill을
  2회+ commit해도 obligation effect가 idempotent·generation 정합·capacity 보존).
- **판정**: **명제가 다르다**(authorization-consumption ≠ capacity-command ≠ event-application ≠ fill-obligation-commit).
  ⇒ PTF은 형제를 **소비하지 않고** 자신의 `obligation_commit_idempotent`를 **canonical `classify_record_pair`에 앵커**
  한다. iap·rcl·nontrade·PTF는 **canonical `classify_record_pair` 원시의 네 독립 하류**이며 상호 import하지 않는다 —
  구조 동형(isomorphic)이나 좌표 상이. 이 판정이 phantom edge(형제 import)를 차단한다.

**(f) `id=f(digest)` 미채택 (canonical REUSE).** `EconomicObligationRecord`·`PostTradeFinalityProof`·`StatementCoverage
Manifest`는 **obligation/proof/statement identity**(source event id·version·supersedes ref·idempotency key §9 line
268·§11 line 320)를 가지며, 위조·contradictory obligation·double-commit fill 탐지에 `classify_record_pair`(**same
primary id·diff bytes ⇒ `CRITICAL_CONFLICT`** / **same idempotency key·diff bytes ⇒ `DIVERGENT_EMISSION`**)를 쓰려면
id⊥digest여야 한다(#4–#21 §3.1 동형). ⇒ `IndependentIdArtifact` 채택, `IdDerivedArtifact`(capsule content-addressed)
미채택. 각 obligation version/correction은 immutable append-only이며 정당한 정정(§11 line 330 "A later correction
supersedes the proof, advances generation ... it does not erase history"·§20 line 460 "SHALL NOT destructively
rewrite")은 **새 versioned record**이지 in-place mutation이 아니다. **`tos.posttrade._base`**: canonical 원시타입의 thin
re-export + all-false `AllFalsePostTradeConsequence`(finality-grants-nothing §10 line 312)의 로컬 fresh 정의(rcl
`AllFalseAuthority`·nontrade `AllFalseNonTradeAuthority` 동형).

**(g) 앵커 규약 — PTF-INV/PTF-EV/PTF-AC/§-clause/SAFE 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-030은 `PTF-INV-
001..018`(§6, 18종)·`PTF-AC-001..012`(§27, 12종)·`PTF-EV-001..012`(register 12행)를 정의한다. ⇒ 본 계약은 모델 불변식·
술어를 **`PTF-INV-###` / `PTF-AC-###` / `PTF-EV-###` / §-clause / `SAFE-###`(§28)**에 앵커하고 **새 INV/AC/EV 시리즈를
창작하지 않는다**. #6/#10/#16/#19 동형(자체 INV 보유).

---

## 1. 범위 매핑 — ADR-002-030 조항별 EV-L1 도달성 (닫는 PTF-EV 0건)

> **판정 규율**: 각 §-clause를 **core(L1 슬라이스 저작) / substrate(predicate-only·EV 미주장) / not-Phase-1(형제 소유
> 또는 EV-L2/3+Broker[+Security] 잔여)** 3분류한다. **register 최소 레벨의 L1 슬라이스**를 가진 PTF-EV만 core 후보다
> (001·002·004·006·008). **닫는 PTF-EV = 0건**(L1 슬라이스 저작 ≠ EV closure — 전 12행 `+Broker` 잔여, 6행 `+Security`
> 잔여). **staged-EV 정직 분리(defect-class #9)**: core 5행도 `EV-L1/2/3` 중 **L1 부분만** 저작하고 `/2`·`/3`·`+Broker`·
> (008)`+Security` 통합 잔여를 명시한다. **over-claim 금지.**

| ADR §-clause (normative 문장 단위) | 분류 | PTF-EV / 앵커 | Phase-1 저작 대상 |
|---|---|---|---|
| §1 line 15–33 Decision (obligation record·PTOL·RCL sole authority·orthogonal finality·UNKNOWN restrictive·no headroom·generation fence·egress·no-substitute) | core+substrate | PTF-INV-001..018·전 PTF-EV | 어휘·모델·중앙 술어(§2·§4·§5) |
| §2 Context / §3 Decision Drivers (10 driver, line 60–69) | 무저작(맥락) | — | **무소유 0건** — driver는 §4 불변식으로 실현 |
| §4 Scope/Non-Scope (governs 8·does-not-decide 11) | 경계 | — | §0.2 NO 목록으로 실현 |
| §5 Definitions (5.1–5.10, 10 def) | core substrate | 어휘 앵커 | `EconomicObligationRecord`·`PostTradeFinalityProof`·`StatementCoverageManifest` 등(§2.2) |
| §6 PTF-INV-001..018 (18 불변식) | core | 전 PTF-EV | §4 불변식으로 전수 실현(§4.0 표) |
| §7 Authority Ownership (13 row, line 228–240) | 경계 | — | §3.5 소유권 분할표 |
| §8 Post-Trade Finality Policy (binds 7) | substrate | — | policy identity 좌표(spg/VP 주입, §8.1); activation-grants-nothing(§8 line 260) |
| §9 Obligation Identity + Exact Leg (record contains 8·leg §5.3 8 direction) | **core** | PTF-EV-001 substrate | `EconomicObligationRecord`·`ObligationLeg`·`obligation_leg_set_complete`·`missing_counterleg_is_adverse`(§5.1/§5.3) |
| §10 Obligation Lifecycle (8+4=12 state·orthogonal to 6) | **core** | PTF-EV-001 | `PostTradeObligationLifecycleState`·`post_trade_consequence_all_false`(§5.7·§2.2-2) |
| §11 Field-Specific Finality Proof (binds 7·non-transferable) | **core** | PTF-EV-001 substrate | `PostTradeFinalityProof`·`finality_proof_class_specific`·`finality_proof_non_transferable`(§5.7) |
| §12 Fills / Execution-Finality Boundary (FQP does-not-prove 6·idempotent commit·late fill) | **core (L1 슬라이스)** | **PTF-EV-001** (impl-plan line 221 명시 지목) | `finality_dimensions_orthogonal`·`obligation_commit_idempotent`(§5.1/§5.2) |
| §13 Fees/Tax/Interest/Financing (9 monetary type·absence≠zero·no favorable offset·corrections) | **core (L1 슬라이스)** | **PTF-EV-002** | `monetary_leg_conservative`·`netting_requires_positive_proof`(§5.3) |
| §14 Settlement/Cash Availability (9 cash distinction) | substrate | PTF-EV-003 `EV-L2/3` (not-L1) | `CashKind`(6) 어휘 + `cash_kind_matches_requirement`(§5.4) — **availability PROOF은 L2/3 잔여** |
| §15 Margin/Collateral/Encumbrance (8 state·double-use) | **core (L1 슬라이스)** | **PTF-EV-004** | `MarginCollateralState`·`collateral_no_double_use`·`margin_collateral_states_distinct`(§5.4) |
| §16 Borrow/Recall/Return/Buy-In (8 distinction) | substrate | PTF-EV-005 `EV-L2/3` (not-L1) | 어휘 substrate만 — **discharge PROOF은 L2/3 잔여**(§6.4) |
| §17 Exercise/Assignment/Delivery/CA Obligations (9 leg·event-state≠final) | **core (L1 슬라이스)** | **PTF-EV-006** | `obligation_legs_from_event_complete`·`event_state_not_obligation_finality`(§5.5) — **nontrade 경계** |
| §18 Custody/Transfer/Legal-Title (7 state) | not-Phase-1 | PTF-EV-007 `EV-L2/3+Sec` | 어휘 substrate만 — chain/title PROOF·+Security 잔여 |
| §19 Broker/Clearing/Custodian Statements (manifest 7·preliminary/final·common-mode) | **core (L1 슬라이스·+Sec 잔여)** | **PTF-EV-008** | `StatementCoverageManifest`·`statement_coverage_complete`·`statement_sources_independent`·`absence_is_negative_evidence_only`(§5.6) |
| §20 Breaks/Busts/Corrections/Reversals/Restatements | substrate | PTF-EV-009 `EV-L2/3+Sec` (not-L1) | append-only-no-overwrite substrate만 — break-to-restrict runtime·+Security 잔여 |
| §21 Aggregate Risk / RCL Capacity Coupling (safe transition 7 step) | not-Phase-1 | PTF-EV-010 `EV-L2/3+Sec` | obligation-set 열거만 — RCL ordered-transfer coupling·are risk 잔여(§3.5) |
| §22 Active Currentness/Authority/Final Egress (7 currentness dimension) | not-Phase-1 | PTF-EV-010 | currentness identity 좌표(VP 주입, §8.1) — fencing runtime·egress 잔여(cur/egress 소유) |
| §23 Failure/Partition/Security/Common-Mode (10 row) | not-Phase-1 | PTF-EV-011 `EV-L3+Sec` | — 전부 런타임·+Security 잔여 |
| §24 Evidence/Recovery/Non-Revival | substrate | PTF-EV-012 `EV-L2/3+Sec` | frozen record 재구성 substrate만 — replay ENGINE·recovery·+Security 잔여 |
| §25 Rejected Alternatives (12) / §26 Consequences | 무저작 | — | §4 불변식이 12 rejected를 구조적으로 실현(§4.9) |
| §27 PTF-AC-001..012 (12) / §28 Traceability / §29 Open Q (12) / §30 Gates (13) | 경계·비-acceptance | — | §0.2·§8·§9.2 |

**L1 슬라이스 = 5 PTF-EV(001·002·004·006·008)**·**substrate = §9/§10/§11/§14/§16/§20/§24**·**not-Phase-1 = §18/§21/§22/
§23**. **닫는 PTF-EV = 0건.** **sibling 서사 상속 금지(defect-class #3)**: PTF의 L1 집합 {001·002·004·006·008}은
nontrade #21의 L1 집합 {001·002·010}과 **다르다** — nontrade NT-EV-005(Futures Expiry/Settlement)·NT-EV-004(Option
Exercise)는 nontrade측 `EV-L3+Broker`로 L1 부재이며, PTF-EV-006(exercise/assignment/CA obligation, L1)와 **좌표가
다르다**(nontrade=event side / PTF=obligation side).

### 1.1 PTF-AC-001..012 커버리지 표 (12/12 개별 대응 — Gap 봉합·AC↔EV 1:1)

> ADR §27은 `PTF-AC-001..012`(line 635–681)를 정의하며 `PTF-AC-n`은 `PTF-EV-n`과 1:1 대응(동일 제목). 아래 표가
> **12개 전수 개별 대응**을 고정한다(L1 슬라이스 5 core + not-Phase-1 7 substrate/deferred). **닫는 AC = 0건**(written
> case는 obligation만 정의·완결 evidence 아님 — §27 line 633).

| PTF-AC | 제목 (§27) | Phase-1 대응 | 실현/이연 |
|---|---|---|---|
| AC-001 | Fill/FQP vs Post-Trade Obligation Separation | **L1 core** | `finality_dimensions_orthogonal`·`obligation_commit_idempotent`(§5.1/§5.2) — `/2`·`/3`·`+Broker` 잔여 |
| AC-002 | Fee/Tax/Interest/Financing Legs and Corrections | **L1 core** | `monetary_leg_conservative`·`netting_requires_positive_proof`(§5.3) — 잔여 동일 |
| AC-003 | Settlement, Cash Availability, Partial/Failure | substrate | `CashKind`·`cash_kind_matches_requirement`(§5.4·§6.1) — availability PROOF **PTF-EV-003 `EV-L2/3` 이연** |
| AC-004 | Margin/Collateral/Encumbrance/Haircut/Double-Use | **L1 core** | `collateral_no_double_use`·`margin_collateral_states_distinct`(§5.4) — 잔여 동일 |
| AC-005 | Borrow/Recall/Return/Buy-In | substrate | 어휘만(§6.2) — discharge PROOF **PTF-EV-005 `EV-L2/3` 이연** |
| AC-006 | Exercise/Assignment/Delivery/Corporate-Action | **L1 core** | `obligation_legs_from_event_complete`·`event_state_not_obligation_finality`(§5.5) — nontrade 경계·잔여 동일 |
| AC-007 | Custody/Transfer/In-Flight/Legal-Title | not-Phase-1 | 어휘만(§6.3) — chain/title PROOF·+Security **PTF-EV-007 `EV-L2/3+Sec` 이연** |
| AC-008 | Statement Coverage, Provenance, Conflict/Common-Mode | **L1 core(+Sec 잔여)** | `statement_coverage_complete`·`statement_sources_independent`·`absence_is_negative_evidence_only`(§5.6) — +Security 이연 |
| AC-009 | Breaks/Busts/Corrections/Reversal/Finality Reopen | substrate | append-only-no-overwrite·`finality_proof_current`(§5.2/§5.7) — break-to-restrict runtime **PTF-EV-009 `EV-L2/3+Sec` 이연** |
| AC-010 | RCL Transfer/Release + Generation Currentness/Send Race | not-Phase-1 | obligation-set 열거만(§6.5) — RCL coupling·generation fence **PTF-EV-010 `EV-L2/3+Sec` 이연**(cur/rcl/egress) |
| AC-011 | Partition/Compromise/Stale Writer/Route Bypass | not-Phase-1 | — 전부 런타임·+Security **PTF-EV-011 `EV-L3+Sec` 이연** |
| AC-012 | Evidence/Recovery/Non-Revival/Status Honesty | substrate | frozen record 재구성만(§6.6) — replay·recovery·no-revival **PTF-EV-012 `EV-L2/3+Sec` 이연** |

**12/12 개별 대응·무저작 0.** L1 core = AC/EV-001·002·004·006·008(5) — 나머지 7은 substrate/not-Phase-1 명시.

---

## 2. 데이터 모델 계약

**핵심 난제**: post-trade economic effect를 **exact·immutable·versioned obligation record**로 표현하되(ADR §1 line 15),
capacity(rcl)·risk(are)·per-field-confidence(recon)·event-identity(nontrade)·broker-capability(brokercap)·egress
(egress)는 **형제가 소유**하므로 PTF은 obligation identity·leg completeness·finality-dimension orthogonality·commit
idempotency·no-favorable-default·collateral-conservation·statement-coverage만 **순수·비전송·fail-closed**로 모델링한다.

### 2.0 소유권 골격 — posttrade는 canonical의 하류, 12+ 형제의 하류(주입 소비)·미래 런타임의 상류(produced-token)

```text
        canonical (core)                         ordering (core)
   FrozenModel·DigestBoundArtifact          obligation / finality / statement /
   IndependentIdArtifact·CanonicalDecimal   correction append-only 순서 +
   classify_record_pair·RecordPairKind      Post-Trade Obligation Generation
              │  (import)                              │  (import)
              ▼                                         ▼
   ┌──────────────────────── tos.posttrade (본 문서, 26번째 패키지) ───────────────────────┐
   │  vocabulary(9): PostTradeObligationLifecycleState(12)·FinalityDimensionKind(10)·      │
   │              ObligationLegDirection(8)·CashKind(6)·MarginCollateralState(8)·          │
   │              StatementClass(3)·EventObligationLegKind(9)·ObligationCommitOutcome(6)·  │
   │              PostTradeDisposition(result)                                             │
   │  records:    EconomicObligationRecord·PostTradeFinalityProof·StatementCoverageManifest│
   │              ·PostTradeBreakRecord·ObligationLeg·ObligationLegScope·MonetaryLeg·      │
   │              CollateralAllocation·AllFalsePostTradeConsequence(all-false)             │
   │  predicates(19): finality_dimensions_orthogonal·obligation_leg_set_complete·         │
   │              obligation_commit_idempotent·monetary_leg_conservative·                 │
   │              netting_requires_positive_proof·missing_counterleg_is_adverse·          │
   │              collateral_no_double_use·margin_collateral_states_distinct·             │
   │              cash_kind_matches_requirement·obligation_legs_from_event_complete·      │
   │              event_state_not_obligation_finality·statement_coverage_complete·        │
   │              statement_sources_independent·absence_is_negative_evidence_only·        │
   │              finality_proof_class_specific·finality_proof_non_transferable·          │
   │              finality_proof_current·post_trade_consequence_all_false·                │
   │              post_trade_disposition (19, §9.1)                                       │
   └──────────────────────────────────────────────────────────────────────────────────────┘
        ▲ (주입 소비 — import 아님; produced-token/bool/CanonicalDecimal 좌표)
        │  rcl(FINAL_QUANTITY_PROOF·credible_union_capacity·CapacityState)·
        │  are(SETTLEMENT_CASH_CURRENCY·MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN·BenefitKind.NETTING·worst_intermediate_risk)·
        │  recon(classify_field·FieldConfidenceClass·POST_TRADE_OBLIGATION_IDENTITY_AND_VERSION)·
        │  brokercap(fqp_adequate·POSITIONS_BALANCES_MARGIN·CapabilityStatus)·nontrade(NonTradeEventWorkflowState:APPLIED_LOCAL/RECONCILED)·
        │  egress(EgressAdmission·credential_route_authority_disjoint)·orthostate(KnowledgeState)·cur(DimensionKey.POST_TRADE·ProofResult·CurrentnessAdmission)·
        │  authority/liveauth(no_automatic_rearm)·sbr(restore_worst_credible_union)·time(freshness_verdict)
        ▼ (produced-token/bool 생산 — 미래 소비자 배선은 런타임 §9.1)
   미래: rcl capacity-commit·are risk-projection·cur/egress currentness-fence·PTOL serialization 런타임
```

**sibling edge 0건**(§0.4b·§3.4): PTF은 canonical·ordering만 import한다. 12+ 상류 형제는 **주입 좌표**로만 소비하고
import하지 않는다.

### 2.1 digest-bound / plain-frozen / value / reference 분류 (총괄)

| 모델 | 종류 | id ⊥ digest | 근거 |
|---|---|---|---|
| `EconomicObligationRecord` | **digest-bound + IndependentIdArtifact** | ✅ (obligation id·version·source event id·generation §9 line 268) | 위조·contradictory obligation·double-commit fill 탐지 `classify_record_pair`(§0.4f·§4.6) |
| `PostTradeFinalityProof` | **digest-bound + IndependentIdArtifact** | ✅ (proof id·obligation ref·leg·finality-class §11 line 320) | non-transferable·non-unionable proof forgery 탐지(§5.7) |
| `StatementCoverageManifest` | **digest-bound + IndependentIdArtifact** | ✅ (source·period·revision·issue id §19 line 440) | statement revision·restatement·common-mode 탐지(§5.6). **`statement_class: StatementClass` 필드 보유**(preliminary/final/revised — Q3 소재 확정, §5.6) |
| `PostTradeBreakRecord` | **digest-bound + IndependentIdArtifact** | ✅ (break id·scope·source-revision·old/new version §20 line 458) | **substrate만**(m5) — break 판정·closure runtime은 PTF-EV-009 `EV-L2/3+Sec` 이연(§6.4); Phase-1은 frozen 레코드 shape·append-only-no-overwrite만 |
| `ObligationLeg` | **plain-frozen value** | — | direction(`ObligationLegDirection`)·magnitude·scope(§5.3); record 내부 leg |
| `ObligationLegScope` | **plain-frozen value** | — | **M8 정식 등재** — finality-proof가 bind하는 **정확한 scope 튜플**(leg·account·currency·value-date·source-revision·finality-class — ADR §11 line 328); `finality_proof_non_transferable`(§5.7) 대조 대상. `ObligationLeg`(direction·magnitude 포함)와 **별개**(scope-only) |
| `MonetaryLeg` | **plain-frozen value** | — | fee/tax/interest/financing basis·period·provisional/final(§13); 값 객체 |
| `CollateralAllocation` | **plain-frozen value** | — | free/encumbered/pledged unit(§15); 보존 검사 입력 |
| `AllFalsePostTradeConsequence` | **all-false frozen** | — | finality-grants-nothing(§10 line 312); 어떤 True도 unconstructable |
| `PostTradeDisposition`·`ObligationCommitOutcome` | **`_NonTruthyStrEnum`**(m7) | — | 결정 결과 — truthy-untestable(`__bool__`⇒`TypeError`); identity 게이트만(§2.2-8) |
| 나머지 어휘 7종(`PostTradeObligationLifecycleState`·`FinalityDimensionKind`·`ObligationLegDirection`·`CashKind`·`MarginCollateralState`·`StatementClass`·`EventObligationLegKind`) | **plain `StrEnum`** | — | 구조적 축·어휘(non-result) |

### 2.2 어휘 (verbatim 전사 — 에라타 defect class 주의·항목 수 대조 전수화)

> **전사 규율**: 아래 enum member는 ADR 원문 리스트를 개념(문자열 아님) 기준으로 전사하며 **항목 수를 병기·개별 계수**
> 한다(defect-class #4). ADR 원문이 "at least"/"where applicable"/"at minimum"으로 열면 **non-closed minimum set**임을
> 명시한다(recon `SafetyRelevantField` 선례).

**2.2-1 `PostTradeObligationLifecycleState`(StrEnum, 8 linear + 4 branch = 12종 — ADR §10 line 287–301 verbatim,
orthogonal)**:

- linear(8): `POTENTIAL` → `RECOGNIZED` → `DUE` → `IN_FLIGHT` → `PARTIALLY_SATISFIED` → `SATISFIED_PENDING_FINALITY`
  → `FINALITY_PROVEN` → `CLOSED`.
- branch(4): `BREAK_OPEN`(Any state →)·`CORRECTION_PENDING`(Any state →)·`FAILED_OR_TRAPPED`(Any state →)·`SUPERSEDED`
  (Any state →).

**항목 수 = 8 + 4 = 12.** **불변식 앵커(§10 line 312 verbatim)**: "``SATISFIED_PENDING_FINALITY`` is not final.
``FINALITY_PROVEN`` proves only the exact declared leg and proof class. ``CLOSED`` preserves immutable lineage and can
be superseded by a later correction without destructive overwrite. **No lifecycle state creates capacity release,
available cash, legal title, or permission**"(finality-grants-nothing §4.7). **orthogonality(§10 line 303–310)**: 이
축은 orthostate Knowledge/Intent/Capacity 축과 **별개 6번째 축**이며 붕괴 금지(§2.2-6). **transition validity는 NOT
Phase-1**(nontrade §5.4 동형): 어떤 state 전이가 정당한지는 rcl capacity·recon confidence·finality proof 런타임 게이트
(EV-L2/3)이며, 본 패키지에 transition 술어 없음·아무것도 state를 set하지 않는다.

**2.2-2 `FinalityDimensionKind`(StrEnum, 10종 — ADR §6 PTF-INV-002 line 156 verbatim, orthogonal finality 축)**:

| member | ADR 근거 | dimension |
|---|---|---|
| `ORDER_FQP` | §12 line 338 | broker order final cumulative fill + zero remaining executable quantity |
| `TRADE_CAPTURE` | §12 line 341 | trade capture free from later bust/correction |
| `INSTRUCTION_ACCEPTANCE` | §14 line 366·PTF-INV-002 | settlement-instruction acceptance |
| `SETTLEMENT` | §14·PTF-INV-002 | settlement completion |
| `CASH_AVAILABILITY` | §14 line 370·PTF-INV-002 | withdrawable/available cash |
| `COLLATERAL_ELIGIBILITY` | §15·PTF-INV-002 | collateral eligibility |
| `CUSTODY_TITLE` | §18 line 428·PTF-INV-002 | custody/legal-title finality |
| `FEE_FINALITY` | §13·PTF-INV-002 | fee/tax/interest/financing finality |
| `BORROW_DISCHARGE` | §16·PTF-INV-002 | borrow discharge |
| `CORPORATE_ACTION_FINALITY` | §17·PTF-INV-002 | corporate-action finality |

**항목 수 = 10**(PTF-INV-002 line 156 "Order FQP, trade capture, instruction acceptance, settlement, cash
availability, collateral eligibility, custody title, fee finality, borrow discharge, and corporate-action finality"
개별 계수). **핵심 불변식(PTF-INV-002 verbatim)**: "**do not imply one another**." **`FinalityDimensionKind`는 enum
membership이지 boolean이 아니다** — 각 dimension의 proven/unknown은 `PostTradeFinalityProof`가 dimension별로 bind하고,
UNKNOWN이 기본(PTF-INV-006). 이 10-축 non-implication이 PTF-EV-001의 핵심(§4.1·§5.1).

**2.2-3 `ObligationLegDirection`(StrEnum, 8종 — ADR §5.3 line 116·§9 line 273 verbatim)**:

`DEBIT`·`CREDIT`·`DELIVERY`·`RECEIPT`·`ENCUMBRANCE`·`RELEASE`·`RETURN`·`CONTINGENT`. **항목 수 = 8**(§5.3 line 116
"debit, credit, delivery, receipt, encumbrance, release, return, and contingent effect" 개별 계수). **극성 축(§4.5-A)**:
`DEBIT`(payable)↔`CREDIT`(receivable)·`DELIVERY`↔`RECEIPT`·`ENCUMBRANCE`↔`RELEASE`가 opposite-direction pair이며,
uncertain receivable(CREDIT)를 payable(DEBIT)에 netting하는 것이 fail-open(§4.5-A·PTF-INV-007). **netting은 flag가
아니라 both-gross-magnitude 병존 + proof-token 부재로 구조 파생**(§0.4d).

**2.2-4 `CashKind`(StrEnum, 6종 — ADR §6 PTF-INV-010 line 188 verbatim, non-substitution 축)**:

`LEDGER_CASH`·`PENDING_CASH`·`SETTLED_CASH`·`WITHDRAWABLE_CASH`·`BUYING_POWER`·`COLLATERAL_ELIGIBLE_CASH`. **항목 수 =
6**(PTF-INV-010 line 188 "Ledger cash, pending cash, settled cash, withdrawable cash, buying power, and collateral-
eligible cash remain distinct" 개별 계수). **불변식(PTF-INV-010)**: "**cannot be silently substituted**." **substrate
경계(정직 공개)**: cash-kind 어휘·non-substitution 구조 property는 L1이나, **settlement/cash availability PROOF은
PTF-EV-003 `EV-L2/3` 잔여**(§14 not-L1) — buying-power→withdrawable 전환 증명은 broker 단계다. §25.4 rejected "Buying
power is available cash"를 타입 구분으로 구조 실현.

**2.2-5 `MarginCollateralState`(StrEnum, 8종 — ADR §15 line 385 verbatim) + `StatementClass`(3종 — §19)**:

- `MarginCollateralState`(8): `MARGIN_OBSERVATION`·`MARGIN_CALL`·`COLLATERAL_REQUEST`·`INSTRUCTION_ACKNOWLEDGEMENT`·
  `PLEDGED_COLLATERAL`·`ACCEPTED_COLLATERAL`·`AVAILABLE_EXCESS`·`CONFIRMED_RELEASE`. **항목 수 = 8**(§15 line 385 "a
  margin observation, margin call, collateral request, instruction acknowledgement, pledged collateral, accepted
  collateral, available excess, and confirmed release" 개별 계수). **불변식(§15 line 385)**: "**No one state implies
  another**"; **double-use 금지(§15 line 386·PTF-INV-011)**: "The same collateral unit SHALL NOT be counted as both
  free and encumbered, pledged to two obligations, or reusable before confirmed release." broker favorable figure는
  Critical Input·ceiling이지 proof 아님(§15 line 387).
- `StatementClass`(3): `PRELIMINARY`·`FINAL`·`REVISED`. **항목 수 = 3**(§19 line 442 "preliminary/final classification,
  restatement"). **불변식(§19 line 448)**: "``FINAL``, contractual, signed, or independently delivered does not make
  it unconditional truth outside the approved proof recipe." **Q3 소재**: `StatementClass`는 `StatementCoverageManifest.
  statement_class` 필드로 보유(§2.1).

**2.2-5b `EventObligationLegKind`(StrEnum, 9종 — ADR §17 line 416 verbatim; m6 신설 — bare-str 축의 enum화·drift-lock)**:

`ASSET`·`CASH`·`FEE`·`TAX`·`FINANCING`·`MARGIN`·`BORROW`·`CUSTODY`·`DELIVERY`. **항목 수 = 9**(§17 line 416 verbatim
"SHALL model every credible **asset, cash, fee, tax, financing, margin, borrow, custody, and delivery** leg" 개별 계수).
**`ObligationLegDirection`(8, debit/credit/…)과 별개 축**: 이것은 exercise/assignment/CA event가 낳는 obligation의
**leg TYPE**(무엇에 대한 의무)이고 direction은 그 leg의 **부호**(채권/채무)다. `obligation_legs_from_event_complete`
(§5.5)가 event-class-parametric required subset을 이 enum으로 받아 완전성 판정(m6 — v1.0의 `frozenset[str]`을 enum화해
drift-lock; §7 seam에 9-member value 바인딩 assert).

**2.2-6 `ObligationCommitOutcome`(StrEnum, 6종 — PTF-local, canonical `classify_record_pair` 하류) + 좌표 비붕괴**:

- `COMMITTED_ONCE`(lineage+retained+**`prior is None`**(첫 commit, classify **선행 게이트** §5.2) ⇒ obligation effect
  count→1)·`IDEMPOTENT_REPLAY`(`RecordPairKind.IDEMPOTENT_DUP`: same primary/idempotency id·same bytes ⇒ no-op)·
  `REJECTED_CONFLICT`(**두 conflict kind 병합**: `CRITICAL_CONFLICT`[same **primary** id·diff bytes — obligation 위조]
  **∪** `DIVERGENT_EMISSION`[same **idempotency** id·diff bytes — 두 상이 fill이 한 key 주장] ⇒ contain-both·no-double-
  commit)·`REJECTED_NO_LINEAGE`(supersedes 부재 — §20 line 460 no-relabel)·`REJECTED_OVERWRITE`(destructive overwrite —
  §11 line 330·§20 line 460 위반)·`REJECTED_UNKNOWN`(`NOT_COMPARABLE`[digest None] ∪ `DISTINCT`[계약 위반] ⇒ fail-
  closed). **항목 수 = 6(outcome).**
- **RecordPairKind 5-member 전수 매핑(#21 C2 교훈 — 실측 `canonical/record_pair.py:52–105`)**: `IDEMPOTENT_DUP`(:94/
  :101)→`IDEMPOTENT_REPLAY` · `CRITICAL_CONFLICT`(same **primary** id·diff bytes, :96)→`REJECTED_CONFLICT` · `DIVERGENT_
  EMISSION`(same **idempotency** id·diff bytes, :103)→`REJECTED_CONFLICT` · `DISTINCT`(:105)→`REJECTED_UNKNOWN` ·
  `NOT_COMPARABLE`(digest None, :87)→`REJECTED_UNKNOWN`; **`prior is None`은 classify 선행 게이트**로 `COMMITTED_ONCE`
  (§5.2). classify는 **4-positional+2-keyword** 시그니처(`a_identity, a_digest, b_identity, b_digest, *, a_idempotency_
  id, b_idempotency_id`)다.
- **좌표 비붕괴(§2.2-6 규율)**: PTF enum 값이 형제 enum 값과 문자열이 겹쳐도 **별개 타입**이다 — `PostTradeObligation
  LifecycleState.CLOSED`(obligation 축) ≠ orthostate `IntentState.CLOSED`(intent 축); `FINALITY_PROVEN`(obligation 축)
  ≠ orthostate `KnowledgeState.RECONCILED`(knowledge 축) ≠ nontrade `NonTradeEventWorkflowState.RECONCILED`(event 축);
  `ObligationCommitOutcome.IDEMPOTENT_REPLAY`(fill-obligation-commit) ≠ iap `ConsumptionOutcome.IDEMPOTENT_REPLAY`
  (authorization-token) ≠ rcl `ApplyReason.IDEMPOTENT_REPLAY`(capacity-command) ≠ nontrade `CorrectionReversalOutcome.
  IDEMPOTENT_REPLAY`(event-application). property 회귀로 별개-타입 assert(§7).

**2.2-7 ADR §12 FQP does-not-prove 6항목 개별 전사 + §9 obligation record 8항목 (카운트 대조 전수화)**:

§12 line 340–345 "It does not prove:" — (1) trade capture free from later bust/correction · (2) cash or securities
settled · (3) proceeds withdrawable or collateral-eligible · (4) fees/tax/interest/financing final · (5) borrow or
delivery obligations discharged · (6) custody or legal title final. **항목 수 = 6.** ⇒ `finality_dimensions_orthogonal`
(§5.1)이 `ORDER_FQP` PROVEN이 이 6(및 나머지 dimension)을 PROVEN으로 만들지 않음을 강제.

§9 line 268–275 "Each Economic Obligation Record SHALL contain:" — (1) obligation identity/type/version/digest/status/
generation · (2) causal source event identities/digests · (3) account/subaccount/legal-entity/beneficial-owner/broker/
clearing-member/custodian/bank/venue/settlement-location · (4) instrument/asset/currency/quantity/amount/unit/sign/
multiplier/price-basis/FX-basis/rounding/tolerance · (5) trade/record/ex/due/value/settlement/recall/delivery/payable/
observation dates · (6) debit/credit/delivery/receipt/encumbrance/release/return/contingent legs · (7) source-
continuity/statement/correction bindings/confidence/conservative-bound · (8) lifecycle/finality/break/supersession/
invalidation/capacity/evidence bindings. **항목 수 = 8**(line 268–275 8 bullet 개별 계수). **non-closed**: line 266
"SHALL contain" — id⊥digest 필수 근거는 (1)의 identity(primary)와 (7)/(2)의 source event id + idempotency-key가 서로
다른 두 identity 축이며 canonical이 `CRITICAL_CONFLICT`/`DIVERGENT_EMISSION`으로 분리 탐지한다(§0.4f).

**2.2-8 `PostTradeDisposition`(StrEnum, result — truthy-untestable, `_NonTruthyStrEnum` 패턴, 5종)**:

- `POST_TRADE_ADMISSIBLE`(전 obligation leg 완전·finality proven(요구 시)·no break·no conflict·no double-use ⇒
  conservative transition 허용 — **§5.8 양성 conjunction으로만 도달**)·`POST_TRADE_BLOCK_NEW_RISK`(§1 line 25 "consumes
  conservative capacity and blocks affected new risk"·PTF-INV-006)·`POST_TRADE_QUARANTINED_UNKNOWN`(unattributable/
  undecidable post-trade state — PTF-INV-006)·`POST_TRADE_TRAPPED`(§14 line 373 trapped cash·§18 line 430 "asset ...
  SHALL NOT disappear")·`POST_TRADE_CONFLICTED`(break·contradicted evidence·record-pair conflict — §20). **항목 수 =
  5.** rcl/venue/nontrade/egress의 `_NonTruthyStrEnum`(`__bool__` ⇒ `TypeError`) 동형 — truthy-sentinel 오용
  (`if disposition:`) 봉인, identity 게이트(`is POST_TRADE_ADMISSIBLE`)만 허용(§4 truthy-sentinel 극성 분기).

### 2.3 아티팩트 covered + self-exclusion (설계 #4 §3.3 상속)

`EconomicObligationRecord`·`PostTradeFinalityProof`·`StatementCoverageManifest`는 `DigestBoundArtifact` covered-field
규율을 따른다(canonical §3.3): digest는 **covered 필드 전수**를 bind하고, `AllFalsePostTradeConsequence`(all-false)·
재구성 파생 필드는 self-exclude(digest 자기 포함 방지). same-id/diff-covered-bytes ⇒ `classify_record_pair`
`CRITICAL_CONFLICT`(§4.6). **PTF은 capsule content-addressed(`IdDerivedArtifact`)를 쓰지 않는다**(§0.4f — id⊥digest 필요).

---

## 3. canonical / ordering REUSE + 12-생산자 주입 seam + 형제 경계

### 3.1 canonical REUSE + `id=f(digest)` 미채택

`EconomicObligationRecord`·`PostTradeFinalityProof`·`StatementCoverageManifest`는 `IndependentIdArtifact`(id⊥digest)를
채택한다(§0.4f). obligation/proof/statement identity(source event id·version·supersedes ref·idempotency key)가 있고
위조·contradictory obligation·double-commit fill을 `classify_record_pair`로 탐지하려면 id⊥digest여야 하기 때문이다
(same primary id·diff bytes ⇒ `CRITICAL_CONFLICT` / same idempotency key·diff bytes ⇒ `DIVERGENT_EMISSION` — 두 축 모두
id⊥digest 전제). `IdDerivedArtifact`(capsule) 미채택. #4–#21 §3.1 동형.

### 3.2 ordering REUSE (obligation / finality / statement / correction append-only 순서 + Post-Trade Obligation Generation)

**Post-Trade Obligation Generation은 `tos.ordering` 좌표다**(§0.1(2)). ADR §4 line 118·§5.5 "PTOL ... SHALL be the
sole serialization authority ... It SHALL append and order obligation identities, versions, lifecycle transitions,
breaks, supersessions, finality-proof bindings, and the monotonic **Post-Trade Obligation Generation**." — 이 append-
only 순서·monotonic generation은 **ordering 원시가 이미 소유**하며(rcl Writer Epoch·nontrade event generation·#13/#16/
#18/#21 동형), PTF은 별도 heavy generation 아티팩트를 저작하지 않고 ordering 좌표를 주입 소비한다. **PTOL serializer
런타임(consensus·writer epoch·restore·idempotency) 자체는 EV-L2/3**(PTF-EV-010 — §30 gate 2/6)이며 본 Phase-1은
generation-monotone·append-only-no-overwrite **구조 property**만 둔다. #21 §3.2 동형.

### 3.3 REUSE 요약 표

| 원시 | REUSE 여부 | 근거 |
|---|---|---|
| canonical `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`CanonicalDecimal`·`classify_record_pair`·`RecordPairKind`·`ArtifactStatus` | **REUSE(import)** | core 원시(§0.3·§3.1) |
| ordering append-only 순서·monotonic generation | **REUSE(import)** | Post-Trade Obligation Generation 좌표(§3.2) |
| rcl `CapacityVector`·are `ProjectedCell`·recon `FieldConfidence` | **미REUSE(edge-0)** | L1 결정에 타입 불요·좌표 충돌(§0.4c) |
| capsule `IdDerivedArtifact`(content-addressed) | **미채택** | id⊥digest 필요(§3.1) |
| 형제 어휘·술어(rcl/are/recon/brokercap/nontrade/egress/orthostate/…) | **미import(sibling edge 0)** | 주입 좌표/produced-token(§3.4/§3.5) |

**PROMOTE 0건. sibling edge 0건.**

### 3.4 12-생산자 주입 seam(edge 0) — produced-token/좌표 소비 (중심, 코드 실측)

PTF은 canonical·ordering만 import하고, 12+ 상류 형제가 생산한 값을 **주입 좌표**로 소비한다. 각 좌표는 **형제 member의
token**(bare string / StrEnum value)으로 seam을 건너며, §7 seam test가 형제를 **test에서만** import해 token이 live
member와 일치함을 drift-lock한다(nontrade `ORDER_ADMISSIBILITY_ADMISSIBLE` / egress `CommitProofValidity` 선례). token은
`==` 비교(StrEnum member는 value와 같음); `is` identity는 PTF 자신의 enum에만 쓰고, `bool(token)`은 쓰지 않는다(형제
producer의 `__bool__`이 raise하며 bare string도 truthy).

**주입 토큰 목록(전수 drift-lock 대상 — #21 MINOR-1 "13개 중 1개 누락" 교훈)**: (1) rcl `FINAL_QUANTITY_PROOF` ·
(2) rcl `CapacityState.TRAPPED_CONSUMED` · (3) rcl `CapacityState.QUARANTINED_UNKNOWN` · (4) are `SETTLEMENT_CASH_
CURRENCY` · (5) are `MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN` · (6) are `MISSING_ACK_RECEIPT_AMBIGUITY` · (7) are
`BenefitKind.NETTING` · (8) recon `FieldConfidenceClass.CORROBORATED` · (9) recon `FieldConfidenceClass.UNKNOWN` ·
(10) recon `FieldConfidenceClass.CONFLICTED` · (11) brokercap `CapabilityStatus.VERIFIED` · (12) brokercap `fqp_
adequate` 산출 bool · (13) nontrade `NonTradeEventWorkflowState.APPLIED_LOCAL` · (14) nontrade `NonTradeEventWorkflow
State.RECONCILED` · (15) egress `EgressAdmission.ADMIT` · (16) egress `CommitProofValidity.VALID` · (17) time
`FreshnessVerdict.FRESH` · **(18) cur `DimensionKey.POST_TRADE`(`cur/vocabulary.py:146`)** · **(19) cur `Currentness
Admission.ADMIT`(`:113`)**(M5 — cur committed 후 신설). **19 주입 토큰 전수 §7 drift-lock**(개별 계수 — 누락 0 강제).
각 토큰은 `vocabulary.py`의 로컬 상수로 고정하고 §7 seam test가 실 member와 대조한다.

### 3.5 소유권 분할표 — posttrade가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11/#16/#18/#21 §3.5 상속)

> **소유권 분할 명시(#8 C1·#18 C2·#21 M4 교훈 — cross-section·명제-동일성 혼동 선제 봉합)**: ADR-002-030은 **obligation
> identity·exact leg·obligation lifecycle·field-specific finality proof·finality-dimension orthogonality·fill-commit
> idempotency·no-favorable-default·collateral conservation·statement coverage**만 결정하며 capacity 산술(rcl)·aggregate-
> risk 투영·netting benefit(are)·per-field confidence(recon)·broker capability(brokercap)·**event·transformation
> identity·event workflow lifecycle(nontrade)**·external egress(egress)·order/knowledge 상태 축(orthostate)·authority/
> re-arm(authority/liveauth)·recovery(sbr)·currentness(cur/ADR-002-024)·evidence custody(ADR-002-016)를 **소유하지
> 않는다**. **최대 함정: 명칭 유사 ≠ 명제 동일**(defect-class #3) — 아래 표의 "seam 방향·명제 동일성" 열이 각 경계를
> 코드 실측으로 고정하며, **명칭이 겹치되 명제가 다른 4쌍**을 명시한다. 인용은 전부 **코드 실측 signature+라인**이다.

| ADR 조항/개념 | posttrade 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향·명제 동일성(실측) |
|---|---|---|---|
| §12 FQP separation (PTF-EV-001) | `finality_dimensions_orthogonal`·`obligation_commit_idempotent`·`FinalityDimensionKind`(10) | **rcl `TransitionCause.FINAL_QUANTITY_PROOF`(`vocabulary.py:94`)·`CommandType.APPLY_FINAL_QUANTITY_PROOF`**·brokercap `fqp_adequate`(`predicates.py:595`)·recon `CUMULATIVE_FILLED_QUANTITY`(`vocabulary.py:74`) | **명제 상이(핵심 seam)**: rcl `FINAL_QUANTITY_PROOF`는 **order capacity의 proof-gated release**(§5 INV-007) / PTF `FinalityDimensionKind.ORDER_FQP`는 **10 post-trade dimension 중 1축이며 나머지 9를 함의하지 않는다**(§12 line 340·PTF-INV-002 "do not prove any post-trade obligation final"). FQP(rcl/brokercap) → PTF 주입 소비, PTF non-implication 판정 |
| §9 obligation identity + exact leg | `EconomicObligationRecord`·`ObligationLeg`·`obligation_leg_set_complete`·`ObligationLegDirection`(8) | canonical `classify_record_pair`·`IndependentIdArtifact`(import)·ordering generation(import) | PTF obligation record 저작; canonical/ordering core import |
| §10 obligation lifecycle | `PostTradeObligationLifecycleState`(12)·`post_trade_consequence_all_false` | **orthostate `KnowledgeState`(`vocabulary.py:121`)·`IntentState`(`:32`)·`BrokerOrderState`(`:92`)** | **명칭 유사·명제 상이**: orthostate `IntentState.CLOSED`(intent 축)·`KnowledgeState.RECONCILED`(knowledge 축) ≠ PTF `PostTradeObligationLifecycleState.CLOSED`·`FINALITY_PROVEN`(obligation 축, §10 line 305 "orthogonal to ... Knowledge/Evidence State"). PTF 6번째 축 소유; orthostate 5 축 주입 좌표(비붕괴) |
| §11 finality proof | `PostTradeFinalityProof`·`finality_proof_class_specific`·`finality_proof_non_transferable` | **recon `classify_field`(`predicates.py:107`)·`FieldConfidenceClass`(`vocabulary.py:26`)·`POST_TRADE_OBLIGATION_IDENTITY_AND_VERSION`(`:85`)** | **명제 상이(핵심 seam)**: recon = **per-field evidence confidence**(UNKNOWN/SINGLE_SOURCE/CORROBORATED/CONFLICTED/STALE) / PTF = **field-specific finality proof**(exact class + "what it does not prove"). PTF-INV-005 verbatim "confidence score ... cannot replace exact per-field proof". recon confidence → PTF 주입 소비, finality-proof binding은 PTF 소유 |
| §13 fees/tax/interest/financing (PTF-EV-002) | `monetary_leg_conservative`(absence≠zero)·`netting_requires_positive_proof`·`MonetaryLeg` | **are `BenefitKind.NETTING`(`vocabulary.py:131`)** | **명칭 유사·명제 상이**: are `BenefitKind.NETTING`(aggregate-risk 축의 netting **benefit** — proof 요구) ≠ PTF obligation-leg no-netting(obligation 축의 receivable/payable **gross 병존** — §9 line 279). PTF gross legs → are netting benefit(proof) 주입 소비. **3중 netting 분리**: nontrade transition-envelope ≠ PTF obligation-leg ≠ are risk-benefit(§0.4d) |
| §14 settlement/cash availability | `CashKind`(6) 어휘 + `cash_kind_matches_requirement`(substrate) | **are `SETTLEMENT_CASH_CURRENCY`(`vocabulary.py:65`)·recon `SETTLEMENT_CASH_AVAILABILITY_COLLATERAL_ELIGIBILITY`(`vocabulary.py:89`)** | cash-kind 구분 L1 / **availability PROOF은 PTF-EV-003 `EV-L2/3` 잔여**. are risk / recon confidence 주입 소비 |
| §15 margin/collateral (PTF-EV-004) | `collateral_no_double_use`·`margin_collateral_states_distinct`·`MarginCollateralState`(8)·`CollateralAllocation` | **are `LEVERAGE_MARGIN_COLLATERAL`(`vocabulary.py:61`)·recon `CASH_MARGIN_COLLATERAL`(`:78`)·brokercap `POSITIONS_BALANCES_MARGIN`(`vocabulary.py:79`)** | PTF 보존(double-use)·8상태 non-implication 소유 / are risk·recon confidence·brokercap capability 주입 소비. broker favorable figure = Critical Input(§15 line 387, brokercap 주입) |
| §16 borrow/recall/return/buy-in | (substrate) borrow-lifecycle 어휘만 | **are `MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN`(`vocabulary.py:112`)** | **not-Phase-1(PTF-EV-005 `EV-L2/3`)** — discharge/buy-in PROOF는 broker 단계 잔여(§6.4) |
| §17 exercise/assignment/CA obligations (PTF-EV-006) | `obligation_legs_from_event_complete`·`event_state_not_obligation_finality` | **nontrade `NonTradeEventClass`·`NonTradeEventWorkflowState`(`vocabulary.py:165`)·`CredibleTransitionLegKind`(`:213`)·`correction_reversal_idempotent`** | **명칭 유사·명제 상이(최대 소유권 경계)**: nontrade "leg"(`CredibleTransitionLegKind` = **transition-envelope completeness 좌표**) ≠ PTF "leg"(`ObligationLeg` = **obligation record with finality**); nontrade `RECONCILED`/`APPLIED_LOCAL`(event 축) → PTF `event_state_not_obligation_finality`가 **주입 소비**해 non-implication 판정(§17 line 418 verbatim). **ADR-002-010 §16 line 309 ↔ ADR-002-030 §17 line 414 상호 이연**(event/transformation identity=nontrade / obligation legs+lifecycle+finality=PTF) |
| §18 custody/transfer/legal-title | (substrate) custody 어휘만 | egress `credential_route_authority_disjoint`(`egress/predicates.py:405`) | **not-Phase-1(PTF-EV-007 `EV-L2/3+Sec`)** — chain/title PROOF·+Security 잔여 |
| §19 statements (PTF-EV-008) | `StatementCoverageManifest`·`statement_coverage_complete`·`statement_sources_independent`·`absence_is_negative_evidence_only`·`StatementClass`(3) | **recon `classify_field` common-mode(`predicates.py:127` "shared independence_class cannot corroborate" RECON-EV-001)·brokercap capability** | **명제 상이(grain 상이)**: recon common-mode = **per-field independence_class** grain / PTF `statement_sources_independent` = **statement-SOURCE** grain(book/parser/administrator/transport disjoint — §19 line 445). PTF coverage-completeness는 recon에 부재(완전 신규); +Security 잔여 |
| §20 breaks/corrections/reversals | (substrate) append-only-no-overwrite | canonical `classify_record_pair`·rcl recompute-from-corrected | **not-Phase-1(PTF-EV-009 `EV-L2/3+Sec`)** — idempotent append L1 / break-to-RCL-restrict runtime·+Security 잔여 |
| §21 RCL capacity coupling | (미소유) obligation-set 열거만 | **rcl `credible_union_capacity`(`predicates.py:739`)·`RELEASE_RESERVATION`·`CapacityState`·are `worst_intermediate_risk`(`predicates.py:186`)** | **not-Phase-1(PTF-EV-010 `EV-L2/3+Sec`)** — PTF obligation-set → are risk → rcl capacity(§0.4d). rcl-only capacity(§1 line 21·PTF-INV-008 "only the RCL may perform the transition"); FINALITY_PROVEN는 release 못 함(§21 line 492) |
| §22 currentness/authority/egress | (미소유) currentness identity 좌표만(VP 주입) | **cur(ADR-002-024, committed `1390ef9d`) `DimensionKey.POST_TRADE`(`cur/vocabulary.py:146`)·`ProofResult`(CURRENT/RESTRICTED/UNKNOWN, `:96–98`)·`CurrentnessAdmission`(ADMIT/DENY, `:113–114`)·egress `generation_monotone`·`CommitProofValidity`·authority/liveauth `no_automatic_rearm`** | **not-Phase-1(PTF-EV-010)** — cur이 post-trade currentness 차원(`POST_TRADE`)을 이미 소유; PTF는 §8.1 identity 좌표(policy/generation/digest)를 주입하고 cur/egress가 fence·admit 판정. currentness vector·egress fence runtime 잔여 |
| §23 partition/compromise/route-bypass | (미소유) | egress `credential_route_authority_disjoint`·rcl containment | **not-Phase-1(PTF-EV-011 `EV-L3+Sec`)** — 전부 런타임·+Security 잔여 |
| §24 evidence/recovery/non-revival | (substrate) frozen digest-bound record 재구성 | **evidence(ADR-002-016) replay ENGINE·sbr `restore_worst_credible_union`·liveauth `no_automatic_rearm`** | **not-Phase-1(PTF-EV-012 `EV-L2/3+Sec`)** — record L1 / replay·recovery·no-revival 런타임 잔여(§24 line 548 "successful replay ... is not executed verification evidence") |

> **핵심 소유권 판정 4건(명제-동일성 함정 봉합)**:
> 1. **nontrade ↔ posttrade 분할(PTF-EV-006 — 최대 경계)**: nontrade가 **non-trade event identity·transformation
>    identity·event workflow lifecycle**(`NonTradeEventWorkflowState` OBSERVED→...→RECONCILED)을 소유하고, PTF가 **그
>    event로부터의 obligation leg·obligation lifecycle(POTENTIAL→...→CLOSED)·finality**를 소유한다. **분할 축 = 인과·
>    grain**: nontrade = 원인(corporate action/exercise event가 발생·transform), PTF = 결과(그로부터의 economic
>    obligation과 최종성). **명칭 함정 2건**: (a) "lifecycle" — nontrade=event workflow lifecycle / PTF=obligation
>    lifecycle serialization(§16 line 309이 후자를 명시 PTF로 이연); (b) "leg" — nontrade `CredibleTransitionLegKind`=
>    transition-envelope 완전성 좌표(credible economic STATE) / PTF `ObligationLeg`=exact economic effect record with
>    finality. ADR §16 line 309(nontrade측)·§17 line 414(PTF측) 상호 명시 경계로 중복 0. PTF-EV-006은 L1 슬라이스이나
>    nontrade측 NT-EV-004/005는 `EV-L3+Broker`(nontrade측 미Phase-1) — **좌표·stage 모두 다름**.
> 2. **recon ↔ posttrade 분할(confidence ≠ finality)**: recon이 **per-field evidence confidence**(`FieldConfidence
>    Class`)를 소유하고, PTF가 **field-specific finality proof**(`PostTradeFinalityProof`)를 소유한다. PTF-INV-005
>    verbatim "One global ``SETTLED``, ``CLOSED``, confidence score, statement flag, or operator decision cannot replace
>    exact per-field proof". **결정적**: recon이 이미 `POST_TRADE_OBLIGATION_IDENTITY_AND_VERSION`·`SETTLEMENT_CASH_
>    AVAILABILITY_COLLATERAL_ELIGIBILITY` 필드의 confidence를 소유(recon `vocabulary.py:85/89`)하므로 — PTF은 그 confidence
>    를 **입력**으로 받아 finality **proof**를 판정한다(CORROBORATED confidence는 finality의 necessary-input이지
>    sufficient가 아님). statement-source common-mode도 grain 상이(recon per-field / PTF statement-source).
> 3. **are ↔ posttrade 분할(netting 3중 명제)**: nontrade transition-envelope no-netting(old/new instrument exposure
>    both counted) ≠ PTF obligation-leg no-netting(receivable/payable gross 병존) ≠ are `BenefitKind.NETTING`(aggregate-
>    risk netting benefit — proof 요구). are가 이미 `SETTLEMENT_CASH_CURRENCY`·`MARGIN_COLLATERAL_BORROW_FX_SETTLE_
>    ASSIGN`·`MISSING_ACK_RECEIPT_AMBIGUITY`를 aggregate-risk 축에 first-class로 소유하므로 — PTF가 risk를 재투영하면
>    좌표 충돌·권위 중복(§0.4d). PTF는 obligation-set completeness+no-favorable-default를 소유하고 are가 risk·benefit을
>    소유한다.
> 4. **rcl ↔ posttrade 분할(FQP·capacity)**: rcl `FINAL_QUANTITY_PROOF` cause/`APPLY_FINAL_QUANTITY_PROOF` command는
>    **order capacity의 proof-gated release**(§5 INV-007이 FQP만 RELEASED 도달 허용)이지 **post-trade obligation
>    finality가 아니다**(PTF-INV-002·§1 line 23 "Final Quantity Proof ... does not prove any post-trade obligation
>    final"). PTF는 obligation-set을 produce하고 rcl이 capacity를 commit/transfer/quarantine한다 — **PTF은 capacity-
>    non-mutating**(§1 line 21·PTF-INV-008). `FINALITY_PROVEN`조차 release를 만들지 못한다(§21 line 492·PTF-INV-009).

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 PTF-INV-001..018·PTF-EV-001..012·
PTF-AC-001..012(§27)·§-clause·SAFE-###(§28)**이며 **새 시리즈를 창작하지 않는다**(§0.4g). **fail-closed discipline**:
미포함/미증명/함의/absent/netting/None/stale/double-use/overwrite에 대한 술어는 절대 vacuous permissive가 되지 않으며,
`POST_TRADE_ADMISSIBLE`/complete는 *양성 conjunction identity 증명*을 요구하고(잔여 fall-through 금지 — #16 CRITICAL),
각 가드에 **both-ways canary**(가드가 실제로 발화함 ∧ 정당한 통과를 막지 않음)를 붙인다.

### 4.0 PTF-INV-001..018 전수 실현 표 (카운트 대조 전수화·무저작 0)

| PTF-INV | 명제 (ADR §6) | Phase-1 실현 | Phase-1/잔여 |
|---|---|---|---|
| 001 Complete Exact Obligation Set | 모든 effect가 exact classification + greatest-credible leg set | `obligation_leg_set_complete`(§5.1·∅⇒False) | L1 substrate |
| 002 Finality Dimensions Orthogonal | 10 dimension 상호 non-implication | **`finality_dimensions_orthogonal`(§5.1)** | **L1 core (PTF-EV-001)** |
| 003 Identity and Lineage Exact | exact source·account·entity·instrument·generation·supersession | `EconomicObligationRecord`(IndependentIdArtifact §2.1) | L1 substrate |
| 004 Absence Is Not Finality | silence·cutoff·missing-page·flat-position·missing-ACK ≠ final/absent | `monetary_leg_conservative`·`absence_is_negative_evidence_only`(§5.3/§5.6) | **L1 core (PTF-EV-002/008)** |
| 005 Finality Proof Class-Specific | global SETTLED/CLOSED/confidence ≠ per-field proof | `finality_proof_class_specific`(§5.7) | L1 substrate |
| 006 UNKNOWN Is Restrictive | unknown/stale/conflicting ⇒ conservative capacity·block | `post_trade_disposition`(§5.8 전순위) | L1 core |
| 007 No Unproven Netting or Reuse | receivable ⊄ payable-funding·pending ⊄ available | `netting_requires_positive_proof`·`missing_counterleg_is_adverse`(§5.3) | **L1 core (PTF-EV-002)** |
| 008 RCL Is the Sole Capacity Authority | only RCL mutates; PTOL/finality create no transition | **구조적 부재**(§4.4·§5.7 — release 필드·술어 0) | L1 (구조) |
| 009 Obligation Transition Transfers Not Releases | closure는 transfer이지 release 아님 | `post_trade_consequence_all_false`(§5.7) | L1 substrate / coupling L2/3 |
| 010 Cash Semantics Exact | 6 cash kind non-substitution | `cash_kind_matches_requirement`(§5.4) | L1 substrate / availability L2/3 |
| 011 Collateral Encumbrance Conserved | free+encumbered 동시 계상·pledge-twice 금지 | **`collateral_no_double_use`(§5.4)** | **L1 core (PTF-EV-004)** |
| 012 Borrow Lifecycle Exact | locate/loan/recall/return/buy-in 구분 | 어휘 substrate | not-L1 (PTF-EV-005 L2/3) |
| 013 Correction Reopens Affected Finality | append new version·preserve old+new·advance generation | append-only-no-overwrite(§5.2 `REJECTED_OVERWRITE`) | L1 substrate / propagation L2/3 |
| 014 Statement Coverage/Independence Proven | exact coverage·revision·no common-mode independence | **`statement_coverage_complete`·`statement_sources_independent`(§5.6)** | **L1 core (PTF-EV-008)** |
| 015 Active Generation Negative Gate | RCL/authority/egress가 current generation 능동 검증 | generation-monotone 구조(§3.2) | not-L1 (fence runtime L2/3) |
| 016 External Economic Egress Non-Bypassable | PTOL 등 credential+route 보유 금지 | **구조적 부재**(§4.4 — credential/route/send 필드 0) | L1 (구조) / egress runtime L2/3 |
| 017 Economic Effect Outlives Artifacts | policy/proof/session expiry가 obligation 만료 못 함 | `post_trade_consequence_all_false`·time no-revival 주입 | L1 substrate / L2/3 |
| 018 Evidence and Recovery Do Not Revive | doc/replay/recovery ≠ prevention·no re-arm | frozen record + liveauth/sbr no-revival 주입 | not-L1 (PTF-EV-012 L2/3) |

**18/18 전수 실현·무저작 0.** core L1 = 002·004·007·011·014(+006 disposition)·008/016 구조; 나머지는 substrate 또는
not-Phase-1 명시. **staged 정직 분리**: core INV도 L1 부분만 — orthogonality/idempotency/completeness는 L1, capacity
coupling·generation fence·availability/discharge PROOF은 L2/3.

### 4.1 finality-dimension orthogonality 중앙 불변식 (ADR §12; PTF-EV-001; PTF-INV-002·PTF-AC-001)

**중앙 결정(IMPLEMENTATION-PLAN-002 line 221 명시 지목 property test)**: Final Quantity Proof는 broker order의 final
cumulative filled quantity + zero remaining executable quantity만 증명하고(§12 line 338·§1 line 23 "Final Quantity
Proof establishes only final cumulative filled quantity and zero remaining executable quantity ... It does not prove
any post-trade obligation final"), settlement·cash·fee·custody·borrow·delivery·title finality를 증명하지 않는다(§12
line 340–345, 6 non-implication). **10 finality dimension은 서로 함의하지 않는다**(PTF-INV-002 verbatim "do not imply
one another"). 실현(구조적):

1. **`finality_dimensions_orthogonal`에 permissive 기본값 부재**: dimension별 proven/unknown을 `PostTradeFinalityProof`
   가 개별 bind하고, **한 dimension PROVEN이 다른 dimension을 PROVEN으로 만들지 않는다**(non-implication matrix). 각
   dimension의 기본은 UNKNOWN(PTF-INV-006). `ORDER_FQP` PROVEN 입력 ⇒ 나머지 9 dimension은 여전히 UNKNOWN(§4.5-B).
   **M1 명제 확정(§5.1)**: 술어는 `claimed_final_dimension`의 **자기 proof만** 참조하며(`dimension_proof_present.get
   (claimed) is True`), **all-UNKNOWN·빈 map ⇒ `False`**(구조 가드 — vacuous-True 차단). claimed 이외 entry를 읽지
   않으므로 non-implication이 구조적으로 성립한다.
2. **trade-level boolean 부재**: `finality`는 universal trade-level bool이 아니다(§5.10 line 144 "not a universal
   trade-level boolean"). global `SETTLED`/`CLOSED`로 per-dimension proof를 대체 불가(PTF-INV-005). **fall-through로
   "all final" 승격 금지** — 각 dimension은 자기 proof를 요구.
3. **capacity/risk 미산출**: dimension proven이 capacity release·available cash·title를 만들지 않는다(PTF-INV-009·§4.7
   `post_trade_consequence_all_false`) — rcl/are 주입 소비.

**canary(both-ways)**: (a) `ORDER_FQP` PROVEN 단독으로 settlement/cash/custody dimension을 final로 주장 ⇒ non-implication
가드 발화(False); (b) 각 dimension이 자기 proof를 가지면 그 dimension만 PROVEN(양성 side, 다른 dimension 불변).
**PTF-EV-001 좌표·`/2`·`/3`·`+Broker` 잔여 — 닫지 않음.** [SAFE-004·SAFE-020·SAFE-021 origin/ack/lineage]

### 4.2 fill-to-obligation commit idempotency 중앙 불변식 (ADR §12 line 336; PTF-EV-001; PTF-AC-001)

**중앙 결정**: fill-to-obligation commit은 idempotent이고 originating Intent·attempt·broker order·fill revision·position
transfer·RCL allocation에 causally linked이다(§12 line 336 verbatim "The fill-to-obligation commit SHALL be idempotent
and causally linked to the originating Intent, attempt, broker order, fill revision, position transfer, and RCL
allocation"). claimed terminal outcome 이후 발견된 fill은 idempotently 적용·obligation 생성/정정·generation advance·
capacity 보존(§12 line 347). 실현(구조적):

1. **`obligation_commit_idempotent -> ObligationCommitOutcome`(6종, §2.2-6)**: 선행 게이트 3 + classify 매핑 — (i)
   **lineage present**(correction 시 `supersedes_ref` not None; 부재 ⇒ `REJECTED_NO_LINEAGE`, §20 line 460), (ii)
   **history preserved**(원본 append-only retained·not overwritten; overwrite ⇒ `REJECTED_OVERWRITE`, §11 line 330·§20
   line 460), (iii) **`prior is None`(첫 commit) ⇒ `COMMITTED_ONCE`**(classify 선행 게이트 — prior 부재를 classify
   호출 전 분리, 없으면 NOT_COMPARABLE로 정당 최초 commit 영구 거부), (iv) **at-most-once commit**(canonical
   `classify_record_pair(incoming.id, incoming.digest, prior.id, prior.digest, a_idempotency_id=incoming.key,
   b_idempotency_id=prior.key)` 실측 4-pos+2-kw: `IDEMPOTENT_DUP`⇒`IDEMPOTENT_REPLAY` no-op·`CRITICAL_CONFLICT`(same
   **primary** id·diff bytes)⇒`REJECTED_CONFLICT`·`DIVERGENT_EMISSION`(same **idempotency** id·diff bytes)⇒`REJECTED_
   CONFLICT`·`DISTINCT`/`NOT_COMPARABLE`⇒`REJECTED_UNKNOWN`).
2. **at-most-once = obligation effect 1회**: 정당 commit(`COMMITTED_ONCE`)은 effect count를 1로, 재적용(`IDEMPOTENT_
   REPLAY`)은 no-op. **위조 2축(둘 다 `REJECTED_CONFLICT`·contain-both·no LWW)**: (a) same primary id·diff bytes ⇒
   `CRITICAL_CONFLICT`(obligation 위조), (b) same idempotency key·diff bytes ⇒ `DIVERGENT_EMISSION`(두 상이 fill이
   한 key 주장). 어느 위조도 silent double-commit 안 됨.
3. **canonical 원시 직접 앵커(§0.4e)**: iap `IDEMPOTENT_REPLAY`(authorization)·rcl `ApplyReason.IDEMPOTENT_REPLAY`
   (capacity-command)·nontrade `CorrectionReversalOutcome.IDEMPOTENT_REPLAY`(event-application)와 별개 축 — PTF은
   canonical `classify_record_pair`를 직접 소비(형제 import 없음).

**canary(both-ways)**: (a) lineage 부재/overwrite/same-key-diff-bytes ⇒ REJECTED_*(가드 발화); (b) prior None인 첫 fill
⇒ `COMMITTED_ONCE`(정당 commit, 양성 side). **late-fill canary(§7)**: claimed terminal 이후 동일 fill(same bytes)을 재
적용 ⇒ `IDEMPOTENT_REPLAY`(effect+0); 새 fill revision(diff obligation, distinct id)이면 새 version commit(§12 line
347). **PTF-EV-001 좌표·`/2`·`/3`·`+Broker` 잔여 — 닫지 않음.** [SAFE-020 lineage·SAFE-051/052 evidence·replay]

### 4.3 no-favorable-default·no-unproven-netting 중앙 불변식 (ADR §13·§9 line 279; PTF-EV-002; PTF-INV-004/007·PTF-AC-002)

**중앙 결정**: uncertain receivable는 payable를 fund 못 하고, pending proceeds는 available cash가 못 되며, unproven
offset은 headroom을 만들지 못한다(PTF-INV-007 verbatim). missing line item·zero estimate는 zero의 proof가 아니다(§13
line 355 verbatim "A missing line item or zero estimate is not proof of zero"). balanced accounting leg를 positively
establish 못 하면 missing counterleg는 explicit·greatest-credible-adverse이고 consumer는 local favorable balancing을
construct 못 한다(§9 line 279 verbatim). 실현(구조적):

1. **`monetary_leg_conservative`(absence≠zero)**: `MonetaryLeg`의 amount가 **None/absent ⇒ UNKNOWN/greatest-credible**
   (favorable-zero 아님); proven zero는 **adequate source의 positive booked-zero**일 때만(주입 confidence CORROBORATED
   + booked flag). estimated/accrued ≠ broker-booked ≠ legally-final(§13 line 355 "Estimated or accrued amounts remain
   distinct from broker-booked and legally final amounts"). favorable rebate/credit는 confirmed adverse obligation을
   offset 못 함(exact enforceable netting proof 없이는 — §13 line 355).
2. **`netting_requires_positive_proof`(구조적, §0.4d)**: receivable(CREDIT)·payable(DEBIT)가 **둘 다 present(not None)·
   비음수로 gross 병존** ∧ same scope(account/currency/value-date/legal-entity/settlement-system) ∧ **injected
   enforceable-netting proof token present**일 때만 netting valid; 하나라도 부재 ⇒ 둘 다 gross(netting 불가). **netting
   은 flag가 아니라 both-gross-magnitude 병존 + proof-token 부재로 파생** — caller가 flag로 위조 불가(#18/#21 no-netting
   선례).
3. **`missing_counterleg_is_adverse`**: balanced pair(debit+credit)를 positively establish 못 하면 missing counterleg는
   explicit·greatest-credible-adverse-union이고, consumer는 **local favorable balancing entry를 construct 못 한다**(§9
   line 279 — 구조적으로 favorable-local-construct 필드·술어 부재).

**canary(both-ways)**: (a) missing line item을 zero로·uncertain receivable를 payable fund로·favorable local balancing
시도 ⇒ UNKNOWN/gross/adverse(가드 발화); (b) booked-zero(positive)·proven-enforceable-netting(proof present)·positively-
established counterleg ⇒ 정당 통과(양성 side). **PTF-EV-002 좌표·`/2`·`/3`·`+Broker` 잔여 — 닫지 않음.** [SAFE-012·
SAFE-013 envelope·SAFE-022 field reconciliation]

### 4.4 collateral no-double-use + cash-kind non-substitution + capacity-non-mutating 중앙 불변식 (ADR §15·§14·§1 line 21; PTF-EV-004; PTF-INV-008/010/011·PTF-AC-004)

**중앙 결정**: same collateral unit은 free+encumbered 동시 계상·two-obligation pledge·confirmed-release 전 reuse 금지
(§15 line 386 verbatim·PTF-INV-011). ledger/pending/settled/withdrawable/buying-power/collateral-eligible cash는 silent
substitution 금지(PTF-INV-010). only RCL이 capacity를 mutate(§1 line 21·PTF-INV-008). 실현(구조적):

1. **`collateral_no_double_use`(보존)**: `CollateralAllocation`의 한 unit에 대해 allocation state는 **상호배타(free XOR
   encumbered)**이고, pledge 합 ≤ available(구조적 보존 — magnitude 합 검사). same unit이 두 obligation에 pledge되거나
   confirmed-release 전 reuse되면 False. **flag가 아니라 magnitude 보존 파생**(#18/#21 구조-파생 선례).
2. **`margin_collateral_states_distinct`(8상태 non-implication)**: `MarginCollateralState` 8상태는 서로 함의하지 않는다
   (§15 line 385 "No one state implies another"). broker favorable margin/buying-power/collateral figure는 Critical
   Input·ceiling(주입 좌표)이지 unconditional proof 아님(§15 line 387). haircut/eligibility/FX/valuation/margin-model
   change는 material·invalidate dependent(§15 line 389 — venue material-change 주입).
3. **`cash_kind_matches_requirement`(6 kind, substrate — M3 rename)**: `CashKind` 6종은 별개 타입이고 요구≡가용
   (identity)일 때만 사용 가능(silent substitution 불가).
   sale proceeds/expected dividends/pending FX/receivables/buying-power는 settled/reusable cash가 아니다(§14 line 375).
   **substrate 경계**: 이 non-substitution은 L1이나 **availability PROOF(buying-power→withdrawable 전환)은 PTF-EV-003
   `EV-L2/3` 잔여**.
4. **capacity-non-mutating(구조적 부재, PTF-INV-008)**: PTF 모델·술어에 **capacity를 release/transfer/quarantine할 필드도
   술어도 존재하지 않는다**(unconstructable — nontrade `AllFalseNonTradeAuthority`·rcl `AllFalseAuthority` 동형). obligation
   closure는 rcl이 transfer하고 PTF은 obligation-set을 produce만 한다. 필드 부재가 곧 강제다.

**canary(both-ways)**: (a) free+encumbered 동시·pledge-twice·reuse-before-release·cash-kind 치환·capacity release 시도
⇒ False/구조적 부재(가드 발화); (b) 상호배타 allocation·pledge 합 ≤ available·구분된 cash kind ⇒ 정당 통과(양성 side).
**PTF-EV-004 좌표·`/2`·`/3`·`+Broker` 잔여 — 닫지 않음.** [SAFE-013·SAFE-014 non-bypassable·SAFE-024 partial/async]

### 4.5 방향 극성 검산 — settlement-direction·finality-monotonicity 진리표 (ADR §9·§12·§21; 사전 브리핑 지목 함정·#16 C1 방향-반전 교훈 선제 봉합)

**settlement 방향(채권/채무·인도/수취)과 finality 단조(미확정→확정 단방향·역전 금지)는 두 별개 극성 축**이므로 진리표로
검산한다(#16이 §1:25 smallest vs §10:276 largest를 혼동한 CRITICAL 교훈 동형 — 극성 오독이 fail-open). **명제 상이 명시**:
아래 두 진리표는 nontrade §4.5(split quantity/price reciprocal multiplicative)와 **구조는 유사하나 명제가 다르다** —
PTF-A는 obligation-leg debit/credit netting-proof, PTF-B는 finality-dimension monotone non-implication이다.

**진리표 A — obligation-leg direction × netting 검산(no-favorable-netting, PTF-INV-007)**:

| receivable(CREDIT) ＼ payable(DEBIT) | 둘 다 present·gross·same-scope | proof-token present | netting 판정 |
|---|---|---|---|
| **둘 다 present + same scope + proof-token present** | ✓ | ✓ | ✓ **netting valid**(exact enforceable — §14 line 377·§13 line 355) |
| **둘 다 present + same scope + proof-token 부재** | ✓ | ✗ | ✗ **gross**(uncertain receivable가 payable fund 못 함 — fail-open 차단) |
| **둘 다 present + scope 상이(account/currency/value-date/entity/settle-system)** | ✓ | — | ✗ **gross**(§14 line 377 "cannot be netted unless ... legal enforceability, operational finality, timing, amount, common-mode independence, and current availability") |
| **한쪽 None/absent** | ✗ | — | ✗ **missing counterleg adverse**(§9 line 279 — local favorable balancing 금지) |

**netting valid cell = 1**(all-conjunct); **gross/adverse cell = 3**. **fail-open 함정 명시**: uncertain receivable를
payable에 netting해 unproven headroom을 만드는 것(§25.5 rejected "Pending receivables may fund payables") — proof-token
부재 cell이 이를 차단. delivery↔receipt·encumbrance↔release도 동형(opposite-direction pair·netting proof 요구).

**진리표 B — finality-dimension monotone × non-implication 검산(PTF-INV-002·PTF-INV-009)**:

| dimension 상태 전이 | 정당? | 근거 |
|---|---|---|
| `UNKNOWN` → `PROVEN` **with dimension-specific proof** | ✓ 정당(단방향) | §11 proof recipe |
| `UNKNOWN` → `PROVEN` **without proof**(silence/cutoff/flat-position/statement-balance) | ✗ **fail-open 차단** | PTF-INV-004 "Absence Is Not Finality" |
| dimension_X `PROVEN` ⇒ dimension_Y `PROVEN`(X≠Y) | ✗ **non-implication 차단** | PTF-INV-002 "do not imply one another" |
| `PROVEN` ⇒ capacity-release / available-cash / legal-title / permission | ✗ **finality-grants-nothing 차단** | PTF-INV-009·§10 line 312 |
| generation N → N+1 (correction 시 append·supersede) | ✓ 정당(monotone 증가) | §11 line 330·PTF-INV-013 |
| generation N → N-1 (revert) | ✗ **차단**(ordering monotone) | §3.2·PTF-INV-015 |
| version N `CLOSED` → destructive overwrite | ✗ **차단** | §11 line 330·§20 line 460 `REJECTED_OVERWRITE` |
| version N `CLOSED` → 새 correction version N+1 (append) | ✓ 정당(비파괴 supersede) | §10 line 312 "can be superseded ... without destructive overwrite" |
| **proof(generation N) 후 correction이 generation N+1로 advance** ⇒ **prior proof는 current 아님**(reopen) | ✗ **stale proof 차단**(M2) | §11 line 330 "A later correction supersedes the proof, advances generation"·PTF-INV-013·`finality_proof_current`(§5.7) |

**정당 cell = 3**(proof 전이·generation 증가·비파괴 supersede); **차단 cell = 6**(9행 전수 — M2로 9번째 추가). **핵심
(defect-class #2)**: "finality 단조"는 naive "once-proven-always-proven"이 아니다 — correction이 finality를 **reopen**할
수 있다(PTF-INV-013). 실제 monotone은 (a) **generation monotone 증가**(ordering — 역전 금지), (b) **UNKNOWN→PROVEN은
proof-only 단방향**(자발적 승격 금지), (c) **history append-only**(destructive overwrite 금지), (d) **PROVEN → consequence
함의 금지**(finality-grants-nothing), (e) **proof는 자기 bound generation이 active generation과 같을 때만 current**
(correction이 generation을 advance하면 prior proof는 stale ⇒ reopen — 9번째 행·M2)이다. **역전 금지 = favorable state
(flat position·FINALITY_PROVEN·settled·statement balance)가 capacity release·obligation discharge를 만들지 못함**(§1
line 27·PTF-INV-009/017).

**검산 규칙(M2 정정 — cell별 소유 술어 명시)**: v1.0의 "3 술어가 각 cell 검사"는 부정확했다(행 5·6 generation-monotone은
그 3 술어가 검사하지 않음). 실제 cell별 소유: **행 1–3(UNKNOWN→PROVEN·non-implication)** = `finality_dimensions_
orthogonal`(§5.1); **행 4(PROVEN⊄consequence)** = `post_trade_consequence_all_false`(§5.7); **행 5·6(generation
monotone 증가·역전 금지)** = **ordering 좌표(§3.2)·`finality_proof_current`(§5.7)**(그 3 술어가 아님); **행 7·8·9
(overwrite·append supersede·proof-reopen)** = `obligation_commit_idempotent`(§5.2 `REJECTED_OVERWRITE`)·`finality_
proof_current`(§5.7 — 9번째). 각 cell은 **별도 conjunction**(fall-through로 PROVEN/consequence 승격 금지 — #16
CRITICAL). **수치 하드코딩 0** — 전부 enum non-implication·boolean·generation 정수 비교·magnitude 병존 비교. [SAFE-020
lineage·SAFE-032/033 current-facts constrain future·SAFE-050 fail-closed activation]

### 4.6 fill-commit idempotency·late-fill 진리표 (ADR §12 line 336/347; PTF-EV-001)

**fill-to-obligation commit 재적용은 idempotent version check로만 정당**하며, same-**idempotency**-key·diff-bytes는
double-commit이 아니라 conflict(`DIVERGENT_EMISSION`)다(canonical `classify_record_pair` 실측). **선행 게이트(classify
이전, 순서)**: correction 시 `supersedes_ref` 부재 ⇒ `REJECTED_NO_LINEAGE`(§20 line 460); `original_retained is not
True`(overwrite) ⇒ `REJECTED_OVERWRITE`(§11 line 330); **`prior is None`(첫 commit) ⇒ `COMMITTED_ONCE`**(prior 부재 시
classify는 NOT_COMPARABLE를 반환하므로 정당 최초 commit이 영구 거부되지 않도록 선행 분기). 그 다음 `classify_record_pair`
(4-positional+2-keyword) 호출:

**진리표 — 선행 게이트 통과 후 `classify_record_pair(...)` (실측 `record_pair.py`) → `ObligationCommitOutcome`**:

| classify 반환 (실측 라인) | → `ObligationCommitOutcome` | obligation effect count |
|---|---|---|
| `IDEMPOTENT_DUP` (same primary/idempotency id·same bytes, :94/:101) | `IDEMPOTENT_REPLAY` | **+0 (no-op·late-fill 무해)** |
| `CRITICAL_CONFLICT` (same **primary** id·diff bytes, :96) | `REJECTED_CONFLICT` | **+0 (obligation 위조·contain-both·no LWW)** |
| `DIVERGENT_EMISSION` (same **idempotency** id·diff bytes, :103) | `REJECTED_CONFLICT` | **+0 (두 상이 fill이 한 key 주장·contain-both)** |
| `DISTINCT` (id·key 둘 다 상이, :105) | `REJECTED_UNKNOWN` | +0 (fail-closed) |
| `NOT_COMPARABLE` (digest None, :87) | `REJECTED_UNKNOWN` | +0 (fail-closed) |

(선행 게이트 outcome: `REJECTED_NO_LINEAGE`·`REJECTED_OVERWRITE` +0; `COMMITTED_ONCE`(prior None) +1.) **RecordPairKind
5-member 전수 매핑** — DIVERGENT_EMISSION 미매핑·COMMITTED_ONCE 구조적 도달불가 결함(#21 C2 유형)을 선제 봉합.

> **M7 각주 — prior 선정 계약(nontrade `predicates.py:526` 선례를 fill-commit 2-축으로 확장)**: nontrade는 prior =
> "incoming의 **idempotency key** 공유 레코드(없으면 None)"로 단일 축 선정한다. PTF fill-commit은 **primary obligation
> identity와 idempotency key 두 identity 축**을 가지므로(§2.2-7), prior = **incoming의 primary obligation identity를
> 공유하는 레코드, 없으면 idempotency key를 공유하는 레코드, 둘 다 없으면 None**으로 선정한다. **이 2-축 선정이 두
> 오독을 차단**한다: (i) key-only 선정이면 same-primary-id·diff-key 위조가 prior=None⇒`COMMITTED_ONCE`로 흘러
> `CRITICAL_CONFLICT`를 **우회**함(막음); (ii) primary-only 선정이면 same-key·diff-primary 위조가 `DIVERGENT_EMISSION`을
> **놓침**(막음). `classify_record_pair`는 두 축(`a_identity`/`b_identity` + keyword `a_idempotency_id`/`b_idempotency_
> id`)을 **모두** 비교하므로 선정된 prior 하나로 두 위조가 각각 정확한 kind로 접힌다. **`DISTINCT`는 prior가 두 축을
> **둘 다** 공유하지 않는 경우 — 즉 caller 선정 계약 위반 시에만** 발생하며 `REJECTED_UNKNOWN`으로 fail-closed(정당
> 최초 commit은 `prior is None` 선행 게이트로 `COMMITTED_ONCE`, classify 미도달).

**late-fill canary(§7 명시)**: (a) **idempotent late-fill**: claimed terminal 이후 동일 fill(same idempotency key·same
bytes)을 재적용 ⇒ 첫 회 prior=None ⇒ `COMMITTED_ONCE`(effect+1)·2회+ prior 존재·same bytes ⇒ `IDEMPOTENT_DUP` ⇒
`IDEMPOTENT_REPLAY`(effect+0) ⇒ 총 effect count == 1(§12 line 347 무해성). (b) **forgery 2종 분리**: (b1) same **primary**
id·diff canonical digest ⇒ `CRITICAL_CONFLICT` ⇒ `REJECTED_CONFLICT`; (b2) same **idempotency** key·diff canonical
digest ⇒ `DIVERGENT_EMISSION` ⇒ `REJECTED_CONFLICT` — 어느 위조도 silent double-commit 안 됨. (c) **both-ways 정당
통과**: prior=None인 서로 다른 정당 fill은 각각 `COMMITTED_ONCE`. [SAFE-020 lineage·SAFE-051/052 evidence·replay]

### 4.7 finality-grants-nothing / representation ≠ enforcement 중앙 불변식 (ADR §10 line 312·§1 line 19·§21 line 492; core substrate)

**중앙 결정(본 ADR 최핵심 안전 성질)**: 어떤 lifecycle state도 그 자체로 capacity release·available cash·legal title·
permission을 create하지 않는다(§10 line 312 verbatim "No lifecycle state creates capacity release, available cash,
legal title, or permission"). `SATISFIED_PENDING_FINALITY`는 not final; `FINALITY_PROVEN`은 exact declared leg·proof
class만 증명(§10 line 312·§11 line 328). flat position·closed order·passed settlement date·`FINALITY_PROVEN` artifact·
favorable receivable·statement balance는 그 자체로 capacity를 release 못 함(§1 line 27 verbatim). 실현:

1. **`post_trade_consequence_all_false`**: `AllFalsePostTradeConsequence`는 all-false — `releases_capacity`·`makes_cash_
   available`·`proves_legal_title`·`grants_permission`·`authorizes_transmission` 어떤 True도 unconstructable(rcl
   `AllFalseAuthority`·nontrade `AllFalseNonTradeAuthority` 동형). lifecycle state·finality proof 무엇이든(FINALITY_
   PROVEN도) consequence는 all-false.
2. **finality proves the LEG, not the CONSEQUENCE**: `FINALITY_PROVEN` ⇒ 오직 그 dimension·leg·class의 finality; capacity
   release·availability·title는 별개(§4.5-B 진리표 4행). RCL이 current proof·policy·generation·scope·obligation-set·
   resulting-asset·risk-decision·writer-epoch·limits를 능동 검증 후에만 transfer(§21 line 492) — PTF 소유 아님.
3. **external egress 구조적 부재(PTF-INV-016)**: PTF 모델에 credential·route·send 필드가 없다(egress-non-bypassable —
   §1 line 31·§4.4). external economic instruction 구성·전송은 egress(ADR-002-013) 소유.

**canary(both-ways)**: (a) 어떤 lifecycle state로도·FINALITY_PROVEN으로도 consequence True/transmit 시도 ⇒ 구성 불가
(가드 발화); (b) finality proof는 결코 consequence를 부여 안 함 — 양성 side 없음(#18 §4.4·#21 §4.4 동형). [SAFE-010·
SAFE-011 non-substitution·SAFE-014/015 non-bypassable]

### 4.8 ∅-공허 fail-closed (양방향 명시 — #10/#11/#16/#18/#21 code-review MAJOR 교훈)

빈 입력의 **모든 방향**을 명문화한다. PTF 금지 동사(**ADR 전 조항 스윕 §1–§24 — 개별 계수**): (1) **treat-FQP-as-post-
trade-final**(§12·§23·PTF-INV-002) · (2) **treat-absence-as-zero-or-final**(§13 line 355·PTF-INV-004) · (3) **net-
unproven-receivable-against-payable**(PTF-INV-007·§25.5) · (4) **construct-favorable-local-counterleg**(§9 line 279) ·
(5) **substitute-cash-kind**(PTF-INV-010·§25.4) · (6) **double-use-collateral**(§15 line 386·PTF-INV-011) · (7) **treat-
event-state-as-obligation-final**(§17 line 418) · (8) **treat-statement-absence-as-negative-evidence-without-coverage**
(§19 line 448·PTF-INV-014) · (9) **treat-common-mode-as-independent**(§19 line 445) · (10) **release-capacity-on-
finality**(§10 line 312·§21 line 492·PTF-INV-008/009) · (11) **transmit-external-economic-instruction**(§1 line 31·
PTF-INV-016) · (12) **transfer-finality-proof-across-leg**(§11 line 328) · (13) **destructive-overwrite-history**(§11
line 330·§20 line 460) · (14) **double-commit-fill**(§12 line 336·§4.6) · (15) **revive-on-recovery-or-replay**(§24
line 552·PTF-INV-018). **금지 동사 = 15개**(개별 번호 계수).

**단일 disposition 생산자 재매핑**: 아래 표의 **모든 행이 `post_trade_disposition(...) -> PostTradeDisposition`(§5.8)의
반환값으로 재매핑**된다 — "∅ ⇒ 별도 처리" 무주 위임 없음(#21 C1 선례). disposition 우선순위(전순서·결정적):
`POST_TRADE_CONFLICTED` > `POST_TRADE_QUARANTINED_UNKNOWN` > `POST_TRADE_TRAPPED` > `POST_TRADE_BLOCK_NEW_RISK` >
`POST_TRADE_ADMISSIBLE`.

| # | 빈/미증명 입력 | 금지 방향(vacuous permissive 차단) | 허용 방향(양성 side) | `post_trade_disposition` 반환 | 근거 |
|---|---|---|---|---|---|
| 1 | **빈 `required_legs` set** | 평가 leg 부재 ⇒ "no risk" 아님 ⇒ completeness 증명 불가 ⇒ **술어 내부 구조 가드** `if not required_legs: return False` | applicable leg subset 전부 포함 ⇒ `obligation_leg_set_complete is True` | `POST_TRADE_BLOCK_NEW_RISK` | §9·PTF-INV-001; rcl `credible_union_capacity` empty⇒`ValueError` 선례 |
| 2 | **finality dimension proof 부재** | dimension UNKNOWN ⇒ PROVEN 자발 승격 불가·다른 dimension 함의 불가 | dimension-specific proof present ⇒ 그 dimension PROVEN | `POST_TRADE_BLOCK_NEW_RISK` | §12·PTF-INV-002/004; §4.5-B |
| 3 | **monetary leg amount None/absent** | missing line item ⇒ zero 아님 ⇒ UNKNOWN/greatest-credible | booked-zero(positive) ⇒ proven zero | `POST_TRADE_BLOCK_NEW_RISK` | §13 line 355 |
| 4 | **netting proof-token 부재** | both gross + proof 부재 ⇒ netting 불가 ⇒ 둘 다 gross | both present·same-scope·proof-token present ⇒ netting valid | `POST_TRADE_BLOCK_NEW_RISK` | PTF-INV-007; §4.5-A |
| 5 | **counterleg missing(None)** | balanced pair 미성립 ⇒ missing counterleg adverse | positively-established counterleg ⇒ balanced | `POST_TRADE_BLOCK_NEW_RISK` | §9 line 279 |
| 6 | **collateral allocation 이중(free∧encumbered)** | 상호배타 위반·pledge-twice·reuse-before-release ⇒ 보존 위반 | 상호배타·pledge 합 ≤ available ⇒ 통과 | `POST_TRADE_CONFLICTED` | §15 line 386·PTF-INV-011 |
| 7 | **event-state = APPLIED_LOCAL/RECONCILED(nontrade 주입)** | event state로 obligation-finality 주장 ⇒ non-implication 차단 | dimension-specific proof present ⇒ 그 dimension만 PROVEN | `POST_TRADE_BLOCK_NEW_RISK` | §17 line 418 |
| 8 | **statement coverage 미완(expected ⊄ received)** | missing interval/page/cursor ⇒ incomplete ⇒ absence는 negative evidence 아님 | expected ⊆ received·revision·cutoff present ⇒ complete | `POST_TRADE_BLOCK_NEW_RISK` | §19 line 443/448·PTF-INV-014 |
| 9 | **statement sources common-mode(shared dep)** | shared book/parser/administrator/transport ⇒ not-independent | disjoint shared-dependency set ⇒ corroborate | `POST_TRADE_CONFLICTED` | §19 line 445 |
| 10 | **finality proof cross-leg reuse 시도** | one leg/class proof를 다른 것에 patch ⇒ non-transferable 위반 | exact same leg/class ⇒ proof valid | `POST_TRADE_CONFLICTED` | §11 line 328 |
| 11 | **`classify_record_pair` = `CRITICAL_CONFLICT`(same primary id·diff bytes, :96)** | obligation 위조 ⇒ `REJECTED_CONFLICT`(contain-both·no LWW) | same primary id·**same** bytes ⇒ `IDEMPOTENT_DUP`⇒`IDEMPOTENT_REPLAY` | `POST_TRADE_CONFLICTED` | §4.6·`record_pair.py:96` |
| 12 | **`classify_record_pair` = `DIVERGENT_EMISSION`(same idempotency id·diff bytes, :103)** | 두 상이 fill이 한 key ⇒ `REJECTED_CONFLICT`(contain-both) | same idempotency id·**same** bytes ⇒ `IDEMPOTENT_REPLAY` | `POST_TRADE_CONFLICTED` | §4.6·`record_pair.py:103` |
| 13 | **`classify_record_pair` = `DISTINCT`(:105)/`NOT_COMPARABLE`(digest None, :87)** | 판정 불가 ⇒ `REJECTED_UNKNOWN` | (해당 없음 — 정당 최초 commit은 `prior is None` 선행 게이트로 `COMMITTED_ONCE`) | `POST_TRADE_QUARANTINED_UNKNOWN` | §4.6·`record_pair.py:87/105` |
| 14 | **FieldConfidenceClass = UNKNOWN/CONFLICTED(recon 주입)** | UNKNOWN ⇒ quarantine / CONFLICTED ⇒ 모순 | 전 material field CORROBORATED ⇒ field gate 통과 | UNKNOWN⇒`QUARANTINED_UNKNOWN` / CONFLICTED⇒`CONFLICTED` | §11·PTF-INV-005; `recon/predicates.py:107` |
| 15 | **capacity-release / transmit 시도(어떤 lifecycle state)** | release/transmit ⇒ **구조적 부재**(필드·술어 0) | (양성 side 없음 — finality는 consequence 부여 안 함) | **disposition 불변** — 어떤 state도 상향 못 시킴 | §10 line 312·§1 line 21·PTF-INV-008/009/016 |
| 16 | **settlement/custody/borrow availability·discharge(not-Phase-1 주입)** | 미증명 availability/discharge ⇒ trapped(zero-risk 아님) | (L2/3 잔여 — Phase-1은 UNKNOWN 유지) | `POST_TRADE_TRAPPED` | §14/§16/§18; PTF-EV-003/005/007 L2/3 |
| 17 | **margin/collateral state implication(observed⇒claimed)** | 8상태 non-implication 위반 ⇒ 한 상태로 다른 상태 주장 | `observed_state`가 `claimed_state`를 함의 안 함 ⇒ distinct | `POST_TRADE_BLOCK_NEW_RISK` | §15 line 385·PTF-INV-011(C1 신규) |
| 18 | **cash-kind 치환(requested≠available)** | buying-power를 withdrawable로 취급 ⇒ `cash_kind_matches_requirement` False | `requested is available`(identity) ⇒ 충족 | `POST_TRADE_BLOCK_NEW_RISK` | PTF-INV-010·§25.4·§5.4(C1 신규 — M3) |
| 19 | **event-obligation leg 누락(required ⊄ present)** | 9축(`EventObligationLegKind`) 중 누락 ⇒ incomplete | required subset 전부 present ⇒ complete | `POST_TRADE_BLOCK_NEW_RISK` | §17 line 416·§5.5(C1 신규) |
| 20 | **absence를 무증명 negative로 읽음** | coverage 미완·correction-semantics 미지지에서 line-item 부재를 "무의무"로 ⇒ `absence_is_negative_evidence_only` False | coverage complete ∧ correction-semantics 지지 ∧ source-capability 지지 ⇒ absence가 negative | `POST_TRADE_BLOCK_NEW_RISK` | §19 line 448·PTF-INV-004(C1 신규 — M6) |
| 21 | **global-flag로 per-field proof 대체** | `SETTLED`/`CLOSED`/confidence-score/statement-flag/operator-decision로 class-specific proof 대체 ⇒ `finality_proof_class_specific` False | exact class-specific proof + `does_not_prove` present ⇒ True | `POST_TRADE_CONFLICTED` | §11 line 320·PTF-INV-005(C1 신규) |
| 22 | **stale-generation proof(bound<active)** | correction이 generation advance 후 prior proof ⇒ `finality_proof_current` False(reopen) | `proof.bound_generation == active_generation` ⇒ current | `POST_TRADE_BLOCK_NEW_RISK` | §11 line 330·PTF-INV-013·§4.5-B 9행(C1 신규 — M2) |

**행 수 = 22**(개별 계수 1–22 — C1으로 6행 신설[17–22]). **§5.8 disposition 16 bool conjunct ↔ §4.8 행 1:1**: leg_set(1)·
finality_orthogonal(2)·monetary(3)·netting(4)·counterleg(5)·collateral(6)·event_state(7)·statement_coverage(8)·
sources_independent(9)·proof_non_transferable(10)·margin_states(17)·cash_kind(18)·event_legs(19)·absence_gate(20)·
proof_class_specific(21)·proof_current(22) = **16 bool** + commit_outcome(11/12/13) + field_confidence(14) + 구조적
부재(15) + availability(16). **§7 ∅-공허 회귀 목록과 1:1**(§7 "∅ 케이스" 22항목). **양방향 규율**: 각 빈-입력 가드는
(a) 금지 방향(가드 발화 canary)과 (b) 허용 방향(정당 통과 canary)을 **둘 다** property로 검증한다(§7). vacuous-admissible도
vacuous-block도 결함이다.

### 4.9 §25 rejected alternatives 구조적 실현 (12/12 — 카운트 대조)

ADR §25는 12 rejected alternative(25.1–25.12)를 열거한다. 본 계약이 각을 **구조적으로 실현**함을 대조(무저작 0):

| § | rejected alternative | 구조적 실현 |
|---|---|---|
| 25.1 | FQP means trade economically final | `finality_dimensions_orthogonal`(§5.1) — 10-dim non-implication |
| 25.2 | broker statement is ledger of truth | `statement_coverage_complete`·`StatementClass`(§5.6) — preliminary/revised/common-mode |
| 25.3 | flat position releases all capacity | `post_trade_consequence_all_false`(§5.7)·capacity-non-mutating(§4.4) |
| 25.4 | buying power is available cash | `CashKind`(6) 타입 구분·`cash_kind_matches_requirement`(§5.4) |
| 25.5 | pending receivables may fund payables | `netting_requires_positive_proof`(§5.3)·§4.5-A |
| 25.6 | transfer ack proves legal title | `CUSTODY_TITLE` dimension non-implication(§5.1) — not-Phase-1 substrate |
| 25.7 | no recall/assignment notice means none | `monetary_leg_conservative`·`event_state_not_obligation_finality`(§5.3/§5.5)·PTF-INV-004 |
| 25.8 | corrections may update old row in place | `REJECTED_OVERWRITE`(§5.2)·append-only(§3.2) |
| 25.9 | PTOL may release capacity when finality proven | capacity-non-mutating 구조적 부재(§4.4·PTF-INV-008) |
| 25.10 | operations may directly send instructions | egress-non-bypassable 구조적 부재(§4.7·PTF-INV-016) |
| 25.11 | priority creates protective settlement capacity | 구조적 부재(§4.4 — priority 필드·capacity 필드 0) |
| 25.12 | recovery/replay/clean statement restores authority | no-revival 주입(§5.7·PTF-INV-018) — not-Phase-1 |

**12/12 실현.** 25.6/25.12는 not-Phase-1 substrate(L2/3 잔여) 명시.

---

## 5. core 술어 — finality-orthogonality · commit-idempotency · no-favorable-default · collateral · event-obligation · statement · finality-proof · disposition (PTF-EV-001/002/004/006/008 substrate)

**핵심 난제**: finality-dimension orthogonality·fill-commit idempotency·no-favorable-default(absence≠zero·netting-proof·
missing-counterleg-adverse)·collateral 보존·event-state≠obligation-finality·statement coverage completeness·finality-
proof class-specificity를 **순수·비전송·fail-closed**로 실현하되 capacity/risk/confidence/event-identity/broker-
capability/egress를 형제에 이연한다. 술어 시그니처는 **입력 = 주입 좌표/frozen 모델**, **출력 = plain `bool` / StrEnum**
(전송·mutate 없음). 각 술어는 **양성 conjunction identity로만 True/ADMISSIBLE** 도달(잔여 fall-through 금지).

### 5.1 finality-dimension orthogonality + obligation-leg completeness (§12/§9; PTF-EV-001 substrate, core L1 슬라이스)

```text
finality_dimensions_orthogonal(
    claimed_final_dimension: FinalityDimensionKind | None,               # 판정 대상 (그 dimension이 final인가)
    dimension_proof_present: Mapping[FinalityDimensionKind, bool | None],  # 주입 per-dim proof (bool|None)
) -> bool
```

- **M1 정정(dead param 삭제·명제 1문장 확정)**: v1.0의 `proven_dimensions` 파라미터는 **`dimension_proof_present`와
  중복**(dimension이 "proven"임은 `dimension_proof_present[dim] is True`와 동치)이라 **삭제**한다. **반환 명제(단일)**:
  *"`claimed_final_dimension`은 **오직 자기 dimension의 proof**로만 final이며, 다른 dimension의 proof는 이 판정에
  전혀 참조되지 않는다"* — 즉 `return (claimed_final_dimension is not None) and (dimension_proof_present.get(claimed_
  final_dimension) is True)`. **구조 가드(§4.1 canary와 정합)**: `if claimed_final_dimension is None or not dimension_
  proof_present: return False`(all-UNKNOWN·빈 map ⇒ vacuous-True 차단 — v1.0 doc:1172 vs §4.1 canary 상충을 이 한 문장
  명제로 해소). non-implication은 **구조적으로** 보장된다 — 함수가 claimed 이외 entry를 **읽지 않으므로** `ORDER_FQP`
  PROVEN이 `SETTLEMENT`/`CASH_AVAILABILITY`/`FEE_FINALITY`/`CUSTODY_TITLE`/`BORROW_DISCHARGE`를 final로 만들 경로가
  없다(§12 line 340). **양극성 `dimension_proof_present[dim]`은 `is True`만**(None/False ⇒ UNKNOWN·not-proven).
- **fail-closed**: proof 부재 dimension은 UNKNOWN(PTF-INV-006); global `SETTLED`/`CLOSED` 입력으로 per-dim proof 대체
  시도 ⇒ False(PTF-INV-005). **fall-through로 "all final" 승격 없음** — 각 dimension 개별 conjunct. **§4.8 행 2(dimension
  proof 부재 ⇒ BLOCK)가 이 술어의 ∅ 방향**이다.

```text
obligation_leg_set_complete(
    required_legs: frozenset[ObligationLegDirection],   # event-class-parametric applicable subset (주입)
    present_legs: frozenset[ObligationLegDirection],
    leg_magnitudes: Mapping[ObligationLegDirection, CanonicalDecimal | None],
) -> bool
```

- **판정**: `required_legs ⊆ present_legs` ∧ 각 leg magnitude present(not None)·finite일 때만 True. **∅ 구조 가드
  (#21 C1 선례)**: `if not required_legs: return False` — 빈 required set은 "no risk"가 아니라 "무엇을 증명해야 하는지
  모름"이므로 vacuous-True로 흐르지 않는다(rcl `credible_union_capacity` empty⇒`ValueError` 선례). missing leg ⇒
  incomplete ⇒ False(§9 line 279 greatest-credible).

**canary**: (a) FQP-only로 다른 dimension final 주장·빈 required set·missing leg ⇒ False(가드 발화); (b) dimension-
specific proof present·required ⊆ present ⇒ True(양성 side). **PTF-EV-001 좌표·`/2`·`/3`·`+Broker` 잔여.**

### 5.2 fill-to-obligation commit idempotency (§12 line 336; PTF-EV-001 substrate, core L1 슬라이스)

```text
obligation_commit_idempotent(
    incoming: EconomicObligationRecord,
    prior: EconomicObligationRecord | None,   # M7 계약: incoming의 primary obligation id 공유 레코드,
                                              #   없으면 idempotency key 공유 레코드, 둘 다 없으면 None
    original_retained: bool | None,   # 양극성 (안전값=True) — append-only 보존
) -> ObligationCommitOutcome
```

- **M7 prior 선정 계약(§4.6 각주 verbatim)**: `prior` = incoming의 **primary obligation identity를 공유하는 레코드,
  없으면 idempotency key를 공유하는 레코드, 둘 다 없으면 None**. nontrade `predicates.py:526`("sharing incoming's
  idempotency key")를 fill-commit **2-축**으로 확장한 것으로, key-only/primary-only 단일 축 선정이 각각 `CRITICAL_
  CONFLICT` 우회·`DIVERGENT_EMISSION` 누락을 낳는 두 오독을 차단한다. classify는 두 축을 모두 비교하므로 선정된 prior
  하나로 두 위조가 정확한 kind로 접힌다.
- **선행 게이트(순서)**: (i) correction이면 `incoming.supersedes_ref is None` ⇒ `REJECTED_NO_LINEAGE`(§20 line 460);
  (ii) `original_retained is not True` ⇒ `REJECTED_OVERWRITE`(§11 line 330 — **양극성 `is True`만 통과**); (iii)
  `prior is None` ⇒ `COMMITTED_ONCE`(첫 commit — classify 선행 분리, NOT_COMPARABLE 영구거부 방지).
- **classify 매핑(5-member 전수)**: `classify_record_pair(incoming.obligation_id, incoming.digest, prior.obligation_id,
  prior.digest, a_idempotency_id=incoming.idempotency_key, b_idempotency_id=prior.idempotency_key)` →
  `IDEMPOTENT_DUP`⇒`IDEMPOTENT_REPLAY`·`CRITICAL_CONFLICT`⇒`REJECTED_CONFLICT`·`DIVERGENT_EMISSION`⇒`REJECTED_
  CONFLICT`·`DISTINCT`/`NOT_COMPARABLE`⇒`REJECTED_UNKNOWN`(§4.6 진리표).
- **truthy-sentinel**: `ObligationCommitOutcome`는 `_NonTruthyStrEnum`(`__bool__`⇒TypeError); consume 게이트는 `outcome
  is COMMITTED_ONCE`/`is IDEMPOTENT_REPLAY`만.

**canary**: (a) no-lineage/overwrite/2-forgery-axis ⇒ REJECTED_*(가드 발화); (b) prior None ⇒ `COMMITTED_ONCE`·late-fill
same-bytes ⇒ `IDEMPOTENT_REPLAY`·effect count==1(양성 side). **PTF-EV-001 좌표·`/2`·`/3`·`+Broker` 잔여.**

### 5.3 no-favorable-default — monetary·netting·counterleg (§13/§9 line 279; PTF-EV-002 substrate, core L1 슬라이스)

```text
monetary_leg_conservative(leg: MonetaryLeg | None) -> bool
netting_requires_positive_proof(
    receivable: ObligationLeg | None, payable: ObligationLeg | None,
    same_scope: bool | None, enforceable_netting_proof: bool | None,  # 양극성 (안전값=True)
) -> bool
missing_counterleg_is_adverse(
    declared_leg: ObligationLeg, counterleg: ObligationLeg | None,
    counterleg_positively_established: bool | None,  # 양극성
) -> bool
```

- **`monetary_leg_conservative`**: `leg`의 amount가 present(not None)·finite ∧ (estimated/booked/final status가 explicit)
  일 때만 conservative; **amount None/absent ⇒ False**(missing line item은 zero 아님 — §13 line 355). proven-zero는
  `leg.booked_zero is True` ∧ source CORROBORATED(주입)일 때만.
- **`netting_requires_positive_proof`(구조적, §0.4d)**: receivable·payable **둘 다 present·비음수로 gross 병존** ∧
  `same_scope is True` ∧ `enforceable_netting_proof is True`일 때만 True(netting valid); 하나라도 부재/None ⇒ False
  (둘 다 gross). **양극성 `is True`만**·flag 위조 불가(구조적 magnitude 병존 요구).
- **`missing_counterleg_is_adverse`**: `counterleg is None` 또는 `counterleg_positively_established is not True` ⇒ True
  (missing counterleg는 greatest-credible-adverse — §9 line 279); consumer local favorable balancing 필드·술어 부재.

**canary**: (a) missing-amount-as-zero·unproven-netting·favorable-local-counterleg ⇒ 보수(가드 발화); (b) booked-zero·
proven-netting·established-counterleg ⇒ 통과(양성 side). **PTF-EV-002 좌표·`/2`·`/3`·`+Broker` 잔여.**

### 5.4 collateral no-double-use + margin-state distinct + cash-kind non-substitution (§15/§14; PTF-EV-004 substrate, core L1 슬라이스)

```text
collateral_no_double_use(allocations: Sequence[CollateralAllocation]) -> bool
margin_collateral_states_distinct(
    observed_state: MarginCollateralState,
    claimed_state: MarginCollateralState,
) -> bool
cash_kind_matches_requirement(          # M3 — rename + 단일 명제
    requested: CashKind, available: CashKind,
) -> bool                               # = (requested is available); identity 외 전 쌍 False
```

- **`collateral_no_double_use`(보존)**: 각 collateral unit에 대해 allocation state 상호배타(free XOR encumbered) ∧
  pledge 합 ≤ available(magnitude 보존 검사)일 때만 True; same unit이 free+encumbered·two-obligation pledge·confirmed-
  release 전 reuse ⇒ False(§15 line 386). **∅ allocations ⇒ True 아님**(빈 입력 ⇒ 판정 불가 ⇒ 보수적 — §4.8 행 1 동형).
- **`margin_collateral_states_distinct`**: 8상태 non-implication — `observed_state`가 `claimed_state`를 함의하지 않음
  (§15 line 385 "No one state implies another"); broker favorable figure(주입)는 ceiling이지 proof 아님.
- **`cash_kind_matches_requirement`(M3 — 단일 명제·substrate)**: `return requested is available` — 요구한 cash kind와
  가용한 cash kind가 **동일**할 때만 True(사용 가능). buying-power로 withdrawable을 충족하려는 시도 =
  `requested(WITHDRAWABLE_CASH) is available(BUYING_POWER)` ⇒ False(치환 차단). **v1.0 자기모순 정정(M3)**: v1.0의
  `cash_kinds_not_substitutable`은 "`requested != available`이면 True(구분 유지)"와 "buying-power-as-withdrawable ⇒
  False"가 **같은 입력에 반대 진리값**을 주는 극성 모순이었다 — disposition conjunct는 "가용 cash가 요구를 충족해야
  통과"가 옳으므로 **identity 명제로 단일화**. identity 외 전 쌍 False 회귀(§7). **availability PROOF(buying-power→
  withdrawable 전환)은 PTF-EV-003 `EV-L2/3` 잔여**.

**canary**: (a) double-use·state-implication·**cash-kind mismatch(requested≠available)** ⇒ False(가드 발화); (b)
상호배타·**cash-kind identity(requested is available)** ⇒ True(양성 side). **PTF-EV-004 좌표·`/2`·`/3`·`+Broker` 잔여.**

### 5.5 exercise/assignment/CA obligation-leg completeness + event-state ≠ obligation-finality (§17; PTF-EV-006 substrate, core L1 슬라이스 · nontrade 경계)

```text
obligation_legs_from_event_complete(
    event_leg_kinds_required: frozenset[EventObligationLegKind],  # m6: enum 화(9축, §2.2-5b)
    present_obligation_legs: frozenset[EventObligationLegKind],
) -> bool
event_state_not_obligation_finality(
    nontrade_event_state: str | None,           # 주입 토큰 — nontrade APPLIED_LOCAL/RECONCILED
    finality_proof_present: Mapping[FinalityDimensionKind, bool | None],
) -> bool
```

- **`obligation_legs_from_event_complete`**: exercise·assignment·expiry·delivery·cash-settlement·conversion·redemption·
  distribution·tender·rights·corporate-action event의 **9 credible leg 축**(`EventObligationLegKind`, m6 enum 화 — asset/
  cash/fee/tax/financing/margin/borrow/custody/delivery, §2.2-5b) required subset이 전부 present일 때만 True(§17 line
  416). **∅ 구조 가드**(빈 required ⇒ False, §5.1 동형).
- **`event_state_not_obligation_finality`(핵심 seam — nontrade 경계)**: `nontrade_event_state` 토큰이 `APPLIED_LOCAL`·
  `RECONCILED`(주입 — nontrade `NonTradeEventWorkflowState`)여도 **어떤 finality dimension도 PROVEN으로 만들지 않는다**
  (§17 line 418 verbatim). obligation finality는 오직 `finality_proof_present[dim] is True`(dimension-specific proof)로만.
  local deadline의 exercise/assignment/delivery/CA report 부재도 obligation 부재의 proof 아님(PTF-INV-004). **PTF은
  event-state를 re-classify하지 않고 주입 토큰으로만 소비**(nontrade 소유 — §3.5).

**canary**: (a) event-state로 obligation-finality 주장·leg 누락 ⇒ False(가드 발화); (b) 9-leg 완비·dimension-proof present
⇒ True(양성 side). **PTF-EV-006 좌표·`/2`·`/3`·`+Broker` 잔여.**

### 5.6 statement coverage completeness + source common-mode independence + absence-negative-only (§19; PTF-EV-008 substrate, core L1 슬라이스 · +Security 잔여)

```text
statement_coverage_complete(manifest: StatementCoverageManifest | None) -> bool
statement_sources_independent(
    source_a_shared_deps: frozenset[str],   # book/parser/administrator/transport
    source_b_shared_deps: frozenset[str],
) -> bool
absence_is_negative_evidence_only(
    line_item_absent: bool | None,       # Gap: unknown 표현 허용 (None ⇒ not-absent-proven ⇒ UNKNOWN)
    coverage_complete: bool | None,      # 양극성 (안전값=True)
    correction_semantics_support: bool | None,   # M6: 시간경과(horizon)가 아니라 correction SEMANTICS 지지
    source_capability_supports: bool | None,
) -> bool
```

- **`statement_coverage_complete`**: `manifest`의 expected pages/files/sections/cursors/checksums/record-counts가 전부
  received ∧ missing interval ∅ ∧ period-boundary·cutoff·revision present일 때만 True(§19 line 443, set-completeness).
  `manifest is None` 또는 preliminary/truncated/stale/conflicting ⇒ False(§19 line 450·`StatementClass`).
- **`statement_sources_independent`(명제 상이 — statement-source grain)**: 두 source의 shared-dependency set(book/parser/
  administrator/transport)이 **disjoint**일 때만 corroborate(§19 line 445·PTF-INV-014). broker API + broker statement,
  또는 broker + custodian이 one book 공유 ⇒ not-independent(intersection 비어있지 않음 ⇒ False). **recon `classify_field`
  의 per-field independence_class와 grain 상이**(recon = field 값 / PTF = statement source — §3.5).
- **`absence_is_negative_evidence_only`(M6 정정)**: `line_item_absent is True` ∧ `coverage_complete is True` ∧
  **`correction_semantics_support is True`** ∧ `source_capability_supports is True`일 때만 absence가 negative evidence
  (§19 line 448 verbatim "exact coverage, **correction semantics**, and source capability positively support"); 하나라도
  아니면 absence ⇒ UNKNOWN. **M6 핵심**: v1.0의 `correction_horizon_passed`(시간 경과)는 **PTF-INV-004가 명시 금지한
  신호**다("cutoff passage ... never proves that an obligation does not exist" — ADR line 164) — cutoff/시간 경과를
  absence-as-negative의 게이트로 쓰면 정확히 그 fail-open이다. ADR line 448이 요구하는 것은 **correction SEMANTICS의
  positive 지지**(정정 규칙이 "이 라인 부재는 곧 무의무"를 능동 지지)이지 시간이 아니므로 `correction_semantics_support`
  로 교체·`is True` 게이트. **양극성 `is True`만**; `line_item_absent is None`(미지)이면 absent 증명 없음 ⇒ 전건 불성립
  ⇒ UNKNOWN.

**canary**: (a) 미완 coverage·common-mode source·미증명 coverage에서 absence-as-negative ⇒ False(가드 발화); (b) complete
coverage·disjoint source·all-conjunct absence ⇒ True(양성 side). **PTF-EV-008 좌표·`/2`·`/3`·`+Broker`·`+Security`
잔여.**

### 5.7 finality-proof class-specificity + non-transferability + finality-grants-nothing (§11/§10 line 312; core substrate)

```text
finality_proof_class_specific(proof: PostTradeFinalityProof | None) -> bool
finality_proof_non_transferable(
    proof: PostTradeFinalityProof,
    target_leg_scope: ObligationLegScope,   # M8: §2.1 정식 등재 value 모델 (leg·account·currency·
                                            #     value-date·source-revision·finality-class — ADR §11 line 328)
    *,                                      # v1.2 에라타 — cross-obligation 봉인 (ADR §11 line 320)
    target_obligation_ref: str | None = None,      # 제공 시 proof.obligation_ref 일치 요구
    target_obligation_version: str | None = None,  # 제공 시 proof.obligation_version 일치 요구
) -> bool
finality_proof_current(                     # M2: 순수 generation 비교 — L1-decidable
    proof: PostTradeFinalityProof, active_generation: int,
) -> bool                                   # = (proof.bound_generation == active_generation)
post_trade_consequence_all_false(consequence: AllFalsePostTradeConsequence) -> bool
```

- **`finality_proof_class_specific`**: `proof`가 exact obligation identity·version·leg·scope·amount·account·currency·
  value-date·generation·finality-class ∧ **`does_not_prove` 필드(what it does not prove)** present일 때만 True(§11
  line 320–326). global `SETTLED`/`CLOSED`/confidence-score/statement-flag/operator-decision로 per-field proof 대체
  시도 ⇒ False(PTF-INV-005). **실패 시 disposition `POST_TRADE_CONFLICTED`**(global-flag 치환 = 위반, §4.8 행).
- **`finality_proof_non_transferable`(M8; v1.2 에라타로 확장)**: `proof`의 leg/account/currency/value-date/
  source-revision/finality-class가 `target_leg_scope`(`ObligationLegScope` value 모델, §2.1)와 **정확히 일치**할
  때만 True; 다른 leg/class로 patch·reuse ⇒ False(§11 line 328 verbatim "non-transferable and non-unionable").
  **cross-obligation 봉인(v1.2 에라타 — 적대적 코드 리뷰 MAJOR)**: 위 6성분에는 **obligation 식별자가 없어**
  서로 다른 두 obligation이 동일 scope를 정당하게 공유할 수 있다(같은 account·통화·value-date). scope-only 대조는
  그 경우 **다른 obligation의 proof를 유효로 판정**해 §4.8 행 10 rank 1이 미발화한다. 따라서 ADR §11 line 320
  "exact obligation identity" 근거로 **keyword-only `target_obligation_ref`/`target_obligation_version`**을 받아
  **제공 시** `proof.obligation_ref`·`proof.obligation_version`과의 일치를 추가 요구한다. **미제공 시 기존
  scope-only 거동**(하위호환); 제공은 판정을 **좁히기만** 하므로 보수 방향이다. proof가 식별자를 갖지 않는데
  (`obligation_ref is None`) 대상 식별자가 제공되면 **불일치 ⇒ False**(미비교로 흘려보내지 않는다).
  §7 canary: §4.8 행 10에 **cross-obligation 변종**(동일 6성분 scope·다른 `obligation_ref` ⇒ False) 필수.
- **`finality_proof_current`(M2 신설 — finality reopen 봉인)**: `return proof.bound_generation == active_generation` —
  proof가 bind한 Post-Trade Obligation Generation이 **현재 active generation과 같을 때만** current. correction이
  generation을 advance하면(§11 line 330 "supersedes the proof, advances generation") prior proof는 `bound_generation
  < active_generation` ⇒ **stale ⇒ not-current ⇒ reopen**(PTF-INV-013). **순수 정수 비교로 L1-decidable**(generation은
  ordering 좌표 주입, §3.2 — bound 필드는 §11 line 320이 이미 요구). §4.5-B 9번째 행이 이 술어의 진리표 cell이다.
- **`post_trade_consequence_all_false`**: `AllFalsePostTradeConsequence`의 `releases_capacity`·`makes_cash_available`·
  `proves_legal_title`·`grants_permission`·`authorizes_transmission`가 **전부 False**일 때만 True(어떤 True도
  unconstructable — §10 line 312·PTF-INV-009; rcl `AllFalseAuthority` 동형). FINALITY_PROVEN도 all-false.

**canary**: (a) global-flag로 per-field proof 대체·cross-leg proof reuse·**stale-generation proof(bound<active)**·
consequence True 시도 ⇒ False/구성 불가(가드 발화); (b) exact class-specific proof·exact-scope match·**current
generation proof**·all-false consequence ⇒ True(양성 side, consequence는 부여 안 함). [SAFE-005 class-specific·SAFE-010/
011 non-substitution·SAFE-020 lineage]

### 5.8 `post_trade_disposition` — 단일 disposition 생산 술어 (C1-style, #21 §5.5 상속)

```text
post_trade_disposition(
    # ── §5 전 L1 verdict를 conjunct로 수용 (C1 정정 — 16 양극성 bool, 안전값=True) ──
    leg_set_complete: bool,          finality_orthogonal: bool,       # §5.1
    monetary_conservative: bool,     netting_proof_ok: bool,          # §5.3
    counterleg_established: bool,    # §5.3  = not missing_counterleg_is_adverse
    collateral_conserved: bool,      margin_states_distinct: bool,    # §5.4
    cash_kind_ok: bool,              # §5.4  = cash_kind_matches_requirement
    event_legs_complete: bool,       event_state_not_final_ok: bool,  # §5.5
    statement_coverage_ok: bool,     sources_independent: bool,       # §5.6
    absence_gate_ok: bool,           # §5.6  (absence를 무증명 negative로 읽지 않음)
    proof_class_specific: bool,      proof_non_transferable: bool,    # §5.7
    proof_current: bool,             # §5.7  finality_proof_current (M2)
    # ── 비-bool 주입 ──
    commit_outcome: ObligationCommitOutcome,   # §5.2
    field_confidence: str | None,              # recon 주입 토큰 (CORROBORATED/UNKNOWN/CONFLICTED/…)
    availability_proven: bool | None,          # not-Phase-1 주입 (None ⇒ TRAPPED; L1-alone은 항상 None)
) -> PostTradeDisposition
```

- **C1 정정(v1.0 fail-open 봉인)**: v1.0 시그니처는 **8 입력**만 받아 `sources_independent`·`proof_class_specific`·
  `proof_non_transferable`·`cash_kind_ok`·`margin_states_distinct`·`absence_gate_ok`·`event_legs_complete`·`event_state_
  not_final_ok`·`proof_current`를 **conjunction에서 누락**했다 — 그 결과 statement common-mode(§4.8 행 9, PTF-INV-014)·
  cross-leg proof reuse(§11 line 328)·global-flag 치환(PTF-INV-005) 위반 상태로 `POST_TRADE_ADMISSIBLE` 도달이 가능
  했고 §4.8 "모든 행 재매핑" 주장이 거짓이었다(#21 C1의 동형 재발). **처방: 16 bool 전 conjunct + commit_outcome +
  confidence + availability를 시그니처에 편입**하고 §4.8 표를 conjunct와 **문자 그대로 1:1**로 확장(§4.8 신규 행).
- **§4.8 ∅-공허 표의 모든 행이 이 술어의 반환값으로 재매핑**된다 — "빈 입력 별도 처리" 무주 위임 없음(#21 C1). 각
  conjunct ↔ §4.8 행 대응은 §7 1:1 property로 강제(구현 차단 방지).
- **5-member 전순서 우선순위(결정적·평가 순서)**: (1) `POST_TRADE_CONFLICTED` ⇐ `not collateral_conserved` ∨ `not
  sources_independent` ∨ `not proof_class_specific` ∨ `not proof_non_transferable` ∨ `commit_outcome is REJECTED_CONFLICT`
  ∨ `field_confidence == "CONFLICTED"`; else (2) `POST_TRADE_QUARANTINED_UNKNOWN` ⇐ `commit_outcome is REJECTED_UNKNOWN`
  ∨ `field_confidence == "UNKNOWN"`; else (3) `POST_TRADE_TRAPPED` ⇐ `availability_proven is not True`(None/False —
  미증명 settlement/discharge/title); else (4) `POST_TRADE_BLOCK_NEW_RISK` ⇐ 나머지 12 bool 중 하나라도 False ∨
  `commit_outcome in {REJECTED_NO_LINEAGE, REJECTED_OVERWRITE}`; else (5) `POST_TRADE_ADMISSIBLE`.
- **Q2 순위 근거(1문장 — #18 순서-미검토 교훈)**: `CONFLICTED > QUARANTINED_UNKNOWN > TRAPPED`인 이유 — **CONFLICTED**는
  능동적 모순(contain-both, 위조·common-mode)으로 최심각, **QUARANTINED_UNKNOWN**은 unattributable·undecidable이라
  **greatest-credible dependency closure 전역으로 무한정 보수 확대**(unbounded scope), **TRAPPED**는 식별된·경계 지어진
  exposure(bounded)이므로 — **더 넓은 scope의 제약이 더 좁은 것을 지배**한다.
- **`POST_TRADE_ADMISSIBLE`은 잔여 fall-through가 아니라 양성 conjunction identity 증명으로만 도달**: **16 bool 전부
  True** ∧ `commit_outcome in {COMMITTED_ONCE, IDEMPOTENT_REPLAY}` ∧ `field_confidence == "CORROBORATED"` ∧
  `availability_proven is True`(#16 CRITICAL "GRANT는 fall-through residue가 아니다"). **정직 공개(staged)**: L1-alone은
  `availability_proven`이 None(PTF-EV-003/007 L2/3 미증명)이라 **항상 TRAPPED at best** — `POST_TRADE_ADMISSIBLE`의
  양성 side canary(§7)는 `availability_proven=True`(L2/3-simulated proof 주입)로만 도달하며, 이는 "L1 구조 성질이 전부
  성립해도 settlement availability 없이는 admissible 아님"을 정직하게 반영한다. **disposition은 grants nothing**(§4.7)
  — `POST_TRADE_ADMISSIBLE`도 capacity release·transmit·admissibility 발급 안 함. truthy-untestable(identity 게이트만).

---

## 6. predicate-only substrate + not-Phase-1 경계 (PTF-EV-003/005/007/009/010/011/012 — 형제 소유·런타임 이연, 닫지 않음)

**핵심 규율(staged EV 정직 분리·defect-class #9)**: 아래는 **L1 슬라이스가 아니며** Phase-1이 **어휘 substrate만** 두거나
**전부 형제/런타임(EV-L2/3+Broker[+Security])에 이연**한다. **어떤 PTF-EV도 닫지 않는다.**

### 6.1 settlement/cash availability (PTF-EV-003 `EV-L2/3+Broker`) — substrate만

`CashKind`(6)·settlement-instruction state 어휘는 substrate(§5.4)이나, **instruction-acceptance·partial-settlement·
booking·settled-ledger-cash·withdrawable-cash·buying-power·collateral-eligible 전환의 PROOF**은 broker/integrated 단계다
(§14 line 365–373 9 distinction). `SETTLEMENT`/`CASH_AVAILABILITY`/`INSTRUCTION_ACCEPTANCE` dimension proof은 EV-L2/3.
NT은 cash-kind 구분·non-substitution만 판정하고 availability는 UNKNOWN 유지(§5.4·§4.8 행 16). are `SETTLEMENT_CASH_
CURRENCY`·recon `SETTLEMENT_CASH_AVAILABILITY_COLLATERAL_ELIGIBILITY` 주입 소비.

### 6.2 borrow/recall/return/buy-in (PTF-EV-005 `EV-L2/3+Broker`) — 어휘 substrate만

locate/indicative·approved-allocation·executed-loan·recall+deadline·return-instruction+ack·confirmed-return·forced-
buy-in·replacement·residual 8 distinction(§16 line 396–404) 어휘만 substrate. **locate ≠ executed loan·recall silence ≠
no-recall·return-ack ≠ discharge**(§16 line 406)의 실제 discharge PROOF은 EV-L2/3(`BORROW_DISCHARGE` dimension). are
`MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN` 주입 소비.

### 6.3 custody/transfer/legal-title (PTF-EV-007 `EV-L2/3+Broker+Security`) — 어휘 substrate·+Security 잔여

instruction-acceptance·source-debit·in-flight·destination-credit·custody-booking·availability·legal-title 7 state
(§18 line 428) 어휘만. **transfer ack·source-disappearance·destination-display·matching-quantity ≠ complete chain**(§18
line 428)의 chain/title PROOF은 EV-L2/3, **credential/route/bypass는 +Security**(egress `credential_route_authority_
disjoint` 소유). `CUSTODY_TITLE` dimension non-implication은 L1 substrate(§5.1).

### 6.4 breaks/corrections/reversals (PTF-EV-009 `EV-L2/3+Broker+Security`) — append-only substrate·break-to-restrict 잔여

`REJECTED_OVERWRITE`·append-only-no-destructive-overwrite(§5.2·PTF-INV-013 "append new versions, preserve old and new")
는 L1 substrate. **break-to-RCL-restrict propagation·correction recompute·finality reopen runtime**은 EV-L2/3(§20 line
462 "Closure requires field-specific evidence ... conservative RCL treatment"), **credential/compromise는 +Security**.
`PostTradeBreakRecord` 모델은 substrate이나 break 판정·closure runtime 미저작.

### 6.5 RCL capacity coupling + generation fencing + currentness (PTF-EV-010 `EV-L2/3+Broker+Security`) — 형제 소유·런타임

§21 safe transition order 7 step(source→candidate-set→PTOL-append→aggregate-risk→RCL-commit→finality-proof→RCL-verify)에서
PTF는 **candidate obligation-set 열거 완전성·no-favorable-default**(§5.1/§5.3)만 소유하고 **RCL ordered-transfer/quarantine/
release·are risk 투영·§22 currentness vector·generation fence**은 rcl/are/cur/egress 런타임 소유(§3.5). currentness
identity 좌표(policy/generation/digest — VP 주입, §8.1)만 substrate. **cur(committed `1390ef9d`)이 `DimensionKey.
POST_TRADE`(`cur/vocabulary.py:146`)로 post-trade currentness 차원을 소유**하며 PTF는 identity 좌표를 주입하고 fencing
runtime(§22)은 cur/egress 소유다(§3.5 §22·§7 `test_seam_cur`).

### 6.6 partition/compromise/route-bypass (PTF-EV-011 `EV-L3+Broker+Security`) + evidence/recovery/non-revival (PTF-EV-012 `EV-L2/3+Broker+Security`) — 전부 런타임

§23 10-row failure table·§24 evidence/recovery는 egress(credential/route)·rcl(containment)·evidence(replay ENGINE)·sbr
(recovery inventory)·liveauth(no-revival) 소유. PTF는 frozen digest-bound record 재구성만 substrate. **replay match·
recovery readiness·no-automatic-re-arm**은 EV-L2/3+Security(§24 line 552 "cannot reuse a prior proof, authority ...").

---

## 7. property-test 하네스 타깃

§1 분류에 정렬한다. **닫는 PTF-EV = 0건** — 어떤 test-target도 PTF-EV closure·acceptance를 주장하지 않는다(규율 태그
부착). 각 술어에 **both-ways canary**(§4·§5)와 **fixture clean-vs-illegal 정합**(#8 교훈)을 건다. **hypothesis 전략은
forgery/∅/finality-implication/double-use/common-mode 케이스를 명시 포함**한다.

- **core(L1 슬라이스, PTF-EV-001/002/004/006/008 substrate)**: `finality_dimensions_orthogonal`+`obligation_leg_set_
  complete`(§5.1); `obligation_commit_idempotent`(§5.2); `monetary_leg_conservative`+`netting_requires_positive_proof`+
  `missing_counterleg_is_adverse`(§5.3); `collateral_no_double_use`+`margin_collateral_states_distinct`+`cash_kinds_not_
  substitutable`(§5.4); `obligation_legs_from_event_complete`+`event_state_not_obligation_finality`(§5.5); `statement_
  coverage_complete`+`statement_sources_independent`+`absence_is_negative_evidence_only`(§5.6); `finality_proof_class_
  specific`+`finality_proof_non_transferable`+`post_trade_consequence_all_false`(§5.7); **`post_trade_disposition`(§5.8·
  §4.8 22행 1:1 회귀)**.
  **hypothesis property**: `EconomicObligationRecord`/`PostTradeFinalityProof`/`StatementCoverageManifest`/`Collateral
  Allocation`/`MonetaryLeg`/`ObligationLeg`/finality-dimension-proof-map를 무작위 생성해 (i) **finality orthogonality**
  (proven dimension 부분집합에서 non-implication — `ORDER_FQP` PROVEN이 다른 9 dimension을 PROVEN 안 만듦; global-flag
  대체 시도⇒False), (ii) **commit idempotency**(§4.6 진리표 전 cell — prior None/same-bytes/diff-bytes·supersedes
  present/absent·retained True/False; **late-fill same-bytes N≥2회 ⇒ effect count==1**), (iii) **no-favorable-default**
  (amount None⇒UNKNOWN·netting proof None⇒gross·counterleg None⇒adverse), (iv) **collateral 보존**(free∧encumbered·
  pledge-twice·reuse-before-release⇒False; magnitude 합 ≤ available), (v) **event-state ≠ finality**(APPLIED_LOCAL/
  RECONCILED 주입 토큰이 어떤 dimension도 PROVEN 안 만듦), (vi) **statement coverage**(expected⊄received⇒False; missing
  interval⇒False; common-mode shared-dep⇒not-independent; absence-without-coverage⇒UNKNOWN), (vii) **finality-proof**
  (cross-leg reuse⇒False; global-flag 대체⇒False), (viii) **consequence all-false**(FINALITY_PROVEN 포함 어떤 state로도
  consequence True 불가), (ix) **disposition 접기**(`post_trade_disposition` 5-member 우선순위 전순서·identity 게이트·
  ADMISSIBLE 양성 conjunction으로만)를 검사.
  - **forgery 케이스(명시, 2종 분리)**: (a) **same primary id·diff canonical digest** `EconomicObligationRecord`/
    `PostTradeFinalityProof` 쌍 ⇒ `classify_record_pair` **`CRITICAL_CONFLICT`**(`record_pair.py:96`) 회귀; (b) **same
    idempotency key·diff canonical digest**(primary id 상이) 쌍 ⇒ **`DIVERGENT_EMISSION`**(:103) 회귀. **둘 다
    `REJECTED_CONFLICT`로 접히고**(§4.6) `post_trade_disposition`은 `POST_TRADE_CONFLICTED`, 양쪽 레코드 보존·no LWW
    assert.
  - **late-fill/double-commit 케이스(명시)**: claimed terminal 이후 동일 fill(same key·same bytes) N≥2회 ⇒ 첫 회
    `COMMITTED_ONCE`·2회+ `IDEMPOTENT_REPLAY` ⇒ 누적 obligation effect count == 1(§12 line 347 무해성 회귀). same-key
    diff-digest ⇒ `REJECTED_CONFLICT`(effect+0).
  - **∅ 케이스(명시, §4.8 표 22행과 1:1 — 번호 대응)**: (1)–(22) 각 빈-입력의 **금지 방향 + 허용 방향 둘 다**(§4.8
    양방향 규율). 특히 (1) 빈 `required_legs`⇒`obligation_leg_set_complete` False(vacuous-True 봉인); (7) event-state로
    finality 주장⇒non-implication False; (10) cross-leg proof reuse⇒False; (15) capacity-release/transmit⇒구조적 부재
    (필드·술어 0 assert).
  - **truthy-sentinel property(양축·극성 분기)**: `PostTradeDisposition` 게이트 `is POST_TRADE_ADMISSIBLE`만·
    `ObligationCommitOutcome` 게이트 `is COMMITTED_ONCE`/`is IDEMPOTENT_REPLAY`만 통과(나머지 토큰·None 관통 시 실패;
    `bool(token)`⇒`TypeError` 확인). **양극성 필드(`original_retained`·`enforceable_netting_proof`·`counterleg_
    positively_established`·`dimension_proof_present[*]`·`coverage_complete`·`correction_semantics_support`·`source_
    capability_supports`·`proof_current`·disposition 16 conjunct)는 `is True`만·None 관통 시 실패**. **음극성 필드는 Phase-1 PTF 모델에 0건이며(정직 공개), 그
    사실 자체를 회귀로 고정**한다 — no-favorable-default는 구조적 magnitude 병존·proof-token 부재로, capacity-release·
    transmit·favorable-local-counterleg는 **필드·술어 부재**(unconstructable)로 실현되므로 음극성 flag 불요. **phantom
    필드(`releases_capacity_flag`·`favorable_netted`·`can_transmit`·`title_proven_by_ack`) 부재 assert**(재유입 방지).
    향후 음극성 필드 도입 시 `is False`만·`is not True` 금지(시리즈 규율 1).
  - **좌표 비붕괴 property(§2.2-6)**: `PostTradeObligationLifecycleState.CLOSED` ∩ orthostate `IntentState.CLOSED`·
    `FINALITY_PROVEN` ∩ orthostate `KnowledgeState.RECONCILED` ∩ nontrade `NonTradeEventWorkflowState.RECONCILED`·
    `ObligationCommitOutcome.IDEMPOTENT_REPLAY` ∩ iap/rcl/nontrade `IDEMPOTENT_REPLAY`가 별개 타입임(토큰 겹침 무관)
    회귀.
- **substrate/not-Phase-1(PTF-EV-003/005/007/009/010/011/012, EV 미주장·seam test로만)**: 형제 술어 주입 소비 polarity만
  검증(§6) — 형제 L1을 재검증하지 않는다(권위 중복 배제). settlement/borrow/custody availability는 UNKNOWN 유지 회귀.
- **seam cross-check(test-only, MANDATED §3.4)**: `test_seam_rcl`(PTF obligation-set ↔ `credible_union_capacity`
  empty⇒`ValueError`·`FINAL_QUANTITY_PROOF`≠post-trade-finality; **PTF `finality_dimensions_orthogonal`의 FQP-non-
  implication이 rcl `FINAL_QUANTITY_PROOF`[order capacity release]와 별개 명제임을 주석 고정** — §3.5)·`test_seam_are`
  (PTF gross-leg ↔ `SETTLEMENT_CASH_CURRENCY`·`MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN`·`BenefitKind.NETTING`
  주입 — **PTF obligation-leg no-netting ≠ are aggregate-risk netting-benefit 명제-동일성 주석**)·`test_seam_recon`
  (PTF finality-proof ↔ `classify_field`·`FieldConfidenceClass`·common-mode RECON-EV-001; **confidence≠finality·
  per-field-grain≠statement-source-grain 주석**)·`test_seam_nontrade`(PTF `event_state_not_obligation_finality` ↔
  nontrade `NonTradeEventWorkflowState.{APPLIED_LOCAL,RECONCILED}` 주입 토큰; **event-lifecycle≠obligation-lifecycle·
  transition-leg≠obligation-leg 명제-동일성 주석 — ADR-002-010 §16 line 309↔ADR-002-030 §17 line 414**)·`test_seam_
  brokercap`(PTF ↔ `fqp_adequate`·`POSITIONS_BALANCES_MARGIN`·`CapabilityStatus.VERIFIED`; +Broker discharge)·`test_
  seam_egress`(PTF 구조적 non-transmission ↔ `credential_route_authority_disjoint`(`egress/predicates.py:405`)·`Egress
  Admission`; egress-non-bypassable)·**`test_seam_cur`(M5 신설 — PTF §22 currentness identity 좌표 ↔ cur `DimensionKey.
  POST_TRADE`(`cur/vocabulary.py:146`)·`ProofResult`(CURRENT/RESTRICTED/UNKNOWN)·`CurrentnessAdmission`(ADMIT/DENY);
  cur이 post-trade currentness 차원·fence·admit 판정을 소유하고 PTF는 policy/generation/digest identity 좌표만 주입함을
  대조)**·`test_seam_orthostate`(PTF obligation-lifecycle 축 ↔ orthostate `KnowledgeState`/`IntentState` 좌표 비붕괴)·
  **`test_seam_vocab`(m6 — `EventObligationLegKind` 9-member value 바인딩 drift-lock)**·`test_seam_canonical`(fill-commit
  ↔ `classify_record_pair` **5-member 전수**: same-bytes⇒`IDEMPOTENT_DUP`·same-primary-id·diff-bytes⇒`CRITICAL_
  CONFLICT`·same-idempotency-key·diff-bytes⇒`DIVERGENT_EMISSION`·id/key 미공유⇒`DISTINCT`·digest None⇒`NOT_COMPARABLE`).
  **19 주입 토큰 전수 drift-lock**(§3.4 목록 1–19 개별 assert, cur 2 포함). 테스트 import는 package closure 불계상
  (§7.1).
- **∅-공허 회귀(양방향, §4.8 표 22행 ↔ 본 §7 "∅ 케이스" 22항목 1:1)**: 각 빈-입력의 금지 방향 + 완비 입력의 정당 통과
  canary **둘 다**.

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#5..#21 §7.1 상속)

**allowlist 형식(denylist 열거 금지 — #16 M9 교훈)**: `import` 후 `{m for m in sys.modules if m.startswith("tos.")}`의
top-level 패키지 ⊆ **{`tos.canonical`, `tos.ordering`, 자기 자신(`tos.posttrade`)}** assert(그 외 모든 tos 형제 — 현재
committed 25개[cur 포함] + 미래 형제 — 등장 시 실패) + `shared.config`·`os.environ` 흔적·`numpy`/`pandas`/`yaml` 부재
assert. **allowlist가 미래-견고**(신규 형제 추가에 자동 방어). required check(`tos-firewall`, `tools/tos_firewall_
check.py` layer-① AST + `.importlinter` layer-② 전이)와 함께 green이어야 §0.3 선언이 능동 성립.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: posttrade Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `PYTHONPATH=tos/src .venv/bin/python -m pytest
tos/tests/posttrade/ -v`(pyenv=mypy 전용 — project memory). (3) 격리: hermetic(`.env` 비주입·clock 미접근·네트워크 없음).
(4) 결정론: hypothesis 시드 고정·`CanonicalDecimal` scale-normalize·NaN/infinity 구성-거부·magnitude 병존 비교. (5)
산출물: property test 결과(EV closure 아님 — 규율 태그). (6) 게이트: `tos-firewall` required green. (7) 비-acceptance:
어떤 PTF-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 posttrade decision 구조에 numeric bound 부재**: 전부 enum(`PostTradeObligationLifecycleState`/`FinalityDimension
Kind`/`ObligationLegDirection`/`CashKind`/`MarginCollateralState`/`StatementClass`/`EventObligationLegKind`/`Obligation
CommitOutcome`/`PostTradeDisposition` — 9종)·boolean·집합 논리·주입 `CanonicalDecimal`(leg magnitude·collateral
allocation·monetary amount·**generation 정수**(§5.7 `finality_proof_current`) — 비교·
`is_finite`·scale-normalize·비음수·보존 합 검사뿐, 어떤 ratio·threshold·age도 하드코딩 없음). **어떤 숫자도 하드코딩하지
않는다**(CLAUDE.md·§0.2).

**§8.1 VP-002 실측 — 19 PTF-전용 키 실재·null/TBD(신규 키 0건)**: ADR §29 Q9/Q10·§22가 요하는 bound/currentness는
`VERIFICATION-PROFILE-002.yaml`에 **이미 19키 실재**(confirmed candidate 신규 키 0건 — #10/#13/#16/#18/#21형):

**(a) 6 `B_*` timing bound(line 527–566) — 전부 `value_ms: null`·`owner: TBD`·`semantics: hard_maximum`**:

| VP-002 키 (line) | failure_response | measurement_source | rationale (요지) |
|---|---|---|---|
| `B_post_trade_effect_to_obligation_commit` (527) | `STOP_NEW_RISK_AND_QUARANTINE_CAPACITY` | `broker_effect_ptol_commit_and_rcl_capacity_trace` | external economic effect → durable PTOL obligation identity + conservative RCL coverage 최대 interval; expiry/missing evidence는 capacity release 안 함 |
| `B_post_trade_change_detect` (534) | `STOP_NEW_RISK_AND_MARK_UNKNOWN` | `post_trade_source_statement_break_and_correction_trace` | material settlement/cash/collateral/borrow/custody/statement/break/correction/finality change → detection 최대 interval |
| `B_post_trade_break_to_restrict` (541) | `HALT_OR_CONTAIN` | `post_trade_break_ptol_rcl_and_authority_trace` | confirmed/suspected break → restrictive authority + conservative capacity 최대 interval; workflow/operator ack가 연장 못 함 |
| `B_post_trade_invalid_to_egress_deny` (548) | `HALT` | `post_trade_generation_finality_break_and_egress_trace` | invalid/stale post-trade state → dependent external-economic send 거부(final egress) 최대 interval; permissive cache 없이 |
| `B_post_trade_generation_fence` (555) | `HALT` | `ptol_generation_writer_consumer_rcl_authority_and_egress_fence_trace` | generation advance/restore/correction/owner-replace → stale writer/consumer/proof/authority/RCL/egress 거부 최대 interval |
| `B_statement_coverage_gap_detect` (562) | `STOP_NEW_RISK_AND_MARK_UNKNOWN` | `statement_pagination_cutoff_revision_and_coverage_trace` | incomplete/truncated/stale/conflicting/preliminary/common-mode statement coverage 탐지 최대 interval |

**(b) 5 `MAX_*` age bound(line 747–751) — 전부 `null`·`# APPROVE per ...` 주석**:

| VP-002 키 (line) | APPROVE 주석 (요지) |
|---|---|
| `MAX_post_trade_obligation_snapshot_age_ms` (747) | per obligation class/scope; stale active-set state blocks dependent new risk |
| `MAX_post_trade_finality_proof_age_ms` (748) | per exact field/class; stale proof cannot establish current finality or release capacity |
| `MAX_statement_coverage_manifest_age_ms` (749) | per source/scope; stale/unknown coverage remains incomplete |
| `MAX_unresolved_post_trade_break_age_ms` (750) | escalation deadline only; age never converts a break to resolved |
| `MAX_pending_external_transfer_age_ms` (751) | per transfer rail; timeout never proves non-acceptance, failure, or finality |

**(c) 8 currentness identity slot(line 107–114) — §22 dimension 1–3, 전부 `TBD`/`null`**: `post_trade_finality_policy_
{id(107),generation(108,null),digest(109)}`·`active_economic_obligation_set_{id(110),digest(112)}`·`post_trade_obligation_
generation(111,null)`·`statement_coverage_manifest_{id(113),digest(114)}`. **numeric bound가 아니라 identity/generation/
digest 좌표**(VP 주입·§3.2 ordering generation).

**19키(6 B + 5 MAX + 8 identity) 전부 null/TBD** — 즉 **값도 소유자도 미승인**이며, 두 축 모두 Bounds-Approver/Phase-0
게이트다(§9.2-1). per-source/per-broker 수치는 Broker/Clearing/Custodian/Banking Capability Profile·reference-source
INSTANCE. **PTF Phase-1 코드는 이 19키를 주입 파라미터/좌표로만 받고 값을 하드코딩·기본값 부여하지 않는다**(값 부재 ⇒
fail-closed). **§8.2 confirmed candidate 신규 키 0건**: PTF decision 술어는 orthogonality(enum non-implication)·
idempotency(`classify_record_pair`)·completeness(set)·no-favorable-default(magnitude 병존)·보존(합)으로 L1-decidable
하며 numeric bound를 결정 내부에 두지 않는다 — 19 VP 키는 전부 런타임 timing/age/currentness라 EV-L2/3 통합 단계 소비이고
Phase-1 순수 커널 밖이다.

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. **`tos/src/tos/posttrade/` 패키지 구현**(EV-L1): `_base.py`(canonical re-export + `AllFalsePostTradeConsequence`
   all-false)·`vocabulary.py`(**9 enum** — `PostTradeObligationLifecycleState`·`FinalityDimensionKind`·`ObligationLeg
   Direction`·`CashKind`·`MarginCollateralState`·`StatementClass`·**`EventObligationLegKind`(m6 신설)**·`ObligationCommit
   Outcome`·`PostTradeDisposition`, 개별 계수 + 19 주입 토큰 상수)·`records.py`(`EconomicObligationRecord`·`PostTrade
   FinalityProof`·`StatementCoverageManifest`·**`PostTradeBreakRecord`(m5)**·`ObligationLeg`·**`ObligationLegScope`(M8)**·
   `MonetaryLeg`·`CollateralAllocation`)·`predicates.py`(**19 술어**)·`state.py`(obligation/finality/statement append-only
   generation order — ordering 좌표).

   **술어 19종 개별 계수(v1.1 — M2 `finality_proof_current` 신설·M3 rename)**: (1) `finality_dimensions_orthogonal`(§5.1,
   M1 dead-param 삭제) · (2) `obligation_leg_set_complete`(§5.1) · (3) `obligation_commit_idempotent`(§5.2, M7 prior
   계약) · (4) `monetary_leg_conservative`(§5.3) · (5) `netting_requires_positive_proof`(§5.3) · (6) `missing_counterleg_
   is_adverse`(§5.3) · (7) `collateral_no_double_use`(§5.4) · (8) `margin_collateral_states_distinct`(§5.4) · (9)
   **`cash_kind_matches_requirement`(§5.4 — M3 rename, 구 `cash_kinds_not_substitutable`)** · (10) `obligation_legs_
   from_event_complete`(§5.5, m6 enum) · (11) `event_state_not_obligation_finality`(§5.5) · (12) `statement_coverage_
   complete`(§5.6) · (13) `statement_sources_independent`(§5.6) · (14) `absence_is_negative_evidence_only`(§5.6, M6
   correction-semantics) · (15) `finality_proof_class_specific`(§5.7) · (16) `finality_proof_non_transferable`(§5.7,
   M8 `ObligationLegScope`; **v1.2 에라타 — keyword-only `target_obligation_ref`/`target_obligation_version`
   확장, 술어 수 불변**) · (17) **`finality_proof_current`(§5.7 — M2 신설, generation 비교)** · (18) `post_trade_
   consequence_all_false`(§5.7) · (19) `post_trade_disposition`(§5.8 — C1 16-conjunct 확장). **19**(§2.0 다이어그램·§7
   목록·§9.1과 일치).
2. **property test 하네스**(§7): `tos/tests/posttrade/` — core 19 + ∅ 양방향 22행 + forgery 2종 + late-fill + truthy-
   sentinel 극성(음극성 필드 **부재 assert**·phantom 필드 부재 assert) + 좌표 비붕괴 + seam cross-check **10종**(rcl·are·
   recon·nontrade·brokercap·egress·**cur**·orthostate·**vocab**·canonical) + 19 주입 토큰 drift-lock + **§4.8 22행 ↔
   disposition 16 conjunct 1:1 property**(C1 — 각 conjunct False가 대응 행 disposition을 내는지 전수).
3. **import-closure 테스트**(§7.1) + `tos-firewall` required green.
4. **구현 단계 예고 반영(#18/#21 defect-class #7 상속)**: (a) **enum member→value 바인딩 단언**(value drift lock);
   (b) **`_ID_FIELD` drift lock**(digest covered-field set 고정·self-exclusion 검증); (c) **forgery 전략 명시**(§7
   same-id/diff-digest hypothesis 전략, falsy 축 포함); (d) **§7.1 allowlist**(자기+canonical+ordering ⊆ 형식); (e)
   **19 주입 토큰 전수 drift-lock**(#21 MINOR-1 "13개 중 1개 누락" 교훈 — 개별 계수 강제).
5. **적대적 코드 리뷰 → 게이트**(품질 파이프라인, 운영자 표준지시 2026-07-25).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §29 Open Questions(line 703–716, 12항) ↔ Phase-0:

1. **numeric bound·currentness**(§8·ADR §29 Q9 line 711·Q10 line 712): 19 VP 키(6 B_* + 5 MAX_* + 8 currentness
   identity) 값 + owner — Bounds-Approver.
2. **source-authority rules**(ADR §29 Q2 line 704): 각 obligation class의 approved broker/clearing/custody/banking/
   statement source·source-authority rule — reference-source INSTANCE.
3. **finality recipes**(ADR §29 Q3 line 705): instruction-acceptance/settlement/cash-availability/collateral-eligibility/
   custody-title/fee-finality/borrow-discharge/assignment/delivery/CA-completion 구별 recipe — 아키텍처 승인.
4. **statement coverage/pagination/cutoff/revision/common-mode rules**(ADR §29 Q5 line 707): 승인 규칙 — 아키텍처 승인.
5. **legally enforceable netting/setoff/cash-reuse/collateral-reuse/custody-availability rules**(ADR §29 Q6 line 708):
   지원 규칙 — 법무·인간 승인.
6. **initial restricted-live scope**(ADR §29 Q7/Q8 line 709–710): 어떤 external economic instruction·account·entity·
   currency·settlement-system·custodian·broker·instrument·borrow·CA class가 초기 범위인지 — 인간 scope 승인.
7. **brokercap settlement/custodian/statement capability dimension 신설 여부**(ADR §29 Q2/Q5): brokercap에 부재 —
   brokercap 확장 vs 기존 dimension 주입 — 아키텍처 판단.

ADR §29 line 716 "Unresolved questions reduce or prohibit live scope. They never permit a weaker default, expire an
obligation, or release capacity." — 본 계약도 동일(§0.2 fail-closed).

---

## 10. 개정 로그 + 비준 체크리스트 + 판단 지점

### 10.1 개정 로그

- **v1.2 (2026-07-27) — 에라타(의미 변경 아님·보수 방향·비준 효력 유지). 발견 경로: 구현 후 적대적 코드 리뷰
  MAJOR**(판정 **ACCEPT-WITH-MINOR**; CRITICAL 0·구현 fail-open 0·MAJOR 1[설계 상속]·MINOR 6·NIT 3; 뮤테이션
  124중 99 검출·13 등가 증명). 구현은 v1.1 계약에 **충실(FAITHFUL)**했고 결함은 **계약 텍스트 측**이었으므로
  오케스트레이터 판정으로 **처방 (a) — 계약과 코드를 함께 정정**을 채택했다. 정정 3건:
  - **§5.7 시그니처 확장**: `finality_proof_non_transferable`에 **keyword-only** `target_obligation_ref: str | None
    = None` / `target_obligation_version: str | None = None`을 추가하고, 제공 시 `proof.obligation_ref` ·
    `proof.obligation_version`과의 일치를 **추가 요구**한다. **근거 = ADR §11 line 320 "exact obligation identity"**
    (§11 line 328 6성분 scope는 leg를 지명할 뿐 obligation을 지명하지 않는다). **결함 경로**: 동일 6성분 scope를
    공유하는 두 obligation 사이에서 한쪽의 proof가 다른 쪽에 유효 판정 ⇒ §4.8 행 10 rank 1 미발화 ⇒
    `POST_TRADE_ADMISSIBLE` 도달 가능.
  - **§7 canary 추가**: §4.8 행 10에 **cross-obligation 변종**(동일 scope·다른 `obligation_ref` ⇒ False, 동일
    obligation·다른 version ⇒ False, 완전 일치 ⇒ True) 및 미제공 시 하위호환 거동 진리표.
  - **제목/비준 parenthetical**: v1.1 → **v1.2 에라타** 표기 + 상단 에라타 고지 블록 신설.

  **효력 판정**: 두 인자는 **선택적**이며 제공 시 판정을 **좁히기만** 한다(`True`→`False`만 가능) ⇒ 어떤 허용도
  넓히지 않는다. 따라서 v1.1 비준 효력·§0.2 비-acceptance·**닫는 PTF-EV = 0건**·EV-L1-complete 미주장 규율은
  전부 **불변**이며, **술어 19종 카운트도 불변**(시그니처 확장이지 신규 술어가 아니다). 동반 반영된 리뷰 지적
  (설계 텍스트 무영향·테스트 전용): MINOR-1 phantom 필드 검사 부분일치화(affix 관통 봉인)·MINOR-2
  `_REQUIRED_COVERED` 내용 pin + required 필드 부재 시 `issue()` 거부 양성 canary·MINOR-3 행 canary가 공개
  `VOID_TABLE_ROWS`를 조회(추적 데이터 drift 봉인)·MINOR-4 생문자열 `CashKind`/`MarginCollateralState` 거부
  (`is` 하드닝 잠금)·MINOR-5 falsy 위조(`releases_capacity=0`) 거부 canary. MINOR-6은 설계 명문에 충실하여 무변경,
  NIT 3건은 조치 불요.
- **v1.0 (2026-07-27)**: 최초 저작. ADR-002-030(739줄) 전독 → EVIDENCE-REGISTER-002.csv CSV-aware 실측(PTF-EV 12행·
  L1 슬라이스 5행 001·002·004·006·008·+Broker 12/12·+Security 6행) → IMPLEMENTATION-PLAN-002 line 221 실측(PTF-EV-001
  property test 명시 지목) → VER-002-001 line 142/171 실측(EV-L1=Model/Property·EV-Ln earliest non-live stage) →
  VP-002 19 PTF 키 실측(6 B_* line 527–566·5 MAX_* line 747–751·8 currentness line 107–114 전부 null/TBD) → 12+ 형제
  패키지 public surface 코드 실측(canonical `classify_record_pair` 5-member·rcl `FINAL_QUANTITY_PROOF`·are `SETTLEMENT_
  CASH_CURRENCY`/`BenefitKind.NETTING`·recon `POST_TRADE_OBLIGATION_IDENTITY_AND_VERSION`/common-mode·brokercap `fqp_
  adequate`·egress `credential_route_authority_disjoint`·orthostate `KnowledgeState`·nontrade `NonTradeEventWorkflow
  State`) → §0–§10 저작. 핵심 판정: (a) 패키지 `tos.posttrade`(ptf 차점), (b) produced-token·sibling edge 0·capacity-
  non-mutating, (c) `CapacityVector`/`ProjectedCell`/`FieldConfidence` REUSE 기각(edge-0), (d) obligation-set gross-
  병존 이중 계상 정합(구조적 no-favorable-default·are/rcl 이연), (e) fill-commit-idempotency 명제 = PTF 고유(iap/rcl/
  nontrade와 canonical 원시의 네 독립 하류·phantom edge 차단), (f) settlement-direction/finality-monotonicity §4.5 진리표
  (enum non-implication·수치 미사용), (g) commit idempotency §4.6 진리표(5-member 전수), (h) **nontrade 경계 4-verdict**
  (event-lifecycle≠obligation-lifecycle·transition-leg≠obligation-leg·confidence≠finality·3중 netting 분리).
- **v1.1 (2026-07-27)**: **독립 비평 리뷰(REVISE — CRITICAL 1·MAJOR 8·MINOR 7·Gap 6) 전건 반영**(소싱 품질은 시리즈
  최고 — 공격 지점 7 중 3건 "주장 정확"으로 불발: nontrade 경계·staged 정직성·VP 19키 clean). 각 수정 전 1차 소스
  재확인(반론 0 — 전 항목 실측 확인). 항목별:
  - **C1(disposition fail-open 봉인 — #21 C1 동형 재발)**: `post_trade_disposition` 시그니처를 **8→19 입력**(16 bool
    conjunct + commit_outcome + confidence + availability)으로 확장하고 ADMISSIBLE 양성 conjunction에 전 conjunct 편입
    (§5.8). v1.0은 `sources_independent`·`proof_class_specific`·`proof_non_transferable`·`cash_kind_ok`·`margin_states_
    distinct`·`absence_gate_ok`·`event_legs_complete`·`event_state_not_final_ok`·`proof_current`를 누락해 PTF-INV-014/
    005·§11:328 위반 상태로 ADMISSIBLE 도달이 가능했다. **§4.8을 16→22행**으로 확장(신규 17–22: margin-state·cash-kind·
    event-legs·absence-gate·proof-class-specific·proof-current)해 disposition 16 conjunct ↔ §4.8 행 **문자 1:1**
    성립·§7 1:1 property 구현 가능화.
  - **M1**: `finality_dimensions_orthogonal` dead param `proven_dimensions` 삭제·반환 명제 1문장 확정(claimed 자기
    proof만 참조)·`if claimed is None or not proof_map: return False` 구조 가드(§5.1·§4.1 canary 정합).
  - **M2**: finality reopen 봉인 — `finality_proof_current(proof, active_generation) -> bool`(generation 정수 비교,
    L1-decidable) 신설(§5.7)·§4.5-B 9번째 행(PROVEN→correction-invalidated)·disposition 편입·"3 술어 각 cell 검사"를
    cell별 소유 술어로 정정(행 5·6 = ordering/finality_proof_current).
  - **M3**: `cash_kinds_not_substitutable` 극성 자기모순 정정 → `cash_kind_matches_requirement = (requested is
    available)` 단일 명제(§5.4).
  - **M4**: rcl `FINAL_QUANTITY_PROOF` 앵커 `vocabulary.py:91`→**:94**(실측 — :91=RECONCILIATION_PROOF; 2개소).
  - **M5**: cur 진부화 정정 — cur은 v1.0 후 **커밋됨**(`1390ef9d`, 실측 disk 실재·`DimensionKey.POST_TRADE`:146). 6개소
    갱신(frontmatter·§0.2·§0.3·§2.0·§6.5·checklist)·패키지 수 **25 committed·PTF=26번째**·§3.5 §22 행에 cur 좌표
    (`DimensionKey.POST_TRADE`·`ProofResult`:96–98·`CurrentnessAdmission`:113–114)·drift-lock 토큰 17→**19**(cur 2)·
    §7 `test_seam_cur` 신설·§0.3 열거 갱신.
  - **M6**: `absence_is_negative_evidence_only`의 `correction_horizon_passed`(시간 — PTF-INV-004 line 164 금지 신호)를
    **`correction_semantics_support`**(ADR:448 "correction semantics ... positively support")로 교체·`is True`(§5.6).
  - **M7**: `obligation_commit_idempotent` prior 선정 계약 명시(nontrade `predicates.py:526` 선례를 **primary id or
    idempotency key 2-축**으로 확장) — CRITICAL_CONFLICT 우회·DIVERGENT_EMISSION 누락 2 오독 차단·§4.6 "DISTINCT는
    계약 위반 시에만" 각주(§4.6·§5.2).
  - **M8**: `ObligationLegScope` phantom 정식 등재(§2.1·§9.1 — leg/account/currency/value-date/source-revision/
    finality-class value 모델, ADR §11:328).
  - **MINOR/Gap**: m1 §1 표 §7 authority **12→13행**(line 228–240 재계수); m2 "§23 line 23"×4→**§1 line 23**; m3 약한
    앵커 정정(egress `credential_route_authority_disjoint` `__init__.py:189`→**`egress/predicates.py:405`**·brokercap
    `CapabilityStatus` `:49`→**`vocabulary.py:29`**); m4 "§16 line 309↔§17 line 414"에 **ADR-002-010/ADR-002-030 한정자**
    부여(-030에도 §16 존재); m5 `PostTradeBreakRecord` 등재; m6 event-leg 9축 **`EventObligationLegKind` enum화**(§2.2-5b·
    drift-lock); m7 §2.1 result enum **`_NonTruthyStrEnum`** 통일; Gap: **PTF-AC-001..012 커버리지 표 §1.1 신설**·
    `line_item_absent: bool|None`·cash-kind/proof-class-specific §4.8 행(C1 흡수)·`test_seam_cur`. **Q답**: Q1 event-
    state↔finality 합성=disposition 입력 확정(C1); Q2 순위 근거 명문화(§5.8 — CONFLICTED>QUARANTINED>TRAPPED = 모순>
    unbounded-scope>bounded); Q3 `StatementClass`=`StatementCoverageManifest.statement_class` 필드(§2.1·§2.2-5).

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] **register 실측 재확인**: PTF-EV 12행·L1 슬라이스 5행(001·002·004·006·008 전부 `EV-L1/2/3+Broker`, 008 `+Security`)·
      +Broker 12/12·닫는 PTF-EV 0건(CSV-aware 파싱 — 제목 쉼표 003/008 등). 재검증 카운트 일치·정정 없음.
- [ ] **staged EV 정직 분리**: core 5행도 L1 부분만·`/2`·`/3`·`+Broker`·(008)`+Security` 잔여 명시·EV-L1-complete 주장 0·
      not-Phase-1(003/005/007/009/010/011/012) over-claim 0.
- [ ] **앵커 규약**: PTF-INV/PTF-EV/PTF-AC/§-clause/SAFE만 앵커·새 INV/AC/EV 시리즈 창작 0(§0.4g — PTF 자체 INV-001..018
      보유).
- [ ] **sibling edge 0·canonical/ordering만 import**(§0.3 allowlist·§7.1)·PROMOTE 0·`CapacityVector`/`ProjectedCell`/
      `FieldConfidence` REUSE 0(§0.4c).
- [ ] **소유권 분할표(§3.5)**: 12+ 형제 소유 vs PTF 소유 코드 실측 signature+라인 정확·권위 중복 0(rcl capacity·are risk/
      netting-benefit·recon confidence·brokercap capability·nontrade event-identity·egress transmission).
- [ ] **명제 동일성 4-verdict(§3.5 시리즈 규율 3)**: (1) event-lifecycle(nontrade) ≠ obligation-lifecycle(PTF)·ADR-002-
      010 §16 line 309↔ADR-002-030 §17 line 414 상호 이연; (2) transition-leg(nontrade `CredibleTransitionLegKind`) ≠ obligation-leg(PTF
      `ObligationLeg`); (3) confidence(recon `FieldConfidenceClass`) ≠ finality(PTF `PostTradeFinalityProof`)·PTF-INV-
      005; (4) 3중 netting(nontrade transition-envelope ≠ PTF obligation-leg ≠ are `BenefitKind.NETTING`). FQP(rcl
      `FINAL_QUANTITY_PROOF` order-release) ≠ post-trade-finality(PTF 10-dim) 포함.
- [ ] **방향 극성 진리표(§4.5)**: A settlement-direction/netting(receivable/payable gross·proof-token 요구)·B finality-
      monotonicity(UNKNOWN→PROVEN proof-only·generation monotone·no-destructive-overwrite·PROVEN⊄consequence) 양방향
      검산·수치 하드코딩 0·**"finality 단조"가 naive once-proven이 아니라 generation-monotone+non-implication+append-only+
      grants-nothing임**(correction reopen 반영).
- [ ] **idempotency 진리표(§4.6)**: `classify_record_pair` **5-member 전수 매핑**·late-fill effect count==1·**forgery
      2종 분리**(same-primary-id⇒`CRITICAL_CONFLICT` / same-idempotency-key⇒`DIVERGENT_EMISSION`, 둘 다 `REJECTED_
      CONFLICT`)·`COMMITTED_ONCE` prior-None 선행 게이트.
- [ ] **finality-grants-nothing(§4.7·§5.7)**: `AllFalsePostTradeConsequence` all-false·`FINALITY_PROVEN`도 capacity-
      release/available-cash/title/permission/transmit 0·**구조적 부재**(release/credential/route/send 필드 0).
- [ ] **disposition 생산자 실재·C1 봉인(§5.8)**: `post_trade_disposition`이 `PostTradeDisposition`의 **유일한 생산자**·
      전순서 5-우선순위 결정적(Q2 근거 명문)·**16 bool conjunct 전 수용**(v1.0 누락 9종 — sources_independent·proof_
      class_specific·proof_non_transferable·cash_kind_ok·margin_states_distinct·absence_gate_ok·event_legs_complete·
      event_state_not_final_ok·proof_current — 편입)·`POST_TRADE_ADMISSIBLE`이 양성 conjunction identity로만 도달·**§4.8
      22행 ↔ 16 conjunct 문자 1:1**(#21 C1 동형 재발 봉인).
- [ ] **∅ 구조 가드(§5.1)**: 빈 `required_legs`가 **술어 내부에서** `False`(하류 "별도 처리" 위임 0건)·rcl `credible_
      union_capacity` empty⇒`ValueError` 선례와 동일 명제.
- [ ] **truthy-sentinel 극성 분기(§4·§7)**: 양극성 `is True`·result identity(`is POST_TRADE_ADMISSIBLE`/`is COMMITTED_
      ONCE`)·fall-through 승격 0·**음극성 필드 0건 정직 공개 + phantom 필드(`releases_capacity_flag`·`favorable_netted`·
      `can_transmit`·`title_proven_by_ack`) 부재 assert**.
- [ ] **∅-공허 양방향(§4.8)**: 금지+허용 canary 둘 다·**22행 ↔ §7 22항목 1:1**·금지동사 **15개**(개별 번호 계수).
- [ ] **카운트 대조 전수화(§2.2 defect-class #4)**: 12 lifecycle·10 finality dimension·8 leg direction·6 cash kind·
      8 margin state·3 statement class·**9 event-obligation-leg(§2.2-5b)**·6 outcome·5 disposition·**9 enum**·**18 PTF-
      INV(§4.0)**·12 rejected(§4.9)·**8 obligation-record 필드(§2.2-7)**·6 FQP-does-not-prove·9 §14 cash·8 §16 borrow·
      9 §17 leg·7 §18 custody·7 §19 manifest·13 §7 authority(ADR)·**12 PTF-AC(§1.1)**·**19 술어(§9.1)**·**22 §4.8 행 ↔
      16 disposition conjunct 1:1** 원문 항목 수 병기·개별 계수.
- [ ] **19 주입 토큰 전수 drift-lock(§3.4·§7)**: 누락 0(#21 MINOR-1 교훈) — 19 토큰 개별 §7 seam assert(cur 2 포함).
- [ ] **broker-agnostic·수치 하드코딩 0**(§0.3·§8): 어떤 broker/clearing/custodian/bank 명명 0(+Broker 12/12 지배
      문서에서 특히)·19 VP 키 null/TBD 주입·brokercap settlement/custodian/statement dimension 부재 정직 공개.
- [ ] **비-acceptance**: 닫는 PTF-EV 0·EV-L1-complete 주장 0·restricted-live/production 미승인(§0.2)·CUR 세션 A WIP doc
      미인용(ADR-002-024 원문만).

### 10.3 운영자 판단 지점 (요약)

1. **타입 REUSE(edge-1) vs plain-type obligation-record producer(edge-0, 채택)**(§0.4c): Phase-1은 finality-orthogonality·
   idempotency·completeness·no-favorable-default·보존이 L1 핵심이고 cell/vector/confidence 산술은 rcl/are/recon 소유
   이므로 **edge-0** 채택. 미래 런타임에서 PTF이 cell/vector를 직접 조립해야 하면 edge-1 승격 가능. **권장: edge-0**
   (nontrade #21·replacement #18 동형).
2. **패키지 명명 `tos.posttrade` vs `tos.ptf`**(§0.4a): semantic 토큰 우선(#18 `pr`→`replacement`·#21 `nt`→`nontrade`
   선례)으로 `posttrade` 채택(nontrade와 평행). register 두문자 정합·terse 선호 시 `tos.ptf` 치환 가능(load-bearing
   아님). **권장: `posttrade`**.
3. **fill-commit-idempotency 형제 소비 여부**(§0.4e): 명제 상이(fill-obligation-commit ≠ authorization-token ≠ capacity-
   command ≠ event-application) ⇒ **미소비·canonical 직접 앵커**. **권장: 미소비**(네 독립 하류).
4. **cash-kind/borrow/custody 어휘 substrate 범위**(§6): Phase-1은 어휘·non-substitution 구조만 두고 availability/
   discharge/title PROOF은 not-Phase-1(PTF-EV-003/005/007 L2/3). **권장: substrate만·PROOF 이연**(over-claim 금지).
5. **brokercap settlement/custodian/statement dimension 신설 여부**(§9.2-7): brokercap에 부재(실측) — Phase-1은 기존
   `POSITIONS_BALANCES_MARGIN`/`CORPORATE_ADMINISTRATIVE_EVENTS`/`FILL_EVENTS` 주입 소비. 전용 dimension 신설은 Phase-0
   brokercap 확장 판단. **권장: 기존 주입 + Phase-0 open question 노출**.

### 10.4 독립 리뷰어 공격 지점 (open questions)

- **G1 — finality-dimension non-closed vs closed**: `FinalityDimensionKind` 10종을 PTF-INV-002 열거로 closed 두었다
  (§2.2-2). 리뷰어는 broker/custody-specific finality dimension(예: banking-rail settlement)이 10에 없어 누락되면
  `finality_dimensions_orthogonal`이 그 축을 놓치는지 공격할 것 — **방어**: 10은 ADR PTF-INV-002 verbatim 열거이며,
  추가 dimension은 Phase-0 finality-recipe(§9.2-3)에서 승인되면 enum 확장(구조적 non-implication은 불변). Phase-1은
  ADR 열거에 정확히 앵커(창작 0).
- **G2 — obligation-leg no-netting의 proof-token 신뢰**: `enforceable_netting_proof: bool|None`을 caller 주입으로 두어
  (§5.3), enforceable netting을 구조적으로 강제하지 않고 flag(양극성)로 받는다. 리뷰어는 caller가 proof 없이 `True`를
  위조하는지 공격할 것 — **방어(정직 공개)**: Phase-1은 이를 주입 flag로 두되 **both-gross-magnitude 병존**을 별도
  conjunct로 요구(netting valid는 receivable·payable 둘 다 gross present ∧ same-scope ∧ proof-token — 하나라도 부재 ⇒
  gross)하고, 실제 legal-enforceability 판정은 Phase-0 netting rule(§9.2-5)·are `BenefitKind.NETTING`(EV-L2/3)이 소유.
  구조적 파생(#18 M6 선례)이 flag 단독 신뢰를 완화한다.
- **G3 — `original_retained`/coverage flag 주입 신뢰**: `original_retained`·`coverage_complete`·`correction_horizon_
  passed`·`source_capability_supports`를 양극성 주입 flag로 둔다(§5.2/§5.6). 리뷰어는 caller가 overwrite/미완-coverage
  후 `True`를 위조하는지 공격할 것 — **방어(정직 공개)**: Phase-1은 양극성 취급(`is True`만·`is not True`⇒reject)하고,
  실제 append-only 강제는 ordering append-only 순서(EV-L3)·statement coverage completeness는 broker statement pagination
  runtime(EV-L2/3)이 소유(§3.2·§6). 구조적 강화(magnitude/set 파생)로 승격할지는 판단 지점.
- **G4 — nontrade 경계의 event-state 주입 신뢰**: `event_state_not_obligation_finality`가 nontrade `APPLIED_LOCAL`/
  `RECONCILED`를 주입 토큰으로 받는다(§5.5). 리뷰어는 nontrade event가 실제 obligation을 이미 final로 만든 상황(예:
  cash-settled CA)에서 PTF가 UNKNOWN을 고집해 가용성 위반인지 공격할 것 — **방어**: 그것이 정확히 ADR §17 line 418
  ("event state ... does not prove its resulting obligations final")·PTF-INV-004의 요구다 — obligation finality는 오직
  dimension-specific proof(§5.1)로만 오고, event-state는 necessary-context이지 sufficient-proof가 아니다. 가용성은
  finality proof(EV-L2/3+Broker)가 회복하며 Phase-1은 보수적으로 UNKNOWN 유지(과잉-보수는 안전 방향).
- **G5 — statement-source common-mode의 shared-dependency set 신뢰**: `statement_sources_independent`가 shared-dependency
  set(book/parser/administrator/transport)을 주입받아 disjoint 검사한다(§5.6). 리뷰어는 shared-dep set 자체가 caller
  선언이라 공통 모드를 숨기는지 공격할 것 — **방어(정직 공개)**: Phase-1은 disjoint 구조 검사만 소유하고, 실제 shared-
  dependency 발견(broker API와 statement가 한 book/transport 공유)은 +Security assessment(PTF-EV-008 +Security)·Phase-0
  common-mode rule(§9.2-4)이 소유한다. Phase-1은 declared-set disjoint의 구조 property만·미완 시 fail-closed.
- **G6 — obligation-set ↔ are cell-set / rcl union 커버리지 결속**: `obligation_leg_set_complete`(PTF)와 are risk 투영·
  rcl capacity union의 결속은 Phase-1 미실현·런타임(EV-L2/3)이다(§6.5). **택1 명시(#21 M5 선례)**: `obligation_set_
  covered` 주입 대조 술어 **미채택** — 결속을 성립시키려면 are `ProjectedCell`/rcl `CapacityVector` 좌표 REUSE(§0.4c
  기각 edge-1)로 돌아가거나 opaque id proxy(fail-open 서사)에 기대야 한다. Phase-1은 **런타임 잔여로 정직 이연**하고
  PTF-EV-010(`EV-L2/3+Sec`)에 귀속. 운영자가 edge-1 수용 시 재검토(§10.3-1).

---

> **문서 종료.** 본 계약은 `tos/src/tos/posttrade/` Phase-1(EV-L1) 순수·비전송·fail-closed 결정-무결성 모델 + hypothesis
> property test **설계**만 확정한다. 코드·테스트·git 커밋은 후속(§9.1)이며, 어떤 PTF-EV·ADR acceptance·restricted-live·
> production도 승인하지 않는다(§0.2). ADR acceptance는 오직 *실행된* evidence로만 온다(VER-002-001 §5).





