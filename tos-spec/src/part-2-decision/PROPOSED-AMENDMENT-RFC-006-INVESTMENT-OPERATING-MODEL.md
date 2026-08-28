# Proposed RFC-006 Amendment — Investment Operating Model and Execution Survivability

- **Status:** Proposed G6 amendment — non-governing until re-ratified
- **Candidate target:** RFC-006, coordinated RFC-004/RFC-005 and ADR-002-002/018/021 amendments
- **Date:** 2026-08-02
- **Profile schema:** `profiles/INVESTMENT-OPERATING-PROFILE.schema.yaml`
- **Evidence family:** IOM-EV-001..008 in VER-DEV-001 and EVIDENCE-REGISTER-DEV
- **Authority:** none; this proposal allocates no capital, risk capacity, account, broker, or live scope

## 1. Defect and governing home

ARCHITECTURE-GATE-STATUS §4.6 registers G-02 through G-05 as future gaps:
capital/portfolio allocation, market-data ingestion and continuity,
multi-account/multi-broker concurrency, and end-to-end safety latency. Safety
mechanisms are substantially specified, but the investment mandate and the
operating conditions under which those mechanisms preserve both safety and edge
are not.

RFC-006 already owns portfolio-risk and economic methodology, so it is the
smallest home for mandate, allocation, degradation, and investment ownership.
The amendment is coordinated rather than duplicated: RFC-004 owns market/context
semantics, RFC-005 owns execution behavior and latency accounting,
ADR-002-018 owns Critical Input admission after acquisition, ADR-002-021 owns
aggregate risk decisions, and ADR-002-002 alone owns risk-capacity mutation.

## 2. Mandatory authority separation

Two decisions SHALL remain distinct:

- **Investment capital allocation** selects the mandate, benchmark, strategies,
  accounts, capital amounts, strategy risk budgets, correlation/crowding
  treatment, and retirement rules. The Investment Authority owns this decision.
- **Risk-capacity authorization** decides whether a proposed economic effect fits
  the approved safety/risk envelope and commits capacity. Risk Authority owns the
  Aggregate Risk Policy/Decision; only the RCL may mutate capacity.

RCL headroom is not available investment capital. An investment allocation does
not create RCL headroom or approve an order. A risk-capacity grant does not select
a strategy, establish a benchmark, or allocate capital. The smaller admissible
scope controls, and disagreement or missing ownership yields no new allocation.

## 3. Investment mandate and lifecycle (G-02)

Before any cross-strategy or cross-account allocation, an approved, versioned
Investment Operating Profile SHALL bind:

- the Investment Mandate Owner and Investment Authority;
- objectives, benchmark and benchmark version, eligible strategies and versions,
  capital/accounts/brokers/venues, horizon, liquidity needs, and prohibited scope;
- strategy risk budgets and a portfolio aggregation rule, without treating those
  budgets as RCL capacity;
- correlation, crowding, concentration, liquidity, and benefit-recognition rules;
- gross and net attribution, benchmark-relative contribution, total costs,
  capital efficiency, deployable capacity, turnover, and capacity utilization;
- degradation, review, suspension, revalidation, capital-withdrawal, and retirement
  triggers, including edge decay and material strategy/profile changes.

The Investment Authority owns mandate, benchmark, allocation, and retirement.
Risk Authority independently owns hard risk/safety bounds and aggregate-risk
methodology. Strategy owners provide hypotheses and implementation; they cannot
self-allocate. Finance/operations records capital and attribution but cannot
substitute for either authority. Independent review remains separate from
authoring/integration.

Unknown correlation, crowding, liquidity, capacity, attribution, or capital
efficiency contributes no diversification or allocation benefit.

## 4. Market-data acquisition and continuity (G-03)

ADR-002-018 admission SHALL be preceded by a governed acquisition/continuity
contract. The Market Data Owner and Data Operations Owner SHALL bind each exact
source, instrument/calendar/session scope, schema/version, timestamp semantics,
entitlement, redundancy, and provenance.

The contract SHALL define:

- expected sequence/cadence and session-aware completeness;
- duplicate, reordering, staleness, clock, value-range, schema, and source-identity
  checks;
- gap detection, source disagreement, quarantine, alerting, and escalation;
- bounded backfill source, reconciliation, late-arrival policy, and lineage;
- warm-up and recovery completeness before a value can be offered to
  ADR-002-018;
- fail-closed behavior for missing, stale, gapped, ambiguous, or unverified data.

Backfill never silently rewrites a prior decision context. It produces a new
versioned observation and invalidates dependent queued work when the admitted
truth changes. A cache, most recent value, healthy feed process, or dashboard is
not evidence of continuity and is not authority.

## 5. Multi-account and multi-broker concurrency (G-04)

Initial scope remains single-account/single-broker until a profile is approved
and IOM evidence is complete. Before a second concurrent account or broker, the
profile SHALL bind:

- legal/operator principal, account, broker, environment, product, venue,
  currency, and strategy scope;
- writer-epoch/lease ownership and fencing domain;
- the RCL namespace and aggregate-risk boundary, including cross-scope exposure
  and unproven-netting treatment;
- per-scope order/attempt identity, reconciliation, idempotency, retry,
  cancellation, and replacement rules;
- partial outage, broker disagreement, delayed fill, split-brain, and recovery
  behavior;
- double-trade prevention across legacy/TOS and across accounts/brokers;
- consolidated operator safety-state ownership and escalation.

No account or broker may borrow another scope's authorization, evidence,
capability, writer epoch, sequence, or capacity. If aggregate visibility is
incomplete, no cross-scope risk benefit is credited and affected new risk is
blocked.

## 6. End-to-end latency and performance survivability (G-05)

The approved profile SHALL allocate human-owned, versioned budgets across the
complete decision-to-observation path: acquisition, continuity/admission,
context/capsule construction, deterministic decision, independent approval,
aggregate risk, RCL commit, construction/conformance, queue/network/broker,
acknowledgement/fill, reconciliation, evidence, and protective response.

Each bound SHALL declare scope, clock and percentile/statistic, measurement
point, load/fault conditions, owner, rationale, alert, stop rule, and invalidation
behavior. There are no default numbers in this amendment.

Verification SHALL demonstrate under representative load and failure that:

- freshness and ordering remain valid at every gate;
- no timeout, backlog, retry, or batching path bypasses approval, capacity,
  currentness, reconciliation, or protective controls;
- protection and halt propagation meet their approved bounds;
- total realized latency, missed opportunities, rejections, partial fills,
  spread/slippage/impact, and safety-induced opportunity loss are included in
  ECO evidence;
- net expectancy and deployable capacity still meet the separately approved
  economic profile.

A latency target SHALL NOT be met by weakening, skipping, caching away, or
reordering a safety gate. If safety and expectancy do not jointly survive, the
scope is not deployable; optimization is not authorization.

## 7. Result semantics and scope restrictions

- **PASS:** the exact approved profile and scope have complete governed evidence,
  independent review, and no unresolved disqualifier.
- **FAIL:** complete evidence establishes violation of a mandate, continuity,
  concurrency, or latency requirement.
- **INCONCLUSIVE:** any required owner, profile, source, scope, bound, measurement,
  review, or evidence is missing, stale, conflicting, or insufficient.

No result is an order authorization, risk-capacity mutation, investment
allocation, ADR acceptance, restricted-live authorization, or production
authorization. Before G6/G7 and evidence completion, G-02 through G-05 restrict
scope: no cross-strategy/account allocation, no ungoverned feed admission, no
second concurrent account/broker, and no latency-sensitive restricted-live
claim.

## 8. Verification family

| Case | Positive obligation |
|---|---|
| IOM-EV-001 | exact mandate, benchmark, accountable owners, and scope binding |
| IOM-EV-002 | allocation versus risk-capacity separation and strategy risk budgets |
| IOM-EV-003 | portfolio attribution, correlation/crowding, capital efficiency, capacity/turnover, degradation, and retirement |
| IOM-EV-004 | source acquisition, continuity, gap detection, quarantine, backfill, and pre-ADR-002-018 admission |
| IOM-EV-005 | account/broker/writer/RCL/aggregate-risk scope isolation |
| IOM-EV-006 | concurrent failure fencing, reconciliation, queued-work invalidation, and double-trade prevention |
| IOM-EV-007 | complete end-to-end latency budget under load and fault |
| IOM-EV-008 | joint safety/economic survivability and non-authority honesty |

All rows begin `NOT_IMPLEMENTED`. A document or schema is not evidence.

## 9. Coordinated G6/G7 decision package

The System Owner must select GOV-001 G6 before any text becomes governing. The
Architecture Board assigns coordinated RFC-004/RFC-005 and ADR touch points;
Investment Authority owns mandate/allocation/economic bounds; Risk Authority owns
safety/aggregate-risk/latency safety bounds; Market Data Owner owns source and
continuity contracts; account/broker operations owners own operating scopes; an
independent reviewer reviews both amendment and evidence.

The act requires version increments, exact amendment text, updated G5 records,
and independent EV-L0 review. If the amendment is rejected, the rollback is to
retain G-02 through G-05 as explicit scope-restricting open gaps—not to infer
their closure from existing safety machinery.
