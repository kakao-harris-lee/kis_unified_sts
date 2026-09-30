"""Shared fixtures for ``tos_runtime.release`` tests."""

from __future__ import annotations

import pytest
from tos.workload import RuntimeIdentity
from tos_runtime.operations.dependency_admission import RuntimeArtifactObservation


@pytest.fixture
def identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        cell_id="test-cell",
        process_nonce="test-nonce-1",
        runtime_generation=1,
        code_digest="digest-abc",
    )


@pytest.fixture
def observation() -> RuntimeArtifactObservation:
    """A real-shaped :class:`RuntimeArtifactObservation` whose
    ``source_tree_digest`` matches ``identity.code_digest`` above (Phase 5
    W4 — release admission now compares the OBSERVATION's digests, not
    ``identity.code_digest``, against the operator-approved expected
    values)."""
    return RuntimeArtifactObservation(
        source_tree_digest="digest-abc",
        dependency_set_digest="dep-digest-abc",
        python_version=(3, 11, 0),
        sqlite_version="3.42.0",
    )
