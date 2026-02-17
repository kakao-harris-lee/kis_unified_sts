# Volume Accumulation Data Pipeline Fix

**Date**: 2026-02-17
**Status**: Approved

## Problem

The `volume_accumulation` strategy requires 5 indicators (`vwap`, `rvol`, `volume_velocity`, `volume_acceleration`, `high_5`) that `StreamingIndicatorEngine` does not compute. The strategy is effectively dead code — entry signals never fire because all data-dependent conditions return `None`.

Additionally:
- `MomentumDecayExit` triggers EOD close at 15:15 for swing positions, violating the "no EOD forced liquidation" principle.
- `AccumulationScanner` is implemented but not registered in cron, so Redis `system:accumulation:latest` is always empty.

## Design Decisions

1. **Extend `StreamingIndicatorEngine`** with volume indicators (VWAP, RVOL, velocity/acceleration, high_N). Reuse existing calculators from `shared/indicators/volume.py`.
2. **Add `eod_close_enabled` config flag** to `MomentumDecayExit`. Set `false` in `volume_accumulation.yaml`.
3. **Register accumulation scanner** as nightly cron (21:30, after LLM nightly analysis).

## Files Changed

| File | Change |
|------|--------|
| `services/trading/indicator_engine.py` | Add VWAP, RVOL, volume_velocity/acceleration, high_N to get_indicators() |
| `shared/strategy/exit/momentum_decay.py` | Add `eod_close_enabled` config field + guard |
| `config/strategies/stock/volume_accumulation.yaml` | Set `eod_close_enabled: false` |
| `scripts/cron/accumulation_scanner.sh` | New: nightly cron script |
| `tests/` | Unit tests for indicator engine extensions |

## Implementation Order

1. IndicatorEngine extension (core change)
2. MomentumDecayExit EOD guard (small, independent)
3. Accumulation Scanner cron (infra)
4. Tests + verification
