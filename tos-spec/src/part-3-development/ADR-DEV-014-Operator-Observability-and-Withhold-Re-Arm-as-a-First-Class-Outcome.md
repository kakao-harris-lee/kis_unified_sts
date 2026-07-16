# ADR-DEV-014 — Operator Observability and "Withhold Re-Arm" as a First-Class Outcome

**ADR ID:** ADR-DEV-014
**Title:** Operator Observability and "Withhold Re-Arm" as a First-Class Outcome
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-011 — Operational Guidelines (with ADR-002-028)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-011 §14 Q3 and RFC-011 §14 Q4
**Date:** 2026-07-16
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-16
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

Two operator-facing decisions are fixed here:

* **Required observability, without the surface becoming authority (Q3).** The operator
  SHALL be able to observe the load-bearing operational state — current authority, risk
  capacity, open and potentially-live orders, trapped exposure, reconciliation status,
  safety configuration, degraded mode, and evidence completeness (RFC-011 §8; Vision
  §9.3). The observability surface is **evidence for operator action, not permission**:
  validity and authority are never inferred from a green dashboard, a `CONFORMING`
  snapshot, or component health, and unknown state is shown as unknown (RFC-011 §8;
  ADR-002-018 §9; ADR-002-028; RFC-002 §10.30).
* **"Withhold re-arm" is a first-class, recorded outcome (Q4).** Declining to re-arm is a
  conforming decision represented as a **first-class, recorded, attributable, auditable
  outcome with its rationale** — not an absence of action; review sees that the operator
  chose to withhold and why (RFC-011 §10; philosophy §8).

This ADR grants no authority, and the observability surface authorizes nothing.

---

## 2. Context

RFC-011 §8 requires the operator to act on observed state — authority, capacity, open and
potentially-live orders, trapped exposure, reconciliation, safety configuration, degraded
mode, evidence completeness — and forbids inferring state validity or authority from
component health (ADR-002-018 §9); a `CONFORMING` monitoring snapshot is a non-authorizing
negative gate (ADR-002-028; RFC-002 §10.30). RFC-011 §10 makes withholding re-arm a
conforming operational decision, and §7 requires operator action to be authenticated,
scoped, attributable, and auditable.

RFC-011 §14 leaves two questions open: Q3 (what operator-facing observability is required
so authority, capacity, trapped exposure, reconciliation, and degraded mode are visible
without the dashboard itself becoming a trusted authority) and Q4 (how the operator
discipline represents "withhold re-arm" as a first-class, recorded, auditable outcome
rather than an absence of action). This ADR fixes both. It defines no monitoring protocol
(ADR-002-028 owns that) and no UI; it fixes what must be observable and that the surface is
non-authorizing, and that a withhold is first-class. Q3 is resolved by binding RFC-011 §8's
scattered observability norms into named, §12-verifiable invariants (the net-new content
being the named non-authorizing Observability Surface and its testable invariants); Q4's
first-class, recorded, attributable withhold is genuinely new operator-facing content
beyond RFC-011 §10's bare "valid outcome."

---

## 3. Decision Drivers

1. **A hidden safety state is not a useful one** (Vision §9.3). The operator must see the
   load-bearing state.
2. **Observation is evidence, not permission** (RFC-011 §8; ADR-002-018 §9). A green
   surface is not authority.
3. **Health is not validity** (ADR-002-018 §9; philosophy §16). Uptime and heartbeats do
   not establish state.
4. **A visible failure is still a failure** (philosophy §37.3). Unknown is shown as unknown.
5. **Withholding is a decision, not nothing** (RFC-011 §10; philosophy §8). It must be
   recorded and auditable like any decision.

---

## 4. Scope and Non-Scope

**In scope:**

* the load-bearing operational state the operator must be able to observe;
* the non-authorizing character of the observability surface;
* the first-class, recorded representation of a withheld re-arm.

**Not in scope (owned elsewhere):**

* the continuous conformance monitoring protocol, telemetry integrity, and alert
  escalation — ADR-002-028 (and its RFC-002 §10.30 component);
* Critical Input freshness/currentness and health-is-not-validity mechanics — ADR-002-018;
* the re-arm mechanism and recovery barrier — ADR-002-007/017; the re-arm checklist —
  ADR-DEV-012;
* the concrete dashboard, layout, and UI, which are approved design and configuration;
* evidence/replay integrity of the recorded withhold — ADR-002-016.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-011 §5 (**Operator**, **Operational Act**,
**Re-arm Decision**), RFC-002 §3.1, and ADR-002-028 (continuous conformance monitoring,
`CONFORMING` snapshot), and SHALL NOT introduce synonyms. The following terms are scoped to
this decision and are non-authorizing.

* **Observability Surface** — the operator-facing presentation of load-bearing operational
  state (RFC-011 §8). It is evidence for operator action; it is not permission and holds no
  authority.
* **Withheld Re-Arm** — the conforming operator outcome of declining to request (or, where
  the operator is the granting authority, grant) re-arm, represented as a first-class,
  recorded, attributable, auditable decision with its rationale (RFC-011 §10; the
  request-side instance is ADR-DEV-012's "Withhold").

These terms describe an observability-and-outcome discipline. None grants authority or
re-arms.

---

## 6. Safety Invariants

* **OBS-INV-001 — Load-Bearing State Is Observable.** The operator SHALL be able to observe
  current authority, risk capacity, open and potentially-live orders, trapped exposure,
  reconciliation status, safety configuration, degraded mode, and evidence completeness
  (RFC-011 §8; Vision §9.3). This obliges presentation of facts already owned upstream (the
  Live Authorization Service, the RCL, reconciliation, ADR-002-028); it assigns no new
  authority or ownership.
* **OBS-INV-002 — Observability Is Evidence, Not Authority.** The Observability Surface is
  evidence for operator action, not permission; validity or authority is never inferred from
  a green dashboard, a `CONFORMING` snapshot, or component health (RFC-011 §8; ADR-002-018
  §9; ADR-002-028; RFC-002 §10.30).
* **OBS-INV-003 — Unknown Is Shown as Unknown.** Unknown or unreconciled state is surfaced
  as unknown, never optimistically resolved to keep operating; a visible failure is still a
  failure (RFC-011 §8; philosophy §37.3). The concrete "SHALL NOT default to green"
  dashboard-rendering rule stays owned by ADR-002-028; this invariant states the
  operator-surface principle only.
* **OBS-INV-004 — Withheld Re-Arm Is a First-Class, Recorded Outcome.** Declining to re-arm
  is a conforming decision represented as a first-class, recorded, attributable, auditable
  outcome with its rationale — not an absence of action (RFC-011 §5, §7, §10; philosophy
  §8; cf. ADR-DEV-007 SOS-INV-001).
* **OBS-INV-005 — Missed Opportunity Is Acceptable.** A Withheld Re-Arm's missed trading
  opportunity is an acceptable consequence of unresolved critical uncertainty (RFC-011 §10;
  Vision §9.6; philosophy §8).
* **OBS-INV-006 — Observability and Withholding Grant No Authority.** Observing state or
  recording a Withheld Re-Arm creates no authority, commits no capacity, and re-arms nothing
  (RFC-002 §9.1; ADR-002-007).

---

## 7. Required Observability, Non-Authorizing (RFC-011 §14 Q3)

The operator SHALL be able to see the load-bearing state, and the surface SHALL NOT be
authority (OBS-INV-001, -002, -003):

* observable state includes current authority, risk capacity, open and potentially-live
  orders, trapped exposure, reconciliation status, safety configuration, degraded mode, and
  evidence completeness (RFC-011 §8; Vision §9.3);
* the Observability Surface is evidence for the operator to act on, never permission — the
  operator's authority comes from its grant, not from what the dashboard shows (RFC-011 §8);
* validity and authority are not inferred from a green surface, a `CONFORMING` snapshot,
  uptime, or heartbeats — health is not validity, and a `CONFORMING` snapshot is a
  non-authorizing negative gate (ADR-002-018 §9; ADR-002-028; RFC-002 §10.30);
* unknown or unreconciled state is shown as unknown, not optimistically resolved
  (OBS-INV-003; philosophy §37.3).

Seeing honestly is the point; the surface informs the operator's bounded authority, it
never becomes it.

---

## 8. Withhold Re-Arm as First-Class (RFC-011 §14 Q4)

Declining to re-arm is a decision, represented as one (OBS-INV-004, -005):

* a Withheld Re-Arm is a first-class, directly represented outcome — recorded,
  attributable, and auditable, with its rationale (for example, which ADR-DEV-012 checklist
  item was unreconciled) — not an absent action or a silent non-event (RFC-011 §10);
* review and audit see that the operator *chose* to withhold and why, exactly as they would
  see a re-arm request (philosophy §8; the same first-class-outcome discipline ADR-DEV-007
  applies to no-action in the strategy layer);
* the missed trading opportunity of a Withheld Re-Arm is an acceptable consequence of
  unresolved uncertainty (OBS-INV-005; Vision §9.6);
* recording a Withheld Re-Arm grants no authority and re-arms nothing (OBS-INV-006).

A withhold is captured as a decision so that "the operator did not re-arm" is never
mistaken for "nothing happened."

---

## 9. Alternatives Considered

* **9.1 Treat a green dashboard as authorization to re-arm.** Rejected (foreclosed upstream
  by RFC-011 §8 and ADR-002-018 §9; restated here to make the boundary testable):
  observation is evidence, not permission; health is not validity (OBS-INV-002).
* **9.2 Optimistically resolve unknown state to keep operating.** Rejected: unknown is shown
  as unknown; a visible failure is still a failure (OBS-INV-003; philosophy §37.3).
* **9.3 Represent a withheld re-arm as an absence of action.** Rejected: withholding is a
  decision and must be first-class and recorded (OBS-INV-004; RFC-011 §10).
* **9.4 Treat a `CONFORMING` snapshot as authority.** Rejected (foreclosed upstream by
  ADR-002-028 / RFC-002 §10.30; restated here for testability): it is a non-authorizing
  negative gate (OBS-INV-002).
* **9.5 Define the monitoring protocol or the dashboard here.** Rejected: owned by
  ADR-002-028 and design/configuration (§4).

---

## 10. Consequences

**Positive.**

* Makes the load-bearing operational state visible so the operator acts on evidence.
* Keeps the surface non-authorizing, preventing "green dashboard ⇒ permission."
* Makes a withheld re-arm auditable, so a conservative choice is visible, not lost.

**Negative / costs.**

* Surfacing every load-bearing state honestly (including unknown) is more work than a
  simple health light.
* Recording each withheld re-arm with rationale adds audit overhead.
* The non-authorizing discipline must be enforced against the natural tendency to treat a
  green surface as permission.

---

## 11. Failure Modes Introduced by This Decision

* **11.1 Dashboard-as-authority.** A green surface treated as permission; blocked by
  OBS-INV-002 and ADR-002-018 §9.
* **11.2 Optimistic unknown.** Unknown state hidden or resolved to a permissive value;
  blocked by OBS-INV-003.
* **11.3 Silent withhold.** A withheld re-arm not recorded, read as "nothing happened";
  blocked by OBS-INV-004.
* **11.4 Snapshot-as-authority.** A `CONFORMING` snapshot treated as authorizing; blocked by
  OBS-INV-002 (ADR-002-028; RFC-002 §10.30).

---

## 12. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010; the monitoring side owned by
ADR-002-028):

* **12.1** The load-bearing operational state is observable to the operator (OBS-INV-001).
* **12.2** A green surface / `CONFORMING` snapshot / component health does not authorize an
  operator action or a re-arm (OBS-INV-002).
* **12.3** Unknown or unreconciled state is surfaced as unknown, not resolved permissively
  (OBS-INV-003).
* **12.4** A withheld re-arm is produced as a first-class, recorded, attributable outcome
  with rationale, distinct from an absent action (OBS-INV-004).
* **12.5** Observing state or recording a withhold grants no authority and re-arms nothing
  (OBS-INV-006).
* OBS-INV-005 (missed opportunity acceptable) is a non-testable value stance, verified by
  review rather than a behavioral test — completing the OBS-INV → §12 mapping.

---

## 13. Acceptance Criteria

ADR-DEV-014 is acceptable when:

* the load-bearing operational state is observable (OBS-INV-001);
* the Observability Surface is evidence, never authority, with unknown shown as unknown
  (OBS-INV-002, -003);
* a withheld re-arm is a first-class, recorded, auditable outcome, its missed opportunity
  accepted (OBS-INV-004, -005);
* observability and withholding grant no authority (OBS-INV-006);
* independent adversarial review (EV-L0) confirms every §12 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 14. Traceability

| Requirement | Discharge in ADR-DEV-014 |
|---|---|
| RFC-011 §14 Q3 (observability without the surface becoming authority) | required observable state; surface is non-authorizing (§7; OBS-INV-001, -002) |
| RFC-011 §14 Q4 (withhold re-arm as first-class outcome) | first-class recorded auditable Withheld Re-Arm (§8; OBS-INV-004) |
| RFC-011 §8 (observe load-bearing state; observation is evidence) | observable state list; evidence not permission (§7; OBS-INV-001, -002) |
| RFC-011 §10 (withholding is conforming; missed opportunity acceptable) | Withheld Re-Arm first-class; missed opportunity accepted (§8; OBS-INV-004, -005) |
| Vision §9.3 (observable, hidden state not useful) | load-bearing state observable (§7; OBS-INV-001) |
| Vision §9.6 (missed opportunity acceptable) | OBS-INV-005 |
| ADR-002-018 §9 (health is not validity) | no validity/authority from health (§7; OBS-INV-002) |
| ADR-002-028; RFC-002 §10.30 (monitoring; CONFORMING snapshot non-authorizing) | surface/snapshot is not authority (§7; OBS-INV-002) |
| ADR-DEV-007 SOS-INV-001 (no-action first-class) | withhold is first-class, like no-action (§8; OBS-INV-004) |
| ADR-DEV-012 (re-arm checklist) | a withhold records the unreconciled item (§8) |
| RFC-002 §9.1 (authority ownership) | observability/withholding grant no authority (OBS-INV-006) |
| philosophy §8, §16, §37.3 | uncertainty restrictive; state from evidence; visible failure is a failure (§3, §7) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes required
observability and the first-class withhold and relies on ADR-002-028 for the monitoring
protocol.

---

## 15. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-014, resolving RFC-011 §14 Q3 (required operator observability without
  the surface becoming authority) and Q4 ("withhold re-arm" as a first-class recorded
  outcome).
* Set the decision: the load-bearing operational state is observable; the Observability
  Surface is evidence not permission, with validity never inferred from a green
  surface/snapshot/health and unknown shown as unknown; a withheld re-arm is a first-class,
  recorded, attributable, auditable outcome whose missed opportunity is acceptable.
* Defined six invariants OBS-INV-001…006 and traced them to RFC-011 §8/§10, Vision §9.3/§9.6,
  ADR-002-018 §9, ADR-002-028, RFC-002 §9.1/§10.30, ADR-DEV-007/012, and philosophy
  §8/§11/§16/§37.3.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding; all twelve substantive attacks blocked and every citation verified. One
  Major (decision quality): the Q3 half largely consolidates RFC-011 §8 and its §9.1/§9.4
  alternatives were foreclosed upstream — §2 now states Q3 is resolved by binding RFC-011
  §8's scattered norms into named, §12-verifiable invariants (Q4's first-class recorded
  withhold being the genuinely new content), and §9.1/§9.4 are reframed as "foreclosed
  upstream, restated for testability." Five Minor fixes: philosophy §11 dropped from §3
  driver 1 (mis-fit); OBS-INV-004's attributable/auditable leg cited to RFC-011 §5/§7;
  OBS-INV-003 notes the concrete "SHALL NOT default to green" rule stays owned by
  ADR-002-028; OBS-INV-001 notes it obliges presentation of upstream-owned facts and assigns
  no ownership; and §12 records that OBS-INV-005 is a non-testable value stance verified by
  review. The review is EV-L0 only and confers no acceptance or live-readiness.
