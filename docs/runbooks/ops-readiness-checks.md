# Ops Readiness Checks

Use the repo-local readiness checklist before and after runtime cutovers to
surface file/config gaps and the external operations that still require an
operator.

```bash
python -m scripts.ops.ops_readiness_check
```

The default mode is offline. It reads repository files and config only; it does
not start Docker, require localhost, touch Redis, or make network calls.

The JSON report contains these sections:

- `runtime_storage_smoke`: `config/storage.yaml`, SQLite runtime ledger config,
  RuntimeLedger file presence, Redis DB 1 config evidence, and the still-required
  post-cutover Redis+SQLite E2E smoke.
- `position_recovery_drill`: position recovery script/test presence plus the
  still-required operator drill.
- `mlflow_tracking`: tracking URI config evidence plus the still-required
  MLflow restart/readiness confirmation.
- `workbench_qa_artifacts`: Workbench QA evidence document presence, currently
  `docs/testing/quant-ops-workbench-2026-06-25.md`. This runbook itself is not
  accepted as visual/accessibility evidence.
- `strategy_lab_workflow`: Strategy Lab config/API/UI file presence plus the
  remaining backtest/paper feedback and reactivation-gate workflow follow-up.

Statuses are intentionally conservative. A missing file/config entry or an
external operation that cannot be completed offline is reported as
`action_required`, not `pass`.

Optional live HTTP probes are disabled unless explicitly requested:

```bash
python -m scripts.ops.ops_readiness_check \
  --require-live-http \
  --http-url http://127.0.0.1:5081/health
```

Only use live probes in an environment where the target service is expected to
be running.
