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


async def _build_and_run() -> int:
    """Production entrypoint. Wires Redis + a stub context_provider and runs.

    The full live MarketContext builder (KIS bars + macro + scheduled events)
    lands with Task 17. Until then this entrypoint exists so systemd can
    actually start the unit; the daemon polls and gets ``None`` from the
    stub provider, emitting no signals — visible behaviour matches "no
    upstream data" rather than the previous silent exit-0.
    """
    import os
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    async def _stub_context_provider():
        # Live builder lands in Task 17. Until then, emit nothing.
        return None

    # Setup imports — defer to runtime so unit tests don't pay for them.
    from shared.decision.setups.event_reaction import SetupCEventReaction
    from shared.decision.setups.gap_reversion import SetupAGapReversion

    setups = [SetupAGapReversion(), SetupCEventReaction()]

    daemon = DecisionEngineDaemon(
        redis=redis_client,
        setups=setups,
        context_provider=_stub_context_provider,
        candidate_stream="stream:signal.candidate",
        candidate_maxlen=10_000,
        tick_interval_seconds=60.0,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await redis_client.aclose()
    return 0


def main() -> int:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
