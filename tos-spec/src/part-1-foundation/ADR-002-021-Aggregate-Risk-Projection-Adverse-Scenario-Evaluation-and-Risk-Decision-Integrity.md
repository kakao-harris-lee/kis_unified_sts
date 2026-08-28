# ADR-002-021 — Aggregate Risk Projection, Adverse-Scenario Evaluation, and Risk-Decision Integrity

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** aggregate-risk policy, immutable aggregate-state snapshot, adverse-scenario set, conservative portfolio projection, single-action and aggregate limits, risk-vector semantics, valuation and uncertainty, netting and hedge recognition, margin/liquidity/concentration treatment, allocation decisions, RCL binding, invalidation/currentness, protective and degraded behavior, recovery, evidence, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-012 and SAFE-013; RFC-002 §§3.1.1, 9.1, 10.4–10.5, 11, 14, 22, and 29; ADR-002-002 §§6–7 and 11; ADR-002-020 §§13–14
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-003, SAFE-004, SAFE-010 through SAFE-015, SAFE-020, SAFE-021, SAFE-024, SAFE-025, SAFE-030, SAFE-031, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-043, SAFE-044, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-002 through ADR-002-020

---

## 1. Decision

Every request for normal or protective risk capacity SHALL be derived from one immutable, current **Aggregate Risk State Snapshot**, one approved **Aggregate Risk Policy**, one approved **Adverse Scenario Set**, and the exact ADR-002-020 **Economic Effect Envelope** for the proposed broker command. The Aggregate Risk Authority SHALL produce an immutable **Aggregate Risk Decision** that binds those inputs, the evaluated scopes, the projected post-action state, the requested Adverse Increment Vector, every limit and assumption, and a result of `GRANT`, `DENY`, or `UNKNOWN`.

The Aggregate Risk Authority is the sole policy authority that may grant or deny an aggregate risk allocation. A `GRANT` is not capacity, Live Authorization, a Transmission Capability, or broker permission. Only the Risk Capacity Ledger may serialize and mutate capacity, and it may commit no more than the exact current granted vector and scope after independently checking current ledger state and all applicable limits. Final egress remains the final transmission enforcement point.

Aggregate projection SHALL include every confirmed, committed, potentially live, UNKNOWN, external, trapped, replacement, protective, margin, collateral, settlement, currency, and concurrent economic effect applicable to the action. A component may not exclude a strategy, instrument, venue, account, legal portfolio, currency, risk factor, or shared dependency merely because it lacks convenient data, appears locally offset, or is outside the proposing service.

Risk SHALL be represented as a governed vector over all applicable scopes and dimensions. A scalar notional, model score, expected loss, value-at-risk point estimate, broker margin number, strategy budget, or local pass flag cannot substitute for the complete vector. Every dimension SHALL declare its unit, sign, aggregation scope, limit source, valuation rule, uncertainty rule, correlation or netting rule, scenario coverage, and freshness requirement.

The Adverse Increment Vector SHALL dominate the maximum credible increase in governed usage over every approved execution path and adverse scenario. It SHALL include full and partial fill prefixes, order overlap, zero crossing, reversal, delayed or missing acknowledgement, broker rounding, fees and cash legs, leverage and margin changes, liquidity and slippage, basis and correlation breakdown, options and assignment effects, settlement and currency effects, and simultaneous credible actions. The intended final state or favorable expected outcome cannot shrink an adverse intermediate state.

Netting, diversification, hedge, collateral, margin-offset, or correlation benefit may reduce projected usage only when an approved policy positively proves the exact instruments, quantities, timing, enforceability, common-mode independence, liquidity, basis behavior, venue availability, and current evidence required for that benefit. Missing, stale, conflicting, common-mode, or unverifiable benefit is zero benefit. Unknown lineage that could cause double counting or omission SHALL be counted conservatively and block new risk if the Hard Safety Envelope cannot still be proven.

Single-action and aggregate evaluation SHALL remain inside the Hard Safety Envelope under worst credible assumptions. Runtime configuration, strategy preference, recent performance, operator approval, broker acceptance, observed margin availability, or a protective label cannot enlarge that envelope. The Runtime Safety Profile may narrow limits only.

The risk calculation SHALL use deterministic, bounded, overflow-safe, unit-safe, and independently reproducible semantics. NaN, infinity, negative zero ambiguity, overflow, underflow, non-convergence, scenario truncation, silent clamp, missing dimension, incompatible schema, parser differential, nondeterministic ordering, or model/library disagreement SHALL result in `UNKNOWN` or `DENY`, never a smaller vector.

All risk inputs are Critical Inputs under ADR-002-018. Price, volatility, correlation, liquidity, FX, margin, collateral, borrow, position, order, fill, broker, corporate-action, settlement, model, mapping, and policy changes SHALL invalidate every affected unconsumed decision through the RCL and final egress. TTL, cache age alone, heartbeat, service health, last-known generation, eventual consistency, or absence of invalidation is not currentness proof.

ADR-002-024 orders Aggregate Risk Generation, exact state/scenario/effect/decision identities, RCL allocation binding, and restrictive risk floors in the complete per-send vector. A prior `GRANT`, existing commitment, cached evaluator state, or previous proof cannot cross a newer risk fence or a local latch in `DENY_LATCHED` or `UNKNOWN` state.

If a decision or its inputs become stale or invalid after capacity was committed but before send, future transmission SHALL be denied and the commitment retained or quarantined. If the command may already have crossed the irreversible send boundary, every credible economic effect remains potentially live and capacity-consuming until authoritative evidence resolves it. Decision, policy, authority, or artifact expiry never expires economic effect.

UNKNOWN broker, order, exposure, capacity, valuation, scenario, correlation, mapping, or aggregate state consumes conservative capacity and blocks new risk. Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. Reconciliation, audit, documentation, replay, human judgment, or a later favorable observation cannot substitute for preventive projection and exclusive commitment.

Protective priority is not reserved protective capacity. A protective or exit-labelled action must still prove its own exact adverse intermediate effects, current venue feasibility, allocation scope, and capacity coverage. During a control-plane partition, the Aggregate Risk Authority cannot create a new grant; only consumption within a valid exclusive pre-committed protective lease may proceed under ADR-002-001/002.

Restart, rollback, restore, failover, cache warm-up, model recovery, data recovery, policy recovery, broker reconnect, reconciliation completion, matching replay, or improved market state cannot revive a prior Aggregate Risk Decision, capacity grant, authority, or live scope. Fresh artifacts and the complete governed re-arm process are required. No automatic re-arm is permitted.

---

## 2. Context

RFC-001 SAFE-012 requires the maximum credible capital effect of one action to be bounded. SAFE-013 requires aggregate evaluation across all strategies, instruments, positions, open orders, venues, margin, collateral, external activity, and concurrent authorizations. ADR-002-002 defines the capacity vector, Adverse Increment Vector, and RCL commitment protocol. ADR-002-020 defines the exact command and its Economic Effect Envelope.

Those documents establish the authority boundary and accounting invariant, but they do not completely define the evaluation protocol between an effect envelope and an RCL grant request. Without one contract, an implementation can:

- evaluate only the proposing strategy or account shard;
- use a stale position projection while a fill or external order is live;
- double count an apparent hedge benefit while omitting its execution gap;
- treat correlation, liquidity, margin offsets, or broker buying power as stable guarantees;
- calculate a favorable final portfolio while ignoring adverse partial-fill prefixes;
- collapse a multi-dimensional limit into scalar notional or expected loss;
- omit a risk dimension because the selected library or product does not support it;
- accept NaN, overflow, non-convergence, scenario truncation, or silent clamp as a smaller result;
- let a proposing service declare an input immaterial or a hedge independent;
- reuse an earlier risk decision after a price, position, margin, policy, model, or mapping change;
- let the risk evaluator directly write capacity or make a broker call;
- treat a risk decision, log, audit record, replay match, broker acceptance, or operator sign-off as capacity or transmission permission;
- restore a cache or model and revive a previous allocation after recovery.

This ADR closes those paths while preserving ADR-002-002's sole-ledger mutation authority and ADR-002-013's final-egress authority.

---

## 3. Decision Drivers

1. Aggregate risk is a portfolio-wide concurrent-state property, not a strategy-local check.
2. The exact command's worst credible economic effect must be projected against current aggregate usage before commitment.
3. Risk dimensions, units, scopes, valuation, uncertainty, and scenario rules must be explicit and reproducible.
4. Favorable netting, hedge, correlation, margin, liquidity, and diversification assumptions require positive evidence.
5. Adverse intermediate states can exceed the intended final-state risk.
6. Calculation failure and missing dimensions must fail closed rather than shrink the vector.
7. Policy evaluation must remain separate from capacity mutation and broker transmission.
8. Material invalidation must reach the RCL and final egress without releasing existing economic effect.
9. UNKNOWN state must consume conservative capacity and block new risk.
10. Recovery must not revive a prior decision or automatically re-arm.

---

## 4. Scope and Non-Scope

This ADR decides:

- Aggregate Risk Policy, Aggregate Risk State Snapshot, Adverse Scenario Set, and Aggregate Risk Decision contracts;
- current aggregate-state completeness and attribution;
- risk-vector dimensions, units, scopes, aggregation, valuation, and uncertainty semantics;
- single-action and projected aggregate evaluation;
- adverse execution paths and scenario coverage;
- netting, hedge, correlation, margin, collateral, liquidity, and concentration recognition;
- exact Economic Effect Envelope and RCL binding;
- deterministic calculation, independent verification, common-mode control, and numerical failure behavior;
- invalidation/currentness at the RCL and final egress;
- degraded/protective, partition, recovery, evidence, acceptance, and approval behavior.

This ADR does not decide:

- alpha, expected return, portfolio preference, or whether a strategy should propose an action;
- exact broker-command construction, which remains ADR-002-020;
- venue/session/order admissibility, which remains ADR-002-019;
- source integrity and Decision Context construction, which remain ADR-002-018;
- capacity serialization, mutation, transfer, quarantine, and release, which remain ADR-002-002/012;
- final credential, route, Commit Proof, and hard-fence security, which remain ADR-002-013;
- the concrete risk engine, optimization solver, scenario generator, numerical library, database, consensus product, or programming language;
- numeric age, invalidation, or execution bounds, which require an approved Verification Profile.

---

## 5. Definitions

### 5.1 Aggregate Risk Policy

An immutable, authenticated, content-addressed policy defining governed risk dimensions, units, signs, scopes, limits, valuation, uncertainty, aggregation, netting, hedge recognition, scenario coverage, numerical rules, dependency closure, invalidation, and consumer compatibility. It is part of the ADR-002-014 Safety Configuration Bundle.

### 5.2 Aggregate Risk Generation

A monotonic generation identifying the current compatible Aggregate Risk Policy, scenario set, schema, model, mapping, dependency, and evaluation semantics for a governed scope. A newer generation fences stale evaluators and decisions; it grants no capacity or authority.

### 5.3 Aggregate Risk State Snapshot

An immutable, consistency-cut artifact containing the complete conservatively attributed current aggregate state used for one evaluation, including positions, orders, fills, commitments, UNKNOWNs, external and trapped effects, collateral, margin, settlement, and protective reservations. It grants no permission.

### 5.4 Adverse Scenario Set

An immutable policy-bound set of approved execution, market, liquidity, correlation, margin, settlement, currency, operational, and broker scenarios used to establish maximum credible effects. Absence from the set is not proof that a credible adverse path can be ignored.

### 5.5 Aggregate Risk Decision

An immutable policy decision binding the exact policy/generation, state snapshot, scenario set, Economic Effect Envelope, evaluated scopes, current and projected vectors, limits, assumptions, uncertainty, and result `GRANT`, `DENY`, or `UNKNOWN`. `GRANT` authorizes only an exact RCL allocation request; it creates no capacity and permits no send.

### 5.6 Projected Aggregate State

The conservative state obtained by applying every credible effect of the proposed command to the complete current aggregate state across every applicable scope and scenario, while preserving existing committed and potentially live effects.

### 5.7 Adverse Increment Vector

The component-wise maximum credible increase in governed risk usage required to cover the proposed command and its adverse intermediate states. It cannot be made smaller by favorable intent, expected rejection, or unproven netting.

### 5.8 Material Risk Change

Any change that may alter a governed current/projected vector, limit, scenario, scope, valuation, uncertainty, dependency, or decision result, or weaken proof. Materiality is policy-owned. Unknown materiality is material.

---

## 6. Safety Invariants

### ARE-INV-001 — Complete Aggregate Scope

Every evaluation includes all applicable strategies, accounts, instruments, venues, positions, orders, commitments, external effects, ADR-002-030 active or possibly active Economic Obligation Records, statement-coverage gaps, breaks, corrections, pending settlement/cash/collateral/borrow/custody/transfer effects, and concurrent actions.

The Post-Trade Obligation Ledger supplies exact lifecycle and generation state but does not grant risk benefit or mutate capacity. Unknown, corrected, partially final, common-mode, or stale post-trade state uses the greatest credible vector; only the RCL can serialize a later capacity transfer, quarantine, or release after current policy-defined evidence.

### ARE-INV-002 — Exact Effect Binding

One decision binds one exact current Economic Effect Envelope and cannot be patched, widened, narrowed, unioned, or substituted.

### ARE-INV-003 — Conservative Projected State

Every credible execution path and adverse intermediate state is included; favorable final intent never erases temporary or uncertain risk.

### ARE-INV-004 — Explicit Vector Semantics

Every governed dimension has exact unit, sign, scope, limit, valuation, aggregation, uncertainty, and scenario semantics.

### ARE-INV-005 — No Unproven Benefit

Netting, hedge, diversification, collateral, margin-offset, liquidity, or correlation benefit is zero unless positively proven under the current policy and evidence.

### ARE-INV-006 — UNKNOWN Is Restrictive

Unknown, stale, conflicting, missing, invalid, or numerically indeterminate state consumes conservative capacity and blocks new risk.

### ARE-INV-007 — Hard Envelope Dominates

Neither runtime policy, strategy, human approval, broker result, nor model output may enlarge the Hard Safety Envelope or single-action bound.

### ARE-INV-008 — Deterministic and Independently Reproducible

Equivalent canonical inputs produce the same conservative result, and an independent verifier can reproduce or reject it without sharing an undeclared common mode.

### ARE-INV-009 — RCL-Only Capacity Mutation

The Aggregate Risk Authority may grant or deny an exact allocation request but cannot create, change, release, transfer, or quarantine capacity.

### ARE-INV-010 — Currentness at Mutation and Egress

The RCL and final egress positively verify exact current decision/generation/scope/invalidation state; permissive cache or absence of invalidation is insufficient.

### ARE-INV-011 — Economic Effect Persists

Decision or input expiry, invalidation, cancellation, missing ACK, cancel ACK, recovery, or replay never expires possible economic effect or releases capacity.

### ARE-INV-012 — Protective Labels Create Nothing

Exit, reduce-only, containment, protective, emergency, or priority labels create no capacity, feasibility, allocation, or transmission permission.

### ARE-INV-013 — Recovery Does Not Revive

Restart, restore, failover, recovery, reconciliation, improved inputs, or replay cannot revive an earlier decision, grant, authority, or live scope.

### ARE-INV-014 — Evidence Does Not Replace Prevention

Logs, monitoring, audit, replay, broker acceptance, and post-trade reconciliation do not replace pre-trade projection and exclusive commitment.

---

## 7. Authority Ownership and Separation

| Action | Policy authority | Enforcement authority | Prohibited combination |
|---|---|---|---|
| Define risk dimensions, scenarios, and limits | Aggregate Risk Policy governance subject to Hard Safety Envelope governance | Safety Profile Validator activates compatible policy | Evaluator SHALL NOT self-approve policy or enlarge the envelope |
| Produce aggregate state snapshot | Position/Order Projection, RCL read model, Reconciliation, and Critical Input owners | Aggregate Risk Authority validates exact consistency and provenance | Snapshot producer SHALL NOT grant allocation or mutate capacity |
| Grant or deny risk allocation | Aggregate Risk Authority | RCL independently validates and serializes an exact request | Aggregate Risk Authority SHALL NOT mutate RCL or transmit |
| Commit, quarantine, transfer, or release capacity | None outside defined RCL transition policy | Risk Capacity Ledger only | Evaluator, strategy, approval, operator, and reconciliation SHALL NOT mutate capacity |
| Issue live authority/capability | Governing Safety/Live Authorization services | RCL and final egress verify current bindings | Risk decision SHALL NOT issue authority or capability |
| Transmit | Execution Coordinator requests | Broker Adapter / Egress Gateway only | Evaluator SHALL NOT hold a usable live credential and broker route |

An identity that can alter policy, scenario, model, mapping, snapshot, evaluation, or verification cannot gain capacity mutation or broker transmission merely by operating that component. If a combined product or administrative plane creates a common mode, the common-mode scope SHALL be declared, independently reviewed, and live scope reduced or prohibited until confinement is proven.

---

## 8. Aggregate Risk Policy Contract

The policy SHALL define at minimum:

- policy identity, version, generation, canonical digest, signer, approval, activation, and compatibility;
- governed environments, Safety Cells, legal portfolios, accounts, strategies, venues, instruments, underlyings, issuers, sectors/themes, currencies, and global scope;
- dimension schemas, units, signs, scaling, precision, rounding, overflow, missing-value, and comparison semantics;
- Hard Safety Envelope and Runtime Safety Profile bindings;
- single-action, aggregate, concentration, leverage, margin, collateral, liquidity, loss/drawdown, settlement, currency, action-rate, and protective-reserve rules;
- valuation sources, conservative price rules, slippage, gap, liquidity, volatility, correlation, basis, FX, fee, exercise, assignment, delivery, and settlement assumptions;
- netting, hedge, diversification, margin-offset, and collateral recognition criteria;
- scenario completeness, dependency closure, materiality, uncertainty, and common-mode rules;
- state-snapshot consistency, maximum age, invalidation, and active-currentness requirements;
- deterministic evaluator and independent-verifier compatibility;
- degraded, partition, protective, and recovery dispositions.

Missing, empty, unsupported, unknown, stale, conflicting, or incompatible policy scope/dimension semantics SHALL make the evaluation `UNKNOWN` or `DENY`. It SHALL NOT mean zero usage, unlimited capacity, wildcard scope, or permission to omit a dimension.

Policy activation does not establish current input, state, scenario, decision, capacity, authority, or egress validity. ADR-002-014 activation and ADR-002-018 currentness remain separate gates.

---

## 9. Aggregate Risk State Snapshot

The snapshot SHALL bind a consistency cut across:

- RCL committed, bound, potentially-live, partial, position, quarantine, trapped, release-pending, and protective-reserve state;
- confirmed positions and cash/collateral/margin/settlement obligations;
- broker orders, attempts, acknowledgements, fills, cancellations, amendments, replacements, and UNKNOWN outcomes;
- external or unattributed activity and non-trade transitions;
- Decision Context, venue constraints, broker capability, time health, configuration, recovery, authority, and writer generations relevant to the evaluation;
- every attribution identity required to distinguish transfer from duplication.

The snapshot is not authoritative merely because all fields are present. Every field SHALL carry source, continuity, observation time, consumer receipt anchor, unit, mapping, confidence/bound, and causal lineage under ADR-002-006/018.

Snapshot assembly SHALL prevent both omission and optimistic double-netting. When the system cannot prove whether two records represent the same effect, it SHALL preserve the maximum credible aggregate usage or block new risk. When it can prove a fill transfers committed order usage to position usage, it SHALL follow the atomic ADR-002-002 transition rather than count both permanently.

A proposer, evaluator shard, model, cache, or read replica cannot declare a missing scope immaterial. Policy dependency closure decides applicability; unknown applicability is included conservatively.

---

## 10. Risk Dimensions, Units, and Scopes

The evaluation SHALL include every dimension required by the Hard Safety Envelope, Runtime Safety Profile, instrument/account semantics, and credible effect. This includes where applicable:

- gross and net notional;
- long, short, delta-equivalent, and directional exposure;
- instrument, underlying, issuer, sector, theme, strategy, venue, account, legal-portfolio, currency, and global concentration;
- leverage, initial/maintenance/stress margin, collateral, buying-power, financing, and liquidation effects;
- liquidity-adjusted exposure, market impact, slippage, gap, overnight, and exit-unavailable risk;
- basis, correlation, hedge mismatch, and common-factor exposure;
- option delta, gamma, vega, theta where safety-relevant, exercise, assignment, delivery, and expiry effects;
- settlement, cash, currency, conversion, fee, tax where safety-relevant, and counterparty obligations;
- realized/unrealized loss, daily loss, drawdown, and constitutional survival budget;
- broker request/order/action-rate budgets and reserved protective capacity.

Cross-dimension conversion SHALL be explicit. Currency conversion, contract multiplier, price scale, option model, duration, beta/correlation, and liquidity transformations are Critical Inputs and cannot silently default.

No lower-dimensional projection may pass if an applicable higher-dimensional or cross-scope limit is unknown. Local compliance never overrides unsafe aggregate state.

---

## 11. Adverse Scenario Set

The scenario set SHALL cover at least:

- every full and partial fill prefix and out-of-order fill sequence;
- original, cancel, amend, replace, split-child, and retry overlap;
- missing acknowledgement and broker receipt ambiguity;
- zero crossing, reversal, reduce-only failure, and position-effect mismatch;
- adverse price, slippage, spread, gap, volatility, liquidity, impact, and limit-state changes;
- correlation and basis breakdown, hedge-leg delay/failure, and venue divergence;
- margin increase, collateral haircut, borrow recall, FX move, settlement delay, assignment/exercise, and delivery;
- external activity, trapped exposure, non-trade changes, and concurrent authorization;
- unavailable exit/protection, rate-limit saturation, broker/session restriction, partition, and recovery uncertainty.

Scenario reduction or pruning SHALL be policy-governed and prove dominance. Sampling, Monte Carlo count, optimizer convergence, historical absence, percentile cutoff, or expected broker rejection cannot prove that an omitted credible tail is harmless.

Where a credible effect cannot be numerically bounded inside the Hard Safety Envelope, the result is `DENY` or `UNKNOWN`; it is not an invitation to choose a convenient finite value.

---

## 12. Projected State and Adverse Increment

For every governed scope `s`, dimension `d`, and approved adverse scenario `q`:

```text
ProjectedUsage[s,d,q]
    = ConservativeCurrentUsage[s,d,q]
    + MaximumCredibleCommandEffect[s,d,q]
    + RequiredConcurrentAndOverlapEffect[s,d,q]

AdverseIncrement[s,d]
    = max_q(
          ProjectedUsage[s,d,q]
          - ConservativeCurrentUsageAlreadyCommitted[s,d,q]
      )
```

The calculation SHALL preserve non-linearity, cross-scope limits, and dependency closure. Component-wise subtraction is permitted only when it cannot hide a joint, concentration, margin, convexity, liquidity, correlation, or scenario constraint.

The decision SHALL record current usage, proposed effect, overlap/concurrency effect, projected usage, effective limit, headroom before commitment, requested increment, and pass/fail result for every applicable scope/dimension/scenario group.

An intended reduction cannot make the requested increment negative merely because the final target is smaller. Temporary overlap, reversal, protection loss, margin, liquidity, rate, and basis effects remain positive where credible.

---

## 13. Netting, Hedge, Correlation, and Diversification

Risk benefit requires positive proof of:

1. exact identity, account/legal-portfolio eligibility, units, quantities, and direction;
2. current enforceable position/order state and Final Quantity Proof where applicable;
3. simultaneous availability and execution behavior across venues, brokers, and sessions;
4. approved basis, correlation, liquidity, gap, and stress behavior;
5. margin/collateral recognition under current broker and account rules;
6. no undeclared common-mode source, model, mapping, administrator, deployment, or failure path;
7. complete adverse partial-fill, leg-failure, replacement, and exit-unavailable scenarios.

If any prerequisite is unknown, the benefit is removed or conservatively bounded. A broker margin number, historical correlation, shared model output, recent co-movement, strategy label, or human assertion is not sufficient proof.

Hedge recognition SHALL never erase trapped exposure or capacity for a potentially live order whose terminal quantity is unproven. A future planned hedge or exit creates no present headroom.

---

## 14. Valuation, Margin, Liquidity, and Numerical Safety

Valuation SHALL use approved conservative rules that distinguish observation price, executable price, stress price, liquidation price, settlement price, conversion rate, and stale/unknown price. A zero, negative, future, crossed, stale, or missing value is not automatically conservative.

Broker margin, buying power, and collateral figures are Critical Inputs and ceilings/observations, not proof that the local aggregate model may omit exposure. More restrictive local or broker constraints dominate. A favorable broker result cannot enlarge the Hard Safety Envelope.

Numerical execution SHALL:

- use approved exact decimal/rational or bounded numeric semantics per dimension;
- detect overflow, underflow, NaN, infinity, negative-zero ambiguity, precision loss, and non-convergence;
- use deterministic ordering and canonical input representation;
- record every conversion, rounding, clamp, solver tolerance, iteration bound, and fallback;
- reject unsupported or silently dropped dimensions;
- produce independently reproducible results across approved implementations.

Any fallback SHALL be explicitly restrictive. “Return zero,” “use last value,” “skip failed scenario,” “accept optimizer incumbent,” or “trust broker validation” is prohibited unless an approved proof establishes it as the conservative upper bound for the exact scope.

---

## 15. Aggregate Risk Decision Contract

The decision SHALL contain at least:

- decision identity, schema, canonical digest, status, result, issuer, and issue evidence;
- Aggregate Risk Policy identity/generation/digest and Safety Configuration Bundle bindings;
- Aggregate Risk State Snapshot identity/cut/generations/digest;
- Adverse Scenario Set identity/generation/digest;
- exact Intent, Canonical Broker Command, Economic Effect Envelope, Decision Context, venue decision, approval, and broker-profile bindings;
- evaluated environments, Safety Cells, accounts, portfolios, strategies, instruments, venues, currencies, and global scopes;
- current, proposed, overlap, projected, limit, headroom, and requested vectors with exact units;
- netting/hedge/correlation/margin/liquidity benefits and the positive evidence for each;
- uncertainty, residual risk, common-mode, numerical, compatibility, invalidation, and maximum-age results;
- requested RCL allocation scope/vector and result `GRANT`, `DENY`, or `UNKNOWN`;
- explicit authority flags.

A `GRANT` SHALL be exact, closed, and non-transferable. Missing or empty requested allocation scope/vector is restrictive and cannot mean zero, wildcard, unbounded, or consumer-selected scope. The RCL SHALL either commit the exact granted vector and scope after its atomic checks or reject and require a fresh evaluation. It cannot shrink, widen, remap, or otherwise reinterpret a grant, because any changed vector may violate effect dominance or a joint constraint.

Two decisions cannot be unioned to obtain a broader scope, reused for another command, or patched with a fresher field. A changed input requires a new complete evaluation.

---

## 16. Non-Cyclic Pipeline and RCL Binding

The required order is:

```text
Approved immutable Intent + unchanged Canonical Broker Command
        ↓
Economic Effect Envelope
        ↓
Current Aggregate Risk State Snapshot + Adverse Scenario Set
        ↓
Aggregate Risk Decision and exact Adverse Increment Vector
        ↓
RCL independently validates and commits exact capacity
        ↓
Order Conformance Proof binds command, effect, risk decision, and commitment
        ↓
Live Authorization / capability / Commit Proof
        ↓
Final-egress active-currentness and actual-outbound verification
```

The Aggregate Risk Decision does not bind a future Capacity Commitment identity. The RCL command binds the prior decision and returns the committed identity/revision. The later Order Conformance Proof binds both. This avoids a cyclic artifact dependency.

Before commitment, the RCL SHALL verify:

- current writer epoch and linearizable state;
- exact decision, policy, generation, snapshot, scenario, effect-envelope, scope, vector, age, and invalidation status;
- current Hard Safety Envelope and Runtime Safety Profile;
- that the decision result is `GRANT` and the requested commitment does not exceed it;
- that current ledger state has not advanced incompatibly since the evaluated snapshot;
- every affected scope remains within its effective limit after the atomic commitment.

If ledger state changed, the RCL SHALL reject or require a fresh evaluation. It SHALL NOT locally repair the risk decision, borrow another grant, or optimistically assume serialization makes stale projection safe.

---

## 17. Invalidation and Active Currentness

Material invalidation triggers include:

- position, order, attempt, fill, commitment, external, trapped, or protective state change;
- Economic Effect Envelope, command, Intent, approval, venue, context, broker capability, or account change;
- price, volatility, liquidity, correlation, basis, FX, margin, collateral, borrow, settlement, exercise, assignment, or corporate-action change;
- Hard Safety Envelope, Runtime Safety Profile, risk policy, scenario, limit, model, schema, mapping, library, build, deployment, or compatibility change;
- source continuity, time confidence, recovery generation, writer epoch, security, or common-mode change.

Dependency closure is policy-owned. Unknown materiality or affected scope expands invalidation conservatively.

The RCL and final egress SHALL actively establish the exact current Aggregate Risk Generation and decision validity for every new-risk mutation/send. Cached `GRANT`, TTL, heartbeat, evaluator health, last-known generation, eventual consistency, successful RCL commit, or absence of invalidation is not currentness proof.

If invalidation races with commitment, capability claim, or the first broker byte and order cannot be proven, the attempt remains potentially live and capacity-covered; blind retry is prohibited. Future permission is denied until the complete current chain is re-evaluated.

---

## 18. Concurrency, Partitions, and Stale Evaluators

Concurrent evaluations may observe the same headroom but cannot reserve it. Only RCL serialization creates exclusive commitment. A risk decision is therefore not proof that headroom remains available.

An evaluator whose Aggregate Risk Generation, policy, state cut, deployment, identity, or compatibility is stale SHALL be fenced. A restored or isolated evaluator is potentially stale until positive currentness and generation ownership are proven.

During loss of the RCL, Aggregate Risk Policy authority, required input/source, currentness path, or complete aggregate state, no new normal capacity grant may become usable. Control-plane isolation while the broker remains reachable SHALL deny new-risk send unless a separately approved, pre-committed, exclusive protective lease and all its local fences remain valid.

No cache lifetime, retry rule, message queue, read replica, majority of evaluators, or eventual-consistency assumption is a fencing mechanism.

---

## 19. Protective, Exit, and Degraded Evaluation

Protective and exit actions SHALL be evaluated against:

- current position and potentially-live quantity;
- zero-crossing and reversal;
- loss or cancellation of existing protection;
- old/new overlap and protection gap;
- broker/venue executability and reduce-only guarantees;
- margin, liquidity, basis, settlement, rate, and partial-fill effects;
- exact pre-committed protective capacity or current normal RCL commitment.

`RESTRICTED_PROTECTIVE_ONLY` or HALT does not permit the evaluator to omit a dimension or invent headroom. If protective feasibility or capacity is unknown, the result is trapped exposure/containment, not permission.

Priority schedules work inside already available safe capacity. They never reserve broker resources or RCL capacity.

---

## 20. Economic Continuity and Reconciliation

Risk decisions govern future allocation only. They do not own capacity lifecycle or authoritative broker/order state.

Missing acknowledgement, timeout, cancel request, cancel acknowledgement, strategy withdrawal, risk-decision expiry, policy expiry, or evaluator failure does not release committed or potentially consumed capacity. Final Quantity Proof and the ADR-002-002 transition rules remain required.

Reconciliation may provide stronger evidence and request a defined RCL transition. It cannot rewrite an earlier risk decision, erase UNKNOWN, or free capacity outside those rules. Conflicting or incomplete evidence expands conservative usage.

---

## 21. Recovery and Non-Revival

Every startup, restart, rollback, restore, failover, model/library change, policy activation, cache rebuild, source recovery, reconciliation recovery, and broker reconnect SHALL pass ADR-002-017's closed Recovery Barrier.

Recovery SHALL:

1. advance or positively verify the current Aggregate Risk Generation;
2. fence all earlier evaluators, publishers, decisions, and caches;
3. reconstruct current aggregate state from authoritative evidence and RCL state without optimistic overwrite;
4. invalidate decisions affected by the recovery cut or changed dependency;
5. require fresh policy, scenario, snapshot, evaluation, commitment, proof, and authority for future new risk;
6. preserve existing committed, potentially live, UNKNOWN, external, and trapped economic effects;
7. complete the governed ADR-002-007/015 re-arm workflow when live scope was withdrawn.

Health, matching totals, successful replay, cleared alerts, restored quorum, or favorable market movement is recovery evidence only. It creates no capacity or authority. No automatic re-arm is permitted.

---

## 22. Evidence, Metrics, and Alerts

Required evidence includes:

- canonical policy, scenario, snapshot, decision, vector, limit, and dependency artifacts;
- source, continuity, consistency-cut, time, schema, mapping, model, library, build, deployment, and compatibility identities;
- every valuation, conversion, rounding, scenario, netting/hedge benefit, uncertainty, and numerical derivation;
- RCL admission/rejection, revision, writer epoch, committed vector, and exact binding;
- invalidation propagation and RCL/final-egress currentness evidence;
- independent reproduction and parser/model/library differential results;
- all failed, denied, unknown, stale, conflicting, overflow, non-convergent, and common-mode cases;
- recovery, fencing, partition, protective, and non-revival evidence.

Metrics and alerts SHALL cover at least:

- decision counts by `GRANT`, `DENY`, and `UNKNOWN`;
- evaluation and invalidation latency;
- snapshot/scenario/decision age and generation mismatch;
- omitted/unknown dimensions and scopes;
- conservative-usage expansion and unproven-benefit removal;
- limit headroom by scope/dimension without treating observability as reservation;
- numerical failure, non-convergence, parser/model/library disagreement;
- stale RCL admission and stale final-egress decision attempts;
- trapped, external, unattributed, potentially-live, and quarantined usage;
- protective-capacity pressure and unavailable protective paths.

Metrics, dashboards, logs, audit, and replay are evidence. They create no allocation, capacity, authority, transmission, or re-arm permission.

---

## 23. Security and Common-Mode Analysis

The security review SHALL cover:

- policy, limit, scenario, model, mapping, schema, library, evaluator, verifier, and deployment supply chain;
- snapshot omission, reordering, substitution, replay, and cross-scope contamination;
- numeric/parser differential and malicious NaN/overflow/non-convergence input;
- benefit inflation through false hedge, correlation, liquidity, margin, or collateral evidence;
- compromised evaluator issuing a broader grant;
- stale generation, rollback, restore, cache poisoning, and mixed-version deployment;
- privilege paths that combine risk-policy change, RCL mutation, Live Authorization, or broker route;
- common source, library, administrator, identity, datastore, clock, deployment, or failure domain shared by evaluation and verification.

The Aggregate Risk Authority SHALL NOT hold or obtain a usable live-order credential, signer, broker session, or broker-order route. If a read credential is inseparable from trade authority, ADR-002-013 confinement applies and live scope is reduced or prohibited until the route is deny-by-default and compromise treatment is proven.

---

## 24. Rejected Alternatives

### 24.1 Strategy-Local Risk Pass

Rejected because local compliance cannot prove aggregate safety or concurrent headroom.

### 24.2 Scalar Notional or Broker Buying Power

Rejected because it omits multi-dimensional, cross-scope, intermediate, liquidity, margin, and uncertainty effects.

### 24.3 Expected or Final-State Risk Only

Rejected because partial fills, overlap, reversal, missing ACK, and hedge-leg failure can be worse.

### 24.4 Historical Correlation or Model Confidence as Hedge Proof

Rejected because common-mode, regime change, liquidity, venue, and execution failure remain credible.

### 24.5 Optimistic Fallback on Calculation Failure

Rejected because skip, zero, last-known, clamp, or partial scenario results can create false headroom.

### 24.6 Risk Decision Directly Mutates Capacity

Rejected because policy evaluation and serialization would collapse, permitting double commitment and bypassing RCL fencing.

### 24.7 RCL Recomputes or Repairs the Decision

Rejected because it would create a second undeclared risk-policy authority and circular semantics.

### 24.8 Capacity Exists, Therefore UNKNOWN May Trade

Rejected because capacity coverage is necessary but not sufficient; UNKNOWN current risk blocks new risk.

### 24.9 Protective Label or Human Override

Rejected because label, urgency, priority, and approval do not prove feasibility, benefit, currentness, or reserved capacity.

### 24.10 Cache, Heartbeat, or Service Health Proves Currentness

Rejected because availability is not current decision/generation/invalidation proof.

### 24.11 Broker Acceptance or Post-Trade Monitoring

Rejected because detection and audit do not replace prevention.

### 24.12 Recovery or Replay Revives the Last Grant

Rejected because recovery evidence is not capacity, authority, or re-arm permission.

---

## 25. Consequences

### 25.1 Positive

- SAFE-012/013 become a deterministic portfolio-wide protocol rather than a generic risk-service responsibility.
- Exact command effects are projected against complete conservative current state before capacity commitment.
- Netting and hedge benefits require positive current evidence.
- Numerical, model, scenario, and common-mode failure is fail-closed.
- Aggregate Risk Authority, RCL, and final egress retain separate non-cyclic duties.
- Invalidation blocks future permission without erasing economic effect.
- Recovery cannot revive old risk decisions or live scope.

### 25.2 Negative

- Complete consistency cuts, scenarios, vectors, and independent verification add latency and engineering cost.
- Conservative unknown treatment can materially reduce availability and apparent capital efficiency.
- Some risk products are non-conforming if they hide dimensions, scenarios, solver fallbacks, or actual derivations.
- Cross-account, cross-venue, derivative, margin, liquidity, and settlement semantics require explicit governance.

These costs are accepted because implementation convenience cannot justify unsafe aggregate headroom.

---

## 26. Acceptance Cases

### ARE-AC-001 — Aggregate Scope Completeness

Omit or delay one strategy, account, venue, instrument, open order, commitment, external activity, trapped exposure, or concurrent action. The evaluation must deny or conservatively include it.

### ARE-AC-002 — Exact Effect and Snapshot Binding

Substitute, patch, union, partially refresh, or replay the state snapshot, scenario set, command, or Economic Effect Envelope. No mixed decision may pass.

### ARE-AC-003 — Partial Fill, Overlap, Reversal, and Missing ACK

Exercise every fill prefix, old/new overlap, zero crossing, reversal, retry, and missing-ACK ordering. The projected state and commitment must dominate every credible path.

### ARE-AC-004 — Dimension, Unit, Scope, and Limit Integrity

Inject missing dimension, wrong unit/sign/scale, scope omission, limit substitution, and scalar-collapse errors. Every ambiguity must fail closed.

### ARE-AC-005 — Netting, Hedge, Correlation, and Common Mode

Break hedge legs, basis/correlation, liquidity, venue availability, margin offsets, shared sources, and independent-verifier assumptions. Unproven benefit must be removed.

### ARE-AC-006 — Valuation, Margin, Liquidity, and Tail Scenarios

Inject stale/zero/negative/future prices, FX moves, margin/collateral changes, liquidity gaps, slippage, option convexity, assignment, settlement, and exit unavailability. Worst credible effect must remain bounded.

### ARE-AC-007 — Numerical Determinism and Failure

Exercise overflow, underflow, NaN/infinity, negative zero, precision, ordering, parser/library/model differential, non-convergence, truncation, and fallback. No smaller permissive vector may result.

### ARE-AC-008 — Concurrent Grant and RCL Serialization

Issue concurrent valid-looking grants against the same headroom, mutate ledger state between snapshot and commit, and replay a grant. Only the RCL may commit available capacity once.

### ARE-AC-009 — Invalidation and Final-Egress Currentness

Change position, fill, margin, policy, scenario, model, mapping, price, correlation, context, or broker capability before commitment, capability claim, and first byte. Stale decisions must be fenced; ambiguous send remains potentially live and covered.

### ARE-AC-010 — Protective, Exit, and Partition Behavior

Use protective/exit/priority labels, control-plane partition with broker alive, exhausted reserve, unavailable exit, and replacement gap. No label or partition may create allocation or capacity.

### ARE-AC-011 — Authority Separation and Security Bypass

Compromise evaluator/verifier/policy identities, attempt direct RCL mutation, issue authority, obtain a broker route, or bypass final egress. Every path must be denied and contained.

### ARE-AC-012 — Recovery, Economic Continuity, and Non-Revival

Restart, restore, fail over, rebuild cache, recover models/data, reconcile, replay, and improve market state while old decisions/effects exist. Capacity remains conservative and fresh governed re-arm is required.

Written cases are not completed evidence. Each case maps one-to-one to `ARE-EV-001` through `ARE-EV-012` in VER-002-001 and the Evidence Register.

---

## 27. Requirements Traceability

| Requirement | ADR-002-021 decision |
|---|---|
| SAFE-003, SAFE-004, SAFE-050 | policy, scenarios, dimensions, limits, models, and compatibility are governed; the Hard Safety Envelope dominates |
| SAFE-010 through SAFE-012 | every action receives conservative single-action/projected evaluation before authority or send |
| SAFE-013 | evaluation is complete across aggregate scopes, existing/potentially-live/external/trapped effects, margin, collateral, and concurrent actions |
| SAFE-014, SAFE-015 | ADR-002-022 governs exact action-flow vectors and permits; only RCL serialization creates exclusive economic and action-flow commitment |
| SAFE-020, SAFE-021, SAFE-024, SAFE-025 | exact immutable lineage, asynchronous broker ambiguity, reconciliation bounds, and partial-fill effects remain conservative |
| SAFE-030, SAFE-031, SAFE-034, SAFE-035 | all inputs are provenance/freshness/time governed and independent verification accounts for common modes |
| SAFE-040, SAFE-043 | protective/exit actions retain exact adverse effects, feasibility, trapped-exposure, and pre-committed-capacity requirements |
| SAFE-041, SAFE-044, SAFE-048 | generation fencing, partition denial, recovery barrier, and non-revival preserve authority separation |
| SAFE-051, SAFE-052 | deterministic derivations, fault injection, retained evidence, replay isolation, and independent review are mandatory |

---

## 28. Open Implementation Questions

1. What canonical Aggregate Risk Policy, State Snapshot, Adverse Scenario Set, and Decision schemas are approved?
2. Which risk dimensions, units, scopes, dependency closures, and cross-dimension comparison rules are mandatory for each product/account class?
3. Which consistency-cut protocol produces a complete snapshot across RCL, broker/order projection, reconciliation, account, and Critical Input state?
4. Which valuation, stress, slippage, liquidity, volatility, correlation, basis, FX, margin, collateral, settlement, option, and assignment models are approved?
5. How are credible scenarios added, pruned, dominated, versioned, independently reviewed, and invalidated?
6. Which exact proof permits a netting, hedge, diversification, margin-offset, collateral, or correlation benefit?
7. Which deterministic numeric, unit, solver, optimization, canonicalization, and independent-verification mechanisms are conforming?
8. How is common mode separated across sources, snapshots, models, schemas, mappings, libraries, evaluators, verifiers, administrators, and deployments?
9. What Aggregate Risk Generation and stale-evaluator fence substrate reaches the RCL and every final egress?
10. How do RCL admission and final egress obtain active decision currentness without permissive cache or circular dependency?
11. How are affected scope and dependency closure computed during position/fill/external/non-trade/policy/model/input invalidation?
12. What approved bounds and measurement definitions govern snapshot/decision age and risk-invalidation propagation to RCL and egress?
13. Which broker/account/product combinations cannot support bounded worst credible effect and therefore remain non-live?
14. What restricted-production evidence is required beyond model, simulation, and broker sandbox verification?

Unresolved questions reduce or prohibit authority. They do not permit local convention, optimistic defaults, omitted dimensions, or live operation.

---

## 29. Approval Gate

ADR-002-021 SHALL remain `Proposed` until all of the following are complete:

1. Aggregate Risk Policy, State Snapshot, Adverse Scenario Set, Decision, vector, and invalidation schemas are approved.
2. Risk dimensions, scopes, units, limits, valuation, uncertainty, scenario, netting/hedge, and dependency rules are approved against the Hard Safety Envelope.
3. Snapshot consistency-cut, deterministic evaluator, independent verifier, numerical safety, and common-mode mechanisms are selected and security-reviewed.
4. Aggregate Risk Generation, stale-evaluator fencing, active RCL/final-egress currentness, and send-race containment mechanisms are selected and security-reviewed.
5. RCL admission proves exact decision/vector/scope/currentness binding without creating a second policy authority.
6. Protective, exit, replacement, partition, trapped-exposure, and economic-continuity behavior is implemented without priority-as-capacity or automatic release.
7. Recovery Barrier integration fences stale artifacts, preserves existing effects, and requires the complete governed re-arm workflow.
8. `ARE-EV-001` through `ARE-EV-012` are executed at their required levels with retained raw artifacts and independent review.
9. Verification Profile bounds for invalidation-to-RCL, invalidation-to-egress, snapshot age, and decision age are approved and measured under fault injection.
10. Broker/account/product-specific scenario, margin, liquidity, hedge, settlement, and Final Quantity Proof assumptions are evidenced.
11. No open Critical or Major finding remains; numerical, scenario-completeness, common-mode, currentness, and security findings are included.
12. Architecture, risk, security, broker/venue, operations, and independent safety reviewers approve the residual-risk and live-scope disposition.
13. ADR-002-022 binds the exact action-flow vector and single-use permit to the same command/effect/risk-decision chain without creating a second capacity authority, and applicable AFG evidence passes.
14. ADR-002-023 ensures the upstream immutable Intent was created by one exact current independently validated and singly consumed approval decision without allowing approval to grant aggregate-risk allocation, and applicable IAP evidence passes.

This ADR authorizes architecture and implementation-planning work only. It grants no capacity, Accepted status, restricted-live readiness, production readiness, or live trading authority.
