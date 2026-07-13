# ADR-002-001 — Degraded-Mode Protective Capacity

**ADR ID:** ADR-002-001
**Title:** Degraded-Mode Protective Capacity
**Status:** Proposed
**Decision Type:** Safety-Critical Architecture Decision
**Parent Document:** RFC-002 — Trading Operating System Architecture
**Governed By:** RFC-000 and RFC-001
**Date:** 2026-07-13
**Amended:** v0.2 review patch — 2026-07-13 (commit/consume semantics, reserve guarantee levels, intermediate-state proof, replacement gaps, cancellation ownership, multi-account allocation, dynamic margin erosion, bounded exhaustion)
**Owners:** Trading Operating System Architecture Board

---

## 1. Context

The Trading Operating System SHALL prohibit new risk creation when it enters the Constitutional Safe State or another degraded operating mode.

However, existing positions, open orders, and margin obligations continue to exist after ordinary trading authority is withdrawn.

The system may still need capacity to:

* cancel risk-increasing open orders;
* maintain or replace approved protective orders;
* reduce existing exposure;
* manage partially filled exits;
* respond to broker or venue state;
* preserve trapped-exposure awareness;
* perform reconciliation;
* notify operators;
* invoke emergency containment.

If normal trading is allowed to consume all available:

* broker API rate;
* order rate;
* execution workers;
* queue capacity;
* risk capacity;
* margin or collateral headroom;
* network capacity;
* operator-control capacity;

then the system may enter a degraded state without sufficient resources to protect existing capital.

This creates a contradiction:

```text
Normal trading consumes all capacity
        ↓
Failure occurs
        ↓
New trading is stopped
        ↓
No capacity remains to protect existing exposure
```

The architecture therefore requires explicitly reserved protective capacity.

---

## 2. Decision Drivers

This decision is driven by:

* CONST-001 — Long-Term Survivability;
* CONST-002 — Capital Preservation;
* CONST-004 — Fail-Safe Operating Principle;
* CONST-006 — Operational Safety Limits;
* CONST-009 — Pre-Trade Constitutional Assurance;
* CONST-011 — Independent Safety Authority;
* CONST-012 — Safe Operational State;
* SAFE-001 — Default Safe State;
* SAFE-002 — No Unmanaged Exposure;
* SAFE-011 — Non-Bypassable Safety Limits;
* SAFE-013 — Aggregate Risk Authority;
* SAFE-014 — Bounded Action Rate;
* SAFE-040 — Protective Control in Degraded Operation;
* SAFE-041 — Independent Safety Authority;
* SAFE-043 — Exit-Unavailable Containment;
* SAFE-048 — Partition-Tolerant Safety Authority.

---

## 3. Decision

The TOS SHALL implement a **Reserved Protective Capacity Architecture**.

Protective capacity SHALL be isolated from ordinary strategy capacity and SHALL remain available during degraded operation to the greatest extent supported by the current verified state.

The architecture SHALL provide:

1. reserved execution capacity;
2. reserved broker/API action capacity;
3. reserved risk and margin headroom where protective actions may require it;
4. a separately governed protective-action authority;
5. an independently validated protective-action classification;
6. degraded-mode operation that does not depend on ordinary strategy authority.

Normal trading SHALL NOT consume the minimum reserved protective capacity.

Protective operation MAY consume:

* the reserved protective capacity;
* unused normal capacity;

but SHALL remain bounded by the Hard Safety Envelope and the approved Protective Action Envelope.

---

## 4. Protective Capacity Domains

Protective capacity SHALL be defined across all resources whose exhaustion could prevent containment.

### 4.1 Execution Capacity

The architecture SHALL reserve sufficient execution-worker and queue capacity for:

* risk-increasing order cancellation;
* approved protective order submission;
* protective replacement;
* emergency containment;
* reconciliation requests.

### 4.2 Broker and Venue Capacity

The architecture SHALL reserve or prioritize sufficient broker/API capacity for:

* cancellation;
* order-state query;
* position query;
* balance and margin query;
* approved protective action;
* emergency halt operations.

### 4.3 Risk Capacity

A portion of aggregate risk authority MAY be reserved for protective action where reducing one form of risk may temporarily require:

* gross exposure;
* margin;
* hedge position;
* basis exposure;
* transaction capacity.

Reserved protective risk capacity SHALL NOT be available to ordinary strategies.

### 4.4 Margin and Collateral Capacity

Where a protective action may consume additional margin or collateral, the Safety Profile SHALL define the minimum protective reserve.

The architecture SHALL NOT assume that every exit or hedge automatically reduces margin.

### 4.5 Control Capacity

The operator and Safety Authority control paths SHALL retain priority over ordinary trading traffic.

---

## 5. Protective Action Authority

Protective actions SHALL be authorized by the Protective Action Controller under the authority of the Safety Control Plane.

A strategy SHALL NOT authorize a protective action.

A strategy MAY request protection, but the request SHALL be independently classified.

The Protective Action Controller SHALL verify:

* current authoritative exposure;
* potentially live orders;
* trapped exposure;
* projected aggregate post-action risk;
* applicable venue constraints;
* Hard Safety Envelope;
* Safety Profile;
* current protective capacity;
* current Safety Authority or approved degraded authority.

---

## 6. Protective Action Classification

An action SHALL be considered protective only when all of the following are true:

1. its projected aggregate post-action state is safer than the current state;
2. it does not exceed the Hard Safety Envelope;
3. it remains within the approved Protective Action Envelope;
4. it does not create a greater credible margin, liquidity, basis, concentration, venue, or execution hazard;
5. its required operational state is sufficiently trustworthy;
6. its quantity is bounded by confirmed and potentially live exposure;
7. its effect can be evaluated before transmission.

An action SHALL NOT be considered protective solely because it is labelled as:

* hedge;
* exit;
* stop;
* flatten;
* emergency;
* reduce-only;
* recovery.

Where projected aggregate risk reduction cannot be established, the action SHALL be treated as risk-increasing and rejected in degraded mode.

---

## 7. Protective Action Envelope

The Safety Profile SHALL define a Protective Action Envelope.

The envelope SHALL identify:

* permitted accounts;
* permitted instruments;
* permitted action classes;
* maximum quantity;
* maximum notional;
* maximum gross-exposure increase;
* maximum margin consumption;
* maximum action rate;
* maximum duration;
* permitted venue and order constraints;
* evidence requirements;
* escalation behavior.

The Protective Action Envelope SHALL remain subordinate to the Hard Safety Envelope.

---

## 8. Degraded Operation Modes

### 8.1 LIVE_RESTRICTED

The system retains verified Safety Authority but one or more dependencies are degraded.

Permitted:

* approved ordinary actions within reduced authority;
* protective actions;
* cancellation;
* reconciliation.

### 8.2 DEGRADED_PROTECTIVE

New risk-increasing actions are prohibited.

Permitted:

* cancellation of confirmed risk-increasing orders;
* maintenance of approved protective orders;
* bounded protective actions;
* reconciliation;
* evidence capture;
* operator notification.

### 8.3 CONTAINED

Autonomous protective classification is unavailable or no longer sufficiently trustworthy.

Permitted:

* operations previously proven not to increase risk;
* independently authorized cancellation;
* narrowly bounded emergency actions;
* reconciliation;
* human escalation.

### 8.4 HALTED

Automated execution authority is withdrawn.

Only explicitly authorized emergency human operations MAY proceed.

---

## 9. Partition Behavior

When the Execution Coordinator loses verifiable contact with the Safety Authority:

1. all new risk-increasing actions SHALL stop;
2. uncommitted ordinary intents SHALL expire or remain blocked;
3. ordinary strategies SHALL lose transmission authority;
4. only actions permitted by a current, locally verifiable Protective Action Envelope MAY continue;
5. stale permissive authority SHALL NOT be reused.

The architecture MAY use a locally verifiable degraded-operation authorization issued before the partition.

Such authorization SHALL be:

* signed or otherwise integrity-protected;
* time-bounded;
* scope-bounded;
* account-bounded;
* instrument-bounded;
* action-bounded;
* subordinate to the Hard Safety Envelope;
* invalid when the Trustworthy Time Basis is unavailable.

RFC-002 SHALL define the concrete authority-validity mechanism.

---

## 10. Behavior When Time Cannot Be Trusted

If the Trustworthy Time Basis is unavailable:

* time-dependent live authority SHALL be invalid;
* time-dependent protective authorization SHALL be invalid;
* new protective orders SHALL NOT be submitted unless an independently approved non-time-dependent emergency rule applies;
* cancellation of confirmed risk-increasing open orders MAY remain permitted when cancellation can be shown not to increase aggregate risk;
* operator escalation SHALL occur.

The architecture SHALL NOT treat an unverified protective authorization as permanently valid.

---

## 11. Cancellation Rules

Cancellation is not automatically protective.

### 11.1 Permitted Cancellation

Cancellation MAY proceed when the cancelled order is:

* risk-increasing;
* no longer authorized;
* outside the current Safety Profile;
* duplicated;
* inconsistent with authoritative exposure.

### 11.2 Restricted Cancellation

Cancellation SHALL require protective-risk evaluation when the order being cancelled is:

* a stop;
* a protective exit;
* a hedge;
* part of an atomic protective replacement.

A protective order SHALL NOT be cancelled merely because ordinary trading is halted.

### 11.3 Replacement

Replacement of a protective order SHALL preserve protection throughout the transition.

The architecture SHALL avoid an interval in which the old protection has been removed but the replacement is not yet live.

Where this cannot be guaranteed, the residual risk SHALL be explicitly represented.

---

## 12. Reserved Capacity Consumption

### 12.1 Normal Operation

Normal strategies MAY use only normal capacity.

Reserved protective capacity SHALL remain unavailable to ordinary action.

### 12.2 Protective Operation

Protective actions MAY consume:

1. reserved protective capacity;
2. unused normal capacity.

### 12.3 Priority

Within degraded operation, capacity priority SHALL be:

```text
1. Safety Authority and operator control
2. Reconciliation and authoritative-state queries
3. Cancellation of risk-increasing open orders
4. Maintenance of existing protective orders
5. Bounded exposure-reducing actions
6. Notifications and supporting evidence
```

This ordering MAY be refined by market-specific subordinate specifications but SHALL NOT place ordinary strategy activity above protective operation.

---

## 13. Capacity Exhaustion

If reserved protective capacity is exhausted:

1. no ordinary trading SHALL resume;
2. the system SHALL remain in the Constitutional Safe State;
3. remaining resources SHALL be allocated according to the protective priority order;
4. trapped or unmanaged exposure SHALL remain explicitly visible;
5. operator escalation SHALL occur;
6. the system SHALL NOT report a safe or flat state unless authoritatively confirmed.

Capacity exhaustion SHALL itself be treated as a Critical operational event.

---

## 14. Risk-Capacity Accounting

Protective risk capacity SHALL be represented separately from normal strategy capacity.

The risk model SHALL account for:

* gross exposure;
* net exposure;
* margin effect;
* concentration;
* basis risk;
* liquidity;
* open orders;
* partial fills;
* trapped exposure;
* potentially live orders.

A protective action SHALL reserve capacity before transmission.

Two protective actions SHALL NOT consume the same reserved capacity.

---

## 15. Trapped Exposure

When exposure cannot be reduced:

* it SHALL remain represented at full conservative risk;
* protective capacity SHALL NOT be released based on an assumed future exit;
* new ordinary risk SHALL remain prohibited;
* operator escalation SHALL continue;
* venue reopen or liquidity return SHALL trigger re-evaluation, not automatic execution.

---

## 16. Recovery and Exit From Degraded Mode

The system SHALL NOT leave degraded protective operation until:

* authoritative state is reconciled;
* Safety Authority is current and verifiable;
* Trustworthy Time Basis is valid;
* Safety Profile is valid;
* protective-capacity accounting is reconciled;
* potentially live orders are known;
* external activity is resolved;
* no blocking hazard remains.

Restored connectivity alone SHALL NOT restore normal trading.

Return to `LIVE_NORMAL` SHALL require explicit re-arming.

---

## 17. Alternatives Considered

### 17.1 Stop All Orders During Failure

**Rejected.**

This can abandon open positions and prevent protective action.

It violates the exposure-aware safe-state requirement.

---

### 17.2 Allow Strategy-Labelled Protective Orders

**Rejected.**

A strategy could classify an ordinary order as protective and bypass limits.

---

### 17.3 Use Shared Capacity Without Reservation

**Rejected.**

Ordinary operation could exhaust resources before failure occurs.

No protective capacity would be guaranteed.

---

### 17.4 Reserve Broker Capacity Only

**Rejected.**

Broker calls alone are insufficient.

Protective operation may also require:

* execution workers;
* risk capacity;
* margin;
* control-path availability;
* state queries.

---

### 17.5 Fully Independent External Risk System

**Not required by this ADR.**

A physically independent external risk system may provide stronger containment and MAY be selected by a later ADR.

This ADR requires authority and failure independence but does not mandate a specific deployment topology.

---

## 18. Consequences

### 18.1 Positive Consequences

* degraded operation preserves containment capacity;
* normal strategies cannot exhaust all protective resources;
* protective actions are independently classified;
* partition behavior is explicit;
* risk and margin required for protection can be preserved;
* failure does not automatically imply unmanaged exposure.

### 18.2 Negative Consequences

* some resources remain unused during normal operation;
* maximum normal trading throughput may be lower;
* capital efficiency may be reduced;
* architecture and testing complexity increase;
* broker-specific capacity planning is required;
* protective classification requires a separate risk evaluation path.

These costs are accepted because capital protection has higher precedence than maximum utilization.

---

## 19. Failure Modes Introduced by This Decision

This decision introduces new hazards that SHALL be controlled.

### 19.1 Protective Capacity Misclassification

Ordinary action is incorrectly classified as protective.

### 19.2 Protective Capacity Starvation

Reserved capacity is too small for credible failure conditions.

### 19.3 Protective Capacity Over-Reservation

Excessive reservation materially prevents normal operation.

### 19.4 Stale Protective Authorization

Expired degraded authority remains active.

### 19.5 Protective Action Increases Risk

A hedge or exit creates greater aggregate risk.

### 19.6 Protective Path Common-Mode Failure

The protective path shares a dependency that fails with the ordinary path.

These hazards SHALL be included in RFC-001 or a subordinate hazard register where not already represented.

---

## 20. Verification Requirements

The decision SHALL be demonstrated through at least the following scenarios.

### 20.1 Resource Saturation

Normal traffic saturates normal capacity.

Expected result:

* reserved protective capacity remains available;
* protective cancellation and state query succeed;
* ordinary actions cannot consume the reserve.

### 20.2 Runaway Strategy

A strategy emits actions at the maximum attempted rate.

Expected result:

* ordinary activity is bounded;
* protective and control traffic remains available;
* new risk stops.

### 20.3 Safety Authority Partition

The execution path loses contact with the Safety Authority.

Expected result:

* ordinary new-risk execution stops;
* only current, locally verifiable protective authority remains usable;
* stale authority is rejected.

### 20.4 Partial Fill During Degradation

An exit partially fills as the system enters degraded mode.

Expected result:

* residual exposure remains represented;
* retry quantity reflects confirmed residual exposure;
* capacity is not released prematurely.

### 20.5 Protective Order Cancellation

A protective order is selected for cancellation.

Expected result:

* cancellation is blocked unless aggregate protection is maintained or improved.

### 20.6 Margin-Constrained Hedge

A proposed hedge reduces directional exposure but increases margin risk beyond the approved envelope.

Expected result:

* the hedge is rejected as non-protective.

### 20.7 Trapped Position

A position cannot be exited because of halt, price limit, or liquidity.

Expected result:

* exposure remains conservatively represented;
* capacity is not released;
* ordinary risk remains blocked;
* escalation occurs.

### 20.8 Protective Capacity Exhaustion

All reserved capacity is consumed.

Expected result:

* system remains in the safe state;
* priority ordering is enforced;
* no ordinary trading resumes;
* exhaustion is reported as Critical.

### 20.9 Clock Failure

Time confidence is lost during partition.

Expected result:

* time-bounded degraded authority becomes invalid;
* no stale protective authorization remains active.

---

## 21. Acceptance Criteria

This ADR MAY be accepted when:

* protective resource domains are identified for each supported broker and market;
* the minimum reservation policy is defined in the Safety Profile;
* normal trading cannot consume the protected reserve;
* protective classification is independent of strategy;
* partition behavior is implemented and tested;
* capacity exhaustion behavior is implemented and tested;
* partial-fill behavior is demonstrated;
* trapped-exposure behavior is demonstrated;
* no test permits a protective label to bypass aggregate-risk evaluation;
* evidence is independently reviewed.

---

## 22. Traceability

| Requirement | ADR decision                                                |
| ----------- | ----------------------------------------------------------- |
| SAFE-001    | Degraded operation enters an exposure-aware safe state      |
| SAFE-002    | Existing exposure retains protective control                |
| SAFE-011    | Protective authority is not controlled by strategy          |
| SAFE-013    | Protective actions use aggregate risk                       |
| SAFE-014    | Protective traffic remains available under runaway activity |
| SAFE-015    | Protective capacity is exclusively committed                |
| SAFE-040    | Protective controls remain available during degradation     |
| SAFE-041    | Safety Authority governs protective operation               |
| SAFE-043    | Trapped and exit-unavailable exposure remains controlled    |
| SAFE-048    | Partition behavior revokes new-risk authority               |

---

## 23. Implementation Notes

The following are possible mechanisms but are not mandated by this ADR:

* dedicated execution queue;
* reserved worker pool;
* priority broker rate limiter;
* separate broker session;
* safety capability token;
* expiring authority lease;
* dedicated risk-capacity ledger;
* pre-positioned protective order;
* independent operator channel.

RFC-002 or subordinate ADRs SHALL select the concrete mechanisms.

---

## 24. Decision Summary

The TOS SHALL reserve independent and bounded capacity for protective operation.

Normal strategy activity SHALL NOT consume that minimum reserve.

Protective actions SHALL be authorized independently, classified using projected aggregate risk, and constrained by the Hard Safety Envelope and Protective Action Envelope.

Loss of Safety Authority contact SHALL stop new risk while permitting only narrowly bounded, current, locally verifiable protective behavior.

The purpose of this decision is not to guarantee that every position can be exited.

Its purpose is to ensure that ordinary operation cannot consume the system's ability to attempt containment when failure occurs.

---

## 25. Version 0.2 Review-Patch Amendments

### 2. Decision Summary — Amended

The Trading Operating System SHALL maintain Reserved Protective Capacity that is separated from ordinary trading capacity across every resource dimension for which protection depends on availability.

Reserved Protective Capacity SHALL be represented at two levels:

1. **Aggregate Protective Commitment** — capacity removed from normal headroom and committed in advance by the authoritative Risk Capacity Ledger;
2. **Protective Action Consumption** — exclusive binding of a portion of the committed pool to a specific protective action.

No new aggregate capacity may be committed during a Safety Control Plane partition.

During a partition, only a previously issued, current, exclusive, scope-limited protective lease may be consumed. The lease may not be enlarged, replenished, transferred, or reused without restoration of the normal authority path.

Protective action is permitted only when the system can prove, before transmission, that the action remains within the Hard Safety Envelope and does not increase conservative aggregate portfolio risk across every credible intermediate execution state.

---

### 3. Corrected Terminology

#### 3.1 Aggregate Protective Commitment

A durable Risk Capacity Ledger commitment that removes a defined capacity vector from normal strategy availability and assigns it to a protective pool.

The Aggregate Risk Authority may approve the allocation. The Risk Capacity Ledger is the sole state-transition authority that creates it.

#### 3.2 Protective Lease

A bounded delegation of part of an Aggregate Protective Commitment to one Protective Action Controller authority domain.

A Protective Lease SHALL include:

- lease identity;
- parent commitment identity;
- account scope;
- instrument or instrument-class scope;
- allowed protective action classes;
- maximum quantity and risk-vector effect;
- margin and collateral allowance;
- broker/API resource allowance where representable;
- authority epoch;
- single active owner;
- monotonic lifetime;
- consumption-state identity;
- Hard Safety Envelope version;
- Runtime Safety Profile version.

#### 3.3 Protective Consumption

An exclusive sub-reservation within a valid Protective Lease, bound to one protective Intent and one or more explicitly identified transmission attempts.

Protective Consumption does not create new aggregate headroom.

#### 3.4 Protective Resource Guarantee Level

Every claimed protective resource SHALL be classified as one of:

```text
PHYSICALLY_RESERVED
LOGICALLY_RESERVED
PRIORITIZED_ONLY
BEST_EFFORT
UNAVAILABLE
```

A prioritized resource is not a reserved resource.

#### 3.5 Protection Gap

A period during which previously effective protection has been removed, invalidated, or reduced before equivalent or stronger replacement protection is confirmed live.

#### 3.6 Protective Ownership

The authority class responsible for maintaining, replacing, or cancelling a protective order.

Allowed values:

```text
STRATEGY_OWNED
EXECUTION_OWNED
SAFETY_OWNED
OPERATOR_OWNED
```

---

### 4. Resource Dimensions — Amended

Reserved Protective Capacity SHALL be evaluated separately for at least:

- execution workers;
- request queues;
- broker/API request rate;
- broker session or connection availability;
- cancellation and order-message rate;
- aggregate risk capacity;
- margin and collateral headroom;
- network and control path;
- reconciliation capacity;
- evidence persistence capacity;
- operator emergency path;
- current trustworthy-time capability;
- protective authorization capability.

A resource dimension SHALL NOT be described as guaranteed unless its failure independence and reservation mechanism have been demonstrated.

---

### 5. Commit Versus Consume

#### 5.1 Normal State

In `LIVE_NORMAL` or another state with current Safety Control Plane authority:

1. the Aggregate Risk Authority evaluates the required protective reserve;
2. the Risk Capacity Ledger atomically commits the protective pool;
3. the committed pool is removed from normal strategy headroom;
4. one or more bounded Protective Leases may be issued from that pool;
5. lease issuance SHALL NOT make the same parent capacity available to multiple owners.

#### 5.2 Partition or Degraded State

In `DEGRADED_PROTECTIVE`:

- no new Aggregate Protective Commitment may be created;
- no existing commitment may be enlarged;
- only an already valid Protective Lease may be consumed;
- the protective sub-ledger or equivalent serialized mechanism SHALL prevent duplicate consumption;
- normal strategy capacity remains unavailable;
- unused lease capacity may not be borrowed for ordinary trading;
- consumed capacity remains bound until Final Quantity Proof or confirmed-position transfer is complete.

#### 5.3 Loss of Exclusivity

If the system cannot prove that a Protective Lease has one current owner, no new protective transmission may use the lease.

Potentially live actions already issued under that lease remain capacity-consuming and enter reconciliation.

---

### 6. Protective Action Classification — Strengthened

#### 6.1 Non-Authoritative Labels

The following SHALL NOT be sufficient to classify an action as protective:

- `protective=true` supplied by strategy;
- sell direction;
- exit or hedge naming;
- reduce-position intent;
- operator description;
- correlation with an existing position.

Only the Protective Action Controller may classify the action, using conservative aggregate risk analysis.

#### 6.2 Final-State Test

The intended final state SHALL satisfy:

```text
Projected conservative aggregate post-action risk
    <
Current conservative aggregate risk
```

for the relevant risk dimensions, while remaining within the Hard Safety Envelope.

#### 6.3 Intermediate-State Test

The final-state test is necessary but not sufficient.

For every credible combination of:

- partial-fill fraction;
- execution ordering;
- leg failure;
- acknowledgement loss;
- cancel/replace race;
- late fill;
- external position change within the detection bound;
- basis movement;
- liquidity deterioration;
- margin revaluation;

it SHALL be shown that:

```text
Worst-case conservative risk after the intermediate state
    <=
Risk of taking no protective action
```

and that every hard limit remains satisfied.

If this property cannot be demonstrated, the action is classified as risk increasing for degraded-mode purposes.

#### 6.4 Risk Dimensions

Protective analysis SHALL include, where relevant:

- gross and net directional exposure;
- leverage;
- margin utilization;
- concentration;
- liquidity-adjusted exit risk;
- basis risk;
- correlation breakdown;
- gap risk;
- option Greeks;
- settlement and rollover risk;
- collateral encumbrance;
- broker order-rate consumption;
- loss of existing protection.

A hedge that reduces delta but materially increases margin, basis, liquidity, or concentration risk may be denied.

---

### 7. Protective Capacity Guarantee Levels

#### 7.1 Physical Reservation

`PHYSICALLY_RESERVED` requires a failure-independent resource partition that ordinary traffic cannot consume.

Examples may include:

- dedicated worker pool;
- separate bounded queue;
- independent network path;
- separate broker session whose quota is contractually or technically independent;
- dedicated credential with independently enforced scope;
- reserved collateral not available to strategy sizing.

#### 7.2 Logical Reservation

`LOGICALLY_RESERVED` means the TOS can enforce non-consumption by ordinary activity but shares a lower-level common dependency.

It SHALL be accompanied by explicit common-mode analysis.

#### 7.3 Priority Only

`PRIORITIZED_ONLY` means ordinary work is deprioritized but may already occupy or exhaust the shared resource.

It SHALL NOT be relied upon as guaranteed protective capacity.

#### 7.4 Best Effort

`BEST_EFFORT` SHALL be treated as a residual-risk disclosure, not a safety guarantee.

The system SHALL compensate by one or more of:

- earlier transition to `LIVE_RESTRICTED` or `DEGRADED_PROTECTIVE`;
- lower normal traffic admission;
- smaller live scope;
- larger margin reserve;
- reduced action frequency;
- stronger operator readiness;
- prohibition of strategies that depend on unavailable protection.

#### 7.5 Single-Session or Global-Rate-Limit Broker

Where the broker exposes a single serialized session or a global account rate limit:

- ordinary traffic SHALL be admitted below the maximum observed or contractual limit;
- a portion of locally controlled request capacity SHALL be withheld;
- blocked or stuck requests SHALL have bounded cancellation/timeout handling;
- the remaining common-mode dependency SHALL be documented;
- the protective API path SHALL be classified no higher than its demonstrated guarantee level.

---

### 8. Dynamic Reserve Sufficiency

Protective reserve is not a static configuration value.

The system SHALL continuously evaluate whether the reserved capacity remains usable under current:

- position size;
- volatility;
- liquidity;
- margin schedule;
- collateral value;
- broker rate usage;
- account count;
- session health;
- network condition;
- protective-order coverage;
- market session and venue status.

When forecast protective capacity falls below the approved minimum, the system SHALL reduce ordinary authority before the reserve is exhausted.

A minimum sequence is:

```text
Reserve degradation detected
    -> LIVE_RESTRICTED
    -> DEGRADED_PROTECTIVE
    -> CONTAINED
    -> HALTED
```

The exact transition thresholds belong in the Safety Profile and Verification Specification.

---

### 9. Multi-Account Allocation

Where multiple accounts share protective infrastructure, reserve allocation SHALL include:

- a minimum protected allocation per account or risk domain;
- a separately identified global emergency pool, if any;
- explicit arbitration based on survivability impact rather than arrival order alone;
- prevention of one account exhausting all resources while another remains protectable;
- treatment of already trapped accounts separately from accounts where intervention remains effective;
- deterministic behavior under simultaneous incidents.

Normal strategy activity SHALL NOT borrow another account's minimum protective allocation.

---

### 10. Protective Lease Validity During Partition

A Protective Lease SHALL be valid only when all of the following can be proven locally:

- correct lease signature or integrity protection;
- current or still-valid authority epoch according to the approved partition model;
- exclusive local ownership;
- unused or sufficient remaining capacity;
- matching account and instrument scope;
- matching Hard Safety Envelope and Runtime Safety Profile constraints;
- monotonic lifetime not expired;
- no process restart that invalidates the lease;
- no local clock-health failure;
- no evidence conflict that makes the protective effect uncertain.

Wall-clock comparison alone is insufficient.

When remaining validity cannot be positively established, the lease is invalid for new transmissions.

Existing potentially-live protective attempts remain capacity-consuming and must be reconciled.

---

### 11. Protective Order Lifecycle and Ownership

#### 11.1 Ownership Assignment

Every order that provides required protection SHALL have explicit Protective Ownership.

Ownership determines who may:

- replace;
- resize;
- cancel;
- suspend;
- declare the protection ineffective.

#### 11.2 Cancellation Arbiter

A single Cancellation Arbiter SHALL authorize cancellation for any order that is or may be part of a protective structure.

The arbiter SHALL evaluate:

- whether cancellation removes active protection;
- whether replacement is already authoritatively live;
- whether aggregate risk becomes worse;
- whether the cancellation itself consumes scarce broker capacity;
- whether a late fill or partial fill remains possible.

Protective evaluation takes precedence over ordinary strategy cancellation.

#### 11.3 Safety-Owned Orders

A `SAFETY_OWNED` order SHALL NOT be cancelled by strategy or ordinary execution cleanup.

It may be cancelled only when:

- protection is no longer required and risk remains within the Hard Safety Envelope; or
- equivalent or stronger protection is authoritatively confirmed; or
- continued existence of the order creates greater conservative aggregate risk and the Protective Action Controller authorizes removal.

---

### 12. Protective Replacement and Protection Gap

#### 12.1 Atomic Replace

If the broker capability profile proves atomic cancel/replace semantics, the system may model the operation according to that guarantee.

#### 12.2 Non-Atomic Replace

For cancel-then-new or other non-atomic replacement:

- the position SHALL be classified as unprotected from the earliest point at which old protection may be ineffective until new protection is authoritatively confirmed;
- aggregate risk SHALL include the unprotected exposure;
- capacity SHALL cover the worst credible order overlap or the protection gap, whichever is more conservative;
- the gap duration SHALL be measured and bounded;
- failure to establish replacement protection SHALL trigger a defined containment response;
- the residual risk SHALL be approved per broker and action class.

#### 12.3 No Optimistic Protection Credit

A submitted, transmitted, or acknowledged replacement order SHALL NOT be credited as effective protection unless the approved protection criterion is met.

---

### 13. Potentially-Live Quantity and Release

#### 13.1 Reservation Persistence

Protective capacity remains consumed while any associated quantity may still create economic effect.

This includes:

- `SEND_STARTED` with uncertain outcome;
- `SENT_UNCONFIRMED`;
- acknowledged working quantity;
- partial fill with unconfirmed remainder;
- cancel pending;
- replace pending;
- UNKNOWN broker state;
- unresolved late-fill interval.

#### 13.2 Cancel Acknowledgement

Cancel acknowledgement does not by itself release protective capacity.

Release requires Final Quantity Proof under the broker capability profile.

#### 13.3 Partial Fill

On confirmed partial fill:

- filled risk transfers to confirmed-position consumption;
- remaining Potentially-Live Quantity retains open-order consumption;
- protective effectiveness is recalculated using confirmed fill quantity, not submitted quantity;
- retries SHALL target the desired safe position state, not blindly resend the original quantity.

#### 13.4 UNKNOWN Outcome

If transmission outcome is UNKNOWN and broker deduplication is not proven:

- blind resubmission is prohibited;
- the full conservative quantity remains consumed;
- available evidence is queried;
- unresolved attribution causes containment;
- no new protective attempt may reuse the same capacity.

---

### 14. Exhaustion and Bounded Retry

#### 14.1 Exhaustion Detection

Protective capacity is exhausted when any required dimension is unavailable or unverifiable, including:

- risk capacity;
- margin;
- broker request quota;
- broker session;
- worker/queue capacity;
- network path;
- trustworthy time;
- current protective lease;
- reconciliation capability.

#### 14.2 Exhaustion Behavior

Exhaustion SHALL NOT cause unbounded autonomous retry.

The system SHALL:

1. block all ordinary risk-increasing activity;
2. preserve existing commitments and Potentially-Live Quantity;
3. perform only bounded, policy-approved retry where retry cannot create duplicate economic effect;
4. escalate to operator control where useful;
5. enter `CONTAINED` or `HALTED` when no demonstrably safe action remains.

#### 14.3 Retry Budget

Protective retry SHALL consume an explicitly reserved retry budget for request rate, queue, and execution resources.

Retry budget exhaustion is itself a containment trigger.

---

### 15. Margin, Collateral, Basis, and Liquidity Constraints

A proposed protective action SHALL be denied when it cannot be shown to avoid unacceptable worsening of:

- initial or maintenance margin;
- collateral concentration;
- liquidation proximity;
- basis exposure;
- liquidity-adjusted exit cost;
- settlement mismatch;
- currency mismatch;
- correlation breakdown risk.

Reserved collateral SHALL be revalued continuously.

When market movement erodes collateral reserve below the approved protective minimum, normal risk authority SHALL be reduced before hard margin limits are reached.

---

### 16. Operator Emergency Path

The operator emergency path is a protective resource and SHALL be subject to the same safety boundaries.

It SHALL:

- use authenticated, scope-limited identities;
- present current account and evidence state;
- prevent operator commands from bypassing Hard Safety Envelope enforcement;
- distinguish halt, cancel, reduce, and re-arm authority;
- record immutable evidence;
- prohibit a single operator identity from both enlarging limits and arming live authority;
- remain unavailable for general strategy execution.

Operator action does not convert an unproven action into a protective action.

---

### 17. Broker Capability Dependency

The protective-capacity guarantee SHALL be conditioned on the approved Broker Capability Profile.

The profile SHALL identify at least:

- independent session availability;
- rate-limit scope;
- cancel semantics;
- replace semantics;
- reduce-only support;
- order identity and deduplication;
- fill replay and ordering;
- real-time versus polled account events;
- margin-query freshness;
- venue-session behavior.

Where capability is insufficient, the permitted degraded protective subset SHALL be reduced.

Examples of potentially admissible actions, subject to proof:

- cancellation of clearly risk-increasing unfilled orders;
- broker-enforced reduce-only action within confirmed position bounds;
- bounded same-instrument reduction under current position evidence;
- use of pre-existing safety-owned protective orders.

Examples that generally require stronger proof:

- cross-instrument hedge;
- multi-leg hedge;
- cancel-then-new protection replacement;
- action that can reverse a position;
- action that increases margin before reducing risk;
- action based on stale or UNKNOWN position state.

---

### 18. Verification Obligations

The ADR SHALL NOT be marked Accepted until evidence demonstrates at least the following.

#### 18.1 Reserve Isolation

- ordinary load cannot consume the configured minimum protective worker and queue allocation;
- ordinary rate usage cannot exceed the admitted ceiling that preserves the local protective request budget;
- any broker-level common mode is explicitly classified and tested.

#### 18.2 Duplicate Consumption

- two Protective Action Controller instances cannot consume the same lease capacity;
- stale lease owner cannot transmit after failover;
- process restart invalidates unprovable local lease authority.

#### 18.3 Intermediate Fill Safety

- 0%, partial, and full fill sequences are tested;
- leg-order inversion is tested for multi-leg actions;
- external position change during the detection window is tested;
- margin and basis shocks are included.

#### 18.4 Replacement Gap

- old protection cancelled and new protection delayed;
- new protection rejected;
- late fill on old protection;
- both old and new protection live;
- measured gap remains within the approved bound.

#### 18.5 Cancel and Late Fill

- cancel acknowledgement followed by late fill does not release capacity early;
- protective effectiveness and confirmed position update correctly;
- no exit retry creates position reversal.

#### 18.6 Exhaustion

- worker, queue, request quota, margin, network, time, and lease exhaustion each cause the defined state transition;
- retry remains bounded;
- normal strategy activity remains blocked.

#### 18.7 Multi-Account Contention

- simultaneous incidents do not allow one account to consume another account's minimum reserve;
- arbitration follows the approved survivability policy.

---

### 19. Consequences

#### 19.1 Positive

- resolves the contradiction between single aggregate committer and partition-time protective action;
- prevents duplicate consumption of protective reserve;
- distinguishes genuine reservation from mere priority;
- prevents strategy from bypassing protective classification;
- prevents capacity release before late-fill uncertainty is resolved;
- makes broker limitations explicit rather than hidden assumptions;
- accounts for protection replacement gaps and partial fills;
- creates measurable production evidence obligations.

#### 19.2 Negative

- some brokers may support only a narrow degraded protective subset;
- more capacity must remain unused during normal operation;
- protective leases and sub-ledgers increase state-machine complexity;
- non-atomic broker semantics may cause prolonged conservative capacity quarantine;
- system availability and trade opportunity are reduced by fail-closed behavior.

These costs are accepted because they preserve capital and long-term system survivability.

---

### 20. Rejected Alternatives

#### 20.1 Strategy-Declared Protective Flag

Rejected because the proposer would be able to bypass normal risk authority.

#### 20.2 Priority Without Reservation

Rejected as a safety guarantee because shared lower-level resources may already be exhausted or blocked.

#### 20.3 New Aggregate Commitment During Partition

Rejected because the current global headroom and authority epoch cannot be proven.

#### 20.4 Cancel Acknowledgement as Capacity Release

Rejected because crossing and late fills may still occur.

#### 20.5 Final-State-Only Risk Test

Rejected because partial fills, leg ordering, and margin/basis effects can make intermediate states less safe than taking no action.

#### 20.6 Unlimited Protective Retry

Rejected because it can exhaust broker quota, duplicate orders, and destroy the remaining protective path.

---

### 21. Dependencies

This amended ADR depends on:

- RFC-000 constitutional safe-state definition;
- RFC-001 Hard Safety Envelope, partition containment, trustworthy time, aggregate capacity, external reconciliation, and partial-fill requirements;
- RFC-002 Authority Matrix and Broker Egress enforcement;
- ADR-002-002 for aggregate commitment, protective pool, sub-reservation, release, crash recovery, and split-brain capacity semantics;
- Safety Authority Validity and Partition ADR;
- Broker Capability Requirements and Fallbacks ADR;
- Intent, Attempt, Order, and Knowledge State ADR;
- Trustworthy Time ADR.

---

### 22. Approval Gate

ADR-002-001 v0.2 may be accepted only when:

- every protective resource is assigned a guarantee level;
- aggregate commitment and protective consumption are unambiguous;
- a duplicate-consumption prevention mechanism is selected;
- degraded lease validity and process-restart behavior are defined;
- intermediate-state protective proof is specified;
- replacement-gap handling is defined per broker capability;
- cancellation ownership and arbitration are implemented in the architecture;
- exhaustion and retry bounds have measurable acceptance criteria;
- residual common-mode broker limitations are explicitly approved.
