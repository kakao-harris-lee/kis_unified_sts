"""Negative-grep pin: no end-of-day liquidation receiver shape under ``tos_runtime/src`` (TOS
Phase 5 W5 plan §2 decision 9; end condition 5; lane f4).

Repo-wide non-negotiable rule (root ``CLAUDE.md``, "Non-Negotiable Rules"): **"Stock swing exits
are signal-driven. Do not add blanket EOD liquidation."** — a rule the tos runtime inherits
unconditionally, regardless of asset class, because this package holds no per-asset branch at all
(the config-driven, DRY-over-per-asset-code discipline the same file states). Phase 5 W5's own
survey (``w5-survey-runtime.md`` §"종료 조건 5") measured zero real hits under
``tos_runtime/src`` today — this test makes that measurement mechanical rather than a one-time
survey finding that could silently regress.

Mirrors the two-part idiom ``tos/runtime/tests/engine/test_no_direct_latch_clear.py`` and
``tos/runtime/tests/operator/test_no_write_port.py`` already establish for this suite: (1) a
receiver-shaped regex swept over every real source file, with **no allowlist** (unlike the latch
test's single permitted caller-file carve-out — there is no legitimate reason for ANY runtime
module to hold an EOD-liquidation shape), and (2) a synthetic-string self-test proving the regex
actually catches the shapes it claims to and does not fire on the one real prose mention already
in this tree (``strategy/bindings.py:37``'s docstring word "flattened").
"""

from __future__ import annotations

import re
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[1]  # tos/runtime
_SRC = _RUNTIME_ROOT / "src"

#: Receiver-shaped EOD/liquidation vocabulary (plan §2 decision 9's exact regex). ``\bEOD\b`` is a
#: whole-word match (never fires inside a longer identifier); ``liquidat`` and ``end_of_day`` are
#: substrings, deliberately broad (catch ``liquidate``/``liquidation``/``Liquidator`` etc. and any
#: ``end_of_day``-named symbol); ``close_all\(`` / ``flatten_positions?\(`` are call-shaped —
#: anchored on the opening paren so a prose mention of the same word with no call never matches.
#: The ``flatten_positions?\(`` shape is deliberately narrower than a bare ``flatten`` substring
#: precisely so ``strategy/bindings.py:37``'s docstring word "flattened" does not need an
#: allowlist entry to stay clean — the regex itself is tuned to miss it (plan §2 decision 9).
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
    """Phase 5 §5 end condition 5, quoted verbatim in the plan: "런타임 EOD/liquidat/flatten 실
    hit 0" — a zero-tolerance sweep, no allowlist. Stock swing exits stay signal-driven; there is
    no blanket EOD liquidation path anywhere in this runtime (root ``CLAUDE.md`` Non-Negotiable
    Rules)."""
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
    """Synthetic-string self-test (anti-vacuity, mirroring the sibling latch/write-port tests):
    prove the regex actually matches the shapes decision 9 names, and does NOT match the one real
    non-offending mention already in this tree — ``strategy/bindings.py:37``'s docstring prose
    "never flattened, remapped, or otherwise widened", which uses the past-participle word
    "flattened", not a ``flatten_positions(``/``flatten(`` call."""
    should_match = (
        "def liquidate_all(account) -> None:",
        "self._liquidator.run()",
        "run_end_of_day_liquidation(account)",
        "if phase is EOD:",
        "    EOD = True",
        "def close_all(account) -> None:",
        "flatten_positions(account, instrument)",
        "flatten_position(account, instrument)",  # the optional-plural branch
    )
    for line in should_match:
        assert _EOD_LIQUIDATION_SHAPE.search(
            line
        ), f"expected the regex to match: {line!r}"

    should_not_match = (
        "# never flattened, remapped, or otherwise widened past what",
        "def build_environment(config):  # not an EODevent, just a substring lookalike",
        "no_decision_union(...)",  # contains neither EOD nor liquidat as whole tokens
        # \bEOD\b's word-boundary blind spot (the same one MEDIUM-7 found in the sibling
        # latch-clear test's prior \binbox\. pattern): `_` is a word character, so the boundary
        # does not fire between it and a following/preceding EOD. This is the plan's literal
        # decision-9 regex, used as specified — recorded here as a KNOWN gap, not silently hidden.
        "if is_EOD:",
    )
    for line in should_not_match:
        assert not _EOD_LIQUIDATION_SHAPE.search(
            line
        ), f"expected the regex NOT to match: {line!r}"


def test_the_one_real_prose_mention_in_this_tree_is_spared_by_name() -> None:
    """Positive confirmation, not just a synthetic string: read the actual file/line the survey
    named (``strategy/bindings.py:37``) and assert the regex does not fire on it — if a future
    edit changed that docstring's wording to something call-shaped, this test (not just the
    synthetic self-test above) would catch it."""
    bindings_path = _SRC / "tos_runtime" / "strategy" / "bindings.py"
    assert bindings_path.exists(), f"expected {bindings_path} to exist"
    lines = bindings_path.read_text(encoding="utf-8").splitlines()
    flattened_lines = [line for line in lines if "flattened" in line]
    assert flattened_lines, (
        "expected to find the known 'flattened' docstring prose in bindings.py — if this no "
        "longer exists the test should be updated, not silently left checking nothing"
    )
    for line in flattened_lines:
        assert not _EOD_LIQUIDATION_SHAPE.search(
            line
        ), f"the EOD/liquidation regex now matches a known-benign prose line: {line!r}"
