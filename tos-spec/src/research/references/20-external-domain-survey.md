# External-Domain Survey: Decision / Market / Execution / Risk / Hedge

> **NON-NORMATIVE — RESEARCH INPUT ONLY.** Background literature/practice survey
> to inform (not draft) the five part-2 specs. No requirements, no authority, no
> normative recommendation, no spec content proposed. Citations are reported with
> a verification-status caveat (see final table) — a spec author must confirm
> against primary sources before formal citation.

**Sourcing caveat:** Academic citations below were spot-checked against secondary
tertiary sources (e.g., encyclopedic summaries of the primary literature) rather
than the primary papers directly, because several primary-source fetches (KRX
official PDFs, paywalled journals) were not reachable during this pass. Metadata
(author, title, journal, year, volume) is reported with that caveat. Korea-market
numeric parameters were cross-checked against this repository's own code and prior
internal research and are marked as *internally corroborated* — KRX's current
rulebook remains the final authority at spec-writing time.

---

## 1. Decision Framework

### (a) Core concepts and standard models

Systematic/algorithmic trading systems are conventionally decomposed into a
**pipeline with hard separation of concerns** (Chan 2013; Narang 2013):

1. **Signal/alpha generation** — a function of market state producing a *view*
   (forecast, score, ranking), generally without direct reference to current
   holdings, cash, or venue mechanics. Where "edge" lives; most-iterated component.
2. **Decision/portfolio-construction layer** — combines signals with current state
   (positions, risk budget, constraints) to produce a **target position** or
   **trade intent**: not an order, but a desired end-state. Where alpha is
   translated into "what should the book look like."
3. **Risk layer** — a gate/filter that can veto, scale down, or delay a target
   position on portfolio-level constraints (VaR/ES budget, drawdown state, leverage
   limits, correlation, concentration) — independent of *why* the signal fired.
4. **Execution layer** — translates an approved target position into child orders,
   deciding *how* and *when* to trade, not *whether* (decided upstream).

This alpha/risk/execution separation is a design pattern (Narang 2013; Grinold &
Kahn 2000 for the alpha/portfolio-construction split), consistent with the
buy-side "PM decides, trader executes" division formalized by **Perold's
Implementation Shortfall** (see §3), which explicitly measures the gap between
"decision" and "execution."

**Trade intent / target position** as a first-class object (vs. raw orders) is the
standard OMS/EMS abstraction and the "parent order" concept of execution algos: a
parent order (the intent — "acquire 10,000 shares by EOD") is distinct from the
child orders that implement it. Generalizes cleanly to a "target position" model
where the intent layer periodically emits a desired position and a separate
reconciliation/execution process moves current → target.

**Deterministic vs. stochastic decision policies.** Deterministic if the same
market + portfolio state always yields the same target (pure function, no internal
randomness, no hidden state). Stochastic if randomization is intentional
(ε-exploration, randomized slicing for anti-gaming, sampling from a predictive
distribution). RL literature (Sutton & Barto 2018) formalizes π(s)→a vs. π(a|s).
For audited systems the load-bearing distinction is **reproducibility**, not the
RL-theoretic one: a policy can be internally "stochastic" (sampling) yet fully
reproducible if the RNG is seeded and the seed logged.

**Auditability / reproducibility** (consistent across model-risk guidance such as
Fed/OCC **SR 11-7**, 2011):
- **Determinism given logged inputs**: same (market snapshot, portfolio state,
  config version, model version) → same decision, re-derivable.
- **Point-in-time input snapshotting**: exact feature/indicator/config values at
  decision time persisted, not recomputed later from revised data.
- **Decision provenance/lineage**: every order traces to the signal, model
  version, config version that produced it.
- **Versioning of config and model artifacts**: since config-driven systems change
  behavior via YAML/parameters, the config version is part of the reproducibility
  record — not just the code commit.
- **Separation of decision-time from execution-time logging**, so audit can
  distinguish "decision was wrong" from "decision right, execution poor."

### (b) Canonical references

| Reference | Detail |
|---|---|
| Grinold & Kahn | *Active Portfolio Management* (2nd ed.), McGraw-Hill, 2000 — alpha/portfolio-construction separation, information ratio, alpha-to-weight transfer. |
| Narang | *Inside the Black Box* (2nd ed.), Wiley, 2013 — practitioner description of signal/construction/execution/risk pipeline. |
| Chan | *Algorithmic Trading: Winning Strategies and Their Rationale*, Wiley, 2013. |
| Perold | "The Implementation Shortfall: Paper vs. Reality," *J. Portfolio Management*, 1988 — decision-price vs. execution-price. *(verify primary source.)* |
| Sutton & Barto | *Reinforcement Learning: An Introduction* (2nd ed.), MIT Press, 2018 — deterministic/stochastic policy definitions. **NB: this repo's CLAUDE.md excludes RL from the current runtime — cite only as generic decision theory, not an implementation direction.** |
| Fed / OCC | SR 11-7, "Guidance on Model Risk Management," 2011 — regulatory-grade framework for model auditability, versioning, outcomes analysis. |

### (c) Korea-specific relevance

The alpha/decision/risk/execution separation is not Korea-specific. What *is*: the
exogenous state the decision layer must treat as input —
- KRX session structure (open/close auctions, continuous session, no lunch break)
  constrains *when* a target position can legally become orders (§2).
- KOSPI200 futures' distinct day/night session policy, and this project's decision
  (`config/market_schedule.yaml`) to keep night session fail-closed disabled, means
  the decision layer's "trading state" must model session-open/closed as a
  first-class KST-anchored input, not assume 24h continuity.
- KRX price limits and Volatility Interruption (VI) halts mean a target position
  can become *unreachable* mid-session — the audit trail must distinguish
  "not implemented because of an exchange-level halt" from an execution failure.

### (d) Open questions for a spec author

- Atomic unit of "decision": per-symbol target position, or portfolio-wide target
  weight vector? Support both?
- How is a stochastic component (e.g. LLM-based context scoring, which this project
  uses) reconciled with reproducibility — is "reproducible given a logged LLM
  response" sufficient, or is bit-for-bit determinism required?
- Minimum logging granularity to reconstruct *why* a decision was made 6 months
  later without re-running any live service?
- How to represent "no decision" (hold) vs. "explicit flat" (target = 0) — both
  need reproducible audit trails.

---

## 2. Market Model

### (a) Core concepts and standard models

**Order book / bid-ask spread.** The limit order book (LOB) is the microstructure
primitive; the **bid-ask spread** is the most basic cost-of-immediacy measure.
Canonical: O'Hara, *Market Microstructure Theory*, Blackwell, 1995; Harris,
*Trading and Exchanges*, Oxford UP, 2003.

**Market impact.** Price move caused by a trade, split into **temporary** (reverts)
and **permanent** (information) components — central to Almgren-Chriss (§3) and to
Kyle, "Continuous Auctions and Insider Trading," *Econometrica* 53(6):1315–1335,
1985 ("Kyle's lambda" linear price-impact model).

**Liquidity** is multidimensional: tightness (spread), depth (size at/near best),
resiliency (replenishment speed). No single formula; operationalized via spread,
top-of-book depth, depth-weighted average price for a given size.

**Volatility — realized volatility and HAR-RV.** Realized variance/volatility (RV)
estimates variance from summed squared high-frequency returns, converging to
quadratic variation (subject to microstructure-noise bias at very high frequency).
- Andersen, Bollerslev, Diebold, Labys, "Modeling and Forecasting Realized
  Volatility," *Econometrica* 71(2):579–625, 2003.
- **HAR-RV**: Corsi, "A Simple Approximate Long-Memory Model of Realized
  Volatility," *J. Financial Econometrics* 7(2):174–196, 2009. **Already
  implemented in this codebase** (`shared/forecasting/volatility_har_rv.py`, citing
  Corsi 2009) — the citation is standard and correctly attributed.

**Price formation / regimes.** Kyle 1985; Glosten & Milgrom, "Bid, Ask and
Transaction Prices...," *J. Financial Economics* 14(1):71–100, 1985. "Regime" is
used loosely for a persistent volatility/trend/liquidity state; formal
regime-switching via Markov-switching (Hamilton, *Econometrica* 57(2):357–384,
1989) or simpler RV-percentile/threshold heuristics (closer to what HAR-RV-based
regime gating does in practice, and what this repo's `regime-gate-analyst`
implements).

### (c) Korea-specific relevance (internally corroborated; confirm vs KRX rulebook)

- **KRX equity session**: pre-market quote window, continuous double-auction
  regular session (09:00–15:30 KST for KOSPI/KOSDAQ), opening + closing call
  auctions bracketing it, after-hours session after close. This repo's
  `config/market_schedule.yaml` models 09:00–15:30 regular + 08:30–08:40 pre-market
  + 15:40–16:00 after-market — treat the exact extended-hours minutes as operative
  internal config, not an external-source claim.
- **Daily price limit**: KRX equities ±30% around previous close (widened from an
  earlier ±15% regime; exact effective date to verify against a KRX/regulator
  announcement). Repo code comment (`parquet_backfill.py`) independently states
  "±30% daily limits / VI halts."
- **Volatility Interruption (VI)**: static VI (single large move from static
  reference → short cooling-off auction) and dynamic VI (large deviation from last
  trade in a short window), per-stock, distinct from the market-wide circuit
  breaker. Exact thresholds (informally ~10% static / ~2–3% dynamic) **need
  primary-source confirmation from the current KRX rulebook**.
- **Market-wide circuit breaker + sidecar**: index-level trading halt distinct from
  per-stock VI, plus a "sidecar" that temporarily suspends program trading on sharp
  KOSPI200-futures moves (a sidecar event occurred 2025-04-10). Exact triggers need
  primary-source verification.
- **Tick size**: price-banded schedule (smaller ticks for low-priced stocks) —
  standard on KRX; pull the current band table from KRX at spec time (revised
  periodically).
- **KOSPI200 futures/options**: standard contract **KRW 250,000/point, 0.05-point
  tick**; **mini KRW 50,000, 0.02-point tick** — corroborated by this repo's
  `shared/execution/futures_instrument.py` (`_PRODUCT_TICK_SIZE = {"mini": 0.02,
  "kospi200": 0.05}`) and prior internal research. Expiry
  **second-Thursday-of-the-month**, cash-settled against the final KOSPI200 index.
  Futures daily price-limit band (repo comment: "±10%", stepped/expanding on
  successive limit-hit days) — reconfirm against primary source.
- **Night session**: a separate KOSPI200 night session (~18:00–05:00 KST) exists;
  this repo disables it (`market_schedule.futures.night.enabled: false`) as a
  deliberate fail-closed operator policy.

### (d) Open questions for a spec author

- Which exact VI/circuit-breaker thresholds and tick-size band table to pin to a
  version/date, and how to require refreshing them when KRX revises.
- Should the Market Model formally define "regime" (e.g. HAR-RV percentile bands)
  or leave regime classification to a downstream consumer (`regime-gate-analyst`)?
- How to represent a stock-level VI halt interacting with portfolio-level decisions
  that assumed liquidity (hands off to Risk and Execution).
- Model KOSPI200 mini vs full as two instruments sharing parameterized logic (the
  existing `futures_instrument.py` pattern) or fully separate models?

---

## 3. Execution Model

### (a) Core concepts and standard models

**Optimal execution — Almgren-Chriss.** Canonical framework for optimally
liquidating/acquiring a position over a fixed horizon, trading market-impact cost
against price-risk (volatility) exposure:
- Almgren & Chriss, "Optimal Execution of Portfolio Transactions," *J. Risk*
  3(2):5–39, 2001.

Total cost = temporary impact (function of trading rate, non-persistent) +
permanent impact (function of total quantity, persistent) + λ·Var[cost] penalizing
path variance, λ = risk-aversion. λ=0 → TWAP-like; λ→∞ → immediate execution;
intermediate λ → front-loaded trajectory. Produces an "efficient frontier" of
execution strategies (expected cost vs. cost variance), analogous to Markowitz.

**Implementation shortfall.** Gap between the "paper" return at decision time and
the actual realized return after frictions — decomposed into delay cost, execution/
impact cost, opportunity cost (unfilled). Perold 1988. *(verify primary source.)*

**VWAP / TWAP.** VWAP = Σ(price·volume)/Σ(volume); both a benchmark and a strategy
(slice to track the volume profile). TWAP slices equally over time. Benchmark
attribution: Berkowitz, Logue, Noser, "The Total Cost of Transactions on the NYSE,"
*J. Finance* 43(1):97–112, 1988. Optimal VWAP-tracking as control: Kato, *JSIAM
Letters* 7:33–36, 2015; Cartea & Jaimungal, *SIAM J. Financial Math.* 7(1):760–785,
2016.

**Impact models: temporary vs permanent** — see §2 (Kyle 1985; Almgren-Chriss).
Square-root impact (cost ∝ √(size/ADV)) is widely used in practitioner TCA but is
more empirical folklore than a single canonical citation — treat as "well-
established heuristic, exact attribution contested."

**Slippage, order types, SOR.** Slippage = realized vs. reference price, the
practical model-agnostic execution-quality metric. Order types (market, limit,
stop, iceberg/hidden, pegged) and smart order routing are standard institutional
topics (Harris 2003); SOR is a routing policy, not a "model."

**Broker-API (non-DMA) relevance — a critical distinction for this project.**
Almgren-Chriss and most academic optimal-execution theory assume **direct market
access** (control of placement, cancellation, sometimes queue position at
microsecond level). A **broker-API path** (KIS REST/WebSocket) sits one layer
removed: the system submits orders to the broker, which interacts with the
exchange, subject to broker-side rate limits, ack latency, and no control over
internal routing/queue mechanics. Practical consequences (Narang 2013; Harris
2003):
- Optimal-execution *trajectories* remain useful as a conceptual scaffold for
  *slicing decisions*, but their *implementation* is constrained by API rate
  limits, quote staleness, and ack/fill latency, not queue-priority control.
- TCA becomes more important as a *measurement* discipline precisely because the
  system cannot observe/control the exchange-side queue — slippage vs. arrival
  price and vs. VWAP become the primary observable execution-quality proxies.
- Broker-API systems typically cannot implement true iceberg/hidden or
  exchange-native pegged orders unless the broker exposes them; "smartness" is
  usually limited to order-type selection, timing/slicing, and passive-vs-aggressive
  placement (this repo's `passive_maker.py`, `pseudo_oco.py` reflect exactly this
  broker-API-constrained execution logic).

### (c) Korea-specific relevance

- KIS is a retail/institutional broker API, not a direct exchange-member
  connection — the non-DMA caveat applies directly.
- KRX's discrete tick schedule and KOSPI200 futures' 0.05/0.02-point ticks bound
  feasible limit-price granularity and therefore slicing/limit-order strategies.
- Continuous double-auction + opening/closing call auctions means naive TWAP/VWAP
  slicing must explicitly decide whether/how to participate in the call-auction
  phases (different price-formation mechanics).
- Price limits / VI halts mean an in-flight schedule can be interrupted by an
  exchange-level halt independent of strategy logic — the execution model needs a
  defined "order rejected/halted mid-schedule" behavior.
- KIS enforces its own request-rate ceilings — an execution-model constraint on top
  of tick/session constraints.

### (d) Open questions for a spec author

- Adopt an explicit Almgren-Chriss cost/risk tradeoff, or a simpler heuristic
  slicing schedule justified by the non-DMA/broker-API constraint (is the added
  sophistication realizable through KIS)?
- Correct execution benchmark: arrival price (implementation shortfall), VWAP, or
  decision-time mid — and does the choice differ between stock and futures
  pipelines (futures backtests already assume a fixed 0.3×tick slippage in
  `decision_harness.py`)?
- How to estimate temporary vs. permanent impact when the broker API exposes only
  top-of-book / limited depth?
- How to represent call-auction participation distinctly from continuous-session
  logic?

---

## 4. Risk Model

### (a) Core concepts and standard models

**Value-at-Risk (VaR).** α-quantile of the loss distribution over a holding period:
VaR_α(L) = F_L⁻¹(α). Three standard estimators:
- **Parametric/variance-covariance** (typically normal): VaR = z_α·σ·√t·value.
  Popularized by J.P. Morgan RiskMetrics (1994).
- **Historical simulation**: empirical past-return distribution applied to the
  current portfolio, no distributional assumption.
- **Monte Carlo**: simulate from an assumed risk-factor model and revalue.

Textbook: Jorion, *Value at Risk* (3rd ed.), McGraw-Hill, 2006.

**Expected Shortfall / CVaR.** Average loss *beyond* VaR:
ES_α(L) = E[L | L ≥ VaR_α(L)]. Unlike VaR, ES is a **coherent** risk measure and is
Basel-mandated (FRTB moved market-risk from VaR to ES) — useful regulatory context
even though this system is not a bank.

**Coherent risk measures** (Artzner, Delbaen, Eber, Heath, "Coherent Measures of
Risk," *Mathematical Finance* 9(3):203–228, 1999) — four axioms:
1. **Monotonicity** — A's outcomes always ≥ B's ⇒ ϱ(A) ≤ ϱ(B).
2. **Sub-additivity** — ϱ(A+B) ≤ ϱ(A)+ϱ(B) (diversification cannot increase risk).
3. **Positive homogeneity** — ϱ(αA) = αϱ(A), α ≥ 0.
4. **Translation invariance** — ϱ(A + cash) = ϱ(A) − cash.
This is also the standard citation that **VaR is not sub-additive** (can penalize
diversification) while ES/CVaR is.

**Position sizing.**
- **Kelly criterion** — optimal bet-sizing to maximize long-run geometric growth;
  f* = p/l − q/g in the binary case (f* = edge/odds generally). Kelly, "A New
  Interpretation of Information Rate," *Bell System Technical Journal*
  35(4):917–926, 1956. Applied to trading via log-utility/growth-optimal framing
  (Thorp 1997/2006 — secondary/applied, verify before citing).
- **Volatility targeting** — scale size inversely to estimated volatility so
  portfolio vol stays near target; standard in CTA/risk-parity (Moskowitz, Ooi &
  Pedersen, "Time Series Momentum," *J. Financial Economics* 104(2):228–250, 2012,
  uses ex-ante vol scaling explicitly).
- **Fixed-fractional** — risk a constant fraction of equity per trade; size =
  (equity·risk_fraction)/(stop_distance·multiplier). Practitioner heuristic (Vince),
  not a peer-reviewed source; this repo already implements a variant
  (`FixedFractionalFuturesSizer`).

**Drawdown control.** Max drawdown (peak-to-trough) is the standard path-risk metric
(distinct from distributional VaR/ES); typically treated empirically or via
drawdown-based sizing in trend-following literature.

**Leverage / futures margin.** Initial/maintenance/variation margin is an
exchange/clearing mechanism, not an academic model; most exchanges (incl. KRX) use
a SPAN-like scenario-based margining set by the clearing corporation (in Korea, KRX
acts as CCP for KOSPI200 futures).

### (c) Korea-specific relevance

- KOSPI200 futures margin is set by KRX (as CCP), periodically revised — treat
  margin rate as an external refreshable input, not a hardcoded constant (this repo
  resolves it via `shared/risk/futures_margin.py` rather than inlining).
- KRX's ±30% equity price limit and narrower futures band cap worst-case single-day
  loss on an unhedged position — a Korea-specific tail/VaR calibration input
  (contrast U.S. equities, no hard daily limit).
- KOSPI200 futures leverage (KRW 250,000 or 50,000/point against a relatively small
  margin) makes leverage/margin-based position limits especially load-bearing for
  the futures book — consistent with CLAUDE.md's long/short symmetry and futures
  leverage-limit emphasis.
- Circuit-breaker/VI halts interact with risk: a model that assumes continuous
  liquidity to de-risk ("if VaR breach, immediately reduce") can be blocked
  mid-execution by a halt — needs an explicit fallback (block new risk, wait for
  reopen) rather than assuming unwind is always achievable in its own horizon.

### (d) Open questions for a spec author

- Which VaR/ES method given data depth and the fact that KOSPI200-futures returns
  are not well-approximated by normal (fat tails, jump risk around macro releases)
  — parametric VaR could understate tail risk.
- Adopt ES/CVaR as primary (coherent, Basel-aligned) rather than VaR given VaR's
  non-subadditivity, or keep VaR for interpretability with ES as a secondary check?
- How does vol-targeting sizing interact with the HAR-RV forecast already in the
  codebase — is the same RV/vol estimate meant to serve both regime classification
  and vol-targeting sizing, or deliberately decoupled?
- How to express margin/leverage limits when an unlevered cash-equity book and a
  levered KOSPI200-futures book share one risk budget — single portfolio-level
  VaR/ES, or asset-class sub-limits?
- Interaction of drawdown control with the existing consecutive-loss size-reduction
  mechanism — formalize drawdown control as a distinct complementary control, or
  fold into the same state machine?

---

## 5. Portfolio Hedge Model

### (a) Core concepts and standard models

**Beta hedging.** Contracts to hedge an equity portfolio's market exposure with an
index future:

    N = −β_portfolio × (V_portfolio / (Futures_price × Multiplier))

The textbook "hedge the index future in proportion to systematic risk" formula
(Hull, *Options, Futures, and Other Derivatives*, 10th/11th ed., Pearson — the
standard derivatives text, covering stock-index-futures hedging explicitly).

**Minimum-variance hedge ratio.** For a general hedge:

    h* = ρ(ΔS, ΔF) × (σ_S / σ_F) = Cov(ΔS, ΔF) / Var(ΔF)

the OLS slope of spot-price changes on futures-price changes — the foundational
cross-hedging result. Johnson, "The Theory of Hedging and Speculation in Commodity
Futures," *Review of Economic Studies* 27(3):139–151, 1960; Ederington, "The
Hedging Performance of the New Futures Markets," *J. Finance* 34(1):157–170, 1979
(popularizes the min-variance hedge ratio and the R² "hedging effectiveness"
measure). *(These two not independently re-verified this pass — extremely
well-established; final citation check recommended.)* Also in Hull.

**Basis risk.** Hedge instrument does not move in exact lock-step with the hedged
exposure — from (i) tracking a different (imperfectly correlated) underlying
(cross-hedge basis risk) and (ii) futures basis convergence to spot near expiry
along an unpredictable path. Treated in Hull and the commodity-hedging literature.

**Roll/expiry management.** A hedge maintained past a contract's expiry must be
"rolled" (close expiring, open next), introducing roll cost/basis risk at whatever
basis prevails at roll time. Practitioner-operational (Hull; CTA literature).

**Delta hedging basics.** For options-based hedges (relevant if KOSPI200 *options*
are used), hold underlying/futures = −(delta × option position × multiplier) so the
combined position is instantaneously price-insensitive; rebalance dynamically as
price/time/vol change. Black & Scholes, "The Pricing of Options and Corporate
Liabilities," *J. Political Economy* 81(3):637–654, 1973; Hull for applied dynamic
hedging.

### (c) Korea-specific relevance

- **KOSPI200 futures as the standard Korean equity-hedge instrument** — the most
  liquid instrument to hedge a diversified Korean large-cap book, analogous to
  S&P 500/E-mini for a U.S. book. Standard market practice.
- **Multiplier-driven hedge sizing** — the standard contract's KRW 250,000
  multiplier vs the mini's KRW 50,000 differ by 5× in the hedge-ratio denominator
  (futures notional per contract); a spec must state which contract the sizing
  assumes, especially since this repo's runtime is config-selectable between "mini"
  and "kospi200" (`FUTURES_TRADING_PRODUCT`).
- **Cross-hedging basis risk for non-KOSPI200-representative portfolios** — if the
  book is concentrated / includes KOSDAQ names / is a differently-weighted subset,
  the hedge is a cross-hedge with nontrivial basis risk; the min-variance
  hedge-ratio (beta-to-KOSPI200, not naive one-for-one notional) is the
  textbook-correct approach.
- **Roll/expiry management under the second-Thursday cycle** — a hedge held across
  rolls needs an explicit policy (roll timing vs. expiry, roll-cost budget,
  all-at-once vs. staggered).
- **Price-limit/VI interaction with hedge maintenance** — both legs are
  independently subject to KRX limits/VI, so a hedge can become temporarily
  unbalanced (one leg halted, the other trading) — a Korea-specific operational
  risk with no direct analog in markets without hard daily limits.
- **Night session and hedge continuity** — since this repo disables the KOSPI200
  futures night session, a futures-based hedge is only actively maintainable during
  the KST day session; overnight/global-event equity risk is *not* currently
  hedgeable via the futures leg outside day-session hours — a binding constraint
  (already-made operator policy), not merely a theoretical open question.

### (d) Open questions for a spec author

- Static beta-based hedge ratio, rolling/regression-estimated min-variance ratio, or
  dynamically re-estimated (rolling window / EWMA covariance) — and over what
  window given Korean regime shifts?
- Denominate hedge sizing in mini or full contract (or config-driven, consistent
  with `FUTURES_TRADING_PRODUCT`), and handle fractional-contract rounding/residual
  basis risk explicitly?
- Roll policy: calendar-day trigger, volume-based, or explicit operator action
  across the second-Thursday cycle?
- If the book is not KOSPI200-representative, is portfolio beta computed against
  KOSPI200 specifically or a broader proxy, and how often re-estimated (the index
  went free-float-weighted in 2007)?
- Given the night-session-disabled policy, document "unhedged overnight/global-event
  gap risk" as accepted residual risk, or define a compensating control (pre-close
  de-risking, reduced overnight equity limits)?

---

## Citation-verification status

| Fact/citation | Status |
|---|---|
| Almgren & Chriss (2001), *J. Risk* 3(2):5–39 | Verified via secondary source |
| Artzner, Delbaen, Eber, Heath (1999), *Math. Finance* 9(3):203 | Verified via secondary source; axioms confirmed |
| Corsi (2009) HAR-RV, *J. Financial Econometrics* 7(2):174–196 | Verified via secondary source; also used/cited in this repo's code |
| Andersen, Bollerslev, Diebold, Labys (2003), *Econometrica* 71(2):579–625 | Verified via secondary source |
| Kelly (1956), *Bell System Technical Journal* 35(4):917–926 | Verified via secondary source |
| Berkowitz, Logue, Noser (1988), *J. Finance* 43(1):97–112 | Verified via secondary source |
| Perold (1988) Implementation Shortfall | NOT independently verified — recommend primary-source check |
| Johnson (1960) / Ederington (1979) min-variance hedge ratio | NOT independently verified (fetch failures) — well-established; recommend check |
| KRX equity ±30% price limit | Corroborated by repo code comments; exact 15%→30% effective date not confirmed |
| KRX static/dynamic VI exact thresholds | NOT confirmed — check current KRX rulebook at spec time |
| KOSPI200 futures 250,000/0.05, mini 50,000/0.02, second-Thursday expiry | Corroborated by repo code (`futures_instrument.py`) + internal research; confirm vs current KRX product spec |
| KOSPI200 futures ±10% daily price limit | Only repo code comment — flag for primary-source confirmation |
| KRX session hours (09:00–15:30 continuous + pre/post) | Verified via secondary source; consistent with repo config |

**Recommendation:** treat Korea-specific numeric thresholds (price limits, VI
percentages, tick bands, futures price-limit bands) as **living parameters pulled
from KRX's current published rulebook at spec-finalization time**, not hardcoded
into spec text — KRX has revised several historically and will again.
