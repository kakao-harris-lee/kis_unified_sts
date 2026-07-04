"""Evaluation-loop methods for StockStrategyDaemon."""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime
from typing import Any

from shared.risk.market_risk_gate import gate_trace_payload
from shared.strategy.base import EntryContext
from shared.streaming.stock_regime import is_bear_regime
from shared.streaming.stock_signal_eval import (
    OUTCOME_REJECT,
    OUTCOME_SIGNAL,
    REJECT_BEAR_CAP_REACHED,
    REJECT_BEAR_REGIME,
    REJECT_BEAR_RS_GATE,
    REJECT_COLD,
    REJECT_CONDITIONS_NOT_MET,
    REJECT_NO_DAILY_WATCHLIST,
    REJECT_NO_MARKET_DATA,
    REJECT_NO_SMA_200,
    SignalEvalCollector,
)

logger = logging.getLogger("services.stock_strategy.daemon")
_STREAM_TTL_SECONDS = 86400


class StockStrategyEvaluationMixin:
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
        # Market-risk ENTRY gate (roadmap Phase 2C §5.1): evaluated ONCE per
        # cycle after the regime publish (M4-X's bear-exit feed must never be
        # skipped) — the (asset="stock", side="long") verdict is identical for
        # every candidate this cycle, mirroring the once-per-cycle bear gate.
        gate_decision = self._evaluate_market_risk_gate(now)
        gate_trace = (
            gate_trace_payload(gate_decision) if gate_decision is not None else None
        )
        if gate_decision is not None and not gate_decision.allow:
            # enforce mode + blocking rule (stock: HIGH blocks new longs,
            # CRITICAL blocks all new entries). Blanket-reject the cycle via
            # the #483 reject-reason lane with the gate's machine-readable
            # reason. Exits (M4-X) are untouched — the gate is entry-only.
            logger.info(
                "market risk gate: blocking new stock entries — %s",
                gate_decision.reason,
            )
            self._record_blanket_reject(evaluator, roster, gate_decision.reason)
            await self._publish_signal_eval(evaluator, now)
            return 0
        if gate_decision is not None and gate_decision.would_block:
            # shadow mode: would-block is observation-only — log (throttled)
            # and annotate the trace; never reject.
            self._log_market_risk_would_block(gate_decision, now.timestamp())
        # Read the DailyScanner payload once for the whole cycle (not per symbol)
        # so daily-gated strategies see the orchestrator's full daily field set.
        scanner_indicators = await self._load_scanner_daily_indicators()
        technical_published_symbols: set[str] = set()
        for symbol in list(self._universe):
            try:
                if is_bear and symbol not in override_codes:
                    self._record_symbol_reject(
                        evaluator, roster, symbol, REJECT_BEAR_REGIME
                    )
                    continue
                if is_bear and (
                    self._bear_override_config is not None
                    and self._bear_override_config.min_change_pct_for_rs > 0
                ):
                    trade_meta = self._trade_targets_payload.get("metadata", {})
                    symbol_meta = trade_meta.get(symbol, {})
                    raw_change = symbol_meta.get("change_pct")
                    if raw_change is None:
                        logger.debug(
                            "bear RS gate: %s has no change_pct in trade_targets — defaulting to 0.0",
                            symbol,
                        )
                    change_pct = float(raw_change or 0)
                    if change_pct < self._bear_override_config.min_change_pct_for_rs:
                        self._record_symbol_reject(
                            evaluator, roster, symbol, REJECT_BEAR_RS_GATE
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
                regime_value = (
                    regime_payload.get("regime")
                    if isinstance(regime_payload, dict)
                    else None
                )
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
                        # Inject the computed market regime so regime-gated
                        # strategies can evaluate instead of fail-closing every
                        # cycle on a missing key: momentum_breakout's trend-mode
                        # gate reads metadata["regime"]; williams_r's
                        # market_state_filter reads metadata["market_state"].
                        # Without this both returned None unconditionally in the
                        # decoupled pipeline (the no-signal root cause).
                        "regime": regime_value,
                        "market_state": regime_value,
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
                    strategy_name = str(getattr(sig, "strategy", "") or "")
                    # The generator DID fire — mark it so the non-firing
                    # classifier below never double-records this strategy.
                    fired_strategies.add(strategy_name)
                    # Fixed contract with the /signals trace lane: every
                    # candidate carries the gate trace in ALL modes.
                    self._attach_market_risk_trace(sig, gate_trace)
                    if not self._market_risk_gate_admits(sig, gate_decision):
                        # enforce mode + ELEVATED min-confidence: signal
                        # confidence below the mapped threshold → reject via
                        # the #483 reject-reason lane with the gate reason.
                        logger.info(
                            "market risk gate: rejected %s %s "
                            "(confidence=%.2f < min_confidence=%s) — %s",
                            strategy_name,
                            symbol,
                            float(getattr(sig, "confidence", 0.0) or 0.0),
                            gate_decision.min_confidence,  # type: ignore[union-attr]
                            gate_decision.reason,  # type: ignore[union-attr]
                        )
                        self._eval_record(
                            evaluator,
                            strategy_name,
                            symbol,
                            OUTCOME_REJECT,
                            gate_decision.reason,  # type: ignore[union-attr]
                        )
                        continue
                    self._eval_record(
                        evaluator,
                        strategy_name,
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
                    technical_published_symbols.add(symbol)
                    published += 1
                # Classify the non-firing roster strategies for this symbol so
                # "why 0 signals" is answerable per strategy. Read-only — derived
                # entirely from observable state (no generator re-execution).
                self._record_nonfiring_rejects(
                    evaluator, roster, fired_strategies, symbol, indicators
                )
            except Exception:
                logger.exception("stock entry eval failed symbol=%s", symbol)
        try:
            published += await self._publish_llm_discovery_signals(
                scanner_indicators=scanner_indicators,
                now=now,
                evaluator=evaluator,
                allowed_codes=override_codes if is_bear else None,
                excluded_codes=technical_published_symbols,
                gate_decision=gate_decision,
                gate_trace=gate_trace,
            )
        except Exception:
            logger.exception("LLM discovery signal publish failed")
        await self._publish_signal_eval(evaluator, now)
        return published

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
