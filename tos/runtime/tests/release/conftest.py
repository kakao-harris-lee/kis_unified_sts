"""Shared fixtures for ``tos_runtime.release`` tests."""

from __future__ import annotations

import pytest
from tos.workload import RuntimeIdentity


@pytest.fixture
def identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        cell_id="test-cell",
        process_nonce="test-nonce-1",
        runtime_generation=1,
        code_digest="digest-abc",
    )
