"""§7.1 import-closure verification for ``tos.time`` + ``tos.ordering``.

Isomorphic to ``test_evidence_import_closure.py`` (design #4) but extended to the
Trustworthy Time package and the promoted ordering core. It imports the pure
packages in a **fresh, spawned interpreter** (``subprocess``/``os`` are firewall-
forbidden even in tests) and asserts (time design §7.1):

  1. No design §2.3 operational package is in the closure.
  2. Neither ``shared.config`` nor ``shared.config.secrets`` is present (C1 — the
     transitive ambient-credential intake the AST gate cannot catch).
  3. ``shared.determinism`` is absent (gap-6 decision: it pulls pandas / is not a
     clock-health primitive).
  4. ``numpy``/``pandas`` are absent (time design §0.3 closure minimisation).
  5. ``tos.capsule`` AND ``tos.evidence`` are absent (time design §5 layering —
     time is a sibling, not a consumer, of those; ordering comes only from the
     dedicated ``tos.ordering`` core).
  6. No ``tos.time`` / ``tos.ordering`` source references ``os.environ`` /
     ``os.getenv``, imports the stdlib ``time`` / ``datetime`` clock modules, or
     calls a real clock (``.now`` / ``.utcnow`` / ``.monotonic`` / ``.time`` /
     ``.perf_counter``) — the "no real clock read" invariant (time design §0.3/§3).

A planted-leak canary proves the spawn+scan pipeline actually catches a leak, so
"green" is evidence the checker works — not that it has been neutered.
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

# §2.3 operational set + C1 + gap-6 shared.determinism + §0.3 numeric libs +
# §5 sibling-layering exclusions (time must not import capsule OR evidence).
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
    "tos.capsule.",
    "tos.evidence.",
)

_SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "tos"
_TIME_SRC = _SRC_ROOT / "time"
_ORDERING_SRC = _SRC_ROOT / "ordering"

#: stdlib clock modules a pure, clock-free time model must never import.
_CLOCK_MODULES = frozenset({"time", "datetime"})
#: clock-read method names a pure, clock-free time model must never call.
_CLOCK_METHODS = frozenset(
    {
        "now",
        "utcnow",
        "monotonic",
        "monotonic_ns",
        "time",
        "perf_counter",
        "perf_counter_ns",
    }
)


def _is_forbidden(module_name: str) -> bool:
    """Whether ``module_name`` is a forbidden closure member (§7.1)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import time + ordering, report forbidden closure members."""
    import sys

    import tos.canonical  # noqa: F401
    import tos.ordering  # noqa: F401
    import tos.time  # noqa: F401
    import tos.time.domains  # noqa: F401
    import tos.time.elements  # noqa: F401
    import tos.time.ordering  # noqa: F401
    import tos.time.predicates  # noqa: F401
    import tos.time.snapshot  # noqa: F401

    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(leaked)


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant fake forbidden modules, then run the same scan."""
    import sys
    import types

    import tos.time  # noqa: F401

    sys.modules["shared.config"] = types.ModuleType("shared.config")
    sys.modules["tos.evidence"] = types.ModuleType("tos.evidence")
    sys.modules["tos.capsule"] = types.ModuleType("tos.capsule")
    sys.modules["numpy"] = types.ModuleType("numpy")
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


def test_time_import_closure_has_no_forbidden_packages() -> None:
    """(§7.1 items 1-5) A fresh import of tos.time pulls no forbidden package."""
    leaked = _run_child(_closure_child)
    assert leaked == [], f"forbidden packages reached tos.time closure: {leaked}"


def test_leak_canary_is_detected() -> None:
    """The spawn+scan pipeline catches planted shared.config / evidence / capsule / numpy."""
    leaked = _run_child(_leak_canary_child)
    for planted in ("shared.config", "tos.evidence", "tos.capsule", "numpy"):
        assert planted in leaked, f"planted {planted} leak was NOT detected"


def test_is_forbidden_classifier_canaries() -> None:
    """The classifier flags forbidden names (incl. evidence/capsule) and clears allowed ones."""
    assert _is_forbidden("shared.config") is True
    assert _is_forbidden("shared.config.secrets") is True
    assert _is_forbidden("shared.determinism") is True
    assert _is_forbidden("numpy") is True
    assert _is_forbidden("tos.capsule") is True
    assert _is_forbidden("tos.evidence") is True
    assert _is_forbidden("tos.evidence.predicates") is True
    # Allowed: self substrate, promoted ordering core, third-party, commons.
    assert _is_forbidden("tos.canonical") is False
    assert _is_forbidden("tos.ordering") is False
    assert _is_forbidden("tos.time") is False
    assert _is_forbidden("pydantic") is False
    assert _is_forbidden("shared.utils") is False
    assert _is_forbidden("click") is False  # must not false-match the "cli" prefix


def _iter_source_files():
    for root in (_TIME_SRC, _ORDERING_SRC):
        yield from sorted(root.rglob("*.py"))


def test_time_source_has_no_ambient_env_access() -> None:
    """(§7.1 item 6a) No time/ordering module references os.environ / os.getenv."""
    offenders: list[str] = []
    for path in _iter_source_files():
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


def test_time_source_reads_no_real_clock() -> None:
    """(§7.1 item 6b) No time/ordering module imports a clock module or reads a clock."""
    offenders: list[str] = []
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            # Stdlib clock-module imports (``import time``/``import datetime``,
            # even aliased). ``tos.time`` is NOT stdlib ``time`` (prefix "tos.").
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name in _CLOCK_MODULES or name.startswith(
                        tuple(f"{m}." for m in _CLOCK_MODULES)
                    ):
                        offenders.append(f"{path.name}:{node.lineno} import {name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module in _CLOCK_MODULES:
                    offenders.append(
                        f"{path.name}:{node.lineno} from {node.module} import ..."
                    )
            # Clock-read method calls (defense-in-depth for aliased access).
            elif isinstance(node, ast.Attribute) and node.attr in _CLOCK_METHODS:
                if isinstance(node.value, ast.Name) and node.value.id in {
                    "time",
                    "datetime",
                    "dt",
                }:
                    offenders.append(
                        f"{path.name}:{node.lineno} {node.value.id}.{node.attr}"
                    )
    assert offenders == [], f"real clock read found: {offenders}"


def test_clock_scan_canary_detects_a_planted_clock_read() -> None:
    """The clock scanner actually fires on a planted ``import time`` / ``time.monotonic()``."""
    planted = "import time\nx = time.monotonic()\n"
    tree = ast.parse(planted)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _CLOCK_MODULES:
                    hits.append(f"import {alias.name}")
        elif (
            isinstance(node, ast.Attribute)
            and node.attr in _CLOCK_METHODS
            and isinstance(node.value, ast.Name)
            and node.value.id in {"time", "datetime", "dt"}
        ):
            hits.append(f"{node.value.id}.{node.attr}")
    assert "import time" in hits and "time.monotonic" in hits
