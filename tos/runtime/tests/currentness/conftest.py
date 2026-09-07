"""Shared fixtures for ``tos_runtime.currentness`` tests.

Uses a real :class:`~tos_runtime.rcl.SqliteCommitLog` under ``tmp_path``
(hermetic — a sqlite file under the test's own ``tmp_path`` is explicitly
allowed by D1.4) and simple test doubles for evidence/time/injected readers,
per the task brief's TDD instruction.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.cur import MANDATED_DIMENSION_FLOOR, CurrentnessPolicy, DimensionKey
from tos.evidence import EvidenceAppendReceipt
from tos.time import (
    EvaluatedMonotonicAnchor,
    HealthState,
    TimeContinuityIdentity,
    TimeHealthSnapshot,
)
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.log import SqliteCommitLog

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


class FakeEvidenceAppendPort:
    """An ``EvidenceAppendPort`` test double (mirrors ``tos_runtime.rcl``'s
    own test double — see that package's ``tests/rcl/conftest.py``)."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, object], str, str]] = []

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        self.calls.append((dict(payload), kind, record_class))
        return EvidenceAppendReceipt(
            segment_id=None,
            seq=len(self.calls) - 1,
            chain_digest="fake",
            key_generation=1,
        )


class FakeMonotonicClock:
    """A settable, injectable monotonic-ns source."""

    def __init__(self, start: int = 0) -> None:
        self.value = start

    def __call__(self) -> int:
        return self.value


class FakeTimeService:
    """A ``TrustworthyTimeService``-shaped double: returns a fixed, injected
    :class:`~tos.time.TimeHealthSnapshot` (or raises
    ``TimeServiceNotStarted``-compatible ``RuntimeError`` when none is set) —
    the real FSM is lane K's own test scope, not this lane's."""

    def __init__(self, snapshot: TimeHealthSnapshot | None = None) -> None:
        self._snapshot = snapshot

    def set_snapshot(self, snapshot: TimeHealthSnapshot | None) -> None:
        self._snapshot = snapshot

    def current_snapshot(self) -> TimeHealthSnapshot:
        if self._snapshot is None:
            from tos_runtime.time.service import TimeServiceNotStarted

            raise TimeServiceNotStarted("no snapshot set on FakeTimeService")
        return self._snapshot


def clean_snapshot(
    *, health_state: HealthState = HealthState.TRUSTED, generation: int = 1
) -> TimeHealthSnapshot:
    """A digest-verified, minimally-complete :class:`TimeHealthSnapshot`."""
    anchor = TimeContinuityIdentity(
        host_or_runtime_id="cell-1",
        boot_id="boot-1",
        process_id="proc-1",
        monotonic_anchor_id="mono-1",
        monotonic_anchor_value=1000,
        tts_generation=generation,
    )
    issued = TimeHealthSnapshot.issue(
        scheme=_SCHEME,
        snapshot_id=f"ths-test-{generation}",
        generation=generation,
        health_state=health_state,
        time_continuity_identity=anchor,
        evaluated_monotonic_anchor=EvaluatedMonotonicAnchor(
            monotonic_anchor_id="mono-1", monotonic_anchor_value=1000
        ),
        issuer_continuity_id="mono-1",
        issue_monotonic_value=1000,
        tz_db_version="v1",
        trading_calendar_version="v1",
        verification_profile_version="v1",
        safety_profile_version="v1",
    )
    assert isinstance(issued, TimeHealthSnapshot)
    return issued


@pytest.fixture
def evidence_port() -> FakeEvidenceAppendPort:
    return FakeEvidenceAppendPort()


@pytest.fixture
def identity() -> RuntimeIdentity:
    return RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-1")


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "rcl.sqlite3"


@pytest.fixture
def log(log_path: Path, evidence_port: FakeEvidenceAppendPort) -> SqliteCommitLog:
    instance = SqliteCommitLog(log_path, evidence_port=evidence_port)
    yield instance
    instance.close()


@pytest.fixture
def writer_epoch(log: SqliteCommitLog, identity: RuntimeIdentity) -> int:
    return log.acquire_epoch(identity)


@pytest.fixture
def trusted_time_service() -> FakeTimeService:
    return FakeTimeService(snapshot=clean_snapshot())


@pytest.fixture
def not_started_time_service() -> FakeTimeService:
    return FakeTimeService(snapshot=None)


@pytest.fixture
def complete_policy() -> CurrentnessPolicy:
    """A policy whose required floor is exactly what this lane can supply —
    genuinely achievable completeness for the narrow "everything this lane
    owns is present" test, distinct from the realistic full-floor policy
    below."""
    issued = CurrentnessPolicy.issue(
        scheme=_SCHEME,
        policy_id="pol-currentness-test",
        policy_generation=1,
        required_dimensions=frozenset(
            {DimensionKey.COMMIT_LOG, DimensionKey.TRUSTWORTHY_TIME}
        ),
    )
    assert isinstance(issued, CurrentnessPolicy)
    return issued


@pytest.fixture
def full_floor_policy() -> CurrentnessPolicy:
    """A policy declaring the real §9 mandated floor — legitimately
    unachievable by this lane alone (most dimensions are owned by lanes not
    wired here), demonstrating the honest "L1 substrate only" posture."""
    issued = CurrentnessPolicy.issue(
        scheme=_SCHEME,
        policy_id="pol-full-floor-test",
        policy_generation=1,
        required_dimensions=MANDATED_DIMENSION_FLOOR,
    )
    assert isinstance(issued, CurrentnessPolicy)
    return issued
