# RFC-001 — Safety Case

**Document ID:** RFC-001
**Document Type:** Safety Requirements Specification and Safety Case
**Title:** Trading Operating System Safety Case
**Version:** 0.7 Review Draft
**Status:** Review Draft — Not Ratified
**Classification:** Foundational Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-13
**Last Updated:** 2026-07-17
**Supersedes:** RFC-001 v0.5 Review Draft

---

## 1. Abstract

This document defines the Safety Case for the Trading Operating System (TOS).

RFC-000 defines the constitutional purpose, precedence, and immutable principles of the system. RFC-001 derives enforceable safety requirements from those constitutional requirements and defines:

* what SHALL NEVER happen;
* which hazards threaten capital, operational integrity, and survivability;
* which preventive, detective, containment, and recovery requirements control those hazards;
* which evidence SHALL be produced before real capital may be exposed;
* which unresolved obligations block progression to production operation.

This document does not claim that the TOS is safe merely because safety requirements have been written.

A safety claim is valid only when its corresponding requirement has objective evidence, has passed independent review, and has reached the `ACCEPTED` state defined in this document.

No production operation SHALL rely on an undemonstrated Critical safety requirement.

---

## 2. Authority and Conformance

This document is subordinate to RFC-000 and SHALL NOT reinterpret, weaken, bypass, or replace any constitutional requirement.

RFC-001 inherits constitutional precedence exclusively from RFC-000.

RFC-001 SHALL NOT introduce, extend, reorder, or reinterpret constitutional precedence.

Where two safety requirements appear to conflict:

1. the conflict SHALL be resolved using RFC-000;
2. the safer interpretation SHALL apply until the conflict is formally resolved;
3. the conflict SHALL be recorded as an unresolved safety obligation;
4. no implementation MAY use the ambiguity to increase operational authority.

Every architecture, implementation, operational procedure, and production deployment claiming conformance with RFC-001 SHALL:

1. identify the applicable `SAFE-xxx` requirements;
2. provide traceability from each requirement to implementation and verification evidence;
3. disclose every unmet requirement;
4. remain non-live while any blocking safety obligation is undemonstrated;
5. preserve the constitutional authority of RFC-000.

---

## 3. Scope

This Safety Case applies to every component and activity capable of influencing real-capital trading, including:

* decision generation;
* approval;
* risk evaluation;
* order construction;
* order transmission;
* order retry and recovery;
* execution and fill processing;
* position and open-order state;
* market, venue, account, and reference data;
* startup, restart, reconnection, and failover;
* safety configuration;
* live-mode authorization;
* human intervention;
* audit, replay, incident response, and recovery.

This Safety Case applies across:

* strategies;
* instruments;
* accounts;
* portfolios;
* brokers;
* execution venues;
* trading sessions;
* automated and human-initiated system actions.

### 3.1 Non-Goals

This document does not:

* guarantee that trading losses will never occur;
* define strategy profitability;
* define alpha-generation logic;
* define concrete numeric risk limits;
* prescribe a particular programming language, database, broker API, or deployment platform;
* guarantee execution when a venue is unavailable;
* treat audit or replay as a substitute for preventive controls.

Numeric thresholds, concrete mechanisms, component interfaces, and implementation designs SHALL be defined by subordinate specifications and approved safety configurations.

---

## 4. Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be interpreted as described in RFC 2119 and RFC 8174 when written in uppercase.

`SHALL NEVER` SHALL NOT be used as a separate normative keyword. Absolute prohibitions SHALL use `SHALL NOT`.

---

## 5. Definitions

### 5.1 Authoritative State

The state accepted by the TOS as the governing basis for positions, open orders, fills, balances, execution outcomes, and risk evaluation after available safety-relevant evidence has been reconciled.

No single internal or external source SHALL be treated as unconditionally correct when an error in that source could produce Critical or Catastrophic exposure.

Authoritative State SHALL be established using corroborating evidence appropriate to the operating environment.

Where available evidence is insufficient, inconsistent, or unresolved, the state SHALL remain unknown and the system SHALL enter the applicable Constitutional Safe State.

Concrete evidence sources and reconciliation mechanisms SHALL be defined by RFC-002.

### 5.2 Constitutional Safe State

An exposure-aware operational state in which:

* no new risk-increasing action is authorized;
* existing exposure is not abandoned;
* protective, risk-reducing, cancellation, reconciliation, or containment actions remain permitted or required;
* unknown exposure is treated conservatively;
* autonomous operation remains restricted until the triggering uncertainty is resolved.

The safe state SHALL NOT be interpreted as mere inactivity.

### 5.3 Critical Input

Any input whose corruption, absence, staleness, unit error, or inconsistency may alter:

* direction;
* instrument;
* quantity;
* price;
* exposure;
* risk;
* margin;
* account state;
* authorization;
* venue availability;
* execution behavior.

### 5.4 Degraded State

An operational condition in which one or more required capabilities or inputs are unavailable, unreliable, delayed, inconsistent, or operating outside approved bounds.

### 5.5 Demonstrated

A requirement state in which objective evidence shows that the requirement has been implemented and verified under its defined normal, boundary, failure, recovery, and restart scenarios.

### 5.6 Exposure-Increasing Action

Any action that may increase gross, net, directional, leveraged, margin, concentration, liquidity, overnight, or portfolio risk.

### 5.7 Exposure-Reducing Action

An action whose intended and bounded effect is to reduce existing risk without creating a larger or materially different risk elsewhere.

### 5.8 Fail-Closed

Behavior in which missing, invalid, unreadable, unverified, expired, or inconsistent safety information reduces operational authority rather than increasing it.

### 5.9 Live Mode

An explicitly authorized operational mode in which the system may transmit instructions capable of transferring real capital.

### 5.10 Non-Live Mode

Any research, replay, simulation, backtest, development, test, or paper-trading mode that SHALL NOT be capable of transmitting real-capital orders.

### 5.11 Operational Safety Limit

An approved, versioned, externally reviewable bound on trading authority, exposure, loss, order behavior, or operational activity.

### 5.12 Protective Control

An action or mechanism intended to contain, reduce, hedge, cancel, close, or otherwise manage existing exposure during normal or degraded operation.

### 5.13 Reconciled State

A state in which internal positions, open orders, fills, balances, and relevant broker or venue records have been compared and any material difference has been resolved or conservatively contained.

### 5.14 Safety Authority

An authority independent of strategy and decision generation that may deny, suspend, restrict, cancel, contain, or terminate autonomous trading activity.

### 5.15 Safety Evidence

Objective and reviewable proof that a safety requirement has been satisfied.

### 5.16 Safety Profile

The complete set of approved safety limits, permissions, operating modes, account constraints, instrument constraints, venue constraints, and escalation rules required to authorize live operation.

### 5.17 Trustworthy Context

Decision context that is complete, valid, sufficiently fresh, internally consistent, correctly typed and scaled, attributable to an approved source, and suitable for the intended decision.

### 5.18 Unknown Execution State

A state in which the system cannot determine with sufficient confidence whether an order was accepted, rejected, cancelled, partially filled, fully filled, or remains active.

### 5.19 Corroborating Evidence Path

A safety-relevant record or observation produced through a path sufficiently independent from another path that a single defect is not expected to corrupt both in the same manner.

Corroborating evidence may include, where available:

* outbound intent and transmission records;
* broker order acknowledgement;
* order-status query;
* fill or execution event;
* position query;
* balance or margin query;
* venue or clearing record;
* independently retained audit evidence.

RFC-001 does not require a specific external data product.

The required degree of independence SHALL be determined by hazard severity and documented residual risk.

### 5.20 Hard Safety Envelope

An independently governed upper boundary on operational authority that runtime Safety Profiles SHALL NOT exceed.

The Hard Safety Envelope SHALL be protected from modification by:

* strategy logic;
* model output;
* ordinary runtime configuration;
* live trading components acting unilaterally.

Changes to the Hard Safety Envelope SHALL require a separately governed approval and validation process.

### 5.21 Risk-Capacity Commitment

The exclusive allocation of a defined portion of available aggregate safety capacity to an authorized action or potentially live order.

Committed capacity SHALL be treated as unavailable to competing actions until it has been released, consumed, cancelled, expired, or reconciled.

### 5.22 Trustworthy Time Basis

A time basis whose ordering, progression, freshness interpretation, and authorization-expiry behavior are sufficiently validated for the safety decision being made.

A Trustworthy Time Basis SHALL support the safe evaluation of:

* input freshness;
* event ordering;
* session state;
* authorization validity;
* Safety Profile validity;
* timeout and recovery behavior.

When the time basis cannot be trusted, any authority depending on that time basis SHALL fail closed.

### 5.23 Unattributed External Activity

An order, cancellation, fill, position change, balance change, or margin change affecting a live account that cannot be traced to an approved TOS Intent.

Unattributed External Activity SHALL be treated as an operational-state divergence.

### 5.24 Trapped Exposure

Exposure that cannot currently be reduced with sufficient confidence because of:

* venue closure;
* trading halt;
* price-limit lock;
* insufficient liquidity;
* broker rejection;
* settlement restriction;
* instrument suspension;
* unavailable execution path;
* other confirmed execution constraints.

Trapped Exposure SHALL NOT be treated as immediately reducible when calculating available risk authority.

### 5.25 Protective Action

A bounded action whose demonstrated projected aggregate effect reduces constitutional risk while remaining inside every applicable safety boundary.

An action SHALL NOT be considered protective solely because it is described as a hedge, exit, stop, recovery, or emergency action.

Where its aggregate risk effect cannot be determined, it SHALL be classified as risk-increasing.

---

## 6. Safety Case Claim Structure

### SC-001 — Top-Level Safety Claim

The TOS MAY expose real capital only when all Critical safety requirements applicable to the intended operating scope are demonstrated, independently reviewed, accepted, and continuously monitored.

### SC-010 — Hazard Completeness Claim

All reasonably foreseeable single-defect and common operational failure paths — including authorized human and operator error and a defect or compromise of the final egress enforcement point — capable of causing catastrophic or critical capital impairment SHALL be identified, classified, and controlled.

### SC-020 — Pre-Trade Prevention Claim

No exposure-increasing action SHALL be transmitted unless preventive safety controls have approved the action before transmission.

### SC-030 — Execution Integrity Claim

Retries, reconnects, restarts, duplicated events, delayed acknowledgements, and ambiguous execution outcomes SHALL NOT multiply authorized exposure.

### SC-040 — State Integrity Claim

The system SHALL NOT authorize new exposure while position, open-order, account, configuration, venue, or critical-input state is unknown or unreconciled.

### SC-050 — Containment Claim

A defect in decision generation, strategy logic, or ordinary execution flow SHALL NOT disable the independent authority required to contain that defect.

A defect or compromise of the final egress enforcement point itself is outside the scope of this claim and is addressed by HAZ-025 and SAFE-054 (out-of-band containment of final egress).

### SC-060 — Operational Segregation Claim

Non-live activities SHALL NOT possess a path to real-capital execution.

### SC-070 — Evidence Claim

Every accepted safety claim SHALL be supported by traceable, repeatable, and reviewable evidence.

---

## 7. Safety Principles

### 7.1 Prevention Before Detection

Pre-trade prevention SHALL take precedence over post-trade detection.

Logging, replay, monitoring, and audit are necessary controls, but SHALL NOT be treated as substitutes for preventive authorization.

### 7.2 Exposure-Aware Failure Handling

Failure handling SHALL account for current positions, open orders, margin, venue state, and execution uncertainty.

Stopping signal generation alone SHALL NOT constitute a safe state.

### 7.3 Conservative Treatment of Uncertainty

Unknown or conflicting state SHALL be interpreted in the direction that grants less trading authority and assumes the greater credible exposure.

### 7.4 Aggregate Safety

Safety SHALL be evaluated at the highest operational scope affected by an action.

A strategy, instrument, venue, or subsystem SHALL NOT be considered safe solely because it remains within a local limit when the resulting aggregate account or portfolio state is unsafe.

### 7.5 Separation of Authority

The actor proposing a trade SHALL NOT possess unilateral authority to:

* approve the same trade;
* relax the applicable safety limits;
* arm live mode;
* disable safety containment;
* declare its own safety evidence accepted.

### 7.6 Non-Disableable Core Controls

Critical safety controls SHALL NOT be disabled by strategy configuration, ordinary application configuration, model output, or runtime optimization.

Any approved maintenance override SHALL be explicit, time-bounded, authenticated, audited, and incompatible with live autonomous trading unless separately ratified.

---

## 8. Hazard Classification

### 8.1 Severity

| Severity     | Definition                                                                                                                                 |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| CATASTROPHIC | May threaten account survival, cause liquidation, create unrecoverable capital impairment, or produce uncontrolled real-capital execution. |
| CRITICAL     | May create material uncontrolled exposure, major capital loss, or loss of containment requiring immediate shutdown.                        |
| MAJOR        | May cause bounded financial loss, incorrect decisions, prolonged outage, or material operational intervention.                             |
| MINOR        | Limited operational impact with no material threat to capital or containment.                                                              |

### 8.2 Acceptance Rules

1. A CATASTROPHIC hazard SHALL have at least one preventive control.
2. A CATASTROPHIC hazard SHALL NOT be accepted solely through monitoring, logging, replay, or human reaction.
3. A CRITICAL hazard SHALL have preventive or containment controls and objective verification evidence.
4. No unresolved CATASTROPHIC hazard is acceptable for live operation.
5. No undemonstrated Critical safety requirement is acceptable for live operation.
6. Residual risk SHALL be explicitly recorded and accepted by the ratifying authority.

---

## 9. Hazard Catalogue

### HAZ-001 — Permanent Capital Impairment

**Severity:** CATASTROPHIC

Capital is impaired beyond the system's approved recovery capability.

**Constitutional basis:** CONST-001, CONST-002
**Controlled by:** SAFE-010, SAFE-012, SAFE-013, SAFE-042

---

### HAZ-002 — Unbounded Loss or Exposure

**Severity:** CATASTROPHIC

Loss, exposure, leverage, margin usage, concentration, or order activity proceeds without an enforced bound.

**Constitutional basis:** CONST-006, CONST-009, CONST-010
**Controlled by:** SAFE-010, SAFE-011, SAFE-012, SAFE-013, SAFE-014

---

### HAZ-003 — Limit-Breaching Action

**Severity:** CATASTROPHIC

An action that would breach a safety limit is transmitted or executed before being rejected.

**Constitutional basis:** CONST-006, CONST-009, CONST-014
**Controlled by:** SAFE-010, SAFE-011, SAFE-012

---

### HAZ-004 — Duplicate Exposure

**Severity:** CATASTROPHIC

One authorized intent produces multiple exposure effects through retries, reconnects, restarts, duplicate events, or ambiguous acknowledgements.

**Constitutional basis:** CONST-001, CONST-002, CONST-009, CONST-014
**Controlled by:** SAFE-020, SAFE-021, SAFE-022

---

### HAZ-005 — Runaway Action Rate

**Severity:** CATASTROPHIC

A defect emits trading actions faster than safety controls, brokers, operators, or venues can contain.

**Constitutional basis:** CONST-001, CONST-006, CONST-011
**Controlled by:** SAFE-014, SAFE-042

---

### HAZ-006 — Trading on Untrustworthy Context

**Severity:** CATASTROPHIC

A decision or execution uses missing, stale, crossed, out-of-range, incorrectly scaled, misidentified, or internally inconsistent data.

**Constitutional basis:** CONST-004, CONST-005, CONST-009
**Controlled by:** SAFE-030, SAFE-031, SAFE-033

---

### HAZ-007 — Trading Into an Unavailable or Restricted Venue

**Severity:** CATASTROPHIC

An action assumes normal tradability while the venue, instrument, session, settlement process, margin regime, or execution path is restricted or unavailable.

**Constitutional basis:** CONST-007
**Controlled by:** SAFE-032, SAFE-043

---

### HAZ-008 — Unmanaged Exposure in a Degraded State

**Severity:** CATASTROPHIC

The system stops ordinary trading activity but abandons existing positions or protective obligations.

**Constitutional basis:** CONST-004, CONST-012
**Controlled by:** SAFE-002, SAFE-040, SAFE-043

---

### HAZ-009 — Trading Before Reconciliation

**Severity:** CATASTROPHIC

Trading resumes after startup, restart, disconnect, failover, or recovery before positions and open orders are reconciled.

**Constitutional basis:** CONST-008, CONST-013
**Controlled by:** SAFE-022, SAFE-044

---

### HAZ-010 — Loss of Containment Authority

**Severity:** CATASTROPHIC

A defect disables or bypasses the authority required to stop, contain, cancel, or restrict trading.

**Constitutional basis:** CONST-011
**Controlled by:** SAFE-041, SAFE-042, SAFE-050

---

### HAZ-011 — Fail-Open Safety Configuration

**Severity:** CATASTROPHIC

Missing, invalid, unreadable, unapproved, or unbounded configuration increases operational authority.

**Constitutional basis:** CONST-010
**Controlled by:** SAFE-003, SAFE-011, SAFE-050

---

### HAZ-012 — Live and Non-Live Crossover

**Severity:** CATASTROPHIC

Research, backtest, simulation, test, or paper-trading components transmit or influence real-capital orders.

**Constitutional basis:** CONST-001, CONST-002, CONST-009
**Controlled by:** SAFE-045, SAFE-046, SAFE-047

---

### HAZ-013 — Aggregate Risk Accumulation

**Severity:** CATASTROPHIC

Individually compliant actions combine into an unsafe account- or portfolio-level exposure.

**Constitutional basis:** CONST-001, CONST-002, CONST-006
**Controlled by:** SAFE-013

---

### HAZ-014 — Intent-to-Order Corruption

**Severity:** CATASTROPHIC

The transmitted order does not conform to the approved intent in instrument, direction, quantity, unit, account, price constraint, or execution authority.

**Constitutional basis:** CONST-005, CONST-009, CONST-014
**Controlled by:** SAFE-033, SAFE-034

---

### HAZ-015 — Audit Mistaken for Prevention

**Severity:** CRITICAL

A system is declared safe because an incident can be explained after execution, even though the action was not prevented.

**Constitutional basis:** CONST-009, CONST-014
**Controlled by:** SAFE-010, SAFE-051, SAFE-052

---

### HAZ-016 — Time-Source Corruption

**Severity:** CATASTROPHIC

A corrupted, stepped, drifting, stale, or otherwise untrustworthy time basis causes:

* stale data to appear fresh;
* expired authorization to appear valid;
* an invalid session state to appear tradable;
* event order to be misinterpreted;
* timeout or recovery behavior to become unsafe.

**Constitutional basis:** CONST-001, CONST-004, CONST-009, CONST-010, CONST-013
**Controlled by:** SAFE-035, SAFE-030, SAFE-044, SAFE-046, SAFE-050

---

### HAZ-017 — Authoritative-State Corruption

**Severity:** CATASTROPHIC

A single internal, broker, venue, or account-state source is wrong or incomplete and is nevertheless accepted as authoritative, causing incorrect exposure or risk decisions.

**Constitutional basis:** CONST-001, CONST-002, CONST-008, CONST-009
**Controlled by:** SAFE-023, SAFE-022, SAFE-024, SAFE-025

---

### HAZ-018 — Containment Isolation

**Severity:** CATASTROPHIC

The execution path loses verifiable contact with the Safety Authority but continues to create new exposure.

**Constitutional basis:** CONST-004, CONST-011, CONST-012
**Controlled by:** SAFE-041, SAFE-048

---

### HAZ-019 — Semantically Invalid Safety Profile

**Severity:** CATASTROPHIC

A Safety Profile is well-formed, readable, and approved but grants unsafe authority because of:

* unit error;
* scaling error;
* implausible value;
* incompatible limits;
* incorrect account or instrument scope;
* value exceeding the Hard Safety Envelope.

**Constitutional basis:** CONST-001, CONST-006, CONST-010
**Controlled by:** SAFE-003, SAFE-004, SAFE-012, SAFE-013, SAFE-050

---

### HAZ-020 — Concurrent Risk-Capacity Oversubscription

**Severity:** CATASTROPHIC

Two or more concurrent or retried actions are authorized against the same uncommitted aggregate risk capacity and jointly exceed the approved safety boundary.

**Constitutional basis:** CONST-001, CONST-002, CONST-006, CONST-009
**Controlled by:** SAFE-013, SAFE-015, SAFE-021

---

### HAZ-021 — Unattributed External Exposure

**Severity:** CATASTROPHIC

A manual trade, third-party system, broker-side action, corporate event, or other external activity changes the live account state without being attributed to an approved TOS Intent.

**Constitutional basis:** CONST-001, CONST-002, CONST-008, CONST-013
**Controlled by:** SAFE-023, SAFE-024, SAFE-044

---

### HAZ-022 — Partial-Fill State Corruption

**Severity:** CATASTROPHIC

A partially or asynchronously filled order is treated as:

* completely unfilled;
* completely filled;
* completely cancelled;
* fully protective;
* fully closed;

causing unmanaged residual exposure, duplicate execution, over-exit, or position reversal.

**Constitutional basis:** CONST-002, CONST-008, CONST-009, CONST-014
**Controlled by:** SAFE-021, SAFE-022, SAFE-025, SAFE-043, SAFE-051

---

### HAZ-023 — Trapped-Exposure Compounding

**Severity:** CATASTROPHIC

Exposure known to be non-reducible is treated as available risk capacity, allowing additional actions to compound the trapped risk.

**Constitutional basis:** CONST-001, CONST-002, CONST-006, CONST-007, CONST-012
**Controlled by:** SAFE-013, SAFE-032, SAFE-043

---

### HAZ-024 — Operator/Human Configuration or Authorization Error

**Severity:** CATASTROPHIC

An authenticated operator, acting within granted TOS authority, makes a safety-relevant mistake — selecting the wrong account, arming or re-arming an incorrect scope, approving an unintended action, or applying an incorrect safety configuration — creating unintended exposure or an unsafe authority state.

This hazard concerns erroneous action inside the operator's own authority and is distinct from HAZ-021, which concerns external or unattributed activity that cannot be traced to an approved TOS Intent.

**Constitutional basis:** CONST-001, CONST-011, CONST-015
**Controlled by:** SAFE-042, SAFE-046, SAFE-050, SAFE-053
**Architecture:** ADR-002-015 (human safety authority, dual control, and the Governed Single-Operator Re-Arm Variant)

---

### HAZ-025 — Defect or Compromise of the Final Egress Enforcement Point

**Severity:** CATASTROPHIC

The final egress enforcement point — the sole holder of usable live-order credentials and the broker-order route — is itself defective, misconfigured, or compromised, so that in-band safety enforcement at that point can no longer be relied upon to prevent unauthorized real-capital transmission.

This hazard concerns a defect in the enforcement point itself. It is distinct from HAZ-010 (a defect elsewhere disabling containment) and from defects in decision, strategy, or ordinary execution flow (SC-050), which assume the egress enforcement point remains intact.

**Constitutional basis:** CONST-009, CONST-011, CONST-014
**Controlled by:** SAFE-041, SAFE-048, SAFE-054
**Architecture:** RFC-002 §10.8; ADR-002-009, ADR-002-013 (egress credential, route, and failure-domain isolation)

---

## 10. Safety Requirements

### SAFE-001 — Default Safe State

**Priority:** Critical
**Type:** Preventive / Containment
**Derived from:** CONST-004, CONST-012

When critical uncertainty exists, the TOS SHALL enter the constitutional safe state.

The system SHALL NOT interpret the safe state as unconditional inactivity.

**Verification:**

* safe-state transition tests;
* open-position fault-injection scenarios;
* venue-unavailable scenarios;
* loss-of-data scenarios.

**Initial status:** SPECIFIED

---

### SAFE-002 — No Unmanaged Exposure

**Priority:** Critical
**Type:** Preventive / Containment
**Derived from:** CONST-004, CONST-012

Existing exposure SHALL remain subject to approved protective control during degraded or safe-state operation.

The system SHALL NOT create new exposure merely to preserve normal strategy behavior.

Where exit is unavailable, the system SHALL preserve the safest feasible containment behavior permitted by venue, account, and market constraints.

**Verification:**

* degraded-state position-management scenarios;
* locked-market and unavailable-exit simulation;
* protective-control continuity tests.

**Initial status:** SPECIFIED

---

### SAFE-003 — Fail-Closed Safety Profile

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-006, CONST-010

Live operation SHALL require a complete, valid, approved, and readable Safety Profile.

A missing, invalid, expired, unapproved, unreadable, or internally inconsistent Safety Profile SHALL result in zero authority to create new exposure.

The absence of a required limit SHALL be treated as the most restrictive limit.

A Safety Profile SHALL be validated for semantic plausibility, unit consistency, account and instrument scope, and conformance with SAFE-004.

A profile SHALL fail closed when it is:

* syntactically valid but semantically implausible;
* outside the Hard Safety Envelope;
* internally incompatible;
* activated only partially;
* associated with the wrong account, instrument, strategy, venue, or software version.

**Verification:**

* missing-configuration tests;
* malformed-value tests;
* stale-version tests;
* incomplete-profile tests;
* unauthorized-change tests.

**Initial status:** SPECIFIED

---

### SAFE-004 — Hard Safety Envelope

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-001, CONST-002, CONST-006, CONST-010

The TOS SHALL enforce a Hard Safety Envelope that establishes the maximum operational authority that any runtime Safety Profile may grant.

A runtime Safety Profile SHALL NOT:

* exceed the Hard Safety Envelope;
* redefine the envelope;
* disable the envelope;
* treat an unavailable envelope as unlimited authority.

The Hard Safety Envelope SHALL constrain every configurable safety value whose incorrect expansion could threaten constitutional survivability.

A Safety Profile that exceeds, contradicts, or cannot be validated against the Hard Safety Envelope SHALL fail closed.

### Acceptance Conditions

**Trigger:** A Safety Profile is loaded, changed, activated, or used for authorization.

**Expected result:** Every applicable profile value is validated against the Hard Safety Envelope before live authority is granted.

**Forbidden outcome:** A profile outside the envelope becomes active or authorizes an exposure-increasing action.

**Pass rule:** No tested unit, scaling, scope, boundary, or mutation error may grant authority above the Hard Safety Envelope.

**Initial status:** SPECIFIED

---

### SAFE-010 — Pre-Trade Safety Authorization

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-006, CONST-009, CONST-014

Every exposure-increasing action SHALL pass all applicable safety checks before transmission.

An action SHALL NOT be authorized if its projected post-action state would violate any applicable safety limit.

Post-trade detection SHALL NOT substitute for pre-trade authorization.

**Verification:**

* boundary-value tests;
* projected-state validation;
* negative authorization tests;
* bypass attempts;
* order-path integration tests.

**Initial status:** SPECIFIED

---

### SAFE-011 — Non-Bypassable Safety Limits

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-006, CONST-010, CONST-011

Critical safety limits SHALL be enforced independently of strategy and decision generation.

No strategy, model, ordinary runtime configuration, or performance optimization SHALL relax or disable a Critical safety limit.

**Verification:**

* strategy-bypass tests;
* configuration-override tests;
* privilege tests;
* failure-injection tests.

**Initial status:** SPECIFIED

---

### SAFE-012 — Bounded Single-Action Risk

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-001, CONST-002, CONST-006, CONST-009

The maximum credible capital effect of any single authorized action SHALL be bounded such that the action alone cannot threaten constitutional survivability.

This bound SHALL apply to quantity, notional exposure, leverage, margin effect, concentration, and worst credible execution effect.

The single-action bound SHALL NOT depend solely on a runtime-configurable value.

It SHALL remain constrained by SAFE-004 and by independently approved worst-case assumptions covering:

* unit and multiplier error;
* price and slippage uncertainty;
* leverage and margin effect;
* potentially live orders;
* partial and asynchronous fills.

For the purpose of this requirement, "maximum credible capital effect" means the maximum effect established by approved worst-case assumptions and bounded by the Hard Safety Envelope.

**Verification:**

* fat-finger scenarios;
* sign inversion tests;
* unit conversion tests;
* quantity multiplier tests;
* worst-price and slippage-bound tests.

**Initial status:** SPECIFIED

---

### SAFE-013 — Aggregate Risk Authority

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-001, CONST-002, CONST-006

Safety limits SHALL be evaluated at the aggregate account and portfolio scope across all strategies, instruments, positions, open orders, and venues affected by the action.

Local compliance SHALL NOT override an unsafe aggregate state.

Aggregate risk evaluation SHALL include:

* confirmed positions;
* potentially live orders;
* partial fills;
* committed risk capacity;
* unattributed external activity;
* trapped exposure;
* margin and collateral obligations;
* concurrent authorizations.

Trapped Exposure SHALL be treated as non-reducible when calculating available authority unless its reduction has been authoritatively confirmed.

Aggregate headroom SHALL NOT be used until it has been exclusively committed under SAFE-015.

**Verification:**

* multi-strategy accumulation tests;
* cross-instrument exposure tests;
* hedge interaction tests;
* open-order reservation tests;
* portfolio-level projected-state tests.

**Initial status:** SPECIFIED

---

### SAFE-014 — Bounded Action Rate

**Priority:** Critical
**Type:** Preventive / Containment
**Derived from:** CONST-001, CONST-006, CONST-011

The number and rate of order-generating, cancelling, replacing, and retrying actions SHALL be bounded.

A runaway loop SHALL NOT be capable of emitting unbounded trading activity.

Rate-bound violations SHALL invoke containment independently of strategy behavior.

**Verification:**

* retry-storm tests;
* event-loop duplication tests;
* reconnect flood tests;
* cancellation/replacement storm tests.

**Initial status:** SPECIFIED

---

### SAFE-015 — Exclusive Risk-Capacity Commitment

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-001, CONST-002, CONST-006, CONST-009

Aggregate risk capacity SHALL be committed exclusively before an exposure-increasing action is transmitted.

Authorization and risk-capacity commitment SHALL behave as one indivisible safety decision from the perspective of concurrent, retried, and competing actions.

The same unit of available safety capacity SHALL NOT be committed to more than one potentially live action.

Where exclusive commitment cannot be established or its state is uncertain:

* the action SHALL NOT create new exposure;
* committed and potentially committed capacity SHALL be reconciled before authority is restored.

### Acceptance Conditions

**Trigger:** Two or more actions compete for overlapping aggregate risk capacity.

**Expected result:** At most the available capacity is committed.

**Forbidden outcome:** Concurrent actions jointly commit or create exposure above the aggregate boundary.

**Pass rule:** All concurrency, retry, timeout, duplicate-event, and restart scenarios preserve the aggregate safety limit.

**Initial status:** SPECIFIED

---

### SAFE-020 — Immutable Intent Identity

**Priority:** Critical
**Type:** Preventive / Detective
**Derived from:** CONST-005, CONST-009, CONST-014

Every approved trading intent SHALL possess a globally unique, immutable identity.

All orders, replacements, cancellations, acknowledgements, fills, retries, and recovery actions SHALL remain traceable to that intent.

**Verification:**

* identifier uniqueness tests;
* restart persistence tests;
* duplicate-event tests;
* end-to-end traceability tests.

**Initial status:** SPECIFIED

---

### SAFE-021 — At-Most-One Exposure Effect

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-001, CONST-002, CONST-009, CONST-014

Retries, reconnects, restarts, duplicate events, and ambiguous acknowledgements SHALL NOT create aggregate exposure greater than the exposure authorized by the originating intent.

The system SHALL NOT assume that a missing acknowledgement means that an order was not accepted.

**Verification:**

* lost-acknowledgement scenarios;
* duplicate-submission tests;
* crash-after-send tests;
* timeout and retry tests;
* partial-fill retry tests.

**Initial status:** SPECIFIED

---

### SAFE-022 — Reconciliation Before Exposure

**Priority:** Critical
**Type:** Preventive / Recovery
**Derived from:** CONST-008, CONST-013

After startup, restart, reconnect, failover, execution timeout, or unknown execution state, the TOS SHALL withhold new exposure until authoritative position and open-order state are reconciled.

Unknown in-flight orders SHALL be treated as potentially live.

Reconciliation SHALL establish Authoritative State in accordance with SAFE-023.

An unresolved disagreement between evidence paths SHALL preserve unknown state.

Unknown state SHALL NOT be converted into new exposure authority by selecting the most convenient source.

**Verification:**

* crash recovery tests;
* stale-cache tests;
* unknown-order tests;
* broker mismatch tests;
* partial-fill recovery tests.

**Initial status:** SPECIFIED

---

### SAFE-023 — Evidence-Based State Validation

**Priority:** Critical
**Type:** Preventive / Detective
**Derived from:** CONST-001, CONST-008, CONST-009, CONST-013

Safety-critical account and execution state SHALL be accepted as Authoritative State only after available corroborating evidence has been evaluated.

No single source SHALL be treated as unconditionally correct where a single-source error could cause Critical or Catastrophic exposure.

Where independent corroboration is unavailable, the dependency and residual risk SHALL be explicitly recorded, independently accepted, and constrained by conservative operating authority.

Unresolved disagreement, missing evidence, or insufficient confidence SHALL result in unknown state and prohibit new risk-increasing exposure.

### Acceptance Conditions

**Trigger:** Safety-relevant evidence sources disagree, disappear, or produce implausible state.

**Expected result:** The state remains unknown, reconciliation is initiated, and new risk is blocked.

**Forbidden outcome:** One disputed source silently becomes authoritative and permits new exposure.

**Pass rule:** Injected corruption of any single evidence path SHALL NOT cause an unsafe state to be accepted as reconciled.

**Initial status:** SPECIFIED

---

### SAFE-024 — Continuous External-State Reconciliation

**Priority:** Critical
**Type:** Preventive / Detective / Recovery
**Derived from:** CONST-008, CONST-013

During live operation, the TOS SHALL detect safety-relevant account changes that cannot be attributed to an approved TOS Intent.

Unattributed External Activity SHALL:

* invalidate the current reconciled-state claim;
* suspend new risk-increasing authority;
* trigger reconciliation;
* remain visible until resolved or explicitly accepted as residual risk.

This obligation applies continuously during live operation, not only during startup or reconnect.

### Acceptance Conditions

**Trigger:** A live account order, fill, position, balance, or margin change appears without a matching approved Intent.

**Expected result:** The system enters the applicable safe state and begins reconciliation.

**Forbidden outcome:** Autonomous exposure continues using the pre-change cached aggregate state.

**Pass rule:** Tested external account changes are detected within the approved detection bound and no new risk is authorized before reconciliation.

**Initial status:** SPECIFIED

---

### SAFE-025 — Partial and Asynchronous Fill Integrity

**Priority:** Critical
**Type:** Preventive / Detective / Recovery
**Derived from:** CONST-002, CONST-008, CONST-009, CONST-014

Position, open-order, protective-order, and available-risk state SHALL reflect confirmed partial and asynchronous fills.

The TOS SHALL NOT infer that an order is:

* unfilled because no acknowledgement was received;
* fully filled because it was submitted;
* cancelled because cancellation was requested;
* fully protective because the requested quantity equals the intended exposure;
* fully closed before the residual position is authoritatively confirmed.

Further actions SHALL be based on:

* confirmed filled quantity;
* confirmed remaining executable quantity;
* potentially live quantity;
* authoritative residual exposure.

Unknown remaining quantity SHALL be treated conservatively as potentially live.

### Acceptance Conditions

**Trigger:** An entry, exit, hedge, cancellation, or replacement is partially filled or its final state is delayed.

**Expected result:** Residual position and potentially live order quantity remain represented accurately.

**Forbidden outcome:** Residual exposure is lost, duplicated, over-exited, or reversed because submission state was mistaken for execution state.

**Pass rule:** Partial-fill, delayed-fill, cancel-race, replacement-race, restart, and replay tests preserve authoritative residual exposure.

**Initial status:** SPECIFIED

---

### SAFE-030 — Trustworthy Context Precondition

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-004, CONST-005, CONST-009

No decision, approval, sizing calculation, or execution SHALL rely on Critical Input that is not trustworthy.

Completeness alone SHALL NOT establish trustworthiness.

Suspect Critical Input SHALL force the constitutional safe state or a defined degraded behavior that cannot increase exposure.

Any time-dependent Critical Input SHALL also satisfy SAFE-035.

Freshness SHALL be evaluated against an approved, measurable bound and a Trustworthy Time Basis.

The phrase "sufficiently fresh" SHALL NOT be considered verifiable without:

* a defined freshness parameter;
* its approved source;
* a pass/fail rule;
* a validated time basis.

**Verification:**

* stale-data tests;
* zero and negative-price tests;
* crossed-market tests;
* outlier tests;
* unit and scale tests;
* timestamp-ordering tests;
* source disagreement tests.

**Initial status:** SPECIFIED

---

### SAFE-031 — Critical Input Provenance

**Priority:** Critical
**Type:** Preventive / Detective
**Derived from:** CONST-005, CONST-009

Every Critical Input SHALL be attributable to an approved source, timestamp, unit, instrument, account, and processing version.

An unidentifiable or ambiguously mapped Critical Input SHALL NOT authorize exposure.

**Verification:**

* symbol mapping tests;
* unit metadata tests;
* timestamp provenance tests;
* account mapping tests;
* source substitution tests.

**Initial status:** SPECIFIED

---

### SAFE-032 — Venue and Tradability Gate

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-007

Every proposed action SHALL be evaluated against current venue, instrument, session, tradability, halt, price-limit, settlement, margin, and execution constraints applicable to that action.

The system SHALL NOT assume that a requested exit is executable.

**Verification:**

* closed-session tests;
* halt and suspension tests;
* price-limit scenarios;
* order-type restriction tests;
* margin and settlement restriction tests.

**Initial status:** SPECIFIED

---

### SAFE-033 — Intent-to-Order Conformance

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-005, CONST-009, CONST-014

Before transmission, every order SHALL be proven to conform to its approved intent in:

* account;
* instrument;
* contract or symbol;
* direction;
* quantity;
* unit;
* price and order constraints;
* exposure effect;
* expiration;
* operating mode.

Any mismatch SHALL cause rejection.

**Verification:**

* sign inversion tests;
* symbol substitution tests;
* multiplier and unit tests;
* account-routing tests;
* quantity mutation tests.

**Initial status:** SPECIFIED

---

### SAFE-034 — Independent Approval Inputs

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-005, CONST-009

Approval SHALL independently validate the safety-critical facts required to authorize an action.

Approval SHALL NOT rely solely on an unvalidated value produced by the proposing component.

Where independent corroboration cannot be provided, the limitation SHALL be independently reviewed and recorded as residual risk. Approval SHALL apply a documented combination of freshness, rate-of-change, range, cross-field, provenance, state, and last-known-good consistency checks. The component proposing the action SHALL NOT unilaterally declare independent corroboration infeasible.

A plausible but incorrect value SHALL remain within the scope of common-mode failure analysis.

**Verification:**

* common-mode corrupt-input tests;
* independent recomputation tests;
* sanity-bound tests;
* source disagreement tests.

**Initial status:** SPECIFIED

---

### SAFE-035 — Trustworthy Time Basis

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-004, CONST-009, CONST-010, CONST-013

Time SHALL be treated as a Critical Input whenever it affects:

* data freshness;
* event ordering;
* venue or session state;
* authorization validity;
* configuration validity;
* timeout behavior;
* recovery behavior.

The TOS SHALL NOT authorize new risk when the time basis required for the decision cannot be trusted.

Time-dependent authority SHALL fail closed when:

* time progression is inconsistent;
* ordering cannot be established;
* freshness cannot be determined;
* expiry cannot be verified;
* clock confidence falls outside the approved safety bound.

RFC-002 SHALL define the mechanism used to establish and monitor the Trustworthy Time Basis.

### Acceptance Conditions

**Trigger:** Clock step, drift, freeze, rollback, disagreement, or unavailable reference.

**Expected result:** Affected time-dependent authority is withdrawn and the applicable safe state is entered.

**Forbidden outcome:** Stale data, expired live authority, or expired configuration is treated as valid.

**Pass rule:** Every injected time fault fails closed before it can authorize a risk-increasing action.

**Initial status:** SPECIFIED

---

### SAFE-040 — Protective Control in Degraded Operation

**Priority:** Critical
**Type:** Containment / Recovery
**Derived from:** CONST-004, CONST-012

When ordinary decision or execution capability degrades, approved protective controls for existing exposure SHALL remain available to the greatest feasible extent.

A degraded subsystem SHALL NOT silently convert managed exposure into unmanaged exposure.

**Verification:**

* data-feed failure tests;
* decision-engine failure tests;
* partial broker outage tests;
* protection-path availability tests.

**Initial status:** SPECIFIED

---

### SAFE-041 — Independent Safety Authority

**Priority:** Critical
**Type:** Containment
**Derived from:** CONST-011

The TOS SHALL maintain a Safety Authority logically independent of strategy and decision generation.

The Safety Authority SHALL be able to deny new exposure, suspend autonomous trading, and initiate approved containment actions.

A defect in the proposing component SHALL NOT disable its own containment.

Logical independence alone SHALL NOT establish effective containment.

The authority required by SAFE-041 SHALL remain effective under the communication-loss behavior defined by SAFE-048.

**Verification:**

* decision-engine failure tests;
* strategy-bypass tests;
* authority isolation tests;
* permission tests;
* forced-halt tests.

**Initial status:** SPECIFIED

---

### SAFE-042 — Human Emergency Authority

**Priority:** Critical
**Type:** Containment / Recovery
**Derived from:** CONST-011, CONST-012, CONST-015

An authenticated human operator SHALL retain the authority to suspend autonomous trading and invoke approved emergency containment.

This authority SHALL remain available independently of normal strategy operation.

Emergency actions SHALL be audited and SHALL NOT silently re-arm autonomous trading.

**Verification:**

* manual halt tests;
* authorization tests;
* normal-component outage tests;
* re-arming prevention tests.

**Initial status:** SPECIFIED

---

### SAFE-043 — Exit-Unavailable Containment

**Priority:** Critical
**Type:** Containment
**Derived from:** CONST-007, CONST-012

The Safety Case SHALL assume that closing an existing position may be temporarily or structurally impossible.

When an exit cannot be executed, the system SHALL:

* prohibit risk-increasing actions;
* preserve authoritative awareness of the trapped exposure;
* continue approved protective and notification obligations;
* avoid reporting the exposure as safely closed;
* escalate according to the approved Safety Profile.

A proposed hedge, exit, or protective action SHALL be classified according to the projected aggregate-risk interpretation established by RFC-000.

Trapped Exposure SHALL remain fully represented and SHALL reduce available aggregate risk authority.

An unconfirmed exit SHALL NOT be treated as completed risk reduction.

**Verification:**

* locked-market tests;
* trading-halt tests;
* broker rejection tests;
* unavailable-order-type tests;
* delayed-reopen tests.

**Initial status:** SPECIFIED

---

### SAFE-044 — Safe Start and Resume

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-008, CONST-013

Live autonomous trading SHALL begin or resume only after:

* safety configuration is validated;
* live authorization is confirmed;
* authoritative positions and open orders are reconciled;
* Critical Inputs are trustworthy;
* venue and account state are usable;
* no blocking safety obligation remains.

The prerequisites for live operation SHALL remain continuously valid.

Loss of:

* reconciled state;
* trustworthy time;
* valid Safety Profile;
* valid live authority;
* attributable account state;
* verifiable Safety Authority contact;

SHALL revoke new risk-increasing authority.

**Verification:**

* cold-start tests;
* warm-restart tests;
* reconnect tests;
* incomplete-startup tests;
* stale-token and expired-session tests.

**Initial status:** SPECIFIED

---

### SAFE-045 — Live and Non-Live Segregation

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-001, CONST-002, CONST-009

Non-live components SHALL NOT possess credentials, permissions, routes, or interfaces capable of transmitting live orders.

Research, backtest, simulation, development, test, and paper-trading activity SHALL remain segregated from real-capital execution.

**Verification:**

* credential-scope tests;
* network-route tests;
* environment-isolation tests;
* attempted cross-mode transmission tests.

**Initial status:** SPECIFIED

---

### SAFE-046 — Explicit Live Arming

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-001, CONST-009, CONST-013, CONST-015

The default operating state SHALL be non-live.

Live operation SHALL require explicit, positive, authenticated, revocable, and time-bounded authorization for a defined:

* account;
* strategy set;
* instrument set;
* venue set;
* safety profile;
* software version;
* operating interval.

**Verification:**

* default-state tests;
* expired-authorization tests;
* wrong-account tests;
* wrong-version tests;
* revocation tests.

**Initial status:** SPECIFIED

---

### SAFE-047 — Production Scope Confinement

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-001, CONST-002, CONST-006

A live authorization SHALL grant no more authority than its explicitly approved scope.

Any action outside the approved production scope SHALL be rejected.

**Verification:**

* unauthorized-instrument tests;
* unauthorized-strategy tests;
* account-scope tests;
* session-scope tests;
* expired-scope tests.

**Initial status:** SPECIFIED

---

### SAFE-048 — Partition-Tolerant Safety Authority

**Priority:** Critical
**Type:** Preventive / Containment
**Derived from:** CONST-004, CONST-011, CONST-012

The execution path SHALL possess current and verifiable safety authority before creating new exposure.

Loss, expiry, or unverifiability of communication with the Safety Authority SHALL revoke authority to create new risk.

The execution path SHALL NOT continue exposure-increasing activity solely because its last known safety state was permissive.

Loss of safety-authority contact SHALL NOT automatically prohibit bounded protective actions that:

* were explicitly authorized for degraded operation;
* satisfy the Constitutional Safe State;
* reduce projected aggregate constitutional risk;
* remain within every applicable safety boundary.

RFC-002 SHALL define the communication, authority-validity, and failure-detection mechanism.

### Acceptance Conditions

**Trigger:** Communication partition, delayed authority message, stale authority, or Safety Authority outage.

**Expected result:** New risk creation stops within the approved containment bound.

**Forbidden outcome:** The execution path continues using stale permissive authority.

**Pass rule:** Partition and stale-authority tests prevent all new risk-increasing actions while preserving only explicitly authorized protective behavior.

**Initial status:** SPECIFIED

---

### SAFE-050 — Safety Configuration Governance

**Priority:** Critical
**Type:** Preventive / Detective
**Derived from:** CONST-006, CONST-010, CONST-011

Critical safety configuration SHALL be versioned, authenticated, reviewable, attributable, and protected from unilateral modification by a trading strategy.

Changes that increase operational authority SHALL require explicit approval and SHALL NOT take effect silently during live operation.

Safety configuration activation SHALL be complete and internally consistent from the perspective of safety authorization.

A partially applied configuration SHALL fail closed.

Changes that increase authority SHALL be validated against SAFE-004 before activation.

**Verification:**

* unauthorized-change tests;
* signature or integrity tests;
* version rollback tests;
* live-change tests;
* audit review.

**Initial status:** SPECIFIED

---

### SAFE-051 — Decision and Execution Evidence

**Priority:** High
**Type:** Detective
**Derived from:** CONST-005, CONST-009, CONST-014

Every proposed, approved, rejected, transmitted, acknowledged, filled, cancelled, and recovered action SHALL produce traceable evidence.

Evidence SHALL include the originating intent, applicable context, approval result, safety profile, order identity, execution outcome, and resulting position state.

**Verification:**

* end-to-end evidence completeness tests;
* rejection-path tests;
* partial-fill tests;
* restart continuity tests.

**Initial status:** SPECIFIED

---

### SAFE-052 — Replay and Incident Reconstruction

**Priority:** High
**Type:** Detective / Recovery
**Derived from:** CONST-014

The TOS SHALL retain sufficient evidence to reconstruct the decision and execution chain of every live action.

Replay SHALL reproduce the safety-relevant decision outcome from the recorded inputs and approved configuration version, subject to documented deterministic boundaries.

Replay SHALL NOT be treated as proof that preventive controls are adequate.

**Verification:**

* recorded-event replay tests;
* configuration-version replay tests;
* deterministic decision comparison;
* incident reconstruction exercises.

**Initial status:** SPECIFIED

---

### SAFE-053 — Independent Approval of Risk-Increasing Re-Arm and Scope Promotion

**Priority:** Critical
**Type:** Preventive
**Derived from:** CONST-005, CONST-011, CONST-013, CONST-015

Every risk-increasing live re-arm, Live Authorization issuance, and
production-scope promotion SHALL require the independent approval of at least
two distinct effective principals. An effective principal is the equivalence
class of all identities, credentials, devices, sessions, service identities, and
administrative control paths under one controller.

The two-independent-effective-principal requirement MAY be satisfied by either:

* a quorum of at least two distinct authenticated natural persons; or
* an approved Governed Single-Operator Re-Arm Variant defined by ADR-002-015, in
  which a time-separated, re-authenticated single-operator path, an independent
  non-authorizing attestation, and — where available — an external independent
  reviewer recognized as a second effective principal together satisfy the
  independence requirement for a reduced, explicitly bound scope.

Under satisfaction path (ii), where no external independent reviewer is
available, the variant's time-separation and independent attestation substitute
for the second effective principal's provenance rather than adding a second
natural person; the substitution is confined to a reduced scope and never lowers
a gate.

The satisfaction path SHALL be fixed in advance by approved policy and bound
into the approval scope. It SHALL NOT be selected, changed, or invented at the
time of re-arm.

Neither satisfaction path may waive a non-waivable safety boundary, widen
emergency (break-glass) authority, expand the Hard Safety Envelope, or lower any
other required safety, capacity, currentness, or final-egress gate. The variant
path may arm no scope broader than the two-natural-person path and no broader
than the smallest explicitly approved scope delta (Progressive Promotion step) declared for the variant under ADR-002-025 §5.11.

Where the required independence cannot be positively established — including
where an attestation required by the variant is unavailable, indeterminate, or
bound to a stale generation — approval SHALL fail closed and no re-arm,
issuance, or promotion may proceed.

Approval under this requirement is not authority. It authorizes only the exact
requested re-arm, issuance, or promotion and creates no capacity, protective
classification, Live Authorization, or transmission authority.

### Acceptance Conditions

**Trigger:** A risk-increasing live re-arm, Live Authorization issuance, or
production-scope promotion is requested.

**Expected result:** The request proceeds only after two independent effective
principals are established through the pre-declared satisfaction path; otherwise
it is denied.

**Forbidden outcome:** A single effective principal obtains a risk-increasing
re-arm, issuance, or promotion — whether through multiple accounts, an
unattested or undelayed single-operator self-approval, an ad-hoc satisfaction
path substitution, or a variant path proceeding without its required
independent attestation.

**Pass rule:** Every tested collapse of the two approvers to one effective
controller, every ad-hoc satisfaction-path substitution, and every missing,
stale, or indeterminate variant attestation fails closed.

**Initial status:** SPECIFIED

---

### SAFE-054 — Out-of-Band Containment of Final Egress

**Priority:** Critical
**Type:** Containment / Recovery
**Derived from:** CONST-009, CONST-011, CONST-014

The Safety Case SHALL assume that the final egress enforcement point may itself become defective or compromised, so that in-band controls at that point cannot be relied upon to stop unauthorized real-capital transmission.

A containment path independent of the final egress enforcement point SHALL be defined and evidenced that can, without relying on the compromised point's own cooperation, terminate its ability to transmit real-capital orders. Such a path may include, where the operating environment provides them:

* revocation or invalidation of the live-order credential;
* deactivation or suspension of the account or its order-entry capability;
* network- or session-level isolation of the enforcement point;
* an equivalent broker-side or out-of-band control.

The available out-of-band containment capability SHALL be established as evidence for the operating environment. Where no such capability exists, the residual risk SHALL be explicitly recorded and accepted under Section 14 before live operation, and the affected live scope SHALL be reduced accordingly.

This requirement SHALL NOT be interpreted to require any specific broker product or proprietary mechanism. It requires a demonstrated capability appropriate to the operating environment, expressed in Broker Capability Profile terms.

### Acceptance Conditions

**Trigger:** The final egress enforcement point is suspected or confirmed defective or compromised and continues, or may continue, to transmit.

**Expected result:** An out-of-band containment path terminates the enforcement point's real-capital transmission capability without depending on that point's cooperation.

**Forbidden outcome:** Containment of a compromised egress point depends solely on that same point functioning correctly.

**Pass rule:** Every tested defect or compromise of the enforcement point is contained by the out-of-band path within the approved containment bound, or the absence of that capability is recorded and accepted as residual risk with a correspondingly reduced live scope.

**Initial status:** SPECIFIED

---

## 11. Verification and Evidence

### 11.1 Requirement Lifecycle

Each `SAFE-xxx` requirement SHALL have one of the following statuses:

| Status       | Meaning                                                                                   |
| ------------ | ----------------------------------------------------------------------------------------- |
| PROPOSED     | Requirement has been proposed but not approved.                                           |
| SPECIFIED    | Requirement wording has been approved for implementation planning.                        |
| IMPLEMENTED  | A traced implementation exists.                                                           |
| DEMONSTRATED | Verification evidence has passed the defined acceptance criteria.                         |
| ACCEPTED     | Evidence has been independently reviewed and approved for the intended operational scope. |
| REJECTED     | The evidence or implementation does not satisfy the requirement.                          |
| DEFERRED     | Requirement is not applicable to the current scope and has an approved deferral record.   |

`IMPLEMENTED` SHALL NOT imply `DEMONSTRATED`.

`DEMONSTRATED` SHALL NOT imply `ACCEPTED`.

### 11.2 Evidence Classes

Safety evidence MAY include:

* requirements review;
* architecture review;
* static analysis;
* unit tests;
* property-based tests;
* integration tests;
* broker-adapter tests;
* replay tests;
* deterministic comparison;
* fault injection;
* chaos tests;
* process-kill and restart tests;
* network partition tests;
* stale-data tests;
* duplicate-event tests;
* simulation;
* paper trading;
* limited-capital operation;
* audit logs;
* operational runbooks;
* independent review;
* production monitoring evidence.

No single evidence class SHALL be assumed sufficient for every Critical requirement.

### 11.3 Fault-Injection Obligation

Every Critical requirement SHALL be tested against at least:

* nominal behavior;
* boundary behavior;
* missing input;
* invalid input;
* stale input;
* duplicated event;
* delayed event;
* process crash;
* restart;
* communication loss;
* broker rejection;
* partial fill;
* unknown execution outcome;
* conflicting authoritative and internal state.

Where a scenario is not applicable, the evidence record SHALL state why.

### 11.4 Independence of Acceptance

The component or agent implementing a Critical safety control SHALL NOT be the sole authority accepting its evidence.

Independent review SHALL be required before `ACCEPTED` status.

### 11.5 Critical Requirement Acceptance Contract

Every Critical `SAFE-xxx` requirement SHALL have an approved acceptance record before its status may advance to `DEMONSTRATED`.

The acceptance record SHALL define:

```text
Requirement ID
Applicable Operational Scope
Preconditions
Trigger Condition
Injected Fault or Boundary Condition
Expected State Transition
Required Observable Result
Forbidden Outcome
Maximum Authorized Exposure
Maximum Detection Time
Maximum Containment Time
Parameter Source
Required Evidence IDs
Pass Rule
Fail Rule
Independent Review Authority
Residual Risk
```

A Critical requirement SHALL remain no higher than `SPECIFIED` when any required acceptance field is missing.

Terms such as:

* sufficiently fresh;
* maximum credible;
* safest feasible;
* greatest feasible extent;
* appropriate;
* timely;
* where feasible;

SHALL NOT constitute acceptance criteria unless resolved by an approved measurable parameter or decision rule.

Numeric criteria MAY reside in an approved Safety Profile or Verification Plan, but RFC-001 traceability SHALL identify:

* the authoritative parameter;
* its units;
* its approval authority;
* its version;
* its applicable scope.

---

## 12. Constitutional Verification Matrix

| Constitutional requirement                     | Safety discharge                                                                                               | Principal hazards                                                                                                   | Current status            |
|------------------------------------------------|----------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|---------------------------|
| CONST-001 — Long-Term Survivability            | SAFE-010, SAFE-012, SAFE-013, SAFE-014, SAFE-021, SAFE-042, SAFE-045                                           | HAZ-001, HAZ-002, HAZ-004, HAZ-005, HAZ-012, HAZ-013, HAZ-016, HAZ-017, HAZ-019, HAZ-020, HAZ-021, HAZ-023, HAZ-024 | SPECIFIED                 |
| CONST-002 — Capital Preservation               | SAFE-010, SAFE-012, SAFE-013, SAFE-021, SAFE-045                                                               | HAZ-001, HAZ-002, HAZ-003, HAZ-004, HAZ-012, HAZ-013, HAZ-017, HAZ-020, HAZ-021, HAZ-022, HAZ-023                   | SPECIFIED                 |
| CONST-003 — Positive Expectancy                | Constrained by all Critical safety requirements; performance demonstration delegated to the Decision Framework | —                                                                                                                   | NOT DISCHARGED BY RFC-001 |
| CONST-004 — Fail-Safe Operating Principle      | SAFE-001, SAFE-002, SAFE-030, SAFE-040                                                                         | HAZ-006, HAZ-008, HAZ-016, HAZ-018                                                                                  | SPECIFIED                 |
| CONST-005 — Independent Approval Authority     | SAFE-031, SAFE-033, SAFE-034, SAFE-051                                                                         | HAZ-006, HAZ-014                                                                                                    | SPECIFIED                 |
| CONST-006 — Operational Safety Limits          | SAFE-003, SAFE-010, SAFE-011, SAFE-012, SAFE-013, SAFE-014                                                     | HAZ-002, HAZ-003, HAZ-005, HAZ-011, HAZ-013, HAZ-019, HAZ-020, HAZ-023                                              | SPECIFIED                 |
| CONST-007 — Venue Constraints                  | SAFE-032, SAFE-043                                                                                             | HAZ-007, HAZ-008, HAZ-023                                                                                           | SPECIFIED                 |
| CONST-008 — Authoritative Position             | SAFE-022, SAFE-044                                                                                             | HAZ-009, HAZ-017, HAZ-021, HAZ-022                                                                                  | SPECIFIED                 |
| CONST-009 — Pre-Trade Constitutional Assurance | SAFE-010, SAFE-012, SAFE-020, SAFE-021, SAFE-030, SAFE-033, SAFE-045, SAFE-046                                 | HAZ-002, HAZ-003, HAZ-004, HAZ-006, HAZ-012, HAZ-014, HAZ-015, HAZ-016, HAZ-017, HAZ-020, HAZ-022, HAZ-025          | SPECIFIED                 |
| CONST-010 — Fail-Closed Configuration          | SAFE-003, SAFE-011, SAFE-050                                                                                   | HAZ-002, HAZ-011, HAZ-016, HAZ-019                                                                                  | SPECIFIED                 |
| CONST-011 — Independent Safety Authority       | SAFE-011, SAFE-014, SAFE-041, SAFE-042, SAFE-050                                                               | HAZ-005, HAZ-010, HAZ-018, HAZ-024, HAZ-025                                                                         | SPECIFIED                 |
| CONST-012 — Safe Operational State             | SAFE-001, SAFE-002, SAFE-040, SAFE-043                                                                         | HAZ-008, HAZ-018, HAZ-023                                                                                           | SPECIFIED                 |
| CONST-013 — Safe Operational Start             | SAFE-022, SAFE-044, SAFE-046                                                                                   | HAZ-009, HAZ-012, HAZ-016, HAZ-021                                                                                  | SPECIFIED                 |
| CONST-014 — Irreversibility Principle          | SAFE-010, SAFE-020, SAFE-021, SAFE-033, SAFE-051, SAFE-052                                                     | HAZ-003, HAZ-004, HAZ-014, HAZ-015, HAZ-022, HAZ-025                                                                | SPECIFIED                 |
| CONST-015 — Bounded Human Authority            | SAFE-042, SAFE-046, SAFE-053                                                                                   | HAZ-024                                                                                                             | SPECIFIED                 |

A `SPECIFIED` entry indicates that RFC-001 defines the required safety obligation. It does not indicate implementation or demonstration.

### Additional Safety Discharges (v0.3)

| Constitutional requirement | Added safety discharge                                              |
| -------------------------- | ------------------------------------------------------------------ |
| CONST-001                  | SAFE-004, SAFE-015, SAFE-023, SAFE-024, SAFE-025, SAFE-035, SAFE-047, SAFE-048 |
| CONST-002                  | SAFE-004, SAFE-015, SAFE-023, SAFE-024, SAFE-025, SAFE-047          |
| CONST-004                  | SAFE-035, SAFE-048                                                  |
| CONST-006                  | SAFE-004, SAFE-015, SAFE-047                                        |
| CONST-008                  | SAFE-023, SAFE-024, SAFE-025                                        |
| CONST-009                  | SAFE-015, SAFE-023, SAFE-025, SAFE-035                             |
| CONST-010                  | SAFE-004, SAFE-035                                                  |
| CONST-011                  | SAFE-048                                                            |
| CONST-012                  | SAFE-048                                                            |
| CONST-013                  | SAFE-023, SAFE-024, SAFE-035                                        |
| CONST-014                  | SAFE-025                                                            |

### Additional Safety Discharges (v0.4)

| Constitutional requirement | Added safety discharge |
| -------------------------- | ---------------------- |
| CONST-005                  | SAFE-053               |
| CONST-011                  | SAFE-053               |
| CONST-013                  | SAFE-053               |

### Additional Safety Discharges (v0.5)

| Constitutional requirement | Added safety discharge |
| -------------------------- | ---------------------- |
| CONST-009                  | SAFE-054               |
| CONST-011                  | SAFE-054               |
| CONST-014                  | SAFE-054               |

---

## 13. Production Readiness Gates

### 13.1 Research

Research MAY operate with undemonstrated safety requirements only when it has no live-order capability.

### 13.2 Simulation

Simulation SHALL use non-live credentials and SHALL NOT possess a route to real-capital execution.

### 13.3 Paper Trading

Paper trading SHALL demonstrate:

* decision traceability;
* safety-profile validation;
* intent identity;
* projected-state limit checks;
* restart and reconciliation behavior;
* safe-state transitions.

### 13.4 Limited Capital

Limited-capital operation SHALL require:

* every applicable Critical requirement at `DEMONSTRATED`;
* independent approval of the evidence;
* explicit live authorization;
* a restricted production scope;
* approved emergency procedures;
* active monitoring;
* an approved residual-risk record.

### 13.5 Production

Production operation SHALL require:

* every applicable Critical requirement at `ACCEPTED`;
* no unresolved CATASTROPHIC hazard;
* no blocking traceability gap;
* successful restart, recovery, duplicate-event, and broker-failure testing;
* accepted aggregate risk controls;
* accepted live/non-live segregation;
* accepted human and automated containment authority;
* an approved Safety Profile;
* ratification by the designated authority.

Failure to maintain any production prerequisite SHALL revoke production readiness and force the applicable safe state.

### 13.6 Additional Critical Blockers

Production operation SHALL NOT begin or continue unless:

* SAFE-004 is `ACCEPTED`;
* SAFE-015 is `ACCEPTED`;
* SAFE-023 is `ACCEPTED`;
* SAFE-024 is `ACCEPTED`;
* SAFE-025 is `ACCEPTED`;
* SAFE-035 is `ACCEPTED`;
* SAFE-048 is `ACCEPTED`;
* no unresolved HAZ-016 through HAZ-025 remains Catastrophic;
* every Critical requirement has a complete acceptance record;
* external account activity is continuously reconciled;
* time-source failure behavior has been demonstrated;
* communication-partition containment has been demonstrated;
* concurrent risk-capacity tests have passed;
* semantically invalid Safety Profiles have been rejected;
* partial-fill and unknown-execution recovery have been demonstrated.

Failure to maintain any prerequisite SHALL revoke new risk-increasing authority.

---

## 14. Waivers, Deviations, and Residual Risk

A Critical requirement SHALL NOT be silently waived.

Any waiver or deviation SHALL:

* identify the affected requirement and hazard;
* state the operational scope;
* state the duration;
* identify compensating controls;
* quantify or classify residual risk;
* identify the approving authority;
* be auditable;
* expire automatically;
* be incompatible with broader production authority than explicitly approved.

A waiver SHALL NOT redefine the Constitution.

No waiver is permitted for:

* loss of independent halt authority;
* live/non-live segregation failure;
* absence of a valid Safety Profile;
* unreconciled authoritative position state;
* unbounded single-action risk;
* unbounded aggregate risk;
* a known path to duplicate exposure.

---

## 15. Safety Evidence Register

The following register SHALL be maintained as implementation proceeds.

| Evidence ID | Requirement | Evidence type                 | Artifact | Owner | Status      | Review authority |
| ----------- | ----------- | ----------------------------- | -------- | ----- | ----------- | ---------------- |
| EVID-TBD    | SAFE-001    | Safe-state fault injection    | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-TBD    | SAFE-003    | Configuration validation      | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-TBD    | SAFE-010    | Pre-trade limit enforcement   | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-TBD    | SAFE-021    | Duplicate-exposure prevention | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-TBD    | SAFE-022    | Restart reconciliation        | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-TBD    | SAFE-030    | Critical-input integrity      | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-TBD    | SAFE-041    | Independent containment       | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-TBD    | SAFE-045    | Live/non-live segregation     | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-TIME-001  | SAFE-035 | Time-fault injection                      | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-STATE-001 | SAFE-023 | Single-source corruption and disagreement | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-EXT-001   | SAFE-024 | External/manual account change detection  | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-FILL-001  | SAFE-025 | Partial and asynchronous fill recovery    | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-ENV-001   | SAFE-004 | Hard-envelope mutation and unit tests     | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-CAP-001   | SAFE-015 | Concurrent capacity commitment            | TBD      | TBD   | NOT STARTED | TBD              |
| EVID-PART-001  | SAFE-048 | Safety-authority partition test           | TBD      | TBD   | NOT STARTED | TBD              |

The register SHALL be expanded until every applicable `SAFE-xxx` requirement has one or more accepted evidence records.

---

## 16. Open Verification Obligations

At this revision:

* all safety requirements are `SPECIFIED`;
* no implementation evidence has been reviewed by this document;
* no Critical safety requirement is `ACCEPTED`;
* the TOS SHALL therefore NOT claim RFC-001 production conformance.

The absence of demonstrated evidence is an explicit readiness blocker, not an editorial TODO.

---

## 17. Review and Ratification

RFC-001 SHALL undergo, at minimum:

1. Engineering review;
2. Trading-operations review;
3. Safety review;
4. Architecture review;
5. Verification review;
6. Production-readiness review.

Ratification SHALL identify:

* the accepted operational scope;
* the applicable Safety Profile;
* accepted requirements;
* deferred requirements;
* residual risks;
* approving authority;
* effective date;
* expiration or re-review date.

The ratifying authority, preconditions, and record schema are defined by GOV-001; document ratification of this Safety Case confers no live authorization, which remains governed by ADR-002-007 and ADR-002-025.

Material changes to hazards, Critical requirements, safe-state semantics, or production gates SHALL require a new RFC-001 revision and renewed review.

---

## 18. Review History

### v0.1 — Scaffold

* Added initial constitutional hazards.
* Added constitutional verification matrix.
* Recorded undischarged constitutional gaps.

### v0.2 — Integrated Safety Case

* Defined the constitutional safe state.
* Added hazard classification and acceptance rules.
* Added derived `SAFE-xxx` requirements.
* Added pre-trade limits and aggregate risk authority.
* Added intent idempotency and at-most-one exposure effect.
* Added bounded action rate.
* Added trusted-input and venue-state requirements.
* Added safe-start and reconciliation requirements.
* Added independent containment authority.
* Added live/non-live segregation and explicit arming.
* Added verification lifecycle and evidence requirements.
* Added production-readiness gates.
* Replaced constitutional gaps with derived safety obligations.
* Added waiver and residual-risk governance.

### v0.3 — Critical Gap Closure

* Closed the Critical review gaps identified in RFC-001 v0.2.
* Added the Hard Safety Envelope, exclusive aggregate risk-capacity commitment, evidence-based Authoritative State, continuous external-state reconciliation, partial and asynchronous fill integrity, Trustworthy Time Basis, and partition-tolerant Safety Authority.
* Added the Critical requirement acceptance contract.
* Added HAZ-016 through HAZ-023 and raised HAZ-007 to CATASTROPHIC.
* Removed the unconditional broker/venue authority assumption.
* Removed the RFC-001-specific constitutional precedence hierarchy.
* Aligned safe-state behavior with RFC-000 (PATCH-0006).
* Strengthened production-readiness gates.

### v0.4 — Independent Re-Arm Approval Parent

* Added SAFE-053 as the Safety-Case-level parent for independent approval of risk-increasing live re-arm, Live Authorization issuance, and production-scope promotion, resolving the philosophy §35 hierarchy inversion in which ADR-002-015 originated a parentless obligation (CORPUS-REVIEW-0001 CR-02).
* Named the two lawful satisfaction paths: a two-natural-person quorum, or the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1).
* Extended the Constitutional Verification Matrix (CONST-005/011/013 → SAFE-053).
* Recorded per DR-0001 — Single-Operator Live Governance.

### v0.5 — Operator-Error and Egress-Defect Hazard Coverage

* Added HAZ-024 (Operator/Human Configuration or Authorization Error), distinct from HAZ-021 external/unattributed activity, and extended SC-010's completeness claim to name authorized human and operator error (CORPUS-REVIEW-0001 M-05).
* Added HAZ-025 (Defect or Compromise of the Final Egress Enforcement Point) and SAFE-054 (Out-of-Band Containment of Final Egress); scoped SC-050 explicitly to exclude egress-self-defect, now covered by HAZ-025/SAFE-054 (CORPUS-REVIEW-0001 M-06).
* Linked SAFE-053 to its new constitutional parent CONST-015 (Bounded Human Authority) and added CONST-015 to the Constitutional Verification Matrix (CORPUS-REVIEW-0001 M-03).
* Extended the Constitutional Verification Matrix (CONST-009/011/014 → SAFE-054) and the production-readiness Catastrophic-hazard blocker to HAZ-016 through HAZ-025.
* Evidence for SAFE-054, HAZ-024, and HAZ-025 is recorded as evidence debt in ARCHITECTURE-GATE-STATUS §4.3; the Evidence Register count is unchanged (363).

### v0.6 — Hazard Coverage Completeness and Traceability Matrix

* Extended the §12 Constitutional Verification Matrix "Principal hazards" cells so HAZ-016 through HAZ-023 appear against their §9 Constitutional-basis CONST rows, and added HAZ-024 (CONST-001) and HAZ-025 (CONST-009, CONST-014) to their remaining bases; every catalogued hazard HAZ-001..025 now appears in the matrix (CORPUS-REVIEW-0001 Wave 3 M-11).
* Corrected the CONST-015 row to drop HAZ-010, whose sole Constitutional basis is CONST-011 (the CONST-015 remove-vs-keep decision is an EV-L0 review item recorded in RFC-001-Patch-0011).
* Added CONST-015 to the Derived-from set of SAFE-042 (Human Emergency Authority) and SAFE-046 (Explicit Live Arming), completing the CONST-015 → SAFE-042/046/053 discharge triple.
* Recorded the new instantiated bidirectional coverage matrix verification/TRACEABILITY-MATRIX-002.md, referenced by VER-002-001 §383; SAFE-053 and SAFE-054 remain UNMAPPED accepted evidence debt (ARCHITECTURE-GATE-STATUS §4.2/§4.3).
* Change recorded in RFC-001-Patch-0011. No new SAFE requirement or hazard was added; the Evidence Register count is unchanged (363); vision.md, philosophy.md, and RFC-000 are unchanged.

### Wave-4 note — Part-2/3 Register Consolidation (2026-07-17)

* CORPUS-REVIEW-0001 CR-01 discharged the SAFE-053, SAFE-054, HAZ-024, and HAZ-025 evidence debt recorded in v0.5/v0.6 above: EVIDENCE-REGISTER-002 gained HAG-EV-013..018 and EGRESS-EV-013 (count 363 → 372), and the previously UNMAPPED SAFE-053/054 are now COVERED in TRACEABILITY-MATRIX-002 §2 (§5.1 resolved). This RFC-001 carries no requirement or hazard change in this wave; the note is dated and additive only.

### v0.7 — Named GOV-001 as the ratification-governance source (patch 0047)

* Added a §17 pointer identifying GOV-001 as the source of the ratifying authority, preconditions, and record schema, and clarifying that document ratification of this Safety Case confers no live authorization, which remains governed by ADR-002-007 and ADR-002-025.
* Pointer only, narrow-only and additive: no SAFE requirement, hazard, safe-state semantic, or numeric bound changed; the Evidence Register count is unchanged (Part-1 372); vision.md, philosophy.md, and RFC-000 are unchanged.

---

## Appendix A — Safety Requirement Dependency Map

```text
RFC-000 Trading Constitution
│
├── Survivability and Capital Preservation
│   ├── SAFE-010 Pre-Trade Safety Authorization
│   ├── SAFE-012 Bounded Single-Action Risk
│   ├── SAFE-013 Aggregate Risk Authority
│   ├── SAFE-014 Bounded Action Rate
│   ├── SAFE-021 At-Most-One Exposure Effect
│   └── SAFE-042 Human Emergency Authority
│
├── Fail-Safe Operation
│   ├── SAFE-001 Default Safe State
│   ├── SAFE-002 No Unmanaged Exposure
│   ├── SAFE-003 Fail-Closed Safety Profile
│   ├── SAFE-040 Protective Control in Degraded Operation
│   └── SAFE-043 Exit-Unavailable Containment
│
├── Decision and Approval Integrity
│   ├── SAFE-030 Trustworthy Context Precondition
│   ├── SAFE-031 Critical Input Provenance
│   ├── SAFE-033 Intent-to-Order Conformance
│   └── SAFE-034 Independent Approval Inputs
│
├── Execution and State Integrity
│   ├── SAFE-020 Immutable Intent Identity
│   ├── SAFE-021 At-Most-One Exposure Effect
│   ├── SAFE-022 Reconciliation Before Exposure
│   ├── SAFE-032 Venue and Tradability Gate
│   └── SAFE-044 Safe Start and Resume
│
├── Independent Safety Authority
│   ├── SAFE-011 Non-Bypassable Safety Limits
│   ├── SAFE-041 Independent Safety Authority
│   ├── SAFE-042 Human Emergency Authority
│   └── SAFE-050 Safety Configuration Governance
│
├── Production Segregation
│   ├── SAFE-045 Live and Non-Live Segregation
│   ├── SAFE-046 Explicit Live Arming
│   └── SAFE-047 Production Scope Confinement
│
└── Evidence and Recovery
    ├── SAFE-051 Decision and Execution Evidence
    └── SAFE-052 Replay and Incident Reconstruction
```

---

## Appendix B — Required Downstream Specifications

RFC-002 and subsequent specifications SHALL provide mechanisms and evidence for, at minimum:

* safe-state transitions;
* independent approval;
* safety-limit enforcement;
* aggregate risk calculation;
* intent identity and order idempotency;
* authoritative state reconciliation;
* input integrity and freshness;
* venue and session gating;
* live/non-live segregation;
* independent halt and containment;
* evidence capture;
* replay;
* operational monitoring;
* recovery and re-arming.

RFC-001 defines the safety obligations. It does not prescribe the concrete implementation architecture.

---

## Appendix C — Normative References

* RFC-000 — Trading Constitution
* RFC 2119 — Key words for use in RFCs to Indicate Requirement Levels
* RFC 8174 — Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words
