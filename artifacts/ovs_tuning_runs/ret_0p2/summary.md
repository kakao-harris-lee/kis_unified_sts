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
- min_ret_1m_pct: 0.2
- min_range_pos: 0.6
- max_upper_shadow_ratio: 0.4
- min_body_ratio: 0.15
- min_score: -999.0

## Candidate Counts
- All filtered candidates: 115
- Realtime top-per-minute candidates: 115
- First-entry points (code x day): 76

## Entry Forward Return (First-entry)
- 5m: mean=0.084% median=0.109% win_rate=50.7% n=75
- 15m: mean=0.121% median=0.000% win_rate=45.2% n=73
- 30m: mean=0.227% median=0.000% win_rate=47.8% n=69

## Entry Hour Distribution
- 09:00 -> 13
- 10:00 -> 21
- 11:00 -> 9
- 12:00 -> 7
- 13:00 -> 11
- 14:00 -> 12
- 15:00 -> 3

## Top Symbols by Entry Count
- 086520: 8
- 000660: 7
- 006400: 7
- 005380: 6
- 003670: 5
- 035720: 5
- 066570: 4
- 196170: 4
- 005490: 4
- 035420: 4
- 247540: 3
- 068270: 3
- 051910: 3
- 009150: 3
- 055550: 2

