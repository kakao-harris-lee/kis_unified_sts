# Market Structure Policy

Last updated: 2026-06-28 KST.

## Scope

This runbook records operator policy for stock venue routing, KOSPI 200 futures
product/session handling, and what must be true before changing runtime windows.

## Current Policy

| Area | Policy | Runtime Setting |
|---|---|---|
| Stock venue | KRX-only until operator approves ATS/SOR readiness | `ats_routing.enabled=false`; `stock_order_router` remains KRX-only |
| Stock extended hours | No automated extended-hours trading until ATS feed/routing evidence exists | `market_schedule.stock.extended` is non-authoritative for automation |
| Futures regular session | **IMPLEMENTED 2026-06-28** — regular open moved to 08:45 KST (day-only; night stays disabled) | `market_schedule.futures.regular.open` now `08:45` |
| Futures night session | Disabled fail-closed | `market_schedule.futures.night.enabled=false` |
| Futures product | Product must be explicit in env and evidence reports before promotion | `FUTURES_TRADING_PRODUCT`, `FUTURES_STRATEGY_SYMBOL`, `FUTURES_SLIPPAGE_TICK_SIZE` |

## Change Gates

### Stock ATS/SOR Gate

Before enabling `ats_routing.enabled=true`, all of these must be present:

- KRX and ATS quote ingestion for the same symbol and timestamp window.
- Routing decision audit persisted with venue, price improvement, spread, depth,
  fill estimate, and reason.
- Paper simulator calibrated for ATS fill rate and price improvement.
- Workbench venue evidence panel.
- Integration test proving KRX fallback when ATS quote is missing.

### Futures 08:45 Regular Session Gate — IMPLEMENTED 2026-06-28

`market_schedule.futures.regular.open` changed from `09:00` to `08:45` (PR feat/futures-0845-open).

**What was changed**

- `config/market_schedule.yaml`: `futures.regular.open: "08:45"`
- `shared/decision/context.py`: `market_open_hour/market_open_minute` fields added to `MarketContext` (defaults 8/45); `market_open_time()` / `minutes_since_open()` are now anchor-configurable.
- `shared/decision/context.py`: `build_market_context()` reads the open from config; module-level cache avoids per-tick I/O.
- `services/trading/orchestrator.py`: `MarketSchedule.futures_open` default updated to 08:45; `MarketSchedule.load_from_yaml()` added; `TradingConfig.futures()` now calls it.

**Per-setup window decisions (open-relative windows auto-shift; close-relative cutoffs re-valued)**

| Setup | Parameter | Old value | New value | Resulting clock time | Rationale |
|-------|-----------|-----------|-----------|----------------------|-----------|
| Setup A | `valid_minutes_min` | 10 | 10 | 08:55 KST | open-relative — auto-shifts |
| Setup A | `valid_minutes_max` | 90 | 90 | 10:15 KST | open-relative — auto-shifts |
| Setup C | `no_entry_after_minutes_since_open` | 360 | 375 | 15:00 KST | close-relative — re-valued to preserve 15:00 KST |
| Setup D | `valid_minutes_min` | 15 | 15 | 09:00 KST | open-relative — auto-shifts (skips open auction) |
| Setup D | `no_entry_after_minutes_since_open` | 345 | 360 | 14:45 KST | close-relative — re-valued to preserve 14:45 KST |

**Slippage**

- `blocked_time_windows` early-open block: `09:00–09:05 → 08:45–08:50`
- `time_of_day_multipliers` early-session key: `"09:00-09:15" → "08:45-09:15"`
- `ats_routing.time_of_day_preferences["09:00-09:30"]` (dormant ATS block): left unchanged (out-of-scope dormant routing)

**Backtest parity — historical data anchor**

`MarketContextReplay` now stamps `market_open_hour`/`market_open_minute` onto every
replayed `MarketContext`, defaulting to 08:45 (current production). **Historical
backtests on pre-08:45 data (the futures day session opened at 09:00 before
2026-06-28) MUST pass `market_open_hour=9, market_open_minute=0`** — otherwise every
setup's open-relative window is shifted 15 min earlier and the replay no longer
matches the regime that produced the historical research numbers. In particular,
**Setup D OOS Sharpe 1.77 and the Setup A profitability numbers were computed at the
09:00 anchor and require re-validation under the 08:45 anchor** before any
08:45-conditioned conclusions are drawn.

**Paper observation**

09:00-only vs 08:45-inclusive behavior will accumulate in paper trading evidence as sessions run with the new anchor.

**To roll back**: revert `market_schedule.yaml::futures.regular.open` to `"09:00"` and revert the per-setup parameter values above. The code path is config-driven so no code change is needed for rollback.

### Futures Night Session Gate

Before enabling night trading:

- Separate feed and order API behavior must be verified.
- Night order validity and quote limits must be reflected in risk/order guards.
- Kill-switch, position recovery, and settlement assumptions must be tested.
- Operator approval must explicitly name the allowed products and max exposure.
