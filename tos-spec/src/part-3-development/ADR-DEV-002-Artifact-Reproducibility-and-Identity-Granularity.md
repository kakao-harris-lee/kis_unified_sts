# ADR-DEV-002 — Artifact Reproducibility and Identity Granularity

**ADR ID:** ADR-DEV-002
**Title:** Artifact Reproducibility and Identity Granularity
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-008 — Strategy DSL, RFC-009 — Agent Guide, RFC-010 — Testing Strategy (cross-cutting)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-009 §14 Q3, RFC-010 §14 Q2, and the reproducibility clause of RFC-008 §14 Q3
**Date:** 2026-07-15
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-15
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

The "bit-for-bit vs. reproducible-from-recorded-inputs" question is resolved by
**separating two distinct granularities**:

* **Artifact identity SHALL be exact and content-addressed** — the Authored Strategy
  (together with its DSL version, Enforcement Mechanism version, and configuration)
  is identified by exact content digest, so that the artifact tested, reviewed,
  admitted, and executed is provably the *same* identity, not a re-derived
  equivalent (ADR-002-029 SCI-INV-002/010).
* **Behavioral reproducibility SHALL be reproducible-from-recorded-inputs** — given
  the recorded Decision Context Capsule, that artifact identity, the versions, and
  any declared seed and captured response, re-execution SHALL reconstruct the same
  outcome and rationale (RFC-003 §10; RFC-008 §9). This recorded-input granularity
  is the normative standard; bit-for-bit *output* equality is required only where
  the platform guarantees determinism, and is never a substitute for identity.

"The artifact tested is the artifact that runs" is therefore an **identity equality**
(exact bytes), while "it behaves the same on re-execution" is **recorded-input
reproducibility**. This ADR fixes both granularities and defers the replay protocol
to ADR-002-016 and the admission-identity mechanism to ADR-002-029.

This ADR grants no authority, creates no capacity, admits no artifact, and
authorizes no live operation.

---

## 2. Context

RFC-009 §9 and RFC-010 §9 require that the artifact reviewed and tested be provably
the artifact that runs, and RFC-008 §9 supplies the recorded provenance that makes
that checkable; each defers the exact granularity: RFC-009 §14 Q3 and RFC-010 §14 Q2 ask "bit-for-bit vs.
reproducible-from-recorded-inputs," and RFC-008 §14 Q3 carries the reproducibility
clause. RFC-010 §9 warns that "a test result bound to a mutable or unidentified
artifact is weak evidence"; ADR-002-029 already requires exact, content-addressed
artifact identity (SCI-INV-002) and that actual runtime bytes match (SCI-INV-010),
and rejects a branch, tag, `latest`, passing scan, or successful build as identity.
RFC-008 §9 requires evaluation to record the Capsule identity/digest and the
artifact, DSL, and configuration versions as conforming inputs to the ADR-002-016
deterministic replay.

What remains open is the *granularity standard* itself — how exact "the same
artifact" and "the same behavior" must be. This ADR sets it, so RFC-010's "tested =
admitted" and RFC-009's "reviewed = runs" have a precise meaning and so ADR-002-016
replay has a defined comparison target. It does not define the replay protocol, the
admission mechanism, or the external-value capture discipline (ADR-DEV-003).

---

## 3. Decision Drivers

1. **Review must bind to the thing that runs.** An independent review or test is
   evidence only about the exact artifact it examined; a mutable or re-derived
   artifact voids that evidence (RFC-010 §9; philosophy §33).
2. **Identity and behavior are different questions.** "Which artifact" is answered
   by exact bytes; "does it behave the same" is answered by reproducing an outcome
   from recorded inputs. Conflating them either over-constrains (demanding bit-for-
   bit output on non-deterministic platforms) or under-constrains (accepting a
   mutable artifact).
3. **Bit-for-bit output is often infeasible and unnecessary.** Floating point,
   parallelism, and platform variation can defeat bit-for-bit output equality;
   recorded-input reproducibility is both achievable and sufficient for replay and
   review (RFC-003 §10).
4. **Exact identity is feasible and already required.** Content-addressing is
   established for software artifacts (ADR-002-029 SCI-INV-002/010); the Authored
   Strategy inherits it.
5. **Missing or unrecorded inputs are conservative.** An outcome that depends on an
   input not in the record is not reproducible and cannot be trusted (ADR-002-016
   ERI-INV-003; philosophy §8).

---

## 4. Scope and Non-Scope

**In scope:**

* the granularity of artifact identity (exact / content-addressed);
* the granularity of behavioral reproducibility (reproducible-from-recorded-inputs);
* the completeness and binding of the recorded input set;
* the conservative treatment of a non-reproducible or unidentified artifact.

**Not in scope (owned elsewhere):**

* the deterministic-replay protocol, Replay Capsule, and evidence integrity —
  ADR-002-016; this ADR supplies conforming inputs;
* the software-artifact admission and content-addressed identity *mechanism* —
  ADR-002-029; this ADR requires exact identity, it does not define admission;
* the Decision Context Capsule contract and Critical Input governance — ADR-002-018;
* the capture, staleness, and re-authoring discipline of externally-sourced /
  LLM-derived values — ADR-DEV-003 (RFC-008 §14 Q3);
* the enforcement mechanism whose version is recorded — ADR-DEV-001;
* what independent verification of a conformance claim is — ADR-DEV-005 (resolving
  RFC-009 §14 Q2 and RFC-010 §14 Q4); the block on treating an author's own asserted
  result as verification rests here on RFC-010 §9 and philosophy §34, not on the
  deferred ADR-DEV-005;
* numeric determinism tolerances, which are approved configuration and the
  Verification Profile.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-000 §6, RFC-002 §3.1, RFC-003 §5, RFC-008
§5, and the ADR series (**Replay Capsule**, ADR-002-016 §5.8; **Source Revision
Manifest**, ADR-002-029 §5.2), and SHALL NOT introduce synonyms. The following
terms are scoped to this decision and are non-authorizing.

* **Artifact Identity** — the exact, content-addressed digest of the Authored
  Strategy together with its DSL version, Enforcement Mechanism version, and
  configuration version. A mutable name, tag, `latest`, cache path, passing scan, or
  successful build is not Artifact Identity (ADR-002-029 SCI-INV-002 and §1).
* **Recorded Input Set** — the complete set of inputs an evaluation's outcome
  depends on: the Decision Context Capsule identity/digest, the Artifact Identity,
  the DSL/Enforcement-Mechanism/configuration versions, and any declared stochastic
  seed with its captured response (RFC-008 §9; RFC-003 §10).
* **Recorded-Input Reproducibility** — the property that re-executing the same
  Artifact Identity over the same Recorded Input Set reconstructs the same outcome
  and rationale. It is a behavioral property, distinct from bit-for-bit output
  equality.

These terms describe reproducibility and identity granularity. None grants
authority, admits an artifact, or defines the replay protocol.

---

## 6. Safety Invariants

* **ARI-INV-001 — Exact, Content-Addressed Artifact Identity.** The artifact tested,
  reviewed, admitted, and executed SHALL be the same content-addressed Artifact
  Identity; a mutable name, tag, `latest`, cache, passing scan, or successful build
  is not identity (ADR-002-029 SCI-INV-002/010 and §1).
* **ARI-INV-002 — Behavioral Reproducibility Is Reproducible-From-Recorded-Inputs.**
  Re-executing the same Artifact Identity over the same Recorded Input Set SHALL
  reconstruct the same outcome and rationale (RFC-003 §10; RFC-008 §9). This is the
  normative granularity; bit-for-bit output equality is required only where the
  platform guarantees determinism and never substitutes for identity.
* **ARI-INV-003 — Recorded Inputs Are Complete and Bound to Identity.** The Recorded
  Input Set SHALL include every input the outcome depends on and SHALL be bound to
  the Artifact Identity; an outcome that depends on an unrecorded input is
  non-reproducible and non-conforming (RFC-008 §9; external-value capture owned by
  ADR-DEV-003).
* **ARI-INV-004 — Identity Precedes Reproduction.** Test or review evidence bound to
  a mutable or unidentified artifact is void as reproducibility evidence; a
  reproducibility claim requires the exact Artifact Identity first (RFC-010 §9, which
  calls such a result weak evidence; escalated to void here because ADR-002-029
  SCI-INV-002 rejects a label as identity outright).
* **ARI-INV-005 — Conforming Input, Not a Replacement.** Artifact Identity and
  Recorded-Input Reproducibility supply conforming inputs to the ADR-002-016
  deterministic replay and evidence integrity and to ADR-002-029 admission; this ADR
  defines neither the replay protocol nor the admission mechanism (ADR-002-016
  ERI-INV-001).
* **ARI-INV-006 — Non-Reproducible Is Conservative.** An artifact whose outcome
  cannot be reproduced from its Recorded Input Set, or whose Artifact Identity cannot
  be established, is inadmissible for live authoring and void as safety evidence; it
  SHALL NOT be accepted optimistically (ADR-002-016 ERI-INV-003; philosophy §8).

---

## 7. Artifact Identity Granularity

Artifact Identity SHALL be **exact and content-addressed** (ARI-INV-001):

* The identity covers the Authored Strategy source together with the DSL version, the
  ADR-DEV-001 Enforcement Mechanism version, and the configuration version, because
  the same source under a different DSL or enforcement version is a different
  behavior surface.
* "The artifact tested = reviewed = admitted = runs" is an equality of this identity,
  not a claim that two builds are equivalent. A change to any component is a versioned
  substitution producing a new identity (RFC-008 §6 principle 8; RFC-003 §13), never
  an in-place mutation.
* The identity *mechanism* — content-addressing, signing, registry custody, runtime
  attestation — is owned by ADR-002-029; this ADR requires that an Authored Strategy
  carry such an identity and that all evidence bind to it, and defines no new
  mechanism.

---

## 8. Behavioral Reproducibility Granularity

Behavioral reproducibility SHALL be **reproducible-from-recorded-inputs**
(ARI-INV-002):

* Re-executing the same Artifact Identity over the same Recorded Input Set SHALL
  reconstruct the same outcome (Proposal or no-action) and the same rationale
  (RFC-003 §10; RFC-008 §9). This is what an independent reviewer and the ADR-002-016
  replay compare against.
* **Bit-for-bit output equality is not the normative bar.** It is required only where
  the platform guarantees deterministic computation for the operations used, because
  floating-point, parallelism, and platform variation can defeat it without any loss
  of decision correctness. Where bit-for-bit equality is claimed, it SHALL be
  demonstrated, not assumed.
* Declared stochastic or externally-sourced components do not break reproducibility
  because their seed and captured response are in the Recorded Input Set and the
  value is captured before evaluation, never fetched live (RFC-008 §9; ADR-DEV-003
  owns the capture/staleness discipline).
* Reproducibility is a property of the artifact-plus-record, not of the author's
  assertion; an author's claim that an outcome is reproducible is evidence for
  independent verification (ADR-DEV-005), never verification itself.

---

## 9. The Recorded Input Set and Its Binding

For Recorded-Input Reproducibility to hold, the Recorded Input Set SHALL be complete
and bound (ARI-INV-003):

* It SHALL contain the Decision Context Capsule identity/digest, the Artifact
  Identity, the DSL/Enforcement-Mechanism/configuration versions, and each declared
  stochastic seed with its captured response (RFC-008 §9).
* It SHALL be bound to the Artifact Identity so that a record cannot be silently
  paired with a different artifact (ARI-INV-004).
* An outcome that depends on any input outside the Recorded Input Set — an ambient
  clock, a live fetch, a mutable global (all already unexpressible per ADR-DEV-001
  DCE-INV-003) — is non-reproducible by construction and non-conforming.
* The execution-environment determinism profile for decision-affecting operations
  SHALL itself be either guaranteed deterministic by the ADR-DEV-001 Enforcement
  Mechanism and RFC-008 §9 pure evaluation, or captured in the Recorded Input Set. A
  platform- or evaluator-introduced non-determinism below the DSL surface (e.g. an
  unseeded parallel reduction order) — which the strategy does not express, so
  DCE-INV-003 does not reach it — that is neither guaranteed deterministic nor
  recorded is non-conforming (RFC-008 §6 principle 4, §9).
* The record is a conforming input to ADR-002-016 evidence and replay integrity; this
  ADR defines what SHALL be recorded for reproducibility, not how the evidence store
  preserves or replays it (ARI-INV-005).

---

## 10. Alternatives Considered

* **10.1 Require bit-for-bit output reproducibility as the normative bar.** Rejected:
  often infeasible (floating point, parallelism, platform variation) and unnecessary
  for decision correctness; would either block conforming strategies or invite
  waivers that erode the standard.
* **10.2 Require only behavioral reproducibility, with identity by mutable
  name/version label.** Rejected: a mutable label lets the tested artifact differ from
  the running one, voiding review evidence (RFC-010 §9; ADR-002-029 rejects labels as
  identity).
* **10.3 Treat the author's asserted reproducibility as sufficient.** Rejected: an
  author's assertion is evidence for independent verification, never verification
  (ADR-DEV-005; philosophy §33/§34).
* **10.4 Record only a subset of inputs ("the important ones").** Rejected: any
  unrecorded input the outcome depends on makes replay non-deterministic and the
  claim unfalsifiable (ARI-INV-003; ADR-002-016 ERI-INV-003).
* **10.5 Define reproducibility here and also define the replay protocol.** Rejected:
  replay integrity is owned by ADR-002-016; duplicating it would create a second,
  divergent protocol (ARI-INV-005).

---

## 11. Consequences

**Positive.**

* Gives RFC-010 "tested = admitted" and RFC-009 "reviewed = runs" a precise meaning
  (identity equality) and gives ADR-002-016 replay a defined comparison target.
* Reproducible-from-recorded-inputs is achievable across realistic platforms without
  waivers, while exact identity remains strict.
* Separating identity from behavior prevents both over- and under-constraint.

**Negative / costs.**

* Every evaluation SHALL record a complete input set and bind it to a content-
  addressed identity — recording and tooling cost.
* Any input the outcome depends on must be brought into the record or made
  unexpressible; hidden dependencies become conformance failures.
* Bit-for-bit claims, where made, must be demonstrated per platform, not assumed.

---

## 12. Failure Modes Introduced by This Decision

* **12.1 Incomplete record.** An outcome depends on an unrecorded input; replay
  diverges. Conservative by ARI-INV-003/006 (non-conforming), but a gap could ship
  undetected until replay fails — surfaced by the RFC-010 reproducibility tests.
* **12.2 Identity/record mismatch.** A record paired with the wrong Artifact
  Identity; prevented by the binding requirement (ARI-INV-004) and detected by replay
  comparison.
* **12.3 Spurious bit-for-bit expectation.** A pipeline demands bit-for-bit output on
  a non-deterministic platform and fails conforming strategies; avoided by making
  recorded-input reproducibility the bar (ARI-INV-002).
* **12.4 Silent non-determinism.** A platform- or evaluator-introduced source of
  non-determinism *below* the DSL surface — for example an unseeded, non-associative
  floating-point parallel reduction — that the strategy does not express and that is
  not a declared seed. This is a distinct class from strategy-reachable ambient state
  (which ADR-DEV-001 DCE-INV-003 makes unexpressible, and which §9 already covers):
  it is forbidden at the outcome level by RFC-008 §6 principle 4 and §9 (evaluation is
  a pure function of its inputs, so no decision-affecting non-deterministic reduction
  is conforming), it is closed by the execution-environment determinism profile
  required in §9, and it is caught by the perturbation-based reproducibility
  demonstration of §13.1 — not by DCE-INV-003.

---

## 13. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010):

* **13.1** Re-executing the same Artifact Identity over the same Recorded Input Set
  reconstructs the same outcome and rationale (ARI-INV-002), and the demonstration
  SHALL perturb the platform's non-deterministic dimensions — thread scheduling,
  parallelism, reduction order, and floating-point mode — and require outcome
  stability, so a single benign re-run cannot discharge it.
* **13.2** A change to the source, DSL version, Enforcement Mechanism version, or
  configuration produces a different Artifact Identity (ARI-INV-001; RFC-008 §6
  principle 8).
* **13.3** Test/review evidence bound to a mutable or unidentified artifact is
  rejected as reproducibility evidence (ARI-INV-004).
* **13.4** An evaluation whose outcome depends on an input outside the Recorded Input
  Set — including a platform- or evaluator-introduced non-determinism surfaced by the
  §13.1 perturbation — is detected as non-reproducible and treated conservatively
  (ARI-INV-003, -006).
* **13.5** A declared stochastic component reproduces from its recorded seed and
  captured response (ARI-INV-002; RFC-008 §9).
* **13.6** Where bit-for-bit output equality is claimed for a platform, it is
  demonstrated for the operations used, not assumed (§8).

---

## 14. Acceptance Criteria

ADR-DEV-002 is acceptable when:

* Artifact Identity is exact and content-addressed, and all test/review/admission/
  runtime evidence binds to that same identity (ARI-INV-001, -004);
* recorded-input reproducibility is the demonstrated behavioral standard, with
  bit-for-bit output required only where platform-guaranteed (ARI-INV-002; §§8, 13);
* the Recorded Input Set is complete and bound to identity, and unrecorded-input
  dependence is conservative (ARI-INV-003, -006);
* the ADR supplies conforming inputs to ADR-002-016 and ADR-002-029 without
  redefining replay or admission (ARI-INV-005);
* independent adversarial review (EV-L0) confirms every §13 obligation is discharged
  and every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 15. Traceability

| Requirement | Discharge in ADR-DEV-002 |
|---|---|
| RFC-009 §14 Q3 (bit-for-bit vs recorded-inputs) | identity exact/content-addressed; behavior reproducible-from-recorded-inputs (§§1, 7, 8) |
| RFC-010 §14 Q2 (tested = admitted granularity) | identity equality binds tested and admitted; recorded-input reproducibility is the compared behavior (§§7, 8; ARI-INV-001, -002) |
| RFC-008 §14 Q3 (reproducibility clause) | recorded-input reproducibility with declared seeds captured before evaluation (§8) |
| RFC-008 §9 (recorded provenance) | Recorded Input Set defines what evaluation records (§9; ARI-INV-003) |
| RFC-010 §9 (mutable/unidentified artifact = weak evidence) | identity precedes reproduction (ARI-INV-004) |
| RFC-003 §10 (determinism/reproducibility) | reproducible-from-recorded-inputs standard (§8; ARI-INV-002) |
| RFC-003 §13 (versioned substitution) | any component change is a new Artifact Identity (§7; ARI-INV-001) |
| ADR-002-029 SCI-INV-002/010 (exact identity; runtime bytes match) | Artifact Identity is content-addressed; mechanism deferred (§7; ARI-INV-001) |
| ADR-002-016 (replay/evidence integrity; ERI-INV-001/003) | conforming inputs, not a replacement; non-reproducible is conservative (§9; ARI-INV-005, -006) |
| ADR-DEV-001 (DCE-INV-003) | ambient/live-fetch dependence unexpressible → not a hidden input (§9) |
| ADR-DEV-003 (external-value capture/staleness) | declared external values captured before evaluation; capture discipline deferred (§8) |
| philosophy §8, §33, §34 | uncertainty-restrictive; demonstration-required; an author's assertion is not verification (§§3, 6, 8, 10.3) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes the
identity and reproducibility granularities and relies on ADR-002-016 replay and
ADR-002-029 admission for enforcement.

---

## 16. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-002, resolving RFC-009 §14 Q3, RFC-010 §14 Q2, and the
  reproducibility clause of RFC-008 §14 Q3.
* Set the decision: Artifact Identity is exact and content-addressed (bit-for-bit
  bytes), while behavioral reproducibility is reproducible-from-recorded-inputs;
  "tested = runs" is an identity equality, not output re-derivation.
* Defined six invariants ARI-INV-001…006, the Recorded Input Set and its binding
  (§9), and five rejected alternatives (§10), and traced them to RFC-008 §9,
  RFC-009 §9, RFC-010 §9, RFC-003 §§10, 13, ADR-002-016 (ERI-INV-001/003),
  ADR-002-029 (SCI-INV-002/010), and ADR-DEV-001/003/005.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no
  acceptance or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding. Thirteen sequences were attempted — mutable-label-as-identity,
  re-derived-build-as-same-artifact, ambient-clock/live-fetch/mutable-global
  dependence, unseeded parallel-reduction non-determinism, author-self-asserted
  reproducibility-as-verification, the bit-for-bit-vs-recorded-inputs gap,
  record/artifact mismatch, partial "important inputs only" recording,
  scan/build-as-identity, external-value live side channel, out-of-band runtime
  flag, and a DSL/enforcement version bump under one source digest — and all were
  confirmed blocked by ARI-INV-001…006 and §§7–9; every citation was verified. One
  Major finding was resolved: §12.4 had mis-attributed containment of *platform- or
  evaluator-introduced* non-determinism (below the DSL surface) to ADR-DEV-001
  DCE-INV-003, which governs only strategy-reachable ambient state — re-anchored on
  RFC-008 §6 principle 4 / §9 pure evaluation, closed by a new execution-environment
  determinism-profile requirement in §9 (guaranteed-deterministic or recorded), and
  made demonstrable by a perturbation-based §13.1 (thread scheduling, parallelism,
  reduction order, FP mode) so a single benign re-run cannot discharge it (§13.4
  aligned). Five Minor citation-precision fixes were applied: scan/build-not-identity
  co-cited to ADR-002-029 §1; the "weak → void" escalation grounded in SCI-INV-002;
  philosophy §34 added to §15; the ADR-DEV-005 forward reference anchored to
  RFC-009 §14 Q2 / RFC-010 §14 Q4 with the standing block noted; and §2's RFC-008 §9
  framing softened to "supplies recorded provenance." The review is EV-L0 only and
  confers no acceptance or live-readiness.
