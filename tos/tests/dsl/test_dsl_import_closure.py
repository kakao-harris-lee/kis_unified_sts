"""Import-closure verification for ``tos.dsl`` (design §6.4 — structural backstop)."""

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
        "shared.determinism",
        "services",
        "cli",
        "numpy",
        "pandas",
        "tos.evidence",
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
    "shared.determinism.",
    "services.",
    "cli.",
    "numpy.",
    "pandas.",
    "tos.evidence.",
)

_DSL_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "dsl"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})


def _is_forbidden(module_name: str) -> bool:
    """Whether ``module_name`` is a forbidden member of the tos.dsl closure (design §6.4)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every tos.dsl submodule; report forbidden members + capsule presence."""
    import sys

    import tos.dsl  # noqa: F401
    import tos.dsl._base  # noqa: F401
    import tos.dsl.admissibility  # noqa: F401
    import tos.dsl.bounds  # noqa: F401
    import tos.dsl.candidate  # noqa: F401
    import tos.dsl.determinism  # noqa: F401
    import tos.dsl.evidence  # noqa: F401
    import tos.dsl.outcome  # noqa: F401
    import tos.dsl.proposal  # noqa: F401
    import tos.dsl.strategy  # noqa: F401
    import tos.dsl.vocabulary  # noqa: F401

    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(
        {
            "leaked": leaked,
            "capsule_present": "tos.capsule.capsule" in sys.modules,
        }
    )


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant fake forbidden modules, then run the same scan."""
    import sys
    import types

    import tos.dsl  # noqa: F401

    sys.modules["shared.config"] = types.ModuleType("shared.config")
    sys.modules["tos.evidence"] = types.ModuleType("tos.evidence")
    sys.modules["numpy"] = types.ModuleType("numpy")
    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put({"leaked": leaked, "capsule_present": None})


def _run_child(target) -> dict:
    """Spawn ``target`` in a clean interpreter and return its reported result dict."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    result = queue.get(timeout=60)
    proc.join(timeout=60)
    assert proc.exitcode == 0, f"closure child exited abnormally: {proc.exitcode}"
    assert isinstance(result, dict), f"closure child returned {type(result).__name__}"
    return result


def test_dsl_import_closure_has_no_forbidden_packages() -> None:
    """(items 1-3, 5) A fresh import of tos.dsl pulls no forbidden package."""
    result = _run_child(_closure_child)
    assert result["leaked"] == [], f"forbidden closure members: {result['leaked']}"


def test_dsl_closure_includes_capsule_as_read_only_input() -> None:
    """(item 6) tos.capsule IS present — the read-only Decision Context Capsule input (design §0/§4)."""
    result = _run_child(_closure_child)
    assert result["capsule_present"] is True, "capsule missing from closure"


def test_leak_canary_is_detected() -> None:
    """The spawn+scan pipeline catches planted shared.config + tos.evidence + numpy leaks."""
    result = _run_child(_leak_canary_child)
    leaked = result["leaked"]
    assert "shared.config" in leaked, "planted shared.config leak was NOT detected"
    assert "tos.evidence" in leaked, "planted tos.evidence leak was NOT detected"
    assert "numpy" in leaked, "planted numpy leak was NOT detected"


def test_is_forbidden_classifier_canaries() -> None:
    """The classifier flags forbidden names and clears the allowed / present ones."""
    assert _is_forbidden("shared.config") is True
    assert _is_forbidden("shared.config.secrets") is True
    assert _is_forbidden("shared.determinism") is True
    assert _is_forbidden("shared.llm.market") is True
    assert _is_forbidden("services.dashboard") is True
    assert _is_forbidden("numpy") is True
    assert _is_forbidden("pandas.core") is True
    assert _is_forbidden("tos.evidence") is True
    assert _is_forbidden("tos.evidence.ledger") is True
    assert _is_forbidden("tos.dsl") is False
    assert _is_forbidden("tos.dsl.evidence") is False
    assert _is_forbidden("tos.capsule") is False
    assert _is_forbidden("tos.capsule.capsule") is False
    assert _is_forbidden("tos.canonical") is False
    assert _is_forbidden("pydantic") is False
    assert _is_forbidden("socket") is False
    assert _is_forbidden("ssl") is False
    assert _is_forbidden("http.client") is False
    assert _is_forbidden("urllib.request") is False
    assert _is_forbidden("urllib.parse") is False
    assert _is_forbidden("click") is False


def _ast_escape_offenders(path: Path) -> list[str]:
    """Return dynamic-escape / ambient-env offenders in one source file (static AST scan)."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith("importlib."):
                    offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "importlib":
                offenders.append(f"{path.name}:{node.lineno} from importlib import ...")
            if node.module == "os":
                for alias in node.names:
                    if alias.name in _AMBIENT_ENV_ATTRS:
                        offenders.append(
                            f"{path.name}:{node.lineno} from os import {alias.name}"
                        )
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _DYNAMIC_CALL_NAMES:
                offenders.append(f"{path.name}:{node.lineno} call {func.id}()")
            elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                offenders.append(f"{path.name}:{node.lineno} call import_module()")
        elif isinstance(node, ast.Attribute):
            if (
                node.attr in _AMBIENT_ENV_ATTRS
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                offenders.append(f"{path.name}:{node.lineno} os.{node.attr}")
    return offenders


def test_dsl_source_has_no_dynamic_escape_or_ambient_env() -> None:
    """(item 7) No tos.dsl source uses exec/eval/importlib/__import__ or os.environ (design §3.2)."""
    sources = sorted(_DSL_SRC.rglob("*.py"))
    assert sources, f"no tos.dsl source files found under {_DSL_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_escape_offenders(path))
    assert offenders == [], f"dynamic-escape / ambient-env access found: {offenders}"


def test_ast_scan_detects_planted_escape(tmp_path: Path) -> None:
    """The AST escape scan actually catches planted escapes (not vacuously green)."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import importlib\n"
        "from os import environ\n"
        "value = os.getenv\n"
        "a = eval\n",
        encoding="utf-8",
    )
    planted.write_text(
        planted.read_text(encoding="utf-8") + "b = __import__('x')\n",
        encoding="utf-8",
    )
    offenders = _ast_escape_offenders(planted)
    joined = " ".join(offenders)
    assert "import importlib" in joined
    assert "from os import environ" in joined
    assert "os.getenv" in joined
    assert "__import__()" in joined
