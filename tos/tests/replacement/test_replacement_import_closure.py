"""§7.1 import-closure verification for ``tos.replacement`` — **allowlist** (design #18 §0.3).

Written as an **allowlist**, never a denylist (design #18 §7.1, the #16 M9 lesson): after
importing every ``tos.replacement`` submodule in a fresh interpreter, the set of top-level
``tos.*`` packages in ``sys.modules`` must be a subset of::

    {tos.canonical, tos.ordering, tos.replacement}

An enumerated denylist would go stale the moment a new sibling lands (session A added
``tos.sbr`` and is adding a venue package while this design was in review); the allowlist
is **future-robust** — any sibling, present or future, fails the assertion simply by
appearing.

**``tos.rcl`` is NOT in the allowlist.** That is the load-bearing difference from the afg
closure test: design #18 §0.4c considered the ``CapacityVector`` REUSE (which would have
been the seventh ``* -> rcl`` sibling edge) and **rejected** it, because the Phase-1
decision is set / polarity / magnitude logic that needs no vector type, and a
replacement-local dimension axis would collide with the rcl / are namespaces. So
``tos.replacement`` holds **sibling edge 0** and a planted ``tos.rcl`` must fail here.

It also asserts:

  1. no design #1 §2.3 operational package is in the closure (``shared.execution`` / ``kis``
     / ``streaming`` / ``llm`` / ``storage`` / ``backtest``, ``services.*``, ``cli.*``);
  2. neither ``shared.config`` nor ``shared.config.secrets`` is present (the transitive
     ambient-credential intake), nor ``shared.determinism``;
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent (bounds are injected; YAML parsing is the
     harness's concern — design #18 §0.3);
  4. no ``tos.replacement`` source references ``os.environ`` / ``os.getenv``, a dynamic
     escape (``exec`` / ``eval`` / ``__import__`` / ``importlib``), or a real clock
     (``time`` / ``datetime``) — replacement is **clock-free** (§3.2: "wall clock does not
     create order"; §15 line 349 every measured duration uses ADR-002-008 trustworthy time,
     injected).

A planted-leak canary proves the spawn+scan pipeline catches a leak (including ``tos.rcl``
and a *future* sibling name that no denylist could have anticipated), and a planted-AST-
escape canary proves the static scan catches an escape — so "green" is evidence the checker
works, not that it has been neutered.

A **test-only** cross-import of a sibling (the ``test_seam_*`` modules) is not a runtime
package edge and is deliberately not counted here (design #18 §3.4(d)/§7.1).
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

#: The §7.1 allowlist: the only top-level ``tos.*`` packages the closure may contain.
#: Note the absence of ``tos.rcl`` — sibling edge 0 (design #18 §0.4b/§0.4c).
_ALLOWED_TOS_PACKAGES = frozenset(
    {"tos", "tos.canonical", "tos.ordering", "tos.replacement"}
)

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
)

_REPLACEMENT_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "replacement"
)

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules that must never be imported by a clock-free source (§3.2).
_CLOCK_MODULES = frozenset({"time", "datetime"})


def _tos_top_level(module_name: str) -> str | None:
    """The ``tos.<pkg>`` top-level package of ``module_name`` (``None`` if not a tos module)."""
    if module_name != "tos" and not module_name.startswith("tos."):
        return None
    parts = module_name.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else "tos"


def _is_allowed_tos_module(module_name: str) -> bool:
    """Whether a ``tos.*`` module is inside the §7.1 allowlist."""
    top = _tos_top_level(module_name)
    return top is None or top in _ALLOWED_TOS_PACKAGES


def _is_forbidden_non_tos(module_name: str) -> bool:
    """Whether a non-``tos`` module is a forbidden closure member (§0.3)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every tos.replacement submodule; report the closure."""
    import sys

    import tos.replacement  # noqa: F401
    import tos.replacement._base  # noqa: F401
    import tos.replacement.predicates  # noqa: F401
    import tos.replacement.records  # noqa: F401
    import tos.replacement.state  # noqa: F401
    import tos.replacement.vocabulary  # noqa: F401

    tos_tops = sorted(
        {top for name in sys.modules if (top := _tos_top_level(name)) is not None}
    )
    queue.put(
        {
            "tos_tops": tos_tops,
            "forbidden": sorted(
                name for name in sys.modules if _is_forbidden_non_tos(name)
            ),
        }
    )


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant fake forbidden + *future* sibling modules, then run the scan."""
    import sys
    import types

    import tos.replacement  # noqa: F401

    for planted in (
        "shared.config",
        "numpy",
        "tos.rcl",  # the REJECTED edge (design #18 §0.4c) — must be caught
        "tos.protective",
        "tos.afg",
        "tos.orthostate",
        "tos.brokercap",
        "tos.some_future_sibling",  # the allowlist catches names no denylist knew
    ):
        sys.modules[planted] = types.ModuleType(planted)

    tos_tops = sorted(
        {top for name in sys.modules if (top := _tos_top_level(name)) is not None}
    )
    queue.put(
        {
            "tos_tops": tos_tops,
            "forbidden": sorted(
                name for name in sys.modules if _is_forbidden_non_tos(name)
            ),
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


def test_replacement_tos_closure_is_within_the_allowlist() -> None:
    """(§7.1 allowlist) The tos closure ⊆ {canonical, ordering, replacement} — edge 0."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert extra == [], (
        "tos.replacement closure escaped the §7.1 allowlist "
        f"{sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"
    )


def test_replacement_closure_includes_the_two_core_packages() -> None:
    """(§3.1/§3.2) tos.canonical AND tos.ordering are both genuinely REUSED."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in ("tos.canonical", "tos.ordering", "tos.replacement"):
        assert expected in tops, f"{expected} missing from the tos.replacement closure"


def test_replacement_closure_contains_no_sibling_at_all() -> None:
    """(§0.4b/§0.4c sibling edge 0) **No** sibling — in particular **not** ``tos.rcl``."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    # The rejected CapacityVector REUSE would have shown up exactly here.
    assert "tos.rcl" not in tops, (
        "tos.rcl reached the replacement closure — design #18 §0.4c REJECTED the "
        "CapacityVector REUSE (edge-1); the Phase-1 decision needs no vector type"
    )
    for sibling in (
        "tos.protective",
        "tos.afg",
        "tos.are",
        "tos.brokercap",
        "tos.orthostate",
        "tos.authority",
        "tos.recon",
        "tos.evidence",
    ):
        assert sibling not in tops, f"sibling {sibling} reached the closure (edge != 0)"


def test_replacement_closure_has_no_forbidden_operational_package() -> None:
    """(§0.3 items 1-3) No shared.* operational package, no services/cli, no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert (
        result["forbidden"] == []
    ), f"forbidden packages reached the closure: {result['forbidden']}"


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted config / numpy / rcl / sibling / **future**-sibling leaks caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in (
        "tos.rcl",
        "tos.protective",
        "tos.afg",
        "tos.orthostate",
        "tos.brokercap",
        "tos.some_future_sibling",
    ):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits the three allowed packages and rejects every other sibling."""
    for allowed in (
        "tos.replacement",
        "tos.replacement.predicates",
        "tos.canonical",
        "tos.canonical._base",
        "tos.ordering",
        "tos.ordering._ordering",
    ):
        assert _is_allowed_tos_module(allowed) is True
    for sibling in (
        "tos.rcl",
        "tos.protective",
        "tos.afg",
        "tos.spg",
        "tos.orthostate",
        "tos.brokercap",
        "tos.time",
        "tos.recon",
        "tos.are",
        "tos.ioc",
        "tos.iap",
        "tos.sbr",
        "tos.liveauth",
        "tos.authority",
        "tos.capsule",
        "tos.evidence",
        "tos.dsl",
        "tos.not_yet_invented",
    ):
        assert _is_allowed_tos_module(sibling) is False
        assert _is_allowed_tos_module(sibling + ".predicates") is False
    # non-tos classification
    assert _is_forbidden_non_tos("shared.config") is True
    assert _is_forbidden_non_tos("shared.config.secrets") is True
    assert _is_forbidden_non_tos("shared.determinism") is True
    assert _is_forbidden_non_tos("services.dashboard") is True
    assert _is_forbidden_non_tos("numpy") is True
    assert _is_forbidden_non_tos("pandas.core") is True
    assert _is_forbidden_non_tos("yaml") is True
    assert _is_forbidden_non_tos("pydantic") is False
    assert _is_forbidden_non_tos("decimal") is False
    assert _is_forbidden_non_tos("click") is False  # must not false-match "cli"


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


def test_replacement_source_has_no_dynamic_escape_ambient_env_or_clock() -> None:
    """(§0.3 item 4) No source uses exec/eval/importlib/os.environ or a real clock."""
    sources = sorted(_REPLACEMENT_SRC.rglob("*.py"))
    assert sources, f"no tos.replacement source files found under {_REPLACEMENT_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_escape_offenders(path))
    assert (
        offenders == []
    ), f"dynamic-escape / ambient-env / clock access found: {offenders}"


def test_ast_scan_detects_planted_escape(tmp_path: Path) -> None:
    """The AST escape scan actually catches planted escapes + a real-clock import."""
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


def test_replacement_source_imports_no_forbidden_sibling_statically() -> None:
    """(§0.3 static mirror) No source contains an ``import tos.<sibling>`` statement."""
    offenders: list[str] = []
    for path in sorted(_REPLACEMENT_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if not _is_allowed_tos_module(name):
                    offenders.append(f"{path.name}:{node.lineno} import {name}")
    assert (
        offenders == []
    ), f"forbidden sibling import in replacement source: {offenders}"


def test_no_hardcoded_numeric_bound_in_replacement_source() -> None:
    """(§8 / CLAUDE.md) No source hardcodes a gap / overlap / timing / risk magnitude.

    Every bound is an injected ``CanonicalDecimal`` (ADR §15 line 353 "Numeric values
    remain unapproved until human approval and executed evidence are recorded"). The only
    numeric literals a decision module may contain are the structural ``0`` / ``1`` used
    for emptiness and non-negativity checks — never a policy number.
    """
    offenders: list[str] = []
    for path in sorted(_REPLACEMENT_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                if isinstance(node.value, bool):
                    continue
                if node.value in (0, 1):
                    continue
                offenders.append(
                    f"{path.name}:{node.lineno} numeric literal {node.value!r}"
                )
    assert (
        offenders == []
    ), f"hardcoded numeric bound in replacement source: {offenders}"
