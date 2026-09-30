"""Stock monitor / observability bridge daemon (M5a, shadow-first).

Consumes the decoupled stock daemon streams and republishes dashboard-native
state (positions/trades/signals/status) via TradingStatePublisher, plus
important-only alerts. Pairs entry<->exit fills (by code) for closed trades,
correlates final signals (by signal_id) for strategy/name, marks positions to
market, and recovers open state from the daemon positions hash on startup.

The transport — XGROUP CREATE, XREADGROUP, vanished-group recovery, XACK and
the liveness heartbeat — is :class:`shared.streaming.stage.MultiStreamStage`,
not code in this file. What remains here is the stock domain: fill/signal
routing, entry<->exit pairing, fee-rate PnL, and the dashboard aggregates.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime, time
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

from services.stock_exit.positions import parse_position_record
from services.stock_monitor.serializers import (
    _ms_to_iso,
    build_position_dict,
    build_signal_dict,
    build_trade_dict,
    parse_fill,
    parse_final_signal,
)
from shared.streaming.audit import (
    decode_stream_id,
    extract_audit_fields,
    format_audit_kv,
)
from shared.streaming.stage import MultiStreamStage
from shared.utils.calc import calc_realized_pnl

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_CONSUME_ERROR_SLEEP_SECONDS = 0.5
#: Same literals the hand-rolled loop passed to XREADGROUP before the migration.
_XREAD_BLOCK_MS = 2000
_BATCH_SIZE = 50
#: Pending-entry reclaim (XAUTOCLAIM) stays off, which is what this daemon did
#: before the migration and what it must keep doing. A monitor's handlers are
#: not idempotent in the way redelivery needs: a redelivered entry fill fires
#: ``alert_sink.on_entry`` a second time and resets the high/low watermarks to
#: the entry price, discarding the progress the position has made. Turning
#: reclaim on is a deliberate behaviour change with its own evidence, not a
#: side effect of moving onto the shared stage.
_PENDING_RETRY_DISABLED_MS = -1


class StockMonitorDaemon(MultiStreamStage):
    """Bridge daemon: daemon streams -> dashboard keys + alerts."""

    def __init__(
        self,
        *,
        redis: Any,
        feed: Any,
        publisher: Any,
        alert_sink: Any | None,
        positions_key: str,
        fill_stream: str,
        signal_stream: str,
        consumer_group: str,
        worker_id: str,
        fee_rate: float,
        status_interval: float,
        signal_meta_max: int = 1000,
        now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
        health_stale_seconds: float = 600.0,
        health_cooldown_seconds: float = 1800.0,
        digest_time_kst: str = "15:40",
        status_clock: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(
            redis=redis,
            input_streams=[fill_stream, signal_stream],
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=_XREAD_BLOCK_MS,
            batch_size=_BATCH_SIZE,
            xreadgroup_error_sleep_seconds=_CONSUME_ERROR_SLEEP_SECONDS,
            pending_retry_idle_ms=_PENDING_RETRY_DISABLED_MS,
        )
        self.feed = feed
        self.publisher = publisher
        self.alert_sink = alert_sink
        self.positions_key = positions_key
        self.fill_stream = fill_stream
        self.signal_stream = signal_stream
        self.fee_rate = fee_rate
        self.status_interval = status_interval
        self.signal_meta_max = signal_meta_max
        self.now_fn = now_fn
        self.health_stale_seconds = health_stale_seconds
        self.health_cooldown_seconds = health_cooldown_seconds
        self.digest_time_kst = digest_time_kst
        self._open: dict[str, dict[str, Any]] = {}
        self._signal_meta: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._last_health_alert_ts: float = 0.0
        self._digest_emitted_date: str = ""
        self._digest_reset_date: str = ""
        # Monotonic, and separate from ``now_fn``: this paces a cadence, while
        # ``now_fn`` answers "what KST time is it" for the digest/health windows.
        self._status_clock = status_clock or monotonic
        self._last_status_at: float | None = None

    # -- handlers --------------------------------------------------------- #

    async def handle_signal(self, fields: dict[bytes, bytes]) -> None:
        """Correlate a final-signal record and publish it to the dashboard.

        Caches ``signal_id -> {strategy, name, code}`` (FIFO-bounded by
        ``signal_meta_max``) so a later entry fill can enrich its position, and
        publishes the signal via ``publisher.publish_raw_signal``.
        """
        sig = parse_final_signal(fields)
        self._signal_meta[sig["signal_id"]] = {
            "strategy": sig["strategy"],
            "name": sig["name"],
            "code": sig["code"],
        }
        while len(self._signal_meta) > self.signal_meta_max:
            self._signal_meta.popitem(last=False)
        self.publisher.publish_raw_signal(build_signal_dict(sig))

    async def handle_fill(self, fields: dict[bytes, bytes]) -> None:
        """Dispatch a fill to entry/exit handling.

        Entry: opens ``_open[code]`` and publishes the position (enriched with
        cached signal meta). Exit: pairs with the open entry by ``code``,
        publishes the closed trade + realized PnL and removes the position.
        Orphaned exits and unknown ``trade_role`` values are logged and dropped.
        Fires entry/exit alerts when an ``alert_sink`` is configured.
        """
        fill = parse_fill(fields)
        code = fill["code"]
        if fill["trade_role"] == "entry":
            meta = self._signal_meta.get(fill["signal_id"], {})
            pos_dict = build_position_dict(fill, meta, fee_rate=self.fee_rate)
            self.publisher.publish_raw_position(code, pos_dict)
            entry_price = fill["filled_price"]
            self._open[code] = {
                "code": code,
                "name": meta.get("name", ""),
                "strategy": meta.get("strategy", ""),
                "entry_price": entry_price,
                "quantity": fill["quantity"],
                "entry_time": pos_dict["entry_time"],
                "highest_price": entry_price,
                "lowest_price": entry_price,
            }
            if self.alert_sink is not None:
                await self.alert_sink.on_entry(
                    code=code,
                    strategy=meta.get("strategy", ""),
                    quantity=fill["quantity"],
                    price=entry_price,
                )
        elif fill["trade_role"] == "exit":
            entry = self._open.pop(code, None)
            if entry is None:
                logger.warning(
                    "exit fill for %s with no open entry; skipping trade", code
                )
                self.publisher.remove_position(code)
                return
            ep, xp, qty = entry["entry_price"], fill["filled_price"], fill["quantity"]
            # matches M4-X exit pnl (services/stock_exit/daemon.py) for
            # dashboard/risk-state parity — calc_realized_pnl is value-identical
            # to the inline (xp-ep)*qty - (ep+xp)*qty*(fee_rate/2).
            pnl = calc_realized_pnl(ep, xp, qty, side="long", fee_rate=self.fee_rate)
            trade = build_trade_dict(entry, fill, pnl=pnl)
            self.publisher.publish_raw_trade(trade)
            self.publisher.remove_position(code)
            if self.alert_sink is not None:
                # on_exit accumulates the digest itself (do NOT call digest.add here)
                await self.alert_sink.on_exit(
                    code=code, pnl=pnl, pnl_pct=trade["pnl_pct"]
                )
        else:
            logger.warning(
                "unknown trade_role %r for %s; dropping", fill["trade_role"], code
            )

    # -- recovery + status ------------------------------------------------ #

    async def recover_open_positions(self) -> None:
        """Rebuild ``_open`` from the daemon positions hash on startup.

        Reads ``positions_key``, decodes each value via ``parse_position_record``
        (skipping foreign orchestrator records that lack ``opened_at_ms``),
        seeds the running high/low watermarks from the persisted
        ``high_water``/``low_water``, and republishes each recovered position.
        Read failures are logged and leave ``_open`` empty (non-fatal).

        First reconciles the dashboard positions hash: clears it so any stale
        or foreign-keyed field (e.g. UUID-keyed leftovers from the retired
        monolithic orchestrator, which this code-keyed pipeline never rewrites)
        is purged, then republishes exactly the positions recovered below.
        """
        self.publisher.reset_positions()
        try:
            raw = await self.redis.hgetall(self.positions_key)
        except Exception:
            logger.warning("recover read failed; starting empty", exc_info=True)
            return
        for value in raw.values():
            rec = parse_position_record(value)
            if rec is None:
                continue  # skip foreign (orchestrator) entries
            code = str(rec["code"])
            entry_price = float(rec["entry_price"])
            quantity = int(rec["quantity"])
            entry_time = _ms_to_iso(str(rec.get("opened_at_ms", "")))
            high = float(rec.get("high_water", entry_price))
            low = float(rec.get("low_water", entry_price))
            self._open[code] = {
                "code": code,
                "name": str(rec.get("name", "")),
                "strategy": str(rec.get("strategy", "")),
                "entry_price": entry_price,
                "quantity": quantity,
                "entry_time": entry_time,
                "highest_price": high,
                "lowest_price": low,
            }
            self.publisher.publish_raw_position(
                code,
                {
                    "id": code,
                    "code": code,
                    "name": self._open[code]["name"],
                    "side": "long",
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "current_price": entry_price,
                    "unrealized_pnl": 0.0,
                    "pnl_pct": 0.0,
                    "entry_time": entry_time,
                    "strategy": self._open[code]["strategy"],
                    "state": "survival",
                    "highest_price": high,
                    "lowest_price": low,
                    "fee_rate": self.fee_rate,
                    "stop_price": None,
                    "client_order_id": str(rec.get("signal_id", "")),
                },
            )

    async def publish_status_and_mtm(self) -> None:
        """Mark each open position to market and publish a daemon status row.

        Iterates a snapshot of ``_open`` rather than the live dict, updates the
        running high/low watermarks, republishes each position with current
        price / unrealized PnL, then publishes an aggregate status dict.

        That snapshot used to be load-bearing: the status task ran concurrently
        with the consume loop, so a fill could mutate ``_open`` across the
        ``get_current_price`` await. One loop now does both, so it is defensive
        — it costs a shallow copy, and it is the guarantee a future second task
        would need.

        The status row carries ``state="running"`` plus nested ``positions`` /
        ``strategies`` aggregates so the dashboard renders the decoupled stock
        pipeline as live. Without these, ``_status_response_from_raw`` (in
        services/dashboard/routes/trading.py) defaults ``state`` to ``stopped``
        and the cockpit's stock tab shows a halted/empty system even while the
        daemon is actively trading.
        """
        unrealized_total = 0.0
        winning = 0
        by_strategy: dict[str, int] = {}
        for code, entry in list(self._open.items()):
            price = await self.feed.get_current_price(code)
            close = price.get("close")
            if close is None:
                continue
            close = float(close)
            qty = int(entry.get("quantity", 0) or 0)
            ep = entry["entry_price"]
            high = max(float(entry.get("highest_price", ep)), close)
            low = min(float(entry.get("lowest_price", ep)), close)
            entry["highest_price"] = high
            entry["lowest_price"] = low
            unrealized = (close - ep) * qty
            unrealized_total += unrealized
            if unrealized > 0:
                winning += 1
            strategy = entry.get("strategy") or ""
            if strategy:
                by_strategy[strategy] = by_strategy.get(strategy, 0) + 1
            self.publisher.publish_raw_position(
                code,
                {
                    "id": code,
                    "code": code,
                    "name": entry["name"],
                    "side": "long",
                    "quantity": qty,
                    "entry_price": ep,
                    "current_price": close,
                    "unrealized_pnl": unrealized,
                    "pnl_pct": ((close - ep) / ep * 100) if ep else 0.0,
                    "entry_time": entry.get("entry_time", ""),
                    "strategy": entry["strategy"],
                    "state": "survival",
                    "highest_price": high,
                    "lowest_price": low,
                    "fee_rate": self.fee_rate,
                    "stop_price": None,
                    "client_order_id": "",
                },
            )
        open_count = len(self._open)
        strategies = sorted(by_strategy)
        self.publisher.publish_status(
            {
                "state": "running",
                "source": "stock_monitor",
                "worker_id": self.worker_id,
                "open_positions": open_count,
                "strategies": {
                    "asset_class": "stock",
                    "strategy_count": len(strategies),
                    "strategies": strategies,
                },
                "positions": {
                    "open_positions": open_count,
                    "unrealized_pnl": unrealized_total,
                    "winning_positions": winning,
                    "by_strategy": by_strategy,
                },
            }
        )

    async def _check_health_and_digest(self) -> None:
        """KST-guarded health-anomaly + session-digest alerts (spec §7 ②/③).

        Called once per status tick. Resets the digest daily at/after 09:00 KST,
        emits one non-empty session digest per day at/after ``digest_time_kst``,
        and (during market hours) sends a cooldown-gated health alert when the
        feed's market-data staleness exceeds ``health_stale_seconds``. No-op when
        no ``alert_sink`` is configured.
        """
        if self.alert_sink is None:
            return
        now_kst = self.now_fn().astimezone(_KST)
        today = now_kst.date().isoformat()
        hhmm = now_kst.strftime("%H:%M")
        in_market = time(9, 0) <= now_kst.time() <= time(15, 30)

        # daily digest reset at/after 09:00 KST (once/day)
        if now_kst.time() >= time(9, 0) and self._digest_reset_date != today:
            self.alert_sink.digest.reset()
            self._digest_reset_date = today

        # session digest once/day at/after digest_time_kst (skip empty)
        if hhmm >= self.digest_time_kst and self._digest_emitted_date != today:
            if self.alert_sink.digest.trades > 0:
                await self.alert_sink.emit_digest(open_count=len(self._open))
            # mark even if empty, so we don't recheck all day
            self._digest_emitted_date = today

        # health anomaly: market data stale during market hours, cooldown-gated.
        # Signal is feed staleness (upstream ingest down), NOT "no trades" — a
        # quiet market legitimately has no trades and must not alert.
        if in_market:
            staleness = self.feed.get_staleness_seconds()
            if staleness is not None and staleness > self.health_stale_seconds:
                now_ts = self.now_fn().timestamp()
                if now_ts - self._last_health_alert_ts > self.health_cooldown_seconds:
                    await self.alert_sink.send_health(
                        f"market data stale {staleness:.0f}s (feed)"
                    )
                    self._last_health_alert_ts = now_ts

    # -- MultiStreamStage hooks ------------------------------------------- #

    async def on_startup(self) -> None:
        """Start the tick feed and rebuild open positions from the hash.

        Runs *before* the stage ensures the consumer groups, where the previous
        hand-rolled ``run()`` recovered after creating them. The order does not
        matter: both create with ``id="0", mkstream=True``, so the group reads
        the stream from the beginning either way, and recovery only touches the
        positions hash and the dashboard keys.
        """
        await self.feed.start()
        await self.recover_open_positions()

    async def pre_iteration_gate(self) -> bool:
        """Run the status/MTM cadence, then always continue the loop.

        **This hook carries cadence work on purpose, and its name says gate.**
        The daemon used to run the status tick as a second task, and that is
        precisely how it could go blind: a consume task that died left
        ``_status_loop`` publishing fresh status keys from a process that was
        no longer reading anything (``RestartCount=0``, ``state: running``).
        One loop makes death visible — if this returns, nothing publishes.

        Of the stage's hooks only this one runs on *every* iteration. The stage
        takes a ``continue`` past ``post_poll`` whenever a read fails, so status
        publishing hung off ``post_poll`` would stop during exactly the Redis
        trouble an operator most wants status for. Today's ``_status_loop``
        keeps ticking through read errors, and this keeps that property.

        The contract is that ``False`` makes ``run()`` return, so this returns
        ``True`` unconditionally and swallows what the cadence raises — the same
        "status loop error; continuing" the second task logged.

        Cadence is unchanged in intent and coarser in practice: an idle
        iteration ends with a ``xread_block_ms`` (2s) poll, so a 5s interval
        fires every ~6s rather than every 5s. The consumers of these keys are
        the dashboard and a 600s staleness alert; neither can tell.
        """
        now = self._status_clock()
        if self._last_status_at is None or (
            now - self._last_status_at >= self.status_interval
        ):
            self._last_status_at = now
            try:
                await self.publish_status_and_mtm()
                await self._check_health_and_digest()
            except Exception:
                logger.exception("status loop error; continuing")
        return True

    async def handle_message(
        self,
        stream: str | bytes,
        msg_id: bytes,
        fields: dict[bytes, bytes],
    ) -> bool:
        """Route one record to its handler; drop a poison message rather than die.

        ``MultiStreamStage._process_messages`` re-raises whatever
        ``handle_message`` throws, which ends ``run()`` — right for a stage
        whose messages are orders, wrong for an observation daemon, where
        losing every later record costs more than dropping one malformed one.
        So the catch lives here and the framework is told to ACK (``True``),
        which is the behaviour this daemon shipped with.

        The dropped record is reported with the same ``stream_message_dropped``
        event and traceback as before. It no longer asserts ``ack=true``: the
        ACK happens after this returns, and the framework's own line for the
        same ``msg_id`` — ``stream_message_processed ack=true``, or
        ``stream_message_ack_failed`` — is the record of whether it landed.
        """
        name = decode_stream_id(stream)
        try:
            if name == self.fill_stream:
                await self.handle_fill(fields)
            elif name == self.signal_stream:
                await self.handle_signal(fields)
            else:
                logger.warning("unexpected stream %s", name)
        except Exception:
            logger.exception(
                format_audit_kv(
                    event="stream_message_dropped",
                    stream=name,
                    consumer_group=self.consumer_group,
                    worker_id=self.worker_id,
                    msg_id=decode_stream_id(msg_id),
                    reason="handler_exception",
                    **extract_audit_fields(fields),
                )
            )
        return True

    async def on_shutdown(self) -> None:
        await self.feed.stop()
