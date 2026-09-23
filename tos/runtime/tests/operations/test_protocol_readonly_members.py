"""Pin tests for the runtime read-only-member Protocol sweep
(docs/plans/2026-09-23-tos-protocol-readonly-members-sweep-plan.md §2/§3).

Five runtime Protocols had a plain (settable) attribute member that a frozen
implementation (dataclass ``frozen=True`` / pydantic frozen model) cannot satisfy —
the same structural break the plan's §1 measurement found already latent in
:class:`~tos_runtime.operations.backup_set._RecoveryVerdictLike` /
:class:`~tos_runtime.operations.backup_set._ComposedForDrill` against the real
(frozen) :class:`~tos_runtime.recovery.barrier.RecoveryVerdict`. §2 converts every
such member to a read-only ``@property``; this file pins that conversion two ways
(plan §3 — one alone is not enough):

(i) **mypy conformance functions** — module-level, fully annotated, never called.
Each real implementer and a purpose-built frozen ``@dataclass(frozen=True)`` double
must both be assignable to the Protocol. These are checked only by the test-tree
mypy step (``mypy tos/runtime/tests --disable-error-code=no-untyped-def``); reverting
any member to a plain attribute makes the *frozen* double's function fail
(``expected settable variable, got read-only attribute`` in reverse — a mutable real
implementer still satisfies a plain attribute, so ``_real_*`` alone would not catch
the regression for the members that currently HAVE a mutable real implementer).

(ii) **runtime data-descriptor check** — reverting a member to a plain annotation-only
attribute leaves nothing on the class itself (only ``__annotations__``), so
``inspect.getattr_static`` raises ``AttributeError`` instead of returning a property
object. This is the branch that would catch a regression even with test-tree mypy
disabled locally.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass

import pytest
from tos.are import AggregateRiskDecision
from tos.egressgw import CandidateConstruction, OrderConstructionStage
from tos.sbr.vocabulary import ReadinessVerdict
from tos_runtime.compose._dimension_readers import _AggregateRiskDecisionReader
from tos_runtime.compose._dimension_readers import (
    _ConstructionStageReader as _ConstructionStageReaderDR,
)
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.compose._venue_wiring import (
    _ConstructionStageReader as _ConstructionStageReaderVW,
)
from tos_runtime.compose.context import RecordingAggregateRiskService
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.operations.backup_set import _ComposedForDrill, _RecoveryVerdictLike
from tos_runtime.recovery.barrier import RecoveryVerdict

# ===========================================================================
# (i) mypy conformance functions — real implementers
# ===========================================================================


def _real_aggregate_risk(
    x: RecordingAggregateRiskService,
) -> _AggregateRiskDecisionReader:
    return x


def _real_construction_dr(x: OrderConstructionStage) -> _ConstructionStageReaderDR:
    return x


def _real_construction_vw(x: OrderConstructionStage) -> _ConstructionStageReaderVW:
    return x


def _real_recovery_verdict(x: RecoveryVerdict) -> _RecoveryVerdictLike:
    return x


def _real_composed_for_drill(x: ComposedRuntime) -> _ComposedForDrill:
    return x


# ===========================================================================
# (i) mypy conformance functions — frozen doubles
# ===========================================================================


@dataclass(frozen=True)
class _FrozenAggregateRiskDecisionReader:
    """A frozen double for :class:`_AggregateRiskDecisionReader` — the real
    :class:`RecordingAggregateRiskService` is mutable, so only this double would have
    caught a regression to a plain attribute for this member."""

    last_decision: AggregateRiskDecision | None


def _frozen_aggregate_risk(
    x: _FrozenAggregateRiskDecisionReader,
) -> _AggregateRiskDecisionReader:
    return x


@dataclass(frozen=True)
class _FrozenConstructionStageReader:
    """A frozen double satisfying both ``_ConstructionStageReader`` definitions
    (``_dimension_readers`` and ``_venue_wiring``) — same real attribute, same shape,
    per the plan's own note that they mirror each other."""

    construction: CandidateConstruction | None


def _frozen_construction_dr(
    x: _FrozenConstructionStageReader,
) -> _ConstructionStageReaderDR:
    return x


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


def _frozen_composed_for_drill(x: _FrozenComposedForDrill) -> _ComposedForDrill:
    return x


# ===========================================================================
# (ii) runtime data-descriptor check
# ===========================================================================

#: The plan §1 inventory of runtime Protocol / member pairs converted to read-only
#: properties (5 Protocols, 8 members — the kernel's 2 Protocols / 2 members are
#: pinned separately in ``tos/tests/canonical/test_protocol_readonly_members.py``,
#: which must not import ``tos_runtime``, per the firewall).
_PROPERTY_MEMBERS = (
    (_AggregateRiskDecisionReader, "last_decision"),
    (_ConstructionStageReaderDR, "construction"),
    (_ConstructionStageReaderVW, "construction"),
    (_RecoveryVerdictLike, "readiness_verdict"),
    (_ComposedForDrill, "evidence_store"),
    (_ComposedForDrill, "inbox"),
    (_ComposedForDrill, "emergency_log"),
    (_ComposedForDrill, "recovery"),
)


@pytest.mark.parametrize("protocol, member", _PROPERTY_MEMBERS)
def test_member_is_read_only_property(protocol: type, member: str) -> None:
    """Reverting ``member`` back to a plain ``name: T`` annotation leaves no
    class-level descriptor at all (only ``__annotations__``), so
    ``inspect.getattr_static`` raises ``AttributeError`` instead of returning a
    ``property`` — this assertion goes RED either way a plain attribute regresses."""
    assert inspect.isdatadescriptor(inspect.getattr_static(protocol, member))
