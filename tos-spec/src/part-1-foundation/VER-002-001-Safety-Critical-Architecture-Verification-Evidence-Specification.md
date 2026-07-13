# VER-002-001 — Safety-Critical Architecture Verification Evidence Specification

- **Status:** Proposed — Ready for Test Implementation
- **Date:** 2026-07-13
- **Verification Scope:** RFC-002 v0.2 patch; ADR-002-001 v0.2; ADR-002-002; ADR-002-003; ADR-002-004
- **Current Evidence State:** Specification complete; implementation evidence not yet executed
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

Each acceptance criterion SHALL state the minimum evidence level. A lower level cannot substitute for a required higher level.

---

## 6. Verification Profile

Numeric bounds SHALL be stored in an approved Verification Profile rather than embedded as arbitrary values in the ADRs.

The profile SHALL define at least:

```text
B_authority_partition_detect
B_risk_increase_revoke
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
B_operator_escalation
B_evidence_persist
MAX_normal_capability_age
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
13. reconciliation evidence and confidence bounds;
14. mode transitions;
15. metrics and alerts;
16. invariant-evaluation report;
17. final-state snapshot;
18. pass/fail decision;
19. reviewer identity and review result;
20. artifact digests and chain-of-custody record.

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
      broker-raw/
      reconciliation/
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

## 78. Model-Based and Property Verification

Before restricted live operation, the following state models SHALL be explored with model checking or equivalent exhaustive/bounded analysis:

- capacity reservation and release;
- concurrent writer and epoch fencing;
- send/ACK/fill/cancel/replace ordering;
- Safety Authority failover and partition;
- degraded protective lease ownership;
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
```

Counterexamples SHALL be stored as evidence and converted into deterministic regression tests.

---

## 79. Fault-Injection Requirements

The test harness SHALL support controlled injection at least for:

- process kill and restart;
- pause/GC-like suspension;
- network partition by direction;
- message drop, duplicate, delay, and reorder;
- datastore leader failover;
- stale read;
- broker response loss;
- fill/cancel ordering;
- clock step and monotonic discontinuity simulation;
- rate-limit saturation;
- credential revocation;
- stale deployment reactivation;
- query omission and pagination truncation;
- external manual activity;
- corporate-action event.

Fault injection SHALL identify the exact boundary at which it acted.

---

## 80. Broker Verification Safety Rules

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

## 81. Continuous Conformance Evidence

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
- automatic or unauthorized re-arm.

A continuous violation invalidates the corresponding evidence item and may revert the ADR/profile status to `EXPIRED` or `CONTRADICTORY`.

---

## 82. Residual Risk Register

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

## 83. Independent Review Checklist

The reviewer SHALL confirm:

- test matched the stated baseline;
- fault was actually injected;
- required evidence was captured;
- pass condition was not inferred from missing data;
- raw and normalized broker evidence agree or conflicts are handled conservatively;
- invariant evaluation covers every risk dimension;
- containment bounds are measured, not assumed;
- no manual cleanup occurred before final evidence capture;
- failed and inconclusive runs are retained;
- residual risk does not contradict RFC-000/RFC-001;
- live scope matches the tested capability profile.

---

## 84. Approval Gates by ADR

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

## 85. Current Evidence Readiness Assessment

As of 2026-07-13:

```text
Evidence specification: COMPLETE
Evidence register: CREATED
Test harness: NOT ASSESSED
Implementation instrumentation: NOT ASSESSED
Aggregate capacity evidence: NOT EXECUTED
Safety Authority evidence: NOT EXECUTED
Broker capability evidence: NOT EXECUTED
Cross-system evidence: NOT EXECUTED
Independent review: NOT STARTED
Production authorization: NO
```

This status is intentionally strict. The documents define completion criteria; they do not replace execution.

---

## 86. Required Next Execution Sequence

```text
1. Implement trace and evidence identities.
2. Implement model/property tests for capacity and authority state machines.
3. Build deterministic fault-injection harness.
4. Complete one broker Capability Profile at document/evidence level.
5. Execute component tests.
6. Execute integrated fault tests.
7. Execute broker sandbox tests where meaningful.
8. Execute approved restricted production capability probes.
9. Run independent evidence review.
10. Update ADR status only after gates pass.
```

---

## 87. Verification Specification Approval Gate

VER-002-001 may move from **Proposed** to **Approved for Execution** when:

- every Critical RFC/ADR invariant maps to at least one evidence item;
- Verification Profile schema is approved;
- evidence package format is implemented;
- artifact integrity and reviewer sign-off workflow exist;
- fault-injection responsibilities are assigned;
- broker production-test safety rules are approved;
- evidence retention and access controls are defined.

Approval for execution does not authorize live trading.
