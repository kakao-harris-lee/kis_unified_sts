"""Futures monitor / observability bridge daemon (F-5, shadow-first).

Consumes the decoupled futures daemon streams and republishes dashboard-native
state (positions/trades/signals/status) via TradingStatePublisher + important-
only alerts. Pairs entry<->exit fills (by symbol) for closed trades, side-aware
contract-multiplier PnL (parity with PseudoOCO._record_pnl), marks positions to
market, owns the futures positions hash for restart recovery.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime, time
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
    RateLimitedLog,
    decode_stream_id,
    extract_audit_fields,
    format_audit_kv,
)
from shared.utils.calc import calc_futures_realized_pnl

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_EXIT_ROLES = ("stop_loss", "take_profit", "force_close")
_CONSUME_ERROR_SLEEP_SECONDS = 0.5


class FuturesMonitorDaemon:
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
    ) -> None:
        self.redis = redis
        self.feed = feed
        self.publisher = publisher
        self.alert_sink = alert_sink
        self.positions_key = positions_key
        self.fill_stream = fill_stream
        self.signal_stream = signal_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.multiplier = multiplier
        self.status_interval = status_interval
        self.signal_meta_max = signal_meta_max
        self.now_fn = now_fn
        self.health_stale_seconds = health_stale_seconds
        self.health_cooldown_seconds = health_cooldown_seconds
        self.digest_time_kst = digest_time_kst
        self._open: dict[str, dict[str, Any]] = {}
        self._signal_meta: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._stop = asyncio.Event()
        self._last_health_alert_ts: float = 0.0
        self._digest_emitted_date: str = ""
        self._digest_reset_date: str = ""
        self._xreadgroup_error_log = RateLimitedLog()

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

    # -- loops ------------------------------------------------------------ #

    async def run(self) -> None:
        await self.feed.start()
        for stream in (self.fill_stream, self.signal_stream):
            with contextlib.suppress(Exception):
                await self.redis.xgroup_create(
                    stream, self.consumer_group, id="0", mkstream=True
                )
        await self.recover_open_positions()
        consumer = asyncio.create_task(self._consume_loop())
        status = asyncio.create_task(self._status_loop())
        try:
            await self._stop.wait()
        finally:
            consumer.cancel()
            status.cancel()
            for t in (consumer, status):
                with contextlib.suppress(asyncio.CancelledError):
                    await t
            await self.feed.stop()

    async def stop(self) -> None:
        self._stop.set()

    async def _consume_loop(self) -> None:
        while not self._stop.is_set():
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.worker_id,
                    streams={self.fill_stream: ">", self.signal_stream: ">"},
                    count=50,
                    block=2000,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self._xreadgroup_error_log.exception(
                    logger,
                    format_audit_kv(
                        event="monitor_stream_read_error",
                        streams=f"{self.fill_stream},{self.signal_stream}",
                        consumer_group=self.consumer_group,
                        worker_id=self.worker_id,
                        sleep_seconds=_CONSUME_ERROR_SLEEP_SECONDS,
                    ),
                )
                await asyncio.sleep(_CONSUME_ERROR_SLEEP_SECONDS)
                continue
            self._xreadgroup_error_log.reset()
            if not messages:
                continue
            for stream, msgs in messages:
                name = decode_stream_id(stream)
                for msg_id, data in msgs:
                    handler_failed = False
                    try:
                        if name == self.fill_stream:
                            await self.handle_fill(data)
                        elif name == self.signal_stream:
                            await self.handle_signal(data)
                        else:
                            logger.warning("unexpected stream %s", name)
                    except Exception:
                        handler_failed = True
                        try:
                            await self.redis.xack(name, self.consumer_group, msg_id)
                        except Exception:
                            logger.error(
                                format_audit_kv(
                                    event="stream_message_ack_failed",
                                    stream=name,
                                    consumer_group=self.consumer_group,
                                    worker_id=self.worker_id,
                                    msg_id=decode_stream_id(msg_id),
                                    reason="handler_exception",
                                    **extract_audit_fields(data),
                                ),
                                exc_info=True,
                            )
                            raise
                        logger.exception(
                            format_audit_kv(
                                event="stream_message_dropped",
                                stream=name,
                                consumer_group=self.consumer_group,
                                worker_id=self.worker_id,
                                msg_id=decode_stream_id(msg_id),
                                ack=True,
                                reason="handler_exception",
                                **extract_audit_fields(data),
                            )
                        )
                    if not handler_failed:
                        await self.redis.xack(name, self.consumer_group, msg_id)

    async def _status_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.publish_status_and_mtm()
                await self._check_health_and_digest()
            except Exception:
                logger.exception("status loop error; continuing")
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self.status_interval)
