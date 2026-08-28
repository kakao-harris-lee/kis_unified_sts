"""§6.1 import-closure verification for ``tos.failuredomain`` — **allowlist** form (design #27 §0.3).

Written as an **allowlist** (design #27 §6.1): after importing every ``tos.failuredomain``
submodule in a fresh interpreter, the set of top-level ``tos.*`` packages in ``sys.modules`` must
be a subset of::

    {tos, tos.canonical, tos.failuredomain}

An enumerated denylist would go stale the moment a new sibling lands; the allowlist is
**future-robust** — any sibling, present or future, fails the assertion simply by appearing.
**sibling edge 0** — failuredomain has **no** sanctioned sibling edge at all, so its allowlist
admits exactly one core package.

**``tos.ordering`` is forbidden too** (design #27 §0.3/§6.1, unlike wdr / recon / nontrade): a
Failure-Domain Allocation Matrix row and an isolation claim carry no causal append-only order,
so there is nothing to compare and no reason to take the edge.

It also asserts (design #27 §0.3):

  1. no operational package is in the closure (``shared.execution`` / ``kis`` / ``streaming`` /
     ``llm`` / ``storage`` / ``backtest``, ``services.*``, ``cli.*``);
  2. neither ``shared.config`` nor ``shared.config.secrets`` is present, nor
     ``shared.determinism``;
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent (every bound is injected; YAML is the harness's);
  4. no ``tos.failuredomain`` source references ``os.environ`` / ``os.getenv``, a dynamic escape
     (``exec`` / ``eval`` / ``__import__`` / ``importlib``), or a real clock (``time`` /
     ``datetime``) — the matrix is a document-level shape, not a timed runtime;
  5. the sibling-absence assertion **explicitly includes the maximum re-authoring temptations**
     ``tos.sbr`` / ``tos.spg`` / ``tos.authority`` / ``tos.rcl`` / ``tos.egress`` / ``tos.cur`` /
     ``tos.time`` / ``tos.orthostate`` — the eight owners the design #27 §3.5 table attributes
     nearly the whole ADR to. They are re-authored NOT AT ALL and imported NOT AT ALL; their
     coordinates enter as injected owner tokens.

A planted-leak canary (including a *future* sibling ``tos.future_sibling`` and ``tos.ordering``
itself) proves the spawn+scan pipeline catches a leak no denylist could have anticipated; a
planted-AST-escape canary proves the static scan catches an escape — so "green" is evidence the
checker works, not that it has been neutered.

Regime tag: EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

import tos.failuredomain

#: The §6.1 allowlist: the only top-level ``tos.*`` packages the closure may contain.
_ALLOWED_TOS_PACKAGES = frozenset({"tos", "tos.canonical", "tos.failuredomain"})

#: Every real sibling + ``tos.ordering`` + a not-yet-invented one. The design #27 §3.5 owners
#: (sbr / spg / authority / rcl / egress / cur / time / orthostate) are the maximum re-authoring
#: temptations and are called out by construction.
_FORBIDDEN_SIBLINGS = frozenset(
    {
        "tos.afg",
        "tos.are",
        "tos.authority",  # §6.1 / §7 / §8.1 / §10 owner — re-authored not at all
        "tos.brokercap",
        "tos.capsule",
        "tos.cur",  # §8.2 / §8.3 owner — re-authored not at all
        "tos.dsl",
        "tos.egress",  # §6.3 / §10.1 owner — re-authored not at all
        "tos.evidence",
        "tos.hag",
        "tos.iap",
        "tos.ioc",
        "tos.liveauth",
        "tos.nontrade",
        "tos.ordering",  # design #27 §0.3 — no causal order on a matrix row
        "tos.orthostate",  # §14 / §10.1 item 3 owner — re-authored not at all
        "tos.posttrade",
        "tos.protective",
        "tos.rcl",  # §6.2 / §13 owner — re-authored not at all
        "tos.recon",
        "tos.replacement",
        "tos.rlp",
        "tos.sbr",  # §6.6 / §15 owner — the largest re-authoring trap (§3.5-1)
        "tos.spg",  # §10 / §11 owner — re-authored not at all (§3.5-2)
        "tos.time",  # §12 owner — re-authored not at all
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

_FD_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "failuredomain"
)

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules a document-level, non-timed package must never import.
_CLOCK_MODULES = frozenset({"time", "datetime"})

#: Sibling predicate / type names the design #27 §3.5 table attributes elsewhere — asserted
#: ABSENT from the failuredomain namespace (never re-authored, never imported; design #27 §6.1).
_REAUTHORED_NOT_IMPORTED = (
    "IsolationFacts",  # sbr — the recovery-isolation proof (§3.5-1)
    "restricted_isolation_proven",  # sbr
    "restore_worst_credible_union",  # sbr
    "competing_owner_fenced",  # sbr
    "hard_fence_proven",  # authority (one of six distinct fence owners, §3.5-3)
    "control_plane_verifiable",  # authority
    "GenerationVector",  # authority
    "rearm_gate",  # authority
    "writer_fenced",  # rcl
    "credible_union_capacity",  # rcl (§13 aggregate — the C2 deferral)
    "CapacityState",  # rcl
    "activation_atomic",  # spg (§3.5-2 — spg owns deployment wholesale)
    "rollback_requires_new_generation",  # spg
    "rollback_revives_nothing",  # spg
    "credential_route_authority_disjoint",  # egress
    "CredentialRouteInventoryEntry",  # egress
    "common_mode_group",  # time (§12)
    "independent_reference_count",  # time
    "ProofResult",  # cur (§8.3 — the runtime currentness mechanism)
    "CurrentnessAdmission",  # cur
    "fence_advances_floor",  # cur
    "KnowledgeState",  # orthostate
    "SEND_STARTED",  # orthostate
    "CapabilityStatus",  # brokercap
    "ScopeDimension",  # rlp (token overlap, different proposition)
    "gate_authority_separated",  # venue
    "mutation_fence_holds",  # ioc
    "stale_writer_hard_fenced",  # afg
)


def _tos_top_level(module_name: str) -> str | None:
    """The ``tos.<pkg>`` top-level package of ``module_name`` (``None`` if not a tos module)."""
    if module_name != "tos" and not module_name.startswith("tos."):
        return None
    parts = module_name.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else "tos"


def _is_allowed_tos_module(module_name: str) -> bool:
    """Whether a ``tos.*`` module is inside the §6.1 allowlist."""
    top = _tos_top_level(module_name)
    return top is None or top in _ALLOWED_TOS_PACKAGES


def _is_forbidden_non_tos(module_name: str) -> bool:
    """Whether a non-``tos`` module is a forbidden closure member (§0.3)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every failuredomain submodule; report the tos + forbidden closure."""
    import sys

    import tos.failuredomain  # noqa: F401
    import tos.failuredomain._base  # noqa: F401
    import tos.failuredomain.predicates  # noqa: F401
    import tos.failuredomain.records  # noqa: F401
    import tos.failuredomain.state  # noqa: F401
    import tos.failuredomain.vocabulary  # noqa: F401

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

    import tos.failuredomain  # noqa: F401

    for planted in (
        "shared.config",
        "numpy",
        "tos.sbr",  # maximum re-authoring temptation (§3.5-1)
        "tos.spg",  # maximum re-authoring temptation (§3.5-2)
        "tos.authority",
        "tos.rcl",
        "tos.egress",
        "tos.cur",
        "tos.ordering",  # deliberately NOT taken by this package (§0.3)
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


def test_failuredomain_tos_closure_is_within_the_allowlist() -> None:
    """(§6.1 allowlist) The tos closure ⊆ {canonical, failuredomain} — sibling edge 0."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert extra == [], (
        f"tos.failuredomain closure escaped the §6.1 allowlist "
        f"{sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"
    )


def test_failuredomain_closure_includes_only_canonical() -> None:
    """(§6.1) tos.canonical IS present; NO sibling edge, and NO tos.ordering edge."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in ("tos.canonical", "tos.failuredomain"):
        assert expected in tops, f"{expected} missing from the closure"
    for sibling in _FORBIDDEN_SIBLINGS:
        assert (
            sibling not in tops
        ), f"{sibling} leaked into the tos.failuredomain closure"
    assert "tos.ordering" not in tops, (
        "tos.failuredomain deliberately takes no ordering edge — a matrix row carries no "
        "causal append-only order (design #27 §0.3/§3.1)"
    )


def test_failuredomain_closure_has_no_forbidden_operational_package() -> None:
    """(§0.3 items 1-3) No shared.* operational package, no services/cli, no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert (
        result["forbidden"] == []
    ), f"forbidden packages reached the closure: {result['forbidden']}"


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted config / numpy / sbr / spg / ordering / future-sibling all caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in (
        "tos.sbr",
        "tos.spg",
        "tos.authority",
        "tos.rcl",
        "tos.egress",
        "tos.cur",
        "tos.ordering",
        "tos.future_sibling",
    ):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits the two allowed packages and rejects every sibling."""
    for allowed in (
        "tos.failuredomain",
        "tos.failuredomain.predicates",
        "tos.canonical",
        "tos.canonical._base",
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
    assert _is_forbidden_non_tos("enum") is False
    assert _is_forbidden_non_tos("click") is False  # must not false-match "cli"


def test_reauthored_predicates_are_absent_from_the_namespace() -> None:
    """(§6.1 / §3.5) Every sibling-owned predicate / type is NOT importable from failuredomain."""
    for name in _REAUTHORED_NOT_IMPORTED:
        assert not hasattr(tos.failuredomain, name), (
            f"{name} must be re-authored NOT AT ALL and imported NOT AT ALL — its presence in "
            "tos.failuredomain would mean a forbidden sibling import or a re-authoring "
            "(design #27 §3.5 / §6.1)"
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


def test_source_has_no_dynamic_escape_ambient_env_or_clock() -> None:
    """(§0.3 item 4) No source uses exec/eval/importlib/os.environ or a real clock."""
    sources = sorted(_FD_SRC.rglob("*.py"))
    assert sources, f"no tos.failuredomain source files found under {_FD_SRC}"
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


def test_source_imports_no_forbidden_sibling_statically() -> None:
    """(§0.3 static mirror) No source contains an ``import tos.<sibling>`` statement."""
    offenders: list[str] = []
    for path in sorted(_FD_SRC.rglob("*.py")):
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


def test_source_contains_no_numeric_literal_bound() -> None:
    """(§0.2 / §7) No number is hardcoded — every bound is injected or Phase-0 deferred.

    ADR-002-009's numeric bounds are ``B_failure_domain_detect`` (VERIFICATION-PROFILE-002 line
    611) and ``B_failure_domain_contain`` (line 618), both still ``null`` pending Phase-0
    approval, plus the blast-radius / cell-escalation keys that do not exist yet. None of them
    may appear here. Only the trivial literals a pure structural module needs (``0``) are
    tolerated, and even those are asserted to be comparison operands, not thresholds.
    """
    offenders: list[str] = []
    for path in sorted(_FD_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(
                node.value, (int, float, complex)
            ):
                if node.value in (0,) and not isinstance(node.value, bool):
                    continue
                if isinstance(node.value, bool):
                    continue
                offenders.append(
                    f"{path.name}:{node.lineno} numeric literal {node.value!r}"
                )
    assert offenders == [], f"hardcoded numeric bound found: {offenders}"
