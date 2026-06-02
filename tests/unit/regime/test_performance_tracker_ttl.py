"""Tests for ``RegimePerformanceTracker`` Redis TTL behaviour (M9).

Background
==========

`AGENTS.md` §2.4 requires every Redis key the system writes to have an
explicit TTL.  Before M9, :meth:`RegimePerformanceTracker._persist_to_redis`
called ``redis.set(key, value)`` *without* a TTL, leaking keys forever in
the regime-performance namespace.

These tests pin down the new contract:

* ``RegimePerformanceConfig`` exposes a ``redis_ttl_seconds`` field with a
  sensible default (30 days, matching ``RUNNING_TOTALS_TTL_SECONDS``).
* The default is non-zero and validated.
* ``from_dict`` accepts an override.
* The actual ``redis.set`` call now forwards ``ex=<ttl_seconds>``.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from shared.regime.performance_tracker import (
    RegimePerformanceConfig,
    RegimePerformanceTracker,
)

DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


class TestRedisTTLConfig:
    """Validate the new ``redis_ttl_seconds`` configuration field."""

    def test_default_ttl_matches_running_totals_window(self):
        cfg = RegimePerformanceConfig()
        assert cfg.redis_ttl_seconds == DEFAULT_TTL_SECONDS

    def test_zero_ttl_rejected(self):
        with pytest.raises(ValueError, match="redis_ttl_seconds must be > 0"):
            RegimePerformanceConfig(redis_ttl_seconds=0)

    def test_negative_ttl_rejected(self):
        with pytest.raises(ValueError, match="redis_ttl_seconds must be > 0"):
            RegimePerformanceConfig(redis_ttl_seconds=-1)

    def test_from_dict_accepts_override(self):
        cfg = RegimePerformanceConfig.from_dict(
            {"redis_enabled": True, "redis_ttl_seconds": 3600}
        )
        assert cfg.redis_ttl_seconds == 3600

    def test_from_dict_uses_default_when_missing(self):
        cfg = RegimePerformanceConfig.from_dict({"redis_enabled": True})
        assert cfg.redis_ttl_seconds == DEFAULT_TTL_SECONDS

    def test_from_dict_rejects_non_int_ttl(self):
        with pytest.raises(TypeError, match="redis_ttl_seconds must be int"):
            RegimePerformanceConfig.from_dict({"redis_ttl_seconds": "3600"})

    def test_from_dict_rejects_bool_ttl(self):
        # ``bool`` is an ``int`` subclass in Python; reject it explicitly
        # so ``redis_ttl_seconds: true`` in YAML does not silently set TTL=1.
        with pytest.raises(TypeError, match="redis_ttl_seconds must be int"):
            RegimePerformanceConfig.from_dict({"redis_ttl_seconds": True})


class TestRedisSetWithTTL:
    """Verify ``_persist_to_redis`` always forwards a TTL."""

    def _make_tracker_with_mock(
        self, *, ttl_seconds: int = DEFAULT_TTL_SECONDS
    ) -> tuple[RegimePerformanceTracker, MagicMock]:
        cfg = RegimePerformanceConfig(
            redis_enabled=True,
            redis_ttl_seconds=ttl_seconds,
            # Keep the stats threshold tiny so a single trade triggers persist.
            min_trades_for_stats=1,
        )
        tracker = RegimePerformanceTracker(cfg)
        mock_redis = MagicMock()
        tracker._redis_client = mock_redis  # bypass lazy init
        return tracker, mock_redis

    def _drive_one_round_trip(self, tracker: RegimePerformanceTracker) -> None:
        ts = datetime(2026, 5, 17, 9, 30)
        tracker.record_entry(
            regime="TRENDING_BULL", code="005930", price=70_000.0, timestamp=ts
        )
        tracker.record_exit(
            regime="TRENDING_BULL",
            code="005930",
            price=71_000.0,
            timestamp=ts,
            pnl=1000.0,
        )

    def test_persist_uses_default_ttl(self):
        tracker, mock_redis = self._make_tracker_with_mock()
        self._drive_one_round_trip(tracker)

        assert mock_redis.set.call_count == 1
        _, kwargs = mock_redis.set.call_args
        assert kwargs.get("ex") == DEFAULT_TTL_SECONDS

    def test_persist_uses_custom_ttl(self):
        custom_ttl = 12 * 3600  # 12 hours
        tracker, mock_redis = self._make_tracker_with_mock(ttl_seconds=custom_ttl)
        self._drive_one_round_trip(tracker)

        _, kwargs = mock_redis.set.call_args
        assert kwargs.get("ex") == custom_ttl

    def test_persist_never_calls_set_without_ttl(self):
        """Regression guard: TTL must be supplied on every write."""
        tracker, mock_redis = self._make_tracker_with_mock()
        self._drive_one_round_trip(tracker)

        for call in mock_redis.set.call_args_list:
            _, kwargs = call
            assert (
                "ex" in kwargs
            ), "Redis SET issued without TTL — AGENTS.md §2.4 violated"
            assert kwargs["ex"] > 0
