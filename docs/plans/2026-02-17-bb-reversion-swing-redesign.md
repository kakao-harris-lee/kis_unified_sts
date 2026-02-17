# BB Reversion Swing Redesign

## Problem

BB reversion targets short-term sharp drops and expects mean reversion over 1-5 days (swing). The current implementation treats it as intraday:

1. **Wrong stock source** -- Screener feeds momentum/gainers, but BB reversion needs stocks that dropped sharply (losers).
2. **Wrong exit timing** -- `time_cut_minutes: 60` and `eod_close: 15:15` force intraday liquidation. Swing positions need overnight holding.
3. **Missing quality filter** -- No check that the drop is temporary (healthy fundamentals), not structural.

## Design

### 1. Screener: Add Loser Source

Add KIS ranking API `loser` type to Screener. Publish separately from the existing universe.

**Files:**
- `shared/kis/ranking_client.py` -- add `loser` to `get_all_aggressive_sources()`
- `services/screener.py` -- publish loser data to `system:dip_candidates:latest`

**Redis payload:**
```json
{
  "codes": ["005930", "035720"],
  "scores": {"005930": 0.85, "035720": 0.72},
  "names": {"005930": "Samsung", "035720": "Kakao"},
  "generated_at": "2026-02-19T10:30:00"
}
```

**Selection criteria:**
- KOSPI + KOSDAQ loser top 30 (by drop percentage)
- Re-ranked by trade_value (liquidity filter)
- Only stocks with change_pct <= -2%

### 2. Orchestrator: Dip Candidate Pipeline

**File:** `services/trading/orchestrator.py`

- Add `_load_dip_candidates()` -- reads `system:dip_candidates:latest` from Redis
- Cross-check with `system:llm_quality:latest` -- only pass stocks with LLM score >= threshold (excludes structurally broken stocks)
- Feed dip candidates exclusively to bb_reversion strategy via `context.metadata`
- Other strategies (opening_volume_surge, volume_accumulation) continue using existing universe

### 3. BB Reversion YAML: Swing Parameters

**File:** `config/strategies/stock/bb_reversion.yaml`

Exit changes (three_stage retained, parameters adjusted):

| Parameter | Before (intraday) | After (swing) |
|-----------|--------------------|---------------|
| stop_loss_pct | -1.5% | -3% |
| breakeven_threshold_pct | +1.5% | +2% |
| overshoot_trailing_pct | -1.5% | -2% |
| time_cut_minutes | 60 | 9999 (disabled) |
| eod_close_hour | 15 | 23 (disabled) |
| eod_close_minute | 15 | 59 (disabled) |

Entry: `skip_market_open_minutes: 30` retained. Mean reversion signals during regular hours.

### 4. LLM Quality Gate

Orchestrator filters dip candidates against LLM quality scores:
- Stocks in `system:llm_quality:latest` with score >= `min_recommendation_score` (5.0) pass
- Stocks on LLM blacklist (`block_negative`) are excluded
- Stocks not in LLM data pass by default (no LLM data != bad stock)

## Unchanged

- `opening_volume_surge` -- intraday, uses existing universe, EOD 15:15
- `volume_accumulation` -- swing, uses accumulation_candidates, momentum_decay exit
- Global position limit: 10 (PositionTracker)
- Screener existing universe output (`system:universe:latest`)

## Implementation Order

1. `ranking_client.py` -- add loser source
2. `screener.py` -- publish dip_candidates
3. `orchestrator.py` -- load dip candidates + LLM filter + feed to bb_reversion
4. `bb_reversion.yaml` -- swing parameters
5. Test: verify dip_candidates published, bb_reversion receives them, overnight holding works
