"""Shared AST scan behind every package's truthy-sentinel source seal."""

from __future__ import annotations

import ast
from pathlib import Path

KERNEL_SRC = Path(__file__).resolve().parent.parent / "src" / "tos"


def bare_truthiness_offenders(path: Path, suspicious: frozenset[str]) -> list[str]:
    """Return ``if <name>:`` / ``if not <name>:`` uses of a ``suspicious`` local (AST)."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            test = test.operand
        if isinstance(test, ast.Name) and test.id in suspicious:
            offenders.append(f"{path.name}:{node.lineno} bare truthiness on {test.id}")
    return offenders


def package_truthiness_offenders(package: str, suspicious: frozenset[str]) -> list[str]:
    """Scan every ``tos.<package>`` source file; an empty package is itself a failure."""
    root = KERNEL_SRC / package
    sources = sorted(root.rglob("*.py"))
    assert sources, f"no tos.{package} source files found under {root}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(bare_truthiness_offenders(path, suspicious))
    return offenders
