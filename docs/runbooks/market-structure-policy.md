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
| Futures regular session | Current runtime keeps conservative configured session until 08:45 policy is implemented and tested | `market_schedule.futures.regular.open` currently `09:00` |
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

### Futures 08:45 Regular Session Gate

Before changing `market_schedule.futures.regular.open` from `09:00` to `08:45`:

- Strategy entry windows must be reviewed for Setup A/C/D.
- Slippage blocked windows must be reviewed for 08:45-09:00.
- Backtest/session filters must state whether 08:45-09:00 is included.
- Paper evidence must compare 09:00-only vs 08:45-inclusive behavior.

### Futures Night Session Gate

Before enabling night trading:

- Separate feed and order API behavior must be verified.
- Night order validity and quote limits must be reflected in risk/order guards.
- Kill-switch, position recovery, and settlement assumptions must be tested.
- Operator approval must explicitly name the allowed products and max exposure.
