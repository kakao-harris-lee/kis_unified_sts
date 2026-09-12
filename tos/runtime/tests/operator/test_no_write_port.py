"""Structural + negative-grep proof that ``tos_runtime.operator`` holds zero write ports (TOS
Phase 5 W4 plan §2 decision 8a).

Mirrors ``tos/runtime/tests/engine/test_no_direct_latch_clear.py``'s two-part idiom: (1) a
receiver-shape regex over every real file under ``operator/`` — with NO allowlist here (unlike
that test's single permitted caller-file carve-out): this package must never contain a write
receiver shape, full stop — and (2) a synthetic-string self-test proving the regex actually
catches every real receiver shape it claims to, rather than passing vacuously because the regex
itself is too narrow. Also asserts, via an AST import scan, that no file under ``operator/``
imports any of the five write-capable modules plan §2 decision 8a names.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_OPERATOR_SRC_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "tos_runtime" / "operator"
)

#: plan §2 decision 8a — the five write-capable modules ``tos_runtime.operator`` must never
#: import, directly or as a submodule of these prefixes.
_FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "tos_runtime.transport",
    "tos_runtime.rcl",
    "tos_runtime.engine.driver",
    "tos_runtime.evidence.store",
    "tos.egressgw",
)

#: plan §2 decision 8b's exact receiver-shape regex: any of these method names, called on
#: anything (``[\w.]*`` — a bare name, an attribute chain, ``self._x.y``, etc.), immediately
#: followed by ``(``. Deliberately NOT a naive substring match (a prose mention or a ``def``
#: line for one of these names must not trip it) and deliberately NOT anchored with ``\b`` at the
#: front (independent-review finding MEDIUM-7 on the sibling
#: ``test_no_direct_latch_clear.py`` test: ``\b`` does not fire between ``_`` and a following
#: word character, silently missing ``self._inbox.clear_new_risk_halt(``).
_WRITE_RECEIVER = re.compile(
    r"[\w.]*\.(append|reserve|commit|send|rotate|mark_\w+|clear_new_risk_halt|enqueue\w*"
    r"|run_once|run_until_idle)\("
)


def _operator_python_files() -> list[Path]:
    return sorted(
        path
        for path in _OPERATOR_SRC_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _is_forbidden_module(module: str) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in _FORBIDDEN_IMPORT_PREFIXES
    )


# -- sanity: the package actually exists and has files to scan --------------


def test_operator_package_has_python_files_to_scan() -> None:
    files = _operator_python_files()
    assert files, f"expected .py files under {_OPERATOR_SRC_ROOT}"


# -- (a) AST import scan ------------------------------------------------------


def test_no_forbidden_write_port_imports_under_operator() -> None:
    offenders: list[str] = []
    for path in _operator_python_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden_module(alias.name):
                        offenders.append(f"{path}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if _is_forbidden_module(module):
                    offenders.append(f"{path}:{node.lineno}: from {module} import ...")
    assert not offenders, (
        "tos_runtime.operator must never import a write-capable module "
        "(plan §2 decision 8a); offenders:\n" + "\n".join(offenders)
    )


# -- (b) negative-grep over real files ----------------------------------------


def test_no_write_receiver_call_shapes_under_operator() -> None:
    offenders: list[str] = []
    for path in _operator_python_files():
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if _WRITE_RECEIVER.search(line):
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, (
        "tos_runtime.operator must hold zero write ports (plan §2 decision 8b); "
        "offending call shapes:\n" + "\n".join(offenders)
    )


# -- (c) synthetic-string self-test: prove the regex is not vacuous ----------


def test_the_receiver_shape_regex_catches_every_real_write_shape() -> None:
    should_match = (
        "self._store.append(payload)",
        "store.rotate(new_generation, key)",
        "inbox.mark_consumed(seq, evidence_seq=1, generation=1)",
        "gateway.send(attempt)",
        "log.reserve(scope)",
        "rcl_log.commit(entry)",
        "driver.run_once()",
        "driver.run_until_idle()",
        "inbox.enqueue(event)",
        "self._inbox.clear_new_risk_halt(latched_evidence_seq=1)",
    )
    should_not_match = (
        "# never call append() here",
        "def append(self, value):",
        "text about how rotate keys works, not a call",
        "def clear_new_risk_halt(self, *, latched_evidence_seq):",
    )
    for line in should_match:
        assert _WRITE_RECEIVER.search(line), f"expected the regex to match: {line!r}"
    for line in should_not_match:
        assert not _WRITE_RECEIVER.search(
            line
        ), f"expected the regex NOT to match: {line!r}"
