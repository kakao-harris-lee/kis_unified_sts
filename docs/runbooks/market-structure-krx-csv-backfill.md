# KRX Foreign Futures CSV Backfill Procedure

**Scope**: Unified roadmap Phase 0 (operator activation) / Wave 2b.

**Purpose**: Manual backfill of `foreign_futures` component into market structure daily snapshots when the automatic KIS FHPTJ04030000 feed cannot provide historical data.

**Related files**:
- `config/market_structure.yaml::collector.kis` — field mapping and rate limits
- `scripts/backfill_market_structure.py::backfill_from_csv()` — CSV loader
- `shared/storage/market_structure_store.py` — snapshot schema

---

## Quick Start

### 1. Obtain KRX foreign futures data

**Source**: [KRX InfoData](https://data.krx.co.kr/)
- Menu: 통계 → 시장통계 → 투자자매매동향 → 선물옵션 → KOSPI200선물
- Parameters:
  - 시장: **선물** (Futures)
  - 상품: **KOSPI200**
  - 기간: Select date range
  - 투자자별: **외국인** (foreign investor)
- Output: Export as **CSV**

### 2. Prepare CSV file

Format with columns:

```
date,net_qty,net_val
2026-06-01,12345,567890000
2026-06-02,8901,234560000
```

**Column definitions**:
- `date`: Trade date (YYYY-MM-DD or YYYYMMDD)
- `net_qty`: Net buy quantity (정수)
- `net_val`: Net buy value in KRW (정수)

### 3. Run backfill

```bash
cd /home/deploy/project/kis_unified_sts
export REDIS_URL=redis://localhost:6379/1  # paper; 6382 for live
python scripts/backfill_market_structure.py \
  --from-csv <csv_file> \
  --trade-date-start 2026-06-01 \
  --trade-date-end 2026-07-02 \
  --component foreign_futures \
  --snapshot-names premarket close
```

**Key flags**:
- `--from-csv <path>`: CSV file path (required)
- `--trade-date-start / --trade-date-end`: Date range
- `--component foreign_futures`: Load only this component
- `--dry-run`: Preview without writing

### 4. Verify parquet

```bash
duckdb << 'SQL'
SELECT 
  date_trunc('day', datetime)::date as trade_date,
  component,
  COUNT(*) as snapshots
FROM read_parquet('data/market/market_structure/daily/**/*.parquet')
WHERE component = 'foreign_futures'
  AND date_trunc('day', datetime)::date >= '2026-06-01'
GROUP BY trade_date, component
ORDER BY trade_date DESC
LIMIT 20;
SQL
```

---

## Troubleshooting

### CSV column name mismatch

Expected columns: `date`, `net_qty`, `net_val` (case-insensitive)

If KRX uses Korean headers, edit to:
```bash
sed -i '1s/.*/date,net_qty,net_val/' foreign_futures.csv
```

### Date format error

Convert dates to YYYY-MM-DD format:
```bash
awk -F',' 'NR==1 {print; next} {
  split($1, d, "/"); 
  $1 = d[3]"-"d[1]"-"d[2]; 
  print
}' foreign_futures.csv > foreign_futures_fixed.csv
```

### Thousands separator in net_val

Remove commas:
```bash
sed 's/,//g' foreign_futures.csv > foreign_futures_clean.csv
```

---

## Integration with Phase 0 Backfill

**Auto components** (filled by KIS REST API):
- `program_trade_daily` — FHPPG04600001
- `oi_and_price` — FHMIF10000000
- `k200_index` — FHPUP02100000
- `fx_rate` — FHKUP03500100

**Manual component** (foreign_futures):
- KIS FHPTJ04030000 has shallow history (1-2 months)
- KRX InfoData has full history (years)
- Use `--from-csv` when recovering from outages or backfilling > 2 months

**Operator workflow**:
1. Run auto backfill (fills 4 components)
2. Check if foreign_futures is present
3. If missing, export from KRX and backfill manually

---

## Schema Reference

**Parquet table**: `data/market/market_structure/daily/**/*.parquet`

| Column | Type | Notes |
|--------|------|-------|
| datetime | timestamp | KST (premarket 08:00, close 18:40) |
| trade_date | date | KST |
| asset_class | string | 'futures' (Phase 0 only) |
| snapshot | string | 'premarket' or 'close' |
| component | string | 'foreign_futures', 'program', 'oi', 'k200', 'basis', 'fx' |
| finalized | boolean | true=official, false=provisional |
| missing_components | list | Absent components |
| foreign_futures | integer | Net qty (if applicable) |
| (others) | ... | One per component |

---

## Next Steps

- **Phase 2 (futures)**: Automate market structure collection for trading orchestrator
- **Phase 2c (stock)**: Add program trading + investor sentiment
- **Phase 2d (macro)**: Expand FX, VIX, 10Y yield, gold
