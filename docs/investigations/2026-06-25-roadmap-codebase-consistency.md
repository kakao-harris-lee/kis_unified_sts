# Roadmap-Codebase Consistency Check (2026-06-25)

**Status**: Completed static audit; follow-up UI evidence captured later on
2026-06-25.
**Source of truth checked**: [../ROADMAP.md](../ROADMAP.md),
[../PROJECT_STATUS.md](../PROJECT_STATUS.md), strategy YAML, Compose profiles,
dashboard route files, frontend route files, and committed tests.

This note is an audit record, not a replacement roadmap. Keep current direction
in `ROADMAP.md` and live snapshot details in `PROJECT_STATUS.md`.

## Findings Updated

### 1. Strategy roster wording was incomplete

Structured YAML parsing of `config/strategies/{stock,futures}/*.yaml` confirmed:

| Asset | Enabled strategies |
|---|---|
| Stock | `momentum_breakout`, `pattern_pullback`, `williams_r` |
| Futures | `setup_a_gap_reversion`, `setup_c_event_reaction` |

The enabled rows in the roadmap/status docs matched the codebase. The disabled
rows needed cleanup:

- Stock docs omitted disabled variants/examples:
  `llm_adaptive_sizing_example`, `opening_volume_surge_combo_balanced`,
  `opening_volume_surge_score_1p8`, and `trend_pullback_consensus_exit`.
- Futures docs used concept names for three disabled configs; the YAML
  `strategy.name` values are `momentum_breakout_futures`,
  `trend_pullback_futures`, and `trix_golden_futures`.
- `config/strategies/futures/track_a_exit.yaml` is intentionally not listed as
  an active/disabled strategy because it has no top-level `strategy:` block. It
  is a reusable exit config retained for future retuning.

Updated:

- [../ROADMAP.md](../ROADMAP.md)
- [../PROJECT_STATUS.md](../PROJECT_STATUS.md)

### 2. Workbench QA evidence was overstated

The codebase contains committed Vitest/Testing Library smoke coverage for
`/risk`, `/coverage`, `/trades`, `/builder`, and `/event-context`:

- `strategy-builder-ui/src/app/quant-ops-workbench.smoke.test.tsx`
- `strategy-builder-ui/package.json` has `npm run test` backed by Vitest.

No committed Playwright config/specs, screenshot artifacts, or HAR artifacts
were found for the Workbench route visual pass. The roadmap/status language was
therefore narrowed from "screenshot review complete" to "automated smoke
coverage complete; screenshot/accessibility artifact capture remains open."

Updated:

- [../ROADMAP.md](../ROADMAP.md)
- [../PROJECT_STATUS.md](../PROJECT_STATUS.md)
- [../plans/2026-06-22-quant-ops-workbench-uiux.md](../plans/2026-06-22-quant-ops-workbench-uiux.md)

## Claims Reconfirmed

- Compose profiles exist for `stock-ingest`, `stock-pipeline`,
  `futures-ingest`, `futures-pipeline`, `futures-killswitch`, `scheduler`, and
  `producers` in `docker-compose.yml`.
- Workbench backend/frontend routes exist for the roadmap rows:
  `/api/health/summary`, `/api/trading/risk-exposure`,
  `/api/trades/lifecycle`, `/api/coverage`, `/api/event-context/diagnostics`,
  `/risk`, `/coverage`, `/trades`, `/builder`, and `/event-context`.
- Runtime storage direction remains Redis DB 1 + SQLite RuntimeLedger +
  Parquet/DuckDB. ClickHouse references in active code are compatibility stubs
  or explicit "removed" errors, not active runtime dependencies.
- `sts rl *`, `sts tft *`, `shared/ml/rl`, and `shared/ml/tft` were not found
  as active runtime paths in `cli`, `shared`, `services`, or `config`.

## Audit Commands

```bash
python - <<'PY'
from pathlib import Path
import yaml

root = Path('.')
for asset in ('stock', 'futures'):
    for path in sorted((root / 'config/strategies' / asset).glob('*.yaml')):
        data = yaml.safe_load(path.read_text()) or {}
        strat = data.get('strategy') or {}
        print(asset, path.name, strat.get('name'), strat.get('enabled'))
PY

rg --files strategy-builder-ui/src/app services/dashboard | sort
find . -maxdepth 3 \( -iname 'playwright.config.*' -o -iname '*.spec.ts' -o -iname '*.spec.tsx' \) -print
find reports docs strategy-builder-ui -maxdepth 4 \( -iname '*screenshot*' -o -iname '*.png' -o -iname '*.webp' -o -iname '*.jpg' \) -print
rg -n "rl_mppo|shared/ml/rl|shared/ml/tft|sts rl|sts tft|tft|RLMPPOEntry|RLMPPOExit|ClickHouse|clickhouse" cli shared services config pyproject.toml docker-compose.yml docs/ROADMAP.md docs/PROJECT_STATUS.md
```

## Remaining Gap

This was a static repository audit. It did not start Docker services, run a
market-session smoke, or perform live browser screenshots. The next evidence
gap is a committed or linked desktop/mobile visual QA artifact set for the
Workbench routes.

## Follow-up UI Evidence

Later on 2026-06-25 KST, the Workbench visual QA gap was closed with Playwright
fallback browser verification and committed desktop/mobile screenshots for
`/risk`, `/coverage`, `/trades`, `/builder`, and `/event-context`.

Evidence: [../testing/quant-ops-workbench-2026-06-25.md](../testing/quant-ops-workbench-2026-06-25.md).
