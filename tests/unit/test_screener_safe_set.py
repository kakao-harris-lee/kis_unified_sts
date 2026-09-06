"""``_safe_set`` Redis guard for the screener publish loop (operator review
2026-09-06).

With Redis connect_retries=0 (fail-fast connect, shared/streaming/client.py),
a transient outage now surfaces as a single raised ConnectionError from
``redis_client.set`` instead of being absorbed by redis-py's built-in
retries. The three publish sites in ``run_screener`` (universe latest,
volume-surge feed, dip candidates) all route through this helper so a Redis
blip logs a warning and skips that one publish instead of aborting the rest
of the screener cycle.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import redis

from services.screener import _safe_set


def test_success_returns_true_and_calls_set_with_ttl():
    fake_redis = MagicMock()

    result = _safe_set(fake_redis, "some:key", "payload", ex=86400)

    assert result is True
    fake_redis.set.assert_called_once_with("some:key", "payload", ex=86400)


def test_connection_error_logs_warning_and_returns_false(caplog):
    fake_redis = MagicMock()
    fake_redis.set.side_effect = redis.exceptions.ConnectionError("down")

    with caplog.at_level("WARNING"):
        result = _safe_set(fake_redis, "some:key", "payload", ex=86400)

    assert result is False
    assert any(
        "Redis SET failed for key=some:key" in rec.message for rec in caplog.records
    )


def test_timeout_error_also_guarded():
    fake_redis = MagicMock()
    fake_redis.set.side_effect = redis.exceptions.TimeoutError("slow")

    result = _safe_set(fake_redis, "some:key", "payload", ex=60)

    assert result is False
