# ADR-002-001 — Degraded-Mode Protective Capacity

**ADR ID:** ADR-002-001
**Title:** Degraded-Mode Protective Capacity
**Status:** Proposed
**Decision Type:** Safety-Critical Architecture Decision
**Parent Document:** RFC-002 — Trading Operating System Architecture
**Governed By:** RFC-000 and RFC-001
**Date:** 2026-07-13
**Version:** 0.4 Part-2/3 Register Consolidation Draft
**Last Updated:** 2026-07-17
**Supersedes:** ADR-002-001 v0.3 Evidence-Gate Binding Draft
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
* SAFE-003 — Fail-Closed Safety Profile;
* SAFE-004 — Hard Safety Envelope;
* SAFE-011 — Non-Bypassable Safety Limits;
* SAFE-013 — Aggregate Risk Authority;
* SAFE-014 — Bounded Action Rate;
* SAFE-015 — Exclusive Risk-Capacity Commitment;
* SAFE-021 — At-Most-One Exposure Effect;
* SAFE-024 — Continuous External-State Reconciliation;
* SAFE-025 — Partial and Asynchronous Fill Integrity;
* SAFE-035 — Trustworthy Time Basis;
* SAFE-040 — Protective Control in Degraded Operation;
* SAFE-041 — Independent Safety Authority;
* SAFE-043 — Exit-Unavailable Containment;
* SAFE-044 — Safe Start and Resume;
* SAFE-048 — Partition-Tolerant Safety Authority;
* SAFE-050 — Safety Configuration Governance;
* SAFE-051 — Decision and Execution Evidence.

---

## 3. Decision

The TOS SHALL implement a **Reserved Protective Capacity Architecture** separated from ordinary trading capacity across every resource dimension on which protection depends.

Reserved Protective Capacity SHALL be represented at two levels:

1. **Aggregate Protective Commitment** — capacity removed from normal headroom and committed in advance by the authoritative Risk Capacity Ledger;
2. **Protective Action Consumption** — exclusive binding of a portion of the committed pool to a specific protective action.

The architecture SHALL provide reserved execution, broker/API action, risk, margin, collateral, reconciliation, evidence, and operator-control capacity where required; a separately governed Protective Action Controller; independently validated classification; and degraded operation that does not depend on ordinary strategy authority.

Normal trading SHALL NOT consume the minimum reserved protective capacity.

No new aggregate capacity may be committed during a Safety Control Plane partition. During a partition, only a previously issued, current, exclusive, scope-limited Protective Lease may be consumed. The lease SHALL NOT be enlarged, replenished, transferred, or reused without restoration of the normal authority path.

Protective action is permitted only when the system proves before transmission that the action remains within the Hard Safety Envelope and does not increase conservative aggregate portfolio risk across every credible intermediate execution state.

### 3.1 Terminology

#### 3.1.1 Aggregate Protective Commitment

A durable Risk Capacity Ledger commitment that removes a defined capacity vector from normal strategy availability and assigns it to a protective pool. The Aggregate Risk Authority may approve the allocation; the Risk Capacity Ledger is the sole state-transition authority that creates it.

#### 3.1.2 Protective Lease

A bounded delegation of part of an Aggregate Protective Commitment to one Protective Action Controller authority domain.

A Protective Lease SHALL include:

* lease and parent commitment identity;
* account and instrument or instrument-class scope;
* allowed protective action classes;
* maximum quantity and risk-vector effect;
* margin, collateral, and representable broker/API resource allowances;
* Authority Epoch and single active owner;
* monotonic lifetime and consumption-state identity;
* Hard Safety Envelope and Runtime Safety Profile versions.

#### 3.1.3 Protective Consumption

An exclusive sub-reservation within a valid Protective Lease, bound to one protective Intent and one or more explicitly identified transmission attempts. Protective Consumption does not create new aggregate headroom.

#### 3.1.4 Protective Resource Guarantee Level

The evidenced availability class for a protective resource: `PHYSICALLY_RESERVED`, `LOGICALLY_RESERVED`, `PRIORITIZED_ONLY`, `BEST_EFFORT`, or `UNAVAILABLE`.

A prioritized resource is not a reserved resource.

#### 3.1.5 Protection Gap

A period during which previously effective protection has been removed, invalidated, or reduced before equivalent or stronger replacement protection is confirmed live.

#### 3.1.6 Protective Ownership

The authority class responsible for maintaining, replacing, or cancelling a protective order: `STRATEGY_OWNED`, `EXECUTION_OWNED`, `SAFETY_OWNED`, or `OPERATOR_OWNED`.

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

The architecture SHALL classify and, where technically possible, reserve sufficient broker/API capacity for:

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

The operator and Safety Authority control paths SHALL be admitted and isolated from ordinary trading traffic according to their evidenced guarantee level.

### 4.6 Required Resource Dimensions and Guarantee Classification

Reserved Protective Capacity SHALL be evaluated separately for at least:

* execution workers and request queues;
* broker/API request rate, broker session availability, and order-message rate;
* aggregate risk capacity, margin, collateral, and protective retry budget;
* network and control path;
* reconciliation and evidence-persistence capacity;
* operator emergency path;
* trustworthy-time and protective-authorization capability.

Each resource dimension SHALL be classified as `PHYSICALLY_RESERVED`, `LOGICALLY_RESERVED`, `PRIORITIZED_ONLY`, `BEST_EFFORT`, or `UNAVAILABLE`.

A resource SHALL NOT be described as guaranteed unless its reservation mechanism and failure independence have been demonstrated. Priority is not reservation.

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

The Protective Action Controller may consume only pre-committed capacity under a valid Protective Lease. It SHALL NOT enlarge aggregate authority, mutate the Risk Capacity Ledger outside its defined transition interface, or transmit directly. The Broker Adapter / Broker Egress Gateway remains the final transmission enforcement point.

---

## 6. Protective Action Classification

Only the Protective Action Controller may classify an action as protective using conservative aggregate-risk analysis.

A strategy flag, sell direction, exit or hedge name, reduce-position intent, operator description, or correlation with an existing position is non-authoritative.

### 6.1 Final-State Test

The intended final state SHALL satisfy:

```text
Projected conservative aggregate post-action risk
    <
Current conservative aggregate risk
```

for the relevant risk dimensions while remaining within the Hard Safety Envelope.

### 6.2 Intermediate-State Test

The final-state test is necessary but not sufficient.

For every credible combination of partial-fill fraction, execution ordering, leg failure, acknowledgement loss, cancel/replace race, late fill, external position change within the detection bound, basis movement, liquidity deterioration, and margin revaluation, the system SHALL prove:

```text
Worst-case conservative risk after the intermediate state
    <=
Risk of taking no protective action
```

and every hard limit SHALL remain satisfied.

If this cannot be demonstrated, the action SHALL be classified as risk increasing and denied in degraded mode.

### 6.3 Risk Dimensions

Protective analysis SHALL include, where relevant:

* gross and net directional exposure;
* leverage and margin utilization;
* concentration and liquidity-adjusted exit risk;
* basis risk, correlation breakdown, and gap risk;
* option Greeks, settlement, and rollover risk;
* collateral encumbrance and currency mismatch;
* broker order-rate consumption and loss of existing protection.

A hedge that reduces delta but materially worsens margin, basis, liquidity, concentration, or another governed dimension MAY be denied.


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
2. no new Aggregate Protective Commitment may be created or enlarged;
3. uncommitted ordinary intents SHALL expire or remain blocked;
4. ordinary strategies SHALL lose transmission authority;
5. only an already valid Protective Lease may be consumed;
6. the protective sub-ledger or equivalent serialized mechanism SHALL prevent duplicate consumption;
7. stale permissive authority SHALL NOT be reused.

A Protective Lease is valid for new transmission only while all of the following can be proven locally:

* correct signature or integrity protection;
* current or still-valid Authority Epoch under ADR-002-003;
* exclusive local ownership;
* unused or sufficient remaining capacity;
* matching account, instrument, and action scope;
* matching Hard Safety Envelope and Runtime Safety Profile constraints;
* monotonic lifetime not expired;
* no process restart that invalidates the lease;
* no local time-health failure;
* no evidence conflict that makes the protective effect uncertain.

Wall-clock comparison alone is insufficient. If ownership, epoch, scope, remaining capacity, or validity cannot be proven, no new protective transmission may use the lease.

Potentially-live actions already issued under the lease remain capacity-consuming and enter reconciliation. Authority expiry does not expire their economic effect.


## 10. Behavior When Time Cannot Be Trusted

If the Trustworthy Time Basis is unavailable:

* time-dependent live authority SHALL be invalid;
* time-dependent protective authorization SHALL be invalid;
* new protective orders SHALL NOT be submitted unless an independently approved non-time-dependent emergency rule applies;
* cancellation of confirmed risk-increasing open orders MAY remain permitted when cancellation can be shown not to increase aggregate risk;
* operator escalation SHALL occur.

The architecture SHALL NOT treat an unverified protective authorization as permanently valid.

---

## 11. Protective Order Lifecycle and Cancellation

Cancellation is not automatically protective.

### 11.1 Protective Ownership

Every order that provides required protection SHALL have explicit Protective Ownership. Ownership determines who may replace, resize, cancel, suspend, or declare the protection ineffective.

A `SAFETY_OWNED` order SHALL NOT be cancelled by strategy or ordinary execution cleanup. It may be cancelled only when:

* protection is no longer required and risk remains within the Hard Safety Envelope; or
* equivalent or stronger protection is authoritatively confirmed; or
* continued existence creates greater conservative aggregate risk and the Protective Action Controller authorizes removal.

### 11.2 Cancellation Arbiter

A single Cancellation Arbiter SHALL authorize cancellation for every order that is or may be part of a protective structure.

The arbiter SHALL evaluate whether cancellation removes protection, whether replacement is authoritatively live, whether aggregate risk becomes worse, whether scarce broker capacity is consumed, and whether late or partial fills remain possible.

Protective evaluation SHALL precede ordinary strategy cancellation.

### 11.3 Ordinary Risk-Increasing Orders

Cancellation MAY proceed only through the Cancellation Arbiter when an order is risk increasing, no longer authorized, outside the Safety Profile, duplicated, or inconsistent with authoritative exposure and cancellation itself cannot worsen conservative aggregate risk.

### 11.4 Protective Replacement and Protection Gap

If the Broker Capability Profile proves atomic cancel/replace semantics, the system MAY model the operation according to that guarantee.

For non-atomic replacement:

* the position SHALL be classified as unprotected from the earliest point old protection may be ineffective until new protection satisfies the approved effective-protection criterion;
* aggregate risk SHALL include the unprotected exposure;
* capacity SHALL cover the more conservative of worst credible order overlap or the Protection Gap;
* the gap duration SHALL be measured and bounded;
* replacement failure SHALL trigger a defined containment response;
* residual risk SHALL be approved per broker and action class.

A submitted, transmitted, or acknowledged replacement order SHALL NOT receive optimistic protection credit.


## 12. Reserved Capacity Commitment and Consumption

### 12.1 Normal State

In `LIVE_NORMAL` or another state with current Safety Control Plane authority:

1. the Aggregate Risk Authority evaluates the required protective reserve;
2. the Risk Capacity Ledger atomically commits the protective pool;
3. the committed pool is removed from normal strategy headroom;
4. one or more bounded Protective Leases may be issued from that pool;
5. lease issuance SHALL NOT make the same parent capacity available to multiple owners.

Normal strategies may use only normal capacity and SHALL NOT borrow a protective allocation.

### 12.2 Partition or Degraded State

In `DEGRADED_PROTECTIVE`:

* no new Aggregate Protective Commitment may be created or enlarged;
* only an already valid Protective Lease may be consumed;
* the protective sub-ledger or equivalent serialized mechanism SHALL prevent duplicate consumption;
* unused lease capacity SHALL NOT be borrowed for ordinary trading;
* consumed capacity remains bound until Final Quantity Proof or confirmed-position transfer is complete.

### 12.3 Loss of Exclusivity

If the system cannot prove that a Protective Lease has one current owner, no new protective transmission may use the lease. Potentially-live actions already issued under that lease remain capacity-consuming and enter reconciliation.

### 12.4 Guarantee Levels and Common Modes

`PHYSICALLY_RESERVED` requires a failure-independent partition ordinary traffic cannot consume.

`LOGICALLY_RESERVED` means the TOS prevents ordinary consumption but shares a lower-level dependency; explicit common-mode analysis is required.

`PRIORITIZED_ONLY` means ordinary work is deprioritized but may already occupy or exhaust the resource. It SHALL NOT be relied upon as guaranteed capacity.

`BEST_EFFORT` is residual risk. The system SHALL compensate through earlier degradation, lower normal admission, smaller live scope, larger margin reserve, reduced action frequency, stronger operator readiness, or prohibition of strategies that depend on unavailable protection.

Where the broker exposes a single serialized session or global account rate limit, ordinary traffic SHALL be admitted below the demonstrated limit, local request capacity SHALL be withheld for protection, stuck requests SHALL have bounded handling, and the remaining common mode SHALL be documented honestly.

### 12.5 Dynamic Reserve Sufficiency

Protective reserve is not a static configuration value. The system SHALL continuously evaluate its usability under current position size, volatility, liquidity, margin schedule, collateral value, broker rate use, account count, session and network health, protective coverage, market session, and venue state.

When forecast capacity falls below the approved minimum, ordinary authority SHALL be reduced before reserve exhaustion:

```text
Reserve degradation detected
    -> LIVE_RESTRICTED
    -> DEGRADED_PROTECTIVE
    -> CONTAINED
    -> HALTED
```

Exact thresholds belong in the Safety Profile and Verification Specification.

### 12.6 Multi-Account Allocation

Where accounts share protective infrastructure, allocation SHALL provide:

* a minimum protected allocation per account or risk domain;
* an identified global emergency pool, if any;
* survivability-based rather than arrival-order-only arbitration;
* prevention of one account exhausting another account's minimum;
* separate treatment of already trapped and still-protectable accounts;
* deterministic behavior under simultaneous incidents.


## 13. Capacity Exhaustion and Bounded Retry

Protective capacity is exhausted when any required resource dimension is unavailable or unverifiable, including risk capacity, margin, broker quota or session, worker or queue capacity, network path, trustworthy time, current Protective Lease, or reconciliation capability.

Exhaustion SHALL NOT cause unbounded autonomous retry.

The system SHALL:

1. block all ordinary risk-increasing activity;
2. preserve existing commitments and Potentially-Live Quantity;
3. perform only bounded, policy-approved retry where retry cannot create duplicate economic effect;
4. allocate remaining resources by survivability impact and protective priority;
5. keep trapped or unmanaged exposure explicitly visible;
6. escalate to operator control where useful;
7. enter `CONTAINED` or `HALTED` when no demonstrably safe action remains;
8. never report a safe or flat state unless authoritatively confirmed.

Protective retry SHALL consume an explicitly reserved retry budget for request rate, queue, and execution resources. Retry-budget exhaustion is itself a containment trigger and a Critical operational event.


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

### 14.1 Reservation Persistence

Protective capacity remains consumed while any associated quantity may still create economic effect, including `SEND_STARTED` with uncertain outcome, `SENT_UNCONFIRMED`, acknowledged working quantity, partial fill with unconfirmed remainder, cancel pending, replace pending, UNKNOWN broker state, and an unresolved late-fill interval.

Authority, lease, or reservation TTL expiry does not expire economic effect.

### 14.2 Cancel Acknowledgement and Final Quantity Proof

Cancel acknowledgement does not by itself release protective capacity. Release requires Final Quantity Proof under the approved Broker Capability Profile.

### 14.3 Partial Fill

On confirmed partial fill:

* filled risk transfers to confirmed-position consumption;
* remaining Potentially-Live Quantity retains open-order consumption;
* protective effectiveness is recalculated using confirmed fill quantity;
* retries target the desired safe position state and SHALL NOT blindly resend the original quantity.

### 14.4 UNKNOWN Outcome

If transmission outcome is UNKNOWN and broker deduplication is not proven:

* blind resubmission is prohibited;
* the full conservative quantity remains consumed;
* all available evidence is queried;
* unresolved attribution causes containment;
* no new attempt may reuse the same capacity.

### 14.5 Margin, Collateral, Basis, and Liquidity

A proposed action SHALL be denied when it cannot be shown to avoid unacceptable worsening of initial or maintenance margin, collateral concentration, liquidation proximity, basis, liquidity-adjusted exit cost, settlement or currency mismatch, or correlation-breakdown risk.

Reserved collateral SHALL be revalued continuously. When market movement erodes it below the approved minimum, normal risk authority SHALL be reduced before hard margin limits are reached.

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

The Recovery Coordinator may produce readiness but SHALL NOT issue Live Authorization. Re-arm requires a current Safety Authority epoch, account-wide reconciliation, Risk Capacity Ledger consistency, evaluated protective coverage, a new Live Authorization, and explicit human dual control. No automatic re-arm is permitted.

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

### 17.6 Priority Without Reservation as a Safety Guarantee

**Rejected.**

Shared lower-level resources may already be exhausted or blocked. Priority alone cannot guarantee protective capacity.

### 17.7 New Aggregate Commitment During Partition

**Rejected.**

Current global headroom and authority epoch cannot be proven during the partition.

### 17.8 Cancel Acknowledgement as Capacity Release

**Rejected.**

Crossing and late fills may remain possible.

### 17.9 Final-State-Only Risk Test

**Rejected.**

Partial fills, leg ordering, margin, basis, and liquidity effects may make an intermediate state less safe than taking no action.

### 17.10 Unlimited Protective Retry

**Rejected.**

It can exhaust broker quota, duplicate economic effect, and destroy the remaining protective path.

---

## 18. Consequences

### 18.1 Positive Consequences

* degraded operation preserves containment capacity;
* normal strategies cannot exhaust all protective resources;
* protective actions are independently classified;
* partition behavior is explicit;
* risk and margin required for protection can be preserved;
* failure does not automatically imply unmanaged exposure.
* aggregate commitment and partition-time consumption cannot create duplicate headroom;
* broker common modes, protection gaps, UNKNOWN sends, and late fills remain explicit.

### 18.2 Negative Consequences

* some resources remain unused during normal operation;
* maximum normal trading throughput may be lower;
* capital efficiency may be reduced;
* architecture and testing complexity increase;
* broker-specific capacity planning is required;
* protective classification requires a separate risk evaluation path.
* non-atomic broker semantics may cause prolonged conservative capacity quarantine;
* some brokers may support only a narrow degraded-protective subset.

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

### 19.7 Duplicate Lease Consumption

Multiple current or stale controllers consume the same protective capacity.

### 19.8 Protection Replacement Gap

Old protection becomes ineffective before equivalent replacement is authoritatively live.

### 19.9 Reserve Erosion or Cross-Account Starvation

Dynamic margin, liquidity, rate, or infrastructure change makes the configured reserve unusable, or one account consumes another account's minimum.

### 19.10 Unbounded Protective Retry

Retry exhausts the remaining protective path or creates duplicate economic effect.

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

### 20.10 Duplicate Consumption and Failover

Expected result:

* two Protective Action Controller instances cannot consume the same lease capacity;
* a stale lease owner cannot transmit after failover;
* process restart invalidates unprovable local lease authority.

### 20.11 Intermediate Fill and Ordering Safety

The test set SHALL cover 0%, partial, and full fills; multi-leg ordering inversion; external position change during the detection window; and margin, basis, and liquidity shocks.

Expected result: every credible intermediate state remains within the Hard Safety Envelope and is no worse than taking no protective action.

### 20.12 Protection Replacement Gap

The test set SHALL cover delayed and rejected replacement, late fill on old protection, and both old and new orders live.

Expected result: overlap or unprotected exposure remains conservatively covered, the gap is measured, and the approved containment response occurs.

### 20.13 Cancel and Late Fill

Expected result:

* cancel acknowledgement followed by late fill does not release capacity early;
* protective effectiveness and confirmed position update correctly;
* no retry reverses the position.

### 20.14 Multi-Account Contention

Expected result: simultaneous incidents cannot consume another account's minimum reserve, and arbitration follows the approved survivability policy.

These written scenarios are verification requirements, not completed evidence. ADR acceptance requires actual execution, retained raw artifacts, invariant evaluation, measured bounds, hashes, and independent review under VER-002-001.

---

## 21. Acceptance Criteria

Each criterion below binds the verification evidence that discharges it. The consolidated required-evidence set for this ADR is enumerated in VER-002-001 §380 (`ADR-002-001`); the Part-2/3 register consolidation (Wave 4) registered dedicated rows PRD-EV-001 and PRD-EV-002 for criteria #1 and #11, and the Evidence Register count is now 372.

This ADR MAY be accepted when:

* protective resource domains are identified for each supported broker and market (Evidence: PRD-EV-001, supported by BC-EV-013, BC-EV-021; dedicated enumeration-completeness row registered in the Wave-4 consolidation);
* the minimum reservation policy is defined in the Safety Profile (Evidence: SPG-EV-001, SPG-EV-002, SPG-EV-011);
* normal trading cannot consume the protected reserve (Evidence: RC-EV-001, X-EV-005, AFG-EV-001, RCLP-EV-004);
* protective classification is independent of strategy (Evidence: FD-EV-001, ARE-EV-010);
* partition behavior is implemented and tested (Evidence: SA-EV-003, SA-EV-004, RC-EV-012, X-EV-002, X-EV-003);
* capacity exhaustion behavior is implemented and tested (Evidence: PR-EV-007, FD-EV-010, AFG-EV-003);
* partial-fill behavior is demonstrated (Evidence: RC-EV-006, PR-EV-005, ARE-EV-003);
* trapped-exposure behavior is demonstrated (Evidence: RC-EV-014);
* no test permits a protective label to bypass aggregate-risk evaluation (Evidence: ARE-EV-001, ARE-EV-010, IOC-EV-006);
* evidence is independently reviewed (Evidence: independent-review gate clause, VER-002-001 §380 `ADR-002-001`).

It additionally requires:

* every protective resource assigned an evidenced guarantee level (Evidence: PRD-EV-002, supported by SPG-EV-001; dedicated per-resource guarantee-level row registered in the Wave-4 consolidation);
* aggregate commitment and Protective Consumption implemented without ambiguity (Evidence: RCLP-EV-001, RCLP-EV-011, RC-EV-001);
* duplicate-consumption prevention and stale-owner fencing selected and demonstrated (Evidence: RC-EV-002, SA-EV-006, SA-EV-007, RCLP-EV-003);
* degraded lease validity and restart behavior defined (Evidence: SA-EV-004, SA-EV-005, SA-EV-006, RC-EV-013, X-EV-008);
* intermediate-state proof implemented (Evidence: PR-EV-005, RC-EV-016, ARE-EV-003);
* replacement-gap handling defined per Broker Capability Profile (Evidence: PR-EV-001, PR-EV-002, PR-EV-006, PR-EV-012);
* cancellation ownership and arbitration enforced (Evidence: PR-EV-011, X-EV-006);
* exhaustion and retry bounds approved and measured (Evidence: PR-EV-007, AFG-EV-003);
* common-mode broker limitations explicitly accepted with reduced scope (Evidence: BC-EV-016, FD-EV-008, VTG-EV-010).

Until those conditions are supported by completed evidence, this ADR remains `Proposed`.

---

## 22. Traceability

| Requirement | ADR decision                                                |
| ----------- | ----------------------------------------------------------- |
| SAFE-001    | Degraded operation enters an exposure-aware safe state      |
| SAFE-002    | Existing exposure retains protective control                |
| SAFE-003    | Invalid or unverifiable protective configuration fails closed |
| SAFE-004    | Every protective action remains inside the Hard Safety Envelope |
| SAFE-011    | Protective authority is not controlled by strategy          |
| SAFE-013    | Protective actions use aggregate risk                       |
| SAFE-014    | Protective traffic remains available under runaway activity |
| SAFE-015    | Protective capacity is exclusively committed                |
| SAFE-021    | Potentially-live protective attempts cannot multiply economic effect |
| SAFE-024    | External activity invalidates protective assumptions within a bound |
| SAFE-025    | Partial, asynchronous, crossing, and late fills retain capacity |
| SAFE-035    | Lease validity fails closed without trustworthy monotonic time |
| SAFE-040    | Protective controls remain available during degradation     |
| SAFE-041    | Safety Authority governs protective operation               |
| SAFE-043    | Trapped and exit-unavailable exposure remains controlled    |
| SAFE-044    | Recovery readiness does not automatically re-arm live scope  |
| SAFE-048    | Partition behavior revokes new-risk authority               |
| SAFE-050    | Protective limits remain subordinate to governed safety configuration |
| SAFE-051    | Protective decisions and transitions produce retained evidence |

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

### 23.1 Broker Capability Dependency

The protective-capacity guarantee is conditioned on an approved Broker Capability Profile covering independent session availability, rate-limit scope, cancel and replace semantics, reduce-only enforcement, order identity and deduplication, fill replay and ordering, account-event delivery, margin-query freshness, and venue-session behavior.

Insufficient capability SHALL reduce the permitted protective subset and live scope; it SHALL NOT weaken the safety property.

### 23.2 Operator Emergency Path

The operator emergency path is a protective resource. It SHALL use authenticated scope-limited identities, present current evidence state, preserve Hard Safety Envelope enforcement, distinguish halt/cancel/reduce/re-arm authority, retain immutable evidence, separate limit enlargement from live arming, and remain unavailable for general strategy execution.

Operator action does not convert an unproven action into a protective action.

### 23.3 Dependencies

This decision depends on RFC-000, RFC-001, RFC-002, ADR-002-002, ADR-002-003, ADR-002-004, ADR-002-005, ADR-002-008, ADR-002-011, and VER-002-001. Detailed state, time, and replacement mechanisms remain delegated to their assigned ADRs.

---

## 24. Decision Summary

The TOS SHALL reserve independent and bounded protective capacity across every resource dimension on which containment depends.

The Risk Capacity Ledger is the sole authority that commits aggregate protective capacity. During partition, the Protective Action Controller may consume only an exclusive, current, pre-committed Protective Lease and cannot create or enlarge headroom.

Normal strategy activity SHALL NOT consume the minimum reserve. Priority alone SHALL NOT be represented as guaranteed capacity.

Protective action requires conservative proof across final and credible intermediate states. UNKNOWN sends, Potentially-Live Quantity, crossing or late fills, and non-atomic replacement remain capacity-consuming until Final Quantity Proof or confirmed-position transfer.

Loss of authority contact stops new risk. Stale epochs and owners are fenced. Recovery does not re-arm live operation automatically.

This decision does not guarantee that every position can be exited. It ensures ordinary operation cannot consume or bypass the system's proven ability to attempt containment when failure occurs.


## 25. Review History

### v0.1 — Initial Proposed Decision

* Established reserved protective capacity and independent protective classification.
* Prohibited ordinary strategy consumption of the minimum reserve.
* Defined degraded modes, trapped exposure, capacity exhaustion, and explicit re-arm.

### v0.2 — Architecture Review Consolidation

* Separated Aggregate Protective Commitment from Protective Consumption.
* Made the Risk Capacity Ledger the sole aggregate capacity mutation authority.
* Added exclusive monotonic-time-bounded Protective Leases and stale-owner fencing.
* Distinguished physical/logical reservation from priority and best effort.
* Required conservative safety proof across credible intermediate execution states.
* Added ownership, cancellation arbitration, Protection Gap, Final Quantity Proof, UNKNOWN-send, dynamic reserve, multi-account, and bounded-retry rules.
* Kept the ADR Proposed pending executed and independently reviewed evidence.

### v0.3 — Evidence-Gate Binding

* Bound every §21 acceptance criterion to its discharging verification evidence, closing the prior gap in which the acceptance criteria named no evidence items and VER-002-001 §380 carried no ADR-002-001 gate.
* Added the consolidated `ADR-002-001` approval gate to VER-002-001 §380 (required RC/SA/PR/ARE/IOC/FD/RCLP/AFG/SPG/BC/VTG/X evidence set plus an approved Broker Capability Profile and Safety Profile per protective resource domain and guarantee level, and independent review).
* Recorded criteria #1 (protective-resource-domain enumeration completeness) and #11 (per-resource guarantee level) as PARTIAL: they are gated by Broker Capability Profile / Safety Profile artifacts and carry dedicated evidence debt in ARCHITECTURE-GATE-STATUS §4.4. No register row was added; the Evidence Register count remains 363.
* Change recorded in PATCH-ADR-002-001-v0.3-Evidence-Gate-Binding.md. The §21↔evidence mapping is an EV-L0 review item; the ADR remains Proposed pending executed and independently reviewed evidence.

### v0.4 — Part-2/3 Register Consolidation (Wave 4)

* Registered dedicated evidence rows PRD-EV-001 (protective-resource-domain enumeration completeness) and PRD-EV-002 (per-resource guarantee-level assignment completeness) under the new ADR-002-001-owned `PRD` family, discharging the criteria #1 and #11 evidence debt recorded in ARCHITECTURE-GATE-STATUS §4.4.
* Re-bound §21 criteria #1 and #11 from PARTIAL (BC-EV-013/BC-EV-021 and SPG-EV-001) to their dedicated PRD-EV rows, supported by those existing families; added PRD-EV-001/PRD-EV-002 to the ADR-002-001 approval gate in VER-002-001 §380 (VER §391–392).
* The Evidence Register count moved from 363 to 372 (nine Part-1 debt rows across ADR-002-001/013/015). The ADR remains `Proposed` pending executed and independently reviewed evidence; the PRD family placement and criticality are EV-L0 review items.
