# TOS Safety Architecture Gate Status

- **Date:** 2026-07-14
- **Scope:** Consolidated RFC-002 v0.2 and ADR-002-001 through ADR-002-018
- **Architecture Documentation:** Phase B and the follow-on RCL consensus, final-egress security, safety-configuration governance, human-authority governance, evidence-integrity/replay, safe-start/recovery-barrier, and Critical Input/decision-context decisions are authored; acceptance cases are registered; every ADR remains Proposed and execution evidence remains open
- **Latest Architecture Review:** ADR-002-002 through ADR-002-017 PASS at document-review level; ADR-002-018 independent document review pending; no status or live-readiness promotion
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
20. VER-002-001 Safety-Critical Architecture Verification Evidence Specification
21. Evidence Register and configuration/evidence templates

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
- Hard Safety Envelope and Runtime Safety Profile artifacts are immutable, authenticated, content-addressed, semantically canonical, separately governed, and bound as one closed Safety Configuration Bundle.
- profile activation is break-before-make and quorum-ordered by one exact Profile Generation; distribution, signatures, repository merge, deployment health, or an Activation Record alone do not arm live scope.
- partial, mixed, incompatible, stale, expired, restored, or rollback configuration fails closed; Restrictive Overrides can only narrow, never release capacity, erase economic effect, auto-revert, or re-arm.
- human dual control counts distinct effective natural persons rather than accounts, credentials, devices, sessions, role labels, or recovery paths.
- Approval Requests, Attestations, and Approval Sets bind one exact current context; a set is consumed once and is never configuration, capacity, protective-classification, Live Authorization, or broker-transmission authority.
- one current authenticated Human Safety Principal may invoke a monotonic restrictive HALT without a permissive quorum; break-glass can only deny, narrow, HALT, or request separately authorized containment.
- delegation, roster change, identity recovery, approval expiry/revocation, workflow recovery, or compromise cannot multiply quorum, erase economic effect, or automatically re-arm.
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
| Reconciliation and recovery | §15 and §23 | Added per-field bounds, external-detection bound, startup barrier, and explicit non-automatic re-arm gate | SAFE-022, 023, 024, 041, 044, 046, 048 |
| Failure domains and verification | §24 and §29 | Added common-mode allocation and measurable trigger/detection/containment/pass-fail obligations | SAFE-011, 041, 045, 048, 051, 052 |
| ADR backlog and findings | §26 and §31 | Preserved IDs ADR-002-002 through 018 and mapped A-01 through A-14 to canonical sections | Corrected the earlier erroneous “009 through 017” history note while later allocating canonical ADR-002-017 to safe startup/recovery and ADR-002-018 to Critical Input integrity |

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
- ADR IDs remain ADR-002-001 through ADR-002-018; ADR-002-002 through ADR-002-018 remain Proposed.
- Every `SAFE-xxx` identifier in the RFC-002 and ADR-002-001 traceability tables exists in RFC-001.
- The Evidence Register contains 219 `NOT_IMPLEMENTED` items, including one-to-one STATE, RECON, TIME, REARM, FD, PR, NT, RCLP, EGRESS, SPG, HAG, ERI, SBR, and CII coverage for ADR-002-005 through ADR-002-018. Registration created no verification evidence or live authority.

---

## 4. Remaining Architecture and Acceptance Work

ADR-002-005 through ADR-002-018 are authored as `Proposed`. Phase B and follow-on RCL-consensus, final-egress-security, safety-configuration-governance, human-authority-governance, evidence-integrity/replay, safe-start/recovery-barrier, and Critical Input/decision-context authorship are complete, but none of those decisions is accepted.

ADR-002-007 selects the egress-currentness protocol, ADR-002-012 selects quorum ordering and RCL writer fencing, ADR-002-013 selects the effective final-egress security boundary, ADR-002-014 selects immutable safety-configuration artifacts and activation, ADR-002-015 selects effective-human identity, exact approvals, dual control, independent Human HALT, and break-glass confinement, ADR-002-016 selects immutable causal evidence, pre-effect durability, integrity anchoring, gap containment, protected retention, and isolated deterministic replay, ADR-002-017 selects closed startup, monotonic Recovery Generations, fenced recovery ownership, conservative Inventory Cuts, dependency-complete obligations, non-authorizing readiness, partial-scope isolation, and fresh re-arm handoff, and ADR-002-018 selects Critical Input classification, source continuity/provenance, exact transformation lineage, immutable Snapshots/Capsules, independent approval common-mode analysis, correction/invalidation fan-out, and active final-egress context currentness. The conforming replicated-state-machine product, non-exportable signer or credential service, configuration registry/signing substrate, semantic-normalization and compatibility-manifest implementation, human identity provider, phishing-resistant authenticator, Effective Principal Graph, approval workflow, quorum and delegation policy, Approval Set consumption mechanism, restrictive HALT ingress/latch, evidence store and acknowledgement mechanism, independent emergency journal, source identity and sequence scheme, external integrity anchor, gap detector, protected raw tier, redaction/export control, retention/deletion policy, isolated replay substrate, Recovery Barrier Policy, trigger classifier, dependency graph, Recovery Generation/owner fence, broker/source Inventory Cut protocol, obligation workflow, package signer, Critical Input Policy, source registry and continuity protocol, schema/unit/mapping registry, transformation manifests, consistency-cut rules, independent approval input paths, Context Generation, invalidation graph, voter and Active Egress Principal topology, identity-aware route, proof encoding/cryptography, authenticated session transport, broker hard-fence mechanism, numeric bounds, and concrete Failure-Domain Allocation Matrix remain acceptance blockers. Other blockers remain for safe protective-replacement modes and broker semantics, non-trade transition and source-authority rules, and Time Health Snapshot distribution.

Dedicated VER-002-001 and Evidence Register entries now exist for ADR-002-005 through ADR-002-018, but all remain `NOT_IMPLEMENTED`. Verification Profile `0.9-PROPOSED` additionally binds the proposed Critical Input Policy and adds unapproved `B_critical_input_loss_detect`, `B_critical_input_invalid_to_authority`, `B_critical_input_invalid_to_egress`, `MAX_critical_input_snapshot_age_ms`, and `MAX_decision_context_age_ms` values while retaining all earlier unapproved bounds. The profile remains unapproved with `approved_by: []`; unresolved values reduce authority and keep live operation prohibited.

### 4.1 Latest Review Disposition

The ADR-002-015 architecture review passed its document and integration scope with no Critical or Major finding. Its sole Minor finding identified a dangling `ADR-002-003 §9.5` citation; commit `fdce384e` records the correction and review disposition.

The latest independent document review reported ADR-002-016 and its integration as PASS. No finding requiring disposition was supplied with that verdict. The review result changes no ADR status: evidence-store, durable-ingress, emergency-journal, integrity-anchor, gap-detection, retention, redaction, replay-isolation, security-review, numeric-bound, and executed-evidence gates remain open. A document-review PASS is EV-L0 evidence only and creates no capacity, authority, broker permission, verification completion, or live readiness.

The independent ADR-002-017 document and adversarial-sequence review found no Critical or Major issue. Four Minor findings were resolved conservatively: the nonexistent SAFE-049 range implication was replaced with explicit real SAFE IDs; Recovery Generation and readiness currentness now explicitly reject TTL, heartbeat, health, eventual-consistency, and absence-of-invalidation substitutes; ADR-002-013 now binds and verifies the exact current recovery package, decision, scope, validity, and invalidation status at every send; and `OPEN_FOR_NON_LIVE` was renamed `CLOSED_NON_LIVE`. These citation and clarity corrections do not change authority, evidence, or live-readiness status.

ADR-002-018 and its CII verification/template integration are newly authored and await independent document, adversarial-sequence, security-boundary, traceability, and gate review. Authorship and registration are EV-L0 inputs only and do not constitute a review PASS or executed evidence.

```text
ADR-002-002 through ADR-002-017 status: Proposed; document review PASS
ADR-002-018 status: Proposed; independent document review pending
ADR-002-016 independent document review: PASS; no finding supplied for disposition
ADR-002-017 independent document review: PASS; four Minor findings resolved
ADR acceptance: NO
Restricted-live readiness: NO
Production readiness: NO
```

The Proposed status is preserved because the applicable approval gates, including ADR-002-007 §25, still require protocol implementation, independent security review, approved bounds, and executed evidence. A passed document review is not verification completion and creates no live authority.

---

## 5. Current Approval State

| Artifact | Current state | Can implement? | Can accept? |
|---|---|---:|---:|
| RFC-002 v0.2 | Consolidated Review Draft | YES | after RFC review gates pass |
| ADR-002-001 v0.2 | Proposed | YES | after protective evidence passes |
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
| VER-002-001 | Proposed, ready for test implementation | YES | after evidence workflow review |
| Verification Profile 0.9 | `PROPOSED`, `approved_by: []` | YES, as draft | NO |
| Broker-specific Capability Profile | Template only | YES | NO |
| Human authority artifacts | Templates only, all non-authorizing | YES | NO |
| Evidence integrity and replay artifacts | Templates only, all DRAFT/unverified/non-authorizing | YES | NO |
| Recovery barrier, session, inventory-cut, obligation, evidence-package, and readiness artifacts | Templates only; default states are DRAFT/TRIGGERED/PENDING/NOT_READY and non-authorizing/fail-closed | YES | NO |
| Critical Input Policy, Snapshot, and Decision Context Capsule artifacts | Templates only; DRAFT/INVALID/non-authorizing/fail-closed | YES | NO |
| Verification evidence | 219 items registered, all `NOT_IMPLEMENTED` | NO claim of completion | NO |

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
1. Select and security-review conforming RCL, egress, canonical safety-configuration, human identity, effective-principal, approval, evidence-store, durable-ingress, emergency-journal, integrity-anchor, gap-detection, protected-retention, isolated-replay, Recovery Barrier Policy, Recovery Generation/owner fence, dependency graph, Inventory Cut, obligation workflow, Critical Input Policy, source continuity, schema/unit/mapping registry, transformation lineage, Context Generation, context invalidation, registry, signing, semantic-validation, compatibility-manifest, and independent Human HALT substrates.
2. Assign implementation owners, evidence owners, and independent reviewers for all 219 items in EVIDENCE-REGISTER-002.csv.
3. Approve numeric bounds in VERIFICATION-PROFILE-002.
4. Implement capacity, authority, trustworthy-time, live-authorization, effective-principal, exact-approval, Human HALT, Recovery Barrier, Recovery Session, Inventory Cut, obligation, readiness, Critical Input, Snapshot, Capsule, common-mode, and invalidation state-machine models.
5. Implement orthogonal state, reconciliation-confidence, failure-domain, replacement, and non-trade transition models.
6. Implement durable evidence identities and event capture.
7. Implement the credential-confined Egress Gateway, authenticated currentness session, monotonic deny latch, Recovery Generation fence, single-use capability journal, epoch fencing, and bounded claim-to-send checks; remove every direct live broker-order path.
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
