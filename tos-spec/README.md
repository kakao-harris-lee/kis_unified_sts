# Trading Operating System Specification

A layered safety-architecture specification for an autonomous trading system. Read
it as a book with `mdbook`, or navigate the source directly; the full table of
contents is in [`src/SUMMARY.md`](src/SUMMARY.md).

The specification is a strict authority hierarchy — every layer is governed by the
ones above it (RFC-000 §9 layering), and no lower document may redefine the intent
of a higher one.

## Part 0 — Introduction

- [Vision](src/part-0-introduction/vision.md) — what the system is for
- [Philosophy](src/part-0-introduction/philosophy.md) — the safety principles every later document inherits

## Part 1 — Foundation (safety architecture)

The canonical safety-architecture documents live under `src/part-1-foundation/`.
Start with:

1. [RFC-000 — Trading Constitution](src/part-1-foundation/RFC-000-Trading-Constitution.md)
2. [RFC-001 — Safety Case](src/part-1-foundation/RFC-001-Safety-Case.md)
3. [RFC-002 — Trading Operating System Architecture](src/part-1-foundation/RFC-002-Architecture.md)
4. [ADR-002-001 — Degraded-Mode Protective Capacity](src/part-1-foundation/ADR-002-001-Degraded-Mode-Protective-Capacity.md) through ADR-002-030 — the thirty-record ADR-002 architecture-decision series
5. [VER-002-001 — Safety-Critical Architecture Verification](src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md) and the [Evidence Register](src/part-1-foundation/verification/EVIDENCE-REGISTER-002.md)
6. [Architecture Gate Status and semantic merge map](src/part-1-foundation/ARCHITECTURE-GATE-STATUS.md)

## Part 2 — Decision Framework

How the system decides what to do, subordinate to Part 1 (`src/part-2-decision/`).

- [RFC-003 — Decision Framework](src/part-2-decision/RFC-003-Decision-Framework.md)
- [RFC-004 — Market Model](src/part-2-decision/RFC-004-Market-Model.md)
- [RFC-005 — Execution Model](src/part-2-decision/RFC-005-Execution-Model.md)
- [RFC-006 — Risk Model](src/part-2-decision/RFC-006-Risk-Model.md)
- [RFC-007 — Portfolio Hedge Model](src/part-2-decision/RFC-007-Portfolio-Hedge-Model.md)

## Part 3 — Development

How a strategy is authored, tested, and operated within the Part 1/2 boundaries
(`src/part-3-development/`).

- [RFC-008 — Strategy DSL](src/part-3-development/RFC-008-Strategy-DSL.md)
- [RFC-009 — Agent Guide](src/part-3-development/RFC-009-Agent-Guide.md)
- [RFC-010 — Testing Strategy](src/part-3-development/RFC-010-Testing-Strategy.md)
- [RFC-011 — Operational Guidelines](src/part-3-development/RFC-011-Operational-Guidelines.md)

Decision records (the `ADR-DEV` series, resolving Part-3 RFC open questions):

- [ADR-DEV-001 — DSL Realization and Purity/Escape-Closure Enforcement](src/part-3-development/ADR-DEV-001-DSL-Realization-and-Purity-Escape-Closure-Enforcement.md)
- [ADR-DEV-002 — Artifact Reproducibility and Identity Granularity](src/part-3-development/ADR-DEV-002-Artifact-Reproducibility-and-Identity-Granularity.md)
- [ADR-DEV-003 — External Value: Capture, Staleness, and Re-Authoring](src/part-3-development/ADR-DEV-003-External-Value-Capture-Staleness-and-Re-Authoring.md)
- [ADR-DEV-004 — Authoring Provenance, Versioning/Substitution, and Admission Binding](src/part-3-development/ADR-DEV-004-Authoring-Provenance-Versioning-and-Admission-Binding.md)
- [ADR-DEV-005 — Independent Review of AI-Authored Strategies and Rationale Representation](src/part-3-development/ADR-DEV-005-Independent-Review-of-AI-Authored-Strategies-and-Rationale-Representation.md)
- [ADR-DEV-006 — Bulk and Family Authoring: Per-Artifact Review at Scale](src/part-3-development/ADR-DEV-006-Bulk-and-Family-Authoring-Per-Artifact-Review-at-Scale.md)
- [ADR-DEV-007 — Strategy Output Semantics: No-Action, Flat, and the Atomic Unit](src/part-3-development/ADR-DEV-007-Strategy-Output-Semantics-No-Action-Flat-and-Atomic-Unit.md)
- [ADR-DEV-008 — Authoring Under a Degraded or Unavailable Companion Model](src/part-3-development/ADR-DEV-008-Authoring-Under-a-Degraded-or-Unavailable-Companion-Model.md)
- [ADR-DEV-009 — Containment Escape-Vector Minimum Set and Currency](src/part-3-development/ADR-DEV-009-Containment-Escape-Vector-Minimum-Set-and-Currency.md)
- [ADR-DEV-010 — Backtest Admissibility, Cost Realism, and Disqualifiers](src/part-3-development/ADR-DEV-010-Backtest-Admissibility-Cost-Realism-and-Disqualifiers.md)
- [ADR-DEV-011 — Test Assumptions and the Pre-Deployment / Runtime-Monitoring Boundary](src/part-3-development/ADR-DEV-011-Test-Assumptions-and-the-Pre-Deployment-Runtime-Monitoring-Boundary.md)
- [ADR-DEV-012 — Re-Arm Reconciled-State Checklist and Barrier Binding](src/part-3-development/ADR-DEV-012-Re-Arm-Reconciled-State-Checklist-and-Barrier-Binding.md)
- [ADR-DEV-013 — Operator Boundaries: Break-Glass and Containment](src/part-3-development/ADR-DEV-013-Operator-Boundaries-Break-Glass-and-Containment.md)
- [ADR-DEV-014 — Operator Observability and "Withhold Re-Arm" as a First-Class Outcome](src/part-3-development/ADR-DEV-014-Operator-Observability-and-Withhold-Re-Arm-as-a-First-Class-Outcome.md)
- [ADR-DEV-015 — Operator Authority-Scope Expression and Revocation](src/part-3-development/ADR-DEV-015-Operator-Authority-Scope-Expression-and-Revocation.md)

## Status

The deterministic [Current TOS Status](src/CURRENT-STATUS.md) is generated from
canonical document headers, the two evidence-register CSVs, and
`src/AUTHORITY-STATUS.csv`. It currently keeps these independent facts separate:

- all 13 RFC-class baselines are `Ratified`;
- all 45 ADRs remain `Proposed`;
- Part 1 has 372 evidence rows: 291 `NOT_IMPLEMENTED`, 79 `READY`, and 2 `PASS`;
- the development register has 118 `NOT_IMPLEMENTED` rows, including twelve
  Proposed economic-viability and eight Proposed investment-operating cases;
- restricted-live and production authorization are both `NOT_AUTHORIZED`.

Ratification, document review, implementation, registration, unit tests, and an
evidence `PASS` do not confer ADR acceptance or live readiness. See
[Architecture Gate Status](src/part-1-foundation/ARCHITECTURE-GATE-STATUS.md) for
the governance record and open decision gates.

The non-authorizing [Migration and Conformance Register](src/MIGRATION-CONFORMANCE-REGISTER.md)
maps configured legacy broker routes, all TOS packages and trust seams, cutover/
rollback/direct-egress criteria, and the still-Proposed Q5/Q6 debt.

Verification assets are under `src/part-1-foundation/verification/`. The
`patches/` and `reviews/` directories are **git-excluded working artifacts**
(`tos-spec/.gitignore`), not tracked spec content and not separately operative
after consolidation; the committed record of what a patch changed is the semantic
merge map in [Architecture Gate Status](src/part-1-foundation/ARCHITECTURE-GATE-STATUS.md) §3.
