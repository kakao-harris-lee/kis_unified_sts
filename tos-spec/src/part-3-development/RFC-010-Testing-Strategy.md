# RFC-010 — Testing Strategy

**Document ID:** RFC-010
**Title:** Testing Strategy
**Version:** 0.1 Review Draft
**Status:** Review Draft — Development
**Classification:** Implementation-Layer Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Safety Authority:** Constrained by RFC-001 — Safety Case and RFC-002 — Architecture
**Decision Authority:** Constrained by RFC-003 — Decision Framework
**Authoring Surface:** Realized through RFC-008 — Strategy DSL and RFC-009 — Agent Guide
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-15
**Last Updated:** 2026-07-15

---

## 1. Abstract

This document defines the **Testing Strategy**: the discipline by which an Authored
Strategy, the Strategy DSL that expresses it, and the pipeline that authors it are
tested, so that their claimed properties become demonstrated rather than asserted.
Per RFC-000 §9 Implementation defines HOW SOFTWARE IS BUILT; RFC-010 occupies that
layer as the verification companion to RFC-008 and RFC-009.

RFC-010 is subordinate to RFC-000, RFC-001, RFC-002, every accepted ADR-002-xxx,
and RFC-003, and it serves the authoring work of RFC-008 and RFC-009. Its governing
thesis is inherited directly from philosophy §37.8: **tests prove only what their
assumptions and acceptance criteria cover**. A passing test suite is evidence for
review, never a safety authority; it cannot make an unsafe strategy safe, cannot
grant live-readiness, and cannot substitute for the prevention that the architecture
enforces before execution. RFC-010 defines what testing must demonstrate and the
limits of what it may claim — it does not become the gate it feeds.

RFC-010 defines a testing discipline. It selects no strategy, grants no authority,
and its acceptance does not authorize live operation.

---

## 2. Normative Authority

RFC-010's authority is bounded as follows:

* **RFC-000 — Trading Constitution** governs this document. RFC-010 SHALL NOT
  redefine constitutional intent (RFC-000 §9) and SHALL use RFC-000 §6
  vocabulary verbatim.
* **RFC-001 — Safety Case** constrains this document. Testing supplies objective
  evidence toward the `ACCEPTED` state RFC-001 §1 requires, but a passing test
  SHALL NOT weaken, bypass, or self-certify any SAFE-xxx requirement, and testing
  never substitutes for prevention.
* **RFC-002 — Architecture** and the accepted **ADR-002-xxx** series define the
  components, evidence, and gates testing feeds. RFC-010 supplies conforming
  inputs to the evidence and replay integrity of ADR-002-016 and to the
  verification artifacts of VER-002-001; it defines none of them and replaces
  none of them.
* **RFC-003 — Decision Framework** defines the determinism, reproducibility, and
  decision-quality discipline (§§10, 12) that RFC-010's tests exercise; RFC-010
  inherits every RFC-003 boundary.
* **RFC-008 — Strategy DSL** and **RFC-009 — Agent Guide** define the surface and
  the author whose properties RFC-010 verifies; RFC-010 adds no expressive power
  and grants no author any trust that testing did not independently earn.
* Where RFC-010 and any higher document appear to conflict, the higher document
  governs and the conflict SHALL be raised through governance, not resolved by a
  local testing convention.

RFC-010 defines a testing discipline. It creates no capacity, authority,
configuration, transmission permission, or protective status, and its acceptance
does not authorize live operation.

---

## 3. Scope and Non-Scope

This document governs:

* what testing SHALL demonstrate about an Authored Strategy: determinism,
  isolation, containment, and no-action correctness;
* how the DSL and its runtime are tested so the RFC-008 containment guarantee is
  verified rather than assumed;
* how an author's conformance claims (RFC-009) are made independently verifiable;
* the discipline of hermetic, reproducible tests and how they feed replay
  integrity (ADR-002-016);
* the evidentiary limits of testing and backtesting, and their relationship to the
  restricted-live verification that ADR-002-025 owns;
* the boundary between the testing discipline and every safety-enforcement,
  acceptance, and admission owner.

This document does not decide:

* the authoring surface (RFC-008) or the authoring actor's discipline (RFC-009);
* the decision process (RFC-003) or any model (RFC-004–007);
* the safety-evidence and deterministic-replay protocol itself — ADR-002-016 owns
  that; RFC-010 supplies conforming inputs;
* the verification-evidence specification and acceptance artifacts — VER-002-001
  and RFC-001 own the `ACCEPTED` gate;
* whether a strategy is admitted to run (ADR-002-029) or promoted toward live
  (ADR-002-025);
* how an admitted strategy is operated (RFC-011);
* numeric coverage targets, thresholds, or pass criteria, which are approved
  configuration and the Verification Profile.

A testing practice that reaches beyond this scope — or that treats a passing suite
as an authority — is non-conforming regardless of its coverage.

---

## 4. Relationship to Vision and Philosophy

RFC-010 operationalizes principles already established upstream; it inherits, and
does not restate, them.

* **Testable** (Vision §9.5). Critical behavior — duplicate events, stale input,
  clock failure, broker inconsistency, partial fill, unknown order state, restart,
  partition, external activity, configuration error, protective-capacity
  exhaustion — SHALL be demonstrable through repeatable tests; a safety property
  that cannot be tested objectively remains an unproven claim.
* **Safety claims require demonstration** (philosophy §33). Specified,
  Implemented, Demonstrated, and Accepted are distinct states; implementing a
  control does not prove it works, and passing a nominal test does not prove it
  works under failure.
* **Tests prove only what their assumptions and acceptance criteria cover**
  (philosophy §37.8). A test's authority is bounded by its assumptions; RFC-010
  makes those assumptions explicit rather than letting a green suite imply more
  than it verified.
* **Prevention is stronger than explanation** (philosophy §11, Vision §6.5).
  Testing, audit, and replay are essential but do not recover capital lost to an
  irreversible action; testing concentrates assurance before execution and never
  substitutes for the architecture's pre-execution prevention.
* **Backtests are evidence, not proof** (philosophy §28, Vision §11.9). Simulated
  or historical performance is one form of evidence, never demonstrated live edge
  and never production-readiness.

Where a testing practice would contradict a Vision or Philosophy principle, that
practice is non-conforming.

---

## 5. Definitions

RFC-010 reuses canonical terms from RFC-000 §6, RFC-001 §5, RFC-002 §3.1, the
ADR series, RFC-003 §5, RFC-008 §5, and RFC-009 §5. It SHALL NOT introduce
synonyms for any of them. The following terms are scoped to the testing discipline
and are non-authorizing.

* **Conformance Test** — a repeatable test that demonstrates an Authored Strategy,
  the DSL, or the authoring pipeline exhibits a required property (determinism,
  isolation, containment, no-action correctness). A Conformance Test produces
  evidence for review; it is not itself an acceptance or admission.
* **Hermetic Test** — a test whose result depends only on its declared inputs and
  fixtures, with no dependence on ambient clock, network, live broker, shared
  mutable state, or external service, so that it is reproducible and attributable
  (Vision §9.5; RFC-003 §10).
* **Test Assumption** — an explicitly recorded precondition or fixture a test
  depends on. Per philosophy §37.8 a test proves nothing beyond what its
  assumptions and acceptance criteria cover; RFC-010 requires assumptions to be
  explicit so the limit of a passing result is visible.
* **Backtest** — a simulation of a Decision Policy over historical data. A
  Backtest is evidence toward a hypothesis, never demonstrated live edge
  (philosophy §28) and never a substitute for restricted-live verification
  (ADR-002-025).

These terms describe a testing discipline. None grants authority, admits an
artifact, or authorizes live operation.

---

## 6. Testing Strategy Principles

A conforming testing discipline SHALL satisfy the following. They are obligations
on how properties are demonstrated, not new runtime enforcement; the enforcement,
acceptance, and admission points remain owned by RFC-002, the ADR series, and
RFC-001.

1. **Tests are evidence, not authority.** A passing test is objective evidence for
   review toward the `ACCEPTED` state (RFC-001 §1); it never itself accepts,
   admits, promotes, or authorizes (philosophy §33).
2. **Assumptions are explicit.** Every Conformance Test SHALL record its Test
   Assumptions and acceptance criteria; a result claims nothing beyond them
   (philosophy §37.8).
3. **Hermetic and reproducible.** A Conformance Test SHALL be hermetic and
   reproducible from its declared inputs, with no dependence on ambient state, so
   the artifact tested is provably the artifact reviewed (RFC-003 §10; Vision
   §9.5).
4. **Failure paths are first-class.** Testing SHALL exercise boundary, fault,
   restart, duplicate-event, partition, time-failure, and degraded-context
   scenarios, not only the nominal path; passing the nominal path proves nothing
   about failure (philosophy §33; Vision §9.5).
5. **Testing does not replace prevention.** No test regime substitutes for the
   pre-execution prevention the architecture enforces; testing concentrates
   assurance before execution and augments, never replaces, it (philosophy §11).
6. **Backtests do not demonstrate live edge.** A Backtest is bounded evidence;
   demonstrated live edge requires the restricted-live verification ADR-002-025
   owns (philosophy §28; RFC-003 §12).
7. **Independent verification.** An author's conformance claim SHALL be verifiable
   by a party independent of the author; running the author's own asserted result
   is not verification (RFC-009 §10; philosophy §34).

---

## 7. Testing the Authored Strategy

An Authored Strategy carries properties that RFC-008 and RFC-003 require. RFC-010
requires each to be demonstrated, not assumed.

* **Determinism.** Testing SHALL demonstrate that evaluating a strategy over a
  fixed Decision Context and fixed configuration yields an identical outcome and
  rationale on re-execution (RFC-003 §10; RFC-008 §9). A declared seeded-stochastic
  component SHALL reproduce from its recorded seed and captured response.
* **Isolation.** Testing SHALL demonstrate that a strategy's error, divergence,
  resource exhaustion, or removal degrades to no-action for its own scope and does
  not affect another strategy's outcome or any safety control (RFC-008 §9; RFC-003
  §13).
* **No-action correctness.** Testing SHALL demonstrate that declining to act, and
  an explicit flat, are produced, recorded, and reproduced with the same rigor as
  an action, and that degraded context narrows rather than widens the action set
  (RFC-003 §6; RFC-008 §6).
* **Boundedness.** Testing SHALL demonstrate that an evaluation exceeding its time
  or resource bound degrades to no-action, never to an unbounded stall or a
  partial, unrecorded action (RFC-008 §9).
* **Proposal well-formedness.** Testing SHALL demonstrate that emitted Proposals
  populate the required field set without wildcard or "latest policy" references
  (RFC-008 §8; ADR-002-020 §8) — while recognizing that well-formedness is
  necessary, never sufficient, for authorization.

Demonstrating these properties is necessary evidence toward acceptance; it does not
itself accept, admit, or authorize the strategy.

---

## 8. Testing the DSL and Its Containment

RFC-008's central claim is that the prohibited effects are *unexpressible*. A claim
of unexpressibility is only as strong as the evidence that the surface truly cannot
express them; RFC-010 requires that evidence.

* **Containment is tested, not assumed.** Testing SHALL attempt to express each
  RFC-008 §11 prohibited effect through the DSL and demonstrate that the surface
  rejects or cannot represent it — approval, transmission, capacity mutation,
  live-arming, safety-config change, protective self-labeling, ambient-state
  access, and escape via foreign-function interface, embedded host, or dynamic
  loading (RFC-008 §11 items 1–17).
* **Enforcement mechanism is verified.** Whatever mechanism enforces purity and the
  absence of ambient state — a capability-restricted interpreter, static rejection,
  a sandbox, or a combination (RFC-008 §14 Q2) — SHALL itself be tested against
  attempted escapes, since an unverified enforcement mechanism leaves the
  unexpressibility claim aspirational.
* **Negative tests are required.** The suite SHALL include adversarial negative
  tests that try to break containment, not only positive tests that confirm
  intended authoring works; a suite that only exercises intended use proves
  nothing about the escape surface (philosophy §37.8).
* **Assumptions of the containment suite are explicit.** The containment suite's
  Test Assumptions SHALL be recorded, because a containment claim is bounded by the
  escape vectors the suite actually attempted.

The unexpressibility guarantee of RFC-008 is a testable property; RFC-010 makes its
demonstration a requirement rather than a hope.

---

## 9. Testing the Authoring Pipeline and Hermeticity

RFC-009 makes the author untrusted and requires an authored artifact to be
reviewable. RFC-010 supplies the tests that make review and replay possible.

* **Hermetic by default.** A Conformance Test SHALL depend only on declared inputs
  and fixtures — no ambient clock, live network, live broker, or shared mutable
  state — so results are reproducible and attributable (Vision §9.5; RFC-003 §10).
  Where a test must exercise an external interaction, it does so against a recorded
  or simulated boundary, never a live real-capital path (RFC-001 §5.10 Non-Live Mode;
  RFC-002 §7.6).
* **Reproducible artifact identity.** Testing SHOULD run against the exact artifact
  that will be reviewed and admitted, so the artifact tested is provably the
  artifact that runs (ADR-002-016; ADR-002-029). A test result bound to a mutable
  or unidentified artifact is weak evidence.
* **Provenance of test evidence.** Test results offered as safety evidence SHALL
  carry the versions and inputs they ran against, as conforming inputs to the
  evidence and deterministic-replay integrity ADR-002-016 owns; RFC-010 supplies
  those inputs and does not replace that integrity.
* **AI-authored artifacts test like any other.** A strategy produced by an
  Authoring Agent is tested and independently verified exactly as a human-authored
  one; the author's own passing result is evidence for review, not verification
  (RFC-009 §10; philosophy §34).

Hermeticity is what makes a test result mean the same thing on re-execution; it is
the property that lets review trust the evidence rather than the author.

---

## 10. The Limits of Testing and the Live Gate

This section states plainly what testing cannot do, so a green suite is never
mistaken for readiness.

* **A passing suite is not acceptance.** Objective test evidence is a precondition
  for the `ACCEPTED` state, but acceptance requires independent review and the
  gate RFC-001 and VER-002-001 define; a suite does not accept itself (philosophy
  §33; RFC-001 §1).
* **A passing suite is not admission.** Whether an artifact may run is decided by
  software-artifact admission on content-addressed identity; a green test run,
  passing scan, or CI success cannot create admission eligibility (ADR-002-029 §§1,
  15, 25.5, SCI-AC-006).
* **A backtest is not live edge.** Historical simulation is evidence toward a
  hypothesis; demonstrated live edge requires the restricted-live verification of
  ADR-002-025 (philosophy §28; RFC-003 §12; RFC-006 §11).
* **Coverage is not correctness.** High coverage does not imply the assumptions
  were right; a test proves only what its assumptions and acceptance criteria cover
  (philosophy §37.8). RFC-010 SHALL NOT let a coverage number stand in for
  demonstrated failure-mode behavior.
* **Test confidence is bounded.** A visible pass is still bounded by its
  assumptions; testing avoids the false confidence philosophy §37 warns against —
  its historical, technical, monitoring, redundancy, configuration, broker, human,
  and test-confidence forms (§37.1–37.8), of which test confidence (§37.8) is only
  one.

Testing earns the right for a claim to be reviewed. It does not earn the claim.

---

## 11. The Testing↔Safety Boundary

This section is the load-bearing safety content of RFC-010. It restates, at the
testing-discipline layer, the separation that RFC-002 §9.1, the ADR series, RFC-003
§11, RFC-008 §11, and RFC-009 §11 enforce. Every item is a hard boundary.

A testing regime, harness, suite, or result SHALL NOT:

1. accept a safety requirement, or move it to `ACCEPTED`, on its own authority;
   acceptance requires independent review and the RFC-001/VER-002-001 gate
   (RFC-001 §1; philosophy §33);
2. admit an artifact to run, or serve as admission identity; a green run, passing
   scan, or CI success is not admission (ADR-002-029 §§1, 15, 25.5, SCI-AC-006);
3. authorize, arm, or presume live operation, or promote a strategy toward live;
   promotion is owned by ADR-002-025 (RFC-002 §7.6; ADR-002-007);
4. commit, reserve, or presume risk capacity for a tested strategy (ADR-002-002;
   RFC-002 §9.1);
5. classify a tested action as protective, or verify a protective claim into
   existence; protective classification is owned by the Protective Action
   Controller (ADR-002-001 §6; RFC-002 §9.1);
6. substitute for the architecture's pre-execution prevention, or justify relaxing
   a control because a test passed (philosophy §11; Vision §6.5);
7. weaken, relax, or reinterpret a SAFE-xxx requirement or safety configuration
   because a suite is green (RFC-001 §7.5; RFC-002 §7.4);
8. reach a live real-capital broker path from a research, backtest, simulation, or
   test context (RFC-001 §5.10 Non-Live Mode, SAFE-045; RFC-002 §7.6);
9. present a backtest or a passing suite as demonstrated live edge or as
   restricted-live evidence (philosophy §28; ADR-002-025; RFC-003 §12);
10. treat coverage, a green suite, or the author's own asserted result as
    verification; independent verification is required, and a test proves only what
    its assumptions cover (philosophy §34, §37.8; RFC-009 §10);
11. stand in for the deterministic-replay and evidence integrity ADR-002-016 owns,
    rather than supplying conforming inputs to it (ADR-002-016);
12. claim a containment property the suite did not actually attempt to break; an
    untested escape vector is an open claim, not a closed one (RFC-008 §11;
    philosophy §37.8).

The single generalizing rule (RFC-002 §9.1; RFC-008 §11; RFC-009 §11): the
identity that proposes, authors, or verifies an action is not thereby the identity
that approves, admits, or authorizes it. RFC-010 occupies only the
evidence-producing role — testing demonstrates properties for independent review,
and a passing suite is the beginning of a case, never its conclusion.

---

## 12. Relationship to RFC-008, RFC-009, and RFC-011

RFC-010 is the verification companion within Part 3. The pointers below are
non-normative scope markers; RFC-010 SHALL NOT define their content.

* **RFC-008 — Strategy DSL.** The surface whose containment RFC-010 verifies;
  RFC-010 tests the unexpressibility claim rather than restating the surface.
* **RFC-009 — Agent Guide.** The authoring actor whose conformance claims RFC-010
  makes independently verifiable; RFC-009 requires such verification to exist,
  RFC-010 defines it.
* **RFC-011 — Operational Guidelines.** How an admitted strategy is operated in
  production. Runtime continuous conformance monitoring is a distinct discipline
  from pre-deployment testing and is architecturally owned by ADR-002-028 (and its
  RFC-002 §10.30 component), not by RFC-010 or RFC-011; RFC-010 ends at
  pre-deployment demonstration and supplies no runtime monitor. RFC-011 governs
  operating within that monitoring, and SHALL NOT be pre-empted here.

Until RFC-011 is authored and accepted, its concerns remain open and SHALL NOT be
resolved by testing convention.

---

## 13. Requirements Traceability

RFC-010 discharges implementation-layer verification obligations that RFC-000,
RFC-001, RFC-002, RFC-003, RFC-008, and RFC-009 assign to the testing discipline.
This table is an initial allocation and SHALL be refined as RFC-011 is accepted.

| Requirement | Discharge in RFC-010 |
|---|---|
| RFC-000 §9 layering (Implementation defines HOW SOFTWARE IS BUILT) | RFC-010 confined to the testing discipline; defines no WHY/WHAT/HOW-DECISIONS content (§§1, 2) |
| RFC-001 §1 (`ACCEPTED` requires objective evidence + independent review) | testing supplies evidence toward acceptance; it does not accept itself (§§6, 10, 11.1) |
| RFC-001 §7.5 (Separation of Authority) | a green suite grants no self-acceptance of safety evidence (§§10, 11.1, 11.7) |
| RFC-001 §5.10 Non-Live Mode, SAFE-045; RFC-002 §7.6 | no test/backtest/simulation path reaches a live broker (§§9, 11.8) |
| RFC-002 §9.1 authority ownership | testing gains none of accept/admit/authorize/commit/classify (§11) |
| RFC-003 §10 determinism/reproducibility | determinism and hermeticity are demonstrated, not assumed (§§7, 9) |
| RFC-003 §12 (expectancy; backtest-not-proof) | backtests are bounded evidence; live edge needs ADR-002-025 (§§6, 10, 11.9) |
| RFC-008 §11 (containment, items 1–17) | the unexpressibility claim is a tested requirement, incl. adversarial negative tests (§8, §11.12) |
| RFC-009 §10 (independent verification; no self-review) | author's conformance claims independently verified; author's result is not verification (§§6, 9, 10, 11.10) |
| ADR-002-016 (evidence/replay integrity) | hermetic, reproducible tests supply conforming inputs; do not replace the protocol (§§9, 11.11) |
| ADR-002-025 (restricted-live promotion) | backtests/suites are not live-readiness; promotion separately owned (§§6, 10, 11.9) |
| ADR-002-029 (software-artifact admission) | a green run/scan/CI is not admission identity (§§10, 11.2) |
| ADR-002-028 (continuous conformance monitoring) | runtime monitoring is owned by ADR-002-028, not by RFC-010's pre-deployment testing (§12) |
| VER-002-001 (verification-evidence specification) | testing produces evidence into the verification artifacts; it does not define the acceptance gate (§§2, 3, 10) |
| Vision §9.5; philosophy §§11, 28, 33, 34, 37.8 | testable, prevention-first, backtest-is-evidence, demonstration-required, bounded-test-confidence operationalized (§§4, 6, 10) |

RFC-010 introduces no SAFE-xxx requirement and no numeric bound. It relies entirely
on the enforcement, acceptance, and admission points already defined upstream.

---

## 14. Open Questions

These questions are open while RFC-010 is a Review Draft and while RFC-011 is
unwritten. They SHALL NOT be resolved by informal testing convention.

1. What minimum set of adversarial escape vectors must the containment suite (§8)
   attempt for the RFC-008 unexpressibility claim to be treated as demonstrated
   rather than open, and how is that set kept current as the DSL evolves?
2. How reproducible must a Conformance Test be — bit-for-bit vs.
   reproducible-from-recorded-inputs — for the artifact tested to be provably the
   artifact admitted (§9; ADR-002-016; RFC-008 §9 and §14 Q3)?
3. What backtest methodology and cost/slippage realism (RFC-005 §9, RFC-006 §11)
   is required before a backtest is admissible evidence toward a hypothesis, and
   what explicitly disqualifies a look-ahead-biased or overfit backtest?
4. What constitutes *independent* verification of an AI-authored strategy's
   conformance claims — must the verifying party be human, a distinct tool, or
   either — consistent with RFC-009 §10's no-self-review rule?
5. How are Test Assumptions recorded and reviewed so that the bounded scope of a
   passing suite (philosophy §37.8) is visible to an independent reviewer rather
   than implied?
6. Where does the boundary sit between RFC-010 pre-deployment testing and the
   runtime continuous conformance monitoring owned by ADR-002-028, so that
   pre-deployment demonstration and runtime monitoring neither leave a gap nor
   duplicate each other?

Unresolved questions reduce, and do not expand, the properties a suite may claim to
have demonstrated.

---

## 15. Review History

### v0.1 — Initial Draft

* Established RFC-010 as the Implementation-layer Testing Strategy: the
  verification companion to RFC-008 and RFC-009, governing how an Authored
  Strategy, the DSL, and the authoring pipeline are tested.
* Set the governing thesis from philosophy §37.8 — **tests prove only what their
  assumptions and acceptance criteria cover** — and made the evidentiary limits of
  testing and backtesting explicit (§§6, 10): a passing suite is evidence for
  review, never acceptance, admission, live-readiness, or a substitute for
  prevention.
* Required determinism, isolation, no-action correctness, boundedness, and
  Proposal well-formedness to be demonstrated (§7); required the RFC-008
  containment/unexpressibility claim to be tested with adversarial negative tests
  and a verified enforcement mechanism (§8); required hermetic, reproducible tests
  that feed ADR-002-016 replay and that verify author claims independently (§9).
* Restated the boundary as twelve prohibitions on the testing regime (§11), each
  traced to RFC-002 §9.1, RFC-001 §1/§7.5/Non-Live Mode, ADR-002-016/025/029,
  RFC-008 §11, and RFC-009 §10.
* Marked scope relationships to RFC-008/009 and forward to RFC-011 without
  pre-empting them (§12).
* Introduced no SAFE-xxx requirement, numeric bound, or authority.
* An in-context self-adversarial review corrected one substantive ownership defect
  before independent review: §12 and §14 Q6 had implied that runtime continuous
  conformance monitoring is an RFC-011 concern, whereas it is architecturally owned
  by ADR-002-028 (and its RFC-002 §10.30 component); the pointers now attribute it
  to ADR-002-028 and confine RFC-010 to pre-deployment demonstration, with
  ADR-002-028 added to §13.
* Independent adversarial EV-L0 document review then returned **PASS-WITH-FIXES**
  with no Critical finding, restoring RFC-010 to the EV-L0 standard applied to
  RFC-008 and RFC-009 (the earlier self-review is superseded). Fifteen
  false-readiness / authority-via-testing sequences were attempted —
  green-suite-as-acceptance, scan/CI-as-admission, backtest-as-live-edge,
  coverage-as-correctness, author-result-as-verification,
  same-agent-twice-as-independent, control-relaxed-because-tests-pass,
  live-broker-from-test-path, untested-containment-claim, and
  testing-as-prevention-substitute among them — and all were confirmed blocked by
  §§6, 8, 9, 10, 11; every load-bearing citation was verified against source,
  including ADR-002-029 §25.5 (the rejected "a passing scan or test admits the
  artifact" alternative), ADR-002-020 §8's verbatim "latest policy" prohibition,
  Vision §6.5's "concentrates assurance before execution," and philosophy §37.8's
  governing thesis. Two Minor precision fixes were applied: §10's false-confidence
  parenthetical now lists all eight philosophy §37.1–37.8 forms rather than reading
  as a partial enumeration, and §14 Q2's reproducibility cross-reference now points
  to RFC-008 §9 and §14 Q3 (reproducibility/staleness) rather than §14 Q2
  (enforcement mechanism). The review is EV-L0 only and confers no acceptance or
  live-readiness.
* Governance note (inherited citation imprecision — RESOLVED). The one Major finding
  raised — §2's RFC-000 §12 citation for "SHALL NOT redefine constitutional intent,"
  whose literal phrase is in RFC-000 §9 (§12 states the cognate "reinterpret
  higher-level intent") — was the series-wide item shared by RFC-003 through
  RFC-011; §2 now cites RFC-000 §9, corrected consistently across the series in a
  single companion change.
