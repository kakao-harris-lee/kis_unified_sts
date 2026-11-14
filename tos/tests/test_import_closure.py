"""§7.1 import-closure verification test (C1 enforcement, design v2)."""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

_FORBIDDEN_EXACT = frozenset(
    {
        "shared.execution",
        "shared.kis",
        "shared.streaming",
        "shared.llm",
        "shared.storage",
        "shared.backtest",
        "shared.config",
        "shared.config.secrets",
        "services",
        "cli",
        "numpy",
        "pandas",
    }
)
_FORBIDDEN_PREFIXES = (
    "shared.execution.",
    "shared.kis.",
    "shared.streaming.",
    "shared.llm.",
    "shared.storage.",
    "shared.backtest.",
    "shared.config.",
    "services.",
    "cli.",
    "numpy.",
    "pandas.",
)

_CAPSULE_SRC = Path(__file__).resolve().parent.parent / "src" / "tos" / "capsule"


def _is_forbidden(module_name: str) -> bool:
    """Whether ``module_name`` is a firewall-forbidden closure member (§2.3/C1)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import the pure package, report any forbidden closure members."""
    import sys

    import tos.capsule  # noqa: F401
    import tos.capsule.canonicalization  # noqa: F401
    import tos.capsule.capsule  # noqa: F401
    import tos.capsule.consistency_cut  # noqa: F401
    import tos.capsule.context_generation  # noqa: F401
    import tos.capsule.field_evaluation  # noqa: F401
    import tos.capsule.field_state  # noqa: F401
    import tos.capsule.lineage  # noqa: F401
    import tos.capsule.observation  # noqa: F401
    import tos.capsule.predicates  # noqa: F401
    import tos.capsule.snapshot  # noqa: F401

    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(leaked)


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant a fake forbidden module, then run the same scan."""
    import sys
    import types

    import tos.capsule  # noqa: F401

    sys.modules["shared.llm"] = types.ModuleType("shared.llm")
    sys.modules["numpy"] = types.ModuleType("numpy")
    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(leaked)


def _run_child(target) -> list[str]:
    """Spawn ``target`` in a clean interpreter and return the leak list it reports."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    proc.join(timeout=60)
    assert proc.exitcode == 0, f"closure child exited abnormally: {proc.exitcode}"
    leaked = queue.get(timeout=5)
    assert isinstance(leaked, list), f"closure child returned {type(leaked).__name__}"
    return leaked


def test_import_closure_has_no_forbidden_packages() -> None:
    """(§7.1 items 1-3) A fresh import of tos.capsule pulls no forbidden package."""
    leaked = _run_child(_closure_child)
    assert leaked == [], f"forbidden packages reached tos.capsule closure: {leaked}"


def test_leak_canary_is_detected() -> None:
    """(MINOR-6) The spawn+scan pipeline catches a planted leak (not vacuously green)."""
    leaked = _run_child(_leak_canary_child)
    assert "shared.llm" in leaked, "planted shared.llm leak was NOT detected"
    assert "numpy" in leaked, "planted numpy leak was NOT detected"


def test_is_forbidden_classifier_canaries() -> None:
    """(MINOR-6) The classifier flags forbidden names and clears allowed ones."""
    assert _is_forbidden("shared.llm") is True
    assert _is_forbidden("shared.llm.market") is True
    assert _is_forbidden("shared.config") is True
    assert _is_forbidden("shared.config.secrets") is True
    assert _is_forbidden("services") is True
    assert _is_forbidden("services.dashboard") is True
    assert _is_forbidden("cli") is True
    assert _is_forbidden("numpy") is True
    assert _is_forbidden("pandas.core") is True
    assert _is_forbidden("shared.utils") is False
    assert _is_forbidden("shared.exceptions") is False
    assert _is_forbidden("pydantic") is False
    assert _is_forbidden("tos.capsule") is False
    assert _is_forbidden("click") is False


def test_model_source_has_no_ambient_env_access() -> None:
    """(§7.1 item 3) No capsule module references os.environ / os.getenv."""
    offenders: list[str] = []
    for path in sorted(_CAPSULE_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr in {"environ", "getenv"}
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                offenders.append(f"{path.name}:{node.lineno} os.{node.attr}")
            elif isinstance(node, ast.ImportFrom) and node.module == "os":
                for alias in node.names:
                    if alias.name in {"environ", "getenv"}:
                        offenders.append(
                            f"{path.name}:{node.lineno} from os import {alias.name}"
                        )
    assert offenders == [], f"ambient env access found: {offenders}"
