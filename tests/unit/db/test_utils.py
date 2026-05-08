"""shared.db.utils helpers — env-based ClickHouse client construction."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.db.utils import clickhouse_client_from_env


class TestClickhouseClientFromEnv:
    def test_uses_env_vars(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_HOST", "h")
        monkeypatch.setenv("CLICKHOUSE_PORT", "9999")
        monkeypatch.setenv("CLICKHOUSE_USER", "u")
        monkeypatch.setenv("CLICKHOUSE_PASSWORD", "p")
        with patch("clickhouse_driver.Client") as mocked:
            mocked.return_value = MagicMock()
            clickhouse_client_from_env(database="test_db")
        mocked.assert_called_once_with(
            host="h", port=9999, user="u", password="p", database="test_db"
        )

    def test_defaults_password_to_empty(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_HOST", "h")
        monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
        with patch("clickhouse_driver.Client") as mocked:
            mocked.return_value = MagicMock()
            clickhouse_client_from_env(database="test_db")
        assert mocked.call_args.kwargs["password"] == ""

    def test_database_is_required(self):
        with pytest.raises(ValueError, match="database"):
            clickhouse_client_from_env(database="")

    def test_http_port_8123_is_redirected_to_native_9000(self, monkeypatch):
        """When CLICKHOUSE_PORT is 8123 (HTTP) the native client must use 9000.

        Regression: this repo's .env historically sets CLICKHOUSE_PORT=8123.
        Naively passing 8123 to clickhouse_driver.Client crashes with
        UnexpectedPacketFromServerError because 8123 is the HTTP port, not
        native protocol (9000).  Mirrors shared/db/config.py::from_env logic.
        """
        monkeypatch.delenv("CLICKHOUSE_NATIVE_PORT", raising=False)
        monkeypatch.setenv("CLICKHOUSE_PORT", "8123")
        with patch("clickhouse_driver.Client") as mocked:
            mocked.return_value = MagicMock()
            clickhouse_client_from_env(database="test_db")
        assert mocked.call_args.kwargs["port"] == 9000

    def test_explicit_native_port_overrides_http_port(self, monkeypatch):
        """CLICKHOUSE_NATIVE_PORT always wins, even if CLICKHOUSE_PORT=8123."""
        monkeypatch.setenv("CLICKHOUSE_NATIVE_PORT", "9100")
        monkeypatch.setenv("CLICKHOUSE_PORT", "8123")
        with patch("clickhouse_driver.Client") as mocked:
            mocked.return_value = MagicMock()
            clickhouse_client_from_env(database="test_db")
        assert mocked.call_args.kwargs["port"] == 9100

    def test_non_8123_port_passes_through_unchanged(self, monkeypatch):
        """Custom non-8123 ports are not silently rewritten."""
        monkeypatch.delenv("CLICKHOUSE_NATIVE_PORT", raising=False)
        monkeypatch.setenv("CLICKHOUSE_PORT", "9100")
        with patch("clickhouse_driver.Client") as mocked:
            mocked.return_value = MagicMock()
            clickhouse_client_from_env(database="test_db")
        assert mocked.call_args.kwargs["port"] == 9100
