# ADR-002-013 — Egress Gateway Credential, Route, and Commit-Proof Security

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Broker Egress Gateway trust boundary, usable live-order authority, credential custody, broker-order route confinement, Commit Proof validation, egress generation and principal fencing, request construction, downstream intermediaries, credential rotation, compromise containment, failover, degraded protective access, and security evidence
- **Supersedes:** None
- **Refines:** RFC-002 §9.1, §10.8, §24, §25, and §28 open decision 2; ADR-002-003 §§8.3, 11, and 18; ADR-002-004 §§18–19; ADR-002-007 §§9.1–9.5 and §16; ADR-002-009 §§6.3, 9, and 10.1; ADR-002-012 §§5.4, 12–14, and 20
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-010, SAFE-011, SAFE-014, SAFE-015, SAFE-021, SAFE-024, SAFE-033, SAFE-040, SAFE-041, SAFE-042, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-012

---

## 1. Decision

Every Safety Cell SHALL have exactly one logical **Broker Egress Authority** for each live broker credential and order-route scope. That authority MAY be implemented by multiple runtime components only when one committed Egress Generation and a finite, committed Active Egress Principal Set identify every principal allowed to participate. A service name, deployment label, shared secret, or network location is not an egress authority identity.

The **Final Egress Trust Boundary** is the last boundary that possesses both:

1. usable authority to make a broker accept an order-affecting request; and
2. a broker-order route capable of delivering that request.

Every live submission, cancellation, replacement, exercise, instruction, or other broker-order mutation SHALL pass through this boundary. Before the first broker-directed byte, the boundary SHALL validate the complete Transmission Capability, currentness session, monotonic deny latch, exact request, and a quorum-sufficient Commit Proof for the committed `ClaimCapabilityAndMarkSendStarted` transition required by ADR-002-012.

A downstream queue, proxy, sidecar, signer, session manager, or network appliance that can originate, modify, duplicate, delay beyond the approved bound, replay, re-route, or independently authenticate a broker-order request is part of the Final Egress Trust Boundary. If it cannot enforce the complete final gate, the topology is non-conforming.

No strategy, decision, execution-coordination, recovery, reconciliation, evidence, administrative, research, simulation, test, market-data, or general operator component may possess both usable live-order authority and a live broker-order route. A broker credential or route that remains usable outside the fenced Egress Generation is a Critical bypass even when every normal application call path uses the gateway.

Credential, route, workload, deployment, active-principal, Commit-Proof trust-bundle, broker-session, or endpoint-policy changes SHALL advance the applicable Egress Generation or bound sub-generation. A new generation SHALL NOT gain live authority until the prior path is hard-fenced or an approved expiry fence proves it incapable of broker acceptance. Recovery, reconnect, credential rotation, route restoration, or deployment health SHALL NOT automatically re-arm transmission.

---

## 2. Context

ADR-002-007 selects the fenced single-use capability and claim-to-send protocol. ADR-002-012 places capacity mutation, capability authorization, capability claim, and `SEND_STARTED` in one quorum-committed order. Those decisions still fail if an identity can bypass the checking component and reach the broker with another usable credential, session, signed request, or route.

Unsafe examples include:

- an old deployment retaining an API key after its Egress Generation is replaced;
- a strategy worker obtaining the same broker credential used by the gateway;
- a network proxy replaying an already claimed signed request;
- a session sidecar reconnecting and flushing queued requests after HALT;
- a test identity reaching a live order endpoint through shared DNS, proxy, or account routing;
- a leader receipt being accepted as Commit Proof without quorum acceptance;
- a valid proof from an old cluster, Restore Generation, membership, or writer epoch being replayed;
- credential rotation temporarily leaving old and new unfenced paths active;
- a failover gateway inheriting a service identity and live credential without fencing its predecessor;
- an operator using a broker portal or emergency credential as an undocumented alternate order path;
- an HSM or signing service signing arbitrary broker payloads without validating capability and claim state;
- a durable local journal being treated as equivalent to ADR-002-012 quorum commit.

The final gate is defined by effective economic authority, not by a component name. This ADR makes credential, route, proof, and failover semantics explicit and testable.

---

## 3. Decision Drivers

1. No live broker mutation may bypass the final safety gate.
2. Stale, removed, compromised, or non-live identities must be unable to create broker-accepted requests.
3. Commit Proof must establish quorum commitment, not leader belief or local persistence.
4. Capability, proof, payload, credential, route, session, and egress identity must be bound without substitution gaps.
5. Restrictive generations must dominate queued, delayed, reconnecting, or retried work.
6. Credential and route changes must reduce authority until hard fencing is proven.
7. Broker limitations must reduce live scope rather than weaken the boundary.
8. Protective operation must remain bounded without becoming an alternate normal-risk route.
9. Security evidence must demonstrate prevention without substituting for prevention.

---

## 4. Scope and Non-Scope

This ADR decides:

- the effective Final Egress Trust Boundary;
- the definition and custody rules for usable live-order authority;
- broker-order route confinement;
- Egress Generation and active-principal fencing;
- quorum-sufficient Commit Proof contents and validation semantics;
- exact request and endpoint binding;
- treatment of queues, proxies, sidecars, signers, and sessions;
- credential rotation, failover, compromise, and recovery behavior;
- degraded protective egress constraints;
- acceptance and evidence obligations.

This ADR does not select:

- a broker, cloud, HSM, secret manager, service mesh, firewall, or consensus product;
- a particular cryptographic algorithm or wire encoding;
- a production network topology;
- broker-specific revocation or session semantics;
- numeric fencing, propagation, session, or rotation bounds;
- a general organization-wide identity platform.

Any implementation may conform only if its actual credential, route, session, administrative, and broker failure semantics satisfy this ADR.

---

## 5. Definitions

### 5.1 Broker Egress Authority

The sole logical authority permitted to transform a quorum-claimed transmission attempt into a broker-directed order-affecting request for one declared Safety Cell and scope.

### 5.2 Final Egress Trust Boundary

The complete set of components from the last full safety validation through the irreversible broker-send boundary. Every component inside it that can create, mutate, replay, authenticate, or route an accepted request inherits the full safety obligations of the boundary.

### 5.3 Usable Live-Order Authority

Any secret, private key, token, certificate, session cookie, client handle, authenticated connection, delegated capability, pre-signed request, broker portal session, signing oracle, or equivalent artifact that can contribute to broker acceptance of an order-affecting request.

Encrypted storage alone does not make an artifact unusable when another accessible identity can decrypt, sign, or transmit with it.

### 5.4 Broker-Order Route

Any network, IPC, proxy, session, portal, signing, or broker-native path capable of delivering an order-affecting request to a live account. DNS separation or a documented endpoint name alone is not route confinement.

### 5.5 Egress Generation

A monotonically advancing identity for the complete approved combination of Egress Gateway logical authority, Active Egress Principal Set, credential generation, broker session policy, route policy, endpoint allowlist, deployment identity, software/configuration digest, Commit-Proof trust bundle, and environment/account scope.

### 5.6 Active Egress Principal Set

The finite set of non-transferable runtime workload identities authorized under one Egress Generation. Each capability and claim SHALL bind one exact principal. A shared generic service credential is not a principal set.

### 5.7 Quorum Commit Certificate

Consumer-verifiable proof that a quorum sufficient under ADR-002-012 durably accepted the exact committed command and result. It may use individual signatures, an aggregate signature, or another reviewed quorum-verifiable construction, but SHALL NOT reduce to one leader signature, local receipt, cache entry, or projection.

### 5.8 Hard Egress Fence

A mechanism that prevents a superseded or compromised principal from producing a broker-accepted order-affecting request even if the principal remains alive, retains old process state, and has some network reachability.

### 5.9 Broker-Order Mutation

Any request that may submit, cancel, replace, amend, exercise, assign, transfer, settle, or otherwise alter broker-held order or economic state. A cancellation is not automatically safer because it may remove required protection.

---

## 6. Safety Invariants

### EGRESS-INV-001 — One Final Authority Path

Every TOS-authorized live broker-order mutation passes through one declared Final Egress Trust Boundary for its Safety Cell and scope.

### EGRESS-INV-002 — No Credential-and-Route Bypass

No identity outside the current boundary possesses both usable live-order authority and a broker-order route.

### EGRESS-INV-003 — Quorum Claim Before Byte

No normal risk-relevant broker-directed byte is transmitted without a valid Quorum Commit Certificate for the exact committed `ClaimCapabilityAndMarkSendStarted` result.

### EGRESS-INV-004 — Exact Binding

Capability, claim, Commit Proof, request bytes, endpoint, account, credential generation, broker session, Egress Generation, and exact runtime principal SHALL match. No field may be substituted after validation.

### EGRESS-INV-005 — Stale Egress Cannot Transmit

A stale, removed, wrong-environment, wrong-generation, or uncommitted egress principal cannot create a broker-accepted TOS request.

### EGRESS-INV-006 — Restrictive State Dominates

HALT, revocation, time-health restriction, authority loss, credential compromise, route-policy contradiction, or proof-verification failure denies later normal sends within the approved containment bounds.

### EGRESS-INV-007 — No Unfenced Intermediary

No queue, proxy, sidecar, signer, reconnect layer, retry service, or session manager may preserve or recreate transmission authority outside the fenced claim-to-send boundary.

### EGRESS-INV-008 — Environment and Scope Confinement

Live and non-live credentials, routes, endpoints, accounts, principals, trust bundles, and configuration roots are non-interchangeable. Unknown routing or scope is denial.

### EGRESS-INV-009 — Rotation and Failover Do Not Overlap Unfenced Authority

Credential rotation, principal replacement, failover, rollback, or recovery cannot create two independently usable live egress paths for the same scope.

### EGRESS-INV-010 — Administration Is Not Trading Authority

Credential, route, deployment, consensus, and secret-store administrators cannot create a broker-order mutation merely by exercising administrative access.

### EGRESS-INV-011 — Unknown Is Denial and Conservative Capacity

Unknown proof, credential, route, send, session, broker acceptance, or old-principal state denies new risk and preserves conservative potentially-live capacity.

### EGRESS-INV-012 — Protective Access Is Bounded

Degraded protective access uses only exclusive pre-issued protective authority and cannot become a normal-risk or replenishing bypass.

### EGRESS-INV-013 — External Broker Activity Is Not TOS Authority

Broker portal, manual desk, third-party, or unattributed activity is external activity requiring detection, reconciliation, and conservative capacity; it cannot be relabelled as a compliant TOS egress path.

### EGRESS-INV-014 — Evidence Does Not Replace Prevention

Credential inventories, network diagrams, logs, alerts, audit, and replay do not establish route confinement, proof validity, or hard fencing.

---

## 7. Authority and Separation of Duties

| Action | Required authority | Prohibited combination |
|---|---|---|
| Grant aggregate risk | Aggregate Risk Authority | Holding usable broker credential or route |
| Mutate capacity / commit claim | RCL State Machine through Safety Commit Log | Holding broker transmission authority |
| Issue capability | Safety Authority / Currentness Sequencer | Holding broker transmission authority |
| Validate and transmit | Broker Egress Authority | Inventing scope, capacity, capability, or proof |
| Administer credentials | Credential governance authority | Unilateral live arming or order construction |
| Administer routes | Network governance authority | Unilateral credential issuance or order construction |
| Deploy egress | Deployment authority | Reusing prior live authorization automatically |
| Halt | Safety Authority or authenticated emergency operator | Requiring the proposer or normal strategy path |
| Re-arm | Governed ADR-002-007 workflow | Automatic activation on health or connectivity |

No one administrative identity SHALL be able to modify payload policy, obtain usable live-order authority, open the broker-order route, and arm the resulting scope without the approved multi-party controls. Separation is evaluated across organizations, automation identities, recovery credentials, and shared control planes, not only application roles.

---

## 8. Egress Generation and Principal Model

The authoritative Egress Generation and Active Egress Principal Set SHALL be committed in the Safety Commit Log or another transactionally coupled linearizable namespace satisfying ADR-002-012.

Each active principal SHALL have:

- a non-transferable workload identity;
- exact deployment, artifact, software, configuration, environment, and Safety Cell digests;
- an exact credential and broker-session generation;
- an exact route and endpoint-policy generation;
- an exact Commit-Proof trust-bundle generation;
- an explicit activation and expiration state;
- no authority outside the committed set.

Capability authorization and claim SHALL bind these identities. A runtime SHALL NOT infer membership from a service account name, namespace, host role, load-balancer target, possession of an old secret, or successful broker authentication.

Multiple active runtime principals are permitted only when:

1. all are explicitly committed in one Active Egress Principal Set;
2. capabilities bind one exact principal and remain single-use;
3. quorum claim serializes every send;
4. removal of one principal is enforced at proof, signer/credential, route, and broker-session boundaries;
5. the shared failure and compromise blast radius is recorded honestly.

If these properties cannot be proven, only one active runtime principal is permitted and replacement requires downtime plus hard fencing.

---

## 9. Credential Custody

### 9.1 Inventory

The credential inventory SHALL include every artifact or service that can contribute to broker acceptance, including indirect signing and delegated-session mechanisms. Hidden operational, recovery, portal, CI/CD, support, and vendor credentials are in scope.

### 9.2 Non-Exportability and Retrieval

Where supported, broker private keys and signing material SHALL be non-exportable and usable only by a current Active Egress Principal. When the broker requires an exportable secret, retrieval SHALL require current workload identity, exact environment and Egress Generation, short-lived delivery, and evidence. The secret SHALL NOT be stored in source, image layers, generic environment files, logs, crash dumps, shared volumes, analytics, or general application configuration.

Possession of a bootstrap or secret-retrieval identity SHALL NOT itself grant broker-order authority. The credential service SHALL enforce generation and principal scope and SHALL NOT sign arbitrary payloads.

### 9.3 Session Authority

An authenticated broker session is usable live-order authority even if the underlying long-term credential is no longer present. Session creation, renewal, reconnect, pooling, and teardown SHALL therefore be bound to Egress Generation, exact principal, environment, account, endpoint policy, and current deny state.

A reconnect SHALL NOT flush a pre-HALT queue, reuse an old capability, clear the deny latch, or restore a superseded session.

### 9.4 Read and Trade Separation

Where the broker supports it, reconciliation and market-data reads SHALL use non-ordering credentials and routes. If one broker credential or session necessarily combines read and trade authority, read consumers SHALL access it only through a constrained service inside the declared common-mode boundary and SHALL NOT receive the credential or a general broker client.

That constrained service is part of the §15 common-mode scope and SHALL be included in the Final Egress Trust Boundary analysis because it handles usable live-order authority. It SHALL have no broker-order route or mutation-endpoint access under §10; if either exists, §1 makes the service part of the Final Egress Trust Boundary and the complete final gate applies. Any combined credential or session exposed outside the approved service and principal scope is suspected compromise under §16.

The Broker Capability Profile SHALL state the actual broker-enforced scope. Application convention is not broker-enforced least privilege.

---

## 10. Broker-Order Route Confinement

Only current Active Egress Principals may reach live broker-order endpoints. The route policy SHALL bind:

- environment and Safety Cell;
- workload identity and Egress Generation;
- broker and account scope;
- canonical destination and transport identity;
- endpoint, method, and action allowlist;
- broker session and credential generation;
- approved proxy, signer, and network path identities.

Route confinement SHALL reject direct, alternate, legacy, test-to-live, operator, administrative, and vendor-support paths unless they are explicitly classified as external broker authority and conservatively governed.

IP allowlists, security groups, DNS, service names, or network segmentation MAY contribute but are not alone proof of identity, payload, endpoint, or broker-account confinement. Any transparent route that allows an outside principal to borrow the gateway's credential or session is a bypass.

Order submission, cancel, replace, amend, and other mutation endpoints SHALL be deny-by-default. Unknown API versions, redirects, hostnames, endpoints, methods, or broker routing changes invalidate the applicable profile and deny transmission.

---

## 11. Commit-Proof Format and Validation

### 11.1 Required Claims

The Quorum Commit Certificate SHALL bind at least:

- Safety Commit Log cluster identity;
- Capacity Domain and Safety Cell;
- membership generation and quorum rule;
- Restore Generation and Writer Epoch;
- committed log revision and parent/preceding commitment where required;
- command identity and canonical command digest;
- resulting state digest;
- exact `ClaimCapabilityAndMarkSendStarted` result;
- intent, reservation, attempt, capability, nonce, and broker-request identities;
- exact worst-case economic effect;
- Safety Authority, Live Authorization, revocation, HALT, Time Health, Recovery Generation, profile, and configuration generations;
- exact current Recovery Evidence Package and Recovery Readiness Decision identities, canonical digests, dependency-complete scope, validity interval, and invalidation set/status;
- exact ADR-002-018 Critical Input Policy, Context Generation, Critical Input Snapshot, and Decision Context Capsule identities/digests, source-continuity vector, maximum age, and invalidation set/status;
- exact ADR-002-019 Venue Constraint Policy, Constraint Generation, Venue Constraint Snapshot, and Order Admissibility Decision identities/digests, complete order shape, maximum age, and invalidation set/status;
- exact ADR-002-020 Order Construction Policy, Construction Generation, Authorized Construction Envelope, Canonical Broker Command, Economic Effect Envelope, and Order Conformance Proof identities/digests, maximum ages, and invalidation set/status;
- exact ADR-002-021 Aggregate Risk Policy, Aggregate Risk Generation, Aggregate Risk State Snapshot, Adverse Scenario Set, Aggregate Risk Decision, evaluated scope, requested vector, maximum ages, and invalidation set/status;
- exact ADR-002-022 Action Flow Policy, Action Flow Generation, Action Flow State Snapshot, Action Flow Decision, RCL action-flow commitment, single-use Action Flow Permit, cause lineage, resource vector, Protective Flow Reserve evidence, maximum ages, and invalidation set/status;
- Egress Generation and exact Active Egress Principal;
- credential, broker-session, route-policy, endpoint-policy, and trust-bundle generations;
- quorum signer identities or equivalent threshold-verification material.

### 11.2 Verification

Before send, the Final Egress Trust Boundary SHALL:

1. parse one canonical, versioned proof representation;
2. reject unknown security-relevant fields or ambiguous encodings;
3. verify a quorum sufficient for the claimed membership and fault model;
4. verify every signer was eligible in the claimed membership generation and trust bundle;
5. reject revoked, removed, duplicated, wrong-environment, or stale signers;
6. verify the exact command and resulting state digests;
7. verify current cluster, Restore Generation, Recovery Generation, Writer Epoch, Egress Generation, and currentness-session generations, and verify that the exact Recovery Evidence Package and Recovery Readiness Decision remain current, unexpired, non-invalidated, and valid for the complete requested dependency scope;
8. actively verify the current Critical Input Policy, Context Generation, permission-critical source continuity, exact Decision Context Capsule binding, age, scope, and invalidation status under ADR-002-018 without treating a cache, TTL, heartbeat, health result, eventual consistency, or absence of invalidation as currentness proof;
9. actively verify the current Venue Constraint Policy, Constraint Generation, session/tradability/account/broker state, exact Order Admissibility Decision binding, age, scope, and invalidation status under ADR-002-019 without treating a schedule, quote, cache, TTL, heartbeat, health result, connectivity, or absence of restriction as currentness proof;
10. actively verify the current Order Construction Policy, Construction Generation, exact command/proof/effect binding, compiler/serializer/SDK compatibility, ages, scope, and invalidation status under ADR-002-020 without treating cached `CONFORMANT`, type safety, SDK validation, signature validity, broker acceptance, or absence of invalidation as proof;
11. actively verify the current Aggregate Risk Policy, Aggregate Risk Generation, exact Aggregate Risk Decision and RCL commitment binding, evaluated scope/vector, ages, and invalidation status under ADR-002-021 without treating cached `GRANT`, RCL commit existence, evaluator health, TTL, heartbeat, or absence of invalidation as proof;
12. actively verify the current Action Flow Policy, Action Flow Generation, exact Action Flow Decision and RCL action-flow commitment, cause lineage, complete shared scope/vector, unused single-use Action Flow Permit, Protective Flow Reserve evidence where applicable, ages, and invalidation status under ADR-002-022 without treating cached `GRANT`, a local token, queue priority, RCL commit existence, governor health, TTL, heartbeat, broker connection, or absence of invalidation as proof;
13. verify the capability nonce and Action Flow Permit claim nonce are each bound and claimed exactly once for this principal and request;
14. reconstruct the exact actual outbound representation after every mutable internal stage and compare its canonical semantics, digest, endpoint, action, account, route, and economic effect to the ADR-002-020 command and proof;
15. verify the claim-to-first-byte bound can still be met.

One leader signature, successful RPC, database primary response, local journal entry, cached proof, event, projection, or audit record is insufficient.

### 11.3 Trust-Bundle Rotation

Commit-Proof verification keys and membership metadata SHALL be rollback-protected and environment-scoped. Rotation SHALL advance the trust-bundle and Egress Generations or use an atomic committed transition that binds both. Failure to establish the current trust bundle is denial.

Compromise of a quorum-verification key or trust-bundle distribution path requires containment, affected proof invalidation, credential/route fencing, reconciliation, and governed re-arm. Restoring an older trust bundle SHALL NOT revive authority.

---

## 12. Fenced Claim-to-Send and Request Construction

After validating the currentness session and before any broker-directed byte, the Egress Gateway SHALL obtain the Quorum Commit Certificate for the exact claim. Request construction SHALL be deterministic from the committed authorized fields and approved Broker Capability Profile.

No security-relevant field may be supplied or changed downstream after the proof comparison. This includes account, instrument, side, quantity, price, unit, multiplier, order type, time-in-force, reduce-only flag, client identity, endpoint, action, credential, and session.

The boundary SHALL begin the broker write within `B_capability_claim_to_send`. If the bound expires, a restrictive generation is accepted, currentness becomes uncertain, proof validation changes, the session reconnects, or request bytes differ, no send is permitted. The committed claim remains potentially live and capacity-covered until resolved; it is not reused.

If an intermediary is unavoidable, it SHALL meet one of these conditions:

1. it cannot inspect, change, duplicate, retain, replay, re-route, or independently authenticate the request and has no separate broker authority; or
2. it becomes part of the Final Egress Trust Boundary and independently enforces the complete proof, generation, deny-latch, single-use, payload, route, and bound rules.

A durable queue after claim is prohibited unless every queued item becomes non-sendable on restrictive-generation change and the queue is inside the complete final boundary. Availability or throughput is not a reason to weaken this rule.

---

## 13. Restrictive Events and Monotonic Denial

The following events SHALL set or advance a restrictive state for the affected scope:

- HALT or Live Authorization suspension/revocation;
- Safety Authority, Writer, membership, Restore, Recovery Generation, Time Health, or profile generation change;
- Egress Generation, principal, credential, route, endpoint, session, or trust-bundle mismatch;
- credential exposure or suspected compromise;
- inability to verify hard fencing of a predecessor;
- Commit Proof parsing, signature, quorum, membership, digest, or currentness failure;
- broker redirect, endpoint drift, unexpected session behavior, or profile contradiction;
- unknown send, broker acceptance, or downstream intermediary state.

The deny state is monotonic until the newer authoritative state and the full ADR-002-007 re-arm conditions are established. Cache recovery, reconnect, secret refresh, route restoration, deployment success, or deletion of an alert cannot clear it.

Restrictive events SHALL reach every final egress within the applicable `B_revocation_to_egress`, `B_halt_to_egress`, `B_time_health_to_egress`, `B_failure_domain_contain`, and `B_egress_hard_fence` bounds. A bound miss is containment or HALT, never extended permission.

---

## 14. Credential Rotation and Hard Fencing

Credential rotation and egress replacement SHALL follow a deny-first sequence:

1. prepare the new principal, credential, route, and trust policy without transmission authority;
2. stop new capability issuance for the old generation;
3. set the old generation's deny latch;
4. invalidate or isolate old broker sessions, signing authority, credential retrieval, and order routes;
5. obtain Hard Egress Fence Proof;
6. commit the new Egress Generation and principal set;
7. reconcile possible old-path activity and UNKNOWN sends;
8. issue fresh capability and live authority only through governed re-arm.

Hard Egress Fence Proof may rely on broker credential/session revocation, a non-exportable signer refusing the old principal, identity-aware route denial, broker-side source restriction, cryptographic key destruction, or another independently enforced mechanism. It SHALL demonstrate inability to create a broker-accepted mutation, not merely process shutdown or configuration intent.

An expiry fence is acceptable only when the credential/session is non-renewable by the old principal, broker acceptance after expiry is disproven within an approved bound, time assumptions are trustworthy, queued or pre-signed requests cannot survive, and the order route cannot establish a replacement session. Until expiry is positively proven, the old path is potentially active.

If the former path cannot be hard-fenced, the replacement remains non-live. New and old credentials SHALL NOT overlap as independently usable paths merely to avoid downtime.

---

## 15. Failover, Deployment, and Recovery

Egress failover is an authority change, not an ordinary load-balancer event. A standby SHALL default to denied transmission and SHALL NOT inherit authority from a service name, shared credential, shared volume, broker session, or prior successful deployment.

Before activation, failover SHALL establish:

- committed new Egress Generation and exact principal identity;
- hard fencing or proven expiry fencing of every predecessor path;
- current RCL, authority, time, profile, credential, route, session, and trust-bundle generations;
- current ADR-002-017 Recovery Generation and an unexpired, non-invalidated readiness decision for the exact dependency-complete scope;
- current ADR-002-018 Critical Input Policy, Context Generation, source continuity, and an unexpired, non-invalidated Decision Context Capsule for the exact requested action scope;
- reconciliation of claims, `SEND_STARTED`, broker orders, fills, positions, and UNKNOWN effects;
- no alternate direct credential or route;
- fresh Live Authorization and Transmission Capabilities where required.

Rollback is a new Egress Generation. Region recovery, cluster restore, credential recovery, or route recovery cannot reuse prior capability, currentness session, deny-latch state, or live authorization.

Multiple active egress principals remain one common-mode scope wherever they share a credential, signer, route, broker session, proxy, trust bundle, administrator, or broker account constraint. Redundancy count does not prove independent fencing.

---

## 16. Credential Compromise and Emergency Containment

Suspected exposure of usable live-order authority is a Critical incident. The affected scope SHALL:

1. stop new capability issuance;
2. set HALT or the narrowest sufficient restrictive state;
3. fence credential retrieval, signing, sessions, routes, and active principals;
4. preserve every open, pending, UNKNOWN, and potentially-live economic effect in capacity;
5. inventory broker and external activity;
6. rotate credential, Egress Generation, trust bundle, and affected authority generations;
7. reconcile before governed re-arm.

Unknown credential revocation or unknown old-session state is not proof of safety. The old path remains potentially active and blocks new risk.

An emergency operator may HALT or request a separately authorized protective action. A general broker portal, shared emergency API key, support credential, or manual dealer channel SHALL NOT be used as an undocumented TOS bypass. If such external authority exists, its activity is governed by ADR-002-004 and ADR-002-006 external-activity detection, reconciliation, and conservative capacity rules.

---

## 17. Degraded Protective Egress

Degraded protective transmission may proceed only with an exclusive pre-issued protective lease, local monotonic validity, bounded sub-ledger capacity, and a principal/credential/route scope committed before partition under ADR-002-001 through ADR-002-003.

The protective path SHALL:

- remain inside the same declared Final Egress Trust Boundary or a separately declared exclusive protective boundary;
- bind the exact lease owner epoch, Egress Generation, principal, credential, route, account, action class, and remaining local budget;
- use single-use nonce claim and durable `SEND_STARTED` semantics;
- prohibit normal-risk issuance, capacity creation, lease renewal, timeout recycling, or automatic failover;
- preserve UNKNOWN and potentially-live consumption after ambiguity or expiry;
- require hard fencing before ownership or egress principal reassignment.

If broker credential, session, route, or rate-limit semantics cannot preserve this exclusivity, protective capability is `PRIORITIZED_ONLY`, `BEST_EFFORT`, or unavailable under the Broker Capability Profile. Priority is not reserved protective capacity.

---

## 18. Broker and Environment Profiles

Each Broker Capability Profile SHALL record:

- every live and non-live credential type and actual broker-enforced scope;
- broker portal, manual, support, sub-account, delegated, and third-party authority;
- credential issuance, retrieval, rotation, expiration, revocation, and session semantics;
- revocation and session-termination bounds;
- simultaneous credential and session behavior;
- endpoint, API version, redirect, host, method, and action scope;
- broker-side IP, identity, device, certificate, or source restrictions;
- order-route, proxy, signing, and connection topology;
- read/trade separation and unavoidable shared authority;
- client request identity, replay, and duplicate acceptance behavior;
- sandbox/live differences;
- hard-fence mechanisms and evidence;
- residual bypass and external-activity paths.

An `UNKNOWN`, contradictory, unmeasured, or weaker-than-required profile field reduces or prohibits live scope. The profile cannot waive a Critical invariant.

Test, simulation, development, paper, restricted-live, and production SHALL use distinct identities, credentials, routes, trust roots, endpoint policies, and account allowlists sufficient to make cross-environment broker acceptance impossible.

---

## 19. Evidence, Metrics, and Alerts

The implementation SHALL retain evidence for:

- complete credential and route inventory by environment and generation;
- Active Egress Principal Set changes;
- credential retrieval, signing, session creation, renewal, reconnect, and destruction;
- route and endpoint-policy activation and denial;
- Commit Proof bytes, parsed claims, signer/quorum validation, trust-bundle generation, and rejection reason;
- capability, claim, request digest, first broker byte, ACK, fill, cancellation, and Final Quantity Proof lineage;
- hard-fence initiation, enforcement observation, broker denial, and completion proof;
- stale, removed, non-live, administrative, and direct-route bypass attempts;
- HALT/revocation propagation and bound measurements;
- external/manual activity and reconciliation;
- failover, rotation, recovery, and re-arm decisions.

Required metrics include current Egress Generation, active-principal count, usable-credential count by scope, open broker sessions, route-policy generation, Commit-Proof validation failures, stale-principal denials, bypass attempts, post-claim queue depth, claim-to-first-byte latency, hard-fence latency, credential revocation latency, external-activity detection latency, and unexplained broker mutations.

Alerts and evidence support containment and review. They do not make an unfenced path safe.

---

## 20. Failure Modes and Required Responses

| Failure | Required response |
|---|---|
| Strategy obtains live credential but route appears blocked | Critical bypass condition; HALT, revoke credential, prove route and broker-session fence, reconcile |
| Outside identity reaches broker order endpoint without credential | deny route; treat as attempted bypass and review credential/signing exposure |
| Leader-signed or locally persisted claim presented | reject; require quorum-sufficient Commit Proof |
| Valid proof from stale cluster or generation | reject at proof and egress-generation checks; contain replay source |
| Proof valid but request bytes or endpoint differ | reject; Critical integrity alert |
| Proxy or queue can replay after claim | topology non-conforming; stop live scope until full gate or non-replay property is proven |
| HALT races claimed request | deny after restrictive acceptance or bound expiry; ambiguity remains potentially live and capacity-covered |
| Credential rotation leaves old session usable | new generation remains non-live; hard-fence old session and reconcile |
| Old egress unavailable but not proven fenced | treat as potentially active; deny replacement live authority |
| Broker cannot revoke credentials rapidly | use internal non-exportable signer and route fence or reduce/prohibit live and degraded scope |
| Credential or trust bundle suspected compromised | HALT, fence, rotate generations, quarantine unknown effects, reconcile, governed re-arm |
| Broker redirects to unknown endpoint | reject and invalidate affected Broker Capability Profile scope |
| Manual broker order appears | classify external/unattributed, preserve capacity, suspend new risk, reconcile |
| Egress reconnects after outage | remain denied; no queued flush or authority revival; fresh currentness and capability required |
| Evidence pipeline unavailable | no new send where required evidence durability cannot be established; evidence is not a substitute for fencing |

---

## 21. Rejected Alternatives

### 21.1 Shared Broker Credential in Execution Workers

Rejected because any worker or stale deployment can bypass final enforcement.

### 21.2 Network Firewall as the Only Gate

Rejected because it does not prove payload authorization, account scope, credential custody, session replay, or final request identity.

### 21.3 HSM or Signer That Signs Arbitrary Payloads

Rejected because a signing oracle becomes a general broker authority unless it validates the complete committed claim and request.

### 21.4 Leader Receipt as Commit Proof

Rejected because leader belief, local persistence, or signature does not prove quorum commitment.

### 21.5 Durable Queue After Authorization

Rejected when the queue can outlive restrictive generations, mutate payloads, reconnect, or replay outside the bounded final gate.

### 21.6 Shared Service Identity Across Deployments

Rejected because a stale instance cannot be distinguished or hard-fenced by exact principal identity.

### 21.7 Credential Rotation With Temporary Unfenced Overlap

Rejected because availability convenience cannot justify two independently usable broker paths.

### 21.8 Operator Portal as Emergency Egress

Rejected as a TOS-controlled path because it bypasses intent, capacity, capability, claim, and evidence ordering. Existing external authority must be detected and conservatively governed.

### 21.9 Audit and Secret Scanning as Prevention

Rejected because detection after credential leakage or broker acceptance cannot replace non-bypassable custody and route enforcement.

### 21.10 Automatic Re-arm After Credential or Route Recovery

Rejected because restoration proves neither state reconciliation nor current economic authority.

---

## 22. Consequences

### 22.1 Positive

- the final enforcement boundary follows actual broker authority rather than component naming;
- stale and non-live identities cannot use alternate credential or route paths;
- quorum commitment is independently verified at the irreversible send boundary;
- request substitution and downstream replay gaps are explicit;
- credential rotation and failover become deny-first, evidenced authority changes;
- broker and environment limitations reduce scope rather than weakening invariants;
- compromise and manual activity preserve conservative economic accounting.

### 22.2 Negative

- credential, route, signer, proxy, and broker-session topology becomes safety-critical;
- every send incurs proof verification and strict request construction;
- failover and rotation may require live downtime;
- some brokers cannot provide sufficient revocation, scope, or session controls;
- non-exportable signing and identity-aware routing may add operational complexity;
- multiple egress replicas remain a common-mode security scope unless independently fenced;
- conservative compromise response may halt substantial scope.

These costs are accepted because an alternate live credential or route defeats every upstream safety decision.

---

## 23. Acceptance Cases

The following cases are mandatory and map one-to-one to `EGRESS-EV-001` through `EGRESS-EV-012`. Written cases are not completed evidence.

| ID | Required demonstration |
|---|---|
| `EGRESS-AC-001` | Complete credential, signer, session, portal, and route inventory proves no identity outside the final boundary possesses a usable live credential-and-route combination |
| `EGRESS-AC-002` | Strategy, stale deployment, removed principal, administrator, and non-live identities cannot submit through direct, alternate, legacy, proxy, or borrowed-session paths |
| `EGRESS-AC-003` | Live/non-live, account, environment, endpoint, method, action, credential, session, and route substitution is rejected before broker acceptance |
| `EGRESS-AC-004` | Leader receipt, minority proof, insufficient signer set, stale membership, old Restore Generation, old Writer Epoch, and wrong trust bundle fail Commit Proof validation |
| `EGRESS-AC-005` | Valid proof or capability cannot be replayed, reused, transplanted to another principal/request/endpoint, or paired with changed request bytes |
| `EGRESS-AC-006` | Queue, proxy, sidecar, signer, reconnect, retry, and session intermediaries cannot mutate or replay after the quorum claim or outlive the claim-to-send bound |
| `EGRESS-AC-007` | HALT, revocation, time restriction, generation change, currentness loss, and deny-latch races dominate later normal sends at the actual irreversible boundary |
| `EGRESS-AC-008` | Credential rotation and trust-bundle/route change use deny-first sequencing and prove the old credential, session, signer, and route are hard-fenced before new live authority |
| `EGRESS-AC-009` | Egress failover, rollback, stale-instance resume, and removed-principal recovery cannot create overlapping or automatically revived transmission authority |
| `EGRESS-AC-010` | Credential compromise or unknown revocation causes bounded HALT/fencing, preserves potentially-live capacity, detects external activity, and requires reconciliation plus governed re-arm |
| `EGRESS-AC-011` | Degraded protective egress consumes only exclusive pre-issued lease capacity, cannot issue normal risk, cannot recycle ambiguity, and cannot reassign without hard fencing |
| `EGRESS-AC-012` | Broker portal/manual activity, route recovery, reconnect, credential recovery, and deployment health cannot be treated as compliant egress or automatic re-arm |

---

## 24. Requirements Traceability

| Requirement | ADR-002-013 allocation |
|---|---|
| SAFE-010, SAFE-011 | Complete pre-send enforcement at the effective non-bypassable Final Egress Trust Boundary (§§1, 6, 10–12) |
| SAFE-014 | Reconnect, retry, queue, and session paths remain bounded and cannot create unbounded broker mutations (§§9.3, 12–13) |
| SAFE-015 | Broker send is bound to the exact quorum-committed capacity claim (§§11–12) |
| SAFE-021, SAFE-033 | Immutable intent/attempt/request lineage and exact broker-order conformance are verified before transmission (§§11–12) |
| SAFE-024 | Manual, portal, third-party, and compromised-credential activity is external activity requiring reconciliation (§16) |
| SAFE-040 | Protective egress remains available only within proven exclusive bounded authority (§17) |
| SAFE-041, SAFE-042, SAFE-048 | Independent restrictive authority dominates egress, partitions, and emergency behavior without creating a bypass (§§7, 13, 16–17) |
| SAFE-045, SAFE-046, SAFE-047 | Environment, live scope, credential, route, principal, and generation confinement fail closed (§§8–10, 18) |
| SAFE-051, SAFE-052 | Security and send evidence supports traceability and replay without replacing prevention (§19) |

---

## 25. Open Implementation Questions

The security architecture is selected. The following product, broker, topology, and parameter choices remain open while Proposed:

1. Which non-exportable signer, secret-delivery mechanism, or broker credential model enforces principal and generation binding?
2. Which identity-aware network, proxy, and broker-side controls establish order-route confinement?
3. What canonical Quorum Commit Certificate schema, signature aggregation, quorum rule, and verification library are approved?
4. How are consensus membership keys and Egress trust bundles rotated and rollback-protected?
5. What active/standby or multi-principal egress topology is approved per Safety Cell?
6. Which broker credential, session, endpoint, redirect, and revocation semantics are evidenced by the first profile?
7. What Hard Egress Fence Proof is available when an old instance, credential, region, or broker session is unreachable?
8. Which downstream proxies, TLS terminators, signers, queues, and session managers are inside the Final Egress Trust Boundary?
9. How are manual portals, support channels, and other external broker authority disabled, detected, or conservatively bounded?
10. How is degraded protective credential/route exclusivity enforced without creating a normal-risk path?
11. Which `B_egress_hard_fence`, credential-revocation, session-expiry, route-propagation, and claim-to-send bounds are approved?
12. Which independently controlled identities approve credential, route, deployment, trust-bundle, and re-arm changes?
13. How does egress verify ADR-002-014 Canonical Semantic Digests, Profile Generations, and Consumer Compatibility without a permissive cache or floating reference?
14. Which ADR-002-015 Human HALT authenticator, policy/graph generation, replay fence, local deny latch, and later reconciliation mechanism is accepted directly at final egress?
15. Which ADR-002-016 Evidence Commit Receipt, emergency durable journal, source sequence, integrity anchor, and gap-containment mechanism binds exact pre-effect and `SEND_STARTED` evidence without becoming transmission authority?
16. How does final egress verify the current ADR-002-017 Recovery Generation, closed-barrier state, and exact readiness-decision invalidation without a permissive cache or treating readiness as authority?
17. How does final egress verify ADR-002-018 Critical Input Policy, Context Generation, source continuity, exact Capsule binding, age, and invalidation without a permissive cache or recomputing strategy logic?
18. How does final egress verify ADR-002-019 Constraint Generation, exact order admissibility, session/tradability/account/broker state, age, and invalidation without a permissive cache or unfenced check-then-send window?

Unresolved questions reduce availability or keep the affected scope non-live. They SHALL NOT create a permissive default.

---

## 26. Approval Gate

ADR-002-013 SHALL remain **Proposed** until all of the following are complete:

1. the Final Egress Trust Boundary, Safety Cells, Egress Generations, and Active Egress Principal Sets are approved;
2. complete credential, signer, session, portal, route, proxy, and endpoint inventories are independently reviewed;
3. Quorum Commit Certificate format and validation are implemented against ADR-002-012 commitment semantics;
4. exact capability/proof/request/principal/credential/route binding is enforced before every broker mutation;
5. all alternate live broker credentials and routes are removed, broker-classified external, or hard-fenced;
6. rotation, failover, stale-instance, compromise, trust-bundle, and disaster-recovery procedures are implemented and security-reviewed;
7. broker-specific credential, session, revocation, endpoint, and manual-authority semantics are `VERIFIED` or `VERIFIED_WITH_RESTRICTION` in an approved Broker Capability Profile;
8. `EGRESS-EV-001` through `EGRESS-EV-012` and applicable SA, BC, REARM, FD, RCLP, and cross-system evidence pass at their required levels and receive independent review;
9. ADR-002-014 exact committed envelope/profile digests, Profile Generation, compatibility, restrictive precedence, and mixed-version denial are enforced at egress and their applicable SPG evidence passes;
10. ADR-002-015 Human HALT and approval references are authenticated, replay-fenced, directionally restricted, and unable to create direct broker or permissive authority, and their applicable HAG evidence passes;
11. ADR-002-016 exact pre-effect and `SEND_STARTED` durability, evidence receipt validation, emergency journal, causal completeness, and replay isolation are implemented and their applicable ERI evidence passes;
12. ADR-002-017 Recovery Generation, barrier state, exact readiness currentness and invalidation, and stale-recovery rejection are enforced at the final boundary and applicable SBR evidence passes;
13. ADR-002-018 exact Decision Context Capsule binding, active Critical Input currentness, correction/invalidation, stale-context rejection, and context non-authority are enforced at the final boundary and applicable CII evidence passes;
14. ADR-002-019 exact Venue Constraint Snapshot and Order Admissibility Decision binding, active constraint currentness, restrictive invalidation, exit/protective non-assumption, and constraint non-authority are enforced at the final boundary and applicable VTG evidence passes;
15. ADR-002-020 exact candidate command, conservative effect envelope, RCL dominance, conformance proof, Construction Generation, downstream-mutation fence, and actual-outbound equivalence are enforced at the final boundary and applicable IOC evidence passes;
16. ADR-002-021 exact Aggregate Risk Decision, policy/generation, state/scenario/effect bindings, RCL allocation/commitment, and active currentness are enforced at the final boundary and applicable ARE evidence passes;
17. ADR-002-022 exact Action Flow Decision, policy/generation, state/cause/vector/permit bindings, RCL allocation, protective reserve, single-use claim, and active currentness are enforced at the final boundary and applicable AFG evidence passes;
18. `B_egress_hard_fence` and all applicable currentness, revocation, HALT, recovery-barrier, Critical Input, venue-constraint, conformance, aggregate-risk, and action-flow invalidation, context/decision/command/proof/permit/snapshot-age, failure-domain, session, claim-to-send, evidence-persistence, and evidence-gap bounds are approved and measured;
19. no unresolved bypass or overlapping old/new egress authority remains;
20. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Authorship, architecture review, credential inventory, route diagram, secret scan, or written acceptance case does not satisfy this gate. This ADR does not authorize acceptance, restricted-live operation, production operation, or automatic re-arm.
