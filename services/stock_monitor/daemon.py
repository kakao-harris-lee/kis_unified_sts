"""Stock monitor / observability bridge daemon (M5a, shadow-first).

Consumes the decoupled stock daemon streams and republishes dashboard-native
state (positions/trades/signals/status) via TradingStatePublisher, plus
important-only alerts. Pairs entry<->exit fills (by code) for closed trades,
correlates final signals (by signal_id) for strategy/name, marks positions to
market, and recovers open state from the daemon positions hash on startup.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import OrderedDict
from typing import Any

from services.stock_exit.positions import parse_position_record
from services.stock_monitor.serializers import (
    build_position_dict,
    build_signal_dict,
    build_trade_dict,
    parse_fill,
    parse_final_signal,
)

logger = logging.getLogger(__name__)


class StockMonitorDaemon:
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
        self.fee_rate = fee_rate
        self.status_interval = status_interval
        self.signal_meta_max = signal_meta_max
        self._open: dict[str, dict[str, Any]] = {}
        self._signal_meta: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._stop = asyncio.Event()

    # -- handlers --------------------------------------------------------- #

    async def handle_signal(self, fields: dict[bytes, bytes]) -> None:
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
        fill = parse_fill(fields)
        code = fill["code"]
        if fill["trade_role"] == "entry":
            meta = self._signal_meta.get(fill["signal_id"], {})
            pos_dict = build_position_dict(fill, meta, fee_rate=self.fee_rate)
            self.publisher.publish_raw_position(code, pos_dict)
            self._open[code] = {
                "code": code,
                "name": meta.get("name", ""),
                "strategy": meta.get("strategy", ""),
                "entry_price": fill["filled_price"],
                "quantity": fill["quantity"],
                "entry_time": pos_dict["entry_time"],
            }
            if self.alert_sink is not None:
                await self.alert_sink.on_entry(
                    code=code,
                    strategy=meta.get("strategy", ""),
                    quantity=fill["quantity"],
                    price=fill["filled_price"],
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
            pnl = (xp - ep) * qty - (ep + xp) * qty * (self.fee_rate / 2)
            trade = build_trade_dict(entry, fill, pnl=pnl)
            self.publisher.publish_raw_trade(trade)
            self.publisher.remove_position(code)
            if self.alert_sink is not None:
                # on_exit accumulates the digest itself (do NOT call digest.add here)
                await self.alert_sink.on_exit(
                    code=code, pnl=pnl, pnl_pct=trade["pnl_pct"]
                )

    # -- recovery + status ------------------------------------------------ #

    async def recover_open_positions(self) -> None:
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
            self._open[code] = {
                "code": code,
                "name": str(rec.get("name", "")),
                "strategy": str(rec.get("strategy", "")),
                "entry_price": entry_price,
                "quantity": quantity,
                "entry_time": "",
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
                    "entry_time": "",
                    "strategy": self._open[code]["strategy"],
                    "state": "survival",
                    "highest_price": float(rec.get("high_water", entry_price)),
                    "lowest_price": float(rec.get("low_water", entry_price)),
                    "fee_rate": self.fee_rate,
                    "stop_price": None,
                    "client_order_id": str(rec.get("signal_id", "")),
                },
            )

    async def publish_status_and_mtm(self) -> None:
        for code, entry in self._open.items():
            price = await self.feed.get_current_price(code)
            close = price.get("close")
            if close is None:
                continue
            close = float(close)
            qty = int(entry.get("quantity", 0) or 0)
            ep = entry["entry_price"]
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
                    "unrealized_pnl": (close - ep) * qty,
                    "pnl_pct": ((close - ep) / ep * 100) if ep else 0.0,
                    "entry_time": entry.get("entry_time", ""),
                    "strategy": entry["strategy"],
                    "state": "survival",
                    "highest_price": ep,
                    "lowest_price": ep,
                    "fee_rate": self.fee_rate,
                    "stop_price": None,
                    "client_order_id": "",
                },
            )
        self.publisher.publish_status(
            {
                "open_positions": len(self._open),
                "worker_id": self.worker_id,
                "source": "stock_monitor",
            }
        )

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
                logger.exception("xreadgroup error; sleeping 0.5s")
                await asyncio.sleep(0.5)
                continue
            if not messages:
                continue
            for stream, msgs in messages:
                name = stream.decode() if isinstance(stream, bytes) else str(stream)
                for msg_id, data in msgs:
                    try:
                        if name == self.fill_stream:
                            await self.handle_fill(data)
                        else:
                            await self.handle_signal(data)
                    except Exception:
                        logger.exception("handler error; dropping (poison-pill)")
                    await self.redis.xack(name, self.consumer_group, msg_id)

    async def _status_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.publish_status_and_mtm()
            except Exception:
                logger.exception("status loop error; continuing")
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self.status_interval)
