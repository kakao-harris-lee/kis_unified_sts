# RFC-003 — Decision Framework

**Document ID:** RFC-003
**Title:** Decision Framework
**Version:** 0.1 Review Draft
**Status:** Review Draft — Decision Framework
**Classification:** Decision-Layer Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Safety Authority:** Constrained by RFC-001 — Safety Case and RFC-002 — Architecture
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-15
**Last Updated:** 2026-07-15

---

## 1. Abstract

This document defines **how trading decisions are made**: the process by which
observed, validated context becomes a proposed trading action. Per RFC-000 §9,
the Constitution defines WHY, the Safety Case defines WHAT SHALL NEVER HAPPEN,
the Architecture RFCs define WHAT EXISTS, and the Decision Framework defines HOW
DECISIONS ARE MADE. RFC-003 occupies exactly that layer and no other.

RFC-003 is subordinate to RFC-000, RFC-001, RFC-002, and every accepted
ADR-002-xxx. It governs the `Interpretation → Decision` portion of the immutable
decision hierarchy (RFC-000 §10) and hands its output to a separately owned
`Approval` stage it does not control. It defines the discipline a decision
process SHALL follow — determinism, reproducibility, uncertainty handling,
rationale, and the exact boundary between proposing and authorizing — without
granting the decision layer any authority to approve, size beyond capacity,
transmit, or arm live operation.

RFC-003 does not select signals, models, indicators, or strategies. It defines
the framework within which any such strategy operates as an untrusted proposer,
so that strategies remain replaceable while the safety model remains durable.

---

## 2. Normative Authority

RFC-003 is a decision-layer specification. Its authority is bounded as follows:

* **RFC-000 — Trading Constitution** governs this document. RFC-003 SHALL NOT
  redefine constitutional intent (RFC-000 §9) and SHALL use RFC-000 §6
  vocabulary verbatim.
* **RFC-001 — Safety Case** constrains this document. No decision process
  defined here may weaken, bypass, or reinterpret any SAFE-xxx requirement.
* **RFC-002 — Architecture** and the accepted **ADR-002-xxx** series define the
  components and contracts RFC-003 operates within. In particular, RFC-002
  §10.2 defines the Decision Service contract that this document elaborates.
* Where RFC-003 and any higher document appear to conflict, the higher document
  governs and the conflict SHALL be raised through governance, not resolved by
  local reinterpretation.

RFC-003 defines process discipline. It creates no capacity, authority,
configuration, or transmission permission, and its acceptance does not authorize
live operation.

---

## 3. Scope and Non-Scope

This document governs:

* the decision pipeline from validated context to a proposed trading action;
* the inputs a decision consumes and the constraints on their use;
* the required structure, determinism, and reproducibility of a decision;
* decision rationale and the evidence a decision leaves behind;
* the exact boundary between the decision layer and every safety-enforcement
  owner;
* decision quality, positive expectancy, and their evidentiary limits;
* strategy replaceability within the framework.

This document does not decide:

* whether a proposal is approved — the Independent Approval Service owns that
  (RFC-002 §10.3, ADR-002-023);
* risk-capacity allocation or mutation — the Risk Capacity Ledger owns that
  (ADR-002-002);
* order construction, transmission, or currentness — ADR-002-020/024 and the
  Broker Egress Gateway own those;
* the concrete market-state model (RFC-004), execution model (RFC-005), risk
  model (RFC-006), or portfolio-hedge model (RFC-007);
* any specific signal, indicator, statistical model, or strategy;
* numeric thresholds, which belong to approved configuration and the
  Verification Profile.

A decision process that reaches beyond this scope is non-conforming regardless
of its predictive merit.

---

## 4. Relationship to Vision and Philosophy

RFC-003 operationalizes several principles already established in the Vision and
Philosophy documents. It does not restate them as new requirements; it inherits
them.

* **No trade is a valid decision** (philosophy §6). Choosing not to act is a
  first-class decision outcome, not the absence of a decision, and SHALL be
  representable, reproducible, and auditable.
* **Prediction has limited authority** (philosophy §7). Signals, models, and
  interpretations are uncertain evidence, never permission. A strong prediction
  SHALL NOT bypass any downstream safety gate.
* **Uncertainty reduces authority** (philosophy §8). As decision context becomes
  less trustworthy, the permissible action set SHALL narrow, never widen.
* **Strategies are replaceable; safety is durable** (philosophy §13). The
  framework treats every strategy as an untrusted proposer whose removal or
  failure SHALL NOT compromise the safety model.
* **Backtests are evidence, not proof** (philosophy §28) and **positive
  expectancy must survive reality** (philosophy §29). Historical or simulated
  performance SHALL NOT be presented as demonstrated live edge.

Where a decision process would contradict a Vision or Philosophy principle, the
process is non-conforming.

---

## 5. Definitions

RFC-003 reuses the canonical terms defined in RFC-000 §6, RFC-001 §5, and
RFC-002 §3.1. It SHALL NOT introduce synonyms for them. The terms most load-
bearing here are reproduced for convenience; the cited source remains normative.

* **Decision Generation** (RFC-000 §6) — the activity of producing a proposed
  trading action from Decision Context and interpretation, prior to Approval.
* **Decision Context** (RFC-000 §6) — the complete, immutable, read-only
  information a decision consumes.
* **Deterministic Decision** (RFC-000 §6) — a decision that, given identical
  Decision Context, always yields the same result; determinism applies to the
  decision process, not to market outcomes.
* **Decision Quality** (RFC-000 §6) — the degree to which a decision was correct
  given the information constitutionally available when it was made, independent
  of its individual outcome.
* **Critical Uncertainty** (RFC-000 §6) — a condition in which the system cannot
  establish, within constitutional bounds, that its Decision Context is
  complete, current, and internally consistent.
* **Positive Expectancy** (RFC-000 §6) — the statistically expected value of the
  complete decision process, evaluated over a population of decisions rather
  than any individual trade.
* **Intent** (RFC-000 §6) — the trading action a decision was constitutionally
  meant to produce, against which any emitted order is validated.
* **Decision Context Capsule** (ADR-002-018 §5.6) — the immutable artifact that
  binds one proposed action's purpose and scope to the exact Critical Input
  Snapshot, trustworthy-time evidence, validation requirements, and invalidation
  generation the decision consumed.

This document introduces two framework-local terms, scoped to the decision layer
and non-authorizing:

* **Proposal** — the decision layer's output: a complete, immutable statement of
  a requested trading action that becomes an **Intent** only after independent
  approval and Intent Registry consumption (ADR-002-023). A Proposal is a
  candidate, not an authorization.
* **Decision Policy** — the deterministic (or seeded-stochastic) function a
  strategy applies to Decision Context to produce a Proposal or an explicit
  no-action outcome. A Decision Policy holds no authority of any kind.

---

## 6. Decision Framework Principles

A conforming decision process SHALL satisfy the following principles. They are
process obligations, not enforcement mechanisms; the enforcement points remain
owned by RFC-002 and the ADR series.

1. **Context precedes decision.** A decision SHALL consume only an immutable,
   validated Decision Context (RFC-000 §11). It SHALL NOT observe, fetch, or
   mutate state during decision generation.
2. **No self-authorization.** A decision produces a Proposal only. It SHALL NOT
   treat its own output as approved, sized, or transmittable.
3. **Uncertainty is restrictive.** Under Critical Uncertainty the only
   conforming outcomes are a more conservative action or no action; the action
   set SHALL NOT expand.
4. **No-action is a decision.** Declining to act SHALL be produced, recorded,
   and reproduced with the same rigor as an action.
5. **Determinism of process.** Given identical Decision Context and identical
   Decision Policy version, the process SHALL yield an identical outcome
   (§10).
6. **Rationale is mandatory.** Every decision SHALL emit a rationale sufficient
   to reconstruct why the outcome followed from the context (§9, §10).
7. **Prediction is evidence, not permission.** No signal strength, confidence
   score, or model output SHALL be treated as authority (§11).

---

## 7. The Decision Pipeline

RFC-000 §10 fixes the immutable decision hierarchy:

```
Observation → Context Construction → Interpretation → Decision → Approval → Execution → Audit
```

RFC-003 governs the **Interpretation → Decision** span. It SHALL NOT bypass,
remove, reorder, or merge any stage of this hierarchy, and it SHALL NOT reach
into the stages it does not own.

Within its span, a conforming decision process proceeds as:

1. **Accept context.** Consume exactly one immutable Decision Context Capsule
   (ADR-002-018). If the Capsule is missing, stale, incomplete, or flagged
   invalid, the process SHALL NOT decide and SHALL produce a restrictive
   no-action outcome bound to that context state.
2. **Interpret.** Apply the Decision Policy to the context to form a view. All
   derived quantities SHALL trace deterministically to admitted context; no
   hidden state, default, or out-of-context fetch is permitted.
3. **Decide.** Select exactly one outcome: a single Proposal, or an explicit
   no-action. The outcome SHALL be within the scope the context and current
   configuration permit.
4. **Bind and emit.** Bind the outcome to the exact Decision Context Capsule
   identity and digest, attach rationale, and emit it to the Approval stage.
   Binding does not create authority.

The process SHALL end at emission. Approval, capacity commitment, authorization,
construction, currentness, and transmission are downstream and separately owned;
the decision process SHALL NOT anticipate, assume, or simulate their outcomes as
permission.

---

## 8. Decision Inputs

A decision consumes Decision Context only. Under RFC-001 §5.3 and SAFE-030
through SAFE-035, any market datum, feature, signal, or reference value that can
change direction, instrument, quantity, price, exposure, risk, margin, venue
eligibility, authorization, or execution behavior is a **Critical Input** and is
governed by ADR-002-018 regardless of what the decision layer calls it.

Accordingly, a conforming decision process:

* SHALL consume Critical Inputs only through the Decision Context Capsule, never
  by direct fetch, cache, or side channel;
* SHALL NOT relabel a value as a "feature," "signal," "derived field," or
  "override" to avoid Critical Input governance (ADR-002-018 §1);
* SHALL treat missing, stale, conflicting, ambiguous, wrongly scaled, or
  unverifiable context as restrictive, never as a permissive default
  (ADR-002-018 CII-INV-005);
* SHALL derive any indicator or feature with complete deterministic or
  explicitly stochastic lineage from admitted observations (ADR-002-018 §10) — a
  stochastic derivation carries the recorded seed or non-determinism declaration
  that ADR-002-018 §10 requires, consistent with the reproducibility discipline
  of §10 (Determinism and Reproducibility) below; the concrete market-state
  model for such derivations is deferred to RFC-004;
* SHALL NOT self-certify the freshness, completeness, or validity of its own
  inputs; that determination is owned by the Context Integrity Service and the
  Independent Approval Service.

The decision layer is a consumer of context, never a definer or authority over
it.

---

## 9. Decision Output: the Proposal

The decision layer's only output is a **Proposal**. Per RFC-002 §10.2 the
Decision Service SHALL identify the intended account, instrument, direction,
quantity, and constraints, and SHALL provide decision rationale. A Proposal
becomes an **Intent** only when the Independent Approval Service approves it and
the Intent Registry consumes it exactly once (ADR-002-023); the decision layer
owns none of those transitions.

A Proposal SHALL be complete and immutable, and SHALL be capable of populating
the Approved Intent Contract field set defined in ADR-002-020 §8, including at
minimum:

* the exact account, instrument, direction, side semantics, and position effect;
* the quantity basis, unit, and maximum quantity;
* order constraints and time-in-force;
* the requested and maximum-credible economic-effect envelope;
* the bound Decision Context Capsule identity and digest;
* the decision rationale and Decision Policy version.

A Proposal SHALL NOT use wildcard account, instrument, side, quantity, unit, or
"latest policy" references (ADR-002-020 §8); such a construction is non-conforming
for live use. The decision layer does not assign Intent identity, does not manage
the Intent lifecycle (ADR-002-005), and SHALL NOT presume that a well-formed
Proposal is or will become authorized.

---

## 10. Determinism and Reproducibility

Determinism applies to the decision *process*, not to market outcomes. A
conforming decision process SHALL be reproducible: given the exact recorded
Decision Context, Decision Policy version, and configuration version, an
independent re-execution SHALL reconstruct the same outcome and rationale.

To achieve this, the process SHALL:

* consume a point-in-time context snapshot and record the exact context
  identity/digest it used, so later reconstruction does not depend on
  re-fetching possibly-revised data;
* version the Decision Policy and any model or configuration artifact it
  applies, and record those versions with the decision;
* record the decision's inputs, outcome, and rationale as evidence separate from
  execution-time records, so an audit can distinguish "the decision was wrong"
  from "the decision was right but poorly executed";
* treat any nondeterminism as a controlled, declared exception: a stochastic or
  externally-sourced component (for example an LLM-derived interpretation) SHALL
  be reproducible from a recorded seed and a recorded response, and the recorded
  artifact SHALL be part of the decision evidence.

Reproducibility is a decision-layer discipline. It does not replace the evidence,
audit, and replay integrity governed by ADR-002-016; it supplies conforming
inputs to it.

---

## 11. The Decision↔Safety Boundary

This section is the load-bearing safety content of RFC-003. It restates, at the
decision-process layer, the separation that RFC-002 §9.1 and the ADR series
enforce. Every item is a hard boundary.

The decision layer, and any strategy or Decision Policy within it, SHALL NOT:

1. approve its own proposal or decision (RFC-000 CONST-005; RFC-002 §10.2);
2. transmit orders or reach a broker route (RFC-002 §10.2, §7.3);
3. reserve, commit, mutate, or release risk capacity, or write to the Risk
   Capacity Ledger (RFC-002 §10.2, §10.5; ADR-002-002);
4. alter, relax, or reinterpret safety limits or safety configuration
   (RFC-002 §10.2; RFC-001 §7.5);
5. arm live mode or issue Live Authorization or Transmission Capability
   (RFC-002 §7.3; ADR-002-007);
6. classify its own action as protective (RFC-002 §9.1; RFC-001 §5.25) — a hedge,
   exit, stop, or emergency label creates no protective status;
7. disable, bypass, or degrade the independent Safety Authority or any
   containment mechanism (RFC-000 CONST-011; RFC-001 §7.6);
8. treat a strong signal or favorable prediction as grounds to bypass risk
   limits, execution checks, account state, venue constraints, live
   authorization, or aggregate controls (philosophy §7);
9. size an action beyond capacity on the assumption that its own risk
   computation is authoritative — the Aggregate Risk Authority and RCL decide
   capacity independently (ADR-002-021, ADR-002-002);
10. self-certify context freshness or validity, or evade Critical Input
    governance by renaming data (ADR-002-018 §1);
11. rely on its own derived facts in place of the Approval Service's independent
    recomputation (RFC-001 SAFE-034; ADR-002-018 §13; ADR-002-023);
12. treat any downstream `ADMISSIBLE`, `CONFORMANT`, `GRANT`, or `APPROVE`
    result as itself constituting capacity, authority, or transmission
    permission (ADR-002-019/020/021/023);
13. use wildcard or "latest policy" scope in any construction it produces
    (ADR-002-020 §8);
14. infer context or market-state validity or source continuity from its own
    component health, uptime, or last-known-good state (ADR-002-018 §9;
    philosophy §16);
15. bypass, remove, or reorder any stage of the RFC-000 §10 pipeline;
16. treat a locally-compliant decision as excusing an unsafe aggregate portfolio
    state (RFC-000 §5; RFC-001 §7.4; philosophy §18).

The single generalizing rule (RFC-002 §9.1): the identity that proposes an
action SHALL NOT also approve it, commit capacity for it, or transmit it. The
Decision Framework occupies only the proposer role.

---

## 12. Decision Quality and Positive Expectancy

RFC-001 §12 records CONST-003 (Positive Expectancy) as **NOT DISCHARGED BY
RFC-001** and delegates its demonstration to the Decision Framework (shared with
RFC-006 — Risk Model). RFC-003 accepts that obligation at the framework level;
the concrete statistical methodology is deferred to RFC-006.

The framework establishes the following, all consistent with philosophy §§28–29:

* **Quality is judged against information available at decision time.** A
  decision's Decision Quality SHALL be assessed on the context it could
  constitutionally have used, independent of the individual outcome. A profitable
  decision made on stale or invalid context is not a high-quality decision.
* **Expectancy is a population property.** Positive Expectancy SHALL be evaluated
  over a population of decisions produced by a Decision Policy, never claimed
  from a single trade or a favorable run.
* **Backtests are evidence, not proof** (philosophy §28). Simulated or historical
  performance SHALL NOT be presented as demonstrated live edge, and SHALL NOT
  substitute for the restricted-live verification governed by ADR-002-025.
* **Expectancy must survive reality** (philosophy §29). A Decision Policy's
  claimed edge SHALL account for realistic execution cost, slippage, and market
  impact (deferred to RFC-005) before it is treated as demonstrated.
* **No expectancy claim creates authority.** Demonstrated or asserted positive
  expectancy is not capacity, live authorization, or scope; it never relaxes a
  safety gate.

RFC-003 defines the obligation and its evidentiary standard. The measurement
apparatus (metrics, populations, significance, cost models) is specified by
RFC-005 and RFC-006 and verified under ADR-002-025.

---

## 13. Strategy Replaceability

Per philosophy §13 and Vision §7.5, a strategy is an untrusted proposer, and the
system's safety and execution integrity SHALL NOT depend on any particular
signal, model, indicator, regime, holding period, or trading style.

The framework therefore requires:

* **Uniform proposer contract.** Every strategy SHALL interact with the system
  only as a producer of Proposals through the pipeline of §7. It SHALL hold no
  privileged path to approval, capacity, configuration, or transmission.
* **Isolation of failure.** A strategy that errors, stalls, or is removed SHALL
  degrade to no-action for its scope; its failure SHALL NOT widen any other
  strategy's authority or weaken any safety control.
* **No shared authority.** Multiple strategies SHALL NOT aggregate their
  Proposals into a combined authority or bypass per-Proposal approval and
  capacity evaluation.
* **Versioned substitution.** Adding, changing, or removing a strategy or
  Decision Policy is a versioned change recorded in decision evidence; it SHALL
  NOT be an in-place, unversioned mutation.

Replaceability is a property of the framework, not of any strategy. The framework
holds; strategies come and go.

---

## 14. Relationship to RFC-004 through RFC-007

RFC-003 is the decision-layer framework. Four companion specifications refine
specific decision concerns within it. RFC-003 defers their content and SHALL NOT
duplicate or pre-empt it; the pointers below are non-normative scope markers.

* **RFC-004 — Market Model.** The concrete model of market state, microstructure,
  volatility, and regime that a decision interprets. It is a consumer of Critical
  Input (ADR-002-018) and SHALL NOT assert tradability, which remains owned by
  ADR-002-019.
* **RFC-005 — Execution Model.** How an approved Intent is executed, including
  cost, slippage, and impact modeling used to make expectancy claims realistic
  (§12). It SHALL NOT redefine canonical command construction (ADR-002-020).
* **RFC-006 — Risk Model.** The risk methodology (valuation, VaR/ES, sizing,
  drawdown) operating strictly inside the Hard Safety Envelope, and the co-owner
  of the CONST-003 positive-expectancy demonstration (§12). It SHALL NOT redefine
  RCL capacity mechanics (ADR-002-002).
* **RFC-007 — Portfolio Hedge Model.** Hedging equity exposure with index
  futures, where a hedge is a protective action whose safety is proven by
  projected aggregate and intermediate effect, never asserted by label
  (ADR-002-001 §6).

Until each companion RFC is authored and accepted, its concerns remain open and
SHALL NOT be resolved by decision-layer convention.

---

## 15. Requirements Traceability

RFC-003 discharges decision-layer obligations that RFC-000 and RFC-001 assign to
the Decision Framework. This table is an initial allocation and SHALL be refined
as RFC-004 through RFC-007 are accepted.

| Requirement | Discharge in RFC-003 |
|---|---|
| RFC-000 CONST-001 (Long-Term Survivability; Traceability names RFC-003) | decision process is subordinate, non-authorizing, and uncertainty-restrictive (§§2, 6, 11) |
| RFC-000 CONST-003 (Positive Expectancy; delegated by RFC-001 §12) | framework-level obligation and evidentiary standard; methodology deferred to RFC-006 (§12) |
| RFC-000 §9 layering; §10 decision hierarchy | RFC-003 confined to Interpretation → Decision, no bypass/reorder (§§1, 7) |
| RFC-000 §11 Decision Context | decision consumes immutable validated context only (§§6, 8) |
| RFC-001 SAFE-030, SAFE-031, SAFE-034 | Critical Input governance, provenance, and independent recomputation honored (§§8, 11) |
| RFC-002 §10.2 Decision Service contract | elaborated as the conforming decision pipeline and Proposal output (§§7, 9) |
| RFC-002 §9.1 authority separation | restated as the decision↔safety boundary (§11) |
| philosophy §§6, 7, 8, 13, 28, 29 | operationalized as framework principles (§§4, 6, 12, 13) |
| RFC-000 §12 narrow-only; §11 Decision↔Safety Boundary | registered as DEC-001 (VER-DEV-001, EVIDENCE-REGISTER-DEV; evidence DEC-EV-001); widens no Part-1 authority |

RFC-003 introduces no SAFE-xxx requirement and no numeric bound. It relies
entirely on the enforcement points already defined upstream.

**CONST-003 composite-discharge note.** RFC-003 §12 accepts the CONST-003
positive-expectancy obligation at the framework level only; it does not and cannot
declare CONST-003 discharged in full. The named composite discharge is RFC-003 §12
(framework obligation) → RFC-006 §11 (methodology) → ADR-002-025 (live-readiness
demonstration, RLP-EV-001 through RLP-EV-012), completable only via the
ADR-002-025 restricted-live evidence (RFC-000 CONST-003 Traceability).

---

## 16. Open Questions

These questions are open while RFC-003 is a Review Draft and while RFC-004
through RFC-007 are unwritten. They SHALL NOT be resolved by informal decision-
layer convention.

1. Is the atomic decision unit a per-instrument target position or a
   portfolio-wide target vector, and does the framework support both?
2. What is the minimum decision-evidence granularity required to reconstruct a
   decision's rationale long after the fact without any live service?
3. For a seeded-stochastic or externally-sourced interpretation component, is
   "reproducible from a recorded seed and response" a sufficient reproducibility
   standard, or is stricter determinism required for specific action classes?
4. How are "no-action / hold" and "explicit flat (target = 0)" represented so
   that both are distinct, reproducible, and auditable?
5. Which concrete market-state, execution-cost, risk, and hedge models
   (RFC-004–007) supply the inputs and the expectancy-realism apparatus this
   framework requires?
6. How does the framework represent a decision made when a companion model
   (market, risk, hedge) is itself degraded or unavailable?

Unresolved questions reduce, and do not expand, the conforming action set.

---

## 17. Review History

### v0.1 — Initial Draft

* Established RFC-003 as the decision-layer framework subordinate to
  RFC-000/001/002 and the ADR-002 series.
* Defined the conforming decision pipeline over the RFC-000 §10 Interpretation →
  Decision span, the Proposal output contract, and determinism/reproducibility
  discipline.
* Restated the decision↔safety boundary as sixteen hard prohibitions consistent
  with RFC-002 §9.1.
* Accepted the CONST-003 positive-expectancy obligation at framework level and
  deferred its methodology to RFC-006.
* Marked scope relationships to RFC-004 through RFC-007 without pre-empting them.
* Introduced no SAFE-xxx requirement, numeric bound, or authority.
* Independent adversarial EV-L0 document review passed with no Critical or Major
  finding; twelve authority-leak sequences were attempted and found blocked by
  §11. One Minor drafting inconsistency was resolved: §8's derived-input lineage
  now reproduces ADR-002-018 §10's "deterministic or explicitly stochastic"
  language, aligning it with the §10 reproducibility carve-out. The review is
  EV-L0 only and confers no acceptance or live-readiness.
* During the RFC-004 review, §11 item 14's health-is-not-validity citation was
  corrected from ADR-002-018 CII-INV-013 (recovery non-revival) to ADR-002-018
  §9 (source continuity is not inferred from health), keeping RFC-003 and RFC-004
  consistent on the same rule.
