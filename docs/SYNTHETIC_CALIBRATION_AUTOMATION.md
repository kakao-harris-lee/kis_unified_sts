# Synthetic Calibration Automation

Synthetic calibration optimization can now be run in two modes:

## 1. Development runner

Use the local convenience wrapper:

- `scripts/run_synthetic_calibration_optimizer.sh`

Environment overrides:

- `MAX_ITERATIONS` (default: `3`)
- `PATIENCE` (default: `1`)
- `MIN_IMPROVEMENT` (default: `1e-6`)
- `OUTPUT_ROOT` (default: `artifacts/datasets/calibration/optimizer_run`)

Outputs:

- `optimizer_manifest.json`
- `optimizer_summary.md`
- per-iteration candidate config, dataset, scorecard, and comparison files

## 2. Server cron runner

Runtime script:

- `scripts/cron/synthetic_calibration_optimizer.sh`

Features:

- lock file protection
- `.env` loading
- timeout support
- daily log file writing
- markdown summary generation after optimization

Default example schedule:

- `30 21 * * 6` (Saturday 21:30)

Relevant environment overrides:

- `SYNTH_CAL_PROJECT_DIR`
- `SYNTH_CAL_OUTPUT_ROOT`
- `SYNTH_CAL_MAX_ITERATIONS`
- `SYNTH_CAL_PATIENCE`
- `SYNTH_CAL_MIN_IMPROVEMENT`
- `SYNTH_CAL_TIMEOUT`

## 3. Crontab registration helper

Installer script:

- `scripts/cron/install_synthetic_calibration_optimizer_cron.sh`

Examples:

- print the entry only:
  - `CRON_MODE=print ./scripts/cron/install_synthetic_calibration_optimizer_cron.sh`
- install default schedule:
  - `./scripts/cron/install_synthetic_calibration_optimizer_cron.sh`
- install custom schedule:
  - `CRON_SCHEDULE="0 22 * * 6" ./scripts/cron/install_synthetic_calibration_optimizer_cron.sh`

## 4. Expected artifacts

Default optimizer run root:

- `artifacts/datasets/calibration/optimizer_run/`

Important files:

- `optimizer_manifest.json`
- `optimizer_summary.md`
- `iteration_01/`, `iteration_02/`, ...

## 5. Operational note

Current real-data reference may still be `sample_fallback` on machines without ClickHouse access.
That means this automation is excellent for synthetic-shape refinement and loop validation,
but not yet for final production calibration sign-off.
