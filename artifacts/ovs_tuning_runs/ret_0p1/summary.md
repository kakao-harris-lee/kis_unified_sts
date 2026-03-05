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
- min_ret_1m_pct: 0.1
- min_range_pos: 0.6
- max_upper_shadow_ratio: 0.4
- min_body_ratio: 0.15
- min_score: -999.0

## Candidate Counts
- All filtered candidates: 137
- Realtime top-per-minute candidates: 137
- First-entry points (code x day): 90

## Entry Forward Return (First-entry)
- 5m: mean=0.075% median=0.000% win_rate=46.6% n=88
- 15m: mean=0.102% median=0.000% win_rate=44.2% n=86
- 30m: mean=0.201% median=-0.059% win_rate=44.4% n=81

## Entry Hour Distribution
- 09:00 -> 14
- 10:00 -> 22
- 11:00 -> 11
- 12:00 -> 12
- 13:00 -> 12
- 14:00 -> 14
- 15:00 -> 5

## Top Symbols by Entry Count
- 000660: 8
- 086520: 8
- 035720: 7
- 006400: 7
- 005380: 6
- 035420: 6
- 055550: 5
- 003670: 5
- 066570: 5
- 005490: 4
- 196170: 4
- 068270: 3
- 051910: 3
- 009150: 3
- 000270: 3

