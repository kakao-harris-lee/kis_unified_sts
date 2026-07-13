# ADR-002-002 — Aggregate Risk-Capacity Commitment Model

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Aggregate risk-capacity calculation, reservation identity, atomic commitment, concurrency, protective pools, order-attempt binding, partial fills, release proof, crash recovery, split-brain prevention, UNKNOWN orders, external exposure, and trapped exposure
- **Supersedes:** None
- **Amends:** RFC-002 v0.2 capacity semantics and consolidated ADR-002-001 v0.2 protective-capacity semantics

---

## 1. Decision

The Trading Operating System SHALL use a **single authoritative, linearizable Risk Capacity Ledger** as the sole serialization point for all risk-capacity commitments and releases.

The Aggregate Risk Authority owns the policy decision to grant or deny risk allocation. The Risk Capacity Ledger owns the atomic state transition that commits, changes, quarantines, transfers, or releases capacity.

No order may become eligible for live transmission unless:

1. its Intent is registered;
2. its aggregate risk effect has been approved;
3. a unique capacity reservation has been atomically committed;
4. the reservation has been bound to a unique transmission attempt;
5. a single-use Transmission Capability has been issued;
6. the Broker Adapter verifies the current reservation, authority epoch, live scope, and request conformance.

Once an order attempt may have reached the broker, its potential economic effect SHALL remain capacity-consuming until final quantity is proven or the consumption is transferred to confirmed-position risk.

`UNKNOWN` is a capacity-consuming state. It is never interpreted as rejected, cancelled, unfilled, or safe to retry.

Reserved Protective Capacity SHALL be committed in advance and removed from normal strategy headroom. During partition, the Protective Action Controller may only consume an exclusive, pre-committed protective lease; it may not create new aggregate headroom.

---

## 2. Context

The system may receive concurrent proposals from multiple strategies, retries, recovery workers, operators, and protective-control paths. Every proposal may independently appear safe when evaluated against the same pre-action portfolio state while their combined effect exceeds the Hard Safety Envelope.

The system must also survive failures at every point between internal authorization and external broker effect:

- crash before send;
- crash during send;
- send success with lost acknowledgement;
- duplicate active instances;
- stale leader resuming after failover;
- partial and asynchronous fills;
- cancel crossing a fill;
- non-atomic replace;
- late broker events;
- process restart with live orders;
- external HTS or third-party activity;
- broker query omission;
- corporate or non-trade position changes;
- trapped or illiquid exposure;
- Safety Control Plane partition.

A normal database record, asynchronous event, or optimistic in-memory check cannot prevent double-spending of aggregate headroom.

A broker acknowledgement cannot be the boundary of safety because acknowledgement may be lost, delayed, duplicated, or ordered differently from fills.

A reservation TTL cannot be the boundary of safety because economic effect does not disappear when local authority expires.

---

## 3. Decision Drivers

The model is selected to satisfy the following drivers, in precedence order:

1. Long-term system survivability;
2. capital preservation;
3. operational safety;
4. decision and execution integrity;
5. prevention of duplicate or unbounded economic effect;
6. conservative behavior under incomplete or conflicting evidence;
7. recoverability and auditability;
8. bounded degraded protective operation;
9. availability and performance.

The model must provide the following safety properties:

- no concurrent double-spending of aggregate headroom;
- exactly one authoritative commitment transition for each reservation;
- stale-writer fencing;
- no live transmission without committed capacity;
- no blind retry after uncertain transmission;
- no capacity release before final economic effect is proven;
- correct partial-fill transfer between open-order and position consumption;
- conservative treatment of UNKNOWN, unattributed, and trapped exposure;
- pre-committed, non-borrowable protective capacity;
- deterministic recovery after crash or failover.

---

## 4. Scope

This ADR decides:

- the abstract risk-capacity model;
- commitment authority and serialization;
- reservation and lease identity;
- capacity state transitions;
- concurrency and compare-and-set behavior;
- order-attempt and broker-egress binding;
- retry, partial-fill, cancel, replace, and late-fill treatment;
- protective-pool allocation and partition-time consumption;
- crash, restart, and split-brain behavior;
- reconciliation-driven quarantine and release;
- acceptance criteria.

This ADR does not select:

- a database vendor;
- a consensus product;
- a Kubernetes topology;
- exact timeout values;
- exact risk-model coefficients;
- broker-specific capability classification;
- detailed Safety Authority election mechanism;
- complete broker-order and knowledge state machines.

Those implementation choices must conform to this ADR.

---

## 5. Safety Invariants

### INV-001 — Aggregate Envelope

For every governed risk constraint `c`:

```text
ConfirmedPositionUsage[c]
+ PotentiallyLiveUsage[c]
+ UnknownUsage[c]
+ ExternalUnattributedUsage[c]
+ TrappedUsage[c]
+ ReplacementOverlapUsage[c]
+ NormalCommittedUnboundUsage[c]
+ ProtectivePoolCommittedUsage[c]
    <= EffectiveLimit[c]
```

where:

```text
EffectiveLimit[c]
    = min(HardSafetyEnvelope[c], RuntimeSafetyProfile[c])
```

The Runtime Safety Profile may reduce but never enlarge the Hard Safety Envelope.

The accounting representation SHALL avoid double-counting when capacity moves between categories. A transition from open-order reservation to confirmed-position usage transfers consumption atomically rather than adding a second independent allocation.

### INV-002 — Unique Commitment Mapping

Every potentially executable broker attempt SHALL map to exactly one active reservation allocation or one active consumption under a unique protective lease.

No active reservation allocation may authorize two independent economic attempts unless the broker capability profile proves deterministic idempotency and the attempts represent the same broker-side order identity.

### INV-003 — Exclusive Headroom

The same unit of aggregate headroom SHALL NOT be committed to more than one reservation, protective pool, lease, or external quarantine.

### INV-004 — No Transmission Without Capacity

The final Broker Adapter or broker-egress gateway SHALL reject any risk-relevant request lacking a valid, current, unused Transmission Capability bound to active committed capacity.

### INV-005 — No Expiry of Economic Effect

Authorization may expire. Potential economic effect does not expire until final quantity is proven.

Once a transmission attempt reaches `SEND_STARTED` or any state where broker receipt cannot be disproven, no TTL, lease expiry, process restart, operator declaration, or missing query result may release its capacity.

### INV-006 — UNKNOWN Consumes Capacity

Any unresolved uncertainty about order existence, quantity, fill, attribution, or remaining executable effect SHALL be represented by a conservative upper bound and shall consume capacity.

### INV-007 — Final Quantity Before Release

Capacity associated with a broker attempt SHALL be released only after the system establishes:

- final cumulative filled quantity; and
- zero remaining executable quantity;

or obtains a stronger proof explicitly approved for that broker capability profile.

### INV-008 — Stale Authority Cannot Mutate or Transmit

A fenced or stale authority epoch SHALL be unable to:

- create or enlarge a commitment;
- bind a new attempt;
- release capacity;
- reassign a protective lease;
- issue an accepted Transmission Capability;
- transmit through broker egress.

### INV-009 — Protective Reserve Is Non-Borrowable

Normal strategy activity SHALL NOT consume the configured minimum Reserved Protective Capacity.

### INV-010 — Partition Does Not Create Capacity

During loss of the normal capacity-authority path, no new aggregate capacity may be committed. Only exclusive pre-committed protective lease capacity may be consumed.

### INV-011 — Trapped Exposure Is Non-Reducible

Known trapped or illiquid exposure SHALL remain fully capacity-consuming and shall not be discounted based on a planned exit that cannot be executed or has not been confirmed.

### INV-012 — Reconciliation Cannot Optimistically Free Capacity

Reconciliation may provide evidence for a defined transition. It SHALL NOT overwrite the Ledger with an optimistic broker snapshot or free capacity merely because one source does not report an order.

---

## 6. Risk Capacity Model

### 6.1 Capacity Is a Constraint Vector

Risk capacity is not represented as one scalar notional value.

A Capacity Vector SHALL include the dimensions required by the approved Safety Profile and Hard Safety Envelope. Depending on instrument and account, these may include:

- gross notional;
- net directional exposure;
- instrument concentration;
- issuer, sector, theme, and correlated concentration;
- leverage;
- margin utilization;
- collateral utilization;
- liquidity-adjusted exposure;
- gap and overnight risk;
- basis and hedge mismatch;
- option delta, gamma, vega, and assignment risk;
- settlement and currency risk;
- daily loss or drawdown budget;
- broker order/request budget;
- protective reserve requirements.

Every dimension SHALL have:

- unit;
- sign convention;
- aggregation scope;
- limit source;
- conservative valuation rule;
- uncertainty treatment;
- evidence freshness requirement.

### 6.2 Risk Scopes

Capacity SHALL be enforceable across every applicable scope, including:

- account;
- legal portfolio;
- strategy group;
- instrument;
- underlying;
- issuer;
- sector or theme;
- currency;
- venue;
- global TOS aggregate.

A reservation is accepted only if every applicable scope remains within its Effective Limit.

### 6.3 Conservative Incremental Effect

For each proposed action, the Aggregate Risk Authority computes an **Adverse Increment Vector**:

```text
AdverseIncrement[c]
    = maximum credible increase in usage[c]
      over all approved execution paths
```

The value is never made negative merely because the intended final action is risk reducing.

A protective action may have a lower final aggregate risk while still requiring positive temporary capacity for margin, basis, overlap, or partial-fill states.

### 6.4 Position and Order Transfer

Capacity reserved for an order SHALL be transferred rather than duplicated when a fill is confirmed.

Conceptually:

```text
OpenOrderReservation
    --confirmed fill-->
ConfirmedPositionUsage
```

For a partial fill:

```text
Filled portion       -> ConfirmedPositionUsage
Potential remainder  -> PotentiallyLiveUsage
```

The transition SHALL be atomic with respect to capacity accounting.

### 6.5 Risk-Reducing Actions

A risk-reducing action may require little or no incremental directional capacity when broker and position semantics guarantee that it cannot reverse or increase exposure.

However, the reservation SHALL include every credible adverse dimension, including:

- over-exit or reversal risk;
- margin increase;
- order overlap;
- hedge basis risk;
- partial-fill mismatch;
- loss of existing protection;
- execution-rate resource use.

Broker-enforced reduce-only semantics may reduce the required vector only when the Broker Capability Profile proves the enforcement scope and behavior.

---

## 7. Authority and Responsibility

### 7.1 Aggregate Risk Authority

The Aggregate Risk Authority:

- computes and approves the requested Adverse Increment Vector;
- references a specific evidence snapshot and Safety Profile version;
- issues a capacity grant decision;
- does not directly mutate the Ledger;
- does not transmit orders;
- does not release capacity.

### 7.2 Risk Capacity Ledger

The Risk Capacity Ledger:

- is the sole serialization point;
- performs the final atomic constraint check;
- commits the reservation or rejects it;
- owns reservation state transitions;
- enforces current writer epoch;
- records durable history;
- rejects duplicate and stale commands;
- does not make strategy decisions;
- does not call the broker.

### 7.3 Intent Registry

The Intent Registry:

- provides immutable Intent identity;
- records proposal, approval, and scope;
- links every attempt to one Intent;
- prevents attempt creation for unknown or invalid Intent;
- does not allocate capacity.

### 7.4 Execution Coordinator

The Execution Coordinator:

- requests attempt binding;
- obtains a Transmission Capability;
- coordinates cancellation, replacement, and query operations;
- never directly modifies capacity;
- never treats timeout as proof of rejection;
- never performs blind resubmission after UNKNOWN send outcome.

### 7.5 Broker Adapter / Egress Gateway

The Broker Adapter:

- is the final transmission enforcement point;
- validates the Transmission Capability and current epochs;
- atomically consumes the one-time capability before beginning the network send boundary;
- records `SEND_STARTED` durably before or as part of capability consumption;
- exposes no ungated live-order method;
- reports transport and broker evidence without interpreting missing acknowledgement as rejection.

### 7.6 Reconciliation Service

The Reconciliation Service:

- collects and evaluates evidence;
- provides per-field confidence and bounds;
- requests defined Ledger transitions;
- cannot directly free capacity outside the transition rules;
- creates or requests quarantine for external, unknown, or conflicting state.

### 7.7 Protective Action Controller

The Protective Action Controller:

- classifies protective actions independently from strategy;
- consumes only a valid pre-committed protective lease;
- serializes sub-reservations through the approved protective sub-ledger mechanism;
- cannot enlarge or replenish the lease during partition;
- cannot reuse consumed capacity.

---

## 8. Authoritative Ledger Semantics

### 8.1 Linearizability

All operations that can change available aggregate headroom SHALL be linearizable.

At minimum, the following operations require strong serialization:

- create reservation;
- resize reservation;
- bind attempt;
- mark send started;
- transfer fill consumption;
- quarantine uncertainty;
- release capacity;
- create protective pool;
- issue or reassign protective lease;
- consume protective lease;
- create external or trapped-exposure allocation.

Asynchronous events, Kafka topics, caches, and read replicas MAY distribute state but SHALL NOT be the authority for these mutations.

### 8.2 Single Logical Writer

The implementation SHALL expose exactly one logical commitment writer for a Ledger scope.

The writer may be replicated for availability only if:

- a consensus or equivalent strong mechanism establishes one current epoch;
- every mutation is checked against that epoch by the authoritative store;
- a stale process cannot successfully mutate after failover;
- broker egress cannot accept a capability issued by a stale writer.

### 8.3 Fencing Epoch

Each writer generation receives a monotonically increasing `ledger_epoch`.

Every state-changing command SHALL carry:

- command identity;
- expected reservation revision where applicable;
- ledger epoch;
- authority identity;
- causation identity;
- evidence identity where applicable.

The authoritative transition function SHALL reject stale epoch or stale revision.

### 8.4 Compare-and-Set

Commitment uses an atomic compare-and-set or equivalent transaction over:

- current aggregate usage;
- existing commitments;
- applicable risk-scope limits;
- requested reservation vector;
- protective pool allocations;
- ledger revision;
- current epoch.

A stale approval cannot be committed against a changed Ledger state.

When the Ledger state has changed after Aggregate Risk Authority evaluation, the request is rejected or reevaluated. It is not silently committed using the old projection.

### 8.5 Command Idempotency

Ledger commands SHALL be idempotent by command identity.

Command idempotency prevents duplicate internal state transitions. It SHALL NOT be confused with broker-order idempotency.

---

## 9. Reservation Identity and Record

Every reservation SHALL have an immutable globally unique `reservation_id` within the TOS authority domain.

A reservation record SHALL include at least:

- reservation identity;
- parent Intent identity;
- account and portfolio scope;
- instrument and underlying scope;
- action class;
- normal or protective pool identity;
- approved quantity upper bound;
- Adverse Increment Vector;
- applicable risk scopes;
- Aggregate Risk Authority grant identity;
- evidence snapshot identity;
- Hard Safety Envelope version;
- Runtime Safety Profile version;
- ledger epoch and creation revision;
- current reservation revision;
- current capacity state;
- bound attempt identities;
- filled quantity lower and upper bounds;
- remaining executable quantity upper bound;
- protective ownership where applicable;
- timestamps from the Trustworthy Time model;
- audit causation and actor identities.

A reservation identity SHALL never be reused after terminal release.

---

## 10. Capacity State Model

The capacity state is independent from Intent, transmission, broker-order, and knowledge states.

### 10.1 States

#### `COMMITTED_UNBOUND`

Capacity is exclusively committed to an Intent but no transmission attempt is bound.

It may expire and release only if the Ledger proves no attempt or Transmission Capability was created or consumed.

#### `ATTEMPT_BOUND`

Capacity is bound to a unique attempt and an unconsumed Transmission Capability.

Release requires proof that the capability was never consumed and no send boundary began.

#### `POTENTIALLY_LIVE`

The attempt may have reached the broker, or broker receipt cannot be disproven.

Full conservative remaining quantity consumes capacity.

#### `PARTIALLY_CONSUMED`

A confirmed partial fill has transferred part of the reservation to confirmed-position usage while the remaining quantity may still execute.

#### `POSITION_CONSUMED`

The economic effect is confirmed in position state. Capacity remains consumed by the position rather than the open order.

This state may be represented as a linked position allocation rather than the original reservation record, but the transfer must be auditable and atomic.

#### `RELEASE_PENDING_PROOF`

A terminal broker outcome is claimed, but Final Quantity Proof is incomplete.

Capacity remains consumed.

#### `QUARANTINED_UNKNOWN`

Evidence is missing, conflicting, unattributed, or unable to bound the economic effect precisely.

The conservative upper bound remains consumed. New risk is blocked according to the containment policy.

#### `TRAPPED_CONSUMED`

Exposure is confirmed or conservatively inferred and cannot currently be reduced.

No planned exit or pending protective action reduces this consumption until confirmed.

#### `RELEASED`

All release conditions are satisfied. The capacity is available for future commitment.

`RELEASED` is terminal for the reservation identity.

### 10.2 State Transition Principle

Every transition SHALL be caused by one of:

- a strongly authorized internal command;
- broker evidence evaluated under the approved Broker Capability Profile;
- reconciliation evidence meeting a defined proof rule;
- a recognized external or non-trade state change;
- a containment action that increases conservatism.

No transition to a less conservative state may be made solely from timeout, absence, or operator assumption.

---

## 11. Normal Commitment Flow

### 11.1 Proposal and Approval

1. Decision Service creates an immutable Intent proposal.
2. Independent Approval Service approves or denies it.
3. Aggregate Risk Authority evaluates the proposed action against conservative current state.
4. Aggregate Risk Authority issues a grant request containing the Adverse Increment Vector and evidence version.

### 11.2 Atomic Commitment

5. Risk Capacity Ledger verifies current epoch, limits, revisions, and scope.
6. Ledger atomically commits a unique reservation in `COMMITTED_UNBOUND` or rejects the request.
7. The reservation is immediately unavailable to all competing actions.

### 11.3 Attempt Binding

8. Execution Coordinator creates a unique attempt request.
9. Ledger verifies the reservation is eligible and atomically binds the attempt.
10. Ledger transitions to `ATTEMPT_BOUND` and issues or authorizes issuance of one single-use Transmission Capability.

### 11.4 Send Boundary

11. Broker Adapter verifies all capability bindings.
12. Broker Adapter atomically consumes the capability and durably records `SEND_STARTED` before the external call can be retried as a new send.
13. Reservation transitions to `POTENTIALLY_LIVE`.
14. Broker Adapter performs the network call.
15. Response, acknowledgement, error, or timeout is recorded as evidence.

The local write and broker call cannot be globally atomic. Therefore a crash after `SEND_STARTED` but before actual broker receipt is intentionally treated as potentially live. This creates conservative capacity retention rather than duplicate economic effect.

---

## 12. Transmission Capability

A Transmission Capability SHALL be:

- single use;
- non-transferable;
- bound to one reservation and one attempt;
- bound to account, instrument, side/action, and maximum quantity;
- bound to the current ledger epoch;
- bound to current live authorization or valid protective lease;
- bound to Hard Safety Envelope and Runtime Safety Profile versions;
- rejected after consumption;
- rejected if the request differs in economic effect.

Broker Adapter validation SHALL compare the actual broker request against the capability, not merely trust upstream metadata.

A capability that has expired before consumption may be discarded if no send began.

A consumed capability never causes capacity release merely because its authorization lifetime ended.

---

## 13. Retry and Duplicate Prevention

### 13.1 Internal Command Retry

Retries of Ledger commands use the same command identity and are idempotent.

### 13.2 Broker Network Retry with Proven Idempotency

If the Broker Capability Profile proves a client order identity and deterministic duplicate rejection or exact replay semantics, a transport retry MAY use the same broker-side identity and reservation under the approved rules.

The proof must define:

- deduplication scope;
- deduplication lifetime;
- account and session behavior;
- response to duplicate submission;
- query and recovery semantics.

### 13.3 Broker Retry Without Proven Idempotency

When send outcome is UNKNOWN and broker idempotency is not proven:

- no new broker submission is permitted for the same intended economic effect;
- the full attempt remains `POTENTIALLY_LIVE` or `QUARANTINED_UNKNOWN`;
- query and reconciliation are required;
- failure to attribute the order causes containment;
- a later replacement or offsetting action is a new economic action requiring independent capacity and protective proof.

### 13.4 New Attempt After Proven Rejection

A new attempt may be created only when authoritative evidence proves the prior attempt was not accepted and cannot fill.

The new attempt receives a new attempt identity. It may reuse the existing reservation only if the reservation vector still covers the full new attempt and no quantity from the prior attempt remains potentially live.

---

## 14. Acknowledgement Loss and Unknown Send

### 14.1 Missing Acknowledgement

Missing acknowledgement does not mean rejection.

The attempt remains potentially live at its full conservative quantity until evidence reduces the upper bound.

### 14.2 Query Strategy

The system queries all broker evidence available under the Broker Capability Profile, which may include:

- order history;
- open orders;
- fills/trades;
- position changes;
- cash and margin changes;
- account event streams;
- broker statements or drop-copy evidence.

Absence from one query is not proof of non-existence.

### 14.3 Unattributable Broker Activity

A broker order or fill that may correspond to the attempt but cannot be deterministically attributed creates `QUARANTINED_UNKNOWN` state and blocks new risk.

The capacity model uses the worst credible combination without double-counting impossible states where sufficient evidence exists.

---

## 15. Partial and Asynchronous Fills

### 15.1 Confirmed Fill

On confirmed fill quantity `q`:

- position usage is recalculated using `q`;
- corresponding order-reservation usage is reduced by no more than the amount proven filled;
- remaining executable quantity retains capacity;
- the transfer is atomic in the Ledger;
- protective effectiveness is recalculated from confirmed quantity.

### 15.2 Out-of-Order Events

Fill may arrive before acknowledgement, after cancel request, after cancel acknowledgement, or after local timeout.

The Ledger SHALL accept valid late evidence and update capacity conservatively.

A state label such as `CANCELLED` SHALL NOT cause a valid later fill to be discarded.

### 15.3 Duplicate Fill Events

Fill processing SHALL be idempotent by broker execution identity or a broker-specific deterministic composite identity.

Where the broker cannot provide a unique execution identity, the Broker Capability Profile SHALL define the safe deduplication and ambiguity treatment.

### 15.4 Exit and Position Reversal

Exit retries SHALL be based on the desired target position and the conservative combination of:

- confirmed current position;
- already filled exit quantity;
- Potentially-Live exit quantity;
- external activity;
- broker reduce-only guarantees.

A full-size resubmission after partial fill is prohibited unless the model proves it cannot reverse the position and independent capacity covers any remaining risk.

---

## 16. Cancellation

### 16.1 Cancel Request

A cancel request changes broker-order intent but does not reduce capacity.

Remaining quantity stays potentially live.

### 16.2 Cancel Acknowledgement

Cancel acknowledgement moves the reservation to `RELEASE_PENDING_PROOF` unless the broker capability profile proves it includes Final Quantity Proof.

### 16.3 Final Quantity Proof

Release requires:

- final cumulative filled quantity;
- zero remaining executable quantity;
- broker event-ordering or reconciliation evidence sufficient to exclude crossing fill under the approved capability model.

### 16.4 Late Fill After Claimed Final State

If a fill arrives after capacity was released under an approved proof rule:

- the event is treated as a safety-control breach or broker-capability violation;
- emergency external/quarantine capacity is created immediately;
- new risk is blocked;
- the Broker Capability Profile and production approval are invalidated pending review;
- the ledger history remains immutable and the release is not silently rewritten.

---

## 17. Replace and Amend

### 17.1 Atomic Broker Replace

Capacity optimization based on atomic replace is permitted only when the Broker Capability Profile proves that the old and new order cannot both execute outside the documented semantics.

### 17.2 Non-Atomic Replace

For cancel-then-new or ambiguous replace:

```text
Required capacity
    >=
worst credible combined economic effect
of old potentially-live quantity
and new attempt quantity
```

The new attempt may not transmit until this overlap capacity is committed.

### 17.3 Protective Replacement

If replacement removes existing protection before new protection is confirmed:

- the position is treated as unprotected during the gap;
- aggregate capacity includes the increased unprotected risk;
- protective action rules from ADR-002-001 apply;
- failure to establish new protection triggers containment.

---

## 18. Capacity Release Rules

### 18.1 Pre-Transmission Release

`COMMITTED_UNBOUND` capacity may be released when:

- the Intent is withdrawn or denied;
- no attempt was ever bound;
- no protective lease consumption exists;
- the Ledger transition is current and authorized.

### 18.2 Bound but Unused Capability

`ATTEMPT_BOUND` capacity may be released only when the Broker Adapter and Ledger prove:

- the Transmission Capability was never consumed;
- `SEND_STARTED` was never recorded;
- no alternate egress path exists;
- the attempt cannot reach the broker.

### 18.3 Proven Rejection

Capacity may be released or reused after broker rejection only when the evidence proves:

- the order was not accepted;
- no partial fill occurred;
- no remaining executable quantity exists.

### 18.4 Cancellation or Expiry

Cancellation or broker expiry requires Final Quantity Proof.

### 18.5 Full Fill

After full fill:

- open-order reservation is transferred to confirmed-position usage;
- any excess adverse-increment reserve may be released only after the new position and margin state are reconciled;
- release does not imply the resulting position is risk free.

### 18.6 UNKNOWN

No automatic release is permitted.

An operator cannot free UNKNOWN capacity by assertion. The operator may halt, reduce scope, request investigation, or accept continued quarantine, but release still requires the defined proof or a separately governed exceptional safety decision that cannot enlarge live authority.

### 18.7 Reservation TTL

TTL applies only to unused pre-transmission authority.

TTL SHALL NOT release potentially-live, partially consumed, position-consumed, trapped, or UNKNOWN capacity.

---

## 19. Reserved Protective Capacity

### 19.1 Parent Protective Pool

The Risk Capacity Ledger creates a `PROTECTIVE_POOL` commitment through the same linearizable process as normal reservations.

The pool:

- is removed from normal available headroom;
- is represented as a Capacity Vector;
- may be scoped by account, instrument class, or risk domain;
- cannot be borrowed by normal strategy;
- remains visible in aggregate accounting.

### 19.2 Protective Lease

A portion of the parent pool may be delegated as an exclusive Protective Lease.

The lease SHALL contain:

- lease identity;
- parent pool identity;
- capacity vector;
- allowed account/instrument/action scope;
- maximum quantity;
- current owner identity;
- lease owner epoch;
- monotonic authorization lifetime;
- Safety Authority epoch binding;
- Hard Safety Envelope and Runtime Safety Profile versions.

### 19.3 Protective Sub-Ledger

Partition-time consumption SHALL use a durable, exclusive sub-ledger or equivalent single-writer state machine bound to the lease.

The sub-ledger SHALL:

- atomically create sub-reservations;
- reject duplicate command identity;
- reject stale owner epoch;
- prevent total consumption above the lease vector;
- durably mark send boundaries;
- preserve potentially-live consumption across restart where evidence remains available;
- fail closed when local continuity or ownership cannot be proven.

### 19.4 No Reassignment on Authorization Expiry Alone

When a Protective Lease authorization expires, it becomes invalid for new transmissions.

Its parent capacity SHALL NOT be reassigned merely because the authorization expired. Reassignment requires reconciliation proving no potentially-live consumption remains.

This prevents the same protective capacity from being active in two partitions or owner generations.

### 19.5 Partition Behavior

During partition:

- no new parent pool is created;
- no lease is enlarged;
- no consumed capacity is recycled without Final Quantity Proof;
- expired or unverifiable lease stops new sends;
- existing attempts remain capacity-consuming;
- normal risk-increasing activity remains blocked.

### 19.6 Rejoin

After connectivity returns:

1. central Ledger freezes lease reassignment;
2. protective sub-ledger evidence is imported and verified;
3. broker-side orders, fills, and positions are reconciled;
4. consumption is transferred to central capacity state;
5. UNKNOWN remains quarantined;
6. only then may unused parent capacity be released or re-leased.

---

## 20. Split-Brain Prevention

### 20.1 Commitment Writer Split Brain

The Ledger implementation SHALL combine:

- single logical writer;
- monotonic epoch;
- authoritative-store fencing;
- state revision compare-and-set;
- egress validation of current capacity authority.

Leader election without store and egress fencing is insufficient.

### 20.2 Stale Writer Behavior

A stale writer may continue running but all its state-changing commands SHALL be rejected by the authoritative transition boundary.

It SHALL be unable to issue a usable Transmission Capability.

### 20.3 Existing Reservations Across Failover

Committed reservations survive writer failover.

The new writer may validate and continue them, but new Transmission Capabilities must be issued or validated under the current epoch.

Potentially-live attempts remain active regardless of writer failover.

### 20.4 Protective Owner Split Brain

A protective lease has one owner epoch.

The same lease capacity SHALL NOT be assigned to a new owner until the old lease has been reconciled and all potentially-live consumption is accounted for.

### 20.5 Loss of Current Epoch Knowledge

If the execution path cannot prove that a capacity or Safety Authority epoch is current:

- normal transmission fails closed;
- only a valid pre-issued degraded protective lease may be used;
- if the protective lease is also unverifiable, no new transmission is allowed.

---

## 21. Crash and Restart Recovery

### 21.1 Crash Before Attempt Binding

A `COMMITTED_UNBOUND` reservation remains committed.

It may later be rebound or safely released under the pre-transmission rule.

### 21.2 Crash After Attempt Binding but Before Capability Consumption

The reservation remains `ATTEMPT_BOUND`.

Recovery verifies whether the capability was consumed. If not provable, the state becomes conservative rather than automatically released.

### 21.3 Crash After `SEND_STARTED`

The full remaining quantity is potentially live.

Recovery SHALL NOT resend blindly.

### 21.4 Crash After Broker Send but Before Local Response Record

Same as UNKNOWN send: full conservative capacity remains.

### 21.5 Crash After Fill but Before Ledger Transfer

Broker fill evidence is replayed idempotently. Until transfer completes, the reservation remains conservative enough to cover the effect.

### 21.6 Startup Barrier

No new normal risk may be committed after restart until the Recovery Coordinator verifies:

- Ledger integrity and current epoch;
- all non-terminal reservations;
- all consumed Transmission Capabilities;
- open and historical broker orders;
- cumulative fills;
- positions;
- cash and margin;
- protective sub-ledgers and leases;
- external/unattributed activity;
- trapped exposure;
- recognized non-trade changes;
- trustworthy time and valid Safety Profile.

### 21.7 Recovery Does Not Rebuild by Overwrite

The system SHALL NOT replace internal state wholesale with one broker position snapshot.

Recovery evaluates evidence consistency and applies explicit, auditable transitions or quarantine.

---

## 22. Reconciliation Integration

### 22.1 Evidence Model

Reconciliation provides separate confidence and bounds for:

- broker-order existence;
- broker-order identity;
- cumulative fill quantity;
- remaining executable quantity;
- position quantity;
- cash and margin;
- protective coverage;
- instrument identity.

### 22.2 Conservative Bound Use

The Ledger uses:

- upper bounds for potential adverse exposure;
- lower bounds only where they cannot understate risk;
- no optimistic midpoint or blended confidence score for release.

### 22.3 Evidence Conflict

Unresolved evidence conflict transitions the affected allocation to `QUARANTINED_UNKNOWN` or retains a more conservative existing state.

### 22.4 Negative Evidence

Order absence from one query, page, session, or event stream is not proof of non-existence.

The Broker Capability Profile defines what combination of evidence, ordering, and delay can establish Final Quantity Proof.

---

## 23. External and Unattributed Activity

### 23.1 Detection

When Reconciliation detects an order, fill, position, balance, or margin change not attributable to a known Intent or approved non-trade event, it requests an `EXTERNAL_QUARANTINE` allocation.

### 23.2 Capacity Treatment

External exposure consumes conservative aggregate capacity immediately.

If observed exposure exceeds available headroom, the Ledger records the breach rather than hiding it. The system blocks new risk and permits only approved containment or protective action.

### 23.3 Attribution

Later attribution may transfer the quarantine to an existing reservation or authorized operator Intent, but the transfer must be atomic and auditable.

### 23.4 Detection Window

The approved external-activity detection bound SHALL be reflected in maximum normal action size and retained headroom.

The system must remain within the Hard Safety Envelope under the approved maximum credible external change during that window, or live scope must be reduced.

---

## 24. Trapped and Illiquid Exposure

### 24.1 Capacity Treatment

Trapped exposure is represented as `TRAPPED_CONSUMED` and treated as non-reducible.

It reduces all relevant remaining headroom.

### 24.2 Planned Exit

A submitted, working, or intended exit does not reduce trapped consumption unless confirmed fills reduce the position.

### 24.3 Failed Protective Action

A protective action that cannot execute does not receive risk-reduction credit.

Its own potentially-live quantity remains accounted for where applicable.

### 24.4 Release

Trapped capacity transfers or releases only when authoritative evidence confirms the exposure has changed, matured, settled, been assigned, or otherwise ceased to exist.

---

## 25. Corporate Actions and Non-Trade Changes

### 25.1 First-Class Input

Corporate and administrative events are distinct from fills.

Examples include:

- split or reverse split;
- stock dividend;
- merger or spin-off;
- symbol or instrument identifier change;
- expiry, exercise, assignment, or settlement;
- account transfer;
- broker correction;
- delisting or venue suspension.

### 25.2 Capacity Remapping

Recognized events SHALL remap position usage, quantity, instrument identity, and applicable limits atomically where possible.

### 25.3 Unknown Mapping

When identity or valuation cannot be established, the affected exposure becomes `QUARANTINED_UNKNOWN` or `TRAPPED_CONSUMED`, and new risk remains blocked for the affected scope.

Detailed event modeling is delegated to ADR-002-010 — Corporate Actions and Non-Trade State Changes.

---

## 26. Availability and Failure Behavior

### 26.1 Ledger Unavailable

If the authoritative Risk Capacity Ledger cannot be reached or current epoch cannot be verified:

- no new normal reservation may be committed;
- no unbound normal reservation may be newly transmitted unless a current egress validation path exists and architecture explicitly proves safety;
- existing potentially-live attempts remain capacity-consuming;
- pre-committed degraded protective leases may operate only within ADR-002-001 rules;
- otherwise the system enters containment.

### 26.2 Event Infrastructure Unavailable

Kafka, Redis, or equivalent event-distribution failure SHALL NOT create new capacity or bypass the Ledger.

The system may lose availability but not exclusivity.

### 26.3 Read Replica Stale

Stale read models may be used for display but not for final commitment or release decisions.

### 26.4 Evidence Store Unavailable

If required evidence cannot be durably recorded, the system fails closed for new risk and retains conservative commitments.

---

## 27. Conceptual Ledger Commands

The implementation may choose different interfaces, but it SHALL provide equivalent semantics for:

```text
CommitReservation
ResizeReservation
BindAttempt
ConsumeTransmissionCapability
MarkSendStarted
RecordBrokerAcknowledgement
RecordBrokerRejection
RecordFill
RequestCancel
RecordFinalQuantityProof
TransferOrderToPositionUsage
QuarantineUnknown
CreateExternalQuarantine
MarkTrappedExposure
CommitProtectivePool
IssueProtectiveLease
ConsumeProtectiveLease
ReconcileProtectiveLease
ReleaseReservation
```

Every command SHALL include:

- command identity;
- actor and authority identity;
- current epoch;
- expected revision where applicable;
- causation identity;
- evidence identity where applicable;
- requested state transition.

Commands that reduce conservatism require stronger proof than commands that increase conservatism.

---

## 28. Evidence and Audit

The Ledger SHALL produce an immutable or tamper-evident transition record containing:

- previous state and revision;
- new state and revision;
- capacity vectors before and after;
- limits and versions used;
- authority epoch;
- command and actor identity;
- causation and correlation identities;
- evidence references;
- rejection reason where applicable;
- trustworthy-time evidence.

Audit and replay support investigation and verification. They do not substitute for atomic commitment or egress enforcement.

---

## 29. Security and Identity

### 29.1 Least Privilege

- strategy identities may propose only;
- Aggregate Risk Authority may issue grant decisions only;
- Ledger writer identity may mutate capacity but may not call broker egress;
- Broker Adapter may transmit only with a valid capability;
- Reconciliation may submit evidence and transition requests but may not arbitrarily release;
- operator identities are separated by function;
- research, test, simulation, and paper identities cannot access live Ledger mutation or broker egress.

### 29.2 No Shared General-Purpose Credential

Live broker credentials SHALL NOT be available to strategy, research, backtest, or general operator components.

### 29.3 Separation of Duties

The same identity SHALL NOT both:

- enlarge limits and arm live trading;
- approve a strategy proposal and transmit it;
- administer the Hard Safety Envelope and operate normal trading;
- reconcile UNKNOWN state and unilaterally release its capacity without the proof rule.

---

## 30. Alternatives Considered

### 30.1 Asynchronous Event-Based Reservation

**Rejected.**

Two consumers may evaluate the same headroom before events converge. Eventual consistency cannot guarantee exclusive aggregate commitment.

### 30.2 Aggregate Risk Authority Mutates Capacity Directly and Ledger Records Later

**Rejected.**

This creates dual-write failure and makes the Ledger an audit log rather than the safety serialization point.

### 30.3 Database Row Lock Without Fencing Epoch

**Rejected as insufficient.**

A stale process or failover scenario may continue acting outside the intended leadership lifecycle. Store-level and egress-level fencing are required.

### 30.4 Reservation TTL Releases Capacity

**Rejected after send boundary.**

Local time expiry does not eliminate broker-side economic effect.

### 30.5 Broker Position Query as Absolute Truth

**Rejected.**

Broker responses may be delayed, incomplete, inconsistent, or wrong. Evidence consistency and bounds are required.

### 30.6 Blind Retry on Timeout

**Rejected.**

Timeout does not prove the original order was not accepted.

### 30.7 Scalar Notional Budget

**Rejected.**

Notional alone cannot represent margin, concentration, liquidity, basis, option, or protective-resource risk.

### 30.8 Protective Controller Creates Capacity During Partition

**Rejected.**

It would violate exclusive aggregate authority exactly when global state is least trustworthy.

### 30.9 Manual Operator Release of UNKNOWN Capacity

**Rejected.**

Human assertion cannot prove absence of economic effect.

---

## 31. Consequences

### 31.1 Positive Consequences

- prevents concurrent double-spending of aggregate headroom;
- provides an enforceable owner for commitment and release;
- fences stale instances;
- binds broker transmission to committed capacity;
- preserves safety across acknowledgement loss and crash;
- correctly accounts for partial fills and late fills;
- prevents cancel acknowledgement from freeing capacity prematurely;
- makes UNKNOWN and external activity conservative;
- keeps trapped exposure from being treated as available headroom;
- allows bounded protective operation without creating capacity during partition;
- creates deterministic evidence for verification and incident analysis.

### 31.2 Negative Consequences

- strong consistency reduces availability and throughput;
- capacity may remain quarantined for long periods when broker evidence is weak;
- some valid trading opportunities will be rejected;
- implementation and testing complexity increase;
- broker integrations without strong identity/query semantics may support only narrow live scope;
- failover does not immediately restore all transmission authority;
- protective reserve reduces capital efficiency during normal operation.

These consequences are accepted because availability and opportunity are subordinate to survivability and capital preservation.

---

## 32. Failure Modes and Required Responses

| Failure | Required capacity response |
|---|---|
| Two committers active | One current epoch succeeds; stale writer rejected and unable to transmit |
| Crash before attempt | Reservation remains committed or safely releases with proof |
| Crash after attempt bind | Capacity retained until unused capability is proven |
| Crash after send start | Full remaining quantity potentially live |
| ACK lost | No blind retry; capacity retained; reconcile |
| Partial fill | Atomic transfer to position plus remaining open-order reservation |
| Cancel pending | No release |
| Cancel ACK with possible crossing fill | Release pending proof |
| Late fill | Apply idempotently; capacity/position updated |
| Replace non-atomic | Reserve worst credible overlap or unprotected gap risk |
| Broker query omits order | Absence not treated as proof |
| External HTS order | Create external quarantine; block new risk |
| Corporate action | Remap or quarantine before re-arm |
| Trapped exposure | Remains non-reducible capacity usage |
| Ledger unavailable | No new normal commitment; protective lease only if valid |
| Protective lease split brain | Stale owner rejected; parent not reassigned before reconciliation |
| Time validity unknown | No new authority consumption |

---

## 33. Verification and Acceptance Criteria

ADR-002-002 SHALL remain Proposed until the following are demonstrated with deterministic tests, fault injection, or formal/state-machine analysis as appropriate.

### AC-001 — Concurrent Commitment

Given two requests that individually fit but jointly exceed one limit, exactly one is committed and the other is rejected or reevaluated.

**Forbidden outcome:** both reservations active against the same headroom.

### AC-002 — Duplicate Active Writer

Start two writer instances with different epochs and force network partition or pause/resume.

**Pass:** only the current epoch can mutate, issue usable capability, or authorize egress.

### AC-003 — Crash Before Send

Crash at every boundary from commitment through capability consumption.

**Pass:** no duplicate send occurs; capacity is either provably releasable or conservatively retained.

### AC-004 — Crash After Send

Crash after network send and before acknowledgement persistence.

**Pass:** full remaining quantity is potentially live; no blind retry occurs.

### AC-005 — Acknowledgement Loss

Broker accepts order but response is lost.

**Pass:** capacity remains; reconciliation finds or quarantines the effect; duplicate submission is prevented.

### AC-006 — Partial Fill

Generate multiple fill fractions and out-of-order events.

**Pass:** filled quantity transfers to position usage exactly once; remaining quantity retains capacity; aggregate invariant is never violated.

### AC-007 — Cancel Crossing Fill

Issue cancel while a fill is in flight and deliver events in every relevant order.

**Pass:** cancel acknowledgement does not release capacity before final quantity proof; late fill updates position.

### AC-008 — Replace Overlap

Test old order fill before, during, and after non-atomic replacement.

**Pass:** worst credible overlap is committed; no unreserved economic effect is possible.

### AC-009 — Reservation TTL

Expire a reservation before and after `SEND_STARTED`.

**Pass:** unused pre-send reservation may release; potentially-live reservation never releases from TTL alone.

### AC-010 — External Activity

Create HTS/manual order and fill without TOS Intent.

**Pass:** external quarantine is created within the approved detection bound; new risk is blocked.

### AC-011 — Broker Query Omission

Hide an order from one query source while it remains visible in another or later appears.

**Pass:** capacity is not released from absence alone.

### AC-012 — Protective Lease Partition

Partition the central Ledger, consume part of a pre-issued lease, restart or fail over the local owner, and attempt duplicate consumption.

**Pass:** total lease vector is never exceeded; stale owner cannot send; parent capacity is not reassigned before reconciliation.

### AC-013 — Protective Lease Expiry

Expire lease authorization with an unresolved potentially-live attempt.

**Pass:** no new send occurs; consumed parent capacity remains quarantined.

### AC-014 — Trapped Exposure

Mark an exposure illiquid or venue-blocked while an exit Intent exists.

**Pass:** the exposure remains fully capacity-consuming until confirmed reduction.

### AC-015 — Corporate Action

Apply quantity and instrument-identity changes without fills.

**Pass:** capacity remaps or quarantines; normal live authority is not restored on unresolved identity.

### AC-016 — Hard Envelope

Attempt commitment with a Runtime Safety Profile above the Hard Safety Envelope.

**Pass:** commitment is rejected regardless of otherwise valid approval.

### AC-017 — Recovery Barrier

Restart with open orders, partial fills, UNKNOWN attempts, external activity, and stale epoch.

**Pass:** no new normal risk is allowed until reconciliation and current authority are established.

### AC-018 — Audit Replay

Replay the immutable command/evidence stream.

**Pass:** the same capacity transitions and terminal state are reproduced or any nondeterministic external dependency is explicitly identified and conservatively handled.

---

## 34. Required Metrics and Alerts

The implementation SHALL expose at least:

- available capacity by risk dimension and scope;
- committed normal capacity;
- committed protective pool capacity;
- leased and consumed protective capacity;
- potentially-live quantity;
- UNKNOWN/quarantined capacity;
- trapped capacity;
- external/unattributed capacity;
- reservations by state and age;
- writer epoch and stale-command rejection count;
- capability issuance and duplicate-consumption rejection count;
- release-pending-proof age;
- cancel-to-final-proof latency;
- external-activity detection latency;
- broker query conflict count;
- capacity invariant violations;
- protective reserve sufficiency.

Any aggregate invariant violation is a Critical incident and immediate new-risk halt condition.

---

## 35. Implementation Constraints

An implementation conforms only if it demonstrates all of the following:

- linearizable mutation for capacity-affecting transitions;
- single logical writer with monotonic fencing;
- authoritative-store rejection of stale epoch;
- final egress capability validation;
- durable write-ahead send boundary;
- idempotent internal command processing;
- conservative UNKNOWN handling;
- proof-gated release;
- durable protective sub-reservation where degraded operation is supported;
- startup reconciliation barrier;
- immutable or tamper-evident transition evidence.

A design based solely on in-memory locks, eventually consistent events, Redis leases without proven fencing, asynchronous audit logs, or broker acknowledgement status is non-conforming.

This ADR does not prohibit any specific technology. The chosen technology must demonstrate the required semantics under failure.

---

## 36. Dependencies and Follow-Up ADRs

This ADR depends on or creates mandatory interfaces with:

1. **ADR-002-001 — Degraded-Mode Protective Capacity v0.2**;
2. **ADR-002-003 — Safety Authority Validity, Epoch Fencing, and Partition Behavior**;
3. **ADR-002-004 — Broker Capability Requirements and Fallbacks**;
4. **ADR-002-005 — Intent, Transmission Attempt, Broker Order, and Knowledge State Model**;
5. **ADR-002-006 — Evidence and Reconciliation Confidence Model**;
6. **ADR-002-008 — Trustworthy Time Architecture**;
7. **ADR-002-007 — Live Authorization, Limit Governance, and Re-arm**;
8. **ADR-002-009 — Failure-Domain Isolation and Deployment Safety**;
9. **ADR-002-010 — Corporate Actions and Non-Trade State Changes**;
10. **ADR-002-011 — Protective Replacement and Protection-Gap Control**;
11. **ADR-002-012 — Risk Capacity Ledger Persistence, Consensus, and Writer Fencing**;
12. **ADR-002-013 — Egress Gateway Credential, Route, and Commit-Proof Security**;
13. **ADR-002-014 — Hard Safety Envelope and Runtime Safety Profile Governance**;
14. **ADR-002-015 — Human Safety Authority, Dual Control, and Break-Glass Governance**;
15. **VER-002-001 — Safety-Critical Architecture Verification Evidence Specification**.

This ADR owns capacity semantics. It does not duplicate the full authority election, broker protocol, or evidence-confidence decisions of those ADRs.

---

## 37. Open Implementation Questions

The following questions may remain open during Proposed status but must be resolved before Accepted status:

1. Which conforming product and deployment profile implement ADR-002-012's quorum-replicated deterministic Safety Commit Log?
2. What exact scope is assigned to one writer epoch: account, portfolio, or global TOS?
3. Which ADR-002-013 Quorum Commit Certificate and final-egress confinement expose current epoch without creating a new common-mode bypass?
4. How are position-usage updates and reservation transfers represented transactionally?
5. What conservative valuation function is used for each risk dimension?
6. How are multiple currencies and delayed FX evidence handled?
7. What local durable mechanism implements the protective sub-ledger?
8. Which broker capabilities permit idempotent network retry?
9. What evidence constitutes Final Quantity Proof for each broker/order type?
10. How long may capacity remain quarantined before mandatory operator escalation?
11. How are corporate-action remaps authorized and verified?
12. What failure-domain isolation is required for the Ledger and Broker Adapter?

An answer that weakens the invariants is not acceptable. When the required semantics cannot be implemented, live scope must be reduced.

---

## 38. Adoption Plan

### Phase 1 — Model and Simulation

- implement the capacity state machine without live transmission;
- run deterministic concurrency and fault simulations;
- verify invariants through property-based and model-based tests.

### Phase 2 — Paper and Shadow Ledger

- calculate reservations against paper or mirrored live evidence;
- compare predicted potentially-live and confirmed usage with broker outcomes;
- measure query gaps, late-fill behavior, and reconciliation latency.

### Phase 3 — Restricted Live Scope

- enable one account and narrowly bounded instruments;
- disable broker retry unless capability is proven;
- maintain oversized protective reserve;
- require operator-supervised re-arm;
- treat any unmodeled state as a production gate failure.

### Phase 4 — Expanded Scope

Expansion is permitted only after:

- acceptance criteria remain demonstrated under production-like fault injection;
- broker capabilities are approved;
- containment bounds are measured;
- no unresolved invariant violation exists;
- independent safety review approves the scope.

---

## 39. Approval Gate

ADR-002-002 may move from **Proposed** to **Accepted** only when:

- RFC-002 Authority Matrix is merged;
- ADR-002-003 is Accepted for the applicable authority domain;
- ADR-002-004 is Accepted and an approved broker-specific Capability Profile exists;
- Safety Profile Validator and Recovery Coordinator are defined;
- the Ledger technology and fencing mechanism are selected and demonstrated;
- the ADR-002-012 persistence, consensus, and writer-fencing mechanism is implemented for the applicable Capacity Domain and its required RCLP evidence passes;
- the ADR-002-013 final-egress boundary, exact claim binding, credential/route confinement, and hard fencing are implemented and their required EGRESS evidence passes;
- the ADR-002-014 canonical envelope/profile validation and committed-generation activation are implemented and their required SPG evidence passes;
- ADR-002-015 human approval and break-glass paths cannot mutate or release capacity and their required HAG evidence passes;
- protective pool and sub-ledger semantics are demonstrated;
- broker-specific Final Quantity Proof rules exist;
- all Critical acceptance criteria pass;
- required RC, SA, BC, and cross-system evidence in VER-002-001 is `PASS` and independently reviewed;
- recovery and split-brain tests produce evidence;
- residual risks are documented and approved;
- independent review confirms that no implementation shortcut permits uncommitted or duplicate economic effect.

Until then, this ADR authorizes implementation and verification work but does not authorize production live trading.
