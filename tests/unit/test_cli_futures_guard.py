"""F-8: orchestrator futures decommission guard in `sts trade start`."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import cli.main as m


def test_enabled_defaults_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FUTURES_ORCHESTRATOR_ENABLED", raising=False)
    assert m._futures_orchestrator_enabled() is True


def test_enabled_false_and_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "false")
    assert m._futures_orchestrator_enabled() is False
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", " FALSE ")
    assert m._futures_orchestrator_enabled() is False
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "true")
    assert m._futures_orchestrator_enabled() is True


def test_enabled_truthy_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "1")
    assert m._futures_orchestrator_enabled() is True
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "YES")
    assert m._futures_orchestrator_enabled() is True
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "0")
    assert m._futures_orchestrator_enabled() is False
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "no")
    assert m._futures_orchestrator_enabled() is False


def test_blocked_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "false")
    assert m._futures_orchestrator_blocked("futures") is True
    assert m._futures_orchestrator_blocked("stock") is False  # only futures is blocked
    monkeypatch.delenv("FUTURES_ORCHESTRATOR_ENABLED", raising=False)
    assert (
        m._futures_orchestrator_blocked("futures") is False
    )  # default-true => allowed


def test_cli_blocks_futures_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "false")
    result = CliRunner().invoke(
        m.cli, ["trade", "start", "--asset", "futures", "--paper"]
    )
    assert result.exit_code == 1
    assert "decoupled chain" in result.output
    assert "FUTURES_ORCHESTRATOR_ENABLED=true" in result.output  # rollback hint


def test_cli_allows_futures_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default-true: the guard does NOT block futures (it proceeds past the gate).

    We don't run a full session — just assert the guard's block message is absent.
    """
    monkeypatch.delenv("FUTURES_ORCHESTRATOR_ENABLED", raising=False)
    # Invoke with an invalid strategy so it exits quickly AFTER the guard; the
    # key assertion is that the FUTURES guard message never appears.
    result = CliRunner().invoke(
        m.cli,
        ["trade", "start", "--asset", "futures", "--paper", "--strategy", "__nope__"],
    )
    assert "the monolithic orchestrator no longer runs futures" not in result.output
