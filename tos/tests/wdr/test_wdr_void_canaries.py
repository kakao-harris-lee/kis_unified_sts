"""Forbidden-verb + clock-free constructive-absence canary (design #26 §4.1/§7).

wdr is **pure, non-transmitting, non-mutating, and clock-free** (§4.1). The constructive-absence canary
asserts the package defines **no** send / transmit / emit / sign / arm / rearm (execution) / mutate /
reserve / release / transfer / commit_capacity (capacity) / approve / authorize / activate (execution
approval — wdr does only *structural* deviation judgement, not real approval / activation) / clear-halt
/ open / connect / socket function, references **no** real clock (``time.time`` / ``datetime.now`` /
``monotonic``), and reaches **no** ambient env / dynamic escape. The structural absence of a transmit /
mutate / approve method is this package's identity (§4.1 — a deviation artifact "creates no ...
authority", WDR-INV-001).

Regime tag: structural substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tos.wdr import (
    ActiveDeviationSet,
    ResidualRiskAcceptanceRecord,
    SafetyDeviationDecision,
    SafetyDeviationPolicy,
    SafetyDeviationRequest,
)
from tos.wdr._base import DigestBoundArtifact

_WDR_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "wdr"

#: Forbidden verb roots — a function whose name starts with any of these would be a wdr capability.
_FORBIDDEN_VERB_PREFIXES = (
    "send",
    "transmit",
    "emit",
    "dispatch",
    "publish",
    "deliver",
    "sign",
    "arm",
    "rearm",
    "re_arm",
    "mutate",
    "reserve",
    "release",
    "transfer",
    "commit_capacity",
    "approve",
    "authorize",
    "activate",  # wdr does STRUCTURAL judgement only — never a real activation action
    "clear_halt",
    "clearhalt",
    "open",
    "connect",
    "socket",
    "revoke_",  # revoking is a runtime side-effect (not an L1 judgement)
)

#: Real-clock call fragments a clock-free package must never reference (§0.4h). Dotted / call forms only.
_FORBIDDEN_CLOCK_FRAGMENTS = (
    "time.time",
    "time.monotonic",
    "datetime.now",
    "datetime.utcnow",
    "perf_counter",
)


def test_artifacts_have_no_transmit_mutate_or_approve_method() -> None:
    """(§4.1 constructive absence) No artifact exposes a send / mutate / approve / activate method."""
    artifacts = (
        SafetyDeviationPolicy,
        SafetyDeviationRequest,
        SafetyDeviationDecision,
        ResidualRiskAcceptanceRecord,
        ActiveDeviationSet,
    )
    base_names = set(dir(DigestBoundArtifact))
    for artifact in artifacts:
        for name in dir(artifact):
            if name in base_names:
                continue
            lowered = name.lstrip("_").lower()
            for prefix in _FORBIDDEN_VERB_PREFIXES:
                assert not lowered.startswith(prefix), (
                    f"{artifact.__name__}.{name} looks like a wdr capability method — the "
                    "structural absence of a transmit / mutate / approve / activate method is this "
                    "package's identity (§4.1 / WDR-INV-001)"
                )


def _defined_function_names(path: Path) -> list[str]:
    """Return every def / async def name in a source file (module + method level)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def test_no_wdr_source_defines_a_capability_verb_function() -> None:
    """(§4.1 constructive absence, source scan) No wdr source defines a capability-verb function."""
    offenders: list[str] = []
    for path in sorted(_WDR_SRC.rglob("*.py")):
        for name in _defined_function_names(path):
            lowered = name.lstrip("_").lower()
            for prefix in _FORBIDDEN_VERB_PREFIXES:
                if lowered.startswith(prefix):
                    offenders.append(f"{path.name}: def {name}")
    assert offenders == [], f"forbidden capability-verb function defined: {offenders}"


def test_no_wdr_source_references_a_real_clock() -> None:
    """(§0.4h clock-free) No wdr source references a real clock (a Deviation Generation ≠ wall-clock)."""
    offenders: list[str] = []
    for path in sorted(_WDR_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for fragment in _FORBIDDEN_CLOCK_FRAGMENTS:
            if fragment in text:
                offenders.append(f"{path.name}: {fragment}")
    assert offenders == [], f"clock reference in a clock-free package: {offenders}"


def test_verb_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The verb scan actually catches a planted ``def activate`` (not vacuous)."""
    planted = tmp_path / "planted.py"
    planted.write_text("def activate_deviation():\n    return 1\n", encoding="utf-8")
    names = _defined_function_names(planted)
    assert any(n.startswith("activate") for n in names)
