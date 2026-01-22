"""Tests for async HTTP session management utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAsyncSessionMixin:
    """Tests for AsyncSessionMixin."""

    @pytest.mark.asyncio
    async def test_lazy_session_creation(self):
        """Test that session is created lazily on first access."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        # Initially no session
        assert not hasattr(client, "_session") or client._session is None
        assert not client._session_active

        # Get session creates one
        with patch("aiohttp.ClientSession") as MockSession:
            mock_session = MagicMock()
            mock_session.closed = False
            MockSession.return_value = mock_session

            session = await client._get_session()

            MockSession.assert_called_once()
            assert session is mock_session
            assert client._session is mock_session

    @pytest.mark.asyncio
    async def test_session_reuse(self):
        """Test that subsequent calls return the same session."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        with patch("aiohttp.ClientSession") as MockSession:
            mock_session = MagicMock()
            mock_session.closed = False
            MockSession.return_value = mock_session

            session1 = await client._get_session()
            session2 = await client._get_session()
            session3 = await client._get_session()

            # Should only create one session
            MockSession.assert_called_once()
            assert session1 is session2 is session3

    @pytest.mark.asyncio
    async def test_session_recreation_when_closed(self):
        """Test that a new session is created if previous one is closed."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        with patch("aiohttp.ClientSession") as MockSession:
            mock_session1 = MagicMock()
            mock_session1.closed = False
            mock_session2 = MagicMock()
            mock_session2.closed = False
            MockSession.side_effect = [mock_session1, mock_session2]

            # First call creates session
            session1 = await client._get_session()
            assert session1 is mock_session1

            # Mark as closed
            mock_session1.closed = True

            # Next call should create new session
            session2 = await client._get_session()
            assert session2 is mock_session2
            assert MockSession.call_count == 2

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test session closure."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        with patch("aiohttp.ClientSession") as MockSession:
            mock_session = MagicMock()
            mock_session.closed = False
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session

            # Create session
            await client._get_session()
            assert client._session_active

            # Close it
            await client._close_session()

            mock_session.close.assert_called_once()
            assert client._session is None
            assert not client._session_active

    @pytest.mark.asyncio
    async def test_close_already_closed_session(self):
        """Test that closing an already closed session is safe."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        # Close without ever creating session
        await client._close_session()
        assert client._session is None

        # Close again
        await client._close_session()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_close_does_not_close_already_closed_aiohttp_session(self):
        """Test that we don't call close() on already closed aiohttp session."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        with patch("aiohttp.ClientSession") as MockSession:
            mock_session = MagicMock()
            mock_session.closed = True  # Already closed
            mock_session.close = AsyncMock()
            MockSession.return_value = mock_session

            client._session = mock_session

            await client._close_session()

            # close() should NOT be called since session.closed is True
            mock_session.close.assert_not_called()
            assert client._session is None

    @pytest.mark.asyncio
    async def test_session_active_property(self):
        """Test _session_active property."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        # No session yet
        assert not client._session_active

        # Mock session
        mock_session = MagicMock()
        mock_session.closed = False
        client._session = mock_session

        assert client._session_active

        # Closed session
        mock_session.closed = True
        assert not client._session_active

    @pytest.mark.asyncio
    async def test_multiple_instances_have_separate_sessions(self):
        """Test that multiple instances don't share sessions (critical bug fix)."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client1 = TestClient()
        client2 = TestClient()

        with patch("aiohttp.ClientSession") as MockSession:
            mock_session1 = MagicMock()
            mock_session1.closed = False
            mock_session2 = MagicMock()
            mock_session2.closed = False
            MockSession.side_effect = [mock_session1, mock_session2]

            session1 = await client1._get_session()
            session2 = await client2._get_session()

            # Each client should have its own session
            assert session1 is not session2
            assert client1._session is mock_session1
            assert client2._session is mock_session2
            assert MockSession.call_count == 2

    @pytest.mark.asyncio
    async def test_closing_one_instance_does_not_affect_other(self):
        """Test that closing one instance's session doesn't affect others."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client1 = TestClient()
        client2 = TestClient()

        with patch("aiohttp.ClientSession") as MockSession:
            mock_session1 = MagicMock()
            mock_session1.closed = False
            mock_session1.close = AsyncMock()
            mock_session2 = MagicMock()
            mock_session2.closed = False
            MockSession.side_effect = [mock_session1, mock_session2]

            await client1._get_session()
            await client2._get_session()

            # Close client1's session
            await client1._close_session()

            # client2 should still have its session
            assert client1._session is None
            assert client2._session is mock_session2
            assert client2._session_active


class TestAsyncSessionWithTimeoutMixin:
    """Tests for AsyncSessionWithTimeoutMixin."""

    @pytest.mark.asyncio
    async def test_session_created_with_timeout(self):
        """Test that session is created with configured timeout."""
        from unittest.mock import ANY
        from shared.http.session import AsyncSessionWithTimeoutMixin

        class TestClient(AsyncSessionWithTimeoutMixin):
            _session_timeout = 15.0

        client = TestClient()

        with patch("aiohttp.ClientSession") as MockSession:
            with patch("aiohttp.ClientTimeout") as MockTimeout:
                mock_timeout = MagicMock()
                MockTimeout.return_value = mock_timeout

                mock_session = MagicMock()
                mock_session.closed = False
                MockSession.return_value = mock_session

                await client._get_session()

                MockTimeout.assert_called_once_with(total=15.0)
                # Session is created with timeout and SSL connector
                MockSession.assert_called_once_with(
                    timeout=mock_timeout, connector=ANY
                )

    @pytest.mark.asyncio
    async def test_default_timeout(self):
        """Test default timeout value."""
        from shared.http.session import AsyncSessionWithTimeoutMixin

        class TestClient(AsyncSessionWithTimeoutMixin):
            pass

        client = TestClient()
        assert client._session_timeout == 30.0

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Test custom timeout configuration."""
        from shared.http.session import AsyncSessionWithTimeoutMixin

        class TestClient(AsyncSessionWithTimeoutMixin):
            _session_timeout = 60.0

        client = TestClient()
        assert client._session_timeout == 60.0


class TestAsyncSessionMixinInheritance:
    """Test mixin inheritance patterns."""

    @pytest.mark.asyncio
    async def test_mixin_with_multiple_inheritance(self):
        """Test mixin works with multiple inheritance."""
        from shared.http.session import AsyncSessionMixin

        class SomeOtherMixin:
            def other_method(self):
                return "other"

        class TestClient(AsyncSessionMixin, SomeOtherMixin):
            def __init__(self, name: str):
                self.name = name

        client = TestClient("test")

        with patch("aiohttp.ClientSession") as MockSession:
            mock_session = MagicMock()
            mock_session.closed = False
            MockSession.return_value = mock_session

            session = await client._get_session()

            assert session is mock_session
            assert client.name == "test"
            assert client.other_method() == "other"

    @pytest.mark.asyncio
    async def test_mixin_works_with_dataclass_like_classes(self):
        """Test mixin works with classes that have __init__ args."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            def __init__(self, base_url: str, api_key: str):
                self.base_url = base_url
                self.api_key = api_key

        client = TestClient("https://api.example.com", "secret")

        with patch("aiohttp.ClientSession") as MockSession:
            mock_session = MagicMock()
            mock_session.closed = False
            MockSession.return_value = mock_session

            session = await client._get_session()

            assert session is mock_session
            assert client.base_url == "https://api.example.com"
            assert client.api_key == "secret"


class TestAsyncSessionMixinLogging:
    """Test logging behavior."""

    @pytest.mark.asyncio
    async def test_logs_session_creation(self, caplog):
        """Test that session creation is logged."""
        import logging
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        with caplog.at_level(logging.DEBUG):
            with patch("aiohttp.ClientSession") as MockSession:
                mock_session = MagicMock()
                mock_session.closed = False
                MockSession.return_value = mock_session

                await client._get_session()

        assert "session created" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_logs_session_closure(self, caplog):
        """Test that session closure is logged."""
        import logging
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        with caplog.at_level(logging.DEBUG):
            with patch("aiohttp.ClientSession") as MockSession:
                mock_session = MagicMock()
                mock_session.closed = False
                mock_session.close = AsyncMock()
                MockSession.return_value = mock_session

                await client._get_session()
                await client._close_session()

        assert "session closed" in caplog.text.lower()


class TestAsyncSessionSSLConfiguration:
    """Test SSL configuration features."""

    def test_default_ssl_verify_enabled(self):
        """Test SSL verification is enabled by default."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()
        assert client._ssl_verify is True
        assert client._ssl_context is None
        assert client._get_ssl_context() is True

    def test_ssl_verify_disabled(self):
        """Test disabling SSL verification."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            _ssl_verify = False

        client = TestClient()
        assert client._get_ssl_context() is False

    def test_custom_ssl_context(self):
        """Test custom SSL context."""
        import ssl
        from shared.http.session import AsyncSessionMixin

        custom_context = ssl.create_default_context()

        class TestClient(AsyncSessionMixin):
            _ssl_context = custom_context

        client = TestClient()
        assert client._get_ssl_context() is custom_context

    def test_ssl_context_takes_precedence_over_verify(self):
        """Test that custom SSL context takes precedence over _ssl_verify."""
        import ssl
        from shared.http.session import AsyncSessionMixin

        custom_context = ssl.create_default_context()

        class TestClient(AsyncSessionMixin):
            _ssl_verify = False  # This should be ignored
            _ssl_context = custom_context

        client = TestClient()
        # Custom context should take precedence
        assert client._get_ssl_context() is custom_context

    @pytest.mark.asyncio
    async def test_session_created_with_ssl_connector(self):
        """Test that session is created with SSL-configured connector."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        with patch("aiohttp.ClientSession") as MockSession:
            with patch("aiohttp.TCPConnector") as MockConnector:
                mock_connector = MagicMock()
                MockConnector.return_value = mock_connector

                mock_session = MagicMock()
                mock_session.closed = False
                MockSession.return_value = mock_session

                await client._get_session()

                # Connector should be created with SSL=True and pool config
                call_kwargs = MockConnector.call_args.kwargs
                assert call_kwargs["ssl"] is True
                assert call_kwargs["limit"] == 100  # Default pool limit
                assert call_kwargs["limit_per_host"] == 0  # Default unlimited
                MockSession.assert_called_once_with(connector=mock_connector)


class TestConnectionPoolConfig:
    """Test connection pool configuration."""

    def test_default_pool_config(self):
        """Test default pool configuration values."""
        from shared.http.session import ConnectionPoolConfig

        config = ConnectionPoolConfig()

        assert config.limit == 100
        assert config.limit_per_host == 0
        assert config.keepalive_timeout == 15.0
        assert config.enable_cleanup_closed is True
        assert config.ttl_dns_cache == 10

    def test_custom_pool_config(self):
        """Test custom pool configuration."""
        from shared.http.session import ConnectionPoolConfig

        config = ConnectionPoolConfig(
            limit=50,
            limit_per_host=10,
            keepalive_timeout=30.0,
            enable_cleanup_closed=False,
            ttl_dns_cache=60,
        )

        assert config.limit == 50
        assert config.limit_per_host == 10
        assert config.keepalive_timeout == 30.0
        assert config.enable_cleanup_closed is False
        assert config.ttl_dns_cache == 60


class TestAsyncSessionPooling:
    """Test connection pooling configuration."""

    def test_default_pool_limits(self):
        """Test default pool limit values."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            pass

        client = TestClient()

        assert client._pool_limit == 100
        assert client._pool_limit_per_host == 0
        assert client._pool_keepalive_timeout == 15.0

    def test_custom_pool_limits_via_attributes(self):
        """Test custom pool limits via class attributes."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            _pool_limit = 50
            _pool_limit_per_host = 5
            _pool_keepalive_timeout = 30.0

        client = TestClient()
        config = client._get_pool_config()

        assert config.limit == 50
        assert config.limit_per_host == 5
        assert config.keepalive_timeout == 30.0

    def test_custom_pool_config_object(self):
        """Test custom pool configuration via config object."""
        from shared.http.session import AsyncSessionMixin, ConnectionPoolConfig

        custom_config = ConnectionPoolConfig(
            limit=25,
            limit_per_host=3,
            keepalive_timeout=10.0,
        )

        class TestClient(AsyncSessionMixin):
            _pool_config = custom_config

        client = TestClient()
        config = client._get_pool_config()

        assert config is custom_config
        assert config.limit == 25
        assert config.limit_per_host == 3

    def test_pool_config_takes_precedence_over_attributes(self):
        """Test that _pool_config takes precedence over individual attributes."""
        from shared.http.session import AsyncSessionMixin, ConnectionPoolConfig

        custom_config = ConnectionPoolConfig(limit=10)

        class TestClient(AsyncSessionMixin):
            _pool_config = custom_config
            _pool_limit = 999  # Should be ignored

        client = TestClient()
        config = client._get_pool_config()

        assert config.limit == 10  # From config object, not attribute

    @pytest.mark.asyncio
    async def test_session_created_with_custom_pool_config(self):
        """Test that session is created with custom pool configuration."""
        from shared.http.session import AsyncSessionMixin

        class TestClient(AsyncSessionMixin):
            _pool_limit = 50
            _pool_limit_per_host = 10

        client = TestClient()

        with patch("aiohttp.ClientSession") as MockSession:
            with patch("aiohttp.TCPConnector") as MockConnector:
                mock_connector = MagicMock()
                MockConnector.return_value = mock_connector

                mock_session = MagicMock()
                mock_session.closed = False
                MockSession.return_value = mock_session

                await client._get_session()

                call_kwargs = MockConnector.call_args.kwargs
                assert call_kwargs["limit"] == 50
                assert call_kwargs["limit_per_host"] == 10
