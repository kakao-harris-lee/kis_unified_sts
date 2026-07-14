# ADR-002-017 — Safe Startup, Recovery Barrier, and Conservative Resume Coordination

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Cold start, warm restart, reconnect, failover, disaster restore, incident recovery, recovery-trigger scope, barrier activation, stale-worker fencing, authoritative inventory, reconciliation convergence, recovery obligations, readiness decisions, partial recovery, invalidation, evidence, and handoff to governed re-arm
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-022 through SAFE-025, SAFE-044, SAFE-046, SAFE-048, SAFE-051, and SAFE-052; RFC-002 §§10.19, 15, 20, 23, and 29; ADR-002-007 §§4.3, 11–15, and 23–25
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-021, SAFE-022, SAFE-023, SAFE-024, SAFE-025, SAFE-030, SAFE-031, SAFE-032, SAFE-033, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-042, SAFE-043, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-016

---

## 1. Decision

Every TOS Safety Cell SHALL start with a closed **Recovery Barrier** that denies new risk. Cold start, restart, reconnect, failover, restore, stale-instance detection, evidence conflict, external activity, non-trade change, lost prerequisite, or any event whose effect on safety scope is not positively bounded SHALL create or advance a monotonic **Recovery Generation** before recovery work begins.

The Recovery Coordinator SHALL assemble one immutable **Recovery Evidence Package** and issue one scoped **Recovery Readiness Decision** only after every required recovery obligation has reached a terminal conservative result under the same Recovery Generation. Recovery readiness is an assessment artifact. It SHALL NOT activate configuration, issue Live Authorization, mutate or release capacity, clear HALT, classify an action as protective, transmit to a broker, or automatically re-arm.

Barrier activation is restrictive and SHALL be ordered before or atomically with suspension of affected new-risk authority. Final egress SHALL reject any risk-increasing capability, authorization, readiness decision, or recovery artifact bound to an older Recovery Generation. A stale, isolated, restored, or resumed Recovery Coordinator cannot publish a usable readiness decision.

Recovery SHALL inventory and reconcile, at minimum, authoritative capacity commitments; intents and transmission attempts; broker orders, fills, cancellations, positions, balances, margin, collateral, sessions, and corrections; potentially-live and UNKNOWN effects; external/manual activity; non-trade events; protective ownership and coverage; safety configuration; authority, time, identity, deployment, egress, credential, route, evidence, and failure-domain state. Missing, stale, contradictory, or unbounded scope remains UNKNOWN, consumes conservative capacity, and blocks new risk.

No broker snapshot is assumed atomic. Recovery SHALL establish a conservative **Recovery Inventory Cut** whose start/end revisions, source continuity, events observed during the cut, and unresolved uncertainty are explicit. A convenient flat snapshot, missing broker acknowledgement, cancellation acknowledgement, cache agreement, process health, or later replay result cannot prove completeness.

`READY_RESTRICTED` may describe only a proven isolated scope. It cannot grant new-risk authority where any relevant UNKNOWN, external activity, shared capacity, common broker resource, protective dependency, or aggregate constraint remains unresolved. Recovery-only and separately authorized protective operations may continue with new risk blocked.

Recovery completion, service health, connectivity restoration, operator acknowledgement, evidence repair, replay match, or human approval never restores prior authority. Any risk-increasing resume requires the complete ADR-002-007 and ADR-002-015 workflow and creates fresh Live Authorization and per-action capabilities.

---

## 2. Context

RFC-001 SAFE-044 requires live autonomous trading to start or resume only after configuration, authorization, positions, open orders, Critical Inputs, venue/account state, and blocking obligations are safe. SAFE-022 requires reconciliation before exposure. RFC-002 assigns the Recovery Coordinator responsibility for the startup/recovery barrier and forbids automatic re-arm. ADR-002-007 separates Recovery Readiness, human Re-arm Approval, Live Authorization, and Transmission Capability.

Those documents do not yet define a complete recovery protocol. Unsafe implementation choices include:

- checking service health before fencing broker-reachable stale instances;
- letting two recovery workers publish competing readiness decisions;
- trusting a broker snapshot taken while fills, cancels, manual actions, or corporate events continue;
- declaring recovery complete because internal caches agree with each other;
- treating a missing order in one query page as proof that it is absent;
- releasing capacity when cancellation is acknowledged but final quantity is unknown;
- reconciling positions without open orders, attempts, protective obligations, or non-trade events;
- resuming one strategy while it still shares account capacity, session, credential, or protection with unresolved scope;
- allowing an old recovery decision to survive a new fill, time fault, profile change, external order, or Evidence Gap;
- restoring a backup and treating its state as current because no newer source is reachable;
- allowing recovery administrators to clear HALT, mutate RCL, or issue Live Authorization;
- converting a recovery timeout into a permissive fallback;
- treating successful replay, operator narrative, or a flat account snapshot as prevention or current authority.

This ADR defines a mechanism-independent recovery state machine, conservative inventory contract, ownership model, and re-arm handoff.

---

## 3. Decision Drivers

1. New risk must be fenced before recovery observation and repair begin.
2. Recovery must cover the complete economic and safety state, not selected healthy services.
3. Concurrent, stale, restored, and partitioned recovery workers must be fenced.
4. Broker and external state must be reconciled without assuming an atomic snapshot or unconditional source truth.
5. UNKNOWN, missing evidence, and conflicting histories must remain capacity-consuming and non-permissive.
6. Partial recovery must not bypass aggregate/shared dependencies.
7. Readiness must be immutable, exact, short-lived, invalidatable, and non-authorizing.
8. Restrictive HALT and existing protection must remain dominant throughout recovery.
9. Recovery must not mutate capacity, silently cancel protection, or issue broker effects.
10. Recovery, evidence repair, restore, or replay must never automatically re-arm.

---

## 4. Scope and Non-Scope

This ADR decides:

- Recovery Barrier Policy and trigger classification;
- Recovery Session and Recovery Generation state machines;
- affected-scope determination and conservative scope expansion;
- barrier ordering and final-egress fencing;
- current Recovery Coordinator ownership and stale-worker rejection;
- Recovery Inventory Cut and source-continuity requirements;
- required recovery obligations and dependency closure;
- reconciliation convergence and fixed-point rules;
- READY, READY_RESTRICTED, and NOT_READY semantics;
- partial-scope recovery and shared-resource exclusion;
- invalidation, timeout, abort, retry, failover, restore, and disaster-recovery behavior;
- evidence and acceptance obligations.

This ADR does not decide:

- field-specific reconciliation confidence or Final Quantity Proof, which remain ADR-002-004 and ADR-002-006;
- capacity mutation, quarantine, import, or release, which remain exclusively with the RCL under ADR-002-002 and ADR-002-012;
- protective classification, capacity, replacement, or broker transmission, which remain ADR-002-001, ADR-002-011, and ADR-002-013;
- human approval, Live Authorization, currentness, or egress permission, which remain ADR-002-007, ADR-002-013, and ADR-002-015;
- safety-configuration activation, which remains ADR-002-014;
- evidence custody and deterministic replay, which remain ADR-002-016;
- concrete workflow, consensus, storage, broker-query, or deployment products;
- approved numeric recovery bounds, which belong in the Verification Profile and Recovery Barrier Policy.

---

## 5. Definitions

### 5.1 Recovery Trigger

An authenticated or independently detected event that invalidates current readiness or requires the affected scope to prove recovery prerequisites again.

### 5.2 Recovery Barrier

A monotonic restrictive gate for one Recovery Scope and Recovery Generation. While closed, it denies new risk at authority issuance and final egress. It grants no recovery or protective action.

### 5.3 Recovery Barrier Policy

The separately governed artifact defining triggers, scope-expansion rules, required obligations, source classes, convergence rules, readiness validity, failure responses, and partial-recovery constraints.

### 5.4 Recovery Session

One immutable-identity workflow instance that owns recovery orchestration for an exact Recovery Generation and scope. It records transitions, obligations, evidence, denial, invalidation, and handoff without owning economic authorities.

### 5.5 Recovery Generation

A monotonic generation that fences readiness decisions and recovery workers for one Safety Cell or Recovery Domain. A newer generation invalidates every older in-progress or terminal readiness artifact for future authority.

### 5.6 Recovery Scope

The closed dependency set of accounts, Capacity Domains, Safety Cells, broker sessions, credentials, routes, strategies, instruments, protective structures, configuration, authority, and failure domains affected by the trigger.

### 5.7 Recovery Inventory Cut

A bounded, versioned set of authoritative-log revisions, broker/source observations, source continuity identities, trustworthy-time intervals, and all intervening events used to evaluate one recovery package. It is conservative evidence, not an assertion that external state was atomically frozen.

### 5.8 Recovery Obligation

One mandatory, typed predicate with owner, scope, evidence rule, dependencies, result, conservative failure response, and invalidation conditions.

### 5.9 Recovery Evidence Package

The immutable canonical manifest of the exact Recovery Session, generation, scope, inventory cut, obligations, conservative bounds, unresolved state, artifacts, and decisions evaluated by the Recovery Coordinator. It grants no authority.

### 5.10 Recovery Readiness Decision

A signed `READY`, `READY_RESTRICTED`, or `NOT_READY` assessment bound to one package, scope, generation, validity interval, and invalidation set. It is an input to later governance and never a live permission.

---

## 6. Safety Invariants

### SBR-INV-001 — Start Closed

Every Safety Cell begins with new-risk authority denied until a current recovery barrier and the separate complete live-arming chain are positively satisfied.

### SBR-INV-002 — Restriction Before Observation

A recovery trigger closes or advances the barrier and suspends affected new-risk authority before recovery work can be treated as current.

### SBR-INV-003 — Readiness Is Not Authority

No Recovery Session, package, obligation result, readiness decision, operator action, health result, or replay result creates capacity, Live Authorization, capability, protective classification, broker transmission, or re-arm permission.

### SBR-INV-004 — One Current Recovery Generation

Only the current fenced Recovery Coordinator generation may publish a candidate decision; stale, minority, restored, duplicated, or resumed workers grant nothing. Current Recovery Generation and barrier state SHALL be established through an authenticated, fenced currentness mechanism within its approved maximum age. Cache TTL, process health, heartbeat, eventual delivery, or last-observed state cannot prove currentness; inability to actively establish current state at authority issuance or final egress is denial.

### SBR-INV-005 — Complete Economic Inventory

Recovery cannot be ready while any required order, attempt, fill, position, capacity, external, non-trade, protective, broker, or evidence dependency is omitted or unbounded.

### SBR-INV-006 — UNKNOWN Remains Conservative

Missing, conflicting, stale, or ambiguous state remains UNKNOWN, consumes conservative capacity, and blocks new risk in affected scope.

### SBR-INV-007 — No Snapshot Optimism

One broker query, flat position, cache agreement, absent page result, missing ACK, or cancel ACK cannot establish completeness, non-acceptance, Final Quantity Proof, or capacity release.

### SBR-INV-008 — Partial Scope Requires Proven Isolation

READY_RESTRICTED cannot exclude unresolved shared capacity, aggregate limits, broker sessions, credentials, routes, protective dependencies, or common failure domains.

### SBR-INV-009 — HALT Dominates Recovery

Recovery cannot clear, outrank, defer, or reinterpret HALT. Valid restrictive action remains available and ordinary recovery cannot cancel required existing protection.

### SBR-INV-010 — Recovery Cannot Mutate Capacity

The Recovery Coordinator may submit evidence-bound requests but only the RCL may mutate, quarantine, import, transfer, or release capacity.

### SBR-INV-011 — Material Change Invalidates

Any relevant state, evidence, generation, policy, configuration, identity, broker, route, credential, time, protection, or scope change invalidates the affected readiness decision before future authority issuance.

### SBR-INV-012 — Timeout Is Restrictive

Recovery timeout, owner loss, backpressure, dependency outage, or inability to converge leaves the barrier closed and never reduces the obligation set.

### SBR-INV-013 — Economic Effect Survives Recovery Lifecycle

Session completion, cancellation, timeout, failover, decision expiry, evidence expiry, or restore never expires orders, attempts, exposure, UNKNOWN, or capacity commitments.

### SBR-INV-014 — No Automatic Re-arm

Recovery completion, health restoration, human acknowledgement, replay match, or evidence repair never revives prior authority; fresh governed re-arm is mandatory.

---

## 7. Authority Ownership and Separation

| Function | Authority | Recovery Coordinator limitation |
|---|---|---|
| Close barrier / advance Recovery Generation | Safety Control Plane ordered recovery namespace | may request/assemble; cannot reopen live authority |
| Determine recovery scope and obligations | Recovery Coordinator under approved policy | unknown scope expands; cannot omit a blocking dependency |
| Reconcile per-field knowledge | Reconciliation Service | Recovery Coordinator consumes result; cannot declare evidence sufficient itself |
| Mutate/quarantine/release capacity | RCL only | may submit evidence-bound request only |
| Classify protective action | Protective Action Controller | recovery/operator label grants nothing |
| Cancel protective order | Cancellation Arbiter | ordinary cleanup cannot cancel required protection |
| Activate safety configuration | ADR-002-014 activation authorities | readiness records status only |
| Approve re-arm | ADR-002-015 effective human quorum | cannot self-approve or waive safety obligations |
| Issue Live Authorization | Live Authorization Service | requires fresh exact readiness but owns independent decision |
| Transmit to broker | Final Egress Trust Boundary | readiness is only a checked non-authorizing claim |
| Evidence custody/replay | ADR-002-016 services | cannot repair readiness by narrative or replay result |

The Recovery Coordinator SHALL NOT hold a usable live broker credential or route. Workflow, database, cloud, recovery, or identity administration SHALL NOT combine into live authority through common effective control.

---

## 8. Recovery Triggers and Scope Expansion

At minimum, the following trigger a new or advanced Recovery Generation for the affected dependency closure:

- cold start, warm restart, process suspension beyond bound, reconnect, failover, deployment, rollback, or restore;
- loss or change of Safety Authority, Writer Epoch, membership, Restore Generation, Live Authorization, currentness session, or egress generation;
- time degradation, continuity change, snapshot expiry, or source disagreement;
- RCL inconsistency, quorum loss, stale read, capacity conflict, or protective sub-ledger rejoin;
- UNKNOWN transmission, missing ACK, partial fill, late fill, cancellation/fill race, replacement gap, or broker correction;
- external/manual activity, corporate action, assignment, exercise, transfer, fee, financing, settlement, or reference-identity change;
- safety-profile, envelope, broker-profile, software, schema, deployment, identity, credential, route, session, endpoint, or failure-domain change;
- Evidence Gap, source continuity reset, fork, integrity failure, replay divergence, or evidence-key/store restore;
- protective coverage loss, ownership conflict, resource degradation, or Cancellation Arbiter ambiguity;
- human HALT, compromise, revoked approval, break-glass event, or Critical alert;
- any unclassified event whose maximum affected scope is not positively bounded.

Scope SHALL be computed from a versioned dependency graph. If an account shares aggregate capacity, broker session, credential, route, rate limit, margin, collateral, protective resource, authority domain, configuration, or failure domain with the trigger, the shared dependency is included unless isolation is positively proven. Unknown dependency mapping expands to the containing account or broader Safety Cell.

A trigger may narrow only after evidence proves the unaffected dependency closure. Operator selection, strategy ownership, organizational boundaries, or service labels are not isolation proof.

---

## 9. Barrier Activation and Final Enforcement

The Recovery Barrier state is:

```text
CLOSED_NON_LIVE
CLOSED_RECOVERY
CLOSED_CONTAINED
CLOSED_HALTED
```

These names describe new-risk denial context, not permission. No barrier state alone permits live transmission.

On trigger:

1. assign a unique trigger identity and conservative initial scope;
2. commit a newer Recovery Generation or apply a locally verifiable restrictive latch when the authoritative plane is unavailable;
3. suspend or revoke affected new-risk Live Authorization;
4. propagate the generation to every affected final egress within approved bounds;
5. preserve economic state, existing protection, UNKNOWN, and capacity;
6. start recovery only after the barrier is effective or the entire scope is hard-fenced.

Final egress SHALL reject any new-risk request when the current Recovery Generation cannot be positively verified, the request references an older generation, the barrier is closed, or readiness is absent/invalid. A readiness decision is never sufficient; egress still validates current authority, capacity, time, profile, broker, identity, route, evidence, and capability.

Final egress SHALL obtain current Recovery Generation, barrier state, and readiness invalidation status through the authenticated fenced currentness mechanism. A cache, TTL, heartbeat, service-health result, eventual-consistency assumption, or absence of an invalidation event is not currentness proof. If the complete current state cannot be positively established within the approved bound at the irreversible send boundary, the request is denied.

Restrictive Human HALT does not wait for recovery persistence. ADR-002-015 and ADR-002-016 emergency latch rules dominate.

---

## 10. Recovery Session State Machine

```text
TRIGGERED
  -> FENCING
  -> INVENTORYING
  -> RECONCILING
  -> VALIDATING
  -> DECISION_CANDIDATE
  -> READY | READY_RESTRICTED | NOT_READY

{TRIGGERED..DECISION_CANDIDATE} -> INVALIDATED | ABORTED | SUPERSEDED
{READY, READY_RESTRICTED}       -> INVALIDATED | EXPIRED | SUPERSEDED
```

Transitions SHALL be monotonic, append-only, authenticated, and bound to the current Recovery Generation. `ABORTED`, `INVALIDATED`, `EXPIRED`, `SUPERSEDED`, and `NOT_READY` cannot transition to a ready state. Retry creates a new session identity; a new trigger that affects the session advances or merges into a newer generation and supersedes the older candidate.

No session state opens the barrier or re-arms live operation. `READY` means only that the exact package met the approved recovery predicate at decision time.

---

## 11. Recovery Coordinator Fencing and Concurrency

Recovery coordination SHALL use an authenticated owner epoch or equivalent quorum-ordered fencing token bound to Recovery Generation, Safety Cell, Recovery Scope, deployment, workload identity, software, and policy generation.

- only one current owner may advance a session or publish a decision for overlapping scope;
- minority, stale, paused, restored, removed, or partitioned owners are rejected at recovery-state commit and by readiness consumers;
- leader election, database primary status, lock TTL, cache ownership, heartbeat health, or broker reachability alone is insufficient fencing;
- concurrent non-overlapping sessions are permitted only when their dependency closures and aggregate constraints are proven disjoint;
- overlapping triggers merge into the more restrictive generation and obligation union;
- owner failover preserves the committed session prefix and never marks in-progress work complete;
- an unavailable former owner remains potentially active until fenced at every decision consumer.

Recovery ownership ordering may use the ADR-002-012 Safety Commit Log mechanism class in a separate non-capacity namespace. This does not give the Recovery Coordinator capacity mutation or capability issuance authority.

---

## 12. Recovery Inventory Cut

The inventory SHALL bind:

- session, Recovery Generation, scope, trigger, policy, and dependency-graph digests;
- start/end trustworthy-time snapshots and uncertainty;
- RCL cluster, membership, Restore Generation, Writer Epoch, committed revision, state digest, and open allocations;
- Safety Authority epoch, currentness, HALT/revocation/restriction generations;
- intent, attempt, capability claim, `SEND_STARTED`, broker request, ACK, order, fill, cancel, replace, and Final Quantity Proof lineage;
- positions, balances, cash, margin, collateral, financing, fees, settlement, and broker session/account state;
- external/manual activity and all recognized non-trade event/correction versions;
- protective orders, obligations, ownership, leases, gaps, overlaps, and resource guarantees;
- envelope/profile activation, broker capability, software, schema, deployment, identity, credential, route, endpoint, and compatibility generations;
- source continuity, page/cursor/completeness, evidence confidence, gaps, anchors, and raw-record digests;
- ADR-002-018 Critical Input Policy, Context Generation, source registry/continuity, transformation lineage, Critical Input Snapshot, Decision Context Capsule, correction, common-mode, and invalidation state;
- every event observed between inventory start and end and its conservative application;
- unobserved-window assumptions, maximum adverse bounds, and required repeat observations.

Where an external source cannot provide an atomic snapshot, recovery SHALL use a bounded convergence protocol: take source observations, record all intervening events, re-read required fields, and repeat until field-specific proof rules reach a stable conservative result or the session becomes NOT_READY. Equality between two reads does not prove that an unobservable event did not occur.

Issuer and consumer monotonic clocks across continuity identities are never directly compared. A time-ambiguous cut remains non-permissive.

---

## 13. Recovery Obligation Graph

Each obligation SHALL contain:

- obligation identity, type, owner, scope, hazard, and priority;
- prerequisite obligations and authoritative sources;
- exact input/evidence digests and inventory-cut position;
- proof rule, conservative bound, and acceptable result classes;
- invalidation conditions and maximum age;
- failure, timeout, conflict, and missing-source response;
- resulting scope restriction and residual risk;
- evidence records and independent-review requirement.

The minimum obligation set includes:

1. stale writers, authorities, egress principals, credentials, sessions, routes, and recovery owners fenced;
2. current RCL committed prefix, capacity invariants, quarantine, and protective sub-ledgers reconciled;
3. all intents, attempts, orders, fills, cancels, replaces, positions, balances, margin, collateral, and corrections reconciled per field;
4. UNKNOWN, missing ACK, late-fill, cancellation, and Final Quantity Proof rules satisfied conservatively;
5. external/manual and non-trade activity attributed and applied through governed transitions;
6. protective coverage, ownership, replacement state, and reserved resource guarantees evaluated;
7. trustworthy time and ADR-002-018 Critical Input Policy, source continuity, Critical Input Snapshots, Decision Context Capsules, and correction/invalidation proven;
8. ADR-002-019 Venue Constraint Policy, Constraint Generation, Venue Constraint Snapshots, exact Order Admissibility Decisions, and current venue/session/tradability/account/margin/borrow/settlement/broker-capability state proven;
9. ADR-002-020 Order Construction Policy, Construction Generation, command/proof/effect schemas, compiler/serializer/SDK compatibility, invalidation, and conservative inventory of every existing command/proof state proven;
10. ADR-002-021 Aggregate Risk Policy/Generation, complete state-snapshot cut, Adverse Scenario Set, evaluator/verifier compatibility, invalidation, and conservative inventory of every existing risk decision/grant proven;
11. ADR-002-022 Action Flow Policy/Generation, complete state-snapshot cut, cause/amplification lineage, shared-scope budgets, outstanding permits/claims/queues/in-flight actions, protective reserves/leases, invalidation, and conservative inventory proven;
12. current Hard Safety Envelope, Runtime Safety Profile, Broker Capability Profile, Verification Profile, and compatibility state validated;
13. deployment, software, schema, identity, credential, route, endpoint, and failure-domain state current and non-bypassable;
14. evidence policy, source records, gaps, integrity anchors, retention, and replay divergence state acceptable;
15. Human HALT, break-glass, approval, compromise, incidents, alerts, and residual-risk obligations resolved or explicitly restrictive;
16. requested and maximum safe recovery scopes recomputed against all shared aggregate dependencies.

An obligation cannot be marked satisfied by its own proposing component where independent evidence is required. Missing or cyclic obligation dependencies make the session NOT_READY.

---

## 14. Reconciliation and Conservative Convergence

The Recovery Coordinator orchestrates but does not own per-field knowledge. ADR-002-006 Reconciliation Service results remain authoritative for confidence and conservative bounds.

Recovery convergence requires:

- every required field has a terminal confidence/result permitted by the policy;
- no unresolved conflict is hidden by aggregation or a blended score;
- all potentially-live quantities remain capacity-covered;
- broker corrections, late fills, query omissions, pagination, external activity, and non-trade transitions are within evidenced bounds;
- capacity release uses RCL transitions and applicable Final Quantity Proof, never recovery status;
- position, open-order, attempt, capacity, and protection views are mutually consistent under the worst credible economic union;
- events after the inventory cut either invalidate the package or are included through a newer cut;
- continuous monitors have not produced a later invalidation trigger.

If convergence cannot be proven within `B_startup_reconciliation`, the bound is an operational target and escalation trigger, not permission. The barrier stays closed. Repeated identical unknown observations do not convert UNKNOWN into known state.

---

## 15. Recovery Modes, HALT, and Protective Continuity

During `RECOVERY`, new risk is prohibited. Permitted activity is limited to:

- non-transmitting inventory, query, validation, evidence, and reconciliation;
- restrictive HALT, denial, and scope narrowing;
- cancellation only through the Cancellation Arbiter;
- separately authorized containment or protective action satisfying ADR-002-001, ADR-002-003, ADR-002-011, RCL capacity, current time, broker capability, ownership, and final-egress rules.

Recovery priority is not reserved protective capacity. A healthy broker connection or emergency credential is not protective permission. Existing safety-owned protection SHALL NOT be cancelled for cleanup, session reset, deployment convenience, or to obtain a clean snapshot.

HALT dominates every recovery state and decision. Recovery cannot downgrade `HALTED` to `RECOVERY`, clear a local deny latch, or schedule an automatic transition. Where HALT application is ambiguous, treat it as applied until reconciled under fresh governance.

---

## 16. Recovery Readiness Decision

The decision SHALL bind:

- decision identity, canonical digest, issuer, Recovery Session, generation, policy, scope, and requested re-arm scope;
- Recovery Evidence Package and Inventory Cut digests;
- complete obligation-set digest and every result;
- READY, READY_RESTRICTED, or NOT_READY;
- maximum safe scope and explicit excluded scopes;
- all UNKNOWN, external, non-trade, protective, capacity, broker, time, configuration, identity, evidence, incident, and residual-risk state;
- issue trustworthy-time snapshot, maximum age, expiry, and invalidation conditions;
- RCL, authority, HALT, profile, broker, deployment, egress, evidence, and human-policy generation vector;
- explicit statements that it creates no capacity, Live Authorization, capability, broker permission, protective classification, or re-arm.

`READY` requires all obligations for the exact requested scope to pass with no blocking Critical hazard.

`READY_RESTRICTED` requires the safe subset to be positively isolated and every excluded dependency to remain new-risk denied. It is not a weaker proof level for included scope.

`NOT_READY` records failure and conservative scope. It cannot be manually promoted; a new session and evidence package are required.

---

## 17. Partial Recovery and Shared Dependencies

Partial readiness SHALL be denied unless all of the following are proven:

- distinct RCL Capacity Domains or conservative aggregate allocation prevent cross-scope headroom reuse;
- broker sessions, credentials, routes, rate limits, and account-level semantics cannot let unresolved scope affect the candidate;
- margin, collateral, cash, settlement, financing, concentration, and portfolio risk remain safe under the unresolved maximum;
- no protective order, lease, resource, Cancellation Arbiter decision, or replacement workflow crosses the boundary;
- configuration, authority, time, evidence, deployment, identity, and failure-domain dependencies are compatible and current;
- external/manual and non-trade activity cannot map into the candidate scope;
- final egress can enforce the exact restricted scope and current Recovery Generation;
- the Hard Safety Envelope remains satisfied under the union of resolved and unresolved effects.

Logical strategy separation, different UI labels, separate recovery tickets, distinct process instances, or unused nominal capacity do not prove isolation. If a shared dependency cannot be bounded, the broader scope remains NOT_READY.

---

## 18. Continuous Invalidation and Readiness Expiry

A decision is invalidated by any material change to:

- trigger set, Recovery Scope, dependency graph, obligation graph, policy, or inventory cut;
- RCL revision, capacity state, writer/membership/restore generation, UNKNOWN, quarantine, or protective allocation;
- broker order, fill, cancel, correction, position, balance, margin, collateral, session, capability, or external activity;
- non-trade event, reference identity, settlement, assignment, exercise, transfer, fee, or financing state;
- Safety Authority, HALT, revocation, time, profile, authorization, currentness, egress, credential, route, deployment, software, schema, or identity generation;
- protection, ownership, gap, overlap, resource guarantee, venue, tradability, or account usability;
- evidence confidence, source continuity, gap, integrity, anchor, policy, replay, incident, alert, approval, or residual risk.

Invalidation advances or closes the barrier for affected scope before a later Live Authorization may be issued. A consumer cannot continue using a cached readiness decision beyond `MAX_recovery_readiness_age` or after a newer generation is observed. Expiry is restrictive and does not affect economic lifetime.

---

## 19. Failure, Abort, Retry, and Recovery of Recovery

| Condition | Required response |
|---|---|
| Recovery Coordinator crashes or pauses | barrier remains closed; fence owner; resume from committed prefix or start new session |
| Two owners publish decisions | reject both unless one current fenced winner is proven; contain and investigate |
| Trigger arrives during validation | advance/merge generation; invalidate candidate; union obligations |
| Broker query omits an order | preserve UNKNOWN/potentially-live capacity; inspect completeness and alternate evidence |
| Cancellation acknowledged without FQP | no release and no ready new-risk scope affected by remaining quantity |
| Inventory observations never converge | NOT_READY; escalate; no timeout fallback |
| Account looks flat but attempts/evidence are incomplete | NOT_READY; preserve maximum adverse union |
| Evidence Gap affects recovery | expand/contain scope; package cannot be READY until policy proof is satisfied |
| Recovery policy or software changes mid-session | invalidate; start new generation/package as required |
| Former instance cannot be reached for fencing | treat potentially active; deny overlapping readiness/live authority |
| Operator requests forced ready | reject; operator may HALT or request governed containment only |
| Recovery session is deleted or expires | economic state persists; barrier remains closed; start new session |

Retry is a new attributable attempt under the same current generation only when inputs and obligation graph are unchanged. Material change requires a new generation or session. Retry never resets elapsed uncertainty, replenishes protective capacity, releases UNKNOWN, or reuses prior approval.

---

## 20. Restore and Disaster Recovery

Disaster restore SHALL begin `CLOSED_RECOVERY` with broker transmission denied and shall:

1. create new cluster, restore, recovery-owner, evidence-store, and deployment continuity generations as applicable;
2. inventory and fence every prior writer, Safety Authority, currentness session, Live Authorization, capability, egress principal, credential, route, broker session, and recovery owner;
3. preserve every surviving snapshot, log branch, receipt, anchor, broker history, protective sub-ledger, and conflicting account observation;
4. select no branch by recency label, backup success, administrator choice, or wall-clock timestamp alone;
5. compute the worst credible union of economic effects and capacity consumption;
6. reconcile broker/account, external, non-trade, protection, configuration, and evidence state;
7. issue a new readiness decision only from the new Recovery Generation;
8. require fresh governed re-arm after readiness.

An older backup may be recovery input but cannot become authority merely because it is available. Missing acknowledged commits, unverifiable fencing, or unresolved conflicting history keeps the affected scope non-live.

---

## 21. Human Governance and Re-arm Handoff

Human principals may:

- invoke HALT;
- approve scope narrowing;
- acknowledge incidents or residual risk through the governed policy;
- request separately authorized containment;
- approve a later exact re-arm request under ADR-002-015.

They SHALL NOT:

- mark obligations satisfied without their proof rule;
- select a convenient broker or internal source as truth;
- waive UNKNOWN into new-risk permission;
- mutate/release RCL capacity;
- clear HALT or stale fencing through recovery UI;
- convert READY or READY_RESTRICTED into Live Authorization;
- direct-transmit a recovery order;
- reuse a prior Approval Set, Live Authorization, capability, or readiness decision.

Handoff order is:

```text
current Recovery Readiness Decision
  -> exact new Re-arm Approval Request
  -> effective-human quorum and single-use Approval Set
  -> new Live Authorization
  -> new per-action capability
  -> final egress enforcement
```

Each step validates the current Recovery Generation and complete generation vector. Failure or invalidation at any step returns the affected scope to non-live; no automatic continuation is permitted.

---

## 22. Evidence, Metrics, and Alerts

ADR-002-016 governs custody and replay. Recovery evidence SHALL include:

- trigger, scope expansion, Recovery Generation, barrier commit, egress receipt, and invalidation lineage;
- owner election/fencing, competing-owner rejection, failover, pause, and restore evidence;
- session transitions and complete obligation graph/results;
- inventory-cut start/end, authoritative revisions, source continuity, query pages/cursors, intervening events, and uncertainty;
- raw and normalized broker/account, external, non-trade, protective, capacity, authority, configuration, identity, and evidence inputs;
- every UNKNOWN, conflict, conservative bound, residual risk, denial, retry, timeout, and escalation;
- package and decision canonical bytes, digests, signatures, consumers, expiry, and later invalidation;
- re-arm handoff and proof that no old artifact was reused.

Metrics SHALL include barrier-close latency, trigger-to-egress denial, owner-fence latency, inventory and convergence duration, source age/skew, obligation completion and invalidation counts, UNKNOWN quantities, shared-dependency scope expansion, competing-owner rejection, readiness age, post-decision invalidations, and recovery-to-re-arm duration.

Critical alerts include barrier bypass, stale recovery decision accepted, missing obligation, scope under-expansion, concurrent owner, optimistic snapshot, recovery-driven capacity release, protection cancellation, readiness used as authorization, timeout fallback, restore branch loss, or automatic re-arm.

Evidence, metrics, replay, tickets, and dashboards never substitute for the barrier or final enforcement.

---

## 23. Rejected Alternatives

### 23.1 Service Health Equals Recovery

Rejected because healthy processes can hold stale, incomplete, or contradictory economic state.

### 23.2 One Broker Snapshot Is Authoritative

Rejected because pagination, eventual consistency, corrections, session scope, and concurrent events can omit risk.

### 23.3 Flat Position Means Safe Resume

Rejected because open orders, late fills, UNKNOWN attempts, external activity, protection, and capacity may remain.

### 23.4 Timeout Opens the Barrier

Rejected because availability pressure cannot convert unresolved state into permission.

### 23.5 Recovery Coordinator Releases Capacity

Rejected because only the RCL owns capacity mutation and proof-gated release.

### 23.6 Operator Force-Ready

Rejected because human authority cannot waive Critical state, evidence, capacity, time, broker, or egress rules.

### 23.7 Per-Strategy Recovery by Default

Rejected because strategies commonly share account capacity, margin, broker resources, protection, and failure domains.

### 23.8 Last-Write-Wins Recovery

Rejected because stale, minority, restored, and conflicting histories may each contain real economic effects.

### 23.9 Recovery Completion Reuses Old Authorization

Rejected because readiness is not authority and recovery cannot revive expired or revoked artifacts.

### 23.10 Audit or Replay Proves Prevention

Rejected because reconstruction cannot retroactively make a permissive start or broker effect safe.

---

## 24. Consequences

### 24.1 Positive

- Startup and recovery use one explicit fail-closed barrier rather than distributed health guesses.
- Stale and concurrent recovery workers cannot publish usable readiness.
- Inventory covers economic, capacity, protection, authority, configuration, identity, and evidence state together.
- Non-atomic broker observations are handled through conservative bounded convergence.
- Partial recovery cannot escape shared aggregate dependencies.
- Readiness remains separate from human approval, Live Authorization, capacity, and egress.
- Every material change invalidates stale recovery conclusions.

### 24.2 Negative

- Recovery is slower and may require repeated broker/source observations.
- Shared accounts and common broker resources often force broad recovery scope.
- Strict owner fencing and generation propagation add control-plane complexity.
- Incomplete broker semantics or evidence may keep an otherwise healthy system non-live.
- Durable obligation graphs, inventory cuts, packages, and invalidation monitoring add storage and operational cost.

These costs are accepted. They SHALL be bounded and engineered, not traded for optimistic readiness.

---

## 25. Acceptance Cases

The following cases are mandatory and map one-to-one to `SBR-EV-001` through `SBR-EV-012`. Written cases are not completed evidence.

| Acceptance case | Required result |
|---|---|
| `SBR-AC-001` | Cold start, warm restart, reconnect, failover, restore, and incident recovery begin with the barrier closed and no new-risk first byte before a complete fresh live-arming chain |
| `SBR-AC-002` | A trigger advances the Recovery Generation and reaches every affected final egress before stale readiness or capability can create new risk |
| `SBR-AC-003` | Concurrent, stale, paused, minority, restored, and broker-reachable recovery owners cannot publish an accepted readiness decision |
| `SBR-AC-004` | Inventory includes every required economic, capacity, protection, authority, configuration, identity, broker, external, non-trade, and evidence dependency; omission creates NOT_READY |
| `SBR-AC-005` | Non-atomic broker queries, pagination, corrections, intervening fills/cancels, missing ACK, and cancel ACK cannot create optimistic convergence or capacity release |
| `SBR-AC-006` | UNKNOWN, conflict, stale evidence, unbounded cut, and Evidence Gap remain conservative, capacity-consuming, and new-risk blocking through timeout and retry |
| `SBR-AC-007` | READY_RESTRICTED includes only a positively isolated dependency closure and cannot reuse shared capacity, margin, broker resources, protection, authority, or failure domains |
| `SBR-AC-008` | HALT dominates all recovery states; evidence/journal failure does not block restriction, and recovery does not blindly cancel existing required protection |
| `SBR-AC-009` | Every material post-cut or post-decision change invalidates the affected readiness before authority issuance or egress acceptance |
| `SBR-AC-010` | Restore and conflicting histories preserve all branches, fence predecessors, cover the worst credible economic union, and remain non-live |
| `SBR-AC-011` | Recovery Coordinator, operator, evidence, and replay paths cannot mutate/release capacity, issue Live Authorization, classify protection, transmit, clear HALT, or force ready |
| `SBR-AC-012` | Recovery completion, health restoration, evidence repair, replay match, and human acknowledgement cannot reuse old artifacts or automatically re-arm |

---

## 26. Requirements Traceability

| Requirement | ADR-002-017 allocation |
|---|---|
| SAFE-003, SAFE-004, SAFE-050 | Recovery validates exact current safety configuration but cannot activate or expand it (§§13, 16, 18) |
| SAFE-010, SAFE-011, SAFE-013, SAFE-015 | Barrier and readiness cannot bypass limits or mutate RCL capacity (§§7, 9, 14) |
| SAFE-020, SAFE-021 | Intent, attempt, claim, send, retry, and ambiguity are fully inventoried and never collapsed (§§12–14) |
| SAFE-022, SAFE-023, SAFE-024, SAFE-025 | Reconciliation, source conflict, external activity, partial fill, missing ACK, cancellation, and FQP stay conservative (§§12–14) |
| SAFE-030 through SAFE-035 | Critical Inputs, provenance, broker/venue usability, decision context, and trustworthy time are explicit recovery obligations (§§12–13) |
| SAFE-040, SAFE-043 | Recovery preserves protective ownership and routes cancellation/containment through their authorities (§15) |
| SAFE-041, SAFE-042, SAFE-048 | Barrier fencing, current authority, partition behavior, and Human HALT remain restrictive and non-revivable (§§9, 11, 15) |
| SAFE-044 | Closed startup, complete obligations, readiness, invalidation, and fresh handoff implement Safe Start and Resume (§§8–21) |
| SAFE-045, SAFE-046, SAFE-047 | Environment/deployment identity and fresh exact live arming remain separate from recovery (§§7, 16, 21) |
| SAFE-051, SAFE-052 | Recovery triggers, cuts, obligations, decisions, failures, and handoff are immutable and replayable without becoming authority (§22) |

---

## 27. Open Implementation Questions

Open questions reduce authority or keep scope non-live. They do not weaken the rules above.

1. Which Recovery Barrier Policy schema, dependency graph, trigger classifier, and obligation registry are approved?
2. Which ADR-002-012 ordered namespace, owner-epoch mechanism, quorum topology, and Commit Proof fence Recovery Generations and competing coordinators?
3. How does every Live Authorization issuer and ADR-002-013 final egress obtain current Recovery Generation without a permissive cache?
4. Which broker query/event/page/cursor protocols implement conservative Inventory Cuts for the first account and broker scopes?
5. Which account, Capacity Domain, Safety Cell, session, credential, route, margin, protection, and failure-domain dependencies permit partial recovery?
6. Which source-independent corroboration and repeat-observation rules establish convergence for each required field?
7. Which RCL commands accept evidence-bound quarantine, import, and release requests without giving recovery capacity authority?
8. Which durable workflow engine, package signer, schema registry, evidence path, and notification mechanism are conforming?
9. Which Human Authority Policy roles review residual risks and later re-arm without becoming recovery proof owners?
10. How are barrier close, local deny latch, HALT, evidence emergency journal, and hard egress fence composed under control-plane loss?
11. What disaster-recovery procedure proves predecessor writer, egress, broker-session, credential, and recovery-owner fencing?
12. What values for `B_recovery_trigger_to_barrier`, `B_recovery_barrier_to_egress`, `B_startup_reconciliation`, `MAX_recovery_readiness_age`, source freshness, convergence, and invalidation bounds are approved?
13. Which ADR-002-018 Critical Input Policy, source-continuity, Snapshot/Capsule, correction, common-mode, and invalidation obligations must be current before recovery readiness for each scope?

---

## 28. Approval Gate

ADR-002-017 SHALL remain **Proposed** until all of the following are complete:

1. Recovery Barrier Policy, Recovery Session, Recovery Inventory Cut, Recovery Obligation, Recovery Evidence Package, and Recovery Readiness Decision schemas and canonicalization are approved;
2. trigger classification and dependency-closure rules cover every account, capacity, broker, protection, authority, configuration, identity, evidence, and failure-domain dependency;
3. Recovery Generation, owner epoch, barrier commit, stale-owner fencing, and final-egress rejection are implemented through a reviewed ordered substrate;
4. broker/source Inventory Cut, page/cursor completeness, correction, convergence, and field-specific proof mechanisms are implemented and broker-evidenced;
5. the complete obligation graph and continuous invalidation paths are implemented without giving Recovery Coordinator economic authority;
6. READY_RESTRICTED isolation is proven against shared capacity, aggregate risk, margin, broker, protection, identity, route, and failure domains;
7. HALT, protective continuity, cancellation arbitration, evidence failure, timeout, retry, owner failover, and disaster restore are independently security- and safety-reviewed;
8. ADR-002-007/015 fresh re-arm and ADR-002-013 final egress enforce exact current readiness without treating it as permission;
9. ADR-002-016 evidence custody, gap detection, integrity, retention, and replay isolation are implemented for recovery artifacts;
10. `SBR-EV-001` through `SBR-EV-012` and applicable cross-ADR evidence pass at required levels and receive independent review;
11. ADR-002-018 Critical Input Policy, source continuity, Snapshot/Capsule, common-mode, correction/invalidation, and non-revival are complete recovery obligations and applicable CII evidence passes;
12. ADR-002-019 Venue Constraint Policy, Constraint Generation, exact Snapshot/Decision, current venue/session/tradability/account/broker state, restrictive invalidation, and non-revival are complete recovery obligations and applicable VTG evidence passes;
13. ADR-002-020 construction policy/generation, deterministic compiler/verifier, exact command/proof/effect binding, invalidation, downstream mutation, recovery inventory, and non-revival are complete recovery obligations and applicable IOC evidence passes;
14. ADR-002-021 risk policy/generation, state consistency cut, scenarios, vectors, evaluator/verifier, exact decision/RCL binding, invalidation, recovery inventory, and non-revival are complete recovery obligations and applicable ARE evidence passes;
15. ADR-002-022 action-flow policy/generation, state consistency cut, cause/amplification lineage, exact decision/vector/RCL permit binding, protective reserve, invalidation, recovery inventory, and non-revival are complete recovery obligations and applicable AFG evidence passes;
16. recovery trigger, barrier, egress, inventory, convergence, Critical Input, venue-constraint, conformance, aggregate-risk, and action-flow invalidation, context/decision/command/proof/permit/snapshot-age, readiness-age, time, evidence, and broker bounds are approved and measured;
17. no unresolved stale-owner, partial-scope, forced-ready, optimistic-snapshot, restore, stale-context/constraint/conformance/risk/flow-decision, capacity-release, permit-reuse, HALT, egress, or automatic re-arm path remains;
18. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Until those gates pass, this ADR authorizes architecture and implementation-planning work only. It does not claim verification completion, ADR acceptance, restricted-live readiness, production readiness, or live trading authority.
