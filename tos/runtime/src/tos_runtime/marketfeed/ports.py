"""The tick-source contract — the surfaces every lane of the TOS 틱 원천 웨이브 builds against"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from tos.capsule import CriticalInputSnapshot
from tos.dsl import ScalarValue
from tos.engine import InstrumentKey
from tos.marketfeed import AdmittedValue, RawPayloadPreimage

__all__ = [
    "AbsentPositionContext",
    "DurableSnapshotStore",
    "MonotonicAnchoredObservation",
    "ObservationIntake",
    "PositionContextReason",
    "RawObservation",
    "TickOutcome",
    "anchor_observation",
]


@dataclass(frozen=True)
class RawObservation:
    """One raw market observation, as an upstream collector recorded it."""

    raw_event_id: str
    instrument: str
    as_of_ms: int
    fields: tuple[tuple[str, ScalarValue], ...]
    source_id: str
    received_ms: int | None = None


@dataclass(frozen=True)
class MonotonicAnchoredObservation:
    """One observation an intake has fetched but CANNOT yet stamp with a wall-clock time —"""

    instrument: str
    fields: tuple[tuple[str, ScalarValue], ...]
    source_id: str
    content_digest: str
    requested_monotonic_ms: int
    received_monotonic_ms: int


def anchor_observation(
    pending: MonotonicAnchoredObservation, *, as_of_ms: int, received_ms: int
) -> RawObservation:
    """Finalize a :class:`MonotonicAnchoredObservation` into a :class:`RawObservation`."""
    return RawObservation(
        raw_event_id=(
            f"{pending.source_id}:{pending.instrument}:{as_of_ms}:"
            f"{pending.content_digest}"
        ),
        instrument=pending.instrument,
        as_of_ms=as_of_ms,
        fields=pending.fields,
        source_id=pending.source_id,
        received_ms=received_ms,
    )


@runtime_checkable
class ObservationIntake(Protocol):
    """The injected supplier of raw observations (plan §2 decision 4)."""

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> Sequence[RawObservation | MonotonicAnchoredObservation]:
        """Return observations for ``instrument`` strictly newer than ``after_as_of_ms``."""
        ...


@runtime_checkable
class DurableSnapshotStore(Protocol):
    """The durable half of the admitted-snapshot injection port (design #38; plan §2 decision 3)."""

    def put(
        self,
        snapshot: CriticalInputSnapshot,
        preimages: Mapping[str, RawPayloadPreimage],
    ) -> None:
        """Durably record an issued snapshot and the preimages its observations address."""
        ...

    def __call__(
        self, *, snapshot_id: str | None, canonical_digest: str | None
    ) -> CriticalInputSnapshot | None:
        """Resolve a content-addressed reference to its body, or ``None``."""
        ...

    def candidates(
        self, snapshot: CriticalInputSnapshot, *, instrument_key: InstrumentKey
    ) -> Sequence[AdmittedValue]:
        """Supply the candidate value claims for one snapshot and dispatch scope."""
        ...

    def latest_as_of(self, *, instrument: str) -> int | None:
        """The newest ``as_of_ms`` this store has already issued a snapshot for, or ``None``."""
        ...


class TickOutcome(StrEnum):
    """Why one scheduler pass did or did not produce a ``DECISION_TICK`` (plan §2 decision 7)."""

    TICKED = "TICKED"
    SKIPPED_NO_OBSERVATION = "SKIPPED_NO_OBSERVATION"
    SKIPPED_NOT_NEWER = "SKIPPED_NOT_NEWER"
    SKIPPED_SESSION_CLOSED = "SKIPPED_SESSION_CLOSED"
    SKIPPED_INTERVAL = "SKIPPED_INTERVAL"
    SKIPPED_TIME_NOT_EVALUATED = "SKIPPED_TIME_NOT_EVALUATED"
    SKIPPED_TIME_UNANCHORED = "SKIPPED_TIME_UNANCHORED"
    REFUSED_POLICY = "REFUSED_POLICY"


class PositionContextReason(StrEnum):
    """Whether one bar published its ``capsule.position`` namespace — and if not, why."""

    PRESENT = "PRESENT"
    PRICE_FIELD_UNUSABLE = "PRICE_FIELD_UNUSABLE"
    STORE_READ_FAILED = "STORE_READ_FAILED"
    QUANTITY_UNSETTLED = "QUANTITY_UNSETTLED"
    BOUND_REFUSED = "BOUND_REFUSED"
    HELD_QUANTITY_UNUSABLE = "HELD_QUANTITY_UNUSABLE"
    READINGS_DISAGREE = "READINGS_DISAGREE"
    ENTRY_SEAL_NOT_SOLE = "ENTRY_SEAL_NOT_SOLE"
    ENTRY_PRICE_UNUSABLE = "ENTRY_PRICE_UNUSABLE"
    ENTRY_EVENT_MISSING = "ENTRY_EVENT_MISSING"
    PROJECTION_REFUSED = "PROJECTION_REFUSED"


@dataclass(frozen=True)
class AbsentPositionContext:
    """Why this bar carries no proven position, in place of the context (plan P4 §2 D3)."""

    reason: PositionContextReason
    bound_refusal: str | None = None
    as_of: int | None = None
