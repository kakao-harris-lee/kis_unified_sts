# HAR-RV Log-RV Validation

Use this runbook before changing forecasting config from `rv_target: raw` to
`rv_target: log`. The validator is local-only: it reads an operator-provided
CSV/Parquet bar file, computes regular-session KST daily realized variance with
the shared HAR-RV path, fits both raw and log targets, and writes a JSON report.

## Inputs

The bars file must include:

- `datetime`: timezone-aware timestamps, or timestamps interpretable as UTC.
- `close`: minute close price.
- `code`: optional, used when passing `--code`.

Use active near-month futures contract bars, not a polluted synthetic continuous
series. Keep real data and generated reports out of committed secrets or runtime
config.

## Command

```bash
python scripts/forecasting/validate_har_rv.py \
  --bars data/validation/kospi200f_1m.parquet \
  --code A01606 \
  --start 2026-05-01T00:00:00+09:00 \
  --end 2026-06-01T00:00:00+09:00 \
  --out data/validation/har_rv_validation.json \
  --min-r2-oos 0.10
```

`--code`, `--start`, and `--end` are optional. `--start` and `--end` are applied
before daily RV computation; session filtering remains KST regular session
inside `shared.forecasting.realized_variance.daily_rv_series`.

## Report Interpretation

The CLI exits `0` when it can read bars, compute daily RV, and write the report,
even if one target fit fails the OOS gate. It exits nonzero only when the input
bars are unreadable/empty, no regular-session RV can be computed, or the report
cannot be written.

Each target report contains:

- `target`: `raw` or `log`.
- `fit_ok`: whether the HAR-RV fit passed the configured OOS gate.
- `r2_oos`: holdout R-squared when fit passed, otherwise `null`.
- `forecast_pct`: annualized volatility forecast when fit passed, otherwise
  `null`.
- `rv_history_days`: daily RV observations available after filtering.
- `error`: fit rejection or exception text when `fit_ok` is false.

Treat `log` as only a candidate until the real-data report is acceptable and the
paper/shadow observation period is complete.
