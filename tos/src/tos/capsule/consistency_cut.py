"""Consistency Cut element schema (design §2.5)."""

from __future__ import annotations

from tos.capsule._base import FrozenModel
from tos.capsule.field_state import FieldState


class SourceContinuityVectorEntry(FrozenModel):
    """Per-source continuity coordinate in the cut (design §2.5)."""

    source_continuity_id: str | None = None
    native_sequence: int | None = None
    continuity_gap: bool = False


class SourceRevisionVectorEntry(FrozenModel):
    """Per-source revision coordinate in the cut (design §2.5)."""

    source_continuity_id: str | None = None
    native_revision: int | None = None


class ConsistencyCut(FrozenModel):
    """A cut across sources at which fields were read together (design §2.5)."""

    cut_id: str | None = None
    source_continuity_vector: tuple[SourceContinuityVectorEntry, ...] = ()
    source_revision_vector: tuple[SourceRevisionVectorEntry, ...] = ()
    receipt_interval: str | None = None
    atomicity_proven: bool = False
    uncertainty: FieldState = FieldState.UNKNOWN
