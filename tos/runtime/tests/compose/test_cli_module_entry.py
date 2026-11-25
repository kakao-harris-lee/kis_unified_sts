"""``python -m tos_runtime.compose.cli`` runs :func:`~tos_runtime.compose.cli.main` (#961)."""

from __future__ import annotations

import runpy
import sys

import pytest

_MODULE = "tos_runtime.compose.cli"


def _run_as_main(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int | str | None:
    monkeypatch.delitem(sys.modules, _MODULE, raising=False)
    monkeypatch.setattr(sys, "argv", [_MODULE, *argv])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module(_MODULE, run_name="__main__", alter_sys=True)
    return excinfo.value.code


def test_help_through_dash_m_prints_usage_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run_as_main(monkeypatch, "--help")
    assert code == 0
    assert "usage:" in capsys.readouterr().out


def test_an_unknown_subcommand_through_dash_m_exits_non_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run_as_main(monkeypatch, "no-such-subcommand")
    assert code == 2
    assert "error:" in capsys.readouterr().err
