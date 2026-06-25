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
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from services.stock_strategy.candidate import stock_signal_to_stream_dict
from services.stock_strategy.universe import parse_watchlist_codes
from shared.models.signal import Signal
from shared.strategy.base import EntryContext
from shared.strategy.symbol_strength import compute_strong_symbols
from shared.streaming.stock_bear_override import (
    BearOverrideConfig,
    compute_override_payload,
)
from shared.streaming.stock_keys import stock_daemon_positions_key
from shared.streaming.stock_regime import (
    StockRegimeConfig,
    compute_regime_payload,
    is_bear_regime,
)
from shared.streaming.stock_signal_eval import (
    OUTCOME_REJECT,
    OUTCOME_SIGNAL,
    REJECT_BEAR_CAP_REACHED,
    REJECT_BEAR_REGIME,
    REJECT_COLD,
    REJECT_CONDITIONS_NOT_MET,
    REJECT_NO_DAILY_WATCHLIST,
    REJECT_NO_MARKET_DATA,
    REJECT_NO_SMA_200,
    SignalEvalCollector,
    StockSignalEvalConfig,
)

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400


class StockStrategyDaemon:
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
        self._universe: list[str] = []
        # Raw watchlist payload ({"strategies": {...}}) from the last refresh.
        # Injected into EntryContext.metadata so daily-watchlist-gated strategies
        # (e.g. momentum_breakout) see the same shape the orchestrator provides.
        self._watchlist: dict[str, Any] = {}
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

    async def evaluate_once(self) -> int:
        """Build context + check_entries per warm symbol; publish. Returns #published."""
        published = 0
        now = self._now_fn()
        # Prewarm any cold universe symbols before evaluation — mirrors
        # ``_apply_watchlist`` but runs every eval cycle so intraday-added
        # symbols (screener surge adds, not in parquet) get a prewarm attempt
        # on every evaluation pass, not only when the universe changes.  Best-
        # effort: failures are logged inside ``_prewarm_cold``.
        await self._prewarm_cold()
        # Read-only per-(symbol, strategy) eval collector for this cycle. None
        # when observability is off; recording is a no-op via _eval_record so
        # the entry path is identical whether or not it is enabled.
        evaluator = (
            SignalEvalCollector()
            if (self._signal_eval_config and self._signal_eval_config.enabled)
            else None
        )
        roster = self._strategy_roster()
        regime_payload = await self._publish_regime(now)
        is_bear = (
            regime_payload is not None
            and self._regime_config is not None
            and self._regime_config.block_entries_in_bear
            and is_bear_regime(regime_payload.get("regime"))
        )
        strong = (
            await self._publish_strong_set(now)
            if (self._bear_override_config and self._bear_override_config.enabled)
            else set()
        )
        override_codes: set[str] = set()
        if is_bear:
            if not strong:
                logger.info(
                    "bear regime %s (mfi=%s, symbols=%s) — skipping entry evaluation",
                    regime_payload.get("regime"),
                    regime_payload.get("mfi"),
                    regime_payload.get("mfi_symbols"),
                )
                self._record_blanket_reject(evaluator, roster, REJECT_BEAR_REGIME)
                await self._publish_signal_eval(evaluator, now)
                return 0
            cap = self._bear_override_config.max_override_positions  # type: ignore[union-attr]
            if await self._override_count(strong) >= cap:
                logger.info(
                    "bear override: cap %d reached — no new override entries", cap
                )
                self._record_blanket_reject(evaluator, roster, REJECT_BEAR_CAP_REACHED)
                await self._publish_signal_eval(evaluator, now)
                return 0
            override_codes = strong
            logger.info(
                "bear override: %d strong symbol(s) — evaluating %s",
                len(strong),
                sorted(strong),
            )
        # Read the DailyScanner payload once for the whole cycle (not per symbol)
        # so daily-gated strategies see the orchestrator's full daily field set.
        scanner_indicators = await self._load_scanner_daily_indicators()
        for symbol in list(self._universe):
            try:
                if is_bear and symbol not in override_codes:
                    self._record_symbol_reject(
                        evaluator, roster, symbol, REJECT_BEAR_REGIME
                    )
                    continue
                if not self.engine.is_warm(symbol):
                    self._record_symbol_reject(evaluator, roster, symbol, REJECT_COLD)
                    continue
                market_data = await self.feed.get_current_price(symbol)
                if not market_data:
                    self._record_symbol_reject(
                        evaluator, roster, symbol, REJECT_NO_MARKET_DATA
                    )
                    continue
                indicators = self.resolver.collect_entry_indicators(symbol)
                # Inject both daily sources (scanner payload + engine) so
                # daily-gated strategies (pattern_pullback sma_200,
                # momentum_breakout daily_volume_ratio) can evaluate; without
                # this every symbol is rejected (no_sma_200) and the configured
                # daily-volume filter fails open — the decoupled no-signal root
                # cause. Mirrors the orchestrator's two-source merge.
                self._merge_daily_indicators(symbol, indicators, scanner_indicators)
                ctx = EntryContext(
                    market_data=market_data,
                    indicators=indicators,
                    current_positions=[],
                    timestamp=now,
                    metadata={
                        "shadow": True,
                        # Per-strategy daily watchlist gate (e.g.
                        # momentum_breakout). Empty → strategy runs dynamic mode.
                        "daily_watchlist": self._watchlist,
                    },
                )
                signals = await self.manager.check_entries(ctx)
                fired_strategies: set[str] = set()
                for sig in signals or []:
                    if is_bear:
                        with contextlib.suppress(Exception):
                            sig.metadata["bear_override"] = (
                                True  # best-effort; tag is observability only
                            )
                    fired_strategies.add(str(getattr(sig, "strategy", "") or ""))
                    self._eval_record(
                        evaluator,
                        str(getattr(sig, "strategy", "") or ""),
                        symbol,
                        OUTCOME_SIGNAL,
                        (
                            str(
                                getattr(sig, "metadata", {}).get(
                                    "signal_direction", "long"
                                )
                            )
                            if isinstance(getattr(sig, "metadata", None), dict)
                            else "long"
                        ),
                    )
                    await self._publish(sig)
                    published += 1
                # Classify the non-firing roster strategies for this symbol so
                # "why 0 signals" is answerable per strategy. Read-only — derived
                # entirely from observable state (no generator re-execution).
                self._record_nonfiring_rejects(
                    evaluator, roster, fired_strategies, symbol, indicators
                )
            except Exception:
                logger.exception("stock entry eval failed symbol=%s", symbol)
        await self._publish_signal_eval(evaluator, now)
        return published

    # ------------------------------------------------------------------
    # Signal-eval observability (read-only; never affects the candidate stream)
    # ------------------------------------------------------------------

    def _strategy_roster(self) -> dict[str, Any]:
        """Return the manager's strategy roster ({name: strategy}) if exposed.

        Legacy/fake managers without ``.strategies`` return ``{}`` → only fired
        strategies are recorded (graceful degradation).
        """
        roster = getattr(self.manager, "strategies", None)
        return dict(roster) if isinstance(roster, dict) else {}

    @staticmethod
    def _eval_record(
        evaluator: SignalEvalCollector | None,
        strategy: str,
        symbol: str,
        outcome: str,
        reason: str,
    ) -> None:
        """Record one outcome when observability is enabled (no-op otherwise)."""
        if evaluator is None or not strategy:
            return
        evaluator.record(strategy, symbol, outcome, reason)

    def _record_symbol_reject(
        self,
        evaluator: SignalEvalCollector | None,
        roster: dict[str, Any],
        symbol: str,
        reason: str,
    ) -> None:
        """Record a single (skipped) symbol's reject across all roster strategies."""
        if evaluator is None:
            return
        for name in roster:
            evaluator.record(name, symbol, OUTCOME_REJECT, reason)

    def _record_blanket_reject(
        self,
        evaluator: SignalEvalCollector | None,
        roster: dict[str, Any],
        reason: str,
    ) -> None:
        """Record the same reject for every universe symbol × roster strategy.

        Used for early-return cycles (bear gate) so the operator still sees the
        per-strategy count and the dominant reason for the whole cycle.
        """
        if evaluator is None:
            return
        for symbol in list(self._universe):
            for name in roster:
                evaluator.record(name, symbol, OUTCOME_REJECT, reason)

    def _record_nonfiring_rejects(
        self,
        evaluator: SignalEvalCollector | None,
        roster: dict[str, Any],
        fired_strategies: set[str],
        symbol: str,
        indicators: dict[str, Any],
    ) -> None:
        """Classify each non-firing roster strategy's reject reason for a symbol.

        Faithful daemon-boundary classification — derived purely from observable
        state, never by re-running a generator (which would double-set firing
        cooldowns). Reasons, in precedence order:

        * ``no_daily_watchlist`` — the strategy is daily-gated (its name is a key
          in ``watchlist["strategies"]``) and this symbol is not on its list.
        * ``no_sma_200`` — the strategy *requires* ``sma_200`` (per its
          ``required_indicators``) but neither ``sma_200`` nor ``daily_sma_200``
          is present, so its base-trend gate is dead (the diagnosis's headline
          reject). Only attributed to SMA(200)-dependent strategies so it never
          over-counts for strategies that ignore SMA(200) (e.g. momentum_breakout,
          williams_r).
        * ``conditions_not_met`` — the residual: the strategy ran but no entry
          condition matched (threshold / RVOL / breakout / etc.).
        """
        if evaluator is None or not roster:
            return
        has_sma_200 = self._has_sma_200(indicators)
        gated = self._daily_gated_strategies()
        sma200_dependent = self._sma200_dependent_strategies(roster)
        for name in roster:
            if name in fired_strategies:
                continue
            reason = self._reject_reason_for(
                name, symbol, gated, has_sma_200, sma200_dependent
            )
            evaluator.record(name, symbol, OUTCOME_REJECT, reason)

    @staticmethod
    def _has_sma_200(indicators: dict[str, Any]) -> bool:
        """True when a usable (>0) daily SMA(200) is present under either key."""
        for key in ("sma_200", "daily_sma_200"):
            value = indicators.get(key)
            if value is None:
                continue
            try:
                if float(value) > 0:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    def _daily_gated_strategies(self) -> dict[str, set[str]]:
        """Map each daily-gated strategy → its allowed symbol set (this cycle).

        A strategy is daily-gated only when it has a NON-EMPTY candidate list in
        the current watchlist's ``strategies`` map — mirroring
        ``daily_watchlist_allows`` (the per-strategy gate the entry strategies
        apply). An empty/absent list → dynamic mode (no gating), so the reject
        classifier attributes the real reason (e.g. ``no_sma_200`` /
        ``conditions_not_met``) instead of masking it with ``no_daily_watchlist``.
        """
        strategies = (
            self._watchlist.get("strategies", {})
            if isinstance(self._watchlist, dict)
            else {}
        )
        if not isinstance(strategies, dict):
            return {}
        return {
            name: {str(c) for c in codes}
            for name, codes in strategies.items()
            if isinstance(codes, list) and codes  # skip empty → dynamic, not gated
        }

    @staticmethod
    def _sma200_dependent_strategies(roster: dict[str, Any]) -> set[str]:
        """Names of roster strategies whose required_indicators include sma_200.

        Used so ``no_sma_200`` is attributed only to strategies that actually
        gate on SMA(200) (e.g. pattern_pullback), not to strategies that ignore
        it (e.g. momentum_breakout, williams_r) — which would over-count the
        diagnosis's headline reject. A strategy whose required keys cannot be
        read is treated as non-dependent (falls through to conditions_not_met).
        """
        dependent: set[str] = set()
        for name, strategy in roster.items():
            try:
                required = getattr(strategy, "required_indicators", None) or ()
                keys = {str(k) for k in required}
            except Exception:
                continue
            if "sma_200" in keys or "daily_sma_200" in keys:
                dependent.add(name)
        return dependent

    @staticmethod
    def _reject_reason_for(
        name: str,
        symbol: str,
        gated: dict[str, set[str]],
        has_sma_200: bool,
        sma200_dependent: set[str],
    ) -> str:
        allowed = gated.get(name)
        if allowed is not None and symbol not in allowed:
            return REJECT_NO_DAILY_WATCHLIST
        if name in sma200_dependent and not has_sma_200:
            return REJECT_NO_SMA_200
        return REJECT_CONDITIONS_NOT_MET

    async def _publish_signal_eval(
        self, evaluator: SignalEvalCollector | None, now: datetime
    ) -> None:
        """Publish the aggregated eval hash with TTL (best-effort; throttled 1/cycle).

        Observability only — a publish failure logs at debug and never affects
        the candidate stream.
        """
        cfg = self._signal_eval_config
        if evaluator is None or cfg is None or not cfg.enabled or evaluator.is_empty():
            return
        try:
            payload = evaluator.to_payload(now=now)
            if not payload:
                return
            await self.redis.hset(cfg.redis_key, mapping=payload)
            await self.redis.expire(cfg.redis_key, cfg.publish_ttl_seconds)
        except Exception:
            logger.debug("stock signal-eval publish failed", exc_info=True)

    async def _publish(self, signal: Signal) -> None:
        fields = stock_signal_to_stream_dict(signal, signal_id=uuid.uuid4().hex)
        await self.redis.xadd(
            self.candidate_stream,
            fields,
            maxlen=self.candidate_maxlen,
            approximate=True,
        )
        await self.redis.expire(self.candidate_stream, _STREAM_TTL_SECONDS)

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
