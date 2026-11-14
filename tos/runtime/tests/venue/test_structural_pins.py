"""AST-pin canaries for tos_runtime.venue (plan §5 mutation table M3/M9):"""

from __future__ import annotations

import ast
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]
_SRC = _RUNTIME_ROOT / "src" / "tos_runtime"
_VENUE_POLICY_LOADER = _SRC / "venue" / "_venue_policy_loader.py"
_OCP_LOADER = _SRC / "venue" / "_order_construction_policy_loader.py"
_VENUE_SERVICE = _SRC / "venue" / "service.py"

_ISSUE_METHOD_HOMES: dict[str, Path] = {
    "VenueConstraintPolicy": _VENUE_POLICY_LOADER,
    "OrderConstructionPolicy": _OCP_LOADER,
    "VenueConstraintSnapshot": _VENUE_SERVICE,
    "OrderAdmissibilityDecision": _VENUE_SERVICE,
}


def _all_py_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _issue_call_owner(node: ast.Call) -> str | None:
    """If ``node`` is a call of the shape ``<Name>.issue(...)``, return the"""
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "issue"
        and isinstance(func.value, ast.Name)
    ):
        return func.value.id
    return None


def test_issue_calls_scoped_to_their_owning_module() -> None:
    offenders: list[str] = []
    for path in _all_py_files(_SRC):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            owner = _issue_call_owner(node)
            if owner is None or owner not in _ISSUE_METHOD_HOMES:
                continue
            allowed_file = _ISSUE_METHOD_HOMES[owner]
            if path != allowed_file:
                offenders.append(f"{path}:{node.lineno}: {owner}.issue(...)")
    assert offenders == [], (
        "VenueConstraintPolicy.issue (only in "
        f"{_VENUE_POLICY_LOADER}), OrderConstructionPolicy.issue (only in "
        f"{_OCP_LOADER}), and VenueConstraintSnapshot/"
        f"OrderAdmissibilityDecision.issue (only in {_VENUE_SERVICE}) must be "
        f"called from exactly its owning module (plan §5 M9): {offenders}"
    )


def _attribute_names_in_call_args_or_keywords(node: ast.Call) -> list[str]:
    """Every ``OrderAdmissibilityResult.<MEMBER>`` attribute-access dotted"""
    found = []
    for arg in node.args:
        if (
            isinstance(arg, ast.Attribute)
            and isinstance(arg.value, ast.Name)
            and arg.value.id == "OrderAdmissibilityResult"
        ):
            found.append(arg.attr)
    for kw in node.keywords:
        value = kw.value
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == "OrderAdmissibilityResult"
        ):
            found.append(value.attr)
    return found


def test_order_admissibility_result_never_passed_as_a_call_argument() -> None:
    """Plan §5 mutation M3: ``VenueConstraintService.decide`` returning a"""
    offenders: list[str] = []
    for path in _all_py_files(_SRC):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for member in _attribute_names_in_call_args_or_keywords(node):
                offenders.append(
                    f"{path}:{node.lineno}: OrderAdmissibilityResult.{member}"
                )
    assert offenders == [], (
        "tos_runtime must never construct/pass an OrderAdmissibilityResult "
        f"member as a call argument (plan §2 decision 1 / §5 M3): {offenders}"
    )
