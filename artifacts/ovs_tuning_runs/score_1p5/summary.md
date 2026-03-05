# Opening Volume Surge Candidate Validation

## Dataset
- Rows: 281,900
- Symbols: 33
- Range: 2026-01-20 09:00:00 ~ 2026-02-27 15:32:00

## Distortion Filters
- Time window: 545~920 (minute-of-day)
- min_vol_ma20: 1000.0
- min_value_ma20: 100000000.0
- min_slot_vol_ma5: 1000.0
- min_slot_value_ma5: 100000000.0
- min_vol_ratio_20: 3.0
- min_vol_ratio_slot: 3.0
- spike_hit_ratio: 2.0
- min_spike_hits_5m: 3
- min_ret_1m_pct: 0.0
- min_range_pos: 0.6
- max_upper_shadow_ratio: 0.4
- min_body_ratio: 0.15
- min_score: 1.5

## Candidate Counts
- All filtered candidates: 93
- Realtime top-per-minute candidates: 93
- First-entry points (code x day): 62

## Entry Forward Return (First-entry)
- 5m: mean=0.108% median=0.000% win_rate=48.4% n=62
- 15m: mean=0.201% median=0.000% win_rate=49.2% n=61
- 30m: mean=0.372% median=-0.059% win_rate=45.8% n=59

## Entry Hour Distribution
- 09:00 -> 10
- 10:00 -> 15
- 11:00 -> 7
- 12:00 -> 9
- 13:00 -> 12
- 14:00 -> 8
- 15:00 -> 1

## Top Symbols by Entry Count
- 086520: 7
- 005380: 6
- 006400: 6
- 000660: 5
- 035420: 5
- 005490: 4
- 003670: 3
- 000270: 3
- 051910: 3
- 066570: 3
- 035720: 3
- 068270: 3
- 196170: 2
- 055550: 2
- 247540: 2

