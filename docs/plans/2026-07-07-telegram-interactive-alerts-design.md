# Telegram Interactive Alerts — Design

- Date: 2026-07-07
- Status: Validated (brainstorming), pending implementation
- Branch: `feat/telegram-interactive-alerts`

## Problem

The current Telegram integration has four user-felt gaps:

1. **Stiff formatting** — every message is a hand-built HTML string with heavy
   emoji and `━━━` dividers; hard to scan, robotic tone.
2. **Alert flood / fragmentation** — signals, fills, warnings arrive as separate
   uncorrelated messages. (Explicitly **out of scope** this round; noted for a
   follow-up.)
3. **No interaction** — the system is outbound-only. There is zero inbound
   surface (no webhook, no polling, no bot commands, no inline buttons).
4. **No context links** — messages never contain a link to check the chart /
   indicators / news for a symbol.

## Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Message tone | Concise / tidy. Deterministic formatter, **no LLM**. |
| Context link | Naver Finance stock page only: `https://finance.naver.com/item/main.naver?code={code}` (stock symbols only). |
| Interaction scope | Signal **approve/reject** + **close holdings**. New entries must go through system signals; closing is free. |
| Inbound transport | **Long polling** (`python-telegram-bot` `Application`). No public URL / TLS / Caddy needed behind the firewall. |
| Authorization | **Allowed `chat_id` whitelist** only. (No re-confirm / expiry this round; live-close re-confirm may be offered later.) |
| Approval gate scope | Only signals whose strategy/symbol match a YAML-configured list are held. Everything else flows automatically, unchanged. |
| Flood cleanup | Out of scope this round. |

## Architecture

New **`services/telegram_bot`** Docker Compose service: a single
`python-telegram-bot` `Application` in long-polling mode. It is **inbound-only**
(receives button clicks / commands). Existing outbound notifications
(`shared/notification/telegram.py`) are unchanged.

Components are decoupled via **Redis DB 1** (project standard). No new direct
service-to-service calls.

```text
[Signal approval flow — Method A]
signal → decision_engine → risk_filter → gate check
   ├─ (not gated) → xadd(signal.final.{asset}) → order_router → OrderExecutor   [UNCHANGED]
   └─ (gated)     → HSET signal:pending_approval:{asset} {approval_id}=<full signal fields + deadline>, EXPIRE 24h
                    → PUBLISH trading:events:approval
                    → return True  (message consumed; risk_filter never blocks)
                         ↓ outbound notify with [승인]/[거부] buttons
                         ↓ user taps [승인]
                    telegram_bot loads pending record → xadd(signal.final.{asset}) → HDEL pending
                    (reject / expiry → HDEL, no order)

[Close flow]
user /positions → telegram_bot reads TradingStateReader(asset).get_positions()
   → per-position [청산] button → tap
   → telegram_bot xadd(signal.final.{asset}, intent=close, ...)
   → order_router / stock_order_router consume intent=close → existing execution path (bypass entry guards)
```

### Why the gate lives in `risk_filter` only

`risk_filter` XADDs to `signal.final.*` right after it passes a signal. That is
the **single chokepoint**: block there and the signal never reaches the final
stream, so the order router never sees it. The order router is downstream and
has no visibility into anything not on `signal.final.*`, so gating there would be
both redundant and incomplete.

- Futures: `services/risk_filter/main.py` — after `if result.passed:` (~L195),
  before `xadd(self.final_stream, ...)` (~L230).
- Stock: `services/stock_risk_filter/main.py` — after pass, before
  `xadd(self.final_stream, ...)` (~L164).

### Method A (chosen): bot owns the final XADD

`risk_filter` only records the pending signal and `return True` (consume). On
approval, **the bot** XADDs the stored signal fields to `signal.final.*`. On
reject/expiry, nothing happens. This keeps the `StreamStage` hot path
non-blocking and gives approve/reject a single clear owner (the bot). Rejected
Method B (risk_filter blocks/polls) — it tangles with XAUTOCLAIM re-delivery.

### Close execution preserves the wallet-authority invariant

The bot does **not** call a broker directly (CLAUDE.md: only the order router
holds wallet authority). It XADDs a `signal.final.{asset}` message with
`intent=close`; the existing order router consumes it and closes via the normal
execution path (futures: market close; stock: `VirtualBroker` SELL + remove from
positions hash). Cost: a small `intent=close` branch added to both order-router
`handle_message`s, bypassing entry guards (closing reduces risk). Rejected
alternative (bot calls `ForceCloseExecutor` directly) — breaks the invariant.

## Data / keys / config

- Pending record: HASH `signal:pending_approval:{asset}`, field = `{asset}:{signal_id}`,
  value = full stream-dict of the signal + approval deadline. `_APPROVAL_TTL_SECONDS = 86400`
  (CLAUDE.md 24h). New module `shared/streaming/approval_keys.py` mirrors
  `stock_keys.py` convention.
- Bot push: `PUBLISH trading:events:approval` mirroring existing
  `trading:events:{positions,signals,fills}`.
- `/positions` read source: `TradingStateReader(asset).get_positions()` (reads
  `trading:{asset}:positions`) — asset-symmetric, already-normalized JSON, matches
  the dashboard.
- Config (`ServiceConfigBase`, `from_yaml()`):

```yaml
telegram_bot:
  enabled: false
  allowed_chat_ids: ["${TELEGRAM_STOCK_CHAT_ID}", "${TELEGRAM_FUTURES_CHAT_ID}"]
  poll_interval_seconds: 2
approval_gate:
  enabled: false
  gated_strategies: []      # e.g. ["setup_a_gap_reversion"]
  gated_symbols: []
  pending_ttl_seconds: 86400
```

## Message format

Before → after (buy fill example):

```text
✅ <b>매수 체결</b>              ✅ 매수 체결 · 삼성전자
종목: 삼성전자 (005930)          005930 · 10주 @ 71,200 (712,000원)
체결가: 71,200원          →      bb_reversion · 10:32
수량: 10주                       [📊 네이버 증권]  (inline button)
금액: 712,000원
전략: bb_reversion
시간: 10:32:14
```

New `shared/notification/formatting.py`: concise formatter + `naver_stock_url(code)`,
`stock_link_button(code)`, `approval_buttons(approval_id)`, `close_button(asset, code)`.

## Files

- New: `services/telegram_bot/{main.py,handlers.py}`
- New: `shared/notification/formatting.py`
- New: `shared/streaming/approval_keys.py`
- New: `config/telegram_bot.yaml` (+ `approval_gate` section)
- Edit: `services/risk_filter/main.py`, `services/stock_risk_filter/main.py` (gate hook)
- Edit: `services/order_router/main.py`, `services/stock_order_router/main.py` (`intent=close`)
- Edit: `docker-compose.yml` (telegram_bot service)

## Testing

- Unit: gate target matching (strategy/symbol), formatter snapshots, whitelist rejection.
- Integration (fakeredis): approve → final XADD flow; `intent=close` order-router branch.
- Hermetic test rules apply (no `.env` injection).

## Rollout

Gate and bot both default `enabled: false`.

1. Enable bot only; verify `/positions`, `/help` (no order impact).
2. On paper, gate one strategy; verify approve/reject.
3. Verify close flow.
4. Pass live gate if/when desired.

Per memory rule: validate scheduled/daemon behavior on the 모의투자 (paper)
server, not local cron.
