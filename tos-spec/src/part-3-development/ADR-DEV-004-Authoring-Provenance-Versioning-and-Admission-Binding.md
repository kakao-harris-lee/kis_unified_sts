# ADR-DEV-004 — Authoring Provenance, Versioning/Substitution, and Admission Binding

**ADR ID:** ADR-DEV-004
**Title:** Authoring Provenance, Versioning/Substitution, and Admission Binding
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-009 — Agent Guide (with RFC-008 §14 Q7)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-009 §14 Q1 and RFC-008 §14 Q7
**Date:** 2026-07-15
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-15
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

Every Authoring Act SHALL produce a **minimum-complete Authoring Provenance record**
and bind it to admission and identity:

* **Minimum record:** author actor identity (human or Authoring Agent); the complete
  set of inputs that determined the artifact — for an Authoring Agent, its prompts,
  retrieved/context inputs, and model and tool versions; the source revision of the
  authored artifact; and the targeted DSL version, ADR-DEV-001 Enforcement Mechanism
  version, and configuration version.
* **Binding:** the Authoring Provenance binds to the ADR-DEV-002 Artifact Identity and
  into the ADR-002-029 Source Revision Manifest and admission evidence. **Generated
  source is source** — an AI-authored artifact records the same provenance and is
  reviewed and admitted identically (RFC-009 §9, §10).
* **Conservative:** an artifact whose Authoring Provenance cannot be established is
  **not admissible** for live authoring (ADR-002-029 §1).
* **Versioned substitution:** any change to the artifact, its DSL version, Enforcement
  Mechanism version, or configuration is a recorded, versioned substitution producing
  a new Artifact Identity and a new ADR-002-029 Release Generation — never an in-place
  mutation, and no superseded generation is revived (RFC-008 §6 principle 8; RFC-003
  §13).

This ADR defines the authoring-side provenance record and its binding obligation. It
grants no authority, admits no artifact, and defines no part of the admission
protocol, which remains owned by ADR-002-029.

---

## 2. Context

RFC-009 §9 requires each Authoring Act to record its Authoring Provenance — actor
identity, inputs, tool and model versions, and source revision — "so it can bind into
the Source Revision Manifest and admission evidence of ADR-002-029," and states that
"generated source is source." RFC-009 §10 adds that an Authoring Agent's prompts,
retrieved context, and model version are part of Authoring Provenance and that "an
authored artifact whose provenance cannot be established is not admissible
(ADR-002-029 §1)." RFC-008 §6 principle 8 and §9 require everything to be versioned
and a change to be a recorded, versioned substitution.

RFC-009 §14 Q1 asks for the *minimum* provenance record for AI-authored admissibility
and *where* it binds; RFC-008 §14 Q7 asks for the versioning/substitution protocol
and how it interacts with ADR-002-029 admission. ADR-002-029 already defines the
admission decision, the immutable Source Revision Manifest, exact content-addressed
identity (SCI-INV-002), and monotonic Release Generations. What is open is the
authoring-side obligation that feeds them. This ADR fixes that minimum record and its
binding; it defines no part of the admission mechanism.

---

## 3. Decision Drivers

1. **An untrusted author's output is only reviewable if its provenance is known**
   (RFC-009 §9; philosophy §13). Provenance is what lets the system trust the review
   rather than the author.
2. **AI authorship is not exempt.** "Generated source is source"; scale and fluency
   are hazards, not warrants (RFC-009 §10).
3. **Admission needs an exact, immutable identity and lineage** (ADR-002-029
   SCI-INV-002/003); the authoring side SHALL feed it, not bypass it.
4. **A change must never be a silent mutation** (RFC-008 §6 principle 8; RFC-003 §13);
   substitution must be recorded and generation-fenced (ADR-002-029).
5. **Unestablished provenance is conservative** — no eligibility for dependent new
   risk (ADR-002-029 §1; philosophy §8).

---

## 4. Scope and Non-Scope

**In scope:**

* the minimum Authoring Provenance record and its required fields;
* where the record binds (Artifact Identity; ADR-002-029 Source Revision Manifest and
  admission evidence);
* the versioned-substitution obligation on the authoring side and its generation
  fencing;
* the conservative treatment of unestablished provenance.

**Not in scope (owned elsewhere):**

* the Artifact Admission Decision, manifests, Release Generation, and runtime
  attestation *mechanism* — ADR-002-029; this ADR feeds them;
* the exact content-addressed identity mechanism — ADR-002-029 SCI-INV-002; the
  identity granularity is fixed by ADR-DEV-002;
* what constitutes *independent review* of an AI-authored artifact — ADR-DEV-005;
* the Decision Context Capsule and Critical Input governance — ADR-002-018;
* the DSL surface and enforcement — RFC-008, ADR-DEV-001;
* the concrete provenance schema and field encodings, which are approved
  configuration.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-000 §6, RFC-002 §3.1, RFC-008 §5, RFC-009
§5, and the ADR series (**Source Revision Manifest**, **Artifact Admission Decision**,
**Release Generation**, ADR-002-029 §§5.2, 5.7, 5.8), and SHALL NOT introduce
synonyms. The following terms are scoped to this decision and are non-authorizing.

* **Authoring Act** — the production or modification of an Authored Strategy, its
  configuration bindings, or its supporting evidence, whether by a human or an
  Authoring Agent (RFC-009 §5).
* **Authoring Provenance** — the record that establishes how an Authored Strategy came
  to be: actor identity, the complete determining input set (for an agent: prompts,
  retrieved context, model and tool versions), source revision, and targeted DSL /
  Enforcement Mechanism / configuration versions (RFC-009 §9, §10).
* **Versioned Substitution** — the replacement of an Authored Strategy or any of its
  bound versions by a new, recorded Artifact Identity and Release Generation; never an
  in-place mutation (RFC-008 §6 principle 8; ADR-002-029).

These terms describe an authoring-side record. None grants authority, admits an
artifact, or performs review.

---

## 6. Safety Invariants

* **APA-INV-001 — Authoring Provenance Is Mandatory and Minimum-Complete.** Every
  Authoring Act SHALL record actor identity; the complete determining input set (for
  an Authoring Agent: prompts, retrieved context, model and tool versions); the source
  revision; and the targeted DSL, Enforcement Mechanism, and configuration versions
  (RFC-009 §9, §10).
* **APA-INV-002 — Generated Source Is Source.** An AI-authored artifact records the
  same Authoring Provenance and is reviewed and admitted identically to any other;
  "a tool wrote it" is not an exemption (RFC-009 §9, §10; ADR-002-029 §1).
* **APA-INV-003 — Provenance Binds to Identity and Admission.** Authoring Provenance
  SHALL bind to the ADR-DEV-002 Artifact Identity and into the ADR-002-029 Source
  Revision Manifest and admission evidence (RFC-009 §9).
* **APA-INV-004 — Unestablished Provenance Is Inadmissible.** An artifact whose
  Authoring Provenance cannot be established is not admissible for live authoring
  (ADR-002-029 §1; philosophy §8).
* **APA-INV-005 — Change Is a Versioned Substitution.** Any change to the artifact,
  DSL version, Enforcement Mechanism version, or configuration SHALL produce a new
  Artifact Identity and requires a new ADR-002-029 Release Generation (issued by
  admission, never reusing the predecessor's); no in-place mutation, and no superseded
  generation is revived (RFC-008 §6 principle 8; RFC-003 §13; ADR-002-029).
* **APA-INV-006 — Provenance Is Evidence, Not Authority or Verification.** Recording
  provenance grants no admission and is not the independent review; a rich provenance
  record or a fluent rationale is not conformance (RFC-009 §10; ADR-DEV-005;
  philosophy §33).
* **APA-INV-007 — Scale Does Not Dilute.** The volume of authorship SHALL NOT reduce
  the per-artifact provenance, review, and admission each artifact requires (RFC-009
  §10). *(The bulk-authoring review discipline itself is owned by ADR-DEV-006
  (planned).)*

---

## 7. The Minimum Authoring Provenance Record (RFC-009 §14 Q1)

The Authoring Provenance record SHALL contain, at minimum (APA-INV-001):

* **actor identity** — the human or Authoring Agent responsible for the Authoring Act;
* **determining inputs** — the complete set of inputs that produced the artifact; for
  an Authoring Agent this includes its prompts, retrieved/context inputs, and model
  and tool versions (RFC-009 §10 prompt-and-input integrity);
* **source revision** — the exact revision of the authored source;
* **targeted versions** — the DSL version, the ADR-DEV-001 Enforcement Mechanism
  version, and the configuration version the artifact is authored against.

This minimum extends RFC-009 §14 Q1's enumerated fields (actor, prompt/input set, tool
and model versions, source revision) with the targeted DSL, Enforcement Mechanism, and
configuration versions, because the same source under a different DSL or enforcement
version is a different behavior surface (ADR-DEV-002; ADR-DEV-001 §9). A record missing
any minimum field leaves provenance unestablished and the artifact inadmissible
(APA-INV-004). The concrete schema is approved configuration; the minimum field set is
the safety obligation.

---

## 8. Binding to Identity and Admission (RFC-009 §14 Q1, "where bound")

The Authoring Provenance SHALL bind (APA-INV-003):

* to the **ADR-DEV-002 Artifact Identity** — so the provenance describes exactly the
  content-addressed artifact that is tested, reviewed, admitted, and run;
* into the **ADR-002-029 Source Revision Manifest and admission evidence** — so the
  Artifact Admission Decision (`ADMIT` / `DENY` / `UNKNOWN`) evaluates an artifact
  whose provenance is present and exact (ADR-002-029 §1).

This ADR requires the binding; ADR-002-029 owns the manifest structure, the admission
decision, and generation fencing. An `ADMIT` remains a non-authorizing eligibility
gate (ADR-002-029 §1); provenance binding does not create admission. Realizing the
binding requires the ADR-002-029 Source Revision Manifest schema (whose field set
ADR-002-029 leaves open) to carry the minimum Authoring Provenance record — including
the AI-authoring fields (agent prompts, retrieved context, model and tool versions) —
so the obligation is not orphaned at the admission gate.

---

## 9. Versioning and Substitution (RFC-008 §14 Q7)

Every change SHALL be a Versioned Substitution (APA-INV-005):

* a change to the Authored Strategy source, its DSL version, its Enforcement Mechanism
  version, or its configuration produces a **new Artifact Identity** (ADR-DEV-002) and
  requires a **new ADR-002-029 Release Generation**, issued by admission and never
  reusing the predecessor's;
* substitution is recorded, never an in-place unversioned mutation (RFC-008 §6
  principle 8; RFC-003 §13);
* no rollback, rebuild, re-authoring, or identical byte sequence revives a superseded,
  revoked, or rejected generation — it uses a new generation (ADR-002-029 §1);
* the superseded and successor artifacts each retain their own provenance, so the
  lineage of substitutions is auditable.

Interaction with admission: a Versioned Substitution is a new admission candidate; it
inherits no admission from its predecessor (ADR-002-029). This closes RFC-008 §14 Q7's
"how does it interact with software-artifact admission."

---

## 10. Alternatives Considered

* **10.1 Exempt AI-authored artifacts (trust the generator).** Rejected: "generated
  source is source"; exemption would let scale and fluency bypass review (RFC-009 §10;
  APA-INV-002).
* **10.2 Record provenance but do not bind it to identity/admission.** Rejected:
  unbound provenance can be paired with a different artifact and proves nothing about
  what runs (APA-INV-003; ADR-DEV-002 ARI-INV-003 and §9).
* **10.3 Allow in-place revision without a new generation.** Rejected: silent mutation
  defeats lineage and lets an unreviewed change ride a predecessor's admission
  (APA-INV-005; ADR-002-029).
* **10.4 Treat a rich provenance record as sufficient for admission.** Rejected:
  provenance is evidence, not admission or verification (APA-INV-006; ADR-002-029 §1).
* **10.5 Define the admission decision/manifest here.** Rejected: owned by ADR-002-029;
  duplicating it would create a divergent second protocol (§4).

---

## 11. Consequences

**Positive.**

* Makes an untrusted (including AI) author's output reviewable and admissible on an
  exact, bound provenance, closing RFC-009 §14 Q1 and RFC-008 §14 Q7.
* Generation-fenced substitution prevents an unreviewed change from inheriting
  admission.
* Unestablished provenance fails closed.

**Negative / costs.**

* Every Authoring Act must capture a complete provenance record, including agent
  prompts/context/model versions — tooling and storage cost.
* Every change becomes a new generation and a new admission candidate — no cheap
  in-place edits.
* Provenance capture for AI authorship must be complete enough to be reproducible,
  raising authoring-pipeline requirements.

---

## 12. Failure Modes Introduced by This Decision

* **12.1 Incomplete provenance.** A minimum field is missing; conservative by
  APA-INV-004 (inadmissible), but a capture gap could ship — surfaced by admission
  evaluation (ADR-002-029) and RFC-010 tests.
* **12.2 Provenance/artifact mismatch.** A record bound to the wrong identity;
  prevented by APA-INV-003 binding to the ADR-DEV-002 Artifact Identity.
* **12.3 In-place edit escaping a new generation.** Prevented by APA-INV-005; a process
  gap is owned operationally by ADR-002-029 generation fencing.
* **12.4 Provenance treated as admission.** Guarded by APA-INV-006 and ADR-002-029 §1
  (`ADMIT` is a separate, non-authorizing gate).

---

## 13. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010):

* **13.1** An Authoring Act missing any minimum provenance field yields an
  inadmissible artifact (APA-INV-001, -004).
* **13.2** An AI-authored artifact records prompts, retrieved context, and model/tool
  versions and is admitted identically to a human-authored one (APA-INV-002).
* **13.3** Authoring Provenance binds to the exact Artifact Identity and appears in the
  Source Revision Manifest evidence (APA-INV-003).
* **13.4** A change to source, DSL version, Enforcement Mechanism version, or
  configuration produces a new Artifact Identity and a new Release Generation, and the
  successor inherits no admission (APA-INV-005).
* **13.5** A superseded/revoked generation is not revived by rebuild or identical bytes
  (APA-INV-005; ADR-002-029).
* **13.6** A rich provenance record alone does not produce admission or verification
  (APA-INV-006).
* **13.7** A bulk/family authoring run does not reduce the per-artifact obligation:
  each artifact in a batch independently requires a complete Authoring Provenance
  record (APA-INV-001) and its own admission candidacy (APA-INV-004), none inheriting
  another's provenance or admission (APA-INV-007).

---

## 14. Acceptance Criteria

ADR-DEV-004 is acceptable when:

* the minimum Authoring Provenance record is defined and mandatory, including the
  AI-authorship fields (APA-INV-001, -002);
* the record binds to the ADR-DEV-002 Artifact Identity and the ADR-002-029 Source
  Revision Manifest/admission evidence (APA-INV-003);
* unestablished provenance is inadmissible (APA-INV-004);
* every change is a recorded, generation-fenced Versioned Substitution (APA-INV-005);
* provenance is evidence only, not authority/admission/verification, and scale does
  not dilute (APA-INV-006, -007);
* independent adversarial review (EV-L0) confirms every §13 obligation is discharged
  and every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 15. Traceability

| Requirement | Discharge in ADR-DEV-004 |
|---|---|
| RFC-009 §14 Q1 (minimum provenance; where bound) | minimum record (§7) bound to Artifact Identity + Source Revision Manifest (§8; APA-INV-001, -003) |
| RFC-008 §14 Q7 (versioning/substitution; admission interaction) | Versioned Substitution → new identity + new generation; no inherited admission (§9; APA-INV-005) |
| RFC-009 §9 (Authoring Provenance for admission) | mandatory provenance feeding ADR-002-029 (§§7, 8) |
| RFC-009 §10 (generated source is source; prompt/input integrity; scale) | AI provenance identical; scale does not dilute (APA-INV-002, -007) |
| RFC-008 §6 principle 8; RFC-003 §13 (versioned substitution) | change is a new recorded identity/generation (§9; APA-INV-005) |
| ADR-002-029 §1, SCI-INV-002/003 (admission; exact identity; closed lineage) | provenance binds into manifests/admission; mechanism deferred (§8; APA-INV-003, -004) |
| ADR-DEV-002 (Artifact Identity) | provenance binds to the content-addressed identity (§8) |
| ADR-DEV-001 (Enforcement Mechanism version) | recorded among targeted versions (§7) |
| ADR-DEV-005 (independent review) | provenance is evidence, not verification (APA-INV-006) |
| philosophy §8, §13, §33 | conservative-on-unknown; untrusted proposer; demonstration-required (§§3, 6) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes the
authoring-side provenance and substitution obligations and relies on ADR-002-029 for
admission and ADR-DEV-002 for identity.

---

## 16. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-004, resolving RFC-009 §14 Q1 (minimum Authoring Provenance and
  where bound) and RFC-008 §14 Q7 (versioning/substitution and admission interaction).
* Set the decision: a minimum-complete Authoring Provenance record (actor, determining
  inputs incl. agent prompts/context/model versions, source revision, targeted
  versions), bound to the ADR-DEV-002 Artifact Identity and the ADR-002-029 Source
  Revision Manifest/admission evidence; unestablished provenance is inadmissible; every
  change is a generation-fenced Versioned Substitution.
* Defined seven invariants APA-INV-001…007 and traced them to RFC-009 §§9, 10,
  RFC-008 §6/§9, RFC-003 §13, ADR-002-029 (§1, SCI-INV-002/003), and ADR-DEV-001/002/005.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no
  acceptance or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding. Twelve sequences were attempted — admit-on-incomplete-provenance,
  AI-exemption, in-place-edit-rides-predecessor-admission, unbound provenance,
  provenance-as-admission/verification, revive-superseded-generation, scale-laundering,
  mutable-label-as-identity, partial record, config-only-change, enforcement-only-change,
  and two-runs-as-author-plus-reviewer — and all were blocked or correctly deferred;
  every citation was verified against source. One Major finding was resolved:
  APA-INV-007 (scale does not dilute) had no §13 verification obligation while §14 ties
  acceptance to §13 — added §13.7 requiring per-artifact provenance and admission
  candidacy under bulk authoring. Minor fixes: §5 "Authoring Act" realigned to the
  canonical RFC-009 §5 term (production/modification of the strategy, its configuration
  bindings, or its supporting evidence); APA-INV-005 and §9 reworded so authoring
  *requires* a new ADR-002-029 Release Generation (issued by admission) rather than
  producing one; §8 notes the binding depends on the ADR-002-029 Source Revision
  Manifest schema (open field set) carrying the minimum record; ADR-DEV-006 marked
  planned; §10.2 re-cited to ADR-DEV-002 ARI-INV-003/§9; and §7 makes transparent that
  the minimum record extends RFC-009 §14 Q1 with the targeted DSL/enforcement/config
  versions. The review is EV-L0 only and confers no acceptance or live-readiness.
