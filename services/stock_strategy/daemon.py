"""StockStrategyDaemon — stock entry-candidate producer (shadow-first).

Owns a daemon-local indicator engine fed by market:ticks (StreamConsumerFeed),
a dynamic screener universe, and the existing StrategyManager. On a decision
cadence it builds an EntryContext per warm symbol and publishes the resulting
orchestrator Signals to signal.candidate.stock(.shadow).

As the only decoupled component with an indicator engine, it also computes the
market-wide regime (median MFI over the universe) and publishes it to Redis for
M4-X's bear exit — see ``shared.streaming.stock_regime``. While the regime is
BEAR_* it skips entry evaluation (``block_entries_in_bear``): long-only entries
in a bear market would be liquidated by M4-X immediately (fee churn).

It additionally consults the shared market-risk ENTRY gate
(``shared.risk.market_risk_gate``, roadmap Phase 2C) once per eval cycle:
every published entry candidate carries the gate trace under
``metadata["market_risk_gate"]`` in ALL modes, and only ``mode: enforce``
(config/market_risk_gate.yaml) may reject entries (HIGH blocks new longs,
CRITICAL blocks all, ELEVATED requires min-confidence). Exit paths (M4-X)
are never gated — the gate is entry-only by contract.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from services.stock_strategy.candidate import stock_signal_to_stream_dict
from services.stock_strategy.daemon_evaluation import StockStrategyEvaluationMixin
from services.stock_strategy.daemon_llm_discovery import StockStrategyLLMDiscoveryMixin
from services.stock_strategy.daemon_market_risk import StockStrategyMarketRiskMixin
from services.stock_strategy.market_risk import MarketRiskGateWiringConfig
from services.stock_strategy.universe import (
    _SCREENER_PAYLOAD_KEY,
    parse_watchlist_codes,
)
from shared.models.signal import Signal
from shared.risk.market_risk_gate import (
    MarketRiskGateConfig,
)
from shared.strategy.symbol_strength import compute_strong_symbols
from shared.streaming.audit import decode_stream_id, format_audit_kv
from shared.streaming.stock_bear_override import (
    BearOverrideConfig,
    compute_override_payload,
)
from shared.streaming.stock_keys import stock_daemon_positions_key
from shared.streaming.stock_regime import (
    StockRegimeConfig,
    compute_regime_payload,
)
from shared.streaming.stock_signal_eval import (
    StockSignalEvalConfig,
)

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400
_KST = ZoneInfo("Asia/Seoul")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("invalid float env %s=%r; using default=%s", name, raw, default)
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid int env %s=%r; using default=%s", name, raw, default)
        return default


@dataclass(frozen=True)
class LLMDiscoverySignalConfig:
    # Ships disabled by default (operator opt-in via env var).
    # Set STOCK_LLM_DISCOVERY_SIGNALS_ENABLED=true to activate.
    enabled: bool = False
    strategy_name: str = "llm_discovered"
    min_llm_quality: float = 0.5
    min_llm_confidence: float = 0.8
    max_per_cycle: int = 5
    cooldown_seconds: float = 86400.0
    quantity: int = 1
    skip_log_interval_seconds: float = 600.0

    @classmethod
    def from_env(cls) -> LLMDiscoverySignalConfig:
        return cls(
            # Opt-in gate: default False — set STOCK_LLM_DISCOVERY_SIGNALS_ENABLED=true
            # to enable LLM-discovery signal emission from the stock strategy daemon.
            enabled=_env_bool("STOCK_LLM_DISCOVERY_SIGNALS_ENABLED", False),
            strategy_name=os.getenv(
                "STOCK_LLM_DISCOVERY_STRATEGY", "llm_discovered"
            ).strip()
            or "llm_discovered",
            min_llm_quality=_env_float("STOCK_LLM_DISCOVERY_MIN_QUALITY", 0.5),
            min_llm_confidence=_env_float("STOCK_LLM_DISCOVERY_MIN_CONFIDENCE", 0.8),
            max_per_cycle=max(0, _env_int("STOCK_LLM_DISCOVERY_MAX_PER_CYCLE", 5)),
            cooldown_seconds=max(
                0.0, _env_float("STOCK_LLM_DISCOVERY_COOLDOWN_SECONDS", 86400.0)
            ),
            quantity=max(1, _env_int("STOCK_LLM_DISCOVERY_QUANTITY", 1)),
            skip_log_interval_seconds=max(
                0.0,
                _env_float("STOCK_LLM_DISCOVERY_SKIP_LOG_INTERVAL_SECONDS", 600.0),
            ),
        )


class StockStrategyDaemon(
    StockStrategyMarketRiskMixin,
    StockStrategyLLMDiscoveryMixin,
    StockStrategyEvaluationMixin,
):
    def __init__(
        self,
        *,
        redis: Any,
        feed: Any,
        engine: Any,
        resolver: Any,
        manager: Any,
        candidate_stream: str,
        candidate_maxlen: int,
        now_fn: Callable[[], datetime],
        eval_interval_seconds: float = 60.0,
        universe_refresh_seconds: float = 30.0,
        max_symbols: int = 40,
        watchlist_reader: Callable[[], Any] | None = None,
        regime_config: StockRegimeConfig | None = None,
        prewarm_fn: Callable[[str], Awaitable[Any]] | None = None,
        max_prewarm_per_cycle: int = 5,
        bear_override_config: BearOverrideConfig | None = None,
        daily_indicators_key: str = "system:daily_indicators:latest",
        signal_eval_config: StockSignalEvalConfig | None = None,
        llm_signal_config: LLMDiscoverySignalConfig | None = None,
        market_risk_gate_config: MarketRiskGateConfig | None = None,
        market_risk_gate_redis: Any | None = None,
        market_risk_wiring: MarketRiskGateWiringConfig | None = None,
    ) -> None:
        self.redis = redis
        self.feed = feed
        self.engine = engine
        self.resolver = resolver
        self.manager = manager
        self.candidate_stream = candidate_stream
        self.candidate_maxlen = candidate_maxlen
        self._now_fn = now_fn
        self._eval_interval = eval_interval_seconds
        self._universe_refresh = universe_refresh_seconds
        self._max_symbols = max_symbols
        self._watchlist_reader = watchlist_reader
        self._regime_config = regime_config
        self._prewarm_fn = prewarm_fn
        self._max_prewarm_per_cycle = max_prewarm_per_cycle
        self._bear_override_config = bear_override_config
        # Redis key for the DailyScanner payload (per-symbol daily_-prefixed
        # indicators: daily_volume_ratio, daily_closes, daily_rsi_14, ...). Same
        # key the bear-override path reads; sourced here independently so the
        # daily merge works even when the bear override is disabled.
        self._daily_indicators_key = daily_indicators_key
        # Read-only per-(symbol, strategy) signal-evaluation observability
        # (stock:daemon:signal_eval). None / disabled → fully inert; recording
        # and publishing never influence the candidate stream.
        self._signal_eval_config = signal_eval_config
        self._llm_signal_config = llm_signal_config or LLMDiscoverySignalConfig()
        # Shared market-risk ENTRY gate (roadmap Phase 2C). The config object is
        # loaded ONCE at startup (main.py) — never re-parsed on the hot path.
        # The gate's Redis read is a sync hgetall by contract, so it gets its
        # own sync client (the async candidate-stream client cannot serve it).
        # Unwired (either is None) → the daemon behaves exactly as before.
        self._market_risk_gate_config = market_risk_gate_config
        self._market_risk_gate_redis = market_risk_gate_redis
        self._market_risk_wiring = market_risk_wiring or MarketRiskGateWiringConfig()
        # Throttle cache for shadow-mode would-block logs (reason → last ts),
        # mirroring the _llm_skip_log_cache throttled-logging pattern.
        self._market_risk_log_cache: dict[str, float] = {}
        self._universe: list[str] = []
        # Raw watchlist payload ({"strategies": {...}}) from the last refresh.
        # Injected into EntryContext.metadata so daily-watchlist-gated strategies
        # (e.g. momentum_breakout) see the same shape the orchestrator provides.
        self._watchlist: dict[str, Any] = {}
        self._trade_targets_payload: dict[str, Any] = {}
        # Redis hash key for LLM-discovery cooldown (symbol → last_published_epoch).
        # Persisted to Redis DB1 so daemon restarts honour the 24h cooldown.
        # In-memory fast-path kept as _llm_last_published_cache; Redis is source of truth.
        self._llm_cooldown_key = "stock:daemon:llm_cooldown"
        self._llm_last_published_cache: dict[str, float] = {}
        self._llm_skip_log_cache: dict[tuple[str, str], float] = {}
        self._stop = asyncio.Event()

    async def _apply_watchlist(self, raw: Any) -> None:
        codes = parse_watchlist_codes(raw, max_symbols=self._max_symbols)
        if not codes:
            return  # keep prior universe
        self._universe = codes
        # Retain the raw watchlist dict for EntryContext.metadata injection
        # (daily-watchlist strategy gate). Non-dict payloads → empty dict so
        # those strategies fall back to dynamic mode (bypass the gate).
        self._watchlist = raw if isinstance(raw, dict) else {}
        payload = (
            self._watchlist.get(_SCREENER_PAYLOAD_KEY)
            if isinstance(self._watchlist, dict)
            else None
        )
        self._trade_targets_payload = payload if isinstance(payload, dict) else {}
        self.feed.update_symbols(codes)
        await self._prewarm_cold()

    async def _load_scanner_daily_indicators(self) -> dict[str, dict[str, Any]]:
        """Load the DailyScanner per-symbol payload once (graceful on miss/stale).

        Returns ``{symbol: {daily_*: value}}`` from ``system:daily_indicators:latest``.
        The scanner fields are already ``daily_``-prefixed (daily_volume_ratio,
        daily_closes, daily_rsi_14, ...). Any missing/stale/malformed payload
        returns ``{}`` so the daily merge falls back to engine-only (no crash).
        Read once per evaluation cycle, not per symbol.
        """
        try:
            raw = await self.redis.get(self._daily_indicators_key)
        except Exception:
            logger.exception("daily-scanner read failed")
            return {}
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("daily-scanner payload is not valid JSON; ignoring")
            return {}
        indicators = payload.get("indicators", {}) if isinstance(payload, dict) else {}
        return indicators if isinstance(indicators, dict) else {}

    def _merge_daily_indicators(
        self,
        symbol: str,
        indicators: dict[str, Any],
        scanner_indicators: dict[str, dict[str, Any]],
    ) -> None:
        """Merge both daily sources into ``indicators`` in place (orchestrator parity).

        Mirrors the orchestrator hot path (orchestrator.py ~6221-6233), which
        merges TWO sources so daily-gated strategies see the full field set:

        1. DailyScanner Redis payload (already ``daily_``-prefixed) first — carries
           the richer set the engine does not compute: ``daily_volume_ratio``
           (momentum_breakout's risk filter), ``daily_closes`` (pattern_pullback
           60d return), ``daily_sma_60_prev``, ``daily_rsi_14``, etc. Without it
           those filters fail open / degrade to defaults.
        2. Engine ``get_daily_indicators`` second (``daily_`` prefix), so live
           recomputed values win on overlap — same precedence as the orchestrator.

        ``PatternPullback._get`` resolves both ``sma_200`` and ``daily_sma_200``,
        so the prefixed values satisfy its base-trend gate (the no-signal bug).

        ``get_daily_indicators`` is cached per-symbol by daily candle count
        (StreamingIndicatorEngine._momentum_cache), so repeated per-cycle calls
        are cheap — it recomputes only when the daily candle count changes
        (once per day).
        """
        # Source 1: DailyScanner payload (already daily_-prefixed) — merge raw.
        scanner = scanner_indicators.get(symbol)
        if isinstance(scanner, dict):
            indicators.update(scanner)

        # Source 2: engine daily indicators (daily_ prefix) — merged last (wins).
        get_daily = getattr(self.engine, "get_daily_indicators", None)
        if get_daily is None:
            return
        try:
            daily = get_daily(symbol)
        except Exception:
            logger.exception("daily indicator fetch failed symbol=%s", symbol)
            return
        for key, value in (daily or {}).items():
            indicators[f"daily_{key}"] = value

    async def _prewarm_cold(self) -> None:
        """Warm universe symbols that are not yet warm (≤ cap per cycle).

        Warmth-based, not membership-based: this naturally covers newly-added
        symbols and earlier REST-missed/over-cap ones (they stay cold and are
        retried next refresh until warm or dropped from the universe).

        Called from both ``_apply_watchlist`` (universe refresh, ~30s) and
        ``evaluate_once`` (each eval cycle, ~60s) so intraday screener adds
        that missed parquet data get a prewarm attempt every cycle, not only on
        universe changes.
        """
        if self._prewarm_fn is None:
            return
        cold = [s for s in self._universe if not self.engine.is_warm(s)]
        if cold:
            logger.debug(
                "prewarm: %d cold symbol(s) in universe (cap=%d): %s",
                len(cold),
                self._max_prewarm_per_cycle,
                cold[: self._max_prewarm_per_cycle],
            )
        for symbol in cold[: self._max_prewarm_per_cycle]:
            try:
                await self._prewarm_fn(symbol)
            except Exception:
                logger.exception("prewarm failed symbol=%s", symbol)

    async def _publish_regime(self, now: datetime) -> dict[str, Any] | None:
        """Compute + publish the market regime; return the payload (None if off).

        Compute failures log and return None — entry evaluation proceeds
        ungated, and M4-X's staleness gate covers the missed publish. A
        publish (``redis.set``) failure still returns the locally computed
        payload so the bear entry gate keeps working: M4-X may still act on
        the previous fresh payload, and entering long during BEAR in that
        window is exactly the fee churn the gate prevents.
        """
        cfg = self._regime_config
        if cfg is None or not cfg.enabled:
            return None
        get_mfi = getattr(self.engine, "get_market_mfi_values", None)
        if get_mfi is None:
            return None
        try:
            mfi_by_symbol = get_mfi(set(self._universe))
            payload = compute_regime_payload(
                mfi_by_symbol,
                config=cfg,
                now_ms=int(now.timestamp() * 1000),
            )
        except Exception:
            logger.exception("stock regime compute failed")
            return None
        try:
            await self.redis.set(
                cfg.redis_key, json.dumps(payload), ex=cfg.publish_ttl_seconds
            )
        except Exception:
            logger.exception("stock regime publish failed")
        return payload

    async def _publish_strong_set(self, now: datetime) -> set[str]:
        """Compute strong symbols from daily indicators and publish to Redis.

        Returns the strong set. Any compute/publish failure returns an empty set
        so the caller treats it as "no strong symbols" → blanket bear block
        (fail-safe).
        """
        cfg = self._bear_override_config
        if cfg is None or not cfg.enabled:
            return set()
        try:
            raw = await self.redis.get(cfg.daily_indicators_key)
            indicators = json.loads(raw).get("indicators", {}) if raw else {}
            strong = compute_strong_symbols(indicators, cfg.criteria)
        except Exception:
            logger.exception("strong-set compute failed")
            return set()
        try:
            payload = compute_override_payload(
                strong, now_ms=int(now.timestamp() * 1000)
            )
            await self.redis.set(
                cfg.redis_key, json.dumps(payload), ex=cfg.publish_ttl_seconds
            )
        except Exception:
            logger.exception("strong-set publish failed")
        return strong

    async def _override_count(self, strong: set[str]) -> int:
        """Count open positions whose code is in the strong set.

        Read failure → returns a very large number (cap-reached) so no new
        override entries are admitted (conservative/fail-safe).
        """
        try:
            open_codes = await self.redis.hkeys(stock_daemon_positions_key())
        except Exception:
            logger.exception("positions hash read failed; treating cap as reached")
            return 1 << 30
        decoded = {
            (c.decode() if isinstance(c, (bytes, bytearray)) else str(c))
            for c in (open_codes or [])
        }
        return len(decoded & strong)

    # ------------------------------------------------------------------
    # Market-risk ENTRY gate (shared/risk/market_risk_gate, roadmap Phase 2C)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Signal-eval observability (read-only; never affects the candidate stream)
    # ------------------------------------------------------------------

    async def _publish(self, signal: Signal) -> None:
        fields = stock_signal_to_stream_dict(signal, signal_id=uuid.uuid4().hex)
        msg_id = await self.redis.xadd(
            self.candidate_stream,
            fields,
            maxlen=self.candidate_maxlen,
            approximate=True,
        )
        await self.redis.expire(self.candidate_stream, _STREAM_TTL_SECONDS)
        logger.info(
            format_audit_kv(
                event="signal_published",
                stream=self.candidate_stream,
                msg_id=decode_stream_id(msg_id),
                signal_id=fields.get("signal_id"),
                code=fields.get("code"),
                strategy=fields.get("strategy"),
                direction=fields.get("direction"),
            )
        )

    async def _refresh_loop(self) -> None:
        while not self._stop.is_set():
            if self._watchlist_reader is not None:
                try:
                    await self._apply_watchlist(self._watchlist_reader())
                except Exception:
                    logger.exception("watchlist refresh failed; keeping prior universe")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self._universe_refresh
                )

    async def run(self) -> None:
        await self.feed.start()
        refresh_task = asyncio.create_task(self._refresh_loop())
        try:
            while not self._stop.is_set():
                await self.evaluate_once()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self._eval_interval
                    )
        finally:
            refresh_task.cancel()
            await asyncio.gather(refresh_task, return_exceptions=True)
            await self.feed.stop()

    async def stop(self) -> None:
        self._stop.set()
