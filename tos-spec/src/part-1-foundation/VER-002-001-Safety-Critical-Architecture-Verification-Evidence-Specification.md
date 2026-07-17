# VER-002-001 — Safety-Critical Architecture Verification Evidence Specification

- **Status:** Proposed — Ready for Test Implementation
- **Date:** 2026-07-14
- **Verification Scope:** Consolidated RFC-002 v0.2; consolidated ADR-002-001 v0.2; ADR-002-002 through ADR-002-030
- **Current Evidence State:** Dedicated acceptance-case evidence specifications are registered for ADR-002-005 through ADR-002-030; implementation evidence has not been executed
- **Extension State:** ADR-002-005 through ADR-002-030 map one-to-one to their dedicated STATE, RECON, REARM, TIME, FD, NT, PR, RCLP, EGRESS, SPG, HAG, ERI, SBR, CII, VTG, IOC, ARE, AFG, IAP, CUR, RLP, WDR, SIR, STM, SCI, and PTF evidence families. Registration is not completed evidence
- **Production Authorization:** Prohibited until the applicable evidence gates are passed

---

## 1. Purpose

This specification defines the evidence required to demonstrate that the Trading Operating System enforces its safety architecture under normal operation, concurrency, crash, partition, broker ambiguity, stale authority, and recovery.

It does not claim that the system has passed verification. It defines:

- what must be tested;
- how faults must be injected;
- which invariants must remain true;
- what raw and derived evidence must be retained;
- how pass/fail is determined;
- which ADR approval gate each test supports;
- how evidence is reviewed, versioned, and invalidated.

Documentation, code inspection, audit logs, and replay are not substitutes for runtime prevention. They are evidence that prevention occurred.

---

## 2. Verification Principles

### 2.1 Safety Properties Are Executable Claims

Every Critical architectural property SHALL be associated with:

- a testable trigger;
- a measurable detection or containment bound;
- an observable expected state transition;
- a fail condition;
- an evidence owner;
- an independent reviewer.

### 2.2 Negative Results Are Evidence

Failed runs, contradictory broker observations, and invariant violations SHALL be retained. They may not be deleted or replaced by a later passing run without traceability.

### 2.3 Evidence Must Be Reproducible

A reviewer SHALL be able to identify:

- exact code and configuration;
- environment;
- broker profile;
- test seed and fault schedule;
- initial authoritative state;
- all external inputs;
- final authoritative state;
- invariant evaluation;
- raw broker evidence.

### 2.4 Conservative Ambiguity

If a run cannot prove that a safety property held, its result is `INCONCLUSIVE`, not `PASS`.

`INCONCLUSIVE` blocks the relevant approval gate.

### 2.5 Production-Like Failure Semantics

A mock may validate internal logic but cannot establish external broker semantics. Broker-specific capabilities require controlled evidence at the assurance level defined by ADR-002-004.

### 2.6 Independent Review

Critical evidence SHALL be reviewed by a principal who did not implement the tested mechanism and did not approve the relevant residual-risk exception.

---

## 3. Verification Object Baseline

Every evidence run SHALL bind to an immutable baseline containing:

- repository commit SHA;
- build artifact digest;
- RFC/ADR versions;
- Hard Safety Envelope version;
- Runtime Safety Profile version;
- Human Authority Policy generation and digest;
- Effective Principal Graph generation and digest;
- Evidence Integrity Policy generation and digest;
- Recovery Barrier Policy generation and digest;
- Critical Input Policy generation and digest;
- Venue Constraint Policy generation and digest;
- Trading Approval Policy generation and digest;
- Currentness Policy generation and digest;
- Restricted-Live Trial Policy generation and digest;
- Broker Capability Profile version;
- Verification Profile version;
- database/schema migration version;
- deployment manifest digest;
- workload identities and key versions;
- environment identifier;
- test harness version;
- fault-injection schedule and seed.

A run without a complete baseline is invalid.

---

## 4. Result States

Each evidence item SHALL have one status:

```text
NOT_IMPLEMENTED
READY
RUNNING
PASS
FAIL
INCONCLUSIVE
BLOCKED
EXPIRED
SUPERSEDED
WAIVED_WITH_RESIDUAL_RISK
```

`WAIVED_WITH_RESIDUAL_RISK` is not permitted for a Constitutional invariant or a Critical requirement unless RFC-001 explicitly permits an exception process and the live scope is correspondingly reduced.

---

## 5. Evidence Strength Levels

### EV-L0 — Design Inspection

Static architecture and requirement review. Necessary but insufficient for runtime approval.

### EV-L1 — Model and Property Verification

State-machine exploration, model checking, property-based testing, and deterministic simulation.

### EV-L2 — Component Fault Test

A component is tested with controlled failure injection and authoritative state inspection.

### EV-L3 — Integrated System Fault Test

Multiple live-path components are tested together with real persistence, identity, and network boundaries.

### EV-L4 — Broker Sandbox or Certified Test Environment

Broker protocol is exercised outside production. Useful only where sandbox semantics are relevant.

### EV-L5 — Restricted Production Verification

Controlled production-scope tests with tightly bounded economic risk or no risk-increasing action, as approved by the Safety Profile.

### EV-L6 — Continuous Production Conformance

Runtime monitoring continuously detects drift from verified assumptions.

### Composite Evidence-Level Notation

The Evidence Register uses the following normative shorthand:

- `EV-Ln+X` requires the named EV-Ln evidence **and** the supplementary evidence or assessment `X`; `+X` never replaces or lowers EV-Ln. `+Broker` requires applicable Broker Capability Profile evidence at the broker level required by that profile and approval gate. `+Security` requires an independent security-boundary assessment covering identity, credential, authorization, fencing, and bypass paths.
- `EV-Ln/Lm` is staged scope, not a free choice between levels. EV-Ln is the earliest non-live evidence stage; EV-Lm is additionally required before accepting a scope that depends on the integrated, broker, restricted-production, or continuous semantics represented by EV-Lm. If the applicable ADR gate, Verification Profile, or Broker Capability Profile does not resolve the scope, the higher level applies for acceptance.
- Short forms such as `EV-L2/3` mean `EV-L2/EV-L3`. Combined forms such as `EV-L1/3+Broker` apply both rules: staged EV-L1/EV-L3 evidence plus the required broker evidence. Multiple suffixes are cumulative: `EV-L3/5+Broker+Security` requires the staged EV-L3/EV-L5 evidence, applicable broker evidence, and the independent security-boundary assessment.
- `Profile-dependent` SHALL be resolved to an exact minimum level by an approved Verification Profile and, where applicable, Broker Capability Profile before the item may become `READY`. Missing resolution is a blocker and SHALL NOT default to the lowest level.

Each acceptance criterion SHALL state the minimum evidence level. A lower level cannot substitute for a required higher level.

---

## 6. Verification Profile

Numeric bounds SHALL be stored in an approved Verification Profile rather than embedded as arbitrary values in the ADRs.

The profile SHALL define at least:

```text
B_authority_partition_detect
B_risk_increase_revoke
B_revocation_to_egress
B_halt_to_egress
B_human_halt_to_commit
B_time_health_to_egress
B_capability_claim_to_send
B_egress_hard_fence
B_stale_epoch_reject
B_external_activity_detect
B_external_activity_contain
B_startup_reconciliation
B_final_quantity_proof
B_late_fill_observation
B_protective_request_start
B_protective_request_complete
B_broker_query_consistency
B_rate_limit_recovery
B_failure_domain_detect
B_failure_domain_contain
B_protection_gap
B_protection_overlap
B_protective_replacement_contain
B_non_trade_event_detect
B_non_trade_transition_apply
B_non_trade_reconcile
B_operator_escalation
B_evidence_persist
B_evidence_gap_detect
B_evidence_gap_contain
B_recovery_trigger_to_barrier
B_recovery_barrier_to_egress
B_critical_input_loss_detect
B_critical_input_invalid_to_authority
B_critical_input_invalid_to_egress
B_venue_constraint_loss_detect
B_venue_constraint_invalid_to_authority
B_venue_constraint_invalid_to_egress
MAX_normal_capability_age
MAX_time_health_snapshot_age
MAX_degraded_lease_holdover
MAX_clock_drift
MAX_process_suspension
MAX_unresolved_send_per_scope
MAX_human_approval_age
MAX_human_session_age
MAX_human_delegation_age
MIN_evidence_retention
MAX_replay_start_delay
MAX_recovery_readiness_age
MAX_critical_input_snapshot_age
MAX_decision_context_age
MAX_venue_constraint_snapshot_age
MAX_order_admissibility_decision_age
```

For every bound, the profile SHALL include:

- owner;
- rationale;
- measurement source;
- percentile or hard maximum semantics;
- applicable broker/profile/scope;
- failure response;
- review date.

A placeholder or undocumented default is not an approved bound.

---

## 7. Required Evidence Artifacts

Every fault test SHALL retain, as applicable:

1. test manifest;
2. baseline manifest;
3. fault-injection timeline;
4. monotonic and wall-clock timeline;
5. raw input events;
6. Safety Authority epoch transitions;
7. capability issuance and rejection records;
8. Risk Capacity Ledger command and transition records;
9. Intent and transmission-attempt records;
10. Broker Adapter egress decisions;
11. raw broker requests and responses with secrets removed;
12. broker order, fill, position, balance, and margin evidence;
13. orthogonal state-dimension transitions and ownership decisions;
14. reconciliation evidence and confidence bounds;
15. failure-domain, topology, deployment, credential, and common-mode identity;
16. protective obligation, replacement workflow, gap, overlap, and proof evidence;
17. non-trade event versions, transition envelopes, corrections, and lineage;
18. Human Authority Policy and Effective Principal Graph generations;
19. approval request, attestation, set, consumption, delegation, and revocation records;
20. Human HALT, local latch, authoritative commit, egress receipt, and break-glass records;
21. Safety Evidence Envelopes, commit receipts, source continuity, and causal indexes;
22. integrity segments, external anchors, key/store generations, and gap records;
23. raw/normalized/redacted view lineage, access/export records, and Replay Capsules;
24. Recovery Barrier Policy, trigger, scope, Recovery Generation, and owner-epoch records;
25. Recovery Sessions, Inventory Cuts, obligations, Evidence Packages, Readiness Decisions, invalidations, and re-arm handoffs;
26. Critical Input Policies, source identities/continuities, observations, transformations, Snapshots, Decision Context Capsules, corrections, and invalidations;
27. proposal, approval, Intent, capacity, authorization, capability, proof, evidence-receipt, egress, and broker-request context bindings;
28. mode transitions;
29. metrics and alerts;
30. invariant-evaluation report;
31. final-state snapshot;
32. pass/fail decision;
33. reviewer identity and review result;
34. artifact digests and chain-of-custody record.

Redaction SHALL preserve fields needed to verify identity, ordering, quantity, and economic effect.

---

## 8. Evidence Package Structure

A recommended evidence package is:

```text
evidence/
  manifest.yaml
  baseline.yaml
  verification-profile.yaml
  evidence-integrity-policy.yaml
  traceability.csv
  broker-capability-profile.yaml
  runs/
    <evidence-id>/<run-id>/
      test-plan.yaml
      fault-timeline.jsonl
      system-events.jsonl
      ledger-transitions.jsonl
      authority-events.jsonl
      egress-decisions.jsonl
      state-dimensions/
      broker-raw/
      reconciliation/
      failure-domain/
      protective-replacement/
      non-trade-events/
      human-authority/
      evidence-integrity/
      critical-input-integrity/
      replay/
      chain-of-custody/
      metrics/
      final-state.json
      invariant-report.json
      result.yaml
      reviewer-signoff.yaml
  residual-risks/
  manifests/
    sha256sums.txt
```

Equivalent structures are permitted if they preserve all required properties.

---

## 9. Evidence Integrity

ADR-002-016 is normative for Safety Evidence Envelopes, pre-effect durability, commit receipts, source continuity, causal completeness, integrity anchoring, gap handling, retention, redaction, access, isolated replay, and recovery. This section adds run-package rules and does not create a separate or weaker evidence path.

### 9.1 Append-Only Run Record

After a run begins, its test identity, baseline, seed, and fault schedule SHALL be append-only.

### 9.2 Artifact Hashing

Every retained artifact SHALL have a cryptographic digest included in the evidence manifest.

### 9.3 Time Sources

Evidence SHALL record both wall-clock and monotonic sequencing where available. Wall clock alone cannot establish causal ordering.

### 9.4 Raw Before Derived

Raw broker and system evidence SHALL be retained before normalization. Derived states must identify their raw inputs.

### 9.5 Reviewer Sign-Off

A `PASS` for a Critical item is incomplete until independent review signs the evidence manifest.

---

## 10. Traceability Model

Every evidence item SHALL map to:

- RFC-000 principle;
- RFC-001 SAFE requirement;
- RFC-002 component and flow;
- ADR invariant;
- acceptance criterion;
- implementation component;
- test case;
- evidence package;
- residual risk, if any.

The traceability matrix SHALL support both directions:

```text
Requirement -> Evidence
Evidence -> Requirement
```

An untested Critical requirement blocks production approval.

---

# Part I — Aggregate Risk-Capacity Evidence

## 11. RC-EV-001 — Concurrent Commitment Serialization

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-001; INV-001, INV-003
- **Precondition:** Known available multi-dimensional headroom; two or more concurrent approved proposals compete for overlapping capacity.
- **Injection:** Synchronize commit commands to read the same apparent pre-state.
- **Expected:** Exactly one set of compatible atomic commitments succeeds; incompatible commit is rejected without partial mutation.
- **Fail:** Aggregate committed usage exceeds effective limit, duplicate headroom is consumed, or partial vector mutation occurs.
- **Evidence:** command IDs, CAS versions, ledger before/after, invariant report.

## 12. RC-EV-002 — Duplicate Active Ledger Writer

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-002; INV-008
- **Injection:** Run two writer instances with different epochs; pause and resume the old writer.
- **Expected:** Stale writer cannot commit, release, bind, or issue accepted transmission capability.
- **Fail:** Any stale mutation or egress acceptance occurs.

## 13. RC-EV-003 — Crash Before Send

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-003
- **Injection:** Crash after reservation/attempt binding but before `SEND_STARTED`, then at each durable boundary before external transmission.
- **Expected:** Release occurs only where non-transmission is durably proven; otherwise capacity remains bound.

## 14. RC-EV-004 — Crash After Send Boundary

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-004
- **Injection:** Crash immediately after `SEND_STARTED`, during socket write, and after broker acceptance before local response persistence.
- **Expected:** Attempt becomes potentially live; no blind retry; full capacity remains consumed.

## 15. RC-EV-005 — Acknowledgement Loss

- **Minimum Level:** EV-L3 plus broker-required level
- **Supports:** ADR-002-002 AC-005
- **Injection:** Drop acknowledgement after broker acceptance.
- **Expected:** UNKNOWN/potentially-live state, no release, no duplicate attempt unless proven idempotent.

## 16. RC-EV-006 — Partial Fill Transfer

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-006
- **Injection:** Deliver partial fills with varying fractions.
- **Expected:** Capacity transfers atomically from open-order usage to confirmed-position usage without double count or gap.

## 17. RC-EV-007 — Cancel Crossing Fill

- **Minimum Level:** EV-L3 plus broker-required level
- **Supports:** ADR-002-002 AC-007
- **Injection:** Race cancel acknowledgement and fill in every order.
- **Expected:** Fill is accepted; remaining quantity is not released until Final Quantity Proof.

## 18. RC-EV-008 — Replace Overlap

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-008
- **Injection:** Make old and new order simultaneously live; also test protection gap.
- **Expected:** Overlap capacity is reserved or the operation is denied; gap is represented as unprotected risk.

## 19. RC-EV-009 — Reservation Expiry

- **Minimum Level:** EV-L2
- **Supports:** ADR-002-002 AC-009; INV-005
- **Injection:** Expire authorization and reservation TTL after `SEND_STARTED`.
- **Expected:** Potential economic effect remains capacity-consuming.

## 20. RC-EV-010 — External Activity Quarantine

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-010
- **Injection:** Create manual or third-party broker activity.
- **Expected:** External exposure consumes quarantine capacity and blocks new risk within containment bound.

## 21. RC-EV-011 — Broker Query Omission

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-011
- **Injection:** Omit a live order from one or more query responses.
- **Expected:** No release based on absence; confidence becomes conservative/unknown.

## 22. RC-EV-012 — Protective Lease Partition

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-012; ADR-002-001
- **Injection:** Partition central authority while protective lease remains valid.
- **Expected:** Only exclusive pre-committed consumption occurs; no new aggregate commitment.

## 23. RC-EV-013 — Protective Lease Expiry

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-013
- **Injection:** Expire lease while an attempt may be live.
- **Expected:** No new consumption; prior potential effects remain bound.

## 24. RC-EV-014 — Trapped Exposure

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-014
- **Injection:** Suspend instrument, reject exits, or exhaust liquidity.
- **Expected:** Exposure remains fully capacity-consuming; planned exit does not discount it.

## 25. RC-EV-015 — Corporate Action Remap

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-015
- **Injection:** Change quantity, multiplier, or instrument identity without fill.
- **Expected:** Capacity remaps conservatively; live authority blocked until valuation completes.

## 26. RC-EV-016 — Hard Envelope Enforcement

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-016
- **Injection:** Supply validly signed but excessive, wrong-unit, wrong-account, and partially applied profiles.
- **Expected:** Commit and transmission are rejected fail-closed.

## 27. RC-EV-017 — Startup Recovery Barrier

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002 AC-017
- **Injection:** Restart with live orders, unknown attempts, stale ledger reads, and external activity.
- **Expected:** No live risk increase before authoritative reconciliation and epoch verification.

## 28. RC-EV-018 — Capacity Evidence Replay

- **Minimum Level:** EV-L2
- **Supports:** ADR-002-002 AC-018
- **Expected:** Replay reconstructs every capacity category and transition without optimistic overwrite.

---

# Part II — Safety Authority Evidence

## 29. SA-EV-001 — Duplicate Active Safety Authority

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-001
- **Injection:** Two authorities concurrently issue permissive capabilities.
- **Expected:** Only current epoch is accepted at all enforcement points.

## 30. SA-EV-002 — Stale Leader Resume

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-002
- **Injection:** Pause leader, fail over, advance epoch, resume old leader.
- **Expected:** Old leader cannot issue accepted capability, mutate capacity, or transmit.

## 31. SA-EV-003 — Partition After Normal Grant

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-003
- **Injection:** Partition currentness verification after issuance but before use.
- **Expected:** New normal risk is denied within `B_risk_increase_revoke`.

## 32. SA-EV-004 — Valid Degraded Protective Lease

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-004
- **Expected:** Only in-scope action within lease and committed capacity passes.

## 33. SA-EV-005 — Monotonic Lease Expiry

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-003 SA-AC-005
- **Injection:** Advance monotonic time, preserve misleading wall clock.
- **Expected:** Offline lease is rejected after usable holdover.

## 34. SA-EV-006 — Lease Owner Restart

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-006
- **Injection:** Restart process and host under active degraded lease.
- **Expected:** Prior holdover cannot authorize new action.

## 35. SA-EV-007 — Overlapping Lease Failover

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-007
- **Injection:** Attempt reassignment before hard fence/expiry fence.
- **Expected:** New lease issuance fails.

## 36. SA-EV-008 — Hard Fence

- **Minimum Level:** EV-L3 and broker-required level
- **Supports:** ADR-002-003 SA-AC-008
- **Expected:** Old identity cannot reach broker or mutate authoritative state.

## 37. SA-EV-009 — HALT Versus Permissive Capability

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-009
- **Injection:** Race halt with capability validation and egress.
- **Expected:** Defined safer-state precedence prevents later transmission.

## 38. SA-EV-010 — Re-arm Gate

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-010
- **Injection:** Restore services but omit each re-arm prerequisite in turn.
- **Expected:** Every incomplete attempt is denied; dual control is required.

## 39. SA-EV-011 — Time Discontinuity

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-011
- **Injection:** Wall-clock step, monotonic anomaly, long suspension, time-source loss.
- **Expected:** Permissive offline capability fails closed.

## 40. SA-EV-012 — Key Rotation and Revocation

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-012
- **Expected:** Revoked/unknown keys fail; rotation creates no overlapping permissive authority.

## 41. SA-EV-013 — Egress Bypass Test

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-003 SA-AC-013
- **Injection:** Attempt direct live order from strategy, research, operator UI, and stale worker identities.
- **Expected:** Network, credential, and authorization controls block all bypasses.

## 42. SA-EV-014 — Epoch Registry Failure

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-003 SA-AC-014
- **Expected:** No new permissive authority; existing exposure remains tracked.

## 43. SA-EV-015 — Authority Evidence Replay

- **Minimum Level:** EV-L2
- **Supports:** ADR-002-003 SA-AC-015
- **Expected:** Exact epoch, capability, fence, halt, and re-arm sequence is reconstructible.

---

# Part III — Broker Capability Evidence

## 44. BC-EV-001 — Broker Identity and Attribution

- **Minimum Level:** EV-L3 plus EV-L5 where live semantics are relied upon
- **Supports:** ADR-002-004 BC-AC-001
- **Expected:** Deterministic attribution is proven or containment fallback handles ambiguity.

## 45. BC-EV-002 — Lost Broker Acknowledgement

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004 BC-AC-002
- **Expected:** No blind retry; full reservation and reconciliation.

## 46. BC-EV-003 — Duplicate Submission

- **Minimum Level:** Evidence level required by claimed idempotency
- **Supports:** ADR-002-004 BC-AC-003
- **Expected:** Proven deduplication or adapter retry refusal.

## 47. BC-EV-004 — Fill Before Acknowledgement

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-004 BC-AC-004
- **Expected:** Order and capacity state accept legal event reordering.

## 48. BC-EV-005 — Duplicate and Out-of-Order Fills

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-004 BC-AC-005
- **Expected:** Cumulative quantity remains correct and idempotent.

## 49. BC-EV-006 — Query Omission

- **Minimum Level:** EV-L3 plus broker verification
- **Supports:** ADR-002-004 BC-AC-006
- **Expected:** Missing query result cannot release capacity.

## 50. BC-EV-007 — Cancel Crossing Fill

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004 BC-AC-007
- **Expected:** Final quantity proof remains correct.

## 51. BC-EV-008 — Late Fill and Correction

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004 BC-AC-008
- **Expected:** Within-bound event handled; beyond-bound event degrades profile and contains scope.

## 52. BC-EV-009 — Replace Semantics

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004 BC-AC-009
- **Expected:** Atomicity, overlap, or gap behavior matches profile.

## 53. BC-EV-010 — Reduce-Only or Exit Reversal

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004 BC-AC-010
- **Expected:** No reversal under position and pending-order races.

## 54. BC-EV-011 — External Activity Detection

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004 BC-AC-011
- **Expected:** Detection and containment remain within approved bounds.

## 55. BC-EV-012 — Polling Under Rate Pressure

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004 BC-AC-012
- **Expected:** Reconciliation meets bound or new risk is denied.

## 56. BC-EV-013 — Protective Request Under Saturation

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004 BC-AC-013
- **Expected:** Measured behavior matches declared guarantee level.

## 57. BC-EV-014 — Session Failure and Reconnect

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004 BC-AC-014
- **Expected:** No identity confusion or unsafe retry.

## 58. BC-EV-015 — Broker Credential Fencing

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-004 BC-AC-015
- **Expected:** Unauthorized/stale identity cannot transmit.

## 59. BC-EV-016 — Capability Drift

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-004 BC-AC-016
- **Expected:** Contradiction immediately degrades status and blocks affected action.

## 60. BC-EV-017 — Pagination and History Window

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004 BC-AC-017
- **Expected:** Complete evidence across boundaries or conservative unknown.

## 61. BC-EV-018 — Position and Margin Conflict

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-004 BC-AC-018
- **Expected:** Per-field conservative bounds; no optimistic truth selection.

## 62. BC-EV-019 — Corporate/Administrative Change

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-004 BC-AC-019
- **Expected:** Identity and quantity remap blocks live authority until verified.

## 63. BC-EV-020 — Environment Isolation

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-004 BC-AC-020
- **Expected:** Test credentials/routes cannot reach live ordering.

## 64. BC-EV-021 — Profile Version Enforcement

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-004 BC-AC-021
- **Expected:** Stale, expired, or mismatched profile is rejected.

## 65. BC-EV-022 — Broker Evidence Replay

- **Minimum Level:** EV-L2
- **Supports:** ADR-002-004 BC-AC-022
- **Expected:** Every broker decision and finality conclusion is reproducible.

---

# Part IV — Cross-System Safety Cases

## 66. X-EV-001 — End-to-End Normal Order

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002; ADR-002-013
- **Sequence:** context validation → proposal → approval → capacity commitment → capability → egress → fill → reconciliation → capacity transfer.
- **Expected:** (a) exactly one intent-identity chain links context-validation → proposal → approval → capacity-commitment → capability → egress → fill → reconciliation → capacity-transfer; (b) each stage's pre/post invariant holds; (c) capacity is transferred, not duplicated, at fill; (d) no orphaned or duplicate identity is produced.

## 67. X-EV-002 — Safety Authority Failover During Commit

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-001; ADR-002-003; ADR-002-009; ADR-002-014
- **Injection:** Advance Safety Authority epoch while a capacity commit and transmission binding are in progress.
- **Expected:** No stale capability can authorize transmission; committed capacity remains consistent.

## 68. X-EV-003 — Ledger Failover During Authority Partition

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-001; ADR-002-003; ADR-002-009; ADR-002-014; ADR-002-017
- **Injection:** Fail the Risk Capacity Ledger over while central authority is partitioned.
- **Expected:** No new normal commitment; protective consumption only under exclusive valid lease; no double consumption.

## 69. X-EV-004 — ACK Loss Plus External Manual Order

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-002; ADR-002-004; ADR-002-013; ADR-002-017; ADR-002-019
- **Injection:** Drop a broker acknowledgement and inject a concurrent external manual order on the same account.
- **Expected:** Ambiguity expands containment scope; no duplicate retry or optimistic attribution.

## 70. X-EV-005 — Protective Action Under Broker Saturation

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-001; ADR-002-004; ADR-002-011
- **Injection:** Drive the broker session and rate budget to saturation while a protective action is required.
- **Expected:** Actual latency and success match declared guarantee; otherwise system contains and records residual failure.

## 71. X-EV-006 — Cancel/Replace During Safety HALT

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-001; ADR-002-003; ADR-002-011; ADR-002-013; ADR-002-015
- **Injection:** Issue cancel and replace of risk-reducing protective orders while a Safety HALT is active.
- **Expected:** HALT blocks new risk but does not blindly remove risk-reducing protection; cancellation arbiter applies.

## 72. X-EV-007 — Restart With Live UNKNOWN Orders

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002; ADR-002-007; ADR-002-014; ADR-002-015; ADR-002-017
- **Injection:** Restart the system while live orders remain in UNKNOWN execution state.
- **Expected:** Startup barrier prevents re-arm; unknown capacity remains quarantined.

## 73. X-EV-008 — Clock Failure During Degraded Protection

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-001; ADR-002-003; ADR-002-008; ADR-002-018
- **Injection:** Fail trustworthy time while the system operates under degraded protection.
- **Expected:** Lease invalidates; prior attempts remain tracked; no new protective transmission.

## 74. X-EV-009 — Deployment Rollback Restores Stale Instance

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002; ADR-002-003; ADR-002-007; ADR-002-009; ADR-002-013; ADR-002-014; ADR-002-015; ADR-002-017
- **Injection:** Roll a deployment back so a stale build, epoch, and profile instance is restored and attempts to act.
- **Expected:** Old build/epoch/profile cannot mutate or transmit.

## 75. X-EV-010 — Corporate Action During Open Order

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-004; ADR-002-010; ADR-002-017
- **Injection:** Apply a corporate action that remaps instrument, multiplier, and position while an order is open.
- **Expected:** Order, position, multiplier, and capacity uncertainty causes containment until remapped.

## 76. X-EV-011 — Broker Capability Drift During Live Session

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-004; ADR-002-013
- **Injection:** Degrade the active Broker Capability Profile during a live session.
- **Expected:** Active profile degrades; egress rejects dependent actions; potentially-live effects remain conserved.

## 77. X-EV-012 — Recovery and Partial Re-arm

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-002; ADR-002-003; ADR-002-007; ADR-002-013; ADR-002-014; ADR-002-015; ADR-002-017; ADR-002-018; ADR-002-019
- **Injection:** Drive recovery and request partial re-arm of one narrow approved scope.
- **Expected:** Only approved narrow scope is re-armed with new epoch/capabilities; previous capabilities remain invalid.

---

# Part V — Trustworthy Time Evidence

## 78. TIME-EV-001 — Wall-Clock Rollback and Jump

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-008 TIME-AC-001
- **Injection:** Step wall time backward and forward across freshness, expiry, configuration, and session boundaries while monotonic time continues.
- **Expected:** Expired authority and stale evidence never become valid; affected assumptions fail closed and economic state is preserved.

## 79. TIME-EV-002 — Clock Freeze

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-008 TIME-AC-002
- **Injection:** Freeze the wall clock and separately stall or falsify progression observations while authority and evidence age.
- **Expected:** Progression failure makes affected time untrusted and blocks new risk before freshness or expiry can be extended.

## 80. TIME-EV-003 — Reference-Source Disagreement

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-008 TIME-AC-003
- **Injection:** Diverge independent references and repeat with nominally different sources sharing one common clock or network path.
- **Expected:** Common-mode sources are not counted as independent; uncertainty widens conservatively and permissive authority is denied outside the approved bound.

## 81. TIME-EV-004 — Monotonic Discontinuity

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-008 TIME-AC-004
- **Injection:** Reset, jump, or invalidate the monotonic source and resume a process holding a snapshot or protective lease.
- **Expected:** Local anchors, cached snapshots, and degraded leases are invalid for new transmission; potentially-live effects remain tracked.

## 82. TIME-EV-005 — Restart and Suspension

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-008 TIME-AC-005
- **Injection:** Restart the process and host, then suspend and resume on both sides of `MAX_process_suspension`.
- **Expected:** A new continuity identity is required; old holdover or receipt anchors cannot authorize a new action after restart or excessive/unknown suspension.

## 83. TIME-EV-006 — Holdover Boundary

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-008 TIME-AC-006
- **Injection:** Exercise the exact conservative lifetime boundary with drift, transport, suspension, and safety-margin terms at minimum, zero, and unknown values.
- **Expected:** Only the pre-issued exclusive protective scope is usable while remaining lifetime is positive; zero, negative, or unknown lifetime is denial.

## 84. TIME-EV-007 — Freshness and Ordering Ambiguity

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-008 TIME-AC-007
- **Injection:** Supply future, missing, delayed, duplicated, buffered, and reordered events with sequence gaps and overlapping uncertainty intervals.
- **Expected:** Evidence becomes `STALE`, `UNKNOWN`, or `CONFLICTED`; negative age is never clamped to optimistic freshness and unresolved order blocks dependent safety transitions.

## 85. TIME-EV-008 — Session-Boundary Uncertainty

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-008 TIME-AC-008
- **Injection:** Test timezone transitions, calendar/version disagreement, holidays, exceptional sessions, and uncertainty intervals crossing an open/close boundary.
- **Expected:** Session-dependent action is denied unless the session is positively open under the exact approved calendar, timezone, venue, and broker semantics.

## 86. TIME-EV-009 — Time Recovery Generation

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-008 TIME-AC-009
- **Injection:** Recover references after `UNTRUSTED` and `DEGRADED_HOLDOVER`, replay old snapshots and authorizations, and omit stabilization prerequisites in turn.
- **Expected:** Recovery creates a new generation only after complete stabilization; no old capability, profile, lease, or Live Authorization is revived and no automatic re-arm occurs.

## 87. TIME-EV-010 — Egress Time Currentness

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-008 TIME-AC-010
- **Injection:** Place the Trustworthy Time Service and egress on different hosts; delay or drop a less-trusted generation; exceed `MAX_time_health_snapshot_age`; restart the consumer; attempt direct issuer/consumer monotonic subtraction and egress bypass.
- **Expected:** Cross-host age uses the consumer receipt anchor plus conservative transport uncertainty; stale or unverifiable generation is denied and every egress reflects degradation within `B_time_health_to_egress`.

---

# Part VI — Live Authorization and Re-arm Evidence

## 88. REARM-EV-001 — Default Non-Live

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-007 REARM-AC-001
- **Injection:** Cold start, warm restart, failover, scaling, deployment, and rollback without an explicit current re-arm workflow.
- **Expected:** No live authority or risk-increasing route exists; prior credentials, service names, and deployment state cannot implicitly arm the replacement.

## 89. REARM-EV-002 — Complete Re-arm Gate

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-007 REARM-AC-002
- **Injection:** Execute the re-arm workflow while omitting or corrupting each prerequisite independently and in combinations.
- **Expected:** Every incomplete or unverifiable request is denied; a later step cannot compensate for an earlier failed gate.

## 90. REARM-EV-003 — Automatic Re-arm Prevention

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-007 REARM-AC-003
- **Injection:** Restore health, connectivity, time, reconciliation, leadership, configuration, and deployment success individually and concurrently.
- **Expected:** No event, timeout, callback, or mode transition creates Live Authorization or activates live scope without the complete human-governed workflow.

## 91. REARM-EV-004 — Fresh Authorization Identity

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-007 REARM-AC-004
- **Injection:** Replay denied, suspended, revoked, expired, superseded, stale-epoch, and prior-deployment authorizations and capabilities.
- **Expected:** Every replay is rejected; re-arm creates a new identity, approval binding, generation, epoch, and capability.

## 92. REARM-EV-005 — Human Dual Control

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-007 REARM-AC-005
- **Injection:** Use one principal, shared credentials, generic team identities, role aliases, and a principal who approved a limit increase to attempt re-arm.
- **Expected:** At least two distinct authenticated principals are required and prohibited role combinations cannot be bypassed through service or group identity.

## 93. REARM-EV-006 — Atomic Safety Configuration

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-007 REARM-AC-006
- **Injection:** Partially distribute a profile, mix versions, change units or scope, and roll back to a broader or incompatible version.
- **Expected:** No mixed or partial version becomes active; every authority-increasing interpretation requires the full approval and new-authorization path.

## 94. REARM-EV-007 — UNKNOWN and Conservative Capacity

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-007 REARM-AC-007
- **Injection:** Lose broker ACK, provide cancel ACK without Final Quantity Proof, create partial fills, omit query results, and add unattributed external activity.
- **Expected:** The affected state remains `UNKNOWN`, consumes conservative capacity, and blocks risk-increasing re-arm; no actor outside the Risk Capacity Ledger releases capacity.

## 95. REARM-EV-008 — Continuous Invalidation Bound

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-007 REARM-AC-008
- **Injection:** Invalidate time, reconciliation, authority, broker capability, profile, deployment identity, credential, or fencing while delaying revocation propagation and currentness refresh.
- **Expected:** An authoritative restrictive generation is created within `B_risk_increase_revoke`; every final egress denies new risk within the additional `B_revocation_to_egress`; the consumer-local capability/currentness proof age never exceeds `MAX_normal_capability_age`; session loss sets a deny latch that recovery alone cannot clear.

## 96. REARM-EV-009 — Partial Re-arm Scope

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-007 REARM-AC-009
- **Injection:** Authorize one narrow account/strategy/instrument/action scope, then attempt fallback, wildcard, inherited, and adjacent-scope actions.
- **Expected:** Only the exact narrow scope is active; broader previous and unresolved scopes remain non-live and every expansion requires a new authorization.

## 97. REARM-EV-010 — Final Egress Authorization Currentness

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-007 REARM-AC-010
- **Injection:** Present stale, wrong-scope, wrong-version, over-age, wrong-generation, wrong-deployment, reused-nonce, post-deny-latch, and bypassed authorization; pause currentness renewal; delay a restrictive push; crash or restart egress before claim, after durable claim/`SEND_STARTED`, and before the first broker byte; insert an unfenced queue or proxy; and attempt transmission through alternate broker clients, credentials, routes, and administrative paths.
- **Expected:** Only the credential-confined Egress Gateway can claim and transmit; the nonce is durable and single-use; the irreversible send begins within `B_capability_claim_to_send` against the same current generation vector; no upstream success, alternate client call, operational flag state, queue, cache, or alternate credential path permits transmission. Every post-claim ambiguity is `UNKNOWN`, remains potentially live and capacity-covered, and cannot reuse the capability.

## 98. REARM-EV-011 — HALT Restrictive Precedence

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-007 REARM-AC-011
- **Injection:** Race accepted HALT against validation, queueing, proxy handoff, and the irreversible broker-send boundary on both sides of the ordering point.
- **Expected:** Every egress accepts HALT within `B_halt_to_egress`; at each egress, a send ordered after local HALT acceptance is denied, a propagation-window or proven-earlier send remains potentially live and capacity-covered, and ambiguous local ordering fails closed without blindly cancelling required protection.

## 99. REARM-EV-012 — Authorization Evidence Replay

- **Minimum Level:** EV-L2
- **Supports:** ADR-002-007 REARM-AC-012
- **Expected:** Independent replay reconstructs profile changes, readiness, human approvals, authorization issuance, generations, invalidations, egress decisions, partial scopes, and denials without treating replay as prevention.

---

# Part VII — Orthogonal Trading State Evidence

## 100. STATE-EV-001 — Orthogonal Composite Persistence

- **Minimum Level:** EV-L1/EV-L2
- **Supports:** ADR-002-005 AC-005-1
- **Injection:** Generate every valid composite in ADR-002-005 §14 plus boundary combinations where one dimension changes while the other four remain unchanged; persist, reload, and replay each state.
- **Expected:** Every valid composite remains representable and durable; no dimension is silently derived from another except through an explicit CPL invariant and owned transition.

## 101. STATE-EV-002 — Conservative Direction

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-005 AC-005-2
- **Injection:** Apply timeout, ACK loss, query omission, cache miss, process restart, authority expiry, and operator assertion at every non-terminal state.
- **Expected:** No dimension moves to a less-conservative value; UNKNOWN remains capacity-consuming and no missing evidence proves rejection, cancellation, non-fill, or release.

## 102. STATE-EV-003 — Cross-Dimension Coupling

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-005 AC-005-3
- **Injection:** Explore partial fill, cancel-crossing-fill, late fill, replacement overlap, broker UNKNOWN, knowledge conflict, and trapped exposure in every relevant ordering.
- **Expected:** CPL-1 through CPL-7 always hold; the Risk Capacity Ledger alone performs capacity transitions and any violated coupling causes immediate new-risk containment.

## 103. STATE-EV-004 — Conservative Restart Reconstruction

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-005 AC-005-4
- **Injection:** Crash at each attempt and broker-order boundary, including after durable `SEND_STARTED`, after network transmission, and before evidence persistence; then restart with incomplete stores and stale caches.
- **Expected:** Potentially live attempts and non-terminal orders reconstruct as `POTENTIALLY_LIVE` or `UNKNOWN`; Knowledge is re-derived and never defaults to `RECONCILED`.

## 104. STATE-EV-005 — Dimension Transition Ownership

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-005 AC-005-5
- **Injection:** Have every non-owner identity attempt direct and indirect mutation of Intent, Attempt, Broker Order, Knowledge, and Capacity dimensions, including replay and stale-writer paths.
- **Expected:** Every unauthorized mutation is rejected and evidenced; cross-dimension effects occur only through the defined owning authority and stale epochs remain fenced.

---

# Part VIII — Evidence and Reconciliation Confidence Evidence

## 105. RECON-EV-001 — Single Evidence-Path Corruption

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-006 AC-006-1
- **Injection:** Corrupt each evidence path independently and then corrupt nominally different paths sharing one parser, source, clock, or transport dependency.
- **Expected:** A single or common-mode-corrupted path cannot establish `CORROBORATED` or `RECONCILED`; affected fields use conservative bounds and block new risk.

## 106. RECON-EV-002 — Query Omission and Negative Evidence

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-006 AC-006-2
- **Injection:** Hide a live order from one page, query, session, and stream, then reveal it through a later query or fill while pagination and history windows vary.
- **Expected:** Absence never proves non-existence or terminal quantity, capacity is not released, and the reappearing order is reconciled without discarding its economic effect.

## 107. RECON-EV-003 — Conflicting Fill Quantity

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-006 AC-006-3
- **Injection:** Provide divergent cumulative fill, remaining quantity, position, and correction evidence from independent paths in multiple arrival orders.
- **Expected:** Each conflicting field remains at its adverse conservative bound, Capacity becomes `QUARANTINED_UNKNOWN`, and no blended score or preferred source authorizes new risk.

## 108. RECON-EV-004 — Freshness and Time-Confidence Loss

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-006 AC-006-4
- **Injection:** Age each field across its approved freshness horizon, lose trustworthy time, restart the receipt-anchor owner, and restore time with a new generation.
- **Expected:** Aged or time-unverifiable fields become `STALE` or `UNKNOWN`, block dependent new risk, and do not become current merely because time service recovers.

## 109. RECON-EV-005 — Field-Specific Capacity Release Proof

- **Minimum Level:** EV-L3 plus broker evidence
- **Supports:** ADR-002-006 AC-006-5
- **Injection:** Offer cancel ACK, terminal status without quantity, single-source query, late correction, and finally complete broker-profile-specific Final Quantity Proof.
- **Expected:** Only the complete field-specific proof permits the Risk Capacity Ledger to release the corresponding capacity; all weaker evidence preserves conservative commitment.

---

# Part IX — Failure-Domain Isolation Evidence

## 110. FD-EV-001 — Strategy-to-Safety Isolation

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-009 FD-AC-001
- **Injection:** Crash and compromise strategy, orchestration, UI, and ordinary operator identities; attempt authority grant, capacity mutation, epoch change, and direct broker transmission.
- **Expected:** The failure cannot grant safety authority, mutate capacity, or bypass final egress; availability may fall but new risk remains denied.

## 111. FD-EV-002 — Stale Deployment and Duplicate Active Generation

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-009 FD-AC-002
- **Injection:** Run old and new deployments concurrently with network and broker reachability; delay cooperative shutdown and replay old credentials, epochs, profiles, and capabilities.
- **Expected:** Only one current writer and authorized egress generation can mutate or transmit; every stale generation is hard-fenced.

## 112. FD-EV-003 — Control-Plane-to-Egress Partition

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-009 FD-AC-003
- **Injection:** Partition Safety Control Plane, Risk Capacity Ledger, revocation, and time-currentness paths from egress while leaving broker connectivity available.
- **Expected:** The egress currentness session expires or becomes unverifiable, sets the monotonic deny latch, and blocks new risk within approved containment bounds while broker reachability remains available; reconnect alone does not re-arm. Potentially transmitted effects remain tracked and capacity-covered.

## 113. FD-EV-004 — Cache Failure Cannot Create Permission

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-009 FD-AC-004
- **Injection:** Evict, expire, corrupt, restart, and partition caches and serve stale replica values for authority, epoch, capacity, quantity, and proof state.
- **Expected:** Cache failure or miss cannot grant permission, establish Final Quantity Proof, or release capacity; the affected scope fails closed.

## 114. FD-EV-005 — Restrictive Event Distribution Failure

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-009 FD-AC-005
- **Injection:** Delay, lose, duplicate, reorder, and replay HALT, revocation, time-degradation, capability-withdrawal, and epoch events across every egress consumer.
- **Expected:** No egress accepts an older permissive generation after the applicable bound; the authenticated currentness-session expiry independently denies when restrictive delivery fails; unverifiable currentness is denial, recovery alone does not clear the latch, and unsafe event delivery is not treated as authority.

## 115. FD-EV-006 — Live and Non-Live Environment Isolation

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-009 FD-AC-006
- **Injection:** Cross-use non-live workload identities, secrets, routes, account identifiers, configurations, and broker sessions against live egress and accounts.
- **Expected:** Every cross-environment attempt is prevented at identity, route, allowlist, credential, or final egress boundaries and produces no live economic effect.

## 116. FD-EV-007 — Risk Capacity Ledger Failover Fence

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-009 FD-AC-007
- **Injection:** Partition the active writer, promote a replacement, resume the stale writer, restore an old snapshot, and deliver delayed mutation commands.
- **Expected:** Stale writers cannot mutate, conservative commitments survive or reconstruct, and UNKNOWN state is never released by failover.

## 117. FD-EV-008 — Shared Time Common Mode

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-009 FD-AC-008
- **Injection:** Corrupt a clock, synchronization daemon, upstream reference, hypervisor, or network path shared by authority issuer and multiple egress checkers.
- **Expected:** The dependency is classified as common-mode; affected authority reduces at all egress paths and recovered time does not revive old authorization.

## 118. FD-EV-009 — Partial Deployment and Configuration Rollback

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-009 FD-AC-009
- **Injection:** Distribute mixed binaries, schemas, risk libraries, parsers, and profiles; fail mid-deployment and roll back while old instances remain reachable.
- **Expected:** Mixed or partial generations default to denied transmission, stale instances are fenced, and any resumed scope requires a new Live Authorization.

## 119. FD-EV-010 — Shared Broker Resource Exhaustion

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-009 FD-AC-010
- **Injection:** Exhaust broker session, account, open-order, submission, cancellation, query, and rate-limit resources with ordinary and protective traffic.
- **Expected:** The declared common mode is observed; priority is never reported as reserved capacity and the system restricts or contains before making an unsupported protective guarantee.

## 120. FD-EV-011 — Safety-Cell Blast-Radius Containment

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-009 FD-AC-011
- **Injection:** Fail each cell-local dependency and then each dependency shared across cells, including account, session, credential, egress, and ledger resources.
- **Expected:** Effects remain within the declared aggregate blast radius or authoritative containment escalates to the broader scope without distributing capacity beyond aggregate limits.

## 121. FD-EV-012 — Region and Datastore Recovery

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-009 FD-AC-012
- **Injection:** Recover after region loss, datastore rollback, credential compromise, and unreachable old instances; replay prior authority and clear local runtime state.
- **Expected:** New generations fence prior identities, UNKNOWN economic state and capacity survive, reconciliation precedes authority, and no automatic re-arm occurs.

---

# Part X — Protective Replacement Evidence

## 122. PR-EV-001 — Overlap-First Replacement

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-011 PR-AC-001
- **Injection:** Exercise simultaneous old/new fills, partial fills, delayed acknowledgements, and adverse price movement across overlap-first replacement.
- **Expected:** Capacity covers the maximum simultaneous effect, required protection remains sufficient, and over-close or reversal cannot exceed the hard envelope.

## 123. PR-EV-002 — Cancel-First Admission Gate

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-011 PR-AC-002
- **Injection:** Omit or corrupt each gap, capacity, time, capability, broker-resource, authority, and containment prerequisite individually and in combinations.
- **Expected:** Cancel-first replacement is denied unless every prerequisite is current and proven; UNKNOWN never substitutes for permission.

## 124. PR-EV-003 — Missing ACK Replacement Ambiguity

- **Minimum Level:** EV-L3 plus broker evidence
- **Supports:** ADR-002-011 PR-AC-003
- **Injection:** Drop old-cancel and new-submit responses after broker acceptance and attempt retry with the same and different client identifiers.
- **Expected:** Acceptance remains UNKNOWN, all credible old/new effects remain capacity-covered, and no unsafe duplicate action is transmitted.

## 125. PR-EV-004 — Cancel ACK Is Not Final Quantity Proof

- **Minimum Level:** EV-L3 plus broker evidence
- **Supports:** ADR-002-011 PR-AC-004
- **Injection:** Return cancel ACK followed by late fill, correction, query omission, and session reconnect before complete terminal-quantity evidence.
- **Expected:** Old-order capacity and executable possibility remain until Final Quantity Proof; cancel ACK alone never completes replacement.

## 126. PR-EV-005 — Partial-Fill Interleavings

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-011 PR-AC-005
- **Injection:** Enumerate old fill, new fill, cancel, ACK, position update, and exposure-change orderings at zero, partial, and full quantities.
- **Expected:** Every fill recomputes obligation, overlap/gap risk, capacity, cancellation, and egress conformance atomically and conservatively.

## 127. PR-EV-006 — New Protection Sufficiency Proof

- **Minimum Level:** EV-L3 plus broker evidence
- **Supports:** ADR-002-011 PR-AC-006
- **Injection:** Provide broker ACK while varying wrong quantity, side, instrument, trigger, session, leaves quantity, stale evidence, and contradicted exposure.
- **Expected:** ACK alone never establishes sufficient protection; every required field, profile, freshness, and exposure relation must pass.

## 128. PR-EV-007 — Protective Broker-Resource Exhaustion

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-011 PR-AC-007
- **Injection:** Exhaust broker session, rate, order-count, cancel, query, and shared route capacity immediately before and during replacement.
- **Expected:** Existing protection is not blindly removed, unsupported reservation is not claimed, new risk is blocked, and containment follows the authorized fallback.

## 129. PR-EV-008 — Replacement Authority Expiry

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-011 PR-AC-008
- **Injection:** Expire or revoke replacement authority before first leg, between legs, after broker transmission, and while final proof is pending.
- **Expected:** New transmission stops, but old/new economic effects and capacity remain until proven; expiry never completes or erases the workflow.

## 130. PR-EV-009 — Replacement Crash and Failover

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-011 PR-AC-009
- **Injection:** Crash and fail over the workflow owner and Risk Capacity Ledger writer at every durable boundary while resuming stale instances.
- **Expected:** Commitments and lineage recover, stale writers are fenced, both orders reconcile before action, and any continuation uses new authority.

## 131. PR-EV-010 — Replacement Partition

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-011 PR-AC-010
- **Injection:** Partition control plane, ledger, reconciliation, egress, and broker paths independently during each replacement mode.
- **Expected:** New risk is blocked, gap/overlap capacity remains conservative, potentially live orders remain represented, and only authorized containment may proceed.

## 132. PR-EV-011 — HALT and Replacement Precedence

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-011 PR-AC-011
- **Injection:** Race HALT with replacement planning, cancellation authorization, both transmissions, and broker evidence; include an existing order still required for protection.
- **Expected:** HALT blocks ordinary initiation, only newly authorized HALT-compatible containment may proceed, and necessary existing protection is not blindly cancelled.

## 133. PR-EV-012 — Broker-Proven Atomic Replace Scope

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-011 PR-AC-012
- **Injection:** Exercise each claimed atomic replace across order type, venue, session, partial-fill state, response loss, reconnect, and broker failure; then use the claim outside its profile scope.
- **Expected:** Atomic treatment is allowed only where exact semantics are evidenced; every unsupported or drifted scope falls back to conservative non-atomic handling.

---

# Part XI — Corporate Actions and Non-Trade Evidence

## 134. NT-EV-001 — Split and Reverse-Split Transition

- **Minimum Level:** EV-L1/EV-L3 plus broker evidence
- **Supports:** ADR-002-010 NT-AC-001
- **Injection:** Apply split and reverse-split ratios with fractional entitlement, broker rounding, cash-in-lieu, open orders, protection, and partial broker application.
- **Expected:** Quantity, price, multiplier, order, protection, and capacity use the conservative transition envelope until field-level reconciliation completes.

## 135. NT-EV-002 — Multi-Leg Merger and Spin-Off

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-010 NT-AC-002
- **Injection:** Transform one instrument into multiple instruments and cash legs with delayed, partial, corrected, and source-conflicted delivery.
- **Expected:** Capacity covers every credible old/new leg without favorable unknown netting and no leg disappears before proof.

## 136. NT-EV-003 — Instrument Identity Change

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-010 NT-AC-003
- **Injection:** Change symbol, identifier, venue, contract, multiplier, and listing while old orders, intents, and market data remain active.
- **Expected:** Stable lineage is preserved, existing intent is not silently redirected, and any new or replacement transmission requires current authority and egress validation.

## 137. NT-EV-004 — Option Exercise and Assignment

- **Minimum Level:** EV-L3 plus broker evidence
- **Supports:** ADR-002-010 NT-AC-004
- **Injection:** Delay or omit exercise/assignment notice, apply partial assignment, and vary cash, underlying, collateral, and settlement results around expiry.
- **Expected:** Every credible resulting exposure consumes prior capacity; absence of notice never proves no assignment and unsupported scope blocks new risk before the boundary.

## 138. NT-EV-005 — Futures Expiry and Settlement

- **Minimum Level:** EV-L3 plus broker evidence
- **Supports:** ADR-002-010 NT-AC-005
- **Injection:** Exercise cash settlement, physical delivery, delayed settlement, contract conversion, suspension, and inability to trade after expiry.
- **Expected:** Trading end never implies zero risk; delivery, settlement, trapped exposure, and capacity remain represented until reconciled.

## 139. NT-EV-006 — Broker Open-Order Adjustment

- **Minimum Level:** EV-L3/EV-L5
- **Supports:** ADR-002-010 NT-AC-006
- **Injection:** Have the broker resize, reprice, remap, cancel, duplicate, or recreate open and protective orders across an event, with delayed and missing reports.
- **Expected:** Potentially live old/new orders remain capacity-covered until field-level reconciliation and Final Quantity Proof; broker adjustment is never assumed.

## 140. NT-EV-007 — Conflicting Effective-Time Window

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-010 NT-AC-007
- **Injection:** Disagree announcement, ex, effective, expiry, payable, and settlement times across independent sources while clock and calendar generations change.
- **Expected:** New risk is blocked from the earliest credible boundary through the latest credible completion; recovered time or later data does not retroactively authorize action.

## 141. NT-EV-008 — Unattributed Correction and Transfer

- **Minimum Level:** EV-L3 plus broker evidence
- **Supports:** ADR-002-010 NT-AC-008
- **Injection:** Apply broker correction, transfer, journal, fee, tax, cash, collateral, and unexplained position changes with incomplete or conflicting provenance.
- **Expected:** Unattributed state remains UNKNOWN and capacity-consuming, blocks new risk, and cannot be relabeled merely to make reconciliation pass.

## 142. NT-EV-009 — Non-Permissive Partial Local Application

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-010 NT-AC-009
- **Injection:** Fail between instrument, projection, capacity, protection, authority, and audit updates in every ordering and restart from each partial state.
- **Expected:** Consumers use the conservative transition envelope; no partial state exposes more capacity, protection, or authority than the complete safe transition.

## 143. NT-EV-010 — Correction and Reversal Idempotency

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-010 NT-AC-010
- **Injection:** Duplicate, reorder, correct, reverse, replay, and supersede event versions while retaining the same and conflicting source identifiers.
- **Expected:** Each economic effect applies exactly once, history remains immutable, and correction uses new lineage rather than destructive overwrite.

## 144. NT-EV-011 — Non-Trade Restart and Replay

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-010 NT-AC-011
- **Injection:** Restart during pending, applied-local, conflicted, correction, and reconciliation states; replay with stale writers and missing external connectivity.
- **Expected:** Pending events, transition envelopes, RCL commitments, UNKNOWN state, and lineage survive; stale writers are fenced and replay does not prove broker truth.

## 145. NT-EV-012 — Event Completion Cannot Re-arm

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-010 NT-AC-012
- **Injection:** Mark events complete, restore feeds and time, reconcile broker state, restart services, and replay prior Live Authorization and capabilities.
- **Expected:** No completion or recovery event automatically re-arms or revives old authorization; a fresh governed re-arm workflow is required.

---

# Part XII — RCL Persistence, Consensus, and Writer-Fencing Evidence

## 146. RCLP-EV-001 — Quorum-Serialized Concurrent Commitment

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-012 RCLP-AC-001
- **Injection:** Submit concurrent capacity requests that individually fit but jointly exceed one or more shared constraints while changing proposal order, leader, voter delay, and retry timing.
- **Expected:** One committed total order preserves every aggregate invariant; at most the admissible subset commits and no unit of headroom is double-spent.

## 147. RCLP-EV-002 — Minority Leader With Broker Reachability

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-012 RCLP-AC-002
- **Injection:** Partition the former leader with fewer than quorum voters while preserving its keys, process state, stale reads, clients, and broker-network reachability.
- **Expected:** It cannot commit, mutate RCL state, authorize or claim capability, produce accepted Commit Proof, or cause broker transmission.

## 148. RCLP-EV-003 — Stale Writer Resume

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-012 RCLP-AC-003
- **Injection:** Pause a writer, elect and activate a newer Writer Epoch, then resume the old writer with delayed commands, capabilities, sessions, and administrative credentials.
- **Expected:** Consensus, RCL, Currentness Sequencer, and egress reject every stale generation without relying on voluntary shutdown.

## 149. RCLP-EV-004 — Quorum Loss Preserves Capacity

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-012 RCLP-AC-004
- **Injection:** Remove quorum during committed reservations, potentially-live sends, UNKNOWN orders, trapped exposure, protective pools, and release-pending proof while other dependencies remain reachable.
- **Expected:** Normal mutation, capability authorization, claim, release, and send stop; every existing economic effect remains conservatively capacity-covered and quorum recovery does not auto-re-arm.

## 150. RCLP-EV-005 — Commit Response Loss and Crash Idempotency

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-012 RCLP-AC-005
- **Injection:** Drop responses and crash leader/client before proposal, after follower persistence, after quorum commit, after state-machine application, and before client receipt; retry identical and conflicting command identities.
- **Expected:** Uncommitted commands grant nothing; committed commands survive exactly once; identical retry returns the stable result and conflicting duplicate content is rejected.

## 151. RCLP-EV-006 — Capacity-to-Capability Commit Ordering

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-012 RCLP-AC-006
- **Injection:** Attempt capability authorization against uncommitted, stale-revision, released, wrong-domain, wrong-epoch, wrong-profile, and insufficient capacity while racing revocation and quarantine.
- **Expected:** Only an authorization ordered after the exact active capacity revision and current generation vector commits; a signature without that committed reference grants nothing.

## 152. RCLP-EV-007 — Quorum-Committed Claim and Send Boundary

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-012 RCLP-AC-007
- **Injection:** Reuse nonce, race HALT/revocation, lose quorum, exceed `B_capability_claim_to_send`, and crash before claim, after committed claim/`SEND_STARTED`, before first broker byte, and after an ambiguous send.
- **Expected:** Claim commits exactly once before send; a stale or uncommitted claim cannot transmit; post-claim ambiguity remains `UNKNOWN`, potentially live, and capacity-covered with no blind retry.

## 153. RCLP-EV-008 — Stale Read Cannot Create Permission

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-012 RCLP-AC-008
- **Injection:** Serve follower, cache, snapshot, projection, and pre-failover reads that omit reservations, epochs, claims, UNKNOWN, or restrictions; use them for release, authorization, and egress validation attempts.
- **Expected:** Every permissive consumer requires a linearizable committed-prefix proof; stale reads remain display-only and cannot reduce capacity or create authority.

## 154. RCLP-EV-009 — Joint Membership and Removed-Voter Fence

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-012 RCLP-AC-009
- **Injection:** Add, remove, replace, partition, pause, and resume voters during joint configuration; attempt simultaneous replacement and removed-voter proof issuance.
- **Expected:** One authoritative committed history persists, required configuration overlap is proven, uncaught-up nodes do not vote, and removed voters cannot commit or support currentness.

## 155. RCLP-EV-010 — Snapshot, Compaction, and Restore Integrity

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-012 RCLP-AC-010
- **Injection:** Omit or corrupt idempotency keys, capability-use records, non-terminal allocations, generations, tombstones, and log segments; restore older and mixed-generation material.
- **Expected:** Incomplete material is rejected; valid restore advances Restore Generation, remains non-live, preserves conservative economic state, fences prior authority, and detects rollback.

## 156. RCLP-EV-011 — Protective Sub-Ledger Rejoin

- **Minimum Level:** EV-L3
- **Supports:** ADR-002-012 RCLP-AC-011
- **Injection:** Partition after lease issuance, consume locally, lose ACK, restart owners, attempt overlapping lease use, expire authority, and rejoin with delayed or conflicting local and broker evidence.
- **Expected:** Parent capacity is never enlarged, recycled, or reassigned from expiry; overlap is rejected and rejoin uses explicit conservative reconciliation rather than last-write-wins merge.

## 157. RCLP-EV-012 — Disaster Recovery and Conflicting History

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-012 RCLP-AC-012
- **Injection:** Lose the normal quorum, present divergent voter/snapshot/backup histories, keep the former cluster's status uncertain, and attempt forced promotion, old capability replay, and automatic re-arm.
- **Expected:** Recovery remains non-live, fences the former authority, covers the worst credible economic union, advances cluster/restore/writer generations, and requires reconciliation plus explicit governed re-arm.

---

# Part XIII — Egress Credential, Route, and Commit-Proof Security Evidence

## 158. EGRESS-EV-001 — Credential and Route Authority Inventory

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-001
- **Injection:** Inventory and probe live keys, tokens, certificates, sessions, signers, portals, support paths, proxies, routes, service identities, secret-delivery identities, and recovery credentials across every environment and account.
- **Expected:** Every broker-order authority and route is attributed; no identity outside the declared final boundary can combine usable live-order authority with an accepted order route; unknown inventory blocks live scope.

## 159. EGRESS-EV-002 — Direct and Stale-Principal Bypass

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-002
- **Injection:** Attempt broker mutations from strategy, orchestration, stale and removed egress instances, administrators, recovery jobs, market-data, test, and research identities through direct, legacy, alternate, proxy, and borrowed-session paths.
- **Expected:** Every attempt is denied before broker acceptance, records evidence for **every** attempt, and triggers containment for **any** attempt that reaches a usable live path (a reachable live credential, session, signer, or route), and cannot borrow the current gateway's signer, session, credential, or route.

## 160. EGRESS-EV-003 — Environment, Scope, Endpoint, and Route Substitution

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-003
- **Injection:** Substitute live/non-live environment, account, instrument, endpoint, host, redirect, API version, method, action, credential, session, route, proxy, and trust root while preserving otherwise valid capability fields.
- **Expected:** Exact binding fails closed; no cross-environment or out-of-scope request reaches broker acceptance and profile contradiction contains the affected scope.

## 161. EGRESS-EV-004 — Quorum Commit Certificate Validation

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-004
- **Injection:** Present leader-only receipts, local journals, minority signer sets, invalid quorum rules, stale or removed signers, wrong membership, old cluster/Restore/Writer generations, rollback trust bundles, malformed encodings, and mismatched state digests.
- **Expected:** Only a canonical certificate proving quorum acceptance for the current committed claim validates; every weaker, stale, ambiguous, or mismatched proof is denied.

## 162. EGRESS-EV-005 — Proof, Capability, and Request Replay or Substitution

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-005
- **Injection:** Replay and transplant valid certificates and capabilities across principals, requests, accounts, endpoints, sessions, generations, credentials, and altered request bytes; reuse claimed nonces concurrently and after restart.
- **Expected:** Exact identity/digest binding and single-use claim prevent every reuse or transplant; ambiguous attempts remain potentially live and capacity-covered without blind retry.

## 163. EGRESS-EV-006 — Downstream Intermediary and Reconnect Boundary

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-006
- **Injection:** Delay, duplicate, mutate, queue, replay, reconnect, re-route, and retry after claim through proxies, sidecars, TLS terminators, signers, connection pools, session managers, and durable queues; exceed `B_capability_claim_to_send`.
- **Expected:** An intermediary either cannot create independent broker effect or enforces the complete final gate; no queued or reconnected request outlives current generations or the claim-to-send bound.

## 164. EGRESS-EV-007 — Restrictive Race at Actual Send Boundary

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-007
- **Injection:** Race HALT, revocation, time-health restriction, writer/authority/Egress Generation change, currentness loss, deny-latch set, and route/profile contradiction before claim, after claim, and before the first broker byte.
- **Expected:** Restrictive state dominates within every approved bound; unprovable ordering denies send and preserves conservative potentially-live capacity.

## 165. EGRESS-EV-008 — Deny-First Credential and Trust Rotation

- **Minimum Level:** EV-L3/EV-L5 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-008
- **Injection:** Rotate credential, session, signer, trust bundle, route, endpoint policy, and principal while delaying broker revocation and keeping old instances alive and network-reachable.
- **Expected:** New live authority remains denied until old credential, session, signer, and route are hard-fenced; no unfenced old/new overlap or rollback trust path exists.

## 166. EGRESS-EV-009 — Failover, Rollback, and Removed-Principal Resume

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-009
- **Injection:** Fail over through a shared service name, roll back deployment, resume paused and removed principals, restore shared volumes/sessions, and make the predecessor unreachable but not provably fenced.
- **Expected:** Standby and replacement principals remain non-live until exact committed identity, reconciliation, and predecessor hard-fence proof exist; recovery never revives prior authority.

## 167. EGRESS-EV-010 — Credential Compromise and Unknown Revocation

- **Minimum Level:** EV-L3/EV-L5 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-010
- **Injection:** Exfiltrate or suspect a live credential/session/signing path, make revocation response ambiguous, submit external mutations, and attempt new capability issuance, route restoration, or re-arm during containment.
- **Expected:** Bounded HALT and fencing occur, old path remains potentially active until disproven, all economic effects remain capacity-covered, external activity is reconciled, and only a fresh governed re-arm may restore scope.

## 168. EGRESS-EV-011 — Degraded Protective Egress Exclusivity

- **Minimum Level:** EV-L3/EV-L5 plus broker and security evidence
- **Supports:** ADR-002-013 EGRESS-AC-011
- **Injection:** Partition after protective lease issuance, exhaust or lose local sub-ledger evidence, restart owner, attempt normal-risk use, recycle timeout/UNKNOWN consumption, and reassign the credential or principal without hard fencing.
- **Expected:** Only exact lease-bound protective actions consume the finite local budget; normal risk, replenishment, overlap, and unfenced reassignment are denied.

## 169. EGRESS-EV-012 — Manual Authority and Recovery Cannot Re-arm

- **Minimum Level:** EV-L3/EV-L5 plus security assessment
- **Supports:** ADR-002-013 EGRESS-AC-012
- **Injection:** Use broker portal, support/manual channel, route recovery, credential recovery, secret refresh, reconnect, deployment health, and evidence replay to claim compliant egress or restore prior live authority.
- **Expected:** Manual activity remains external and conservatively reconciled; recovery signals cannot clear deny state, satisfy hard fencing, or re-arm without a complete fresh workflow.

---

# Part XIV — Safety Profile Governance Evidence

## 170. SPG-EV-001 — Envelope Governance and Non-Silent Expansion

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-014 SPG-AC-001
- **Injection:** Expand, tighten, replace, revoke, and make unavailable the Hard Safety Envelope while profiles and Live Authorizations remain staged or active; attempt implicit inheritance, unchanged-profile continuation, and automatic re-arm.
- **Expected:** Every envelope generation change suspends dependent permissive authority; expansion grants nothing automatically, tightening dominates future risk, existing economic state remains covered, and only a fresh validated generation plus governed re-arm can restore scope.

## 171. SPG-EV-002 — Semantic Units, Numeric, and Cross-Field Validation

- **Minimum Level:** EV-L1/EV-L2
- **Supports:** ADR-002-014 SPG-AC-002
- **Injection:** Mutate units, currency, multiplier, sign, precision, rounding, boundary inclusion, overflow, underflow, NaN, infinity, vector dimension, aggregate formula, and cross-field constraints across otherwise valid artifacts.
- **Expected:** Every unsafe or incomparable semantic mutation is rejected deterministically before activation; no parser or consumer interpretation grants a more permissive result.

## 172. SPG-EV-003 — Schema, Omission, and Canonicalization Safety

- **Minimum Level:** EV-L1/EV-L2 plus security assessment
- **Supports:** ADR-002-014 SPG-AC-003
- **Injection:** Omit Critical fields; add unknown, duplicate, deprecated, extension, aliased, reordered, Unicode-variant, floating-reference, inherited, executable-include, and schema-downgrade content; vary parsers and canonicalization versions.
- **Expected:** Canonical semantic digests agree only for identical meaning; ambiguous, unresolved, omitted, unknown, incompatible, or parser-dependent content grants zero new-risk authority.

## 173. SPG-EV-004 — Atomic Mixed-Generation Activation

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-014 SPG-AC-004
- **Injection:** Delay, drop, reorder, partially deliver, and independently activate old/new envelope, profile, broker, verification, software, and compatibility artifacts across RCL, authority, recovery, and egress consumers and multiple regions.
- **Expected:** No mixed or partial set creates a permissive union; absent or incompatible consumers remain denied and final egress accepts only one exact committed complete bundle.

## 174. SPG-EV-005 — Concurrent and Stale-Base Activation

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-014 SPG-AC-005
- **Injection:** Submit concurrent, overlapping, retried, duplicated, conflicting, stale-predecessor, authority-increasing, and restrictive activations while changing referenced artifacts and quorum leadership.
- **Expected:** One exact committed history and predecessor wins; stale-base, conflicting, or superseded proposals are rejected without last-write-wins merge or field patching.

## 175. SPG-EV-006 — Restrictive Precedence and Economic Continuity

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-014 SPG-AC-006
- **Injection:** Race proven and falsely classified restrictive changes with capability issuance, claim, broker send, open orders, fills, UNKNOWN, protective leases, profile distribution, and delayed egress currentness.
- **Expected:** Only mechanically monotonic restriction uses the fast path; it denies future risk within approved bounds, cannot auto-revert, and never releases capacity, erases economic effect, cancels required protection, or converts ambiguity into permission.

## 176. SPG-EV-007 — Rollback, Restore, and Historical Replay Fencing

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-014 SPG-AC-007
- **Injection:** Restore old registry data, snapshots, caches, signatures, approvals, software, profile bundles, Activation Records, and partial histories after rollback, failover, quorum recovery, and disaster recovery.
- **Expected:** Historical validity never proves current activation; restore advances fences, incomplete history remains non-live, and reuse requires a new generation, current validation, approval, activation, and re-arm.

## 177. SPG-EV-008 — Expiry and Recovery Non-Revival

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-014 SPG-AC-008
- **Injection:** Expire and make time-unverifiable the envelope, profile, approval, compatibility attestation, and activation; then restore time, registry, cache, approval service, and deployment health.
- **Expected:** New risk is denied; recovery alone restores no generation or Live Authorization, and existing orders, exposure, UNKNOWN, and capacity remain economically effective.

## 178. SPG-EV-009 — Separation of Duties and Break-Glass Confinement

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-014 SPG-AC-009
- **Injection:** Combine author, approver, registry, signer, workflow-admin, CI/CD, deployer, compatibility-attester, emergency, and live-armer identities through shared credentials, delegation, recovery paths, and compromised automation.
- **Expected:** No strategy or single effective principal can enlarge, approve, activate, and arm authority; break-glass can only HALT or prove restriction and cannot expand, revert, release capacity, or re-arm.

## 179. SPG-EV-010 — Consumer, Software, and Broker Compatibility Drift

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-014 SPG-AC-010
- **Injection:** Change parser, schema, field coverage, formula, software, deployment, Broker Capability Profile, Failure-Domain Matrix, credential, route, endpoint, and Consumer Compatibility Manifest before and after activation.
- **Expected:** Drift invalidates or suspends affected authority; incompatible consumers and egress deny the bundle and no old attestation or permissive cache survives the change.

## 180. SPG-EV-011 — Missing or Contradictory Configuration Containment

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-014 SPG-AC-011
- **Injection:** Remove, corrupt, contradict, partition, make unreadable, or make unverifiable every bundle component while open orders, potentially-live attempts, positions, protective ownership, and external activity remain.
- **Expected:** New risk is blocked without deleting economic facts; UNKNOWN remains conservative and capacity-covered, and neither missing ACK nor cancel ACK becomes release proof.

## 181. SPG-EV-012 — Configuration Decision Replay and Evidence Completeness

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-014 SPG-AC-012
- **Injection:** Replay accepted, rejected, restrictive, expired, superseded, rollback, mixed-version, incompatible, and recovery transitions from retained artifacts and independently recompute canonical digests and decisions.
- **Expected:** An independent reviewer reconstructs every artifact, identity, approval, validation, generation, activation, denial, restrictive race, consumer result, and re-arm lineage; missing evidence blocks the gate and creates no authority.

---

# Part XV — Human Authority Governance Evidence

## 182. HAG-EV-001 — Effective Principal Collapse and Quorum Independence

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-AC-001
- **Injection:** Present multiple accounts, aliases, credentials, devices, sessions, service identities, delegated identities, authenticators, and recovery or administrative paths controlled by one natural person as separate approval principals.
- **Expected:** The Effective Principal Graph collapses common control to one counted principal; unknown or unresolved control denies authority increase and no label, role, device, or organizational separation substitutes for independence proof.

## 183. HAG-EV-002 — Exact Approval Context Binding

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-AC-002
- **Injection:** Alter or substitute request action, maximum authority, scope, reason, evidence, artifact digest, generation, software, deployment, broker, credential, route, time, policy, graph, residual risk, validity, or consumption rule after an attestation.
- **Expected:** Every material change invalidates the request, attestation, or set; only one exact current canonical context is eligible and approval creates no downstream authority by itself.

## 184. HAG-EV-003 — Separation of Duties and Self-Approval Prevention

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-AC-003
- **Injection:** Combine author, proposer, implementer, validator, evidence producer, reviewer, workflow or identity administrator, approver, deployer, credential or route administrator, and live armer through shared control, delegation, impersonation, recovery, groups, bots, and service accounts.
- **Expected:** No one effective principal can construct a unilateral authority-increasing chain; required role and conflict independence is enforced before quorum and consumption.

## 185. HAG-EV-004 — Approval Replay, Expiry, Revocation, and Consumption

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-AC-004
- **Injection:** Duplicate, reorder, replay, extend, revoke, expire, supersede, consume twice, partially consume, restore, or apply a broader or policy-mismatched attestation and Approval Set across concurrent decisions and failover.
- **Expected:** Only one current exact set can be consumed once through authoritative ordering; stale, terminal, mismatched, duplicated, or replayed artifacts grant nothing and are retained as security evidence.

## 186. HAG-EV-005 — Independent Human HALT Availability and Propagation

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-AC-005
- **Injection:** Invoke authenticated Human HALT while strategy, ordinary control plane, approval workflow, identity service, network paths, and selected egress instances fail, partition, pause, or race a permissive send before and after the irreversible boundary.
- **Expected:** One current authorized human can create a monotonic restrictive latch without a permissive quorum; authoritative commit or local latch occurs within `B_human_halt_to_commit` and every affected egress denies later risk-increasing sends within `B_halt_to_egress`.

## 187. HAG-EV-006 — Break-Glass Directional Confinement

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-AC-006
- **Injection:** Use break-glass custody, emergency credentials, workflow administration, recovery, route access, command substitution, outage, and automatic revert to attempt expansion, capacity mutation, live arming, protective self-classification, direct broker effect, or re-arm.
- **Expected:** Break glass can only HALT, deny, narrow, or request separately authorized containment; it exposes no general broker route, creates no permissive authority, never auto-reverts, and cannot re-arm.

## 188. HAG-EV-007 — Human Protective Request Cannot Bypass Safety

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-015 HAG-AC-007
- **Injection:** Label cancel, close, hedge, replace, exercise, liquidation, or emergency actions as protective while capacity, lease, state, time, broker, ownership, Final Quantity Proof, or final-egress evidence is missing, UNKNOWN, stale, or contradictory.
- **Expected:** The human input remains a proposal; independent protective classification, exclusive capacity, conservative intermediate-state proof, and final egress remain mandatory, with missing ACK and cancel ACK never becoming release proof.

## 189. HAG-EV-008 — Delegation, Roster, and Identity Recovery Fencing

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-AC-008
- **Injection:** Change employment, roster, role, scope, delegator, delegate, identity provider, authenticator, device, recovery factor, administrative control, and personnel availability before and after attestation, then restore old graphs, sessions, approvals, and delegations.
- **Expected:** Delegation is bounded, non-transitive, revocable, and never multiplies quorum; unavailable personnel do not lower quorum and recovery or migration cannot transfer or revive prior approval.

## 190. HAG-EV-009 — Approver and Workflow Compromise Containment

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-AC-009
- **Injection:** Compromise a principal, authenticator, device, session, identity provider, roster, workflow, signer, approval verifier, recovery path, or break-glass custodian before and after approval consumption, including unknown compromise scope.
- **Expected:** Affected pending authority is revoked, live scope is conservatively restricted, old control paths are fenced, economic effects remain capacity-covered, external activity is reconciled, and restoration requires fresh governance.

## 191. HAG-EV-010 — Dual-Control Re-arm and Narrow Scope

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-AC-010
- **Injection:** Attempt re-arm with one person through multiple identities, incomplete quorum, stale evidence, a reused or unioned Approval Set, broader scope, partial consumption, or a request to waive UNKNOWN, capacity, time, broker, profile, failure-domain, or egress gates.
- **Expected:** At least two distinct effective humans approve one exact current request; one set is consumed once, a fresh Live Authorization is issued only for the narrow scope, and no human quorum waives a safety gate.

## 192. HAG-EV-011 — Approval and Economic-State Continuity and Non-Revival

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-015 HAG-AC-011
- **Injection:** Expire, revoke, consume, lose, ambiguously apply, restore, or recover approvals, HALT, identity, workflow, and time services while orders, fills, cancellations, UNKNOWN, exposure, and capacity remain.
- **Expected:** Approval lifecycle changes affect only future authority; they do not cancel economic effects, release capacity, prove non-acceptance or Final Quantity, resolve UNKNOWN, clear an ambiguous HALT, or automatically re-arm.

## 193. HAG-EV-012 — Human Authority Replay and Evidence Completeness

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-015 HAG-AC-012
- **Injection:** Replay allowed, denied, abstained, expired, revoked, delegated, compromised, break-glass, Human HALT, external-manual, approval-consumption, and re-arm histories from retained raw artifacts; remove or alter required lineage and recompute independently.
- **Expected:** An independent reviewer reconstructs effective control, policy, exact review context, quorum, consumption, restriction, compromise, economic continuity, and recovery; missing or contradictory evidence blocks the gate and never substitutes for prevention.

---

# Part XVI — Evidence and Replay Integrity Evidence

## 194. ERI-EV-001 — Complete Immutable Causal Evidence Chain

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-016 ERI-AC-001
- **Injection:** Exercise proposed, approved, denied, transmitted, acknowledged, filled, cancelled, corrected, quarantined, recovered, and failed paths; omit each mandatory record class and causal parent at every owning boundary.
- **Expected:** Complete paths produce immutable source-attributed chains; every mandatory omission creates an Evidence Gap, denies a completeness claim, and cannot be repaired by inferring a convenient downstream result.

## 195. ERI-EV-002 — Pre-Effect Durability and Exact Receipt Binding

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-016 ERI-AC-002
- **Injection:** Delay, drop, forge, replay, substitute, partially persist, or acknowledge without required durability the exact pre-effect and `SEND_STARTED` records; race first broker byte against persistence and alter request, scope, policy, store, principal, or egress generation.
- **Expected:** Final egress sends no first byte before exact verifiable durability; a receipt proves custody only, stale or mismatched receipts are rejected, and post-claim ambiguity remains potentially live and capacity-covered.

## 196. ERI-EV-003 — Evidence Outage and Emergency Path Confinement

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-016 ERI-AC-003
- **Injection:** Fail, partition, pause, saturate, corrupt, or exhaust ordinary evidence ingress, primary storage, and the emergency journal while new-risk requests, Human HALT, existing protection, and separately authorized containment race at multiple egress boundaries.
- **Expected:** New risk is denied; valid restrictive HALT is still applied and hard-fences transmission even when emergency durability is ambiguous, a Critical gap is raised, protective requests still pass every non-evidence safety gate, existing protection is not blindly cancelled, and no emergency path creates permissive authority.

## 197. ERI-EV-004 — Duplicate, Reorder, Conflict, and Continuity Safety

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-016 ERI-AC-004
- **Injection:** Duplicate, delay, reorder, truncate, partially deliver, reuse identities with changed bytes, restart sequences, change continuity identities, deliver children before parents, and claim competing exclusive transitions or effects.
- **Expected:** Exact duplicates are idempotent, changed-byte reuse and semantic conflicts contain scope, continuity resets are explicit, incomplete chains remain gaps, and no ordering artifact clears UNKNOWN or releases capacity.

## 198. ERI-EV-005 — Mutation, Deletion, Fork, Anchor, and Restore Detection

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-016 ERI-AC-005
- **Injection:** Mutate, delete, substitute, truncate, fork, roll back, compact unsafely, restore an old backup, roll back source/store keys, skip anchors, and corrupt primary and replica histories under insider and infrastructure compromise.
- **Expected:** Content commitments, source identity, segment chaining, external anchors, continuity generations, and independent inventory detect every required defect; all branches are preserved and affected scope remains contained and non-live.

## 199. ERI-EV-006 — Causal Ordering and Trustworthy-Time Ambiguity

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-016 ERI-AC-006
- **Injection:** Skew, step, freeze, and disagree clocks; reset process continuity; reorder HALT, authority, capacity, capability claim, first byte, ACK, fill, cancel, replace, correction, and external events across hosts and overlapping uncertainty intervals.
- **Expected:** Reconstruction uses authoritative log positions, egress sequence, source sequence, causal links, and bounded time intervals; cross-host monotonic values are never subtracted and unresolved order is explicit and restrictive.

## 200. ERI-EV-007 — Isolated Deterministic Replay and Divergence

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-016 ERI-AC-007
- **Injection:** Replay complete and incomplete capsules while exposing candidate live credentials, signer, route, production state endpoint, Approval Set, Live Authorization, capacity API, and nondeterministic schedules; alter one safety-relevant input and output.
- **Expected:** Replay cannot reach or mutate live systems, exact inputs reproduce the approved safety-relevant result, and missing, unsupported, corrupted, or divergent inputs produce a non-PASS state with no authority or re-arm effect.

## 201. ERI-EV-008 — Historical Baseline and Schema Evolution Replay

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-016 ERI-AC-008
- **Injection:** Change schema, canonicalization, parser, dependency, software, deployment, envelope/profile, human policy/graph, broker profile, evidence policy, migration, and normalized-view version; remove historical artifacts and compare historical versus current-rule evaluation.
- **Expected:** Historical replay binds and uses the exact historical baseline, current-rule analysis is distinct, and any unavailable or incompatible baseline is `UNSUPPORTED_BASELINE` or `INCONCLUSIVE`, never silently migrated to PASS.

## 202. ERI-EV-009 — Redaction, Export, Secret, and Chain-of-Custody Safety

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-016 ERI-AC-009
- **Injection:** Redact or export identity, scope, sign, unit, quantity, ordering, outcome, and economic-effect fields; attempt unauthorized raw access and export; insert usable credentials, keys, session material, and bearer tokens; break custody metadata.
- **Expected:** Required review semantics and original digests remain verifiable, insufficient views cannot PASS, access/export is attributable, usable secrets are rejected or trigger compromise response, and chain of custody is complete without granting trading authority.

## 203. ERI-EV-010 — Retention, Compaction, Supersession, and Deletion Safety

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-016 ERI-AC-010
- **Injection:** Expire, compact, supersede, archive, release legal hold, and request deletion while open orders, potentially-live attempts, UNKNOWN, positions, capacity, incidents, failed evidence, and accepted verification scope remain; attempt single-admin destructive action.
- **Expected:** Economic and verification horizons dominate retention, reconstructability and tombstones survive approved compaction, negative evidence remains linked, destructive action is dual-controlled and ineligible while obligations remain, and no lifecycle action releases capacity or authority.

## 204. ERI-EV-011 — Broker, External, and Non-Trade Evidence Conservatism

- **Minimum Level:** EV-L2/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-016 ERI-AC-011
- **Injection:** Lose ACK, receive cancel ACK without final quantity, omit query pages, delay or correct fills, change broker cursor/session, create portal/dealer activity, and inject assignment, exercise, transfer, fee, and corporate-action events with incomplete provenance.
- **Expected:** Raw broker semantics and completeness metadata are retained; no omission proves non-effect, no cancel ACK becomes Final Quantity Proof, external/non-trade facts remain attributed, and affected uncertainty consumes conservative capacity and blocks new risk.

## 205. ERI-EV-012 — Recovery Non-Revival and Incident Reconstruction

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-016 ERI-AC-012
- **Injection:** Fail over and recover evidence store, ingestion, keys, anchors, emergency journal, archive, and replay service; restore conflicting histories; repair gaps; complete replay while old approvals, authority, profiles, credentials, HALT state, orders, fills, UNKNOWN, and capacity exist.
- **Expected:** Recovery creates new continuity and preserves branches, gaps, economic effects, and restrictive state; it creates no permission or automatic re-arm, and an independent reviewer reconstructs facts, inferences, uncertainty, custody, exposure, and gate impact.

---

# Part XVII — Safe Startup and Recovery Barrier Evidence

## 206. SBR-EV-001 — Closed Startup and Fresh Live-Arming Chain

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-017 SBR-AC-001
- **Injection:** Exercise cold start, warm restart, reconnect, failover, rollback, restore, incident recovery, process pause, and delayed dependency discovery while attempting risk-increasing authorization and first broker byte at every transition.
- **Expected:** The affected Recovery Barrier begins closed before recovery observation is treated as current; no new-risk capability or byte passes until the complete fresh readiness, approval, Live Authorization, capacity, and egress chain succeeds.

## 207. SBR-EV-002 — Recovery Generation Propagation and Stale Egress Rejection

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-017 SBR-AC-002
- **Injection:** Advance Recovery Generation during capability issuance, quorum claim, queued work, reconnect, and the final send race; delay, drop, reorder, replay, and cache the barrier transition beyond `B_recovery_trigger_to_barrier` and `B_recovery_barrier_to_egress`.
- **Expected:** New generation restriction reaches every affected issuer and final egress within approved bounds; stale readiness, package, capability, claim, cache, or session is denied and any ambiguous send remains potentially live and capacity-covered.

## 208. SBR-EV-003 — Competing Recovery Owner Fencing

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-017 SBR-AC-003
- **Injection:** Run concurrent, stale, paused, minority, partitioned, restored, rolled-back, and broker-reachable Recovery Coordinators; reuse session identities and publish conflicting candidates under old owner epochs and generations.
- **Expected:** Only the current fenced owner may publish a candidate for the current Recovery Generation; every stale or conflicting owner and decision is rejected without opening the barrier or creating authority.

## 209. SBR-EV-004 — Complete Recovery Inventory and Obligation Closure

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-017 SBR-AC-004
- **Injection:** Omit each required capacity, intent, attempt, order, fill, position, external, non-trade, protection, configuration, authority, identity, credential, route, time, evidence, broker, and failure-domain dependency from the scope and obligation graph.
- **Expected:** Dependency closure expands conservatively, every omission or unresolved obligation produces `NOT_READY`, and no service-health or cache-consistency result substitutes for complete economic and safety inventory.

## 210. SBR-EV-005 — Non-Atomic Broker Inventory Conservatism

- **Minimum Level:** EV-L2/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-017 SBR-AC-005
- **Injection:** Page and query while fills, cancels, late fills, corrections, manual orders, assignments, and corporate events occur; omit pages and cursors, lose ACK, return cancel ACK without final quantity, change broker sessions, and present temporary flat snapshots.
- **Expected:** The Inventory Cut records source continuity, start/end revisions, intervening events, completeness uncertainty, and convergence; missing ACK never proves non-acceptance, cancel ACK never becomes Final Quantity Proof, and no optimistic capacity release or readiness occurs.

## 211. SBR-EV-006 — UNKNOWN Conflict Gap Timeout and Retry Containment

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-017 SBR-AC-006
- **Injection:** Create stale and conflicting evidence, UNKNOWN attempts and exposure, unbounded cuts, Evidence Gaps, dependency outage, timeout, owner loss, backpressure, failed retries, and repeated non-convergence.
- **Expected:** Uncertainty remains explicit, consumes conservative capacity, blocks new risk, leaves the barrier closed, and cannot be reduced by timeout, retry count, operator narrative, audit, or replay.

## 212. SBR-EV-007 — Restricted Readiness Dependency Isolation

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-017 SBR-AC-007
- **Injection:** Request `READY_RESTRICTED` while nominally separate scopes share aggregate capacity, margin, collateral, broker session, credential, route, rate limit, protection, authority, configuration, identity administrator, or failure domain; hide and then reveal dependency edges.
- **Expected:** Partial readiness is denied unless the complete unaffected dependency closure is positively proven; unknown mapping expands scope and no shared resource or aggregate constraint is reused as permission.

## 213. SBR-EV-008 — HALT Evidence Failure and Protective Continuity

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-017 SBR-AC-008
- **Injection:** Race Human HALT and authoritative HALT against every recovery state, owner failover, evidence-store and emergency-journal failure, ordinary cleanup, cancellation, replacement, and separately authorized protective action.
- **Expected:** HALT and local restrictive latches dominate; evidence failure never delays restriction or creates permission, recovery cannot clear HALT, and required existing protection is not blindly cancelled while any new protective action still passes its independent authority and capacity gates.

## 214. SBR-EV-009 — Readiness Invalidation Before Authority and Egress

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-017 SBR-AC-009
- **Injection:** After Inventory Cut, package, or readiness creation, change fills, broker corrections, external activity, non-trade events, capacity, protection, configuration, software, identity, credential, route, time, evidence, policy, scope, and any bound generation; race each change against approval, authorization issuance, claim, and send.
- **Expected:** Every material change invalidates the affected readiness before future authority issuance or egress acceptance; an expired, stale, or superseded readiness artifact creates no permission and does not expire economic effect.

## 215. SBR-EV-010 — Restore Conflict and Worst-Credible Economic Union

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-017 SBR-AC-010
- **Injection:** Restore old and divergent workflow, RCL, evidence, broker, configuration, key, and identity histories; keep predecessor writers, sessions, credentials, egress principals, and recovery owners reachable; withhold the apparent highest branch.
- **Expected:** Restore creates new generations, fences every predecessor, preserves all histories and gaps, covers the worst credible economic union, and remains non-live until conservative resolution and fresh governed re-arm.

## 216. SBR-EV-011 — Recovery Authority Separation and Forced-Ready Denial

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-017 SBR-AC-011
- **Injection:** Give recovery, operator, evidence, replay, workflow, and administrator identities direct or indirect access to RCL mutation, configuration activation, Live Authorization, protective classification, HALT clear, broker credential, signer, session, route, and forced-readiness endpoints.
- **Expected:** Every privilege path is absent or denied; recovery may submit evidence-bound requests only, the RCL remains sole capacity authority, final egress remains sole transmission enforcement, and no human or service can force `READY` or clear HALT.

## 217. SBR-EV-012 — Recovery Completion Non-Revival and Replay

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-017 SBR-AC-012
- **Injection:** Complete recovery, restore health and connectivity, repair evidence gaps, match replay, expire decisions, acknowledge incidents, and recover time, identity, profile, workflow, broker, and egress services while prior authorization, approval, capability, orders, UNKNOWN, exposure, and capacity remain.
- **Expected:** Prior artifacts never become current or active again; readiness grants no authority, economic effects survive artifact lifecycle, and only a complete fresh ADR-002-007/015 chain can create narrowly scoped new authority.

---

# Part XVIII — Critical Input Integrity and Decision-Context Evidence

## 218. CII-EV-001 — Critical Input Classification Completeness

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-018 CII-AC-001
- **Injection:** Introduce safety-relevant values through feature, signal, cache, reference, override, operator, derived-field, broker-fact, and fallback paths while omitting or misclassifying each from policy.
- **Expected:** Dependency analysis classifies every value capable of changing safety or economic effect as Critical; omitted or unknown classification blocks affected new risk and no naming or storage path bypasses policy.

## 219. CII-EV-002 — Source Identity Continuity and Replay Fencing

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-018 CII-AC-002
- **Injection:** Substitute source principal, endpoint, credential, environment, account, venue, or feed; reset, gap, duplicate-conflict, roll back, restore, and replay source sequence/revision and continuity while keeping transport healthy.
- **Expected:** Unknown or stale source and continuity are rejected or explicitly non-permissive; cache, heartbeat, connection health, repeated payload, and last sequence do not establish continuity or permission.

## 220. CII-EV-003 — Identity Unit Scale and Mapping Integrity

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-018 CII-AC-003
- **Injection:** Mutate instrument, contract, account, venue, currency, unit, scale, sign, multiplier, symbol alias, and mapping generation at proposal, approval, capacity, request construction, and egress.
- **Expected:** Every mismatch or ambiguity is rejected before new-risk transmission; no default account, symbol fallback, silent conversion, or valid signature over wrong semantics creates permission.

## 221. CII-EV-004 — Transformation Lineage and Hidden-Default Safety

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-018 CII-AC-004
- **Injection:** Change parser, library, model, formula, schema, configuration, rounding, clipping, interpolation, imputation, fill-forward, missing-data behavior, parameter, and intermediate input while hiding or breaking lineage.
- **Expected:** Unreproducible, unapproved, incomplete, or changed lineage invalidates the derived input and dependent Capsule; no hidden default or stale feature reuse permits new risk.

## 222. CII-EV-005 — Freshness Consistency and Source-Conflict Conservatism

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-018 CII-AC-005
- **Injection:** Supply stale, future, delayed, reordered, crossed, outlier, incompatible-cut, non-atomic, and conflicting source values; manipulate transport uncertainty, receipt age, time health, majority composition, cache agreement, and last-known-good age.
- **Expected:** Field states and uncertainty remain explicit; cross-host age follows consumer-local receipt rules; no averaging, majority, cache, health, TTL, or repeated-read shortcut turns conflict or unknown state into permission.

## 223. CII-EV-006 — Independent Approval and Common-Mode Detection

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-018 CII-AC-006
- **Injection:** Make proposer and approver share upstream origin, parser, mapping registry, feature store, cache, message bus, library, administrator, credential, time source, deployment, or failure domain; falsely label endpoints or vendors independent.
- **Expected:** Effective common modes collapse before corroboration is counted; missing independence blocks approval unless a separately approved SAFE-034 residual-risk path and scope reduction are present, and the proposer cannot approve the exception.

## 224. CII-EV-007 — Exact Capsule Binding and Substitution Resistance

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-018 CII-AC-007
- **Injection:** Mutate, union, partially refresh, downgrade, replay, or substitute Capsule, Snapshot, digest, field, scope, generation, proposal, attestation, Intent, capacity request, authorization, capability, proof, evidence receipt, or broker request.
- **Expected:** Every consumer rejects the chain; a material change requires a new Capsule and complete downstream decisions, and no hidden recomputation or valid artifact from another scope creates permission.

## 225. CII-EV-008 — Correction Retraction and Invalidation Fan-Out

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-018 CII-AC-008
- **Injection:** Correct, retract, supersede, expire, or change source continuity, policy, mapping, unit, schema, transformation, time, venue, broker/account state, external activity, non-trade state, or evidence after Snapshot, approval, authorization, and capability creation.
- **Expected:** The full affected dependency closure is invalidated at approval/authority and egress within approved bounds; new risk is blocked while orders, attempts, UNKNOWN, exposure, and capacity effects persist.

## 226. CII-EV-009 — Active Final-Egress Context Currentness

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-018 CII-AC-009
- **Injection:** Delay, drop, reorder, cache, replay, and suppress Context Generation and invalidation state; partition egress from context authority; race invalidation before capability claim, after claim, and before first byte.
- **Expected:** Final egress actively proves exact current context and rejects permissive cache, TTL, heartbeat, health, eventual-consistency, or absence-of-event substitutes; ambiguous sends become potentially live and capacity-covered without blind retry.

## 227. CII-EV-010 — Input Degradation and Protective Confinement

- **Minimum Level:** EV-L1/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-018 CII-AC-010
- **Injection:** Remove or conflict market, reference, account, venue, session, and protective inputs during normal and degraded operation; pressure fallback through outage and protective urgency.
- **Expected:** Ordinary new risk is denied; HALT and existing protection remain available, and only separately authorized, RCL-capacity-backed, conservatively bounded protective or containment action may reach final egress. Priority alone creates no reserve.

## 228. CII-EV-011 — Context Authority Separation and Human-Override Denial

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-018 CII-AC-011
- **Injection:** Give Context Integrity, data, operator, workflow, evidence, and replay principals direct or indirect access to approval, RCL mutation/release, protective classification, HALT clear, Live Authorization, broker credential, signer, session, route, forced-ready, or re-arm paths.
- **Expected:** Every authority path is absent or denied; RCL remains sole capacity authority, final egress remains sole transmission enforcement, and manual values follow the full Critical Input contract.

## 229. CII-EV-012 — Restart Restore Recovery and Non-Revival

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-018 CII-AC-012
- **Injection:** Restart and restore sources, parser, mapping, cache, policy, Context Integrity, approval, evidence, time, and recovery services; warm old caches, repair gaps, match replay, and recover connectivity while old Capsules and economic effects remain.
- **Expected:** New continuity and fresh Snapshots/Capsules are required; no old context, approval, authorization, or capability revives, no automatic re-arm occurs, and economic/UNKNOWN/capacity state persists conservatively.

---

# Part XIX — Venue and Tradability Gate Evidence

## 230. VTG-EV-001 — Closed Exceptional and Phase-Transition Sessions

- **Minimum Level:** EV-L1/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-019 VTG-AC-001
- **Injection:** Exercise scheduled and unscheduled close, delayed open, opening and closing auctions, volatility interruption, reopen, after-hours, and next-session transitions while stale phase decisions remain cached.
- **Expected:** Exact phase-specific decisions are required; schedule, quote flow, connectivity, and old `ADMISSIBLE` state never authorize a send.

## 231. VTG-EV-002 — Halt Suspension and Tradability Conflict

- **Minimum Level:** EV-L2/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-019 VTG-AC-002
- **Injection:** Conflict venue status, broker state, quote/trade flow, calendar, halt, suspension, auction, and instrument-eligibility sources; delay and suppress restrictive changes.
- **Expected:** Ordinary new risk stops, conflict remains `UNKNOWN`, and no majority, newest event, recent trade, or absence of restriction resolves the state permissively.

## 232. VTG-EV-003 — Exact Instrument Contract Account and Route

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-019 VTG-AC-003
- **Injection:** Substitute environment, broker, account/subaccount, venue, market segment, symbol alias, contract month, product, currency, and broker route at each proposal-to-egress binding.
- **Expected:** Every mismatch is rejected; no alias, fallback account, or alternate route widens the exact approved scope.

## 233. VTG-EV-004 — Price Tick Lot Quantity and Order Shape

- **Minimum Level:** EV-L1/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-019 VTG-AC-004
- **Injection:** Cross static/dynamic price bands and tick-table boundaries; vary lot, odd-lot, min/max quantity, rounding, order type, time in force, position effect, triggers, and routing flags.
- **Expected:** Unsupported or mutated shapes fail; no silent rounding, normalization, partial refresh, or broker-rejection assumption creates permission.

## 234. VTG-EV-005 — Margin Borrow Settlement and Account Eligibility

- **Minimum Level:** EV-L2/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-019 VTG-AC-005
- **Injection:** Return stale, contradictory, revoked, scope-mismatched, or discontinuous product permission, margin, collateral, buying power, borrow, locate, settlement, currency, and account-restriction evidence.
- **Expected:** New risk stops; uncertainty cannot create headroom or permission, and existing or potentially-live effects remain conservatively capacity-covered.

## 235. VTG-EV-006 — Exact Decision Binding and Substitution Resistance

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-019 VTG-AC-006
- **Injection:** Mutate, union, widen, partially refresh, replay, or substitute one Venue Constraint Snapshot, Order Admissibility Decision, Capsule, approval, Intent, capacity, authorization, capability, Commit Proof, or broker-request field.
- **Expected:** The complete chain is rejected and a fresh exact decision plus every affected downstream artifact is required.

## 236. VTG-EV-007 — Active Final-Egress Currentness and Invalidation Race

- **Minimum Level:** EV-L2/EV-L3 plus security and applicable broker evidence
- **Supports:** ADR-002-019 VTG-AC-007
- **Injection:** Invalidate session, halt, tradability, price band, account permission, margin, borrow, settlement, or broker capability before claim and between capability claim and first byte; partition egress from the constraint authority and offer cached permissive substitutes.
- **Expected:** Final egress actively proves current exact state and denies stale or unverifiable requests; unprovable send ordering remains potentially live and capacity-covered with no blind retry.

## 237. VTG-EV-008 — Exit Reduce-Only Cancel and Reversal

- **Minimum Level:** EV-L2/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-019 VTG-AC-008
- **Injection:** Exercise unsupported exits, wrong close-side/position-effect, zero crossing, reversal, reduce-only drift, cancel crossing fill, missing acknowledgement, cancel acknowledgement, and late fill.
- **Expected:** No exit is assumed executable; missing ACK is not non-acceptance, cancel ACK is not Final Quantity Proof, and no early capacity release or blind retry occurs.

## 238. VTG-EV-009 — Protective and Replacement Constraints

- **Minimum Level:** EV-L2/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-019 VTG-AC-009
- **Injection:** Request protective maintenance and replacement during halt, auction, price limit, shared rate/session pressure, unsupported reduce-only, non-atomic replace, partial fill, gap, and overlap.
- **Expected:** Protective label and priority create no permission or reserve; only exact separately authorized and capacity-covered paths proceed, otherwise containment and trapped-exposure handling apply.

## 239. VTG-EV-010 — Source Policy Capability and Common-Mode Drift

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-019 VTG-AC-010
- **Injection:** Restart, roll back, substitute, corrupt, partition, or jointly administer calendars, status feeds, mappings, rule engines, margin/borrow services, broker profiles, caches, credentials, routes, and deployments.
- **Expected:** Unknown continuity and shared control are not counted as current or independent; stale generations are fenced and live scope reduces or closes.

## 240. VTG-EV-011 — Authority Separation and Bypass Resistance

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-019 VTG-AC-011
- **Injection:** Give Gate, data, operator, workflow, broker-query, evidence, and replay principals paths to approval, RCL mutation/release, protective classification, HALT clear, authority issuance, capability creation, live credential, order route, portal fallback, or re-arm.
- **Expected:** Every path is absent or denied; RCL remains sole capacity authority and final egress remains sole transmission enforcement.

## 241. VTG-EV-012 — Recovery Reopen and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security and applicable broker evidence
- **Supports:** ADR-002-019 VTG-AC-012
- **Injection:** Reopen venue, release halt, reconnect broker, restore account/margin/borrow/clock/Gate/evidence services, warm old decisions, match replay, and complete reconciliation while old economic effects remain.
- **Expected:** Fresh continuity, Constraint Generation, Snapshot, decision, recovery obligations, approval, authority, and governed re-arm are required; no old decision or authority revives and economic state remains conservative.

---

# Part XX — Intent-to-Order Conformance Evidence

## 242. IOC-EV-001 — Direction and Position-Effect Inversion

- **Minimum Level:** EV-L1/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-020 IOC-AC-001
- **Injection:** Invert buy/sell, long/short, open/close, reduce-only, signed quantity, broker side, and position-effect semantics, including zero-crossing and reversal cases.
- **Expected:** Every unintended semantic or economic effect is rejected before send; no sign, side, or position-effect default can change the approved Intent.

## 243. IOC-EV-002 — Account Instrument Contract Environment and Route Substitution

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-020 IOC-AC-002
- **Injection:** Substitute default account, subaccount, environment, broker, venue, market segment, symbol alias, contract month, endpoint, redirect, session family, and route during construction and after proof.
- **Expected:** Every mismatch is rejected at construction or final egress; no alias, default, redirect, or credential/route combination widens exact scope.

## 244. IOC-EV-003 — Unit Multiplier Currency Scale and Numeric Safety

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-020 IOC-AC-003
- **Injection:** Vary quantity unit, contract multiplier, currency, scale, precision, sign, exponent, locale, platform, overflow, underflow, NaN, infinity, and negative-zero behavior.
- **Expected:** Construction fails or remains exactly equivalent under the approved deterministic numeric rules; no lossy or ambiguous coercion reaches authority or egress.

## 245. IOC-EV-004 — Quantity Tick Lot and Rounding

- **Minimum Level:** EV-L1/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-020 IOC-AC-004
- **Injection:** Cross minimum, maximum, step, fractional/odd-lot, lot, tick, clamp, truncation, integer-division, and supposedly risk-reducing rounding boundaries.
- **Expected:** Only exact envelope-authorized results pass; smaller or rounded commands that remove protection, change exposure, or evade capacity and venue evaluation are rejected.

## 246. IOC-EV-005 — Price Order Type TIF Expiration Flags and Mode

- **Minimum Level:** EV-L1/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-020 IOC-AC-005
- **Injection:** Mutate price aggressiveness, trigger, collar, order type, time in force, expiry, auction/route flags, reduce/post-only, and live/non-live/degraded mode through defaults and explicit fields.
- **Expected:** Every widening, omission, default disagreement, or semantic mismatch is denied; non-live commands cannot become live through a flag or route change.

## 247. IOC-EV-006 — Economic Effect and Capacity Dominance

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-020 IOC-AC-006
- **Injection:** Exercise full/partial fills, reversal, reduce-only failure, broker rounding, fees/cash legs, simultaneous split execution, existing potentially-live attempts, and amend/replace overlap.
- **Expected:** The Economic Effect Envelope covers every credible outcome and the exact RCL commitment dominates it; uncertainty never shrinks the envelope or creates headroom.

## 248. IOC-EV-007 — Canonicalization and Parser Differential

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-020 IOC-AC-007
- **Injection:** Use duplicate JSON keys or FIX tags, unknown/extra fields, field reordering, Unicode and percent-encoding variants, alternate numeric encodings, null/default ambiguity, and compiler/SDK/broker parser disagreement.
- **Expected:** Any ambiguous, non-canonical, or different broker interpretation fails closed; byte and semantic digests cannot be used interchangeably without proof.

## 249. IOC-EV-008 — Post-Proof Mutation and Actual-Outbound Equivalence

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-020 IOC-AC-008
- **Injection:** Mutate, merge, split, duplicate, redirect, normalize, or replay commands through serializer, signer, queue, proxy, sidecar, SDK, session manager, and retry wrapper after proof issuance.
- **Expected:** Final egress detects every semantic, identity, route, signer-input, or outbound-representation mismatch and sends no broker-directed byte.

## 250. IOC-EV-009 — Retry Cancel Amend Replace Split and Aggregate

- **Minimum Level:** EV-L2/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-020 IOC-AC-009
- **Injection:** Lose ACK, cross cancel/fill, change retry payload, reuse idempotency identity, regenerate remaining quantity, overlap replacement, duplicate split children, and aggregate unrelated Intents.
- **Expected:** Exact command/attempt lineage, current proof/authority, conservative capacity, missing-ACK, cancel-ACK, and no-blind-retry rules hold under every interleaving.

## 251. IOC-EV-010 — Protective and Exit Construction

- **Minimum Level:** EV-L2/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-020 IOC-AC-010
- **Injection:** Under urgency, alter protective/exit side, position effect, order type, price, route, quantity, reduce-only behavior, priority, or construction envelope.
- **Expected:** Label and priority create no permission or reserve; only exact separately authorized, admissible, capacity-covered, conformant commands may proceed, otherwise containment and trapped-exposure handling apply.

## 252. IOC-EV-011 — Authority Separation Compiler Drift and Bypass

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-020 IOC-AC-011
- **Injection:** Compromise or roll back policy, mapping, schema, compiler, SDK, compatibility, generation, verifier, and deployment identities; give compiler or manual paths approval, RCL, authority, credential, route, transmission, HALT-clear, or re-arm access.
- **Expected:** Stale generations and all bypass paths are fenced or denied; Order Construction remains non-authorizing and final egress remains the sole transmission enforcement point.

## 253. IOC-EV-012 — Restart Restore Recovery Replay and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-020 IOC-AC-012
- **Injection:** Restart, restore, fail over, or roll back compiler, mappings, serializer, SDK, cache, signer, egress, and evidence; recompile identically and match replay while old commands, UNKNOWN, exposure, and capacity remain.
- **Expected:** Fresh current artifacts and governed authority are required; no old proof, capability, or live scope revives, no automatic re-arm occurs, and economic state remains conservative.

---

# Part XXI — Aggregate Risk Evaluation Evidence

## 254. ARE-EV-001 — Aggregate Scope Completeness

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-021 ARE-AC-001
- **Injection:** Omit, delay, duplicate, or misattribute one strategy, account, venue, instrument, position, order, fill, commitment, external action, trapped exposure, protective reservation, or concurrent authorization from the aggregate cut.
- **Expected:** Missing or ambiguous scope is included conservatively or denies allocation; no local pass or incomplete shard creates aggregate headroom.

## 255. ARE-EV-002 — Exact Effect and Snapshot Binding

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-021 ARE-AC-002
- **Injection:** Substitute, patch, union, partially refresh, replay, or cross-scope mix the Aggregate Risk State Snapshot, Adverse Scenario Set, Canonical Broker Command, or Economic Effect Envelope.
- **Expected:** Every identity, generation, digest, cut, scope, and dependency mismatch is denied; no mixed artifact yields `GRANT`.

## 256. ARE-EV-003 — Partial Fill Overlap Reversal and Missing ACK

- **Minimum Level:** EV-L1/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-021 ARE-AC-003
- **Injection:** Explore every partial-fill prefix, fill/cancel/replace/retry ordering, old/new overlap, zero crossing, reversal, delayed fill, acknowledgement loss, and broker receipt ambiguity.
- **Expected:** Projected state and the exact committed vector dominate every credible intermediate effect; missing ACK remains potentially live and cancel ACK is not Final Quantity Proof.

## 257. ARE-EV-004 — Dimension Unit Scope and Limit Integrity

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-021 ARE-AC-004
- **Injection:** Omit a risk dimension or scope; alter unit, sign, scale, aggregation, limit source, valuation rule, uncertainty rule, or cross-dimension comparison; replace a vector with scalar notional.
- **Expected:** Every missing, incompatible, or ambiguous semantic fails closed; the Hard Safety Envelope and every applicable scope remain dominant.

## 258. ARE-EV-005 — Netting Hedge Correlation and Common Mode

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-021 ARE-AC-005
- **Injection:** Break hedge legs, basis/correlation, liquidity, venue availability, timing, account eligibility, margin offset, source independence, verifier independence, and shared model/mapping/administrator assumptions.
- **Expected:** Unproven benefits are removed; trapped or potentially-live exposure is not netted away; common-mode paths cannot fabricate independent confirmation.

## 259. ARE-EV-006 — Valuation Margin Liquidity and Tail Scenarios

- **Minimum Level:** EV-L1/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-021 ARE-AC-006
- **Injection:** Use stale/zero/negative/future/crossed prices, extreme FX, margin/collateral/borrow changes, illiquidity, impact, slippage, gaps, volatility/convexity, assignment/exercise, settlement delay, and exit unavailability.
- **Expected:** The maximum credible effect remains within the approved envelope or the action is denied; broker buying power and expected rejection never create local authority.

## 260. ARE-EV-007 — Numerical Determinism and Failure

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-021 ARE-AC-007
- **Injection:** Trigger overflow, underflow, NaN, infinity, negative zero, precision loss, nondeterministic ordering, parser/library/model differential, solver non-convergence, scenario truncation, iteration limit, and fallback.
- **Expected:** Independent implementations reproduce the same conservative vector or deny; no failure, truncation, clamp, last-known value, or skipped dimension shrinks risk.

## 261. ARE-EV-008 — Concurrent Grant and RCL Serialization

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-021 ARE-AC-008
- **Injection:** Issue concurrent exact-looking grants against overlapping headroom, advance RCL state between snapshot and commit, replay a grant, use a stale writer epoch, and request a vector/scope different from the decision.
- **Expected:** Only the RCL commits available capacity once; stale, conflicting, broader, replayed, or state-incompatible requests are rejected without evaluator-side mutation.

## 262. ARE-EV-009 — Invalidation and Final-Egress Currentness

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-021 ARE-AC-009
- **Injection:** Change position, fill, external activity, margin, collateral, price, liquidity, correlation, policy, scenario, model, schema, mapping, context, venue, or broker capability before RCL admission, capability claim, and first byte; delay invalidation beyond approved bounds.
- **Expected:** Stale decisions are actively fenced at RCL and final egress; cache/TTL/heartbeat/health/absence-of-event is not currentness proof; ambiguous sends remain potentially live and capacity-covered.

## 263. ARE-EV-010 — Protective Exit and Partition Behavior

- **Minimum Level:** EV-L2/EV-L3 plus applicable broker evidence
- **Supports:** ADR-002-021 ARE-AC-010
- **Injection:** Apply protective/exit/reduce-only/priority labels, exhaust reserve, remove exit feasibility, create protection gap/overlap, partition the risk/control plane while broker egress remains reachable, and attempt new grant or lease expansion.
- **Expected:** No label, priority, partition, or urgency creates capacity; only exact pre-committed exclusive protective scope may proceed, otherwise containment and trapped-exposure handling apply.

## 264. ARE-EV-011 — Authority Separation and Security Bypass

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-021 ARE-AC-011
- **Injection:** Compromise policy, scenario, snapshot, evaluator, verifier, model, mapping, library, deployment, or administrator identities; attempt direct RCL mutation, authority issuance, live credential/route acquisition, or final-egress bypass.
- **Expected:** Every unauthorized combination is denied or contained; the Aggregate Risk Authority grants only an exact allocation request, RCL alone mutates capacity, and final egress alone transmits.

## 265. ARE-EV-012 — Recovery Economic Continuity and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-021 ARE-AC-012
- **Injection:** Restart, restore, roll back, fail over, rebuild cache, recover source/model/library, reconcile, replay, improve prices or margin, and reconnect broker while prior decisions, UNKNOWN, commitments, or possible effects remain.
- **Expected:** Stale generations and decisions remain fenced; existing effects retain conservative capacity; fresh evaluation and governed re-arm are required and no automatic re-arm occurs.

# Part XXII — Action Flow Governance Evidence

## 266. AFG-EV-001 — Distributed Shared-Limit Serialization

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-022 AFG-AC-001
- **Injection:** Drive concurrent producers across processes, nodes, accounts, credentials, sessions, routes, endpoints, and action classes against overlapping local, broker-global, and unknown-scope limits.
- **Expected:** The RCL serializes the complete shared action-flow vector; local counters cannot over-allocate, choose a narrower scope, or create headroom.

## 267. AFG-EV-002 — Duplicate Event and Fan-Out Amplification

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-022 AFG-AC-002
- **Injection:** Duplicate, reorder, fork, replay, redeliver, and fail over one root cause through multiple consumers, queues, and schedulers while attempting to reset cause identity.
- **Expected:** One immutable cause lineage remains within finite fan-out, depth, attempts, queue, elapsed-time, and broker-mutation bounds; overflow invokes containment.

## 268. AFG-EV-003 — Missing-ACK Retry and Reconnect Storm

- **Minimum Level:** EV-L2/EV-L3 plus broker evidence
- **Supports:** ADR-002-022 AFG-AC-003
- **Injection:** Drop responses after possible broker acceptance, trigger timeouts, SDK/proxy retries, reconnect callbacks, redirects, route failover, and new client-order identities.
- **Expected:** Missing ACK never becomes non-acceptance; the original action remains potentially live and capacity-covered, every retry is governed, and blind resubmission is denied.

## 269. AFG-EV-004 — Cancel Amend and Replace Storm

- **Minimum Level:** EV-L1/EV-L3 plus broker evidence
- **Supports:** ADR-002-022 AFG-AC-004
- **Injection:** Cross partial fills, price changes, cancel ACKs, timeouts, reconnects, and protective replacement while repeatedly oscillating cancel, amend, replace, and submit.
- **Expected:** Cause amplification remains bounded; cancel ACK is not Final Quantity Proof; overlap, late-fill, reversal, protection-gap, economic-capacity, and flow-capacity rules remain conservative.

## 270. AFG-EV-005 — Complete Action and Resource Classification

- **Minimum Level:** EV-L2/EV-L3 plus broker evidence
- **Supports:** ADR-002-022 AFG-AC-005
- **Injection:** Exhaust submit, cancel, amend, replace, query, session, reconnect, queue, in-flight, credential, route, endpoint, and administrative resources separately and jointly while relabeling actions.
- **Expected:** Every broker-facing class and common-mode resource is counted under the most conservative applicable shared scope; no label or omitted class bypasses admission.

## 271. AFG-EV-006 — Protective Reserve Exclusivity

- **Minimum Level:** EV-L2/EV-L3 plus broker and security assessment
- **Supports:** ADR-002-022 AFG-AC-006
- **Injection:** Saturate ordinary request, order, cancel, query, queue, in-flight, credential, session, route, endpoint, and broker-rate resources, then require protective, reconciliation, and HALT-supporting traffic while presenting priority-only claims.
- **Expected:** Normal traffic cannot consume the minimum reserve; only physically or logically reserved proven scope is counted; priority-only or common-mode uncertainty narrows or prohibits live scope.

## 272. AFG-EV-007 — RCL Atomicity and Permit Single Use

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-022 AFG-AC-007
- **Injection:** Race economic and action-flow commitments, lose commit responses, duplicate permits and claim nonces, crash before and after claim, replay consumed identities, and advance RCL state between decision and admission.
- **Expected:** Economic and flow coverage commit atomically or not at all; every permit is exact and single-use; ambiguous claims remain consumed or quarantined and cannot be replayed.

## 273. AFG-EV-008 — Time Refill and Counter Integrity

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-022 AFG-AC-008
- **Injection:** Step, freeze, roll back, and recover wall clocks; break monotonic continuity; compare cross-host timestamps; restart counters; race window boundaries; restore stale snapshots; and create counter divergence.
- **Expected:** Only approved trustworthy-time and RCL history can replenish capacity; uncertainty is restrictive and no clock, restart, restore, or divergence manufactures headroom.

## 274. AFG-EV-009 — Invalidation and Final-Egress Currentness

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-022 AFG-AC-009
- **Injection:** Change policy, broker limit, scope graph, session, credential, route, endpoint, reserve, queue, constraint, capability, or generation between decision, RCL commit, claim, and first byte; suppress invalidation and offer cached health or tokens.
- **Expected:** RCL and final egress actively prove exact current state and deny stale or unprovable actions; ambiguous races remain potentially live, permit-consumed or quarantined, and economically covered without blind retry.

## 275. AFG-EV-010 — Partition Stale Writer and Protective Lease

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-022 AFG-AC-010
- **Injection:** Partition the control plane from broker-reachable egress, lose quorum, resume stale RCL/governor/scheduler/egress instances, overlap protective sub-ledgers, and attempt remote or wall-clock refill.
- **Expected:** Normal permits stop; stale generations remain fenced; only an exclusive pre-issued bounded protective lease may consume a monotonic local sub-budget, otherwise transmission is denied.

## 276. AFG-EV-011 — Authority Separation and Bypass

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-022 AFG-AC-011
- **Injection:** Attempt direct capacity mutation or broker send from strategy, Action Flow Governor, local limiter, scheduler, queue, retry/reconnect service, SDK, signer, reconciliation, recovery, replay, operator, and alternate credentials/routes.
- **Expected:** RCL remains the sole capacity mutation authority, final egress remains the sole transmission enforcement point, and no evaluator, local token, priority, or intermediary creates permission.

## 277. AFG-EV-012 — Recovery Economic Continuity and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-022 AFG-AC-012
- **Injection:** Restart, roll back, restore, fail over, reconnect, drain queues, expire backoff, refill counters, recover broker health, and replay matching history while prior actions, permits, claims, UNKNOWN, or possible effects remain.
- **Expected:** Old decisions, permits, counters, capabilities, authority, and live scope do not revive; possible effects remain capacity-covered; recovery stays non-live until fresh governed re-arm.

---

# Part XXIII — Independent Proposal Approval Evidence

## 278. IAP-EV-001 — Complete Exact Request

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-023 IAP-AC-001
- **Injection:** Omit, wildcard, default, patch, partially refresh, union, or substitute each request field and bound artifact independently and in combinations.
- **Expected:** No incomplete or changed request yields or preserves `APPROVE`; every material change creates a new identity and chain.

## 279. IAP-EV-002 — Independent Validation and Common Mode

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-023 IAP-AC-002
- **Injection:** Corrupt proposer output and repeat through nominally separate approvers sharing source, parser, mapping, library, cache, registry, administrator, deployment, network, credential, or clock dependencies.
- **Expected:** Shared paths are identified as common mode and cannot satisfy independent validation; unavailable independence denies or enforces only the independently approved reduced scope.

## 280. IAP-EV-003 — Deterministic Restrictive Decision

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-023 IAP-AC-003
- **Injection:** Replay identical complete inputs across evaluator instances and platforms, then introduce missing, stale, conflicting, unsupported, unverifiable, future-time, and timeout conditions.
- **Expected:** Complete identical inputs produce one deterministic result; every uncertain condition is `DENY` or `UNKNOWN`, never promoted by retry, majority, prior success, or unused capacity.

## 281. IAP-EV-004 — Exact Artifact and Scope Binding

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-023 IAP-AC-004
- **Injection:** Substitute account, instrument, direction, quantity, unit, price, Capsule, venue decision, construction envelope, candidate command, broker, route, environment, policy, software, deployment, or generation after request or decision.
- **Expected:** Every mismatch is rejected; no narrower approval, alias, default, or later favorable input can authorize the changed action.

## 282. IAP-EV-005 — Single-Use Intent Consumption

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-023 IAP-AC-005
- **Injection:** Race concurrent Intent Registry writers and consumers; replay identical and conflicting commands; restore an old database; reuse the decision across scopes and Intent identities.
- **Expected:** At most one exact immutable Intent and authoritative Consumption Record exist; identical duplicate commands are idempotent, conflicts and stale writers are fenced.

## 283. IAP-EV-006 — No Widening or Authority Escalation

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-023 IAP-AC-006
- **Injection:** Union decisions, widen scope after approval, request capacity mutation, classify protection, issue authority/capability, clear HALT, re-arm, or transmit from approval and Intent Registry identities.
- **Expected:** Every escalation and direct route fails; later gates may only narrow or deny and exclusive authority ownership remains intact.

## 284. IAP-EV-007 — Invalidation Dependency Closure

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-023 IAP-AC-007
- **Injection:** Correct inputs, change policy/generation/software/deployment/route, discover common mode or compromise, and invalidate before decision, during consumption, after Intent creation, and before send.
- **Expected:** Complete affected dependency closure is denied before future new-risk use while any possible prior broker/economic effect remains explicit and capacity-covered.

## 285. IAP-EV-008 — Active Final-Egress Currentness

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-023 IAP-AC-008
- **Injection:** Present cached, stale, invalidated, unconsumed, multiply consumed, wrong-Intent, wrong-generation, over-age, or unavailable approval lineage; delay invalidation across claim/first-byte boundaries.
- **Expected:** Egress actively proves exact current lineage without cache/TTL/heartbeat inference; ambiguity denies send and any raced attempt remains potentially live, capacity-covered, and non-retryable without proof.

## 286. IAP-EV-009 — UNKNOWN, Protective, and Human Confinement

- **Minimum Level:** EV-L1/EV-L3 plus broker assessment
- **Supports:** ADR-002-023 IAP-AC-009
- **Injection:** Combine UNKNOWN approval with unused capacity, human approval, emergency/exit/hedge/reduce-only/protective labels, queue priority, or expected broker rejection.
- **Expected:** Ordinary new risk remains blocked; labels and humans create neither automated approval nor protective classification/reserve, and only separately authorized complete protective flow may proceed.

## 287. IAP-EV-010 — Partition and Stale-Generation Fencing

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-023 IAP-AC-010
- **Injection:** Partition proposer/approval/registry/currentness planes while broker egress remains reachable; resume stale evaluator, writer, deployment, recovery, authority, and egress generations.
- **Expected:** No stale decision is consumed or transmitted; predecessors remain potentially active until hard fenced and unavailable currentness denies new risk.

## 288. IAP-EV-011 — Economic Continuity and Broker Ambiguity

- **Minimum Level:** EV-L1/EV-L3 plus broker assessment
- **Supports:** ADR-002-023 IAP-AC-011
- **Injection:** Expire, revoke, deny, or invalidate approval after send; lose ACK; receive cancel ACK without Final Quantity Proof; restart while order state is UNKNOWN.
- **Expected:** Future permission is denied but order/exposure/UNKNOWN state and conservative RCL coverage remain; no blind retry or approval-driven capacity release occurs.

## 289. IAP-EV-012 — Recovery, Evidence, and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-023 IAP-AC-012
- **Injection:** Restart, restore, roll back, replay, recover sources/policy/approval/registry/evidence, and reproduce an identical historical result while prior effects or generations remain.
- **Expected:** Historical artifacts remain evidence only; no auto-consumption, permission revival, capacity release, broker transmission, or automatic re-arm occurs.

---

# Part XXIV — Active Currentness and Final-Egress Admission Evidence

## 290. CUR-EV-001 — Complete Exact Vector

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-024 CUR-AC-001
- **Injection:** Omit, wildcard, default, mix, stale, conflict, or substitute each owner generation, artifact, restrictive floor, scope, dependency, command, attempt, principal, route, and session dimension.
- **Expected:** No partial or mixed vector produces `CURRENT`; unknown materiality or closure expands scope and denies admission.

## 291. CUR-EV-002 — Restrictive Fence Dominance

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-024 CUR-AC-002
- **Injection:** Order HALT, revocation, input/constraint/conformance/risk/flow/approval invalidation, policy reduction, owner compromise, and newer generation before and during competing claims.
- **Expected:** Every fence ordered before claim denies; older permissive artifacts, vectors, proofs, priority, and cached state cannot cross the new floor.

## 292. CUR-EV-003 — Independent Local Deny

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-024 CUR-AC-003
- **Injection:** Deliver credible authenticated restriction or currentness loss to final egress while quorum, proposer, approval, normal authority, publisher acknowledgement, and evidence store are unavailable; restart or fail over the egress.
- **Expected:** The Local Restrictive Latch transitions to `DENY_LATCHED` before later claims, survives restart/failover under its generation, remains `DENY_LATCHED` without global confirmation, and creates no permission.

## 293. CUR-EV-004 — Per-Send Proof and No Cache

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-024 CUR-AC-004
- **Injection:** Attempt multiple sends using one proof, cached vector, currentness session, TTL, heartbeat, health, last-known generation, prior success, or absence of invalidation.
- **Expected:** Each send requires one new exact proof ordered with its claim; replay, cache, and inference paths are rejected.

## 294. CUR-EV-005 — Claim, Fence, and First-Byte Race

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-024 CUR-AC-005
- **Injection:** Exercise every fence/claim/`SEND_STARTED`/local-latch/first-byte order, lose each response, crash each participant, delay proxies and sessions, and suppress broker ACK.
- **Expected:** Pre-claim fences deny; earlier or ambiguous claims remain potentially live and capacity-covered; no timeout, retry, or missing evidence creates permission or release.

## 295. CUR-EV-006 — Partition with Broker Reachability

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-024 CUR-AC-006
- **Injection:** Keep broker credential, route, and session usable while partitioning currentness quorum, owner proof, restrictive ingress, RCL, capability issuer, or final egress from one another.
- **Expected:** No normal send occurs without complete positive proof and ordered claim; broker reachability, local cache, and session health do not preserve authority.

## 296. CUR-EV-007 — Stale Generation and Restore Fence

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-024 CUR-AC-007
- **Injection:** Resume old owner, sequencer, writer, cluster, restored database, deployment, credential, signer, route, session, and egress principal after each newer generation.
- **Expected:** Every predecessor is rejected and remains potentially active until hard fenced; no old identity creates or consumes a current vector/proof.

## 297. CUR-EV-008 — Multi-Domain and Shared Scope

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-024 CUR-AC-008
- **Injection:** Race parent/child and cross-domain actions, omit shared limits, union narrow proofs, split scope during claim, fail one participant, and attempt best-effort compensation.
- **Expected:** One complete domain or proven serializable barrier orders the action; otherwise admission is denied without proof union or double use.

## 298. CUR-EV-009 — Authority and Capacity Separation

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-024 CUR-AC-009
- **Injection:** Use Currentness Policy, sequencer, vector, fence, proof, latch, evidence, replay, or administrator identities to approve, create Intent, mutate/release RCL capacity, classify protection, issue authority/capability, transmit, clear HALT, or re-arm.
- **Expected:** Every escalation and direct route fails; RCL and final egress retain their sole authorities and currentness remains non-authorizing.

## 299. CUR-EV-010 — UNKNOWN and Economic Continuity

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-024 CUR-AC-010
- **Injection:** Lose claim, proof, send, ACK, broker query, order, fill, exposure, currentness, and cancellation evidence; expire or invalidate every currentness artifact after possible effect.
- **Expected:** New risk stops, worst credible effect remains capacity-covered, missing ACK is not non-acceptance, cancel ACK is not Final Quantity Proof, and expiry releases nothing.

## 300. CUR-EV-011 — Protective Confinement

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-024 CUR-AC-011
- **Injection:** Combine priority and protective/exit/hedge/reduce-only labels with missing normal currentness, absent protective lease, exhausted capacity/flow reserve, stale admissibility, or unavailable conformance.
- **Expected:** Labels and priority create no reserve or authority; only the exact pre-issued complete protective path may proceed, otherwise exposure is trapped and contained.

## 301. CUR-EV-012 — Recovery, Evidence, and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-024 CUR-AC-012
- **Injection:** Restart, reconnect, fail over, restore, replay, recover quorum/time/health/owners/evidence, reconstruct an identical vector, and drain old queues or sessions.
- **Expected:** Old vectors, proofs, capabilities, claims, latches, permissions, and live state do not revive; recovery remains non-live until fresh governed re-arm.

---

# Part XXV — Restricted-Live Trial and Production-Promotion Evidence

## 302. RLP-EV-001 — Exact Pre-Registered Scope

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-025 RLP-AC-001
- **Injection:** Omit, wildcard, default, patch, union, stale, conflict, substitute, or change after review every environment, Safety Cell, account, broker, venue, instrument, strategy, action, order, software, configuration, identity, route, session, time, evidence, and failure-domain scope dimension.
- **Expected:** The plan remains `INELIGIBLE`; no trial authorization, action, evidence validity, promotion eligibility, or production scope is created.

## 303. RLP-EV-002 — Worst-Credible Effect and RCL Separation

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-025 RLP-AC-002
- **Injection:** Exercise full, partial, duplicate, reordered, delayed, missing-ACK, cancel/replace, reversal, external, protective, abort-latency, recovery, and concurrent shared-scope effects while attempting to use Trial Budget as capacity or headroom.
- **Expected:** The worst credible union remains inside RCL-committed capacity; Trial Budget never mutates or releases capacity and UNKNOWN never creates permission.

## 304. RLP-EV-003 — No Trial Safety Bypass

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-025 RLP-AC-003
- **Injection:** Label actions canary, low-notional, supervised, expected-rejection, priority, evidence-only, or restricted-live and omit each ordinary approval, conformance, risk, flow, capacity, authority, currentness, and final-egress prerequisite.
- **Expected:** Every omission denies the action; no trial flag or evidence goal bypasses a normal control or creates protective capacity or authority.

## 305. RLP-EV-004 — Abort Dominance and Race

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-025 RLP-AC-004
- **Injection:** Race invariant failure, scope drift, bound breach, evidence loss, external activity, currentness loss, HALT, abort, capability claim, `SEND_STARTED`, first byte, ACK loss, crash, restart, and delayed queue/session delivery.
- **Expected:** Restriction dominates every later action; ambiguous attempts remain potentially live and capacity-covered; no continuation, blind retry, timeout, or recovery restores the run.

## 306. RLP-EV-005 — Evidence Completeness and Negative-Result Retention

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-025 RLP-AC-005
- **Injection:** Remove, alter, delay, select, redact, supersede, or hide failed, aborted, inconclusive, contradictory, fault, broker, capacity, and operator records; change metrics or stopping rules after start.
- **Expected:** The package remains `INVALID`; missing or selected evidence and post-hoc rules cannot produce PASS or promotion eligibility.

## 307. RLP-EV-006 — Coverage and Non-Extrapolation

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-025 RLP-AC-006
- **Injection:** Reuse evidence across broker, account, venue, instrument, strategy, action, order type, credential, route, session, version, failure domain, concurrency, or market regime; union several narrow packages.
- **Expected:** Unknown equivalence is non-equivalence; evidence covers only the exact exercised scope and a combined scope requires its own evidence.

## 308. RLP-EV-007 — Progressive Single-Use Promotion

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-025 RLP-AC-007
- **Injection:** Skip a promotion step, widen a delta, union decisions, replay or partially consume a decision, auto-chain on counters/P&L/time/incident absence, or treat eligibility as activation or live authority.
- **Expected:** Every path is rejected; one exact decision is consumed once only to request a new non-live configuration and fresh governed authorization chain.

## 309. RLP-EV-008 — Independent Governance and Authority Separation

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-025 RLP-AC-008
- **Injection:** Collapse proposer, implementer, operator, evidence producer, reviewer, promoter, configuration approver, armer, and egress administrator into one effective principal; give trial or promotion services capacity or broker-route authority.
- **Expected:** Effective-principal and role conflicts deny promotion; trial components cannot mutate RCL, activate configuration, issue authority, transmit, clear HALT, or re-arm.

## 310. RLP-EV-009 — Expiry and Economic Continuity

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-025 RLP-AC-009
- **Injection:** Expire, abort, invalidate, consume, revoke, or supersede plans, runs, evidence, promotion decisions, profiles, and authorizations after possible broker effect; lose ACK and receive cancel ACK without Final Quantity Proof.
- **Expected:** Future use is denied while orders, fills, positions, UNKNOWN state, obligations, and conservative RCL coverage remain; no expiry authorizes retry or release.

## 311. RLP-EV-010 — Restart, Recovery, and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-025 RLP-AC-010
- **Injection:** Restart, fail over, reconnect, restore, roll back, replay, reconcile, recover time/broker/monitoring/operator paths, resume old queues, and reproduce identical prior artifacts.
- **Expected:** The prior run and consumable artifacts remain invalid and fenced; no resume, promotion reuse, queued action, scope revival, or automatic re-arm occurs.

## 312. RLP-EV-011 — Continuous Conformance and Demotion

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-025 RLP-AC-011
- **Injection:** Drift software, configuration, profile, broker semantics, route, identity, session, generation, capacity, action-flow, protection, evidence, currentness, and monitoring while attempting to preserve or automatically restore production scope.
- **Expected:** Affected evidence and future authority are restricted or demoted; recovery cannot restore scope without fresh evidence, configuration, reconciliation, and authorization.

## 313. RLP-EV-012 — Gate Honesty and Status Separation

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-025 RLP-AC-012
- **Injection:** Treat EV-L0 review, ADR acceptance, plan eligibility, deployed code, trial start, trial completion, package creation, EV-L5 review, promotion eligibility, configuration activation, dashboard state, or incident-free time as another gate or as live readiness.
- **Expected:** Every state remains distinct and explicit; no documentary, evidentiary, deployment, or governance state creates capacity, authority, transmission, restricted-live readiness, or production readiness.

---

# Part XXVI — Safety Waiver, Deviation, and Residual-Risk Evidence

## 314. WDR-EV-001 — Non-Waivable Boundary

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-026 WDR-AC-001
- **Injection:** Request deviations from RFC-000, RFC-001's prohibited set, RCL exclusivity, final-egress enforcement, UNKNOWN conservatism, broker-finality semantics, economic continuity, stale-generation fencing, segregation, independent HALT, evidence honesty, and no-auto-rearm.
- **Expected:** Every request is deterministically denied before configuration eligibility; no quorum, emergency path, policy change, or scope reduction can approve it.

## 315. WDR-EV-002 — Exact Scope and Dependency Closure

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-026 WDR-AC-002
- **Injection:** Omit or wildcard an account, broker, strategy, action, software, route, failure domain, requirement, hazard, shared dependency, or active deviation; patch, widen, substitute, or union narrow decisions after review.
- **Expected:** Incomplete or non-canonical scope and dependency closure is denial; no local union or post-review mutation becomes eligible or active.

## 316. WDR-EV-003 — Compensating-Control Effectiveness

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-026 WDR-AC-003
- **Injection:** Offer documentation, monitoring, alerting, operator presence, priority, expected rejection, capacity reservation, or a control sharing the failed control's dependency as the sole compensation; then fail that compensation.
- **Expected:** Observational, permissive, unknown, or common-mode-only compensation is rejected; loss of an accepted control restricts the complete dependency closure.

## 317. WDR-EV-004 — Independent Effective-Person Approval

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-026 WDR-AC-004
- **Injection:** Use one natural person through multiple accounts, shared administrators, delegated identities, device/recovery paths, requester-reviewer role aliases, or a compromised workflow to satisfy the approval quorum.
- **Expected:** Effective Principal collapse and conflicts prevent self-approval; unresolved identity or administrative common mode is denial.

## 318. WDR-EV-005 — Non-Authorizing Single-Use Activation

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-026 WDR-AC-005
- **Injection:** Replay, duplicate-consume, partially consume, union, or present a request, decision, acceptance record, ticket, or active-set artifact directly to configuration, RCL, authority, protection, or egress.
- **Expected:** Artifacts create no capacity or authority; only one exact eligible decision may request separate restricted configuration once, and all later gates remain mandatory.

## 319. WDR-EV-006 — Currentness, Revocation, and Send Race

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-026 WDR-AC-006
- **Injection:** Cache old policy, control, decision, active-set, configuration, or Deviation Generation state; partition the workflow while broker egress remains reachable; race revocation or expiry against claim, `SEND_STARTED`, and first byte.
- **Expected:** Stale or unproven currentness denies later send; ambiguous attempts remain potentially live, capacity-covered, and non-retriable without fresh proof.

## 320. WDR-EV-007 — UNKNOWN, Capacity, and Protective Confinement

- **Minimum Level:** EV-L1/EV-L3 plus broker assessment
- **Supports:** ADR-002-026 WDR-AC-007
- **Injection:** Make applicability, residual risk, broker/order/exposure/control/evidence/currentness unknown while capacity is reserved or the action is labelled protective, priority, exit, hedge, or emergency.
- **Expected:** New risk remains denied, worst-credible possible effect remains capacity-covered, and no label, priority, or reserve creates permission or executability.

## 321. WDR-EV-008 — Broker Finality and Economic Continuity

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-026 WDR-AC-008
- **Injection:** Lose submission ACK, receive Cancel ACK without Final Quantity Proof, partially fill, late-fill, correct, bust, revoke, expire, or roll back the deviation-dependent configuration while attempting retry or capacity release.
- **Expected:** Missing ACK remains potentially accepted, Cancel ACK remains non-final, economic effect survives artifact expiry, and only proof-gated RCL transitions release capacity.

## 322. WDR-EV-009 — Expiry, Renewal, Recovery, and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-026 WDR-AC-009
- **Injection:** Expire or revoke a deviation, then restart, reconnect, fail over, restore, roll back, replay, repair evidence, recover time/workflow/reviewer state, reconcile, silently renew, or restore a predecessor profile.
- **Expected:** Dependent scope stays restricted; prior artifacts remain fenced and no renewal, rollback, recovery, or reconciliation restores permission or automatically re-arms.

## 323. WDR-EV-010 — Evidence and Status Honesty

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-026 WDR-AC-010
- **Injection:** Relabel failed, missing, inconclusive, blocked, expired, or waived evidence as `PASS`, hide negative history, use a review or incident-free period as completion, or delete a superseded residual-risk record.
- **Expected:** Exact non-PASS status and history remain durable; documentation, audit, replay, review, and incident absence create no verification completion or authority.

## 324. WDR-EV-011 — Security, Alternate Route, and Emergency Behavior

- **Minimum Level:** EV-L2/EV-L3 plus security and broker assessment
- **Supports:** ADR-002-026 WDR-AC-011
- **Injection:** Compromise or disable the deviation registry/workflow, give it a broker credential or route, use break-glass or a broker portal, suppress revocation, or attempt a post-hoc deviation for an external action.
- **Expected:** Workflow loss restricts rather than broadens scope; no deviation identity bypasses final egress, external action remains external, and break-glass remains restrictive-only.

## 325. WDR-EV-012 — Combined Deviations and Gate Separation

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-026 WDR-AC-012
- **Injection:** Activate interacting individually approved deviations without combined analysis and treat ADR acceptance, decision eligibility, residual-risk acceptance, configuration activation, live authorization, restricted-live review, or production review as interchangeable.
- **Expected:** One canonical combined Active Deviation Set and reduced scope are required; every governance, evidence, configuration, authority, and readiness state remains distinct and non-authorizing.

---

# Part XXVII — Safety Incident and Controlled-Shutdown Evidence

## 326. SIR-EV-001 — Restrictive Detection and Declaration

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-027 SIR-AC-001
- **Injection:** Delay confirmation, ticket creation, severity review, responder assignment, or ordinary control-plane workflow after a credible, conflicting, ambiguous, suppressed, or unclassified material signal.
- **Expected:** The greatest credible affected scope becomes restrictive before administrative coordination; declaration creates no capacity, authority, protection, transmission, readiness, closure, or re-arm permission.

## 327. SIR-EV-002 — Exact Scope and Combined Incidents

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-027 SIR-AC-002
- **Injection:** Omit a shared account, Capacity Domain, broker session, credential, route, failure domain, protection, evidence path, parent, child, overlap, or common cause; present separate narrow incidents or a favorable subset.
- **Expected:** Scope expands to the greatest credible dependency closure and one canonical Active Safety Incident Set; no local exemption, subset, child closure, or union creates permission.

## 328. SIR-EV-003 — Containment Authority Separation

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-027 SIR-AC-003
- **Injection:** Present severity, incident priority, commander approval, a Containment Plan, or an emergency label directly to the RCL, Protective Action Controller, authority issuer, alternate broker route, or final egress.
- **Expected:** Incident artifacts coordinate only; every action retains its normal classifier, RCL, authority, currentness, venue, and final-egress gates, and no incident identity gains economic authority.

## 329. SIR-EV-004 — Controlled Shutdown and Hard Fencing

- **Minimum Level:** EV-L3 plus broker and security assessment
- **Supports:** ADR-002-027 SIR-AC-004
- **Injection:** Stop strategy/processes, scale workloads to zero, close sockets, revoke a credential, delete a queue, or mark deployment shutdown while a stale principal, signer, proxy, session, route, or broker effect may remain.
- **Expected:** Denial precedes stop, former paths remain potentially active until independently hard fenced, queued work is rejected rather than drained by sending, and shutdown state is never broker-finality proof.

## 330. SIR-EV-005 — Protection and Ongoing Obligations

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-027 SIR-AC-005
- **Injection:** Request cancel-all, blanket liquidation, component stop, retention cleanup, or ownership transfer while required protection, trapped exposure, settlement, reconciliation, evidence, notification, or recovery obligations remain.
- **Expected:** Required safety functions and obligations are preserved or transferred through a proven break-before-make handoff; no blind cancellation, liquidation, abandonment, or false closed state occurs.

## 331. SIR-EV-006 — UNKNOWN, Broker Finality, and Capacity

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-027 SIR-AC-006
- **Injection:** Lose submission ACK, receive Cancel ACK without Final Quantity Proof, omit an order from a query, observe partial or late fill, or expire incident, plan, task, authority, credential, session, or evidence state during shutdown and closure.
- **Expected:** Unknown effects remain potentially live and capacity-covered; no expiry, acknowledgement, process state, or administrative state proves non-acceptance, Final Quantity, or capacity release.

## 332. SIR-EV-007 — Incident Currentness and Send Race

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-027 SIR-AC-007
- **Injection:** Cache or replay old policy, Incident Generation, Active Safety Incident Set, scope, plan, closure, or handoff; race declaration or scope expansion against capability claim, `SEND_STARTED`, and first byte.
- **Expected:** Stale or unproven incident currentness denies later send; ambiguous attempts remain potentially live, capacity-covered, and ineligible for blind retry.

## 333. SIR-EV-008 — Partition, Common Mode, and Compromise

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-027 SIR-AC-008
- **Injection:** Partition or compromise signal, registry, coordinator, notification, evidence, signer, closure, or active-set services while broker egress remains reachable; restore a stale database or coordinator.
- **Expected:** The union of possibly affected scope remains restricted, local latches and hard fences dominate, stale owners are rejected, and no alternate credential or route becomes available.

## 334. SIR-EV-009 — Evidence, Communication, and Status Honesty

- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-027 SIR-AC-009
- **Injection:** Treat a ticket, page, chat acknowledgement, dashboard, timeline, root-cause report, postmortem, replay match, quiet interval, or incident-free period as restriction delivery, broker finality, prevention evidence, closure, or readiness.
- **Expected:** Observations and administrative artifacts retain their exact non-authorizing meaning; enforcement, finality, currentness, verification completion, and readiness require their separate proofs.

## 335. SIR-EV-010 — Independent Non-Permissive Closure

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-027 SIR-AC-010
- **Injection:** Use one Effective Principal across detector, service owner, remediator, evidence producer, closer, and live armer; close with stale generation, unresolved gap, open shared incident, or ongoing effect; present closure to HALT, RCL, Recovery Barrier, configuration, or egress.
- **Expected:** Closure is denied unless exact current independent conditions hold and, even when recorded administratively, clears nothing, releases nothing, marks no evidence `PASS`, and grants no permission.

## 336. SIR-EV-011 — External Activity and Demotion

- **Minimum Level:** EV-L2/EV-L3 plus broker and security assessment
- **Supports:** ADR-002-027 SIR-AC-011
- **Injection:** Use a broker portal or alternate manual route for emergency action, rewrite it as compliant, create a post-hoc deviation, or demote to a historically proven narrower production scope without fresh configuration, isolation, reconciliation, and authority.
- **Expected:** Manual effects remain external and conservatively reconciled; no post-hoc authorization occurs and demotion remains restrictive, non-authorizing, and break-before-make.

## 337. SIR-EV-012 — Recovery and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-027 SIR-AC-012
- **Injection:** Restart, reconnect, restore, roll back, deploy remediation, repair evidence, replay, reconcile, recover time/quorum/monitoring/workflow, accept handoff, close the incident, or return an operator while old work, trial, production scope, authority, or latch exists.
- **Expected:** The Recovery Barrier remains closed until its own gate passes; no prior work, scope, authority, proof, capability, or permission revives and no automatic re-arm occurs.

---

# Part XXVIII — Safety Telemetry, Continuous-Conformance, and Alert-Escalation Evidence

## 338. STM-EV-001 — Complete Critical Coverage

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-028 STM-AC-001
- **Injection:** Omit, wildcard, optionalize, patch, partially refresh, or consumer-union one requirement, hazard, control, bound, environment, account, broker, source, dependency, restrictive path, alert path, or currentness dimension while claiming broad coverage.
- **Expected:** Coverage remains incomplete and UNKNOWN, one Monitoring Gap covers the greatest credible scope, dependent new risk is denied, and no count, percentage, dashboard, or favorable manifest union creates conformance or permission.

## 339. STM-EV-002 — Provenance, Continuity, Semantics, and Time

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-028 STM-AC-002
- **Injection:** Restart or replace a publisher, reset sequence, swap endpoint or credential, restore history, change schema, unit, sign, scale, mapping, derivation, aggregator, clock, or receipt anchor while retaining the old source identity and freshness history.
- **Expected:** A new continuity fact or explicit gap is mandatory; identical or cached payloads cannot bridge the discontinuity, ambiguity is restrictive, and stale semantics cannot remain current.

## 340. STM-EV-003 — UNKNOWN, Silence, and Stale Green State

- **Minimum Level:** EV-L2/EV-L3
- **Supports:** ADR-002-028 STM-AC-003
- **Injection:** Freeze or remove telemetry while preserving heartbeat, collector health, empty queries, last-known values, a green dashboard, quiet time, TTL, or absence of an invalidation or alert.
- **Expected:** Silence and health metadata prove neither completeness nor safety; the state becomes UNKNOWN or a Monitoring Gap, dependent new risk is denied, and no cached green result survives.

## 341. STM-EV-004 — Effective Independence and Common Mode

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-028 STM-AC-004
- **Injection:** Corrupt one shared source, collector, parser, schema registry, clock, datastore, message bus, network, administrator, identity, deployment, notification provider, or upstream fact behind nominally separate monitors.
- **Expected:** Shared paths count as one common mode, independent coverage is not claimed, the residual becomes a restrictive gap or scope reduction, and no majority of correlated outputs creates a favorable result.

## 342. STM-EV-005 — Deterministic Evaluation and Bound Integrity

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-028 STM-AC-005
- **Injection:** Exercise threshold boundaries, hysteresis, debounce, grace, units, signs, precision, NaN, infinity, overflow, underflow, empty windows, missing history, parser differential, policy-generation change, percentile substitution, and local permissive defaults.
- **Expected:** Identical exact inputs produce one policy-bound result; numeric or semantic ambiguity is UNKNOWN or restrictive, hard maxima retain their exact semantics, and no local optimization weakens the approved failure response.

## 343. STM-EV-006 — Suppression and Maintenance Safety

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-028 STM-AC-006
- **Injection:** Apply broad, wildcard, stale, expired, unapproved, self-approved, replayed, conflicting, or unavailable suppression and maintenance state during a Critical violation.
- **Expected:** Underlying collection, evaluation, gap creation, restriction, incident signaling, evidence, escalation, and final-egress denial remain active; uncertainty is restrictive and suppression recovery or expiry never auto-resumes scope.

## 344. STM-EV-007 — Alert Correlation, Delivery, and Escalation

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-028 STM-AC-007
- **Injection:** Cause duplicate, fan-out, retry, out-of-order, wrong-recipient, stale-roster, dedup-collision, queue-overflow, backpressure, provider-outage, delivery-loss, acknowledgement-loss, and responder-timeout behavior across distinct scopes and causes.
- **Expected:** Distinct scope, lineage, first occurrence, deadlines, and restrictive state are preserved; adverse facts are not sampled away, delivery ambiguity keeps restriction and escalates, and acknowledgement or ticket closure proves no containment or resolution.

## 345. STM-EV-008 — Restrictive and Incident Handoff

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-028 STM-AC-008
- **Injection:** Fail or compromise the ordinary monitor, dashboard, alert, notification, or control-plane path during a material violation and attempt to make monitor severity directly mutate RCL, classify protection, clear a latch, declare a favorable incident scope, or call a broker route.
- **Expected:** An independently available restrictive request and exact authenticated signal reach ADR-002-024/027 owners; monitoring gains no economic, incident, closure, or broker authority and cannot downgrade an existing restriction.

## 346. STM-EV-009 — Active Currentness and Send Race

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-028 STM-AC-009
- **Injection:** Cache or replay old policy, manifests, conformance snapshot, gap state, suppression, or Monitor Generation; partition monitoring while egress remains broker-reachable; race a material gap or invalidation against capability claim, `SEND_STARTED`, and first byte.
- **Expected:** Final egress actively rejects stale, missing, conflicting, or unproven monitoring currentness; a prior green result is insufficient and ambiguous attempts remain potentially live, capacity-covered, and ineligible for blind retry.

## 347. STM-EV-010 — UNKNOWN, Broker Finality, and Economic Continuity

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-028 STM-AC-010
- **Injection:** Lose submission ACK, receive Cancel ACK without Final Quantity Proof, lose broker-state monitoring, expire telemetry/alerts/suppressions, observe available capacity, or mark a dashboard flat while broker effect remains possible.
- **Expected:** Monitoring changes no broker-finality rule or economic lifetime; UNKNOWN remains capacity-consuming, RCL alone mutates capacity, priority is not reserve, and no monitor or alert state creates new-risk permission.

## 348. STM-EV-011 — Compromise, Fencing, and Failure Domains

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-028 STM-AC-011
- **Injection:** Compromise or restore stale telemetry publishers, evaluators, policy/manifest registries, suppression service, dashboard, paging system, acknowledgement workflow, Monitor Generation owner, credential, or alternate route.
- **Expected:** The greatest credible shared scope is restricted, stale writers and consumers are fenced, histories remain visible, combined read/trade authority does not create bypass, and compromised components cannot attest their own recovery or clear state.

## 349. STM-EV-012 — Evidence, Recovery, and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-028 STM-AC-012
- **Injection:** Present a written case, registered item, dashboard, page, alert acknowledgement, quiet interval, replay match, source recovery, monitor failover, backlog drain, gap repair, operator return, or Recovery Readiness Decision as evidence completion or authority restoration.
- **Expected:** Documentation and observations do not replace prevention or executed evidence; the Recovery Barrier and prior restrictions remain until their own gates pass, old generations and snapshots remain invalid, and no automatic re-arm occurs.

---

# Part XXIX — Software Supply-Chain and Runtime Artifact Admission Evidence

## 350. SCI-EV-001 — Source Identity and Review Integrity

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-001
- **Injection:** Move a branch or tag after review; rewrite repository history; omit or substitute a submodule, generated source, large-file object, patch, build script, or policy identity; or present a favorable partial source tree as the reviewed revision.
- **Expected:** Only the exact immutable tree and complete source closure remain eligible; mutable names and incomplete lineage are `UNKNOWN` or denied, the greatest credible dependent scope is restricted, and no historical review creates admission or authority.

## 351. SCI-EV-002 — Build Isolation, Provenance, and Reproducibility

- **Minimum Level:** EV-L1/EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-002
- **Injection:** Change builder epoch, commands, environment, locale, time, randomness, secret input, network policy, or unpinned fetch; replay provenance for different bytes or scope; or create an independent/reproducible-build mismatch and select the favorable output.
- **Expected:** Provenance binds the exact recipe, builder, inputs, environment, and output digests but never self-admits them; unexplained nondeterminism or differential mismatch is restrictive and cannot be hidden by a valid attestation.

## 352. SCI-EV-003 — Dependency and Toolchain Closure

- **Minimum Level:** EV-L1/EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-003
- **Injection:** Omit, float, replace, or dynamically load a transitive library, plugin, build script, compiler, linker, SDK, code generator, base image, OS package, sidecar, proxy, signer component, or runtime module; compromise a dependency registry or lockfile.
- **Expected:** The exact transitive closure and resolver evidence are mandatory; undeclared, mutable, conflicting, unavailable, or unbounded resolution denies admission and runtime use, and shared corrupted dependencies cannot count as independent verification.

## 353. SCI-EV-004 — Signer, Key, and Attestation Compromise

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-004
- **Injection:** Collapse author, reviewer, builder, signer, registry, admission, deployment, configuration, and arming identities under one effective controller; compromise, revoke, roll back, or replay a signing key or attestation chain.
- **Expected:** Effective control and common modes are collapsed before independence is credited; signature authenticates exact bytes and origin only, stale or compromised key state restricts, and no signer or workflow gains admission, capacity, live, or broker authority.

## 354. SCI-EV-005 — Registry Custody and Artifact Substitution

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-005
- **Injection:** Move a mutable tag, select another platform manifest, replace a layer or blob, race scan/sign/download/deploy, restore a registry without later revocations, or serve bytes differing from those reviewed, signed, scanned, admitted, or attested.
- **Expected:** Retrieval and every transition use content identity and exact manifest closure; substitution and TOCTOU become restrictive, registry custody is not admission, restored stale state is fenced, and favorable tags or health cannot preserve eligibility.

## 355. SCI-EV-006 — Independent Admission and Compatibility

- **Minimum Level:** EV-L1/EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-006
- **Injection:** Treat CI, tests, SBOM, scan, signature, registry presence, deployment, canary, or health success as admission; patch, union, widen, or replay narrow decisions across account, environment, Safety Cell, platform, consumer, configuration, or broker scope.
- **Expected:** One exact current policy deterministically returns `ADMIT`, `DENY`, or `UNKNOWN` for the complete artifact and compatibility graph; only exact `ADMIT` is eligible for release-set commit, remains non-authorizing, and cannot be widened or composed permissively.

## 356. SCI-EV-007 — Release Generation and Stale Fencing

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-007
- **Injection:** Publish a stale, partial, mixed, patched, unioned, or favorably subsetted Admitted Release Set; resume a removed writer; roll back or restore registry state; or reuse a superseded Release Generation.
- **Expected:** One monotonic generation and one complete exact set govern overlapping scope; stale writers and consumers are hard fenced, uncertainty denies dependent new risk, and restore or rollback creates a new non-live generation rather than reviving admission.

## 357. SCI-EV-008 — Deployment Attestation and Environment Confinement

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-008
- **Injection:** Cross a non-live artifact into live scope; run bytes, plugins, sidecars, proxies, SDKs, signer components, platform variants, or dynamic modules different from desired or admitted state; preserve a stale broker-capable instance after replacement.
- **Expected:** Actual runtime bytes and workload/environment/Safety-Cell identity match one current attestation and admitted set; deployment labels and readiness are insufficient, drift restricts and fences, and deployment never self-arms or reaches the broker outside final egress.

## 358. SCI-EV-009 — Mixed Version, Promotion, Rollback, and Restore

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-009
- **Injection:** Mix old and new schema, protocol, migration, serializer, SDK, risk logic, verifier, configuration, or egress versions; apply emergency hotfix or historical rollback; restore a previously admitted artifact while retaining old activation or authority.
- **Expected:** Every compatibility edge and safety-dominance claim is exact and positive; unknown combinations are incompatible, change creates a new generation and non-live admission path, and no prior approval, activation, promotion, or authorization revives.

## 359. SCI-EV-010 — Active Currentness, Revocation, Partition, and Send Race

- **Minimum Level:** EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-010
- **Injection:** Delay or lose vulnerability, compromise, correction, revocation, drift, or generation restriction; partition the supply-chain plane while egress remains broker-reachable; race restriction against capability claim, `SEND_STARTED`, and first byte; or rely on cached admission, TTL, heartbeat, health, or absence of revocation.
- **Expected:** Authority and final egress actively prove exact current release facts and deny missing or stale state; ambiguous attempts remain potentially live, capacity-covered, and ineligible for blind retry, and a broker-reachable partition creates no bypass.

## 360. SCI-EV-011 — Authority Separation, Broker Finality, and Economic Continuity

- **Minimum Level:** EV-L2/EV-L3 plus broker and security assessment
- **Supports:** ADR-002-029 SCI-AC-011
- **Injection:** Give repository, builder, signer, registry, scanner, admission, deployment, or attestation identities RCL, Safety Authority, protective classification, live authorization, or broker route; expire or revoke software state while prior broker effect or UNKNOWN remains.
- **Expected:** Release artifacts are negative gates only; RCL and final egress remain exclusive, missing ACK is not non-acceptance, Cancel ACK is not Final Quantity Proof, software expiry or revocation never erases economic effect or releases capacity, and priority is not protective reserve.

## 361. SCI-EV-012 — Evidence, Recovery, Hotfix, and Non-Revival

- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-029 SCI-AC-012
- **Injection:** Present source review, signature, SBOM, scan, tests, reproducible build, provenance, registry log, deployment health, canary, replay, quiet monitoring, incident closure, evidence repair, restore, reconnect, or operator approval as completed evidence, release currentness, readiness, or authority restoration.
- **Expected:** Evidence remains evidence; recovery occurs behind the closed barrier, exact release state is reconstructed under a new generation, restrictions survive, written cases remain unexecuted, and no scope, admission, authority, capacity, or automatic re-arm is restored.

---

# Part XXX — Post-Trade Economic Obligation and Finality Evidence

## 362. PTF-EV-001 — Fill/FQP vs Post-Trade Obligation Separation

- **Minimum Level:** EV-L1/EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-030 PTF-AC-001
- **Injection:** Treat full or partial fill, trade capture, Final Quantity Proof, a closed order, or a flat position as proof that settlement, fee, tax, cash, collateral, borrow, custody, or legal-title obligations are final.
- **Expected:** Every economic obligation leg remains independently identified and conservatively covered; Final Quantity Proof proves only the broker-order quantity fact, and no order or position state releases post-trade capacity.

## 363. PTF-EV-002 — Fee/Tax/Interest/Financing Legs and Corrections

- **Minimum Level:** EV-L1/EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-030 PTF-AC-002
- **Injection:** Omit, net away, estimate favorably, duplicate, reverse, or correct a fee, tax, interest, financing, currency, rounding, or accrual leg after initial booking or apparent finality.
- **Expected:** Exact immutable obligation legs and versions are appended under policy; ambiguity and corrections retain worst-credible coverage, advance the Post-Trade Obligation Generation, and never create headroom by omission or favorable netting.

## 364. PTF-EV-003 — Settlement, Cash Availability, Partial/Failure Semantics

- **Minimum Level:** EV-L2/EV-L3 plus broker and custody assessment
- **Supports:** ADR-002-030 PTF-AC-003
- **Injection:** Present instruction acceptance, scheduled date, partial settlement, status text, quiet interval, or transfer acknowledgement as completed settlement or reusable cash; delay, fail, or reverse one leg.
- **Expected:** Instruction, settlement, cash availability, and custody finality remain orthogonal field-specific facts; partial/failure state is conservative, pending effect consumes capacity, and timeout or expiry proves neither non-acceptance nor finality.

## 365. PTF-EV-004 — Margin/Collateral/Encumbrance/Haircut/Double-Use

- **Minimum Level:** EV-L1/EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-030 PTF-AC-004
- **Injection:** Reuse pledged, pending, recalled, haircut-changed, cross-account, cross-currency, disputed, or stale collateral; count margin release before exact eligibility and settlement proof; apply favorable netting under conflict.
- **Expected:** Encumbrance, eligibility, haircut, location, legal owner, reuse, and release are exact current fields; unknown or conflicting collateral produces no benefit, consumes conservative capacity, and cannot be double-used.

## 366. PTF-EV-005 — Borrow/Recall/Return/Buy-In

- **Minimum Level:** EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-030 PTF-AC-005
- **Injection:** Treat locate, borrow confirmation, delivery, return request, recall acknowledgement, position close, or statement omission as borrow discharge; inject recall, forced buy-in, rate change, partial return, and contradictory lender/broker facts.
- **Expected:** Borrow, recall, return, financing, and buy-in obligations remain separate and conservatively covered; missing or conflicting evidence blocks affected new risk, and neither close nor acknowledgement releases the obligation.

## 367. PTF-EV-006 — Exercise/Assignment/Delivery/Corporate-Action Obligations

- **Minimum Level:** EV-L1/EV-L2/EV-L3 plus broker assessment
- **Supports:** ADR-002-030 PTF-AC-006
- **Injection:** Apply exercise, assignment, expiry, physical delivery, cash settlement, dividend, split, conversion, merger, or withholding as a fill or zero-risk event; deliver partial, corrected, or conflicting notices.
- **Expected:** Each resulting asset, cash, delivery, fee, tax, funding, and custody leg is independently identified under ADR-002-010 and PTOL; uncertainty preserves the greatest credible effect and no event, calendar, or favorable projection releases capacity.

## 368. PTF-EV-007 — Custody/Transfer/In-Flight/Legal-Title Behavior

- **Minimum Level:** EV-L2/EV-L3 plus custody and security assessment
- **Supports:** ADR-002-030 PTF-AC-007
- **Injection:** Treat an initiated, acknowledged, internally booked, externally visible, failed, reversed, or in-flight transfer as settled legal title or available inventory; substitute account, custodian, currency, asset, route, or beneficiary.
- **Expected:** Transfer instruction, acceptance, movement, custody receipt, legal title, availability, and reversal remain exact separate facts; ambiguity is capacity-consuming, and every external instruction uses the separately governed chain and final egress.

## 369. PTF-EV-008 — Statement Coverage, Provenance, Conflict/Common-Mode

- **Minimum Level:** EV-L1/EV-L2/EV-L3 plus broker and custody assessment
- **Supports:** ADR-002-030 PTF-AC-008
- **Injection:** Truncate pagination, omit account/subledger/date/class coverage, use preliminary or stale statements, reset continuity, replay a revision, select the favorable source, or claim independence where sources share parser, administrator, endpoint, or origin.
- **Expected:** Exact coverage, provenance, continuity, cutoff, revision, class, and completeness are positively established; missing or common-mode coverage remains UNKNOWN, cannot be silently unioned, and blocks affected new risk.

## 370. PTF-EV-009 — Breaks/Busts/Corrections/Reversal/Finality Reopen

- **Minimum Level:** EV-L2/EV-L3 plus broker and security assessment
- **Supports:** ADR-002-030 PTF-AC-009
- **Injection:** Bust, correct, reverse, rebook, cancel, dispute, or restate a previously matched or final field; overwrite prior facts, hide dependency fan-out, retain a stale proof, or release capacity before correction closure.
- **Expected:** Corrections append and advance generation, field-specific finality reopens over the complete dependency closure, prior evidence remains auditable, and RCL retains or expands conservative coverage until new positive proof supports a serialized transition.

## 371. PTF-EV-010 — RCL Transfer/Release + Generation Currentness/Send Race

- **Minimum Level:** EV-L2/EV-L3 plus broker and security assessment
- **Supports:** ADR-002-030 PTF-AC-010
- **Injection:** Race fill, obligation commit, PTOL transition, correction, RCL transfer/release, authority issuance, capability claim, `SEND_STARTED`, and first external byte; use a cached active set, proof, or Post-Trade Obligation Generation.
- **Expected:** PTOL serializes obligation lifecycle only and RCL alone mutates capacity; transitions are conservatively ordered with no gap or double release, stale or unprovable currentness denies, and ambiguous sends remain potentially live and capacity-covered without blind retry.

## 372. PTF-EV-011 — Partition/Compromise/Stale Writer/Route Bypass

- **Minimum Level:** EV-L3 plus broker, custody, and security assessment
- **Supports:** ADR-002-030 PTF-AC-011
- **Injection:** Partition PTOL, reconciliation, statement, RCL, authority, or final-egress planes while an external route remains reachable; resume a stale writer or restore; compromise a source, mapper, finality signer, operator, transfer credential, or route.
- **Expected:** Stale writers, proofs, authorities, and routes are hard fenced; absent current exact proof restricts the greatest credible scope, post-trade identities cannot mutate RCL or bypass final egress, and external reachability creates no permission.

## 373. PTF-EV-012 — Evidence/Recovery/Non-Revival/Status Honesty

- **Minimum Level:** EV-L2/EV-L3 plus broker and security assessment
- **Supports:** ADR-002-030 PTF-AC-012
- **Injection:** Present statements, matching balances, audit, monitoring, replay, break closure, service health, restore, quiet time, written cases, or registered evidence as finality, completed verification, capacity release, readiness, authority restoration, or re-arm.
- **Expected:** Evidence remains evidence and every case remains `NOT_IMPLEMENTED` until executed; recovery reconstructs exact obligations behind the closed barrier under a new generation, restrictions and economic effects survive, and no automatic re-arm or live-readiness claim occurs.

---

## 374. Model-Based and Property Verification

Before restricted live operation, the following state models SHALL be explored with model checking or equivalent exhaustive/bounded analysis:

- capacity reservation and release;
- quorum commit, committed-prefix durability, command idempotency, membership change, and restore generation;
- concurrent writer and epoch fencing;
- send/ACK/fill/cancel/replace ordering;
- Safety Authority failover and partition;
- degraded protective lease ownership;
- Trustworthy Time health, continuity, snapshot age, and recovery generation;
- Live Authorization, revocation generation, partial scope, and HALT precedence;
- orthogonal state dimensions, conservative direction, and transition ownership;
- field-level evidence confidence, conflict, freshness, and proof rules;
- failure-domain allocation, stale deployment, and Safety Cell containment;
- Egress Generation, active-principal, credential, route, session, Commit-Proof, hard-fence, and downstream-intermediary state;
- Hard Safety Envelope, Runtime Safety Profile, canonical bundle, approval, compatibility, Profile Generation, activation, restriction, expiry, rollback, and restore state;
- Human Authority Policy, Effective Principal Graph, Approval Request, attestation, quorum, Approval Set consumption, delegation, Human HALT, break-glass, compromise, and recovery state;
- Safety Evidence Envelope, Evidence Commit Receipt, source/store/key continuity, causal graph, integrity segment/anchor, Evidence Gap, retention, redaction, Replay Capsule, divergence, and recovery state;
- Recovery Barrier Policy, trigger, scope, Recovery Generation, owner epoch, session, Inventory Cut, obligation graph, package, readiness, invalidation, partial-scope, and handoff state;
- Critical Input Policy, source identity and continuity, observation, transformation lineage, consistency cut, Snapshot, Decision Context Capsule, common-mode analysis, correction, Context Generation, invalidation, and final-egress binding state;
- Venue Constraint Policy, Constraint Generation, Session Phase, tradability, exact order shape, Snapshot, Order Admissibility Decision, invalidation, final-egress currentness, and recovery state;
- Order Construction Policy, Authorized Construction Envelope, Canonical Broker Command, Economic Effect Envelope, Order Conformance Proof, Construction Generation, retry/split/replace lineage, downstream mutation, actual-outbound equivalence, and recovery state;
- Aggregate Risk Policy, Aggregate Risk Generation, Aggregate Risk State Snapshot, Adverse Scenario Set, dimension/scope vectors, projected state, benefit evidence, Aggregate Risk Decision, RCL admission, invalidation, final-egress currentness, and recovery state;
- Action Flow Policy, Action Flow Generation, Action Flow State Snapshot, cause lineage, amplification envelope, shared-scope resource vector, Action Flow Decision, RCL Permit allocation/claim/consumption/quarantine, protective reserve/lease, invalidation, final-egress currentness, and recovery state;
- Trading Approval Policy, Trading Approval Generation, Proposal Approval Request, independent/common-mode fact evaluation, Independent Approval Decision, Intent Registry writer and single-use consumption, immutable Intent binding, invalidation closure, final-egress currentness, and recovery state;
- Currentness Policy, owner/dependency closure, Safety Currentness Vector, restrictive floors, Restrictive Fence Record, Local Restrictive Latch, Egress Currentness Proof, capability/permit claim, `SEND_STARTED`, first-byte ordering, cross-domain barrier, and recovery state;
- Restricted-Live Trial Policy, exact Trial Plan and Run, effect/count/duration envelope, abort generation, evidence completeness, coverage, Promotion Generation, single-use Production Scope Promotion Decision, configuration handoff, demotion, and continuous-conformance state;
- Safety Deviation Policy, Non-Waivable Boundary, exact Request, dependency closure, compensating controls, effective-person quorum, Decision consumption, Residual-Risk Acceptance Record, Active Deviation Set, Deviation Generation, configuration binding, expiry, revocation, and recovery state;
- Safety Incident Policy, authenticated signals, severity/materiality, greatest-credible scope, dependency closure, Incident Generation, Active Safety Incident Set, lifecycle, containment, controlled shutdown, economic/protection obligations, recovery handoff, independent closure, currentness, and non-revival state;
- Safety Monitoring Policy, Critical Telemetry and Monitor Coverage Manifests, deterministic evaluators, Monitor Generation, Continuous Conformance Snapshot, Monitoring Gaps, suppressions, alerts, delivery, escalation, restrictive and incident handoff, currentness, and non-revival state;
- Software Release Policy, exact source revision, build recipe and provenance, dependency/toolchain closure, Release Artifact Manifest, independent admission, Release Generation, Admitted Release Set, deployment/runtime attestation, restriction, currentness, rollback, restore, and non-revival state;
- protective-replacement gap, overlap, and partial-fill interleavings;
- non-trade transition envelopes, correction, and event idempotency;
- startup recovery and re-arm;
- external activity and evidence conflicts.

Properties SHALL include:

```text
Potentially executable exposure <= committed capacity
No stale epoch can authorize new economic effect
UNKNOWN never transitions to RELEASED without proof
No two owners consume the same protective capacity
HALT cannot be reversed by an older capability
No live transmission bypasses capability and capacity validation
Issuer and consumer monotonic clocks are never directly compared across continuity identities
No restrictive time, revocation, or HALT generation is accepted after its egress containment bound
No check-then-send gap can outrun a restrictive generation at the irreversible send boundary
No non-permissive Live Authorization state returns to ACTIVE
No non-owner mutates a state dimension
No evidence conflict or staleness reduces a conservative bound
No shared failure is claimed as independent without evidence
No protective replacement step exceeds committed overlap or gap risk
No partial non-trade transition exposes a more permissive state
No minority, stale writer, stale read, snapshot, or restore can create capacity or transmission authority
No capability authorization or send claim precedes its exact quorum-committed capacity state
No identity outside the current Final Egress Trust Boundary can combine usable live-order authority with an accepted broker-order route
No leader receipt, local journal, stale proof, altered request, removed principal, or unfenced downstream intermediary can create broker effect
No credential rotation, egress failover, reconnect, or recovery can revive or overlap prior transmission authority
No partial, mixed, stale, incompatible, restored, or uncommitted safety configuration can create permission
No envelope expansion, profile recovery, expiry recovery, or Restrictive Override can silently expand or re-arm authority
No configuration transition can release capacity, erase economic effect, or turn UNKNOWN into permission
No account, credential, device, session, delegation, service identity, or recovery path makes one effective natural person count twice
No approval artifact, human session, or break-glass command creates capacity, Live Authorization, protective classification, or broker transmission authority
No stale, changed, expired, revoked, consumed, compromised, or recovered approval context creates permission or automatic re-arm
No Human HALT path requires a permissive quorum or permits a later stale generation to clear its restrictive effect
No evidence record, receipt, anchor, replay result, or incident report creates capacity, approval, Live Authorization, protective classification, transmission authority, or re-arm permission
No risk-increasing first broker byte precedes exact durable pre-effect and SEND_STARTED evidence
No missing, forked, truncated, conflicting, expired, redacted, or unsupported evidence produces a permissive or PASS result
No replay principal reaches a live credential, broker route, production mutation endpoint, live approval, or consumable authority
No retention, compaction, deletion, restore, or evidence recovery expires economic effect, releases capacity, clears UNKNOWN, or revives authority
No startup, restart, reconnect, failover, restore, or incident recovery begins with new-risk authority enabled
No stale, minority, restored, or competing Recovery Coordinator publishes usable readiness
No incomplete Inventory Cut, unresolved obligation, UNKNOWN, Evidence Gap, timeout, or retry produces READY
No READY_RESTRICTED scope excludes an unresolved shared capacity, broker, protection, authority, identity, configuration, or failure-domain dependency
No Recovery Evidence Package, Readiness Decision, operator action, health result, or replay result opens the barrier, mutates capacity, clears HALT, issues authority, or transmits
No stale Recovery Generation, invalidated readiness, or recovered prior artifact passes authority issuance or final egress
No unclassified safety-relevant input, unknown source continuity, unit/mapping ambiguity, hidden transformation, incompatible cut, or stale Critical Input creates new-risk permission
No shared source, parser, mapping, cache, administrator, deployment, or failure domain is counted as independent approval corroboration without evidence
No Capsule mutation, union, partial refresh, downgrade, substitution, or hidden recomputation survives proposal-to-egress exact binding
No correction, retraction, source/policy/mapping change, or input invalidation misses affected authority issuance or final egress beyond its approved bound
No context expiry, invalidation, restart, restore, recovery, or replay releases capacity, expires economic effect, revives authority, or automatically re-arms
No calendar, quote, recent trade, connection, login, broker health, cached state, TTL, or absence of restriction proves exact order tradability
No exit, reduce-only, cancellation, replacement, or protective label bypasses current exact venue, session, account, margin, settlement, and broker constraints
No Venue Constraint Snapshot or Order Admissibility Decision mutation, union, partial refresh, widening, substitution, or replay survives exact binding
No venue/session/halt/price/account/margin/borrow/settlement/capability invalidation misses affected authority or final egress beyond its approved bound
No venue reopen, halt release, broker reconnect, account restoration, constraint recovery, or replay revives a prior decision, authority, or live scope
No direction, position-effect, account, instrument, contract, route, unit, multiplier, currency, price, order, expiration, or operating-mode mutation survives Intent-to-order conformance
No hidden default, lossy conversion, permissive rounding, duplicate field, parser differential, SDK rewrite, signer mutation, redirect, or post-proof transformation reaches broker effect
No Economic Effect Envelope understates a credible full, partial, overlapping, split, reversal, or reduce-only-failure outcome or exceeds its exact RCL commitment
No retry, cancel, amend, replace, split, or aggregate command reuses stale proof, loses lineage, assumes missing ACK is non-acceptance, or treats cancel ACK as Final Quantity Proof
No compiler, serializer, SDK, cache, signer, route, restore, recovery, identical recompilation, or replay revives a prior proof, capability, authority, or live scope
No missing strategy, account, venue, instrument, order, commitment, external activity, trapped exposure, or concurrent action creates aggregate headroom
No omitted risk dimension, scenario truncation, scalar collapse, unit/sign/scope error, numerical failure, or unproven hedge/netting/correlation/margin benefit shrinks the conservative vector
No Aggregate Risk Decision mutation, union, partial refresh, widening, substitution, or replay survives exact effect-to-RCL binding
No aggregate-risk invalidation misses RCL admission or final egress beyond its approved bound
No evaluator, verifier, cache, model, restore, reconciliation, improved market state, or replay mutates capacity, revives a prior grant, or automatically re-arms
No local limiter, producer, scheduler, queue, SDK, retry, reconnect, replay, or failover path can exceed one complete shared action-flow vector
No duplicate event, changed cause identity, fan-out, redelivery, reconnect, cancel/replace loop, or replay exceeds its finite amplification envelope
No Action Flow Decision or Permit mutation, union, widening, substitution, double claim, or replay survives exact action-to-RCL-to-egress binding
No ordinary priority, queue position, broker connection, or local headroom consumes or proves Protective Flow Reserve
No action-flow invalidation misses RCL admission or final egress beyond its approved bound
No counter refill, backoff expiry, queue drain, broker recovery, restart, restore, or replay revives a permit, creates headroom, or automatically re-arms
No incomplete, patched, unioned, stale, unsupported, conflicting, or proposer-only approval request produces usable `APPROVE`
No shared source, parser, mapping, library, cache, registry, administrator, deployment, network, credential, or clock path is counted as independent without evidence
No Independent Approval Decision mutation, widening, replay, duplicate consumption, stale writer, or wrong-Intent binding creates a second or different Intent
No approval or Intent Registry identity mutates capacity, classifies protection, issues authority/capability, reaches the broker, clears HALT, or re-arms
No approval invalidation misses affected Intent registration or final egress beyond its approved bound
No approval expiry, denial, invalidation, recovery, restore, or replay erases possible economic effect, releases capacity, or revives authority
No incomplete, mixed, stale, conflicting, wrong-scope, or cached Safety Currentness Vector creates a per-send proof
No restrictive fence ordered before claim, or credible local restriction observed before first byte, permits the affected new-risk send
No TTL, heartbeat, health, currentness session, prior proof, or absence of invalidation substitutes for one new single-use Egress Currentness Proof
No currentness quorum or owner-proof loss with broker reachability permits a normal send
No currentness policy, sequencer, vector, fence, proof, latch, evidence, replay, or administrator mutates capacity or creates approval, authority, protection, transmission, HALT clear, or re-arm
No currentness expiry, claim ambiguity, missing ACK, cancel ACK, partition, restore, recovery, or replay releases economic capacity or revives permission
No trial policy, plan, review, run, dashboard, evidence package, coverage claim, or promotion decision creates capacity, authority, protection, transmission, HALT clear, resume, or re-arm
No omitted, wildcard, patched, unioned, stale, conflicting, wrong-scope, post-hoc, selected, or extrapolated trial evidence produces eligibility or promotion
No trial abort, evidence gap, UNKNOWN, drift, bound breach, expiry, recovery, or monitoring restoration permits later trial action or releases possible economic effect
No success count, elapsed time, P&L, incident absence, narrow package set, or promotion-decision replay automatically widens production scope
No signal delay, severity downgrade, incident subset, process shutdown, quiet time, closure, handoff, or remediation creates permission, broker finality, capacity release, scope restoration, or re-arm
No incident coordinator, plan, evidence, message, postmortem, or closure decision mutates RCL capacity, classifies protection, issues authority, transmits, clears HALT, or establishes recovery readiness
No controlled shutdown drains broker-bound work by sending, blindly cancels required protection, or treats process death as a hard fence
No omitted, wildcarded, patched, unioned, stale, conflicting, wrong-scope, semantically ambiguous, or common-mode-invalid monitor coverage produces `CONFORMING` or permission
No absent alert, green dashboard, heartbeat, successful scrape, quiet time, TTL, last-known value, or missing invalidation proves telemetry completeness or currentness
No schema, unit, sign, scale, time, sequence, derivation, threshold, window, parser, NaN, overflow, percentile, or local-default drift produces a favorable monitor result
No suppression, maintenance, deduplication, queue overflow, delivery failure, acknowledgement, ticket closure, or alert retirement disables a required restrictive path or proves containment
No monitoring policy, manifest, snapshot, gap, alert, page, dashboard, or escalation artifact mutates RCL, classifies protection, issues authority, reaches the broker, clears safety state, closes an incident, restores scope, or re-arms
No stale Monitor Generation, monitoring-plane partition, cached conformance, restore, recovery, replay, backlog drain, or operator return revives prior permission or automatically re-arms
No mutable source name, incomplete source closure, floating dependency, unpinned toolchain, undeclared runtime load, signature, scan, test, CI result, registry tag, deployment health, or canary creates artifact admission or live permission
No compromised, stale, revoked, substituted, mixed, incompatible, restored, or unattested software artifact survives Release Generation, authority, or final-egress currentness checks
No repository, builder, signer, registry, scanner, admission, deployment, or attestation identity mutates RCL, activates configuration, issues authority, transmits, clears safety state, restores scope, or re-arms
No software rollback, hotfix, restore, rebuild, evidence repair, monitoring recovery, or incident closure revives a prior admission, activation, capability, economic-state interpretation, or live scope
No fill, Final Quantity Proof, trade capture, statement, scheduled date, acknowledgement, flat position, or closed order proves any independent post-trade obligation final
No omitted, stale, conflicting, common-mode, corrected, partially settled, or in-flight fee, tax, cash, collateral, borrow, custody, transfer, delivery, or legal-title leg creates headroom or permission
No PTOL writer, finality proof, statement, reconciliation result, operator, evidence, replay, or recovery mutates RCL capacity, issues authority, or bypasses final egress
No obligation correction, break closure, statement arrival, cutoff, quiet time, restore, or Post-Trade Obligation Generation change erases economic effect, releases capacity by itself, revives authority, or automatically re-arms
```

Counterexamples SHALL be stored as evidence and converted into deterministic regression tests.

---

## 375. Fault-Injection Requirements

The test harness SHALL support controlled injection at least for:

- process kill and restart;
- pause/GC-like suspension;
- network partition by direction;
- message drop, duplicate, delay, and reorder;
- datastore leader failover;
- quorum loss, minority leader survival, joint membership change, removed-voter resume, and conflicting restore history;
- credential/session compromise, stale egress resume, signer and trust-bundle rollback, route/endpoint substitution, proof corruption, downstream replay, and hard-fence delay beyond `B_egress_hard_fence`;
- envelope/profile semantic mutation, omitted and unknown fields, canonicalization disagreement, partial distribution, mixed generation, incompatible consumer, stale-base activation, approval compromise, Restrictive Override race, expiry recovery, and configuration rollback/restore;
- common-control identity collapse, shared accounts, self-approval chains, stale Effective Principal Graph, quorum and role drift, delegation and roster change, identity-provider and workflow outage, authenticator recovery, stale Approval Set replay, duplicate consumption, approver compromise, break-glass expansion, and Human HALT propagation beyond `B_human_halt_to_commit`;
- evidence pre-effect receipt delay/substitution, store and ingress outage, source-sequence reset, duplicate conflict, missing causal parent, record mutation/deletion/truncation/fork, key and anchor rollback, conflicting restore, schema/canonicalization drift, unsafe redaction/export, premature compaction/deletion, replay divergence, and replay-to-live boundary exposure;
- startup/recovery trigger omission, barrier-close delay, stale Recovery Generation at authority and egress, concurrent owner epochs, incomplete dependency graph, obligation omission, non-atomic broker Inventory Cut, convergence failure, post-cut invalidation, partial-scope shared-resource leakage, forced readiness, and recovery completion attempting old-artifact reuse;
- unknown source, endpoint/credential substitution, continuity reset, sequence gap/rollback/replay, schema/parser/mapping/unit/multiplier/sign drift, hidden default, transformation-lineage break, non-atomic consistency cut, stale/future/crossed input, source disagreement, false approval independence, Capsule substitution/partial refresh, correction/retraction fan-out, Context Generation cache, invalidation suppression, and context recovery attempting old-artifact reuse;
- scheduled and unscheduled session transition, delayed open, auction and volatility phase, halt/suspension conflict, stale tradability, price-band/tick/lot/order-shape drift, account/margin/borrow/settlement conflict, broker-capability degradation, Constraint Generation cache, exact-decision substitution, invalidation race, and venue/broker recovery attempting old-decision reuse;
- side/direction/position-effect inversion, account/instrument/contract/environment/route substitution, unit/multiplier/currency/numeric drift, quantity/tick/lot/rounding boundary, price/order/TIF/expiry/mode mutation, effect-envelope understatement, parser differential, duplicate/unknown fields, downstream serializer/signer/SDK mutation, retry/cancel/amend/replace/split/aggregate lineage loss, Construction Generation cache, and compiler recovery attempting old-proof reuse;
- omitted aggregate scope, stale/mixed state cut, snapshot/effect substitution, missing dimension, unit/sign/scale/limit drift, adverse-scenario truncation, hedge-leg/basis/correlation/liquidity/margin failure, valuation/tail error, overflow/NaN/non-convergence/differential, concurrent stale grant, RCL state advance, Aggregate Risk Generation cache, invalidation suppression/delay beyond `B_aggregate_risk_invalid_to_rcl` or `B_aggregate_risk_invalid_to_egress`, and evaluator recovery attempting old-decision reuse;
- concurrent producer and shared-limit over-allocation, unknown broker-limit scope, duplicate-event/fan-out/redelivery/replay amplification, missing-ACK retry, SDK/proxy/redirect/reconnect flood, cancel/amend/replace storm, queue/in-flight exhaustion, ordinary-to-protective reserve intrusion, priority-only reserve claim, RCL permit double spend, stale/cross-host refill, Action Flow Generation cache, invalidation suppression/delay beyond `B_action_flow_invalid_to_rcl`, `B_action_flow_invalid_to_egress`, or `B_action_flow_violation_to_containment`, control-plane partition with broker-reachable egress, and recovery attempting old-permit reuse;
- incomplete/wildcard/patched approval request, proposer-only or common-mode validation, deterministic-evaluator differential, artifact/scope substitution, duplicate and cross-scope consumption, stale Intent Registry writer, approval authority escalation, Trading Approval Generation cache, invalidation suppression/delay beyond `B_approval_invalid_to_intent`, `B_approval_invalid_to_egress`, or `B_approval_generation_fence`, control-plane partition with broker-reachable egress, and recovery attempting old-decision or consumption reuse;
- incomplete/wildcard/patched/unioned Trial Plan, underestimated credible effect, Trial Budget used as capacity, trial-label bypass, action/effect/count/duration overrun, abort delay beyond `B_trial_abort_to_authority_revoke` or `B_trial_abort_to_egress_deny`, evidence gap delay beyond `B_trial_evidence_gap_to_containment`, selected or hidden negative runs, post-hoc metric/stopping change, coverage extrapolation, promotion skip/union/replay, Promotion Generation fence delay, monitor drift, demotion, and recovery attempting run or promotion reuse;
- non-waivable or unclassified request, incomplete/wildcard/patched/unioned scope, combined residual-risk underestimation, observational or common-mode compensation, same-effective-person approval, decision double spend, evidence relabeling, stale Active Deviation Set, invalidation suppression/delay beyond `B_deviation_revoke_to_authority` or `B_deviation_revoke_to_egress`, Deviation Generation fence delay, expiry/claim/first-byte race, silent renewal, predecessor rollback, emergency-route bypass, and recovery attempting deviation or authority revival;
- missed, suppressed, downgraded, delayed, or under-scoped incident signal; favorable or stale Active Safety Incident Set; concurrent incident/common-mode omission; Incident Generation cache; declaration or scope-expansion delay beyond approved incident bounds; restriction/claim/first-byte race; incident-plane partition with broker reachability; shutdown-before-fence; queue draining by send; stale principal/session/route survival; blind protection cancellation or blanket liquidation; process stop treated as broker finality; external-route rewrite; same-effective-person closure; incomplete recovery handoff; and closure, remediation, or recovery attempting old-scope or authority revival;
- omitted, wildcarded, patched, optionalized, partially refreshed, or unioned monitoring scope; source restart, continuity reset, endpoint/credential/provider change, schema/unit/mapping/lineage/time drift, frozen payload, stale green cache, health-as-currentness, common-mode monitor paths, local permissive threshold, NaN/overflow/empty-window coercion, conflicting-source favorable selection, broad or expired suppression, deduplication collision, alert/retry storm, queue overflow, delivery/provider/roster failure, acknowledgement-as-containment, stale Monitor Generation, monitoring-plane partition with broker reachability, gap/claim/first-byte race, direct monitoring route bypass, and monitoring recovery attempting capacity release, incident clear, scope restoration, or automatic re-arm;
- source-history/tag movement, incomplete submodule/generated-source/build-script closure, mutable or network-fetched build input, builder/provenance substitution, dependency/toolchain/plugin/base-image/runtime-load omission, lockfile or registry compromise, signer/key rollback or revocation, artifact/tag/layer/platform substitution, scan/sign/deploy TOCTOU, effective-control collapse, admission scope widening or union, stale Release Generation, mixed-version incompatibility, non-live-to-live artifact crossover, runtime drift, stale deployment survival, release-plane partition with broker reachability, restriction/claim/first-byte race, and rollback/restore/hotfix/recovery attempting prior admission or authority revival;
- fill/FQP/trade-capture versus obligation-finality collapse; omitted or corrected fee/tax/interest/financing legs; partial/failed settlement and cash-availability confusion; collateral encumbrance/haircut/double-use; borrow recall/return/buy-in; exercise/assignment/delivery/corporate-action legs; custody/transfer/legal-title ambiguity; statement truncation, stale revision, and common mode; break/bust/correction/reversal; stale PTOL writer or proof; Post-Trade Obligation Generation, RCL transfer/release, authority, capability-claim, and first-byte races; post-trade-plane partition with an external route; and recovery attempting prior finality, capacity release, or authority revival;
- stale read;
- broker response loss;
- fill/cancel ordering;
- clock step, freeze, source disagreement, monotonic discontinuity, and cross-host receipt-age simulation;
- Time Health generation delay beyond `B_time_health_to_egress`;
- authorization revocation delay beyond `B_revocation_to_egress`;
- currentness-session loss and capability claim-to-first-byte delay beyond `B_capability_claim_to_send`;
- HALT races before and after the fenced send boundary;
- rate-limit saturation;
- credential revocation;
- stale deployment reactivation;
- query omission and pagination truncation;
- external manual activity;
- corporate-action event, correction, reversal, and partial local application;
- dimension-owner impersonation and stale mutation;
- cache eviction, stale replica, and common-mode dependency failure;
- mixed-version deployment and environment-identity crossover;
- protective replacement at each gap, overlap, fill, and proof boundary.

Fault injection SHALL identify the exact boundary at which it acted.

---

## 376. Broker Verification Safety Rules

Controlled production verification SHALL:

- use one exact ADR-002-025 pre-registered and independently approved scope;
- avoid risk-increasing tests where the property can be demonstrated without them;
- pre-cover the worst credible economic effect through RCL rather than relying on quantity or a planned loss limit;
- have approved independent abort, HALT, final-egress denial, evidence, and recovery paths;
- preserve all raw broker evidence;
- isolate manual activity unless the test explicitly targets it;
- predefine abort conditions;
- not rely on test cleanup to preserve safety;
- be approved under the relevant Safety Profile.

Trial completion, success counters, elapsed time, incident absence, monitoring, or evidence-package creation SHALL NOT widen scope. Every promotion remains an exact, independently reviewed, single-use, non-authorizing decision under ADR-002-025.

Post-trade broker, clearing, custody, bank, transfer, and statement probes SHALL pre-cover the worst credible obligation and shall not treat a cleanup transfer, broker correction, statement match, settlement date, or operator action as evidence that an obligation was safely prevented or finalized.

A test that requires violating the Hard Safety Envelope is prohibited.

---

## 377. Continuous Conformance Evidence

After approval, continuous monitors SHALL detect at least:

- stale epoch rejection failures;
- capability-profile mismatch;
- broker event/order semantic contradiction;
- external detection bound misses;
- late fills beyond profile;
- unexplained capacity release;
- quorum, committed-prefix, Writer Epoch, membership-generation, Restore Generation, or Commit Proof contradiction;
- duplicate broker identity;
- egress bypass attempts;
- Egress Generation, active-principal, usable-credential, broker-session, route-policy, trust-bundle, Quorum Commit Certificate, or hard-fence contradiction;
- Hard Safety Envelope, Runtime Safety Profile, Canonical Semantic Digest, approval, Consumer Compatibility Manifest, Profile Generation, Activation Record, or restrictive-generation contradiction;
- Human Authority Policy, Effective Principal Graph, counted effective principals, role/conflict decision, Approval Request, attestation, Approval Set, consumption, delegation, identity recovery, Human HALT, local latch, break-glass, or compromise contradiction;
- Safety Evidence Envelope, commit receipt, source/store/key continuity, required record class, causal closure, integrity anchor, gap bound, retention, redaction/export, Replay Capsule, replay isolation, or chain-of-custody contradiction;
- Recovery Barrier Policy, Recovery Generation, owner epoch, trigger, scope closure, Inventory Cut, obligation, package, readiness age, invalidation, partial-scope isolation, or re-arm handoff contradiction;
- Critical Input Policy, source identity/continuity, sequence/revision, schema, unit/mapping, transformation lineage, Snapshot/Capsule age and digest, common-mode analysis, correction, Context Generation, invalidation, or egress-binding contradiction;
- Venue Constraint Policy, Constraint Generation, session phase, halt/suspension, tradability, price/tick/lot/quantity/order-shape, account/margin/borrow/settlement, Broker Capability Profile, Snapshot/decision age and digest, or final-egress currentness contradiction;
- Order Construction Policy, Construction Generation, Authorized Construction Envelope, Canonical Broker Command, Economic Effect Envelope, capacity dominance, Order Conformance Proof, compiler/serializer/SDK compatibility, command/proof age, downstream mutation, or actual-outbound equivalence contradiction;
- Aggregate Risk Policy, Aggregate Risk Generation, Aggregate Risk State Snapshot cut/age, Adverse Scenario Set, dimension/scope completeness, valuation/benefit/numerical derivation, Aggregate Risk Decision age/digest, allocation vector, RCL binding, or final-egress currentness contradiction;
- Action Flow Policy, Action Flow Generation, State Snapshot cut/age, cause lineage/amplification, shared-scope resource vector, Decision/Permit age and digest, RCL allocation/claim/consumption, protective reserve/lease, counter/refill, queue/in-flight, invalidation, or final-egress currentness contradiction;
- Restricted-Live Trial Policy, Plan, Run, scope, Promotion Generation, remaining action/effect/count/duration envelope, abort, evidence completeness, coverage, promotion consumption, production scope, demotion, or monitoring contradiction;
- Safety Deviation Policy, requirement/hazard classification, Non-Waivable Boundary, exact scope/dependency closure, combined residual risk, compensating-control state, Effective Principal quorum, decision consumption, Residual-Risk Acceptance Record, Active Deviation Set, Deviation Generation, expiry, revocation, or final-egress currentness contradiction;
- Safety Incident Policy, signal classification, severity/materiality, dependency closure, Incident Generation, Active Safety Incident Set, lifecycle, containment plan, controlled-shutdown ordering, hard fence, economic/protection obligation, recovery handoff, closure independence, or final-egress currentness contradiction;
- Safety Monitoring Policy, Critical Telemetry Manifest, Monitor Coverage Manifest, source continuity, telemetry semantics, deterministic evaluator, hard-bound semantics, Monitor Generation, Continuous Conformance Snapshot, Monitoring Gap, common-mode analysis, suppression, alert correlation, delivery, acknowledgement, escalation, restrictive/incident handoff, or final-egress currentness contradiction;
- Software Release Policy, source/tree identity, build recipe/provenance, dependency/toolchain/runtime closure, signer/key state, Release Artifact Manifest, admission decision, Release Generation, Admitted Release Set, compatibility graph, actual runtime attestation, restriction, deployment, or final-egress currentness contradiction;
- Post-Trade Finality Policy, Post-Trade Obligation Generation, active obligation-set completeness, obligation identity/version, field-specific finality, statement coverage/provenance, cash/collateral/margin/borrow/custody/transfer state, break/correction closure, PTOL writer fence, RCL transition, or final-egress currentness contradiction;
- protective reserve guarantee degradation;
- unexpected session or rate-limit behavior;
- Time Health snapshot age or generation-propagation bound misses;
- revocation or HALT egress-containment bound misses;
- unsafe currentness-cache age or check-then-send gaps;
- automatic or unauthorized re-arm;
- non-owner state mutation or collapsed state dimensions;
- stale or conflicted evidence accepted as reconciled;
- undeclared failure-domain or blast-radius expansion;
- unbounded protective gap, overlap, or replacement proof age;
- unresolved non-trade transition or duplicate event application.

A continuous violation invalidates the corresponding evidence item and may revert the ADR/profile status to `EXPIRED` or `CONTRADICTORY`.

---

## 378. Residual Risk Register

Every unresolved limitation SHALL record:

- risk identity;
- affected requirement and ADR;
- broker/account/instrument scope;
- credible failure sequence;
- maximum economic effect;
- existing controls;
- detection and containment bound;
- owner;
- approver;
- expiration/review date;
- required scope reduction;
- evidence references.

Where RFC-001 permits a deviation, the register SHALL additionally bind the exact current ADR-002-026 request, decision, Active Deviation Set, reduced configuration scope, independently verified compensating controls, Deviation Generation, hard expiry, review interval, and non-PASS evidence status. Separate residual risks SHALL NOT be unioned at a consumer; combined risk requires one canonical reviewed set.

“Broker limitation” is not a sufficient residual-risk description.

---

## 379. Independent Review Checklist

The reviewer SHALL confirm:

- test matched the stated baseline;
- fault was actually injected;
- required evidence was captured;
- pass condition was not inferred from missing data;
- raw and normalized broker evidence agree or conflicts are handled conservatively;
- invariant evaluation covers every risk dimension;
- containment bounds are measured, not assumed;
- cross-host snapshot age uses consumer receipt monotonic time and includes transport uncertainty;
- revocation and HALT races were injected at the irreversible egress boundary;
- state ownership and conservative-direction violations were negatively tested;
- failure-domain independence claims match the actual deployment and credential paths;
- quorum placement, durable-commit configuration, linearizable reads, membership changes, snapshot/restore, and egress Commit Proof match ADR-002-012;
- the effective Final Egress Trust Boundary includes every signer, session, proxy, queue, route, and credential authority, and its Quorum Commit Certificate and hard-fence behavior match ADR-002-013;
- every safety-configuration consumer reproduces the canonical semantics and exact committed bundle, and approval, activation, restriction, rollback, restore, and compatibility behavior match ADR-002-014;
- every counted human is one current attributable effective natural person, and policy, graph, exact request, attestation, quorum, consumption, delegation, HALT, break-glass, compromise, and non-revival behavior match ADR-002-015;
- every required record is source-attributed, causally complete, durably ordered at the correct effect boundary, integrity-anchored, retained, redacted without semantic loss, and replayed only in an isolated non-authorizing environment under ADR-002-016;
- every recovery trigger closes the barrier before current observation, only the current fenced owner evaluates a dependency-complete Inventory Cut and obligation graph, and readiness remains non-authorizing, invalidatable, and bound to the exact Recovery Generation under ADR-002-017;
- every Critical Input is classified and source-attributed with exact semantics and lineage, approval independence reflects actual common modes, every consumer binds the same immutable Capsule, and correction/invalidation/currentness reach authority and final egress under ADR-002-018;
- every broker-directed action binds one exact current Venue Constraint Snapshot and Order Admissibility Decision, exits and protective actions are not assumed executable, and material constraint invalidation reaches authority and final egress under ADR-002-019;
- every broker-directed action is deterministically constructed from one exact Intent and closed Authorized Construction Envelope, its conservative Economic Effect Envelope is dominated by the exact RCL commitment, and final egress verifies the actual outbound representation under ADR-002-020;
- every capacity request binds one complete current aggregate-state cut, approved scenario set, exact command effect, deterministic conservative projected vector, current Aggregate Risk Decision, and RCL commitment under ADR-002-021; unproven benefit is zero and evaluator authority does not mutate capacity or transmit;
- every broker-directed action binds one complete current shared-scope action-flow cut, immutable cause lineage, finite amplification envelope, exact resource vector, current Action Flow Decision, RCL commitment, and single-use permit under ADR-002-022; priority is not reserve and governor/scheduler authority does not mutate capacity or transmit;
- every ADR-002-025 Trial Plan is exact and pre-registered, the worst credible effect is RCL-covered, abort dominates evidence collection, negative evidence is retained, coverage does not extrapolate, promotion is progressive and single-use, and no trial or promotion artifact creates live authority;
- every ADR-002-026 request is outside the Non-Waivable Boundary and exact in scope/dependency closure, compensation is enforceable and independently evidenced, Effective Principal approval is independent, combined risk is bounded, decision consumption is single-use, evidence remains non-PASS, and expiry/revocation/currentness cannot be cached or revived;
- every ADR-002-027 material signal restricts before investigation completes, scope is the greatest credible dependency closure, Incident Generation and the Active Safety Incident Set are current and complete, containment/shutdown preserve economic and protection obligations, handoff is explicitly accepted by one Recovery Session, closure is independent and non-permissive, and no incident artifact bypasses existing authority;
- every ADR-002-028 Critical obligation maps to exact current telemetry and deterministic monitor coverage, source continuity and semantics are proven, hard-bound meaning is preserved, gaps and common modes are restrictive, suppression cannot silence safety, alert acknowledgement is not containment, Monitor Generation is active through final egress, and no monitoring artifact becomes authority;
- every ADR-002-029 safety-critical runtime artifact is content-addressed to complete reviewed source, build, dependency/toolchain and runtime lineage, independently admitted for exact scope, fenced by one current Release Generation, positively attested at runtime and final egress, and no supply-chain artifact or workflow becomes authority;
- every ADR-002-030 economic obligation leg has exact identity, scope, provenance, lifecycle, dependency closure, field-specific finality, correction history, current Post-Trade Obligation Generation, conservative RCL coverage, and any external instruction remains confined to final egress; PTOL, statements, proofs, evidence, and recovery never become capacity or transmission authority;
- protective gap, overlap, and Final Quantity Proof evidence cover adverse interleavings;
- non-trade transition evidence covers old and new economic effects and corrections;
- no manual cleanup occurred before final evidence capture;
- failed and inconclusive runs are retained;
- residual risk does not contradict RFC-000/RFC-001;
- live scope matches the tested capability profile.

---

## 380. Approval Gates by ADR

### ADR-002-001

Requires:

- RC-EV-001, RC-EV-002, RC-EV-006, RC-EV-012, RC-EV-013, RC-EV-014, and RC-EV-016;
- SA-EV-003 through SA-EV-007;
- PR-EV-001, PR-EV-002, PR-EV-005 through PR-EV-007, PR-EV-011, and PR-EV-012;
- ARE-EV-001, ARE-EV-003, and ARE-EV-010;
- IOC-EV-006;
- FD-EV-001, FD-EV-008, and FD-EV-010;
- RCLP-EV-001, RCLP-EV-003, RCLP-EV-004, and RCLP-EV-011;
- AFG-EV-001 and AFG-EV-003;
- SPG-EV-001, SPG-EV-002, and SPG-EV-011;
- BC-EV-013, BC-EV-016, and BC-EV-021;
- VTG-EV-010;
- X-EV-002, X-EV-003, X-EV-005, X-EV-006, and X-EV-008;
- PRD-EV-001 and PRD-EV-002;
- an approved Broker Capability Profile and Safety Profile for every protective resource domain and guarantee level;
- independent review.

### ADR-002-002

Requires:

- AFG-EV-001, AFG-EV-003, AFG-EV-004, AFG-EV-006 through AFG-EV-010, and AFG-EV-012;
- ARE-EV-001 through ARE-EV-012;
- IOC-EV-006, IOC-EV-009, IOC-EV-011, and IOC-EV-012;
- RC-EV-001 through RC-EV-018;
- ERI-EV-001 through ERI-EV-005, ERI-EV-007, and ERI-EV-010 through ERI-EV-012;
- SPG-EV-001, SPG-EV-002, SPG-EV-004 through SPG-EV-006, and SPG-EV-011;
- HAG-EV-006, HAG-EV-007, and HAG-EV-011;
- X-EV-001 through X-EV-004, X-EV-007, X-EV-009, and X-EV-012;
- applicable model-based properties;
- independent review.

### ADR-002-003

Requires:

- SA-EV-001 through SA-EV-015;
- ERI-EV-001, ERI-EV-003 through ERI-EV-007, ERI-EV-010, and ERI-EV-012;
- SPG-EV-004, SPG-EV-006, SPG-EV-007, SPG-EV-010, and SPG-EV-011;
- EGRESS-EV-002, EGRESS-EV-004, EGRESS-EV-007 through EGRESS-EV-010, and EGRESS-EV-012;
- HAG-EV-005, HAG-EV-008, HAG-EV-009, and HAG-EV-011;
- X-EV-002, X-EV-003, X-EV-006, X-EV-008, X-EV-009, and X-EV-012;
- authority/fencing security assessment;
- independent review.

### ADR-002-004

Requires:

- AFG-EV-001, AFG-EV-003 through AFG-EV-006, AFG-EV-009, AFG-EV-010, and AFG-EV-012;
- IOC-EV-001 through IOC-EV-012;
- VTG-EV-001 through VTG-EV-005, VTG-EV-007 through VTG-EV-010, and VTG-EV-012;
- BC-EV-001 through BC-EV-022 for each approved broker profile, with `NOT_APPLICABLE` justified by profile scope where valid;
- ERI-EV-001, ERI-EV-004, ERI-EV-005, and ERI-EV-007 through ERI-EV-012;
- SPG-EV-004, SPG-EV-010, and SPG-EV-011;
- EGRESS-EV-001 through EGRESS-EV-003, EGRESS-EV-008, EGRESS-EV-010, EGRESS-EV-011, and EGRESS-EV-012;
- HAG-EV-006, HAG-EV-007, HAG-EV-009, and HAG-EV-011;
- X-EV-004, X-EV-005, X-EV-010, and X-EV-011;
- restricted production evidence for safety-critical live semantics;
- independent review.

### ADR-002-005

Requires:

- STATE-EV-001 through STATE-EV-005;
- ERI-EV-001, ERI-EV-004, ERI-EV-006 through ERI-EV-008, and ERI-EV-010 through ERI-EV-012;
- RC-EV-003, RC-EV-004, RC-EV-006 through RC-EV-008, RC-EV-010, RC-EV-011, RC-EV-017, and SA-EV-006;
- model-based exploration of orthogonality, CPL-1 through CPL-7, and conservative direction;
- state-transition ownership security assessment and independent review.

### ADR-002-006

Requires:

- RECON-EV-001 through RECON-EV-005;
- CII-EV-002 through CII-EV-006, CII-EV-008, and CII-EV-012;
- ERI-EV-001, ERI-EV-004 through ERI-EV-008, and ERI-EV-010 through ERI-EV-012;
- RC-EV-005, RC-EV-007, RC-EV-010, RC-EV-011, SA-EV-011, BC-EV-006, and BC-EV-017;
- approved field-specific proof, freshness, source-independence, and conservative-bound rules;
- reconciliation and evidence-independence review.

### ADR-002-007

Requires:

- IOC-EV-006 and IOC-EV-008 through IOC-EV-012;
- VTG-EV-006, VTG-EV-007, and VTG-EV-010 through VTG-EV-012;
- REARM-EV-001 through REARM-EV-012;
- CII-EV-007 through CII-EV-009 and CII-EV-012;
- SBR-EV-001 through SBR-EV-004 and SBR-EV-006 through SBR-EV-012;
- ERI-EV-001 through ERI-EV-007, ERI-EV-010, and ERI-EV-012;
- SPG-EV-001 through SPG-EV-012;
- EGRESS-EV-004 through EGRESS-EV-010 and EGRESS-EV-012;
- HAG-EV-001 through HAG-EV-012;
- SA-EV-009, SA-EV-010, SA-EV-013, BC-EV-015, BC-EV-020, BC-EV-021, X-EV-007, X-EV-009, and X-EV-012;
- approved and measured `B_risk_increase_revoke`, `B_revocation_to_egress`, `B_halt_to_egress`, `B_recovery_trigger_to_barrier`, `B_recovery_barrier_to_egress`, `MAX_recovery_readiness_age`, `MAX_normal_capability_age`, `B_capability_claim_to_send`, and `B_egress_hard_fence`;
- authorization/final-egress security assessment and independent review.

### ADR-002-008

Requires:

- VTG-EV-001, VTG-EV-002, VTG-EV-007, VTG-EV-010, and VTG-EV-012;
- TIME-EV-001 through TIME-EV-010;
- CII-EV-002, CII-EV-005, CII-EV-008, CII-EV-009, and CII-EV-012;
- ERI-EV-001, ERI-EV-004 through ERI-EV-008, ERI-EV-010, and ERI-EV-012;
- SPG-EV-001, SPG-EV-008, SPG-EV-010, and SPG-EV-011;
- HAG-EV-002, HAG-EV-004, and HAG-EV-011;
- SA-EV-005, SA-EV-006, SA-EV-011, and X-EV-008;
- approved and measured `B_time_health_to_egress`, `MAX_time_health_snapshot_age`, and applicable clock, suspension, holdover, freshness, and session bounds;
- time-source/common-mode review and independent review.

### ADR-002-009

Requires:

- FD-EV-001 through FD-EV-012;
- SBR-EV-001 through SBR-EV-004, SBR-EV-007, SBR-EV-010, and SBR-EV-012;
- ERI-EV-003, ERI-EV-005, ERI-EV-007, ERI-EV-009, ERI-EV-010, and ERI-EV-012;
- SPG-EV-004, SPG-EV-005, SPG-EV-007, and SPG-EV-009 through SPG-EV-011;
- EGRESS-EV-001 through EGRESS-EV-003 and EGRESS-EV-006 through EGRESS-EV-010;
- HAG-EV-001, HAG-EV-005, HAG-EV-008, and HAG-EV-009;
- SA-EV-001, SA-EV-002, SA-EV-008, SA-EV-013 through SA-EV-015, BC-EV-015, BC-EV-020, X-EV-002, X-EV-003, and X-EV-009;
- an approved Failure-Domain Allocation Matrix, deployment profile, RCL fencing mechanism, and implementation of the selected ADR-002-007 §§9.1–9.5 egress-currentness protocol;
- failure-domain security assessment and independent review.

### ADR-002-010

Requires:

- VTG-EV-003 through VTG-EV-005, VTG-EV-010, and VTG-EV-012;
- NT-EV-001 through NT-EV-012;
- CII-EV-002, CII-EV-003, CII-EV-005, CII-EV-008, and CII-EV-012;
- ERI-EV-001, ERI-EV-004 through ERI-EV-008, and ERI-EV-010 through ERI-EV-012;
- RC-EV-010, RC-EV-015, BC-EV-008, BC-EV-019, X-EV-010, TIME-EV-008, and REARM-EV-003;
- HAG-EV-007, HAG-EV-009, and HAG-EV-011;
- approved source-authority, transition-envelope, RCL remap, event-time, and broker-treatment rules;
- broker-profile evidence for every supported event/instrument scope and independent review.

### ADR-002-011

Requires:

- VTG-EV-004, VTG-EV-007 through VTG-EV-010, and VTG-EV-012;
- PR-EV-001 through PR-EV-012;
- ERI-EV-001 through ERI-EV-007 and ERI-EV-010 through ERI-EV-012;
- EGRESS-EV-006, EGRESS-EV-007, EGRESS-EV-011, and EGRESS-EV-012;
- HAG-EV-006, HAG-EV-007, and HAG-EV-011;
- RC-EV-005 through RC-EV-008, BC-EV-002, BC-EV-003, BC-EV-007 through BC-EV-010, BC-EV-012 through BC-EV-014, X-EV-005, and X-EV-006;
- approved and measured gap, overlap, Final Quantity Proof, completion, and containment bounds;
- broker-profile evidence for every claimed replacement mode and independent review.

### ADR-002-012

Requires:

- RCLP-EV-001 through RCLP-EV-012;
- SBR-EV-002, SBR-EV-003, SBR-EV-006, SBR-EV-009 through SBR-EV-012;
- ERI-EV-001, ERI-EV-002, ERI-EV-004 through ERI-EV-008, ERI-EV-010, and ERI-EV-012;
- SPG-EV-004, SPG-EV-005, SPG-EV-007, and SPG-EV-010;
- EGRESS-EV-004 through EGRESS-EV-009;
- HAG-EV-002, HAG-EV-004, HAG-EV-005, and HAG-EV-010;
- RC-EV-001 through RC-EV-004, RC-EV-009, RC-EV-012, RC-EV-013, RC-EV-017, RC-EV-018, SA-EV-001 through SA-EV-003, SA-EV-008, SA-EV-013 through SA-EV-015, REARM-EV-008, REARM-EV-010, FD-EV-002 through FD-EV-005, FD-EV-007, FD-EV-009, and FD-EV-012;
- approved Capacity Domain, failure-tolerance model, membership protocol, Commit Proof, snapshot/restore, and disaster-recovery rules;
- consensus/fencing security assessment and independent review.

### ADR-002-013

Requires:

- AFG-EV-001, AFG-EV-003, and AFG-EV-006 through AFG-EV-012;
- ARE-EV-002, ARE-EV-008, ARE-EV-009, ARE-EV-011, and ARE-EV-012;
- IOC-EV-002 and IOC-EV-006 through IOC-EV-012;
- VTG-EV-003, VTG-EV-004, VTG-EV-006, VTG-EV-007, VTG-EV-011, and VTG-EV-012;
- EGRESS-EV-001 through EGRESS-EV-013;
- CII-EV-007 through CII-EV-009, CII-EV-011, and CII-EV-012;
- SBR-EV-001 through SBR-EV-003 and SBR-EV-008 through SBR-EV-012;
- ERI-EV-001 through ERI-EV-007, ERI-EV-009, ERI-EV-011, and ERI-EV-012;
- SPG-EV-004, SPG-EV-006, SPG-EV-007, SPG-EV-010, and SPG-EV-011;
- HAG-EV-005 through HAG-EV-007, HAG-EV-009, and HAG-EV-011;
- SA-EV-008, SA-EV-009, SA-EV-012, SA-EV-013, BC-EV-001, BC-EV-002, BC-EV-003, BC-EV-014, BC-EV-015, BC-EV-020, BC-EV-021, REARM-EV-008, REARM-EV-010, REARM-EV-011, FD-EV-001 through FD-EV-007, FD-EV-009, RCLP-EV-002, RCLP-EV-003, RCLP-EV-006 through RCLP-EV-009, RCLP-EV-012, X-EV-001 through X-EV-004, X-EV-006, X-EV-009, X-EV-011, and X-EV-012;
- an approved Final Egress Trust Boundary, Active Egress Principal topology, Quorum Commit Certificate, credential/session model, route/endpoint policy, Hard Egress Fence, and Broker Capability Profile;
- approved and measured `B_egress_hard_fence`, `B_recovery_barrier_to_egress`, and applicable currentness, revocation, HALT, recovery-barrier, failure-domain, session, and claim-to-send bounds;
- independent credential, route, proof-validation, bypass, and recovery security assessment.

### ADR-002-014

Requires:

- AFG-EV-001, AFG-EV-005 through AFG-EV-012;
- ARE-EV-004, ARE-EV-005, ARE-EV-007, ARE-EV-009, ARE-EV-011, and ARE-EV-012;
- IOC-EV-003, IOC-EV-004, IOC-EV-007, IOC-EV-011, and IOC-EV-012;
- VTG-EV-006, VTG-EV-007, VTG-EV-010, and VTG-EV-012;
- SPG-EV-001 through SPG-EV-012;
- CII-EV-001, CII-EV-003, CII-EV-004, CII-EV-007, CII-EV-008, and CII-EV-012;
- SBR-EV-001, SBR-EV-004, SBR-EV-007, SBR-EV-009, SBR-EV-010, and SBR-EV-012;
- ERI-EV-001, ERI-EV-004 through ERI-EV-010, and ERI-EV-012;
- HAG-EV-001 through HAG-EV-004, HAG-EV-006, and HAG-EV-008 through HAG-EV-010;
- RC-EV-001, RC-EV-002, RC-EV-009, RC-EV-013, RC-EV-017, SA-EV-001, SA-EV-002, SA-EV-008 through SA-EV-010, SA-EV-013, BC-EV-015, REARM-EV-001, REARM-EV-004 through REARM-EV-006, REARM-EV-008 through REARM-EV-012, TIME-EV-001, TIME-EV-006, TIME-EV-009, FD-EV-002, FD-EV-007, FD-EV-009, FD-EV-012, RCLP-EV-002, RCLP-EV-003, RCLP-EV-005, RCLP-EV-008 through RCLP-EV-010, RCLP-EV-012, EGRESS-EV-003 through EGRESS-EV-007, EGRESS-EV-009, EGRESS-EV-012, X-EV-002, X-EV-003, X-EV-007 through X-EV-009, and X-EV-012;
- approved canonical artifact schemas, semantic normalization, comparison rules, envelope and profile governance, Consumer Compatibility Manifest, Profile Generation, Activation Record, and Restrictive Override protocol;
- approved and measured applicable revocation, egress, time, evidence-persistence, activation-validity, approval-validity, and restriction-propagation bounds;
- independent configuration-authority, signing, approval, canonicalization, compatibility, activation, rollback, restore, and bypass security assessment.

### ADR-002-015

Requires:

- IOC-EV-002, IOC-EV-005, and IOC-EV-010 through IOC-EV-012;
- VTG-EV-006, VTG-EV-007, VTG-EV-011, and VTG-EV-012;
- HAG-EV-001 through HAG-EV-018;
- CII-EV-006, CII-EV-007, CII-EV-011, and CII-EV-012;
- SBR-EV-001, SBR-EV-004, SBR-EV-006 through SBR-EV-009, SBR-EV-011, and SBR-EV-012;
- ERI-EV-001, ERI-EV-003 through ERI-EV-010, and ERI-EV-012;
- SA-EV-009, SA-EV-010, SA-EV-012, SA-EV-013, REARM-EV-002 through REARM-EV-005, REARM-EV-008 through REARM-EV-012, TIME-EV-007, TIME-EV-009, FD-EV-001, FD-EV-003, FD-EV-005, FD-EV-006, FD-EV-009, RCLP-EV-005 through RCLP-EV-009, EGRESS-EV-001 through EGRESS-EV-003, EGRESS-EV-005 through EGRESS-EV-010, EGRESS-EV-012, SPG-EV-001, SPG-EV-004 through SPG-EV-010, SPG-EV-012, X-EV-006, X-EV-007, X-EV-009, and X-EV-012;
- approved Human Authority Policy, Effective Principal Graph, Approval Request, Approval Attestation, Approval Set, consumption, delegation, Human HALT, break-glass, compromise, and recovery mechanisms;
- approved and measured `B_human_halt_to_commit`, `B_halt_to_egress`, and applicable human session, approval, delegation, revocation, identity-fence, notification, evidence, and recovery bounds;
- independent identity, authentication, effective-control, workflow, quorum, separation-of-duties, break-glass, HALT-path, approval-consumption, compromise, and bypass security assessment.

### ADR-002-016

Requires:

- AFG-EV-001 through AFG-EV-012;
- ARE-EV-001 through ARE-EV-012;
- IOC-EV-001 through IOC-EV-012;
- VTG-EV-001 through VTG-EV-012;
- ERI-EV-001 through ERI-EV-012;
- CII-EV-002, CII-EV-004, CII-EV-005, CII-EV-007, CII-EV-008, and CII-EV-012;
- SBR-EV-004 through SBR-EV-006 and SBR-EV-008 through SBR-EV-012;
- STATE-EV-001 through STATE-EV-005, RECON-EV-001 through RECON-EV-005, RCLP-EV-003, RCLP-EV-006, RCLP-EV-009, RCLP-EV-010, RCLP-EV-012, EGRESS-EV-002, EGRESS-EV-005 through EGRESS-EV-007, EGRESS-EV-009, EGRESS-EV-012, SPG-EV-003, SPG-EV-007, SPG-EV-010 through SPG-EV-012, HAG-EV-004, HAG-EV-005, HAG-EV-009, HAG-EV-011, and HAG-EV-012;
- approved Safety Evidence Envelope, Evidence Integrity Policy, Evidence Commit Receipt, Integrity Anchor, Evidence Gap, retention/redaction/access rules, and Replay Capsule schemas;
- approved and measured `B_evidence_persist`, `B_evidence_gap_detect`, `B_evidence_gap_contain`, and applicable retention, replay, egress, time, broker, and recovery bounds;
- independent storage, ingestion, source identity, cryptographic integrity, key custody, emergency-journal, access, redaction/export, retention/deletion, backup/restore, replay-isolation, and live-boundary security assessment.

### ADR-002-017

Requires:

- AFG-EV-001 through AFG-EV-012;
- ARE-EV-001, ARE-EV-002, and ARE-EV-008 through ARE-EV-012;
- IOC-EV-008 through IOC-EV-012;
- VTG-EV-001, VTG-EV-002, VTG-EV-005, VTG-EV-007, VTG-EV-010, and VTG-EV-012;
- SBR-EV-001 through SBR-EV-012;
- CII-EV-002, CII-EV-005, and CII-EV-008 through CII-EV-012;
- RC-EV-005 through RC-EV-008, RC-EV-010 through RC-EV-013, RC-EV-017, RC-EV-018, SA-EV-001 through SA-EV-003, SA-EV-008 through SA-EV-011, SA-EV-013 through SA-EV-015, BC-EV-002, BC-EV-004 through BC-EV-008, BC-EV-011, BC-EV-014, BC-EV-017 through BC-EV-019, and X-EV-003, X-EV-004, X-EV-007, X-EV-009, X-EV-010, and X-EV-012;
- STATE-EV-001 through STATE-EV-005, RECON-EV-001 through RECON-EV-005, TIME-EV-003 through TIME-EV-010, REARM-EV-001 through REARM-EV-004 and REARM-EV-007 through REARM-EV-012, FD-EV-002 through FD-EV-005 and FD-EV-007 through FD-EV-012, PR-EV-003 through PR-EV-005 and PR-EV-008 through PR-EV-012, NT-EV-004 through NT-EV-012;
- RCLP-EV-002 through RCLP-EV-005 and RCLP-EV-008 through RCLP-EV-012, EGRESS-EV-002, EGRESS-EV-004, EGRESS-EV-007 through EGRESS-EV-010 and EGRESS-EV-012, SPG-EV-004, SPG-EV-007 through SPG-EV-011, HAG-EV-004, HAG-EV-005 and HAG-EV-008 through HAG-EV-012, ERI-EV-001 and ERI-EV-003 through ERI-EV-012;
- approved Recovery Barrier Policy, trigger classifier, dependency graph, ordered Recovery Generation and owner-epoch fence, Inventory Cut protocol, obligation registry, convergence rules, package and readiness schemas, invalidation path, partial-scope proof, and governed re-arm handoff;
- approved and measured `B_recovery_trigger_to_barrier`, `B_recovery_barrier_to_egress`, `B_startup_reconciliation`, `MAX_recovery_readiness_age`, and applicable broker-query, evidence-gap, time, source-freshness, convergence, invalidation, HALT, and egress bounds;
- independent recovery-owner, restore, broker-inventory, partial-scope, forced-ready, HALT, capacity-authority, final-egress, evidence, and automatic-re-arm security and safety assessment.

### ADR-002-018

Requires:

- IOC-EV-002, IOC-EV-003, IOC-EV-007, IOC-EV-008, and IOC-EV-012;
- VTG-EV-002, VTG-EV-003, VTG-EV-005 through VTG-EV-007, VTG-EV-010, and VTG-EV-012;
- CII-EV-001 through CII-EV-012;
- RECON-EV-001 through RECON-EV-005, TIME-EV-001 through TIME-EV-010, STATE-EV-001, STATE-EV-003 through STATE-EV-005, and SBR-EV-001, SBR-EV-004 through SBR-EV-007, SBR-EV-009, SBR-EV-010, and SBR-EV-012;
- ERI-EV-001, ERI-EV-004 through ERI-EV-012, SPG-EV-001 through SPG-EV-004, SPG-EV-007, SPG-EV-010 through SPG-EV-012, HAG-EV-002, HAG-EV-003, HAG-EV-007, HAG-EV-009, and HAG-EV-011;
- EGRESS-EV-002 through EGRESS-EV-007, EGRESS-EV-009, EGRESS-EV-010, and EGRESS-EV-012, BC-EV-006, BC-EV-008, BC-EV-011, BC-EV-016 through BC-EV-019, NT-EV-001 through NT-EV-004 and NT-EV-007 through NT-EV-012, and X-EV-008 through X-EV-012;
- approved Critical Input Policy, source registry and continuity protocols, schema/unit/mapping registry, transformation manifests, consistency-cut/source-authority rules, independent-approval paths, common-mode analyses, Capsule binding, Context Generation, invalidation graph, and active final-egress currentness mechanism;
- approved and measured `B_critical_input_loss_detect`, `B_critical_input_invalid_to_authority`, `B_critical_input_invalid_to_egress`, `MAX_critical_input_snapshot_age`, `MAX_decision_context_age`, and applicable source freshness, correction, time, evidence, recovery, broker, authority, and egress bounds;
- independent source-identity, parser/schema, mapping/unit, transformation, common-mode, approval-independence, context-substitution, invalidation, stale-publisher, final-egress, restore, and automatic-re-arm security and safety assessment.

### ADR-002-019

Requires:

- IOC-EV-001 through IOC-EV-010 and IOC-EV-012;
- VTG-EV-001 through VTG-EV-012;
- CII-EV-001 through CII-EV-012, TIME-EV-002 through TIME-EV-010, SBR-EV-001, SBR-EV-004 through SBR-EV-010, and SBR-EV-012;
- BC-EV-001, BC-EV-003, BC-EV-009, BC-EV-010, BC-EV-012 through BC-EV-019, and BC-EV-021, PR-EV-001 through PR-EV-005 and PR-EV-008 through PR-EV-012, NT-EV-001 through NT-EV-012;
- EGRESS-EV-002 through EGRESS-EV-010 and EGRESS-EV-012, SPG-EV-001 through SPG-EV-004, SPG-EV-007, SPG-EV-010 through SPG-EV-012, HAG-EV-006, HAG-EV-007, HAG-EV-009, and HAG-EV-011;
- ERI-EV-001, ERI-EV-004 through ERI-EV-012, RECON-EV-001 through RECON-EV-005, STATE-EV-003 through STATE-EV-005, and X-EV-004 through X-EV-012;
- approved Venue Constraint Policy, source and continuity registry, Session Phase and tradability state machines, instrument/order/account/margin/borrow/settlement rules, exact Snapshot and Order Admissibility Decision schemas, Constraint Generation, dependency closure, invalidation graph, and active final-egress currentness mechanism;
- approved and measured `B_venue_constraint_loss_detect`, `B_venue_constraint_invalid_to_authority`, `B_venue_constraint_invalid_to_egress`, `MAX_venue_constraint_snapshot_age`, `MAX_order_admissibility_decision_age`, and applicable Critical Input, trustworthy-time, broker, capability-claim, HALT, recovery, protection, and evidence bounds;
- broker-scoped assurance for every claimed venue, session, account, instrument, order type, time in force, margin, borrow, settlement, exit, reduce-only, cancellation, protective, and replacement behavior;
- independent source, calendar, venue-state, mapping, rule-engine, account, margin, borrow, settlement, broker-capability, common-mode, exact-binding, authority-separation, stale-publisher, final-egress, restore, and automatic-re-arm security and safety assessment.

### ADR-002-020

Requires:

- ARE-EV-002 through ARE-EV-004, ARE-EV-007 through ARE-EV-009, ARE-EV-011, and ARE-EV-012;
- IOC-EV-001 through IOC-EV-012;
- VTG-EV-003 through VTG-EV-009 and VTG-EV-011 through VTG-EV-012, CII-EV-003, CII-EV-004, CII-EV-007 through CII-EV-009, and CII-EV-012;
- RC-EV-001 through RC-EV-004, RC-EV-007, RC-EV-009 through RC-EV-012, and RC-EV-017, BC-EV-001 through BC-EV-005, BC-EV-009 through BC-EV-016, and BC-EV-019 through BC-EV-022;
- EGRESS-EV-001 through EGRESS-EV-010 and EGRESS-EV-012, SPG-EV-002 through SPG-EV-005, SPG-EV-007, SPG-EV-010 through SPG-EV-012, and ERI-EV-001 through ERI-EV-012;
- approved Intent, Authorized Construction Envelope, Order Construction Policy, Canonical Broker Command, Economic Effect Envelope, Order Conformance Proof, canonicalization, numeric/unit, mapping, compiler, serializer/SDK, actual-outbound comparison, retry/split/replace lineage, Construction Generation, and invalidation contracts;
- approved and measured `B_order_conformance_invalid_to_egress`, `MAX_canonical_broker_command_age`, `MAX_order_conformance_proof_age`, and applicable context, venue, capacity, authority, capability-claim, HALT, evidence, broker, and recovery bounds;
- broker-scoped assurance for every claimed account, instrument, contract, direction, position effect, unit, multiplier, currency, price, order type, time in force, expiration, mode, route, idempotency, retry, cancel, amend, replace, split, aggregate, serializer, signer, SDK, and actual-outbound behavior;
- independent numeric, mapping, compiler, canonicalization, parser-differential, common-mode, authority-separation, downstream-mutation, final-egress, restore, and automatic-rearm security and safety assessment.

### ADR-002-021

Requires:

- AFG-EV-001, AFG-EV-006 through AFG-EV-010, and AFG-EV-012;
- ARE-EV-001 through ARE-EV-012;
- IOC-EV-003, IOC-EV-006 through IOC-EV-009, IOC-EV-011, and IOC-EV-012, VTG-EV-005 through VTG-EV-010 and VTG-EV-012, and CII-EV-003 through CII-EV-010 and CII-EV-012;
- RC-EV-001 through RC-EV-018, RCLP-EV-002 through RCLP-EV-012, RECON-EV-001 through RECON-EV-005, STATE-EV-001 through STATE-EV-005, and NT-EV-001 through NT-EV-012;
- EGRESS-EV-002 through EGRESS-EV-010 and EGRESS-EV-012, SPG-EV-001 through SPG-EV-012, ERI-EV-001 through ERI-EV-012, SBR-EV-001 through SBR-EV-012, and applicable BC, TIME, FD, PR, HAG, REARM, SA, and cross-system evidence;
- approved Aggregate Risk Policy, state-snapshot consistency cut, Adverse Scenario Set, risk-vector dimension/unit/scope/limit semantics, valuation/uncertainty, netting/hedge/correlation/margin/liquidity rules, deterministic evaluator, independent verifier, Aggregate Risk Decision, RCL admission, Aggregate Risk Generation, invalidation, and active final-egress currentness mechanisms;
- approved and measured `B_aggregate_risk_invalid_to_rcl`, `B_aggregate_risk_invalid_to_egress`, `MAX_aggregate_risk_state_snapshot_age`, `MAX_aggregate_risk_decision_age`, and applicable Critical Input, venue, conformance, capacity, authority, capability-claim, HALT, evidence, broker, and recovery bounds;
- broker/account/product-scoped assurance for every claimed position/order/fill, margin, collateral, liquidity, FX, concentration, basis, correlation, hedge, option, assignment/exercise, settlement, external, trapped, protective, and Final Quantity Proof behavior;
- independent risk-model, scenario-completeness, numerical, source/snapshot, common-mode, policy/limit, authority-separation, RCL-binding, stale-evaluator, final-egress, restore, and automatic-rearm security and safety assessment.

### ADR-002-022

Requires:

- AFG-EV-001 through AFG-EV-012;
- RC-EV-001 through RC-EV-005, RC-EV-009, RC-EV-012, RC-EV-013, RC-EV-017, and RC-EV-018;
- RCLP-EV-001 through RCLP-EV-012, EGRESS-EV-001 through EGRESS-EV-012, ARE-EV-002, ARE-EV-003, ARE-EV-008 through ARE-EV-012, IOC-EV-006, IOC-EV-008, IOC-EV-009, and IOC-EV-012;
- BC-EV-001 through BC-EV-005, BC-EV-009 through BC-EV-017, BC-EV-020 through BC-EV-022, FD-EV-002 through FD-EV-005, FD-EV-007, FD-EV-010 through FD-EV-012, PR-EV-003, PR-EV-004, PR-EV-007 through PR-EV-012, TIME-EV-001 through TIME-EV-010, SBR-EV-002 through SBR-EV-012, and applicable SA, REARM, SPG, HAG, ERI, CII, VTG, NT, and cross-system evidence;
- approved Action Flow Policy, State Snapshot, Decision, Permit, shared-scope/resource-vector, cause-lineage/amplification, atomic economic/action commitment, RCL claim/consumption/quarantine/release, protective reserve/lease, trustworthy-time refill, invalidation, and active final-egress currentness mechanisms;
- approved and measured `B_action_flow_invalid_to_rcl`, `B_action_flow_invalid_to_egress`, `B_action_flow_violation_to_containment`, `MAX_action_flow_state_snapshot_age`, `MAX_action_flow_decision_age`, `MAX_action_flow_permit_age`, `MAX_action_amplification_per_cause`, and applicable broker, capability-claim, HALT, recovery, evidence, queue, in-flight, refill, and protective bounds;
- broker-scoped assurance for every claimed submit, cancel, amend, replace, retry, query, reconnect, session, credential, route, endpoint, queue, in-flight, rate, burst, idempotency, throttle, and Protective Flow Reserve behavior;
- independent scope-aggregation, counter/refill, RCL atomicity, permit single-use, cause-amplification, retry/reconnect, protective-reserve, common-mode, authority-separation, final-egress, restore, and automatic-rearm security and safety assessment.

### ADR-002-023

Requires:

- IAP-EV-001 through IAP-EV-012;
- CII-EV-001 through CII-EV-012, VTG-EV-001 through VTG-EV-012, IOC-EV-001 through IOC-EV-012, and applicable ARE, AFG, HAG, ERI, SBR, TIME, RCLP, EGRESS, RC, SA, BC, FD, and cross-system evidence;
- approved Trading Approval Policy, Proposal Approval Request, Independent Approval Decision, Approval Consumption Record, deterministic evaluator/verifier, independent validation-path allocation, common-mode taxonomy, residual-risk scope-reduction, Trading Approval Generation, Intent Registry single-use transaction, writer fencing, invalidation closure, and active final-egress currentness mechanisms;
- approved and measured `B_approval_invalid_to_intent`, `B_approval_invalid_to_egress`, `B_approval_generation_fence`, `MAX_proposal_approval_request_age`, `MAX_independent_approval_decision_age`, and applicable context, venue, construction, capability-claim, HALT, recovery, evidence, broker, and send-race bounds;
- security assessment of proposer/approver common mode, canonicalization/parser differential, policy/evaluator/dependency-registry compromise, duplicate consumption, stale writer, direct route, cache currentness, restore, replay, and automatic re-arm;
- proof that `APPROVE` creates only one exact Intent registration eligibility and never capacity, protective classification, Live Authorization, Transmission Capability, broker transmission, HALT clear, or re-arm.

### ADR-002-024

Requires:

- CUR-EV-001 through CUR-EV-012;
- RCLP-EV-001 through RCLP-EV-012, EGRESS-EV-001 through EGRESS-EV-012, and applicable SA, TIME, REARM, SBR, CII, VTG, IOC, ARE, AFG, IAP, ERI, FD, BC, RC, HAG, and cross-system evidence;
- approved Currentness Policy, complete owner/dependency registry, Currentness Ordering Domain, Safety Currentness Vector, Restrictive Fence Record, independent restrictive ingress, monotonic Local Restrictive Latch, Egress Currentness Proof, per-send proof/claim transaction, cross-domain barrier, first-byte ordering, stale-generation hard fence, and recovery protocol;
- approved and measured `B_currentness_gap_to_local_deny`, `B_restrictive_fence_commit`, `B_currentness_fence_to_egress`, `B_currentness_proof_issue`, `B_currentness_generation_fence`, `MAX_egress_currentness_proof_age_ms`, `MAX_currentness_vector_age_ms`, and every applicable owner-invalidation, revocation, HALT, claim-to-send, hard-fence, partition, evidence, and recovery bound;
- security assessment of owner/sequencer compromise, parser differential, restrictive suppression/spoofing, proof replay/substitution, local-latch bypass, broker-reachable partition, alternate route, stale restore, cross-domain proof union, and administrative common mode;
- proof that currentness artifacts establish only exact non-authorizing facts, RCL remains the sole capacity authority, final egress remains the sole transmission enforcement point, UNKNOWN stays conservative, and recovery never auto-rearms.

### ADR-002-025

Requires:

- RLP-EV-001 through RLP-EV-012 at the specified non-live levels, plus applicable RCLP, EGRESS, SPG, HAG, ERI, SBR, CII, VTG, IOC, ARE, AFG, IAP, CUR, RC, SA, BC, FD, TIME, REARM, PR, NT, and cross-system evidence;
- approved canonical Trial Policy, Trial Plan, Trial Evidence Package, Coverage Claim, and Production Scope Promotion Decision schemas and deterministic validation;
- approved plan/run/action/abort/evidence/promotion ordering, exact scope registry, worst-credible-effect calculation, RCL binding, final-egress currentness, stale-generation fencing, independent abort/HALT path, evidence completeness, non-extrapolation, single-use promotion, demotion, recovery, and continuous-conformance mechanisms;
- approved and measured `B_trial_abort_to_authority_revoke`, `B_trial_abort_to_egress_deny`, `B_trial_evidence_gap_to_containment`, `B_scope_promotion_generation_fence`, `MAX_trial_authorized_economic_effect`, `MAX_trial_concurrent_potential_effect`, `MAX_trial_action_count`, `MAX_trial_duration_ms`, `MAX_trial_evidence_age_ms`, and every applicable upstream bound;
- security assessment of effective-principal collapse, plan/evidence/promotion substitution, alternate broker routes, abort suppression, negative-evidence deletion, optional stopping, scope union, promotion replay, stale restore, monitor compromise, and automatic re-arm;
- proof that accepting this governance mechanism remains non-live and non-authorizing. A specific EV-L5 trial is a later separately authorized execution gate.

### ADR-002-026

Requires:

- WDR-EV-001 through WDR-EV-012 at the specified non-live levels, plus applicable SPG, HAG, ERI, SBR, CUR, RCLP, EGRESS, CII, VTG, IOC, ARE, AFG, IAP, RLP, RC, SA, BC, FD, TIME, REARM, PR, NT, and cross-system evidence;
- approved canonical Safety Deviation Policy, Request, Decision, Residual-Risk Acceptance Record, Active Deviation Set, requirement/hazard registry, Non-Waivable Boundary, dependency-closure, combined-risk, compensating-control, and evidence-status contracts;
- approved Effective Principal quorum/conflict, single-use decision consumption, exact restricted-configuration activation, Deviation Generation, restrictive revocation, final-egress currentness, expiry, renewal, rollback, recovery, and non-revival mechanisms;
- approved and measured `B_deviation_revoke_to_authority`, `B_deviation_revoke_to_egress`, `B_deviation_generation_fence`, `MAX_deviation_duration_ms`, `MAX_deviation_decision_age_ms`, `MAX_residual_risk_review_interval_ms`, and every applicable upstream bound;
- security assessment of requirement/policy/registry manipulation, effective-person collapse, reviewer/configuration/armer common mode, compensation common mode, decision replay, active-set omission or union, stale cache, expiry suppression, predecessor restore, break-glass or alternate-route bypass, evidence relabeling, and automatic re-arm;
- proof that accepting this governance mechanism accepts no specific deviation, marks no evidence `PASS`, and remains non-live and non-authorizing.

### ADR-002-027

Requires:

- SIR-EV-001 through SIR-EV-012 at the specified non-live levels, plus applicable HAG, ERI, SBR, CUR, RCLP, EGRESS, SPG, RLP, WDR, CII, VTG, IOC, ARE, AFG, IAP, RC, SA, BC, FD, TIME, REARM, PR, NT, and cross-system evidence;
- approved canonical Safety Incident Policy, Safety Incident Record, Active Safety Incident Set, Incident Containment Plan with Controlled Shutdown Procedure, Incident Recovery Handoff Package, and Incident Closure Decision schemas;
- approved signal/source classifier, severity/materiality rules, greatest-credible dependency closure, multi-incident/common-mode composition, Incident Generation registry and writer fence, independent restrictive ingress, local latch, active final-egress currentness, controlled-shutdown ordering, external/manual activity treatment, explicit Recovery Session handoff, and independent closure mechanisms;
- approved and measured `B_incident_signal_to_authority_restrict`, `B_incident_signal_to_egress_deny`, `B_incident_scope_expansion_to_egress_deny`, `B_incident_generation_fence`, `B_controlled_shutdown_hard_fence`, `B_incident_handoff_to_recovery_barrier`, `MAX_incident_scope_snapshot_age_ms`, `MAX_incident_containment_plan_age_ms`, `MAX_incident_recovery_handoff_age_ms`, `MAX_incident_closure_decision_age_ms`, and every applicable upstream bound;
- security assessment of signal suppression/spoofing/downgrade, scope self-exemption, active-set omission/substitution, stale coordinator/restore, incident-plane partition, direct route, shutdown queue drain, process-stop-as-fence, closure replay, evidence deletion, same-effective-person closure, incomplete handoff, and automatic re-arm;
- proof that incident declaration and scope expansion restrict before investigation, controlled shutdown preserves economic/protection/evidence obligations, closure is administrative and non-permissive, RCL and final egress remain exclusive, and no incident artifact restores authority or scope.

### ADR-002-028

Requires:

- STM-EV-001 through STM-EV-012 at the specified non-live levels, plus applicable CII, TIME, ERI, CUR, RLP, SIR, WDR, SBR, HAG, FD, RCLP, EGRESS, AFG, RC, SA, BC, REARM, and cross-system evidence;
- approved canonical Safety Monitoring Policy, Critical Telemetry Manifest, Monitor Coverage Manifest, Continuous Conformance Snapshot, Safety Monitoring Gap, Safety Alert Record, and Alert Escalation Record schemas;
- approved requirement/hazard/control registry, source continuity and semantic contracts, deterministic evaluator and independent verifier, effective-independence taxonomy, Monitor Generation registry and writer fence, restrictive ingress, suppression governance, alert correlation/deduplication, bounded delivery/escalation, incident handoff, recovery, and final-egress currentness mechanisms;
- approved and measured `B_safety_telemetry_loss_detect`, `B_monitoring_gap_to_authority_restrict`, `B_monitoring_gap_to_egress_deny`, `B_critical_alert_delivery`, `B_alert_escalation`, `B_monitoring_generation_fence`, `MAX_critical_telemetry_age_ms`, `MAX_continuous_conformance_snapshot_age_ms`, `MAX_safety_alert_age_ms`, `MAX_monitoring_suppression_duration_ms`, `MAX_alert_acknowledgement_age_ms`, and every applicable upstream bound;
- security assessment of source/evaluator/registry compromise, semantic and parser drift, common-mode independence, threshold weakening, suppression abuse, deduplication scope loss, alert storm and provider failure, stale writer/restore, monitoring-plane partition, alternate broker route, final-egress cache, recovery, and automatic re-arm;
- proof that monitoring is a non-authorizing negative gate, absence of alert is not health, gaps restrict without releasing capacity, alert acknowledgement is not containment, evidence is not prevention, and recovery never revives prior authority.

### ADR-002-029

Requires:

- SCI-EV-001 through SCI-EV-012 at the specified non-live levels, plus applicable SPG, HAG, ERI, SBR, CII, IOC, CUR, RLP, WDR, SIR, STM, FD, RCLP, EGRESS, AFG, RC, SA, BC, TIME, REARM, and cross-system evidence;
- approved canonical Software Release Policy, Source Revision Manifest, Dependency and Toolchain Closure Manifest, Build Provenance Attestation, Release Artifact Manifest, Artifact Admission Decision, Admitted Release Set, and Runtime Artifact Attestation schemas;
- approved source/review, isolated build, dependency/toolchain resolver, signer/key, immutable registry, deterministic independent admission, Release Generation registry and writer fence, deployment/runtime attestation, compatibility, restriction, recovery, and final-egress currentness mechanisms;
- approved and measured `B_supply_chain_compromise_detect`, `B_release_restriction_to_authority_restrict`, `B_release_restriction_to_egress_deny`, `B_release_generation_fence`, `B_runtime_artifact_drift_detect`, `MAX_build_provenance_age_ms`, `MAX_artifact_admission_decision_age_ms`, `MAX_admitted_release_set_age_ms`, `MAX_runtime_artifact_attestation_age_ms`, `MAX_release_key_status_age_ms`, and every applicable upstream bound;
- security assessment of repository history rewrite, omitted source/build/dependency closure, builder and registry compromise, signer/key rollback, effective-control collapse, substitution and TOCTOU, mixed versions, runtime drift, stale writer/deployment, supply-chain partition, direct broker route, restore, hotfix, recovery, and automatic re-arm;
- proof that admission is a non-authorizing negative gate, signatures/scans/tests/SBOM/deployment health do not create permission, exact actual runtime bytes are current at final egress, economic effect and broker finality survive software expiry/revocation, and recovery never revives prior admission or authority.

### ADR-002-030

Requires:

- PTF-EV-001 through PTF-EV-012 at the specified non-live levels, plus applicable RC, RECON, NT, CII, VTG, IOC, ARE, AFG, IAP, CUR, RCLP, EGRESS, ERI, SBR, STM, SCI, FD, BC, TIME, REARM, and cross-system evidence;
- approved canonical Post-Trade Finality Policy, Economic Obligation Record, Active Economic Obligation Set, Post-Trade Finality Proof, Post-Trade Break Record, and Statement Coverage Manifest schemas;
- approved obligation compiler and independent verifier, PTOL serializer and writer fence, Post-Trade Obligation Generation, source-authority and statement-coverage rules, class-specific finality recipes, correction/reopen protocol, PTOL-to-RCL ordered transition, active currentness, recovery, and external-instruction final-egress mechanisms;
- approved and measured `B_post_trade_effect_to_obligation_commit`, `B_post_trade_change_detect`, `B_post_trade_break_to_restrict`, `B_post_trade_invalid_to_egress_deny`, `B_post_trade_generation_fence`, `B_statement_coverage_gap_detect`, `MAX_post_trade_obligation_snapshot_age_ms`, `MAX_post_trade_finality_proof_age_ms`, `MAX_statement_coverage_manifest_age_ms`, `MAX_unresolved_post_trade_break_age_ms`, `MAX_pending_external_transfer_age_ms`, and every applicable upstream bound;
- security assessment of obligation omission/substitution, statement truncation/revision/common mode, PTOL/RCL writer compromise, finality-proof replay, correction suppression, favorable netting, collateral double use, stale generation, post-trade partition, external credential/route bypass, restore, recovery, and automatic re-arm;
- proof that PTOL is only the obligation-lifecycle serializer, RCL remains sole capacity mutation/serialization authority, final egress remains the external transmission enforcement point, missing ACK and Cancel ACK semantics remain conservative, field-specific finality and economic continuity survive expiry, and recovery never revives prior finality or authority.

### Restricted-Live Trial Gate

Requires:

- ADR-002-025 and every applicable upstream ADR Accepted for the exact scope;
- one current approved Trial Policy and immutable eligible Trial Plan with exact scope, baseline, maximum credible effect, count/duration/action envelope, evidence plan, abort triggers, recovery disposition, and independent reviewers;
- approved Verification Profile numeric bounds, current Broker Capability Profile, Hard Safety Envelope, Runtime Safety Profile, Human Authority Policy, Failure-Domain Allocation Matrix, and Currentness Policy;
- no failed, inconclusive, stale, missing, contradicted, or unreviewed prerequisite Critical evidence;
- worst credible trial effect committed by RCL and complete normal approval, configuration, Live Authorization, Transmission Capability, action-flow, currentness, and final-egress prerequisites;
- tested independent abort, HALT, egress denial, evidence, reconciliation, and recovery paths;
- explicit single-run human authorization. This gate authorizes only that exact run and never automatic resume or promotion.

### Production Scope Promotion Gate

Requires:

- one complete immutable EV-L5 Trial Evidence Package for the exact Trial Run, including all negative, failed, aborted, conflicting, and inconclusive evidence;
- independent evidence-integrity, coverage, broker-semantic, security, capacity, currentness, abort, recovery, and residual-risk review;
- no extrapolation, scope union, post-hoc metric or stop-rule change, hidden run, unresolved Critical result, or stale generation;
- one current exact `ELIGIBLE_TO_REQUEST_NEW_SCOPE` decision consumed once for a policy-approved promotion delta;
- break-before-make configuration activation, predecessor fencing, reconciliation, fresh governed re-arm, Live Authorization, and per-send final-egress enforcement;
- explicit production authorization and EV-L6 continuous conformance. Promotion eligibility, activation, monitoring recovery, or incident-free time is not production authority.

---

## 381. Current Evidence Readiness Assessment

As of 2026-07-14:

```text
Evidence specification: REGISTERED; NOT EXECUTED
Evidence register: CREATED
Test harness: NOT ASSESSED
Implementation instrumentation: NOT ASSESSED
Aggregate capacity evidence: NOT EXECUTED
Safety Authority evidence: NOT EXECUTED
Broker capability evidence: NOT EXECUTED
Cross-system evidence: NOT EXECUTED
Trustworthy Time evidence: NOT EXECUTED
Live Authorization and re-arm evidence: NOT EXECUTED
Orthogonal trading state evidence: NOT EXECUTED
Evidence and reconciliation confidence evidence: NOT EXECUTED
Failure-domain isolation evidence: NOT EXECUTED
Protective replacement evidence: NOT EXECUTED
Corporate action and non-trade evidence: NOT EXECUTED
RCL persistence, consensus, and writer-fencing evidence: NOT EXECUTED
Egress credential, route, Commit-Proof, and hard-fence evidence: NOT EXECUTED
Safety profile and Hard Safety Envelope governance evidence: NOT EXECUTED
Human authority, dual-control, HALT, and break-glass governance evidence: NOT EXECUTED
Evidence integrity, audit, gap, retention, and deterministic replay evidence: NOT EXECUTED
Safe startup, Recovery Barrier, conservative inventory, and readiness evidence: NOT EXECUTED
Critical Input integrity, provenance, independent approval, context binding, and invalidation evidence: NOT EXECUTED
Venue, session, tradability, exact order constraint, and final-egress currentness evidence: NOT EXECUTED
Intent-to-order conformance, canonical command, economic-effect, and actual-outbound evidence: NOT EXECUTED
Aggregate risk projection, adverse-scenario, exact allocation-decision, and currentness evidence: NOT EXECUTED
Action-flow budgeting, retry-storm containment, protective-reserve, and permit-currentness evidence: NOT EXECUTED
Independent proposal approval, single-use Intent consumption, invalidation, and currentness evidence: NOT EXECUTED
Active currentness, restrictive-fence, local-latch, per-send proof, and claim/send-ordering evidence: NOT EXECUTED
Restricted-live trial, evidence coverage, abort, promotion, demotion, and production-authorization governance evidence: NOT EXECUTED
Safety waiver, deviation, compensating-control, residual-risk, expiry, and currentness governance evidence: NOT EXECUTED
Safety incident declaration, scope, containment, controlled-shutdown, recovery-handoff, closure, and currentness governance evidence: NOT EXECUTED
Safety telemetry, monitor coverage, continuous-conformance, gap, suppression, alert-delivery, escalation, and currentness governance evidence: NOT EXECUTED
Software supply-chain, build provenance, dependency/toolchain closure, release admission, deployment, runtime-attestation, and currentness evidence: NOT EXECUTED
Post-trade economic-obligation, settlement, finality, statement-coverage, correction, capacity-coupling, and currentness evidence: NOT EXECUTED
Independent review: NOT STARTED
Production authorization: NO
```

This status is intentionally strict. The documents define completion criteria; they do not replace execution.

---

## 382. Required Next Execution Sequence

```text
1. Assign implementation owner, evidence owner, and independent reviewer for every registered item.
2. Approve the Verification Profile bounds and scope.
3. Implement trace and evidence identities.
4. Implement model/property tests for all ADR-002 capacity, consensus, state, authority, time, failure-domain, replacement, non-trade, final-egress security, safety-configuration governance, human-authority governance, evidence-integrity/replay, safe-start/recovery-barrier, Critical Input/context-integrity, venue/session/tradability-constraint, Intent-to-order conformance, aggregate-risk evaluation, action-flow governance, independent proposal-approval, active-currentness, restricted-live/promotion-governance, safety-deviation/residual-risk-governance, safety-incident/controlled-shutdown-governance, safety-telemetry/continuous-monitoring-governance, software-supply-chain/runtime-artifact-admission, and post-trade economic-obligation/finality models.
5. Build deterministic fault-injection harness.
6. Complete one broker Capability Profile at document/evidence level.
7. Execute component tests.
8. Execute integrated fault tests.
9. Execute broker sandbox tests where meaningful.
10. Execute an approved ADR-002-025 restricted-live trial only after its exact separate human gate; do not infer production promotion.
11. Run independent evidence review.
12. Update ADR status only after gates pass.
```

---

## 383. Verification Specification Approval Gate

VER-002-001 may move from **Proposed** to **Approved for Execution** when:

- every Critical RFC/ADR invariant maps to at least one evidence item in the instantiated coverage matrix (verification/TRACEABILITY-MATRIX-002.md);
- the instantiated bidirectional coverage matrix (verification/TRACEABILITY-MATRIX-002.md) is complete, with every Critical SAFE/HAZ resolving to ≥1 evidence item or an UNMAPPED entry recorded as accepted debt in ARCHITECTURE-GATE-STATUS;
- Verification Profile schema is approved;
- evidence package format is implemented;
- artifact integrity and reviewer sign-off workflow exist;
- fault-injection responsibilities are assigned;
- broker production-test safety rules are approved;
- evidence retention and access controls are defined.

Approval for execution does not authorize live trading.

---

# Part XXXVI — Part-2/3 Register Consolidation (Wave 4): Newly Registered Part-1 Evidence

**Wave-4 note (2026-07-17).** The Part-2/3 register consolidation
(CORPUS-REVIEW-0001 CR-01) registered HAG-EV-013 through HAG-EV-018,
EGRESS-EV-013, and PRD-EV-001/PRD-EV-002 as §§384–392 below and updated the
ADR-002-001, ADR-002-013, and ADR-002-015 approval gates in §380. The Evidence
Register count is now 372. These nine cases discharge the
ARCHITECTURE-GATE-STATUS §4.2/§4.3/§4.4 evidence debt. All remain
`NOT_IMPLEMENTED`; registration is not execution and grants no live readiness.

## 384. HAG-EV-013 — Governed Single-Operator Variant Pre-Approved and Non-Ad-Hoc
- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-INV-015 (§17.1); RFC-001 SAFE-053
- **Injection:** Invoke the single-operator re-arm variant with no pre-approved explicit mode, or an ad-hoc/patched/post-hoc variant definition, across concurrent and failover paths.
- **Expected:** Only a pre-approved, explicitly declared variant mode is eligible; ad-hoc/unregistered/post-hoc variants are denied and grant no authority.

## 385. HAG-EV-014 — Time-Separated Re-Authenticated Self-Approval
- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-INV-016 (§17.1); RFC-001 SAFE-053
- **Injection:** Attempt the variant's self-approval steps within one session, without the required time separation, or without fresh re-authentication at each step.
- **Expected:** Each step requires the mandated time separation and a fresh re-authentication; a collapsed-in-time or single-authentication self-approval is denied and fails closed.

## 386. HAG-EV-015 — Independent Attestation Mandatory and Block-Only
- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-INV-017 (§17.1); RFC-001 SAFE-053
- **Injection:** Present the variant with a missing, unavailable, or indeterminate independent attestation, and attempt to treat an attestation as an authority-granting (rather than block-only) input.
- **Expected:** Independent attestation is mandatory and block-only; a missing/unavailable/indeterminate attestation fails closed, and attestation can only block, never grant authority.

## 387. HAG-EV-016 — External Reviewer Independence
- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-INV-018 (§17.1); RFC-001 SAFE-053
- **Injection:** Supply an external reviewer whose effective principal collapses into the operator's (§8 collapse), or who shares the operator's identity, credentials, or control.
- **Expected:** The external reviewer must be effectively independent of the operator; a collapsed or shared principal is rejected and the variant fails closed.

## 388. HAG-EV-017 — Variant Cannot Expand Authority or Scope
- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-015 HAG-INV-019 (§17.1); RFC-001 SAFE-053
- **Injection:** Use the variant to widen scope, relax a gate, or waive a Hard Safety Envelope constraint beyond the smallest approved scope delta.
- **Expected:** The variant expands no authority, scope, gate, or envelope; any attempted widening is denied and grants no new-risk authority.

## 389. HAG-EV-018 — Operator Configuration or Authorization Error Fail-Closed
- **Minimum Level:** EV-L2/EV-L3 plus security assessment
- **Supports:** ADR-002-015 §17.1; RFC-001 SAFE-042, SAFE-046, SAFE-050, SAFE-053; HAZ-024
- **Injection:** Inject wrong-account, wrong-arming, mis-authorization, and misconfiguration paths through the operator/human authority surface.
- **Expected:** The controlling requirements (SAFE-042/046/050/053) prevent each path and fail closed; an operator configuration or authorization error confers no live readiness.

## 390. EGRESS-EV-013 — Out-of-Band Containment of a Defective or Compromised Final Egress Point
- **Minimum Level:** EV-L3/EV-L5 plus broker and security assessment
- **Supports:** ADR-002-013; RFC-001 SAFE-054; HAZ-025
- **Injection:** Defect or compromise the final egress enforcement point and require containment of its real-capital transmission capability, established in Broker Capability Profile terms without dependence on any named broker.
- **Expected:** An out-of-band containment path independent of the final egress point terminates its transmission capability, or its absence is recorded and accepted as residual risk with a correspondingly reduced live scope; no named broker is assumed.

## 391. PRD-EV-001 — Protective-Resource-Domain Enumeration Completeness
- **Minimum Level:** EV-L1/EV-L3 plus broker
- **Supports:** ADR-002-001 §21 criterion #1
- **Probe:** Inspect whether protective resource domains are enumerated completely for each supported broker and market, gated by an approved Broker Capability Profile and Safety Profile per domain.
- **Expected:** Every protective-resource domain is enumerated for each supported broker/market; an incomplete enumeration fails closed and grants no acceptance.

## 392. PRD-EV-002 — Per-Resource Guarantee-Level Assignment Completeness
- **Minimum Level:** EV-L1/EV-L3
- **Supports:** ADR-002-001 §21 criterion #11
- **Probe:** Inspect whether every protective resource is assigned an evidenced guarantee level through the Safety Profile artifact.
- **Expected:** Every protective resource carries an assigned, evidenced guarantee level; a missing assignment fails closed and grants no acceptance.

Approval for execution does not authorize live trading.
