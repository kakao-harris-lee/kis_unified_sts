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
- min_spike_hits_5m: 4
- min_ret_1m_pct: 0.1
- min_range_pos: 0.7
- max_upper_shadow_ratio: 0.3
- min_body_ratio: 0.2
- min_score: 1.8

## Candidate Counts
- All filtered candidates: 17
- Realtime top-per-minute candidates: 17
- First-entry points (code x day): 12

## Entry Forward Return (First-entry)
- 5m: mean=0.452% median=0.343% win_rate=50.0% n=12
- 15m: mean=0.740% median=0.968% win_rate=66.7% n=12
- 30m: mean=1.246% median=0.754% win_rate=66.7% n=12

## Entry Hour Distribution
- 09:00 -> 2
- 10:00 -> 3
- 11:00 -> 2
- 13:00 -> 4
- 14:00 -> 1

## Top Symbols by Entry Count
- 005380: 4
- 000660: 2
- 086520: 2
- 005490: 1
- 006400: 1
- 035420: 1
- 066570: 1

