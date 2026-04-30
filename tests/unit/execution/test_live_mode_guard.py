"""Tests for shared/execution/live_mode_guard.py — Phase 5 Task 5."""

from __future__ import annotations

import textwrap
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from shared.execution.live_mode_guard import LiveModeGuard


class TestYAMLLoad:
    def test_default_yaml_loads_disabled(self):
        cfg = LiveModeGuard.from_yaml()
        # Default config/futures_live.yaml ships with enabled=false
        assert cfg.enabled is False
        assert cfg.max_position_size_contracts == 1
        assert cfg.max_daily_trades == 2
        assert cfg.symbol_lock_enabled is True
        assert cfg.account_suffix == "_live"
        assert cfg.suspend_key == "futures:live:suspended"

    def test_loads_custom_yaml(self, tmp_path):
        custom = tmp_path / "futures_live.yaml"
        custom.write_text(textwrap.dedent("""
                futures_live:
                  enabled: true
                  max_position_size_contracts: 2
                  max_daily_trades: 4
                  symbol_lock_enabled: false
                  account_suffix: "_canary"
                  suspend_key: "futures:live:halt"
                """).strip())
        cfg = LiveModeGuard.from_yaml(str(custom))
        assert cfg.enabled is True
        assert cfg.max_position_size_contracts == 2
        assert cfg.max_daily_trades == 4
        assert cfg.symbol_lock_enabled is False
        assert cfg.account_suffix == "_canary"
        assert cfg.suspend_key == "futures:live:halt"

    def test_max_position_size_must_be_positive(self):
        with pytest.raises(ValidationError):
            LiveModeGuard(max_position_size_contracts=0)

    def test_max_daily_trades_must_be_positive(self):
        with pytest.raises(ValidationError):
            LiveModeGuard(max_daily_trades=0)


class TestIsLiveSuspended:
    @pytest.mark.asyncio
    async def test_disabled_always_suspended(self):
        cfg = LiveModeGuard(enabled=False)
        redis = AsyncMock()
        # Even if Redis flag absent, disabled => suspended.
        redis.get = AsyncMock(return_value=None)
        assert await cfg.is_live_suspended(redis) is True
        # The Redis lookup should be short-circuited (no get call).
        redis.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_enabled_no_flag_not_suspended(self):
        cfg = LiveModeGuard(enabled=True)
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        assert await cfg.is_live_suspended(redis) is False
        redis.get.assert_awaited_once_with(cfg.suspend_key)

    @pytest.mark.asyncio
    async def test_enabled_flag_set_to_1_suspended(self):
        cfg = LiveModeGuard(enabled=True)
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"1")
        assert await cfg.is_live_suspended(redis) is True

    @pytest.mark.asyncio
    async def test_enabled_flag_string_true_suspended(self):
        cfg = LiveModeGuard(enabled=True)
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"true")
        assert await cfg.is_live_suspended(redis) is True

    @pytest.mark.asyncio
    async def test_enabled_flag_string_zero_not_suspended(self):
        # Operator sets the key to "0" — explicit not-suspended.
        cfg = LiveModeGuard(enabled=True)
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"0")
        assert await cfg.is_live_suspended(redis) is False

    @pytest.mark.asyncio
    async def test_enabled_flag_empty_string_not_suspended(self):
        cfg = LiveModeGuard(enabled=True)
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"")
        assert await cfg.is_live_suspended(redis) is False

    @pytest.mark.asyncio
    async def test_enabled_flag_false_string_not_suspended(self):
        cfg = LiveModeGuard(enabled=True)
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"false")
        assert await cfg.is_live_suspended(redis) is False

    @pytest.mark.asyncio
    async def test_redis_io_failure_fails_closed(self):
        # If Redis is unreachable we'd rather skip an order than place one
        # under unknown guard state — fail-closed semantics.
        cfg = LiveModeGuard(enabled=True)
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=Exception("connection refused"))
        assert await cfg.is_live_suspended(redis) is True

    @pytest.mark.asyncio
    async def test_str_value_decoded(self):
        # Some Redis libs return str instead of bytes
        cfg = LiveModeGuard(enabled=True)
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="1")
        assert await cfg.is_live_suspended(redis) is True

    @pytest.mark.asyncio
    async def test_custom_suspend_key_used(self):
        cfg = LiveModeGuard(enabled=True, suspend_key="custom:halt:flag")
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        await cfg.is_live_suspended(redis)
        redis.get.assert_awaited_once_with("custom:halt:flag")
