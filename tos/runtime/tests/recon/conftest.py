"""Shared fixtures for ``tos_runtime.recon`` tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.recon import FreshnessMarker
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed bytes."""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes")


@pytest.fixture
def key_provider() -> KeyProvider:
    return FixedKeyProvider()


@pytest.fixture
def store(tmp_path: Path, key_provider: KeyProvider) -> SqliteEvidenceStore:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


@pytest.fixture
def fresh_marker() -> FreshnessMarker:
    """A genuinely fresh, time-confident marker (both generations concrete and equal)."""
    return FreshnessMarker(
        fresh_within_horizon=True,
        time_confidence_held=True,
        time_generation=1,
        anchored_generation=1,
    )
