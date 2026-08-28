"""Import-closure verification for ``tos.dsl`` (design §6.4 — structural backstop).

Isomorphic to ``test_import_closure.py`` (capsule) and ``test_evidence_import_
closure.py`` (evidence), extended to the Strategy DSL package. It imports every
``tos.dsl`` submodule in a **fresh, spawned interpreter** (``subprocess``/``os`` are
firewall-forbidden even in tests) and asserts the closure is the structural backstop
of DCE-EV-003 (no ambient authority) and EXV-INV-001 (captured, not called):

  1. No design §2.3 operational package is present (``shared.execution``/``kis``/
     ``streaming``/``llm``/``storage``/``backtest``, ``services.*``, ``cli.*``).
  2. Neither ``shared.config`` nor ``shared.config.secrets`` is present (C1 — the
     transitive ambient-credential intake), and neither is ``shared.determinism``
     (the pure DSL has no operational-time dependency).
  3. ``numpy``/``pandas`` are absent (closure minimisation, design §0.3).
  4. Network stdlib (``socket``/``ssl``/…) is NOT asserted absent from the closure:
     ``pydantic`` transitively loads it into *every* tos package closure (even the
     pure ``tos.canonical``), and design #1 §4 / #2 §4 explicitly accept a
     transitively-loaded stdlib network primitive as residual risk (no credential,
     route, or order-construction ⇒ not a live-order interface, SAFE-045 layered
     defense). The DIRECT-import ban on network stdlib in tos *source* is enforced by
     the firewall gate (TOS-FW-B) alone — not by closure membership, and NOT by the
     item-7 AST source scan (that scan only looks for importlib/os.environ/exec/eval,
     never socket/ssl/http/urllib). (The sibling capsule/evidence/time closure tests
     likewise do not assert network-stdlib absence.)
  5. ``tos.evidence`` is **absent** — the DSL is deliberately kept free of the
     evidence package (``tos.dsl._base`` re-exports ``IndependentIdArtifact`` from
     ``tos.canonical`` — PROMOTEd by design #6 §0.4c; ``tos.canonical`` imports no
     ``tos.evidence``, so the evidence-absence guarantee is preserved
     precisely for this; design §firewall). NB: the sibling ``tos.dsl.evidence`` is a
     different module and is NOT flagged.
  6. ``tos.capsule`` **is present** — the Decision Context Capsule is a legitimate
     read-only evaluation input (``tos.dsl.determinism`` imports it; design §0/§4,
     captured-not-called). This is asserted present, not absent.
  7. No ``tos.dsl`` source references ``os.environ``/``os.getenv`` or any dynamic
     escape (``exec``/``eval``/``__import__``/``importlib``) — AST-scan reinforcement
     that the escape-checker itself obeys the firewall (design §3.2).

A planted-leak canary proves the spawn+scan pipeline actually catches a leak, so
"green" is evidence the checker works — not that it was neutered.

(Reconciliation note: the parent task brief asked to assert ``tos.capsule`` absence.
That contradicts ``tos.dsl.determinism``'s legitimate read-only Capsule import and
design §6.4/§0/§4; the normative spec + actual code win — ``tos.capsule`` is asserted
*present*, and only ``tos.evidence`` is asserted absent.)
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

# Forbidden exact names + dotted prefixes: §2.3 operational set + C1 (shared.config
# [.secrets]) + shared.determinism + numpy/pandas + tos.evidence.
# NB: tos.capsule is intentionally NOT here (present, read-only input). Network
# stdlib (socket/ssl/…) is intentionally NOT here either — pydantic loads it into
# every tos closure; it is accepted residual risk (design #1 §4 / #2 §4), and the
# network-stdlib direct-import ban is enforced by the firewall gate (TOS-FW-B) alone
# (the item-7 AST source scan does not inspect socket/ssl/http/urllib).
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
        "tos.evidence",
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
    "tos.evidence.",
)

_DSL_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "dsl"

# Dynamic-escape call names (data, never invoked here) for the AST source scan.
_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})


def _is_forbidden(module_name: str) -> bool:
    """Whether ``module_name`` is a forbidden member of the tos.dsl closure (design §6.4)."""
    if module_name in _FORBIDDEN_EXACT:
        return True
    return module_name.startswith(_FORBIDDEN_PREFIXES)


def _closure_child(queue: mp.Queue) -> None:
    """Child target: import every tos.dsl submodule; report forbidden members + capsule presence."""
    import sys

    import tos.dsl  # noqa: F401
    import tos.dsl._base  # noqa: F401
    import tos.dsl.admissibility  # noqa: F401
    import tos.dsl.bounds  # noqa: F401
    import tos.dsl.candidate  # noqa: F401
    import tos.dsl.determinism  # noqa: F401
    import tos.dsl.evidence  # noqa: F401
    import tos.dsl.outcome  # noqa: F401
    import tos.dsl.proposal  # noqa: F401
    import tos.dsl.strategy  # noqa: F401
    import tos.dsl.vocabulary  # noqa: F401

    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put(
        {
            "leaked": leaked,
            "capsule_present": "tos.capsule.capsule" in sys.modules,
        }
    )


def _leak_canary_child(queue: mp.Queue) -> None:
    """Child target: plant fake forbidden modules, then run the same scan."""
    import sys
    import types

    import tos.dsl  # noqa: F401

    sys.modules["shared.config"] = types.ModuleType("shared.config")
    sys.modules["tos.evidence"] = types.ModuleType("tos.evidence")
    sys.modules["numpy"] = types.ModuleType("numpy")
    leaked = sorted(name for name in sys.modules if _is_forbidden(name))
    queue.put({"leaked": leaked, "capsule_present": None})


def _run_child(target) -> dict:
    """Spawn ``target`` in a clean interpreter and return its reported result dict."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    # Read before join: the child stays alive until its small result is drained,
    # so join cannot race ahead of a full-pipe writer (mirrors the evidence test).
    result = queue.get(timeout=60)
    proc.join(timeout=60)
    assert proc.exitcode == 0, f"closure child exited abnormally: {proc.exitcode}"
    return result


def test_dsl_import_closure_has_no_forbidden_packages() -> None:
    """(items 1-3, 5) A fresh import of tos.dsl pulls no forbidden package."""
    result = _run_child(_closure_child)
    assert result["leaked"] == [], f"forbidden closure members: {result['leaked']}"


def test_dsl_closure_includes_capsule_as_read_only_input() -> None:
    """(item 6) tos.capsule IS present — the read-only Decision Context Capsule input (design §0/§4)."""
    result = _run_child(_closure_child)
    assert result["capsule_present"] is True, "capsule missing from closure"


def test_leak_canary_is_detected() -> None:
    """The spawn+scan pipeline catches planted shared.config + tos.evidence + numpy leaks."""
    result = _run_child(_leak_canary_child)
    leaked = result["leaked"]
    assert "shared.config" in leaked, "planted shared.config leak was NOT detected"
    assert "tos.evidence" in leaked, "planted tos.evidence leak was NOT detected"
    assert "numpy" in leaked, "planted numpy leak was NOT detected"


def test_is_forbidden_classifier_canaries() -> None:
    """The classifier flags forbidden names and clears the allowed / present ones."""
    # Positive: forbidden exacts + dotted children (§2.3 operational, C1, numpy/pandas,
    # tos.evidence).
    assert _is_forbidden("shared.config") is True
    assert _is_forbidden("shared.config.secrets") is True
    assert _is_forbidden("shared.determinism") is True
    assert _is_forbidden("shared.llm.market") is True
    assert _is_forbidden("services.dashboard") is True
    assert _is_forbidden("numpy") is True
    assert _is_forbidden("pandas.core") is True
    assert _is_forbidden("tos.evidence") is True
    assert _is_forbidden("tos.evidence.ledger") is True
    # Negative: self, the read-only capsule input, third-party, the sibling
    # tos.dsl.evidence module, and network stdlib (accepted residual — item 4; the
    # network-stdlib direct-import ban is the firewall gate (TOS-FW-B) alone, not
    # closure and not the item-7 source scan).
    assert _is_forbidden("tos.dsl") is False
    assert _is_forbidden("tos.dsl.evidence") is False  # sibling, not tos.evidence
    assert _is_forbidden("tos.capsule") is False  # present read-only input
    assert _is_forbidden("tos.capsule.capsule") is False
    assert _is_forbidden("tos.canonical") is False
    assert _is_forbidden("pydantic") is False
    assert _is_forbidden("socket") is False  # accepted residual (pydantic baseline)
    assert _is_forbidden("ssl") is False
    assert _is_forbidden("http.client") is False
    assert _is_forbidden("urllib.request") is False
    assert _is_forbidden("urllib.parse") is False
    assert _is_forbidden("click") is False  # must not false-match the "cli" prefix


def _ast_escape_offenders(path: Path) -> list[str]:
    """Return dynamic-escape / ambient-env offenders in one source file (static AST scan)."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        # importlib import (statement form)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith("importlib."):
                    offenders.append(f"{path.name}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "importlib":
                offenders.append(f"{path.name}:{node.lineno} from importlib import ...")
            if node.module == "os":
                for alias in node.names:
                    if alias.name in _AMBIENT_ENV_ATTRS:
                        offenders.append(
                            f"{path.name}:{node.lineno} from os import {alias.name}"
                        )
        # dynamic-eval / dynamic-import calls
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _DYNAMIC_CALL_NAMES:
                offenders.append(f"{path.name}:{node.lineno} call {func.id}()")
            elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                offenders.append(f"{path.name}:{node.lineno} call import_module()")
        # os.environ / os.getenv attribute access
        elif isinstance(node, ast.Attribute):
            if (
                node.attr in _AMBIENT_ENV_ATTRS
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                offenders.append(f"{path.name}:{node.lineno} os.{node.attr}")
    return offenders


def test_dsl_source_has_no_dynamic_escape_or_ambient_env() -> None:
    """(item 7) No tos.dsl source uses exec/eval/importlib/__import__ or os.environ (design §3.2)."""
    sources = sorted(_DSL_SRC.rglob("*.py"))
    assert sources, f"no tos.dsl source files found under {_DSL_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_ast_escape_offenders(path))
    assert offenders == [], f"dynamic-escape / ambient-env access found: {offenders}"


def test_ast_scan_detects_planted_escape(tmp_path: Path) -> None:
    """The AST escape scan actually catches planted escapes (not vacuously green)."""
    planted = tmp_path / "planted.py"
    # Written as source text; never executed. Exercises each offender branch.
    planted.write_text(
        "import importlib\n"
        "from os import environ\n"
        "value = os.getenv\n"
        "a = eval\n",  # bare name — but the scan also has a call branch below
        encoding="utf-8",
    )
    # Add a real call form so the ast.Call branch is exercised too.
    planted.write_text(
        planted.read_text(encoding="utf-8") + "b = __import__('x')\n",
        encoding="utf-8",
    )
    offenders = _ast_escape_offenders(planted)
    joined = " ".join(offenders)
    assert "import importlib" in joined
    assert "from os import environ" in joined
    assert "os.getenv" in joined
    assert "__import__()" in joined
