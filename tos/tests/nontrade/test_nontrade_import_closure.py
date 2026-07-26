"""§7.1 import-closure verification for ``tos.nontrade`` — **allowlist** (design #21 §0.3).

Written as an **allowlist**, never a denylist (design #21 §7.1, the #16 M9 lesson): after
importing every ``tos.nontrade`` submodule in a fresh interpreter, the set of top-level
``tos.*`` packages in ``sys.modules`` must be a subset of::

    {tos.canonical, tos.ordering, tos.nontrade}

An enumerated denylist would go stale the moment a new sibling lands (session A is landing
packages while this design was in review); the allowlist is **future-robust** — any
sibling, present or future, fails the assertion simply by appearing.

**Neither ``tos.rcl`` nor ``tos.are`` is in the allowlist.** That is the load-bearing
absence: design #21 §0.4c considered the rcl ``CapacityVector`` and are ``ProjectedCell``
REUSE and **rejected** both, because the Phase-1 decision is set / polarity / idempotency
logic that needs no vector or cell type and a nontrade-local dimension axis would collide
with the are / rcl namespaces. So ``tos.nontrade`` holds **sibling edge 0** and a planted
``tos.rcl`` / ``tos.are`` must fail here. ``tos.iap`` is equally excluded: its
``ConsumptionOutcome.IDEMPOTENT_REPLAY`` is a *different proposition* (authorization-token
consumption, not economic-event application), and importing it would be the phantom edge
design #21 §0.4e blocks.

It also asserts:

  1. no design #1 §2.3 operational package is in the closure (``shared.execution`` / ``kis``
     / ``streaming`` / ``llm`` / ``storage`` / ``backtest``, ``services.*``, ``cli.*``);
  2. neither ``shared.config`` nor ``shared.config.secrets`` is present (the transitive
     ambient-credential intake), nor ``shared.determinism``;
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent (bounds are injected; YAML parsing is the
     harness's concern — design #21 §0.3);
  4. no ``tos.nontrade`` source references ``os.environ`` / ``os.getenv``, a dynamic escape
     (``exec`` / ``eval`` / ``__import__`` / ``importlib``), or a real clock (``time`` /
     ``datetime``) — nontrade is **clock-free** (§8 line 175: clock recovery grants no
     retroactive authority; every boundary and freshness verdict is injected);
  5. no numeric policy literal is hardcoded (§8.0 / CLAUDE.md) — in particular **no split
     ratio**.

A planted-leak canary proves the spawn+scan pipeline catches a leak (including ``tos.rcl``,
``tos.are``, ``tos.venue``, and a *future* sibling name that no denylist could have
anticipated), and a planted-AST-escape canary proves the static scan catches an escape — so
"green" is evidence the checker works, not that it has been neutered.

A **test-only** cross-import of a sibling (the ``test_seam_*`` modules) is not a runtime
package edge and is deliberately not counted here (design #21 §3.4(d)/§7.1).
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

#: The §7.1 allowlist: the only top-level ``tos.*`` packages the closure may contain.
#: Note the absence of ``tos.rcl`` / ``tos.are`` / ``tos.venue`` / ``tos.recon`` /
#: ``tos.iap`` — sibling edge 0 (design #21 §0.4b/§0.4c/§0.4e).
_ALLOWED_TOS_PACKAGES = frozenset(
    {"tos", "tos.canonical", "tos.ordering", "tos.nontrade"}
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

_NONTRADE_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "nontrade"
)

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules that must never be imported by a clock-free source (§8 line 175).
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
    """Child target: import every tos.nontrade submodule; report the closure."""
    import sys

    import tos.nontrade  # noqa: F401
    import tos.nontrade._base  # noqa: F401
    import tos.nontrade.predicates  # noqa: F401
    import tos.nontrade.records  # noqa: F401
    import tos.nontrade.state  # noqa: F401
    import tos.nontrade.vocabulary  # noqa: F401

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

    import tos.nontrade  # noqa: F401

    for planted in (
        "shared.config",
        "numpy",
        "tos.rcl",  # the REJECTED CapacityVector edge (design #21 §0.4c)
        "tos.are",  # the REJECTED ProjectedCell edge (design #21 §0.4c)
        "tos.iap",  # the phantom idempotency edge (design #21 §0.4e)
        "tos.venue",
        "tos.recon",
        "tos.replacement",
        "tos.orthostate",
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


def test_nontrade_tos_closure_is_within_the_allowlist() -> None:
    """(§7.1 allowlist) The tos closure ⊆ {canonical, ordering, nontrade} — edge 0."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert extra == [], (
        "tos.nontrade closure escaped the §7.1 allowlist "
        f"{sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"
    )


def test_nontrade_closure_includes_the_two_core_packages() -> None:
    """(§3.1/§3.2) tos.canonical AND tos.ordering are both genuinely REUSED.

    A package that merely *declared* the ordering REUSE without importing it would pass the
    allowlist trivially; this asserts the REUSE is real.
    """
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in ("tos.canonical", "tos.ordering", "tos.nontrade"):
        assert expected in tops, f"{expected} missing from the tos.nontrade closure"


def test_nontrade_closure_contains_no_sibling_at_all() -> None:
    """(§0.4b/§0.4c/§0.4e sibling edge 0) **No** sibling — notably not rcl / are / iap."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    assert "tos.rcl" not in tops, (
        "tos.rcl reached the nontrade closure — design #21 §0.4c REJECTED the "
        "CapacityVector REUSE (edge-1); the Phase-1 decision needs no vector type"
    )
    assert "tos.are" not in tops, (
        "tos.are reached the nontrade closure — design #21 §0.4c REJECTED the "
        "ProjectedCell REUSE; the aggregate-risk axis is are's coordinate system"
    )
    assert "tos.iap" not in tops, (
        "tos.iap reached the nontrade closure — design #21 §0.4e blocks that phantom "
        "edge: authorization-token consumption is a different proposition"
    )
    for sibling in (
        "tos.venue",
        "tos.recon",
        "tos.orthostate",
        "tos.brokercap",
        "tos.replacement",
        "tos.authority",
        "tos.liveauth",
        "tos.sbr",
        "tos.time",
        "tos.protective",
        "tos.afg",
        "tos.spg",
        "tos.ioc",
        "tos.hag",
        "tos.evidence",
        "tos.capsule",
        "tos.dsl",
    ):
        assert sibling not in tops, f"sibling {sibling} reached the closure (edge != 0)"


def test_nontrade_closure_has_no_forbidden_operational_package() -> None:
    """(§0.3 items 1-3) No shared.* operational package, no services/cli, no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert (
        result["forbidden"] == []
    ), f"forbidden packages reached the closure: {result['forbidden']}"


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted config / numpy / rcl / are / iap / **future**-sibling leaks caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in (
        "tos.rcl",
        "tos.are",
        "tos.iap",
        "tos.venue",
        "tos.recon",
        "tos.replacement",
        "tos.orthostate",
        "tos.some_future_sibling",
    ):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits the three allowed packages and rejects every other sibling."""
    for allowed in (
        "tos.nontrade",
        "tos.nontrade.predicates",
        "tos.canonical",
        "tos.canonical._base",
        "tos.ordering",
        "tos.ordering._ordering",
    ):
        assert _is_allowed_tos_module(allowed) is True
    for sibling in (
        "tos.rcl",
        "tos.are",
        "tos.iap",
        "tos.venue",
        "tos.recon",
        "tos.orthostate",
        "tos.brokercap",
        "tos.replacement",
        "tos.protective",
        "tos.afg",
        "tos.spg",
        "tos.time",
        "tos.ioc",
        "tos.sbr",
        "tos.hag",
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


def test_nontrade_source_has_no_dynamic_escape_ambient_env_or_clock() -> None:
    """(§0.3 item 4) No source uses exec/eval/importlib/os.environ or a real clock."""
    sources = sorted(_NONTRADE_SRC.rglob("*.py"))
    assert sources, f"no tos.nontrade source files found under {_NONTRADE_SRC}"
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


def test_nontrade_source_imports_no_forbidden_sibling_statically() -> None:
    """(§0.3 static mirror) No source contains an ``import tos.<sibling>`` statement."""
    offenders: list[str] = []
    for path in sorted(_NONTRADE_SRC.rglob("*.py")):
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
    assert offenders == [], f"forbidden sibling import in nontrade source: {offenders}"


def test_no_hardcoded_numeric_bound_in_nontrade_source() -> None:
    """(§8.0 / CLAUDE.md) No source hardcodes a ratio / bound / threshold.

    Every bound is an injected ``CanonicalDecimal`` (VP-002 ``B_non_trade_event_detect`` /
    ``B_non_trade_transition_apply`` / ``B_non_trade_reconcile`` are all ``value_ms: null``
    with ``owner: TBD``). The only numeric literals a decision module may contain are the
    structural ``0`` / ``1`` used for emptiness and non-negativity checks — never a policy
    number, and in particular **never a split ratio** (the "2" of a 2-for-1).
    """
    offenders: list[str] = []
    for path in sorted(_NONTRADE_SRC.rglob("*.py")):
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
    assert offenders == [], f"hardcoded numeric bound in nontrade source: {offenders}"


def test_no_broker_is_named_in_the_nontrade_source() -> None:
    """(broker-agnostic) No concrete broker name appears anywhere in the package.

    Broker constraints are expressed as capability classes (the Broker Capability Profile,
    ADR-002-004) and arrive as injected tokens — project memory
    ``tos-spec-broker-agnostic``.
    """
    forbidden_tokens = ("kis", "korea investment", "koreainvestment", "ebest", "kiwoom")
    offenders: list[str] = []
    for path in sorted(_NONTRADE_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{path.name}: {token!r}")
    assert offenders == [], f"a concrete broker is named in the source: {offenders}"
