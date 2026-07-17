# VER-DEV-001 — Development-Track Verification Evidence Specification

- **Status:** Proposed — Ready for Test Implementation
- **Date:** 2026-07-17
- **Verification Scope:** Part 2 (RFC-003 through RFC-007) and Part 3 (RFC-008 through RFC-011, ADR-DEV-001 through ADR-DEV-015).
- **Companion register:** verification/EVIDENCE-REGISTER-DEV.md (the machine-editable CSV is authoritative).
- **Production Authorization:** NO

---

## 1. Purpose

This specification instantiates the Vision §7.7 traceability chain
(Requirement → Architecture → Implementation → Verification Evidence) for the
decision and development layers. It collects the RFC-000 reserved `DEC-xxx` and
`TEST-xxx` namespaces (instantiated through governance in RFC-000-Patch-0012) and
gives every Part-2/3 invariant and each Part-2 decision-boundary and RFC-010
testing-boundary cluster at least one evidence row under the same discipline as
VER-002-001.

It closes the structural gap recorded in the Wave-4 inventory: RFC-003 through
RFC-007 define zero named invariants, so before this specification their
normative content carried no requirement identity or evidence row. The
`DEC-EV-001` through `DEC-EV-005` cluster rows give each Part-2 decision RFC a
requirement identity and an evidence obligation for the first time.

This specification is independent of VER-002-001 and does not change the Part-1
evidence count. Its companion register (`EVIDENCE-REGISTER-DEV`, 97 items) never
enters the Part-1 count accounting.

## 2. Result States and Evidence Strength Levels (by reference)

The authoritative Result-State vocabulary is **VER-002-001 §4**. The Evidence
Strength Levels EV-L0 through EV-L6 and the composite level notation are
**VER-002-001 §5**. This specification DEFINES no new state, level, or notation
and cites them verbatim.

## 3. Acceptance Gate Rule (by reference)

The accepting-state whitelist Gate Rule of `EVIDENCE-REGISTER-002` (§"Gate Rule")
applies verbatim to this track; VER-DEV-001 introduces no new accepting state.
Every ADR-DEV and every boundary cluster remains `Proposed` until its required
evidence is `PASS` (or a correctly conditioned `WAIVED_WITH_RESIDUAL_RISK`) and
independently reviewed, with reviewer provenance recorded per ADR-DEV-005.

## 4. Narrow-Only Constraint

No evidence, invariant, or boundary requirement in this track widens, relaxes, or
reinterprets any Part-1 authority, limit, gate, or Hard Safety Envelope
constraint (RFC-000 §12). Every case is verified against the Part-1 enforcement
point it narrows or conforms to. Passing any case here creates no capacity, no
authority, no admission, and no live readiness.

## 5. Evidence Cases

The 91 invariant cases are 1:1 with the Part-3 ADR-DEV invariants
(`PFX-EV-0nn` supports `PFX-INV-0nn`). The label **Injection** is used where the
minimum level exercises a fault; **Probe** is used for pure EV-L0 design
inspection.

### DCE — ADR-DEV-001 (DSL Realization and Escape-Closure)

#### DCE-EV-001 — Default-Deny Expressibility
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-001 DCE-INV-001
- **Injection:** Attempt to express an effect outside RFC-008 §7's permitted vocabulary, and attempt to realize the surface as a full host guarded by a denylist.
- **Expected:** Only the enumerated permitted expressions are surface-reachable; everything else is absent, and a denylist-guarded full host is non-conforming.

#### DCE-EV-002 — Layered Non-Self-Trusting Enforcement
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-001 DCE-INV-002
- **Injection:** Disable or defeat one enforcement layer (purity, no-ambient, or escape-closure) in isolation.
- **Expected:** No single layer's failure by itself exposes a prohibited effect; purity, no-ambient-authority, and escape-closure remain jointly enforced.

#### DCE-EV-003 — No Ambient Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-001 DCE-INV-003
- **Injection:** From within evaluation, attempt to reach an ambient clock, randomness, network, filesystem, mutable global, or host builtin.
- **Expected:** The evaluation environment exposes only the read-only Capsule and the effect-free Proposal Builder; no ambient capability is reachable.

#### DCE-EV-004 — Escape-Closure
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-001 DCE-INV-004
- **Injection:** Attempt to reintroduce a prohibited effect via FFI, embedded host, dynamic loading, reflection, or an extension point.
- **Expected:** No extension mechanism can reintroduce a prohibited effect; any such extension point is non-conforming.

#### DCE-EV-005 — Enforcement Is a Verified Non-Authorizing Artifact
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-001 DCE-INV-005
- **Injection:** Present an unverified, unversioned, or bypassable enforcement mechanism as the containment guarantee.
- **Expected:** The enforcement mechanism is itself adversarially tested, software-admitted, and version-recorded; an unverified mechanism leaves unexpressibility aspirational and is rejected.

#### DCE-EV-006 — Inadmissible Is Conservative
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-001 DCE-INV-006
- **Injection:** Submit an artifact not statically provable within the vocabulary, or one whose enforcement cannot be established.
- **Expected:** The artifact fails closed as inadmissible; it is never admitted optimistically.

#### DCE-EV-007 — Bounded Evaluation Degrades to No-Action
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-001 DCE-INV-007
- **Injection:** Exhaust the time or resource bound during evaluation of a strategy scope.
- **Expected:** Evaluation degrades to no-action for that scope; there is no unbounded stall and no partial unrecorded action.

### ARI — ADR-DEV-002 (Artifact Reproducibility and Identity)

#### ARI-EV-001 — Exact Content-Addressed Artifact Identity
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-002 ARI-INV-001
- **Injection:** Substitute a mutable name, tag, "latest", cache entry, passing scan, or build for the tested/reviewed/admitted/executed artifact.
- **Expected:** Identity is the content-addressed artifact; a mutable reference is not identity and is rejected across test, review, admission, and execution.

#### ARI-EV-002 — Behavioral Reproducibility Is Reproducible-From-Recorded-Inputs
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-002 ARI-INV-002
- **Injection:** Re-execute the same identity over the same recorded input set and compare outcome and rationale; demand bit-for-bit equality where the platform does not guarantee determinism.
- **Expected:** The same outcome and rationale reconstruct; bit-for-bit output equality is required only where the platform guarantees determinism.

#### ARI-EV-003 — Recorded Inputs Are Complete and Bound to Identity
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-002 ARI-INV-003
- **Injection:** Let the outcome depend on an input absent from the recorded input set or not bound to identity.
- **Expected:** The recorded input set includes every input the outcome depends on and is bound to identity; dependence on an unrecorded input is non-reproducible and non-conforming.

#### ARI-EV-004 — Identity Precedes Reproduction
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-002 ARI-INV-004
- **Injection:** Bind test or review evidence to a mutable or unidentified artifact and offer it as reproducibility evidence.
- **Expected:** Evidence bound to a mutable or unidentified artifact is void as reproducibility evidence; exact identity comes first.

#### ARI-EV-005 — Conforming Input Not a Replacement
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-002 ARI-INV-005
- **Injection:** Attempt to have identity/recorded-input reproducibility redefine the ADR-002-016 replay or ADR-002-029 admission protocol.
- **Expected:** Reproducibility supplies conforming inputs to replay and admission without redefining either protocol.

#### ARI-EV-006 — Non-Reproducible Is Conservative
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-002 ARI-INV-006
- **Injection:** Present an artifact whose outcome cannot be reproduced or whose identity cannot be established.
- **Expected:** It fails closed as inadmissible and void as safety evidence; it is never accepted optimistically.

### EXV — ADR-DEV-003 (External Value Capture and Staleness)

#### EXV-EV-001 — Captured Not Called
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-003 EXV-INV-001
- **Injection:** Attempt a live fetch of an external value during DSL evaluation.
- **Expected:** The external value is produced before evaluation and delivered through the Capsule as Critical Input; evaluation performs no live fetch.

#### EXV-EV-002 — Staleness Is Bounded and Restrictive Anchored to Production Time
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-003 EXV-INV-002
- **Injection:** Present a captured value past its validity window (or with no window) and attempt to convert it to permission via TTL, cache, or last-known-good.
- **Expected:** Each value carries a validity window anchored to production/as-of time; once STALE (or UNKNOWN with no window) it blocks new risk, and no cache converts staleness into permission.

#### EXV-EV-003 — Stale Requires Re-Authoring Not Reuse
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-003 EXV-INV-003
- **Injection:** Silently reuse a stale config binding instead of re-capturing it.
- **Expected:** A stale value is re-captured as a new Critical Input; a stale config binding is a Versioned Substitution producing a new Artifact Identity, never silent reuse.

#### EXV-EV-004 — Correction Invalidates
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-003 EXV-INV-004
- **Injection:** Apply a material correction, retraction, or source-continuity change and attempt new-risk transmission on dependent artifacts.
- **Expected:** The captured value and every dependent Snapshot, Capsule, and proposal are invalidated before any new-risk transmission.

#### EXV-EV-005 — Captured Value Is in the Recorded Input Set
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-003 EXV-INV-005
- **Injection:** Omit the captured value or its provenance/seed/response from the recorded input set.
- **Expected:** The captured value plus provenance is part of the recorded input set so the outcome stays reproducible; the value is evidence, never authority.

#### EXV-EV-006 — Governance Is Owned Upstream
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-003 EXV-INV-006
- **Injection:** Attempt to have this ADR redefine Critical Input classification, currentness, or invalidation, or per-send ordering.
- **Expected:** Classification/currentness/invalidation remain owned by ADR-002-018 (per-send ordering by ADR-002-024); this track defines only the external-value authoring discipline.

### APA — ADR-DEV-004 (Authoring Provenance and Admission)

#### APA-EV-001 — Authoring Provenance Is Mandatory and Minimum-Complete
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-004 APA-INV-001
- **Injection:** Perform an Authoring Act missing actor identity, determining inputs (prompts/context/model/tool versions), source revision, or targeted DSL/Enforcement/config versions.
- **Expected:** Every Authoring Act records the minimum-complete determining input set; an incomplete record is non-conforming.

#### APA-EV-002 — Generated Source Is Source
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-004 APA-INV-002
- **Injection:** Claim exemption from provenance/review because a tool authored the artifact.
- **Expected:** AI-authored artifacts record the same provenance and are reviewed/admitted identically; "a tool wrote it" is not an exemption.

#### APA-EV-003 — Provenance Binds to Identity and Admission
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-004 APA-INV-003
- **Injection:** Record provenance unbound from the Artifact Identity or absent from the ADR-002-029 Source Revision Manifest and admission evidence.
- **Expected:** Authoring Provenance binds to the ADR-DEV-002 Artifact Identity and into the ADR-002-029 admission evidence.

#### APA-EV-004 — Unestablished Provenance Is Inadmissible
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-004 APA-INV-004
- **Injection:** Submit an artifact whose provenance cannot be established for live authoring.
- **Expected:** It fails closed as not admissible.

#### APA-EV-005 — Change Is a Versioned Substitution
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-004 APA-INV-005
- **Injection:** Mutate artifact/DSL/Enforcement/config in place, or revive a superseded generation.
- **Expected:** Any change produces a new Artifact Identity and Release Generation; no in-place mutation and no revival of a superseded generation.

#### APA-EV-006 — Provenance Is Evidence Not Authority or Verification
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-004 APA-INV-006
- **Injection:** Offer a rich provenance record or fluent rationale as admission or as the independent review.
- **Expected:** Recording provenance grants no admission and does not count as the independent review.

#### APA-EV-007 — Scale Does Not Dilute
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-004 APA-INV-007
- **Injection:** Use authorship volume to reduce per-artifact provenance, review, or admission.
- **Expected:** Each artifact retains its full per-artifact provenance, review, and admission regardless of volume.

### AIR — ADR-DEV-005 (Independent Review of AI-Authored Strategies)

#### AIR-EV-001 — Independence Is of the Authority Not the Substrate
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-005 AIR-INV-001
- **Probe:** Inspect whether reviewer independence is defined against the author's authority rather than against being human or tool.
- **Expected:** The reviewer is independent from the author regardless of substrate; substrate is never the requirement.

#### AIR-EV-002 — No Self-Review
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-005 AIR-INV-002
- **Injection:** Submit the author itself, another run/instance of the same author, or a reviewer sharing the author's model or determining prompts/context as the reviewer.
- **Expected:** Each is rejected as non-independent; shared model or determining inputs are the observable common-mode proxy.

#### AIR-EV-003 — Rationale Is a Claim to Be Checked
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-005 AIR-INV-003
- **Injection:** Present the author's rationale or self-asserted results as a passed check.
- **Expected:** Rationale and self-asserted results are recorded as distinct from verified conformance; a fluent rationale cannot substitute for a passed check.

#### AIR-EV-004 — A Tool Reviewer Is Itself Verified Recursively Independent
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-005 AIR-INV-004
- **Injection:** Use an unverified or self-certifying tool reviewer to confer independence.
- **Expected:** A tool reviewer is independent per AIR-INV-002 and is itself a verified artifact whose own verification meets the §7 independence standard; an unverified reviewer confers no independence.

#### AIR-EV-005 — Review Is Not Acceptance or Admission
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-005 AIR-INV-005
- **Probe:** Inspect whether independent review is treated as itself accepting, admitting, or authorizing.
- **Expected:** Independent review produces evidence only toward the RFC-001/VER-002-001 acceptance and ADR-002-029 admission gates; it accepts, admits, and authorizes nothing.

### BFA — ADR-DEV-006 (Bulk and Family Authoring)

#### BFA-EV-001 — The Reviewable and Admissible Unit Is the Individual Artifact
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-006 BFA-INV-001
- **Injection:** Review or admit a bulk/family batch as a single unit.
- **Expected:** Each artifact in the run is independently reviewed and admitted; a batch is never reviewed or admitted as one unit.

#### BFA-EV-002 — No Inheritance Across a Batch
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-006 BFA-INV-002
- **Injection:** Let one artifact inherit another's review, provenance, or admission.
- **Expected:** Each artifact carries its own provenance and admission candidacy; no inheritance across the batch.

#### BFA-EV-003 — Volume Is a Hazard Not a Warrant
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-006 BFA-INV-003
- **Probe:** Inspect whether throughput is treated as quality evidence or as a reduction of per-artifact review.
- **Expected:** Throughput is not quality evidence; scale does not reduce per-artifact review.

#### BFA-EV-004 — Independent Review Per Artifact
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-006 BFA-INV-004
- **Injection:** Substitute a re-run of the author for the per-artifact independent verification.
- **Expected:** Each artifact's conformance is independently verified per ADR-DEV-005; re-running the author is not review.

#### BFA-EV-005 — Batch Tooling Is Assistance Not Authority
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-006 BFA-INV-005
- **Injection:** Treat batch tooling as conferring review, admission, or acceptance.
- **Expected:** Batch tooling confers none of review/admission/acceptance; the unit stays the individual artifact.

#### BFA-EV-006 — Bulk Authoring Grants No Authority
- **Minimum Level:** EV-L0/L1
- **Supports:** ADR-DEV-006 BFA-INV-006
- **Probe:** Inspect whether producing many artifacts is treated as creating authority, admission, or acceptance.
- **Expected:** Producing many artifacts creates no authority, admission, or acceptance.

### SOS — ADR-DEV-007 (Strategy Output Semantics)

#### SOS-EV-001 — No-Action and Explicit Flat Are Distinct First-Class Reproducible
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-007 SOS-INV-001
- **Injection:** Conflate no-action with explicit flat, or represent either as an error, null, or omission.
- **Expected:** No-action and explicit flat are separate, directly expressible, reproducible outcomes; never conflated and never an error/null/omission.

#### SOS-EV-002 — The Atomic Authored Unit Is Explicit
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-007 SOS-INV-002
- **Injection:** Leave the emitted unit (per-instrument target or portfolio vector) to be inferred rather than declared.
- **Expected:** The emitted unit is explicitly declared, not inferred.

#### SOS-EV-003 — No Combined Authority via Aggregation
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-007 SOS-INV-003
- **Injection:** Aggregate proposals into combined authority that bypasses per-Proposal approval, capacity, or isolation.
- **Expected:** No unit aggregates into combined authority; a vector is per-instrument-governed.

#### SOS-EV-004 — Each Target Is Well-Formed and Bounded
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-007 SOS-INV-004
- **Injection:** Emit a target (or vector component) with an unpopulated ADR-002-020 §8 field set, a wildcard/"latest" scope, or no bound Capsule.
- **Expected:** Every target populates the ADR-002-020 §8 field set, has no wildcard/"latest" scope, and binds the exact Capsule.

#### SOS-EV-005 — Output Semantics Grant No Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-007 SOS-INV-005
- **Injection:** Treat representing an outcome as approving, committing capacity, or transmitting.
- **Expected:** Representing any outcome is a Proposal only; it approves nothing, commits no capacity, and transmits nothing.

#### SOS-EV-006 — Vector Component Interdependence Is Declared; Undeclared Is Atomic
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-007 SOS-INV-006
- **Injection:** Emit a portfolio vector with no interdependence declaration and confirm the default; partially approve an atomic vector (reject one per-target) and attempt to realize the approved remainder as a partial position; attempt to satisfy atomicity by unionizing per-target approvals.
- **Expected:** An undeclared vector is atomic; partial approval of an atomic vector yields whole-vector non-realization plus a recorded, first-class strategy-level re-evaluation (never a silent naked partial), and that re-evaluation follows RFC-003 §9.1 (a still-intended reduction is re-expressed as Explicit Flat(s) classified under ADR-002-001 §6); per-target Independent Approval/capacity/consumption remain un-unionized (ADR-002-023, ADR-002-002/021), and the naked-leg consequence is independently bounded by ADR-002-021 aggregate projection.

### DCM — ADR-DEV-008 (Degraded Companion Model)

#### DCM-EV-001 — Degradation Narrows Never Widens
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-008 DCM-INV-001
- **Injection:** Under model degradation, attempt to express an action that widens the action set.
- **Expected:** Under degradation only a more-conservative action or no-action is expressible; no construct widens the action set.

#### DCM-EV-002 — Degraded Output Is Restrictive Not Neutral
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-008 DCM-INV-002
- **Injection:** Express a degraded/UNKNOWN/STALE output as a neutral prior or permissive default.
- **Expected:** A degraded output is expressible only restrictively, never as a neutral prior or permissive default.

#### DCM-EV-003 — The Degraded Decision Is First-Class and Reproducible
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-008 DCM-INV-003
- **Injection:** Emit a degraded decision as an error, null, or silent fallback.
- **Expected:** The degraded decision is a recorded, reproducible outcome with rationale.

#### DCM-EV-004 — No Authority Substitution
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-008 DCM-INV-004
- **Injection:** Have a strategy self-compute a substitute to acquire a degraded model's authority.
- **Expected:** Self-computed risk is not capacity and self-computed hedge is not protective; substitution is rejected.

#### DCM-EV-005 — Degradation Is Scope-Isolated
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-008 DCM-INV-005
- **Injection:** Let one model's degradation widen another strategy's outcome or a safety control.
- **Expected:** Degradation narrows only the affected strategy's own scope; it never widens another strategy or a safety control.

### CEV — ADR-DEV-009 (Containment Escape Vector)

#### CEV-EV-001 — Minimum Set Is the Union of the Boundary
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-009 CEV-INV-001
- **Injection:** Omit any component of the minimum escape-vector set (RFC-008 §11 items 1-16, item-17 escape classes, DCE-INV-003 ambient capabilities, realization-specific surface, three single-layer-failure cases).
- **Expected:** The minimum set is the full union of those sources; an omission is non-conforming.

#### CEV-EV-002 — Attempted Not Assumed
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-009 CEV-INV-002
- **Injection:** Claim unexpressibility for a vector that has no adversarial negative test.
- **Expected:** Each vector is exercised by an adversarial negative test; an un-attempted vector leaves the claim open, not closed.

#### CEV-EV-003 — Versioned With the Surface and Enforcement
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-009 CEV-INV-003
- **Injection:** Change DSL/enforcement/surface-affecting config without re-deriving the set or re-running the suite.
- **Expected:** The set is bound to those versions; any versioned substitution re-derives the set and re-runs the suite before the surface is demonstrated.

#### CEV-EV-004 — Discovered Vectors Are Permanent Regressions
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-009 CEV-INV-004
- **Injection:** Prune a previously discovered escape vector from the set.
- **Expected:** Any discovered vector is added and retained permanently; the set grows monotonically and is never pruned.

#### CEV-EV-005 — Assumptions Are Explicit and Bound the Claim
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-009 CEV-INV-005
- **Injection:** Assert demonstrated containment beyond the vectors and assumptions actually covered.
- **Expected:** The suite's Test Assumptions are recorded and the claim is bounded by the vectors and assumptions actually covered.

#### CEV-EV-006 — Coverage Is Evidence Not Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-009 CEV-INV-006
- **Probe:** Inspect whether passing the suite is treated as acceptance, admission, promotion, or live-readiness.
- **Expected:** Passing the suite is evidence toward review only; it grants no acceptance, admission, promotion, or live-readiness.

### BTE — ADR-DEV-010 (Backtest Admissibility)

#### BTE-EV-001 — A Backtest Is Evidence Toward a Hypothesis Never Live Edge or Proof
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-010 BTE-INV-001
- **Injection:** Present a backtest as demonstrated live edge or proof.
- **Expected:** A backtest is bounded evidence only; demonstrated live edge requires ADR-002-025 restricted-live verification.

#### BTE-EV-002 — Admissible Only Net of Realistic Cost
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-010 BTE-INV-002
- **Injection:** Admit a backtest on optimistic execution cost, slippage, or market-impact assumptions.
- **Expected:** Admissibility is net of realistic cost, slippage, and market impact; optimistic cost assumption disqualifies.

#### BTE-EV-003 — Population and Significance Required
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-010 BTE-INV-003
- **Injection:** Submit a single run or an uncorrected search without sample-size, estimation-error, multiple-testing, selection-bias, or regime treatment.
- **Expected:** Population-based evaluation with those treatments is required; a single run or uncorrected search is inadmissible.

#### BTE-EV-004 — No Look-Ahead
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-010 BTE-INV-004
- **Injection:** Leak future data into any indicator or input relative to the current context timestamp.
- **Expected:** Every indicator/input is bounded by the current context timestamp; any future-data leak disqualifies.

#### BTE-EV-005 — Hermetic Reproducible Assumptions Explicit
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-010 BTE-INV-005
- **Injection:** Run a backtest that is non-hermetic, irreproducible from recorded inputs, or has implicit assumptions.
- **Expected:** The backtest is hermetic and reproducible from recorded inputs with recorded assumptions; otherwise it is void as evidence.

#### BTE-EV-006 — Overfit Is Disqualifying
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-010 BTE-INV-006
- **Injection:** Submit a result tuned to evaluation data, surviving only uncorrected multiple testing, or in-sample-only with no holdout.
- **Expected:** Such results are disqualified.

#### BTE-EV-007 — A Backtest Creates No Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-010 BTE-INV-007
- **Injection:** Treat an admissible/favorable backtest as granting capacity, live-authorization, promotion, acceptance, or as relaxing a safety gate.
- **Expected:** It grants none of those and relaxes no safety gate.

### TAB — ADR-DEV-011 (Test Assumptions and Monitoring Boundary)

#### TAB-EV-001 — Test Assumptions Are Recorded First-Class Artifacts
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-011 TAB-INV-001
- **Injection:** Run a Conformance Test/suite without recording its preconditions, fixtures, platform conditions, and attempted vectors.
- **Expected:** Each suite records its Assumption Record; unrecorded assumptions mean no artifact.

#### TAB-EV-002 — The Claim Is Bounded by Recorded Assumptions
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-011 TAB-INV-002
- **Injection:** Claim coverage beyond a passing suite's recorded assumptions.
- **Expected:** The claim covers only its recorded assumptions; anything unstated is a visible open edge, not implied coverage.

#### TAB-EV-003 — Pre-Deployment Demonstration and Runtime Monitoring Are Distinct
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-011 TAB-INV-003
- **Injection:** Treat RFC-010 pre-deployment testing as a continuous runtime monitor.
- **Expected:** Pre-deployment testing (fixed Artifact Identity) and ADR-002-028 runtime monitoring are separate phases; RFC-010 defines no monitor and does not run continuously.

#### TAB-EV-004 — No Gap Within the Purview
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-011 TAB-INV-004
- **Injection:** Leave a safety-relevant property neither demonstrated nor monitored, or treat monitoring as adequacy where prevention is required.
- **Expected:** Within the joint testing+monitoring purview every safety-relevant property is demonstrated, monitored, or both; an unowned one is a surfaced (never silent) gap, and monitoring is not adequacy where prevention is required.

#### TAB-EV-005 — No Duplication
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-011 TAB-INV-005
- **Injection:** Re-run the pre-deployment demonstration continuously in production, or re-derive the demonstration from monitoring.
- **Expected:** Each phase owns its role; the demonstration does not re-run continuously and monitoring does not re-derive the demonstration.

#### TAB-EV-006 — Assumptions Bridge the Two
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-011 TAB-INV-006
- **Injection:** Leave an assumption whose runtime falsity would invalidate a demonstrated property untracked as a Monitored Assumption.
- **Expected:** Such an assumption is proposed as a Monitored Assumption (an open coordination dependency on ADR-002-028) so its production break is surfaced, not silently trusted.

#### TAB-EV-007 — Recording and Boundary Grant No Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-011 TAB-INV-007
- **Injection:** Treat an Assumption Record or the boundary as conferring acceptance, admission, or live-readiness.
- **Expected:** The record and the boundary are evidence/structure only; they confer none of those.

### RRC — ADR-DEV-012 (Re-Arm Reconciled-State Checklist)

#### RRC-EV-001 — Minimum Reconciled-State Checklist
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-012 RRC-INV-001
- **Injection:** Request re-arm without positively confirming the nine listed items (config, time, live-auth, positions, open orders, safety authority, aggregate risk, single instance, account/venue/critical-input).
- **Expected:** All nine items must be positively confirmed before a re-arm request; a missing confirmation blocks the request.

#### RRC-EV-002 — Any Unreconciled Item Withholds the Request
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-012 RRC-INV-002
- **Injection:** Proceed with an UNKNOWN, unreconciled, conflicting, stale, or ambiguous checklist item.
- **Expected:** Any such item forces the operator to withhold the request; uncertainty narrows, never permits.

#### RRC-EV-003 — The Checklist Is Operator Evidence Not the Grant
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-012 RRC-INV-003
- **Injection:** Treat checklist confirmation as the Re-arm Decision or as lowering/replacing the recovery barrier.
- **Expected:** Confirming the checklist is necessary evidence toward re-arm, not the decision, and does not lower or replace the recovery barrier.

#### RRC-EV-004 — The Barrier Remains the Enforcement Point
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-012 RRC-INV-004
- **Injection:** Attempt to bypass the ADR-002-017 recovery barrier via the checklist.
- **Expected:** Enforcement stays with the recovery barrier (Start Closed, Restriction Before Observation); the checklist sits before it and never bypasses it.

#### RRC-EV-005 — Positively Established and Current
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-012 RRC-INV-005
- **Injection:** Satisfy an item with cached, last-known-good, heartbeat, or once-true-now-stale state.
- **Expected:** Each item is positively established and current at request time; stale/cached state does not satisfy it.

#### RRC-EV-006 — Checklist Confirmation Grants No Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-012 RRC-INV-006
- **Injection:** Treat completing the checklist as committing capacity, issuing Live Authorization, or re-arming.
- **Expected:** Completing the checklist commits no capacity, issues no Live Authorization, and re-arms nothing.

### OPB — ADR-DEV-013 (Operator Boundaries and Containment)

#### OPB-EV-001 — Degraded-Response Is Within Scope; Out-of-Scope Action Routes by Direction
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-013 OPB-INV-001
- **Injection:** Take an out-of-scope action as ordinary operation, or disable/bypass/clear a constitutional control.
- **Expected:** Degraded response stays within granted scope; out-of-scope actions route by direction (authority-increasing/re-arm to dual control; emergency restrictive to break-glass), and disabling a control is never ordinary operation.

#### OPB-EV-002 — Break-Glass Is Restrictive-Only; Authority Increase Is Dual-Control
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-013 OPB-INV-002
- **Injection:** Use break-glass to enlarge authority, or increase authority/re-arm without an independent dual-control quorum.
- **Expected:** Break-glass may only HALT/deny/narrow/request containment; any authority increase or re-arm requires an independent dual-control quorum.

#### OPB-EV-003 — Operator Containment Is Restrictive and Uses Normal Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-013 OPB-INV-003
- **Injection:** Treat operator-invoked containment as creating new authority.
- **Expected:** Operator containment is a restrictive, asymmetric act using normal authority; it narrows only and creates no new authority.

#### OPB-EV-004 — Operator Complements Does Not Pre-empt Incident Governance
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-013 OPB-INV-004
- **Injection:** Have the operator declare, close, or clear an incident or containment.
- **Expected:** The operator complements the independent Safety Authority; incident lifecycle is owned by ADR-002-027 and the operator cannot declare/close/clear it.

#### OPB-EV-005 — Neither Boundary Grants Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-013 OPB-INV-005
- **Injection:** Treat classifying an act as degraded-response or invoking containment as creating authority, capacity, live scope, or protective status.
- **Expected:** Neither creates any of those.

### OBS — ADR-DEV-014 (Operator Observability)

#### OBS-EV-001 — Load-Bearing State Is Observable
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-014 OBS-INV-001
- **Injection:** Hide load-bearing state (authority, capacity, orders, trapped exposure, reconciliation, safety config, degraded mode, evidence completeness), or infer new authority from the surface.
- **Expected:** The operator can observe load-bearing state; the surface presents upstream-owned facts and assigns no new authority.

#### OBS-EV-002 — Observability Is Evidence Not Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-014 OBS-INV-002
- **Injection:** Infer validity or authority from a green dashboard, CONFORMING snapshot, or component health.
- **Expected:** The Observability Surface is evidence, not permission; authority is never inferred from it.

#### OBS-EV-003 — Unknown Is Shown as Unknown
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-014 OBS-INV-003
- **Injection:** Optimistically resolve unknown/unreconciled state to keep operating.
- **Expected:** Unknown state is surfaced as unknown; a visible failure is still a failure.

#### OBS-EV-004 — Withheld Re-Arm Is a First-Class Recorded Outcome
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-014 OBS-INV-004
- **Injection:** Treat declining to re-arm as an absence of action rather than a decision.
- **Expected:** Declining to re-arm is a first-class, recorded, attributable, auditable decision with rationale.

#### OBS-EV-005 — Missed Opportunity Is Acceptable
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-014 OBS-INV-005
- **Probe:** Inspect whether a missed trading opportunity from a withheld re-arm is treated as an unacceptable outcome forcing operation under uncertainty.
- **Expected:** The missed opportunity is an acceptable consequence of unresolved critical uncertainty (a review-verified value stance).

#### OBS-EV-006 — Observability and Withholding Grant No Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-014 OBS-INV-006
- **Injection:** Treat observing state or recording a withheld re-arm as creating authority, committing capacity, or re-arming.
- **Expected:** Neither creates authority, commits capacity, nor re-arms.

### OAS — ADR-DEV-015 (Operator Authority Scope)

#### OAS-EV-001 — Authority Is Scoped on Explicit Dimensions
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-015 OAS-INV-001
- **Injection:** Express operator authority without one of the nine explicit dimensions (account, strategy, instrument, venue, operating mode, software version, safety config, risk capacity, current safety state).
- **Expected:** Authority is expressed along all nine explicit dimensions.

#### OAS-EV-002 — An Act Is Conforming Only Within Current Scope on Every Applicable Dimension
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-015 OAS-INV-002
- **Injection:** Act outside a bounding dimension, or on a dimension whose scope is unknown, stale, or unverifiable.
- **Expected:** An act conforms only if within current valid scope on every bounding dimension; otherwise it is Out-of-Scope, fails closed, and routes to ADR-DEV-013.

#### OAS-EV-003 — Authority Is Explicit Attributable and Does Not Persist
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-015 OAS-INV-003
- **Injection:** Rely on a scope merely because it was valid in the past, or leave it non-attributable/non-time-bounded.
- **Expected:** Scope is explicit, attributable, and time-bounded where appropriate, and does not persist merely because it was once valid.

#### OAS-EV-004 — Revocation Is Immediate and Complete
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-015 OAS-INV-004
- **Injection:** Apply a grace period on revocation, auto-clear a suspended scope, or act on a revoked/expired scope after context change.
- **Expected:** Revocation is immediate and complete with no grace period; suspended scopes do not auto-clear, a revoked/expired scope grants nothing, and changed context invalidates the scope.

#### OAS-EV-005 — Scope Mechanism Is Owned Upstream
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-015 OAS-INV-005
- **Injection:** Attempt to have this track own the per-dimension issuance/revocation mechanism.
- **Expected:** The mechanism is owned by upstream owners (ADR-002-015/007/002, RFC-002/ADR series); this track fixes only the operator-facing discipline.

#### OAS-EV-006 — Expression Grants No Authority
- **Minimum Level:** EV-L1
- **Supports:** ADR-DEV-015 OAS-INV-006
- **Injection:** Treat expressing, observing, or recording a scope as creating authority.
- **Expected:** Expressing a scope creates no authority; authority is issued by its owner and remains revocable.

### DEC-EV — Part-2 Decision-Boundary Conformance

#### DEC-EV-001 — Decision-Framework Boundary Reduces to RFC-002 §9.1
- **Minimum Level:** EV-L0
- **Supports:** DEC-001 (RFC-003 §11 The Decision↔Safety Boundary)
- **Probe:** Inspect RFC-003 §11's 16 prohibitions against the RFC-002 §9.1 authority-separation generalization.
- **Expected:** The boundary list is complete, narrow-only, and reduces to RFC-002 §9.1; the decision framework widens no Part-1 authority.

#### DEC-EV-002 — Execution-Model Boundary Reduces to RFC-002 §9.1
- **Minimum Level:** EV-L0
- **Supports:** DEC-002 (RFC-005 §12 The Execution-Model↔Safety Boundary)
- **Probe:** Inspect RFC-005 §12's prohibitions against RFC-002 §9.1.
- **Expected:** The boundary list is complete, narrow-only, and reduces to RFC-002 §9.1; the execution model widens no Part-1 authority.

#### DEC-EV-003 — Market-Model Venue-Constraint Boundary Reduces to RFC-002 §9.1
- **Minimum Level:** EV-L0
- **Supports:** DEC-003 (RFC-004 §12 The Market-Model↔Safety Boundary; venue/tradability)
- **Probe:** Inspect RFC-004 §12's prohibitions, including venue/tradability deferral to ADR-002-019 (VTG-INV-002), against RFC-002 §9.1.
- **Expected:** The boundary list is complete, narrow-only, and reduces to RFC-002 §9.1; the market model asserts no tradability and widens no Part-1 authority.

#### DEC-EV-004 — Risk-Model Boundary Reduces to RFC-002 §9.1
- **Minimum Level:** EV-L0
- **Supports:** DEC-004 (RFC-006 §13 The Risk-Model↔Safety Boundary)
- **Probe:** Inspect RFC-006 §13's prohibitions against RFC-002 §9.1.
- **Expected:** The boundary list is complete, narrow-only, and reduces to RFC-002 §9.1; the risk methodology feeds the Aggregate Risk Policy without becoming the authority.

#### DEC-EV-005 — Hedge-Model Boundary Reduces to RFC-002 §9.1
- **Minimum Level:** EV-L0
- **Supports:** DEC-005 (RFC-007 §12 The Hedge-Model↔Safety Boundary)
- **Probe:** Inspect RFC-007 §12's prohibitions against RFC-002 §9.1.
- **Expected:** The boundary list is complete, narrow-only, and reduces to RFC-002 §9.1; hedge protective status is established by proof, not by label, and widens no Part-1 authority.

### TEST-EV — RFC-010 Testing-Boundary Conformance

#### TEST-EV-001 — Testing-Boundary Conformance and Non-Authority
- **Minimum Level:** EV-L0
- **Supports:** TEST-001 (RFC-010 §11 The Testing↔Safety Boundary)
- **Probe:** Inspect RFC-010 §11's prohibitions against RFC-002 §9.1 and the pre-deployment/runtime-monitoring boundary.
- **Expected:** Tests produce evidence toward acceptance and grant no authority; pre-deployment proofs do not substitute for runtime monitoring, and the boundary reduces to RFC-002 §9.1.

## 6. Approval Gates by ADR-DEV

Each gate moves its owning ADR-DEV from `Proposed` toward acceptance only when
every required evidence item is in an accepting state (per §3) and independent
review is complete with reviewer provenance recorded per ADR-DEV-005.

### ADR-DEV-001

Requires:

- DCE-EV-001 through DCE-EV-007;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-002

Requires:

- ARI-EV-001 through ARI-EV-006;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-003

Requires:

- EXV-EV-001 through EXV-EV-006;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-004

Requires:

- APA-EV-001 through APA-EV-007;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-005

Requires:

- AIR-EV-001 through AIR-EV-005;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-006

Requires:

- BFA-EV-001 through BFA-EV-006;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-007

Requires:

- SOS-EV-001 through SOS-EV-006;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-008

Requires:

- DCM-EV-001 through DCM-EV-005;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-009

Requires:

- CEV-EV-001 through CEV-EV-006;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-010

Requires:

- BTE-EV-001 through BTE-EV-007;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-011

Requires:

- TAB-EV-001 through TAB-EV-007;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-012

Requires:

- RRC-EV-001 through RRC-EV-006;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-013

Requires:

- OPB-EV-001 through OPB-EV-005;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-014

Requires:

- OBS-EV-001 through OBS-EV-006;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### ADR-DEV-015

Requires:

- OAS-EV-001 through OAS-EV-006;
- independent review (reviewer provenance recorded per ADR-DEV-005).

### Part-2 Decision-Boundary Conformance (DEC-EV)

Supports ratification of RFC-003 through RFC-007. Requires DEC-EV-001 through
DEC-EV-005 and independent review (reviewer provenance recorded per ADR-DEV-005).

### RFC-010 Testing-Boundary Conformance (TEST-EV)

Requires TEST-EV-001 and independent review (reviewer provenance recorded per
ADR-DEV-005).

## 7. Coverage Summary

Invariant → evidence coverage is 91/91 (1:1). Part-2 decision RFCs and RFC-010
map to boundary clusters:

| Owning RFC / ADR-DEV | Requirement / boundary | Evidence |
|---|---|---|
| RFC-003 (Decision Framework) | DEC-001 (§11) | DEC-EV-001 |
| RFC-004 (Market Model) | DEC-003 (§12, venue/tradability) | DEC-EV-003 |
| RFC-005 (Execution Model) | DEC-002 (§12) | DEC-EV-002 |
| RFC-006 (Risk Model) | DEC-004 (§13) | DEC-EV-004 |
| RFC-007 (Portfolio Hedge Model) | DEC-005 (§12) | DEC-EV-005 |
| RFC-008 (Strategy DSL) | §11 boundary | owned by DCE family (ADR-DEV-001) |
| RFC-009 (Agent Guide) | §11 boundary | owned by AIR/APA/BFA families (ADR-DEV-004/005/006) |
| RFC-010 (Testing Strategy) | TEST-001 (§11) + testing discipline | TEST-EV-001 + BTE/TAB families |
| RFC-011 (Operational Guidelines) | §11 boundary | owned by OPB/OBS/OAS/RRC families (ADR-DEV-012/013/014/015) |
| ADR-DEV-001..015 | PFX-INV-0nn | PFX-EV-0nn (91 rows) |

RFC-008, RFC-009, and RFC-011 introduce no separate cluster evidence row: their
§11 boundary lists are owned by the ADR-DEV families named above, which avoids
redundant rows while leaving no invariant uncovered.

The DEC-003 → RFC-004 mapping is deliberate: RFC-000 CONST-007 (Venue Constraints)
reserved `DEC-003`, and RFC-004 owns venue/tradability at the decision layer
(citing VTG-INV-002). DEC identifiers are their own namespace, so the
non-sequential mapping is legitimate. This mapping is flagged as an EV-L0
confirmation item.

## 8. Development-Track Approval Gate

VER-DEV-001 moves from **Proposed** to **Approved for Execution** when:

- every Part-2/3 invariant and each DEC/TEST cluster maps to at least one evidence
  row (this specification);
- reviewer provenance is recorded for each review per ADR-DEV-005;
- Part-1 (VER-002-001) is unaffected and the Part-1 evidence count is unchanged by
  this track.

Approval for execution authorizes no live trading, creates no capacity, and
admits no artifact. All 97 development-track items remain `NOT_IMPLEMENTED` until
executed and independently reviewed.
