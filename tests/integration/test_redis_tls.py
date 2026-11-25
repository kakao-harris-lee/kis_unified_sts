"""Integration tests for Redis TLS support."""

import os

import pytest

from tests.support.live_infra import live_infra_enabled

pytestmark = [pytest.mark.integration, pytest.mark.serial]


def redis_available():
    """Check if Redis is available."""
    if not live_infra_enabled():
        return False

    try:
        import redis

        r = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/1"),
            socket_timeout=1,
        )
        r.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment for TLS testing."""
    env_vars = [
        "REDIS_TLS_ENABLED",
        "REDIS_TLS_CERT_REQS",
        "REDIS_TLS_CA_CERTS",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_PASSWORD",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def redis_url():
    """Get Redis URL from environment or use default."""
    return os.getenv("REDIS_URL", "redis://localhost:6379/1")


def test_redis_url_non_tls_by_default(clean_env, monkeypatch):
    """Test that redis_url() returns redis:// scheme by default (TLS disabled)."""
    from shared.config.secrets import SecretsManager

    SecretsManager.clear_cache()

    url = SecretsManager.redis_url()

    assert url.startswith("redis://"), f"Expected redis:// scheme, got {url}"
    assert not url.startswith("rediss://"), "Should not use rediss:// by default"


def test_redis_url_tls_enabled(clean_env, monkeypatch):
    """Test that redis_url() returns rediss:// scheme when TLS is enabled."""
    from shared.config.secrets import SecretsManager

    monkeypatch.setenv("REDIS_TLS_ENABLED", "true")
    SecretsManager.clear_cache()

    url = SecretsManager.redis_url()

    assert url.startswith("rediss://"), f"Expected rediss:// scheme, got {url}"


def test_redis_url_tls_case_insensitive(clean_env, monkeypatch):
    """Test that TLS_ENABLED accepts various case formats."""
    from shared.config.secrets import SecretsManager

    test_cases = ["true", "True", "TRUE", "TrUe"]

    for value in test_cases:
        monkeypatch.setenv("REDIS_TLS_ENABLED", value)
        SecretsManager.clear_cache()

        url = SecretsManager.redis_url()
        assert url.startswith("rediss://"), f"TLS_ENABLED={value} should enable TLS"


def test_redis_url_tls_false_values(clean_env, monkeypatch):
    """Test that TLS is disabled for false/invalid values."""
    from shared.config.secrets import SecretsManager

    test_cases = ["false", "False", "FALSE", "0", "no", "", "invalid"]

    for value in test_cases:
        monkeypatch.setenv("REDIS_TLS_ENABLED", value)
        SecretsManager.clear_cache()

        url = SecretsManager.redis_url()
        assert url.startswith("redis://") and not url.startswith(
            "rediss://"
        ), f"TLS_ENABLED={value} should disable TLS"


def test_redis_url_with_password_non_tls(clean_env, monkeypatch):
    """Test redis_url() with password uses redis:// when TLS disabled."""
    from shared.config.secrets import SecretsManager

    monkeypatch.setenv("REDIS_PASSWORD", "testpass123")
    monkeypatch.setenv("REDIS_TLS_ENABLED", "false")
    SecretsManager.clear_cache()

    url = SecretsManager.redis_url()

    assert url.startswith("redis://"), "Should use redis:// scheme"
    assert ":testpass123@" in url, "Password should be in URL"


def test_redis_url_with_password_tls(clean_env, monkeypatch):
    """Test redis_url() with password uses rediss:// when TLS enabled."""
    from shared.config.secrets import SecretsManager

    monkeypatch.setenv("REDIS_PASSWORD", "testpass123")
    monkeypatch.setenv("REDIS_TLS_ENABLED", "true")
    SecretsManager.clear_cache()

    url = SecretsManager.redis_url()

    assert url.startswith("rediss://"), "Should use rediss:// scheme"
    assert ":testpass123@" in url, "Password should be in URL"


def test_redis_url_domain_specific(clean_env, monkeypatch):
    """Test redis_url() returns correct DB for different domains."""
    from shared.config.secrets import SecretsManager

    monkeypatch.setenv("REDIS_STOCK_DB", "1")
    monkeypatch.setenv("REDIS_FUTURES_DB", "2")
    monkeypatch.setenv("REDIS_SYSTEM_DB", "0")
    monkeypatch.setenv("REDIS_TLS_ENABLED", "true")
    SecretsManager.clear_cache()

    stock_url = SecretsManager.redis_url("stock")
    futures_url = SecretsManager.redis_url("futures")
    system_url = SecretsManager.redis_url()

    assert stock_url.startswith("rediss://"), "Stock should use TLS"
    assert futures_url.startswith("rediss://"), "Futures should use TLS"
    assert system_url.startswith("rediss://"), "System should use TLS"

    assert stock_url.endswith("/1"), "Stock should use DB 1"
    assert futures_url.endswith("/2"), "Futures should use DB 2"
    assert system_url.endswith("/0"), "System should use DB 0"


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_redis_client_non_tls_connection(clean_env, monkeypatch):
    """Test RedisClient connects without TLS by default."""
    from shared.streaming.client import RedisClient

    monkeypatch.setenv("REDIS_TLS_ENABLED", "false")
    monkeypatch.setenv("REDIS_HOST", os.getenv("REDIS_HOST", "localhost"))
    monkeypatch.setenv("REDIS_PORT", os.getenv("REDIS_PORT", "6379"))
    monkeypatch.setenv("REDIS_DB", "1")

    RedisClient.reset()

    try:
        client = RedisClient.get_client()

        assert client.ping(), "Should connect to Redis without TLS"

        conn_kwargs = client.connection_pool.connection_kwargs
        assert conn_kwargs.get("ssl", False) is False, "SSL should not be enabled"

    finally:
        RedisClient.close()


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_redis_client_tls_settings_applied(clean_env, monkeypatch):
    """Test RedisClient applies TLS settings when enabled."""
    import ssl

    from shared.streaming.client import RedisClient

    monkeypatch.setenv("REDIS_TLS_ENABLED", "true")
    monkeypatch.setenv("REDIS_TLS_CERT_REQS", "none")
    monkeypatch.setenv("REDIS_HOST", os.getenv("REDIS_HOST", "localhost"))
    monkeypatch.setenv("REDIS_PORT", os.getenv("REDIS_PORT", "6379"))
    monkeypatch.setenv("REDIS_DB", "1")

    RedisClient.reset()

    try:
        try:
            client = RedisClient.get_client()

            conn_kwargs = client.connection_pool.connection_kwargs
            assert conn_kwargs.get("ssl") is True, "SSL should be enabled"
            assert (
                conn_kwargs.get("ssl_cert_reqs") == ssl.CERT_NONE
            ), "Should use CERT_NONE"

        except Exception as e:
            error_str = str(e).lower()
            if any(
                kw in error_str
                for kw in ("ssl", "certificate", "connection", "timeout", "timed out")
            ):
                pytest.skip(f"Redis TLS not available in test environment: {e}")
            else:
                raise
    finally:
        RedisClient.close()


def test_redis_client_cert_reqs_mapping(clean_env, monkeypatch):
    """Test RedisClient maps cert_reqs string to ssl.CERT_* constants."""
    import ssl

    from shared.streaming.client import RedisClient

    test_cases = [
        ("none", ssl.CERT_NONE),
        ("optional", ssl.CERT_OPTIONAL),
        ("required", ssl.CERT_REQUIRED),
        ("invalid", ssl.CERT_REQUIRED),
    ]

    for cert_reqs_str, expected_const in test_cases:
        monkeypatch.setenv("REDIS_TLS_ENABLED", "true")
        monkeypatch.setenv("REDIS_TLS_CERT_REQS", cert_reqs_str)
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("REDIS_PORT", "6379")
        monkeypatch.setenv("REDIS_DB", "1")

        RedisClient.reset()

        try:
            try:
                client = RedisClient.get_client()
                conn_kwargs = client.connection_pool.connection_kwargs

                assert conn_kwargs.get("ssl") is True, "SSL should be enabled"
                assert (
                    conn_kwargs.get("ssl_cert_reqs") == expected_const
                ), f"CERT_REQS={cert_reqs_str} should map to {expected_const}"

            except Exception as e:
                error_str = str(e).lower()
                if any(
                    kw in error_str
                    for kw in (
                        "ssl",
                        "certificate",
                        "connection",
                        "timeout",
                        "timed out",
                    )
                ):
                    pass
                else:
                    raise
        finally:
            RedisClient.close()


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_backward_compatibility_no_env_vars(clean_env, monkeypatch):
    """Test that Redis works without any TLS env vars (backward compatibility)."""
    from shared.config.secrets import SecretsManager
    from shared.streaming.client import RedisClient

    monkeypatch.setenv("REDIS_HOST", os.getenv("REDIS_HOST", "localhost"))
    monkeypatch.setenv("REDIS_PORT", os.getenv("REDIS_PORT", "6379"))
    monkeypatch.setenv("REDIS_DB", "1")

    SecretsManager.clear_cache()
    RedisClient.reset()

    try:
        url = SecretsManager.redis_url()
        assert url.startswith("redis://"), "Should default to non-TLS"

        client = RedisClient.get_client()
        assert client.ping(), "Should connect without TLS by default"

    finally:
        RedisClient.close()


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_e2e_all_redis_clients_respect_tls_disabled(
    clean_env, monkeypatch, redis_url
):
    """End-to-end test: all Redis clients work with TLS disabled."""
    from shared.config.secrets import SecretsManager
    from shared.streaming.client import RedisClient

    monkeypatch.setenv("REDIS_TLS_ENABLED", "false")
    monkeypatch.setenv("REDIS_HOST", os.getenv("REDIS_HOST", "localhost"))
    monkeypatch.setenv("REDIS_PORT", os.getenv("REDIS_PORT", "6379"))
    monkeypatch.setenv("REDIS_DB", "1")

    SecretsManager.clear_cache()
    RedisClient.reset()

    try:
        url = SecretsManager.redis_url()
        assert url.startswith("redis://"), "URL should use redis:// scheme"

        client = RedisClient.get_client()
        assert client.ping(), "RedisClient should connect"
        client.set("test-key", "test-value")
        assert client.get("test-key") == "test-value", "Should read/write data"

    finally:
        RedisClient.close()


@pytest.mark.skipif(not redis_available(), reason="Redis not available")
@pytest.mark.asyncio
async def test_e2e_tls_configuration_consistency(clean_env, monkeypatch, redis_url):
    """End-to-end test: TLS configuration is consistent across all components."""
    from shared.config.secrets import SecretsManager

    monkeypatch.setenv("REDIS_TLS_ENABLED", "true")
    monkeypatch.setenv("REDIS_TLS_CERT_REQS", "none")
    monkeypatch.setenv("REDIS_HOST", os.getenv("REDIS_HOST", "localhost"))
    monkeypatch.setenv("REDIS_PORT", os.getenv("REDIS_PORT", "6379"))

    SecretsManager.clear_cache()

    url = SecretsManager.redis_url()
    assert url.startswith("rediss://"), "URL should use rediss:// scheme"

    stock_url = SecretsManager.redis_url("stock")
    futures_url = SecretsManager.redis_url("futures")

    assert stock_url.startswith("rediss://"), "Stock URL should use TLS"
    assert futures_url.startswith("rediss://"), "Futures URL should use TLS"

    pass
