"""Risk-filter consumer-group daemon.

Phase 4 Task 11 — reads :class:`Signal` candidates from
``signal.candidate.futures``, runs the :class:`RiskFilterLayer`, persists
every (signal, layer_result) pair to ``kospi.signals_all`` (Phase 3
audit), and on pass forwards the enriched signal to ``signal.final.futures``
where the order_router daemon (Task 12) consumes it.

Error taxonomy (mirrors services.news_scorer.main):
- Parse error → XACK (poison-pill drop)
- Filter evaluation raises → NO XACK (leave pending)
- ``signals_all`` flush raises → NO XACK
- ``signal.final.futures`` XADD raises → NO XACK
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from shared.config.runtime_defaults import redis_url_from_env
from shared.decision.signal import Signal
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState
from shared.streaming.stage import StreamStage

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400

# Candidate-stream fields attached by the decision_engine market-risk ENTRY
# gate (roadmap §5.2 track C). Optional — absent on legacy candidates.
_ENTRY_SIZE_FACTOR_FIELD = b"entry_size_factor"
_MARKET_RISK_GATE_FIELD = b"market_risk_gate"


def _entry_size_factor(fields: dict[bytes, bytes]) -> float:
    """Upstream (decision_engine) entry-size factor, neutral 1.0 default.

    Carries the market-risk gate's enforce-mode size factor (shadow always
    publishes 1.0 — the observed factor lives in the ``market_risk_gate``
    trace payload instead). Missing/invalid/out-of-range values fail open to
    the neutral multiplier so a malformed field can never inflate or zero
    out sizing.
    """
    raw = fields.get(_ENTRY_SIZE_FACTOR_FIELD)
    if not raw:
        return 1.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 1.0
    if not 0.0 < value <= 1.0:
        return 1.0
    return value


def _resolve_mode() -> str:
    """risk_filter mode: off (default, inert) | shadow | live."""
    import os

    mode = os.getenv("FUTURES_RISK_FILTER", "off").strip().lower()
    return mode if mode in ("shadow", "live") else "off"


def _streams_for(mode: str) -> tuple[str, str]:
    """Return (candidate, final) stream names for the mode (F-1).

    shadow → `.shadow`-suffixed isolated streams; live → unsuffixed. Both are
    env-overridable (FUTURES_CANDIDATE_STREAM / FUTURES_FINAL_STREAM), mirroring
    the stock chain.
    """
    import os

    if mode == "shadow":
        candidate = "signal.candidate.futures.shadow"
        final = "signal.final.futures.shadow"
    else:  # live
        candidate = "signal.candidate.futures"
        final = "signal.final.futures"
    return (
        os.getenv("FUTURES_CANDIDATE_STREAM", candidate),
        os.getenv("FUTURES_FINAL_STREAM", final),
    )


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


class RiskFilterDaemon(StreamStage):
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
        super().__init__(
            redis=redis,
            input_stream=candidate_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=0.5,
        )
        self.layer = layer
        self.signals_writer = signals_writer
        self.runtime_state = runtime_state
        self.final_stream = final_stream
        self.final_maxlen = final_maxlen

    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]  # noqa: ARG002
    ) -> bool:
        try:
            signal_id, signal = _signal_from_stream_fields(fields)
        except Exception:
            logger.exception("Unparseable candidate; ACKing as poison-pill")
            return True  # poison-pill: consume (base XACKs)

        try:
            snapshot = await self.runtime_state.snapshot()
            result = self.layer.evaluate(signal, snapshot)
        except Exception:
            logger.exception(
                "Filter evaluation failed signal_id=%s; leaving pending", signal_id
            )
            return False  # leave pending (base does NOT XACK)

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
            return False

        if result.passed:
            try:
                fields_out = signal.to_stream_dict()
                fields_out["signal_id"] = signal_id
                # Multiplicative size composition: the upstream entry factor
                # (market-risk gate enforce size_factor today; any future
                # LLM size factor rides the same field) stacks with the
                # RiskFilterLayer product. Every factor is <= 1.0, so the
                # composition only ever shrinks size — the most conservative
                # verdict wins cumulatively. order_router applies the final
                # product to base_quantity.
                fields_out["size_multiplier"] = str(
                    result.size_multiplier * _entry_size_factor(fields)
                )
                fields_out["filtered_at_ms"] = str(int(time.time() * 1000))
                gate_trace = fields.get(_MARKET_RISK_GATE_FIELD)
                if gate_trace:
                    # Forward the decision trace unchanged — fixed
                    # ``market_risk_gate`` key contract for the /signals
                    # trace lane downstream.
                    fields_out["market_risk_gate"] = (
                        gate_trace.decode("utf-8", errors="replace")
                        if isinstance(gate_trace, bytes)
                        else str(gate_trace)
                    )
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
                return False

        return True  # passed+XADD ok, or rejected (audit-only): consume

    async def on_shutdown(self) -> None:
        await self.signals_writer.flush()


async def _build_and_run() -> int:
    """Production entrypoint. Wires Redis + optional CH + RiskFilterLayer."""
    import os
    import signal as signal_mod
    import socket

    import redis.asyncio as aioredis

    from shared.backtest.signals_writer import SignalsAllWriter
    from shared.risk.config import FuturesRiskConfig, load_trading_windows
    from shared.risk.layer import RiskFilterLayer
    from shared.risk.runtime_state import RuntimeRiskState

    redis_url = redis_url_from_env()
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if mode not in ("shadow", "live"):
        logger.info("FUTURES_RISK_FILTER=%s (off) — risk_filter inert, exiting", mode)
        await redis_client.aclose()
        return 0
    candidate_stream, final_stream = _streams_for(mode)
    risk_state_suffix = "shadow" if mode == "shadow" else ""

    risk_config = FuturesRiskConfig.from_yaml()
    trading_windows = load_trading_windows()
    layer = RiskFilterLayer.from_config(risk_config, trading_windows)
    runtime_state = RuntimeRiskState(
        redis=redis_client, asset_class="futures", key_suffix=risk_state_suffix
    )
    signals_writer = SignalsAllWriter(archive_client=None, batch_size=10)

    worker_id = f"risk-filter-{socket.gethostname()}-{os.getpid()}"
    daemon = RiskFilterDaemon(
        redis=redis_client,
        layer=layer,
        signals_writer=signals_writer,
        runtime_state=runtime_state,
        candidate_stream=candidate_stream,
        final_stream=final_stream,
        consumer_group="risk_filter",
        worker_id=worker_id,
        final_maxlen=10_000,
        xread_block_ms=2000,
        batch_size=10,
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
