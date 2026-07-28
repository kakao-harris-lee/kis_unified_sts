"""§7.1 import-closure verification for ``tos.sir`` — **allowlist** form (design #28 §0.3/§7.1).

Written as an **allowlist** (design #28 §7.1): after importing every ``tos.sir`` submodule in a fresh
interpreter, the set of top-level ``tos.*`` packages in ``sys.modules`` must be a subset of::

    {tos, tos.canonical, tos.ordering, tos.sir}

An enumerated denylist would go stale the moment a new sibling lands; the allowlist is **future-robust**
— any sibling, present or future (including a not-landed ``tos.stm`` / ``tos.sci``), fails the assertion
simply by appearing. **sibling edge 0** — sir has **no** sanctioned sibling edge, so its allowlist admits
only the two core packages. **rcl edge 0 in particular** (design #28 §3.5/§10.1): sir does no capacity
arithmetic — the worst-credible effect is an injected opaque coordinate, never a ``CapacityVector`` —
so unlike are / ioc / afg it takes no rcl edge, and ``tos.rcl`` is in the forbidden set. **protective /
sbr in particular**: the forward seam is an anonymous ``bool | None`` consumed *by them*, so there is no
sir → protective / sbr import either (design #28 §3.6).

It also asserts (design #28 §0.3):

  1. no operational package is in the closure (``shared.execution`` / ``kis`` / ``streaming`` / ``llm``
     / ``storage`` / ``backtest``, ``services.*``, ``cli.*``);
  2. neither ``shared.config`` nor ``shared.config.secrets`` is present, nor ``shared.determinism``;
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent (bounds are injected; YAML is the harness's);
  4. no ``tos.sir`` source references ``os.environ`` / ``os.getenv``, a dynamic escape (``exec`` /
     ``eval`` / ``__import__`` / ``importlib``), or a real clock (``time`` / ``datetime``) — sir is
     **clock-free** (an Incident Generation is an ordering identity, not wall-clock);
  5. the sibling-absence assertion **explicitly includes the maximum re-authoring temptations**
     ``tos.hag`` / ``tos.sbr`` / ``tos.spg`` / ``tos.evidence`` / ``tos.rcl`` / ``tos.egress`` /
     ``tos.cur`` / ``tos.protective`` / ``tos.liveauth`` / ``tos.iap`` (the Effective Principal collapse
     + quorum, the Recovery Barrier + Recovery Session, the Safety Incident Policy activation + Hard
     Safety Envelope, evidence custody, the CapacityVector, final-egress enforcement, the Active
     Currentness Vector, the Protective Action Controller + Cancellation Arbiter, the Live Authorization
     and the single-use consumption shape are re-authored NOT AT ALL and imported NOT AT ALL — produced
     facts arrive as injected scalars / verdicts / digests).

A planted-leak canary (including ``tos.hag`` / ``tos.sbr`` / ``tos.rcl`` / ``tos.protective`` / a
*future* sibling ``tos.stm`` / ``tos.future_sibling`` / ``shared.config``) proves the spawn+scan pipeline
catches a leak no denylist could have anticipated; a planted-AST-escape canary proves the static scan
catches an escape — so "green" is evidence the checker works, not that it has been neutered.
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

import tos.sir

#: The §7.1 allowlist: the only top-level ``tos.*`` packages the sir closure may contain.
_ALLOWED_TOS_PACKAGES = frozenset({"tos", "tos.canonical", "tos.ordering", "tos.sir"})

#: The forbidden siblings (all real siblings + the not-landed ``tos.stm`` / ``tos.sci`` + a future
#: ``tos.future_sibling``) — INCLUDING the maximum re-authoring temptations (design #28 §3.5).
_FORBIDDEN_SIBLINGS = frozenset(
    {
        "tos.afg",
        "tos.are",
        "tos.authority",
        "tos.brokercap",
        "tos.capsule",
        "tos.cur",
        "tos.dsl",
        "tos.egress",
        "tos.evidence",
        "tos.failuredomain",
        "tos.hag",
        "tos.iap",
        "tos.ioc",
        "tos.liveauth",
        "tos.nontrade",
        "tos.orthostate",
        "tos.posttrade",
        "tos.protective",
        "tos.rcl",
        "tos.recon",
        "tos.replacement",
        "tos.rlp",
        "tos.sbr",
        "tos.spg",
        "tos.time",
        "tos.venue",
        "tos.wdr",
        "tos.stm",  # not-landed upstream — excluded by construction
        "tos.sci",  # not-landed upstream — excluded by construction
        "tos.future_sibling",  # a *future* sibling — the allowlist excludes it by construction
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

_SIR_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "sir"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules that must never be imported by a clock-free sir source.
_CLOCK_MODULES = frozenset({"time", "datetime"})

#: The re-authored (never imported) sibling predicate / type names — asserted ABSENT from the sir
#: namespace (local authorship, not an import; design #28 §7.1).
_REAUTHORED_NOT_IMPORTED = (
    "effective_principal_collapse",  # hag
    "quorum_independence_satisfied",  # hag
    "EffectivePrincipalGraph",  # hag
    "IsolationFacts",  # sbr
    "HardSafetyEnvelope",  # spg
    "CapacityVector",  # rcl (edge 0 — sir does no capacity arithmetic)
    "SafetyCurrentnessVector",  # cur
    "DimensionKey",  # cur (the INCIDENT dimension key is cur-owned)
    "GapStatus",  # evidence (its SUSPECTED is a different proposition)
    "SegmentCommitmentScheme",  # evidence
    "DeRestrictionInputs",  # protective
)


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
    """Whether a non-``tos`` module is a forbidden closure member (design #28 §0.3)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every tos.sir submodule; report the tos + forbidden closure."""
    import sys

    import tos.sir  # noqa: F401
    import tos.sir._base  # noqa: F401
    import tos.sir.predicates  # noqa: F401
    import tos.sir.records  # noqa: F401
    import tos.sir.state  # noqa: F401
    import tos.sir.vocabulary  # noqa: F401

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

    import tos.sir  # noqa: F401

    for planted in (
        "shared.config",
        "numpy",
        "tos.hag",  # maximum re-authoring temptation — re-authored, not imported
        "tos.sbr",  # maximum re-authoring temptation — re-authored, not imported
        "tos.rcl",  # rcl edge 0 — re-authored, not imported
        "tos.protective",  # forward-seam consumer — an import would invert the seam
        "tos.cur",  # downstream consumer — a sir → cur import would be a cycle
        "tos.stm",  # not-landed upstream the allowlist catches
        "tos.future_sibling",  # a *future* sibling the allowlist catches
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


def test_sir_tos_closure_is_within_the_allowlist() -> None:
    """(§7.1 allowlist) The tos closure ⊆ {canonical, ordering, sir} — no sibling leaks (edge 0)."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert (
        extra == []
    ), f"tos.sir closure escaped the §7.1 allowlist {sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"


def test_sir_closure_includes_only_the_two_core_packages() -> None:
    """(§7.1) tos.canonical + tos.ordering ARE present; NO sibling edge."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in ("tos.canonical", "tos.ordering", "tos.sir"):
        assert expected in tops, f"{expected} missing from the tos.sir closure"
    for sibling in _FORBIDDEN_SIBLINGS:
        assert sibling not in tops, f"{sibling} leaked into the tos.sir closure"


def test_sir_closure_has_no_forbidden_operational_package() -> None:
    """(design #28 §0.3 items 1-3) No shared.* operational package, no services/cli, no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert (
        result["forbidden"] == []
    ), f"forbidden packages reached the tos.sir closure: {result['forbidden']}"


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted config / numpy / hag / sbr / rcl / protective / cur / stm / future caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in (
        "tos.hag",
        "tos.sbr",
        "tos.rcl",
        "tos.protective",
        "tos.cur",
        "tos.stm",
        "tos.future_sibling",
    ):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits the three allowed packages and rejects every sibling (incl. hag / rcl)."""
    for allowed in (
        "tos.sir",
        "tos.sir.predicates",
        "tos.canonical",
        "tos.canonical._base",
        "tos.ordering",
    ):
        assert _is_allowed_tos_module(allowed) is True
    for sibling in _FORBIDDEN_SIBLINGS | {"tos.not_yet_invented"}:
        assert _is_allowed_tos_module(sibling) is False
        assert _is_allowed_tos_module(sibling + ".predicates") is False
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


def test_reauthored_predicates_are_absent_from_sir_namespace() -> None:
    """(§7.1) The re-authored sibling predicates / types are NOT importable from tos.sir."""
    for name in _REAUTHORED_NOT_IMPORTED:
        assert not hasattr(tos.sir, name), (
            f"{name} must be re-authored NOT AT ALL and imported NOT AT ALL — its presence in "
            "tos.sir would mean a forbidden sibling import (design #28 §7.1)"
        )


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


def test_sir_source_has_no_dynamic_escape_ambient_env_or_clock() -> None:
    """(design #28 §0.3 item 4) No tos.sir source uses exec/eval/importlib/os.environ or a real clock."""
    sources = sorted(_SIR_SRC.rglob("*.py"))
    assert sources, f"no tos.sir source files found under {_SIR_SRC}"
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


def test_sir_source_imports_no_forbidden_sibling_statically() -> None:
    """(design #28 §0.3 static mirror) No sir source contains an ``import tos.<sibling>`` statement."""
    offenders: list[str] = []
    for path in sorted(_SIR_SRC.rglob("*.py")):
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
    assert offenders == [], f"forbidden sibling import in sir source: {offenders}"
