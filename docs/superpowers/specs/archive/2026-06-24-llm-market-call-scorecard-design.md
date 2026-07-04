# LLM Market-Call Scorecard — Design Spec

**Status:** Draft for review
**Date:** 2026-06-24

## Goal

Measure and report whether the pre-market LLM market call is **actually useful**, with a
validation-first scorecard that captures each day's structured prediction, scores it against
realized outcomes, and reports a baseline-relative track record. Trading actuation comes LATER,
gated on validation — this spec does NOT wire predictions into trading decisions.

Precise market prediction is impossible; the question is narrower and answerable: **does the LLM
call beat a naive baseline, and is its confidence calibrated?**

## Design principles (operator-confirmed)

1. **Validation first.** Build the scorecard before any automated trading reflection. Do not feed
   an unvalidated signal into the trading pipeline.
2. **Extensible facets.** "Direction / themes / movers / volume-surge" are EXAMPLES, not a fixed
   set. A *facet* (one scorable prediction type) is a first-class, registry-based abstraction;
   new facets plug in without touching the pipeline. Mirrors `shared/strategy/registry.py`.
3. **Score all four reference facets** in v1, built incrementally.
4. **Accuracy/calibration core + economic-value proxy.** Headline = is the call right + is
   confidence honest; secondary = a simple "act on the call" PnL proxy.
5. **Baseline-relative usefulness.** Every facet is scored against a naive baseline; "useful" means
   `edge = value − baseline > 0` robustly (report n + a simple significance flag; samples are small).
6. **No look-ahead.** Outcomes are read only from data timestamped AFTER the prediction's capture time.
7. **Iterative.** v1 = extensible core + reference facets; the design evolves under continuous testing.
8. **Repo conventions.** KST-native; runtime ledger (SQLite) + Redis DB1 with TTLs; config-driven;
   no ClickHouse; hermetic tests.

## Architecture & data flow

```
[pre-market ~ early session]        [post-close cron]            [aggregate]        [report]
 CAPTURE            ──persist──▶     SCORE          ──write──▶    AGGREGATE  ──▶    REPORT
 FacetPrediction(s)                 per-facet scorer             rolling metrics    Telegram daily/weekly
 (registered facets)                (realized vs predicted)      + baseline edge    (+ dashboard fast-follow)
   │                                      │                           │
   └─ ledger: llm_predictions             └─ ledger: prediction_scores ┘
      + Redis llm:prediction:latest
```

1. **CAPTURE** — the real morning/early-session call is persisted at the time it is made (today it
   is Telegram-ephemeral; this fixes that). Direction/themes from
   `scripts/llm_premarket_briefing.py` (`run_unified_analysis` → `MarketContext`); movers/volume-surge
   from the screener / intraday flag outputs at their flag time. The recorder iterates registered facets.
2. **SCORE** — a post-close cron iterates registered facets; each computes its realized outcome
   (bounded to after `captured_at`) and writes a score row.
3. **AGGREGATE** — rolling-window metrics per facet (hit-rate, calibration, theme spread,
   economic-proxy, edge vs baseline, n_scored).
4. **REPORT** — Telegram (BRIEFING channel): daily "yesterday's call scored" + weekly rolling
   track record. Dashboard (Quant Ops Workbench) page reads the same tables as a fast-follow.

## Facet abstraction (the extension point)

```python
@dataclass
class FacetPrediction:
    facet: str
    date_kst: str
    captured_at: datetime        # KST; the no-look-ahead boundary
    payload: dict                # facet-specific structured prediction
    confidence: float | None     # for calibration, if the facet carries one

@dataclass
class FacetScore:
    facet: str
    date_kst: str
    correct: bool | None         # None = unscorable (data gap) — NOT counted as wrong
    value: float                 # facet-native score (signed move / spread / follow-through rate)
    economic_proxy: float        # PnL of acting on the call (facet-native unit)
    baseline_value: float
    edge: float                  # value - baseline_value  (the "is it useful" number)
    detail: dict                 # per-item breakdown for the report
    scored_at: datetime

class PredictionFacet(Protocol):
    name: str
    outcome_horizon: str         # "same_session_open_to_close" | "next_session" | "T+30min" ...
    outcome_source: str          # "futures_minute" | "stock_daily" | "stock_intraday"
    def capture(self, ctx: CaptureContext) -> FacetPrediction | None: ...
    def score(self, pred: FacetPrediction, mkt: OutcomeData) -> FacetScore: ...
    def baseline(self, pred: FacetPrediction, mkt: OutcomeData) -> float: ...
```

- `CaptureContext` — available pre-market/early-session state: `MarketContext`, screener outputs,
  `forecast:event:latest`, redis clients.
- `OutcomeData` — a no-look-ahead accessor: returns market data only AFTER `pred.captured_at`.
- **Registry** — `register_facet()` / `FACET_REGISTRY`; recorder/scorer/aggregator/reporter iterate
  registered + config-enabled facets. Adding a facet = implement + register, no pipeline change.

## Reference facets (v1)

| facet | capture (prediction) | outcome / horizon · source | metric / economic_proxy | baseline → edge |
|---|---|---|---|---|
| **direction** | `MarketContext` direction (BULL/BEAR/NEUTRAL) + confidence + risk_mode | futures 101S6000 open→close return / same_session · futures_minute | sign hit + calibration / 1-unit directional PnL | always-flat & coin-flip → directional PnL − baseline |
| **themes** | `sector_rotation` top-N themes + constituent symbols | theme equal-weight close return / same_session · stock_daily | strong-theme mean − market mean spread / strong basket vs market | random-theme (≈ market) → spread |
| **movers** | pre-market flagged movers + direction (screener/trade_targets) | per-symbol follow-through return / session · stock_intraday | follow-through rate · mean follow-through return / mover-entry PnL | base-rate follow-through → excess |
| **volume_surge** | early-session volume-surge flags (symbol · flag time · flag price) | post-flag return / flag→close · stock_intraday | continuation rate · mean post-flag return / flag-entry PnL | random-entry → excess |

**Cross-cutting calibration** — for confidence-carrying facets (direction, optionally themes), bin
by confidence and check the correct-rate rises with confidence (reliability curve).

**Future facet candidates** (validate the abstraction; plug in later, not in v1):
`event_impact` (`forecast:event` vs realized move), `risk_mode` (vs realized volatility),
`macro_overnight` (vs KR open gap), `sector_rotation` (rotation correctness).

## Storage

- **SQLite runtime ledger** (`shared/storage/runtime_ledger.py`, runtime.db), two tables:
  - `llm_predictions` (date_kst, facet, captured_at, payload_json, confidence, created_at) —
    idempotent upsert per (date_kst, facet).
  - `prediction_scores` (date_kst, facet, correct NULLABLE, value, economic_proxy, baseline_value,
    edge, detail_json, scored_at) — idempotent per (date_kst, facet) (re-score overwrites).
- **Redis (DB1, TTL'd):** `llm:prediction:latest` (today's captured prediction, 48h),
  `llm:scorecard:latest` (latest aggregate for the dashboard).
- Aggregates computed on-demand from the tables in v1 (no separate aggregate table).

## Config — `config/llm_scorecard.yaml`

- Enabled facets + per-facet params: `direction.neutral_band`, `themes.top_n` + theme→symbols
  mapping source, `movers`/`volume_surge` horizon windows.
- Rolling windows (e.g. `[20, 60]` trading days).
- Baseline definitions per facet.
- Report toggles (daily/weekly Telegram on/off) + channel (BRIEFING).
- **Theme→symbols mapping**: reuse existing sector/theme tagging if present (KRX sector or the
  screener's theme tags); else a config map. The implementer verifies which source exists — this is
  the one external data dependency to confirm during implementation.

## Error handling

- **Capture** is best-effort: a recorder failure must NOT break the briefing or screener (try/except
  + log). A facet whose `capture` returns `None` (not applicable that day) is skipped — no row.
- **Score** is per-facet isolated: a data gap → `FacetScore.correct = None` (unscorable, logged +
  counted; never counted as wrong — honest metrics). No-look-ahead enforced by `OutcomeData`
  (only data after `captured_at`; use `LookaheadGuard` / timestamp bounds). Idempotent re-score.
- KST-native throughout; new Redis keys TTL'd; no ClickHouse.
- The scorer cron runs post-close and depends on the EOD/intraday data having settled; when outcome
  data is not yet available, the facet is marked unscorable and re-attempted on a later run.

## Testing (all hermetic, clocks pinned)

- **Per facet**: synthetic `FacetPrediction` + synthetic `OutcomeData` → expected `FacetScore`
  (correct/value/economic_proxy/baseline/edge); the unscorable-on-data-gap path; a no-look-ahead
  test (`OutcomeData` must not leak pre-`captured_at` data).
- **Recorder**: captures registered facets, idempotent upsert, best-effort (failure doesn't raise).
- **Aggregator**: rolling math (hit-rate, mean edge, calibration binning) on synthetic score rows.
- **Reporter**: Telegram formatting (daily + weekly), baseline/edge presentation; fake notifier.
- **Registry**: register/iterate; config enable/disable.
- No live KIS/Redis (fakes / fakeredis).

## Components / files

- `shared/llm_scorecard/` — `facets/base.py` (contract + registry),
  `facets/{direction,themes,movers,volume_surge}.py`, `recorder.py`, `scorer.py`, `aggregator.py`,
  `outcome_data.py`.
- `shared/storage/runtime_ledger.py` — the two tables + accessors
  (save_prediction / load_prediction / save_score / query_scores).
- `scripts/analysis/llm_scorecard_score.py` — post-close cron entry (score the day) + reporter
  (daily/weekly).
- Capture hooks: `scripts/llm_premarket_briefing.py` (direction/themes); the screener / intraday
  path (movers/volume-surge).
- `config/llm_scorecard.yaml`; `deploy/scheduler.crontab` (scorer + weekly-digest cron, off-hours /
  post-close, KST); `tests/unit/llm_scorecard/`.

## Incremental build order

1. Facet contract + registry + the two ledger tables + `OutcomeData` (no-look-ahead accessor).
2. **`direction` facet end-to-end** (capture → score → aggregate → daily Telegram) — proves the loop.
3. Add `themes`, `movers`, `volume_surge` facets via the registry.
4. Weekly digest + calibration curve.
5. Dashboard track-record page (fast-follow; separate, reads the same tables).

## Scope / out of scope

- **In:** the validation scorecard loop (capture, score, aggregate, Telegram report) + the
  extensible facet abstraction + the four reference facets.
- **Out (deferred until validated):** automated trading reflection (futures sizing/gating, stock
  theme/universe weighting from the call). `DailyBiasProvider` already feeds the LLM daily direction
  into the futures Setup A/C filter; broadening actuation waits on the scorecard showing edge.
- **Out (fast-follow, separate spec/plan):** the dashboard track-record page.
- **Evolving:** facets and metrics will be added/tuned iteratively under continuous testing.
