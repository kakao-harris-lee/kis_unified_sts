"""§7.1 import-closure verification for ``tos.stm`` — **allowlist** form (design #30 §0.3/§7.1).

Written as an **allowlist** (design #30 §7.1): after importing every ``tos.stm`` submodule in a fresh
interpreter, the set of top-level ``tos.*`` packages in ``sys.modules`` must be a subset of::

    {tos, tos.canonical, tos.ordering, tos.stm}

An enumerated denylist would go stale the moment a new sibling lands; the allowlist is **future-robust**
— any sibling, present or future, fails the assertion simply by appearing. **sibling edge 0** — stm has
**no** sanctioned sibling edge, so its allowlist admits only the two core packages. **rcl edge 0 in
particular** (design #30 §3.5/§10.2-⑥): stm does no capacity arithmetic — the worst credible economic
effect is an injected opaque coordinate, never a ``CapacityVector`` — which is what ADR §7 line 235
demands ("Risk Capacity Ledger | monitoring never writes capacity"), so ``tos.rcl`` is forbidden.
**cur / rlp / spg / sir in particular**: those four are the committed **forward** seam — they consume
coordinates stm produces, anonymously — so an stm → cur / rlp / spg / sir import would invert the seam
into a cycle and is forbidden too. **sci in particular**: ``tos.sci`` (ADR-002-029) landed after this
contract was authored, but the contract keeps -029 as an **injected** coordinate with **zero** code
citation, so it stays in the forbidden set exactly like every other sibling.

It also asserts (design #30 §0.3):

  1. no operational package is in the closure (``shared.execution`` / ``kis`` / ``streaming`` / ``llm``
     / ``storage`` / ``backtest``, ``services.*``, ``cli.*``);
  2. neither ``shared.config`` nor ``shared.config.secrets`` is present, nor ``shared.determinism``;
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent (bounds are injected; YAML is the harness's);
  4. no ``tos.stm`` source references ``os.environ`` / ``os.getenv``, a dynamic escape (``exec`` /
     ``eval`` / ``__import__`` / ``importlib``), or a real clock (``time`` / ``datetime``) — stm is
     **clock-free** (a Monitor Generation is an ordering identity, not wall-clock);
  5. the sibling-absence assertion **explicitly includes the maximum re-authoring temptations**
     ``tos.cur`` / ``tos.spg`` / ``tos.rlp`` / ``tos.sir`` / ``tos.egress`` / ``tos.evidence`` /
     ``tos.rcl`` / ``tos.authority`` / ``tos.liveauth`` / ``tos.hag`` / ``tos.wdr`` / ``tos.iap``
     (the Active Currentness Vector **and the MONITORING dimension's completeness judgement**, the
     Safety Monitoring Policy activation + Hard Safety Envelope, the EV-L6 demotion, the Incident
     Generation + incident classification, final-egress enforcement, evidence custody, the
     CapacityVector, Safety Authority / HALT, Live Authorization, the Effective Principal, the
     Non-Waivable Boundary and the single-use consumption shape are re-authored NOT AT ALL and imported
     NOT AT ALL — produced facts arrive as injected scalars / verdicts / digests / generations).

A planted-leak canary (including ``tos.cur`` / ``tos.rcl`` / ``tos.sir`` / ``tos.sci`` / a *future*
sibling ``tos.future_sibling`` / ``shared.config``) proves the spawn+scan pipeline catches a leak no
denylist could have anticipated; a planted-AST-escape canary proves the static scan catches an escape —
so "green" is evidence the checker works, not that it has been neutered.

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

import tos.stm

#: The §7.1 allowlist: the only top-level ``tos.*`` packages the stm closure may contain.
_ALLOWED_TOS_PACKAGES = frozenset({"tos", "tos.canonical", "tos.ordering", "tos.stm"})

#: The forbidden siblings (every real sibling, including the landed ``tos.sci`` the contract keeps as
#: an injected coordinate, plus a future ``tos.future_sibling``) — INCLUDING the maximum re-authoring
#: temptations (design #30 §3.5).
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
        "tos.sci",  # ADR-002-029 — landed, but kept an injected coordinate with 0 code citation
        "tos.sir",
        "tos.spg",
        "tos.time",
        "tos.venue",
        "tos.wdr",
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

_STM_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "stm"


def _stm_sources() -> list[Path]:
    """Every ``tos.stm`` source, asserted **non-empty** so a path typo cannot make a sweep vacuous."""
    sources = sorted(_STM_SRC.rglob("*.py"))
    assert (
        sources
    ), f"no tos.stm source found under {_STM_SRC} — this sweep would be vacuous"
    return sources


_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules that must never be imported by a clock-free stm source.
_CLOCK_MODULES = frozenset({"time", "datetime"})

#: The re-authored (never imported) sibling predicate / type names — asserted ABSENT from the stm
#: namespace (local authorship, not an import; design #30 §7.1).
_REAUTHORED_NOT_IMPORTED = (
    "SafetyCurrentnessVector",  # cur
    "DimensionKey",  # cur — the MONITORING dimension key is cur-owned
    "MANDATED_DIMENSION_FLOOR",  # cur — the mandated floor judgement is cur-owned
    "vector_complete",  # cur — the completeness judgement is cur-owned
    "HardSafetyEnvelope",  # spg
    "GovernedArtifactKind",  # spg — the artifact-kind tokens are spg-owned
    "monitoring_not_preventive",  # rlp — the forward consumer, never imported back
    "AllFalseTrialAuthority",  # rlp
    "IncidentGeneration",  # sir
    "IncidentLifecycleState",  # sir
    "CapacityVector",  # rcl (edge 0 — stm does no capacity arithmetic)
    "GapStatus",  # evidence (a different gap axis from MonitoringGapKind)
    "ConformanceResult",  # ioc (a different conformance axis)
    "ApprovalResult",  # iap (the single-use shape is re-expressed, not imported)
    "EffectivePrincipalGraph",  # hag
    "AdmissionResult",  # sci — ADR-002-029, injected only
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
    """Whether a non-``tos`` module is a forbidden closure member (design #30 §0.3)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every tos.stm submodule; report the tos + forbidden closure."""
    import sys

    import tos.stm  # noqa: F401
    import tos.stm._base  # noqa: F401
    import tos.stm.predicates  # noqa: F401
    import tos.stm.records  # noqa: F401
    import tos.stm.state  # noqa: F401
    import tos.stm.vocabulary  # noqa: F401

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

    import tos.stm  # noqa: F401

    for planted in (
        "shared.config",
        "numpy",
        "tos.cur",  # forward-seam consumer — an import would invert the seam into a cycle
        "tos.spg",  # governed-artifact-kind owner — re-authored, not imported
        "tos.rlp",  # forward-seam consumer
        "tos.sir",  # forward-seam consumer
        "tos.rcl",  # rcl edge 0 — re-authored, not imported
        "tos.sci",  # ADR-002-029 — injected coordinate, never a code citation
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


def test_stm_tos_closure_is_within_the_allowlist() -> None:
    """(§7.1 allowlist) The tos closure ⊆ {canonical, ordering, stm} — no sibling leaks (edge 0)."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert (
        extra == []
    ), f"tos.stm closure escaped the §7.1 allowlist {sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"


def test_stm_closure_includes_only_the_two_core_packages() -> None:
    """(§7.1) tos.canonical + tos.ordering ARE present; NO sibling edge."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in ("tos.canonical", "tos.ordering", "tos.stm"):
        assert expected in tops, f"{expected} missing from the tos.stm closure"
    for sibling in _FORBIDDEN_SIBLINGS:
        assert sibling not in tops, f"{sibling} leaked into the tos.stm closure"


def test_stm_closure_has_no_forbidden_operational_package() -> None:
    """(design #30 §0.3 items 1-3) No shared.* operational package, no services/cli, no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert (
        result["forbidden"] == []
    ), f"forbidden packages reached the tos.stm closure: {result['forbidden']}"


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted config / numpy / cur / spg / rlp / sir / rcl / sci / future caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in (
        "tos.cur",
        "tos.spg",
        "tos.rlp",
        "tos.sir",
        "tos.rcl",
        "tos.sci",
        "tos.future_sibling",
    ):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits the three allowed packages and rejects every sibling (incl. cur / rcl)."""
    for allowed in (
        "tos.stm",
        "tos.stm.predicates",
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


def test_reauthored_predicates_are_absent_from_stm_authorship() -> None:
    """(§7.1, the #27 FD MAJOR-1 lesson) The sibling symbols are absent from **authorship**, not just
    from the export surface.

    An ``hasattr(tos.stm, name)`` check only locks the 87-symbol export surface, while the package
    *authors* several hundred names; ten of these sixteen could have been re-authored inside a module
    — never exported — and the whole suite would still have been green. The lock therefore runs against
    :func:`~tos.tests.stm.test_stm_anchor_resolution._authored_names`, which is the union of every
    module namespace **and** an AST sweep of every source, so a symbol nested in a class body or left
    out of ``__all__`` is caught too.
    """
    from .test_stm_anchor_resolution import _authored_names

    authored = _authored_names()
    offenders = sorted(name for name in _REAUTHORED_NOT_IMPORTED if name in authored)
    assert offenders == [], (
        f"{offenders} must be re-authored NOT AT ALL and imported NOT AT ALL — presence in tos.stm "
        "authorship means either a forbidden sibling import or a re-authoring of a sibling's owned "
        "judgement (design #30 §7.1/§3.5)"
    )
    # the export surface stays locked too — a strictly weaker check kept as a fast tripwire
    for name in _REAUTHORED_NOT_IMPORTED:
        assert not hasattr(tos.stm, name)


def test_the_authorship_lock_is_strictly_stronger_than_the_export_lock() -> None:
    """(canary) The authorship sweep really sees more than ``__all__`` — otherwise the fix is a no-op."""
    from .test_stm_anchor_resolution import _authored_names

    authored = _authored_names()
    exported = set(tos.stm.__all__)
    assert (
        exported < authored
    ), "the authorship sweep must be a strict superset of the export surface"
    # a real internal, never exported, must be visible to the sweep
    assert "_is_placeholder_reference" in authored
    assert "_is_placeholder_reference" not in exported


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


def test_stm_source_has_no_dynamic_escape_ambient_env_or_clock() -> None:
    """(design #30 §0.3 item 4) No tos.stm source uses exec/eval/importlib/os.environ or a real clock."""
    sources = _stm_sources()
    assert sources, f"no tos.stm source files found under {_STM_SRC}"
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


def test_stm_source_imports_no_forbidden_sibling_statically() -> None:
    """(design #30 §0.3 static mirror) No stm source contains an ``import tos.<sibling>`` statement."""
    offenders: list[str] = []
    for path in _stm_sources():
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
    assert offenders == [], f"forbidden sibling import in stm source: {offenders}"
