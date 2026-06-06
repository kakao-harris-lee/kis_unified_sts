"""M5e: orchestrator stock decommission guard in `sts trade start`."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import cli.main as m


def test_enabled_defaults_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_ORCHESTRATOR_ENABLED", raising=False)
    assert m._stock_orchestrator_enabled() is True


def test_enabled_false_and_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_ORCHESTRATOR_ENABLED", "false")
    assert m._stock_orchestrator_enabled() is False
    monkeypatch.setenv("STOCK_ORCHESTRATOR_ENABLED", " FALSE ")
    assert m._stock_orchestrator_enabled() is False
    monkeypatch.setenv("STOCK_ORCHESTRATOR_ENABLED", "true")
    assert m._stock_orchestrator_enabled() is True


def test_blocked_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_ORCHESTRATOR_ENABLED", "false")
    assert m._stock_orchestrator_blocked("stock") is True
    assert m._stock_orchestrator_blocked("futures") is False  # only stock is blocked
    monkeypatch.delenv("STOCK_ORCHESTRATOR_ENABLED", raising=False)
    assert m._stock_orchestrator_blocked("stock") is False  # default-true => allowed


def test_cli_blocks_stock_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_ORCHESTRATOR_ENABLED", "false")
    result = CliRunner().invoke(
        m.cli, ["trade", "start", "--asset", "stock", "--paper"]
    )
    assert result.exit_code == 1
    assert "decoupled M4 pipeline" in result.output
    assert "STOCK_ORCHESTRATOR_ENABLED=true" in result.output  # rollback hint
