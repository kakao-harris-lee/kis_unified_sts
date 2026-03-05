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
- min_score: 1.8

## Candidate Counts
- All filtered candidates: 43
- Realtime top-per-minute candidates: 43
- First-entry points (code x day): 31

## Entry Forward Return (First-entry)
- 5m: mean=0.246% median=0.000% win_rate=48.4% n=31
- 15m: mean=0.410% median=0.107% win_rate=54.8% n=31
- 30m: mean=0.755% median=0.100% win_rate=51.6% n=31

## Entry Hour Distribution
- 09:00 -> 3
- 10:00 -> 7
- 11:00 -> 5
- 12:00 -> 4
- 13:00 -> 8
- 14:00 -> 4

## Top Symbols by Entry Count
- 005490: 4
- 005380: 4
- 006400: 4
- 000660: 3
- 086520: 3
- 000270: 2
- 068270: 2
- 051910: 2
- 066570: 2
- 003670: 1
- 055550: 1
- 035420: 1
- 196170: 1
- 247540: 1

