# Futures Monitor Daemon (F-5) — Design

**Status:** Approved (design) — 2026-06-07
**Scope unit:** F-5 of the futures-decoupling roadmap (Phase B, after F-6). Depends on F-1 (stream naming, shadow risk-state) and F-6 (exit fills exist). Mirrors the stock monitor (`services/stock_monitor/`).

---

## 1. Problem

The decoupled futures chain now enters AND exits (F-6), emitting `order.fill.futures[.shadow]` (entry + stop_loss/take_profit/force_close) and `signal.final.futures[.shadow]`. But there is **no dashboard/observability bridge** for the decoupled chain — futures dashboard state (`trading:futures:*`) is published only by the in-process orchestrator. Without a monitor, a shadow futures run is invisible: no positions/trades/signals on the Cockpit, no alerts. The stock chain solved this with `services/stock_monitor/` (M5a); futures has no equivalent.

## 2. Goal

A shadow-first `services/futures_monitor/` that consumes the decoupled futures streams and republishes dashboard-native state (`trading:futures:*[:shadow]`) + Telegram alerts, mirroring the stock monitor. Per operator decision, a **full mirror** (dashboard bridge + Telegram AlertSink + session digest + health) with a **monitor-owned futures positions hash** for restart recovery.

- **off** (default): inert.
- **shadow** (`FUTURES_MONITOR_DAEMON=shadow`): keys → `trading:futures:*:shadow`; Telegram suppressed-to-log; consumes `*.futures.shadow` streams.
- **live**: unsuffixed keys; real futures Telegram; consumes unsuffixed streams. (Phase-5-gated; delivered DISABLED. At the eventual cutover the decoupled monitor replaces the orchestrator as the futures alerter, mirroring stock M5e.)

## 3. Approach (decided)

1. **Full mirror** of stock_monitor structure, adapted for futures. **Reuse** (import, don't copy) the asset-agnostic pieces: `AlertSink`/`SessionDigest` (`services.stock_monitor.alerts`), `TradingStatePublisher`, `StreamConsumerFeed`, `notifier_for_domain("futures")`, contract-spec helpers.
2. **Futures-specific** new code: serializers (futures signal schema, side+multiplier `build_*`), a `calc_futures_realized_pnl` helper, a `futures_monitor/positions.py` codec, and `FuturesMonitorDaemon`.
3. **Monitor-owned positions hash** `futures:monitor:positions` (the decoupled chain has none): HSET on entry, update high/low on MTM, HDEL on exit, recover on startup.
4. **PnL parity (critical):** the monitor's PnL must equal `PseudoOCO._record_pnl` exactly — `(exit−entry)·sign·qty·multiplier`, sign +1 long / −1 short, **no fee** — so the dashboard PnL matches the risk-state writer (F-6). The monitor does **not** write risk state (PseudoOCO already does); it computes PnL independently only for display/alerts.

## 4. Design

### 4.1 File list

```
services/futures_monitor/__init__.py
services/futures_monitor/serializers.py   # parse_fill, parse_final_signal (futures schema),
                                          #   build_position_dict/trade_dict/signal_dict (side+multiplier)
services/futures_monitor/positions.py     # parse_futures_position_record + record builder
services/futures_monitor/daemon.py        # FuturesMonitorDaemon
services/futures_monitor/main.py          # FUTURES_MONITOR_DAEMON entrypoint
config/futures_monitor.yaml               # futures_monitor.telegram.{...}
deploy/systemd/kis-futures-monitor-daemon.service   # mirror stock unit, delivered DISABLED
tests/unit/futures_monitor/{__init__,test_serializers,test_positions,test_daemon,test_entrypoint}.py
shared/utils/calc.py                      # + calc_futures_realized_pnl
```
Reused via import: `AlertSink`/`SessionDigest`, `TradingStatePublisher`, `StreamConsumerFeed`, `notifier_for_domain`, `ContractSpecRegistry`/`resolve_contract_spec`/`get_front_month_code`.

### 4.2 Streams + modes + shadow isolation (mirror stock main.py)

- `_resolve_mode()` → `FUTURES_MONITOR_DAEMON` (default `off`).
- `_streams_for(mode)` → shadow: `("order.fill.futures.shadow", "signal.final.futures.shadow")`; else `("order.fill.futures", "signal.final.futures")`. Env-overridable: `FUTURES_FILL_STREAM`/`FUTURES_FINAL_STREAM`.
- `_ensure_shadow_isolation(mode)` → shadow sets `TRADING_STATE_KEY_SUFFIX=shadow` (if unset); live clears it. Identical fail-safe to stock.
- off → log + `aclose` + return 0 (inert).
- Tick feed: `StreamConsumerFeed(redis, stream=os.environ.get("FUTURES_TICK_STREAM", "raw_data"))` (futures tick stream is `raw_data`).
- Consumer group: `"futures_monitor"`.

### 4.3 Serializers (`services/futures_monitor/serializers.py`)

`_s` + `_ms_to_iso` duplicated (2 trivial pure helpers; keeps futures_monitor self-contained — avoids touching the working stock serializers / cross-service private import).

- `parse_fill(fields)` → `{signal_id, order_id, symbol, side, filled_price, quantity, trade_role, filled_at_ms}` (FillLogger schema; keep `symbol` not aliased to `code`).
- `parse_final_signal(fields)` → futures schema: `{signal_id, symbol, setup_type, direction, entry_price, confidence, generated_at_ms}` (NO name/strategy/code/price — `signal.final.futures` is `Signal.to_stream_dict()`: `setup_type`/`symbol`/`entry_price`/`direction`/...).
- `build_position_dict(fill, meta, *, multiplier)` → dashboard open-position dict; `side` from `fill["side"]`; `unrealized_pnl=0.0` at entry; keys: `id, code(=symbol), name, side, quantity, entry_price, current_price, unrealized_pnl, pnl_pct, entry_time, strategy(=setup_type), state, highest_price, lowest_price, fee_rate(=0.0 or commission_rate), stop_price, client_order_id`.
- `build_trade_dict(entry, exit_fill, *, pnl)` → dashboard closed-trade dict; **side-aware** `pnl_pct` (long: `(xp-ep)/ep*100`; short: `(ep-xp)/ep*100`); `side` from entry; `exit_reason` = the futures `trade_role` (`stop_loss`/`take_profit`/`force_close`); keys: `id, symbol, name, side, quantity, entry_price, exit_price, pnl, pnl_pct, strategy, entry_time, exit_time, exit_reason`.
- `build_signal_dict(sig)` → dashboard signal dict; `side="entry"`/`signal_type="entry"` (mirror stock convention), `strategy=setup_type`, `price=entry_price`, `name=""`; keys: `id, symbol, name, side, signal_type, strategy, price, confidence, timestamp, executed, reason, stage`.

### 4.4 `calc_futures_realized_pnl` (`shared/utils/calc.py`)

```python
def calc_futures_realized_pnl(
    entry_price: float, exit_price: float, quantity: int, side: str,
    *, multiplier_krw_per_point: float,
) -> float:
    """Futures realized PnL in KRW, matching PseudoOCO._record_pnl (no fee).

    sign = +1 long / -1 short → (exit-entry)*sign*qty*multiplier.
    """
    sign = 1.0 if side == "long" else -1.0
    return (exit_price - entry_price) * sign * quantity * multiplier_krw_per_point
```
Parity-tested against the F-6 `PseudoOCO._record_pnl` formula so dashboard PnL == risk-state PnL.

### 4.5 Futures positions hash (`services/futures_monitor/positions.py`)

- **Key:** `futures:monitor:positions` (HASH, field=symbol), env `FUTURES_MONITOR_POSITIONS_KEY`. The monitor's private working store — disjoint from the orchestrator's `trading:futures:positions` and from `risk:state:futures*`.
- **Record (JSON):** `{symbol, side, entry_price, quantity, opened_at_ms, setup_type, signal_id, high_water, low_water}`.
- `parse_futures_position_record(value) -> dict | None`: JSON-decode; return None unless it has both `opened_at_ms` and `symbol` (foreign-skip guard, mirrors stock's `parse_position_record`).
- `build_position_record(open_state) -> str`: JSON-encode for HSET.

### 4.6 `FuturesMonitorDaemon` (`services/futures_monitor/daemon.py`)

Mirrors `StockMonitorDaemon` scaffolding (run/stop/_consume_loop/_status_loop/_check_health_and_digest verbatim-equivalent; health/digest KST logic reused as-is). Constructor adds `multiplier: float` and `positions_key: str`; drops stock's `fee_rate` semantics (keep a `commission_rate` for display only if desired, default 0).

- **`handle_signal`** — cache `signal_id → {setup_type, symbol, direction}` (FIFO-bounded), publish `build_signal_dict`.
- **`handle_fill`** —
  - `trade_role == "entry"`: open `_open[symbol]` (side, entry_price, qty, entry_time, high/low watermarks, setup_type, signal_id), **HSET the positions hash**, publish position dict, `await alert_sink.on_entry(...)`.
  - `trade_role in {"stop_loss","take_profit","force_close"}`: pair with `_open.pop(symbol)`; if none → log + `remove_position(symbol)` (orphan exit, e.g. post-restart). Else PnL via `calc_futures_realized_pnl(entry, exit, qty, side, multiplier)`; publish `build_trade_dict(... exit_reason=trade_role)`; `remove_position(symbol)`; **HDEL the positions hash**; `await alert_sink.on_exit(code=symbol, pnl, pnl_pct)`.
  - else: log + drop (unknown role).
- **`recover_open_positions`** — read `futures:monitor:positions`, `parse_futures_position_record` (skip foreign), seed `_open` (incl. side + high/low + setup_type), republish each position.
- **`publish_status_and_mtm`** — for each open position: `get_current_price(symbol)`; update high/low; **side-aware** `unrealized_pnl = (close-ep)*sign*qty*multiplier`; `pnl_pct` side-aware; update the hash's high/low; publish; then publish aggregate status (`open_positions`, `worker_id`, `source="futures_monitor"`).
- **`_check_health_and_digest`** — reused from stock (KST market window, digest reset 09:00, emit at `digest_time_kst`, cooldown-gated staleness health). Market window stays 09:00–15:30 (safe shadow default; futures' 15:45 close is a later refinement).

### 4.7 AlertSink (reuse, futures domain)

`from services.stock_monitor.alerts import AlertSink`. main.py: `notifier = notifier_for_domain("futures") if mode == "live" else None`; `AlertSink(notifier=notifier, mode=mode, pnl_alert_pct=...)`. Shadow → `would-alert` logs (no Telegram); live → futures Telegram channel (`TELEGRAM_FUTURES_*`). The KRW-denominated digest/exit messages are correct for futures.

### 4.8 Entrypoint + config + systemd

- `main.py` mirrors stock main.py with the §4.2 futures deltas + contract-spec resolution (`get_front_month_code(product="mini")` + `resolve_contract_spec` → `multiplier_krw_per_point`, front-month `symbol`; `feed.update_symbols([symbol])`).
- `config/futures_monitor.yaml`: `futures_monitor.telegram.{pnl_alert_pct: 3.0, health_stale_seconds: 600, health_cooldown_seconds: 1800, digest_time_kst: "15:40"}` (mirror stock; `scripts/cron/`-style gitignore does NOT apply — this is `config/`, tracked).
- `deploy/systemd/kis-futures-monitor-daemon.service`: mirror the stock unit, **delivered DISABLED** (no `FUTURES_MONITOR_DAEMON` set → off-inert; operator enables shadow explicitly).

## 5. Data flow

```
SHADOW:
  order.fill.futures.shadow (entry) ─┐
  signal.final.futures.shadow ───────┤→ FuturesMonitorDaemon._consume_loop
                                      │    handle_signal → publish trading:futures:signals:shadow
                                      │    handle_fill(entry) → _open[sym] + HSET futures:monitor:positions
                                      │                       → publish trading:futures:positions:shadow
  order.fill.futures.shadow (exit:   │    handle_fill(stop_loss|take_profit|force_close)
   stop_loss/take_profit/force_close)─┘      → pair _open.pop(sym), PnL=(exit-entry)·sign·qty·mult
                                            → publish trading:futures:trades:shadow + remove_position + HDEL
  _status_loop (every status_interval): MTM each open via raw_data feed → publish positions + status
                                       + health/digest (shadow → would-alert logs)
LIVE: same, unsuffixed keys + real futures Telegram (Phase-5-gated, unit DISABLED).
OFF: inert.
```

## 6. Error handling / safety

- **Collision isolation:** shadow keys `trading:futures:*:shadow` are disjoint from the orchestrator's live `trading:futures:*` (suffix via `_key`); the dashboard reader is suffix-blind → shadow keys invisible to the UI until a cutover. The private `futures:monitor:positions` hash is disjoint from `trading:futures:positions` and `risk:state:futures*`.
- **No double risk-write:** the monitor never writes `risk:state:futures*` — PseudoOCO (F-6) is the sole risk writer; the monitor computes PnL independently for display only (parity formula guarantees agreement).
- **off-inert:** no daemon work without an explicit mode.
- **Poison-pill drop:** handler exceptions logged + message ACKed (mirror stock _consume_loop).
- **Orphan exit (post-restart / pre-recovery):** an exit with no `_open` entry → logged + `remove_position` (no crash).
- **Loop resilience:** status loop per-tick try/except; consume loop backs off on read errors; clean stop cancels both loops + stops the feed.
- **Live Telegram:** `notifier_for_domain("futures")` returns None if creds missing → AlertSink logs instead (no crash).

## 7. Testing

Mirror `tests/unit/stock_monitor/` under `tests/unit/futures_monitor/`:
- **test_serializers.py:** parse_fill (futures fields), parse_final_signal (futures schema), build_position_dict (side from fill, long AND short), build_trade_dict (side-aware pnl_pct long+short, exit_reason=role), build_signal_dict, empty defaults.
- **test_positions.py:** parse_futures_position_record round-trip + foreign-skip (missing opened_at_ms/symbol → None); build_position_record.
- **test_daemon.py:** signal→entry→exit lifecycle with PnL assertion (long: `(exit-entry)*qty*mult`; **short** test: entry short + stop_loss → correct sign + `side=="short"`); exit-without-entry (orphan); recover-from-hash (+ skip-foreign); MTM (side-aware unrealized); hash-write (entry → HEXISTS; exit → HDEL); signal-meta FIFO; off/mode; health/digest KST (injected now_fn).
- **test_entrypoint.py:** `_resolve_mode` default off; `_streams_for` shadow/live; off-inert; shadow-forces-suffix; live-clears-suffix; `config/futures_monitor.yaml` loads.
- **calc:** `calc_futures_realized_pnl` long+short parity (in `tests/unit/...calc` or the serializers test).
- Full CI-parity gate; mypy on changed `shared/` (`calc.py`); ruff/black.

## 8. Out of scope

- Bracket/position durability across an **order_router** restart (PseudoOCO brackets are still in-memory; the monitor's hash only makes the MONITOR restart-durable). Documented limitation.
- Enabling shadow/live (systemd `Environment=` — operator step; unit delivered disabled).
- Dashboard/frontend changes (futures is already a first-class asset in the read path).
- F-4 (MarketContext unification — next), F-8/F-9 cutover.
- Generalizing AlertSink / monitor daemon into a shared base (reuse-by-import suffices; a future refactor could hoist them).

## 9. Risks / open items

- **Coupling `futures_monitor → stock_monitor` (AlertSink import).** Accepted: both are sibling monitor services; AlertSink is asset-agnostic. A future refactor may hoist AlertSink to `shared/`.
- **PnL display vs risk parity.** Guaranteed by the shared `calc_futures_realized_pnl` matching `PseudoOCO._record_pnl` (no fee). If commission is ever added, add it in BOTH or the dashboard diverges from risk state — flagged.
- **Monitor restart vs chain restart.** The hash makes the monitor durable; an order_router restart still orphans in-memory brackets (pre-existing, out of scope). Documented.
- **Market window 09:00–15:30** for health/digest is the stock default; futures night/extended sessions are a later refinement.

## 10. Acceptance criteria

1. `services/futures_monitor/` consumes `order.fill.futures[.shadow]` + `signal.final.futures[.shadow]`, pairs entry→{stop_loss,take_profit,force_close} by symbol, and publishes `trading:futures:*[:shadow]` (positions/trades/signals/status) with side-aware, multiplier-based PnL.
2. PnL matches `PseudoOCO._record_pnl` (parity); long AND short correct.
3. Monitor owns `futures:monitor:positions` (HSET entry / update MTM / HDEL exit) and recovers from it on startup (skips foreign records).
4. Full AlertSink wired (shadow → would-alert logs, live → futures Telegram); off-inert by default; shadow keys never collide with the orchestrator's live keys; monitor never writes risk state.
5. `config/futures_monitor.yaml` + a DISABLED systemd unit added.
6. Tests per §7; full gate green; mypy/ruff/black clean; stock_monitor untouched (reuse-by-import only).
