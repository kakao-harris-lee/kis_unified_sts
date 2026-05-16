# Crontab Operations

## Required crontab entries (deploy user)

Production crontab on the deploy server. Maintained manually via `crontab -e` — this document is the registration reference.

### RL / Futures Paper Trading

- `55 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/rl_paper.sh start`
  - Starts: RL Maskable PPO paper trading (or profile matrix comparison if enabled)
  - Time: 08:55 (5 min before market open)
  
- `40 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/rl_paper.sh stop`
  - Stops: RL paper trading gracefully
  - Time: 15:40 (25 min before market close, allows position exit)

### Stock Trading Orchestrator

- `55 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_trading.sh start`
  - Starts: Multi-strategy stock orchestrator (bb_reversion, trend_pullback, momentum_breakout, vr_composite)
  - Time: 08:55 (5 min before market open)

- `2-52/5 9-15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_trading.sh start >> /home/deploy/project/kis_unified_sts/logs/stock_trading_watchdog_$(date +\%Y\%m\%d).log 2>&1`
  - Watchdog: re-runs idempotent start during market hours
  - Time: every 5 min from 09:02 to 15:52
  - Install/update: `bash /home/deploy/project/kis_unified_sts/scripts/cron/install_stock_trading_watchdog.sh`
  
- `0 16 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_trading.sh stop`
  - Stops: Stock trading gracefully
  - Time: 16:00 (30 min after market close)

### LLM Analysis

- `0 9 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_intraday.sh`
  - Lightweight stock scoring refresh (keep Redis LLM quality snapshot fresh)
  - Runs: 09:00 (immediately after market open)
  - Note: Script has internal lock to prevent concurrent runs
  
- `0 11 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_intraday.sh`
  - Second intraday refresh
  - Runs: 11:00 (mid-morning)
  
- `0 13 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_intraday.sh`
  - Third intraday refresh
  - Runs: 13:00 (after lunch)
  
- `0 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_intraday.sh`
  - Fourth intraday refresh
  - Runs: 15:00 (late afternoon)

- `30 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_market_close.sh`
  - End-of-day comprehensive trading report
  - Runs: 15:30 (30 min after market close)
  - Sends summary via Telegram with position/trade details

### Capital Tracking

- `40 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/publish_equity_snapshot.sh`
  - Daily equity snapshot for cross-session capital tracking
  - Runs: 15:40 (10 min before RL paper stop)
  - Records equity state to Redis `trading:{asset}:equity_timeline` sorted set
  - Introduced: PR #120 (Phase 3 equity tracking)

### Log Rotation (Optional)

- `0 3 * * 0 find /home/deploy/project/kis_unified_sts/logs -name "*.log" -mtime +7 -exec gzip {} \;`
  - Gzip logs older than 7 days
  - Runs: 03:00 Sunday
  
- `0 4 * * 0 find /home/deploy/project/kis_unified_sts/logs -name "*.log.gz" -mtime +30 -delete`
  - Delete compressed logs older than 30 days
  - Runs: 04:00 Sunday

---

## Schedule Summary

| Time | Command | Service |
|------|---------|---------|
| 08:55 | `rl_paper.sh start` | RL futures paper trading |
| 08:55 | `stock_trading.sh start` | Stock orchestrator |
| 09:02-15:52 | `stock_trading.sh start` | Stock watchdog restart/no-op |
| 09:00 | `llm_intraday.sh` | LLM refresh #1 |
| 11:00 | `llm_intraday.sh` | LLM refresh #2 |
| 13:00 | `llm_intraday.sh` | LLM refresh #3 |
| 15:00 | `llm_intraday.sh` | LLM refresh #4 |
| 15:30 | `llm_market_close.sh` | End-of-day briefing |
| 15:40 | `publish_equity_snapshot.sh` | Daily equity snapshot |
| 15:40 | `rl_paper.sh stop` | Stop RL paper trading |
| 16:00 | `stock_trading.sh stop` | Stop stock trading |
| 03:00 (Sun) | Log gzip | Maintenance |
| 04:00 (Sun) | Log delete | Maintenance |

---

## Manual Registration

### Step 1: Review

Check current crontab (if any):
```bash
crontab -l
```

### Step 2: Edit

Open crontab editor:
```bash
crontab -e
```

### Step 3: Add entries

Copy the required entries above into your crontab. Ensure weekday-only filter (`1-5` = Mon–Fri).

### Step 4: Verify

Confirm entries were saved:
```bash
crontab -l
```

---

## Verification after registration

### Stock Trading

```bash
# Check if stock trading started correctly
tail -50 /home/deploy/project/kis_unified_sts/logs/stock_trading_$(date +%Y%m%d).log

# Expected: "Trading started" and no errors
```

### RL Paper Trading

```bash
# Check if RL paper trading started
tail -50 /home/deploy/project/kis_unified_sts/logs/rl_paper_$(date +%Y%m%d).log

# Expected: "RL paper trading started" or "Matrix profile comparison started"
```

### Equity Snapshot

```bash
# Run manually to test
/home/deploy/project/kis_unified_sts/scripts/cron/publish_equity_snapshot.sh

# Check log
tail -20 /home/deploy/project/kis_unified_sts/logs/equity_snapshot_$(date +%Y%m%d).log

# Expected: "Published ... equity snapshot" lines for stock + futures (2 total)
```

### LLM Briefing

```bash
# Check market close output
tail -100 /home/deploy/project/kis_unified_sts/logs/llm_market_close_$(date +%Y%m%d).log

# Expected: Market close briefing completion message with no errors
```

---

## Troubleshooting

### Service fails to start

- Check `.env` file exists and has required variables (`REDIS_*`, `KIS_*`, `TELEGRAM_*`)
- Verify `source .venv/bin/activate` succeeds
- Run script manually: `/home/deploy/project/kis_unified_sts/scripts/cron/<script>.sh start`

### Services already running

- Check PID file: `cat /home/deploy/project/kis_unified_sts/pids/<service>.pid`
- Kill stale process: `kill <pid>`
- Remove PID file and retry

### Log file not found

- Check logs directory: `ls -la /home/deploy/project/kis_unified_sts/logs/`
- Ensure directory is writable: `chmod 755 logs/`

### Cron not executing

- Verify `deploy` user is authorized to run cron: `/etc/cron.allow` or no `/etc/cron.deny`
- Check system cron logs: `grep CRON /var/log/syslog | tail -20`
- Verify crontab is set: `crontab -l`

---

## Notes

- **Weekday only**: All entries filter to Monday–Friday (`1-5`) — no weekend trading
- **Market hours**: Korean stock/futures market 09:00–15:30 KST
- **15:40 buffer**: Equity snapshot at 15:40 ensures market is fully closed; RL paper stop same time
- **LLM timing**: Intraday refreshes at 09:00, 11:00, 13:00, 15:00 allow gradual re-scoring without cron collision
- **Redis DB 1**: All services use Redis DB 1 (not DB 0) — critical for isolation
- **Graceful shutdown**: All `*.sh stop` commands allow ~10 seconds for position exit before SIGKILL
