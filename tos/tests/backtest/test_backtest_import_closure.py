"""§9 — import-closure + determinism canaries for ``tos.backtest`` (design #33 §0.3/§4.4/§9).

``tos.backtest`` is a **consumer of the D-E1 integrator**, so design #33 §0.3 states its closure as a
relation rather than a fresh list: it must be a subset of ``tos.engine``'s closure **plus itself**.
Two assertions therefore carry different weight:

* **the runtime closure** (this file's ``_ALLOWED_TOS_PACKAGES``) is the engine's fourteen plus
  ``tos.backtest`` — importing the integrator legitimately pulls in what the integrator assembles,
  and adding a *new* top-level package beyond that would be a real breach;
* **the direct-import surface** is the narrower §0.3 list —
  ``{tos, tos.canonical, tos.ordering, tos.time, tos.dsl, tos.capsule, tos.rcl, tos.engine,
  tos.backtest}`` — because that is what the harness itself may name. ``are`` / ``afg`` / ``ioc`` /
  ``venue`` / ``cur`` are reached only through the engine's stand-ins and adapters, never re-authored
  or re-imported here (design #33 §0.3).

The two packages kept **outside** carry the most weight: ``tos.egress`` (the QCC kernel) and
``tos.brokercap`` live beyond the D-E4 send-boundary injection point, and the harness reaches the
send boundary only through the injected ``Transmit`` interface (design #33 §0.3/§7.5).

Beyond the closure, an AST scan of the shipped sources asserts (design #33 §4.4/§9):

  1. no operational package (``shared.*``, ``services.*``, ``cli.*``) and no ``numpy`` / ``pandas`` /
     ``yaml`` — bar loading is out-of-tree precisely so this stays true (§3.1);
  2. no ``os.environ`` / ``os.getenv``;
  3. no dynamic escape — ``exec`` / ``eval`` / ``compile`` / ``__import__`` / ``importlib``;
  4. no network stdlib — the fill model is a synthetic band, not a sender (RFC-002 §10.8:763);
  5. **no wall clock** — the harness's time is the coordinate the bar carries (§3.3);
  6. **no RNG or nonce source** — ``random`` / ``secrets`` / ``uuid`` / the seed-randomized builtin
     ``hash``. This is what keeps a replay byte-identical: introducing ``uuid4()`` or a timestamp
     into a fill would destroy replay identity (RFC-003 §10:360-363), and this canary detects it.

Planted-leak and planted-escape canaries prove the checks actually catch what they claim, so "green"
is evidence the checker works rather than evidence it was neutered.

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

import tos.backtest
import tos.backtest._base
import tos.backtest.bars
import tos.backtest.converter
import tos.backtest.driver
import tos.backtest.fills
import tos.backtest.records
import tos.backtest.resolver
import tos.backtest.results
import tos.backtest.scenarios
import tos.backtest.vocabulary

#: The runtime closure allowlist: the ``tos.engine`` closure (design #31 §0.3) **plus** the harness
#: itself. A subset relation, exactly as design #33 §0.3 states it.
_ALLOWED_TOS_PACKAGES = frozenset(
    {
        "tos",
        "tos.canonical",
        "tos.ordering",
        "tos.dsl",
        "tos.capsule",
        "tos.time",
        "tos.evidence",
        "tos.ioc",
        "tos.venue",
        "tos.rcl",
        "tos.are",
        "tos.afg",
        "tos.cur",
        "tos.engine",
        "tos.backtest",
    }
)

#: The narrower set design #33 §0.3 lets the harness **name directly**. The sibling stage bands are
#: reached through ``tos.engine.standins`` / ``tos.engine.adapters``, never re-imported here.
_ALLOWED_DIRECT_IMPORTS = frozenset(
    {
        "tos",
        "tos.canonical",
        "tos.ordering",
        "tos.time",
        "tos.dsl",
        "tos.capsule",
        "tos.rcl",
        "tos.engine",
        "tos.backtest",
    }
)

#: Siblings deliberately kept outside the closure, plus a future one.
_FORBIDDEN_SIBLINGS = frozenset(
    {
        "tos.authority",
        "tos.brokercap",  # D-E4 edge — beyond the send-boundary injection point (§7.5)
        "tos.egress",  # the QCC kernel — never encroached upon (§0.3/§7.5)
        "tos.egressgw",  # D-E4's future send boundary — excluded by construction
        "tos.failuredomain",
        "tos.hag",
        "tos.iap",
        "tos.liveauth",
        "tos.nontrade",
        "tos.orthostate",
        "tos.posttrade",
        "tos.protective",
        "tos.recon",
        "tos.replacement",
        "tos.rlp",
        "tos.sbr",
        "tos.sci",
        "tos.sir",
        "tos.spg",
        "tos.stm",
        "tos.wdr",
        "tos.brokeradapter",
        "tos.future_sibling",
    }
)

_FORBIDDEN_EXACT = frozenset(
    {
        "shared.execution",
        "shared.kis",
        "shared.streaming",
        "shared.llm",
        "shared.storage",
        "shared.backtest",  # the differential oracle's *other* side — compared, never imported (§6.1)
        "shared.config",
        "shared.config.secrets",
        "shared.determinism",
        "services",
        "cli",
        "numpy",
        "pandas",
        "yaml",
        "vectorbt",
    }
)
#: ``socket`` / ``ssl`` / ``asyncio`` are deliberately **absent** from the closure denylist: the
#: allowed third party ``pydantic`` pulls them into ``sys.modules`` on its own, so a
#: closure-membership assertion about them would measure pydantic, not the harness. The accurate
#: mechanism is the AST source scan below.
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
    "vectorbt.",
)

_BACKTEST_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "backtest"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "compile", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules the harness must never import (design #33 §3.3).
_CLOCK_MODULES = frozenset({"time", "datetime"})
#: Nondeterministic identity / nonce sources (design #33 §4.4).
_RNG_MODULES = frozenset({"random", "secrets", "uuid"})
#: Network / process stdlib.
_NETWORK_MODULES = frozenset(
    {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "asyncio", "subprocess", "ctypes"}
)
#: Wall-clock / RNG call names that would be nondeterministic even without a module import.
_NONDETERMINISTIC_CALLS = frozenset(
    {
        "monotonic",
        "perf_counter",
        "perf_counter_ns",
        "time_ns",
        "now",
        "utcnow",
        "today",
        "uuid1",
        "uuid3",
        "uuid4",
        "uuid5",
        "getrandbits",
        "randrange",
        "shuffle",
        "sample",
        "token_hex",
        "token_bytes",
        "token_urlsafe",
    }
)
#: The seed-randomized builtin. Using it for any identity would break cross-process reproduction.
_FORBIDDEN_BUILTIN_CALLS = frozenset({"hash", "id"})

_BACKTEST_SUBMODULES = (
    "tos.backtest",
    "tos.backtest._base",
    "tos.backtest.bars",
    "tos.backtest.converter",
    "tos.backtest.driver",
    "tos.backtest.fills",
    "tos.backtest.records",
    "tos.backtest.resolver",
    "tos.backtest.results",
    "tos.backtest.scenarios",
    "tos.backtest.vocabulary",
)

#: Every shipped submodule, imported **statically** (the firewall forbids ``import_module``).
_LOADED_SUBMODULES = {
    "tos.backtest": tos.backtest,
    "tos.backtest._base": tos.backtest._base,
    "tos.backtest.bars": tos.backtest.bars,
    "tos.backtest.converter": tos.backtest.converter,
    "tos.backtest.driver": tos.backtest.driver,
    "tos.backtest.fills": tos.backtest.fills,
    "tos.backtest.records": tos.backtest.records,
    "tos.backtest.resolver": tos.backtest.resolver,
    "tos.backtest.results": tos.backtest.results,
    "tos.backtest.scenarios": tos.backtest.scenarios,
    "tos.backtest.vocabulary": tos.backtest.vocabulary,
}


def _tos_top_level(module_name: str) -> str | None:
    """The ``tos.<pkg>`` top-level package of ``module_name`` (``None`` if not a tos module)."""
    if module_name != "tos" and not module_name.startswith("tos."):
        return None
    parts = module_name.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else "tos"


def _is_allowed_tos_module(module_name: str) -> bool:
    """Whether a ``tos.*`` module is inside the runtime closure allowlist."""
    top = _tos_top_level(module_name)
    return top is None or top in _ALLOWED_TOS_PACKAGES


def _is_allowed_direct_import(module_name: str) -> bool:
    """Whether a ``tos.*`` module may be **named directly** by a harness source (§0.3)."""
    top = _tos_top_level(module_name)
    return top is None or top in _ALLOWED_DIRECT_IMPORTS


def _is_forbidden_non_tos(module_name: str) -> bool:
    """Whether a non-``tos`` module is a forbidden closure member (design #33 §0.3)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every harness submodule; report the tos + forbidden closure."""
    import sys

    import tos.backtest  # noqa: F401
    import tos.backtest._base  # noqa: F401
    import tos.backtest.bars  # noqa: F401
    import tos.backtest.converter  # noqa: F401
    import tos.backtest.driver  # noqa: F401
    import tos.backtest.fills  # noqa: F401
    import tos.backtest.records  # noqa: F401
    import tos.backtest.resolver  # noqa: F401
    import tos.backtest.results  # noqa: F401
    import tos.backtest.scenarios  # noqa: F401
    import tos.backtest.vocabulary  # noqa: F401

    tos_tops = sorted(
        {top for name in sys.modules if (top := _tos_top_level(name)) is not None}
    )
    queue.put(
        {
            "tos_tops": tos_tops,
            "forbidden": sorted(name for name in sys.modules if _is_forbidden_non_tos(name)),
        }
    )


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant fake forbidden + *future* sibling modules, then run the scan."""
    import sys
    import types

    import tos.backtest  # noqa: F401

    for planted in (
        "shared.backtest",
        "shared.execution",
        "numpy",
        "pandas",
        "vectorbt",
        "tos.egress",
        "tos.brokercap",
        "tos.egressgw",
        "tos.future_sibling",
    ):
        sys.modules[planted] = types.ModuleType(planted)

    tos_tops = sorted(
        {top for name in sys.modules if (top := _tos_top_level(name)) is not None}
    )
    queue.put(
        {
            "tos_tops": tos_tops,
            "forbidden": sorted(name for name in sys.modules if _is_forbidden_non_tos(name)),
        }
    )


def _run_child(target) -> dict:  # noqa: ANN001 - a multiprocessing target callable
    """Spawn ``target`` in a clean interpreter and return its reported result dict."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    result = queue.get(timeout=120)
    proc.join(timeout=120)
    assert proc.exitcode == 0, f"closure child exited abnormally: {proc.exitcode}"
    return result


def test_backtest_closure_is_a_subset_of_the_engine_closure_plus_itself() -> None:
    """(§0.3) The relation the design states: ⊆ ``tos.engine`` closure ∪ {``tos.backtest``}."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert extra == [], (
        f"tos.backtest closure escaped the §0.3 relation {sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"
    )


def test_the_harness_really_takes_its_own_declared_edges() -> None:
    """(anti-phantom §0.5) Every directly-declared edge is really in the closure — no dead names."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in sorted(_ALLOWED_DIRECT_IMPORTS):
        assert expected in tops, (
            f"{expected} is declared in the §0.3 direct-import list but is NOT in the closure — an "
            "unused allowlist entry is a phantom edge (existence claims are grepped too)"
        )


def test_backtest_closure_excludes_the_send_boundary_siblings() -> None:
    """(§0.3/§7.5) egress / brokercap / a future D-E4 gateway stay outside the closure."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for sibling in _FORBIDDEN_SIBLINGS:
        assert sibling not in tops, f"{sibling} leaked into the tos.backtest closure"
    assert "tos.egress" not in tops, (
        "tos.backtest must never import tos.egress — the QCC kernel is not encroached upon; the "
        "send boundary is reached only through the injected Transmit interface (design #33 §7.5)"
    )


def test_backtest_closure_has_no_operational_package_or_dataframe_library() -> None:
    """(§0.3/§3.1) No ``shared.*``, no services/cli, and no numpy / pandas / vectorbt / yaml.

    ``shared.backtest`` is the differential oracle's *other* side: it is compared against, out of
    tree, by a comparator that imports neither — and it is never imported here (design #33 §6.1).
    """
    result = _run_child(_closure_child)
    assert result["forbidden"] == [], (
        f"forbidden packages reached the closure: {result['forbidden']}"
    )


def test_leak_canary_is_detected() -> None:
    """(both ways) Planted egress / brokercap / shared.backtest / pandas leaks are all caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in ("tos.egress", "tos.brokercap", "tos.egressgw", "tos.future_sibling"):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.backtest", "shared.execution", "numpy", "pandas", "vectorbt"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifiers admit every allowlisted package and reject every excluded one."""
    for allowed in ("tos.backtest", "tos.backtest.driver", "tos.engine.sequencer", "tos.canonical"):
        assert _is_allowed_tos_module(allowed) is True
        assert _is_allowed_direct_import(allowed) is True
    for sibling in _FORBIDDEN_SIBLINGS | {"tos.not_yet_invented"}:
        assert _is_allowed_tos_module(sibling) is False
        assert _is_allowed_direct_import(sibling) is False
    # In the closure but NOT directly nameable by a harness source (reached via the engine).
    for indirect in ("tos.are", "tos.afg", "tos.ioc", "tos.venue", "tos.cur", "tos.evidence"):
        assert _is_allowed_tos_module(indirect) is True
        assert _is_allowed_direct_import(indirect) is False
    assert _is_forbidden_non_tos("shared.backtest") is True
    assert _is_forbidden_non_tos("shared.determinism") is True
    assert _is_forbidden_non_tos("services.dashboard") is True
    assert _is_forbidden_non_tos("pandas") is True
    assert _is_forbidden_non_tos("pydantic") is False
    assert _is_forbidden_non_tos("decimal") is False
    assert _is_forbidden_non_tos("click") is False  # must not false-match "cli"


def _ast_offenders(path: Path) -> list[str]:
    """Return every escape / ambient-env / clock / RNG / network offender in one source (AST)."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root == "importlib":
                    offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
                if root in _CLOCK_MODULES:
                    offenders.append(f"{path.name}:{node.lineno} clock import {alias.name}")
                if root in _RNG_MODULES:
                    offenders.append(f"{path.name}:{node.lineno} rng import {alias.name}")
                if root in _NETWORK_MODULES:
                    offenders.append(f"{path.name}:{node.lineno} network import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if root == "importlib":
                offenders.append(f"{path.name}:{node.lineno} from importlib import ...")
            if root in _CLOCK_MODULES:
                offenders.append(f"{path.name}:{node.lineno} clock from {module} import ...")
            if root in _RNG_MODULES:
                offenders.append(f"{path.name}:{node.lineno} rng from {module} import ...")
            if root in _NETWORK_MODULES:
                offenders.append(f"{path.name}:{node.lineno} network from {module} import ...")
            if module == "os":
                for alias in node.names:
                    if alias.name in _AMBIENT_ENV_ATTRS:
                        offenders.append(f"{path.name}:{node.lineno} from os import {alias.name}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in _DYNAMIC_CALL_NAMES:
                    offenders.append(f"{path.name}:{node.lineno} call {func.id}()")
                if func.id in _FORBIDDEN_BUILTIN_CALLS:
                    offenders.append(f"{path.name}:{node.lineno} nondeterministic {func.id}()")
                if func.id in _NONDETERMINISTIC_CALLS:
                    offenders.append(f"{path.name}:{node.lineno} nondeterministic {func.id}()")
            elif isinstance(func, ast.Attribute):
                if func.attr == "import_module":
                    offenders.append(f"{path.name}:{node.lineno} call import_module()")
                if func.attr in _NONDETERMINISTIC_CALLS:
                    offenders.append(f"{path.name}:{node.lineno} nondeterministic .{func.attr}()")
                if func.attr in _FORBIDDEN_BUILTIN_CALLS:
                    offenders.append(f"{path.name}:{node.lineno} nondeterministic .{func.attr}()")
        elif isinstance(node, ast.Attribute):
            if (
                node.attr in _AMBIENT_ENV_ATTRS
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                offenders.append(f"{path.name}:{node.lineno} os.{node.attr}")
    return offenders


def test_source_has_no_escape_env_clock_rng_or_network() -> None:
    """(§4.4/§9) No dynamic escape, ambient env, wall clock, RNG/nonce, or network in the sources.

    The RNG half is what keeps the fill model reproducible: a ``uuid4()`` or a ``now()`` anywhere on
    the settlement path would destroy replay identity (RFC-003 §10:360-363).
    """
    sources = sorted(_BACKTEST_SRC.rglob("*.py"))
    assert sources, f"no tos.backtest source files found under {_BACKTEST_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_offenders(path))
    assert offenders == [], f"forbidden construct found in tos.backtest sources: {offenders}"


def test_the_test_suite_is_clock_and_rng_free_too() -> None:
    """(§9) The suite models nothing the shipped package forbids — including here.

    A determinism canary that scans only ``src`` while its own fixtures seed an RNG would be
    measuring the wrong thing.
    """
    suite = sorted(Path(__file__).resolve().parent.rglob("*.py"))
    offenders: list[str] = []
    for path in suite:
        offenders.extend(
            offender
            for offender in _ast_offenders(path)
            # ``id()`` is not used, but ``hash``/``id`` bans are about *identity derivation*; the
            # suite derives none. Everything else applies verbatim.
            if True
        )
    assert offenders == [], f"forbidden construct found in the backtest suite: {offenders}"


def test_ast_scan_detects_planted_escapes(tmp_path: Path) -> None:
    """The AST scan really catches planted escapes, clocks, RNG, network, and a builtin hash."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import importlib\n"
        "import time\n"
        "import datetime\n"
        "import random\n"
        "import secrets\n"
        "import uuid\n"
        "import socket\n"
        "import asyncio\n"
        "from os import environ\n"
        "value = os.getenv\n"
        "a = __import__('x')\n"
        "b = eval('1')\n"
        "c = exec('pass')\n"
        "d = compile('1', '<s>', 'eval')\n"
        "e = uuid.uuid4()\n"
        "f = time.monotonic()\n"
        "g = datetime.datetime.now()\n"
        "h = hash('x')\n"
        "i = secrets.token_hex()\n"
        "j = random.shuffle([1])\n",
        encoding="utf-8",
    )
    joined = " ".join(_ast_offenders(planted))
    for expected in (
        "import importlib",
        "clock import time",
        "clock import datetime",
        "rng import random",
        "rng import secrets",
        "rng import uuid",
        "network import socket",
        "network import asyncio",
        "from os import environ",
        "os.getenv",
        "__import__()",
        "eval()",
        "exec()",
        "compile()",
        "uuid4()",
        "monotonic()",
        "now()",
        "hash()",
        "token_hex()",
        "shuffle()",
    ):
        assert expected in joined, f"the AST scan missed a planted {expected}"


def test_source_imports_no_module_outside_the_direct_allowlist() -> None:
    """(§0.3 static mirror) No source statically names a ``tos.*`` module off the §0.3 list."""
    offenders: list[str] = []
    for path in sorted(_BACKTEST_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if not _is_allowed_direct_import(name):
                    offenders.append(f"{path.name}:{node.lineno} import {name}")
    assert offenders == [], f"forbidden sibling import in source: {offenders}"


def test_every_submodule_is_covered_by_the_closure_child() -> None:
    """Anti-phantom: the closure child imports **every** shipped submodule, not a stale subset.

    The #27 FD lesson: locking the export surface is not locking the package. If a new submodule
    lands and the child does not import it, its imports would never be exercised by the closure
    scan — so the file list on disk is compared against the child's list.
    """
    on_disk = {
        f"tos.backtest.{path.stem}" if path.stem != "__init__" else "tos.backtest"
        for path in _BACKTEST_SRC.glob("*.py")
    }
    assert on_disk == set(_BACKTEST_SUBMODULES) == set(_LOADED_SUBMODULES), (
        "the shipped submodule set and the closure child's import list have drifted: "
        f"on-disk={sorted(on_disk)}, child={sorted(_BACKTEST_SUBMODULES)}"
    )


def test_the_harness_namespace_exposes_no_engine_or_sibling_mutation_symbol() -> None:
    """(§0.2-1/§2.4 author-level lock) No core-construction or authority symbol is reachable.

    Not merely "the harness does not import it" but "the harness's own namespaces do not carry it":
    every module's ``vars()`` is swept, not just ``tos.backtest.__all__`` (the #27 FD lesson).
    """
    forbidden = (
        "run_commitment_flow",  # §0.2-1 — the sequencer is consumed, never re-authored
        "run_decision_pipeline",  # §0.2-1 — the pipeline is the engine's
        "ProvisionalReservationLedger",  # §2.4 — the ledger is the core's, never the harness's
        "apply_egress_result",  # §2.4 — the projection transition is the core's
        "apply_committed",  # rcl — capacity mutation
        "claim_capability",  # rcl — capability consumption
        "compile_command",  # ioc — broker-command construction
        "permit_single_use",  # afg — permit consumption semantics
        "vector_complete",  # cur — per-send currentness production
    )
    for module_name, module in _LOADED_SUBMODULES.items():
        for name in forbidden:
            assert name not in vars(module), (
                f"{module_name} exposes {name!r} — the harness consumes the engine through its "
                "injected seams; it constructs no core, re-authors no sequencer step, mutates no "
                "capacity, and produces no other authority's decision (design #33 §0.2-1/§2.4)"
            )
    for name in forbidden:
        assert not hasattr(tos.backtest, name)


def test_the_core_type_is_referenced_for_typing_only_and_never_re_exported() -> None:
    """(§2.4) ``EngineCore`` is a **contract-typing** reference in one module, and nothing more.

    The driver names the type so its ``run(core: EngineCore, ...)`` signature is honest about what
    it requires. That is deliberately *not* the same as constructing one — the construction ban is
    proven separately by the AST sweep in ``test_backtest_single_core.py``, which reports any
    ``EngineCore(...)`` call anywhere in the package. Here the narrower claim is pinned: the harness
    does not re-export the core, so no consumer can reach a constructor *through* it.
    """
    assert not hasattr(tos.backtest, "EngineCore"), (
        "tos.backtest re-exports EngineCore — the harness's public surface must not offer the core "
        "it is forbidden to re-instantiate (design #33 §2.4)"
    )
    carriers = sorted(
        name for name, module in _LOADED_SUBMODULES.items() if "EngineCore" in vars(module)
    )
    assert carriers == ["tos.backtest.driver"], (
        f"EngineCore is named by {carriers} — slice #1 needs it in exactly one place, the driver's "
        "run signature (design #33 §4.1)"
    )
