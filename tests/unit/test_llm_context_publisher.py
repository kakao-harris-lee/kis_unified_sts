"""Unit tests for services/trading/llm_context_publisher.py

Covers Phase 1.1-a (futures analysis branch + prompt addendum) and
Phase 1.1-b (1h interval config, request_refresh idempotence).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from services.trading.llm_context_publisher import LLMContextPublisher
from shared.llm.config import LLMConfig
from shared.llm.data_classes import MarketSignal, RiskMode
from shared.llm.market_context import MarketContext


# =============================================================================
# Helpers
# =============================================================================


def _make_llm_config(
    futures_prompt_addendum: str = "",
) -> LLMConfig:
    """Create a minimal LLMConfig for testing.

    Uses all defaults except for the futures prompt addendum.
    """
    return LLMConfig(
        futures_prompt_addendum=futures_prompt_addendum,
        llm_provider="openai",
        api_key="",  # No real API key — LLM client will be None
        model="gpt-4o-mini",
    )


def _make_market_context(
    regime: str = "NEUTRAL",
    risk_score: float = 50.0,
    confidence: float = 0.6,
) -> MarketContext:
    """Create a sample MarketContext for testing."""
    return MarketContext(
        regime=regime,
        overall_signal=MarketSignal.NEUTRAL,
        risk_mode=RiskMode.NEUTRAL,
        risk_score=risk_score,
        confidence=confidence,
        sector_rotation={},
        generated_at=datetime(2026, 5, 4, 10, 0, 0),
        metadata={},
    )


# =============================================================================
# Phase 1.1-a: Futures analysis branch + prompt addendum
# =============================================================================


class TestFuturesPromptAddendum:
    """Verify that the futures prompt addendum is loaded from config and passed
    through to UnifiedMarketAnalyzer only when asset_class='futures'."""

    def test_stock_publisher_has_no_addendum(self):
        """Stock publisher ignores futures.prompt_addendum in config."""
        config = _make_llm_config(futures_prompt_addendum="some futures addendum")
        publisher = LLMContextPublisher("stock", config=config)

        # Stock mode must NOT inject the addendum
        assert publisher._prompt_addendum == ""

    def test_futures_publisher_loads_addendum_from_config(self):
        """Futures publisher loads addendum from LLMConfig.futures_prompt_addendum."""
        addendum = (
            "You are analyzing for KOSPI200 futures intraday trading.\n"
            "Focus on regime and risk_score."
        )
        config = _make_llm_config(futures_prompt_addendum=addendum)
        publisher = LLMContextPublisher("futures", config=config)

        assert publisher._prompt_addendum == addendum.strip()

    def test_futures_publisher_empty_addendum_when_config_unset(self):
        """Futures publisher has empty addendum when config field is blank."""
        config = _make_llm_config(futures_prompt_addendum="")
        publisher = LLMContextPublisher("futures", config=config)

        assert publisher._prompt_addendum == ""

    def test_futures_publisher_strips_whitespace_from_addendum(self):
        """Futures publisher strips leading/trailing whitespace from addendum."""
        addendum = "  KOSPI200 futures focus.  \n"
        config = _make_llm_config(futures_prompt_addendum=addendum)
        publisher = LLMContextPublisher("futures", config=config)

        assert publisher._prompt_addendum == addendum.strip()

    @pytest.mark.asyncio
    async def test_futures_run_analysis_passes_addendum_to_analyzer(self):
        """run_analysis() for futures passes _prompt_addendum to analyzer.run_analysis()."""
        addendum = "KOSPI200 futures focus"
        config = _make_llm_config(futures_prompt_addendum=addendum)
        publisher = LLMContextPublisher("futures", config=config)

        # Patch the analyzer's run_analysis to capture keyword arguments
        mock_analysis = MagicMock()
        mock_analysis.overall_signal = MarketSignal.NEUTRAL
        mock_analysis.risk_mode = RiskMode.NEUTRAL
        mock_analysis.llm_summary = ""
        mock_analysis.llm_strategy = ""
        mock_analysis.key_points = []
        mock_analysis.etf_flows = []
        mock_analysis.futures = None
        mock_analysis.options = None
        mock_analysis.bonds = None
        mock_analysis.indices = []
        mock_analysis.sector_rotation = {}

        publisher.analyzer.run_analysis = Mock(return_value=mock_analysis)

        await publisher.run_analysis()

        publisher.analyzer.run_analysis.assert_called_once()
        _, kwargs = publisher.analyzer.run_analysis.call_args
        assert kwargs.get("prompt_addendum") == addendum.strip()

    @pytest.mark.asyncio
    async def test_stock_run_analysis_passes_empty_addendum_to_analyzer(self):
        """run_analysis() for stock passes empty string as addendum."""
        config = _make_llm_config(futures_prompt_addendum="irrelevant futures text")
        publisher = LLMContextPublisher("stock", config=config)

        mock_analysis = MagicMock()
        mock_analysis.overall_signal = MarketSignal.NEUTRAL
        mock_analysis.risk_mode = RiskMode.NEUTRAL
        mock_analysis.llm_summary = ""
        mock_analysis.llm_strategy = ""
        mock_analysis.key_points = []
        mock_analysis.etf_flows = []
        mock_analysis.futures = None
        mock_analysis.options = None
        mock_analysis.bonds = None
        mock_analysis.indices = []
        mock_analysis.sector_rotation = {}

        publisher.analyzer.run_analysis = Mock(return_value=mock_analysis)

        await publisher.run_analysis()

        _, kwargs = publisher.analyzer.run_analysis.call_args
        assert kwargs.get("prompt_addendum") == ""

    @pytest.mark.asyncio
    async def test_futures_run_analysis_returns_market_context_with_all_fields(self):
        """run_analysis() for futures returns MarketContext with all expected fields."""
        config = _make_llm_config(futures_prompt_addendum="KOSPI200 focus")
        publisher = LLMContextPublisher("futures", config=config)

        mock_analysis = MagicMock()
        mock_analysis.overall_signal = MarketSignal.BULLISH
        mock_analysis.risk_mode = RiskMode.RISK_ON
        mock_analysis.llm_summary = "Market is bullish with strong momentum" * 3
        mock_analysis.llm_strategy = "Buy on dips with tight stops" * 3
        mock_analysis.key_points = ["Point 1", "Point 2"]
        mock_analysis.etf_flows = [MagicMock()]
        mock_analysis.futures = MagicMock()
        mock_analysis.options = None
        mock_analysis.bonds = MagicMock(risk_mode=RiskMode.RISK_ON)
        mock_analysis.indices = []
        mock_analysis.sector_rotation = {"Technology": "INFLOW"}

        publisher.analyzer.run_analysis = Mock(return_value=mock_analysis)

        context = await publisher.run_analysis()

        assert context is not None
        assert isinstance(context, MarketContext)
        # Regime, risk_mode, risk_score must all be populated
        assert context.regime in (
            "BULL_STRONG", "BULL_MODERATE", "NEUTRAL",
            "BEAR_MODERATE", "BEAR_STRONG",
        )
        assert context.risk_mode == RiskMode.RISK_ON
        assert 0 <= context.risk_score <= 100
        assert 0.0 <= context.confidence <= 1.0


# =============================================================================
# Phase 1.1-b: 1h interval config
# =============================================================================


class TestAnalysisIntervalConfig:
    """Verify analysis_interval_minutes is 60 in config/llm.yaml."""

    def test_config_yaml_interval_is_60_minutes(self):
        """config/llm.yaml::market_context_publisher.analysis_interval_minutes == 60."""
        from pathlib import Path
        import yaml

        config_path = (
            Path(__file__).resolve().parents[2]
            / "config"
            / "llm.yaml"
        )
        assert config_path.exists(), f"config/llm.yaml not found at {config_path}"

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        publisher_config = data.get("market_context_publisher", {})
        interval = publisher_config.get("analysis_interval_minutes")

        assert interval == 60, (
            f"Expected analysis_interval_minutes=60 (operator §7-2), got {interval}"
        )

    def test_config_yaml_futures_prompt_addendum_present(self):
        """config/llm.yaml::futures.prompt_addendum is non-empty."""
        from pathlib import Path
        import yaml

        config_path = (
            Path(__file__).resolve().parents[2]
            / "config"
            / "llm.yaml"
        )
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        futures_config = data.get("futures", {})
        addendum = futures_config.get("prompt_addendum", "")

        assert addendum.strip(), (
            "config/llm.yaml::futures.prompt_addendum must be non-empty "
            "(Phase 1.1-a requirement)"
        )
        # Verify the addendum mentions futures trading
        assert "futures" in addendum.lower() or "KOSPI200" in addendum


# =============================================================================
# Phase 1.1-b: request_refresh idempotence
# =============================================================================


class TestRequestRefresh:
    """Verify request_refresh() serialises concurrent calls and does not
    queue duplicate in-flight analyses."""

    @pytest.mark.asyncio
    async def test_request_refresh_triggers_analysis_and_returns_true(self):
        """request_refresh() triggers run_analysis() and returns True."""
        config = _make_llm_config()
        publisher = LLMContextPublisher("futures", config=config)

        context = _make_market_context()
        publisher.run_analysis = AsyncMock(return_value=context)
        publisher.publish_to_redis = Mock()

        result = await publisher.request_refresh()

        assert result is True
        publisher.run_analysis.assert_awaited_once()
        publisher.publish_to_redis.assert_called_once_with(context)

    @pytest.mark.asyncio
    async def test_request_refresh_with_none_result_returns_true(self):
        """request_refresh() returns True even when run_analysis() returns None
        (e.g., LLM API failure) — the lock was acquired so the call was attempted."""
        config = _make_llm_config()
        publisher = LLMContextPublisher("futures", config=config)

        publisher.run_analysis = AsyncMock(return_value=None)
        publisher.publish_to_redis = Mock()

        result = await publisher.request_refresh()

        assert result is True
        publisher.publish_to_redis.assert_not_called()  # Nothing to publish

    @pytest.mark.asyncio
    async def test_concurrent_request_refresh_second_call_returns_false(self):
        """When a refresh is already in-flight, a concurrent request_refresh()
        returns False immediately without triggering a second analysis."""
        config = _make_llm_config()
        publisher = LLMContextPublisher("futures", config=config)

        # Initialise the lock eagerly for this test so we can acquire it manually
        publisher._refresh_lock = asyncio.Lock()

        # Track how many times run_analysis was called
        call_count = 0

        async def slow_analysis(mode: str = "all") -> Optional[MarketContext]:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)  # Simulate slow analysis
            return _make_market_context()

        publisher.run_analysis = slow_analysis
        publisher.publish_to_redis = Mock()

        # Launch first request in background; lock it before launching second
        async def first_requester():
            return await publisher.request_refresh()

        # Acquire lock to simulate in-flight analysis
        await publisher._refresh_lock.acquire()
        try:
            # While lock is held, a concurrent call should return False
            result = await publisher.request_refresh()
            assert result is False
        finally:
            publisher._refresh_lock.release()

        # After release, a new call should succeed
        result2 = await publisher.request_refresh()
        assert result2 is True

    @pytest.mark.asyncio
    async def test_request_refresh_lock_is_lazily_initialised(self):
        """_refresh_lock is None before first request_refresh() call."""
        config = _make_llm_config()
        publisher = LLMContextPublisher("futures", config=config)

        assert publisher._refresh_lock is None

        publisher.run_analysis = AsyncMock(return_value=None)
        publisher.publish_to_redis = Mock()

        await publisher.request_refresh()

        # Lock should now be initialised
        assert publisher._refresh_lock is not None

    @pytest.mark.asyncio
    async def test_request_refresh_does_not_block_if_analysis_raises(self):
        """If run_analysis() raises, request_refresh() returns True (attempted)
        and does not leave the lock permanently acquired (no deadlock)."""
        config = _make_llm_config()
        publisher = LLMContextPublisher("futures", config=config)
        publisher._refresh_lock = asyncio.Lock()

        async def failing_analysis(mode: str = "all"):
            raise RuntimeError("LLM API unavailable")

        publisher.run_analysis = failing_analysis
        publisher.publish_to_redis = Mock()

        # Should not deadlock or raise
        result = await publisher.request_refresh()
        assert result is True

        # Lock must be released — a second call should be able to acquire it
        assert not publisher._refresh_lock.locked()

    @pytest.mark.asyncio
    async def test_two_sequential_refreshes_both_succeed(self):
        """Two sequential (non-concurrent) request_refresh() calls both return True."""
        config = _make_llm_config()
        publisher = LLMContextPublisher("futures", config=config)

        contexts = [_make_market_context("BULL_STRONG"), _make_market_context("BEAR_MODERATE")]
        side_effects = iter(contexts)

        async def sequential_analysis(mode: str = "all"):
            return next(side_effects)

        publisher.run_analysis = sequential_analysis
        publisher.publish_to_redis = Mock()

        r1 = await publisher.request_refresh()
        r2 = await publisher.request_refresh()

        assert r1 is True
        assert r2 is True
        assert publisher.publish_to_redis.call_count == 2


# =============================================================================
# Smoke test: stock mode unchanged
# =============================================================================


class TestStockModeUnchanged:
    """Verify stock publisher behaviour is unchanged after Phase 1.1 changes."""

    @pytest.mark.asyncio
    async def test_stock_publisher_run_analysis_returns_market_context(self):
        """Stock publisher run_analysis() still returns MarketContext normally."""
        config = _make_llm_config()
        publisher = LLMContextPublisher("stock", config=config)

        mock_analysis = MagicMock()
        mock_analysis.overall_signal = MarketSignal.NEUTRAL
        mock_analysis.risk_mode = RiskMode.NEUTRAL
        mock_analysis.llm_summary = ""
        mock_analysis.llm_strategy = ""
        mock_analysis.key_points = []
        mock_analysis.etf_flows = []
        mock_analysis.futures = None
        mock_analysis.options = None
        mock_analysis.bonds = None
        mock_analysis.indices = []
        mock_analysis.sector_rotation = {}

        publisher.analyzer.run_analysis = Mock(return_value=mock_analysis)

        context = await publisher.run_analysis()

        assert context is not None
        assert isinstance(context, MarketContext)

    @patch("services.trading.llm_context_publisher.HAS_PROMETHEUS", False)
    def test_stock_publisher_prompt_addendum_always_empty(self):
        """Stock publisher always has empty _prompt_addendum, regardless of config."""
        for addendum_value in ("some addendum", "", "   "):
            config = _make_llm_config(futures_prompt_addendum=addendum_value)
            publisher = LLMContextPublisher("stock", config=config)
            assert publisher._prompt_addendum == "", (
                f"Expected empty addendum for stock, got {publisher._prompt_addendum!r}"
            )
