"""Static admissibility — layer 1 pure predicate (design §3.3; ADR-DEV-001 §8 layer 1)."""

from __future__ import annotations

from enum import StrEnum

from tos.dsl._base import FrozenModel
from tos.dsl.candidate import (
    AMBIENT_SYMBOLS,
    WILDCARD_TOKENS,
    CandidateNode,
    CandidateProgram,
    iter_nodes,
)
from tos.dsl.vocabulary import (
    ADMISSIBLE_CONTEXT_SOURCES,
    ADMISSIBLE_KINDS,
    KIND_CONTEXT_REF,
)


class AdmissibilityVerdict(StrEnum):
    """The binary output of static admissibility analysis (ADR-DEV-001 §5)."""

    ADMISSIBLE = "ADMISSIBLE"
    INADMISSIBLE = "INADMISSIBLE"


class AdmissibilityAnalysis(FrozenModel):
    """The pure verdict + reasons for one candidate (design §3.3)."""

    verdict: AdmissibilityVerdict
    reasons: tuple[str, ...] = ()


def _node_findings(node: CandidateNode) -> list[str]:
    """Return every inadmissibility reason for a single node (fail-closed, design §3.3)."""
    reasons: list[str] = []

    if node.kind not in ADMISSIBLE_KINDS:
        reasons.append(f"non_vocabulary_kind:{node.kind}")

    if node.source is not None and node.source not in ADMISSIBLE_CONTEXT_SOURCES:
        reasons.append(f"ambient_source:{node.source}")

    if node.kind == KIND_CONTEXT_REF and node.source is None:
        reasons.append("context_ref_without_declared_source")

    if node.symbol is not None and (
        node.symbol in AMBIENT_SYMBOLS or node.symbol.lower() in AMBIENT_SYMBOLS
    ):
        reasons.append(f"ambient_symbol:{node.symbol}")

    if node.scope is not None and node.scope in WILDCARD_TOKENS:
        reasons.append(f"wildcard_scope:{node.scope}")

    return reasons


def analyze(program: CandidateProgram) -> AdmissibilityAnalysis:
    """Analyze a candidate program for admissibility (pure; design §3.3)."""
    reasons: list[str] = []
    if not program.nodes:
        reasons.append("empty_candidate")
    for node in iter_nodes(program):
        reasons.extend(_node_findings(node))
    if reasons:
        return AdmissibilityAnalysis(
            verdict=AdmissibilityVerdict.INADMISSIBLE, reasons=tuple(reasons)
        )
    return AdmissibilityAnalysis(verdict=AdmissibilityVerdict.ADMISSIBLE)


def admissibility_reasons(program: CandidateProgram) -> tuple[str, ...]:
    """Return the inadmissibility reasons for ``program`` (empty iff admissible)."""
    return analyze(program).reasons


def is_admissible(program: CandidateProgram) -> bool:
    """Pure default-deny admissibility predicate (design §3.3; DCE-INV-001/003/004/006)."""
    return analyze(program).verdict is AdmissibilityVerdict.ADMISSIBLE
