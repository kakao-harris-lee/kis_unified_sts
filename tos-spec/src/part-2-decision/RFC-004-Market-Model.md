# RFC-004 — Market Model

**Document ID:** RFC-004
**Title:** Market Model
**Version:** 0.1
**Status:** Ratified (2026-07-18 — GOV-001 G5 record RR-0006, ARCHITECTURE-GATE-STATUS §9.7; ratification confers no live authorization, no ADR acceptance, and no capacity)
**Classification:** Decision-Layer Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Safety Authority:** Constrained by RFC-001 — Safety Case and RFC-002 — Architecture
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-15
**Last Updated:** 2026-07-17

---

## 1. Abstract

This document defines the **market model**: the structured representation of
market state that a decision interprets. It gives the Decision Framework
(RFC-003) a disciplined vocabulary for order book, spread, liquidity, market
impact, volatility, and regime, so that a Decision Policy reasons about the
market from a consistent, provenance-bound, uncertainty-aware picture rather than
from ad hoc reads of raw data.

RFC-004 is subordinate to RFC-000, RFC-001, RFC-002, and every accepted
ADR-002-xxx, and it operates within RFC-003. It is a **consumer** of the Critical
Input and Decision Context machinery (ADR-002-018); it is not a definer of that
machinery and holds no authority over it. Critically, RFC-004 models the market;
it does **not** decide whether an order may be sent. Instrument tradability,
session phase, halts, and order admissibility are owned exclusively by
ADR-002-019 and the Venue Constraint Gate. Market-data health and venue
tradability are different facts, and RFC-004 SHALL NOT conflate them.

RFC-004 selects no specific data vendor, feed, indicator, or model. It defines
the model shape and its safety boundary; concrete numeric parameters are living
values drawn from approved configuration and the current venue rulebook, never
hardcoded into this specification.

---

## 2. Normative Authority

RFC-004's authority is bounded as follows:

* **RFC-000 — Trading Constitution** governs this document; RFC-004 SHALL NOT
  redefine constitutional intent (RFC-000 §9) and SHALL use RFC-000 §6
  vocabulary verbatim.
* **RFC-001 — Safety Case** constrains this document; any market datum, feature,
  or signal RFC-004 describes is a Critical Input under RFC-001 §5.3 and SAFE-030
  through SAFE-035.
* **RFC-002 — Architecture** and the **ADR-002-xxx** series define the components
  RFC-004 consumes. In particular ADR-002-018 governs Critical Input integrity,
  provenance, and derived-input lineage, and ADR-002-019 owns venue, session,
  tradability, and order admissibility.
* **RFC-003 — Decision Framework** is the layer RFC-004 serves; RFC-004 supplies
  interpreted market state to a decision and inherits every RFC-003 boundary.
* Where RFC-004 and any higher document appear to conflict, the higher document
  governs and the conflict SHALL be raised through governance.

RFC-004 creates no capacity, authority, tradability determination, configuration,
or transmission permission, and its acceptance authorizes no live operation.

---

## 3. Scope and Non-Scope

This document governs:

* the representation of market state: order book, bid/ask spread, depth,
  liquidity, and market impact;
* volatility estimation and the representation of market regime;
* how market data and derived features are consumed as Critical Inputs;
* the boundary between market modeling and venue tradability;
* the boundary between market modeling and every safety-enforcement owner;
* how Korea-specific market structure is represented as living parameters.

This document does not decide:

* whether an instrument is tradable or an order is admissible — ADR-002-019 and
  the Venue Constraint Gate own that;
* the definition of Critical Input, its provenance, or its consistency-cut
  construction — ADR-002-018 owns that;
* the decision process itself — RFC-003 owns that;
* execution cost, slippage, or impact *realization* for execution purposes —
  RFC-005 owns that (RFC-004 models impact as a market property, not an execution
  tactic);
* risk measurement or position sizing — RFC-006 owns that;
* any specific data vendor, feed, indicator, or statistical model;
* concrete numeric thresholds (price-limit bands, VI thresholds, tick tables),
  which are living configuration values, not RFC-004 content.

A market model that asserts tradability, defines context integrity, or carries
hardcoded venue thresholds is non-conforming.

---

## 4. Relationship to Vision and Philosophy

RFC-004 operationalizes principles already established upstream; it inherits, and
does not restate, them.

* **Prediction has limited authority** (philosophy §7). A market model produces
  interpretation and estimates — uncertain evidence, never permission. A regime
  label or volatility forecast SHALL NOT authorize any action.
* **State is established from evidence** (philosophy §16). Market state SHALL be
  established from admitted observations with provenance, not from component
  health, connection status, or last-known-good caches.
* **Time is data** (philosophy §17). Timestamps, staleness, and observation age
  are first-class modeled quantities governed by the trustworthy-time
  architecture (ADR-002-008), not incidental metadata.
* **Uncertainty reduces authority** (philosophy §8, via RFC-003 §6). Where market
  state is incomplete, stale, or ambiguous, the model SHALL report that
  uncertainty rather than impute a confident value, and the decision's action set
  narrows accordingly.

Where a market model would contradict a Vision or Philosophy principle, it is
non-conforming.

---

## 5. Definitions

RFC-004 reuses canonical terms from RFC-000 §6, RFC-001 §5, RFC-002 §3.1, and the
ADR series, and SHALL NOT introduce synonyms for them. The following
framework-local terms are scoped to market modeling and are non-authorizing.

* **Market State** — the interpreted, provenance-bound representation of a
  venue's and instrument's observable condition (price, book, spread, depth,
  volatility, regime) at a bound observation time. Market State is derived
  Critical Input under ADR-002-018 and grants no authority.
* **Order Book** — the represented set of resting bids and asks by price level,
  to the depth the approved feed provides. The model SHALL record the observed
  depth limit and SHALL NOT impute levels beyond it.
* **Bid/Ask Spread** — the represented gap between best bid and best ask at a
  bound observation time; a cost-of-immediacy indicator, not a tradability claim.
* **Liquidity** — a multi-dimensional representation of tightness (spread), depth
  (size available), and resiliency (replenishment); it is an estimate with
  uncertainty, never a guarantee that an exit will execute.
* **Market Impact** — the represented price response attributable to trading,
  conventionally decomposed into a temporary (reverting) and a permanent
  (information) component. RFC-004 models impact as a market property; its use in
  execution is deferred to RFC-005.
* **Realized Volatility** — a volatility estimate computed from admitted
  high-frequency return observations over a bound window.
* **Market Regime** — a represented, persistent volatility/trend/liquidity state.
  A regime label is interpretation, never authority, and its exact
  classification method is a modeling choice bound to configuration.

---

## 6. Market Model Principles

A conforming market model SHALL satisfy the following. They are modeling
obligations, not enforcement mechanisms.

1. **Model, do not authorize.** The market model produces interpreted state and
   estimates only. No output SHALL be treated as approval, capacity, or
   tradability.
2. **Market-data health is not tradability.** A live feed, recent quote, or
   accepted subscription SHALL NOT be represented as, or used to infer,
   instrument tradability or order admissibility (ADR-002-019).
3. **State from admitted observation.** Every modeled quantity SHALL derive from
   admitted Critical Input with complete lineage; no out-of-context fetch,
   default, forward-fill, or last-known-good substitution is permitted
   (ADR-002-018 §10).
4. **Uncertainty is represented, not imputed away.** Missing, stale, conflicting,
   or wrongly scaled data SHALL be represented as uncertainty or a gap, never
   silently completed into a confident value (ADR-002-018 CII-INV-005).
5. **Estimates are evidence.** Volatility forecasts, regime labels, impact
   estimates, and liquidity measures are uncertain evidence for a decision, never
   permission (philosophy §7).
6. **Determinism of derivation.** Given identical admitted observations and an
   identical model version, a derived quantity SHALL be reproducible; a
   seeded-stochastic derivation carries its recorded seed or non-determinism
   declaration (ADR-002-018 §10; RFC-003 §10).

---

## 7. Market State and Microstructure

RFC-004 represents market microstructure as interpreted Critical Input. The model
SHALL bind, for each represented instrument and venue, the observation time, the
source provenance, and the observed depth and completeness limits.

* **Order book and depth.** The model represents resting liquidity to the depth
  the approved feed provides and SHALL record that depth limit. Depth beyond the
  observed limit is unknown, not zero. A broker-API feed that exposes only
  top-of-book is represented as top-of-book with explicit depth uncertainty.
* **Spread and immediacy.** The bid/ask spread is represented as a cost-of-
  immediacy indicator at a bound time. A tight spread SHALL NOT be read as
  tradability or as a guarantee of fill.
* **Liquidity and resiliency.** Liquidity is a multi-dimensional estimate;
  resiliency (replenishment after a shock) is inherently uncertain under a
  limited-depth feed and SHALL be represented with that uncertainty.
* **Market impact.** Temporary and permanent impact are represented as market
  properties estimated from observation. RFC-004 does not prescribe how impact is
  managed during execution — that is RFC-005 — and SHALL NOT present an impact
  estimate as an execution guarantee.

The concrete microstructure estimators, their windows, and their parameters are
modeling and configuration choices; RFC-004 fixes the representation and its
provenance discipline, not the estimator values.

---

## 8. Volatility and Regime

Volatility and regime are interpreted market state, not authority.

* **Realized volatility.** The model estimates realized volatility from admitted
  high-frequency return observations over a bound window, aware of the
  microstructure-noise limits of the sampling frequency. Heterogeneous-horizon
  approaches (for example the HAR family, which aggregates short-, medium-, and
  long-horizon realized variance) are a conforming choice; the concrete estimator
  and its parameters are bound to configuration, not fixed here.
* **Regime.** A market regime is a represented persistent state (for example a
  volatility band or trend/liquidity classification). Whether regime is
  classified by a realized-volatility percentile scheme, a switching model, or
  another approved method is a modeling choice. A regime label is interpretation
  and SHALL NOT by itself gate, authorize, or size any action.
* **Shared estimation.** Where the same volatility estimate feeds both regime
  classification here and risk sizing in RFC-006, the shared estimate SHALL carry
  one provenance and one uncertainty representation; RFC-004 and RFC-006 SHALL
  NOT silently diverge on the same underlying quantity. Whether the estimate is
  shared or deliberately decoupled is an open question (§15) pending RFC-006.

RFC-004 defines what volatility and regime *represent* and their provenance
discipline. The statistical method and its numeric parameters are configuration,
and any risk use is RFC-006.

---

## 9. Market Data as Critical Input

Any market datum, quote, book snapshot, trade print, reference value, or feature
derived from them that can change a decision's direction, instrument, quantity,
price, exposure, risk, or execution behavior is a **Critical Input** under
RFC-001 §5.3 and is governed by ADR-002-018 regardless of what RFC-004 calls it.

Accordingly, a conforming market model:

* SHALL consume market data only as admitted Critical Input with source identity,
  continuity, and provenance (ADR-002-018 §§8–9), never by unattributed fetch or
  side channel;
* SHALL derive every indicator or feature with complete deterministic or
  explicitly stochastic lineage from admitted observations, carrying the recorded
  seed or non-determinism declaration where applicable (ADR-002-018 §10);
* SHALL represent missing, stale, future-dated, conflicting, wrongly scaled, or
  unverifiable data as restrictive uncertainty, never a permissive default
  (ADR-002-018 CII-INV-005);
* SHALL NOT relabel a value as a "feature," "signal," or "derived field" to
  escape Critical Input governance (ADR-002-018 §1);
* SHALL NOT self-certify the freshness, completeness, or validity of its own
  inputs, and SHALL NOT infer data validity or source continuity from feed
  uptime or component health (ADR-002-018 §9);
* SHALL express observation time and staleness on the trustworthy-time basis
  (ADR-002-008), not on unqualified wall-clock reads.

The market model is a consumer of context. It never becomes a second definer or
authority over Critical Input.

---

## 10. The Tradability Boundary

This section is load-bearing. Instrument tradability, session phase, halts,
price-limit state, auction phase, and order admissibility are owned **exclusively
by ADR-002-019 and the Venue Constraint Gate**. RFC-004 models the market; it
does not decide whether an order may be sent.

A conforming market model SHALL NOT:

* assert, represent, or export a `TRADABLE` determination for an order — the
  order-specific ability to trade is the ADR-002-019 Tradability State (§5.6),
  which is "not a global instrument boolean";
* infer tradability, session phase, or halt state from a quote, a recent trade, a
  live subscription, or a broker connection (ADR-002-019 VTG-INV-002 "Tradability
  Is Not Inferred", §25.2);
* treat market-data health as evidence that a venue is open, an instrument is
  tradable, or an exit can execute (ADR-002-019: "Market-data health and venue
  tradability are different facts");
* substitute its own session or halt representation for the authoritative Session
  Phase (ADR-002-019 §5.5) at any admissibility or send decision.

The market model MAY represent an *observed* session phase or halt as market
state for interpretation (for example, "no trades observed; venue may be halted"),
but such a representation is uncertain observation, explicitly not the
authoritative Tradability State, and SHALL be labeled as observation, never as a
tradability determination. Any decision, approval, or send continues to require
the authoritative ADR-002-019 evaluation.

---

## 11. Korean Market Structure

The system trades on the Korea Exchange (KRX) — KOSPI/KOSDAQ equities and KOSPI200
index futures — through the KIS broker API. RFC-004 represents the following
Korea-specific structure. Every numeric threshold below is a **living parameter**:
it SHALL be sourced from the current KRX rulebook and approved configuration at
runtime, and SHALL NOT be hardcoded into this specification, because KRX has
revised several of these values historically.

* **Session structure.** KRX runs a pre-open quote window, opening call auction,
  a continuous double-auction regular session, a closing call auction, and an
  after-hours session. The model SHALL represent the observed session phase
  distinctly from the authoritative ADR-002-019 Session Phase (§10), and SHALL
  represent call-auction phases distinctly from continuous trading because their
  price-formation mechanics differ.
* **Price limits.** KRX equities operate a daily price-limit band around the
  previous close, and KOSPI200 futures operate their own (narrower, stepped)
  band. The model represents proximity to a limit as market state; the exact band
  values are living configuration.
* **Volatility Interruption (VI) and circuit breakers.** KRX applies static and
  dynamic per-instrument VI halts, an index-level circuit breaker, and a
  program-trading sidecar. The model MAY represent an observed VI/halt condition
  as uncertain market state, subject to §10 (it is not an authoritative
  tradability determination). Exact thresholds are living configuration.
* **Tick-size schedule.** KRX uses a price-banded tick schedule for equities and
  fixed ticks for KOSPI200 futures products. The model represents the applicable
  tick as market structure; the band table is living configuration.
* **KOSPI200 futures products.** The standard and "mini" KOSPI200 futures
  contracts differ in multiplier and tick. The model SHALL represent the exact
  contract, multiplier, and tick per the configured product and SHALL NOT assume
  one product's parameters for another.
* **Night session.** A KOSPI200 futures night session exists but is disabled by
  operator policy in this system's configuration. The model SHALL treat
  out-of-session periods as no observable continuous market for the affected
  scope and SHALL NOT impute continuity across a disabled session.

RFC-004 fixes what Korean market structure the model represents and its
provenance discipline. It fixes no numeric value.

---

## 12. The Market-Model↔Safety Boundary

RFC-004 restates, at the market-modeling layer, the separation enforced by
RFC-002 §9.1 and inherited from RFC-003 §11. The market model, and any component
producing Market State, SHALL NOT:

1. approve any proposal or decision, or treat a modeled estimate as approval
   (RFC-002 §9.1; RFC-003 §11);
2. determine tradability, session phase, halt, or order admissibility, or
   substitute a modeled observation for the authoritative ADR-002-019 evaluation
   (§10);
3. reserve, commit, mutate, or release risk capacity, or write to the Risk
   Capacity Ledger (ADR-002-002);
4. issue Live Authorization or Transmission Capability, or reach a broker route
   (RFC-002 §10.2; ADR-002-007);
5. classify any action as protective on the basis of a regime or volatility
   reading (RFC-001 §5.25);
6. define, override, or self-certify Critical Input integrity, provenance, or
   freshness — that is owned by the Context Integrity Service (ADR-002-018);
7. infer market-state validity or source continuity from its own component
   health, feed uptime, or last-known-good cache (ADR-002-018 §9; philosophy §16);
8. present a volatility forecast, regime label, liquidity measure, or impact
   estimate as authority to bypass any risk, venue, approval, or currentness gate
   (philosophy §7; RFC-003 §11);
9. carry a hardcoded venue threshold in place of the living configuration value
   (§11).

The market model informs a decision. It authorizes nothing.

---

## 13. Relationship to RFC-003, RFC-005, RFC-006, and RFC-007

RFC-004 sits within the decision layer and shares boundaries with its companions.
The pointers below are non-normative scope markers; RFC-004 SHALL NOT define
their content.

* **RFC-003 — Decision Framework.** RFC-004 supplies interpreted Market State to
  the decision process and inherits every RFC-003 boundary. A Decision Policy
  consumes Market State as evidence, not as authority.
* **RFC-005 — Execution Model.** RFC-004 models market impact and liquidity as
  market properties; how impact and cost are managed and realized during
  execution is RFC-005. The two SHALL agree on the underlying impact
  representation without RFC-004 prescribing execution tactics.
* **RFC-006 — Risk Model.** Where a volatility or correlation estimate feeds both
  regime classification (§8) and risk sizing, RFC-006 owns the risk methodology;
  the shared estimate carries one provenance (§8).
* **RFC-007 — Portfolio Hedge Model.** RFC-004 supplies the market state
  (basis, correlation, volatility) a hedge decision interprets; the hedge
  methodology remains owned by RFC-007, and its protective classification is
  owned exclusively by the Protective Action Controller under ADR-002-001 §6.

Until each companion RFC is accepted, its concerns remain open and SHALL NOT be
resolved by market-model convention.

---

## 14. Requirements Traceability

RFC-004 discharges decision-layer market-representation obligations within the
bounds set upstream. This table is an initial allocation and SHALL be refined as
the companion RFCs are accepted.

| Requirement | Discharge in RFC-004 |
|---|---|
| RFC-000 CONST-007 (Venue Constraints as first-class decision inputs) | venue/session structure represented as market state feeding decisions, with authoritative tradability deferred to ADR-002-019 (§§10, 11) |
| RFC-001 §5.3, SAFE-030, SAFE-031, SAFE-035 | market data and derived features governed as Critical Input with provenance and trustworthy time (§9) |
| RFC-001 SAFE-032 (current venue/tradability; no assumed exit) | market model never asserts tradability or exit availability; defers to ADR-002-019 (§10) |
| RFC-002 §10.1 Context Integrity Service boundary | market model consumes, never defines, Critical Input integrity (§§9, 12) |
| ADR-002-018 §10 derived-input lineage | every indicator/feature carries deterministic or explicitly stochastic lineage (§9) |
| ADR-002-019 tradability/session ownership | market-model observation is explicitly not the authoritative Tradability State (§10) |
| philosophy §§7, 16, 17 | prediction-is-evidence, state-from-evidence, time-is-data operationalized (§§4, 6, 9) |
| RFC-000 §12 narrow-only; §12 Market-Model↔Safety Boundary | registered as DEC-003 (VER-DEV-001, EVIDENCE-REGISTER-DEV; evidence DEC-EV-003; instantiates the CONST-007 DEC-003 venue-constraint requirement); widens no Part-1 authority |

RFC-004 introduces no SAFE-xxx requirement and no numeric bound.

---

## 15. Open Questions

These are open while RFC-004 is a Review Draft and while the companion RFCs are
unwritten. They SHALL NOT be resolved by informal market-model convention.

1. Is "market regime" formally defined by RFC-004 (for example as realized-
   volatility bands) or left to a downstream consumer's classification?
2. Is one volatility/correlation estimate shared between regime classification
   (§8) and RFC-006 risk sizing, or are they deliberately decoupled?
3. How does the model represent a per-instrument VI halt or price-limit event
   relative to a decision that assumed liquidity — as pure observation handed to
   RFC-003/RFC-006, or with a richer state?
4. Are the KOSPI200 "mini" and full products modeled as one parameterized model
   or as two, given they share microstructure logic but differ in multiplier and
   tick?
5. To what version/date are the KRX VI, circuit-breaker, price-limit, and
   tick-band parameter sets pinned, and how is a refresh triggered when KRX
   revises them?
6. How is impact represented so that RFC-004 (market property) and RFC-005
   (execution realization) agree without RFC-004 prescribing execution tactics?

Unresolved questions reduce, and do not expand, the conforming action set.

---

## 16. Review History

### v0.1 — Initial Draft

* Established RFC-004 as the decision-layer market model, subordinate to
  RFC-000/001/002 and the ADR-002 series and operating within RFC-003.
* Defined Market State, microstructure, volatility, and regime as interpreted,
  provenance-bound Critical Input, consumed under ADR-002-018.
* Made the tradability boundary explicit: tradability, session phase, halts, and
  admissibility remain owned by ADR-002-019; the market model represents
  observation only and never asserts tradability (§10).
* Represented Korean (KRX/KOSPI200/KIS) market structure as living configuration
  parameters, with no hardcoded numeric threshold (§11).
* Restated the market-model↔safety boundary as nine prohibitions consistent with
  RFC-002 §9.1 and RFC-003 §11.
* Marked scope relationships to RFC-003/005/006/007 without pre-empting them.
* Introduced no SAFE-xxx requirement, numeric bound, or authority.
* Independent adversarial EV-L0 document review passed with no Critical or Major
  finding; both target properties — consumer-not-definer of Critical Input, and
  never-asserts-tradability — held against twelve attack sequences. Two Minor
  citation-precision defects were resolved: the tradability-not-inferred rule now
  cites ADR-002-019 VTG-INV-002/§25.2 (not a raw line number), and the
  health-is-not-validity rule now cites ADR-002-018 §9 (source continuity is not
  inferred from health) rather than the mis-scoped CII-INV-013; the same
  CII-INV-013 correction was applied to RFC-003 §11 to keep the two documents
  consistent. The review is EV-L0 only and confers no acceptance or
  live-readiness.
* During the part-2 cross-RFC consistency audit, §13's RFC-007 pointer was
  corrected: protective classification is owned exclusively by the Protective
  Action Controller under ADR-002-001 §6, not "by RFC-007 and ADR-002-001." This
  aligns RFC-004 with RFC-007 §§3, 10, 12, which state that RFC-007 classifies
  nothing and supplies only the methodology the Controller evaluates. RFC-007
  retains ownership of the hedge methodology only.
