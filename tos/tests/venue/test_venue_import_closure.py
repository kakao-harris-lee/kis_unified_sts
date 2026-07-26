"""§7.1 import-closure verification for ``tos.venue`` — **allowlist** form (design #19 §0.3).

Written as an **allowlist** (design #19 §7.1): after importing every ``tos.venue`` submodule in
a fresh interpreter, the set of top-level ``tos.*`` packages in ``sys.modules`` must be a subset
of::

    {tos, tos.canonical, tos.ordering, tos.venue}

An enumerated denylist would go stale the moment a new sibling lands; the allowlist is
**future-robust** — any sibling, present or future (``tos.pr`` etc.), fails the assertion simply
by appearing. **sibling edge 0** — venue has **no** sanctioned sibling edge, so its allowlist
admits only the two core packages.

It also asserts (design #19 §0.3):

  1. no operational package is in the closure (``shared.execution`` / ``kis`` / ``streaming`` /
     ``llm`` / ``storage`` / ``backtest``, ``services.*``, ``cli.*``);
  2. neither ``shared.config`` nor ``shared.config.secrets`` is present (transitive ambient-
     credential intake), nor ``shared.determinism``;
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent (bounds are injected; YAML is the harness's);
  4. no ``tos.venue`` source references ``os.environ`` / ``os.getenv``, a dynamic escape
     (``exec`` / ``eval`` / ``__import__`` / ``importlib``), or a real clock (``time`` /
     ``datetime``) — venue is **clock-free** (§8);
  5. the sibling-absence assertion **includes ``tos.iap`` and ``tos.sbr``** (the
     ``invalidation_closure`` / ``_reachability_closure`` isomorph is re-authored locally, NOT
     imported — §0.4d) and **``tos.dsl``** (the ``AdmissibilityResult`` homonym is NOT reused —
     §0.4d).

A planted-leak canary (including ``tos.iap``, ``tos.dsl``, a *future* sibling ``tos.pr``, and
``shared.config``) proves the spawn+scan pipeline catches a leak no denylist could have
anticipated, and a planted-AST-escape canary proves the static scan catches an escape — so
"green" is evidence the checker works, not that it has been neutered.
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

#: The §7.1 allowlist: the only top-level ``tos.*`` packages the venue closure may contain.
_ALLOWED_TOS_PACKAGES = frozenset({"tos", "tos.canonical", "tos.ordering", "tos.venue"})

#: The forbidden siblings (all real siblings + a future ``tos.pr``) — INCLUDING ``tos.iap`` /
#: ``tos.sbr`` (closure isomorph re-authored locally, §0.4d) and ``tos.dsl`` (AdmissibilityResult
#: homonym NOT reused, §0.4d). Asserted absent by the classifier canary below.
_FORBIDDEN_SIBLINGS = frozenset(
    {
        "tos.afg",
        "tos.are",
        "tos.authority",
        "tos.brokercap",
        "tos.capsule",
        "tos.dsl",
        "tos.evidence",
        "tos.iap",
        "tos.ioc",
        "tos.liveauth",
        "tos.orthostate",
        "tos.protective",
        "tos.rcl",
        "tos.recon",
        "tos.sbr",
        "tos.spg",
        "tos.time",
        "tos.pr",  # a *future* sibling (session B) — the allowlist excludes it by construction
    }
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

_VENUE_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "venue"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules that must never be imported by a clock-free venue source (§8).
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
    """Child target: import every tos.venue submodule; report the tos + forbidden closure."""
    import sys

    import tos.venue  # noqa: F401
    import tos.venue._base  # noqa: F401
    import tos.venue.predicates  # noqa: F401
    import tos.venue.records  # noqa: F401
    import tos.venue.state  # noqa: F401
    import tos.venue.vocabulary  # noqa: F401

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

    import tos.venue  # noqa: F401

    for planted in (
        "shared.config",
        "numpy",
        "tos.iap",  # the invalidation_closure isomorph is re-authored, not imported
        "tos.sbr",  # the _reachability_closure isomorph is re-authored, not imported
        "tos.dsl",  # the AdmissibilityResult homonym is NOT reused
        "tos.pr",  # a *future* sibling (session B) the allowlist catches
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


def test_venue_tos_closure_is_within_the_allowlist() -> None:
    """(§7.1 allowlist) The tos closure ⊆ {canonical, ordering, venue} — no sibling leaks (edge 0)."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert (
        extra == []
    ), f"tos.venue closure escaped the §7.1 allowlist {sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"


def test_venue_closure_includes_only_the_two_core_packages() -> None:
    """(§7.1) tos.canonical + tos.ordering ARE present; NO sibling edge."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in ("tos.canonical", "tos.ordering", "tos.venue"):
        assert expected in tops, f"{expected} missing from the tos.venue closure"
    for sibling in _FORBIDDEN_SIBLINGS:
        assert sibling not in tops, f"{sibling} leaked into the tos.venue closure"


def test_venue_closure_has_no_forbidden_operational_package() -> None:
    """(§0.3 items 1-3) No shared.* operational package, no services/cli, no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert (
        result["forbidden"] == []
    ), f"forbidden packages reached the tos.venue closure: {result['forbidden']}"


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted config / numpy / iap / sbr / dsl / future-sibling leaks are all caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in ("tos.iap", "tos.sbr", "tos.dsl", "tos.pr"):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits the three allowed packages and rejects every sibling (incl. iap / dsl)."""
    for allowed in (
        "tos.venue",
        "tos.venue.predicates",
        "tos.canonical",
        "tos.canonical._base",
        "tos.ordering",
    ):
        assert _is_allowed_tos_module(allowed) is True
    for sibling in _FORBIDDEN_SIBLINGS | {"tos.not_yet_invented"}:
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


def test_venue_source_has_no_dynamic_escape_ambient_env_or_clock() -> None:
    """(§0.3 item 4) No tos.venue source uses exec/eval/importlib/os.environ or a real clock."""
    sources = sorted(_VENUE_SRC.rglob("*.py"))
    assert sources, f"no tos.venue source files found under {_VENUE_SRC}"
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


def test_venue_source_imports_no_forbidden_sibling_statically() -> None:
    """(§0.3 static mirror) No venue source contains an ``import tos.<sibling>`` statement."""
    offenders: list[str] = []
    for path in sorted(_VENUE_SRC.rglob("*.py")):
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
    assert offenders == [], f"forbidden sibling import in venue source: {offenders}"
