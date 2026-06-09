# Cron → Compose Scheduler Migration

- Date: 2026-06-09
- Status: **Design (for review)** — implementation phased, cutover off-hours
- Owner decision: paper/live run via Docker Compose only; **host crontab must
  carry no KIS triggers** (portability / single-machine-free operation).
  See memory `cron-to-compose-migration`.

## 1. Goal

Move every KIS-related scheduled execution from the host crontab into the
Compose stack, so the whole paper/live system is self-contained and portable to
another machine with `cp .env.paper.example .env.paper` + secrets + `docker
compose up`. No `crontab` entry, no host `.venv`, no `scripts/cron/*.sh` host
wrappers in the operational path.

Out of scope: the already-migrated decoupled stock pipeline + futures
`trader-futures` (done — `2026-06-06-compose-pipeline-services.md`); non-KIS host
crons (other projects).

## 2. Current state (2026-06-09)

Runtime is Compose (paper cutover done today). Still on **host crontab**:

### 2a. Long-running daemons (start 08:55 / stop 16:00 KST)

| Job | Entry | Role | Live impact |
|---|---|---|---|
| `screener.sh` | `python -m services.screener` | KIS 등락률/거래대금 5s ranking → `system:universe`, `dip_candidates` | **feeds live paper** |
| `fusion_ranker.sh` | `python -m services.fusion_ranker` | fuse → `system:trade_targets:latest` | **feeds live paper** |

### 2b. One-shot scheduled jobs (→ scheduler service)

| KST | Job | Entry (python) |
|---|---|---|
| 06:30 M-F | premarket briefing | `python scripts/llm_premarket_briefing.py` |
| 06:30 M-F | macro overnight (us) | `python -m services.macro_overnight_collector.main us` |
| */15 M-F | macro fx | `python -m services.macro_overnight_collector.main fx` |
| 07:35 M-F | forecasting refit | `python scripts/forecasting/refit_har_rv.py` |
| 08:30 M-F | daily scanner | `python scripts/run_daily_scanner.py` |
| 08:50,08:58 M-F | indicator scanner | `python scripts/daily_indicator_scanner.py` |
| 10–15h M-F | llm intraday | `python -m scripts.analysis.llm_intraday_refresh` |
| 15:30 M-F | market-close briefing | `python -m scripts.analysis.llm_market_close_briefing` |
| 15:40 M-F | equity snapshot | `python scripts/analysis/publish_equity_snapshot.py` |
| 15:50 M-F | stock backfill | `sts stock-backfill run` / `today` |
| 16:00 M-F | phase2 verification | `scripts/cron/phase2_daily_verification.sh` (TBD entry) |
| 16:05 M-F | backfill --all | `sts backfill run` |
| 16:10 M-F | accumulation scan | `scripts/cron/accumulation_scan.sh` (TBD entry) |
| 16:10 M-F | stock paper verify | `python scripts/analysis/stock_paper_daily_verification.py` |
| 16:20 M-F | stock daily backfill | `sts stock-backfill daily` |
| Sun 04:00 | rotate reports | `python -m scripts.maintenance.rotate_reports` |
| Mon 07:00 | counterfactual weekly | `scripts/cron/counterfactual_weekly.sh` (TBD entry) |
| Sun 14:00 | forecast weekly report | `scripts/cron/forecast_weekly_report.sh` (TBD entry) |
| Sun 18:00 | regime-gate counterfactual | `python scripts/analysis/regime_gate_counterfactual.py` |

(TBD entries: read the `.sh` during implementation; all resolve to a
`python …`/`sts …` one-shot.)

### 2c. Drop (do not migrate)

- `stock_builder_preset_experiment` — one-off window 2026-06-01..05, **expired**.
- Dead RL crons — already removed 2026-06-08.

### 2d. Already in Compose

`redis`(host-redis via host-gateway in paper), `dashboard`, `strategy-builder-ui`,
`caddy`, `forecasting` (HAR-RV daemon — distinct from the refit one-shot),
`stream-exporter`, `prometheus`, decoupled stock daemons, `trader-futures`.
No scheduler service exists.

## 3. Target architecture

```
Compose stack (self-contained)
├─ producers (profile: producers)
│   ├─ screener        (python -m services.screener,        market-hours self-gated)
│   └─ fusion-ranker   (python -m services.fusion_ranker,   market-hours self-gated)
├─ scheduler (profile: scheduler)
│   └─ supercronic running deploy/scheduler.crontab (KST), one-shot jobs §2b
└─ existing: stock pipeline + trader-futures + infra
```

All new services use the **same app image** (`Dockerfile`, has `services/` +
`scripts/`), the shared `x-redis-runtime-env` / `x-runtime-storage-env` /
`x-kis-runtime-env` (real stock key, single host redis) + `TZ=Asia/Seoul`.

## 4. Decision — scheduler technology: **supercronic**

Chosen: **supercronic** (static Go binary, purpose-built for crontab-in-container).
- Respects crontab syntax incl. `CRON_TZ`/`TZ=Asia/Seoul`; logs to **stdout**
  (Docker logging), reports exit codes, no PID-1/`crond` quirks, no docker socket.
- Add binary to the app image (or a thin `Dockerfile.scheduler` `FROM` app image
  + download supercronic); `command: ["supercronic", "/app/deploy/scheduler.crontab"]`.

Rejected:
- **ofelia** — schedules via docker labels/API, needs the **docker socket**
  (privilege/security); we want jobs run *inside* the stack image.
- **system cron/crond in container** — PID-1, log-to-file (not stdout), env
  propagation friction.
- **python APScheduler service** — reinvents scheduling; more code to own.

## 5. New service definitions (sketch)

```yaml
# producers
screener:
  <<: *pipeline-service            # app image, host-gateway, redis depends, logging
  profiles: ["producers"]
  command: ["python", "-m", "services.screener"]
  environment:
    <<: [*redis-runtime-env, *runtime-storage-env, *kis-runtime-env, *alert-runtime-env]
    TZ: "Asia/Seoul"
fusion-ranker:
  <<: *pipeline-service
  profiles: ["producers"]
  command: ["python", "-m", "services.fusion_ranker"]
  environment: { <<: [...], TZ: "Asia/Seoul" }

# scheduler
scheduler:
  build: { context: ., dockerfile: Dockerfile.scheduler }
  profiles: ["scheduler"]
  command: ["supercronic", "/app/deploy/scheduler.crontab"]
  environment:
    <<: [*redis-runtime-env, *runtime-storage-env, *kis-runtime-env, *alert-runtime-env]
    OPENAI_API_KEY: "${OPENAI_API_KEY:-}"
    TZ: "Asia/Seoul"
  volumes: *trading-runtime-volumes
```

`deploy/scheduler.crontab` (KST native, no host paths):
```cron
30 6  * * 1-5 cd /app && python scripts/llm_premarket_briefing.py
30 8  * * 1-5 cd /app && python scripts/run_daily_scanner.py
50 8  * * 1-5 cd /app && python scripts/daily_indicator_scanner.py
58 8  * * 1-5 cd /app && python scripts/daily_indicator_scanner.py
…   (all §2b jobs)
```

## 6. Daemon market-hours gating (screener / fusion)

As always-on services (`restart: unless-stopped`) they would poll KIS 24/7
(wasteful; ranking empty off-hours). The `.sh` currently bounds them 08:55–16:00.
**Add a session gate to each module's loop**: idle (sleep to next open) outside
09:00–15:30 KST and on non-trading days, reusing `HolidayCache` /
`config/market_schedule.yaml`. This is the only **code** change in the migration
(everything else is compose/config). Alternatively accept 24/7 polling for v1 and
add gating later — but the gate is cheap and avoids off-hours KIS load.

## 7. Phased implementation (separate PRs)

1. **PR-A — scheduler infra**: `Dockerfile.scheduler`, `deploy/scheduler.crontab`,
   `scheduler` service (profile `scheduler`), wire 2–3 low-risk EOD jobs
   (rotate_reports, backfills). Verify in paper stack (jobs fire, write parquet)
   without touching host crons. Resolve TBD entrypoints.
2. **PR-B — remaining one-shots**: add briefings, scanners, macro, forecasting
   refit, verifications, counterfactuals to the crontab. Verify each.
3. **PR-C — producer services + gating**: `screener`/`fusion-ranker` services +
   market-hours self-gate code. Shadow-validate they produce the same
   `universe`/`trade_targets` keys as the host daemons.
4. **PR-D — cutover runbook + host-cron teardown doc**.

## 8. Cutover (off-hours, after 16:00 or before 06:30 KST)

```bash
# 1. stop host KIS crons (comment all KIS entries; keep backup)
crontab -e        # or a teardown script
# 2. bring up the compose producers + scheduler
docker compose --env-file .env.paper --profile producers up -d screener fusion-ranker
docker compose --env-file .env.paper --profile scheduler up -d scheduler
# 3. verify next session: watchlist keys fresh, scheduler jobs ran
redis-cli -p 6379 -n 1 ttl system:trade_targets:latest system:daily_watchlist:latest
docker compose --env-file .env.paper logs scheduler | grep -iE "scanner|backfill"
```

**Do NOT cut over during market hours** — the live producers feed the running
paper watchlist. First safe window: today after 16:00 KST, or before 06:30 KST.

## 9. Rollback

Re-enable the host-cron backup (`crontab ~/crontab.backup.<ts>`) and
`docker compose stop screener fusion-ranker scheduler`. Host crons resume on the
next schedule tick. Redis keys are shared (single host redis), so no data move.

## 10. Risks & open questions

- **Watchlist continuity**: producer cutover must be off-hours; a mismatch
  (compose producers not producing) starves the strategy → no trades next day.
  Mitigate: shadow-run producers in parallel (different output keys) for 1 day,
  diff vs host output, then swap keys.
- **TBD entrypoints** (§2b): finalize by reading the 4 `.sh` wrappers; all are
  one-shot `python`/`sts`.
- **Token cache / rate limits**: scheduler + producers + trader-futures share the
  real stock key. KIS token cache is per-key file (`/app/.cache`, mounted) —
  fine. Watch EGW00201 rate-limit if many jobs hit KIS at 16:00; stagger if needed.
- **`forecasting` name clash**: the existing `forecasting` service (HAR-RV daemon)
  vs the `forecasting refit` one-shot — keep both; the one-shot goes in the
  scheduler crontab, the daemon stays a service.
- **CRON_TZ vs TZ**: supercronic honors `TZ`/`CRON_TZ`; set `TZ=Asia/Seoul` on
  the scheduler service so all crontab times are KST (CLAUDE.md §5).
- **Idempotency**: scheduler restart shouldn't double-run; supercronic doesn't
  catch-up missed runs by default (acceptable).

## 11. Acceptance

- Host crontab carries **zero KIS entries** after cutover.
- `universe` / `trade_targets` / `daily_watchlist` / parquet backfills / briefings
  all produced by Compose services on schedule.
- Reproducible on a fresh host: `.env.paper` + `docker compose --profile
  producers --profile scheduler --profile stock-ingest --profile stock-pipeline
  --profile trading up -d`.
