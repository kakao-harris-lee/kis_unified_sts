# ADR-DEV-007 — Strategy Output Semantics: No-Action, Explicit Flat, and the Atomic Authored Unit

**ADR ID:** ADR-DEV-007
**Title:** Strategy Output Semantics — No-Action, Explicit Flat, and the Atomic Authored Unit
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-008 — Strategy DSL (with RFC-003 — Decision Framework)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-008 §14 Q4 and RFC-008 §14 Q5
**Date:** 2026-07-16
**Version:** 0.2 Review Draft
**Last Updated:** 2026-07-17
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

The DSL represents strategy output with two decisions fixed here:

* **No-action and explicit flat are distinct, first-class, reproducible outcomes.**
  "No-action / hold" (propose nothing; leave current state untouched) and "explicit
  flat" (propose a target of zero position) are separate, directly expressible outcomes,
  each carrying its rationale and each reproducible — never conflated, and never
  represented as an error, a null, or an omission (RFC-008 §6 principle 5; RFC-003 §16
  Q4).
* **The atomic authored unit is explicit and may be per-instrument or a portfolio
  vector, with no combined authority.** The Proposal Builder supports a per-instrument
  target and a portfolio-wide target vector; the unit is declared, not implicit. A
  portfolio vector is emitted as a set of per-instrument Proposals, **each its own
  ADR-002-020 §8 contract and each independently subject to approval, capacity
  evaluation, and isolation** — never a single aggregated authority that bypasses
  per-Proposal governance (RFC-003 §16 Q1; ADR-002-023 and ADR-002-020 §8; RFC-008 §9
  states the analogous cross-strategy rule).
* **A portfolio vector declares its component interdependence; absent a declaration it is
  atomic (fail-closed).** A portfolio-vector emission carries an explicit all-or-none
  (atomic) or mutual-independence declaration for its component targets; undeclared, it is
  atomic. Partial approval of an atomic vector (one or more per-target rejections under
  ADR-002-023) yields whole-vector non-realization plus a recorded strategy-level
  re-evaluation, never a silent naked partial — while per-target approval, capacity, and
  consumption remain un-unionized and the safety consequence of any partial is independently
  bounded by ADR-002-021 aggregate projection (RFC-003 §16 Q1; SOS-INV-006).

This ADR fixes output semantics. It grants no authority, approves nothing, commits no
capacity, and authorizes no live operation.

---

## 2. Context

RFC-008 §6 principle 5 makes no-action first-class; §8 makes the Proposal the only
output, assembled through the effect-free Proposal Builder and populating the
ADR-002-020 §8 field set; §9 requires isolation — "Multiple Authored Strategies SHALL
NOT … aggregate their Proposals into a combined authority, or bypass per-Proposal
approval and capacity evaluation" (a cross-strategy rule; the intra-strategy
portfolio-vector case is governed instead by per-contract Independent Approval,
ADR-002-023). RFC-003 §16 leaves two questions open: Q4 asks how "no-action / hold" and
"explicit flat (target = 0)" are represented as distinct, first-class, reproducible
outcomes; Q1 asks whether the atomic unit is a per-instrument target or a portfolio-wide
target vector, and whether the framework supports both. RFC-008 §14 carries the same two
as Q4 and Q5.

This ADR resolves both at the authoring surface. It defines no Proposal field
(ADR-002-020 owns that), no approval/capacity mechanism (ADR-002-023/002 own those), and
no model — it fixes how an Authored Strategy *expresses* its outcome so the distinctions
are visible, reproducible, and non-aggregating.

---

## 3. Decision Drivers

1. **No-action is a decision, not an absence** (philosophy §6; RFC-008 §6 principle 5).
   It must be as expressible, recorded, and reproducible as an action.
2. **Hold and flat are materially different economic acts.** "Do nothing" leaves
   exposure as-is; "go flat" proposes to close it. Conflating them is a safety-relevant
   ambiguity.
3. **The atomic unit determines what gets approved.** Whether the unit is a single
   instrument or a vector must be explicit so per-Proposal approval and capacity
   evaluation attach to the right object (RFC-003 §13; ADR-002-023).
4. **Aggregation is an authority-laundering risk.** A portfolio vector treated as one
   enlarged authority could bypass per-Proposal governance (RFC-008 §9; ADR-002-023).
5. **Well-formedness is necessary, never sufficient.** Each target must be complete and
   wildcard-free, but that never authorizes it (RFC-008 §8; ADR-002-020 §8).

---

## 4. Scope and Non-Scope

**In scope:**

* the distinct, first-class, reproducible representation of no-action vs explicit flat;
* the atomic authored unit (per-instrument or portfolio vector) and its explicitness;
* the prohibition on aggregating proposals into a combined authority.

**Not in scope (owned elsewhere):**

* the Proposal field set and canonical construction — ADR-002-020 §8;
* independent approval and consumption fencing — ADR-002-023;
* risk-capacity evaluation and the RCL — ADR-002-002/021;
* the decision pipeline and Proposal contract — RFC-003;
* reproducibility/identity of the outcome — ADR-DEV-002;
* concrete target encodings and unit schemas, which are approved configuration.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-008 §5 (**Proposal**, **Proposal Builder**),
RFC-003 §5, and ADR-002-020 (Approved Intent Contract field set), and SHALL NOT
introduce synonyms. The following terms are scoped to this decision and are
non-authorizing.

* **No-Action Outcome** — an authored outcome that proposes nothing and leaves the
  current position and orders untouched. It is a first-class decision, recorded with its
  rationale (RFC-008 §6 principle 5).
* **Explicit Flat** — an authored outcome that proposes a target of zero position for a
  single instrument, i.e. an action to reach flat. A portfolio-wide flat is a vector of
  per-instrument Explicit Flats, never one wildcard flat. It is an action, distinct from
  a No-Action Outcome.
* **Atomic Authored Unit** — the unit an Authored Strategy emits as one or more
  Proposals: a per-instrument target (one Proposal), or a portfolio-wide target vector
  emitted as a **set** of per-instrument Proposals, **each its own ADR-002-020 §8
  contract** — never a single multi-instrument Proposal. The unit is declared, not
  implicit.
* **Vector Interdependence Declaration** — a portfolio vector's explicit statement that its
  component targets are all-or-none (atomic) or mutually independent, carried with the
  emission as an authoring-semantics property; absent the declaration the vector is atomic
  (fail-closed). It grants no authority and does not unionize per-target approval
  (SOS-INV-006).

These terms describe output semantics. None grants authority, approves, or commits
capacity.

---

## 6. Safety Invariants

* **SOS-INV-001 — No-Action and Explicit Flat Are Distinct, First-Class, Reproducible.**
  The DSL represents a No-Action Outcome and an Explicit Flat as separate, directly
  expressible outcomes, each with rationale and each reproducible; they are never
  conflated and never represented as an error, null, or omission (RFC-008 §6 principle 5;
  RFC-003 §16 Q4; ADR-DEV-002).
* **SOS-INV-002 — The Atomic Authored Unit Is Explicit.** The Proposal Builder supports a
  per-instrument target and a portfolio-wide target vector; the unit an Authored Strategy
  emits is declared, not inferred (RFC-003 §16 Q1, §13).
* **SOS-INV-003 — No Combined Authority via Aggregation.** Neither unit lets a strategy
  aggregate proposals into a combined authority that bypasses per-Proposal approval,
  capacity evaluation, or isolation; a portfolio vector is a set of per-instrument
  targets each independently governed. The primary structural block is per-contract,
  non-unionable Independent Approval (ADR-002-023) over single-instrument contracts
  (ADR-002-020 §8); RFC-008 §9 and RFC-003 §13 state the analogous prohibition on
  aggregation *across* strategies.
* **SOS-INV-004 — Each Target Is Well-Formed and Bounded.** Each per-instrument target,
  including a component of a vector, populates the ADR-002-020 §8 field set with no
  wildcard or "latest" scope and binds the exact Decision Context Capsule (RFC-008 §8;
  ADR-002-020 §8).
* **SOS-INV-005 — Output Semantics Grant No Authority.** Representing an outcome —
  no-action, flat, or a target — is a Proposal only; it approves nothing, commits no
  capacity, and transmits nothing (RFC-008 §8; RFC-002 §9.1).
* **SOS-INV-006 — Vector Component Interdependence Is Declared; Undeclared Is Atomic
  (Fail-Closed).** A portfolio-vector emission SHALL carry, for its component targets, either
  (a) an explicit all-or-none atomicity declaration or (b) an explicit mutual-independence
  declaration; absent an explicit declaration the vector SHALL be treated as atomic. On
  partial approval — one or more per-target rejections under ADR-002-023 — an atomic vector
  SHALL NOT be partially realized as though the whole vector were approved; the outcome SHALL
  be whole-vector non-realization plus a recorded, first-class strategy-level re-evaluation on
  fresh context (SOS-INV-001), never a silent naked partial. That re-evaluation is itself
  subject to RFC-003 §9.1: if the strategy still intends to reduce exposure it re-expresses
  Explicit Flat(s), each individually classified by the Protective Action Controller under
  ADR-002-001 §6, so an atomic default preserves intent and never silently strands an intended
  reduction as a hold. A declared-independent vector allows its non-rejected targets to
  proceed under their own per-target governance, the strategy having declared that a rejected
  component does not compromise the others. This invariant fixes authoring intent-fidelity
  only: the per-target Independent Approval, capacity, and single-use consumption mechanics
  (ADR-002-023, ADR-002-002/021) are unchanged and never unionized, and the safety consequence
  of any partial (for example a naked hedge leg) is independently bounded by ADR-002-021
  aggregate projection, which credits no unproven offset (ARE-INV-005) and covers partial-fill
  prefixes.

---

## 7. No-Action vs Explicit Flat (RFC-008 §14 Q4)

The DSL SHALL provide distinct, first-class expressions (SOS-INV-001):

* a **No-Action Outcome** proposes nothing and leaves the current position, open orders,
  and exposure untouched; it is a direct, ordinary expression (RFC-008 §6 principle 5),
  recorded with rationale and reproducible (ADR-DEV-002);
* an **Explicit Flat** proposes a target of zero position for a single instrument — an
  action to close that exposure — assembled as a Proposal like any other action; a
  portfolio-wide flat is a vector of per-instrument Explicit Flats, never one wildcard
  flat (RFC-008 §8; ADR-002-020 §8);
* the two SHALL NOT be conflated: "hold" is not "close," and a strategy that intends to go
  flat SHALL express Explicit Flat, not a No-Action Outcome (which would leave exposure
  in place);
* neither is an error, a null, or a missing return; a degraded or bounded evaluation that
  produces no action produces a recorded No-Action Outcome, not an exception (RFC-008 §9;
  ADR-DEV-008 DCM-INV-003).

The distinction is load-bearing because the two produce opposite exposure effects; making
them separate first-class outcomes removes the ambiguity.

---

## 8. The Atomic Authored Unit and No Combined Authority (RFC-008 §14 Q5)

The Proposal Builder SHALL support both units explicitly (SOS-INV-002, -003):

* a **per-instrument target** is a single-instrument Proposal;
* a **portfolio-wide target vector** is emitted as a **set of per-instrument Proposals**,
  each its own ADR-002-020 §8 single-instrument contract — never one multi-instrument
  Proposal;
* the vector's **scope is exactly its enumerated targets**: an instrument outside that
  enumerated scope is untouched by this emission (its existing position and orders are
  left as-is), a deliberate hold of that instrument. This is the vector's **declared
  coverage**, not a no-action-by-omission and not an inferred flatten: the emitted set *is*
  the strategy's coverage for this evaluation, which is what distinguishes an intended
  exclusion from a mistaken omission. A strategy that intends to flatten an instrument SHALL
  include an Explicit Flat target for it (the DSL never infers a flatten from silence), and
  the strategy-level decision remains a first-class recorded outcome, never a null evaluation
  (SOS-INV-001);
* the vector's **component interdependence is declared**: it carries an explicit all-or-none
  (atomic) or mutual-independence declaration, and absent a declaration it is atomic
  (SOS-INV-006). On partial approval — a per-target rejection under ADR-002-023 — an atomic
  vector is not partially realized: the strategy-level outcome is a recorded re-evaluation on
  fresh context (subject to RFC-003 §9.1, so a still-intended reduction is re-expressed as
  Explicit Flat(s) individually classified under ADR-002-001 §6), never a silent naked
  partial. This preserves authoring intent; it neither unionizes approval (each target
  remains its own non-unionable Independent Approval Decision) nor adds a safety floor, since
  the naked-leg consequence is independently bounded by ADR-002-021 aggregate projection
  (ARE-INV-005; partial-fill-prefix coverage);
* whichever unit a strategy uses is declared, so per-Proposal approval and capacity
  evaluation attach to the right object (RFC-003 §13);
* the vector is **not** a single aggregated authority. The primary structural block is
  that each per-instrument target is its own non-unionable Independent Approval Decision
  (ADR-002-023) over a single-instrument contract (ADR-002-020 §8), each independently
  capacity-evaluated (ADR-002-002/021). A strategy SHALL NOT use a vector to obtain, in
  one approval, authority its per-instrument targets would not each obtain. (RFC-008 §9
  and RFC-003 §13 state the analogous rule for aggregation *across* strategies; the
  intra-strategy vector is blocked here by per-contract approval, not by those
  cross-strategy clauses.)
* each target is well-formed and wildcard-free (SOS-INV-004; ADR-002-020 §8).

Supporting the vector unit is a convenience of expression, never a concentration of
authority.

---

## 9. Alternatives Considered

* **9.1 Represent no-action as a null/absent Proposal.** Rejected: that makes a decision
  indistinguishable from a missing evaluation and is not first-class or reproducible
  (SOS-INV-001; RFC-008 §6 principle 5).
* **9.2 Treat explicit flat as a kind of no-action.** Rejected: they have opposite
  exposure effects; conflation is a safety-relevant ambiguity (SOS-INV-001).
* **9.3 Support only a per-instrument unit.** Rejected: portfolio-level strategies need a
  vector; RFC-003 §16 Q1 asks for both.
* **9.4 Treat a portfolio vector as one aggregated authority.** Rejected: that bypasses
  per-Proposal approval, capacity, and isolation (SOS-INV-003; RFC-008 §9; ADR-002-023).
* **9.5 Define the Proposal field set or approval here.** Rejected: owned by ADR-002-020
  and ADR-002-023 (§4).

---

## 10. Consequences

**Positive.**

* Removes the hold-vs-flat ambiguity by making both first-class, reproducible outcomes.
* Supports portfolio expression without concentrating authority.
* Keeps per-Proposal approval/capacity/isolation attached to the right unit.

**Negative / costs.**

* The DSL must carry two distinct outcome forms and both unit forms — more surface to
  design and test. The vector-as-combined-authority case is not an RFC-008 §11
  containment-escape class (so it is not in the ADR-DEV-009 minimum set); it is verified
  by §12.4 against ADR-002-020 §8 and ADR-002-023 conformance, and the vector-interdependence
  case (SOS-INV-006) by §12.7 against ADR-002-023 and ADR-002-021 conformance.
* A portfolio vector's per-target independent governance may reject part of a vector. The
  authoring model SHALL represent this by declared interdependence (SOS-INV-006): partial
  approval of an atomic vector (the fail-closed default) yields whole-vector non-realization
  plus a recorded strategy-level re-evaluation — never a silent partial — and a
  declared-independent vector lets its non-rejected targets proceed under their own per-target
  governance. This is intent-fidelity only; the safety consequence of any partial is
  independently bounded by ADR-002-021 aggregate projection.
* Authors must choose hold vs flat deliberately; the DSL cannot infer intent.

---

## 11. Failure Modes Introduced by This Decision

* **11.1 Hold/flat conflation.** A strategy intending to close emits no-action, leaving
  exposure; prevented by SOS-INV-001's distinct forms and surfaced by RFC-010 tests.
* **11.2 Vector aggregation.** A vector used to win combined authority; blocked by
  SOS-INV-003 and per-target approval (ADR-002-023).
* **11.3 No-action-as-null.** No-action represented as an absent/null Proposal, hiding the
  decision; prevented by SOS-INV-001.
* **11.4 Wildcard target in a vector.** A vector component with a wildcard/"latest" scope;
  blocked by SOS-INV-004 and ADR-002-020 §8 (and the ADR-DEV-009 wildcard vector).
* **11.5 Silent naked partial.** An atomic portfolio vector, partially approved (one leg
  rejected), is partially realized and leaves an unintended naked position; prevented by
  SOS-INV-006 (whole-vector non-realization + strategy-level re-evaluation) and independently
  bounded by ADR-002-021 aggregate projection.

---

## 12. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010):

* **12.1** No-action and explicit flat are produced, recorded, and reproduced as distinct
  first-class outcomes; neither is an error/null (SOS-INV-001).
* **12.2** A strategy intending to close expresses Explicit Flat, not No-Action, and the
  two produce opposite exposure effects (SOS-INV-001).
* **12.3** Both a per-instrument target and a portfolio vector are supported and the unit
  is explicit (SOS-INV-002).
* **12.4** A portfolio vector's targets are each independently approved and
  capacity-evaluated; a vector obtains no authority its per-instrument targets would not
  (SOS-INV-003).
* **12.5** Each target is well-formed and wildcard-free (SOS-INV-004; overlaps the
  ADR-DEV-009 wildcard vector).
* **12.6** Emitting an outcome — no-action, flat, or a target — commits no capacity and
  transmits nothing; it is a Proposal only (SOS-INV-005; RFC-002 §9.1).
* **12.7** A portfolio vector declares its component interdependence (atomic when
  undeclared); a per-target rejection of an atomic vector yields whole-vector non-realization
  plus a recorded strategy-level re-evaluation, with per-target approval/capacity/consumption
  un-unionized (SOS-INV-006; verified against ADR-002-023 and ADR-002-021 conformance, not the
  RFC-010 §8 containment suite).

---

## 13. Acceptance Criteria

ADR-DEV-007 is acceptable when:

* no-action and explicit flat are distinct, first-class, reproducible outcomes
  (SOS-INV-001);
* the atomic unit is explicit and both per-instrument and portfolio-vector forms are
  supported (SOS-INV-002);
* no aggregation yields a combined authority (SOS-INV-003);
* each target is well-formed and grants no authority (SOS-INV-004, -005);
* a portfolio vector's component interdependence is declared (atomic when undeclared), and
  partial approval of an atomic vector yields whole-vector non-realization plus a
  strategy-level re-evaluation (SOS-INV-006);
* independent adversarial review (EV-L0) confirms every §12 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 14. Traceability

| Requirement | Discharge in ADR-DEV-007 |
|---|---|
| RFC-008 §14 Q4 / RFC-003 §16 Q4 (no-action vs flat) | distinct first-class reproducible outcomes (§7; SOS-INV-001) |
| RFC-008 §14 Q5 / RFC-003 §16 Q1 (atomic unit; both supported) | explicit per-instrument or portfolio-vector unit (§8; SOS-INV-002) |
| RFC-008 §9 / RFC-003 §13 (no combined authority — cross-strategy) | analogous cross-strategy principle; the intra-strategy vector is blocked by per-contract approval (§8; SOS-INV-003) |
| RFC-008 §6 principle 5 (no-action first-class) | No-Action Outcome is first-class (§7; SOS-INV-001) |
| RFC-008 §8 (Proposal via effect-free builder) | each target well-formed, no wildcard, binds Capsule (§8; SOS-INV-004) |
| RFC-003 §13 (replaceability; per-Proposal governance) | unit explicit; per-Proposal approval/capacity attach (§8; SOS-INV-002/003) |
| ADR-002-020 §8 (canonical field set; no wildcard) | targets populate the field set, wildcard-free (SOS-INV-004) |
| ADR-002-023 (independent proposal approval, consumption fencing) | each target is a non-unionable Independent Approval Decision — the primary intra-vector block (§8; SOS-INV-003) |
| ADR-002-002/021 (capacity) | each target independently capacity-evaluated (§8; SOS-INV-003) |
| ADR-002-021 (aggregate projection; no unproven benefit; partial-fill prefixes) | naked-leg safety consequence of any partial is independently bounded; SOS-INV-006 adds intent-fidelity only (§8; SOS-INV-006) |
| RFC-003 §16 Q1 / mn-08 (portfolio reasoning at interpretation; per-target at emission) | vector emitted as per-target set; interdependence declared, undeclared atomic (§8; SOS-INV-002/006) |
| CORPUS-REVIEW-0001 M-14 (vector partial approval) | "represent gracefully" replaced by declared interdependence + fail-closed atomic default (§§8, 10; SOS-INV-006) |
| ADR-DEV-002 (reproducibility) | outcomes reproducible and recorded (§7; SOS-INV-001) |
| ADR-DEV-008 DCM-INV-003 (degraded decision first-class) | degraded → recorded No-Action, not an error (§7) |
| RFC-002 §9.1 (authority ownership) | output semantics grant no authority (SOS-INV-005) |
| philosophy §6 (no-trade valid) | No-Action is a decision (§3) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes output
semantics and relies on ADR-002-020/023/002 for the field set, approval, and capacity.

---

## 15. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-007, resolving RFC-008 §14 Q4 (no-action vs explicit flat) and Q5
  (atomic authored unit; both supported without combined authority).
* Set the decision: no-action and explicit flat are distinct, first-class, reproducible
  outcomes; the atomic unit is explicit and may be per-instrument or a portfolio vector,
  the vector being per-target governed rather than an aggregated authority.
* Defined five invariants SOS-INV-001…005 and traced them to RFC-008 §6/§8/§9,
  RFC-003 §13/§16, ADR-002-020 §8, ADR-002-023, ADR-002-002/021, and ADR-DEV-002/008.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding; the safety property (a portfolio vector cannot win one aggregated
  approval) holds and all attack sequences were blocked. Three Major findings were
  resolved: (M1) §5's "emits as a Proposal" (singular) contradicted SOS-INV-004 (a vector
  is N contracts) — now "one or more Proposals, each its own ADR-002-020 §8 contract";
  (M2) no-action-within-a-vector-by-omission collided with SOS-INV-001's "never an
  omission" — §8 now fixes the vector's scope to its enumerated targets (instruments
  outside scope untouched, a declared coverage, not omission), reconciled with
  SOS-INV-001; (M3) RFC-008 §9 / RFC-003 §13 are cross-strategy scoped while the ADR led
  with them for the intra-strategy vector — the primary block is now attributed to
  ADR-002-023 (non-unionable Independent Approval) + ADR-002-020 §8 (single-instrument
  contract), with §9/§13 as the analogous cross-strategy rule (§§1, 2, 8, SOS-INV-003,
  §14). Three Minor fixes: a §12.6 obligation for SOS-INV-005; "Explicit Flat … for a
  scope" narrowed to a single instrument (a portfolio flat is a vector of per-instrument
  flats); and §10 clarified that the vector case is verified via ADR-002-020/023
  conformance, not the RFC-010 §8 containment suite. The review is EV-L0 only and confers
  no acceptance or live-readiness.

### v0.2 — Wave 5 (CORPUS-REVIEW-0001 Theme E, M-14)

* Added **SOS-INV-006** (Vector Component Interdependence Is Declared; Undeclared Is Atomic,
  fail-closed): a portfolio vector carries an explicit all-or-none or mutual-independence
  declaration for its components; undeclared it is atomic. Partial approval of an atomic
  vector (per-target rejection under ADR-002-023) yields whole-vector non-realization plus a
  recorded, first-class strategy-level re-evaluation (SOS-INV-001), never a silent naked
  partial; the re-evaluation follows RFC-003 §9.1 (a still-intended reduction re-expresses
  Explicit Flat(s) classified under ADR-002-001 §6). This replaced the §10 "represent
  gracefully" phrase with a normative rule (§§1, 5, 6, 8, 10, 11.5, 12.7, 13, 14).
* Recorded that SOS-INV-006 fixes authoring intent-fidelity only and introduces no SAFE-xxx:
  per-target Independent Approval, capacity, and single-use consumption (ADR-002-023,
  ADR-002-002/021) are unchanged and never unionized, and the naked-leg safety consequence of
  any partial is independently bounded by ADR-002-021 aggregate projection (ARE-INV-005;
  partial-fill-prefix coverage) — confirming the CORPUS-REVIEW-0001 M-14 mitigant that the
  review had left unconfirmed.
* Sharpened §8's declared-coverage prose to name the declared-coverage-vs-mistaken-omission
  distinction explicitly. A seventh invariant (SOS-INV-007) was judged unnecessary: the
  enumerated set is the strategy's declared coverage, omission is a deliberate hold, and the
  DSL never infers a flatten from silence, so an intended exclusion is already distinguished
  from a mistaken omission without new mechanism (a strategy bug that drops a target is caught
  by RFC-010 testing and ADR-DEV-005 review, not by a DSL invariant that cannot know unstated
  intent).
* Synchronized VER-DEV-001 and EVIDENCE-REGISTER-DEV: added SOS-EV-006, the ADR-DEV-007 gate
  now requires SOS-EV-001..006, invariant→evidence coverage 90→91, development-track total
  96→97.
* Introduced no SAFE-xxx requirement, numeric bound, or authority. Independent adversarial
  EV-L0 review of these Wave-5 changes is **owed** (reviewer provenance to be recorded per
  ADR-DEV-005; M-18); this patch confers no acceptance or live-readiness.
