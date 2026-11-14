"""``tos_runtime.operations.dependency_admission`` — real dependency-set /"""

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

_SKIP_DIR_NAMES = frozenset({"__pycache__"})


def default_package_roots() -> tuple[Path, ...]:
    """The two installed package roots this observation covers by default:"""
    import tos
    import tos_runtime

    return (Path(tos.__file__).parent, Path(tos_runtime.__file__).parent)


def observe_source_tree_digest(package_roots: tuple[Path, ...] | None = None) -> str:
    """Sha256 every ``*.py`` file's bytes under each root (sorted relative"""
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
    """The installed distribution set plus interpreter/sqlite coordinates,"""
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
    """One honest, real measurement of this process's installed runtime"""

    source_tree_digest: str
    dependency_set_digest: str
    python_version: tuple[int, int, int]
    sqlite_version: str


def observe_runtime_artifact(
    package_roots: tuple[Path, ...] | None = None,
) -> RuntimeArtifactObservation:
    """Build one :class:`RuntimeArtifactObservation` bundling both"""
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
    """Human-readable ``print-digests`` CLI output (computation only, no"""
    lines = [
        f"expected_code_digest: {observation.source_tree_digest}",
        f"expected_dependency_set_digest: {observation.dependency_set_digest}",
        "python_version: " + ".".join(str(part) for part in observation.python_version),
        f"sqlite_version: {observation.sqlite_version}",
    ]
    return "\n".join(lines) + "\n"
