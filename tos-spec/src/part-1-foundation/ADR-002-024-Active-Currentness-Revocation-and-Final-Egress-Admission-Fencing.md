# ADR-002-024 — Active Currentness, Revocation, and Final-Egress Admission Fencing

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** cross-artifact active currentness, monotonic restrictive fencing, currentness ordering domains, exact generation vectors, local deny latches, per-send currentness proof, claim-versus-restriction ordering, partition behavior, multi-domain admission, recovery, evidence, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-010, SAFE-011, SAFE-014, SAFE-015, SAFE-021, SAFE-024, SAFE-035, SAFE-041, SAFE-044 through SAFE-048, SAFE-050, and SAFE-051; RFC-002 §§9.1, 10.5, 10.8, 11, 16.5, 24, and 28–29; ADR-002-007 §§9 and 16; ADR-002-012 §§5, 12–14, and 20; ADR-002-013 §§8, 11, 16, and 25
- **Depends On:** RFC-000; RFC-001 SAFE-001, SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-014, SAFE-015, SAFE-020, SAFE-021, SAFE-022, SAFE-023, SAFE-024, SAFE-025, SAFE-030, SAFE-031, SAFE-032, SAFE-033, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-042, SAFE-043, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, and SAFE-052; ADR-002-001 through ADR-002-023

---

## 1. Decision

Every normal risk-relevant broker transmission SHALL be admitted through one **Active Currentness Protocol** that orders the exact required safety-generation vector, every applicable restrictive fence, the single-use Transmission Capability claim, and `SEND_STARTED` for the affected scope before the first broker-directed byte.

The protocol SHALL use the ADR-002-012 Safety Commit Log or another transactionally coupled linearizable **Currentness Ordering Domain**. A cache, TTL, heartbeat, replicated read model, event stream, health endpoint, last-known generation, absence of an invalidation event, or local leader belief is not an ordering domain and cannot prove currentness.

Every authority, policy, input, decision, capacity, flow, recovery, identity, route, session, and configuration dependency required for the exact action SHALL appear in one immutable **Safety Currentness Vector**. A currentness sequencer validates and orders owner-issued facts; it does not invent facts, decide business safety, mutate capacity, issue Live Authorization, classify protection, or transmit.

A restrictive owner transition SHALL create a monotonically ordered **Restrictive Fence Record** over the complete dependency scope. Restriction does not wait for a new permissive vector. Any final egress that receives a credible authenticated restriction, detects loss of required currentness, or cannot prove ordering SHALL first transition a monotonic **Local Restrictive Latch** to `DENY_LATCHED`, deny new risk, and then converge the authoritative fence. Restrictive evidence may reduce authority without depending on the availability of the permission path it disables.

For each normal send, final egress SHALL obtain one exact, single-use **Egress Currentness Proof** in the same linearizable transaction or serializable ordering boundary that claims the Transmission Capability and commits `SEND_STARTED`. The proof binds the complete vector, currentness revision, restrictive floors, attempt, canonical broker command, capacity and action-flow commitments, capability, egress principal, route, session, and local-latch state. The proof is a non-authorizing conformance fact and cannot be reused.

If a restrictive fence is ordered before the claim, the claim is rejected. If the claim is ordered first, the attempt is treated as potentially live and remains conservatively capacity-covered even if a restriction is ordered before the first byte or broker acknowledgement. A local restrictive latch observed before the irreversible boundary denies the send regardless of an earlier permissive read. Ambiguous ordering, lost claim response, lost send evidence, or uncertain broker acceptance cannot produce a retry permission.

During loss of quorum, currentness ordering, required owner proof, trustworthy time, current egress identity, route confinement, or complete dependency scope, normal new-risk admission is denied even when the broker session remains reachable. Only already issued exclusive degraded protective authority may be considered, within ADR-002-001/003 bounds and without converting priority into reserved capacity.

Expiry, invalidation, fencing, HALT, or loss of currentness limits future authority only. It does not cancel an order, erase a position, release capacity, establish broker non-acceptance, or establish Final Quantity Proof. Recovery, reconnect, replay, restore, leader election, or health restoration cannot revive an old vector, proof, capability, permission, or live state. No automatic re-arm is permitted.

---

## 2. Context

ADR-002-007 selects a fenced single-use capability protocol. ADR-002-012 orders capacity commitment, capability authorization, capability claim, and `SEND_STARTED`. ADR-002-013 confines usable broker authority to the final egress boundary. ADR-002-014 through ADR-002-023 add governed configuration, human authority, evidence, recovery, Critical Input, venue constraints, command conformance, aggregate risk, action flow, and automated approval generations.

Those decisions repeatedly require final egress to establish active currentness without permissive caches. They do not yet define one complete cross-artifact ordering contract. Independent implementations could otherwise:

- validate each generation from unrelated caches at different points in time;
- issue a capability against a vector that was never atomically complete;
- observe a revocation after a permissive read but send before the cache updates;
- continue normal sends during a control-plane partition because the broker remains reachable;
- treat a heartbeat or absence of invalidation as proof that no restriction exists;
- allow a stale publisher, restored registry, or former egress principal to recreate a permissive vector;
- create circular dependencies in which restriction cannot be committed because the disabled permission path is unavailable;
- claim that a short TTL is equivalent to measured revocation containment;
- release capacity because an approval, proof, vector, or capability expired;
- use audit or replay to explain a send that should have been prevented.

This ADR closes those paths while preserving the sole authority of each underlying owner and the RCL.

---

## 3. Decision Drivers

1. Every required generation must be evaluated as one exact action-scoped vector.
2. Restriction must dominate permission and must not depend on the permission path.
3. Capability claim, currentness proof, and send-start state must have one authoritative order.
4. Broker reachability during control-plane partition must not preserve normal-risk authority.
5. Stale writers, publishers, restore generations, and egress principals must be fenced.
6. Currentness aggregation must not become a new business, capacity, or transmission authority.
7. UNKNOWN ordering or scope must preserve conservative economic capacity and deny new risk.
8. Protective availability must remain explicitly pre-committed and bounded.
9. Recovery and replay must not revive permission.
10. The protocol must be product-independent and fault-injection testable.

---

## 4. Scope and Non-Scope

This ADR decides:

- the Currentness Policy and dependency-scope contract;
- the Currentness Ordering Domain and revision semantics;
- Safety Currentness Vector and Restrictive Fence Record contracts;
- local restrictive-latch behavior;
- per-send Egress Currentness Proof semantics;
- claim, fence, and `SEND_STARTED` ordering;
- partition, multi-domain, stale-writer, failover, recovery, and ambiguity behavior;
- evidence and acceptance obligations.

This ADR does not select:

- a consensus, database, RPC, queue, service-mesh, cryptographic, or HSM product;
- the business result of any underlying policy, evaluator, or owner;
- the capacity state-transition function, which remains RCL-only;
- the Safety Authority, Live Authorization, approval, risk, flow, venue, or construction policy;
- broker-specific Final Quantity Proof;
- numeric bounds, which remain approved Verification Profile decisions.

---

## 5. Definitions

### 5.1 Currentness Policy

An ADR-002-014 governed immutable policy defining required currentness dimensions, owner identities, dependency-scope closure, generation comparison, restrictive precedence, proof construction, consumer compatibility, and failure response.

### 5.2 Currentness Ordering Domain

The smallest linearizable ordering scope that contains every shared restrictive dependency, capability claim, and send-start decision for an action. It is implemented by the Safety Commit Log or a transactionally coupled namespace satisfying ADR-002-012.

### 5.3 Safety Currentness Vector

An immutable canonical action-scoped vector binding every required owner-issued generation, artifact identity and digest, minimum restrictive floor, validity fact, dependency scope, and source proof at one Currentness Revision.

### 5.4 Currentness Revision

The committed log position that orders one vector, fence, capability claim, or send-state transition. It is an ordering identity, not wall-clock time and not proof that unobserved external facts do not exist.

### 5.5 Restrictive Fence Record

An immutable owner-authenticated record that advances a monotonic minimum generation or denial state for a complete affected scope. It invalidates future use of older or incompatible facts without erasing prior economic effect.

### 5.6 Egress Currentness Proof

A single-use non-authorizing proof created for one exact attempt at the claim-to-send boundary, demonstrating that the complete vector satisfied all committed restrictive floors and local latches at the claim revision.

### 5.7 Local Restrictive Latch

A monotonic fail-closed state inside the Final Egress Trust Boundary with explicit states `CLEAR`, `DENY_LATCHED`, and `UNKNOWN`. Only positively established `CLEAR` may satisfy one send; `DENY_LATCHED` and `UNKNOWN` deny. It cannot transition back to `CLEAR` because of timeout, process restart, health recovery, or cache refresh.

### 5.8 Send Admission Point

The last irreversible boundary before the first broker-directed byte, at which the exact currentness proof, claimed capability, committed `SEND_STARTED`, local latch, payload, principal, route, and session must all agree.

### 5.9 Dependency Closure

The complete set of actions and scopes whose permission may be affected by one fact, shared limit, policy, identity, credential, route, configuration, or generation. Unknown closure expands scope or denies admission.

### 5.10 Currentness Gap

Any missing, stale, conflicting, unordered, unverified, partially propagated, wrong-scope, wrong-owner, or ambiguous required fact or fence.

---

## 6. Safety Invariants

### CUR-INV-001 — Complete Exact Vector

Every normal send binds one complete exact Safety Currentness Vector; partial, mixed-generation, defaulted, wildcard, or best-effort vectors are denial.

### CUR-INV-002 — One Authoritative Order

Every applicable restrictive fence, normal capability claim, currentness proof, and `SEND_STARTED` transition has one authoritative order in the affected Currentness Ordering Domain.

### CUR-INV-003 — Restriction Dominates

A committed or locally latched restriction prevents later affected new-risk admission and cannot be overridden by an older permissive artifact, vector, proof, priority, or cached state.

### CUR-INV-004 — Deny Path Is Independent

Restriction and local latching do not require availability of the proposer, approval, normal capability, or broker-send permission path.

### CUR-INV-005 — Proof Is Not Authority

Currentness sequencing and proof construction create no approval, Intent, capacity, protection, Live Authorization, Transmission Capability, broker permission, HALT clear, or re-arm authority.

### CUR-INV-006 — Per-Send Active Verification

Each normal send obtains one new single-use proof at the claim boundary. TTL, heartbeat, health, cache age, last-known generation, prior proof, or absence of invalidation is insufficient.

### CUR-INV-007 — Claim/Fence Race Is Conservative

A fence ordered before claim denies; a claim ordered first remains potentially live and capacity-covered. Ambiguity never creates retry or capacity release permission.

### CUR-INV-008 — No Quorum, No Normal Send

Loss of authoritative ordering or required current owner proof denies normal new-risk transmission even when final egress can reach the broker.

### CUR-INV-009 — Complete Shared Scope

Every shared limit and dependency has one ordering boundary or a proven serializable cross-domain barrier. Unknown overlap merges scope or denies.

### CUR-INV-010 — Stale Generations Are Fenced

Old owners, publishers, writers, clusters, restore histories, deployments, credentials, routes, sessions, and egress principals cannot create or consume a current vector or proof.

### CUR-INV-011 — UNKNOWN Is Restrictive and Capacity-Consuming

Unknown currentness, ordering, send, broker acceptance, order, or exposure state blocks new risk and preserves the worst credible capacity obligation.

### CUR-INV-012 — Economic Effect Outlives Currentness

Expiry, invalidation, fencing, proof consumption, or currentness loss cannot erase an economic fact, release capacity, prove non-acceptance, or prove Final Quantity.

### CUR-INV-013 — Protective Authority Remains Bounded

Priority and protective labels are not reserved capacity. Only pre-issued exclusive protective authority may survive a normal-currentness partition, within its exact scope and lease.

### CUR-INV-014 — Recovery Does Not Revive

Restart, reconnect, failover, restore, replay, quorum recovery, time recovery, or health restoration cannot revive a vector, proof, capability, permission, or live state.

### CUR-INV-015 — Evidence Is Not Prevention

Logs, metrics, traces, audit, replay, and reconciliation cannot replace the ordered proof, local latch, capability claim, or final-egress denial.

---

## 7. Authority Ownership and Separation

| Action | Policy or fact owner | Enforcement owner | Explicit prohibition |
|---|---|---|---|
| Publish underlying generation or restriction | applicable source owner | owner transition rules | sequencer cannot invent the fact |
| Order vector and fence records | Currentness Sequencer through Currentness Ordering Domain | quorum state machine | cannot decide business approval or mutate capacity |
| Mutate capacity | none | RCL only | currentness components cannot reserve, transfer, quarantine, or release |
| Issue Live Authorization | Live Authorization Service | final egress verifies | currentness proof cannot arm scope |
| Issue Transmission Capability | Safety Authority under ADR-002-007 | Currentness Sequencer records and orders issuance only | sequencer and proof cannot manufacture capability or widen scope |
| Claim capability and mark send started | request by Execution Coordinator | ADR-002-012 ordered state machine | egress cannot bypass commit |
| Latch restriction | authenticated restrictive source or local detection | Final Egress Trust Boundary | latch cannot become permission |
| Transmit | Execution Coordinator requests | Broker Egress Gateway only | no complete current proof means no send |
| Clear HALT or re-arm | ADR-002-007/015 workflow | new authority and egress generation | health/currentness recovery is insufficient |

The Currentness Sequencer MAY share the ADR-002-012 consensus substrate, but sharing a substrate does not merge authority. It validates owner-issued facts and ordering preconditions only.

No currentness, evidence, recovery, policy, or registry identity may possess both usable live broker authority and an order route unless it is inside the ADR-002-013 Final Egress Trust Boundary and enforces the complete gate.

---

## 8. Currentness Policy and Dependency Scope

The Currentness Policy SHALL define:

- exact owner and verifier identities for each dimension;
- canonical artifact and generation comparison rules;
- scope keys and dependency-closure rules;
- restrictive state and minimum-floor semantics;
- required source proof and common-mode constraints;
- compatibility and schema rules;
- local-latch triggers and scope;
- cross-domain transaction rules;
- normal and degraded-protective distinctions;
- maximum permitted proof age and claim-to-send interval;
- evidence and failure responses.

Policy materiality and closure are governed. A producer, consumer, sequencer, operator, or egress cannot omit a dimension because it expects the fact to be unchanged. Unknown materiality is material; unknown scope expands to every credibly affected action.

Policy activation follows ADR-002-014 and advances Currentness Policy Generation. Activation alone does not create a current vector, authority, capability, proof, or live permission.

---

## 9. Safety Currentness Vector Contract

For the exact action, the vector SHALL bind at least:

- environment, Safety Cell, Capacity Domain, account, portfolio, strategy, venue, session, instrument, action class, and route scope;
- Currentness Policy identity, generation, digest, and compatibility manifest;
- Safety Commit Log cluster, membership, restore, writer, and committed-prefix identities;
- Safety Authority epoch, revocation generation, HALT generation, and Live Authorization;
- Hard Safety Envelope, Runtime Safety Profile, activation, ADR-002-026 Safety Deviation Policy, Active Deviation Set, and Deviation generations;
- ADR-002-027 Safety Incident Policy, Incident Generation, Active Safety Incident Set, exact affected-scope disposition, and incident restriction floor;
- ADR-002-028 Safety Monitoring Policy, Monitor Generation, Critical Telemetry and Monitor Coverage Manifest digests, exact coverage result, unresolved Monitoring Gaps, suppression state, and monitoring restriction floor;
- ADR-002-029 Software Release Policy, Release Generation, complete Admitted Release Set digest, exact Release Artifact Manifest, actual Runtime Artifact Attestation, compatibility result, signer/key status, and release restriction floor;
- Trustworthy Time, Recovery, Critical Input, Context, Constraint, Construction, Trading Approval, Aggregate Risk, and Action Flow generations;
- exact decision, proof, Intent, commitment, permit, and invalidation identities required by the action;
- Egress Generation, active principal, credential, route, endpoint, signer, session, and trust-bundle generations;
- minimum accepted restrictive floor for every dimension;
- currentness revision, source proofs, issue evidence, and validity bounds;
- canonical vector digest and signature or equivalent integrity evidence.

The vector is complete only when every required owner fact is positively established. A vector cannot use `latest`, wildcards, null-as-current, implicit inheritance, silent fallback, or mixed revisions.

A vector is not reusable across action, command, attempt, capability, scope, environment, route, session, or egress principal. Narrow reuse is permitted only when the active policy proves identical complete binding and the per-send proof is still newly created; broadening is prohibited.

---

## 10. Owner Publication and Generation Floors

Each underlying owner SHALL publish immutable authenticated generation facts and restrictive transitions through its own normative state machine. The Currentness Sequencer SHALL verify owner identity, canonical digest, scope, predecessor, monotonicity, dependency closure, and compatibility before ordering them.

Permissive state requires complete positive owner proof. Restrictive state requires only sufficient authenticated evidence to reduce authority. A restrictive submission SHALL NOT be rejected merely because a permissive dependency, normal capability issuer, or affected service is unavailable.

Every ordered restriction advances a minimum accepted generation or terminal denial floor. A later permissive fact cannot cross that floor without a new owner generation and, where required, the complete governed re-arm process.

Conflicting owners, forks, sequence regression, missing predecessor, unknown source continuity, or unverifiable scope create a Currentness Gap and restrictive closure over the union of credible scopes.

---

## 11. Restrictive Fence Commit and Local Deny

Restrictive handling is deny-first:

1. the detecting final egress sets the affected Local Restrictive Latch to `DENY_LATCHED` before accepting new claims;
2. the owner or authenticated restrictive ingress submits a Restrictive Fence Record;
3. the Currentness Ordering Domain commits the fence and advances the minimum floor;
4. every affected issuer, Intent Registry, RCL admission gate, and final egress rejects dependent older state;
5. gaps, unreachable consumers, stale principals, and late acknowledgements remain contained until proven fenced;
6. only a fresh governed chain may restore permission.

The local latch is monotonic within its egress/restore generation. Process restart, reconnect, queue drain, session recreation, cache refresh, clock recovery, or receipt of an older permissive proof cannot clear it.

`DENY_LATCHED` is terminal within that latch generation. A later `CLEAR` may be positively established only in a new latch and egress generation after every predecessor send path is hard-fenced, every applicable restrictive floor is satisfied by fresh owner facts, and any required ADR-002-007/015 governed re-arm has completed. A new generation starts `UNKNOWN`; it never inherits `CLEAR`.

If authoritative fence commit is unavailable, local denial remains. Lack of a committed global fence is not evidence that continued sending is safe.

---

## 12. Egress Currentness Proof Contract

One proof SHALL bind:

- exact vector identity, digest, and committed revision;
- every required owner generation and restrictive floor;
- exact Intent, attempt, command, effect envelope, capacity commitment, action-flow permit, Live Authorization, and Transmission Capability;
- exact egress principal, deployment, credential, signer, route, endpoint, broker session, and local-latch generation;
- where applicable, the exact ADR-002-025 Trial Policy, Trial Plan, Trial Run, Promotion Generation, remaining action/effect/count/duration envelope, and abort generation;
- the capability-claim command and committed result;
- `SEND_STARTED` revision and maximum claim-to-send bound;
- proof identity, nonce, single-use state, issue revision, expiry evidence, and integrity evidence.

The proof result is `CURRENT`, `RESTRICTED`, or `UNKNOWN`. Only `CURRENT`, together with every separately required authority and commitment, can satisfy this one conformance check. `CURRENT` itself grants no authority.

Missing, stale, mismatched, conflicting, consumed, duplicate, wrong-scope, wrong-principal, wrong-route, unknown-age, or unverifiable proof is denial. Proof expiry never expires possible economic effect.

---

## 13. Normal Per-Send Admission Protocol

For every normal risk-relevant attempt:

1. the Execution Coordinator submits the exact immutable attempt, command digest, capability, and required dependency set;
2. final egress verifies its own current principal, route, session, trust bundle, and positively established local latch state `CLEAR`;
3. the ordering domain validates the complete current vector and all restrictive floors at one revision;
4. the RCL commitment and Action Flow Permit are verified current and exact without mutating capacity outside RCL transitions;
5. one atomic command claims the capability, claims the action-flow permit as applicable, creates the Egress Currentness Proof, and commits `SEND_STARTED`;
6. final egress rechecks the local latch and exact outbound representation at the Send Admission Point;
7. the first broker-directed byte is emitted only within the approved claim-to-send bound;
8. outcome evidence is recorded without treating missing acknowledgement as rejection.

Steps 3–5 SHALL be one linearizable transition or a proven serializable composition that cannot admit a fence between validation and claim. Step 6 ensures a locally observed restriction still dominates before the irreversible boundary.

A failed or unknown result does not authorize retry, alternate route, regenerated capability, or capacity release. A new attempt requires the applicable complete current chain.

---

## 14. Restriction, Claim, and Send Races

The authoritative order determines future-use permission:

- `FENCE < CLAIM`: reject claim; no send.
- `CLAIM < FENCE < FIRST_BYTE`: local or global restriction prevents the byte when observed; nevertheless the claimed attempt remains potentially live until evidence proves otherwise.
- `CLAIM < FIRST_BYTE < FENCE`: the attempt is potentially live; retain capacity and contain later activity.
- unknown order, lost response, or incomplete trace: treat as potentially live, preserve capacity, deny blind retry, and reconcile.

No timeout rewrites one case into another. Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. Broker rejection does not retroactively make an unsafe admission compliant.

The approved bounds SHALL measure detection-to-fence, fence-to-egress denial, proof creation, and claim-to-first-byte separately. One interval cannot be hidden inside an unmeasured cache TTL, retry delay, or aggregate SLA.

---

## 15. Partition and Quorum Behavior

If final egress can reach the broker but cannot obtain a current linearizable revision, validate every owner proof, or commit the claim, normal transmission is denied.

If the ordering domain retains quorum but an owner path is unavailable, missing positive proof creates a Currentness Gap and denies dependent normal sends. Quorum availability does not manufacture an owner fact.

If owner paths are reachable but the ordering domain lacks quorum, no process-local vector, signed bundle, read replica, cache, or pre-fetched proof may substitute for the missing order.

Partition healing does not auto-submit queued work, revive capabilities, clear latches, or re-arm. Stale queued attempts remain invalid and potentially live where broker acceptance is unresolved.

---

## 16. Multi-Domain and Shared-Scope Ordering

An action affecting multiple Currentness Ordering Domains or any shared aggregate limit SHALL use one of:

1. one domain containing the complete shared scope;
2. a serializable cross-domain barrier with proven non-forking failure semantics; or
3. denial of the action.

Independent per-domain proofs cannot be unioned into a broader action. Best-effort compensation after multiple claims is not atomic admission. Unknown overlap merges the affected scope or denies new risk.

Parent and child generation rules SHALL prevent a child from appearing current after a restrictive parent floor advances. A narrower domain cannot create permission against a stale shared parent.

---

## 17. Degraded Protective Operation

Normal active-currentness loss does not create protective authority. A protective request may proceed only when:

- ADR-002-001/003 provide an already issued, exclusive, scope-limited, monotonic lease;
- ADR-002-002 provides pre-committed protective capacity;
- ADR-002-022 provides actual reserved Protective Flow capacity;
- ADR-002-019/020 prove the exact action remains admissible and conforming;
- ADR-002-011 proves protection/replacement semantics;
- the final egress path remains confined and every degraded proof required by the lease is current.

Priority, emergency, close, hedge, exit, reduce-only, or protective labels cannot replace any condition. If safe protection cannot be proved executable, the state is trapped exposure requiring containment and escalation, not permission expansion.

---

## 18. Expiry, Invalidation, and Economic Continuity

Currentness artifacts and proofs expire only for future use. Expiry or invalidation SHALL NOT:

- cancel or prove cancellation of broker state;
- prove an unacknowledged attempt was not accepted;
- establish Final Quantity;
- release, reduce, or forget capacity;
- erase a position, fill, external activity, trapped exposure, or obligation;
- authorize retry or alternate routing.

RCL remains the sole capacity mutation authority and applies only proof-gated lifecycle transitions. Any unknown broker/order/exposure outcome remains conservatively capacity-consuming.

---

## 19. Failover, Restore, and Recovery

New ordering-cluster, restore, membership, writer, egress, credential, route, session, policy, or deployment generations fence every predecessor vector and proof.

An old instance is potentially active until hard fencing proves it cannot order, claim, sign, route, or create a broker-accepted mutation. Administrative intent, deployment status, process absence, or credential-rotation request is not hard-fence proof.

Restore creates a new Restore Generation and starts with currentness `UNKNOWN` and its local latch `DENY_LATCHED`. Authoritative history, restrictive floors, consumed proofs, capability claims, `SEND_STARTED`, local-latch evidence, idempotency records, and economic obligations must be preserved or conservatively reconstructed.

Recovery readiness is non-authorizing. Reconciliation, current quorum, healthy owners, complete replay, or current vectors do not clear HALT or re-arm. ADR-002-007/015 must issue fresh authority through the complete governed workflow.

---

## 20. Security and Failure-Domain Requirements

The design SHALL resist:

- compromised or stale currentness sequencers;
- source-owner impersonation and restrictive-record suppression;
- vector, scope, generation, digest, proof, capability, command, principal, route, or session substitution;
- permission/restriction parser differential;
- replay of a proof across attempt, domain, restore, egress, or broker scope;
- credential or signer services accepting arbitrary payloads;
- local-latch bypass through sidecar, proxy, SDK, alternate route, or broker portal;
- denial-path dependence on normal control-plane availability;
- two administrative groups forcing conflicting authoritative histories.

Permission and restriction use canonical schemas with restrictive parser disagreement. Restrictive paths, local latches, ordering quorum, final egress, and evidence retention require an approved Failure-Domain Allocation Matrix.

An alternate identity, broker portal, or route outside the complete gate is external activity, not a compliant escape hatch. It requires detection, conservative capacity, reconciliation, and containment.

---

## 21. Evidence, Metrics, and Alerts

Evidence SHALL preserve:

- policy, vector, owner-generation, dependency-closure, and restrictive-floor identities;
- every vector/fence/claim/proof/`SEND_STARTED` command and committed revision;
- quorum, membership, restore, writer, principal, credential, route, session, and latch generations;
- exact request, command, capability, commitments, proof, outbound bytes, broker evidence, and ambiguity classification;
- local restriction receipt and latch time separately from global fence commit;
- rejection, conflict, stale-writer, duplicate, partition, timeout, and retry outcomes;
- measured detection, fence, propagation, proof, claim-to-send, and hard-fence intervals;
- recovery and non-revival evidence.

Required alerts include Currentness Gap, mixed vector, stale owner, fence conflict, local/global latch divergence, quorum loss, proof reuse, claim conflict, claim-to-send bound breach, outbound mismatch, old-principal activity, and broker-reachable/control-plane-unreachable state.

Evidence is written according to ADR-002-016 and must not become permission. Written tests and registered rows are not executed evidence.

---

## 22. Failure Modes and Required Responses

| Failure | Required response |
|---|---|
| Missing or mixed vector dimension | deny new risk; expand affected scope |
| Restrictive source observed | set local latch to `DENY_LATCHED`; order fence; contain |
| Fence commit unavailable | keep local denial; no normal send |
| Quorum or linearizable revision unavailable | deny normal claim and send |
| Owner proof unavailable or conflicting | Currentness Gap; deny dependent scope |
| Stale owner/sequencer/writer | reject and fence; investigate predecessor activity |
| Duplicate or replayed proof | reject; preserve original claim and economic state |
| Claim result unknown | potentially live; capacity-covered; no blind retry |
| Restriction/send order unknown | potentially live; contain and reconcile |
| Local latch differs from global state | restrictive state wins; HALT affected scope |
| Cross-domain barrier incomplete | abort/deny; do not compensate into permission |
| Claim-to-send bound exceeded | do not emit new byte; quarantine attempt |
| Old egress principal or route may remain usable | HALT; no replacement authority until hard fenced |
| Broker result unknown | preserve capacity and reconcile |
| Recovery appears healthy | remain non-live until fresh governed re-arm |

---

## 23. Rejected Alternatives

### 23.1 Cache Each Generation with a Short TTL

TTL bounds stale data age only under assumptions; it does not order restriction against claim and cannot prove absence of a newer fence.

### 23.2 Heartbeat Means Current

Health is not semantic currentness and can remain green while a dependency, scope, or generation is stale.

### 23.3 Push Revocations Eventually

Eventual delivery leaves broker-reachable stale egress paths. Restriction and claim require authoritative ordering plus local deny-first behavior.

### 23.4 Sign One Periodic Currentness Bundle

A reusable bundle creates a permissive window and cannot order a restriction that occurs before a later send.

### 23.5 Let Final Egress Recompute Strategy Safety

Egress verifies exact owner facts and conformance; it does not invent policy results, widen decisions, or become aggregate authority.

### 23.6 Availability Requires Sending During Partition

Normal-risk availability is subordinate to provable exclusivity and currentness. Broker reachability alone is not permission.

### 23.7 Priority Is Sufficient for Protection

Scheduling priority is not pre-committed capacity, flow reserve, admissibility, conformance, or protective authority.

### 23.8 Proof Expiry Releases Capacity

Proof validity limits future use only. Economic effect persists until RCL receives the required lifecycle proof.

### 23.9 Recovery Can Reuse the Last Complete Vector

Recovery changes generations and uncertainty. It requires fresh facts, reconciliation, authority, and governed re-arm.

### 23.10 Audit and Replay Are Enough

Detective evidence cannot replace ordered prevention at the irreversible boundary.

---

## 24. Consequences

### 24.1 Positive

- all cross-artifact currentness requirements gain one exact protocol;
- revocation, HALT, invalidation, and capability claim have explicit ordering;
- control-plane partition with broker reachability fails closed;
- local deny paths do not depend on normal permission availability;
- stale generations and restored histories are testably fenced;
- final egress verifies facts without absorbing business or capacity authority;
- send ambiguity remains economically conservative.

### 24.2 Negative

- every normal send requires a linearizable admission operation;
- currentness scope and dependency closure become substantial governed data;
- multi-domain actions may require expensive serialization or denial;
- local and global restrictive state require careful monotonic convergence;
- latency and availability decrease under partition or owner uncertainty;
- the ordering, proof, and hard-fence mechanisms require security review and fault injection.

These costs are accepted because un-ordered cached permission at a live broker boundary is not a safety mechanism.

---

## 25. Acceptance Cases

The following cases are mandatory and map one-to-one to `CUR-EV-001` through `CUR-EV-012`. Written cases are not completed evidence.

### CUR-AC-001 — Complete Exact Vector

Omitted, wildcard, defaulted, mixed-generation, wrong-scope, stale, conflicting, or substituted vector dimensions cannot produce a current proof.

### CUR-AC-002 — Restrictive Fence Dominance

HALT, revocation, invalidation, policy reduction, owner compromise, or generation advance ordered before claim denies every affected later claim and send.

### CUR-AC-003 — Independent Local Deny

Final egress sets its local latch to `DENY_LATCHED` on credible restriction/currentness loss even when quorum, proposer, approval, normal authority, or the restriction publisher is unavailable.

### CUR-AC-004 — Per-Send Proof and No Cache

TTL, heartbeat, health, cached vector, cached `ACTIVE`, cached `APPROVE`, last-known generation, prior proof, or absence of invalidation cannot replace a new exact per-send proof.

### CUR-AC-005 — Claim/Fence/First-Byte Race

Every ordering and lost-response permutation is either denied or retained as potentially live and capacity-covered without blind retry.

### CUR-AC-006 — Partition with Broker Reachability

Loss of currentness quorum, required owner proof, or ordering while the broker route remains reachable cannot produce a normal send.

### CUR-AC-007 — Stale Generation and Restore Fence

Old sequencers, owners, writers, clusters, restored databases, deployments, credentials, routes, sessions, and egress principals cannot create or consume a current vector or proof.

### CUR-AC-008 — Multi-Domain and Shared Scope

Concurrent cross-domain and parent/child actions cannot union independent proofs, omit a shared restrictive floor, double claim, or escape serialization.

### CUR-AC-009 — Authority and Capacity Separation

Currentness policy, sequencer, vector, fence, proof, latch, evidence, or replay cannot approve, mutate/release capacity, classify protection, issue authority/capability, transmit, clear HALT, or re-arm.

### CUR-AC-010 — UNKNOWN and Economic Continuity

Unknown order, claim, send, broker, exposure, proof, or currentness state blocks new risk, consumes conservative capacity, and preserves missing-ACK/cancel-ACK semantics.

### CUR-AC-011 — Protective Confinement

Priority or protective/exit labels cannot substitute for exclusive protective lease, reserved capacity, flow reserve, admissibility, conformance, and final-egress proof.

### CUR-AC-012 — Recovery, Evidence, and Non-Revival

Restart, failover, reconnect, restore, replay, quorum/time/health recovery, or complete evidence cannot revive permission or auto-re-arm.

---

## 26. Requirements Traceability

| Requirement | ADR-002-024 allocation |
|---|---|
| SAFE-001, SAFE-003 | Missing, conflicting, unordered, or unknown currentness is restrictive (§§8–15) |
| SAFE-010, SAFE-011 | Every normal send requires an exact non-bypassable ordered proof (§§7, 12–14) |
| SAFE-013 through SAFE-015 | RCL remains sole capacity authority; risk and flow facts are exact currentness inputs (§§7, 9, 13, 18) |
| SAFE-020, SAFE-021 | Intent/attempt identity, capability claim, and `SEND_STARTED` remain exact and single use (§§9, 12–14) |
| SAFE-022 through SAFE-025 | Unknown broker/order/exposure evidence remains conservative and cannot be overwritten by currentness (§§14, 18) |
| SAFE-030 through SAFE-035 | Context, constraint, construction, approval, risk, flow, and trustworthy-time generations form one vector (§9) |
| SAFE-040 through SAFE-043 | Restrictive and protective paths dominate without turning labels or priority into authority (§§11, 17) |
| SAFE-044 through SAFE-048 | Startup, partition, identity, live scope, stale generations, and recovery are fenced (§§15, 19–20) |
| SAFE-050 | Currentness Policy, schemas, compatibility, scope, and generation are governed artifacts (§8) |
| SAFE-051, SAFE-052 | Complete ordered evidence supports reconstruction but never substitutes for prevention (§21) |

---

## 27. Open Implementation Questions

The architecture is selected. These mechanism and parameter choices remain open while Proposed:

1. Which canonical Currentness Policy, Safety Currentness Vector, Restrictive Fence Record, and Egress Currentness Proof schemas are approved?
2. Does each scope use the ADR-002-012 Safety Commit Log directly or a transactionally coupled currentness namespace, and how is serializability proven?
3. Which owner-authentication, canonicalization, dependency-registry, generation-floor, and restriction-ingress mechanisms are used?
4. Which local latch storage and enforcement mechanism survives process restart, sidecar/proxy behavior, credential rotation, and egress failover?
5. Which per-send transaction atomically validates the vector, claims capability/action-flow permit, creates proof, and commits `SEND_STARTED`?
6. Which cross-domain protocol, if any, can satisfy shared parent/child and aggregate-scope ordering without fork or compensation gaps?
7. How are restrictive signals delivered independently from normal permission paths and protected against suppression or spoofing?
8. Which mechanism proves actual first-byte ordering and prevents queue/proxy/session flush after a latch or fence?
9. Which failure-domain and identity allocation separates owners, sequencer, RCL, authority, final egress, latch administration, and evidence?
10. Which degraded protective currentness subset is allowed per broker and lease without becoming normal-risk fallback?
11. Which restore and disaster-recovery mechanism preserves floors, claims, latches, idempotency, and economic obligations?
12. What `B_currentness_gap_to_local_deny`, `B_restrictive_fence_commit`, `B_currentness_fence_to_egress`, `B_currentness_proof_issue`, `B_currentness_generation_fence`, `MAX_egress_currentness_proof_age_ms`, and `MAX_currentness_vector_age_ms` values are approved?

Unresolved questions reduce authority or keep affected scope non-live. They do not permit cache-based or eventually consistent normal-risk admission.

---

## 28. Approval Gate

ADR-002-024 SHALL remain **Proposed** until all of the following are complete:

1. Currentness Policy, Vector, Restrictive Fence Record, and Egress Currentness Proof schemas and canonicalization are approved.
2. The Currentness Ordering Domain and its coupling to ADR-002-012 capacity/capability/claim ordering are implemented, fault-injected, and independently reviewed.
3. Every required owner generation, dependency closure, restrictive floor, and compatibility rule is complete and governed.
4. Restrictive ingress and Local Restrictive Latch are independent, monotonic, restart/failover safe, and non-bypassable at every effective egress boundary.
5. Per-send vector validation, capability/permit claim, proof creation, `SEND_STARTED`, outbound comparison, and first-byte ordering are implemented without permissive caches or circular dependencies.
6. Fence/claim/send ambiguity preserves potentially-live state, conservative capacity, and no-blind-retry behavior.
7. Partition with broker reachability, quorum loss, owner loss, stale writers, restore, credential/route/session overlap, and cross-domain races fail closed.
8. Currentness components cannot mutate capacity, create approval/authority/protection, transmit, clear HALT, or re-arm.
9. Protective degraded operation remains within pre-issued exclusive leases and actual reserved protective capacity/flow.
10. `CUR-EV-001` through `CUR-EV-012` and all applicable RCLP, EGRESS, SA, TIME, REARM, SBR, CII, VTG, IOC, ARE, AFG, IAP, ERI, FD, BC, RC, and cross-system evidence pass at required levels and receive independent review.
11. All currentness, restriction, claim-to-send, hard-fence, age, partition, and recovery bounds are approved and measured under actual fault injection.
12. Independent security review covers owner/sequencer compromise, parser differential, restrictive suppression/spoofing, proof replay/substitution, local-latch bypass, alternate route, stale restore, and administrative common mode.
13. No Critical or Major review finding remains unresolved, and canonical RFC/ADR/VER/Evidence Register traceability is complete.
14. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Authorship, schema drafting, successful vector/proof generation, signatures, logs, cache freshness, written cases, registered evidence, or EV-L0 document review do not satisfy this gate. This ADR authorizes architecture and implementation planning only. It does not authorize acceptance, restricted-live operation, production operation, broker transmission, or automatic re-arm.
