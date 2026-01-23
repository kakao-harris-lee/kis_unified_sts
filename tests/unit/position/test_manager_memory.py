"""Tests for PositionManager memory bounds."""

import pytest


@pytest.fixture
def exit_config():
    """Default exit config for testing."""
    from shared.position.exit_checker import ExitConfig

    return ExitConfig(
        stop_loss_pct=-0.02,
        trailing_stop_pct=0.015,
        profit_target_pct=0.05,
        time_exit_minutes=60,
    )


class TestClosedPositionsBounded:
    """Test closed_positions memory bounds."""

    @pytest.mark.asyncio
    async def test_closed_positions_bounded(self, exit_config):
        """closed_positions should not grow beyond max_closed_history."""
        from shared.position.manager import PositionManager
        from shared.models.position import PositionSide

        manager = PositionManager(
            exit_config=exit_config,
            max_closed_history=100
        )

        # Open and close 200 positions
        for i in range(200):
            pos = await manager.open_position(
                code=f"TEST{i:03d}",
                name=f"Test Stock {i}",
                side=PositionSide.LONG,
                entry_price=100.0,
                quantity=10,
                strategy="test"
            )
            await manager.close_position(pos.id, 105.0, "TEST_EXIT")

        # Should be bounded to max_closed_history
        assert len(manager.closed_positions) <= 100

    @pytest.mark.asyncio
    async def test_default_max_closed_history(self, exit_config):
        """Should have sensible default max_closed_history."""
        from shared.position.manager import PositionManager

        manager = PositionManager(exit_config=exit_config)
        assert manager.max_closed_history == 10000

    @pytest.mark.asyncio
    async def test_closed_positions_fifo(self, exit_config):
        """Older positions should be removed first (FIFO)."""
        from shared.position.manager import PositionManager
        from shared.models.position import PositionSide

        manager = PositionManager(
            exit_config=exit_config,
            max_closed_history=3
        )

        for i in range(5):
            pos = await manager.open_position(
                code=f"TEST{i}",
                name=f"Test Stock {i}",
                side=PositionSide.LONG,
                entry_price=100.0,
                quantity=10,
                strategy="test"
            )
            await manager.close_position(pos.id, 105.0, "TEST_EXIT")

        # Should only have the last 3 positions
        assert len(manager.closed_positions) == 3
        codes = [p.code for p in manager.closed_positions]
        assert "TEST2" in codes
        assert "TEST3" in codes
        assert "TEST4" in codes
        assert "TEST0" not in codes
        assert "TEST1" not in codes

    @pytest.mark.asyncio
    async def test_closed_positions_returns_list(self, exit_config):
        """closed_positions property should return list for backward compatibility."""
        from shared.position.manager import PositionManager

        manager = PositionManager(exit_config=exit_config)
        assert isinstance(manager.closed_positions, list)
