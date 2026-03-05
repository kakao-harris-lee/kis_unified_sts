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
- min_spike_hits_5m: 4
- min_ret_1m_pct: 0.1
- min_range_pos: 0.65
- max_upper_shadow_ratio: 0.4
- min_body_ratio: 0.15
- min_score: 1.5

## Candidate Counts
- All filtered candidates: 41
- Realtime top-per-minute candidates: 41
- First-entry points (code x day): 28

## Entry Forward Return (First-entry)
- 5m: mean=0.207% median=-0.031% win_rate=46.4% n=28
- 15m: mean=0.360% median=0.059% win_rate=50.0% n=28
- 30m: mean=0.637% median=0.058% win_rate=51.9% n=27

## Entry Hour Distribution
- 09:00 -> 4
- 10:00 -> 8
- 11:00 -> 4
- 12:00 -> 4
- 13:00 -> 4
- 14:00 -> 4

## Top Symbols by Entry Count
- 005380: 5
- 086520: 5
- 006400: 4
- 035420: 3
- 000660: 2
- 000270: 1
- 005490: 1
- 003670: 1
- 012330: 1
- 009150: 1
- 035720: 1
- 051910: 1
- 066570: 1
- 196170: 1

