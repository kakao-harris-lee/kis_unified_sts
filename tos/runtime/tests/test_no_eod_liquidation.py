"""Negative-grep pin: no end-of-day liquidation receiver shape under ``tos_runtime/src`` (TOS"""

from __future__ import annotations

import re
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[1]
_SRC = _RUNTIME_ROOT / "src"

_EOD_LIQUIDATION_SHAPE = re.compile(
    r"\bEOD\b|liquidat|end_of_day|close_all\(|flatten_positions?\("
)


def _runtime_python_files() -> list[Path]:
    return sorted(
        path for path in _SRC.rglob("*.py") if "__pycache__" not in path.parts
    )


def test_runtime_src_has_python_files_to_scan() -> None:
    files = _runtime_python_files()
    assert files, f"expected .py files under {_SRC}"


def test_no_eod_liquidation_shape_anywhere_under_tos_runtime_src() -> None:
    """Phase 5 §5 end condition 5, quoted verbatim in the plan: "런타임 EOD/liquidat/flatten 실"""
    offenders: list[str] = []
    for path in _runtime_python_files():
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _EOD_LIQUIDATION_SHAPE.search(line):
                offenders.append(
                    f"{path.relative_to(_RUNTIME_ROOT)}:{lineno}: {line.strip()}"
                )
    assert offenders == [], (
        "found an EOD/liquidation receiver shape under tos_runtime/src — stock/futures exits "
        "must stay signal-driven, never a blanket EOD liquidation (root CLAUDE.md Non-Negotiable "
        "Rules; Phase 5 §5 end condition 5):\n" + "\n".join(offenders)
    )


def test_the_pattern_catches_every_real_offending_shape_and_spares_the_one_real_prose_mention() -> (
    None
):
    """Synthetic-string self-test (anti-vacuity, mirroring the sibling latch/write-port tests):"""
    should_match = (
        "def liquidate_all(account) -> None:",
        "self._liquidator.run()",
        "run_end_of_day_liquidation(account)",
        "if phase is EOD:",
        "    EOD = True",
        "def close_all(account) -> None:",
        "flatten_positions(account, instrument)",
        "flatten_position(account, instrument)",
    )
    for line in should_match:
        assert _EOD_LIQUIDATION_SHAPE.search(
            line
        ), f"expected the regex to match: {line!r}"

    should_not_match = (
        "# never flattened, remapped, or otherwise widened past what",
        "def build_environment(config):  # not an EODevent, just a substring lookalike",
        "no_decision_union(...)",
        "if is_EOD:",
    )
    for line in should_not_match:
        assert not _EOD_LIQUIDATION_SHAPE.search(
            line
        ), f"expected the regex NOT to match: {line!r}"
