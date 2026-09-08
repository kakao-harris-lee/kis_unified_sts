"""§7.1 import-closure verification for ``tos.workload`` (design #40 D4 kernel side).

Isomorphic to the authority / evidence closure tests. It imports every
``tos.workload`` submodule in a **fresh, spawned interpreter** (``subprocess`` /
``os`` are firewall-forbidden even in tests) and asserts:

  1. No design §2.3 operational package is in the closure.
  2. Neither ``shared.config`` nor ``shared.config.secrets`` is present (C1).
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent.
  4. **No other ``tos`` sibling package is present** — ``tos.rcl`` / ``tos.evidence``
     / ``tos.authority`` / ``tos.egress`` / ``tos.capsule`` are all absent
     (``tos.workload``'s own module docstring "package placement" note: the
     ``key_generation`` / epoch / principal identity axes are reported as
     distinct, never silently coupled by an import edge).
  5. ``tos.canonical`` IS present (the digest-binding substrate this package's
     ``FrozenModel``/``ArtifactIntegrityError`` come from).
  6. No ``tos.workload`` source references ``os.environ`` / ``os.getenv``, a
     dynamic escape, or a real clock/RNG module (``time`` / ``datetime`` /
     ``random`` / ``secrets`` / ``uuid`` — this package issues no nonce itself).

A planted-leak canary proves the spawn+scan pipeline actually catches a leak, so
"green" is evidence the checker works — not that it has been neutered.
"""

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
        "yaml",
        "tos.rcl",
        "tos.capsule",
        "tos.evidence",
        "tos.authority",
        "tos.egress",
        "tos.egressgw",
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
    "yaml.",
    "tos.rcl.",
    "tos.capsule.",
    "tos.evidence.",
    "tos.authority.",
    "tos.egress.",
    "tos.egressgw.",
)

_WORKLOAD_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "workload"
)

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock / RNG modules forbidden in a clock-free, nonce-issuing-elsewhere
#: package (§0.2-style convention shared by every ``tos`` kernel package).
_CLOCK_AND_RNG_MODULES = frozenset({"time", "datetime", "random", "secrets", "uuid"})


def _is_forbidden(module_name: str) -> bool:
    """Whether ``module_name`` is a forbidden member of the tos.workload closure."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every tos.workload submodule; report forbidden closure members."""
    import sys

    import tos.canonical  # noqa: F401
    import tos.workload  # noqa: F401
    import tos.workload.predicates  # noqa: F401
    import tos.workload.records  # noqa: F401

    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put({"leaked": leaked, "canonical_present": "tos.canonical" in sys.modules})


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant fake forbidden modules, then run the same scan."""
    import sys
    import types

    import tos.workload  # noqa: F401

    sys.modules["shared.config"] = types.ModuleType("shared.config")
    sys.modules["tos.rcl"] = types.ModuleType("tos.rcl")
    sys.modules["tos.evidence"] = types.ModuleType("tos.evidence")
    sys.modules["numpy"] = types.ModuleType("numpy")
    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put({"leaked": leaked, "canonical_present": None})


def _run_child(target) -> dict:
    """Spawn ``target`` in a clean interpreter and return its reported result dict."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    result = queue.get(timeout=60)
    proc.join(timeout=60)
    assert proc.exitcode == 0, f"closure child exited abnormally: {proc.exitcode}"
    return result


def test_workload_import_closure_has_no_forbidden_packages() -> None:
    """(items 1-4) A fresh import of tos.workload pulls no forbidden package."""
    result = _run_child(_closure_child)
    assert (
        result["leaked"] == []
    ), f"forbidden packages reached tos.workload closure: {result['leaked']}"


def test_workload_closure_includes_canonical() -> None:
    """(item 5) tos.canonical IS present in the closure."""
    result = _run_child(_closure_child)
    assert result["canonical_present"] is True, "tos.canonical missing from closure"


def test_leak_canary_is_detected() -> None:
    """The spawn+scan pipeline catches planted shared.config / rcl / evidence / numpy leaks."""
    result = _run_child(_leak_canary_child)
    leaked = result["leaked"]
    assert "shared.config" in leaked, "planted shared.config leak was NOT detected"
    assert "tos.rcl" in leaked, "planted tos.rcl leak was NOT detected"
    assert "tos.evidence" in leaked, "planted tos.evidence leak was NOT detected"
    assert "numpy" in leaked, "planted numpy leak was NOT detected"


def test_is_forbidden_classifier_canaries() -> None:
    """The classifier flags forbidden names and clears allowed ones."""
    assert _is_forbidden("shared.config") is True
    assert _is_forbidden("tos.rcl") is True
    assert _is_forbidden("tos.evidence.ledger") is True
    assert _is_forbidden("tos.authority") is True
    assert _is_forbidden("tos.egress") is True
    assert _is_forbidden("numpy") is True
    assert _is_forbidden("yaml") is True
    # Allowed: self, the core substrate, third-party.
    assert _is_forbidden("tos.workload") is False
    assert _is_forbidden("tos.canonical") is False
    assert _is_forbidden("pydantic") is False
    assert _is_forbidden("click") is False  # must not false-match the "cli" prefix


def _ast_escape_offenders(path: Path) -> list[str]:
    """Return dynamic-escape / ambient-env / real-clock/RNG offenders in one source file."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith("importlib."):
                    offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
                if alias.name in _CLOCK_AND_RNG_MODULES:
                    offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "importlib":
                offenders.append(f"{path.name}:{node.lineno} from importlib import ...")
            if node.module in _CLOCK_AND_RNG_MODULES:
                offenders.append(
                    f"{path.name}:{node.lineno} from {node.module} import ..."
                )
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


def test_workload_source_has_no_dynamic_escape_ambient_env_or_clock() -> None:
    """(item 6) No tos.workload source uses exec/eval/importlib/os.environ/clock/RNG."""
    sources = sorted(_WORKLOAD_SRC.rglob("*.py"))
    assert sources, f"no tos.workload source files found under {_WORKLOAD_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_escape_offenders(path))
    assert (
        offenders == []
    ), f"dynamic-escape / ambient-env / clock / RNG access found: {offenders}"


def test_ast_scan_detects_planted_escape(tmp_path: Path) -> None:
    """The AST escape scan actually catches planted escapes + a real-clock import."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import importlib\nimport time\nimport random\nfrom os import environ\n"
        "value = os.getenv\nb = __import__('x')\n",
        encoding="utf-8",
    )
    offenders = _ast_escape_offenders(planted)
    joined = " ".join(offenders)
    assert "import importlib" in joined
    assert "import time" in joined
    assert "import random" in joined
    assert "from os import environ" in joined
    assert "os.getenv" in joined
    assert "__import__()" in joined
