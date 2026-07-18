# RFC-007 — Portfolio Hedge Model

**Document ID:** RFC-007
**Title:** Portfolio Hedge Model
**Version:** 0.1 Review Draft
**Status:** Review Draft — Decision Framework
**Classification:** Decision-Layer Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Safety Authority:** Constrained by RFC-001 — Safety Case and RFC-002 — Architecture
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-15
**Last Updated:** 2026-07-17

---

## 1. Abstract

This document defines the **portfolio hedge model**: the methodology for hedging
equity exposure with index futures — hedge-ratio estimation, basis risk, hedge
effectiveness, and roll/expiry management — for the decision layer. It gives the
Decision Framework (RFC-003) a disciplined way to propose a hedge, using the risk
methodology of RFC-006 and the market state of RFC-004.

RFC-007 is subordinate to RFC-000, RFC-001, RFC-002, and every accepted
ADR-002-xxx, and it operates within RFC-003. Its single most important property:
**a hedge is a protective action, and a protective action is established by
proof, not by label.** A sell, an exit, a "hedge" name, or a correlation with an
existing position is non-authoritative (ADR-002-001 §6). Whether a proposed hedge
is actually protective is decided exclusively by the Protective Action Controller
under ADR-002-001's Final-State and Intermediate-State tests; RFC-007 supplies the
hedge methodology those tests evaluate, never the classification itself.

RFC-007 mutates no capacity, issues no protective classification, and reaches no
broker route. It selects no specific hedge instrument beyond the KOSPI200 futures
the system already trades, and fixes no numeric parameter; hedge ratios,
estimation windows, and roll timing are living configuration inside the Hard
Safety Envelope.

---

## 2. Normative Authority

RFC-007's authority is bounded as follows:

* **RFC-000 — Trading Constitution** governs this document; RFC-007 SHALL NOT
  redefine constitutional intent (RFC-000 §9) and SHALL use RFC-000 §6
  vocabulary verbatim. CONST-012 (Safe Operational State) is the constitutional
  root of protective-action authorization.
* **RFC-001 — Safety Case** constrains this document; SAFE-002, SAFE-040, and
  SAFE-043 govern protective action and degraded operation, and no hedge
  methodology may weaken them. RFC-007 operates inside the Hard Safety Envelope
  (SAFE-004).
* **RFC-002 — Architecture** and the **ADR-002-xxx** series own the protective
  machinery RFC-007 operates within: ADR-002-001 (protective-action
  classification, envelope, and reserved protective capacity), ADR-002-011
  (protective replacement and protection-gap control), ADR-002-002 §19 (reserved
  protective capacity in the RCL), and ADR-002-021 (aggregate-risk and
  netting/hedge-benefit rules).
* **RFC-003 — Decision Framework** is the layer RFC-007 serves; a hedge is a
  proposed action produced through RFC-003 and inherits every RFC-003 boundary.
  RFC-007 uses RFC-004 (market state) and RFC-006 (risk methodology).
* Where RFC-007 and any higher document appear to conflict, the higher document
  governs and the conflict SHALL be raised through governance.

RFC-007 creates no capacity, protective classification, authority, configuration,
or transmission permission, and its acceptance authorizes no live operation.

---

## 3. Scope and Non-Scope

This document governs:

* hedge-ratio methodology (beta hedge, minimum-variance hedge ratio, cross-hedge);
* basis risk, correlation breakdown, and hedge-effectiveness methodology;
* roll and expiry management for a maintained futures hedge;
* how a hedge is presented for protective-action classification;
* the hedge's dependence on reserved protective capacity;
* the boundary between hedge methodology and every safety-enforcement owner.

This document does not decide:

* whether an action is protective — the Protective Action Controller owns that
  under ADR-002-001 §6 (RFC-007 supplies the methodology it evaluates, never the
  verdict);
* protective-order replacement, cancellation authority, or protection-gap
  control — ADR-002-011 owns those;
* reserved-protective-capacity mechanics or any capacity mutation — ADR-002-002
  §19 and the Risk Capacity Ledger own those;
* aggregate-risk evaluation or the netting/hedge-benefit proof standard —
  ADR-002-021 owns that (RFC-007 conforms to ARE-INV-005);
* the decision process (RFC-003), market model (RFC-004), execution (RFC-005), or
  general risk methodology (RFC-006);
* venue tradability or session state (ADR-002-019);
* any specific hedge instrument beyond the system's KOSPI200 futures, or any
  numeric parameter (hedge ratios, windows, roll timing), which are living
  configuration inside the Hard Safety Envelope.

A hedge model that classifies its own action as protective, mutates capacity,
credits an unproven hedge benefit, or hardcodes a numeric parameter is
non-conforming.

---

## 4. Relationship to Vision and Philosophy

RFC-007 operationalizes principles already established upstream; it inherits, and
does not restate, them.

* **Safe state is exposure-aware** (philosophy §10). A hedge does not make a
  position "safe"; safety is judged by projected aggregate exposure. A hedge that
  reduces directional risk while increasing gross exposure, leverage, margin,
  basis, liquidity, or concentration risk is not automatically safe.
* **"Hedge means safe" is an anti-pattern** (philosophy §39.5). An action SHALL
  NOT bypass any control because it is labeled protective; RFC-007 SHALL NOT
  encode label-based protection.
* **Safe operational state** (RFC-000 CONST-012). A bounded protective action may
  be authorized only when its projected aggregate effect reduces constitutional
  risk and violates no safety limit — the constitutional basis for every hedge.
* **Aggregate risk dominates local compliance** (philosophy §18, via RFC-006). A
  hedge is judged at the portfolio/aggregate level, not by the delta of one leg.

Where a hedge methodology would contradict a Vision or Philosophy principle, it is
non-conforming.

---

## 5. Definitions

RFC-007 reuses canonical terms from RFC-000 §6, RFC-001 §5, RFC-002 §3.1, and the
ADR series (notably Protective Action, RFC-001 §5.25), and SHALL NOT introduce
synonyms for them. The following framework-local terms are scoped to hedge
methodology and are non-authorizing.

* **Hedge** — a proposed position, normally in index futures, intended to reduce
  a portfolio's market exposure. A hedge is a *proposed* action whose protective
  status is decided by ADR-002-001 §6; the term grants no protective status by
  itself.
* **Beta Hedge** — a hedge sized by the portfolio's beta to the index underlying
  the future: notionally, contracts ≈ −β · portfolio value / (futures price ×
  contract multiplier). A sizing methodology, not an authorization.
* **Minimum-Variance Hedge Ratio** — the variance-minimizing hedge ratio
  h\* = Cov(ΔS, ΔF) / Var(ΔF), i.e. the regression slope of spot changes on
  futures changes; the cross-hedge generalization when the book is not
  index-representative.
* **Basis Risk** — the risk that the hedge instrument does not move in lock-step
  with the hedged exposure (imperfect correlation, and futures-to-spot basis
  convergence along an unpredictable path).
* **Hedge Effectiveness** — a measure (for example the regression R²) of how much
  exposure variance a hedge removes; an estimate with uncertainty, never a
  guarantee.
* **Roll** — replacing an expiring futures contract with the next to maintain a
  hedge past expiry; a protective-replacement workflow under ADR-002-011.

These terms describe methodology. None grants protective status, allocates
capacity, or authorizes transmission.

---

## 6. Hedge Model Principles

A conforming hedge model SHALL satisfy the following. They are methodology
obligations, not enforcement mechanisms.

1. **A hedge is not protective by label.** A sell, exit, hedge name, reduce-intent,
   operator description, or correlation with a position is non-authoritative
   (ADR-002-001 §6); only the Protective Action Controller classifies (§10).
2. **Judged by projected aggregate effect.** A hedge is evaluated by its projected
   aggregate risk across all governed dimensions, not by the delta of one leg
   (philosophy §10; RFC-006 §6).
3. **Unproven hedge benefit is zero.** A correlation, basis, netting, or
   diversification benefit is zero unless positively proven under current policy
   and evidence (ADR-002-021 ARE-INV-005).
4. **A hedge can worsen other dimensions.** Reducing delta may worsen margin,
   basis, liquidity, concentration, or gap risk; such a hedge MAY be denied
   (ADR-002-001 §6.3).
5. **Roll is protective replacement.** Maintaining a hedge across expiry is a
   protection-gap-controlled workflow, never an ordinary cancel-then-submit
   (ADR-002-011).
6. **The model proposes; it does not authorize.** A hedge ratio, effectiveness
   estimate, or roll plan creates no protective status, capacity, or transmission
   permission.

---

## 7. Hedging Methodology

RFC-007 defines the methodology for sizing and maintaining a futures hedge of
equity exposure; the approved model instance, estimation window, and parameters
are configuration inside the Hard Safety Envelope.

* **Beta hedge.** For an index-representative book, the hedge is sized by the
  portfolio's beta to the index underlying the future, scaled by the futures
  notional per contract (price × contract multiplier). Because the standard and
  mini KOSPI200 products differ in multiplier, the methodology SHALL size against
  the exact configured product's multiplier and SHALL NOT assume one product's
  parameters for another.
* **Minimum-variance / cross-hedge.** When the book is not proportionally
  representative of the index (sector-concentrated, includes non-index names, or a
  differently weighted subset), the hedge is a cross-hedge; the variance-minimizing
  ratio h\* = Cov(ΔS, ΔF)/Var(ΔF) is the textbook-correct sizing rather than a
  naive one-for-one notional hedge. Whether the ratio is static (beta-based),
  rolling/regression-estimated, or dynamically re-estimated, and over what window,
  is approved configuration (open question §16).
* **Fractional contracts.** Because futures trade in whole contracts, a hedge
  ratio rarely lands on an integer; the methodology SHALL make the rounding rule
  and the resulting residual basis explicit rather than silently over- or
  under-hedging.
* **Non-authorizing.** A computed hedge size is a proposal. It is subordinate to
  the Aggregate Risk Decision, the RCL commitment (RFC-006 §9), and the
  protective-action classification (§10); the model never sizes a hedge into
  existence.

Concrete betas, ratios, windows, and rounding rules are configuration; RFC-007
fixes the methodology, not the numbers.

---

## 8. Basis Risk and Hedge Effectiveness

A hedge reduces exposure only to the extent its instrument tracks the hedged
book, and that tracking is never perfect.

* **Basis risk is first-class.** The methodology SHALL represent basis risk — from
  cross-hedge imperfect correlation and from futures-to-spot basis convergence —
  as an explicit modeled quantity, not an ignored residual. A hedge that removes
  directional risk while leaving large basis risk has not made the book safe.
* **Effectiveness is an estimate.** Hedge effectiveness (for example regression
  R²) is an uncertain estimate over a historical window; it SHALL be represented
  with its uncertainty and SHALL NOT be presented as a guaranteed variance
  reduction.
* **Unproven benefit is zero.** Any correlation, basis-stability, or
  diversification benefit the hedge is credited with SHALL be positively proven
  under current policy and evidence; otherwise it is zero (ADR-002-021
  ARE-INV-005). Correlation breakdown and gap risk SHALL be treated at their worst
  credible bound when unproven (ARE-INV-006).
* **Consistent risk inputs.** The volatility and correlation estimates a hedge
  uses SHALL be the RFC-006 / RFC-004 estimates with their single provenance
  (RFC-004 §8, RFC-006 §8); the hedge model SHALL NOT introduce a divergent,
  more-optimistic correlation for the same instruments.

A hedge whose effectiveness or basis behavior is unproven contributes no risk
reduction in this model.

---

## 9. Roll and Expiry Management

A futures hedge maintained past a contract's expiry must be rolled. Because both
the old and the new contract can be economically live during the transition, a
roll is a **protective-replacement workflow governed by ADR-002-011**, not an
ordinary cancel-then-submit.

* **Both legs live.** During a roll the system SHALL account for the worst
  credible intermediate state — both old and new hedge legs live and fillable, or
  the old leg gone while the new leg is not yet effective (a protection gap) — and
  reserve for it before transmitting any roll step (ADR-002-011 §1).
* **No premature discharge.** An old hedge leg remains potentially live until
  Final Quantity Proof; a cancel ACK, timeout, or lease expiry is not Final
  Quantity Proof (ADR-002-011). The roll SHALL NOT assume the old leg is gone.
* **Roll policy.** The roll trigger (calendar-day relative to the KOSPI200
  second-Thursday expiry cycle, volume-based, or explicit operator action), the
  roll-cost budget, and whether the roll is staged or all-at-once are approved
  configuration; RFC-007 fixes that a roll is protection-gap-controlled, not the
  trigger values.
* **Roll cost and basis.** A roll executes at whatever basis prevails at roll
  time, which need not equal the basis at hedge initiation; the methodology SHALL
  treat roll cost and roll-time basis as risks, consistent with §8.

The roll workflow's transitions, capacity, and cancellation authority remain owned
by ADR-002-011, the RCL, and the Cancellation Arbiter; RFC-007 supplies the
hedge-maintenance methodology within them.

---

## 10. Hedge as a Protective Action

This section is load-bearing. Whether a proposed hedge is protective is decided
exclusively by the Protective Action Controller under ADR-002-001 §6; RFC-007
never classifies its own action.

* **Label is non-authoritative.** Per ADR-002-001 §6, "a strategy flag, sell
  direction, exit or hedge name, reduce-position intent, operator description, or
  correlation with an existing position is non-authoritative." A hedge is a
  request for protection, independently classified (ADR-002-001 §5).
* **Final-State Test.** The hedge's intended final state SHALL satisfy projected
  conservative aggregate post-action risk < current conservative aggregate risk,
  for the relevant dimensions, while remaining inside the Hard Safety Envelope
  (ADR-002-001 §6.1). The hedge methodology supplies the projected risk inputs;
  the Controller applies the test.
* **Intermediate-State Test.** The final-state test is necessary but not
  sufficient. For every credible partial-fill fraction, leg-failure,
  acknowledgement loss, cancel/replace race, late fill, basis movement, liquidity
  deterioration, and margin revaluation, worst-case conservative risk after the
  intermediate state SHALL be ≤ the risk of taking no protective action
  (ADR-002-001 §6.2). If this cannot be demonstrated, the hedge is classified
  risk-increasing and denied in degraded mode.
* **A hedge may be denied.** A hedge that reduces delta but materially worsens
  margin, basis, liquidity, concentration, or another governed dimension MAY be
  denied (ADR-002-001 §6.3). RFC-007 SHALL surface those dimension effects so the
  Controller can evaluate them; it SHALL NOT hide them to secure classification.
* **Protective envelope.** Even a classified-protective hedge remains bounded by
  the Protective Action Envelope (ADR-002-001 §7), subordinate to the Hard Safety
  Envelope.

RFC-007 gives the Protective Action Controller a complete, honest risk picture. It
does not, and cannot, classify the hedge itself.

---

## 11. Reserved Protective Capacity

A hedge and its roll consume real resources — risk capacity, margin, broker
order-rate, and cancel capacity — precisely when the system may be degraded.
RFC-007 depends on, and never creates, the reserved protective capacity governed
by ADR-002-001 §4 and ADR-002-002 §19.

* **Capacity is reserved, not conjured.** A hedge or roll SHALL execute only
  against pre-committed protective capacity under a valid Protective Lease
  (ADR-002-001 §5); the hedge model SHALL NOT enlarge aggregate authority or
  mutate the RCL.
* **Priority is not reservation.** Scheduling priority for a hedge is not reserved
  capacity; a resource is guaranteed only when its reservation mechanism and
  failure independence are demonstrated (ADR-002-001 §4.6). The hedge model SHALL
  NOT treat priority as a protective guarantee.
* **Roll needs overlap capacity.** Because a roll can have both legs live, its
  capacity requirement includes the overlap; the methodology SHALL request roll
  capacity for the worst credible both-legs-live state (ADR-002-011 §1), not the
  net.
* **Degraded-mode dependence.** In degraded mode a hedge is permitted only as a
  bounded protective action within reserved capacity (ADR-002-001 §8); the model
  SHALL NOT assume ordinary capacity is available to hedge.

The RCL reserves and commits; RFC-007 sizes a hedge to fit within what is
reserved and never beyond it.

---

## 12. The Hedge-Model↔Safety Boundary

RFC-007 restates, at the hedge-methodology layer, the separation enforced by
RFC-002 §9.1 and inherited from RFC-003 §11. The hedge model, and any hedge-sizing
or roll component, SHALL NOT:

1. classify its own action as protective, or treat a hedge label, sell direction,
   or correlation as protective status (ADR-002-001 §6; RFC-001 §5.25);
2. reserve, commit, mutate, or release risk or protective capacity, or write to
   the Risk Capacity Ledger (ADR-002-002 §19; ADR-002-001 §5);
3. authorize, reduce, or remove required protection, or perform a roll as an
   ordinary cancel-then-submit — the Cancellation Arbiter and ADR-002-011 own
   protective replacement;
4. credit a hedge, correlation, basis, or diversification benefit that is not
   positively proven (ADR-002-021 ARE-INV-005), or treat correlation breakdown
   optimistically (ARE-INV-006);
5. hide or understate a hedge's adverse effect on margin, basis, liquidity,
   concentration, or gap risk to secure a protective classification
   (ADR-002-001 §6.3);
6. treat scheduling priority as reserved protective capacity (ADR-002-001 §4.6);
7. widen, relax, or reinterpret the Hard Safety Envelope or the Protective Action
   Envelope; a hedge remains subordinate to both (ADR-002-001 §7, RFC-001 §5.20);
8. approve a proposal, size beyond the Aggregate Risk Decision or RCL commitment,
   or transmit (RFC-003 §11; RFC-006 §13; ADR-002-002);
9. assume an old hedge leg is discharged before Final Quantity Proof, or that a
   roll leaves no protection gap (ADR-002-011);
10. carry a hardcoded hedge ratio, roll trigger, or margin/leverage threshold in
    place of the living configuration value inside the Hard Safety Envelope
    (§§7, 9, 13).

The hedge model sizes and maintains a proposed hedge and hands an honest risk
picture to the Protective Action Controller. It classifies nothing, mutates no
capacity, and authorizes nothing.

---

## 13. Korean Hedge Environment

The system hedges a KRX equity book with KOSPI200 index futures through the KIS
broker API. RFC-007 represents the following environment facts; every numeric
value is a **living parameter** sourced from the current KRX rulebook, the
broker-capability profile (ADR-002-004), and approved configuration inside the
Hard Safety Envelope, and SHALL NOT be hardcoded into this specification.

* **KOSPI200 futures as the hedge instrument.** KOSPI200 futures are the standard,
  most liquid instrument for hedging a diversified Korean large-cap book. The
  standard and mini products differ in contract multiplier; the methodology sizes
  against the exact configured product (§7) and treats the multiplier as a living
  parameter.
* **Cross-hedge basis for non-representative books.** A book concentrated in
  sectors, including KOSDAQ names, or a differently weighted KOSPI200 subset is a
  cross-hedge with nontrivial basis risk; the minimum-variance ratio applies (§7,
  §8). The index's free-float weighting methodology and its revisions are external
  facts the estimation consumes, not RFC-007 content.
* **Roll cycle.** KOSPI200 futures follow a defined expiry cycle (a second-Thursday
  monthly/quarterly convention); the roll is protection-gap-controlled (§9) with
  timing drawn from configuration.
* **Per-leg halt imbalance.** Equity and futures legs are independently subject to
  KRX price limits and volatility interruptions; a hedge can become temporarily
  unbalanced when one leg is halted and the other trades — a Korea-specific
  operational risk the methodology SHALL represent (consistent with RFC-004 §11,
  RFC-005 §10).
* **Night-session-disabled overnight gap (binding).** The KOSPI200 futures night
  session is disabled by operator policy, so a futures hedge is only actively
  maintainable during the KST day session. Overnight and global-event equity gap
  risk is therefore NOT hedgeable via the futures leg outside day-session hours.
  RFC-007 SHALL treat this as a binding constraint: it SHALL NOT assume an
  overnight hedge adjustment is available, and the unhedged overnight gap SHALL be
  surfaced as a residual risk (or addressed by a compensating control such as
  pre-close de-risking), not silently assumed away (open question §16).

RFC-007 fixes what Korean hedge-environment facts the methodology respects and
their provenance. It fixes no numeric value.

---

## 14. Relationship to RFC-003, RFC-004, RFC-005, and RFC-006

RFC-007 sits within the decision layer and shares boundaries with its companions.
The pointers below are non-normative scope markers; RFC-007 SHALL NOT define their
content.

* **RFC-003 — Decision Framework.** A hedge is a proposed action produced through
  RFC-003 and inherits every RFC-003 boundary; a hedge proposal is not
  self-authorizing.
* **RFC-004 — Market Model.** RFC-007 consumes RFC-004's market state — basis,
  correlation, volatility — for hedge sizing and effectiveness, with one shared
  provenance (§8).
* **RFC-005 — Execution Model.** A hedge order and its roll execute through
  RFC-005 (slicing, benchmark, halt handling); RFC-007 supplies the hedge to
  execute, not the execution tactics.
* **RFC-006 — Risk Model.** RFC-007 uses RFC-006's risk methodology (correlation,
  volatility, sizing, ARE-INV-005 benefit proof); a hedge's risk-reduction claim
  is subject to that methodology and is not credited unless proven (§8).

Until each companion RFC is accepted, its concerns remain open and SHALL NOT be
resolved by hedge-model convention.

---

## 15. Requirements Traceability

RFC-007 discharges decision-layer hedge-methodology obligations within the bounds
set upstream. This table is an initial allocation and SHALL be refined as the
companion RFCs are accepted.

| Requirement | Discharge in RFC-007 |
|---|---|
| RFC-000 CONST-012 (Safe Operational State) | a hedge is authorized only when its projected aggregate effect reduces risk and violates no limit — via ADR-002-001 §6 classification, not by label (§§4, 10) |
| RFC-001 §5.25 (Protective Action) | a hedge's protective status is established by proof, not by hedge name (§§6, 10) |
| RFC-001 SAFE-002, SAFE-040, SAFE-043 | protective/degraded hedge behavior conforms to the protective-action requirements (§§10, 11) |
| RFC-001 §5.20, SAFE-004 (Hard Safety Envelope) | hedge and Protective Action Envelope stay inside the Hard Safety Envelope (§§10, 12) |
| ADR-002-001 §§4–7 | classification tests, protective envelope, and reserved capacity honored, not redefined (§§10, 11) |
| ADR-002-011 | roll is protection-gap-controlled replacement; no premature discharge (§9) |
| ADR-002-002 §19 | reserved protective capacity is consumed, never mutated (§§11, 12) |
| ADR-002-021 ARE-INV-005/006 | unproven hedge/correlation benefit is zero; breakdown is worst-credible (§§6, 8) |
| philosophy §§10, 18, 39.5 | exposure-aware safety, aggregate-dominates-local, no "hedge means safe" (§§4, 6) |
| RFC-000 §12 narrow-only; §12 Hedge-Model↔Safety Boundary | registered as DEC-005 (VER-DEV-001, EVIDENCE-REGISTER-DEV; evidence DEC-EV-005); widens no Part-1 authority |

RFC-007 introduces no SAFE-xxx requirement and no numeric bound.

---

## 16. Open Questions

These are open while RFC-007 is a Review Draft and while the companion RFCs are
accepted only in part. They SHALL NOT be resolved by informal hedge-model
convention.

1. Is the hedge ratio static (beta-based), rolling/regression-estimated, or
   dynamically re-estimated, and over what estimation window given Korean regime
   shifts?
2. Is hedge sizing denominated in the mini or full KOSPI200 product (or
   config-driven), and how is fractional-contract rounding and residual basis
   handled?
3. What roll policy governs the second-Thursday expiry cycle — calendar-day
   trigger, volume-based, or explicit operator action — and is the roll staged or
   all-at-once?
4. For a non-index-representative book, is portfolio beta computed against
   KOSPI200 specifically or a broader Korean proxy, and how often re-estimated?
5. Is the unhedged overnight/global-event gap (night session disabled) accepted
   as a documented residual risk, or addressed by a compensating control such as
   pre-close de-risking or reduced overnight equity limits?
6. Which exact benefit-recognition proof (ADR-002-021 §13) does the hedge rely on
   for its correlation/basis benefit, and which book compositions cannot support a
   bounded worst-credible hedged effect and therefore cannot be treated as
   protective?

Unresolved questions reduce, and do not expand, the conforming action set.

---

## 17. Review History

### v0.1 — Initial Draft

* Established RFC-007 as the decision-layer portfolio hedge model, subordinate to
  RFC-000/001/002 and the ADR-002 series and operating within RFC-003, using
  RFC-004 and RFC-006.
* Made the load-bearing property explicit: a hedge is a protective action
  established by proof, not by label; classification is owned exclusively by the
  Protective Action Controller under ADR-002-001 §6 (Final-State and
  Intermediate-State tests), and a hedge that worsens margin/basis/liquidity/
  concentration may be denied (§10).
* Defined hedge-ratio methodology (beta, minimum-variance/cross-hedge), basis risk
  and effectiveness under ARE-INV-005, and roll/expiry as ADR-002-011
  protection-gap-controlled replacement (§§7–9).
* Bound the hedge to reserved protective capacity (ADR-002-001 §4, ADR-002-002
  §19); priority is not reservation (§11).
* Restated the hedge-model↔safety boundary as ten prohibitions consistent with
  RFC-002 §9.1 and RFC-003 §11.
* Represented the Korean/KOSPI200 hedge environment as living configuration, and
  recorded the night-session-disabled unhedged-overnight-gap as a binding
  constraint and residual-risk item (§13).
* Marked scope relationships to RFC-003/004/005/006 without pre-empting them.
* Introduced no SAFE-xxx requirement, numeric bound, or authority.
* Independent adversarial EV-L0 document review passed cleanly with no Critical,
  Major, or Minor finding. All four target properties held: a hedge is protective
  by proof not label, with classification owned exclusively by the Protective
  Action Controller under ADR-002-001 §6 and adverse dimensions surfaced not
  hidden (§10); unproven hedge/correlation/basis benefit is zero and breakdown is
  worst-credible (ARE-INV-005/006 — §8); the model mutates no capacity and never
  treats priority as reservation (§11); and a roll is a protection-gap-controlled
  replacement with no discharge before Final Quantity Proof (ADR-002-011 — §9).
  Twelve self-classification/benefit/capacity/roll sequences were attempted and
  blocked, and every ADR/CONST/SAFE/philosophy citation was verified verbatim
  against source text. The review is EV-L0 only and confers no acceptance or
  live-readiness.
