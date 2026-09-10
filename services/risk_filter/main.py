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
from shared.risk.layer import LayerResult, RiskFilterLayer

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
from shared.streaming.trading_state import TradingStateReader, ensure_state_key_suffix

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

# Open-position hash owned by ``services/futures_monitor`` (HSET field=symbol on
# an entry fill, HDEL on an exit fill) and already read back by
# ``services/order_router``'s close path. Same env var + default as both of
# those, so an operator override moves all three together.
_FUTURES_POSITIONS_KEY_ENV = "FUTURES_MONITOR_POSITIONS_KEY"
_DEFAULT_FUTURES_POSITIONS_KEY = "futures:monitor:positions"


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


def _rejecting_filter(result: LayerResult) -> str:
    """Name of the filter that rejected *result*, or ``"-"`` when none did.

    ``RiskFilterLayer`` short-circuits, so at most one outcome can carry
    ``passed=False`` and it is always the last one. Falls back to ``"-"`` when
    the layer produced no outcomes at all (empty filter list).
    """
    for outcome in result.filter_outcomes:
        if not outcome.passed:
            return outcome.filter_name
    return "-"


def _outcomes_summary(result: LayerResult) -> str:
    """Compact ``name:pass|fail,...`` trace of every filter that ran.

    Filters after the rejector are absent (short-circuit semantics), so the
    list doubles as "how far down the chain the candidate got".
    """
    if not result.filter_outcomes:
        return "-"
    return ",".join(
        f"{o.filter_name}:{'pass' if o.passed else 'fail'}"
        for o in result.filter_outcomes
    )


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

        # F-9 Gate 1b gap G2 (2026-09-10): the ONLY durable record of a
        # verdict. ``SignalsAllWriter`` is wired with ``archive_client=None``
        # (a no-op stub — ClickHouse is not an active runtime) and there is no
        # metric, so before this line 29 of 30 shadow rejections on 2026-09-10
        # carried no reason anywhere. Unthrottled on purpose: the candidate
        # stream is at most ~1/min, and Gate 1b's "CLOSED = shadow rejection
        # evidence" needs every row, not a sampled one.
        logger.info(
            "risk_filter verdict=%s signal_id=%s setup_type=%s direction=%s "
            "symbol=%s filter=%s reason=%s size_multiplier=%.3f outcomes=%s",
            "passed" if result.passed else "rejected",
            signal_id,
            signal.setup_type,
            signal.direction,
            signal.symbol,
            _rejecting_filter(result),
            result.skip_reason or "-",
            result.size_multiplier,
            _outcomes_summary(result),
        )

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
        from shared.risk.leverage_provider import build_leverage_snapshot_provider
        from shared.risk.product_specs import (
            build_product_specs,
            load_execution_contract_specs,
        )

        margin_config = FuturesMarginConfig.load_or_default()
        execution_specs = load_execution_contract_specs()
        product_specs = build_product_specs(margin_config, execution_specs)
        if not product_specs:
            # F1 (#601 class): an empty spec map means EVERY futures symbol falls
            # back to multiplier 1.0 (~250,000x understatement for a full-size
            # contract) AND the LeverageFilter's per-symbol drift warning never
            # fires (it needs a non-empty product_specs to reach that path), so
            # the understatement would otherwise be *silent*. The filter itself
            # stays fail-open (no hard failure) — this only adds observability.
            logger.warning(
                "futures leverage: 0 product specs resolved from execution.yaml "
                "— leverage will understate, gate ineffective"
            )

        reader = TradingStateReader("futures")
        # F6(a): the equity denominator is the margin config's STATIC fallback,
        # captured once here in a startup lambda. The margin daemon re-reads
        # ``fallback_account_equity_krw`` per compute; today both are identical
        # (both the static fallback — the KIS futures balance endpoint is REST-
        # unstable / mock-blocked). They DIVERGE if the margin lane is later
        # wired to a live broker-equity snapshot (per-compute) while this stays a
        # one-shot capture — unify then (P4-h2 follow-up).
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


def _build_open_position_provider(
    sync_redis: Any, positions_key: str
) -> Callable[[str], bool]:
    """Build the OpenPositionFilter provider for the futures chain.

    Mirrors ``services/stock_risk_filter``'s provider, including its error
    polarity. The data already exists: ``services/futures_monitor`` keeps
    ``futures:monitor:positions`` as a symbol-keyed hash (HSET on an entry fill,
    HDEL on an exit fill), and ``services/order_router`` already reads it back
    on the close path. Both services live in the ``futures-pipeline`` compose
    profile alongside this daemon, and the hash field is the contract symbol —
    the same string ``Signal.symbol`` carries here, since the fill row that
    creates the hash entry is logged with ``symbol=signal.symbol``.

    Without this the layer falls back to ``from_config``'s stub, which reports
    "no position held" for EVERY symbol — not merely an absent filter but a
    disabled duplicate-entry guard.

    A Redis error resolves to "open" (fail-closed), blocking re-entry on
    uncertainty: a duplicated entry is the more expensive mistake, and the
    stock chain already made this call. Sync client because ``layer.evaluate``
    is synchronous.
    """

    def _has_open_position(symbol: str) -> bool:
        try:
            return bool(sync_redis.hexists(positions_key, symbol))
        except Exception:
            logger.warning(
                "Redis error checking open position for %s; "
                "assuming open (fail-closed)",
                symbol,
            )
            return True  # fail-closed: block re-entry on uncertainty

    return _has_open_position


#: Returned (as the sole asset class's count) when Redis is unreachable, so
#: ``ConcurrentPositionsFilter``'s ``>=`` boundary check rejects regardless of
#: the configured cap. The filter itself has a documented fail-OPEN contract
#: (any exception from the provider, or a missing/non-mapping return, passes
#: every signal — see shared/risk/filters/concurrent_positions.py), so
#: matching ``_build_open_position_provider``'s fail-CLOSED polarity has to
#: happen inside this provider: it must never raise, and must return a
#: mapping whose count is large enough to trip both the total and per-asset
#: caps rather than a mapping the filter would treat as "few open positions".
_COUNT_FAIL_CLOSED_SENTINEL = 10**9


def _build_open_positions_count_provider(
    sync_redis: Any, positions_key: str, asset_class: str = _ASSET
) -> Callable[[], Mapping[str, int]]:
    """Build the ``ConcurrentPositionsFilter`` count provider for the futures chain.

    Reads the same ``futures:monitor:positions`` hash
    (``services/futures_monitor`` HSET on entry / HDEL on exit) that
    :func:`_build_open_position_provider` already reads for the per-symbol
    duplicate-entry guard, via ``HLEN`` for the total open-position count.
    This is a read-only accessor — no new Redis key, no write path.

    The provider returns ``{asset_class: count}`` — a single-asset-class
    mapping, since this daemon only ever observes futures positions. Per the
    filter's provider contract (shared/risk/filters/concurrent_positions.py),
    a single-asset daemon's mapping under-counts a true cross-asset
    ``max_total_positions``; this repo has no cross-asset position aggregator
    today, so the total check effectively degrades to "futures-only total"
    until one exists. This is a pre-existing scope limit of the filter design,
    not something this wiring introduces.

    Error polarity matches ``_build_open_position_provider``'s fail-CLOSED
    choice (a duplicated/over-limit entry is the more expensive mistake than
    a blocked one): a Redis error returns an inflated sentinel count rather
    than raising, so it reads as "far over any cap" instead of the filter's
    own default fail-OPEN response to a raised exception or missing mapping.
    """

    def _count() -> Mapping[str, int]:
        try:
            count = int(sync_redis.hlen(positions_key))
        except Exception:
            logger.warning(
                "Redis error counting open futures positions (key=%s); "
                "reporting an inflated count so ConcurrentPositionsFilter "
                "rejects on uncertainty (fail-closed)",
                positions_key,
            )
            return {asset_class: _COUNT_FAIL_CLOSED_SENTINEL}
        return {asset_class: count}

    return _count


def _build_volatility_reference_provider(
    risk_config: FuturesRiskConfig, sync_redis: Any
) -> Callable[[str], Any] | None:
    """Build the VolatilityFilter reference reader for the futures chain.

    Reads ``risk:volatility:reference:futures``, the per-symbol hash published
    by ``services/decision_engine`` (the only futures service that owns a
    ``StreamingIndicatorEngine``, hence the only one that can produce ATR).
    Each field carries the current ATR *and* its percentile threshold together,
    so this daemon cannot arm half of the comparison — see
    :mod:`shared.risk.volatility_reference` for why that matters.

    Gated on the same ``volatility.enabled`` flag that starts the publisher, so
    one operator flip moves both sides. Default ``false`` ⇒ returns ``None`` ⇒
    the filter is built with no provider and passes every signal, exactly as
    the futures chain behaves today. Any wiring failure also returns ``None``
    (fail-open ⇒ inert filter), never a rejection.

    Read-only: it reuses the daemon's existing sync client and writes nothing.
    """
    settings = getattr(risk_config, "volatility", None)
    if settings is None or not settings.enabled:
        return None
    try:
        from shared.risk.volatility_reference import (
            build_volatility_reference_provider,
        )

        provider = build_volatility_reference_provider(
            asset_class="futures",
            settings=settings,
            redis_client=sync_redis,
        )
        logger.info(
            "Futures VolatilityFilter provider wired (percentile=%.1f, "
            "window=%d, min_samples=%d) — publisher: services/decision_engine",
            settings.percentile,
            settings.window_samples,
            settings.min_samples,
        )
        return provider
    except Exception:
        logger.exception(
            "futures volatility reference provider wiring failed; "
            "VolatilityFilter left inert (fail-open)"
        )
        return None


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
    # F-9 Gate 1 gap G3 (2026-09-10): bind the trading-state key suffix BEFORE
    # anything resolves a ``trading:{asset}:*`` key — ``_build_leverage_wiring``
    # below builds a ``TradingStateReader`` whose positions key is resolved from
    # this env var. Without it the shadow chain read the UNSUFFIXED
    # ``trading:futures:positions`` — the monolithic orchestrator's book — so a
    # single orchestrator contract (~5.5x on the 50M denominator) rejected every
    # shadow candidate through the enforce-mode LeverageFilter. Same helper /
    # same semantics as ``services/futures_monitor``.
    ensure_state_key_suffix(mode, label="futures risk filter")
    candidate_stream, final_stream = _streams_for(mode)
    risk_state_suffix = "shadow" if mode == "shadow" else ""
    logger.info(
        "risk_filter mode=%s trading_state_key_suffix=%r "
        "leverage_positions_key=%s monitor_positions_key=%s",
        mode,
        os.environ.get("TRADING_STATE_KEY_SUFFIX", ""),
        TradingStateReader("futures").positions_key,
        os.environ.get(_FUTURES_POSITIONS_KEY_ENV, _DEFAULT_FUTURES_POSITIONS_KEY),
    )

    risk_config = FuturesRiskConfig.from_yaml()
    trading_windows = load_trading_windows()

    # Sync redis for the open-position provider (layer.evaluate is sync).
    from shared.streaming.client import RedisClient

    sync_redis = RedisClient.get_client()
    positions_key = os.environ.get(
        _FUTURES_POSITIONS_KEY_ENV, _DEFAULT_FUTURES_POSITIONS_KEY
    )

    leverage_provider, leverage_product_specs = _build_leverage_wiring(risk_config)
    volatility_provider = _build_volatility_reference_provider(risk_config, sync_redis)
    layer = RiskFilterLayer.from_config(
        risk_config,
        trading_windows,
        has_open_position_provider=_build_open_position_provider(
            sync_redis, positions_key
        ),
        open_positions_count_provider=_build_open_positions_count_provider(
            sync_redis, positions_key
        ),
        leverage_snapshot_provider=leverage_provider,
        leverage_product_specs=leverage_product_specs,
        volatility_reference_provider=volatility_provider,
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
