# TOS Safety Architecture Gate Status

- **Date:** 2026-07-14
- **Scope:** Consolidated RFC-002 v0.2 and ADR-002-001 through ADR-002-030
- **Architecture Documentation:** Phase B and the follow-on RCL consensus, final-egress security, safety-configuration governance, human-authority governance, evidence-integrity/replay, safe-start/recovery-barrier, Critical Input/decision-context, venue/session/tradability-constraint, Intent-to-order conformance, aggregate-risk evaluation, action-flow governance, independent proposal-approval, active-currentness, restricted-live/promotion, safety-deviation/residual-risk, safety-incident/controlled-shutdown, safety-telemetry/continuous-monitoring, software-supply-chain/runtime-artifact-admission, and post-trade economic-obligation/finality decisions are authored; acceptance cases are registered; every ADR remains Proposed and execution evidence remains open
- **Latest Architecture Review:** ADR-002-002 through ADR-002-030 PASS at document-review level; no independent review is pending; no status or live-readiness promotion
- **Verification Execution:** Not started
- **Production Authorization:** NO

---

## 1. Completed Design Artifacts

The following design decisions now have normative documents:

1. RFC-002 v0.2 consolidated architecture review
2. ADR-002-001 v0.2 consolidated Degraded-Mode Protective Capacity decision
3. ADR-002-002 Aggregate Risk-Capacity Commitment Model
4. ADR-002-003 Safety Authority Validity, Epoch Fencing, and Partition Behavior
5. ADR-002-004 Broker Capability Requirements and Fallbacks
6. ADR-002-005 Intent, Transmission Attempt, Broker Order, and Knowledge State Model
7. ADR-002-006 Evidence and Reconciliation Confidence Model
8. ADR-002-007 Live Authorization, Limit Governance, and Re-arm
9. ADR-002-008 Trustworthy Time Architecture
10. ADR-002-009 Failure-Domain Isolation and Deployment Safety
11. ADR-002-011 Protective Replacement and Protection-Gap Control
12. ADR-002-010 Corporate Actions and Non-Trade State Changes
13. ADR-002-012 Risk Capacity Ledger Persistence, Consensus, and Writer Fencing
14. ADR-002-013 Egress Gateway Credential, Route, and Commit-Proof Security
15. ADR-002-014 Hard Safety Envelope and Runtime Safety Profile Governance
16. ADR-002-015 Human Safety Authority, Dual Control, and Break-Glass Governance
17. ADR-002-016 Safety Evidence, Audit, and Deterministic Replay Integrity
18. ADR-002-017 Safe Startup, Recovery Barrier, and Conservative Resume Coordination
19. ADR-002-018 Critical Input Integrity, Provenance, and Decision-Context Fencing
20. ADR-002-019 Venue, Session, Tradability, and Broker Constraint Gate
21. ADR-002-020 Intent-to-Order Conformance, Canonical Command Construction, and Economic-Effect Fencing
22. ADR-002-021 Aggregate Risk Projection, Adverse-Scenario Evaluation, and Risk-Decision Integrity
23. ADR-002-022 Action-Flow Budgeting, Retry-Storm Containment, and Protective-Traffic Preservation
24. ADR-002-023 Independent Proposal Approval, Exact-Decision Binding, and Consumption Fencing
25. ADR-002-024 Active Currentness, Revocation, and Final-Egress Admission Fencing
26. ADR-002-025 Restricted-Live Verification, Progressive Scope Promotion, and Production Authorization Governance
27. ADR-002-026 Safety Waiver, Deviation, and Residual-Risk Governance
28. ADR-002-027 Safety Incident Declaration, Containment, Controlled Shutdown, and Closure Governance
29. ADR-002-028 Safety Telemetry Integrity, Continuous Conformance Monitoring, and Alert Escalation Governance
30. ADR-002-029 Software Supply-Chain Integrity, Release-Artifact Admission, and Deployment Provenance Governance
31. ADR-002-030 Post-Trade Economic Obligations, Settlement Finality, and Conservative Account-State Governance
32. VER-002-001 Safety-Critical Architecture Verification Evidence Specification
33. Evidence Register and configuration/evidence templates

---

## 2. Closed Architecture Questions

The current bundle decides:

- Risk Capacity Ledger is the sole serialization and mutation authority for capacity.
- each Capacity Domain uses one quorum-replicated deterministic Safety Commit Log; only quorum-durable committed state may create capacity or transmission authority.
- minority, stale, removed, restored, and conflicting RCL writers are fenced at consensus admission, state-machine mutation, and final egress.
- capability authorization and the final `ClaimCapabilityAndMarkSendStarted` transition are ordered against the exact committed capacity revision; a stale read or local cache cannot create permission.
- the Final Egress Trust Boundary is defined by actual possession of usable live-order authority plus a broker-order route; any downstream signer, proxy, queue, or session layer with independent broker effect inherits the full final-gate obligations.
- Commit Proof at egress is a quorum-sufficient certificate for the exact claim, request, principal, credential, route, and generation set; leader receipt, local journal, audit, or projection is insufficient.
- stale egress replacement, credential rotation, and recovery are deny-first and cannot activate a new generation until every predecessor path is hard-fenced or an approved expiry fence is positively proven.
- every normal send requires one complete action-scoped Safety Currentness Vector and one new non-authorizing Egress Currentness Proof ordered with the capability claim and `SEND_STARTED`.
- restrictive owner facts advance monotonic generation floors; final egress sets its local latch to `DENY_LATCHED` before convergence, and restriction does not depend on the normal permission path.
- a fence ordered before claim denies; an earlier or ambiguous claim remains potentially live and capacity-covered, with no blind retry or expiry-based release.
- broker reachability during currentness/control-plane partition does not preserve normal-risk authority; cache, TTL, heartbeat, health, or absence of invalidation is never currentness proof.
- restricted-live is one exact pre-registered real-broker experiment, not a softer production mode; low notional, canary naming, supervision, monitoring, or evidence collection never bypasses a normal safety or final-egress control.
- before a trial action, RCL covers the worst credible union of existing, planned, partial, potentially-live, external, protective, abort, and recovery effects; Trial Budget is a non-authorizing ceiling and never capacity or headroom.
- abort and demotion dominate evidence collection; trial completion, success count, elapsed time, incident absence, evidence-package creation, or recovery cannot resume a run, promote scope, or re-arm.
- Trial Evidence Packages and Production Scope Promotion Decisions are immutable non-authorizing artifacts; evidence applies only to exact exercised scope, negative results remain durable, and promotion is progressive, independent, single-use, break-before-make, and followed by fresh governed authorization.
- Safety deviations are exact, time-bounded, independently reviewed, non-authorizing artifacts; RFC-000, RFC-001's prohibited set, RCL/egress exclusivity, UNKNOWN conservatism, broker finality, economic continuity, fencing, segregation, independent HALT, evidence honesty, and no-auto-rearm form a Non-Waivable Boundary.
- residual-risk acceptance never marks an unmet requirement `PASS`; only one exact decision may be consumed to request separate restricted configuration, all interacting deviations are reviewed as one canonical Active Deviation Set, and expiry/revocation monotonically fences future authority without erasing economic effect.
- documentation, monitoring, audit, replay, priority, operator presence, capacity reservation, low notional, and incident absence are not compensating prevention; unknown or unbounded combined risk denies the deviation.
- material safety signals restrict the greatest credible dependency scope before administrative confirmation; Safety Incident Records, Active Safety Incident Sets, plans, messages, evidence, handoffs, and closure decisions are non-authorizing.
- incident containment and controlled shutdown use the existing Safety Authority, Human HALT, RCL, protective-classification, cancellation, currentness, and final-egress owners; incident priority and emergency labels create neither protective reserve nor a broker bypass.
- controlled shutdown denies and hard-fences future action while preserving potentially-live economic effect, RCL commitments, required protection, reconciliation, evidence, and recovery obligations; process death, disconnect, credential expiry, or queue deletion is not broker finality.
- incident closure is administrative only, handoff transfers no obligation until one exact Recovery Session accepts it, and neither closure, remediation, quiet time, replay, nor recovery can restore scope, clear HALT, release capacity, or automatically re-arm.
- every safety-critical software artifact is bound to exact reviewed source, dependency and toolchain closure, isolated build provenance, content-addressed registry custody, independent admission, one monotonic Release Generation, a complete Admitted Release Set, and actual runtime attestation.
- artifact admission is a non-authorizing negative gate; signatures, scans, tests, CI success, tags, registry presence, deployment health, cached admission, heartbeat, or absence of revocation cannot create capacity, authority, broker permission, readiness, scope promotion, or re-arm.
- rollback, restore, hotfix, mixed-version deployment, signer or registry compromise, runtime drift, and release-currentness failure restrict affected scope and require a new admitted generation; they never revive historical admission or economic authority.
- every possible or confirmed post-trade effect is represented as exact immutable Economic Obligation Records with field-specific finality, complete statement coverage, correction history, one monotonic Post-Trade Obligation Generation, and conservative RCL coverage.
- PTOL is the obligation-lifecycle serializer only; RCL remains the sole capacity mutation/serialization authority, final egress remains the external instruction boundary, and fills, Final Quantity Proof, statements, acknowledgements, dates, quiet time, or flat positions cannot manufacture finality or headroom.
- breaks, corrections, reversals, settlement/cash/collateral/borrow/custody uncertainty, stale writers, partition, restore, and recovery retain worst-credible capacity and never expire economic effect, revive authority, or automatically re-arm.
- Hard Safety Envelope and Runtime Safety Profile artifacts are immutable, authenticated, content-addressed, semantically canonical, separately governed, and bound as one closed Safety Configuration Bundle.
- profile activation is break-before-make and quorum-ordered by one exact Profile Generation; distribution, signatures, repository merge, deployment health, or an Activation Record alone do not arm live scope.
- partial, mixed, incompatible, stale, expired, restored, or rollback configuration fails closed; Restrictive Overrides can only narrow, never release capacity, erase economic effect, auto-revert, or re-arm.
- human dual control counts distinct effective natural persons rather than accounts, credentials, devices, sessions, role labels, or recovery paths.
- Approval Requests, Attestations, and Approval Sets bind one exact current context; a set is consumed once and is never configuration, capacity, protective-classification, Live Authorization, or broker-transmission authority.
- one current authenticated Human Safety Principal may invoke a monotonic restrictive HALT without a permissive quorum; break-glass can only deny, narrow, HALT, or request separately authorized containment.
- delegation, roster change, identity recovery, approval expiry/revocation, workflow recovery, or compromise cannot multiply quorum, erase economic effect, or automatically re-arm.
- risk-increasing re-arm, Live Authorization issuance, and production-scope promotion require two independent effective principals (RFC-001 SAFE-053), satisfiable by a two-natural-person quorum or the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1); the variant adds a fail-closed, scope-reduced satisfaction path and waives no non-waivable boundary, break-glass limit, or Hard Safety Envelope.
- safety evidence is source-attributed, immutable, causally linked, integrity-anchored, gap-detected, retention-governed, and replayed only in an isolated non-authorizing environment.
- exact pre-effect and `SEND_STARTED` evidence durability is required before risk-increasing first broker byte; an Evidence Commit Receipt proves custody only and creates no permission.
- evidence gaps, forks, restore conflicts, replay divergence, and evidence-service recovery fail closed, preserve economic effect, and cannot release capacity, clear UNKNOWN, or re-arm.
- every Safety Cell starts behind a closed Recovery Barrier; cold start, restart, reconnect, failover, restore, stale-owner detection, and material uncertainty advance a monotonic Recovery Generation before recovery work can be treated as current.
- only the current fenced Recovery Coordinator may assemble a dependency-complete Inventory Cut and Recovery Evidence Package; readiness is immutable, invalidatable, exact-scope assessment and never capacity, configuration, protection, Live Authorization, HALT-clear, broker-transmission, or re-arm authority.
- non-atomic broker inventory, UNKNOWN, missing ACK, cancel ACK without Final Quantity Proof, Evidence Gaps, timeout, conflict, and incomplete obligations remain conservative and block new risk; `READY_RESTRICTED` requires positive isolation from every shared dependency.
- every safety-relevant value is governed as a Critical Input with approved source identity/continuity, exact units/mappings, transformation lineage, measurable freshness, consistency-cut semantics, and correction/invalidation rules.
- immutable Critical Input Snapshots and Decision Context Capsules bind one exact context through proposal, independent approval, Intent, capacity, Live Authorization, capability, Commit Proof, evidence receipt, and final egress without giving the Context Integrity Service economic authority.
- shared source, parser, mapping, cache, administrator, identity, deployment, or failure domain is common mode rather than independent approval evidence; missing independence reduces live scope and cannot be waived by the proposer.
- final egress actively establishes current Critical Input Policy, Context Generation, permission-critical source continuity, Capsule age/scope, and invalidation status; TTL, heartbeat, service health, eventual consistency, or absence of correction is not currentness proof.
- correction, retraction, source/policy/mapping change, context expiry, restart, restore, or data recovery invalidates future permission but never releases capacity, expires economic effect, or automatically re-arms.
- every broker-directed action binds one exact current Venue Constraint Snapshot and Order Admissibility Decision covering venue/session/tradability, halt, price/tick/lot/quantity/order shape, account/margin/borrow/settlement, and Broker Capability Profile constraints.
- calendar time, quote flow, recent trades, connectivity, broker login, cached health, priority, or an exit/protective label never proves exact order executability or reserved protective capacity.
- material constraint change invalidates future permission through authority and final egress; decision or constraint expiry never erases economic effect, releases capacity, or revives live scope.
- every broker mutation is deterministically constructed from one exact approved Intent and closed Authorized Construction Envelope; construction is non-authorizing and cannot create capacity, protection, authority, transmission, or re-arm permission.
- the candidate Canonical Broker Command precedes venue and capacity decisions; the later Order Conformance Proof binds the unchanged command to the exact admissibility decision, conservative Economic Effect Envelope, and RCL commitment without cyclic authority.
- account, instrument, contract, route, side, position effect, quantity, unit, multiplier, currency, price, order type, time in force, expiration, flags, and operating mode cannot be silently defaulted, rounded, normalized, substituted, or changed after proof.
- final egress verifies the actual outbound representation after serializer, signer, queue, proxy, SDK, and route processing; cached `CONFORMANT`, type safety, broker acceptance, audit, or replay cannot substitute for prevention.
- every capacity request binds one complete current Aggregate Risk State Snapshot, approved Adverse Scenario Set, exact Economic Effect Envelope, deterministic conservative projected vector, and exact Aggregate Risk Decision before RCL commitment.
- netting, hedge, diversification, correlation, margin, collateral, or liquidity benefit is zero unless positively proven for the exact current scope; missing dimensions/scopes and numerical or scenario failure are restrictive.
- an Aggregate Risk `GRANT` authorizes only the exact RCL allocation request; it is not capacity or transmission authority, RCL remains the sole capacity mutation/serialization authority, and final egress actively fences stale risk decisions.
- every broker-directed submit, cancel, amend, replace, retry, query, reconnect, session, and administrative action is governed by one complete shared-scope Action Flow Policy, immutable cause lineage, and finite amplification envelope.
- an Action Flow `GRANT` authorizes only an exact RCL allocation request; the RCL alone commits and mutates economic and action-flow capacity and creates one exact single-use Action Flow Permit.
- missing ACK never creates retry permission, cancel ACK is not Final Quantity Proof, and permit expiry never expires possible broker or economic effect.
- Protective Flow Reserve is a proven exclusive RCL pre-commitment across request, queue, in-flight, credential, session, route, endpoint, and broker-rate dimensions; priority is not reserve.
- final egress actively verifies current Action Flow Generation, exact decision/vector/cause, RCL commitment, unused permit, broker constraint state, and protective lease; local token, TTL, heartbeat, connection health, queue priority, or absence of invalidation is insufficient.
- every ordinary exposure-increasing proposal is independently evaluated under one current Trading Approval Policy and Generation against a complete immutable request; `APPROVE` is deterministic, exact, and non-authorizing.
- the Intent Registry alone atomically consumes one current `APPROVE` decision into one immutable Intent and one Approval Consumption Record; duplicate, concurrent, stale-writer, union, widening, and replay paths cannot create another Intent.
- final egress actively verifies exact current approval request/decision/consumption/Intent lineage; cached `APPROVED`, Intent state, TTL, heartbeat, service health, or absence of invalidation is insufficient.
- human approval cannot replace automated independent approval, and automated approval cannot satisfy a human quorum; neither creates capacity, protective classification, Live Authorization, broker permission, or re-arm.
- restart, reconnect, queue drain, backoff expiry, counter refill, broker recovery, audit, or replay cannot revive an old permit, create headroom, or automatically re-arm.
- Aggregate Risk Authority owns policy evaluation but does not independently mutate capacity.
- stale capacity writers are fenced by monotonic epochs.
- Broker Adapter or broker-egress gateway is the final transmission enforcement point.
- Safety Authority uses a single current epoch per authority domain.
- stale Safety Authority instances cannot create new permissive authority.
- normal risk-increasing authority requires online currentness verification.
- degraded protective operation uses exclusive, pre-issued, monotonic-time-bounded leases.
- overlapping offline protective ownership is prohibited until hard fencing or expiry fencing.
- broker behavior is governed by a versioned, evidence-backed Capability Profile.
- uncertain broker transmission is not blindly retried.
- missing or contradictory broker capability reduces or prohibits live scope.
- cancellation acknowledgement alone is not Final Quantity Proof.
- documentation and replay do not substitute for runtime prevention.
- Intent, Transmission Attempt, Broker Order, Knowledge/Evidence, and Capacity are orthogonal state dimensions.
- reconciliation confidence is maintained per field with conservative bounds; a blended score cannot release risk.
- trustworthy time is an evidence-backed service with explicit continuity identity, bounded error, holdover, and fail-closed state transitions; direct wall-clock trust is prohibited.
- cross-host Time Health Snapshot age uses a consumer-local receipt anchor plus conservative transport uncertainty; issuer and consumer monotonic values are never directly subtracted.
- trustworthy-time restoration creates a new generation and cannot revive expired or invalidated economic authority.
- Recovery Readiness, Re-arm Approval, Live Authorization, and per-action Transmission Capability are separate artifacts with separate issuers and enforcement duties.
- health restoration, restart, failover, reconciliation, configuration change, or deployment cannot automatically re-arm risk-increasing live operation.
- re-arm requires explicit scoped human governance, fresh authority, current reconciled state, and final enforcement at broker egress.
- restrictive time, revocation, and HALT generations have explicit egress-containment bounds; an unfenced check-then-send path is prohibited.
- normal risk-relevant egress currentness uses a selected fenced single-use capability protocol: Safety Authority issuance through a linearizable Currentness Sequencer, a bounded authenticated currentness session, a monotonic deny latch, durable nonce claim plus `SEND_STARTED`, and a bounded claim-to-first-byte boundary.
- only the approved Egress Gateway may hold a usable live order credential and broker-order route; reconnect, cache recovery, or deletion of a restrictive flag cannot clear the deny latch or re-arm authority.
- failure-domain independence is an evidence-backed property; logical service separation, cache health, and redundancy count do not prove isolation.
- deployment, rollback, split-brain, credential, broker-session, and shared infrastructure common modes are explicitly allocated, fenced, and bounded by Safety Cell.
- protective replacement is one safety workflow that accounts for both protection gaps and simultaneous old/new execution before cancellation or submission.
- corporate actions and non-trade state changes are first-class economic events with conservative pre/post transition envelopes and RCL-only capacity remapping.

---

## 3. Repository Merge Map

The review files were section-level amendments, not canonical-document diffs. Their normative content was consolidated into the canonical RFC and ADR sections as follows.

### 3.1 RFC-002 v0.2

| Patch content | Canonical target | Conflict or duplicate resolved | Traceability update |
|---|---|---|---|
| Definitions | §3.1 Terminology | Removed the appended duplicate definitions; patch-local `3.x` became canonical `3.1.x` | SAFE-013, 015, 021, 025, 048 |
| Authority Matrix | §9.1 Authority Ownership | Separated risk policy grant from sole-ledger mutation and made broker egress the final send gate | SAFE-010, 011, 013, 015, 041, 048 |
| Component corrections | §10 Core Components | Defined Safety Profile Validator, Recovery Coordinator, Deployment/Identity, Replay/Evidence, and Cancellation Arbiter once | SAFE-003, 044, 045, 050, 052 |
| Orthogonal states | §12 | Replaced the unsafe mixed Intent/order/evidence/capacity enum; `RECONCILED` is evidence state | SAFE-020, 021, 025; ADR-002-005 |
| Capacity and release | §14 | Replaced generic cancellation release with Final Quantity Proof; expiry does not erase economic effect | SAFE-013, 015, 021, 024, 025 |
| Broker capability | §10.8 and §13.6 | Replaced generic capability assumptions with evidence-backed scoped profiles and no blind UNKNOWN retry | SAFE-021, 024, 025, 032, 033 |
| Partition and time | §16.5 and §17 | Added currentness checks, monotonic lease validity, restart invalidation, and writer/authority fencing | SAFE-035, 041, 048 |
| Protective capacity | §21 | Distinguished reservation from priority; added intermediate-state proof, replacement gaps, ownership, and cancellation arbitration | SAFE-001, 002, 040, 043, 048 |
| Failure domains and verification | §24 and §29 | Added common-mode allocation and measurable trigger/detection/containment/pass-fail obligations | SAFE-011, 041, 045, 048, 051, 052 |
| ADR backlog and findings | §26 and §31 | Preserved IDs ADR-002-002 through 030 and mapped A-01 through A-14 to canonical sections | Corrected the earlier erroneous “009 through 017” history note while later allocating canonical ADR-002-017 to safe startup/recovery, ADR-002-018 to Critical Input integrity, ADR-002-019 to venue/session/tradability constraints, ADR-002-020 to Intent-to-order conformance, ADR-002-021 to aggregate-risk evaluation, ADR-002-022 to action-flow governance, ADR-002-023 to independent proposal approval, ADR-002-024 to active currentness/final-egress admission, ADR-002-025 to restricted-live verification and production-scope promotion governance, ADR-002-026 to safety-deviation and residual-risk governance, ADR-002-027 to safety-incident and controlled-shutdown governance, ADR-002-028 to safety-telemetry and continuous-monitoring governance, ADR-002-029 to software-supply-chain and runtime-artifact admission governance, and ADR-002-030 to post-trade economic-obligation and finality governance |

### 3.2 ADR-002-001 v0.2

| Patch content | Canonical target | Conflict or duplicate resolved |
|---|---|---|
| Amended decision and terms | §3 and §3.1 | Consolidated aggregate commit versus protective consume; removed appended definitions |
| Resource guarantees | §4 and §12.4 | Replaced “reserve or prioritize” ambiguity with evidenced guarantee levels |
| Protective proof | §6 | Replaced final-state-only classification with conservative intermediate-state proof |
| Partition lease | §9 and §12 | Prohibited new partition-time commitment; added exclusive epoch-fenced monotonic lease consumption |
| Ownership and replacement | §11 | Added one Cancellation Arbiter, safety-owned order protection, and measured Protection Gap |
| Potentially-live release | §14 | Added UNKNOWN, partial-fill, cancel/late-fill, and Final Quantity Proof rules |
| Exhaustion and shared capacity | §12–§14 | Added dynamic sufficiency, multi-account minimums, and bounded retry |
| Verification and acceptance | §20–§21 | Preserved Proposed status and distinguished written cases from executed reviewed evidence |

### 3.3 Conflict and Numbering Disposition

- RFC-000 was not changed because no contradiction was found.
- Patch-local section numbers are provenance only; canonical section numbers now govern.
- ADR IDs remain ADR-002-001 through ADR-002-030; ADR-002-002 through ADR-002-030 remain Proposed.
- Every `SAFE-xxx` identifier in the RFC-002 and ADR-002-001 traceability tables exists in RFC-001.
- The Evidence Register contains 363 `NOT_IMPLEMENTED` items, including one-to-one STATE, RECON, TIME, REARM, FD, PR, NT, RCLP, EGRESS, SPG, HAG, ERI, SBR, CII, VTG, IOC, ARE, AFG, IAP, CUR, RLP, WDR, SIR, STM, SCI, and PTF coverage for ADR-002-005 through ADR-002-030. Registration created no verification evidence or live authority.

### 3.4 DR-0001 Single-Operator Live Governance (CR-02, option (c))

DR-0001 adopts CORPUS-REVIEW-0001 CR-02 option (c). The following patches were consolidated into the canonical documents named below. No numbered section was renumbered; all additions are additive.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| Independent re-arm/promotion approval parent | RFC-001 §10 SAFE-053 (new); §12 matrix (CONST-005/011/013 → SAFE-053); §18 v0.4 | RFC-001-Patch-0008; resolves the philosophy §35 hierarchy inversion — the ADR-002-015 obligation now has a Safety-Case parent |
| Governed Single-Operator Re-Arm Variant | ADR-002-015 §5.10–§5.12, HAG-INV-015..019, §17.1, §27 (SAFE-053 row), §30 Review History; header v0.2 | PATCH-ADR-002-015-v0.2; refines SAFE-053; Non-Waivable Boundary, break-glass, and Hard Safety Envelope unchanged |
| Recognition as an added satisfaction path | ADR-002-025 (RLP-INV-014, §7, §11(10), §22); ADR-002-026 (WDR-INV-007, §7, §12); ADR-002-027 (SIR-INV-016, §7, §20(10)); each header v0.2 + Review History | PATCH-ADR-002-025/026/027-v0.2; obligation not relaxed; ADR-002-026 restricted to deviations outside the Non-Waivable Boundary |
| Governance decision record | decision-records/DR-0001-Single-Operator-Live-Governance.md (new) | vision.md, philosophy.md, and RFC-000 unchanged |

The variant's armable scope is bound to the smallest explicitly approved scope delta (Progressive Promotion step) declared for the variant under ADR-002-025 §5.11 and may be narrower than a two-natural-person quorum could arm. RFC-000 is not amended in this wave; a dedicated constitutional bounded-human-authority principle (the RFC-000-level parent of SAFE-053) is owed to a later wave.

### 3.5 CORPUS-REVIEW-0001 Wave 2 (Theme A/B — constitutional fidelity and safety-case coverage)

Wave 2 resolves CORPUS-REVIEW-0001 Theme A (M-01..M-04) and Theme B (M-05..M-06). The following patches were consolidated into the canonical documents named below. No numbered section was renumbered; all changes are additive except the in-place rewording of CONST-004's constraint and of CONST-008's requirement, constraint, failure scenario, and the §6 Authoritative Source definition.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| Seven-tier North Star precedence + mapping table; CONST-003 subordinated to integrity | RFC-000 §5 Constitutional Precedence | RFC-000-Patch-0009; resolves M-01 |
| CONST-004 safe-state constraint made actor-neutral (autonomous or human-authorized) | RFC-000 CONST-004 §7 | RFC-000-Patch-0009; resolves M-02; aligned with CONST-012 and the §6 safe-state definition |
| CONST-015 Bounded Human Authority (new); constitutional parent of SAFE-053 | RFC-000 §7 (new CONST-015); §5 mapping table | RFC-000-Patch-0009; resolves M-03; discharges the RFC-000 parent owed by DR-0001 §6 without reintroducing an absolute two-natural-person rule |
| CONST-008 reframed in evidence terms + §6 Authoritative-State term table | RFC-000 CONST-008 §7; §6 Definitions | RFC-000-Patch-0009; resolves M-04; RFC-001 §5.1 is now a discharge of, not a reinterpretation of, CONST-008 |
| SAFE-053 gains parent CONST-015; §12 matrix CONST-015 row | RFC-001 §10 SAFE-053 Derived-from; §12 matrix; §18 v0.5 | RFC-001-Patch-0010; completes M-03 wiring |
| HAZ-024 Operator/Human Configuration or Authorization Error (new) | RFC-001 §9; SC-010; §12 matrix | RFC-001-Patch-0010; resolves M-05; distinct from HAZ-021 |
| HAZ-025 Final-Egress defect + SAFE-054 Out-of-Band Containment (new) | RFC-001 §9; §10 SAFE-054; SC-050 note; §12 matrix; §13.6 blocker | RFC-001-Patch-0010; resolves M-06; capability-neutral, no broker named |

CONST-015 discharges the constitutional bounded-human-authority principle that §3.4 recorded as "owed to a later wave"; SAFE-053's requirement text is unchanged (only its Derived-from parent set is extended), consistent with DR-0001 §6. The two-natural-person quorum and the Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1) remain the two lawful SAFE-053 satisfaction paths; CONST-015 does not mandate any number of natural persons. vision.md and philosophy.md are unchanged.

### 3.6 CORPUS-REVIEW-0001 Wave 3 (evidence-gate binding, hazard-coverage completeness, and traceability instantiation)

Wave 3 resolves review items M-09 through M-12 and mn-01 through mn-06. The following patches were consolidated into the canonical documents named below. No numbered section was renumbered except the in-place correction of the ADR-002-002 §11.4 duplicate step number; all other changes are additive.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| ADR-002-001 §21 acceptance criteria bound to discharging evidence; consolidated `ADR-002-001` approval gate added to VER §380 | ADR-002-001 §21, §25 Review History (v0.3); VER-002-001 §380 | PATCH-ADR-002-001-v0.3; M-09; criteria #1/#11 PARTIAL → §4.4 debt |
| EVIDENCE-REGISTER-002 Gate Rule rewritten as an explicit accepting-state whitelist cross-referencing VER §4 | EVIDENCE-REGISTER-002 Gate Rule | M-10; no register row changed (count 363) |
| §12 Constitutional Verification Matrix extended so HAZ-016..025 appear against their bases; HAZ-010 removed from CONST-015; SAFE-042/046 Derived-from += CONST-015 | RFC-001 §10 (SAFE-042/046), §12, §18 Review History (v0.6) | RFC-001-Patch-0011; M-11 |
| New instantiated bidirectional coverage matrix; VER approval gate points to it | verification/TRACEABILITY-MATRIX-002.md (new); VER-002-001 §383 | RFC-001-Patch-0011; M-11 |
| IMPLEMENTATION-PLAN-002 count/range refreshed to 363 and ADR-002-001..030; ADR-002-030 post-trade role, phases, and decision item added | verification/IMPLEMENTATION-PLAN-002.md | M-12; register count held at 363 pending Part-2/3 consolidation |
| Mechanical corrections: ADR-002-002 §11.4 step renumber; X-EV-001..012 `Supports:`/`Injection:` fields and X-EV-001 enumerated pass criterion; EGRESS-EV-002 containment wording | ADR-002-002 §11.4, §40 Review History; VER-002-001 §66–77 and EGRESS-EV-002 | mn-01, mn-05, mn-06; X-EV-002/003/005/006/008 also bound to ADR-002-001 |

The mn-02 finding (EVIDENCE-REGISTER-002.csv quoting/alignment) was re-verified and closed as **verified-resolved**: the CSV is RFC-4180-conformant (363 data rows, every row 16 fields, zero misaligned); no edit was made and the file is unchanged. The M-09 §21↔evidence mapping, the mn-05/mn-06 reworded criteria, and the HAZ-010/CONST-015 remove-vs-keep decision are recorded as EV-L0 review items in RFC-001-Patch-0011 and PATCH-ADR-002-001-v0.3. vision.md, philosophy.md, RFC-000, and RFC-002 are unchanged in this wave.

### 3.7 CORPUS-REVIEW-0001 Wave 4 (CR-01 — Part-2/3 register consolidation)

Wave 4 resolves CORPUS-REVIEW-0001 CR-01: it instantiates the Part-2/3
verification track, discharges the §4.2/§4.3/§4.4 Part-1 evidence debt, promotes
the narrow-only meta-principle to RFC-000 §12, and instantiates the reserved
`DEC-xxx` / `TEST-xxx` namespaces. No numbered section was renumbered; the
VER-002-001 case sections were appended as §§384–392 so the §380/§383
cross-references are preserved.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| New development-track verification specification and register (96 items: 90 ADR-DEV invariants + DEC-EV-001..005 + TEST-EV-001) | part-3-development/VER-DEV-001-Development-Track-Verification-Evidence-Specification.md; part-3-development/verification/EVIDENCE-REGISTER-DEV.{md,csv}; SUMMARY.md | CR-01; independent of the Part-1 count |
| Narrow-only governance meta-principle; DEC-003 / TEST-001 instantiation; CONST-003 composite discharge | RFC-000 §12, §5 reserved-namespace note, CONST-007, CONST-014, CONST-003; header/Review History v0.13 | RFC-000-Patch-0012; residual items in §4.5 |
| Part-1 evidence debt discharged: nine new rows (HAG-EV-013..018, EGRESS-EV-013, PRD-EV-001/002); count 363 → 372 | EVIDENCE-REGISTER-002.{md,csv}; VER-002-001 §§384–392 and §380 gates (ADR-002-001/013/015); ADR-002-001 v0.4 §21/§25; TRACEABILITY-MATRIX-002 | CR-01; SAFE-053/054 UNMAPPED resolved |
| Part-2/3 RFC DEC/TEST narrow-only traceability rows | RFC-003 §15, RFC-004 §14, RFC-005 §15, RFC-006 §16, RFC-007 §15, RFC-010 §13 | CR-01; RFC-003/RFC-006 also carry CONST-003 notes |
| IMPLEMENTATION-PLAN-002 count refreshed to 372; DEV register recorded | verification/IMPLEMENTATION-PLAN-002.md | CR-01 |

The Wave-4 EV-L0 review items (each MUST record reviewer provenance —
model/substrate/determining inputs — per ADR-DEV-005; M-18) are: (1) DEV-row
uniform `Critical` criticality vs per-family `High`; (2) per-family Minimum-Level
defaults, especially AIR/BFA EV-L0/L1 and TAB's runtime-monitoring boundary;
(3) SAFE-054 home (EGRESS-EV-013 chosen vs a new OBC family); (4) HAZ-024 anchor
(HAG-EV-018 chosen vs a cross-system case); (5) PRD as a new ADR-002-001-owned
family (chosen vs folding into SPG/BC); (6) the DEC-003 → RFC-004 venue mapping
satisfying CONST-007's intent; (7) M-18 reviewer-provenance compliance for all
Wave-4 artifacts; (8) narrow-only placement §12 (chosen) vs §5 and clause vs a
new CONST-016; (9) per-case Probe/Injection/Expected wording fidelity to each
source invariant.

### 3.8 CORPUS-REVIEW-0001 Wave 5 (Theme E — decision-output semantics; mn-08/mn-09)

Wave 5 resolves CORPUS-REVIEW-0001 Theme E (M-13, M-14, M-15) and mn-08/mn-09. All changes are
narrow-only and additive; no numbered section was renumbered, and vision.md, philosophy.md,
RFC-000, and every Part-1 document are unchanged. No SAFE-xxx requirement or numeric bound was
introduced. RFC-003, RFC-006, and ADR-DEV-007 move to v0.2.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| M-13: no-action (hold) vs explicit flat (target=0) defined as distinct reproducible auditable outcome types, with a type-aware restrictive default (a reduction routes through ADR-002-001 §6 protective classification; hold blocks new risk); §16 Q4 resolved | RFC-003 §7, §9, new §9.1, §16 Q4; header/Review History v0.2 | RFC-003-Patch-0013; adopts ADR-DEV-007 SOS-INV-001 at the decision layer; grounds in CONST-012, philosophy §39.4; introduces no SAFE-xxx |
| M-15: LLM/stochastic Critical-Input proviso — recorded-response reproducibility satisfies audit but not SAFE-034 independent recomputation; a Critical-Input LLM value is non-approvable (restrictive), soft-evidence only; §16 Q3 reformulated and resolved | RFC-003 §10, §16 Q3; header/Review History v0.2 | RFC-003-Patch-0013; cites SAFE-034, ADR-002-018 §13, ADR-002-023; introduces no SAFE-xxx |
| mn-08: portfolio reasoning at Interpretation, per-target semantics at emission/approval binding; §16 Q1 resolved | RFC-003 §9/§9.1, §16 Q1; header/Review History v0.2 | RFC-003-Patch-0013; cites ADR-DEV-007 SOS-INV-002/006, ADR-002-023 |
| M-14: new SOS-INV-006 (vector component interdependence declared; undeclared atomic, fail-closed; partial approval of an atomic vector → whole-vector non-realization + strategy re-evaluation); §10 "represent gracefully" replaced; declared-coverage-vs-mistaken-omission sharpened (no SOS-INV-007) | ADR-DEV-007 §1, §5, §6 (SOS-INV-006), §8, §10, §11.5, §12.7, §13, §14; header/Review History v0.2 | ADR-DEV-007-Patch-0014; safety floor held by ADR-002-021 aggregate projection (M-14 mitigant confirmed); SOS-INV-006 adds intent-fidelity only; introduces no SAFE-xxx |
| M-14 sync: SOS-EV-006 added; ADR-DEV-007 gate now requires SOS-EV-001..006; invariant→evidence coverage 90 → 91; development-track total 96 → 97 | VER-DEV-001 §1/§5/§6/§7/§8; EVIDENCE-REGISTER-DEV.{md,csv} | ADR-DEV-007-Patch-0014; independent of the Part-1 count; all rows `NOT_IMPLEMENTED`. Note: RFC-002 §26's "(96 items)" is the Wave-4 establishment figure and is preserved as history; the current development-track total is 97 per this row |
| mn-09: unhedged overnight gap (RFC-007 §13 binding constraint) accepted as an explicit input to the tail methodology | RFC-006 §14 (and §15 pointer); header/Review History v0.2 | RFC-006-Patch-0015; one-line link; introduces no SAFE-xxx |

The Wave-5 EV-L0 review items (each MUST record reviewer provenance — model/substrate/
determining inputs — per ADR-DEV-005, M-18; none is self-reviewed by the author) are:
(1) SOS-INV-007 excluded — the declared-coverage-vs-mistaken-omission distinction folded into
ADR-DEV-007 §8 prose rather than a seventh invariant; (2) RFC-003 §16 Q3 marked
resolved-with-narrowed-residual (soft-evidence boundary deferred to RFC-004) rather than left
precise-open; (3) the decision-layer adoption of ADR-DEV-007 SOS-INV-001/002/006 as a
parent-to-child citation; (4) placement of the hold/flat taxonomy in a new RFC-003 §9.1 versus
inline in §9; (5) SOS-INV-006's cross-reference into RFC-003 §9.1 for the atomic-vector
re-evaluation (M-13 ↔ M-14 mutual consistency); (6) mn-09 tail-input placement in RFC-006 §14
versus §7 tail caveats. Patch documents (RFC-003-Patch-0013, ADR-DEV-007-Patch-0014,
RFC-006-Patch-0015) are recorded in the git-excluded patches/ per the repository convention;
this section is the committed merge record.

### 3.9 CORPUS-REVIEW-0001 Wave 6 (seam-sealing)

Wave 6 seals cross-ADR and cross-part seams identified in CORPUS-REVIEW-0001. All changes
are narrow-only and additive; no numbered section was renumbered, and vision.md,
philosophy.md, and RFC-000 are unchanged. The canonical documents already carry the changes;
the following table is the committed merge record.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| M-07: §6.2 Intermediate-State non-worsening test anchored to the no-protective-action counterfactual; §6.1 already-exceeded clarification; new §8.3.1 CONTAINED emergency-action proof standard (reduce-only by construction over the reconciled structure); §20.11 aligned; ADR-002-019 added to §23.3 Dependencies | ADR-002-001 (0.4 → **0.5**) | Patch 0016; introduces no SAFE-xxx and no new EV (count stays 372); M-07 scenario debt below |
| M-08: partition-time lease-admissibility rule — §3.1.2 bounded pre-proven admissibility scope + staleness tolerance and §9 owning rule (overlap-first / add-only within scope; cancellation-involving replacement outside scope prohibited during partition) | ADR-002-001 §3.1.2/§9 owns (**0.5**); ADR-002-011 §5 (— → **0.2**) and ADR-002-019 §19 (— → **0.2**) cross-reference | Patches 0016/0017/0018; introduces no SAFE-xxx and no new EV; M-08 scenario debt below |
| Capability class: §13.15 composed-consequence minimal partition-time protective class ({§13.11; §13.12; §13.10} composed with ADR-002-009 §10.1, ADR-002-001 §5, ADR-002-003 §11.3) reduces to HALT + operator escalation | ADR-002-004 §13.15 (— → **0.2**) | Patch 0019; Broker Capability Profile dimension language, no broker named; scope-reducing; no SAFE-xxx and no new EV (within BC-EV-016 / FD-EV-008 / VTG-EV-010) |
| M-19: Proposal bound — unchanged — into the ADR-002-023 §5.3 Proposal Approval Request (§9); §5 "candidate" → "provisional"; ADR-002-023 §5.3 informative back-reference | RFC-003 §5/§9 (0.2 → **0.3**); ADR-002-023 §5.3 (— → **0.2**) | Patches 0020/0021; introduces no SAFE-xxx and no new EV |
| M-21: admitted ≠ promotable — §4 non-scope bullet, §8 clause, new §8.1 Authoring-to-Live lifecycle; live promotion owned by ADR-002-025 | ADR-DEV-004 §4/§8/§8.1 (0.1 → **0.2**) | Patch 0022; no new APA-INV, no new APA-EV, no SAFE-xxx; DEV count stays 97 |
| M-22: §14 Open-Questions status hygiene — a `Proposed` ADR-DEV *addresses* but does not *resolve* a question; stale "unwritten" clauses removed | RFC-008/009/010/011 §14 (each 0.1 → **0.2**) | Patches 0023/0024/0025/0026; introduces no SAFE-xxx and no new EV |
| mn-16: RFC-010 demonstrates only the authoring-track subset of the Vision §9.5 list; execution-layer/architecture items owned by VER-002-001 families (e.g. RC-EV-006, BC-EV-005); §9 identity SHALL attributed upstream to ADR-DEV-002 / ADR-002-029 | RFC-010 §4/§9 (**0.2**) | Patch 0025; introduces no SAFE-xxx and no new EV |
| M-23: Monitor Coverage Manifest assumption-derived intake (Monitored Assumption); ADR-DEV-011 open-coordination-dependency flipped to a defined §9 intake with monitoring evidence still owed | ADR-002-028 §9 (— → **0.2**); ADR-DEV-011 TAB-INV-006/§8/§12.5 (0.1 → **0.2**) | Patches 0027/0028; flips a dependency status, adds no obligation ID; no SAFE-xxx and no new EV (STM-INV-002 / STM-AC-001; DEV count stays 97) |
| mn-13: conditional ADR-002-025 dimension added to the §9 Safety Currentness Vector, aligning it with the §12 Egress Currentness Proof binding and ADR-002-025 §13 | ADR-002-024 §9 (— → **0.2**) | Patch 0029; consistency fix; no SAFE-xxx and no new EV (CUR-INV-001 / CUR-AC-001) |
| M-20 / mn-18 / mn-14: `preface.md` filled — derivation + governance-precedence map carrying every layer on both axes, effective-state guidance, backward-only `Depends On` convention, broker-agnosticism rule | `src/preface.md` (new; non-normative) | Direct edit (in this subsection); harmonizes vision §7.7 and RFC-000 §12; no EV impact; `SUMMARY.md` already links it |

> Wave 6 seals cross-ADR/cross-part seams. All changes are narrow-only and additive;
> vision.md, philosophy.md, and RFC-000 are unchanged. No SAFE-xxx requirement or numeric
> bound is introduced, and the Evidence Register counts are unchanged (Part-1 372; Part-2/3
> 97). ADR-002-001 → v0.5; RFC-003 → v0.3; ADR-DEV-004/011 and RFC-008/009/010/011 → v0.2;
> ADR-002-004/011/019/023/024/028 receive a Version field (0.2) and Review History on first
> patch, per the ADR-002-025/026/027 precedent (§3.4).
>
> **Wave-6 evidence debt (no new EV IDs; scenario extensions within existing families):**
> * **M-07.** The intermediate-state proof (PR-EV-005, RC-EV-016, ARE-EV-003), §20.11, and
>   trapped-exposure (RC-EV-014, §20.7) verification scenarios are owed an extension covering
>   the already-exceeded-envelope regime (ADR-002-002 §23.2) and the §8.3.1 CONTAINED
>   by-construction emergency-action path. Discharged within those existing families; no new
>   EV row; count stays 372.
> * **M-08.** SA-EV-004/005/006 (lease validity), VTG-EV (admissibility), and
>   PR-EV-001/002/006/012 (replacement) are owed a partition-time pre-proven-admissibility-scope
>   + staleness-tolerance validity scenario. Discharged within those existing families; no new
>   EV row; count stays 372.

Patch documents 0016 through 0029 are recorded in the git-excluded `patches/` per the
repository convention (each born-MERGED, pointing here); this subsection is the committed
merge record. The Wave-6 changes are EV-L0 review items — most load-bearing, the M-07
no-protective-action-counterfactual anchor — with reviewer provenance to be recorded per
ADR-DEV-005 (M-18).

---

### 3.10 CORPUS-REVIEW-0001 Wave 7 (final wave: AI-on-AI review, review depth, provenance, credible state space, complexity register, mode-transition matrix)

Wave 7 closes the remaining CORPUS-REVIEW-0001 items. All changes are narrow-only and
additive; no numbered section was renumbered, and vision.md and philosophy.md are unchanged.
The only evidence-count change anywhere is the development-track total moving **97 → 98**
(BFA-EV-007, M-17); the Part-1 count is unchanged at 372. The canonical documents already
carry the changes; the following table is the committed merge record.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| M-16: AI-on-AI review presumption inverted for the review of an AI-*authored* artifact (proponent SHALL affirmatively demonstrate decorrelation, else common-mode, fail-closed); human-in-the-loop independent review normativized (SHALL) at the ADR-002-025 production gate | ADR-DEV-005 §7/§9/§10.7/§12.2/§14 (0.1 → **0.2**) | Patch 0030; amends existing AIR-INV-002 + a §9 binding on existing evidence (AIR-EV-002/-005, HAG-EV-016, RLP-EV-008); **no new AIR-INV, no new AIR-EV**, no SAFE-xxx; DEV count unaffected by this item |
| M-17: BFA-INV-007 (per-artifact review depth is evidenced; family similarity is not a warrant) + paired BFA-EV-007; ADR-DEV-006 gate now requires BFA-EV-001..007; invariant→evidence coverage 91 → 92; development-track total **97 → 98**, BFA family 6 → 7 | ADR-DEV-006 §1/§6/§7/§8/§12/§13/§14 (0.1 → **0.2**); EVIDENCE-REGISTER-DEV.{md,csv}; VER-DEV-001 §1/§5/§6/§7/§8 | Patch 0031; independent of the Part-1 count; all rows `NOT_IMPLEMENTED`. Note: RFC-002 §26's "(96 items)" and §3.7/§3.8's Wave-4/Wave-5 figures are preserved as history; the current development-track total is 98 per this row |
| M-18: EV-L0 reviewer-provenance obligation added (model/substrate + determining inputs per ADR-DEV-005 §7), applying to the corpus's own specification reviews and these gate-status merge records | VER-002-001 §5 (EV-L0), §9.5 (sign-off provenance SHALL); dated header note | Patch 0032; no new EV; VER-DEV-001 already inherits the obligation by citing VER-002-001 §5 for evidence-strength levels (§2), so provenance inherits automatically — confirmed, no VER-DEV-001 edit required |
| M-24: Credible State Space defined at the architecture tier (RFC-002 §3.1.17) — bounded by the active Broker Capability Profile (ADR-002-004) and the approved Adverse Scenario Set (ADR-002-021) — and bound into the ADR-002-011 §9 and ADR-002-012 §18 "credible"/"worst credible" universals and the ADR-002-001 §6.2 protective universal; VER-002-001 §2.7 Coverage Argument for universally-quantified claims added, with a §374 pointer | RFC-002 §3.1.17 (0.2 → **0.3**); ADR-002-011 §9 (0.2 → **0.3**); ADR-002-012 §18 (— → **0.2**, Version field added); ADR-002-001 §6.2 (0.5 → **0.6**); VER-002-001 §2.7/§374 | Patches 0033/0034/0035; no new SAFE-xxx, no numeric bound, no new EV (Part-1 count stays 372) |
| M-25: Complexity Justification Register created (discharges RFC-000 AX-005 via philosophy §24's six questions across eight load-bearing mechanisms); every cell cites an existing HAZ/SAFE/ADR/EV, unanswered cells marked OPEN (Q5 consolidated operator-degraded-state view and Q6 safe removability are OPEN corpus-wide; egress single-point carries the M-06 residual) | `part-1-foundation/COMPLEXITY-REGISTER-002.md` (new; **non-normative**); SUMMARY.md | Direct edit; creates no verification evidence, acceptance, or live readiness; **adds nothing to either evidence count** (Part-1 372; development track 98) |
| M-26 / M-07-3: RFC-002 §20.1 Mode-Transition Matrix — derived restrictive/restorative edges, the RECOVERY-transit rule, and forbidden transitions normativized; the §6.2→§8.3.1 CONTAINED emergency-action routing authority resolved (M-07-3); three underivable edges marked UNRESOLVED (see Wave-7 debt below) | RFC-002 §20.1 (**0.3**) | Patch 0033; no SAFE-xxx, no numeric bound; only derived edges normativized, no edge invented |
| M-07-2 (Wave-6 deferred): §8.3.1 bullet-2 parenthetical reworded so it no longer implies a live §6.2 test in CONTAINED (established at approval time for the pre-approved emergency-action set) | ADR-002-001 §8.3.1 (**0.6**) | Patch 0035; folded into the ADR-002-001 v0.6 patch with the M-24 §6.2 cross-reference; no SAFE-xxx, no new EV |
| Minors: **mn-10** operator-as-granting-authority limited to ADR-002-015 quorum / §17.1 variant membership; **mn-11** External-Value Validity Window must be *adequate* to the source's real currentness (ADR-002-018 CII-INV-005/006); **mn-12** trapped-exposure representation added to the re-arm checklist as a complementary item (not a tenth reconciliation confirmation — "nine reconciliation items" preserved); **mn-15** RFC-000 §12 governance hierarchy harmonized (ADR + Verification Evidence tiers, intra-tier tie-break, recorded-status precedence); **mn-17** operator scoped residual-risk acceptance distinguished from the System Owner's final acceptance; **Wave-5-deferred** RFC-003 §10 Critical-Input classification is fixed by ADR-002-018, not the proposer | ADR-DEV-014 §5 (0.1 → **0.2**); ADR-DEV-003 §6/§8 (0.1 → **0.2**); ADR-DEV-012 §7 (0.1 → **0.2**); RFC-000 §12 (0.13 → **0.14**); RFC-011 §5 (0.2 → **0.3**); RFC-003 §10 (0.3 → **0.4**) | Patches 0036–0041; each narrow-only and additive; no SAFE-xxx, no numeric bound, no new EV; RFC-000 change is confined to §12 (the H1 governance hierarchy), vision/philosophy untouched |
| G-02..G-05 scoped-future-specification gaps registered; G-01 recorded resolved | ARCHITECTURE-GATE-STATUS §4.6 (new subsection) | Direct edit; gap registration only — no ADR authored, no SAFE-xxx, no new EV |

> Wave 7 closes CORPUS-REVIEW-0001. No new SAFE-xxx requirement or numeric bound is
> introduced; no broker proper noun appears; vision.md and philosophy.md are unchanged. The
> Part-1 Evidence Register count is unchanged (372); the development-track count moves 97 → 98
> (BFA-EV-007 only). Historical counts are preserved: RFC-002 §26 "(96 items)" and §3.7/§3.8
> remain as Wave-4/Wave-5 history.
>
> **Wave-7 debt (M-26 UNRESOLVED mode-transition edges; no new EV IDs):**
> * **U1 (substantive).** CONTAINED → DEGRADED_PROTECTIVE inter-protective de-restriction: no
>   ADR fixes the trigger/guard/owner. Marked UNRESOLVED in RFC-002 §20.1 D; a conservative
>   default is inferable by principle but not normatively fixed. **DISCHARGED (Wave 8):**
>   resolved by a new normative decision — ADR-002-001 §8.5 (governed, never-automatic,
>   Safety-Authority-owned de-restriction; grants no new-risk/live authority; fail-closed to
>   CONTAINED; revocable); RFC-002 §20.1 D updated. Scenario-extension debt within SA-EV/FD-EV;
>   no new EV; Part-1 stays 372. Patches 0043/0044; merge map §3.11.
> * **U2 (partial).** LIVE_RESTRICTED → LIVE_NORMAL §14 in-place readiness-refresh extent is
>   not enumerated. Marked UNRESOLVED (partial). **DISCHARGED (Wave 8):** resolved by
>   enumeration in ADR-002-007 §14.1 (delta-proportional §12 re-establishment; new Live
>   Authorization for the delta; §13 approver ≠ sole-armer; ADR-002-025 progressive-promotion
>   gate; full §12 only if continuous validity broke). ADR-002-007 → v0.2 (Version field +
>   Review History on first patch). No new EV; count 372. Patches 0045/0044; §3.11.
> * **U3 (terminology).** RFC-002 §20 `NON_LIVE`/`RECOVERY` vs ADR-002-017
>   `CLOSED_NON_LIVE`/`CLOSED_RECOVERY` labels are not explicitly unified. Marked UNRESOLVED
>   (naming seam). **DISCHARGED (Wave 8):** resolved by the informative RFC-002 §20.1
>   naming-map (mode names vs recovery-barrier CLOSED_* names; 1:1 by non-live condition;
>   neither renamed). No meaning change; no new EV. Patch 0044; §3.11.

Patch documents 0030 through 0041 are recorded in the git-excluded `patches/` per the
repository convention (each born-MERGED, pointing here); this subsection is the committed
merge record. The Wave-7 changes are EV-L0 review items, with reviewer provenance to be
recorded per ADR-DEV-005 §7 / VER-002-001 §5 (M-18).

---

### 3.11 CORPUS-REVIEW-0001 Wave 8 (EV-L0 carry-over discharge: mn-1 citation precision; U1/U2/U3 mode-transition seams)

Wave 8 discharges the Wave-7 EV-L0 carry-over items: the mn-1 citation-precision fix and the
three §20.1 mode-transition edges (U1/U2/U3) that Wave 7 recorded as debt in §3.10. All changes
are narrow-only and additive except U1, which is a new normative decision — a governed,
risk-neutral, revocable de-restriction that grants no new-risk or live authority. No numbered
section was renumbered; vision.md, philosophy.md, RFC-000, COMPLEXITY-REGISTER-002.md, SUMMARY.md,
and both Evidence Registers are unchanged (Part-1 372; development-track 98). The canonical
documents already carry the changes; the following table is the committed merge record.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| mn-1: split the §7 trapped-exposure citation — SBR-INV-005 scoped to recovery-inventory inclusion; conservative valuation and non-release attributed to ADR-002-001 §15 + ADR-002-017 SBR-INV-006 (previously over-attributed to SBR-INV-005 "which enforces this independently"); forward-only v0.3 Review-History entry supersedes the v0.2 phrasing | ADR-DEV-012 §7/§15 (0.2 → **0.3**) | Patch 0042; citation precision only; no SAFE-xxx, no numeric bound, no new RRC-INV or EV (development-track count stays 98) |
| U1: new §8.5 De-Restriction Between Degraded Modes — the governed CONTAINED → DEGRADED_PROTECTIVE re-enabling of the §6 protective classifier (never automatic; affirmative trust-premise re-establishment; explicit Safety-Authority decision; no dominating HALT/incident; fail-closed to CONTAINED; revocable) | ADR-002-001 §8.5 (0.6 → **0.7**); RFC-002 §20.1 D/preamble (0.3 → **0.4**) | Patches 0043/0044; **new normative decision** (not a derived edge); refines SAFE-003/041/044; no new SAFE-xxx, no numeric bound, no new EV (Part-1 stays 372); U1 scenario debt below |
| U2: new §14.1 In-Place Scope Expansion Readiness Extent — delta-proportional §12 re-establishment for an in-place LIVE_RESTRICTED → LIVE_NORMAL expansion; new Live Authorization for the delta (§7); §13 approver ≠ sole armer; ADR-002-025 progressive-promotion gate; full §12 only where continuous validity broke | ADR-002-007 §14.1 (— → **0.2**, Version field + Review History on first patch); RFC-002 §20.1 D (**0.4**) | Patches 0045/0044; restrictive and narrow-only (adds constraints on the existing §14 expansion pathway, grants no authority); no SAFE-xxx, no numeric bound, no new EV (Part-1 stays 372); U2 scenario debt below |
| U3: informative RFC-002 §20.1 naming-map — §20 mode names vs ADR-002-017 §9 CLOSED_* recovery-barrier-state names, one-to-one by the non-live condition; neither vocabulary renamed | RFC-002 §20.1 (**0.4**) | Patch 0044; informative only, no meaning change; no SAFE-xxx, no new EV |
| Hygiene: §5 Current Approval State versions synchronized to the current canonical headers (the two stale version-bearing rows corrected — RFC-002 v0.2 → v0.4; ADR-002-001 v0.3 → v0.7) | ARCHITECTURE-GATE-STATUS §5 | Direct edit; presentational hygiene only — no ADR authored, no SAFE-xxx, no new EV |

> Wave 8 discharges the Wave-7 EV-L0 carry-over. No new SAFE-xxx requirement or numeric bound is
> introduced; no broker proper noun appears; vision.md, philosophy.md, RFC-000, and both Evidence
> Registers are unchanged (Part-1 372; development-track 98). ADR-DEV-012 → v0.3; ADR-002-001 →
> v0.7; RFC-002 → v0.4; ADR-002-007 receives a Version field (v0.2) and Review History on first
> patch, per the ADR-002-025/026/027 precedent (§3.4). U1 is a new normative decision and is
> flagged as such wherever it appears; it is narrow-only in the risk sense (no new-risk or live
> authority), following the M-07 §8.3.1 precedent that added a whole subsection with zero new EV.
>
> **Wave-8 evidence debt (no new EV IDs; scenario extensions within existing families):**
> * **U1.** SA-EV-003/004/006/007 (Safety-Authority governance) and FD-EV-001 (protective-
>   classification independence) are owed a scenario in which de-restriction never occurs
>   automatically, requires the explicit Safety-Authority decision plus affirmative trust
>   premises, grants no new-risk or live authority, and returns to CONTAINED on premise failure.
>   Discharged within those existing families; no new EV row; Part-1 count stays 372.
> * **U2.** REARM-EV-009 (partial re-arm), SBR-EV-007/009 (readiness isolation/invalidation),
>   and the SA-EV continuous-validity families are owed a scenario in which an in-place expansion
>   re-establishes the delta-proportional readiness elements, issues a new Live Authorization for
>   the delta, preserves approver ≠ sole armer, and falls back to the full §12 re-arm when
>   continuous validity broke. Discharged within those existing families; no new EV row; count
>   stays 372.

Patch documents 0042 through 0045 are recorded in the git-excluded `patches/` per the repository
convention (each born-MERGED, pointing here); this subsection is the committed merge record. The
Wave-8 changes are EV-L0 review items — most load-bearing, the U1 new normative de-restriction
decision — with reviewer provenance to be recorded per ADR-DEV-005 §7 / VER-002-001 §5 (M-18).

---

### 3.12 CORPUS-REVIEW-0001 Wave 9 (ratification machinery: GOV-001; ratification ledger and provenance record)

Wave 9 supplies the ratification machinery the corpus presupposed but never defined (mn-15): it
creates GOV-001 as the governance process delegated by RFC-000 §13, points RFC-000 §13/§18 and
RFC-001 §17 at it, and adds the §9 Ratification Ledger and §10 Wave Review Provenance Record to
this document. All changes are narrow-only and additive; GOV-001 is process-normative and
content-inert. No numbered section was renumbered; vision.md, philosophy.md, COMPLEXITY-REGISTER-002.md,
and both Evidence Registers are unchanged (Part-1 372; development-track 98). The canonical
documents already carry the changes; the following table is the committed merge record.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| GOV-001 created — Ratification and Change Governance: the three governance acts (G1); the RFC-class status ladder Working/Review/Ratification-Ready/Ratified with the ADR (Proposed/Accepted), VER (Proposed/Approved for Execution), and vision/philosophy (Baseline Adoption) exclusions (G2); Ratification-Ready preconditions P1–P5 (G3); the single-operator System-Owner ratifying authority reconciled with SAFE-053 non-applicability and CONST-015 (G4); the ratification-record schema (G5); Baseline Adoption (§7); amendment/re-ratification and cited-version-pin citation-integrity re-check (G6); fail-safe de-ratification (G7); the non-authority safety belt (G8) | NEW part-1-foundation/GOV-001-Ratification-and-Change-Governance.md (v0.1 Review Draft); SUMMARY.md gains the GOV-001 entry | Direct creation, born-MERGED (no patch file), per the COMPLEXITY-REGISTER-002 precedent; process-normative, content-inert; no SAFE-xxx, no numeric bound, no ADR, no new EV (Part-1 stays 372; development track stays 98) |
| RFC-000 §13 pointer to GOV-001 (the approved, independently specified governance process, per the existing §13 sentence) and §18 pointer naming GOV-001 as the source of the ratifying authority, preconditions, and record; ratification confers no live authorization | RFC-000 §13/§18 (0.14 → **0.15**); Appendix A v0.15 entry | Patch 0046; pointer only, narrow-only and additive; no CONST/AX change, no new requirement, no numeric bound, no new EV |
| RFC-001 §17 pointer naming GOV-001 as the ratification-governance source; document ratification of the Safety Case confers no live authorization, which remains governed by ADR-002-007 and ADR-002-025 | RFC-001 §17 (0.6 → **0.7**); §18 Review History v0.7 entry | Patch 0047; pointer only, narrow-only and additive; no SAFE-xxx, no hazard change, no numeric bound, no new EV |
| §9 Ratification Ledger added — the three-act declaration, ratification order, per-document ladder-rung table (all Working/Review Draft; Ratification-Ready count 0, P1/M-18 unmet), the P1–P5 checklist, the empty ratification-record store, the CORPUS-REVIEW-0001 open-questions disposition table, and the §4.5 residual-debt classification; non-normative, cites GOV-001 for the normative procedure | ARCHITECTURE-GATE-STATUS §9 | Direct edit; status-ledger content only; no ADR, no SAFE-xxx, no new EV |
| §10 Wave Review Provenance Record added — the M-18 provenance table for CORPUS-REVIEW-0001 and the Wave 1–8 EV-L0 reviews, with the substrate-decorrelation honesty limitation recorded | ARCHITECTURE-GATE-STATUS §10 | Direct edit; provenance metadata about existing EV-L0 design inspections; adds no evidence-register row (Part-1 stays 372); no SAFE-xxx, no numeric bound |
| M-06 owner attestation recorded — the System Owner attested (2026-07-17) that an out-of-band broker-side containment path exists for the final egress enforcement point; recorded in capability-class terms only; closes the M-06 open question; EGRESS-EV-013 remains the acceptance-track evidence obligation (`NOT_IMPLEMENTED`) | ARCHITECTURE-GATE-STATUS §4.5 (M-06 item) and §9 disposition table | Direct edit; owner disposition only; no register change (Part-1 stays 372); no broker proper noun |
| DR-0001 registered in the reading order | SUMMARY.md gains the DR-0001 entry | Direct edit; presentational only — no document authored, no SAFE-xxx, no new EV |

> Wave 9 supplies the ratification machinery (mn-15). No new SAFE-xxx requirement or numeric bound
> is introduced; no broker proper noun appears (the M-06 owner attestation is recorded in
> capability-class terms); vision.md, philosophy.md, and both Evidence Registers are unchanged
> (Part-1 372; development-track 98). GOV-001 is process-normative and content-inert: it derives
> from RFC-000 §13, governs process only, does not enter the §12 content hierarchy, and grants no
> authority. Ratification is evidence-independent and confers no live authorization, no ADR
> acceptance, and no capacity. Nothing in this wave is ratified — the §9 ladder is empty because
> precondition P1 (the M-18 independent-review provenance) is only now being recorded and no
> ratification act has been performed.

Patch documents 0046 and 0047 are recorded in the git-excluded `patches/` per the repository
convention (each born-MERGED, pointing here); GOV-001 and the gate-status/SUMMARY edits are direct
(born-MERGED, no patch file). The Wave-9 changes are EV-L0 review items, with reviewer provenance
to be recorded per ADR-DEV-005 §7 / VER-002-001 §5 (M-18) — see §10.

---

### 3.13 External independent EV-L0 review (GOV-001 G3 P1): RFC-000 v0.15 → v0.16 and GOV-001 v0.1

The first external-substrate EV-L0 review (GEMINI-EVL0-REQUEST-0001 package) was executed to
discharge the GOV-001 G3(P1) independent-review precondition on a substrate demonstrably
independent of the authoring substrate (ADR-DEV-005 AIR-INV-002). The reviewer (Gemini, vendor
Google, self-reported) returned **RFC-000 v0.15: FAIL** (1 MAJOR + 1 MINOR) and **GOV-001 v0.1:
PASS**. The authoring side independently verified both findings against the source before applying
them; the verdict is preserved verbatim in the git-excluded `reviews/GEMINI-EVL0-VERDICT-0001.md`.
All changes are narrow-only and additive; no CONST/AX renumbering, no new requirement, no numeric
bound, no new evidence row; vision.md, philosophy.md, and both Evidence Registers are unchanged
(Part-1 372; development-track 98). The canonical documents already carry the changes; the
following table is the committed merge record.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| Finding 1 (MAJOR) — §5 schema self-violation: `Depends On` declared in the §5 optional-field list (with a backward-only cross-reference note), justifying the existing CONST-004/012/015 usage; CONST-001, CONST-002, and CONST-003 completed with the previously absent `Classification` (`Constitutional Requirement`) and `Derived Requirements` fields. CONST-001/002 Derived Requirements are transcribed verbatim from the RFC-001 §12 Constitutional Verification Matrix Safety-discharge column (CONST-001: SAFE-010/012/013/014/021/042/045; CONST-002: SAFE-010/012/013/021/045); CONST-003 is recorded as deliberately not discharged by RFC-001, consistent with its Traceability composite chain (RFC-003, RFC-006, ADR-002-025) | RFC-000 §5 and §7 CONST-001/002/003 (0.15 → **0.16**); Appendix A v0.16 entry | Patch 0048; schema-completion and optional-field declaration only; no CONST/AX change, no new requirement, no numeric bound, no new EV (Part-1 stays 372); Derived Requirements values transcribed from RFC-001 §12, not invented |
| Finding 2 (MINOR) — §5 precedence-table lead-in corrected to match the column header: "maps each North Star tier to its constitutional expression" (the mapped cells for Profitability/Performance Optimization are document sections, not CONST-xxx identifiers) | RFC-000 §5 (0.16) | Patch 0048; terminology only; no meaning change |
| GOV-001 v0.1 — verdict PASS; no change required. P1 positively established via the external substrate, blocked only by P3 (upstream RFC-000 not yet Ratified) | GOV-001 (unchanged, v0.1) | No edit; §9.3/§9.4 status update only |
| External EV-L0 provenance recorded — the §10 External EV-L0 row and the external-substrate decorrelation argument (the AIR-INV-002 "recorded decorrelation argument"); §9.3 ladder rungs and §9.4 P1 updated to the per-document status | ARCHITECTURE-GATE-STATUS §10, §9.3, §9.4 | Direct edit; provenance metadata and status-ledger content only; adds no evidence-register row (Part-1 stays 372); no SAFE-xxx, no numeric bound |

> The external review is the first affirmatively decorrelated EV-L0 review in the ledger (§10). No
> new SAFE-xxx requirement or numeric bound is introduced; no broker proper noun appears; vision.md,
> philosophy.md, and both Evidence Registers are unchanged (Part-1 372; development-track 98). The
> v0.16 delta re-review (RFC-000 only) is requested in the git-excluded
> `reviews/GEMINI-EVL0-REQUEST-0002.md`; RFC-000 P1 remains pending until that delta confirms the
> fixes are complete and introduce no new defect (§9.3, §9.4).

Patch document 0048 is recorded in the git-excluded `patches/` per the repository convention
(born-MERGED, pointing here); the gate-status edits are direct. The `reviews/` verdict and
delta-request packages are git-excluded working artifacts.

**Disposition (2026-07-17).** The v0.16 delta re-review returned **PASS with zero residual
findings** (GEMINI-EVL0-VERDICT-0002; external substrate, owner-captured app UI model
"Gemini 3.1 Pro"). RFC-000 P1 is satisfied; the §9.3 ladder advanced RFC-000 v0.16 to
**Ratification-Ready**, awaiting the System Owner ratification act (GOV-001 G4/G5).

---

### 3.14 External independent EV-L0 review (GOV-001 G3 P1): RFC-001 v0.7 → v0.8 (FAIL closure)

The first external-substrate EV-L0 review of RFC-001 (GEMINI-EVL0-REQUEST-0003 package) was
executed to discharge the GOV-001 G3(P1) independent-review precondition for RFC-001 on a substrate
demonstrably independent of the authoring substrate (ADR-DEV-005 AIR-INV-002). The reviewer (Gemini
app, vendor Google; owner-captured app UI model "Gemini 3.1 Pro"; the self-report version mismatch
of VERDICT-0001 recurred and is recorded as unreliable) returned **RFC-001 v0.7: FAIL** with two
MAJOR findings and one flag-only MINOR. The authoring side independently verified both MAJOR
findings against the source before applying them; the verdict is preserved verbatim in the
git-excluded `reviews/GEMINI-EVL0-VERDICT-0003.md`. The changes are additive and do not add any
SAFE-xxx requirement, hazard, numeric bound, or evidence row; no broker proper noun appears;
vision.md, philosophy.md, and RFC-000 (Ratified) are unchanged; both Evidence Registers are
unchanged (Part-1 372; development-track 98). The canonical documents already carry the changes; the
following table is the committed merge record.

| Patch content | Canonical target | Traceability update |
|---|---|---|
| Finding 1 (MAJOR) — SAFE-050: the risk-increasing-change clause now requires independent approval satisfying the two-effective-principal requirement of SAFE-053, closing the single-operator loophole for widening a safety limit. The SAFE-053 two-satisfaction-path structure is preserved verbatim (two-natural-person quorum, or the approved Governed Single-Operator Re-Arm Variant, ADR-002-015 §17.1); no absolute two-natural-person requirement is reintroduced (CR-02 / DR-0001). CONST-015 added to SAFE-050's Derived-from set, and SAFE-050 added to the §12 Constitutional Verification Matrix CONST-015 Safety-discharge cell | RFC-001 §10 SAFE-050, §12 matrix CONST-015 row (0.7 → **0.8**); §18 v0.8 entry | Patch 0049; approval-linkage and matrix/Derived-from only; no new SAFE-xxx, no numeric bound, no new EV (Part-1 stays 372). RFC-000 is Ratified and unchanged; the CONST-015 Derived Requirements curated subset (→ SAFE-042/046/053) is the established one-directional-add convention, so the §12/Derived-from asymmetry against RFC-000 is intentional and permitted |
| Finding 2 (MAJOR) — §14: added "exceeding or disabling the Hard Safety Envelope (SAFE-004)" to the explicit no-waiver set (within the risk series, after unbounded aggregate risk), closing the path by which a waiver could exceed or disable the Hard Safety Envelope contrary to CONST-015 | RFC-001 §14 (0.8); §18 v0.8 entry | Patch 0049; no new SAFE-xxx, no numeric bound, no new EV |
| Finding 3 (flag-only MINOR) — SAFE-053's ADR-002-025 §5.11 Progressive-Promotion-step reference could not be judged (ADR-002-025 not in the package). No text change; deferred to the acceptance-tier review that verifies ADR-002-025 §5.11 defines the scope delta quantifiably | No canonical text change | Recorded in GEMINI-EVL0-VERDICT-0003 and the RFC-001 §18 v0.8 entry; acceptance-track item |
| ADR-002-026 §8.2 synchronization: added "the Hard Safety Envelope (SAFE-004)" to the §8 item-2 enumeration of RFC-001's explicit no-waiver set (after bounded aggregate risk, before duplicate-exposure prevention), keeping the mirror 1:1 with RFC-001 §14 (now eight items). §5.6 Non-Waivable Boundary (union pointer) and §8 item 9 unchanged | ADR-002-026 §8 (0.2 → **0.3**); §29 v0.3 Review-History entry | Patch 0050; enumeration synchronization only; no new invariant, requirement, numeric bound, or EV |
| External EV-L0 provenance recorded — the §10 External EV-L0 row (RFC-001 v0.7); §9.3 ladder rung and §9.4 P1 updated to per-document status; this merge map | ARCHITECTURE-GATE-STATUS §10, §9.3, §9.4, §3.14 | Direct edit; provenance metadata and status-ledger content only; adds no evidence-register row (Part-1 stays 372); no SAFE-xxx, no numeric bound |

> RFC-001 P1 remains pending: the FAIL is closed in v0.8, but P1 is positively established only when
> the v0.8 delta re-review confirms both MAJOR findings are fully resolved and introduce no new
> defect. The delta re-review (RFC-001 only) is requested in the git-excluded
> `reviews/GEMINI-EVL0-REQUEST-0004.md` (§9.3, §9.4). The flag-only MINOR (Finding 3) is a
> deferred acceptance-tier item, not a v0.8 blocker.

Patch documents 0049 (RFC-001) and 0050 (ADR-002-026) are recorded in the git-excluded `patches/`
per the repository convention (born-MERGED, pointing here); the gate-status edits are direct. The
`reviews/` verdict and delta-request packages are git-excluded working artifacts.

**Disposition (2026-07-17).** The v0.8 delta re-review returned **PASS with zero residual
findings** (GEMINI-EVL0-VERDICT-0004; external substrate, owner-captured app UI model
"Gemini 3.1 Pro"), specifically confirming that the SAFE-050 correction preserves SAFE-053's
two-satisfaction-path structure. RFC-001 P1 is satisfied; the §9.3 ladder advanced RFC-001 v0.8
to **Ratification-Ready**, awaiting the System Owner ratification act (GOV-001 G4/G5).

---

### 3.15 Pre-ratification self-scan: RFC-002 v0.4 → v0.5 (SAFE-053/054 absorption; FIX-FIRST)

A pre-ratification self-scan of RFC-002 v0.4 — performed before assembling the external EV-L0
review package, on the two-lens pattern that produced the last two external RFC-000/RFC-001 FAILs
(self-gate conformance §30; CONST-015/SAFE-053 constitutional linkage) — found the same
fingerprint defect family the two prior external reviews had surfaced: the ratified-baseline
SAFE-053 and SAFE-054 (added to RFC-001 in v0.8, RR-0003) were not yet absorbed into the RFC-002
architecture, the §19.4 runtime-change clause still permitted a single effective principal to
widen authority, and the §9.1 re-arm and production-scope-promotion rows lacked the SAFE-053
linkage. All findings were verified against the source before applying them. Every fix is
narrow-only realignment to the Ratified RFC-001 v0.8; the SAFE-053 two-satisfaction-path structure
is preserved verbatim (two-natural-person quorum, or the approved Governed Single-Operator Re-Arm
Variant, ADR-002-015 §17.1) and no absolute two-natural-person requirement is reintroduced
(CR-02 / DR-0001). No SAFE-xxx requirement, hazard, numeric bound, or evidence row is added; no
broker proper noun appears; vision.md, philosophy.md, RFC-000 (Ratified v0.16), RFC-001 (Ratified
v0.8), and GOV-001 (Ratified v0.1) are unchanged; both Evidence Registers are unchanged (Part-1
372; development-track 98). The canonical document already carries the changes; the following table
is the committed merge record.

| Finding | Canonical target | Traceability update |
|---|---|---|
| C-1 (ratified SAFE-053/054 not absorbed) — added two §5 Architecture Drivers rows (`Bounded human authority → SAFE-042, SAFE-046, SAFE-050, SAFE-053`; `Final-egress out-of-band containment → SAFE-054`); added §27 Requirements Traceability rows for SAFE-053 and SAFE-054 (§27 SAFE row count 34 → 36); added the §10.8 SAFE-054 out-of-band-containment mechanism in capability-neutral terms, preserving RFC-001 SAFE-054's defined-and-evidenced / accepted-residual-risk-with-reduced-scope branch structure. The M-06 owner attestation is referenced through SAFE-054, not restated (it remains §4.5) | RFC-002 §5, §10.8, §27 (0.4 → **0.5**); §32 v0.5 entry | Patch 0051; no new SAFE-xxx, no numeric bound, no new EV (Part-1 stays 372); §27 SAFE rows 34 → 36 |
| M-1 (§19.4 authority-widening + §9.1 config rows) — replaced the §19.4 runtime authority-increase sentence with the RFC-001 SAFE-053 two-effective-principal clause (two-natural-person quorum or ADR-002-015 §17.1 variant); added the same SAFE-053 linkage to the §9.1 "Change Runtime Safety Profile" and "Change Hard Safety Envelope" rows; cited RFC-000 CONST-015 in §19.4 | RFC-002 §9.1, §19.4 (0.5); §32 v0.5 entry | Patch 0051; approval-linkage only; no new SAFE-xxx, no numeric bound, no new EV. RFC-000/RFC-001 are Ratified and unchanged; SAFE-053's two paths preserved (CR-02 / DR-0001) |
| M-2 (§9.1 re-arm / production-scope-promotion) — added "(two independent effective principals per RFC-001 SAFE-053 — quorum or ADR-002-015 §17.1 variant; see §20.1, §23.1)" to the §9.1 Re-arm and production-scope-promotion rows, consistent with the §20.1 table B restorative-edge owners | RFC-002 §9.1 (0.5); §32 v0.5 entry | Patch 0051; no new SAFE-xxx, no numeric bound, no new EV |
| Minor (CONST-015 unmentioned) — RFC-000 CONST-015 (Bounded Human Authority), the constitutional parent of SAFE-053, is now cited explicitly in §19.4 | RFC-002 §19.4 (0.5); §32 v0.5 entry | Patch 0051; citation only; no meaning change |
| ADR-002-014 alignment check (Open Question) — the ADR-002-014 profile-commit/approval wording ("quorum-committed Profile Generation"; "Independent envelope/limit approval quorum") was checked against SAFE-053's two satisfaction paths and judged **consistent — no change required**: ADR-002-014 fixes no absolute two-natural-person count, uses a generic approval "quorum" whose composition is explicitly deferred to ADR-002-015 (§26 Q3; §27 item 3), and carries effective-principal separation through SPG-INV-010 and the §8 authority table, so the §17.1 variant already flows through the ADR-002-015 delegation. Unlike ADR-002-025/026/027, which hard-coded "two distinct natural persons" and needed the Wave-1 recognition clause (§3.4), ADR-002-014 never hard-codes a natural-person count, so no recognition clause is added | No canonical text change (ADR-002-014 unchanged, v0.2 Proposed) | Judgment recorded here and in RFC-002 §32 v0.5; **no Patch 0052 authored** |
| External EV-L0 provenance — RFC-002 v0.5 external independent EV-L0 review requested; §5 and §9.3 RFC-002 rows advanced to v0.5; this merge map | ARCHITECTURE-GATE-STATUS §3.15, §5, §9.3; RFC-002 §32 | Direct edit; provenance/status-ledger content only; adds no evidence-register row (Part-1 stays 372); no SAFE-xxx, no numeric bound |

> RFC-002 P1 remains unmet: this self-scan is an authoring-side FIX-FIRST pass, not the required
> external-substrate EV-L0 review. The independent external review of RFC-002 v0.5 (full document,
> against the Ratified RFC-000 v0.16 and RFC-001 v0.8 governing baselines) is requested in the
> git-excluded `reviews/GEMINI-EVL0-REQUEST-0005.md`; RFC-002 P1 is positively established only when
> that review is executed on a demonstrably independent substrate (ADR-DEV-005 AIR-INV-002;
> GOV-001 G3 P1) and returns a disposition (§9.3, §9.4). P3 for RFC-002 is satisfied (RFC-000 and
> RFC-001 are Ratified).

Patch document 0051 (RFC-002) is recorded in the git-excluded `patches/` per the repository
convention (born-MERGED, pointing here); the gate-status edits are direct. The `reviews/` request
package is a git-excluded working artifact.

---

## 4. Remaining Architecture and Acceptance Work

ADR-002-005 through ADR-002-030 are authored as `Proposed`. Phase B and follow-on RCL-consensus, final-egress-security, safety-configuration-governance, human-authority-governance, evidence-integrity/replay, safe-start/recovery-barrier, Critical Input/decision-context, venue/session/tradability-constraint, Intent-to-order conformance, aggregate-risk evaluation, action-flow governance, independent proposal-approval, active-currentness, restricted-live/promotion-governance, safety-deviation/residual-risk-governance, safety-incident/controlled-shutdown-governance, safety-telemetry/continuous-monitoring-governance, software-supply-chain/runtime-artifact-admission, and post-trade economic-obligation/finality authorship are complete, but none of those decisions is accepted.

ADR-002-007 selects the single-use capability currentness model, ADR-002-012 selects quorum ordering and RCL writer fencing, ADR-002-013 selects the effective final-egress security boundary, ADR-002-014 selects immutable safety-configuration artifacts and activation, ADR-002-015 selects effective-human identity, exact approvals, dual control, independent Human HALT, and break-glass confinement, ADR-002-016 selects immutable causal evidence, pre-effect durability, integrity anchoring, gap containment, protected retention, and isolated deterministic replay, ADR-002-017 selects closed startup, monotonic Recovery Generations, fenced recovery ownership, conservative Inventory Cuts, dependency-complete obligations, non-authorizing readiness, partial-scope isolation, and fresh re-arm handoff, ADR-002-018 selects Critical Input classification, source continuity/provenance, exact transformation lineage, immutable Snapshots/Capsules, independent approval common-mode analysis, correction/invalidation fan-out, and active final-egress context currentness, ADR-002-019 selects exact venue/session/tradability, instrument/order/account/margin/borrow/settlement, Broker Capability Profile, Order Admissibility Decision, Constraint Generation, protective-path, final-egress currentness, and non-revival rules, ADR-002-020 selects deterministic closed-envelope construction, canonical command semantics, conservative effect proof, downstream-mutation fencing, and actual-outbound verification, ADR-002-021 selects complete aggregate-state cuts, adverse scenarios, vector/scoped projection, benefit proof, numerical safety, exact allocation decisions, and active RCL/egress currentness, ADR-002-022 selects complete action classification, shared-scope budgets, bounded cause amplification, RCL-serialized single-use permits, retry/reconnect containment, Protective Flow Reserve, and active RCL/egress currentness, ADR-002-023 selects complete automated approval requests, true independent validation, exact decisions, single-use Intent consumption, invalidation closure, and active final-egress currentness, ADR-002-024 selects the complete cross-artifact vector, restrictive-fence/local-latch, per-send proof, and claim/fence/first-byte ordering protocol, ADR-002-025 selects exact restricted-live pre-registration, worst-credible-effect coverage, abort dominance, evidence non-extrapolation, progressive single-use promotion, and fresh production-authorization handoff, ADR-002-026 selects the Non-Waivable Boundary, exact safety-deviation scope, compensating-control and combined residual-risk rules, independent Effective Principal approval, single-use restricted-configuration eligibility, Deviation Generation currentness, evidence honesty, expiry/revocation, and non-revival, ADR-002-027 selects restrictive incident declaration, greatest-credible dependency scope, Incident Generation, Active Safety Incident Set, non-authorizing containment and controlled shutdown, lossless recovery handoff, administrative closure, and non-revival, ADR-002-028 selects exact telemetry and monitor coverage, deterministic conformance evaluation, Monitor Generation, restrictive gaps, suppression safety, bounded alert delivery/escalation, active egress currentness, and non-revival, ADR-002-029 selects exact reviewed-source identity, complete dependency/toolchain closure, isolated build provenance, immutable artifact custody, independent admission, monotonic Release Generation, complete Admitted Release Sets, runtime attestation, restriction currentness, rollback/restore fencing, and non-revival, and ADR-002-030 selects exact economic-obligation legs, field-specific finality, PTOL lifecycle serialization, source and statement coverage, breaks/corrections, Post-Trade Obligation Generation, conservative RCL capacity coupling, external-instruction confinement, and non-revival. Conforming products, schemas, registries, compilers/evaluators/verifiers, numeric/unit/risk/flow/approval/currentness/trial/deviation/incident/monitoring/release/post-trade rules, canonicalization, scenario/valuation models, SDK/serializer constraints, failure-domain allocation, bounds, and broker evidence remain acceptance blockers.

Dedicated VER-002-001 and Evidence Register entries now exist for ADR-002-005 through ADR-002-030, but all remain `NOT_IMPLEMENTED`. Verification Profile `2.1-PROPOSED` has matching actual/template key sets with 91 scope keys, 82 bounds, and 55 limits. It additionally binds the proposed Post-Trade Finality Policy, Post-Trade Obligation Generation, complete Active Economic Obligation Set, Statement Coverage Manifest, and their unapproved effect-to-obligation, change-detection, break-to-restriction, egress-denial, generation-fence, statement-gap, obligation/finality/statement/break/transfer age values while retaining every earlier unapproved bound. The profile remains unapproved with `approved_by: []`; unresolved values keep the affected scope contained and live operation prohibited.

### 4.1 Latest Review Disposition

The ADR-002-015 architecture review passed its document and integration scope with no Critical or Major finding. Its sole Minor finding identified a dangling `ADR-002-003 §9.5` citation; commit `fdce384e` records the correction and review disposition.

The latest independent document review reported ADR-002-016 and its integration as PASS. No finding requiring disposition was supplied with that verdict. The review result changes no ADR status: evidence-store, durable-ingress, emergency-journal, integrity-anchor, gap-detection, retention, redaction, replay-isolation, security-review, numeric-bound, and executed-evidence gates remain open. A document-review PASS is EV-L0 evidence only and creates no capacity, authority, broker permission, verification completion, or live readiness.

The independent ADR-002-017 document and adversarial-sequence review found no Critical or Major issue. Four Minor findings were resolved conservatively: the nonexistent intervening SAFE identifier implied by a numeric range was replaced with explicit real SAFE IDs; Recovery Generation and readiness currentness now explicitly reject TTL, heartbeat, health, eventual-consistency, and absence-of-invalidation substitutes; ADR-002-013 now binds and verifies the exact current recovery package, decision, scope, validity, and invalidation status at every send; and `OPEN_FOR_NON_LIVE` was renamed `CLOSED_NON_LIVE`. These citation and clarity corrections do not change authority, evidence, or live-readiness status.

The independent ADR-002-018 document, adversarial-sequence, integration, and traceability review found no Critical or Major issue and no unsafe sequence. Twenty-two sequences were blocked outright and two final-egress invalidation/send races were correctly classified as open-but-gated by fail-closed currentness and unapproved bounds. Two Minor clarity findings were resolved conservatively: §1/§15/§17 now make materiality and binding applicability policy-owned with unknown materiality treated as Critical/material, and ADR-002-014 §12.3 now states in its normative body that configuration activation does not establish Critical Input or Decision Context validity/currentness. The review PASS is EV-L0 only; currentness implementation, approved bounds, security review, and executed evidence remain open.

The independent ADR-002-019 document, adversarial-sequence, integration, and traceability review found no Critical or Major issue and no unsafe sequence. Twenty-two sequences were blocked outright and two final-egress invalidation/send or constraint-plane-partition races were correctly classified as open-but-gated by fail-closed currentness and unapproved bounds. Two non-safety Minor findings were resolved: the Completed Design Artifacts list now has unique sequential numbering, and RFC-002 §9.1 now includes the Venue Constraint Gate as an explicitly non-authorizing evaluator whose decision cannot approve, commit capacity, classify protection, transmit, or arm live scope. The review PASS is EV-L0 only; the fenced currentness protocol, approved bounds, security review, and executed evidence remain open.

The independent ADR-002-020 document, adversarial-sequence, integration, and traceability review passed at EV-L0 with no Critical or Major finding and no unsafe path. Its sole soft Minor finding was resolved conservatively: an absent, empty, unknown, stale, conflicting, or unverifiable `required_authority_scope` now makes the Order Conformance Proof `UNKNOWN` or `NON_CONFORMANT` and blocks authority issuance and transmission; the template defaults `required_authority_scope_complete` to `false`. The review does not satisfy schema, compiler/verifier, actual-outbound, Construction Generation, approved-bound, fault-injection, security-review, or executed-evidence gates.

The independent ADR-002-021 document review passed at EV-L0. No finding requiring disposition was supplied with that verdict. The review changes no ADR status: Aggregate Risk Policy/state-cut/scenario/evaluator/verifier, RCL/egress currentness, security review, approved-bound, fault-injection, and executed ARE evidence gates remain open. No ARE case has been executed, no bound is approved, and the review creates no allocation, capacity, Accepted status, or live readiness.

The independent ADR-002-022 document review passed at EV-L0. No finding requiring disposition was supplied with that verdict. The review changes no ADR status: Action Flow Policy/scope/budget/evaluator, RCL permit and atomic-claim protocol, final-egress currentness, security review, approved-bound, fault-injection, and executed AFG evidence gates remain open. No AFG case has been executed, no bound is approved, and the review creates no flow headroom, protective reserve, capacity, Accepted status, or live readiness.

The independent ADR-002-023 document review passed at EV-L0 with zero Critical, Major, or Minor findings. All 15 IAP invariants were preserved and all 18 adversarial approval-escalation, duplicate-consumption, union/replay, and cached-egress sequences were blocked by the normative contract. The review changes no ADR status: independent-input, Intent Registry, active-currentness, security-review, approved-bound, fault-injection, and executed IAP evidence gates remain open. At review time all 279 registered items were `NOT_IMPLEMENTED`; the later ADR-002-024 and ADR-002-025 registrations change only the count, not the result. The review creates no approval authority, Intent transition, capacity, Accepted status, verification completion, or live readiness.

The independent ADR-002-024 document review passed at EV-L0. No finding requiring disposition was supplied with that verdict. The review changes no ADR status: Currentness Policy, ordering domain, restrictive ingress, local latch, per-send proof, first-byte ordering, stale-generation fencing, security review, approved-bound, fault-injection, and executed CUR evidence gates remain open. At that review point all 291 registered items were `NOT_IMPLEMENTED`; no bound was approved, and the review created no currentness fact, capability, capacity, Accepted status, verification completion, or live readiness.

The independent ADR-002-025 document review passed cleanly at EV-L0. No finding requiring disposition was supplied with that verdict. The review changes no ADR status: restricted-live trial policy, active-currentness, security-review, approved-bound, fault-injection, EV-L5, promotion, and executed RLP evidence gates remain open. All 303 registered items remain `NOT_IMPLEMENTED`, every new trial bound is unapproved, and the four new templates remain DRAFT/fail-closed/non-authorizing. The review creates no plan eligibility, restricted-live authorization, promotion eligibility, production authorization, Accepted status, verification completion, or live readiness.

The independent ADR-002-026 document, adversarial-sequence, integration, and traceability review passed cleanly at EV-L0 with zero Critical, Major, or Minor findings. WDR acceptance/evidence titles are exact 1:1 (WDR-AC-001..012 ↔ WDR-EV-001..012), the Non-Waivable Boundary is hard and non-erodable, a deviation is non-authorizing by itself and single-use/generation-fenced, self-approval and common-mode compensation are blocked, combined residual risk is conservatively aggregated at both request and activation, no executive/management-override carve-out exists, and expiry/revocation/recovery neither revive a deviation nor auto re-arm. Break-glass (ADR-002-015 §16) and configuration activation (ADR-002-014) relationships are non-circular. The review changes no ADR status: deviation-policy, effective-principal-quorum, compensating-control-evidence, Deviation Generation, currentness, security-review, approved-bound, fault-injection, and executed WDR evidence gates remain open. All 363 registered items remain `NOT_IMPLEMENTED`, Verification Profile `2.1-PROPOSED` remains unapproved, every deviation bound and limit is unapproved, and the five deviation templates remain DRAFT/fail-closed/non-authorizing. The review creates no approved deviation, residual-risk acceptance, compensating-control proof, configuration eligibility, evidence `PASS`, capacity, live authority, broker transmission, Accepted status, verification completion, or live readiness.

The independent ADR-002-027 document review passed at EV-L0. No finding requiring disposition was supplied with that verdict. The review changes no ADR status: incident policy, declaration, scope expansion, containment-plan, controlled-shutdown, recovery-handoff, closure, final-egress currentness, security-review, approved-bound, fault-injection, and executed SIR evidence gates remain open. At that review point, all 327 then-registered items were `NOT_IMPLEMENTED`, Verification Profile `1.8-PROPOSED` was unapproved, every new incident bound was unapproved, and the six new templates were DRAFT/fail-closed/non-authorizing. The review creates no incident restriction, containment-action authority, shutdown authorization, broker-finality proof, recovery readiness, administrative closure, scope restoration, capacity release, live authority, Accepted status, verification completion, or live readiness.

The independent ADR-002-028 document review passed at EV-L0 with no unsafe path. Two Minor traceability and authority-ownership clarity findings were resolved in commit `c442dd82`: STM acceptance/evidence titles now match exactly, and the monitoring trigger is established by the requirement, hazard, and control registries rather than policy self-declaration. The review changes no ADR status: monitoring implementation, security review, approved bounds, fault injection, and executed STM evidence remain open.

The independent ADR-002-029 document and integration review passed cleanly at EV-L0 with zero Critical, Major, or Minor findings. SCI acceptance/evidence titles are exact 1:1, all 351 then-registered items remained `NOT_IMPLEMENTED`, and Profile `2.0-PROPOSED` remained unapproved. The review changes no ADR status: source/build/dependency/toolchain/signer/registry/admission/runtime-attestation implementation, security review, generation/currentness fencing, approved bounds, fault injection, and executed SCI evidence remain open.

The independent ADR-002-030 document, adversarial-sequence, integration, and traceability review passed cleanly at EV-L0 with zero Critical, Major, or Minor findings. PTF acceptance/evidence titles are exact 1:1 (PTF-AC-001..012 ↔ PTF-EV-001..012), the non-authorizing/fail-closed/generation-fenced protocol keeps PTOL out of capacity, authority, external-egress, incident, scope, and re-arm ownership, statement common-mode is disclosed, corrections reopen field-specific finality, and status honesty holds with no premature Accepted/PASS claim. The upstream corpus (ADR-002-002/004/010/016/017/019/021 and RFC-002 §§9.1/10.32/23.1) already carries consistent bidirectional forward-references. The review changes no ADR status: obligation-compiler, PTOL, finality-recipe, statement-coverage, break/correction, RCL-coupling, currentness, security-review, approved-bound, fault-injection, and executed PTF evidence gates remain open. All 363 registered items remain `NOT_IMPLEMENTED`, Verification Profile `2.1-PROPOSED` remains unapproved, every new post-trade bound and limit is unapproved, and the six new templates remain DRAFT/fail-closed/non-authorizing. The review creates no obligation finality, statement completeness, settlement or cash availability, collateral eligibility, legal title, borrow discharge, capacity release, live authority, external transmission, Accepted status, verification completion, or live readiness.

```text
ADR-002-002 through ADR-002-018 status: Proposed; document review PASS
ADR-002-019 status: Proposed; independent document review PASS; two non-safety Minor findings resolved
ADR-002-020 status: Proposed; independent document review PASS; one soft Minor finding resolved
ADR-002-021 status: Proposed; independent document review PASS; no finding supplied for disposition
ADR-002-022 status: Proposed; independent document review PASS; no finding supplied for disposition
ADR-002-023 status: Proposed; independent document review PASS; no finding supplied for disposition
ADR-002-024 status: Proposed; independent document review PASS; no finding supplied for disposition
ADR-002-025 status: Proposed; independent document review PASS; no finding supplied for disposition
ADR-002-026 status: Proposed; independent document review PASS; zero findings
ADR-002-027 status: Proposed; independent document review PASS; no finding supplied for disposition
ADR-002-028 status: Proposed; independent document review PASS; two Minor findings resolved
ADR-002-029 status: Proposed; independent document review PASS; zero findings
ADR-002-030 status: Proposed; independent document review PASS; zero findings
ADR-002-018 independent document review: PASS; two Minor findings resolved
ADR-002-016 independent document review: PASS; no finding supplied for disposition
ADR-002-017 independent document review: PASS; four Minor findings resolved
ADR acceptance: NO
Restricted-live readiness: NO
Production readiness: NO
```

The Proposed status is preserved because the applicable approval gates, including ADR-002-007 §25, still require protocol implementation, independent security review, approved bounds, and executed evidence. A passed document review is not verification completion and creates no live authority.

### 4.2 Evidence Debt — DR-0001 / CR-02 (single-operator live governance)

DR-0001 introduced one new Safety-Case requirement (RFC-001 SAFE-053) and five new ADR-002-015 invariants (HAG-INV-015 through HAG-INV-019) defining the Governed Single-Operator Re-Arm Variant. These carry verification-evidence obligations that are **deliberately not registered in EVIDENCE-REGISTER-002 in this wave**, to prevent evidence-count drift while the Part-2/3 register consolidation is pending. The register count remains 363 `NOT_IMPLEMENTED` items; no row was added or removed.

Recorded evidence debt (to be discharged in the Part-2/3 register consolidation wave):

- SAFE-053 — independent approval of risk-increasing re-arm/issuance/promotion: requires acceptance-criteria evidence that fails closed on collapsed principals, ad-hoc satisfaction-path substitution, and missing or indeterminate variant attestation.
- HAG-INV-015..019 and ADR-002-015 §17.1 — the variant: requires prospective `HAG-EV-013` and successor rows covering pre-approval, time-separation, independent block-only attestation (fail-closed on unavailable/indeterminate), external-reviewer independence, and the no-scope-expansion / no-boundary-waiver guarantee.

Acceptance criteria for the new invariants are stated in ADR-002-015 §17.1 and carried in the HAG-INV-015..019 statements. Until the evidence is registered, passed, and independently reviewed, the variant is non-authorizing and confers no live readiness; the ADR-002-015 §29 Approval Gate is unchanged. This is an acceptance blocker, not a status promotion.

**DISCHARGED (Wave 4):** registered as HAG-EV-013 through HAG-EV-017 (the Governed Single-Operator Re-Arm Variant, HAG-INV-015..019, and SAFE-053); see §3.7 and VER-002-001 §§384–388. Register count 363 → 372. The variant remains non-authorizing and `NOT_IMPLEMENTED`; registration is not execution.

### 4.3 Evidence Debt — CORPUS-REVIEW-0001 Wave 2 (Theme A/B)

Wave 2 (RFC-000-Patch-0009, RFC-001-Patch-0010) introduced one new constitutional requirement (CONST-015), two new Catastrophic hazards (HAZ-024, HAZ-025), and one new Critical safety requirement (SAFE-054). Consistent with §4.2, the associated verification-evidence obligations are **deliberately not registered in EVIDENCE-REGISTER-002 in this wave**, to prevent evidence-count drift while the Part-2/3 register consolidation is pending. The register count remains 363 `NOT_IMPLEMENTED` items; no row was added or removed.

Recorded evidence debt (to be discharged in the Part-2/3 register consolidation wave):

- CONST-015 (Bounded Human Authority): verification rides on its derived Safety-Case requirements SAFE-042, SAFE-046, and SAFE-053; SAFE-053's evidence debt is already recorded in §4.2. No separate register row is owed for CONST-015 itself.
- HAZ-024 (Operator/Human Configuration or Authorization Error): requires SAFE→HAZ coverage evidence that its controlling requirements (SAFE-042, SAFE-046, SAFE-050, SAFE-053) prevent wrong-account, wrong-arming, mis-authorization, and misconfiguration paths and fail closed.
- HAZ-025 (Defect or Compromise of the Final Egress Enforcement Point) and SAFE-054 (Out-of-Band Containment of Final Egress): require prospective evidence that an out-of-band containment path independent of the final egress enforcement point exists and terminates its real-capital transmission capability, or that its absence is recorded and accepted as residual risk with a correspondingly reduced live scope — established in Broker Capability Profile terms, without dependence on any named broker.

Until this evidence is registered, passed, and independently reviewed, CONST-015, HAZ-024, HAZ-025, and SAFE-054 confer no live readiness; production readiness remains NO. This is an acceptance blocker, not a status promotion.

**DISCHARGED (Wave 4):** registered as HAG-EV-018 (HAZ-024; SAFE-042/046/050/053) and EGRESS-EV-013 (HAZ-025 / SAFE-054); see §3.7 and VER-002-001 §§389–390. Register count 363 → 372. CONST-015 rides on SAFE-042/046/053 and owed no separate row. The M-06 question of whether an out-of-band egress path actually exists remains open (§4.5); SAFE-054 permits closing EGRESS-EV-013 via the accepted-residual-risk / reduced-scope branch. All rows remain `NOT_IMPLEMENTED`.

### 4.4 Evidence Debt — CORPUS-REVIEW-0001 Wave 3 (ADR-002-001 evidence-gate binding)

Wave 3 (PATCH-ADR-002-001-v0.3, RFC-001-Patch-0011) bound ADR-002-001's §21 acceptance criteria to verification evidence and added the consolidated `ADR-002-001` approval gate to VER-002-001 §380. Two criteria are only PARTIALLY discharged by existing evidence families and carry dedicated evidence debt. Consistent with §4.2/§4.3, no register row was added; the count remains 363 `NOT_IMPLEMENTED` items.

Recorded evidence debt (to be discharged in the Part-2/3 register consolidation wave):

- ADR-002-001 §21 criterion #1 (protective resource domains identified for each supported broker and market): BC-EV-013 and BC-EV-021 establish broker-capability behavior but not enumeration completeness across every protective-resource domain. A dedicated protective-resource-domain enumeration-completeness EV is owed, gated by an approved Broker Capability Profile and Safety Profile per domain. No register row added (count 363).
- ADR-002-001 §21 criterion #11 (every protective resource assigned an evidenced guarantee level): SPG-EV-001 establishes Safety-Profile governance but not a per-resource guarantee-level assignment for every protective resource. A dedicated per-resource guarantee-level EV is owed, gated by the Safety Profile artifact. No register row added (count 363).
- The TRACEABILITY-MATRIX-002 UNMAPPED entries SAFE-053 and SAFE-054 remain accepted evidence debt already recorded in §4.2 and §4.3 respectively; no additional row is owed for them here.

Until this evidence is registered, passed, and independently reviewed, ADR-002-001 remains `Proposed` and criteria #1 and #11 confer no acceptance. This is an acceptance blocker, not a status promotion.

**DISCHARGED (Wave 4):** registered as PRD-EV-001 (§21 criterion #1, protective-resource-domain enumeration completeness) and PRD-EV-002 (§21 criterion #11, per-resource guarantee-level assignment) under the new ADR-002-001-owned PRD family; see §3.7, ADR-002-001 v0.4 §21/§25, and VER-002-001 §§391–392. Register count 363 → 372. ADR-002-001 remains `Proposed`; both rows are `NOT_IMPLEMENTED`.

### 4.5 Remaining Debt After Wave 4

- **M-06 architectural existence.** Whether an out-of-band final-egress containment path independent of the egress enforcement point actually exists remains open. EGRESS-EV-013 registers the evidence obligation; SAFE-054 permits closing it via the accepted-residual-risk / reduced-scope branch. This is a separate Major finding, not part of CR-01. **Owner disposition (Wave 9, 2026-07-17):** the System Owner attested that an out-of-band broker-side containment path exists for the final egress enforcement point (credential revocation and account deactivation through broker-side channels), recorded in capability-class terms only; the concrete procedure belongs to a non-normative Broker Capability Profile instance on the implementation track. This closes the M-06 open question; EGRESS-EV-013 remains the acceptance-track evidence obligation (`NOT_IMPLEMENTED`).
- **No execution.** All 372 Part-1 items (EVIDENCE-REGISTER-002) and all 98 Part-2/3 items (EVIDENCE-REGISTER-DEV) remain `NOT_IMPLEMENTED`; registration is not execution and confers no live readiness. (The Part-2/3 count rose 96 → 97 in Wave 5, §3.8; 97 → 98 in Wave 7, §3.10.)
- **TRACEABILITY-MATRIX-002 §5.3 source gaps.** ADR-002-002 through ADR-002-006 lack a §2x Requirements Traceability table, so their families (RC, SA, BC, STATE, RECON) are not reachable through the SAFE→ADR bridge. This is deferred and scoped out of CR-01; no coverage is lost because those SAFEs are co-claimed by other realizing ADRs.
- **Part-2/3 ratification pending.** RFC-003 through RFC-011, ADR-DEV-001 through ADR-DEV-015, and VER-DEV-001 remain `Proposed`.

### 4.6 Scoped Future Specifications (G-02..G-05)

These are architecture gaps identified in CORPUS-REVIEW-0001 that are out of the current
corpus's scope. Each is registered here (not authored) with its basis, the trigger condition
under which a specification becomes required, and an owner candidate. Registration authors no
ADR, introduces no SAFE-xxx, and adds no evidence row.

- **G-01 — resolved.** The single-operator live-governance gap is resolved via CR-02 option
  (c) / DR-0001 (§3.4).
- **G-02 — Capital/portfolio allocation governance.** Basis: vision §8 (Long-Term Scope),
  §10.4 (Economic Viability). Trigger: the first cross-strategy or cross-account capital
  allocation beyond per-action RCL headroom. Owner candidate: Architecture Board (a new
  ADR-002-0xx or an RFC-006 successor).
- **G-03 — Market-data / context ingestion pipeline.** Basis: vision §6.8 (Evidence-Based
  State); ADR-002-018 governs Critical Inputs *after* arrival but not their ingestion.
  Trigger: the first feed with continuity, gap, or backfill needs. Owner candidate: an RFC-004
  successor or a new ADR.
- **G-04 — Multi-account / multi-broker concurrent operating model.** Basis: aggregation
  exists (ADR-002-021) but the writer-epoch scope is open (ADR-002-002 §37); initial live is
  single-account. Trigger: a second concurrent account or broker. Owner candidate: Architecture
  Board.
- **G-05 — Performance / latency budget for the safety machinery.** Basis: philosophy §29
  (safety and expectancy must survive real conditions); all latency bounds currently defer to
  the unapproved Verification Profile. Trigger: before restricted-live for a latency-sensitive
  market. Owner candidate: the Verification Profile / an RFC-002 §29 successor.

---

## 5. Current Approval State

| Artifact | Current state | Can implement? | Can accept? |
|---|---|---:|---:|
| RFC-002 v0.5 | Consolidated Review Draft | YES | after RFC review gates pass |
| ADR-002-001 v0.7 | Proposed | YES | after protective evidence passes |
| ADR-002-002 | Proposed | YES | NO |
| ADR-002-003 | Proposed | YES | NO |
| ADR-002-004 | Proposed | YES | NO |
| ADR-002-005 | Proposed | YES | NO |
| ADR-002-006 | Proposed | YES | NO |
| ADR-002-007 | Proposed | YES | NO |
| ADR-002-008 | Proposed | YES | NO |
| ADR-002-009 | Proposed | YES | NO |
| ADR-002-010 | Proposed | YES | NO |
| ADR-002-011 | Proposed | YES | NO |
| ADR-002-012 | Proposed | YES | NO |
| ADR-002-013 | Proposed | YES | NO |
| ADR-002-014 | Proposed | YES | NO |
| ADR-002-015 | Proposed | YES | NO |
| ADR-002-016 | Proposed | YES | NO |
| ADR-002-017 | Proposed | YES | NO |
| ADR-002-018 | Proposed | YES | NO |
| ADR-002-019 | Proposed | YES | NO |
| ADR-002-020 | Proposed | YES | NO |
| ADR-002-021 | Proposed | YES | NO |
| ADR-002-022 | Proposed | YES | NO |
| ADR-002-023 | Proposed | YES | NO |
| ADR-002-024 | Proposed | YES | NO |
| ADR-002-025 | Proposed | YES | NO |
| ADR-002-026 | Proposed | YES | NO |
| ADR-002-027 | Proposed | YES | NO |
| ADR-002-028 | Proposed | YES | NO |
| ADR-002-029 | Proposed | YES | NO |
| ADR-002-030 | Proposed | YES | NO |
| VER-002-001 | Proposed, ready for test implementation | YES | after evidence workflow review |
| Verification Profile 2.1 | `PROPOSED`, `approved_by: []` | YES, as draft | NO |
| Broker-specific Capability Profile | Template only | YES | NO |
| Human authority artifacts | Templates only, all non-authorizing | YES | NO |
| Evidence integrity and replay artifacts | Templates only, all DRAFT/unverified/non-authorizing | YES | NO |
| Recovery barrier, session, inventory-cut, obligation, evidence-package, and readiness artifacts | Templates only; default states are DRAFT/TRIGGERED/PENDING/NOT_READY and non-authorizing/fail-closed | YES | NO |
| Critical Input Policy, Snapshot, and Decision Context Capsule artifacts | Templates only; DRAFT/INVALID/non-authorizing/fail-closed | YES | NO |
| Venue Constraint Policy, Snapshot, and Order Admissibility Decision artifacts | Templates only; DRAFT/INVALID/UNKNOWN/non-authorizing/fail-closed | YES | NO |
| Order Construction Policy, Authorized Construction Envelope, Canonical Broker Command, Economic Effect Envelope, and Order Conformance Proof artifacts | Templates only; DRAFT/PENDING/UNKNOWN/non-authorizing/fail-closed | YES | NO |
| Aggregate Risk Policy, Aggregate Risk State Snapshot, Adverse Scenario Set, and Aggregate Risk Decision artifacts | Templates only; DRAFT/INVALID/UNKNOWN/non-authorizing or non-mutating/fail-closed | YES | NO |
| Action Flow Policy, Action Flow State Snapshot, Action Flow Decision, and Action Flow Permit artifacts | Templates only; DRAFT/INVALID/UNKNOWN/non-authorizing/non-mutating/fail-closed | YES | NO |
| Trading Approval Policy, Proposal Approval Request, Independent Approval Decision, and Approval Consumption Record artifacts | Templates only; DRAFT/UNKNOWN/INVALID/non-authorizing/non-mutating/fail-closed | YES | NO |
| Currentness Policy, Safety Currentness Vector, Restrictive Fence Record, and Egress Currentness Proof artifacts | Templates only; DRAFT/UNKNOWN/RESTRICTIVE/non-authorizing/non-mutating/fail-closed | YES | NO |
| Restricted-Live Trial Policy, Trial Plan, Trial Evidence Package, and Production Scope Promotion Decision artifacts | Templates only; DRAFT/INELIGIBLE/INVALID/DENY/non-authorizing/non-mutating/fail-closed | YES | NO |
| Safety Incident Policy, Safety Incident Record, Active Safety Incident Set, Incident Containment Plan, Incident Recovery Handoff Package, and Incident Closure Decision artifacts | Templates only; DRAFT/SUSPECTED/NOT_READY/HOLD/non-authorizing/non-mutating/fail-closed | YES | NO |
| Safety Monitoring Policy, Critical Telemetry and Monitor Coverage Manifests, Continuous Conformance Snapshot, Safety Monitoring Gap, Safety Alert Record, and Alert Escalation Record artifacts | Templates only; DRAFT/INCOMPLETE/UNKNOWN/SUSPECTED/non-authorizing/non-mutating/fail-closed | YES | NO |
| Software Release Policy, reviewed-source, dependency/toolchain-closure, build-provenance, artifact, admission, admitted-set, and runtime-attestation artifacts | Templates only; DRAFT/UNKNOWN/INVALID/DENY/non-authorizing/non-mutating/fail-closed | YES | NO |
| Post-Trade Finality Policy, Economic Obligation Record, Active Economic Obligation Set, Post-Trade Finality Proof, Post-Trade Break Record, and Statement Coverage Manifest artifacts | Templates only; DRAFT/UNKNOWN/UNPROVEN/OPEN/non-authorizing/non-mutating/fail-closed | YES | NO |
| Verification evidence | 372 items registered, all `NOT_IMPLEMENTED` | NO claim of completion | NO |
| Development-track verification evidence | 98 items registered (EVIDENCE-REGISTER-DEV), all `NOT_IMPLEMENTED` | NO claim of completion | NO |

---

## 6. Evidence Completion Meaning

Evidence is complete only when:

- the test mechanism exists;
- the defined fault was actually injected;
- raw and normalized evidence was captured;
- the invariant report passed;
- bounds were measured;
- artifacts were hashed and retained;
- an independent reviewer signed the run;
- the run matches the approved code, configuration, Safety Profile, and Broker Capability Profile.

A written test case, mock output, or design review is not completed verification evidence.

---

## 7. Immediate Engineering Sequence

```text
1. Select and security-review conforming RCL, egress, canonical safety-configuration, human identity, effective-principal, human and automated approval, evidence/replay/recovery, Critical Input/context, venue constraint, Order Construction Policy, Aggregate Risk Policy, Action Flow Policy, Trading Approval Policy, Currentness Policy, Restricted-Live Trial Policy, Software Release Policy, reviewed-source/dependency/toolchain/build-provenance/signing/registry/admission/release-set/runtime-attestation mechanisms, plan/run/abort/promotion registry, evidence-coverage model, owner/dependency registry, Currentness Ordering Domain, restrictive ingress, local latch, per-send proof/claim, independent-validation/common-mode, single-use Intent and promotion consumption, adverse-scenario/state-cut/shared-scope/cause-amplification protocols, deterministic compiler/evaluator/verifier, numeric/unit/mapping/risk/flow/trial/release registry, canonicalization, serializer/SDK, actual-outbound comparison, generation fencing, signing, and independent Human HALT substrates.
2. Assign implementation owners, evidence owners, and independent reviewers for all 372 items in EVIDENCE-REGISTER-002.csv, and for all 98 items in EVIDENCE-REGISTER-DEV.csv.
3. Approve numeric bounds in VERIFICATION-PROFILE-002.
4. Implement capacity, authority, trustworthy-time, live-authorization, effective-principal, human and automated exact approval, single-use Intent consumption, Human HALT, Recovery Barrier, Critical Input/context, venue constraint/admissibility, canonical command, economic-effect, aggregate-risk projection/decision, action-flow decision/permit/reserve, conformance-proof, downstream-mutation, and invalidation state-machine models.
5. Implement orthogonal state, reconciliation-confidence, failure-domain, replacement, and non-trade transition models.
6. Implement durable evidence identities and event capture.
7. Implement the credential-confined Egress Gateway, complete Safety Currentness Vector, Restrictive Fence Record, independently available monotonic deny latch, per-send Egress Currentness Proof, Recovery Generation fence, single-use capability journal, epoch fencing, and bounded claim-to-send checks; remove every direct live broker-order path.
8. Complete the first broker-specific Capability Profile.
9. Build deterministic fault injection.
10. Execute EV-L1 through EV-L3 tests.
11. Execute approved broker capability probes.
12. Perform independent evidence review.
13. Re-evaluate ADR Accepted status only within the proven scope.
```

---

## 8. Gate Verdict

```text
Ready for implementation and test-harness work: YES
Ready for ADR acceptance: NO
Ready for restricted live trading: NO
Ready for production live trading: NO
```

---

## 9. Ratification Ledger

This ledger records the status of the authoring-track ratification defined normatively by GOV-001.
It is non-normative; where it and GOV-001 differ, GOV-001 governs. Nothing below is ratified.

### 9.1 The Three Governance Acts

Ratification, ADR acceptance, and live authorization are distinct acts (GOV-001 G1):

- **Document ratification** establishes an exact document version as the governing baseline. It is the terminal state of the authoring track, is independent of verification-evidence execution, and confers no live authorization, no ADR acceptance, no capacity, and no transmission authority.
- **ADR acceptance** moves an ADR from Proposed to Accepted under the EVIDENCE-REGISTER-002 Gate Rule and VER-002-001 §380, and requires its Architecture RFC to be Ratified.
- **Live authorization** is governed solely by ADR-002-007, ADR-002-025, and RFC-001 SAFE-053; only this act grants live authority.

Ratification is a precondition for acceptance and for live authorization; it substitutes for neither.

### 9.2 Ratification Order

The authoring-track dependency chain (GOV-001; RFC-000 §12):

0. Baseline adoption of vision and philosophy — not ratification (GOV-001 §7); recorded by committed version and date.
1. RFC-000 (Trading Constitution).
2. RFC-001 (Safety Case) — requires the M-06 residual-risk disposition as a named input (now recorded, §4.5).
3. RFC-002 (Architecture) — ADR-002-001..030 do not ratify here; they follow the acceptance track. RFC-002 ratification pins the cited ADR versions. VER-002-001 travels its own §383 approval gate (not ratified).
4. RFC-003..007 (Decision Framework).
5. RFC-008..011 and ADR-DEV-001..015 (Development); VER-DEV-001 via its §8 gate.
6. Operational procedures (runtime) — no ratification vocabulary.

### 9.3 Per-Document Ladder Rung

Ratified count: **3** — RFC-000 v0.16 (RR-0001), GOV-001 v0.1 (RR-0002), and RFC-001 v0.8
(RR-0003), all 2026-07-17, all in §9.7. Ratification-Ready count: **0**. The vision/philosophy
directional baseline is adopted (BA-0001, §9.7). Next candidate: **RFC-002** — P3 is now
satisfied (governing documents RFC-000 and RFC-001 are Ratified); its blocker is P1 (no
external-substrate EV-L0 review has been performed for RFC-002 yet). All other documents' P1
remains unmet corpus-wide. All other normative RFC-class documents remain at Working/Review
Draft; all ADRs remain Proposed; both Verification Evidence specifications remain Proposed.

| Document | Class | Current rung | Ratification-Ready? | Blocking precondition |
|---|---|---|---|---|
| vision | Part-0 (non-normative) | **Baseline adopted** (BA-0001, 2026-07-17) | n/a | not a ratification target (GOV-001 §7) |
| philosophy | Part-0 (non-normative) | **Baseline adopted** (BA-0001, 2026-07-17) | n/a | not a ratification target (GOV-001 §7) |
| RFC-000 | Normative RFC | **Ratified** (v0.16, 2026-07-17) | **YES** | — (record RR-0001, §9.7) |
| RFC-001 | Normative RFC | **Ratified** (v0.8, 2026-07-17) | **YES** | — (record RR-0003, §9.7) |
| RFC-002 | Normative RFC | Review Draft (v0.5) | NO | P1 (external EV-L0 review requested, REQUEST-0005) |
| ADR-002-001..030 | ADR | Proposed | n/a (no ratification ladder) | acceptance track; Parent RFC-002 not Ratified |
| VER-002-001 | Verification Evidence | Proposed | n/a (not ratified) | §383 approval gate |
| RFC-003..007 | Normative RFC | Review Draft | NO | P1; P3 (upstream not Ratified) |
| RFC-008..011 | Normative RFC | Review Draft | NO | P1; P3 (upstream not Ratified) |
| ADR-DEV-001..015 | ADR | Proposed | n/a (no ratification ladder) | acceptance track; Parent RFC not Ratified |
| VER-DEV-001 | Verification Evidence | Proposed | n/a (not ratified) | §8 approval gate |
| GOV-001 | Governance process (content-inert) | **Ratified** (v0.1, 2026-07-17) | **YES** | — (record RR-0002, §9.7) |

### 9.4 Ratification-Ready Precondition Checklist (GOV-001 G3)

A document is Ratification-Ready only when all hold. A precondition that cannot be positively
established is treated as unmet.

- **P1 — Independent EV-L0 review with recorded provenance.** A review meeting the ADR-DEV-005 §7 independence standard has passed at EV-L0 with reviewer provenance recorded per VER-002-001 §5 (§10). Corpus status: **partially established via an external substrate.** The Wave 1–8 internal reviews (§10) do not carry a decorrelation demonstration, so under ADR-DEV-005 §6 AIR-INV-002 they cannot by themselves establish P1. The first external-substrate EV-L0 review (Gemini, vendor Google; §10 External EV-L0 row and its recorded decorrelation argument) supplies the affirmative decorrelation AIR-INV-002 requires. Per-document status:
  - **GOV-001 v0.1 — P1 satisfied.** The external review returned PASS on GOV-001 v0.1 with recorded external-substrate provenance, so P1 is positively established. GOV-001 remains not Ratification-Ready because **P3 is unmet** (upstream RFC-000 not yet Ratified).
  - **RFC-000 — P1 satisfied (2026-07-17).** The external review returned FAIL on RFC-000 v0.15 (1 MAJOR + 1 MINOR); both findings were verified against source and applied in v0.16 (§3.13, patch 0048). The v0.16 delta re-review (GEMINI-EVL0-REQUEST-0002.md → GEMINI-EVL0-VERDICT-0002) returned **PASS with zero residual findings** on the external substrate (owner-captured app UI model "Gemini 3.1 Pro", vendor Google). With P2 (findings resolved, §9.5), P3 (vacuously satisfied — RFC-000 is governed by no higher document), P4, and P5 held, **RFC-000 v0.16 is Ratification-Ready**; the remaining step is the System Owner ratification act recorded per GOV-001 G5.
  - **RFC-001 — P1 satisfied (2026-07-17).** The first external-substrate EV-L0 review (GEMINI-EVL0-REQUEST-0003.md → GEMINI-EVL0-VERDICT-0003) returned **FAIL** on RFC-001 v0.7 with two MAJOR findings (SAFE-050 independent-approval linkage; §14 Hard Safety Envelope non-waiver) plus one flag-only MINOR (SAFE-053 → ADR-002-025 §5.11, unjudgeable from the package — deferred to the acceptance tier). Both MAJOR findings were verified against source and applied in v0.8 (§3.14). The v0.8 delta re-review (GEMINI-EVL0-REQUEST-0004.md → GEMINI-EVL0-VERDICT-0004) returned **PASS with zero residual findings** on the external substrate (owner-captured app UI model "Gemini 3.1 Pro", vendor Google), specifically confirming that the SAFE-050 correction preserves SAFE-053's two-satisfaction-path structure. With P2 (findings resolved, flag-only MINOR explicitly deferred), P3 (satisfied by RR-0001), P4, and P5 held, **RFC-001 v0.8 is Ratification-Ready**; the remaining step is the System Owner ratification act recorded per GOV-001 G5.
  All other corpus documents (beyond GOV-001, RFC-000, and RFC-001) remain **unmet, fail-closed** for P1 — no external review is yet recorded for them; discharging P1 requires an affirmatively decorrelated, human, or demonstrably independent-substrate reviewer.
- **P2 — Findings resolved or explicitly deferred.** Corpus status: 5 of 6 CORPUS-REVIEW-0001 questions resolved in canonical text (§9.5); M-06 now recorded by owner disposition (§4.5); the RFC-002 §20.1 U1/U2/U3 mode-transition seams are resolved in Wave 8 (§3.11).
- **P3 — Upstream documents Ratified.** Corpus status: **satisfied through RFC-001** — RFC-000 v0.16 (RR-0001), GOV-001 v0.1 (RR-0002), and RFC-001 v0.8 (RR-0003) are Ratified, so RFC-002's P3 is satisfied. Documents downstream of RFC-002 (RFC-003 and below) remain P3-blocked until RFC-002 is Ratified; the ratification order of §9.2 governs.
- **P4 — No dangling citation and no unresolved cross-document conflict** (CONSISTENCY-AUDIT-002 clean for the document).
- **P5 — Version stable, not under active revision.**

### 9.5 Open-Questions Disposition (CORPUS-REVIEW-0001)

CORPUS-REVIEW-0001 is a working artifact recorded in the git-excluded `reviews/`; its
open-questions list is dispositioned canonically here.

| # | Open question | Disposition | Canonical evidence |
|---|---|---|---|
| M-06 | Does an out-of-band broker-side final-egress containment path already exist? | **RESOLVED (owner attestation, Wave 9)** | System Owner attested (2026-07-17) that an out-of-band broker-side containment path exists for the final egress enforcement point (credential revocation and account deactivation through broker-side channels), recorded in capability-class terms only; the concrete procedure belongs to a non-normative Broker Capability Profile instance on the implementation track. Closes the finding; EGRESS-EV-013 remains the acceptance-track evidence obligation (`NOT_IMPLEMENTED`). See §4.5. |
| M-04 | CONST-008 "single authoritative source" — account-as-entity, responses-as-evidence? | **RESOLVED** | RFC-000 §6 "Authoritative Source": individual responses, including any single API response, are evidence and SHALL NOT by themselves be treated as unconditionally correct; plus the Authoritative-State term-relationships table. |
| M-07 | ADR-002-001 §6.2 "remain satisfied" — absolute or non-worsening? | **RESOLVED (re-confirmed Wave 8)** | ADR-002-001 §6.2 reformulated as the non-worsening test against the no-protective-action counterfactual; reduces to the prior "remain satisfied" where none exceeded; Review-History M-07. Final v0.7 text confirmed. |
| M-14 | Does ADR-002-021 aggregate projection evaluate the naked-leg case on partial vector approval? | **RESOLVED by existing text (EV-L0 spec-check)** | ADR-002-021: the Adverse Increment Vector SHALL include full and partial fill prefixes and simultaneous credible actions; an alternative is rejected because hedge-leg failure can be worse; ARE-AC-003. The literal "naked-leg" term is absent — coverage confirmed rather than assumed. |
| M-15 | Are LLM-derived interpretations only soft, direction-non-determining evidence? | **RESOLVED** | RFC-003: LLM-derived interpretations are admissible only as soft, non-determining evidence. Residual sub-question (the exact soft-vs-Critical-Input line) noted, non-blocking. |
| mn-14 | Is the backward-only "Depends On" convention intentional? | **RESOLVED** | preface Conventions: "Depends On" headers are backward-only; forward dependencies live in each ADR's Approval Gate section. |

The Wave-7 mode-transition items U1/U2/U3 (RFC-002 §20.1) recorded as debt in §3.10 are
**resolved in Wave 8** (§3.11): U1 by the new ADR-002-001 §8.5 normative de-restriction decision,
U2 by the ADR-002-007 §14.1 enumeration, and U3 by the §20.1 informative naming-map. No open
ratification-blocking mode-transition seam remains.

### 9.6 Residual-Debt Classification (ratification-blocking vs acceptance-track)

| §4.5 item | Classification | Blocks ratification? |
|---|---|---|
| M-06 out-of-band egress containment existence | Owner-decision-required (now recorded, §4.5) + acceptance-track (EGRESS-EV-013) | No — the owner disposition is the required residual-risk-acceptance input to RFC-001 ratification and is now recorded; EGRESS-EV-013 remains an acceptance-track obligation |
| No execution (all 372 Part-1 / 98 development-track items `NOT_IMPLEMENTED`) | Acceptance/live-track only | No — the corpus can be fully ratified with zero evidence executed; ratification is evidence-independent (GOV-001 G1) |
| TRACEABILITY-MATRIX-002 §5.3 source gaps (ADR-002-002..006) | Acceptance-track, explicitly deferred (no coverage lost) | No — but must be listed as a deferred item in RFC-002's ratification record (P2) |
| Part-2/3 ratification pending | This is the plan (§9.2) | N/A |

### 9.7 Ratification Records

Each ratification is recorded here per the GOV-001 G5 schema — the target document and its exact
version and commit; the decision and date; the ratifying authority and the conformance attestor;
the passing independent EV-L0 review and its provenance; the P1–P5 evidence; accepted and deferred
requirements; residual risks accepted by the System Owner; the cited-version pins; the Ratified
upstream documents relied upon; the effective date; and the re-review or expiry trigger — and
states that the ratification confers no live authority, no ADR acceptance, and no capacity.

#### RR-0001 — RFC-000 v0.16 (Trading Constitution) — RATIFIED

- **Target:** RFC-000 — Trading Constitution, version 0.16 (content commit `3bed676d`).
- **Decision:** RATIFIED. **Date / effective:** 2026-07-17.
- **Ratifying authority:** System Owner (vision §12.1). **Conformance attestor:** Architecture
  Board role (vision §12.2) — both roles held by the same natural person per GOV-001 G4 and the
  vision §12 closing note; ratification confers no live authority, so RFC-001 SAFE-053 does not
  apply to this act.
- **Independent EV-L0 review (P1):** external substrate — GEMINI-EVL0-VERDICT-0001 (v0.15: FAIL,
  1 MAJOR + 1 MINOR, both verified against source and applied in v0.16) and
  GEMINI-EVL0-VERDICT-0002 (v0.16 delta: PASS, zero residual findings). Provenance: the §10
  External EV-L0 rows (Gemini app, vendor Google; owner-captured app UI model "Gemini 3.1 Pro";
  no tools/browsing; recorded decorrelation argument per ADR-DEV-005 AIR-INV-002).
- **P1–P5 evidence:** §9.4 — P1 satisfied (2026-07-17); P2 findings resolved and open questions
  dispositioned (§9.5); P3 vacuously satisfied (RFC-000 is governed by no higher document,
  GOV-001 G3); P4 no dangling citation (DEC/TEST namespaces instantiated, ARCH-xxx explicitly
  reserved); P5 version stable at v0.16.
- **Accepted requirements:** the full v0.16 normative text — CONST-001..CONST-015, the §5
  requirement structure and North Star precedence mapping, the §8 axioms, the §12 governance
  hierarchy with the narrow-only meta-principle, and the §18 amendment process.
- **Deferred:** the ARCH-xxx derived-requirement namespace remains explicitly reserved; no other
  deferral.
- **Residual risks accepted:** none arising from the RFC-000 document text itself.
- **Cited-version pins:** GOV-001 v0.1 (the §13 governance-process delegation and the §18
  ratifying-authority reference). A change to the pinned clauses triggers a citation-integrity
  re-check of RFC-000 (GOV-001 G6).
- **Re-review trigger:** any material change proceeds only through the RFC-000 §18 amendment
  process and re-ratification (GOV-001 G6); de-ratification per GOV-001 G7.
- **Non-authority statement:** this ratification establishes RFC-000 v0.16 as the governing
  baseline and confers no live authorization, no ADR acceptance, and no capacity.

#### RR-0002 — GOV-001 v0.1 (Ratification and Change Governance) — RATIFIED

- **Target:** GOV-001 — Ratification and Change Governance, version 0.1 (content commit
  `cb7f8a65`, unchanged since creation).
- **Decision:** RATIFIED. **Date / effective:** 2026-07-17.
- **Ratifying authority:** System Owner (vision §12.1). **Conformance attestor:** Architecture
  Board role (vision §12.2) — both roles held by the same natural person per GOV-001 G4;
  ratification confers no live authority, so RFC-001 SAFE-053 does not apply to this act. This
  is the controlled self-reference G2 anticipates: GOV-001 is ratified under the process it
  defines, recorded here.
- **Independent EV-L0 review (P1):** external substrate — GEMINI-EVL0-VERDICT-0001, GOV-001
  v0.1 verdict **PASS**; the reviewer specifically challenged the three-act separation, the
  single-operator ratifier argument, and the de-ratification fail-safe and found them sound.
  Provenance: §10 (Gemini app, vendor Google; owner-captured app UI model "Gemini 3.1 Pro";
  no tools/browsing; recorded decorrelation argument per ADR-DEV-005 AIR-INV-002).
- **P1–P5 evidence:** §9.4 — P1 satisfied; P2 all internal-review findings fixed before the
  creating commit and zero external findings; P3 satisfied by RR-0001 (RFC-000 v0.16 Ratified);
  P4 citations resolve; P5 version stable at v0.1.
- **Accepted requirements:** the full v0.1 normative text — G1 through G8, the status ladder,
  preconditions P1–P5, the ratification-record schema, Baseline Adoption (§7), amendment and
  re-ratification (G6), de-ratification (G7), and the non-authority safety belt (G8).
- **Deferred:** none. **Residual risks accepted:** none arising from the document text.
- **Cited-version pins:** RFC-000 v0.16 (the §13 delegation GOV-001 derives its authority
  from, and the §18 amendment procedure it operates). A change to the pinned clauses triggers
  a citation-integrity re-check of GOV-001 (G6).
- **Re-review trigger:** material change via RFC-000 §18 amendment + re-ratification (G6);
  de-ratification per G7.
- **Non-authority statement:** this ratification establishes GOV-001 v0.1 as the governing
  process baseline and confers no live authorization, no ADR acceptance, and no capacity.

#### BA-0001 — vision.md and philosophy.md — BASELINE ADOPTED (GOV-001 §7)

- **Target:** `part-0-introduction/vision.md` (v0.1 Draft, created 2026-07-13) and
  `part-0-introduction/philosophy.md` (v0.1 Draft, created 2026-07-13), as present at commit
  `d0805ad2` — both unmodified throughout the CORPUS-REVIEW-0001 resolution track.
- **Act:** the System Owner records these versions as the accepted directional baseline from
  which the normative corpus derives (GOV-001 §7). **Date:** 2026-07-17.
- **Effect:** none beyond the record — Baseline Adoption modifies neither document and confers
  no requirement, no authority, and no live readiness; the documents remain non-normative and
  are not ratification targets (GOV-001 G2).

#### RR-0003 — RFC-001 v0.8 (Safety Case) — RATIFIED

- **Target:** RFC-001 — Trading Operating System Safety Case, version 0.8 (content commit
  `904299cd`).
- **Decision:** RATIFIED. **Date / effective:** 2026-07-17.
- **Ratifying authority:** System Owner (vision §12.1). **Conformance attestor:** Architecture
  Board role (vision §12.2) — both roles held by the same natural person per GOV-001 G4;
  ratification confers no live authority, so SAFE-053 does not apply to this act.
- **Independent EV-L0 review (P1):** external substrate — GEMINI-EVL0-VERDICT-0003 (v0.7:
  FAIL, 2 MAJOR verified against source and applied in v0.8; 1 flag-only MINOR deferred) and
  GEMINI-EVL0-VERDICT-0004 (v0.8 delta: PASS, zero residual findings; SAFE-053
  two-satisfaction-path preservation specifically confirmed). Provenance: the §10 External
  EV-L0 rows (Gemini app, vendor Google; owner-captured app UI model "Gemini 3.1 Pro"; no
  tools/browsing; recorded decorrelation argument per ADR-DEV-005 AIR-INV-002).
- **P1–P5 evidence:** §9.4 — P1 satisfied (2026-07-17); P2 findings resolved with the explicit
  deferrals below; P3 satisfied by RR-0001 (RFC-000 v0.16 Ratified); P4 citations resolve
  (references to Proposed ADRs are acceptance-track, narrow-only); P5 version stable at v0.8.
- **Accepted requirements:** the full v0.8 normative text — HAZ-001..HAZ-025, SAFE-001..
  SAFE-054, the safety claims, the §12 Constitutional Verification Matrix, the §13 production
  gates, the §14 non-waivable set (eight items, including the Hard Safety Envelope), the §15
  evidence-register obligations, and the §17 ratification linkage to GOV-001.
- **Deferred (explicit, with rationale):** (1) the flag-only MINOR of VERDICT-0003 — whether
  ADR-002-025 §5.11 quantifiably bounds the SAFE-053 variant-path "Progressive Promotion
  step" — is verified at the ADR-acceptance tier, not at document ratification (ADRs are
  Proposed and evidence-gated); (2) all evidence execution — every SAFE requirement remains
  `NOT_IMPLEMENTED` in the registers (372/98); ratification is evidence-independent by design
  (GOV-001 G1).
- **Residual risks accepted:** none new. The M-06 out-of-band final-egress containment path is
  owner-attested to exist (2026-07-17, §4.5/§9.5) in capability-class terms; EGRESS-EV-013
  remains the acceptance-track evidence obligation.
- **Cited-version pins:** RFC-000 v0.16 (Ratified, governing), GOV-001 v0.1 (Ratified, §17
  ratification linkage), ADR-002-015 v0.2 (SAFE-053 two-path mechanism), ADR-002-025 v0.2
  (SAFE-053 variant scope bound), ADR-002-026 v0.3 (§14 non-waivable mirror). Other ADR
  citations follow the Proposed-tier acceptance track and cannot weaken this Ratified text
  (RFC-000 §12 narrow-only). A change to a pinned clause triggers a citation-integrity
  re-check (GOV-001 G6).
- **Re-review trigger:** material change via RFC-000 §18 amendment + re-ratification (GOV-001
  G6); de-ratification per G7.
- **Non-authority statement:** this ratification establishes RFC-001 v0.8 as the governing
  safety-case baseline and confers no live authorization, no ADR acceptance, and no capacity.

*(empty)*

---

## 10. Wave Review Provenance Record

This record discharges the M-18 provenance obligation that VER-002-001 §5 and §9.4 place on the
corpus's own EV-L0 reviews: every EV-L0 review of a corpus document SHALL record its reviewer
provenance per the ADR-DEV-005 §7 independence standard. It is provenance metadata about existing
EV-L0 design inspections, not a new executable evidence item; it adds no row to either Evidence
Register (Part-1 stays 372; development track stays 98).

| Review | Target | Reviewer substrate | Determining inputs | Date | Disposition |
|---|---|---|---|---|---|
| CORPUS-REVIEW-0001 (9 lenses) | Entire corpus | 8× `oh-my-claudecode:critic` + 1× `deep-reasoner` subagents, model session-inherited (`claude-fable-5`), independent isolated context lanes, read-only; orchestrator synthesis on `claude-fable-5` | canonical corpus text; vision/philosophy baseline; prior CONSISTENCY-AUDIT-002 / gate-status (known-issue exclusion) | 2026-07-16..17 | Report issued (working artifact) |
| Wave 1 EV-L0 | RFC-001 / ADR-002-015 / 025 / 026 / 027 / DR-0001 | `oh-my-claudecode:critic`, `claude-fable-5` (session-inherited), separate lane from author (`deep-reasoner`, `claude-fable-5`) | uncommitted git diff; CORPUS-REVIEW-0001 CR-02; canonical originals | 2026-07-17 | APPROVE-WITH-FIXES → fixes applied → committed de57c55e |
| Wave 2 EV-L0 | RFC-000 v0.12 / RFC-001 v0.5 | Same pattern (critic, fable-5, separate lane) | git diff; M-01..M-06; originals | 2026-07-17 | APPROVE-WITH-FIXES → c3f43fa1 |
| Wave 3 EV-L0 | VER / register / ADR-001·002 / RFC-001 v0.6 | critic (fable-5); author: deep-reasoner design + `oh-my-claudecode:executor` (`claude-opus-4-8` explicitly specified) applied | git diff; spec; originals | 2026-07-17 | APPROVE → 455b363f |
| Wave 4 EV-L0 | VER-DEV-001 / register-DEV / RFC-000 v0.13 et al. | critic (fable-5); designer deep-reasoner + executor (opus-4-8) | git diff; spec; inventory | 2026-07-17 | APPROVE-WITH-FIXES → d1020a09 |
| Wave 5 EV-L0 | RFC-003 v0.2 / ADR-DEV-007 v0.2 / RFC-006 v0.2 | critic (fable-5); author deep-reasoner (applied directly) | git diff; M-13..15; originals | 2026-07-17 | APPROVE-WITH-FIXES → 8dbe9b4e |
| Wave 6 EV-L0 | ADR-002-001 v0.5 and 15 others | critic (fable-5); designer deep-reasoner + executor (opus-4-8) | git diff; 6 spec judgments; originals | 2026-07-17 | APPROVE-WITH-FIXES → 9391fa83 |
| Wave 7 EV-L0 | RFC-000 v0.14 / RFC-002 v0.3 et al. | critic (fable-5); designer deep-reasoner + executor (opus-4-8) | git diff; spec; originals | 2026-07-17 | ACCEPT → 7e7ee9cb |
| Wave 8 EV-L0 | ADR-002-001 v0.7 / ADR-002-007 v0.2 / RFC-002 v0.4 | critic (fable-5); designer deep-reasoner + executor (opus-4-8) | git diff; spec; originals | 2026-07-17 | APPROVE-WITH-FIXES → c861da82 |
| External EV-L0 (GOV-001 G3 P1) | RFC-000 v0.15 + GOV-001 v0.1 | Gemini app (vendor Google), human-relayed; self-reported "Gemini 1.5 Pro", owner-captured app UI model "Gemini 3.1 Pro" (same-day follow-up session) — self-report recorded as unreliable for version identity, UI capture the better evidence | GEMINI-EVL0-REQUEST-0001.md package only (RFC-000 v0.15, GOV-001 v0.1, vision, philosophy baselines); no tools/browsing | 2026-07-17 | RFC-000: FAIL (1 MAJOR + 1 MINOR — verified against source, applied in v0.16); GOV-001: PASS |
| External EV-L0 delta (GOV-001 G3 P1) | RFC-000 v0.16 (delta of the v0.15 findings) | Gemini app (vendor Google), human-relayed; owner-captured app UI model "Gemini 3.1 Pro"; self-report version-less ("Gemini") | GEMINI-EVL0-REQUEST-0002.md package only (change summary; corrected §5 schema; full corrected CONST-001/002/003; corrected precedence-table lead-in); no tools/browsing | 2026-07-17 | PASS — zero residual findings; RFC-000 P1 satisfied (GEMINI-EVL0-VERDICT-0002; a prior preamble-only void attempt correctly FAILed for missing material and is superseded) |
| External EV-L0 (GOV-001 G3 P1) | RFC-001 v0.7 | Gemini app (vendor Google), human-relayed; owner-captured app UI model "Gemini 3.1 Pro" (authoritative); self-report version mismatch **recurred** — self-report "Gemini 1.5 Pro (operating under Gemini instructions)" recorded as unreliable for version identity, consistent with the VERDICT-0001 correction note | GEMINI-EVL0-REQUEST-0003.md package only (RFC-001 v0.7, RFC-000 v0.16 Ratified, vision, philosophy baselines); no tools/browsing | 2026-07-17 | **FAIL** — 2 MAJOR (SAFE-050 independent-approval linkage; §14 Hard Safety Envelope non-waiver — both verified against source and applied in v0.8) + 1 flag-only MINOR (SAFE-053 → ADR-002-025 §5.11, unjudgeable from the package — deferred to acceptance tier); GEMINI-EVL0-VERDICT-0003; v0.8 delta re-review pending (REQUEST-0004) |
| External EV-L0 delta (GOV-001 G3 P1) | RFC-001 v0.8 (delta of the v0.7 findings) | Gemini app (vendor Google), human-relayed; owner-captured app UI model "Gemini 3.1 Pro"; self-report version-less ("Gemini") | GEMINI-EVL0-REQUEST-0004.md package only (change summary; post-fix SAFE-050 incl. Derived-from; post-fix §14 list; context-only §12/ADR-002-026 sync); no tools/browsing | 2026-07-17 | **PASS** — zero residual findings; SAFE-053 two-satisfaction-path preservation specifically confirmed; RFC-001 P1 satisfied (GEMINI-EVL0-VERDICT-0004) |

**Honesty limitation (internal reviews).** Lane separation (not-the-author, not-author-rerun,
read-only) is established for every review above. For the CORPUS-REVIEW-0001 and Wave 1–8 rows,
substrate decorrelation is NOT established — those authors and reviewers ran on the same
session-inherited model family. This limitation is recorded rather than obscured (M-18
falsifiability). Under ADR-DEV-005 §6 AIR-INV-002 this is not a discretionary judgment: absent an
affirmative decorrelation demonstration, a same-model-family AI-on-AI review is treated as
common-mode and fails closed, so those internal reviews cannot by themselves positively establish
GOV-001 G3(P1) (see §9.4 P1).

**External-substrate decorrelation argument (GOV-001 G3 P1).** The External EV-L0 row above is
recorded as the affirmative decorrelation demonstration that AIR-INV-002 requires for the review of
an AI-authored artifact. The reviewer substrate is a different vendor (Google) with a different
model lineage and a different training/alignment pipeline than the authoring and internal-review
substrate (the Anthropic Claude family). Under ADR-DEV-005 §6 AIR-INV-002, decorrelation may be
shown by "disjoint determining training/data provenance to the extent establishable, or a recorded
decorrelation argument"; distinct vendor, lineage, and pipeline are the establishable disjoint
provenance, and this paragraph is that recorded argument. The residual — possible overlap in the
public web-corpus pretraining data shared across vendors — cannot be eliminated and is honestly
recorded, not obscured (M-18 falsifiability). The substrate identity rests on the reviewer's
PROVENANCE SELF-REPORT (the Gemini app UI model name was not separately captured); the verdict is
preserved verbatim in reviews/GEMINI-EVL0-VERDICT-0001.md. On this basis the external review
positively establishes P1 for GOV-001 v0.1 (verdict PASS); for RFC-000 the v0.15 verdict was FAIL
and the two findings are applied in v0.16, so RFC-000 P1 is pending the v0.16 delta re-review
(GEMINI-EVL0-REQUEST-0002.md) — see §9.4.

The Wave-9 changes recorded in §3.12 are themselves EV-L0 review items; their provenance row SHALL
be appended here once their independent review completes.
