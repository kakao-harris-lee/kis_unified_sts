# RFC-001 — Safety Case

**Document ID**: RFC-001
**Title**: Safety Case
**Version**: 0.1 Draft (Scaffold)
**Status**: Working Draft
**Classification**: Foundational Specification
**Authority**: Governed by RFC-000 Trading Constitution
**Owner**: Trading Operating System Architecture Board

---

# 1. Abstract

This document is the Safety Case for the Trading Operating System (TOS).

Where RFC-000 defines WHY the system exists and WHAT SHALL always be true, this
document defines WHAT SHALL NEVER HAPPEN, and records how each constitutional
requirement is discharged.

This document is governed by RFC-000 and SHALL NOT reinterpret or weaken
constitutional intent.

This revision is a scaffold. Demonstration content is marked TODO and SHALL be
completed before any reliance on the corresponding constitutional guarantee
(RFC-000 Section 15, Verification Obligation).

---

# 2. Scope

This Safety Case applies to every production trading operation of the TOS.

It enumerates the constitutional hazards, and for each constitutional
requirement records the hazard(s) it mitigates, the required evidence, and the
demonstration status.

---

# 3. Normative Language

The key words MUST, MUST NOT, SHALL, SHALL NOT, SHOULD, SHOULD NOT and MAY are
to be interpreted as described in RFC 2119, consistent with RFC-000 Section 3.

---

# 4. Constitutional Safe State

The constitutional safe state is defined by RFC-000 (CONST-012 and the
Definitions section).

In the safe state:

- no new exposure SHALL be created;
- every existing position SHALL remain within constitutional risk bounds under active protective control;
- the safe state SHALL NOT be interpreted as mere inactivity.

TODO: define concrete safe-state transition and protective behaviour per asset
class.

---

# 5. Constitutional Hazards

The following hazards define WHAT SHALL NEVER HAPPEN.

## HAZ-001 — Permanent Capital Impairment

Capital is impaired beyond recovery.

Governing requirements: CONST-001, CONST-002.

## HAZ-002 — Unbounded Loss

Loss proceeds without an enforced limit.

Governing requirements: CONST-006, CONST-009, CONST-010.

## HAZ-003 — Post-Breach Execution

An action that breaches a safety limit is executed before being stopped.

Governing requirements: CONST-006, CONST-009.

## HAZ-004 — Duplicate or Runaway Execution

A single intent produces multiple or unbounded orders.

Governing requirements: none yet (constitutional gap — no exactly-once or
bounded-action-rate requirement exists).

## HAZ-005 — Trading on Invalid Context

A decision or execution rests on stale, incomplete or inconsistent data.

Governing requirements: CONST-004, CONST-007 (partial); constitutional gap — no
explicit input-integrity requirement exists.

## HAZ-006 — Trading Into an Unavailable Venue

An action is taken while the venue is halted or closed.

Governing requirements: CONST-007.

## HAZ-007 — Unmanaged Exposure After Failure

Existing exposure is abandoned when the system degrades.

Governing requirements: CONST-004, CONST-012.

## HAZ-008 — Trading Before Reconciliation

Autonomous trading resumes before operational state is validated.

Governing requirements: CONST-008, CONST-013.

## HAZ-009 — Loss of Containment

A defect disables the authority meant to stop it.

Governing requirements: CONST-011.

## HAZ-010 — Fail-Open Configuration

Missing or invalid safety configuration increases operational authority.

Governing requirements: CONST-010.

## HAZ-011 — Irreversible Mistake Treated as Recoverable

Execution is treated as reversible; prevention is deferred to audit.

Governing requirements: CONST-014.

---

# 6. Constitutional Verification Matrix

For each constitutional requirement: the hazard(s) mitigated, the required
evidence, and the demonstration status.

Status legend: DEMONSTRATED | PARTIAL | NOT-YET-DEMONSTRATED.

| Requirement | Title | Mitigates | Required evidence | Status |
|-------------|-------|-----------|-------------------|--------|
| CONST-001 | Long-Term Survivability | HAZ-001 | Safety Case + risk-policy review | NOT-YET-DEMONSTRATED |
| CONST-002 | Capital Preservation | HAZ-001 | Risk-policy review | NOT-YET-DEMONSTRATED |
| CONST-003 | Positive Expectancy | — | Expectancy-based evaluation | NOT-YET-DEMONSTRATED |
| CONST-004 | Fail-Safe Operating Principle | HAZ-005, HAZ-007 | Safe-state demonstration | NOT-YET-DEMONSTRATED |
| CONST-005 | Independent Approval Authority | HAZ-003 | Architecture separation evidence | NOT-YET-DEMONSTRATED |
| CONST-006 | Operational Safety Limits | HAZ-002, HAZ-003 | Pre-trade limit-enforcement evidence | NOT-YET-DEMONSTRATED |
| CONST-007 | Venue Constraints | HAZ-006 | Venue-state gating evidence | NOT-YET-DEMONSTRATED |
| CONST-008 | Authoritative Position | HAZ-008 | Reconciliation evidence | NOT-YET-DEMONSTRATED |
| CONST-009 | Pre-Trade Constitutional Assurance | HAZ-002, HAZ-003 | Pre-trade enforcement evidence | NOT-YET-DEMONSTRATED |
| CONST-010 | Fail-Closed Configuration | HAZ-002, HAZ-010 | Config-validation evidence | NOT-YET-DEMONSTRATED |
| CONST-011 | Independent Safety Authority | HAZ-009 | Independence demonstration | NOT-YET-DEMONSTRATED |
| CONST-012 | Safe Operational State | HAZ-007 | Safe-state definition + test | NOT-YET-DEMONSTRATED |
| CONST-013 | Safe Operational Start | HAZ-008 | Startup-validation evidence | NOT-YET-DEMONSTRATED |
| CONST-014 | Irreversibility Principle | HAZ-011 | Pre-execution assurance evidence | NOT-YET-DEMONSTRATED |

Per RFC-000 Section 15, every NOT-YET-DEMONSTRATED requirement is an
undischarged verification obligation and SHALL force the constitutional safe
state until demonstrated.

---

# 7. Open Constitutional Gaps

The following hazards are not yet fully governed by a constitutional
requirement, and are recorded for RFC-000 evolution.

- HAZ-004 — no exactly-once execution or bounded-action-rate requirement.
- HAZ-005 — no explicit input-integrity requirement.
- Live / non-live segregation — no requirement.
- Aggregate (portfolio-level) risk authority — no requirement.

---

# 8. Review History

v0.1

Initial scaffold (hazards + constitutional verification matrix)
