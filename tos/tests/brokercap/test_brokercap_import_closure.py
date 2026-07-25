"""§7.1 import-closure verification for ``tos.brokercap`` (design #10 §7.1).

Isomorphic to the canonical / rcl / orthostate / liveauth / recon closure tests. It imports
every ``tos.brokercap`` submodule in a **fresh, spawned interpreter** (``subprocess`` / ``os``
are firewall-forbidden even in tests) and asserts:

  1. No design #1 §2.3 operational package is in the closure (``shared.execution`` / ``kis``
     / ``streaming`` / ``llm`` / ``storage`` / ``backtest``, ``services.*``, ``cli.*``).
  2. Neither ``shared.config`` nor ``shared.config.secrets`` is present (the transitive
     ambient-credential intake), nor ``shared.determinism``.
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent (bounds are injected; YAML parsing is the
     harness's concern — design #10 §0.3/§7.1).
  4. **All nine consumers / siblings are absent** — ``tos.liveauth`` / ``tos.orthostate`` /
     ``tos.recon`` / ``tos.rcl`` / ``tos.evidence`` / ``tos.capsule`` / ``tos.time`` /
     ``tos.authority`` / ``tos.dsl`` (design #10 §3.4/§3.5 — brokercap keeps a **sibling edge
     of 0**, producing bools / scalars / injected coordinates instead of importing any).
  5. **``tos.canonical`` AND ``tos.ordering`` ARE present** — the two core substrate
     dependencies (§3.1/§3.2) are explicitly ALLOWED; the closure *bounds* them, it does not
     forbid them.
  6. No ``tos.brokercap`` source references ``os.environ`` / ``os.getenv`` or a dynamic escape
     (``exec`` / ``eval`` / ``__import__`` / ``importlib``) or a real clock
     (``time`` / ``datetime``).

A planted-leak canary proves the spawn+scan pipeline actually catches a leak, and a
planted-AST-escape canary proves the static scan catches an escape, so "green" is evidence
the checker works — not that it has been neutered.

Network stdlib (``socket`` / ``ssl`` / …) is intentionally NOT asserted absent: ``pydantic``
transitively loads it into every tos closure; design #1 §4 accepts that as residual risk, and
the direct-import ban is the firewall gate (TOS-FW-B) alone.
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
        "tos.liveauth",
        "tos.orthostate",
        "tos.recon",
        "tos.rcl",
        "tos.evidence",
        "tos.capsule",
        "tos.time",
        "tos.authority",
        "tos.dsl",
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
    "tos.liveauth.",
    "tos.orthostate.",
    "tos.recon.",
    "tos.rcl.",
    "tos.evidence.",
    "tos.capsule.",
    "tos.time.",
    "tos.authority.",
    "tos.dsl.",
)

_BROKERCAP_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "brokercap"
)

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules that must never be imported by a clock-free brokercap source (§0.2).
_CLOCK_MODULES = frozenset({"time", "datetime"})


def _is_forbidden(module_name: str) -> bool:
    """Whether ``module_name`` is a forbidden member of the tos.brokercap closure (§7.1)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every tos.brokercap submodule; report forbidden closure members."""
    import sys

    import tos.brokercap  # noqa: F401
    import tos.brokercap._base  # noqa: F401
    import tos.brokercap.predicates  # noqa: F401
    import tos.brokercap.records  # noqa: F401
    import tos.brokercap.vocabulary  # noqa: F401

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

    import tos.brokercap  # noqa: F401

    sys.modules["shared.config"] = types.ModuleType("shared.config")
    sys.modules["tos.liveauth"] = types.ModuleType("tos.liveauth")
    sys.modules["tos.orthostate"] = types.ModuleType("tos.orthostate")
    sys.modules["tos.recon"] = types.ModuleType("tos.recon")
    sys.modules["numpy"] = types.ModuleType("numpy")
    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(
        {
            "leaked": leaked,
            "canonical_present": None,
            "ordering_present": None,
        }
    )


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


def test_brokercap_import_closure_has_no_forbidden_packages() -> None:
    """(§7.1 items 1-4) A fresh import of tos.brokercap pulls no forbidden package (sibling edge 0)."""
    result = _run_child(_closure_child)
    assert (
        result["leaked"] == []
    ), f"forbidden packages reached tos.brokercap closure: {result['leaked']}"


def test_brokercap_closure_includes_core_substrate() -> None:
    """(§7.1 item 5) tos.canonical + tos.ordering (the two core dependencies) are present."""
    result = _run_child(_closure_child)
    assert result["canonical_present"] is True, "tos.canonical missing from closure"
    assert result["ordering_present"] is True, "tos.ordering missing from closure"


def test_leak_canary_is_detected() -> None:
    """The spawn+scan pipeline catches planted config / liveauth / orthostate / recon / numpy leaks."""
    result = _run_child(_leak_canary_child)
    leaked = result["leaked"]
    assert "shared.config" in leaked, "planted shared.config leak was NOT detected"
    assert "tos.liveauth" in leaked, "planted tos.liveauth leak was NOT detected"
    assert "tos.orthostate" in leaked, "planted tos.orthostate leak was NOT detected"
    assert "tos.recon" in leaked, "planted tos.recon leak was NOT detected"
    assert "numpy" in leaked, "planted numpy leak was NOT detected"


def test_is_forbidden_classifier_canaries() -> None:
    """The classifier flags forbidden names (incl. every sibling) and clears the allowed core."""
    assert _is_forbidden("shared.config") is True
    assert _is_forbidden("shared.config.secrets") is True
    assert _is_forbidden("shared.determinism") is True
    assert _is_forbidden("shared.llm.market") is True
    assert _is_forbidden("services.dashboard") is True
    assert _is_forbidden("numpy") is True
    assert _is_forbidden("pandas.core") is True
    assert _is_forbidden("yaml") is True
    assert _is_forbidden("tos.liveauth") is True
    assert _is_forbidden("tos.liveauth.predicates") is True
    assert _is_forbidden("tos.orthostate") is True
    assert _is_forbidden("tos.recon") is True
    assert _is_forbidden("tos.rcl") is True
    assert _is_forbidden("tos.evidence") is True
    assert _is_forbidden("tos.capsule") is True
    assert _is_forbidden("tos.time") is True
    assert _is_forbidden("tos.authority") is True
    assert _is_forbidden("tos.dsl") is True
    # Allowed: self, the core substrate, third-party.
    assert _is_forbidden("tos.brokercap") is False
    assert _is_forbidden("tos.brokercap.predicates") is False
    assert _is_forbidden("tos.canonical") is False
    assert _is_forbidden("tos.ordering") is False
    assert _is_forbidden("pydantic") is False
    assert _is_forbidden("decimal") is False
    assert _is_forbidden("click") is False  # must not false-match the "cli" prefix


def _ast_escape_offenders(path: Path) -> list[str]:
    """Return dynamic-escape / ambient-env / real-clock offenders in one source file (AST)."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith("importlib."):
                    offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
                if alias.name in _CLOCK_MODULES:
                    offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "importlib":
                offenders.append(f"{path.name}:{node.lineno} from importlib import ...")
            if node.module in _CLOCK_MODULES:
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


def test_brokercap_source_has_no_dynamic_escape_ambient_env_or_clock() -> None:
    """(§7.1 item 6) No tos.brokercap source uses exec/eval/importlib/os.environ or a real clock."""
    sources = sorted(_BROKERCAP_SRC.rglob("*.py"))
    assert sources, f"no tos.brokercap source files found under {_BROKERCAP_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_escape_offenders(path))
    assert (
        offenders == []
    ), f"dynamic-escape / ambient-env / clock access found: {offenders}"


def test_ast_scan_detects_planted_escape(tmp_path: Path) -> None:
    """The AST escape scan actually catches planted escapes + a real-clock import (not vacuously green)."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import importlib\nimport time\nfrom os import environ\n"
        "value = os.getenv\nb = __import__('x')\n",
        encoding="utf-8",
    )
    offenders = _ast_escape_offenders(planted)
    joined = " ".join(offenders)
    assert "import importlib" in joined
    assert "import time" in joined
    assert "from os import environ" in joined
    assert "os.getenv" in joined
    assert "__import__()" in joined
