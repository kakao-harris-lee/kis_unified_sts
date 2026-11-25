"""AST-pin canary: none of the boot-time replay stand-in modules"""

from __future__ import annotations

import ast
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]
_SRC = _RUNTIME_ROOT / "src"

_REPLAY_FILES = {
    _SRC / "tos_runtime" / "engine" / "replay.py",
    _SRC / "tos_runtime" / "engine" / "replay_transmit.py",
    _SRC / "tos_runtime" / "engine" / "replay_stage.py",
}

_FORBIDDEN_PREFIXES = (
    "tos.brokeradapter",
    "tos.egressgw",
    "tos_runtime.authority",
    "tos_runtime.risk",
    "tos_runtime.currentness",
)


def _imported_module_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _is_forbidden(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(prefix + ".")
        for prefix in _FORBIDDEN_PREFIXES
    )


def test_replay_modules_never_import_a_transport_or_service_package() -> None:
    offenders: list[str] = []
    for path in sorted(_REPLAY_FILES):
        for module_name in _imported_module_names(path):
            if _is_forbidden(module_name):
                offenders.append(
                    f"{path.relative_to(_RUNTIME_ROOT)}: imports {module_name!r}"
                )
    assert offenders == [], (
        "boot-time replay module(s) import a transport-capable or tos_runtime service package — "
        "replay must never be ABLE to construct or call a real transport/service, structurally, "
        "regardless of what any given test scenario happens to exercise (CR5/CR5-3, 2026-09-09):"
        "\n" + "\n".join(offenders)
    )
