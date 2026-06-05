"""Policy tests for removed ClickHouse runtime dependency."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOTS = (
    "services",
    "core",
    "cli",
    "shared/strategy/gates",
)
FORBIDDEN_DB_CLIENT_IMPORTS = {
    "ClickHouseClient",
    "AsyncClickHouseClient",
    "get_clickhouse_client",
}


def _runtime_python_files() -> list[Path]:
    files: list[Path] = []
    for root in RUNTIME_ROOTS:
        files.extend(
            path
            for path in (REPO_ROOT / root).rglob("*.py")
            if "__pycache__" not in path.parts
        )
    return sorted(files)


def test_runtime_code_does_not_import_clickhouse_clients_directly():
    """Runtime code should not import removed ClickHouse clients."""
    violations: list[str] = []
    for path in _runtime_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "clickhouse_driver":
                        violations.append(
                            f"{path.relative_to(REPO_ROOT)}:{node.lineno}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "clickhouse_driver":
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
                elif module == "shared.db.client":
                    imported = {alias.name for alias in node.names}
                    if imported & FORBIDDEN_DB_CLIENT_IMPORTS:
                        violations.append(
                            f"{path.relative_to(REPO_ROOT)}:{node.lineno}"
                        )

    assert violations == []
