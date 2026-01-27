"""Tests for E4 MarketRegimeExit strategy."""

import pytest
from datetime import datetime, timedelta

from shared.models.position import Position, PositionSide, PositionState
from shared.strategy.exit.market_regime import MarketRegimeExit, MarketRegimeConfig
from shared.strategy.market_classifier import MarketClassifier, MarketState
from shared.strategy.base import ExitContext


@pytest.fixture
def config():
    return MarketRegimeConfig()


@pytest.fixture
def exit_strategy(config):
    return MarketRegimeExit(config)


@pytest.fixture
def sample_position():
    return Position(
        id="test-001",
        code="005930",
        name="삼성전자",
        side=PositionSide.LONG,
        quantity=10,
        entry_price=70000.0,
        entry_time=datetime.now() - timedelta(minutes=15),
        current_price=69500.0,  # -0.7% loss
        state=PositionState.SURVIVAL,
    )


class TestMarketClassifier:
    """MarketClassifier tests."""

    def test_classify_bull_strong(self):
        classifier = MarketClassifier()
        state = classifier.classify(mfi=52, adx=25)
        assert state == MarketState.BULL_STRONG

    def test_classify_bull_moderate(self):
        classifier = MarketClassifier()
        state = classifier.classify(mfi=48.5, adx=20)
        assert state == MarketState.BULL_MODERATE

    def test_classify_bear_strong(self):
        classifier = MarketClassifier()
        state = classifier.classify(mfi=30, adx=25)
        assert state == MarketState.BEAR_STRONG

    def test_is_bullish(self):
        classifier = MarketClassifier()
        assert classifier.is_bullish(MarketState.BULL_STRONG)
        assert classifier.is_bullish(MarketState.BULL_MODERATE)
        assert not classifier.is_bullish(MarketState.BEAR_STRONG)

    def test_is_bearish(self):
        classifier = MarketClassifier()
        assert classifier.is_bearish(MarketState.BEAR_STRONG)
        assert classifier.is_bearish(MarketState.BEAR_MODERATE)
        assert not classifier.is_bearish(MarketState.BULL_STRONG)

    def test_position_multiplier(self):
        classifier = MarketClassifier()
        assert classifier.get_position_size_multiplier(MarketState.BULL_STRONG) == 1.0
        assert classifier.get_position_size_multiplier(MarketState.BEAR_STRONG) == 0.0


class TestMarketRegimeExit:
    """MarketRegimeExit tests."""

    def test_init(self, exit_strategy):
        """Test initialization."""
        assert exit_strategy.name == "MARKET_REGIME_EXIT"
        assert exit_strategy.version == "E4"

    def test_get_regime_action_bear(self, exit_strategy):
        """Test regime action for BEAR state."""
        action = exit_strategy.get_regime_action(MarketState.BEAR_STRONG)
        assert action["action"] == "immediate_exit"
        assert action["priority"] == 1

    def test_get_regime_action_bull(self, exit_strategy):
        """Test regime action for BULL state."""
        action = exit_strategy.get_regime_action(MarketState.BULL_STRONG)
        assert action["action"] == "skip"
        assert action["priority"] is None

    def test_get_regime_action_sideways(self, exit_strategy):
        """Test regime action for SIDEWAYS state."""
        action = exit_strategy.get_regime_action(MarketState.SIDEWAYS_FLAT)
        assert action["action"] == "conditional_exit"
        assert action["required_profit_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_should_exit_in_bear_market(self, exit_strategy, sample_position):
        """Test exit signal in BEAR market."""
        context = ExitContext(
            position=sample_position,
            market_data={"close": 69500.0},
            indicators={},
            timestamp=datetime.now(),
            market_state=MarketState.BEAR_STRONG,
        )

        should_exit, signal = await exit_strategy.should_exit(context)
        assert should_exit is True
        assert signal is not None
        assert signal.reason.value == "bear_exit"
        assert signal.priority == 1

    @pytest.mark.asyncio
    async def test_should_not_exit_in_bull_market(self, exit_strategy, sample_position):
        """Test no exit signal in BULL market."""
        context = ExitContext(
            position=sample_position,
            market_data={"close": 69500.0},
            indicators={},
            timestamp=datetime.now(),
            market_state=MarketState.BULL_STRONG,
        )

        should_exit, signal = await exit_strategy.should_exit(context)
        assert should_exit is False
        assert signal is None

    @pytest.mark.asyncio
    async def test_should_exit_sideways_with_loss(self, exit_strategy, sample_position):
        """Test exit signal in SIDEWAYS_FLAT with loss."""
        sample_position.current_price = 69500.0  # -0.7% loss

        context = ExitContext(
            position=sample_position,
            market_data={"close": 69500.0},
            indicators={},
            timestamp=datetime.now(),
            market_state=MarketState.SIDEWAYS_FLAT,
        )

        should_exit, signal = await exit_strategy.should_exit(context)
        assert should_exit is True
        assert signal is not None

    @pytest.mark.asyncio
    async def test_should_not_exit_sideways_with_profit(self, exit_strategy, sample_position):
        """Test no exit signal in SIDEWAYS_FLAT with profit."""
        sample_position.current_price = 70500.0  # +0.7% profit

        context = ExitContext(
            position=sample_position,
            market_data={"close": 70500.0},
            indicators={},
            timestamp=datetime.now(),
            market_state=MarketState.SIDEWAYS_FLAT,
        )

        should_exit, signal = await exit_strategy.should_exit(context)
        assert should_exit is False
        assert signal is None

    @pytest.mark.asyncio
    async def test_skip_without_market_state(self, exit_strategy, sample_position):
        """Test skipping when market_state is None."""
        context = ExitContext(
            position=sample_position,
            market_data={"close": 69500.0},
            indicators={},
            timestamp=datetime.now(),
            market_state=None,
        )

        should_exit, signal = await exit_strategy.should_exit(context)
        assert should_exit is False
        assert signal is None

    @pytest.mark.asyncio
    async def test_skip_maximize_in_bear_disabled(self, sample_position):
        """Test skipping MAXIMIZE state when exit_maximize_in_bear is False."""
        config = MarketRegimeConfig(exit_maximize_in_bear=False)
        exit_strategy = MarketRegimeExit(config)

        sample_position.state = PositionState.MAXIMIZE

        context = ExitContext(
            position=sample_position,
            market_data={"close": 69500.0},
            indicators={},
            timestamp=datetime.now(),
            market_state=MarketState.BEAR_STRONG,
        )

        should_exit, signal = await exit_strategy.should_exit(context)
        assert should_exit is False  # MAXIMIZE is skipped
        assert signal is None

    def test_config_from_dict(self):
        """Test config creation from dict."""
        config = MarketRegimeConfig.from_dict({
            "exit_maximize_in_bear": False,
            "immediate_exit_states": ["BEAR_STRONG"],
        })
        assert config.exit_maximize_in_bear is False
        assert len(config.immediate_exit_states) == 1
