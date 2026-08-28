"""§7.1 import-closure verification for ``tos.rlp`` — **allowlist** form (design #25 §0.3/§7.1).

Written as an **allowlist** (design #25 §7.1): after importing every ``tos.rlp`` submodule in a fresh
interpreter, the set of top-level ``tos.*`` packages in ``sys.modules`` must be a subset of::

    {tos, tos.canonical, tos.ordering, tos.rlp}

An enumerated denylist would go stale the moment a new sibling lands; the allowlist is
**future-robust** — any sibling, present or future (including ``tos.wdr`` / ``tos.sir`` /
``tos.stm`` / ``tos.sci`` / ``tos.posttrade``, all of which landed after rlp),
fails the assertion simply by appearing. **sibling edge 0** — rlp has **no** sanctioned sibling edge,
so its allowlist admits only the two core packages.

It also asserts (design #25 §0.3):

  1. no operational package is in the closure (``shared.execution`` / ``kis`` / ``streaming`` /
     ``llm`` / ``storage`` / ``backtest``, ``services.*``, ``cli.*``);
  2. neither ``shared.config`` nor ``shared.config.secrets`` is present (transitive ambient-
     credential intake), nor ``shared.determinism``;
  3. ``numpy`` / ``pandas`` / ``yaml`` are absent (bounds are injected; YAML is the harness's);
  4. no ``tos.rlp`` source references ``os.environ`` / ``os.getenv``, a dynamic escape
     (``exec`` / ``eval`` / ``__import__`` / ``importlib``), or a real clock (``time`` /
     ``datetime``) — rlp is **clock-free** (§0.4g: a Promotion Generation is an ordering identity, not
     wall-clock);
  5. the sibling-absence assertion **explicitly includes ``tos.egress`` / ``tos.cur`` / ``tos.hag`` /
     ``tos.evidence`` / ``tos.rcl`` / ``tos.iap``** (the maximum re-authoring temptations — the egress
     ``QuorumCommitCertificate`` / cur RESTRICTED_LIVE_TRIAL dimension / hag effective-principal +
     quorum / evidence ``SegmentCommitmentScheme`` / rcl ``CapacityVector`` / iap single-use shape are
     re-authored NOT AT ALL and imported NOT AT ALL — produced facts injected as scalars / verdicts /
     digests, §0.4b-g; a rlp → egress / cur import would additionally be a **cycle** since egress /
     cur consume rlp, §3.4).

A planted-leak canary (including ``tos.egress`` / ``tos.cur`` / the placeholder name ``tos.ptf`` /
``tos.future_sibling`` / ``shared.config``) proves the spawn+scan pipeline catches a leak no denylist
could have anticipated; a planted-AST-escape canary proves the static scan catches an escape — so
"green" is evidence the checker works, not that it has been neutered.
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

import tos.rlp

#: The §7.1 allowlist: the only top-level ``tos.*`` packages the rlp closure may contain.
_ALLOWED_TOS_PACKAGES = frozenset({"tos", "tos.canonical", "tos.ordering", "tos.rlp"})

#: The forbidden siblings (all real siblings, including ``tos.wdr`` / ... which landed after rlp, + a future
#: ``tos.future_sibling``) — INCLUDING the maximum re-authoring temptations ``tos.egress`` /
#: ``tos.cur`` / ``tos.hag`` / ``tos.evidence`` / ``tos.rcl`` / ``tos.iap`` (re-authored NOT AT ALL,
#: imported NOT AT ALL; a rlp → egress / cur import would be a cycle).
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
        "tos.hag",
        "tos.iap",
        "tos.ioc",
        "tos.liveauth",
        "tos.nontrade",
        "tos.orthostate",
        "tos.protective",
        "tos.rcl",
        "tos.recon",
        "tos.replacement",
        "tos.sbr",
        "tos.spg",
        "tos.time",
        "tos.venue",
        "tos.wdr",  # landed sibling — still excluded (sibling edge 0)
        "tos.sir",  # landed sibling — still excluded (sibling edge 0)
        "tos.stm",  # landed sibling — still excluded (sibling edge 0)
        "tos.sci",  # landed sibling — still excluded (sibling edge 0)
        "tos.posttrade",  # landed sibling — still excluded (sibling edge 0)
        "tos.ptf",  # historical placeholder — landed as tos.posttrade (above); kept, never importable
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

_RLP_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "rlp"

_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})
#: Real-clock modules that must never be imported by a clock-free rlp source (§0.4g).
_CLOCK_MODULES = frozenset({"time", "datetime"})

#: The re-authored (never imported) sibling predicate / type names — asserted ABSENT from the rlp
#: namespace (local authorship, not an import; design #25 §7.1).
_REAUTHORED_NOT_IMPORTED = (
    "QuorumCommitCertificate",  # egress
    "SafetyCurrentnessVector",  # cur
    "SegmentCommitmentScheme",  # evidence
    "causal_chain_complete",  # evidence (rlp consumes it as an injected bool, never imports it)
    "effective_principal_collapse",  # hag
    "quorum_independence_satisfied",  # hag
    "CapacityVector",  # rcl
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
    """Whether a non-``tos`` module is a forbidden closure member (§0.3)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every tos.rlp submodule; report the tos + forbidden closure."""
    import sys

    import tos.rlp  # noqa: F401
    import tos.rlp._base  # noqa: F401
    import tos.rlp.predicates  # noqa: F401
    import tos.rlp.records  # noqa: F401
    import tos.rlp.state  # noqa: F401
    import tos.rlp.vocabulary  # noqa: F401

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

    import tos.rlp  # noqa: F401

    for planted in (
        "shared.config",
        "numpy",
        "tos.egress",  # maximum re-authoring temptation — re-authored, not imported (cycle)
        "tos.cur",  # maximum re-authoring temptation — re-authored, not imported (cycle)
        "tos.hag",  # maximum re-authoring temptation — re-authored, not imported
        "tos.evidence",  # maximum re-authoring temptation — re-authored, not imported
        "tos.ptf",  # historical placeholder name the allowlist catches all the same
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


def test_rlp_tos_closure_is_within_the_allowlist() -> None:
    """(§7.1 allowlist) The tos closure ⊆ {canonical, ordering, rlp} — no sibling leaks (edge 0)."""
    result = _run_child(_closure_child)
    extra = sorted(set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES)
    assert (
        extra == []
    ), f"tos.rlp closure escaped the §7.1 allowlist {sorted(_ALLOWED_TOS_PACKAGES)}: {extra}"


def test_rlp_closure_includes_only_the_two_core_packages() -> None:
    """(§7.1) tos.canonical + tos.ordering ARE present; NO sibling edge."""
    result = _run_child(_closure_child)
    tops = set(result["tos_tops"])
    for expected in ("tos.canonical", "tos.ordering", "tos.rlp"):
        assert expected in tops, f"{expected} missing from the tos.rlp closure"
    for sibling in _FORBIDDEN_SIBLINGS:
        assert sibling not in tops, f"{sibling} leaked into the tos.rlp closure"


def test_rlp_closure_has_no_forbidden_operational_package() -> None:
    """(§0.3 items 1-3) No shared.* operational package, no services/cli, no numpy/pandas/yaml."""
    result = _run_child(_closure_child)
    assert (
        result["forbidden"] == []
    ), f"forbidden packages reached the tos.rlp closure: {result['forbidden']}"


def test_leak_canary_is_detected() -> None:
    """(both-ways) Planted config / numpy / egress / cur / hag / evidence / ptf / future-sibling caught."""
    result = _run_child(_leak_canary_child)
    extra = set(result["tos_tops"]) - _ALLOWED_TOS_PACKAGES
    for expected in (
        "tos.egress",
        "tos.cur",
        "tos.hag",
        "tos.evidence",
        "tos.ptf",
        "tos.future_sibling",
    ):
        assert expected in extra, f"planted {expected} leak was NOT detected"
    for expected in ("shared.config", "numpy"):
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


def test_allowlist_classifier_canaries() -> None:
    """The classifier admits the three allowed packages and rejects every sibling (incl. egress / cur)."""
    for allowed in (
        "tos.rlp",
        "tos.rlp.predicates",
        "tos.canonical",
        "tos.canonical._base",
        "tos.ordering",
    ):
        assert _is_allowed_tos_module(allowed) is True
    for sibling in _FORBIDDEN_SIBLINGS | {"tos.not_yet_invented"}:
        assert _is_allowed_tos_module(sibling) is False
        assert _is_allowed_tos_module(sibling + ".predicates") is False
    # non-tos classification
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


def test_reauthored_predicates_are_absent_from_rlp_namespace() -> None:
    """(§7.1) The re-authored sibling predicates / types are NOT importable from tos.rlp."""
    for name in _REAUTHORED_NOT_IMPORTED:
        assert not hasattr(tos.rlp, name), (
            f"{name} must be re-authored NOT AT ALL and imported NOT AT ALL — its presence in "
            "tos.rlp would mean a forbidden sibling import (§7.1)"
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


def test_rlp_source_has_no_dynamic_escape_ambient_env_or_clock() -> None:
    """(§0.3 item 4) No tos.rlp source uses exec/eval/importlib/os.environ or a real clock."""
    sources = sorted(_RLP_SRC.rglob("*.py"))
    assert sources, f"no tos.rlp source files found under {_RLP_SRC}"
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


def test_rlp_source_imports_no_forbidden_sibling_statically() -> None:
    """(§0.3 static mirror) No rlp source contains an ``import tos.<sibling>`` statement."""
    offenders: list[str] = []
    for path in sorted(_RLP_SRC.rglob("*.py")):
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
    assert offenders == [], f"forbidden sibling import in rlp source: {offenders}"
