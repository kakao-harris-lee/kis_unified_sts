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

## Chart Samples
- 005380 2026-02-27 11:51:00 | score=2.667 | vol20=8.01x slot=40.29x | chart=charts/005380_20260227_1151.png
- 086520 2026-02-25 13:49:00 | score=2.312 | vol20=3.96x slot=34.24x | chart=charts/086520_20260225_1349.png
- 006400 2026-02-25 13:15:00 | score=2.243 | vol20=10.25x slot=15.89x | chart=charts/006400_20260225_1315.png
- 005380 2026-02-19 13:02:00 | score=2.060 | vol20=7.49x slot=14.24x | chart=charts/005380_20260219_1302.png
- 066570 2026-02-19 11:26:00 | score=2.045 | vol20=6.66x slot=14.56x | chart=charts/066570_20260219_1126.png
- 035420 2026-01-29 13:03:00 | score=2.035 | vol20=6.80x slot=14.26x | chart=charts/035420_20260129_1303.png
- 086520 2026-02-19 10:08:00 | score=2.011 | vol20=7.17x slot=9.59x | chart=charts/086520_20260219_1008.png
- 000660 2026-01-28 09:53:00 | score=2.003 | vol20=6.28x slot=11.34x | chart=charts/000660_20260128_0953.png
- 005380 2026-02-26 14:01:00 | score=1.973 | vol20=3.43x slot=16.93x | chart=charts/005380_20260226_1401.png
- 006400 2026-02-19 14:50:00 | score=1.972 | vol20=3.33x slot=17.53x | chart=charts/006400_20260219_1450.png
- 000270 2026-02-11 12:52:00 | score=1.804 | vol20=9.75x slot=6.75x | chart=charts/000270_20260211_1252.png
- 086520 2026-02-12 10:35:00 | score=1.769 | vol20=4.91x slot=8.87x | chart=charts/086520_20260212_1035.png
- 035720 2026-02-09 10:05:00 | score=1.748 | vol20=8.68x slot=5.83x | chart=charts/035720_20260209_1005.png
- 005380 2026-02-11 09:55:00 | score=1.737 | vol20=3.99x slot=9.53x | chart=charts/005380_20260211_0955.png
- 005490 2026-02-05 10:12:00 | score=1.731 | vol20=3.82x slot=9.80x | chart=charts/005490_20260205_1012.png
- 196170 2026-02-23 10:15:00 | score=1.691 | vol20=5.66x slot=6.99x | chart=charts/196170_20260223_1015.png
- 086520 2026-02-09 14:47:00 | score=1.685 | vol20=4.41x slot=7.14x | chart=charts/086520_20260209_1447.png
- 086520 2026-01-27 10:13:00 | score=1.668 | vol20=3.01x slot=6.83x | chart=charts/086520_20260127_1013.png
- 003670 2026-02-25 11:34:00 | score=1.642 | vol20=3.02x slot=9.88x | chart=charts/003670_20260225_1134.png
- 006400 2026-02-05 10:13:00 | score=1.622 | vol20=4.54x slot=6.04x | chart=charts/006400_20260205_1013.png
- 000660 2026-02-20 10:35:00 | score=1.621 | vol20=3.86x slot=7.91x | chart=charts/000660_20260220_1035.png
- 035420 2026-02-23 09:26:00 | score=1.610 | vol20=4.47x slot=6.90x | chart=charts/035420_20260223_0926.png
- 012330 2026-01-29 09:18:00 | score=1.578 | vol20=3.48x slot=5.93x | chart=charts/012330_20260129_0918.png
- 005380 2026-02-03 12:07:00 | score=1.567 | vol20=4.10x slot=6.61x | chart=charts/005380_20260203_1207.png
- 006400 2026-01-27 12:45:00 | score=1.562 | vol20=7.47x slot=3.79x | chart=charts/006400_20260127_1245.png
- 035420 2026-01-28 12:15:00 | score=1.557 | vol20=3.26x slot=6.70x | chart=charts/035420_20260128_1215.png
- 051910 2026-02-03 14:51:00 | score=1.538 | vol20=5.46x slot=4.74x | chart=charts/051910_20260203_1451.png
- 009150 2026-02-24 11:16:00 | score=1.505 | vol20=3.56x slot=6.17x | chart=charts/009150_20260224_1116.png
