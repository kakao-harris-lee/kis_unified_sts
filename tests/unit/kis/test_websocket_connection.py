"""Unit tests for WebSocket connection lifecycle."""
import pytest
from unittest.mock import MagicMock, patch


class TestKISWebSocketAdapterInit:
    """Tests for adapter initialization."""

    def test_init_real_mode(self, mock_config):
        """Test initialization in real mode."""
        mock_config.is_real = True

        with patch('shared.kis.websocket.websocket.WebSocketApp'):
            from shared.kis.websocket import KISWebSocketAdapter
            adapter = KISWebSocketAdapter(mock_config)

            assert adapter.ws_url == "ws://ops.koreainvestment.com:21000"
            assert adapter._connected is False
            assert adapter._running is False

    def test_init_mock_mode(self, mock_config):
        """Test initialization in mock mode."""
        mock_config.is_real = False

        with patch('shared.kis.websocket.websocket.WebSocketApp'):
            from shared.kis.websocket import KISWebSocketAdapter
            adapter = KISWebSocketAdapter(mock_config)

            assert adapter.ws_url == "ws://ops.koreainvestment.com:31000"

    def test_init_bounded_queue(self, mock_config):
        """Test message queue is bounded."""
        with patch('shared.kis.websocket.websocket.WebSocketApp'):
            from shared.kis.websocket import KISWebSocketAdapter, MESSAGE_QUEUE_MAXSIZE
            adapter = KISWebSocketAdapter(mock_config)

            assert adapter._message_queue.maxsize == MESSAGE_QUEUE_MAXSIZE


class TestThreadSafeStateAccessors:
    """Tests for thread-safe state accessors."""

    def test_is_connected_property(self, mock_adapter):
        """Test is_connected property is thread-safe."""
        assert mock_adapter.is_connected is False

        mock_adapter._set_connected(True)
        assert mock_adapter.is_connected is True

    def test_is_running_property(self, mock_adapter):
        """Test is_running property is thread-safe."""
        assert mock_adapter.is_running is False

        mock_adapter._set_running(True)
        assert mock_adapter.is_running is True

    def test_connected_event_set(self, mock_adapter):
        """Test connected event is set when connected."""
        assert not mock_adapter._connected_event.is_set()

        mock_adapter._set_connected(True)
        assert mock_adapter._connected_event.is_set()

    def test_connected_event_clear(self, mock_adapter):
        """Test connected event is cleared when disconnected."""
        mock_adapter._set_connected(True)
        assert mock_adapter._connected_event.is_set()

        mock_adapter._set_connected(False)
        assert not mock_adapter._connected_event.is_set()


class TestWebSocketHandlers:
    """Tests for WebSocket event handlers."""

    def test_on_open_sets_connected(self, mock_adapter):
        """Test _on_open handler sets connected state."""
        assert mock_adapter.is_connected is False

        mock_adapter._on_open(None)

        assert mock_adapter.is_connected is True
        assert mock_adapter._connected_event.is_set()

    def test_on_close_clears_connected(self, mock_adapter):
        """Test _on_close handler clears connected state."""
        mock_adapter._set_connected(True)

        mock_adapter._on_close(None, 1000, "Normal closure")

        assert mock_adapter.is_connected is False

    def test_on_message_queues_message(self, mock_adapter):
        """Test _on_message queues incoming messages."""
        mock_adapter._on_message(None, "test_message")

        assert not mock_adapter._message_queue.empty()
        assert mock_adapter._message_queue.get() == "test_message"

    def test_on_message_queue_overflow(self, mock_adapter):
        """Test _on_message handles queue overflow."""
        # Fill queue to capacity
        for i in range(mock_adapter._message_queue.maxsize):
            mock_adapter._message_queue.put_nowait(f"msg_{i}")

        # Should not raise, should drop oldest
        mock_adapter._on_message(None, "new_message")

        # Queue should still be full
        assert mock_adapter._message_queue.full()


class TestSymbolValidation:
    """Tests for symbol validation in subscribe."""

    def test_empty_symbols_raises(self, mock_adapter):
        """Test empty symbols list raises ValueError."""
        mock_adapter._set_connected(True)

        with pytest.raises(ValueError, match="At least one symbol required"):
            mock_adapter.subscribe([], lambda x: None)

    def test_invalid_symbol_format_raises(self, mock_adapter):
        """Test invalid symbol format raises ValueError."""
        mock_adapter._set_connected(True)

        with pytest.raises(ValueError, match="Invalid symbol format"):
            mock_adapter.subscribe(["invalid;symbol"], lambda x: None)

    def test_valid_symbol_formats(self, mock_adapter):
        """Test valid symbol formats are accepted."""
        _ = mock_adapter
        from shared.kis.websocket import SYMBOL_PATTERN

        valid_symbols = ["101V01", "A05601", "105X25", "KOSPI200"]

        for symbol in valid_symbols:
            assert SYMBOL_PATTERN.match(symbol), f"Should accept: {symbol}"

    def test_invalid_symbol_formats(self, mock_adapter):
        """Test invalid symbol formats are rejected."""
        _ = mock_adapter
        from shared.kis.websocket import SYMBOL_PATTERN

        invalid_symbols = [
            "abc",  # Too short
            "12345678901",  # Too long
            "ABC;DEF",  # Contains semicolon
            "ABC DEF",  # Contains space
            "",  # Empty
        ]

        for symbol in invalid_symbols:
            assert not SYMBOL_PATTERN.match(symbol), f"Should reject: {symbol}"


class TestDisconnect:
    """Tests for disconnect functionality."""

    def test_disconnect_sets_running_false(self, mock_adapter):
        """Test disconnect sets running to False."""
        mock_adapter._set_running(True)
        mock_adapter._set_connected(True)
        mock_adapter.ws = MagicMock()

        mock_adapter.disconnect()

        assert mock_adapter.is_running is False

    def test_disconnect_closes_websocket(self, mock_adapter):
        """Test disconnect closes WebSocket."""
        mock_ws = MagicMock()
        mock_adapter.ws = mock_ws
        mock_adapter._set_connected(True)

        mock_adapter.disconnect()

        mock_ws.close.assert_called_once()

    def test_disconnect_clears_connected(self, mock_adapter):
        """Test disconnect clears connected state."""
        mock_adapter._set_connected(True)
        mock_adapter.ws = MagicMock()

        mock_adapter.disconnect()

        assert mock_adapter.is_connected is False


class TestApprovalKeyValidation:
    """Tests for approval key request validation."""

    def test_https_validation(self):
        """Test HTTPS validation for approval key request."""
        from shared.kis.auth import KISAuthConfig
        from shared.kis.websocket import KISWebSocketAdapter

        # Create config that would return HTTP URL
        config = MagicMock(spec=KISAuthConfig)
        config.base_url = "http://insecure.example.com"  # HTTP, not HTTPS
        config.app_key = "test_key"
        config.app_secret = "test_secret"
        config.is_real = False

        with patch('shared.kis.websocket.websocket.WebSocketApp'):
            adapter = KISWebSocketAdapter.__new__(KISWebSocketAdapter)
            adapter.config = config

        with pytest.raises(ValueError, match="Approval key request requires HTTPS"):
            adapter._get_approval_key()


class TestMessageProcessing:
    """Tests for message processing."""

    def test_process_json_message(self, mock_adapter):
        """Test processing JSON subscription response."""
        json_msg = '{"header":{"tr_id":"test"},"body":{"msg_cd":"OPSP0000"}}'
        mock_adapter._process_message(json_msg)
        # Should not raise

    def test_process_pipe_separated_message(self, mock_adapter, sample_orderbook_data):
        """Test processing pipe-separated market data."""
        callback = MagicMock()
        mock_adapter._callback = callback

        # Format: encrypted|tr_id|symbol|data
        msg = f"0|H0IFASP0|101V01|{sample_orderbook_data}"
        mock_adapter._process_message(msg)

        callback.assert_called_once()

    def test_callback_exception_handled(self, mock_adapter, sample_orderbook_data):
        """Test callback exceptions are handled gracefully."""
        def bad_callback(_tick):
            raise RuntimeError("Callback error")

        mock_adapter._callback = bad_callback

        msg = f"0|H0IFASP0|101V01|{sample_orderbook_data}"
        # Should not raise
        mock_adapter._process_message(msg)

    def test_aes_key_extraction(self, mock_adapter):
        """Test AES key extraction from JSON message."""
        json_msg = '''
        {
            "header": {"tr_id": "test"},
            "body": {
                "output": {
                    "key": "0123456789abcdef",
                    "iv": "fedcba9876543210"
                }
            }
        }
        '''
        mock_adapter._process_message(json_msg)

        assert mock_adapter._aes_key == b"0123456789abcdef"
        assert mock_adapter._aes_iv == b"fedcba9876543210"

    def test_pingpong_response(self, mock_adapter):
        """Test PINGPONG message is echoed back."""
        mock_adapter._set_connected(True)
        mock_adapter.ws = MagicMock()

        json_msg = '{"header":{"tr_cd":"PINGPONG"},"body":{}}'
        mock_adapter._process_message(json_msg)

        mock_adapter.ws.send.assert_called_once()
