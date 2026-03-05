# Opening Volume Surge Candidate Validation

## Dataset
- Rows: 281,900
- Symbols: 33
- Range: 2026-01-20 09:00:00 ~ 2026-02-27 15:32:00

## Distortion Filters
- Time window: 545~870 (minute-of-day)
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
- min_score: -999.0

## Candidate Counts
- All filtered candidates: 121
- Realtime top-per-minute candidates: 121
- First-entry points (code x day): 77

## Entry Forward Return (First-entry)
- 5m: mean=0.116% median=0.000% win_rate=48.1% n=77
- 15m: mean=0.061% median=-0.087% win_rate=40.3% n=77
- 30m: mean=0.152% median=-0.156% win_rate=41.6% n=77

## Entry Hour Distribution
- 09:00 -> 14
- 10:00 -> 22
- 11:00 -> 12
- 12:00 -> 12
- 13:00 -> 12
- 14:00 -> 5

## Top Symbols by Entry Count
- 000660: 8
- 086520: 7
- 035720: 7
- 005380: 6
- 035420: 6
- 055550: 5
- 066570: 5
- 003670: 5
- 006400: 5
- 005490: 4
- 000270: 3
- 196170: 3
- 009150: 3
- 068270: 2
- 051910: 2

