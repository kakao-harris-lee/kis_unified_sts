# ADR-002-012 — Risk Capacity Ledger Persistence, Consensus, and Writer Fencing

- **Status:** Proposed
- **Date:** 2026-07-13
- **Version:** 0.2
- **Last Updated:** 2026-07-17
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Authoritative Risk Capacity Ledger persistence, replicated-state-machine consensus, durable commit, writer epochs, stale-writer fencing, capability-order coupling, egress claim ordering, quorum loss, membership change, snapshot/restore, and disaster recovery
- **Supersedes:** None
- **Refines:** RFC-002 §10.5, §14, §16.5, §24, and §28 open decisions 1–3; ADR-002-002 §§8, 20, 21, 26, 35, and 39; ADR-002-003 authority-epoch enforcement; ADR-002-007 §§9.1–9.5; ADR-002-009 §§6.2–6.4 and §8.1
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-021, SAFE-024, SAFE-041, SAFE-048, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-011

---

## 1. Decision

Each Risk Capacity Ledger Capacity Domain SHALL be implemented as a **quorum-replicated deterministic Safety Commit Log** and state machine.

For a deployment designed to tolerate `f` crash or omission failures under a non-Byzantine replica model, the voting configuration SHALL contain at least `2f + 1` voters. A capacity-affecting transition is committed only after a quorum has durably accepted one identical ordered command. A leader, process, node, database primary, lock holder, or signed message is not authoritative before quorum commit.

This `2f + 1` rule does not claim Byzantine fault tolerance. If voter compromise, equivocation, storage falsification, or correlated administrative takeover is credible within the approved threat model, the deployment SHALL either use an independently reviewed Byzantine-tolerant mechanism with sufficient replicas and quorum rules or classify that condition as an uncontained common mode and prohibit live authority for the affected scope. Authentication alone does not convert crash-fault consensus into Byzantine consensus.

The Safety Commit Log SHALL provide one committed order for:

1. Risk Capacity Ledger mutations;
2. writer-epoch activation and fencing;
3. normal Transmission Capability authorization and invalidation ordering;
4. durable capability claim and `SEND_STARTED` transition before broker transmission;
5. membership, restore-generation, and safety-profile generation changes that affect authority.

The Risk Capacity Ledger state machine remains the sole capacity mutation and serialization authority. Sharing the consensus substrate with authority-currentness ordering does not grant the Safety Authority, Currentness Sequencer, consensus leader, or infrastructure administrator the right to mutate capacity.

ADR-002-024 defines the complete currentness namespace carried by or transactionally coupled to this log. Ordering a Safety Currentness Vector, Restrictive Fence Record, or Egress Currentness Proof does not add an RCL mutation path or business authority.

When quorum or current committed-prefix proof is unavailable, no new normal capacity mutation, normal capability authorization, capability claim, or normal broker transmission is permitted. Existing reservations, potentially-live attempts, UNKNOWN exposure, trapped exposure, and economic effect remain capacity-consuming. Only an already issued, exclusive degraded protective lease may operate under ADR-002-001, ADR-002-002, and ADR-002-003.

Quorum restoration, leader election, node restart, snapshot restore, or membership recovery SHALL NOT automatically re-arm live operation or revive a prior capability.

---

## 2. Context

ADR-002-002 requires a linearizable Ledger, a single logical writer, monotonic fencing, compare-and-set transitions, and egress validation. ADR-002-003 requires current epochs at every authority-enlarging enforcement point. ADR-002-007 selects a fenced single-use capability protocol but leaves its linearizable substrate open. ADR-002-009 prohibits treating a cache lifetime, event retry, or ordinary leader belief as currentness.

Those rules cannot be implemented safely by selecting a database and then assuming its primary is authoritative. Failure sequences include:

- two nodes both accepting writes after a partition;
- a paused former leader resuming with valid credentials;
- an asynchronous replica being promoted before acknowledged commits arrive;
- a capability being issued against a reservation that was never durably committed;
- a broker send beginning after local validation but before durable capability claim;
- a snapshot or backup restoring an older permissive epoch;
- two disjoint operator groups each forcing a new cluster;
- membership replacement temporarily creating overlapping quorums;
- a stale read being used to release capacity or authorize transmission;
- loss of acknowledgement for a committed Ledger command causing duplicate application;
- quorum recovery being mistaken for economic reconciliation or live re-arm.

A deterministic, quorum-committed state machine makes the prevention boundary explicit and testable. It sacrifices permissive availability when exclusivity cannot be proved.

---

## 3. Decision Drivers

1. No concurrent double-spending of aggregate capacity.
2. No acknowledged capacity transition may disappear after failover or restore.
3. A stale writer may remain alive but cannot mutate capacity or create an egress-accepted capability.
4. Capability issuance and send claim must be ordered after the exact capacity commitment they consume.
5. Quorum loss must reduce authority rather than create a second writer.
6. UNKNOWN and potentially-live economic effect must survive infrastructure recovery.
7. Membership and disaster recovery must not create overlapping authoritative histories.
8. The mechanism must be product-independent but precise enough for conformance testing.
9. Evidence and replay must reconstruct prevention without becoming the prevention mechanism.

---

## 4. Scope and Non-Scope

This ADR decides:

- the required consensus and durability class;
- the authoritative command ordering and commit rule;
- writer activation and fencing semantics;
- the coupling between capacity commitment, capability authorization, and egress claim;
- linearizable read requirements;
- quorum-loss and partition behavior;
- membership-change safety;
- snapshot, compaction, backup, restore, and disaster-recovery rules;
- acceptance cases and evidence obligations.

This ADR does not select:

- a consensus product or database vendor;
- a cloud, region, container, or orchestration platform;
- numeric latency, election, or recovery bounds;
- the risk-vector mathematics defined by ADR-002-002;
- Safety Authority policy defined by ADR-002-003;
- degraded protective classification or broker-specific proof rules;
- a production topology before its Failure-Domain Allocation Matrix is approved.

Any product or topology may conform only by demonstrating the semantics in this ADR under its actual failure model.

---

## 5. Definitions

### 5.1 Capacity Domain

The smallest scope whose capacity can be mutated without sharing any aggregate limit, protective pool, reservation, or potentially-live economic effect with another independently committed scope.

If two scopes share any enforceable aggregate envelope, they belong to one Capacity Domain unless a proven distributed transaction serializes their shared constraint.

### 5.2 Safety Commit Log

The quorum-replicated, totally ordered log whose committed prefix is the only input allowed to advance the authoritative RCL and currentness-ordering state machines.

### 5.3 RCL State Machine

The deterministic transition function that applies committed Ledger commands, validates invariants, and exclusively creates or changes capacity state.

### 5.4 Commit Proof

Consumer-verifiable evidence binding a command result to the current cluster identity, restore generation, membership generation, writer epoch, log revision, command identity, and committed state digest.

A leader signature or local success response alone is not Commit Proof.

### 5.5 Writer Epoch

A monotonically increasing RCL generation activated by a committed command. It fences state-changing commands from every earlier writer generation.

Consensus term, process generation, and Writer Epoch MAY be related but SHALL NOT be treated as equivalent unless the implementation proves the mapping survives membership change, restore, and failover.

### 5.6 Log Revision

The immutable position of a committed command in the Safety Commit Log. A revision is an ordering identity, not a wall-clock time.

### 5.7 Restore Generation

A monotonically advancing identity created whenever authoritative state is reconstructed from snapshot, backup, or disaster-recovery media. Old capabilities and currentness sessions cannot cross a Restore Generation.

### 5.8 Quorum Currentness

Proof that a consumer's accepted committed prefix and generations remain within the approved currentness bounds of the presently authoritative quorum configuration.

---

## 6. Safety Invariants

### RCLP-INV-001 — Sole Capacity Authority

Only the deterministic RCL State Machine may create, reserve, commit, transfer, quarantine, remap, resize, or release capacity.

### RCLP-INV-002 — No Quorum, No Normal Mutation

No normal capacity-affecting transition is committed without durable quorum acceptance.

### RCLP-INV-003 — One Committed Order

Every committed capacity mutation, normal capability authorization, invalidation, capability claim, and `SEND_STARTED` transition for one Capacity Domain has one total order.

### RCLP-INV-004 — Stale Writer Cannot Mutate or Authorize

A command carrying an earlier Writer Epoch, membership generation, Restore Generation, or stale expected revision cannot mutate RCL state or support an egress-accepted normal capability.

### RCLP-INV-005 — Committed Prefix Does Not Regress

No failover, snapshot, compaction, restore, or disaster-recovery operation may make an acknowledged committed transition disappear from authoritative history.

### RCLP-INV-006 — Command Idempotency

One command identity produces at most one authoritative transition and one stable result. Retrying a lost response cannot apply the transition twice.

### RCLP-INV-007 — Permissive Reads Are Linearizable

Any read used to create or enlarge authority, release capacity, validate current capacity, or authorize transmission reflects a linearizable committed prefix. Stale reads may support display only.

### RCLP-INV-008 — Quorum Loss Preserves Economic Effect

Quorum loss cannot release, expire, discount, or forget committed, potentially-live, UNKNOWN, external, trapped, replacement-overlap, or protective consumption.

### RCLP-INV-009 — Snapshot Completeness

A snapshot used for authoritative recovery preserves all non-terminal allocations, command-idempotency records, generation fences, capability-use records, proof-gated release state, and sufficient history commitments to detect rollback or omission.

### RCLP-INV-010 — Membership Cannot Fork Authority

Membership change cannot create two configurations capable of committing conflicting authoritative prefixes for the same Capacity Domain.

### RCLP-INV-011 — Restore Cannot Revive Authority

Restore creates a new Restore Generation, defaults to non-live, invalidates prior normal capabilities and currentness sessions, and requires reconciliation plus governed re-arm.

### RCLP-INV-012 — Documentation Is Not Consensus

Audit logs, event streams, projections, replay, runbooks, and human declarations cannot establish commit, currentness, capacity release, or writer fencing.

---

## 7. Capacity-Domain Boundaries and Sharding

Every aggregate limit SHALL have exactly one authoritative serialization boundary.

A Capacity Domain SHALL include every account, portfolio, strategy, instrument, currency, venue, protective pool, and external quarantine that can consume one shared limit. Independent shards are permitted only when their capacity envelopes are disjoint and cannot later be recombined to exceed a parent constraint.

Cross-domain actions require one of:

1. a single Capacity Domain covering the complete action;
2. a proven serializable distributed transaction whose failure semantics satisfy this ADR; or
3. independent conservative commitment of the full credible adverse effect in each affected domain without double-use of headroom.

Best-effort compensation after independent commits is not atomic capacity control. Unknown domain overlap SHALL merge the affected scope into one conservative domain or block new risk.

---

## 8. Consensus and Durable Commit

### 8.1 Voting Configuration

A crash/omission failure tolerance claim of `f` requires at least `2f + 1` voting members distributed according to the approved Failure-Domain Allocation Matrix. A Byzantine-failure claim requires a separately approved replica and quorum model; it SHALL NOT reuse the crash-fault claim.

Two voters do not tolerate one voter failure while preserving quorum. A witness counts only for the state and failure semantics it actually durably participates in.

### 8.2 Commit Rule

A command is committed only when:

1. it has one immutable command identity and canonical encoding;
2. the current leader proposes it under the active membership and Writer Epoch;
3. a quorum durably records the same ordered entry;
4. the deterministic state machine validates the command against the preceding committed state;
5. the resulting transition and state digest are bound to the committed revision.

The client SHALL NOT receive a successful authoritative result before this rule is satisfied.

### 8.3 Leader Is Not Authority

Leadership permits proposal and coordination. It does not permit unilateral commit, capacity mutation, capability authorization, membership change, or proof issuance.

A minority-side leader SHALL fail closed even if it remains alive, retains keys, serves stale reads, or can reach the broker network.

### 8.4 Linearizable Reads

Permissive reads SHALL use a quorum-confirmed read, read-index protocol, committed no-op barrier, or equivalent linearizable mechanism. A time-based leader lease is acceptable only if its clock, suspension, overlap, and failover assumptions are explicitly proven and it cannot outlive current authority.

Follower, cache, snapshot, analytics, and asynchronous projection reads SHALL be labelled non-authoritative and rejected for permissive decisions.

### 8.5 Consensus Ordering Does Not Depend on Wall Clock

Log order, command idempotency, Writer Epoch, and commit validity SHALL NOT depend on synchronized wall clocks. Trustworthy time remains required for artifact validity, evidence, bounded currentness, and degraded protective leases under ADR-002-008.

---

## 9. Command Envelope and Determinism

Every authoritative command SHALL bind at least:

- command identity and canonical schema version;
- Capacity Domain and cluster identity;
- expected Writer Epoch, membership generation, and Restore Generation;
- expected reservation, allocation, or domain revision where applicable;
- authenticated actor identity and permitted command role;
- causation, intent, attempt, reservation, evidence, and profile identities as applicable;
- requested deterministic transition;
- trustworthy-time evidence where the transition depends on validity or freshness.

The state machine SHALL reject:

- unknown or non-canonical fields that affect meaning;
- stale generations or revisions;
- duplicate identity with different content;
- unauthorized command type;
- non-deterministic external lookup during transition application;
- missing proof for a less-conservative transition;
- any result violating ADR-002-002 invariants.

Randomness, local clocks, network responses, environment defaults, and unordered collections SHALL NOT change replicated transition results.

---

## 10. State-Machine and Authority Separation

The shared Safety Commit Log MAY host multiple deterministic namespaces, but authority remains separated:

- the RCL State Machine alone applies capacity mutations;
- the Safety Authority and Currentness Sequencer may submit authenticated capability-authorization or restrictive-generation commands but cannot mutate capacity;
- the Egress Gateway may claim an authorized capability and mark send start but cannot invent capacity or scope;
- Reconciliation and Recovery may submit evidence-bound transition requests but cannot force release;
- consensus administration may manage nodes only through governed membership commands and cannot create trading authority.

A composite command that orders capacity and authority facts atomically SHALL validate every independently authorized input. Co-location in one log SHALL NOT collapse separation of duties.

At minimum, the state machine SHALL provide semantics equivalent to:

```text
ActivateWriterEpoch
CommitReservation
ResizeReservation
BindAttempt
AuthorizeTransmissionCapability
InvalidateCapabilities
ClaimCapabilityAndMarkSendStarted
RecordFillAndTransferUsage
QuarantineUnknown
ApplyFinalQuantityProof
ReleaseReservation
CommitProtectivePool
IssueProtectiveLease
ReconcileProtectiveLease
AdvanceRestoreGeneration
ChangeMembership
```

---

## 11. Capacity-to-Capability Ordering

Normal capability authorization SHALL reference an already committed reservation revision and exact adverse-effect bound.

The Currentness Sequencer SHALL submit `AuthorizeTransmissionCapability` through the same Safety Commit Log after the RCL State Machine proves:

- the reservation exists and is active;
- the attempt identity is bound and unused;
- the capacity vector covers the exact worst-case effect;
- Writer Epoch, Safety Authority epoch, Live Authorization, profiles, Restore Generation, Recovery Generation, and membership generation are current;
- no dominating restriction or UNKNOWN condition blocks the action.

The committed authorization record SHALL bind the capability identity, nonce, reservation revision, commit revision, state digest, generation vector, issuer identity, and Egress Gateway identity.

An uncommitted, minority-issued, stale-generation, or capacity-unbound capability is invalid even if cryptographically signed.

---

## 12. Fenced Egress Claim and Send Boundary

Before the first broker-directed byte of a normal risk-relevant action, the Egress Gateway SHALL submit `ClaimCapabilityAndMarkSendStarted` and obtain Commit Proof together with the ADR-002-024 single-use Egress Currentness Proof over the complete action-scoped vector and restrictive floors.

The committed transition SHALL atomically:

1. prove the capability is current, in scope, and unused;
2. consume its nonce exactly once;
3. transition the reservation to `POTENTIALLY_LIVE` or the applicable conservative state;
4. record `SEND_STARTED`, broker-request identity, exact economic effect, generation vector, and Egress Gateway identity;
5. make every later duplicate claim return the original committed result without creating another send authority.

The Egress Gateway SHALL revalidate the Commit Proof against its current ADR-002-007 session and ADR-002-024 local restrictive latch, then begin broker transmission within `B_capability_claim_to_send`. The session, cache, or a prior proof cannot replace the new per-send ordered proof.

If quorum commit, Commit Proof, currentness, evidence durability, or claim-to-send ordering is unavailable or ambiguous, no new send is permitted. A crash or ambiguity after the committed claim remains potentially live and capacity-covered. Missing broker ACK is not proof of non-acceptance, and authority expiry does not expire economic effect.

---

## 13. Writer Activation and Fencing

A newly elected leader cannot mutate the RCL until `ActivateWriterEpoch` is committed under the current membership and Restore Generation.

Every subsequent state-changing command SHALL carry that Writer Epoch. The deterministic state machine rejects every earlier epoch synchronously. The Currentness Sequencer and Egress Gateway reject capability authorization or claim not bound to the current committed Writer Epoch.

Writer fencing therefore has three mandatory layers:

1. **consensus fencing** — a minority or former leader cannot commit;
2. **state-machine fencing** — stale epoch or revision is rejected by the RCL transition;
3. **egress fencing** — stale or uncommitted capacity authority cannot produce a usable broker send.

Voluntary shutdown, orchestration state, heartbeat loss, process identity, or a leader lock without all three layers is insufficient.

---

## 14. Membership Change

Membership change SHALL use joint consensus or an equivalent protocol that proves an authoritative overlap between the old and new voter configurations.

The change SHALL be represented in the Safety Commit Log and advance the membership generation. During change:

- commands remain ordered through one committed prefix;
- a node cannot be added and used as authoritative before required state catch-up and identity validation;
- a removed node cannot vote, issue Commit Proof, activate a writer, or support capability currentness under the new generation;
- multiple voters SHALL NOT be replaced simultaneously when that can create an unverified quorum;
- forced reconfiguration requires the disaster-recovery procedure and cannot preserve live authority.

Infrastructure availability pressure does not justify creating a second cluster identity or accepting conflicting histories.

---

## 15. Partition and Quorum-Loss Behavior

When a partition divides voters, only a side holding the current quorum may commit. Every other side is non-authoritative regardless of former leadership, last observed health, or broker reachability.

When no side can prove quorum:

```text
New normal capacity mutation: DENIED
Normal capability authorization: DENIED
Normal capability claim: DENIED
Normal broker transmission: DENIED
Capacity release: DENIED
Membership change: DENIED except governed disaster recovery
Automatic re-arm: DENIED
```

Committed reservations and economic effects remain. Read-only projections may continue only when labelled stale and cannot drive permissive decisions.

Already claimed attempts remain potentially live. Degraded protective behavior is permitted only under an exclusive pre-committed protective lease and durable sub-ledger satisfying ADR-002-001 through ADR-002-003. Quorum loss does not create or replenish protective capacity.

---

## 16. Protective Sub-Ledger Boundary

The central Safety Commit Log SHALL commit the parent protective pool, lease identity, capacity vector, owner epoch, scope, and maximum holdover before partition.

The protective sub-ledger is a separate bounded state machine only for consumption already removed from normal headroom. It SHALL NOT:

- create or enlarge parent capacity;
- recycle potentially-live consumption from timeout or expiry;
- overlap another owner for the same lease scope;
- issue normal-risk capability;
- treat rejoin as proof that offline effects did not occur.

On rejoin, central reassignment remains frozen until sub-ledger history, broker evidence, fills, positions, UNKNOWN attempts, and remaining capacity are reconciled. Import is an explicit conservative RCL transition, not a last-write-wins merge.

---

## 17. Snapshot, Compaction, Backup, and Restore

### 17.1 Snapshot

An authoritative snapshot SHALL bind:

- cluster identity, Capacity Domain, membership generation, Restore Generation, Writer Epoch, and last included revision;
- complete RCL state and aggregate invariant inputs;
- non-terminal reservations, attempts, capability authorizations, claims, and send-start records;
- command-idempotency keys and conflicting-duplicate evidence;
- protective pools, leases, sub-ledger import state, UNKNOWN, external, trapped, and replacement allocations;
- profile and Hard Safety Envelope generations;
- a digest or equivalent integrity commitment to the included state and retained log prefix.

### 17.2 Compaction

Compaction MAY remove replay detail only when retained snapshot and log material preserve deterministic recovery, idempotency, fencing, economic-effect lineage, and required evidence retention. Tombstones and consumed capability identities SHALL outlive every credible retry, replay, and economic-effect horizon.

### 17.3 Backup

A backup is recovery material, not a live authority source. Backup success cannot prove current Ledger health or release capacity.

### 17.4 Restore

Restore SHALL:

1. start non-live with broker transmission denied;
2. establish a new cluster identity or new Restore Generation under governed recovery;
3. fence all prior writers, capabilities, currentness sessions, and egress identities;
4. verify snapshot and log integrity and detect missing acknowledged commits;
5. preserve or conservatively reconstruct every potentially-live and UNKNOWN effect;
6. reconcile broker/account state and protective sub-ledgers;
7. require explicit re-arm under ADR-002-007.

A restored older snapshot SHALL NOT become authoritative merely because it is the newest available backup.

---

## 18. Disaster Recovery and Conflicting History

Disaster recovery is permitted only when the existing quorum cannot be recovered within the approved operational policy. It is an authority-reducing recovery workflow, not an availability shortcut.

Before a replacement cluster may authorize normal risk, it SHALL establish:

- the former cluster cannot commit or reach accepted egress;
- all available voter, snapshot, backup, evidence, and broker histories have been inventoried;
- the highest provable committed prefix is selected without discarding a conflicting acknowledged transition;
- unresolved divergence is represented as conservative UNKNOWN and capacity quarantine;
- a new cluster identity, membership generation, Restore Generation, Writer Epoch, and Live Authorization are issued;
- the full Recovery Coordinator and human re-arm gates pass.

If two histories both plausibly contain economic effects, capacity SHALL cover the worst credible union without double-counting states proven mutually exclusive. Documentation or operator preference cannot choose the more permissive branch. The "worst credible union" ranges over the Credible State Space (RFC-002 §3.1.17): the union of reconstructable histories admitted by the active Broker Capability Profile (ADR-002-004) and the approved Adverse Scenario Set (ADR-002-021); a history state not bounded by these is treated conservatively as UNKNOWN and capacity-consuming, never dropped.

---

## 19. Projections, Events, Evidence, and Replay

The Safety Commit Log is the preventive ordering source. Event streams, change-data capture, caches, analytics databases, dashboards, and evidence stores are downstream projections.

Projection lag, duplication, reordering, omission, or replay SHALL NOT:

- create permission;
- release or remap capacity;
- establish current Writer Epoch;
- prove Final Quantity Proof;
- authorize broker transmission;
- clear a deny latch or re-arm.

Every committed transition and rejection SHALL emit evidence containing command identity, previous and resulting revision, generation vector, state digest, actor, causation, proof inputs, and rejection reason. Evidence loss fails closed where required but evidence replication does not substitute for quorum commit.

Independent replay SHALL reproduce the same deterministic state from the same committed prefix or identify corruption and remain non-live.

---

## 20. Security and Administrative Authority

Consensus-node identity, client command identity, Commit Proof, membership administration, snapshot signing, and restore authorization SHALL be authenticated and environment-scoped.

The following authorities SHALL remain separated:

- capacity policy grant;
- RCL command submission;
- Safety Authority capability decision;
- Egress Gateway claim and broker transmission;
- consensus membership administration;
- backup/restore administration;
- live re-arm approval.

An infrastructure administrator SHALL NOT gain trading authority by controlling a node, snapshot, DNS name, load balancer, or deployment manifest. Membership and disaster-recovery changes require governed multi-party approval and immutable evidence.

Compromise or uncertainty affecting quorum identity, Commit Proof integrity, membership, or snapshot provenance causes containment and credential/epoch rotation. Recovery does not automatically restore live authority.

---

## 21. Failure Modes and Required Responses

| Failure | Required response |
|---|---|
| Two leaders in one membership | only quorum-committed prefix is authoritative; minority leader cannot mutate or authorize |
| Former leader resumes | stale Writer Epoch and membership generation rejected by log, RCL, Currentness Sequencer, and egress |
| Quorum lost while broker remains reachable | deny normal capability authorization, claim, and send; preserve all economic effects |
| Commit response lost | retry same command identity; return same committed result without duplicate transition |
| Leader crashes after proposal before quorum | command is uncommitted and grants no authority; retry resolves through command identity |
| Leader crashes after quorum before response | committed transition survives; retry returns its result |
| Capability issued without committed capacity reference | reject capability and raise Critical security alert |
| Crash after committed send claim | remain potentially live; no capability reuse or blind retry |
| Stale follower or cache read | display-only; reject for mutation, release, authorization, or egress |
| Snapshot missing idempotency or capability-use state | reject snapshot for authoritative restore |
| Restore from older prefix | new Restore Generation, non-live, reconcile and quarantine missing effects |
| Conflicting disaster-recovery histories | cover worst credible union; remain non-live until governed resolution |
| Membership change loses overlap proof | stop reconfiguration and normal mutations; do not force permissive continuation |
| Event or audit projection unavailable | no new permission; authoritative state remains the committed log |
| Quorum recovers | remain at prior restrictive state; run recovery and explicit re-arm |

---

## 22. Rejected Alternatives

### 22.1 Asynchronous Primary and Replica Promotion

Rejected because an acknowledged capacity transition may be absent from the promoted replica.

### 22.2 Leader Election or Distributed Lock Without Fencing

Rejected because a former holder may remain alive and broker-reachable.

### 22.3 Single Database Transaction Without Quorum Failure Semantics

Rejected as an availability profile for failover claims. A single-node deployment may remain non-live or use manual hard-fenced recovery, but it cannot claim replicated failover safety.

### 22.4 Separate Capacity and Capability Datastores With Eventual Coupling

Rejected because capability may be issued against uncommitted, rolled-back, or stale capacity.

### 22.5 Cache or Event Stream as Current Authority

Rejected because expiry, eviction, delay, omission, duplication, and replay cannot prove exclusive commitment.

### 22.6 Time-Based Writer Lease Alone

Rejected because clock fault, suspension, and overlap may leave two writers or preserve stale permission.

### 22.7 Forced Promotion That Discards an Unavailable Voter

Rejected for live continuation unless governed disaster recovery proves fencing and conservatively accounts for missing history.

### 22.8 Restore Then Replay Best-Effort Events

Rejected because omitted or reordered events can erase capacity and economic effect.

### 22.9 Operator Selection of the “Most Likely” History

Rejected because probability or convenience is not proof that another history produced no economic effect.

---

## 23. Consequences

### 23.1 Positive

- exclusive capacity commitment has one testable prevention boundary;
- stale writers cannot commit even when alive;
- capability issuance and egress claim cannot outrun committed capacity;
- acknowledged state survives leader failover;
- currentness, restore, and membership generations are explicit;
- quorum loss is safely asymmetric toward denial;
- snapshot and disaster-recovery paths cannot silently revive authority;
- deterministic replay and fault evidence become possible.

### 23.2 Negative

- normal live availability is lost without quorum;
- every normal send claim incurs consensus-path latency;
- membership and restore operations are operationally heavy;
- Capacity Domains cannot be freely sharded across shared aggregate limits;
- conservative disaster recovery may quarantine substantial capacity;
- the consensus substrate becomes a safety-critical common mode requiring strong operational controls.

These costs are accepted because permissive availability and latency are subordinate to capital preservation and exclusive economic authority.

---

## 24. Acceptance Cases

The following cases are mandatory and map one-to-one to `RCLP-EV-001` through `RCLP-EV-012`. Written cases are not completed evidence.

| ID | Required demonstration |
|---|---|
| `RCLP-AC-001` | Concurrent requests that jointly exceed capacity produce at most one committed admissible result under quorum ordering |
| `RCLP-AC-002` | A minority-side leader with broker reachability cannot mutate RCL state, authorize capability, claim send, or produce accepted Commit Proof |
| `RCLP-AC-003` | A paused stale writer resuming after Writer Epoch advancement is rejected at consensus, RCL, currentness, and egress boundaries |
| `RCLP-AC-004` | Quorum loss blocks normal mutation and transmission while preserving committed, potentially-live, UNKNOWN, trapped, and protective capacity |
| `RCLP-AC-005` | Lost responses and crashes before and after quorum commit remain idempotent and never duplicate or erase a transition |
| `RCLP-AC-006` | Capability authorization cannot commit without the exact current capacity revision and generation vector |
| `RCLP-AC-007` | Capability claim and `SEND_STARTED` commit exactly once before send; crash and bound overrun preserve conservative UNKNOWN capacity |
| `RCLP-AC-008` | Stale follower, cache, snapshot, and projection reads cannot release capacity or create permissive authority |
| `RCLP-AC-009` | Joint membership change and voter replacement preserve one committed history and fence removed voters |
| `RCLP-AC-010` | Snapshot, compaction, backup, and restore preserve idempotency, generations, non-terminal economic state, and rollback detection |
| `RCLP-AC-011` | Protective sub-ledger partition and rejoin cannot enlarge, recycle, overlap, or last-write-wins merge parent capacity |
| `RCLP-AC-012` | Disaster recovery and conflicting history remain non-live, cover the worst credible economic union, and require new generations plus explicit re-arm |

---

## 25. Evidence and Metrics

The implementation SHALL retain enough evidence to reconstruct:

- voter and failure-domain membership by generation;
- leader terms and committed Writer Epoch activation;
- proposal, durable quorum acceptance, commit, application, and client-result ordering;
- command idempotency and conflicting-duplicate rejection;
- state digests and invariant results by revision;
- capability authorization, invalidation, claim, and `SEND_STARTED` ordering;
- linearizable-read proofs and rejected stale reads;
- quorum-loss detection and egress denial;
- membership changes and removed-voter fencing;
- snapshot, compaction, backup, restore, and integrity validation;
- protective sub-ledger import and reconciliation;
- disaster-recovery approvals, history selection, quarantine, and re-arm denial.

Required metrics include quorum availability, commit latency, applied revision lag, current Writer Epoch, current membership and Restore Generations, stale-command rejections, duplicate-command conflicts, stale-read rejection, uncommitted capability attempts, capability-claim latency, snapshot age and verification state, restore events, and invariant violations.

Metrics and audit support detection. They do not substitute for quorum commit, state-machine validation, or egress fencing.

---

## 26. Requirements Traceability

| Requirement | ADR-002-012 allocation |
|---|---|
| SAFE-010, SAFE-013 | One quorum-committed aggregate capacity order and exact capacity-to-capability binding (§§6–12) |
| SAFE-011 | Policy, capacity, consensus administration, and egress authorities remain separated (§10, §20) |
| SAFE-015 | RCL is the sole capacity mutation and serialization authority (§1, §6, §10) |
| SAFE-021, SAFE-024 | Send ambiguity, UNKNOWN, idempotency, and proof-gated release survive failover and restore (§§12, 15, 17–18) |
| SAFE-041, SAFE-048 | Writer epochs, quorum currentness, partitions, and stale-writer fencing fail closed (§§8, 13–15) |
| SAFE-051, SAFE-052 | Committed transition evidence and deterministic replay are retained without replacing prevention (§19, §25) |

---

## 27. Open Implementation Questions

The mechanism class is selected. The following product and deployment choices remain open while Proposed:

1. Which replicated-state-machine product and storage engine meet the deterministic quorum and durability contract?
2. What `f`, voter count, zone/region allocation, and Capacity Domain boundaries are approved for the first deployment profile?
3. Which ADR-002-013 Quorum Commit Certificate format, trust bundle, exact egress principal, and authenticated currentness transport are used by the Egress Gateway?
4. How are RCL and Currentness Sequencer namespaces transactionally composed without collapsing separation of duties?
5. Which ADR-002-014 deterministic command schema, namespace, semantic digest, and compatibility rules order Profile Generation activation during mixed-version deployment?
6. What snapshot interval, compaction horizon, idempotency retention, and evidence-retention period are approved?
7. What joint-consensus or equivalent membership-change protocol is provided by the selected product?
8. Which ADR-002-013 Hard Egress Fence proves an unavailable former cluster or removed voter cannot reach accepted egress?
9. What recovery media and procedure prove the highest committed prefix after a multi-site failure?
10. What local durable state machine implements degraded protective sub-ledger consumption?
11. Which numeric commit, currentness, claim-to-send, failure-detection, and recovery bounds are approved?
12. How are consensus, membership, snapshot, and restore administration protected by multi-party control?
13. Which ADR-002-015 Approval Set identity, request digest, policy/graph generation, and single-use consumption command are ordered without giving approval services RCL, Live Authorization, or egress authority?
14. Which ordered namespace and Commit Proof bind ADR-002-017 Recovery Generations, barrier commits, owner epochs, stale-owner rejection, and readiness invalidation without giving the Recovery Coordinator capacity authority?
15. Which ADR-002-016 pre-effect receipt, source sequence, integrity anchor, gap detector, retention, and Replay Capsule mechanisms preserve the committed log history without becoming capacity authority?

Unresolved questions reduce availability or keep the scope non-live. They SHALL NOT weaken any invariant.

---

## 28. Approval Gate

ADR-002-012 SHALL remain **Proposed** until all of the following are complete:

1. the Capacity Domain and failure-tolerance model are approved;
2. the replicated-state-machine product, durable commit configuration, and deterministic transition implementation are selected and reviewed;
3. Writer Epoch, membership generation, Restore Generation, Commit Proof, and stale-read rejection are implemented at every required boundary;
4. capability authorization and `ClaimCapabilityAndMarkSendStarted` share the committed ordering required by §§11–12;
5. no alternate capacity mutation or live broker path bypasses the RCL and Egress Gateway;
6. the applicable ADR-002-013 Quorum Commit Certificate validation, exact egress-principal binding, credential/route confinement, and Hard Egress Fence are implemented and their required EGRESS evidence passes;
7. the applicable ADR-002-014 Profile Generation, Activation Record, stale-base rejection, and restore non-revival ordering are implemented and their required SPG evidence passes;
8. the applicable ADR-002-015 Approval Set consumption, stale/replayed approval rejection, Human HALT ordering, and authority separation are implemented and their required HAG evidence passes;
9. ADR-002-016 immutable committed-transition evidence, causal completeness, fork/gap detection, retention, and isolated replay are implemented and their required ERI evidence passes;
10. membership change, quorum loss, snapshot, restore, and disaster-recovery procedures are implemented and security-reviewed;
11. ADR-002-017 Recovery Generation, barrier commit, competing-owner fence, worst-credible restore union, and non-authorizing readiness handoff are implemented on the reviewed ordered substrate and applicable SBR evidence passes;
12. `RCLP-EV-001` through `RCLP-EV-012` are registered, executed at their required levels, retained, and independently reviewed;
13. applicable RC, SA, REARM, FD, and cross-system evidence passes;
14. numeric bounds and the Failure-Domain Allocation Matrix are approved;
15. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Authorship and document review do not satisfy these conditions. This ADR does not authorize acceptance, restricted-live operation, production operation, or automatic re-arm.

---

## 29. Review History

### v0.1 — Initial Proposed Decision (2026-07-13)

Initial Risk Capacity Ledger persistence, quorum-consensus, writer-fencing, and disaster-recovery decision.

### v0.2 — Credible State Space Binding (CORPUS-REVIEW-0001 Wave 7) (2026-07-17)

- **M-24.** Bound the §18 disaster-recovery "worst credible union" to the Credible State Space (RFC-002 §3.1.17): the union ranges over the reconstructable histories admitted by the active Broker Capability Profile (ADR-002-004) and the approved Adverse Scenario Set (ADR-002-021), with any unbounded history state treated conservatively as UNKNOWN and capacity-consuming.
- Received a Version field and this Review History on first patch, per the ADR-002-011/025/026/027 precedent. The change is narrow-only and additive; it introduces no SAFE-xxx requirement, no numeric bound, and no new EV ID (Evidence Register count unchanged at 372). Independent EV-L0 review is owed, with reviewer provenance recorded per VER-002-001 §5 (M-18).
