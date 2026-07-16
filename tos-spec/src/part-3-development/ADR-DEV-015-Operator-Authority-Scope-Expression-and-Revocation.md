# ADR-DEV-015 — Operator Authority-Scope Expression and Revocation

**ADR ID:** ADR-DEV-015
**Title:** Operator Authority-Scope Expression and Revocation
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-011 — Operational Guidelines (with ADR-002-015 and ADR-002-007)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-011 §14 Q6
**Date:** 2026-07-16
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-16
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

Operator authority is **expressed and revoked along explicit dimensions** — account,
strategy, instrument, venue, operating mode, software version, safety configuration, risk
capacity, and current safety state (Vision §6.6; RFC-011 §7). An Operational Act is
conforming **only if it is within the operator's current, valid scope on every applicable
dimension**; acting outside any dimension is out-of-scope and routes to the ADR-DEV-013
dual-control/break-glass boundary. Scope is **explicit, attributable, and does not persist
merely because it was valid in the past**; it is time-bounded where appropriate.
**Revocation is immediate and complete** — a revoked scope grants nothing. The
scope-issuance and revocation *mechanism* is owned by ADR-002-015 (human authority) and
ADR-002-007 (live authorization); this ADR fixes the operator-facing expression and
revocation discipline.

This ADR grants no authority; expressing a scope issues none.

---

## 2. Context

RFC-011 §7 holds that operational authority is bounded by many dimensions — "account,
strategy, instrument, venue, operating mode, software version, safety configuration, risk
capacity, and current safety state" — and that an operator SHALL NOT act outside the
dimension its authority is scoped to. Vision §6.6 makes authority explicit, scoped,
time-bounded where appropriate, attributable, and revocable, and states it does not
persist merely because it was valid in the past. ADR-002-015 owns human-authority
governance (Changed Context Invalidates, Approval Is Not Authority); ADR-002-007 owns
live authorization and its scope.

RFC-011 §14 Q6 leaves open how operator authority scopes are *expressed and revoked*
consistent with Vision §6.6 and ADR-002-015. This ADR fixes that discipline — and, in
doing so, supplies the scope definition on which the ADR-DEV-013 degraded-response /
out-of-scope boundary depends. It defines neither the human-authority mechanism
(ADR-002-015) nor the live-authorization mechanism (ADR-002-007) — it fixes the
operator-facing expression and revocation.

---

## 3. Decision Drivers

1. **Authority must be explicit** (philosophy §14; Vision §6.6). An operator cannot act on
   authority it cannot point to.
2. **Authority is multi-dimensional** (RFC-011 §7). A single "operator role" is
   insufficient; scope is per-dimension.
3. **Authority does not persist** (Vision §6.6). Past validity is not present authority.
4. **Revocation must be immediate and complete** (ADR-002-015 HAG-INV-008). A stale grant
   is a live hazard.
5. **The out-of-scope boundary needs a scope definition** (ADR-DEV-013). Q2's line is only
   testable once scope is expressed.

---

## 4. Scope and Non-Scope

**In scope:**

* the explicit dimensions along which operator authority is expressed;
* the requirement that an act be within current, valid scope on every applicable dimension;
* the non-persistence and immediate, complete revocation of scope.

**Not in scope (owned elsewhere):**

* the human-authority, dual-control, and break-glass mechanism — ADR-002-015;
* the live-authorization scope and re-arm mechanism — ADR-002-007;
* the degraded-response / out-of-scope routing that consumes this scope — ADR-DEV-013;
* risk-capacity scope issuance — ADR-002-002; safety-state — RFC-002/ADR series;
* concrete scope schemas, dimension encodings, and time bounds, which are approved
  configuration.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-011 §5 (**Operator**, **Operational Act**),
RFC-002 §3.1, Vision §6.6 (authority dimensions), and ADR-002-015, and SHALL NOT introduce
synonyms. The following terms are scoped to this decision and are non-authorizing.

* **Authority Scope** — the set of per-dimension bounds within which an operator's authority
  is valid: account, strategy, instrument, venue, operating mode, software version, safety
  configuration, risk capacity, and current safety state (Vision §6.6; RFC-011 §7).
* **Out-of-Scope Act** — an Operational Act outside the operator's current, valid Authority
  Scope on any applicable dimension; it is non-conforming as ordinary operation and routes
  to ADR-DEV-013.
* **Revocation** — the immediate, complete withdrawal of an Authority Scope; a revoked scope
  grants no authority (ADR-002-015 HAG-INV-008).

These terms describe an authority-scope discipline. None grants authority.

---

## 6. Safety Invariants

* **OAS-INV-001 — Authority Is Scoped on Explicit Dimensions.** Operator authority is
  expressed along explicit dimensions — account, strategy, instrument, venue, operating
  mode, software version, safety configuration, risk capacity, and current safety state
  (Vision §6.6; RFC-011 §7).
* **OAS-INV-002 — An Act Is Conforming Only Within Current Scope on Every Dimension.** An
  Operational Act is conforming only if within the operator's current, valid Authority Scope
  on every applicable dimension; acting outside any dimension is an Out-of-Scope Act that
  routes to ADR-DEV-013 (dual-control or break-glass by direction).
* **OAS-INV-003 — Authority Is Explicit, Attributable, and Does Not Persist.** An Authority
  Scope is explicit and attributable; it does not persist merely because it was valid in the
  past and is time-bounded where appropriate (Vision §6.6; philosophy §14).
* **OAS-INV-004 — Revocation Is Immediate and Complete.** Revoking an Authority Scope is
  immediate and complete; a revoked scope grants no authority, and an act under a revoked
  scope is an Out-of-Scope Act (RFC-011 §7; ADR-002-015 HAG-INV-008).
* **OAS-INV-005 — Scope Mechanism Is Owned Upstream.** The scope-issuance and revocation
  mechanism is owned by ADR-002-015 (human authority) and ADR-002-007 (live authorization);
  this ADR fixes only the operator-facing expression/revocation discipline.
* **OAS-INV-006 — Expression Grants No Authority.** Expressing, observing, or recording an
  Authority Scope creates no authority; authority is issued by its owner and remains
  revocable (RFC-002 §9.1).

---

## 7. Expression Along Explicit Dimensions (RFC-011 §14 Q6, part 1)

Operator authority SHALL be expressed per dimension (OAS-INV-001, -002, -003):

* the dimensions are account, strategy, instrument, venue, operating mode, software version,
  safety configuration, risk capacity, and current safety state (Vision §6.6; RFC-011 §7);
* an Operational Act is conforming only if within the operator's current, valid scope on
  every applicable dimension — a valid account scope does not authorize an out-of-scope
  instrument or mode;
* the scope is explicit and attributable, so both the operator and review can point to the
  exact authority under which an act was taken (philosophy §14);
* the scope does not persist merely because it was valid in the past, and is time-bounded
  where appropriate (Vision §6.6).

Per-dimension expression is what makes "within the operator's scope" (ADR-DEV-013) a
decidable test rather than a judgment call.

---

## 8. Revocation (RFC-011 §14 Q6, part 2)

Revocation is immediate and complete (OAS-INV-004):

* revoking an Authority Scope withdraws it immediately and completely; there is no grace
  period during which a revoked scope still authorizes;
* an act attempted under a revoked or expired scope is an Out-of-Scope Act (OAS-INV-002),
  routed to ADR-DEV-013;
* a changed safety-relevant context invalidates the affected scope (ADR-002-015
  HAG-INV-008); the operator does not infer continued authority from a scope that was valid
  before the change;
* the revocation *mechanism* — how the owner effects and propagates it — is owned by
  ADR-002-015/007; this ADR fixes that revocation is immediate, complete, and
  non-authorizing (OAS-INV-005, -006).

A scope is authority only while current; revocation returns it to nothing.

---

## 9. Alternatives Considered

* **9.1 A single undifferentiated "operator" authority.** Rejected: authority is
  multi-dimensional; one role cannot express account/instrument/mode bounds (OAS-INV-001;
  RFC-011 §7).
* **9.2 Let authority persist until explicitly revoked.** Rejected: authority does not
  persist on past validity, and is time-bounded where appropriate (OAS-INV-003; Vision §6.6).
* **9.3 Allow a grace period after revocation.** Rejected: revocation is immediate and
  complete; a grace period is a live stale grant (OAS-INV-004; ADR-002-015 HAG-INV-008).
* **9.4 Treat a valid scope on one dimension as sufficient.** Rejected: an act must be within
  scope on every applicable dimension (OAS-INV-002).
* **9.5 Define the scope-issuance mechanism here.** Rejected: owned by ADR-002-015/007 (§4).

---

## 10. Consequences

**Positive.**

* Makes operator authority explicit and per-dimension, so acts are attributable to an exact
  scope.
* Supplies the scope definition the ADR-DEV-013 out-of-scope boundary needs, making Q2
  testable.
* Immediate, complete revocation removes stale-grant hazards.

**Negative / costs.**

* Expressing and checking authority per dimension is more work than a single role flag.
* No grace period after revocation may interrupt an in-flight operator action — the
  intended, conservative cost.
* Time-bounded scopes require re-granting, adding operational overhead.

---

## 11. Failure Modes Introduced by This Decision

* **11.1 Stale scope.** An act under an expired/revoked scope; blocked by OAS-INV-004 and
  routed out-of-scope.
* **11.2 Single-dimension sufficiency.** A valid account scope used to act on an out-of-scope
  instrument; blocked by OAS-INV-002.
* **11.3 Persistent authority.** Authority assumed from past validity; blocked by
  OAS-INV-003.
* **11.4 Expression-as-authority.** Recording a scope treated as granting it; blocked by
  OAS-INV-006.

---

## 12. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010; enforcement owned by
ADR-002-015/007):

* **12.1** An act outside the operator's scope on any dimension is out-of-scope
  (OAS-INV-002).
* **12.2** Authority is not inferred from a past-valid scope (OAS-INV-003).
* **12.3** A revoked or expired scope grants no authority immediately and completely
  (OAS-INV-004).
* **12.4** A valid scope on one dimension does not authorize an act out of scope on another
  (OAS-INV-002).
* **12.5** Expressing or recording a scope grants no authority (OAS-INV-006).

---

## 13. Acceptance Criteria

ADR-DEV-015 is acceptable when:

* authority is expressed along the explicit dimensions and an act must be within current
  scope on every applicable dimension (OAS-INV-001, -002);
* scope is explicit, attributable, and non-persistent (OAS-INV-003);
* revocation is immediate and complete (OAS-INV-004);
* the mechanism stays owned by ADR-002-015/007 and expression grants no authority
  (OAS-INV-005, -006);
* independent adversarial review (EV-L0) confirms every §12 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 14. Traceability

| Requirement | Discharge in ADR-DEV-015 |
|---|---|
| RFC-011 §14 Q6 (operator authority-scope expression/revocation) | per-dimension expression (§7); immediate/complete revocation (§8) |
| RFC-011 §7 (bounded by many dimensions) | the dimension list; act within scope on every dimension (§7; OAS-INV-001, -002) |
| Vision §6.6 (explicit, scoped, time-bounded, attributable, revocable; not persistent) | explicit non-persistent scope; immediate revocation (§§7, 8; OAS-INV-003, -004) |
| ADR-002-015 (human authority; HAG-INV-008 changed context invalidates) | changed context invalidates scope; mechanism owned there (§8; OAS-INV-004, -005) |
| ADR-002-007 (live authorization scope) | live-authorization scope mechanism owned there (OAS-INV-005) |
| ADR-DEV-013 (degraded-response vs out-of-scope) | this scope is what ADR-DEV-013's out-of-scope test consumes (§7; OAS-INV-002) |
| RFC-002 §9.1 (authority ownership) | expression grants no authority (OAS-INV-006) |
| philosophy §14 (authority must be explicit) | explicit, attributable scope (§7; OAS-INV-003) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes operator
authority-scope expression and revocation and relies on ADR-002-015/007 for the mechanism.

---

## 15. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-015, resolving RFC-011 §14 Q6 (operator authority-scope expression and
  revocation) and supplying the scope definition on which ADR-DEV-013's out-of-scope
  boundary depends.
* Set the decision: authority is expressed along explicit dimensions (account, strategy,
  instrument, venue, mode, software version, safety configuration, risk capacity, safety
  state); an act is conforming only within current scope on every applicable dimension;
  scope is explicit, attributable, non-persistent, and time-bounded where appropriate; and
  revocation is immediate and complete.
* Defined six invariants OAS-INV-001…006 and traced them to RFC-011 §7, Vision §6.6,
  ADR-002-015 (HAG-INV-008), ADR-002-007, ADR-DEV-013, RFC-002 §9.1, and philosophy §14.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* **Independent EV-L0 review is OWED.** An in-context self-adversarial consistency review
  was performed (invariants defined and cross-referenced; citations checked against source;
  the ADR-DEV-013 dependency confirmed coherent), but the independent EV-L0 reviewer
  dispatch failed on a session/usage limit (resets 2026-07-16 18:50 KST). Unlike
  ADR-DEV-001 through -014, this ADR has **not** yet had an independent adversarial EV-L0
  review; that review is owed and SHALL be run before ADR-DEV-015 advances beyond Review
  Draft. The self-review is not independent and confers no acceptance or live-readiness.
