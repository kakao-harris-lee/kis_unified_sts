# VER-002-001 — Safety-Critical Architecture Verification Evidence Specification

- **Status:** Proposed — Ready for Test Implementation
- **Date:** 2026-07-13
- **Verification Scope:** Consolidated RFC-002 v0.2; consolidated ADR-002-001 v0.2; ADR-002-002 through ADR-002-011
- **Current Evidence State:** Dedicated acceptance-case evidence specifications are registered for ADR-002-005 through ADR-002-011; implementation evidence has not been executed
- **Extension State:** ADR-002-005/006/007/008/009/010/011 map one-to-one to STATE-EV-001..005, RECON-EV-001..005, REARM-EV-001..012, TIME-EV-001..010, FD-EV-001..012, NT-EV-001..012, and PR-EV-001..012. Registration is not completed evidence
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
- Short forms such as `EV-L2/3` mean `EV-L2/EV-L3`. Combined forms such as `EV-L1/3+Broker` apply both rules: staged EV-L1/EV-L3 evidence plus the required broker evidence.
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
B_time_health_to_egress
B_capability_claim_to_send
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
MAX_normal_capability_age
MAX_time_health_snapshot_age
MAX_degraded_lease_holdover
MAX_clock_drift
MAX_process_suspension
MAX_unresolved_send_per_scope
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
18. mode transitions;
19. metrics and alerts;
20. invariant-evaluation report;
21. final-state snapshot;
22. pass/fail decision;
23. reviewer identity and review result;
24. artifact digests and chain-of-custody record.

Redaction SHALL preserve fields needed to verify identity, ordering, quantity, and economic effect.

---

## 8. Evidence Package Structure

A recommended evidence package is:

```text
evidence/
  manifest.yaml
  baseline.yaml
  verification-profile.yaml
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
- **Sequence:** context validation → proposal → approval → capacity commitment → capability → egress → fill → reconciliation → capacity transfer.
- **Expected:** One traceable identity chain; all state transitions and invariants correct.

## 67. X-EV-002 — Safety Authority Failover During Commit

- **Minimum Level:** EV-L3
- **Injection:** Advance Safety Authority epoch while a capacity commit and transmission binding are in progress.
- **Expected:** No stale capability can authorize transmission; committed capacity remains consistent.

## 68. X-EV-003 — Ledger Failover During Authority Partition

- **Minimum Level:** EV-L3
- **Expected:** No new normal commitment; protective consumption only under exclusive valid lease; no double consumption.

## 69. X-EV-004 — ACK Loss Plus External Manual Order

- **Minimum Level:** EV-L3/EV-L5
- **Expected:** Ambiguity expands containment scope; no duplicate retry or optimistic attribution.

## 70. X-EV-005 — Protective Action Under Broker Saturation

- **Minimum Level:** EV-L3/EV-L5
- **Expected:** Actual latency and success match declared guarantee; otherwise system contains and records residual failure.

## 71. X-EV-006 — Cancel/Replace During Safety HALT

- **Minimum Level:** EV-L3
- **Expected:** HALT blocks new risk but does not blindly remove risk-reducing protection; cancellation arbiter applies.

## 72. X-EV-007 — Restart With Live UNKNOWN Orders

- **Minimum Level:** EV-L3
- **Expected:** Startup barrier prevents re-arm; unknown capacity remains quarantined.

## 73. X-EV-008 — Clock Failure During Degraded Protection

- **Minimum Level:** EV-L3
- **Expected:** Lease invalidates; prior attempts remain tracked; no new protective transmission.

## 74. X-EV-009 — Deployment Rollback Restores Stale Instance

- **Minimum Level:** EV-L3
- **Expected:** Old build/epoch/profile cannot mutate or transmit.

## 75. X-EV-010 — Corporate Action During Open Order

- **Minimum Level:** EV-L3
- **Expected:** Order, position, multiplier, and capacity uncertainty causes containment until remapped.

## 76. X-EV-011 — Broker Capability Drift During Live Session

- **Minimum Level:** EV-L3/EV-L5
- **Expected:** Active profile degrades; egress rejects dependent actions; potentially-live effects remain conserved.

## 77. X-EV-012 — Recovery and Partial Re-arm

- **Minimum Level:** EV-L3
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

## 146. Model-Based and Property Verification

Before restricted live operation, the following state models SHALL be explored with model checking or equivalent exhaustive/bounded analysis:

- capacity reservation and release;
- concurrent writer and epoch fencing;
- send/ACK/fill/cancel/replace ordering;
- Safety Authority failover and partition;
- degraded protective lease ownership;
- Trustworthy Time health, continuity, snapshot age, and recovery generation;
- Live Authorization, revocation generation, partial scope, and HALT precedence;
- orthogonal state dimensions, conservative direction, and transition ownership;
- field-level evidence confidence, conflict, freshness, and proof rules;
- failure-domain allocation, stale deployment, and Safety Cell containment;
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
```

Counterexamples SHALL be stored as evidence and converted into deterministic regression tests.

---

## 147. Fault-Injection Requirements

The test harness SHALL support controlled injection at least for:

- process kill and restart;
- pause/GC-like suspension;
- network partition by direction;
- message drop, duplicate, delay, and reorder;
- datastore leader failover;
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

## 148. Broker Verification Safety Rules

Controlled production verification SHALL:

- use the smallest approved live scope;
- avoid risk-increasing tests where the property can be demonstrated without them;
- use bounded quantity and pre-approved loss limits;
- have an operator halt path;
- preserve all raw broker evidence;
- isolate manual activity unless the test explicitly targets it;
- predefine abort conditions;
- not rely on test cleanup to preserve safety;
- be approved under the relevant Safety Profile.

A test that requires violating the Hard Safety Envelope is prohibited.

---

## 149. Continuous Conformance Evidence

After approval, continuous monitors SHALL detect at least:

- stale epoch rejection failures;
- capability-profile mismatch;
- broker event/order semantic contradiction;
- external detection bound misses;
- late fills beyond profile;
- unexplained capacity release;
- duplicate broker identity;
- egress bypass attempts;
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

## 150. Residual Risk Register

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

“Broker limitation” is not a sufficient residual-risk description.

---

## 151. Independent Review Checklist

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
- protective gap, overlap, and Final Quantity Proof evidence cover adverse interleavings;
- non-trade transition evidence covers old and new economic effects and corrections;
- no manual cleanup occurred before final evidence capture;
- failed and inconclusive runs are retained;
- residual risk does not contradict RFC-000/RFC-001;
- live scope matches the tested capability profile.

---

## 152. Approval Gates by ADR

### ADR-002-002

Requires:

- RC-EV-001 through RC-EV-018;
- X-EV-001 through X-EV-004, X-EV-007, X-EV-009, and X-EV-012;
- applicable model-based properties;
- independent review.

### ADR-002-003

Requires:

- SA-EV-001 through SA-EV-015;
- X-EV-002, X-EV-003, X-EV-006, X-EV-008, X-EV-009, and X-EV-012;
- authority/fencing security assessment;
- independent review.

### ADR-002-004

Requires:

- BC-EV-001 through BC-EV-022 for each approved broker profile, with `NOT_APPLICABLE` justified by profile scope where valid;
- X-EV-004, X-EV-005, X-EV-010, and X-EV-011;
- restricted production evidence for safety-critical live semantics;
- independent review.

### ADR-002-005

Requires:

- STATE-EV-001 through STATE-EV-005;
- RC-EV-003, RC-EV-004, RC-EV-006 through RC-EV-008, RC-EV-010, RC-EV-011, RC-EV-017, and SA-EV-006;
- model-based exploration of orthogonality, CPL-1 through CPL-7, and conservative direction;
- state-transition ownership security assessment and independent review.

### ADR-002-006

Requires:

- RECON-EV-001 through RECON-EV-005;
- RC-EV-005, RC-EV-007, RC-EV-010, RC-EV-011, SA-EV-011, BC-EV-006, and BC-EV-017;
- approved field-specific proof, freshness, source-independence, and conservative-bound rules;
- reconciliation and evidence-independence review.

### ADR-002-007

Requires:

- REARM-EV-001 through REARM-EV-012;
- SA-EV-009, SA-EV-010, SA-EV-013, BC-EV-015, BC-EV-020, BC-EV-021, X-EV-007, X-EV-009, and X-EV-012;
- approved and measured `B_risk_increase_revoke`, `B_revocation_to_egress`, `B_halt_to_egress`, `MAX_normal_capability_age`, and `B_capability_claim_to_send`;
- authorization/final-egress security assessment and independent review.

### ADR-002-008

Requires:

- TIME-EV-001 through TIME-EV-010;
- SA-EV-005, SA-EV-006, SA-EV-011, and X-EV-008;
- approved and measured `B_time_health_to_egress`, `MAX_time_health_snapshot_age`, and applicable clock, suspension, holdover, freshness, and session bounds;
- time-source/common-mode review and independent review.

### ADR-002-009

Requires:

- FD-EV-001 through FD-EV-012;
- SA-EV-001, SA-EV-002, SA-EV-008, SA-EV-013 through SA-EV-015, BC-EV-015, BC-EV-020, X-EV-002, X-EV-003, and X-EV-009;
- an approved Failure-Domain Allocation Matrix, deployment profile, RCL fencing mechanism, and implementation of the selected ADR-002-007 §§9.1–9.5 egress-currentness protocol;
- failure-domain security assessment and independent review.

### ADR-002-010

Requires:

- NT-EV-001 through NT-EV-012;
- RC-EV-010, RC-EV-015, BC-EV-008, BC-EV-019, X-EV-010, TIME-EV-008, and REARM-EV-003;
- approved source-authority, transition-envelope, RCL remap, event-time, and broker-treatment rules;
- broker-profile evidence for every supported event/instrument scope and independent review.

### ADR-002-011

Requires:

- PR-EV-001 through PR-EV-012;
- RC-EV-005 through RC-EV-008, BC-EV-002, BC-EV-003, BC-EV-007 through BC-EV-010, BC-EV-012 through BC-EV-014, X-EV-005, and X-EV-006;
- approved and measured gap, overlap, Final Quantity Proof, completion, and containment bounds;
- broker-profile evidence for every claimed replacement mode and independent review.

### Production Restricted Live Gate

Requires:

- applicable ADRs Accepted;
- no failed or inconclusive Critical evidence;
- approved Verification Profile;
- active broker profile;
- all residual risks approved;
- operational runbooks and halt/recovery exercises complete;
- explicit production authorization.

---

## 153. Current Evidence Readiness Assessment

As of 2026-07-13:

```text
Evidence specification (registered scope): COMPLETE
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
Independent review: NOT STARTED
Production authorization: NO
```

This status is intentionally strict. The documents define completion criteria; they do not replace execution.

---

## 154. Required Next Execution Sequence

```text
1. Assign implementation owner, evidence owner, and independent reviewer for every registered item.
2. Approve the Verification Profile bounds and scope.
3. Implement trace and evidence identities.
4. Implement model/property tests for all ADR-002 state, authority, time, failure-domain, replacement, and non-trade models.
5. Build deterministic fault-injection harness.
6. Complete one broker Capability Profile at document/evidence level.
7. Execute component tests.
8. Execute integrated fault tests.
9. Execute broker sandbox tests where meaningful.
10. Execute approved restricted production capability probes only after their separate human gate.
11. Run independent evidence review.
12. Update ADR status only after gates pass.
```

---

## 155. Verification Specification Approval Gate

VER-002-001 may move from **Proposed** to **Approved for Execution** when:

- every Critical RFC/ADR invariant maps to at least one evidence item;
- Verification Profile schema is approved;
- evidence package format is implemented;
- artifact integrity and reviewer sign-off workflow exist;
- fault-injection responsibilities are assigned;
- broker production-test safety rules are approved;
- evidence retention and access controls are defined.

Approval for execution does not authorize live trading.
