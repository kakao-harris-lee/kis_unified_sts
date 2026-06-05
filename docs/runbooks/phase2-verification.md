# Phase 2 Verification

Phase 2 verifies news/scoring/event flow without a server database.

```bash
redis-cli -n 1 ping
uv run --frozen pytest tests/unit/news tests/unit/scoring -q
```

Expected:

- Redis stream publisher tests pass.
- Archive writers are no-op or RuntimeLedger-backed.
- No test imports a removed database driver.
