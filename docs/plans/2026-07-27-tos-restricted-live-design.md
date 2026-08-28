# 설계 문서 #25 — Restricted-Live Verification·Scope Promotion 계약 (2026-07-27, v1.1)

> **문서 번호 규약**: #24 = 세션 B의 PTF(ADR-002-030, 선점 — 병렬 세션 번호 규약, #18/#19 선례).
> 본 RLP(ADR-002-025) 문서는 **설계 문서 #25**다.

> ADR-002-025 (Restricted-Live Verification, Progressive Scope Promotion, and Production Authorization
> Governance — "RLP")를 Phase 1(EV-L1) 설계 계약으로 실현한다. **이 문서가 실현하는 것은 시리즈의
> "내용 소유자(content owner)이자 피이연자(deferee)"**다: egress(#22)와 cur(#23)는 restricted-live
> trial 청구군(Trial Policy / Plan / Run / Promotion Generation + remaining envelope + abort generation)을
> **opaque optional scalar 그룹으로 수용하고 그 내용 검증을 명시적으로 RLP에 이연**해 두었다(코드 실측
> verbatim: egress `state.py:196` "the actual trial-content validation is **deferred to RLP** (`tos.rlp`,
> not landed — design #22 §9.2 item 17), so egress cites no RLP code"; cur `state.py:140-141` "the actual
> trial-content validation is **deferred to RLP** (`tos.rlp`, not landed — design #23 §0.4f / §9.2 item 16),
> so cur cites **no** RLP code (phantom seal)"; egress `records.py:203` "opaque scalars; **RLP-deferred**";
> cur `vocabulary.py:131-132` "`RESTRICTED_LIVE_TRIAL` is the **conditional** dimension ... **RLP-deferred
> content**"). **본 계약은 그 이연을 회수한다** — cur(#23)가 형제의 complete-vector 집계 이연을 회수한
> 것의 거울상이되, 방향이 반대다: cur는 *상류 집계자*였고 RLP는 *상류 내용 소유자*다. egress/cur가
> **하류 소비자**로서 RLP-생산 generation을 opaque scalar로 나른다.
>
> **이 문서의 두 최대 위험은 서로 반대 방향이다.** (1) **over-realization(주 위험)**: RLP는 거버넌스
> ADR이라 *인간 절차*(independent review·promotion approval·production authorization)와 *런타임*
> (per-action final-egress binding·abort race·worst-credible-effect 계산·evidence 조립 무결성)의 색채가
> 압도적이다. 이들을 L1으로 오주장하면 안 된다 — 전부 인간/런타임/+Security/+Broker/evidence-owned.
> **L1-decidable 슬라이스는 4개 core 구조 완전성 술어 + 7개 얇은 predicate-only substrate 뿐**이며
> **이 정직한 경계가 본 문서의 최대 규율**이다(#22/#23 선례). (2) **duplication/over-reach**: 형제
> 소유(egress QCC/TrialClaims seal·cur RESTRICTED_LIVE_TRIAL 차원·hag effective-principal/quorum·
> evidence SegmentCommitmentScheme/gap/causal-chain·rcl CapacityVector/worst-credible-effect·liveauth
> Live Authorization·spg policy activation)의 *비즈니스 내용*을 RLP가 재판정하는 것. 각 owner verdict/
> generation/digest를 **주입 소비**만 하고 재저작하지 않는다.
>
> **비준 기록: 2026-07-27 운영자 위임 자동 비준(v1.1; 2026-07-25 지시 — 독립 비평 리뷰 REVISE[CRITICAL 0·
> **MAJOR 0**·MINOR 3 — 시리즈 첫-초안 최고 성적: ~30 인용 전수 실측 phantom 0·EV 4/7/1 정확·over-realization/
> duplication 반론 전부 기각]의 minimal edit set 전량 반영 후 집행. v1.1: MINOR-1 §9:277→RLP-INV-002:154
> 인용 정정·MINOR-2 §13→§12 release(-029) 정합·MINOR-3 `promotion_complete_claim` 필드 명시[coexistence
> seal 3-of-3 대칭]. 판단 지점: `tos.rlp` 명명[soft load-bearing — 형제 2곳이 이름으로 이연]·edge 0·
> content-owner 미러 채택. 효력: `tos/src/tos/rlp/` Phase 1 착수).** 본 문서는 GOV-001의 세 거버넌스 행위(비준 / ADR
> acceptance / live authorization) 중 어느 것도 수행하지 않는다. tos-spec을 수정하지 않으며 어떤
> RLP-EV/RLP-AC/acceptance/비준도 선언하지 않는다. 기존 `docs/plans/**` 무수정. 미착지 상류(-026 WDR·
> -027 SIR·-028 STM·-029 SCI·-030 PTF) 코드 인용 없음(전부 ADR 원문만·phantom seal).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. **패키지 명명** `tos.rlp`(register prefix `RLP` 소문자 1:1·terse-lowercase 관행; §0.4a). **naming이
   *soft load-bearing***: 두 착지 형제(egress `state.py:196`·cur `state.py:140`)가 RLP-이연 주석에서
   `tos.rlp`를 **이름으로 명시 인용** — 다른 이름을 쓰면 그 참조가 orphan이 된다(cur가 §7.1 allowlist로
   naming을 non-load-bearing으로 둔 것과 대비되는 본 문서 특유점). runner-up `tos.restrictedlive`·
   `tos.trial`·`tos.promotion`(기각·§10.1).
2. **핵심 아키텍처 판정 — RLP = trial-content 소유자·egress/cur = per-boundary consumer(본 문서 최대
   판정·§0.4b).** egress/cur 코드가 스스로 RLP로 이연했음을 **이름까지 명시해 증언**한다. RLP는 상류
   내용 소유자로서 `TrialPolicy`·`ExactTrialPlan`·`TrialRun`·`TrialEvidencePackage`·`CoverageClaim`·
   `ProductionScopePromotionDecision`·`GateStatusLadder`를 저작하고, 그 generation 좌표가 egress
   `QuorumCommitCertificate`/cur `SafetyCurrentnessVector`의 opaque `TrialClaims` scalar로 **하류에 흘러간다**.
   **RLP는 egress/cur를 import하지 않으며**(sibling edge 0·게다가 egress/cur가 RLP를 소비하므로 import 시
   순환) **그들의 boundary seal을 재저작하지 않는다**.
3. **EV 3분류(행별 정직)** — **core(L1-floor) 4행 {RLP-EV-001 Exact Pre-Registered Scope·005 Evidence
   Completeness and Negative-Result Retention·006 Coverage and Non-Extrapolation·012 Gate Honesty and Status
   Separation — 전부 `EV-L1/3`}**(**거버넌스 6부작 중 L1 접근성 최상·좌표 태그 없는 순수 `EV-L1/3` 4행**·
   survey line 237/517) / **predicate-only 7행 {002·003 `EV-L2/3+Broker`·007·008·010 `EV-L2/3+Security`·009·011
   `EV-L2/3+Broker`}** / **not-Phase-1 1행 {004 Abort Dominance and Race `EV-L3+Security`}**. **닫는 RLP-EV =
   0건**(§1). "EV-L1-complete 주장 금지".
4. **중심 L1 술어(§5·4 노른자)** — `plan_scope_exact_and_complete`(RLP-EV-001·노른자 1)·
   `evidence_package_complete`(RLP-EV-005·노른자 2·negative-result retention)·`coverage_supports_claim`
   (RLP-EV-006·노른자 3·비외삽 부분집합)·`gate_status_separated`(RLP-EV-012·노른자 4·상태 분리). 전부 순수·
   fail-closed·전 owner verdict/generation/digest는 주입.
5. **over-realization + duplication 이중 경계 명시(§1·§6c·§3.5)** — trial 실행(§13 per-action egress
   binding)·abort dominance/race(§15)·worst-credible-effect 계산(§10)·independent review + promotion
   approval(§18)·production authorization(§19)·evidence 조립 무결성(§16 SegmentCommitmentScheme)은 **전부
   인간/런타임/+Security/+Broker/evidence-owned**; 형제 소유 비즈니스 내용은 전부 주입 소비. L1은 **plan/
   package/coverage/gate 구조 완전성·단일-사용·비외삽 부분집합·상태 분리** 판정만.
6. **소유권/seam 분할표(§3.5) — 본 문서 최대 함정.** egress(QCC/TrialClaims boundary seal·소유)·cur
   (RESTRICTED_LIVE_TRIAL conditional 차원·소유)·hag(effective-principal collapse + quorum·소유)·evidence
   (SegmentCommitmentScheme + gap + causal-chain·소유)·rcl(CapacityVector + worst-credible-effect·소유)·
   liveauth(Live Authorization·소유)·spg(policy activation generation·소유)·iap(single-use consumption
   *shape* 선례)·authority(epoch floor + non-revival 선례)를 **RLP가 재저작하지 않는다**. **sibling edge 0**(§3.4).
7. **선제 봉합** — ∅ 양방향(mandated/observed/element-class set 부재 ⇒ deny)·집합 양방향(claimed ⊆ observed·
   mandated ⊆ bound both-ways)·truthy-sentinel 구조 봉인(`PlanResult`·`PromotionResult`·`TrialRunState`
   `__bool__ ⇒ TypeError`)·all-false trial authority·malformed-model 자기방어(positive-claim + incomplete-group
   coexistence seal — egress QCC `_trial_claim_completeness` 동형)·**극성 규율 전 적용(음극성 `is not False`·
   양극성 `is not True`·#22 MAJOR-2 재발 방지)**·**그룹 reconcile(전-package 보수·no-union·#22 MAJOR-1 재발
   방지)**·**manually-transcribed regression anchor**(§9/§16/§17 참조집합·seam 6-scalar 정합 — enum-drift
   정직화·§0.4h)·금지 동사 canary(§4).

### 0.2 하지 않는 것 (경계·NO 목록)

- **형제 소유 로직 재저작 금지(duplication 경계·본 문서 특유 최대 위험).** egress QCC/TrialClaims `is_complete()`
  boundary seal·cur `RESTRICTED_LIVE_TRIAL` 차원·hag `effective_principal_collapse`/`quorum_independence_
  satisfied`·evidence `SegmentCommitmentScheme`/`causal_chain_complete`/gap machine·rcl `CapacityVector`/
  worst-credible-effect/`within_limits`·liveauth Live Authorization·spg `bundle_complete`/policy activation·
  authority epoch/HALT/revocation을 **재판정하지 않는다** — 각 owner verdict/generation/digest를 **주입
  좌표**로만 소비(§3.5 SoD).
- **trial 실행·per-action enforcement runtime 재구현 금지(over-realization 경계).** §13 per-action final-egress
  binding(exact plan/remaining-envelope/authorization/currentness 검증)·§14 Trial Run 상태 전이 serialization·
  §15 abort/HALT/demotion race·§10 worst-credible-effect 계산·§12 trial Live Authorization 발급은 **전부 런타임/
  egress-owned/+Security/+Broker**. L1은 **주입된 좌표 위의 순수 completeness/subset/separation** 술어만.
- **egress `QuorumCommitCertificate`/`TrialClaims.is_complete()` boundary seal 재저작 금지(§0.4c).** egress(#22)가
  `is_restricted_live_trial` + `trial_claims` slot과 `_trial_claim_completeness` malformed-model validator를
  **소유**한다. RLP의 `trial_claims_complete`(내용 소유자 authoritative 완전성)는 egress의 thin all-present
  seal과 **다른(더 두꺼운) 축**이며, 정합은 **design-time 6-scalar 계약**(§11.1 line 308 / §9:258)을
  manually-transcribed anchor로 회귀 확인할 뿐 **import 아님**.
- **cur `RESTRICTED_LIVE_TRIAL` conditional 차원 재저작 금지(§0.4c).** cur(#23)가 currentness-vector의 조건부
  차원 식별자·`CONDITIONAL_DIMENSION_KEYS`를 소유. RLP는 그 차원의 *generation 내용*(무엇이 흘러가는지)을
  소유하되 cur의 vector-completeness 판정을 재저작하지 않는다.
- **evidence `SegmentCommitmentScheme`/gap/causal-chain 재저작 금지(§0.4d).** trial evidence *조립 + custody
  무결성*은 evidence(ADR-002-016)-owned. RLP는 trial-package *완전성 계약*(§16 element-class manifest +
  negative-retention as promotion gate)을 소유하되 `causal_chain_complete`/gap-first-class-failure를 **주입
  verdict**로 소비.
- **hag effective-principal/quorum 재저작 금지(§0.4e).** promotion independent review·effective-principal
  separation(RLP-INV-014·§22)은 hag(ADR-002-015)-owned. RLP는 hag verdict를 주입 소비. Governed
  Single-Operator Re-Arm Variant도 hag/liveauth 소유.
- **수치 하드코딩 금지(§8)** — `B_trial_abort_to_authority_revoke`·`B_trial_abort_to_egress_deny`·
  `B_trial_evidence_gap_to_containment`·`B_scope_promotion_generation_fence`·`MAX_trial_authorized_economic_
  effect`·`MAX_trial_concurrent_potential_effect`·`MAX_trial_action_count`·`MAX_trial_duration_ms`·
  `MAX_trial_evidence_age_ms`·`restricted_live_trial_policy_{id,generation,digest}` 전부 Profile INSTANCE
  측정/승인·주입(현재 전부 `null`/`TBD`·§8 실측).
- **미착지 상류 코드 인용 금지** — WDR(-026)·SIR(-027)·STM(-028)·SCI(-029)·PTF(-030) 미착지(`tos/src/tos/`
  하 부재 실측). §12의 release(-029, line 339 — v1.1 MINOR-2 정정: §0.4f와 정합)·§15의 incident(-027)·§19의 monitoring(-028) generation 차원은 **ADR
  원문만·generation 주입·코드 인용 0**(phantom 봉합·§0.4f).
- **EV/acceptance/비준 선언 금지.** tos-spec 수정 금지·기존 docs/plans 무수정. 미비준 문서 인용 없음.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.rlp`는 **순수 모델·술어 패키지**다: `pydantic` + stdlib + `tos.canonical`(digest substrate) +
`tos.ordering`(generation 순서)만 import. `shared.*`·`services.*`·`cli.*`·`numpy`/`pandas`/`yaml`·
`os.environ`·동적 escape(`exec`/`eval`/`importlib`/`__import__`) **전면 부재**. **형제 tos 패키지(egress·cur·
rcl·ioc·evidence·capsule·venue·iap·are·afg·sbr·hag·liveauth·protective·recon·brokercap·authority·orthostate·
spg·dsl·time·replacement·nontrade + 미래 wdr/sir/stm/sci/ptf) 전부 import 부재** — 형제 상호작용은 **주입
scalar/digest/bool/verdict/enum-token**으로만(sibling edge 0·§3.4). clock·network·egress·persistence 미접근.
`tos/tests/rlp/test_rlp_import_closure.py`가 import-closure를 allowlist(`closure ⊆ {canonical, ordering, rlp}`)로
강제하고 `tools/tos_firewall_check.py`(§3.2 ratified allowlist·default-deny) required check와 함께 green이어야
본 선언이 능동 성립(§7.1). **`tos.rlp`를 §3.2 allowlist에 추가하는 것은 본 설계 문서 §3.2를 편집하는 PR을
요구**(firewall check line 422 "Changing the allowlist requires a PR editing that doc").

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 명명 = `tos.rlp` (register-prefix 1:1·seam 토큰이 이미 이름을 고정).**

- **선택(권장) `tos.rlp`** — 근거 3중:
  1. **register prefix 1:1**: 시리즈가 `RLP-INV`/`RLP-AC`/`RLP-EV`를 사용(register 실측 md line 324-335·
     ADR §6/§26). terse-lowercase 관행(rcl·spg·iap·hag·are·ioc·afg·sbr·cur·egress — 전부 register prefix
     lowercase)과 정합.
  2. **seam 토큰이 이름을 이미 고정(soft load-bearing)**: egress `state.py:196`·cur `state.py:140`이
     RLP-이연 주석에서 **`tos.rlp`를 문자 그대로 명시**. 다른 이름 선택 시 두 착지 형제의 참조가 orphan.
     이는 cur(#23 §0.4a)가 naming을 non-load-bearing으로 둔 것과 **대비되는 본 문서 특유 조건**.
  3. **충돌 없음**: `rlp`는 미점유(현 28패키지 실측). **주의**: `rlp`(Restricted-Live Promotion) ≠ `rcl`
     (Risk Capacity Ledger) — 인접 3자 토큰이나 register prefix가 다르며 seam이 명확(§10.2 disambiguation).
- **runner-up `tos.restrictedlive`/`tos.trial`/`tos.promotion`(기각)** — full-word 관행(liveauth·brokercap·
  orthostate·protective·replacement·nontrade)도 존재하나 register-prefix 1:1(egress/hag/sbr/cur 최근 선례)이
  더 강하고, 무엇보다 seam 토큰이 `tos.rlp`를 이미 못박았다. **§10.1 운영자 판단 지점**: `tos.rlp` 채택.

**(b) RLP = trial-content 소유자·egress/cur = per-boundary consumer (본 문서 최대 판정·재저작 금지 경계).**
이것이 본 계약의 **핵심 아키텍처 결정**이며, **형제 코드가 스스로 RLP로 이연했음을 이름까지 명시해 증언**한다.

- **결정적 코드 증언 4중(실측 verbatim)**:
  1. egress `state.py:193-197`: "§11.1 line 308: a restricted-live trial (**ADR-002-025 RLP**) request
     requires the Trial Policy / Plan / Run / Promotion Generation, the remaining envelope, and the abort
     generation as **conditional** required claims. Phase 1 carries these as an **opaque optional scalar
     group**; the actual trial-content validation is **deferred to RLP** (`tos.rlp`, not landed ...), so
     egress cites no RLP code."
  2. cur `state.py:137-141`: "§9:258: a restricted-live trial (**ADR-002-025 RLP**) vector / proof carries
     the Trial Policy / Plan / Run / Promotion Generation ... Phase 1 carries these as an **opaque optional
     scalar group**; the actual trial-content validation is **deferred to RLP** ... so cur cites **no** RLP
     code (phantom seal)."
  3. egress `records.py:200-204`: "Positive restricted-live-trial completeness claim (§11.1 line 308).
     `True` requires a fully concrete `trial_claims` group — the malformed-model coexistence seal ... The
     conditional restricted-live trial claim group (opaque scalars; **RLP-deferred**, §2.4)."
  4. cur `vocabulary.py:131-132`: "`RESTRICTED_LIVE_TRIAL` is the **conditional** dimension (§9:258;
     **RLP-deferred content** — design #23 §0.4f) and is the **only** member outside the
     `MANDATED_DIMENSION_FLOOR`."
- **실측 사실(형제가 하류 consumer로 opaque scalar 이미 소유)** — 두 형제의 `TrialClaims`는 **동일 6-scalar**:
  - egress `TrialClaims`(`state.py:190-227`): `trial_policy_generation`·`trial_plan_generation`·
    `trial_run_generation`·`promotion_generation`·`remaining_envelope: str|None`·`abort_generation: int|None`
    + `REQUIRED_SCALARS`(6개)·`is_complete()` = `all(getattr(self,n) is not None ...)` — **thin all-present
    구조 seal**. QCC validator `_trial_claim_completeness`(`records.py:210-227`)가 `is_restricted_live_trial
    is True` + incomplete 그룹 공존을 `ArtifactIntegrityError`로 봉인.
  - cur `TrialClaims`(`state.py:134-150`): **동일 6-scalar**·`is_complete()` 없음(all-optional value model —
    non-trial vector는 `None`).
- **⇒ RLP가 소유하는 잔여(형제가 이연한 것)** = **trial-content 계약**:
  1. **§9 Exact Trial Plan 완전성**(RLP-EV-001·노른자 1) — `ExactTrialPlan`이 §9 전 scope 차원 + baseline
     digest를 **exact·pre-registered·concrete**로 bind. 6-scalar generation은 이 plan/policy/run/promotion
     아티팩트가 **생산**하는 좌표(하류로 egress/cur에 흘러감). `trial_claims_complete`는 egress의 thin
     all-present seal보다 **두꺼운 내용 완전성**(§0.4c·§5.1).
  2. **§16 Evidence Package 완전성**(RLP-EV-005·노른자 2) — negative/failed/inconclusive/aborted/conflicting
     결과 retention이 promotion gate. evidence의 `causal_chain_complete`/gap-first-class는 주입 소비.
  3. **§17 Coverage 비외삽**(RLP-EV-006·노른자 3) — claimed scope ⊆ observed(exercised) scope 순수 부분집합.
  4. **§26 AC-012 Gate 분리**(RLP-EV-012·노른자 4) — 9개 gate 상태가 distinct explicit·상호 비함의.
- **재저작 금지 경계(엄격)**: RLP는 egress QCC/TrialClaims seal·cur 차원을 **재저작·import하지 않는다**.
  6-scalar 정합은 **design-time 계약**(§11.1 line 308 / §9:258 = manually-transcribed anchor·§0.4h)일 뿐
  RLP가 egress/cur를 검증하지 않는다(계층 병렬·순환 방지). **리뷰어 공격 지점(§10.2-①)**: "RLP가 egress
  seal 중복" — 반론: egress seal = *egress boundary* all-present 구조 검사(is_restricted_live_trial 공존),
  RLP = *content* exact-completeness(plan이 §9 전 scope bind). 축이 다르고 egress가 명시 이연·RLP는 상류
  생산자.

**(c) egress = QCC/TrialClaims boundary seal 소유; cur = RESTRICTED_LIVE_TRIAL 차원 소유; RLP = 그 내용 소유
(재저작 금지).**

- **판정: seam은 *generation scalar*로만 교차**. RLP 아티팩트(`TrialPolicy`/`ExactTrialPlan`/`TrialRun`/
  `ProductionScopePromotionDecision`)는 `tos.ordering` generation을 발급하고, 그 정수/digest가 egress/cur의
  `TrialClaims` 6-scalar로 **하류 주입**된다. **방향**: RLP(상류 생산) → egress/cur(하류 소비). RLP는
  egress/cur를 import·검증하지 않는다(§3.4).
- **egress의 thin seal 존치**: egress `is_complete()`(all-present) + `_trial_claim_completeness`(coexistence)는
  egress boundary의 malformed-model 자기방어로 **그대로 유지**. RLP의 `trial_claims_complete`는 그와 **정합
  하되 더 두껍다**(plan이 exact scope bind·pre-registered·result ELIGIBLE). 정합은 6-scalar 필드-집합 계약을
  manually-transcribed anchor로 회귀 확인(§7.2). **리뷰어 공격 지점(§10.2-②)**: "RLP가 cur 차원 재저작" —
  반론: cur는 vector-completeness 축(어떤 차원이 present한지), RLP는 그 차원의 *내용*(generation이 무엇을
  가리키는지)·edge 0.

**(d) evidence = SegmentCommitmentScheme/gap/causal-chain 소유; RLP = trial-package 완전성 계약 소유 (§16
경계·재저작 금지).**
**실측 인접**: evidence(착지)가 `SegmentCommitmentScheme`(Protocol·`ledger.py:82`)·`EvidenceGapRecord`/
`GapStatus`(`gap.py`)·`causal_chain_complete`(`predicates.py:130`)·`gap_blocks_new_risk`를 소유. ERI-INV-004:
gap/denial/failure는 first-class 증거(`gap.py:7`). §16(Trial Evidence Package)이 "gap-checked, causally
complete package"라 **재저작 함정**이다.

- **판정: 조립 + custody 무결성은 evidence(ADR-002-016)-owned, trial-package *완전성 계약*은 RLP-owned**.
  §7 table verbatim: "Assemble evidence package | **Evidence and Replay Service** from source-owner records |
  **ADR-002-016 integrity rules** | package cannot select away failures or create permission." ⇒ 조립/무결성/
  custody는 evidence. RLP 소유 = §16 element-class manifest 완전성 + **negative-result retention을 promotion
  gate로**(§16 "Post-hoc metric changes, optional stopping, discarded runs ... invalidate the promotion
  claim") + selection-fixed-before-start.
- **경계 분할**: **evidence 소유** = SegmentCommitmentScheme(custody)·gap machine·causal_chain_complete·
  gap-first-class-failure. **RLP 소유** = `TrialEvidencePackage`(§16 전 element-class 존재 + negative retention
  + no-selective-reporting·result 완전성). RLP는 `causal_chain_complete`·gap-status를 **주입 verdict**로 소비.
  **리뷰어 공격 지점(§10.2-③)**: "evidence_package_complete = causal_chain_complete 중복" — 반론:
  causal_chain_complete = *인과 체인* 무결성(evidence·주입), evidence_package_complete = *§16 element-class
  manifest 완전성 + negative-retention* (RLP·다른 축)·집계 고유. evidence가 negative를 first-class로 보존
  (ERI-INV-004)하는 것과, RLP가 negative 부재를 promotion-incomplete로 판정하는 것은 별개 gate.

**(e) hag = effective-principal collapse + quorum 소유; RLP = 주입 verdict 소비 (§18/§22 independence 경계·
재저작 금지).**
**실측 인접**: hag(착지·`__init__.py:6-7`)가 "human-authority general model — the effective-principal control
graph"를 저작. `effective_principal_collapse`(yolk·same-person collapse)·`quorum_independence_satisfied`·
`quorum_for(approval_type) -> int|None`(`records.py:109`)·`EffectivePrincipalGraph`/`QuorumRule` 소유.
RLP-INV-014(Independent Acceptance)·§18 promotion quorum·§22 role separation이 **hag 재저작 함정**.

- **판정: 인간 authority 일반 모델은 hag(ADR-002-015)-owned**. RLP-INV-014 verbatim: "Trial implementers,
  strategy owners, evidence producers, and performance beneficiaries cannot be the sole reviewers or
  production authorizers of their trial." ⇒ effective-principal collapse 판정 = hag. RLP는 hag verdict
  (`effective_principal_collapse` 결과·quorum satisfied)를 **주입 소비**. Governed Single-Operator Re-Arm
  Variant(ADR-002-015 §17.1)도 hag/liveauth 소유·RLP 주입.
- **⇒ RLP는 `effective_principal_collapse`·`quorum_independence_satisfied`를 재저작·import하지 않는다.** RLP는
  `all_false_trial_authority` + SoD 구조 선언(trial 컴포넌트는 RCL/egress authority 무보유)만 L1으로 저작하고,
  실 independence는 hag verdict + +Security(RLP-EV-008 `EV-L2/3+Security`). **리뷰어 공격 지점(§10.2-④)**:
  "RLP가 quorum 재저작" — 반론: quorum/collapse = hag, RLP = 주입 소비·RLP-EV-008 L2+·edge 0.

**(f) 미착지 상류 026/027/028/029/030 차원 (phantom 봉합).** **실측**: `tos/src/tos/` 하 wdr·sir·stm·sci·ptf
**부재**(ls 확인). §12가 release(-029)·§15가 incident(-027)·§19가 monitoring(-028) generation을 요구.

- **판정: RLP는 이들을 주입 generation/digest 좌표로만 소비.** ADR 원문(§12 line 339·§15 line 406·§19 line
  476-484·§6 RLP-INV-015 line 208)만 참조하고 **코드 인용 0**(미착지 — phantom 금지). Software Release
  (-029)·Incident(-027)·Monitoring(-028) generation은 opaque 주입 scalar로 수용하고 내용 검증은 각 미착지
  ADR 이연. **리뷰어 공격 지점(§10.2-⑤)**: "미착지 차원 substrate 오인용" — 반론: ADR 원문만·코드 0·주입
  좌표·§0.2 NO-list.

**(g) rcl·liveauth·spg·iap·authority·time·are·dsl 경계 (전부 verdict 주입 소비·§3.5 표).**

- **rcl(ADR-002-002/012)**: `CapacityVector`(`vector.py:74`)·`within_limits`(effect vs limits·
  `predicates.py:78`·∅-seal 선례)·worst-credible-effect·commit-proof 좌표 소유. §7 table verbatim: "Mutate capacity |
  **none** | **RCL only** | plan, budget, evidence, and promotion cannot reserve or release." ⇒ RLP Trial
  Budget은 capacity 아님(RLP-INV-003·§10)·주입 CapacityVector 좌표 소비. worst-credible-effect *계산*은 rcl +
  +Broker(§28 open Q #3·RLP-EV-002 `EV-L2/3+Broker`).
- **liveauth(ADR-002-007)**: trial Live Authorization(§12)·promoted-scope re-arm 소유. RLP는 authorization
  generation을 주입 소비·발급 안 함(RLP-INV-001).
- **spg(ADR-002-014)**: `bundle_complete`/`missing_config_denies`(`predicates.py:818/857`·완전성 선례). Trial
  Policy 활성화는 spg/014-governed(§8 line 253 "Policy activation follows ADR-002-014"). RLP는 policy
  **content model**을 저작하고 **활성화/generation은 spg verdict 주입 소비**(cur §0.4g 동형).
- **iap(ADR-002-023)**: `single_use`/`exact_intent_only`(`predicates.py:176`)·"eligibility to be consumed
  once"(`predicates.py:230`)·consume gate `result is ApprovalResult.APPROVE`. **single-use consumption
  *shape* 선례** — RLP `promotion_progressive_single_use`가 이 shape을 로컬 재표현(import 아님·§0.4 iap
  동형). Promotion(§18)은 iap approval consumption과 **단조·단일-사용 동형**.
- **authority(ADR-002-003)**: `authority_epoch_current`(`>=` floor)·`recovery_generation_revives_nothing`
  (`predicates.py:787`) — floor `>=` shape + non-revival 선례(RLP `recovery_revives_nothing`이 REUSE via
  `tos.ordering`·재저작 아님).
- **time(ADR-002-008)**: `freshness_verdict` — trial timing/age(§9/§12/§21)의 Trustworthy Time generation은
  RLP 주입 좌표. `MAX_trial_*_ms` wall-clock age는 secondary +Security/INSTANCE.
- **are(ADR-002-021)**: correlated concurrent trial/non-trial activity(§10)의 aggregate-risk는 are + Phase-0
  (correlation/solver는 §4 non-scope). RLP 주입.
- **dsl(ADR-002-DEV-001)**: §8 trial policy가 겨냥하는 strategy 대상은 dsl StrategySpec 식별자·RLP 주입 scope 좌표.

**(h) 앵커 규약 + manually-transcribed regression anchor.** **실측**: ADR-002-025는 자체 시리즈 **`RLP-INV-001..015`
(§6 line 148-206, 15종)·`RLP-AC-001..012`(§26 line 634-680, 12종)·`RLP-EV-001..012`(register md line 324-335,
12행)**를 정의한다. §26 preamble(line 632 verbatim): "The following cases are mandatory and **map one-to-one
to `RLP-EV-001` through `RLP-EV-012`**. Written cases are not completed evidence." 본 계약은 모델 불변식·술어를
**`RLP-INV-###`/`RLP-AC-###`/`RLP-EV-###`/§-clause/`SAFE-###`**에 앵커하고 **새 시리즈를 창작하지 않는다**.
**참조집합 정직화(§0.4h)**: §9 mandated scope 차원·§16 element-class·seam 6-scalar 같은 참조집합은 ADR 조항을
손으로 옮긴 **"manually-transcribed regression anchor"**로 명시 표기하며(파생이 아님·자동 유도 아님), 회귀
property가 모델 집합 == anchor를 강제해 drift를 즉시 발각한다(cur v1.1 §7.2 enum-drift 선례). naive grep 파싱
금지(survey 교훈).

---

## 1. 범위 매핑 — ADR-002-025 조항별 EV-L1 도달성 (닫는 RLP-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **+Security = 독립 security-boundary assessment**, **+Broker = broker-capability
실측**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — RLP-EV core 4행(거버넌스 6부작 중 L1 최상)**: register 실측 histogram(md line 324-335):
> **core(L1-floor) 4행 = {001 Exact Pre-Registered Scope·005 Evidence Completeness and Negative-Result
> Retention·006 Coverage and Non-Extrapolation·012 Gate Honesty and Status Separation — 전부 `EV-L1/3`,
> 좌표 태그 없음}**. **predicate-only(≥ L2) 7행 = {002 Worst-Credible Effect·003 No Trial Safety Bypass
> [`EV-L2/3+Broker`]·007 Progressive Single-Use Promotion·008 Independent Governance·010 Restart/Recovery
> [`EV-L2/3+Security`]·009 Expiry/Economic·011 Continuous Conformance [`EV-L2/3+Broker`]}**. **not-Phase-1
> (L3+) 1행 = {004 Abort Dominance and Race [`EV-L3+Security`]}**. **닫는 RLP-EV = 0건**. `EV-L1/3`(4행)은
> *staged* L1 **및** L3을 모두 요구하므로 Phase-1 L1 모델·property test는 이들을 **닫지 못한다**.
>
> **결정적 사실 2 — authoring ≠ acceptance (닫는 RLP-EV = 0건)**: (a) core 4행조차 `/3`(integration/
> adversarial) 잔여, (b) predicate-only 7행은 최소 ≥ L2(+Broker/+Security), (c) not-Phase-1 1행은 L3+ 런타임
> race, (d) VER-002-001 §5 "Registration is not execution"·ADR §26 line 632 "Written cases are not completed
> evidence"·§29 line 747 "Authorship ... does not satisfy these gates. This ADR authorizes architecture and
> implementation planning only." ⇒ **"EV-L1-complete 주장 금지"**(#12–#23 §1 규율 상속). Owner/Reviewer는
> register상 TBD·status NOT_IMPLEMENTED(전 12행).
>
> **결정적 사실 3 — survey "not-Phase-1" 라벨의 정직한 세분(§10.1 판단 지점)**: survey(line 216-227)는
> non-core 8행을 전부 "not-Phase-1"로 뭉뚱그렸다. 본 계약은 cur/afg 하우스 관행(predicate-only ≥ L2 vs
> not-Phase-1 L3+/런타임)에 따라 이를 **세분**한다: 002·003·007·008·009·010·011은 **L1-decidable 얇은
> substrate가 존재**(closing EV는 L2)하므로 **predicate-only**, 004만 순수 race/timing이라 **not-Phase-1**.
> 이는 register EV-level(004만 유일 `EV-L3+`)과 정확히 정합하는 증거기반 세분이다.

**규율 태그(모든 주장에 부착)**: "**structural/completeness/subset/separation predicate substrate only;
RLP-EV-001..012 전부 NOT_IMPLEMENTED — core 4행(001·005·006·012)은 `/3` 통합·adversarial 대기, predicate-only
7행은 component-fault L2·+Security/+Broker 대기, not-Phase-1 1행(004)은 런타임 abort race(+Security).
EV-L1-complete 주장 금지·trial 실행·per-action egress binding·worst-credible-effect 계산·independent review·
promotion approval·evidence 조립 무결성은 재저작/런타임/인간/+Security. L1은 plan/package/coverage/gate 구조
판정만.**"

**RLP-EV core 4행 ↔ AC(1:1) ↔ ADR 조항 매핑(실측)**:

| RLP-EV | register 제목(verbatim, md line) | 최소 레벨 | RLP-AC(1:1) | ADR 조항 앵커 | L1 substrate 술어(§5) |
|---|---|---|---|---|---|
| **001** | Exact Pre-Registered Scope (324) | `EV-L1/3` | AC-001(§26) | §9 Exact Trial Plan Contract·RLP-INV-002 | `plan_scope_exact_and_complete`(노른자 1) + `no_wildcard_scope`·`baseline_digests_bound`·`plan_result_admissible`·`trial_claims_complete`(§5.1) |
| **005** | Evidence Completeness and Negative-Result Retention (328) | `EV-L1/3` | AC-005(§26) | §16 Evidence Collection·RLP-INV-009 | `evidence_package_complete`(노른자 2) + `negative_results_retained`·`selection_fixed_before_start`·`no_selective_reporting`(§5.2) |
| **006** | Coverage and Non-Extrapolation (329) | `EV-L1/3` | AC-006(§26) | §17 Coverage·RLP-INV-008 | `coverage_supports_claim`(노른자 3) + `no_union_coverage`·`equivalence_positively_proven`·`unexercised_is_uncovered`(§5.3) |
| **012** | Gate Honesty and Status Separation (335) | `EV-L1/3` | AC-012(§26) | §26 AC-012·§29·RLP-INV-007 | `gate_status_separated`(노른자 4) + `no_status_implication`·`readiness_not_authority`(§5.4) |

**ADR-002-025 조항 → Phase-1 분류(core / predicate-only / not-Phase-1)**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | RLP-EV |
|---|---|---|---|---|
| **§9** (line 259-278) | Exact Trial Plan Contract·pre-registered exact scope·baseline digest·no patch/union | **core (L1 슬라이스)** | `plan_scope_exact_and_complete`(§5.1) — §9 전 scope 차원 + baseline present·concrete·no-wildcard·result ELIGIBLE. 6-scalar generation은 RLP 생산·egress/cur 하류(§0.4b). | **001** |
| **§16** (line 414-428) | Evidence package 완전성·negative retention·no optional stopping | **core (L1 슬라이스)** | `evidence_package_complete`(§5.2) — §16 전 element-class present + negative/inconclusive/aborted 보존 + selection-fixed. custody/무결성은 evidence-owned 주입(§0.4d). | **005** |
| **§17** (line 434-446) | Coverage 매핑·비외삽·no-union·unknown equivalence = non-equivalence | **core (L1 슬라이스)** | `coverage_supports_claim`(§5.3) — claimed ⊆ observed(exercised) 순수 부분집합·no-union·equivalence positively proven. | **006** |
| **§26 AC-012 / §29** (line 678-680 / 747) | Gate honesty·9개 상태 distinct explicit | **core (L1 슬라이스)** | `gate_status_separated`(§5.4) — plan-eligible ↛ live-authorized·promotion-eligible ↛ production-ready·readiness ≠ authority. all-false 확장. | **012** |
| **§10** (line 283-298) | Maximum credible trial effect·budget ≠ capacity | **predicate-only (+Broker)** | `trial_budget_is_not_capacity`(§6.1·all-false — budget는 capacity 불변·§7 "RCL only"). worst-credible-effect *계산*은 rcl + +Broker. | **002** |
| **§13** (line 343-357) | Per-action trial enforcement·no safety waiver | **predicate-only (+Broker)** | `trial_status_waives_no_gate`(§6.2·all-false — trial flag/low-notional/canary/supervision는 bypass authority 무보유·RLP-INV-004). 실 per-send binding은 egress 런타임. | **003** |
| **§18** (line 452-468) | Progressive scope promotion·single-use·no-union·break-before-make | **predicate-only (+Security)** | `promotion_progressive_single_use`(§6.3·iap consumption shape REUSE — single_use is not True ⇒ deny·no-union·no-widening·result ELIGIBLE_TO_REQUEST_NEW_SCOPE). 실 registry replay는 +Security. | **007** |
| **§7 SoD·§22** (line 214-231 / 521-536) | Independent governance·authority separation·no role collapse | **predicate-only (+Security)** | `all_false_trial_authority`(§6.4) + SoD 구조 선언. effective-principal collapse는 hag-owned 주입(§0.4e). | **008** |
| **§20** (line 490-499) | Expiry·invalidation·economic continuity | **predicate-only (+Broker)** | `expiry_denies_future_use_only`(§6.5·음극성 — expiry ⇒ future deny·capacity/economic 불변·RLP-INV-012) + `economic_effect_persists`(afg/are/capsule shape). | **009** |
| **§21** (line 505-515) | Restart/failover/recovery·non-revival | **predicate-only (+Security)** | `recovery_revives_nothing`(§6.6·authority/cur 선례 — restart ⇒ INVALIDATED·no resume/re-arm·RLP-INV-013). 실 hard-fence는 +Security. | **010** |
| **§19** (line 472-484) | Continuous conformance·EV-L6 monitoring·demotion | **predicate-only (+Broker)** | `monitoring_not_preventive`(§6.7·RLP-INV-015 — CONFORMING은 non-authorizing) + `demotion_not_rearm`. monitoring gen은 -028 미착지 주입(§0.4f). | **011** |
| **§15** (line 383-408) | Abort/HALT/demotion·abort dominates·race | **not-Phase-1 (런타임 race)** | 얇은 순서 permutation model(§6b·ABORT<ACTION ⇒ deny·ambiguous ⇒ potentially-live + capacity-covered). 실 abort latency·`B_trial_abort_*`·deny-first는 +Security 런타임. | **004** |
| **§8·§11·§12·§14·§28·§29** | Trial Policy·pre-trial gate·authorization·run serialization·수치·acceptance | **not-Phase-1 (Phase-0/INSTANCE·런타임)** | policy content model(§8 activation=spg 주입)·pre-trial gate(§11 런타임)·Live Auth(§12 liveauth)·run serialization(§14 런타임). 수치·acceptance는 §9.2 Phase-0. | (전 행 분산) |

---

## 2. 데이터 모델 계약

### 2.1 digest-bound / value / reference 분류

| 분류 | 모델 | 근거 |
|---|---|---|
| **digest-bound `IndependentIdArtifact`** (id ⊥ digest) | `TrialPolicy`(§5.1/§8 governed policy)·`ExactTrialPlan`(§5.2/§9 immutable pre-registered)·`TrialRun`(§5.5/§14 run 인스턴스)·`TrialEvidencePackage`(§5.7/§16 immutable gap-checked)·`ProductionScopePromotionDecision`(§5.9/§18 single-use) | append-only ledger citizen(§16 line 428 "Evidence Commit Receipt proves custody"·§9 line 261 "canonical digest and predecessor"·§18 line 462 "single-use consumption identity"). id 서비스 부여(≠ `f(digest)`). same-id/different-bytes 위조/replay를 `classify_record_pair` CRITICAL_CONFLICT로 탐지(§3.1). |
| **value (frozen, id 없음)** | `TrialScope`(§5.3 exact scope tuple)·`TrialBudget`(§5.4 request envelope·NOT capacity)·`CoverageClaim`(§5.8 claimed/observed scope)·`GateStatusLadder`(§26 AC-012 distinct 상태)·`TrialClaimGroup`(seam 6-scalar mirror — 검증 대상·egress/cur 재저작 아님) | id 미도출·mutate 없음. `TrialClaimGroup`은 egress/cur가 하류로 나르는 6-scalar와 **필드-집합 정합**(manually-transcribed anchor·§0.4h)하는 RLP-owned content view. |
| **enum-token (`_NonTruthyStrEnum`)** | `PlanResult`{INELIGIBLE/HOLD/ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION}·`PromotionResult`{DENY/HOLD/ELIGIBLE_TO_REQUEST_NEW_SCOPE}·`TrialRunState`{7-state}·`CoverageVerdict`{COVERED/UNCOVERED/UNKNOWN} | 어휘(§2.2). `__bool__ ⇒ TypeError`(truthy 봉인·비-pass 멤버가 non-empty string). |
| **reference (scalar/digest only, 주입)** | egress/cur TrialClaims가 나르는 하류 generation(RLP 생산이나 소비 검증은 egress/cur)·rcl CapacityVector + commit-proof 좌표(effect envelope)·hag effective-principal collapse verdict + quorum satisfied·evidence causal_chain_complete + gap-status·spg policy activation generation·liveauth Live Authorization generation·authority epoch/HALT/revocation gen·time Trustworthy Time gen·are aggregate-risk gen·dsl strategy 식별자·**026/027/028/029/030 governance generation(미착지·주입)** | 형제/미착지 소유 — 주입 scalar/digest/verdict로만 참조(§3.4/§3.5). RLP는 이들을 저작·import하지 않음. **-026~-030은 미착지 — ADR 원문만·코드 인용 0(phantom 봉합·§0.4f).** |

### 2.2 어휘 (verbatim 전사 + truthy 봉인)

**(1) `PlanResult` (§9 line 275, non-truthy StrEnum — 핵심 truthy 봉인).** `INELIGIBLE`·`HOLD`·
`ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`. **`_NonTruthyStrEnum` 로컬 재표현**(iap `vocabulary.py` `ApprovalResult`
동형·**import 아님**·`__bool__ ⇒ TypeError`). **근거**: §9 line 275 verbatim: "The plan result is
`INELIGIBLE`, `HOLD`, or `ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`. The last result is **non-authorizing**."
`INELIGIBLE`/`HOLD`는 non-empty string이라 `if result:`가 **거부를 truthy로 오독하는 치명적 fail-open**. 소비
게이트는 **`result is PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION` 명시 비교 강제**(§4.2·§7 회귀).
ELIGIBLE 자체도 authority 아님(§9 line 275 "non-authorizing"·all-false·§6.4).

**(2) `PromotionResult` (§5.9/§18, non-truthy StrEnum).** `DENY`·`HOLD`·`ELIGIBLE_TO_REQUEST_NEW_SCOPE`.
**`_NonTruthyStrEnum`**. **근거**: §5.9 verbatim: "A single-use, **non-authorizing** independent decision of
`DENY`, `HOLD`, or `ELIGIBLE_TO_REQUEST_NEW_SCOPE`." §18 line 464: "Only `ELIGIBLE_TO_REQUEST_NEW_SCOPE` may
be consumed, once." `DENY`/`HOLD`는 non-empty string ⇒ `if result:` 오용이 fail-open. 소비:
`result is PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE` 명시 + single-use.

**(3) `TrialRunState` (§14, non-truthy StrEnum — 7-state).** `NOT_STARTED`·`AUTHORIZED_NOT_STARTED`·`RUNNING`·
`ABORTING`·`TERMINATED`·`COMPLETED_PENDING_REVIEW`·`INVALIDATED`. **`_NonTruthyStrEnum`**(비-permissive 상태가
non-empty string이라 `if state:`가 terminal/aborting을 truthy "go"로 오독하는 fail-open). **근거**: §14 line
374 "`RUNNING` requires current Live Authorization and **does not itself grant transmission permission**"·line
378 "`ABORTING`, `TERMINATED`, `COMPLETED_PENDING_REVIEW`, and `INVALIDATED` are **non-permissive**. No
terminal state returns to `RUNNING`." 상태는 all-false authority(어떤 상태도 transmission 무부여·§6.4).

**(4) `CoverageVerdict` (§17, non-truthy StrEnum).** `COVERED`·`UNCOVERED`·`UNKNOWN`. **근거**: §5.8 "Unexercised
or ambiguously observed behavior is **uncovered**"·§17 line 444 "**Unknown equivalence is non-equivalence**."
`UNCOVERED`/`UNKNOWN` non-empty ⇒ truthy 오독 fail-open. 소비: `verdict is CoverageVerdict.COVERED` 명시.

### 2.3 아티팩트 covered + self-exclusion + malformed-model 자기방어 (설계 #4 §3.3·#20 §2.3·#22 §2.3·#23 §2.3 상속)

- 모든 digest-bound 아티팩트는 `IndependentIdArtifact`(canonical `_base.py`)를 상속 — `_ID_FIELD`(독립 id·
  digest preimage self-exclusion)·`_COVERED_FIELDS`(digest cover)·`_REQUIRED_COVERED`(구조 identity 최소
  필수)를 선언(spg·ioc·rcl·egress·cur 선례).
- **coordinate 비붕괴(설계 #4 §4.4)**: mutable lifecycle 좌표(promotion `single_use_consumed`·run state·주입
  verdict)는 covered digest에 **미포함** — 정당한 전이가 digest를 바꿔 same-id/different-bytes CRITICAL_CONFLICT로
  오탐되지 않도록. 현재 상태는 술어에 주입·별도 append-only record.
- **malformed-model 자기방어 — positive-claim + incomplete-group coexistence seal(egress QCC
  `_trial_claim_completeness` 동형·본 문서 핵심 seal)**: `ExactTrialPlan` `model_validator`가 **불완전 scope와
  "eligible" 주장의 공존을 구조로 봉인**. `result is PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`인데
  §9 mandated scope 차원 중 하나라도 `None`/wildcard이면 **`ArtifactIntegrityError` at construction** — 즉
  "eligible"을 주장하면서 exact scope가 비는 plan은 **애초에 구성 불가**(egress `records.py:222-227` "declares
  is_restricted_live_trial=True but carries an incomplete trial claim group" 동형·다른 아티팩트). 동일하게
  `TrialEvidencePackage`(promotion-complete 주장 + negative-class 부재 ⇒ unconstructable)·
  `ProductionScopePromotionDecision`(ELIGIBLE 주장 + coverage 부재 ⇒ unconstructable). `plan_scope_exact_and_
  complete`(§5.1)는 validator 통과 후에도 술어 층에서 재확인(defense-in-depth·`model_construct` 우회 대비·2층).
  **리뷰어 공격 지점(§10.2-⑥)**: `model_construct`로 malformed plan 구성 → validator + 술어 2층 봉인.
- **`_REQUIRED_COVERED`는 구조 identity/generation/digest만** — action count·budget·quorum N·age 같은 numeric
  bound은 제외(Phase-1 null profile 하에서 아티팩트 구성 가능하도록·§8); 누락 numeric claim은 fail-closed(§4.2).

### 2.4 핵심 모델 필드 골격 (§ref·형제 seam·all-false)

**`TrialPolicy`(§5.1/§8)** — governed policy content model. 필드: `policy_id`(독립 id)·`policy_generation`·
`policy_digest`·`eligible_trial_classes: frozenset[str]`·`prohibited_trial_classes: frozenset[str]`·
`scope_dimensions: frozenset[ScopeDimension]`(§9 mandated 차원 catalogue 선언)·`required_evidence_classes:
frozenset[EvidenceClass]`(§16)·`coverage_rules`·`abort_triggers`·`promotion_ladder`·`max_delta`·
`required_reviewers`·`compatibility_manifest_digest`·`authority_effect: AllFalseTrialAuthority`. **활성화/generation은
spg/014 주입**(§0.4g·§8 line 253). `_REQUIRED_COVERED` = {policy_id·policy_generation·policy_digest}.

**`ExactTrialPlan`(§5.2/§9)** — immutable pre-registered proposal. 필드(전부 주입·검증 대상):
- **identity**: `plan_id`(독립 id)·`plan_generation`·`plan_digest`·`predecessor_plan_id`·`policy_id`·
  `policy_generation`·`policy_digest`·`compatibility_manifest_digest`.
- **scope/baseline**(§9 line 263): `trial_scope: TrialScope`·`baseline_digests: tuple[str, ...]`(전 baseline
  artifact digest·concrete).
- **claims**(§9 line 264): `targeted_safety_claims: tuple[str, ...]`·`evidence_ids: tuple[str, ...]`.
- **pre-registered**(§9 line 265): `pre_registered_actions`·`order_shapes`·`failure_injections`·`observations`·
  `coverage_claims: tuple[CoverageClaim, ...]`.
- **budget**(§9 line 266): `trial_budget: TrialBudget`(NOT capacity·§10).
- **assumptions**(§9 line 267): `existing_exposure`·`external_activity_window`·`protective_obligation`·
  `abort_overlap`·`recovery_assumptions`.
- **prereq 좌표**(§9 line 268-269·전부 주입): `rcl_capacity_request`(rcl CapacityVector 좌표)·`action_flow_reserve`·
  `protective_capacity`·`start_window`·`expiry`·`trustworthy_time_requirements`·`consumer_receipt_anchors`.
- **principals**(§9 line 270): `required_principals`·`operators`·`independent_reviewers`·`observers`.
- **evidence plan**(§9 line 271): `evidence_sources`·`pre_effect_durability`·`package_schema`·`retention`.
- **abort/recovery**(§9 line 272): `abort_triggers`·`halt_scope`·`egress_latch_behavior`·`reconciliation`·
  `recovery_disposition`.
- **residual**(§9 line 273): `residual_risks`·`prohibited_inferences`.
- `result: PlanResult`(§9 line 275)·`pre_registered: bool | None`(양극성)·`independently_reviewed: bool | None`
  (양극성)·`authority_effect: AllFalseTrialAuthority`.
- `_REQUIRED_COVERED` = {plan_id·plan_generation·plan_digest·policy_id·policy_generation}. malformed-model
  validator: `result is ELIGIBLE` + incomplete scope/baseline ⇒ `ArtifactIntegrityError`(§2.3).

**`TrialScope`(value·§5.3)** — exact scope tuple(§5.3/§9 line 263 전 차원): `environment`·`safety_cell`·
`capacity_domain`·`portfolio`·`account`·`broker`·`venue`·`instrument`·`strategy`·`action_class`·`order_shape`·
`software_release`·`configuration`·`identity`·`credential`·`route`·`session`·`time_interval`·`failure_domain`.
각 `str | None`; `None`/wildcard ⇒ `no_wildcard_scope` 실패(§5.1). **`ScopeDimension` enum(closed StrEnum)**은
이 차원의 식별자군(manually-transcribed anchor·§9 line 263 = 참조집합·§7.2 drift property). **숫자 하드코딩
아님**(구조 dimension identifier·cur `DimensionKey` 선례).

**`TrialBudget`(value·§5.4·NOT capacity)**: `max_action_count: int | None`·`broker_resource_vector`·
`duration_ms: int | None`·`credible_economic_effect_envelope`(rcl CapacityVector 좌표·주입). §10 line 296
verbatim: "The plan's Trial Budget is an **upper request envelope**. **Only RCL may commit capacity**. Unused
plan budget creates **no headroom** and cannot be transferred." ⇒ TrialBudget은 검증 대상 request envelope이지
capacity 아님(`trial_budget_is_not_capacity`·§6.1). numeric은 전부 INSTANCE 주입(§8).

**`TrialRun`(§5.5/§14)** — run 인스턴스·상태기계. 필드: `run_id`(독립 id)·`run_generation`·`plan_id`·`plan_digest`
(§12 line 335 "binds one Trial Run identity, plan digest")·`baseline_digest`·`promotion_generation`·
`live_authorization_generation`(liveauth 주입·§12)·`max_action_effect_count_duration_envelope`·`start_window`·
`expiry`·`abort_generation`·`state: TrialRunState`·`is_aborted: bool | None`(음극성)·`is_invalidated: bool | None`
(음극성)·`authority_effect: AllFalseTrialAuthority`. §14 line 374 "RUNNING ... does not itself grant transmission."
`_REQUIRED_COVERED` = {run_id·run_generation·plan_id·plan_digest}.

**`TrialEvidencePackage`(§5.7/§16)** — immutable gap-checked package. **`promotion_complete_claim:
bool | None`(양극성 — v1.1 MINOR-3: §2.3 coexistence seal의 construction-time 키; validator =
`promotion_complete_claim is True` ∧ negative-class element 부재 ⇒ `ArtifactIntegrityError` —
Plan/Decision의 result-enum seal과 3-of-3 대칭; §5.2 술어층 negative-retention gate는 별개 2층).** 필드:
- **identity/binding**: `package_id`·`package_generation`·`package_digest`·`plan_id`·`plan_digest`·
  `policy_digest`·`baseline_digest`·`run_id`·`approvals`·`authorizations`(§16 line 416).
- **event classes**(§16 line 417·전 class present 요구): `proposed`·`denied`·`committed`·`transmitted`·
  `acknowledged`·`filled`·`cancelled`·`corrected`·`external`·`protective`·`abort`·`recovery` events.
- **capacity/flow**(§16 line 418): `rcl_transitions`·`action_flow_transitions`·`potentially_live_intervals`·
  `final_quantity_evidence`.
- **coverage/negative**(§16 line 419-422·노른자 2 핵심): `coverage_claims`·`unexercised_conditions`·`deviations`·
  `common_modes`·**`negative_results`**·`failed_results`·`inconclusive_results`·`aborted_results`·
  `conflicting_results`·`superseded_results`.
- **broker evidence**(§16 line 420): `raw_broker_evidence`·`normalized_broker_evidence`·`source_continuity`·`gaps`.
- **measured bounds**(§16 line 421): `detection`·`containment`·`abort`·`fence`·`evidence`·`reconciliation`·
  `recovery` bounds(INSTANCE 주입).
- **generations/review**(§16 line 423-424): `software_generation`·`configuration_generation`·`broker_profile`·
  `identities`·`reviewer_decisions`·`independent_reproduction`·`independent_review`.
- **integrity 좌표(evidence-owned 주입·§0.4d)**: `causal_chain_complete: bool | None`(evidence 주입)·
  `gap_status`(evidence 주입)·`commit_receipt_id`.
- **selection**: `selection_fixed_before_start: bool | None`(양극성·§16 line 426 "fixes evidence-selection
  and stop rules before start")·`optional_stopping: bool | None`(음극성)·`discarded_runs: bool | None`(음극성)·
  `selected_windows: bool | None`(음극성)·`removed_adverse: bool | None`(음극성).
- `authority_effect: AllFalseTrialAuthority`. `_REQUIRED_COVERED` = {package_id·package_generation·plan_id·
  plan_digest·run_id}. malformed-model validator: promotion-complete 주장 + negative-class 부재 ⇒ error(§2.3).

**`CoverageClaim`(value·§5.8/§17)**: `claimed_scope: frozenset[str]`·`observed_scope: frozenset[str]`(actually
exercised)·`exercised_conditions: frozenset[str]`(§17 line 440 nominal/boundary/missing/stale/duplicate/delayed/
crash/restart/partition/broker-rejection/partial-fill/UNKNOWN/conflict)·`unexercised_conditions: frozenset[str]`·
`equivalence_positively_proven: bool | None`(양극성·§17 line 444)·`verdict: CoverageVerdict`. §17 line 434-444.

**`ProductionScopePromotionDecision`(§5.9/§18)** — single-use non-authorizing. 필드: `decision_id`·
`decision_generation`·`promotion_generation`·`source_run_id`·`source_package_id`·`source_package_digest`·
`baseline_digest`·`current_scope`·`requested_delta`(§18 line 455)·`coverage_claims`·`uncovered_conditions`·
`residual_risks`·`max_effect`·`config_profile_changes_required`·`required_additional_evidence`·`expiry`·
`reviewer_quorum`(hag 주입)·`effective_principal_verdict: bool | None`(hag 주입)·`single_use_consumed: bool | None`
(음극성·§18 line 464 "consumed, once")·`result: PromotionResult`·`authority_effect: AllFalseTrialAuthority`.
`_REQUIRED_COVERED` = {decision_id·decision_generation·promotion_generation·source_run_id·source_package_id}.

**`GateStatusLadder`(value·§26 AC-012/§29)** — distinct explicit 상태(§26 RLP-AC-012 line 680 9-stage): `evl0_review:
bool | None`·`adr_accepted: bool | None`·`plan_eligible: bool | None`·`evl5_complete: bool | None`·
`promotion_eligible: bool | None`·`config_activated: bool | None`·`live_authorized: bool | None`·
`restricted_live_ready: bool | None`·`production_ready: bool | None` + `authority_effect: AllFalseTrialAuthority`.
각 독립 bool(주입) — 상호 함의 없음(§5.4). **manually-transcribed anchor**: 9-stage 집합은 §26 RLP-AC-012
line 680 verbatim 전사("... remain distinct explicit states"·§7.2 drift property).

**`AllFalseTrialAuthority`(all-false·§6.4·RLP-INV-001/§7)**: `creates_capacity: bool = False`·`creates_protection:
bool = False`·`issues_live_authorization: bool = False`·`issues_capability: bool = False`·`transmits: bool =
False`·`clears_halt: bool = False`·`re_arms: bool = False`·`grants_broker_permission: bool = False`·
`classifies_protection: bool = False`. `model_validator` any-True ⇒ `ArtifactIntegrityError`(rcl `AllFalseAuthority`·
egress `AllFalseEgressAuthority`·cur `AllFalseCurrentnessAuthority` 동형·**로컬 재표현·import 아님**). **근거**:
RLP-INV-001 line 150 verbatim: "Policy, plan, run state, evidence, review, and promotion artifacts create **no**
capacity, protection, Live Authorization, capability, transmission, HALT clear, or re-arm authority."

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계

### 3.1 canonical REUSE

`tos.canonical` **REUSE**(import): `IndependentIdArtifact`(id ⊥ digest base)·`classify_record_pair`+
`RecordPairKind`{CRITICAL_CONFLICT/IDEMPOTENT_REPLAY/...}(plan/package/decision의 append-only 무결성·same-id/
different-bytes 탐지)·`CanonicalDecimal`(effect envelope digest용)·`FrozenModel`·`EVL1ProvisionalCanonicalizer`
(digest 결정론). **canonical만이 base 의존**(rcl/ioc/evidence/capsule/egress/cur 선례 동형). **주의**: promotion
decision replay-across-attempt 런타임 탐지는 +Security(RLP-EV-007) — L1은 `classify_record_pair` 구조 분류만.

### 3.2 ordering REUSE (generation floor·promotion generation 순서)

`tos.ordering` **REUSE**(import·`compare_order`): plan/run/promotion generation 순서·Promotion Generation
monotonic fence(§5.10)·predecessor floor(§9 line 261)·authority epoch `>=` shape REUSE(§0.4g). **PROMOTE 0**
(신규 core 승격 없음 — canonical/ordering이 충분). Promotion Generation(§5.10)은 ordering identity이지 wall-clock
아님 — RLP는 clock-free(`MAX_trial_*_ms` wall-clock age는 secondary +Security/INSTANCE·§8).

### 3.3 REUSE 요약 표

| 대상 | 결정 | 근거 |
|---|---|---|
| `tos.canonical`(IndependentIdArtifact·classify_record_pair·CanonicalDecimal·FrozenModel·EVL1ProvisionalCanonicalizer) | **REUSE (import)** | base digest substrate·replay/substitution 구조 분류·전 시리즈 선례 |
| `tos.ordering`(compare_order·Ordering·OrderingEvent) | **REUSE (import)** | plan/run/promotion generation floor·predecessor·Promotion Generation monotonic·authority 선례 |
| 형제 tos 패키지 전부(egress·cur·rcl·ioc·evidence·hag·iap·spg·liveauth·authority·time·are·afg·sbr·capsule·venue·protective·recon·brokercap·orthostate·replacement·nontrade·dsl + 미래 wdr/sir/stm/sci/ptf) | **NO import (sibling edge 0)** | 형제 상호작용은 주입 scalar/digest/bool/verdict/enum-token으로만(§3.4). egress/cur가 RLP를 소비하므로 RLP→egress/cur import 시 순환 |
| `_NonTruthyStrEnum` | **로컬 재표현 (import 아님)** | iap `ApprovalResult`·cur `ProofResult` 선례 — 각 패키지 로컬 정의 |
| `AllFalseTrialAuthority` | **로컬 재표현 (import 아님)** | rcl/egress/cur `AllFalse*Authority` 선례 |
| iap single-use consumption *shape* | **로컬 재표현 (import 아님)** | `promotion_progressive_single_use`가 iap shape REUSE(§0.4g·§6.3) |

### 3.4 sibling edge 0 정책

RLP는 **어떤 형제 tos 패키지도 import하지 않는다.** 형제/미착지 owner의 verdict/generation/digest는 전부
**주입 좌표**(scalar/digest/bool/verdict/enum-token). 이는 (a) **순환 방지(본 문서 특유·강)**: egress/cur가
RLP-생산 generation을 소비하므로 RLP가 egress/cur를 import하면 **순환**, (b) firewall allowlist(`closure ⊆
{canonical, ordering, rlp}`·§7.1), (c) 계층 분리(RLP가 content 생산 → egress/cur가 boundary 소비)를 강제한다.
**PROMOTE 0**(canonical/ordering 외 신규 core 없음).

### 3.5 소유권 / seam 분할표 (본 문서 최대 함정 — 코드 실측)

| trial/promotion 관련 아티팩트/술어 | 소유 (실측) | RLP 관계 (재저작 금지) |
|---|---|---|
| egress `TrialClaims`(6-scalar)·`is_complete()`·`QuorumCommitCertificate._trial_claim_completeness`(`state.py:190-227`·`records.py:210-227`) | **egress (#22)** | egress = **boundary all-present 구조 seal**. RLP = 그 6-scalar의 **내용 생산자**(하류 주입)·boundary seal 재저작 안 함(§0.4b/c) |
| cur `TrialClaims`(6-scalar)·`DimensionKey.RESTRICTED_LIVE_TRIAL`(`state.py:134-150`·`vocabulary.py:159-165`) | **cur (#23)** | cur = **currentness-vector conditional 차원**. RLP = 그 차원의 *generation 내용* 소유·cur vector-completeness 재저작 안 함(§0.4c) |
| **ExactTrialPlan 완전성·6-scalar 내용**(§9) | **RLP (신규)** | plan이 §9 exact scope + baseline bind — egress thin seal보다 두꺼운 content completeness(§0.4b·형제가 RLP로 이연 증언) |
| **TrialEvidencePackage 완전성·negative retention**(§16) | **RLP (신규)** | §16 element-class manifest + negative-retention gate. custody는 evidence 주입 |
| **CoverageClaim 비외삽**(§17)·**GateStatusLadder 분리**(§26 AC-012) | **RLP (신규)** | claimed ⊆ observed 부분집합·9-stage distinct 상태 |
| evidence `SegmentCommitmentScheme`·`causal_chain_complete`·gap machine(`ledger.py:82`·`predicates.py:130`·`gap.py`) | **evidence** | 조립 + custody 무결성(ADR-002-016). RLP = causal_chain_complete/gap-status **주입 소비**(§0.4d) |
| hag `effective_principal_collapse`·`quorum_independence_satisfied`·`quorum_for`(`predicates.py`·`records.py:109`) | **hag (#…)** | human-authority 일반 모델(ADR-002-015). RLP = collapse/quorum verdict **주입 소비**·RLP-EV-008 L2+(§0.4e) |
| rcl `CapacityVector`·`within_limits`·worst-credible-effect·commit-proof(`vector.py:74`·`predicates.py:78`) | **rcl** | §7 "RCL only" capacity. RLP Trial Budget ≠ capacity·주입 좌표 소비·worst-effect 계산 +Broker(§0.4g) |
| liveauth Live Authorization generation | **liveauth** | trial Live Auth(§12)·promoted re-arm. RLP 주입 소비·발급 안 함(RLP-INV-001) |
| spg `bundle_complete`·policy activation(`predicates.py:818/857`) | **spg** | **완전성 선례**·Trial Policy 활성화 = spg/014 주입(§0.4g·§8 line 253) |
| iap `single_use`/`exact_intent_only`·consume gate(`predicates.py:176/230`) | **iap** | **single-use consumption shape 선례**. `promotion_progressive_single_use`가 REUSE(재저작 아님·§6.3) |
| authority `authority_epoch_current`(`>=`)·`recovery_generation_revives_nothing`(`predicates.py:787`) | **authority** | floor `>=` shape·non-revival 선례(compare_order REUSE·§0.4g) |
| 026/027/028/029/030 governance 내용(release/incident/monitoring/…) | **미착지 owner** | RLP = generation/digest 좌표 주입 소비·**내용 재판정 금지(phantom·§0.4f)** |

---

## 4. 술어 규율 (canary·극성·reconcile·집합)

### 4.1 금지 동사 canary (`test_rlp_void_canaries.py`)

RLP 모듈은 **순수·비전송·비변이·clock-free**임을 정적 회귀로 봉인한다: `tos/src/tos/rlp/**`에 `send`/`transmit`/
`emit`/`sign`/`arm`/`rearm`(실행)·`mutate`/`reserve`/`release`/`transfer`/`commit_capacity`(capacity)·`approve`/
`authorize`/`promote`(실행 승인·**RLP는 promotion *구조 판정*만·실 승인 아님**)·`clear_halt`·`open`/`connect`/
`socket`·`time.time`/`datetime.now`/`monotonic`(clock)·`os.environ`·`exec`/`eval`/`importlib`/`__import__` 문자열이
**부재**함을 grep 회귀로 확인(egress/cur `test_*_void_canaries.py` 동형). trial artifact가 authority를 생성하지
않음을 코드 수준에서 증언(RLP-INV-001).

### 4.2 truthy-sentinel 봉인 (`test_rlp_truthy_sentinel.py`)

`PlanResult`·`PromotionResult`·`TrialRunState`·`CoverageVerdict`는 `_NonTruthyStrEnum`(`__bool__ ⇒ TypeError`).
회귀: 각 멤버에 `bool(x)`가 `TypeError`; 소비 게이트는 `result is PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`·
`result is PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE`·`verdict is CoverageVerdict.COVERED` 명시 비교만
사용(`if result:` 부재 grep). `INELIGIBLE`/`HOLD`/`DENY`/`ABORTING`/`TERMINATED`/`UNCOVERED`/`UNKNOWN`을 truthy로
오독하는 fail-open 방지.

### 4.3 극성 규율 (§4.2 — #22 MAJOR-2 재발 방지·전수 점검)

**핵심 교훈(#22 MAJOR-2·#23 상속)**: `bool | None` 필드에 `if field:`/`if not field:`를 쓰면 `None`이 극성에
따라 **fail-open**한다. 모든 필드는 **극성을 명시**하고 `is True`/`is False`/`is not True`/`is not False`로만
정규화한다. `None`은 **양쪽 극성 모두에서 UNKNOWN ⇒ deny**로 수렴하되, clear시키는 명시값이 극성마다 다르다.

| 필드 | 극성 | clear 조건 | deny 조건 | 정규화 | 근거 |
|---|---|---|---|---|---|
| `pre_registered` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §9 line 275 "pre-registered" |
| `independently_reviewed` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §11 item 6·RLP-INV-014 |
| `selection_fixed_before_start` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ incomplete` | §16 line 426 |
| `equivalence_positively_proven` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ non-equivalence` | §17 line 444 "Unknown equivalence is non-equivalence" |
| `effective_principal_verdict`(hag 주입) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §22·RLP-INV-014(hag 소유) |
| `causal_chain_complete`(evidence 주입) | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ incomplete` | §16(evidence 소유) |
| `single_use_consumed` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ reject reuse` | §18 line 464 "consumed, once" |
| `is_expired` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ future-use deny`(capacity 불변·§6.5) | §20·RLP-INV-012 |
| `is_aborted` / `is_invalidated` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §14 line 378·§15 |
| `optional_stopping` / `discarded_runs` / `selected_windows` / `removed_adverse` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ invalidate promotion` | §16 line 426 |
| `run_resumed` / `re_armed` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny`(non-revival) | §21·RLP-INV-013 |

**전수 점검 회귀(`test_rlp_polarity.py`)**: 모든 음극성 필드에 대해 `None` 입력이 **restricted/deny로 수렴**함을
property test(hypothesis)로 확인 — `single_use_consumed=None`이 "not consumed"로 fail-open하거나 `is_expired=None`이
"not expired"로 fail-open하는 #22 MAJOR-2 재발을 구조적으로 봉인. 모든 양극성 필드에 대해 `None`/`False`가 deny로 수렴.

### 4.4 그룹 reconcile 규율 (#22 MAJOR-1 재발 방지 — 전-package 보수·no-union)

**핵심 교훈(#22 MAJOR-1)**: 여러 entry가 한 그룹/scope에 매핑될 때 판정은 **첫-entry가 아니라 전-entry를
보수적으로 reconcile**해야 한다. RLP의 reconcile 지점(§17 no-union이 특히 강):

- **`no_union_coverage`(§6.3 지지·§17 line 446)**: 여러 narrow passing package를 **union하지 않음**(§17 line
  446 verbatim: "Multiple narrow passing packages cannot be unioned into a broad coverage claim. An aggregate
  scope requires its **own** combined-scope concurrency and common-mode evidence"). 한 package라도 claim을
  cover 못 하면 aggregate deny(any-narrow-wins·첫-package 채택 아님).
- **`negative_results_retained`(§5.2)**: 전 run(negative 포함) reconcile — passing subset 선택 불가(§16 line
  426·RLP-INV-009 "Passing subsets cannot erase them"). entry 순서 무관·negative 하나라도 누락 ⇒ incomplete.
- **Promotion Generation floor(§5.10)**: 여러 generation entry ⇒ **MAX(최신 fence)** 채택(§18 line 466 "after
  ... a newer Promotion Generation" ⇒ 구 decision 무효)·첫-generation 아님.

**회귀(`test_rlp_reconcile.py`)**: entry/package 순서 permutation에 대해 verdict 불변(순서 독립) + 가장
restrictive(any-narrow-wins·negative-present-required·MAX-generation) 지배를 property test로 확인.

---

## 5. 핵심 L1 술어 (§5 — 4 노른자 + 지지)

> 전 술어 규율 태그: **structural/completeness/subset/separation predicate substrate only; RLP-EV-001/005/006/012
> 전부 NOT_IMPLEMENTED(`EV-L1/3` — `/3` 통합·adversarial 대기). 전 owner verdict/generation/digest는 주입. L1은
> plan/package/coverage/gate 구조 판정만.**

### 5.1 `plan_scope_exact_and_complete` (RLP-EV-001 노른자·§9)

**`mandated_scope` floor 고정(cur v1.1 MINOR-1 선례)**: `mandated_scope` 파라미터는 자유 주입이 아니라 **전
`ScopeDimension` 멤버(= §9 line 263 floor)를 기본 하한**으로 하며 caller는 이보다 좁힐 수 없다(policy는 위로
추가만·"at least" 방향).

**시그니처(계약)**: `plan_scope_exact_and_complete(plan: ExactTrialPlan | None, policy: TrialPolicy | None,
mandated_scope: frozenset[ScopeDimension]) -> bool`.

**판정(전부 AND·fail-closed)**:
1. **∅-seal 양방향**: `plan is None` 또는 `policy is None` 또는 `mandated_scope` ∅ ⇒ `False`(**absent
   scope에 대해 완전성을 vacuously 참으로 두지 않음**·§9 line 275 "A missing ... plan is `INELIGIBLE`"). plan
   scope 차원 ∅인데 mandated 비어있지 않으면 ⇒ `False`.
2. **result admissible(truthy 봉인)**: `plan_result_admissible(plan)` — `plan.result is
   PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`(§4.2). INELIGIBLE/HOLD ⇒ deny.
3. **전 scope 차원 present + concrete**: `mandated_scope ⊆ {d for d in plan.trial_scope if concrete(d)}`
   (§5.3). **집합 양방향**: mandated ⊄ present ⇒ deny(plan이 §9 floor 미달). 미표현 scope 차원 ⇒ incomplete ⇒
   deny(egress QCC coexistence seal·spg `bundle_complete` 동형).
4. **no wildcard/inferred/unioned/stale**: `no_wildcard_scope(plan)` — 어떤 차원도 `*`/`latest`/null-as-scope/
   inferred sentinel 미사용(RLP-INV-002 line 154 "wildcard, inferred, patched, unioned, stale, or conflicting scope is
   denial"·RLP-INV-002).
5. **baseline digests bound**: `baseline_digests_bound(plan)` — 전 baseline artifact digest concrete(§9 line
   263 "complete baseline artifact digests")·`None`/wildcard ⇒ deny.
6. **pre-registered + reviewed**: `plan.pre_registered is True` AND `plan.independently_reviewed is True`(양극성·§4.3).

**반환**: 위 전부 성립시에만 `True`. **완전성은 egress thin all-present seal이 아니다** — (3)의 미표현 차원,
(4)의 wildcard, (5)의 baseline은 exact-scope content 축이며, egress의 `is_complete()`(6-scalar all-present)는
boundary 구조 seal일 뿐이다(§0.4b/c). **RLP-EV-001을 닫지 않음**(`/3` 잔여).

**`trial_claims_complete`(§0.4b/c seam 정합·내용 소유자 authoritative)**: `trial_claims_complete(claims:
TrialClaimGroup | None, plan: ExactTrialPlan | None) -> bool` — 6-scalar(trial_policy/plan/run/promotion
generation·remaining_envelope·abort_generation) 전부 concrete(egress `is_complete()` 정합) **AND** plan이
`plan_scope_exact_and_complete`(내용 두께 추가). **정합 회귀(manually-transcribed anchor·§7.2)**: RLP
`TrialClaimGroup` 필드-집합 == egress §11.1 line 308 / cur §9:258 6-scalar 집합을 손으로 옮긴 anchor와 일치를
강제(import 아님·drift 발각).

### 5.2 `evidence_package_complete` (RLP-EV-005 노른자·§16·negative retention)

**시그니처**: `evidence_package_complete(package: TrialEvidencePackage | None, policy: TrialPolicy | None,
mandated_classes: frozenset[EvidenceClass]) -> bool`.

**판정(전부 AND·fail-closed)**:
1. **∅-seal 양방향**: `package is None` 또는 `policy is None` 또는 `mandated_classes` ∅ ⇒ `False`(§16 line
   428 "A complete package proves what occurred ... it does not prove that untested behavior is safe").
2. **전 element-class present**: `mandated_classes ⊆ present_classes(package)`(§16 line 417-424 event/coverage/
   broker/generation classes). **집합 양방향**·미표현 class ⇒ incomplete ⇒ deny.
3. **negative retention(노른자 핵심)**: `negative_results_retained(package)` — `negative_results`·
   `failed_results`·`inconclusive_results`·`aborted_results`·`conflicting_results` class가 **present**(부재 ⇒
   incomplete·RLP-INV-009 "Failed, aborted, conflicting, incomplete, and inconclusive trials remain retained").
   evidence ERI-INV-004(gap/denial/failure first-class)와 **정합하되 별개 gate**(§0.4d).
4. **selection fixed + no selective reporting**: `package.selection_fixed_before_start is True`(양극성) AND
   `optional_stopping`/`discarded_runs`/`selected_windows`/`removed_adverse` 전부 `is False`(음극성·§4.3·§16
   line 426 "Post-hoc metric changes, optional stopping, discarded runs, selected time windows, selected
   accounts, or removal of adverse results invalidate the promotion claim").
5. **evidence integrity 주입**: `package.causal_chain_complete is True`(evidence 주입 verdict·§0.4d) AND
   gap-status가 unresolved gap 부재. **재저작 아님**(evidence 소유).

**반환**: 위 전부 성립시에만 `True`. **RLP-EV-005를 닫지 않음**(`/3` 잔여).

### 5.3 `coverage_supports_claim` (RLP-EV-006 노른자·§17·비외삽 부분집합)

**시그니처**: `coverage_supports_claim(claim: CoverageClaim | None) -> bool`. **가장 깨끗한 L1 슬라이스**
(순수 부분집합·survey line 237 "L1 접근성 가장 깨끗").

**판정(전부 AND·fail-closed)**:
1. **∅-seal 양방향**: `claim is None` 또는 `claim.observed_scope` ∅ 또는 `claim.claimed_scope` ∅ ⇒ `False`
   (관측 없는 claim·claim 없는 coverage 둘 다 deny — §5.8 "Unexercised ... behavior is uncovered").
2. **부분집합 비외삽(집합 양방향)**: `claim.claimed_scope ⊆ claim.observed_scope`(§17 line 434 "map evidence
   to exact ... scope"). **claimed에 observed ∉ 원소가 하나라도 있으면 ⇒ deny**(외삽·§17 line 444 "No
   inference may broaden evidence across a different ... scope").
3. **equivalence positively proven(외삽 예외의 유일 경로)**: cross-scope 추론은 `claim.equivalence_positively_
   proven is True`(양극성·정책 승인 equivalence 증거)일 때만(§17 line 444 "unless the active policy supplies
   approved equivalence evidence. **Unknown equivalence is non-equivalence**"). None/False ⇒ 비외삽 강제.
4. **unexercised is uncovered**: `unexercised_is_uncovered(claim)` — `claim.unexercised_conditions`가 claimed에
   포함되면 ⇒ deny(§5.8 "Silence and unexercised coverage do not prove safety"·RLP-INV-008).
5. **verdict 정합**: `claim.verdict is CoverageVerdict.COVERED`(truthy 봉인·§4.2). UNCOVERED/UNKNOWN ⇒ deny.

**반환**: 위 전부 성립시에만 `True`. `no_union_coverage`(§6.3·다중 package 비합집합)와 함께 §17 완결. **RLP-EV-006을
닫지 않음**(`/3` 잔여).

### 5.4 `gate_status_separated` (RLP-EV-012 노른자·§26 AC-012/§29·상태 분리)

**시그니처**: `gate_status_separated(ladder: GateStatusLadder | None) -> bool`.

**판정(전부 AND·fail-closed)**:
1. **∅-seal**: `ladder is None` ⇒ `False`.
2. **9-stage present(manually-transcribed anchor)**: `evl0_review`·`adr_accepted`·`plan_eligible`·`evl5_complete`·
   `promotion_eligible`·`config_activated`·`live_authorized`·`restricted_live_ready`·`production_ready` 전
   stage가 독립 표현(§26 RLP-AC-012 line 680 "remain distinct explicit states"). anchor 집합 == 모델 필드(§7.2 drift).
3. **no implication(핵심)**: `no_status_implication(ladder)` — 어떤 stage의 positive가 다른 stage를 함의하지
   않음. 특히 `plan_eligible is True`가 `live_authorized`를 함의하지 않고(§9 "non-authorizing"),
   `promotion_eligible is True`가 `config_activated`/`production_ready`를 함의하지 않음(§18 line 464 "It is not
   approval of an order or production permission"·§19 "Production authorization is a **separate** explicit
   human-governed decision"). 구조적으로: 각 stage는 독립 주입 bool이며, 한 stage에서 다른 stage를 파생하는
   코드 경로가 부재함을 술어가 강제(파생 시도 = malformed).
4. **readiness ≠ authority**: `readiness_not_authority(ladder)` — `restricted_live_ready`/`production_ready`가
   `True`여도 `ladder.authority_effect`는 all-false(sbr readiness≠re-arm 선례·§26 AC-012). readiness는 상태
   보고이지 permission 아님.

**반환**: 위 전부 성립시에만 `True`. 이는 all-false-authority를 **상태 분리**로 확장한 것(전 gate가 서로를
truthy-함의하지 않음)이다. **RLP-EV-012를 닫지 않음**(`/3` 잔여).

---

## 6. predicate-only substrate (§6 — 닫지 않음) + not-Phase-1 (§6b)

> 전 술어 규율 태그: **predicate substrate only; 해당 RLP-EV 전부 NOT_IMPLEMENTED(≥ L2 component-fault +
> +Security/+Broker 대기). L1-decidable 순수 판정을 저작하되 어떤 RLP-EV도 닫지 않는다.**

### 6.1 `trial_budget_is_not_capacity` (§10·RLP-EV-002 substrate·+Broker)
`TrialBudget`은 capacity를 mutate/reserve/release하지 않음(all-false 축 — §7 "RCL only"·§10 line 296 "Unused
plan budget creates no headroom"). budget numeric은 검증 대상 request envelope·rcl CapacityVector는 주입 좌표.
**worst-credible-effect 계산(§10 line 283-294)은 rcl + +Broker**(§28 open Q #3). `EV-L2/3+Broker`.

### 6.2 `trial_status_waives_no_gate` (§13·RLP-EV-003 substrate·+Broker)
trial flag/low-notional/canary label/operator supervision/evidence-collection은 **bypass authority 무보유**
(all-false·RLP-INV-004 line 162 "Restricted-live status, low notional, supervision, canary naming, or evidence
collection **never bypasses** a normal safety check or final-egress enforcement"). 실 per-send binding(§13 line
347-354)은 egress 런타임·+Broker. `EV-L2/3+Broker`.

### 6.3 `promotion_progressive_single_use` (§18·RLP-EV-007 substrate·+Security·iap shape REUSE)
`promotion_progressive_single_use(decision) -> bool`: `decision.single_use_consumed is False`(음극성 — 명시
False에서만·consumed ⇒ reject reuse·§18 line 464) AND `decision.result is PromotionResult.ELIGIBLE_TO_REQUEST_
NEW_SCOPE`(§4.2) AND `no_union_coverage`(다중 package 비합집합·§4.4) AND `within_max_delta`(요청 delta ≤ policy
max_delta·§18 line 466 "exceed the approved delta") AND no-replay(§18 line 466 "combine decisions, reuse old
evidence"). **iap `single_use`/`exact_intent_only` consumption shape REUSE**(재저작 아님·§0.4g). 실 registry
replay/generation-fence는 +Security. `EV-L2/3+Security`.

### 6.4 `all_false_trial_authority` (§7 SoD/§22·RLP-EV-008 substrate·+Security)
`AllFalseTrialAuthority` 전 필드 `is False` 확인 + model_validator any-True ⇒ `ArtifactIntegrityError`. policy/
plan/run/package/decision 어느 것도 create-capacity/issue-Live-Auth/transmit/clear-HALT/re-arm 불가(RLP-INV-001).
SoD 구조 선언: trial 컴포넌트는 RCL/egress authority 무보유(§7 table). **effective-principal collapse는 hag-owned
주입**(§0.4e)·실 independence는 +Security. `EV-L2/3+Security`.

### 6.5 `expiry_denies_future_use_only` (§20·RLP-EV-009 substrate·+Broker·극성 봉합)
`is_expired is not False` ⇒ **future-use deny**; **capacity/economic effect 불변**(RLP-INV-012 line 194 verbatim:
"Trial completion, abort, expiry, invalidation, or promotion-decision consumption **cannot cancel orders, prove
non-acceptance or Final Quantity, erase positions, or release capacity**"). §20 line 490-499 전 항목 금지.
**음극성 함정 봉합**: `is_expired`가 `None`이면 "not expired" fail-open 없이 deny. `economic_effect_persists`
(afg/are/capsule `terminal_release_proven` shape) 동형. `EV-L2/3+Broker`.

### 6.6 `recovery_revives_nothing` (§21·RLP-EV-010 substrate·+Security·authority 선례)
restart/reconnect/failover/restore/replay/reconciliation/time-recovery/broker-recovery/operator-return ⇒ **no
revival**(RLP-INV-013 line 197). prior run ⇒ `INVALIDATED`(§21 line 509)·queued action reject·old authorization/
promotion fence·new run identity 요구. authority `recovery_generation_revives_nothing`·cur `recovery_revives_
nothing` 동형(재저작 아님·§0.4g). 실 hard-fence는 +Security. `EV-L2/3+Security`.

### 6.7 `monitoring_not_preventive` + `demotion_not_rearm` (§19·RLP-EV-011 substrate·+Broker)
EV-L6 monitoring은 **detective**(non-authorizing·RLP-INV-015 line 208 "A `CONFORMING` monitor result remains
non-authorizing and cannot promote, resume, or re-arm"). drift ⇒ invalidate evidence + restrict(§19 line 484).
demotion to narrower scope는 **historical promotion 재사용 아님**(§19 line 484 "historical promotion is not a
reusable authorization")·fresh config/reconciliation/authority 요구. monitoring generation은 **-028 미착지
주입**(§0.4f). `EV-L2/3+Broker`.

### 6b. not-Phase-1 얇은 모델 property (RLP-EV-004 — 닫지 않음·런타임 race)
- **abort dominance/race(§15·RLP-EV-004·`EV-L3+Security`)**: 순서 permutation model(`ABORT<ACTION ⇒ deny`·
  `ACTION<ABORT<FIRST_BYTE ⇒ potentially-live + capacity-covered`·unknown ⇒ potentially-live·no-blind-retry·
  §15 line 408 "A lost abort response is treated as **possibly applied**"). 실 abort latency·`B_trial_abort_to_
  authority_revoke`/`B_trial_abort_to_egress_deny` bound·deny-first latch·incident protocol(§15 line 406·-027
  미착지)는 **전부 +Security 런타임**. abort dominates evidence(RLP-INV-005)는 런타임 우선순위 규칙.

### 6c. 순수 런타임 / 인간 절차 (L1 model property 없음)
per-action final-egress 8-control binding(§13)·Trial Run 상태 전이 serialization(§14 line 376 "Process-local
counters ... are not serialization authority")·worst-credible-effect 계산(§10)·trial Live Authorization 발급
(§12·liveauth)·independent review + promotion approval + production authorization(§18-§19·hag/인간)·evidence
조립 무결성(§16·evidence SegmentCommitmentScheme)·pre-trial gate 12항목(§11·런타임)·Governed Single-Operator
Re-Arm(§22·hag/liveauth). 전부 런타임/인간/+Security/+Broker/형제-owned — §9.2 Phase-0.

---

## 7. firewall allowlist + 회귀

### 7.1 import-closure allowlist (`test_rlp_import_closure.py`)

`tos.rlp`의 전이 import closure는 **`{canonical, ordering, rlp}`에 국한**되어야 한다(egress/cur/rcl
`test_*_import_closure.py` 동형). `tools/tos_firewall_check.py`(§3.2 ratified allowlist·default-deny·line 55)가
`shared.*`/`services.*`/`cli.*`/외부 수치 라이브러리/동적 escape/형제 tos 패키지 import를 **차단**. 이 required
check가 green이어야 §0.3 firewall 선언이 능동 성립. **naming(§0.4a)은 soft load-bearing**(seam 토큰 정합) —
미래 형제 wdr/sir/stm/sci/ptf는 allowlist가 자동 배제. **`tos.rlp`를 §3.2 allowlist에 추가하려면 본 설계 문서
§3.2를 편집하는 PR 필요**(firewall check line 422).

### 7.2 회귀 스위트 (예정 — `tos/tests/rlp/`)

`test_rlp_plan.py`(plan_scope_exact_and_complete 노른자·∅/미표현/wildcard/baseline property + **6-scalar seam
정합 anchor property**[egress §11.1 line 308 / cur §9:258 필드-집합 == RLP TrialClaimGroup·manually-transcribed
anchor·§0.4h])·`test_rlp_package.py`(evidence_package_complete·negative retention·selection-fixed·∅/집합
양방향)·`test_rlp_coverage.py`(coverage_supports_claim 부분집합 양방향·no-union·equivalence·비외삽 property)·
`test_rlp_gate.py`(gate_status_separated·no-implication·9-stage anchor)·`test_rlp_polarity.py`(극성 전수·§4.3)·
`test_rlp_reconcile.py`(그룹 reconcile 순서독립·no-union·§4.4)·`test_rlp_truthy_sentinel.py`(§4.2)·`test_rlp_
void_canaries.py`(§4.1)·`test_rlp_authority.py`(all-false)·`test_rlp_predicate_only.py`(§6 substrate)·
`test_seam_egress.py`+`test_seam_cur.py`(seam 6-scalar 정합·§3.5)·`test_rlp_import_closure.py`(§7.1).
**property-based(hypothesis)** 중심(EV-L1 = model/property). **anchor drift property가 최우선**(seam 6-scalar·
§9 scope 차원·§16 element-class·§29 9-stage가 손전사 anchor와 일치·cur v1.1 §7.2 교훈).

---

## 8. 수치 → Phase-0 / INSTANCE (숫자 하드코딩 0)

RLP 소유 numeric은 **전부 Profile INSTANCE 측정/승인·주입**(현재 전부 `null`/`TBD`·`VERIFICATION-PROFILE-002.yaml`
실측):

| 키 (VP line) | 소유 | 상태 | 근거 |
|---|---|---|---|
| `restricted_live_trial_policy_id`(73) | **RLP** | TBD | §8 Trial Policy identity(활성화 spg 주입) |
| `restricted_live_trial_policy_generation`(74) | **RLP** | null | §8 policy generation(spg/014 advance) |
| `restricted_live_trial_policy_digest`(75) | **RLP** | TBD | §8 policy canonical digest |
| `B_trial_abort_to_authority_revoke`(359) | **RLP** | MEASURE·null | §15 abort→authorization revoke(런타임·RLP-EV-004) |
| `B_trial_abort_to_egress_deny`(366) | **RLP** | MEASURE·null | §15 abort→egress deny(런타임) |
| `B_trial_evidence_gap_to_containment`(373) | **RLP** | MEASURE·null | §16 evidence gap→containment(런타임) |
| `B_scope_promotion_generation_fence`(380) | **RLP** | MEASURE·null | §18 promotion gen→predecessor 무능 증명 |
| `MAX_trial_authorized_economic_effect`(725) | **RLP** | APPROVE·null | §10 unbounded effect ⇒ trial 금지(+Broker) |
| `MAX_trial_concurrent_potential_effect`(726) | **RLP** | APPROVE·null | §10 shared scope potentially-live + abort/recovery overlap |
| `MAX_trial_action_count`(727) | **RLP** | APPROVE·null | §14 unavailable counter ⇒ deny action |
| `MAX_trial_duration_ms`(728) | **RLP** | APPROVE·null | §14/§20 expiry ends future action only(economic 불변) |
| `MAX_trial_evidence_age_ms`(729) | **RLP** | APPROVE·null | §18 stale evidence ⇒ deny promotion(wall-clock secondary·+Security) |

**주의**: worst-credible-effect *계산*(§10)은 rcl + +Broker(§28 open Q #3)·RLP는 CapacityVector 주입 소비.
**L1 아티팩트는 전 numeric이 `null` 상태에서 구성 가능**해야 하며(§2.3 `_REQUIRED_COVERED` numeric 제외), 누락
numeric claim은 fail-closed(§4.2). broker proper noun/KIS 특정값 부재(broker-agnostic).

---

## 9. Phase-0 / not-Phase-1 체크리스트

### 9.1 Phase-1(EV-L1) 산출물 (본 계약이 실현 지침을 제공)
1. `tos.rlp` 패키지(canonical/ordering만 의존·firewall green).
2. 모델: `TrialPolicy`·`ExactTrialPlan`·`TrialRun`·`TrialEvidencePackage`·`ProductionScopePromotionDecision` +
   value(`TrialScope`·`TrialBudget`·`CoverageClaim`·`GateStatusLadder`·`TrialClaimGroup`)·`AllFalseTrialAuthority`
   + enum(`PlanResult`·`PromotionResult`·`TrialRunState`·`CoverageVerdict`·`ScopeDimension`·`EvidenceClass`).
3. 노른자 술어 4종(§5) + 지지 + predicate-only substrate(§6) + 얇은 not-Phase-1 model(§6b).
4. malformed-model validator(positive-claim + incomplete-group seal)·truthy 봉인·극성·reconcile·all-false·
   canary·**seam 6-scalar anchor drift** 회귀(§4·§7.2).

### 9.2 Phase-0 / 미착지 / +Security / 런타임 / 인간 (닫지 않음 — 20 항목)
1. Trial Policy/Plan/Evidence Package/Promotion Decision canonical schema **승인**(§28.1·§29.1·거버넌스).
2. plan/run/action/abort/promotion ordering domain + stale-generation fencing(§28.2·§29.2·**런타임**).
3. worst-credible trial effect + RCL/action-flow binding 결정론 계산(§28.3·§29.3·**+Broker·rcl-owned**).
4. per-action final-egress binding(exact plan/remaining-envelope/authorization/currentness·cache-free·§29.4·
   **egress-owned 런타임**).
5. abort/HALT/demotion 독립·monotonic·bounded·non-bypassable(§29.5·**+Security 런타임·RLP-EV-004**).
6. evidence capture 조립 + 무결성(negative/inconclusive 보존·no-selection·SegmentCommitmentScheme·§29.6·
   **evidence-owned 런타임**).
7. promotion progressive/single-use/exact-delta registry(§29.7·**+Security**).
8. restart/failover/restore/recovery/queue-drain/monitoring-recovery hard-fence(§29.8·**런타임·+Security**).
9. trial/evidence/replay/promotion identity segregation from live egress(§29.9·**+Security·failure-domain**).
10. RLP-EV-001..012 required-level pass + 독립 review(§29.10·**전 EV**).
11. security/failure-domain/currentness/capacity/authority/evidence/abort/generation-fence review(§29.11·**+Security**).
12. 12개 numeric bound 측정/승인(§8·§29.12·**INSTANCE·+Broker·+Security**).
13. Critical/Major finding 0 + RFC/ADR/VER/Evidence Register traceability(§29.13).
14. ARCHITECTURE-GATE-STATUS 명시 ADR acceptance(§29.14·거버넌스).
15. independent effective-principal review workflow(§28.4·**hag-owned·인간·+Security**).
16. Governed Single-Operator Re-Arm Variant(ADR-002-015 §17.1·**hag/liveauth-owned·인간**).
17. trial Live Authorization 발급(§12·**liveauth-owned·ADR-002-007/015**).
18. pre-trial eligibility gate 12항목(§11·**런타임 통합**).
19. EV-L6 continuous monitoring + bounded demotion(§19·**-028 STM 미착지·+Broker**).
20. 026/027/028/029/030 governance generation 차원 owner 착지 후 실 좌표 배선(현재 주입 opaque·미착지·§0.4f).

**cross-EV 의존(§29.10)**: RLP-EV closure는 rcl/egress/cur/hag/evidence/liveauth/spg/iap/authority/time 및
026-030 evidence가 required level에서 pass해야 성립 — Phase-1 범위 밖.

---

## 10. 명명 결정 + 리뷰어 공격 지점

### 10.1 운영자 판단 지점
- **패키지 명명 `tos.rlp`**(§0.4a) — register-prefix 1:1·**seam 토큰이 이미 이름 고정**(egress `state.py:196`·
  cur `state.py:140`이 `tos.rlp` 명시 인용). runner-up `tos.restrictedlive`/`tos.trial`/`tos.promotion` 기각.
  naming soft load-bearing(cur와 대비).
- **survey "not-Phase-1" 8행을 predicate-only 7 + not-Phase-1 1로 세분**(§1 결정적 사실 3) — register EV-level
  (004만 유일 `EV-L3+`)과 정합하는 증거기반 세분. **독립 리뷰어가 재검토할 지점**(survey 원 라벨과의 차이).
- **RLP = content 소유자·egress/cur boundary seal 존치**(§0.4b/c) — 대안: RLP가 canonical `TrialClaims`를
  소유하고 egress/cur가 import(기각 근거: sibling edge 0 + 순환[egress/cur가 RLP 소비] + egress/cur 이미 착지).

### 10.2 리뷰어 공격 지점 (선제 반론)
1. **"RLP가 egress QCC/TrialClaims seal 중복"** — 반론: egress seal = boundary all-present 구조 검사
   (is_restricted_live_trial 공존), RLP = content exact-completeness(plan이 §9 전 scope bind)·egress가 명시
   이연(`state.py:196` "deferred to RLP")·RLP는 상류 생산자·edge 0.
2. **"RLP가 cur RESTRICTED_LIVE_TRIAL 차원 재저작"** — 반론: cur = vector-completeness 축(차원 present 여부),
   RLP = 그 차원 generation *내용*·cur `vocabulary.py:132` "RLP-deferred content" 명시·edge 0.
3. **"evidence_package_complete = causal_chain_complete 중복"** — 반론: causal_chain_complete = 인과 체인 무결성
   (evidence·주입), evidence_package_complete = §16 element-class manifest + negative-retention(RLP·다른 축).
   evidence ERI-INV-004(negative first-class 보존)과 RLP negative-부재-incomplete gate는 별개.
4. **"RLP가 hag quorum/effective-principal 재저작"** — 반론: collapse/quorum = hag(ADR-002-015)·RLP는 verdict
   주입 소비·RLP-EV-008 `EV-L2/3+Security`·edge 0(§0.4e).
5. **"미착지 026-030 차원 phantom 인용"** — 반론: ADR 원문만·코드 인용 0·주입 opaque generation(§0.4f·§0.2).
6. **"model_construct로 malformed plan 통과"** — 반론: positive-claim + incomplete-group validator + 술어 2층
   (§2.3·egress QCC `_trial_claim_completeness` 동형·#20 상속).
7. **"over-realization: per-action egress binding/abort race/worst-effect를 L1 주장"** — 반론: 닫는 RLP-EV 0·
   RLP-EV-004 not-Phase-1·§6c 순수 런타임/인간 명시(§1·§9.2).
8. **"duplication: rcl capacity/liveauth Live Auth 재판정"** — 반론: §7 "RCL only"·liveauth Live Auth·전 owner
   verdict 주입 소비·재저작 0(§0.2·§3.5).
9. **"trial_budget이 capacity headroom 생성"** — 반론: §10 line 296 "Unused plan budget creates no headroom"·
   `trial_budget_is_not_capacity` all-false·RLP-INV-003.
10. **"coverage 부분집합이 union 허용"** — 반론: §17 line 446 "Multiple narrow ... cannot be unioned"·
    `no_union_coverage` any-narrow-wins·`equivalence_positively_proven` 유일 예외(unknown = non-equivalence).

---

## 11. 선제 defect-class 봉합 (전 시리즈 교훈)

| defect class | 출처 | RLP 봉합 |
|---|---|---|
| grep head 절단 카운트 오류 | #12 | register 전수 파싱(md line 324-335 직접·§1·naive grep 금지) |
| under-realization(얇은 표면) | #7 | — (RLP는 반대 — over-realization 경계가 주 위험·§1) |
| truthy-sentinel fail-open | #13·#14 M1 | `_NonTruthyStrEnum` 처음부터(§2.2·§4.2·PlanResult/PromotionResult/TrialRunState/CoverageVerdict 4종) |
| ∅ 단방향 seal | #8·#15 | plan/package/coverage mandated·observed·claimed ∅ 양방향(§5.1-5.3) |
| 집합 단방향 | #10 | mandated ⊆ present·claimed ⊆ observed 양방향(§5.1-5.3) |
| malformed-model model_construct 우회 | #20 | positive-claim + incomplete-group validator + 술어 2층(§2.3·egress QCC seal 동형) |
| 미표현 요소 vacuous pass | #20·#23 | 미표현 scope 차원/element-class ⇒ incomplete(§5.1-5.2) |
| phantom id/코드 인용 | #17·#20·#23 | 인용 전 grep·미착지 026-030 코드 0(§0.4f)·seam은 실측 코드 line 인용 |
| **극성 fail-open(consumed/expired/aborted None)** | **#22 MAJOR-2** | **극성 전수 표 + None ⇒ deny 수렴 회귀(§4.3·11 필드)** |
| **그룹 첫-entry/union 판정** | **#22 MAJOR-1** | **전-package 보수 reconcile(no-union·any-narrow-wins·negative-retention·MAX-generation·§4.4)** |
| **enum-drift 참조집합 부정직** | **#14 anchor·cur v1.1 §7.2** | **manually-transcribed regression anchor 명시 표기(seam 6-scalar·§9 scope·§16 class·§29 9-stage·§0.4h·§7.2 drift property)** |
| seam 재저작(trial-content 중복) | #19·#22·#23 | egress/cur/hag/evidence/rcl/liveauth/spg/iap/authority 소유 실측·주입 소비(§3.5·§10.2) |
| 과대 주장(authoring=acceptance) | 전 시리즈 | 닫는 RLP-EV 0·"EV-L1-complete 주장 금지"(§1) |

---

## 12. 요약

`tos.rlp`는 시리즈의 **restricted-live trial 내용 소유자(content owner)이자 피이연자(deferee)**를 실현한다.
egress(#22)·cur(#23)가 trial 청구군을 opaque 6-scalar로 수용하고 그 내용 검증을 **이름까지 명시해(`tos.rlp`)
RLP에 이연**했음을 **코드가 증언**한다(egress `state.py:196`·cur `state.py:140`). 이는 cur(형제의 집계 이연을
*회수*한 상류 집계자)의 **거울상**이되 방향이 반대다: RLP는 상류 내용 생산자이고 egress/cur가 하류 소비자다.
본 계약의 core는 **4행(RLP-EV-001 Exact Pre-Registered Scope·005 Evidence Completeness/Negative-Retention·006
Coverage/Non-Extrapolation·012 Gate Honesty/Status Separation·전부 `EV-L1/3`·거버넌스 6부작 중 L1 최상)**이며,
노른자 술어 4종(`plan_scope_exact_and_complete`·`evidence_package_complete`·`coverage_supports_claim`·
`gate_status_separated`)으로 저작한다. **닫는 RLP-EV = 0**(authoring ≠ acceptance).

거버넌스 ADR의 본질(인간 절차·런타임)을 정직하게 경계 짓는 것이 **본 문서의 최대 규율**이다: trial 실행·
per-action egress binding·abort race·worst-credible-effect 계산·independent review·promotion approval·
production authorization·evidence 조립 무결성은 **전부 인간/런타임/+Security/+Broker/형제-owned**이며 L1이
아니다(over-realization 경계·§1·§6c). 동시에 egress QCC seal·cur 차원·hag quorum·evidence
SegmentCommitmentScheme·rcl CapacityVector·liveauth Live Authorization·spg activation은 **전부 주입 소비**이며
RLP가 재저작하지 않는다(duplication 경계·§3.5). #22 MAJOR-1(reconcile/no-union)·MAJOR-2(극성)·cur v1.1
(enum-drift anchor)를 §4.3-4.4·§7.2로 선제 봉합한다.

**비준 기록: 2026-07-27 운영자 위임 자동 비준(v1.1 — 상세는 문서 헤더 비준 기록 블록).**
