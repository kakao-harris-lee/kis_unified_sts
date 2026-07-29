"""The concrete ``DecisionContextResolver`` — the adapter layer (design #32 §3.3/§3.4).

This is the **only** module in ``tos.marketfeed`` with a ``tos.engine`` edge, and the split is
load-bearing: :mod:`tos.marketfeed.value` stays engine-free so its closure is a pure-kernel closure
(design #32 §3.4), while everything that must speak the engine's payload vocabulary lives here.

The direction of every edge is *into* the engine, never out of it. ``tos.marketfeed`` imports
``tos.engine`` and ``tos.dsl``; neither imports ``tos.marketfeed``. So the committed engine
import-closure allowlist (fourteen packages,
``tos/tests/engine/test_engine_import_closure.py:59-76``) is untouched, and
``engine -> marketfeed -> engine`` has no first edge to start from (design #32 §3.4/§15.2 ③).

:class:`MarketFeedContextResolver` fills the D-E1 slot declared at ``tos.engine.core`` lines 86-105.
What it does is resolve, verify, and refuse — it **invents nothing**:

* the snapshot body comes from an **injected** store (D-E3 supplies history, D-E4 supplies the live
  publication path; the resolver cannot tell them apart, which is the parity claim);
* the candidate values come from an **injected** source — the resolver opens no feed;
* the time coordinates come from an **injected** projection; absent one, the payload carries the
  engine's all-``None`` :class:`~tos.engine.TimeAdmissionInputs`, which denies admission
  (``pipeline.time_admits``). Absence is restrictive, never permissive.

⚠ **Honest limits.** A refused binding yields ``value_view=None``, so every value operand resolves
to ``UNKNOWN`` and the decision narrows — the resolver never falls back to a "last known good" view
(ADR-002-018 §14:367). And the value ⟺ digest verification happens at publication, not again at
environment-injection time (design #32 §2.3 trust seam).

⚠ **Provisional; closes no EV** (design #32 §1.1).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only. No clock, no RNG, no network.
"""

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
    """The injected content-addressed snapshot lookup (design #32 §3.3 step 1, 미결-4).

    ``tos.capsule``'s ``SnapshotRef`` carries an id and a digest and nothing else
    (``capsule.py:41-50``), so the snapshot *body* — the observations, field evaluations, and
    lineage a value is read from — has to come from outside the Capsule. This is that seam.

    Returning ``None`` is a first-class answer ("this store has no such snapshot") and is handled
    fail-closed; a store must never substitute a different snapshot for a missing one.
    """

    def __call__(
        self, *, snapshot_id: str | None, canonical_digest: str | None
    ) -> CriticalInputSnapshot | None:
        """Resolve a content-addressed snapshot reference to its body, or ``None``."""
        ...


@runtime_checkable
class ValueCandidateSource(Protocol):
    """The injected supplier of candidate values for one snapshot (design #32 §3.3 step 3).

    Candidates are *claims* — "the value under this key in the payload behind this observation" —
    which the publication gate then verifies against the snapshot. The source therefore cannot
    admit anything by supplying it; the most a dishonest source achieves is a rejection record.
    """

    def __call__(
        self, snapshot: CriticalInputSnapshot, *, instrument_key: InstrumentKey
    ) -> Sequence[AdmittedValue]:
        """Supply the candidate values for one snapshot and dispatch scope."""
        ...


@runtime_checkable
class TimeCoordinateProjection(Protocol):
    """The injected as-of → time-coordinate projection (design #32 §3.3 step 4).

    The engine never reads a clock and neither does this package: a "now" reading, if the deployment
    has one, rides in through this projection. ``as_of`` is the newest admitted value's as-of, or
    ``None`` when no value was published.
    """

    def __call__(self, *, as_of: int | None) -> TimeAdmissionInputs:
        """Project the value surface's as-of anchor onto the engine's injected time inputs."""
        ...


@dataclass(frozen=True)
class ResolvedTick:
    """One resolution: the engine payload plus the value-surface report (design #32 §6).

    The engine Protocol returns only a :class:`~tos.engine.DecisionTickPayload`, which cannot say
    *why* a value surface is absent. This carries both, so an explicit-empty view and a refused
    binding stay distinguishable to a caller that wants to record the difference — the ∅ 양방향
    discipline surviving the narrowing to the engine's slot.
    """

    payload: DecisionTickPayload
    resolution: ValueResolution

    @property
    def value_surface_published(self) -> bool:
        """Whether a value view was published at all (an explicit-empty view counts as published)."""
        return self.resolution.disposition in ADMITTING_DISPOSITIONS


class MarketFeedContextResolver:
    """The D-E2 :class:`~tos.engine.DecisionContextResolver` (design #32 §3.3).

    ``(capsule, *, instrument_key) -> DecisionTickPayload``, exactly the shipped slot signature
    (``core.py:101-105``). Every collaborator is injected, so the resolver is a pure function of its
    injected surfaces and its arguments — no ambient source, no clock, no feed.
    """

    #: The label every provisional artifact in this slice carries (design #31 §4.4 mirror).
    authority_label = "NON_AUTHORITATIVE_PROVISIONAL"

    def __init__(
        self,
        *,
        snapshot_store: SnapshotStore,
        candidate_source: ValueCandidateSource,
        scheme: CanonicalizationScheme,
        time_projection: TimeCoordinateProjection | None = None,
    ) -> None:
        """Wire the resolver.

        Args:
            snapshot_store: The injected snapshot-body lookup.
            candidate_source: The injected candidate-value supplier.
            scheme: The injected canonicalization scheme used for the value ⟺ digest check and the
                view digest.
            time_projection: The injected as-of → time-coordinate projection. ``None`` leaves the
                payload's time coordinates at the engine's all-``None`` default, which **denies**
                admission — absence is restrictive.
        """
        self._snapshot_store = snapshot_store
        self._candidate_source = candidate_source
        self._scheme = scheme
        self._time_projection = time_projection

    def resolve(
        self, capsule: DecisionContextCapsule, *, instrument_key: InstrumentKey
    ) -> ResolvedTick:
        """Resolve one Decision Context into a payload **and** its value-surface report.

        Args:
            capsule: The Decision Context Capsule for this tick.
            instrument_key: The dispatch scope.

        Returns:
            The :class:`ResolvedTick`.
        """
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
        """Resolve one Decision Context into a tick payload (the engine's slot signature).

        Args:
            capsule: The Decision Context Capsule for this tick.
            instrument_key: The dispatch scope.

        Returns:
            The :class:`~tos.engine.DecisionTickPayload`. ``reference`` is left at its engine
            default: the causal-ordering coordinate is stamped by whichever event source yields the
            event (design #33 §3.4), and claiming it here would be an invention.
        """
        return self.resolve(capsule, instrument_key=instrument_key).payload
