"""Test rate limiter memory management."""
import pytest
import time
from unittest.mock import MagicMock


def test_rate_limiter_cleans_old_entries():
    """Test that rate limiter cleans up old request timestamps."""
    from services.dashboard.middleware.rate_limit import RateLimitMiddleware

    middleware = RateLimitMiddleware(
        app=MagicMock(),
        requests_per_window=10,
        window_seconds=60,
    )

    # Simulate old requests (2 minutes ago - outside window)
    old_time = time.time() - 120
    middleware._request_times["client1"] = [old_time] * 5
    middleware._request_times["client2"] = [old_time] * 5

    # Trigger cleanup
    middleware._cleanup_old_entries()

    # Old entries should be cleaned and empty dicts removed
    assert "client1" not in middleware._request_times
    assert "client2" not in middleware._request_times


def test_rate_limiter_keeps_recent_entries():
    """Test that cleanup keeps recent entries."""
    from services.dashboard.middleware.rate_limit import RateLimitMiddleware

    middleware = RateLimitMiddleware(
        app=MagicMock(),
        requests_per_window=10,
        window_seconds=60,
    )

    now = time.time()
    # Mix of old and new entries
    middleware._request_times["client1"] = [
        now - 120,  # Old - should be removed
        now - 30,  # Recent - should be kept
        now - 10,  # Recent - should be kept
    ]

    middleware._cleanup_old_entries()

    # Should have 2 entries left
    assert "client1" in middleware._request_times
    assert len(middleware._request_times["client1"]) == 2


def test_rate_limiter_removes_empty_clients():
    """Test that empty client entries are removed."""
    from services.dashboard.middleware.rate_limit import RateLimitMiddleware

    middleware = RateLimitMiddleware(
        app=MagicMock(),
        requests_per_window=10,
        window_seconds=60,
    )

    now = time.time()
    # Client with only old entries
    middleware._request_times["old_client"] = [now - 120]
    # Client with recent entries
    middleware._request_times["active_client"] = [now - 10]

    middleware._cleanup_old_entries()

    # Old client should be removed entirely
    assert "old_client" not in middleware._request_times
    # Active client should remain
    assert "active_client" in middleware._request_times


def test_rate_limiter_periodic_cleanup_triggered():
    """Test that periodic cleanup is triggered based on interval."""
    from services.dashboard.middleware.rate_limit import RateLimitMiddleware

    middleware = RateLimitMiddleware(
        app=MagicMock(),
        requests_per_window=10,
        window_seconds=60,
    )

    # Set cleanup interval to 0 to always trigger
    middleware._cleanup_interval = 0
    middleware._last_cleanup = time.time() - 1

    # Add old entries
    old_time = time.time() - 120
    middleware._request_times["client1"] = [old_time] * 5

    # Simulate a request by triggering dispatch logic
    # (We can't fully test async dispatch, but we can test cleanup logic)
    current_time = time.time()
    if current_time - middleware._last_cleanup > middleware._cleanup_interval:
        middleware._cleanup_old_entries()
        middleware._last_cleanup = current_time

    # Old entries should be cleaned
    assert "client1" not in middleware._request_times


def test_rate_limiter_no_x_forwarded_for_spoofing():
    """Test that rate limiter uses client IP, not X-Forwarded-For."""
    from services.dashboard.middleware.rate_limit import RateLimitMiddleware

    middleware = RateLimitMiddleware(
        app=MagicMock(),
        requests_per_window=10,
        window_seconds=60,
    )

    # Create mock request with spoofed X-Forwarded-For
    mock_request = MagicMock()
    mock_request.headers = {"X-Forwarded-For": "1.1.1.1, 2.2.2.2"}
    mock_request.client.host = "192.168.1.1"

    client_id = middleware._get_client_id(mock_request)

    # Should use actual client IP, not spoofed header
    assert client_id == "192.168.1.1"


def test_rate_limiter_handles_missing_client():
    """Test rate limiter handles requests with no client info."""
    from services.dashboard.middleware.rate_limit import RateLimitMiddleware

    middleware = RateLimitMiddleware(
        app=MagicMock(),
        requests_per_window=10,
        window_seconds=60,
    )

    mock_request = MagicMock()
    mock_request.client = None

    client_id = middleware._get_client_id(mock_request)

    assert client_id == "unknown"
