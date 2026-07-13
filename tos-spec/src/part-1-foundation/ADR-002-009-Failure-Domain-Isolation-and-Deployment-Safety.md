# ADR-002-009 — Failure-Domain Isolation and Deployment Safety

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Failure-domain allocation, common-mode analysis, safety-cell boundaries, control-plane and egress isolation, deployment fencing, credential and data-plane separation, blast-radius containment, recovery, and evidence
- **Supersedes:** None
- **Amends:** RFC-002 §24 Deployment and Isolation Requirements and the failure-domain prerequisites in §15.5, §16, §17, §21, and §23
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-003, SAFE-004, SAFE-011, SAFE-013, SAFE-015, SAFE-021, SAFE-022, SAFE-024, SAFE-030, SAFE-031, SAFE-035, SAFE-041, SAFE-044, SAFE-045, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-008

---

## 1. Decision

The Trading Operating System SHALL treat failure-domain independence as an evidence-backed property of authority, state, identity, network, deployment, and broker paths. Separate processes, services, containers, nodes, or names do not by themselves prove isolation.

Every live deployment SHALL maintain a versioned **Failure-Domain Allocation Matrix** that identifies, for each safety-critical authority and dependency:

1. the failure domains it occupies;
2. all shared and common-mode dependencies;
3. the safety consequence of loss, corruption, delay, partition, or stale survival;
4. the preventive enforcement point;
5. the containment and detection bounds;
6. the recovery and fencing mechanism;
7. the evidence required to support any isolation claim;
8. the residual blast radius.

No single failure or untrusted application identity may both create trading intent, grant or extend safety authority, mutate Risk Capacity Ledger state, and bypass the final Broker Adapter/Egress Gateway enforcement point.

The Broker Adapter/Egress Gateway remains the final transmission enforcement point. The Risk Capacity Ledger remains the sole capacity mutation and serialization authority. Failure-domain isolation SHALL preserve both properties during normal operation, degraded operation, deployment, failover, partition, and recovery.

If an asserted isolation property cannot be positively established, the affected paths SHALL be classified as common-mode. The result SHALL reduce authority, consume conservative capacity where economic state is uncertain, and block new risk. It SHALL NOT be converted into permission by redundancy count, operator confidence, a healthy dashboard, replay capability, or an audit trail.

Deployment, rollback, restart, or service recovery SHALL NOT automatically re-arm live authority. Every newly active runtime identity requires current fencing, compatible configuration, current time health, and the re-arm controls in ADR-002-007.

---

## 2. Context

The safety architecture assigns different responsibilities to strategy code, the Safety Control Plane, the Risk Capacity Ledger, reconciliation, recovery, and final egress. Those logical assignments are meaningful only if a plausible failure cannot defeat all of them together.

Unsafe common modes include:

- strategy and safety services sharing one process or runtime failure;
- active and standby writers retaining credentials that permit concurrent mutation;
- a stale deployment using a valid broker credential after losing control-plane membership;
- the same cache, stream, database, or configuration distributor granting authority and reporting its own health;
- a network partition isolating revocation from egress while leaving broker transmission reachable;
- a shared clock failure making both authority and its checker believe an expired capability remains current;
- a deployment pipeline updating policy, capacity logic, and egress enforcement incompatibly;
- live and non-live environments sharing credentials, routes, accounts, or mutable configuration;
- an emergency control relying on the same dependency whose failure created the emergency;
- multiple services using one broker session, account limit, or rate limit while claiming independent protective capacity.

These conditions can remain hidden in normal-path testing. The architecture therefore requires explicit allocation, negative testing, hard fencing, and conservative classification of every shared dependency.

---

## 3. Decision Drivers

1. Safety authority must remain non-bypassable under partial failure and stale deployment.
2. Capacity serialization must not split across writers during failover or partition.
3. Restrictive transitions must reach final egress within approved bounds.
4. Live and non-live operation must not share a path that can create unintended live economic effect.
5. Common-mode dependencies must be disclosed rather than disguised as redundancy.
6. Recovery must not revive stale authority or clear unresolved economic effect.
7. Numeric containment bounds must be configuration-governed and independently approved.
8. Isolation claims must be reproducible through executed evidence, not architecture diagrams alone.

Availability is subordinate to these requirements.

---

## 4. Definitions

### 4.1 Failure Domain

A set of components that may fail, become stale, be corrupted, or become unreachable together because of one causal event.

Failure domains include process, runtime, node, zone, region, datastore, event infrastructure, cache, network path, broker session, account, credential, workload identity, deployment pipeline, clock, configuration distribution, parser, and shared risk library.

### 4.2 Common-Mode Dependency

A dependency whose failure can invalidate two or more controls that were otherwise being treated as independent.

Different endpoints, replicas, or service names backed by one administrator, credential, database, network, clock, library, or broker resource remain common-mode for that dependency.

### 4.3 Safety Cell

The smallest governed scope within which authority, capacity, egress, reconciliation, and containment consequences are intentionally coupled.

A Safety Cell SHALL have an explicit account, portfolio, broker, environment, authority-epoch, writer-epoch, and egress scope. A cell boundary is not proven merely by labels or namespaces.

### 4.4 Isolation Claim

A versioned claim that one failure cannot defeat specified controls together. Every claim SHALL state assumptions, excluded common modes, enforcement mechanisms, verification cases, and residual risk.

### 4.5 Hard Fence

An enforcement mechanism that prevents a stale or unauthorized identity from mutating safety state or transmitting to the broker even if the identity remains alive and network-connected.

Process convention, leader belief, a dashboard flag, or cooperative shutdown is not a hard fence.

### 4.6 Blast Radius

The maximum accounts, portfolios, instruments, strategies, capacities, credentials, and broker paths that one failure can affect before containment is authoritative.

---

## 5. Failure-Domain Allocation Matrix

The canonical matrix SHALL be versioned, reviewed with every topology or authority change, and bound to the Runtime Safety Profile and Live Authorization.

For each component and shared dependency it SHALL record at least:

| Field | Required content |
|---|---|
| Authority or state | Exact authority, capacity, knowledge, or economic state affected |
| Safety Cell | Account, portfolio, broker, environment, and egress scope |
| Failure domains | Process, node, zone, region, data, event, cache, network, broker, identity, deployment, time, library, and configuration domains |
| Shared dependencies | Every dependency shared with a purportedly independent control |
| Failure behavior | Crash, omission, delay, duplication, corruption, partition, stale survival, Byzantine input, or exhaustion |
| Unsafe consequence | Authority, capacity, quantity, protection, or transmission consequence |
| Prevention | Non-bypassable enforcement point and fence |
| Detection and containment | Observable signal and approved upper bound |
| Recovery | Required reconciliation, epoch change, and re-arm barrier |
| Evidence | Acceptance case and registered evidence identifier |
| Residual risk | Remaining common mode and approved owner |

Unknown, untested, or undocumented sharing SHALL be recorded as common-mode. It SHALL NOT be recorded as independent with an explanatory footnote.

The matrix SHALL cover at minimum the failure-domain categories listed in RFC-002 §24.1.

---

## 6. Mandatory Isolation Invariants

### 6.1 Strategy-to-Safety Isolation

Strategy, orchestration, UI, and ordinary operator identities SHALL NOT grant Live Authorization, mutate capacity, change writer or authority epochs, or bypass egress denial.

Their failure may reduce availability. It SHALL NOT disable the Safety Control Plane or convert denied transmission into allowed transmission.

### 6.2 Capacity Serialization Isolation

Only the Risk Capacity Ledger may create, reserve, commit, release, transfer, or remap capacity. All writers SHALL be hard-fenced by current writer epoch and scope.

Database replication, event replay, cache state, or a replacement process SHALL NOT infer release from silence, lease expiry, missing ACK, cancel ACK, or process death.

### 6.3 Final Egress Isolation

Only approved Broker Adapter/Egress Gateway identities SHALL possess a usable live transmission route. Every live transmission SHALL revalidate current authority, writer and authority epochs, time health, revocation generation, capability, capacity commitment, environment, account, broker session, and intent lineage at the final enforcement point.

No strategy, recovery tool, administrative shell, alternate adapter, or test environment may possess an ungoverned live route.

### 6.4 Restrictive-Path Dominance

HALT, revocation, epoch advancement, time degradation, capacity exhaustion, broker-capability withdrawal, and reconciliation degradation SHALL become authoritative at egress within approved containment bounds.

ADR-002-007 §§9.1–9.5 selects the fenced single-use capability protocol. This invariant remains an acceptance blocker until the protocol has an approved implementation substrate and numeric bounds, is the only usable live route, and has executed evidence. A cache lifetime, message retry, or eventual-consistency assumption is not an implementation of that protocol.

### 6.5 Environment Isolation

Live, restricted-live, simulation, replay, test, and development environments SHALL use distinct workload identities, broker credentials, routes, account allowlists, and configuration roots sufficient to prevent non-live execution from reaching a live broker account.

A shared secret with an environment label is not sufficient isolation.

### 6.6 Recovery Isolation

Recovery and reconciliation identities MAY gather evidence and propose state transitions. They SHALL NOT independently grant normal live authority, release unresolved capacity, or erase potentially-live quantity.

### 6.7 Evidence Independence

Audit, replay, documentation, and observability support detection and proof. They SHALL NOT substitute for preventive fencing. Loss of an evidence path SHALL reduce confidence and authority; it SHALL NOT make the system permissive.

---

## 7. Control-Plane and Data-Plane Placement

The Safety Control Plane, Risk Capacity Ledger, reconciliation path, Trustworthy Time Service, and final egress MAY share infrastructure only when the matrix explicitly analyzes the resulting common mode and the approved deployment profile accepts the reduced isolation claim.

The following rules always apply:

1. a failure of ordinary strategy compute cannot grant safety authority;
2. a stale Safety Control Plane instance cannot extend authority after its epoch is fenced;
3. a stale Risk Capacity Ledger writer cannot mutate capacity after writer-epoch change;
4. egress cannot rely only on a front-end or upstream allow decision;
5. the path that observes a restrictive state cannot be the only unverified source asserting delivery of that restriction;
6. loss of a required control-plane dependency causes denial of new risk at egress;
7. unresolved broker, order, or exposure state remains capacity-consuming through control-plane recovery.

Logical separation on one runtime or node SHALL be described as logical separation, not physical independence.

---

## 8. Data, Event, Cache, and Network Domains

### 8.1 Authoritative Data

Authoritative capacity and epoch state SHALL use storage and fencing semantics capable of preventing split-brain mutation. The chosen mechanism remains subject to RFC-002 §28 open decision 1.

Replica lag, failover, backup restore, or disaster recovery SHALL NOT move the system backward to an older permissive authority generation.

### 8.2 Event Infrastructure

Kafka, streams, queues, and event buses MAY distribute facts and restrictive updates. Receipt of an allow event is not continuing authority, and absence of a deny event is not proof of permission.

Consumer lag, replay, duplication, reordering, partition, or retention loss SHALL be included in containment analysis.

### 8.3 Cache Infrastructure

Redis or any other cache SHALL NOT be the sole source of current permission, revocation state, Final Quantity Proof, or capacity release.

Cache miss, expiration, eviction, restart, or stale replica read SHALL fail closed for permissive decisions.

### 8.4 Network Partitions

The matrix SHALL analyze partitions separately for:

- Safety Control Plane to egress;
- Risk Capacity Ledger to egress;
- Trustworthy Time Service to egress;
- reconciliation to broker and ledger;
- egress to broker;
- operator controls to safety services;
- primary to standby writer.

A partition that preserves broker reachability while removing revocation or capacity currentness is a high-severity unsafe path and SHALL be prevented or bounded by the selected currentness mechanism.

---

## 9. Identity, Credential, and Broker-Session Domains

Credentials SHALL be least-privilege, environment-scoped, account-scoped where supported, attributable to a workload identity, and revocable independently of ordinary application deployment.

The deployment SHALL inventory:

- every identity capable of live broker transmission;
- every identity capable of Safety Control Plane mutation;
- every Risk Capacity Ledger writer;
- every identity capable of epoch or configuration change;
- shared broker sessions, account limits, order-rate limits, and cancel capacity.

Credential rotation or workload replacement advances the applicable identity or authority generation. An old credential remaining cryptographically valid does not preserve its architectural authority.

Broker sessions, account limits, and rate limits shared by normal and protective traffic SHALL be classified as common-mode resources. Priority is not reserved protective capacity. Protective capacity may be claimed only where the Broker Capability Profile and executed evidence prove the reservation or isolation.

---

## 10. Deployment and Rollback Safety

Every safety-critical deployment SHALL use immutable artifact identity and bind at least:

- source revision and build provenance;
- artifact digest;
- schema and protocol compatibility;
- Safety Profile and Verification Profile versions;
- Broker Capability Profile version;
- risk-library and configuration-parser versions;
- workload and credential identities;
- authority and writer epochs;
- target environment and Safety Cell.

Deployment SHALL default the new runtime to non-live, denied transmission. Health checks, canary success, or process readiness SHALL NOT grant Live Authorization.

Mixed-version operation is permitted only where compatibility and safety dominance are explicitly proven. Otherwise the affected scope SHALL remain halted or non-live until one compatible generation is authoritative.

Rollback is a new deployment generation. It SHALL NOT reuse stale authority merely because the binary version was previously accepted.

An incomplete deployment, failed migration, partial configuration distribution, or unknown active instance SHALL invalidate normal live authority for the affected scope until fencing and reconciliation establish exclusivity.

### 10.1 Greenfield Egress and Credential Boundary

Every conforming TOS deployment SHALL implement the following boundary:

1. one approved Egress Gateway identity per declared Safety Cell holds the usable live order credential and broker-order network route;
2. strategy, orchestration, recovery, reconciliation, administrative, and market-data components hold no usable live order credential or direct broker-order route;
3. all broker submission, cancellation, and replacement operations exist only behind the Egress Gateway's fenced capability-claim and `SEND_STARTED` boundary;
4. market-data access uses separate non-ordering credentials and routes where the broker supports them; any broker-enforced inability to separate credentials is recorded as a common mode and mitigated by a non-bypassable order-route boundary;
5. operational flags, event streams, caches, and sentinels may trip a monotonic restrictive input but their absence, deletion, expiry, or recovery never establishes current permission or clears the deny latch;
6. cache or ordinary local application storage is not treated as the sole Risk Capacity Ledger, Currentness Sequencer, or authoritative fencing substrate without a separately approved mechanism and executed partition/failover evidence.

Until credential inventory, route confinement, bypass prevention, and fault testing prove this boundary, restricted-live and production gates remain `NO`.

---

## 11. Shared Libraries and Configuration Domains

A shared risk library, parser, schema, calendar, or policy bundle can defeat multiple services simultaneously. Such sharing SHALL be a named common mode in the matrix.

Configuration changes SHALL be atomic at the governed profile boundary. Partial, mixed, missing, or unverifiable configuration causes denial or scope reduction.

Configuration and code review reduce likelihood but do not create runtime independence. Executed fault evidence is required for acceptance.

---

## 12. Time Failure Domains

Time-source names, synchronization daemons, host clocks, hypervisors, network paths, timezone data, and calendars SHALL be allocated as explicit failure domains under ADR-002-008.

Two time sources using one upstream reference or network path are not independent. A common clock failure affecting both authority issuer and egress checker SHALL be analyzed as one common mode.

Loss of trusted time SHALL reduce authority. Restored time health SHALL create a new health generation and SHALL NOT revive prior authority.

---

## 13. Safety-Cell Blast-Radius Control

Every Safety Cell SHALL define:

- maximum economic exposure and capacity affected by one cell failure;
- broker accounts and sessions reachable by the cell;
- identities and credentials shared across cells;
- data and control dependencies shared across cells;
- whether a cell-level HALT can be enforced without a global dependency;
- conditions requiring escalation from cell HALT to global HALT.

If cells share an account, broker session, capacity pool, credential, ledger writer, or final egress process, that common mode SHALL be included in the aggregate blast radius.

Cell partitioning SHALL NOT allow aggregate limits to be exceeded by distributing reservations among cells. Aggregate capacity remains serialized by the Risk Capacity Ledger.

---

## 14. Failure Response

When an isolation assumption fails or becomes unknown, the system SHALL:

1. deny new risk for the affected aggregate scope;
2. preserve all committed and potentially consumed capacity;
3. fence stale writers, authority generations, and transmission identities where possible;
4. retain potentially-live order quantity and UNKNOWN economic state;
5. continue only safety-authorized recovery or protective action that has independent current authority and capacity;
6. escalate to the broader Safety Cell or global HALT when blast radius cannot be bounded;
7. require reconciliation and governed re-arm before normal authority returns.

Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. Lease or authority expiry does not expire economic effect.

---

## 15. Startup, Failover, and Recovery

Startup and failover SHALL establish, before any normal live authority:

- exclusive current writer and authority epochs;
- inventory and fencing of previous active identities;
- current immutable deployment and profile generations;
- Risk Capacity Ledger continuity;
- broker-session and account reconciliation;
- current trustworthy-time health;
- current egress revocation and capability generations;
- absence or conservative treatment of UNKNOWN orders and exposure;
- required evidence and operator approvals under ADR-002-007.

An unavailable old instance SHALL be treated as potentially active until a hard fence or an approved expiry fence proves otherwise. Process death, heartbeat loss, lease expiry, or orchestration replacement alone is insufficient.

Recovery from datastore rollback, region loss, or credential compromise SHALL advance generations and invalidate prior live authorization.

---

## 16. Observability and Evidence

The system SHALL retain enough evidence to reconstruct:

- the active Failure-Domain Allocation Matrix and profile versions;
- component, workload, credential, artifact, authority, and writer identities;
- topology and common-mode dependency changes;
- every restrictive-state propagation and egress decision;
- split-brain, partition, stale-instance, and mixed-version observations;
- broker-session and account-resource contention;
- containment start, completion, and measured bound;
- operator actions, approvals, and re-arm decisions;
- residual risks and exceptions.

Required metrics include at least:

- active writers and egress identities per Safety Cell;
- age and generation of authority, revocation, time-health, and capability proofs at egress;
- restrictive-update propagation latency;
- denied stale-epoch and stale-deployment transmissions;
- dependency-health unknown duration;
- unbounded or expanded blast-radius incidents;
- shared broker-resource exhaustion affecting protective action.

Documentation and written tests are not completed evidence. Acceptance requires registered, executed, retained, and independently reviewed evidence under VER-002-001.

---

## 17. Acceptance Cases

The following cases are mandatory and map one-to-one to `FD-EV-001` through `FD-EV-012`. Registration is not execution; every item remains incomplete until its required evidence is executed, retained, and independently reviewed:

| ID | Required demonstration |
|---|---|
| `FD-AC-001` | Strategy-runtime compromise or crash cannot grant authority, mutate capacity, or bypass egress |
| `FD-AC-002` | Simultaneous old and new deployments leave only one writer and one authorized egress generation effective |
| `FD-AC-003` | Control-plane-to-egress partition blocks new risk while broker reachability remains available |
| `FD-AC-004` | Cache loss, eviction, stale replica, and restart cannot create permission or release capacity |
| `FD-AC-005` | Event lag, loss, duplication, reordering, and replay cannot preserve revoked authority beyond the approved bound |
| `FD-AC-006` | Live and non-live credentials, routes, accounts, and workload identities cannot cross environments |
| `FD-AC-007` | Risk Capacity Ledger failover fences stale writers and preserves conservative commitments |
| `FD-AC-008` | Shared time-source or synchronization failure reduces authority at all affected egress paths |
| `FD-AC-009` | Partial deployment, mixed configuration, and rollback default to denied live transmission and require new authorization |
| `FD-AC-010` | Broker-session, account-limit, or rate-limit exhaustion exposes the declared protective common mode without claiming reserved capacity |
| `FD-AC-011` | Safety-Cell failure is contained within the declared aggregate blast radius or escalates to broader HALT |
| `FD-AC-012` | Region or datastore recovery does not revive stale authority, erase UNKNOWN state, or automatically re-arm |

---

## 18. Rejected Alternatives

### 18.1 “Different services are independent”

Rejected. They may share runtime, identity, data, network, time, deployment, or broker domains.

### 18.2 “High availability proves safety isolation”

Rejected. Availability redundancy can preserve the same unsafe authority or create split brain.

### 18.3 “The message bus will deliver every revocation”

Rejected. Delivery, freshness, ordering, and currentness require bounded enforcement at final egress.

### 18.4 “Cache expiry removes stale authority”

Rejected. Cache expiry is not an economic, authority, quantity, or capacity proof.

### 18.5 “Operator procedure is the emergency fence”

Rejected. Procedure is not a non-bypassable runtime mechanism.

### 18.6 “Priority guarantees protective access”

Rejected. Priority does not reserve broker capacity, session capacity, rate limit, or market liquidity.

### 18.7 “A healthy dashboard proves containment”

Rejected. Observability and replay do not substitute for prevention.

---

## 19. Consequences

### 19.1 Positive

- Isolation claims become explicit and testable.
- Stale deployment and split-brain paths are fenced at authority, capacity, and egress boundaries.
- Common broker, time, configuration, and identity dependencies remain visible.
- Deployment and recovery cannot silently restore live authority.
- Blast-radius statements become conservative and reviewable.

### 19.2 Negative

- Deployment profiles require more infrastructure and evidence metadata.
- Some apparently redundant topologies will be classified as common-mode.
- Uncertain dependency health will reduce availability.
- Restricted-live acceptance requires destructive fault testing in a controlled environment.

These costs are accepted because safety claims without failure-domain proof are unreliable.

---

## 20. Traceability

| Requirement | ADR coverage |
|---|---|
| SAFE-003, SAFE-004, SAFE-013 | Safety-cell and aggregate blast-radius control |
| SAFE-011 | Non-bypassable final egress and identity isolation |
| SAFE-015 | RCL-only mutation and writer fencing |
| SAFE-021, SAFE-022, SAFE-024 | Duplicate, recovery, reconciliation, and external-state containment |
| SAFE-030, SAFE-031, SAFE-035 | Profile, configuration, and time common modes |
| SAFE-041, SAFE-044 | Safety authority, startup, failover, and re-arm barriers |
| SAFE-045 | Live and non-live isolation |
| SAFE-048 | Partition behavior and restrictive-path dominance |
| SAFE-050 | Deployment and configuration fencing |
| SAFE-051, SAFE-052 | Executed evidence and reconstructable fault behavior |

---

## 21. Open Questions

1. Which conforming product, voter topology, Capacity Domain allocation, and hard-fence profile implement ADR-002-012 for each deployment profile?
2. Which conforming ADR-002-013 signer/credential, Active Egress Principal, order-route, Quorum Commit Certificate, and Hard Egress Fence topology will implement the selected ADR-002-007 §§9.1–9.5 protocol?
3. Which Safety Cell boundaries and deployment topology will be approved for the first restricted-live profile?
4. Which dependencies require physical separation, and which common modes will be explicitly accepted as residual risk?
5. How will region loss and broker-session continuity be tested without creating live economic effect?
6. Which numeric propagation, detection, containment, and recovery bounds will be approved in the Verification Profile?
7. Which ADR-002-014 consumers must attest to the exact bundle and compatibility generation in each Safety Cell before activation?
8. Which ADR-002-015 identity, approval, notification, and pre-provisioned Human HALT failure domains remain independent of strategy, ordinary control plane, and live arming?

Open questions may only reduce scope or block acceptance. They SHALL NOT weaken the invariants in this ADR.

---

## 22. Approval Gate

This ADR SHALL remain **Proposed** until all of the following are complete:

1. a concrete deployment profile and Failure-Domain Allocation Matrix are approved;
2. the applicable ADR-002-012 quorum, writer-fencing, membership, and recovery mechanisms are implemented and their required RCLP evidence passes;
3. the ADR-002-007 §§9.1–9.5 protocol and ADR-002-013 final-egress security boundary have an approved implementation substrate, isolated credential/route topology, Hard Egress Fence, executed EGRESS evidence, and numeric bounds;
4. ADR-002-014 exact-generation activation, Consumer Compatibility Manifest, mixed-version denial, and rollback fencing are implemented across the approved Failure-Domain Allocation Matrix, and applicable SPG evidence passes;
5. ADR-002-015 Human HALT, human identity, approval, effective-principal, and notification paths have approved failure-domain allocation and applicable HAG evidence passes;
6. ADR-002-016 ordinary evidence ingress/store, emergency journal, integrity anchor, archive, key custody, and replay runtime have explicit failure-domain allocation, gap containment, and applicable ERI evidence;
7. dedicated evidence items are registered for every `FD-AC-*` case;
8. required EV-L1, EV-L2, and EV-L3 fault evidence is executed and retained;
9. all isolation claims and residual common modes receive independent review;
10. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Authorship of this ADR does not satisfy these conditions and does not authorize restricted-live or production operation.
