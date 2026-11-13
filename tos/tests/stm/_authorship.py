"""The ``tos.stm`` authorship sweep — the target of every §0.2 absence lock.

An ``hasattr(tos.stm, name)`` check only locks the export surface, while the package
*authors* several hundred names: a forbidden symbol re-authored inside a module and
never exported would slip through (the #27 adversarial-review MAJOR-1 lesson — lock
authorship, not the export surface). :func:`authored_names` is therefore the union of
every module namespace **and** an AST sweep of every source, so a symbol nested in a
class body or left out of ``__all__`` is caught too.

Lifted out of ``test_stm_anchor_resolution.py`` when that module was deleted with the
``tos-spec/`` corpus it resolved ADR line anchors against
(``docs/plans/2026-11-13-tos-code-halving-plan.md`` §S3). Only the ADR-anchor half of
that module went; this half has three importers and no spec dependency.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import tos.stm as s
import tos.stm._base
import tos.stm.predicates
import tos.stm.records
import tos.stm.state
import tos.stm.vocabulary

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STM_SRC = _REPO_ROOT / "tos" / "src" / "tos" / "stm"

_SUBMODULES: dict[str, ModuleType] = {
    "_base": tos.stm._base,
    "predicates": tos.stm.predicates,
    "records": tos.stm.records,
    "state": tos.stm.state,
    "vocabulary": tos.stm.vocabulary,
}


def stm_sources() -> list[Path]:
    """Every ``tos.stm`` source, asserted **non-empty** so a path typo cannot make a sweep vacuous."""
    sources = sorted(_STM_SRC.rglob("*.py"))
    assert (
        sources
    ), f"no tos.stm source found under {_STM_SRC} — this sweep would be vacuous"
    return sources


def _assignment_targets(node: ast.AST) -> list[str]:
    """The identifier names a statement binds, if any."""
    names: list[str] = []
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.extend(
                element.id for element in target.elts if isinstance(element, ast.Name)
            )
    return names


def _source_authored_names() -> set[str]:
    """Every identifier any ``tos.stm`` source *defines* — at any nesting depth."""
    names: set[str] = set()
    for path in stm_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            else:
                names.update(_assignment_targets(node))
    return names


def authored_names() -> set[str]:
    """Everything this package authors or binds — the target of every absence lock."""
    names = set(vars(s))
    for module in _SUBMODULES.values():
        names |= set(vars(module))
    return names | _source_authored_names()
