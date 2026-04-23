# Phase 1 Completion Gate — 48h Verification

Target spec: `docs/plans/2026-04-20-futures-paradigm-phase1-data-infra.md` §10.
Implementation plan: `docs/plans/2026-04-20-futures-paradigm-phase1-implementation-plan.md`.
Branch: `feat/futures-paradigm-phase1`.

All checkboxes must be ✅ before Phase 2 begins.

## 1. ClickHouse schema

- [ ] `V1` migration applied (commit 072c75a and subsequent runs should be idempotent).
  ```bash
  set -a && source .env && set +a
  python scripts/migrations/apply_clickhouse_migrations.py
  ```
  Expected: `applied: []` after first deploy.

- [ ] All 5 paradigm tables exist:
  ```bash
  curl -s "http://localhost:8123/?query=SHOW+TABLES+FROM+kospi" \
    --user "default:${CLICKHOUSE_PASSWORD}" \
    | grep -E "news_raw|macro_overnight|schema_migrations|signals_all|daily_performance"
  ```
  Expected: all 5 names returned.

## 2. News collector daemon (48h uptime)

- [ ] systemd unit deployed:
  ```bash
  sudo cp deploy/systemd/kis-news-collector.service /etc/systemd/system/
  sudo systemctl daemon-reload && sudo systemctl enable --now kis-news-collector
  ```

- [ ] 48h continuous uptime, restart count 0:
  ```bash
  systemctl show kis-news-collector -p NRestarts,ActiveEnterTimestamp
  ```
  Expected: `NRestarts=0`, `ActiveEnterTimestamp` ≥ 48h ago.

- [ ] Journal shows no repeated errors:
  ```bash
  journalctl -u kis-news-collector --since "48h ago" -p err | head
  ```
  Expected: empty or only transient network errors.

## 3. Macro overnight cron

- [ ] Cron installed:
  ```bash
  bash scripts/cron/install_phase1_crontab.sh
  crontab -l | grep macro_overnight
  ```
  Expected: two entries (us + fx).

- [ ] US session fired at 06:30 KST on a weekday:
  ```bash
  tail -40 logs/macro-us.log
  ```

- [ ] FX session fires every 15 minutes during weekdays:
  ```bash
  tail -40 logs/macro-fx.log
  ```

## 4. Redis stream volume (weekday window)

- [ ] `stream:news.raw` has ≥ 500 entries over 2 days:
  ```bash
  redis-cli -n 1 XLEN stream:news.raw
  ```

- [ ] `stream:macro.overnight` has ≥ 20 entries over 2 days:
  ```bash
  redis-cli -n 1 XLEN stream:macro.overnight
  ```

## 5. ClickHouse persistence matches streams (±1%)

- [ ] news_raw count reasonable vs stream volume:
  ```sql
  -- Run against CH HTTP
  SELECT count() FROM kospi.news_raw WHERE received_at >= now() - INTERVAL 2 DAY
  ```

- [ ] macro_overnight count:
  ```sql
  SELECT count() FROM kospi.macro_overnight WHERE ts >= now() - INTERVAL 2 DAY
  ```

## 6. Test coverage (new modules ≥ 80%)

- [ ] Run:
  ```bash
  source .venv/bin/activate
  pytest tests/unit/news/ tests/unit/macro/ tests/unit/migrations/ \
         tests/unit/monitoring/test_news_macro_metrics.py \
         tests/integration/test_news_collector_e2e.py \
         tests/integration/test_macro_overnight_e2e.py \
         --cov=shared/news --cov=shared/macro \
         --cov=services/news_collector --cov=services/macro_overnight_collector \
         --cov=scripts/migrations --cov-report=term-missing
  ```
  Expected: all tests pass, line coverage ≥ 80% for the six `--cov` targets.

## 7. `rl_mppo` unaffected

- [ ] `rl_mppo` paper trading P&L over 48h post-deploy compared to 48h pre-deploy:
  - Grafana `trading-overview`: open position count, daily PnL KRW, tick-to-fill latency.
  - Acceptance: no statistically significant shift.
  - Cron `scripts/cron/rl_paper.sh` still runs on schedule.

## 8. Prometheus metrics emitting

- [ ] Spot-check emitted metric families:
  ```bash
  curl -s http://localhost:9091/metrics | grep -E "news_collected_total|news_duplicates_total|news_errors_total|macro_collected_total|news_publish_lag_seconds"
  ```
  Expected: at least 3 of the 5 families with non-zero samples (counter/histogram).

## 9. Sign-off

- [ ] Fill in actual numbers above in a comment on PR #(TBD), then request user approval to close out Phase 1.
- [ ] On approval, Phase 2 implementation plan writing (`2026-04-20-futures-paradigm-phase2-scoring.md`) begins.
- [ ] On rejection: note failure mode, rollback (stop systemd unit + remove crontab entries), fix, re-verify.

## Rollback (if needed)

```bash
sudo systemctl stop kis-news-collector
sudo systemctl disable kis-news-collector
sudo rm /etc/systemd/system/kis-news-collector.service
sudo systemctl daemon-reload

crontab -l | grep -v macro_overnight.sh | crontab -
```

ClickHouse tables are left in place — no destructive rollback (they are empty if news collector never ran).
