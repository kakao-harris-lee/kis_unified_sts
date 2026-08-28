# ADR-DEV-013 — Operator Boundaries: Degraded-Response vs Break-Glass, and Operator-Containment vs Incident Governance

**ADR ID:** ADR-DEV-013
**Title:** Operator Boundaries — Degraded-Response vs Break-Glass, and Operator-Containment vs Incident Governance
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-011 — Operational Guidelines (with ADR-002-015 and ADR-002-027)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-011 §14 Q2 and RFC-011 §14 Q5
**Date:** 2026-07-16
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-16
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

Two operator boundaries are fixed here:

* **Degraded-response vs out-of-scope action (Q2).** An **approved degraded-response** is
  an Operational Act *within* the operator's already-granted, scoped, revocable authority
  and approved procedures — including restrictively invoking a control (RFC-011 §7). An
  action *outside* ordinary authority routes by direction: an **authority-increasing or
  re-arm** action requires **dual control** (an independent quorum; ADR-002-015 HAG-INV-001),
  while an **emergency restrictive** action outside scope uses the **break-glass** path,
  which is restrictive-only and cannot enlarge authority (ADR-002-015 §5.7, HAG-INV-006).
  Disabling, bypassing, or clearing a constitutional control is never ordinary operation
  (RFC-002 §7.5). The full line is testable once operator scope is fixed by ADR-DEV-015
  (RFC-011 §14 Q6).
* **Operator-containment vs incident governance (Q5).** The operator **invokes** approved
  containment — a restrictive, asymmetric act using normal authority (ADR-002-027
  SIR-INV-002/005) — which **complements, and does not pre-empt**, the independently-owned
  Safety Authority and incident coordinator (RFC-000 CONST-011; ADR-002-027). The operator
  does **not** declare, close, or clear an incident or containment on its own authority;
  the incident lifecycle is owned by ADR-002-027 (SIR-INV-001, incident artifacts are not
  authority).

This ADR fixes two boundaries. It grants no authority, classifies no protection, and
authorizes no live operation.

---

## 2. Context

RFC-011 §7 makes the operator part of the safety model, exercising bounded, revocable
authority, and requires that a human command not silently bypass a constitutional safety
control (RFC-002 §7.5); §9 has the operator *invoke* approved containment while
protective classification and the incident lifecycle stay separately owned. ADR-002-015
owns human-authority, dual-control, and break-glass governance (Break Glass Cannot
Expand; Approval Is Not Authority). ADR-002-027 owns incident declaration, containment,
controlled shutdown, and closure (Incident Artifacts Are Not Authority; Declaration Is
Restrictive and Asymmetric; Containment Uses Normal Authority). RFC-000 CONST-011
establishes the independent Safety Authority.

RFC-011 §14 leaves two boundaries open: Q2 (where the line sits between an approved
degraded-response and a break-glass action needing ADR-002-015 dual control) and Q5 (how
operator-initiated containment relates to the independently-owned incident governance so
the operator complements rather than pre-empts). This ADR draws both. It defines neither
the break-glass mechanics (ADR-002-015) nor the incident lifecycle (ADR-002-027) — it
fixes where the operator's ordinary authority ends and the owned governance begins.

---

## 3. Decision Drivers

1. **Human authority is bounded, not an override** (philosophy §22; RFC-011 §7). The line
   between ordinary operation and break-glass must be explicit.
2. **Break-glass cannot expand authority** (ADR-002-015 HAG-INV-006). It is confined,
   governed, and auditable.
3. **A human command must not silently bypass a control** (RFC-002 §7.5). Bypassing is
   break-glass under governance, never a quiet degraded-response.
4. **Containment is restrictive and separately owned** (ADR-002-027). The operator
   invokes; it does not own the lifecycle.
5. **The independent Safety Authority is constitutional** (RFC-000 CONST-011). Operator
   action complements, never pre-empts, it.

---

## 4. Scope and Non-Scope

**In scope:**

* the boundary between an approved operator degraded-response and a break-glass action;
* the relationship between operator-invoked containment and ADR-002-027 incident
  governance;
* the confinement of both within the operator's bounded, revocable authority.

**Not in scope (owned elsewhere):**

* human-authority, dual-control, and break-glass mechanics — ADR-002-015;
* incident declaration, containment lifecycle, controlled shutdown, and closure —
  ADR-002-027;
* protective classification — the Protective Action Controller (ADR-002-001 §6);
* the independent Safety Authority's constitution — RFC-000 CONST-011;
* operator authority-scope expression and revocation — ADR-DEV-015;
* concrete break-glass procedures and quorums, which are approved configuration.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-011 §5 (**Operator**, **Operational Act**),
RFC-002 §3.1, ADR-002-015 (break-glass, dual control), and ADR-002-027 (containment,
incident), and SHALL NOT introduce synonyms. The following terms are scoped to this
decision and are non-authorizing.

* **Approved Degraded-Response** — an Operational Act within the operator's already-granted,
  scoped, revocable authority and approved procedures, taken in a degraded state (RFC-011
  §7, §9).
* **Break-Glass Action** — an emergency *restrictive* action (HALT, deny, narrow, request
  separately authorized containment) taken outside the operator's ordinary authority,
  permitted only under the ADR-002-015 break-glass path; it is restrictive-only and cannot
  enlarge authority (ADR-002-015 §5.7, HAG-INV-006).
* **Dual-Control Action** — an authority-increasing or re-arm action taken outside ordinary
  authority, permitted only through an independent dual-control quorum of at least two
  distinct effective principals (ADR-002-015 HAG-INV-001); it is not break-glass.
* **Operator-Invoked Containment** — the operator's invocation of an approved, restrictive
  containment that uses normal authority and defers the incident lifecycle to ADR-002-027
  (SIR-INV-005).

These terms describe operator boundaries. None grants authority or classifies protection.

---

## 6. Safety Invariants

* **OPB-INV-001 — Degraded-Response Is Within Scope; Out-of-Scope Action Routes by
  Direction.** An Approved Degraded-Response is within already-granted, scoped, revocable
  authority (including restrictively invoking a control). An action *outside* that ordinary
  authority routes by direction: an **authority-increasing or re-arm** action requires
  **dual control** — an independent quorum of at least two distinct effective principals
  (ADR-002-015 HAG-INV-001) — and an **emergency restrictive** action taken outside scope
  uses the **break-glass** path, which is restrictive-only and cannot enlarge authority
  (ADR-002-015 §5.7, HAG-INV-006). Disabling, bypassing, weakening, degrading, or clearing a
  constitutional safety control is never an ordinary degraded-response and is prohibited as
  a silent bypass (RFC-002 §7.5; RFC-011 §11.2).
* **OPB-INV-002 — Break-Glass Is Restrictive-Only; Authority Increase Is Dual-Control.** A
  break-glass action may HALT, deny, narrow, or request separately authorized containment;
  it SHALL NOT enlarge authority, broaden a safety profile, issue Live Authorization, create
  or release capacity, or re-arm (ADR-002-015 §5.7, HAG-INV-006). Any authority-increasing or
  re-arm action is instead a Dual-Control Action requiring an independent quorum (ADR-002-015
  HAG-INV-001); both are authenticated, scoped, attributable, and auditable (RFC-011 §7).
* **OPB-INV-003 — Operator Containment Is Restrictive and Uses Normal Authority.**
  Operator-Invoked Containment is a restrictive, asymmetric act using normal authority; it
  narrows, never widens, and creates no new authority (ADR-002-027 SIR-INV-002/005).
* **OPB-INV-004 — Operator Complements, Does Not Pre-empt, Incident Governance.** The
  operator invokes approved containment complementing the independently-owned Safety
  Authority; it does not declare, close, or clear an incident or containment on its own
  authority — the incident lifecycle is owned by ADR-002-027 and the independent authority
  by RFC-000 CONST-011 (ADR-002-027 SIR-INV-001).
* **OPB-INV-005 — Neither Boundary Grants Authority.** Classifying an action as a
  degraded-response, or invoking containment, creates no authority, capacity, live scope,
  or protective status (RFC-002 §9.1; ADR-002-001 §6).

---

## 7. Degraded-Response vs Break-Glass (RFC-011 §14 Q2)

The line is the operator's **scoped authority** (OPB-INV-001, -002):

* an **Approved Degraded-Response** stays within the operator's granted scope and approved
  procedures — halting, withholding re-arm, invoking approved containment, narrowing
  exposure. Restrictively *invoking* a control (a HALT, an approved containment) is a
  degraded-response, not a bypass (RFC-011 §7, §9);
* an action *outside* ordinary authority routes by direction: an **authority-increasing or
  re-arm** action is a **Dual-Control Action** requiring an independent quorum (ADR-002-015
  HAG-INV-001), and an **emergency restrictive** action taken outside scope is a
  **Break-Glass Action** — restrictive-only, confined to the emergency scope, unable to
  enlarge authority (ADR-002-015 §5.7, HAG-INV-006);
* **disabling, bypassing, weakening, degrading, or clearing** a constitutional safety
  control is never ordinary operation; an operator confronting a blocking control raises it
  through the appropriate governance, never by silently disabling the control (RFC-002 §7.5;
  RFC-011 §7, §11.2);
* both Dual-Control and Break-Glass Actions are authenticated, scoped, attributable, and
  auditable — the discipline that distinguishes them from an uncontrolled manual bypass
  (philosophy §22).

**Testability (RFC-011 §14 Q6).** The line "within the operator's scope" is fully testable
only once operator authority-scope expression is fixed by ADR-DEV-015 (RFC-011 §14 Q6).
Until then the two unambiguous ends are decidable — clearly-within-granted-scope
(degraded-response) and clearly-authority-increasing (dual-control) — while the middle
awaits ADR-DEV-015.

---

## 8. Operator-Containment vs Incident Governance (RFC-011 §14 Q5)

The operator **invokes**, the lifecycle is **owned** (OPB-INV-003, -004):

* Operator-Invoked Containment is a restrictive, asymmetric act using normal authority — it
  narrows the system and creates no new authority (ADR-002-027 SIR-INV-002/005);
* it **complements** the independently-owned Safety Authority and incident coordinator; the
  Safety Authority's ability to suspend autonomous trading is constitutional (RFC-000
  CONST-011);
* the operator does **not** declare, close, or clear an incident, nor clear a containment
  state, on its own authority — those are owned by ADR-002-027, and incident artifacts are
  not authority (SIR-INV-001);
* the operator's containment invocation and the independently-owned incident lifecycle are
  complementary, not competing: the operator can narrow immediately, and the incident
  coordinator governs declaration, shutdown, and closure.

The operator can always make the system *more* restrictive; it cannot own or clear the
incident that governs the restriction.

---

## 9. Alternatives Considered

* **9.1 Let the operator silently disable a blocking control under pressure.** Rejected: a
  human command must not silently bypass a constitutional control; that path is break-glass
  under governance (OPB-INV-001; RFC-002 §7.5).
* **9.2 Treat any emergency action as within ordinary authority.** Rejected: actions that
  exceed scope require ADR-002-015 governance (OPB-INV-001, -002).
* **9.3 Let break-glass grant open-ended authority.** Rejected: break-glass cannot expand
  authority beyond its emergency scope (OPB-INV-002; HAG-INV-006).
* **9.4 Let the operator declare/close incidents or clear containment.** Rejected: the
  incident lifecycle is owned by ADR-002-027; the operator invokes, it does not own
  (OPB-INV-004; SIR-INV-001).
* **9.5 Define break-glass or the incident lifecycle here.** Rejected: owned by ADR-002-015
  and ADR-002-027 (§4).
* **9.6 Draw the Q2 line by action-restrictiveness alone rather than authority-scope.**
  Considered: classify solely by whether an action is restrictive vs. authority-increasing,
  ignoring scope. Rejected as the *sole* criterion because a restrictive action can still
  fall outside the operator's granted scope (a HALT on an account it does not control); the
  scope test is primary, and direction (restrictive → break-glass, increasing →
  dual-control) then selects the governance for an out-of-scope action.

---

## 10. Consequences

**Positive.**

* Draws a clear, auditable line between ordinary degraded operation and break-glass.
* Lets the operator narrow immediately (containment) without owning the incident lifecycle.
* Keeps break-glass confined and the independent Safety Authority un-pre-empted.

**Negative / costs.**

* Some emergency actions require dual-control (authority increase) or break-glass
  (emergency restriction) governance rather than a quick operator move — the intended,
  conservative cost.
* Distinguishing "within scope" from "exceeds scope" requires the operator's authority
  scope to be explicit (ADR-DEV-015).
* Operator containment and incident governance must coordinate so the operator's narrowing
  is reflected in the owned lifecycle.

---

## 11. Failure Modes Introduced by This Decision

* **11.1 Silent bypass as "degraded-response."** A control disabled under the guise of
  ordinary operation; blocked by OPB-INV-001 and RFC-002 §7.5.
* **11.2 Break-glass scope creep.** A break-glass action grants more than its emergency
  scope; blocked by OPB-INV-002 (HAG-INV-006).
* **11.3 Operator clears an incident.** The operator closes/clears containment on its own
  authority; blocked by OPB-INV-004 (SIR-INV-001).
* **11.4 Containment pre-empts the authority.** Operator containment presented as replacing
  the independent Safety Authority; blocked by OPB-INV-004 (CONST-011).

---

## 12. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010; enforcement owned by
ADR-002-015/027):

* **12.1** An action exceeding operator scope or touching a control is routed to
  ADR-002-015 break-glass, not taken as a degraded-response (OPB-INV-001).
* **12.2** A break-glass action is restrictive-only and cannot enlarge authority; an
  authority-increasing or re-arm action instead requires a dual-control quorum (OPB-INV-002).
* **12.3** Operator-invoked containment narrows and creates no new authority (OPB-INV-003).
* **12.4** The operator cannot declare, close, or clear an incident/containment on its own
  authority (OPB-INV-004).
* **12.5** Neither classifying a degraded-response nor invoking containment grants authority
  or protective status (OPB-INV-005).

---

## 13. Acceptance Criteria

ADR-DEV-013 is acceptable when:

* the degraded-response/out-of-scope line is drawn at the operator's scoped authority —
  fully testable once ADR-DEV-015 fixes scope (RFC-011 §14 Q6); authority increase routes to
  dual control and emergency restriction to break-glass, which is restrictive-only and cannot
  expand (OPB-INV-001, -002);
* operator containment is restrictive, uses normal authority, and complements rather than
  pre-empts the incident governance (OPB-INV-003, -004);
* neither boundary grants authority (OPB-INV-005);
* independent adversarial review (EV-L0) confirms every §12 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 14. Traceability

| Requirement | Discharge in ADR-DEV-013 |
|---|---|
| RFC-011 §14 Q2 (degraded-response vs out-of-scope action) | line at scoped authority; authority-increase → dual control, emergency restriction → break-glass (§7; OPB-INV-001, -002) |
| RFC-011 §14 Q5 (operator containment vs incident governance) | operator invokes; lifecycle owned by ADR-002-027 (§8; OPB-INV-003, -004) |
| RFC-011 §7 (bounded operator authority; not a bypass path) | degraded-response within scope; no silent bypass (§7; OPB-INV-001) |
| RFC-011 §9 (operator invokes approved containment) | restrictive invocation (§8; OPB-INV-003); protective classification separately owned (OPB-INV-005) |
| RFC-002 §7.5 (human operations boundary; no silent bypass) | bypass is break-glass under governance (§7; OPB-INV-001) |
| RFC-000 CONST-011 (independent Safety Authority) | operator complements, does not pre-empt (§8; OPB-INV-004) |
| ADR-002-015 HAG-INV-001/006 (dual-control quorum; break glass cannot expand) | authority increase → dual control; break-glass restrictive-only (§7; OPB-INV-001, -002) |
| ADR-002-027 SIR-INV-001/002/005 (incident artifacts not authority; restrictive; normal authority) | operator invokes; does not own lifecycle (§8; OPB-INV-003, -004) |
| ADR-002-001 §6 (protective classification) | invoking containment classifies no protection (OPB-INV-005) |
| RFC-002 §9.1 (authority ownership) | neither boundary grants authority (OPB-INV-005) |
| philosophy §22 | human authority bounded, not override (§3) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes two operator
boundaries and relies on ADR-002-015 and ADR-002-027 for break-glass and the incident
lifecycle.

---

## 15. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-013, resolving RFC-011 §14 Q2 (degraded-response vs break-glass) and
  Q5 (operator-containment vs incident governance).
* Set the decision: the degraded-response/break-glass line is the operator's scoped
  authority — anything that would enlarge authority, act out of scope, or touch a control
  is break-glass under ADR-002-015 and cannot expand; operator-invoked containment is
  restrictive, uses normal authority, and complements rather than pre-empts the
  ADR-002-027 incident lifecycle and the CONST-011 independent Safety Authority.
* Defined five invariants OPB-INV-001…005 and traced them to RFC-011 §7/§9, RFC-002
  §7.5/§9.1, RFC-000 CONST-011, ADR-002-015 (HAG-INV-006), ADR-002-027 (SIR-INV-001/002/005),
  ADR-002-001 §6, and philosophy §22.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* Independent adversarial EV-L0 document review returned CHANGES REQUESTED with no Critical
  finding (the enforced boundary was correct via ADR-002-015 deferral; only the description
  was defective). Three Major findings were resolved: (M1) the Q2 boundary conflated
  break-glass with dual control — in ADR-002-015 an authority increase is a dual-control
  quorum (HAG-INV-001) while break-glass is restrictive-only and cannot enlarge authority
  (HAG-INV-006); OPB-INV-001/002, §1, §5, §7 now split the two, routing authority-increasing/
  re-arm actions to dual control and emergency restrictive actions to break-glass, and add a
  distinct Dual-Control Action term; (M2) the undefined "touch a constitutional safety
  control" (which collided with §7's own list of restrictive degraded-responses) was replaced
  with "disable, bypass, weaken, degrade, or clear," so restrictively *invoking* a control is
  a degraded-response and only disabling/clearing is out of ordinary authority; (M3) the Q2
  line depends on operator-scope expression owned by the not-yet-written ADR-DEV-015 — §1, §7,
  and §13 now state Q2 is fully testable only once ADR-DEV-015 fixes scope (RFC-011 §14 Q6),
  the two unambiguous ends being decidable meanwhile. Five Minor fixes: scoped-term collision
  resolved by the M1 split; the dual-control/break-glass pairing unmerged; a genuinely-weighed
  §9.6 alternative added; the §14 RFC-011 §9 protective-classification attribution moved to
  OPB-INV-005; and the SIR-INV-002 restriction clause noted. Q5 (operator-containment vs
  incident governance) was found clean. The review is EV-L0 only and confers no acceptance or
  live-readiness.
