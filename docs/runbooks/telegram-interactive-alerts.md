# Runbook: Telegram Interactive Alerts

Operate the inbound Telegram bot that adds **signal approve/reject** and
**position close** buttons on top of the existing outbound alerts, plus concise
message formatting and Naver Finance links on stock alerts.

This feature is **inert by default** (`enabled: false`). Nothing in this runbook
changes trading behavior until an operator explicitly opts in per the Rollout
section below. Money-moving surface — read the whole runbook before enabling.

Design: `docs/plans/2026-07-07-telegram-interactive-alerts-design.md`

## What it is

- New `services/telegram_bot` — a single `python-telegram-bot` `Application` in
  **long-polling** mode. Inbound-only: it receives button taps / commands. No
  webhook, no public URL, no Caddy route, no host port. Works behind the
  firewall on the paper server as-is.
- **Approval gate** lives in `risk_filter` / `stock_risk_filter`, right before
  the `signal.final.{asset}` XADD. Only signals whose strategy/symbol match the
  configured lists are held; everything else flows automatically, unchanged.
- On **approve**, the bot replays the stored signal to `signal.final.{asset}`
  (Method A — the bot owns the final XADD). On **reject/expiry**, nothing fires.
- On **close** (`/positions` → 청산), the bot XADDs an `intent=close` message;
  the existing order router closes via its normal execution path (wallet
  authority stays in the router; the bot never calls a broker directly).

## Components and config

| Piece | Location |
|---|---|
| Bot service | `services/telegram_bot/` (compose service `telegram_bot`, profile `telegram-bot`) |
| Config | `config/telegram_bot.yaml` — `telegram_bot:` + `approval_gate:` sections |
| Gate helper | `shared/streaming/approval_gate.py` (`is_gated`, `record_pending`, `log_gate_config`) |
| Redis keys | pending HASH `signal:pending_approval:{asset}` (24h TTL); pub/sub `trading:events:approval` |
| Formatting | `shared/notification/formatting.py`; live path `services/stock_monitor/alerts.py::AlertSink.on_exit` |

`config/telegram_bot.yaml`:

```yaml
telegram_bot:
  enabled: false
  allowed_chat_ids: ["${TELEGRAM_STOCK_CHAT_ID}", "${TELEGRAM_FUTURES_CHAT_ID}"]
  poll_interval_seconds: 2
approval_gate:
  enabled: false
  gated_strategies: []   # futures: Signal.setup_type e.g. ["A_gap_reversion","C_event_reaction"]
                         # stock:  signal.strategy   e.g. ["bb_reversion","opening_volume_surge"]
  gated_symbols: []
  pending_ttl_seconds: 86400
```

## Non-obvious operational facts

- **Bot token / channel**: the bot listens on the **stock** domain token
  (`TELEGRAM_STOCK_BOT_TOKEN` / `TELEGRAM_STOCK_CHAT_ID`), but `/positions` and
  close cover **both** stock and futures. Set that token and include both stock
  and futures chat_ids in the whitelist.
- **Whitelist is fail-closed**: an unset/unresolved chat_id env var drops that
  entry from the whitelist (it never becomes a wildcard match). If the bot
  ignores your taps, check the chat_id is in `allowed_chat_ids`.
- **Stream mode must match the pipeline**: the bot's compose service forwards
  `STOCK_RISK_FILTER`/`FUTURES_RISK_FILTER` (via `STOCK_PIPELINE_MODE`/
  `FUTURES_PIPELINE_MODE`) so approve/close XADDs land on the SAME
  `signal.final.{asset}[.shadow]` stream the order routers consume. If you run
  the bot with a different mode than the pipeline, approvals go to the wrong
  stream and silently vanish. Keep the modes identical.
- **Gate strategy names are runtime identifiers**, not YAML file names — futures
  uses `Signal.setup_type` (`A_gap_reversion`, not `setup_a_gap_reversion`),
  stock uses `signal.strategy` (`bb_reversion`). On startup, `log_gate_config`
  logs the gated lists — eyeball that line to confirm your entries are the real
  identifiers. Matching is case-insensitive.
- **Entry alerts stay silent** by policy (spec §7 — no per-fill entry alerts);
  the concise formatter + Naver link attach to the **exit** alert path.
- Doubly gated: even with the `telegram-bot` profile up, `enabled: false` keeps
  the bot inert. Both must be flipped to activate.

## Rollout (paper server)

Validate on the 모의투자 (paper) server, not locally.

### Gate 0 — Prerequisites
- `TELEGRAM_STOCK_BOT_TOKEN` / `TELEGRAM_STOCK_CHAT_ID` set; futures chat_id too
  if you want futures `/positions`.
- Decoupled pipeline running (stock and/or futures), Redis DB 1 reachable.

### Gate 1 — Bot only, zero order impact
- Set `telegram_bot.enabled: true`, keep `approval_gate.enabled: false`.
- Start: `docker compose --env-file .env.paper --profile telegram-bot up -d telegram_bot`
- Verify:
  - `docker compose --env-file .env.paper logs telegram_bot` shows long-polling started, no auth errors.
  - `/help` and `/start` respond.
  - `/positions` lists current holdings with a 청산 button per position.
  - A tap from a non-whitelisted chat is ignored (logged as a warning).
- This gate places **no orders** — approve/close only act once the gate holds signals.

### Gate 2 — Gate one strategy on paper
- Set `approval_gate.enabled: true` and add ONE strategy to `gated_strategies`
  (use the real runtime identifier; confirm via the startup `log_gate_config` line).
- Restart the relevant risk-filter service and the bot.
- Verify:
  - A matching signal produces an approve/reject message (not an automatic order).
  - `/pending` lists it.
  - **Approve** → order appears on `signal.final.{asset}[.shadow]` and the order
    router acts; message edits to 승인됨.
  - **Reject** → no order; message edits to 거부됨.
  - Non-gated strategies still flow automatically (unchanged).

### Gate 3 — Close flow
- From `/positions`, tap 청산 on a paper position → order router closes it via
  the normal path; futures preserves long/short direction. Confirm the position
  clears from the positions hash / dashboard.

### Gate 4 — Live (only if desired)
- Live orders remain guarded by the existing `config/futures_live.yaml` +
  `futures:live:suspended` machinery. Passing the paper gates does not bypass it.

## Rollback

- Disable interaction with zero code change: set `approval_gate.enabled: false`
  (signals resume automatic flow) and/or `telegram_bot.enabled: false`, restart.
- Or stop the container: `docker compose --env-file .env.paper stop telegram_bot`.
- Pending approvals live in Redis (`signal:pending_approval:{asset}`, 24h TTL);
  a bot restart does not lose them. To clear manually:
  `docker compose --env-file .env.paper exec -T redis redis-cli -n 1 DEL signal:pending_approval:stock signal:pending_approval:futures`

## Quick checks

```bash
# bot up?
docker compose --env-file .env.paper ps telegram_bot
# gated lists actually loaded (startup log)?
docker compose --env-file .env.paper logs stock-risk-filter | grep approval_gate
# pending approvals right now?
docker compose --env-file .env.paper exec -T redis redis-cli -n 1 HGETALL signal:pending_approval:stock
```
