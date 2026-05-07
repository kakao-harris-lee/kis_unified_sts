"""LLM Context Publisher Service

This service runs UnifiedMarketAnalyzer periodically and publishes MarketContext
to Redis for consumption by trading strategies.

Architecture:
    LLMContextPublisher → UnifiedMarketAnalyzer → MarketAnalysis
    MarketAnalysis → MarketContext conversion
    MarketContext → Redis (via TradingStatePublisher pattern)

Futures-specific behaviour (Phase 1.1-a/b):
    When ``asset_class="futures"`` the publisher injects a futures-focused
    LLM prompt addendum loaded from ``config/llm.yaml::futures.prompt_addendum``.
    This steers the LLM toward KOSPI200 macro/regime classification and intraday
    risk scoring rather than stock-universe quality scoring.

    The periodic analysis interval is 1 h (``analysis_interval_minutes: 60``,
    operator §7-2 decision 2026-05-03).  Additionally, Setup A/C signal adapters
    can request an immediate refresh via ``request_refresh()`` — the method
    serialises concurrent calls so at most one analysis runs at a time.

Usage:
    publisher = LLMContextPublisher("stock")
    context = await publisher.run_analysis()

    # On-demand refresh (e.g. from Setup A/C adapter):
    refreshed = await publisher.request_refresh()
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from shared.llm.config import LLMConfig
from shared.llm.data_classes import MarketAnalysis, MarketSignal, RiskMode
from shared.llm.market_context import MarketContext
from shared.llm.unified_market_analyzer import UnifiedMarketAnalyzer

logger = logging.getLogger(__name__)

# Optional Prometheus
try:
    from prometheus_client import Counter, Gauge

    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    logger.debug("prometheus_client not available, metrics disabled")


class LLMContextPublisher:
    """Publisher service that runs LLM market analysis and publishes MarketContext.

    This service acts as a bridge between the LLM analysis system and the trading
    signal pipeline. It:
    1. Runs UnifiedMarketAnalyzer to get comprehensive market analysis
    2. Converts MarketAnalysis to MarketContext
    3. Publishes to Redis for strategy consumption (via TradingStatePublisher)

    All methods use fire-and-forget error handling: they log errors but never raise,
    ensuring the trading orchestrator is not disrupted by LLM analysis failures.

    Attributes:
        asset_class: Asset class for this publisher ("stock" or "futures").
        config: LLMConfig instance for analysis parameters.
        analyzer: UnifiedMarketAnalyzer instance.
    """

    def __init__(self, asset_class: str, config: Optional[LLMConfig] = None):
        """Initialize LLM context publisher.

        Args:
            asset_class: Asset class to publish context for ("stock" or "futures").
            config: Optional LLMConfig. If None, loads from environment/YAML.
        """
        self.asset_class = asset_class
        self.config = config or LLMConfig.from_env()
        self.analyzer = UnifiedMarketAnalyzer(self.config)

        # Futures-specific prompt addendum (Phase 1.1-a).
        # Non-empty only when asset_class="futures" and the YAML key is set.
        # Loaded from config/llm.yaml::futures.prompt_addendum — never hardcoded.
        self._prompt_addendum: str = (
            (self.config.futures_prompt_addendum or "").strip()
            if asset_class == "futures"
            else ""
        )
        if self._prompt_addendum:
            logger.info(
                "LLMContextPublisher: futures prompt addendum loaded (%d chars)",
                len(self._prompt_addendum),
            )

        # On-demand refresh lock (Phase 1.1-b).
        # Serialises concurrent request_refresh() calls so at most one analysis
        # is in-flight at a time; does not block the periodic loop.
        self._refresh_lock: Optional[asyncio.Lock] = None

        # Setup Prometheus metrics (optional)
        if HAS_PROMETHEUS:
            self._setup_prometheus_metrics()

        logger.info(
            "LLMContextPublisher initialized for %s (provider=%s, model=%s)",
            asset_class,
            self.config.llm_provider,
            self.config.model,
        )

    def _setup_prometheus_metrics(self):
        """Setup Prometheus metrics for LLM context monitoring."""
        # Counters for success/failure tracking
        self.prom_analysis_success = Counter(
            "llm_analysis_success_total",
            "Total successful LLM market analyses",
            ["asset_class"],
        )
        self.prom_analysis_failure = Counter(
            "llm_analysis_failure_total",
            "Total failed LLM market analyses",
            ["asset_class"],
        )

        # Gauge for last update timestamp
        self.prom_last_update_time = Gauge(
            "llm_analysis_last_update_timestamp",
            "Timestamp of last successful LLM analysis (Unix time)",
            ["asset_class"],
        )

        logger.debug(f"Prometheus metrics initialized for LLM context ({self.asset_class})")

    async def run_analysis(self, mode: str = "all") -> Optional[MarketContext]:
        """Run market analysis and return MarketContext.

        This is the main entry point for getting LLM-derived market context.
        It runs the full UnifiedMarketAnalyzer pipeline and converts the result
        to a MarketContext object suitable for strategy consumption.

        When ``asset_class="futures"`` a futures-focused prompt addendum is
        injected (config-driven from ``config/llm.yaml::futures.prompt_addendum``)
        to steer the LLM toward KOSPI200 intraday regime/risk classification.

        Args:
            mode: Analysis mode ("all", "etf", "futures", "options", "bonds", "indices").
                  Default "all" runs comprehensive analysis.

        Returns:
            MarketContext instance if analysis succeeds, None on failure.
            Never raises exceptions (fire-and-forget pattern).
        """
        try:
            logger.debug("Running LLM market analysis (mode=%s, asset=%s)...", mode, self.asset_class)

            # Run unified market analysis (verbose=False for production).
            # Pass the futures-specific prompt addendum when applicable — empty
            # string is a safe no-op for stock mode (UnifiedMarketAnalyzer ignores it).
            market_analysis = self.analyzer.run_analysis(
                mode=mode,
                verbose=False,
                prompt_addendum=self._prompt_addendum,
            )

            # Convert to MarketContext
            market_context = self._convert_analysis(market_analysis)

            logger.info(
                f"LLM analysis complete: regime={market_context.regime}, "
                f"signal={market_context.overall_signal.name}, "
                f"risk_mode={market_context.risk_mode.name}, "
                f"confidence={market_context.confidence:.2f}"
            )

            # Update success metrics
            if HAS_PROMETHEUS:
                self.prom_analysis_success.labels(asset_class=self.asset_class).inc()
                self.prom_last_update_time.labels(asset_class=self.asset_class).set(time.time())

            return market_context

        except Exception as e:
            logger.debug(
                f"LLM market analysis failed: {e}",
                exc_info=True,
            )

            # Update failure metrics
            if HAS_PROMETHEUS:
                self.prom_analysis_failure.labels(asset_class=self.asset_class).inc()

            return None

    def _convert_analysis(self, analysis: MarketAnalysis) -> MarketContext:
        """Convert MarketAnalysis to MarketContext.

        Maps the comprehensive MarketAnalysis output from UnifiedMarketAnalyzer
        to the streamlined MarketContext format used by strategies.

        Mapping logic:
            - regime: Derived from overall_signal strength
            - overall_signal: Direct copy from MarketAnalysis
            - risk_mode: Direct copy from MarketAnalysis
            - risk_score: Calculated from risk_mode (RISK_OFF=75, NEUTRAL=50, RISK_ON=25)
            - confidence: Estimated from analysis completeness and signal strength
            - sector_rotation: Direct copy from MarketAnalysis

        Args:
            analysis: MarketAnalysis from UnifiedMarketAnalyzer.

        Returns:
            MarketContext instance.
        """
        # Derive regime from overall signal strength
        regime = self._derive_regime(analysis.overall_signal)

        # Calculate risk score from risk mode
        risk_score = self._risk_mode_to_score(analysis.risk_mode)

        # Estimate confidence from analysis completeness
        confidence = self._estimate_confidence(analysis)

        # Build metadata from LLM analysis outputs
        metadata = {}
        if analysis.llm_summary:
            metadata["llm_summary"] = analysis.llm_summary[:500]  # Truncate for Redis
        if analysis.llm_strategy:
            metadata["llm_strategy"] = analysis.llm_strategy[:500]
        if analysis.key_points:
            metadata["key_points"] = "; ".join(analysis.key_points[:3])  # Top 3 points

        return MarketContext(
            regime=regime,
            overall_signal=analysis.overall_signal,
            risk_mode=analysis.risk_mode,
            risk_score=risk_score,
            confidence=confidence,
            sector_rotation=analysis.sector_rotation,
            generated_at=datetime.now(),
            metadata=metadata,
        )

    @staticmethod
    def _derive_regime(signal: MarketSignal) -> str:
        """Derive market regime classification from overall signal.

        Maps MarketSignal enum to a regime string that strategies can use
        for decision-making.

        Args:
            signal: MarketSignal enum value.

        Returns:
            Regime string (e.g., "BULL_STRONG", "BEAR_MODERATE", "NEUTRAL").
        """
        regime_map = {
            MarketSignal.STRONG_BULLISH: "BULL_STRONG",
            MarketSignal.BULLISH: "BULL_MODERATE",
            MarketSignal.NEUTRAL: "NEUTRAL",
            MarketSignal.BEARISH: "BEAR_MODERATE",
            MarketSignal.STRONG_BEARISH: "BEAR_STRONG",
        }
        return regime_map.get(signal, "NEUTRAL")

    @staticmethod
    def _risk_mode_to_score(risk_mode: RiskMode) -> float:
        """Convert RiskMode enum to numeric risk score.

        Maps RiskMode to a 0-100 scale where higher values indicate higher risk:
            - RISK_OFF: 75.0 (high risk, defensive positioning)
            - NEUTRAL: 50.0 (moderate risk)
            - RISK_ON: 25.0 (low risk, aggressive positioning)

        Strategies can use this to scale position sizes (lower score = larger size).

        Args:
            risk_mode: RiskMode enum value.

        Returns:
            Risk score from 0-100.
        """
        score_map = {
            RiskMode.RISK_OFF: 75.0,
            RiskMode.NEUTRAL: 50.0,
            RiskMode.RISK_ON: 25.0,
        }
        return score_map.get(risk_mode, 50.0)

    @staticmethod
    def _estimate_confidence(analysis: MarketAnalysis) -> float:
        """Estimate confidence score from analysis completeness.

        Analyzes the MarketAnalysis structure to estimate how confident the
        LLM analysis is based on:
            - Presence of LLM summary/strategy (indicates successful LLM processing)
            - Signal strength (STRONG signals → higher confidence)
            - Data completeness (more data sources → higher confidence)

        Args:
            analysis: MarketAnalysis instance.

        Returns:
            Confidence score from 0.0 (no confidence) to 1.0 (maximum confidence).
        """
        confidence = 0.3  # Base confidence

        # Boost if LLM analysis succeeded
        if analysis.llm_summary and len(analysis.llm_summary) > 50:
            confidence += 0.2
        if analysis.llm_strategy and len(analysis.llm_strategy) > 50:
            confidence += 0.1

        # Boost for strong signals
        if analysis.overall_signal in (MarketSignal.STRONG_BULLISH, MarketSignal.STRONG_BEARISH):
            confidence += 0.2
        elif analysis.overall_signal in (MarketSignal.BULLISH, MarketSignal.BEARISH):
            confidence += 0.1

        # Boost for data completeness
        data_sources = 0
        if analysis.etf_flows:
            data_sources += 1
        if analysis.futures:
            data_sources += 1
        if analysis.options:
            data_sources += 1
        if analysis.bonds:
            data_sources += 1
        if analysis.indices:
            data_sources += 1

        # Add up to 0.2 based on data completeness
        confidence += min(0.2, data_sources * 0.04)

        # Cap at 1.0
        return min(1.0, confidence)

    async def request_refresh(self) -> bool:
        """Request an immediate (on-demand) market analysis refresh.

        Called by Setup A/C signal adapters when a new setup signal arrives,
        so the LLM context is freshened before threshold tuning decisions are
        made (Phase 1.1-b, operator §7-2 decision).

        The method is idempotent under concurrency: if a refresh is already
        in-flight the call returns ``False`` immediately rather than queueing
        another analysis.  This prevents thundering-herd behaviour when multiple
        setup signals fire in quick succession.

        The asyncio.Lock is created lazily on the first call so that the method
        is safe to use from any event loop.

        Returns:
            ``True`` if a fresh analysis was triggered and completed (or
            attempted) by this call, ``False`` if a refresh was already in
            progress and this call was skipped.

        Note:
            This method does *not* block the periodic background loop — the
            loop uses its own ``asyncio.sleep`` cadence and is unaffected by
            on-demand refreshes.
        """
        # Lazy lock initialisation — asyncio.Lock must be created inside a
        # running event loop, which is guaranteed here since this is async.
        if self._refresh_lock is None:
            self._refresh_lock = asyncio.Lock()

        # Atomic try-acquire: a separate ``locked()`` check + ``async with``
        # is racy — two callers can both observe the lock as free before
        # either has acquired it, then run the analysis sequentially under
        # the same lock instead of one returning False.  ``wait_for`` with a
        # tiny timeout collapses the check-and-acquire into a single step:
        # the second caller's acquire times out and returns False without
        # queueing.
        try:
            await asyncio.wait_for(self._refresh_lock.acquire(), timeout=0.001)
        except (TimeoutError, asyncio.TimeoutError):
            logger.debug(
                "LLMContextPublisher.request_refresh: refresh already in-flight "
                "(asset=%s) — skipping duplicate call",
                self.asset_class,
            )
            return False

        try:
            logger.info(
                "LLMContextPublisher.request_refresh: on-demand analysis triggered "
                "(asset=%s)",
                self.asset_class,
            )
            try:
                market_context = await self.run_analysis()
                if market_context:
                    self.publish_to_redis(market_context)
                    logger.info(
                        "LLMContextPublisher.request_refresh: context refreshed "
                        "(asset=%s, regime=%s, confidence=%.2f)",
                        self.asset_class,
                        market_context.regime,
                        market_context.confidence,
                    )
                return True
            except Exception as e:
                logger.debug(
                    "LLMContextPublisher.request_refresh: analysis failed: %s",
                    e,
                    exc_info=True,
                )
                return True  # Lock was acquired; analysis was attempted
        finally:
            self._refresh_lock.release()

    def publish_to_redis(self, context: MarketContext) -> None:
        """Publish MarketContext to Redis.

        Args:
            context: MarketContext to publish.
        """
        try:
            from shared.streaming.trading_state import TradingStatePublisher

            publisher = TradingStatePublisher(self.asset_class)
            publisher.publish_market_context(context)
            logger.debug(
                "Published LLM market context to Redis: asset=%s regime=%s confidence=%.2f",
                self.asset_class,
                context.regime,
                context.confidence,
            )
        except Exception as e:
            logger.debug(
                "Failed to publish LLM market context to Redis: %s",
                e,
                exc_info=True,
            )
