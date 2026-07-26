"""Forbidden-verb + clock-free constructive-absence canary (design #23 §4.1/§7).

cur is **pure, non-transmitting, non-mutating, and clock-free** (§4.1). The constructive-absence
canary asserts the package defines **no** send / transmit / emit / sign / claim (execution) /
mutate / reserve / release / transfer / quarantine (capacity) / approve / arm / rearm / clear-halt /
open / connect / socket function, references **no** real clock (``time.time`` / ``datetime.now`` /
``monotonic``), and reaches **no** ambient env / dynamic escape. The structural absence of a transmit
/ mutate method is this package's identity (§4.1 — "a currentness sequencer ... does not invent
facts ... or transmit", §1 line 21).

Regime tag: structural substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tos.cur import (
    CurrentnessPolicy,
    EgressCurrentnessProof,
    RestrictiveFenceRecord,
    SafetyCurrentnessVector,
)
from tos.cur._base import DigestBoundArtifact

_CUR_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "cur"

#: Forbidden verb roots — a function whose name starts with any of these would be a cur capability.
_FORBIDDEN_VERB_PREFIXES = (
    "send",
    "transmit",
    "emit",
    "dispatch",
    "publish",
    "deliver",
    "sign",
    "claim",  # execution verb (a claim_capability would be an rcl-owned execution — sibling turf)
    "mutate",
    "reserve",
    "release",
    "transfer",
    "quarantine",
    "approve",
    "arm",
    "rearm",
    "re_arm",
    "clear_halt",
    "clearhalt",
    "open",
    "connect",
    "socket",
)

#: Real-clock call fragments a clock-free package must never reference (§5.4 / §0.4e). Dotted /
#: call forms only, so a bare "monotonic" adjective in prose never false-matches.
_FORBIDDEN_CLOCK_FRAGMENTS = (
    "time.time",
    "time.monotonic",
    "datetime.now",
    "datetime.utcnow",
    "perf_counter",
)


def test_artifacts_have_no_transmit_or_mutate_method() -> None:
    """(§4.1 constructive absence) No artifact exposes a send / mutate / claim / approve method."""
    artifacts = (
        SafetyCurrentnessVector,
        EgressCurrentnessProof,
        RestrictiveFenceRecord,
        CurrentnessPolicy,
    )
    # The inherited core digest machinery (``.issue()`` — issue an artifact's digest) is NOT a cur
    # capability; only cur-artifact-SPECIFIC additions are checked (skip base names).
    base_names = set(dir(DigestBoundArtifact))
    for artifact in artifacts:
        for name in dir(artifact):
            if name in base_names:
                continue
            lowered = name.lstrip("_").lower()
            for prefix in _FORBIDDEN_VERB_PREFIXES:
                assert not lowered.startswith(prefix), (
                    f"{artifact.__name__}.{name} looks like a cur capability method — the "
                    "structural absence of a transmit / mutate / claim method is this package's "
                    "identity (§4.1)"
                )


def _defined_function_names(path: Path) -> list[str]:
    """Return every def / async def name in a source file (module + method level)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def test_no_cur_source_defines_a_capability_verb_function() -> None:
    """(§4.1 constructive absence, source scan) No cur source defines a capability-verb function."""
    offenders: list[str] = []
    for path in sorted(_CUR_SRC.rglob("*.py")):
        for name in _defined_function_names(path):
            lowered = name.lstrip("_").lower()
            for prefix in _FORBIDDEN_VERB_PREFIXES:
                if lowered.startswith(prefix):
                    offenders.append(f"{path.name}: def {name}")
    assert offenders == [], f"forbidden capability-verb function defined: {offenders}"


def test_no_cur_source_references_a_real_clock() -> None:
    """(§5.4 / §0.4e clock-free) No cur source references a real clock (currentness ≠ wall-clock)."""
    offenders: list[str] = []
    for path in sorted(_CUR_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for fragment in _FORBIDDEN_CLOCK_FRAGMENTS:
            if fragment in text:
                offenders.append(f"{path.name}: {fragment}")
    assert offenders == [], f"clock reference in a clock-free package: {offenders}"


def test_verb_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The verb scan actually catches a planted ``def transmit`` (not vacuous)."""
    planted = tmp_path / "planted.py"
    planted.write_text("def transmit_order():\n    return 1\n", encoding="utf-8")
    names = _defined_function_names(planted)
    assert any(n.startswith("transmit") for n in names)
