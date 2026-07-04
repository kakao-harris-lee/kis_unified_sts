# Futures Conviction-Hold Strategy (THESIS C) — Research, Design, Validation

Status: **[NEEDS-VALIDATION]** — prototype gate + counterfactual evidence pending review.
Author: regime-gate-analyst
Date: 2026-06-25
Branch: `feat/futures-conviction-hold`
Asset: KOSPI200 futures (backtest symbol `101S6000`, trade `A05xxx`), paper-only.

---

## 1. Problem statement (THESIS C)

On 2026-06-25 the KOSPI cash index surged ~+3% on a semiconductor-led intraday
**trend** day. The futures book made 0 trades — Setup A/C are mean-reversion / event
strategies and neither targets a sustained domestic directional move. THESIS C asks
whether a **high-conviction directional HOLD** can capture such days *without*
bleeding on the many chop days, by taking a position **only when multiple
independent high-conviction signals ALIGN**:

> MFI regime STRONG  +  LLM daily bias strong same-direction  +
> semiconductor (반도체) sector-leadership / breadth confirmation
> → HOLD for the session with a WIDE trailing stop; stay FLAT otherwise.

This is **not** a per-bar trend entry (that family is falsified — see §2). It is a
*gated directional hold*, few trades/month. **The crux is the GATE**: can the
conjunction separate the genuine big-trend days from the false starts (days that
begin trending then reverse) **ex-ante**? If it cannot, that is the finding.

## 2. The hard constraint (the same wall every futures-trend idea hits)

Intraday KOSPI200 futures are **predominantly mean-reverting** — the established,
repeatedly-reproduced finding in this repo. Standalone intraday TREND entry is
falsified (`macd_ema ~-106%`, `williams_r ~-14`, `momentum` bankrupt; closed PR
#529). Most recently the **triple-gated ORB trend-day** strategy (efficiency +
vol-expansion + direction-agreement) also failed walk-forward — OOS Sharpe −0.18,
IS→OOS inversion, tightening the central gate made OOS *worse*
(`docs/superpowers/plans/2026-06-25-futures-trend-day-strategy.md`, NO-SHIP).

THESIS C is a different *shape* (a gated HOLD, not a breakout entry), so it deserved
its own honest test. But it inherits the same burden of proof: **the gate must
demonstrably avoid the chop/reversal days.** A conjunction that cannot pre-identify
trend days is not worth shipping.

## 3. What is actually available (and what is NOT) — the data reality

The gate has three conviction arms. They are **asymmetrically backtestable** on the
only clean window (`101S6000`, Dec 2025 – Apr 2026):

| Arm | Live source | Historically replayable on clean window? |
|-----|-------------|------------------------------------------|
| **MFI regime** (BULL_STRONG / BEAR_STRONG) | `MarketClassifier` on futures price/volume; computed inline in the orchestrator (`_classify_market`) — **not** published to Redis for futures | **Yes** — recomputed per-bar from minute bars (the backtest adapter already injects it via `MarketClassifier`). |
| **Semiconductor leadership** (반도체) | Derivable from Samsung `005930` + SK Hynix `000660` change% (screener `system:universe` carries per-symbol change%); no pre-built sector index | **Yes (daily)** — `005930`/`000660` have full **daily** parquet coverage for the window (105 / 102 days). A daily equal-weight basket vs KOSPI200 is computable ex-post. (Their *minute* history only starts March, so intraday alignment is not available — but a *daily* leadership read is exactly what a once-a-day conviction hold needs.) |
| **LLM daily bias** (`trading:futures:daily_bias` via `DailyBiasProvider`) | LLM market context → daily long/short/flat | **NO.** The `market_context_history` SQLite ledger starts **2026-06-04** (dev) / **2026-06-09** (paper). There is **zero** LLM-context history before June. The LLM-bias arm **cannot be replayed** on the Dec2025–Apr2026 window. This is a finding, not a gap I can engineer around — there is no pre-computed archive. |

**Design consequence.** The historically-testable gate is the **2-arm price/structure
conjunction** (MFI-strong + semiconductor-leadership + a morning directional-move
filter). The **LLM-bias arm is wired as an OPTIONAL, PERMISSIVE-on-missing live
confirmation** (§9): present forward, never blocking when absent, and explicitly
**unvalidated** historically. Any claim about the LLM arm's contribution is
forward-only and out of scope for this evidence.

## 4. Gate definition (precise)

A pure, strategy-agnostic conjunction filter
(`shared/strategy/gates/conviction_hold_gate.py`, mirrors `RegimeGate`'s
`(allow, reason, …)` contract). Evaluated **once** at a KST decision time
(default 10:00), it returns `(arm: bool, direction, reason, score)` using **only**
information available up to that time (look-ahead-safe — the caller computes every
input from bars ≤ ts). All arms are long/short symmetric.

1. **Morning structural arm** (energy + efficiency). From the open→decision path:
   - displacement `|decision − open| / open ≥ min_morning_disp_pct` (default 0.30%),
   - Kaufman efficiency ratio over the morning path `≥ min_morning_efficiency`
     (default 0.10 — note the granularity caveat in §6).
   The candidate **direction** is the sign of the morning displacement.
2. **MFI-regime arm.** When `require_mfi_strong`, the `MarketClassifier` state at the
   decision bar must be `BULL_STRONG` (long) / `BEAR_STRONG` (short).
3. **Semiconductor-leadership arm.** Prior-session 반도체 basket (Samsung+SK Hynix
   equal-weight) daily change must agree with the candidate direction by
   `≥ min_semi_leadership_pct` (default 0.50%).
4. **Optional LLM-bias arm** (`use_llm_bias`, default off). If a non-flat bias is
   present it must match the candidate; **missing/flat → permissive** (does not
   block) per §9. Cannot be validated historically (§3).

A "false start" is defined for scoring as: the gate armed a direction, but the day
**closed against** that direction.

## 5. Config (`config/gates/conviction_hold_gate_default.yaml`)

```yaml
enabled: false                  # FALSIFIED on clean window — ships disabled
min_morning_disp_pct: 0.30
min_morning_efficiency: 0.10
require_mfi_strong: true
min_semi_leadership_pct: 0.50
use_llm_bias: false             # optional, permissive, NOT historically validated
permissive_on_missing: true     # §9 — governs only the LLM arm
decision_hour: 10
decision_minute: 0
allow_short: true               # long/short symmetry
```

## 6. Methodology and a granularity correction (caught, not papered over)

Validation harness: `scripts/analysis/conviction_hold_counterfactual.py`. It builds a
per-day panel for `101S6000` (minute bars, regular session 09:00–15:30 KST),
evaluates the gate **ex-ante** at the decision time, and scores it against an
**ex-post** trend-day label built from the FULL day (used only to grade the gate,
never to compute it).

**Correction made during the work.** The first label definition reused the ORB doc's
intraday thresholds (move ≥1.5 ATR, ER ≥0.40) and found **0 trend days**. Diagnosis:
the Kaufman ER over a full day of **1-minute** bars is structurally tiny (the path
length — sum of ~390 absolute 1-min moves — is huge relative to net displacement). On
this window the cleanest real trend day (2026-01-27, +3.9%) tops out at ER ≈ 0.23
while the median day is ≈ 0.05. An ER ≥ 0.40 threshold is **unreachable** at 1-min
full-day granularity. The label was re-grounded in the data: **post-decision move ≥
1.0% of price AND ER ≥ 0.10** (a *relative* separator at this granularity — the 8
biggest-move days all clear ER ≥ 0.10; the median day does not). This yields 19/96
trend days (~20%), which matches intuition. A 0-trend-day result would have been a
false negative; this matters.

## 7. Results — the gate CANNOT separate trend days from false starts

### 7.1 Strict conjunction at the thesis decision time (10:00 KST), Dec 2025 – Apr 2026

| Metric | Value |
|--------|------:|
| trading days evaluated | 96 |
| genuine trend days (ex-post) | 19 (20%) |
| days the gate ARMED | 17 |
| true positives (armed → same-dir trend day) | **1** → true-pos rate **6%** |
| false starts (armed → day closed against) | **11** → false-start rate **65%** |
| recall on big-trend days (caught / 19) | **5%** |
| EOD-proxy PnL, hold-to-EOD (armed dir) | **−0.710% mean / −12.07% sum** (n=17) |
| EOD-proxy PnL, wide trailing stop (the thesis mechanism) | −0.162% mean / **−2.75% sum** |
| naive baseline (arm every day, morning-move dir, hold EOD) | −0.307% mean (n=96) |

The gate is **worse than the naive baseline** and the wide-trailing-stop HOLD (the
actual mechanism) loses money. Vivid false starts in the armed set:
`2026-02-02` armed LONG (MFI 64.8 BULL_STRONG, semi +2.73%) → day **−4.97%**;
`2026-03-27` armed SHORT (BEAR_STRONG, semi −5.47%) → day **+4.32%**;
`2026-03-25` armed LONG (semi +3.75%) → **−2.20%**.

### 7.2 Robustness sweep (decision time × strictness × thresholds)

Across the full grid (decision time 09:15–12:00; `min_disp_pct` 0.2–0.5;
`min_morning_er` 0.10/0.20; MFI-strong on/off): true-positive rate 0–27%,
false-start rate 38–100%, recall on trend days 0–17%. **EOD-proxy PnL is negative in
the overwhelming majority of cells**, and the **wide-trailing-stop sum is negative in
every single cell of the sweep** — the thesis mechanism never makes money anywhere.
The strict-conjunction cells are consistently among the worst.

A single isolated positive cell exists at **11:00** (e.g. +4.48% hold-to-EOD over 5
months) — but it is flanked by deep negatives at 10:00 (−12.96%), 10:15 (−6.12%),
10:30 (−6.26%) and 11:30 (−3.48%); its trailing-stop variant is still **negative**
(−1.65%); and by 11:00 the "hold the session" runway is largely spent. This is the
textbook noise-sensitivity / overfitting signature, not an edge.

### 7.3 Walk-forward split (thesis: 10:00 strict conjunction)

| Window | armed | true-pos rate | false-start rate | EOD-proxy sum | trail sum |
|--------|------:|--------------:|-----------------:|--------------:|----------:|
| Dec–Feb (IS)  | 8 | 12% | 62% | −4.56% | −0.88% |
| Mar–Apr (OOS) | 9 | **0%** | 67% | **−7.51%** | −1.87% |

Out-of-sample the gate caught **zero** trend days correctly and lost −7.51%. No
transferable edge.

### 7.4 Mechanism — *why* it fails (the substantive finding)

1. **The semiconductor-leadership arm has no day-to-day predictive value.** Prior-day
   Samsung+SK Hynix leadership agrees with next-day KOSPI200 direction **52%** of the
   time (corr −0.025 with next-day return). Sector leadership does not carry over.
2. **The morning-structure arm is *anti*-predictive.** The morning move (open→10:00)
   is **negatively correlated (−0.177)** with the rest of the day; rest-of-day
   continues the morning direction only **47%** of the time. Conditioning on "a strong
   morning move in a direction" systematically selects the days most likely to
   reverse — the mean-reversion tendency expressed at daily scale.
3. **Trend days are not identifiable at 10:00.** Of the 19 genuine trend days, only
   **37%** had their morning move already aligned with the eventual trend direction
   (most trend days were going the *other* way at 10:00 and reversed into the trend
   later), and trend days had *smaller* mean morning moves (0.76%) than chop days
   (0.84%). There is no ex-ante morning fingerprint of a trend day.
4. The failure is **symmetric** (long −8.42% / 38% win, short −3.65% / 25% win) — not
   a directional artifact.

The conjunction is strongest precisely on the overextended days that reverse, so it
arms *into* reversals. This is THESIS C's specific instance of the established
mean-reversion finding.

## 8. Sample-size caveat (honest)

By construction the strict conjunction arms rarely — 8–17 days over ~5 months. With
so few armed days the per-cell PnL is noisy and individual numbers should not be
over-read. **But the conclusion does not rest on one number**: it is the *direction*
agreement across (a) the strict 10:00 result, (b) a wide parameter sweep where the
trailing mechanism is negative in every cell, (c) the IS→OOS inversion, and (d) four
independent mechanism diagnostics (§7.4), all of which point the same way. A tiny
sample that is *consistently* negative and mechanistically explained is a sound
no-ship; it is not a "needs more data" verdict for *this* design. (More data could
not rescue an anti-predictive signal.)

## 9. Ship / No-ship recommendation

**NO-SHIP.** Do not enable `conviction_hold_gate` for paper promotion.

Rationale:
- The gate **fails the only question that matters** — ex-ante separation of trend
  days from false starts: 6% true-positive rate, 65% false-start rate, 5% recall,
  0% OOS true-positive rate.
- The thesis mechanism (wide-trailing HOLD) is **negative across the entire
  parameter sweep**, and the gate underperforms a naive everyday baseline.
- The failure is **robust and mechanistically explained**: two of the three arms are
  non-predictive (sector leadership) or anti-predictive (morning structure) on this
  market; the third (LLM bias) is **un-validatable** on the clean window.
- This reproduces, for a *gated directional HOLD*, the same finding that sank the
  triple-gated ORB breakout: intraday KOSPI200 is mean-reverting and the rare
  strong-trend days cannot be pre-identified at a mid-morning decision point.

**What is worth keeping** (the deliverable is not wasted):
1. The **negative result itself** — a rigorous, reproducible falsification of the
   "align multiple conviction signals → hold the trend" thesis, with a re-runnable
   harness for any future variant.
2. The reusable **`ConvictionHoldGate`** — a clean, config-driven, long/short
   symmetric, PERMISSIVE-on-missing conjunction filter (24 hermetic tests), available
   disabled as a building block and a guard against re-deriving this negative.
3. The **data finding** that LLM daily bias has no history before 2026-06; any future
   LLM-arm validation must wait for forward data accumulation (the scorecard that
   *validates* LLM calls only merged 2026-06-24).
4. The **granularity lesson** (Kaufman ER over 1-min full-day paths is structurally
   ≤~0.2; do not reuse 5-min intraday ER thresholds for daily-scale labels).

**If revisited**, the more promising direction is the same one the ORB doc reached:
**not** "hold the trend day," but feed a *confirmed-trend-regime* read into the
existing Setup A/C as a context modifier (e.g. relax/size mean-reversion, or suppress
counter-trend fades, on confirmed strong-regime days) — keeping the mean-reversion
edge that works while not fading the rare strong-trend day. That is separate work and
requires forward LLM-bias data to test the full conjunction.

The code ships **disabled** (`enabled: false`) as a tested, documented filter; it
must not be promoted to paper on these numbers.

## 10. Files

- Gate (pure filter): `shared/strategy/gates/conviction_hold_gate.py`
- Config (disabled): `config/gates/conviction_hold_gate_default.yaml`
- Counterfactual harness: `scripts/analysis/conviction_hold_counterfactual.py`
- Tests: `tests/unit/strategy/gates/test_conviction_hold_gate.py` (24),
  `tests/unit/analysis/test_conviction_hold_counterfactual.py` (9)

### Reproduce

```bash
# strict conjunction at the thesis decision time
python scripts/analysis/conviction_hold_counterfactual.py --decision-time 10:00
# relax the MFI-strong arm, sweep a different decision time
python scripts/analysis/conviction_hold_counterfactual.py --decision-time 11:00 --no-require-mfi-strong
```
