# RFC-005 — Execution Model

**Document ID:** RFC-005
**Title:** Execution Model
**Version:** 0.1
**Status:** Ratified (2026-07-18 — GOV-001 G5 record RR-0007, ARCHITECTURE-GATE-STATUS §9.7; ratification confers no live authorization, no ADR acceptance, and no capacity)
**Classification:** Decision-Layer Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Safety Authority:** Constrained by RFC-001 — Safety Case and RFC-002 — Architecture
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-15
**Last Updated:** 2026-07-17

---

## 1. Abstract

This document defines the **execution model**: how an already-approved Intent is
worked into the market — how a parent Intent is sliced over time, which
execution benchmark it is measured against, how transaction cost, slippage, and
market impact are estimated and analyzed, and how order types, auctions, halts,
retries, and ambiguous outcomes are handled.

RFC-005 is subordinate to RFC-000, RFC-001, RFC-002, and every accepted
ADR-002-xxx, and it operates within RFC-003. It elaborates *execution quality*;
it does **not** redefine the canonical order-construction, commitment, and
transmission machinery. The deterministic construction of a broker command, the
atomic risk-capacity commitment, the conformance proof, the single-use
Transmission Capability, and the final-egress currentness protocol are owned by
ADR-002-020, ADR-002-002, ADR-002-022, ADR-002-024, and the Broker Egress
Gateway. RFC-005 describes how execution is *planned and measured* inside that
machinery, never a path around it.

A decisive constraint runs through this document: the system reaches the market
through a **broker API (KIS), not direct market access**. Optimal-execution
theory is therefore a scaffold for slicing and measurement, not a claim of
queue-level control. RFC-005 selects no specific algorithm or venue tactic and
fixes no numeric parameter; those are living configuration.

---

## 2. Normative Authority

RFC-005's authority is bounded as follows:

* **RFC-000 — Trading Constitution** governs this document; RFC-005 SHALL NOT
  redefine constitutional intent (RFC-000 §9) and SHALL use RFC-000 §6
  vocabulary verbatim.
* **RFC-001 — Safety Case** constrains this document; in particular SAFE-021
  (At-Most-One Exposure Effect) governs retries, reconnects, and ambiguous
  acknowledgements, and no execution behavior defined here may weaken it.
* **RFC-002 — Architecture** and the **ADR-002-xxx** series own the execution
  machinery RFC-005 operates within: ADR-002-020 (Intent-to-order conformance and
  canonical command construction), ADR-002-002 (risk-capacity commitment and the
  Normal Commitment Flow), ADR-002-022 (action-flow budgeting and retry-storm
  containment), and ADR-002-024 (active currentness and final-egress admission).
  RFC-002 §10.7 (Execution Coordinator) and §10.8 (Broker Adapter / Broker Egress
  Gateway) are the owning components.
* **RFC-003 — Decision Framework** is the layer RFC-005 serves; execution acts
  only on an approved Intent and inherits every RFC-003 boundary.
* Where RFC-005 and any higher document appear to conflict, the higher document
  governs and the conflict SHALL be raised through governance.

RFC-005 creates no capacity, authority, Transmission Capability, configuration,
or transmission permission, and its acceptance authorizes no live operation.

---

## 3. Scope and Non-Scope

This document governs:

* how an approved Intent is worked into the market over time (slicing schedules);
* execution benchmarks and transaction-cost analysis (TCA);
* the representation of slippage and the *use* of market-impact estimates for
  execution planning;
* order-type selection, auction participation, and behavior at halts and
  rejections;
* retry, reconnection, and ambiguous-outcome handling at the execution layer;
* the broker-API (non-DMA) constraints on all of the above.

This document does not decide:

* whether to trade, or the target position — RFC-003 and the Decision Policy own
  that;
* canonical broker-command construction, the Order Conformance Proof, or exact
  economic-effect fencing — ADR-002-020 owns that;
* risk-capacity allocation, the Normal Commitment Flow ordering, or the
  Transmission Capability — ADR-002-002 owns that;
* action-flow budgets, rate limits, and retry-storm containment mechanisms —
  ADR-002-022 owns that (RFC-005 respects them, does not define them);
* final-egress currentness and the send-boundary ordering — ADR-002-024 and the
  Broker Egress Gateway own that;
* venue tradability, session phase, and admissibility — ADR-002-019 owns that;
* the market-impact/liquidity *model* — RFC-004 owns that (RFC-005 consumes it);
* risk methodology and sizing — RFC-006 owns that;
* any specific execution algorithm, venue tactic, or numeric parameter.

An execution model that reconstructs, defaults, or repairs a broker command,
mutates capacity, or reaches a broker route outside the owning components is
non-conforming.

---

## 4. Relationship to Vision and Philosophy

RFC-005 operationalizes principles already established upstream; it inherits, and
does not restate, them.

* **Execution is irreversible** (philosophy §12). A transmitted order can produce
  a real, unrecoverable economic effect. Execution planning SHALL treat every
  send as potentially live and SHALL NOT rely on the ability to undo it.
* **Potential exposure matters before confirmed exposure** (philosophy §19). An
  in-flight or ambiguous order consumes exposure at its worst credible bound
  until proven otherwise; execution SHALL NOT wait for confirmation to account
  for exposure it may already have.
* **Partial success is not complete success** (philosophy §20). A partially
  filled parent Intent, a partially completed slicing schedule, or a partially
  acknowledged batch SHALL be represented as partial, never rounded up to
  complete.
* **Uncertainty reduces authority** (philosophy §8, via RFC-003 §6). An
  ambiguous execution outcome narrows, never widens, subsequent execution
  action; UNKNOWN is restrictive.

Where an execution behavior would contradict a Vision or Philosophy principle, it
is non-conforming.

---

## 5. Definitions

RFC-005 reuses canonical terms from RFC-000 §6, RFC-001 §5, RFC-002 §3.1, and the
ADR series, and SHALL NOT introduce synonyms for them. The following
framework-local terms are scoped to execution and are non-authorizing.

* **Execution Plan** — the strategy for working one approved Intent into the
  market over time: the intended slicing, timing, order types, and benchmark. An
  Execution Plan is a plan for how to execute an *already-approved* Intent; it
  creates no authorization and does not alter the Intent's approved scope or
  economic-effect envelope.
* **Child Order (Slice)** — one broker-directed order that implements a portion
  of a parent Intent. Every Child Order SHALL remain within the parent Intent's
  approved scope and SHALL pass the full commitment and send machinery
  individually; slicing never bypasses per-order approval, capacity, or
  currentness.
* **Execution Benchmark** — the reference price against which execution quality
  is measured (for example arrival price / implementation shortfall, VWAP, TWAP,
  or a decision-time mid). A benchmark is a measurement reference, not an
  authorization.
* **Slippage** — the realized difference between an execution benchmark and the
  actual fill price. A measured, after-the-fact quantity.
* **Transaction Cost Analysis (TCA)** — the after-the-fact measurement discipline
  that decomposes realized execution cost against a benchmark. TCA is
  observation; it grants no authority and changes no committed capacity.
* **Market Impact (execution use)** — the price response attributable to the
  system's own trading, as represented by RFC-004 and *used* for execution
  planning. RFC-005 consumes the impact representation; it does not define it.

---

## 6. Execution Model Principles

A conforming execution model SHALL satisfy the following. They are execution
obligations, not enforcement mechanisms; the enforcement points remain owned by
RFC-002 and the ADR series.

1. **Execution acts on an approved Intent only.** The execution layer SHALL work
   only Intents that have been independently approved and registered
   (ADR-002-023); it SHALL NOT originate, widen, or re-scope an Intent.
2. **Every child order runs the full machinery.** Slicing a parent Intent SHALL
   NOT bypass per-order construction, admissibility, capacity commitment,
   conformance proof, authority, or final-egress currentness (ADR-002-002 §11).
3. **Irreversibility governs.** Every send is treated as potentially live;
   execution SHALL NOT presume it can cancel or undo a transmitted order to
   restore prior state (philosophy §12).
4. **Partial is partial.** Partial fills and partial schedules SHALL be
   represented exactly and conservatively, never completed by assumption
   (philosophy §20).
5. **UNKNOWN is restrictive.** A missing acknowledgement, timeout, or ambiguous
   response SHALL NOT be read as rejection or as safe-to-retry; it consumes
   exposure at its worst credible bound (SAFE-021; RFC-002 §10.7).
6. **The model informs, it does not authorize.** An Execution Plan, benchmark, or
   TCA result SHALL NOT create capacity, authority, or transmission permission.

---

## 7. The Approved-Intent Execution Path

The exact ordering by which an approved Intent becomes a transmitted order is
defined by ADR-002-002 §11 (Normal Commitment Flow) and ADR-002-020, and is
enforced by the Execution Coordinator (RFC-002 §10.7) and the Broker Egress
Gateway (RFC-002 §10.8). RFC-005 SHALL NOT redefine, reorder, or abridge that
sequence. In summary — normative source ADR-002-002 §11 — each broker-directed
order proceeds through deterministic candidate construction, venue admissibility,
independent approval and Intent registration, conservative economic-effect
derivation, aggregate-risk evaluation, action-flow evaluation, atomic RCL
capacity commitment, conformance proof, attempt binding, single-use Transmission
Capability issuance, and final-egress verification with `SEND_STARTED`
durability, after which the reservation is `POTENTIALLY_LIVE`.

RFC-005's contribution is confined to *how the work is planned around* that
machinery:

* deciding how a parent Intent is divided into Child Orders over time (§8);
* selecting order types, timing, and benchmark (§§8, 10);
* measuring realized quality against the benchmark (§9);
* handling retries, reconnections, and ambiguous outcomes within the machinery's
  rules (§11).

Each Child Order is itself an ordinary broker-directed order that traverses the
full ADR-002-002 §11 flow. The execution layer SHALL NOT invent, default,
normalize, round, or repair any broker-command field (RFC-002 §10.7); ADR-002-020
owns construction, and the Broker Adapter owns the actual-outbound comparison.

---

## 8. Optimal Execution and Slicing

Working a large Intent as a single order can incur excessive market impact;
working it too slowly incurs price risk over the execution horizon. The classical
treatment of this trade-off (Almgren–Chriss optimal execution, 2001) frames it as
minimizing a combination of expected impact cost and the variance of execution
cost over a fixed horizon, producing a slicing trajectory; benchmark-tracking
strategies (VWAP, TWAP) and implementation-shortfall measurement (Perold, 1988)
are the standard companions. RFC-005 treats these as a **scaffold** for choosing
a slicing schedule and a benchmark, not as prescribed algorithms.

**Non-DMA caveat (load-bearing).** These models were developed for direct market
access, where the trader controls placement, cancellation, and often queue
position. This system reaches the market through the **KIS broker API**, one
layer removed: it submits orders subject to broker-side rate limits, acknowledgement
latency, and no control over exchange-side matching or queue priority.
Consequently:

* an optimal-execution *trajectory* is usable as a slicing guide, but its
  *implementation* is bounded by broker-API rate limits (owned by ADR-002-022),
  quote staleness, and acknowledgement/fill latency, not by queue-level control;
* execution "smartness" is limited to order-type selection, timing and slicing,
  and passive-versus-aggressive placement; the model SHALL NOT assume access to
  exchange-native hidden, iceberg, or pegged behavior unless the broker
  demonstrably exposes it (evidenced under ADR-002-004);
* the model SHALL NOT assume a Child Order can be cancelled or repriced in time
  to avoid an adverse fill; irreversibility (§4) governs.

The concrete slicing algorithm, its risk-aversion parameter, and its horizon are
modeling and configuration choices. RFC-005 fixes the discipline — every slice is
a full-machinery order, and no slicing plan is a substitute for approval,
capacity, or currentness — not the algorithm.

---

## 9. Transaction Cost, Slippage, and Impact

Because the system cannot observe or control the exchange-side queue, transaction
cost analysis is primarily a **measurement discipline** rather than a control
lever.

* **Benchmark and slippage.** Execution quality is measured as slippage against a
  declared Execution Benchmark (arrival price / implementation shortfall, VWAP,
  TWAP, or decision-time mid). The benchmark choice is a configuration decision
  and MAY differ between the equity and futures pipelines; RFC-005 fixes that a
  benchmark SHALL be declared and measured, not which one.
* **Impact consumption.** RFC-005 consumes the temporary/permanent market-impact
  representation defined by RFC-004; it SHALL NOT redefine that representation.
  Under a top-of-book-limited broker feed, impact and depth are estimated with
  explicit uncertainty (RFC-004 §7), and the execution model SHALL NOT treat an
  impact estimate as a guarantee.
* **Expectancy realism.** A Decision Policy's claimed edge SHALL account for
  realistic execution cost, slippage, and impact before it is treated as
  demonstrated. RFC-005 supplies the cost/slippage/impact-realism apparatus that
  RFC-003 §12 requires for the positive-expectancy obligation; the population and
  significance methodology is RFC-006's, and demonstration is verified under
  ADR-002-025.
* **TCA is non-authorizing.** A favorable or unfavorable TCA result is
  observation. It SHALL NOT release or create capacity, alter an approved Intent,
  or authorize a retry.

RFC-005 fixes the measurement discipline and its provenance. The concrete cost
model and numeric assumptions are configuration; a pipeline's existing slippage
assumption (for example a fixed per-tick figure in a backtest harness) is a
configuration value, not RFC-005 content.

---

## 10. Order Types, Auctions, and Halts

Execution occurs across distinct venue mechanics, which the Execution Plan SHALL
represent explicitly rather than assuming a single continuous regime.

* **Order types.** Market, limit, and any broker-exposed conditional order types
  are selected as part of the Execution Plan. Available types are bounded by what
  the broker evidences (ADR-002-004); the plan SHALL NOT assume an unavailable
  type.
* **Auctions vs continuous session.** Opening and closing call auctions have
  price-formation mechanics distinct from continuous trading. An Execution Plan
  SHALL decide auction participation explicitly and SHALL NOT apply naive
  continuous-session slicing logic to a call-auction phase. The authoritative
  session phase remains owned by ADR-002-019; RFC-005 plans within it and never
  asserts it.
* **Halts and rejections mid-schedule.** A price-limit event, volatility
  interruption, or broker rejection can interrupt an in-flight Execution Plan
  independently of the plan's own logic. On such an event the execution layer
  SHALL treat outstanding and in-flight slices conservatively (potential exposure
  per §4), SHALL NOT blindly resubmit (§11), and SHALL re-establish authoritative
  admissibility and currentness before any further send (ADR-002-019,
  ADR-002-024). A halt is not a cancellation; an in-flight order may still fill.

The specific order-type catalogue, auction-participation policy, and halt-handling
thresholds are configuration and broker-capability facts, not RFC-005 numeric
content.

---

## 11. Retry, Duplication, and UNKNOWN

Retry and reconnection are the highest-risk execution behaviors, because a
careless retry can create duplicate exposure. This section is load-bearing.

Per SAFE-021 (At-Most-One Exposure Effect), retries, reconnects, restarts,
duplicate events, and ambiguous acknowledgements SHALL NOT create aggregate
exposure greater than the exposure authorized by the originating Intent, and the
system SHALL NOT assume that a missing acknowledgement means an order was not
accepted. Accordingly, a conforming execution model:

* SHALL treat a timeout, missing acknowledgement, or ambiguous response as
  **UNKNOWN**, not as rejection — UNKNOWN consumes exposure at its worst credible
  bound and is never silently retried (RFC-002 §10.7, §12.1);
* SHALL NOT resubmit an order whose outcome is UNKNOWN without the
  reconciliation, attempt-identity, and capacity conditions the owning components
  require; retry is a new send under ADR-002-002 §11.4 and ADR-002-022, not a
  free repeat;
* SHALL keep retry and reconnection within the ADR-002-022 action-flow budget and
  retry-storm containment; execution SHALL NOT amplify traffic beyond the
  committed budget, and SHALL NOT consume protective-flow reserve;
* SHALL account for a `POTENTIALLY_LIVE` reservation and a post-`SEND_STARTED`
  crash as possibly live (ADR-002-002 §11.4), retaining conservative capacity
  rather than assuming no effect;
* SHALL represent a partially filled parent Intent as partial and SHALL NOT
  re-request the already-filled quantity.

No execution convenience — batching, fire-and-forget, optimistic retry, or
assumed rejection — overrides SAFE-021.

---

## 12. The Execution-Model↔Safety Boundary

RFC-005 restates, at the execution layer, the separation enforced by RFC-002
§9.1 and inherited from RFC-003 §11. The execution model, and any Execution Plan
or slicing component, SHALL NOT:

1. originate, approve, widen, or re-scope an Intent, or act on an unapproved
   proposal (RFC-002 §10.7; ADR-002-023; RFC-003 §11);
2. reserve, commit, mutate, or release risk capacity, or write to the Risk
   Capacity Ledger (ADR-002-002);
3. construct, invent, default, normalize, round, or repair a canonical broker
   command, or bypass the Order Conformance Proof (RFC-002 §10.7; ADR-002-020);
4. issue, extend, or reuse a Transmission Capability, or reach a broker route
   outside the Broker Egress Gateway (ADR-002-002 §11.4; ADR-002-013);
5. bypass final-egress currentness or the claim/`SEND_STARTED`/first-byte
   ordering at the send boundary (ADR-002-024);
6. treat a timeout or missing acknowledgement as rejection, or blind-retry an
   UNKNOWN outcome (SAFE-021; §11);
7. create aggregate exposure beyond the originating Intent's authorized scope via
   slicing, retry, reconnect, or duplicate handling (SAFE-021);
8. exceed the action-flow budget or consume protective-flow reserve to push
   execution traffic (ADR-002-022);
9. assert venue tradability, session phase, or admissibility, or proceed through
   a halt without re-establishing the authoritative ADR-002-019 evaluation
   (§10);
10. classify an execution action (for example a fast liquidation) as protective
    on its own authority (RFC-001 §5.25);
11. present a benchmark, slippage, or TCA result as authority to release capacity,
    alter an Intent, or authorize a retry (§9).

The execution model plans and measures how an approved Intent reaches the market.
It authorizes nothing.

---

## 13. Korean Execution Environment

Execution occurs on KRX venues through the KIS broker API. RFC-005 represents the
following environment facts; every numeric value is a **living parameter** sourced
from the current broker-capability profile (ADR-002-004), the KRX rulebook, and
approved configuration, and SHALL NOT be hardcoded into this specification.

* **Broker-API rate limits.** KIS enforces its own request-rate ceilings. These
  bound feasible slicing cadence and retry behavior and are governed as
  action-flow limits under ADR-002-022; RFC-005 plans within them and defines
  none of the values.
* **Tick granularity.** KRX's price-banded equity tick schedule and the fixed
  KOSPI200 futures ticks bound feasible limit-price placement and therefore
  slicing and passive-order strategy. The applicable tick is a market-structure
  fact from RFC-004; RFC-005 respects it.
* **Session and auctions.** The continuous session plus opening/closing call
  auctions require explicit auction-participation planning (§10); session times
  are configuration and the authoritative phase is ADR-002-019's.
* **Halts and limits.** Per-instrument volatility interruptions, index circuit
  breakers, the program-trading sidecar, and daily price-limit bands can
  interrupt execution; the execution layer treats these conservatively (§10) with
  thresholds drawn from configuration.
* **Futures products and night session.** The standard and mini KOSPI200 futures
  differ in multiplier and tick; the execution layer works the configured product
  and SHALL NOT assume one product's parameters for another. The night session is
  disabled by operator policy, so execution SHALL NOT plan continuous futures
  work outside the enabled session.

RFC-005 fixes what execution-environment facts the model respects and their
provenance. It fixes no numeric value.

---

## 14. Relationship to RFC-003, RFC-004, RFC-006, and RFC-007

RFC-005 sits within the decision layer and shares boundaries with its companions.
The pointers below are non-normative scope markers; RFC-005 SHALL NOT define
their content.

* **RFC-003 — Decision Framework.** Execution acts only on an approved Intent
  produced through RFC-003; RFC-005 supplies the execution-cost realism RFC-003
  §12 requires for the positive-expectancy obligation.
* **RFC-004 — Market Model.** RFC-005 consumes RFC-004's market-impact,
  liquidity, and microstructure representation for execution planning; it does
  not redefine it and does not assert tradability.
* **RFC-006 — Risk Model.** The population, significance, and cost-model
  methodology behind expectancy and risk is RFC-006's; RFC-005 provides
  execution-cost inputs, not the risk methodology.
* **RFC-007 — Portfolio Hedge Model.** A hedge order executes through this model,
  but its hedge sizing remains owned by RFC-007 and its protective classification
  is owned exclusively by the Protective Action Controller under ADR-002-001 §6;
  RFC-005 executes, it does not classify.

Until each companion RFC is accepted, its concerns remain open and SHALL NOT be
resolved by execution-model convention.

---

## 15. Requirements Traceability

RFC-005 discharges decision-layer execution obligations within the bounds set
upstream. This table is an initial allocation and SHALL be refined as the
companion RFCs are accepted.

| Requirement | Discharge in RFC-005 |
|---|---|
| RFC-000 CONST-002 (Capital Preservation; Traceability names RFC-005) | irreversibility, potential-exposure, and partial-success discipline in execution planning (§§4, 6, 11) |
| RFC-000 CONST-004 (Fail-Safe Operating Principle; Traceability names RFC-005) | UNKNOWN is restrictive; halts and ambiguous outcomes fail closed (§§6, 10, 11) |
| RFC-000 CONST-009 (Pre-Trade Constitutional Assurance; Traceability names RFC-005) | every child order runs the full pre-send machinery; no slicing bypass (§§7, 12) |
| RFC-001 SAFE-021 (At-Most-One Exposure Effect) | retry/reconnect/duplicate/UNKNOWN handling never exceeds the originating Intent's exposure (§§11, 12) |
| ADR-002-002 §11 Normal Commitment Flow | referenced as the authoritative execution ordering; not redefined (§7) |
| ADR-002-020 canonical construction | execution never invents/repairs a broker command (§§7, 12) |
| ADR-002-022 action-flow/retry-storm | execution stays within the action-flow budget and protective reserve (§§8, 11, 12) |
| ADR-002-024 final-egress currentness | execution never bypasses send-boundary currentness/ordering (§§10, 12) |
| philosophy §§12, 19, 20 | execution-is-irreversible, potential-exposure, partial≠complete operationalized (§4) |
| RFC-000 §12 narrow-only; §12 Execution-Model↔Safety Boundary | registered as DEC-002 (VER-DEV-001, EVIDENCE-REGISTER-DEV; evidence DEC-EV-002); widens no Part-1 authority |

RFC-005 introduces no SAFE-xxx requirement and no numeric bound.

---

## 16. Open Questions

These are open while RFC-005 is a Review Draft and while the companion RFCs are
unwritten. They SHALL NOT be resolved by informal execution-model convention.

1. Is an explicit Almgren–Chriss cost/risk trade-off adopted, or a simpler
   heuristic slicing schedule, given that the non-DMA broker-API path bounds what
   is realizable?
2. Which Execution Benchmark (arrival price / implementation shortfall, VWAP,
   TWAP, decision-time mid) applies, and does it differ between the equity and
   futures pipelines?
3. How is temporary-versus-permanent impact estimated for planning when the
   broker feed exposes only top-of-book / limited depth?
4. How is call-auction participation represented and planned distinctly from
   continuous-session execution?
5. What is the exact reconciliation and attempt-identity precondition for a retry
   after an UNKNOWN outcome, within ADR-002-002 §11.4 and ADR-002-022?
6. How is the execution-cost apparatus shared with RFC-006 so that expectancy
   realism (RFC-003 §12) uses one consistent cost model?

Unresolved questions reduce, and do not expand, the conforming action set.

---

## 17. Review History

### v0.1 — Initial Draft

* Established RFC-005 as the decision-layer execution model, subordinate to
  RFC-000/001/002 and the ADR-002 series and operating within RFC-003.
* Confined RFC-005 to execution quality — slicing, benchmark, TCA, order types,
  auctions, halts, and retry — and deferred canonical construction, capacity
  commitment, action-flow budgeting, and final-egress currentness to their owning
  ADRs (§§3, 7).
* Stated the non-DMA broker-API caveat as load-bearing: optimal-execution theory
  is a slicing/measurement scaffold, not queue-level control (§8), and TCA is a
  measurement discipline (§9).
* Made retry/UNKNOWN/duplication handling explicit under SAFE-021 (§11).
* Restated the execution-model↔safety boundary as eleven prohibitions consistent
  with RFC-002 §9.1 and RFC-003 §11.
* Represented the Korean/KIS execution environment as living configuration with
  no hardcoded numeric threshold (§13).
* Marked scope relationships to RFC-003/004/006/007 without pre-empting them.
* Introduced no SAFE-xxx requirement, numeric bound, or authority.
* Independent adversarial EV-L0 document review passed cleanly with no Critical,
  Major, or Minor finding. All three target properties held: RFC-005 does not
  redefine or bypass the canonical execution machinery (§§7, 12); slicing does
  not become a safety bypass and no schedule exceeds the parent Intent's approved
  exposure (§§6, 8, 12); and retry/UNKNOWN handling honors SAFE-021 with no
  blind-retry, no timeout-as-rejection, and no protective-reserve consumption
  (§§11, 12). Twelve bypass/leak/SAFE-021 sequences were attempted and blocked,
  and every ADR/SAFE/CONST/philosophy citation was verified against source text.
  The review is EV-L0 only and confers no acceptance or live-readiness.
* During the part-2 cross-RFC consistency audit, §14's RFC-007 pointer was
  corrected: protective classification is owned exclusively by the Protective
  Action Controller under ADR-002-001 §6, not "by RFC-007 and ADR-002-001." This
  aligns RFC-005 with RFC-007 §§3, 10, 12, under which RFC-007 classifies nothing.
  RFC-007 retains ownership of hedge sizing only.
