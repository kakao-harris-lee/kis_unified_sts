"""The durable stores every post-trade test opens together, declared once."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog

from ..engine.conftest import FakeMonotonicSource, FixedKeyProvider

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
MONOTONIC_BASE_MS = 1_700_000_000_000


@pytest.fixture
def evidence_store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    yield instance
    instance.close()


@pytest.fixture
def inbox(tmp_path: Path) -> Iterator[SqliteEventInbox]:
    instance = SqliteEventInbox(tmp_path / "inbox.sqlite3", scheme=_SCHEME)
    yield instance
    instance.close()


@pytest.fixture
def rcl_log(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> Iterator[SqliteCommitLog]:
    instance = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)
    yield instance
    instance.close()


@pytest.fixture
def monotonic_source() -> FakeMonotonicSource:
    return FakeMonotonicSource(start=MONOTONIC_BASE_MS)


@dataclass(frozen=True)
class Rig:
    """The four stores above bound together, so one parameter carries them all."""

    rcl_log: SqliteCommitLog
    evidence_store: SqliteEvidenceStore
    inbox: SqliteEventInbox
    monotonic_source: FakeMonotonicSource


@pytest.fixture
def rig(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> Rig:
    return Rig(rcl_log, evidence_store, inbox, monotonic_source)
