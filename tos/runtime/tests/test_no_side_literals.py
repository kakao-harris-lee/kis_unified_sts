"""Negative-grep pin: no bare ``"BUY"``/``"SELL"`` side literal under ``tos_runtime/src``,
except the one wire-codec module that legitimately owns the vocabulary (TOS Phase 5 W5 plan
§2 decision 8/9; lane f4).

Long/short symmetry (plan §2 decision 8) depends on side never being a runtime-authored
constant: the kernel's own venue inventory measured zero ``BUY``/``SELL`` literals and structural
side symmetry (``ActionClass.NEW_LONG``/``NEW_SHORT`` only — ``w5-survey-kernel.md`` §5), so a
runtime module that hardcodes ``"BUY"``/``"SELL"`` — or branches on ``side == "BUY"`` — is exactly
the M6 mutation the plan's mutation table names: *"런타임에 ``if side == 'BUY'`` 삽입 → 대칭/
리터럴 핀 red"*. Side is always a policy/config-carried token (``ConstructionConfig.outbound_side``,
``OrderShapeFields.side``, ``VenueShapeConstraints.allowed_sides``), never a literal this package
re-derives its own meaning from.

**One legitimate exception, allowlisted by name.** ``transport/kis_mock/adapter.py``'s
``_tr_id_for_side`` maps the wire-level side string to the KIS TR-id the mock broker's own wire
protocol requires (``self._config.tr_id_buy`` / ``self._config.tr_id_sell``) — a genuine transport
**codec vocabulary boundary** (this side IS "BUY"/"SELL" in the KIS wire protocol itself; the
alternative, threading a config-defined token past the transport into the KIS TR-id lookup table,
would just move the same two-way vocabulary mapping one layer up without removing it). Measured
directly (2026-09-12, main `c626d878`): every other file under ``tos_runtime/src`` has zero hits.

Mirrors the two-part idiom ``tos/runtime/tests/engine/test_no_direct_latch_clear.py`` and
``tos/runtime/tests/operator/test_no_write_port.py`` already establish: a receiver-shaped regex
scan with a named, justified allowlist (like the latch test's single permitted caller-file, not
like the write-port test's zero-allowlist rule), plus a synthetic-string self-test proving the
regex is not vacuous.
"""

from __future__ import annotations

import re
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[1]  # tos/runtime
_SRC = _RUNTIME_ROOT / "src"

#: The ONE module allowed to spell ``"BUY"``/``"SELL"`` literally — the KIS mock transport's wire
#: codec, which maps the outbound side to the broker's own TR-id vocabulary
#: (``tos_runtime/transport/kis_mock/adapter.py:384-389``, ``_tr_id_for_side``). No other module
#: has a structural reason to know the literal spelling of a side token — everywhere else, side
#: travels as a policy/config-carried opaque string (``ConstructionConfig.outbound_side`` et al.).
_ALLOWED_FILES = {
    _SRC / "tos_runtime" / "transport" / "kis_mock" / "adapter.py",
}

#: Matches a quoted ``BUY`` or ``SELL`` string literal — covers a bare literal
#: (``"BUY"``/``'BUY'``/``"SELL"``/``'SELL'``) and an ``==``/``!=`` comparison shape
#: (``side == "BUY"``) alike, since the comparison shape already contains the literal quote pair
#: this pattern matches; a separate comparison-only pattern would be redundant. Deliberately does
#: NOT match an unquoted mention of the word (a variable named ``buy_flag``, a comment saying
#: "the buy side") — only an actual string literal token.
_SIDE_LITERAL = re.compile(r"[\"']BUY[\"']|[\"']SELL[\"']")


def _runtime_python_files() -> list[Path]:
    return sorted(
        path for path in _SRC.rglob("*.py") if "__pycache__" not in path.parts
    )


def test_runtime_src_has_python_files_to_scan() -> None:
    files = _runtime_python_files()
    assert files, f"expected .py files under {_SRC}"


def test_the_allowlisted_file_actually_exists_and_is_scanned() -> None:
    """Anti-phantom: the one carve-out must be a real, currently-scanned file — an allowlist entry
    for a file that no longer exists (or was never in the scan set) would silently widen scope.
    """
    for path in _ALLOWED_FILES:
        assert path.exists(), f"allowlisted file does not exist: {path}"
        assert (
            path in _runtime_python_files()
        ), f"allowlisted file is not in the scan set: {path}"


def test_no_buy_sell_string_literal_outside_the_kis_mock_wire_codec() -> None:
    """(plan §2 decision 8/9; M6 mutation pin) Zero ``"BUY"``/``"SELL"`` literals anywhere under
    ``tos_runtime/src`` except the one named, justified wire-codec module."""
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
    """The allowlist entry is not a blank check: pin that the carve-out file still contains
    exactly the codec mapping it was allowlisted for, not some unrelated later addition that
    happened to land in the same file. If this file's side literals ever disappeared, the
    allowlist entry would be stale and should be removed."""
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
    """Synthetic-string self-test (anti-vacuity, mirroring the sibling latch/write-port tests):
    prove the regex actually matches every real receiver shape it claims to, and does not fire on
    an unquoted mention of the word."""
    should_match = (
        'if side == "BUY":',
        "if side == 'SELL':",
        'SIDE = "BUY"',
        "allowed_sides = frozenset({'SELL'})",
        '        "venue_session_account_facts_current": "BUY",',  # any quoted context, not only ==
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
