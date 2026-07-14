# Per-RFC Starting Points (RFC-003 – RFC-007)

> **NON-NORMATIVE — RESEARCH INPUT ONLY.** Author-facing synthesis of the
> upstream-constraints dossier (`10-*`) and the external-domain survey (`20-*`).
> Not a spec, not a plan, no requirements, no authority. When a part-2 RFC is
> written, it is canonical — not this note.

Each section below is a starting checklist for one future RFC: the **binding
upstream** it must honor, the **nearest existing anchor** it must not duplicate or
weaken, the **external scaffold** it may draw on, and the **decisions to make**.
Ordering follows dependency: RFC-003 is the framework토대; 004–007 refine it.

---

## RFC-003 — Decision Framework

**Role (RFC-000 §9):** defines *HOW DECISIONS ARE MADE* — subordinate to
Architecture RFCs, above Implementation. Governs the `Interpretation → Decision`
portion of the immutable pipeline (RFC-000 §10) and hands off to a separately-owned
`Approval`.

**Binding upstream (must honor):**
- RFC-000 §6 vocabulary (Decision Generation, Decision Context, Deterministic
  Decision, Decision Quality, Critical Uncertainty, Positive Expectancy) — use
  verbatim; §12 forbids reinterpreting higher intent.
- RFC-000 §10 fixed 7-stage pipeline (no bypass/reorder).
- RFC-002 §10.2 Decision Service responsibility/prohibition list.
- The 20-item decision↔safety boundary (`10-*` §4) — every "MUST NOT."
- ADR-002-005 (`PROPOSED` Intent state), ADR-002-018 (consume Capsules as bound),
  ADR-002-020 §8 (proposal field set), ADR-002-023 (proposal → Intent pipeline).

**Nearest existing anchor:** RFC-002 §10.2 Decision Service is the contract; there
is **no** RFC-002 component for the Decision Service's *internal reasoning engine*
— RFC-003 has an open canvas *within* that contract.

**External scaffold (`20-*` §1):** alpha/decision/risk/execution separation
(Narang 2013; Grinold & Kahn 2000); target-position/parent-order abstraction;
deterministic-vs-stochastic policy with **reproducibility** as the load-bearing
property; SR 11-7 auditability (point-in-time snapshots, config+model versioning,
decision provenance).

**Decisions to make:**
- Atomic decision unit: per-symbol target position vs. portfolio-wide weight vector.
- Reproducibility standard for any stochastic/LLM component ("reproducible given
  logged response" vs. bit-for-bit).
- Minimum decision-time logging to reconstruct *why* months later without a live
  service.
- Represent "hold" vs. "explicit flat (target=0)" distinctly.
- **Inherited obligation:** RFC-001 §12 marks CONST-003 (Positive Expectancy) "NOT
  DISCHARGED BY RFC-001" and delegates it here (shared with RFC-006).

---

## RFC-004 — Market Model

**Role:** define the market-state model the decision layer consumes — as a
*consumer* of the Critical Input / Decision Context machinery, never an independent
definer of context or asserter of tradability.

**Binding upstream (must honor):**
- RFC-001 §5.3, SAFE-030..035 — any market data/feature/signal is Critical Input.
- ADR-002-018 (whole), esp. §10 "Transformation Lineage and Derived Inputs" —
  governs every indicator/feature; CII-INV-005 ambiguity-is-restrictive.
- ADR-002-019 — must not conflict with / duplicate the authoritative
  tradability/session-phase state machine; cannot assert tradability itself.
- philosophy.md §7 — predictions are "uncertain evidence, not authority."

**Nearest existing anchor:** ADR-002-018 (Critical Input) + ADR-002-019
(venue/session). **Gap:** no RFC-002 "Market Model" component exists — fill without
contradicting those boundaries.

**External scaffold (`20-*` §2):** LOB/spread/impact (O'Hara 1995; Harris 2003;
Kyle 1985); realized volatility + HAR-RV (Andersen et al. 2003; Corsi 2009 — HAR-RV
already in `shared/forecasting/volatility_har_rv.py`); regime via Markov-switching
(Hamilton 1989) or RV-percentile heuristics (`regime-gate-analyst`). Korea:
09:00–15:30 continuous + auctions, ±30% equity limit, static/dynamic VI, sidecar,
banded tick sizes, KOSPI200 250,000/0.05 & mini 50,000/0.02.

**Decisions to make:**
- Pin VI/circuit-breaker thresholds + tick-band table to a version/date; define a
  refresh requirement when KRX revises.
- Define "regime" formally (HAR-RV bands) or defer to a downstream consumer.
- Represent a stock-level VI halt vs. portfolio decisions that assumed liquidity.
- Mini vs. full KOSPI200 as parameterized-shared vs. separate models.
- **Gap to resolve through governance:** `DEC-003` dangling traceability
  (`RFC-000:747`) — adopt formally or note its absence.

---

## RFC-005 — Execution Model

**Role:** describe how an *approved* Intent flows through execution — must not
duplicate or weaken the Execution Coordinator / Broker Egress Gateway, nor redefine
canonical command construction.

**Binding upstream (must honor):**
- RFC-000 CONST-002/004/009 (Traceability `RFC-001, RFC-005`).
- RFC-002 §10.7 / §10.8 (Execution Coordinator, Broker Egress Gateway).
- ADR-002-020 (Intent-to-Order Conformance — the architecture-layer "execution
  model" for command construction; reference, don't redefine).
- ADR-002-002 §11 "Normal Commitment Flow" — the exact pipeline order any narrative
  must match.
- ADR-002-022 (retry/reconnect/rate-budget), ADR-002-024 (send-time currentness).

**Nearest existing anchor:** ADR-002-020 + ADR-002-002 §11. Existing
broker-API-constrained execution logic: `shared/execution/passive_maker.py`,
`pseudo_oco.py`.

**External scaffold (`20-*` §3):** Almgren-Chriss (2001); implementation shortfall
(Perold 1988); VWAP/TWAP (Berkowitz et al. 1988; Cartea & Jaimungal 2016); temp/
perm impact (Kyle 1985); slippage/order-types/SOR (Harris 2003). **Non-DMA caveat:
KIS is a broker API, not DMA** — optimal-execution *trajectories* are a slicing
scaffold, not directly implementable at queue level; TCA is a *measurement*
discipline.

**Decisions to make:**
- Explicit Almgren-Chriss cost/risk tradeoff vs. simpler heuristic slicing (is the
  sophistication realizable via KIS?).
- Execution benchmark: arrival price / VWAP / decision-mid — possibly differing
  between stock and futures pipelines (futures backtests already assume 0.3×tick
  slippage in `decision_harness.py`).
- Estimate temp vs. perm impact with only top-of-book/limited depth.
- Represent call-auction participation distinctly from continuous-session logic.
- Behavior when an order is rejected/halted mid-schedule (VI/limit).

---

## RFC-006 — Risk Model

**Role:** define risk methodology (how risk is modeled, valued, projected) strictly
*inside* the Hard Safety Envelope (may narrow, never widen) — without redefining
ADR-002-002's ledger/commitment mechanics.

**Binding upstream (must honor):**
- RFC-000 CONST-002 (Capital Preservation) + CONST-003 (Positive Expectancy,
  Traceability `RFC-003, RFC-006`).
- RFC-001 §5.20 Hard Safety Envelope, §5.21, SAFE-004/012/013.
- ADR-002-002 (risk-capacity mechanics — describe methodology, don't redefine).
- ADR-002-021 — closest existing analog: §8 Aggregate Risk Policy Contract, §10
  Risk Dimensions/Units/Scopes, §11 Adverse Scenario Set, §13 Netting/Hedge/
  Correlation. ARE-INV-005 "No Unproven Benefit" — netting/hedge benefit is **zero
  by default**. Open Implementation Question #4 (§28) defers "which valuation/
  stress/slippage/liquidity/vol/correlation/basis/FX/margin models are approved" to
  here, subject to that ADR's invariants.

**Nearest existing anchor:** ADR-002-021 (aggregate risk) + ADR-002-002 (capacity).

**External scaffold (`20-*` §4):** VaR (parametric/historical/MC; Jorion 2006); ES/
CVaR + coherence axioms (Artzner et al. 1999, incl. VaR non-subadditivity); sizing
(Kelly 1956; vol-targeting per Moskowitz et al. 2012; fixed-fractional —
`FixedFractionalFuturesSizer` exists); drawdown control; SPAN-like futures margin
(KRX as CCP). Korea: ±30%/±10% limits cap single-day loss; futures leverage makes
margin limits load-bearing; halts can block mid-de-risk (needs fallback).

**Decisions to make:**
- VaR/ES method given data depth + fat-tailed/jump-prone KOSPI200-futures returns.
- ES/CVaR primary (coherent) vs. VaR for interpretability with ES secondary check.
- Whether the HAR-RV estimate serves both regime classification (RFC-004) and
  vol-targeting sizing, or they are decoupled.
- One portfolio-level VaR/ES vs. asset-class sub-limits for the mixed unlevered-
  equity / levered-futures book.
- Drawdown control as a distinct control vs. folded into the existing
  consecutive-loss size-reduction state machine.
- **Gap through governance:** CONST-002 traceability omits RFC-006 (open reviewer
  finding) — do not silently fix.

---

## RFC-007 — Portfolio Hedge Model

**Role:** formalize hedging of equity exposure with index futures — where a hedge
is a *protective action* whose safety is proven by projected aggregate **and
intermediate** effect, never asserted by label.

**Binding upstream (must honor):**
- RFC-000 CONST-012 "Safe Operational State" — a bounded protective action may be
  authorized only when its projected aggregate effect reduces constitutional risk
  and violates no safety limit.
- RFC-001 §5.25, SAFE-002/040/043.
- ADR-002-001 §6 Protective Action Classification (Final-State §6.1 + Intermediate-
  State §6.2 tests, Risk Dimensions §6.3) — the exact test a hedge must pass; §7
  Envelope; §4 Capacity Domains.
- ADR-002-002 §19 Reserved Protective Capacity; ADR-002-011 (protective replacement
  / protection-gap for hedge rollover); ADR-002-021 §19 (risk-projection rules for
  hedge/exit).
- philosophy.md §10 (a hedge may reduce directional risk while increasing gross
  exposure/leverage/margin/basis/liquidity/execution/concentration risk) and §39.5
  anti-pattern ("Hedge Means Safe") — must not encode.

**Nearest existing anchor:** ADR-002-001 (degraded-mode protective capacity) +
ADR-002-011 (protective replacement).

**External scaffold (`20-*` §5):** beta hedge N = −β·V/(F·multiplier); min-variance
hedge ratio h* = Cov(ΔS,ΔF)/Var(ΔF) (Johnson 1960; Ederington 1979; Hull); basis
risk; roll/expiry management; delta hedging (Black-Scholes 1973) if options used.
Korea: KOSPI200 futures as standard hedge; 5× multiplier gap mini vs. full;
cross-hedge basis risk for non-representative books; second-Thursday roll cycle;
per-leg halt imbalance; **night-session-disabled ⇒ futures hedge only maintainable
in KST day session** (binding operator policy).

**Decisions to make:**
- Static beta vs. rolling min-variance vs. dynamically re-estimated hedge ratio +
  estimation window.
- Mini vs. full contract denomination + fractional-contract rounding/residual basis.
- Roll policy across the second-Thursday cycle.
- Portfolio beta vs. KOSPI200 vs. a broader proxy for non-representative books.
- Document unhedged overnight/global-event gap risk as accepted residual risk, or
  define a compensating control (pre-close de-risk, reduced overnight equity
  limits).

---

## Cross-cutting reminders for every part-2 RFC

1. **You are a proposer, not an authority.** No RFC-003–007 content may issue
   authority, commit capacity, transmit, classify its own action as protective, or
   self-certify context. (`10-*` §4.)
2. **Reuse canonical terminology** (`10-*` §6) — do not invent synonyms for Intent,
   Capacity, Currentness, Hard Safety Envelope, Protective Action, UNKNOWN, etc.
3. **Korea-specific numbers are living parameters** — pull from KRX's current
   rulebook at spec time; never hardcode.
4. **Carry the four known upstream gaps forward through governance**, not by silent
   patching (`00-*` "Known upstream gaps").
5. **Confirm the foundation has settled** before finalizing — part-1 was still
   growing (ADR-002-029, 351 evidence items) at the time these notes were written.
