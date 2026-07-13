# TOS Safety Architecture Gate Status

- **Date:** 2026-07-13
- **Scope:** Consolidated RFC-002 v0.2 and ADR-002-001 through ADR-002-008
- **Architecture Documentation:** Consolidated for the current Proposed gate; ADR-002-009 through ADR-002-011 remain open
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
10. VER-002-001 Safety-Critical Architecture Verification Evidence Specification
11. Evidence Register and configuration/evidence templates

---

## 2. Closed Architecture Questions

The current bundle decides:

- Risk Capacity Ledger is the sole serialization and mutation authority for capacity.
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

---

## 3. Repository Merge Map

The review files were section-level amendments, not repository-aware diffs. Their normative content was consolidated into the canonical RFC and ADR sections as follows.

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
| ADR backlog and findings | §26 and §31 | Preserved IDs ADR-002-002 through 011 and mapped A-01 through A-14 to canonical sections | Corrected the erroneous “009 through 017” history note |

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
- ADR IDs remain ADR-002-001 through ADR-002-011; ADR-002-002 through ADR-002-008 remain Proposed.
- Every `SAFE-xxx` identifier in the RFC-002 and ADR-002-001 traceability tables exists in RFC-001.
- The Evidence Register contains 89 `NOT_IMPLEMENTED` items, including dedicated TIME-EV-001..010 and REARM-EV-001..012 coverage. Registration created no verification evidence or live authority.

---

## 4. Remaining Architecture ADRs

ADR-002-005 through ADR-002-008 are now authored as `Proposed`. The following decisions remain Required and do not block non-live implementation of the current verification harness:

- ADR-002-009 — Failure-Domain Isolation and Deployment Safety
- ADR-002-010 — Corporate Actions and Non-Trade State Changes
- ADR-002-011 — Protective Replacement and Protection-Gap Control

Some of these are required before production approval even when the current ADR acceptance tests pass.

Acceptance-blocking implementation decisions also remain for the currentness distribution and fenced-send mechanism, the numeric egress-containment bounds, Time Health Snapshot distribution, and authenticated human dual-control roles. The corresponding Verification Profile values remain unapproved; unresolved choices reduce authority and keep live operation prohibited.

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
| VER-002-001 | Proposed, ready for test implementation | YES | after evidence workflow review |
| Broker-specific Capability Profile | Template only | YES | NO |
| Verification evidence | 89 items registered, all `NOT_IMPLEMENTED` | NO claim of completion | NO |

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
1. Complete ADR-002-009, then ADR-002-011, then ADR-002-010.
2. Extend VER-002-001 and EVIDENCE-REGISTER-002 for ADR-002-005 and ADR-002-006; ADR-002-007/008 cases are registered but not implemented.
3. Assign owners and reviewers in EVIDENCE-REGISTER-002.csv.
4. Approve numeric bounds in VERIFICATION-PROFILE-002.
5. Implement capacity, authority, trustworthy-time, and live-authorization state-machine models.
6. Implement durable evidence identities and event capture.
7. Implement epoch/fencing and final egress checks.
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
