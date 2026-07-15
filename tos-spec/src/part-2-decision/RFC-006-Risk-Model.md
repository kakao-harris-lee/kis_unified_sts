# RFC-006 — Risk Model

**Document ID:** RFC-006
**Title:** Risk Model
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

This document defines the **risk model**: the methodology by which risk is
measured, valued, projected, and turned into position sizing and drawdown
control for the decision layer. It gives the Decision Framework (RFC-003) a
disciplined vocabulary for risk measures (VaR, Expected Shortfall), volatility
and correlation, position sizing, leverage, and drawdown, and it co-owns — with
RFC-003 — the constitutional positive-expectancy obligation.

RFC-006 is subordinate to RFC-000, RFC-001, RFC-002, and every accepted
ADR-002-xxx, and it operates within RFC-003. It defines risk *methodology*; it
does **not** redefine the aggregate-risk-capacity mechanics. The Aggregate Risk
Policy, the risk state consistency-cut, the Adverse Scenario Set, the Aggregate
Risk Decision, and — decisively — every mutation of risk capacity are owned by
ADR-002-021 and the Risk Capacity Ledger (ADR-002-002). ADR-002-021 §28
explicitly defers "which valuation, stress, slippage, liquidity, volatility,
correlation, basis, FX, margin, collateral, settlement, option, and assignment
models are approved" to a risk-methodology specification; RFC-006 is that
specification, and it operates strictly inside the constraints ADR-002-021
imposes, above all ARE-INV-005 (No Unproven Benefit).

RFC-006 operates strictly inside the Hard Safety Envelope (RFC-001 §5.20,
SAFE-004): a risk methodology may narrow authority, never widen it. It selects no
specific model instance and fixes no numeric parameter; those are living
configuration and approved policy.

---

## 2. Normative Authority

RFC-006's authority is bounded as follows:

* **RFC-000 — Trading Constitution** governs this document; RFC-006 SHALL NOT
  redefine constitutional intent (RFC-000 §12) and SHALL use RFC-000 §6
  vocabulary verbatim. It co-owns CONST-003 (Positive Expectancy) with RFC-003.
* **RFC-001 — Safety Case** constrains this document; RFC-006 operates strictly
  inside the Hard Safety Envelope (§5.20, SAFE-004) and honors SAFE-012 and
  SAFE-013 (aggregate risk authority and capacity). A risk methodology may
  narrow, never widen, authority.
* **RFC-002 — Architecture** and the **ADR-002-xxx** series own the risk-capacity
  machinery RFC-006 operates within: ADR-002-021 (aggregate risk projection,
  adverse-scenario evaluation, risk-decision integrity) and ADR-002-002 (the Risk
  Capacity Ledger and capacity commitment). RFC-006 supplies methodology to the
  Aggregate Risk Policy; it does not become the risk authority.
* **RFC-003 — Decision Framework** is the layer RFC-006 serves; RFC-006 supplies
  the risk methodology and expectancy apparatus a decision requires, and inherits
  every RFC-003 boundary.
* Where RFC-006 and any higher document appear to conflict, the higher document
  governs and the conflict SHALL be raised through governance.

RFC-006 creates no capacity, authority, risk allocation, configuration, or
transmission permission, and its acceptance authorizes no live operation.

---

## 3. Scope and Non-Scope

This document governs:

* risk-measure methodology: VaR, Expected Shortfall / CVaR, and coherence
  properties;
* volatility, correlation, and the proof standard for netting/hedge/diversification
  benefit;
* position sizing, leverage, and margin methodology;
* drawdown control and capital-preservation methodology;
* the positive-expectancy demonstration methodology (co-owned with RFC-003);
* the boundary between risk methodology and the aggregate-risk-capacity machinery.

This document does not decide:

* risk-capacity allocation, mutation, or release — the Risk Capacity Ledger owns
  that exclusively (ADR-002-002);
* the Aggregate Risk Policy contract, state consistency-cut, Adverse Scenario
  Set, or Aggregate Risk Decision mechanics — ADR-002-021 owns those (RFC-006
  supplies methodology *into* the policy, it does not redefine the policy's
  machinery);
* the Hard Safety Envelope values — those are separately governed (RFC-001 §5.20);
* the decision process itself — RFC-003 owns that;
* the market-state model (RFC-004) or execution model (RFC-005) — RFC-006
  consumes their outputs;
* protective-action classification or hedge construction — ADR-002-001 and
  RFC-007 own those;
* any specific model instance, calibration, or numeric threshold, which are
  living configuration and approved policy.

A risk model that mutates capacity, redefines the aggregate-risk machinery,
widens the Hard Safety Envelope, or hardcodes a numeric bound is non-conforming.

---

## 4. Relationship to Vision and Philosophy

RFC-006 operationalizes principles already established upstream; it inherits, and
does not restate, them.

* **Capital is a finite operating resource** (philosophy §5). Risk methodology
  SHALL treat capital as non-renewable: the objective is to preserve the ability
  to keep operating, not to maximize a single-period return.
* **Aggregate risk is more important than local compliance** (philosophy §18). A
  per-position risk check that passes SHALL NOT excuse an unsafe aggregate
  portfolio state; risk is evaluated at the portfolio level.
* **Positive expectancy must survive reality** (philosophy §29). A claimed edge
  SHALL be evaluated net of realistic cost, slippage, and impact and over a
  population of decisions, never asserted from a favorable backtest or run.
* **Uncertainty reduces authority** (philosophy §8, via RFC-003 §6). Where a risk
  input is missing, stale, or unproven, the methodology SHALL treat the risk as
  its worst credible bound and any claimed benefit as zero.

Where a risk methodology would contradict a Vision or Philosophy principle, it is
non-conforming.

---

## 5. Definitions

RFC-006 reuses canonical terms from RFC-000 §6, RFC-001 §5, RFC-002 §3.1, and the
ADR series, and SHALL NOT introduce synonyms for them. The following
framework-local terms are scoped to risk methodology and are non-authorizing.

* **Risk Measure** — a function from a portfolio's projected outcome distribution
  to a scalar risk quantity (for example VaR or Expected Shortfall). A Risk
  Measure informs the Aggregate Risk Policy; it is not itself capacity or
  authority.
* **Value-at-Risk (VaR)** — the loss quantile of a portfolio's outcome
  distribution over a holding period at a confidence level. A quantile estimate,
  not a loss guarantee.
* **Expected Shortfall (ES / CVaR)** — the expected loss conditional on exceeding
  the VaR threshold; a coherent risk measure.
* **Coherent Risk Measure** — a risk measure satisfying monotonicity,
  sub-additivity, positive homogeneity, and translation invariance
  (Artzner–Delbaen–Eber–Heath, 1999). ES is coherent; VaR is not sub-additive.
* **Position Sizing** — the methodology mapping a decision and its risk estimate
  to a bounded quantity, subordinate to the Aggregate Risk Decision and RCL
  capacity.
* **Volatility Target** — a target portfolio volatility used to scale position
  size inversely to estimated volatility.
* **Drawdown** — the peak-to-trough decline of portfolio equity; a path-based
  risk quantity distinct from a distributional measure.

These terms describe methodology. None grants authority, allocates capacity, or
overrides the Aggregate Risk Decision.

---

## 6. Risk Model Principles

A conforming risk model SHALL satisfy the following. They are methodology
obligations, not enforcement mechanisms; the enforcement points remain owned by
ADR-002-021, ADR-002-002, and the RCL.

1. **Inside the envelope, always.** Every risk methodology output SHALL remain
   within the Hard Safety Envelope (RFC-001 §5.20, SAFE-004); it may narrow
   authority, never widen it.
2. **The model informs; the RCL decides capacity.** A Risk Measure, sizing
   output, or drawdown signal SHALL NOT allocate, mutate, or release capacity;
   only the RCL may (ADR-002-002).
3. **Unproven benefit is zero.** Netting, hedge, diversification, correlation,
   margin-offset, collateral, or liquidity benefit SHALL be treated as zero
   unless positively proven under current policy and evidence (ADR-002-021
   ARE-INV-005).
4. **UNKNOWN is worst-credible.** A missing, stale, or unverifiable risk input
   SHALL be treated at its worst credible bound, never an optimistic default
   (ADR-002-021 ARE-INV-006).
5. **Aggregate dominates local.** Risk SHALL be evaluated at the portfolio /
   aggregate level; a passing per-position check SHALL NOT excuse an unsafe
   aggregate state (philosophy §18; RFC-001 §7.4).
6. **Determinism and reproducibility.** A risk computation SHALL be reproducible
   from recorded inputs and a versioned model; a seeded-stochastic method (for
   example Monte Carlo VaR) carries its recorded seed (RFC-003 §10).

---

## 7. Risk Measures

RFC-006 defines the methodology for measuring portfolio risk; the approved model
instances and confidence levels are configuration bound to the Aggregate Risk
Policy (ADR-002-021 §8).

* **Value-at-Risk.** VaR is the loss quantile over a holding period at a
  confidence level, estimable parametrically, by historical simulation, or by
  Monte Carlo. VaR is an estimate, not a bound: it says nothing about losses
  beyond the quantile, and — being non-sub-additive (Artzner et al., 1999) — it
  can understate the benefit of diversification or penalize it inconsistently.
* **Expected Shortfall.** ES (CVaR) is the expected loss conditional on exceeding
  VaR. It is a coherent risk measure and captures tail severity that VaR omits.
  Where the two disagree, the methodology SHALL prefer the more conservative
  measure for a given scope; ES is the preferred primary measure and VaR, if
  used, is a secondary/interpretability check. The exact choice per product/account
  class is approved configuration.
* **Tail and distributional caveats.** KOSPI200 futures returns are fat-tailed
  and jump-prone around scheduled macro events; a normal-parametric VaR can
  materially understate tail risk and SHALL NOT be relied upon alone for a
  fat-tailed scope. The methodology SHALL represent estimation uncertainty rather
  than present a point estimate as exact.
* **Non-authorizing.** A Risk Measure result is an input to the Aggregate Risk
  Policy and the RCL; it never itself allocates capacity or authorizes an action.

The concrete estimator, confidence level, window, and distributional assumptions
are configuration; RFC-006 fixes the methodology and its conservatism discipline,
not the numbers.

---

## 8. Volatility, Correlation, and Netting

Volatility and correlation feed both risk measurement and position sizing, and
they are the inputs most tempting to over-credit.

* **Volatility estimation.** Realized-volatility and heterogeneous-horizon
  approaches (for example the HAR family) are conforming methods for estimating
  volatility from admitted observations. Where the same volatility estimate is
  also used by RFC-004 for regime classification, the estimate SHALL carry one
  provenance and one uncertainty representation across both uses (RFC-004 §8);
  RFC-006 and RFC-004 SHALL NOT silently diverge on the same underlying quantity.
* **Correlation and netting.** A netting, hedge, diversification, correlation,
  margin-offset, or collateral benefit is **zero unless positively proven** under
  current policy and evidence (ADR-002-021 ARE-INV-005). The proof standard,
  and the exact conditions under which such a benefit may be recognized, are
  governed by ADR-002-021 §13; RFC-006 supplies the methodology consistent with
  that section and SHALL NOT recognize a benefit ADR-002-021 would not.
* **Valuation, margin, liquidity, numerical safety.** Valuation, margin,
  liquidity, and numerical-safety methodology SHALL conform to ADR-002-021 §14,
  including conservative treatment of unknown or unstable inputs and deterministic
  numerical behavior. RFC-006 chooses methodology within those rules; it does not
  relax them.

A correlation matrix, hedge ratio, or diversification assumption that is not
positively proven contributes no risk reduction in this model.

---

## 9. Position Sizing and Leverage

Position sizing maps a decision and its risk estimate to a bounded quantity. It
is always subordinate to the Aggregate Risk Decision (ADR-002-021) and the RCL
capacity commitment (ADR-002-002); sizing proposes, the RCL disposes.

* **Sizing methodologies.** Volatility targeting (scale size inversely to
  estimated volatility), fixed-fractional sizing (risk a bounded fraction of
  equity per decision), and growth-optimal (Kelly) sizing are conforming
  methodologies. Kelly and its fractional variants SHALL be applied conservatively
  — full-Kelly sizing is generally too aggressive under estimation error and a
  fractional or capped form is expected — with the exact fraction as approved
  configuration.
* **Leverage and margin.** For the levered KOSPI200 futures book, margin and
  leverage limits are load-bearing risk controls. Margin methodology treats the
  broker/exchange margin requirement as a living, externally-set input (KRX acts
  as central counterparty), never a hardcoded constant. Leverage limits are
  expressed inside the Hard Safety Envelope.
* **Mixed book.** Where an unlevered cash-equity book and a levered futures book
  share one risk budget, the methodology SHALL make explicit whether risk is
  governed by one portfolio-level measure or by asset-class sub-limits; either is
  conforming, but the choice SHALL be explicit and bound to policy (open question
  §17).
* **Non-authorizing.** A sizing output is a proposed bound. It SHALL NOT create
  capacity or exceed the Aggregate Risk Decision or RCL commitment; the smaller of
  the model's size and the RCL-granted capacity governs.

Concrete sizing fractions, volatility targets, and leverage limits are
configuration inside the Hard Safety Envelope; RFC-006 fixes the methodology, not
the numbers.

---

## 10. Drawdown and Capital Preservation

Capital is a finite operating resource (philosophy §5); preserving the ability to
keep operating dominates single-period return.

* **Drawdown as a distinct control.** Maximum drawdown is a path-based risk
  quantity distinct from a distributional measure (VaR/ES). The methodology MAY
  reduce risk appetite as drawdown deepens (for example scaling size down through
  drawdown bands). Whether drawdown control is a distinct control layered on top
  of, or folded into, an existing consecutive-loss size-reduction mechanism is an
  open question (§17); either is conforming if explicit and bound to policy.
* **Preservation over optimization.** The methodology SHALL prioritize capital
  preservation over return maximization (CONST-002, philosophy §5). A sizing or
  drawdown rule SHALL NOT increase risk appetite purely because recent
  performance was favorable.
* **Halt interaction.** A de-risking action can be blocked mid-execution by a
  venue halt or price-limit event (RFC-004 §11, RFC-005 §10). The methodology
  SHALL treat a de-risking plan as possibly unachievable within its own horizon
  and SHALL fall back to blocking new risk and waiting rather than assuming an
  unwind will complete.
* **Non-authorizing.** A drawdown signal restricts; it never itself releases
  capacity, re-arms, or authorizes an action.

Concrete drawdown bands and preservation thresholds are configuration inside the
Hard Safety Envelope.

---

## 11. Positive Expectancy Methodology

RFC-001 §12 records CONST-003 (Positive Expectancy) as NOT DISCHARGED BY RFC-001
and delegates its demonstration to the Decision Framework; CONST-003's
Traceability names RFC-003 and RFC-006 jointly. RFC-003 §12 accepts the obligation
at the framework level and defers the concrete statistical methodology to RFC-006.
RFC-006 supplies that methodology.

* **Population, not trade.** Positive Expectancy SHALL be evaluated as the
  expected value of the complete decision process over a population of decisions,
  never claimed from a single trade or a favorable run (RFC-000 §6; philosophy
  §29).
* **Net of realistic cost.** Expectancy SHALL be computed net of realistic
  execution cost, slippage, and market impact. RFC-006 consumes the
  execution-cost realism apparatus supplied by RFC-005 §9 and the impact
  representation from RFC-004; it SHALL NOT substitute an optimistic cost
  assumption.
* **Significance and estimation error.** The methodology SHALL account for
  sample size, estimation error, multiple-testing / selection bias, and
  regime dependence, and SHALL represent the uncertainty of an expectancy
  estimate rather than present it as established fact.
* **Backtests are evidence, not proof.** Simulated or historical performance is
  evidence, never demonstrated live edge (philosophy §28). A demonstrated
  positive expectancy for live purposes requires the restricted-live verification
  governed by ADR-002-025; RFC-006 defines the methodology, ADR-002-025 defines
  the live-evidence gate.
* **No expectancy claim creates authority.** A demonstrated or asserted positive
  expectancy is not capacity, live authorization, or scope, and it never relaxes
  a safety gate.

RFC-006 owns the statistical methodology; the live-readiness demonstration is
ADR-002-025's, and the framework-level obligation remains RFC-003 §12's.

---

## 12. Relationship to the Aggregate Risk Architecture

ADR-002-021 already defines, at the architecture layer, the Aggregate Risk Policy
contract (§8), risk dimensions/units/scopes (§10), the Adverse Scenario Set
(§11), projected state and the Adverse Increment (§12), netting/hedge/correlation
rules (§13), valuation/margin/liquidity/numerical safety (§14), the Aggregate Risk
Decision contract (§15), and RCL binding (§16). RFC-006 SHALL NOT redefine,
duplicate, or weaken any of these.

RFC-006's relationship to that machinery is precisely scoped:

* RFC-006 supplies the **methodology** that populates the Aggregate Risk Policy —
  which risk measures, valuation models, scenarios, and sizing rules are approved
  (ADR-002-021 §28 Q4/Q6) — subject to every ADR-002-021 invariant.
* RFC-006 does **not** produce or override an Aggregate Risk Decision, and does
  **not** touch the RCL. The Aggregate Risk Authority issues the decision; only
  the RCL mutates capacity (ADR-002-021 §7, ADR-002-002).
* Every RFC-006 methodology output that would credit a benefit remains bound by
  ARE-INV-005 (No Unproven Benefit) and ARE-INV-006 (UNKNOWN Is Restrictive).

The Aggregate Risk architecture is the mechanism; RFC-006 is the methodology that
fills its approved-model slots without becoming the authority.

---

## 13. The Risk-Model↔Safety Boundary

RFC-006 restates, at the risk-methodology layer, the separation enforced by
RFC-002 §9.1 and inherited from RFC-003 §11. The risk model, and any risk
computation or sizing component, SHALL NOT:

1. allocate, mutate, or release risk capacity, or write to the Risk Capacity
   Ledger — only the RCL may (ADR-002-002; RFC-002 §9.1);
2. issue, override, or substitute for an Aggregate Risk Decision — the Aggregate
   Risk Authority owns it (ADR-002-021 §7, §15);
3. widen, relax, or reinterpret the Hard Safety Envelope or any safety limit; a
   risk methodology may only narrow authority (RFC-001 §5.20, SAFE-004);
4. credit a netting/hedge/diversification/correlation/margin/collateral benefit
   that is not positively proven (ADR-002-021 ARE-INV-005);
5. treat a missing, stale, or unverifiable risk input as an optimistic default
   rather than its worst credible bound (ADR-002-021 ARE-INV-006);
6. approve a proposal, size beyond the Aggregate Risk Decision or RCL commitment,
   or transmit (RFC-003 §11; ADR-002-002);
7. classify a de-risking or hedge action as protective on its own authority
   (RFC-001 §5.25; RFC-007, ADR-002-001 own protective classification);
8. present a VaR/ES value, sizing output, drawdown signal, or expectancy estimate
   as authority to release capacity, re-arm, or bypass a gate (§§7, 9, 10, 11);
9. increase risk appetite because recent performance was favorable (philosophy
   §5; §10);
10. carry a hardcoded risk, margin, leverage, or drawdown threshold in place of
    the living configuration value inside the Hard Safety Envelope (§§9, 10, 14).

The risk model measures, sizes, and informs. It authorizes nothing and mutates no
capacity.

---

## 14. Korean Risk Environment

The system carries an unlevered KRX cash-equity book and a levered KOSPI200
futures book, traded through the KIS broker API. RFC-006 represents the following
risk-environment facts; every numeric value is a **living parameter** sourced from
the current KRX rulebook, the broker-capability profile (ADR-002-004), and
approved configuration inside the Hard Safety Envelope, and SHALL NOT be hardcoded
into this specification.

* **Futures margin.** KOSPI200 futures margin is set by KRX as central
  counterparty and revised periodically; margin is a living external input, never
  a hardcoded constant. Leverage/margin-based limits are especially load-bearing
  for the futures book.
* **Price-limit tail bound.** KRX equity and futures daily price-limit bands cap
  the worst-case single-day move on an unhedged position — a Korea-specific input
  to tail-risk calibration that differs from markets without hard daily limits.
  The methodology uses the band as a living input, not a hardcoded value.
* **Fat tails and jumps.** KOSPI200 futures returns are fat-tailed and jump-prone
  around scheduled macro events; normal-parametric VaR alone can understate tail
  risk (§7).
* **Mixed unlevered/levered book.** The cash-equity and futures books share one
  constitutional risk budget; the methodology makes the one-measure-vs-sub-limit
  choice explicit (§9).
* **Halt-blocked de-risking.** Per-instrument VI, index circuit breakers, and
  price limits can block a de-risking action mid-execution; the methodology
  assumes an unwind may not complete within its horizon (§10).
* **Long/short and product symmetry.** The methodology SHALL treat the standard
  and mini KOSPI200 products by their exact configured multiplier and SHALL NOT
  assume one product's risk parameters for another.

RFC-006 fixes what Korean risk-environment facts the methodology respects and
their provenance. It fixes no numeric value.

---

## 15. Relationship to RFC-003, RFC-004, RFC-005, and RFC-007

RFC-006 sits within the decision layer and shares boundaries with its companions.
The pointers below are non-normative scope markers; RFC-006 SHALL NOT define their
content.

* **RFC-003 — Decision Framework.** RFC-006 co-owns the CONST-003
  positive-expectancy obligation with RFC-003 and supplies the statistical
  methodology RFC-003 §12 deferred to it (§11).
* **RFC-004 — Market Model.** RFC-006 consumes RFC-004's volatility, correlation,
  and market-state representation; where a volatility estimate is shared, it
  carries one provenance (§8).
* **RFC-005 — Execution Model.** RFC-006 consumes RFC-005's execution-cost,
  slippage, and impact realism for the expectancy computation (§11); it does not
  define execution tactics.
* **RFC-007 — Portfolio Hedge Model.** RFC-006 supplies the risk methodology a
  hedge decision uses (hedge ratio, basis risk, correlation), but hedge
  construction and protective classification remain owned by RFC-007 and
  ADR-002-001; a hedge's risk-reduction benefit is subject to ARE-INV-005 (§8).

Until each companion RFC is accepted, its concerns remain open and SHALL NOT be
resolved by risk-model convention.

---

## 16. Requirements Traceability

RFC-006 discharges decision-layer risk-methodology obligations within the bounds
set upstream. This table is an initial allocation and SHALL be refined as the
companion RFCs are accepted.

| Requirement | Discharge in RFC-006 |
|---|---|
| RFC-000 CONST-002 (Capital Preservation) | capital-preservation, drawdown, and conservative-sizing methodology (§§4, 9, 10) — see governance note below |
| RFC-000 CONST-003 (Positive Expectancy; Traceability names RFC-003, RFC-006) | statistical expectancy methodology, co-owned with RFC-003 §12 (§11) |
| RFC-001 §5.20, SAFE-004 (Hard Safety Envelope) | every methodology output stays inside the envelope; narrow-only (§§6, 13) |
| RFC-001 SAFE-012, SAFE-013 (aggregate risk authority and capacity) | methodology feeds the Aggregate Risk Policy without becoming the authority (§12) |
| ADR-002-021 §§8, 10, 11, 13, 14, 28 | methodology populates the approved-model slots ADR-002-021 defers, under all its invariants (§§7, 8, 12) |
| ADR-002-021 ARE-INV-005, ARE-INV-006 | unproven benefit is zero; UNKNOWN is worst-credible (§§6, 8, 13) |
| ADR-002-002 (Risk Capacity Ledger) | methodology never mutates capacity; the RCL alone does (§§6, 13) |
| philosophy §§5, 18, 29 | capital-finite, aggregate-dominates-local, expectancy-survives-reality operationalized (§4) |

**Governance note (CONST-002 traceability gap).** CONST-002's Traceability field
lists only RFC-001 and RFC-005 and omits RFC-006, although capital preservation is
substantively a risk-model concern. RFC-006 does not silently amend the
constitution; this omission is recorded here and in the consistency audit and
SHALL be resolved through governance, not by unilateral edit.

RFC-006 introduces no SAFE-xxx requirement and no numeric bound.

---

## 17. Open Questions

These are open while RFC-006 is a Review Draft and while the companion RFCs are
unwritten. They SHALL NOT be resolved by informal risk-model convention.

1. Which VaR/ES estimation method (parametric, historical, Monte Carlo) is
   approved per product/account class, given fat-tailed, jump-prone KOSPI200
   futures returns?
2. Is ES/CVaR the primary measure (coherent, tail-aware) with VaR as a secondary
   interpretability check, or is VaR retained as primary for some scope?
3. Is one volatility/correlation estimate shared between RFC-004 regime
   classification and RFC-006 sizing, or deliberately decoupled?
4. Is the mixed unlevered-equity / levered-futures book governed by one
   portfolio-level measure or by asset-class sub-limits?
5. Is drawdown control a distinct control layer or folded into the existing
   consecutive-loss size-reduction mechanism?
6. What restricted-live evidence (ADR-002-025) is required to treat a positive
   expectancy as demonstrated rather than backtested?
7. Which exact benefit-recognition proofs (ADR-002-021 §13) does the methodology
   rely on for netting/hedge/correlation, and which broker/product combinations
   cannot support a bounded worst-credible effect and therefore remain non-live
   (ADR-002-021 §28 Q13)?

Unresolved questions reduce, and do not expand, the conforming action set.

---

## 18. Review History

### v0.1 — Initial Draft

* Established RFC-006 as the decision-layer risk model, subordinate to
  RFC-000/001/002 and the ADR-002 series and operating within RFC-003 and inside
  the Hard Safety Envelope.
* Defined risk-measure methodology (VaR, ES/CVaR, coherence), volatility/
  correlation/netting under ARE-INV-005, position sizing and leverage, drawdown
  and capital preservation, and the positive-expectancy methodology co-owned with
  RFC-003 §12 and demonstrated under ADR-002-025.
* Scoped RFC-006 as the methodology that populates ADR-002-021's approved-model
  slots (§28 Q4/Q6) without redefining the aggregate-risk machinery or touching
  the RCL (§12).
* Restated the risk-model↔safety boundary as ten prohibitions consistent with
  RFC-002 §9.1 and RFC-003 §11, including narrow-only Hard Safety Envelope and
  RCL-sole-capacity.
* Represented the Korean/KOSPI200 risk environment as living configuration with
  no hardcoded numeric threshold (§14).
* Recorded the CONST-002 traceability gap (RFC-006 omitted) as a governance item,
  not a unilateral edit (§16).
* Marked scope relationships to RFC-003/004/005/007 without pre-empting them.
* Introduced no SAFE-xxx requirement, numeric bound, or authority.
* Independent adversarial EV-L0 document review passed cleanly with no Critical,
  Major, or Minor finding. All four target properties held: RFC-006 is
  methodology and never the risk authority (no capacity mutation, no Aggregate
  Risk Decision override, no machinery redefinition — §§12, 13); it operates
  narrow-only inside the Hard Safety Envelope (§§6, 13); it credits no unproven
  benefit and treats UNKNOWN as worst-credible (ARE-INV-005/006 — §§6, 8); and
  its positive-expectancy methodology defers live demonstration to ADR-002-025
  without overclaiming (§11). Twelve leak/widening/unproven-benefit/overclaim
  sequences were attempted and blocked, every citation was verified against
  source text, and the boundary was cross-checked as consistent with RFC-003
  §14, RFC-004 §13, and RFC-005 §14 written from the other side. The review is
  EV-L0 only and confers no acceptance or live-readiness.
