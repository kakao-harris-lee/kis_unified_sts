"""The tick-source contract — the surfaces every lane of the TOS 틱 원천 웨이브 builds against
(plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 "계약").

**Signatures only. No logic lives here**, deliberately: this module lands first so the wave's
parallel lanes (policy/snapshot issuance, the durable store, the observation journal + time
projection) can be authored in separate worktrees against one committed shape instead of
converging on a shape afterwards.

**What the wave is.** ``tos.marketfeed``'s :class:`~tos.marketfeed.MarketFeedContextResolver`
(``resolver.py:135``) is already real, and its three injected surfaces —
:class:`~tos.marketfeed.SnapshotStore` (``:62``), :class:`~tos.marketfeed.ValueCandidateSource`
(``:84``), :class:`~tos.marketfeed.TimeCoordinateProjection` (``:103``) — are the *only* way a
value reaches a decision. What does not exist is anything in production that **implements** them:
as of ``e3e26e3e`` every caller of ``CriticalInputSnapshot.issue`` / ``DecisionContextCapsule
.issue`` is a test fixture (``tos/tests/**``), which is exactly what ``compose/cli.py:96-100``
records as blocker (c). This package is that upstream producer — the Context Integrity Service
the kernel explicitly keeps outside itself (design #2 §0.2, restated at
``tos/src/tos/marketfeed/__init__.py``'s "(c)" paragraph).

**Two obligations this contract inherits, named rather than assumed.**

* *Per-observation distinctness is the CIS's, not the gate's.* ``tos/tests/marketfeed
  /test_marketfeed_cis_port.py:46-49`` states it plainly: a producer that stamps two bars with one
  as-of collapses the digest chain, and the publication gate detects nothing.
  :meth:`DurableSnapshotStore.latest_as_of` exists so the tick source can refuse rather than hope
  — see :attr:`TickOutcome.SKIPPED_NOT_NEWER`.
* *The ordering coordinate is not ours to claim.* ``EngineDriver._stamp``
  (``engine/driver.py:397``) discards a caller-supplied ``reference`` and re-stamps from its own
  global counter, so a tick payload leaves ``reference`` at the engine default — the same rule
  ``MarketFeedContextResolver.__call__``'s own docstring already states for itself.

**Field state is derived, never declared.** ``value_field_state`` (``marketfeed/value.py:190-230``)
adds an explicit ``UNKNOWN`` floor when no ``FieldEvaluation`` names a key, which is what seals
vacuous validity. A CIS that stamped ``FieldState.VALID`` unconditionally would walk straight
through that seal, so the wave binds every evaluation to a governed Critical Input Policy
(plan §2 decision 2) and this module carries no state constructor at all.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` only. No
``shared.*`` (rule (h)), no network, no clock — the implementations own those, not the contract.
"""

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
    "DurableSnapshotStore",
    "ObservationIntake",
    "RawObservation",
    "TickOutcome",
]


@dataclass(frozen=True)
class RawObservation:
    """One raw market observation, as an upstream collector recorded it.

    This is the runtime's own intake shape, deliberately **not** a kernel type: a
    :class:`~tos.capsule.Observation` is a provenance record whose ``raw.payload_digest`` already
    addresses a payload, and deriving that digest is the snapshot issuer's job (lane A), not the
    collector's. A collector that could hand over a digest could hand over a *wrong* digest and
    have it covered by the snapshot; making the digest derived removes the option.

    ``fields`` is the flat, scalar-keyed payload the preimage is built from — flat because
    :class:`~tos.marketfeed.RawPayloadPreimage` is flat (design #32 §2.3, 미결-3: the preimage
    *form* is provisional, the value ⟺ digest *binding* is what the contract fixes). A
    :class:`~decimal.Decimal` is refused downstream at ``PreimageEntry`` construction rather than
    silently coerced (``marketfeed/records.py:78-88``), so a collector holding a fractional
    magnitude must expose exact integer minor/tick units or leave the field out.

    Attributes:
        raw_event_id: The source's own event identity — becomes ``Observation.raw.raw_event_id``
            and the ``observation_ref`` every candidate value points at. Two observations sharing
            one id make both ambiguous and neither admissible (``value.py`` ``index_observations``).
        instrument: The instrument this observation is about (the scheduler's single-instrument
            scope — see :class:`TickOutcome`'s note on FORWARD-OBLIGATION-MS1).
        as_of_ms: The source event time in epoch milliseconds — the Validity-Window anchor
            (``Observation.time.source_event_time``), never a receipt or wrap time.
        fields: ``(key, value)`` pairs of the raw payload. Order-independent: the shipped
            canonicalizer key-sorts mappings before digesting.
        source_id: The feed/source identity, carried into the observation's source attribution.
        received_ms: The consumer-local receipt anchor, or ``None`` when the collector recorded
            none. ``None`` is a real answer, not a reason to substitute ``as_of_ms``.
    """

    raw_event_id: str
    instrument: str
    as_of_ms: int
    fields: tuple[tuple[str, ScalarValue], ...]
    source_id: str
    received_ms: int | None = None


@runtime_checkable
class ObservationIntake(Protocol):
    """The injected supplier of raw observations (plan §2 decision 4).

    The one surface a real market transport would implement. This wave ships a file-backed
    append-only journal (``journal.py``, lane C) against it; a KIS 모의투자 quote adapter is a
    named follow-up (plan §6 ①), not a hole left open here — the point of the port is that the
    rest of the chain cannot tell them apart, which is the same parity claim
    ``MarketFeedContextResolver``'s own snapshot store makes.

    Returning an empty sequence is a first-class answer ("nothing new"), and the scheduler reports
    it as :attr:`TickOutcome.SKIPPED_NO_OBSERVATION` rather than manufacturing a tick.
    """

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> Sequence[RawObservation]:
        """Return observations for ``instrument`` strictly newer than ``after_as_of_ms``.

        Args:
            instrument: The single instrument in scope.
            after_as_of_ms: The newest as-of already issued, or ``None`` when none has been.

        Returns:
            The new observations, oldest first. Empty when there are none.
        """
        ...


@runtime_checkable
class DurableSnapshotStore(Protocol):
    """The durable half of the admitted-snapshot injection port (design #38; plan §2 decision 3).

    One implementation plays two kernel roles — :class:`~tos.marketfeed.SnapshotStore` (via
    :meth:`__call__`, the exact shipped signature) and
    :class:`~tos.marketfeed.ValueCandidateSource` (via :meth:`candidates`) — because both read the
    same durable rows: the snapshot body and the preimages its observations' digests address.
    Splitting them across two stores would let the two halves disagree about what was issued.

    **Durability is load-bearing, not hygiene.** The value ⟺ digest check recomputes the digest
    from the producer's preimage and compares it against what the snapshot-covered observation
    attests (``value.py:514-523``). A process that kept preimages in memory could not re-publish
    a view for a snapshot it issued before a restart — the tick would resolve to
    ``SNAPSHOT_UNRESOLVED`` and every value operand would go ``UNKNOWN``, silently, with a
    perfectly valid-looking snapshot id in hand.
    """

    def put(
        self,
        snapshot: CriticalInputSnapshot,
        preimages: Mapping[str, RawPayloadPreimage],
    ) -> None:
        """Durably record an issued snapshot and the preimages its observations address.

        Args:
            snapshot: The issued snapshot (``snapshot_id``/``canonical_digest`` both concrete).
            preimages: ``raw_event_id -> preimage`` for every observation the snapshot covers.
        """
        ...

    def __call__(
        self, *, snapshot_id: str | None, canonical_digest: str | None
    ) -> CriticalInputSnapshot | None:
        """Resolve a content-addressed reference to its body, or ``None``.

        The digest is re-checked, not merely the id: a store that returned a stale body held under
        a live id would pass off a substitute, which ADR-002-018 §15:386 refuses and which
        ``publish_context_value_view``'s own binding gate would then have to catch second-hand.
        ``None`` means "this store has no such snapshot" and is handled fail-closed upstream.
        """
        ...

    def candidates(
        self, snapshot: CriticalInputSnapshot, *, instrument_key: InstrumentKey
    ) -> Sequence[AdmittedValue]:
        """Supply the candidate value claims for one snapshot and dispatch scope.

        Candidates are *claims*, never admissions: the publication gate verifies each against the
        snapshot, so the most a dishonest store achieves is a rejection record
        (``resolver.py:89``).
        """
        ...

    def latest_as_of(self, *, instrument: str) -> int | None:
        """The newest ``as_of_ms`` this store has already issued a snapshot for, or ``None``.

        The distinctness obligation ``test_marketfeed_cis_port.py:46-49`` leaves upstream: the
        tick source reads this and refuses a not-newer observation instead of issuing a second
        snapshot under a colliding as-of.
        """
        ...


class TickOutcome(StrEnum):
    """Why one scheduler pass did or did not produce a ``DECISION_TICK`` (plan §2 decision 7).

    Every non-``TICKED`` member is a *named* absence. A scheduler that returned a bare ``bool``
    would make "the session is closed" and "the policy refused this observation" the same
    observation to an operator reading a log, which is the distinction the ∅ 양방향 discipline
    exists to keep.

    The scheduler this vocabulary serves is **single-instrument** on purpose: a live multi-symbol
    event source owes the engine core the same single-continuity ingest order its backtest
    counterpart provides, and that obligation is FORWARD-OBLIGATION-MS1 — recorded as *new and
    unratified* at ``tos/src/tos/backtest/driver.py:78-86``, not as something this wave may assume.
    """

    TICKED = "TICKED"
    SKIPPED_NO_OBSERVATION = "SKIPPED_NO_OBSERVATION"
    SKIPPED_NOT_NEWER = "SKIPPED_NOT_NEWER"
    SKIPPED_SESSION_CLOSED = "SKIPPED_SESSION_CLOSED"
    SKIPPED_INTERVAL = "SKIPPED_INTERVAL"
    REFUSED_POLICY = "REFUSED_POLICY"
