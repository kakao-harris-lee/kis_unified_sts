# ADR-DEV-010 — Backtest Admissibility, Cost Realism, and Disqualifiers

**ADR ID:** ADR-DEV-010
**Title:** Backtest Admissibility, Cost Realism, and Disqualifiers
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-010 — Testing Strategy (with RFC-005 §9, RFC-006 §11)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-010 §14 Q3
**Date:** 2026-07-16
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-16
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

A **Backtest is admissible as evidence toward a hypothesis** only when it meets every one
of the following, and is **disqualified** by any of the failure conditions:

* **Net of realistic cost.** Computed net of realistic execution cost, slippage, and
  market impact (RFC-005 §9; RFC-006 §11); an optimistic cost assumption disqualifies it.
* **Population and significance.** Evaluated over a population of decisions with
  sample-size, estimation-error, multiple-testing/selection-bias, and regime treatment
  (RFC-006 §11; philosophy §28); a single favorable run or an uncorrected search is not
  admissible.
* **No look-ahead.** Every indicator and input bounded by the current context timestamp,
  judged on information available at decision time; any future-data leak disqualifies it
  (RFC-003 §10, §12; RFC-010 §9).
* **Hermetic, reproducible, assumptions explicit.** Reproducible from recorded inputs
  (ADR-DEV-002) with its assumptions recorded (philosophy §37.8); an irreproducible or
  assumption-implicit backtest is void as evidence.
* **Not overfit.** Parameters not tuned on the evaluation data, and no result surviving
  only uncorrected multiple testing (RFC-006 §11 selection bias).

A Backtest — however favorable — is **evidence toward a hypothesis, never demonstrated
live edge, proof, or authority**; demonstrated live edge requires the restricted-live
verification ADR-002-025 owns.

This ADR fixes the admissibility bar and disqualifiers. It grants no authority, promotes
nothing, and authorizes no live operation.

---

## 2. Context

RFC-010 §6 and §10 hold that a backtest is bounded evidence, never demonstrated live edge,
and §11.9 forbids presenting a backtest as restricted-live evidence. RFC-005 §9 supplies
the cost/slippage/impact-realism apparatus and states a "claimed edge SHALL account for
realistic execution cost, slippage, and impact before it is treated as demonstrated."
RFC-006 §11 owns the statistical methodology: population-not-trade, net-of-realistic-cost,
significance/estimation-error/multiple-testing/selection-bias/regime, and "Backtests are
evidence, not proof" with live edge gated by ADR-002-025. philosophy §28 states backtests
are evidence, not proof.

RFC-010 §14 Q3 leaves open the concrete *admissibility bar* — what methodology and cost
realism is required before a backtest is admissible evidence toward a hypothesis — and
what explicitly *disqualifies* a look-ahead-biased or overfit backtest. This ADR fixes
both. It defines no new statistical methodology (RFC-006 §11 owns it), no cost apparatus
(RFC-005 §9 owns it), and no live gate (ADR-002-025 owns it) — it fixes the evidentiary
bar and the disqualifiers.

---

## 3. Decision Drivers

1. **A backtest is evidence, not proof** (philosophy §28; RFC-006 §11). Its admissibility
   must be bounded so it is not read as live edge.
2. **Optimistic cost is the commonest overstatement.** Ignoring realistic cost/slippage/
   impact inflates edge (RFC-005 §9; RFC-006 §11).
3. **Look-ahead is silent and fatal.** Future data leaking into a decision produces an
   un-tradeable result that looks excellent (RFC-010 §9).
4. **Overfitting and selection bias manufacture edge** from noise (RFC-006 §11).
5. **A green backtest is not readiness.** Live edge and authority require ADR-002-025, not
   a favorable simulation (RFC-010 §10; ADR-002-025).

---

## 4. Scope and Non-Scope

**In scope:**

* the admissibility bar for a Backtest as evidence toward a hypothesis;
* the explicit disqualifiers (look-ahead, overfit, optimistic cost, unrepresentative
  population, irreproducible);
* the bound that a Backtest is never live edge or authority.

**Not in scope (owned elsewhere):**

* the statistical expectancy methodology (population, significance, estimation error) —
  RFC-006 §11;
* the execution cost/slippage/impact apparatus — RFC-005 §9; the impact representation —
  RFC-004;
* the restricted-live verification and live-edge gate — ADR-002-025;
* reproducibility/identity granularity — ADR-DEV-002;
* concrete cost parameters, significance thresholds, and window choices, which are
  approved configuration and the Verification Profile.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-010 §5 (**Backtest**, **Test Assumption**),
RFC-005 §5 (**Slippage**, **TCA**), RFC-006 §11, and RFC-003 §12, and SHALL NOT introduce
synonyms. The following terms are scoped to this decision and are non-authorizing.

* **Admissible Backtest** — a Backtest that meets every §1 condition and so may be offered
  as evidence toward a hypothesis. Admissibility is evidentiary, not acceptance,
  promotion, or live-readiness.
* **Look-Ahead Bias** — the use, in a simulated decision at time t, of any input not
  available at or before t (future prices, revised data, survivorship-filtered universes).
* **Overfit** — a result that does not generalize because it depends on tuning parameters
  to the evaluation data, on an uncorrected multiple-testing search, or on an in-sample-only
  fit with no out-of-sample/holdout evaluation. Here **evaluation data** is data not used to
  select or tune the strategy; the concrete train/evaluation partition is RFC-006 §11
  methodology and the Verification Profile.

These terms describe an evidentiary bar. None grants authority or demonstrates live edge.

---

## 6. Safety Invariants

* **BTE-INV-001 — A Backtest Is Evidence Toward a Hypothesis, Never Live Edge or Proof.**
  A Backtest is bounded evidence; demonstrated live edge requires ADR-002-025's
  restricted-live verification (philosophy §28; RFC-006 §11; RFC-010 §10).
* **BTE-INV-002 — Admissible Only Net of Realistic Cost.** A Backtest is admissible only
  if computed net of realistic execution cost, slippage, and market impact; an optimistic
  cost assumption disqualifies it (RFC-005 §9; RFC-006 §11).
* **BTE-INV-003 — Population and Significance Required.** Admissibility requires
  population-based evaluation with sample-size, estimation-error, multiple-testing/
  selection-bias, and regime treatment; a single favorable run or an uncorrected search is
  inadmissible (RFC-006 §11; philosophy §28).
* **BTE-INV-004 — No Look-Ahead.** Every indicator and input SHALL be bounded by the
  current context timestamp — judged on information available at decision time; any
  future-data leak disqualifies the Backtest (RFC-003 §10 and §12; RFC-010 §9 hermeticity).
* **BTE-INV-005 — Hermetic, Reproducible, Assumptions Explicit.** A Backtest is admissible
  only if hermetic and reproducible from recorded inputs (ADR-DEV-002) with its Test
  Assumptions recorded; an irreproducible or assumption-implicit Backtest is void as
  evidence (RFC-010 §9; philosophy §37.8).
* **BTE-INV-006 — Overfit Is Disqualifying.** A result that depends on parameters tuned to
  the evaluation data (data not used to select or tune the strategy), that survives only
  uncorrected multiple testing, or that is an in-sample-only fit with no out-of-sample /
  holdout evaluation, is disqualified (RFC-006 §11 selection bias; the concrete
  train/evaluation partition is deferred to RFC-006 §11 and the Verification Profile).
* **BTE-INV-007 — A Backtest Creates No Authority.** An admissible or favorable Backtest
  grants no capacity, live authorization, promotion, or acceptance, and relaxes no safety
  gate (RFC-006 §11; RFC-010 §11; ADR-002-025).

---

## 7. The Admissibility Bar (RFC-010 §14 Q3, part 1)

A Backtest is an **Admissible Backtest** only when all hold (BTE-INV-002…006):

* **cost realism** — net of realistic execution cost, slippage, and market impact, using
  the RFC-005 §9 apparatus and the RFC-004 impact representation, never an optimistic
  assumption;
* **population and significance** — evaluated over a decision population with the RFC-006
  §11 treatment of sample size, estimation error, multiple testing/selection bias, and
  regime dependence, representing the uncertainty of the estimate rather than asserting it;
* **no look-ahead** — every indicator and input bounded by the context timestamp
  (RFC-010 §9);
* **hermetic and reproducible** — reproducible from recorded inputs with recorded Test
  Assumptions (ADR-DEV-002; philosophy §37.8);
* **not overfit** — parameters not tuned to the evaluation data, no in-sample-only fit
  without a holdout, and no edge surviving only uncorrected multiple testing (RFC-006 §11
  selection bias; BTE-INV-006).

Meeting the bar makes a Backtest admissible *as evidence toward a hypothesis* — it does
not accept, promote, or demonstrate live edge.

---

## 8. Disqualifiers (RFC-010 §14 Q3, part 2)

Any of the following disqualifies a Backtest as evidence (BTE-INV-002/003/004/005/006):

* **look-ahead bias** — any input used in a simulated decision at time t that was not
  available at or before t (future prices, revised/restated data, survivorship-filtered
  universe);
* **overfit** — parameters tuned to the evaluation data (data not used to select or tune),
  an edge surviving only uncorrected multiple testing, or an in-sample-only fit with no
  out-of-sample/holdout evaluation (RFC-006 §11 selection bias; partition per the
  Verification Profile);
* **optimistic cost** — cost/slippage/impact assumptions more favorable than realistic
  (RFC-005 §9);
* **unrepresentative population** — too few decisions, a single favorable run, or a
  regime-narrow sample presented as general (RFC-006 §11);
* **irreproducibility** — not reproducible from recorded inputs, or with implicit
  assumptions (ADR-DEV-002; philosophy §37.8).

A disqualified Backtest is not admissible evidence; it is not "weaker evidence" to be
weighed — it is out. This exclusion (not down-weighting) is this ADR's rule.

---

## 9. Alternatives Considered

* **9.1 Admit a gross (pre-cost) backtest as evidence.** Rejected: optimistic cost inflates
  edge; realism is required before an edge is "demonstrated" (RFC-005 §9; BTE-INV-002).
* **9.2 Admit a single favorable run.** Rejected: expectancy is a population property
  (RFC-006 §11; BTE-INV-003).
* **9.3 Treat look-ahead as a quality caveat, not a disqualifier.** Rejected: a look-ahead
  result is un-tradeable; it is out, not discounted (BTE-INV-004; RFC-010 §11.9).
* **9.4 Present a strong backtest as live-readiness.** Rejected: live edge requires
  ADR-002-025; a backtest is never live edge (BTE-INV-001, -007).
* **9.5 Define the statistical methodology or cost apparatus here.** Rejected: owned by
  RFC-006 §11 and RFC-005 §9 (§4).

---

## 10. Consequences

**Positive.**

* Gives RFC-010 §6/§10 a concrete admissibility bar and an explicit disqualifier list.
* Cost realism and anti-overfit discipline keep manufactured edge out of the evidence base.
* The never-live-edge bound preserves the ADR-002-025 promotion gate.

**Negative / costs.**

* Realistic cost modelling, look-ahead auditing, and multiple-testing correction raise the
  cost of producing admissible backtests.
* Some historically-favorable results become inadmissible (overfit/look-ahead), which is
  the intended effect.
* Reproducibility and recorded assumptions add tooling burden (shared with ADR-DEV-002).

---

## 11. Failure Modes Introduced by This Decision

* **11.1 Hidden look-ahead.** A subtle future-data leak (restated fundamentals,
  survivorship) passes as excellent; contained by BTE-INV-004 and reproducibility audit,
  but detection depends on the look-ahead review being thorough — a process risk flagged
  here.
* **11.2 Silent overfit.** An uncorrected search presented as a single result; blocked by
  BTE-INV-003/006 multiple-testing treatment.
* **11.3 Optimistic cost creep.** Slightly favorable cost assumptions; blocked by
  BTE-INV-002 (RFC-005 §9 realism).
* **11.4 Backtest-as-readiness.** A green backtest promoted toward live; blocked by
  BTE-INV-001/007 and ADR-002-025.

---

## 12. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010):

* **12.1** A gross/pre-cost or optimistic-cost backtest is inadmissible (BTE-INV-002).
* **12.2** A single-run or uncorrected-search result is inadmissible (BTE-INV-003, -006).
* **12.3** A backtest with any future-data leak is disqualified (BTE-INV-004).
* **12.4** An irreproducible or assumption-implicit backtest is void as evidence
  (BTE-INV-005).
* **12.5** An admissible/favorable backtest yields no capacity, promotion, or acceptance
  (BTE-INV-001, -007).
* **12.6** A disqualified backtest is excluded from the evidence base, not retained as
  down-weighted evidence (§8).

---

## 13. Acceptance Criteria

ADR-DEV-010 is acceptable when:

* the admissibility bar (cost realism, population/significance, no look-ahead, hermetic/
  reproducible/assumptions-explicit) is fixed (§7; BTE-INV-002…005);
* the disqualifiers (look-ahead, overfit, optimistic cost, unrepresentative population,
  irreproducibility) are explicit and out, not discounted (§8; BTE-INV-002/003/004/005/006);
* a Backtest is never live edge or authority (BTE-INV-001, -007), with the live gate left
  to ADR-002-025;
* independent adversarial review (EV-L0) confirms every §12 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 14. Traceability

| Requirement | Discharge in ADR-DEV-010 |
|---|---|
| RFC-010 §14 Q3 (backtest methodology/realism; disqualifiers) | admissibility bar (§7) and disqualifier list (§8) |
| RFC-010 §6, §10, §11.9 (backtest is bounded evidence; not live edge) | BTE-INV-001, -007 |
| RFC-005 §9 (cost/slippage/impact realism) | net-of-realistic-cost admissibility (§7; BTE-INV-002) |
| RFC-006 §11 (population; significance; net cost; backtest-not-proof) | population/significance bar; anti-overfit (§§7, 8; BTE-INV-003/006) |
| RFC-004 (impact representation) | impact consumed, not redefined (§7) |
| RFC-003 §10, §12 (determinism; information-at-decision-time; expectancy) | no look-ahead (BTE-INV-004); expectancy/cost realism (BTE-INV-002) |
| RFC-010 §9 (hermetic; reproducible artifact) | hermetic/reproducible/assumptions bar (BTE-INV-005) |
| ADR-DEV-002 (reproducibility from recorded inputs) | reproducible backtest (§7; BTE-INV-005) |
| ADR-002-025 (restricted-live promotion) | live edge separately owned; backtest not readiness (BTE-INV-001, -007) |
| philosophy §28, §29, §37.8 | backtest-is-evidence; population; assumptions bound the claim (§§1, 3, 7) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes the backtest
admissibility bar and disqualifiers and relies on RFC-005 §9, RFC-006 §11, and
ADR-002-025 for the cost apparatus, statistical methodology, and live gate.

---

## 15. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-010, resolving RFC-010 §14 Q3 (backtest admissibility bar and
  look-ahead/overfit disqualifiers).
* Set the decision: a Backtest is admissible evidence toward a hypothesis only if net of
  realistic cost, population/significance-treated, look-ahead-free, and
  hermetic/reproducible with explicit assumptions; look-ahead, overfit, optimistic cost,
  unrepresentative population, and irreproducibility are explicit disqualifiers; a
  Backtest is never live edge or authority.
* Defined seven invariants BTE-INV-001…007 and traced them to RFC-010 §6/§9/§10/§11,
  RFC-005 §9, RFC-006 §11, RFC-004, RFC-003 §10/§12, ADR-DEV-002, ADR-002-025, and
  philosophy §28/§29/§37.8.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding; the admissibility bar and disqualifier rule were confirmed sound and
  eleven of thirteen attacks fully blocked. Two Major findings were resolved: (M1) §8/§13
  named an incomplete invariant set for the five-item disqualifier list — now
  BTE-INV-002/003/004/005/006; (M2) the "overfit" disqualifier hinged on an undefined
  "evaluation data" that let an in-sample-only fit slip past — now "evaluation data" is
  defined as data not used to select or tune the strategy, in-sample-only-without-holdout
  is explicitly disqualifying, and the concrete train/evaluation partition is deferred to
  RFC-006 §11 and the Verification Profile. Five Minor fixes: look-ahead re-anchored on
  RFC-003 §12 (information available at decision time) beside RFC-010 §9; the population
  citation corrected from philosophy §29 to §28; overfit added as an explicit §7 bar item;
  the §14 expectancy-realism row reassigned to BTE-INV-002; and the §8 "out, not weaker
  evidence" rule kept as this ADR's own rather than propped on RFC-010 §11.9, with a §12.6
  obligation. The review is EV-L0 only and confers no acceptance or live-readiness.
