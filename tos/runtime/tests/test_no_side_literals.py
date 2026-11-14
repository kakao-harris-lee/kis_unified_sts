"""Negative-grep pin: no bare ``"BUY"``/``"SELL"`` side literal under ``tos_runtime/src``,"""

from __future__ import annotations

import re
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[1]
_SRC = _RUNTIME_ROOT / "src"

_ALLOWED_FILES = {
    _SRC / "tos_runtime" / "transport" / "kis_mock" / "adapter.py",
}

_SIDE_LITERAL = re.compile(r"[\"']BUY[\"']|[\"']SELL[\"']")


def _runtime_python_files() -> list[Path]:
    return sorted(
        path for path in _SRC.rglob("*.py") if "__pycache__" not in path.parts
    )


def test_runtime_src_has_python_files_to_scan() -> None:
    files = _runtime_python_files()
    assert files, f"expected .py files under {_SRC}"


def test_the_allowlisted_file_actually_exists_and_is_scanned() -> None:
    """Anti-phantom: the one carve-out must be a real, currently-scanned file — an allowlist entry"""
    for path in _ALLOWED_FILES:
        assert path.exists(), f"allowlisted file does not exist: {path}"
        assert (
            path in _runtime_python_files()
        ), f"allowlisted file is not in the scan set: {path}"


def test_no_buy_sell_string_literal_outside_the_kis_mock_wire_codec() -> None:
    """(plan §2 decision 8/9; M6 mutation pin) Zero ``"BUY"``/``"SELL"`` literals anywhere under"""
    offenders: list[str] = []
    for path in _runtime_python_files():
        if path in _ALLOWED_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _SIDE_LITERAL.search(line):
                offenders.append(
                    f"{path.relative_to(_RUNTIME_ROOT)}:{lineno}: {line.strip()}"
                )
    assert offenders == [], (
        'found a "BUY"/"SELL" string literal outside the allowlisted KIS mock wire codec — side '
        "must stay a policy/config-carried token everywhere else, never a runtime-authored "
        "constant (long/short symmetry, plan §2 decision 8):\n" + "\n".join(offenders)
    )


def test_the_allowlisted_file_itself_still_contains_the_justified_literals() -> None:
    """The allowlist entry is not a blank check: pin that the carve-out file still contains"""
    (adapter_path,) = _ALLOWED_FILES
    text = adapter_path.read_text(encoding="utf-8")
    assert _SIDE_LITERAL.search(text), (
        f"{adapter_path} was allowlisted for its BUY/SELL wire-codec mapping, but no such "
        "literal was found — the allowlist entry is stale and should be removed"
    )
    assert "tr_id_buy" in text and "tr_id_sell" in text, (
        f"{adapter_path}'s side literals were expected to feed a TR-id codec lookup "
        "(tr_id_buy/tr_id_sell) — if that shape changed, re-justify or remove the allowlist entry"
    )


def test_the_pattern_catches_every_real_offending_shape() -> None:
    """Synthetic-string self-test (anti-vacuity, mirroring the sibling latch/write-port tests):"""
    should_match = (
        'if side == "BUY":',
        "if side == 'SELL':",
        'SIDE = "BUY"',
        "allowed_sides = frozenset({'SELL'})",
        '        "venue_session_account_facts_current": "BUY",',
    )
    for line in should_match:
        assert _SIDE_LITERAL.search(line), f"expected the regex to match: {line!r}"

    should_not_match = (
        "# the buy side of the book",
        "buy_flag = True",
        "def sell_all(account) -> None:",
        "side: str  # BUY or SELL, but as an unquoted docstring word only",
    )
    for line in should_not_match:
        assert not _SIDE_LITERAL.search(
            line
        ), f"expected the regex NOT to match: {line!r}"
