"""§7.1 import-closure verification for ``tos.rcl`` (RCL design §7.1).

Isomorphic to the capsule / evidence / dsl closure tests, extended to the RCL
package. It imports every ``tos.rcl`` submodule in a **fresh, spawned interpreter**
(``subprocess``/``os`` are firewall-forbidden even in tests) and asserts:

  1. No design §2.3 operational package is in the closure (``shared.execution`` /
     ``kis`` / ``streaming`` / ``llm`` / ``storage`` / ``backtest``, ``services.*``,
     ``cli.*``).
  2. Neither ``shared.config`` nor ``shared.config.secrets`` is present (C1 — the
     transitive ambient-credential intake), nor ``shared.determinism``.
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent (bounds are injected; YAML parsing
     is the harness's concern — RCL design §0.3/§7.1).
  4. **``tos.capsule`` AND ``tos.evidence`` are absent** (§0.3/§3.1 layering — RCL is
     the *upstream* Safety Commit Log and evidence is a downstream projection, so RCL
     imports neither; ordering comes only from the core ``tos.ordering``).
  5. No ``tos.rcl`` source references ``os.environ`` / ``os.getenv`` or a dynamic
     escape (``exec`` / ``eval`` / ``__import__`` / ``importlib``).

A planted-leak canary proves the spawn+scan pipeline actually catches a leak, so
"green" is evidence the checker works — not that it has been neutered.

Network stdlib (``socket`` / ``ssl`` / …) is intentionally NOT asserted absent:
``pydantic`` transitively loads it into every tos closure; design #1 §4 accepts that
as residual risk, and the direct-import ban is the firewall gate (TOS-FW-B) alone.
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
        "tos.capsule",
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
    "yaml.",
    "tos.capsule.",
    "tos.evidence.",
)

_RCL_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "rcl"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})


def _is_forbidden(module_name: str) -> bool:
    """Whether ``module_name`` is a forbidden member of the tos.rcl closure (§7.1)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every tos.rcl submodule; report forbidden closure members."""
    import sys

    import tos.canonical  # noqa: F401
    import tos.ordering  # noqa: F401
    import tos.rcl  # noqa: F401
    import tos.rcl._base  # noqa: F401
    import tos.rcl.authority  # noqa: F401
    import tos.rcl.predicates  # noqa: F401
    import tos.rcl.records  # noqa: F401
    import tos.rcl.state  # noqa: F401
    import tos.rcl.vector  # noqa: F401
    import tos.rcl.vocabulary  # noqa: F401

    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(
        {
            "leaked": leaked,
            "canonical_present": "tos.canonical" in sys.modules,
            "ordering_present": "tos.ordering" in sys.modules,
        }
    )


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant fake forbidden modules, then run the same scan."""
    import sys
    import types

    import tos.rcl  # noqa: F401

    sys.modules["shared.config"] = types.ModuleType("shared.config")
    sys.modules["tos.evidence"] = types.ModuleType("tos.evidence")
    sys.modules["tos.capsule"] = types.ModuleType("tos.capsule")
    sys.modules["numpy"] = types.ModuleType("numpy")
    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put({"leaked": leaked, "canonical_present": None, "ordering_present": None})


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


def test_rcl_import_closure_has_no_forbidden_packages() -> None:
    """(§7.1 items 1-4) A fresh import of tos.rcl pulls no forbidden package."""
    result = _run_child(_closure_child)
    assert (
        result["leaked"] == []
    ), f"forbidden packages reached tos.rcl closure: {result['leaked']}"


def test_rcl_closure_includes_core_substrate() -> None:
    """tos.canonical + tos.ordering ARE present (the one-directional core deps)."""
    result = _run_child(_closure_child)
    assert result["canonical_present"] is True, "tos.canonical missing from closure"
    assert result["ordering_present"] is True, "tos.ordering missing from closure"


def test_leak_canary_is_detected() -> None:
    """The spawn+scan pipeline catches planted config / evidence / capsule / numpy leaks."""
    result = _run_child(_leak_canary_child)
    leaked = result["leaked"]
    assert "shared.config" in leaked, "planted shared.config leak was NOT detected"
    assert "tos.evidence" in leaked, "planted tos.evidence leak was NOT detected"
    assert "tos.capsule" in leaked, "planted tos.capsule leak was NOT detected"
    assert "numpy" in leaked, "planted numpy leak was NOT detected"


def test_is_forbidden_classifier_canaries() -> None:
    """The classifier flags forbidden names (incl. tos.capsule + tos.evidence) and clears allowed ones."""
    assert _is_forbidden("shared.config") is True
    assert _is_forbidden("shared.config.secrets") is True
    assert _is_forbidden("shared.determinism") is True
    assert _is_forbidden("shared.llm.market") is True
    assert _is_forbidden("services.dashboard") is True
    assert _is_forbidden("numpy") is True
    assert _is_forbidden("pandas.core") is True
    assert _is_forbidden("yaml") is True
    assert _is_forbidden("tos.capsule") is True
    assert _is_forbidden("tos.capsule._base") is True
    assert _is_forbidden("tos.evidence") is True
    assert _is_forbidden("tos.evidence.ledger") is True
    # Allowed: self, the core substrate, third-party.
    assert _is_forbidden("tos.rcl") is False
    assert _is_forbidden("tos.canonical") is False
    assert _is_forbidden("tos.ordering") is False
    assert _is_forbidden("pydantic") is False
    assert _is_forbidden("decimal") is False
    assert _is_forbidden("click") is False  # must not false-match the "cli" prefix


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


def test_rcl_source_has_no_dynamic_escape_or_ambient_env() -> None:
    """(§7.1 item 5) No tos.rcl source uses exec/eval/importlib/__import__ or os.environ."""
    sources = sorted(_RCL_SRC.rglob("*.py"))
    assert sources, f"no tos.rcl source files found under {_RCL_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_escape_offenders(path))
    assert offenders == [], f"dynamic-escape / ambient-env access found: {offenders}"


def test_ast_scan_detects_planted_escape(tmp_path: Path) -> None:
    """The AST escape scan actually catches planted escapes (not vacuously green)."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import importlib\nfrom os import environ\nvalue = os.getenv\nb = __import__('x')\n",
        encoding="utf-8",
    )
    offenders = _ast_escape_offenders(planted)
    joined = " ".join(offenders)
    assert "import importlib" in joined
    assert "from os import environ" in joined
    assert "os.getenv" in joined
    assert "__import__()" in joined
