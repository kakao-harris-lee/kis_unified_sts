"""Table-driven import-closure + determinism policy shared by every package canary."""

from __future__ import annotations

import ast
import multiprocessing as mp
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
SRC_ROOT = TESTS_DIR.parent / "src" / "tos"

ESCAPE = "escape"
ENV = "env"
CLOCK = "clock"
CLOCK_ATTR = "clock_attr"
RNG = "rng"
NETWORK = "network"
NONDET = "nondet"
BUILTIN = "builtin"

AMBIENT_ENV_ATTRS: frozenset[str] = frozenset({"environ", "getenv"})
CLOCK_MODULES: frozenset[str] = frozenset({"time", "datetime"})
RNG_MODULES: frozenset[str] = frozenset({"random", "secrets", "uuid"})
NETWORK_MODULES: frozenset[str] = frozenset(
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
    }
)
NONDETERMINISTIC_CALLS: frozenset[str] = frozenset(
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
BUILTIN_CALLS: frozenset[str] = frozenset({"hash", "id"})
CLOCK_ATTRS: frozenset[str] = frozenset(
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
CLOCK_ATTR_OWNERS: frozenset[str] = frozenset({"time", "datetime", "dt"})

DENIED_NON_TOS_PROBES: tuple[str, ...] = (
    "shared.config",
    "shared.config.secrets",
    "shared.llm",
    "shared.llm.market",
    "shared.execution",
    "shared.kis",
    "shared.storage",
    "shared.backtest",
    "services",
    "services.dashboard",
    "cli",
    "numpy",
    "pandas.core",
)

OPTIONAL_DENIED_PROBES: tuple[str, ...] = ("shared.determinism", "yaml")

CLEARED_NON_TOS_PROBES: tuple[str, ...] = (
    "pydantic",
    "decimal",
    "click",
    "enum",
    "shared.utils",
    "shared.exceptions",
    "socket",
    "ssl",
    "http.client",
    "urllib.request",
    "urllib.parse",
)

PLANTED_SOURCE = (
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
    "j = random.shuffle([1])\n"
)


@dataclass(frozen=True)
class ScanSpec:
    """Which determinism categories a package's sources are scanned for, and with what vocabulary."""

    categories: frozenset[str]
    dynamic_calls: frozenset[str] = frozenset({"exec", "eval", "__import__"})
    clock_modules: frozenset[str] = CLOCK_MODULES
    rng_modules: frozenset[str] = RNG_MODULES
    network_modules: frozenset[str] = NETWORK_MODULES
    nondeterministic_calls: frozenset[str] = NONDETERMINISTIC_CALLS
    builtin_calls: frozenset[str] = BUILTIN_CALLS
    clock_attrs: frozenset[str] = CLOCK_ATTRS

    def planted_markers(self) -> tuple[str, ...]:
        """The substrings ``PLANTED_SOURCE`` must produce for the enabled categories."""
        markers: list[str] = []
        if ESCAPE in self.categories:
            markers.extend(["import importlib", "__import__()", "eval()", "exec()"])
            if "compile" in self.dynamic_calls:
                markers.append("compile()")
        if ENV in self.categories:
            markers.extend(["from os import environ", "os.getenv"])
        if CLOCK in self.categories:
            markers.extend(["clock import time", "clock import datetime"])
        if CLOCK_ATTR in self.categories:
            markers.append("time.monotonic")
        if RNG in self.categories:
            markers.extend(
                ["rng import random", "rng import secrets", "rng import uuid"]
            )
        if NETWORK in self.categories:
            markers.extend(
                f"network import {name}"
                for name in ("socket", "asyncio")
                if name in self.network_modules
            )
        if NONDET in self.categories:
            markers.extend(["uuid4()", "monotonic()", "now()", "token_hex()"])
        if BUILTIN in self.categories:
            markers.append("hash()")
        return tuple(markers)


def scan_offenders(path: Path, spec: ScanSpec) -> list[str]:
    """Every escape / ambient-env / clock / RNG / network / nondeterminism offender in one source."""
    cats = spec.categories
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if ESCAPE in cats and root == "importlib":
                    offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
                if CLOCK in cats and root in spec.clock_modules:
                    offenders.append(
                        f"{path.name}:{node.lineno} clock import {alias.name}"
                    )
                if RNG in cats and root in spec.rng_modules:
                    offenders.append(
                        f"{path.name}:{node.lineno} rng import {alias.name}"
                    )
                if NETWORK in cats and root in spec.network_modules:
                    offenders.append(
                        f"{path.name}:{node.lineno} network import {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if ESCAPE in cats and root == "importlib":
                offenders.append(f"{path.name}:{node.lineno} from importlib import ...")
            if CLOCK in cats and root in spec.clock_modules:
                offenders.append(
                    f"{path.name}:{node.lineno} clock from {module} import ..."
                )
            if RNG in cats and root in spec.rng_modules:
                offenders.append(
                    f"{path.name}:{node.lineno} rng from {module} import ..."
                )
            if NETWORK in cats and root in spec.network_modules:
                offenders.append(
                    f"{path.name}:{node.lineno} network from {module} import ..."
                )
            if ENV in cats and module == "os":
                for alias in node.names:
                    if alias.name in AMBIENT_ENV_ATTRS:
                        offenders.append(
                            f"{path.name}:{node.lineno} from os import {alias.name}"
                        )
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if ESCAPE in cats and func.id in spec.dynamic_calls:
                    offenders.append(f"{path.name}:{node.lineno} call {func.id}()")
                if BUILTIN in cats and func.id in spec.builtin_calls:
                    offenders.append(
                        f"{path.name}:{node.lineno} nondeterministic {func.id}()"
                    )
                if NONDET in cats and func.id in spec.nondeterministic_calls:
                    offenders.append(
                        f"{path.name}:{node.lineno} nondeterministic {func.id}()"
                    )
            elif isinstance(func, ast.Attribute):
                if ESCAPE in cats and func.attr == "import_module":
                    offenders.append(f"{path.name}:{node.lineno} call import_module()")
                if NONDET in cats and func.attr in spec.nondeterministic_calls:
                    offenders.append(
                        f"{path.name}:{node.lineno} nondeterministic .{func.attr}()"
                    )
                if BUILTIN in cats and func.attr in spec.builtin_calls:
                    offenders.append(
                        f"{path.name}:{node.lineno} nondeterministic .{func.attr}()"
                    )
        elif isinstance(node, ast.Attribute):
            if (
                ENV in cats
                and node.attr in AMBIENT_ENV_ATTRS
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                offenders.append(f"{path.name}:{node.lineno} os.{node.attr}")
            if (
                CLOCK_ATTR in cats
                and node.attr in spec.clock_attrs
                and isinstance(node.value, ast.Name)
                and node.value.id in CLOCK_ATTR_OWNERS
            ):
                offenders.append(
                    f"{path.name}:{node.lineno} {node.value.id}.{node.attr}"
                )
    return offenders


def statically_imported_modules(path: Path) -> list[tuple[str, int]]:
    """Every ``(module, lineno)`` one source statically imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    entries: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            entries.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            entries.append((node.module, node.lineno))
    return entries


def names(text: str) -> tuple[str, ...]:
    """The whitespace-separated module names in ``text``, as a tuple."""
    return tuple(text.split())


def nameset(text: str) -> frozenset[str]:
    """The whitespace-separated module names in ``text``, as a frozenset."""
    return frozenset(text.split())


def tos_top_level(module_name: str) -> str | None:
    """The ``tos.<pkg>`` top-level package of ``module_name`` (``None`` if not a tos module)."""
    if module_name != "tos" and not module_name.startswith("tos."):
        return None
    parts = module_name.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else "tos"


def is_denied(
    module_name: str, exact: frozenset[str], prefixes: tuple[str, ...]
) -> bool:
    """Whether ``module_name`` is a forbidden closure member under one package's denylist."""
    if module_name in exact:
        return True
    return module_name.startswith(prefixes)


@dataclass(frozen=True)
class ClosurePolicy:
    """One package's declared import closure, denylist, canaries and source-scan vocabulary."""

    name: str
    child_imports: tuple[str, ...]
    deny_exact: frozenset[str]
    deny_prefixes: tuple[str, ...]
    canary_imports: tuple[str, ...] = ()
    planted: tuple[str, ...] = ()
    planted_tos: tuple[str, ...] = ()
    planted_non_tos: tuple[str, ...] = ()
    allowed_tos: frozenset[str] | None = None
    static_allowed: frozenset[str] | None = None
    static_scan: bool = False
    forbidden_siblings: tuple[str, ...] = ()
    declared_but_not_taken: frozenset[str] = frozenset()
    expected_present: tuple[str, ...] = ()
    expected_present_mode: str = ""
    allowed_canaries: tuple[str, ...] = ()
    indirect_only: tuple[str, ...] = ()
    cleared_canaries: tuple[str, ...] = ()
    src_dirs: tuple[str, ...] = ()
    scan: ScanSpec | None = None
    suite_dir: str | None = None
    namespace_forbidden: tuple[str, ...] = ()
    namespace_all_submodules: bool = False
    submodule_dir: str | None = None
    declared_submodules: tuple[str, ...] = ()
    bounded_by: tuple[str, ...] = ()
    every_edge_is_taken: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def denies(self, module_name: str) -> bool:
        """Whether this package's denylist flags ``module_name``."""
        return is_denied(module_name, self.deny_exact, self.deny_prefixes)

    def edges(self) -> tuple[str, ...]:
        """The modules this package's closure must contain (its declared, really-taken edges)."""
        if self.expected_present_mode == "allowlist":
            assert self.allowed_tos is not None
            return tuple(sorted(self.allowed_tos))
        if self.expected_present_mode == "direct":
            assert self.static_allowed is not None
            return tuple(sorted(self.static_allowed))
        return self.expected_present

    def denied_tos_siblings(self) -> tuple[str, ...]:
        """Every ``tos.*`` sibling this package's denylist names outright."""
        return tuple(sorted(n for n in self.deny_exact if n.startswith("tos.")))

    def rejected_tos_siblings(self) -> tuple[str, ...]:
        """Every sibling the declared allowlist must reject, plus an unborn one."""
        return tuple(sorted(set(self.forbidden_siblings) | {"tos.not_yet_invented"}))

    def admits(self, module_name: str) -> bool:
        """Whether a ``tos.*`` module is inside this package's declared allowlist."""
        assert self.allowed_tos is not None, f"{self.name} declares no tos allowlist"
        top = tos_top_level(module_name)
        return top is None or top in self.allowed_tos

    def admits_directly(self, module_name: str) -> bool:
        """Whether a ``tos.*`` module may be **named directly** by one of this package's sources."""
        allowed = self.static_allowed or self.allowed_tos
        assert allowed is not None, f"{self.name} declares no direct-import allowlist"
        top = tos_top_level(module_name)
        return top is None or top in allowed

    def sources(self) -> list[Path]:
        """Every shipped source file this package's scans cover."""
        out: list[Path] = []
        for name in self.src_dirs:
            out.extend(sorted((SRC_ROOT / name).rglob("*.py")))
        return out


def _child(queue: Any, plan: dict[str, Any]) -> None:
    """Child target: run ``plan['importer']``, plant ``plan['planted']``, report the closure."""
    import sys
    import types

    from ._closure_children import IMPORTERS

    IMPORTERS[plan["importer"]]()
    for name in plan["planted"]:
        sys.modules[name] = types.ModuleType(name)

    exact = plan["deny_exact"]
    prefixes = plan["deny_prefixes"]
    queue.put(
        {
            "tos_tops": sorted(
                {
                    top
                    for name in sys.modules
                    if (top := tos_top_level(name)) is not None
                }
            ),
            "forbidden": sorted(
                name for name in sys.modules if is_denied(name, exact, prefixes)
            ),
            "present": {name: name in sys.modules for name in plan["probes"]},
        }
    )


def _run(plan: dict[str, Any]) -> dict[str, Any]:
    """Spawn a clean interpreter for ``plan`` and return the closure it reports."""
    ctx = mp.get_context("spawn")
    queue: Any = ctx.Queue()
    proc = ctx.Process(target=_child, args=(queue, plan))
    proc.start()
    result = queue.get(timeout=180)
    proc.join(timeout=180)
    assert proc.exitcode == 0, f"closure child exited abnormally: {proc.exitcode}"
    assert isinstance(result, dict), f"closure child returned {type(result).__name__}"
    return result


_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def _plan(policy: ClosurePolicy, importer: str, planted: tuple[str, ...]):
    """The picklable description one spawn child needs."""
    return {
        "importer": importer,
        "planted": list(planted),
        "deny_exact": policy.deny_exact,
        "deny_prefixes": policy.deny_prefixes,
        "probes": list(policy.edges()),
    }


def closure_of(policy: ClosurePolicy) -> dict[str, Any]:
    """The measured closure of ``policy``'s own submodules, cached per session."""
    key = (policy.name, "closure")
    if key not in _CACHE:
        _CACHE[key] = _run(_plan(policy, policy.name, ()))
    return _CACHE[key]


def canary_of(policy: ClosurePolicy) -> dict[str, Any]:
    """The measured closure after planting ``policy``'s fake leaks, cached per session."""
    key = (policy.name, "canary")
    if key not in _CACHE:
        _CACHE[key] = _run(_plan(policy, f"{policy.name}:root", policy.planted))
    return _CACHE[key]


def closure_of_module(policy: ClosurePolicy, module: str) -> dict[str, Any]:
    """The measured closure of ``module`` alone, cached per session."""
    key = (policy.name, f"bound:{module}")
    if key not in _CACHE:
        _CACHE[key] = _run(_plan(policy, f"module:{module}", ()))
    return _CACHE[key]
