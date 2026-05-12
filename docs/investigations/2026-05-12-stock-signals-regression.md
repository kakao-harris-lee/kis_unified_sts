# Stock Paper Trading — Zero Signals Regression (2026-05-06 onwards)

**Status**: Diagnosis in progress, root cause not yet pinned.
**First observed**: 2026-05-06 (first session after 5/5 holiday).
**Last good day**: 2026-05-04 — 547 entry signals, 24 fills, 25 closed trades persisted to `market.stock_trades`.
**Severity**: P1 — stock paper trading running but no signal generation; 8+ days of zero data.

---

## Observed Behavior

Per `logs/stock_trading_YYYYMMDD.log`:

| Date | Cron | Cycles | Entry signals | Fills | Trades persisted |
|------|------|--------|---------------|-------|------------------|
| 2026-05-04 | ✅ | 360 cycles | **547** | 24 | 25 |
| 2026-05-05 | Holiday (140 byte log, skipped) | — | — | — | — |
| 2026-05-06 | ✅ | 338 cycles | **0** | 0 | 0 |
| 2026-05-07 | ✅ | 295 cycles | 0 | 0 | 0 |
| 2026-05-08 | ✅ | 364 cycles | 0 | 0 | 0 |
| 2026-05-11 | ✅ | 346 cycles | 0 | 0 | 0 |
| 2026-05-12 | ✅ | 300 cycles | 0 | 0 | 0 |

All 4 stock strategies — `momentum_breakout`, `daily_pullback`, `vr_composite`, `trend_pullback` — produce zero signals every cycle since 5/6.

## Timeline reconstruction (revised after review)

The original write-up claimed "zero commits to trading code in 5/4 → 5/8". That was wrong on two counts:

1. **PR #159 (`fix(paper): tz-aware UTC across entry hot-path`)** merged on **2026-05-04 10:49 KST** (commit `c37214f`). The 5/4 cron started at 08:55 KST under **pre-#159** code and produced 547 signals. The 5/5 cron skipped (holiday). The 5/6 cron started 08:55 KST under **post-#159** code and produced 0 signals. **This is an exact cause-effect timeline.** PR #159's branch name even maps onto this PR's branch (`fix/stock-signals-tz-aware-regression`).
2. **`services/trading/orchestrator.py` was modified ~6 times** between 5/4 and 5/8 (PR #162, #166, #170, #171, #173, #186). `services/trading/position_tracker.py` was modified once (PR #174). EntryRegistry gained two entries (Setup A, Setup C in PR #165). The stock orchestrator shares all of this code path with futures.

PR #232's body — already merged — explicitly fingered PR #159 as the suspect ("PR #159 tz-aware UTC change may have broken stock-side indicator freshness. Out of scope for this PR; needs separate dig.").

## Confirmed: NOT the cause

1. **Universe selection**: 5/4 and 5/6 both reach 40 symbols within 2 min of startup. Universe churn patterns nearly identical.
2. **Pre-warming volume**: 5/4 had 96 pre-warm events; 5/6 had 127 (more, actually). 5/12 had 125. Indicators ARE getting seeded.
3. **WebSocket ticks**: 5/4 final `tick_count=1,185,653`; 5/12 final `tick_count=1,286,666`. Tick flow normal.
4. **Strategy YAML**: `git log --since='2026-05-01' -- config/strategies/stock/*.yaml` — no changes since well before regression.
5. **Cooldown state**: All stock strategy `_last_signal_time` dicts are in-memory only (verified by grep in `shared/strategy/entry/`) — no Redis persistence — so day-to-day carryover impossible.
6. **LLM regime distribution**: 5/4 and 5/12 both saw extensive BULL_STRONG cycles (224 vs 158). Regime gating blocked some cycles on both days; plenty of unblocked cycles available.
7. **Indicator staleness ratio**: 5/4 had 85,211 stale warnings; 5/12 had 85,379 — same order of magnitude.

## Suspicious observations (not yet root cause)

1. **5/4 vs 5/12 `cached_symbols` difference**: At various data-source-unhealthy events, 5/4 logged `cached_symbols=[]` (empty) but still produced signals at other moments; 5/12 logged `cached_symbols=[19 fresh symbols]` but produced zero signals. The 5/4 working sessions had fresh ticks during signal generation; 5/12 may have fresh ticks only at moments when strategy_manager isn't running, or vice versa.
2. **More entry-blocked logs on 5/12 (5,386) vs 5/4 (1,791)**: Could indicate the LLM regime classifier is BEAR-leaning more often, but BULL_STRONG counts are still significant on 5/12 (158 occurrences).
3. **Strategy "Signal cycle: 0 signals" log was introduced by commit `0a5d019`** (2026-03-10 throttled summary log) — does NOT affect signal generation, just logs. Pre-dates the regression by 2 months.

## Hypothesis branches (in priority order)

### H0 (top priority) — PR #159 tz-aware UTC contract broke stock indicator freshness

PR #159 (commit `c37214f`, merged 2026-05-04 10:49 KST) rewrote the WebSocket-tick → indicator-engine → strategy-manager timestamp contract:

- `shared/kis/stock_feed.py:540` callback ts built as `datetime.fromtimestamp(epoch, UTC)` (tz-aware)
- `services/trading/indicator_engine.py::on_tick` defaults to `datetime.now(UTC)` (tz-aware)
- `get_indicators` staleness guard now normalizes both `last_tick_ts` and `now` to UTC tz-aware
- `services/trading/strategy_manager.py::_dedupe_signals` uses `datetime.now(UTC)`
- `services/trading/data_provider.py::MarketDataCache.is_stale` tz-aware-safe
- `services/trading/pipeline.py::with_retry` emits `exc_info=True` so the next tz/typing regression is diagnosable

Validation in PR #159 watched `kospi.rl_trades` (futures) only — `market.stock_trades` was not in the success criteria, so a stock-side regression on the same contract would land silently. The 5/4 (pre-#159) → 5/6 (post-#159) timeline matches the symptom exactly.

**Reproduce**:
- `git show c37214f -- services/trading/indicator_engine.py services/trading/data_provider.py services/trading/strategy_manager.py shared/kis/stock_feed.py` and diff each surface for stock-path coverage; in particular look for the staleness guard's `now or datetime.now(UTC)` branch and whether `last_tick_ts` from the stock WS callback is reliably tz-aware in the live path.
- Add a single INFO log at the `if age > self._staleness_seconds:` branch in `get_indicators` recording `last_ts.tzinfo` value; if it's `None` in production, the normalization path is masking the bug rather than fixing it.

### H1 — `is_warm` check failing for all symbols

`check_symbol` in `services/trading/orchestrator.py` early-returns if `not self._indicator_engine.is_warm(symbol)`. `is_warm` requires `≥ bb_period` (20) candles. `_prewarm_symbols` calls `_fetch_candles_from_clickhouse(symbol, limit=120)` and `get_minute_bars(symbol, count=120)` — **uniform 120-candle seed**, no major/minor distinction. (Earlier write-up claimed a 120/26 split — that was wrong; the 26 figure came from MACD slow-EMA, unrelated.)

So `is_warm` should be true for all pre-warmed symbols. If H0 turns out wrong, the next thing to verify is whether on-tick is actually appending candles since 5/6 (regardless of pre-warm). A symbol that pre-warmed 120 but received no on-tick updates would still be `is_warm=True` until the candle accumulator decays.

**Reproduce**: At startup, log `is_warm()` results for each universe symbol; then every 60s log how many `acc.candles` each accumulator has. Compare distribution 5/4 vs 5/12.

### H2 — LLM context publisher injection mismatch (low confidence)

`strategy_manager.check_entries` fetches LLM `market_context` and injects into `EntryContext.market_context`. Initial write-up speculated `risk_mode=RISK_OFF` invisibly gates strategies.

**Verified WRONG for the 4 stock strategies in question**: `grep -rn "risk_mode\|market_context" shared/strategy/entry/{momentum_breakout,daily_pullback,vr_composite,trend_pullback}.py` returns no matches. `risk_mode` gating exists only in `shared/strategy/entry/setup_adapters.py` (Phase 5 futures paradigm) and `shared/strategy/entry/rl_mppo.py` (futures RL) — neither is in the stock signal path. **This hypothesis is effectively ruled out** unless the gating happens at a layer above the strategy class (e.g., `strategy_manager._filter_signals` reads risk_mode). Quick verification: `grep -n "risk_mode\|risk_score" services/trading/strategy_manager.py shared/strategy/filters.py`.

### H3 — Stock universe symbol composition drift

A combination of `screener.sh` + LLM `dip_candidates` chooses symbols. If post-5/5 the screener picks symbols with characteristically lower volatility or volume, all 4 momentum/pullback strategies may consistently miss their thresholds. The `momentum_breakout` `rvol_threshold=1.6` (or `1.0` in trend mode per `config/strategies/stock/momentum_breakout.yaml`) wouldn't trigger if the volume profile is flat.

**Reproduce**: Pull current 40-symbol universe → run momentum_breakout strategy against historical 1min OHLCV for those symbols offline → see if any would have fired. Compare to 5/4 universe.

Weight: low. Universe coverage spans 40 symbols and BULL_STRONG sessions are common. A four-day-running zero-signal pattern across all four strategies (not just momentum_breakout) is hard to explain by universe drift alone.

## Recommended next steps

1. **Audit PR #159 changes for stock-path coverage** (`git show c37214f`). Specifically the `indicator_engine.get_indicators` staleness guard's tz-normalization branch — does it short-circuit to `return {}` if `last_tick_ts` is `None` rather than zero, and does the stock on-tick path ever leave it `None`?
2. **Enable DEBUG logging** for `shared.strategy.entry.momentum_breakout` and `services.trading.indicator_engine` for one trading session to surface the rejection reason at evaluation time (e.g., "Cooldown active", "Invalid ATR", "No breakout — close=X, threshold=Y", "rvol=Z < required=W"). PR #159 also wired `exc_info=True` into `with_retry`; if any silent exception is being swallowed in the stock path, it should surface here.
3. **Add a per-cycle counter** to `strategy_manager.check_entries` reporting (a) cycles attempted, (b) symbols where indicators returned, (c) symbols where strategy returned None vs Signal — so silent-failure mode becomes visible without DEBUG logs.
4. **Bisect with offline backtest**: take 2026-05-12 1min OHLCV → run momentum_breakout against it → if it produces signals, the bug is in live data plumbing (favors H0); if not, the bug is in strategy params or universe (favors H3).
5. **Side-by-side log comparison**: take 5/4 09:10:48 (1 second before first signal fired for 006340) and 5/12 09:10:48 — diff the orchestrator state, indicator readiness, LLM context.

## Out of scope for this issue

- Fix dashboard `/api/trades/rl?asset_class=stock` routing — done in PR #232 (deployed 2026-05-12).
- Re-architect orchestrator to run both stock + futures in one container — out of redesign scope.
- Investigate futures-side parallel issue — futures continues firing signals (614 RL trades) so isolated regression to the stock path.

## Operator impact

Stock paper trading log volume is normal (15MB/day) so silent — only visible via the absence in `market.stock_trades`. Recommend adding a daily verification gate:
- "stock signals today >= 1" (or operator-acceptable threshold) → FAIL → Telegram alert
- Equivalent to existing `setup_a_signals_today` Phase 2 gate but for stock.

## References

- Last good day log: `logs/stock_trading_20260504.log` (15MB)
- First bad day log: `logs/stock_trading_20260506.log`
- **PR #159 (suspect)**: `fix(paper): tz-aware UTC across entry hot-path; restore signal-to-fill flow` — commit `c37214f`, merged 2026-05-04 10:49 KST. Validation in body was futures-only.
- Dashboard fix (separate): PR #232 — `fix(dashboard): route stock vs futures trades to different DB.table`
- Related: PR #218 (`fix(data-provider): silent-stall guard via fresh-symbol ratio threshold`) — applied 2026-05-11. Doesn't directly fix this regression but its existence is **corroborating evidence for H0**: a stock-side silent-stall on 2026-05-11 had the same fingerprint (data fresh ratio collapse → strategy receives no usable data → 0 signals). The post-#218 `min_fresh_ratio=0.5` default should now fail health checks if the stock path hits a similar mode again.
- Phase 2 cutover plan: `docs/plans/2026-05-03-llm-primary-rl-minimization.md`
