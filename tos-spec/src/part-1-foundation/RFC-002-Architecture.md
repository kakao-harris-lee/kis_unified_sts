# RFC-002 — Trading Operating System Architecture

**Document ID:** RFC-002
**Title:** Trading Operating System Architecture
**Version:** 0.2 Review Draft
**Status:** Review Draft — Architecture (v0.2 review-patch integrated)
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
* include confirmed positions;
* include potentially live orders;
* include partial fills;
* include trapped exposure;
* include committed capacity;
* include external activity;
* enforce the Hard Safety Envelope and Safety Profile;
* grant or deny exclusive risk-capacity commitment.

The Aggregate Risk Authority is the sole policy authority permitted to grant or deny aggregate risk allocation. The Risk Capacity Ledger is the sole serialization point and state-transition authority permitted to create, change, quarantine, transfer, or release a Capacity Commitment. Neither component may independently perform both policy approval and broker transmission.

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

### 10.8 Broker Adapter

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
- conformance of broker request to the authorized economic effect.

It SHALL reject the request when any required fact is missing, stale, conflicting, or unverifiable.

The Broker Adapter SHALL NOT expose a general-purpose live-order method to strategy, research, simulation, backtest, or operator-interface components.

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

---

### 10.17 Operator Control Interface

Responsibilities:

* expose current safety state;
* expose open and trapped exposure;
* expose unknown execution state;
* permit authenticated emergency commands;
* prevent silent live re-arming;
* preserve complete audit evidence.

---

## 11. Trading Action Pipeline

The logical action sequence SHALL be:

```text
Validated Context
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
Transmission
        ↓
Acknowledgement / Fill Processing
        ↓
Reconciliation
        ↓
Capacity Release or Adjustment
```

No stage SHALL be bypassed for an exposure-increasing action.

Protective actions SHALL follow the separate restrictions defined by ADR-002-001.

---

## 12. Intent Lifecycle

The minimum Intent lifecycle SHALL be:

```text
PROPOSED
    ↓
APPROVED
    ↓
CAPACITY_COMMITTED
    ↓
TRANSMISSION_AUTHORIZED
    ↓
TRANSMITTED
    ↓
ACTIVE
    ├── PARTIALLY_FILLED
    ├── FILLED
    ├── CANCEL_PENDING
    ├── CANCELLED
    ├── REJECTED
    └── UNKNOWN
            ↓
        RECONCILING
            ↓
        RECONCILED
```

### 12.1 UNKNOWN Is a First-Class State

`UNKNOWN` SHALL NOT be treated as:

* rejected;
* cancelled;
* unfilled;
* safe to retry;
* safe to release capacity.

Potentially live quantity SHALL remain reserved until reconciled.

### 12.2 State Transition Authority

Each state transition SHALL be attributable to:

* approved internal evidence;
* broker or venue evidence;
* reconciliation result;
* authorized operational action.

---

## 13. Order and Fill Integrity

### 13.1 At-Most-Authorized Exposure

One Intent MAY produce multiple technical messages, retries, or broker orders only when the aggregate potential exposure remains bounded by the approved Intent.

### 13.2 Partial Fills

Position and risk state SHALL update by confirmed fill quantity.

Submission quantity SHALL NOT be treated as filled quantity.

### 13.3 Cancel and Replace

A cancellation request SHALL NOT release risk capacity until cancellation or replacement state is reconciled.

### 13.4 Restart

After restart, potentially live orders SHALL remain potentially live until reconciled.

### 13.5 Over-Exit Prevention

Protective or exit retries SHALL use confirmed residual exposure and potentially live exit quantity.

The system SHALL NOT resubmit the original full exit quantity solely because a final acknowledgement is missing.

---

## 14. Aggregate Risk Capacity

### 14.1 Projected State

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

### 14.2 Exclusive Commitment

Risk capacity SHALL be committed before transmission.

Commitment SHALL be exclusive for the relevant capacity.

Two actions SHALL NOT consume the same available capacity.

### 14.3 Release Conditions

Capacity MAY be released only when:

* the action is definitively rejected before becoming live;
* cancellation is authoritatively confirmed;
* fill state has been incorporated;
* the Intent expires without transmission;
* reconciliation establishes that no exposure remains possible.

### 14.4 Crash Recovery

Risk-capacity commitments SHALL survive process restart or be reconstructed conservatively before trading resumes.

### 14.5 Trapped Exposure

Trapped exposure SHALL be treated as non-reducible.

No future exit assumption SHALL create additional risk authority.

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

### 17.2 Partition Behavior

Loss of verifiable control-plane authority SHALL revoke exposure-increasing execution.

Protective behavior under partition SHALL follow ADR-002-001.

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

Recovery SHALL require:

* valid Safety Profile;
* valid Hard Safety Envelope;
* trustworthy time;
* reconciled account state;
* resolved unknown orders;
* valid Safety Authority;
* valid live authorization;
* no blocking Critical hazard.

### 23.2 No Automatic Re-Arming

The system SHALL NOT automatically restore live autonomous authority merely because a failed dependency becomes available.

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

---

## 26. Architectural Decision Records

The following ADRs are initially required.

| ADR         | Subject                                                              | Status   |
| ----------- | -------------------------------------------------------------------- | -------- |
| ADR-002-001 | Degraded-Mode Protective Capacity                                    | Proposed |
| ADR-002-002 | Aggregate Risk-Capacity Commitment Model                             | Proposed |
| ADR-002-003 | Evidence-Based State Reconciliation and Confidence Model             | Required |
| ADR-002-004 | Safety Authority Validity, Epoch, and Partition Behavior             | Required |
| ADR-002-005 | Trustworthy Time Architecture                                        | Required |
| ADR-002-006 | Live and Non-Live Isolation                                          | Required |
| ADR-002-007 | Safety Configuration Activation                                      | Required |
| ADR-002-008 | Intent, Transmission Attempt, Broker Order, and Knowledge State Model | Required |
| ADR-002-009 | Broker Capability Requirements and Fallbacks                         | Required |
| ADR-002-010 | Live Authorization, Limit Governance, and Re-arm                     | Required |
| ADR-002-011 | Failure-Domain Isolation and Deployment Safety                       | Required |
| ADR-002-012 | Corporate Actions and Non-Trade State Changes                        | Required |
| ADR-002-013 | Protective Replacement and Protection-Gap Control                    | Required |

The subjects added by the v0.2 review patch that overlapped existing entries were merged into ADR-002-003/004/008 (title-refined) rather than duplicated; ADR-002-009 through ADR-002-013 are the genuinely new decisions.

---

## 27. Requirements Traceability Matrix

| RFC-001 requirement | Architectural responsibility                            |
| ------------------- | ------------------------------------------------------- |
| SAFE-001            | Safety Authority, Protective Action Controller          |
| SAFE-002            | Protective Action Controller, Position Projection       |
| SAFE-003            | Safety Profile Validator                                |
| SAFE-004            | Hard Safety Envelope Registry                           |
| SAFE-010            | Aggregate Risk Authority, Execution Coordinator         |
| SAFE-011            | Safety Control Plane                                    |
| SAFE-012            | Aggregate Risk Authority                                |
| SAFE-013            | Aggregate Risk Authority, Risk Capacity Ledger          |
| SAFE-014            | Execution Coordinator                                   |
| SAFE-015            | Risk Capacity Ledger                                    |
| SAFE-020            | Intent Registry                                         |
| SAFE-021            | Execution Coordinator, Intent Registry                  |
| SAFE-022            | Reconciliation Service                                  |
| SAFE-023            | Reconciliation Service                                  |
| SAFE-024            | Reconciliation Service                                  |
| SAFE-025            | Position and Order Projection                           |
| SAFE-030            | Context Integrity Service                               |
| SAFE-031            | Context Integrity Service                               |
| SAFE-032            | Context Integrity Service, Broker Adapter               |
| SAFE-033            | Independent Approval Service, Execution Coordinator     |
| SAFE-034            | Independent Approval Service                            |
| SAFE-035            | Trustworthy Time Service                                |
| SAFE-040            | Protective Action Controller                            |
| SAFE-041            | Safety Authority                                        |
| SAFE-042            | Operator Control Interface                              |
| SAFE-043            | Protective Action Controller                            |
| SAFE-044            | Recovery Coordinator                                    |
| SAFE-045            | Deployment and Identity Architecture                    |
| SAFE-046            | Live Authorization Service                              |
| SAFE-047            | Live Authorization Service                              |
| SAFE-048            | Safety Authority, Execution Coordinator                 |
| SAFE-050            | Hard Safety Envelope Registry, Safety Profile Validator |
| SAFE-051            | Evidence Store                                          |
| SAFE-052            | Replay and Evidence Services                            |

This matrix is an initial allocation and SHALL be refined as ADRs are accepted.

---

## 28. Open Architectural Decisions

The following questions remain open in v0.1.

1. What persistence model guarantees exclusive risk-capacity commitment?
2. How is Safety Authority validity represented and verified locally?
3. Which evidence paths are required for each broker?
4. How is partial-fill state persisted across restart?
5. How is time confidence established?
6. How are external manual trades detected within an approved bound?
7. How is the Hard Safety Envelope distributed and activated?
8. Which protective actions remain available during partition?
9. How are trapped positions represented in aggregate risk?
10. Which common-mode failures require physical component isolation?

Open decisions SHALL NOT be resolved by informal implementation convention.

---

## 29. Verification Obligations

RFC-002 SHALL eventually provide objective evidence that:

* concurrent authorizations cannot double-commit capacity;
* duplicate messages cannot multiply exposure;
* lost acknowledgements preserve potentially live state;
* partial fills preserve residual position;
* external activity revokes reconciled state;
* clock faults fail closed;
* control-plane partitions revoke new-risk authority;
* invalid Safety Profiles cannot expand authority;
* non-live environments cannot reach live endpoints;
* degraded protective capacity remains available;
* normal strategy traffic cannot consume reserved protection;
* recovery does not silently re-arm live operation.

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

## 31. Version 0.2 Review-Patch Amendments

The following subsections integrate the additive normative content of PATCH-RFC-002-v0.2 (Architecture Review Corrections).

### 31.1 New and Corrected Definitions

Add the following definitions to the RFC-002 terminology section.

#### 3.1 Aggregate Risk Decision

A policy decision that evaluates whether a proposed economic action may be allocated risk capacity under the current evidence, Hard Safety Envelope, Runtime Safety Profile, existing commitments, confirmed positions, potentially-live orders, UNKNOWN exposure, external/unattributed exposure, trapped exposure, and protective reserves.

An Aggregate Risk Decision does not itself mutate the Risk Capacity Ledger.

#### 3.2 Capacity Commitment

An atomic, exclusive, durable allocation of aggregate risk headroom to a uniquely identified economic action, reservation pool, or protective lease.

A commitment reduces capacity available to all other competing actions.

Only the authoritative Risk Capacity Ledger transition function may create, resize, quarantine, transfer, or release a Capacity Commitment.

#### 3.3 Protective Capacity Consumption

The binding of a portion of an already committed Reserved Protective Capacity pool to a specific protective action.

Protective Capacity Consumption:

- is not a new aggregate commitment;
- MUST remain within an existing protective lease or pre-committed pool;
- MUST be exclusive and durable;
- MUST NOT enlarge the aggregate authority granted by the original commitment;
- MUST fail closed when exclusivity, scope, epoch, or remaining capacity cannot be proven.

#### 3.4 Potentially-Live Quantity

The conservative upper bound of quantity that may still produce broker-side economic effect.

Potentially-Live Quantity includes, as applicable:

- transmitted quantity whose acceptance is not disproven;
- acknowledged but unfilled quantity;
- quantity under cancel-pending or replace-pending state;
- quantity associated with UNKNOWN transmission outcome;
- duplicate or overlapping attempts that cannot be proven deduplicated;
- late-fill exposure that remains possible under the broker capability profile.

Potentially-Live Quantity is not reduced merely because an acknowledgement timed out, a cancel request was accepted, an order was absent from one query, a process restarted, or a local authorization expired.

#### 3.5 Final Quantity Proof

Evidence sufficient, under the approved broker capability profile and reconciliation model, to establish both:

1. final cumulative filled quantity; and
2. zero remaining executable quantity.

A cancel acknowledgement alone is not Final Quantity Proof unless the broker capability profile proves that the acknowledgement is ordered after all possible fills and is complete for the relevant order identity.

#### 3.6 Authority Epoch

A monotonically increasing fencing value that identifies the current authority generation for a state-changing safety domain.

A stale epoch MUST NOT be accepted for:

- capacity commitment;
- capacity release;
- transmission permission;
- protective lease consumption;
- live authorization;
- safety authority grants.

#### 3.7 Transmission Capability

A single-use, scope-limited authorization presented to the final broker-egress enforcement point.

A Transmission Capability MUST be bound to at least:

- intent identity;
- reservation identity;
- account and instrument scope;
- maximum economic effect;
- authority epoch;
- live authorization identity;
- Hard Safety Envelope version;
- Runtime Safety Profile version;
- action class;
- one-time use identity.

#### 3.8 Trapped Exposure

Confirmed or conservatively inferred exposure that cannot currently be reduced within the approved liquidity, venue, price-limit, session, margin, or operational constraints.

Trapped Exposure MUST be treated as non-reducible when computing available capacity.

#### 3.9 Unattributed External Exposure

A broker-side order, fill, position, balance, margin, or instrument-identity change that cannot be attributed to an authorized TOS Intent, an authorized operator action, or a recognized non-trade event.

Unattributed External Exposure MUST consume conservative capacity and block new risk until disposition is complete.

### 31.2 Authority Ownership Matrix

Add the following matrix as the normative authority model.

| Action | Policy authority | State-transition / enforcement authority | Prohibited combinations |
|---|---|---|---|
| Propose trading action | Decision Service | None | Decision Service MUST NOT approve, commit, or transmit |
| Approve proposal | Independent Approval Service | None | Approval Service MUST NOT commit or transmit |
| Evaluate aggregate risk | Aggregate Risk Authority | None | Aggregate Risk Authority MUST NOT directly transmit |
| Commit normal risk capacity | Aggregate Risk Authority supplies a grant decision | Risk Capacity Ledger is the sole serialization and mutation authority | Execution Coordinator MUST NOT mutate capacity |
| Pre-commit protective pool | Aggregate Risk Authority supplies a grant decision | Risk Capacity Ledger commits the pool | Protective Action Controller MUST NOT enlarge the pool |
| Consume protective reserve | Protective Action Controller classifies and requests consumption within a valid lease | Protective sub-ledger or Risk Capacity Ledger transition function, as defined by ADR-002-002 | Strategy MUST NOT self-label an action as protective |
| Issue safety authority | Safety Authority | Final egress validates current epoch and scope | Safety Authority MUST NOT hold broker transmission credentials |
| Arm live scope | Live Authorization Service | Broker egress validates scope | Limit administrator MUST NOT also arm live scope |
| Change Runtime Safety Profile | Safety Profile governance authority | Safety Profile Validator activates only after validation | Live armer MUST NOT change limits |
| Change Hard Safety Envelope | Independent Hard Safety Envelope governance | Hard Safety Envelope Registry publishes immutable version | Runtime trading identity MUST NOT administer the envelope |
| Create transmission attempt | Execution Coordinator | Intent Registry and Risk Capacity Ledger bind attempt before send | Broker Adapter MUST NOT invent an unbound attempt |
| Transmit | Execution Coordinator requests | Broker Adapter / egress gateway is final enforcement point | No valid capability means no send |
| Retry | Execution Coordinator under broker capability rules | Broker Adapter enforces attempt identity and reservation | UNKNOWN outcome MUST NOT cause blind resubmission |
| Cancel ordinary order | Execution Coordinator requests | Cancellation Arbiter authorizes; Broker Adapter sends | Ordinary cancellation MUST NOT remove required protection |
| Cancel protective order | Protective Action Controller requests | Cancellation Arbiter authorizes; Broker Adapter sends | Strategy MUST NOT directly cancel safety-owned protection |
| Classify protective action | Protective Action Controller | Aggregate risk proof and protective rules enforce classification | Decision Service MUST NOT classify its own action as protective |
| Halt | Safety Authority or authenticated emergency operator | Egress deny gate applies monotonically | Halt MUST NOT depend on proposer availability |
| Re-arm | Recovery Coordinator verifies prerequisites; Live Authorization Service issues new authority; explicit human control approves | Broker egress accepts only new epoch/scope | Automatic re-arm is prohibited |
| Reconcile | Reconciliation Service evaluates evidence | Ledger transitions only through defined proof rules | Reconciliation Service MUST NOT arbitrarily release capacity |

#### 4.1 Capacity Authority Clarification

Replace any statement equivalent to:

> The Aggregate Risk Authority is the only component permitted to commit aggregate risk capacity.

with:

> The Aggregate Risk Authority is the sole policy authority permitted to grant or deny aggregate risk allocation. The Risk Capacity Ledger is the sole serialization point and state-transition authority permitted to create, change, quarantine, transfer, or release a Capacity Commitment. Neither component may independently perform both policy approval and broker transmission.

#### 4.2 Protective Partition Clarification

Add:

> During a Safety Control Plane partition, no new aggregate capacity may be committed. A Protective Action Controller may consume only capacity that was pre-committed to a valid, exclusive, scope-limited protective lease before the partition. Consumption must remain within the lease and must be serialized by the protective sub-ledger or equivalent mechanism defined by ADR-002-002. If exclusivity or current lease validity cannot be proven, no protective transmission is permitted.

### 31.3 Component Model Additions and Corrections

#### 5.5 Safety Profile Validator — New Component

Add a component named **Safety Profile Validator**.

Responsibilities:

- validate completeness, authenticity, version, account scope, instrument scope, units, multipliers, currencies, sign conventions, and temporal validity;
- validate all Runtime Safety Profile values against the independently governed Hard Safety Envelope;
- reject semantically implausible or internally inconsistent values;
- prevent partial activation;
- activate a profile atomically or leave the previous valid profile in force only where such continued use is explicitly authorized and time-valid;
- fail closed when correctness cannot be proven.

Trust boundary:

- it MUST be independent from strategy configuration;
- it MUST NOT expand the Hard Safety Envelope;
- the identity permitted to approve or publish a Runtime Safety Profile MUST NOT also arm live trading.

#### 5.6 Recovery Coordinator — New Component

Add a component named **Recovery Coordinator**.

Responsibilities:

- enforce the startup and recovery barrier;
- coordinate account-wide reconciliation of orders, fills, positions, cash, margin, capacity commitments, external activity, and recognized non-trade events;
- verify current authority epochs and trustworthy time;
- require UNKNOWN and unattributed activity to be resolved or conservatively reserved;
- verify ledger consistency and protective-order coverage;
- produce a recovery-readiness decision;
- request, but not issue, new live authorization.

The Recovery Coordinator SHALL NOT automatically re-arm live trading.

#### 5.7 Deployment and Identity Architecture — Explicit Responsibility Set

If retained as a traceability owner, define it as an explicit architecture responsibility set or component group.

It SHALL own:

- live/non-live credential segregation;
- workload identity;
- least-privilege broker credential access;
- deployment provenance;
- independent safety-component release controls;
- stale instance removal and fencing integration;
- prevention of research, simulation, paper, and backtest paths from reaching live broker egress.

#### 5.8 Replay and Evidence Service — Explicit Component

If referenced in traceability, define it explicitly.

It SHALL:

- retain immutable or tamper-evident evidence sufficient to reconstruct authority, reservation, attempt, broker event, reconciliation, and operator action timelines;
- support deterministic replay of architecture state transitions;
- preserve evidence provenance and failure-domain metadata;
- never substitute replay or audit for pre-trade prevention.

### 31.4 Orthogonal State Model Requirement

Add the following architectural rule.

The system SHALL NOT represent the entire trading lifecycle as a single order-status enumeration.

At minimum, the following state dimensions SHALL be modeled independently:

1. **Intent State** — proposal and business authorization lifecycle;
2. **Transmission Attempt State** — local send preparation and transport uncertainty;
3. **Broker Order State** — broker-side order lifecycle;
4. **Knowledge / Evidence State** — confidence, conflict, and reconciliation status;
5. **Capacity State** — reservation, potentially-live, consumed, quarantined, and released state.

A state such as `RECONCILED` belongs to the knowledge/evidence dimension, not the broker-order lifecycle.

The architecture SHALL support combinations such as:

```text
Transmission Attempt: SENT_UNCONFIRMED
Broker Order: UNKNOWN
Knowledge: CONFLICTED
Capacity: POTENTIALLY_LIVE
```

The detailed state machines are delegated to the Intent, Attempt, Order, and Knowledge State ADR. ADR-002-002 defines the capacity dimension and its coupling rules.

### 31.5 Capacity and Release Invariants

Add the following invariants.

#### 7.1 Aggregate Envelope Invariant

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

The Runtime Safety Profile may further restrict this bound but may never enlarge it.

#### 7.2 Commitment Mapping Invariant

Every potentially executable broker order SHALL map to exactly one active capacity commitment or to a specifically identified pre-committed protective lease consumption.

No active capacity commitment may be reused for another economic action.

#### 7.3 No Expiry of Economic Effect

Authority may expire. Potential economic effect does not expire until terminal quantity is proven.

A reservation may expire before transmission begins. Once an attempt may have reached the broker, the associated capacity SHALL remain committed, quarantined, or transferred to confirmed-position consumption until Final Quantity Proof exists.

#### 7.4 Cancellation Release Rule

Cancel acknowledgement alone SHALL NOT release capacity.

Release after cancellation requires Final Quantity Proof or a stronger broker-specific proof approved by the Broker Capability ADR.

#### 7.5 Replace Rule

Unless the broker capability profile proves atomic cancel/replace semantics, the capacity model SHALL reserve the worst credible overlap of the original and replacement orders.

#### 7.6 External and Non-Trade Changes

External activity and recognized non-trade changes SHALL enter the reconciliation model as first-class inputs.

The following SHALL NOT be assumed to be fills:

- corporate actions;
- symbol or instrument-identity changes;
- expiry, exercise, assignment, or rollover;
- broker administrative adjustments;
- account transfers;
- venue delisting or suspension changes.

Unrecognized changes are treated as unattributed external exposure.

### 31.6 Broker Capability Contract

Add an architectural dependency on a Broker Capability Profile.

No broker integration may be approved for live use without an explicit capability assessment covering at least:

- client-generated order identity support;
- duplicate-key and idempotency behavior;
- broker order-number issuance semantics;
- order-query completeness and pagination;
- cumulative fill query and replay;
- event ordering guarantees;
- cancel acknowledgement semantics;
- cancel/replace atomicity;
- reduce-only or equivalent position-side enforcement;
- account-wide order/fill/position visibility;
- push versus poll account events;
- rate-limit scope;
- session and credential concurrency;
- late-fill behavior;
- reconnect and recovery behavior.

Capability results SHALL be classified as:

```text
SUPPORTED
SUPPORTED_WITH_RESTRICTION
BEST_EFFORT
UNAVAILABLE
LIVE_SCOPE_PROHIBITED
```

Where a transmission outcome is UNKNOWN and broker-side deterministic deduplication is unavailable:

1. a new broker order SHALL NOT be blindly submitted;
2. all available broker evidence SHALL be queried;
3. the original reservation SHALL remain fully conservative;
4. unattributable activity SHALL force containment;
5. live scope SHALL be reduced if safe attribution cannot be achieved.

### 31.7 Partition and Trustworthy-Time Clarifications

#### 9.1 Normal Risk-Increasing Authority

Loss of verifiable current Safety Authority contact SHALL prevent new risk-increasing transmission.

A previously permissive authority grant SHALL NOT be reused indefinitely.

#### 9.2 Degraded Protective Authority

A degraded protective lease SHALL:

- be issued before the partition;
- be bound to an authority epoch;
- use a short bounded lifetime;
- be verifiable against local monotonic elapsed time;
- become invalid after process restart unless explicitly re-established;
- be invalid whenever remaining validity cannot be positively proven;
- limit account, instrument, action class, maximum quantity, and maximum risk-vector effect;
- be single-owner and protected from duplicate consumption.

Wall-clock deadline comparison alone is insufficient.

#### 9.3 Stale Instance Fencing

Leadership election alone is insufficient.

Every state-changing safety domain SHALL provide a fencing mechanism such that an old process that resumes after partition, pause, or failover cannot:

- commit or release capacity;
- issue accepted Safety Authority grants;
- consume an already reassigned protective lease;
- transmit through broker egress.

Detailed Safety Authority fencing is delegated to the Safety Authority Validity and Partition ADR. Capacity fencing is decided by ADR-002-002.

### 31.8 Protective Capacity Clarifications

Add or replace protective-capacity wording with the following.

#### 10.1 Guarantee Levels

Protective resources SHALL be classified by actual guarantee level:

```text
PHYSICALLY_RESERVED
LOGICALLY_RESERVED
PRIORITIZED_ONLY
BEST_EFFORT
UNAVAILABLE
```

Priority SHALL NOT be described as reservation.

#### 10.2 Common-Mode Disclosure

Where a broker exposes only one serialized session, one global account rate limit, or one shared credential path, protective API capacity may be only `PRIORITIZED_ONLY` or `BEST_EFFORT`.

Such limitations SHALL be recorded as residual risk and SHALL influence:

- normal traffic admission;
- earlier degraded-mode thresholds;
- maximum live scope;
- protective action assumptions;
- production acceptance.

#### 10.3 Intermediate-State Safety

A protective action is permitted in degraded mode only when conservative analysis proves that every credible partial-fill fraction and execution ordering remains within the Hard Safety Envelope and does not create a worse aggregate-risk state than taking no action.

If this cannot be proven, the action is treated as risk increasing.

#### 10.4 Protection Replacement Gap

When a broker cannot atomically replace a protective order:

- the position SHALL be treated as unprotected during the replacement gap;
- the gap SHALL be bounded and measured;
- replacement failure SHALL have a defined safe response;
- the broker-specific residual risk SHALL be approved;
- capacity calculation SHALL account for either overlap or protection absence.

#### 10.5 Protective Ownership and Cancellation

Every protective order SHALL carry an ownership classification:

```text
STRATEGY_OWNED
EXECUTION_OWNED
SAFETY_OWNED
OPERATOR_OWNED
```

A safety-owned protective order SHALL NOT be cancelled by ordinary strategy logic.

A single Cancellation Arbiter SHALL evaluate whether cancellation removes required protection. Protective evaluation precedes ordinary cancellation authority.

### 31.9 Reconciliation and Evidence Amendments

#### 11.1 No Single Unconditional Truth

Replace any unconditional statement that broker or venue records are absolute truth with:

> Broker and venue evidence is externally authoritative evidence but no single response is treated as unconditional truth. State is established through evidence consistency evaluation, source provenance, temporal ordering, and conservative bounds. Unresolved conflict produces UNKNOWN state and blocks new risk.

#### 11.2 Per-Field Confidence and Bounds

Reconciliation SHALL maintain confidence or conservative bounds separately for at least:

- order existence;
- broker order identity;
- cumulative filled quantity;
- remaining executable quantity;
- position quantity;
- cash and margin;
- protective coverage;
- instrument identity.

A single blended confidence score is insufficient for risk release.

#### 11.3 External-Activity Detection Bound

For broker integrations without real-time account events, the architecture SHALL define a measurable maximum external-activity detection bound.

Normal action size and aggregate headroom SHALL be constrained so that plausible external activity during the detection window cannot exceed the Hard Safety Envelope.

#### 11.4 Startup and Recovery Barrier

New risk SHALL remain blocked until the Recovery Coordinator verifies:

- open orders and potentially-live attempts;
- cumulative fills;
- positions;
- cash and margin;
- Risk Capacity Ledger state;
- protective-order coverage;
- external and unattributed activity;
- recognized non-trade changes;
- current authority epochs;
- trustworthy time;
- valid safety configuration.

### 31.10 Re-arm Governance

Add the following rule.

Automatic re-arm is prohibited.

Re-arm requires all of the following:

1. trustworthy time restored;
2. current Safety Authority epoch established;
3. account-wide reconciliation completed;
4. no unresolved UNKNOWN order unless fully conservatively reserved and explicitly accepted for restricted recovery;
5. no unresolved unattributed external activity;
6. Risk Capacity Ledger consistency verified;
7. Hard Safety Envelope and Runtime Safety Profile versions verified;
8. protective coverage evaluated;
9. Recovery Coordinator readiness decision;
10. new Live Authorization issued;
11. explicit human control according to the approved separation-of-duty policy.

The same human or service identity SHALL NOT both enlarge limits and arm live trading.

### 31.11 Failure-Domain Allocation Requirement

Add a mandatory Failure-Domain Allocation Matrix covering at least:

- process and runtime;
- pod and node;
- cluster and region;
- datastore;
- Kafka or equivalent event infrastructure;
- Redis or equivalent cache/stream infrastructure;
- network path;
- broker session;
- credential and workload identity;
- deployment pipeline;
- clock source;
- risk-calculation library;
- configuration parser and distribution path.

For each shared dependency, RFC-002 or a delegated ADR SHALL identify:

- affected authorities;
- failure consequence;
- containment behavior;
- whether the dependency is physically independent, logically independent, or common-mode;
- residual risk;
- verification method.

Logical service separation SHALL NOT be presented as proof of physical failure independence.

### 31.12 Verification and Acceptance Bound Requirements

Each Critical architecture property SHALL identify:

- triggering condition;
- detection bound;
- containment bound;
- responsible component;
- observable evidence;
- forbidden outcome;
- pass/fail criterion;
- fault-injection or replay scenario.

At minimum, the verification set SHALL include:

- duplicate active committer;
- stale capacity writer;
- stale Safety Authority;
- crash before send;
- crash after send;
- acknowledgement loss;
- partial fill;
- cancel crossing fill;
- replace crossing fill;
- late fill;
- process restart with live broker order;
- external HTS order;
- broker query omission;
- time-source loss during partition;
- protective reserve exhaustion;
- ordinary traffic blocking the protective path;
- corporate action or instrument-identity change.

Numeric values belong in an approved Safety Profile or Verification Specification, not necessarily in the architecture RFC, but the requirement to define and verify them is architectural.

### 31.13 Review Finding Disposition

| Finding | Disposition |
|---|---|
| A-01 split-brain double commitment | RFC patch + ADR-002-002 |
| A-02 stale Safety Authority | RFC patch + Safety Authority ADR |
| A-03 broker idempotency assumption | RFC patch + Broker Capability ADR |
| A-04 protective commit contradiction | RFC patch + ADR-002-001 patch + ADR-002-002 |
| A-05 cancel/fill release race | RFC invariant + ADR-002-002 |
| A-06 undefined components | Resolved in component additions |
| A-07 execution-side partition time | RFC rule + Trustworthy Time ADR |
| A-08 soft protective reserve | RFC classification + ADR-002-001 patch |
| A-09 protection replacement gap | RFC rule + ADR-002-001 patch |
| A-10 corporate actions | RFC input model + new ADR |
| A-11 external detection latency | RFC measurable bound + Broker/Reconciliation ADRs |
| A-12 unquantified containment | RFC verification obligation |
| A-13 split cancellation authority | Cancellation Arbiter rule |
| A-14 minor over-specification | Mode table retained; change governance delegated to ADR |

---

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
* Expanded the ADR backlog (ADR-002-009 through ADR-002-017) and set ADR-002-002 to Proposed.
* Resolves review findings A-01 through A-14.
