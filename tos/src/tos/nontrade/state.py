"""nontrade workflow-lifecycle structure + append-only generation order (§3.2/§5.4).

The rules that concern **workflow state and state over time** (design #21 §5.4 / §3.2):

* **orthogonality (§6 line 123)** — :func:`event_axes_not_collapsed`: the five axes the
  ADR forbids collapsing into the non-trade event state stay five separate injected fields
  on :class:`~tos.nontrade.records.NonTradeEventRecord`, and the nontrade-owned
  :attr:`~tos.nontrade.records.NonTradeEventRecord.workflow_state` is a *sixth*,
  non-authoritative coordinate;
* **append-only versioned order (§10 line 219 / §20 line 380)** —
  :func:`event_generation_order`, :func:`event_generation_append_only`,
  :func:`correction_generation_order`, :func:`correction_generation_append_only`.

**Transition validity is deliberately absent (design #21 §5.4).** Whether one
:class:`~tos.nontrade.vocabulary.NonTradeEventWorkflowState` may follow another depends on
the rcl capacity remap, the recon field confidence (§6 line 143 "``RECONCILED`` requires
evidence sufficient under ADR-002-006"), the venue admissibility, and trustworthy time —
all runtime gates (EV-L2/L3). Phase 1 authors the vocabulary, the no-collapse structure,
and the append-only order only; nothing here *sets* a state, and no label grants anything
(§6 line 144, sealed by the all-false
:class:`~tos.nontrade.records.NonTradeAuthorityEffect`).

The append-only generation order is **not** re-authored: it REUSES ``tos.ordering``
(``Ordering`` / ``OrderingEvent`` / ``compare_order``, which depends only on
``tos.canonical``) — design #21 §3.2. ADR §10 line 219 "A correction or reversal is a **new
event linked to** the event it supersedes" and §20 line 380 "every event version" require
an append-only versioned order, and ordering supplies the order / generation / fencing
coordinate. **A wall clock never orders**: this package reads no clock at all (§8 line 175
clock recovery grants no retroactive authority) — time health, freshness, and effective
boundaries are injected tokens produced by ``tos.time``.

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.canonical`` (via the records)
only; **no sibling** ``tos.*`` (sibling edge 0, design #21 §0.3/§0.4b).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from tos.nontrade.records import CorrectionReversalRecord, NonTradeEventRecord
from tos.nontrade.vocabulary import ORTHOGONAL_EVENT_AXES
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    # §5.4 orthogonality (§6 line 123 no-collapse)
    "event_axes_not_collapsed",
    # §3.2 append-only generation order (tos.ordering REUSE)
    "event_generation_order",
    "event_generation_append_only",
    "correction_generation_order",
    "correction_generation_append_only",
]


# ===========================================================================
# §5.4 orthogonality — §6 line 123 no-collapse
# ===========================================================================


def event_axes_not_collapsed(record: NonTradeEventRecord | None) -> bool:
    """Whether the five orthogonal axes stay five separate fields (ADR §6 line 123).

    §6 line 123 verbatim: "Non-trade event state SHALL remain orthogonal to order,
    exposure, capacity, authority, and evidence-confidence state." Collapsing them into one
    enum is the ADR-002-005 §11 defect class this package must not repeat: a single fused
    token cannot express "the workflow says ``APPLIED_LOCAL`` while the broker order state
    is ``UNKNOWN`` and the capacity is ``TRAPPED_CONSUMED``", which is precisely the state
    that must stay representable.

    A **structural** check (design #21 §5.4): each of the five
    :data:`~tos.nontrade.vocabulary.ORTHOGONAL_EVENT_AXES` names must exist as its own
    field on the record, and none of them may be the nontrade-owned ``workflow_state``
    coordinate. Each axis field carries a **sibling-owned token** (orthostate
    ``BrokerOrderState`` / ``KnowledgeState``, rcl ``CapacityState``, authority
    ``AuthorityState``, recon ``FieldConfidenceClass``) that this package **consumes and
    never sets** — the tokens are opaque strings precisely because ``tos.nontrade`` holds
    sibling edge 0 and cannot name their types.

    This proves the *shape*, not the legality of any particular combination: the coupling
    invariants over those axes are orthostate's ``no_coupling_violation``
    (``orthostate/predicates.py:206``), whose own proposition is "no violation **detected**,
    never certified fully legal" (necessary, not sufficient).

    Args:
        record: The event record to check (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff all five axes exist as separate, non-``workflow_state`` fields.
    """
    if record is None:
        return False
    field_names = set(type(record).model_fields)
    if "workflow_state" not in field_names:
        return False
    for axis in ORTHOGONAL_EVENT_AXES:
        if axis not in field_names:
            return False
        if axis == "workflow_state":
            return False
    return len(set(ORTHOGONAL_EVENT_AXES)) == len(ORTHOGONAL_EVENT_AXES)


# ===========================================================================
# §3.2 append-only generation order (tos.ordering REUSE)
# ===========================================================================


def event_generation_order(
    earlier: NonTradeEventRecord,
    later: NonTradeEventRecord,
) -> Ordering:
    """Compare two event generations with the core ordering law (design #21 §3.2).

    The append-only order of non-trade event versions is **not** re-authored here: it
    REUSES ``tos.ordering`` (``compare_order`` over ``OrderingEvent``), which depends only
    on ``tos.canonical``. A generation is a plain ``int`` coordinate on the record, not a
    heavy artifact (the #13 are / #16 afg / #18 replacement precedent).

    **A wall clock never orders** (§8 line 175): the comparison rests only on the injected
    ``workflow_generation`` carried on the core ``source_native_sequence`` coordinate,
    scoped by ``idempotency_key`` as the ``source_continuity_id`` — so two records from
    **different** event series are ``AMBIGUOUS``, never silently ordered. A missing
    generation is likewise ``AMBIGUOUS`` rather than an assumed precedence.

    Args:
        earlier: The record believed to be earlier.
        later: The record believed to be later.

    Returns:
        The :class:`~tos.ordering.Ordering` verdict (``AMBIGUOUS`` when either generation is
        absent or the two records belong to different series).
    """
    return compare_order(
        OrderingEvent(
            source_continuity_id=earlier.idempotency_key,
            source_native_sequence=earlier.workflow_generation,
        ),
        OrderingEvent(
            source_continuity_id=later.idempotency_key,
            source_native_sequence=later.workflow_generation,
        ),
    )


def event_generation_append_only(records: Sequence[NonTradeEventRecord]) -> bool:
    """Whether an event-record sequence is strictly append-only (ADR §10 line 219).

    §10 line 219: "History SHALL be corrected by new versioned facts, not destructive
    overwrite." §20 line 380 requires "every event version" to be retained. Each generation
    is an **immutable** record: a legitimate progression or correction is a **new**
    generation, never an in-place mutation (design #21 §2.3). This predicate asserts that
    discipline over an observed sequence: every generation must be concrete and strictly
    increasing.

    A sequence shorter than two records has nothing to violate and is ``True``; an absent
    (``None``) generation is UNKNOWN and fails closed, because an unordered record cannot be
    proven append-only.

    Args:
        records: The observed event records, in claimed order.

    Returns:
        ``True`` iff every generation is concrete and strictly increasing.
    """
    return _strictly_increasing(record.workflow_generation for record in records)


def correction_generation_order(
    earlier: CorrectionReversalRecord,
    later: CorrectionReversalRecord,
) -> Ordering:
    """Compare two correction generations with the core ordering law (design #21 §3.2).

    The correction / reversal counterpart of :func:`event_generation_order`, scoped by the
    correction's ``idempotency_key`` continuity. §10 line 219: a correction "is a new event
    linked to the event it supersedes", so corrections form their own append-only series.

    Args:
        earlier: The correction believed to be earlier.
        later: The correction believed to be later.

    Returns:
        The :class:`~tos.ordering.Ordering` verdict (``AMBIGUOUS`` when either generation is
        absent or the two corrections belong to different series).
    """
    return compare_order(
        OrderingEvent(
            source_continuity_id=earlier.idempotency_key,
            source_native_sequence=earlier.correction_generation,
        ),
        OrderingEvent(
            source_continuity_id=later.idempotency_key,
            source_native_sequence=later.correction_generation,
        ),
    )


def correction_generation_append_only(
    records: Sequence[CorrectionReversalRecord],
) -> bool:
    """Whether a correction sequence is strictly append-only (ADR §10 line 219; §16 line 313).

    §16 line 313: "local history SHALL preserve both the original observation and correcting
    event." A correction never overwrites its predecessor; it is appended as a new
    generation. Same discipline as :func:`event_generation_append_only`: concrete and
    strictly increasing, with an absent generation failing closed.

    Args:
        records: The observed correction records, in claimed order.

    Returns:
        ``True`` iff every generation is concrete and strictly increasing.
    """
    return _strictly_increasing(record.correction_generation for record in records)


def _strictly_increasing(generations: Iterable[int | None]) -> bool:
    """Whether an iterable of ``int | None`` generations is concrete and increasing.

    Shared by the two append-only predicates so the two series cannot drift apart. An
    absent generation is UNKNOWN and fails closed (an unordered record cannot be proven
    append-only); equality is a violation too, because two records sharing a generation are
    an in-place edit rather than an append.

    Args:
        generations: An iterable of ``int | None`` generation coordinates in claimed order.

    Returns:
        ``True`` iff every generation is concrete and strictly increasing.
    """
    previous: int | None = None
    for current in generations:
        if current is None:
            return False
        if previous is not None and current <= previous:
            return False
        previous = current
    return True
