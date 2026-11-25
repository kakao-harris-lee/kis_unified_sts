"""Provisional evidence sink (design #31 §5.1 / §12-5) + the replay-result adapter."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tos.engine.records import EngineEvidenceRecord
from tos.evidence import (
    EV_L1_PROVISIONAL_CHAIN_VERSION,
    ReplayResultState,
    compute_replay_result,
)

__all__ = [
    "PROVISIONAL_SINK_CHAIN_VERSION",
    "EvidenceSink",
    "NullEvidenceSink",
    "RecordingEvidenceSink",
    "replay_result_for",
]

PROVISIONAL_SINK_CHAIN_VERSION = EV_L1_PROVISIONAL_CHAIN_VERSION


@runtime_checkable
class EvidenceSink(Protocol):
    """The injected sink the engine writes its provisional records to (design #31 §12-5)."""

    def record(self, record: EngineEvidenceRecord) -> None:
        """Accept one engine evidence record."""
        ...


class RecordingEvidenceSink:
    """An in-memory provisional sink that keeps every record in arrival order."""

    def __init__(self) -> None:
        """Create an empty sink."""
        self._records: list[EngineEvidenceRecord] = []

    def record(self, record: EngineEvidenceRecord) -> None:
        """Append one record (arrival order is preserved)."""
        self._records.append(record)

    @property
    def records(self) -> tuple[EngineEvidenceRecord, ...]:
        """Every record received so far, in arrival order."""
        return tuple(self._records)


class NullEvidenceSink:
    """A sink that discards records — for callers that supply their own observation path."""

    def record(self, record: EngineEvidenceRecord) -> None:
        """Discard the record."""


def replay_result_for(
    *,
    expected_outcome_digest: str | None,
    actual_outcome_digest: str | None,
    baseline_supported: bool,
    input_complete: bool,
) -> ReplayResultState:
    """Reproducibility judgement over two runs' outcome digests (design #31 §7.2-5)."""
    return compute_replay_result(
        baseline_supported=baseline_supported,
        input_complete=input_complete,
        schema_compatible=True,
        nondeterminism_bounded=True,
        expected_state_digest=expected_outcome_digest,
        actual_state_digest=actual_outcome_digest,
    )
