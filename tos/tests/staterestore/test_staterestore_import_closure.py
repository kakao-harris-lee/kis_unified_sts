"""§7.1 import-closure verification for ``tos.staterestore`` (design #39 §7.4 / §8).

Isomorphic to the orthostate / rcl / evidence closure tests, extended to the first tos
package that performs real I/O. It imports every ``tos.staterestore`` submodule in a
**fresh, spawned interpreter** (``multiprocessing`` spawn — ``subprocess`` is
firewall-forbidden inside ``tos/``) and asserts:

  1. No design #1 §2.3 operational package is in the closure (``shared.execution`` /
     ``kis`` / ``streaming`` / ``llm`` / ``storage`` / ``backtest``, ``services.*``,
     ``cli.*``), nor ``shared.config`` / ``shared.config.secrets`` / ``shared.determinism``.
  2. ``numpy`` / ``pandas`` / ``yaml`` are absent.
  3. The orthostate layering is inherited: ``tos.evidence`` / ``tos.capsule`` /
     ``tos.dsl`` / ``tos.authority`` / ``tos.liveauth`` / ``tos.time`` are absent.
     Persistence sits *beside* the decision-side state model, not above the evidence
     ledger.
  4. ``tos.orthostate`` AND ``tos.rcl`` ARE present — the declared, bounded edges.
  5. ``sqlite3`` IS present. Asserted **positively**: this package's whole reason to
     exist is a real durable substrate, and a closure that no longer reached ``sqlite3``
     would mean the store had quietly become something else.
  6. No ``tos.staterestore`` source references ``os.environ`` / ``os.getenv`` (TOS-FW-C
     — S-4 is parametrized by argv alone) or a dynamic escape (``exec`` / ``eval`` /
     ``__import__`` / ``importlib``), and none imports a forbidden egress / process /
     FFI stdlib module (TOS-FW-B).

A planted-leak canary proves the spawn+scan pipeline actually catches a leak, and a
planted-AST-escape canary proves the static scan catches an escape, so "green" is
evidence the checker works — not that it has been neutered.

Network stdlib (``socket`` / ``ssl`` / …) is intentionally NOT asserted absent from the
closure: ``pydantic`` transitively loads it into every tos closure; design #1 §4 accepts
that as residual risk, and the direct-import ban (TOS-FW-B, item 6 above) is the gate.
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
        "tos.evidence",
        "tos.capsule",
        "tos.dsl",
        "tos.authority",
        "tos.liveauth",
        "tos.time",
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
    "tos.evidence.",
    "tos.capsule.",
    "tos.dsl.",
    "tos.authority.",
    "tos.liveauth.",
    "tos.time.",
)

_STATERESTORE_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "staterestore"
)

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: TOS-FW-B (design #1 §3.2) — the egress / process / FFI primitives no tos source may
#: import directly. Restated here so the package carries its own executable copy of the
#: obligation rather than relying on a gate that lives elsewhere.
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


def _is_forbidden(module_name: str) -> bool:
    """Whether ``module_name`` is a forbidden member of the closure (§7.1)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every tos.staterestore submodule; report the closure."""
    import sys

    import tos.staterestore  # noqa: F401
    import tos.staterestore._l3_worker  # noqa: F401
    import tos.staterestore.reload  # noqa: F401
    import tos.staterestore.store  # noqa: F401

    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(
        {
            "leaked": leaked,
            "orthostate_present": "tos.orthostate" in sys.modules,
            "rcl_present": "tos.rcl" in sys.modules,
            "sqlite3_present": "sqlite3" in sys.modules,
        }
    )


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant fake forbidden modules, then run the same scan."""
    import sys
    import types

    import tos.staterestore  # noqa: F401

    sys.modules["shared.config"] = types.ModuleType("shared.config")
    sys.modules["tos.evidence"] = types.ModuleType("tos.evidence")
    sys.modules["tos.liveauth"] = types.ModuleType("tos.liveauth")
    sys.modules["numpy"] = types.ModuleType("numpy")
    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(
        {
            "leaked": leaked,
            "orthostate_present": None,
            "rcl_present": None,
            "sqlite3_present": None,
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


def test_staterestore_import_closure_has_no_forbidden_packages() -> None:
    """(items 1-3) A fresh import of tos.staterestore pulls no forbidden package."""
    result = _run_child(_closure_child)
    assert (
        result["leaked"] == []
    ), f"forbidden packages reached the tos.staterestore closure: {result['leaked']}"


def test_staterestore_closure_includes_its_declared_edges_and_substrate() -> None:
    """(items 4-5) orthostate + rcl are reached, and the real sqlite substrate is too."""
    result = _run_child(_closure_child)
    assert result["orthostate_present"] is True, "tos.orthostate missing from closure"
    assert result["rcl_present"] is True, "tos.rcl missing from closure"
    assert result["sqlite3_present"] is True, (
        "sqlite3 is NOT in the closure — the durable substrate this package exists for "
        "is not being loaded"
    )


def test_leak_canary_is_detected() -> None:
    """The spawn+scan pipeline catches planted config / evidence / liveauth / numpy leaks."""
    result = _run_child(_leak_canary_child)
    leaked = result["leaked"]
    assert "shared.config" in leaked, "planted shared.config leak was NOT detected"
    assert "tos.evidence" in leaked, "planted tos.evidence leak was NOT detected"
    assert "tos.liveauth" in leaked, "planted tos.liveauth leak was NOT detected"
    assert "numpy" in leaked, "planted numpy leak was NOT detected"


# --------------------------------------------------------------------------
# item 6 — static source scan (TOS-FW-B / TOS-FW-C / TOS-FW-D)
# --------------------------------------------------------------------------


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
