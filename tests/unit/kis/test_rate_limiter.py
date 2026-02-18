"""Tests for _RateLimiter exponential backoff in shared/kis/client.py."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from shared.kis.client import _RateLimiter


class TestRateLimiterBackoff:
    """Test exponential backoff on consecutive penalties."""

    def test_first_penalty_uses_base_seconds(self):
        limiter = _RateLimiter(max_requests=5)
        before = time.monotonic()
        limiter.penalty(1.0)

        assert limiter._consecutive_penalties == 1
        assert limiter._penalty_until >= before + 1.0
        assert limiter._penalty_until < before + 2.0

    def test_consecutive_penalties_double(self):
        limiter = _RateLimiter(max_requests=5)

        limiter.penalty(1.0)
        assert limiter._consecutive_penalties == 1
        first_until = limiter._penalty_until

        limiter.penalty(1.0)
        assert limiter._consecutive_penalties == 2
        # Second penalty: 1.0 * 2^1 = 2.0
        assert limiter._penalty_until > first_until

    def test_third_penalty_quadruples(self):
        limiter = _RateLimiter(max_requests=5)

        limiter.penalty(1.0)  # 1s
        limiter.penalty(1.0)  # 2s
        before = time.monotonic()
        limiter.penalty(1.0)  # 4s

        assert limiter._consecutive_penalties == 3
        assert limiter._penalty_until >= before + 4.0

    def test_penalty_capped_at_max(self):
        limiter = _RateLimiter(max_requests=5)
        limiter._max_penalty = 5.0

        # Apply many penalties to exceed cap
        for _ in range(10):
            limiter.penalty(1.0)

        before = time.monotonic()
        limiter.penalty(1.0)

        # Should be capped at 5.0
        assert limiter._penalty_until <= before + 5.0 + 0.1

    def test_reset_backoff_clears_counter(self):
        limiter = _RateLimiter(max_requests=5)
        limiter.penalty(1.0)
        limiter.penalty(1.0)
        assert limiter._consecutive_penalties == 2

        limiter.reset_backoff()
        assert limiter._consecutive_penalties == 0

    def test_reset_backoff_noop_when_zero(self):
        limiter = _RateLimiter(max_requests=5)
        limiter.reset_backoff()  # Should not raise
        assert limiter._consecutive_penalties == 0

    @pytest.mark.asyncio
    async def test_acquire_respects_penalty(self):
        limiter = _RateLimiter(max_requests=100)
        limiter.penalty(0.05)  # 50ms penalty

        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        # Should have waited at least ~50ms
        assert elapsed >= 0.04

    @pytest.mark.asyncio
    async def test_acquire_no_delay_without_penalty(self):
        limiter = _RateLimiter(max_requests=100)
        limiter._last_request = 0.0  # No recent request

        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        # Should be nearly instant
        assert elapsed < 0.05
