# ADR-DEV-005 — Independent Review of AI-Authored Strategies and Rationale Representation

**ADR ID:** ADR-DEV-005
**Title:** Independent Review of AI-Authored Strategies and Rationale Representation
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-009 — Agent Guide, RFC-010 — Testing Strategy
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-009 §14 Q2, RFC-009 §14 Q4, and RFC-010 §14 Q4
**Date:** 2026-07-15
**Version:** 0.2 Review Draft
**Last Updated:** 2026-07-17
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

**Independence is a property of the reviewing authority, not of its substrate.** The
independent review (and independent verification) of an AI-authored strategy MAY be
performed by a human, by a distinct tool, or by either — what is required is
independence *from the author*, defined by three exclusions:

* it is not the authoring actor or Authoring Agent itself;
* it is not another instance or run of the same author (running the author twice is
  never independent);
* it does not share the author's determining inputs or model such that it would
  reproduce the author's blind spots (RFC-009 §10; philosophy §34; Vision §12.7).

The **author's rationale and self-asserted results are inputs to review — a claim to
be checked — never verified conformance**; they SHALL be recorded and presented as
distinct from a passed check, and a fluent rationale SHALL NOT be presentable as if it
were verification (RFC-009 §10; RFC-003 §12). A **tool** acting as the independent
reviewer is acceptable only if it is independent by the test above and is itself a
verified, non-self-certifying artifact. Independent review produces evidence toward
the RFC-001 / VER-002-001 acceptance and ADR-002-029 admission gates; it is not itself
acceptance or admission.

This ADR fixes what makes a review *independent* and how rationale is represented. It
grants no authority, accepts nothing, and admits no artifact.

---

## 2. Context

RFC-009 §10 states the no-self-review rule directly: "An Authoring Agent SHALL NOT be
the authority that accepts its own output, nor may two instances of the same agent
constitute the independent review that Vision §12.4/§12.7 and ADR-002-025/029 require.
Review independence is a property of the reviewing authority, not of running the author
twice." It also warns that "plausibility is not conformance" — an agent's rationale is
an input to review and "SHALL NOT substitute for independent verification" (RFC-003
§12). Vision §12.7 makes the Independent Reviewer responsible for challenging
assumptions, common-mode failures, and evidence quality; philosophy §34 holds that the
purpose of review is not to confirm the author.

Three open questions remain: RFC-009 §14 Q2 (must the reviewer be human, a tool, or
either?), RFC-009 §14 Q4 (how is rationale represented so it aids review without being
mistaken for verified conformance?), and RFC-010 §14 Q4 (what constitutes independent
verification of an AI-authored strategy's conformance claims?). This ADR resolves all
three. It does not define the acceptance gate (RFC-001, VER-002-001), admission
(ADR-002-029), or the testing discipline itself (RFC-010) — it defines the
independence standard those rely on.

---

## 3. Decision Drivers

1. **Self-review is not review** (RFC-009 §10; philosophy §34). An author confirming
   its own output discovers nothing.
2. **Independence is about correlation of failure, not job title.** A reviewer that
   shares the author's model, prompts, or blind spots exhibits common-mode failure
   even if nominally separate (Vision §12.7).
3. **Fluency is not correctness** (RFC-009 §10; philosophy §7). AI rationale is
   persuasive and can be wrong; it must be checkable, not trusted.
4. **A tool reviewer is itself software** and earns no trust it has not demonstrated
   (philosophy §33) — the same principle ADR-DEV-001 applies to the enforcement
   mechanism.
5. **Review is evidence, not the gate.** Acceptance and admission are separately owned
   (RFC-001; VER-002-001; ADR-002-029); review feeds them.

---

## 4. Scope and Non-Scope

**In scope:**

* the independence standard for the review/verification of an AI-authored strategy;
* the human/tool/either question and the test that decides it;
* how an author's rationale and self-asserted results are represented relative to
  verified conformance;
* the boundary between independent review and the acceptance/admission gates.

**Not in scope (owned elsewhere):**

* the `ACCEPTED` gate and verification-evidence specification — RFC-001, VER-002-001;
* software-artifact admission — ADR-002-029;
* restricted-live promotion — ADR-002-025;
* the testing discipline and its assumptions — RFC-010;
* Authoring Provenance and its binding — ADR-DEV-004;
* Artifact Identity and reproducibility — ADR-DEV-002;
* the bulk/family-authoring review-at-scale discipline — ADR-DEV-006 (planned;
  RFC-009 §14 Q5);
* who is organizationally assigned as reviewer, which is governance, not this ADR.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-000 §6, RFC-002 §3.1, RFC-008 §5, RFC-009 §5,
and RFC-010 §5, and SHALL NOT introduce synonyms. The following terms are scoped to
this decision and are non-authorizing.

* **Independent Reviewer** — the authority (human, a distinct tool, or either) that
  reviews or verifies an Authored Strategy's conformance claims and is independent of
  the author by the §6 exclusions (Vision §12.7).
* **Author's Rationale** — the explanation an author (including an Authoring Agent)
  provides for why an outcome follows from its inputs. It is an input to review, not
  evidence of conformance (RFC-009 §10; RFC-003 §12).
* **Independence** — the property that the reviewing authority is not the author, not
  another run of the same author, and does not share the author's model or its
  determining prompts/context (the observable proxy for common-mode failure; §7).

These terms describe a review standard. None grants authority, accepts, or admits.

---

## 6. Safety Invariants

* **AIR-INV-001 — Independence Is of the Authority, Not the Substrate.** The
  independent reviewer of an AI-authored strategy MAY be a human, a distinct tool, or
  either; the requirement is independence from the author, never a particular
  substrate (RFC-009 §10; Vision §12.7).
* **AIR-INV-002 — No Self-Review.** The authoring actor or Authoring Agent, another
  instance or run of the same author, or a reviewer that **shares the author's model
  or its determining prompts/context** does NOT constitute independent review. This
  observable sharing is the decision rule; it is the testable proxy for the
  common-mode failure that would reproduce the author's blind spots. A reviewer built
  on a distinct model with disjoint determining inputs is not excluded by this rule
  for the human or genuinely-decorrelated-tool case. **For the AI-on-AI review of an
  AI-*authored* artifact, the presumption is inverted (§7):** model distinctness is
  necessary but not sufficient, and the proponent SHALL affirmatively demonstrate
  decorrelation; absent that demonstration the review is treated as common-mode,
  fail-closed. The testable proxy is unchanged for the human / decorrelated-tool case,
  so this tightens the scope of AIR-EV-002 rather than adding a new evidence obligation
  (RFC-009 §10; philosophy §34, §37.4, §15; Vision §12.7).
* **AIR-INV-003 — Rationale Is a Claim to Be Checked.** An Author's Rationale and any
  self-asserted result are inputs to review, recorded and presented as distinct from
  verified conformance; a fluent rationale SHALL NOT be presentable as, or substituted
  for, a passed check (RFC-009 §10; RFC-003 §12; philosophy §7).
* **AIR-INV-004 — A Tool Reviewer Is Itself Verified, Recursively Independent.** A tool
  acting as the Independent Reviewer is acceptable only if it is independent
  (AIR-INV-002) and is itself a verified, non-self-certifying artifact; an unverified
  reviewer confers no independence. The tool reviewer's own verification SHALL itself
  satisfy the §7 independence standard — it is not performed by the author or by a party
  common-mode with the author — so the verify-the-verifier recursion is bound, not
  assumed (philosophy §33; cf. ADR-DEV-001 driver 6).
* **AIR-INV-005 — Review Is Not Acceptance or Admission.** Independent review produces
  evidence toward the RFC-001 / VER-002-001 acceptance and ADR-002-029 admission
  gates; it does not itself accept, admit, or authorize (RFC-001 §1; ADR-002-029 §1;
  philosophy §33).

---

## 7. The Independence Standard (RFC-009 §14 Q2; RFC-010 §14 Q4)

Whether a reviewer is human or a tool is **not** the deciding question; independence
is (AIR-INV-001). A reviewer is independent iff all three exclusions below hold
(AIR-INV-002), and the review records the reviewer's provenance so those exclusions
are checkable:

* **Not the author.** The authoring actor or Authoring Agent cannot review or accept
  its own output (RFC-009 §10).
* **Not the author re-run.** A second instance or run of the same Authoring Agent is
  the same author; it inherits the same training, prompt, and failure surface and is
  not independent (RFC-009 §10).
* **Not common-mode with the author.** The decision rule is observable sharing: a
  distinct reviewer that shares the author's model, or its determining prompts/context,
  does not satisfy independence — because it would reproduce the author's blind spots
  (Vision §12.7 common-mode failures). "Determining" means the reviewer's conclusion is
  driven by the same model or inputs, not merely that it consulted them; a reviewer
  built on a distinct model with disjoint determining inputs is independent under this
  rule. Where a correlated failure mode is suspected beyond this observable proxy, the
  burden is on the proponent to demonstrate independence, not to presume it (§12.2).
  **For the review of an AI-*authored* artifact by an AI reviewer, distinctness of model
  is necessary but not sufficient.** A shared-training-corpus blind spot is by
  construction *unsuspected*, so the "suspected" trigger above cannot fire in precisely
  the dangerous case; the presumption "distinct model + disjoint determining inputs ⇒
  independent" is therefore inverted for this case. The proponent SHALL affirmatively
  demonstrate decorrelation — disjoint determining training/data provenance to the extent
  establishable, or a recorded decorrelation argument — and where decorrelation cannot be
  affirmatively shown the AI-on-AI review is treated as common-mode (not independent),
  fail-closed (philosophy §37.4, §15). This inversion does not disturb the "determining"
  clarification above: a human reviewer, or a genuinely-decorrelated tool, is not
  over-blocked (AIR-INV-001 substrate-neutrality is preserved).
* **Reviewer provenance is recorded.** So the three exclusions are checkable, an
  independent review SHALL record the reviewer's identity, substrate (human, or the
  tool's model and version), and determining inputs, to be compared against the
  author's Authoring Provenance (ADR-DEV-004). The author's provenance alone
  establishes who authored, not that the reviewer is independent.

The same standard governs *independent verification* of a conformance claim under
RFC-010 (§14 Q4): running the author's own asserted test result is not verification;
an independent authority must exercise the claim (RFC-010 §11.10; RFC-009 §10).

A tool reviewer carries a demonstrated-verification bar (AIR-INV-004) that a human
reviewer does not, because a tool is software that earns no trust it has not
demonstrated (philosophy §33), whereas a human reviewer's competence and assignment
are governance (ADR-002-015; §4). This asymmetry is principled — it is not a
privileging of substrate over the independence standard, which is itself
substrate-neutral (AIR-INV-001).

---

## 8. Rationale Representation (RFC-009 §14 Q4)

An Author's Rationale SHALL be represented so it cannot be mistaken for verified
conformance (AIR-INV-003):

* it is recorded and presented explicitly **as a claim to be checked**, visually and
  structurally distinct from any independently verified result;
* it carries **no evidentiary weight** toward conformance until an Independent Reviewer
  checks it; a fluent or confident rationale is not a passed check (RFC-009 §10;
  RFC-003 §12);
* it aids the reviewer by exposing the author's stated assumptions and intended
  reasoning — which is precisely what philosophy §34 review exists to challenge — and
  is never a shortcut around that challenge;
* an Authoring Agent's rationale is treated with the same skepticism as any author's,
  and its fluency grants it no additional credence (RFC-009 §10);
* the independent check itself SHALL be evidence-producing and record what it
  exercised, so a genuine check is distinguishable from a mere endorsement; the
  testing discipline that makes a check auditable is owned by RFC-010 (§9, §11.10).

Representing rationale as a checkable claim is what lets it help review without
becoming a channel by which plausibility launders into presumed conformance.

---

## 9. Review, Acceptance, and Admission (boundary)

Independent review is evidence-producing, not gate-owning (AIR-INV-005):

* it produces objective evidence toward the `ACCEPTED` state, which requires the
  independent review and gate of RFC-001 §1 and VER-002-001 — review does not accept
  itself;
* it does not admit an artifact; admission is owned by ADR-002-029 on content-addressed
  identity;
* it does not promote toward live; promotion is owned by ADR-002-025;
* the same separation RFC-009 §11 and RFC-010 §11 enforce holds here: the identity that
  reviews is not thereby the identity that accepts, admits, or authorizes.

At the highest-risk promotion gate — the ADR-002-025 production authorization — at least
one independent review SHALL be performed by a **human-in-the-loop** independent reviewer.
This requirement is satisfiable by the second natural person of the two-person quorum
**or** by the external independent reviewer of the Governed Single-Operator Re-Arm Variant
(ADR-002-015 §17.1; evidence HAG-EV-016 "External Reviewer Independence"). This is a
*binding of* the existing independent-review requirement at that gate — not a new
authority or safety control — and it rides on the already-registered HAG-EV-016 /
RLP-EV-008 obligations; it introduces no new SAFE-xxx and no new AIR-EV. It is consistent
with the single-operator reality (DR-0001) and its already-existing external-reviewer
path; a fully-automated (AI-on-AI) review, however decorrelated, does not by itself
satisfy this gate.

---

## 10. Alternatives Considered

* **10.1 Require a human reviewer always.** Rejected: over-constrains; a verified,
  independent tool can review, and independence — not substrate — is the safety
  property (AIR-INV-001). (Human authority remains available and is required where the
  architecture separately mandates it — e.g. ADR-002-015.)
* **10.2 Allow a second instance of the author to review.** Rejected: same author, same
  blind spots; explicitly forbidden (RFC-009 §10; AIR-INV-002).
* **10.3 Accept the author's rationale/self-test as verification.** Rejected:
  plausibility is not conformance; the author's result is evidence, not verification
  (AIR-INV-003; RFC-009 §10; RFC-010 §11.10).
* **10.4 Treat any distinct tool as independent regardless of shared model/inputs.**
  Rejected: shared model/inputs are common-mode failure; distinctness of instance is
  not independence (AIR-INV-002; Vision §12.7).
* **10.5 Let independent review stand in for acceptance/admission.** Rejected: those
  gates are separately owned (AIR-INV-005; RFC-001; ADR-002-029).
* **10.6 Trust a tool reviewer without verifying it.** Rejected: a reviewer is software
  and earns no trust it has not demonstrated (AIR-INV-004; philosophy §33).
* **10.7 Presume independence from model-distinctness alone (for AI-on-AI review of an
  AI-authored artifact).** Rejected: an unsuspectable shared-corpus blind spot defeats the
  §7 suspicion trigger precisely when it is most dangerous; the burden is therefore
  inverted onto the proponent to affirmatively demonstrate decorrelation (§7; philosophy
  §37.4, §15). Deferring the concern to an Open Question absorbed by the acceptance gate
  was also rejected: it leaves the operative rule intact and, with every gate unexecuted
  and all evidence `NOT_IMPLEMENTED`, defers the fix indefinitely; the residual it would
  have flagged is instead discharged by this inversion (§12.2).

---

## 11. Consequences

**Positive.**

* Resolves human/tool/either without privileging a substrate, while closing the
  self-review and common-mode loopholes.
* Makes AI rationale usable for review without letting fluency become presumed
  conformance.
* Keeps review as evidence, preserving the acceptance/admission separation.

**Negative / costs.**

* Establishing that a tool reviewer is independent (no shared model/inputs/blind
  spots) and itself verified is non-trivial and must be demonstrated, not assumed.
* Rationale tooling must structurally separate "claim" from "verified," adding UI/record
  discipline.
* A verified independent tool reviewer is itself an artifact requiring its own
  verification lineage.

---

## 12. Failure Modes Introduced by This Decision

* **12.1 Disguised self-review.** A second run of the author is presented as
  independent; blocked by AIR-INV-002. Detection requires comparing the recorded
  reviewer provenance (§7) against the author's Authoring Provenance (ADR-DEV-004);
  author provenance alone is necessary but not sufficient to detect reviewer == author
  or common-mode.
* **12.2 Common-mode tool reviewer.** A distinct tool shares the author's model/inputs;
  blocked by AIR-INV-002's third exclusion. For the AI-on-AI review of an AI-authored
  artifact this is not merely flagged as a residual: it is discharged by the §7
  burden-inversion (the proponent SHALL affirmatively demonstrate decorrelation, else the
  review is common-mode, fail-closed), and the residual at the production-authorization
  gate is closed by the §9 human-in-the-loop requirement. Establishing decorrelation
  remains a real, deliberate cost.
* **12.3 Rationale laundering.** A fluent rationale is presented as a passed check;
  blocked by AIR-INV-003 representation discipline.
* **12.4 Review-as-acceptance.** A green independent review is treated as acceptance or
  admission; blocked by AIR-INV-005 and the RFC-001/ADR-002-029 gates.
* **12.5 Unverified tool reviewer.** A tool reviewer is trusted without its own
  verification; blocked by AIR-INV-004.

---

## 13. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010):

* **13.1** An author (or a second run of the same author) reviewing/accepting its own
  output is rejected as non-independent (AIR-INV-002).
* **13.2** A distinct tool sharing the author's model/determining inputs is rejected as
  common-mode, not independent (AIR-INV-002).
* **13.3** An author's rationale/self-asserted result carries no conformance weight
  until independently checked and is presented as distinct from a verified result
  (AIR-INV-003).
* **13.4** A tool reviewer that is not itself verified confers no independence
  (AIR-INV-004).
* **13.5** A passing independent review does not, by itself, accept or admit an
  artifact (AIR-INV-005).
* **13.6** A human reviewer and a verified independent tool reviewer are each accepted
  when they satisfy the independence exclusions (AIR-INV-001).

---

## 14. Acceptance Criteria

ADR-DEV-005 is acceptable when:

* independence is defined by the three exclusions and applies to human or verified-tool
  reviewers alike (AIR-INV-001, -002);
* the author's rationale is represented as a checkable claim distinct from verified
  conformance (AIR-INV-003);
* a tool reviewer must be independent and itself verified (AIR-INV-004);
* review remains evidence toward, never a substitute for, the acceptance/admission
  gates (AIR-INV-005);
* independence for the AI-on-AI review of an AI-authored artifact requires
  affirmatively-demonstrated decorrelation, not model-distinctness alone (§7;
  AIR-INV-002);
* the ADR-002-025 production-authorization gate requires at least one human-in-the-loop
  independent review (§9; HAG-EV-016);
* independent adversarial review (EV-L0) confirms every §13 obligation is discharged
  and every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 15. Traceability

| Requirement | Discharge in ADR-DEV-005 |
|---|---|
| RFC-009 §14 Q2 (human/tool/either) | independence is of the authority, not the substrate; three exclusions (§7; AIR-INV-001, -002) |
| RFC-009 §14 Q4 (rationale representation) | rationale is a claim to be checked, distinct from verified conformance (§8; AIR-INV-003) |
| RFC-010 §14 Q4 (independent verification of AI conformance) | same independence standard; author's result is not verification (§7; AIR-INV-002; RFC-010 §11.10) |
| RFC-009 §10 (no self-review loop; plausibility not conformance) | AIR-INV-002, -003 |
| Vision §12.7 (Independent Reviewer; common-mode) | common-mode exclusion (§7; AIR-INV-002) |
| philosophy §34 (independent review creates value) | review challenges, not confirms, the author (§§3, 8) |
| philosophy §7 (prediction has limited authority) | fluency is not conformance (AIR-INV-003) |
| philosophy §33 (demonstration required) | tool reviewer itself verified (AIR-INV-004) |
| RFC-003 §12 (quality vs outcome) | rationale is not verified conformance (§8; AIR-INV-003) |
| RFC-001 §1; VER-002-001 (acceptance gate) | review is evidence, not acceptance (§9; AIR-INV-005) |
| ADR-002-029 §1; ADR-002-025 (admission; promotion) | review is not admission/promotion (§9; AIR-INV-005) |
| ADR-DEV-004 (provenance) | provenance records author identity/model to detect disguised self-review (§12.1) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes the
independence standard and rationale representation and relies on RFC-001/VER-002-001,
ADR-002-029, and ADR-002-025 for the gates it feeds.

---

## 16. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-005, resolving RFC-009 §14 Q2 (human/tool/either), RFC-009 §14 Q4
  (rationale representation), and RFC-010 §14 Q4 (independent verification of
  AI-authored conformance).
* Set the decision: independence is a property of the reviewing authority (human, a
  distinct tool, or either), defined by three exclusions — not the author, not the
  author re-run, not common-mode with the author; the author's rationale is a claim to
  be checked, never verified conformance; a tool reviewer must itself be verified; and
  review is evidence, not the acceptance/admission gate.
* Defined five invariants AIR-INV-001…005 and traced them to RFC-009 §10, Vision §12.7,
  philosophy §7/§33/§34, RFC-003 §12, RFC-010 §11.10, RFC-001 §1/VER-002-001, and
  ADR-002-025/029, ADR-DEV-004.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no
  acceptance or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding. Fifteen sequences were attempted — author re-run as "independent,"
  a common-mode tool reviewer, rationale laundering, review-as-acceptance, an
  unverified tool reviewer, an over-constraining human-always requirement,
  author-self-certified test results, routing acceptance/promotion into "review," a
  tool's own self-check, an A/B tool chain sharing a foundation model, a human
  rubber-stamp, collapsing evidence-toward-acceptance into acceptance, a
  common-mode-verified tool, unrecorded reviewer identity, and over-blocking a human
  who merely consulted the same model — and the eight targeted classes were all
  blocked. Three Major findings were resolved: (M1) the common-mode exclusion's
  standard (§§5–7) was stricter and vaguer than its test (§13.2) — the observable proxy
  (shares the author's model or its determining prompts/context) is now the decision
  rule in AIR-INV-002 and §7, with "reproduces the author's blind spots" reframed as
  rationale and burden-of-demonstration, and distinct-model/disjoint-input reviewers
  explicitly admitted; (M2) the exclusions were unfalsifiable because only the author's
  provenance was recorded — §7 now requires the review to record the reviewer's
  identity/substrate/determining inputs, and §12.1 is softened accordingly; (M3) the
  verify-the-verifier recursion was only a stated cost — AIR-INV-004 now requires the
  tool reviewer's own verification to satisfy the §7 independence standard. Four Minor
  fixes were applied: ADR-DEV-006 marked planned; the tool-vs-human verification
  asymmetry explained as principled (§7); the independent check required to be
  evidence-producing and auditable (§8; RFC-010 §9/§11.10); and "determining" clarified
  to prevent over-blocking a reviewer that merely consulted a model. The review is
  EV-L0 only and confers no acceptance or live-readiness.

### v0.2 — Wave 7 (CORPUS-REVIEW-0001 M-16)

* Inverted the AI-on-AI review presumption for the review of an AI-*authored* artifact:
  model distinctness is necessary but not sufficient, because a shared-training-corpus
  blind spot is unsuspectable and defeats the §7 "suspected" trigger precisely when it is
  most dangerous; the proponent SHALL now affirmatively demonstrate decorrelation, and
  absent that demonstration the review is treated as common-mode and fails closed
  (§7; AIR-INV-002; philosophy §37.4, §15). This adopts presumption-inversion (option A)
  over Open-Question-promotion (option B, §10.7), which would have left the operative rule
  intact and deferred the fix indefinitely.
* Normativized (SHALL) a human-in-the-loop independent reviewer at the highest-risk
  ADR-002-025 production-authorization gate (§9; §14), satisfiable by the two-person
  quorum's second natural person or the ADR-002-015 §17.1 external independent reviewer,
  riding on the existing HAG-EV-016 / RLP-EV-008 obligations.
* Reframed §12.2 from a flagged residual to one discharged by the §7 inversion and the §9
  gate; added §10.7 and two §14 acceptance criteria.
* **No new AIR-INV and no new AIR-EV were introduced** (deliberate count discipline): the
  change is an amendment to the existing AIR-INV-002 plus a §9 binding on already-registered
  evidence (AIR-EV-002/-005, HAG-EV-016, RLP-EV-008), so the development-track evidence
  count is unchanged by this item. No SAFE-xxx, no numeric bound, no broker proper noun.
  The Wave-7 changes are EV-L0 review items with reviewer provenance to be recorded per
  ADR-DEV-005 §7 / VER-002-001 §5 (M-18); this patch confers no acceptance or live-readiness.
