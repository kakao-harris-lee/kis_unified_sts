"""Gateway-cycle canaries for ``tos.egressgw`` — the closure canaries live in the shared table."""

from __future__ import annotations

import ast
from pathlib import Path

from .._closure_policy import SRC_ROOT

_SRC = SRC_ROOT / "egressgw"

_MESH_PACKAGE_BITS = ("tos", "egressgw")


def _resolve_relative_import_prefix(module: str, level: int) -> str | None:
    """Resolve one ``ImportFrom(module, level)`` in ``mesh.py`` to the absolute dotted prefix it"""
    if level > len(_MESH_PACKAGE_BITS):
        return None
    base = ".".join(_MESH_PACKAGE_BITS[: len(_MESH_PACKAGE_BITS) - level + 1])
    return f"{base}.{module}" if module else base


def test_mesh_never_imports_gateway() -> None:
    """(kernel round #2 §2 decision 1 — mutation M5) ``mesh.py`` must not import ``gateway.py``."""
    mesh_path = _SRC / "mesh.py"
    tree = ast.parse(mesh_path.read_text(encoding="utf-8"), filename=str(mesh_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tos.egressgw.gateway" or alias.name.endswith(
                    ".gateway"
                ):
                    offenders.append(f"mesh.py:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                prefix = _resolve_relative_import_prefix(module, node.level)
                if prefix is None:
                    continue
                if prefix == "tos.egressgw.gateway":
                    offenders.append(
                        f"mesh.py:{node.lineno} relative import resolves to gateway "
                        f"(level={node.level}, module={module!r})"
                    )
                    continue
                for alias in node.names:
                    if f"{prefix}.{alias.name}" == "tos.egressgw.gateway":
                        offenders.append(
                            f"mesh.py:{node.lineno} relative import resolves to gateway "
                            f"(level={node.level}, module={module!r}, name={alias.name!r})"
                        )
                continue
            if module in ("tos.egressgw.gateway", "tos.egressgw"):
                for alias in node.names:
                    if alias.name == "gateway":
                        offenders.append(
                            f"mesh.py:{node.lineno} from {module} import {alias.name}"
                        )
            if module == "tos.egressgw.gateway":
                offenders.append(f"mesh.py:{node.lineno} from {module} import ...")
    assert offenders == [], f"mesh.py imports gateway.py — circular edge: {offenders}"


def _module_imports_gateway(path: Path) -> list[str]:
    """The same gateway-import scan :func:`test_mesh_never_imports_gateway` runs against"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tos.egressgw.gateway" or alias.name.endswith(
                    ".gateway"
                ):
                    offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                prefix = _resolve_relative_import_prefix(module, node.level)
                if prefix is None:
                    continue
                if prefix == "tos.egressgw.gateway":
                    offenders.append(
                        f"{path.name}:{node.lineno} relative import resolves to gateway "
                        f"(level={node.level}, module={module!r})"
                    )
                    continue
                for alias in node.names:
                    if f"{prefix}.{alias.name}" == "tos.egressgw.gateway":
                        offenders.append(
                            f"{path.name}:{node.lineno} relative import resolves to gateway "
                            f"(level={node.level}, module={module!r}, name={alias.name!r})"
                        )
                continue
            if module in ("tos.egressgw.gateway", "tos.egressgw"):
                for alias in node.names:
                    if alias.name == "gateway":
                        offenders.append(
                            f"{path.name}:{node.lineno} from {module} import {alias.name}"
                        )
            if module == "tos.egressgw.gateway":
                offenders.append(f"{path.name}:{node.lineno} from {module} import ...")
    return offenders


def test_venuefacts_never_imports_gateway() -> None:
    """(kernel round #3 §2 decision 4 — mutation M4) ``venuefacts.py`` must not import"""
    offenders = _module_imports_gateway(_SRC / "venuefacts.py")
    assert (
        offenders == []
    ), f"venuefacts.py imports gateway.py — circular edge: {offenders}"
