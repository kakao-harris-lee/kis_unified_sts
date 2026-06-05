# Phase 1 Verification

Phase 1 now verifies Redis stream flow and file-based persistence.

```bash
redis-cli -n 1 ping
sts data validate-parquet --root data/market
uv run --frozen pytest tests/unit/storage/test_runtime_ledger.py -q
```

Expected:

- Redis DB 1 responds.
- Parquet dataset validation completes.
- RuntimeLedger tests pass with temporary SQLite files.
