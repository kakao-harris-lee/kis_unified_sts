"""Hermetic fixtures for tos_runtime.venue tests (tmp_path only, no external"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore

from ._documents import (
    FIXTURE_OCP_POLICY_GENERATION,
    FIXTURE_OCP_POLICY_ID,
    FIXTURE_OCP_POLICY_VERSION,
    FIXTURE_POLICY_GENERATION,
    FIXTURE_POLICY_ID,
    SCHEME,
    ocp_yaml,
    venue_policy_yaml,
    write_fixture_ocp,
    write_fixture_venue_policy,
)

__all__ = [
    "FIXTURE_OCP_POLICY_GENERATION",
    "FIXTURE_OCP_POLICY_ID",
    "FIXTURE_OCP_POLICY_VERSION",
    "FIXTURE_POLICY_GENERATION",
    "FIXTURE_POLICY_ID",
    "SCHEME",
    "FixedKeyProvider",
    "evidence_store",
    "key_provider",
    "kind_count",
    "ocp_yaml",
    "venue_policy_yaml",
    "write_fixture_ocp",
    "write_fixture_venue_policy",
]


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed"""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-venue-suite")

    def generations(self) -> tuple[int, ...]:
        return (1,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-venue-suite"


@pytest.fixture
def key_provider() -> KeyProvider:
    return FixedKeyProvider()


@pytest.fixture
def evidence_store(tmp_path: Path, key_provider: KeyProvider):
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


def kind_count(evidence_store: SqliteEvidenceStore, kind: str) -> int:
    return sum(1 for entry in evidence_store.iter_entry_meta() if entry.kind == kind)
