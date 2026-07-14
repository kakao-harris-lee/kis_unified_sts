# ADR-002-020 — Intent-to-Order Conformance, Canonical Command Construction, and Economic-Effect Fencing

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Approved Intent contract, deterministic broker-command construction, account/instrument/contract mapping, direction and position-effect mapping, quantity/unit/multiplier/currency conversion, price and order constraints, authorized construction envelopes, canonical encoding and digest, economic-effect proof, retry/cancel/replace lineage, downstream mutation fencing, final-egress verification, degraded behavior, recovery, evidence, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-033; RFC-002 §§3.1, 9.1, 10.7–10.8, 11, 13.6, 22, and 29; ADR-002-013 §§11–12; ADR-002-019 §§12, 14, and 16–17
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013 through SAFE-015, SAFE-020, SAFE-021, SAFE-024, SAFE-025, SAFE-030 through SAFE-035, SAFE-040, SAFE-041, SAFE-043, SAFE-044, SAFE-046, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-002 through ADR-002-019

---

## 1. Decision

Every broker-directed mutation SHALL be constructed from one immutable Intent proposal through an approved deterministic **Order Construction Policy** and SHALL ultimately bind the identical approved Intent digest. The resulting **Canonical Broker Command** and **Order Conformance Proof** SHALL prove exact conformance in environment, broker, account, subaccount, venue, market segment, instrument, contract or symbol, direction, side, position effect, quantity, unit, multiplier, currency, price instruction, order constraints, time in force, expiration, operating mode, action class, endpoint, route, and worst credible economic effect.

The TOS SHALL NOT treat an adapter request, SDK object, serialized payload, signer input, HTTP body, FIX message, queue message, or broker acknowledgement as self-proving conformance. Account defaults, symbol aliases, enum defaults, implicit units, floating-point coercion, permissive rounding, sign conventions, broker SDK defaults, omitted fields, duplicated fields, field-order ambiguity, and transport rewrites SHALL NOT alter the approved meaning.

The approved Intent SHALL contain or reference an explicit **Authorized Construction Envelope**. The envelope declares every deterministic transformation permitted during construction, including exact symbol mapping, unit conversion, multiplier, price representation, lot/tick handling, bounded quantity rule, side and position-effect mapping, supported broker fields, and conservative economic-effect bound. A transformation outside that closed envelope is a new proposal, not implementation detail.

The **Order Construction Service** is a pure, non-authorizing compiler. It may produce a Canonical Broker Command and an Order Conformance Proof. It cannot approve an Intent, widen the Authorized Construction Envelope, commit or release capacity, issue Safety Authority or Live Authorization, classify an action as protective, create or consume a Transmission Capability, choose a more permissive Venue Constraint Decision, transmit, clear HALT, or re-arm.

Any mapping, normalization, rounding, splitting, aggregation, default, or broker-specific field that can alter economic effect SHALL be explicit in the policy and proof. A transformation that is expected to reduce risk is not automatically safe: it may remove protection, create residual exposure, cross zero, reverse a position, change queue behavior, or violate capacity and venue assumptions. Silent narrowing is prohibited unless the exact bounded choice was authorized and all dependent gates evaluated that same choice set.

The **Economic Effect Envelope** SHALL conservatively cover every broker interpretation and executable outcome permitted by the exact command, including full and partial fill, side and position-effect semantics, quantity and multiplier, cash and currency legs, fees or margin effects where safety-relevant, reduce-only failure, zero crossing, reversal, order overlap, and broker rounding. The RCL commitment SHALL dominate this envelope in every governed risk dimension. The Order Construction Service cannot mutate the RCL.

Unknown, stale, conflicting, unsupported, non-canonical, non-deterministic, overflowed, underflowed, lossy, ambiguously rounded, or unverifiable construction state SHALL block transmission. It SHALL NOT create headroom, capacity, or protective permission. If a command may already have crossed the irreversible send boundary, every credible effect remains potentially live and capacity-consuming until authoritative proof resolves it.

Retries, resubmissions, cancellations, amendments, replacements, exercise instructions, and other broker mutations require their own canonical command identity, exact lineage, conformance proof, applicable authority, capacity treatment, and venue admissibility. Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. Reuse of a prior command digest does not authorize a new attempt.

No security- or economic-effect-relevant field may be created, defaulted, normalized, modified, duplicated, reordered ambiguously, or removed downstream of proof issuance. Transport-only fields may vary only when the policy declares their semantics irrelevant, excludes them through one canonicalization rule, and final egress independently proves that they cannot affect broker interpretation, routing, authentication scope, idempotency, or economic effect.

Final egress remains the last enforcement point. Before the first broker-directed byte, it SHALL verify the exact Intent, construction policy and generation, Authorized Construction Envelope, Canonical Broker Command digest, Order Conformance Proof, Economic Effect Envelope, capacity commitment, authority, Order Admissibility Decision, Commit Proof, endpoint, route, credential, session, and actual outbound representation. Any mismatch, unknown field, duplicate semantic field, unsupported encoding, stale generation, or unverifiable equivalence denies transmission.

Intent withdrawal, policy change, mapping change, compiler or serializer change, schema change, broker SDK change, broker capability change, context or venue-constraint invalidation, security compromise, or recovery SHALL invalidate every affected unconsumed conformance proof before future new-risk send. Invalidation or expiry never expires a command that may already have economic effect, releases capacity, proves rejection, or re-arms live operation.

Restart, rollback, restore, failover, cache warm-up, serializer recovery, SDK recovery, broker reconnect, successful replay, or identical recompilation cannot revive a prior proof, capability, or authority. Fresh current artifacts and the complete governed authorization chain are required. No automatic re-arm is permitted.

---

## 2. Context

RFC-001 SAFE-033 requires every order to conform to its approved Intent. RFC-002 allocates construction to the Execution Coordinator and final checking to broker egress. ADR-002-013 secures the final route and requires exact request comparison. ADR-002-018 binds the exact decision context, and ADR-002-019 decides whether the complete order shape is currently admissible.

Those decisions do not define the compiler between an approved Intent and a broker payload. Without one complete contract, an implementation can:

- approve a portfolio or instrument quantity but submit a broker quantity in a different unit;
- invert buy/sell, open/close, long/short, debit/credit, or position-effect semantics;
- apply the wrong contract multiplier, currency scale, price scale, tick table, or lot rule;
- use a symbol alias that routes to another venue, contract month, account, or product;
- let a broker SDK default account, time in force, order type, routing, reduce-only, or position side;
- round a quantity down and silently leave protection insufficient;
- split one Intent into several commands whose aggregate quantity or overlap exceeds authority;
- aggregate several Intents into one command that loses per-Intent capacity and attribution;
- mutate a command after proof through a queue, proxy, signer, serializer, retry wrapper, redirect, or broker SDK;
- use JSON duplicate keys, FIX tag duplication, numeric overflow, Unicode ambiguity, or canonicalization disagreement to make reviewers and the broker see different commands;
- call a changed command a retry and reuse a prior capability or idempotency identity;
- treat a broker acknowledgement as proof that the command matched the approved Intent;
- restore a compiler or cache and reuse stale proof after policy, context, venue, or authority changed;
- retain only logs of the transformation while permitting the live path to bypass it.

This ADR closes those paths without giving the compiler approval, capacity, venue, authority, or transmission power.

---

## 3. Decision Drivers

1. An approved Intent and a broker request use different semantic vocabularies and cannot be compared by field names alone.
2. Unit, multiplier, sign, position-effect, currency, and rounding errors can create orders that appear syntactically valid but have different economic effect.
3. Broker SDKs, serializers, proxies, and signers can mutate meaning after application-level validation.
4. Exact conformance must be deterministic, canonical, and independently reproducible.
5. Capacity must cover the broker command's worst credible economic effect, not only the intended point estimate.
6. Retry, cancel, amend, replace, and split/aggregate paths must preserve exact lineage and authority.
7. Final egress must compare the actual outbound representation, not merely trust an upstream “validated” flag.
8. Artifact invalidation must block future permission without erasing already possible economic effect.
9. UNKNOWN or non-canonical construction must fail closed.
10. Recovery and recompilation must never automatically revive authority.

---

## 4. Scope and Non-Scope

This ADR decides:

- approved Intent fields required for order construction;
- Order Construction Policy and Authorized Construction Envelope;
- deterministic compiler behavior and canonical broker-command representation;
- account, instrument, contract, direction, position-effect, quantity, unit, multiplier, currency, price, order, expiration, mode, endpoint, and route conformance;
- Economic Effect Envelope and capacity-proof binding;
- split, aggregation, retry, cancel, amend, replace, and protective command lineage;
- downstream mutation, serializer, signer, queue, proxy, SDK, and wire-equivalence fencing;
- invalidation, degraded behavior, recovery, evidence, acceptance cases, and approval gates.

This ADR does not decide:

- whether an Intent should exist or is independently approved;
- alpha, strategy, desired quantity, portfolio construction, or risk appetite;
- current venue/session/tradability admissibility, which remains ADR-002-019;
- Critical Input validity and provenance, which remain ADR-002-018;
- broker capability and Final Quantity Proof semantics, which remain ADR-002-004;
- capacity mutation or release, which remain exclusively ADR-002-002 and ADR-002-012;
- final credential, route, Commit Proof, and hard-fence security, which remain ADR-002-013;
- protective classification and replacement workflow, which remain ADR-002-001 and ADR-002-011;
- concrete programming language, serialization library, broker SDK, FIX engine, schema registry, signer, queue, or transport product;
- numeric age or invalidation bounds, which require an approved Verification Profile.

---

## 5. Definitions

### 5.1 Approved Intent Contract

The immutable approved statement of requested action, allowed scope, maximum economic effect, constraints, expiration, context, and authority prerequisites. A non-authorizing candidate command may be compiled from the identical immutable approval-pending proposal so independent approval can inspect the exact candidate and venue decision. Any approval-time mutation requires a new proposal, candidate, venue decision, and downstream chain. The Intent is not a broker command.

### 5.2 Order Construction Policy

An immutable, authenticated, separately governed artifact defining supported Intent and broker-command schemas, exact mappings, canonicalization, permitted transformations, numeric semantics, failure responses, compiler requirements, and evidence rules.

### 5.3 Authorized Construction Envelope

The closed set of exact broker-command variants that an approved Intent permits after declared deterministic transformations. An absent or open-ended envelope permits no construction.

### 5.4 Canonical Broker Command

An immutable, broker- and endpoint-specific semantic candidate command with one canonical representation and digest, complete field presence, explicit units and defaults, exact proposal lineage, and no unbound economic-effect field. It is non-authorizing until a later proof binds the identical approved Intent and all independent gates.

### 5.5 Economic Effect Envelope

The conservative set of all credible economic effects the exact command may produce under supported broker interpretation, partial execution, rounding, ordering, overlap, and reversal semantics.

### 5.6 Order Conformance Proof

An immutable non-authorizing artifact proving that one Canonical Broker Command is a deterministic member of the approved Intent's Authorized Construction Envelope and that its Economic Effect Envelope is covered by the exact RCL commitment. It declares the exact authority scope later issuance must dominate; Live Authorization and capability bind the proof downstream and are not proof-issuance prerequisites.

### 5.7 Construction Generation

A monotonic restrictive generation binding the active construction policy, schemas, mappings, compiler, canonicalization, serializer, SDK constraints, and compatibility state. A newer restrictive generation fences older unconsumed proofs.

### 5.8 Material Command Change

Any change that may alter identity, routing, authentication scope, idempotency, broker interpretation, accepted syntax, execution behavior, economic effect, capacity need, venue admissibility, or evidence strength. Unknown materiality is material.

### 5.9 Actual Outbound Representation

The final bytes, message fields, signed parameters, endpoint, method, headers, routing metadata, and transport semantics presented to the broker or first external intermediary capable of broker effect.

---

## 6. Safety Invariants

### IOC-INV-001 — One Exact Proposal and Approved Intent

Every candidate Canonical Broker Command binds one exact immutable Intent proposal identity and digest, and every usable Order Conformance Proof binds the identical approved Intent identity and digest; no orphan, implicit, merged, mutated, or substituted Intent may reach egress.

### IOC-INV-002 — Deterministic Canonical Construction

The same complete approved inputs and Construction Generation produce the same canonical semantic command and digest, or construction fails.

### IOC-INV-003 — Exact Identity and Scope

Environment, broker, account, venue, instrument, contract, endpoint, route, mode, and action class cannot be defaulted, aliased, or substituted outside the authorized envelope.

### IOC-INV-004 — Exact Numeric and Direction Semantics

Side, direction, position effect, quantity, unit, multiplier, currency, price scale, sign, precision, and rounding are explicit and proven without lossy or ambiguous coercion.

### IOC-INV-005 — Economic Effect Is Conservatively Bounded

The committed capacity dominates every credible effect in the command's Economic Effect Envelope, and any later-issued authority must dominate the proof's declared required authority scope; compiler confidence or expected rejection cannot reduce either bound.

### IOC-INV-006 — No Silent Widening or Narrowing

No mapping, rounding, split, aggregation, default, or normalization changes authorized meaning unless the exact bounded transformation is inside the envelope and every dependent gate evaluated it.

### IOC-INV-007 — No Downstream Mutation

No economic- or security-relevant command field changes after proof issuance; final egress verifies the actual outbound representation.

### IOC-INV-008 — Retry and Mutation Preserve Lineage

Retry, cancel, amend, replace, exercise, split, and aggregation operations use explicit command and attempt identities, proof, capacity, authority, and broker rules; UNKNOWN never causes blind resubmission.

### IOC-INV-009 — Unknown Construction Is Denial

Missing, stale, conflicting, unsupported, non-canonical, non-deterministic, overflowed, lossy, or unverifiable construction state blocks transmission and cannot create headroom.

### IOC-INV-010 — Final Egress Fences Conformance

No broker-directed byte is sent unless exact Intent-to-command membership, proof currentness, economic-effect coverage, and outbound equivalence are positively established at the irreversible boundary.

### IOC-INV-011 — Compiler Has No Economic Authority

Order construction cannot approve, mutate capacity, issue authority, classify protection, choose permissive admissibility, transmit, clear HALT, or re-arm.

### IOC-INV-012 — Economic Effect Outlives Construction Artifacts

Intent, policy, command, proof, compiler, or capability expiry/invalidation never expires orders, attempts, fills, exposure, UNKNOWN, or capacity commitments already capable of effect.

### IOC-INV-013 — Recovery Does Not Revive

Compiler, serializer, SDK, cache, signer, route, or service recovery cannot revive a prior proof, capability, command permission, or live scope.

### IOC-INV-014 — Evidence Does Not Replace Prevention

Logs, code review, type checking, static schemas, audit, replay, broker acceptance, or reconciliation cannot substitute for canonical construction and final-egress enforcement.

---

## 7. Authority Ownership and Separation

| Function | Owning authority | Prohibited collapse |
|---|---|---|
| Define construction and canonicalization policy | Order Construction Policy governance under ADR-002-014 | compiler, adapter, or SDK owner cannot self-activate permissive rules |
| Approve Intent and construction envelope | Independent Approval Service and applicable human governance | compiler cannot approve or widen the envelope |
| Compile Canonical Broker Command and proof | Order Construction Service | cannot mutate capacity, issue authority, classify protection, or transmit |
| Validate current venue admissibility | Venue Constraint Gate under ADR-002-019 | compiler cannot choose a more permissive decision |
| Evaluate and commit capacity | Aggregate Risk Authority / RCL respectively | proof cannot create or release capacity |
| Issue Live Authorization and capability | ADR-002-007 authorities | command construction cannot issue or revive authority |
| Serialize and sign actual outbound representation | declared Final Egress Trust Boundary | serializer or signer cannot change proved semantics |
| Enforce final send | ADR-002-013 Broker Egress Gateway | upstream conformance result cannot bypass actual-byte verification |
| Preserve evidence and replay | ADR-002-016 services | evidence and replay cannot generate a live command or proof |
| Recover and re-arm | ADR-002-017/007/015 workflow | identical recompilation cannot reopen live scope |

The compiler and its policy, schema, mapping, test, and evidence identities SHALL NOT hold a usable live broker credential or broker-order route. If an implementation combines compiler and egress process boundaries, the complete combined identity and code path is inside the Final Egress Trust Boundary and must satisfy both ADRs; logical function names do not prove separation.

---

## 8. Approved Intent and Authorized Construction Envelope

An Intent proposal eligible for non-authorizing candidate construction, and the identical Intent eligible for later proof and transmission, SHALL bind at least:

- immutable Intent identity, version, digest, issuer, approval, and expiration;
- environment, safety cell, broker scope, account/subaccount, venue, market segment, instrument, contract, and canonical identity;
- requested action, action class, direction, side semantics, position effect, operating mode, and protective classification reference where applicable;
- quantity basis, unit, maximum quantity, multiplier, currency, price basis, order constraints, time in force, and expiration;
- requested and maximum credible economic-effect vector;
- Critical Input Snapshot and Decision Context Capsule;
- required venue, capacity, authority, profile, recovery, and evidence scopes and predicates;
- Authorized Construction Envelope identity/digest and permitted deterministic transformations;
- forbidden transformations, retry/split/aggregation policy, invalidation predicates, and residual risks.

Wildcard account, instrument, contract, side, quantity, unit, multiplier, mode, endpoint, or “latest policy” references are prohibited for live construction. Missing envelope fields are denial.

An envelope may authorize a closed set or an exact formula only when all inputs, numeric semantics, bounds, and outputs are deterministic and independently reproducible. A formula cannot query new mutable state or choose a more favorable value after approval.

---

## 9. Order Construction Policy and Compiler Determinism

The policy SHALL declare:

- supported Intent, command, broker API, endpoint, schema, and canonicalization versions;
- exact field mapping and required presence rules;
- account, venue, instrument, contract, symbol, product, and route registries;
- side, direction, position-effect, open/close, long/short, debit/credit, and reduce-only semantics;
- integer, decimal, rational, currency, unit, multiplier, precision, overflow, underflow, sign, and rounding rules;
- price, tick, lot, quantity, notional, trigger, time-in-force, expiration, and broker flag mappings;
- allowed split/aggregation behavior and aggregate limits;
- canonical field ordering, duplicate-field rejection, unknown-field handling, Unicode/encoding, null/default, and serialization semantics;
- broker SDK and signer constraints, actual-outbound comparison method, and transport-only field rules;
- compiler build, dependency, configuration, deployment, and compatibility identities;
- material change, invalidation, failure response, evidence, and approved scope.

The compiler SHALL be deterministic for the complete input set. Hidden clock reads, randomness, locale, environment variables, mutable caches, unordered map iteration, platform floating-point variation, network lookup, “latest” registry reads, or broker SDK implicit defaults are prohibited unless their exact value is already bound and canonicalized.

Construction failure is denial. A compiler must not “best effort” an unsupported field or fall back to a prior mapping.

---

## 10. Identity, Account, Instrument, and Route Conformance

The proof SHALL demonstrate exact mapping across:

- environment and live/non-live identity;
- broker, API product/version, account, subaccount, portfolio, custody, and legal scope;
- venue, market segment, board, route, endpoint, and session family;
- canonical instrument, broker symbol, contract month, option series, product, currency, and settlement identity;
- Intent action class and broker mutation endpoint.

Aliases are data, not authority. An alias, default account, default route, “primary” venue, front-month calculation, symbol truncation, case folding, Unicode normalization, or exchange suffix rule must be policy-bound and produce one unambiguous mapping. One-to-many or many-to-one ambiguity is denial unless the exact result was already approved.

Redirects, endpoint discovery, broker SDK environment selection, account fallback, or session reuse cannot change the proved destination. ADR-002-013 route confinement remains mandatory.

---

## 11. Direction, Position Effect, Quantity, Unit, and Multiplier

The construction proof SHALL independently validate:

- strategy direction versus broker side;
- long/short position side and open/close/reduce-only effect;
- position quantity versus order quantity;
- shares, lots, contracts, base/quote units, nominal/notional, face value, and fractional units;
- contract multiplier, split factor, conversion ratio, currency, price scale, and sign;
- minimum, maximum, step, precision, overflow, underflow, and exact rounding result.

Signed quantity alone is insufficient when broker side and position effect are separate fields. A negative value cannot silently flip a side. `abs`, clamp, cast, truncation, integer division, binary floating-point, scientific notation, or unitless numeric transport is prohibited unless its exact semantics and bound are policy-approved.

Any rounding or conversion result outside the Authorized Construction Envelope is rejected. A smaller order still requires re-evaluation when it can leave protection insufficient, violate a minimum/lot constraint, change exposure direction, or alter approved economic effect.

Splitting one Intent into commands requires a declared partition whose aggregate worst credible simultaneous effect is within the same approved envelope and committed capacity. Aggregating separate Intents into one broker command is prohibited unless one explicit aggregate Intent, allocation rule, capacity proof, attribution plan, and adverse partial-fill allocation were approved.

---

## 12. Price, Order, Expiration, and Mode Conformance

The command SHALL preserve the exact approved semantics of:

- market, limit, stop, stop-limit, peg, auction, discretionary, conditional, and broker-specific order type;
- price, trigger, offset, collar, limit, currency, scale, precision, tick, and reference generation;
- time in force, good-till date/time, day/session boundary, expiration, activation, and cancellation conditions;
- route, venue phase, participation, display, reduce-only, post-only, all-or-none, minimum quantity, and broker flags;
- live, restricted, degraded-protective, containment, simulation, test, and paper operating mode.

Omission of a field is permitted only when the policy proves the broker default is invariant, explicit in canonical semantics, current in the Broker Capability Profile, and identical to the approved Intent. Otherwise the field must be explicit.

A price improvement, more aggressive price, longer expiration, different order type, or broader route is a material change unless the exact bounded alternative was approved and capacity/venue/protection analysis covered it. “More likely to fill” is not a safety justification.

Non-live commands SHALL carry non-live environment and route identity; changing only a mode flag cannot transform them into live commands.

---

## 13. Economic Effect Envelope and Capacity Binding

For each command, the proof SHALL calculate a conservative effect vector over every governed dimension, including where applicable:

- position delta by account, instrument, contract, side, and currency;
- gross and net notional, leverage, margin, concentration, liquidity, basis, and settlement effects;
- maximum executable quantity and partial-fill prefixes;
- zero-crossing and reversal effect;
- old/new overlap for amend or replace;
- simultaneous split-command execution;
- reduce-only or close-only failure semantics;
- broker rounding, fee, cash, conversion, exercise, assignment, and delivery effects;
- existing and potentially-live attempts sharing the same Intent or containment scope.

The RCL commitment identity and vector SHALL be bound in the proof. The proof must show the committed vector dominates the envelope; it cannot request a ledger mutation or treat unused theoretical capacity as permission.

If exact broker interpretation is unknown, the envelope expands to the worst credible supported interpretation or the command is denied. Expected broker rejection, a protective label, human approval, or historical behavior cannot shrink it.

Intent, proof, or capability expiry after possible send does not release capacity. Missing ACK and cancel ACK retain the governing ADR-002-002/004 rules.

---

## 14. Canonical Broker Command and Proof Contract

The Canonical Broker Command SHALL contain at least:

- command identity, schema, canonicalization version, Construction Generation, and digest;
- exact immutable Intent proposal, Authorized Construction Envelope, construction policy, broker profile, and context references;
- every broker mutation field with explicit semantic type, unit, presence, and value;
- endpoint, method/message type, route, broker session scope, idempotency identity, and client order identity;
- actual-outbound canonicalization and comparison rules;
- issue, maximum-age, invalidation, and evidence metadata;
- explicit non-authorizing flags.

The Order Conformance Proof SHALL bind:

- policy and Authorized Construction Envelope identity/digest;
- compiler, dependency, schema, mapping, serializer, SDK, build, configuration, deployment, and compatibility generations;
- deterministic input and output digests;
- field-by-field and semantic conformance results;
- numeric conversion and rounding derivations;
- economic-effect and capacity-dominance result;
- venue admissibility and broker-capability references;
- unknown, residual-risk, expiry, invalidation, and reviewer data;
- final result `CONFORMANT` or `NON_CONFORMANT`/`UNKNOWN`.

`CONFORMANT` grants no approval or authority. It is usable only as one current input to separately owned capacity, authorization, capability, and final-egress enforcement.

The non-cyclic protocol order is:

```text
Immutable Intent Proposal + proposed Authorized Construction Envelope
        ↓
Deterministic candidate Canonical Broker Command
        ↓
Exact Venue Constraint Snapshot and Order Admissibility Decision
        ↓
Independent Approval + immutable Intent Registration
        ↓
Economic Effect Envelope derived from unchanged candidate
        ↓
RCL capacity commitment that dominates the envelope
        ↓
Order Conformance Proof
        ↓
Live Authorization / Transmission Capability / Commit Proof
        ↓
Final-egress actual-outbound verification
```

The candidate command does not require approval, a future venue decision, capacity commitment, or authority reference in order to exist and grants none of them. Independent approval binds the exact proposal, envelope, candidate digest, and venue decision; any approval-time change restarts construction. The later proof binds approval, registration, venue, and capacity results to the unchanged candidate digest. No downstream artifact is permitted to rewrite the candidate to satisfy its own gate.

For the same reason, the candidate command does not bind an Economic Effect Envelope identity or digest, and the Economic Effect Envelope does not bind a future Capacity Commitment. The envelope is derived from the immutable candidate, the RCL independently commits a vector that dominates it, and the later proof binds the command, envelope, and commitment together. This ordering prevents cyclic artifact dependencies while preserving exact economic-effect coverage.

Unknown fields, duplicate semantic fields, alternate encodings, unbound headers, or ambiguous canonicalization are rejection. A byte digest alone is insufficient if two byte sequences or parser behaviors can produce different broker meaning.

---

## 15. Downstream Serialization, Signing, and Mutation Fence

After proof issuance:

1. no economic- or security-relevant semantic field may change;
2. the serializer SHALL produce an actual outbound representation equivalent to the Canonical Broker Command under one approved rule;
3. the signer SHALL authenticate the exact endpoint, method/message type, body/fields, idempotency identity, principal, and session scope;
4. queues, proxies, sidecars, SDKs, gateways, retries, and intermediaries SHALL be unable to modify, merge, split, duplicate, redirect, or replay the command outside the proof;
5. final egress SHALL compare the actual outbound representation after every mutable internal stage and before the first external effect;
6. any downstream nondeterminism or unverifiable transformation is denial.

If broker signing requires a timestamp, nonce, session token, or transport sequence generated near send, the policy SHALL define it as a bound transport field, prove it cannot alter economic semantics or route scope, include its generation in the final comparison, and preserve ADR-002-008/013 currentness. “Excluded from digest” is not sufficient justification.

Parameter pollution, duplicate JSON keys, duplicate FIX tags, alternate Unicode forms, percent-encoding variants, numeric exponent variants, NaN/infinity, negative zero, integer overflow, silent truncation, or parser differential SHALL fail closed.

---

## 16. Retry, Cancel, Amend, Replace, Split, and Aggregate Commands

Every broker mutation has its own command identity and proof.

Same-command retry is permitted only when the active Broker Capability Profile proves deterministic idempotency for the exact identity and scope, the original attempt state permits retry, current context/constraint/authority remains valid, and the governing capability workflow authorizes it. Otherwise UNKNOWN remains potentially live and no blind resubmission occurs.

Cancel does not erase the original command or capacity. Cancel ACK is not Final Quantity Proof. Amend and replace bind old and new command identities, capacity overlap, cancellation/protection rules, and ADR-002-011 gap/overlap proof.

Split commands SHALL bind one partition plan, aggregate quantity/effect bound, per-child identity, simultaneous-execution envelope, and completion accounting. A child cannot be regenerated with remaining original quantity merely because sibling acknowledgement is missing.

Aggregation is denied by default. When explicitly supported, adverse partial fills, attribution, allocation, cancellation, replacement, recovery, and capacity shall remain deterministic and conservative for every source Intent.

---

## 17. Final-Egress Verification

Before every broker mutation, final egress SHALL:

1. validate the current Final Egress Trust Boundary and principal under ADR-002-013;
2. verify exact current Intent, approval, Decision Context Capsule, Order Admissibility Decision, capacity commitment, Safety Authority, Live Authorization, capability, and Commit Proof;
3. verify current Order Construction Policy, Construction Generation, Authorized Construction Envelope, command, proof, compiler/serializer compatibility, age, and invalidation status;
4. reproduce or independently verify deterministic membership of the command in the authorized envelope;
5. verify every identity, numeric, direction, unit, multiplier, currency, order, expiration, mode, endpoint, and route field;
6. verify Economic Effect Envelope coverage by the exact committed capacity;
7. verify the actual outbound representation and signer input are semantically identical to the command;
8. reject unknown, duplicate, extra, missing, ambiguous, stale, unsupported, or post-proof-mutated fields;
9. durably claim the exact single-use capability and record `SEND_STARTED` before the first broker-directed byte;
10. preserve potentially-live and conservative-capacity behavior for any ambiguous post-claim outcome.

Final egress SHALL NOT repair, normalize, clamp, round, remap, default, or recompile a non-conforming command. It rejects and requires a fresh upstream chain.

Cached `CONFORMANT`, type safety, successful serialization, SDK validation, signature validity, broker acceptance, or absence of policy invalidation is not current conformance proof.

---

## 18. Change, Invalidation, and Economic Continuity

Material changes SHALL advance Construction Generation or otherwise create a restrictive invalidation and fence affected unconsumed proofs. Triggers include:

- Intent, approval, envelope, context, venue decision, capacity, authority, or capability change;
- account, instrument, contract, symbol, unit, multiplier, currency, sign, position effect, price, lot, tick, order, route, endpoint, or operating-mode change;
- policy, mapping, schema, compiler, dependency, serializer, SDK, signing, canonicalization, configuration, deployment, or compatibility change;
- broker API/version/behavior, capability, redirect, session, credential, or route change;
- correction, security compromise, evidence gap, restore, or common-mode discovery.

Invalidation SHALL reach approval/capability issuance and every final egress within the approved bound. If complete propagation cannot be proven, containment expands to the complete possibly affected scope.

Commands or attempts that may already have crossed the send boundary remain potentially live and capacity-covered. A newly `NON_CONFORMANT` or invalidated proof does not retroactively prove broker rejection or zero quantity.

---

## 19. Degraded and Protective Operation

Construction uncertainty blocks ordinary new risk. Protective, reduction, cancel, or containment commands are not exempt.

Only a separately approved and classified action with an exact Authorized Construction Envelope, conservative Economic Effect Envelope, committed protective capacity, current Order Admissibility Decision, current authority, conformant command, and final-egress proof may proceed.

A compiler may not change order type, price, route, side, quantity, position effect, or broker flags to “make protection work” unless that exact alternative was pre-authorized and every intermediate effect remains inside the Hard Safety Envelope.

If no conforming executable protective command exists, the system SHALL contain, HALT, escalate, preserve existing protection, and treat exposure as trapped or insufficiently protected. It SHALL NOT fabricate a permissive command, reuse stale proof, or call priority a reserve.

---

## 20. Failure, Partition, Restart, and Restore

Loss or partition of Intent, policy, mapping, schema, registry, compiler, serializer, SDK, compatibility, context, venue constraint, RCL, authority, proof, or final-egress currentness blocks new risk for the affected scope.

A compiler replica, cache, adapter, or egress instance cannot continue from a last-known permissive mapping or proof after losing active currentness. Restrictive generations and local deny latches dominate.

Restart, failover, rollback, restore, or deployment SHALL fence stale compiler and serializer identities. A former instance is potentially active until hard fencing is proven. Restored commands are evidence, not permission.

Compiler/control-plane partition while broker connectivity remains alive is a high-severity path. No command may be sent unless the complete current construction, capacity, authority, venue, and egress chain is independently proven within the fenced protocol.

---

## 21. Recovery and Non-Revival

Recovery follows ADR-002-017 and SHALL establish:

- fresh current Intent and approval state;
- current construction policy, generation, mappings, schemas, compiler, serializer, SDK, and compatibility;
- current Critical Input and Venue Constraint artifacts;
- conservative inventory of every command, attempt, broker order, fill, UNKNOWN, and capacity commitment;
- invalidation of stale commands, proofs, capabilities, and publishers;
- fresh command/proof for any future mutation;
- current final-egress readiness and a new governed authorization/re-arm chain where live scope was suspended.

Identical recompilation, replay equivalence, passing regression tests, broker reconnect, cache restore, process health, or recovered credentials cannot revive an old proof or authority. Recovery completion does not automatically re-arm.

---

## 22. Evidence, Metrics, and Alerts

Evidence SHALL preserve:

- Intent, approval, envelope, policy, Construction Generation, compiler, schemas, mappings, dependencies, serializer, SDK, and compatibility identities/digests;
- complete canonical inputs, command, proof, numeric derivations, Economic Effect Envelope, capacity dominance, and decision results;
- actual outbound representation, signer input, endpoint, route, session, idempotency identity, first-byte ordering, and broker evidence;
- split/aggregation plan, child commands, retries, cancels, amendments, replacements, partial fills, and lineage;
- invalidation trigger, dependency closure, propagation, denial, recovery, and incident evidence;
- failed, unknown, non-canonical, non-deterministic, overflow, parser differential, and bypass attempts.

Required metrics and alerts include:

- construction result by policy, compiler, broker, command, and failure reason;
- Intent/command/proof/outbound digest mismatch;
- unit, multiplier, sign, quantity, rounding, price, account, symbol, route, and mode mismatch;
- unknown, duplicate, extra, defaulted, or omitted field count;
- Construction Generation lag at compiler, capability issuer, and every egress;
- proof invalidation-to-egress denial latency;
- post-proof mutation, serializer/signature differential, redirect, and SDK-default detection;
- split aggregate effect and child completion discrepancies;
- broker acceptance of a command locally classified non-conforming;
- stale compiler, restored proof, bypass, and automatic-rearm attempts.

ADR-002-016 governs evidence custody and replay. Evidence does not create conformance or authority.

---

## 23. Security and Common-Mode Analysis

The design SHALL protect policies, schemas, mappings, compiler builds, dependencies, serializers, SDKs, registries, canonicalization rules, commands, proofs, and invalidations from unauthorized widening, rollback, substitution, suppression, and replay.

Common-mode analysis SHALL include:

- the same wrong symbol/unit/multiplier/sign logic in compiler and verifier;
- shared generated models or schemas used by approval, compiler, and egress;
- shared broker SDK parser/serializer on both proof and comparison paths;
- one administrator controlling policy, mappings, compiler deployment, and compatibility attestations;
- numeric library, locale, platform, floating-point, Unicode, and canonicalization differences;
- signer, proxy, queue, or route capable of post-proof mutation;
- compromised test fixtures or replay baselines that reproduce the same wrong mapping.

Independent verification must differ in effective control and failure path, not merely process name. Where true independence is unavailable, residual risk and live-scope reduction follow SAFE-034.

No compiler, mapping, registry, test, evidence, or replay principal may combine usable live-order authority with a broker-order route.

---

## 24. Rejected Alternatives

### 24.1 Broker SDK Type Safety Is Conformance

Rejected. Types can encode the wrong account, unit, side, multiplier, default, or economic effect.

### 24.2 Adapter Validation Is Sufficient

Rejected. The adapter may share the same defect and cannot replace final-egress actual-representation verification.

### 24.3 Broker Acceptance Proves Correctness

Rejected. Brokers can accept economically unintended but syntactically valid commands.

### 24.4 Risk-Reducing Rounding Needs No Approval

Rejected. It can remove protection, create residual exposure, or violate the evaluated command shape.

### 24.5 Signed Quantity Alone Defines Direction

Rejected. Side, position effect, and quantity semantics may be independent.

### 24.6 Default Account, Route, TIF, or Order Type

Rejected unless the invariant default is explicitly canonicalized, capability-evidenced, and approved.

### 24.7 Retry Reuses Prior Proof and Capability

Rejected. Each attempt follows current state and single-use authority rules.

### 24.8 Aggregate Several Intents for Efficiency

Rejected by default because it loses capacity, attribution, partial-fill, and cancellation semantics.

### 24.9 Downstream Signer May Normalize the Request

Rejected. A signer that can change meaning is inside the full final gate and must verify the exact command.

### 24.10 Unknown Field Is Forward Compatible

Rejected. Unknown safety-relevant semantics are denial until approved.

### 24.11 Human Confirms the Command Looks Right

Rejected. Human review cannot replace deterministic proof or final enforcement.

### 24.12 Replay Match or Identical Recompile Restores Permission

Rejected. Evidence equivalence cannot revive authority or live state.

---

## 25. Consequences

### 25.1 Positive

- SAFE-033 becomes an explicit deterministic protocol rather than an adapter convention.
- Unit, multiplier, direction, account, symbol, and rounding errors are fenced before send.
- Broker payloads remain bound to the exact approved economic effect and capacity.
- Downstream serializers, signers, queues, SDKs, and proxies cannot silently mutate live commands.
- Retry, split, cancel, and replacement lineage remains explicit and conservative.
- Final egress verifies the actual outbound representation.
- Compiler recovery cannot revive prior authority.

### 25.2 Negative

- Every broker API, command type, schema, mapping, compiler, serializer, and SDK version needs governance and evidence.
- Canonicalization and independent reproduction add engineering complexity and latency.
- Closed envelopes reject opportunistic adapter behavior and silent broker defaults.
- Split and aggregate execution require explicit capacity and attribution models.
- Some broker SDKs or intermediaries may be non-conforming if actual outbound semantics cannot be observed and proven.

These costs are accepted because convenience cannot justify unintended economic effect.

---

## 26. Acceptance Cases

### IOC-AC-001 — Direction and Position-Effect Inversion

Invert buy/sell, long/short, open/close, reduce-only, signed quantity, and zero-crossing semantics. Every unintended effect must be rejected.

### IOC-AC-002 — Account, Instrument, Contract, Environment, and Route Substitution

Substitute default account, symbol alias, contract month, venue, live/non-live environment, endpoint, redirect, or route at each construction and egress boundary. No substitution may survive.

### IOC-AC-003 — Unit, Multiplier, Currency, Scale, and Numeric Safety

Exercise wrong units, multiplier, currency, sign, scale, precision, overflow, underflow, NaN/infinity, negative zero, exponent, and platform/locale variation. Construction must fail or remain exactly equivalent.

### IOC-AC-004 — Quantity, Tick, Lot, and Rounding

Exercise min/max/step, fractional and odd lots, tick boundaries, clamps, truncation, and “risk-reducing” rounding that removes protection. Only exact authorized results may pass.

### IOC-AC-005 — Price, Order Type, TIF, Expiration, Flags, and Mode

Mutate price aggressiveness, trigger, order type, time in force, expiry, route, reduce/post-only, auction, and live/paper mode. Every widening or semantic mismatch must be denied.

### IOC-AC-006 — Economic Effect and Capacity Dominance

Inject partial fill, reversal, reduce-only failure, broker rounding, fees/cash legs, simultaneous split execution, and replace overlap. The envelope must remain inside exact committed capacity.

### IOC-AC-007 — Canonicalization and Parser Differential

Exercise duplicate JSON keys/FIX tags, unknown fields, field reordering, Unicode and percent encoding, alternate numerics, null/default ambiguity, SDK/model disagreement, and byte/semantic digest mismatch. Ambiguity must fail closed.

### IOC-AC-008 — Post-Proof Mutation and Actual-Outbound Equivalence

Mutate or redirect through serializer, signer, queue, proxy, sidecar, SDK, session manager, and retry wrapper after proof. Final egress must detect every semantic or route change.

### IOC-AC-009 — Retry, Cancel, Amend, Replace, Split, and Aggregate

Lose ACK, cross cancel/fill, change retry payload, regenerate remaining quantity, overlap replacement, duplicate split child, and aggregate unrelated Intents. Identity, capacity, proof, and no-blind-retry rules must hold.

### IOC-AC-010 — Protective and Exit Construction

Attempt to change side, order type, price, route, quantity, or reduce-only behavior under protective urgency. Label and priority must not bypass exact envelope, admissibility, capacity, or egress.

### IOC-AC-011 — Authority Separation, Compiler Drift, and Bypass

Compromise policy/mapping/compiler/SDK identities, roll back generation, make compiler approve or mutate RCL, expose a broker route, bypass proof, or use human/manual command injection. Every path must be denied and contained.

### IOC-AC-012 — Restart, Restore, Recovery, Replay, and Non-Revival

Restart or restore compiler, mappings, serializer, SDK, cache, signer, egress, and evidence; recompile identically and match replay while old effects remain. Fresh artifacts and governed re-arm are required without capacity release.

Written cases are not completed evidence. Each case maps one-to-one to `IOC-EV-001` through `IOC-EV-012` in VER-002-001 and the Evidence Register.

---

## 27. Requirements Traceability

| Requirement | ADR-002-020 decision |
|---|---|
| SAFE-003, SAFE-004, SAFE-050 | construction policy, schemas, compiler, canonicalization, and compatibility are separately governed and fail closed |
| SAFE-010, SAFE-011 | compiler is non-authorizing; RCL and final egress retain exclusive authority |
| SAFE-013 through SAFE-015 | Economic Effect Envelope binds exact committed capacity; artifact expiry never erases effect |
| SAFE-020, SAFE-021, SAFE-024, SAFE-025 | immutable Intent/attempt/command lineage, broker ambiguity, evidence bounds, and conservative UNKNOWN remain intact |
| SAFE-030 through SAFE-032 | exact trusted context and current venue admissibility are mandatory construction inputs, not compiler-created facts |
| SAFE-033 | every actual broker mutation proves exact account, instrument, contract, direction, quantity, unit, price/order constraint, effect, expiry, and mode conformance |
| SAFE-034, SAFE-035 | independent verification accounts for compiler common mode and all time-dependent validity uses trustworthy time |
| SAFE-040, SAFE-043 | protective construction requires exact feasibility, authority, and committed reserve; priority and label create nothing |
| SAFE-041, SAFE-044, SAFE-046, SAFE-048 | restart/recovery is restrictive, old proofs do not revive, and re-arm is explicit |
| SAFE-051, SAFE-052 | deterministic fault injection, actual outbound evidence, replay isolation, and independent review are mandatory |

---

## 28. Open Implementation Questions

1. What canonical Intent, Authorized Construction Envelope, command, effect, and proof schemas are approved?
2. Which deterministic numeric types, rational/decimal libraries, unit system, overflow rules, and canonicalization format are conforming?
3. Which account, instrument, contract, symbol, route, price, tick, lot, multiplier, currency, and position-effect registries are authoritative?
4. How is independent reproduction separated from compiler common modes in schemas, generated models, libraries, SDKs, and administration?
5. How does final egress observe and compare the actual outbound representation after SDK, signing, proxy, queue, and session processing?
6. Which fields are truly transport-only, and how is non-economic/non-routing relevance independently proven?
7. Which brokers and order types permit deterministic split, aggregation, same-command retry, cancel, amend, or replace semantics?
8. What Construction Generation and invalidation substrate fences stale compiler, serializer, capability issuer, and egress instances?
9. How is proof currentness obtained without permissive cache or a circular dependency at final egress?
10. What failure-domain allocation prevents one mapping, numeric, schema, compiler, serializer, SDK, signer, or administrator defect from fooling both construction and verification?
11. How are broker-accepted but locally non-conforming commands contained, reconciled, and preserved as incidents?
12. What approved values and measurement definitions govern proof invalidation-to-egress, command age, proof age, and composition with capability-claim-to-first-byte bounds?

Unresolved questions reduce or prohibit live scope. They SHALL NOT permit a default, guessed mapping, optimistic effect, or bypass.

---

## 29. Approval Gate

ADR-002-020 remains `Proposed` until all applicable conditions pass:

1. Approved Intent, Order Construction Policy, Authorized Construction Envelope, Canonical Broker Command, Economic Effect Envelope, and Order Conformance Proof schemas and canonicalization are approved.
2. Account/instrument/contract/route, side/position-effect, unit/multiplier/currency, numeric, price/order, expiration, mode, and broker-field rules are complete for each supported scope.
3. Deterministic compiler, independent verifier, serializer, SDK, signer, queue/proxy, and actual-outbound comparison mechanisms are implemented and security-reviewed.
4. Exact command/proof/effect binding is enforced through approval, Intent, venue decision, RCL capacity, Live Authorization, capability, Commit Proof, evidence, and final egress.
5. RCL-only capacity mutation, conservative UNKNOWN, missing-ACK, cancel-ACK, retry, split/aggregate, replacement, and economic-continuity rules are demonstrated.
6. Final egress rejects every stale, mutated, non-canonical, unsupported, ambiguous, wrong-scope, or unproven command without repairing or recompiling it.
7. Compiler and supporting identities hold no approval, capacity, protective-classification, live credential, broker-route, HALT-clear, or re-arm authority.
8. Construction Generation, dependency closure, invalidation propagation, stale publisher fencing, recovery, and non-revival are implemented.
9. Numeric bounds and limits are approved in the Verification Profile and measured under fault injection.
10. `IOC-EV-001` through `IOC-EV-012` are executed at required EV-L1/EV-L2/EV-L3, Broker, and Security levels with independent review.
11. All Critical or Major findings from architecture, numeric, canonicalization, parser-differential, and security review are resolved.
12. Architecture Gate acceptance, restricted-live, and production criteria pass for the exact proven scope.

This ADR authorizes architecture and implementation-planning work only. It creates no live trading authority and makes no verification-completion or live-readiness claim.
