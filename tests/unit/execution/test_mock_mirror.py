from types import SimpleNamespace

import pytest

from shared.execution.mock_mirror import MockAccountMirror


@pytest.mark.asyncio
async def test_mirror_entry_returns_skipped_when_uninitialized():
    mirror = MockAccountMirror()

    result = await mirror.mirror_entry("005930", "BUY", 3, 70_000.0)

    assert result["success"] is False
    assert result["skipped"] is True
    assert result["message"] == "mock_mirror_not_initialized"


@pytest.mark.asyncio
async def test_mirror_order_returns_failure_result():
    class Executor:
        config = SimpleNamespace(
            tr_code_buy_mock="VTTC0802U",
            tr_code_sell_mock="VTTC0801U",
        )

        async def execute_order(self, _order):
            return SimpleNamespace(
                success=False,
                order_no="",
                message="insufficient funds",
            )

    mirror = MockAccountMirror()
    mirror._executor = Executor()
    mirror._initialized = True

    result = await mirror.mirror_entry("005930", "BUY", 3, 70_000.0)

    assert result["success"] is False
    assert result["skipped"] is False
    assert result["message"] == "insufficient funds"
