# No-Trade Diagnosis Plan — Stock + Futures

**Status:** Draft for approval
**Date:** 2026-06-24
**Goal:** Pinpoint the EXACT stage where each asset's trade decision stops, and
separate *legitimate selectivity* (don't "fix") from *broken blockage* (fix).
No real trade since 2026-06-11 (stock: 1 trade ever = 에코프로; futures: 7 trades, all 06-11).

## Grounding snapshot (2026-06-24 10:42 KST)
The earlier "bear gate" hypothesis is WRONG for the current state:
- **Both regimes = BULL_STRONG** (stock mfi 61 / 20 symbols; futures status regime BULL_STRONG) → the bear entry/exit gate is NOT what's blocking now.
- **Stock**: market-ingest feed healthy (20 symbols subscribed, ticks flowing); `system:universe:latest` = 20 real codes; `system:trade_targets:latest` fresh (10:42). YET `services.trading.strategy_manager` logs **"Signal cycle: 0 signals from [momentum_breakout, williams_r, pattern_pullback, golden_cross]"** every cycle. `daily_indicator_scanner` built **pattern_pullback watchlist = 0**.
- **Futures**: trader-futures running; `setup_eval` shows Setup A `outside_time_window(103m∉[10,60])` (post-window at 10:42), Setup C `no_event_in_window`. In-window (09:10–10:00) evals + multi-week base-rate unknown. Futures minute data now clean (#516); Setup A on clean data backtested +4.99 Sharpe.

**Reframed problem:** stock stops at **signal generation** (0 signals despite bull + populated universe + live feed); futures stops at **setup trigger / selectivity**. Two structurally different failures → two tracks.

## Core principle
For every "no trade," answer: **legitimate (no qualifying setup existed) or broken (a stage dropped a setup that should have passed)?** The whole plan is per-stage observability to make that call with evidence, not guesses.

---

## Track S — Stock: why 0 signals
The single biggest gap: **stock has NO per-signal reject observability** (unlike futures' `setup_eval`). We see "0 signals" but not WHY each symbol×strategy rejected. S2 builds that and is the highest-value step.

- **S1 — Per-strategy daily watchlist population.** Run `daily_indicator_scanner` + inspect `system:daily_watchlist:*` / `system:daily_indicators:latest`. For each of [momentum_breakout, williams_r, pattern_pullback, golden_cross]: how many candidates, and WHICH daily filter zeroed them. (Already saw pattern_pullback=0.) Deliverable: per-strategy candidate count + the zeroing filter.
- **S2 — Entry-condition reject observability (BUILD).** Instrument M4-P (`services/stock_strategy`) to publish per-strategy, per-symbol reject reasons each cycle → Redis `stock:daemon:signal_eval` (mirror futures `trading:futures:setup_eval` + reject-reason pattern from PR #483). Then read: for the 20 universe symbols × 4 strategies, the exact reason (threshold not met / warmth / RVOL / daily-gate / regime). Deliverable: a live "why 0 signals" table.
- **S3 — Indicator warmth.** Confirm the 20 universe symbols (esp. intraday-added) have enough minute bars to compute indicators. Component B prewarm (`candle_warmup`) is dormant — verify symbols aren't silently cold→skip.
- **S4 — Daily-gate vs dynamic mode.** Confirm whether each strategy is daily-gated (needs a non-empty daily watchlist) vs dynamic (universe-driven). If daily-gated and watchlist=0 → that's the block (ties to S1).
- **S5 — Strategy config/threshold audit.** Review enabled flags + entry thresholds (rvol_threshold, rsi_oversold, vr_bottom_threshold, breakout params) in `config/strategies/stock/` against current bull-market conditions — are they tuned for a regime we're not in?

**Track S deliverable:** for each strategy, "blocked at stage X because Y," and the verdict: legitimate (genuinely no entries) vs broken (empty watchlist / cold warmth / mis-tuned threshold).

---

## Track F — Futures: why 0 entries
- **F1 — Base-rate on clean data.** Using the #516-clean store + the existing experiment harness, replay Setup A/C over the last ~6–8 weeks: how many qualifying setups SHOULD have fired? (Repo base-rate ≈ 4.8 setups/month — quantify for the recent window specifically.)
- **F2 — In-window eval reconstruction.** From trader-futures logs, extract the daily 09:10–10:00 Setup A reject reasons for each recent trading day (aligned gap present? magnitude gate? misaligned?) + Setup C event presence. Deliverable: a per-day in-window reject log.
- **F3 — "Would-have-traded" check.** Cross F1/F2: did any recent day present a qualifying aligned gap / tier≤2 event that the LIVE path rejected? If yes → live bug; if no → legitimate selectivity.
- **F4 — Gate/config + clean-data viability.** Audit Setup A/C thresholds (`min_sp500_gap_pct`, `min_kr_gap_pct`, time window, `no_entry_after`) and reconcile with the clean-data finding (Setup A +4.99 Sharpe). Decide if any gate is mis-set vs correctly selective.

**Track F deliverable:** futures 0-entry verdict (legitimate selectivity with the base-rate number, vs a misconfigured/buggy gate), and whether clean data changes the viability picture.

---

## Track C — Shared (feed / regime / session / ledger)
- **C1 — Live feed health** both assets (WS staleness, REST fallback active?).
- **C2 — Regime correctness.** Is BULL_STRONG correct, and does ANY gate still block entries in BULL? (Confirm bear-gate truly inert in bull.)
- **C3 — Session/time gating.** `no_entry_after`, EOD, market-hours — confirm not over-restricting.
- **C4 — Ledger/state integrity.** Dev-ledger fossil (에코프로) now closed; confirm no other `is_open=1` fossils in either ledger, and that EOD/backtest scripts use the **paper** ledger (the orphan recurred because a recovery path read the leftover `development` ledger — pin that writer or remove the dev ledger).

---

## Do we need separate stock & futures experts? — YES (parallel tracks)
The two pipelines are architecturally distinct (decoupled M4 screener/universe/per-strategy-watchlist signal generation vs orchestrator Setup A/C gap/event triggers), have different blockers, and need different domain knowledge. Run them as parallel diagnostic tracks. **No NEW agents need to be created** — the registry already has the right specialists; map them:

| Track | Primary agent(s) | Why |
|---|---|---|
| **Stock (S)** | `strategy-architect` (entry logic) + `data-engineer` (universe/watchlist/feed/warmth) | signal-generation + screener/universe ownership |
| **Futures (F)** | `regime-gate-analyst` (gates/selectivity) + `backtest-engineer` (base-rate replay) + `model-evaluator` (viability) | gate audit + would-have-traded quantification |
| **Shared (C)** | `ops-monitor` / `incident-responder` | live feed/regime/session/state |

Create persistent dedicated `stock-trader` / `futures-trader` agents (via the harness skill) ONLY if you want recurring ownership of these; for this diagnosis the mapped existing agents suffice.

## Sequencing
1. **S2 first** (stock reject observability) — it is the missing instrument that directly answers "what are we missing" for stock; everything else in Track S reads from it.
2. S1/S3/S4/S5 + Track F in parallel (independent).
3. Track C as a backstop (rules out feed/regime/session false-positives).
4. Synthesize: per-asset "exact blocking stage + legitimate-or-broken verdict + recommended fix." Fixes are a SEPARATE follow-up plan, gated on this diagnosis.

## Out of scope
Actually changing strategy thresholds, loosening gates, or enabling Components A/B — those are fixes that follow once the diagnosis pinpoints the real block. This plan only produces the precise diagnosis.
