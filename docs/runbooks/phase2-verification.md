# Phase 2 Completion Gate — 48h Verification

Target spec: `docs/plans/2026-04-20-futures-paradigm-phase2-scoring.md` §10.
Implementation plan: `docs/plans/2026-04-20-futures-paradigm-phase2-implementation-plan.md`.
Branch: `feat/futures-paradigm-phase2`.

All checkboxes must be ✅ before Phase 3 begins.

## 1. ClickHouse schema

- [ ] V2 migration applied (idempotent):
  ```bash
  set -a && source .env && set +a
  python scripts/migrations/apply_clickhouse_migrations.py
  ```
  Expected: `applied: []` after first deploy.

- [ ] `kospi.news_scored` exists with 10 columns:
  ```bash
  curl -s "http://localhost:8123/?query=DESC+kospi.news_scored" \
    --user "default:${CLICKHOUSE_PASSWORD}"
  ```

## 2. Scorer daemon uptime (48h)

- [ ] systemd unit deployed:
  ```bash
  sudo cp deploy/systemd/kis-news-scorer.service /etc/systemd/system/
  sudo systemctl daemon-reload && sudo systemctl enable --now kis-news-scorer
  ```

- [ ] 48h continuous uptime, NRestarts=0:
  ```bash
  systemctl show kis-news-scorer -p NRestarts,ActiveEnterTimestamp
  ```

- [ ] journalctl shows no repeated errors:
  ```bash
  journalctl -u kis-news-scorer --since "48h ago" -p err | head
  ```

## 3. Consumer-group lag

- [ ] `XPENDING stream:news.raw news_scorer-v1` < 100 continuously:
  ```bash
  redis-cli -n 1 XPENDING stream:news.raw news_scorer-v1
  ```
  Also tracked by Prometheus gauge `news_scorer_backlog`.

## 4. Scoring volume + cost

- [ ] ≥1,000 scored rows over 48h:
  ```sql
  SELECT count() FROM kospi.news_scored WHERE scored_at >= now() - INTERVAL 2 DAY
  ```

- [ ] Daily LLM cost < $5:
  ```bash
  curl -s http://localhost:9091/metrics | grep news_scoring_cost_usd_today
  ```

## 5. Golden-set agreement

- [ ] Pull ~100 random items from `stream:news.raw`, hand-label category + direction_bias, write to `tests/fixtures/news_scoring_golden.json`. Format:
  ```json
  [
    {
      "news_id": "yn-abc123",
      "title": "...",
      "body": "...",
      "human_label": {"category": "macro_us", "direction_bias": "long"}
    }
  ]
  ```
- [ ] Run:
  ```bash
  source .venv/bin/activate
  RUN_GOLDEN=1 pytest tests/integration/test_news_scorer_golden.py -v
  ```
  Expected: category ≥70%, direction ≥75%.

## 6. Fallback ratio

- [ ] `news_scoring_fallback_total / news_scored_total` < 5% over 48h:
  ```
  rate(news_scoring_fallback_total[48h]) / rate(news_scored_total[48h]) < 0.05
  ```

## 7. ML/RL removed

- [ ] No `sts rl`/`sts tft` runtime command or RL shadow logger is required for this gate.
- [ ] Futures validation uses Setup A/C and indicator/strategy-native exits.

## 8. Prometheus metrics spot-check

- [ ] At least 3 of these families emit non-zero samples:
  ```bash
  curl -s http://localhost:9091/metrics | grep -E \
    "news_scored_total|news_scoring_duration_seconds|news_scoring_errors_total|news_scoring_fallback_total|news_scoring_cost_usd_today|news_scorer_backlog"
  ```

## 9. Sign-off

- [ ] Fill in actual numbers above in a comment on the Phase 2 PR.
- [ ] On approval: Phase 3 (decision engine) implementation plan writing begins.
- [ ] On rejection: document failure, rollback (systemd stop + disable), fix, re-verify.

## Rollback

```bash
sudo systemctl stop kis-news-scorer
sudo systemctl disable kis-news-scorer
sudo rm /etc/systemd/system/kis-news-scorer.service
sudo systemctl daemon-reload
```

`kospi.news_scored` table can be left in place — empty table does no harm. Consumer group entries for unhandled messages can be cleared with:

```bash
redis-cli -n 1 XGROUP DESTROY stream:news.raw news_scorer-v1
```

This stops Phase 2 scoring but does NOT affect Phase 1 (raw stream continues collecting).
