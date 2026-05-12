# Stock Paper Trading — Zero Signals Regression (2026-05-06 onwards)

**Status**: Diagnosis in progress, root cause not yet pinned.
**First observed**: 2026-05-06 (first session after 5/5 holiday).
**Last good day**: 2026-05-04 — 581 entry signals, 24 fills, 25 closed trades persisted to `market.stock_trades`.
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

## Confirmed: NOT the cause

1. **Code changes**: `git log --since='2026-05-04' --until='2026-05-08'` shows zero commits to `services/trading/strategy_manager.py`, `services/trading/indicator_engine.py`, `services/trading/orchestrator.py`, or any stock strategy file. All commits in that window are Phase 0/1/2 LLM-primary cutover work touching futures-side code and infra (PR #163–#195).
2. **Universe selection**: 5/4 and 5/6 both reach 40 symbols within 2 min of startup. Universe churn patterns nearly identical.
3. **Pre-warming**: 5/4 had 96 pre-warm events; 5/6 had 127 (more, actually). 5/12 had 125. Indicators ARE getting seeded.
4. **WebSocket ticks**: 5/4 final `tick_count=1,185,653`; 5/12 final `tick_count=1,286,666`. Tick flow normal.
5. **Strategy YAML**: `git log --since='2026-05-04' -- config/strategies/stock/*.yaml` — no changes.
6. **Cooldown state**: All strategy `_last_signal_time` dicts are in-memory only — no Redis persistence — so day-to-day carryover impossible.
7. **LLM regime**: 5/4 and 5/12 both saw extensive BULL_STRONG cycles (224 vs 158). Regime gating blocked some cycles on both days; plenty of unblocked cycles available.
8. **Indicator staleness ratio**: 5/4 had 85,211 stale warnings; 5/12 had 85,379 — same order of magnitude.

## Suspicious observations (not yet root cause)

1. **5/4 vs 5/12 `cached_symbols` difference**: At various data-source-unhealthy events, 5/4 logged `cached_symbols=[]` (empty) but still produced signals at other moments; 5/12 logged `cached_symbols=[19 fresh symbols]` but produced zero signals. The 5/4 working sessions had fresh ticks during signal generation; 5/12 may have fresh ticks only at moments when strategy_manager isn't running, or vice versa.
2. **More entry-blocked logs on 5/12 (5,386) vs 5/4 (1,791)**: Could indicate the LLM regime classifier is BEAR-leaning more often, but BULL_STRONG counts are still significant on 5/12 (158 occurrences).
3. **Strategy "Signal cycle: 0 signals" introduced by commit 0a5d019** (2026-03-10 throttled summary log) — does NOT affect signal generation, just logs.

## Likely hypothesis branches (in priority order)

### H1 — Indicator data semantic regression

`indicator_engine.get_indicators()` returns `{}` when `last_tick_ts` staleness > 180s (per `_staleness_seconds`). On 5/4 this guard worked but tick-fresh moments produced signals; on 5/12 the staleness check may always fire because:

- `last_tick_ts` may be set incorrectly (e.g., minute-aligned epoch vs callback receive time)
- WebSocket → data_provider → indicator_engine relay may drop ticks silently if a midstream component changed expectations

**Reproduce**: Add INFO-level logging at `indicator_engine.on_tick` entry to count tick rates per symbol; cross-reference with `get_indicators` stale-rejections per symbol per cycle. Compare 5/4 raw log vs 5/12.

### H2 — `is_warm` check failing for all symbols

`orchestrator.check_symbol` early-returns if `not self._indicator_engine.is_warm(symbol)`. `is_warm` requires ≥ `bb_period` (20) candles. Pre-warm seeds 120 candles for major symbols — fine. But minor symbols only get 26 candles seeded. If the new universe leans heavy on minor symbols since 5/6, `is_warm` may fail more.

**Reproduce**: Log `is_warm` results per symbol once at startup; compare 5/4 vs 5/12. Also count symbols that pass `is_warm` per cycle.

### H3 — LLM context publisher injection mismatch

`strategy_manager.check_entries` fetches `LLM market_context` and injects into `EntryContext.market_context`. The momentum_breakout strategy uses this for sizing/regime checks. If `risk_mode=RISK_OFF` (which 5/12 09:00 logged) gates strategies invisibly, all entries get filtered.

**Reproduce**: Search for `risk_mode` / `risk_score` usage in stock strategy entry classes. Check if `RISK_OFF` blocks entry. Verify 5/4 had `RISK_ON` throughout (`risk_mode=RISK_ON, confidence=0.90` per log).

**Key finding**: 5/4 09:00 LLM was `risk_mode=RISK_ON`. 5/12 09:00 was `risk_mode=RISK_OFF`. Later 5/12 became `NEUTRAL` then `RISK_ON` again. Yet 0 signals all day.

### H4 — Stock universe symbol composition drift

A combination of `screener.sh` + LLM `dip_candidates` chooses symbols. If post-5/5 the screener picks symbols with characteristically lower volatility or volume, all 4 momentum/pullback strategies may consistently miss their thresholds. The momentum_breakout `rvol_threshold=1.6` (or 1.0 in trend mode) wouldn't trigger if volume profile is flat.

**Reproduce**: Pull current 40-symbol universe → run momentum_breakout strategy against historical 1min OHLCV for those symbols offline → see if any would have fired. Compare to 5/4 universe.

## Recommended next steps

1. **Enable DEBUG logging** for `shared.strategy.entry.momentum_breakout` and `services.trading.indicator_engine` for one trading session to surface the rejection reason at evaluation time (e.g., "Cooldown active", "Invalid ATR", "No breakout — close=X, threshold=Y", "rvol=Z < required=W").
2. **Add a per-cycle counter** to `strategy_manager.check_entries` reporting (a) cycles attempted, (b) symbols where indicators returned, (c) symbols where strategy returned None vs Signal — so silent-failure mode becomes visible without DEBUG logs.
3. **Bisect with offline backtest**: take 2026-05-12 1min OHLCV → run momentum_breakout against it → if it produces signals, the bug is in live data plumbing; if not, the bug is in strategy params or LLM context interaction.
4. **Side-by-side log comparison**: take 5/4 09:10:48 (1 second before first signal fired for 006340) and 5/12 09:10:48 — diff the orchestrator state, indicator readiness, LLM context.

## Out of scope for this issue

- Fix dashboard `/api/trades/rl?asset_class=stock` routing — done in PR #232 (deployed 2026-05-12).
- Re-architect orchestrator to run both stock + futures in one container — out of redesign scope.
- Investigate futures-side parallel issue — futures continues firing signals (614 RL trades) so isolated regression.

## Operator impact

Stock paper trading log volume is normal (15MB/day) so silent — only visible via the absence in `market.stock_trades`. Recommend adding a daily verification gate:
- "stock signals today >= 1" (or operator-acceptable threshold) → FAIL → Telegram alert
- Equivalent to existing `setup_a_signals_today` Phase 2 gate but for stock.

## References

- Last good day log: `logs/stock_trading_20260504.log` (15MB)
- First bad day log: `logs/stock_trading_20260506.log`
- Dashboard fix (separate): PR #232 — `fix(dashboard): route stock vs futures trades to different DB.table`
- Related: PR #218 (data_provider silent-stall guard) — applied 2026-05-11, did NOT address this issue
- Phase 2 cutover plan: `docs/plans/2026-05-03-llm-primary-rl-minimization.md`
