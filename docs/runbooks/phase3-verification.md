# Phase 3 Completion Gate — Verification

Target spec: `docs/plans/2026-04-20-futures-paradigm-phase3-decision-engine.md` §12.
Implementation plan: `docs/plans/2026-04-20-futures-paradigm-phase3-implementation-plan.md`.
Branch: `feat/futures-paradigm-phase3`.

Phase 3 is **backtest-only**. There is no runtime daemon to observe for 48 h;
the gate is almost entirely backtest + static-analysis checks.

## 1. Unit / integration test suite

- [ ] Full Phase 3 test sweep passes:
  ```bash
  source .venv/bin/activate
  pytest tests/unit/decision tests/unit/risk \
         tests/unit/execution/test_contract_spec.py \
         tests/unit/strategy/position/test_fixed_fractional_futures_sizer.py \
         tests/unit/monitoring/test_decision_metrics.py \
         tests/integration/test_backtest_harness.py \
         tests/integration/test_decision_pipeline_e2e.py \
         --cov=shared/decision --cov=shared/risk \
         --cov=shared/execution/contract_spec \
         --cov=shared/backtest --cov-report=term-missing
  ```
- [ ] Coverage: `shared/decision` ≥ 90 %, `shared/risk` ≥ 85 %,
      `shared/execution/contract_spec` = 100 %, `shared/backtest` ≥ 80 %.

## 2. Hardcoded multiplier removal

- [ ] No literal `50000` in `shared/arbitrage/config.py` or
      `shared/trend/config.py` outside the defensive fallback helper:
  ```bash
  grep -n "50000" shared/arbitrage/config.py shared/trend/config.py
  ```
  Expected output: matches only inside `_load_default_mini_multiplier` fallback.
- [ ] `config/execution.yaml` contains a `futures_contract_spec` section with
      both `kospi200_mini` and `kospi200_full` entries.

## 3. ClickHouse schema

- [ ] `kospi.signals_all` exists (V1 migration already applied in Phase 1):
  ```bash
  set -a && source .env && set +a
  curl -s "http://localhost:8123/?query=DESC+kospi.signals_all" \
    --user "default:${CLICKHOUSE_PASSWORD}"
  ```
  Expected: `signal_id, generated_at, setup_type, direction, entry_price,
  stop_loss, take_profit, confidence, executed, skip_reason, reason_tags`.

## 4. 6-month backtest per Setup

- [ ] Run harness on `data/kospi200f_1m_clean.csv` (6 months):
  ```bash
  # See scripts/walk_forward_phase3.py for the orchestration pattern.
  # The smoke test: just a single IS-only run across 6 months.
  python scripts/walk_forward_phase3.py \
      --data data/kospi200f_1m_clean.csv \
      --is-months 6 --oos-months 0 \
      --out results/phase3_smoke.json
  ```
- [ ] Expected per spec §8.3:
  - Setup A: ≥ 30 trades / 6 mo, EV > 0.5 tick (post-slippage), win rate ≥ 45 %
  - Setup C: ≥ 30 trades / 6 mo, EV > 0.5 tick (post-slippage), win rate ≥ 45 %
  - Avg R:R ≥ 1.5
  - Max consecutive losses ≤ 5

## 5. Walk-forward analysis

- [ ] 4-month IS / 2-month OOS folds:
  ```bash
  python scripts/walk_forward_phase3.py \
      --data data/kospi200f_1m_clean.csv \
      --is-months 4 --oos-months 2 \
      --out results/phase3_wf.json
  ```
- [ ] Gate: OOS EV ≥ 0.5 × IS EV **AND** OOS EV > 0 on ≥ half of folds.

## 6. `signals_all` persistence smoke

- [ ] Integration test wrote rows to the mocked CH client:
  ```bash
  pytest tests/integration/test_decision_pipeline_e2e.py -v
  ```
- [ ] No need to write to real CH from the gate; Phase 4 runtime will drive
      real persistence.

## 7. `rl_mppo` unaffected

- [ ] `services/trading/` and `shared/ml/rl/` were NOT modified in this PR —
      confirm:
  ```bash
  git log origin/main..HEAD --name-only | \
      grep -E "services/trading/|shared/ml/rl/" && echo "REGRESSION" || echo "OK"
  ```
  Expected: `OK`.
- [ ] `rl_mppo` paper trading Grafana `trading-overview` shows no regressions
      in open positions / daily PnL / latency after the Phase 3 branch merges.

## 8. Prometheus metrics compile

- [ ] The 7 new metric families + their helpers import cleanly:
  ```bash
  python -c "
  from services.monitoring.metrics import (
      signal_candidate_total, signal_final_total, signal_rejected_total,
      signal_generator_duration_seconds, risk_state_daily_pnl_pct,
      risk_state_consecutive_losses, risk_state_daily_trade_count,
      record_signal_candidate, record_signal_final, record_signal_rejected,
      record_signal_generator_duration, record_risk_state_daily_pnl_pct,
      record_risk_state_consecutive_losses, record_risk_state_daily_trade_count,
  )
  print('ok')
  "
  ```

## 9. Sign-off

- [ ] Fill in actual backtest numbers in a comment on the Phase 3 PR.
- [ ] On approval: Phase 4 (execution/ordering) implementation-plan writing
      begins.
- [ ] On rejection: tune Setup params via
      `scripts/optimize_decision_engine.py`, re-run WF, re-verify.

## Rollback

Phase 3 is backtest-only — there is nothing running to stop. If any
downstream code starts depending on `shared/decision/*` or
`shared/risk/filters/*` prematurely, revert this PR:

```bash
git revert -m 1 <merge-commit-sha>
```

The V2 migration (news_scored, Phase 2) and V1 migration (signals_all, Phase 1)
stay in place.
