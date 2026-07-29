"""§0.3 import-closure + **network-absence** canary for ``tos.brokeradapter``.

This is the package where the closure canary is not merely hygiene but the mechanical evidence for
the design's largest judgement (§2 / §2.2-①): the real broker path **cannot** be a ``tos/``
artifact, because ``tos/`` forbids network stdlib and a real transport needs it. If a socket, an
HTTP client, or a credential ever appeared here, the judgement would be false — so it is asserted
directly, and the assertion is itself canaried against a planted violation.

The declared closure is the series' narrowest::

    {tos, tos.canonical, tos.ordering, tos.engine, tos.brokercap, tos.brokeradapter}

Two claims, proven separately (see the egressgw twin for the reasoning): the **static** claim
that no source imports a ``tos.*`` module off the list, and the **runtime** claim that the closure
is bounded by ``declared ∪ closure(tos.engine)`` — ``tos.engine`` is a declared edge and an
integrator whose own §0.3-locked closure legitimately rides along.

``tos.egressgw`` is asserted absent: the gateway injects itself into this boundary through a
structural port, never the reverse.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

import tos.brokeradapter
import tos.brokeradapter.protocol
import tos.brokeradapter.synthetic

_ALLOWED_TOS_PACKAGES = frozenset(
    {
        "tos",
        "tos.canonical",
        "tos.ordering",
        "tos.engine",
        "tos.brokercap",
        "tos.brokeradapter",
    }
)

_FORBIDDEN_SIBLINGS = frozenset(
    {
        "tos.egressgw",
        "tos.egress",
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

_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "brokeradapter"

#: The network / transport stdlib and third-party clients a *real* broker adapter would need —
#: and which this package may never contain (design #34 §2.2-① / §5.1).
_NETWORK_MODULES = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "urllib",
        "ftplib",
        "smtplib",
        "telnetlib",
        "asyncio",
        "selectors",
        "subprocess",
        "ctypes",
        "requests",
        "aiohttp",
        "httpx",
        "websocket",
        "websockets",
        "grpc",
    }
)
#: Credential-shaped identifiers a real transport would carry; none may appear here (§4.5).
_CREDENTIAL_FRAGMENTS = (
    "app_key",
    "app_secret",
    "access_token",
    "api_key",
    "secret_key",
    "bearer",
)
_CLOCK_MODULES = frozenset({"time", "datetime"})
_RNG_MODULES = frozenset({"random", "secrets", "uuid"})
_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "compile", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})

_SUBMODULES = ("tos.brokeradapter", "tos.brokeradapter.protocol", "tos.brokeradapter.synthetic")

_LOADED_SUBMODULES = {
    "tos.brokeradapter": tos.brokeradapter,
    "tos.brokeradapter.protocol": tos.brokeradapter.protocol,
    "tos.brokeradapter.synthetic": tos.brokeradapter.synthetic,
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
    """Whether a non-``tos`` module is a forbidden closure member."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every brokeradapter submodule; report the closure."""
    import sys

    import tos.brokeradapter  # noqa: F401
    import tos.brokeradapter.protocol  # noqa: F401
    import tos.brokeradapter.synthetic  # noqa: F401

    queue.put(
        {
            "tos_tops": sorted(
                {top for name in sys.modules if (top := _tos_top_level(name)) is not None}
            ),
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
    """Child target: plant fake forbidden modules, then run the scan."""
    import sys
    import types

    import tos.brokeradapter  # noqa: F401

    for planted in ("shared.kis", "numpy", "tos.egressgw", "tos.egress", "tos.future_sibling"):
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


# ---------------------------------------------------------------------------
# the load-bearing canary: no network anywhere in this package
# ---------------------------------------------------------------------------


def _network_offenders(path: Path) -> list[str]:
    """Every network / credential / clock / RNG / escape offender in one source."""
    offenders: list[str] = []
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _NETWORK_MODULES:
                    offenders.append(f"{path.name}:{node.lineno} network import {alias.name}")
                if root in _CLOCK_MODULES:
                    offenders.append(f"{path.name}:{node.lineno} clock import {alias.name}")
                if root in _RNG_MODULES:
                    offenders.append(f"{path.name}:{node.lineno} rng import {alias.name}")
                if root == "importlib":
                    offenders.append(f"{path.name}:{node.lineno} import importlib")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if root in _NETWORK_MODULES:
                offenders.append(f"{path.name}:{node.lineno} network from {module} import ...")
            if root in _CLOCK_MODULES:
                offenders.append(f"{path.name}:{node.lineno} clock from {module} import ...")
            if root in _RNG_MODULES:
                offenders.append(f"{path.name}:{node.lineno} rng from {module} import ...")
            if root == "importlib":
                offenders.append(f"{path.name}:{node.lineno} from importlib import ...")
            if module == "os":
                for alias in node.names:
                    if alias.name in _AMBIENT_ENV_ATTRS:
                        offenders.append(f"{path.name}:{node.lineno} from os import {alias.name}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _DYNAMIC_CALL_NAMES:
                offenders.append(f"{path.name}:{node.lineno} call {func.id}()")
            if isinstance(func, ast.Attribute) and func.attr == "import_module":
                offenders.append(f"{path.name}:{node.lineno} call import_module()")
        elif isinstance(node, ast.Attribute):
            if (
                node.attr in _AMBIENT_ENV_ATTRS
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                offenders.append(f"{path.name}:{node.lineno} os.{node.attr}")
        elif isinstance(node, (ast.Name, ast.arg)):
            identifier = node.id if isinstance(node, ast.Name) else node.arg
            lowered = identifier.lower()
            for fragment in _CREDENTIAL_FRAGMENTS:
                if fragment in lowered:
                    offenders.append(f"{path.name}:{node.lineno} credential name {identifier}")
    return offenders


def test_the_package_contains_no_network_credential_clock_or_rng() -> None:
    """(§2.2-① / §5.1) The mechanical evidence that a real transport cannot live in ``tos/``."""
    sources = sorted(_SRC.rglob("*.py"))
    assert sources, f"no tos.brokeradapter source files found under {_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_network_offenders(path))
    assert offenders == [], (
        "tos.brokeradapter must contain no network, credential, clock, or RNG construct — its "
        f"absence is what makes design #34 §2's judgement true: {offenders}"
    )


def test_the_network_canary_detects_a_planted_violation(tmp_path: Path) -> None:
    """(both ways) Green above is evidence the canary works, not that it was neutered."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import socket\n"
        "import ssl\n"
        "import asyncio\n"
        "import requests\n"
        "from http import client\n"
        "import time\n"
        "import uuid\n"
        "import importlib\n"
        "from os import environ\n"
        "app_key = 'x'\n"
        "def f(access_token):\n"
        "    return access_token\n"
        "y = eval('1')\n",
        encoding="utf-8",
    )
    joined = " ".join(_network_offenders(planted))
    for expected in (
        "network import socket",
        "network import ssl",
        "network import asyncio",
        "network import requests",
        "network from http import",
        "clock import time",
        "rng import uuid",
        "import importlib",
        "from os import environ",
        "credential name app_key",
        "credential name access_token",
        "eval()",
    ):
        assert expected in joined, f"the network canary missed a planted {expected}"


# ---------------------------------------------------------------------------
# the closure itself
# ---------------------------------------------------------------------------


def test_source_imports_no_tos_module_outside_the_declared_allowlist() -> None:
    """(§0.3, the strict claim) The narrowest closure in the series, asserted statically."""
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


def test_runtime_closure_is_bounded_by_the_declared_set_plus_the_engine_edge() -> None:
    """(§0.3, the honest consequence) closure(brokeradapter) ⊆ declared ∪ closure(tos.engine)."""
    result = _run_child(_closure_child)
    engine = _run_child(_engine_only_child)
    bound = _ALLOWED_TOS_PACKAGES | set(engine["tos_tops"])
    extra = sorted(set(result["tos_tops"]) - bound)
    assert extra == [], f"tos.brokeradapter closure escaped its bound: {extra}"


def test_closure_excludes_the_gateway_and_the_egress_kernel() -> None:
    """(§0.3/§5.1) The gateway injects itself here; the adapter never reaches back."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for sibling in _FORBIDDEN_SIBLINGS:
        assert sibling not in tops, f"{sibling} leaked into the tos.brokeradapter closure"


def test_closure_has_no_forbidden_operational_package() -> None:
    """(§0.3) Emphatically no ``shared.kis`` — the real broker band is outside ``tos/``."""
    result = _run_child(_closure_child)
    assert result["forbidden"] == [], (
        f"forbidden packages reached the closure: {result['forbidden']}"
    )


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted egressgw / egress / shared.kis / numpy leaks are all caught."""
    result = _run_child(_leak_canary_child)
    engine = _run_child(_engine_only_child)
    bound = _ALLOWED_TOS_PACKAGES | set(engine["tos_tops"])
    extra = set(result["tos_tops"]) - bound
    for expected in ("tos.egressgw", "tos.egress", "tos.future_sibling"):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.kis", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits every allowlisted package and rejects every excluded one."""
    for allowed in ("tos.brokeradapter", "tos.brokeradapter.synthetic", "tos.engine.records"):
        assert _is_allowed_tos_module(allowed) is True
    for sibling in _FORBIDDEN_SIBLINGS | {"tos.not_yet_invented"}:
        assert _is_allowed_tos_module(sibling) is False
    assert _is_forbidden_non_tos("shared.kis") is True
    assert _is_forbidden_non_tos("pydantic") is False
    assert _is_forbidden_non_tos("click") is False  # must not false-match "cli"


def test_every_submodule_is_covered_by_the_closure_child() -> None:
    """Anti-phantom: the child imports **every** shipped submodule, not a stale subset."""
    on_disk = {
        f"tos.brokeradapter.{path.stem}" if path.stem != "__init__" else "tos.brokeradapter"
        for path in _SRC.glob("*.py")
    }
    assert on_disk == set(_SUBMODULES) == set(_LOADED_SUBMODULES)


def test_the_package_declares_that_the_real_path_is_designed_but_not_implemented() -> None:
    """(§2.1 / §5.1) The stage separation is stated in the code, not only in the design doc."""
    doc = " ".join((tos.brokeradapter.__doc__ or "").split())
    for phrase in (
        "the real broker path",
        "not implemented",
        "broker-resource-consuming",
        "closes no EV",
        "No blind resubmission",
    ):
        assert phrase in doc, f"the package docstring lost its honest-scope phrase: {phrase!r}"
