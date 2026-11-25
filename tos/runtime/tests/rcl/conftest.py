"""Shared fixtures for ``tos_runtime.rcl`` tests."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from tos.evidence import EvidenceAppendReceipt
from tos.rcl import (
    AppendReceipt,
    AppendRefusal,
    CapacityReservationTransition,
    CommandType,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import SqliteCommitLog


class FakeEvidenceAppendPort:
    """An :class:`~tos_runtime.evidence.ports.EvidenceAppendPort` test double."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, object], str, str]] = []
        self._raise_next: Exception | None = None

    def fail_next_append(self, exc: Exception) -> None:
        self._raise_next = exc

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        if self._raise_next is not None:
            pending = self._raise_next
            self._raise_next = None
            raise pending
        self.calls.append((dict(payload), kind, record_class))
        return EvidenceAppendReceipt(
            segment_id=None,
            seq=len(self.calls) - 1,
            chain_digest="fake",
            key_generation=1,
        )


class FakeMonotonicClock:
    """A settable, injectable monotonic-ns source (can be made to regress — fault ⑥)."""

    def __init__(self, start: int = 0) -> None:
        self.value = start

    def __call__(self) -> int:
        return self.value


@pytest.fixture
def evidence_port() -> FakeEvidenceAppendPort:
    return FakeEvidenceAppendPort()


@pytest.fixture
def monotonic_clock() -> FakeMonotonicClock:
    return FakeMonotonicClock(start=0)


@pytest.fixture
def identity() -> RuntimeIdentity:
    return RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-1")


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "rcl.sqlite3"


@pytest.fixture
def log(
    log_path: Path,
    evidence_port: FakeEvidenceAppendPort,
    monotonic_clock: FakeMonotonicClock,
) -> Iterator[SqliteCommitLog]:
    instance = SqliteCommitLog(
        log_path, evidence_port=evidence_port, monotonic_ns=monotonic_clock
    )
    yield instance
    instance.close()


def bind_attempt(
    log: SqliteCommitLog,
    transition: CapacityReservationTransition,
    *,
    command_id: str = "cmd-1",
    command_digest: str = "dig-1",
    expected_seq: int = -1,
) -> AppendReceipt | AppendRefusal:
    """Commit ``transition`` as this suite's standard strongly-authorized BIND_ATTEMPT."""
    return log.apply_reservation_transition(
        transition,
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id=command_id,
        command_digest=command_digest,
        expected_seq=expected_seq,
    )
