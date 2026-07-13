# TOS Safety Architecture Gate Status

- **Date:** 2026-07-13
- **Scope:** RFC-002 review patch and ADR-002-001 through ADR-002-004
- **Architecture Documentation:** Substantially complete for the current gate
- **Verification Execution:** Not started
- **Production Authorization:** NO

---

## 1. Completed Design Artifacts

The following design decisions now have normative documents:

1. RFC-002 v0.2 Architecture Review Patch
2. ADR-002-001 v0.2 Degraded-Mode Protective Capacity Patch
3. ADR-002-002 Aggregate Risk-Capacity Commitment Model
4. ADR-002-003 Safety Authority Validity, Epoch Fencing, and Partition Behavior
5. ADR-002-004 Broker Capability Requirements and Fallbacks
6. VER-002-001 Safety-Critical Architecture Verification Evidence Specification
7. Evidence Register and configuration/evidence templates

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

---

## 3. Remaining Architecture ADRs

The following remain necessary but do not block implementation of the current verification harness:

- ADR-002-005 — Intent, Transmission Attempt, Broker Order, and Knowledge State Model
- ADR-002-006 — Evidence and Reconciliation Confidence Model
- ADR-002-007 — Live Authorization, Limit Governance, and Re-arm
- ADR-002-008 — Trustworthy Time Architecture
- ADR-002-009 — Failure-Domain Isolation and Deployment Safety
- ADR-002-010 — Corporate Actions and Non-Trade State Changes
- ADR-002-011 — Protective Replacement and Protection-Gap Control

Some of these are required before production approval even when the current ADR acceptance tests pass.

---

## 4. Current Approval State

| Artifact | Current state | Can implement? | Can accept? |
|---|---|---:|---:|
| RFC-002 v0.2 patch | Proposed merge patch | YES | after repository merge review |
| ADR-002-001 v0.2 | Proposed amendment | YES | after protective evidence passes |
| ADR-002-002 | Proposed | YES | NO |
| ADR-002-003 | Proposed | YES | NO |
| ADR-002-004 | Proposed | YES | NO |
| VER-002-001 | Proposed, ready for test implementation | YES | after evidence workflow review |
| Broker-specific Capability Profile | Template only | YES | NO |
| Verification evidence | Register created, not executed | NO claim of completion | NO |

---

## 5. Evidence Completion Meaning

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

## 6. Immediate Engineering Sequence

```text
1. Assign owners and reviewers in EVIDENCE-REGISTER-002.csv.
2. Approve numeric bounds in VERIFICATION-PROFILE-002.
3. Implement capacity and authority state-machine models.
4. Implement durable evidence identities and event capture.
5. Implement epoch/fencing and final egress checks.
6. Complete the first broker-specific Capability Profile.
7. Build deterministic fault injection.
8. Execute EV-L1 through EV-L3 tests.
9. Execute approved broker capability probes.
10. Perform independent evidence review.
11. Re-evaluate ADR Accepted status.
```

---

## 7. Gate Verdict

```text
Ready for implementation and test-harness work: YES
Ready for ADR acceptance: NO
Ready for restricted live trading: NO
Ready for production live trading: NO
```
