# ADR-DEV-011 — Test Assumptions and the Pre-Deployment / Runtime-Monitoring Boundary

**ADR ID:** ADR-DEV-011
**Title:** Test Assumptions and the Pre-Deployment / Runtime-Monitoring Boundary
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-010 — Testing Strategy (with ADR-002-028)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-010 §14 Q5 and RFC-010 §14 Q6
**Date:** 2026-07-16
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-16
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

Two decisions are fixed here:

* **Test Assumptions are recorded, first-class, reviewable artifacts.** Each Conformance
  Test and suite records its preconditions, fixtures, platform conditions, and the
  vectors/scenarios attempted, as a structured artifact; a passing suite's demonstrated
  claim extends only over its recorded assumptions, and unstated assumptions are visible
  open edges, not implied coverage (RFC-010 §8; philosophy §37.8).
* **Pre-deployment testing and runtime monitoring are distinct, complementary phases with
  no gap and no duplication within their joint purview.** RFC-010 pre-deployment testing
  demonstrates properties on a fixed Artifact Identity *before* deployment; ADR-002-028
  owns runtime *continuous conformance monitoring* of the running system. Within that joint
  purview every safety-relevant property is demonstrated pre-deployment, monitored at
  runtime, or both; neither re-runs the other. Runtime prevention/enforcement, admission,
  promotion, and incident handling are owned elsewhere and are out of scope — and being
  monitored never substitutes for prevention (philosophy §11). A recorded pre-deployment
  Test Assumption whose runtime falsity would invalidate a demonstrated property is proposed
  as a runtime-Monitored Assumption — an open coordination dependency on ADR-002-028 — the
  assumptions being the bridge.

This ADR fixes the assumption-recording discipline and the testing/monitoring boundary.
It defines no monitoring protocol (ADR-002-028 owns it), grants no authority, and
authorizes no live operation.

---

## 2. Context

RFC-010 §8 requires containment-suite Test Assumptions to be recorded; §5 defines a Test
Assumption as an explicitly recorded precondition a test depends on, and philosophy §37.8
holds that a test proves nothing beyond its assumptions and acceptance criteria. RFC-010
§12 already states that runtime continuous conformance monitoring "is a distinct
discipline from pre-deployment testing and is architecturally owned by ADR-002-028 (and
its RFC-002 §10.30 component), not by RFC-010 [or RFC-011]," and that RFC-010 "ends at
pre-deployment demonstration and supplies no runtime monitor." ADR-002-028 owns safety-telemetry
integrity, continuous conformance monitoring, monitoring gaps, and alert escalation.

RFC-010 §14 leaves two questions open: Q5 asks how Test Assumptions are recorded and
reviewed so the bounded scope of a passing suite is visible rather than implied; Q6 asks
where the boundary sits between RFC-010 pre-deployment testing and ADR-002-028 runtime
monitoring so the two neither leave a gap nor duplicate each other. This ADR resolves
both. It defines the assumption-recording discipline and the boundary; it defines none of
the ADR-002-028 monitoring mechanism.

---

## 3. Decision Drivers

1. **A green suite over-claims unless its assumptions are visible** (philosophy §37.8;
   RFC-010 §8). Implicit assumptions hide the bounded scope of a pass.
2. **Independent review needs the assumptions explicitly** (visibility per RFC-010 §6
   principle 2 and §8; independence per §11.10); a reviewer cannot bound a claim it cannot
   see.
3. **Pre-deployment and runtime answer different questions.** Testing asks "does this
   artifact demonstrate the property before deployment?"; monitoring asks "does the
   running system remain conformant?" (RFC-010 §12; ADR-002-028).
4. **A gap is a silent hole; duplication wastes and diverges.** Within the
   testing/monitoring purview every safety-relevant property needs an owning phase — never
   neither; but monitoring is not prevention, and being monitored never discharges a
   prevention obligation (philosophy §11; ADR-002-028 §1).
5. **Assumptions can break in production.** An assumption that held in test may fail live;
   that transition must be monitored, not silently trusted (ADR-002-028).

---

## 4. Scope and Non-Scope

**In scope:**

* the recording and review discipline for Test Assumptions;
* the boundary between RFC-010 pre-deployment testing and ADR-002-028 runtime monitoring;
* the bridge by which a pre-deployment assumption becomes a runtime-monitored condition.

**Not in scope (owned elsewhere):**

* the continuous conformance monitoring protocol, telemetry integrity, monitoring gaps,
  and alert escalation — ADR-002-028 (and its RFC-002 §10.30 component);
* runtime prevention/enforcement (the architecture's pre-execution barriers) and the
  properties owned by admission (ADR-002-029), promotion (ADR-002-025), human authority
  (ADR-002-015), and incident (ADR-002-027) — outside the testing/monitoring purview;
* the containment-suite coverage floor and its assumptions' content — ADR-DEV-009;
* the testing discipline itself and pass criteria — RFC-010 and the Verification Profile;
* reproducibility/identity of the tested artifact — ADR-DEV-002;
* concrete assumption schemas and monitoring thresholds, which are approved configuration.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-010 §5 (**Conformance Test**, **Test
Assumption**), RFC-002 §3.1, and ADR-002-028 (continuous conformance monitoring,
Safety Monitoring Gap), and SHALL NOT introduce synonyms. The following terms are scoped to this
decision and are non-authorizing.

* **Test Assumption** (reused, RFC-010 §5) — an explicitly recorded precondition, fixture,
  or platform condition a Conformance Test depends on; a result claims nothing beyond it
  (philosophy §37.8).
* **Assumption Record** — the structured, reviewable artifact attached to a Conformance
  Test or suite that carries its Test Assumptions and the vectors/scenarios attempted, so
  the bounded scope of a pass is explicit.
* **Monitored Assumption** — a recorded pre-deployment Test Assumption whose continued
  validity at runtime is observed by ADR-002-028 monitoring, so its failure in production
  is surfaced rather than silently trusted.

These terms describe a recording-and-boundary discipline. None grants authority or defines
the monitoring protocol.

---

## 6. Safety Invariants

* **TAB-INV-001 — Test Assumptions Are Recorded, First-Class Artifacts.** Each Conformance
  Test and suite records its preconditions, fixtures, platform conditions, and attempted
  vectors/scenarios as an Assumption Record (RFC-010 §5, §8; philosophy §37.8).
* **TAB-INV-002 — The Claim Is Bounded by Recorded Assumptions.** A passing suite's
  demonstrated claim extends only over its recorded Test Assumptions; an unstated
  assumption is a visible open edge, not implied coverage (philosophy §37.8; cf.
  ADR-DEV-009 CEV-INV-005).
* **TAB-INV-003 — Pre-Deployment Demonstration and Runtime Monitoring Are Distinct.**
  RFC-010 pre-deployment testing demonstrates properties on a fixed Artifact Identity
  before deployment; ADR-002-028 owns runtime continuous conformance monitoring of the
  running system. RFC-010 defines no monitoring protocol and does not run continuously
  (RFC-010 §12; ADR-002-028).
* **TAB-INV-004 — No Gap Within the Purview.** Within the *joint purview* of pre-deployment
  testing and runtime monitoring, every safety-relevant property is demonstrated
  pre-deployment, monitored at runtime, or both; a property in that purview owned by
  neither is an open gap that SHALL be surfaced, never silently uncovered — pre-deployment
  by independent review and the ADR-DEV-009 floor, at runtime as an ADR-002-028 Safety
  Monitoring Gap (RFC-010 §12). Runtime **prevention/enforcement** — the
  architecture's pre-execution barriers — is a distinct discipline this boundary does not
  enumerate, and **being monitored is not adequacy where the architecture requires
  prevention**: monitoring observes, it does not prevent (philosophy §11, §37.3; RFC-010
  §6 principle 5; ADR-002-028 §1). Properties owned by other phases — admission (ADR-002-029),
  promotion (ADR-002-025), human authority (ADR-002-015), incident (ADR-002-027) — are
  outside this purview, not gaps.
* **TAB-INV-005 — No Duplication.** Pre-deployment demonstration does not run continuously
  in production, and runtime monitoring does not re-derive the pre-deployment
  demonstration; each owns its phase (RFC-010 §12; ADR-002-028).
* **TAB-INV-006 — Assumptions Bridge the Two (Proposed Coordination with ADR-002-028).**
  A recorded pre-deployment Test Assumption **whose runtime falsity would invalidate a
  property demonstrated under it** SHALL be proposed, at acceptance, as a Monitored
  Assumption. Whether and how it is monitored is owned by ADR-002-028; because
  ADR-002-028's Monitor Coverage Manifest does not today enumerate assumption-derived
  obligations, admitting a Monitored Assumption is a **coordination obligation on
  ADR-002-028** (an open dependency), not something this ADR adds unilaterally. An
  assumption that held in test but breaks in production is then a monitoring signal, not a
  silent failure (ADR-002-028).
* **TAB-INV-007 — Recording and Boundary Grant No Authority.** An Assumption Record, and
  the testing/monitoring boundary, are evidence and structure; they confer no acceptance,
  admission, or live-readiness (RFC-010 §11).

---

## 7. Recording and Reviewing Test Assumptions (RFC-010 §14 Q5)

Every Conformance Test and suite SHALL carry an Assumption Record (TAB-INV-001, -002):

* it records the preconditions, fixtures, platform conditions, and the vectors/scenarios
  the suite actually attempted (RFC-010 §8; for containment, the ADR-DEV-009 minimum set);
* it is structured and reviewable, so an independent reviewer sees the bounded scope of a
  passing suite explicitly rather than inferring it (RFC-010 §6 principle 2 and §8 for
  visibility; §11.10 for independence; philosophy §37.8);
* the demonstrated claim extends only over the recorded assumptions; an assumption that is
  not recorded is not part of the demonstrated claim, and the corresponding scope is a
  visible open edge (TAB-INV-002);
* an Assumption Record is evidence, not authority — a complete record does not accept,
  admit, or promote anything (TAB-INV-007).

Recording assumptions is what turns "the suite passed" into "the suite passed *under these
stated conditions*," which is the only claim philosophy §37.8 permits.

---

## 8. The Pre-Deployment / Runtime-Monitoring Boundary (RFC-010 §14 Q6)

The boundary is drawn so the two phases are complementary (TAB-INV-003, -004, -005):

* **Pre-deployment (RFC-010).** Testing demonstrates properties on a fixed Artifact
  Identity (ADR-DEV-002) *before* deployment: determinism, isolation, containment,
  no-action correctness, and the like. It ends at demonstration and supplies no runtime
  monitor (RFC-010 §12).
* **Runtime (ADR-002-028).** Continuous conformance monitoring observes the *running*
  system's conformance in production — telemetry integrity, monitoring coverage, gaps, and
  alert escalation. RFC-010 defines none of this.
* **No gap within the purview.** Within the joint purview of testing and monitoring, every
  safety-relevant property is demonstrated pre-deployment, monitored at runtime, or both. A
  *pre-deployment* coverage gap is caught pre-deployment — by independent review (RFC-010
  §11.10) and the ADR-DEV-009 coverage floor, not by runtime monitoring, which cannot see a
  demonstration that was supposed to happen and did not — and a *runtime* coverage gap is a
  Safety Monitoring Gap surfaced restrictively by ADR-002-028. Runtime prevention/
  enforcement is a distinct discipline outside this boundary, and being monitored never
  substitutes for prevention where the architecture requires it (philosophy §11, §37.3;
  RFC-010 §6 principle 5; ADR-002-028 §1); properties owned by admission/promotion/human-authority/
  incident are outside the purview, not gaps (TAB-INV-004).
* **No duplication.** Pre-deployment demonstration is not re-run continuously in
  production, and runtime monitoring does not re-derive the pre-deployment demonstration;
  each owns its phase (TAB-INV-005).
* **The bridge (proposed coordination).** A recorded pre-deployment Test Assumption whose
  runtime falsity would invalidate a property demonstrated under it is proposed, at
  acceptance, as a Monitored Assumption: the property was *demonstrated* under that
  assumption pre-deployment, and its *continued* validity would be *monitored* at runtime.
  Because ADR-002-028's coverage manifest does not yet enumerate assumption-derived
  obligations, this is an **open coordination dependency on ADR-002-028**, not an obligation
  this ADR imposes unilaterally; an assumption that breaks in production is then surfaced by
  ADR-002-028, not silently trusted (TAB-INV-006).

The seam is exactly the assumptions: what testing demonstrated conditionally, monitoring
watches for the conditions holding — closing the gap without duplicating the work.

---

## 9. Alternatives Considered

* **9.1 Leave Test Assumptions implicit.** Rejected: a green suite then over-claims; the
  reviewer cannot bound it (TAB-INV-002; philosophy §37.8).
* **9.2 Re-run pre-deployment tests continuously in production as "monitoring."** Rejected:
  duplicates ADR-002-028 and conflates a fixed-artifact demonstration with running-system
  conformance (TAB-INV-005; RFC-010 §12).
* **9.3 Let runtime monitoring stand in for pre-deployment demonstration.** Rejected:
  monitoring observes production, it does not demonstrate a property before deployment; a
  gap would open pre-deployment (TAB-INV-003, -004).
* **9.4 Trust that test-time assumptions hold forever in production.** Rejected: an
  assumption can break live; its continued validity must be monitored (TAB-INV-006;
  ADR-002-028).
* **9.5 Define the monitoring protocol here.** Rejected: owned by ADR-002-028 (§4).

---

## 10. Consequences

**Positive.**

* Makes the bounded scope of a passing suite explicit and reviewable (philosophy §37.8).
* Draws a boundary that is gap-free and duplication-free within the joint purview of
  testing and monitoring, with assumptions as the bridge.
* Turns a test-time assumption into a monitored condition, so its production failure is
  surfaced.

**Negative / costs.**

* Every suite must carry a structured Assumption Record — authoring and review burden.
* Identifying which assumptions must become Monitored Assumptions requires coordination
  with ADR-002-028 ownership.
* The boundary must be maintained as properties move between phases.

---

## 11. Failure Modes Introduced by This Decision

* **11.1 Implicit assumption.** A load-bearing assumption unrecorded; the claim silently
  over-reaches. Contained by TAB-INV-001/002 and independent review.
* **11.2 Boundary gap.** A safety-relevant property in the purview owned by neither phase:
  a *pre-deployment* coverage gap is caught by independent review and the ADR-DEV-009
  coverage floor (not by runtime monitoring, which cannot see a missing pre-deployment
  demonstration), and a *runtime* coverage gap is a Safety Monitoring Gap surfaced by
  ADR-002-028 (TAB-INV-004).
* **11.3 Duplication drift.** Pre-deployment and runtime checks diverge on the same
  property; prevented by TAB-INV-005's phase ownership.
* **11.4 Unmonitored broken assumption.** A test-time assumption breaks live but is not a
  Monitored Assumption; TAB-INV-006 requires the bridge, and a miss is an ADR-002-028
  coverage concern.

---

## 12. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010, with the monitoring side owned
by ADR-002-028):

* **12.1** Each suite carries a structured Assumption Record and its claim is reported as
  bounded by it (TAB-INV-001, -002).
* **12.2** An unrecorded assumption is reported as an open edge, not implied coverage
  (TAB-INV-002).
* **12.3** A property demonstrated pre-deployment is not re-run continuously as
  "monitoring," and monitoring does not re-derive the demonstration (TAB-INV-003, -005).
* **12.4** *(review/traceability obligation, not an RFC-010-executed test)* A safety-relevant
  property in the purview owned by neither phase is surfaced — a pre-deployment coverage
  gap by independent review / the ADR-DEV-009 floor, a runtime gap by ADR-002-028
  (TAB-INV-004).
* **12.5** *(coordination obligation, owner ADR-002-028)* A recorded assumption whose
  runtime falsity would invalidate a demonstrated property is proposed as a Monitored
  Assumption; its admission into the ADR-002-028 coverage manifest is an open dependency
  (TAB-INV-006).

---

## 13. Acceptance Criteria

ADR-DEV-011 is acceptable when:

* Test Assumptions are recorded, first-class, reviewable artifacts bounding the claim
  (§7; TAB-INV-001, -002);
* pre-deployment testing and runtime monitoring are distinct with no gap and no
  duplication within their joint purview (§8; TAB-INV-003, -004, -005);
* assumptions bridge the two so a broken production assumption is surfaced (TAB-INV-006);
* recording and the boundary grant no authority (TAB-INV-007), with the monitoring
  protocol left to ADR-002-028;
* independent adversarial review (EV-L0) confirms every §12 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 14. Traceability

| Requirement | Discharge in ADR-DEV-011 |
|---|---|
| RFC-010 §14 Q5 (assumptions recorded/reviewed; scope visible) | Assumption Record; claim bounded (§7; TAB-INV-001, -002) |
| RFC-010 §14 Q6 (testing↔monitoring boundary; no gap/duplication) | distinct phases; no gap and no duplication *within the joint purview*; prevention and other phases out of purview; assumption bridge (§8; TAB-INV-003…006) |
| RFC-010 §5 (Test Assumption) | reused; recorded as an artifact (§5; TAB-INV-001) |
| RFC-010 §8 (containment assumptions explicit) | Assumption Record includes attempted vectors (§7) |
| RFC-010 §6 principle 2, §8 (assumption visibility); §11.10 (independence) | assumptions visible to and bounding the reviewer (§7; TAB-INV-002) |
| philosophy §11, §37.3; RFC-010 §6 principle 5; ADR-002-028 §1 (prevention primacy) | being monitored is not adequacy where prevention is required; prevention is outside the purview (§8; TAB-INV-004) |
| RFC-010 §12 (monitoring owned by ADR-002-028; RFC-010 ends at pre-deployment) | phase distinction; no monitor defined here (§8; TAB-INV-003) |
| ADR-002-028 (continuous conformance monitoring; Safety Monitoring Gap) | runtime phase and Safety Monitoring Gap owned there; Monitored Assumptions are an open coordination dependency on it (§8; TAB-INV-003…006) |
| ADR-DEV-009 CEV-INV-005 (containment assumptions bound the claim) | consistent assumption discipline (§7; TAB-INV-002) |
| ADR-DEV-002 (Artifact Identity) | pre-deployment demonstration is on a fixed identity (§8) |
| philosophy §37.8 (tests prove only what they cover) | claim bounded by recorded assumptions (§§1, 7; TAB-INV-002) |
| RFC-010 §11 (testing↔safety boundary) | recording/boundary grant no authority (TAB-INV-007) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes the
assumption-recording discipline and the testing/monitoring boundary and relies on
ADR-002-028 for the runtime monitoring protocol.

---

## 15. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-011, resolving RFC-010 §14 Q5 (recording/reviewing Test Assumptions)
  and Q6 (the pre-deployment-testing ↔ runtime-monitoring boundary).
* Set the decision: Test Assumptions are recorded, first-class, reviewable artifacts that
  bound a passing suite's claim; pre-deployment testing (RFC-010, on a fixed Artifact
  Identity) and runtime continuous conformance monitoring (ADR-002-028) are distinct
  phases with no gap and no duplication, bridged by Monitored Assumptions.
* Defined seven invariants TAB-INV-001…007 and traced them to RFC-010 §5/§8/§11/§12,
  ADR-002-028, ADR-DEV-002/009, and philosophy §37.8.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* Independent adversarial EV-L0 document review returned CHANGES REQUESTED with one
  Critical finding, now resolved. (C1) The "No Gap" invariant framed testing + monitoring
  as an exhaustive two-bucket partition over *every* safety-relevant property, which erased
  runtime prevention/enforcement and licensed the forbidden misread "monitored, therefore
  covered, therefore prevention unnecessary" — TAB-INV-004, §1, §3, §4, and §8 now scope
  "no gap" to the *joint purview* of testing and monitoring, state that runtime
  prevention/enforcement is a distinct discipline outside this boundary, that being
  monitored is not adequacy where prevention is required (philosophy §11, §37.3; RFC-010
  §6 principle 5; ADR-002-028 §1), and that admission/promotion/human-authority/incident properties
  are outside the purview, not gaps. Three Major findings were resolved: (M1) pre-deployment
  gap detection was mis-assigned to runtime monitoring — now split by phase (pre-deployment
  gaps caught by independent review / the ADR-DEV-009 floor, runtime gaps by ADR-002-028),
  with §12.4 reclassified as a review obligation; (M2) the Monitored Assumption bridge was
  under-specified and imposed an obligation ADR-002-028's coverage manifest does not
  enumerate — TAB-INV-006 and §8 now define the criterion (runtime falsity would invalidate
  a demonstrated property) and mark it an explicit *open coordination dependency* on
  ADR-002-028, not a unilateral imposition; (M3) "no gap AND no duplication" is now
  established only within the joint purview. Five Minor fixes: the §2 RFC-010 §12 quote
  marks its "[or RFC-011]" elision; the canonical "Safety Monitoring Gap" term is used;
  assumption-visibility re-anchored on RFC-010 §6 principle 2 / §8 (with §11.10 for
  independence); the §14 Q5/Q6 back-annotations were already added; and §12 obligations
  now name their owning discipline. The review is EV-L0 only and confers no acceptance or
  live-readiness.
