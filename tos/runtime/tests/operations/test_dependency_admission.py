"""Hermetic tests for :mod:`tos_runtime.operations.dependency_admission`
(Phase 5 W4 §2 decision 5 — real dependency-set / source-tree digest
observation, replacing the constant ``code_digest`` fixture the survey
named as the M6 vacuous pattern)."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest
from tos_runtime.operations.dependency_admission import (
    RuntimeArtifactObservation,
    default_package_roots,
    observe_dependency_set_digest,
    observe_runtime_artifact,
    observe_source_tree_digest,
    print_digests_text,
)


def _make_tree(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# observe_source_tree_digest — real measurement, not a constant (M2 guard)
# ---------------------------------------------------------------------------


def test_digest_changes_when_one_source_byte_changes(tmp_path: Path) -> None:
    root = tmp_path / "pkg_a"
    _make_tree(root, {"__init__.py": "x = 1\n", "sub/mod.py": "y = 2\n"})
    before = observe_source_tree_digest((root,))

    (root / "sub" / "mod.py").write_text("y = 3\n", encoding="utf-8")
    after = observe_source_tree_digest((root,))

    assert before != after


def test_digest_is_stable_for_unchanged_tree(tmp_path: Path) -> None:
    root = tmp_path / "pkg_a"
    _make_tree(root, {"__init__.py": "x = 1\n"})
    first = observe_source_tree_digest((root,))
    second = observe_source_tree_digest((root,))
    assert first == second


def test_digest_is_order_independent_of_root_tuple_order(tmp_path: Path) -> None:
    root_a = tmp_path / "pkg_a"
    root_b = tmp_path / "pkg_b"
    _make_tree(root_a, {"__init__.py": "x = 1\n"})
    _make_tree(root_b, {"__init__.py": "y = 2\n"})

    forward = observe_source_tree_digest((root_a, root_b))
    reversed_order = observe_source_tree_digest((root_b, root_a))
    assert forward == reversed_order


def test_pycache_and_non_py_files_are_excluded(tmp_path: Path) -> None:
    root = tmp_path / "pkg_a"
    _make_tree(root, {"__init__.py": "x = 1\n"})
    baseline = observe_source_tree_digest((root,))

    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "__init__.cpython-312.pyc").write_bytes(b"\x00\x01")
    (root / "README.md").write_text("not python\n", encoding="utf-8")
    after_noise = observe_source_tree_digest((root,))

    assert baseline == after_noise


def test_default_package_roots_are_the_installed_tos_and_tos_runtime_trees() -> None:
    import tos_runtime

    import tos

    roots = default_package_roots()
    assert roots == (Path(tos.__file__).parent, Path(tos_runtime.__file__).parent)


# ---------------------------------------------------------------------------
# observe_dependency_set_digest — real installed distributions, not a lock file
# ---------------------------------------------------------------------------


def test_dependency_set_digest_is_stable_across_repeated_calls() -> None:
    first = observe_dependency_set_digest()
    second = observe_dependency_set_digest()
    assert first == second


def test_dependency_set_digest_changes_when_the_observed_set_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M2 guard for the dependency coordinate: a distribution-set digest that
    never changed no matter what was installed would be exactly the vacuous
    constant this module replaces."""
    baseline = observe_dependency_set_digest()
    real_distributions = importlib.metadata.distributions

    def _with_one_extra():
        yield from real_distributions()

        class _Fake:
            metadata = {"Name": "totally-fake-test-package"}
            version = "0.0.1"

        yield _Fake()

    monkeypatch.setattr(importlib.metadata, "distributions", _with_one_extra)
    mutated = observe_dependency_set_digest()

    assert baseline != mutated


# ---------------------------------------------------------------------------
# RuntimeArtifactObservation / observe_runtime_artifact — the bundled fact
# ---------------------------------------------------------------------------


def test_observe_runtime_artifact_bundles_both_digests(tmp_path: Path) -> None:
    root = tmp_path / "pkg_a"
    _make_tree(root, {"__init__.py": "x = 1\n"})
    observation = observe_runtime_artifact((root,))
    assert isinstance(observation, RuntimeArtifactObservation)
    assert observation.source_tree_digest == observe_source_tree_digest((root,))
    assert observation.dependency_set_digest == observe_dependency_set_digest()
    assert isinstance(observation.python_version, tuple)
    assert len(observation.python_version) == 3
    assert isinstance(observation.sqlite_version, str)


def test_print_digests_text_names_both_expected_keys(tmp_path: Path) -> None:
    root = tmp_path / "pkg_a"
    _make_tree(root, {"__init__.py": "x = 1\n"})
    observation = observe_runtime_artifact((root,))
    text = print_digests_text(observation)
    assert f"expected_code_digest: {observation.source_tree_digest}" in text
    assert (
        f"expected_dependency_set_digest: {observation.dependency_set_digest}" in text
    )
