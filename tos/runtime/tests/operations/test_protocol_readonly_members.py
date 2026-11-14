"""Pin tests for the runtime read-only-member Protocol sweep"""

from __future__ import annotations

import inspect
from dataclasses import dataclass

import pytest
from tos.egressgw import CandidateConstruction, OrderConstructionStage
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.compose._venue_wiring import (
    _ConstructionStageReader as _ConstructionStageReaderVW,
)
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.operations.backup_set import _ComposedForDrill, _RecoveryVerdictLike
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.recovery.barrier import RecoveryVerdict
from tos_runtime.recovery.readiness import ReadinessVerdict


def _real_construction_vw(x: OrderConstructionStage) -> _ConstructionStageReaderVW:
    return x


def _real_recovery_verdict(x: RecoveryVerdict) -> _RecoveryVerdictLike:
    return x


def _real_composed_for_drill(x: ComposedRuntime) -> _ComposedForDrill:
    return x


@dataclass(frozen=True)
class _FrozenConstructionStageReader:
    """A frozen double satisfying ``_venue_wiring._ConstructionStageReader``."""

    construction: CandidateConstruction | None


def _frozen_construction_vw(
    x: _FrozenConstructionStageReader,
) -> _ConstructionStageReaderVW:
    return x


@dataclass(frozen=True)
class _FrozenRecoveryVerdictLike:
    readiness_verdict: ReadinessVerdict


def _frozen_recovery_verdict(x: _FrozenRecoveryVerdictLike) -> _RecoveryVerdictLike:
    return x


@dataclass(frozen=True)
class _FrozenComposedForDrill:
    evidence_store: SqliteEvidenceStore
    inbox: SqliteEventInbox
    emergency_log: EmergencyAppendLog
    recovery: _RecoveryVerdictLike | None
    rcl_log: SqliteCommitLog


def _frozen_composed_for_drill(x: _FrozenComposedForDrill) -> _ComposedForDrill:
    return x


_PROPERTY_MEMBERS = (
    (_ConstructionStageReaderVW, "construction"),
    (_RecoveryVerdictLike, "readiness_verdict"),
    (_ComposedForDrill, "evidence_store"),
    (_ComposedForDrill, "inbox"),
    (_ComposedForDrill, "emergency_log"),
    (_ComposedForDrill, "recovery"),
)


@pytest.mark.parametrize("protocol, member", _PROPERTY_MEMBERS)
def test_member_is_read_only_property(protocol: type, member: str) -> None:
    """Reverting ``member`` back to a plain ``name: T`` annotation leaves no"""
    assert inspect.isdatadescriptor(inspect.getattr_static(protocol, member))
