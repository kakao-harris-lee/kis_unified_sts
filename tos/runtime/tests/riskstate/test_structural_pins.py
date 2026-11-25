"""Structural (AST/grep) pins for the risk state service wave (plan §4.1/§5 deliverable E)."""

from __future__ import annotations

import ast
from pathlib import Path

_RUNTIME_SRC = Path(__file__).resolve().parents[2] / "src" / "tos_runtime"
_TRANSPORT_ROOT = _RUNTIME_SRC / "transport"

_FORBIDDEN_METHOD_SUBSTRINGS = ("query", "balance", "position")

_PINNED_ARTIFACT_CALLS = ("AggregateRiskPolicy", "ActionFlowPolicy")
_ALLOWED_ISSUE_CALL_SITES: dict[str, Path] = {
    "AggregateRiskPolicy": _RUNTIME_SRC
    / "riskstate"
    / "_aggregate_risk_policy_loader.py",
    "ActionFlowPolicy": _RUNTIME_SRC / "riskstate" / "_action_flow_policy_loader.py",
}

_PINNED_RECORD_TYPES = (
    "ObservedAmplification",
    "ActionCause",
    "ScopeIndependenceEvidence",
)


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_no_transport_method_name_contains_query_balance_or_position() -> None:
    assert _TRANSPORT_ROOT.is_dir(), f"expected transport root at {_TRANSPORT_ROOT}"
    violations: list[str] = []
    for path in _iter_python_files(_TRANSPORT_ROOT):
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        lowered = item.name.lower()
                        if any(sub in lowered for sub in _FORBIDDEN_METHOD_SUBSTRINGS):
                            violations.append(
                                f"{path}:{item.lineno}: {node.name}.{item.name}"
                            )
    assert not violations, (
        "a tos_runtime transport now exposes a query/balance/position-shaped method — "
        "riskstate.flow_observation.to_observed_amplification's queries=0 structural constant "
        f"must be rebuilt (offending methods: {violations})"
    )


def _issue_call_sites(
    tree: ast.Module, artifact_names: tuple[str, ...]
) -> dict[str, list[int]]:
    """``{artifact_name: [lineno, ...]}`` — one entry per pinned artifact name that has at"""
    by_artifact: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "issue":
            continue
        value = func.value
        if isinstance(value, ast.Name) and value.id in artifact_names:
            by_artifact.setdefault(value.id, []).append(node.lineno)
    return by_artifact


def test_are_afg_policy_issue_scoped_to_riskstate_policies_module() -> None:
    violations: list[str] = []
    for path in _iter_python_files(_RUNTIME_SRC):
        tree = _parse(path)
        by_artifact = _issue_call_sites(tree, _PINNED_ARTIFACT_CALLS)
        for artifact_name, sites in by_artifact.items():
            if path != _ALLOWED_ISSUE_CALL_SITES[artifact_name]:
                violations.append(f"{path}: {artifact_name}.issue() at lines {sites}")
    assert not violations, (
        "AggregateRiskPolicy.issue() must be called ONLY from "
        "_aggregate_risk_policy_loader.py, ActionFlowPolicy.issue() ONLY from "
        f"_action_flow_policy_loader.py — found elsewhere: {violations}"
    )
    for artifact_name, allowed_path in _ALLOWED_ISSUE_CALL_SITES.items():
        allowed_tree = _parse(allowed_path)
        allowed_sites = _issue_call_sites(allowed_tree, (artifact_name,))
        assert allowed_sites.get(artifact_name), (
            f"{allowed_path} itself must call {artifact_name}.issue() at least once "
            "(sanity check)"
        )


def _bool_literal_keyword_violations(
    tree: ast.Module, type_names: tuple[str, ...]
) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else None
        if name not in type_names:
            continue
        for kw in node.keywords:
            if kw.arg is None:
                continue
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool):
                violations.append(
                    f"line {node.lineno}: {name}({kw.arg}={kw.value.value})"
                )
    return violations


def test_no_bool_literal_keyword_on_observed_amplification_action_cause_scope_independence() -> (
    None
):
    violations: list[str] = []
    for path in _iter_python_files(_RUNTIME_SRC):
        tree = _parse(path)
        found = _bool_literal_keyword_violations(tree, _PINNED_RECORD_TYPES)
        if found:
            violations.append(f"{path}: {found}")
    assert not violations, (
        "a True/False literal was passed directly as a keyword to "
        "ObservedAmplification/ActionCause/ScopeIndependenceEvidence — every field on these "
        f"three types must be a real observation or governed declaration: {violations}"
    )
