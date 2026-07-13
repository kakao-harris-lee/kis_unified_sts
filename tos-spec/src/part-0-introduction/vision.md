# Trading Operating System — Vision

**Document:** Vision
**Path:** `part-0-introduction/vision.md`
**Version:** 0.1 Draft
**Status:** Working Draft
**Classification:** Introduction / Non-Normative
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-13
**Last Updated:** 2026-07-13

---

## 1. Document Status

This document is explanatory and non-normative.

It describes the long-term direction, intended operating model, and desired characteristics of the Trading Operating System.

It does not establish constitutional, safety, architectural, or implementation requirements.

If this document conflicts with RFC-000 or another ratified normative specification, the normative specification governs.

---

## 2. Purpose

The Trading Operating System exists to operate real-capital trading activities with the discipline expected of mission-critical financial software.

The system is not intended to be a collection of trading scripts, a single-strategy bot, or an automation layer built primarily to maximize trading frequency.

It is intended to become a durable operating system for:

* constructing trading decisions;
* evaluating risk;
* controlling execution authority;
* protecting capital;
* managing degraded operation;
* maintaining authoritative operational state;
* producing evidence for every material action;
* supporting controlled evolution over many years.

Its purpose is not merely to place profitable trades.

Its purpose is to make trading decisions and execution safe enough that the system can survive long enough for positive expectancy to matter.

---

## 3. Problem Statement

Automated trading converts software behavior into irreversible financial consequences.

A small defect can become a real-capital event through:

* an oversized order;
* duplicated execution;
* stale market data;
* an incorrect contract multiplier;
* a wrong account;
* a failed retry;
* a partially filled exit;
* an unreconciled position;
* a network partition;
* a configuration error;
* a broker inconsistency;
* an operator mistake.

Traditional trading systems often focus first on:

* signal quality;
* prediction accuracy;
* latency;
* order throughput;
* backtest performance;
* strategy profitability.

These concerns are important, but they are not sufficient.

A strategy with positive expectancy can still destroy an account when:

* operational authority is unbounded;
* state is incorrect;
* safety limits fail open;
* execution is duplicated;
* risk is evaluated locally rather than across the account;
* failure handling abandons existing exposure;
* the system cannot be stopped independently;
* live and non-live operation are insufficiently separated.

The central problem is therefore not only:

> How can the system identify profitable opportunities?

It is also:

> How can the system prevent uncertainty, defects, operational failures, and external inconsistencies from becoming catastrophic capital loss?

---

## 4. Vision Statement

The vision is to build a long-lived, evidence-driven Trading Operating System that operates real capital only within explicitly bounded and continuously verifiable authority.

The system should remain conservative under uncertainty, resistant to single-defect account loss, and capable of entering an exposure-aware safe state without abandoning existing positions.

Trading strategies should remain replaceable.

Safety principles, authority boundaries, execution integrity, and evidence obligations should remain durable.

The long-term system should support multiple:

* strategies;
* instruments;
* asset classes;
* accounts;
* brokers;
* execution venues;
* operating modes;

without allowing that expansion to weaken capital protection or operational control.

---

## 5. North Star

The system is guided by the following long-term ordering:

```text
Long-Term Survivability
    >
Capital Preservation
    >
Operational Safety
    >
Decision and Execution Integrity
    >
Positive Expectancy
    >
Profitability
    >
Performance Optimization
```

This ordering does not imply that profitability is unimportant.

It means that profitability has value only when:

* capital remains available;
* operational authority remains controlled;
* decisions remain valid;
* execution remains bounded;
* failures remain containable;
* evidence remains sufficient to understand what happened.

A system that maximizes short-term return while exposing the account to catastrophic operational failure does not satisfy this vision.

---

## 6. Desired Operating Model

### 6.1 Strategies Propose; the System Authorizes

A trading strategy is treated as a proposer of intent, not as the final authority.

A strategy may identify:

* an opportunity;
* a direction;
* a desired quantity;
* an execution preference;
* an expected holding period.

The operating system independently determines whether the proposed action is:

* based on trustworthy context;
* consistent with current positions;
* within account and portfolio risk capacity;
* permitted by the venue;
* permitted by live authorization;
* safe to transmit;
* safe to retry;
* safe to continue during degradation.

No strategy is expected to possess unilateral authority over real capital.

---

### 6.2 Default Non-Live

The default operating condition is non-live.

Real-capital operation is an explicitly granted capability rather than an implied property of:

* deployment location;
* process startup;
* broker credentials;
* environment variables;
* previous operation;
* strategy configuration.

Research, simulation, backtesting, development, testing, and paper trading remain structurally separated from live execution.

---

### 6.3 Fail-Closed Under Uncertainty

Uncertainty reduces authority.

Missing, stale, inconsistent, or unverifiable safety information does not expand the system's freedom to act.

Examples include uncertainty about:

* position state;
* open-order state;
* fills;
* time;
* configuration;
* venue availability;
* market data;
* account state;
* safety authority;
* live authorization.

When the system cannot establish sufficient confidence, the preferred outcome is loss of new-risk authority rather than continued autonomous trading.

---

### 6.4 Exposure-Aware Safe Operation

Safe operation is not equivalent to shutting down every action.

Existing positions, open orders, margin obligations, and trapped exposure continue to exist after normal trading stops.

The desired system can distinguish between:

* actions that create new risk;
* actions that preserve existing protection;
* actions that reduce aggregate risk;
* actions that appear protective but create greater margin, basis, liquidity, concentration, or execution risk.

The safe state preserves control over existing exposure while preventing unverified risk expansion.

---

### 6.5 Prevention Before Explanation

The system prioritizes preventing unsafe execution over explaining it afterward.

Audit, logging, replay, and incident reconstruction remain essential, but they do not recover capital already lost through an irreversible action.

The desired operating model therefore concentrates assurance before execution.

---

### 6.6 Explicit and Revocable Authority

Trading authority is:

* explicit;
* scoped;
* time-bounded where appropriate;
* attributable;
* reviewable;
* revocable.

Authority is limited by:

* account;
* strategy;
* instrument;
* venue;
* operating mode;
* software version;
* safety configuration;
* risk capacity;
* current safety state.

Authority does not persist indefinitely merely because it was valid in the past.

---

### 6.7 Independent Containment

The system retains an authority capable of restricting or suspending autonomous operation independently from the strategy that proposed the action.

A defect should not control both:

* the action that creates the hazard;
* the mechanism expected to contain it.

The long-term architecture seeks effective containment not only under ordinary component failure, but also under:

* process crash;
* network partition;
* stale authority;
* duplicate active instances;
* partial system availability;
* broker inconsistency.

---

### 6.8 Evidence-Based State

No individual database, cache, message, broker response, or local projection is assumed to be infallible.

Operational state is established from available evidence.

The system distinguishes between:

* submitted;
* acknowledged;
* partially filled;
* filled;
* cancellation requested;
* cancelled;
* unknown;
* reconciled.

Unknown state remains explicitly unknown until sufficient evidence exists.

Convenient assumptions are not used to convert uncertainty into trading authority.

---

### 6.9 Human Authority Remains Available

Automation exists to improve consistency and control, not to eliminate responsible human authority.

Authorized operators retain the ability to:

* observe the current operational state;
* identify unknown or trapped exposure;
* suspend autonomous operation;
* invoke approved containment;
* withhold re-arming;
* review safety evidence.

Human intervention is itself bounded, authenticated, and auditable.

---

## 7. What Success Looks Like

The Trading Operating System is successful when it demonstrates the following characteristics.

### 7.1 Survivable Failure

A single ordinary defect does not have a direct, uncontrolled path to account destruction.

Failures may reduce:

* availability;
* trading opportunity;
* throughput;
* automation;
* performance.

They do not silently grant unbounded financial authority.

---

### 7.2 Bounded Financial Consequences

Every material trading action is constrained by an approved safety boundary.

The system can explain:

* what authority permitted the action;
* which risk capacity was committed;
* what state was believed;
* which evidence supported that state;
* what outcome occurred;
* what residual exposure remains.

---

### 7.3 Controlled Degradation

The system does not treat all degraded conditions identically.

It can distinguish among:

* restricted live operation;
* protective-only operation;
* contained operation;
* reconciliation;
* halted operation;
* recovery.

Normal trading does not consume all resources required for emergency or protective control.

---

### 7.4 Reliable Recovery

Restart and reconnection do not imply safety.

The system restores authority only after re-establishing:

* valid configuration;
* trustworthy time;
* live authorization;
* reconciled positions;
* reconciled open orders;
* valid safety authority;
* known aggregate risk.

Recovery does not silently create a second execution path or duplicate exposure.

---

### 7.5 Replaceable Strategies

Strategies can evolve, fail, or be removed without requiring the safety model to be reinvented.

The system's core safety and execution integrity do not depend on a particular:

* signal;
* model;
* indicator;
* market regime;
* holding period;
* trading style.

---

### 7.6 Broker and Market Portability

The system can adapt to different brokers and venues without assuming that every provider offers:

* idempotent order APIs;
* perfect state;
* drop-copy feeds;
* unlimited queries;
* synchronous fills;
* reliable cancellation;
* consistent timestamps.

When a broker cannot support the desired assurance level, the system reduces its operational scope rather than weakening its safety principles.

---

### 7.7 Traceable Evolution

Every major safety and architecture decision is recorded and traceable through:

```text
Vision
    ↓
Philosophy
    ↓
Constitution
    ↓
Safety Requirements
    ↓
Architecture
    ↓
Architecture Decisions
    ↓
Implementation
    ↓
Verification Evidence
```

The system evolves through explicit decisions rather than undocumented convention.

---

## 8. Long-Term Scope

The long-term vision includes support for multiple forms of systematic trading, potentially including:

* Korean equities;
* stock-index futures;
* exchange-traded derivatives;
* global equities;
* digital assets;
* spot and derivatives portfolios;
* hedged and unhedged strategies;
* event-driven strategies;
* trend-following strategies;
* swing strategies;
* portfolio-level allocation.

Expansion is conditional.

A new:

* market;
* broker;
* account;
* instrument class;
* strategy type;
* execution mode;

is introduced only when its hazards, operational constraints, evidence sources, and containment behavior can be incorporated without weakening the existing safety model.

Market expansion is not itself a success criterion.

Safe and controlled expansion is.

---

## 9. Desired Qualities

### 9.1 Durable

The system is designed to remain understandable and maintainable over many years.

Core principles should change slowly.

Strategies and adapters may change more frequently.

---

### 9.2 Simple Where Possible

Complexity is accepted only when it controls a real hazard or enables a necessary capability.

Complexity that exists only to:

* improve elegance;
* increase abstraction;
* anticipate hypothetical scale;
* reproduce fashionable architecture;

is not automatically valuable.

A simpler mechanism with clear failure behavior is preferred to a complex mechanism whose safety properties are difficult to demonstrate.

---

### 9.3 Observable

The system makes important states visible, including:

* current authority;
* current risk capacity;
* open and potentially live orders;
* trapped exposure;
* reconciliation status;
* safety configuration;
* degraded mode;
* evidence completeness.

A hidden safety state is not an operationally useful safety state.

---

### 9.4 Explainable

The system can explain why an action was:

* proposed;
* approved;
* rejected;
* transmitted;
* retried;
* cancelled;
* contained.

Explainability supports review and learning, but does not replace prevention.

---

### 9.5 Testable

Critical behavior can be demonstrated through repeatable tests, including:

* duplicate events;
* stale input;
* clock failure;
* broker inconsistency;
* partial fill;
* unknown order state;
* process restart;
* network partition;
* external account activity;
* configuration error;
* protective-capacity exhaustion.

A safety property that cannot be tested objectively remains an unproven claim.

---

### 9.6 Conservative at Boundaries

The system is deliberately conservative when:

* data quality declines;
* state diverges;
* market liquidity disappears;
* execution becomes ambiguous;
* time becomes untrustworthy;
* configuration is incomplete;
* safety authority is unavailable.

Missed trading opportunities are acceptable consequences of unresolved critical uncertainty.

---

## 10. Success Measures

Success is evaluated across multiple dimensions.

### 10.1 Safety

* no uncontrolled single-defect path to catastrophic exposure;
* no unidentified live-order path;
* no silent fail-open safety configuration;
* no automatic live re-arming after material failure;
* no unresolved unknown execution state treated as safe.

### 10.2 Operational Integrity

* positions and open orders remain reconcilable;
* manual and external account activity is detected;
* partial fills remain correctly represented;
* degraded operating modes are explicit;
* containment authority remains available.

### 10.3 Decision Integrity

* decisions use trustworthy context;
* approval remains independent;
* intent and transmitted order remain conformant;
* decisions remain reproducible within documented boundaries.

### 10.4 Economic Viability

* live strategies demonstrate positive expectancy after realistic costs;
* risk-adjusted performance justifies the operational complexity;
* capital allocation reflects confidence and evidence;
* performance does not depend on violating safety limits.

### 10.5 Maintainability

* responsibilities remain explicit;
* state transitions remain reviewable;
* architecture decisions remain documented;
* safety evidence remains traceable;
* broker and strategy changes do not require constitutional redesign.

No single metric is sufficient to declare the system successful.

---

## 11. Non-Goals

The Trading Operating System is not intended to:

### 11.1 Guarantee Profit

Markets remain uncertain.

No architecture can guarantee profitable outcomes.

### 11.2 Eliminate All Trading Loss

Expected trading losses are distinct from operationally uncontrolled losses.

The system seeks to control the latter without pretending to eliminate the former.

### 11.3 Maximize Trading Frequency

More orders, more strategies, and more market participation are not inherently better.

The system may deliberately choose not to trade.

### 11.4 Predict Every Market Event

The system does not assume that news, policy events, liquidity shocks, or market transitions can always be predicted.

It seeks to bound exposure when prediction is unreliable.

### 11.5 Operate Fully Autonomously at Any Cost

Automation is subordinate to explicit authority, safety, evidence, and human governance.

### 11.6 Support Every Broker or Market

A broker or venue may be excluded when its operational characteristics cannot support the required safety properties.

### 11.7 Optimize Away Safety Capacity

Reserved capacity, margin headroom, conservative limits, and reduced throughput may appear inefficient.

They are not considered waste when they preserve containment capability.

### 11.8 Hide Uncertainty

The system does not convert unknown state into confident state merely to maintain availability.

Unknown is represented explicitly.

### 11.9 Treat Backtests as Production Evidence

Backtest performance does not demonstrate execution safety, broker correctness, recovery behavior, or production readiness.

### 11.10 Replace Judgment With Complexity

Machine learning, reinforcement learning, distributed infrastructure, and advanced models are tools, not goals.

They are adopted only when their value can be demonstrated and their failure behavior can be controlled.

---

## 12. Intended Users and Stakeholders

The documentation and system are intended for:

### 12.1 System Owner

Responsible for capital, operating scope, and final risk acceptance.

### 12.2 Architecture Board

Responsible for constitutional conformance, safety integrity, and architecture decisions.

### 12.3 Strategy Developer

Responsible for producing trading intent within the system's authority model.

### 12.4 Safety and Risk Reviewer

Responsible for identifying hazards, validating safety controls, and reviewing evidence.

### 12.5 Implementation Engineer

Responsible for building mechanisms that satisfy approved requirements and ADRs.

### 12.6 Operator

Responsible for monitoring live operation, responding to degraded states, and controlling re-arming.

### 12.7 Independent Reviewer

Responsible for challenging assumptions, common-mode failures, evidence quality, and production readiness.

A single person may perform multiple roles in a small project, but the logical responsibilities remain distinct.

---

## 13. Evolution Strategy

The system evolves from principles to evidence.

```text
Vision
    ↓
Philosophy
    ↓
RFC-000 — Trading Constitution
    ↓
RFC-001 — Safety Case
    ↓
RFC-002 — System Architecture
    ↓
ADR-002-xxx — Architecture Decisions
    ↓
Implementation Specifications
    ↓
Verification Plans
    ↓
Safety Evidence
    ↓
Restricted Live Operation
    ↓
Expanded Production Scope
```

Expansion is incremental.

The system begins with:

* narrow operational scope;
* limited instruments;
* limited capital;
* explicit supervision;
* conservative authority;
* extensive evidence collection.

Scope increases only when the prior scope has produced sufficient evidence.

---

## 14. Relationship to Other Documents

### 14.1 `philosophy.md`

Explains the recurring beliefs and reasoning principles used when designing and operating the system.

### 14.2 RFC-000 — Trading Constitution

Defines the normative constitutional principles that all lower-level documents must preserve.

### 14.3 RFC-001 — Safety Case

Defines hazards, safety requirements, production gates, and evidence obligations.

### 14.4 RFC-002 — System Architecture

Defines components, authority, state, trust boundaries, failure behavior, and structural mechanisms.

### 14.5 Architecture Decision Records

Record important architectural choices, alternatives, consequences, and verification obligations.

### 14.6 Implementation Specifications

Define concrete protocols, storage models, algorithms, interfaces, deployment, and operational procedures.

### 14.7 Verification Evidence

Demonstrates whether implemented controls satisfy their approved requirements.

---

## 15. Vision Boundary

This vision guides the project but does not grant production authority.

The existence of this document does not establish that:

* a strategy is profitable;
* the system is safe;
* architecture requirements are satisfied;
* implementation is complete;
* evidence has been accepted;
* live operation is authorized.

Those claims require the normative specifications and evidence defined elsewhere.

---

## 16. Review Questions

This vision should be reviewed using the following questions:

1. Does it clearly distinguish the project from an ordinary trading bot?
2. Does it make survivability and capital protection primary without denying the need for positive expectancy?
3. Does it preserve a useful role for trading strategies without granting them excessive authority?
4. Does it describe uncertainty and degraded operation realistically?
5. Does it allow long-term expansion without implying that every market or broker must be supported?
6. Does it avoid duplicating normative RFC requirements?
7. Does it explain why preventive safety has priority over post-event analysis?
8. Does it preserve human authority without allowing human action to become an unbounded bypass?
9. Does it define success broadly enough to include safety, operation, economics, and maintainability?
10. Is the long-term vision stable even if current strategies, brokers, and technologies change?

---

## 17. Summary

The Trading Operating System is envisioned as a durable, safety-governed platform for real-capital systematic trading.

Its defining characteristic is not that it trades automatically.

Its defining characteristic is that automation is permitted only within explicit, bounded, reviewable, and revocable authority.

The system seeks positive expectancy, but only within a structure that prioritizes:

* survival;
* capital preservation;
* operational safety;
* decision and execution integrity;
* evidence;
* controlled evolution.

The ultimate objective is not maximum activity.

It is a system that can make disciplined trading decisions, survive failures, protect capital, learn from evidence, and continue operating responsibly over the long term.
