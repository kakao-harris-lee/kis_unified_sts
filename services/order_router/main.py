"""Order-router consumer-group daemon.

Phase 4 Task 12 — reads filtered :class:`Signal`s from
``stream:signal.final``, places passive limit entries via
:class:`PassiveMaker`, and on fill registers a stop+target bracket via
:class:`PseudoOCO`. Fills are logged through :class:`FillLogger` (already
wired into PassiveMaker).

This is the only daemon that holds wallet authority — every other Phase 4
component reads/audits, but the order_router places real orders. Kill
switch (Task 13) signals shutdown via a sentinel; we honor that by exiting
the run loop without accepting new messages.

Error taxonomy:
- Parse error                   → XACK (poison-pill drop)
- PassiveMaker raises           → NO XACK (retry)
- PseudoOCO.register_bracket    → NO XACK (entry filled but bracket not
                                  registered → caller must reconcile)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from services.risk_filter.main import _signal_from_stream_fields
from shared.execution.contract_spec import ContractSpec
from shared.execution.passive_maker import PassiveMaker
from shared.execution.pseudo_oco import PseudoOCO

logger = logging.getLogger(__name__)


def _resolve_quantity(*, base_quantity: int, size_multiplier: float) -> int:
    """Scale ``base_quantity`` by ``size_multiplier``, floor at 1.

    Risk filter's :class:`ConsecutiveLossFilter` may emit
    ``size_multiplier=0.5`` to halve sizing after a losing streak. With
    ``base_quantity=1`` (current Phase 4 ladder), 0.5 rounds to 0; we floor
    at 1 contract because zero-sized orders are nonsensical and the filter's
    intent is "trade smaller", not "skip the trade" (which would have
    used ``passed=False``).
    """
    scaled = int(round(base_quantity * size_multiplier))
    return max(scaled, 1)


class OrderRouterDaemon:
    def __init__(
        self,
        *,
        redis: Any,
        passive_maker: PassiveMaker,
        pseudo_oco: PseudoOCO,
        contract_spec: ContractSpec,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        xread_block_ms: int,
        batch_size: int,
        passive_timeout_seconds: int,
        base_quantity: int = 1,
    ) -> None:
        self.redis = redis
        self.passive_maker = passive_maker
        self.pseudo_oco = pseudo_oco
        self.contract_spec = contract_spec
        self.final_stream = final_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.xread_block_ms = xread_block_ms
        self.batch_size = batch_size
        self.passive_timeout_seconds = passive_timeout_seconds
        self.base_quantity = base_quantity
        self._stop = asyncio.Event()

    async def run(self) -> None:
        with contextlib.suppress(Exception):
            await self.redis.xgroup_create(
                self.final_stream, self.consumer_group, id="0", mkstream=True
            )

        while not self._stop.is_set():
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.worker_id,
                    streams={self.final_stream: ">"},
                    count=self.batch_size,
                    block=self.xread_block_ms,
                )
            except Exception:
                logger.exception("xreadgroup error; sleeping 0.5s")
                await asyncio.sleep(0.5)
                continue

            if not messages:
                await asyncio.sleep(0)
                continue

            for _stream, msgs in messages:
                for msg_id, data in msgs:
                    await self._process(msg_id, data)

    async def stop(self) -> None:
        self._stop.set()

    async def _process(self, msg_id: bytes, fields: dict[bytes, bytes]) -> None:
        try:
            signal_id, signal = _signal_from_stream_fields(fields)
            size_multiplier = float(
                fields.get(b"size_multiplier", b"1.0").decode(errors="replace") or 1.0
            )
        except Exception:
            logger.exception("Unparseable final signal; ACK as poison-pill")
            await self.redis.xack(self.final_stream, self.consumer_group, msg_id)
            return

        quantity = _resolve_quantity(
            base_quantity=self.base_quantity, size_multiplier=size_multiplier
        )

        # Place passive limit + log fill
        try:
            result = await self.passive_maker.place_passive_limit_futures(
                signal=signal,
                signal_id=signal_id,
                quantity=quantity,
                spec=self.contract_spec,
                timeout_seconds=self.passive_timeout_seconds,
            )
        except Exception:
            logger.exception(
                "passive_maker raised signal_id=%s; leaving pending", signal_id
            )
            return

        if not result.is_filled:
            # Missed (timeout/cancel) — final state, ACK and drop. The signal
            # is consumed; no bracket to register, no retry.
            logger.info(
                "passive limit not filled signal_id=%s reason=%s",
                signal_id,
                result.reason,
            )
            await self.redis.xack(self.final_stream, self.consumer_group, msg_id)
            return

        # Register bracket on the entry fill
        try:
            from shared.execution.passive_maker import Fill

            fill = Fill(
                order_id=result.order_id or "",
                price=result.filled_price or 0.0,
                quantity=quantity,
                filled_at_ms=0,  # bracket cares about handle state, not entry timestamp
            )
            await self.pseudo_oco.register_bracket(
                signal=signal,
                signal_id=signal_id,
                fill=fill,
                tick_size_points=self.contract_spec.tick_size_points,
            )
        except Exception:
            logger.exception(
                "OCO register failed signal_id=%s order_id=%s; leaving pending",
                signal_id,
                result.order_id,
            )
            return

        await self.redis.xack(self.final_stream, self.consumer_group, msg_id)
