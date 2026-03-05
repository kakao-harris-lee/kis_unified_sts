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

## Chart Samples
- 005380 2026-02-27 11:51:00 | score=2.667 | vol20=8.01x slot=40.29x | chart=charts/005380_20260227_1151.png
- 000270 2026-02-19 13:08:00 | score=2.446 | vol20=7.89x slot=32.81x | chart=charts/000270_20260219_1308.png
- 003670 2026-01-26 12:41:00 | score=2.401 | vol20=12.98x slot=20.22x | chart=charts/003670_20260126_1241.png
- 005490 2026-02-12 10:27:00 | score=2.320 | vol20=5.05x slot=35.70x | chart=charts/005490_20260212_1027.png
- 086520 2026-02-25 13:49:00 | score=2.312 | vol20=3.96x slot=34.24x | chart=charts/086520_20260225_1349.png
- 006400 2026-02-27 13:47:00 | score=2.298 | vol20=13.23x slot=15.24x | chart=charts/006400_20260227_1347.png
- 006400 2026-02-25 13:15:00 | score=2.243 | vol20=10.25x slot=15.89x | chart=charts/006400_20260225_1315.png
- 247540 2026-01-26 10:28:00 | score=2.218 | vol20=3.81x slot=33.73x | chart=charts/247540_20260126_1028.png
- 005490 2026-01-28 13:15:00 | score=2.149 | vol20=8.33x slot=14.94x | chart=charts/005490_20260128_1315.png
- 196170 2026-02-19 10:01:00 | score=2.097 | vol20=10.12x slot=11.04x | chart=charts/196170_20260219_1001.png
- 066570 2026-02-11 09:33:00 | score=2.086 | vol20=3.54x slot=25.35x | chart=charts/066570_20260211_0933.png
- 005380 2026-02-19 13:02:00 | score=2.060 | vol20=7.49x slot=14.24x | chart=charts/005380_20260219_1302.png
- 066570 2026-02-19 11:26:00 | score=2.045 | vol20=6.66x slot=14.56x | chart=charts/066570_20260219_1126.png
- 035420 2026-01-29 13:03:00 | score=2.035 | vol20=6.80x slot=14.26x | chart=charts/035420_20260129_1303.png
- 086520 2026-02-19 10:08:00 | score=2.011 | vol20=7.17x slot=9.59x | chart=charts/086520_20260219_1008.png
- 006400 2026-01-30 14:50:00 | score=2.006 | vol20=5.10x slot=12.20x | chart=charts/006400_20260130_1450.png
- 005490 2026-02-05 10:10:00 | score=2.003 | vol20=7.27x slot=10.90x | chart=charts/005490_20260205_1010.png
- 000660 2026-01-28 09:53:00 | score=2.003 | vol20=6.28x slot=11.34x | chart=charts/000660_20260128_0953.png
- 005380 2026-02-26 14:01:00 | score=1.973 | vol20=3.43x slot=16.93x | chart=charts/005380_20260226_1401.png
- 006400 2026-02-19 14:50:00 | score=1.972 | vol20=3.33x slot=17.53x | chart=charts/006400_20260219_1450.png
- 086520 2026-01-26 12:54:00 | score=1.964 | vol20=4.04x slot=14.76x | chart=charts/086520_20260126_1254.png
- 000660 2026-01-23 12:06:00 | score=1.944 | vol20=9.17x slot=8.29x | chart=charts/000660_20260123_1206.png
- 005380 2026-02-11 09:57:00 | score=1.943 | vol20=4.38x slot=14.24x | chart=charts/005380_20260211_0957.png
- 051910 2026-02-10 13:24:00 | score=1.912 | vol20=9.20x slot=7.55x | chart=charts/051910_20260210_1324.png
- 000660 2026-02-20 10:33:00 | score=1.882 | vol20=10.94x slot=6.18x | chart=charts/000660_20260220_1033.png
- 051910 2026-02-25 11:07:00 | score=1.874 | vol20=4.09x slot=10.58x | chart=charts/051910_20260225_1107.png
- 005490 2026-01-29 14:23:00 | score=1.873 | vol20=8.46x slot=7.88x | chart=charts/005490_20260129_1423.png
- 068270 2026-02-04 11:05:00 | score=1.849 | vol20=12.41x slot=5.42x | chart=charts/068270_20260204_1105.png
- 055550 2026-02-11 11:33:00 | score=1.815 | vol20=3.99x slot=12.99x | chart=charts/055550_20260211_1133.png
- 068270 2026-01-28 10:46:00 | score=1.809 | vol20=4.57x slot=9.40x | chart=charts/068270_20260128_1046.png
- 000270 2026-02-11 12:52:00 | score=1.804 | vol20=9.75x slot=6.75x | chart=charts/000270_20260211_1252.png
