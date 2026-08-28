"""Provisional evidence sink (design #31 §5.1 / §12-5) + the replay-result adapter.

⚠ **Provisional.** The full Evidence Store runtime (ADR-002-016) — custody, integrity policy,
segment commitment, retention — is deferred (design #31 §9-3), so this is an injected sink that
receives engine-local :class:`~tos.engine.records.EngineEvidenceRecord` values. Issuing a
:class:`~tos.evidence.SafetyEvidenceEnvelope` whose policy / custody / commitment chain do not
exist would be over-realization, so it is not done.

What *is* reused from :mod:`tos.evidence` is the pure divergence predicate
:func:`~tos.evidence.compute_replay_result`: :func:`replay_result_for` feeds two runs' recorded
outcome digests into it, which is exactly the RFC-003 §10:345-348 reproducibility question the
design's §7.2-5 property targets. Its honest scope is **reproducibility (same inputs ⇒ same
outcome)**, not **distinctness** (different bars ⇒ different identity) — the latter depends on
D-E2 producing distinct Snapshot digests and is deferred (design #31 §6 Gap-1 / §9-9).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3).
"""

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

#: The provisional (explicitly non-production) chain version this sink labels itself with, reused
#: from :mod:`tos.evidence` rather than invented (design #31 §1.1 (a): every slice digest is
#: non-production while ADR-002-018 OQ1 / ADR-002-016 §27 Q2 stay open).
PROVISIONAL_SINK_CHAIN_VERSION = EV_L1_PROVISIONAL_CHAIN_VERSION


@runtime_checkable
class EvidenceSink(Protocol):
    """The injected sink the engine writes its provisional records to (design #31 §12-5)."""

    def record(self, record: EngineEvidenceRecord) -> None:
        """Accept one engine evidence record."""
        ...


class RecordingEvidenceSink:
    """An in-memory provisional sink that keeps every record in arrival order.

    ⚠ Not an Evidence Store: no durability, no custody, no integrity anchor, no retention. It
    exists so a run's outcomes, halts, degradations, and egress transitions are *observable* —
    the slice's whole value is that the wiring is demonstrable (design #31 §1.1).
    """

    def __init__(self) -> None:
        """Create an empty sink."""
        self._records: list[EngineEvidenceRecord] = []

    def record(self, record: EngineEvidenceRecord) -> None:
        """Append one record (arrival order is preserved).

        Args:
            record: The engine evidence record.
        """
        self._records.append(record)

    @property
    def records(self) -> tuple[EngineEvidenceRecord, ...]:
        """Every record received so far, in arrival order."""
        return tuple(self._records)


class NullEvidenceSink:
    """A sink that discards records — for callers that supply their own observation path.

    It still satisfies the :class:`EvidenceSink` protocol, so the engine never has to branch on
    "is there a sink"; a missing sink would be an unrecorded halt, which the design forbids.
    """

    def record(self, record: EngineEvidenceRecord) -> None:
        """Discard the record.

        Args:
            record: The engine evidence record (ignored).
        """


def replay_result_for(
    *,
    expected_outcome_digest: str | None,
    actual_outcome_digest: str | None,
    baseline_supported: bool,
    input_complete: bool,
) -> ReplayResultState:
    """Reproducibility judgement over two runs' outcome digests (design #31 §7.2-5).

    A thin adapter onto the shipped :func:`~tos.evidence.compute_replay_result`: a ``MATCH`` needs
    a supported baseline, complete inputs, a compatible schema, bounded nondeterminism, and equal
    present digests. The engine passes ``schema_compatible`` and ``nondeterminism_bounded`` as
    positively established because the decision pipeline it replays is a pure function of
    ``(strategy, capsule, config)`` with no ambient clock, RNG, network, or filesystem in its
    signature (``tos.dsl.determinism`` module docstring; DCE-INV-003) and the engine adds no
    nondeterministic source of its own — the §7.1 canary is what keeps that true.

    **Scope honesty:** this establishes reproducibility (same inputs ⇒ same outcome), never
    distinctness (design #31 §6 Gap-1 / §7.2-5 / §9-9).

    Args:
        expected_outcome_digest: The first run's recorded outcome digest.
        actual_outcome_digest: The second run's recorded outcome digest.
        baseline_supported: Whether the exact baseline is supported.
        input_complete: Whether every required input was present.

    Returns:
        The conservative :class:`~tos.evidence.ReplayResultState`.
    """
    return compute_replay_result(
        baseline_supported=baseline_supported,
        input_complete=input_complete,
        schema_compatible=True,
        nondeterminism_bounded=True,
        expected_state_digest=expected_outcome_digest,
        actual_state_digest=actual_outcome_digest,
    )
