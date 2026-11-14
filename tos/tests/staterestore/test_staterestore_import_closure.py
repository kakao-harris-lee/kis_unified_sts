"""TOS-FW-B/C/D static scan for ``tos.staterestore`` — the closure canaries are table-driven."""

from __future__ import annotations

import ast
from pathlib import Path

from .._closure_policy import SRC_ROOT

_STATERESTORE_SRC = SRC_ROOT / "staterestore"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
_FORBIDDEN_STDLIB = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "urllib.request",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "telnetlib",
        "subprocess",
        "ctypes",
    }
)


def _scan_source(tree: ast.AST) -> dict[str, list[str]]:
    """Report ambient-env reads, dynamic escapes, and forbidden stdlib imports."""
    env: list[str] = []
    dynamic: list[str] = []
    forbidden: list[str] = []

    def _forbidden_module(dotted: str) -> bool:
        return any(
            dotted == name or dotted.startswith(name + ".")
            for name in _FORBIDDEN_STDLIB
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _AMBIENT_ENV_ATTRS:
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                env.append(f"os.{node.attr}@{node.lineno}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _DYNAMIC_CALL_NAMES:
                dynamic.append(f"{func.id}@{node.lineno}")
            elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                dynamic.append(f"import_module@{node.lineno}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _forbidden_module(alias.name):
                    forbidden.append(f"{alias.name}@{node.lineno}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "os":
                for alias in node.names:
                    if alias.name in _AMBIENT_ENV_ATTRS:
                        env.append(f"from os import {alias.name}@{node.lineno}")
            if module == "importlib":
                for alias in node.names:
                    if alias.name == "import_module":
                        dynamic.append(f"from importlib import ...@{node.lineno}")
            if not node.level and module:
                for alias in node.names:
                    if _forbidden_module(f"{module}.{alias.name}") or _forbidden_module(
                        module
                    ):
                        forbidden.append(f"{module}.{alias.name}@{node.lineno}")
    return {"env": env, "dynamic": dynamic, "forbidden_stdlib": forbidden}


def _staterestore_sources() -> list[Path]:
    return sorted(p for p in _STATERESTORE_SRC.rglob("*.py"))


def test_the_package_has_sources_to_scan() -> None:
    """∅-seal: an empty file list would make every scan below vacuously green."""
    assert len(_staterestore_sources()) >= 4


def test_no_staterestore_source_reaches_for_ambient_env_or_a_dynamic_escape() -> None:
    """TOS-FW-C / TOS-FW-D — S-4 is parametrized by argv, never by the environment."""
    findings: dict[str, dict[str, list[str]]] = {}
    for path in _staterestore_sources():
        result = _scan_source(ast.parse(path.read_text(encoding="utf-8")))
        if result["env"] or result["dynamic"]:
            findings[path.name] = result
    assert findings == {}, f"ambient env / dynamic escape in staterestore: {findings}"


def test_no_staterestore_source_imports_a_forbidden_stdlib_module() -> None:
    """TOS-FW-B — no egress / process / FFI primitive is imported directly."""
    findings = {
        path.name: result["forbidden_stdlib"]
        for path in _staterestore_sources()
        if (result := _scan_source(ast.parse(path.read_text(encoding="utf-8"))))[
            "forbidden_stdlib"
        ]
    }
    assert findings == {}, f"forbidden stdlib imported by staterestore: {findings}"


def test_the_static_scan_catches_a_planted_escape() -> None:
    """The scanner works: a planted ``os.environ`` / ``eval`` / ``socket`` is reported."""
    planted = ast.parse(
        "import os\n"
        "import socket\n"
        "from importlib import import_module\n"
        "def leak():\n"
        "    return os.environ.get('X'), eval('1'), socket\n"
    )
    result = _scan_source(planted)
    assert result["env"], "planted os.environ was NOT detected"
    assert result["dynamic"], "planted eval / import_module was NOT detected"
    assert result["forbidden_stdlib"], "planted socket import was NOT detected"
