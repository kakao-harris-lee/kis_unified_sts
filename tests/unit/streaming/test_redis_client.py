"""Unit tests for RedisClient reconnection logic in shared/streaming/client.py."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest
import redis

from shared.streaming.client import RedisClient


@pytest.fixture(autouse=True)
def reset_redis_client():
    """Isolate each test by resetting the singleton before and after."""
    RedisClient.reset()
    yield
    RedisClient.reset()


class TestGetClientFirstCall:
    def test_get_client_creates_new_on_first_call(self):
        """First call to get_client() must create a new Redis instance and ping it."""
        mock_instance = MagicMock(spec=redis.Redis)

        with patch("shared.streaming.client.redis.Redis", return_value=mock_instance) as mock_cls:
            client = RedisClient.get_client()

        # A Redis instance was constructed exactly once
        mock_cls.assert_called_once()
        # ping() was called during _create_client (connection verification)
        mock_instance.ping.assert_called_once()
        assert client is mock_instance


class TestGetClientCaching:
    def test_get_client_returns_cached_on_second_call(self):
        """Subsequent calls return the same instance without creating a new one."""
        mock_instance = MagicMock(spec=redis.Redis)
        # ping always succeeds
        mock_instance.ping.return_value = True

        with patch("shared.streaming.client.redis.Redis", return_value=mock_instance) as mock_cls:
            first = RedisClient.get_client()
            second = RedisClient.get_client()

        # Redis() constructor called only once
        mock_cls.assert_called_once()
        assert first is second is mock_instance
        # ping called once in _create_client, once in the liveness check for the second call
        assert mock_instance.ping.call_count == 2


class TestGetClientReconnectsOnConnectionError:
    def test_get_client_reconnects_on_connection_error(self):
        """If the cached instance raises ConnectionError on ping, a new client is created."""
        stale_instance = MagicMock(spec=redis.Redis)
        fresh_instance = MagicMock(spec=redis.Redis)
        fresh_instance.ping.return_value = True

        # Simulate: first creation OK, subsequent liveness ping fails
        create_side_effects = [stale_instance, fresh_instance]

        with patch(
            "shared.streaming.client.redis.Redis", side_effect=create_side_effects
        ) as mock_cls:
            # Populate the singleton
            first = RedisClient.get_client()
            assert first is stale_instance

            # Make the cached instance appear dead
            stale_instance.ping.side_effect = redis.ConnectionError("lost connection")

            second = RedisClient.get_client()

        # Two Redis instances were created
        assert mock_cls.call_count == 2
        assert second is fresh_instance


class TestGetClientReconnectsOnTimeoutError:
    def test_get_client_reconnects_on_timeout_error(self):
        """If the cached instance raises TimeoutError on ping, a new client is created."""
        stale_instance = MagicMock(spec=redis.Redis)
        fresh_instance = MagicMock(spec=redis.Redis)
        fresh_instance.ping.return_value = True

        create_side_effects = [stale_instance, fresh_instance]

        with patch(
            "shared.streaming.client.redis.Redis", side_effect=create_side_effects
        ) as mock_cls:
            first = RedisClient.get_client()
            assert first is stale_instance

            stale_instance.ping.side_effect = redis.TimeoutError("timed out")

            second = RedisClient.get_client()

        assert mock_cls.call_count == 2
        assert second is fresh_instance


class TestClose:
    def test_close_clears_instance(self):
        """close() must call close() on the underlying client and set _instance to None."""
        mock_instance = MagicMock(spec=redis.Redis)

        with patch("shared.streaming.client.redis.Redis", return_value=mock_instance):
            RedisClient.get_client()

        assert RedisClient._instance is mock_instance

        RedisClient.close()

        mock_instance.close.assert_called_once()
        assert RedisClient._instance is None

    def test_close_is_idempotent_when_no_instance(self):
        """close() when no instance exists must not raise."""
        assert RedisClient._instance is None
        RedisClient.close()  # should not raise
        assert RedisClient._instance is None


class TestReset:
    def test_reset_clears_instance(self):
        """reset() must set _instance to None without calling close() on the client."""
        mock_instance = MagicMock(spec=redis.Redis)

        with patch("shared.streaming.client.redis.Redis", return_value=mock_instance):
            RedisClient.get_client()

        assert RedisClient._instance is mock_instance

        RedisClient.reset()

        # reset() is test-only — it skips close() on the underlying client
        mock_instance.close.assert_not_called()
        assert RedisClient._instance is None


class TestCreateClientParams:
    def test_create_client_uses_correct_kwargs(self):
        """_create_client() must pass socket timeouts to redis.Redis."""
        mock_instance = MagicMock(spec=redis.Redis)

        with patch("shared.streaming.client.redis.Redis", return_value=mock_instance) as mock_cls:
            RedisClient.get_client()

        _, kwargs = mock_cls.call_args
        assert kwargs.get("socket_connect_timeout") == 5
        assert kwargs.get("socket_timeout") == 5
        assert kwargs.get("decode_responses") is True

    def test_create_client_env_override(self, monkeypatch):
        """_create_client() reads host/port/db from environment variables."""
        monkeypatch.setenv("REDIS_HOST", "redis-test")
        monkeypatch.setenv("REDIS_PORT", "6380")
        monkeypatch.setenv("REDIS_DB", "3")
        monkeypatch.setenv("REDIS_PASSWORD", "secret")

        mock_instance = MagicMock(spec=redis.Redis)

        with patch("shared.streaming.client.redis.Redis", return_value=mock_instance) as mock_cls:
            RedisClient.get_client()

        _, kwargs = mock_cls.call_args
        assert kwargs["host"] == "redis-test"
        assert kwargs["port"] == 6380
        assert kwargs["db"] == 3
        assert kwargs["password"] == "secret"

    def test_create_client_empty_password_becomes_none(self, monkeypatch):
        """An empty REDIS_PASSWORD string is treated as None (no auth)."""
        monkeypatch.setenv("REDIS_PASSWORD", "")

        mock_instance = MagicMock(spec=redis.Redis)

        with patch("shared.streaming.client.redis.Redis", return_value=mock_instance) as mock_cls:
            RedisClient.get_client()

        _, kwargs = mock_cls.call_args
        assert kwargs["password"] is None


class TestThreadSafety:
    def test_get_client_thread_safe_single_instance(self):
        """Concurrent get_client() calls must produce only one Redis instance."""
        mock_instance = MagicMock(spec=redis.Redis)
        mock_instance.ping.return_value = True

        results: list = []
        errors: list = []

        def worker():
            try:
                results.append(RedisClient.get_client())
            except Exception as exc:
                errors.append(exc)

        with patch("shared.streaming.client.redis.Redis", return_value=mock_instance):
            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors
        assert all(c is mock_instance for c in results)
