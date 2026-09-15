"""Shared fixtures for ``tos_runtime.engine`` tests (TOS Phase 3 Wave 1 Lane A-R).

Hermetic: every sqlite file lives under ``tmp_path`` (D1.4, ``tos/runtime/tests/conftest.py``'s
autouse guards enforce this); no network, no ambient env.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed bytes."""

    def __init__(
        self, key_generation: int = 1, key: bytes = b"engine-test-fixed-key"
    ) -> None:
        self._key_generation = key_generation
        self._key = key

    def current(self) -> tuple[int, bytes]:
        return (self._key_generation, self._key)

    def generations(self) -> tuple[int, ...]:
        return (self._key_generation,)


class FakeMonotonicSource:
    """A settable, injectable monotonic-ms source (:class:`~tos_runtime.time.sources.MonotonicSource`)."""

    def __init__(self, start: int = 0) -> None:
        self.value = start

    def now_ms(self) -> int:
        return self.value

    def advance(self, delta_ms: int) -> None:
        self.value += delta_ms


@pytest.fixture
def key_provider() -> KeyProvider:
    return FixedKeyProvider()


@pytest.fixture
def evidence_store(tmp_path: Path, key_provider: KeyProvider) -> SqliteEvidenceStore:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


@pytest.fixture
def emergency_log(tmp_path: Path) -> EmergencyAppendLog:
    return EmergencyAppendLog(tmp_path / "emergency.jsonl")


@pytest.fixture
def inbox(tmp_path: Path) -> SqliteEventInbox:
    instance = SqliteEventInbox(tmp_path / "inbox.sqlite3", scheme=SCHEME)
    yield instance
    instance.close()


@pytest.fixture
def monotonic_source() -> FakeMonotonicSource:
    return FakeMonotonicSource()
