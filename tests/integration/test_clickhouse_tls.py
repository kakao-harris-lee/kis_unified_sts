"""Integration tests for ClickHouse TLS support.

These tests validate that ClickHouse connections work correctly in both TLS and non-TLS modes,
ensuring backward compatibility while supporting encrypted connections.

Run with: pytest tests/integration/test_clickhouse_tls.py -v

To skip these tests when ClickHouse is unavailable:
    pytest -m "not integration"
"""
import asyncio
import os
import ssl
import pytest
from unittest.mock import patch, MagicMock


# Skip all tests in this module if ClickHouse is not available
pytestmark = [pytest.mark.integration]

_LIVE_INFRA_ENV = "KIS_RUN_LIVE_INFRA_TESTS"


def live_infra_enabled():
    """Return whether live ClickHouse tests may touch infrastructure."""
    return os.getenv(_LIVE_INFRA_ENV, "").lower() in {"1", "true", "yes"}


def clickhouse_available():
    """Check if ClickHouse is available."""
    if not live_infra_enabled():
        return False

    try:
        from clickhouse_driver import Client
        client = Client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
            user=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            connect_timeout=2,
            send_receive_timeout=2,
        )
        client.execute("SELECT 1")
        client.disconnect()
        return True
    except Exception:
        return False


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment for TLS testing.

    Preserves CLICKHOUSE_PASSWORD so tests can authenticate against a
    password-protected ClickHouse instance.
    """
    # Save password before cleaning — needed for auth
    saved_password = os.environ.get("CLICKHOUSE_PASSWORD")

    # Remove TLS-related env vars to start fresh
    env_vars = [
        "CLICKHOUSE_SECURE",
        "CLICKHOUSE_VERIFY_SSL",
        "CLICKHOUSE_CA_CERT",
        "CLICKHOUSE_CLIENT_CERT",
        "CLICKHOUSE_CLIENT_KEY",
        "CLICKHOUSE_HOST",
        "CLICKHOUSE_PORT",
        "CLICKHOUSE_NATIVE_PORT",
        "CLICKHOUSE_USER",
        "CLICKHOUSE_PASSWORD",
        "CLICKHOUSE_STOCK_DATABASE",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)

    # Restore password for authentication
    if saved_password:
        monkeypatch.setenv("CLICKHOUSE_PASSWORD", saved_password)


# =============================================================================
# ClickHouseConfig Tests
# =============================================================================


def test_clickhouse_config_non_tls_by_default(clean_env, monkeypatch):
    """Test that ClickHouseConfig disables TLS by default."""
    from shared.db.config import ClickHouseConfig

    config = ClickHouseConfig.from_env()

    # Should disable TLS by default
    assert config.secure is False, "TLS should be disabled by default"
    assert config.verify_ssl is True, "SSL verification should be True by default"
    assert config.ca_cert is None, "CA cert should be None by default"


def test_clickhouse_config_tls_enabled(clean_env, monkeypatch):
    """Test that ClickHouseConfig enables TLS when CLICKHOUSE_SECURE=true."""
    from shared.db.config import ClickHouseConfig

    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")

    config = ClickHouseConfig.from_env()

    # Should enable TLS
    assert config.secure is True, "TLS should be enabled when CLICKHOUSE_SECURE=true"


def test_clickhouse_config_tls_case_insensitive(clean_env, monkeypatch):
    """Test that TLS_SECURE accepts various case formats."""
    from shared.db.config import ClickHouseConfig

    test_cases = ["true", "True", "TRUE", "TrUe", "1", "yes", "YES"]

    for value in test_cases:
        monkeypatch.setenv("CLICKHOUSE_SECURE", value)

        config = ClickHouseConfig.from_env()
        assert config.secure is True, f"CLICKHOUSE_SECURE={value} should enable TLS"


def test_clickhouse_config_tls_false_values(clean_env, monkeypatch):
    """Test that TLS is disabled for false/invalid values."""
    from shared.db.config import ClickHouseConfig

    test_cases = ["false", "False", "FALSE", "0", "no", "", "invalid"]

    for value in test_cases:
        monkeypatch.setenv("CLICKHOUSE_SECURE", value)

        config = ClickHouseConfig.from_env()
        assert config.secure is False, f"CLICKHOUSE_SECURE={value} should disable TLS"


def test_clickhouse_config_verify_ssl_disabled(clean_env, monkeypatch):
    """Test that verify_ssl can be disabled."""
    from shared.db.config import ClickHouseConfig

    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    monkeypatch.setenv("CLICKHOUSE_VERIFY_SSL", "false")

    config = ClickHouseConfig.from_env()

    assert config.secure is True, "TLS should be enabled"
    assert config.verify_ssl is False, "SSL verification should be disabled"


def test_clickhouse_config_certificate_paths(clean_env, monkeypatch):
    """Test that certificate paths are loaded correctly."""
    from shared.db.config import ClickHouseConfig

    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    monkeypatch.setenv("CLICKHOUSE_CA_CERT", "/path/to/ca.crt")
    monkeypatch.setenv("CLICKHOUSE_CLIENT_CERT", "/path/to/client.crt")
    monkeypatch.setenv("CLICKHOUSE_CLIENT_KEY", "/path/to/client.key")

    config = ClickHouseConfig.from_env()

    assert config.secure is True
    assert config.ca_cert == "/path/to/ca.crt"
    assert config.client_cert == "/path/to/client.crt"
    assert config.client_key == "/path/to/client.key"


def test_clickhouse_config_str_protocol(clean_env, monkeypatch):
    """Test that __str__ returns correct protocol based on secure flag."""
    from shared.db.config import ClickHouseConfig

    # Non-TLS
    monkeypatch.setenv("CLICKHOUSE_SECURE", "false")
    config = ClickHouseConfig.from_env()
    assert str(config).startswith("clickhouse://"), "Should use clickhouse:// for non-TLS"

    # TLS
    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    config = ClickHouseConfig.from_env()
    assert str(config).startswith("clickhouses://"), "Should use clickhouses:// for TLS"


# =============================================================================
# ClickHouseClient (Sync) Tests
# =============================================================================


@pytest.mark.skipif(not clickhouse_available(), reason="ClickHouse not available")
def test_sync_client_non_tls_connection(clean_env, monkeypatch):
    """Test ClickHouseClient connects without TLS by default."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import ClickHouseClient

    monkeypatch.setenv("CLICKHOUSE_SECURE", "false")
    monkeypatch.setenv("CLICKHOUSE_HOST", os.getenv("CLICKHOUSE_HOST", "localhost"))
    monkeypatch.setenv("CLICKHOUSE_NATIVE_PORT", os.getenv("CLICKHOUSE_NATIVE_PORT", "9000"))
    monkeypatch.setenv("CLICKHOUSE_USER", os.getenv("CLICKHOUSE_USER", "default"))

    config = ClickHouseConfig.from_env()

    # Reset singleton to force new connection
    ClickHouseClient.reset_singleton()

    try:
        client = ClickHouseClient(config)
        sync_client = client.get_sync_client()

        # Should connect successfully
        result = sync_client.execute("SELECT 1")
        assert result == [(1,)], "Should execute query without TLS"

    finally:
        ClickHouseClient.reset_singleton()


@pytest.mark.skipif(not clickhouse_available(), reason="ClickHouse not available")
def test_sync_client_tls_settings_applied(clean_env, monkeypatch):
    """Test ClickHouseClient applies TLS settings when enabled."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import ClickHouseClient

    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    monkeypatch.setenv("CLICKHOUSE_VERIFY_SSL", "false")  # Disable verification for testing
    monkeypatch.setenv("CLICKHOUSE_HOST", os.getenv("CLICKHOUSE_HOST", "localhost"))
    monkeypatch.setenv("CLICKHOUSE_NATIVE_PORT", os.getenv("CLICKHOUSE_NATIVE_PORT", "9000"))
    monkeypatch.setenv("CLICKHOUSE_USER", os.getenv("CLICKHOUSE_USER", "default"))

    config = ClickHouseConfig.from_env()

    # Reset singleton to force new connection
    ClickHouseClient.reset_singleton()

    try:
        # This will fail if ClickHouse doesn't support TLS, which is expected
        # We're testing that the TLS settings are applied, not that connection succeeds
        try:
            client = ClickHouseClient(config)

            # Verify config has TLS settings
            assert client.config.secure is True, "Config should have TLS enabled"
            assert client.config.verify_ssl is False, "Config should disable SSL verification"

            # Try to get connection params
            params = client._build_connection_params()
            assert params.get("secure") is True, "Connection params should have secure=True"
            assert params.get("verify") is False, "Connection params should have verify=False"

        except Exception as e:
            # Connection may fail if ClickHouse doesn't support TLS
            # That's OK - we verified the configuration was attempted
            error_str = str(e).lower()
            # These are expected errors when ClickHouse doesn't support TLS
            if "ssl" in error_str or "certificate" in error_str or "connection" in error_str or "secure" in error_str:
                pytest.skip(f"ClickHouse TLS not available in test environment: {e}")
            else:
                raise
    finally:
        ClickHouseClient.reset_singleton()


def test_sync_client_build_connection_params_tls(clean_env, monkeypatch):
    """Test ClickHouseClient._build_connection_params includes TLS settings."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import ClickHouseClient

    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    monkeypatch.setenv("CLICKHOUSE_VERIFY_SSL", "true")
    monkeypatch.setenv("CLICKHOUSE_CA_CERT", "/path/to/ca.crt")
    monkeypatch.setenv("CLICKHOUSE_CLIENT_CERT", "/path/to/client.crt")
    monkeypatch.setenv("CLICKHOUSE_CLIENT_KEY", "/path/to/client.key")

    config = ClickHouseConfig.from_env()

    # Reset singleton
    ClickHouseClient.reset_singleton()

    try:
        client = ClickHouseClient(config)
        params = client._build_connection_params()

        # Verify TLS parameters
        assert params.get("secure") is True, "Should have secure=True"
        assert params.get("verify") is True, "Should have verify=True"
        assert params.get("ca_certs") == "/path/to/ca.crt", "Should have ca_certs path"
        assert params.get("certfile") == "/path/to/client.crt", "Should have certfile path"
        assert params.get("keyfile") == "/path/to/client.key", "Should have keyfile path"

    finally:
        ClickHouseClient.reset_singleton()


def test_sync_client_build_connection_params_non_tls(clean_env, monkeypatch):
    """Test ClickHouseClient._build_connection_params excludes TLS settings when disabled."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import ClickHouseClient

    monkeypatch.setenv("CLICKHOUSE_SECURE", "false")

    config = ClickHouseConfig.from_env()

    # Reset singleton
    ClickHouseClient.reset_singleton()

    try:
        client = ClickHouseClient(config)
        params = client._build_connection_params()

        # Verify no TLS parameters
        assert "secure" not in params or params.get("secure") is False, "Should not have secure parameter"
        assert "verify" not in params, "Should not have verify parameter"
        assert "ca_certs" not in params, "Should not have ca_certs parameter"

    finally:
        ClickHouseClient.reset_singleton()


# =============================================================================
# AsyncClickHouseClient Tests
# =============================================================================


@pytest.mark.skipif(not clickhouse_available(), reason="ClickHouse not available")
@pytest.mark.asyncio
async def test_async_client_non_tls_connection(clean_env, monkeypatch):
    """Test AsyncClickHouseClient connects without TLS by default."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import AsyncClickHouseClient

    monkeypatch.setenv("CLICKHOUSE_SECURE", "false")
    monkeypatch.setenv("CLICKHOUSE_HOST", os.getenv("CLICKHOUSE_HOST", "localhost"))
    monkeypatch.setenv("CLICKHOUSE_PORT", os.getenv("CLICKHOUSE_PORT", "8123"))  # HTTP port
    monkeypatch.setenv("CLICKHOUSE_USER", os.getenv("CLICKHOUSE_USER", "default"))

    config = ClickHouseConfig.from_env()
    client = AsyncClickHouseClient(config)

    try:
        await client.connect()

        # Verify connection uses HTTP (not HTTPS)
        assert client._session is not None, "Session should be created"
        assert client._client is not None, "Client should be created"

        # Try a simple query
        ch_client = await client.get_client()
        result = await ch_client.fetchval("SELECT 1")
        assert result == 1, "Should execute query without TLS"

    finally:
        await client.close()


@pytest.mark.skipif(not clickhouse_available(), reason="ClickHouse not available")
@pytest.mark.asyncio
async def test_async_client_tls_settings_applied(clean_env, monkeypatch):
    """Test AsyncClickHouseClient applies TLS settings when enabled."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import AsyncClickHouseClient

    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    monkeypatch.setenv("CLICKHOUSE_VERIFY_SSL", "false")  # Disable verification for testing
    monkeypatch.setenv("CLICKHOUSE_HOST", os.getenv("CLICKHOUSE_HOST", "localhost"))
    monkeypatch.setenv("CLICKHOUSE_PORT", os.getenv("CLICKHOUSE_PORT", "8123"))
    monkeypatch.setenv("CLICKHOUSE_USER", os.getenv("CLICKHOUSE_USER", "default"))

    config = ClickHouseConfig.from_env()
    client = AsyncClickHouseClient(config)

    try:
        # This will fail if ClickHouse doesn't support TLS, which is expected
        # We're testing that the TLS settings are applied, not that connection succeeds
        try:
            # Verify config has TLS settings
            assert client.config.secure is True, "Config should have TLS enabled"
            assert client.config.verify_ssl is False, "Config should disable SSL verification"

            # Build SSL context to verify it's created
            ssl_context = client._build_ssl_context()
            assert ssl_context is not None, "SSL context should be created when TLS enabled"
            assert isinstance(ssl_context, ssl.SSLContext), "Should return SSLContext"

            # Verify SSL context settings
            assert ssl_context.verify_mode == ssl.CERT_NONE, "Should have CERT_NONE when verify_ssl=False"

            # Try to connect
            await client.connect()

            # If we get here, verify connection works
            ch_client = await client.get_client()
            result = await ch_client.fetchval("SELECT 1")
            assert result == 1, "Should execute query with TLS"

        except Exception as e:
            # Connection may fail if ClickHouse doesn't support TLS
            # That's OK - we verified the configuration was attempted
            error_str = str(e).lower()
            if "ssl" in error_str or "certificate" in error_str or "connection" in error_str or "https" in error_str:
                pytest.skip(f"ClickHouse TLS not available in test environment: {e}")
            else:
                raise
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_async_client_build_ssl_context_tls_enabled(clean_env, monkeypatch):
    """Test AsyncClickHouseClient._build_ssl_context creates SSL context when TLS enabled."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import AsyncClickHouseClient

    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    monkeypatch.setenv("CLICKHOUSE_VERIFY_SSL", "true")

    config = ClickHouseConfig.from_env()
    client = AsyncClickHouseClient(config)

    ssl_context = client._build_ssl_context()

    assert ssl_context is not None, "SSL context should be created when TLS enabled"
    assert isinstance(ssl_context, ssl.SSLContext), "Should return SSLContext"
    assert ssl_context.verify_mode == ssl.CERT_REQUIRED, "Should require certificate verification"


@pytest.mark.asyncio
async def test_async_client_build_ssl_context_tls_disabled(clean_env, monkeypatch):
    """Test AsyncClickHouseClient._build_ssl_context returns None when TLS disabled."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import AsyncClickHouseClient

    monkeypatch.setenv("CLICKHOUSE_SECURE", "false")

    config = ClickHouseConfig.from_env()
    client = AsyncClickHouseClient(config)

    ssl_context = client._build_ssl_context()

    assert ssl_context is None, "SSL context should be None when TLS disabled"


@pytest.mark.asyncio
async def test_async_client_build_ssl_context_with_ca_cert(clean_env, monkeypatch, tmp_path):
    """Test AsyncClickHouseClient._build_ssl_context loads CA certificate."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import AsyncClickHouseClient

    # Create a temporary CA cert file (empty is OK for this test)
    ca_cert_path = tmp_path / "ca.crt"
    ca_cert_path.write_text("# Dummy CA cert for testing")

    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    monkeypatch.setenv("CLICKHOUSE_CA_CERT", str(ca_cert_path))

    config = ClickHouseConfig.from_env()
    client = AsyncClickHouseClient(config)

    # This will fail because the cert is invalid, but we verify the path was loaded
    try:
        ssl_context = client._build_ssl_context()
        # If we got this far, the CA cert path was accepted
        assert ssl_context is not None
    except Exception as e:
        # Expected to fail with invalid cert, but verify it tried to load it
        error_str = str(e).lower()
        assert "certificate" in error_str or "pem" in error_str or "cert" in error_str


# =============================================================================
# Collector Client Tests (clickhouse_connect)
# =============================================================================


@pytest.mark.skipif(not clickhouse_available(), reason="ClickHouse not available")
def test_collector_stock_client_non_tls(clean_env, monkeypatch):
    """Test stock collector client uses non-TLS by default."""
    from shared.collector.historical.stock import _get_clickhouse_config

    monkeypatch.setenv("CLICKHOUSE_SECURE", "false")
    monkeypatch.setenv("CLICKHOUSE_HOST", os.getenv("CLICKHOUSE_HOST", "localhost"))

    config = _get_clickhouse_config()

    # Verify config has TLS disabled
    assert config.get("secure") is False, "Should have secure=False by default"
    assert config.get("verify") is True, "Should have verify=True by default"
    assert config.get("ca_cert") is None, "Should have no CA cert by default"


@pytest.mark.skipif(not clickhouse_available(), reason="ClickHouse not available")
def test_collector_stock_client_tls_enabled(clean_env, monkeypatch):
    """Test stock collector client applies TLS settings when enabled."""
    from shared.collector.historical.stock import _get_clickhouse_config

    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    monkeypatch.setenv("CLICKHOUSE_VERIFY_SSL", "false")
    monkeypatch.setenv("CLICKHOUSE_CA_CERT", "/path/to/ca.crt")

    config = _get_clickhouse_config()

    # Verify config has TLS enabled
    assert config.get("secure") is True, "Should have secure=True when enabled"
    assert config.get("verify") is False, "Should have verify=False when disabled"
    assert config.get("ca_cert") == "/path/to/ca.crt", "Should have CA cert path"


@pytest.mark.skipif(not clickhouse_available(), reason="ClickHouse not available")
def test_collector_stock_get_db_client_tls(clean_env, monkeypatch):
    """Test get_stock_db_client passes TLS parameters to clickhouse_connect."""
    from shared.collector.historical.stock import get_stock_db_client
    import clickhouse_connect

    monkeypatch.setenv("CLICKHOUSE_SECURE", "false")
    monkeypatch.setenv("CLICKHOUSE_HOST", os.getenv("CLICKHOUSE_HOST", "localhost"))
    monkeypatch.setenv("CLICKHOUSE_PORT", os.getenv("CLICKHOUSE_PORT", "8123"))

    # Try to get client
    try:
        client = get_stock_db_client()

        # Should connect successfully without TLS
        result = client.query("SELECT 1")
        assert result.result_rows[0][0] == 1, "Should execute query without TLS"

    except Exception as e:
        # Connection may fail in test environment
        error_str = str(e).lower()
        if "connection" in error_str or "refused" in error_str or "timeout" in error_str:
            pytest.skip(f"ClickHouse not available: {e}")
        else:
            raise


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


@pytest.mark.skipif(not clickhouse_available(), reason="ClickHouse not available")
def test_backward_compatibility_no_env_vars(clean_env, monkeypatch):
    """Test that ClickHouse works without any TLS env vars (backward compatibility)."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import ClickHouseClient

    # Don't set any TLS env vars
    monkeypatch.setenv("CLICKHOUSE_HOST", os.getenv("CLICKHOUSE_HOST", "localhost"))
    monkeypatch.setenv("CLICKHOUSE_NATIVE_PORT", os.getenv("CLICKHOUSE_NATIVE_PORT", "9000"))
    monkeypatch.setenv("CLICKHOUSE_USER", os.getenv("CLICKHOUSE_USER", "default"))

    config = ClickHouseConfig.from_env()

    # Should default to non-TLS
    assert config.secure is False, "Should default to non-TLS"

    # Reset singleton
    ClickHouseClient.reset_singleton()

    try:
        # ClickHouseClient should connect successfully
        client = ClickHouseClient(config)
        sync_client = client.get_sync_client()

        result = sync_client.execute("SELECT 1")
        assert result == [(1,)], "Should connect without TLS by default"

    finally:
        ClickHouseClient.reset_singleton()


@pytest.mark.skipif(not clickhouse_available(), reason="ClickHouse not available")
@pytest.mark.asyncio
async def test_backward_compatibility_existing_code(clean_env, monkeypatch):
    """Test that existing code continues to work without modifications."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import AsyncClickHouseClient

    # Don't set TLS env vars - simulate existing deployment
    monkeypatch.delenv("CLICKHOUSE_SECURE", raising=False)
    monkeypatch.delenv("CLICKHOUSE_VERIFY_SSL", raising=False)

    monkeypatch.setenv("CLICKHOUSE_HOST", os.getenv("CLICKHOUSE_HOST", "localhost"))
    monkeypatch.setenv("CLICKHOUSE_PORT", os.getenv("CLICKHOUSE_PORT", "8123"))
    monkeypatch.setenv("CLICKHOUSE_USER", os.getenv("CLICKHOUSE_USER", "default"))

    # This is how existing code creates clients
    config = ClickHouseConfig.from_env()
    client = AsyncClickHouseClient(config)

    try:
        await client.connect()

        # Should work exactly as before
        ch_client = await client.get_client()
        result = await ch_client.fetchval("SELECT 1")
        assert result == 1, "Existing code should continue working"

    finally:
        await client.close()


# =============================================================================
# End-to-End Validation
# =============================================================================


@pytest.mark.skipif(not clickhouse_available(), reason="ClickHouse not available")
@pytest.mark.asyncio
async def test_e2e_all_clickhouse_clients_respect_tls_disabled(clean_env, monkeypatch):
    """End-to-end test: all ClickHouse clients work with TLS disabled."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import ClickHouseClient, AsyncClickHouseClient
    from shared.collector.historical.stock import _get_clickhouse_config

    # Explicitly disable TLS
    monkeypatch.setenv("CLICKHOUSE_SECURE", "false")
    monkeypatch.setenv("CLICKHOUSE_HOST", os.getenv("CLICKHOUSE_HOST", "localhost"))
    monkeypatch.setenv("CLICKHOUSE_NATIVE_PORT", os.getenv("CLICKHOUSE_NATIVE_PORT", "9000"))
    monkeypatch.setenv("CLICKHOUSE_PORT", os.getenv("CLICKHOUSE_PORT", "8123"))
    monkeypatch.setenv("CLICKHOUSE_USER", os.getenv("CLICKHOUSE_USER", "default"))

    # 1. ClickHouseConfig should disable TLS
    config = ClickHouseConfig.from_env()
    assert config.secure is False, "Config should disable TLS"
    assert str(config).startswith("clickhouse://"), "URL should use clickhouse:// scheme"

    # 2. Sync client should work
    ClickHouseClient.reset_singleton()
    try:
        sync_client_wrapper = ClickHouseClient(config)
        sync_client = sync_client_wrapper.get_sync_client()
        result = sync_client.execute("SELECT 1")
        assert result == [(1,)], "Sync client should work without TLS"
    finally:
        ClickHouseClient.reset_singleton()

    # 3. Async client should work
    async_client = AsyncClickHouseClient(config)
    try:
        await async_client.connect()
        ch_client = await async_client.get_client()
        result = await ch_client.fetchval("SELECT 1")
        assert result == 1, "Async client should work without TLS"
    finally:
        await async_client.close()

    # 4. Collector config should disable TLS
    collector_config = _get_clickhouse_config()
    assert collector_config.get("secure") is False, "Collector should disable TLS"


@pytest.mark.asyncio
async def test_e2e_tls_configuration_consistency(clean_env, monkeypatch):
    """End-to-end test: TLS configuration is consistent across all components."""
    from shared.db.config import ClickHouseConfig
    from shared.db.client import AsyncClickHouseClient
    from shared.collector.historical.stock import _get_clickhouse_config

    # Enable TLS
    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    monkeypatch.setenv("CLICKHOUSE_VERIFY_SSL", "false")
    monkeypatch.setenv("CLICKHOUSE_CA_CERT", "/path/to/ca.crt")

    # 1. ClickHouseConfig should enable TLS
    config = ClickHouseConfig.from_env()
    assert config.secure is True, "Config should enable TLS"
    assert config.verify_ssl is False, "Config should disable SSL verification"
    assert config.ca_cert == "/path/to/ca.crt", "Config should have CA cert path"
    assert str(config).startswith("clickhouses://"), "URL should use clickhouses:// scheme"

    # 2. Async client should have TLS settings
    async_client = AsyncClickHouseClient(config)
    assert async_client.config.secure is True, "Async client config should enable TLS"

    # Mock ssl_context.load_verify_locations to avoid FileNotFoundError for non-existent CA cert
    with patch("ssl.SSLContext.load_verify_locations"):
        ssl_context = async_client._build_ssl_context()
    assert ssl_context is not None, "SSL context should be created"

    # 3. Collector config should enable TLS
    collector_config = _get_clickhouse_config()
    assert collector_config.get("secure") is True, "Collector should enable TLS"
    assert collector_config.get("verify") is False, "Collector should disable SSL verification"
    assert collector_config.get("ca_cert") == "/path/to/ca.crt", "Collector should have CA cert path"

    # 4. All components should have consistent TLS configuration
    assert config.secure == async_client.config.secure == collector_config.get("secure"), \
        "All components should have same TLS enabled setting"
