"""§0.3 import-closure + determinism canaries for ``tos.egressgw`` — allowlist form.

The design's declared closure is a **direct-import allowlist**::

    {tos, tos.canonical, tos.ordering, tos.ioc, tos.venue, tos.cur, tos.egress,
     tos.brokercap, tos.rcl, tos.capsule, tos.evidence, tos.engine, tos.egressgw}

**⚠ ``tos.capsule`` / ``tos.evidence`` are deliberately absent from the allowlist this test
enforces** (adversarial review MINOR-3). Design §0.3 declares them — for a future evidence-sink
edge — but no shipped source imports either, and the previous form of this file kept them on the
allowlist while *exempting* them from the "every declared edge is really taken" check. That is
the phantom-edge defect refracted: an anti-phantom test that carves out its own exception proves
nothing about the two names it excuses. The test now enforces the **actual** state, so re-adding
either package is required at the moment it is really consumed. The design text is unchanged —
an unused declared edge is sealed as an absence, not as an exemption.

Two distinct claims are proven separately, because conflating them is how a closure test quietly
becomes weaker than it reads:

1. **Static (the strict claim).** No egressgw source imports any ``tos.*`` module outside the
   eleven currently taken. This is the load-bearing seal and it is asserted with no widening and
   no per-name exemption at all.
2. **Runtime (the honest consequence).** The runtime closure is the declared set **plus whatever
   the declared ``tos.engine`` edge itself pulls in** — ``tos.engine`` is an integrator whose own
   §0.3 allowlist (locked by its own ``test_engine_import_closure.py``) legitimately includes
   ``tos.dsl`` / ``tos.time`` / ``tos.are`` / ``tos.afg``. Rather than hand-widening the list,
   the bound is *computed*: a child process imports ``tos.engine`` alone and reports its closure,
   and egressgw's closure must be a subset of ``declared ∪ closure(tos.engine)``. A leak that is
   not reachable through the declared engine edge still fails loudly.

Beyond the closure this module asserts, by AST scan of the shipped sources: no operational
package, no ambient env, no dynamic escape, **no network stdlib**, no wall clock, and no
RNG / nonce source (design #34 §0.3/§12.1-8 — attempt identities are content-addressed).

``tos.brokeradapter`` is asserted **absent** in both directions: the transport arrives by
injection through a structural port, never by import (design #34 §0.3).

Planted-leak and planted-escape canaries prove the checker catches what it claims to, so green is
evidence the pipeline works rather than evidence it was neutered.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

import tos.egressgw
import tos.egressgw._base
import tos.egressgw.construction
import tos.egressgw.gateway
import tos.egressgw.records
import tos.egressgw.vocabulary

#: The §0.3 allowlist **as actually taken** — the only top-level ``tos.*`` packages the sources
#: may import. ``tos.capsule`` / ``tos.evidence`` are declared by design §0.3 for a future
#: evidence-sink edge but are imported by nothing today, so they are held out here rather than
#: exempted from the phantom-edge check (adversarial review MINOR-3): re-add each at the moment
#: it is really consumed.
#:
#: ``tos.dsl`` was added by design #35 §0.3 / §6-C9 (the single sanctioned widening of this list).
#: It is **not a new runtime-closure member** — ``tos.dsl`` already rides along inside
#: ``closure(tos.engine)``, as :func:`test_runtime_closure_is_bounded_by_the_declared_set_plus_the_engine_edge`
#: computes rather than assumes — so what changed is only the *direct naming* permission:
#: ``construction.py`` now names ``ContextValueView`` (the D-E2 value surface a price is projected
#: from) and ``FLAT_QUANTITY_BASIS`` (the single source of truth for the flat basis token, rather
#: than a duplicated constant). The edge is really taken, which
#: :func:`test_every_declared_edge_is_really_taken` proves from the other side.
_ALLOWED_TOS_PACKAGES = frozenset(
    {
        "tos",
        "tos.canonical",
        "tos.ordering",
        "tos.ioc",
        "tos.venue",
        "tos.cur",
        "tos.egress",
        "tos.brokercap",
        "tos.rcl",
        "tos.engine",
        "tos.dsl",
        "tos.egressgw",
    }
)

#: The two design-§0.3 names deferred out of :data:`_ALLOWED_TOS_PACKAGES` (MINOR-3). Named so
#: the hold-out is itself asserted rather than merely implied by an omission.
_DECLARED_BUT_NOT_TAKEN = frozenset({"tos.capsule", "tos.evidence"})

#: Siblings that must stay outside the closure entirely — including the D-E4 twin, which is
#: reached only through the injected structural transport port (design #34 §0.3/§5.1).
_FORBIDDEN_SIBLINGS = frozenset(
    {
        "tos.brokeradapter",
        "tos.authority",
        "tos.backtest",
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

_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "egressgw"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "compile", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
_CLOCK_MODULES = frozenset({"time", "datetime"})
_RNG_MODULES = frozenset({"random", "secrets", "uuid"})
_NETWORK_MODULES = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "urllib",
        "ftplib",
        "smtplib",
        "asyncio",
        "subprocess",
        "ctypes",
        "requests",
        "aiohttp",
        "httpx",
    }
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

_SUBMODULES = (
    "tos.egressgw",
    "tos.egressgw._base",
    "tos.egressgw.construction",
    "tos.egressgw.gateway",
    "tos.egressgw.records",
    "tos.egressgw.vocabulary",
)

_LOADED_SUBMODULES = {
    "tos.egressgw": tos.egressgw,
    "tos.egressgw._base": tos.egressgw._base,
    "tos.egressgw.construction": tos.egressgw.construction,
    "tos.egressgw.gateway": tos.egressgw.gateway,
    "tos.egressgw.records": tos.egressgw.records,
    "tos.egressgw.vocabulary": tos.egressgw.vocabulary,
}


def _tos_top_level(module_name: str) -> str | None:
    """The ``tos.<pkg>`` top-level package of ``module_name`` (``None`` if not a tos module)."""
    if module_name != "tos" and not module_name.startswith("tos."):
        return None
    parts = module_name.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else "tos"


def _is_allowed_tos_module(module_name: str) -> bool:
    """Whether a ``tos.*`` module is inside the §0.3 declared allowlist."""
    top = _tos_top_level(module_name)
    return top is None or top in _ALLOWED_TOS_PACKAGES


def _is_forbidden_non_tos(module_name: str) -> bool:
    """Whether a non-``tos`` module is a forbidden closure member (design #34 §0.3)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every egressgw submodule; report the tos + forbidden closure."""
    import sys

    import tos.egressgw  # noqa: F401
    import tos.egressgw._base  # noqa: F401
    import tos.egressgw.construction  # noqa: F401
    import tos.egressgw.gateway  # noqa: F401
    import tos.egressgw.records  # noqa: F401
    import tos.egressgw.vocabulary  # noqa: F401

    tos_tops = sorted(
        {top for name in sys.modules if (top := _tos_top_level(name)) is not None}
    )
    queue.put(
        {
            "tos_tops": tos_tops,
            "forbidden": sorted(name for name in sys.modules if _is_forbidden_non_tos(name)),
        }
    )


def _engine_only_child(queue: mp.Queue) -> None:
    """Child target: import ``tos.engine`` alone and report its own tos closure."""
    import sys

    import tos.engine  # noqa: F401

    queue.put(
        {
            "tos_tops": sorted(
                {top for name in sys.modules if (top := _tos_top_level(name)) is not None}
            ),
            "forbidden": [],
        }
    )


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant fake forbidden + future-sibling modules, then run the scan."""
    import sys
    import types

    import tos.egressgw  # noqa: F401

    for planted in (
        "shared.config",
        "shared.execution",
        "numpy",
        "tos.brokeradapter",
        "tos.spg",
        "tos.future_sibling",
    ):
        sys.modules[planted] = types.ModuleType(planted)

    queue.put(
        {
            "tos_tops": sorted(
                {top for name in sys.modules if (top := _tos_top_level(name)) is not None}
            ),
            "forbidden": sorted(name for name in sys.modules if _is_forbidden_non_tos(name)),
        }
    )


def _run_child(target) -> dict:
    """Spawn ``target`` in a clean interpreter and return its reported result dict."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    result = queue.get(timeout=180)
    proc.join(timeout=180)
    assert proc.exitcode == 0, f"closure child exited abnormally: {proc.exitcode}"
    return result


def test_source_imports_no_tos_module_outside_the_declared_allowlist() -> None:
    """(§0.3, the strict claim) No source statically imports a ``tos.*`` module off the list."""
    offenders: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
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


def test_every_declared_edge_is_really_taken() -> None:
    """(anti-phantom) The allowlist is not padded with dead names — every edge is imported."""
    imported: set[str] = set()
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                top = _tos_top_level(name)
                if top is not None:
                    imported.add(top)
    unused = _ALLOWED_TOS_PACKAGES - imported - {"tos"}
    assert unused == set(), (
        f"allowlist entries are never imported: {sorted(unused)} — an unused allowlist "
        "entry is a phantom edge (anti-phantom: existence claims are grepped too)"
    )
    # (MINOR-3) …and the hold-out is asserted from the other side: the two design-§0.3 names
    # really are unconsumed today, so nothing was quietly dropped from a live edge.
    assert _DECLARED_BUT_NOT_TAKEN & imported == set(), (
        f"{sorted(_DECLARED_BUT_NOT_TAKEN & imported)} is now imported — add it back to "
        "_ALLOWED_TOS_PACKAGES; the design §0.3 declaration is only honoured once the edge is "
        "really taken"
    )


def test_runtime_closure_is_bounded_by_the_declared_set_plus_the_engine_edge() -> None:
    """(§0.3, the honest consequence) closure(egressgw) ⊆ declared ∪ closure(tos.engine).

    The bound is **computed**, not hand-widened: ``tos.engine`` is a declared edge and an
    integrator, so its own §0.3-locked closure (``tos.dsl`` / ``tos.time`` / ``tos.are`` /
    ``tos.afg`` …) legitimately rides along. Anything reachable *outside* that union is a leak.
    """
    result = _run_child(_closure_child)
    engine = _run_child(_engine_only_child)
    bound = _ALLOWED_TOS_PACKAGES | set(engine["tos_tops"])
    extra = sorted(set(result["tos_tops"]) - bound)
    assert extra == [], (
        f"tos.egressgw closure escaped declared ∪ closure(tos.engine): {extra}"
    )


def test_closure_excludes_the_transport_twin_and_every_unrelated_sibling() -> None:
    """(§0.3/§5.1) ``tos.brokeradapter`` is injected, never imported."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for sibling in _FORBIDDEN_SIBLINGS:
        assert sibling not in tops, f"{sibling} leaked into the tos.egressgw closure"


def test_the_egress_kernel_is_in_the_closure_because_it_is_consumed() -> None:
    """(§11-3, both ways) egressgw *does* import tos.egress — consumption, not encroachment."""
    result = _run_child(_closure_child)
    assert "tos.egress" in set(result["tos_tops"])


def test_closure_has_no_forbidden_operational_package() -> None:
    """(§0.3) No shared.* operational package, no services/cli, and no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert result["forbidden"] == [], (
        f"forbidden packages reached the closure: {result['forbidden']}"
    )


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted brokeradapter / spg / shared / numpy leaks are all caught."""
    result = _run_child(_leak_canary_child)
    engine = _run_child(_engine_only_child)
    bound = _ALLOWED_TOS_PACKAGES | set(engine["tos_tops"])
    extra = set(result["tos_tops"]) - bound
    for expected in ("tos.brokeradapter", "tos.spg", "tos.future_sibling"):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "shared.execution", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits every allowlisted package and rejects every excluded one."""
    for allowed in ("tos.egressgw", "tos.egressgw.gateway", "tos.egress.predicates", "tos.ioc"):
        assert _is_allowed_tos_module(allowed) is True
    for sibling in _FORBIDDEN_SIBLINGS | {"tos.not_yet_invented"}:
        assert _is_allowed_tos_module(sibling) is False
        assert _is_allowed_tos_module(sibling + ".predicates") is False
    assert _is_forbidden_non_tos("shared.config") is True
    assert _is_forbidden_non_tos("services.dashboard") is True
    assert _is_forbidden_non_tos("numpy") is True
    assert _is_forbidden_non_tos("pydantic") is False
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
    """(§0.3/§12.1-8) No dynamic escape, ambient env, wall clock, RNG/nonce, or network."""
    sources = sorted(_SRC.rglob("*.py"))
    assert sources, f"no tos.egressgw source files found under {_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_offenders(path))
    assert offenders == [], f"forbidden construct found in tos.egressgw sources: {offenders}"


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
        "import ssl\n"
        "import asyncio\n"
        "import requests\n"
        "from os import environ\n"
        "value = os.getenv\n"
        "a = __import__('x')\n"
        "b = eval('1')\n"
        "c = exec('pass')\n"
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
        "rng import uuid",
        "network import socket",
        "network import ssl",
        "network import requests",
        "from os import environ",
        "os.getenv",
        "__import__()",
        "eval()",
        "exec()",
        "uuid4()",
        "monotonic()",
        "now()",
        "hash()",
        "token_hex()",
    ):
        assert expected in joined, f"the AST scan missed a planted {expected}"


def test_every_submodule_is_covered_by_the_closure_child() -> None:
    """Anti-phantom: the child imports **every** shipped submodule, not a stale subset."""
    on_disk = {
        f"tos.egressgw.{path.stem}" if path.stem != "__init__" else "tos.egressgw"
        for path in _SRC.glob("*.py")
    }
    assert on_disk == set(_SUBMODULES) == set(_LOADED_SUBMODULES), (
        "the shipped submodule set and the closure child's import list have drifted: "
        f"on-disk={sorted(on_disk)}, child={sorted(_SUBMODULES)}"
    )
