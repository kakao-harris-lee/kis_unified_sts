"""Canary for the shared truthy-sentinel AST scan every package seal runs on."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._truthiness_scan import bare_truthiness_offenders

_SUSPICIOUS = frozenset({"result", "state", "verdict", "admission"})


@pytest.mark.parametrize("name", sorted(_SUSPICIOUS))
def test_bare_truthiness_scan_detects_a_planted_offender(
    tmp_path: Path, name: str
) -> None:
    """(canary) The AST scan actually catches a planted ``if <name>:`` (not vacuous)."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        f"def f({name}):\n    if {name}:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    assert bare_truthiness_offenders(planted, _SUSPICIOUS) != []


@pytest.mark.parametrize("name", sorted(_SUSPICIOUS))
def test_a_negated_bare_truthiness_use_is_caught_too(tmp_path: Path, name: str) -> None:
    """(canary) ``if not <name>:`` is the same trap and the scan unwraps the ``not``."""
    planted = tmp_path / "planted_not.py"
    planted.write_text(
        f"def f({name}):\n    if not {name}:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    assert bare_truthiness_offenders(planted, _SUSPICIOUS) != []


def test_an_explicit_identity_gate_is_not_an_offender(tmp_path: Path) -> None:
    """(canary polarity) The mandated ``is`` gate must not be reported — the scan is not vacuous."""
    clean = tmp_path / "clean.py"
    clean.write_text(
        "def f(result):\n    if result is None:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    assert bare_truthiness_offenders(clean, _SUSPICIOUS) == []
