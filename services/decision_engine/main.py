"""Decision-engine daemon — Setup A/C → stream:signal.candidate.

Phase 4 Task 10. Polls a context provider on a fixed cadence (default
~1 minute), runs each registered :class:`Setup` (A_gap_reversion,
C_event_reaction) against the snapshot, and publishes any emitted
:class:`Signal` to ``stream:signal.candidate`` for the risk_filter daemon
(Task 11) to consume.

The ``context_provider`` is an injected async callable returning either a
:class:`MarketContext` or None. The production wiring (live KIS feed +
overnight macro + scheduled events) is heavier than this PR's scope and
will be supplied by the parent runtime: this module just runs the
"context → setup → publish" loop. Tests inject a stub provider that
yields pre-built contexts.

Error taxonomy:
- Setup raises          → log + skip that setup (other setups still run)
- context_provider None → tick produces no signal; sleep until next tick
- redis xadd failure    → propagated; the supervisor restarts the daemon
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from shared.decision.context import MarketContext
from shared.decision.setup_base import Setup

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400


class DecisionEngineDaemon:
    def __init__(
        self,
        *,
        redis: Any,
        setups: list[Setup],
        context_provider: Callable[[], Awaitable[MarketContext | None]],
        candidate_stream: str,
        candidate_maxlen: int,
        tick_interval_seconds: float,
    ) -> None:
        self.redis = redis
        self.setups = setups
        self.context_provider = context_provider
        self.candidate_stream = candidate_stream
        self.candidate_maxlen = candidate_maxlen
        self.tick_interval_seconds = tick_interval_seconds
        self._stop = asyncio.Event()

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                ctx = await self.context_provider()
            except Exception:
                logger.exception("context_provider raised; sleeping and retrying")
                await asyncio.sleep(self.tick_interval_seconds)
                continue

            if ctx is None:
                await asyncio.sleep(self.tick_interval_seconds)
                continue

            for setup in self.setups:
                try:
                    signal = setup.check(ctx)
                except Exception:
                    logger.exception(
                        "setup %s raised; skipping this tick",
                        setup.__class__.__name__,
                    )
                    continue
                if signal is None:
                    continue

                try:
                    await self._publish(signal)
                except Exception:
                    logger.exception(
                        "publish to %s failed; signal dropped (%s)",
                        self.candidate_stream,
                        signal.setup_type,
                    )

            await asyncio.sleep(self.tick_interval_seconds)

    async def stop(self) -> None:
        self._stop.set()

    async def _publish(self, signal) -> None:
        fields = signal.to_stream_dict()
        # Issue a fresh signal_id per emission so downstream consumers can
        # de-dupe and trace through risk_filter / order_router / order_fills.
        fields["signal_id"] = uuid.uuid4().hex
        await self.redis.xadd(
            self.candidate_stream,
            fields,
            maxlen=self.candidate_maxlen,
            approximate=True,
        )
        await self.redis.expire(self.candidate_stream, _STREAM_TTL_SECONDS)
