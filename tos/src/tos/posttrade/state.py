"""posttrade lifecycle orthogonality + append-only generation order (§3.2/§2.2-1).

The rules that concern **obligation state and state over time** (design #24 §3.2/§2.2-1):

* **orthogonality (§10 line 303-310)** — :func:`obligation_axes_not_collapsed`: the five
  orthostate-owned axes the ADR keeps the obligation-lifecycle state orthogonal to stay five
  separate injected fields on
  :class:`~tos.posttrade.records.EconomicObligationRecord`, and the posttrade-owned
  :attr:`~tos.posttrade.records.EconomicObligationRecord.lifecycle_state` is a *sixth*,
  non-authoritative coordinate;
* **append-only versioned order (§11 line 330 / §20 line 460)** — the three series this
  package serializes: obligation records, finality proofs, and statement coverage manifests.
  Each has an ``*_generation_order`` comparison and an ``*_generation_append_only`` sequence
  predicate.

**Transition validity is deliberately absent (design #24 §2.2-1).** Whether one
:class:`~tos.posttrade.vocabulary.PostTradeObligationLifecycleState` may follow another
depends on the rcl capacity state, the recon field confidence, the field-specific finality
proof, and the statement coverage — all runtime gates (EV-L2/L3). Phase 1 authors the
vocabulary, the no-collapse structure, and the append-only order only; nothing here *sets* a
state, and no lifecycle label grants anything (§10 line 312, sealed by the all-false
:class:`~tos.posttrade._base.AllFalsePostTradeConsequence`).

The append-only generation order is **not** re-authored: it REUSES ``tos.ordering``
(``Ordering`` / ``OrderingEvent`` / ``compare_order``, which depends only on
``tos.canonical``) — design #24 §3.2. ADR §4 line 118 / §5.5 make the PTOL "the sole
serialization authority ... it SHALL append and order obligation identities, versions,
lifecycle transitions, breaks, supersessions, finality-proof bindings, and the monotonic
**Post-Trade Obligation Generation**", and ordering supplies exactly that order / generation
/ fencing coordinate. The PTOL **serializer runtime** itself (consensus, writer epoch,
restore, idempotency) is PTF-EV-010 ``EV-L2/3``; Phase 1 holds only the
generation-monotone and append-only-no-overwrite **structure**.

**A wall clock never orders**: this package reads no clock at all — every age bound is a
null VP-002 key (design #24 §8.1) and every freshness verdict is an injected ``tos.time``
token.

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.canonical`` (via the records)
only; **no sibling** ``tos.*`` (sibling edge 0, design #24 §0.3/§0.4b).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.posttrade.records import (
    EconomicObligationRecord,
    PostTradeFinalityProof,
    StatementCoverageManifest,
)
from tos.posttrade.vocabulary import ORTHOGONAL_POST_TRADE_AXES

__all__ = [
    # §2.2-1 orthogonality (§10 line 303-310 no-collapse)
    "obligation_axes_not_collapsed",
    # §3.2 append-only generation order (tos.ordering REUSE) — three series
    "obligation_generation_order",
    "obligation_generation_append_only",
    "finality_proof_generation_order",
    "finality_proof_generation_append_only",
    "statement_manifest_generation_order",
    "statement_manifest_generation_append_only",
]


# ===========================================================================
# §2.2-1 orthogonality — §10 line 303-310 no-collapse
# ===========================================================================


def obligation_axes_not_collapsed(record: EconomicObligationRecord | None) -> bool:
    """Whether the five orthogonal axes stay five separate fields (ADR §10 line 303-310).

    §10 line 305 keeps the obligation-lifecycle axis "orthogonal to ADR-002-006
    Knowledge/Evidence State", and §10 line 303-310 lists the order, knowledge, capacity,
    authority, and evidence-confidence axes it must not be fused with. Collapsing them into
    one enum is the ADR-002-005 §11 defect class this package must not repeat: a single fused
    token cannot express "the obligation says ``SATISFIED_PENDING_FINALITY`` while the broker
    order state is ``UNKNOWN`` and the capacity is ``TRAPPED_CONSUMED``", which is precisely
    the state that must stay representable.

    A **structural** check: each of the five
    :data:`~tos.posttrade.vocabulary.ORTHOGONAL_POST_TRADE_AXES` names must exist as its own
    field on the record, and none of them may be the posttrade-owned ``lifecycle_state``
    coordinate. Each axis field carries a **sibling-owned token** (orthostate
    ``BrokerOrderState`` / ``KnowledgeState``, rcl ``CapacityState``, authority
    ``AuthorityState``, recon ``FieldConfidenceClass``) that this package **consumes and
    never sets** — the tokens are opaque strings precisely because ``tos.posttrade`` holds
    sibling edge 0 and cannot name their types.

    This proves the *shape*, not the legality of any particular combination: the coupling
    invariants over those axes are orthostate's ``no_coupling_violation``
    (``orthostate/predicates.py:206``), whose own proposition is "no violation **detected**,
    never certified fully legal" (necessary, not sufficient).

    Args:
        record: The obligation record to check (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff all five axes exist as separate, non-``lifecycle_state`` fields.
    """
    if record is None:
        return False
    field_names = set(type(record).model_fields)
    if "lifecycle_state" not in field_names:
        return False
    for axis in ORTHOGONAL_POST_TRADE_AXES:
        if axis not in field_names:
            return False
        if axis == "lifecycle_state":
            return False
    return len(set(ORTHOGONAL_POST_TRADE_AXES)) == len(ORTHOGONAL_POST_TRADE_AXES)


# ===========================================================================
# §3.2 append-only generation order (tos.ordering REUSE) — three series
# ===========================================================================


def obligation_generation_order(
    earlier: EconomicObligationRecord,
    later: EconomicObligationRecord,
) -> Ordering:
    """Compare two Post-Trade Obligation Generations with the core ordering law (§3.2).

    The append-only order of obligation versions is **not** re-authored here: it REUSES
    ``tos.ordering`` (``compare_order`` over ``OrderingEvent``), which depends only on
    ``tos.canonical``. A generation is a plain ``int`` coordinate on the record, not a heavy
    artifact (the #13 are / #16 afg / #18 replacement / #21 nontrade precedent).

    **A wall clock never orders**: the comparison rests only on the injected
    ``obligation_generation`` carried on the core ``source_native_sequence`` coordinate,
    scoped by ``idempotency_key`` as the ``source_continuity_id`` — so two records from
    **different** obligation series are ``AMBIGUOUS``, never silently ordered. A missing
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
            source_native_sequence=earlier.obligation_generation,
        ),
        OrderingEvent(
            source_continuity_id=later.idempotency_key,
            source_native_sequence=later.obligation_generation,
        ),
    )


def obligation_generation_append_only(
    records: Sequence[EconomicObligationRecord],
) -> bool:
    """Whether an obligation sequence is strictly append-only (§11 line 330; §20 line 460).

    §11 line 330: "A later correction supersedes the proof, **advances generation** ... it
    does not erase history." §20 line 460 forbids destructively rewriting an earlier version.
    Each generation is an **immutable** record: a legitimate progression or correction is a
    **new** generation, never an in-place mutation (design #24 §2.3). This predicate asserts
    that discipline over an observed sequence: every generation must be concrete and strictly
    increasing.

    A sequence shorter than two records has nothing to violate and is ``True``; an absent
    (``None``) generation is UNKNOWN and fails closed, because an unordered record cannot be
    proven append-only.

    Args:
        records: The observed obligation records, in claimed order.

    Returns:
        ``True`` iff every generation is concrete and strictly increasing.
    """
    return _strictly_increasing(record.obligation_generation for record in records)


def finality_proof_generation_order(
    earlier: PostTradeFinalityProof,
    later: PostTradeFinalityProof,
) -> Ordering:
    """Compare two finality-proof bound generations with the core ordering law (§3.2).

    The finality-proof counterpart of :func:`obligation_generation_order`, scoped by the
    proof's ``idempotency_key`` continuity. §11 line 330: a later correction "supersedes the
    proof, advances generation", so proofs form their own append-only series and an earlier
    proof's bound generation must fall behind — which is exactly what
    :func:`~tos.posttrade.predicates.finality_proof_current` then reads as **not current**
    (the finality reopen, PTF-INV-013).

    Args:
        earlier: The proof believed to be earlier.
        later: The proof believed to be later.

    Returns:
        The :class:`~tos.ordering.Ordering` verdict (``AMBIGUOUS`` when either bound
        generation is absent or the two proofs belong to different series).
    """
    return compare_order(
        OrderingEvent(
            source_continuity_id=earlier.idempotency_key,
            source_native_sequence=earlier.bound_generation,
        ),
        OrderingEvent(
            source_continuity_id=later.idempotency_key,
            source_native_sequence=later.bound_generation,
        ),
    )


def finality_proof_generation_append_only(
    proofs: Sequence[PostTradeFinalityProof],
) -> bool:
    """Whether a finality-proof sequence is strictly append-only (§11 line 330).

    §11 line 330: a correction "supersedes the proof, advances generation ... **it does not
    erase history**." A superseding proof is appended at the next generation; the superseded
    one stays. Same discipline as :func:`obligation_generation_append_only`: concrete and
    strictly increasing, with an absent generation failing closed.

    Args:
        proofs: The observed finality proofs, in claimed order.

    Returns:
        ``True`` iff every bound generation is concrete and strictly increasing.
    """
    return _strictly_increasing(proof.bound_generation for proof in proofs)


def statement_manifest_generation_order(
    earlier: StatementCoverageManifest,
    later: StatementCoverageManifest,
) -> Ordering:
    """Compare two statement-manifest generations with the core ordering law (§3.2).

    The statement counterpart of :func:`obligation_generation_order`, scoped by the
    manifest's ``idempotency_key`` continuity. §19 line 442 makes restatement a first-class
    case, so a revised manifest is a **new** generation in the same series rather than an
    edit of the earlier one.

    Args:
        earlier: The manifest believed to be earlier.
        later: The manifest believed to be later.

    Returns:
        The :class:`~tos.ordering.Ordering` verdict (``AMBIGUOUS`` when either generation is
        absent or the two manifests belong to different series).
    """
    return compare_order(
        OrderingEvent(
            source_continuity_id=earlier.idempotency_key,
            source_native_sequence=earlier.manifest_generation,
        ),
        OrderingEvent(
            source_continuity_id=later.idempotency_key,
            source_native_sequence=later.manifest_generation,
        ),
    )


def statement_manifest_generation_append_only(
    manifests: Sequence[StatementCoverageManifest],
) -> bool:
    """Whether a statement-manifest sequence is strictly append-only (§19 line 442; §20).

    A restatement is an **append** at the next generation, never an overwrite of the
    preliminary manifest (§20 line 460). Same discipline as
    :func:`obligation_generation_append_only`.

    Args:
        manifests: The observed coverage manifests, in claimed order.

    Returns:
        ``True`` iff every generation is concrete and strictly increasing.
    """
    return _strictly_increasing(manifest.manifest_generation for manifest in manifests)


def _strictly_increasing(generations: Iterable[int | None]) -> bool:
    """Whether an iterable of ``int | None`` generations is concrete and increasing.

    Shared by the three append-only predicates so the three series cannot drift apart. An
    absent generation is UNKNOWN and fails closed (an unordered record cannot be proven
    append-only); equality is a violation too, because two records sharing a generation are
    an in-place edit rather than an append (§20 line 460).

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
