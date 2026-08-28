"""Consistency Cut element schema (design §2.5).

Models ``CRITICAL-INPUT-SNAPSHOT-template.yaml:consistency_cut`` (lines 20-26)
1:1 — **no new stored field is added** (design §2.5/§2.6 byte-alignment).

The design §2.5 gate "individually fresh != valid snapshot" is realized as the
**derived, non-stored predicate** ``cut_compatible`` in
:mod:`tos.capsule.predicates` (m3): it is computed from
``source_continuity_vector`` / ``source_revision_vector`` / field evaluations and
is therefore *not* part of the snapshot canonical bytes (design §2.5).

Pure module: ``pydantic`` + stdlib only.
"""

from __future__ import annotations

from tos.capsule._base import FrozenModel
from tos.capsule.field_state import FieldState


class SourceContinuityVectorEntry(FrozenModel):
    """Per-source continuity coordinate in the cut (design §2.5).

    ``continuity_gap`` records an unestablished/broken continuity for the source;
    a set gap makes the cut incompatible (design §2.5, §5.3).
    """

    source_continuity_id: str | None = None
    native_sequence: int | None = None
    continuity_gap: bool = False


class SourceRevisionVectorEntry(FrozenModel):
    """Per-source revision coordinate in the cut (design §2.5)."""

    source_continuity_id: str | None = None
    native_revision: int | None = None


class ConsistencyCut(FrozenModel):
    """A cut across sources at which fields were read together (design §2.5).

    ``atomicity_proven`` defaults ``False`` (template line 25): equality between
    reads or absence from one query is not a completeness proof (ADR §11 line
    309). ``uncertainty`` defaults ``UNKNOWN`` (template line 26). Both feed the
    derived ``cut_compatible`` predicate.
    """

    cut_id: str | None = None
    source_continuity_vector: tuple[SourceContinuityVectorEntry, ...] = ()
    source_revision_vector: tuple[SourceRevisionVectorEntry, ...] = ()
    receipt_interval: str | None = None
    atomicity_proven: bool = False
    uncertainty: FieldState = FieldState.UNKNOWN
