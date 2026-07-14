# Upstream Constraints on the Decision Layer (RFC-003 – RFC-007)

> **NON-NORMATIVE — RESEARCH INPUT ONLY.** Grounding dossier extracted from
> part-0 (`vision.md`, `philosophy.md`) and part-1 (RFC-000/001/002 + ADR-002-*).
> Defines no requirements and grants no authority. Citations point at the ratified
> constitution (RFC-000), the drafted Safety Case (RFC-001), and drafted
> architecture (RFC-002/ADRs — "authoritative design intent, not yet Accepted").
> Verify against the live files before quoting in a future RFC.

**Scope confirmed:** `src/part-2-decision/RFC-003..007-*.md` are all **empty
0-byte files** (re-confirmed 2026-07-14). Everything below is extracted from
part-0 and part-1, the only ratified/drafted upstream sources.

---

## 1. Decision layer's intended role

**vision.md §6.1 "Strategies Propose; the System Authorizes"** (lines 161–185): "A
trading strategy is treated as a proposer of intent, not as the final authority...
The operating system independently determines whether the proposed action is:
based on trustworthy context; consistent with current positions; within account
and portfolio risk capacity; permitted by the venue; permitted by live
authorization; safe to transmit; safe to retry; safe to continue during
degradation. No strategy is expected to possess unilateral authority over real
capital."

**vision.md §7.5 "Replaceable Strategies"** (lines 412–424): "Strategies can
evolve, fail, or be removed without requiring the safety model to be reinvented.
The system's core safety and execution integrity do not depend on a particular:
signal; model; indicator; market regime; holding period; trading style."

**philosophy.md §13 "Strategies Are Replaceable; Safety Is Durable"** (lines
413–448): "The system therefore treats a strategy as an untrusted proposer. A
strategy may express: intent; expected edge; desired quantity; preferred timing;
execution constraints. **It does not independently control**: live authority;
final approval; aggregate risk capacity; safety limits; protective classification;
broker transmission; emergency containment."

**philosophy.md §7 "Prediction Has Limited Authority"** (lines 193–239):
decision/model output ("indicators; statistical models; machine learning; market
structure; flow analysis; event interpretation; trend and momentum signals") is
"treated as uncertain evidence, not as authority." Explicitly separates
`Prediction` from `Permission to risk capital`: "A strong signal does not bypass:
risk limits; execution checks; account state; venue constraints; live
authorization; aggregate portfolio controls."

**RFC-000 §6 Definitions — "Decision Generation"**: "The activity of producing a
proposed trading action from Decision Context and interpretation, prior to
Approval." The constitutional name for what the future Decision Framework
implements.

**RFC-000 §9 "Constitutional Boundaries"** (lines 1260–1272): explicit layering —
"This Constitution defines **WHY**. RFC-001 Safety Case defines **WHAT SHALL NEVER
HAPPEN**. Architecture RFCs define **WHAT EXISTS**. **Decision Framework defines
HOW DECISIONS ARE MADE**. Implementation defines **HOW SOFTWARE IS BUILT**." — i.e.
RFC-003 is constitutionally scoped to the *decision-generation process*, not
safety enforcement, architecture, or implementation.

**RFC-000 §12 "Constitutional Governance"** (lines 1324–1345): hierarchy places
**Decision Framework below Architecture RFCs and above Implementation** —
`Trading Constitution → Safety Case → Architecture RFCs → Decision Framework →
Implementation → Operational Procedures`. RFC-003 (and RFC-004–007) is
subordinate to RFC-002 and every accepted ADR-002-xxx.

**RFC-000 §10 "Decision Hierarchy"** (lines 1276–1310, immutable):
`Observation → Context Construction → Interpretation → Decision → Approval →
Execution → Audit`. "No implementation SHALL bypass, remove or reorder these
stages." The Decision Framework governs the **Interpretation → Decision** portion
and hands off to a separately-owned **Approval** stage it does not control.

---

## 2. What "Intent" is

**Canonical constitutional definition — RFC-000 §6**: "**Intent** — The trading
action a decision was constitutionally meant to produce, against which any emitted
order is validated." Defined as a *reference for validation*, not a data schema.

**RFC-002 builds Intent up compositionally; ADR-002-005 makes the state model
normative:**

- **RFC-002 §10.6 "Intent Registry"**: "assign immutable Intent identity; retain
  the approved intent; associate all orders, retries, replacements, cancellations,
  fills, and evidence with the originating intent; maintain intent lifecycle
  state." The Intent Registry — not the Decision Service — owns Intent
  identity/creation.
- **RFC-002 §10.2 "Decision Service"**: what the decision layer supplies for a
  proposal — "consume immutable validated context; generate proposed trading
  intent; provide decision rationale; identify intended **account, instrument,
  direction, quantity, and constraints**." Explicitly SHALL NOT approve its own
  decision, transmit orders, reserve risk capacity, or modify safety config.
- **ADR-002-005 §5 "Dimension: Intent State"** (lines 65–78): Intent has its own
  orthogonal lifecycle owned by the Intent Registry:
  `PROPOSED → APPROVED → AUTHORIZED_FOR_CAPACITY → ACTIVE → CLOSED`, with a
  `DENIED` branch off `APPROVED` and `ACTIVE → WITHDRAWN` only if no attempt may
  be live. `APPROVED` means only that Approval accepted the proposal;
  `AUTHORIZED_FOR_CAPACITY` means Approval + Aggregate-Risk policy granted and does
  **not** mean capacity is committed or anything was transmitted. Intent identity
  is immutable, globally unique (SAFE-020), and a terminal identity is not reused.
- **ADR-002-020 §5.1 "Approved Intent Contract"**: "The immutable approved
  statement of requested action, allowed scope, maximum economic effect,
  constraints, expiration, context, and authority prerequisites... The Intent is
  not a broker command." §8 lists mandatory fields the proposal (and identical
  approved Intent) SHALL bind: immutable identity/version/digest/issuer/approval/
  expiration; environment/safety-cell/broker-scope/account-subaccount/venue/
  market-segment/instrument/contract/canonical-identity; requested action/
  action-class/direction/side-semantics/position-effect/operating-mode/
  protective-classification-reference; quantity-basis/unit/max-quantity/multiplier/
  currency/price-basis/order-constraints/time-in-force/expiration; requested-and-
  maximum-credible-economic-effect-vector; Critical Input Snapshot and Decision
  Context Capsule; required venue/capacity/authority/profile/recovery/evidence
  scopes and predicates; Authorized Construction Envelope identity/digest and
  permitted deterministic transformations; forbidden transformations, retry/split/
  aggregation policy, invalidation predicates, residual risks. **"Wildcard account,
  instrument, contract, side, quantity, unit, multiplier, mode, endpoint, or
  'latest policy' references are prohibited for live construction."**

**Bottom line for RFC-003 authors:** the Decision Framework produces a *proposal*
that becomes an Intent only after Approval + Intent Registry consumption
(ADR-002-023). It does not own Intent identity, Intent lifecycle, or the
downstream state dimensions (Transmission Attempt, Broker Order, Knowledge/
Evidence, Capacity — ADR-002-005 §9, owned by RCL). RFC-003/004/005/006/007
produce the *inputs* to a proposal (direction, instrument, quantity basis,
constraints, rationale) but cannot define Intent's binding legal contract — that
belongs to ADR-002-020 and ADR-002-023.

---

## 3. Inputs the decision layer consumes

**RFC-000 §6 "Decision Context"**: "The complete, immutable, read-only information
a decision consumes; its concrete taxonomy is defined by Architecture RFCs." §11:
"Every decision SHALL consume immutable Decision Context... Decision logic SHALL
treat all contexts as read-only." Taxonomy is intentionally left to
RFC-002/ADR-002-018 — **RFC-004 (Market Model) plugs in here**, but as a *consumer*
of the Critical Input / Decision Context Capsule machinery, not an independent
definer of context.

**RFC-001 §5.17 "Trustworthy Context"**: "Decision context that is complete,
valid, sufficiently fresh, internally consistent, correctly typed and scaled,
attributable to an approved source, and suitable for the intended decision."
**SAFE-030 "Trustworthy Context Precondition"**: "No decision, approval, sizing
calculation, or execution SHALL rely on Critical Input that is not trustworthy.
Completeness alone SHALL NOT establish trustworthiness." **SAFE-031 "Critical
Input Provenance"**: every Critical Input must be attributable to approved
source/timestamp/unit/instrument/account/processing version.

**RFC-001 §5.3 "Critical Input"**: "Any input whose corruption, absence,
staleness, unit error, or inconsistency may alter: direction; instrument;
quantity; price; exposure; risk; margin; account state; authorization; venue
availability; execution behavior." — market data, price feeds, reference data fall
under this if they feed a decision.

**ADR-002-018** is the concrete, exact contract for Critical Input and the single
most important input-side document for RFC-004/RFC-006 authors:

- Any value that "can change direction, instrument, account, quantity, price
  constraint, exposure, risk, margin, venue or session eligibility, authorization,
  protective classification, or execution behavior SHALL be governed as a Critical
  Input" (§1). A component "may not avoid this contract by calling the value a
  feature, signal, cache, reference, override, derived field, broker fact, or
  operator input." **Directly binds any market/signal/feature data a future Market
  Model layer would use.**
- The Context Integrity Service constructs an immutable **Critical Input Snapshot**
  and **Decision Context Capsule** the decision layer consumes; the capsule "grants
  no approval, capacity, Live Authorization, protective classification, or broker
  permission" (§1, CII-INV-011). The decision layer cannot self-certify freshness
  or validity (§7 table: "Propose action | Decision Service | cannot validate its
  own independent approval inputs").
- **CII-INV-005 "Ambiguity Is Restrictive"**: missing/stale/future/conflicting/
  discontinuous/wrongly-scaled/ambiguously-mapped/unsupported/unverifiable Critical
  Input "blocks new risk and never defaults to a permissive value." A Market Model
  computing derived indicators/features inherits this: derived Critical Inputs
  require "complete deterministic or explicitly stochastic lineage from admitted
  observations" (§10) — no hidden default, silent coercion, forward fill, zero
  fill, stale feature reuse, symbol alias, unit conversion, or fallback source
  outside policy.
- **§13 "Independent Approval Inputs"**: the decision layer's own outputs must be
  *independently recomputed*, not merely re-validated, by the Independent Approval
  Service — "The same library used by proposer and approver is a common-mode
  dependency unless independently verified isolation or diverse implementation is
  demonstrated" (§10). Hard constraint on how RFC-003/004 may be implemented if
  SAFE-034 is to hold.
- The Capsule identity/digest must be bound through the entire downstream chain:
  proposal → independent approval → Intent → aggregate-risk evaluation → Live
  Authorization/capability → Commit Proof → evidence → final egress (§15). **Any
  RFC-003/004 output not carried as an exact Capsule-bound artifact is
  non-conforming.**

**ADR-002-019 (Venue/Session/Tradability)** is also an *input* constraint on
decision-making: "Venue, session, tradability, account, margin, settlement, and
broker-constraint facts are Critical Inputs" (RFC-002 §10.1, last line). SAFE-032/
ADR-002-019 requires decisions never assume tradability, exit-availability, or
venue state from calendar time, quotes, or connectivity — relevant to any Market
Model reasoning about liquidity or session state.

---

## 4. The decision↔safety boundary (MOST IMPORTANT SECTION)

Precise, cited list of things the decision/strategy layer (and hence
RFC-003/004/005/006/007) **MUST NOT** do. RFC-002/ADR items are authoritative
design intent, not yet Accepted.

| # | Prohibition | Citation |
|---|---|---|
| 1 | MUST NOT approve its own proposal/decision. | RFC-000 CONST-005 "Independent Approval Authority" — "Decision components SHALL NOT approve their own trading actions." Also philosophy.md §14. |
| 2 | MUST NOT transmit orders. | RFC-002 §10.2; §7.3 "A strategy SHALL be treated as an untrusted proposer... SHALL NOT transmit live orders." |
| 3 | MUST NOT reserve/commit aggregate risk capacity. | RFC-002 §10.2; §7.3; §10.5 ("A strategy SHALL NOT write directly to the Risk Capacity Ledger"). |
| 4 | MUST NOT alter/relax safety limits or modify safety configuration. | RFC-002 §10.2; §7.3; RFC-001 §7.5 "Separation of Authority." |
| 5 | MUST NOT arm live mode / issue live authorization. | RFC-002 §7.3; RFC-001 §7.5; philosophy.md §14. |
| 6 | MUST NOT classify its own action as protective. | RFC-002 §7.3; §10.15 / §9.1 authority matrix; RFC-001 §5.25 — "An action SHALL NOT be considered protective solely because it is described as a hedge, exit, stop, recovery, or emergency action." |
| 7 | MUST NOT disable/bypass the independent Safety Authority or containment. | RFC-000 CONST-011; RFC-001 §7.6 "Non-Disableable Core Controls." |
| 8 | Strong signal/prediction does not bypass risk limits, execution checks, account state, venue constraints, live authorization, or aggregate controls. | philosophy.md §7. |
| 9 | Cannot size beyond capacity: aggregate risk effect must independently pass Aggregate Risk Authority / RCL regardless of what the decision layer computed. | RFC-001 SAFE-010/012/013/015; ADR-002-021 §1/§7. |
| 10 | Cannot self-certify context freshness/validity or bypass Critical Input governance by re-labeling data as "feature"/"signal"/"derived value." | ADR-002-018 §1, CII-AC-001. |
| 11 | Output (Intent proposal) is subject to mandatory *independent recomputation* by Approval — cannot rely on its own derived facts. | RFC-001 SAFE-034; ADR-002-018 §13; ADR-002-023 §1. |
| 12 | A `GRANT`/`APPROVE`/`ADMISSIBLE`/`CONFORMANT` result from any downstream gate is never itself capacity, authority, or transmission permission. | ADR-002-019 §1; ADR-002-020 §1; ADR-002-021 §1; ADR-002-023 §1. |
| 13 | Wildcard / "latest policy" / unbounded scope in any decision-layer construction is prohibited. | ADR-002-020 §8. |
| 14 | Cannot rely on its own component health/uptime/"last known good" to imply market data or context validity. | ADR-002-018 CII-INV-013; philosophy.md §16. |
| 15 | No decision may bypass, remove, or reorder the constitutional pipeline stages. | RFC-000 §10. |
| 16 | Locally-safe decision logic does not excuse an unsafe aggregate portfolio state. | RFC-000 §5; RFC-001 §7.4; philosophy.md §18. |
| 17 | A hedge/exit/protective action (directly relevant to RFC-007) is not automatically safe — aggregate *and intermediate* risk effect must be proven, not labeled. | RFC-000 CONST-012; RFC-001 §5.25, SAFE-043; ADR-002-001 §6 (Final-State + Intermediate-State tests). |
| 18 | Netting/hedge/correlation/diversification benefit is **zero unless positively proven** under approved policy and current evidence. | ADR-002-021 §13, ARE-INV-005 "No Unproven Benefit." |
| 19 | Cannot decide materiality of a context/constraint change itself — no self-exemption of a context dependency. | ADR-002-018 §1, §5.8. |
| 20 | No output treated as complete/valid merely because internally consistent or well-typed — trustworthiness is decided elsewhere. | RFC-001 §5.17, SAFE-030. |

**Generalizing invariant** (RFC-000 §5 "Constitutional Precedence" + RFC-002 §9.1
Authority Ownership Matrix): every pipeline stage has exactly one "policy
authority" and a separate "state-transition/enforcement authority," and the same
identity may never combine proposing an action with approving, committing capacity
for, or transmitting it. The Decision Framework (RFC-003) and its subordinate
models (RFC-004–007) occupy only the "Decision Service" row of RFC-002 §9.1:
*"Propose trading action | Decision Service | None | Decision Service SHALL NOT
approve, commit, or transmit."*

---

## 5. Per-RFC mapping — upstream sections/ADRs a future author MUST honor

### RFC-003 — Decision Framework
- **RFC-000 §7 CONST-001/003/004/005/009** — Traceability fields name RFC-003.
  CONST-001's list is `RFC-001, RFC-002, RFC-003` (lines 347–353); CONST-003's is
  `RFC-003, RFC-006` (lines 459–463).
- **RFC-000 §6** — "Decision Generation," "Decision Context," "Deterministic
  Decision," "Decision Quality," "Critical Uncertainty" are vocabulary RFC-003
  must use verbatim (RFC-000 §12: lower specs SHALL NOT reinterpret higher intent).
- **RFC-000 §10** — the fixed 7-stage pipeline RFC-003 operates inside.
- **RFC-000 §11** — RFC-003 must *consume*, not redefine, the Decision Context
  taxonomy (which RFC-000 defers to Architecture RFCs / ADR-002-018).
- **RFC-001 SAFE-030/031/034**.
- **RFC-002 §10.2 "Decision Service"** — exact responsibility/prohibition list.
- **ADR-002-005** — the `PROPOSED` Intent state the proposal feeds; RFC-003 owns
  no transition beyond creating the proposal.
- **ADR-002-018** — consume Decision Context Capsules exactly as bound.
- **ADR-002-020 §8** — the exact field set a proposal must populate.
- **ADR-002-023** — the proposal becomes an Intent only through this pipeline.
- **Explicit deferral marker**: RFC-001 §12 — "CONST-003 — Positive Expectancy |
  ... performance demonstration delegated to the Decision Framework | — | **NOT
  DISCHARGED BY RFC-001**" (`RFC-001-Safety-Case.md:1769`). RFC-003 (and RFC-006,
  per CONST-003's dual traceability) inherits the entire unmet obligation.

### RFC-004 — Market Model
- **philosophy.md §7** — predictions are "uncertain evidence, not authority."
- **RFC-000 CONST-007 "Venue Constraints"** — "SHALL treat venue-imposed
  constraints as first-class decision inputs"; Traceability `ARCH-005, DEC-003,
  SAFE-015` (lines 743–750). **`DEC-003` is an undefined placeholder** —
  not addressed in part-1; research gap.
- **RFC-001 §5.3, SAFE-030..035** — any market data/feature/signal is Critical
  Input.
- **ADR-002-018** (whole) — provenance/lineage/freshness/consistency-cut contract;
  §10 "Transformation Lineage and Derived Inputs" governs any indicator/feature.
- **ADR-002-019** — RFC-004's "market state" must not conflict with or duplicate
  the authoritative tradability/session-phase state machine; it cannot assert
  tradability itself.
- **Not addressed in part-1**: no RFC-002 component is a "Market Model." Gap for
  RFC-004 to fill without contradicting Context Integrity / Venue Constraint
  boundaries.

### RFC-005 — Execution Model
- **RFC-000 CONST-002 "Capital Preservation"** — Traceability `RFC-001, RFC-005`
  (lines 403–407).
- **RFC-000 CONST-004 "Fail-Safe Operating Principle"** — `RFC-001, RFC-005`
  (lines 550–552).
- **RFC-000 CONST-009 "Pre-Trade Constitutional Assurance"** — `RFC-001, RFC-005`
  (lines 869–871).
- **RFC-002 §10.7 "Execution Coordinator," §10.8 "Broker Adapter/Broker Egress
  Gateway"** — RFC-005 must not duplicate/weaken these; only describe how an
  approved Intent flows through them.
- **ADR-002-020** — already effectively "the execution model" at the architecture
  layer for command construction; RFC-005 references, does not redefine.
- **ADR-002-002 §11 "Normal Commitment Flow"** — exact pipeline order any
  execution narrative must match.
- **ADR-002-022** — retry/reconnect/rate-budget semantics.
- **ADR-002-024** — the exact currentness protocol at send time.

### RFC-006 — Risk Model
- **RFC-000 CONST-002, CONST-003** (Traceability `RFC-003, RFC-006`, lines
  459–463) — shares the positive-expectancy-demonstration obligation with RFC-003.
- **Open reviewer finding**: CONST-002 (Capital Preservation) traceability *omits*
  RFC-006 though capital preservation is a risk-model concern — do not silently
  "fix"; route through governance.
- **RFC-001 §5.20 "Hard Safety Envelope," §5.21, SAFE-004/012/013** — RFC-006
  operates strictly *inside* the Hard Safety Envelope; may narrow, never widen.
- **ADR-002-002** — architecture-layer risk-capacity mechanics; RFC-006 describes
  risk methodology without redefining the ledger/commitment mechanics.
- **ADR-002-021** — closest existing analog to "the Risk Model." §8 "Aggregate
  Risk Policy Contract," §10 "Risk Dimensions, Units, and Scopes," §11 "Adverse
  Scenario Set," §13 "Netting, Hedge, Correlation, and Diversification" are the
  exact normative content RFC-006 must be consistent with. ARE-INV-005 "No
  Unproven Benefit" — netting/hedge assumption is zero by default. Open
  Implementation Question #4 (§28) defers "which valuation/stress/slippage/
  liquidity/vol/correlation/basis/FX/margin models are approved" — squarely
  RFC-006's job, subject to that ADR's invariants.

### RFC-007 — Portfolio Hedge Model
- **RFC-000 CONST-012 "Safe Operational State"** — "a bounded protective action
  MAY be authorized only when its projected aggregate effect reduces constitutional
  risk and does not violate any applicable safety limit."
- **RFC-001 §5.25, SAFE-002/040/043**.
- **ADR-002-001 (Degraded-Mode Protective Capacity)** — most directly relevant. §6
  "Protective Action Classification" (Final-State Test §6.1, Intermediate-State
  Test §6.2, Risk Dimensions §6.3) is the exact test a hedge must pass; §7
  "Protective Action Envelope"; §4 "Protective Capacity Domains." RFC-007 must be
  consistent with (not duplicate/weaken) this.
- **ADR-002-002 §19 "Reserved Protective Capacity"** — protective pool/lease
  mechanics any hedge capacity request goes through.
- **ADR-002-011 (Protective Replacement and Protection-Gap Control)** — hedge
  replacement/rollover (gap risk when replacing one hedge with another).
- **ADR-002-021 §19 "Protective, Exit, and Degraded Evaluation"** — the
  risk-projection-side rules for hedge/exit actions.
- **philosophy.md §10 "Safe State Is Exposure-Aware"** — "A hedge, exit, stop, or
  cancellation is not automatically safe... A protective action may reduce
  directional risk while increasing gross exposure; leverage; margin; basis risk;
  liquidity risk; execution risk; concentration elsewhere."
- **philosophy.md §39.5 "Hedge Means Safe" (anti-pattern)** — "An order bypasses
  controls because it is labelled protective." RFC-007 must not encode this.

---

## 6. Terminology (canonical — reuse, do not invent synonyms)

| Term | Canonical source | Definition (paraphrased/quoted) |
|---|---|---|
| **Intent** | RFC-000 §6 | "The trading action a decision was constitutionally meant to produce, against which any emitted order is validated." |
| **Decision Context** | RFC-000 §6 | "The complete, immutable, read-only information a decision consumes." |
| **Decision Generation** | RFC-000 §6 | "The activity of producing a proposed trading action from Decision Context and interpretation, prior to Approval." |
| **Approval** | RFC-000 §6 | "The independent authority that accepts or rejects a proposed trading action before execution, distinct from the component that generated it." |
| **Critical Uncertainty** | RFC-000 §6 | "A condition in which the system cannot establish, within constitutional bounds, that its Decision Context is complete, current and internally consistent." |
| **Constitutional Safe State** | RFC-000 §6; RFC-001 §5.2 | Exposure-aware state prohibiting new risk-increasing exposure while preserving protective control; "SHALL NOT be interpreted as mere inactivity." |
| **Deterministic Decision** | RFC-000 §6 | "A decision that, given identical Decision Context, always yields the same result; determinism applies to the decision process, not to market outcomes." |
| **Autonomous Trading** | RFC-000 §6 | "Any creation, modification or cancellation of orders performed by the system without contemporaneous human authorization." |
| **Trustworthy Context** | RFC-001 §5.17 | "complete, valid, sufficiently fresh, internally consistent, correctly typed and scaled, attributable to an approved source, and suitable for the intended decision." |
| **Critical Input** | RFC-001 §5.3; ADR-002-018 §1 | Any input whose corruption/absence/staleness/unit-error/inconsistency may alter direction, instrument, quantity, price, exposure, risk, margin, account state, authorization, venue availability, or execution behavior — regardless of what it is *named*. |
| **Decision Context Capsule** | ADR-002-018 §5.6 | "An immutable canonical artifact binding one proposed action purpose and scope to the exact Critical Input Snapshot, safety configuration, trustworthy-time evidence, independent-validation requirements, maximum age, and invalidation generation." |
| **Capacity / Risk-Capacity Commitment** | RFC-001 §5.21; ADR-002-002 | "The exclusive allocation of a defined portion of available aggregate safety capacity to an authorized action or potentially live order." Only the RCL may mutate it. |
| **Hard Safety Envelope** | RFC-001 §5.20 | "An independently governed upper boundary on operational authority that runtime Safety Profiles SHALL NOT exceed." |
| **Runtime Safety Profile** | RFC-002 §19.1 | The layer beneath the Hard Safety Envelope; may only *narrow*, never expand, authority. |
| **Aggregate Risk Decision** | RFC-002 §3.1.1; ADR-002-021 §5.5 | "A policy decision that evaluates whether a proposed economic action may be allocated risk capacity." Result `GRANT`/`DENY`/`UNKNOWN`; grants no capacity itself. |
| **Adverse Increment Vector** | ADR-002-002 §6.3; ADR-002-021 §5.7 | "The component-wise maximum credible increase in governed risk usage required to cover the proposed command and its adverse intermediate states." Never negative merely because the action is risk-reducing. |
| **Protective Action** | RFC-001 §5.25 | "A bounded action whose demonstrated projected aggregate effect reduces constitutional risk while remaining inside every applicable safety boundary." Not established by label. |
| **Trapped Exposure** | RFC-001 §5.24; RFC-002 §3.1.8 | Exposure that cannot currently be reduced with sufficient confidence; treated as non-reducible for capacity purposes. |
| **Potentially-Live Quantity** | RFC-002 §3.1.4 | "The conservative upper bound of quantity that may still produce broker-side economic effect." |
| **Currentness** | ADR-002-024; RFC-001 §5.22 | The property that a fact used at authorization/transmission is actively, not merely cache-verified, current — "Cached health, TTL, heartbeat... is not proof." |
| **Order Admissibility Decision** | ADR-002-019 §5.4 | Venue/session/tradability result: `ADMISSIBLE`/`RESTRICTED_PROTECTIVE_ONLY`/`INADMISSIBLE`/`UNKNOWN`; a safety fact, not permission. |
| **Order Conformance Proof** | ADR-002-020 §5.6 | Proof that a Canonical Broker Command is a deterministic member of the Intent's Authorized Construction Envelope, with Economic Effect Envelope covered by RCL commitment. |
| **Authoritative State / Operational State** | RFC-000 §6; RFC-001 §5.1 | The true state of positions/orders/account established from corroborating evidence, distinct from internal representation. |
| **UNKNOWN** (first-class) | RFC-002 §12.1; ADR-002-005 | Never treated as rejected/cancelled/unfilled/safe-to-retry; consumes conservative capacity. |
| **Decision Quality** | RFC-000 §6 | "The degree to which a decision was correct given the information constitutionally available when it was made, independent of its individual outcome." |
| **Positive Expectancy** | RFC-000 §6, CONST-003 | "The statistically expected value of the complete decision process, evaluated over a population of decisions rather than any individual trade." |

---

## Explicit research gaps (not addressed in part-1)

1. **`DEC-003`** (`RFC-000-Trading-Constitution.md:747`, CONST-007 derived
   requirements) is referenced but defined nowhere; the `DEC-xxx` namespace does
   not exist in the corpus. A prior review already flagged this dangling
   traceability target. RFC-004 (natural home for venue-constraint-as-input)
   should adopt the identifier formally or note its absence — through governance.
2. **No RFC-002 component is named "Market Model," "Risk Model," "Hedge Model," or
   "Decision Framework."** The 31 core components (RFC-002 §10.1–§10.31) cover
   context/decision/approval/risk-capacity/execution/safety/governance, but none is
   the Decision Service's internal reasoning engine. Intentional per RFC-000 §9;
   RFC-003 has an open architectural canvas *within* the Decision Service contract
   (RFC-002 §10.2).
3. **CONST-002 (Capital Preservation) traceability omits RFC-006** despite being
   semantically a risk-model concern — open reviewer finding, not yet corrected.
4. **No numeric bounds/models/methodologies exist anywhere in part-1** for
   valuation, correlation, liquidity-adjustment, VaR/stress, or hedge-effectiveness.
   ADR-002-021 §8/§10/§14 lists *what properties* any such model must have
   (deterministic, bounded, overflow-safe, independently reproducible, conservative
   fallback) but defers "which models are approved" as Open Implementation Question
   #4 (§28) — RFC-006's job, subject to that ADR's invariants.
5. **RFC-001 §12 marks CONST-003 "NOT DISCHARGED BY RFC-001"** and delegates it to
   the Decision Framework — the clearest textual admission that positive-expectancy
   demonstration is entirely unaddressed until RFC-003 exists.
