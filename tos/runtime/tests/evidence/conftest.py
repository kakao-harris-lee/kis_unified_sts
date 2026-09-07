"""Shared fixtures for ``tos_runtime.evidence`` tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed bytes."""

    def __init__(
        self, key_generation: int = 1, key: bytes = b"test-fixed-key-bytes"
    ) -> None:
        self._key_generation = key_generation
        self._key = key

    def current(self) -> tuple[int, bytes]:
        return (self._key_generation, self._key)


class FakeMonotonicClock:
    """A settable, injectable monotonic-ns source — deterministic age arithmetic in tests."""

    def __init__(self, start: int = 0) -> None:
        self.value = start

    def __call__(self) -> int:
        return self.value


@pytest.fixture
def key_provider() -> KeyProvider:
    return FixedKeyProvider()


@pytest.fixture
def monotonic_clock() -> FakeMonotonicClock:
    return FakeMonotonicClock(start=0)


@pytest.fixture
def store(
    tmp_path: Path, key_provider: KeyProvider, monotonic_clock: FakeMonotonicClock
) -> SqliteEvidenceStore:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3",
        key_provider=key_provider,
        monotonic_ns=monotonic_clock,
    )
    yield instance
    instance.close()
