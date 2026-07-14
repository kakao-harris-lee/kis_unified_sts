# ADR-002-010 — Corporate Actions and Non-Trade State Changes

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Corporate actions, expiry and assignment, settlement and transfer, broker correction, instrument-identity change, external position mutation, attribution, risk-capacity remapping, open-order and protection impact, uncertainty containment, recovery, and evidence
- **Supersedes:** None
- **Amends:** RFC-002 §14.7 External and Non-Trade State Changes, §15 Reconciliation, and the capacity, recovery, protection, and instrument-identity prerequisites in §10, §19, §21, and §23
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-002, SAFE-004, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-022, SAFE-023, SAFE-024, SAFE-025, SAFE-030, SAFE-032, SAFE-035, SAFE-040, SAFE-041, SAFE-044, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-009 and ADR-002-011

---

## 1. Decision

The Trading Operating System SHALL represent corporate actions and other non-trade state changes as first-class, versioned economic events. They SHALL NOT be fabricated as fills, silently folded into position corrections, or treated as harmless reference-data changes.

Every non-trade event SHALL retain its own identity, provenance, effective-time model, affected instruments and accounts, transformation rules, evidence confidence, and relation to pre-event and post-event economic state.

The Reconciliation Service SHALL coordinate classification and evidence. The Position and Order Projection SHALL preserve bitemporal state and attribution. The Risk Capacity Ledger remains the sole authority that reserves, commits, releases, transfers, or remaps capacity. The Safety Control Plane governs authority reduction and re-arm. The Broker Adapter/Egress Gateway remains the final enforcement point for any required cancellation, replacement, offset, exercise instruction, or other transmitted action.

Before a known event can affect a live scope, the system SHALL either:

1. prove and pre-authorize a conservative transition within the aggregate hard envelope; or
2. block new risk and place the affected scope into restricted recovery or HALT.

When the event, transformation, broker treatment, instrument identity, effective boundary, quantity, or downstream effect is missing, stale, contradictory, or unknown, the system SHALL conservatively account all credible old and new economic effects. UNKNOWN consumes capacity and blocks new risk.

No capacity, protection, or authority may be released merely because an instrument expired, a symbol changed, a broker altered a position, a corporate-action date passed, or a local projection applied a transformation. Economic effect requires field-level evidence and reconciliation.

---

## 2. Context

Trading systems commonly derive position changes from fills. That model is incomplete. Brokers, venues, issuers, clearing systems, and account administrators can change economic state without a new trade fill.

Examples include:

- stock splits, reverse splits, and stock dividends;
- cash dividends and cash-in-lieu;
- mergers, acquisitions, spin-offs, conversions, and redemptions;
- rights, warrants, tender offers, and voluntary elections;
- symbol, identifier, listing, exchange, or contract changes;
- delisting, suspension, and trading-status changes;
- option expiry, exercise, assignment, and settlement;
- futures expiry, delivery, cash settlement, and contract conversion;
- account transfers and administrative journals;
- broker corrections, busts, fees, tax, interest, margin, and collateral adjustments;
- externally initiated position or cash changes.

These events can alter quantity, price basis, multiplier, currency, tradability, settlement obligations, margin, cash, instrument identity, open orders, protective coverage, and aggregate risk.

Sources can disagree about announcement, ex-date, record date, effective time, payable date, settlement date, ratio, rounding, eligibility, or broker treatment. A broker may apply an event before or after local reference data. A broker may also adjust, cancel, or recreate open orders without preserving local identity.

The architecture therefore requires an explicit event model and a conservative transition envelope.

---

## 3. Decision Drivers

1. Non-trade economic effects must remain distinguishable from fills.
2. Instrument and position changes must not release capacity without proof.
3. Known future events must reduce authority before their uncertainty can create unmanaged exposure.
4. Broker-side adjustment of orders and positions must be reconciled, not assumed.
5. Quantity, multiplier, currency, and instrument transformations must preserve aggregate risk conservatively.
6. Effective-time uncertainty and time recovery must not revive stale authority.
7. Event replay, correction, and reversal must be idempotent and historically reconstructable.
8. Unrecognized external state must enter unattributed quarantine and block new risk.

---

## 4. Scope and Classification

### 4.1 Corporate Actions

Issuer, exchange, or clearing events that transform an instrument, entitlement, cash flow, or holder obligation.

### 4.2 Lifecycle Events

Expiry, exercise, assignment, delivery, settlement, conversion, redemption, termination, or rollover-related changes.

A strategy-initiated rollover trade remains a trade. Exchange or broker expiry and settlement effects are non-trade events.

### 4.3 Administrative and Broker Events

Transfers, journals, corrections, bust consequences, fee, tax, interest, collateral, margin, and broker-applied adjustments.

### 4.4 Instrument and Tradability Events

Symbol, identifier, venue, contract-specification, tick, lot, multiplier, currency, listing, delisting, suspension, and session-eligibility changes.

### 4.5 Unrecognized External Changes

Any account, position, order, cash, collateral, or instrument state that cannot be attributed with sufficient confidence to a trade or recognized non-trade event.

Such changes SHALL enter `QUARANTINED_UNKNOWN` or `TRAPPED_CONSUMED` treatment under RFC-002 and ADR-002-002.

---

## 5. Non-Trade Event Identity

Every event SHALL have a durable **Non-Trade Event ID** and contain at least:

- event class and subtype;
- issuer, venue, broker, clearing, or administrative source identities;
- source event identifiers and versions;
- announcement, observation, record, ex, effective, payable, and settlement times where applicable;
- affected account, portfolio, instrument, currency, and broker scopes;
- old and new instrument identities;
- transformation legs, ratios, multipliers, prices, cash values, and rounding rules;
- eligibility and election conditions;
- broker-treatment profile and expected open-order behavior;
- evidence confidence and contradiction status per field;
- Safety Profile, Broker Capability Profile, Verification Profile, calendar, and instrument-master versions;
- workflow generation and idempotency key;
- supersession, correction, reversal, and lineage references.

Source IDs SHALL be retained. A locally generated ID SHALL NOT erase source identity or make conflicting events identical.

---

## 6. Event Knowledge and Workflow State

Non-trade event state SHALL remain orthogonal to order, exposure, capacity, authority, and evidence-confidence state.

The event workflow MAY use:

```text
OBSERVED
    -> CORROBORATING
    -> VALIDATED
    -> TRANSITION_PREPARED
    -> EFFECT_PENDING
    -> APPLIED_LOCAL
    -> RECONCILING
    -> RECONCILED

Any state -> CONFLICTED
Any state -> QUARANTINED_UNKNOWN
Any applied state -> CORRECTION_PENDING
```

`APPLIED_LOCAL` is not proof that the broker or venue applied the same effect. `RECONCILED` requires evidence sufficient under ADR-002-006.

No workflow state by itself releases capacity, closes an instrument, proves final quantity, or grants authority.

---

## 7. Source and Evidence Requirements

The Reconciliation Service SHALL evaluate each material field independently using available evidence from:

- broker account, position, order, cash, and corporate-action data;
- venue, exchange, clearing, or issuer notices;
- approved instrument-master and reference-data sources;
- authoritative calendars and contract specifications;
- custody, transfer, or administrative records;
- prior local intent, fill, and non-trade-event lineage.

Multiple feeds using one upstream vendor, parser, clock, or distribution path are common-mode and SHALL NOT be described as independent corroboration.

Evidence freshness, source capability, disagreement, sequence, completeness, and time uncertainty SHALL be retained per field. Majority vote SHALL NOT resolve conflicting semantics without source-authority rules.

If a required field cannot be established within approved confidence and freshness bounds, permissive processing is denied.

---

## 8. Effective-Time Model

The system SHALL preserve distinct announcement, observation, record, ex, effective, payable, expiry, exercise, assignment, and settlement times where applicable.

It SHALL NOT collapse them into one “corporate action date.”

Time-dependent decisions SHALL use ADR-002-008 trustworthy time and approved market-calendar semantics. If the effective boundary is ambiguous or source disagreement can change economic exposure, the affected scope SHALL block new risk before the earliest credible effective boundary and remain restricted through the latest credible completion boundary.

Clock recovery or a later source update SHALL NOT retroactively grant authority to actions denied during the uncertainty interval.

---

## 9. Conservative Transition Envelope

Before effect, the system SHALL construct a **Non-Trade Transition Envelope** containing all credible economic states during the event.

The envelope SHALL include where applicable:

- the full pre-event position and order state;
- every plausible post-event quantity, instrument, multiplier, currency, and cash leg;
- both old and new instruments when identity transition is not final;
- fractional quantity and cash-in-lieu outcomes;
- exercise, assignment, delivery, settlement, or conversion obligations;
- broker-side open-order cancellation, adjustment, duplication, or recreation;
- delayed, partial, reversed, or corrected application;
- price, margin, settlement, and market-movement bounds;
- protective-order gaps and overlaps;
- source disagreement and time uncertainty.

Risk capacity SHALL cover the maximum aggregate risk across the envelope. Favorable effects SHALL NOT be netted against uncertain adverse effects.

The Risk Capacity Ledger SHALL commit any required transition capacity before normal live authority continues through the event boundary.

---

## 10. Atomic State Transition

Within the Trading Operating System, application of a recognized event SHALL be one idempotent, versioned transition that coordinates:

- position and cash projection;
- instrument identity and contract terms;
- Risk Capacity Ledger remapping;
- aggregate and per-instrument limits;
- protective obligations and related order lineage;
- Safety Authority and Live Authorization validity;
- reconciliation expectations;
- audit and replay records.

Where one physical transaction cannot cover all stores, the implementation SHALL use a durable protocol that cannot expose a more permissive partial state. Until completion, consumers SHALL use the conservative pre/post transition envelope.

Only the Risk Capacity Ledger may mutate capacity. The event processor, instrument master, projection, reconciliation, or recovery components may propose a remap but SHALL NOT update capacity independently.

History SHALL be corrected by new versioned facts, not destructive overwrite. A correction or reversal is a new event linked to the event it supersedes.

Every material event, correction, or reversal SHALL invalidate affected ADR-002-019 Venue Constraint Snapshots and Order Admissibility Decisions. A symbol, quantity, multiplier, margin, settlement, or account remap requires a fresh exact order decision before future transmission; neither the event nor a favorable projection releases capacity.

---

## 11. Quantity, Price, Multiplier, and Currency Transformation

Every transformation SHALL specify exact units and rounding rules.

The system SHALL distinguish:

- position quantity from executable order quantity;
- raw ratio from broker-applied rounded quantity;
- fractional entitlement from tradable whole quantity;
- reference price from cost basis, settlement price, trigger price, and limit price;
- instrument multiplier from contract quantity;
- trade currency from settlement, collateral, and reporting currency.

Economic equivalence SHALL NOT be assumed from a theoretical ratio. Broker rounding, cash-in-lieu, fees, taxes, margin rules, liquidity, and execution constraints can change risk.

If the transformed state cannot be represented exactly, the residual SHALL remain explicit and capacity-consuming until reconciled.

---

## 12. Instrument Identity and Lineage

Symbol text is not instrument identity.

Instrument transitions SHALL preserve stable lineage among old and new identifiers, venues, contracts, deliverables, multipliers, and currencies. Both identities remain active in the transition envelope until broker and reference-data evidence establish the final mapping.

Open intents and orders SHALL not be silently reassigned to a new instrument. Any cancellation, replacement, or new submission requires current intent lineage, authority, capacity, Broker Capability Profile, and final egress validation.

If an instrument becomes suspended, delisted, expired, or untradeable, inability to exit SHALL be represented as trapped exposure. It SHALL not be represented as zero risk.

---

## 13. Open Orders and Protective Coverage

The system SHALL NOT assume that a broker will preserve, cancel, resize, reprice, or remap an open order correctly across a non-trade event.

For every affected order it SHALL establish:

- broker order identity before and after the event;
- broker adjustment or cancellation semantics from the active capability profile;
- remaining and filled quantity;
- transformed instrument, side, price, trigger, lot, and multiplier semantics;
- whether the order remains executable;
- whether the order still conforms to its original intent;
- whether it satisfies a current protective obligation.

Potentially live old and new orders remain in aggregate risk and capacity until Final Quantity Proof and reconciliation establish otherwise.

If protective coverage must be changed, ADR-002-011 governs cancellation, replacement, gap, overlap, and capacity. Cancel ACK is not Final Quantity Proof, and priority is not reserved protective capacity.

---

## 14. Derivative Expiry, Exercise, Assignment, and Settlement

Derivative lifecycle processing SHALL model every credible resulting leg, including:

- position expiration with no further obligation;
- cash settlement;
- physical delivery or receipt;
- exercise or assignment creating underlying exposure;
- partial assignment;
- delayed broker notice;
- currency, multiplier, strike, and settlement-price effects;
- insufficient cash, collateral, borrow, or delivery capacity.

Absence of an assignment or exercise report at a local deadline is not proof that no assignment or exercise occurred.

Any possible resulting exposure SHALL consume capacity before the event boundary. If the system cannot support or prove a safe outcome, new risk in the affected scope SHALL be blocked early enough to prevent entry into the unsafe lifecycle state.

---

## 15. Voluntary Actions and Elections

Tender, conversion, rights, exercise, and similar elections that require an instruction SHALL use explicit governed intent and authorization.

An operator selection, UI action, or reference-data flag SHALL NOT itself transmit an instruction. Transmission requires current capacity, authority, time, capability, identity, and final egress validation.

Unconfirmed election acceptance remains UNKNOWN. Deadline expiry does not prove acceptance or non-acceptance, and it does not erase resulting economic possibilities.

---

## 16. Broker Corrections, Transfers, and Administrative Changes

Broker corrections, trade bust consequences, transfers, journals, fees, tax, interest, collateral, and margin adjustments SHALL retain source provenance and effective time.

ADR-002-030 governs the resulting Economic Obligation Records, Post-Trade Obligation Generation, statement coverage, field-specific finality, breaks, corrections, and conservative PTOL-to-RCL transition. This ADR owns the non-trade event and transformation identity; ADR-002-030 owns the obligation-lifecycle serialization. Neither event recognition nor PTOL state may declare external truth, mutate RCL capacity, collapse Final Quantity Proof into settlement or legal-title finality, or expire economic effect.

The system SHALL not relabel an unexplained position change as a correction merely to make reconciliation pass.

A recognized correction may alter prior economic state, but local history SHALL preserve both the original observation and correcting event. Capacity and authority shall be recomputed from the corrected transition envelope.

External transfer or adjustment that cannot be attributed confidently becomes unattributed exposure or cash. New risk remains blocked for the affected aggregate scope.

---

## 17. Authority Invalidation and Pre-Event Controls

A known event SHALL invalidate normal live authority when it can change any bound or assumption used by the current authorization, including:

- instrument identity or tradability;
- position quantity or multiplier;
- currency, cash, collateral, margin, or settlement obligation;
- open-order conformance;
- protective coverage;
- aggregate capacity;
- market session or calendar interpretation;
- broker capability or event-processing confidence.

The system MAY issue a new, narrower authorization after the conservative transition envelope and required capacity are approved.

Event completion, restored reference data, broker reconciliation, or service recovery SHALL NOT automatically re-arm normal live operation. ADR-002-007 applies.

---

## 18. Unknown and Conflicting Events

When broker state changes without sufficient attribution, or event sources conflict materially, the system SHALL:

1. retain the observed external state;
2. create or update an unattributed non-trade event record;
3. mark affected fields `UNKNOWN` or `CONFLICTED`;
4. compute the maximum credible aggregate exposure and capacity;
5. block new risk in the affected scope;
6. preserve potentially live order quantity;
7. permit only newly authorized recovery or protective action;
8. escalate containment if the aggregate scope cannot be bounded.

An operator explanation, document, replay, or manual label is not sufficient to remove UNKNOWN without supporting evidence.

---

## 19. Startup, Recovery, and Replay

Startup and recovery SHALL load all pending, effective, applied, conflicted, corrected, and unreconciled non-trade events before granting normal live authority.

These records are mandatory ADR-002-017 Recovery Obligations. An unknown event feed, effective-time interval, instrument mapping, correction lineage, or open-order adjustment keeps the affected Recovery Scope conservative and non-live.

Recovery SHALL:

- preserve event idempotency and source lineage;
- restore pre/post transition envelopes and RCL commitments;
- reconcile instrument, position, cash, order, protection, and settlement state;
- reapply events only through idempotent version checks;
- fence stale event and ledger writers;
- retain unknown old and new economic possibilities;
- obtain new authority for any external action;
- require governed re-arm.

Replay may reconstruct a projection or reveal a defect. It SHALL NOT itself prove that the broker state is correct or authorize capacity release.

---

## 20. Evidence and Observability

The system SHALL retain:

- every event version, source, field-level confidence, and contradiction;
- all relevant time boundaries and trusted-time evidence;
- pre-event, post-event, and transition-envelope states;
- instrument and event lineage;
- RCL capacity reservations, commitments, remaps, and release proof;
- open-order and protective-coverage assessments;
- broker capability and treatment evidence;
- authority invalidation, egress, containment, recovery, and re-arm decisions;
- corrections, reversals, operator elections, and independent reviews.

Required metrics include pending-event age, conflicted-field age, unreconciled transition duration, capacity held for non-trade uncertainty, unknown external adjustments, open-order conformance failures, protection gaps, event corrections, and stale-authority denials.

Written cases, event catalogs, and successful replay are not completed evidence. Acceptance requires registered, executed, retained, and independently reviewed evidence under VER-002-001.

---

## 21. Acceptance Cases

The following cases are mandatory and map one-to-one to `NT-EV-001` through `NT-EV-012`. Registration is not execution; every item remains incomplete until its required evidence is executed, retained, and independently reviewed:

| ID | Required demonstration |
|---|---|
| `NT-AC-001` | Split and reverse-split transformations preserve quantity, rounding, price, order, protection, and capacity conservatively |
| `NT-AC-002` | Merger or spin-off with multiple instrument and cash legs uses the worst credible transition envelope |
| `NT-AC-003` | Symbol or identifier change preserves lineage and cannot silently redirect existing intent or orders |
| `NT-AC-004` | Option exercise or assignment can create underlying exposure despite delayed or missing broker notice and consumes prior capacity |
| `NT-AC-005` | Futures expiry, delivery, or cash settlement cannot be treated as zero risk merely because trading ended |
| `NT-AC-006` | Broker-adjusted, cancelled, duplicated, or recreated open orders remain conservative until field-level reconciliation and Final Quantity Proof |
| `NT-AC-007` | Conflicting effective times block new risk across the earliest-to-latest credible event window |
| `NT-AC-008` | Broker correction, transfer, or external position change remains unattributed and capacity-consuming until evidenced |
| `NT-AC-009` | Partial local application cannot expose a more permissive capacity, protection, or authority state |
| `NT-AC-010` | Correction and reversal preserve history and idempotency without double-applying economic effect |
| `NT-AC-011` | Restart and replay preserve pending events, capacity, UNKNOWN state, and stale-writer fencing |
| `NT-AC-012` | Event completion or restored data cannot automatically re-arm or revive prior authorization |

---

## 22. Rejected Alternatives

### 22.1 “Represent every position change as a fill”

Rejected. It corrupts intent lineage, order identity, reconciliation, and evidence semantics.

### 22.2 “Reference data can update the position in place”

Rejected. Reference data is evidence, not capacity or economic-state mutation authority.

### 22.3 “The broker will adjust all open orders correctly”

Rejected. Broker treatment is capability-specific and must be reconciled per order.

### 22.4 “Expired or delisted means no risk”

Rejected. Settlement, delivery, assignment, trapped exposure, and stale orders may remain.

### 22.5 “Apply the most likely ratio and correct later”

Rejected. Later audit or replay does not prevent an unsafe intermediate state.

### 22.6 “Net favorable and adverse unknown effects”

Rejected. UNKNOWN does not create permission for new risk.

### 22.7 “Recovery can re-arm when the event feed is healthy”

Rejected. Restored service or time health does not revive prior authority.

---

## 23. Consequences

### 23.1 Positive

- Non-trade effects remain attributable and distinct from fills.
- Capacity remains conservative across identity and quantity transformations.
- Instrument, order, protection, and settlement dependencies become explicit.
- Conflicting timing and broker treatment fail closed.
- Corrections and replay preserve historical evidence without silently rewriting authority.

### 23.2 Negative

- More data sources and event-specific transformation logic are required.
- Capacity may remain committed for long settlement or reconciliation intervals.
- Some instruments or event windows will be ineligible for new risk.
- Corporate-action and derivative-lifecycle evidence requires broker-specific testing.

These costs are accepted because unmodeled external mutation can create exposure without any normal order path.

---

## 24. Traceability

| Requirement | ADR coverage |
|---|---|
| SAFE-002, SAFE-004, SAFE-013 | Unmanaged exposure and conservative transition-envelope risk |
| SAFE-011 | Governed instruction and final egress enforcement |
| SAFE-015 | RCL-only capacity remap and release |
| SAFE-020 | Intent, order, instrument, and event lineage |
| SAFE-022, SAFE-023, SAFE-024 | Reconciliation, field evidence, and external-state attribution |
| SAFE-025 | Partial, delayed, asynchronous, and corrected effects |
| SAFE-030, SAFE-032, SAFE-035 | Profile, tradability, session, calendar, and trustworthy-time rules |
| SAFE-040, SAFE-041, SAFE-044 | Protection, authority invalidation, startup, recovery, and re-arm |
| SAFE-048, SAFE-050 | Partition, stale writer, configuration, and deployment behavior |
| SAFE-051, SAFE-052 | Executed evidence and reconstructable event replay |

---

## 25. Open Questions

1. Which event sources and source-authority rules will be approved for each first-live instrument class?
2. Which broker-specific open-order adjustment semantics can be proven?
3. Which voluntary actions, derivative lifecycle events, and delivery obligations are in initial restricted-live scope?
4. Which transition protocol will preserve conservative state across projection, instrument, capacity, and authority stores?
5. Which numeric pre-event, reconciliation, settlement, and evidence-freshness bounds will be approved?
6. Which corporate-action and non-trade residual risks require explicit human acceptance?

Open questions may only narrow instrument or event scope or block acceptance. They SHALL NOT permit optimistic transformation.

---

## 26. Approval Gate

This ADR SHALL remain **Proposed** until all of the following are complete:

1. initial supported event and instrument scopes are explicitly approved;
2. source-authority, broker-treatment, transition, and RCL remap mechanisms are selected;
3. numeric event, freshness, reconciliation, and settlement bounds receive human approval;
4. dedicated evidence items are registered for every `NT-AC-*` case;
5. required EV-L1, EV-L2, and EV-L3 evidence is executed across correction and failure paths;
6. ADR-002-016 preserves raw source events, corrections, transition lineage, gaps, conservative ambiguity, and deterministic replay without rewriting external facts, and applicable ERI evidence passes;
7. ADR-002-019 invalidates and rebuilds exact venue/instrument/account/margin/settlement/order decisions across initial events, corrections, reversals, and recovery, and applicable VTG evidence passes;
8. source common modes, broker residuals, and delivery obligations receive independent review;
9. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Authorship of this ADR does not prove non-trade-event safety and does not authorize restricted-live or production operation.
