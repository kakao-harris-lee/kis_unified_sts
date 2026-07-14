# ADR-002-019 — Venue, Session, Tradability, and Broker Constraint Gate

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Venue and market state, session phase, instrument tradability, price and quantity constraints, order-type and time-in-force restrictions, account eligibility, margin and settlement constraints, broker restrictions, exact order-admissibility decisions, invalidation, final-egress currentness, degraded and protective behavior, recovery, evidence, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-032 and SAFE-033; RFC-002 §§7.1–7.2, 10.1, 10.7–10.8, 13.6, 15, 20, 21, 22, and 29; ADR-002-004 §§8.10, 8.13–8.17, 11, 12, 17–20, and 25
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-020 through SAFE-025, SAFE-030 through SAFE-035, SAFE-040, SAFE-041, SAFE-043, SAFE-044, SAFE-046, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-002 through ADR-002-018

---

## 1. Decision

Every proposed broker action SHALL be evaluated against the current venue, market, instrument, contract, session, tradability, halt, price-limit, tick, lot, quantity, order-type, time-in-force, auction, account, short-sale or borrow, margin, settlement, currency, expiration, broker, and execution constraints applicable to the exact action. A quote, open connection, broker login, accepted market-data subscription, recent trade, scheduled session, or operator belief SHALL NOT prove that an order is admissible.

The TOS SHALL govern these constraints through an immutable **Venue Constraint Policy**, an immutable **Venue Constraint Snapshot**, and a purpose-bound **Order Admissibility Decision**. The decision SHALL bind the exact environment, broker, account, venue, market segment, instrument and contract identity, side, position effect, action class, quantity, price or pricing instruction, order type, time in force, session phase, settlement and margin context, Critical Input Snapshot, Decision Context Capsule, policy generation, constraint generation, maximum age, and invalidation predicates.

An Order Admissibility Decision is a safety fact, not permission. It cannot approve an Intent, commit or release capacity, issue Safety Authority or Live Authorization, classify an action as protective, create or consume a Transmission Capability, transmit to a broker, clear HALT, or re-arm live operation. Those authorities remain separately owned.

`ADMISSIBLE` means only that the exact order shape passed the declared constraint checks at the decision point. It does not mean the order is economically safe, approved, capacity-covered, currently authorized, accepted by the broker, filled, or capable of reducing exposure. All other safety gates remain mandatory.

The TOS SHALL distinguish ordinary new-risk admission, ordinary reduction, cancellation, protective maintenance, protective replacement, emergency containment, and reconciliation queries. An action's label, intent, side, or expected net effect SHALL NOT exempt it from current constraints. The system SHALL NOT assume that a requested exit, reduce-only action, cancel, or protective action is executable.

Unknown, stale, conflicting, discontinuous, unsupported, or unverifiable constraint state SHALL block ordinary new risk. It SHALL NOT create headroom, capacity, or protective permission. If uncertainty can conceal an accepted order, fill, position, margin obligation, settlement obligation, or reversal, the worst credible economic effect remains capacity-consuming until resolved by the authoritative state and proof rules.

Protective or containment activity under a restrictive venue state MAY proceed only when a separately authorized exact path is positively proven to be supported for that account, instrument, venue phase, order shape, broker capability, and current constraint generation; its full credible intermediate and reversal effects must be capacity-covered. Priority is not reserved protective capacity, and a “protective” label is not proof of admissibility.

Material changes to venue state, session phase, halt or suspension state, price bands, instrument eligibility, order rules, account permissions, borrow, margin, settlement, broker capability, or source continuity SHALL invalidate every affected unconsumed Order Admissibility Decision and dependent future permission before a new-risk send. Constraint expiry or invalidation never expires an order, fill, exposure, UNKNOWN state, settlement obligation, or capacity commitment already capable of economic effect.

The Broker Adapter / Broker Egress Gateway remains the final enforcement point. At the irreversible send boundary it SHALL validate the exact Order Admissibility Decision and actively establish current Venue Constraint Policy, Constraint Generation, session and tradability state, broker-capability profile, scope, age, and invalidation status. TTL, schedule, heartbeat, cached health, last-known state, eventual consistency, or absence of a halt/correction event is not currentness proof. Failure to establish currentness denies transmission.

ADR-002-024 defines the per-send ordering mechanism. Constraint Generation, exact decision, session/tradability/account/broker floors, and invalidation are dimensions in the Safety Currentness Vector; a restrictive transition sets the local latch to `DENY_LATCHED` and is ordered against capability claim and `SEND_STARTED`.

Venue reopen, session transition, halt release, broker recovery, margin restoration, borrow restoration, reconnect, restart, failover, deployment, clock recovery, or constraint-service recovery cannot revive an older decision or authority. A fresh decision and the complete governed authorization chain are required. No automatic re-arm is permitted.

---

## 2. Context

RFC-001 SAFE-032 requires current venue and tradability evaluation and explicitly forbids assuming that an exit can execute. RFC-001 SAFE-033 requires exact Intent-to-order conformance. ADR-002-004 defines what broker capabilities have been evidenced, while ADR-002-018 governs the integrity and provenance of the inputs used to make decisions.

Those rules do not yet define one order-specific gate. Without it, an implementation can:

- treat a market calendar as proof that the venue is currently accepting the intended order type;
- infer tradability from a recent quote, trade, or broker connection;
- reuse a pre-open or continuous-session decision in an auction, halt, reopen, closing, or after-hours phase;
- validate the symbol but miss the exact contract, market segment, price band, tick, lot, quantity, or time-in-force rule;
- call an order an exit even though it can reverse exposure, violate reduce-only semantics, or be rejected by the venue;
- rely on an account-level margin or borrow snapshot that does not cover the exact order and settlement state;
- treat a broker rejection as harmless even though the send may have been accepted, partially accepted, or duplicated;
- let the constraint evaluator directly approve, reserve, classify, or transmit;
- accept a cached `TRADABLE` flag after a halt, rule change, account restriction, or source discontinuity;
- assume that reopening the venue or restoring a broker session revives the old authorization;
- reserve no protection capacity because protective traffic was merely prioritized;
- use logs, alerts, replay, or post-trade rejection statistics instead of pre-send prevention.

This ADR closes those paths while keeping venue constraint evaluation separate from risk capacity, authorization, broker transmission, and broker evidence finality.

---

## 3. Decision Drivers

1. Admissibility is specific to the exact order, account, instrument, venue phase, and broker path.
2. Venue and broker rules can change faster than configuration deployment or human review.
3. Market-data health and venue tradability are different facts.
4. Session calendars are expectations, not authoritative current state.
5. Exit, reduce-only, cancel, and protective actions have constraints and failure modes of their own.
6. Broker capability evidence must constrain, not expand, venue claims.
7. Margin, settlement, borrow, and account permissions can invalidate an otherwise syntactically valid order.
8. Constraint changes must invalidate future permission without erasing existing economic effects.
9. Final egress must prevent stale-decision, wrong-scope, and order-shape substitution.
10. Recovery and venue reopening must never automatically re-arm live operation.

---

## 4. Scope and Non-Scope

This ADR decides:

- Venue Constraint Policy and source requirements;
- venue, market-segment, session-phase, halt, suspension, auction, and tradability states;
- instrument, contract, tick, lot, quantity, price-band, order-type, and time-in-force rules;
- account, permission, borrow, margin, settlement, currency, and expiration constraints;
- immutable Venue Constraint Snapshots and exact Order Admissibility Decisions;
- independent validation, common-mode disclosure, and constraint dependency closure;
- invalidation, final-egress currentness, send-race, degraded, protective, recovery, and evidence rules;
- acceptance cases and approval gates.

This ADR does not decide:

- alpha, expected return, strategy selection, or desired execution style;
- broker capability semantics or Final Quantity Proof recipes, which remain ADR-002-004;
- Critical Input provenance and Decision Context construction, which remain ADR-002-018;
- trustworthy-time implementation, which remains ADR-002-008;
- corporate-action and non-trade economic transitions, which remain ADR-002-010;
- protective replacement workflow, which remains ADR-002-011;
- risk calculation, capacity mutation, or release, which remain ADR-002-002 and ADR-002-012;
- human approval, configuration activation, live authorization, or re-arm, which remain ADR-002-015, ADR-002-014, ADR-002-007, and ADR-002-017;
- concrete venue calendar, exchange feed, broker, margin, borrow, reference-data, or rule-engine products;
- numeric freshness, detection, invalidation, or propagation bounds, which require approved policy and Verification Profile values.

---

## 5. Definitions

### 5.1 Venue Constraint Policy

An immutable, authenticated, separately governed artifact that defines constraint classes, approved sources, phase and state machines, exact order fields, decision rules, conservative defaults, dependency and invalidation rules, permitted scopes, evidence requirements, and failure responses.

### 5.2 Venue Constraint Snapshot

An immutable, time- and scope-bounded evaluation of the exact venue, session, tradability, instrument, account, margin, settlement, and broker constraints relevant to a declared action family. It binds Critical Input provenance and uncertainty but grants no authority.

### 5.3 Constraint Generation

A monotonic restrictive generation for one constraint domain. A newer halt, suspension, restriction, source discontinuity, account restriction, or policy generation fences older decisions for future new-risk transmission.

### 5.4 Order Admissibility Decision

An immutable canonical result for one exact broker-request shape. Its result is one of `ADMISSIBLE`, `RESTRICTED_PROTECTIVE_ONLY`, `INADMISSIBLE`, or `UNKNOWN`. No result creates economic authority.

### 5.5 Session Phase

The explicit venue state in which a rule set applies, such as closed, pre-open, opening auction, continuous trading, volatility interruption, halt, reopening auction, closing auction, post-close, or approved after-hours phase. Names are policy-defined and never imply permission by themselves.

### 5.6 Tradability State

The current order-specific ability of the declared venue and broker path to accept the declared action under known constraints. `TRADABLE` is not a global instrument boolean.

### 5.7 Constraint Dependency Closure

The complete set of orders, approvals, authorizations, accounts, instruments, positions, protective obligations, and capacity dimensions whose future behavior can change when one constraint changes.

### 5.8 Material Constraint Change

Any change that may alter order identity, accepted syntax, allowed phase, price or quantity, direction or position effect, margin or settlement obligation, broker routing, approval result, capacity need, protective sufficiency, or evidence strength. Unknown materiality is material.

### 5.9 Constraint Currentness Proof

Evidence obtained at the consumer boundary that positively establishes the current applicable policy, generation, scope, age, state, and invalidation status within approved bounds. A cached permissive assertion is not proof.

---

## 6. Safety Invariants

### VTG-INV-001 — Every Action Has an Exact Constraint Decision

No broker-directed action is eligible for transmission without an exact Order Admissibility Decision for its complete order shape and scope.

### VTG-INV-002 — Tradability Is Not Inferred

Calendar time, quote flow, recent trades, connectivity, login, broker health, or absence of a restriction event never proves order-specific tradability.

### VTG-INV-003 — Exit Is Not Assumed Executable

Exit, reduce-only, cancel, replacement, and protective actions are independently constrained and may be `INADMISSIBLE` or `UNKNOWN`.

### VTG-INV-004 — Exact Immutable Binding

Proposal, approval, Intent, capacity analysis, authorization, capability, Commit Proof, and egress bind the same exact Snapshot and Decision identities; mutation requires a new chain.

### VTG-INV-005 — Ambiguity Is Restrictive

Missing, stale, conflicting, unsupported, discontinuous, or unverifiable constraint state blocks ordinary new risk and cannot be replaced with a permissive default.

### VTG-INV-006 — Broker Capability Is a Ceiling

The active Broker Capability Profile may reduce or prohibit scope. It never proves current venue state and cannot expand policy, authorization, capacity, or Hard Safety Envelope limits.

### VTG-INV-007 — Protective Labels Do Not Bypass Constraints

Protective or containment use requires exact current admissibility, separate protective classification and authority, and conservative capacity for every credible intermediate effect.

### VTG-INV-008 — Constraint Change Invalidates Future Permission

A material constraint change fences affected unconsumed decisions and downstream permission before future new-risk send.

### VTG-INV-009 — Economic Effect Outlives Constraint Artifacts

Decision, policy, session, borrow, margin, or constraint expiry/invalidation never expires orders, fills, exposure, settlement obligations, UNKNOWN state, or capacity commitments.

### VTG-INV-010 — Final Egress Actively Fences Currentness

No new-risk broker byte is sent unless the exact decision and current policy, generation, phase, tradability, broker capability, age, scope, and invalidation status are positively established at the irreversible boundary.

### VTG-INV-011 — Constraint Evaluation Has No Economic Authority

Constraint evaluation cannot approve, mutate capacity, issue authority, classify protection, transmit, clear HALT, or re-arm.

### VTG-INV-012 — UNKNOWN Consumes Conservatively

Where constraint uncertainty can hide an existing or potentially-live effect, its worst credible effect remains capacity-consuming and cannot create permission.

### VTG-INV-013 — Reopen and Recovery Do Not Revive

Venue reopen, halt release, account restoration, reconnect, restart, failover, clock recovery, or constraint-service recovery cannot revive a previous decision or authority.

### VTG-INV-014 — Evidence Does Not Replace Prevention

Documentation, broker rejections, logs, dashboards, audit, replay, alerts, and later reconciliation cannot substitute for pre-send enforcement.

---

## 7. Authority Ownership and Separation

| Function | Owning authority | Prohibited collapse |
|---|---|---|
| Define and approve constraint policy | Venue Constraint Policy governance under ADR-002-014 | strategy, evaluator, broker adapter, or operator cannot self-activate a permissive rule |
| Ingest venue/account/broker constraint evidence | authenticated Critical Input paths under ADR-002-018 | ingress cannot declare an order admissible |
| Build Snapshot and evaluate exact order | Venue Constraint Gate | cannot approve, reserve, arm, classify protection, or transmit |
| Assess broker semantics and assurance | Broker Capability governance under ADR-002-004 | a capability profile cannot declare current venue state |
| Approve action | Independent Approval Service | an admissibility result is only one required input |
| Evaluate/commit capacity | Aggregate Risk Authority / RCL respectively | constraint evaluator cannot mutate or release capacity |
| Classify protective action | Protective Action Controller | label cannot waive venue constraints |
| Issue Safety Authority, Live Authorization, and capability | ADR-002-003/007 authorities | constraint health cannot issue or revive authority |
| Enforce broker send | ADR-002-013 final egress | upstream `ADMISSIBLE` cannot bypass final currentness or exact-request checks |
| Preserve evidence and replay | ADR-002-016 services | rejection history or replay cannot authorize current action |
| Recover and re-arm | ADR-002-017/007/015 workflow | venue or broker recovery cannot reopen live scope |

The Venue Constraint Gate SHALL NOT hold a usable live broker credential, signer, session, or broker-order route merely because it queries broker or venue constraints.

---

## 8. Venue Constraint Policy

The policy SHALL declare, at minimum:

- environment, broker, account, venue, market segment, product, instrument, and contract scope;
- source identities, continuity semantics, schema, mappings, unit, scale, and trustworthy-time requirements;
- session-phase state machine, holidays, exceptional closures, auctions, halts, volatility interruptions, reopen, and after-hours rules;
- instrument listing, suspension, expiration, roll, exercise, assignment, settlement, and corporate-action dependencies;
- price bands, dynamic and static limits, tick tables, quantity and notional limits, lot rules, minimums, and rounding policy;
- supported sides, position effects, order types, time-in-force values, routing instructions, and amend/cancel rules;
- account permissions, product eligibility, short-sale/borrow, locate, margin, collateral, buying power, currency, and settlement requirements;
- broker capability profile and assurance-level prerequisites;
- independent-validation and common-mode requirements;
- exact decision fields, maximum age, dependency closure, material-change and invalidation rules;
- conservative failure response, protective-only restrictions, evidence class, approved live scope, and escalation.

Policy activation follows ADR-002-014. Repository merge, signature, distribution, deployment, broker login, venue open, or successful dry run is not activation and does not re-arm.

Missing policy coverage, unsupported enum, ambiguous precedence, unapproved source, or unknown materiality produces `UNKNOWN` or `INADMISSIBLE`, never a permissive default.

---

## 9. Constraint Sources, Provenance, and Continuity

Every constraint fact is a Critical Input under ADR-002-018 and SHALL retain:

- source principal, provider, endpoint, environment, account, venue, and product scope;
- Source Continuity Identity, native revision/sequence, effective time, receipt ordering, and uncertainty;
- schema, semantic-contract, mapping, parser, policy, configuration, deployment, and evidence generations;
- raw payload digest and transformation lineage;
- conflict, correction, supersession, retraction, and predecessor links.

Constraint sources may include venue notices and status feeds, market/reference feeds, approved calendars, broker account and instrument queries, margin and borrow services, settlement systems, and governed manual observations. Source names do not establish authority; policy decides precedence and corroboration.

A calendar is a baseline expectation. A quote or trade is an observation. A broker query is broker evidence. None alone proves current admissibility unless the active policy explicitly defines the fact, source semantics, bound, independence, and failure response.

Restart, reconnect, endpoint or credential substitution, sequence reset, rollback, failover, missed page, stale cache, or unverifiable continuity creates a new continuity identity or explicit gap. Unknown continuity invalidates affected future decisions.

---

## 10. Venue and Session State

The Venue Constraint Snapshot SHALL represent the current declared Session Phase and all relevant transition evidence. Scheduled time SHALL NOT be used as the sole proof of phase when unscheduled closure, delayed open, auction extension, volatility interruption, halt, suspension, or venue incident is credible.

Every phase transition SHALL be ordered by trustworthy time and Constraint Generation. Cross-host monotonic values SHALL NOT be directly subtracted. Consumer-local receipt anchors and conservative transport uncertainty follow ADR-002-008.

Phase-specific rules SHALL be explicit. An order approved for continuous trading cannot be reused in an opening auction, volatility auction, reopening auction, closing auction, after-hours session, or next trading day unless the policy proves identical semantics and a fresh exact decision is issued.

An observed `OPEN`, `RESUMED`, or equivalent source state is an input, not permission. Contradictory venue, broker, calendar, and market observations remain `UNKNOWN` until policy-defined resolution; majority or newest-arrival selection is not automatically authoritative.

---

## 11. Instrument, Contract, and Tradability State

The Snapshot SHALL bind canonical instrument identity and every routing-relevant alias, venue listing, market segment, contract month, product type, currency, multiplier, expiration, exercise/assignment state, settlement method, and account mapping.

Tradability SHALL be evaluated for the exact action. At minimum, it SHALL distinguish:

- new long or short risk;
- increase, decrease, close, and reversal potential;
- cancel, amend, replace, and reduce-only semantics;
- protective maintenance and emergency containment;
- session and venue routing alternatives.

An instrument may be quoteable but not orderable, sellable but not shortable, cancellable but not replaceable, closeable only with a specific position effect, or restricted for one account or broker path. A global `tradable=true` field is insufficient.

Corporate actions, expiry, assignment, exercise, symbol remap, contract roll, listing change, or non-trade position change invokes ADR-002-010 and invalidates dependent decisions. The Gate does not infer that a favorable remap or reduced position releases capacity.

---

## 12. Price, Quantity, and Order-Shape Constraints

The exact decision SHALL validate, without permissive rounding or substitution:

- price representation, currency, unit, scale, sign, and decimal precision;
- static and dynamic price limits, collar, auction range, and reference-price generation;
- tick table and boundary transitions;
- quantity unit, lot, minimum, maximum, step, notional, odd-lot, and fractional rules;
- side, direction, position effect, reduce-only/close-only behavior, and reversal risk;
- order type, pricing instruction, time in force, expiry, trigger, peg, discretionary, routing, and venue-specific flags;
- cancel, amend, and replace restrictions and any overlap or protection gap.

Rounding that changes price, quantity, direction, risk, or authorized economic effect creates a new broker-request shape and requires a new exact decision and any affected approval, capacity, authority, capability, and proof artifacts.

Broker-side validation is defense in depth. Expected rejection does not authorize sending a known-invalid or unproven order.

---

## 13. Account, Margin, Borrow, Settlement, and Broker Constraints

The Snapshot SHALL bind the exact account and subaccount, legal and tax classification where safety-relevant, product permission, trading and settlement currency, cash/collateral, margin model and generation, borrow/locate state, short-sale marking, settlement calendar, pending settlement, broker restriction, and account-level order or position limits.

Margin, buying power, borrow availability, or account eligibility is not inferred from a stale balance, a previous successful order, or the absence of a broker error. Conflicting account, order, fill, position, margin, borrow, and settlement evidence remains conservative under ADR-002-006.

ADR-002-030 Post-Trade Finality Policy, Post-Trade Obligation Generation, complete Active Economic Obligation Set, Statement Coverage Manifest, unresolved breaks/corrections, and field-specific settlement/cash/collateral/borrow/custody finality are account-constraint inputs where applicable. A fill, Final Quantity Proof, flat position, statement balance, scheduled date, or PTOL state never proves current order eligibility or creates headroom; missing or stale post-trade state makes the affected constraint `UNKNOWN` or `INADMISSIBLE`.

The Broker Capability Profile is a required ceiling on live scope and SHALL match the exact broker, API, environment, account type, market, order type, session, and relevant capability generation. `BEST_EFFORT`, `UNAVAILABLE`, expired, contradictory, or insufficiently evidenced capability cannot be promoted by the Gate.

Rate, session, credential, and connection budgets are constraints, not reserved protective capacity. Shared or priority-only resources retain their guarantee class under ADR-002-001 and ADR-002-004.

---

## 14. Snapshot and Exact Order Admissibility Decision

Before approval and again for any changed broker-request shape, the Gate SHALL evaluate the exact ADR-002-020 candidate Canonical Broker Command and construct or select an immutable Snapshot and issue a canonical decision containing at least:

- policy identity, version, generation, digest, approval state, and scope;
- Constraint Generation and Decision Context Capsule identity/digest;
- exact source continuity, observation, mapping, schema, time-health, and consistency-cut identities;
- exact broker, environment, account, venue, market segment, instrument, contract, side, position effect, action class, quantity, price instruction, order type, time in force, session phase, and routing fields;
- exact candidate Canonical Broker Command identity/digest and Order Construction Policy/Construction Generation;
- relevant price, tick, lot, margin, borrow, settlement, account, and broker-capability facts;
- result, failed or unknown predicates, uncertainty, maximum age, issue and expiry evidence, invalidation predicates, and dependency closure;
- evaluator identity, software/build, configuration, deployment, and evidence generations;
- explicit non-authorizing flags.

The canonical digest SHALL cover all fields that can change the decision or economic effect. Decisions cannot be patched, partially refreshed, unioned, widened, or silently recomputed. Any material field change creates a new Snapshot or decision and repeats every affected downstream gate.

The policy, not a proposer or consumer, determines materiality and dependency closure. Unknown applicability or materiality is restrictive.

---

## 15. Independent Validation and Common-Mode Analysis

Independent approval SHALL validate the safety-critical constraint facts needed for the exact action without relying solely on the proposer or Gate's derived result.

Shared venue feed, broker endpoint, calendar vendor, mapping table, margin library, borrow service, cache, parser, administrator, credential, network path, cloud region, deployment, or rule engine is a common-mode dependency. Two services that consume the same corrupted dependency do not provide independent corroboration.

Where independent corroboration is unavailable, SAFE-034 requires separate residual-risk approval, additional checks, explicit failure-domain disclosure, and reduced or prohibited live scope. The proposer, Gate, broker adapter, or data owner cannot approve its own exception.

Common-mode analysis SHALL include simultaneous stale-open state, incorrect price band or tick, wrong contract/account mapping, margin or borrow overstatement, broker-capability drift, and correction/invalidation loss.

---

## 16. Binding Through Approval, Capacity, Authority, and Egress

The exact Snapshot and Order Admissibility Decision identity/digest SHALL be bound into every affected:

1. proposal and Decision Context Capsule;
2. independent approval and Human Approval Set where required;
3. Intent and broker-request shape;
4. candidate Canonical Broker Command and later Order Conformance Proof;
5. capacity request, commitment, and conservative intermediate-state analysis;
6. Live Authorization and per-action Transmission Capability claims;
7. Commit Proof and durable egress journal record;
8. broker request and response evidence;
9. reconciliation, correction, invalidation, incident, and replay evidence.

The RCL remains the sole capacity mutation and serialization authority. Decision expiry, rejection, or invalidation cannot release capacity for an order or attempt that may already have economic effect.

Every consumer SHALL reject missing, mismatched, stale, wrong-scope, wrong-environment, superseded, invalidated, or unverifiable bindings. A more permissive policy, Snapshot, decision, profile, price band, margin fact, or session state cannot be silently substituted.

---

## 17. Final-Egress Currentness and Send Race

For every risk-relevant send, final egress SHALL, at the last reversible point before the first broker-directed byte:

1. verify the exact ADR-002-020 Canonical Broker Command, Order Conformance Proof, Economic Effect Envelope, and actual outbound representation against Intent, approval, capacity, authority, capability, Commit Proof, Decision Context Capsule, Snapshot, and Order Admissibility Decision;
2. actively establish the current Venue Constraint Policy and Constraint Generation;
3. actively establish current session phase, halt/suspension/tradability state, account eligibility, and relevant broker-capability generation;
4. verify approved age and uncertainty bounds using ADR-002-008 time evidence;
5. verify no material correction, supersession, restriction, or invalidation affects the dependency closure;
6. reject any unsupported field, rounding, mutation, widening, or scope mismatch;
7. enforce HALT, Recovery Generation, authority epoch, writer epoch, configuration, context, and egress-generation fences from the governing ADRs;
8. durably claim the single-use capability and record `SEND_STARTED` under ADR-002-013 before the irreversible send.

Cached permissive state, TTL, schedule, heartbeat, service health, broker connectivity, last-known generation, eventual consistency, or absence of a halt/restriction event SHALL NOT establish currentness. If the active-currentness path is unavailable, contradictory, cyclic, stale, or outside approved bounds, the send is denied.

The design SHALL bound the race between the final currentness decision and first broker-directed byte. If ordering against a concurrent restriction cannot be proved, the attempt is potentially live, all credible effects remain capacity-covered, and no blind retry is permitted. Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof.

Final egress verifies facts and conformance; it does not invent a strategy, widen an Intent, recalculate permission with more favorable inputs, or turn an inadmissible action into a protective one.

---

## 18. Change, Correction, and Continuous Invalidation

A material constraint change SHALL create a newer restrictive Constraint Generation and invalidate the complete affected dependency closure. Triggers include:

- unscheduled closure, delayed open, auction change, halt, suspension, volatility interruption, reopen, or session transition;
- listing, contract, expiration, settlement, corporate-action, mapping, unit, multiplier, currency, tick, lot, quantity, price-band, order-type, or time-in-force change;
- account restriction, product permission, borrow, locate, margin, collateral, settlement, credential, session, or route change;
- broker capability degradation, contradictory observation, evidence expiry, API behavior change, or operational notice;
- source correction, retraction, discontinuity, schema drift, policy/configuration change, security compromise, or evidence-integrity failure.

Invalidation SHALL reach approval, authority issuance, unconsumed capabilities, and every final egress within approved bounds. Failure to prove complete propagation expands containment to the complete possibly affected scope.

If a restriction races with an order transmission, the order remains potentially live and capacity-covered until broker evidence establishes its state. A broker rejection, missing acknowledgement, or cancel acknowledgement is interpreted only under ADR-002-004 and cannot erase the attempt.

---

## 19. Degraded and Protective Operation

Under `UNKNOWN`, `STALE`, `CONFLICTED`, `INADMISSIBLE`, closed, halted, suspended, margin-deficient, borrow-unknown, or broker-capability-degraded state:

- ordinary new risk is blocked;
- no unused capacity or reserved headroom converts uncertainty into permission;
- existing and potentially-live economic effects remain conservatively capacity-covered;
- cancellation, protective maintenance, replacement, or containment is not assumed executable;
- only a separately authorized exact action whose current restrictive-path constraints are positively proven may proceed;
- every credible partial fill, simultaneous old/new execution, rejection, reversal, gap, and settlement effect must remain inside the Hard Safety Envelope and committed capacity;
- blind retry, permissive fallback, manual bypass, alternative route, or broker portal is prohibited;
- lack of a safe executable protective path triggers containment, HALT, escalation, and explicit trapped-exposure treatment rather than fabrication of permission.

ADR-002-011 governs protective replacement. Priority, queue order, or reserved internal worker capacity is not broker or venue protective capacity.

---

## 20. Broker Responses, Rejection, and Ambiguous Outcomes

Pre-send admissibility cannot guarantee broker acceptance. Broker responses remain evidence under ADR-002-004.

A rejection may reveal policy drift, wrong mapping, stale session state, account restriction, margin change, or broker-capability contradiction. It SHALL trigger scoped invalidation and investigation when the active policy requires it. Repeated rejection SHALL NOT be converted into a broader permissive fallback.

An acknowledgement proves only the semantics established by the active Broker Capability Profile. A missing acknowledgement never proves non-acceptance, and a cancellation acknowledgement never proves final filled quantity or zero remaining quantity.

If the broker accepted a request that the current policy says was inadmissible, the event is a safety incident. The order is treated as potentially live, capacity remains conservative, new risk is contained, and evidence is preserved. The incident does not justify weakening the policy.

---

## 21. Failure, Partition, Restart, and Restore

Loss or partition of policy, source, constraint generation, account, margin, borrow, settlement, broker-capability, trustworthy-time, authority, RCL, or final-egress currentness dependencies blocks new risk for the affected scope.

A cache, replica, strategy, approval service, Gate instance, or egress instance cannot continue from a last-known permissive decision after it loses bounded active currentness. Restrictive local latches dominate permissive cached state.

Restart, failover, rollback, restore, or deployment SHALL fence stale publishers and evaluators by generation and identity. A former instance is considered potentially active until hard fencing is proven. Old decisions, capabilities, sessions, credentials, and routes cannot be reused merely because stored state was restored.

Constraint-plane and control-plane partition while broker connectivity remains alive is a high-severity path. Final egress SHALL deny new-risk sends unless all currentness, authority, capacity, and exact-decision predicates are independently proven within the approved fenced protocol.

---

## 22. Recovery and Non-Revival

Recovery follows ADR-002-017 and SHALL establish, at minimum:

- fresh source and Constraint Generations with continuity evidence;
- current venue/session/tradability, account, margin, borrow, settlement, and broker-capability state;
- invalidation closure for every stale or contradictory decision;
- conservative Inventory Cut and Recovery Obligations for accepted, potentially-live, external, and UNKNOWN economic effects;
- fresh Snapshot, Decision Context Capsule, and Order Admissibility Decision;
- current configuration, human governance, evidence, authority, and final-egress readiness;
- a new scoped re-arm chain under ADR-002-007 and ADR-002-015.

Venue reopen, halt release, next-session arrival, broker reconnect, margin restoration, account unlock, borrow restoration, replay match, or successful reconciliation is a recovery input only. It cannot move live scope to active, reactivate an old decision, or create authority automatically.

Partial recovery may support a restricted non-live or explicitly isolated scope only when no shared dependency can contaminate it. Unknown dependency isolation remains closed.

---

## 23. Evidence, Metrics, and Alerts

Evidence SHALL preserve:

- policy, Snapshot, decision, Constraint Generation, Capsule, broker-capability, configuration, authority, capacity, proof, and egress identities/digests;
- raw venue, session, halt, instrument, account, margin, borrow, settlement, and broker observations with provenance and continuity;
- exact broker-request shape and every validation predicate/result;
- independent-validation sources and common-mode analysis;
- invalidation trigger, dependency closure, propagation, local latch, and final-egress denial times;
- send-boundary ordering, broker responses, order/fill queries, reconciliation, and capacity transitions;
- restart, partition, restore, recovery, re-arm, and incident evidence;
- unapproved, unsupported, rejected, UNKNOWN, inconclusive, and failed results.

Required metrics and alerts include:

- age and uncertainty by constraint class and consumer;
- source discontinuity, correction, conflict, and invalidation counts;
- session/venue state disagreement and unexpected transition counts;
- decision result and rejection counts by predicate and scope;
- constraint-generation lag at approval, authority, and each egress;
- invalidation-to-authority and invalidation-to-egress containment latency;
- broker rejection that contradicts an admissibility result;
- stale-decision, wrong-scope, substituted-order, and bypass attempts;
- protective path unavailable, margin/borrow/settlement conflict, and trapped-exposure alerts.

ADR-002-016 governs evidence integrity, custody, retention, replay, and review. Evidence proves what enforcement did; it does not perform enforcement.

---

## 24. Security and Common-Mode Analysis

The design SHALL protect policy, sources, mappings, calendars, rule tables, margin and borrow facts, account permissions, Constraint Generation, Snapshots, decisions, invalidations, and currentness channels against unauthorized creation, widening, rollback, suppression, substitution, and replay.

Least privilege SHALL ensure that:

- source and Gate identities cannot activate policy or transmit;
- policy authors cannot unilaterally activate a more permissive generation;
- broker-query credentials used by the Gate cannot obtain a live order route;
- strategies and operators cannot forge an admissibility result or bypass final egress;
- stale deployments, credentials, sessions, and publishers are hard-fenced;
- compromise expands containment to every scope sharing the effective principal, route, source, administrator, mapping, or failure domain.

An unavoidable combined read/trade credential remains inside the declared common-mode scope and requires ADR-002-013 confinement: the constrained read service holds no broker-order route, order endpoints remain deny-by-default, and credential compromise is treated as potential usable live-order authority. The limitation reduces or prohibits live scope.

---

## 25. Rejected Alternatives

### 25.1 Calendar Time Means the Market Is Open

Rejected. Calendars do not prove unscheduled venue state or exact phase semantics.

### 25.2 Quote or Trade Means the Instrument Is Tradable

Rejected. Market data can continue while order entry is halted, restricted, stale, or account-ineligible.

### 25.3 Broker Will Reject Invalid Orders

Rejected. Expected broker rejection is not a preventive safety gate and broker semantics can be incomplete or contradictory.

### 25.4 Exit and Reduce-Only Are Always Safe

Rejected. They can be unsupported, reverse exposure, cross zero, violate account/venue rules, or fail while protection is removed.

### 25.5 Protective Label Bypasses Constraints

Rejected. Classification, capacity, authority, and exact current admissibility remain separate gates.

### 25.6 Last-Known Tradable State During Outage

Rejected. Stale permissive state blocks new risk and cannot be extended by TTL or operator judgment.

### 25.7 Any Successful Broker Login Proves Eligibility

Rejected. Authentication and connectivity do not prove account, instrument, session, order-type, margin, borrow, settlement, or route eligibility.

### 25.8 Retry After Reject or Missing ACK

Rejected. The original attempt may be accepted or partially effective; deterministic attribution and current fresh permission are mandatory.

### 25.9 Human Override of Venue or Margin State

Rejected. Humans may HALT or narrow scope but cannot fabricate Critical Input or economic authority.

### 25.10 Decision Expiry Releases Capacity

Rejected. Artifact expiry limits future use and does not erase economic effect.

### 25.11 Broker Portal Is a Compliant Fallback

Rejected. A portal or manual route outside the final egress boundary is non-conforming live authority.

### 25.12 Audit, Replay, or Rejection Statistics Replace Prevention

Rejected. They are evidence, not enforcement.

---

## 26. Consequences

### 26.1 Positive

- Venue and broker constraints become exact, versioned, order-specific safety facts.
- Market-data health is separated from current tradability.
- Session, halt, price, quantity, account, margin, borrow, settlement, and broker rules are bound through final egress.
- Exit and protective feasibility are treated honestly rather than assumed.
- Constraint changes invalidate future permission without erasing existing economic effects.
- Broker capability remains an evidence-backed ceiling.
- Recovery cannot revive stale decisions or authority.

### 26.2 Negative

- Every venue, broker, account, instrument family, session phase, and order shape requires governed rules and evidence.
- Active currentness and invalidation distribution add latency and availability dependencies.
- Independent constraint validation may require separate sources and failure domains.
- Restrictive defaults will block trading during ambiguous venue or account states.
- Margin, borrow, settlement, and dynamic price rules can require broker-specific probes and restricted-live evidence.

These costs are accepted because ambiguity cannot safely create live permission.

---

## 27. Acceptance Cases

### VTG-AC-001 — Closed, Exceptional, and Phase-Transition Sessions

Exercise scheduled close, unscheduled close, delayed open, opening/closing auction, volatility interruption, reopen, after-hours, and next-day transition. No stale phase decision may authorize a send.

### VTG-AC-002 — Halt, Suspension, and Tradability Conflict

Inject conflicting venue, broker, quote, and calendar state. Ordinary new risk must stop and no quote or recent trade may resolve the conflict permissively.

### VTG-AC-003 — Exact Instrument, Contract, Account, and Route

Substitute symbol alias, market segment, contract month, account, environment, or broker route. Every mismatch must be rejected through final egress.

### VTG-AC-004 — Price, Tick, Lot, Quantity, and Order Shape

Exercise price bands, dynamic collars, tick transitions, odd lots, min/max quantity, rounding, unsupported order type, time in force, and position effect. Silent normalization or widening must fail.

### VTG-AC-005 — Margin, Borrow, Settlement, and Account Eligibility

Inject stale, contradictory, revoked, and scope-mismatched facts. New risk must stop; uncertainty must not create headroom or permission.

### VTG-AC-006 — Exact Decision Binding and Substitution Resistance

Mutate one decision, Capsule, approval, Intent, capacity, capability, proof, or broker-request field. The chain must be rejected and no decision union or partial refresh accepted.

### VTG-AC-007 — Active Final-Egress Currentness and Invalidation Race

Invalidate session, halt, price band, account permission, margin, borrow, or broker capability before capability claim and between claim and first byte. Prove denial or conservative potentially-live containment within approved bounds.

### VTG-AC-008 — Exit, Reduce-Only, Cancel, and Reversal

Exercise unsupported exits, close-side errors, zero crossing, reversal, cancel crossing fill, and missing/cancel ACK. No exit assumption, blind retry, or early capacity release is permitted.

### VTG-AC-009 — Protective and Replacement Constraints

Exercise protective action during halt, auction, rate/session pressure, price limit, unsupported reduce-only, and non-atomic replacement. Exact admissibility, separate authority, capacity, gap, overlap, and trapped-exposure rules must hold.

### VTG-AC-010 — Source, Policy, Capability, and Common-Mode Drift

Restart, roll back, substitute, corrupt, or partition calendars, mappings, rule engines, margin/borrow services, broker profiles, and shared administrators. Unknown continuity and common mode must reduce or prohibit scope.

### VTG-AC-011 — Authority Separation and Bypass Resistance

Attempt direct capacity mutation, authority issuance, protective self-label, human override, stale decision replay, direct broker route, and portal fallback. Every path must be denied and alerted.

### VTG-AC-012 — Recovery, Reopen, and Non-Revival

Recover venue, broker, account, margin, borrow, clock, Gate, and evidence services. Old decisions and authority must remain invalid; fresh recovery obligations, decision, approval, authority, and governed re-arm are required.

Written cases are not completed evidence. Each case maps one-to-one to `VTG-EV-001` through `VTG-EV-012` in VER-002-001 and the Evidence Register.

---

## 28. Requirements Traceability

| Requirement | ADR-002-019 decision |
|---|---|
| SAFE-003, SAFE-004 | restrictive state and independent approval cannot be bypassed by naming, health, or operator action |
| SAFE-010, SAFE-011 | Gate has no capacity or transmission authority; final egress remains the irreversible enforcement point |
| SAFE-013, SAFE-015 | exact capacity binding is required; artifact expiry never erases economic effect |
| SAFE-020 through SAFE-025 | broker ambiguity, orthogonal state, reconciliation, and conservative UNKNOWN rules remain intact |
| SAFE-030, SAFE-031 | venue/account/broker constraint facts are Critical Inputs with provenance and trustworthy time |
| SAFE-032 | every exact action is evaluated against current venue, session, tradability, halt, price, settlement, margin, and execution constraints; exits are not assumed executable |
| SAFE-033 | broker request must exactly conform to approved Intent, decision, account, instrument, direction, quantity, units, price constraints, effect, expiry, and mode |
| SAFE-034, SAFE-035 | independent validation accounts for common mode and all time-dependent validity uses ADR-002-008 |
| SAFE-040, SAFE-043 | protective feasibility and replacement are explicitly proven; priority is not reserved capacity |
| SAFE-041, SAFE-044, SAFE-046, SAFE-048 | recovery, degradation, invalidation, and re-arm are fail-closed and never automatic |
| SAFE-050, SAFE-051, SAFE-052 | active configuration, measurable fault bounds, adversarial tests, evidence, and acceptance gates are mandatory |

---

## 29. Open Implementation Questions

1. Which venue, broker, reference, calendar, account, margin, borrow, settlement, and corporate-action sources are approved per scope?
2. How are Session Phase and exceptional venue-state precedence modeled across venues and market segments?
3. What canonical instrument, contract, account, position-effect, order-type, time-in-force, and routing schemas are used?
4. How are dynamic price bands, tick tables, lot rules, reference prices, auctions, and effective-time transitions represented atomically?
5. Which broker/account queries provide product permission, margin, collateral, borrow, locate, settlement, and restriction evidence, and at what assurance level?
6. How is independent validation achieved where venue and broker expose only one authoritative source?
7. What Constraint Generation and dependency-graph substrate fences stale policy, evaluators, approvals, authorities, and egress instances?
8. How does final egress actively establish currentness without permissive cache, circular dependency, or an unfenced check-then-send window?
9. How are close, reduce-only, cancellation, replacement, and protective actions modeled when the venue or broker supports only partial semantics?
10. What failure-domain allocation prevents one mapping, rule engine, administrator, credential, route, clock, or deployment from corrupting both decision and independent validation?
11. How are accepted-but-inadmissible broker outcomes, venue corrections, and post-send rule changes contained and reconciled?
12. What approved values and measurement definitions govern constraint loss detection, invalidation-to-authority, invalidation-to-egress, Snapshot age, decision age, and claim-to-first-byte composition?

Unresolved questions SHALL reduce or prohibit live scope. They SHALL NOT weaken an invariant or create a permissive fallback.

---

## 30. Approval Gate

ADR-002-019 remains `Proposed` until all applicable conditions pass:

1. Venue Constraint Policy, Snapshot, and Order Admissibility Decision schemas are approved and canonically encoded.
2. Venue/session/tradability, price/quantity/order-shape, account/margin/borrow/settlement, and broker-capability source contracts are selected and security-reviewed.
3. Constraint Generation, dependency closure, correction, invalidation, and stale-publisher fencing are implemented.
4. Exact decision binding is implemented through proposal, approval, Intent, RCL analysis, Live Authorization, capability, Commit Proof, evidence, and final egress.
5. Final egress actively establishes current constraint currentness without permissive cache or bypass and passes send-race review.
6. The Gate holds no capacity, authority, protective-classification, re-arm, live credential, or broker-order route privilege.
7. Exit, reduce-only, cancellation, protective, replacement, auction, halt, price-limit, margin, borrow, settlement, and trapped-exposure rules pass broker-scoped tests.
8. Common-mode and failure-domain analysis is independently reviewed and residual risk reduces live scope.
9. Numeric bounds and limits are approved in the Verification Profile and measured under fault injection.
10. `VTG-EV-001` through `VTG-EV-012` are executed at required EV-L1/EV-L2/EV-L3, Broker, and Security levels with independent review.
11. ADR-002-020 exact candidate command and later conformance-proof binding preserve the decision's complete order shape without circular dependency or downstream mutation, and applicable IOC evidence passes.
12. ADR-002-023 binds the exact current Snapshot/Decision and complete order shape into one independently validated single-use approval/Intent lineage without converting admissibility into approval, and applicable IAP evidence passes.
13. All Critical or Major findings from architecture and security review are resolved.
14. Architecture Gate acceptance, restricted-live, and production criteria pass for the exact proven scope.

This ADR authorizes architecture and implementation-planning work only. It creates no live trading authority and makes no verification-completion or live-readiness claim.
