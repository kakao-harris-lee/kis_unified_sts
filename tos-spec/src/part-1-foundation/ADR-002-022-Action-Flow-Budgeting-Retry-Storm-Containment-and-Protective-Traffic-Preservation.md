# ADR-002-022 — Action-Flow Budgeting, Retry-Storm Containment, and Protective-Traffic Preservation

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** bounded broker-directed action flow, distributed and hierarchical rate budgets, action amplification, retry/reconnect/replay containment, queue and in-flight limits, RCL-serialized Action Flow Permits, protective-flow reservation, broker shared-resource constraints, active final-egress currentness, degraded behavior, recovery, evidence, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-014 and SAFE-015; RFC-002 §§9.1, 10.7–10.8, 11, 13.6, 20–21, and 29; ADR-002-001 §§6, 9, 12–14; ADR-002-002 §§6–7, 11, and 15; ADR-002-004 §§8.10, 11–14, and 17
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-012, SAFE-013, SAFE-014, SAFE-015, SAFE-020, SAFE-021, SAFE-024, SAFE-025, SAFE-030, SAFE-031, SAFE-032, SAFE-033, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-042, SAFE-043, SAFE-044, SAFE-046, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-021

---

## 1. Decision

Every broker-directed order-generating, cancelling, amending, replacing, retrying, querying, reconnecting, session-mutating, or administrative action SHALL be admitted through one complete **Action Flow Policy**, one current **Action Flow State Snapshot**, and one exact **Action Flow Decision** before it can consume broker-facing resources. The decision SHALL bind the exact canonical broker command or exact non-order operation, originating cause and lineage, action class, all applicable shared scopes, maximum broker mutations, amplification path, queue and in-flight effect, resource-consumption vector, and result `GRANT`, `DENY`, or `UNKNOWN`.

The **Action Flow Governor** is a non-authorizing evaluator. It may grant or deny an exact action-flow allocation request, but it cannot mutate any budget, issue Live Authorization or a Transmission Capability, classify an action as protective, hold a live broker route, or transmit. A `GRANT` is not capacity or permission to send.

The Risk Capacity Ledger is the sole serialization and mutation authority for every governed action-flow capacity dimension. The RCL SHALL atomically commit the exact risk-capacity vector and action-flow vector required by one potentially live action, or commit neither when their atomicity is required for safety. It SHALL produce an immutable, exact, single-use **Action Flow Permit** as evidence of the committed action-flow allocation. The permit is a mandatory precondition, not transmission authority.

The Broker Adapter / Egress Gateway remains the final transmission enforcement point. Immediately before the irreversible broker-directed boundary, it SHALL actively verify the exact current Action Flow Policy, Action Flow Generation, state and decision binding, RCL commitment, permit status, action lineage, broker capability and constraint state, protective classification where applicable, and all other required authority. A cached boolean, local counter, TTL, heartbeat, service health, queue position, prior success, broker connection, absence of a rate-limit response, or absence of invalidation is not currentness proof.

Action flow SHALL be bounded over every applicable shared scope, including global, Safety Cell, broker, legal portfolio, account, credential, session, route, endpoint, venue, instrument, strategy, Intent, originating event, and action class. A component may not select a narrower scope merely because it cannot observe another producer or because a broker documents limits incompletely. Unknown dependency or limit scope expands to the smallest conservative containing scope and blocks new normal risk.

The architecture SHALL bound amplification, not only final sends. Duplicate events, fan-out, retries, reconnect callbacks, replay, failover, resubscription, cancellation loops, replacement loops, reconciliation polling, broker redirects, SDK retries, and queue redelivery SHALL have explicit causal lineage, maximum depth, maximum fan-out, maximum attempts, and bounded time/resource consumption. A changed command is a new action, not a harmless retry.

Missing ACK is not proof of non-acceptance and SHALL NOT authorize a retry. Cancel ACK is not Final Quantity Proof and SHALL NOT authorize capacity release, replacement reuse, or retry. Any transmission whose ordering or broker acceptance cannot be proven remains potentially live, consumes conservative economic capacity, consumes or quarantines its action-flow allocation, and blocks blind resubmission.

Protective, cancellation, reconciliation, HALT-supporting, and recovery traffic SHALL NOT depend on ordinary traffic merely having lower priority. Every claimed protective broker-facing resource SHALL have an evidence-backed guarantee classification and an exclusive RCL pre-commitment for the relevant request, queue, in-flight, credential, session, route, endpoint, and broker-rate dimensions. Priority is not reserved protective capacity. If the broker exposes an inseparable common-mode limit, normal admission SHALL be reduced enough to preserve the proven reserve or the protective guarantee SHALL be downgraded honestly and live scope reduced or prohibited.

Ordinary flow exhaustion, broker throttling, queue saturation, rate-state ambiguity, counter divergence, permit-store partition, or evidence loss SHALL stop new normal risk before consuming the protective reserve. Protective traffic still requires exact current admissibility, capacity, authority, and a valid protective lease; the label `protective`, `exit`, `cancel`, `reconcile`, `emergency`, or `high priority` creates none of them.

During a control-plane partition while a broker route remains reachable, no new normal Action Flow Decision or RCL allocation may be created. Only an exclusive, bounded, pre-issued protective lease with a monotonic local sub-budget may be consumed within its exact scope. If lease exclusivity, remaining budget, time continuity, action classification, or final-egress currentness cannot be proven, no broker-directed action is permitted.

Permit, policy, decision, capability, authority, queue item, or retry-window expiry limits future action only. It does not expire or reverse any possible broker or economic effect. Unknown order, exposure, transmission, broker-rate, queue, session, or permit state consumes conservative capacity and blocks new risk until authoritative resolution.

Restart, rollback, restore, failover, reconnect, backoff expiry, queue drain, counter refill, broker throttle recovery, matching replay, or improved service health cannot revive an old decision, permit, capability, action budget, authority, or live scope. Fresh artifacts and the complete governed re-arm process are required. No automatic re-arm is permitted.

Documentation, metrics, alerts, audit, replay, rate-limit responses, broker rejection, or post-trade reconciliation cannot substitute for preventive action-flow admission, exclusive budget commitment, and final-egress enforcement. Written acceptance cases and registered evidence are not completed evidence.

---

## 2. Context

RFC-001 SAFE-014 requires bounded order-generation, cancellation, replacement, and retry behavior, and requires rate-bound violations to invoke containment independently of strategy behavior. ADR-002-001 requires protective traffic capacity, ADR-002-004 requires broker-specific rate-limit and session evidence, ADR-002-009 addresses shared-resource failure domains, ADR-002-013 bounds reconnect and retry paths, and ADR-002-021 includes action-rate dimensions in aggregate risk.

Those rules establish the requirement but do not yet define one complete distributed protocol for all producers and all broker-facing resources. Without one contract, an implementation can:

- enforce a local token bucket per strategy while many producers exceed a shared broker or account limit;
- count only submissions while cancel, replace, amend, query, session, or SDK retry traffic exhausts the same broker resource;
- duplicate one event into unbounded commands through fan-out, redelivery, reconnect, or replay;
- treat missing ACK, timeout, HTTP retry, or SDK retry as evidence that another attempt is safe;
- let an ordinary burst consume the queue, session, credential, or broker limit needed for containment;
- call priority scheduling a protective reserve without proving exclusive usable capacity;
- issue several locally valid tokens against the same distributed headroom;
- refill a bucket from stale or cross-host-incomparable time;
- keep sending from a cached `ALLOW` after a limit, generation, policy, or broker constraint changes;
- let a retry queue, proxy, signer, SDK, or reconnect layer bypass the final gate;
- release action or economic capacity because a permit expired or a broker rejected a later duplicate;
- recover counters or reconnect a session and automatically resume or re-arm.

This ADR closes those paths without creating a second capacity ledger or weakening final-egress enforcement.

---

## 3. Decision Drivers

1. Bounded activity is a distributed aggregate property, not a producer-local rate limit.
2. Broker limits may be shared across accounts, sessions, credentials, endpoints, action classes, or environments.
3. One cause can amplify into many broker mutations through retry, fan-out, reconnect, replay, or replacement.
4. Ordinary traffic must not consume resources required for safety-owned protection and containment.
5. Priority ordering does not prove capacity, exclusivity, route availability, or broker acceptance.
6. Action-flow capacity and economic risk capacity must not race or be double committed.
7. Unknown send and broker state must remain conservative and cannot become retry permission.
8. Every live route and intermediary must remain inside the final enforcement boundary.
9. Rate windows and refill require trustworthy-time and generation fencing.
10. Recovery must not restore permission or automatically re-arm.

---

## 4. Scope and Non-Scope

This ADR decides:

- Action Flow Policy, Generation, State Snapshot, Decision, and Permit contracts;
- complete action and producer classification;
- hierarchical shared-scope budgets, burst limits, queue/in-flight limits, and amplification limits;
- RCL-only action-flow capacity mutation and atomic risk/action commitment;
- retry, reconnect, replay, duplicate-event, cancellation, amendment, and replacement containment;
- protective-flow reservation and common-mode disclosure;
- trustworthy-time, invalidation, partitions, stale writers, and final-egress currentness;
- economic continuity, recovery, evidence, acceptance, and approval behavior.

This ADR does not decide:

- whether a strategy should propose an action;
- exact broker-command construction, which remains ADR-002-020;
- venue, session, account, or order admissibility, which remains ADR-002-019;
- aggregate economic-risk evaluation, which remains ADR-002-021;
- capacity-ledger persistence and consensus product selection, which remains ADR-002-012;
- final credential, route, Commit Proof, and hard-fence mechanism, which remains ADR-002-013;
- concrete token-bucket, leaky-bucket, queue, scheduler, broker SDK, database, consensus, or programming-language products;
- numeric rates, bursts, ages, queue sizes, or propagation bounds, which require an approved Verification Profile and Broker Capability Profile.

---

## 5. Definitions

### 5.1 Action Flow Policy

An immutable, authenticated, content-addressed policy defining governed action classes, resource dimensions, scope aggregation, rates, bursts, queue and in-flight limits, amplification bounds, retry and reconnect rules, protective reservations, materiality, invalidation, and consumer compatibility. It is part of the ADR-002-014 Safety Configuration Bundle.

### 5.2 Action Flow Generation

A monotonic generation identifying the current compatible policy, broker capability and constraint inputs, scope graph, counter semantics, time/refill semantics, resource model, and consumer set. A newer generation fences stale evaluators, RCL requests, permits, and egress consumers. It grants no authority.

### 5.3 Action Flow State Snapshot

An immutable consistency-cut artifact containing all committed and potentially consumed action-flow capacity, outstanding permits, claimed and ambiguous sends, queues, in-flight operations, broker-observed limits, protective reservations, partitions, and shared dependencies for every applicable scope. It grants no permission.

### 5.4 Action Flow Decision

An immutable non-authorizing result binding one exact action, cause and lineage, current policy/generation, state snapshot, broker capability and constraint state, resource-consumption vector, amplification envelope, applicable scopes, protective classification evidence, and `GRANT`, `DENY`, or `UNKNOWN`. A `GRANT` authorizes only an exact RCL allocation request.

### 5.5 Action Flow Permit

An immutable, exact, single-use RCL commitment record for one action-flow vector and one action identity. It is consumed or quarantined atomically with the send claim. It is not Live Authorization, a Transmission Capability, broker permission, or evidence that an action is safe.

### 5.6 Action Flow Vector

The multi-dimensional maximum resource consumption of an action, including broker request, order mutation, cancel/amend/replace, query, session, credential, route, endpoint, queue, in-flight, and cause-amplification dimensions over all applicable scopes.

### 5.7 Action Cause

The immutable root and causal path that led to an action, such as an approved Intent, fill, venue event, protection obligation, reconciliation obligation, human HALT, timeout, retry decision, recovery obligation, or external event. Every derived action preserves the root cause and parent lineage.

### 5.8 Action Amplification Envelope

The policy-owned maximum count, rate, fan-out, depth, time, queue, and broker-resource consumption that one root cause may induce across all paths and components. Unknown or unbounded amplification is denial.

### 5.9 Protective Flow Reserve

An exclusive, scope-limited RCL pre-commitment of proven broker-facing resources for safety-owned protective or containment actions. It is separate from priority and is usable only through a valid protective lease and final gate.

### 5.10 Material Flow Change

Any change that may alter action classification, resource usage, shared scope, limit, reserve, lineage, retry safety, currentness, or result, or weaken proof. Materiality is policy-owned. Unknown materiality is material.

---

## 6. Safety Invariants

### AFG-INV-001 — Complete Action Scope

Every broker-directed producer, path, action class, resource, and shared limit is governed. Unknown scope expands conservatively.

### AFG-INV-002 — Bounded Amplification

Every root cause has finite, enforced fan-out, depth, attempt, time, queue, and broker-mutation bounds across all components.

### AFG-INV-003 — Exact Action Binding

One decision and permit bind one exact action identity, command or operation, cause, lineage, scope, generation, and resource vector; they cannot be patched, unioned, widened, transplanted, or replayed.

### AFG-INV-004 — RCL-Only Budget Mutation

Only the RCL serializes, commits, consumes, quarantines, replenishes, transfers, or releases governed action-flow capacity.

### AFG-INV-005 — Atomic Economic and Flow Coverage

No potentially live action may cross egress unless its worst credible economic effect and action-flow resource vector are both exclusively committed for the exact action.

### AFG-INV-006 — Protective Reserve Is Exclusive

Normal traffic cannot borrow, consume, relabel, or depend on the minimum Protective Flow Reserve. Priority alone is never reservation.

### AFG-INV-007 — UNKNOWN Is Restrictive

Unknown, stale, missing, conflicting, ambiguous, or unverifiable action, send, broker, counter, queue, permit, or reserve state consumes conservative capacity and blocks new normal risk.

### AFG-INV-008 — No Blind Retry

Missing ACK, timeout, reconnect, redelivery, broker error, or SDK behavior never proves non-acceptance or authorizes resubmission.

### AFG-INV-009 — Cancel ACK Is Not Final Quantity Proof

Cancellation acknowledgement does not release economic or action-flow coverage and does not make replacement or retry safe.

### AFG-INV-010 — Active Currentness at RCL and Egress

The RCL and final egress positively verify current policy, generation, state, decision, permit, broker constraint, and invalidation status without permissive cache assumptions.

### AFG-INV-011 — Authority Separation

The Action Flow Governor cannot mutate capacity, issue authority, classify protection, transmit, clear HALT, or re-arm. Final egress cannot invent or widen a decision.

### AFG-INV-012 — Economic Effect Persists

Permit, decision, policy, authority, retry-window, or queue-item expiry never expires a possible broker or economic effect.

### AFG-INV-013 — Stale Generations Are Fenced

Stale policy, flow, writer, recovery, authority, capability, credential, session, route, and egress generations cannot allocate, consume, or transmit.

### AFG-INV-014 — Recovery and Evidence Create No Permission

Recovery, refill, queue drain, broker health, audit, replay, documentation, or evidence registration cannot revive permission or automatically re-arm.

---

## 7. Authority Ownership and Separation

| Action | Policy or request authority | State-transition or enforcement authority | Prohibited combination |
|---|---|---|---|
| Define action classes, limits, and reserve policy | Action Flow Policy governance | Safety Profile Validator activates a compatible bundle | Runtime producer SHALL NOT self-select limits or scope |
| Classify ordinary action | Execution Coordinator requests exact class under policy | Action Flow Governor verifies the class | Producer label cannot create a more permissive class |
| Classify protective action | Protective Action Controller under ADR-002-001 | RCL and final egress verify lease, proof, and scope | Action Flow Governor and strategy SHALL NOT create protective authority |
| Evaluate action flow | Action Flow Governor | None | Governor SHALL NOT mutate a budget, issue authority, or transmit |
| Commit or consume action-flow capacity | Exact current grant supplies an allocation request | RCL is sole serialization and mutation authority | Local limiter SHALL NOT create distributed headroom |
| Issue Action Flow Permit | None | RCL records an exact committed single-use allocation | Permit SHALL NOT be treated as Transmission Capability |
| Schedule within committed scope | Execution Coordinator or Protective Action Controller | Bounded scheduler orders eligible work | Scheduler priority SHALL NOT create reserve or authority |
| Claim and transmit | Execution Coordinator requests | RCL claim plus Broker Egress Gateway final enforcement | No valid permit and capability means no send |
| Reconcile usage | Reconciliation Service supplies evidence | RCL transitions only through defined proof rules | Reconciliation SHALL NOT arbitrarily refill or release capacity |
| Halt | Safety Authority or authenticated emergency operator | Final-egress deny latch applies monotonically | Flow availability SHALL NOT delay HALT denial |
| Re-arm | ADR-002-007/015 governed workflow | Final egress accepts only fresh authority and generations | Counter recovery and broker reconnect SHALL NOT auto re-arm |

The Action Flow Governor SHALL NOT hold a live broker credential, signer, session, route, or endpoint capability. A combined broker read/trade credential is a declared common mode under ADR-002-013; the governor may consume constrained evidence only through a service that cannot reach an order route.

---

## 8. Action Flow Policy Contract

The policy SHALL define at least:

- exact action taxonomy for submit, cancel, amend, replace, retry, query, session, reconnect, subscribe, unsubscribe, administrative, evidence, protective, and HALT-supporting operations;
- resource dimensions and units, including broker requests, mutations, orders, cancels, queries, sessions, queues, in-flight operations, credentials, routes, endpoints, and cause amplification;
- global and hierarchical scope graph, aggregation, shared-limit, and dependency rules;
- sustained rate, burst, maximum outstanding, queue, in-flight, fan-out, depth, attempt, and elapsed-time bounds;
- atomic risk/action commitment requirements;
- retry, deduplication, idempotency, reconnect, replay, redelivery, and replacement rules;
- Protective Flow Reserve dimensions, guarantee levels, exclusive consumers, and lease requirements;
- trustworthy-time and refill semantics;
- materiality, invalidation, containment, recovery, and consumer-compatibility rules;
- evidence and alert requirements.

Omitted or unknown fields are restrictive. A policy cannot delegate materiality, scope, or reserve classification to a producer. Runtime configuration may narrow the Hard Safety Envelope but cannot enlarge it.

---

## 9. Complete Action and Resource Classification

Every operation that may consume a broker, credential, session, connection, route, queue, thread, socket, endpoint, order, cancel, query, or rate resource is governed even when it is believed not to create economic exposure.

The policy SHALL distinguish at least:

- `NORMAL_NEW_RISK`;
- `ORDINARY_REDUCE_OR_EXIT`;
- `SAFETY_PROTECTIVE`;
- `CANCEL_OR_REPLACE`;
- `RECONCILIATION_QUERY`;
- `SESSION_OR_CONNECTION_CONTROL`;
- `HALT_SUPPORT`;
- `RECOVERY_NON_LIVE`;
- `ADMINISTRATIVE_NON_LIVE`.

Classification does not create admissibility, risk capacity, protective capacity, authority, or broker permission. An exit can increase risk through zero crossing, reversal, wrong-side execution, overlap, or stale state. A cancel can remove required protection. A query or reconnect can exhaust the same shared resource needed for protection. The more conservative applicable class and vector govern when classification conflicts.

---

## 10. Scope Graph and Shared Limits

The Action Flow State Snapshot SHALL cover every applicable global, environment, Safety Cell, broker, legal portfolio, account, credential, session, connection pool, route, endpoint, venue, instrument, strategy, Intent, cause, and action-class scope.

If a broker's documented scope is incomplete, contradictory, stale, or unverified, the limit SHALL be treated as shared across the largest credible containing scope. Account-local success is not evidence that a credential, session, IP, route, or broker-global limit is independent.

Separate processes, nodes, regions, queues, or local counters do not establish independent capacity. Independence requires evidence that allocation, refill, broker enforcement, credential/session state, failure domain, and final route are genuinely separate.

---

## 11. Action Amplification and Causal Lineage

Every broker-directed action SHALL carry an immutable root-cause identity and complete parent lineage. The governing envelope SHALL bound:

- maximum child actions per parent and per root cause;
- maximum causal depth;
- maximum attempts per exact action and root cause;
- maximum broker mutations and queries;
- maximum queued and in-flight work;
- maximum elapsed monotonic duration;
- maximum duplicate, redelivery, failover, reconnect, and replay expansion.

A duplicate event does not create another allowance. Concurrent consumers of the same cause share one envelope. A replay is evidence unless a fresh non-live workflow creates a new governed cause; it cannot recreate a live action. A changed quantity, price, route, account, instrument, action class, effect, session, credential, or broker identity is a new action and requires fresh construction, risk, flow, authority, and capability artifacts.

If cause lineage is missing, cyclic, forked beyond its bound, or inconsistent across components, the action is `UNKNOWN`, no new normal flow is admitted, and the affected scope is contained.

---

## 12. Rate, Burst, Queue, and In-Flight Semantics

Every limit SHALL have an exact unit, scope, measurement point, aggregation rule, window or refill rule, burst rule, maximum debt, and failure response. The policy SHALL distinguish at least:

- allocations committed but not yet claimed;
- claims made but no broker byte proven;
- broker-directed writes started;
- acknowledged and unacknowledged operations;
- queued, in-flight, throttled, rejected, timed out, and ambiguous operations;
- usage reserved exclusively for protection.

Queues SHALL be bounded by count, bytes where relevant, age, cause, scope, and action class. Queueing does not extend permit, authority, context, constraint, decision, capability, or policy validity. Work whose prerequisites expire in queue is denied and cannot be silently refreshed.

A local scheduler may reorder only actions whose independent prerequisites remain valid. It cannot merge permits, borrow a reserve, regenerate a command, or turn backlog into current authority.

---

## 13. RCL Commitment and Action Flow Permit

For an exact potentially live action, the RCL SHALL verify:

1. current writer epoch, committed prefix, and relevant ledger revision;
2. exact current Action Flow Policy and Generation;
3. exact Action Flow State Snapshot and Decision digests;
4. action identity, cause lineage, class, scope, and complete vector;
5. current Aggregate Risk Decision and economic capacity request where applicable;
6. sufficient ordinary or protective action-flow capacity in every dimension;
7. no incompatible outstanding permit or duplicate cause consumption;
8. current invalidation, recovery, HALT, and configuration state.

Where economic and action-flow coverage are both required, the RCL SHALL commit both in one deterministic transaction or in an ordering that cannot leave a live-send-capable partial state. If atomic coverage cannot be proven, no permit or Transmission Capability is issued.

The Action Flow Permit SHALL bind:

- permit, RCL commitment, writer epoch, revision, and command identities;
- exact policy/generation, state snapshot, decision, cause, and lineage digests;
- exact broker, account, credential/session, route, endpoint, venue, instrument, and action class;
- exact resource vector and whether each dimension is ordinary or protective;
- exact protective lease and reserve proof when applicable;
- exact consumer, claim nonce, single-use state, issue anchor, maximum age, and invalidation generation;
- exact economic-capacity commitment and conformance chain where applicable.

An unused permit may be released only by an RCL transition proving it was never claimed and cannot reach any broker path. A claimed, ambiguous, lost, or conflicting permit remains consumed or quarantined. Releasing action-flow capacity never releases economic capacity without its separate Final Quantity Proof rules.

---

## 14. Retry, Timeout, and Missing Acknowledgement

Retry is a new broker-directed action unless the active Broker Capability Profile positively proves exact broker-side idempotency for the same immutable request identity and the approved policy defines a safe transport replay. Even then, the replay consumes governed action-flow capacity and remains inside the original economic reservation and causal envelope.

Missing ACK, timeout, connection reset, proxy failure, SDK exception, redirect, or rate-limit response does not prove that the broker did not accept the request. The attempt remains potentially live. No retry occurs until current evidence, capability, policy, economic coverage, flow capacity, action lineage, and fresh authority all allow it.

Retry count, elapsed time, backoff completion, or repeated identical response cannot convert UNKNOWN into known rejection. Blind failover to another session, endpoint, route, credential, broker, or client order identity is prohibited.

---

## 15. Cancellation, Amendment, and Replacement Storms

Cancel, amend, and replace actions consume explicit broker and action-flow dimensions. A cancel acknowledgement is not Final Quantity Proof. The original order and any replacement remain covered for worst credible overlap, late fill, reversal, and protection gap under ADR-002-002 and ADR-002-011.

Repeated cancellation or replacement triggered by price movement, partial fill, timeout, reconnect, stale observation, or duplicate event SHALL share one bounded cause envelope. No controller may oscillate indefinitely between cancel and submit, or create a new cause merely to reset its budget.

When the reserve required to preserve or restore protection is unavailable, the system records trapped or insufficiently protected exposure, blocks new risk, contains the affected scope, and escalates. It does not assume the broker will accept one more cancel or replacement.

---

## 16. Protective Flow Reserve

Every protective resource claim SHALL be classified `PHYSICALLY_RESERVED`, `LOGICALLY_RESERVED`, `PRIORITIZED_ONLY`, `BEST_EFFORT`, or `UNAVAILABLE` under ADR-002-001/004. Only the first two may be counted as guaranteed Protective Flow Reserve, and only within their proven broker, account, session, credential, route, endpoint, action-class, and failure-domain scope.

The RCL SHALL pre-commit the minimum reserve separately from ordinary headroom. Normal actions cannot consume, borrow, temporarily use, or repay it later. Protective actions consume it only through a valid exclusive protective lease, exact protective proof, and single-use permit.

Admission SHALL account for broker request and order limits, cancellation and query limits, session serialization, queue and in-flight slots, credential and route availability, reconnect behavior, and common-mode saturation. A high-priority queue without exclusive capacity is `PRIORITIZED_ONLY`, not reserved.

If normal and protective traffic share an inseparable broker limit, normal admission SHALL remain below the demonstrated worst-case level needed to preserve the reserve. If that level cannot be established, protective capability is downgraded, normal live scope is narrowed or prohibited, and the residual risk is explicitly approved. Documentation cannot turn common mode into capacity.

---

## 17. Final-Egress Enforcement and Active Currentness

For every broker-directed effect, the final egress SHALL verify at minimum:

1. exact current Action Flow Policy, Generation, and consumer compatibility;
2. exact current Action Flow Decision and complete scope/vector binding;
3. exact RCL commitment, current writer epoch/revision, and unused single-use permit;
4. exact command or operation digest, action identity, root cause, lineage, and action class;
5. current broker capability, venue constraint, rate-limit, session, route, endpoint, and credential state;
6. current risk commitment, conformance proof, Live Authorization, Safety Authority, and Transmission Capability where applicable;
7. current protective lease, reserve proof, and classification for protective consumption;
8. no newer invalidation, HALT, Recovery Generation, policy, capability, constraint, or egress generation.

The proof SHALL be active and bounded at the irreversible boundary. Cache lifetime, TTL, heartbeat, last-known counter, last-known generation, service health, broker connection, prior success, eventual consistency, queue ownership, or absence of invalidation/error is not proof.

Final egress SHALL invoke one RCL-owned atomic claim transition that consumes or quarantines the permit in the same fenced ordering used for `SEND_STARTED`; egress does not mutate the budget independently. No queue, proxy, sidecar, signer, SDK retry, session manager, reconnect layer, redirect, or alternate route may exist after this boundary in a way that can delay, duplicate, mutate, or replay the action outside the bound.

If invalidation, exhaustion, HALT, or a newer generation races the claim or first byte and ordering cannot prove that the broker action preceded the restriction, the action is potentially live, the permit remains consumed or quarantined, all credible economic effects remain capacity-covered, and no blind retry occurs.

Final egress verifies facts and exact conformance. It cannot recalculate a more favorable flow vector, invent a cause, change an action class, borrow reserve, or widen a decision.

---

## 18. Time, Windows, and Refill

Rate windows, permit age, backoff, refill, and lease consumption SHALL follow ADR-002-008 trustworthy-time rules. Consumer-local elapsed time uses a local monotonic basis. Monotonic values from different hosts or processes SHALL NOT be directly subtracted.

Distributed refill SHALL be serialized by the RCL from an approved time model and committed history. Wall-clock movement, clock recovery, process restart, broker timestamp, or a newly healthy time source cannot manufacture headroom. Negative age, future issue time, uncertainty, discontinuity, or unknown continuity is clamped toward restriction, never toward refill.

Time recovery creates a new Time Health Generation and does not revive permits, decisions, leases, or live authority.

---

## 19. Invalidation, Containment, and Economic Continuity

Material changes to policy, broker limits, constraint state, session, credential, route, endpoint, scope graph, time health, queue/in-flight state, cause lineage, RCL state, protective reserve, capability, or consumer compatibility SHALL invalidate every affected unclaimed decision and permit.

Invalidation SHALL reach the RCL and every final egress within approved bounds. If complete propagation cannot be proven, the affected scope stops new risk and expands containment to every possibly affected shared scope.

Rate-bound violation, unexpected throttling, counter divergence, queue overflow, amplification breach, duplicated permit, unknown claim state, or protective-reserve intrusion SHALL invoke containment independently of strategy behavior. Ordinary work is denied first. Necessary existing protection is not blindly cancelled merely to clear a queue or regain limits.

Permit invalidation or expiry does not reverse a broker action, release economic capacity, prove rejection, or clear UNKNOWN. Missing ACK remains potentially live; cancel ACK remains insufficient for Final Quantity Proof.

---

## 20. Partitions, Failover, and Stale Writers

During loss of RCL quorum, Action Flow Generation currentness, required broker constraint currentness, or egress-currentness proof, no new normal permit may be committed or consumed.

An exclusive protective sub-ledger may operate only from a pre-issued scope-limited lease with a monotonic local budget that cannot overlap another writer or rejoin without reconciliation. The lease cannot refill from a remote or wall clock during partition. Loss of lease, continuity, exclusivity, or remaining-budget proof denies transmission.

Old RCL writers, Action Flow Governors, schedulers, recovery owners, deployment generations, credential holders, sessions, and egress principals are potentially active until hard fenced. A newer generation does not make them harmless by observation alone.

Failover does not reset counters, causes, queues, attempts, permits, or ambiguity. Conflicting histories expand UNKNOWN and containment; they do not choose the more favorable headroom.

---

## 21. Broker Capability and Constraint Integration

The active Broker Capability Profile SHALL establish, per exact scope:

- documented and observed request, mutation, order, cancel, query, session, connection, and in-flight limits;
- whether limits are broker-, credential-, IP-, route-, session-, account-, venue-, endpoint-, or action-class shared;
- burst and sustained semantics, rolling/fixed windows, server time, response fields, and reset behavior;
- queueing, throttling, rejection, partial processing, redirect, SDK retry, reconnect, and duplicate behavior;
- idempotency and client-order identity semantics;
- protective-resource guarantee level and common-mode limitations;
- drift, contradiction, and recovery detection.

Broker documentation, sandbox behavior, prior success, HTTP status, headers, or SDK defaults are evidence inputs, not permission. Contradiction, drift, `BEST_EFFORT`, or `UNAVAILABLE` reduces or prohibits scope.

The Venue Constraint Gate may report current broker constraints but cannot create action-flow capacity. The Action Flow Governor may evaluate them but cannot override venue admissibility. Final egress independently enforces both exact current contracts.

---

## 22. Recovery and Non-Revival

Recovery SHALL inventory and reconcile:

- all causes, child actions, decisions, permits, claims, queues, in-flight work, and ambiguous sends;
- current and historical RCL action-flow commitments and protective leases;
- broker requests, orders, cancels, queries, throttles, sessions, reconnects, and external activity;
- policy, generation, time, scope graph, broker capability, constraint, credential, route, and egress state;
- every counter divergence, Evidence Gap, unknown result, and containment action.

Restarted or restored producers begin non-live and cannot assume a zero counter, empty queue, unused permit, rejected request, or recovered broker limit. A fresh complete Action Flow State Snapshot and Decision are required. Old permits are invalid unless their exact unused state and generation remain authoritatively proven; conservative default is consumed or quarantined.

Recovery readiness is not action capacity, authority, or permission. Broker reconnect, counter refill, backoff expiry, empty queue, matching replay, or healthy metrics cannot open the Recovery Barrier or re-arm. ADR-002-007, ADR-002-015, and ADR-002-017 govern fresh explicit re-arm.

---

## 23. Evidence, Metrics, and Alerts

Prevention evidence SHALL record at least:

- exact policy, generation, state snapshot, decision, permit, RCL revision/writer epoch, and action identity;
- root cause, parent lineage, amplification counters, scope graph, class, vector, limit, reserve, and remaining headroom;
- queue, in-flight, claim, `SEND_STARTED`, first-byte, broker response, ACK, fill, cancel, and reconciliation transitions;
- broker capability and constraint sources, rate responses, contradictions, drift, and common-mode classification;
- every deny, UNKNOWN, invalidation, exhaustion, overflow, duplicate, stale generation, containment, HALT, and recovery transition;
- consumer-local monotonic anchors and trustworthy-time state;
- exact final-egress currentness and outbound equivalence checks.

Metrics and alerts SHALL cover action rate and burst by all scopes, cause amplification, queue age/depth, in-flight operations, permit lifecycle, ordinary/protective reserve usage, unexpected broker throttle, counter divergence, stale generation, invalidation latency, and containment latency.

Logs, metrics, dashboards, replay, and post-hoc alerts are evidence. They do not authorize, serialize, reserve, prevent, transmit, release capacity, or re-arm.

---

## 24. Security and Common-Mode Analysis

Security review SHALL trace every identity and path that can:

- create or duplicate a cause;
- issue, mutate, replay, or suppress a decision or permit;
- change policy, limit, scope, reserve, or generation;
- mutate RCL action-flow capacity;
- schedule, queue, retry, reconnect, sign, route, or transmit;
- conceal broker throttling, queue depth, in-flight state, or reserve exhaustion.

Shared libraries, counters, datastores, clocks, schedulers, queues, credentials, sessions, routes, endpoints, SDKs, network paths, identity administrators, and deployment pipelines are declared common modes. Apparent independent local limiters do not count as independent when they share any authority or failure path that can over-allocate or bypass enforcement.

No flow-evaluation, strategy, recovery, reconciliation, replay, operator, or administrative identity may combine usable live broker authority and a route outside the ADR-002-013 final boundary.

---

## 25. Rejected Alternatives

### 25.1 Per-Strategy or Per-Process Rate Limiting

Rejected. It cannot serialize shared broker, account, credential, session, route, endpoint, or protective capacity.

### 25.2 Broker Rejection as the Limit

Rejected. Broker rejection is late, may be partial or ambiguous, can consume protective resources, and does not prevent duplicate economic effect.

### 25.3 Priority Queue as Protective Reservation

Rejected. Priority does not prove headroom, exclusive queue slots, route/session availability, or broker acceptance.

### 25.4 Retry With Exponential Backoff

Rejected as a safety mechanism. Backoff bounds timing but does not prove non-acceptance, deduplication, capacity, or current authority.

### 25.5 Reset Counters on Restart or Reconnect

Rejected. It manufactures headroom while old requests or broker effects may remain live.

### 25.6 Count Only New Orders

Rejected. Cancel, amend, replace, query, session, reconnect, and SDK behavior can exhaust the same safety-critical resource.

### 25.7 Flow Decision Directly Sends or Mutates Capacity

Rejected. It collapses policy, serialization, and transmission authority.

### 25.8 Cached Allow or Token at Egress

Rejected. It permits stale generation, reserve, limit, session, or invalidation state to cross the final boundary.

### 25.9 Human Override, Protective Label, or Emergency Mode

Rejected. These cannot create reserve, current admissibility, economic coverage, or broker permission.

### 25.10 Documentation, Monitoring, or Replay as Prevention

Rejected. Observation after the fact cannot bound an already emitted storm.

### 25.11 Rate Recovery Automatically Resumes

Rejected. Refill, queue drain, reconnect, or broker recovery cannot revive old authority or auto re-arm.

### 25.12 Cancel ACK or Timeout Releases Capacity

Rejected. Cancel ACK is not Final Quantity Proof, and timeout is not proof of non-acceptance.

---

## 26. Consequences

### 26.1 Positive

- One distributed contract bounds every broker-facing producer and path.
- RCL remains the sole capacity mutation and serialization authority.
- Economic and broker-resource coverage cannot be independently overcommitted.
- Retry, reconnect, replay, redelivery, and replacement amplification become explicit and testable.
- Protective traffic is backed by proven exclusive capacity rather than priority language.
- Final egress remains non-bypassable and generation-current.
- Recovery and broker-rate improvement cannot revive permission.

### 26.2 Negative

- Action-flow capacity becomes another conservative RCL vector with higher write and proof load.
- Accurate shared-limit scope and broker capability evidence may be difficult or unavailable.
- Exclusive protective reservation reduces normal throughput.
- Some brokers will support only `PRIORITIZED_ONLY` or `BEST_EFFORT` protection, reducing live scope.
- Active currentness and claim-to-send ordering require a concrete bounded protocol.
- Queue, retry, SDK, and reconnect behavior must be brought inside the governed boundary.

These costs are accepted because throughput cannot outrank prevention and protective continuity.

---

## 27. Acceptance Cases

### AFG-AC-001 — Distributed Shared-Limit Serialization

Drive concurrent producers across processes, nodes, accounts, sessions, credentials, routes, and endpoints against overlapping local and broker-global limits. The RCL must prevent aggregate over-allocation.

### AFG-AC-002 — Duplicate Event and Fan-Out Amplification

Duplicate, reorder, fork, replay, and redeliver root events through multiple consumers. One cause must remain within finite fan-out, depth, attempt, queue, and mutation bounds.

### AFG-AC-003 — Missing-ACK Retry and Reconnect Storm

Drop responses after possible broker acceptance, reconnect sessions, trigger SDK/proxy retries, and fail over routes. No blind retry or new identity may escape conservative economic and flow coverage.

### AFG-AC-004 — Cancel, Amend, and Replace Storm

Cross partial fills, price changes, cancel ACKs, timeouts, and protection replacement. Cancel ACK must not become Final Quantity Proof, and oscillation must be bounded.

### AFG-AC-005 — Complete Action and Resource Classification

Exhaust submit, cancel, query, session, reconnect, queue, in-flight, and administrative dimensions separately and jointly. No uncounted class may bypass the most conservative shared limit.

### AFG-AC-006 — Protective Reserve Exclusivity

Saturate ordinary traffic, then require protective, cancellation, reconciliation, and HALT-supporting actions. Only proven reserved capacity may be claimed; priority alone must not pass.

### AFG-AC-007 — RCL Atomicity and Permit Single Use

Race economic and flow commitments, duplicate permits, lose commit responses, crash at claim, and replay consumed identities. No partial coverage, double spend, or permit reuse may transmit.

### AFG-AC-008 — Time, Refill, and Counter Integrity

Inject wall-clock jumps, monotonic discontinuity, cross-host timestamps, restart, stale refill, window-boundary races, and counter divergence. No event may manufacture headroom.

### AFG-AC-009 — Invalidation and Final-Egress Currentness

Change policy, broker limit, session, route, constraint, reserve, or generation between decision, RCL commit, claim, and first byte. Stale or unprovable actions must be denied or remain potentially live and covered.

### AFG-AC-010 — Partition, Stale Writer, and Protective Lease

Partition control plane from broker-reachable egress, resume old writers and schedulers, and overlap protective sub-ledgers. Normal traffic must stop; only a proven exclusive bounded lease may proceed.

### AFG-AC-011 — Authority Separation and Bypass

Attempt direct sends or capacity mutation from strategy, governor, scheduler, retry queue, SDK, reconciliation, recovery, replay, operator, and alternate credentials/routes. Every bypass must fail.

### AFG-AC-012 — Recovery, Economic Continuity, and Non-Revival

Restart, rollback, restore, reconnect, drain queues, refill counters, recover broker health, and replay matching history while orders remain uncertain. Old decisions, permits, capabilities, and authority must not revive or auto re-arm.

Each case SHALL have a dedicated `AFG-EV-*` Evidence Register item. Writing or registering the case does not satisfy it.

---

## 28. Requirements Traceability

| Requirement | Decision coverage |
|---|---|
| SAFE-003, SAFE-004 | Conservative ambiguity, exact state, no permissive collapse (§§1, 9, 19) |
| SAFE-010, SAFE-011 | Independent containment and final-egress enforcement (§§7, 17, 19) |
| SAFE-012, SAFE-013 | Atomic economic and action-flow coverage (§§6, 13) |
| SAFE-014 | Distributed bounded rate, amplification, retry, reconnect, and storm containment (§§8–15) |
| SAFE-015 | RCL-only exclusive commitment and permit single use (§§6–7, 13) |
| SAFE-020, SAFE-021 | Complete causal lineage, potentially live UNKNOWN, and no blind retry (§§11, 14–15) |
| SAFE-024, SAFE-025 | Evidence-backed broker limits and conservative fallback (§§16, 21) |
| SAFE-030, SAFE-031 | Protective reserve and degraded partition behavior (§§16, 20) |
| SAFE-032, SAFE-033 | Exact venue/broker constraints and order shape remain independently enforced (§§17, 21) |
| SAFE-034, SAFE-035 | Common-mode disclosure and prevention-first evidence (§§16, 23–24) |
| SAFE-040, SAFE-041 | Closed recovery and stale-generation fencing (§§20, 22) |
| SAFE-042, SAFE-043, SAFE-044 | Independent safety path, immutable policy, and conservative configuration (§§7–8, 16) |
| SAFE-046, SAFE-048, SAFE-050 | Exact authority/capability binding and non-authorizing inputs (§§13, 17) |
| SAFE-051, SAFE-052 | No automatic re-arm and no unsafe live promotion (§§22, 29) |

---

## 29. Open Implementation Questions

1. Which RCL vector schema and deterministic transition model represent multi-scope rate, burst, queue, in-flight, cause-amplification, and protective-reserve capacity?
2. Which bounded protocol atomically commits economic and action-flow coverage without creating a cyclic dependency with Order Conformance Proof and Transmission Capability issuance?
3. How will the scope graph represent broker-global, credential-, IP-, route-, session-, account-, endpoint-, venue-, action-class-, and environment-shared limits?
4. Which currentness protocol lets the RCL and final egress actively prove Action Flow Generation, counter, permit, broker-limit, and invalidation state without permissive caches or circular dependencies?
5. How are claim, `SEND_STARTED`, first byte, permit consumption, and ambiguous send ordered and durably evidenced?
6. How are broker SDK retries, redirects, connection pools, proxies, signers, queues, reconnect layers, and session managers prevented from acting after the final claim boundary?
7. How will cause lineage and amplification counters remain complete across fan-out, replay, failover, and redelivery without one compromised producer self-resetting its envelope?
8. Which broker scopes can prove `PHYSICALLY_RESERVED` or `LOGICALLY_RESERVED` protective flow, and which remain `PRIORITIZED_ONLY`, `BEST_EFFORT`, or `UNAVAILABLE`?
9. How will protective sub-ledger leases prevent overlap and refill during partition, then rejoin the main RCL conservatively?
10. Which trustworthy-time model governs distributed refill and consumer receipt age without cross-host monotonic subtraction?
11. How will cancellation, query, session, reconnect, and administrative traffic share or isolate broker resources across normal and protective classes?
12. Which numeric rate, burst, amplification, age, queue, in-flight, invalidation, containment, and recovery bounds are approved per exact broker/profile scope?

Unresolved questions reduce authority and live scope. They never relax an invariant or create permissive fallback.

---

## 30. Approval Gate

ADR-002-022 remains `Proposed` until all of the following are true:

1. Action Flow Policy, State Snapshot, Decision, Permit, vector, cause-lineage, and amplification schemas are approved.
2. The RCL action-flow vector and deterministic atomic economic/flow commitment protocol are implemented and independently reviewed.
3. Exact distributed scope aggregation, refill, claim, consumption, quarantine, release, and protective-lease mechanisms are selected and security-reviewed.
4. Every broker-facing producer, queue, SDK, retry, reconnect, signer, proxy, session, credential, route, and endpoint is inventoried and confined behind final egress.
5. Active RCL and final-egress currentness, invalidation, claim-to-send, and stale-generation fencing mechanisms are selected and proven.
6. Broker Capability Profiles establish exact shared-limit, idempotency, retry, throttle, reconnect, and protective-reserve behavior for every claimed live scope.
7. Protective Flow Reserve is proven exclusive across request, queue, in-flight, session, credential, route, endpoint, and broker-rate resources; priority-only claims are not counted.
8. Missing-ACK, cancel-ACK, retry, replacement, UNKNOWN, permit-expiry, and economic-continuity rules are implemented without weakening ADR-002-001/002/004/011/020/021.
9. Verification Profile rate, burst, amplification, queue, age, invalidation, containment, refill, and protective-reserve bounds are approved and measured under fault injection.
10. `AFG-EV-001` through `AFG-EV-012` are executed at the required EV-L1/EV-L2/EV-L3/Broker/Security levels and independently reviewed.
11. Security review finds no direct broker route, capacity mutation path, local-budget over-allocation, reserve borrowing, stale-currentness cache, or post-claim retry path.
12. Critical and Major findings, including broker common-mode and send-race findings, are resolved or reduce live scope to non-live.
13. ADR-002-023 exact approval/consumption/Intent lineage is bound before flow allocation without allowing approval or Intent Registry identities to create action-flow capacity, and applicable IAP evidence passes.

This ADR authorizes architecture and implementation-planning work only. It authorizes no live trading. Written acceptance cases and registered evidence are not completed evidence. No automatic re-arm is permitted.
