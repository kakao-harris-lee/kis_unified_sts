# Hybrid Pipeline Trust Status

Last verified: `2026-03-11`

## Current status

The hybrid learning pipeline is runnable in this worktree, but the current machine does **not** have authentic ClickHouse-backed KOSPI data access.

- Regime catalog provenance: `sample_fallback`
- Real catalog authenticity: `false`
- Hybrid manifest final selection: `false`

## What is trustworthy right now

- Dataset materialization logic
- Provenance propagation into artifacts
- Bootstrap/fallback safety guards
- Hybrid RL loader/training/evaluation code paths
- Smoke validation and pretraining-oriented runs

## What is *not* trustworthy right now

- Final model ranking
- Claimed outperformance vs baseline on authentic KOSPI holdout
- Any evaluation result presented as production-ready selection evidence

## Required condition for final-selection eligibility

Rebuild the artifacts after restoring real ClickHouse access so that:

1. `artifacts/datasets/regime_catalog/summary.json` reports:
   - `provenance.source_mode = clickhouse`
   - `provenance.is_authentic_real = true`
2. `artifacts/datasets/hybrid/manifest.json` reports:
   - `rules.real_catalog_authentic = true`
   - `rules.final_selection_allowed = true`

Until then, every hybrid training/evaluation run should be interpreted as **non-final**.
