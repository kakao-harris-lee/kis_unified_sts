# ADR-DEV-001 — DSL Realization and Purity/Escape-Closure Enforcement

**ADR ID:** ADR-DEV-001
**Title:** DSL Realization and Purity/Escape-Closure Enforcement
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-008 — Strategy DSL
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-008 §14 Q1 (realization form) and Q2 (enforcement mechanism and its verification)
**Date:** 2026-07-15
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-15
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

The Strategy DSL SHALL be realized as a **default-deny, capability-restricted
authoring surface** whose vocabulary admits only the expressions RFC-008 §7 permits,
and its purity and escape-closure (RFC-008 §9, §11 item 17) SHALL be enforced by
**three complementary, non-self-trusting layers** — static admissibility analysis,
capability-restricted evaluation, and an isolation boundary — none of which is
trusted alone. The enforcement mechanism SHALL itself be a **verified,
non-authorizing artifact**: exercised by the adversarial containment suite (RFC-010
§8), admitted as software (ADR-002-029), and conferring no authority. This decision
makes RFC-008's *unexpressibility* thesis (RFC-008 §6 principle 1) a structural
property rather than an authoring convention.

This ADR selects a realization and enforcement architecture. It grants no authority,
creates no capacity, admits no artifact, and authorizes no live operation.

---

## 2. Context

RFC-008 establishes **containment by construction**: every RFC-003 §11 prohibition,
plus the DSL-specific ambient-state prohibition (RFC-008 §11 item 12) and the
escape-closure property (RFC-008 §11 item 17), SHALL be *unexpressible* at the
authoring surface, not merely forbidden. RFC-008 §7 fixes what a strategy MAY
express and §9 requires pure, bounded, isolated evaluation with context delivered
only through the Decision Context Capsule (RFC-008 §6 principle 3; ADR-002-018).

RFC-008 left two questions open (RFC-008 §14 Q1, Q2): *how* the surface is realized
(standalone language, embedded subset, or restricted API), and *by what mechanism*
purity and the absence of ambient state are enforced and how that mechanism is
itself verified. RFC-010 §8 depends on the answer — it requires the containment
guarantee to be tested against real escape vectors, and warns that "an unverified
enforcement mechanism leaves the unexpressibility claim aspirational." Until this
ADR is accepted, RFC-010's containment suite (and the minimum escape-vector set of
RFC-010 §14 Q1) cannot be fully specified. This ADR resolves the realization and
enforcement questions; it does not define the test-vector set, which remains owned
by RFC-010 and its ADR.

---

## 3. Decision Drivers

1. **Unexpressibility must be structural, not aspirational.** A prohibition enforced
   only by an author's discipline or a reviewer's vigilance is not containment
   (RFC-008 §6 principle 1; philosophy §13).
2. **A containment surface with an escape hatch is not a containment surface**
   (RFC-008 §11, closing rule). FFI, an unconstrained embedded host, dynamic
   loading, or reflection can reintroduce every prohibited effect.
3. **The proposer is untrusted** (RFC-002 §7.3; philosophy §13). The realization
   SHALL assume the authored artifact is adversarial, including AI-authored
   artifacts (RFC-009).
4. **Purity enables review and replay.** Pure, bounded, reproducible evaluation is
   what lets an independent party verify an artifact and lets ADR-002-016 replay it
   (RFC-008 §9; RFC-003 §10).
5. **Defense in depth.** No static analysis is provably complete against every
   escape; no single runtime guard is provably unbypassable. Layered enforcement
   contains the residual failure of any one layer.
6. **The enforcement mechanism is itself software** and inherits no trust it did not
   earn (RFC-010 §8; ADR-002-029; philosophy §33).

---

## 4. Scope and Non-Scope

**In scope:**

* the realization form of the DSL and the default-deny criterion that governs it;
* the layered mechanism that enforces purity, absence of ambient authority, and
  escape-closure;
* the requirement and standard for verifying the enforcement mechanism itself;
* the conservative treatment of an artifact whose containment cannot be established.

**Not in scope (owned elsewhere):**

* the concrete surface grammar, keywords, or API signatures — approved
  configuration and detailed design, not a safety decision;
* the *minimum adversarial escape-vector set* the containment suite must attempt —
  owned by ADR-DEV-009 (RFC-010 §14 Q1); RFC-010 §8 builds and runs the suite;
* deterministic-replay and evidence integrity — owned by ADR-002-016; this ADR
  supplies conforming inputs;
* software-artifact admission of the enforcement components and authored artifacts —
  owned by ADR-002-029;
* Critical Input governance and the Capsule contract — owned by ADR-002-018;
* what a strategy MAY express (RFC-008 §7) and the Proposal contract (RFC-008 §8;
  ADR-002-020 §8);
* externally-sourced/LLM-derived value capture and staleness — owned by ADR-DEV-003
  (RFC-008 §14 Q3);
* reproducibility granularity (bit-for-bit vs. reproducible-from-recorded-inputs) —
  owned by ADR-DEV-002 (RFC-008 §14 Q3⁻; RFC-010 §14 Q2).

---

## 5. Definitions

This ADR reuses canonical terms from RFC-000 §6, RFC-002 §3.1, RFC-003 §5, and
RFC-008 §5 (**Strategy DSL**, **Proposal Builder**, **Expressible Effect**), and
SHALL NOT introduce synonyms for them. The following terms are scoped to this
decision and are non-authorizing.

* **Authoring Surface Vocabulary** — the complete set of Expressible Effects
  (RFC-008 §5) the DSL provides a term, argument, handle, or reachable construct
  for. Default-deny means this set is exactly the RFC-008 §7 permitted expressions.
* **Static Admissibility Analysis** — the pre-evaluation check that proves an
  authored artifact references nothing outside the Authoring Surface Vocabulary
  (no ambient state, FFI, import, reflection, dynamic evaluation, or host builtin).
  Its output is admissible / inadmissible; it grants no authority and is not
  software-artifact admission (ADR-002-029).
* **Capability-Restricted Evaluation** — evaluation in which the only capabilities
  in scope are the read-only Decision Context Capsule and the effect-free Proposal
  Builder; every other capability (clock, randomness, network, filesystem, mutable
  global, host builtin) is absent, not merely denied on use.
* **Isolation Boundary** — the runtime containment in which evaluation executes such
  that an escape not caught statically still cannot reach a prohibited effect, and
  in which time and resource bounds are enforced (RFC-008 §9 bounded evaluation).
* **Enforcement Mechanism** — the composite of Static Admissibility Analysis,
  Capability-Restricted Evaluation, and the Isolation Boundary. It is a software
  artifact, not an authority.

---

## 6. Safety Invariants

* **DCE-INV-001 — Default-Deny Expressibility.** The Authoring Surface Vocabulary is
  exactly the RFC-008 §7 permitted expressions; anything outside it is *absent from
  the surface*, not blocklisted on a reachable general-purpose host. A DSL realized
  as a full host language guarded by a denylist is non-conforming (RFC-008 §6
  principle 1, §7).
* **DCE-INV-002 — Layered, Non-Self-Trusting Enforcement.** Purity, absence of
  ambient authority, and escape-closure SHALL be enforced by Static Admissibility
  Analysis *and* Capability-Restricted Evaluation *and* the Isolation Boundary. No
  single layer is trusted alone; the failure of one layer SHALL NOT by itself
  expose a prohibited effect.
* **DCE-INV-003 — No Ambient Authority.** The evaluation environment SHALL expose
  only the read-only Capsule and the effect-free Proposal Builder. No ambient clock,
  randomness, network, filesystem, mutable global, or host builtin is reachable
  (RFC-008 §9, §11 item 12; ADR-002-018).
* **DCE-INV-004 — Escape-Closure.** No foreign-function interface, unconstrained
  embedded host, dynamic code loading, reflection, or extension point may
  reintroduce any effect prohibited by RFC-008 §11 items 1–16. An extension point
  that could is non-conforming (RFC-008 §11 item 17). Item 17 enumerates the
  foreign-function interface, unconstrained embedded host, dynamic code loading, and
  extension point; this ADR adds reflection as a conservative strengthening of the
  same escape class.
* **DCE-INV-005 — Enforcement Is a Verified, Non-Authorizing Artifact.** The
  Enforcement Mechanism SHALL itself be exercised by the adversarial containment
  suite (RFC-010 §8), admitted as software (ADR-002-029), and version-recorded; it
  confers no authority, and an unverified or bypassable mechanism leaves
  unexpressibility aspirational (RFC-010 §8; philosophy §33).
* **DCE-INV-006 — Inadmissible Is Conservative.** An authored artifact that cannot
  be statically proven within the Authoring Surface Vocabulary, or for which the
  Enforcement Mechanism cannot be established, is inadmissible for live authoring; it
  SHALL NOT be admitted optimistically (philosophy §8; RFC-003 §6 principle 3).
* **DCE-INV-007 — Bounded Evaluation Degrades to No-Action.** Exhausting a time or
  resource bound SHALL degrade to no-action for that strategy's scope, never to an
  unbounded stall or a partial, unrecorded action (RFC-008 §9; RFC-003 §13).

---

## 7. Realization Form (RFC-008 §14 Q1)

The DSL SHALL be realized so that **default-deny expressibility (DCE-INV-001)**
holds. Three realization families were considered against that criterion:

* **Standalone constrained language** — a purpose-built language whose grammar
  admits only §7 expressions. Meets default-deny natively: prohibited effects have
  no syntax.
* **Strictly-restricted embedded subset** — a capability-restricted sublanguage of a
  host, admissible **only if** the host is unreachable around the surface (no host
  builtins, import, reflection, or dynamic evaluation in scope), so it is
  functionally equivalent to a standalone constrained language.
* **Restricted API over a general-purpose host** — a permitted-only API exposed to
  otherwise-arbitrary host code. Conforming **only if** the host cannot be reached
  around the API; if arbitrary host code remains executable, the API is a denylist,
  not a surface, and is non-conforming (DCE-INV-001, DCE-INV-004).

**Decision.** Any of the three is permitted **iff** default-deny expressibility and
escape-closure hold; a general-purpose host guarded by a denylist is **not**. The
decisive property is not which family is chosen but that prohibited effects are
*absent from the reachable vocabulary*. Where the realization embeds or extends a
host, escape-closure (DCE-INV-004) SHALL be demonstrated for that embedding, not
assumed. RFC-008 §14 Q1's comparative sub-question — which family is *most* credible
— is deliberately not adjudicated as a safety matter: any family that satisfies
default-deny and escape-closure is conforming, and the concrete choice among them is
approved design and configuration (§4).

---

## 8. Enforcement Architecture (RFC-008 §14 Q2)

Enforcement SHALL be layered and defense-in-depth (DCE-INV-002). The three layers
are complementary, not redundant substitutes:

1. **Static Admissibility Analysis (before evaluation).** The authored artifact is
   analyzed against the Authoring Surface Vocabulary; any reference outside it —
   ambient state, FFI, import, reflection, dynamic evaluation, host builtin, or a
   wildcard/"latest" scope (RFC-008 §11 item 13; ADR-002-020 §8) — makes the
   artifact **inadmissible**. Inadmissibility is the default for anything not proven
   inside the surface (DCE-INV-006). This layer makes prohibited effects
   *inadmissible*.
2. **Capability-Restricted Evaluation (during evaluation).** The runtime passes only
   explicit capabilities — the read-only Capsule and the effect-free Proposal
   Builder — and holds no ambient capability in scope (DCE-INV-003). This layer makes
   prohibited effects *unreachable* even if a static check were incomplete.
3. **Isolation Boundary (containment of residual failure).** Evaluation executes in
   an environment that denies host-process access, dynamic loading, and network/
   filesystem egress, and enforces time and resource bounds whose exhaustion
   degrades to no-action (DCE-INV-007). This layer *contains* an escape that slipped
   the other two.

No layer is trusted alone (DCE-INV-002): for the ambient-authority, FFI, and
dynamic-loading/escape class, static analysis need not be provably complete and
capability restriction need not be provably unbypassable, because the isolation
boundary contains the residue — and vice versa. A content defect that is *not* a
host escape — a wildcard or "latest" scope (RFC-008 §11 item 13) — is not contained
by the isolation boundary; it is rejected by static admissibility (layer 1) and,
additionally, by the effect-free Proposal Builder (RFC-008 §8) and downstream
canonical-construction fencing (ADR-002-020 §8). The enforcement layers produce
evidence (admissibility result, capability manifest, bound outcomes) as conforming
inputs to ADR-002-016 replay integrity; they define none of it.

---

## 9. Verification of the Enforcement Mechanism (RFC-008 §14 Q2, second clause)

The Enforcement Mechanism SHALL NOT be self-certifying (DCE-INV-005):

* **Adversarially tested.** It SHALL be exercised by the RFC-010 §8 containment
  suite, which attempts to express each RFC-008 §11 prohibited effect and each
  escape vector (item 17) and demonstrates rejection, unreachability, or
  containment. The *minimum* escape-vector set is owned by ADR-DEV-009 (RFC-010 §14 Q1);
  RFC-010 §8 builds and runs the suite. This ADR requires only that the mechanism be
  tested against it, not what it contains.
* **Admitted as software.** The analyzer, capability runtime, and isolation boundary
  are software artifacts subject to ADR-002-029 admission and content-addressed
  identity; a change to any of them is a versioned substitution (RFC-008 §6
  principle 8), never an in-place mutation.
* **Version-bound to evaluation evidence.** Each evaluation records the Enforcement
  Mechanism version alongside the Capsule identity, Authored Strategy version, DSL
  version, and configuration version (RFC-008 §9), so the surface that contained an
  artifact is provably the surface reviewed and replayed (ADR-002-016).
* **Conservative on unverified enforcement.** If the Enforcement Mechanism's
  verification cannot be established for a given surface version, artifacts authored
  against it are inadmissible for live authoring (DCE-INV-006); an unverified
  mechanism is treated as absent containment, not as presumed-good.

---

## 10. Alternatives Considered

* **10.1 General-purpose language with a denylist.** Rejected: a denylist over a
  reachable host is defeated by any un-enumerated escape (import, reflection, FFI),
  violating DCE-INV-001/004; unexpressibility becomes a blocklist race.
* **10.2 Single-layer enforcement (static analysis only).** Rejected: no static
  analysis is provably complete against every dynamic escape; a missed vector is an
  open hole with no containment (violates DCE-INV-002).
* **10.3 Single-layer enforcement (sandbox only).** Rejected: a runtime sandbox
  without static admissibility admits artifacts whose intent to escape is only
  discovered at run time, forfeiting pre-evaluation review and reproducibility and
  concentrating trust in one boundary (violates DCE-INV-002, DCE-INV-006).
* **10.4 Author/reviewer discipline as the guarantee.** Rejected: makes containment
  a convention an untrusted (possibly AI) author is asked to observe, which is
  exactly what RFC-008 §6 principle 1 and philosophy §13 forbid.
* **10.5 Trust the enforcement mechanism without verifying it.** Rejected: the
  mechanism is software and inherits no trust it did not earn; an unverified
  mechanism leaves the whole unexpressibility claim aspirational (RFC-010 §8;
  violates DCE-INV-005).
* **10.6 Permit an extension point / plugin surface for expressive convenience.**
  Rejected: any extension point that can reintroduce a prohibited effect is an escape
  hatch (violates DCE-INV-004); expressive needs are raised through governance and
  the model/architecture layer (RFC-008 §7), not a language escape.

---

## 11. Consequences

**Positive.**

* Makes RFC-008 unexpressibility structural and testable, unblocking the RFC-010 §8
  containment suite.
* Layering contains the residual failure of any single enforcement component.
* A verified, version-bound mechanism gives independent review and ADR-002-016
  replay a stable, provable surface.

**Negative / costs.**

* Default-deny plus layered enforcement constrains DSL expressiveness and adds
  static-analysis and isolation engineering cost.
* Every enforcement-component change is a versioned substitution requiring
  re-verification (RFC-010 §8) and re-admission (ADR-002-029).
* Escape-closure for any embedded/extended realization must be demonstrated, not
  assumed, raising the bar for host-embedded designs.

---

## 12. Failure Modes Introduced by This Decision

* **12.1 Incomplete static analysis.** A missed escape vector is admitted; contained
  by the capability and isolation layers (DCE-INV-002) and surfaced by the RFC-010
  §8 suite, but a residual unknown remains until the vector is added to the minimum
  set (RFC-010 §14 Q1).
* **12.2 Capability leak.** An ambient capability inadvertently in scope defeats
  DCE-INV-003; contained by the isolation boundary and detected by containment
  tests.
* **12.3 Isolation-boundary bypass.** A host-escape or resource-bound bypass; the
  most severe residual, mitigated only by the other two layers and by
  version-bound re-verification of the boundary.
* **12.4 Unverified enforcement version drift.** An enforcement-component change that
  ships without re-verification; DCE-INV-005/006 require treating it as absent
  containment (inadmissible), and §13.6 makes the positive obligation concrete — the
  Enforcement Mechanism version is recorded in evaluation evidence and
  content-addressed for admission. A residual process gap that admitted an
  un-reverified version is owned operationally by ADR-002-029.
* **12.5 Over-restriction.** A legitimate authoring need is wrongly inadmissible;
  conservative by design (DCE-INV-006) and resolved through governance, never by
  relaxing enforcement.

---

## 13. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010; this ADR specifies the
obligations, not the test-vector set):

* **13.1** Each RFC-008 §11 item 1–16 prohibited effect is unexpressible or rejected
  at the surface (static admissibility) — positive and adversarial cases.
* **13.2** Each escape vector — FFI, embedded host, dynamic loading, extension point
  (RFC-008 §11 item 17), and reflection (added by this ADR) — is rejected,
  unreachable, or contained, with the attempt recorded.
* **13.3** No ambient capability (clock, randomness, network, filesystem, mutable
  global, host builtin) is reachable during evaluation (DCE-INV-003).
* **13.4** An artifact not statically provable within the surface is inadmissible,
  never admitted optimistically (DCE-INV-006).
* **13.5** Time/resource-bound exhaustion degrades to no-action, never to a stall or
  partial unrecorded action (DCE-INV-007).
* **13.6** The Enforcement Mechanism version is recorded in evaluation evidence and
  is content-addressed for admission (DCE-INV-005; ADR-002-016, ADR-002-029).
* **13.7** Each single-layer failure is independently simulated — (a) incomplete
  static admissibility, (b) an inadvertent capability in evaluation scope, and (c) an
  isolation-boundary bypass — and in each case the remaining two layers are shown to
  contain the prohibited effect (DCE-INV-002; §§12.1–12.3).

---

## 14. Acceptance Criteria

ADR-DEV-001 is acceptable when:

* the realization satisfies default-deny expressibility (DCE-INV-001) and
  escape-closure (DCE-INV-004), demonstrated for the chosen realization family;
* the three enforcement layers exist and are independently effective, with no single
  layer trusted alone (DCE-INV-002);
* the evaluation environment exposes only the Capsule and Proposal Builder
  (DCE-INV-003);
* the Enforcement Mechanism is exercised by the RFC-010 §8 suite, admitted under
  ADR-002-029, and version-bound to evaluation evidence (DCE-INV-005);
* inadmissible-is-conservative and bounded-degrades-to-no-action hold (DCE-INV-006,
  DCE-INV-007);
* independent adversarial review (EV-L0) confirms every §13 verification obligation
  is discharged and every citation resolves against source.

Acceptance of this ADR records a decision; it grants no authority and does not
authorize live operation, which remain governed by RFC-001 and VER-002-001.

---

## 15. Traceability

| Requirement | Discharge in ADR-DEV-001 |
|---|---|
| RFC-008 §14 Q1 (realization form) | default-deny realization criterion; three families permitted iff escape-closure holds (§7; DCE-INV-001) |
| RFC-008 §14 Q2 (enforcement mechanism + its verification) | three-layer enforcement (§8) and its adversarial verification (§9; DCE-INV-002, -005) |
| RFC-008 §6 principle 1 (containment by construction) | unexpressibility made structural (§1, §6, §7) |
| RFC-008 §9 (purity, ambient absence, bounded eval) | no ambient authority; bounded degrades to no-action (DCE-INV-003, -007) |
| RFC-008 §11 item 12 (ambient state) | DCE-INV-003 |
| RFC-008 §11 item 17 (escape-closure) | DCE-INV-004; §§7, 8 |
| RFC-002 §7.3 (untrusted proposer) | realization assumes an adversarial author (§3, §7) |
| RFC-003 §11 (decision↔safety boundary) | prohibited effects unexpressible/inadmissible (§§6, 8, 13) |
| ADR-002-018 (Critical Input, Capsule) | context only through the read-only Capsule (DCE-INV-003) |
| ADR-002-016 (evidence/replay integrity) | enforcement layers supply conforming, version-bound inputs; define none of it (§§8, 9) |
| ADR-002-020 §8 (no wildcard/"latest") | static admissibility rejects wildcard/"latest" scope (§8) |
| ADR-002-029 (software-artifact admission) | Enforcement Mechanism and artifacts admitted; changes are versioned substitutions (§9) |
| RFC-010 §8 (containment testing) | mechanism is adversarially verified, not self-certifying (§9; DCE-INV-005) |
| philosophy §§8, 13, 33 | uncertainty-restrictive, untrusted-proposer, demonstration-required (§§3, 6, 9) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It relies on the
enforcement, admission, and replay-integrity points already defined upstream; its
contribution is to fix the realization and the layered mechanism that make RFC-008
unexpressibility structural and verifiable.

---

## 16. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-001 as the first Development-layer decision record, resolving
  RFC-008 §14 Q1 (realization form) and Q2 (enforcement mechanism and its
  verification).
* Set the decision: a default-deny, capability-restricted authoring surface with
  three-layer, non-self-trusting enforcement (static admissibility analysis,
  capability-restricted evaluation, isolation boundary), and a verified,
  non-authorizing Enforcement Mechanism.
* Defined seven safety invariants DCE-INV-001…007 and traced them to RFC-008 §§6,
  7, 9, 11, RFC-002 §7.3, RFC-003 §11, ADR-002-016/018/020/029, and RFC-010 §8.
* Recorded the realization criterion (§7), the layered enforcement architecture
  (§8), the mechanism-verification standard (§9), six rejected alternatives (§10),
  and the verification obligations and acceptance criteria (§§13, 14).
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no
  acceptance or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding. Fifteen containment-escape / authority-leak sequences were
  attempted — self-approval via a confidence field, FFI-to-transmit, dynamic
  loading/eval, reflection to a host builtin, ambient-clock read, live network fetch
  during evaluation, an extension point reintroducing a prohibited effect, a
  restricted-API-over-reachable-host, protective self-labeling, live-arm via a
  timing constraint, a self-certifying enforcement mechanism, enforcement version
  drift, optimistic admit on inconclusive static analysis, a capability leak, and
  aggregate-state laundering — and all fifteen were confirmed blocked by DCE-INV-001…
  007 and §§7–9; every load-bearing citation was verified against source. Two Major
  findings were resolved: (M1) §13.7 verified only the static single-layer failure —
  now requires independently simulating each of the three single-layer failures
  (static, capability, isolation) so DCE-INV-002 is demonstrated, not asserted, for
  all three (§§12.1–12.3); (M2) §8's "isolation boundary contains the residue" claim
  was over-generalized — now scoped to the ambient/FFI/escape class, with wildcard/
  "latest" content defects attributed to the Proposal Builder (RFC-008 §8) and
  ADR-002-020 §8 instead. Four Minor fixes were applied: reflection marked as an ADR
  strengthening beyond RFC-008 §11 item 17's literal enumeration (DCE-INV-004, §13.2);
  DCE-INV-006 citation narrowed to RFC-003 §6 principle 3; §12.4 now points at §13.6
  as the closing obligation; and §7 states that Q1's comparative sub-question is set
  aside as design/configuration. The review is EV-L0 only and confers no acceptance
  or live-readiness.
