"""Static admissibility — layer 1 pure predicate (design §3.3; ADR-DEV-001 §8 layer 1).

This is the only enforcement layer Phase 1 realizes; capability-restricted
evaluation (layer 2) and the isolation boundary (layer 3) are deferred (design
§0/§3.5). It is a **pure function** over the candidate-AST — it never imports,
compiles, executes, or evaluates a candidate (design §3.2 firewall-critical).
Source-form input (analyzing a candidate delivered as Python source) is a
family/config concern the design defers to Phase-0 (design §3.2), so this Phase
ships no source scanner.

The predicate realizes four DCE invariants as static facets (design §3.3):

* **DCE-INV-001 (default-deny membership)** — a node whose ``kind`` is not in
  :data:`~tos.dsl.vocabulary.ADMISSIBLE_KINDS` is *absent from the surface* and
  inadmissible. This is an **allowlist**, not a blocklist: a novel/unknown kind is
  inadmissible because it is not admitted, not because it is enumerated forbidden.
* **DCE-INV-003 (no ambient authority — static naming)** — a ``context_ref`` that
  names a non-``{capsule, config}`` source, or any node naming an
  :data:`~tos.dsl.candidate.AMBIENT_SYMBOLS` symbol, is an ambient reach and is
  inadmissible (RFC-008 §11 item 12).
* **DCE-INV-004 (escape-closure)** — import / dynamic-eval / reflection / FFI /
  extension nodes are not in the vocabulary, so default-deny membership rejects
  them (RFC-008 §11 item 17). Escape-closure is realized by node-membership on the
  closed candidate algebra, not by scanning candidate source text.
* **DCE-INV-006 (inadmissible is conservative)** — anything not *provably* inside
  the surface is inadmissible; an empty candidate, an unresolved kind, or a
  ``context_ref`` with no positively-declared source fails **closed**, never
  optimistically admitted.

DCE-INV-002 (layered) and DCE-INV-005 (mechanism verification) are **not** realized
here (design §0/§1): this checker is itself an Enforcement-Mechanism component and
so cannot self-certify (DCE-INV-005) — it is provisional and non-authorizing, and
property tests over it are *authoring* evidence, not acceptance.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only. No
``importlib``/``__import__``/``exec``/``eval``/``compile`` (design §3.2/§3.3-①d).
"""

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
    """The pure verdict + reasons for one candidate (design §3.3).

    ``reasons`` is non-empty **iff** the verdict is ``INADMISSIBLE`` — a
    consistency the evidence record (:class:`tos.dsl.evidence.AdmissibilityResult`)
    re-checks so a producer cannot claim admissibility while carrying rejection
    reasons (★ producer-optimism prohibition).
    """

    verdict: AdmissibilityVerdict
    reasons: tuple[str, ...] = ()


def _node_findings(node: CandidateNode) -> list[str]:
    """Return every inadmissibility reason for a single node (fail-closed, design §3.3)."""
    reasons: list[str] = []

    # DCE-INV-001: default-deny membership (covers escape + unknown kinds alike).
    if node.kind not in ADMISSIBLE_KINDS:
        reasons.append(f"non_vocabulary_kind:{node.kind}")

    # DCE-INV-003: an ambient read source is an ambient reach.
    if node.source is not None and node.source not in ADMISSIBLE_CONTEXT_SOURCES:
        reasons.append(f"ambient_source:{node.source}")

    # DCE-INV-006 (fail-closed): a context_ref must POSITIVELY declare an admissible
    # source; a null source is not proven inside the surface, so it is inadmissible.
    if node.kind == KIND_CONTEXT_REF and node.source is None:
        reasons.append("context_ref_without_declared_source")

    # DCE-INV-003 (static naming): any named ambient symbol, in any node kind.
    if node.symbol is not None and (
        node.symbol in AMBIENT_SYMBOLS or node.symbol.lower() in AMBIENT_SYMBOLS
    ):
        reasons.append(f"ambient_symbol:{node.symbol}")

    # RFC-008 §11 item 13 / ADR-002-020 §8: wildcard / "latest" scope.
    if node.scope is not None and node.scope in WILDCARD_TOKENS:
        reasons.append(f"wildcard_scope:{node.scope}")

    return reasons


def analyze(program: CandidateProgram) -> AdmissibilityAnalysis:
    """Analyze a candidate program for admissibility (pure; design §3.3).

    Fail-closed on every axis: an empty program, any non-vocabulary node, any
    ambient source/symbol, any wildcard scope, or a source-less ``context_ref`` is
    inadmissible. The verdict is ``ADMISSIBLE`` only when *every* node is proven
    inside the surface and the program is non-empty (DCE-INV-006).

    Args:
        program: The candidate program to analyze.

    Returns:
        The :class:`AdmissibilityAnalysis` (verdict + reasons).
    """
    reasons: list[str] = []
    # Fail-closed even if a program was assembled via a validation-bypassing path
    # (e.g. model_construct) that left it empty (mirrors capsule re-check pattern).
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
    """Pure default-deny admissibility predicate (design §3.3; DCE-INV-001/003/004/006).

    Args:
        program: The candidate program to test.

    Returns:
        ``True`` iff every node is inside the Authoring Surface Vocabulary and the
        program is non-empty; ``False`` (fail-closed) otherwise.
    """
    return analyze(program).verdict is AdmissibilityVerdict.ADMISSIBLE
