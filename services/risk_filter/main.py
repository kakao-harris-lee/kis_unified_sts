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
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.config.runtime_defaults import redis_url_from_env
from shared.decision.signal import Signal
from shared.risk.layer import RiskFilterLayer

if TYPE_CHECKING:
    from shared.risk.config import FuturesRiskConfig
    from shared.risk.futures_margin import MarginProductSpec
from shared.risk.runtime_state import RuntimeRiskState
from shared.streaming.approval_gate import (
    ApprovalGateConfig,
    is_gated,
    log_gate_config,
    record_pending,
)
from shared.streaming.stage import StreamStage

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400

# Asset-class tag for the pending-approval hash key / HASH field id (see
# shared/streaming/approval_keys.py). Fixed for this daemon — futures only.
_ASSET = "futures"

# Candidate-stream fields attached by the decision_engine market-risk ENTRY
# gate (roadmap §5.2 track C). Optional — absent on legacy candidates.
_ENTRY_SIZE_FACTOR_FIELD = b"entry_size_factor"
_MARKET_RISK_GATE_FIELD = b"market_risk_gate"
# Structured futures-context trace (roadmap hardening Phase C). Attached by the
# decision_engine; forwarded verbatim to the final stream for the /signals
# trace lane (same passthrough contract as market_risk_gate). Optional.
_FUTURES_CONTEXT_FIELD = b"futures_context"


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
        approval_gate_config: ApprovalGateConfig | None = None,
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
        # Telegram interactive-alerts approval gate (Method A). Defaults to a
        # fully-inert config (enabled=False) so existing behavior is
        # unchanged unless an operator opts a strategy/symbol in.
        self.approval_gate_config = approval_gate_config or ApprovalGateConfig()

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
                context_trace = fields.get(_FUTURES_CONTEXT_FIELD)
                if context_trace:
                    # Forward the Phase C futures-context trace unchanged —
                    # fixed ``futures_context`` key contract for the /signals
                    # trace lane (futures_monitor serializers passthrough).
                    fields_out["futures_context"] = (
                        context_trace.decode("utf-8", errors="replace")
                        if isinstance(context_trace, bytes)
                        else str(context_trace)
                    )
                if is_gated(
                    signal.setup_type, signal.symbol, self.approval_gate_config
                ):
                    # Telegram interactive-alerts approval gate (Method A):
                    # hold the fully-assembled final-stream dict for operator
                    # approval instead of XADDing to signal.final.futures.
                    # The bot replays fields_out verbatim on approval.
                    await record_pending(
                        self.redis,
                        _ASSET,
                        signal_id,
                        fields_out,
                        self.approval_gate_config.pending_ttl_seconds,
                    )
                    return True  # consumed: held pending, not XADDed
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


def _build_leverage_wiring(
    risk_config: FuturesRiskConfig,
) -> tuple[
    Callable[[], Mapping[str, Any] | None] | None,
    Mapping[str, MarginProductSpec] | None,
]:
    """Build the ``(snapshot_provider, product_specs)`` for the LeverageFilter (P5-3).

    Reuses the futures margin read-model's sources so the leverage denominator
    and per-contract multipliers stay consistent with the margin lane — DRY,
    and NO new Redis key:

    * open positions ← the same ``trading:futures:positions`` hash the margin
      publisher reads (:class:`~shared.streaming.trading_state.TradingStateReader`);
      its records already carry ``code`` / ``quantity`` / ``current_price``;
    * account equity ← ``FuturesMarginConfig.fallback_account_equity_krw`` (the
      exact denominator the margin daemon uses when no live broker snapshot is
      available — the futures balance endpoint is REST-unstable / mock-blocked);
    * multiplier map ← :func:`build_product_specs` (execution.yaml contract
      constants merged with margin.yaml rates) — the same spec map the margin
      read-model resolves ``spec_for_symbol`` against.

    Read-only: no order path is touched. Only built when ``leverage.enabled``,
    so the default (disabled) path wires nothing and behaviour is unchanged even
    though the filter itself is never constructed then either. Any failure fails
    OPEN — returns ``(None, None)`` so the filter (if built) stays inert and
    passes every signal — mirroring the fail-open contract in
    ``shared/risk/filters/leverage.py``. Enforcement remains a separate operator
    decision (``leverage.mode`` flip to ``enforce``); this wiring only makes the
    shadow filter able to *compute* gross leverage.
    """
    leverage_settings = getattr(risk_config, "leverage", None)
    if leverage_settings is None or not leverage_settings.enabled:
        return None, None
    try:
        from services.futures_margin_risk.config import FuturesMarginConfig
        from services.futures_margin_risk.main import build_product_specs
        from shared.config.loader import ConfigLoader
        from shared.risk.leverage_provider import build_leverage_snapshot_provider
        from shared.streaming.trading_state import TradingStateReader

        margin_config = FuturesMarginConfig.load_or_default()
        execution_yaml = ConfigLoader.load("execution.yaml")
        execution_specs = (
            execution_yaml.get("futures_contract_spec", {})
            if isinstance(execution_yaml, dict)
            else {}
        )
        product_specs = build_product_specs(margin_config, execution_specs)

        reader = TradingStateReader("futures")
        equity = margin_config.fallback_account_equity_krw
        provider = build_leverage_snapshot_provider(
            positions_provider=reader.get_positions,
            equity_provider=lambda: equity,
        )
        logger.info(
            "LeverageFilter provider wired (mode=%s, equity=%.0f, %d product specs)"
            " — read-only; enforcement still gated by mode=enforce",
            leverage_settings.mode,
            equity,
            len(product_specs),
        )
        return provider, product_specs
    except Exception:
        logger.exception(
            "futures leverage provider wiring failed; LeverageFilter left inert "
            "(fail-open)"
        )
        return None, None


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
    leverage_provider, leverage_product_specs = _build_leverage_wiring(risk_config)
    layer = RiskFilterLayer.from_config(
        risk_config,
        trading_windows,
        leverage_snapshot_provider=leverage_provider,
        leverage_product_specs=leverage_product_specs,
    )
    runtime_state = RuntimeRiskState(
        redis=redis_client, asset_class="futures", key_suffix=risk_state_suffix
    )
    signals_writer = SignalsAllWriter(archive_client=None, batch_size=10)
    # Loaded once at startup (not on the hot path) — inert by default
    # (config/telegram_bot.yaml::approval_gate.enabled = false).
    approval_gate_config = ApprovalGateConfig.from_yaml()
    log_gate_config(approval_gate_config, asset="futures")

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
        approval_gate_config=approval_gate_config,
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
