"""Stock streaming key conventions."""

from __future__ import annotations

from shared.streaming.stock_keys import (
    DASHBOARD_STOCK_POSITIONS_KEY,
    DEFAULT_STOCK_DAEMON_POSITIONS_KEY,
    stock_daemon_positions_key,
)


def test_stock_daemon_positions_default_is_not_dashboard_key(monkeypatch) -> None:
    monkeypatch.delenv("STOCK_POSITIONS_KEY", raising=False)

    assert stock_daemon_positions_key() == DEFAULT_STOCK_DAEMON_POSITIONS_KEY
    assert stock_daemon_positions_key() != DASHBOARD_STOCK_POSITIONS_KEY


def test_stock_daemon_positions_env_override(monkeypatch) -> None:
    monkeypatch.setenv("STOCK_POSITIONS_KEY", "custom:stock:positions")

    assert stock_daemon_positions_key() == "custom:stock:positions"
