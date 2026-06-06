# Runbook: Stock Pipeline Cutover (M5d)

Flip stock **paper** trading from the monolithic orchestrator to the decoupled M4
pipeline (M4-P → M4-R → M4-O → M4-X) + M5a monitor + M5b LLM context cron + M5c
daily risk reset cron. Paper→paper (VirtualBroker in both shadow and live; the only
difference is the stream suffix), so there is no real-money risk — the risks are
operational (silent stop, double-trading, no halt). Reversible via the rollback script.

Spec: `docs/superpowers/specs/2026-06-06-stock-stream-cutover-m5d-design.md`

## Gate 0 — Prerequisites
- M4-P/R/O/X + M5a monitor running in SHADOW (`systemctl status kis-stock-*`).
- M5b crontab (`STOCK_LLM_CONTEXT=shadow`) and M5c crontab (`scripts.maintenance.daily_risk_reset`) installed.
- Orchestrator stock running normally (`scripts/cron/stock_trading.sh status` / pid alive).
- Operator has read this runbook AND the rollback section.

## Gate 1 — Shadow validation (>= 3-5 trading days)
Each trading day:
- `python -m scripts.ops.stock_cutover_verify --mode shadow` → PASS (exit 0).
- M5a dashboard (`:shadow` keys) shows decoupled positions / fills / signals flowing.
- No unbounded stream backlog; no daemon crash (`systemctl status kis-stock-*`).
- (Optional) sanity-compare decoupled shadow paper trades vs orchestrator live paper
  trades — directional agreement only (different broker/timing, not an exact match).

## Gate 2 — Operator written approval
Record the date + a one-line shadow-validation summary before proceeding.

## Cutover sequence (run OFF-HOURS — after 16:00 KST or a weekend)
1. **Flatten + clear positions** (current paper data is disposable):
   - `python scripts/trading/flatten_all.py --asset stock`  (optional — close orchestrator positions)
   - `bash scripts/cron/stock_trading.sh stop`
   - Disable the orchestrator cron (comment out the `stock_trading.sh` + watchdog lines in the crontab) so the 5-min watchdog does not resurrect it.
   - `redis-cli -n 1 del stock:daemon:positions trading:stock:positions`  (decoupled working-store + live dashboard snapshot start clean)
2. **Flip M4 daemons to live** (per unit, via systemd drop-in — keeps the repo-tracked unit unmodified):
   ```
   sudo mkdir -p /etc/systemd/system/kis-stock-strategy-daemon.service.d
   printf '[Service]\nEnvironment=STOCK_STRATEGY_DAEMON=live\n' | sudo tee /etc/systemd/system/kis-stock-strategy-daemon.service.d/live.conf
   sudo mkdir -p /etc/systemd/system/kis-stock-risk-filter.service.d
   printf '[Service]\nEnvironment=STOCK_RISK_FILTER=live\nEnvironment=STOCK_POSITIONS_KEY=stock:daemon:positions\n' | sudo tee /etc/systemd/system/kis-stock-risk-filter.service.d/live.conf
   sudo mkdir -p /etc/systemd/system/kis-stock-order-router.service.d
   printf '[Service]\nEnvironment=STOCK_ORDER_ROUTER=live\nEnvironment=STOCK_POSITIONS_KEY=stock:daemon:positions\n' | sudo tee /etc/systemd/system/kis-stock-order-router.service.d/live.conf
   sudo mkdir -p /etc/systemd/system/kis-stock-exit-daemon.service.d
   printf '[Service]\nEnvironment=STOCK_EXIT_DAEMON=live\nEnvironment=STOCK_POSITIONS_KEY=stock:daemon:positions\n' | sudo tee /etc/systemd/system/kis-stock-exit-daemon.service.d/live.conf
   sudo systemctl daemon-reload
   sudo systemctl enable --now kis-stock-strategy-daemon kis-stock-risk-filter kis-stock-order-router kis-stock-exit-daemon
   ```
3. **Flip M5a/b/c to live**:
   - M5a: drop-in `Environment=STOCK_MONITOR_DAEMON=live`, `Environment=STOCK_POSITIONS_KEY=stock:daemon:positions`, and `Environment=TRADING_STATE_KEY_SUFFIX=` for `kis-stock-monitor-daemon`, `daemon-reload`, `systemctl restart kis-stock-monitor-daemon`. The entrypoint also clears any non-empty suffix in live mode as a fail-safe.
   - M5b: change the crontab entry to `STOCK_LLM_CONTEXT=live`; set `config/llm.yaml::market_context_publisher.enabled: false`.
   - M5c: no change (mode-agnostic).
4. **Post-cutover verification**:
   - `python -m scripts.ops.stock_cutover_verify --mode live` → PASS (exit 0).
   - `systemctl is-active kis-stock-strategy-daemon kis-stock-risk-filter kis-stock-order-router kis-stock-exit-daemon kis-stock-monitor-daemon` → all `active`.
   - Watch the first 09:00 KST session on the M5a dashboard (live keys): positions/fills appear.
5. **Permanently block the orchestrator stock path** (M5e): set `STOCK_ORCHESTRATOR_ENABLED=false` in the operator `.env` so `sts trade start --asset stock` (and the stock cron) is refused at the CLI even if accidentally invoked — belt-and-suspenders on top of disabling the cron in step 1.

## Rollback triggers
Roll back if ANY of: `verify --mode live` fails; no fills flowing for >10 min during
market hours while signals are present; a stream backlog grows unbounded; a daemon
crash-loops; M5a emits a health-anomaly Telegram alert.

## Rollback
```
bash scripts/ops/stock_cutover_rollback.sh --dry-run   # preview
bash scripts/ops/stock_cutover_rollback.sh             # execute
```
Then: re-enable `config/llm.yaml::market_context_publisher.enabled: true`, revert the
M5b crontab to `STOCK_LLM_CONTEXT=shadow`, re-enable the orchestrator cron, and confirm
`verify --mode shadow` + orchestrator pid alive.
The rollback script also sets `STOCK_ORCHESTRATOR_ENABLED=true` in `.env` when that
file exists, removes live systemd drop-ins, disables the decoupled units, and clears
`stock:daemon:positions` + the live dashboard positions snapshot.

## Notes
- `stock:daemon:positions` is the M4-R/O/X/monitor recovery working-store. The
  dashboard-native positions key remains `trading:stock:positions[:shadow]` and is
  owned by `TradingStatePublisher`.
- Residual positions in the paper (KIS mock) account from the orchestrator are a
  documented FOLLOW-UP cleanup — out of M5d scope (operator decision: current paper
  data is disposable).
- A decoupled-pipeline kill-switch consumer is deferred; the paper-grade halt is
  `systemctl stop kis-stock-*`.
