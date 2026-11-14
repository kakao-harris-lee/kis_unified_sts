"""Grep-pin canary: nothing under ``tos_runtime/src`` outside the two sanctioned doors —"""

from __future__ import annotations

import re
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]
_SRC = _RUNTIME_ROOT / "src"

_ALLOWED_FILES = {
    _SRC / "tos_runtime" / "compose" / "_types.py",
    _SRC / "tos_runtime" / "compose" / "_cli_ops.py",
}

_DIRECT_CALL = re.compile(r"[\w.]*inbox\.clear_new_risk_halt\(")


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def test_no_direct_inbox_latch_clear_calls_outside_the_compose_wrapper() -> None:
    offenders: list[str] = []
    for path in _python_files(_SRC):
        if path in _ALLOWED_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _DIRECT_CALL.search(line):
                offenders.append(
                    f"{path.relative_to(_RUNTIME_ROOT)}:{lineno}: {line.strip()}"
                )
    assert offenders == [], (
        "direct SqliteEventInbox.clear_new_risk_halt( call(s) found outside the two "
        "sanctioned doors (tos_runtime/compose/_types.py, tos_runtime/compose/_cli_ops.py) "
        "— this bypasses the evidence-writing operator door(s) (re-review finding RR2):\n"
        + "\n".join(offenders)
    )


def test_the_pattern_itself_catches_every_real_receiver_shape() -> None:
    """MEDIUM-7 mutation pin: prove the regex, not just the file scan, actually catches"""
    caught = (
        "self._inbox.clear_new_risk_halt(",
        "self.inbox.clear_new_risk_halt(",
        "_inbox.clear_new_risk_halt(",
        "runtime.inbox.clear_new_risk_halt(",
    )
    for scratch in caught:
        assert _DIRECT_CALL.search(
            scratch
        ), f"_DIRECT_CALL must match the real receiver shape {scratch!r}"

    not_caught = (
        "ComposedRuntime.clear_new_risk_halt(latched_evidence_seq=1, approvals_dir=path)",
        "    def clear_new_risk_halt(",
    )
    for scratch in not_caught:
        assert not _DIRECT_CALL.search(
            scratch
        ), f"_DIRECT_CALL must NOT match the non-offending text {scratch!r}"
