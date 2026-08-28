# 설계 문서 #22 — Egress Gateway·Credential·Commit-Proof 계약 (2026-07-26, v1.1)

> ADR-002-013 (Egress Gateway, Credential, Route, and Commit-Proof Security — "EGRESS")를
> Phase 1(EV-L1) 설계 계약으로 실현한다. **이 문서는 시리즈에서 가장 얇은 L1 표면**이며
> (register L1-floor 2행), 따라서 **최대 위험은 over-realization**이다 — 런타임 보안(암호
> 검증·서명·quorum consensus·bypass 저항·credential custody·route confinement·rotation·
> failover·compromise)을 L1으로 오주장하지 않는다. L1은 **좌표·구조·체인·generation 판정**만
> 저작하고, cryptographic validity·quorum durability·bypass resistance는 전부 **주입
> verified-flag** 또는 **+Security 런타임**으로 이연한다.
>
> **비준 기록: 2026-07-26 운영자 위임 자동 비준(v1.1; 2026-07-25 지시 — 독립 비평 리뷰 REVISE
> [CRITICAL 0·MAJOR 2·MINOR 3]의 minimal edit set 전량 반영·오케스트레이터 검증 후 집행. 판단
> 지점: `tos.egress` 명명·edge 0·over-realization 경계[암호=주입 verified-flag]·signer dedup
> 해석 B[fail-closed] 채택. 효력: `tos/src/tos/egress/` Phase 1[EV-L1] 착수).** 본 문서는 tos-spec을 수정하지 않으며 어떤
> EGRESS-EV/acceptance/비준도 선언하지 않는다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. **패키지 명명** `tos.egress`(register prefix `EGRESS` 소문자 1:1·저마찰 명명; §0.4a).
2. **핵심 아키텍처 판정** — **rcl = ADR-002-012 Commit Proof(quorum commitment 좌표) 소유;
   EGRESS = Quorum Commit Certificate(QCC — egress-boundary aggregating 아티팩트) 소유·구조
   검증**(§0.4b·§3.5 최대 경계·재저작 금지). ADR §5.7 line 129 verbatim: "The bare ADR-002-012
   Commit Proof is necessary but not sufficient at final egress; the full Quorum Commit
   Certificate claim set in §11.1 SHALL be satisfied." ⇒ rcl가 quorum 커밋을, EGRESS가 그 위의
   §11.1 claim-set 구조 완전성·좌표 currency·threshold shape을 판정.
3. **EV 3분류(행별 정직)** — **core(L1-floor) 2행 {EGRESS-EV-004 QCC Validation, -005 Replay/
   Substitution}** / **predicate-only 1행 {EGRESS-EV-001 Credential·Route Inventory}** /
   **not-Phase-1 10행 {-002·-003·-006·-007·-008·-009·-010·-011·-012·-013}**. **닫는 EGRESS-EV
   = 0건**(§1). "EV-L1-complete 주장 금지".
4. **중심 L1 술어(§5)** — `quorum_commit_certificate_structurally_complete`·`quorum_
   coordinates_current`·`quorum_threshold_structurally_met`·`evidence_receipt_is_not_quorum_
   proof`(EV-004) + `replay_or_substitution_detected`·`capability_and_permit_single_use`·
   `exact_binding_holds`(EV-005). 전부 순수·fail-closed·전 서명/암호/consensus는 주입
   verified-flag.
5. **over-realization 경계 명시(§1·§6)** — cryptographic validity·quorum consensus·durability·
   bypass resistance·credential custody·route/env enforcement·rotation/failover/compromise
   runtime은 **전부 +Security**. L1은 구조 완전성·좌표 등치/currency·distinct-count-over-
   injected-flags·`classify_record_pair` replay/substitution·single-use·monotonic non-revival
   state-machine 판정만.
6. **소유권/seam 분할표(§3.5)** — rcl(commit-proof 좌표·`claim_capability`·`TransmissionCapability`
   재저작 금지)·ioc(command/conformance 재저작 금지)·evidence(commit-receipt/anchor/
   `SegmentCommitmentScheme` 재저작 금지)·capsule(Bindings 체인 재저작 금지)·venue/iap/capsule
   (egress-currentness 선례 — 소유 vs 소비)·brokercap(§18 profile)·protective(§17 lease)·recon
   (§16 external activity)·authority(epoch/generation)·liveauth(Live Authorization). **sibling
   edge 0**(§3.4).
7. **선제 봉합** — ∅ 양방향·집합 양방향·truthy-sentinel 구조 봉인(`__bool__ ⇒ TypeError`)·
   all-false egress authority·malformed-model 자기방어(§2.3·#20 상속)·금지 동사 canary(§4).

### 0.2 하지 않는 것 (경계·NO 목록)

- **암호·서명·quorum consensus 검증 재구현 금지.** §11.2 step 3-5(quorum sufficient·signer
   eligibility·revoked/removed/duplicated/stale signer 거부)의 **실제 암호 검증**은 +Security.
   L1은 **주입된 `signer_eligible_verified`·`signer_signature_verified` bool 위**의 distinct-
   count-≥-N 구조 판정만.
- **rcl commit-proof·`claim_capability`·`TransmissionCapability`·`writer_fenced`·
   `AuthoritativeSnapshot` 재저작 금지**(§3.5). EGRESS는 이들의 좌표/verdict를 주입 소비.
- **ioc `derived_command_conformance`·`mutation_fence_holds` 재저작 금지**(§3.5; v1.1 MAJOR-1 —
  "proof_binds_command"는 phantom, 실재 함수는 `mutation_fence_holds`). §11.2 step 18
   actual-outbound equivalence는 ioc verdict 주입 소비.
- **evidence `EvidenceCommitReceipt`·`SegmentCommitmentScheme`·`IntegrityAnchor` 재저작 금지**
   (§3.5). commit receipt ≠ QCC(§0.4d·§21.4).
- **credential custody·route confinement·network enforcement·bypass 저항 구현 금지**(§9/§10 —
   전부 +Security 런타임·EGRESS-EV-002/003 not-Phase-1).
- **rotation·failover·compromise·degraded protective·OOB containment 런타임 구현 금지**(§14-§17 —
   EGRESS-EV-008/009/010/011/013 not-Phase-1).
- **수치 하드코딩 금지**(§8) — `B_egress_hard_fence`·`B_capability_claim_to_send`·`B_revocation_
   to_egress`·`MAX_egress_currentness_proof_age_ms` 등 전부 Profile INSTANCE 측정·주입.
- **CUR(024)/SCI(029)/PTF(030)/RLP(025)/WDR(026)/NT(010) 코드 인용 금지**(미착지 상류 —
   ADR 원문만·verdict 주입·§0.4f phantom 봉합).
- **EV/acceptance/비준 선언 금지**(EV·acceptance는 미선언; 문서 비준 자체는 운영자 위임 자동 비준 v1.1).
- tos-spec 수정 금지·기존 docs/plans 무수정·세션 B 미비준 문서(NT #21) 인용 금지.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.egress`는 **순수 모델·술어 패키지**다: `pydantic` + stdlib + `tos.canonical`(digest
substrate) + `tos.ordering`(generation 순서)만 import. `shared.*`·`services.*`·`cli.*`·
`numpy`/`pandas`/`yaml`·`os.environ`·동적 escape(`exec`/`eval`/`importlib`/`__import__`)
**전면 부재**. **형제 tos 패키지(rcl·ioc·evidence·capsule·venue·iap·are·afg·sbr·hag·
liveauth·protective·recon·brokercap·authority·orthostate·spg·dsl·time·replacement + 미래
nt/cur/sci/ptf) 전부 import 부재** — 형제 상호작용은 **주입 scalar/digest/bool/verdict/
enum-token**으로만(sibling edge 0·§3.4). clock·network·egress·persistence 미접근. §7.1이
import-closure를 allowlist(`closure ⊆ {canonical, ordering, egress}`)로 강제하고 `tos-firewall`
required check와 함께 green이어야 본 선언이 능동 성립.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 명명 = `tos.egress` (저마찰·근거 3중).** HAG(#20)와 동형으로 경쟁이 약한 명명이다.

- **선택(권장) `tos.egress`** — 근거 3중:
  1. **register prefix 1:1**: 시리즈가 `EGRESS-INV`/`EGRESS-AC`/`EGRESS-EV`를 사용(register
     실측 csv line 149-160·371·ADR §6/§23). terse-lowercase 관행(rcl·spg·iap·hag·are·ioc·
     afg·sbr — 전부 register prefix lowercase; 그리고 descriptive full-word도 자연스러우면
     사용: liveauth·brokercap·orthostate·protective·replacement)과 정합. `egress`는 register
     prefix를 그대로 소문자화한 head-noun.
  2. **`tos.authority` 류 충돌 없음**: `egress`는 미점유(현 21+패키지 실측 — afg·are·authority·
     brokercap·canonical·capsule·dsl·evidence·hag·iap·ioc·liveauth·ordering·orthostate·
     protective·rcl·recon·replacement·sbr·spg·time·venue). 충돌 회피용 축약 불요.
  3. **seam 토큰 정합**: 도메인 아티팩트명이 이미 형제 코드에 고정 — capsule `capsule.py:167`
     `egress_request_digest`·rcl `records.py:249` `TransmissionCapability`·venue/iap/capsule
     `egress_currentness_*`. `tos.egress` 명명은 이 앵커와 정합.
- **runner-up `tos.qcc`(기각)** — "Quorum Commit Certificate"만 포착·§8 generation/§10 route/
   §13 monotonic-denial 등 EGRESS의 다른 축을 배제. **기각**: EGRESS는 QCC 검증 이상(egress
   generation·exact binding·restrictive denial). `tos.egr`(불필요 축약·기각). **§10.2 운영자
   판단 지점**: `tos.egress`(register-prefix·head-noun) 채택. naming은 load-bearing 아님
   (§7.1 allowlist가 미래 형제 자동 배제).

**(b) rcl = ADR-002-012 Commit Proof(quorum commitment) 소유; EGRESS = Quorum Commit
Certificate(QCC) 소유·구조 검증 (본 문서 최대 판정·재저작 금지 경계).** 이것이 본 계약의
**핵심 아키텍처 결정**이다.

- **결정적 ADR 문언(2층 분리)**: ADR §5.7 line 127-129 verbatim: "It may use individual
   signatures, an aggregate signature, or another reviewed quorum-verifiable construction, but
   **SHALL NOT reduce to one leader signature, local receipt, cache entry, or projection.**
   Where this ADR's body says 'Commit Proof'... it means the Quorum Commit Certificate defined
   here — **the egress-boundary artifact that carries the ADR-002-012 Commit Proof as one of
   its bound claims. The bare ADR-002-012 Commit Proof is necessary but not sufficient at final
   egress; the full Quorum Commit Certificate claim set in §11.1 SHALL be satisfied.**" ⇒
   **2층 아티팩트**: (1) ADR-002-012 Commit Proof = quorum commitment 좌표 = **rcl 소유**;
   (2) QCC = egress-boundary aggregating 아티팩트(commit proof + §11.1 전 sibling generation/
   digest binding + egress generation + signer 좌표) = **EGRESS 소유**.
- **실측 사실(rcl 코드가 commit-proof 좌표를 이미 소유)**: rcl(설계 #5·ADR-002-002, 착지)은
   ADR-002-012 quorum commitment 좌표를 **이미 실현**:
  - `AuthoritativeSnapshot`(`records.py:428`, `_REQUIRED_COVERED` = `cluster_identity`·
     `capacity_domain`·`membership_generation`·`restore_generation`·`writer_epoch`·`last_
     included_revision`·`profile_generation`·`hard_safety_envelope_generation`) — cluster/
     domain/membership/restore/writer/revision **좌표**.
  - `RclTransitionRecord`(`records.py:191`, `previous_revision`·`new_revision`) — committed log
     revision + parent.
  - `LedgerCommandRecord`(`records.py:119`) — command identity + canonical command digest.
  - `TransmissionCapability`(`records.py:249`, "only a committed `ClaimCapabilityAndMarkSend
     Started` consumes its... bound_reservation_revision, worst_case_effect") + `capability_
     authorization_valid`(`predicates.py:627`) + `claim_capability`(`predicates.py:677` —
     nonce **single-use** + replay 탐지 `predicates.py:698-703`) + `CLAIM_CAPABILITY_AND_MARK_
     SEND_STARTED`(`vocabulary.py:54`) — ADR-002-007/012 claim-to-send.
  - `writer_fenced`(`predicates.py:507-552`, **any-None ⇒ fail-closed**·stale writer/removed
     voter/stale CAS) + `partition_verdict`(`predicates.py:711`, quorum None/False ⇒ 전
     denied·`automatic_rearm_denied=True` **무조건**).
- **⇒ EGRESS가 소유하는 잔여(rcl가 이연한 것)** = **QCC egress-boundary aggregation + 구조
   검증**:
  1. **§11.1 QCC claim-set 구조 완전성**(EGRESS-EV-004) — QCC가 §11.1의 전 필수 claim(rcl
     commit-proof 좌표 + 018/019/020/021/022/023/024/029/030 sibling generation/digest +
     egress generation + active principal + credential/session/route/trust-bundle generation +
     signer 좌표)을 **구조적으로 완전히 carry**하는지. `None`/누락 ⇒ fail-closed(§5.1).
  2. **§11.2 step 1-7 좌표 currency(구조 부분)** — QCC-carried 좌표가 **주입된 현재 committed
     값과 등치**인지(stale/mismatch ⇒ 거부). rcl `writer_fenced`를 **재저작하지 않고** carried-
     vs-current **등치**만 판정(§5.2). 실제 quorum consensus 검증(step 3의 durability)은
     +Security.
  3. **§11.2 step 3-5 threshold shape** — distinct signer 좌표 중 `eligible_verified is True`
     AND `signature_verified is True`가 **≥ 주입 quorum N**인지(§5.3). "one leader signature
     insufficient"(§11.2 line 351)를 **구조적으로** 잡는 count 판정. 서명/eligibility 자체는
     주입 verified-flag(+Security).
- **재저작 금지 경계(엄격)**: EGRESS는 rcl `writer_fenced`·`capability_authorization_valid`·
   `claim_capability`·`TransmissionCapability`·`AuthoritativeSnapshot`·`partition_verdict`를
   **재저작·import하지 않는다**. 런타임에서 rcl가 **먼저** commit-proof 좌표를 산출하고, 그
   좌표가 EGRESS QCC의 bound claim으로 **주입**된다(계층 상하). **EGRESS-EV-004 L1 잔여 =
   aggregation-completeness + coordinate-currency + threshold-shape의 저작**이지 quorum
   commitment 재구현이 아니다(§5.1-5.3). **리뷰어 공격 지점(§10.2)**: "EGRESS QCC가 rcl commit
   proof를 중복" — 반론: 축이 다름(rcl=quorum 커밋 좌표 *생산*; EGRESS=egress-boundary
   §11.1 claim-set *aggregation·구조 검증*); ADR §5.7 line 129가 "bare Commit Proof necessary
   but not sufficient... full QCC claim set SHALL be satisfied"로 2층을 **명시**.

**(c) ioc = command/conformance 소유 (§11.2 step 18 actual-outbound equivalence 경계).**
**실측 충돌 후보**: ioc(설계 #14, 착지)가 `CanonicalBrokerCommand`(`records.py:301`)·
`OrderConformanceProof`(`records.py:357`, `command_digest`·`effect_digest`·`conformance_result`)·
`mutation_fence_holds`(`predicates.py:492`; 본문 `proof.command_digest == command.canonical_digest` — v1.1 MAJOR-1 정정: :502는 그 docstring 줄)·
`derived_command_conformance`(`predicates.py:527`)를 **이미 소유**한다.

- **판정: 축이 다르며 ioc가 conformance-decision kernel**. ioc `__init__.py:14` verbatim:
   "conformance-decision kernel, **not a serializer / signer / egress engine**". ⇒ ioc는
   intent→command exact-match conformance를, EGRESS는 그 conformance verdict를 **egress
   boundary에서 소비**해 exact-binding에 편입.
- **경계 분할**: **ioc 소유** = §11.2 step 18의 "reconstruct the exact actual outbound
   representation... compare its canonical semantics, digest, endpoint, action, account, route,
   and economic effect to the ADR-002-020 command and proof"의 **command↔proof conformance
   decision**(`derived_command_conformance` verdict). **EGRESS 소유** = 그 verdict를 소비하고
   egress-scope 좌표(endpoint·account·env·credential-gen·session·egress-gen·principal)의
   **등치**를 추가 판정(§5.7 `exact_binding_holds`).
- **⇒ EGRESS는 `derived_command_conformance`·`mutation_fence_holds`를 재저작·import하지 않는다.**
   ioc verdict(`is ConformanceResult.CONFORMANT`)를 주입 소비. **리뷰어 공격 지점(§10.2)**:
   "EGRESS exact-binding이 IOC conformance 재저작" — 반론: ioc는 command↔proof 축, EGRESS는
   egress-scope 좌표(route/session/credential-gen) 축·defense-in-depth(venue의 ioc-conformance
   vs venue-admissibility 다층 방어 동형).

**(d) evidence = commit-receipt/anchor 소유; QCC ≠ evidence receipt (§21.4 재저작 금지 경계).**
**실측 충돌 후보**: evidence(설계 #4·ADR-002-016, 착지)가 `EvidenceCommitReceipt`(`receipt.py:59`)·
`SegmentCommitmentScheme`(`ledger.py:82`, Protocol)·`IntegrityAnchor`·`EvidenceSegment`를
**이미 소유**한다. §11 "Commit-Proof Format"이 evidence commit receipt와 표면상 인접이라
**재저작 함정**이다.

- **판정: 축이 다르며 evidence 코드가 스스로 QCC 자격 부재를 증언**. evidence `receipt.py`
   실측: `ReceiptVerificationStatus`는 `UNVERIFIED`만 Phase-1이 정직하게 보유(`receipt.py:50-51(모듈 자기한정 :11-12)`
   verbatim: "`UNVERIFIED` is the only state a pure Phase-1 model can honestly hold — `VERIFIED`
   (durable acceptance) requires an out-of-scope durable store"); `EvidenceCommitReceipt`은
   **단일 `receipt_signer_identity`·`receipt_signature`**(`receipt.py:141/143` — leader 서명
   1개)·**all-false authority**(`creates_authority`·`permits_broker_transmission` False).
- **⇒ evidence commit receipt는 구조적으로 QCC일 수 없다**: (i) 단일 signer(≠ quorum
   threshold), (ii) UNVERIFIED(≠ durable quorum acceptance), (iii) all-false(transmission
   미허가). 이것이 ADR §21.4 line 560-562 "Leader Receipt as Commit Proof... Rejected because
   leader belief, local persistence, or signature does not prove quorum commitment" + §11.2
   line 351 "One leader signature, successful RPC, database primary response, **local journal
   entry, cached proof, event, projection, or audit record is insufficient**" + §2 line 49 "a
   durable local journal being treated as equivalent to ADR-002-012 quorum commit"의 **정확한
   실현 지점**.
- **경계 분할**: **evidence 소유** = commit-receipt/anchor/segment-commitment = **evidence
   durability substrate**(pre-effect·`SEND_STARTED` 증거의 durable commit, ADR-002-016). **EGRESS
   소유** = QCC = **quorum-acceptance proof at egress**. 두 축은 직교. EGRESS는 evidence
   receipt를 QCC로 **대체 거부**하는 `evidence_receipt_is_not_quorum_proof` 술어를 로컬 저작
   (§5.4) — evidence `EvidenceCommitReceipt`·`SegmentCommitmentScheme` **재저작·import 안 함**.
   **리뷰어 공격 지점(§10.2)**: "§11 Commit-Proof = evidence commit receipt 중복" — 반론:
   evidence `receipt.py:50-51(모듈 자기한정 :11-12)`가 UNVERIFIED/durability 축을 스스로 한정·QCC는 quorum-multi-
   signer 축·§21.4가 leader receipt를 **명시 기각**·EGRESS는 evidence receipt를 QCC 대체
   시도로 **거부**(같은 방향 아님).

**(e) capsule = Bindings 체인 소유 (§11.1/EGRESS-INV-004 exact-binding 체인 종단).** **실측**:
capsule(설계 #2·CII·ADR-002-018, 착지)의 `Bindings`(`capsule.py:153`)가 **downstream binding 체인
전체**를 이미 모델링: `proposal_id`·`approval_request_id`·`intent_id`·`capacity_request_id`·
`live_authorization_id`·`transmission_capability_id`·`commit_proof_id`·`egress_request_digest`
(`capsule.py:160-167`). **`egress_request_digest`가 체인 종단**이다.

- **판정: 방향이 다르다(forward-reference vs terminal-validation)**. capsule `Bindings`은
   **forward reference**("Forward references to downstream chain artifacts; Phase B
   authoritative binding is out of scope... these stay `None` in Phase 1", `capsule.py:156-157`).
   capsule = capsule→egress **선언 체인**(forward). EGRESS = 실제 QCC/request가 그 선언 체인과
   **등치**인지 **terminal 검증**(backward).
- **⇒ EGRESS는 capsule `Bindings`을 재저작·import하지 않는다.** EGRESS `exact_binding_holds`
   (§5.7)는 QCC-carried `commit_proof_id`·`transmission_capability_id`·`egress_request_digest`가
   주입된 capsule Bindings 좌표와 **등치**인지 판정(주입 digest 소비). **리뷰어 공격 지점
   (§10.2)**: "exact-binding이 capsule Bindings 중복" — 반론: capsule=forward-reference(Phase B
   None), EGRESS=terminal-equivalence(실제 QCC vs 선언 Bindings)·다른 방향.

**(f) currentness aggregation — CUR/venue/iap/capsule 경계 (미착지 상류·phantom 봉합).**
**실측**: venue `egress_currentness_active`+`stale_decision_rejected_at_egress`(`predicates.py:493/
529`, VTG-EV-007)·iap `active_egress_currentness`(`predicates.py:578`, IAP-EV-008)·capsule
`egress_currentness_ok`(`predicates.py:656`, CII-EV-009) — **각 형제가 자기 decision의 egress-
staleness predicate-only 슬라이스를 이미 저작**했다.

- **판정: EGRESS는 aggregation-consumer·CUR가 진짜 aggregator(미착지)**. §11.2 step 14 line 344
   verbatim: "verify under ADR-002-024 that one **complete Safety Currentness Vector** satisfies
   every restrictive floor... and that the local restrictive latch is positively established as
   `CLEAR`". **ADR-002-024(CUR)가 complete-vector aggregation 소유** — 그러나 **CUR(`tos.cur`)는
   미착지**(실측: `tos/src/tos/` 하 `cur`/`sci`/`ptf`/`nt` 부재). ⇒ EGRESS는 "complete
   Currentness Vector satisfied" 및 "restrictive latch CLEAR"를 **주입 verdict**로 소비
   (`RestrictiveLatchState is CLEAR`·§2.2·§5) — **CUR 코드 인용 없음**(phantom 봉합).
- **⇒ EGRESS는 venue/iap/capsule egress-currentness 술어를 재저작하지 않는다** — 각 형제가
   자기 축 소유. EGRESS는 QCC의 §11.1 "single-use Egress Currentness Proof identity/digest"
   claim의 **구조 존재**만 판정(주입). **리뷰어 공격 지점(§10.2)**: "EGRESS가 venue/iap/capsule/
   CUR egress-currentness 중복" — 반론: 각 형제=자기 decision staleness, CUR=complete-vector
   aggregation(미착지·주입), EGRESS=QCC claim-set의 currentness-proof **구조 존재** 판정만.

**(g) brokercap(§18 profile)·protective(§17 lease)·recon(§16 external)·authority(epoch)·
liveauth(Live Authorization) 경계 (전부 verdict 주입 소비).**

- **brokercap(§18)**: `credential_scope_declared_ok`(`predicates.py:675`)·`session_type`/
   `credential_scope`/`session_scope` profile 필드 소유. **decisive 코드 증언**: brokercap
   `predicates.py:684` verbatim: "The runtime credential-fencing / **egress-bypass resistance
   is +Security (ADR-002-013)**". ⇒ brokercap가 §18 profile 필드를, EGRESS/+Security가 egress-
   bypass 저항을 소유(brokercap가 EGRESS로 명시 이연). EGRESS는 profile-declared verdict 주입
   소비·`UNKNOWN`/weaker ⇒ live scope 축소(§18 line 496·fail-closed).
- **protective(§17)**: `ProtectiveLeaseAdmissibilityScope`(`records.py:111`)·`GuaranteeLevel`
   {PRIORITIZED_ONLY/BEST_EFFORT/UNAVAILABLE}(`vocabulary.py:39`)·"rcl's `ProtectiveLease`
   aggregation... authority's `lease_scope_exclusive` verdict"(`predicates.py:840-842`) 소유.
   ⇒ degraded protective egress exclusivity(EGRESS-EV-011)는 protective+rcl+authority 축·
   **not-Phase-1(+Broker+Security)**. EGRESS는 lease-exclusivity verdict 주입 소비.
- **recon(§16)**: external/unattributed activity(`vocabulary.py:82` Row 5·`records.py:40`) 소유.
   ⇒ EGRESS-INV-013 "external activity ≠ TOS authority"(EGRESS-EV-012)는 recon 축. EGRESS는
   external-activity를 **all-false egress authority**로 판정(compliant path 재라벨 거부·§6b).
- **authority(ADR-002-003)**: `authority_epoch_current`/`authority_epoch_fenced`/`recovery_
   generation_revives_nothing`(`predicates.py:787`)/`GenerationVector` 소유. EGRESS는 epoch/
   generation verdict 주입 소비·`recovery_generation_revives_nothing`을 **monotonic-denial
   non-revival 선례**로 인용(§6b·재저작 아님).
- **liveauth(ADR-002-007)**: `LiveAuthorization`·`LiveAuthorizationScope`·`scope_covers`·
   `no_automatic_rearm`(`predicates.py:606`) 소유. liveauth `__init__.py:10` verbatim:
   "implements **no** egress / fenced single-use capability". ⇒ **transmission capability는
   liveauth 아니라 rcl 소유**(§0.4b — 사전 지도 정정). EGRESS는 Live Authorization verdict 주입
   소비.

**(h) 앵커 규약 — EGRESS-INV/AC/EV 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-013은 자체
시리즈 **`EGRESS-INV-001..014`(§6 line 143-197, 14종)·`EGRESS-AC-001..012`(§23 line 622-633,
12종)·`EGRESS-EV-001..013`(register csv line 149-160·371, 13행)**를 정의한다. §23 preamble(line
618 verbatim): "The following cases are mandatory and map one-to-one to `EGRESS-EV-001` through
`EGRESS-EV-012`. Written cases are not completed evidence." ⇒ **EGRESS-AC는 12행이며 EGRESS-
EV-001..012에만 1:1 매핑**; EGRESS-EV-013(Out-of-Band Containment, csv line 371)은 후행-등재
row로 §23 AC가 없다. 본 계약은 모델 불변식·술어를 **`EGRESS-INV-###`/`EGRESS-AC-###`/`EGRESS-
EV-###`/§-clause/`SAFE-###`(§24 traceability line 641-649)**에 앵커하고 **새 시리즈를 창작하지
않는다**. #12–#20 동형.

**(i) EGRESS-EV = core 2 + predicate-only 1 + not-Phase-1 10, 닫는 EGRESS-EV = 0건 (over-
realization 최대 위험).** register 최소-레벨 histogram(csv line 149-160·371): **`EV-L1/3+
Security` ×2**(004·005 — L1-floor **core**)·**`EV-L2/3+Security` ×1**(001 — **predicate-only**)·
**`EV-L3+Security` ×5**(002·003·006·007·009)·**`EV-L3/5+Security` ×3**(008·010·012)·**`EV-L3/5+
Broker+Security` ×2**(011·013). ⇒ **L1 슬라이스 보유 2행 = core**(task 재실측 일치)·predicate-
only 1행·**not-Phase-1 10행(L3+/L5+·전부 +Security, 물리 bypass·rotation·failover·compromise·
external·OOB는 런타임 보안)**. **닫는 EGRESS-EV = 0건**. **over-realization 봉합(#7 under-
realization의 반대)**: 이 문서는 시리즈에서 **가장 얇은 L1 표면**이므로 런타임 보안을 L1로
오주장하는 것이 최대 위험 — cryptographic validity·quorum consensus·bypass resistance는 전부
주입 verified-flag/+Security로 정직 이연(§1·§6). **truthy-sentinel 규율(#13·#14 M1 교훈을
처음부터)**: `EgressAdmission`{ADMIT/DENY}·`CommitProofValidity`{VALID/INVALID/UNKNOWN}·
`RestrictiveLatchState`{CLEAR/DENY_LATCHED} 전부 `_NonTruthyStrEnum`(`__bool__ ⇒ TypeError`) —
DENY/INVALID/DENY_LATCHED truthy fail-open 방지(§2.2·§4.7).

---

## 1. 범위 매핑 — ADR-002-013 조항별 EV-L1 도달성 (닫는 EGRESS-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine
exploration, model checking, property-based testing, deterministic simulation). **EV-L2 =
Component Fault Test**, **EV-L3 = Integration/Adversarial**, **EV-L5 = 확장 adversarial/
red-team**, **+Security = 독립 security-boundary assessment**(identity/credential/authorization/
fencing/bypass), **+Broker = broker-capability 실측**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — EGRESS-EV core 2행(시리즈 최소 core tier)**: register 실측 histogram:
> **core(L1-floor) 2행 = {004 Quorum Commit Certificate Validation [`EV-L1/3+Security`,
> csv:152]·005 Proof, Capability, and Request Replay or Substitution [`EV-L1/3+Security`,
> csv:153]}**. **predicate-only(≥ L2) 1행 = {001 Credential and Route Authority Inventory
> [`EV-L2/3+Security`, csv:149]}**. **not-Phase-1(L3+/L5+) 10행 = {002 Direct/Stale-Principal
> Bypass·003 Env/Scope/Endpoint/Route Substitution [`EV-L3+Security`, csv:150-151]·006
> Downstream Intermediary/Reconnect·007 Restrictive Race·009 Failover/Rollback [`EV-L3+
> Security`, csv:154-155·157]·008 Deny-First Rotation·010 Compromise/Unknown Revocation·012
> Manual Authority/Recovery [`EV-L3/5+Security`, csv:156·158·160]·011 Degraded Protective
> Exclusivity·013 Out-of-Band Containment [`EV-L3/5+Broker+Security`, csv:159·371]}**.
> **+Security 13/13**(전 행)·**닫는 EGRESS-EV = 0건**.
>
> **결정적 사실 2 — authoring ≠ acceptance·over-realization 최대 위험(닫는 EGRESS-EV = 0건)**:
> Phase 1은 core 2행의 **L1-decidable 구조/좌표 predicate substrate**를 저작하나 **어떤
> EGRESS-EV도 닫지 않는다.** (a) core 2행조차 `/3`(integration/adversarial)·+Security(quorum
> consensus·crypto·bypass) 잔여, (b) predicate-only 1행은 최소 ≥ L2(inventory enumeration),
> (c) not-Phase-1 10행은 L3+/L5+ 런타임 보안, (d) VER-002-001 §5 "Registration is not
> execution"·ADR §23 line 618 "Written cases are not completed evidence"·§26 line 708
> "Authorship... does not satisfy this gate". ⇒ **"EV-L1-complete 주장 금지"**(#12–#20 §1 규율
> 상속). Owner/Reviewer는 register상 TBD·status NOT_IMPLEMENTED(전 13행).

**규율 태그(모든 주장에 부착)**: "**structural/coordinate predicate substrate only; EGRESS-
EV-001..013 전부 NOT_IMPLEMENTED — core 2행(004·005)은 `/3`·+Security(quorum consensus·
cryptographic signature·bypass resistance) 통합·adversarial·독립 security review 대기,
predicate-only 1행(001)은 inventory-enumeration L2·+Security 대기, not-Phase-1 10행은 런타임
보안(+Security/+Broker). EV-L1-complete 주장 금지·cryptographic validity는 주입 verified-flag·
L1은 구조/체인/generation 판정만.**"

**EGRESS-EV core 2행 ↔ AC(1:1) ↔ ADR 조항 매핑(실측)**:

| EGRESS-EV | register 제목(verbatim, csv line) | 최소 레벨 | EGRESS-AC(1:1) | ADR 조항 앵커 | L1 substrate 술어(§5) |
|---|---|---|---|---|---|
| **004** | Quorum Commit Certificate Validation (152) | `EV-L1/3+Security` | AC-004(line 625) | §11 Commit-Proof·EGRESS-INV-003 | `quorum_commit_certificate_structurally_complete`+`quorum_coordinates_current`+`quorum_threshold_structurally_met`+`evidence_receipt_is_not_quorum_proof`(§5.1-5.4 — 노른자) |
| **005** | Proof, Capability, and Request Replay or Substitution (153) | `EV-L1/3+Security` | AC-005(line 626) | §11/§12·EGRESS-INV-004 | `replay_or_substitution_detected`+`capability_and_permit_single_use`+`exact_binding_holds`(§5.5-5.7) |

**ADR-002-013 조항 → Phase-1 분류(core / predicate-only / not-Phase-1)**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | EGRESS-EV |
|---|---|---|---|---|
| **§11.1/§11.2 step 1-7** (line 297-337) | QCC claim-set·quorum coordinate 검증 | **core (L1 슬라이스)** | `quorum_commit_certificate_structurally_complete`(§5.1)+`quorum_coordinates_current`(§5.2) — §11.1 전 필수 claim 구조 완전성·carried-vs-current 좌표 등치. rcl commit-proof 좌표 **주입 소비**(재저작 금지·§3.5). **over-realization 경계**: actual quorum consensus/durability(step 3)는 +Security. | **004** |
| **§11.2 step 3-5·line 351** (line 333-335·351) | quorum threshold shape·leader-receipt 거부 | **core (L1 슬라이스)** | `quorum_threshold_structurally_met`(§5.3)+`evidence_receipt_is_not_quorum_proof`(§5.4) — distinct signer(eligible+signed) ≥ N·single-leader 거부. **서명/eligibility 주입 verified-flag**(+Security). §21.4 leader-receipt 기각의 구조 실현. | **004** |
| **§11/§12·§11.2 step 17-18** (line 347-348·EGRESS-INV-004 line 155) | replay/substitution·single-use·exact binding | **core (L1 슬라이스)** | `replay_or_substitution_detected`(§5.5·`classify_record_pair`)+`capability_and_permit_single_use`(§5.6·rcl `claim_capability` 소비)+`exact_binding_holds`(§5.7·ioc conformance+capsule Bindings 주입). **over-realization 경계**: actual byte-level reconstruction(step 18)·route/session 실 enforcement는 +Security. | **005** |
| **§6/§9/§10** (EGRESS-INV-002 line 147·§9.1 line 249) | credential·route authority inventory | **predicate-only (≥ L2)** | `credential_route_authority_disjoint`(§6.1) — 주입 inventory 위 "no outside-boundary principal has usable-credential AND route". 실 inventory enumeration(hidden/recovery/portal/CI credential)은 L2+. 최소 `EV-L2/3+Security`. | **001** |
| **§8** (line 219-243) | egress generation·stale-principal | **not-Phase-1 (thin model property)** | `egress_generation_monotonic`+`stale_principal_structurally_rejected`(§6.2) — QCC egress-gen/principal claim에 편입되는 model property. 실 bypass 저항(credential custody+route confinement+network)은 +Security. | **002** |
| **§10/EGRESS-INV-004** (line 275-291) | env/scope/endpoint/route substitution | **not-Phase-1 (coordinate-equality 공유)** | 좌표 등치 부분은 `exact_binding_holds`(§5.7)와 공유. 실 route/env confinement·network enforcement는 +Security. | **003** |
| **§12** (line 371-376) | downstream intermediary·reconnect | **not-Phase-1 (reconnect-non-revival isomorphic)** | reconnect ↛ revival model property(§6.3·§13 동형). 실 topology/queue/reconnect 런타임은 +Security. | **006** |
| **§13** (line 380-395) | restrictive race·monotonic denial | **not-Phase-1 (monotonic-denial model property)** | `monotonic_denial_no_revival`(§6.3) — DENY_LATCHED ↛ CLEAR(authority `recovery_generation_revives_nothing` 동형). 실 race timing·`B_*_to_egress` bound은 +Security. | **007** |
| **§14** (line 399-418) | deny-first credential/trust rotation | **not-Phase-1 (deny-first ordering model)** | 8-step deny-first 순서 model(§6b). 실 rotation·hard fence 메커니즘은 +Security/+L5. | **008** |
| **§15** (line 422-439) | failover·rollback·removed-principal | **not-Phase-1 (rollback=new-generation non-revival)** | "rollback is new Egress Generation"(§15 line 437) non-revival model(§6b). 실 failover 런타임은 +Security. | **009** |
| **§16** (line 443-457) | credential compromise·unknown revocation | **not-Phase-1 (unknown-is-denial model)** | EGRESS-INV-011 "unknown... denies new risk, preserves conservative capacity" model(§6b). 실 compromise detection/rotation은 +Security/+L5. | **010** |
| **§17** (line 461-474) | degraded protective egress exclusivity | **not-Phase-1 (protective 경계)** | protective `ProtectiveLeaseAdmissibilityScope`+rcl `ProtectiveLease`+authority `lease_scope_exclusive` **소유**(§0.4g·§3.5). EGRESS는 verdict 주입 소비. `EV-L3/5+Broker+Security`. | **011** |
| **§16** (line 443-457) | manual authority·recovery cannot re-arm | **not-Phase-1 (no-auto-rearm + external all-false)** | `no_automatic_rearm`(liveauth 동형)+external-activity all-false egress authority(§6b·recon 경계). 실 external detection/reconciliation은 +Security/+L5. | **012** |
| **§14/§16** (line 414·443) | out-of-band containment (defective/compromised egress point) | **not-Phase-1 (pure seam)** | OOB containment 런타임(`B_controlled_shutdown_hard_fence` VP line 436). L1 model property 없음 — pure seam. `EV-L3/5+Broker+Security`. | **013** |
| **§7 SoD·§18 profile·§19 evidence·§20 failure·§25 open Q·§26 gate** | authority 분리·profile·metrics·수치·acceptance | **not-Phase-1 (Phase-0/INSTANCE·런타임)** | 제품·broker·network·수치·acceptance는 §9.2 Phase-0. §7 SoD는 hag `separation_of_duties_satisfied`(ADR-002-015) 축. 전부 주입/+Security. | (런타임) |

---

## 2. 데이터 모델 계약

### 2.1 digest-bound / value / reference 분류

| 분류 | 모델 | 근거 |
|---|---|---|
| **digest-bound `IndependentIdArtifact`** (id ⊥ digest·§3.1) | `QuorumCommitCertificate`(§11.1 aggregating 아티팩트)·`EgressRequestRecord`(§12 exact outbound request)·`EgressGeneration`(§8)·`ActiveEgressPrincipalSet`(§8)·`ReplayObservation`(§11 replay/substitution 관측) | append-only ledger citizen — same-id/different-bytes 위조/replay를 `classify_record_pair` CRITICAL_CONFLICT로 탐지(§5.5). id는 서비스 부여(≠ `f(digest)`), digest는 §11.1/§12/§8 immutable claim cover. |
| **value (frozen, id 없음)** | `SignerCoordinate`(signer identity + 주입 `eligible_verified`/`signature_verified` bool)·`EgressCoordinateSet`(endpoint/account/env/credential-gen/session/route-gen/egress-gen/principal — exact-binding 좌표)·`CredentialRouteInventoryEntry`(principal × usable-credential-flag × route-flag × inside-boundary-flag·§6)·`CommitProofCoordinates`(주입된 rcl commit-proof 좌표 mirror — 검증 대상, rcl 재저작 아님) | id 미도출·mutate 없음. `CommitProofCoordinates`는 rcl `AuthoritativeSnapshot` 좌표를 **주입 입력**으로 받는 value(등치 판정용·§5.2). |
| **enum-token (`_NonTruthyStrEnum`)** | `EgressAdmission`{ADMIT/DENY}·`CommitProofValidity`{VALID/INVALID/UNKNOWN}·`RestrictiveLatchState`{CLEAR/DENY_LATCHED} | 어휘(§2.2). `__bool__ ⇒ TypeError`(truthy 봉인). |
| **reference (scalar/digest only, 주입)** | rcl commit-proof 좌표(cluster/domain/membership_gen/restore_gen/writer_epoch/revision/command_digest/state_digest)·ioc conformance verdict + command_digest·capsule Bindings digest(`egress_request_digest`)·venue/iap/capsule egress-currentness verdict·**CUR complete-vector verdict(미착지·주입)**·brokercap credential-scope verdict + profile digest·authority epoch/generation verdict·liveauth Live Authorization scope·protective lease-exclusivity verdict·recon external-activity 분류·evidence commit-receipt(all-false·UNVERIFIED)·018/019/020/021/022/023/**024/029/030** decision digest | 형제 소유 — 주입 scalar/digest/verdict로만 참조(§3.4/§3.5). EGRESS는 이들을 저작·import하지 않음. **024/029/030(CUR/SCI/PTF)·025/026(RLP/WDR)·010(NT)은 미착지 — ADR 원문만·코드 인용 0(phantom 봉합).** |

### 2.2 어휘 (verbatim 전사 + truthy 봉인)

**(1) `EgressAdmission` (§1/§11.2 최종 verdict, non-truthy StrEnum — 핵심 truthy 봉인).**
`ADMIT`·`DENY`. **`_NonTruthyStrEnum` 로컬 재표현**(iap `vocabulary.py:50` 동형·import 아님) —
`__bool__ ⇒ TypeError`. **근거**: `DENY`는 non-empty string이라 `if admission:` 오용이 **거부를
truthy로 오독하는 치명적 fail-open**(ADR §6 EGRESS-INV-011 line 183 "Unknown... is denial";
§11.2 line 351 "insufficient" ⇒ deny). 소비 게이트는 **`admission is EgressAdmission.ADMIT`
명시 비교 강제**(§4.7·§7 회귀). egress는 근본적으로 DENY-biased.

**(2) `CommitProofValidity` (§11.2, non-truthy StrEnum).** `VALID`·`INVALID`·`UNKNOWN`. **`_Non
TruthyStrEnum`** — ioc `ConformanceResult`(`vocabulary.py:40-72`, VALID/INVALID/**UNKNOWN을
truthy로 오독하면 catastrophic fail-open**) 동형. `UNKNOWN` ⇒ deny(ADR §6 EGRESS-INV-011·§11.2
step 2 "reject unknown security-relevant fields or ambiguous encodings" line 332). 소비:
`validity is CommitProofValidity.VALID` 명시.

**(3) `RestrictiveLatchState` (§13/§11.2 step 14, non-truthy StrEnum).** `CLEAR`·`DENY_LATCHED`.
**`_NonTruthyStrEnum`** — monotonic. §11.2 step 14 line 344 verbatim: "the local restrictive
latch is **positively established as `CLEAR`**". ⇒ **CLEAR는 positive 증명이어야**(주입
verdict·`state is RestrictiveLatchState.CLEAR` 명시; `None`/`DENY_LATCHED` ⇒ deny). §13 line 393
verbatim: "The deny state is monotonic... Cache recovery, reconnect, secret refresh, route
restoration, deployment success, or deletion of an alert cannot clear it." ⇒ 상태기계 arrow는
§6.3 술어로 판정(레코드 판정 안 함).

**(4) `SignerRole` (§11.1 quorum signer, closed StrEnum — leader-vs-quorum 축).** `QUORUM_MEMBER`·
`LEADER`. §11.2 line 351 "One leader signature... is insufficient" ⇒ **LEADER 단독은 quorum
불충족**(§5.3 threshold count에서 LEADER 단독/1인 거부). closed(ADR가 leader belief vs quorum
commitment를 §21.4에서 고정 대비).

### 2.3 아티팩트 covered + self-exclusion + malformed-model 자기방어 (설계 #4 §3.3·#20 §2.3 상속)

- 모든 digest-bound 아티팩트는 `IndependentIdArtifact`(canonical `_base.py`)를 상속 —
   `_ID_FIELD`(독립 id·digest preimage self-exclusion)·`_COVERED_FIELDS`(digest cover)·
   `_REQUIRED_COVERED`(구조 identity 최소 필수)를 선언(ioc `records.py:301/357`·rcl `records.py:428`
   선례).
- **coordinate 비붕괴(설계 #4 §4.4)**: mutable `RestrictiveLatchState`·QCC의 lifecycle 좌표는
   covered digest에 **미포함** — 정당한 전이(예: CLEAR→DENY_LATCHED)가 digest를 바꿔 same-id/
   different-bytes CRITICAL_CONFLICT로 오탐되지 않도록(rcl coordinate-non-collapse 선례). 현재
   상태는 술어에 주입·별도 append-only record.
- **malformed-model 자기방어(#20 교훈 — 처음부터)**: `QuorumCommitCertificate` `model_validator`가
   **불완전 레코드와 "complete" claim의 공존을 구조로 봉인**. §11.1의 `_REQUIRED_COVERED`
   (commit-proof 좌표·egress generation·active principal·signer 좌표 최소 집합) 중 하나라도
   `None`이면 **`ArtifactIntegrityError` at construction** — 즉 "구조적으로 완전"을 주장하면서
   필수 claim이 비는 QCC는 **애초에 구성 불가**. `quorum_commit_certificate_structurally_
   complete`(§5.1)는 validator 통과 후에도 술어 층에서 재확인(defense-in-depth·validator
   우회 `model_construct` 대비). **리뷰어 공격 지점(§10.2)**: `model_construct`로 필수 None QCC를
   만들어 complete-flag를 truthy로 통과시키는 경로 → validator + 술어 2층 봉인.
- `_REQUIRED_COVERED`는 **구조 identity/generation/digest** 필드만 — quorum N·age 같은 numeric
   bound은 제외(Phase-1 null profile 하에서 아티팩트 구성 가능하도록·§8); 누락 numeric claim은
   fail-closed(§4.7).

### 2.4 핵심 모델 필드 골격 (§ref·형제 seam·all-false)

**`QuorumCommitCertificate`(§11.1)** — egress-boundary aggregating 아티팩트. **조건부 trial
claim(v1.1 gap 보강)**: ADR §11.1 line 308이 restricted-live trial(ADR-002-025) 요청에 대해 Trial
Policy/Plan/Run/Promotion Generation·remaining envelope·abort generation을 조건부 필수 claim으로
요구 — Phase 1은 이들을 **opaque optional scalar 필드군**(`trial_claims: ... | None`)으로 수용하고
내용 검증은 RLP(-025, 미착지) 이연(§9.2 item 17). 필드(전부 주입·
검증 대상):
- **commit-proof 좌표**(주입·rcl 소유): `cluster_identity`·`capacity_domain`·`safety_cell`·
   `membership_generation`·`restore_generation`·`writer_epoch`·`committed_revision`·
   `parent_revision`·`command_identity`·`canonical_command_digest`·`resulting_state_digest`
   (§11.1 line 300-306).
- **egress 좌표**(EGRESS 소유 축): `egress_generation`·`active_egress_principal`·`credential_
   generation`·`broker_session_generation`·`route_policy_generation`·`endpoint_policy_
   generation`·`trust_bundle_generation`(§11.1 line 323-324).
- **sibling generation/digest binding**(주입·형제 소유): `recovery_evidence_package_digest`
   (sbr)·`decision_context_capsule_digest`(capsule/018)·`venue_admissibility_decision_digest`
   (venue/019)·`canonical_broker_command_digest`+`order_conformance_proof_digest`(ioc/020)·
   `aggregate_risk_decision_digest`(are/021)·`action_flow_decision_digest`+`action_flow_
   permit_id`(afg/022)·`approval_consumption_record_digest`(iap/023)·`egress_currentness_
   proof_id`(024/CUR·미착지 주입)·`release_artifact_attestation_digest`(029/SCI·미착지 주입)·
   `post_trade_obligation_generation`(030/PTF·미착지 주입)(§11.1 line 313-322).
- **signer 좌표**: `signer_coordinates: tuple[SignerCoordinate, ...]`(§11.1 line 325 "quorum
   signer identities or equivalent threshold-verification material").
- **`capability_nonce`·`action_flow_permit_nonce`**(§11.2 step 17).
- **`authority_effect: AllFalseEgressAuthority`**(§4.3 — QCC는 검증 대상이지 authority 아님).
- `_REQUIRED_COVERED` = {cluster_identity·capacity_domain·membership_generation·restore_
   generation·writer_epoch·committed_revision·canonical_command_digest·resulting_state_digest·
   egress_generation·active_egress_principal} (malformed-model 봉인·§2.3).

**`SignerCoordinate`(value·§11.1)**: `signer_identity: str | None`·`signer_role: SignerRole |
None`·`eligible_verified: bool | None`(주입 — membership generation에서 자격 검증됨·+Security)·
`signature_verified: bool | None`(주입 — 서명 검증됨·+Security). **`None` ⇒ 미검증 ⇒ count
제외(fail-closed·§5.3)**.

**`EgressRequestRecord`(§12)**: `request_id`·`request_bytes_digest`·`endpoint`·`account`·
`environment`·`action`·`method`·`side`·`quantity_digest`·`route_identity`·`credential_
generation`·`broker_session_generation`·`egress_generation`·`active_egress_principal`
(§12 line 367 "account, instrument, side, quantity, price, unit, multiplier, order type,
time-in-force, reduce-only flag, client identity, endpoint, action, credential, and session")·
`authority_effect: AllFalseEgressAuthority`.

**`EgressGeneration`+`ActiveEgressPrincipalSet`(§8)**: `egress_generation: int | None`(monotonic·
`tos.ordering` 순서)·`active_principals: frozenset[str]`·각 principal의 `EgressPrincipal`
(workload identity·deployment/artifact/config/env digest·credential/session/route/trust-bundle
generation·activation/expiration state·§8 line 223-231). **`authority_effect: AllFalseEgress
Authority`**(§8 line 231 "no authority outside the committed set").

**`AllFalseEgressAuthority`(all-false·§4.3)**: `permits_transmission: bool = False`·`creates_
route: bool = False`·`grants_credential: bool = False`·`arms_generation: bool = False`·`re_arms:
bool = False`. `model_validator` any-True ⇒ `ArtifactIntegrityError`(rcl `AllFalseAuthority`
`_base.py`·liveauth `LiveAuthorizationEffect` `_base.py:75` 동형·로컬 재표현·import 아님).

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계

### 3.1 canonical REUSE

`tos.canonical` **REUSE**(import): `IndependentIdArtifact`(id ⊥ digest digest-bound base)·
`classify_record_pair`+`RecordPairKind`{CRITICAL_CONFLICT/IDEMPOTENT_REPLAY/...}(§5.5 replay/
substitution 노른자)·`CanonicalDecimal`(quantity/effect digest용)·`FrozenModel`·
`EVL1ProvisionalCanonicalizer`(digest 결정론). **canonical만이 base 의존**(rcl/ioc/evidence/
capsule 선례 동형).

### 3.2 ordering REUSE (egress generation·restrictive generation monotonic 순서)

`tos.ordering` **REUSE**(import): egress generation·credential/session/route/trust-bundle
generation·restrictive generation의 **committed monotonic 순서**(§8 monotonic·§13 monotonic
denial·§14 deny-first). `compare_order` 결정론. venue `Constraint Generation`·authority
`GenerationVector` 순서 REUSE 동형. **PROMOTE 0**(신규 core 승격 없음 — canonical/ordering이
전부 충분).

### 3.3 REUSE 요약 표

| 대상 | 결정 | 근거 |
|---|---|---|
| `tos.canonical`(IndependentIdArtifact·classify_record_pair·CanonicalDecimal·FrozenModel) | **REUSE (import)** | base digest substrate·replay/substitution(§5.5)·전 시리즈 선례 |
| `tos.ordering`(generation monotonic 순서) | **REUSE (import)** | egress/restrictive generation 순서(§8/§13/§14) |
| rcl commit-proof 좌표·`claim_capability`·`TransmissionCapability`·`writer_fenced`·`partition_verdict` | **주입 소비 (edge 0·재저작 금지)** | §0.4b — rcl가 ADR-002-012 commit proof 소유; EGRESS는 QCC aggregation |
| ioc `derived_command_conformance`·`mutation_fence_holds` | **주입 verdict 소비 (edge 0)** | §0.4c — command↔proof conformance는 ioc 축 |
| evidence `EvidenceCommitReceipt`·`SegmentCommitmentScheme` | **주입 소비 (edge 0·재저작 금지)** | §0.4d — receipt ≠ QCC(§21.4) |
| capsule `Bindings`(`egress_request_digest`) | **주입 digest 소비 (edge 0)** | §0.4e — forward-reference vs terminal-validation |
| venue/iap/capsule egress-currentness·CUR complete-vector | **주입 verdict 소비 (edge 0)** | §0.4f — 각 형제 자기 축·CUR 미착지 |
| brokercap/protective/recon/authority/liveauth verdict | **주입 verdict 소비 (edge 0)** | §0.4g |
| **sibling edge** | **0건** | 모든 형제 상호작용을 injected scalar/digest/bool/verdict/enum-token으로 — iap/sbr/venue/hag 선례 |

### 3.4 형제 경계 — scalar·bool·enum-token·verdict·digest seam (edge 0, 코드 실측)

EGRESS는 형제 **결과**를 대량 소비하나 iap(#15)/sbr(#17)/venue(#19)/hag(#20)와 동형으로
**edge 0**을 채택한다. 모든 형제 상호작용은 **주입된 scalar·digest·bool·verdict·opaque
enum-token(str)** 으로 받는다:

- **rcl** → commit-proof 좌표(cluster/domain/membership_gen/restore_gen/writer_epoch/revision/
   command_digest/state_digest·주입 scalar/digest)·`claim_capability` ClaimOutcome verdict(주입
   bool: consumed_now/replay)·`TransmissionCapability` 검증 verdict(`capability_authorization_
   valid` bool·주입)·`partition_verdict` PartitionVerdict(주입 bool). **재저작·import 0**.
- **ioc** → `ConformanceResult` verdict(주입 enum-token: CONFORMANT/NONCONFORMANT/UNKNOWN)·
   `command_digest`(주입 digest). **재저작·import 0**.
- **evidence** → commit-receipt all-false·UNVERIFIED status(주입 — QCC 대체 거부용). **재저작·
   import 0**.
- **capsule** → `Bindings.egress_request_digest`·capsule digest(주입 digest). **재저작·import 0**.
- **venue/iap/capsule** → egress-currentness active verdict(주입 bool). **CUR** → complete-vector
   satisfied verdict(주입 bool·미착지). **재저작·import 0**.
- **brokercap** → `credential_scope_declared_ok` verdict + profile digest(주입). **protective** →
   lease-exclusivity verdict(주입). **recon** → external-activity 분류(주입). **authority** →
   epoch/generation current verdict(주입). **liveauth** → Live Authorization scope verdict(주입).
   전부 **재저작·import 0**.

### 3.5 소유권 분할표 — EGRESS가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11-#20 §3.5 상속)

| 축 | EGRESS 소유 (로컬 저작) | 형제 소유 (주입 소비·재저작 금지) | 경계 근거 |
|---|---|---|---|
| **quorum 커밋** | QCC §11.1 claim-set aggregation·구조 완전성·좌표 currency·threshold shape(§5.1-5.4) | **rcl**: ADR-002-012 Commit Proof 좌표(`AuthoritativeSnapshot`·`RclTransitionRecord`·`LedgerCommandRecord`)·`writer_fenced`·CAS | **ADR §5.7 line 129 2층 분리**·§0.4b — bare Commit Proof necessary but not sufficient; full QCC claim set |
| **claim-to-send** | QCC의 capability-claim 좌표 존재·exact binding(§5.6-5.7) | **rcl**: `TransmissionCapability`·`claim_capability`(nonce single-use)·`CLAIM_CAPABILITY_AND_MARK_SEND_STARTED` | **rcl `records.py:249`·`predicates.py:677`**·liveauth `__init__.py:10` "no fenced single-use capability" ⇒ rcl 소유 |
| **command conformance** | egress-scope 좌표 등치(route/session/credential-gen·§5.7) | **ioc**: `derived_command_conformance`·`mutation_fence_holds`·`CanonicalBrokerCommand`·`OrderConformanceProof` | **ioc `__init__.py:14`** "not... egress engine"·§0.4c |
| **commit receipt** | `evidence_receipt_is_not_quorum_proof`(대체 거부·§5.4) | **evidence**: `EvidenceCommitReceipt`(UNVERIFIED·all-false·single-signer)·`SegmentCommitmentScheme`·`IntegrityAnchor` | **evidence `receipt.py:50-51(모듈 자기한정 :11-12)`**·§21.4·§0.4d — receipt ≠ QCC |
| **binding 체인** | terminal exact-binding 등치(§5.7) | **capsule**: `Bindings`(forward-reference·`egress_request_digest` 종단) | **capsule `capsule.py:153-167`**·§0.4e — forward vs terminal |
| **currentness** | QCC currentness-proof claim 구조 존재(§5.1) | **venue/iap/capsule**: 각 decision egress-currentness; **CUR(미착지)**: complete-vector | **§0.4f**·venue `predicates.py:493`·iap `predicates.py:578`·capsule `predicates.py:656`·CUR 주입 |
| **§18 profile** | profile-declared verdict 소비·UNKNOWN⇒축소 | **brokercap**: `credential_scope_declared_ok`·profile 필드 | **brokercap `predicates.py:684`** "egress-bypass resistance is +Security (ADR-002-013)" — brokercap가 EGRESS로 명시 이연 |
| **degraded protective** | (없음 — 전부 not-Phase-1 소비) | **protective+rcl+authority**: `ProtectiveLeaseAdmissibilityScope`·`ProtectiveLease`·`lease_scope_exclusive` | **protective `predicates.py:840-842`**·§17·EGRESS-EV-011 +Broker+Security |
| **external activity** | external all-false egress authority(§6b) | **recon**: external/unattributed 분류 | **recon `vocabulary.py:82`**·§16·EGRESS-INV-013 |
| **epoch/generation** | egress generation monotonic model(§6.2) | **authority**: epoch fencing·`recovery_generation_revives_nothing` | **authority `predicates.py:787`** non-revival 선례 |
| **Live Authorization** | (없음 — verdict 소비) | **liveauth**: `LiveAuthorization`·`scope_covers`·`no_automatic_rearm` | **liveauth `predicates.py:606`** |

---

## 4. 불변식

> 전부 순수·fail-closed. EGRESS-INV-###/AC-###/EV-###/§-clause/SAFE-###에 앵커. **어떤 EGRESS-EV도
> 닫지 않음**(규율 태그 §1).

### 4.1 QCC 구조 완전성 + 좌표 currency 중앙 불변식 (core; §11.1/§11.2; EGRESS-INV-003/004; EGRESS-AC-004; EGRESS-EV-004)

QCC는 §11.1 전 필수 claim을 **구조적으로 완전히 carry**하고, 그 carried 좌표가 **주입된 현재
committed 값과 등치**여야 한다. `None`/누락/stale/mismatch ⇒ **`EgressAdmission.DENY`**. rcl
commit-proof 좌표는 **주입 소비**(재저작 금지·§3.5). **over-realization 경계**: actual quorum
consensus/durability(§11.2 step 3의 "verify a quorum sufficient... for the claimed membership
and fault model")는 **+Security** — L1은 carried-vs-current 등치 + threshold shape만. `quorum_
commit_certificate_structurally_complete`(§5.1)·`quorum_coordinates_current`(§5.2). [EGRESS-AC-004;
SAFE-010/011/015]

### 4.2 leader-receipt ≠ quorum-proof 중앙 불변식 (core; §5.7/§11.2 line 351/§21.4; EGRESS-INV-003; EGRESS-EV-004)

단일 leader 서명·local journal·cache·projection·evidence commit receipt는 **QCC일 수 없다**.
`quorum_threshold_structurally_met`(§5.3)가 **distinct signer(eligible+signed) ≥ N**을,
`evidence_receipt_is_not_quorum_proof`(§5.4)가 **evidence receipt 대체를 거부**. §11.2 line 351
verbatim: "One leader signature, successful RPC, database primary response, local journal entry,
cached proof, event, projection, or audit record is insufficient." [EGRESS-AC-004; SAFE-010/011]

### 4.3 QCC/request/generation is-not-authority all-false 불변식 (core+predicate; §8/§11; EGRESS-INV-005/010; EGRESS-EV-004)

`QuorumCommitCertificate`·`EgressRequestRecord`·`EgressGeneration`·external-activity 아티팩트는
**`AllFalseEgressAuthority`**(permits_transmission·creates_route·grants_credential·arms_
generation·re_arms 전부 False). any-True ⇒ `ArtifactIntegrityError`(구성 불가). §8 line 231 "no
authority outside the committed set"·§10 EGRESS-INV-010 "Credential, route, deployment,
consensus, and secret-store administrators cannot create a broker-order mutation merely by
exercising administrative access". **QCC를 보유하는 것이 transmission authority가 아니다** —
authority는 §5의 술어 판정으로만(rcl `GrantDecisionRef` all-false 동형). [SAFE-045/046/047]

### 4.4 exact-binding no-substitution 중앙 불변식 (core; §11.2 step 18/§12; EGRESS-INV-004; EGRESS-AC-005; EGRESS-EV-005)

capability·claim·commit-proof·request-bytes-digest·endpoint·account·credential-generation·
broker-session·egress-generation·exact-principal이 **전부 등치**여야 하며 검증 후 **어떤 필드도
치환 불가**. EGRESS-INV-004 line 155-157 verbatim: "Capability, claim, Commit Proof, request
bytes, endpoint, account, credential generation, broker session, Egress Generation, and exact
runtime principal SHALL match. **No field may be substituted after validation.**" command↔proof
conformance는 ioc verdict 주입(§5.7). **over-realization 경계**: §12 line 367 전 필드의 actual
byte-level downstream 치환 방지는 +Security. `exact_binding_holds`(§5.7). [EGRESS-AC-005;
SAFE-021/033]

### 4.5 monotonic denial + non-revival 불변식 (predicate; §13; EGRESS-INV-006; EGRESS-EV-007 seam)

restrictive 이벤트(HALT·revocation·generation change·credential compromise·proof failure·route
contradiction) 후 deny 상태는 **monotonic** — cache recovery·reconnect·secret refresh·route
restoration·deployment success·alert 삭제로 **clear 불가**(§13 line 393). `monotonic_denial_no_
revival`(§6.3). authority `recovery_generation_revives_nothing`(`predicates.py:787`)·rcl
`partition_verdict` `automatic_rearm_denied=True`·liveauth `no_automatic_rearm` 동형. **over-
realization 경계**: 실 race timing·`B_revocation_to_egress`/`B_halt_to_egress`/`B_egress_hard_
fence` bound 전파는 +Security(§8·EGRESS-EV-007 not-Phase-1). [SAFE-041/042/048]

### 4.6 unknown-is-denial + conservative-capacity 불변식 (predicate; §11.2/§16; EGRESS-INV-011; EGRESS-EV-010 seam)

unknown proof·credential·route·send·session·broker acceptance·old-principal state는 **new risk
거부 + conservative potentially-live capacity 보존**. EGRESS-INV-011 line 183-185 verbatim:
"Unknown proof, credential, route, send, session, broker acceptance, or old-principal state
denies new risk and preserves conservative potentially-live capacity." `None`/`UNKNOWN` ⇒ deny
(§4.7). **over-realization 경계**: 실 compromise detection·capacity 정합은 +Security(§16·EGRESS-
EV-010 not-Phase-1). [SAFE-045/046/047]

### 4.7 ∅-공허 fail-closed + truthy-sentinel 소비 계약 + 집합 양방향 (양방향 명시 — #12/#13/#14 교훈)

- **∅ 양방향(#12)**: (거부 방향) ∅ signer set ⇒ 0 distinct < quorum N ⇒ QCC deny(§5.3); ∅
   required-claim(누락) ⇒ 구조 불완전 ⇒ deny(§5.1); ∅ inventory ⇒ disjointness 미증명 ⇒ deny
   (§6.1 — inventory 완전성 자체가 unproven). (허용/안전 방향) **∅ active-egress-principal-set
   ⇒ 전 transmission 거부(deny-all)는 정당한 fully-fenced 안전 상태**(§8·§14 hard-fence 완료 —
   결함 아님·오탐 금지); **∅ restrictive-event ⇒ 아무것도 새로 무효화 안 함**(availability 측 —
   currency 내 valid QCC를 spurious deny 안 함·§6.3). **양쪽 명시**.
- **집합 양방향(#14)**: quorum threshold는 **distinct signer 집합 위 연산**. (distinct 방향)
   서로 다른 eligible+signed signer ⇒ count = |signers|. (dedup 방향) 중복/replay signer ⇒
   dedup(§11.2 step 5 line 335 "reject... duplicated... signers" ⇒ 동일 signer_identity 중복.
   **dedup 규칙(v1.1 — fail-closed 해석 B 확정)**: 동일 `signer_identity`의 entry가 복수이면 **전
   entry가 eligible ∧ signature_verified `is True`로 합치할 때만** 그 identity를 1로 카운트 —
   상충 entry(하나라도 None/False)가 섞이면 그 identity는 **카운트 제외**(위조/미검증 entry 혼입이
   정상 entry에 편승하는 해석 A의 fail-open 차단; 비용은 spurious-deny 방향 = 가용성, 안전 아님)
   count 금지). LEADER 단독 ⇒ count 1 < N(§5.3). **`count >= N`이 ∅/1에서 vacuous 안 되도록**
   non-empty + N ≥ 1 강제(authority `lease_scope_exclusive` M1 non-empty 봉인 상속).
- **truthy-sentinel 구조 봉인(#13·#14 M1 — 처음부터)**: `EgressAdmission`{ADMIT/DENY}·`Commit
   ProofValidity`{VALID/INVALID/UNKNOWN}·`RestrictiveLatchState`{CLEAR/DENY_LATCHED}는 `_Non
   TruthyStrEnum`(`__bool__ ⇒ TypeError`). 소비 게이트는 **`admission is EgressAdmission.ADMIT`·
   `validity is CommitProofValidity.VALID`·`state is RestrictiveLatchState.CLEAR` 명시 비교**
   (bare `if admission:`/`if validity:`/`if state:` 금지 — DENY/INVALID/DENY_LATCHED가 non-empty
   string이라 truthy fail-open). `bool | None` 주입 조건(`eligible_verified`·`signature_
   verified`·`egress_currentness_active`)은 `is True`(None=UNKNOWN=fail-closed). iap `_Non
   TruthyStrEnum`(`vocabulary.py:50`)·ioc `ConformanceResult`(`vocabulary.py:63`) 동형·로컬
   재표현. §7 회귀 강제.
- **금지 동사 canary(#5 상속)**: EGRESS 모델에 mutate/activate/issue/transmit/sign/re-arm/
   clear-latch/rotate/failover 메서드 **구조적 부재**(constructive absence) — all-false +
   no-method가 fail-open 경로를 구조로 봉인.

---

## 5. core 술어 — L1 슬라이스 (EGRESS-EV-004/005 substrate)

> 전부 **순수 함수·fail-closed**: ∅·missing/`None`·미검증 witness·unknown state ⇒ `EgressAdmission.
> DENY`. **어떤 EGRESS-EV도 닫지 않음**(규율 태그 §1). **서명/eligibility/quorum consensus/
> byte-level reconstruction은 전부 주입 verified-flag 또는 +Security**(over-realization 경계).

### 5.1 `quorum_commit_certificate_structurally_complete` (§11.1/§11.2 step 1-2; EGRESS-EV-004 substrate, core L1 — 노른자·+Security)

`quorum_commit_certificate_structurally_complete(qcc) -> bool`: `True` **오직** (i) §11.1
`_REQUIRED_COVERED` 전 필드(commit-proof 좌표·egress generation·active principal·signer 좌표·
capability/permit nonce) **concrete**(None 없음), (ii) closed schema — unknown security-relevant
필드/ambiguous encoding 없음(§11.2 step 2 line 332 "reject unknown security-relevant fields or
ambiguous encodings"), (iii) signer_coordinates **non-empty**(§4.7). missing/`None`/unknown 필드
⇒ `False`. **malformed-model 자기방어**(§2.3): validator가 이미 필수 None을 구성 단계에서
거부하나 술어 층 재확인(defense-in-depth). **over-realization 경계**: 이것은 **구조 완전성**만 —
quorum이 실제로 durably accept했는지는 §5.2/§5.3 + +Security. [EGRESS-AC-004; SAFE-010/011]

### 5.2 `quorum_coordinates_current` (§11.2 step 1-7 구조 부분; EGRESS-EV-004 substrate, core L1, +Security)

`quorum_coordinates_current(qcc, injected_current) -> bool`: `True` **오직** QCC-carried 좌표가
주입된 현재 committed 값과 **전부 등치** — cluster_identity·capacity_domain·membership_
generation·restore_generation·writer_epoch·committed_revision·canonical_command_digest·
resulting_state_digest·egress_generation·credential/session/route/trust-bundle generation
(§11.2 step 6-7 line 336-337). any None/mismatch/stale ⇒ `False`. **rcl `writer_fenced` 재저작
아님**(§3.5) — carried-vs-current **등치**만 판정(rcl가 stale writer/CAS를 이미 소유; EGRESS는
QCC가 그 현재 좌표를 정확히 carry하는지). sibling generation(018/019/020/021/022/023/024/029/
030)도 주입 current와 등치(§11.2 step 8-16 — 각 형제 verdict는 §5.7/§6에서). **over-realization
경계**: §11.2 step 3 "verify a quorum sufficient... for the claimed membership and fault model"의
**실제 consensus/durability 검증은 +Security** — L1은 좌표 등치만. [EGRESS-AC-004; SAFE-015]

### 5.3 `quorum_threshold_structurally_met` (§11.2 step 3-5/line 351; EGRESS-EV-004 substrate, core L1, +Security)

`quorum_threshold_structurally_met(signer_coordinates, quorum_n) -> bool`: `True` **오직** (i)
`quorum_n >= 1`(degenerate 0 거부·§4.7), (ii) **distinct** signer_identity 중 `eligible_verified
is True` AND `signature_verified is True`인 것의 count **≥ quorum_n**, (iii) 중복 signer_identity
dedup(§11.2 step 5 line 335 "reject... duplicated... signers"), (iv) LEADER 단독/1인 ⇒ False
(§11.2 line 351 "one leader signature insufficient"), (v) signer_coordinates non-empty(§4.7).
**서명·eligibility는 주입 verified-flag**(`is True`·§4.7 truthy-sentinel; None ⇒ count 제외).
**over-realization 경계(최대 위험 지점)**: 이 술어는 **주입 flag 위의 distinct-count 구조
판정**일 뿐 — (a) 실제 cryptographic signature 검증(step 4 "verify every signer was eligible")·
(b) membership-generation eligibility 증명·(c) quorum consensus durability(step 3)는 **전부
+Security**. green `quorum_threshold_structurally_met`은 **quorum commitment 증명이 아니라
carried claim-set이 quorum-shaped라는 구조 증명**. [EGRESS-AC-004; SAFE-010/011]

### 5.4 `evidence_receipt_is_not_quorum_proof` (§5.7/§11.2 line 351/§21.4; EGRESS-EV-004 substrate, core L1)

`evidence_receipt_is_not_quorum_proof(candidate) -> bool`: **무조건 True**(거부 술어) — evidence
commit receipt·leader receipt·local journal·cache entry·projection·audit record는 QCC를 **대체할
수 없다**. 구조 근거(§0.4d): (i) evidence `EvidenceCommitReceipt`은 단일 `receipt_signer_
identity`(≠ quorum threshold·§5.3), (ii) `ReceiptVerificationStatus.UNVERIFIED`(≠ durable quorum
acceptance·`receipt.py:50-51(모듈 자기한정 :11-12)`), (iii) all-false authority(transmission 미허가). §21.4 line 560-562
"Leader Receipt as Commit Proof... Rejected because leader belief, local persistence, or
signature does not prove quorum commitment"·§2 line 49 "durable local journal... equivalent to
ADR-002-012 quorum commit"(UNSAFE). **evidence `EvidenceCommitReceipt`·`SegmentCommitmentScheme`
재저작·import 아님**(§3.5 — 대체 시도 거부만). [EGRESS-AC-004; SAFE-010/011]

### 5.5 `replay_or_substitution_detected` (§11/§12·EGRESS-INV-004; EGRESS-EV-005 substrate, core L1 — 노른자)

`replay_or_substitution_detected(a, b) -> RecordPairKind`: **`classify_record_pair` REUSE**
(canonical·§3.1). same proof-id/capability-id/nonce + **different bound bytes** ⇒
`CRITICAL_CONFLICT`(substitution — §11.2 step 18 "request bytes differ"·§20 line 532 "Proof valid
but request bytes or endpoint differ... reject; Critical integrity alert"). same 완전 동일 ⇒
`IDEMPOTENT_REPLAY`(already-consumed·no new send authority·rcl `claim_capability` replay 동형).
`EGRESS-AC-005` verbatim(line 626): "Valid proof or capability cannot be replayed, reused,
transplanted to another principal/request/endpoint, or paired with changed request bytes."
transplant(다른 principal/endpoint) ⇒ exact-binding mismatch(§5.7). **id ⊥ digest**(§2.1) ⇒
same-id/different-bytes가 **탐지 가능**하게 유지(digest-bound 아티팩트). [EGRESS-AC-005;
SAFE-021/033]

### 5.6 `capability_and_permit_single_use` (§11.2 step 17; EGRESS-EV-005 substrate, core L1)

`capability_and_permit_single_use(capability_nonce, action_flow_permit_nonce, prior_claims, *,
principal, request_digest) -> bool`: `True` **오직** capability nonce **AND** action-flow-permit
nonce가 **각각 이 exact principal + request에 대해 정확히 한 번** claim(§11.2 step 17 line 347
"verify the capability nonce and Action Flow Permit claim nonce are each bound and claimed
exactly once for this principal and request"). **rcl `claim_capability`(`predicates.py:677`) 소비**
— rcl가 nonce single-use + replay를 이미 소유(`predicates.py:698-703`); EGRESS는 그 ClaimOutcome
(주입)이 **THIS principal + THIS request_digest에 bound**인지 추가 판정(rcl는 nonce 유일성,
EGRESS는 principal/request 결합). None nonce ⇒ False(fail-closed·rcl `predicates.py:698` 동형).
prior claim에 same nonce 존재(다른 principal/request) ⇒ transplant ⇒ False. **rcl `claim_
capability` 재저작 아님**(§3.5 — ClaimOutcome 주입 소비). [EGRESS-AC-005; SAFE-014/015]

### 5.7 `exact_binding_holds` (§11.2 step 18/§12·EGRESS-INV-004; EGRESS-EV-005 substrate, core L1, +Security)

`exact_binding_holds(request, qcc, injected_authorized, ioc_conformance_verdict, capsule_egress_
request_digest) -> bool`: `True` **오직** (i) request의 egress 좌표(endpoint·account·environment·
action·method·route_identity·credential_generation·broker_session_generation·egress_generation·
active_principal)가 **주입 authorized 값과 전부 등치**(EGRESS-INV-004 line 155-157 "SHALL match.
No field may be substituted"), (ii) `request.request_bytes_digest == capsule_egress_request_
digest`(capsule Bindings 종단 등치·§0.4e), (iii) `qcc.canonical_command_digest ==
request`에 대응하는 command digest, (iv) **`ioc_conformance_verdict is ConformanceResult.
CONFORMANT`**(command↔proof↔effect conformance는 ioc 주입 verdict·§0.4c·§11.2 step 18 "compare
its canonical semantics, digest, endpoint, action, account, route, and economic effect to the
ADR-002-020 command and proof"). any None/mismatch/non-CONFORMANT ⇒ `False`. **ioc `derived_
command_conformance`·capsule `Bindings` 재저작 아님**(§3.5 — verdict/digest 주입). **over-
realization 경계**: §11.2 step 18의 "reconstruct the exact actual outbound representation after
every mutable internal stage"의 **실제 byte-level reconstruction·§10 route confinement·§8 env
non-interchangeability enforcement는 +Security**(EGRESS-EV-003 not-Phase-1) — L1은 주입 좌표
등치 + ioc verdict 소비만. [EGRESS-AC-005; SAFE-021/033/045/046/047]

---

## 6. predicate-only 술어 — ≥ L2 (EGRESS-EV-001 substrate, 닫지 않음)

> **최소 ≥ L2** — L1-decidable predicate substrate를 저작하나 **EV를 닫지 않음**(inventory
> enumeration·+Security 잔여).

### 6.1 `credential_route_authority_disjoint` (§6/§9/§10; EGRESS-EV-001 substrate, predicate-only, 최소 EV-L2/3+Security)

`credential_route_authority_disjoint(inventory) -> bool`: 주입 inventory(각 entry = principal ×
`usable_credential: bool | None` × `broker_route: bool | None` × `inside_boundary: bool | None`)
위에서 `True` **오직** **어떤 outside-boundary principal도 usable-credential AND route를 동시
보유하지 않음**(EGRESS-INV-002 line 147-149 "No identity outside the current boundary possesses
both usable live-order authority and a broker-order route"). 판정: 각 entry에 대해 `inside_
boundary is not True`(outside/unknown)이면서 `usable_credential is not False`(True/None=
potentially-usable) AND `broker_route is not False`이면 ⇒ **False**(bypass 후보). **unknown
flag(None) ⇒ potentially-usable로 취급**(conservative·EGRESS-INV-011·§4.6). **∅ inventory ⇒
False**(disjointness 미증명 — inventory 완전성 자체가 unproven·§4.7). **over-realization 경계**:
실 inventory enumeration(hidden operational/recovery/portal/CI-CD/support/vendor credential·
§9.1 line 251)은 **L2+**(register floor `EV-L2/3+Security`) — L1은 주입 inventory 위 disjointness
predicate만. §14 EGRESS-INV-014 line 195 "Credential inventories... do not establish route
confinement, proof validity, or hard fencing" — inventory 술어는 prevention이 아니라 predicate.
[EGRESS-AC-001; SAFE-045/046/047]

---

## 6b. not-Phase-1 술어 — seam + thin model property (EGRESS-EV-002/003/006-013, 닫지 않음·over-realization 봉합)

> **정직한 over-realization 경계**: 아래 10행은 **런타임 보안(+Security/+Broker/+L5)**이며
> Phase 1은 이들을 **닫지 않는다.** 일부는 isomorphic한 **thin L1 model property**를 defense-in-
> depth로 저작하나 — **이 model property는 EV 실현이 아니다**(EV acceptance는 +Security 런타임).
> 나머지는 pure seam(형제/런타임 소유). **이것이 이 문서의 최대 위험 봉합**: 물리 bypass·
> rotation·failover·compromise를 L1으로 오주장하지 않는다.

### 6b.1 `egress_generation_monotonic` + `stale_principal_structurally_rejected` (§8; EGRESS-EV-002 seam, thin model property)

- `egress_generation_monotonic(prior, new) -> bool`: egress generation은 monotonic 증가(§8·`tos.
   ordering`); 감소/동일-different-content ⇒ False.
- `stale_principal_structurally_rejected(principal, active_set) -> bool`: `principal ∈ active_
   egress_principal_set`이고 generation 일치해야 `True`; 미표현/wrong-generation/expired ⇒ False
   (§8 line 233 "SHALL NOT infer membership from a service account name, namespace, host role,
   load-balancer target, possession of an old secret, or successful broker authentication").
- **이것은 §5.1/§5.2 QCC egress-gen/principal claim에 편입되는 model property**이지 EGRESS-EV-002
   실현이 아니다. **EGRESS-EV-002(Direct/Stale-Principal Bypass) 실 bypass 저항**(credential
   custody §9 + route confinement §10 + network enforcement)은 **+Security**(csv:150 `EV-L3+
   Security`). [SAFE-045/046/047]

### 6b.2 `exact_binding_coordinate_equality` 공유 (§10/EGRESS-INV-004; EGRESS-EV-003 seam)

env/scope/endpoint/route substitution의 **좌표 등치 부분**은 `exact_binding_holds`(§5.7)와 공유
(주입 좌표 등치). **EGRESS-EV-003 실 route/env confinement·network enforcement·live/non-live
non-interchangeability**(§8 line 173 EGRESS-INV-008·§10 line 291)는 **+Security**(csv:151 `EV-L3+
Security`). L1 model property 없음(좌표 등치는 §5.7에서 이미).

### 6b.3 `monotonic_denial_no_revival` (§13; EGRESS-EV-006/007 seam, thin model property)

`monotonic_denial_no_revival(latch_state, injected_events) -> RestrictiveLatchState`: `latch_
state is DENY_LATCHED`이면 어떤 주입 event(recovery/reconnect/secret_refresh/route_restoration/
deployment_success/alert_deletion)도 `CLEAR`로 전환 **불가**(§13 line 393). authority `recovery_
generation_revives_nothing`(`predicates.py:787`)·rcl `partition_verdict` `automatic_rearm_
denied=True`·liveauth `no_automatic_rearm`(`predicates.py:606`) 동형(재저작 아님·isomorphic 저작).
- **EGRESS-EV-006(Downstream Intermediary/Reconnect)**: reconnect ↛ queue flush/authority revival
   (§12 line 376·§20 line 541 "Egress reconnects after outage... remain denied; no queued flush
   or authority revival")는 이 non-revival의 인스턴스이나 **실 topology/queue/reconnect 런타임**은
   +Security(csv:154 `EV-L3+Security`).
- **EGRESS-EV-007(Restrictive Race at Actual Send Boundary)**: 이 monotonic-denial model property가
   decidability를 주나 **실 race at irreversible boundary·`B_revocation_to_egress`/`B_halt_to_
   egress`/`B_egress_hard_fence` bound 전파**는 +Security(csv:155 `EV-L3+Security`). [SAFE-041/042/048]

### 6b.4 나머지 not-Phase-1 (pure seam / thin model property)

- **EGRESS-EV-008 (Deny-First Credential/Trust Rotation·§14)**: 8-step deny-first 순서(§14 line
   401-410)를 model로 표현 가능하나 **실 rotation·Hard Egress Fence Proof(credential/session
   revocation·non-exportable signer·route denial·key destruction·§14 line 412)**는 **+Security/+L5**
   (csv:156 `EV-L3/5+Security`). thin ordering model만·EV 미실현.
- **EGRESS-EV-009 (Failover/Rollback/Removed-Principal·§15)**: "Rollback is a new Egress
   Generation"(§15 line 437) non-revival model(§6b.3 동형). **실 failover authority change·predecessor
   hard-fence**는 +Security(csv:157 `EV-L3+Security`).
- **EGRESS-EV-010 (Compromise/Unknown Revocation·§16)**: `unknown-is-denial` model property(§4.6·
   EGRESS-INV-011). **실 compromise detection·rotation·quarantine·reconciliation**는 +Security/+L5
   (csv:158 `EV-L3/5+Security`).
- **EGRESS-EV-011 (Degraded Protective Exclusivity·§17)**: **protective+rcl+authority 소유**
   (`ProtectiveLeaseAdmissibilityScope`·`ProtectiveLease`·`lease_scope_exclusive`·§0.4g·§3.5).
   EGRESS는 lease-exclusivity verdict 주입 소비. **pure seam**·+Broker+Security(csv:159).
- **EGRESS-EV-012 (Manual Authority/Recovery Cannot Re-arm·§16)**: `no_automatic_rearm`(liveauth
   동형)+external-activity **all-false egress authority**(§4.3·recon 분류 주입·§0.4g). external
   broker portal/manual/third-party는 "external activity requiring detection, reconciliation, and
   conservative capacity; it cannot be relabelled as a compliant TOS egress path"(EGRESS-INV-013
   line 191-193). **실 external detection/reconciliation**는 recon+ +Security/+L5(csv:160 `EV-L3/5+
   Security`).
- **EGRESS-EV-013 (Out-of-Band Containment·§14/§16)**: defective/compromised final egress point의
   OOB containment(`B_controlled_shutdown_hard_fence` VP line 436). **pure seam·L1 model property
   없음**·+Broker+Security(csv:371 `EV-L3/5+Broker+Security`).

---

## 7. property-test 하네스 타깃

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#12-#20 §7.1 상속·allowlist 형식)

`import tos.egress` 후 `sys.modules` closure를 **allowlist로 검증**: `tos.* closure ⊆
{tos.canonical, tos.ordering, tos.egress}`(rcl `test_rcl_import_closure.py` 선례 — subset
검증이라 미래 신규 형제(cur/sci/ptf/nt)·카운트 오차 자동 배제). 추가로 금지 집합 부재 assert:
`shared.config`·`shared.config.secrets`·`shared.determinism`·`os.environ`/`os.getenv` 흔적·동적
escape(`exec`/`eval`/`importlib`/`__import__`)·`numpy`/`pandas`/`yaml`·**전 형제 tos 패키지
부재**(afg·are·authority·brokercap·capsule·dsl·evidence·hag·iap·**ioc**·liveauth·orthostate·
protective·**rcl**·recon·replacement·sbr·spg·time·venue — **`tos.rcl`·`tos.ioc`·`tos.evidence`·
`tos.capsule` 명시 포함**, #17 MAJOR-1 교훈: EGRESS의 최대 재저작 유혹이 이 4개이므로 부재
assert가 "verdict 주입이지 import 아님"을 강제); **`tos.canonical`·`tos.ordering`만 존재 허용**
(sibling edge 0·§3.4). **병렬 레이스 봉합(#17/#19 교훈·세션 B NT 착지 대비)**: allowlist는
subset 검증이므로 NT(`tos.nt`)·CUR(`tos.cur`)·SCI·PTF가 병렬 착지해도 **자동 배제**(신규
`tos.egress` import가 이들을 끌어오면 closure ⊄ allowlist ⇒ 즉시 fail) — "NT 코드 부재" 같은
거짓 하드코딩 없이 subset이 봉인. required check(`tos-firewall`, `tools/tos_firewall_check.py`
layer-① AST + `.importlinter` layer-② 전이)와 함께 green이어야 §0.3 선언 능동 성립. **주의**:
rcl `claim_capability`·ioc `derived_command_conformance`·evidence `EvidenceCommitReceipt`·capsule
`Bindings` **부재**를 assert — 로컬 저작(evidence_receipt_is_not_quorum_proof 등)이지 import 아님을
이 테스트가 강제. planted-leak canary(fake `tos.rcl`·`tos.ioc`·`shared.config` 주입 후 탐지
확인)로 checker 작동 증명.

**property test 군(§5/§6 술어별)**: (1) QCC 구조 완전성·malformed-model 거부(§5.1·`model_
validator` 필수-None ⇒ ArtifactIntegrityError·`model_construct` 우회도 술어 층에서 거부)·(2)
좌표 currency·carried-vs-current 등치·any-mismatch ⇒ deny(§5.2)·(3) **quorum threshold distinct-
count**(hypothesis signer 집합 생성·LEADER 단독 거부·중복 dedup·∅/1 vacuous 거부·주입 flag
`is True` 소비·§5.3 — over-realization 경계: 서명 주입임을 회귀로 명시)·(4) evidence-receipt
대체 거부(§5.4)·(5) replay/substitution `classify_record_pair` CRITICAL_CONFLICT·transplant
탐지(§5.5)·(6) capability/permit single-use·rcl ClaimOutcome 소비·transplant 거부(§5.6)·(7)
exact-binding 좌표 등치·ioc verdict 소비·capsule digest 등치(§5.7)·(8) credential-route
disjointness·unknown⇒conservative·∅⇒deny(§6.1)·(9) monotonic-denial non-revival(§6b.3)·(10)
all-false 구성 거부(§4.3 any-True ⇒ ArtifactIntegrityError)·(11) **truthy-sentinel 회귀**
(`bool(EgressAdmission.DENY)`·`bool(CommitProofValidity.UNKNOWN)`·`bool(RestrictiveLatchState.
DENY_LATCHED)` ⇒ TypeError·§4.7)·(12) **∅ 양방향**(∅ signer set 거부·∅ active-principal-set
deny-all 안전상태·∅ restrictive-event availability·§4.7)·(13) **집합 양방향**(distinct signers vs
중복 dedup·§4.7).

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: egress Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `pytest tos/tests/egress/ -v`
(실행: `PYTHONPATH=tos/src .venv/bin/python -m pytest tos/tests/egress/ -v` — pyenv은 mypy
전용). (3) 격리: hermetic(`.env` 비주입·clock 미접근·네트워크 없음·egress 비전송 — final-egress
판정의 hidden-input·실 broker 접촉 부재). (4) 결정론: hypothesis 시드 고정·`EVL1Provisional
Canonicalizer` 고정·StrEnum 고정·`compare_order` 결정론·`classify_record_pair` 결정론. (5)
산출물: property test 결과(EV closure 아님 — 규율 태그). (6) 게이트: `tos-firewall` required
green. (7) 비-acceptance: 어떤 EGRESS-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 egress 모델 구조에 numeric 값 부재**: quorum N·claim-to-send latency·revocation/HALT/
hard-fence propagation·currentness-proof age 전부 enum·boolean·집합/좌표 논리·주입 opaque param.
ADR §25 q11(line 667)·§4 non-scope(line 90 "numeric fencing, propagation, session, or rotation
bounds")가 수치를 명시 배제 — 전부 Safety/Verification Profile INSTANCE 측정값. 값 부재 ⇒
fail-closed(§4·§5). 하드코딩 0.

**§8.1 Verification-Profile 키 실측(#13 MAJOR-2 규율 — 전수 grep)**: EGRESS-owned/관련 키(전부
실재·null/TBD·미승인):

- **`B_egress_hard_fence`**(VP line 170, `value_ms: null` — "APPROVE after credential, session,
   signer, route, and broker fence mechanisms are selected and measured", `measurement_source:
   egress_identity_route_session_and_broker_denial_log`, rationale line 174 "ADR-002-013 §§13-16.
   Unknown completion keeps replacement authority non-live") — **실재**. §4.5·§6b.3/§6b.4 정합.
- **`B_capability_claim_to_send`**(VP line 163, `null` — "APPROVE after the fenced egress journal
   and broker transport are implemented", `measurement_source: egress_journal_and_broker_
   transport_trace`) — **실재**. §5.6/§5.7 claim-to-send 정합.
- **`B_revocation_to_egress`**(VP line 135, `null` — rationale line 139 "ADR-002-007 §§9, 16")·
   **`B_halt_to_egress`**(VP line 142, `null`)·**`B_time_health_to_egress`**(VP line 156, `null`)
   — **전부 실재**. §4.5 monotonic-denial 전파 bound.
- **`MAX_egress_currentness_proof_age_ms`**(VP line 723, `null` — "APPROVE per send boundary;
   every normal send still requires a new single-use proof") — **실재**. §5.1 QCC currentness-
   proof claim·§0.4f 정합.
- **결론(over-claim 봉합·#10 lesson)**: ADR §25 q11·§26 item 20이 요구하는 EGRESS-owned bound
   (`B_egress_hard_fence`·`B_capability_claim_to_send` + 전파 bound `B_revocation_to_egress`/
   `B_halt_to_egress`/`B_time_health_to_egress`)가 전부 실재하고, `MAX_egress_currentness_proof_age_ms`
   (line 723)는 **ADR-002-024(CUR) 소유·EGRESS는 주입 소비/verify 대상**(v1.1 MAJOR-2 — §8.2·§0.4f 정합)이며 함께 실재함이
   **전부 실재**·전부 null/TBD(미승인). ⇒ **candidate 신규 키 = 0건**(#10/#13/#15/#17/#19/#20 "0
   누락" 동형). 결함 아님 — **Phase-0 Bounds-Approver 승인 항목**. egress는 이 값들을 신뢰하지
   않으며(VP status null/TBD·unapproved bound은 approved bound 아님, VER-002-001 §6) 전 수치를
   fail-closed로 처리(§4·§5).

**§8.2 형제 키와 혼동 주의**: `B_currentness_fence_to_egress`(VP line 338)·`MAX_egress_
currentness_proof_age_ms`(line 723)는 **ADR-002-024(CUR) 소유**(미착지)·`B_action_flow_invalid_
to_egress`(line 289) 등 `*_invalid_to_egress` 접미 계열은 **각 형제 소유**(018/019/020/021/022/023/
024/029/030 각자의 invalidation-to-egress 전파). EGRESS는 이 전파 verdict를 **주입 소비**하지
소유하지 않는다(§3.5). EGRESS-owned는 `B_egress_hard_fence`·`B_capability_claim_to_send` +
restrictive-event 전파(`B_revocation/halt/time_health_to_egress`).

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. `tos/src/tos/egress/` 5-module 저작(`_base.py` all-false `AllFalseEgressAuthority` +
   `model_validator` + defence-in-depth·`vocabulary.py`[`EgressAdmission`·`CommitProofValidity`·
   `RestrictiveLatchState`·`SignerRole`·`_NonTruthyStrEnum` truthy 봉인]·`records.py`[`Quorum
   CommitCertificate`+`model_validator` malformed-model 봉인·`EgressRequestRecord`·`EgressGeneration`·
   `ActiveEgressPrincipalSet`·`ReplayObservation` digest-bound 아티팩트]·`predicates.py`[core §5 7군
   + predicate-only §6.1 + not-Phase-1 thin model §6b]·`state.py`[`SignerCoordinate`·`EgressCoordinate
   Set`·`CredentialRouteInventoryEntry`·`CommitProofCoordinates` 주입 입력]) + `tos/tests/egress/`
   property test(§7) + seam cross-check(§3.4) + import-closure(§7.1 allowlist·rcl/ioc/evidence/
   capsule 부재 명시) + truthy-sentinel 구조 봉인 회귀(§4.7) + all-false any-True 거부 회귀(§4.3) +
   malformed-model 자기방어 회귀(§2.3).
2. core 술어 7군(§5) + predicate-only §6.1 + not-Phase-1 thin model §6b + 5-아티팩트·all-false
   `AllFalseEgressAuthority`·enum 어휘(§2) 구현. **sibling edge 0 유지**(§0.4·§3.4) — 어떤 형제
   타입도 REUSE·import 안 함(형제 결과는 injected scalar/bool/enum-token/verdict/digest). rcl
   `claim_capability`·`writer_fenced`·`TransmissionCapability`·ioc `derived_command_conformance`·
   evidence `EvidenceCommitReceipt`·capsule `Bindings` **재저작 금지·import 금지**(§7.1 부재 assert).
3. 미래 caller 런타임(Broker Egress Gateway·Final Egress Trust Boundary service)이 egress 산출
   (QCC 구조 verdict·exact-binding verdict·admission)을 소비자로 배선(§3.4; Phase 1 밖·EV-L2/L3+
   Security). **rcl commit-proof 좌표 → QCC 주입 → EGRESS 구조 검증 → +Security quorum consensus
   검증**은 런타임 gate 몫(§3.5) — egress 순수 모델은 주입 위 구조/좌표 판정만.

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §25 Open Implementation Questions(19항)·§26 Approval Gate(22조건)에서 Phase-1 밖으로 이연:

1. **non-exportable signer·secret-delivery·broker credential model 선정**(§25 q1·§26 item 4) —
   제품·+Security(§9.2 credential custody).
2. **identity-aware network/proxy/broker-side route 확립**(§25 q2·§26 item 5) — +Security route
   confinement(EGRESS-EV-002/003 not-Phase-1).
3. **canonical QCC schema·signature aggregation·quorum rule·verification library**(§25 q3·§26
   item 3) — **QCC 구조 술어는 §5.1-5.4**; 서명 aggregation·crypto library는 Phase-0·+Security.
4. **consensus membership key·Egress trust bundle rotation/rollback-protect**(§25 q4·§26 item 6)
   — +Security(EGRESS-EV-008 not-Phase-1·§11.3).
5. **active/standby·multi-principal egress topology per Safety Cell**(§25 q5) — 제품·+Security
   (EGRESS-EV-009).
6. **broker credential/session/endpoint/redirect/revocation semantics(first profile)**(§25 q6·
   §26 item 7) — brokercap profile INSTANCE·+Broker(§0.4g).
7. **Hard Egress Fence Proof (old instance/credential/region unreachable)**(§25 q7·§26 item 5) —
   +Security/+L5(EGRESS-EV-008/013).
8. **downstream proxy/TLS-terminator/signer/queue/session-manager 경계 분류**(§25 q8·§26 item 8)
   — +Security topology(EGRESS-EV-006).
9. **manual portal/support channel governance·external broker detection**(§25 q9·§26 item 5) —
   recon + +Security/+Broker(EGRESS-EV-012·§16).
10. **degraded protective credential/route exclusivity**(§25 q10) — protective+rcl+authority·
    +Broker+Security(EGRESS-EV-011·§0.4g).
11. **numeric bounds 승인**(§25 q11·§26 item 20) — `B_egress_hard_fence`·`B_capability_claim_to_
    send`·전파 bound·`MAX_egress_currentness_proof_age_ms`(§8.1 **전부 실재·null/TBD**)의 Bounds-
    Approver 승인 + fault-injection 측정. **candidate 신규 키 0건.**
12. **credential/route/deployment/trust-bundle/re-arm 승인 독립 identity(§7 SoD)**(§25 q12·§26
    item 6) — hag `separation_of_duties_satisfied`(ADR-002-015) + +Security(§7 SoD는 hag 축).
13. **ADR-002-014 SPG Canonical Semantic Digest·Profile Generation·Consumer Compatibility**(§25
    q13·§26 item 9) — spg 주입 소비(배포됨·§3.4).
14. **ADR-002-015 HAG Human HALT authenticator·replay fence·local deny latch(final egress)**(§25
    q14·§26 item 10) — hag 주입 소비(배포·#20)·+Security.
15. **ADR-002-016 ERI Evidence Commit Receipt·durable journal·source sequence(pre-effect/SEND_
    STARTED, ≠ transmission authority)**(§25 q15·§26 item 11) — evidence 주입 소비(배포)·§5.4
    receipt ≠ QCC.
16. **ADR-002-017/018/019/020/021/022/023 exact binding·active currentness(final egress)**(§25
    q16-19·§26 item 12-18) — sbr/capsule/venue/ioc/are/afg/iap digest·verdict 주입 소비(전부
    배포됨·§3.4; egress import 아님)·+Security.
17. **ADR-002-024 CUR complete-vector/deny-first/monotonic/claim-fence·ADR-002-029 SCI·ADR-002-030
    PTF·ADR-002-025 RLP restricted-live·ADR-002-026 WDR·ADR-002-010 NT**(§11.1 line 308-322·§26
    item 19·§12 line 365) — **미착지 상류** — scalar/verdict 주입(not-Phase-1·phantom 봉합·코드
    인용 0).
18. **ARCHITECTURE-GATE-STATUS 명시 acceptance 결정**(§26 item 22) — 실행된 EGRESS-EV-001..013 +
    cross-system evidence(SA/BC/REARM/FD/RCLP/SPG/HAG/cross-system, §26 item 8) + 독립 security
    review(§26 item 6 "independently reviewed"·Independent-Safety-Reviewer 하드 배제).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- **v1.0 (2026-07-26) — 초안, 독립 비평 리뷰 대기.** ADR-002-013(EGRESS)를 Phase 1(EV-L1) 설계
  계약으로 실현. 문서 번호 **#22**(#21 NT 이후·NT는 세션 B 미비준이라 인용 없음·ADR-002-010
  원문만). 패키지 **`tos.egress`**(runner-up `tos.qcc`[QCC-only 축 배제]·기각; 근거: register
  prefix EGRESS 1:1·head-noun·seam 토큰[capsule `egress_request_digest`·rcl `TransmissionCapability`]
  정합, §0.4a). 5 digest-bound 아티팩트(`QuorumCommitCertificate`·`EgressRequestRecord`·`Egress
  Generation`·`ActiveEgressPrincipalSet`·`ReplayObservation`, 전부 `IndependentIdArtifact`)+enum
  어휘(`EgressAdmission`[non-truthy]·`CommitProofValidity`[non-truthy]·`RestrictiveLatchState`
  [non-truthy]·`SignerRole`)+all-false `AllFalseEgressAuthority`(§2). **EV 3분류(행별)**: **core
  2행(EGRESS-EV-004/005, L1-floor `EV-L1/3+Security`) / predicate-only 1행(001, `EV-L2/3+Security`) /
  not-Phase-1 10행(002/003/006-013, L3+/L5+·+Security/+Broker) — 닫는 EGRESS-EV = 0건**(§1).
  seam: **rcl/ioc/evidence/capsule/venue/iap/are/afg/sbr/hag/brokercap/protective/recon/authority/
  liveauth + CUR/SCI/PTF/RLP/WDR/NT(미착지·주입) scalar·bool·enum-token·verdict·digest
  producer/consumer + sibling edge 0건, PROMOTE 0**(코드 실측: rcl `records.py:249/428`·
  `predicates.py:507/627/677/711`, ioc `records.py:301/357`·`predicates.py:492/527`, evidence
  `receipt.py:11/59`·`ledger.py:82`, capsule `capsule.py:153-167/656`, venue `predicates.py:493/529`,
  iap `predicates.py:578`, brokercap `predicates.py:675/684`, protective `predicates.py:840-842`,
  recon `vocabulary.py:82`, authority `predicates.py:787`, liveauth `__init__.py:10`·`predicates.py:606`,
  §3.4). **핵심 아키텍처 판정**: (i) **rcl = ADR-002-012 Commit Proof(quorum commitment 좌표)
  소유; EGRESS = Quorum Commit Certificate(QCC — egress-boundary aggregation·구조 검증) 소유**
  (§0.4b·§3.5 최대 경계) — ADR §5.7 line 129 "bare Commit Proof necessary but not sufficient...
  full QCC claim set SHALL be satisfied"가 2층을 명시; EGRESS는 rcl `writer_fenced`/`claim_
  capability`/`TransmissionCapability` **재저작 금지·주입 소비**. (ii) **QCC ≠ evidence commit
  receipt**(§0.4d·§5.4 핵심 판정) — evidence `receipt.py:50-51(모듈 자기한정 :11-12)`가 UNVERIFIED/single-signer/
  all-false로 QCC 자격 부재를 스스로 증언·§21.4 leader-receipt 기각. (iii) **command conformance =
  ioc 축; egress-scope 좌표 = EGRESS 축**(§0.4c·defense-in-depth). (iv) **over-realization 최대
  위험 봉합**(§1·§6b) — cryptographic validity·quorum consensus·bypass resistance·credential
  custody·rotation/failover/compromise runtime을 **전부 주입 verified-flag/+Security로 정직
  이연**; not-Phase-1 10행은 thin L1 model property(monotonic-denial·egress-generation·unknown-
  is-denial)를 defense-in-depth로만 저작하고 **EV 미실현 명시**. 중심 fail-closed 술어: `quorum_
  commit_certificate_structurally_complete`+`quorum_coordinates_current`+`quorum_threshold_
  structurally_met`+`evidence_receipt_is_not_quorum_proof`(§5.1-5.4·EV-004 노른자)·`replay_or_
  substitution_detected`+`capability_and_permit_single_use`+`exact_binding_holds`(§5.5-5.7·EV-005)·
  `credential_route_authority_disjoint`(§6.1·predicate-only). **∅ 양방향**(∅ signer set 거부·∅
  active-principal deny-all 안전상태·∅ restrictive-event availability, §4.7)·**집합 양방향**
  (distinct signers vs 중복 dedup·LEADER 단독 거부, §4.7). 앵커: EGRESS-INV-001..014·EGRESS-
  AC-001..012·EGRESS-EV-001..013(§0.4h). **bounds 실측**: EGRESS-owned `B_egress_hard_fence`
  (line 170)·`B_capability_claim_to_send`(line 163) + 전파 bound(line 135/142/156) + `MAX_egress_
  currentness_proof_age_ms`(line 723) 전부 실재·null/TBD(candidate 신규 키 0건, §8.1). 선제 봉합:
  fail-open(all-false §4.3·vacuous-∅ §4.7 authority `lease_scope_exclusive` M1 상속)·∅ 양방향
  (§4.7)·**truthy-sentinel 구조 봉인(#13/#14 M1 선제 — `EgressAdmission`/`CommitProofValidity`/
  `RestrictiveLatchState` `__bool__ ⇒ TypeError`)**·집합 양방향(§4.7)·**malformed-model 자기방어
  (#20 — QCC 필수-None construction 거부·`model_construct` 우회도 술어 층 봉인, §2.3)**·**over-
  realization 경계(#7 반대 — 시리즈 최얇 L1 표면·런타임 보안 L1 오주장 금지, §1·§6b)**·**phantom
  타입 0**(전 인용 grep 실측·CUR/SCI/PTF/RLP/WDR/NT 미착지 코드 인용 0·필드-클래스 소유까지
  #15 M1 교훈)·verbatim+line·**병렬 레이스 봉합(#17/#19 — NT/CUR 병렬 착지 대비 subset allowlist,
  §7.1)**·**차원 비붕괴**(§3.5 — EGRESS QCC≠rcl commit-proof·QCC≠evidence receipt·egress-scope≠ioc
  conformance)·**과대 주장 금지**(닫는 EV 0·EV-L1-complete 금지·not-Phase-1 10행 정직 표기).
  **어떤 EV도 닫지 않음·acceptance 미선언·비준 기록 = "2026-07-26 운영자 위임 자동 비준(v1.1)".**

- **v1.1 (2026-07-26) — 독립 비평 리뷰 REVISE(CRITICAL 0·MAJOR 2·MINOR 3·gap 2) 반영, forward-only
  (오케스트레이터 직접 적용 — 저작자 세션 한도 사망으로 최종 self-check 미실행이 예고한 잔존
  인용 결함).** **MAJOR-1**: phantom 함수 `proof_binds_command`(6곳) → 실재 `mutation_fence_holds`
  (`ioc/predicates.py:492`; :502는 docstring 줄)로 전 교체. **MAJOR-2**: §8.1↔§8.2 소유권 모순 해소 —
  `MAX_egress_currentness_proof_age_ms`(VP:723)는 **CUR(-024) 소유·EGRESS는 주입 소비**(§8.1 결론·
  §10.2 item 12 정합화; "candidate 신규 키 0건" 결론 불변). **MINOR-1/2/3**: receipt.py verbatim
  → `:50-51`(모듈 자기한정 `:11-12` 병기)·필드 → `:141/143`·`writer_fenced` → `:507`. **gap 보강**:
  QCC 조건부 trial claim placeholder(ADR §11.1:308 — opaque optional scalar·RLP 이연)·**signer dedup
  해석 B 확정**(동일 identity 전 entry 합치 시에만 카운트 — 위조 entry 편승[해석 A fail-open] 차단,
  비용은 spurious-deny=가용성). 리뷰어 검증 확인: over-realization 봉인 성공·L1 슬라이스 non-vacuous
  (004 구조완전성·005 classify_record_pair)·EV 2/1/10 정확·ADR verbatim 문자 일치·VP 9키 실재.
  아키텍처(QCC 신규 소유·rcl/evidence/ioc 재저작 금지 경계·edge 0) 불변.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

1. **패키지 명명** `tos.egress`(register-prefix·head-noun·seam 정합) 승인. **[운영자 판단
   지점]**: `egress`가 register prefix EGRESS와 1:1이고 seam 토큰(capsule `egress_request_
   digest`·rcl `TransmissionCapability`)과 정합하며 미점유인지. naming은 load-bearing 아님(§7.1
   allowlist subset이 미래 형제 자동 배제).
2. **rcl = ADR-002-012 Commit Proof ≠ EGRESS QCC(§0.4b·§3.5 — 최대 아키텍처 공격 지점)**: rcl가
   quorum commitment 좌표를 *생산*, EGRESS가 QCC로 §11.1 claim-set을 *aggregate·구조 검증*이라는
   2층 관계가 정확한지·EGRESS↛rcl import 0·`writer_fenced`/`claim_capability`/`TransmissionCapability`
   재저작 0인지. **[리뷰어 공격]**: "EGRESS QCC가 rcl commit proof 중복" — 반론: ADR §5.7 line
   129 "bare Commit Proof necessary but not sufficient... full QCC claim set SHALL be satisfied"가
   2층 명시·rcl `records.py:249/428`가 commit-proof 좌표 소유·EGRESS는 aggregation-completeness+
   coordinate-currency+threshold-shape. 리뷰어: rcl `AuthoritativeSnapshot` `_REQUIRED_COVERED`
   (`records.py:428`) 좌표가 QCC에 주입 carry되는지 확인.
3. **over-realization 경계(§1·§6b — 이 문서의 최대 위험·최대 공격 지점)**: core 2행(004/005)의
   L1 술어가 **cryptographic validity·quorum consensus·bypass resistance를 주입 verified-flag/
   +Security로 정직 이연**하는지·`quorum_threshold_structurally_met`(§5.3)이 "주입 flag 위
   distinct-count 구조 판정"일 뿐 실 서명/consensus 검증이 아님을 명시하는지·not-Phase-1 10행이
   thin model property를 defense-in-depth로만 저작하고 **EV 미실현**을 명시하는지. **[리뷰어
   공격]**: "green `quorum_threshold_structurally_met`이 quorum commitment 증명인가" — 반론:
   §5.3이 서명(step 4)·eligibility·durability(step 3)를 +Security로 명시 이연·green은 carried
   claim-set이 quorum-shaped라는 구조 증명만. 리뷰어: `SignerCoordinate.signature_verified`가
   주입 `bool | None`(EGRESS가 계산 안 함)인지 확인.
4. **QCC ≠ evidence commit receipt(§0.4d·§5.4)**: evidence receipt(단일 signer·UNVERIFIED·
   all-false)가 QCC 대체 불가·`evidence_receipt_is_not_quorum_proof`가 §21.4 leader-receipt
   기각의 구조 실현인지·evidence `EvidenceCommitReceipt`/`SegmentCommitmentScheme` 재저작 0인지.
   **[리뷰어 공격]**: "§11 Commit-Proof가 evidence commit receipt 중복" — 반론: evidence
   `receipt.py:50-51(모듈 자기한정 :11-12)`가 UNVERIFIED/durability 축 자체 한정·§2 line 49 "durable local journal ≠
   quorum commit". 리뷰어: evidence `receipt.py:141/143` 단일 `receipt_signer_identity`·`receipt_
   signature` 확인.
5. **command conformance = ioc / capsule Bindings 경계(§0.4c/§0.4e)**: `exact_binding_holds`가
   ioc `derived_command_conformance` verdict + capsule `egress_request_digest`를 주입 소비(재저작
   0)하고 egress-scope 좌표(route/session/credential-gen) 등치만 추가하는지. **[리뷰어 공격]**:
   "exact-binding이 ioc/capsule 중복" — 반론: ioc=command↔proof 축·capsule=forward-reference·
   EGRESS=egress-scope terminal-equivalence·defense-in-depth. 리뷰어: ioc `predicates.py:502`
   `mutation_fence_holds`(`predicates.py:492`)·capsule `capsule.py:167` `egress_request_digest` 소유 확인.
6. **replay/substitution 노른자(§5.5)**: `classify_record_pair` REUSE로 same-id/different-bytes
   ⇒ CRITICAL_CONFLICT(substitution)·transplant(다른 principal/endpoint) 거부·id ⊥ digest 유지가
   정확한지. 리뷰어: canonical `classify_record_pair`·rcl `claim_capability` replay(`predicates.py:
   698-703`) 선례 대조.
7. **truthy-sentinel 구조 봉인(§4.7·§2.2)**: `EgressAdmission`/`CommitProofValidity`/`Restrictive
   LatchState` `__bool__ ⇒ TypeError`가 §7 회귀로 강제되는지 — 특히 **DENY/INVALID/DENY_LATCHED
   truthy fail-open**(거부를 허용으로 오독) 방지. 리뷰어: iap `_NonTruthyStrEnum`(`vocabulary.py:
   50-77`)·ioc `ConformanceResult`(`vocabulary.py:63`) 동형 확인.
8. **malformed-model 자기방어(§2.3·#20 교훈)**: `QuorumCommitCertificate` `model_validator`가
   필수-None(commit-proof 좌표·egress generation·signer 좌표)을 construction 단계에서 거부·
   `model_construct` 우회도 `quorum_commit_certificate_structurally_complete`(§5.1) 술어 층에서
   거부하는 2층 봉인인지. **[리뷰어 공격]**: 필수 None QCC를 `model_construct`로 만들어 complete-
   flag truthy 통과.
9. **all-false `AllFalseEgressAuthority`(§4.3)**: 5 flag 전부 False·`model_validator` any-True ⇒
   `ArtifactIntegrityError`·QCC/request/generation/external-activity가 authority 미보유가 rcl
   `AllFalseAuthority`(`_base.py`)·liveauth `LiveAuthorizationEffect`(`_base.py:75`) 동형인지.
   **[리뷰어 공격]**: QCC 보유가 transmission authority로 전환되는 경로.
10. **EGRESS-EV 3분류 재실측(§1)**: core 2행 {004·005}·predicate-only 1행 {001}·not-Phase-1
    10행 {002/003/006-013}이 register(csv line 149-160·371)와 정확 일치하는지·닫는 EGRESS-EV 0·
    EGRESS-AC 12행(§23, EV-001..012에만 1:1)·EGRESS-INV 14종·EGRESS-EV 13행. 리뷰어: register
    13행 tier 직접 재실측.
11. **∅ 양방향·집합 양방향(§4.7)**: ∅ signer set(거부)·∅ active-principal-set(deny-all 안전
    상태·오탐 금지)·∅ restrictive-event(availability)·distinct signers vs 중복 dedup·LEADER 단독
    거부 5방향이 전부 명시·회귀되는지. 리뷰어: authority `lease_scope_exclusive` non-empty M1
    선례가 `count >= N` vacuous 봉인에 상속됐는지 확인.
12. **bounds 실측(§8.1)**: EGRESS-owned `B_egress_hard_fence`(line 170)·`B_capability_claim_to_
    send`(line 163) + 전파(line 135/142/156) 전부 실재·null/TBD·candidate 신규 키 0건·형제
    `*_invalid_to_egress` 계열과 혼동 없는지(§8.2). `MAX_egress_currentness_proof_age_ms`(line
    723)는 **ADR-002-024(CUR) 소유 — EGRESS-owned 아님**(v1.1 MAJOR-2 정합; egress는 주입
    소비/verify 대상).
    리뷰어: VP line 135/142/156/163/170/723 직접 grep.
13. **firewall allowlist(§7.1)·병렬 레이스 봉합**: `closure ⊆ {canonical, ordering, egress}`·
    rcl/ioc/evidence/capsule **부재 assert**(재저작이지 import 아님)·subset이 NT/CUR/SCI/PTF
    병렬 착지를 자동 배제(거짓 "NT 부재" 하드코딩 없이·#17/#19 교훈)하는지·CUR/SCI/PTF/RLP/WDR/NT
    코드 인용 0(phantom 봉합)인지. 리뷰어: rcl `test_rcl_import_closure.py` subset 선례 대조·미착지
    상류 인용 부재 확인.

---

> **비준 기록**: 2026-07-26 운영자 위임 자동 비준(v1.1). 본 문서는 tos-spec을 수정하지 않으며 어떤
> EGRESS-EV/acceptance/비준도 선언하지 않는다(§0.2). 구현은 §9.1 순서로 별도 진행하며 적대적
> 코드 리뷰·게이트를 거친다.
