# WebSocket Failover Integration Test Documentation

## Overview

This document provides links and guidance for executing the manual integration test for the WebSocket failover with REST fallback feature.

**Feature:** WebSocket Failover with REST Fallback
**Spec ID:** 041-websocket-failover-with-rest-fallback
**Subtask:** subtask-5-3
**Status:** Documentation Complete, Test Execution Pending

## Test Documentation Location

All test documentation is located in the worktree spec directory:

```
.auto-claude/specs/041-websocket-failover-with-rest-fallback/
├── manual_integration_test.md      # Comprehensive test guide (408 lines)
├── run_integration_test.sh         # Automated interactive test script (335 lines)
└── TEST_CHECKLIST.md               # Quick reference checklist (199 lines)
```

## Quick Start

### Option 1: Automated Test Script (Recommended)

```bash
cd /path/to/worktree/041-websocket-failover-with-rest-fallback
source .venv/bin/activate
./.auto-claude/specs/041-websocket-failover-with-rest-fallback/run_integration_test.sh
```

### Option 2: Manual Test with Guide

```bash
# Read the comprehensive guide
cat .auto-claude/specs/041-websocket-failover-with-rest-fallback/manual_integration_test.md

# Execute test scenarios manually following the guide
sts trade start --strategy setup_a_gap_reversion --asset futures --paper
# ... follow guide steps
```

### Option 3: Quick Checklist

```bash
# Print the quick reference checklist
cat .auto-claude/specs/041-websocket-failover-with-rest-fallback/TEST_CHECKLIST.md

# Execute test following the checklist
```

## Test Scenarios

### 1. Normal Operation Baseline
- **Duration:** 2-3 minutes
- **Purpose:** Establish baseline WebSocket behavior
- **Expected:** WebSocket connected, health checks running, data flowing

### 2. WebSocket Disconnection & Failover to REST
- **Duration:** < 10 seconds
- **Purpose:** Verify automatic failover
- **Expected:** Failover completed < 10s, Telegram alert received, REST polling starts

### 3. Continued Operation in REST Fallback Mode
- **Duration:** 2-3 minutes
- **Purpose:** Verify system stability during REST fallback
- **Expected:** Consistent polling, strategies continue, no errors

### 4. WebSocket Recovery & Automatic Reconnection
- **Duration:** < 10 seconds
- **Purpose:** Verify automatic recovery
- **Expected:** Recovery completed < 10s, Telegram alert received, REST polling stops

### 5. Multiple Failover Cycles (Optional)
- **Duration:** 10-15 minutes per cycle
- **Purpose:** Verify robustness
- **Expected:** All cycles successful, no degradation

## Prerequisites

- ✅ Virtual environment activated
- ✅ Redis running (DB 1)
- ✅ ClickHouse running (optional, for historical data)
- ✅ Telegram bot configured
- ✅ KIS API credentials configured
- ✅ Failover enabled in `config/streaming.yaml`

## Acceptance Criteria

All acceptance criteria from the original spec are covered:

| Criterion | Target | Test Coverage |
|-----------|--------|---------------|
| Health monitoring | Detect disconnection < 5s | Scenarios 1-2 |
| Automatic failover | Complete < 10s | Scenario 2 |
| REST polling interval | Configurable (5s default) | Scenario 3 |
| Automatic reconnection | When available | Scenario 4 |
| Telegram alerts | Failover + Recovery | Scenarios 2, 4 |
| Strategy continuity | No interruption | Scenario 3 |

## Metrics to Record

| Metric | Target | Actual |
|--------|--------|--------|
| Failover detection time | < 5 sec | _____ |
| Failover completion time | < 10 sec | _____ |
| Recovery detection time | < 5 sec | _____ |
| Recovery completion time | < 10 sec | _____ |
| Telegram failover alert | Received | _____ |
| Telegram recovery alert | Received | _____ |
| Strategy continuity | No interruption | _____ |
| Data loss | None | _____ |

## Test Execution Status

- **Documentation Created:** 2026-03-09 ✅
- **Test Execution:** PENDING ⏳
- **QA Sign-off:** PENDING ⏳

## Related Tests

- **Unit Tests (WebSocket Health):** `tests/unit/kis/test_websocket_health.py` ✅ PASS (23 tests)
- **Unit Tests (Failover Logic):** `tests/unit/trading/test_data_provider.py -k failover` ✅ PASS (18 tests)

## Notes for Testers

1. **Time Required:** Minimum 10 minutes, recommended 30-40 minutes with optional scenarios
2. **Manual Steps Required:** Yes - monitoring logs, verifying Telegram alerts, triggering disconnection
3. **Automation Available:** Interactive script provides guided execution and automated reporting
4. **Environment:** Paper trading environment (futures RL strategy recommended)

## Troubleshooting

### Common Issues

**Failover not triggering?**
- Check: `grep 'failover:' config/streaming.yaml` → enabled: true?
- Check: WebSocket process actually killed? `ps aux | grep websocket`

**No Telegram alerts?**
- Check: `echo $TELEGRAM_FUTURES_BOT_TOKEN` → set?
- Check: `grep 'send_telegram_alerts' config/streaming.yaml` → true?

**Strategies stopped?**
- Check logs for errors in strategy execution
- Check cache updates during REST mode
- Check signal generation continues

## Support

For questions or issues during test execution:
- Review troubleshooting section in `manual_integration_test.md`
- Check logs: `grep -i "failover\|recovery" logs/paper_trading.log`
- Review build progress: `.auto-claude/specs/041-websocket-failover-with-rest-fallback/build-progress.txt`

---

**Last Updated:** 2026-03-09
**Prepared By:** auto-claude (Claude Sonnet 4.5)
**Status:** Ready for Test Execution
