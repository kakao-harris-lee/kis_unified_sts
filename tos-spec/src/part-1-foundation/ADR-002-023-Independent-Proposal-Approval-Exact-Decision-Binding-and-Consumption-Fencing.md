# ADR-002-023 — Independent Proposal Approval, Exact-Decision Binding, and Consumption Fencing

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** automated independent proposal approval, policy and generation governance, exact request and decision binding, independent recomputation, common-mode control, immutable Intent registration, single-use consumption, invalidation, final-egress currentness, recovery, evidence, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-010, SAFE-011, SAFE-020, SAFE-030, SAFE-031, SAFE-033, SAFE-034, SAFE-041, SAFE-050, SAFE-051, and SAFE-052; RFC-002 §§9.1, 10.3, 11, 12, 27–29
- **Depends On:** RFC-000; RFC-001 SAFE-001 through SAFE-004, SAFE-010 through SAFE-015, SAFE-020, SAFE-021, SAFE-030 through SAFE-035, SAFE-040, SAFE-041, SAFE-043, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050 through SAFE-052; ADR-002-001 through ADR-002-022

---

## 1. Decision

Every ordinary exposure-increasing proposal SHALL pass one current **Trading Approval Policy**, one immutable **Proposal Approval Request**, and one exact **Independent Approval Decision** before the Intent Registry may create an approved Intent. The decision result is `APPROVE`, `DENY`, or `UNKNOWN`. Only `APPROVE` may be consumed, and it is eligible only for one atomic registration of one exact immutable Intent.

The Independent Approval Service SHALL independently validate every safety-critical fact required at this pipeline stage. It SHALL NOT trust a proposer-produced value merely because it is well formed, signed, internally consistent, recent, or repeated by another consumer of the same dependency. It SHALL use the exact ADR-002-018 Decision Context Capsule, ADR-002-020 proposal, Authorized Construction Envelope and candidate Canonical Broker Command, ADR-002-019 Venue Constraint Snapshot and Order Admissibility Decision, current governed policy generations, and approved independent or explicitly risk-reduced validation paths.

An `APPROVE` result is a non-authorizing business gate. It does not commit or release capacity, establish aggregate-risk safety, establish action-flow headroom, classify protection, issue Safety Authority or Live Authorization, create a Transmission Capability, clear HALT, reach a broker, or re-arm. Later aggregate-risk, action-flow, RCL, conformance, authority, live-scope, capability, and final-egress gates remain independently mandatory.

The Intent Registry is the sole owner of the `PROPOSED -> APPROVED` Intent transition. It SHALL atomically verify and consume one exact current approval decision while creating one immutable Intent identity and one **Approval Consumption Record**. The approval service cannot advance Intent state. The same decision cannot create a second Intent, be unioned with another decision, or authorize a mutated proposal.

Approval policy, evaluator, dependency, source, context, constraint, construction, software, deployment, credential, route, time, or invalidation change that can affect the result SHALL advance the applicable generation and invalidate the affected unconsumed decision. A consumed decision remains part of the economic lineage, but invalidation blocks future new-risk use of dependent Intents, attempts, authorities, capabilities, and sends until a fresh chain is completed. Invalidation never cancels an order, releases capacity, resolves UNKNOWN, proves broker non-acceptance, or proves Final Quantity.

Final egress SHALL actively verify the exact approval decision, consumption record, Trading Approval Generation, invalidation state, Intent binding, and all later gates immediately before the irreversible broker boundary. Cache age, TTL, heartbeat, service health, last-known generation, prior success, an Intent `APPROVED` flag, or absence of an invalidation event is not currentness proof. If currentness or ordering cannot be proved, the action is denied; any ambiguous send remains potentially live and capacity-covered.

ADR-002-024 defines the common per-send ordering mechanism. Trading Approval Generation, exact request/decision/consumption/Intent identities, and invalidation floors are dimensions in the Safety Currentness Vector; each later normal send requires a new Egress Currentness Proof ordered with the capability claim and `SEND_STARTED`.

Loss, partition, restart, rollback, failover, or recovery of the proposer, approval service, Intent Registry, policy registry, independent input path, or evidence system cannot revive an old decision or Intent authority. No automatic re-arm is permitted.

---

## 2. Context

RFC-001 requires pre-trade authorization, non-bypassable limits, immutable Intent identity, trustworthy context, and independent approval inputs. RFC-002 separates Decision Service proposal from Independent Approval Service validation and places Independent Approval before Intent registration.

The existing ADRs define human approval governance, Critical Input independence, venue admissibility, deterministic command construction, aggregate-risk evaluation, action-flow budgeting, capacity, authority, and final egress. They do not yet define the complete automated proposal-approval lifecycle or which component serializes its consumption.

Unsafe interpretations include:

- treating a schema-valid proposal or proposer signature as independent approval;
- recomputing with the same corrupted parser, cache, mapping, source, or administrator and calling it independent;
- approving an incomplete request and filling fields afterward;
- refreshing only price, venue, quantity, account, route, or context while preserving approval;
- consuming one approval into multiple Intent identities;
- racing two Intent Registry writers to consume the same decision;
- letting `APPROVE` bypass aggregate-risk, action-flow, capacity, authority, or final egress;
- accepting cached approval currentness after policy or input invalidation;
- treating approval expiry as cancellation of an order or release of capacity;
- allowing approval-service recovery to revive previous permission.

This ADR closes those paths without selecting an implementation product.

---

## 3. Decision Drivers

1. Approval must validate safety-critical facts independently from the proposer.
2. One exact immutable request and result must remain bound through Intent and egress.
3. `UNKNOWN`, conflict, omission, or stale state must deny ordinary new risk.
4. Approval consumption must be serialized and single use.
5. Approval must remain separate from capacity, authority, protection, and transmission.
6. Common-mode dependencies must be explicit and conservatively handled.
7. Invalidation must reach every dependent future-use gate without erasing economic effect.
8. Partitions, stale writers, rollback, and recovery must not revive approval.
9. Evidence and replay must reconstruct decisions without creating permission.

---

## 4. Scope and Non-Scope

This ADR decides:

- Trading Approval Policy and Generation semantics;
- Proposal Approval Request, Independent Approval Decision, and Approval Consumption Record contracts;
- independent recomputation and common-mode analysis;
- exact proposal, context, constraint, construction, environment, account, and route binding;
- deterministic result and restrictive default behavior;
- Intent Registry consumption serialization and Intent identity binding;
- invalidation, expiry, partition, recovery, evidence, and final-egress checks;
- acceptance cases and approval gates.

This ADR does not select:

- a workflow engine, rules product, language, database, consensus product, signature scheme, or RPC protocol;
- trading strategy logic or a profitability rule;
- aggregate-risk, action-flow, RCL, Live Authorization, Transmission Capability, or broker-send authority;
- human dual-control or break-glass policy, which remains governed by ADR-002-015;
- broker-specific admissibility, command construction, or Final Quantity Proof semantics;
- numeric bounds, which remain Verification Profile decisions.

---

## 5. Definitions

### 5.1 Trading Approval Policy

An ADR-002-014 governed immutable policy defining required facts, independent validation, common-mode rules, exact request semantics, decision logic, scope, validity, invalidation, compatibility, and failure responses for automated proposal approval.

### 5.2 Trading Approval Generation

A monotonic fenced generation identifying the active Trading Approval Policy, evaluator and verifier builds, dependency registry, independent-source allocation, compatibility set, and invalidation namespace for a scope.

### 5.3 Proposal Approval Request

An immutable canonical request binding the exact proposal and maximum requested business action to all approval-stage context, constraint, construction, policy, software, deployment, identity, and generation inputs.

### 5.4 Independent Approval Decision

An immutable signed or strongly bound `APPROVE`, `DENY`, or `UNKNOWN` result for one exact request, including independently established facts, comparisons, common-mode analysis, uncertainties, validity, and invalidation conditions.

### 5.5 Approval Consumption Record

The Intent Registry's authoritative immutable proof that one exact current `APPROVE` decision was consumed once to create one exact immutable Intent identity under one serialized transition.

### 5.6 Independent Validation Path

A validation path whose effective source, transformation, control, failure, administration, and deployment dependencies satisfy the active policy's independence rule. A separate process or endpoint alone is not independent.

### 5.7 Material Approval Change

Any change that may alter identity, allowedness, economic effect, constraint, requested maximum, approval result, dependent capacity need, route, evidence strength, or common-mode status. Unknown materiality is material.

---

## 6. Safety Invariants

### IAP-INV-001 — Complete Exact Request

Approval evaluates one complete immutable request. Omission, wildcard, ambiguity, hidden default, substitution, union, patch, or partial refresh is not the approved request.

### IAP-INV-002 — Independent Means Failure-Independent

The approval path does not rely solely on proposer-produced or common-mode-corrupted facts. Independence is evaluated by effective source and control path, not process count.

### IAP-INV-003 — Deterministic Restrictive Result

The same complete input set under one policy and generation yields one deterministic result. Missing, stale, conflicting, unverifiable, unsupported, or unknown input yields `DENY` or `UNKNOWN`, never `APPROVE`.

### IAP-INV-004 — Exact Decision Binding

The decision binds the exact Capsule, proposal, construction envelope, candidate command, venue snapshot and decision, policies, generations, scope, software, deployment, environment, account, broker, route, and validity.

### IAP-INV-005 — Approval Is Not Economic Authority

Approval cannot mutate capacity, create headroom, issue authority, classify protection, transmit, clear HALT, or re-arm.

### IAP-INV-006 — Single-Use Serialized Consumption

One current `APPROVE` decision creates at most one immutable Intent through one atomic Intent Registry consumption transition.

### IAP-INV-007 — No Widening or Union

A narrower decision, multiple decisions, or a later more favorable fact cannot be combined to approve broader or different scope.

### IAP-INV-008 — Material Change Invalidates Future Use

A material bound change invalidates the affected unconsumed decision and blocks future new-risk use of dependent consumed lineage until fresh approval and later gates complete.

### IAP-INV-009 — Active Final-Egress Currentness

Final egress actively verifies approval generation, exact consumption, Intent binding, and invalidation without permissive cache inference.

### IAP-INV-010 — UNKNOWN Cannot Create Permission

UNKNOWN approval, input, common-mode status, consumption state, or invalidation state blocks ordinary new risk and cannot be offset by unused capacity.

### IAP-INV-011 — Economic Effect Outlives Approval

Expiry, invalidation, consumption, revocation, or loss of approval never proves non-acceptance, final quantity, cancellation, zero exposure, or releasable capacity.

### IAP-INV-012 — Stale Generations Are Fenced

Old policy, evaluator, approval, registry-writer, deployment, recovery, authority, and egress generations cannot decide, consume, or transmit after a newer applicable generation is committed.

### IAP-INV-013 — Human and Protective Labels Do Not Bypass

Human approval, emergency priority, exit, hedge, close, reduce-only, or protective labels do not substitute for this approval or create protective authority or reserve.

### IAP-INV-014 — Recovery Does Not Revive

Restart, replay, restore, rollback, source recovery, approval-service recovery, or Intent Registry recovery cannot revive a decision, Intent permission, authority, or live state.

### IAP-INV-015 — Evidence Is Not Prevention

Documents, logs, signatures, audit, replay, or successful prior decisions do not replace current enforcement at Intent registration and final egress.

---

## 7. Authority Ownership and Separation

| Action | Decision owner | Transition/enforcement owner | Prohibited combination |
|---|---|---|---|
| Propose action | Decision Service | none | proposer cannot approve or register its own proposal |
| Govern approval policy | separated safety-configuration governance | ADR-002-014 activation | proposer or runtime approver cannot activate policy |
| Validate approval facts | Independent Approval Service | none | service cannot mutate Intent, capacity, authority, or broker state |
| Produce approval decision | Independent Approval Service | none | `APPROVE` is eligible for consumption only |
| Consume approval and register Intent | none | Intent Registry | registry cannot invent, widen, or reevaluate a decision |
| Grant aggregate-risk allocation | Aggregate Risk Authority | RCL admits exact decision | approval cannot create risk headroom |
| Commit capacity | none | RCL only | approval and Intent Registry cannot mutate capacity |
| Classify protection | Protective Action Controller under ADR-002-001 | RCL and final egress verify | approval cannot self-label protection |
| Issue live authority | Safety/Live Authorization authorities | final egress verifies | approval service cannot issue authority |
| Transmit | Execution Coordinator requests | Broker Adapter / Egress Gateway | approval identity cannot hold usable route and credential |
| Re-arm | ADR-002-007/015 governed workflow | Live Authorization and final egress | approval-service recovery cannot re-arm |

The Independent Approval Service and Intent Registry SHALL NOT hold a usable live broker credential, signer, session, route, or endpoint capability. Combined read/trade credentials remain a declared ADR-002-013 common mode and must be consumed through a constrained service without an order route.

---

## 8. Trading Approval Policy Contract

The policy SHALL define:

- exact proposal and decision types and their canonical schemas;
- complete required fields and explicit absence semantics;
- approved Critical Input, venue constraint, construction, broker, profile, envelope, and human-governance dependencies;
- independent recomputation and comparison rules for account, instrument, direction, quantity, unit, price/order constraints, economic-effect envelope, environment, route, and requested maximum;
- source, parser, mapping, library, model, administrator, deployment, credential, network, cache, clock, and registry common-mode rules;
- deterministic decision logic and `DENY`/`UNKNOWN` precedence;
- allowed scope and maximum authority represented by the resulting Intent;
- validity, age, time, generation, invalidation, correction, and dependency-closure rules;
- Intent consumption, deduplication, concurrency, and replay behavior;
- compatibility, software, evaluator, verifier, and deployment requirements;
- evidence, metrics, alerts, residual-risk approval, and scope-reduction requirements.

Policy materiality and dependency closure are policy-owned. The proposer, approval evaluator, Intent Registry, consumer, or operator cannot self-exempt a field or dependency. Unknown materiality is material.

The policy is an immutable safety artifact under ADR-002-014. Activation does not approve a proposal, create an Intent, or establish current input validity.

---

## 9. Proposal Approval Request Contract

Every request SHALL bind at least:

- request identity, nonce, canonical digest, predecessor, cause, and creation generation;
- proposer identity, Decision Service build, strategy, model/rule identity, and proposal identity;
- exact environment, Safety Cell, legal portfolio, account, instrument, contract, venue, broker, route, action class, and operating mode;
- direction, position effect, quantity, unit, multiplier, currency, price/order constraints, expiration, and maximum Economic Effect Envelope;
- Decision Context Capsule identity and digest;
- Authorized Construction Envelope and candidate Canonical Broker Command identities and digests;
- Venue Constraint Snapshot and Order Admissibility Decision identities and digests;
- Hard Safety Envelope, Runtime Safety Profile, Trading Approval Policy, Critical Input Policy, Venue Constraint Policy, Order Construction Policy, Human Authority Policy, Broker Capability Profile, and compatibility identities and digests;
- context, constraint, construction, approval, profile, recovery, time, deployment, credential, route, HALT, and revocation generations;
- required independent facts, validation paths, common-mode declarations, residual risks, and scope reductions;
- requested validity, maximum age, consumption rule, and invalidation set;
- explicit declaration that the request and any result create no capacity, authority, protection, transmission, or re-arm permission.

An absent, empty, wildcard, unknown, stale, conflicting, or unverifiable required scope or maximum is incomplete and cannot yield `APPROVE`.

The request is immutable. Any field change creates a new identity and restarts approval. Requests cannot be patched, partially refreshed, intersected, unioned, or widened.

---

## 10. Independent Evaluation and Common-Mode Control

The Independent Approval Service SHALL:

1. verify the request schema, signature, canonical digest, completeness, compatibility, age, policy, and current generation;
2. verify every bound artifact identity, digest, generation, scope, validity, and invalidation state;
3. obtain or verify safety-critical facts through approved independent paths;
4. independently recompute or verify account, instrument, direction, quantity, unit, price/order constraints, venue admissibility, command semantics, and conservative economic-effect bounds applicable at approval;
5. compare independently established facts and results to the request without permissive rounding, coercion, fallback, or hidden default;
6. evaluate dependency overlap and common-mode failure across sources, parsers, mappings, libraries, models, caches, registries, administrators, deployments, networks, credentials, and clocks;
7. apply approved freshness, rate-of-change, range, cross-field, provenance, state, last-known-good consistency, and source-authority rules;
8. retain every discrepancy, uncertainty, residual risk, and scope reduction;
9. emit `DENY` or `UNKNOWN` on missing proof, mismatch, stale state, unsupported semantics, unresolved common mode, unapproved residual risk, or evaluator failure;
10. produce one immutable decision without mutating the request or downstream state.

The proposer cannot select a more favorable independent source, policy version, evaluator, fallback, or residual-risk disposition. Two services sharing the same effective failure path do not create independence. Recalculation with the same corrupted implementation is not validation.

Where independent corroboration is unavailable, SAFE-034 and ADR-002-018 require independent review of the limitation, explicit additional validation, and a live scope no broader than the demonstrated conservative residual. Availability pressure cannot waive this rule.

---

## 11. Decision Semantics

The decision SHALL contain:

- exact request identity and digest;
- active policy, Trading Approval Generation, evaluator, verifier, dependency-registry, software, deployment, and compatibility identities;
- independently established facts and canonical comparison results;
- source and transformation lineage, common-mode analysis, uncertainties, discrepancies, residual risks, and scope reductions;
- exact approved Intent envelope and maximum requested effect when result is `APPROVE`;
- `APPROVE`, `DENY`, or `UNKNOWN` with deterministic reason codes;
- issue receipt anchor, maximum consumer age, expiry, invalidation generation, and invalidation conditions;
- issuer identity, signature or strong binding, and evidence receipt;
- explicit non-authority claims.

`APPROVE` means only: the exact request is eligible to be consumed once by the Intent Registry while every binding remains current. It is not equivalent to `AUTHORIZED_FOR_CAPACITY`, capacity commitment, Live Authorization, capability issuance, or transmission.

`DENY` is terminal for the request. `UNKNOWN` is restrictive and requires new evidence or a new request; repeated evaluation, timeout, majority vote, unused capacity, human preference, prior success, or an expected broker rejection cannot promote it.

A decision cannot be edited. A corrected or newer result is a new decision and explicitly supersedes the prior decision without erasing its evidence.

---

## 12. Intent Registration and Single-Use Consumption

The Intent Registry SHALL atomically:

1. establish one current Trading Approval Generation and registry-writer generation;
2. verify the decision is `APPROVE`, complete, current, unexpired, unrevoked, unconsumed, compatible, and in scope;
3. revalidate the exact request, proposal, Capsule, construction, venue decision, policy, software, deployment, recovery, time, HALT, and invalidation bindings;
4. verify the proposed Intent is byte-for-byte or canonically equivalent to the approved Intent envelope and no field is added, defaulted, widened, or substituted;
5. reserve the decision identity against concurrent consumption;
6. create one globally unique immutable Intent identity;
7. transition that Intent from `PROPOSED` to `APPROVED` and write one Approval Consumption Record in the same authoritative transaction;
8. make duplicate identical commands return the same record without creating another Intent, and reject conflicting commands;
9. durably expose the consumption and Intent binding before any downstream capacity request.

The transaction SHALL be linearizable or equivalently fenced. A database uniqueness constraint without authoritative generation fencing is insufficient if stale writers can still create an Intent or dependent effect.

The Approval Consumption Record SHALL bind the decision, request, Intent, policy/generation, writer epoch, transaction revision, receipt time, invalidation state, and result. It grants no downstream authority.

One approved Intent may later produce only the attempts allowed by ADR-002-005 and its exact approved semantics. Every attempt independently requires current aggregate-risk, action-flow, RCL, conformance, authority, live-scope, capability, and egress gates. Single consumption is not a single-send promise and cannot be used to bypass attempt-level controls.

---

## 13. Exact Binding Through the Pipeline

The following identities and digests SHALL remain transitively bound:

```text
Decision Context Capsule
  -> immutable proposal and construction envelope
  -> candidate Canonical Broker Command
  -> exact Venue Constraint Snapshot and Order Admissibility Decision
  -> Proposal Approval Request
  -> Independent Approval Decision
  -> Approval Consumption Record and immutable Intent
  -> Aggregate Risk Decision
  -> Action Flow Decision
  -> RCL commitments and Action Flow Permit
  -> Order Conformance Proof
  -> Safety Authority / Live Authorization / Transmission Capability
  -> actual outbound broker representation
```

No downstream stage may use approval to widen, repair, reinterpret, refresh, or reconstruct a more favorable proposal. Later gates may only narrow or deny. A later material change requires a new upstream chain as defined by the owning ADR.

The Order Conformance Proof SHALL include the exact approval decision and consumption-record identities and prove that the candidate, Intent, capacity commitment, and actual downstream request remain inside the approved envelope.

---

## 14. Invalidation and Dependency Closure

Material invalidation triggers include:

- correction, retraction, source-continuity break, or Critical Input degradation;
- venue/session/tradability/account/margin/borrow/settlement or Broker Capability change;
- proposal, mapping, construction envelope, candidate command, route, endpoint, credential, or environment change;
- policy, profile, envelope, software, evaluator, verifier, dependency registry, compatibility, deployment, or Trading Approval Generation change;
- common-mode discovery, security compromise, stale writer, recovery generation, HALT, or revocation change;
- age, expiry, time-health, scope, residual-risk, or evidence-validity breach.

The system SHALL compute the complete dependency closure across requests, decisions, consumption records, Intents, risk/flow decisions, commitments, proofs, authorities, capabilities, pending attempts, egresses, and protection.

Before consumption, invalidation makes the decision ineligible. After consumption but before future send, it denies dependent new-risk use and invokes the required restriction, quarantine, containment, HALT, or fresh-chain workflow. If a send may already have crossed the irreversible boundary, the attempt is potentially live and its worst credible economic effect remains capacity-covered.

An invalidation event may be evidence, but absence of the event is not proof of currentness.

---

## 15. Final-Egress Enforcement and Active Currentness

Immediately before every broker-directed new-risk send, final egress SHALL actively verify:

1. exact approval request, decision, consumption record, and Intent identities and digests;
2. current Trading Approval Policy and Generation;
3. decision result `APPROVE`, exact approved envelope, and current validity;
4. single authoritative consumption into the same Intent and no conflicting consumption;
5. current dependency and invalidation state across context, constraints, construction, policies, software, deployment, recovery, time, HALT, and revocation;
6. exact Order Conformance Proof binding to the approval lineage;
7. all independently owned aggregate-risk, action-flow, RCL, authority, live-scope, capability, and outbound-conformance gates.

The proof SHALL be active and bounded. Cached `APPROVED`, local Intent state, TTL, heartbeat, service health, last-known generation, prior verification, eventual consistency, or absence of an invalidation event is not sufficient.

Final egress verifies facts and conformance; it does not rerun strategy logic, invent approval, choose a more favorable input, mutate Intent, or widen scope. Failure or ambiguity is denial.

If invalidation races capability claim or first outbound byte and order cannot be proved, the attempt is potentially live, blind retry is prohibited, and capacity remains committed or quarantined until proof-governed resolution.

---

## 16. UNKNOWN, Protective Actions, and Economic Continuity

An `UNKNOWN` approval or unknown request completeness, independent-input status, common-mode scope, generation, consumption, or invalidation state blocks ordinary new risk. Available RCL capacity cannot convert uncertainty into permission.

Approval does not classify an action as protective. A close, exit, hedge, cancel, reduce-only, emergency, or high-priority label must still pass the applicable ADR-002-001/011/019/020/021/022 rules. Priority is not reserved protective capacity.

If the ordinary approval path is unavailable, no ordinary new-risk proposal may advance. A separately pre-authorized protective path may operate only inside its exact exclusive lease, capacity, classification, currentness, broker, and final-egress constraints. Uncertainty denies the protective send; it does not justify an ordinary fallback.

Missing ACK is not proof of broker non-acceptance. Cancel ACK is not Final Quantity Proof. Approval expiry, invalidation, revocation, denial, or service outage does not cancel broker state or release RCL capacity. Existing and possible economic effects follow evidence, reconciliation, and Final Quantity Proof.

---

## 17. Concurrency, Partition, and Stale-Writer Fencing

Concurrent approval evaluators may compute decisions only under one exact policy and generation; conflicting results are retained and make the request `UNKNOWN` until authoritatively resolved. Majority or newest-arrival selection is not automatically authoritative.

Only the current fenced Intent Registry writer may consume a decision and create an Intent. Old writers, restored databases, replay workers, approval-service instances, deployment generations, credential holders, and egress principals are potentially active until hard fenced.

During loss of approval-generation currentness, independent input availability, Intent Registry serialization, required invalidation state, or final-egress currentness, no new approval may be consumed and no dependent new-risk send may occur.

A broker-reachable partition does not permit egress to trust an old consumed approval. Only an approved independently fenced currentness protocol may continue; otherwise the affected scope denies new risk. Protective leases remain subject to their separate precommitment and local monotonic constraints.

---

## 18. Security and Failure-Domain Requirements

The proposer, approval evaluator, policy authority, independent input path, Intent Registry writer, aggregate-risk authority, RCL writer, Live Authorization issuer, final egress, and evidence/replay identities SHALL be separated according to their effective authority and common-mode risk.

Security review SHALL cover:

- request/decision substitution, digest collision, signature confusion, parser differential, downgrade, and canonicalization attacks;
- proposer-controlled source selection, policy selection, residual-risk declaration, or evaluator routing;
- compromised approval evaluator, verifier, dependency registry, Intent Registry writer, or invalidation publisher;
- duplicate consumption, stale writer, split brain, restore, rollback, and replay;
- combined read/trade credentials, SSRF, proxy, redirect, SDK, service-mesh, and downstream route bypass;
- false independence caused by shared source, library, mapping, administrator, identity, clock, network, cache, deployment, or vendor path;
- denial-to-approval failover, permissive default, timeout promotion, or evidence-only enforcement.

Suspected compromise makes affected approval and consumption state untrusted, blocks future new risk, preserves possible economic effect, advances generations, fences old paths, and requires fresh governance and re-arm.

---

## 19. Time, Expiry, and Validity

Freshness and validity SHALL use ADR-002-008 Trustworthy Time. Cross-host monotonic values are never directly subtracted. Consumers establish age from a local receipt anchor plus conservative transport uncertainty and source-time semantics.

The policy SHALL define separate maximum ages for request, decision, consumption currentness, independent facts, Capsule, venue decision, candidate command, and dependent proof. A future timestamp, negative age, missing time, clock discontinuity, unknown transport, or untrusted Time Health is restrictive.

Expiry prevents future consumption or send. It does not expire an Intent's history, broker effect, order, fill, exposure, UNKNOWN state, or capacity commitment.

---

## 20. Recovery and Non-Revival

Startup and recovery begin unable to approve, consume, or transmit until ADR-002-017 establishes the current Recovery Generation, dependencies, inventory, obligations, and readiness scope.

Restored requests, decisions, consumption records, and Intents are evidence only until their complete current binding and authoritative history are proven. A stale, duplicated, forked, or incompletely restored consumption namespace blocks new risk and expands reconciliation scope.

Approval-service health, source recovery, policy rollback, database restore, replay match, Intent Registry recovery, or broker reconnect does not revive approval or live authority. Material recovery requires fresh generation fencing, current artifacts, new approval where required, and the complete ADR-002-007/015 re-arm chain. There is no automatic re-arm.

---

## 21. Evidence, Metrics, and Alerts

The system SHALL retain:

- every Trading Approval Policy and Generation;
- request, proposal, Capsule, construction, constraint, broker, policy, software, deployment, and compatibility bindings;
- all independent observations, recomputations, comparisons, common-mode analyses, residual risks, and scope reductions;
- every `APPROVE`, `DENY`, and `UNKNOWN` decision with deterministic reasons;
- Intent Registry writer generation, consumption command, transaction, duplicate/conflict result, Consumption Record, and Intent transition;
- invalidation, dependency closure, authority/egress receipt, race, quarantine, and recovery lineage;
- bypass, replay, substitution, stale-writer, direct-route, and failed-currentness attempts.

Metrics SHALL include request/decision age, result counts, independent mismatch, common-mode denial, unknown materiality, invalidation latency, duplicate consumption, writer conflict, stale-generation denial, decision-to-consumption latency, consumed-to-egress age, currentness failures, and approval bypass attempts.

Critical alerts include proposer-only approval, false independence, incomplete request approved, decision mutation, multiple Intent creation, stale decision consumption, invalidation missed at egress, approval identity holding a broker route, UNKNOWN promoted, capacity released on approval expiry, or approval recovery re-arming live scope.

ADR-002-016 governs durable custody and isolated replay. Evidence and replay have no approval, Intent-transition, capacity, authority, protection, or transmission permission.

---

## 22. Failure Modes and Required Responses

| Failure | Required response |
|---|---|
| Required request field absent or wildcard | `DENY` or `UNKNOWN`; no consumption |
| Proposer and approver share effective validation path | treat as common mode; deny or apply independently approved residual-risk scope reduction |
| Independent value mismatches proposal | retain both; deny request; do not coerce |
| Evaluators disagree | `UNKNOWN`; no majority/newest promotion |
| Proposal or bound artifact changes | new request and decision; invalidate affected old chain |
| Two consumers race one decision | one authoritative Intent at most; loser receives duplicate/conflict denial |
| Stale Intent Registry writer consumes | reject/fence; restrict affected scope and investigate |
| Decision invalidates after consumption | block future dependent new risk; preserve economic lineage and capacity |
| Egress cannot prove approval currentness | deny send; no cached fallback |
| Approval partition while broker remains reachable | deny new risk unless approved fenced currentness is independently proven |
| Approval expires with live/unknown order | deny future use; order/effect/capacity remain |
| Missing ACK after approved send | potentially live; no blind retry or capacity release |
| Cancel ACK arrives | do not treat as Final Quantity Proof |
| Approval component gains broker route | isolate, HALT/restrict affected scope, rotate/fence, reconcile |
| Recovery finds old approved decisions | evidence only; never auto-consume or re-arm |

---

## 23. Rejected Alternatives

### 23.1 Proposer Signature Equals Approval

Rejected because integrity and independence are different properties.

### 23.2 Separate Process Equals Independent Validation

Rejected because common sources, code, control, and failure paths can corrupt both.

### 23.3 Approve an Envelope and Fill Fields Later

Rejected because later account, route, quantity, price, venue, or command selection changes the approved action.

### 23.4 Approval Boolean in Intent Is Sufficient

Rejected because it does not prove exact lineage, single consumption, generation, or current invalidation state.

### 23.5 Cache Approval Until TTL

Rejected because material revocation or correction may occur inside the TTL.

### 23.6 Multiple Approvals May Be Unioned

Rejected because individually narrow decisions do not prove the combined effect.

### 23.7 Capacity Can Cover UNKNOWN Approval

Rejected because capacity bounds economic effect but cannot validate a missing preventive authorization.

### 23.8 Approval May Directly Create Live Authority

Rejected because it collapses business review, risk, capacity, arming, and egress.

### 23.9 Human or Protective Label May Override

Rejected because labels do not prove independent facts, protective classification, or reserved capacity.

### 23.10 Recovery May Reuse Prior Approval

Rejected because dependencies, generations, evidence, state, and authority may have changed.

### 23.11 Audit or Replay Is Sufficient

Rejected because after-the-fact reconstruction does not prevent consumption or transmission.

---

## 24. Consequences

### 24.1 Positive

- automated approval has a complete enforceable contract distinct from human governance;
- proposer corruption and common-mode validation failures become explicit;
- request mutation and approval replay cannot silently create another Intent;
- Intent registration has one authoritative serialized owner;
- approval cannot bypass risk, flow, capacity, authority, protection, or egress;
- invalidation reaches final egress without erasing possible economic effect;
- recovery and replay remain non-authorizing.

### 24.2 Negative

- approval availability and latency become explicit safety dependencies;
- independent data and implementation paths may be expensive or unavailable;
- material changes restart approval and may reduce throughput;
- Intent Registry consumption requires strongly fenced serialization;
- final egress must validate another active-currentness contract;
- common-mode discovery can suspend broad scope;
- policy, schema, evaluator, and dependency registries require governed lifecycle management.

These costs are accepted because a fast but non-independent or replayable approval is not a preventive safety control.

---

## 25. Acceptance Cases

The following cases are mandatory and map one-to-one to `IAP-EV-001` through `IAP-EV-012`. Written cases are not completed evidence.

### IAP-AC-001 — Complete Exact Request

Omitted, defaulted, wildcard, ambiguous, partially refreshed, patched, unioned, or substituted request fields cannot yield or preserve `APPROVE`.

### IAP-AC-002 — Independent Validation and Common Mode

Proposer-only values and paths sharing source, parser, mapping, library, administrator, cache, network, clock, deployment, or registry common modes cannot masquerade as independent approval.

### IAP-AC-003 — Deterministic Restrictive Decision

Identical complete inputs produce the same result, while missing, stale, conflicting, unsupported, or unknown input produces `DENY` or `UNKNOWN` without permissive fallback.

### IAP-AC-004 — Exact Artifact and Scope Binding

Account, instrument, direction, quantity, unit, price, Capsule, venue decision, construction, broker, route, environment, policy, generation, software, or deployment substitution invalidates the decision.

### IAP-AC-005 — Single-Use Intent Consumption

Concurrent, duplicate, replayed, cross-scope, and stale-writer consumption produces at most one exact immutable Intent and one authoritative Consumption Record.

### IAP-AC-006 — No Widening or Authority Escalation

Approval cannot be unioned, widened, converted into capacity/headroom, classify protection, issue authority/capability, transmit, clear HALT, or re-arm.

### IAP-AC-007 — Invalidation Dependency Closure

Material correction, policy/generation change, compromise, or dependency degradation blocks every affected future new-risk use through Intent, authority, and egress while retaining possible economic effect.

### IAP-AC-008 — Active Final-Egress Currentness

Final egress rejects cached, stale, invalidated, mismatched, unconsumed, multiply consumed, wrong-Intent, or unverifiable approval lineage and cannot infer currentness from absence of events.

### IAP-AC-009 — UNKNOWN, Protective, and Human Confinement

UNKNOWN approval plus available capacity, human preference, emergency/exit/hedge/protective labels, or priority cannot create ordinary or protective permission.

### IAP-AC-010 — Partition and Stale-Generation Fencing

Approval/registry/control-plane partition with broker route alive, old evaluators, stale registry writers, rollback, and split brain cannot consume or transmit under an old generation.

### IAP-AC-011 — Economic Continuity and Broker Ambiguity

Expiry, invalidation, denial, missing ACK, cancel ACK, timeout, or service outage cannot erase order/exposure/UNKNOWN state or release capacity; ambiguous sends remain potentially live.

### IAP-AC-012 — Recovery, Evidence, and Non-Revival

Restart, restore, replay, source recovery, approval recovery, or Intent Registry recovery cannot auto-consume, revive permission, or re-arm; evidence reconstructs without acting.

---

## 26. Requirements Traceability

| Requirement | ADR-002-023 allocation |
|---|---|
| SAFE-001, SAFE-003 | Missing, stale, unsupported, conflicting, or unknown approval state is restrictive (§§8–11, 16) |
| SAFE-010, SAFE-011 | Independent approval is a mandatory non-bypassable pre-trade gate, with final-egress enforcement (§§10–15) |
| SAFE-013, SAFE-015 | Approval cannot grant aggregate risk or mutate capacity; RCL remains sole capacity authority (§§7, 12–16) |
| SAFE-020, SAFE-021 | One decision is consumed once into one immutable Intent; later attempts retain exact lineage (§§12–13) |
| SAFE-030, SAFE-031, SAFE-034 | Approval uses trustworthy attributable facts, true independent validation, and explicit common-mode analysis (§§9–11) |
| SAFE-032, SAFE-033 | Approval binds exact current venue admissibility and canonical command/construction semantics (§§9–13) |
| SAFE-035 | Request, decision, consumption, and dependency freshness use Trustworthy Time (§19) |
| SAFE-040, SAFE-043 | Protective labels cannot bypass approval, capacity, constraints, or egress; unavailable protection becomes containment (§16) |
| SAFE-041 | Approval, Intent transition, capacity, authority, and transmission remain separately owned (§7) |
| SAFE-044 through SAFE-048 | Startup, live scope, partitions, generations, and recovery fail closed without revival (§§15, 17, 20) |
| SAFE-050 | Policy, schema, evaluator, compatibility, and generation are immutable governed artifacts (§8) |
| SAFE-051, SAFE-052 | Complete decision and consumption evidence supports independent reconstruction without becoming prevention (§21) |

---

## 27. Open Implementation Questions

The architecture is selected. These mechanism and parameter choices remain open while Proposed:

1. Which canonical Trading Approval Policy, Proposal Approval Request, Independent Approval Decision, and Approval Consumption Record schemas are approved?
2. Which policy language and deterministic evaluator/verifier implementations provide parser and semantic diversity?
3. Which independent source, transformation, mapping, registry, clock, and administrative paths validate each safety-critical fact?
4. Which common-mode taxonomy and residual-risk process determine required scope reduction when independent corroboration is unavailable?
5. Which monotonic Trading Approval Generation and invalidation graph fence stale evaluators, writers, Intents, authorities, and egresses?
6. Which Intent Registry storage, consensus, idempotency, and writer-fence mechanism atomically consumes one decision into one Intent?
7. Which active currentness protocol lets Intent Registry and final egress prove approval, consumption, and invalidation without permissive caches or circular dependencies?
8. Which signature, digest, canonicalization, compatibility, and evidence-receipt formats resist substitution and parser differential?
9. Which failure domains and identities separate proposer, approval, independent input, policy activation, Intent Registry, RCL, authority, egress, and evidence paths?
10. Which approval classes require additional ADR-002-015 human approval without allowing human approval to replace automated validation?
11. How do corrections and late discoveries bound dependency closure across already consumed Intents and potentially live attempts?
12. What `B_approval_invalid_to_intent`, `B_approval_invalid_to_egress`, `B_approval_generation_fence`, `MAX_proposal_approval_request_age_ms`, and `MAX_independent_approval_decision_age_ms` values are approved?

Unresolved questions reduce authority or keep affected scope non-live. They do not permit a simpler permissive implementation.

---

## 28. Approval Gate

ADR-002-023 SHALL remain **Proposed** until all of the following are complete:

1. Trading Approval Policy, Proposal Approval Request, Independent Approval Decision, and Approval Consumption Record schemas are approved.
2. Canonicalization, deterministic evaluator, independent verifier, compatibility, dependency registry, and common-mode mechanisms are implemented and security-reviewed.
3. Every safety-critical fact has an approved independent validation path or an independently approved explicit residual risk with demonstrated scope reduction.
4. Intent Registry consumption is linearizable or equivalently fenced, single use, idempotent, recovery-safe, and incapable of creating a second or widened Intent.
5. Approval, Intent transition, aggregate risk, action flow, RCL, authority, live scope, capability, and final egress remain separately owned and non-bypassable.
6. Active approval/consumption currentness reaches Intent Registry and every final egress without permissive cache inference; send/invalidation races are bounded and conservative.
7. Stale evaluator, policy, registry writer, deployment, recovery, authority, and egress generations are hard fenced.
8. UNKNOWN, partial request, common mode, partition, timeout, human override, protective label, and available capacity cannot create permission.
9. Expiry, invalidation, compromise, recovery, replay, missing ACK, and cancel ACK preserve economic continuity and cannot release capacity or revive authority.
10. `IAP-EV-001` through `IAP-EV-012` and all applicable CII, VTG, IOC, ARE, AFG, RCLP, EGRESS, HAG, ERI, SBR, TIME, SA, RC, BC, and cross-system evidence pass at required levels and receive independent review.
11. All applicable numeric and age bounds are approved and measured under concurrency, partition, rollback, compromise, recovery, and fault injection.
12. No Critical or Major review finding remains unresolved, and canonical RFC/ADR/VER/Evidence Register traceability is complete.
13. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Authorship, schema drafting, `APPROVE` output, successful Intent creation, signatures, logs, written cases, registered evidence, or EV-L0 document review do not satisfy this gate. This ADR authorizes architecture and implementation planning only. It does not authorize acceptance, restricted-live operation, production operation, broker transmission, or automatic re-arm.
