"""Tests for E3 TimeDecayExit strategy."""

import pytest
from datetime import datetime, timedelta

from shared.models.position import Position, PositionSide, PositionState
from shared.strategy.exit.time_decay import TimeDecayExit, TimeDecayConfig
from shared.strategy.base import ExitContext


@pytest.fixture
def config():
    return TimeDecayConfig(
        decay_tiers=[
            (10, 0.0),    # 10분 이후: 손실이면 청산
            (20, 0.005),  # 20분 이후: +0.5% 미달 시 청산
        ],
        max_hold_minutes=30,
        skip_maximize_state=True,
    )


@pytest.fixture
def exit_strategy(config):
    return TimeDecayExit(config)


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


class TestTimeDecayExit:
    """TimeDecayExit tests."""

    def test_init(self, exit_strategy):
        """Test initialization."""
        assert exit_strategy.name == "TIME_DECAY_EXIT"
        assert exit_strategy.version == "E3"
        assert len(exit_strategy._decay_tiers) == 2

    def test_decay_tiers_sorted(self, exit_strategy):
        """Test decay tiers are sorted."""
        tiers = exit_strategy._decay_tiers
        for i in range(len(tiers) - 1):
            assert tiers[i][0] < tiers[i + 1][0]

    def test_get_required_profit_before_first_tier(self, exit_strategy):
        """Test required profit before first tier."""
        required = exit_strategy._get_required_profit(5)  # 5분
        assert required == -999.0  # 조건 없음

    def test_get_required_profit_in_first_tier(self, exit_strategy):
        """Test required profit in first tier."""
        required = exit_strategy._get_required_profit(15)  # 15분
        assert required == 0.0  # 손실이면 청산

    def test_get_required_profit_in_second_tier(self, exit_strategy):
        """Test required profit in second tier."""
        required = exit_strategy._get_required_profit(25)  # 25분
        assert required == 0.005  # +0.5% 미달 시 청산

    def test_decay_status(self, exit_strategy):
        """Test decay status helper."""
        status = exit_strategy.get_decay_status(15)
        assert status["hold_minutes"] == 15
        assert status["required_profit_pct"] == 0.0
        assert status["current_tier"] == (10, 0.0)
        assert status["next_tier"] == (20, 0.005)
        assert status["time_to_next"] == 5

    @pytest.mark.asyncio
    async def test_should_exit_with_loss_after_10min(self, exit_strategy, sample_position):
        """Test exit signal with loss after 10 minutes."""
        sample_position.entry_time = datetime.now() - timedelta(minutes=15)
        sample_position.current_price = 69500.0  # -0.7% loss

        context = ExitContext(
            position=sample_position,
            market_data={"close": 69500.0},
            indicators={},
            timestamp=datetime.now(),
        )

        should_exit, signal = await exit_strategy.should_exit(context)
        assert should_exit is True
        assert signal is not None
        assert signal.reason.value == "time_cut"

    @pytest.mark.asyncio
    async def test_should_not_exit_with_profit_after_10min(self, exit_strategy, sample_position):
        """Test no exit signal with profit after 10 minutes."""
        sample_position.entry_time = datetime.now() - timedelta(minutes=15)
        sample_position.current_price = 70500.0  # +0.7% profit

        context = ExitContext(
            position=sample_position,
            market_data={"close": 70500.0},
            indicators={},
            timestamp=datetime.now(),
        )

        should_exit, signal = await exit_strategy.should_exit(context)
        assert should_exit is False
        assert signal is None

    @pytest.mark.asyncio
    async def test_should_exit_max_hold_exceeded(self, exit_strategy, sample_position):
        """Test exit signal when max hold time exceeded."""
        sample_position.entry_time = datetime.now() - timedelta(minutes=35)
        sample_position.current_price = 71000.0  # +1.4% profit

        context = ExitContext(
            position=sample_position,
            market_data={"close": 71000.0},
            indicators={},
            timestamp=datetime.now(),
        )

        should_exit, signal = await exit_strategy.should_exit(context)
        assert should_exit is True
        assert signal is not None

    @pytest.mark.asyncio
    async def test_skip_maximize_state(self, exit_strategy, sample_position):
        """Test skipping MAXIMIZE state positions."""
        sample_position.entry_time = datetime.now() - timedelta(minutes=15)
        sample_position.current_price = 69500.0  # -0.7% loss
        sample_position.state = PositionState.MAXIMIZE

        context = ExitContext(
            position=sample_position,
            market_data={"close": 69500.0},
            indicators={},
            timestamp=datetime.now(),
        )

        should_exit, signal = await exit_strategy.should_exit(context)
        assert should_exit is False  # MAXIMIZE is skipped
        assert signal is None

    def test_config_from_dict(self):
        """Test config creation from dict."""
        config = TimeDecayConfig.from_dict({
            "decay_tiers": [(5, 0.0), (15, 0.01)],
            "max_hold_minutes": 20,
        })
        assert config.max_hold_minutes == 20
        assert len(config.decay_tiers) == 2
