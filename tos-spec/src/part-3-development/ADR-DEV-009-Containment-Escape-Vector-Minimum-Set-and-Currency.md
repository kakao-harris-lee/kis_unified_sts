# ADR-DEV-009 — Containment Escape-Vector Minimum Set and Currency

**ADR ID:** ADR-DEV-009
**Title:** Containment Escape-Vector Minimum Set and Currency
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-010 — Testing Strategy (with RFC-008 §11 and ADR-DEV-001)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-010 §14 Q1
**Date:** 2026-07-16
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-16
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

The **minimum escape-vector set** the RFC-010 §8 containment suite SHALL attempt is the
**union of the whole boundary**: (a) the RFC-008 §11 items 1–16 prohibited effects,
(b) the item-17 escape classes — foreign-function interface, unconstrained embedded
host, dynamic code loading, extension point, plus reflection (ADR-DEV-001 DCE-INV-004's
conservative addition beyond item 17),
(c) the ambient capabilities DCE-INV-003 forbids — clock, randomness, network,
filesystem, mutable global, host builtin, (d) the realization-specific escape surface
of the chosen ADR-DEV-001 realization, and (e) the three single-layer-failure cases of
DCE-INV-002. Each vector SHALL be **attempted, not assumed**: a vector the suite does
not attempt leaves the unexpressibility claim *open*, not closed (philosophy §37.8;
RFC-010 §8). The set is **versioned with the surface and Enforcement Mechanism**;
a Versioned Substitution of either re-derives the set and re-runs the suite. A newly
discovered escape vector becomes a **permanent regression** case.

This ADR fixes the minimum containment-test obligation. It runs no test, grants no
authority, admits no artifact, and authorizes no live operation.

---

## 2. Context

RFC-008's central claim is *unexpressibility* — every prohibited effect is not merely
forbidden but absent from the surface (RFC-008 §6 principle 1, §11). ADR-DEV-001 makes
that structural via default-deny realization and three-layer enforcement, and requires
the Enforcement Mechanism to be adversarially verified (DCE-INV-005). RFC-010 §8
requires the containment guarantee to be *tested*, with adversarial negative tests, and
warns that "a claim of unexpressibility is only as strong as the evidence that the
surface truly cannot express them." RFC-010 §14 Q1 leaves open exactly which vectors the
suite must attempt for the claim to be treated as demonstrated, and how that set is kept
current as the DSL evolves.

This ADR answers both. It defines the minimum set (what SHALL be attempted) and the
currency discipline (how the set tracks the surface and grows). It does not build the
suite, define the realization (ADR-DEV-001), or own admission/acceptance — it fixes the
coverage floor below which the unexpressibility claim is not demonstrated.

---

## 3. Decision Drivers

1. **An untested vector is an open claim, not a closed one.** A test proves only what
   its assumptions and attempted vectors cover (philosophy §37.8; RFC-010 §11.12).
2. **Unexpressibility is a whole-boundary property.** Closing fifteen of sixteen
   prohibitions and one escape class is not containment; the set must span the boundary
   (RFC-008 §11 closing rule).
3. **The surface evolves.** A new keyword, capability, or realization change can open a
   new escape; a static, one-time suite decays into false assurance (RFC-010 §8).
4. **Discovered escapes must never regress.** An escape found once and fixed must stay
   tested forever, or it silently reopens.
5. **The suite is evidence, not a gate.** Passing it earns review, not acceptance
   (RFC-010 §11; ADR-DEV-001 DCE-INV-005).

---

## 4. Scope and Non-Scope

**In scope:**

* the minimum escape-vector set the containment suite SHALL attempt;
* the currency discipline binding the set to the surface/enforcement version and growing
  it with discovered vectors;
* the requirement that the suite's Test Assumptions be explicit and bound the claim.

**Not in scope (owned elsewhere):**

* the containment suite implementation, harness, and pass criteria — RFC-010 and the
  Verification Profile;
* the DSL realization and Enforcement Mechanism under test — RFC-008, ADR-DEV-001;
* the reproducibility/identity of the surface under test — ADR-DEV-002;
* software-artifact admission and acceptance — ADR-002-029, RFC-001/VER-002-001;
* the fail-closed disposition (ADR-DEV-001 DCE-INV-006) and bounded-evaluation
  degradation (DCE-INV-007), which are containment-relevant but are verified under
  ADR-DEV-001's own §13 and lie outside the escape-vector minimum set by design;
* concrete test counts, tolerances, or scheduling, which are approved configuration.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-008 §5, RFC-010 §5 (**Conformance Test**,
**Test Assumption**), and ADR-DEV-001 (**Enforcement Mechanism**, **Escape-Closure**),
and SHALL NOT introduce synonyms. The following terms are scoped to this decision and
are non-authorizing.

* **Escape Vector** — a concrete attempt to express a prohibited effect (RFC-008 §11
  items 1–16) or to escape the authoring surface (item 17), or to reach an ambient
  capability (DCE-INV-003), through the DSL or its runtime.
* **Minimum Escape-Vector Set** — the union defined in §1/§7 that the containment suite
  SHALL attempt for the RFC-008 unexpressibility claim to be treated as demonstrated
  rather than open.
* **Containment Regression** — an Escape Vector, once discovered, retained permanently
  in the Minimum Escape-Vector Set for a surface lineage so it can never silently
  reopen.

These terms describe a test-coverage obligation. None grants authority or admits an
artifact.

---

## 6. Safety Invariants

* **CEV-INV-001 — Minimum Set Is the Union of the Boundary.** The Minimum Escape-Vector
  Set is the union of (a) RFC-008 §11 items 1–16, (b) the item-17 escape classes
  (DCE-INV-004), (c) the DCE-INV-003 ambient capabilities, (d) the realization-specific
  escape surface of the chosen ADR-DEV-001 realization, and (e) the three
  single-layer-failure cases (DCE-INV-002).
* **CEV-INV-002 — Attempted, Not Assumed.** Each vector in the set SHALL be exercised by
  an adversarial negative test that tries to express or reach it and demonstrates
  rejection, unreachability, or containment; a vector not attempted leaves the
  unexpressibility claim open, not closed (RFC-010 §8, §11.12; philosophy §37.8).
* **CEV-INV-003 — Versioned With the Surface and Enforcement.** The Minimum
  Escape-Vector Set is bound to the DSL version, the ADR-DEV-001 Enforcement Mechanism
  version, and any configuration that alters the expressible surface (a feature gate
  that enables a construct is a surface change; ADR-DEV-004 APA-INV-005 includes
  configuration in the substitution set); a Versioned Substitution of any of these
  SHALL re-derive the set and re-run the suite before the substituted surface is
  treated as demonstrated.
* **CEV-INV-004 — Discovered Vectors Are Permanent Regressions.** A newly discovered
  Escape Vector — from review, incident, or research — SHALL be added to the set and
  retained as a Containment Regression; the set grows monotonically for a surface
  lineage and is never pruned to "save time."
* **CEV-INV-005 — Assumptions Are Explicit and Bound the Claim.** The containment
  suite's Test Assumptions SHALL be recorded; the demonstrated-containment claim is
  bounded by the vectors and assumptions the suite actually covered (RFC-010 §8;
  philosophy §37.8).
* **CEV-INV-006 — Coverage Is Evidence, Not Authority.** Passing the containment suite
  is objective evidence toward review; it grants no acceptance, admission, promotion, or
  live-readiness (RFC-010 §11; ADR-DEV-001 DCE-INV-005).

---

## 7. The Minimum Escape-Vector Set (RFC-010 §14 Q1, part 1)

The set SHALL contain at least one adversarial negative test for each of the following
(CEV-INV-001), each attempting to express/reach the effect and demonstrating it is
rejected, unreachable, or contained:

* **Prohibited effects (RFC-008 §11 items 1–16 — item 12, ambient state, is
  discharged by the Ambient capabilities bullet below via DCE-INV-003):**
  self-approval; transmit/broker route;
  capacity reserve/commit/mutate/release or RCL write; alter/relax safety config;
  arm-live/issue Live Authorization or Transmission Capability; protective self-label;
  disable/bypass a safety control; signal-as-bypass; size-beyond-capacity;
  self-certify context / relabel Critical Input; act-on-Approval-as-permission; wildcard
  or "latest" scope; validity-from-health; bypass a pipeline stage; local-compliance-as-
  aggregate-permission — one vector per item.
* **Escape classes (item 17; DCE-INV-004):** FFI, unconstrained embedded host, dynamic
  code loading, and any extension point (item 17), plus reflection (DCE-INV-004's
  conservative addition).
* **Ambient capabilities (DCE-INV-003):** clock, randomness, network, filesystem,
  mutable global, host builtin.
* **Realization-specific surface (ADR-DEV-001 §7):** for an embedded/API realization,
  probes that attempt to reach the host around the surface; for a standalone language,
  probes of the grammar's escape edges.
* **Single-layer-failure cases (DCE-INV-002):** simulate an incomplete static check, an
  inadvertent capability in scope, and an isolation-boundary bypass, and show the
  remaining layers contain the effect.

A suite that omits any class attempts less than the boundary and does not demonstrate
unexpressibility (CEV-INV-002).

---

## 8. Currency and Growth (RFC-010 §14 Q1, part 2)

The set SHALL track the surface and only grow (CEV-INV-003, -004):

* it is bound to the DSL version, the Enforcement Mechanism version, and any
  configuration that alters the expressible surface (a surface-affecting feature gate);
  a change to any of these is a Versioned Substitution (ADR-DEV-004 APA-INV-005, which
  includes configuration) that re-derives the set — new keywords, capabilities, gated
  constructs, or realization changes add their own vectors — and re-runs the suite
  before the new surface is treated as demonstrated. This re-derivation is a process
  obligation (§12.1), surfaced by independent review, not a structural guarantee;
* a discovered escape (from independent review, a containment incident, or research) is
  added and kept as a Containment Regression for the surface lineage, never removed;
* the set is monotonic per lineage: coverage for a given surface only increases, so a
  once-closed vector cannot silently reopen under a later surface version.

Because the demonstrated claim is bounded by what was attempted (CEV-INV-005), the set's
growth is how the unexpressibility claim keeps pace with an evolving DSL.

---

## 9. Assumptions and the Bound on the Claim

The suite's Test Assumptions SHALL be explicit (CEV-INV-005; RFC-010 §8): the escape
vectors attempted, the realization assumed, the enforcement version, and the platform
conditions. The demonstrated-containment claim extends only over the attempted vectors
under the recorded assumptions — an un-attempted vector or an unstated assumption leaves
a corresponding open edge in the claim (philosophy §37.8). This is the discipline that
keeps a green containment suite from being read as more than it proved.

---

## 10. Alternatives Considered

* **10.1 A fixed, one-time vector list.** Rejected: the surface evolves; a static list
  decays into false assurance as new capabilities are added (CEV-INV-003; RFC-010 §8).
* **10.2 Sample a subset of the boundary.** Rejected: unexpressibility is a
  whole-boundary property; an unsampled prohibition is an untested, open claim
  (CEV-INV-001, -002).
* **10.3 Positive tests only (confirm intended authoring works).** Rejected: a suite that
  only exercises intended use proves nothing about the escape surface (RFC-010 §8;
  philosophy §37.8).
* **10.4 Drop regressions once "the code changed."** Rejected: a fixed escape can reopen
  under refactor; regressions are permanent (CEV-INV-004).
* **10.5 Treat a passing suite as admission/acceptance.** Rejected: coverage is evidence,
  not a gate (CEV-INV-006; RFC-010 §11).

---

## 11. Consequences

**Positive.**

* Gives RFC-010 §8 a concrete, whole-boundary coverage floor, so "containment tested"
  has a defined meaning.
* Currency binding keeps the claim honest as the DSL evolves; monotonic regressions
  prevent silent reopening.
* Explicit assumptions keep a green suite from over-claiming.

**Negative / costs.**

* The suite is large (one vector per prohibition + escape/ambient/realization/layer
  classes) and re-runs on every surface/enforcement substitution.
* Realization-specific vectors must be re-derived when the realization changes.
* Discovered-vector regressions accumulate, growing suite runtime over a lineage.

---

## 12. Failure Modes Introduced by This Decision

* **12.1 Under-derived set.** A new capability ships without its vector added; contained
  only if the Versioned-Substitution re-derivation (CEV-INV-003) is actually performed —
  a process obligation surfaced by independent review.
* **12.2 Assumption drift.** The platform/realization changes but the recorded
  assumptions do not; the claim silently over-reaches. Mitigated by CEV-INV-005 and
  re-derivation on substitution.
* **12.3 Regression pruning.** A regression is dropped to save runtime, reopening a
  closed vector; forbidden by CEV-INV-004.
* **12.4 Green-suite over-read.** A passing suite is read as acceptance; blocked by
  CEV-INV-006 and RFC-010 §11.

---

## 13. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010):

* **13.1** The suite attempts at least one adversarial vector for every RFC-008 §11 item
  1–16 (item 12, ambient state, via the DCE-INV-003 ambient capabilities), every
  item-17 escape class, every DCE-INV-003 ambient capability, the realization-specific
  surface, and the three single-layer-failure cases (CEV-INV-001, -002).
* **13.2** A surface or Enforcement Mechanism Versioned Substitution re-derives the set
  and re-runs the suite before the new surface is treated as demonstrated (CEV-INV-003).
* **13.3** A vector removed from the set (simulated) causes the corresponding
  unexpressibility claim to be reported as open, not demonstrated (CEV-INV-002, -005).
* **13.4** A discovered escape vector is added and retained across subsequent surface
  versions as a regression (CEV-INV-004).
* **13.5** The suite's Test Assumptions are recorded and the demonstrated claim is
  reported as bounded by them (CEV-INV-005).
* **13.6** A passing suite produces no acceptance/admission/promotion (CEV-INV-006).

---

## 14. Acceptance Criteria

ADR-DEV-009 is acceptable when:

* the minimum set spans the whole boundary (CEV-INV-001) and every vector is attempted
  adversarially (CEV-INV-002);
* the set is versioned with the surface/enforcement and re-derived on substitution
  (CEV-INV-003), with discovered vectors kept as permanent regressions (CEV-INV-004);
* Test Assumptions are explicit and bound the claim (CEV-INV-005);
* coverage remains evidence, never a gate (CEV-INV-006);
* independent adversarial review (EV-L0) confirms every §13 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 15. Traceability

| Requirement | Discharge in ADR-DEV-009 |
|---|---|
| RFC-010 §14 Q1 (minimum escape-vector set; kept current) | union-of-boundary set (§7); currency + monotonic growth (§8) |
| RFC-010 §8 (containment tested, adversarial negative tests, assumptions explicit) | attempted-not-assumed; assumptions bound the claim (CEV-INV-002, -005) |
| RFC-010 §11.12 (untested containment claim is open) | an un-attempted vector leaves the claim open (CEV-INV-002) |
| RFC-008 §11 items 1–16 + item 17 (boundary + escape-closure) | one vector per prohibition (item 12 ambient state via the DCE-INV-003 ambient bullet) + each escape class (§7; CEV-INV-001) |
| ADR-DEV-001 DCE-INV-002/003/004 (layers; ambient; escape-closure) | single-layer, ambient, and escape-class vectors (§7; CEV-INV-001) |
| ADR-DEV-001 DCE-INV-005 (enforcement verified, non-authorizing) | coverage is evidence, not authority (CEV-INV-006) |
| ADR-DEV-004 APA-INV-005 (versioned substitution) | substitution re-derives the set and re-runs the suite (CEV-INV-003) |
| ADR-DEV-002 (identity/reproducibility) | the surface under test is an exact identity; deferred there (§4) |
| philosophy §37.8 (tests prove only what they cover) | demonstrated claim bounded by attempted vectors + assumptions (CEV-INV-002, -005) |
| RFC-010 §11 (testing↔safety boundary) | coverage grants no acceptance/admission (CEV-INV-006) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes the coverage
floor and currency of the containment suite and relies on RFC-010 to build and run it.

---

## 16. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-009, resolving RFC-010 §14 Q1 (minimum adversarial escape-vector
  set and how it stays current).
* Set the decision: the minimum set is the union of the whole boundary (RFC-008 §11
  items 1–16, the item-17 escape classes, the DCE-INV-003 ambient capabilities, the
  realization-specific surface, and the three single-layer-failure cases); every vector
  is attempted, not assumed; the set is versioned with the surface/enforcement and grows
  monotonically with discovered regressions.
* Defined six invariants CEV-INV-001…006 and traced them to RFC-010 §8/§11/§11.12,
  RFC-008 §11, ADR-DEV-001 (DCE-INV-002/003/004/005), ADR-DEV-004 (APA-INV-005), and
  philosophy §37.8.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding; the union-of-boundary set was confirmed complete (no coverage hole)
  and all twelve attack sequences blocked or correctly deferred, with every citation
  verified. Two Major findings were resolved: (M1) §7's "items 1–16" bullet enumerated
  15 effects because item 12 (ambient state) is discharged by the separate ambient
  bullet — now stated explicitly in §7, §13.1, and §15 so the completeness is
  mechanically auditable; (M2) the currency trigger bound re-derivation to the DSL and
  Enforcement Mechanism versions only, while ADR-DEV-004 APA-INV-005 includes
  configuration — CEV-INV-003 and §8 now also fire on any configuration that alters the
  expressible surface (a surface-affecting feature gate). Three Minor fixes: reflection
  labelled as DCE-INV-004's addition rather than an item-17 class (§1, §7); §4 notes the
  DCE-INV-006 fail-closed and DCE-INV-007 bounded-degradation dispositions are verified
  under ADR-DEV-001's own §13 and lie outside the escape-vector set by design; and §8
  states the re-derivation is a process obligation (§12.1), not a structural guarantee.
  The review is EV-L0 only and confers no acceptance or live-readiness.
