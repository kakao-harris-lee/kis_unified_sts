"""shared.db.utils helpers — env-based ClickHouse client construction."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

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
