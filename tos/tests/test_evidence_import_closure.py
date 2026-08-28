"""§7.1 import-closure verification for ``tos.evidence`` + ``tos.canonical``.

Isomorphic to ``test_import_closure.py`` (capsule) but extended to the promoted
substrate and the evidence package (design #4 §7.1). It imports the pure packages
in a **fresh, spawned interpreter** (``subprocess``/``os`` are firewall-forbidden
even in tests) and asserts:

  1. No design §2.3 operational package is in the closure.
  2. Neither ``shared.config`` nor ``shared.config.secrets`` is present (C1 — the
     transitive ambient-credential intake the AST gate cannot catch).
  3. ``numpy``/``pandas`` are absent (design §0.3 closure minimisation).
  4. ``tos.capsule`` is **absent** from the ``tos.evidence`` closure (design #4
     §3.1 layering — evidence must not reach the capsule package).
  5. No evidence/canonical source references ``os.environ`` / ``os.getenv``.

A planted-leak canary proves the spawn+scan pipeline actually catches a leak, so
"green" is evidence the checker works — not that it has been neutered.
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

# Forbidden exact names + dotted prefixes: the §2.3 set + C1 + §0.3 numeric libs +
# the §3.1 capsule-layering exclusion (evidence must not import tos.capsule).
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
        "tos.capsule",
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
    "tos.capsule.",
)

_SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "tos"
_EVIDENCE_SRC = _SRC_ROOT / "evidence"
_CANONICAL_SRC = _SRC_ROOT / "canonical"


def _is_forbidden(module_name: str) -> bool:
    """Whether ``module_name`` is a forbidden closure member (§2.3/C1/§3.1)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import evidence + canonical, report forbidden closure members."""
    import sys

    import tos.canonical  # noqa: F401
    import tos.canonical.canonicalization  # noqa: F401
    import tos.evidence  # noqa: F401
    import tos.evidence.elements  # noqa: F401
    import tos.evidence.envelope  # noqa: F401
    import tos.evidence.gap  # noqa: F401
    import tos.evidence.ledger  # noqa: F401
    import tos.evidence.policy  # noqa: F401
    import tos.evidence.predicates  # noqa: F401
    import tos.evidence.receipt  # noqa: F401
    import tos.evidence.replay  # noqa: F401

    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(leaked)


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant fake forbidden modules, then run the same scan."""
    import sys
    import types

    import tos.evidence  # noqa: F401

    sys.modules["shared.config"] = types.ModuleType("shared.config")
    sys.modules["tos.capsule"] = types.ModuleType("tos.capsule")
    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(leaked)


def _run_child(target) -> list[str]:
    """Spawn ``target`` in a clean interpreter and return its reported leak list."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    proc.join(timeout=60)
    assert proc.exitcode == 0, f"closure child exited abnormally: {proc.exitcode}"
    return queue.get(timeout=5)


def test_evidence_import_closure_has_no_forbidden_packages() -> None:
    """(§7.1 items 1-4) A fresh import of tos.evidence pulls no forbidden package."""
    leaked = _run_child(_closure_child)
    assert leaked == [], f"forbidden packages reached tos.evidence closure: {leaked}"


def test_leak_canary_is_detected() -> None:
    """The spawn+scan pipeline catches planted shared.config + tos.capsule leaks."""
    leaked = _run_child(_leak_canary_child)
    assert "shared.config" in leaked, "planted shared.config leak was NOT detected"
    assert "tos.capsule" in leaked, "planted tos.capsule leak was NOT detected"


def test_is_forbidden_classifier_canaries() -> None:
    """The classifier flags forbidden names (incl. tos.capsule) and clears allowed ones."""
    assert _is_forbidden("shared.config") is True
    assert _is_forbidden("shared.config.secrets") is True
    assert _is_forbidden("shared.llm.market") is True
    assert _is_forbidden("services.dashboard") is True
    assert _is_forbidden("numpy") is True
    assert _is_forbidden("tos.capsule") is True
    assert _is_forbidden("tos.capsule._base") is True
    # Allowed: self substrate, third-party, commons.
    assert _is_forbidden("tos.canonical") is False
    assert _is_forbidden("tos.evidence") is False
    assert _is_forbidden("pydantic") is False
    assert _is_forbidden("shared.utils") is False
    assert _is_forbidden("click") is False  # must not false-match the "cli" prefix


def test_evidence_source_has_no_ambient_env_access() -> None:
    """(§7.1 item 5) No evidence/canonical module references os.environ / os.getenv."""
    offenders: list[str] = []
    for root in (_EVIDENCE_SRC, _CANONICAL_SRC):
        for path in sorted(root.rglob("*.py")):
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
