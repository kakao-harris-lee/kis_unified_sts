# RFC-000 — Trading Constitution

**Document ID**: RFC-000
**Title**: Trading Constitution
**Version**: 0.13 Review Draft
**Status**: Working Draft
**Classification**: Constitutional Specification
**Authority**: Highest-Level Governing Specification
**Owner**: Trading Operating System Architecture Board

---

# 1. Abstract

This document defines the constitutional principles governing the Trading Operating System (TOS).

The Constitution establishes immutable engineering principles, architectural boundaries, governance rules and system-level requirements that every future specification, implementation, deployment and operational procedure SHALL satisfy.

This document intentionally avoids implementation details.

Its purpose is to define **what SHALL always be true**, regardless of technology, programming language, infrastructure or broker implementation.

---

# 2. Scope

This Constitution applies to:

- All RFC documents
- All ADR documents
- All Decision Records
- All software implementations
- All AI-assisted development
- All deployment pipelines
- All operational procedures
- All production trading systems

This Constitution SHALL remain implementation-independent.

---

# 3. Normative Language

The key words

**MUST**

**MUST NOT**

**REQUIRED**

**SHALL**

**SHALL NOT**

**SHOULD**

**SHOULD NOT**

**MAY**

in this document are to be interpreted as described in RFC 2119.

---

# 4. Constitutional Requirement Identification

Every constitutional requirement SHALL possess a globally unique identifier.

Identifier format

```
CONST-001

CONST-002

CONST-003
```

Identifiers SHALL remain stable for the lifetime of the Constitution.

Deleted identifiers SHALL NEVER be reused.

### Rationale

Requirement traceability requires stable identifiers.

---

# 5. Normative Requirement Structure

Every constitutional requirement SHALL contain the following mandatory fields.

```
Identifier

Title

Classification

Priority

Requirement

Constraint

Rationale

Failure Scenario

Risk of Violation

Verification

Derived Requirements
```

A constitutional requirement MAY additionally carry the following optional
fields. They are supplementary cross-references, not completeness gates:

```
Traceability

Revision History
```

Document-level change history is recorded in the Review History section rather
than per-requirement, so a `Revision History` field is present only where a
requirement carries requirement-specific history.

A `Derived Requirements` entry marked `(reserved)` names an identifier
namespace that is anticipated but not yet instantiated in this specification
set. Three such namespaces were reserved; as of the Wave-4 Part-2/3 register
consolidation, two (`DEC-xxx`, `TEST-xxx`) are now instantiated through
governance and one (`ARCH-xxx`) remains reserved:

* `ARCH-xxx` — architecture-level requirements. These are currently discharged
  through the `ADR-002-xxx` decision series (see RFC-002 §26) rather than a
  standalone `ARCH-xxx` register; the reserved marker preserves the intended
  constitution-to-architecture trace until or unless a dedicated register is
  introduced.
* `DEC-xxx` — decision-layer requirements, now instantiated in VER-DEV-001 and
  EVIDENCE-REGISTER-DEV (the Part-2/3 development track): DEC-001 through DEC-005
  for the RFC-003 Decision Framework and its part-2 companions RFC-004 through
  RFC-007, with evidence DEC-EV-001 through DEC-EV-005.
* `TEST-xxx` — test-and-verification requirements, now instantiated in VER-DEV-001
  and EVIDENCE-REGISTER-DEV as TEST-001 for the RFC-010 Testing↔Safety Boundary
  (evidence TEST-EV-001). VER-002-001 and the Part-1 Evidence Register remain the
  Part-1 verification track.

A reserved marker is a forward placeholder only. It grants no requirement,
creates no obligation, and SHALL NOT be treated as a defined identifier until
its namespace is formally instantiated through governance. Two of the three
namespaces (`DEC-xxx`, `TEST-xxx`) have now been so instantiated through the
Wave-4 governance consolidation; `ARCH-xxx` remains reserved. Any
subordinate-layer instantiation is bound by the narrow-only governance rule of
§12 and MAY narrow but SHALL NOT widen any Part-1 authority.

### Rationale

Uniform requirements improve readability and verification.

### Requirement Priority

Requirement priorities SHALL be

Critical

High

Medium

Low

Constitutional Requirements SHALL normally be classified as Critical.

### Constitutional Precedence

Classification as Critical SHALL NOT imply that all constitutional requirements are equal when they conflict.

Where two constitutional requirements conflict, the interpretation that provides greater operational safety, stronger capital preservation and lower systemic risk SHALL prevail.

The constitutional objectives SHALL be ordered as follows, mirroring the North Star ordering of vision §5.

```
Long-Term Survivability
        │
        ▼
Capital Preservation
        │
        ▼
Operational Safety
        │
        ▼
Decision and Execution Integrity
        │
        ▼
Positive Expectancy
        │
        ▼
Profitability
        │
        ▼
Performance Optimization
```

The following table maps each North Star tier to the constitutional requirements that express it.

| North Star tier (vision §5) | Constitutional expression |
| --- | --- |
| Long-Term Survivability | CONST-001 |
| Capital Preservation | CONST-002 |
| Operational Safety | CONST-004, CONST-006, CONST-007, CONST-010, CONST-011, CONST-012, CONST-013, CONST-015 |
| Decision and Execution Integrity | CONST-005, CONST-008, CONST-009, CONST-014 |
| Positive Expectancy | CONST-003 |
| Profitability | Definition of Success (§16); subordinate to every higher tier |
| Performance Optimization | Non-Goals (§17); subordinate to all preventive and safety requirements |

Positive Expectancy (CONST-003), although classified Critical, is ordered below survivability, capital preservation, operational safety, and decision-and-execution integrity. CONST-003 SHALL NOT be satisfied by weakening any operational-safety or integrity requirement, and in particular SHALL remain subordinate to CONST-005 (Independent Approval Authority) and CONST-009 (Pre-Trade Constitutional Assurance).

Preventive and safety requirements SHALL take precedence over performance objectives.

No optimization, performance improvement or feature addition SHALL weaken a higher-precedence requirement to satisfy a lower-precedence one.

In every conflict, the safety-favoring resolution rule above governs; the tier ordering provides direction only and SHALL NOT be used to weaken any preventive or integrity requirement in favour of a lower tier.

Safety-favoring resolution preserves survivability under uncertainty, which is the constitution's highest objective.

### Risk-Effect Interpretation

For constitutional interpretation, an action SHALL be classified by its projected aggregate effect on the safety of the account or portfolio.

Classification SHALL NOT be based solely on:

* order direction;
* gross quantity;
* strategy intent;
* component-provided labels;
* whether the action opens or closes an individual position.

An action may be classified as risk-reducing only when:

1. its projected aggregate post-action state is safer than the current state;
2. the conclusion is based on sufficiently trustworthy operational context;
3. the action remains within all applicable safety limits;
4. the action does not create a greater credible risk through margin, leverage, liquidity, basis, concentration, venue, settlement, or execution effects;
5. the conclusion can be demonstrated before execution.

An action whose aggregate risk effect cannot be determined SHALL be classified as risk-increasing.

---

# 6. Definitions

The following terms SHALL carry the following constitutional meaning.

Definitions establish principle-level meaning only.

They SHALL NOT prescribe implementation.

**Survivability**

The capacity of the system to remain solvent and able to continue making decisions indefinitely, such that no event or sequence of events causes permanent, unrecoverable capital impairment.

**Capital Preservation**

The protection of operating capital from impairment that would threaten survivability, taking precedence over the pursuit of return.

**Positive Expectancy**

The statistically expected value of the complete decision process, evaluated over a population of decisions rather than any individual trade.

**Decision Quality**

The degree to which a decision was correct given the information constitutionally available when it was made, independent of its individual outcome.

**Deterministic Decision**

A decision that, given identical Decision Context, always yields the same result; determinism applies to the decision process, not to market outcomes.

**Decision Context**

The complete, immutable, read-only information a decision consumes; its concrete taxonomy is defined by Architecture RFCs.

**Critical Uncertainty**

A condition in which the system cannot establish, within constitutional bounds, that its Decision Context is complete, current and internally consistent.

**Operational Safety**

The property that the system's behaviour remains within constitutional safety limits under all conditions, including failure.

**Operational Safety Limits**

Constitutionally mandated, externally configured bounds on exposure, loss and action beyond which trading SHALL NOT proceed; an absent or invalid limit is a bound of zero.

**Constitutional Safe State**

The Constitutional Safe State is an exposure-aware operational state in which:

* no new risk-increasing exposure SHALL be authorized;
* existing exposure SHALL remain subject to approved protective control;
* unknown or unverified exposure SHALL be treated conservatively;
* autonomous risk-increasing activity SHALL remain suspended;
* bounded protective actions MAY remain authorized only when their projected aggregate effect reduces constitutional risk and remains within every applicable constitutional safety boundary.

The Constitutional Safe State SHALL NOT be interpreted as:

* mere inactivity;
* unconditional abandonment of existing exposure;
* automatic liquidation regardless of market or venue conditions;
* authorization to create unlimited hedge, margin, liquidity, basis, or execution risk.

Where the risk effect of an action cannot be determined with sufficient confidence, the action SHALL be treated as risk-increasing.

**Autonomous Trading**

Any creation, modification or cancellation of orders performed by the system without contemporaneous human authorization.

**Approval**

The independent authority that accepts or rejects a proposed trading action before execution, distinct from the component that generated it.

**Decision Generation**

The activity of producing a proposed trading action from Decision Context and interpretation, prior to Approval.

**Intent**

The trading action a decision was constitutionally meant to produce, against which any emitted order is validated.

**Constitutional Assurance**

Demonstrable confirmation, before an action is transmitted for execution, that the action satisfies all applicable constitutional requirements.

**Authoritative Source**

The authoritative basis for positions, orders and account state recognized under CONST-008: the account's true operational state established through reconciliation from corroborating evidence. Individual internal or external responses, including any single API response, are evidence contributing to that basis and SHALL NOT by themselves be treated as unconditionally correct. The system's internal representation SHALL NOT override the Authoritative Source.

**Operational State**

The true state of positions, orders and account held by the Authoritative Source, as distinct from the system's internal representation of it.

**Constitutionally Validated**

The condition in which Operational State has been reconciled against the Authoritative Source and confirmed consistent within constitutional bounds.

**Replay**

The reconstruction of a past decision and its execution from recorded inputs for audit purposes; replay is diagnostic and SHALL NOT substitute for preventive assurance.

### Authoritative-State Term Relationships

The following related terms SHALL be read as one concept expressed at different levels; none SHALL be interpreted as a single infallible source.

| Term | Defined in | Meaning |
| --- | --- | --- |
| Authoritative Position | RFC-000 CONST-008 | The constitutional principle that positions, orders, and account state have an authoritative basis the internal representation SHALL NOT override. |
| Authoritative Source | RFC-000 §6 | The account's true operational state established through reconciliation from corroborating evidence; individual responses are evidence, not themselves ground truth. |
| Operational State | RFC-000 §6 | The true state of positions, orders, and account reflected by the Authoritative Source, as distinct from the system's internal representation. |
| Authoritative State | RFC-001 §5.1 | The Safety-Case discharge of the Authoritative Source: the state accepted as the governing basis after safety-relevant corroborating evidence has been reconciled. |

Constitutionally Validated (this section) is the condition in which Operational State has been reconciled against the Authoritative Source; it corresponds to the RFC-001 Reconciled State (RFC-001 §5.13). RFC-001 §5.1 (Authoritative State) is the Safety-Case discharge of CONST-008 and SHALL be read as consistent with it, not as a reinterpretation of it.

### Rationale

Normative requirements require unambiguous terminology.

Undefined terms in a constitution propagate divergent interpretations into every downstream specification.

---

# 7. Constitutional Mission

## CONST-001

### Title

Long-Term Survivability

### Priority

Critical

### Requirement

The Trading Operating System SHALL prioritize long-term survivability above every other engineering objective.

### Constraint

No architectural decision SHALL weaken survivability in exchange for expected profitability.

### Rationale

Financial markets contain uncertainty that cannot be eliminated.

A system that cannot survive cannot generate long-term positive expectancy.

### Failure Scenario

System optimization favors aggressive leverage.

↓

Unexpected market event occurs.

↓

Capital becomes permanently impaired.

↓

System objective fails.

### Risk of Violation

Critical

Permanent capital loss.

### Verification

Every child RFC SHALL explicitly demonstrate compliance with CONST-001.

### Traceability

RFC-001 Safety Case

RFC-002 Architecture

RFC-003 Decision Framework

---

## CONST-002

### Title

Capital Preservation

### Priority

Critical

### Requirement

The Trading Operating System SHALL preserve capital before attempting to maximize return.

### Constraint

No subsystem SHALL increase portfolio risk unless explicitly justified by constitutional risk policy.

### Rationale

Capital is a non-renewable operational resource.

Profit generation is impossible after catastrophic capital impairment.

### Failure Scenario

Position sizing ignores downside exposure.

↓

Drawdown exceeds recovery capability.

↓

Operational termination.

### Risk of Violation

Critical

Loss of operational continuity.

### Verification

Risk policies SHALL demonstrate compliance.

### Traceability

RFC-001

RFC-005

---

## CONST-003

### Title

Positive Expectancy

### Priority

Critical

### Requirement

The Trading Operating System SHALL optimize the long-term positive expectancy of the complete decision process.

The optimization target SHALL NOT be individual trade outcome.

### Constraint

Performance metrics SHALL evaluate decision populations rather than isolated trades.

### Rationale

Individual trades contain irreducible uncertainty.

Only sufficiently large decision populations provide statistically meaningful evaluation.

### Failure Scenario

Engineering effort optimizes win rate.

↓

Risk/reward deteriorates.

↓

Long-term expectancy becomes negative.

### Risk of Violation

Major

False optimization.

### Verification

Performance evaluation SHALL use expectation-based metrics.

### Traceability

RFC-003

RFC-006

CONST-003 is discharged through a named composite chain: RFC-003 §12 accepts the framework-level obligation, RFC-006 §11 owns the statistical expectancy methodology, and ADR-002-025 owns the live-readiness demonstration (RLP-EV-001 through RLP-EV-012). Completion of CONST-003 is declarable only via the ADR-002-025 restricted-live evidence; no single document declares CONST-003 discharged in full.

---

## CONST-004

### Title

Fail-Safe Operating Principle

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

When critical operational uncertainty exceeds approved bounds, or when the operational state cannot be constitutionally verified, the Trading Operating System SHALL transition to the Constitutional Safe State defined by CONST-012.

The preferred failure mode SHALL be withdrawal of authority to create new risk.

Fail-safe operation SHALL NOT abandon existing exposure or terminate required protective obligations solely because ordinary autonomous trading has been suspended.

### Constraint

No risk-increasing action, whether autonomous or human-authorized, SHALL be authorized while the system is in the Constitutional Safe State, except bounded protective actions permitted under CONST-012.

Any protective action authorized in the Constitutional Safe State SHALL:

* comply with CONST-006;
* satisfy the pre-execution assurance required by CONST-009;
* satisfy the exposure-aware interpretation required by CONST-012;
* remain within every applicable constitutional safety boundary.

### Depends On

CONST-006 — Operational Safety Limits

CONST-009 — Pre-Trade Constitutional Assurance

CONST-012 — Safe Operational State

### Rationale

Financial systems cannot guarantee correctness.

They can only guarantee safe behaviour under uncertainty.

### Failure Scenario

Market data becomes inconsistent.

↓

Decision engine continues trading.

↓

Position increases.

↓

Loss accelerates.

### Risk of Violation

Critical

Potential account termination.

### Verification

RFC-001 SHALL define constitutional fail-safe behaviour.

### Derived Requirements

SAFE-001

SAFE-002

SAFE-003

### Traceability

RFC-001

RFC-005

---

## CONST-005

### Title

Independent Approval Authority

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

Approval SHALL remain logically independent from Decision generation.

Approval SHALL possess authority to reject any proposed trading action.

### Constraint

Decision components SHALL NOT approve their own trading actions.

### Rationale

A defect in signal generation SHALL NOT automatically become an executed trade.

### Failure Scenario

Signal bug generates BUY.

↓

Approval shares identical logic.

↓

Order executed.

↓

Capital loss.

### Risk of Violation

Critical

Loss amplification.

### Verification

Architecture SHALL demonstrate logical separation between Decision and Approval.

### Derived Requirements

ARCH-002 (reserved)

SAFE-004

---

## CONST-006

### Title

Operational Safety Limits

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

The Trading Operating System SHALL operate only within predefined operational safety limits.

Operational safety limits SHALL be externally configurable.

### Constraint

Any trading action that would cause a constitutional safety limit to be exceeded SHALL be rejected before execution.

If a constitutional safety limit is nonetheless exceeded, trading SHALL NOT continue.

### Rationale

No autonomous system may possess unlimited operational authority.

### Failure Scenario

Runaway strategy.

↓

Unlimited orders.

↓

Account destroyed.

### Risk of Violation

Critical

Unbounded financial loss.

### Verification

RFC-001 SHALL define safety limit policies.

### Derived Requirements

SAFE-010

SAFE-011

SAFE-012

---

## CONST-007

### Title

Venue Constraints

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

The Trading Operating System SHALL treat venue-imposed constraints as first-class decision inputs.

Examples include, but are not limited to,

- Trading halts
- Exchange session state
- Market availability
- Settlement restrictions
- Margin restrictions
- Exchange-imposed execution constraints

### Constraint

No trading decision SHALL ignore venue constraints.

### Rationale

Markets impose physical constraints that software cannot override.

Ignoring those constraints creates invalid trading decisions.

### Failure Scenario

Trading system assumes immediate execution.

↓

Exchange enters trading halt.

↓

Risk increases.

↓

Exit becomes impossible.

### Risk of Violation

Critical

Position trapped.

### Verification

Decision Context SHALL include venue state.

### Derived Requirements

ARCH-005 (reserved)

DEC-003 — venue-constraint decision requirement; instantiated in VER-DEV-001 and realized by RFC-004 §12 (Market-Model↔Safety Boundary); evidence DEC-EV-003

SAFE-015

---

## CONST-008

### Title

Authoritative Position

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

The Trading Operating System SHALL recognize an authoritative basis for trading positions, orders, and account state that its internal representation SHALL NOT override.

The authoritative basis SHALL be the reconciled state established from corroborating evidence, and SHALL NOT be any single internal or external source or any single API response.

No single source SHALL be treated as unconditionally correct where a single-source error could cause critical or catastrophic exposure.

### Constraint

Position, order, or account-state inconsistencies SHALL trigger constitutional safety behaviour.

An unresolved disagreement between evidence sources SHALL preserve unknown state and SHALL NOT be resolved by selecting the most convenient source.

### Rationale

Incorrect position information invalidates every downstream decision.

### Failure Scenario

Two evidence sources disagree about a position.

↓

The most convenient source is accepted as ground truth.

↓

Decision engine trades an incorrect quantity.

### Risk of Violation

Critical

Position corruption.

### Verification

Architecture SHALL define reconciliation mechanisms.

### Derived Requirements

ARCH-008 (reserved)

SAFE-020

---

## CONST-009

### Title

Pre-Trade Constitutional Assurance

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

Every trading action SHALL satisfy all constitutional requirements BEFORE execution.

No constitutional requirement SHALL be evaluated only after capital has been exposed.

### Constraint

Post-trade validation SHALL NOT substitute pre-trade assurance.

### Rationale

Executed trades are irreversible.

Risk prevention must therefore precede execution.

### Failure Scenario

Risk validation occurs after order submission.

↓

Oversized position is accepted.

↓

Capital impairment occurs.

### Risk of Violation

Critical

Permanent capital loss.

### Verification

RFC-001 SHALL demonstrate pre-trade constitutional enforcement.

### Derived Requirements

SAFE-021

SAFE-022

### Traceability

RFC-001

RFC-005

---

## CONST-010

### Title

Fail-Closed Configuration

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

Whenever constitutional safety configuration cannot be verified, the Trading Operating System SHALL transition to the constitutional safe state.

### Constraint

Missing, invalid, corrupted, or unreadable configuration SHALL NEVER increase operational authority.

### Rationale

Unknown safety configuration must never produce unknown risk.

### Failure Scenario

Daily loss limit cannot be loaded.

↓

Trading continues.

↓

Unlimited exposure.

### Risk of Violation

Critical

Unlimited operational risk.

### Verification

Safety Case SHALL define configuration validation.

### Derived Requirements

SAFE-030

SAFE-031

---

## CONST-011

### Title

Independent Safety Authority

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

The Trading Operating System SHALL always maintain an operational authority capable of suspending autonomous trading.

The authority SHALL remain logically independent from Decision Generation.

### Constraint

Decision components SHALL NOT disable constitutional safety authority.

### Rationale

Software defects must never disable their own containment mechanisms.

### Failure Scenario

Decision engine becomes unstable.

↓

Safety authority fails simultaneously.

↓

Trading continues.

### Risk of Violation

Critical

Runaway autonomous execution.

### Verification

Architecture SHALL demonstrate independence of constitutional safety authority.

### Derived Requirements

ARCH-011 (reserved)

SAFE-041

---

## CONST-012

### Title

Safe Operational State

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

The Trading Operating System SHALL always possess a constitutionally defined safe operational state.

The safe operational state SHALL account for:

* current positions;
* open and potentially live orders;
* margin and collateral obligations;
* venue availability;
* execution uncertainty;
* the ability or inability to reduce exposure;
* the aggregate risk effect of any proposed protective action.

The safe operational state SHALL prohibit new risk-increasing exposure.

A bounded protective action MAY be authorized only when its projected aggregate effect reduces constitutional risk and does not violate any applicable safety limit or constitutional requirement.

### Constraint

Safe state SHALL NOT be interpreted as simple inactivity.

An action SHALL NOT be considered protective solely because it is labelled as:

* an exit;
* a hedge;
* a stop;
* a reduction;
* a recovery action;
* an emergency action.

Its classification SHALL be determined from the projected aggregate post-action risk state.

Where the classification remains uncertain, the action SHALL be treated as risk-increasing.

### Depends On

CONST-001 — Long-Term Survivability

CONST-002 — Capital Preservation

CONST-006 — Operational Safety Limits

CONST-007 — Venue Constraints

CONST-009 — Pre-Trade Constitutional Assurance

### Rationale

Existing exposure continues to carry risk.

Safety therefore depends upon current position.

### Failure Scenario

Market data fails.

↓

System stops generating signals.

↓

Open leveraged position remains unmanaged.

### Risk of Violation

Critical

Uncontrolled exposure.

### Verification

RFC-001 SHALL define constitutional safe-state behaviour.

### Derived Requirements

SAFE-051

SAFE-052

---

## CONST-013

### Title

Safe Operational Start

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

Following system startup, restart, recovery, or communication loss, autonomous trading SHALL NOT resume until operational state has been constitutionally validated.

### Constraint

Unknown operational state SHALL prohibit new autonomous decisions.

### Rationale

Recovery introduces uncertainty.

Uncertainty must be eliminated before trading resumes.

### Failure Scenario

Application restarts.

↓

Internal state differs from operational state.

↓

Trading resumes immediately.

### Risk of Violation

Critical

Incorrect exposure.

### Verification

Architecture SHALL define operational validation.

### Derived Requirements

ARCH-015 (reserved)

SAFE-022, SAFE-023, SAFE-024, SAFE-035, SAFE-044, SAFE-046

---

## CONST-014

### Title

Irreversibility Principle

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

The Trading Operating System SHALL recognize that execution transfers real capital.

Execution SHALL therefore be treated as an irreversible operation.

Constitutional assurance SHALL always precede execution.

### Constraint

Replay, logging, audit, or monitoring SHALL NEVER replace preventive assurance.

### Rationale

Financial loss cannot always be recovered.

The prevention of irreversible mistakes is therefore constitutionally superior to post-event diagnosis.

### Failure Scenario

Incorrect order executes.

↓

Replay identifies root cause.

↓

Capital cannot be recovered.

### Risk of Violation

Critical

Permanent financial loss.

### Verification

All downstream specifications SHALL preserve pre-execution assurance.

### Derived Requirements

SAFE-010, SAFE-020, SAFE-021, SAFE-025, SAFE-033, SAFE-051, SAFE-052

ARCH-020 (reserved)

TEST-001 — testing-and-verification boundary requirement; instantiated in VER-DEV-001 and realized by RFC-010 §11 (Testing↔Safety Boundary); evidence TEST-EV-001

---

## CONST-015

### Title

Bounded Human Authority

### Classification

Constitutional Requirement

### Priority

Critical

### Requirement

The Trading Operating System SHALL treat authorized human authority as a necessary but bounded element of the safety model.

Every human or operator action that grants, modifies, suspends, restores, or increases safety-relevant authority SHALL be authenticated, scoped, attributable, reviewable, and auditable.

Human authority SHALL NOT bypass, disable, weaken, or override a constitutional safety control, and SHALL NOT extend exposure, operational authority, or new-risk capacity beyond the operational safety limits required by CONST-006 or beyond the independently governed maximum operational authority (the Hard Safety Envelope defined by the Safety Case).

No single human acting alone SHALL possess unilateral authority to increase new-risk authority beyond bounded protective action. Any risk-increasing re-arm, live-authorization issuance, or production-scope promotion SHALL require independent approval established through an approved satisfaction path.

### Constraint

A human-authorized action SHALL be subject to the same constitutional safety requirements as an autonomous action. Being human-initiated SHALL NOT exempt an action from CONST-006, CONST-009, CONST-012, or CONST-014.

This requirement SHALL NOT be construed to mandate any specific number of natural persons. The independent-approval obligation for risk-increasing re-arm, issuance, and promotion SHALL be discharged through the approved satisfaction paths defined by its derived Safety-Case requirement, which SHALL fail closed when the required independence cannot be established.

Emergency human authority SHALL be limited to actions that restrict, suspend, or contain, and SHALL NOT become a path to increase new risk.

### Depends On

CONST-006 — Operational Safety Limits

CONST-009 — Pre-Trade Constitutional Assurance

CONST-011 — Independent Safety Authority

CONST-012 — Safe Operational State

### Rationale

Automation exists to improve consistency and control, not to remove responsible human authority; that authority is part of the safety model but is not an unbounded override.

A single mistaken, stressed, or compromised human is a credible source of catastrophic loss, so human authority is bounded exactly as autonomous authority is.

Fixing the number of natural persons at the constitutional level would foreclose governed single-operator operation; the number and the independence mechanism are therefore delegated to the Safety Case, which preserves a fail-closed posture.

### Failure Scenario

An operator, acting alone, re-arms live trading after a material failure.

↓

No independent approval or attestation constrains the action.

↓

A single mistaken or compromised human expands new-risk authority.

↓

Exposure is created outside the safety envelope.

### Risk of Violation

Critical

Single-actor bypass of safety authority.

### Verification

RFC-001 SHALL define bounded-human-authority safety behaviour and the independent-approval requirement for risk-increasing re-arm, issuance, and promotion.

### Derived Requirements

SAFE-042

SAFE-046

SAFE-053

### Traceability

RFC-001 Safety Case

RFC-002 Architecture

DR-0001 Single-Operator Live Governance

---

# 8. Constitutional Axioms

The following axioms define the philosophical foundation of the Trading Operating System.

These axioms are not implementation requirements.

They define assumptions from which all constitutional requirements are derived.

---

## AX-001

Markets are observable.

Markets are not predictable.

---

## AX-002

Every decision requires complete context.

No context.

No decision.

---

## AX-003

Safety precedes profitability.

Profit SHALL NEVER justify weakening safety.

---

## AX-004

Decision quality is evaluated over populations of decisions.

Never over individual trades.

---

## AX-005

Complexity requires justification.

Simplicity is the default architectural choice.

---

# 9. Constitutional Boundaries

This Constitution defines **WHY**.

RFC-001 Safety Case defines **WHAT SHALL NEVER HAPPEN**.

Architecture RFCs define **WHAT EXISTS**.

Decision Framework defines **HOW DECISIONS ARE MADE**.

Implementation defines **HOW SOFTWARE IS BUILT**.

No lower-level document SHALL redefine constitutional intent.

---

# 10. Decision Hierarchy

The following hierarchy is immutable.

The Constitution defines only the immutable decision lifecycle.

Concrete implementations SHALL be specified by Architecture RFCs.

The ordering SHALL remain invariant.

```
Observation
        │
        ▼
Context Construction
        │
        ▼
Interpretation
        │
        ▼
Decision
        │
        ▼
Approval
        │
        ▼
Execution
        │
        ▼
Audit
```

No implementation SHALL bypass, remove or reorder these stages.

---

# 11. Decision Context

Every decision SHALL consume immutable Decision Context.

The Constitution intentionally does not enumerate concrete context types.

Context taxonomy SHALL be defined by Architecture RFCs.

Decision logic SHALL treat all contexts as read-only.

---

# 12. Constitutional Governance

The governance hierarchy SHALL be

```
Trading Constitution
        │
        ▼
Safety Case
        │
        ▼
Architecture RFCs
        │
        ▼
Decision Framework
        │
        ▼
Implementation
        │
        ▼
Operational Procedures
```

Higher-level specifications SHALL govern lower-level specifications.

Lower-level specifications SHALL NOT reinterpret higher-level intent.

No Part-2 or Part-3 artifact — RFC-003 through RFC-011, ADR-DEV-001 through ADR-DEV-015, and their verification evidence — SHALL widen, relax, or reinterpret any Part-1 authority, limit, gate, or Hard Safety Envelope constraint. A subordinate-layer artifact MAY only narrow authority, never widen it.

---

# 13. Engineering Governance

Architectural modifications SHALL follow the approved governance process.

The governance process SHALL be specified independently from this Constitution.

Implementation SHALL NEVER become the source of architectural truth.

---

# 14. Requirements Traceability

Every constitutional requirement SHALL be traceable.

Traceability SHALL exist from

```
Requirement
        │
        ▼
Architecture
        │
        ▼
Implementation
        │
        ▼
Verification
        │
        ▼
Operational Evidence
```

No implementation SHALL exist without traceability to an approved constitutional requirement.

The following requirements SHALL be interpreted as a single constitutional safety chain:

```text
CONST-004 — Fail-Safe Operating Principle
        ↓
CONST-012 — Safe Operational State
        ↓
CONST-006 — Operational Safety Limits
        ↓
CONST-009 — Pre-Trade Constitutional Assurance
        ↓
CONST-014 — Irreversibility Principle
```

CONST-004 defines when safe-state authority applies.

CONST-012 defines the constitutional properties of that state.

CONST-006 defines the safety boundaries that remain applicable.

CONST-009 requires assurance before any permitted action is executed.

CONST-014 establishes why preventive assurance cannot be replaced by post-execution recovery or audit.

No requirement in this chain SHALL be interpreted independently in a way that weakens another requirement in the chain.

---

# 15. Constitutional Evidence

Every constitutional requirement SHALL define acceptable evidence demonstrating compliance.

Evidence MAY include

- Safety Case
- Test Results
- Replay Logs
- Audit Reports
- Formal Review

### Verification Obligation

Every constitutional requirement's verification obligation SHALL be discharged by its referenced specification before the system is operated in reliance on that requirement.

An undischarged verification obligation SHALL be treated as unverified safety configuration under CONST-010 and SHALL force the constitutional safe state.

A constitutional requirement whose verification has not been demonstrated SHALL NOT be relied upon as an operational safety guarantee.

### Rationale

Verification requires objective evidence.

Unverified safety guarantees provide no protection and SHALL NOT be relied upon.

---

# 16. Definition of Success

The Trading Operating System SHALL be considered successful only if all of the following remain simultaneously true.

- Long-term operational survivability
- Capital preservation
- Positive expectancy
- Deterministic decision process
- Replayable decisions
- Explainable decisions
- Safety compliance
- Production stability

Peak backtest return SHALL NOT constitute project success.

---

# 17. Non-Goals

The Trading Operating System does NOT pursue

- Maximum individual trade profit
- Maximum annual return
- Strategy complexity
- AI-driven autonomous architecture
- Over-fitted backtests
- Framework development without measurable engineering value

---

# 18. Amendment Process

This Constitution SHALL be amended only through a formal RFC process.

Every amendment SHALL include

- Motivation
- Constitutional impact assessment
- Backward compatibility assessment
- Migration strategy
- Review history

Constitutional amendments SHALL require explicit ratification before becoming effective.

Unratified drafts SHALL NOT supersede previously ratified constitutional requirements.

---

# Appendix A — Review History

v0.1

Initial Draft

v0.2

Added Constitutional Axioms

v0.3

Added Constitutional Invariants

v0.4

Added Decision Hierarchy

v0.5

Added Governance

v0.6

Applied PATCH-0001

v0.7

Applied PATCH-0002

v0.8

Applied PATCH-0003

v0.9

Applied PATCH-0004

v0.10

Applied PATCH-0005

v0.11

Applied PATCH-0006

Reconciled the constitutional safe-state definition.

Replaced unconditional "no new exposure" wording with "no new risk-increasing exposure."

Clarified that bounded protective actions may be authorized only when their projected aggregate effect reduces constitutional risk and remains within all applicable safety boundaries.

Aligned CONST-004 with CONST-012.

v0.12

Applied PATCH-0009 (CORPUS-REVIEW-0001 Theme A, M-01..M-04).

Encoded the full seven-tier North Star ordering in Constitutional Precedence and added a North Star to constitutional-requirement mapping table; fixed CONST-003 (Positive Expectancy) as subordinate to the operational-safety and integrity requirements, in particular CONST-005 and CONST-009.

Removed the "autonomous" qualifier from CONST-004's safe-state constraint so that no risk-increasing action, whether autonomous or human-authorized, is authorized in the Constitutional Safe State except bounded protective action.

Added CONST-015 (Bounded Human Authority) as the constitutional parent of RFC-001 SAFE-053 owed by DR-0001 §6; it does not mandate any number of natural persons and preserves the governed single-operator satisfaction path.

Reframed CONST-008 in evidence terms (the authoritative basis is the reconciled state from corroborating evidence, not any single source) and added an Authoritative-State term-relationship table to Section 6.

v0.13

Applied PATCH-0012 (CORPUS-REVIEW-0001 CR-01, Part-2/3 register consolidation).

Added the narrow-only governance meta-principle to §12 Constitutional Governance: no Part-2 or Part-3 artifact SHALL widen, relax, or reinterpret any Part-1 authority, limit, gate, or Hard Safety Envelope constraint, and a subordinate-layer artifact MAY only narrow authority; cross-referenced from the §5 reserved-namespace note.

Instantiated the reserved DEC-xxx and TEST-xxx namespaces through governance: CONST-007's DEC-003 is realized by RFC-004 §12 (evidence DEC-EV-003) and CONST-014's TEST-001 by RFC-010 §11 (evidence TEST-EV-001), both registered in VER-DEV-001 / EVIDENCE-REGISTER-DEV; ARCH-xxx remains reserved.

Named the CONST-003 composite discharge (RFC-003 §12 framework obligation, RFC-006 §11 methodology, ADR-002-025 live-readiness RLP-EV-001..012), declarable in full only via the ADR-002-025 restricted-live evidence.
