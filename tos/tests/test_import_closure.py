"""§7.1 import-closure verification test (C1 enforcement, design v2).

C1 (the v1 REJECT CRITICAL) slipped through a firewall blind spot precisely
because no test asserted the *runtime* import closure. Isomorphic to design #1
§3.4's determinism closure test, this test imports the pure model package in a
**fresh, isolated interpreter** (via ``multiprocessing`` spawn — ``subprocess``
and ``os`` are firewall-forbidden even in tests) and asserts:

  1. No design §2.3 operational package (``shared.execution``/``shared.kis``/
     ``shared.streaming``/``shared.llm``/``shared.storage``/``shared.backtest``/
     ``services.*``/``cli.*``) is in the closure.
  2. Neither ``shared.config`` nor ``shared.config.secrets`` is in the closure
     (C1 direct hit — the transitive ambient-credential intake the AST gate,
     seeing only literal top-level imports, cannot catch).
  3. ``numpy``/``pandas`` are absent too: design §0.3 forbids the pure model from
     importing them (closure minimisation), so their presence would be a
     regression even though the firewall allowlist tolerates them (MINOR-1).
  4. Even if ``os`` is loaded, no model source references ``os.environ`` /
     ``os.getenv`` (AST scan reinforcement; ambient-credential-reader absence).

Spawn gives a clean interpreter so the parent pytest process's pre-existing
imports cannot mask a real leak. A negative canary (``test_leak_canary_is_
detected``) proves the spawn+scan pipeline actually *catches* a planted leak, so
"green" is evidence the checker works — not evidence it has been neutered.
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

# Forbidden top-level package names (exact) and dotted prefixes (design §2.3 + C1
# + §0.3 numpy/pandas closure-minimisation, MINOR-1).
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
    """Child target: import the pure package, report any forbidden closure members.

    Runs in a spawned (clean) interpreter. Imports every capsule submodule and
    scans ``sys.modules`` for forbidden packages, returning the sorted leak list.
    """
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
    """Child target: plant a fake forbidden module, then run the same scan.

    Proves the spawn+scan pipeline actually detects a leak — if the scanner were
    silently neutered, this would return an empty list and the canary test would
    fail (MINOR-6).
    """
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
    return queue.get(timeout=5)


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
    # Positive: forbidden exacts, dotted children, and §0.3 numeric libs.
    assert _is_forbidden("shared.llm") is True
    assert _is_forbidden("shared.llm.market") is True
    assert _is_forbidden("shared.config") is True
    assert _is_forbidden("shared.config.secrets") is True
    assert _is_forbidden("services") is True
    assert _is_forbidden("services.dashboard") is True
    assert _is_forbidden("cli") is True
    assert _is_forbidden("numpy") is True
    assert _is_forbidden("pandas.core") is True
    # Negative: the allowlisted commons/third-party/self must NOT be flagged.
    assert _is_forbidden("shared.utils") is False
    assert _is_forbidden("shared.exceptions") is False
    assert _is_forbidden("pydantic") is False
    assert _is_forbidden("tos.capsule") is False
    assert _is_forbidden("click") is False  # must not false-match the "cli" prefix


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
