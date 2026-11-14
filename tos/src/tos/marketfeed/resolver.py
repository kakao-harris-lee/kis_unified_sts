"""The concrete ``DecisionContextResolver`` — the adapter layer (design #32 §3.3/§3.4)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tos.capsule import CriticalInputSnapshot, DecisionContextCapsule
from tos.engine import DecisionTickPayload, InstrumentKey, TimeAdmissionInputs
from tos.marketfeed._base import CanonicalizationScheme
from tos.marketfeed.records import AdmittedValue, ValueResolution
from tos.marketfeed.value import publish_context_value_view
from tos.marketfeed.vocabulary import ADMITTING_DISPOSITIONS

__all__ = [
    "MarketFeedContextResolver",
    "ResolvedTick",
    "SnapshotStore",
    "TimeCoordinateProjection",
    "ValueCandidateSource",
]


@runtime_checkable
class SnapshotStore(Protocol):
    """The injected content-addressed snapshot lookup (design #32 §3.3 step 1, 미결-4)."""

    def __call__(
        self, *, snapshot_id: str | None, canonical_digest: str | None
    ) -> CriticalInputSnapshot | None:
        """Resolve a content-addressed snapshot reference to its body, or ``None``."""
        ...


@runtime_checkable
class ValueCandidateSource(Protocol):
    """The injected supplier of candidate values for one snapshot (design #32 §3.3 step 3)."""

    def __call__(
        self, snapshot: CriticalInputSnapshot, *, instrument_key: InstrumentKey
    ) -> Sequence[AdmittedValue]:
        """Supply the candidate values for one snapshot and dispatch scope."""
        ...


@runtime_checkable
class TimeCoordinateProjection(Protocol):
    """The injected as-of → time-coordinate projection (design #32 §3.3 step 4)."""

    def __call__(self, *, as_of: int | None) -> TimeAdmissionInputs:
        """Project the value surface's as-of anchor onto the engine's injected time inputs."""
        ...


@dataclass(frozen=True)
class ResolvedTick:
    """One resolution: the engine payload plus the value-surface report (design #32 §6)."""

    payload: DecisionTickPayload
    resolution: ValueResolution

    @property
    def value_surface_published(self) -> bool:
        """Whether a value view was published at all (an explicit-empty view counts as published)."""
        return self.resolution.disposition in ADMITTING_DISPOSITIONS


class MarketFeedContextResolver:
    """The D-E2 :class:`~tos.engine.DecisionContextResolver` (design #32 §3.3)."""

    authority_label = "NON_AUTHORITATIVE_PROVISIONAL"

    def __init__(
        self,
        *,
        snapshot_store: SnapshotStore,
        candidate_source: ValueCandidateSource,
        scheme: CanonicalizationScheme,
        time_projection: TimeCoordinateProjection | None = None,
    ) -> None:
        """Wire the resolver."""
        self._snapshot_store = snapshot_store
        self._candidate_source = candidate_source
        self._scheme = scheme
        self._time_projection = time_projection

    def resolve(
        self, capsule: DecisionContextCapsule, *, instrument_key: InstrumentKey
    ) -> ResolvedTick:
        """Resolve one Decision Context into a payload **and** its value-surface report."""
        ref = capsule.critical_input_snapshot
        snapshot = self._snapshot_store(
            snapshot_id=ref.snapshot_id, canonical_digest=ref.canonical_digest
        )
        candidates: Sequence[AdmittedValue] = (
            ()
            if snapshot is None
            else self._candidate_source(snapshot, instrument_key=instrument_key)
        )
        resolution = publish_context_value_view(
            capsule=capsule,
            snapshot=snapshot,
            candidates=candidates,
            scheme=self._scheme,
        )
        view = resolution.view
        as_of = max((value.as_of for value in resolution.values), default=None)
        time_inputs = (
            TimeAdmissionInputs()
            if self._time_projection is None
            else self._time_projection(as_of=as_of)
        )
        payload = DecisionTickPayload(
            instrument_key=instrument_key,
            capsule=capsule,
            time=time_inputs,
            value_view=view,
        )
        return ResolvedTick(payload=payload, resolution=resolution)

    def __call__(
        self, capsule: DecisionContextCapsule, *, instrument_key: InstrumentKey
    ) -> DecisionTickPayload:
        """Resolve one Decision Context into a tick payload (the engine's slot signature)."""
        return self.resolve(capsule, instrument_key=instrument_key).payload
