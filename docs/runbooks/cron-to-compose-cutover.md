# Cron → Compose Cutover (host-crontab teardown)

Operator runbook for the final step of the cron→compose migration: removing all
KIS triggers from the **host crontab** and running every scheduled job from the
Compose stack instead.

- Design: `docs/plans/archive/2026-06-09-cron-to-compose-scheduler.md`
- Prereqs (already merged): PR-A scheduler infra (#447), PR-B one-shots (#448),
  PR-C producer services + session gate (#449)
- **Cutover window: off-hours only** (after 16:00 KST or before 06:30 KST). The
  producers feed the running paper watchlist; do not swap them mid-session.
- Memory: `cron-to-compose-migration`, `deploy-is-docker-not-systemd`

## What the cutover replaces

| Host crontab (before) | Compose (after) |
|---|---|
| `screener.sh start/stop` 08:55/16:00 | `screener` service (profile `producers`), market-hours self-gate |
| `fusion_ranker.sh start/stop` 08:55/16:00 | `fusion-ranker` service (profile `producers`), self-gate |
| ~20 one-shot `*.sh`/`python` jobs | `scheduler` service (profile `scheduler`) running `deploy/scheduler.crontab` via supercronic |
| `kis-news-collector` / `kis-news-scorer` host daemons | `news-collector` / `news-scorer` services (profile `news`) |

After cutover the host crontab keeps **only** non-KIS lines: the env-var
declarations and the two log-maintenance `find` jobs (gzip/delete old host logs).
Every KIS execution trigger lives in the stack.

## 1. Pre-flight

```bash
cd /home/deploy/project/kis_unified_sts
# off-hours? (KST). Futures close 15:45, premarket cron starts 06:30.
TZ=Asia/Seoul date
# the producer/scheduler images exist (built from PR-A/C):
docker compose --env-file .env.paper --profile producers --profile scheduler --profile news build
```

## 2. Disable host KIS crons (keep a backup)

```bash
ts=$(date +%Y%m%d-%H%M%S)
crontab -l > ~/crontab.backup.$ts
# Comment out every KIS execution entry. Keep: SHELL/PATH/KIS_* env vars and the
# two `find $KIS_LOG_DIR ... gzip/-delete` log-maintenance jobs.
crontab -e        # prefix each KIS line with `# [CUTOVER <date> cron->compose] `
```

Verify **zero** active KIS execution crons remain:

```bash
crontab -l | grep -vE '^\s*#' | grep -vE '^\s*$' | grep -E 'scripts/cron|\.py|cli\.main'
# (no output = clean)
```

The only active lines left should be the 5 env-var declarations + the two
`find $KIS_LOG_DIR …` log-maintenance jobs.

## 3. Bring up the Compose producers + scheduler + news/LLM stream

```bash
docker compose --env-file .env.paper --profile producers --profile scheduler --profile news up -d --no-deps \
  screener fusion-ranker scheduler news-collector news-scorer
```

Exactly **one** scheduler must run. A leftover `docker compose run` one-off
(name suffix `-run-<hash>`) double-fires every cron — remove it:

```bash
docker ps --filter name=scheduler --format '{{.Names}}\t{{.Status}}'
docker rm -f <name>-scheduler-run-<hash>   # only if a `-run-` duplicate exists
```

## 4. Kill any stale host producer/news processes

The host `screener.sh stop` / `fusion_ranker.sh stop` use a PID file that can go
stale (report "No process found" while a process keeps running). The *Compose*
producers and news daemons run inside containers (parent = `containerd-shim`); do **not** kill
those. Only kill genuine **host** `python -m services.{screener,fusion_ranker}`
or `python -m services.{news_collector,news_scorer}` processes whose parent is **not** containerd:

```bash
for p in $(pgrep -f 'services\.(screener|fusion_ranker|news_collector|news_scorer)'); do
  ppid=$(ps -o ppid= -p "$p" | tr -d ' ')
  ps -o cmd= -p "$ppid" | grep -q containerd && continue   # container → leave it
  echo "host orphan $p"; kill "$p"
done
```

> The 2026-06-09 cutover initially mis-diagnosed the *container* producer PIDs as
> host orphans and SIGKILLed them; Docker's `restart: unless-stopped` respawned
> them cleanly (no harm), but always check the parent before killing.

## 5. Verify

```bash
# off-hours: the session gate idles — producers log no "Published" lines, and
# system:universe:latest keeps its last in-session timestamp (does NOT advance).
docker compose --env-file .env.paper logs --tail 20 screener fusion-ranker

# scheduler read its crontab and fires jobs on schedule:
docker compose --env-file .env.paper logs --tail 20 scheduler | grep -iE "crontab|job"
docker compose --env-file .env.paper logs --tail 20 news-collector
docker compose --env-file .env.paper logs --tail 20 news-scorer

# next trading day (≥09:00 KST) watchlist continuity:
redis-cli -p 6379 -n 1 get system:universe:latest | head -c 200
redis-cli -p 6379 -n 1 get system:trade_targets:latest | head -c 200
redis-cli -p 6379 -n 1 xinfo stream stream:news.raw
redis-cli -p 6379 -n 1 xinfo groups stream:news.raw
```

Acceptance: host crontab has zero KIS entries; `universe`/`trade_targets`/
`daily_watchlist`, parquet backfills, briefings, and `stream:news.*` are all
produced/consumed by Compose services on schedule.

## 6. Rollback

```bash
crontab ~/crontab.backup.<ts>                               # host crons resume next tick
docker compose --env-file .env.paper stop screener fusion-ranker scheduler
docker compose --env-file .env.paper stop news-collector news-scorer
```

Redis is a single host instance (shared), so no data migration on rollback.

## Appendix — trader-futures after-close restart loop (fixed)

During this cutover the `trader-futures` container showed `RestartCount 257`
(`ExitCode 0`) after the 15:45 KST close. Root cause: in `--daemon` mode,
`TradingOrchestrator.run_session()` started after close would call
`start()`→`stop()`; `stop()` sets `_running=False`, breaking the daemon
`while self._running` loop → clean exit → `restart: unless-stopped` respawn →
~14s tight loop re-running KIS REST/WS prewarm + startup LLM analysis.

Fix: `run_session()` returns early (no `start()`/`stop()`) when started after the
day's close, so `_running` is preserved and the daemon loop sleeps to the next
session. One restart/day at close (then idle) is expected and harmless.
Regression test: `tests/unit/trading/test_orchestrator_daemon_after_close.py`.
