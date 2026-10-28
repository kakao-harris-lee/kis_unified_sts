"""``python -m tos_runtime.compose.cli`` runs :func:`~tos_runtime.compose.cli.main` (#961).

Before the ``__main__`` guard the module only defined ``main``: ``-m`` imported it, did nothing
and exited 0 — so an operator following a ``-m`` instruction for ``write-standing-approval`` would
have seen success with no approval file written.

Run in-process through :func:`runpy.run_module` with ``run_name="__main__"`` — what ``-m`` does —
because ``subprocess`` is forbidden under ``tos/`` (firewall TOS-FW-B). The module is evicted from
``sys.modules`` for the call so ``runpy`` executes a fresh copy, as a real ``-m`` start would.
"""

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
    # An unknown first token is not a subcommand, so it falls to the implicit ``run`` (module
    # docstring) and argparse refuses that: exit 2 with an ``error:`` line, never a silent 0.
    code = _run_as_main(monkeypatch, "no-such-subcommand")
    assert code == 2
    assert "error:" in capsys.readouterr().err
