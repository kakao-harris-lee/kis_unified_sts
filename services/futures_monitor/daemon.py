"""Futures monitor / observability bridge daemon (F-5, shadow-first).

Consumes the decoupled futures daemon streams and republishes dashboard-native
state (positions/trades/signals/status) via TradingStatePublisher + important-
only alerts. Pairs entry<->exit fills (by symbol) for closed trades, side-aware
contract-multiplier PnL (parity with PseudoOCO._record_pnl), marks positions to
market, owns the futures positions hash for restart recovery.

The transport — XGROUP CREATE, XREADGROUP, vanished-group recovery, XACK and
the liveness heartbeat — is :class:`shared.streaming.stage.MultiStreamStage`,
not code in this file. What remains here is the futures domain: fill/signal
routing, entry<->exit pairing, contract-multiplier PnL, and the positions hash.
"""

from __future__ import annotations

import contextlib
import logging
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime, time
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

from services.futures_monitor.positions import (
    build_position_record,
    parse_futures_position_record,
)
from services.futures_monitor.serializers import (
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
from shared.utils.calc import calc_futures_realized_pnl

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_EXIT_ROLES = ("stop_loss", "take_profit", "force_close")
_CONSUME_ERROR_SLEEP_SECONDS = 0.5
#: Same literals the hand-rolled loop passed to XREADGROUP before the migration.
_XREAD_BLOCK_MS = 2000
_BATCH_SIZE = 50
#: Pending-entry reclaim (XAUTOCLAIM) stays off, which is what this daemon did
#: before the migration and what it must keep doing. A monitor's handlers are
#: not idempotent in the way redelivery needs: a redelivered entry fill fires
#: ``alert_sink.on_entry`` a second time and resets ``high_water``/``low_water``
#: to the entry price, discarding the watermark progress the position has made.
#: Turning reclaim on is a deliberate behaviour change with its own evidence,
#: not a side effect of moving onto the shared stage.
_PENDING_RETRY_DISABLED_MS = -1


class FuturesMonitorDaemon(MultiStreamStage):
    """Bridge daemon: futures daemon streams -> dashboard keys + alerts."""

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
        multiplier: float,
        status_interval: float,
        signal_meta_max: int = 1000,
        now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
        health_stale_seconds: float = 600.0,
        health_cooldown_seconds: float = 1800.0,
        digest_time_kst: str = "15:40",
        contract_symbol: str | None = None,
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
        # The contract this process resolved and subscribed to. Only used to
        # flag recovered positions on another (e.g. pre-roll) contract; None
        # disables the check.
        self.contract_symbol = contract_symbol
        self.feed = feed
        self.publisher = publisher
        self.alert_sink = alert_sink
        self.positions_key = positions_key
        self.fill_stream = fill_stream
        self.signal_stream = signal_stream
        self.multiplier = multiplier
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
        sig = parse_final_signal(fields)
        self._signal_meta[sig["signal_id"]] = {
            "setup_type": sig["setup_type"],
            "direction": sig["direction"],
            "symbol": sig["symbol"],
        }
        while len(self._signal_meta) > self.signal_meta_max:
            self._signal_meta.popitem(last=False)
        self.publisher.publish_raw_signal(build_signal_dict(sig))

    async def _persist_open(self, symbol: str) -> None:
        with contextlib.suppress(Exception):
            await self.redis.hset(
                self.positions_key, symbol, build_position_record(self._open[symbol])
            )

    async def handle_fill(self, fields: dict[bytes, bytes]) -> None:
        fill = parse_fill(fields)
        symbol = fill["symbol"]
        role = fill["trade_role"]
        if role == "entry":
            meta = self._signal_meta.get(fill["signal_id"], {})
            pos_dict = build_position_dict(fill, meta, multiplier=self.multiplier)
            self.publisher.publish_raw_position(symbol, pos_dict)
            entry_price = fill["filled_price"]
            self._open[symbol] = {
                "symbol": symbol,
                "side": fill["side"],
                "setup_type": meta.get("setup_type", ""),
                "signal_id": fill["signal_id"],
                "entry_price": entry_price,
                "quantity": fill["quantity"],
                "entry_time": pos_dict["entry_time"],
                "opened_at_ms": int(float(fill["filled_at_ms"] or 0)),
                "high_water": entry_price,
                "low_water": entry_price,
            }
            await self._persist_open(symbol)
            if self.alert_sink is not None:
                await self.alert_sink.on_entry(
                    code=symbol,
                    strategy=meta.get("setup_type", ""),
                    quantity=fill["quantity"],
                    price=entry_price,
                )
        elif role in _EXIT_ROLES:
            entry = self._open.pop(symbol, None)
            if entry is None:
                logger.warning("exit fill for %s with no open entry; skipping", symbol)
                self.publisher.remove_position(symbol)
                with contextlib.suppress(Exception):
                    await self.redis.hdel(self.positions_key, symbol)
                return
            ep, xp, qty = entry["entry_price"], fill["filled_price"], fill["quantity"]
            side = entry["side"]
            pnl = calc_futures_realized_pnl(
                ep, xp, qty, side, multiplier_krw_per_point=self.multiplier
            )
            trade = build_trade_dict(entry, fill, pnl=pnl)
            self.publisher.publish_raw_trade(trade)
            self.publisher.remove_position(symbol)
            with contextlib.suppress(Exception):
                await self.redis.hdel(self.positions_key, symbol)
            if self.alert_sink is not None:
                await self.alert_sink.on_exit(
                    code=symbol, pnl=pnl, pnl_pct=trade["pnl_pct"]
                )
        else:
            logger.warning("unknown trade_role %r for %s; dropping", role, symbol)

    # -- recovery + status ------------------------------------------------ #

    async def recover_open_positions(self) -> None:
        try:
            raw = await self.redis.hgetall(self.positions_key)
        except Exception:
            logger.warning("recover read failed; starting empty", exc_info=True)
            return
        for value in raw.values():
            rec = parse_futures_position_record(value)
            if rec is None:
                continue
            symbol = str(rec["symbol"])
            if self.contract_symbol and symbol != self.contract_symbol:
                # Warn only — the record is still recovered unchanged. A
                # position left on a rolled-out contract gets no price
                # updates here (the feed follows contract_symbol).
                logger.warning(
                    "recovered futures position %s is not on the current "
                    "contract %s (likely opened before a front-month roll); "
                    "it will not be marked to market",
                    symbol,
                    self.contract_symbol,
                )
            entry_price = float(rec["entry_price"])
            self._open[symbol] = {
                "symbol": symbol,
                "side": str(rec.get("side", "long")),
                "setup_type": str(rec.get("setup_type", "")),
                "signal_id": str(rec.get("signal_id", "")),
                "entry_price": entry_price,
                "quantity": int(rec["quantity"]),
                "entry_time": _ms_to_iso(str(rec.get("opened_at_ms", ""))),
                "opened_at_ms": int(rec.get("opened_at_ms", 0) or 0),
                "high_water": float(rec.get("high_water", entry_price)),
                "low_water": float(rec.get("low_water", entry_price)),
            }
            self._publish_position(symbol, entry_price)

    def _publish_position(self, symbol: str, close: float) -> None:
        entry = self._open[symbol]
        ep = entry["entry_price"]
        qty = int(entry.get("quantity", 0) or 0)
        sign = 1.0 if entry["side"] == "long" else -1.0
        self.publisher.publish_raw_position(
            symbol,
            {
                "id": symbol,
                "code": symbol,
                "name": "",
                "side": entry["side"],
                "quantity": qty,
                "entry_price": ep,
                "current_price": close,
                "unrealized_pnl": (close - ep) * sign * qty * self.multiplier,
                "pnl_pct": (((close - ep) * sign) / ep * 100) if ep else 0.0,
                "entry_time": entry.get("entry_time", ""),
                "strategy": entry.get("setup_type", ""),
                "state": "survival",
                "highest_price": entry["high_water"],
                "lowest_price": entry["low_water"],
                "fee_rate": 0.0,
                "stop_price": None,
                "client_order_id": entry.get("signal_id", ""),
            },
        )

    async def publish_status_and_mtm(self) -> None:
        for symbol, entry in list(self._open.items()):
            price = await self.feed.get_current_price(symbol)
            close = price.get("close")
            if close is None:
                continue
            close = float(close)
            entry["high_water"] = max(float(entry.get("high_water", close)), close)
            entry["low_water"] = min(float(entry.get("low_water", close)), close)
            self._publish_position(symbol, close)
            await self._persist_open(symbol)
        self.publisher.publish_status(
            {
                "open_positions": len(self._open),
                "worker_id": self.worker_id,
                "source": "futures_monitor",
            }
        )

    async def _check_health_and_digest(self) -> None:
        if self.alert_sink is None:
            return
        now_kst = self.now_fn().astimezone(_KST)
        today = now_kst.date().isoformat()
        hhmm = now_kst.strftime("%H:%M")
        in_market = time(9, 0) <= now_kst.time() <= time(15, 30)
        if now_kst.time() >= time(9, 0) and self._digest_reset_date != today:
            self.alert_sink.digest.reset()
            self._digest_reset_date = today
        if hhmm >= self.digest_time_kst and self._digest_emitted_date != today:
            if self.alert_sink.digest.trades > 0:
                await self.alert_sink.emit_digest(open_count=len(self._open))
            self._digest_emitted_date = today
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
        positions hash.
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
