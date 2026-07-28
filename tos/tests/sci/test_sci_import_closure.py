"""§6.1 import-closure verification for ``tos.sci`` — **allowlist** form (design #29 §0.3/§6.1).

After importing every ``tos.sci`` submodule in a fresh interpreter, the set of top-level ``tos.*``
packages in ``sys.modules`` must be a subset of::

    {tos, tos.canonical, tos.ordering, tos.sci}

An enumerated denylist would go stale the moment a new sibling lands; the allowlist is
**future-robust** — any sibling, present or future, fails the assertion simply by appearing.
**sibling edge 0** (design #29 §3.4): ``tos.canonical`` (digest substrate) and ``tos.ordering``
(Release Generation / restriction-floor order) are the only two sanctioned edges, and **rcl edge 0**
in particular is deliberate (§7 line 235 "Mutate or release capacity | Risk Capacity Ledger only |
artifact lifecycle never writes capacity").

It also asserts (design #29 §0.3):

  1. no operational package is in the closure (``shared.execution`` / ``kis`` / ``streaming`` /
     ``llm`` / ``storage`` / ``backtest``, ``services.*``, ``cli.*``);
  2. neither ``shared.config`` nor ``shared.config.secrets`` is present, nor ``shared.determinism``;
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent (every bound is injected);
  4. no ``tos.sci`` source references ``os.environ`` / ``os.getenv``, a dynamic escape (``exec`` /
     ``eval`` / ``__import__`` / ``importlib``), or a real clock (``time`` / ``datetime``) — release
     admission is an ordering-scalar protocol, not a timed runtime;
  5. **authoring-level locking (the FD #27 lesson)**: the sweep runs over each submodule's
     ``vars()`` *and* its AST, not only the package's export surface, so a sibling imported into a
     submodule but never re-exported is still caught.

A planted-leak canary (including a *future* sibling ``tos.future_sibling``) proves the spawn+scan
pipeline catches a leak no denylist could have anticipated; a planted-AST-escape canary proves the
static scan catches an escape — so "green" is evidence the checker works, not that it is neutered.

Regime tag: release-admission predicate/model substrate only; closes no SCI-EV; +Security 12/12.
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path
from types import ModuleType

import tos.sci

#: The §6.1 allowlist: the only top-level ``tos.*`` packages the closure may contain.
_ALLOWED_TOS_PACKAGES = frozenset({"tos", "tos.canonical", "tos.ordering", "tos.sci"})

#: Every real sibling + a not-yet-invented one. The design #29 §3.5 owners (spg / hag / rcl / cur /
#: egress / failuredomain / posttrade / rlp / evidence / sbr / liveauth / authority / protective /
#: dsl) are the maximum re-authoring temptations and are called out by construction. ``tos.sir`` is
#: listed too: ADR-002-027 landed mid-implementation and its incident coordinate is still an
#: injected opaque scalar — the seam is test-only (``test_seam_sir.py``), the runtime edge is zero.
_FORBIDDEN_SIBLINGS = frozenset(
    {
        "tos.afg",
        "tos.are",
        "tos.authority",  # §7 epoch owner — re-authored not at all
        "tos.brokercap",
        "tos.capsule",
        "tos.cur",  # §16/§20 restriction-floor advance owner (M4) — re-authored not at all
        "tos.dsl",  # AdmissibilityResult is a different proposition, not a seam (§3.5)
        "tos.egress",  # §19 final-egress owner — re-authored not at all
        "tos.evidence",  # §24 custody owner
        "tos.failuredomain",  # RFC-002 §24.1 supply-chain *coordinates* (§0.4d)
        "tos.hag",  # §9 effective-principal collapse owner (§0.4e)
        "tos.iap",
        "tos.ioc",
        "tos.liveauth",
        "tos.nontrade",
        "tos.orthostate",
        "tos.posttrade",  # ADR-002-030 — landed, still edge 0 (§3.5 item split)
        "tos.protective",
        "tos.rcl",  # §7 line 235 capacity owner — rcl edge 0 (§0.4g)
        "tos.recon",
        "tos.replacement",
        "tos.rlp",  # §17 production-promotion owner
        "tos.sbr",  # §24 recovery owner
        "tos.sir",  # ADR-002-027 — landed mid-implementation; still edge 0 (§0.4f, test_seam_sir)
        "tos.spg",  # §8/§13 activation owner + the software_deployment_ok consumer (§3.5-1)
        "tos.stm",  # ADR-002-028 — not landed
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

_SCI_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "sci"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules an ordering-scalar package must never import (§3.2 — no clock).
_CLOCK_MODULES = frozenset({"time", "datetime"})

#: Sibling-owned predicate / type names the design #29 §3.5 table attributes elsewhere — asserted
#: ABSENT from the sci namespace (never re-authored, never imported).
_REAUTHORED_NOT_IMPORTED = (
    "fence_advances_floor",  # cur — the restriction-floor ADVANCE mechanism (§3.5 M4)
    "RestrictiveFenceRecord",  # cur
    "floor_strictly_advances",  # cur
    "ProofResult",  # cur — the per-send currentness mechanism
    "CapacityVector",  # rcl — §7 line 235, capacity is the ledger's alone (§0.4g)
    "within_limits",  # rcl
    "effective_principal_collapse",  # hag — §9 line 267 (§0.4e)
    "HardSafetyEnvelope",  # spg — §8 / §13
    "profile_within_envelope",  # spg
    "SemanticValidationInputs",  # spg — the software_deployment_ok CONSUMER (§3.5-1)
    "activation_atomic",  # spg — §13 configuration activation
    "AdmissibilityResult",  # dsl — a different proposition, explicitly not a seam (§3.5)
    "FailureDomainKind",  # failuredomain — the four supply-chain COORDINATES (§0.4d)
    "SOURCE_REPOSITORY",  # failuredomain coordinate
    "BUILD_TOOLCHAIN",  # failuredomain coordinate
    "ARTIFACT_SIGNING",  # failuredomain coordinate
    "ARTIFACT_REGISTRY",  # failuredomain coordinate
    "is_wildcard_value",  # rlp — the shape is re-expressed locally under a different name
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
    """Child target: import every sci submodule; report the tos + forbidden closure."""
    import sys

    import tos.sci  # noqa: F401
    import tos.sci._base  # noqa: F401
    import tos.sci.predicates  # noqa: F401
    import tos.sci.records  # noqa: F401
    import tos.sci.state  # noqa: F401
    import tos.sci.vocabulary  # noqa: F401

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

    import tos.sci  # noqa: F401

    for planted in (
        "shared.config",
        "numpy",
        "tos.spg",  # the landed downstream consumer — still edge 0 (§3.5-1)
        "tos.cur",  # the floor-advance owner (§3.5 M4)
        "tos.hag",
        "tos.rcl",
        "tos.failuredomain",
        "tos.posttrade",
        "tos.sir",  # landed mid-implementation; still edge 0 (§0.4f)
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


def _run_child(target) -> dict:  # type: ignore[no-untyped-def]
    """Spawn ``target`` in a clean interpreter and return its reported result dict."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    result = queue.get(timeout=60)
    proc.join(timeout=60)
    assert proc.exitcode == 0, f"closure child exited abnormally: {proc.exitcode}"
    return result


def test_sci_tos_closure_is_within_the_allowlist() -> None:
    """(§6.1 allowlist) The tos closure ⊆ {canonical, ordering, sci} — sibling edge 0."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert (
        extra == []
    ), f"tos.sci closure escaped the §6.1 allowlist {sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"


def test_sci_closure_includes_canonical_and_ordering_only() -> None:
    """(§3.3) Both sanctioned core edges ARE present; NO sibling edge is."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in ("tos.canonical", "tos.ordering", "tos.sci"):
        assert expected in tops, f"{expected} missing from the closure"
    for sibling in _FORBIDDEN_SIBLINGS:
        assert sibling not in tops, f"{sibling} leaked into the tos.sci closure"


def test_sci_closure_has_no_forbidden_operational_package() -> None:
    """(§0.3 items 1-3) No shared.* operational package, no services/cli, no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert (
        result["forbidden"] == []
    ), f"forbidden packages reached the closure: {result['forbidden']}"


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted config / numpy / spg / cur / sir / future-sibling are all caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in (
        "tos.spg",
        "tos.cur",
        "tos.hag",
        "tos.rcl",
        "tos.failuredomain",
        "tos.posttrade",
        "tos.sir",
        "tos.future_sibling",
    ):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits the three allowed packages and rejects every sibling."""
    for allowed in (
        "tos.sci",
        "tos.sci.predicates",
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
    assert _is_forbidden_non_tos("enum") is False
    assert _is_forbidden_non_tos("click") is False  # must not false-match "cli"


def test_reauthored_names_are_absent_from_the_package_surface() -> None:
    """(§6.1 / §3.5) Every sibling-owned predicate / type is NOT importable from tos.sci."""
    for name in _REAUTHORED_NOT_IMPORTED:
        assert not hasattr(tos.sci, name), (
            f"{name} must be re-authored NOT AT ALL and imported NOT AT ALL — its presence in "
            "tos.sci would mean a forbidden sibling import or a re-authoring (design #29 §3.5)"
        )


def _submodules() -> list[ModuleType]:
    """Every ``tos.sci`` submodule object (the authoring level, not the export surface)."""
    import tos.sci._base
    import tos.sci.predicates
    import tos.sci.records
    import tos.sci.state
    import tos.sci.vocabulary

    return [
        tos.sci,
        tos.sci._base,
        tos.sci.predicates,
        tos.sci.records,
        tos.sci.state,
        tos.sci.vocabulary,
    ]


def test_authoring_level_vars_sweep_finds_no_sibling_binding() -> None:
    """(FD #27 lesson) The lock is at the **authoring** level, not the export surface.

    A sibling imported into ``records.py`` but never re-exported from ``__init__.py`` would pass a
    surface-only check. This sweeps every submodule's ``vars()`` for a module object or a class
    whose defining module is a forbidden sibling.
    """
    offenders: list[str] = []
    for module in _submodules():
        for name, value in vars(module).items():
            if isinstance(value, ModuleType):
                if not _is_allowed_tos_module(value.__name__) or _is_forbidden_non_tos(
                    value.__name__
                ):
                    offenders.append(f"{module.__name__}.{name} -> {value.__name__}")
                continue
            origin = getattr(value, "__module__", None)
            if isinstance(origin, str) and origin.startswith("tos."):
                if not _is_allowed_tos_module(origin):
                    offenders.append(f"{module.__name__}.{name} defined in {origin}")
        for name in _REAUTHORED_NOT_IMPORTED:
            assert name not in vars(
                module
            ), f"{module.__name__} binds the sibling-owned name {name} (design #29 §3.5)"
    assert offenders == [], f"authoring-level sibling binding found: {offenders}"


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
    sources = sorted(_SCI_SRC.rglob("*.py"))
    assert sources, f"no tos.sci source files found under {_SCI_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_escape_offenders(path))
    assert (
        offenders == []
    ), f"dynamic-escape / ambient-env / clock access found: {offenders}"


def test_ast_scan_detects_planted_escape(tmp_path: Path) -> None:
    """(both-ways) The AST escape scan actually catches planted escapes + a real-clock import."""
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
    for path in sorted(_SCI_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if not _is_allowed_tos_module(name) or _is_forbidden_non_tos(name):
                    offenders.append(f"{path.name}:{node.lineno} import {name}")
    assert offenders == [], f"forbidden sibling import in source: {offenders}"


def test_source_contains_no_numeric_literal_bound() -> None:
    """(§8) No number is hardcoded — every bound is injected or Phase-0 deferred.

    ADR §29 item 12 names ten VERIFICATION-PROFILE-002 keys
    (``B_supply_chain_compromise_detect`` … ``MAX_release_key_status_age_ms``), all still ``null``
    with ``owner: TBD`` pending Phase-0 approval. None of them may appear here as a literal. Only
    the trivial literals a pure structural module needs (``0``) are tolerated.
    """
    offenders: list[str] = []
    for path in sorted(_SCI_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(
                node.value, (int, float, complex)
            ):
                if isinstance(node.value, bool):
                    continue
                if node.value in (0,):
                    continue
                offenders.append(
                    f"{path.name}:{node.lineno} numeric literal {node.value!r}"
                )
    assert offenders == [], f"hardcoded numeric bound found: {offenders}"


#: The ten ADR §29 item 12 VERIFICATION-PROFILE-002 keys — all ``null`` / ``owner: TBD`` (§8).
_VERIFICATION_PROFILE_KEYS = (
    "B_supply_chain_compromise_detect",
    "B_release_restriction_to_authority_restrict",
    "B_release_restriction_to_egress_deny",
    "B_release_generation_fence",
    "B_runtime_artifact_drift_detect",
    "MAX_build_provenance_age_ms",
    "MAX_artifact_admission_decision_age_ms",
    "MAX_admitted_release_set_age_ms",
    "MAX_runtime_artifact_attestation_age_ms",
    "MAX_release_key_status_age_ms",
)


def _executable_string_literals(path: Path) -> list[str]:
    """Every string constant that is *code*, excluding docstrings / bare string expressions."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstring_nodes = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstring_nodes
    ]


def test_source_binds_no_verification_profile_key_in_code() -> None:
    """(§8 / anti-phantom) SCI authors zero VP-002 keys and hardcodes zero bound values.

    The ten ADR §29 item 12 keys are referenced in **prose** (the ``__init__`` docstring names them
    so the deferral is explicit), but no executable string literal binds one: the
    ``maximum_age_key`` slot is a plain ``str | None`` an INSTANCE fills, never a default written
    here.
    """
    offenders: list[str] = []
    for path in sorted(_SCI_SRC.rglob("*.py")):
        for literal in _executable_string_literals(path):
            if literal in _VERIFICATION_PROFILE_KEYS:
                offenders.append(f"{path.name}: {literal}")
    assert (
        offenders == []
    ), f"a VERIFICATION-PROFILE-002 key is bound in code: {offenders}"


def test_verification_profile_deferral_is_documented() -> None:
    """(§8) The ten keys are named in prose so the Phase-0 deferral is explicit, not silent."""
    doc = tos.sci.__doc__ or ""
    for key in _VERIFICATION_PROFILE_KEYS:
        assert key in doc, f"{key} is not named in the §8 deferral note"
