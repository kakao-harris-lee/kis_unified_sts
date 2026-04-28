"""Risk-filter consumer-group daemon.

Phase 4 Task 11 — reads :class:`Signal` candidates from
``stream:signal.candidate``, runs the :class:`RiskFilterLayer`, persists
every (signal, layer_result) pair to ``kospi.signals_all`` (Phase 3
audit), and on pass forwards the enriched signal to ``stream:signal.final``
where the order_router daemon (Task 12) consumes it.

Error taxonomy (mirrors services.news_scorer.main):
- Parse error → XACK (poison-pill drop)
- Filter evaluation raises → NO XACK (leave pending)
- ``signals_all`` flush raises → NO XACK
- ``stream:signal.final`` XADD raises → NO XACK
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from shared.decision.signal import Signal
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400


def _signal_from_stream_fields(fields: dict[bytes, bytes]) -> tuple[str, Signal]:
    """Parse a Redis stream field dict into ``(signal_id, Signal)``.

    Mirrors :meth:`Signal.to_stream_dict` (timestamps as epoch ms, reason
    tags JSON-encoded).
    """

    def _s(key: str) -> str:
        raw = fields.get(key.encode(), b"")
        return (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes)
            else str(raw)
        )

    def _ms_to_dt(ms: str) -> datetime | None:
        if not ms:
            return None
        return datetime.fromtimestamp(int(ms) / 1000, tz=UTC)

    signal_id = _s("signal_id")
    signal = Signal(
        setup_type=_s("setup_type"),
        direction=_s("direction"),
        symbol=_s("symbol"),
        entry_price=float(_s("entry_price")),
        stop_loss=float(_s("stop_loss")),
        take_profit=float(_s("take_profit")),
        confidence=float(_s("confidence")),
        reason_tags=tuple(json.loads(_s("reason_tags_json") or "[]")),
        valid_until=_ms_to_dt(_s("valid_until_ms")),
        generated_at=_ms_to_dt(_s("generated_at_ms")),
    )
    return signal_id, signal


class RiskFilterDaemon:
    """Apply the 8-filter RiskFilterLayer to every candidate signal."""

    def __init__(
        self,
        *,
        redis: Any,
        layer: RiskFilterLayer,
        signals_writer: Any,
        runtime_state: RuntimeRiskState,
        candidate_stream: str,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        final_maxlen: int,
        xread_block_ms: int,
        batch_size: int,
    ) -> None:
        self.redis = redis
        self.layer = layer
        self.signals_writer = signals_writer
        self.runtime_state = runtime_state
        self.candidate_stream = candidate_stream
        self.final_stream = final_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.final_maxlen = final_maxlen
        self.xread_block_ms = xread_block_ms
        self.batch_size = batch_size
        self._stop = asyncio.Event()

    async def run(self) -> None:
        with contextlib.suppress(Exception):
            await self.redis.xgroup_create(
                self.candidate_stream, self.consumer_group, id="0", mkstream=True
            )

        try:
            while not self._stop.is_set():
                try:
                    messages = await self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.worker_id,
                        streams={self.candidate_stream: ">"},
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
        finally:
            await self.signals_writer.flush()

    async def stop(self) -> None:
        self._stop.set()

    async def _process(self, msg_id: bytes, fields: dict[bytes, bytes]) -> None:
        try:
            signal_id, signal = _signal_from_stream_fields(fields)
        except Exception:
            logger.exception("Unparseable candidate; ACKing as poison-pill")
            await self.redis.xack(self.candidate_stream, self.consumer_group, msg_id)
            return

        try:
            snapshot = await self.runtime_state.snapshot()
            result = self.layer.evaluate(signal, snapshot)
        except Exception:
            logger.exception(
                "Filter evaluation failed signal_id=%s; leaving pending", signal_id
            )
            return

        # Audit row first — every candidate, accepted or rejected.
        # Thread the stream signal_id so kospi.signals_all rows match the
        # later kospi.order_fills row on signal_id (spec §5.3 reconciliation
        # JOIN). SignalsAllWriter falls back to a fresh uuid for backtest
        # harness callers without a pre-existing id.
        try:
            await self.signals_writer.enqueue(
                signal,
                result,
                executed=result.passed,
                signal_id=signal_id,
            )
        except Exception:
            logger.exception(
                "signals_all enqueue failed signal_id=%s; leaving pending", signal_id
            )
            return

        if result.passed:
            try:
                fields_out = signal.to_stream_dict()
                fields_out["signal_id"] = signal_id
                fields_out["size_multiplier"] = str(result.size_multiplier)
                fields_out["filtered_at_ms"] = str(int(time.time() * 1000))
                await self.redis.xadd(
                    self.final_stream,
                    fields_out,
                    maxlen=self.final_maxlen,
                    approximate=True,
                )
                await self.redis.expire(self.final_stream, _STREAM_TTL_SECONDS)
            except Exception:
                logger.exception(
                    "final stream XADD failed signal_id=%s; leaving pending",
                    signal_id,
                )
                return

        await self.redis.xack(self.candidate_stream, self.consumer_group, msg_id)
