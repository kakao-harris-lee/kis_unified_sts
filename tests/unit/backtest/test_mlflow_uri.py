"""Unit tests for shared/backtest/mlflow_uri.py — tracking-URI resolution.

Precedence: explicit arg > MLFLOW_TRACKING_URI env > local sqlite default.
(conftest pins MLFLOW_TRACKING_URI for the session, so these use monkeypatch.)
"""

from __future__ import annotations

from shared.backtest.mlflow_uri import DEFAULT_TRACKING_URI, resolve_tracking_uri


def test_explicit_arg_wins_over_env(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://server:5000")
    assert (
        resolve_tracking_uri("sqlite:///tmp/explicit.db") == "sqlite:///tmp/explicit.db"
    )


def test_env_used_when_no_explicit(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    assert resolve_tracking_uri() == "http://localhost:5000"


def test_defaults_to_sqlite_when_env_unset(monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    assert resolve_tracking_uri() == DEFAULT_TRACKING_URI
    assert DEFAULT_TRACKING_URI == "sqlite:///mlflow.db"


def test_empty_env_falls_through_to_default(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "")
    assert resolve_tracking_uri() == DEFAULT_TRACKING_URI
