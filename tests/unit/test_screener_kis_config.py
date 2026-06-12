"""Screener builds its KIS config from the stock-specific market flag.

Regression: run_screener read the generic KIS_IS_REAL (="false" in the paper
stack) instead of KIS_STOCK_MARKET (="real"), so KISRankingClient raised
"ranking APIs are not supported in mock investment" → 0 candidates → no
trade_targets → idle stock pipeline (daily-verification FAIL trade_targets_missing).
"""

from __future__ import annotations

from services.screener import _stock_kis_config


def test_uses_stock_market_flag_not_generic_kis_is_real(monkeypatch):
    monkeypatch.setenv("KIS_STOCK_MARKET", "real")
    monkeypatch.setenv("KIS_STOCK_APP_KEY", "stock-key")
    monkeypatch.setenv("KIS_STOCK_APP_SECRET", "stock-secret")
    # Generic flags say mock — they MUST be ignored for the stock screener.
    monkeypatch.setenv("KIS_IS_REAL", "false")
    monkeypatch.setenv("KIS_MARKET", "mock")
    monkeypatch.setenv("KIS_APP_KEY", "generic-key")

    cfg = _stock_kis_config()

    assert cfg.is_real is True  # ranking APIs require real investment
    assert cfg.app_key == "stock-key"
    assert cfg.app_secret == "stock-secret"


def test_mock_when_stock_market_is_mock(monkeypatch):
    monkeypatch.setenv("KIS_STOCK_MARKET", "mock")
    monkeypatch.setenv("KIS_STOCK_APP_KEY", "k")
    monkeypatch.setenv("KIS_STOCK_APP_SECRET", "s")

    cfg = _stock_kis_config()

    assert cfg.is_real is False


def test_defaults_to_mock_when_unset(monkeypatch):
    monkeypatch.delenv("KIS_STOCK_MARKET", raising=False)
    monkeypatch.setenv("KIS_STOCK_APP_KEY", "k")
    monkeypatch.setenv("KIS_STOCK_APP_SECRET", "s")

    cfg = _stock_kis_config()

    assert cfg.is_real is False  # safe default: mock unless explicitly real
