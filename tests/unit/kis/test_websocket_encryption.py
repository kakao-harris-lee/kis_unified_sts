"""Unit tests for WebSocket AES encryption/decryption."""
import base64
import binascii

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


def encrypt_test_data(plaintext: str, key: bytes, iv: bytes) -> str:
    """Helper to encrypt test data."""
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(plaintext.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode("utf-8")


class TestAESDecryption:
    """Tests for AES decryption functionality."""

    def test_decrypt_valid_data(self, mock_adapter):
        """Test decryption with valid key and data."""
        key = b"0123456789abcdef"  # 16 bytes for AES-128
        iv = b"fedcba9876543210"
        plaintext = "Hello, World!"

        mock_adapter._aes_key = key
        mock_adapter._aes_iv = iv

        encrypted = encrypt_test_data(plaintext, key, iv)
        result = mock_adapter._decrypt(encrypted)

        assert result == plaintext

    def test_decrypt_korean_text(self, mock_adapter):
        """Test decryption of Korean text."""
        key = b"0123456789abcdef"
        iv = b"fedcba9876543210"
        plaintext = "안녕하세요"

        mock_adapter._aes_key = key
        mock_adapter._aes_iv = iv

        encrypted = encrypt_test_data(plaintext, key, iv)
        result = mock_adapter._decrypt(encrypted)

        assert result == plaintext

    def test_decrypt_market_data_format(self, mock_adapter):
        """Test decryption of typical market data format."""
        key = b"0123456789abcdef"
        iv = b"fedcba9876543210"
        # Typical market data format
        plaintext = "101V01^093000^330.25^1^0.50^0.15^329.50^331.00^329.00"

        mock_adapter._aes_key = key
        mock_adapter._aes_iv = iv

        encrypted = encrypt_test_data(plaintext, key, iv)
        result = mock_adapter._decrypt(encrypted)

        assert result == plaintext
        assert "^" in result

    def test_decrypt_missing_key_raises(self, mock_adapter):
        """Test decryption fails without AES key."""
        mock_adapter._aes_key = None
        mock_adapter._aes_iv = None

        with pytest.raises(ValueError, match="AES key not initialized"):
            mock_adapter._decrypt("some_encrypted_data")

    def test_decrypt_missing_iv_raises(self, mock_adapter):
        """Test decryption fails without IV."""
        mock_adapter._aes_key = b"0123456789abcdef"
        mock_adapter._aes_iv = None

        with pytest.raises(ValueError, match="AES key not initialized"):
            mock_adapter._decrypt("some_encrypted_data")

    def test_decrypt_invalid_base64_raises(self, mock_adapter):
        """Test decryption fails with invalid base64."""
        mock_adapter._aes_key = b"0123456789abcdef"
        mock_adapter._aes_iv = b"fedcba9876543210"

        with pytest.raises((binascii.Error, ValueError)):
            mock_adapter._decrypt("not_valid_base64!!!")

    def test_decrypt_wrong_key_raises(self, mock_adapter):
        """Test decryption fails with wrong key."""
        correct_key = b"0123456789abcdef"
        wrong_key = b"fedcba9876543210"
        iv = b"0123456789abcdef"

        encrypted = encrypt_test_data("test data", correct_key, iv)

        mock_adapter._aes_key = wrong_key
        mock_adapter._aes_iv = iv

        # Should raise due to padding error or produce garbage
        with pytest.raises(ValueError):
            mock_adapter._decrypt(encrypted)

    def test_decrypt_empty_data(self, mock_adapter):
        """Test decryption of empty string fails appropriately."""
        mock_adapter._aes_key = b"0123456789abcdef"
        mock_adapter._aes_iv = b"fedcba9876543210"

        with pytest.raises(ValueError):
            mock_adapter._decrypt("")


class TestAESKeyStorage:
    """Tests for AES key storage and handling."""

    def test_key_set_from_json_response(self, mock_adapter):
        """Test AES key is set from JSON subscription response."""
        assert mock_adapter._aes_key is None
        assert mock_adapter._aes_iv is None

        data = {
            "header": {"tr_id": "test"},
            "body": {
                "output": {
                    "key": "0123456789abcdef",
                    "iv": "fedcba9876543210"
                }
            }
        }

        mock_adapter._handle_json_message(data)

        assert mock_adapter._aes_key == b"0123456789abcdef"
        assert mock_adapter._aes_iv == b"fedcba9876543210"

    def test_key_not_set_without_output(self, mock_adapter):
        """Test AES key not set if output missing."""
        data = {
            "header": {"tr_id": "test"},
            "body": {}
        }

        mock_adapter._handle_json_message(data)

        assert mock_adapter._aes_key is None

    def test_key_not_set_partial_output(self, mock_adapter):
        """Test AES key not set if only key provided."""
        data = {
            "header": {"tr_id": "test"},
            "body": {
                "output": {
                    "key": "0123456789abcdef"
                    # Missing 'iv'
                }
            }
        }

        mock_adapter._handle_json_message(data)

        # Should not update keys if incomplete
        assert mock_adapter._aes_key is None


class TestEncryptedMessageProcessing:
    """Tests for processing encrypted messages."""

    def test_process_encrypted_orderbook(self, mock_adapter, sample_orderbook_data):
        """Test processing encrypted orderbook message."""
        from unittest.mock import MagicMock

        key = b"0123456789abcdef"
        iv = b"fedcba9876543210"

        mock_adapter._aes_key = key
        mock_adapter._aes_iv = iv

        # Encrypt the sample data
        encrypted = encrypt_test_data(sample_orderbook_data, key, iv)

        callback = MagicMock()
        mock_adapter._callback = callback

        # Format: encrypted_flag|tr_id|symbol|data
        msg = f"1|H0IFASP0|101V01|{encrypted}"
        mock_adapter._process_message(msg)

        callback.assert_called_once()
        tick = callback.call_args[0][0]
        assert tick.symbol == "101V01"
        assert tick.bid_price_1 == 330.45

    def test_process_unencrypted_message(self, mock_adapter, sample_orderbook_data):
        """Test processing unencrypted message (flag=0)."""
        from unittest.mock import MagicMock

        callback = MagicMock()
        mock_adapter._callback = callback

        # Flag "0" means unencrypted
        msg = f"0|H0IFASP0|101V01|{sample_orderbook_data}"
        mock_adapter._process_message(msg)

        callback.assert_called_once()

    def test_encrypted_message_without_key_skipped(self, mock_adapter):
        """Test encrypted message without AES key is skipped."""
        from unittest.mock import MagicMock

        mock_adapter._aes_key = None
        mock_adapter._aes_iv = None

        callback = MagicMock()
        mock_adapter._callback = callback

        # Flag "1" means encrypted, but we have no key
        msg = "1|H0IFASP0|101V01|encrypted_garbage"
        mock_adapter._process_message(msg)

        # Callback should not be called (decryption would fail)
        callback.assert_not_called()
