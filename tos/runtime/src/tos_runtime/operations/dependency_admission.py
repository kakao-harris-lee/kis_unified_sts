"""``tos_runtime.operations.dependency_admission`` — real dependency-set /
source-tree digest observation (Phase 5 W4 plan §2 decision 5;
``docs/plans/2026-09-12-tos-phase5-w4-operations-plan.md``).

Replaces the constant :func:`~tos_runtime.compose._wiring._build_identity`
digest (``_SCHEME.compute_digest({"component": "tos_runtime.compose"})`` —
a literal that matches regardless of what code is actually installed, the
measured M6 vacuous pattern the survey names) with a REAL measurement of the
installed source tree, and adds a second, previously-absent measurement of
the installed dependency set. Every function here is pure observation: no
admission decision is made in this module — that stays
:func:`~tos.sci.predicates.software_deployment_ok_verdict`, called from
:mod:`tos_runtime.release.admission`.

Firewall: stdlib (``hashlib``, ``importlib.metadata``, ``pathlib``,
``sqlite3``, ``sys``, ``dataclasses``) + ``tos.canonical`` only — no
``shared.*``, no third-party deps beyond what ``tos.canonical`` already
brings in.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

__all__ = [
    "RuntimeArtifactObservation",
    "default_package_roots",
    "observe_source_tree_digest",
    "observe_dependency_set_digest",
    "observe_runtime_artifact",
    "print_digests_text",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Directory names never contributing a source-tree ``*.py`` file (compiled
#: cache only — ``*.pyc`` is already excluded structurally by the ``*.py``
#: glob, this excludes any stray ``.py`` a build tool left under the cache
#: directory).
_SKIP_DIR_NAMES = frozenset({"__pycache__"})


def default_package_roots() -> tuple[Path, ...]:
    """The two installed package roots this observation covers by default:
    the ``tos`` kernel distribution and the ``tos_runtime`` shell
    distribution (plan §2 decision 5 (a))."""
    import tos
    import tos_runtime

    return (Path(tos.__file__).parent, Path(tos_runtime.__file__).parent)


def observe_source_tree_digest(package_roots: tuple[Path, ...] | None = None) -> str:
    """Sha256 every ``*.py`` file's bytes under each root (sorted relative
    paths, ``__pycache__``/``*.pyc`` excluded), then fold the sorted
    ``(root label, relative path, file digest)`` triples through the SAME
    canonical digest scheme ``compose/_wiring.py`` uses for
    ``RuntimeIdentity.code_digest`` — a REAL measurement of the installed
    source tree (plan §2 decision 5 (a)).

    Args:
        package_roots: Installed package directories to walk; defaults to
            :func:`default_package_roots`. Each root is labeled by its own
            directory name (``root.name``), not by its position in the
            tuple, so the result does not depend on the order
            ``package_roots`` is supplied in.

    Returns:
        A hex digest over the sorted ``(root label, relative path,
        sha256(file bytes))`` triples.
    """
    roots = package_roots if package_roots is not None else default_package_roots()
    entries: list[tuple[str, str, str]] = []
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if any(part in _SKIP_DIR_NAMES for part in path.parts):
                continue
            relative = path.relative_to(root).as_posix()
            file_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append((root.name, relative, file_digest))
    entries.sort()
    return _SCHEME.compute_digest({"files": [list(entry) for entry in entries]})


def observe_dependency_set_digest() -> str:
    """The installed distribution set plus interpreter/sqlite coordinates,
    folded through the shared canonical scheme (plan §2 decision 5 (b)).

    Uses ``importlib.metadata.distributions()`` — the installed TRUTH, not
    ``tos/uv.lock`` (an operator's stated INTENT, not a measurement of what
    is actually on disk; plan §3 "기각 대안" rejects lock-parsing as the
    expected-value source).

    Returns:
        A hex digest over the sorted unique ``(name, version)`` pairs plus
        ``python_version``/``sqlite_version``.
    """
    names_and_versions: set[tuple[str, str]] = set()
    for distribution in importlib.metadata.distributions():
        try:
            name = distribution.metadata["Name"]
        except KeyError:
            name = None
        version = distribution.version
        if name is None or version is None:
            continue
        names_and_versions.add((name, version))
    covered = {
        "distributions": [list(pair) for pair in sorted(names_and_versions)],
        "python_version": list(sys.version_info[:3]),
        "sqlite_version": sqlite3.sqlite_version,
    }
    return _SCHEME.compute_digest(covered)


@dataclass(frozen=True)
class RuntimeArtifactObservation:
    """One honest, real measurement of this process's installed runtime
    artifact set (plan §2 decision 5) — what
    :mod:`tos_runtime.release.admission` compares against the operator-
    approved expected digests. STAGE A (:mod:`tos_runtime.compose._wiring`)
    computes this ONCE and STAGE B reuses it — no double filesystem walk /
    no double ``distributions()`` enumeration (plan §2 decision 5 (e))."""

    source_tree_digest: str
    dependency_set_digest: str
    python_version: tuple[int, int, int]
    sqlite_version: str


def observe_runtime_artifact(
    package_roots: tuple[Path, ...] | None = None,
) -> RuntimeArtifactObservation:
    """Build one :class:`RuntimeArtifactObservation` bundling both
    measurements (used by the ``print-digests`` CLI and the test conftests —
    :mod:`tos_runtime.compose._wiring` computes the two measurements
    separately at their own single call sites instead, so this bundler
    itself is never on the compose boot path).

    Args:
        package_roots: Forwarded to :func:`observe_source_tree_digest`;
            defaults to :func:`default_package_roots`.
    """
    return RuntimeArtifactObservation(
        source_tree_digest=observe_source_tree_digest(package_roots),
        dependency_set_digest=observe_dependency_set_digest(),
        python_version=(
            sys.version_info[0],
            sys.version_info[1],
            sys.version_info[2],
        ),
        sqlite_version=sqlite3.sqlite_version,
    )


def print_digests_text(observation: RuntimeArtifactObservation) -> str:
    """Human-readable ``print-digests`` CLI output (computation only, no
    writes) — the operator copies these two values into ``release.yaml``'s
    ``expected_code_digest``/``expected_dependency_set_digest`` (plan §2
    decision 5 (g); §6 operator confirmation 1)."""
    lines = [
        f"expected_code_digest: {observation.source_tree_digest}",
        f"expected_dependency_set_digest: {observation.dependency_set_digest}",
        "python_version: " + ".".join(str(part) for part in observation.python_version),
        f"sqlite_version: {observation.sqlite_version}",
    ]
    return "\n".join(lines) + "\n"
