# ADR-002-014 — Hard Safety Envelope and Runtime Safety Profile Governance

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Hard Safety Envelope and Runtime Safety Profile artifact contracts, semantic validation, authority separation, approval, versioning, atomic activation, restrictive precedence, compatibility fencing, distribution, rollback, restore, expiry, evidence, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-003, SAFE-004, and SAFE-050; RFC-002 §§9.1, 10.12, 10.18, 19.3, and 28; ADR-002-007 §§4–6, 10, 12, and 25; ADR-002-009 §§10–12; ADR-002-012 §§5.4, 10, 15, and 20
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-035, SAFE-041, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-013

---

## 1. Decision

The TOS SHALL govern the **Hard Safety Envelope** and each **Runtime Safety Profile** as separate immutable, authenticated, content-addressed safety artifacts with independent authority, explicit generations, canonical semantics, and fail-closed activation.

The Hard Safety Envelope is the maximum authority the system is technically and organizationally permitted to grant. A Runtime Safety Profile may only reduce that authority for one exact live scope. Neither artifact grants live authority by itself.

For every governed dimension:

```text
Transmission Capability
    <= Live Authorization
    <= active Runtime Safety Profile
    <= active Hard Safety Envelope
```

Every activation SHALL satisfy the following break-before-make safety order. Section 13 is the authoritative operational sequence: candidate classification, construction, approval, and validation may occur while the predecessor remains active because those steps grant the candidate no authority, but the predecessor SHALL be revoked or suspended before the candidate becomes eligible for activation or fresh arming.

1. validate the complete immutable artifact set against the current envelope, software, broker, time, deployment, and evidence contracts;
2. revoke or suspend prior permission-creating authority for the affected scope before candidate activation eligibility;
3. commit one exact Profile Generation and activation record through the ADR-002-012 Safety Commit Log ordering;
4. require every permission-creating consumer and final egress to prove the same committed generation and artifact digests;
5. issue fresh Live Authorization through ADR-002-007 only after the new generation is active and all readiness gates pass.

Partial activation, mixed generations, unknown fields, missing values, incompatible consumers, ambiguous encodings, stale approvals, rollback, restore, cache recovery, or “latest” resolution SHALL grant zero new-risk authority.

An authority-reducing emergency transition MAY deny or narrow future authority before the ordinary approval workflow completes only when it is mechanically proven monotonic in every affected dimension. It SHALL advance restrictive generations, cannot release capacity or cancel required protection, and cannot automatically revert or re-arm.

The Risk Capacity Ledger remains the sole capacity mutation and serialization authority. The Safety Profile Validator validates and attests configuration; it does not create capacity, issue Live Authorization, or transmit orders.

---

## 2. Context

RFC-001 requires complete, semantically valid, approved Safety Profiles inside an independently governed Hard Safety Envelope. RFC-002 identifies a Hard Safety Envelope Registry and Safety Profile Validator. ADR-002-007 requires semantic validation, atomic activation, separated approval, and no automatic re-arm.

Those obligations still leave unsafe implementation choices unless the artifact, generation, activation, compatibility, and rollback protocols are explicit. Examples include:

- YAML fields loading successfully while a quantity multiplier is interpreted in different units by two consumers;
- a profile author omitting a newly introduced Critical field so an older permissive default applies;
- one region using the new position limit while final egress uses the old order-rate limit;
- a deployment resolving `latest` to different profile objects at different times;
- an envelope expansion silently enlarging an already active Runtime Safety Profile;
- a nominally restrictive change increasing authority along an unexamined risk dimension;
- a rollback restoring an older, broader, or software-incompatible profile;
- a datastore restore reviving an activation record or approval that belonged to a prior generation;
- an emergency override reducing a limit and then automatically expiring back to a broader profile;
- one operator authoring, approving, deploying, and arming an authority increase;
- configuration distribution success being treated as activation without quorum ordering;
- profile expiry or invalidation being treated as release of orders, exposure, or capacity.

Configuration is an authority boundary, not an operational convenience. This ADR defines the mechanism-independent safety contract.

---

## 3. Decision Drivers

1. No configuration representation, omission, race, or rollback may expand authority silently.
2. Hard Safety Envelope governance must remain independent from strategy, deployment, and live arming.
3. Semantic equivalence must be deterministic across every permission-creating consumer.
4. Atomic activation must mean one committed generation, not merely simultaneous file delivery.
5. Restrictive changes must dominate permissive work without erasing economic effect.
6. Authority-increasing changes must require explicit separated approval and fresh re-arm.
7. Recovery, restore, rollback, expiry recovery, or cache refill must not revive prior authority.
8. Missing, unknown, incompatible, or contradictory configuration must reduce authority or keep scope non-live.
9. Evidence and replay must prove enforcement but cannot substitute for it.

---

## 4. Scope and Non-Scope

This ADR decides:

- the normative content and identity of Hard Safety Envelope and Runtime Safety Profile artifacts;
- canonical encoding, authentication, version, digest, and reference rules;
- governance roles and prohibited authority combinations;
- semantic validation and consumer-compatibility requirements;
- profile and envelope lifecycle state machines;
- activation, restriction, concurrency, distribution, rollback, restore, and expiry behavior;
- economic-state continuity and final-egress enforcement;
- acceptance cases and evidence obligations.

This ADR does not select:

- a configuration language, repository, signing product, workflow product, or secret store;
- a consensus implementation beyond ADR-002-012's selected mechanism class;
- numeric safety limits;
- organization-specific human names or approval quorum sizes;
- a broker or deployment topology;
- strategy parameters that cannot affect safety authority.

Any field or artifact capable of changing live permission, capacity bounds, protective guarantees, state confidence, broker scope, failure response, or safety timing is safety configuration regardless of where it is stored or what it is named.

---

## 5. Definitions

### 5.1 Hard Safety Envelope

An independently governed immutable artifact that defines the maximum operational authority, mandatory safety dimensions, permitted semantics, prohibited states, and compatibility constraints for a declared scope.

### 5.2 Runtime Safety Profile

An immutable artifact that selects a strictly equal-or-narrower operating scope and limits under one exact Hard Safety Envelope generation.

### 5.3 Safety Configuration Bundle

The complete closed set of artifacts required to evaluate safety authority for one scope, including the Hard Safety Envelope, Runtime Safety Profile, Broker Capability Profile, Verification Profile, Recovery Barrier Policy, ADR-002-018 Critical Input Policy, ADR-002-019 Venue Constraint Policy, ADR-002-020 Order Construction Policy, ADR-002-021 Aggregate Risk Policy and Adverse Scenario Set, ADR-002-022 Action Flow Policy, ADR-002-023 Trading Approval Policy, ADR-002-024 Currentness Policy, Failure-Domain Allocation Matrix, applicable time/calendar data, software compatibility manifests, and referenced policy objects.

### 5.4 Profile Generation

A monotonically advancing identity for one committed Safety Configuration Bundle and activation scope. It is not a mutable version label and cannot be reused after rejection, revocation, rollback, restore, or supersession.

### 5.5 Canonical Semantic Digest

A digest over the normalized meaning of an artifact, including schema, units, types, explicit defaults, scope, references, expressions, and ordering rules. A byte digest alone is insufficient when two encodings can produce different meaning.

### 5.6 Consumer Compatibility Manifest

An authenticated declaration of the exact schemas, fields, units, calculations, constraints, and failure semantics a permission-creating consumer implements.

### 5.7 Activation Record

A quorum-committed record binding the Profile Generation, complete artifact digests, scope, approvals, compatibility attestations, validity interval, predecessor generation, and restrictive-generation effects. It grants no Live Authorization by itself.

### 5.8 Restrictive Override

A separately authorized, mechanically monotonic transition that only denies or narrows future authority. It cannot expand any credible dimension, release capacity, erase economic effect, issue Live Authorization, or schedule automatic reversion.

### 5.9 Authority-Increasing Change

Any change for which at least one credible interpretation permits an identity, action, scope, duration, rate, quantity, notional, risk vector, broker behavior, fallback, or failure response that was previously denied or more constrained.

When monotonic direction cannot be proven, the change is authority increasing.

---

## 6. Safety Invariants

### SPG-INV-001 — Envelope Dominance

No Runtime Safety Profile or downstream authorization may exceed, redefine, disable, omit, or reinterpret a Hard Safety Envelope constraint.

### SPG-INV-002 — Complete Closed Bundle

No new-risk authority is created from a partial, unresolved, mutable, or open-ended Safety Configuration Bundle.

### SPG-INV-003 — One Committed Generation

Every permission-creating decision for a scope binds one exact quorum-committed Profile Generation. `latest`, local file state, cache state, or deployment order is not authority.

### SPG-INV-004 — Semantic Agreement

Every permission-creating consumer evaluates the same canonical types, units, scope, formulas, defaults, and constraints. Unknown or incompatible semantics are denial.

### SPG-INV-005 — Atomic Permission

Partial or mixed activation cannot create the union of permissions from old and new generations.

### SPG-INV-006 — Break Before Make

Prior permission-creating authority is revoked or suspended before a changed generation can become eligible for fresh Live Authorization.

### SPG-INV-007 — No Silent Expansion

Envelope expansion, profile expansion, schema change, reference change, or software change grants no additional live authority without explicit approval and governed re-arm.

### SPG-INV-008 — Restrictive Monotonicity

A Restrictive Override only denies or narrows in every credible dimension and cannot later restore broader authority automatically.

### SPG-INV-009 — Rollback and Restore Do Not Revive

Rollback, snapshot restore, disaster recovery, cache recovery, or approval replay cannot reactivate a prior Profile Generation, artifact, approval, or Live Authorization.

### SPG-INV-010 — Separation of Duties

No trading strategy or single principal can unilaterally enlarge the Hard Safety Envelope, approve an authority increase, activate it, and arm the enlarged scope.

### SPG-INV-011 — Existing Economic Effect Persists

Profile restriction, invalidation, expiry, or supersession does not cancel orders, release capacity, expire economic effect, or convert UNKNOWN into safety.

### SPG-INV-012 — Final-Egress Enforcement

Final egress rejects stale, mixed, incompatible, revoked, expired, or uncommitted envelope and profile generations before the first broker-directed byte.

### SPG-INV-013 — Recovery Cannot Re-arm

Time recovery, profile-service recovery, configuration redistribution, deployment health, or restoration of a previously valid artifact cannot automatically re-arm live scope.

### SPG-INV-014 — Evidence Is Not Authority

Approval records, signatures, logs, diffs, dashboards, review tickets, and replay evidence do not create activation, capacity, Live Authorization, or transmission authority.

---

## 7. Canonical Artifact Contract

Every governed artifact SHALL include or bind:

- artifact type, schema identity, schema version, and canonicalization version;
- immutable artifact identity and Canonical Semantic Digest;
- author identity and creation time under ADR-002-008 trustworthy-time rules;
- exact environment, account, portfolio, strategy, instrument, venue, broker, action, and Safety Cell scope;
- all quantities with explicit type, unit, currency, multiplier, precision, rounding, sign, and boundary semantics;
- complete defaults expressed as explicit values; absence is never permissive;
- referenced artifact identities and digests, never floating names or `latest`;
- required software and Consumer Compatibility Manifest versions;
- validity start, expiry, review deadline, and invalidation conditions;
- approval policy identity and collected approval identities;
- predecessor generation and change classification;
- integrity and authenticity evidence.

Unknown fields that can affect authority SHALL be rejected. Duplicate keys, ambiguous aliases, implicit unit conversion, environment interpolation, executable includes, unresolved references, non-deterministic expressions, and parser-dependent behavior are prohibited.

The canonicalization algorithm SHALL make semantically relevant ordering, numeric representation, Unicode, time zone, calendar, set membership, inheritance, and default expansion deterministic. Two consumers unable to reproduce the same Canonical Semantic Digest SHALL not authorize new risk.

---

## 8. Authority and Separation of Duties

| Action | Required authority | Prohibited combination |
|---|---|---|
| Define envelope schema and mandatory dimensions | Independent envelope architecture authority | Runtime strategy or sole profile author |
| Propose Hard Safety Envelope | Envelope author | Sole envelope approver, deployer, and live armer |
| Approve Hard Safety Envelope | Independent envelope approval quorum | Runtime trading identity or unilateral live armer |
| Propose Runtime Safety Profile | Authorized profile author | Strategy self-expanding its authority |
| Approve authority-increasing profile | Independent limit approval quorum | Sole author, deployer, or live armer for that change |
| Validate semantics | Safety Profile Validator | Inventing missing values or expanding the envelope |
| Commit Profile Generation | ADR-002-012 Safety Commit Log transition | Bypassing approval or mutating capacity |
| Distribute artifacts | Configuration distribution service | Declaring activation from delivery success |
| Attest compatibility | Exact consumer identity | Approving its own authority expansion |
| Issue Restrictive Override | Independent restrictive/emergency authority | Expanding, rearming, releasing capacity, or automatic revert |
| Arm live scope | ADR-002-007 governed re-arm | Authoring or solely approving the enlarged limits |
| Enforce transmission | ADR-002-013 Final Egress Trust Boundary | Resolving missing or incompatible configuration permissively |

Approval policy SHALL account for service accounts, automation, repository administration, signing keys, CI/CD, recovery credentials, and workflow administrators. Splitting labels across roles while one principal controls all underlying credentials does not establish separation.

Break-glass authority may HALT or apply a proven Restrictive Override. It SHALL NOT expand the envelope, broaden a profile, waive semantic validation, activate a generation, or re-arm.

---

## 9. Hard Safety Envelope Governance

The Hard Safety Envelope SHALL define at least:

- mandatory aggregate and per-action risk dimensions;
- maximum quantity, notional, leverage, margin, concentration, liquidity, correlation, rate, session, and exposure authority as applicable;
- required worst-case economic-effect functions and conservative aggregation rules;
- permitted instruments, accounts, venues, brokers, order classes, protective actions, and operating modes;
- mandatory trustworthy-time, freshness, evidence-confidence, reconciliation, failure-domain, egress, and broker-capability constraints;
- prohibited fallbacks, implicit defaults, wildcard scope, and unsupported states;
- required protective-capacity and containment guarantees;
- schema and Consumer Compatibility Manifest floors;
- residual-risk ceilings and required independent approvals.

Every envelope change creates a new immutable Envelope Generation. Activation of any new Envelope Generation suspends dependent Runtime Safety Profiles and Live Authorizations until they are revalidated and explicitly re-armed. An envelope expansion does not enlarge existing profiles automatically.

An emergency tightening SHALL revoke affected future authority first. Existing orders, exposure, UNKNOWN state, and capacity remain economic facts requiring containment and reconciliation.

The envelope registry SHALL expose authenticated immutable artifacts and revocation state. It SHALL NOT expose a mutable “current limits” object that can change meaning without a new generation.

---

## 10. Runtime Safety Profile Content

Each Runtime Safety Profile SHALL state every applicable permission and limit explicitly. At minimum it SHALL bind:

- one exact Hard Safety Envelope identity and generation;
- scope across environment, Safety Cell, account, portfolio, strategy, instrument, venue, broker, order type, action class, session, and time;
- per-action and aggregate quantity, notional, risk-vector, margin, leverage, concentration, liquidity, and rate constraints;
- permitted normal, recovery-only, protective, degraded, contained, and halted behaviors;
- protective lease and reserve constraints without treating priority as reserved capacity;
- evidence-confidence and reconciliation thresholds;
- trustworthy-time sources, calendars, freshness, expiry, and holdover rules;
- Broker Capability Profile and failure-domain restrictions;
- allowed software, deployment, workload, credential, route, and egress generations;
- fallback rules, each of which must be no more permissive than the primary rule;
- escalation, suspension, revocation, HALT, and re-arm conditions;
- every numeric bound and reference required for deterministic evaluation.

Wildcards, “all”, “default broker behavior”, “current”, “latest”, inherited environment values, and unspecified Critical fields are prohibited unless the Hard Safety Envelope defines a finite closed interpretation and the artifact includes that expanded set in its semantic digest.

---

## 11. Semantic Validation

The Safety Profile Validator SHALL validate the complete Safety Configuration Bundle, not isolated files. Validation SHALL include:

1. signature, digest, identity, generation, approval, and revocation status;
2. schema completeness and canonical semantic reproducibility;
3. types, units, currencies, multipliers, signs, precision, rounding, overflow, underflow, NaN, infinity, and boundary inclusion;
4. account, instrument, venue, broker, environment, session, and action scope;
5. cross-field and cross-artifact constraints;
6. conservative comparison of every Runtime Safety Profile dimension with the Hard Safety Envelope;
7. maximum credible aggregate effect, concurrent-action union, partial-fill states, replacement overlap, UNKNOWN, external activity, and trapped exposure assumptions;
8. software, parser, schema, Consumer Compatibility Manifest, deployment, and egress compatibility;
9. Broker Capability Profile, Recovery Barrier Policy, Critical Input Policy, source/mapping/lineage contract, and Failure-Domain Allocation consistency;
10. trustworthy-time validity and expiry behavior;
11. authority-direction classification for every change;
12. absence of a bypass through omitted, unknown, deprecated, duplicated, or extension fields.

Validation must produce a deterministic result and reason set for one exact bundle digest. A human review, successful parse, schema validation, unit test, or signed artifact alone is insufficient.

If one dimension cannot be ordered conservatively, the change is authority increasing and the scope remains non-live until independently resolved.

---

## 12. Lifecycle State Models

### 12.1 Hard Safety Envelope

```text
DRAFT -> VALIDATED -> APPROVED -> STAGED -> ACTIVE

{DRAFT, VALIDATED, APPROVED, STAGED} -> REJECTED
ACTIVE -> RESTRICTED
ACTIVE -> SUPERSEDED
ACTIVE -> REVOKED
```

Only one Envelope Generation may be permission-relevant for an exact scope. `SUPERSEDED`, `REVOKED`, or restored generations never return to `ACTIVE`.

### 12.2 Runtime Safety Profile

```text
DRAFT -> VALIDATED -> APPROVED -> STAGED -> ACTIVATION_READY -> ACTIVE

{DRAFT, VALIDATED, APPROVED, STAGED, ACTIVATION_READY} -> REJECTED
ACTIVE -> SUSPENDED
ACTIVE -> SUPERSEDED
ACTIVE -> REVOKED
ACTIVE -> EXPIRED
```

No transition from `SUSPENDED`, `SUPERSEDED`, `REVOKED`, or `EXPIRED` returns the same Profile Generation to `ACTIVE`. Reuse of identical content still requires a new generation, current validation, current approvals, activation, and re-arm.

### 12.3 Activation Is Not Arming

`ACTIVE` means the bundle is the current validated configuration basis for the declared scope. It does not mean trading is live. ADR-002-007 Live Authorization remains a separate, fresh, revocable authority.

Activation does not establish Critical Input validity, freshness, source continuity, Context Generation currentness, Decision Context Capsule validity, or absence of correction/invalidation. Those predicates remain independently governed and enforced under ADR-002-018; missing or unverifiable context remains denial even when the configuration bundle is `ACTIVE`.

Activation also does not establish venue/session/tradability, account/margin/borrow/settlement, Broker Capability Profile currentness, Constraint Generation, Venue Constraint Snapshot, or Order Admissibility Decision validity. Those predicates remain independently governed and enforced under ADR-002-019; configuration activation cannot make an exact order admissible.

Activation does not establish that a candidate command conforms to an approved Intent, that an Economic Effect Envelope is capacity-covered, that an Order Conformance Proof is current, or that the actual outbound representation is equivalent. Those predicates remain independently governed and enforced under ADR-002-020; configuration activation cannot create conformance or transmission permission.

Activation does not establish aggregate-state completeness, scenario sufficiency, valuation or hedge validity, an Aggregate Risk Decision, RCL headroom, or risk-decision currentness. Those predicates remain independently governed and enforced under ADR-002-021; configuration activation cannot grant an allocation or create capacity.

Activation does not establish the ADR-002-024 complete Safety Currentness Vector, satisfy a restrictive generation floor, open a Local Restrictive Latch, create an Egress Currentness Proof, or order a capability claim. Currentness Policy is part of the governed bundle, but active configuration is not per-send currentness or transmission authority.

---

## 13. Atomic Activation Protocol

Activation SHALL follow this order:

1. classify the change using the old and candidate complete bundles;
2. create a new immutable artifact set and Profile Generation;
3. obtain required independent approvals with bounded validity;
4. validate the candidate against the current active envelope and all referenced artifacts;
5. revoke or suspend old permission-creating Live Authorization for the affected scope;
6. stage exact artifacts to every required permission-creating consumer without making them active;
7. collect authenticated compatibility attestations for exact digests and consumer identities;
8. commit one `ActivateProfileGeneration` record through the Safety Commit Log with predecessor, approvals, attestations, scope, and restrictive-generation updates;
9. require RCL, Safety Authority, Live Authorization, Currentness Sequencer, Recovery Coordinator, and final egress to observe the same committed record;
10. perform fresh readiness evaluation and governed re-arm for only the approved scope.

No delivery acknowledgement, configuration-management success, repository merge, signer approval, deployment completion, cache refresh, or health check substitutes for the committed Activation Record.

If any consumer is absent, incompatible, stale, mixed, or unable to verify the record, that consumer and every scope able to reach it remain denied. The system SHALL NOT combine old and new field values to improve availability.

The Activation Record SHALL not mutate risk capacity. Any capacity change required by a new profile occurs through explicit RCL transitions after activation and under the new limits.

---

## 14. Restrictive Changes and Emergency Overrides

A change may use the Restrictive Override path only when a deterministic comparison proves it cannot increase authority in any credible state, intermediate transition, fallback, unit interpretation, or failure mode.

A Restrictive Override SHALL:

- identify the exact affected scope and predecessor generations;
- advance profile and applicable revocation or HALT generations;
- reach final egress within `B_risk_increase_revoke` plus `B_revocation_to_egress`, or the tighter applicable bound;
- deny old and mixed generations;
- preserve capacity, orders, exposure, UNKNOWN, protective ownership, and economic lineage;
- prohibit scheduled or health-triggered automatic reversion;
- require a new normal activation and re-arm for any later expansion.

A nominal limit reduction that changes units, aggregation, scope exclusions, fallback behavior, protective ownership, broker capability, state confidence, or calculation semantics is not presumed restrictive.

When the validator or ordering plane is unavailable, emergency authority may HALT. It may not construct a new permissive profile from local configuration.

---

## 15. Concurrency and Ordering

Concurrent envelope, profile, broker-profile, software, deployment, and emergency proposals SHALL be ordered against one exact predecessor generation.

The Safety Commit Log SHALL reject:

- two successful activations for the same predecessor and overlapping scope;
- stale-base approval or activation;
- last-write-wins merge;
- partial field patching of an active artifact;
- an activation whose referenced generation changed after validation;
- a permissive activation ordered after a restrictive event without fresh validation and approval.

Disjoint scope may activate independently only when the Failure-Domain Allocation Matrix, capacity domains, credentials, routes, broker limits, and aggregate-envelope constraints prove independence. Shared aggregate constraints require serialized evaluation.

Quorum ordering establishes one authoritative history. It does not collapse envelope governance, profile approval, capacity mutation, Live Authorization, and egress enforcement into one authority.

---

## 16. Distribution and Consumer Enforcement

Artifact distribution is untrusted delivery. Every consumer SHALL independently verify:

- artifact type, digest, signature, scope, generation, and revocation state;
- canonical semantic digest reproduction;
- exact Consumer Compatibility Manifest match;
- current committed Activation Record and predecessor relationship;
- trustworthy-time validity;
- all referenced artifact identities;
- absence of a newer restrictive generation or local deny latch.

Permission-creating caches SHALL be content-addressed and generation-bound. Cache miss, cache conflict, stale cache, registry partition, signature failure, or inability to establish currentness is denial.

Final egress SHALL bind the Hard Safety Envelope and Runtime Safety Profile generations and digests into the Transmission Capability and Quorum Commit Certificate validation required by ADR-002-013. Upstream agreement is insufficient if egress cannot prove the same generation.

Monitoring may identify drift, but the enforcing consumer must prevent stale or mixed permission before monitoring reacts.

---

## 17. Rollback, Restore, and Disaster Recovery

Rollback is a new proposal, never a state reversal. Reusing an older artifact requires:

- a new Envelope or Profile Generation;
- validation against current schemas, software, broker capabilities, failure domains, time rules, and the active Hard Safety Envelope;
- current approvals;
- break-before-make activation;
- fresh readiness and governed re-arm.

Snapshot, backup, replica, or disaster-recovery restore SHALL preserve artifact digests, approvals, revocations, generations, Activation Records, rejection records, and sufficient history to detect omission or rollback. ADR-002-012 Restore Generation advancement fences all prior configuration authority.

If the highest committed configuration history cannot be proven, the affected scope remains non-live. Presenting a valid historical signature does not prove current activation.

Rolling back software without rolling back configuration is also a compatibility change and fails closed unless the restored software's Consumer Compatibility Manifest exactly supports the current bundle.

---

## 18. Expiry and Trustworthy Time

Envelope, profile, approval, compatibility attestation, and activation validity SHALL use ADR-002-008 Trustworthy Time.

Expiry or time unverifiability suspends future new-risk authority. It does not:

- cancel or prove cancellation of orders;
- release committed capacity;
- expire economic effect;
- resolve UNKNOWN state;
- restore a predecessor profile;
- permit an automatic grace-period expansion;
- re-arm when time health recovers.

Time recovery only permits current validation to resume. A fresh activation or Live Authorization remains required wherever the prior artifact or authority expired, was revoked, or was superseded.

---

## 19. Economic-State and Capacity Continuity

Every reservation, attempt, order, fill, position, exposure, UNKNOWN effect, protective lease, and non-trade transition SHALL retain the envelope and profile generations under which it was created.

A narrower new profile may cause existing state to exceed future limits. That state remains an economic fact and consumes conservative capacity. The system SHALL suspend new risk and use separately authorized containment or protective workflows; it SHALL NOT rewrite history, discard the state, or enlarge the new profile to make the state appear compliant.

The Safety Profile Validator and configuration services SHALL NOT mutate, release, transfer, or synthesize RCL capacity. Configuration expiry, deletion, rollback, or supersession is never Final Quantity Proof and never a capacity-release proof.

Missing ACK is not proof of broker non-acceptance. Cancel ACK is not Final Quantity Proof. Configuration state cannot override either rule.

---

## 20. Failure Modes and Required Responses

| Failure | Required response |
|---|---|
| Missing or unreadable Hard Safety Envelope | zero new-risk authority; preserve economic state and containment paths |
| Runtime profile exceeds or cannot be compared with envelope | reject candidate; keep scope non-live |
| Unknown or duplicate field | reject artifact; do not ignore or default permissively |
| Unit, multiplier, currency, sign, precision, or rounding disagreement | reject bundle and affected compatibility attestations |
| Partial distribution or mixed generation | deny permission at every mismatched consumer and final egress |
| Concurrent activation from same predecessor | serialize one winner; reject stale-base candidate |
| Consumer lacks new schema or field | mark incompatible; no activation or send through that consumer |
| Restrictive change cannot be proven monotonic | treat as authority increasing; use HALT if immediate containment is required |
| Envelope or profile changes while live | revoke affected Live Authorization before candidate eligibility |
| Old profile restored from cache, backup, or rollback | reject generation; advance restore/fence state; no automatic re-arm |
| Approval expired or approver authority revoked | candidate cannot activate; active scope follows its explicit invalidation policy and fails closed if current approval is required |
| Profile expires while orders remain open | block new risk; retain orders, UNKNOWN, exposure, and capacity; reconcile and contain |
| Configuration service recovers | remain denied until committed current generation is proven; recovery does not re-arm |
| Break-glass attempts expansion | reject; preserve only HALT or proven restrictive authority |
| Evidence pipeline succeeds but enforcement is mixed | deny; evidence cannot legalize partial activation |

---

## 21. Evidence, Metrics, and Alerts

Evidence SHALL retain:

- every artifact byte representation and Canonical Semantic Digest;
- schema, canonicalization, compatibility, and reference graphs;
- authors, approvers, approval policies, signatures, validity, and revocations;
- semantic-validation inputs, results, rejected dimensions, and direction classification;
- staging and consumer compatibility attestations;
- Activation Records, predecessor generations, quorum proof, and restrictive ordering;
- every consumer and egress acceptance or denial by exact generation;
- rollback, restore, cache, mixed-version, stale-base, and incompatible-consumer attempts;
- Live Authorization suspension and fresh re-arm lineage;
- RCL capacity and economic state preserved across profile transitions.

Metrics SHALL include active envelope/profile generations by scope, bundle digest agreement, incompatible or missing consumers, staging age, activation attempts, stale-base rejections, semantic-validation failures by class, mixed-generation denials, restrictive-propagation latency, approval age, rollback attempts, expired artifacts, and egress generation mismatch.

Critical alerts include envelope bypass, unapproved authority increase, mixed-generation send, stale profile accepted, automatic revert, configuration-driven capacity release, single-principal expand-and-arm, or live transmission without the exact committed bundle.

Evidence records what occurred. It does not make mutable, partial, stale, or incompatible configuration safe.

---

## 22. Rejected Alternatives

### 22.1 Mutable “Current Configuration” Object

Rejected because meaning can change without an immutable identity or predecessor fence.

### 22.2 File Delivery Equals Activation

Rejected because distribution does not establish atomic authority or consumer agreement.

### 22.3 Syntax or Schema Validation Alone

Rejected because valid syntax can still encode unsafe units, scope, aggregates, or semantics.

### 22.4 Ignore Unknown Fields for Compatibility

Rejected because an ignored field may be the restriction another consumer enforces.

### 22.5 Per-Field Live Patching

Rejected because mixed fields can create a profile broader than either complete version.

### 22.6 Rollback Is Automatically Safer

Rejected because an older profile may be broader, stale, incompatible, revoked, or based on obsolete broker behavior.

### 22.7 Envelope Expansion Preserves Existing Arming

Rejected because changing the maximum authority and assumptions invalidates the prior safety basis even when the old profile values appear unchanged.

### 22.8 Automatic Revert of Emergency Restriction

Rejected because timer or health recovery cannot prove economic readiness or current approval.

### 22.9 Strategy-Owned Safety Limits

Rejected because the subject of control cannot unilaterally enlarge its own authority.

### 22.10 Logs, Diffs, or Signatures as Enforcement

Rejected because authenticated evidence cannot prevent a stale or mismatched consumer from granting permission.

---

## 23. Consequences

### 23.1 Positive

- configuration becomes an explicit authority protocol rather than mutable deployment data;
- envelope and runtime limits remain separately governed;
- semantic and unit errors fail before permission creation;
- mixed-version and partial activation cannot form a permissive union;
- rollback, restore, expiry recovery, and cache recovery cannot revive authority;
- restrictive emergency action remains available without creating an expansion path;
- every consumer and final egress binds the same committed generation;
- existing economic effect remains conservatively accounted through configuration changes.

### 23.2 Negative

- configuration changes require immutable bundles, compatibility manifests, quorum ordering, and separated approval;
- authority-increasing changes incur deliberate non-live time and fresh re-arm;
- incompatible consumers reduce availability;
- envelope changes invalidate dependent profiles and may require broad revalidation;
- emergency restrictions cannot automatically revert;
- strict canonical semantics limit configuration-language flexibility;
- rollback and disaster recovery require new generations rather than quick state reversal.

These costs are accepted because silent configuration expansion can bypass every other safety layer.

---

## 24. Acceptance Cases

The following cases are mandatory and map one-to-one to `SPG-EV-001` through `SPG-EV-012`. Written cases are not completed evidence.

| ID | Required demonstration |
|---|---|
| `SPG-AC-001` | Hard Safety Envelope expansion, tightening, replacement, or unavailable state cannot silently expand a Runtime Safety Profile or preserve prior live arming |
| `SPG-AC-002` | Unit, multiplier, currency, sign, precision, rounding, overflow, and cross-field semantic defects fail closed before activation |
| `SPG-AC-003` | Missing, unknown, duplicate, deprecated, extension, ambiguous, floating-reference, and schema-downgrade fields cannot create permission |
| `SPG-AC-004` | Partial distribution, mixed old/new fields, incompatible consumers, and regional skew cannot create a permissive union or broker transmission |
| `SPG-AC-005` | Concurrent, retried, overlapping, and stale-base activations serialize to one committed generation without last-write-wins behavior |
| `SPG-AC-006` | A proven restrictive transition dominates new risk within approved bounds while preserving orders, exposure, UNKNOWN, capacity, and protection |
| `SPG-AC-007` | Rollback, snapshot restore, disaster recovery, cache recovery, and historical signature replay cannot revive an old generation or approval |
| `SPG-AC-008` | Profile or approval expiry and later time/service recovery cannot restore authority or erase economic effect |
| `SPG-AC-009` | Strategy, single operator, workflow administrator, break-glass identity, or compromised automation cannot author, approve, activate, and arm an authority increase |
| `SPG-AC-010` | Software, parser, schema, Broker Capability Profile, deployment, credential, route, or compatibility drift suspends affected authority and fails closed at egress |
| `SPG-AC-011` | Missing, contradictory, unreadable, or unverifiable configuration blocks new risk while unresolved economic state remains conservatively capacity-covered |
| `SPG-AC-012` | Independent replay reconstructs every artifact, approval, validation, activation, restriction, consumer decision, denial, and re-arm without treating evidence as authority |

---

## 25. Requirements Traceability

| Requirement | ADR-002-014 allocation |
|---|---|
| SAFE-003 | Complete, readable, semantically valid, scope-correct profile is required for permission (§§7, 10–13) |
| SAFE-004 | Runtime Safety Profile cannot exceed, redefine, omit, or disable the Hard Safety Envelope (§§6, 9, 11) |
| SAFE-010, SAFE-011, SAFE-013 | Permission binds exact current configuration semantics and fails closed on incompatibility (§§11, 13, 16) |
| SAFE-035 | Expiry and validity use Trustworthy Time and cannot revive on recovery (§18) |
| SAFE-041, SAFE-046, SAFE-048 | Independent restriction, explicit fresh arming, and partition-safe denial remain separate from configuration activation (§§8, 12–16) |
| SAFE-045, SAFE-047 | Environment, account, broker, software, and deployment scope are explicit and non-interchangeable (§§7, 10, 16) |
| SAFE-050 | Critical configuration is immutable, authenticated, attributable, separately approved, atomically activated, and rollback-fenced (§§7–17) |
| SAFE-051, SAFE-052 | Full artifact and transition lineage supports evidence and replay without replacing enforcement (§21) |

---

## 26. Open Implementation Questions

The architecture is selected. The following product, schema, governance, topology, and parameter choices remain open while Proposed:

1. Which canonical artifact format and semantic-normalization algorithm are approved?
2. Which signing, approval-workflow, registry, and revocation mechanisms enforce independent envelope and profile governance?
3. Which ADR-002-015 effective-principal, approval quorum, expiry, delegation, consumption, compromise, and emergency-role policies apply to envelope and authority-increasing profile changes?
4. Which deterministic comparison system proves a change restrictive across scalar, set, vector, conditional, fallback, and time dimensions?
5. How are Consumer Compatibility Manifests generated, authenticated, and checked across mixed-version deployment?
6. Which ADR-002-012 command schema and namespace commit Profile Generations without collapsing separation of duties?
7. Which consumers must attest before activation for each Safety Cell and scope?
8. How are shared aggregate constraints serialized when nominally disjoint profiles change concurrently?
9. Which exact artifact changes require full re-arm versus scoped suspension and revalidation?
10. How are emergency envelope tightening and Restrictive Overrides distributed when the ordinary configuration plane is impaired?
11. What retention and proof establish the highest committed configuration history after disaster recovery?
12. Which numeric validity, approval, restriction-propagation, and review bounds are approved?
13. Which ADR-002-016 Evidence Integrity Policy, canonical evidence envelope, integrity anchor, gap detector, retention rule, and Replay Capsule preserve every configuration decision without becoming activation authority?
14. How are the ADR-002-017 Recovery Barrier Policy generation and digest governed, activated, and bound into the closed bundle without allowing configuration activation to open the barrier or re-arm?
15. How are ADR-002-018 Critical Input Policy identity, generation, digest, source/mapping/lineage compatibility, and restrictive invalidation bound into the bundle without letting configuration activation declare context valid or current?
16. How are ADR-002-021 Aggregate Risk Policy and Adverse Scenario Set identities, generations, digests, evaluator/verifier compatibility, and restrictive invalidation bound into the bundle without letting activation grant allocation or create capacity?
17. How are ADR-002-022 Action Flow Policy identity, generation, digest, resource/scope semantics, governor/RCL/egress compatibility, and restrictive invalidation bound into the bundle without letting activation create capacity, reserve, permit, or transmission authority?
18. How are ADR-002-023 Trading Approval Policy identity, generation, digest, evaluator/verifier compatibility, independent-path allocation, and restrictive invalidation bound into the bundle without letting activation approve a proposal or create an Intent?
19. How are ADR-002-024 Currentness Policy identity, generation, digest, owner/dependency registry, vector/fence/proof schemas, local-latch rules, and compatibility bound into the bundle without letting activation establish per-send currentness or transmission permission?

Unresolved questions reduce authority or keep the affected scope non-live. They SHALL NOT create a permissive default.

---

## 27. Approval Gate

ADR-002-014 SHALL remain **Proposed** until all of the following are complete:

1. canonical Hard Safety Envelope, Runtime Safety Profile, Safety Configuration Bundle, and Consumer Compatibility Manifest schemas are approved;
2. envelope, profile, validation, activation, restriction, and live-arming authorities are implemented with reviewed separation of duties;
3. ADR-002-015 Human Authority Policy, effective-principal independence, approval-set consumption, and break-glass confinement are implemented and their required HAG evidence passes;
4. semantic comparison covers every Critical unit, scope, aggregate, fallback, compatibility, and economic-effect dimension;
5. the ADR-002-012 Profile Generation and Activation Record ordering is implemented without creating a capacity or approval bypass;
6. every permission-creating consumer and ADR-002-013 final egress enforces exact committed digests, generations, compatibility, and restrictive precedence;
7. rollback, restore, cache, expiry, mixed-version, emergency restriction, and software-compatibility fencing are implemented and security-reviewed;
8. no configuration transition releases capacity, expires economic effect, treats missing ACK as non-acceptance, or treats cancel ACK as Final Quantity Proof;
9. `SPG-EV-001` through `SPG-EV-012` and applicable REARM, FD, RCLP, EGRESS, SA, and cross-system evidence pass at required levels and receive independent review;
10. ADR-002-016 artifact, decision, denial, activation, restriction, rollback, restore, and consumer evidence is immutable, causally complete, gap-checked, and replayable, and applicable ERI evidence passes;
11. ADR-002-017 Recovery Barrier Policy identity, generation, digest, compatibility, and restrictive activation behavior are bound into the complete configuration bundle without becoming recovery readiness or re-arm authority, and applicable SBR evidence passes;
12. ADR-002-018 Critical Input Policy identity, generation, digest, compatibility, and restrictive invalidation behavior are bound into the complete configuration bundle without becoming context validity, approval, capacity, or egress authority, and applicable CII evidence passes;
13. ADR-002-019 Venue Constraint Policy identity, generation, digest, compatibility, and restrictive invalidation behavior are bound into the complete configuration bundle without becoming order admissibility, approval, capacity, or egress authority, and applicable VTG evidence passes;
14. ADR-002-021 Aggregate Risk Policy and Adverse Scenario Set identities, generations, digests, compatibility, and restrictive invalidation behavior are bound into the complete configuration bundle without becoming allocation, capacity, Live Authorization, or egress authority, and applicable ARE evidence passes;
15. ADR-002-022 Action Flow Policy identity, generation, digest, resource/scope semantics, compatibility, and restrictive invalidation behavior are bound into the complete configuration bundle without becoming capacity, protective reserve, Action Flow Permit, Live Authorization, or egress authority, and applicable AFG evidence passes;
16. ADR-002-023 Trading Approval Policy identity, generation, digest, independent-validation requirements, compatibility, and restrictive invalidation behavior are bound into the complete configuration bundle without becoming proposal approval, Intent transition, capacity, authority, or egress permission, and applicable IAP evidence passes;
17. ADR-002-024 Currentness Policy identity, generation, digest, owner/dependency registry, vector/fence/proof schemas, local-latch rules, and compatibility are bound into the complete configuration bundle without becoming currentness fact, capacity mutation, live authority, or egress permission, and applicable CUR evidence passes;
18. applicable activation, revocation, restriction-propagation, recovery-barrier, Critical Input, venue-constraint, aggregate-risk, action-flow, approval, and currentness invalidation, context/request/decision/permit/proof/vector/snapshot-age, readiness-age, time, evidence, and egress bounds are approved and measured;
19. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Authorship, signatures, successful parsing, repository merge, staged distribution, written acceptance cases, or document review do not satisfy this gate. This ADR does not authorize acceptance, restricted-live operation, production operation, configuration-driven capacity mutation, or automatic re-arm.
