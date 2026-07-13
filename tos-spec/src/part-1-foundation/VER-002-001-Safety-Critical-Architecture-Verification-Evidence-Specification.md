# VER-002-001 — Safety-Critical Architecture Verification Evidence Specification

- **Status:** Proposed — Ready for Test Implementation
- **Date:** 2026-07-13
- **Verification Scope:** Consolidated RFC-002 v0.2; consolidated ADR-002-001 v0.2; ADR-002-002 through ADR-002-016
- **Current Evidence State:** Dedicated acceptance-case evidence specifications are registered for ADR-002-005 through ADR-002-016; implementation evidence has not been executed
- **Extension State:** ADR-002-005/006/007/008/009/010/011/012/013/014/015/016 map one-to-one to STATE-EV-001..005, RECON-EV-001..005, REARM-EV-001..012, TIME-EV-001..010, FD-EV-001..012, NT-EV-001..012, PR-EV-001..012, RCLP-EV-001..012, EGRESS-EV-001..012, SPG-EV-001..012, HAG-EV-001..012, and ERI-EV-001..012. Registration is not completed evidence
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
24. mode transitions;
25. metrics and alerts;
26. invariant-evaluation report;
27. final-state snapshot;
28. pass/fail decision;
29. reviewer identity and review result;
30. artifact digests and chain-of-custody record.

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
- **Expected:** Every attempt is denied before broker acceptance, triggers evidence and containment where appropriate, and cannot borrow the current gateway's signer, session, credential, or route.

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

## 206. Model-Based and Property Verification

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
```

Counterexamples SHALL be stored as evidence and converted into deterministic regression tests.

---

## 207. Fault-Injection Requirements

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

## 208. Broker Verification Safety Rules

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

## 209. Continuous Conformance Evidence

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

## 210. Residual Risk Register

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

## 211. Independent Review Checklist

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
- protective gap, overlap, and Final Quantity Proof evidence cover adverse interleavings;
- non-trade transition evidence covers old and new economic effects and corrections;
- no manual cleanup occurred before final evidence capture;
- failed and inconclusive runs are retained;
- residual risk does not contradict RFC-000/RFC-001;
- live scope matches the tested capability profile.

---

## 212. Approval Gates by ADR

### ADR-002-002

Requires:

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
- ERI-EV-001, ERI-EV-004 through ERI-EV-008, and ERI-EV-010 through ERI-EV-012;
- RC-EV-005, RC-EV-007, RC-EV-010, RC-EV-011, SA-EV-011, BC-EV-006, and BC-EV-017;
- approved field-specific proof, freshness, source-independence, and conservative-bound rules;
- reconciliation and evidence-independence review.

### ADR-002-007

Requires:

- REARM-EV-001 through REARM-EV-012;
- ERI-EV-001 through ERI-EV-007, ERI-EV-010, and ERI-EV-012;
- SPG-EV-001 through SPG-EV-012;
- EGRESS-EV-004 through EGRESS-EV-010 and EGRESS-EV-012;
- HAG-EV-001 through HAG-EV-012;
- SA-EV-009, SA-EV-010, SA-EV-013, BC-EV-015, BC-EV-020, BC-EV-021, X-EV-007, X-EV-009, and X-EV-012;
- approved and measured `B_risk_increase_revoke`, `B_revocation_to_egress`, `B_halt_to_egress`, `MAX_normal_capability_age`, `B_capability_claim_to_send`, and `B_egress_hard_fence`;
- authorization/final-egress security assessment and independent review.

### ADR-002-008

Requires:

- TIME-EV-001 through TIME-EV-010;
- ERI-EV-001, ERI-EV-004 through ERI-EV-008, ERI-EV-010, and ERI-EV-012;
- SPG-EV-001, SPG-EV-008, SPG-EV-010, and SPG-EV-011;
- HAG-EV-002, HAG-EV-004, and HAG-EV-011;
- SA-EV-005, SA-EV-006, SA-EV-011, and X-EV-008;
- approved and measured `B_time_health_to_egress`, `MAX_time_health_snapshot_age`, and applicable clock, suspension, holdover, freshness, and session bounds;
- time-source/common-mode review and independent review.

### ADR-002-009

Requires:

- FD-EV-001 through FD-EV-012;
- ERI-EV-003, ERI-EV-005, ERI-EV-007, ERI-EV-009, ERI-EV-010, and ERI-EV-012;
- SPG-EV-004, SPG-EV-005, SPG-EV-007, and SPG-EV-009 through SPG-EV-011;
- EGRESS-EV-001 through EGRESS-EV-003 and EGRESS-EV-006 through EGRESS-EV-010;
- HAG-EV-001, HAG-EV-005, HAG-EV-008, and HAG-EV-009;
- SA-EV-001, SA-EV-002, SA-EV-008, SA-EV-013 through SA-EV-015, BC-EV-015, BC-EV-020, X-EV-002, X-EV-003, and X-EV-009;
- an approved Failure-Domain Allocation Matrix, deployment profile, RCL fencing mechanism, and implementation of the selected ADR-002-007 §§9.1–9.5 egress-currentness protocol;
- failure-domain security assessment and independent review.

### ADR-002-010

Requires:

- NT-EV-001 through NT-EV-012;
- ERI-EV-001, ERI-EV-004 through ERI-EV-008, and ERI-EV-010 through ERI-EV-012;
- RC-EV-010, RC-EV-015, BC-EV-008, BC-EV-019, X-EV-010, TIME-EV-008, and REARM-EV-003;
- HAG-EV-007, HAG-EV-009, and HAG-EV-011;
- approved source-authority, transition-envelope, RCL remap, event-time, and broker-treatment rules;
- broker-profile evidence for every supported event/instrument scope and independent review.

### ADR-002-011

Requires:

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
- ERI-EV-001, ERI-EV-002, ERI-EV-004 through ERI-EV-008, ERI-EV-010, and ERI-EV-012;
- SPG-EV-004, SPG-EV-005, SPG-EV-007, and SPG-EV-010;
- EGRESS-EV-004 through EGRESS-EV-009;
- HAG-EV-002, HAG-EV-004, HAG-EV-005, and HAG-EV-010;
- RC-EV-001 through RC-EV-004, RC-EV-009, RC-EV-012, RC-EV-013, RC-EV-017, RC-EV-018, SA-EV-001 through SA-EV-003, SA-EV-008, SA-EV-013 through SA-EV-015, REARM-EV-008, REARM-EV-010, FD-EV-002 through FD-EV-005, FD-EV-007, FD-EV-009, and FD-EV-012;
- approved Capacity Domain, failure-tolerance model, membership protocol, Commit Proof, snapshot/restore, and disaster-recovery rules;
- consensus/fencing security assessment and independent review.

### ADR-002-013

Requires:

- EGRESS-EV-001 through EGRESS-EV-012;
- ERI-EV-001 through ERI-EV-007, ERI-EV-009, ERI-EV-011, and ERI-EV-012;
- SPG-EV-004, SPG-EV-006, SPG-EV-007, SPG-EV-010, and SPG-EV-011;
- HAG-EV-005 through HAG-EV-007, HAG-EV-009, and HAG-EV-011;
- SA-EV-008, SA-EV-009, SA-EV-012, SA-EV-013, BC-EV-001, BC-EV-002, BC-EV-003, BC-EV-014, BC-EV-015, BC-EV-020, BC-EV-021, REARM-EV-008, REARM-EV-010, REARM-EV-011, FD-EV-001 through FD-EV-007, FD-EV-009, RCLP-EV-002, RCLP-EV-003, RCLP-EV-006 through RCLP-EV-009, RCLP-EV-012, X-EV-001 through X-EV-004, X-EV-006, X-EV-009, X-EV-011, and X-EV-012;
- an approved Final Egress Trust Boundary, Active Egress Principal topology, Quorum Commit Certificate, credential/session model, route/endpoint policy, Hard Egress Fence, and Broker Capability Profile;
- approved and measured `B_egress_hard_fence` plus applicable currentness, revocation, HALT, failure-domain, session, and claim-to-send bounds;
- independent credential, route, proof-validation, bypass, and recovery security assessment.

### ADR-002-014

Requires:

- SPG-EV-001 through SPG-EV-012;
- ERI-EV-001, ERI-EV-004 through ERI-EV-010, and ERI-EV-012;
- HAG-EV-001 through HAG-EV-004, HAG-EV-006, and HAG-EV-008 through HAG-EV-010;
- RC-EV-001, RC-EV-002, RC-EV-009, RC-EV-013, RC-EV-017, SA-EV-001, SA-EV-002, SA-EV-008 through SA-EV-010, SA-EV-013, BC-EV-015, REARM-EV-001, REARM-EV-004 through REARM-EV-006, REARM-EV-008 through REARM-EV-012, TIME-EV-001, TIME-EV-006, TIME-EV-009, FD-EV-002, FD-EV-007, FD-EV-009, FD-EV-012, RCLP-EV-002, RCLP-EV-003, RCLP-EV-005, RCLP-EV-008 through RCLP-EV-010, RCLP-EV-012, EGRESS-EV-003 through EGRESS-EV-007, EGRESS-EV-009, EGRESS-EV-012, X-EV-002, X-EV-003, X-EV-007 through X-EV-009, and X-EV-012;
- approved canonical artifact schemas, semantic normalization, comparison rules, envelope and profile governance, Consumer Compatibility Manifest, Profile Generation, Activation Record, and Restrictive Override protocol;
- approved and measured applicable revocation, egress, time, evidence-persistence, activation-validity, approval-validity, and restriction-propagation bounds;
- independent configuration-authority, signing, approval, canonicalization, compatibility, activation, rollback, restore, and bypass security assessment.

### ADR-002-015

Requires:

- HAG-EV-001 through HAG-EV-012;
- ERI-EV-001, ERI-EV-003 through ERI-EV-010, and ERI-EV-012;
- SA-EV-009, SA-EV-010, SA-EV-012, SA-EV-013, REARM-EV-002 through REARM-EV-005, REARM-EV-008 through REARM-EV-012, TIME-EV-007, TIME-EV-009, FD-EV-001, FD-EV-003, FD-EV-005, FD-EV-006, FD-EV-009, RCLP-EV-005 through RCLP-EV-009, EGRESS-EV-001 through EGRESS-EV-003, EGRESS-EV-005 through EGRESS-EV-010, EGRESS-EV-012, SPG-EV-001, SPG-EV-004 through SPG-EV-010, SPG-EV-012, X-EV-006, X-EV-007, X-EV-009, and X-EV-012;
- approved Human Authority Policy, Effective Principal Graph, Approval Request, Approval Attestation, Approval Set, consumption, delegation, Human HALT, break-glass, compromise, and recovery mechanisms;
- approved and measured `B_human_halt_to_commit`, `B_halt_to_egress`, and applicable human session, approval, delegation, revocation, identity-fence, notification, evidence, and recovery bounds;
- independent identity, authentication, effective-control, workflow, quorum, separation-of-duties, break-glass, HALT-path, approval-consumption, compromise, and bypass security assessment.

### ADR-002-016

Requires:

- ERI-EV-001 through ERI-EV-012;
- STATE-EV-001 through STATE-EV-005, RECON-EV-001 through RECON-EV-005, RCLP-EV-003, RCLP-EV-006, RCLP-EV-009, RCLP-EV-010, RCLP-EV-012, EGRESS-EV-002, EGRESS-EV-005 through EGRESS-EV-007, EGRESS-EV-009, EGRESS-EV-012, SPG-EV-003, SPG-EV-007, SPG-EV-010 through SPG-EV-012, HAG-EV-004, HAG-EV-005, HAG-EV-009, HAG-EV-011, and HAG-EV-012;
- approved Safety Evidence Envelope, Evidence Integrity Policy, Evidence Commit Receipt, Integrity Anchor, Evidence Gap, retention/redaction/access rules, and Replay Capsule schemas;
- approved and measured `B_evidence_persist`, `B_evidence_gap_detect`, `B_evidence_gap_contain`, and applicable retention, replay, egress, time, broker, and recovery bounds;
- independent storage, ingestion, source identity, cryptographic integrity, key custody, emergency-journal, access, redaction/export, retention/deletion, backup/restore, replay-isolation, and live-boundary security assessment.

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

## 213. Current Evidence Readiness Assessment

As of 2026-07-13:

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
Independent review: NOT STARTED
Production authorization: NO
```

This status is intentionally strict. The documents define completion criteria; they do not replace execution.

---

## 214. Required Next Execution Sequence

```text
1. Assign implementation owner, evidence owner, and independent reviewer for every registered item.
2. Approve the Verification Profile bounds and scope.
3. Implement trace and evidence identities.
4. Implement model/property tests for all ADR-002 capacity, consensus, state, authority, time, failure-domain, replacement, non-trade, final-egress security, safety-configuration governance, human-authority governance, and evidence-integrity/replay models.
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

## 215. Verification Specification Approval Gate

VER-002-001 may move from **Proposed** to **Approved for Execution** when:

- every Critical RFC/ADR invariant maps to at least one evidence item;
- Verification Profile schema is approved;
- evidence package format is implemented;
- artifact integrity and reviewer sign-off workflow exist;
- fault-injection responsibilities are assigned;
- broker production-test safety rules are approved;
- evidence retention and access controls are defined.

Approval for execution does not authorize live trading.
