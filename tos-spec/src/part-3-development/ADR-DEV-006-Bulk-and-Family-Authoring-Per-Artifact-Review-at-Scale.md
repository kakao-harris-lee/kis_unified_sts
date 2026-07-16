# ADR-DEV-006 — Bulk and Family Authoring: Per-Artifact Review at Scale

**ADR ID:** ADR-DEV-006
**Title:** Bulk and Family Authoring — Per-Artifact Review at Scale
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-009 — Agent Guide (with ADR-DEV-004 and ADR-DEV-005)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-009 §14 Q5
**Date:** 2026-07-16
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-16
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

When an Authoring Agent produces or revises a large family of strategies at once,
**per-artifact review and admission SHALL NOT be diluted by scale**:

* the **reviewable and admissible unit is the individual artifact** — a batch is not
  reviewed or admitted as one unit (RFC-009 §10; ADR-DEV-004 APA-INV-007);
* **no artifact inherits another's review, provenance, or admission** — each carries its own
  complete Authoring Provenance and its own admission candidacy (ADR-DEV-004
  APA-INV-001/004/005; ADR-002-029);
* each artifact's conformance is **independently reviewed per ADR-DEV-005** — running the
  author over many artifacts is not review of any of them (ADR-DEV-005 AIR-INV-002);
* **volume is a hazard, not a warrant**: throughput of authorship is not evidence of quality
  (RFC-009 §10). Batch tooling MAY assist triage and organization but confers no review or
  admission; the unit remains the individual artifact.

This ADR grants no authority, admits no artifact, and confers no review.

---

## 2. Context

RFC-009 §10 anticipates automated and AI-assisted authorship and states its characteristic
hazard directly: "Scale is a hazard, not a warrant. An Authoring Agent can produce many
strategies quickly; volume SHALL NOT reduce the per-artifact review and admission each
requires (ADR-002-029). Throughput of authorship is not evidence of quality." ADR-DEV-004
(APA-INV-007) already states that the volume of authorship does not reduce the per-artifact
provenance, review, and admission each artifact requires, and defers the concrete bulk
discipline here; ADR-DEV-005 fixes the independent-review standard, including that a second
run of the same author is not independent.

RFC-009 §14 Q5 leaves open how the authoring discipline handles an Authoring Agent that
revises a large family of strategies at once, so that per-artifact review and admission are
not diluted by scale. This ADR fixes that discipline. It defines no admission mechanism
(ADR-002-029), no provenance record (ADR-DEV-004), and no independent-review standard
(ADR-DEV-005) — it fixes that the unit of review and admission remains the individual
artifact under bulk authorship.

---

## 3. Decision Drivers

1. **Scale is a hazard, not a warrant** (RFC-009 §10). Volume must not buy a shortcut past
   per-artifact review.
2. **Generated source is source** (RFC-009 §9). A machine-produced family is reviewed and
   admitted like any other source.
3. **Fluency and throughput are not quality** (RFC-009 §10; philosophy §7). A large,
   plausible batch is not a reviewed one.
4. **Admission is per content-addressed artifact** (ADR-002-029; ADR-DEV-004 APA-INV-005).
   A batch has no single admissible identity.
5. **Independent review is per artifact** (ADR-DEV-005). Running the author many times is not
   review.

---

## 4. Scope and Non-Scope

**In scope:**

* that the reviewable/admissible unit remains the individual artifact under bulk/family
  authorship;
* the prohibition on inheritance of review/provenance/admission across a batch;
* the role of batch tooling as assistance, not authority.

**Not in scope (owned elsewhere):**

* the software-artifact admission mechanism — ADR-002-029;
* the Authoring Provenance record and versioned substitution — ADR-DEV-004;
* the independent-review standard — ADR-DEV-005;
* the DSL surface and containment — RFC-008, ADR-DEV-001;
* concrete batch tooling, triage heuristics, and throughput limits, which are approved
  configuration.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-009 §5 (**Authoring Agent**, **Authoring Act**,
**Authored Strategy**), RFC-002 §3.1, and ADR-DEV-004/005/002-029, and SHALL NOT introduce
synonyms. The following terms are scoped to this decision and are non-authorizing.

* **Bulk/Family Authoring** — an Authoring Act (or a coordinated set of them) in which an
  Authoring Agent produces or revises many Authored Strategies at once (RFC-009 §10).
* **Reviewable/Admissible Unit** — the individual Authored Strategy artifact that is
  independently reviewed (ADR-DEV-005) and admitted (ADR-002-029); a batch is not such a
  unit.
* **Batch Tooling** — tooling that assists triage, organization, or presentation of a
  Bulk/Family Authoring run; it confers no review or admission.

These terms describe a review-at-scale discipline. None grants authority, review, or
admission.

---

## 6. Safety Invariants

* **BFA-INV-001 — The Reviewable/Admissible Unit Is the Individual Artifact.** Each artifact
  in a Bulk/Family Authoring run is independently reviewed and admitted; a batch is not
  reviewed or admitted as one unit (RFC-009 §10; ADR-DEV-004 APA-INV-007; ADR-DEV-005;
  ADR-002-029).
* **BFA-INV-002 — No Inheritance Across a Batch.** No artifact inherits another's review,
  Authoring Provenance, or admission; each carries its own provenance and admission
  candidacy (ADR-DEV-004 APA-INV-001/004/005).
* **BFA-INV-003 — Volume Is a Hazard, Not a Warrant.** Throughput of authorship is not
  evidence of quality; scale does not reduce the per-artifact review each artifact requires
  (RFC-009 §10; philosophy §7).
* **BFA-INV-004 — Independent Review Per Artifact.** Each artifact's conformance is
  independently verified per ADR-DEV-005; running the author over many artifacts is not
  review of any of them (ADR-DEV-005 AIR-INV-002).
* **BFA-INV-005 — Batch Tooling Is Assistance, Not Authority.** Batch Tooling may assist
  triage and organization but confers no review, admission, or acceptance; the unit remains
  the individual artifact (RFC-009 §10; ADR-002-029).
* **BFA-INV-006 — Bulk Authoring Grants No Authority.** Producing many artifacts creates no
  authority, admission, or acceptance (RFC-002 §9.1; ADR-002-029).

---

## 7. The Unit Is the Individual Artifact (RFC-009 §14 Q5)

Under Bulk/Family Authoring the unit does not change (BFA-INV-001, -002):

* each artifact is independently reviewed (ADR-DEV-005) and admitted on its own
  content-addressed identity (ADR-002-029; ADR-DEV-004 APA-INV-005); there is no batch-level
  review verdict or batch-level admission;
* no artifact inherits another's review, provenance, or admission — a family sharing a
  template still requires each member to carry its own complete Authoring Provenance
  (ADR-DEV-004 APA-INV-001) and its own admission candidacy (APA-INV-004);
* a change to one member is a Versioned Substitution of that member (ADR-DEV-004
  APA-INV-005), not of the family;
* volume is a hazard, not a warrant — a large, fluent, quickly-produced batch is not thereby
  reviewed, and throughput is not evidence of quality (RFC-009 §10; philosophy §7).

The response to scale is more disciplined per-artifact review and admission, never more
trust in the producer (RFC-009 §10).

---

## 8. Batch Tooling Is Assistance, Not Authority

Tooling may help at scale without becoming a shortcut (BFA-INV-005):

* Batch Tooling may triage, cluster, diff, or present a family to reviewers and admitters,
  and may parallelize the *mechanics* of running per-artifact review and admission;
* it confers no review verdict and no admission — a tool that "passes a batch" has reviewed
  and admitted nothing (BFA-INV-005; ADR-002-029);
* a tool acting as the independent reviewer of any artifact is subject to ADR-DEV-005
  (independent, itself verified, not the author or common-mode with it);
* the reviewable/admissible unit remains the individual artifact regardless of how the batch
  is organized.

Tooling scales the *work* of per-artifact review; it never replaces the per-artifact
verdict.

---

## 9. Alternatives Considered

* **9.1 Review/admit a batch as one unit.** Rejected: admission is per content-addressed
  artifact; a batch has no single admissible identity (BFA-INV-001; ADR-002-029).
* **9.2 Let family members inherit a template's review/admission.** Rejected: no artifact
  inherits another's review or admission (BFA-INV-002; ADR-DEV-004 APA-INV-004).
* **9.3 Treat throughput/coverage of a batch as quality evidence.** Rejected: volume is a
  hazard, not a warrant (BFA-INV-003; RFC-009 §10).
* **9.4 Let a batch-pass tool stand in for per-artifact review.** Rejected: tooling confers
  no review; the unit is the individual artifact (BFA-INV-005; ADR-DEV-005).
* **9.5 Define the admission mechanism or provenance record here.** Rejected: owned by
  ADR-002-029 and ADR-DEV-004 (§4).

---

## 10. Consequences

**Positive.**

* Prevents scale from buying a shortcut past per-artifact review and admission.
* Keeps admission on exact per-artifact identity, so a family cannot ride one approval.
* Lets tooling scale the work without becoming an authority.

**Negative / costs.**

* Reviewing and admitting each family member individually is expensive at scale — the
  intended, conservative cost.
* Batch tooling must be built to assist per-artifact review, not to short-circuit it.
* A large family produces a large review and admission load, which throughput cannot reduce.

---

## 11. Failure Modes Introduced by This Decision

* **11.1 Batch admission.** A family admitted as one unit; blocked by BFA-INV-001 and
  ADR-002-029 (per-artifact identity).
* **11.2 Template inheritance.** A member riding a template's review/admission; blocked by
  BFA-INV-002.
* **11.3 Throughput-as-quality.** A large batch treated as reviewed because it is large;
  blocked by BFA-INV-003.
* **11.4 Tool-as-reviewer.** A batch tool's "pass" treated as review; blocked by BFA-INV-005
  and ADR-DEV-005.

---

## 12. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010):

* **12.1** A bulk/family run is not reviewed or admitted as one unit; each artifact is
  independent (BFA-INV-001).
* **12.2** No artifact inherits another's review, provenance, or admission (BFA-INV-002).
* **12.3** Throughput/coverage of a batch is not accepted as quality evidence (BFA-INV-003).
* **12.4** Each artifact is independently reviewed per ADR-DEV-005 (BFA-INV-004).
* **12.5** Batch tooling confers no review or admission, and producing many artifacts grants
  no authority (BFA-INV-005, -006).

---

## 13. Acceptance Criteria

ADR-DEV-006 is acceptable when:

* the reviewable/admissible unit remains the individual artifact under bulk authoring
  (BFA-INV-001);
* no artifact inherits another's review/provenance/admission (BFA-INV-002);
* volume is a hazard not a warrant, with per-artifact independent review preserved
  (BFA-INV-003, -004);
* batch tooling is assistance not authority, and bulk authoring grants nothing (BFA-INV-005,
  -006);
* independent adversarial review (EV-L0) confirms every §12 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 14. Traceability

| Requirement | Discharge in ADR-DEV-006 |
|---|---|
| RFC-009 §14 Q5 (bulk/family authoring not diluted by scale) | unit is the individual artifact; no inheritance (§7; BFA-INV-001, -002) |
| RFC-009 §10 (scale is a hazard, not a warrant; throughput ≠ quality) | volume is a hazard; per-artifact review preserved (§7; BFA-INV-003) |
| RFC-009 §9 (generated source is source) | a machine family is reviewed/admitted like any source (§3) |
| ADR-DEV-004 APA-INV-001/004/005/007 (provenance; admission candidacy; versioned substitution; scale does not dilute) | each member carries its own provenance/admission; one-member change is its own substitution (§7; BFA-INV-002) |
| ADR-DEV-005 AIR-INV-002 (no self-review; independent per artifact) | independent review per artifact; tool reviewer per ADR-DEV-005 (§§7, 8; BFA-INV-004, -005) |
| ADR-002-029 (per content-addressed admission) | no batch-level admission; per-artifact identity (§7; BFA-INV-001) |
| RFC-002 §9.1 (authority ownership) | bulk authoring grants no authority (BFA-INV-006) |
| philosophy §7 (fluency/prediction limited authority) | throughput/fluency is not quality (§3; BFA-INV-003) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes the bulk-authoring
review-at-scale discipline and relies on ADR-002-029, ADR-DEV-004, and ADR-DEV-005 for
admission, provenance, and independent review.

---

## 15. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-006, resolving RFC-009 §14 Q5 (bulk/family authoring per-artifact
  review and admission not diluted by scale).
* Set the decision: the reviewable/admissible unit is the individual artifact; no artifact
  inherits another's review, provenance, or admission; each is independently reviewed
  (ADR-DEV-005) and admitted (ADR-002-029); volume is a hazard, not a warrant; and batch
  tooling is assistance, not authority.
* Defined six invariants BFA-INV-001…006 and traced them to RFC-009 §9/§10, ADR-DEV-004
  (APA-INV-001/004/005/007), ADR-DEV-005 (AIR-INV-002), ADR-002-029, RFC-002 §9.1, and
  philosophy §7.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* **Independent EV-L0 review is OWED.** An in-context self-adversarial consistency review
  was performed (invariants defined and cross-referenced; citations checked against source),
  but the independent EV-L0 reviewer dispatch failed on a session/usage limit (resets
  2026-07-16 18:50 KST). Unlike ADR-DEV-001 through -014, this ADR has **not** yet had an
  independent adversarial EV-L0 review; that review is owed and SHALL be run before
  ADR-DEV-006 advances beyond Review Draft. The self-review is not independent and confers
  no acceptance or live-readiness.
