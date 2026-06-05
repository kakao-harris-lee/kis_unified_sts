# Phase 3 Verification

Phase 3 verifies futures market data and strategy gates against Parquet.

```bash
sts data validate-parquet --root data/market
python scripts/analysis/check_futures_backfill_integrity.py
uv run --frozen pytest tests/unit/strategy/gates -q
```

Expected:

- required futures partitions exist under `data/market/futures`
- gate tests pass without server DB clients
- backtests load data through `MarketDataStore`
