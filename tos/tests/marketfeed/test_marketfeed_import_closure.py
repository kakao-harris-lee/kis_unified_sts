"""§7.1 — import-closure, cycle-0, and determinism canaries for ``tos.marketfeed`` (design #32 §7.1).

``tos.marketfeed`` is a **producer** package: it consumes ``tos.dsl``, ``tos.capsule``,
``tos.canonical`` and (in its resolver layer only) ``tos.engine``, and **nothing consumes it**. That
asymmetry is the whole cycle-0 argument of design #32 §2.2/§3.4, and it is asserted here in both
directions rather than asserted in prose:

* *forward* — the marketfeed closure ⊆ the declared allowlist, and every declared entry is really
  taken (no padded phantom edge);
* *backward* — importing ``tos.dsl`` or ``tos.engine`` in a **fresh interpreter** never pulls in
  ``tos.marketfeed``. That is what makes ``engine -> marketfeed -> engine`` and
  ``dsl -> marketfeed -> dsl`` impossible, and it is what keeps the committed fourteen-package
  engine allowlist (``tos/tests/engine/test_engine_import_closure.py:59-76``) green with no edit.

**The pure-layer claim, stated honestly.** Design #32 §3.4 splits the package into a pure value
layer and a resolver adapter, and says the pure layer's closure carries no ``tos.engine``. At
*runtime* that claim is unmeasurable for a submodule: ``import tos.marketfeed.value`` necessarily
executes ``tos.marketfeed.__init__`` first, whose re-exports include the resolver. So the split is
enforced **statically**, by scanning the pure modules' own sources for a ``tos.engine`` import — the
form of the claim that is actually checkable. Asserting the runtime form would be asserting
something the import system makes untrue.

Beyond the closure this module asserts, by AST scan of the shipped sources:

  1. no operational package (``shared.*``, ``services.*``, ``cli.*``) and no ``numpy`` / ``pandas``
     / ``yaml``;
  2. no ``os.environ`` / ``os.getenv``;
  3. no dynamic escape — ``exec`` / ``eval`` / ``compile`` / ``__import__`` / ``importlib``;
  4. **no network stdlib** — the structural form of "the value surface never fetches"
     (RFC-004 §9:242-244), which is the single most load-bearing canary for a package whose *name*
     says "feed";
  5. no wall clock and no RNG / nonce source, so a published view digest is reproducible.

Planted-leak and planted-escape canaries prove the checker catches what it claims to, so green is
evidence the pipeline works rather than evidence it was neutered.

Regime tag: authoring evidence only; closes no EV (design #32 §1.1).
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

import tos.marketfeed
import tos.marketfeed._base
import tos.marketfeed.records
import tos.marketfeed.resolver
import tos.marketfeed.value
import tos.marketfeed.vocabulary

from . import _cycle_children

#: The §0.3 allowlist — the only top-level ``tos.*`` packages the marketfeed closure may contain.
#: Wide, because the resolver layer speaks the engine's payload vocabulary and ``tos.engine`` is
#: itself an integrator; still a strict subset, so a leak fails as loudly as anywhere else.
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
        "tos.marketfeed",
    }
)

#: Siblings deliberately outside the closure. ``tos.egress`` (the QCC kernel) and ``tos.brokercap``
#: live beyond the D-E4 send boundary; ``tos.backtest`` / ``tos.egressgw`` / ``tos.brokeradapter``
#: are *downstream consumers* — a marketfeed edge into any of them would invert the layering the
#: same way an ``engine -> marketfeed`` edge would.
_FORBIDDEN_SIBLINGS = frozenset(
    {
        "tos.authority",
        "tos.backtest",
        "tos.brokeradapter",
        "tos.brokercap",
        "tos.egress",
        "tos.egressgw",
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

_MARKETFEED_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "marketfeed"

#: The pure layer (design #32 §3.4) — every module except the resolver adapter.
_PURE_MODULE_FILES = ("__init__.py", "_base.py", "vocabulary.py", "records.py", "value.py")
_ADAPTER_MODULE_FILE = "resolver.py"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "compile", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
_CLOCK_MODULES = frozenset({"time", "datetime"})
_RNG_MODULES = frozenset({"random", "secrets", "uuid"})
_NETWORK_MODULES = frozenset(
    {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "asyncio", "subprocess", "ctypes"}
)
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
        "token_hex",
        "token_bytes",
        "token_urlsafe",
    }
)
_FORBIDDEN_BUILTIN_CALLS = frozenset({"hash", "id"})

_MARKETFEED_SUBMODULES = (
    "tos.marketfeed",
    "tos.marketfeed._base",
    "tos.marketfeed.records",
    "tos.marketfeed.resolver",
    "tos.marketfeed.value",
    "tos.marketfeed.vocabulary",
)

#: Every shipped submodule, imported **statically** (the firewall forbids ``import_module``), so the
#: author-level sweep below reads the real namespaces rather than a re-import.
_LOADED_SUBMODULES = {
    "tos.marketfeed": tos.marketfeed,
    "tos.marketfeed._base": tos.marketfeed._base,
    "tos.marketfeed.records": tos.marketfeed.records,
    "tos.marketfeed.resolver": tos.marketfeed.resolver,
    "tos.marketfeed.value": tos.marketfeed.value,
    "tos.marketfeed.vocabulary": tos.marketfeed.vocabulary,
}


def _tos_top_level(module_name: str) -> str | None:
    """The ``tos.<pkg>`` top-level package of ``module_name`` (``None`` if not a tos module)."""
    if module_name != "tos" and not module_name.startswith("tos."):
        return None
    parts = module_name.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else "tos"


def _is_allowed_tos_module(module_name: str) -> bool:
    """Whether a ``tos.*`` module is inside the §0.3 allowlist."""
    top = _tos_top_level(module_name)
    return top is None or top in _ALLOWED_TOS_PACKAGES


def _is_forbidden_non_tos(module_name: str) -> bool:
    """Whether a non-``tos`` module is a forbidden closure member (design #1 §3.2)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every marketfeed submodule; report the tos + forbidden closure."""
    import sys

    import tos.marketfeed  # noqa: F401
    import tos.marketfeed._base  # noqa: F401
    import tos.marketfeed.records  # noqa: F401
    import tos.marketfeed.resolver  # noqa: F401
    import tos.marketfeed.value  # noqa: F401
    import tos.marketfeed.vocabulary  # noqa: F401

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

    import tos.marketfeed  # noqa: F401

    for planted in (
        "shared.config",
        "shared.execution",
        "numpy",
        "tos.egress",
        "tos.brokercap",
        "tos.backtest",
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


def _run_child(target) -> dict:
    """Spawn ``target`` in a clean interpreter and return its reported result dict."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    result = queue.get(timeout=120)
    proc.join(timeout=120)
    assert proc.exitcode == 0, f"closure child exited abnormally: {proc.exitcode}"
    return result


# ---------------------------------------------------------------------------
# Forward: the closure is inside the allowlist, and the allowlist is not padded
# ---------------------------------------------------------------------------


def test_marketfeed_tos_closure_is_within_the_allowlist() -> None:
    """(§0.3) The tos closure ⊆ the declared packages."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert extra == [], (
        f"tos.marketfeed closure escaped the allowlist {sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"
    )


def test_marketfeed_closure_contains_every_declared_edge() -> None:
    """(anti-phantom §0.5) Every declared edge is really taken — no padded phantom entry."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in sorted(_ALLOWED_TOS_PACKAGES):
        assert expected in tops, (
            f"{expected} is declared in the allowlist but is NOT in the closure — an unused "
            "allowlist entry is a phantom edge (existence claims are grepped too)"
        )


def test_marketfeed_closure_excludes_the_downstream_and_send_boundary_siblings() -> None:
    """(§0.3/§3.4) Consumers and the QCC kernel stay outside — the layering is not inverted."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for sibling in _FORBIDDEN_SIBLINGS:
        assert sibling not in tops, f"{sibling} leaked into the tos.marketfeed closure"


def test_marketfeed_closure_has_no_forbidden_operational_package() -> None:
    """(§0.3) No ``shared.*`` operational package, no services/cli, no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert result["forbidden"] == [], (
        f"forbidden packages reached the closure: {result['forbidden']}"
    )


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted egress / brokercap / backtest / future-sibling leaks are all caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in ("tos.egress", "tos.brokercap", "tos.backtest", "tos.future_sibling"):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "shared.execution", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits every allowlisted package and rejects every excluded one."""
    for allowed in ("tos.marketfeed", "tos.marketfeed.value", "tos.dsl.determinism", "tos.canonical"):
        assert _is_allowed_tos_module(allowed) is True
    for sibling in _FORBIDDEN_SIBLINGS | {"tos.not_yet_invented"}:
        assert _is_allowed_tos_module(sibling) is False
        assert _is_allowed_tos_module(sibling + ".predicates") is False
    assert _is_forbidden_non_tos("shared.config") is True
    assert _is_forbidden_non_tos("shared.config.secrets") is True
    assert _is_forbidden_non_tos("services.dashboard") is True
    assert _is_forbidden_non_tos("numpy") is True
    assert _is_forbidden_non_tos("pydantic") is False
    assert _is_forbidden_non_tos("click") is False  # must not false-match "cli"


# ---------------------------------------------------------------------------
# Backward: nothing imports marketfeed — the cycle has no first edge (§7.2-13)
# ---------------------------------------------------------------------------


def _run_cycle_child(target) -> list[str]:
    """Spawn a cycle-0 child (defined in a marketfeed-free module) and return its report."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    result = queue.get(timeout=120)
    proc.join(timeout=120)
    assert proc.exitcode == 0, f"cycle child exited abnormally: {proc.exitcode}"
    return list(result)


def test_importing_dsl_alone_never_pulls_in_marketfeed() -> None:
    """(§3.4 ★ cycle-0) ``dsl -> marketfeed -> dsl`` has no first edge, measured in a fresh child."""
    assert _run_cycle_child(_cycle_children.dsl_only_child) == []


def test_importing_engine_alone_never_pulls_in_marketfeed() -> None:
    """(§2.2 F1 ★ cycle-0) ``engine -> marketfeed -> engine`` has no first edge either.

    This is the property that lets ``DecisionTickPayload.value_view`` be a **dsl** type and lets the
    committed fourteen-package engine allowlist stay untouched.
    """
    assert _run_cycle_child(_cycle_children.engine_only_child) == []


def test_importing_capsule_alone_never_pulls_in_marketfeed() -> None:
    """(§0.2-1) The ratified Capsule package is untouched — it does not learn about marketfeed."""
    assert _run_cycle_child(_cycle_children.capsule_only_child) == []


def test_the_cycle_children_module_imports_nothing_at_module_scope() -> None:
    """(anti-phantom) The measurement is real only if its child module is marketfeed-free.

    A spawn child imports the module its target lives in. Were that module to import
    ``tos.marketfeed`` at scope, the three assertions above would pass vacuously — they would be
    measuring the harness. So the harness itself is checked.
    """
    source = Path(_cycle_children.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_level = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    ]
    assert module_level == [], "the cycle-child module must import nothing at module scope"


def test_no_dsl_or_engine_source_statically_imports_marketfeed() -> None:
    """(§3.4, static mirror) The runtime measurement above is confirmed at the source level."""
    src_root = _MARKETFEED_SRC.parent
    offenders: list[str] = []
    for package in ("dsl", "engine"):
        for path in sorted((src_root / package).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name == "tos.marketfeed" or name.startswith("tos.marketfeed."):
                        offenders.append(f"{package}/{path.name}:{node.lineno} import {name}")
    assert offenders == [], f"a dsl/engine source imports marketfeed — cycle risk: {offenders}"


def test_the_engine_allowlist_still_omits_marketfeed() -> None:
    """(§15.2 ③) The committed engine canary's own allowlist is read and confirmed unchanged.

    Anti-phantom in its existence form: rather than asserting "we did not have to edit the engine
    test", the shipped constant is parsed out of the engine canary's source. It is read from disk
    rather than imported because the firewall's allowlist has no cross-suite ``tests.*`` entry —
    reading the file is both compliant and a stricter check, since it sees the committed text.
    """
    engine_canary = (
        Path(__file__).resolve().parents[1] / "engine" / "test_engine_import_closure.py"
    )
    tree = ast.parse(engine_canary.read_text(encoding="utf-8"), filename=str(engine_canary))
    declared: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_ALLOWED_TOS_PACKAGES"
            for target in node.targets
        ):
            for literal in ast.walk(node.value):
                if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                    declared.append(literal.value)
    assert declared, "could not read the engine canary's allowlist — the anti-phantom read failed"
    assert "tos.marketfeed" not in declared
    assert len(declared) == 14


# ---------------------------------------------------------------------------
# The pure / adapter split, enforced statically (§3.4)
# ---------------------------------------------------------------------------


def _statically_imported_tos_modules(path: Path) -> set[str]:
    """Every ``tos.*`` module a source statically imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return {name for name in imported if name == "tos" or name.startswith("tos.")}


def test_the_pure_layer_statically_imports_no_engine() -> None:
    """(§3.4 ★) Only the resolver adapter may name ``tos.engine``.

    The ``__init__`` re-export is excluded from the *pure* list on purpose: a package's ``__init__``
    exposing the adapter is the adapter's edge, not the value layer's.
    """
    offenders: list[str] = []
    for filename in _PURE_MODULE_FILES:
        if filename == "__init__.py":
            continue
        imported = _statically_imported_tos_modules(_MARKETFEED_SRC / filename)
        for name in sorted(imported):
            if name == "tos.engine" or name.startswith("tos.engine."):
                offenders.append(f"{filename} imports {name}")
    assert offenders == [], f"the pure value layer reached tos.engine: {offenders}"


def test_the_adapter_layer_really_holds_the_engine_edge() -> None:
    """(anti-phantom §0.5) The split is real in both directions — the adapter does import engine."""
    imported = _statically_imported_tos_modules(_MARKETFEED_SRC / _ADAPTER_MODULE_FILE)
    assert any(
        name == "tos.engine" or name.startswith("tos.engine.") for name in imported
    ), "resolver.py declares no tos.engine import — the declared adapter edge would be a phantom"


# ---------------------------------------------------------------------------
# Source-level escape / ambient / clock / RNG / network canaries (§7.1)
# ---------------------------------------------------------------------------


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
    """(§7.1 ★) The package whose name says "feed" opens nothing and reads no clock."""
    sources = sorted(_MARKETFEED_SRC.rglob("*.py"))
    assert sources, f"no tos.marketfeed source files found under {_MARKETFEED_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_offenders(path))
    assert offenders == [], f"forbidden construct found in tos.marketfeed sources: {offenders}"


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
        "import urllib\n"
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
        "i = secrets.token_hex()\n",
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
        "network import urllib",
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
    ):
        assert expected in joined, f"the AST scan missed a planted {expected}"


def test_source_imports_no_module_outside_the_allowlist() -> None:
    """(§0.3 static mirror) No source statically imports a ``tos.*`` module off the allowlist."""
    offenders: list[str] = []
    for path in sorted(_MARKETFEED_SRC.rglob("*.py")):
        for name in sorted(_statically_imported_tos_modules(path)):
            if not _is_allowed_tos_module(name):
                offenders.append(f"{path.name} import {name}")
    assert offenders == [], f"forbidden sibling import in source: {offenders}"


def test_every_submodule_is_covered_by_the_closure_child() -> None:
    """Anti-phantom (#27 FD): the child imports **every** shipped submodule, not a stale subset.

    Locking the export surface is not locking the package. If a new submodule lands and the child
    does not import it, its imports would never be exercised — so the on-disk file list is compared
    against the child's list.
    """
    on_disk = {
        f"tos.marketfeed.{path.stem}" if path.stem != "__init__" else "tos.marketfeed"
        for path in _MARKETFEED_SRC.glob("*.py")
    }
    assert on_disk == set(_MARKETFEED_SUBMODULES) == set(_LOADED_SUBMODULES), (
        "the shipped submodule set and the closure child's import list have drifted: "
        f"on-disk={sorted(on_disk)}, child={sorted(_MARKETFEED_SUBMODULES)}"
    )


def test_the_pure_module_file_list_matches_disk() -> None:
    """Anti-phantom: the pure/adapter partition names every shipped file, exactly once."""
    on_disk = {path.name for path in _MARKETFEED_SRC.glob("*.py")}
    assert on_disk == set(_PURE_MODULE_FILES) | {_ADAPTER_MODULE_FILE}
    assert _ADAPTER_MODULE_FILE not in _PURE_MODULE_FILES


def test_marketfeed_namespace_exposes_no_authority_or_mutation_symbol() -> None:
    """(author-level lock, #27 FD) No sibling capability symbol is reachable from any submodule.

    Not "marketfeed does not import it" but "marketfeed's own namespaces do not carry it": every
    module's ``vars()`` is swept, not just ``tos.marketfeed.__all__``. A value surface produces
    evidence about values; it approves nothing, mutates no capacity, constructs no command, and
    transmits nothing.
    """
    forbidden = (
        "apply_committed",  # rcl — capacity mutation
        "claim_capability",  # rcl — capability consumption
        "compile_command",  # ioc — broker-command construction
        "permit_single_use",  # afg — permit consumption semantics
        "risk_decision",  # are — the Authority's own production
        "action_flow_decision",  # afg — the Governor's own production
        "vector_complete",  # cur — the per-send currentness production
        "send_once",  # brokeradapter — transmission
    )
    for module_name, module in _LOADED_SUBMODULES.items():
        for name in forbidden:
            assert name not in vars(module), (
                f"{module_name} exposes {name!r} — the value surface produces values, not "
                "authority (RFC-002 §9.1:557; RFC-005 §12)"
            )
    for name in forbidden:
        assert not hasattr(tos.marketfeed, name)
