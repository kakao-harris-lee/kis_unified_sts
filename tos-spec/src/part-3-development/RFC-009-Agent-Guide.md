# RFC-009 — Agent Guide

**Document ID:** RFC-009
**Title:** Agent Guide
**Version:** 0.1 Review Draft
**Status:** Review Draft — Development
**Classification:** Implementation-Layer Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Safety Authority:** Constrained by RFC-001 — Safety Case and RFC-002 — Architecture
**Decision Authority:** Constrained by RFC-003 — Decision Framework
**Authoring Surface:** Realized through RFC-008 — Strategy DSL
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-15
**Last Updated:** 2026-07-15

---

## 1. Abstract

This document defines the **Agent Guide**: the discipline that governs any actor —
a human developer, a tool, or an AI coding assistant — that *authors* a Decision
Policy in the RFC-008 Strategy DSL. Per RFC-000 §9 Implementation defines HOW
SOFTWARE IS BUILT; RFC-009 occupies that layer as the companion to RFC-008. Where
RFC-008 defines the authoring *surface*, RFC-009 defines the authoring *actor* and
what conforming authorship requires of it.

RFC-009 is subordinate to RFC-000, RFC-001, RFC-002, every accepted ADR-002-xxx,
and RFC-003, and it works entirely within the RFC-008 surface. Its governing
thesis extends RFC-008's containment one level outward: **the author is untrusted
too**. RFC-008 makes the runtime proposer unable to name a prohibited effect;
RFC-009 ensures that the *process of producing* that proposer cannot smuggle
authority, cannot self-accept, and cannot become the reason a strategy is trusted.
Authorship is neither authorization nor acceptance: an authored strategy is a
candidate proposer whose safety rests on the durable model, never on the identity,
sophistication, or confidence of whatever wrote it.

RFC-009 defines an authoring discipline. It selects no strategy, grants no
authority, and its acceptance does not authorize live operation.

---

## 2. Normative Authority

RFC-009's authority is bounded as follows:

* **RFC-000 — Trading Constitution** governs this document. RFC-009 SHALL NOT
  redefine constitutional intent (RFC-000 §9) and SHALL use RFC-000 §6
  vocabulary verbatim.
* **RFC-001 — Safety Case** constrains this document. No authoring practice,
  automation, or agent convenience defined here may weaken, bypass, or reinterpret
  any SAFE-xxx requirement.
* **RFC-002 — Architecture** and the accepted **ADR-002-xxx** series define the
  components, boundaries, and admission controls an authored artifact is subject
  to. RFC-009 honors the strategy boundary (RFC-002 §7.3), the human-operations
  boundary (RFC-002 §7.5), and software-artifact admission (ADR-002-029); it
  defines none of them.
* **RFC-003 — Decision Framework** is the discipline an authored strategy must
  satisfy at runtime; RFC-009 governs the authoring that produces a conforming
  Decision Policy and inherits every RFC-003 boundary.
* **RFC-008 — Strategy DSL** is the surface RFC-009's actors write in. RFC-009
  adds no expressive power to that surface and relaxes none of its containment;
  an authoring practice that would require a DSL escape is non-conforming.
* Where RFC-009 and any higher document appear to conflict, the higher document
  governs and the conflict SHALL be raised through governance, not resolved by a
  local authoring convention.

RFC-009 defines an authoring discipline. It creates no capacity, authority,
configuration, transmission permission, or protective status, and its acceptance
does not authorize live operation.

---

## 3. Scope and Non-Scope

This document governs:

* the authoring actor: what a conforming Strategy Author (human, tool, or AI
  agent) SHALL and SHALL NOT do when producing a Decision Policy;
* the untrusted-author principle: why authorship confers no trust and no
  authority;
* the separation of authoring from approval, acceptance, promotion, and operation;
* the provenance, versioning, and evidence an authored strategy SHALL carry so it
  can be reviewed and admitted;
* the specific hazards of automated and AI-assisted authorship and the discipline
  that contains them;
* the boundary between the authoring actor and every safety-enforcement,
  decision-authority, review, and admission owner.

This document does not decide:

* the authoring surface itself — RFC-008 owns that; RFC-009 governs working within
  it;
* the decision process discipline — RFC-003 owns that;
* whether a Proposal is approved at runtime — the Independent Approval Service owns
  that (RFC-002 §10.3, ADR-002-023);
* whether an authored artifact is admitted to run — software-artifact admission
  owns that (ADR-002-029);
* whether a strategy is promoted toward live — restricted-live governance owns
  that (ADR-002-025);
* how an authored strategy is tested (RFC-010) or operated (RFC-011);
* any specific signal, indicator, model, or strategy an agent might author;
* numeric thresholds, limits, symbols, or schedules, which are approved
  configuration and the Verification Profile.

An authoring practice that reaches beyond this scope — or that treats authorship
as a source of authority — is non-conforming regardless of the author's capability.

---

## 4. Relationship to Vision and Philosophy

RFC-009 operationalizes principles already established upstream; it inherits, and
does not restate, them.

* **Strategies are replaceable; safety is durable** (philosophy §13, Vision §7.5).
  If the author were trusted, the safety model would depend on the author;
  replaceability requires that neither a strategy nor its author be load-bearing.
* **Authority must be explicit** (philosophy §14). An agent SHALL NOT infer
  authority from its role, its access, a prior successful strategy, or its own
  confidence; producing a well-formed strategy is not producing an authorized one.
* **Prediction has limited authority** (philosophy §7). An AI author's assessment
  that a strategy is good, safe, or profitable is uncertain evidence for human and
  independent review, never permission.
* **Backtests are evidence, not proof** (philosophy §28, Vision §11.9). An author
  SHALL NOT present simulated or historical performance as demonstrated live edge
  or as a substitute for the restricted-live verification governed by ADR-002-025.
* **Human authority remains available** (Vision §6.9, §12). Automation of
  authorship improves consistency; it does not remove the responsible human roles
  (Vision §12.3 Strategy Developer, §12.4 Safety/Risk Reviewer, §12.7 Independent
  Reviewer) or their accountability.

Where an authoring practice would contradict a Vision or Philosophy principle, that
practice is non-conforming.

---

## 5. Definitions

RFC-009 reuses canonical terms from RFC-000 §6, RFC-001 §5, RFC-002 §3.1, the
ADR series, RFC-003 §5 (**Proposal**, **Decision Policy**), and RFC-008 §5
(**Strategy DSL**, **Strategy Author**, **Authored Strategy**, **Proposal
Builder**). It SHALL NOT introduce synonyms for any of them. The following terms
are scoped to the authoring discipline and are non-authorizing.

* **Authoring Agent** — a Strategy Author (RFC-008 §5) that is automated or
  AI-assisted rather than a human writing directly. An Authoring Agent is an
  untrusted producer of candidate artifacts; it holds no runtime authority and no
  review or admission authority.
* **Authoring Act** — the production or modification of an Authored Strategy, its
  configuration bindings, or its supporting evidence. An Authoring Act produces a
  candidate for review and admission; it is not a decision, an approval, or a
  promotion.
* **Authoring Provenance** — the recorded account of who or what performed an
  Authoring Act, from which inputs, at which versions, sufficient for independent
  review and for the software-artifact admission of ADR-002-029.

These terms describe an authoring discipline. None grants authority, produces a
Proposal at runtime, or admits an artifact to run.

---

## 6. Agent Guide Principles

A conforming authoring actor SHALL satisfy the following. They are obligations on
the authoring process, not new runtime enforcement; the enforcement points remain
owned by RFC-002, the ADR series, RFC-003, and RFC-008.

1. **The author is untrusted.** Nothing an author is — human seniority, tool
   pedigree, or AI capability — makes its output trusted. An Authored Strategy is
   a candidate proposer whose safety rests on the durable model (philosophy §13).
2. **Authorship is not authority.** Producing a strategy confers no approval,
   capacity, promotion, live authorization, or protective status; those remain
   separately owned (RFC-002 §9.1).
3. **Author within the surface, never around it.** A conforming strategy is
   expressed entirely within the RFC-008 DSL. An authoring practice that needs a
   foreign-function interface, embedded host, or dynamic-loading escape is
   non-conforming (RFC-008 §11 item 17).
4. **Provenance is mandatory.** Every Authoring Act SHALL record its Authoring
   Provenance — actor, inputs, and versions — sufficient for independent review
   and ADR-002-029 admission.
5. **Uncertainty restricts the author too.** When an author cannot establish that a
   strategy is conforming, the conforming outcome is to withhold it or narrow it,
   never to ship it on optimism (philosophy §8; RFC-003 §6).
6. **No self-acceptance.** An author — especially an Authoring Agent — SHALL NOT
   review, approve, admit, or promote its own output; those are separately owned
   roles (Vision §12.4/§12.7; ADR-002-025/029).
7. **Evidence, not assertion.** Claims about a strategy (edge, safety,
   conformance) SHALL be backed by reviewable evidence, never asserted by the
   author's confidence (philosophy §7, §28).

---

## 7. The Untrusted Author

RFC-008 establishes that a strategy is an untrusted proposer at runtime. RFC-009
establishes the same about the layer that *creates* the strategy: the author is
untrusted at authoring time. The two are complementary — a trusted author would
reintroduce, at build time, exactly the coupling RFC-008 removes at run time.

* **Capability is not trust.** Sophisticated technology does not guarantee
  correctness (philosophy §37.2); a highly capable human or AI author can produce
  a subtly non-conforming strategy as easily as a conforming one. Sophistication
  raises the stakes of review, it does not lower the need for it (Vision §11.10).
* **Output is a candidate, always.** The product of any Authoring Act is a
  candidate Authored Strategy for review and admission. It is not runnable by
  virtue of having been authored; it becomes runnable only through the separately
  owned admission of ADR-002-029 and, for live, the governance of ADR-002-025.
* **Failure of the author is contained.** A defective, biased, adversarial, or
  malfunctioning author SHALL NOT be able to widen any authority, because its
  output is confined to the RFC-008 surface, its runtime effect is confined to a
  Proposal, and its admission is confined to independent review. An author's
  failure degrades to "a candidate that review should reject," never to an
  unsafe live action.
* **The author cannot certify itself.** No author asserts that its own output is
  conforming, safe, or profitable in a way that carries weight; such assertions
  are evidence for review, subordinate to independent evaluation. A safety claim
  is valid only when its requirement has objective evidence, has passed
  independent review, and has reached `ACCEPTED` (RFC-001 §1), and a defect in
  strategy logic SHALL NOT disable the independent authority required to contain
  it (RFC-001 SC-050; RFC-002 §9.1).

The durability of the safety model is precisely its independence from who, or what,
authored a strategy.

---

## 8. Authoring Is Not Authorizing, Accepting, or Promoting

The single most important boundary in this document is the separation of
authorship from every downstream gate. An Authoring Act ends at producing a
candidate; it touches none of the following, and an authoring practice that
conflates them is non-conforming.

* **Authoring vs. runtime approval.** Whether a strategy's Proposal is approved is
  decided per-Proposal, at runtime, by the Independent Approval Service
  (RFC-002 §10.3, ADR-002-023). Authoring a strategy grants its future Proposals
  nothing.
* **Authoring vs. capacity.** Authoring commits no risk capacity; only the RCL
  mutates capacity (ADR-002-002), driven by the Aggregate Risk Authority
  (ADR-002-021), independent of authorship.
* **Authoring vs. admission.** Whether an authored artifact may run at all is
  decided by software-artifact admission against an immutable, content-addressed,
  generation-fenced release identity (ADR-002-029). A branch name or a passing
  build is not artifact identity or admission proof (ADR-002-029 §1), and a green
  test run, a passing scan, CI success, or an author's self-approval cannot create
  admission eligibility (ADR-002-029 §§15, 25.5, SCI-AC-006).
* **Authoring vs. live promotion.** Whether a conforming, admitted strategy is
  promoted toward live is decided by restricted-live governance on pre-registered
  evidence (ADR-002-025); authorship extrapolates to no live scope.
* **Authoring vs. operation.** How an admitted strategy is operated, monitored,
  and re-armed is owned by operators and RFC-011; the author has no operational
  authority (Vision §6.9, §12.6).

Authorship is the beginning of a governed lifecycle, not a shortcut through it.

---

## 9. Authoring Discipline and Provenance

RFC-009 supplies the conforming inputs that review, admission, and replay require
from the authoring process. It does not replace those owners; it feeds them.

* **Author within the DSL.** A conforming Decision Policy is expressed only through
  the RFC-008 surface and its Proposal Builder (RFC-008 §§7, 8). Any capability an
  author believes it needs beyond that surface is raised through governance, not
  satisfied by an escape (RFC-008 §11 item 17).
* **Externally-sourced material is captured, not called.** Where authoring uses an
  external or AI-generated artifact that a strategy will consume at runtime (for
  example a model-derived parameter or an LLM interpretation), that material SHALL
  be produced at authoring time and delivered into the runtime as Critical Input
  through the Decision Context Capsule — never fetched live during DSL evaluation
  (RFC-008 §9, §10; ADR-002-018). The authoring pipeline records its seed and
  response as evidence (RFC-003 §10).
* **Everything is versioned.** An Authored Strategy, its DSL version, and its
  configuration bindings SHALL be versioned; a change is a recorded, versioned
  substitution, never an in-place unversioned mutation (RFC-008 §6, RFC-003 §13).
* **Provenance for admission.** Each Authoring Act SHALL record its Authoring
  Provenance — actor identity, inputs, tool and model versions, and source
  revision — so it can bind into the Source Revision Manifest and admission
  evidence of ADR-002-029. Generated source is source: it is reviewed and admitted
  under ADR-002-029 like any other, and an author SHALL NOT treat "the tool wrote
  it" as exempting it from review (ADR-002-029 §1).
* **Reproducible authorship where feasible.** An authoring pipeline SHOULD be
  reproducible from its recorded inputs and versions, so that review examines the
  same artifact that will run and replay integrity (ADR-002-016) is supported.

Provenance and versioning are how an untrusted author's output becomes reviewable —
the mechanism that lets the system trust the *review*, not the author.

---

## 10. Automated and AI-Assisted Authorship

Automated and AI-assisted authorship is explicitly anticipated and explicitly
contained. It is neither privileged nor prohibited; it is subject to the same
untrusted-author discipline as any other author, with additional attention to its
characteristic hazards.

* **Scale is a hazard, not a warrant.** An Authoring Agent can produce many
  strategies quickly; volume SHALL NOT reduce the per-artifact review and admission
  each requires (ADR-002-029). Throughput of authorship is not evidence of quality.
* **Plausibility is not conformance.** AI-generated code and rationale can be
  fluent and wrong. An Authoring Agent's rationale is an input to review, and a
  fluent justification SHALL NOT substitute for independent verification of
  conformance (philosophy §7; RFC-003 §12 quality-vs-outcome).
* **No self-review loop.** An Authoring Agent SHALL NOT be the authority that
  accepts its own output, nor may two instances of the same agent constitute the
  independent review that Vision §12.4/§12.7 and ADR-002-025/029 require. Review
  independence is a property of the reviewing authority, not of running the author
  twice.
* **Prompt and input integrity.** The inputs that steer an Authoring Agent —
  prompts, retrieved context, model version — are part of Authoring Provenance and
  SHALL be recorded; an authored artifact whose provenance cannot be established is
  not admissible (ADR-002-029 §1).
* **Containment is unchanged.** Whatever an Authoring Agent produces is still
  confined to the RFC-008 surface, still emits only a Proposal, and still faces
  independent approval, capacity, admission, and promotion. The agent inherits
  every containment property of RFC-008; it is granted no exception.

An Authoring Agent is a fast, tireless, untrusted producer of candidates. The
system's response to that is more disciplined review and admission, never more
trust.

---

## 11. The Author↔Safety Boundary

This section is the load-bearing safety content of RFC-009. It restates, at the
authoring-actor layer, the separation that RFC-002 §9.1, the ADR series, RFC-003
§11, and RFC-008 §11 enforce. Every item is a hard boundary.

An authoring actor — human, tool, or Authoring Agent — SHALL NOT:

1. treat authorship of a strategy as approval of its Proposals; approval is
   per-Proposal, runtime, and independent (RFC-002 §9.1, §10.3; ADR-002-023);
2. commit, reserve, mutate, or release risk capacity, or presume future capacity
   for an authored strategy (ADR-002-002; RFC-002 §9.1);
3. grant, arm, or presume live authorization or transmission for an authored
   strategy (RFC-002 §7.6; ADR-002-007, ADR-002-025);
4. classify an authored action as protective, or encode any keyword or label that
   claims protective status (RFC-002 §9.1 "Strategy SHALL NOT self-label an action
   as protective"; ADR-002-001 §6; RFC-008 §11 item 6);
5. author around the RFC-008 surface via a foreign-function interface, embedded
   host, dynamic loading, or any escape that reintroduces a prohibited effect
   (RFC-008 §11 item 17);
6. cause a runtime strategy to read ambient state — clock, randomness, network,
   filesystem — by embedding a live call in authored logic; externally-sourced
   material is captured into the Capsule at authoring time (RFC-008 §9, §11 item
   12; ADR-002-018);
7. weaken, relax, or reinterpret any safety limit or safety configuration through
   an authored artifact or its configuration bindings (RFC-002 §7.4; RFC-001
   §7.5);
8. present backtested or simulated performance as demonstrated live edge, or as a
   substitute for restricted-live verification (philosophy §28; ADR-002-025;
   RFC-003 §12);
9. review, accept, admit, or promote its own output, or stand in for the
   independent review and admission required by Vision §12.4/§12.7 and
   ADR-002-025/029 (RFC-001 §7.5 forbids an actor declaring its own safety
   evidence accepted);
10. treat a branch, tag, `latest`, or passing build as artifact identity
    (ADR-002-029 §1), or a green test run, passing scan, CI success, or its own
    self-approval as admission eligibility (ADR-002-029 §§15, 25.5, SCI-AC-006);
11. ship an authored artifact whose Authoring Provenance — actor, inputs, versions,
    source revision — cannot be established for review and admission (ADR-002-029
    §1; §9);
12. treat the author's role, access, capability, or confidence as authority of any
    kind (philosophy §14; RFC-002 §7.3, §7.5).

The single generalizing rule (RFC-002 §9.1; RFC-008 §11): the identity that
proposes an action SHALL NOT also approve, commit, or transmit it — and RFC-009
adds its corollary: the identity that *authors* a proposer is not thereby trusted,
does not approve or admit its own output, and gains no authority from having
written it.

---

## 12. Relationship to RFC-008, RFC-010, and RFC-011

RFC-009 is the authoring-actor companion within Part 3. The pointers below are
non-normative scope markers; RFC-009 SHALL NOT define their content.

* **RFC-008 — Strategy DSL.** The surface RFC-009's actors author within. RFC-009
  adds no expressive power and relaxes no containment; it governs the actor, not
  the language.
* **RFC-010 — Testing Strategy.** How an Authored Strategy — and the DSL and
  authoring pipeline themselves — are tested, including that determinism,
  isolation, and containment hold and that an author's conformance claims are
  independently verifiable. RFC-009 requires such verification to exist; RFC-010
  defines it.
* **RFC-011 — Operational Guidelines.** How an admitted strategy is operated,
  monitored, and re-armed, and the operator authority the author does not hold.
  RFC-009 ends the lifecycle at a reviewed, admitted candidate; RFC-011 governs
  what happens after.

Until RFC-010 and RFC-011 are authored and accepted, their concerns remain open
and SHALL NOT be resolved by authoring-actor convention.

---

## 13. Requirements Traceability

RFC-009 discharges implementation-layer obligations that RFC-000, RFC-002,
RFC-003, and RFC-008 assign to the authoring actor. This table is an initial
allocation and SHALL be refined as RFC-010 and RFC-011 are accepted.

| Requirement | Discharge in RFC-009 |
|---|---|
| RFC-000 §9 layering (Implementation defines HOW SOFTWARE IS BUILT) | RFC-009 confined to the authoring actor for a Decision Policy; defines no WHY/WHAT/HOW-DECISIONS content (§§1, 2) |
| RFC-000 CONST-005 (Independent Approval Authority) + RFC-001 §7.5 (Separation of Authority) | authorship is not approval; the separation-of-authority pattern is generalized so an actor SHALL NOT self-review/self-accept its output (§§8, 10, 11.1, 11.9) |
| RFC-002 §7.3 Strategy Boundary | the author's product is an untrusted candidate proposer, contained to the RFC-008 surface (§§7, 10, 11) |
| RFC-002 §7.5 Human Operations Boundary | authoring automation does not remove or bypass responsible human roles (§§4, 10) |
| RFC-002 §9.1 authority ownership | authorship gains none of approve/commit/transmit/arm/classify (§§8, 11) |
| RFC-003 §11, §13 | authored artifacts inherit the decision↔safety boundary and versioned replaceability (§§9, 11) |
| RFC-008 §11 (containment, items 6/12/17) | authoring within the surface; no protective self-label, no ambient call, no escape (§§9, 11.4–11.6) |
| ADR-002-025 (restricted-live promotion) | authorship extrapolates to no live scope; promotion is separately governed (§§8, 11.3) |
| ADR-002-029 (software-artifact admission) | generated source is reviewed/admitted; provenance mandatory; build/test/sign-off is not admission (§§8, 9, 10, 11.10, 11.11) |
| ADR-002-016 (evidence/replay integrity) | reproducible authorship supplies conforming inputs to replay (§9) |
| ADR-002-018 (Critical Input) | externally-sourced material captured into the Capsule, not called live (§§9, 11.6) |
| philosophy §§7, 8, 13, 14, 28; Vision §§6.9, 7.5, 9.2, 11.9, 11.10, 12 | untrusted-author, explicit-authority, evidence-not-assertion operationalized (§§4, 7, 10) |

RFC-009 introduces no SAFE-xxx requirement and no numeric bound. It relies
entirely on the enforcement, review, and admission points already defined upstream.

---

## 14. Open Questions

These questions are open while RFC-009 is a Review Draft and while RFC-010 and
RFC-011 are unwritten. They SHALL NOT be resolved by informal authoring-actor
convention.

1. What minimum Authoring Provenance record (actor, prompt/input set, tool and
   model versions, source revision) is required to make an AI-authored strategy
   admissible under ADR-002-029, and where is that record bound? *(Resolved by
   ADR-DEV-004: minimum record defined; bound to the Artifact Identity and the
   ADR-002-029 Source Revision Manifest/admission evidence.)*
2. What constitutes *independent* review of an AI-authored strategy — must the
   reviewing authority be human, a distinct tool, or either — given Vision
   §12.4/§12.7 and the no-self-review rule (§10)? *(Resolved by ADR-DEV-005:
   independence is of the authority, not the substrate — human or a verified tool or
   either — defined by three exclusions.)*
3. To what extent must an authoring pipeline be reproducible (bit-for-bit vs.
   reproducible-from-recorded-inputs) for the artifact reviewed to be provably the
   artifact that runs (§9; ADR-002-016)? *(Resolved by ADR-DEV-002: identity is
   exact/content-addressed; behavior is reproducible-from-recorded-inputs.)*
4. How is an author's rationale represented so it aids review without being
   mistaken for verified conformance (§10; RFC-003 §12)? *(Resolved by ADR-DEV-005:
   rationale is recorded and presented as a claim to be checked, distinct from
   verified conformance, with no evidentiary weight until independently checked.)*
5. How does the authoring discipline handle an Authoring Agent that revises a
   large family of strategies at once, so that per-artifact review and admission
   are not diluted by scale (§10)?
6. Where an authored strategy embeds an externally-sourced value, what staleness
   and re-authoring discipline governs that value between authoring time and
   runtime capture (§9; RFC-008 §9)? *(Resolved by ADR-DEV-003: an explicit Validity
   Window beyond which the value is STALE and restrictive, and re-authoring — not
   reuse — of a stale value, with correction invalidating dependents.)*

Unresolved questions reduce, and do not expand, the conforming authoring surface.

---

## 15. Review History

### v0.1 — Initial Draft

* Established RFC-009 as the Implementation-layer Agent Guide: the authoring-actor
  companion to RFC-008, governing any human, tool, or AI agent that authors a
  Decision Policy in the Strategy DSL.
* Set the governing thesis as **the author is untrusted too** — extending RFC-008's
  runtime containment to authoring time — and separated authorship from runtime
  approval, capacity, admission, live promotion, and operation (§§7, 8).
* Defined the authoring discipline and provenance obligations that feed
  ADR-002-029 admission and ADR-002-016 replay (§9), and the specific hazards of
  automated/AI-assisted authorship — scale, plausibility, self-review, prompt/input
  integrity — with unchanged containment (§10).
* Restated the boundary as twelve prohibitions on the authoring actor (§11),
  each traced to RFC-002 §9.1/§7.3/§7.5, RFC-008 §11, RFC-003 §11, and
  ADR-002-025/029.
* Marked scope relationships to RFC-008 and forward to RFC-010/011 without
  pre-empting them (§12).
* Introduced no SAFE-xxx requirement, numeric bound, or authority.
* Independent adversarial EV-L0 document review returned PASS-WITH-FIXES with no
  Critical finding. Ten author-time leak sequences were attempted —
  self-review/self-accept, authorship-as-approval, capacity/live-authorization
  presumption, using scale to dilute per-artifact review, presenting a fluent AI
  rationale as verified conformance, treating a passing build/test/branch/sign-off
  as admission, shipping without establishable provenance, embedding a live call
  in authored logic, and using two instances of the same agent as "independent"
  review — and all were found blocked by §§7, 8, 10, 11, each tied to a real
  separately-owned enforcer (Independent Approval Service, RCL, Live Authorization
  Service, Protective Action Controller, ADR-002-029 admission, ADR-002-025
  promotion). The RFC-008 (surface) / RFC-009 (actor) split was confirmed clean and
  non-overlapping, and no SAFE-xxx, numeric bound, synonym, or authority grant was
  introduced. Three Major findings, all citation-precision rather than substance,
  were resolved: (M1) the CONST-005 traceability row was relabeled as a
  generalization of the separation-of-authority pattern and paired with RFC-001
  §7.5, whose "declare its own safety evidence accepted" prohibition is the tight
  fit for the no-self-review rule (§§11.9, 13); (M2) "capability is not trust" was
  re-anchored from Vision §9.2/§11.10 to philosophy §37.2 (Technical Confidence —
  "Sophisticated technology does not guarantee correctness"), an exact match (§7);
  (M3) the "green test run / sign-off is not admission" claims were re-cited from
  ADR-002-029 §1 (which covers branch/build identity) to §§15, 25.5, and SCI-AC-006
  (which cover tests, CI success, and self-approval) (§§8, 11.10). The review is
  EV-L0 only and confers no acceptance or live-readiness.
* Governance note (inherited citation imprecision — RESOLVED). §2's citation for
  "SHALL NOT redefine constitutional intent" now points to RFC-000 §9, where the
  literal phrase appears (§12 states the cognate "reinterpret higher-level intent").
  The identical imprecision across RFC-003 through RFC-011 was corrected
  consistently across the series in a single companion change.
