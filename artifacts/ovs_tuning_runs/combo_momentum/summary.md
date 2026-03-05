# Opening Volume Surge Candidate Validation

## Dataset
- Rows: 281,900
- Symbols: 33
- Range: 2026-01-20 09:00:00 ~ 2026-02-27 15:32:00

## Distortion Filters
- Time window: 545~900 (minute-of-day)
- min_vol_ma20: 1000.0
- min_value_ma20: 100000000.0
- min_slot_vol_ma5: 1000.0
- min_slot_value_ma5: 100000000.0
- min_vol_ratio_20: 3.0
- min_vol_ratio_slot: 3.0
- spike_hit_ratio: 2.0
- min_spike_hits_5m: 3
- min_ret_1m_pct: 0.2
- min_range_pos: 0.7
- max_upper_shadow_ratio: 0.4
- min_body_ratio: 0.15
- min_score: 2.0

## Candidate Counts
- All filtered candidates: 25
- Realtime top-per-minute candidates: 25
- First-entry points (code x day): 18

## Entry Forward Return (First-entry)
- 5m: mean=0.247% median=0.059% win_rate=50.0% n=18
- 15m: mean=0.362% median=0.015% win_rate=50.0% n=18
- 30m: mean=0.818% median=0.350% win_rate=55.6% n=18

## Entry Hour Distribution
- 09:00 -> 2
- 10:00 -> 4
- 11:00 -> 2
- 12:00 -> 2
- 13:00 -> 7
- 14:00 -> 1

## Top Symbols by Entry Count
- 086520: 3
- 006400: 3
- 066570: 2
- 000660: 2
- 005490: 2
- 005380: 2
- 000270: 1
- 003670: 1
- 035420: 1
- 196170: 1

