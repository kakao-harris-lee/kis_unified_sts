# Shutdown Troubleshooting Runbook

Operational guide for diagnosing and recovering from shutdown-related position data issues.

## Overview

The KIS Unified Trading Platform implements graceful shutdown with Redis-based position persistence. This runbook helps operators verify position recovery, diagnose shutdown failures, and restore position data when needed.

**Target Audience**: Operations team, SRE, traders managing automated strategies

**Related Documents**:
- Architecture: `docs/architecture/shutdown_safety.md`
- Verification: `docs/VERIFICATION-graceful-shutdown.md`

---

## 1. Quick Health Check

### 1.1 Verify Position Recovery After Restart

**When to use**: After any process restart (planned or unplanned)

```bash
# Check if positions were recovered from Redis
tail -100 logs/trading_*.log | grep -i "position.*recover"

# Expected output:
# [INFO] Recovered 3 positions from Redis (2 stock, 1 futures)
# [INFO] Position recovery: 005930 (Samsung) LONG 100 @ 71000 [MAXIMIZE]
# [INFO] Position recovery: 101S6000 (KOSPI200F) SHORT 2 @ 340.50 [BREAKEVEN]
```

**Green Signal**: Log shows "Recovered N positions" with correct count

**Red Signal**: "No positions to recover" when you expect open positions

---

### 1.2 Compare Redis vs In-Memory Positions

```bash
# Count positions in Redis
redis-cli -n 1 HLEN trading:stock:positions
redis-cli -n 1 HLEN trading:futures:positions

# Check orchestrator dashboard
curl -s http://localhost:8000/api/trading/positions | jq '.positions | length'

# Or using CLI (if available)
sts trade status --asset stock | grep -c "Position:"
```

**Verification**: Redis count should match in-memory count after startup

---

## 2. Redis Position Inspection

### 2.1 List All Positions

**Important**: All trading Redis keys are in **DB 1** (not default DB 0)

```bash
# Stock positions
redis-cli -n 1 HKEYS trading:stock:positions

# Futures positions
redis-cli -n 1 HKEYS trading:futures:positions

# Output: List of position IDs (UUIDs)
# Example:
# 1) "a3f2e1d0-1234-5678-90ab-cdef12345678"
# 2) "b4f3e2d1-2345-6789-01bc-def123456789"
```

---

### 2.2 Inspect Position Details

```bash
# Get specific position (replace UUID with actual position ID)
redis-cli -n 1 HGET trading:stock:positions "a3f2e1d0-1234-5678-90ab-cdef12345678" | jq .

# Get all positions with details
redis-cli -n 1 HGETALL trading:stock:positions | \
  awk 'NR%2==0' | \
  while read line; do echo "$line" | jq -c '{code: .code, side: .side, qty: .quantity, state: .state, strategy: .strategy}'; done
```

**Critical Fields to Verify**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | UUID | Position identifier | `"a3f2e1d0-..."` |
| `code` | String | Symbol code | `"005930"` |
| `name` | String | Symbol name | `"삼성전자"` |
| `side` | Enum | Position direction | `"LONG"` or `"SHORT"` |
| `quantity` | Int | Position size | `100` |
| `entry_price` | Float | Entry price | `71000.0` |
| `current_price` | Float | Last price | `72500.0` |
| `state` | Enum | Position state | `"SURVIVAL"`, `"BREAKEVEN"`, `"MAXIMIZE"` |
| `strategy` | String | Originating strategy | `"bb_reversion"`, `"rl_mppo"` |
| `entry_time` | ISO8601 | Entry timestamp | `"2026-03-05T09:15:30+09:00"` |
| `highest_price` | Float | Tracking high | `73000.0` |
| `lowest_price` | Float | Tracking low | `70500.0` |

---

### 2.3 Check Position Freshness

```bash
# Get position entry times
redis-cli -n 1 HGETALL trading:stock:positions | \
  awk 'NR%2==0' | \
  jq -r '.code + " | " + .entry_time + " | " + .strategy'

# Example output:
# 005930 | 2026-03-05T09:15:30+09:00 | bb_reversion
# 000660 | 2026-03-05T10:22:15+09:00 | opening_volume_surge
```

**Freshness Rules** (from `orchestrator.py:1122-1218`):

- **Swing Strategies** (`bb_reversion`, `opening_volume_surge`, `volume_accumulation`): Recover up to 7 days old
- **Intraday Strategies** (`rl_mppo`): Recover same-day only
- Stale positions are automatically removed from Redis with logging

---

## 3. Log Analysis for Shutdown Events

### 3.1 Log File Locations

```bash
# Trading orchestrator logs
logs/trading_stock_*.log      # Stock trading
logs/trading_futures_*.log    # Futures trading
logs/rl_paper_*.log           # RL paper trading

# Cron script logs (if using cron-based execution)
logs/cron_stock_trading.log
logs/cron_rl_paper.log

# System logs (for signal handling)
journalctl -u trading-stock.service -n 100      # If using systemd
docker logs kis-trading-stock                   # If using Docker
```

---

### 3.2 Grep Patterns for Shutdown Events

```bash
# 1. Signal reception
grep -i "shutdown signal received" logs/trading_*.log

# Expected: "Shutdown signal received, stopping gracefully..."

# 2. Orchestrator stop sequence
grep -i "stopping.*orchestrator\|orchestrator.*stop" logs/trading_*.log

# Expected: "Stopping orchestrator (timeout=4.0s)..."

# 3. Redis flush on shutdown
grep -i "flush.*position\|position.*flush.*redis" logs/trading_*.log

# Expected: "Flushing positions to Redis before shutdown (attempt 1/3)"

# 4. Position state transitions (immediate flush trigger)
grep -i "position state.*→" logs/trading_*.log

# Expected: "Position state: 005930 SURVIVAL → BREAKEVEN"

# 5. Shutdown completion
grep -i "shutdown complete\|stopped successfully" logs/trading_*.log

# Expected: "Orchestrator stopped successfully"
```

---

### 3.3 Identify Shutdown Failures

**Symptoms of Failed Graceful Shutdown**:

```bash
# Check for timeout messages
grep -i "shutdown timeout\|force.*flush" logs/trading_*.log

# Check for Redis connection errors during shutdown
grep -i "redis.*error\|connection.*failed" logs/trading_*.log | grep -A 5 -B 5 "shutdown"

# Check for SIGKILL (process killed before graceful shutdown)
grep -i "killed\|sigkill\|terminated" logs/trading_*.log
```

**Red Flags**:
- `"Shutdown timeout exceeded, forcing Redis flush"` → Orchestrator took >4 seconds
- `"Redis flush failed after 3 retries"` → Persistent Redis connection issue
- No shutdown completion message → Process was SIGKILL'd

---

## 4. Recovery Procedures

### 4.1 Scenario: Positions Missing After Restart

**Cause**: Redis flush failed during shutdown or positions were stale

**Recovery Steps**:

1. **Check Redis for stale positions**:
   ```bash
   # Inspect all position entry times
   redis-cli -n 1 HGETALL trading:stock:positions | \
     awk 'NR%2==0' | jq -r '.code + " | " + .entry_time'
   ```

2. **Manually verify with broker** (KIS API):
   ```bash
   # Get current broker positions
   sts trade broker-positions --asset stock

   # Compare with expected positions from last session
   ```

3. **Restore from ClickHouse trade history** (if available):
   ```bash
   # Query recent open positions (not yet closed)
   clickhouse-client --query "
   SELECT
     code, name, side, quantity, entry_price, entry_time, strategy
   FROM kospi.stock_trades
   WHERE asset_class = 'stock'
     AND exit_time IS NULL
     AND entry_time >= today() - INTERVAL 7 DAY
   ORDER BY entry_time DESC
   FORMAT PrettyCompact
   "
   ```

4. **Manually reconstruct positions** (last resort):
   ```bash
   # Use PositionTracker.add_position_recovered() via Python shell
   python3 -c "
   from services.trading.position_tracker import PositionTracker
   from shared.models.position import PositionSide, PositionState
   from datetime import datetime
   import redis

   tracker = PositionTracker()

   # Reconstruct position
   position = tracker.add_position_recovered(
       id='a3f2e1d0-1234-5678-90ab-cdef12345678',
       code='005930',
       name='삼성전자',
       side=PositionSide.LONG,
       quantity=100,
       entry_price=71000.0,
       entry_time=datetime.fromisoformat('2026-03-05T09:15:30+09:00'),
       state=PositionState.MAXIMIZE,
       strategy='bb_reversion'
   )

   # Save to Redis
   from shared.streaming.trading_state import TradingStatePublisher
   publisher = TradingStatePublisher('stock')
   publisher.publish_positions_update([position], throttle=0)
   print(f'Position {position.code} restored to Redis')
   "
   ```

---

### 4.2 Scenario: Redis Connection Failed During Shutdown

**Symptoms**:
- Logs show `"Redis flush failed after 3 retries"`
- Positions exist in memory but not in Redis

**Recovery Steps**:

1. **Check Redis health**:
   ```bash
   redis-cli -n 1 PING
   # Expected: PONG

   # Check Redis logs
   tail -50 /var/log/redis/redis-server.log
   ```

2. **Verify Redis DB 1 is accessible**:
   ```bash
   redis-cli -n 1 INFO keyspace
   # Expected: db1:keys=...
   ```

3. **Restart Redis if needed**:
   ```bash
   sudo systemctl restart redis
   # or
   docker restart kis-redis
   ```

4. **Force position flush** (if orchestrator is still running):
   ```bash
   # Send SIGHUP to trigger manual flush (if implemented)
   # Or restart orchestrator gracefully
   sts trade stop --asset stock
   ```

---

### 4.3 Scenario: State Transition Not Persisted

**Symptoms**:
- Position shows `SURVIVAL` in Redis but was `BREAKEVEN` before shutdown
- Logs show state transition but no immediate flush

**Root Cause**: Orchestrator was killed between state update and Redis flush

**Prevention**: Immediate flush on state transitions (already implemented)

**Recovery**:

1. **Verify current broker position**:
   ```bash
   sts trade broker-positions --asset stock --symbol 005930
   ```

2. **Manually update Redis state** (if state is known):
   ```bash
   # Get current position JSON
   POSITION=$(redis-cli -n 1 HGET trading:stock:positions "a3f2e1d0-1234-5678-90ab-cdef12345678")

   # Update state field
   echo "$POSITION" | jq '.state = "BREAKEVEN"' | \
     redis-cli -n 1 HSET trading:stock:positions "a3f2e1d0-1234-5678-90ab-cdef12345678"
   ```

3. **Restart orchestrator to reload**:
   ```bash
   sts trade start --asset stock --daemon
   ```

---

### 4.4 Scenario: Shutdown Timeout (>4 seconds)

**Symptoms**:
- Logs show `"Shutdown timeout exceeded, forcing Redis flush"`
- Cron script sends SIGKILL before graceful shutdown completes

**Diagnosis**:

```bash
# Check shutdown duration in logs
grep -i "stopping orchestrator" logs/trading_*.log
grep -i "shutdown complete" logs/trading_*.log

# Calculate time difference (manual check)
```

**Timeout Budget** (from `orchestrator.py:2293-2350`):
- Market data stop: ~0.5s
- Position close attempts: ~1.5s
- Redis flush (with 3 retries): ~0.8s
- Cache save: ~0.3s
- Cleanup: ~0.2s
- Status publish: ~0.2s
- Notifications: ~0.5s
- **Total**: ~4.0s (1s safety margin before cron SIGKILL at 5s)

**Recovery**:

1. **If shutdown consistently exceeds 4s**:
   - Check for slow WebSocket disconnections
   - Check for Redis latency
   - Consider increasing cron timeout to 10s (edit `scripts/cron/*.sh`)

2. **Force flush verification**:
   ```bash
   # Verify force flush was executed
   grep -i "force.*flush\|last resort" logs/trading_*.log

   # Verify positions were still saved
   redis-cli -n 1 HLEN trading:stock:positions
   ```

---

## 5. Preventive Monitoring

### 5.1 Pre-Shutdown Checklist

**Before planned restarts** (upgrades, config changes):

```bash
# 1. Verify position count
sts trade status --asset stock | grep "Open positions:"

# 2. Verify Redis is healthy
redis-cli -n 1 PING

# 3. Verify all positions are in Redis
redis-cli -n 1 HLEN trading:stock:positions

# 4. Export positions as backup
redis-cli -n 1 HGETALL trading:stock:positions > /tmp/positions_backup_$(date +%Y%m%d_%H%M%S).json

# 5. Initiate graceful shutdown
sts trade stop --asset stock
# OR send SIGTERM
kill -TERM $(pgrep -f "sts trade start")

# 6. Wait for completion (max 5 seconds)
sleep 5

# 7. Verify clean shutdown
tail -20 logs/trading_*.log | grep -i "shutdown complete"
```

---

### 5.2 Automated Health Checks

**Cron job for position consistency check** (run every 5 minutes during trading):

```bash
#!/bin/bash
# /etc/cron.d/trading_health_check.sh

REDIS_COUNT=$(redis-cli -n 1 HLEN trading:stock:positions)
API_COUNT=$(curl -s http://localhost:8000/api/trading/positions | jq '.positions | length')

if [ "$REDIS_COUNT" -ne "$API_COUNT" ]; then
  echo "❌ Position mismatch: Redis=$REDIS_COUNT API=$API_COUNT" | \
    tee -a /var/log/trading_health.log

  # Send Telegram alert
  curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    -d "text=⚠️ Position mismatch detected: Redis=$REDIS_COUNT API=$API_COUNT"
else
  echo "✅ Position consistency OK: $REDIS_COUNT positions" >> /var/log/trading_health.log
fi
```

---

### 5.3 Prometheus Alerts

**Recommended Grafana alerts**:

```yaml
# Position persistence lag
- alert: PositionPersistenceLag
  expr: trading_redis_flush_errors_total > 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Redis flush failures detected"
    description: "{{ $value }} Redis flush errors in the last minute"

# Shutdown duration
- alert: ShutdownTimeout
  expr: trading_shutdown_duration_seconds > 3.5
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "Shutdown taking too long"
    description: "Shutdown duration {{ $value }}s exceeds 3.5s threshold"

# Position recovery failures
- alert: PositionRecoveryFailure
  expr: increase(trading_position_recovery_errors_total[5m]) > 0
  labels:
    severity: critical
  annotations:
    summary: "Position recovery failed on restart"
```

---

## 6. Common Issues & Solutions

### Issue 1: "No positions to recover" but positions were open

**Diagnosis**:
```bash
# Check if positions were auto-removed as stale
grep -i "stale position.*removed" logs/trading_*.log

# Check Redis directly
redis-cli -n 1 HGETALL trading:stock:positions
```

**Solutions**:
- **Intraday positions**: Only recovered if entry_time is today. Old positions are intentionally discarded.
- **Swing positions**: Recovered if <7 days old. Check entry_time.
- **Redis cleared**: Restore from ClickHouse trade history (see Section 4.1 step 3)

---

### Issue 2: Position state reverted after restart

**Cause**: State transition occurred but Redis flush failed before shutdown

**Verification**:
```bash
# Check for state transition logs followed by shutdown
grep -i "position state.*→" logs/trading_*.log | tail -5
grep -i "shutdown signal" logs/trading_*.log | tail -1
```

**Solution**: Manually update Redis state (see Section 4.3)

---

### Issue 3: Duplicate positions after recovery

**Cause**: Position was both in Redis and re-entered after restart

**Verification**:
```bash
# Check for duplicate position IDs
redis-cli -n 1 HGETALL trading:stock:positions | \
  awk 'NR%2==0' | jq -r '.code' | sort | uniq -c | awk '$1 > 1'
```

**Solution**:
```bash
# Remove duplicate (keep the one with correct state)
redis-cli -n 1 HDEL trading:stock:positions "duplicate-uuid-here"

# Restart orchestrator
sts trade restart --asset stock
```

---

### Issue 4: Redis DB 0 used instead of DB 1

**Symptoms**: Positions not recovering, but `redis-cli HGETALL trading:stock:positions` shows data

**Cause**: Redis client connected to wrong database

**Verification**:
```bash
# Check default DB (0)
redis-cli HLEN trading:stock:positions
# Should be 0 or non-existent

# Check correct DB (1)
redis-cli -n 1 HLEN trading:stock:positions
# Should show position count
```

**Solution**: Always use `-n 1` flag with redis-cli for trading data

---

## 7. Operational Best Practices

### 7.1 Daily Checklist

- [ ] Verify position recovery after overnight cron restart
- [ ] Check Redis position count matches orchestrator count
- [ ] Review shutdown logs for any timeout warnings
- [ ] Export position backup before market open
- [ ] Verify Redis health (latency, memory usage)

### 7.2 Weekly Checklist

- [ ] Review position persistence metrics in Grafana
- [ ] Analyze shutdown duration trends
- [ ] Clean up stale positions in Redis (>7 days for swing)
- [ ] Verify ClickHouse trade history matches Redis positions
- [ ] Test disaster recovery procedure (restore from backup)

### 7.3 Emergency Contacts

| Issue | Contact | Action |
|-------|---------|--------|
| Redis down | SRE on-call | Restart Redis, verify data integrity |
| Orchestrator hung | Trading team | SIGKILL + manual position reconstruction |
| Position data corruption | Lead developer | Restore from ClickHouse, manual verification |
| Broker API mismatch | KIS support | Verify broker positions, sync manually |

---

## 8. Testing Shutdown Safety

### 8.1 Graceful Shutdown Test

```bash
# Start orchestrator
sts trade start --asset stock --daemon

# Wait for positions to open
sleep 60

# Trigger graceful shutdown
kill -TERM $(pgrep -f "sts trade start")

# Verify shutdown completed
tail -f logs/trading_stock_*.log | grep -i "shutdown complete"

# Verify positions persisted
redis-cli -n 1 HLEN trading:stock:positions

# Restart and verify recovery
sts trade start --asset stock --daemon
tail -f logs/trading_stock_*.log | grep -i "recovered.*position"
```

---

### 8.2 SIGKILL Simulation (Worst Case)

```bash
# Start orchestrator
sts trade start --asset stock --daemon

# Wait for positions + state transition
sleep 120

# Force kill (simulates SIGKILL)
kill -9 $(pgrep -f "sts trade start")

# Check Redis (should still have positions from last flush)
redis-cli -n 1 HLEN trading:stock:positions

# Restart and verify recovery
sts trade start --asset stock --daemon
```

**Expected**: Positions recovered up to last state transition (immediate flush)

---

### 8.3 Redis Failure Simulation

```bash
# Start orchestrator
sts trade start --asset stock --daemon

# Block Redis temporarily
sudo iptables -A OUTPUT -p tcp --dport 6379 -j DROP

# Trigger shutdown (should retry 3 times)
kill -TERM $(pgrep -f "sts trade start")

# Check logs for retry attempts
tail -f logs/trading_stock_*.log | grep -i "retry"

# Unblock Redis
sudo iptables -D OUTPUT -p tcp --dport 6379 -j DROP
```

**Expected**: Logs show 3 retry attempts with exponential backoff (100ms, 200ms, 400ms)

---

## 9. Reference

### 9.1 Key Code Locations

| Component | File | Lines | Description |
|-----------|------|-------|-------------|
| Signal handlers | `cli/main.py` | 1368-1402, 2327-2358 | SIGTERM/SIGINT registration |
| Shutdown sequence | `services/trading/orchestrator.py` | 2293-2370 | stop() method with timeout |
| Position recovery | `services/trading/orchestrator.py` | 1122-1218 | _recover_positions_from_redis() |
| Redis flush retry | `services/trading/orchestrator.py` | 2235-2290 | _flush_positions_with_retry() |
| State transition flush | `services/trading/orchestrator.py` | 3160-3180 | Immediate flush on state change |
| Redis keys | `shared/streaming/trading_state.py` | 31 | Key pattern definitions |

---

### 9.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STS_DISABLE_POSITION_RECOVERY` | `false` | Disable position recovery on startup (testing only) |
| `REDIS_HOST` | `localhost` | Redis server host |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_DB` | `1` | Redis database number (always 1 for trading) |
| `REDIS_PASSWORD` | _(none)_ | Redis authentication password |

---

### 9.3 Redis Key Schema

```
trading:{asset}:positions      # HASH   - Open positions
  field: {position_id}         #   UUID string
  value: {position_json}       #   JSON with all position fields

trading:{asset}:accumulation   # ZSET   - Accumulation candidates (score=timestamp)
trading:{asset}:dips           # HASH   - Dip candidates
trading:{asset}:daily          # HASH   - Daily indicators
```

---

## 10. Troubleshooting Decision Tree

```
Position missing after restart?
│
├─ YES → Check Redis
│   │
│   ├─ Position in Redis? → NO → Check logs for flush failure
│   │                           → Restore from ClickHouse (4.1)
│   │
│   └─ Position in Redis? → YES → Check entry_time
│       │
│       ├─ Stale (>7 days for swing, >1 day for intraday)?
│       │   → YES → Position auto-removed (expected)
│       │   → NO  → Check broker positions (4.1)
│       │
│       └─ Orchestrator not loading?
│           → Check STS_DISABLE_POSITION_RECOVERY env var
│           → Check recovery logs for errors
│
└─ NO → Position state incorrect?
    │
    ├─ State reverted? → Check state transition logs (4.3)
    │                  → Manually update Redis
    │
    └─ Duplicate positions? → Remove duplicate from Redis (Issue 3)
                             → Restart orchestrator
```

---

## Support

For issues not covered in this runbook:

1. Check `docs/architecture/shutdown_safety.md` for design details
2. Review integration tests: `tests/integration/test_graceful_shutdown.py`
3. Contact: trading-platform-team@company.com
4. Emergency: SRE on-call (PagerDuty)

**Last Updated**: 2026-03-05
**Maintainer**: Trading Platform Team
