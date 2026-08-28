"""§7.1 import-closure + determinism canaries for ``tos.engine`` — **allowlist** form (design #31 §0.3).

``tos.engine`` is the series' first **wide** import-closure integrator: the thirty-two packages
before it are pure decision kernels whose closure is minimal, whereas the engine assembles them, so
its closure is a *superset* of theirs. That is the nature of an integrator, not a firewall breach
(design #31 §0.3/§10.2-1) — and the allowlist is still a strict subset, so a leak fails exactly as
loudly as it does everywhere else::

    {tos, tos.canonical, tos.ordering, tos.dsl, tos.capsule, tos.time, tos.evidence,
     tos.ioc, tos.venue, tos.rcl, tos.are, tos.afg, tos.cur, tos.engine}

The two packages the design puts **outside** the closure carry the most weight: ``tos.brokercap``
and ``tos.egress`` live beyond the D-E4 send-boundary injection point, and ``tos.egress`` (the QCC
kernel) must never be encroached upon (design #31 §5.4/§4.5/§10.2-3). Both are asserted absent, as
is a not-yet-invented ``tos.brokeradapter``.

Beyond the closure this module asserts, by AST scan of the shipped sources (design #31 §0.3/§7.1):

  1. no operational package (``shared.*`` runtime, ``services.*``, ``cli.*``) and no
     ``numpy`` / ``pandas`` / ``yaml`` in the closure;
  2. no ``os.environ`` / ``os.getenv``;
  3. no dynamic escape — ``exec`` / ``eval`` / ``compile`` / ``__import__`` / ``importlib``;
  4. no network stdlib;
  5. **no wall clock** — ``time`` / ``datetime`` / ``monotonic`` / ``perf_counter``: the core's time
     is the reference coordinate the event carries and :mod:`tos.time` is itself clock-free
     (design #31 §2.3);
  6. **no RNG or nonce source** — ``random`` / ``secrets`` / ``uuid`` / the seed-randomized builtin
     ``hash`` (design #31 §7.1, MAJOR-3). This is what forces the step-12 attempt identity to stay
     content-addressed; introducing ``uuid4()`` or a timestamp nonce would destroy replay identity
     (RFC-003 §10:360-363), and this canary is what detects it.

Planted-leak and planted-escape canaries prove the pipeline actually catches what it claims to, so
"green" is evidence the checker works rather than evidence it was neutered.

Regime tag: orchestration authoring evidence only; closes no EV (design #31 §1.1).
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

import tos.engine
import tos.engine._base
import tos.engine.adapters
import tos.engine.admission
import tos.engine.core
import tos.engine.pipeline
import tos.engine.records
import tos.engine.registry
import tos.engine.sequencer
import tos.engine.sink
import tos.engine.standins
import tos.engine.state
import tos.engine.vocabulary

#: The §0.3 allowlist — the only top-level ``tos.*`` packages the closure may contain.
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
    }
)

#: Siblings the design deliberately keeps **outside** the closure, plus a future one.
_FORBIDDEN_SIBLINGS = frozenset(
    {
        "tos.authority",
        "tos.brokercap",  # D-E4 edge — beyond the send-boundary injection point (§4.5)
        "tos.egress",  # the QCC kernel — never encroached upon (§5.4)
        "tos.failuredomain",
        "tos.hag",
        "tos.iap",
        "tos.liveauth",
        "tos.nontrade",
        "tos.orthostate",  # forward seam only — the core state projection is engine-local (§2.4)
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
        "tos.brokeradapter",  # a *future* D-E4 sibling — excluded by construction
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
#: ``socket`` / ``ssl`` / ``asyncio`` are deliberately **absent** from the closure denylist: the
#: allowed third party ``pydantic`` pulls them into ``sys.modules`` on its own, in every tos
#: package alike, so a closure-membership assertion about them would measure pydantic, not the
#: engine. The accurate mechanism for "the engine opens no socket and runs no event loop" is the
#: AST source scan below (:data:`_NETWORK_MODULES`), which is what design #31 §0.3/§2.1 actually
#: constrains — the engine's own sources.
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

_ENGINE_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "engine"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "compile", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules the event core must never import (design #31 §2.3).
_CLOCK_MODULES = frozenset({"time", "datetime"})
#: Nondeterministic identity / nonce sources (design #31 §7.1, MAJOR-3).
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
        "token_hex",
        "token_bytes",
        "token_urlsafe",
    }
)
#: The seed-randomized builtin. Using it for any identity would break cross-process reproduction.
_FORBIDDEN_BUILTIN_CALLS = frozenset({"hash", "id"})

_ENGINE_SUBMODULES = (
    "tos.engine",
    "tos.engine._base",
    "tos.engine.adapters",
    "tos.engine.admission",
    "tos.engine.core",
    "tos.engine.pipeline",
    "tos.engine.records",
    "tos.engine.registry",
    "tos.engine.sequencer",
    "tos.engine.sink",
    "tos.engine.standins",
    "tos.engine.state",
    "tos.engine.vocabulary",
)


#: Every shipped submodule, imported **statically** (the firewall forbids ``import_module``), so
#: the author-level sweep below reads the real namespaces rather than a re-import.
_LOADED_SUBMODULES = {
    "tos.engine": tos.engine,
    "tos.engine._base": tos.engine._base,
    "tos.engine.adapters": tos.engine.adapters,
    "tos.engine.admission": tos.engine.admission,
    "tos.engine.core": tos.engine.core,
    "tos.engine.pipeline": tos.engine.pipeline,
    "tos.engine.records": tos.engine.records,
    "tos.engine.registry": tos.engine.registry,
    "tos.engine.sequencer": tos.engine.sequencer,
    "tos.engine.sink": tos.engine.sink,
    "tos.engine.standins": tos.engine.standins,
    "tos.engine.state": tos.engine.state,
    "tos.engine.vocabulary": tos.engine.vocabulary,
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
    """Whether a non-``tos`` module is a forbidden closure member (design #31 §0.3)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every engine submodule; report the tos + forbidden closure."""
    import sys

    import tos.engine  # noqa: F401
    import tos.engine._base  # noqa: F401
    import tos.engine.adapters  # noqa: F401
    import tos.engine.admission  # noqa: F401
    import tos.engine.core  # noqa: F401
    import tos.engine.pipeline  # noqa: F401
    import tos.engine.records  # noqa: F401
    import tos.engine.registry  # noqa: F401
    import tos.engine.sequencer  # noqa: F401
    import tos.engine.sink  # noqa: F401
    import tos.engine.standins  # noqa: F401
    import tos.engine.state  # noqa: F401
    import tos.engine.vocabulary  # noqa: F401

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

    import tos.engine  # noqa: F401

    for planted in (
        "shared.config",
        "shared.execution",
        "numpy",
        "tos.egress",
        "tos.brokercap",
        "tos.orthostate",
        "tos.brokeradapter",
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


def test_engine_tos_closure_is_within_the_allowlist() -> None:
    """(§0.3 allowlist) The tos closure ⊆ the 14 declared packages — wide, but still a subset."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert extra == [], (
        f"tos.engine closure escaped the §0.3 allowlist {sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"
    )


def test_engine_closure_contains_every_declared_edge() -> None:
    """(§0.3) Every declared edge is really taken — the allowlist is not padded with dead names."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in sorted(_ALLOWED_TOS_PACKAGES):
        assert expected in tops, (
            f"{expected} is declared in the §0.3 allowlist but is NOT in the closure — an unused "
            "allowlist entry is a phantom edge (anti-phantom: existence claims are grepped too)"
        )


def test_engine_closure_excludes_the_send_boundary_siblings() -> None:
    """(§4.5/§5.4/§10.2-3) brokercap / egress / a future broker adapter stay outside the closure."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for sibling in _FORBIDDEN_SIBLINGS:
        assert sibling not in tops, f"{sibling} leaked into the tos.engine closure"
    assert "tos.egress" not in tops, (
        "tos.engine must never import tos.egress — the QCC kernel is not encroached upon; the "
        "send boundary is reached only through the injected Transmit interface (design #31 §5.4)"
    )


def test_engine_closure_has_no_forbidden_operational_package() -> None:
    """(§0.3) No shared.* operational package, no services/cli, and no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert result["forbidden"] == [], (
        f"forbidden packages reached the closure: {result['forbidden']}"
    )


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted egress / brokercap / orthostate / future-sibling leaks are all caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in (
        "tos.egress",
        "tos.brokercap",
        "tos.orthostate",
        "tos.brokeradapter",
        "tos.future_sibling",
    ):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "shared.execution", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits every allowlisted package and rejects every excluded one."""
    for allowed in ("tos.engine", "tos.engine.sequencer", "tos.dsl.determinism", "tos.canonical"):
        assert _is_allowed_tos_module(allowed) is True
    for sibling in _FORBIDDEN_SIBLINGS | {"tos.not_yet_invented"}:
        assert _is_allowed_tos_module(sibling) is False
        assert _is_allowed_tos_module(sibling + ".predicates") is False
    assert _is_forbidden_non_tos("shared.config") is True
    assert _is_forbidden_non_tos("shared.config.secrets") is True
    assert _is_forbidden_non_tos("services.dashboard") is True
    assert _is_forbidden_non_tos("numpy") is True
    assert _is_forbidden_non_tos("pydantic") is False
    assert _is_forbidden_non_tos("enum") is False
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
    """(§0.3/§7.1) No dynamic escape, ambient env, wall clock, RNG/nonce, or network in the sources."""
    sources = sorted(_ENGINE_SRC.rglob("*.py"))
    assert sources, f"no tos.engine source files found under {_ENGINE_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_offenders(path))
    assert offenders == [], f"forbidden construct found in tos.engine sources: {offenders}"


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
    for path in sorted(_ENGINE_SRC.rglob("*.py")):
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
    assert offenders == [], f"forbidden sibling import in source: {offenders}"


def test_every_submodule_is_covered_by_the_closure_child() -> None:
    """Anti-phantom: the closure child imports **every** shipped submodule, not a stale subset.

    The #27 FD lesson in its author-level form: locking the export surface is not locking the
    package. If a new submodule lands and the child does not import it, its imports would never be
    exercised by the closure scan — so the file list on disk is compared against the child's list.
    """
    on_disk = {
        f"tos.engine.{path.stem}" if path.stem != "__init__" else "tos.engine"
        for path in _ENGINE_SRC.glob("*.py")
    }
    assert on_disk == set(_ENGINE_SUBMODULES) == set(_LOADED_SUBMODULES), (
        "the shipped submodule set and the closure child's import list have drifted: "
        f"on-disk={sorted(on_disk)}, child={sorted(_ENGINE_SUBMODULES)}"
    )


def test_engine_namespace_exposes_no_sibling_mutation_symbol() -> None:
    """(§4.3 author-level lock) No mutation / construction / capability symbol is reachable.

    Not only "the engine does not import it" but "the engine's own namespaces do not carry it":
    the #27 FD lesson that locking the export surface alone leaves the submodules open. Every
    engine module's ``vars()`` is swept, not just ``tos.engine.__all__``.
    """
    forbidden = (
        "apply_committed",  # rcl — capacity mutation
        "apply_benefit",  # rcl
        "claim_capability",  # rcl — capability consumption
        "fold_commands",  # rcl
        "compile_command",  # ioc — broker-command construction
        "permit_single_use",  # afg — permit consumption semantics
        "risk_decision",  # are — the Authority's own production
        "action_flow_decision",  # afg — the Governor's own production
        "vector_complete",  # cur — the per-send currentness production
    )
    for module_name, module in _LOADED_SUBMODULES.items():
        for name in forbidden:
            assert name not in vars(module), (
                f"{module_name} exposes {name!r} — the Execution Coordinator neither mutates "
                "capacity, constructs commands, issues capabilities, nor produces another "
                "authority's decision (RFC-002 §9.1:557, §10.7:724; RFC-005 §12)"
            )
    for name in forbidden:
        assert not hasattr(tos.engine, name)
