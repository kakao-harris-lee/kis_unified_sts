# RFC-002 — Trading Operating System Architecture

**Document ID:** RFC-002
**Title:** Trading Operating System Architecture
**Version:** 0.6 Review Draft
**Status:** Review Draft — Architecture
**Classification:** Foundational Architecture Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Safety Authority:** Constrained by RFC-001 — Safety Case
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-13
**Last Updated:** 2026-07-18

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
* safety telemetry, continuous conformance monitoring, and alert escalation;
* production recovery and re-arming;
* safety deviations, exceptions, and residual-risk governance.

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

ADR-002-021 defines the exact Aggregate Risk Policy, Aggregate Risk State Snapshot, Adverse Scenario Set, projected vectors, currentness, invalidation, and RCL-binding semantics. A `GRANT` authorizes only the exact allocation request presented to the RCL; it is not a Capacity Commitment or broker permission.

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

#### 3.1.10 Action Flow Permit

An immutable, exact, single-use Risk Capacity Ledger commitment record for one broker-directed action-flow vector, action identity, cause lineage, scope, and generation.

An Action Flow Permit is a required capacity precondition, not Live Authorization, a Transmission Capability, protective classification, or broker permission. Only the Risk Capacity Ledger may create, consume, quarantine, or release it under ADR-002-022.

#### 3.1.11 Safety Deviation Decision

An immutable, exact, time-bounded, independently reviewed, non-authorizing decision that may make one RFC-001-permitted residual risk eligible to request one restricted Safety Configuration Bundle.

A Safety Deviation Decision does not satisfy the affected requirement, mark evidence `PASS`, activate configuration, mutate capacity, issue Live Authorization, permit transmission, clear HALT, or re-arm. ADR-002-026 defines the Non-Waivable Boundary, exact scope, compensating controls, Deviation Generation, currentness, expiry, and evidence-honesty rules.

#### 3.1.12 Safety Incident Declaration

A monotonic restrictive declaration that a policy-classified safety signal may affect one exact dependency-complete scope under one current Incident Generation.

The declaration and its Incident Record, Active Safety Incident Set, containment plan, recovery handoff, evidence, and closure artifacts are non-authorizing. They do not mutate or release capacity, classify protection, issue authority, transmit, clear HALT, establish recovery readiness, restore scope, or re-arm. ADR-002-027 defines incident scope, controlled shutdown, closure, currentness, and non-revival semantics.

#### 3.1.13 Monitoring Gap

An immutable non-authorizing record that required safety telemetry or monitor coverage is missing, stale, conflicting, ambiguous, discontinuous, incomplete, unverified, common-mode-invalid, suppressed, overflowed, or otherwise unable to demonstrate its declared contract.

A Monitoring Gap restricts the greatest credible dependent scope and creates no permission, capacity transition, broker finality, incident closure, recovery readiness, scope restoration, or re-arm. ADR-002-028 defines telemetry, coverage, continuous-conformance, suppression, alert, escalation, currentness, and non-revival semantics.

#### 3.1.14 Artifact Admission Decision

An immutable, exact-scope, policy- and content-bound `ADMIT`, `DENY`, or `UNKNOWN` evaluation of one complete source, build, dependency/toolchain, release-artifact, compatibility, deployment, and runtime-attestation lineage under one Release Generation.

`ADMIT` is a non-authorizing negative gate. It does not deploy, activate configuration, mutate or release capacity, classify protection, issue Safety Authority, Live Authorization, or Transmission Capability, transmit, clear restrictive state, establish readiness, promote production scope, or re-arm. ADR-002-029 defines release admission, fencing, runtime attestation, currentness, and non-revival semantics.

#### 3.1.15 Economic Obligation Record

An immutable exact-scope version of one possible or confirmed post-trade economic leg, including its cause, account and legal entity, asset or currency, direction, quantity or amount, units, timing, source provenance, lifecycle, field-specific finality, dependency closure, correction lineage, and conservative capacity binding.

An Economic Obligation Record is not external truth, settled cash, legal title, capacity, Live Authorization, or transmission permission. Missing, stale, conflicting, incomplete, common-mode, corrected, or unverifiable obligation state remains UNKNOWN and capacity-consuming under ADR-002-030.

#### 3.1.16 Post-Trade Finality Proof

An immutable non-authorizing proof that one exact field of one exact Economic Obligation Record reached its policy-defined finality state under the current Post-Trade Obligation Generation and complete evidence recipe.

Finality is field- and class-specific. Execution finality, Final Quantity Proof, trade capture, instruction acceptance, settlement completion, cash availability, collateral eligibility, custody or legal title, fee or tax finality, borrow discharge, and corporate-action completion SHALL NOT substitute for one another. Proof expiry or invalidation restricts future reliance but does not expire economic effect or release capacity.

#### 3.1.17 Credible State Space

The bounded set of behaviours a universally-quantified safety claim ("every credible …", "worst credible …") ranges over. The Credible State Space for a given evaluation is the union of (a) the behaviour/interpretation set admitted by the active **Broker Capability Profile** (ADR-002-004) — supported broker interpretation, partial-execution, ordering, rounding, overlap, and reversal semantics — and (b) the approved **Adverse Scenario Set** (ADR-002-021). A behaviour outside this bounded set is either excluded by the active profile or, if unbounded or unknown, forces the conservative UNKNOWN treatment — it does not silently drop out. "Credible" is never the proposer's or an operator's judgement; it is fixed by these two governing artifacts. This is the set the ADR-002-011/012/020/021 "credible"/"worst credible" universals range over, and it is the coverage target for the VER-002-001 §2.7 coverage argument.

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

Safety-incident investigation, ticketing, notification, and root-cause analysis SHALL NOT delay a required restrictive fence or substitute for containment. Failure or delay of the incident-management plane grants no continuing permission.

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
| Bounded human authority        | SAFE-042, SAFE-046, SAFE-050, SAFE-053 |
| Final-egress out-of-band containment | SAFE-054                         |

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

An unavailable, stale, or compromised incident-management service SHALL NOT preserve permissive authority. Material signals and unknown incident scope require conservative restriction through independently available owners.

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
| Approve proposal | Independent Approval Service | Intent Registry atomically consumes one exact current decision into one immutable Intent | Approval Service SHALL NOT create Intent state, commit capacity, issue authority, or transmit |
| Construct canonical broker command | Order Construction Policy governance supplies rules | Order Construction Service produces a non-authorizing candidate and later conformance proof; Broker Egress Gateway verifies the actual outbound representation | Order Construction Service SHALL NOT approve, mutate capacity, classify protection, issue authority, transmit, or arm live scope |
| Evaluate venue and order admissibility | Venue Constraint Policy governance supplies rules | Venue Constraint Gate produces a non-authorizing decision; Broker Egress Gateway enforces the exact current result | Venue Constraint Gate SHALL NOT approve, commit capacity, classify protection, transmit, or arm live scope |
| Evaluate aggregate risk | Aggregate Risk Policy governance supplies rules; Aggregate Risk Authority grants or denies an exact allocation request | RCL admits and serializes only the exact current decision; final egress fences its current binding | Aggregate Risk Authority SHALL NOT mutate capacity, issue live authority, or transmit |
| Evaluate broker-directed action flow | Action Flow Policy governance supplies rules; Action Flow Governor grants or denies an exact allocation request | RCL serializes and mutates action-flow capacity; final egress requires and triggers the exact current RCL-owned single-use claim | Action Flow Governor and local limiters SHALL NOT mutate distributed capacity, classify protection, issue authority, or transmit |
| Commit normal risk capacity | Aggregate Risk Authority supplies a grant decision | Risk Capacity Ledger is the sole serialization and mutation authority | Execution Coordinator SHALL NOT mutate capacity |
| Commit or consume action-flow capacity | Exact current Action Flow Decision supplies an allocation request | Risk Capacity Ledger is the sole serialization and mutation authority | Scheduler priority and producer-local counters SHALL NOT create headroom or reserve |
| Pre-commit protective pool | Aggregate Risk Authority supplies a grant decision | Risk Capacity Ledger commits the pool | Protective Action Controller SHALL NOT enlarge the pool |
| Consume protective reserve | Protective Action Controller classifies and requests consumption within a valid lease | Protective sub-ledger or Risk Capacity Ledger transition function defined by ADR-002-002 | Strategy SHALL NOT self-label an action as protective |
| Issue Safety Authority | Safety Authority | Final broker egress validates current epoch and scope | Safety Authority SHALL NOT hold broker transmission credentials |
| Arm live scope | Live Authorization Service | Final broker egress validates scope | Limit administrator SHALL NOT also arm live scope |
| Change Runtime Safety Profile | Safety Profile governance authority; an authority-increasing profile change requires two independent effective principals per RFC-001 SAFE-053 (quorum or ADR-002-015 §17.1 variant) | Safety Profile Validator activates only after validation | Live armer SHALL NOT change limits |
| Change Hard Safety Envelope | Independent Hard Safety Envelope governance; an envelope-expanding change requires two independent effective principals per RFC-001 SAFE-053 (quorum or ADR-002-015 §17.1 variant) | Hard Safety Envelope Registry publishes an immutable version | Runtime trading identity SHALL NOT administer the envelope |
| Create transmission attempt | Execution Coordinator | Intent Registry and Risk Capacity Ledger bind the attempt before send | Broker Adapter SHALL NOT invent an unbound attempt |
| Transmit | Execution Coordinator requests | Broker Adapter / Broker Egress Gateway is the final enforcement point | No valid Transmission Capability means no send |
| Establish per-send active currentness | Underlying owners publish exact facts; Currentness Sequencer orders them | Currentness Ordering Domain creates a non-authorizing proof within the capability-claim transaction; final egress enforces it | Currentness components SHALL NOT invent facts, mutate capacity, issue business authority, or transmit |
| Govern restricted-live trial and production-scope promotion | Independent safety and broker reviewers evaluate exact pre-registered evidence; Human Authority approves eligibility (two independent effective principals per RFC-001 SAFE-053 — quorum or ADR-002-015 §17.1 variant; see §20.1, §23.1) | Configuration governance activates a new scope and Live Authorization Service issues fresh authority only through existing gates | Trial plans, evidence packages, promotion decisions, dashboards, and monitors SHALL NOT create capacity, activate production, transmit, or re-arm |
| Evaluate safety deviation and residual risk | Safety Deviation Policy governance supplies the Non-Waivable Boundary; independent effective-person quorum evaluates exact reduced scope | Configuration governance may consume one eligible decision into one new restricted Safety Configuration Bundle; all ordinary gates remain | Request, decision, residual-risk record, ticket, evidence, and monitor SHALL NOT mark a requirement PASS, mutate capacity, activate configuration, issue live authority, transmit, or re-arm |
| Declare and coordinate safety incident | Safety Incident Policy governance supplies signal, severity, scope, containment, shutdown, handoff, and closure rules; the incident coordinator produces non-authorizing artifacts | Safety Authority, Human HALT, ADR-002-024 Restrictive Fence Record, RCL, Protective Action Controller, Cancellation Arbiter, Recovery Coordinator, and final egress retain their existing enforcement ownership | Incident records, plans, messages, evidence, handoffs, and closure decisions SHALL NOT mutate or release capacity, classify protection, issue live authority, transmit, clear HALT, establish readiness, restore scope, or re-arm |
| Evaluate safety telemetry and continuous conformance | Safety Monitoring Policy governance supplies exact telemetry, coverage, evaluator, suppression, and alert rules; source owners publish facts | Safety Monitoring Service produces non-authorizing snapshots, gaps, alerts, and restrictive requests; ADR-002-024/027 and existing owners enforce restriction and incident lifecycle | Monitoring, alert, paging, dashboard, and escalation artifacts SHALL NOT mark a requirement PASS, mutate or release capacity, classify protection, issue live authority, transmit, clear safety state, close an incident, restore scope, or re-arm |
| Evaluate and admit safety-critical software artifacts | Software Release Policy governance supplies exact source, build, dependency/toolchain, compatibility, admission, and revocation rules | Artifact Admission Service produces non-authorizing decisions; Release Registry orders one Release Generation and Admitted Release Set; configuration, deployment, currentness, and final egress enforce exact admitted runtime identity | Repository, builder, signer, registry, scanner, admission, deployment, and attestation identities SHALL NOT activate configuration, mutate or release capacity, classify protection, issue live authority, transmit, clear safety state, restore scope, or re-arm |
| Serialize post-trade economic obligations and finality | Post-Trade Finality Policy governance supplies exact leg, source, statement, finality, break, correction, and dependency rules | Post-Trade Obligation Ledger serializes obligation lifecycle and generation; RCL alone performs evidence-bound capacity transitions; final egress enforces any external economic instruction | PTOL, reconciliation, statements, proofs, operators, evidence, and recovery SHALL NOT mutate capacity, issue live authority, transmit, expire economic effect, or re-arm |
| Retry | Execution Coordinator under Broker Capability Profile rules | Broker egress enforces attempt identity and reservation | UNKNOWN outcome SHALL NOT cause blind resubmission |
| Cancel ordinary order | Execution Coordinator requests | Cancellation Arbiter authorizes; broker egress sends | Ordinary cancellation SHALL NOT remove required protection |
| Cancel protective order | Protective Action Controller requests | Cancellation Arbiter authorizes; broker egress sends | Strategy SHALL NOT directly cancel safety-owned protection |
| Classify protective action | Protective Action Controller | Aggregate-risk proof and protective rules enforce classification | Decision Service SHALL NOT classify its own action as protective |
| Halt | Safety Authority or authenticated emergency operator | Broker-egress deny gate applies monotonically | Halt SHALL NOT depend on proposer availability |
| Re-arm | Recovery Coordinator verifies prerequisites; Live Authorization Service issues new authority; explicit human control approves (two independent effective principals per RFC-001 SAFE-053 — quorum or ADR-002-015 §17.1 variant; see §20.1, §23.1) | Broker egress accepts only the new epoch and scope | Automatic re-arm is prohibited |
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

* validate one exact immutable proposal against the current Trading Approval Policy;
* independently verify safety-critical proposal fields and common-mode dependencies;
* validate account, instrument, direction, quantity, unit, and price constraints;
* reject or return `UNKNOWN` for a proposal that is incomplete, stale, conflicting, unsupported, unverifiable, or does not conform to trusted context.

Approval SHALL NOT imply final execution authority.

ADR-002-023 defines the normative Trading Approval Policy and Generation, complete immutable Proposal Approval Request, independent recomputation and common-mode analysis, deterministic `APPROVE`/`DENY`/`UNKNOWN` decision, single-use Intent Registry consumption, dependency-complete invalidation, and active final-egress approval currentness. `APPROVE` is eligible only for one exact Intent registration and creates no capacity, protective classification, Live Authorization, Transmission Capability, broker permission, or re-arm authority.

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

ADR-002-021 defines the normative aggregate-state consistency cut, risk-vector and scope semantics, adverse-scenario coverage, netting/hedge recognition, numerical safety, independent verification, Aggregate Risk Generation fencing, and active RCL/final-egress currentness. UNKNOWN or incomplete aggregate state is restrictive and cannot create headroom.

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

* accept only immutable Intent proposals with a closed proposed Authorized Construction Envelope for non-authorizing candidate construction, and only identically approved/registered Intents for later proof and transmission;
* verify current Safety Authority;
* verify live authorization;
* invoke the non-authorizing Order Construction Service and preserve the exact candidate command digest;
* require current venue admissibility, conservative economic-effect coverage, and capacity commitment before requesting authority or transmission;
* invoke the non-authorizing Action Flow Governor and request only exact RCL-serialized action-flow capacity;
* preserve at-most-authorized exposure effect;
* maintain potentially live order state;
* coordinate retries and recovery.

The Execution Coordinator SHALL NOT infer that a missing acknowledgement means rejection.

The Execution Coordinator SHALL NOT invent, default, normalize, round, or repair broker-command fields. ADR-002-020 defines the deterministic construction protocol and exact ordering of candidate command, venue decision, capacity commitment, conformance proof, authority, and final-egress verification.

---

### 10.8 Broker Adapter / Broker Egress Gateway

Responsibilities:

* serialize and sign only approved canonical execution commands under the declared outbound-comparison rule;
* transmit orders;
* receive acknowledgements and fills;
* query order, position, balance, and margin state;
* preserve broker identifiers and timestamps;
* expose broker evidence without declaring it authoritative.

Broker-specific behavior SHALL remain isolated behind the Broker Adapter boundary.

Before any risk-relevant or broker-resource-consuming transmission, it SHALL verify:

- valid and unused Transmission Capability;
- matching intent and reservation identities;
- current commitment epoch;
- current Safety Authority epoch or valid degraded protective lease;
- valid live scope;
- allowed account, instrument, action class, and maximum quantity;
- applicable Hard Safety Envelope and Runtime Safety Profile versions;
- exact current Safety Deviation Policy, Deviation Generation, canonical Active Deviation Set, reduced configuration scope, and absence of applicable invalidation;
- exact current Safety Incident Policy, Incident Generation, canonical Active Safety Incident Set, affected-scope result, and absence of an applicable suspected or open restriction;
- exact current Safety Monitoring Policy, Monitor Generation, Critical Telemetry and Monitor Coverage Manifest digests, action-scope coverage completeness, absence of applicable unresolved Monitoring Gaps, and required restrictive disposition;
- exact current Venue Constraint Snapshot and Order Admissibility Decision binding;
- current venue, session, halt, tradability, account, margin, settlement, and broker-constraint generation;
- current Order Construction Policy, Construction Generation, Authorized Construction Envelope, Canonical Broker Command, Order Conformance Proof, and Economic Effect Envelope;
- exact current Trading Approval Policy, Trading Approval Generation, Proposal Approval Request, Independent Approval Decision, single-use Approval Consumption Record, and immutable Intent binding;
- exact current Action Flow Policy, Action Flow Generation, Action Flow Decision, RCL action-flow commitment, and unused single-use Action Flow Permit;
- exact current Currentness Policy, complete Safety Currentness Vector, applicable Restrictive Fence Records, positively established Local Restrictive Latch state `CLEAR`, and one new single-use Egress Currentness Proof ordered with the capability claim and `SEND_STARTED`;
- conformance of the actual outbound representation to the exact command and authorized economic effect.

It SHALL reject the request when any required fact is missing, stale, conflicting, or unverifiable.

The Broker Adapter / Broker Egress Gateway is the final live-transmission enforcement point. It SHALL NOT expose a general-purpose live-order method to strategy, research, simulation, backtest, or operator-interface components.

No broker integration may be approved for live use without a versioned, evidence-backed Broker Capability Profile covering the supported broker, API, account, market, order type, and session scope. Missing, contradictory, or insufficient capability evidence SHALL reduce or prohibit live scope; it SHALL NOT weaken a safety requirement.

Because this gateway is the final live-transmission enforcement point, a defect or compromise of the gateway itself SHALL be assumed possible. A containment path independent of the gateway — one that can, without that gateway's own cooperation, terminate its ability to transmit real-capital orders (for example, revocation of the live-order credential, deactivation of the account's order-entry capability, or network- or session-level isolation of the enforcement point) — SHALL be defined and evidenced for the operating environment in capability-neutral terms. Where no such out-of-band containment capability exists, the residual risk SHALL be explicitly recorded and accepted and the affected live scope reduced accordingly (RFC-001 SAFE-054).

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

The Safety Profile Validator SHALL be independent from strategy configuration and SHALL NOT expand the Hard Safety Envelope. The identity permitted to approve or publish a Runtime Safety Profile SHALL NOT also arm live trading, except through the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1) satisfying RFC-001 SAFE-053, whose compensating controls substitute for the second effective principal and whose scope remains bound to the variant's pre-declared smallest approved scope delta.

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

### 10.24 Order Construction Service

Responsibilities:

* compile one immutable approval-pending Intent proposal and closed proposed Authorized Construction Envelope into one deterministic non-authorizing candidate Canonical Broker Command;
* make account, instrument, contract, route, direction, position effect, quantity, unit, multiplier, currency, price, order, expiration, and operating-mode semantics explicit;
* reject hidden defaults, unsupported fields, ambiguous canonicalization, lossy numeric conversion, permissive rounding, and non-deterministic mappings;
* derive a conservative Economic Effect Envelope from the unchanged candidate command;
* produce a non-authorizing Order Conformance Proof after exact venue admissibility and RCL capacity dominance are established;
* expose complete construction, mapping, compiler, serializer, SDK, and invalidation evidence to final egress and the Evidence Store.

The Order Construction Service SHALL NOT approve or widen an Intent, mutate or release RCL capacity, classify protection, issue Safety Authority or Live Authorization, create or consume a Transmission Capability, select a permissive venue decision, transmit, clear HALT, or re-arm. Candidate construction precedes venue, independent approval, and capacity decisions; the later proof binds those independently owned results to the unchanged command digest. Any approval-time mutation restarts construction. ADR-002-020 defines the exact protocol and acceptance gates.

---

### 10.25 Action Flow Governor

Responsibilities:

* evaluate every broker-directed submit, cancel, amend, replace, retry, query, reconnect, session, and administrative operation against one current Action Flow Policy;
* bind the exact action, cause lineage, action class, shared scopes, amplification envelope, broker resource vector, and Protective Flow Reserve requirements;
* produce immutable non-authorizing Action Flow State Snapshots and Action Flow Decisions;
* signal material invalidation, exhaustion, counter conflict, amplification breach, and reserve intrusion to the RCL, authority issuers, final egress, and containment path;
* preserve complete distributed scope and conservative UNKNOWN behavior.

The Action Flow Governor SHALL NOT mutate or refill capacity, create an Action Flow Permit, classify an action as protective, issue Safety Authority or Live Authorization, create or consume a Transmission Capability, hold a usable broker credential or route, transmit, clear HALT, or re-arm. A `GRANT` authorizes only the exact allocation request presented to the RCL. ADR-002-022 defines the exact protocol and acceptance gates.

---

### 10.26 Currentness Sequencer and Final-Egress Admission

Responsibilities:

* validate owner-issued currentness and restrictive facts without inventing their business result;
* order the complete action-scoped Safety Currentness Vector, restrictive generation floors, capability claim, and `SEND_STARTED` in the applicable Currentness Ordering Domain;
* allow an independently available restrictive ingress and monotonic local egress deny latch;
* create one non-authorizing, exact, single-use Egress Currentness Proof for each normal send;
* reject missing, stale, conflicting, mixed, unordered, wrong-scope, or unverifiable currentness;
* preserve conservative economic state across invalidation, ambiguity, partition, and recovery.

The Currentness Sequencer SHALL NOT approve an Intent, decide an underlying policy result, mutate or release capacity, classify protection, issue Live Authorization, manufacture a Transmission Capability, transmit, clear HALT, or re-arm. The Broker Egress Gateway remains the final transmission enforcement point and the RCL remains the sole capacity mutation/serialization authority. ADR-002-024 defines the exact protocol and acceptance gates.

---

### 10.27 Restricted-Live Trial and Production-Promotion Governance

Responsibilities:

* govern immutable pre-registered Restricted-Live Trial Policies and Plans;
* bind exact scope, baseline, maximum credible effect, capacity request, action count, duration, evidence, abort, and recovery rules;
* preserve complete negative, failed, aborted, conflicting, and inconclusive trial evidence;
* produce a non-authorizing Trial Evidence Package and single-use Production Scope Promotion Decision;
* prevent scope extrapolation, proof union, automatic promotion, and recovery-based resume;
* trigger monotonic abort and demotion on drift, ambiguity, bound breach, or evidence loss.

Trial-planning, evidence, review, promotion, dashboard, and monitoring components SHALL NOT mutate or release RCL capacity, activate configuration, issue Live Authorization or Transmission Capability, classify protection, transmit, clear HALT, or re-arm. ADR-002-025 defines the exact governance and operational gates. Acceptance of the governance mechanism does not authorize an EV-L5 trial.

---

### 10.28 Safety Deviation and Residual-Risk Governance

Responsibilities:

* govern an immutable Safety Deviation Policy and explicit Non-Waivable Boundary;
* validate exact requirement, hazard, scope, duration, dependency closure, residual risk, compensating controls, evidence, and conflicts;
* produce non-authorizing Safety Deviation Decisions and Residual-Risk Acceptance Records;
* maintain one canonical Active Deviation Set and monotonic Deviation Generation for each exact Safety Configuration Bundle;
* prevent self-approval, permissive union, silent renewal, evidence relabeling, stale-decision reuse, and recovery-based revival;
* trigger monotonic restriction when a decision, control, evidence item, scope, review, or generation expires or becomes invalid.

Deviation registries, evaluators, workflows, ticketing, dashboards, evidence, and review components SHALL NOT mark an unmet requirement `PASS`, mutate or release RCL capacity, activate configuration, issue Live Authorization or Transmission Capability, classify protection, transmit, clear HALT, or re-arm. ADR-002-026 defines the exact governance and acceptance gates. Acceptance of the governance mechanism accepts no specific deviation.

---

### 10.29 Safety Incident and Containment Governance

Responsibilities:

* govern one immutable Safety Incident Policy and authenticated signal registry;
* classify material signals conservatively and calculate the greatest credible affected dependency scope;
* maintain immutable Safety Incident Records, a monotonic Incident Generation, and one canonical Active Safety Incident Set;
* coordinate separately authorized restriction, hard fencing, containment, demotion, protection review, controlled shutdown, evidence, notification, and recovery handoff;
* preserve unresolved broker, order, fill, exposure, capacity, protection, external-activity, evidence, and recovery obligations;
* produce non-authorizing Incident Recovery Handoff Packages and independent administrative closure decisions;
* prevent stale-owner restore, favorable incident subsets, shutdown-as-finality, post-hoc waiver, premature closure, and recovery-based revival.

Incident detection, registry, coordination, notification, evidence, investigation, and closure components SHALL NOT mutate or release RCL capacity, classify an action as protective, activate configuration, issue Safety Authority, Live Authorization, or Transmission Capability, hold a usable live-order credential and route, transmit, clear HALT or a local restrictive latch, establish recovery readiness, restore production scope, or re-arm. Safety Authority, Human HALT, RCL, Protective Action Controller, Cancellation Arbiter, Recovery Coordinator, and Broker Egress Gateway retain their existing authority. ADR-002-027 defines the exact lifecycle and acceptance gates.

---

### 10.30 Safety Telemetry and Continuous Conformance Monitoring

Responsibilities:

* govern one immutable Safety Monitoring Policy, Critical Telemetry Manifest, and Monitor Coverage Manifest;
* preserve exact telemetry identity, scope, source continuity, semantics, units, derivation lineage, trustworthy-time basis, completeness, and failure domains;
* map every applicable Critical requirement, hazard, accepted control, bound, live prerequisite, and failure mode to deterministic monitors, restrictive paths, alerts, evidence, and currentness;
* publish fenced Monitor Generations, non-authorizing Continuous Conformance Snapshots, Safety Monitoring Gaps, Safety Alert Records, and Alert Escalation Records;
* preserve effective independence and disclose source, collector, evaluator, datastore, administrator, deployment, and notification common modes;
* keep suppression, maintenance, correlation, deduplication, backpressure, delivery, acknowledgement, and escalation fail-closed;
* request independently owned restrictive fencing and supply exact authenticated signals to incident governance;
* preserve economic continuity, evidence honesty, and non-revival across failure and recovery.

Monitoring, alert, paging, dashboard, workflow, and escalation components SHALL NOT own the underlying safety fact, mark a requirement or evidence item `PASS`, mutate or release RCL capacity, classify an action as protective, activate configuration, issue Safety Authority, Live Authorization, or Transmission Capability, hold a usable live-order credential and route, transmit, clear UNKNOWN, HALT, a Local Restrictive Latch, a Monitoring Gap, or an incident, establish recovery readiness, restore production scope, or re-arm. A `CONFORMING` Snapshot is only a non-authorizing negative gate. ADR-002-028 defines the exact protocol and acceptance gates.

---

### 10.31 Software Supply-Chain and Release Artifact Admission

Responsibilities:

* govern one immutable Software Release Policy and exact source-review, build, dependency/toolchain, signer/key, registry, compatibility, admission, deployment, runtime-attestation, restriction, and recovery rules;
* bind immutable source tree and generated-source closure to exact hermetic or explicitly bounded build recipes, builder identities and epochs, dependency/toolchain closure, release outputs, platforms, consumers, and Safety Configuration Bundle scope;
* authenticate build provenance without treating attestation, signature, scan, SBOM, tests, CI success, registry custody, deployment health, canary success, or historical acceptance as admission or authority;
* evaluate one complete Release Artifact Manifest and compatibility graph deterministically and independently as `ADMIT`, `DENY`, or `UNKNOWN`;
* commit one monotonic Release Generation and complete exact Admitted Release Set for each overlapping scope; fence stale publishers, deployments, runtime instances, consumers, restore histories, and signer/key state;
* positively attest actual executable, image, library, plugin, sidecar, proxy, SDK, signer, and dynamically loaded runtime bytes and their workload, environment, Safety Cell, configuration, route, and egress bindings;
* propagate compromise, revocation, vulnerability, substitution, compatibility loss, runtime drift, and provenance gaps restrictively through ADR-002-024 and final egress;
* preserve broker finality, economic effect, capacity, evidence honesty, recovery, and non-revival semantics.

Supply-chain and release artifacts are non-authorizing negative gates. Repository, review, builder, signer, key, registry, scanner, admission, deployment, attestation, evidence, and replay identities SHALL NOT activate configuration, mutate or release RCL capacity, classify protection, issue Safety Authority, Live Authorization, or Transmission Capability, hold a usable live-order credential and route, transmit, clear UNKNOWN, HALT, a Local Restrictive Latch, a Monitoring Gap, or an incident, establish readiness, restore production scope, or re-arm. ADR-002-029 defines the exact protocol and acceptance gates.

---

### 10.32 Post-Trade Obligation and Finality Governance

Responsibilities:

* govern one immutable Post-Trade Finality Policy covering exact obligation classes, leg construction, source authority, statement coverage, field-specific finality, breaks, corrections, dependency closure, currentness, recovery, and evidence;
* compile full and partial fills, fees, taxes, interest, financing, settlement, cash, collateral, margin, borrow, recall, exercise, assignment, corporate action, custody, transfer, delivery, break, correction, and reversal facts into immutable Economic Obligation Records;
* maintain one complete Active Economic Obligation Set and monotonic Post-Trade Obligation Generation through a fenced Post-Trade Obligation Ledger;
* keep execution, trade capture, instruction acceptance, settlement, cash availability, collateral eligibility, custody/legal title, fees/tax, borrow discharge, and corporate-action finality orthogonal;
* bind exact source provenance, continuity, statement coverage, pagination, cutoff, revision, preliminary/final status, common-mode analysis, and correction horizons;
* preserve conservative capacity across order-to-position-to-obligation transfers and corrections without making PTOL, finality proof, or reconciliation a capacity authority;
* restrict stale, conflicting, incomplete, broken, corrected, or unverified state at RCL admission, authority issuance, and final egress under active currentness;
* ensure every broker-, clearing-, custodian-, bank-, or transfer-directed instruction uses a separately governed exact Intent, approval, effect, RCL commitment, current authority, and the Final Egress Trust Boundary;
* preserve missing-ACK, Cancel-ACK, economic-continuity, evidence-honesty, recovery, and non-revival semantics.

The Post-Trade Obligation Ledger is the sole TOS serializer for obligation lifecycle only. The RCL remains the sole capacity mutation and serialization authority, and Broker Adapter / Egress Gateway remains the final external transmission enforcement point. PTOL, reconciliation, statement, finality, dashboard, operator, evidence, and recovery identities SHALL NOT create external truth, cash, collateral, legal title, capacity, authority, route access, readiness, or re-arm. ADR-002-030 defines the exact protocol and acceptance gates.

---

## 11. Trading Action Pipeline

The logical action sequence SHALL be:

```text
Critical Input Snapshot and immutable Decision Context Capsule
        ↓
Decision Proposal
        ↓
Deterministic Candidate Canonical Broker Command
        ↓
Exact Venue and Order Admissibility Decision
        ↓
Independent Approval
        ↓
Intent Registration
        ↓
Current Aggregate Risk State Snapshot and Adverse Scenario Set
        ↓
Exact Aggregate Risk Decision and Adverse Increment Vector
        ↓
Current Action Flow State Snapshot and Exact Action Flow Decision
        ↓
Exclusive RCL Risk-Capacity and Action-Flow Commitment
        ↓
Order Conformance Proof
        ↓
Current Safety Authority Verification
        ↓
Live Scope Verification
        ↓
Final Outbound Conformance Verification
        ↓
Per-Send Active Currentness Proof and Ordered Capability Claim
        ↓
Transmission
        ↓
Acknowledgement / Fill Processing
        ↓
Reconciliation
        ↓
Post-Trade Obligation and Field-Specific Finality Reconciliation
        ↓
Capacity Release or Adjustment
```

No stage SHALL be bypassed for an exposure-increasing action.

ADR-002-018 requires the exact Decision Context Capsule identity and digest to remain bound through proposal, independent approval, Intent, capacity, authority, capability, Commit Proof, and final egress. Material context change invalidates affected future permission; it does not erase possible economic effect.

ADR-002-019 additionally requires one exact current Venue Constraint Snapshot and Order Admissibility Decision for the complete broker-request shape. A calendar, quote, connection, or “exit” label does not prove executability; constraint invalidation blocks future new-risk send without erasing prior economic effect.

ADR-002-020 requires the candidate Canonical Broker Command to be constructed deterministically from one immutable proposal before venue evaluation and independent approval. Approval and Intent registration bind the unchanged proposal, envelope, candidate digest, and exact admissibility decision. Its later non-authorizing Order Conformance Proof binds those results to the RCL commitment before authority issuance. Final egress compares the actual outbound representation and does not repair or recompile a mismatch.

ADR-002-023 requires one complete Proposal Approval Request and one exact Independent Approval Decision over the unchanged Capsule, proposal, construction envelope, candidate command, venue decision, policies, generations, and independent facts. The Intent Registry atomically consumes `APPROVE` once into one immutable Intent; later stages may only narrow or deny, and final egress actively verifies the exact current approval and consumption lineage.

ADR-002-021 requires one exact current aggregate-state snapshot and approved adverse-scenario set to project the Economic Effect Envelope across every applicable risk dimension and scope. The Aggregate Risk Decision precedes RCL commitment and grants only an exact allocation request; the RCL remains the sole capacity mutation/serialization authority, and the later conformance proof binds decision and commitment without a cyclic dependency.

ADR-002-022 additionally requires one exact current Action Flow State Snapshot and Action Flow Decision for the canonical broker action before RCL commitment. The RCL atomically commits every required economic and broker-resource vector and creates a single-use Action Flow Permit; the later conformance, authority, capability, and final-egress steps cannot widen or regenerate it. This ordering does not turn the Action Flow Governor or permit into transmission authority.

ADR-002-024 requires final egress to validate one complete exact Safety Currentness Vector and every applicable restrictive generation floor for each normal send. The Currentness Ordering Domain orders the non-authorizing Egress Currentness Proof with the single-use capability claim and `SEND_STARTED`; a restrictive fence ordered first denies, while ambiguity remains potentially live and capacity-covered. Cached state, heartbeat, health, TTL, or absence of invalidation cannot replace this step.

ADR-002-025 additionally requires any restricted-live action to bind one exact current Trial Policy, Trial Plan, Trial Run, Promotion Generation, Live Authorization, remaining count/effect/duration envelope, evidence path, and abort generation. Trial status never bypasses the normal pipeline. Trial completion and promotion eligibility are non-authorizing; a broader production scope requires break-before-make configuration activation and a fresh governed re-arm.

ADR-002-026 requires every configuration to bind an explicit empty or complete canonical Active Deviation Set. Where a permitted residual risk applies, final egress actively verifies the exact current Safety Deviation Policy, Deviation Generation, active-set digest, reduced profile scope, and absence of invalidation. A deviation decision never skips a pipeline stage, changes broker-finality semantics, marks evidence `PASS`, or creates authority.

ADR-002-027 requires every affected authority issuer and final egress to establish the exact current Safety Incident Policy, Incident Generation, and Active Safety Incident Set. Incident state may only deny or narrow later permission. A declaration or scope expansion ordered before the capability claim denies; ambiguous declaration-versus-first-byte ordering remains potentially live, capacity-covered, and ineligible for blind retry. Incident closure, quiet time, process shutdown, or recovery status never bypasses a pipeline stage or creates permission.

ADR-002-028 requires every scope whose continued operation depends on continuous monitoring to bind the exact current Safety Monitoring Policy, Monitor Generation, Critical Telemetry and Monitor Coverage Manifest digests, coverage completeness, unresolved Monitoring Gaps, and restrictive disposition through authority issuance and final egress. `CONFORMING` is only a non-authorizing negative gate. Cached green state, quiet time, heartbeat, page acknowledgement, or absence of an alert cannot prove currentness, override another denial, or create permission.

ADR-002-029 requires every safety-critical consumer, authority issuer, and final egress to bind the exact current Software Release Policy, Release Generation, complete Admitted Release Set, Release Artifact Manifest, actual Runtime Artifact Attestation, compatibility graph, signer/key status, and restriction floor. `ADMIT` is only a non-authorizing negative gate. Tags, signatures, scans, SBOMs, tests, CI, registry presence, deployment health, canary state, cached admission, heartbeat, or absence of revocation cannot prove currentness or create permission.

ADR-002-030 requires every fill or other economic event to create or update exact immutable obligation legs under one current Post-Trade Finality Policy and Post-Trade Obligation Generation. PTOL serializes obligation lifecycle; RCL alone transfers, quarantines, or releases capacity after exact current evidence. Final Quantity Proof, statements, acknowledgements, scheduled dates, quiet time, and favorable balances cannot collapse field-specific finality or create headroom. Any external economic instruction re-enters the complete governed pipeline and final egress.

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
* complete action-class, sustained-rate, burst, queue, in-flight, retry, reconnect, cause-amplification, and Protective Flow Reserve semantics required by ADR-002-022;
* current venue/session/halt/tradability, price/tick/lot/quantity, order-type/time-in-force, account/margin/borrow/settlement, and rule-change semantics needed by ADR-002-019.
* API/SDK defaults, duplicate-field behavior, canonicalization, numeric encoding, signing, redirects, transport rewrites, and actual-outbound observability needed by ADR-002-020.

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

Incident declaration, administrative closure, shutdown-plan completion, component termination, session or credential expiry, route removal, quiet time, or recovery handoff SHALL NOT release capacity or expire possible economic effect.

### 14.5 Crash Recovery

Risk-capacity commitments SHALL survive process restart or be reconstructed conservatively before trading resumes.

### 14.6 Trapped Exposure

Trapped exposure SHALL be treated as non-reducible.

No future exit assumption SHALL create additional risk authority.

### 14.7 External and Non-Trade Changes

External activity and recognized non-trade changes SHALL enter the reconciliation and capacity models as first-class inputs.

Corporate actions, symbol or instrument-identity changes, expiry, exercise, assignment, rollover, broker administrative adjustments, account transfers, delisting, and suspension changes SHALL NOT be assumed to be fills. Unrecognized changes SHALL be treated as Unattributed External Exposure.

ADR-002-010 defines the normative event identity, conservative transition envelope, Risk Capacity Ledger remapping, open-order treatment, and recovery requirements.

ADR-002-021 defines the normative aggregate-state snapshot, adverse-scenario evaluation, single-action and portfolio-wide projected vectors, benefit recognition, numerical safety, exact allocation decision, invalidation, and active RCL/final-egress currentness. Missing scopes or dimensions and unknown broker/order/exposure state consume conservative capacity and block new risk.

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

Manual or broker-portal activity performed during incident containment remains external activity until attributed and reconciled under the normal evidence rules. An incident record, operator statement, or emergency label cannot make it retroactively compliant or release its capacity effect.

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
* production-scope constraints;
* current safety-incident restriction and Incident Generation.

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

Changes that increase operational authority or widen a safety limit SHALL require independent approval satisfying the two-effective-principal requirement of RFC-001 SAFE-053 — satisfiable by the two-natural-person quorum or by the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1) — and SHALL NOT take effect silently during live operation.

This discharges the RFC-000 CONST-015 bounded-human-authority principle for runtime safety-configuration changes; it adds no authority and preserves both SAFE-053 satisfaction paths.

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

Incident lifecycle state is orthogonal to these operational modes and never grants a mode transition. Controlled shutdown SHALL deny or fence new economic action before ordinary producers are stopped, preserve RCL and potentially-live state, required protection, reconciliation, evidence, and recovery obligations, and leave the scope behind a closed Recovery Barrier. Process death, scale-to-zero, socket close, credential disablement, or queue deletion is not a Hard Egress Fence or broker-finality proof.

### 20.1 Mode-Transition Matrix

Every edge below is derived from existing normative fragments, except U1, which is fixed by a new normative decision (ADR-002-001 §8.5); none is invented. Three edges that no earlier ADR fixed (see D) were resolved in Wave 8 — U1 by a new normative decision (ADR-002-001 §8.5), U2 by enumeration (ADR-002-007 §14), and U3 by the informative naming-map below — discharging the Wave-7 debt recorded in ARCHITECTURE-GATE-STATUS §3.10/§3.11.

**Restriction lattice** (derived from ADR-002-001 §8 ordering and the §20 table; increasing restriction left to right):

```text
LIVE_NORMAL ⊐ LIVE_RESTRICTED ⊐ DEGRADED_PROTECTIVE ⊐ CONTAINED ⊐ HALTED
```

`RECOVERY` is the non-live pre-arm reconciliation state; `NON_LIVE` is the no-live-authority baseline.

**Naming map (informative; U3).** The §20 names are the canonical labels for the operational
*mode*; the ADR-002-017 §9 `CLOSED_NON_LIVE`, `CLOSED_RECOVERY`, `CLOSED_CONTAINED`, and
`CLOSED_HALTED` names are the canonical labels for the corresponding recovery-*barrier state*
(which describes new-risk-denial context, not permission — ADR-002-017 §9). They name different
objects and correspond one-to-one by the non-live condition they describe: mode `NON_LIVE` ↔
barrier `CLOSED_NON_LIVE`; mode `RECOVERY` ↔ barrier `CLOSED_RECOVERY`; mode `CONTAINED` ↔ barrier
`CLOSED_CONTAINED`; mode `HALTED` ↔ barrier `CLOSED_HALTED`. Neither vocabulary is renamed; the
`CLOSED_` prefix is the barrier-state form of the same non-live condition.

**A. Restrictive (degradation) edges — always available, monotonic, restrictive-authorized** (derived: SIR-INV-002 asymmetry; ADR-002-007 §9/§10/§17; ADR-002-001 §8):

| Edge | Trigger | Guard | Authorizing owner |
|---|---|---|---|
| any live/degraded → HALTED | human HALT or Critical safety signal | none required beyond authentication (HALT is broader/easier than re-arm, ADR-002-007 §13) | Human Safety Principal / Safety Authority (ADR-002-017 §21) |
| LIVE_NORMAL → LIVE_RESTRICTED | dependency degradation, Safety Authority still verified (ADR-002-001 §8.1) | reduced-authority envelope approved | Safety Authority (automatic restrictive, ADR-002-007 §10) |
| LIVE_NORMAL / LIVE_RESTRICTED → DEGRADED_PROTECTIVE | loss of a new-risk continuous-validity predicate (ADR-002-007 §9) | protective classification still trustworthy | Safety Authority (suspend/revoke, §8.2) |
| any → CONTAINED | autonomous protective classification unavailable/untrustworthy (ADR-002-001 §8.3) **or** incident containment | Safety Authority action (§20) | Safety Authority; in CONTAINED, emergency de-risking per §8.3.1 is authorized by the current Safety Authority, or the operator emergency path (ADR-002-001 §23.2) when the Safety Authority is unavailable — **this resolves M-07-3** (the §6.2→§8.3.1 routing authority); an action not provable reduce-only routes to trapped exposure (ADR-002-001 §15), with no mode change |

**B. Restorative (toward-live) edges — governed, never automatic** (derived):

| Edge | Trigger | Guard | Owner |
|---|---|---|---|
| NON_LIVE / HALTED / CONTAINED / DEGRADED_PROTECTIVE → RECOVERY | recovery trigger (ADR-002-017 §8) | barrier advanced/closed; fenced current Recovery Generation | Recovery Coordinator (fenced) |
| RECOVERY → LIVE_RESTRICTED | READY_RESTRICTED (ADR-002-017 §16) + full ADR-002-007 §12 workflow | positively-isolated safe subset; new Live Authorization; human dual control (§13); no dominating CONTAINED/HALTED | Live Authorization Service issues; ADR-002-015 quorum (or §17.1 variant) approves |
| RECOVERY → LIVE_NORMAL | READY (full scope) + full §12 workflow | as above at full scope | as above |
| LIVE_RESTRICTED → LIVE_NORMAL | staged scope expansion (ADR-002-007 §14; ADR-002-025 progressive promotion) | promotion gates; new Live Authorization for the authority increase; approver of the limit increase ≠ sole armer, except via the approved ADR-002-015 §17.1 variant per RFC-001 SAFE-053 (§13) | governed authority increase — two independent effective principals per RFC-001 SAFE-053 (quorum or ADR-002-015 §17.1 variant) |

**The RECOVERY-transit rule (normative).** No transition *into* LIVE_NORMAL or LIVE_RESTRICTED is permitted except as the terminal step of the ADR-002-007 §12 re-arm workflow, whose guards include a current ADR-002-017 Recovery Readiness Decision; equivalently, recovery readiness is a mandatory precondition for any live re-entry (ADR-002-001 §16; §23.1). HALTED is dominant: leaving HALTED requires explicit human governance clearing HALT under fresh re-arm — recovery cannot downgrade HALTED → RECOVERY or clear a deny latch (ADR-002-017 §15 / SBR-INV-009; ADR-002-007 §17).

**C. Forbidden transitions (explicit — derived):**

* Any → LIVE_NORMAL that is automatic or connectivity/health/quiet-time/replay/cooldown-triggered (§20, §23.2; ADR-002-007 §17; SBR-INV-014; SIR-INV-015; philosophy §23; anti-pattern §39.8).
* HALTED → any live mode directly, bypassing recovery readiness + fresh re-arm (SBR-INV-009/-014; ADR-002-007 §17).
* Any mode transition driven by incident lifecycle state or by administrative incident closure (§20 "orthogonal … never grants a mode transition"; SIR-INV-012 closure is non-permissive; SIR-INV-015 recovery does not revive; ADR-002-027 §19/§21).
* Re-arm where one identity both enlarges limits and arms other than through the approved Governed Single-Operator Re-Arm Variant satisfying RFC-001 SAFE-053 (ADR-002-007 §13; §23.1).
* Recovery downgrading HALTED → RECOVERY automatically (ADR-002-017 §15).

**D. Previously-UNRESOLVED edges — resolved in Wave 8 (Wave-7 debt discharged; ARCHITECTURE-GATE-STATUS §3.10/§3.11):**

* **U1 — CONTAINED → DEGRADED_PROTECTIVE (inter-protective de-restriction), resolved by a new
  normative decision in ADR-002-001 §8.5.** Trigger: an explicit current-Safety-Authority
  governance decision (never elapsed time, reconnection, or quiet time). Guard: affirmative
  re-establishment of the §6 classifier trust premises — current reconciled authoritative state,
  valid Safety Authority (ADR-002-003), current Hard Safety Envelope / Runtime Safety Profile, and
  restored Critical-Input trust (ADR-002-018); no dominating HALTED or unresolved incident
  (ADR-002-027; ADR-002-015). Owner: the current Safety Authority under restrictive-authority
  governance. It grants no new-risk and no live authority and is not a re-arm (ADR-002-007
  §12/§13); the guard fails closed to CONTAINED and is revocable. → **new normative decision: ADR-002-001 §8.5.**
* **U2 — LIVE_RESTRICTED → LIVE_NORMAL in-place readiness-refresh extent, resolved by enumeration
  in ADR-002-007 §14.** An in-place expansion re-establishes the §12 recovery-readiness elements
  proportional to the delta (reconciled state, admissibility, capacity and protective coverage,
  envelope/profile headroom, Recovery Readiness Decision, and Decision Context Capsule for the
  added scope), requires a new Live Authorization for the delta (§7), preserves the §13 rule that
  the limit-increase approver is not the sole armer, and obeys the ADR-002-025 progressive-promotion
  gate; a full §12 re-arm from a non-live start is required only where a failure, incident, or
  containment interrupted continuous validity. → **enumerated: ADR-002-007 §14.**
* **U3 — NON_LIVE / RECOVERY vs ADR-002-017 CLOSED_NON_LIVE / CLOSED_RECOVERY, resolved by the
  informative naming-map above (§20.1).** The two vocabularies name different objects — operating
  mode vs recovery-barrier state — and map one-to-one by the non-live condition; neither is
  renamed. → **mapped (informative): §20.1.**

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

### 21.6 Protective Action-Flow Capacity

Protective request priority SHALL NOT be counted as reserved capacity. Every claimed protective submit, cancel, replacement, query, session, queue, in-flight, credential, route, endpoint, or broker-rate resource SHALL be physically or logically reserved within its proven scope and pre-committed through the Risk Capacity Ledger.

ADR-002-022 defines the complete Action Flow Policy, shared-scope budget, amplification, retry/reconnect containment, single-use permit, active final-egress currentness, and Protective Flow Reserve contract. Unknown or inseparable broker limits reduce or prohibit normal live scope; they do not create permission.

---

## 22. Evidence and Observability

Every live action SHALL produce evidence for:

* context identity and version;
* decision;
* approval;
* Intent;
* Safety Profile;
* Hard Safety Envelope version;
* Safety Deviation Policy, Deviation Generation, and Active Deviation Set;
* Safety Incident Policy, Incident Generation, Active Safety Incident Set, and incident-scope result;
* Safety Monitoring Policy, Monitor Generation, Critical Telemetry and Monitor Coverage Manifest digests, Continuous Conformance Snapshot, unresolved Safety Monitoring Gaps, suppression state, and monitoring-currentness result;
* applicable Safety Alert and Alert Escalation Record identities and delivery state;
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
* suspected or declared incident;
* incident scope expansion, containment, controlled shutdown, recovery handoff, and administrative closure;

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
9. every applicable Safety Deviation Policy, Active Deviation Set, compensating control, review, expiry, and Deviation Generation is positively current, and no request inside the Non-Waivable Boundary exists;
10. every applicable Safety Incident Policy, Incident Generation, Active Safety Incident Set, ongoing obligation, Incident Recovery Handoff Package, and closure invalidation is positively current, and no suspected or open incident blocks the scope;
11. every applicable Safety Monitoring Policy, Monitor Generation, Critical Telemetry Manifest, Monitor Coverage Manifest, Continuous Conformance Snapshot, Safety Monitoring Gap, suppression, and alert/escalation obligation is positively current, and no unresolved monitoring condition blocks the scope;
12. every applicable Software Release Policy, Release Generation, complete Admitted Release Set, exact Release Artifact Manifest, Runtime Artifact Attestation, compatibility result, signer/key status, and release restriction is positively current, and no unresolved supply-chain or runtime-artifact condition blocks the scope;
13. every applicable Post-Trade Finality Policy, Post-Trade Obligation Generation, complete Active Economic Obligation Set, Statement Coverage Manifest, open break/correction, field-specific finality proof, and RCL capacity transition is positively current, and no unresolved obligation or statement condition creates headroom or blocks the scope;
14. Recovery Coordinator readiness decision;
15. new Live Authorization issued;
16. explicit human control according to the approved separation-of-duty policy.

No blocking Critical hazard may remain. The same human or service identity SHALL NOT both enlarge limits and arm live trading, except through the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1) satisfying RFC-001 SAFE-053; a service identity SHALL NOT use the variant, which is a human-authority path.

### 23.2 No Automatic Re-Arming

The system SHALL NOT automatically restore live autonomous authority merely because a failed dependency becomes available.

Recovery readiness is not live authority.

Incident stabilization, remediation, administrative closure, accepted recovery handoff, evidence repair, replay match, or quiet time is not recovery readiness and SHALL NOT clear HALT, a local restrictive latch, or the Recovery Barrier. ADR-002-027 governs the incident-to-recovery handoff; ADR-002-017 and ADR-002-007/015 retain readiness and fresh re-arm ownership.

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
* bounded blast radius;
* independently available incident restriction and durable incident-record custody.

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
* source-code repository and review workflow;
* isolated build runner and dependency/toolchain resolver;
* artifact signer, key custody, and transparency or admission service;
* content-addressed artifact registry and restore path;
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

Incident detection, registry, coordination, notification, evidence, investigation, and closure identities SHALL NOT hold a usable live-order credential and broker route, clear restrictive state, or publish a stale Incident Generation after replacement or restore. Suspected signal suppression, active-set substitution, closure replay, or alternate-route access SHALL restrict the affected scope.

ADR-002-013 defines the normative Final Egress Trust Boundary, usable live-order authority, credential and broker-order route confinement, quorum-sufficient Commit Proof validation, stale-egress hard fencing, and fail-closed credential rotation and recovery rules.

ADR-002-015 defines the normative effective Human Safety Principal, Human Authority Policy, exact dual-control approval artifacts, one-human restrictive HALT, break-glass confinement, delegation, compromise, and non-revival rules. Human approval remains an input to separately enforced decisions and cannot become configuration, capacity, Live Authorization, protective-classification, or broker-transmission authority.

ADR-002-016 defines the security and custody boundary for immutable safety evidence, durable pre-effect receipts, independent integrity anchors, protected raw records, redaction views, replay isolation, evidence administration, and chain of custody. Evidence and replay principals SHALL NOT possess live broker authority or production mutation paths.

ADR-002-018 defines source identity and continuity, transformation-lineage, independent-input common-mode, immutable context binding, correction/invalidation, stale-publisher, Capsule-substitution, and active final-egress currentness threats. Context, data, evidence, operator, and replay principals SHALL NOT obtain approval, capacity, Live Authorization, protective-classification, or broker-transmission authority through input processing.

ADR-002-019 defines Venue Constraint Policy integrity, exact order-admissibility binding, Constraint Generation fencing, session/halt/account/margin/broker-rule invalidation, and active final-egress constraint-currentness threats. The Venue Constraint Gate and its read identities SHALL NOT obtain capacity, approval, protective-classification, Live Authorization, broker-transmission, HALT-clear, or re-arm authority.

ADR-002-020 defines deterministic Intent-to-order construction, closed transformation envelopes, exact identity/unit/direction/numeric semantics, conservative economic-effect proof, downstream mutation fencing, parser-differential defense, and actual-outbound verification. Compiler, mapping, schema, SDK, evidence, and replay identities SHALL NOT obtain approval, capacity, protective-classification, Live Authorization, broker-transmission, HALT-clear, or re-arm authority.

ADR-002-021 defines complete aggregate-state consistency cuts, adverse-scenario evaluation, risk-vector dimensions/scopes, valuation and benefit proof, deterministic numerical safety, exact allocation decisions, RCL binding, invalidation, and active RCL/final-egress currentness. Risk evaluators, scenario/model services, snapshot projections, independent verifiers, evidence, and replay identities SHALL NOT mutate capacity, issue Live Authorization or Transmission Capability, classify protection, transmit, clear HALT, or re-arm.

ADR-002-022 defines complete broker-directed action classification, distributed shared-scope budgets, bounded cause amplification, RCL-serialized single-use Action Flow Permits, retry/reconnect containment, Protective Flow Reserve, and active final-egress currentness. Action Flow Governors, producer-local limiters, schedulers, queues, retry/reconnect services, evidence, and replay identities SHALL NOT mutate distributed capacity, issue Live Authorization or Transmission Capability, classify protection, transmit outside final egress, clear HALT, or re-arm.

ADR-002-023 defines automated independent proposal approval, complete exact request and decision binding, true validation-path independence, serialized single-use Intent registration, invalidation fan-out, and active final-egress approval currentness. Approval evaluators, independent-input services, policy engines, Intent Registry identities, evidence, and replay identities SHALL NOT mutate capacity, issue Live Authorization or Transmission Capability, classify protection, transmit, clear HALT, or re-arm.

ADR-002-024 defines the normative cross-artifact Currentness Policy, complete Safety Currentness Vector, monotonic Restrictive Fence Record, independent local deny latch, per-send Egress Currentness Proof, and claim/fence/first-byte ordering. Currentness sequencers, owner publishers, latch administrators, evidence, and replay identities SHALL NOT invent owner facts, mutate or release capacity, issue approval or live authority, classify protection, transmit, clear HALT, or re-arm.

ADR-002-025 defines the normative restricted-live Trial Policy and Plan, pre-registered maximum credible effect, abort/demotion behavior, immutable Trial Evidence Package, exact coverage rules, progressive single-use Production Scope Promotion Decision, and production-authorization handoff. Trial, evidence, review, promotion, dashboard, monitoring, and replay identities SHALL NOT mutate capacity, create live authority, activate production, transmit, clear HALT, or re-arm.

ADR-002-026 defines the normative Safety Deviation Policy, Non-Waivable Boundary, exact request and residual-risk contracts, independently verified compensating controls, Effective Principal approval, single-use configuration eligibility, canonical Active Deviation Set, Deviation Generation, expiry/revocation, and evidence-honesty rules. Deviation, workflow, registry, ticketing, reviewer, evidence, monitoring, and replay identities SHALL NOT mark unmet requirements `PASS`, mutate capacity, activate configuration, create live authority, transmit, clear HALT, or re-arm.

ADR-002-027 defines the normative Safety Incident Policy, authenticated signal classification, greatest-credible dependency scope, monotonic Incident Generation, canonical Active Safety Incident Set, containment and controlled-shutdown coordination, external emergency activity, lossless recovery handoff, independent administrative closure, currentness, and non-revival rules. Incident, workflow, coordination, notification, evidence, investigation, plan, handoff, and closure identities SHALL NOT mutate or release capacity, classify protection, create live authority, transmit, clear HALT, establish readiness, restore scope, or re-arm.

ADR-002-028 defines the normative Safety Monitoring Policy, exact Critical Telemetry and Monitor Coverage Manifests, deterministic continuous-conformance evaluation, monotonic Monitor Generation, Monitoring Gaps, effective independence, suppression and maintenance safety, bounded alert delivery and escalation, restrictive and incident handoff, active final-egress currentness, and non-revival rules. Monitoring, alert, paging, dashboard, and escalation identities SHALL NOT mark a requirement `PASS`, mutate or release capacity, classify protection, create live authority, transmit, clear safety state, close an incident, establish readiness, restore scope, or re-arm.

ADR-002-029 defines the normative Software Release Policy, exact source/build/dependency/toolchain lineage, build provenance, content-addressed release artifacts, independent admission, monotonic Release Generation, complete Admitted Release Set, runtime artifact attestation, compatibility, restriction, final-egress currentness, rollback/restore, and non-revival rules. Repository, builder, signer, registry, scanner, admission, deployment, attestation, evidence, and replay identities SHALL NOT activate configuration, mutate or release capacity, classify protection, create live authority, transmit, clear safety state, establish readiness, restore scope, or re-arm.

ADR-002-030 defines exact post-trade Economic Obligation Records, field-specific finality, Post-Trade Obligation Ledger serialization, source and statement coverage, breaks/corrections, Post-Trade Obligation Generation fencing, conservative RCL capacity transfer/release, external-instruction confinement, recovery, and non-revival. PTOL, reconciliation, statement, finality, custody, dashboard, operator, evidence, and replay identities SHALL NOT create external truth, mutate or release capacity, issue live authority, hold an unconfined external-economic credential and route, transmit outside final egress, expire economic effect, restore scope, or re-arm.

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
| ADR-002-020 | Intent-to-Order Conformance, Canonical Command Construction, and Economic-Effect Fencing | Proposed |
| ADR-002-021 | Aggregate Risk Projection, Adverse-Scenario Evaluation, and Risk-Decision Integrity | Proposed |
| ADR-002-022 | Action-Flow Budgeting, Retry-Storm Containment, and Protective-Traffic Preservation | Proposed |
| ADR-002-023 | Independent Proposal Approval, Exact-Decision Binding, and Consumption Fencing | Proposed |
| ADR-002-024 | Active Currentness, Revocation, and Final-Egress Admission Fencing | Proposed |
| ADR-002-025 | Restricted-Live Verification, Progressive Scope Promotion, and Production Authorization Governance | Proposed |
| ADR-002-026 | Safety Waiver, Deviation, and Residual-Risk Governance | Proposed |
| ADR-002-027 | Safety Incident Declaration, Containment, Controlled Shutdown, and Closure Governance | Proposed |
| ADR-002-028 | Safety Telemetry Integrity, Continuous Conformance Monitoring, and Alert Escalation Governance | Proposed |
| ADR-002-029 | Software Supply-Chain Integrity, Release-Artifact Admission, and Deployment Provenance Governance | Proposed |
| ADR-002-030 | Post-Trade Economic Obligations, Settlement Finality, and Conservative Account-State Governance | Proposed |

ADR-002-002 through ADR-002-030 are authored as co-located `Proposed` decisions. The Phase B design order ADR-002-009 → ADR-002-011 → ADR-002-010 and the follow-on RCL consensus, final-egress security, safety-configuration governance, human-authority governance, evidence-integrity, safe-start/recovery-barrier, Critical Input/decision-context, venue/session/tradability, Intent-to-order conformance, aggregate-risk evaluation, action-flow governance, independent proposal-approval, active-currentness, restricted-live-promotion, safety-deviation, safety-incident, safety-monitoring, software-supply-chain, and post-trade-finality decisions ADR-002-012 → ADR-002-013 → ADR-002-014 → ADR-002-015 → ADR-002-016 → ADR-002-017 → ADR-002-018 → ADR-002-019 → ADR-002-020 → ADR-002-021 → ADR-002-022 → ADR-002-023 → ADR-002-024 → ADR-002-025 → ADR-002-026 → ADR-002-027 → ADR-002-028 → ADR-002-029 → ADR-002-030 are complete at authorship level only. VER-002-001 and the Evidence Register now cover ADR-002-001 through ADR-002-030, including one-to-one dedicated cases for ADR-002-005 through ADR-002-030. All 372 registered evidence items remain `NOT_IMPLEMENTED`; registration is not execution and does not change ADR or live-readiness status. The Wave-4 Part-2/3 register consolidation discharged the recorded evidence debt into the Evidence Register (now 372) and established the separate development-track register EVIDENCE-REGISTER-DEV (96 items).

---

## 27. Requirements Traceability Matrix

| RFC-001 requirement | Architectural responsibility                            |
| ------------------- | ------------------------------------------------------- |
| SAFE-001            | Safety Authority, Protective Action Controller          |
| SAFE-002            | Protective Action Controller, Position Projection, Cancellation Arbiter |
| SAFE-003            | Safety Profile Validator, Safety Monitoring Policy, Software Release Policy |
| SAFE-004            | Hard Safety Envelope Registry, Monitor Coverage Manifest, Admitted Release Set |
| SAFE-010            | Independent Approval Service, Intent Registry, Aggregate Risk Authority, Risk Capacity Ledger, Post-Trade Obligation Ledger, Currentness Ordering Domain, Artifact Admission Service, Broker Egress Gateway |
| SAFE-011            | Safety Control Plane, Currentness Sequencer, Safety Monitoring Service, Release Registry, Broker Egress Gateway |
| SAFE-012            | Aggregate Risk Policy, Adverse Scenario Set, Aggregate Risk Authority |
| SAFE-013            | Aggregate Risk State Snapshot, Aggregate Risk Authority, Risk Capacity Ledger, admitted risk-runtime artifacts |
| SAFE-014            | Action Flow Governor, Risk Capacity Ledger, Execution Coordinator, Safety Monitoring Service, admitted action-flow runtime artifacts, Currentness Ordering Domain, Broker Egress Gateway |
| SAFE-015            | Risk Capacity Ledger, Action Flow Permit, ordered Egress Currentness Proof |
| SAFE-020            | Independent Approval Decision, Approval Consumption Record, Intent Registry |
| SAFE-021            | Execution Coordinator, Intent Registry, Risk Capacity Ledger, Broker Egress Gateway |
| SAFE-022            | Reconciliation Service, Post-Trade Obligation Ledger, Statement Coverage Manifest |
| SAFE-023            | Reconciliation Service, Post-Trade Finality Policy, Post-Trade Finality Proof |
| SAFE-024            | Reconciliation Service, Post-Trade Break Record, Safety Monitoring Service |
| SAFE-025            | Position and Order Projection, Active Economic Obligation Set, Risk Capacity Ledger |
| SAFE-030            | Context Integrity Service, Decision Context Capsule, Critical Telemetry Manifest, Source Revision Manifest, Dependency and Toolchain Closure Manifest |
| SAFE-031            | Context Integrity Service, Critical Input Policy, Critical Telemetry Manifest, Build Provenance Attestation, Release Artifact Manifest, Evidence Store |
| SAFE-032            | Venue Constraint Gate, Context Integrity Service, Broker Egress Gateway |
| SAFE-033            | Decision Context Capsule, Order Construction Service, Canonical Broker Command, Order Conformance Proof, Order Admissibility Decision, Independent Approval Service, admitted compiler/serializer/SDK artifacts, Execution Coordinator, Broker Egress Gateway |
| SAFE-034            | Trading Approval Policy, Independent Approval Service, Critical Input common-mode analysis, supply-chain effective-control analysis, Human Authority Governance, Safety Deviation Governance |
| SAFE-035            | Trustworthy Time Service, Safety Monitoring Service, build/admission/runtime attestation time contracts |
| SAFE-040            | Protective Action Controller, Cancellation Arbiter, Broker Egress Gateway, Safety Incident Governance |
| SAFE-041            | Safety Authority, Human Authority Governance, Safety Monitoring Service, Release Restriction ingress, Safety Incident Governance |
| SAFE-042            | Operator Control Interface, Human Safety Principals, Safety Alert Escalation, Broker Egress Gateway, Safety Incident Governance |
| SAFE-043            | Protective Action Controller, Incident Containment Plan |
| SAFE-044            | Recovery Coordinator, Safety Control Plane, Post-Trade Obligation Ledger, Safety Monitoring Service, Release Registry and Runtime Artifact Inventory, Broker Egress Gateway, Incident Recovery Handoff Package |
| SAFE-045            | Deployment and Identity Architecture, Software Release Policy, Runtime Artifact Attestation, Restricted-Live Trial Governance, Safety Monitoring Service |
| SAFE-046            | Live Authorization Service, Human Authority Governance, Admitted Release Set, Restricted-Live Trial Governance |
| SAFE-047            | Live Authorization Service, Artifact Admission Decision, Production Scope Promotion Governance, Safety Deviation Governance |
| SAFE-048            | Safety Authority, Risk Capacity Ledger, Currentness Ordering Domain, Release Generation, Safety Monitoring Service, Broker Egress Gateway, Incident Generation |
| SAFE-050            | Hard Safety Envelope Registry, Safety Profile Validator, Human Authority Policy, Restricted-Live Trial Policy, Safety Deviation Policy, Safety Incident Policy, Safety Monitoring Policy, Software Release Policy |
| SAFE-051            | Evidence Store, source decision owners, Build Provenance Attestation, Artifact Admission Decision, Runtime Artifact Attestation, Economic Obligation Record, Statement Coverage Manifest, Post-Trade Finality Proof, Safety Monitoring Service, Broker Egress Gateway, Trial Evidence Package, Residual-Risk Acceptance Record, Safety Incident Record |
| SAFE-052            | Replay and Evidence Service, Evidence Store, Supply-Chain and Release Admission Review, Post-Trade Obligation and Finality Review, Safety Monitoring Review, Production Promotion Review, Safety Deviation Review, Incident Reconstruction and Closure Review |
| SAFE-053            | Human Authority Governance, Operator Control Interface, Live Authorization Service, Restricted-Live Trial Governance, Production Scope Promotion Governance, Recovery Coordinator |
| SAFE-054            | Broker Egress Gateway, Deployment and Identity Architecture, Safety Authority |

This matrix is an initial allocation and SHALL be refined as ADRs are accepted.

---

## 28. Open Architectural Decisions

ADR-002-005 through ADR-002-030 now define the normative orthogonal-state, evidence-confidence, trustworthy-time, re-arm, failure-domain, protective-replacement, non-trade-event, RCL consensus, final-egress security, safety-configuration governance, human-authority governance, evidence-integrity/replay, safe-start/recovery-barrier, Critical Input/decision-context, venue/session/tradability-constraint, Intent-to-order conformance, aggregate-risk evaluation, action-flow governance, independent proposal-approval, active-currentness, restricted-live-promotion, safety-deviation, safety-incident, safety-telemetry/continuous-monitoring, software-supply-chain/runtime-artifact-admission, and post-trade economic-obligation/finality models. Their listed implementation and acceptance questions remain open while those ADRs are `Proposed`. The following architecture and implementation choices SHALL be resolved by the assigned ADR, implementation specification, Verification Profile, Currentness Policy, Restricted-Live Trial Policy, Safety Deviation Policy, Safety Incident Policy, Safety Monitoring Policy, Software Release Policy, Post-Trade Finality Policy, Critical Input Policy, Venue Constraint Policy, Order Construction Policy, Aggregate Risk Policy, Action Flow Policy, Trading Approval Policy, Recovery Barrier Policy, Evidence Integrity Policy, or Broker Capability Profile.

1. Which conforming replicated-state-machine product, storage engine, voter topology, and durability configuration implement ADR-002-012's selected quorum Safety Commit Log mechanism?
2. Which conforming non-exportable signer or credential service, identity-aware order route, Quorum Commit Certificate format, Active Egress Principal topology, and Hard Egress Fence implement ADR-002-013 while carrying ADR-002-007 and ADR-002-012 generations to the broker-send boundary?
3. Which canonical artifact, semantic-normalization, approval, registry, signing, compatibility-manifest, and activation mechanisms implement ADR-002-014 without collapsing configuration governance, capacity, and live-arming authority?
4. Which human identity, phishing-resistant authentication, Effective Principal Graph, approval workflow, quorum, delegation, emergency authenticator, and restrictive egress-latch mechanisms implement ADR-002-015?
5. Which append-only store, source identity, durable acknowledgement, emergency journal, integrity anchor, gap detector, protected raw tier, retention policy, and isolated replay mechanisms implement ADR-002-016?
6. Which Recovery Barrier Policy, ordered Recovery Generation and owner fence, dependency graph, broker/source Inventory Cut protocol, obligation workflow, package signer, and final-egress currentness mechanism implement ADR-002-017?
7. Which Critical Input Policy, source registry/continuity protocol, schema and unit/mapping registry, transformation manifest, consistency-cut rule, independent approval path, Context Generation, invalidation graph, and active final-egress currentness mechanism implement ADR-002-018?
8. Which Venue Constraint Policy, source/continuity registry, Session Phase and tradability state machines, order/account/margin/borrow/settlement rules, exact Snapshot/Decision schemas, Constraint Generation, invalidation graph, and active final-egress currentness mechanism implement ADR-002-019?
9. Which canonical schemas, deterministic numeric/unit system, mapping registry, compiler, independent verifier, serializer/SDK constraints, actual-outbound comparison, Construction Generation, and invalidation mechanism implement ADR-002-020?
10. Which Aggregate Risk Policy, state consistency-cut, risk-vector, scenario, valuation, uncertainty, netting/hedge, numerical, independent-verification, Aggregate Risk Generation, and active RCL/final-egress currentness mechanisms implement ADR-002-021?
11. Which Action Flow Policy, scope graph, RCL vector/permit, atomic risk/action commitment, cause-lineage/amplification, distributed refill, protective lease/reserve, and active RCL/final-egress currentness mechanisms implement ADR-002-022?
12. Which Trading Approval Policy, canonical request/decision/consumption schemas, independent validation and common-mode paths, Trading Approval Generation, Intent Registry single-use transaction, invalidation graph, and active final-egress currentness mechanisms implement ADR-002-023?
13. What deployment topology provides the required failure-domain isolation?
14. What numeric detection, containment, protective-gap, lease, retry, action-flow, amplification, queue, approval-invalidation, evidence-persistence, evidence-gap, recovery-barrier, Critical Input invalidation, venue-constraint invalidation, conformance invalidation, aggregate-risk invalidation, currentness-gap/local-deny/restrictive-fence/per-send-proof/generation-fence, trial-abort/evidence-gap/promotion-generation, deviation-revocation/generation-fence, incident-signal/restriction/scope-expansion/generation/shutdown/handoff, safety-telemetry-loss/monitoring-gap/alert-delivery/escalation/generation-fence, supply-chain-compromise/release-restriction/generation-fence/runtime-drift, post-trade-effect/change/break/restriction/generation/statement-coverage, context/request/decision/command/proof/vector/snapshot/trial/deviation/incident/telemetry/alert/provenance/admission/release-set/runtime-attestation/key-status/obligation/finality/statement/break/transfer age, suppression, effect/count/duration/review-interval, readiness-age, retention, and replay bounds are approved?
15. What evidence establishes broker-specific Final Quantity Proof and external-activity detection bounds?
16. Which broker resources can be physically or logically reserved for protection?
17. How are corporate actions and other non-trade changes attributed and remapped?
18. Which Currentness Policy, owner/dependency registry, Currentness Ordering Domain, generation-floor and Restrictive Fence protocol, independent restrictive ingress, Local Restrictive Latch, exact Safety Currentness Vector, per-send proof/claim transaction, cross-domain barrier, and first-byte ordering mechanism implement ADR-002-024?
19. Which Restricted-Live Trial Policy, exact plan/run registry, worst-credible-effect calculator, action/effect serializer, abort and demotion path, evidence coverage model, independent promotion workflow, production-authorization handoff, and continuous-conformance mechanism implement ADR-002-025?
20. Which Safety Deviation Policy, requirement/hazard registry, Non-Waivable Boundary classifier, dependency-closure and combined-risk evaluator, compensating-control evidence model, independent Effective Principal workflow, Deviation Generation registry, Active Deviation Set, restrictive revocation path, and final-egress currentness mechanism implement ADR-002-026?
21. Which Safety Incident Policy, signal registry and classifier, dependency-closure/common-mode engine, Incident Generation and Active Safety Incident Set registry, independent restrictive ingress, containment and controlled-shutdown orchestrator, external-activity procedure, recovery-handoff transaction, closure quorum, and final-egress currentness mechanism implement ADR-002-027?
22. Which Safety Monitoring Policy, Critical Telemetry and Monitor Coverage Manifest registries, source-continuity and deterministic-evaluator mechanisms, Monitor Generation and writer fence, independent restrictive ingress, suppression governance, correlation/deduplication, delivery/escalation, incident handoff, recovery protocol, and final-egress currentness mechanism implement ADR-002-028?
23. Which Software Release Policy, source-review and immutable-tree registry, isolated build and provenance mechanism, dependency/toolchain closure resolver, signer/key hierarchy, content-addressed registry, independent admission evaluator, Release Generation and Admitted Release Set registry, compatibility graph, deployment/runtime attestation, restriction path, recovery protocol, and final-egress artifact-currentness mechanism implement ADR-002-029?
24. Which Post-Trade Finality Policy, obligation compiler and independent verifier, PTOL consensus/writer-fence/generation mechanism, source-authority and statement-coverage registry, class-specific finality recipes, correction/reopen graph, PTOL-to-RCL ordered transition, external-instruction egress path, recovery protocol, and active currentness mechanism implement ADR-002-030?

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
* direction/position-effect inversion, account/instrument/contract/route substitution, unit/multiplier/currency/numeric drift, permissive rounding, hidden defaults, parser differential, downstream serializer/signer/SDK mutation, command/proof substitution, split/aggregate/retry lineage failure, stale Construction Generation, and compiler recovery attempting old-proof reuse;
* omitted strategy/account/venue/instrument/order/commitment/external/trapped scope, stale or mixed aggregate-state cut, missing risk dimension, unit/sign/limit substitution, adverse-scenario truncation, unproven hedge/netting/correlation/margin benefit, valuation/liquidity/tail failure, numerical overflow/NaN/non-convergence/differential, concurrent stale grant, Aggregate Risk Generation cache, invalidation race, and evaluator recovery attempting old-decision reuse;
* concurrent producer over-allocation, unknown shared broker-limit scope, duplicate-event/fan-out amplification, missing-ACK retry, reconnect/SDK/proxy retry storm, cancel/amend/replace oscillation, queue and in-flight exhaustion, ordinary traffic consuming protective reserve, priority masquerading as reserve, RCL permit double spend, stale refill, Action Flow Generation cache, partition with broker-reachable egress, and recovery attempting old-permit reuse;
* incomplete or mixed Safety Currentness Vector, cached or reusable currentness proof, restrictive-source loss, local-latch bypass, fence/claim/first-byte race, currentness-quorum loss with broker reachability, stale owner/sequencer/restore/egress generation, cross-domain proof union, claim-response loss, and recovery attempting old-vector reuse;
* incomplete, wildcard, patched, or unioned restricted-live scope; underestimated trial effect; local counter overspend; trial-label bypass; abort/send race; evidence-gap continuation; selected or hidden negative runs; post-hoc metric or stop-rule change; scope extrapolation; promotion replay/widening/auto-chain; monitor-loss continuation; and recovery attempting trial resume or automatic re-arm;
* non-waivable requirement exception, under-scoped or unioned deviation, self-approval through shared effective control, observational-only or common-mode compensation, unbounded combined residual risk, evidence relabeled `PASS`, decision replay or duplicate consumption, stale Active Deviation Set, expiry/revocation send race, automatic renewal or predecessor rollback, emergency-route bypass, and recovery attempting deviation or authority revival;
* missed, suppressed, downgraded, delayed, under-scoped, split, or conflicting incident declaration; stale or favorably subsetted Active Safety Incident Set; declaration/scope-expansion versus capability-claim/first-byte race; incident-plane partition with broker reachability; shutdown-before-fence, queue draining by send, process death treated as hard fencing, blind cancellation of required protection, unproven blanket liquidation, priority treated as protective reserve, external broker-portal action, closure releasing capacity or clearing HALT, incomplete recovery handoff, and recovery attempting incident or authority revival;
* omitted, wildcarded, patched, or unioned monitoring coverage; stale green state; source restart or continuity reuse; schema, unit, mapping, derivation, time, NaN, overflow, threshold, hard-maximum, parser, or evaluator drift; nominally independent common-mode monitors; missing or conflicting telemetry selected permissively; broad or expired suppression; deduplication scope loss; alert storm, queue overflow, delivery or escalation failure; acknowledgement treated as containment; stale Monitor Generation; monitoring-plane partition with broker-reachable egress; monitoring invalidation versus first-byte race; direct monitoring broker-route bypass; and recovery attempting authority revival or automatic re-arm;
* source-history or tag movement; incomplete submodule, generated-source, large-file, or build-script closure; mutable build input; builder or provenance substitution; dependency/toolchain/plugin/base-image/runtime-load omission; lockfile or registry compromise; signer/key rollback or revocation; artifact/tag/layer/platform substitution; scan/sign/deploy TOCTOU; effective-control collapse; admission scope widening or set union; stale Release Generation; mixed-version incompatibility; non-live-to-live artifact crossover; runtime drift; stale broker-capable deployment; supply-chain partition with broker-reachable egress; release restriction versus first-byte race; direct deployment or admission broker-route bypass; and rollback, restore, hotfix, or recovery attempting admission or authority revival;
* fill/FQP/trade-capture treated as post-trade finality; omitted or corrected fee/tax/interest/financing legs; partial or failed settlement treated as reusable cash; collateral encumbrance, haircut, or double-use; borrow recall/return/buy-in ambiguity; exercise/assignment/delivery/corporate-action obligation omission; custody transfer or legal-title confusion; statement truncation, revision, or common mode; break/bust/correction/reversal suppression; premature RCL transfer/release; stale Post-Trade Obligation Generation or PTOL writer; finality-proof replay; post-trade partition with external-route reachability; direct transfer-route bypass; and recovery attempting prior finality, capacity release, authority, or automatic re-arm;
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
* Expanded the ADR register through ADR-002-030 and registered ADR-002-002 through ADR-002-030 as Proposed.
* Added the Phase B failure-domain isolation, protective-replacement, and corporate-action/non-trade decisions without changing verification or live-readiness status.
* Selected the quorum-replicated deterministic Safety Commit Log mechanism class for RCL persistence, consensus, writer fencing, currentness ordering, and recovery in ADR-002-012; concrete products and deployment values remain open.
* Defined the effective Final Egress Trust Boundary, credential and route confinement, quorum-sufficient Commit Proof validation, and stale-egress hard fencing in ADR-002-013.
* Defined immutable Hard Safety Envelope and Runtime Safety Profile artifacts, separated governance, canonical semantic validation, committed Profile Generations, break-before-make activation, restrictive precedence, and rollback non-revival in ADR-002-014.
* Defined effective Human Safety Principal identity, exact dual-control approval artifacts, one-human restrictive HALT, break-glass confinement, delegation, compromise, and approval non-revival in ADR-002-015.
* Defined immutable safety evidence, pre-effect durability, integrity anchoring, gap containment, protected retention, isolated deterministic replay, and evidence non-authority in ADR-002-016.
* Defined closed safe startup, monotonic Recovery Generations, fenced recovery ownership, conservative account-wide inventory, dependency-complete obligations, non-authorizing readiness, partial-scope isolation, and fresh governed re-arm handoff in ADR-002-017.
* Defined Critical Input classification, source identity and continuity, exact provenance and transformation lineage, immutable Snapshots and Decision Context Capsules, independent approval common-mode analysis, correction/invalidation fan-out, active final-egress currentness, and data-recovery non-revival in ADR-002-018.
* Defined exact venue/session/tradability, instrument/order/account/margin/borrow/settlement, Broker Capability Profile, Order Admissibility Decision, Constraint Generation, protective-path, final-egress currentness, and non-revival rules in ADR-002-019.
* Defined deterministic Intent-to-order construction, closed Authorized Construction Envelopes, Canonical Broker Commands, conservative Economic Effect Envelopes, Order Conformance Proofs, downstream mutation fencing, and actual-outbound verification in ADR-002-020.
* Defined complete aggregate-state cuts, adverse-scenario evaluation, vector/scoped projection, positive benefit proof, deterministic numerical safety, exact allocation decisions, RCL binding, and active currentness in ADR-002-021.
* Defined complete broker-directed action classification, distributed shared-scope action-flow budgets, bounded cause amplification, RCL-serialized single-use permits, retry/reconnect containment, Protective Flow Reserve, and active currentness in ADR-002-022.
* Defined automated independent proposal approval, exact immutable request/decision binding, true validation-path independence, serialized single-use Intent consumption, invalidation closure, and active egress currentness in ADR-002-023.
* Defined complete cross-artifact active currentness, monotonic restrictive fencing, local deny latches, per-send proof, and claim/fence/first-byte ordering in ADR-002-024.
* Defined restricted-live pre-registration, worst-credible trial effect, abort dominance, evidence coverage, progressive single-use scope promotion, production-authorization handoff, and continuous conformance in ADR-002-025.
* Defined the Non-Waivable Boundary, exact safety-deviation scope, compensating-control and combined residual-risk rules, independent Effective Principal approval, single-use restricted-configuration eligibility, Deviation Generation currentness, evidence honesty, expiry/revocation, and non-revival in ADR-002-026.
* Defined restrictive safety-incident declaration, greatest-credible dependency scope, monotonic Incident Generation, canonical Active Safety Incident Set, non-authorizing containment and controlled shutdown, lossless recovery handoff, administrative closure, currentness, and non-revival in ADR-002-027.
* Defined exact safety-telemetry and monitor coverage, deterministic continuous conformance, Monitoring Gaps, effective independence, suppression safety, bounded alert delivery/escalation, restrictive and incident handoff, active final-egress currentness, and monitoring-recovery non-revival in ADR-002-028.
* Defined exact reviewed-source, build-provenance, dependency/toolchain-closure, content-addressed artifact, independent admission, Release Generation, Admitted Release Set, runtime-attestation, active-currentness, rollback/restore, and non-revival rules in ADR-002-029.
* Defined exact post-trade Economic Obligation Records, field-specific finality, Post-Trade Obligation Ledger serialization, statement coverage, break/correction reopening, conservative RCL transfer/release, external-instruction confinement, currentness, recovery, and non-revival rules in ADR-002-030.
* Expanded VER-002-001 and the Evidence Register to 363 `NOT_IMPLEMENTED` items with one-to-one acceptance-case coverage for ADR-002-005 through ADR-002-030.
* Resolves review findings A-01 through A-14.
* Wave 4 (CORPUS-REVIEW-0001 CR-01, 2026-07-17): the Part-2/3 register consolidation raised the Evidence Register to 372 `NOT_IMPLEMENTED` items (nine Part-1 debt rows discharged, §26 body updated) and created the separate development-track register EVIDENCE-REGISTER-DEV (96 items). RFC-002's normative architecture content is unchanged; this is a count and traceability note only.

### v0.3 — Architecture Terminology and Mode-Transition (Wave 7)

* Wave 7 (CORPUS-REVIEW-0001, 2026-07-17): added §3.1.17 Credible State Space (M-24) — the corpus-wide canonical term the ADR-002-011/012/020/021 "credible"/"worst credible" universals range over, bounded by the active Broker Capability Profile (ADR-002-004) and the approved Adverse Scenario Set (ADR-002-021) — and §20.1 Mode-Transition Matrix (M-26 / M-07-3), normativizing the derived restrictive/restorative edges, the RECOVERY-transit rule, and the forbidden transitions, while marking three underivable edges UNRESOLVED (U1 CONTAINED→DEGRADED_PROTECTIVE; U2 LIVE_RESTRICTED→LIVE_NORMAL §14 readiness-refresh extent; U3 NON_LIVE vs ADR-002-017 CLOSED_NON_LIVE/RECOVERY label). No SAFE-xxx, no numeric bound, no broker proper noun; the §26 "(96 items)" and "372" figures are Wave-4 history and are preserved unchanged. EV-L0 review items, reviewer provenance per VER-002-001 §5 (M-18).

### v0.4 — Mode-Transition Seam Resolution (Wave 8)

* Wave 8 (CORPUS-REVIEW-0001, 2026-07-17): resolved the three §20.1 D edges that Wave 7 had marked UNRESOLVED, discharging the Wave-7 debt recorded in ARCHITECTURE-GATE-STATUS §3.10/§3.11. **U1 (CONTAINED → DEGRADED_PROTECTIVE)** is fixed by a new normative decision in ADR-002-001 §8.5 — a governed, never-automatic, Safety-Authority-owned inter-protective de-restriction that grants no new-risk and no live authority, is not a re-arm, fails closed to CONTAINED, and is revocable; this is flagged explicitly as a new normative decision, not a derived edge. **U2 (LIVE_RESTRICTED → LIVE_NORMAL in-place readiness-refresh extent)** is fixed by enumeration in ADR-002-007 §14.1 (delta-proportional §12 re-establishment, a new Live Authorization for the delta, approver ≠ sole armer, and the ADR-002-025 progressive-promotion gate; a full §12 re-arm from a non-live start only where continuous validity broke). **U3 (NON_LIVE/RECOVERY vs ADR-002-017 CLOSED_* labels)** is resolved by the informative §20.1 naming-map (operating-mode names vs recovery-barrier-state names, one-to-one by the non-live condition; neither vocabulary renamed). No edge is invented; the §20.1 preamble and section D are updated accordingly. No SAFE-xxx, no numeric bound, no broker proper noun; the Evidence Register counts are held (Part-1 372; development-track 98). EV-L0 review items, reviewer provenance per VER-002-001 §5 (M-18).

### v0.5 — Pre-Ratification Self-Scan (Ratified-Baseline SAFE-053/054 Absorption)

* Pre-ratification self-scan (two-lens: self-gate conformance §30; CONST-015/SAFE-053 linkage) — C-1/M-1/M-2 applied; ratified-baseline SAFE-053/054 absorbed. All changes are narrow-only realignment to the Ratified RFC-001 v0.8 (RR-0003); no RFC-000 v0.16, RFC-001 v0.8, or GOV-001 v0.1 (all Ratified), vision, or philosophy text is changed.
* **C-1 (SAFE-053/054 absorption):** added two §5 Architecture Drivers rows — `Bounded human authority → SAFE-042, SAFE-046, SAFE-050, SAFE-053` and `Final-egress out-of-band containment → SAFE-054`; added §27 Requirements Traceability rows for SAFE-053 and SAFE-054 (§27 SAFE row count 34 → 36); and added the §10.8 SAFE-054 out-of-band containment mechanism in capability-neutral terms, preserving RFC-001 SAFE-054's defined-and-evidenced / accepted-residual-risk-with-reduced-scope branch structure. The M-06 owner attestation remains ARCHITECTURE-GATE-STATUS §4.5 and is referenced through SAFE-054, not restated.
* **M-1 (§19.4 authority-widening):** replaced the former §19.4 authority-increase sentence with a clause requiring independent approval satisfying the two-effective-principal requirement of RFC-001 SAFE-053 — satisfiable by the two-natural-person quorum or by the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1) — and added the same SAFE-053 linkage to the §9.1 "Change Runtime Safety Profile" and "Change Hard Safety Envelope" rows; RFC-000 CONST-015 is now cited explicitly in §19.4.
* **M-2 (§9.1 re-arm / promotion):** added "(two independent effective principals per RFC-001 SAFE-053 — quorum or ADR-002-015 §17.1 variant; see §20.1, §23.1)" to the §9.1 Re-arm and production-scope-promotion rows, consistent with the §20.1 table B restorative-edge owners.
* SAFE-053's two-satisfaction-path structure is preserved verbatim throughout; no absolute two-natural-person requirement is reintroduced (CR-02 / DR-0001). ADR-002-014's profile-commit/approval wording was checked against SAFE-053's two paths and judged consistent — it uses a generic approval "quorum" whose composition is deferred to ADR-002-015 (§26 Q3, §27 item 3), and effective-principal separation is carried by SPG-INV-010 — so no ADR-002-014 change was required.
* No new SAFE-xxx, no numeric bound, no broker proper noun; the Evidence Register counts are held (Part-1 372; development-track 98). Independent external EV-L0 review of v0.5 is requested in the git-excluded reviews/GEMINI-EVL0-REQUEST-0005.md; reviewer provenance per VER-002-001 §5 (M-18).

### v0.6 — External EV-L0 CRITICAL Closure (SAFE-053 variant-path legalization in the residual absolute prohibitions)

* The external independent EV-L0 review of v0.5 (owner-captured app UI model "Gemini 3.1 Pro", vendor Google; REQUEST-0005 package; GEMINI-EVL0-VERDICT-0005, 2026-07-18) returned **FAIL** with one **CRITICAL** finding: while the v0.5 §9.1 and §19.4 SAFE-053 absorption correctly carried both satisfaction paths (two-natural-person quorum **or** the ADR-002-015 §17.1 Governed Single-Operator Re-Arm Variant), four legacy absolute prohibitions were left un-updated — §10.18, §20.1 Table B (the LIVE_RESTRICTED → LIVE_NORMAL guard and owner), §20.1 Section C (forbidden re-arm edge), and §23.1 — so that a literal reading outlawed the SAFE-053 single-operator variant path entirely (a partial-update inconsistency that collapsed the newly absorbed SAFE-053 branch structure and conflicted with the Ratified RFC-001 v0.8).
* The finding was verified against source (all four sites confirmed) and applied narrow-only: each residual absolute prohibition now carries a strict conditional exception — permitted **only** through the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1) satisfying RFC-001 SAFE-053, with the variant's existing constraints (pre-declared exact scope, smallest approved scope delta binding, Hard Safety Envelope not expanded, Non-Waivable Boundary preserved — ADR-002-015 §17.1.5) carried in-clause or by adjacent reference. The §20.1 Table B owner cell — formerly a single-path quorum-only label — now reads "governed authority increase — two independent effective principals per RFC-001 SAFE-053 (quorum or ADR-002-015 §17.1 variant)". The quorum-path dual control is not weakened; the §23.1 clause additionally states that a service identity SHALL NOT use the variant, which is a human-authority path.
* Upstream synchronization: the same partial-update pattern was found at the source ADR-002-007 (§13, §14.1 item 3, REARM-AC-005) — a Wave-1 CR-02 propagation site that had been missed while ADR-002-025/026/027 received the recognition clause — and is corrected in ADR-002-007 v0.3 (Patch 0053) with the identical exception wording. The three NON-FINDINGS in VERDICT-0005 (§10.8 SAFE-054 branch preservation; §27/§30 traceability-matrix gate over SAFE-001..054; §12.1 orthogonal fail-closed UNKNOWN state) confirm the v0.5 pre-fixes pass.
* Narrow-only realignment to the Ratified RFC-001 v0.8; no RFC-000 v0.16, RFC-001 v0.8, or GOV-001 v0.1 (all Ratified), vision, or philosophy text is changed. SAFE-053's two-satisfaction-path structure is preserved and no absolute two-natural-person requirement is reintroduced (CR-02 / DR-0001); the variant's ADR-002-015 §17.1 constraints are preserved unchanged. No new SAFE-xxx, no numeric bound, no broker proper noun; the Evidence Register counts are held (Part-1 372; development-track 98). The v0.6 delta re-review is requested in the git-excluded reviews/GEMINI-EVL0-REQUEST-0006.md; reviewer provenance per VER-002-001 §5 (M-18).
