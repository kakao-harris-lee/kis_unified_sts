# RFC-002 — Trading Operating System Architecture

**Document ID:** RFC-002
**Title:** Trading Operating System Architecture
**Version:** 0.2 Review Draft
**Status:** Review Draft — Architecture
**Classification:** Foundational Architecture Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Safety Authority:** Constrained by RFC-001 — Safety Case
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-13
**Last Updated:** 2026-07-13

---

## 1. Abstract

This document defines the architecture of the Trading Operating System (TOS).

RFC-000 defines the constitutional principles that SHALL remain true.

RFC-001 defines the hazards and safety properties that SHALL be controlled.

RFC-002 defines the system boundaries, components, authority relationships, state models, trust boundaries, failure behavior, and architectural mechanisms required to satisfy those constitutional and safety obligations.

This document is not a trading-strategy specification.

It does not define:

* alpha-generation logic;
* concrete trading signals;
* market-specific numeric limits;
* profitability targets;
* broker-specific implementation code;
* deployment-specific sizing.

The architecture SHALL be evaluated primarily by its ability to:

1. preserve capital and survivability;
2. prevent unauthorized or unbounded exposure;
3. remain fail-closed under uncertainty;
4. maintain authoritative operational state;
5. contain component failures;
6. produce objective safety evidence;
7. support controlled recovery without silently restoring trading authority.

---

## 2. Normative Authority

RFC-002 is subordinate to:

1. RFC-000 — Trading Constitution;
2. RFC-001 — Safety Case.

RFC-002 SHALL NOT:

* reinterpret constitutional intent;
* weaken a `CONST-xxx` requirement;
* weaken a `SAFE-xxx` requirement;
* convert a fail-closed safety property into fail-open behavior;
* replace preventive control with monitoring or audit;
* introduce an architecture that requires safety requirements to be bypassed for normal operation.

Where RFC-002 is ambiguous, the safer interpretation SHALL apply.

Where RFC-002 conflicts with RFC-000 or RFC-001, the higher-level specification SHALL govern and the conflict SHALL be recorded.

---

## 3. Scope

This architecture applies to all components capable of influencing real-capital trading.

The scope includes:

* market and reference data ingestion;
* account and broker state ingestion;
* context construction;
* decision generation;
* independent approval;
* aggregate risk authorization;
* intent creation;
* risk-capacity commitment;
* order transmission;
* order retry and recovery;
* fill and position processing;
* reconciliation;
* safety configuration;
* live authorization;
* emergency containment;
* protective operation;
* evidence capture;
* replay;
* production recovery and re-arming.

The architecture applies across:

* strategies;
* accounts;
* portfolios;
* instruments;
* brokers;
* execution venues;
* automated operation;
* human operational intervention.

---

### 3.1 Terminology

#### 3.1.1 Aggregate Risk Decision

A policy decision that evaluates whether a proposed economic action may be allocated risk capacity under the current evidence, Hard Safety Envelope, Runtime Safety Profile, existing commitments, confirmed positions, potentially-live orders, UNKNOWN exposure, external or unattributed exposure, trapped exposure, and protective reserves.

An Aggregate Risk Decision does not itself mutate the Risk Capacity Ledger.

#### 3.1.2 Capacity Commitment

An atomic, exclusive, durable allocation of aggregate risk headroom to a uniquely identified economic action, reservation pool, or protective lease.

A commitment reduces capacity available to all other competing actions. Only the authoritative Risk Capacity Ledger transition function may create, resize, quarantine, transfer, or release a Capacity Commitment.

#### 3.1.3 Protective Capacity Consumption

The binding of a portion of an already committed Reserved Protective Capacity pool to a specific protective action.

Protective Capacity Consumption:

* is not a new aggregate commitment;
* SHALL remain within an existing protective lease or pre-committed pool;
* SHALL be exclusive and durable;
* SHALL NOT enlarge the aggregate authority granted by the original commitment;
* SHALL fail closed when exclusivity, scope, epoch, or remaining capacity cannot be proven.

#### 3.1.4 Potentially-Live Quantity

The conservative upper bound of quantity that may still produce broker-side economic effect.

Potentially-Live Quantity includes, as applicable:

* transmitted quantity whose acceptance is not disproven;
* acknowledged but unfilled quantity;
* quantity under cancel-pending or replace-pending state;
* quantity associated with UNKNOWN transmission outcome;
* duplicate or overlapping attempts that cannot be proven deduplicated;
* late-fill exposure that remains possible under the Broker Capability Profile.

Potentially-Live Quantity is not reduced merely because an acknowledgement timed out, a cancel request was accepted, an order was absent from one query, a process restarted, or a local authorization expired.

#### 3.1.5 Final Quantity Proof

Evidence sufficient, under the approved Broker Capability Profile and reconciliation model, to establish both:

1. final cumulative filled quantity; and
2. zero remaining executable quantity.

A cancel acknowledgement alone is not Final Quantity Proof unless the Broker Capability Profile proves that the acknowledgement is ordered after all possible fills and is complete for the relevant order identity.

#### 3.1.6 Authority Epoch

A monotonically increasing fencing value that identifies the current authority generation for a state-changing safety domain.

A stale epoch SHALL NOT be accepted for capacity commitment, capacity release, transmission permission, protective lease consumption, live authorization, or Safety Authority grants.

#### 3.1.7 Transmission Capability

A single-use, scope-limited authorization presented to the final broker-egress enforcement point.

A Transmission Capability SHALL be bound to at least:

* intent identity;
* reservation identity;
* account and instrument scope;
* maximum economic effect;
* authority epoch;
* live authorization identity;
* Hard Safety Envelope version;
* Runtime Safety Profile version;
* action class;
* one-time use identity.

#### 3.1.8 Trapped Exposure

Confirmed or conservatively inferred exposure that cannot currently be reduced within the approved liquidity, venue, price-limit, session, margin, or operational constraints.

Trapped Exposure SHALL be treated as non-reducible when computing available capacity.

#### 3.1.9 Unattributed External Exposure

A broker-side order, fill, position, balance, margin, or instrument-identity change that cannot be attributed to an authorized TOS Intent, an authorized operator action, or a recognized non-trade event.

Unattributed External Exposure SHALL consume conservative capacity and block new risk until disposition is complete.

---

## 4. Architectural Goals

The architecture SHALL provide the following properties.

### 4.1 Safety Before Availability

Loss of trading availability is preferable to granting unverified authority to create risk.

### 4.2 Prevention Before Detection

Unsafe actions SHALL be rejected before transmission whenever prevention is possible.

Detection, alerting, audit, and replay SHALL NOT replace pre-trade prevention.

### 4.3 Explicit Authority

No component SHALL infer live trading authority from deployment location, account credentials, process state, or previous successful operation.

Every exposure-increasing action SHALL possess explicit and current authority.

### 4.4 Authoritative State Through Evidence

No single state source SHALL be assumed infallible.

Safety-relevant state SHALL be established from corroborating evidence and SHALL remain unknown when evidence is insufficient or inconsistent.

### 4.5 Failure Containment

A failure in:

* strategy;
* decision logic;
* market data;
* account state;
* broker adapter;
* messaging;
* configuration;
* time source;
* execution processing;

SHALL NOT automatically disable the independent controls required to contain it.

### 4.6 Bounded Action

Every order-producing path SHALL be bounded by:

* authorization;
* risk capacity;
* action rate;
* account and instrument scope;
* live-mode scope;
* time validity;
* safety configuration.

### 4.7 Recovery Without Automatic Trust

Restart, reconnect, failover, or restored connectivity SHALL NOT automatically restore live trading authority.

---

## 5. Architecture Drivers

The following safety properties are mandatory architectural inputs.

| Driver                         | Principal requirements                 |
| ------------------------------ | -------------------------------------- |
| Constitutional safe state      | SAFE-001, SAFE-002, SAFE-040, SAFE-043 |
| Hard Safety Envelope           | SAFE-003, SAFE-004, SAFE-050           |
| Pre-trade safety authorization | SAFE-010, SAFE-011, SAFE-012           |
| Aggregate risk authority       | SAFE-013, SAFE-015                     |
| Bounded action rate            | SAFE-014                               |
| Intent and execution integrity | SAFE-020, SAFE-021, SAFE-025           |
| Reconciliation                 | SAFE-022, SAFE-023, SAFE-024           |
| Trustworthy context            | SAFE-030, SAFE-031, SAFE-034           |
| Venue constraints              | SAFE-032                               |
| Intent-to-order conformance    | SAFE-033                               |
| Trustworthy time               | SAFE-035                               |
| Independent safety authority   | SAFE-041, SAFE-042, SAFE-048           |
| Safe start and resume          | SAFE-044                               |
| Live and non-live segregation  | SAFE-045, SAFE-046, SAFE-047           |
| Evidence and replay            | SAFE-051, SAFE-052                     |

No architecture alternative MAY be selected without demonstrating how it satisfies these drivers.

---

## 6. System Context

The TOS operates between external markets and internal decision-producing systems.

```text
                        +----------------------+
                        |   Human Operators    |
                        +----------+-----------+
                                   |
                                   v
+-------------+       +------------+-------------+       +----------------+
| Market Data | ----> | Trading Operating System | ----> | Broker / Venue |
+-------------+       +------------+-------------+       +----------------+
                                   |
                                   v
                        +----------+-----------+
                        | Evidence and Audit   |
                        +----------------------+
```

The TOS SHALL treat all external systems as potentially:

* unavailable;
* delayed;
* duplicated;
* inconsistent;
* stale;
* partially correct;
* semantically wrong;
* temporarily unreachable.

---

## 7. Trust Boundaries

The architecture SHALL explicitly represent the following trust boundaries.

### 7.1 Market and Reference Data Boundary

Inputs crossing this boundary SHALL NOT be trusted until validated for:

* source;
* timestamp;
* freshness;
* instrument identity;
* unit;
* scale;
* internal consistency;
* venue state.

### 7.2 Broker and Venue Boundary

Broker acknowledgements, fills, positions, balances, and order state SHALL be treated as evidence, not as an infallible truth source.

### 7.3 Strategy Boundary

A strategy SHALL be treated as an untrusted proposer.

A strategy MAY propose intent.

It SHALL NOT:

* approve its own intent;
* reserve aggregate risk capacity directly;
* alter safety limits;
* arm live mode;
* transmit live orders;
* classify its own action as protective without independent validation.

### 7.4 Safety Control Boundary

Safety controls SHALL remain outside the authority of strategy and ordinary decision components.

### 7.5 Human Operations Boundary

Human commands SHALL be authenticated, authorized, scoped, time-bounded, and audited.

A human command SHALL NOT silently bypass constitutional safety controls.

### 7.6 Live and Non-Live Boundary

Research, backtest, simulation, development, test, and paper-trading environments SHALL NOT possess a path to live execution authority.

---

## 8. Failure Model

RFC-002 assumes that the following failures can occur.

### 8.1 Process Failures

* process termination;
* deadlock;
* infinite loop;
* memory exhaustion;
* partial startup;
* partial shutdown;
* duplicate active instances.

### 8.2 Communication Failures

* packet loss;
* delayed messages;
* duplicated messages;
* reordered messages;
* network partition;
* stale connection;
* half-open connection.

### 8.3 Data Failures

* stale market data;
* crossed or invalid price;
* incorrect unit;
* incorrect multiplier;
* incorrect symbol mapping;
* missing field;
* inconsistent account state;
* broker-side state error.

### 8.4 Execution Failures

* lost acknowledgement;
* duplicate submission;
* partial fill;
* asynchronous fill;
* cancel/replace race;
* broker rejection;
* unknown order state;
* fill after timeout;
* fill after restart.

### 8.5 Configuration Failures

* missing Safety Profile;
* wrong account scope;
* wrong instrument scope;
* unit error;
* scale error;
* partially activated configuration;
* valid but unsafe configuration;
* stale live authorization.

### 8.6 Time Failures

* clock rollback;
* clock jump;
* drift;
* frozen clock;
* source disagreement;
* unverified time source;
* incorrect session evaluation.

### 8.7 Operational Failures

* manual broker trade;
* third-party account activity;
* incorrect live arming;
* wrong account selection;
* delayed emergency response;
* operator interface failure.

The architecture SHALL NOT assume that only one failure category occurs at a time.

---

## 9. Architectural Overview

The TOS SHALL separate the **Trading Data Plane** from the **Safety Control Plane**.

```text
+-------------------------------------------------------------------+
|                       Safety Control Plane                         |
|                                                                   |
|  Hard Safety Envelope     Safety Authority     Live Authorization |
|           |                       |                     |           |
|           +------------+----------+---------------------+           |
|                        |                                          |
|              Aggregate Risk Authority                             |
|                        |                                          |
+------------------------+------------------------------------------+
                         |
                         | Current, verifiable authority
                         v
+-------------------------------------------------------------------+
|                       Trading Data Plane                           |
|                                                                   |
|  Context -> Decision -> Approval -> Intent -> Execution -> Fills |
|                                              |                    |
|                                              v                    |
|                                      Position Projection          |
+-------------------------------------------------------------------+
                         |
                         v
+-------------------------------------------------------------------+
|               Reconciliation and Evidence Plane                   |
|                                                                   |
|  Account Evidence   Order Evidence   State Reconciliation         |
|  Audit Store        Replay Evidence  External Activity Detection  |
+-------------------------------------------------------------------+
```

The separation SHALL be based on authority and failure containment, not merely source-code packaging.

---

### 9.1 Authority Ownership

The following matrix is the normative authority model.

| Action | Policy authority | State-transition or enforcement authority | Prohibited combination |
|---|---|---|---|
| Propose trading action | Decision Service | None | Decision Service SHALL NOT approve, commit, or transmit |
| Approve proposal | Independent Approval Service | None | Approval Service SHALL NOT commit or transmit |
| Evaluate venue and order admissibility | Venue Constraint Policy governance supplies rules | Venue Constraint Gate produces a non-authorizing decision; Broker Egress Gateway enforces the exact current result | Venue Constraint Gate SHALL NOT approve, commit capacity, classify protection, transmit, or arm live scope |
| Evaluate aggregate risk | Aggregate Risk Authority | None | Aggregate Risk Authority SHALL NOT mutate capacity or transmit |
| Commit normal risk capacity | Aggregate Risk Authority supplies a grant decision | Risk Capacity Ledger is the sole serialization and mutation authority | Execution Coordinator SHALL NOT mutate capacity |
| Pre-commit protective pool | Aggregate Risk Authority supplies a grant decision | Risk Capacity Ledger commits the pool | Protective Action Controller SHALL NOT enlarge the pool |
| Consume protective reserve | Protective Action Controller classifies and requests consumption within a valid lease | Protective sub-ledger or Risk Capacity Ledger transition function defined by ADR-002-002 | Strategy SHALL NOT self-label an action as protective |
| Issue Safety Authority | Safety Authority | Final broker egress validates current epoch and scope | Safety Authority SHALL NOT hold broker transmission credentials |
| Arm live scope | Live Authorization Service | Final broker egress validates scope | Limit administrator SHALL NOT also arm live scope |
| Change Runtime Safety Profile | Safety Profile governance authority | Safety Profile Validator activates only after validation | Live armer SHALL NOT change limits |
| Change Hard Safety Envelope | Independent Hard Safety Envelope governance | Hard Safety Envelope Registry publishes an immutable version | Runtime trading identity SHALL NOT administer the envelope |
| Create transmission attempt | Execution Coordinator | Intent Registry and Risk Capacity Ledger bind the attempt before send | Broker Adapter SHALL NOT invent an unbound attempt |
| Transmit | Execution Coordinator requests | Broker Adapter / Broker Egress Gateway is the final enforcement point | No valid Transmission Capability means no send |
| Retry | Execution Coordinator under Broker Capability Profile rules | Broker egress enforces attempt identity and reservation | UNKNOWN outcome SHALL NOT cause blind resubmission |
| Cancel ordinary order | Execution Coordinator requests | Cancellation Arbiter authorizes; broker egress sends | Ordinary cancellation SHALL NOT remove required protection |
| Cancel protective order | Protective Action Controller requests | Cancellation Arbiter authorizes; broker egress sends | Strategy SHALL NOT directly cancel safety-owned protection |
| Classify protective action | Protective Action Controller | Aggregate-risk proof and protective rules enforce classification | Decision Service SHALL NOT classify its own action as protective |
| Halt | Safety Authority or authenticated emergency operator | Broker-egress deny gate applies monotonically | Halt SHALL NOT depend on proposer availability |
| Re-arm | Recovery Coordinator verifies prerequisites; Live Authorization Service issues new authority; explicit human control approves | Broker egress accepts only the new epoch and scope | Automatic re-arm is prohibited |
| Reconcile | Reconciliation Service evaluates evidence | Ledger transitions only through defined proof rules | Reconciliation Service SHALL NOT arbitrarily release capacity |

During a Safety Control Plane partition, no new aggregate capacity may be committed. A Protective Action Controller may consume only capacity pre-committed to a valid, exclusive, scope-limited protective lease before the partition. Consumption SHALL remain within the lease and be serialized by the protective sub-ledger or equivalent mechanism defined by ADR-002-002. If exclusivity or current lease validity cannot be proven, no protective transmission is permitted.

ADR-002-015 defines effective Human Safety Principal independence, exact approval artifacts, dual-control quorum, delegation, one-human restrictive HALT, break-glass confinement, approval consumption, compromise, and recovery behavior. Human approval remains separate from configuration activation, capacity mutation, Live Authorization issuance, and broker transmission.

---

## 10. Core Architectural Components

### 10.1 Context Integrity Service

Responsibilities:

* ingest market, reference, account, and venue inputs;
* validate provenance;
* validate freshness;
* validate units and mappings;
* calculate context confidence;
* expose only validated context to Decision and Approval;
* signal degraded or unknown context.

The Context Integrity Service SHALL NOT authorize trading.

ADR-002-018 defines the normative Critical Input Policy, source identity and continuity, observation and transformation provenance, immutable Snapshot and Decision Context Capsule, independent-approval common-mode analysis, correction/invalidation fan-out, exact proposal-to-egress context binding, and active final-egress currentness rules. Context validity is a mandatory input to separately owned authority and never creates approval, capacity, Live Authorization, protective classification, broker transmission, or re-arm permission.

Venue, session, tradability, account, margin, settlement, and broker-constraint facts are Critical Inputs. Their input integrity is governed here and by ADR-002-018; exact order admissibility and final-egress constraint fencing are delegated to ADR-002-019.

---

### 10.2 Decision Service

Responsibilities:

* consume immutable validated context;
* generate proposed trading intent;
* provide decision rationale;
* identify intended account, instrument, direction, quantity, and constraints.

The Decision Service SHALL NOT:

* approve its own decision;
* transmit orders;
* reserve risk capacity;
* modify safety configuration.

---

### 10.3 Independent Approval Service

Responsibilities:

* validate intent against approved policy;
* independently verify safety-critical intent fields;
* validate account, instrument, direction, quantity, unit, and price constraints;
* reject intent that does not conform to trusted context.

Approval SHALL NOT imply final execution authority.

---

### 10.4 Aggregate Risk Authority

Responsibilities:

* calculate projected aggregate post-action risk;
* use conservative evidence bounds rather than optimistic point estimates;
* include confirmed positions, Potentially-Live Quantity, partial fills, UNKNOWN orders, trapped exposure, replacement overlap, committed capacity, external or unattributed exposure, margin, liquidity, basis, concentration, and protective reserves;
* enforce the Hard Safety Envelope and Safety Profile;
* grant or deny aggregate risk allocation;
* produce a signed or otherwise strongly bound decision referencing the evaluated evidence version and requested capacity vector.

The Aggregate Risk Authority is the sole policy authority permitted to grant or deny aggregate risk allocation. The Risk Capacity Ledger is the sole serialization point and state-transition authority permitted to create, change, quarantine, transfer, or release a Capacity Commitment. Neither component may independently perform both policy approval and broker transmission.

The Aggregate Risk Authority SHALL NOT mutate the Risk Capacity Ledger, transmit broker orders, or release capacity.

---

### 10.5 Risk Capacity Ledger

Responsibilities:

* record available aggregate safety capacity;
* record committed capacity;
* bind capacity to immutable Intent identity;
* prevent concurrent double commitment;
* recover capacity state after restart;
* release capacity only on confirmed lifecycle transitions.

It SHALL:

- provide linearizable commitment semantics for competing capacity requests;
- reject stale authority epochs and stale evidence versions where required;
- atomically bind each commitment to a unique reservation identity and intent identity;
- prevent duplicate reservation and duplicate consumption;
- track normal and protective pools separately;
- represent potentially-live, confirmed-position, UNKNOWN, trapped, and unattributed consumption;
- prohibit release without the evidence required by the applicable release rule;
- preserve commitments across process restart and failover;
- expose an auditable transition history;
- support startup reconciliation before normal live authority is restored.

It SHALL NOT:

- infer that a broker order is absent from a single missing query result;
- release capacity solely due to TTL expiry after an attempt may have become live;
- accept mutation from a fenced or stale writer;
- permit Execution Coordinator or Reconciliation Service to bypass transition rules.

A strategy SHALL NOT write directly to the Risk Capacity Ledger.

---

### 10.6 Intent Registry

Responsibilities:

* assign immutable Intent identity;
* retain the approved intent;
* associate all orders, retries, replacements, cancellations, fills, and evidence with the originating intent;
* maintain intent lifecycle state.

---

### 10.7 Execution Coordinator

Responsibilities:

* accept only approved and capacity-committed intents;
* verify current Safety Authority;
* verify live authorization;
* construct broker-specific order commands;
* enforce action-rate limits;
* preserve at-most-authorized exposure effect;
* maintain potentially live order state;
* coordinate retries and recovery.

The Execution Coordinator SHALL NOT infer that a missing acknowledgement means rejection.

---

### 10.8 Broker Adapter / Broker Egress Gateway

Responsibilities:

* translate approved execution commands;
* transmit orders;
* receive acknowledgements and fills;
* query order, position, balance, and margin state;
* preserve broker identifiers and timestamps;
* expose broker evidence without declaring it authoritative.

Broker-specific behavior SHALL remain isolated behind the Broker Adapter boundary.

Before any risk-relevant transmission, it SHALL verify:

- valid and unused Transmission Capability;
- matching intent and reservation identities;
- current commitment epoch;
- current Safety Authority epoch or valid degraded protective lease;
- valid live scope;
- allowed account, instrument, action class, and maximum quantity;
- applicable Hard Safety Envelope and Runtime Safety Profile versions;
- exact current Venue Constraint Snapshot and Order Admissibility Decision binding;
- current venue, session, halt, tradability, account, margin, settlement, and broker-constraint generation;
- conformance of broker request to the authorized economic effect.

It SHALL reject the request when any required fact is missing, stale, conflicting, or unverifiable.

The Broker Adapter / Broker Egress Gateway is the final live-transmission enforcement point. It SHALL NOT expose a general-purpose live-order method to strategy, research, simulation, backtest, or operator-interface components.

No broker integration may be approved for live use without a versioned, evidence-backed Broker Capability Profile covering the supported broker, API, account, market, order type, and session scope. Missing, contradictory, or insufficient capability evidence SHALL reduce or prohibit live scope; it SHALL NOT weaken a safety requirement.

---

### 10.9 Reconciliation Service

Responsibilities:

* collect corroborating state evidence;
* compare internal state, outbound records, broker queries, fills, and account state;
* establish or revoke reconciled-state status;
* detect unattributed external activity;
* maintain unknown state until evidence is sufficient;
* block new risk while material divergence remains unresolved.

---

### 10.10 Position and Order Projection

Responsibilities:

* maintain confirmed positions;
* maintain potentially live order quantities;
* represent partial and asynchronous fills;
* represent trapped exposure;
* expose conservative projected aggregate state;
* distinguish submitted, acknowledged, partially filled, filled, cancelled, and unknown state.

Projection state SHALL NOT silently replace reconciled authoritative state.

---

### 10.11 Safety Authority

Responsibilities:

* grant current authority to create new risk;
* revoke authority;
* suspend autonomous trading;
* enter degraded or safe operation;
* coordinate emergency containment;
* provide independently verifiable authority state.

Loss of verifiable Safety Authority contact SHALL revoke new-risk authority.

---

### 10.12 Hard Safety Envelope Registry

Responsibilities:

* hold independently governed maximum authority;
* validate Safety Profiles;
* prevent runtime expansion beyond approved ceilings;
* expose versioned, authenticated envelope state.

The Hard Safety Envelope SHALL NOT be modifiable by normal strategy operation.

ADR-002-014 defines the normative immutable envelope artifact, independent governance, generation, semantic comparison, activation, restriction, rollback, restore, compatibility, and evidence contract.

---

### 10.13 Live Authorization Service

Responsibilities:

* authorize live mode for a defined scope;
* bind authorization to account, strategy, instrument, venue, software version, Safety Profile, and time interval;
* revoke or expire authority;
* default to non-live.

---

### 10.14 Trustworthy Time Service

Responsibilities:

* provide monotonic event ordering;
* validate wall-clock confidence;
* expose time-health state;
* invalidate time-dependent authority when confidence is insufficient;
* prevent stale data or expired authority from appearing valid.

---

### 10.15 Protective Action Controller

Responsibilities:

* classify proposed degraded-mode actions;
* verify projected aggregate risk reduction;
* enforce the approved protective-action envelope;
* use reserved protective capacity;
* deny strategy-labelled protection that does not reduce aggregate risk;
* operate according to ADR-002-001.

Amended responsibilities:

- strategy labels are non-authoritative;
- classification is based on conservative aggregate portfolio risk;
- classification evaluates all credible intermediate fill fractions and execution orderings, not only the intended final state;
- it may consume only pre-committed protective capacity under a valid protective lease;
- it may not enlarge aggregate authority;
- it may not directly mutate the central Risk Capacity Ledger except through the defined transition interface;
- it owns the protective-order lifecycle and participates in cancellation arbitration;
- when the protective action cannot be proven risk reducing, it is treated as risk increasing and denied in degraded mode.

---

### 10.16 Evidence Store

Responsibilities:

* retain immutable safety-relevant evidence;
* associate evidence with requirement, intent, order, state transition, configuration version, and software version;
* support replay and incident reconstruction;
* preserve rejection and failure evidence as well as successful actions.

ADR-002-016 defines the normative Safety Evidence Envelope, Evidence Integrity Policy, pre-effect durability, commit-receipt semantics, causal ordering, integrity anchoring, gap detection, retention, redaction, isolated deterministic replay, incident reconstruction, and non-revival rules. Evidence remains detective and recovery material and cannot become capacity, approval, reconciliation, Live Authorization, protective-classification, or broker-transmission authority.

---

### 10.17 Operator Control Interface

Responsibilities:

* expose current safety state;
* expose open and trapped exposure;
* expose unknown execution state;
* permit authenticated emergency commands;
* prevent silent live re-arming;
* preserve complete audit evidence.

ADR-002-015 defines the normative authenticated Human HALT, Approval Request, Approval Attestation, Approval Set, Effective Principal Graph, delegation, session, break-glass, and approval-revocation contracts for this interface.

---

### 10.18 Safety Profile Validator

Responsibilities:

* validate completeness, authenticity, version, account scope, instrument scope, units, multipliers, currencies, sign conventions, and temporal validity;
* validate every Runtime Safety Profile value against the independently governed Hard Safety Envelope;
* reject semantically implausible or internally inconsistent values;
* prevent partial activation;
* activate a profile atomically, or leave the previous valid profile in force only when continued use is explicitly authorized and time-valid;
* fail closed when correctness cannot be proven.

The Safety Profile Validator SHALL be independent from strategy configuration and SHALL NOT expand the Hard Safety Envelope. The identity permitted to approve or publish a Runtime Safety Profile SHALL NOT also arm live trading.

ADR-002-014 defines the complete Safety Configuration Bundle, canonical semantic validation, consumer-compatibility attestations, quorum-committed Profile Generation, break-before-make atomic activation, restrictive precedence, and rollback non-revival rules.

---

### 10.19 Recovery Coordinator

Responsibilities:

* enforce the startup and recovery barrier;
* coordinate account-wide reconciliation of orders, fills, positions, cash, margin, capacity commitments, external activity, and recognized non-trade events;
* verify current authority epochs and trustworthy time;
* require UNKNOWN and unattributed activity to be resolved or conservatively reserved;
* verify ledger consistency and protective-order coverage;
* produce a recovery-readiness decision;
* request, but not issue, new live authorization.

The Recovery Coordinator SHALL NOT automatically re-arm live trading.

ADR-002-017 defines the normative closed startup barrier, monotonic Recovery Generation, fenced Recovery Coordinator ownership, conservative account-wide Inventory Cut, required recovery obligations, bounded convergence, partial-scope isolation, immutable readiness decision, continuous invalidation, and handoff to fresh governed re-arm. Recovery readiness remains an assessment artifact and cannot activate configuration, mutate or release capacity, clear HALT, classify protection, issue Live Authorization, or transmit to a broker.

---

### 10.20 Deployment and Identity Architecture

Responsibilities:

* live and non-live credential segregation;
* workload identity and least-privilege broker credential access;
* deployment provenance and independent safety-component release controls;
* stale-instance removal and fencing integration;
* prevention of research, simulation, paper, and backtest paths from reaching live broker egress.

---

### 10.21 Replay and Evidence Service

Responsibilities:

* retain immutable or tamper-evident evidence sufficient to reconstruct authority, reservation, attempt, broker event, reconciliation, and operator-action timelines;
* support deterministic replay of architecture state transitions;
* preserve evidence provenance and failure-domain metadata.

Replay and audit SHALL NOT substitute for pre-trade prevention.

---

### 10.22 Cancellation Arbiter

Responsibilities:

* provide one authorization point for cancellation of any order that is or may be part of a protective structure;
* determine whether cancellation removes required protection or worsens conservative aggregate risk;
* require equivalent or stronger protection to be authoritatively live where replacement is required;
* account for late fills, partial fills, scarce broker capacity, and non-atomic replace semantics.

Protective evaluation SHALL precede ordinary cancellation authority. Strategy and ordinary execution cleanup SHALL NOT cancel a safety-owned protective order directly.

---

### 10.23 Venue Constraint Gate

Responsibilities:

* evaluate the exact broker-request shape against current venue, market-segment, session-phase, tradability, halt, price, tick, lot, quantity, order-type, time-in-force, account, margin, borrow, settlement, and Broker Capability Profile constraints;
* produce immutable, non-authorizing Venue Constraint Snapshots and Order Admissibility Decisions;
* preserve source continuity, uncertainty, dependency closure, and invalidation generation;
* signal restrictive changes to approval, authority issuance, and final egress;
* distinguish ordinary new risk, reduction, cancellation, protective maintenance, replacement, and containment without assuming any action is executable.

The Venue Constraint Gate SHALL NOT approve an Intent, mutate capacity, issue Live Authorization, classify protection, transmit, clear HALT, or re-arm. `ADMISSIBLE` is a required safety fact, not economic authority. ADR-002-019 defines its exact contract and acceptance gates.

---

## 11. Trading Action Pipeline

The logical action sequence SHALL be:

```text
Critical Input Snapshot and immutable Decision Context Capsule
        ↓
Decision Proposal
        ↓
Independent Approval
        ↓
Intent Registration
        ↓
Projected Aggregate Risk Evaluation
        ↓
Exclusive Risk-Capacity Commitment
        ↓
Current Safety Authority Verification
        ↓
Live Scope Verification
        ↓
Intent-to-Order Conformance
        ↓
Exact Venue and Order Admissibility Decision
        ↓
Transmission
        ↓
Acknowledgement / Fill Processing
        ↓
Reconciliation
        ↓
Capacity Release or Adjustment
```

No stage SHALL be bypassed for an exposure-increasing action.

ADR-002-018 requires the exact Decision Context Capsule identity and digest to remain bound through proposal, independent approval, Intent, capacity, authority, capability, Commit Proof, and final egress. Material context change invalidates affected future permission; it does not erase possible economic effect.

ADR-002-019 additionally requires one exact current Venue Constraint Snapshot and Order Admissibility Decision for the complete broker-request shape. A calendar, quote, connection, or “exit” label does not prove executability; constraint invalidation blocks future new-risk send without erasing prior economic effect.

Protective actions SHALL follow the separate restrictions defined by ADR-002-001.

---

## 12. Orthogonal Trading State Model

The system SHALL NOT represent the entire trading lifecycle as a single order-status enumeration.

At minimum, the following state dimensions SHALL be modeled independently:

1. **Intent State** — proposal and business-authorization lifecycle;
2. **Transmission Attempt State** — local send preparation and transport uncertainty;
3. **Broker Order State** — broker-side order lifecycle;
4. **Knowledge / Evidence State** — confidence, conflict, and reconciliation status;
5. **Capacity State** — reservation, potentially-live, consumed, quarantined, and released state.

A state such as `RECONCILED` belongs to the Knowledge / Evidence dimension, not the Broker Order lifecycle. The model SHALL support combinations such as:

```text
Transmission Attempt: SENT_UNCONFIRMED
Broker Order: UNKNOWN
Knowledge / Evidence: CONFLICTED
Capacity: POTENTIALLY_LIVE
```

### 12.1 UNKNOWN Is a First-Class Condition

An UNKNOWN broker order, transmission outcome, exposure, or evidence condition SHALL NOT be treated as rejected, cancelled, unfilled, safe to retry, or safe to release capacity.

Any such UNKNOWN condition SHALL consume conservative capacity and block new risk in the affected scope. Potentially-Live Quantity SHALL remain covered by committed or quarantined capacity until Final Quantity Proof or confirmed-position transfer is complete.

### 12.2 State Transition Authority

Each transition in each dimension SHALL be attributable to approved internal evidence, broker or venue evidence, a reconciliation result, or an authorized operational action. A transition in one dimension SHALL NOT imply a transition in another without its required evidence and authority.

ADR-002-005 SHALL define the detailed Intent, Transmission Attempt, Broker Order, and Knowledge / Evidence state machines and their transition owners. ADR-002-002 defines the Capacity State dimension and its coupling rules.

---

## 13. Order and Fill Integrity

### 13.1 At-Most-Authorized Exposure

One Intent MAY produce multiple technical messages, retries, or broker orders only when the aggregate potential exposure remains bounded by the approved Intent.

### 13.2 Partial Fills

Position and risk state SHALL update by confirmed fill quantity.

Submission quantity SHALL NOT be treated as filled quantity.

### 13.3 Cancel and Replace

A cancellation request or cancel acknowledgement SHALL NOT release risk capacity. Release after cancellation requires Final Quantity Proof or a stronger broker-specific proof approved by ADR-002-004 and recorded in the active Broker Capability Profile.

Unless that profile proves atomic cancel/replace semantics, the system SHALL reserve the worst credible overlap of the original and replacement orders and account for any interval of reduced or absent protection.

ADR-002-011 defines the normative protective-replacement workflow, Cancellation Arbiter rules, Protection Sufficiency Proof, gap and overlap controls, and acceptance gates.

### 13.4 Restart

After restart, potentially live orders SHALL remain potentially live until reconciled.

### 13.5 Over-Exit Prevention

Protective or exit retries SHALL use confirmed residual exposure and potentially live exit quantity.

The system SHALL NOT resubmit the original full exit quantity solely because a final acknowledgement is missing.

### 13.6 Broker Capability Contract

The Broker Capability Profile SHALL assess at least:

* client-generated order identity support and duplicate-key behavior;
* broker order-number issuance and query attribution;
* order-query completeness, pagination, and history windows;
* cumulative fill query, replay, correction, and event ordering;
* cancel acknowledgement and cancel/replace semantics;
* reduce-only or equivalent position-side enforcement;
* account-wide order, fill, position, balance, and margin visibility;
* push versus poll account events and the external-activity detection bound;
* rate-limit scope, session concurrency, credential fencing, late fills, reconnect, and recovery;
* current venue/session/halt/tradability, price/tick/lot/quantity, order-type/time-in-force, account/margin/borrow/settlement, and rule-change semantics needed by ADR-002-019.

Capability results SHALL be classified as `SUPPORTED`, `SUPPORTED_WITH_RESTRICTION`, `BEST_EFFORT`, `UNAVAILABLE`, or `LIVE_SCOPE_PROHIBITED`.

Where a transmission outcome is UNKNOWN and deterministic broker-side deduplication is unavailable:

1. a new broker order SHALL NOT be blindly submitted;
2. all available broker evidence SHALL be queried;
3. the original reservation SHALL remain fully conservative;
4. unattributable activity SHALL force containment;
5. live scope SHALL be reduced when safe attribution cannot be achieved.

---

## 14. Aggregate Risk Capacity

### 14.1 Aggregate Envelope Invariant

For every governed risk dimension:

```text
Confirmed Position Risk
+ Potentially-Live Order Risk
+ UNKNOWN Order Conservative Bound
+ Unattributed External Exposure
+ Trapped / Illiquid Exposure
+ Replacement Overlap Risk
+ Required Protective Reserve
    <=
Applicable Hard Safety Envelope
```

The Runtime Safety Profile may further restrict this bound but SHALL NOT enlarge it.

### 14.2 Projected State

Risk authorization SHALL evaluate the projected state after the proposed action.

The projected state SHALL include:

* current positions;
* potentially live orders;
* partial fills;
* trapped exposure;
* external account activity;
* committed capacity;
* concurrent actions;
* margin and collateral effects.

### 14.3 Commitment Mapping and Exclusivity

Risk capacity SHALL be committed before transmission.

Commitment SHALL be exclusive for the relevant capacity.

Two actions SHALL NOT consume the same available capacity.

Every potentially executable broker order SHALL map to exactly one active Capacity Commitment or to a specifically identified consumption within a pre-committed protective lease. No active commitment or lease consumption may be reused for another economic action.

### 14.4 Release Conditions and Economic Effect

Capacity MAY be released only when:

* the Intent expires and durable evidence proves that transmission never began;
* the action is definitively rejected before it may have become live;
* confirmed fill risk is atomically transferred to confirmed-position consumption;
* Final Quantity Proof establishes final cumulative filled quantity and zero remaining executable quantity;
* reconciliation supplies a stronger broker-specific proof approved by ADR-002-004.

Authority may expire. Potential economic effect does not expire until terminal quantity is proven.

Once an attempt may have reached the broker, reservation TTL, acknowledgement timeout, process restart, strategy timeout, cancel request, cancel acknowledgement, or authority expiry SHALL NOT release its capacity. The capacity SHALL remain committed, quarantined, or transferred to confirmed-position consumption until the applicable proof exists.

### 14.5 Crash Recovery

Risk-capacity commitments SHALL survive process restart or be reconstructed conservatively before trading resumes.

### 14.6 Trapped Exposure

Trapped exposure SHALL be treated as non-reducible.

No future exit assumption SHALL create additional risk authority.

### 14.7 External and Non-Trade Changes

External activity and recognized non-trade changes SHALL enter the reconciliation and capacity models as first-class inputs.

Corporate actions, symbol or instrument-identity changes, expiry, exercise, assignment, rollover, broker administrative adjustments, account transfers, delisting, and suspension changes SHALL NOT be assumed to be fills. Unrecognized changes SHALL be treated as Unattributed External Exposure.

ADR-002-010 defines the normative event identity, conservative transition envelope, Risk Capacity Ledger remapping, open-order treatment, and recovery requirements.

---

## 15. State Authority and Reconciliation

### 15.1 Evidence-Based State

Authoritative State SHALL be established from available corroborating evidence.

Possible evidence paths include:

* immutable Intent records;
* outbound order records;
* broker acknowledgement;
* order query;
* fill stream;
* position query;
* balance and margin query;
* independently retained audit records.

No specific evidence path SHALL be presumed infallible.

Broker and venue evidence is externally authoritative evidence, but no single response SHALL be treated as unconditional truth. State SHALL be established through evidence-consistency evaluation, source provenance, temporal ordering, and conservative bounds. Unresolved conflict produces UNKNOWN state and blocks new risk.

Reconciliation SHALL maintain confidence or conservative bounds separately for at least:

* order existence;
* broker order identity;
* cumulative filled quantity;
* remaining executable quantity;
* position quantity;
* cash and margin;
* protective coverage;
* instrument identity.

A single blended confidence score is insufficient for risk release.

### 15.2 Divergence

Material divergence SHALL:

* revoke reconciled-state status;
* block new risk-increasing actions;
* initiate reconciliation;
* remain visible to operations.

### 15.3 External Activity

Orders, fills, or positions not attributable to a TOS Intent SHALL be classified as external activity.

External activity SHALL force re-evaluation of:

* positions;
* open orders;
* aggregate risk;
* margin;
* live authorization.

For integrations without real-time account events, the architecture SHALL define a measurable maximum external-activity detection bound. Normal action size and aggregate headroom SHALL be constrained so plausible external activity during that window cannot exceed the Hard Safety Envelope.

### 15.4 Continuous Reconciliation

Reconciliation SHALL occur:

* at startup;
* after restart;
* after reconnect;
* after execution timeout;
* after unknown order state;
* after external activity;
* periodically during live operation;
* before restoring authority after material divergence.

### 15.5 Startup and Recovery Barrier

New risk SHALL remain blocked until the Recovery Coordinator verifies:

* open orders and potentially-live attempts;
* cumulative fills and positions;
* cash and margin;
* Risk Capacity Ledger state;
* protective-order coverage;
* external and unattributed activity;
* recognized non-trade changes;
* current Critical Input Policy, source continuity, required input freshness, Decision Context Capsule invalidation, and common-mode status;
* current writer and Safety Authority epochs;
* trustworthy time;
* valid safety configuration.

---

## 16. Trustworthy Time Architecture

### 16.1 Time Domains

The architecture SHALL distinguish:

* monotonic process time;
* wall-clock time;
* source event time;
* broker or venue time;
* authorization validity time.

### 16.2 Time Confidence

Time-dependent authorization SHALL require valid time confidence.

### 16.3 Clock Failure

Clock rollback, jump, drift, freeze, or disagreement SHALL:

* invalidate affected freshness assumptions;
* invalidate affected expiry assumptions;
* revoke new-risk authority where safety depends on time;
* create evidence and operational alerts.

### 16.4 Event Ordering

Event ordering SHALL NOT rely solely on wall-clock timestamps when monotonic sequence or source sequence is available.

### 16.5 Degraded Protective Lease Time

A degraded protective lease SHALL be issued before partition, bound to an Authority Epoch, limited to a short approved lifetime, and verifiable using local monotonic elapsed time. It SHALL become invalid after process restart unless explicitly re-established and SHALL be invalid whenever remaining validity cannot be positively proven.

Wall-clock deadline comparison alone is insufficient.

---

## 17. Safety Control Plane

The Safety Control Plane SHALL own:

* Hard Safety Envelope;
* Safety Profile validation;
* aggregate risk authority;
* live authorization;
* Safety Authority state;
* protective-action authority;
* production-scope constraints.

It SHALL NOT depend on strategy approval for safety decisions.

### 17.1 Authority Validity

Execution SHALL require current, locally verifiable authority.

Previously valid authority SHALL expire according to approved safety rules.

Normal risk-increasing authority requires online currentness verification. A previously permissive grant SHALL NOT be reused indefinitely.

### 17.2 Partition Behavior

Loss of verifiable control-plane authority SHALL revoke exposure-increasing execution.

Protective behavior under partition SHALL follow ADR-002-001.

No new aggregate capacity may be committed during a Safety Control Plane partition. Only bounded consumption of a pre-committed protective pool under a valid, exclusive protective lease is permitted. The lease SHALL limit account, instrument, action class, maximum quantity, and maximum risk-vector effect and SHALL have one active owner protected from duplicate consumption.

### 17.3 Stale Instance Fencing

Leadership election alone is insufficient. Every state-changing safety domain SHALL use a monotonic fencing mechanism so a stale process resuming after partition, pause, rollback, or failover cannot:

* commit or release capacity;
* issue an accepted Safety Authority grant;
* consume a reassigned protective lease;
* transmit through broker egress.

The final broker-egress gate and every Risk Capacity Ledger mutation SHALL reject stale Authority Epochs and stale writer epochs.

---

## 18. Live and Non-Live Segregation

The architecture SHALL separate live and non-live operation through multiple controls.

Required separation domains include:

* account;
* credentials;
* network route;
* deployment identity;
* runtime authorization;
* broker endpoint;
* configuration;
* evidence classification.

A non-live component SHALL NOT gain live capability solely by changing a runtime flag.

Live authorization SHALL be positively granted and revocable.

---

## 19. Safety Configuration Architecture

### 19.1 Configuration Layers

The architecture SHALL distinguish:

```text
Hard Safety Envelope
        ↓
Approved Safety Profile
        ↓
Live Authorization Scope
        ↓
Per-Intent Safety Decision
```

A lower layer SHALL NOT expand the authority granted by a higher layer.

### 19.2 Atomic Activation

Safety configuration SHALL become active as a complete version.

Partially applied configuration SHALL fail closed.

### 19.3 Semantic Validation

Validation SHALL cover:

* units;
* scale;
* account;
* instrument;
* venue;
* strategy;
* software version;
* compatibility between limits;
* plausibility;
* Hard Safety Envelope compliance.

### 19.4 Runtime Changes

Changes that increase authority SHALL NOT silently take effect during live operation.

---

## 20. Degraded Operation

The minimum operational modes SHALL be:

| Mode                |                   New risk |                             Protective actions | Requirement             |
| ------------------- | -------------------------: | ---------------------------------------------: | ----------------------- |
| NON_LIVE            |                 Prohibited |                                Simulation only | No live authority       |
| LIVE_NORMAL         | Permitted within authority |                                      Permitted | All live gates valid    |
| LIVE_RESTRICTED     |                 Restricted |             Permitted within approved envelope | Partial degradation     |
| DEGRADED_PROTECTIVE |                 Prohibited |                    Limited approved protection | ADR-002-001             |
| CONTAINED           |                 Prohibited |  Cancellation and narrowly bounded containment | Safety Authority action |
| RECOVERY            |                 Prohibited | Reconciliation only unless explicitly approved | State restoration       |
| HALTED              |                 Prohibited |        Human-authorized emergency actions only | Maximum restriction     |

Mode transitions SHALL be explicit, auditable, and safety-authorized.

Restoration of connectivity SHALL NOT automatically transition the system to `LIVE_NORMAL`.

---

## 21. Protective Capacity

Protective capacity SHALL be governed by ADR-002-001.

The architecture SHALL preserve the ability to:

* cancel risk-increasing open orders;
* maintain approved protective orders;
* reduce existing exposure where feasible;
* manage trapped exposure;
* notify and escalate;
* preserve authoritative evidence.

Normal strategies SHALL NOT consume reserved protective capacity.

### 21.1 Guarantee Levels

Every claimed protective resource SHALL be classified as:

```text
PHYSICALLY_RESERVED
LOGICALLY_RESERVED
PRIORITIZED_ONLY
BEST_EFFORT
UNAVAILABLE
```

Priority SHALL NOT be described as reservation. `BEST_EFFORT` is a residual-risk disclosure, not guaranteed protective capacity.

### 21.2 Common-Mode Disclosure

Where a broker exposes only one serialized session, one global account rate limit, or one shared credential path, protective API capacity may be only `PRIORITIZED_ONLY` or `BEST_EFFORT`.

The limitation SHALL be recorded as residual risk and SHALL reduce normal traffic admission, trigger earlier degraded-mode thresholds, restrict maximum live scope, constrain protective assumptions, and affect production acceptance.

### 21.3 Intermediate-State Safety

A protective action is permitted in degraded mode only when conservative analysis proves that every credible partial-fill fraction and execution ordering remains inside the Hard Safety Envelope and does not create a worse aggregate-risk state than taking no action.

If this cannot be proven, the action SHALL be treated as risk increasing.

### 21.4 Protection Replacement Gap

When a broker cannot atomically replace a protective order:

* the position SHALL be treated as unprotected during the replacement gap;
* the gap SHALL be bounded and measured;
* replacement failure SHALL have a defined safe response;
* broker-specific residual risk SHALL be approved;
* capacity calculation SHALL account for the more conservative of order overlap or protection absence.

ADR-002-011 governs every protective-replacement mode and requires dedicated evidence before any broker or order scope may claim safe replacement.

### 21.5 Protective Ownership and Cancellation

Every protective order SHALL carry one ownership classification: `STRATEGY_OWNED`, `EXECUTION_OWNED`, `SAFETY_OWNED`, or `OPERATOR_OWNED`.

A safety-owned protective order SHALL NOT be cancelled by ordinary strategy logic. The Cancellation Arbiter SHALL determine whether cancellation removes required protection, and protective evaluation SHALL precede ordinary cancellation authority.

---

## 22. Evidence and Observability

Every live action SHALL produce evidence for:

* context identity and version;
* decision;
* approval;
* Intent;
* Safety Profile;
* Hard Safety Envelope version;
* risk calculation;
* capacity commitment;
* live authorization;
* Safety Authority state;
* transmitted order;
* acknowledgement;
* fill;
* reconciliation;
* resulting position.

### 22.1 Rejected Actions

Rejected and blocked actions SHALL be recorded with the applicable safety reason.

### 22.2 Safety State Transitions

Every transition into or out of:

* degraded mode;
* contained mode;
* unknown state;
* recovery;
* live operation;

SHALL produce evidence.

---

## 23. Recovery and Re-Arming

### 23.1 Recovery Preconditions

Re-arm SHALL require all of the following:

1. trustworthy time restored;
2. current Safety Authority epoch established;
3. account-wide reconciliation completed;
4. no unresolved UNKNOWN order, unless it remains fully conservatively reserved and is explicitly accepted only for restricted recovery in which new risk remains blocked;
5. no unresolved unattributed external activity;
6. Risk Capacity Ledger consistency verified;
7. Hard Safety Envelope and Runtime Safety Profile versions verified;
8. protective coverage evaluated;
9. Recovery Coordinator readiness decision;
10. new Live Authorization issued;
11. explicit human control according to the approved separation-of-duty policy.

No blocking Critical hazard may remain. The same human or service identity SHALL NOT both enlarge limits and arm live trading.

### 23.2 No Automatic Re-Arming

The system SHALL NOT automatically restore live autonomous authority merely because a failed dependency becomes available.

Recovery readiness is not live authority.

### 23.3 Changed Scope

A change to account, strategy, instrument, broker, venue, software version, or Safety Profile SHALL trigger re-evaluation of live authorization.

---

## 24. Deployment and Isolation Requirements

RFC-002 does not mandate a specific deployment platform.

The deployment SHALL nevertheless demonstrate:

* Safety Control Plane isolation from strategy failure;
* persistence of risk-capacity commitments;
* independent emergency authority;
* live/non-live credential isolation;
* failure visibility;
* recoverable evidence;
* bounded blast radius.

The deployment architecture SHALL document which common-mode failures remain possible.

### 24.1 Failure-Domain Allocation

RFC-002 or a delegated ADR SHALL maintain a Failure-Domain Allocation Matrix covering at least:

* process and runtime;
* pod and node;
* cluster and region;
* datastore;
* Kafka or equivalent event infrastructure;
* Redis or equivalent cache or stream infrastructure;
* network path;
* broker session;
* credential and workload identity;
* deployment pipeline;
* clock source;
* risk-calculation library;
* configuration parser and distribution path.

For each shared dependency, the matrix SHALL identify affected authorities, failure consequence, containment behavior, physical/logical/common-mode classification, residual risk, and verification method.

Logical service separation SHALL NOT be presented as proof of physical failure independence.

ADR-002-009 defines the normative matrix fields, isolation invariants, deployment fencing, Safety Cell blast-radius rules, and acceptance gates.

---

## 25. Security-Relevant Architecture

Security is part of operational safety where unauthorized access can create real-capital actions.

The architecture SHALL provide:

* authenticated component identity;
* least privilege;
* protected live credentials;
* protected safety configuration;
* protected authority messages;
* audit of human actions;
* revocable live authorization;
* separation between configuration authorship and approval.

Detailed security controls MAY be specified in a subordinate RFC.

ADR-002-013 defines the normative Final Egress Trust Boundary, usable live-order authority, credential and broker-order route confinement, quorum-sufficient Commit Proof validation, stale-egress hard fencing, and fail-closed credential rotation and recovery rules.

ADR-002-015 defines the normative effective Human Safety Principal, Human Authority Policy, exact dual-control approval artifacts, one-human restrictive HALT, break-glass confinement, delegation, compromise, and non-revival rules. Human approval remains an input to separately enforced decisions and cannot become configuration, capacity, Live Authorization, protective-classification, or broker-transmission authority.

ADR-002-016 defines the security and custody boundary for immutable safety evidence, durable pre-effect receipts, independent integrity anchors, protected raw records, redaction views, replay isolation, evidence administration, and chain of custody. Evidence and replay principals SHALL NOT possess live broker authority or production mutation paths.

ADR-002-018 defines source identity and continuity, transformation-lineage, independent-input common-mode, immutable context binding, correction/invalidation, stale-publisher, Capsule-substitution, and active final-egress currentness threats. Context, data, evidence, operator, and replay principals SHALL NOT obtain approval, capacity, Live Authorization, protective-classification, or broker-transmission authority through input processing.

ADR-002-019 defines Venue Constraint Policy integrity, exact order-admissibility binding, Constraint Generation fencing, session/halt/account/margin/broker-rule invalidation, and active final-egress constraint-currentness threats. The Venue Constraint Gate and its read identities SHALL NOT obtain capacity, approval, protective-classification, Live Authorization, broker-transmission, HALT-clear, or re-arm authority.

---

## 26. Architectural Decision Records

The following ADRs are initially required.

| ADR         | Subject                                                               | Status   |
| ----------- | --------------------------------------------------------------------- | -------- |
| ADR-002-001 | Degraded-Mode Protective Capacity                                     | Proposed |
| ADR-002-002 | Aggregate Risk-Capacity Commitment Model                              | Proposed |
| ADR-002-003 | Safety Authority Validity, Epoch Fencing, and Partition Behavior      | Proposed |
| ADR-002-004 | Broker Capability Requirements and Fallbacks                          | Proposed |
| ADR-002-005 | Intent, Transmission Attempt, Broker Order, and Knowledge State Model | Proposed |
| ADR-002-006 | Evidence and Reconciliation Confidence Model                          | Proposed |
| ADR-002-007 | Live Authorization, Limit Governance, and Re-arm                      | Proposed |
| ADR-002-008 | Trustworthy Time Architecture                                         | Proposed |
| ADR-002-009 | Failure-Domain Isolation and Deployment Safety                        | Proposed |
| ADR-002-010 | Corporate Actions and Non-Trade State Changes                         | Proposed |
| ADR-002-011 | Protective Replacement and Protection-Gap Control                     | Proposed |
| ADR-002-012 | Risk Capacity Ledger Persistence, Consensus, and Writer Fencing        | Proposed |
| ADR-002-013 | Egress Gateway Credential, Route, and Commit-Proof Security             | Proposed |
| ADR-002-014 | Hard Safety Envelope and Runtime Safety Profile Governance               | Proposed |
| ADR-002-015 | Human Safety Authority, Dual Control, and Break-Glass Governance          | Proposed |
| ADR-002-016 | Safety Evidence, Audit, and Deterministic Replay Integrity                 | Proposed |
| ADR-002-017 | Safe Startup, Recovery Barrier, and Conservative Resume Coordination       | Proposed |
| ADR-002-018 | Critical Input Integrity, Provenance, and Decision-Context Fencing          | Proposed |
| ADR-002-019 | Venue, Session, Tradability, and Broker Constraint Gate                     | Proposed |

ADR-002-002 through ADR-002-019 are authored as co-located `Proposed` decisions. The Phase B design order ADR-002-009 → ADR-002-011 → ADR-002-010 and the follow-on RCL consensus, final-egress security, safety-configuration governance, human-authority governance, evidence-integrity, safe-start/recovery-barrier, Critical Input/decision-context, and venue/session/tradability decisions ADR-002-012 → ADR-002-013 → ADR-002-014 → ADR-002-015 → ADR-002-016 → ADR-002-017 → ADR-002-018 → ADR-002-019 are complete at authorship level only. VER-002-001 and the Evidence Register now cover ADR-002-001 through ADR-002-019, including one-to-one dedicated cases for ADR-002-005 through ADR-002-019. All 231 registered evidence items remain `NOT_IMPLEMENTED`; registration is not execution and does not change ADR or live-readiness status.

---

## 27. Requirements Traceability Matrix

| RFC-001 requirement | Architectural responsibility                            |
| ------------------- | ------------------------------------------------------- |
| SAFE-001            | Safety Authority, Protective Action Controller          |
| SAFE-002            | Protective Action Controller, Position Projection, Cancellation Arbiter |
| SAFE-003            | Safety Profile Validator                                |
| SAFE-004            | Hard Safety Envelope Registry                           |
| SAFE-010            | Aggregate Risk Authority, Risk Capacity Ledger, Broker Egress Gateway |
| SAFE-011            | Safety Control Plane                                    |
| SAFE-012            | Aggregate Risk Authority                                |
| SAFE-013            | Aggregate Risk Authority, Risk Capacity Ledger          |
| SAFE-014            | Execution Coordinator                                   |
| SAFE-015            | Risk Capacity Ledger                                    |
| SAFE-020            | Intent Registry                                         |
| SAFE-021            | Execution Coordinator, Intent Registry, Risk Capacity Ledger, Broker Egress Gateway |
| SAFE-022            | Reconciliation Service                                  |
| SAFE-023            | Reconciliation Service                                  |
| SAFE-024            | Reconciliation Service                                  |
| SAFE-025            | Position and Order Projection                           |
| SAFE-030            | Context Integrity Service, Decision Context Capsule     |
| SAFE-031            | Context Integrity Service, Critical Input Policy, Evidence Store |
| SAFE-032            | Venue Constraint Gate, Context Integrity Service, Broker Egress Gateway |
| SAFE-033            | Decision Context Capsule, Order Admissibility Decision, Independent Approval Service, Execution Coordinator, Broker Egress Gateway |
| SAFE-034            | Independent Approval Service, Critical Input common-mode analysis, Human Authority Governance |
| SAFE-035            | Trustworthy Time Service                                |
| SAFE-040            | Protective Action Controller, Cancellation Arbiter, Broker Egress Gateway |
| SAFE-041            | Safety Authority, Human Authority Governance            |
| SAFE-042            | Operator Control Interface, Human Safety Principals, Broker Egress Gateway |
| SAFE-043            | Protective Action Controller                            |
| SAFE-044            | Recovery Coordinator, Safety Control Plane, Broker Egress Gateway |
| SAFE-045            | Deployment and Identity Architecture                    |
| SAFE-046            | Live Authorization Service, Human Authority Governance  |
| SAFE-047            | Live Authorization Service                              |
| SAFE-048            | Safety Authority, Risk Capacity Ledger, Broker Egress Gateway |
| SAFE-050            | Hard Safety Envelope Registry, Safety Profile Validator, Human Authority Policy |
| SAFE-051            | Evidence Store, source decision owners, Broker Egress Gateway |
| SAFE-052            | Replay and Evidence Service, Evidence Store             |

This matrix is an initial allocation and SHALL be refined as ADRs are accepted.

---

## 28. Open Architectural Decisions

ADR-002-005 through ADR-002-019 now define the normative orthogonal-state, evidence-confidence, trustworthy-time, re-arm, failure-domain, protective-replacement, non-trade-event, RCL consensus, final-egress security, safety-configuration governance, human-authority governance, evidence-integrity/replay, safe-start/recovery-barrier, Critical Input/decision-context, and venue/session/tradability-constraint models. Their listed implementation and acceptance questions remain open while those ADRs are `Proposed`. The following architecture and implementation choices SHALL be resolved by the assigned ADR, implementation specification, Verification Profile, Critical Input Policy, Venue Constraint Policy, Recovery Barrier Policy, Evidence Integrity Policy, or Broker Capability Profile.

1. Which conforming replicated-state-machine product, storage engine, voter topology, and durability configuration implement ADR-002-012's selected quorum Safety Commit Log mechanism?
2. Which conforming non-exportable signer or credential service, identity-aware order route, Quorum Commit Certificate format, Active Egress Principal topology, and Hard Egress Fence implement ADR-002-013 while carrying ADR-002-007 and ADR-002-012 generations to the broker-send boundary?
3. Which canonical artifact, semantic-normalization, approval, registry, signing, compatibility-manifest, and activation mechanisms implement ADR-002-014 without collapsing configuration governance, capacity, and live-arming authority?
4. Which human identity, phishing-resistant authentication, Effective Principal Graph, approval workflow, quorum, delegation, emergency authenticator, and restrictive egress-latch mechanisms implement ADR-002-015?
5. Which append-only store, source identity, durable acknowledgement, emergency journal, integrity anchor, gap detector, protected raw tier, retention policy, and isolated replay mechanisms implement ADR-002-016?
6. Which Recovery Barrier Policy, ordered Recovery Generation and owner fence, dependency graph, broker/source Inventory Cut protocol, obligation workflow, package signer, and final-egress currentness mechanism implement ADR-002-017?
7. Which Critical Input Policy, source registry/continuity protocol, schema and unit/mapping registry, transformation manifest, consistency-cut rule, independent approval path, Context Generation, invalidation graph, and active final-egress currentness mechanism implement ADR-002-018?
8. Which Venue Constraint Policy, source/continuity registry, Session Phase and tradability state machines, order/account/margin/borrow/settlement rules, exact Snapshot/Decision schemas, Constraint Generation, invalidation graph, and active final-egress currentness mechanism implement ADR-002-019?
9. What deployment topology provides the required failure-domain isolation?
10. What numeric detection, containment, protective-gap, lease, retry, evidence-persistence, evidence-gap, recovery-barrier, Critical Input invalidation, venue-constraint invalidation, context/decision-age, readiness-age, retention, and replay bounds are approved?
11. What evidence establishes broker-specific Final Quantity Proof and external-activity detection bounds?
12. Which broker resources can be physically or logically reserved for protection?
13. How are corporate actions and other non-trade changes attributed and remapped?
14. What restricted-production evidence is required beyond non-live verification?

Open decisions SHALL NOT be resolved by informal implementation convention.

---

## 29. Verification Obligations

Each Critical architecture property SHALL identify:

* triggering condition;
* detection bound;
* containment bound;
* responsible component;
* observable evidence;
* forbidden outcome;
* pass/fail criterion;
* fault-injection or replay scenario.

At minimum, the verification set SHALL include:

* concurrent authorization and duplicate active committer;
* quorum loss, minority leader survival, membership change, committed-prefix rollback, and conflicting restore history;
* direct credential/route bypass, stale egress resume, proof substitution, downstream replay, credential rotation overlap, and hard-fence failure;
* stale capacity writer and stale Safety Authority;
* crash before send and crash after send;
* acknowledgement loss and duplicate message;
* partial fill, cancel crossing fill, replace crossing fill, and late fill;
* process restart with a live or UNKNOWN broker order;
* external HTS order and broker-query omission;
* clock fault and time-source loss during partition;
* invalid Safety Profile, Hard Safety Envelope expansion, semantic/unit ambiguity, partial activation, mixed generation, incompatible consumer, stale-base race, rollback/restore, expiry recovery, and unauthorized expand-and-arm attempt;
* shared-account or same-person dual approval, self-approval chain, stale Approval Set replay, delegation/roster drift, compromised approver, break-glass expansion, Human HALT path failure, and identity-service recovery attempting automatic re-arm;
* missing pre-effect evidence, receipt substitution, evidence-store outage, record omission, duplicate conflict, history truncation or fork, integrity-anchor rollback, schema/canonicalization drift, unsafe redaction, premature deletion, replay divergence, and replay-to-live boundary violation;
* startup, reconnect, failover, restore, or recovery trigger failing to close the barrier before observation; concurrent or stale recovery owners; incomplete dependency scope; non-atomic broker inventory; post-cut invalidation; forced readiness; and partial recovery using unresolved shared resources;
* unclassified safety input, unknown source or continuity, sequence rollback/gap, schema/parser/mapping/unit drift, hidden transformation, incompatible consistency cut, false approval independence, Capsule substitution, correction/retraction propagation failure, permissive context cache, and stale-context final-egress acceptance;
* exceptional session transition, halt/suspension conflict, quote-without-tradability, price/tick/lot/order-shape change, account/margin/borrow/settlement conflict, exact decision substitution, permissive constraint cache, stale Constraint Generation, exit/protective executability assumption, and venue/broker recovery attempting old-decision reuse;
* non-live environment attempting to reach live egress;
* protective reserve exhaustion and ordinary traffic blocking the protective path;
* corporate action or instrument-identity change;
* recovery completion, readiness, health restoration, evidence repair, or replay attempting to reuse prior authority or re-arm automatically.

Numeric values belong in an approved Verification Profile, Safety Profile, or Broker Capability Profile. Written cases do not constitute completed evidence; completion requires actual execution, retained raw artifacts, invariant evaluation, hashes, measured bounds, and independent review as specified by VER-002-001.

---

## 30. Review Gates

RFC-002 SHALL undergo:

1. architecture consistency review;
2. safety traceability review;
3. failure-mode review;
4. concurrency review;
5. broker and venue integration review;
6. trading-operations review;
7. recovery review;
8. security boundary review.

RFC-002 SHALL NOT progress to Release Candidate until:

* every Critical `SAFE-xxx` requirement has an architectural allocation;
* every architecture-shaping Critical finding has an accepted ADR;
* no unresolved safety contradiction remains;
* all trust boundaries are explicit;
* all unknown-state behavior is fail-closed;
* degraded-mode protective capacity is resolved.

---

## 31. Review Finding Disposition

| Finding | Consolidated disposition |
|---|---|
| A-01 split-brain double commitment | §9.1, §10.5, §14, and ADR-002-002 |
| A-02 stale Safety Authority | §16.5, §17.3, and ADR-002-003 |
| A-03 broker idempotency assumption | §13.6 and ADR-002-004 |
| A-04 protective commit contradiction | §9.1, §21, ADR-002-001, and ADR-002-002 |
| A-05 cancel/fill release race | §13.3, §14.4, and ADR-002-002 |
| A-06 undefined components | §10.18 through §10.22 |
| A-07 execution-side partition time | §16.5 and ADR-002-008 |
| A-08 soft protective reserve | §21.1–§21.2 and ADR-002-001 |
| A-09 protection replacement gap | §21.4 and ADR-002-011 |
| A-10 corporate actions | §14.7 and ADR-002-010 |
| A-11 external detection latency | §15.3 and ADR-002-004/006 |
| A-12 unquantified containment | §29 and VER-002-001 |
| A-13 split cancellation authority | §9.1, §10.22, and §21.5 |
| A-14 minor over-specification | §20 mode table retained; detailed governance remains delegated |


## 32. Review History

### v0.1 — Architecture Scaffold

* Defined architectural scope and authority.
* Defined Safety Control Plane and Trading Data Plane.
* Defined core components and trust boundaries.
* Added failure model.
* Added Intent and order lifecycle.
* Added aggregate risk-capacity architecture.
* Added evidence-based reconciliation.
* Added Trustworthy Time architecture.
* Added degraded operation modes.
* Added initial RFC-001 traceability allocation.
* Added required ADR register.
* Referenced ADR-002-001 for degraded-mode protective capacity.

### v0.2 — Architecture Review Corrections

* Added the Authority Ownership Matrix as the normative authority model.
* Separated commit versus consume terminology: the Aggregate Risk Authority grants or denies aggregate risk allocation while the Risk Capacity Ledger is the sole serialization and state-transition authority for capacity commitments.
* Established the Broker Adapter / broker-egress gateway as the final live-transmission enforcement point.
* Defined the Safety Profile Validator and Recovery Coordinator components and the Deployment/Identity and Replay/Evidence responsibility sets.
* Required orthogonal state modeling (Intent, Transmission Attempt, Broker Order, Knowledge/Evidence, Capacity).
* Added capacity and release invariants (aggregate envelope, commitment mapping, no expiry of economic effect, cancellation release, replace, external/non-trade changes).
* Added the Broker Capability Contract dependency and capability classification.
* Added partition, trustworthy-time, and protective-capacity clarifications.
* Added reconciliation and evidence amendments (no single unconditional truth, per-field confidence, external-activity detection bound, startup/recovery barrier).
* Added re-arm governance prohibiting automatic re-arm.
* Added the Failure-Domain Allocation requirement.
* Added verification and acceptance-bound requirements.
* Expanded the ADR register through ADR-002-019 and registered ADR-002-002 through ADR-002-019 as Proposed.
* Added the Phase B failure-domain isolation, protective-replacement, and corporate-action/non-trade decisions without changing verification or live-readiness status.
* Selected the quorum-replicated deterministic Safety Commit Log mechanism class for RCL persistence, consensus, writer fencing, currentness ordering, and recovery in ADR-002-012; concrete products and deployment values remain open.
* Defined the effective Final Egress Trust Boundary, credential and route confinement, quorum-sufficient Commit Proof validation, and stale-egress hard fencing in ADR-002-013.
* Defined immutable Hard Safety Envelope and Runtime Safety Profile artifacts, separated governance, canonical semantic validation, committed Profile Generations, break-before-make activation, restrictive precedence, and rollback non-revival in ADR-002-014.
* Defined effective Human Safety Principal identity, exact dual-control approval artifacts, one-human restrictive HALT, break-glass confinement, delegation, compromise, and approval non-revival in ADR-002-015.
* Defined immutable safety evidence, pre-effect durability, integrity anchoring, gap containment, protected retention, isolated deterministic replay, and evidence non-authority in ADR-002-016.
* Defined closed safe startup, monotonic Recovery Generations, fenced recovery ownership, conservative account-wide inventory, dependency-complete obligations, non-authorizing readiness, partial-scope isolation, and fresh governed re-arm handoff in ADR-002-017.
* Defined Critical Input classification, source identity and continuity, exact provenance and transformation lineage, immutable Snapshots and Decision Context Capsules, independent approval common-mode analysis, correction/invalidation fan-out, active final-egress currentness, and data-recovery non-revival in ADR-002-018.
* Defined exact venue/session/tradability, instrument/order/account/margin/borrow/settlement, Broker Capability Profile, Order Admissibility Decision, Constraint Generation, protective-path, final-egress currentness, and non-revival rules in ADR-002-019.
* Expanded VER-002-001 and the Evidence Register to 231 `NOT_IMPLEMENTED` items with one-to-one acceptance-case coverage for ADR-002-005 through ADR-002-019.
* Resolves review findings A-01 through A-14.
