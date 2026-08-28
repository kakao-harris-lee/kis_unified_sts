# Proposed RFC-006 Amendment — Economic Viability and CONST-003 Evidence

- **Status:** Proposed G6 amendment — non-governing until re-ratified
- **Candidate target:** RFC-006 v0.3, coordinated RFC-000/RFC-003/ADR-002-025 traceability amendment
- **Date:** 2026-08-02
- **Profile schema:** `profiles/ECONOMIC-VIABILITY-PROFILE.schema.yaml`
- **Evidence family:** ECO-EV-001..012 in VER-DEV-001 and EVIDENCE-REGISTER-DEV
- **Authority:** none; this proposal grants no admission, capacity, live scope, or production authority

## 1. Defect and smallest governing home

The Ratified chain currently points CONST-003 completion to RLP-EV-001..012.
Those cases govern restricted-live trial scope, safety separation, abort,
promotion, recovery, and status honesty. They do not positively establish net
expectancy or economic viability. DEC-EV-001..005 inspect decision-boundary
conformance only.

RFC-006 §11 already owns expectancy methodology, so a G6 amendment to RFC-006 is
the smallest governing home. RFC-000, RFC-003, and ADR-002-025 need coordinated
traceability corrections, not duplicate methodology.

## 2. Proposed completion rule

CONST-003 completion SHALL require all four layers:

1. RFC-003 framework-level decision-quality obligation;
2. RFC-006 methodology plus an **approved and exact-version-bound Economic
   Viability Profile**;
3. every applicable ECO-EV-001..012 case in an accepting evidence state after
   governed execution and independent review; and
4. every applicable RLP-EV-001..012 safety/trial-governance case in an accepting
   evidence state.

RLP is necessary for restricted-live governance but insufficient for positive
expectancy. ECO is necessary for economic viability but creates no live
authority. Backtest-only evidence cannot complete the rule. A strategy cannot
inherit another strategy's result, and a portfolio claim must bind the exact
strategy/version, population, benchmark, capital scope, and evidence set.

## 3. Pre-registration and evidence identity

Before observing evaluation or restricted-live results, the evidence package
must bind:

- strategy and Decision Policy identity/version;
- falsifiable hypothesis and selection history;
- target population and inclusion/exclusion rules;
- benchmark and benchmark version;
- evaluation horizon and regime coverage;
- stop, abort, early-termination, and result-retention rules;
- data, feature, cost, execution, safety, and portfolio profile versions;
- analysis plan, uncertainty method, selection correction, and result semantics.

A post-hoc change is a new preregistration and evidence identity. Negative and
inconclusive runs remain retained; optional stopping cannot turn them into PASS.

## 4. Complete net economic effect

The result must account for every applicable economic effect, with provenance
and uncertainty:

- fees, commissions, taxes, financing, borrow, and settlement costs;
- quoted and effective spread, slippage, and market impact;
- missed trades, rejections, partial fills, cancellations, and replacements;
- decision, approval, queue, network, broker, and fill latency;
- safety-induced opportunity loss, including conservative vetoes, capacity
  retention, halts, recovery barriers, and unavailable protective paths.

Missing or optimistic cost components yield `INCONCLUSIVE`, never an assumed
zero. No safety gate may be weakened to improve measured expectancy.

## 5. Statistical and selection discipline

The evidence package must report an uncertainty interval and estimation error,
apply the approved minimum effective-sample discipline, and bind the approved
multiple-testing / selection-bias correction. It must identify the strategy
search universe, rejected candidates, data reuse, researcher degrees of freedom,
and any dependency that reduces effective sample size.

Results must be stratified by the pre-registered regimes and must disclose
heterogeneity, instability, tail sensitivity, and missing regime coverage. A
favorable pooled estimate cannot hide a disqualifying or unknown required scope.

## 6. Generalization and real-execution evidence

Out-of-sample evidence must be temporally and procedurally separated from model
selection and must pass leakage/provenance checks. Backtest and simulation remain
evidence toward a hypothesis, not proof.

Restricted-live evidence must bind exact trial scope and RLP governance, and must
measure realized costs, latency, rejections, partial fills, missed opportunity,
and safety effects. Neither out-of-sample nor restricted-live evidence substitutes
for the other when the approved profile requires both.

## 7. Portfolio and capital economics

The evaluation must report, at the approved capital scope:

- turnover and turnover stability;
- deployable capacity and capacity sensitivity;
- capital efficiency, including capital tied by pending/unknown effects;
- drawdown magnitude, duration, recovery, and path dependence;
- correlation, crowding, and marginal contribution relative to the existing
  book, without assuming unproven netting or hedge benefit;
- edge/alpha decay, degradation triggers, and retirement/revalidation triggers.

Risk-capacity headroom is not investment allocation. Passing this contract does
not allocate capital, approve a mandate, or accept correlation benefit.

## 8. Result semantics

The exact human-owned bounds come only from an approved profile; this proposal
defines no numeric threshold.

- **PASS:** all required profile fields and evidence cases are complete; every
  human-owned bound is met under the approved comparison; uncertainty,
  correction, regime, capacity, portfolio, decay, out-of-sample, and applicable
  restricted-live obligations pass; independent review is signed.
- **FAIL:** complete governed evidence establishes violation of at least one
  approved disqualifier or bound. Failure remains retained and cannot be hidden by
  narrowing the reported population after observation.
- **INCONCLUSIVE:** any required profile, cost component, sample basis, correction,
  regime, capacity estimate, portfolio comparison, evidence stage, or independent
  review is missing, stale, contradictory, or insufficient. INCONCLUSIVE is not
  PASS and grants nothing.

No result is ADR acceptance, strategy admission, capital allocation,
restricted-live authorization, production authority, or permission to weaken a
safety gate.

## 9. Evidence family

| Case | Positive obligation |
|---|---|
| ECO-EV-001 | exact pre-registration and immutable evaluation identity |
| ECO-EV-002 | complete total-cost and safety-opportunity-loss accounting |
| ECO-EV-003 | uncertainty interval, effective sample, and estimation error |
| ECO-EV-004 | multiple-testing and selection-bias correction |
| ECO-EV-005 | regime dependence and required-scope stability |
| ECO-EV-006 | leakage-controlled out-of-sample generalization |
| ECO-EV-007 | exact-scope restricted-live economic observation bound to RLP |
| ECO-EV-008 | turnover, deployable capacity, and capital efficiency |
| ECO-EV-009 | drawdown magnitude, duration, recovery, and path behavior |
| ECO-EV-010 | existing-book correlation, crowding, and marginal contribution |
| ECO-EV-011 | edge decay, degradation, revalidation, and retirement triggers |
| ECO-EV-012 | complete verdict, RLP/ECO separation, and non-authority honesty |

All twelve rows are initially `NOT_IMPLEMENTED`. Registration and schema
creation are not evidence execution.

## 10. Coordinated traceability amendment text

If the System Owner selects GOV-001 G6, the amendment must replace every
RLP-only completion statement in:

- RFC-000 CONST-003 Derived Requirements / Traceability;
- RFC-003 §§12 and 15 completion note;
- RFC-006 §§11 and 16 completion note; and
- ADR-002-025 §§26/29 approval and traceability text.

The common replacement is:

> CONST-003 completion requires the RFC-003 framework obligation, RFC-006
> methodology bound to an approved Economic Viability Profile, complete governed
> ECO-EV-001..012 economic evidence, and complete applicable RLP-EV-001..012
> restricted-live governance evidence. RLP alone cannot establish expectancy;
> ECO alone grants no live authority.

The G6 act requires version increments, citation-integrity review, independent
EV-L0 delta review, and new G5 records. Until then the Ratified versions remain
the governing text, while current-status surfaces conservatively prohibit an
RLP-only CONST-003 completion claim because the semantic discrepancy is known.

## 11. Human decision gate

Required before this proposal becomes governing:

1. System Owner chooses and authorizes the coordinated G6 amendment.
2. Architecture Board confirms layering and traceability.
3. Investment Authority owns every economic bound and disqualifier.
4. Risk Authority co-owns safety/risk/capacity/correlation bounds.
5. Independent reviewer approves the amendment and later reviews each evidence
   package without being its author/integrator.

Default before those acts: profile unapproved, all ECO rows `NOT_IMPLEMENTED`,
CONST-003 incomplete, restricted-live not authorized, production not authorized.
