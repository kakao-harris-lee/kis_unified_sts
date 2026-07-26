"""cur injected inputs + value models + generation-order ordering REUSE (design #23 §2.1/§3.2).

Two roles:

* **injected value / input models (design #23 §2.1)** — the committed ordering identity
  (:class:`CurrentnessRevision` — §5.4 "an ordering identity, not wall-clock time"), one vector
  dimension coordinate (:class:`CurrentnessDimension` — each owner's produced verdict / generation /
  digest injected, **not** re-authored), the injected egress-scope coordinate mirror
  (:class:`EgressProofCoordinateSet` — the *verification target*, carrying the egress-owned
  ``local_latch_clear`` injected latch state, **not** an egress re-authoring, §0.4c/d), the
  conditional restricted-live trial claim group (:class:`TrialClaims` — opaque optional scalars
  deferred to RLP, §0.4f), one owner restriction submission (:class:`OwnerSubmission`, §6.3), and one
  per-domain proof (:class:`DomainProof`, §6.7). Every one is a **pydantic v2 frozen model**
  (``frozen=True, extra="forbid"`` via :class:`~tos.cur._base.FrozenModel`): ``extra="forbid"`` is
  the schema-level "omission is restrictive", and frozen is the append-only realization — there is
  **no** update / delete / mutate method on any model (design #23 §2.3/§4.1).

* **generation order (design #23 §3.2 ordering REUSE)** — :func:`floor_strictly_advances` REUSES
  ``tos.ordering.compare_order`` (no re-authored order) for the monotonic restrictive-floor advance
  (§10/§11) and the parent/child floor order (§16). cur owns the fence *meaning* (restriction /
  non-revival); ordering only carries the monotonic order. **A wall clock never orders — cur reads
  no clock**: a Currentness Revision is an ordering identity, not wall-clock time (§5.4/§0.4e), so
  this package is clock-free.

**Numeric-bound freedom (design #23 §8; ADR §8 non-scope).** cur carries no numeric floor / age /
bound constant: every such value is an **injected** opaque scalar (null in Phase 1, fail-closed at
the consuming predicate). Nothing numeric is hardcoded — the cur logic is over StrEnums, booleans,
set / coordinate membership, and injected values only.

**Injected-verdict discipline (design #23 §1/§0.4b over-realization + duplication boundary).** Every
dimension owner's ``positively_established`` / ``bound_generation`` / ``bound_digest`` is an
**injected** produced verdict / scalar / digest: cur does **not** re-decide any owner's business
safety (spg profile validity, are aggregate-risk, iap approval, ioc conformance, venue admissibility,
capsule CII, liveauth Live Authorization, authority epoch, time freshness, 026-030 governance) — it
consumes the produced fact and judges only present / floor / revision / structure (§1 line 21).

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.cur.*`` only; no ``shared.*``, no
other sibling ``tos.*`` (design #23 §0.3). Clock-free.
"""

from __future__ import annotations

from tos.cur._base import FrozenModel
from tos.cur.vocabulary import DimensionKey, ProofResult
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "CurrentnessRevision",
    "CurrentnessDimension",
    "EgressProofCoordinateSet",
    "TrialClaims",
    "OwnerSubmission",
    "DomainProof",
    "floor_strictly_advances",
]


class CurrentnessRevision(FrozenModel):
    """One committed Currentness Revision — an ordering identity (ADR-002-024 §5.4; design #23 §2.1).

    §5.4 verbatim: "A Currentness Revision ... is an **ordering identity, not wall-clock time** and
    not proof that unobserved external facts do not exist." So it carries an immutable identity plus
    an injected ordering coordinate (``commit_index`` — a committed ordering scalar, **not** a clock),
    never a timestamp. Two revisions compare by **value equality** (pydantic frozen ``__eq__``) for
    :func:`~tos.cur.predicates.single_revision_consistent` (every dimension must sit at exactly one
    revision, §9 line 266); a wall clock never participates (cur is clock-free, §0.4e). The optional
    ``commit_index`` feeds the ``tos.ordering`` REUSE for the monotonic floor advance (§10/§16) — it
    is a committed ordering value, not time.
    """

    revision_id: str | None = None
    #: The committed ordering coordinate (an ordering scalar, NOT a clock — §5.4). ``None`` ⇒ the
    #: revision is order-unlocatable and fails closed at the consuming predicate.
    commit_index: int | None = None


class CurrentnessDimension(FrozenModel):
    """One Safety Currentness Vector dimension coordinate (ADR-002-024 §9; design #23 §2.1).

    §9 line 250-262: one dependency dimension the vector aggregates — its owner identity, the owner's
    **injected** produced bound generation + bound digest, the restrictive floor that must be met
    (§10), the owner's **injected** ``positively_established`` verdict, and the Currentness Revision
    the coordinate sits at. Every produced fact is **injected** — cur re-authors **no** owner
    business logic (duplication boundary, §1 line 21 / §3.5); it judges only present / established /
    floor / revision (§0.4b).

    ``positively_established`` is **positive-polarity** (design #23 §4.3): an owner must have
    *actively established* the dimension. A ``None`` / ``False`` is **not established ⇒ fail-closed**
    (the venue ``current_actively_established is not True`` precedent; §5.2) — absence is never
    currentness (§5.4). A ``None`` on any identity / generation / digest / revision coordinate also
    fails closed (:func:`~tos.cur.predicates.dimension_positively_established`).
    """

    dimension_key: DimensionKey | None = None
    owner_identity: str | None = None
    #: Injected — the owner's produced bound generation (an ordering scalar; §10 floor comparison).
    bound_generation: int | None = None
    #: Injected — the owner's produced bound content digest (§9 line 264 integrity evidence).
    bound_digest: str | None = None
    #: Injected — the restrictive floor this dimension's generation must meet (§10; ``None`` ⇒ deny).
    restrictive_floor: int | None = None
    #: Injected owner verdict — positively established (``None`` / ``False`` ⇒ not current, §5.2).
    positively_established: bool | None = None
    #: The Currentness Revision this coordinate sits at (single-revision consistency, §5.3).
    at_revision: CurrentnessRevision | None = None


class EgressProofCoordinateSet(FrozenModel):
    """The injected egress-scope coordinate mirror (ADR-002-024 §12 line 310-311; design #23 §2.1).

    A **mirror** of the egress-owned final-egress coordinates (principal / deployment / credential /
    signer / route / endpoint / broker session), carried as an **injected verification target** —
    **not** an egress re-authoring (design #23 §0.4c/§3.5; cur imports no egress). It also carries the
    egress-owned **injected** ``local_latch_clear`` latch state (§5.7 / §0.4d): the Local Restrictive
    Latch state machine + monotonic resolver ``monotonic_denial_no_revival`` is egress-owned (Final
    Egress Trust Boundary = ADR-002-013), and cur **consumes** the resolved latch as an injected
    ``bool | None`` — it re-authors **no** latch state machine. ``local_latch_clear`` is
    **positive-polarity** (§5.7 "positively established ``CLEAR``"): ``is True`` ⇒ CLEAR;
    ``None`` / ``False`` ⇒ not clear ⇒ deny (the egress ``None`` ⇒ ``DENY_LATCHED`` behavioural
    equivalent, §0.4d). Consumed by :func:`~tos.cur.predicates.proof_admissible`.
    """

    principal: str | None = None
    deployment: str | None = None
    credential: str | None = None
    signer: str | None = None
    route: str | None = None
    endpoint: str | None = None
    broker_session: str | None = None
    #: Injected egress-owned latch state — ``True`` = CLEAR; ``None`` / ``False`` = deny (§5.7/§0.4d).
    local_latch_clear: bool | None = None


class TrialClaims(FrozenModel):
    """The conditional restricted-live trial claim group (ADR-002-024 §9:258 / §12; design #23 §2.1).

    §9:258: a restricted-live trial (ADR-002-025 RLP) vector / proof carries the Trial Policy / Plan /
    Run / Promotion Generation, the remaining envelope, and the abort generation as **conditional**
    claims. Phase 1 carries these as an **opaque optional scalar group**; the actual trial-content
    validation is deferred to RLP (``tos.rlp``, not landed — design #23 §0.4f / §9.2 item 16), so cur
    cites **no** RLP code (phantom seal). An all-optional value model — a non-trial vector leaves it
    ``None`` (§9 conditional).
    """

    trial_policy_generation: int | None = None
    trial_plan_generation: int | None = None
    trial_run_generation: int | None = None
    promotion_generation: int | None = None
    remaining_envelope: str | None = None
    abort_generation: int | None = None


class OwnerSubmission(FrozenModel):
    """One owner restriction submission (ADR-002-024 §10 line 280; design #23 §2.1/§6.3).

    An injected record of one owner's currentness submission for a scope, with its
    **negative-polarity** conflict flags (design #23 §4.3): a conflicting / forked /
    sequence-regressed / missing-predecessor / unverifiable-scope submission forces a restrictive
    closure over the **union** of credible scopes (§10 line 280 "restrictive closure over the union
    of credible scopes"). Consumed by :func:`~tos.cur.predicates.conflicting_owner_restricts` and
    :func:`~tos.cur.predicates.restrictive_union_scope`. Every flag is ``bool | None`` and negative-
    polarity: ``is not False`` (``True`` / ``None``) ⇒ conservatively restrictive (a ``None`` unknown
    conflict is denial, §4.3).
    """

    owner_identity: str | None = None
    affected_scope: tuple[str, ...] = ()
    #: Negative-polarity — ``is not False`` (True / None) ⇒ conflicting ⇒ restrict (§10/§4.3).
    is_conflicting: bool | None = None
    is_fork: bool | None = None
    sequence_regression: bool | None = None
    missing_predecessor: bool | None = None
    unverifiable_scope: bool | None = None


class DomainProof(FrozenModel):
    """One independent per-domain currentness proof result (ADR-002-024 §16; design #23 §2.1/§6.7).

    §16 line 376: independent per-domain proofs **cannot be unioned**. An injected per-domain result
    carrying the domain identity and its :class:`~tos.cur.vocabulary.ProofResult`. Consumed by
    :func:`~tos.cur.predicates.multi_domain_no_union`, which denies the whole request when any domain
    is non-``CURRENT`` (any-restriction-wins, §4.4) — never a union. A ``None`` domain / result fails
    closed.
    """

    domain: str | None = None
    result: ProofResult | None = None


def floor_strictly_advances(predecessor: int | None, advanced: int | None) -> bool:
    """Whether ``advanced`` strictly exceeds ``predecessor`` in append-only order (§3.2/§6.4).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) to check the monotonic restrictive-
    floor advance (§10 line 278 "advances a minimum accepted generation or terminal denial floor" /
    §11) and the parent/child floor order (§16). The two floors are wrapped as ordering coordinates
    (an ordering scalar, **not** a clock — §5.4) and ``True`` **only** when ``predecessor`` provably
    precedes ``advanced`` (``BEFORE``); an equal / ambiguous / regressing pair fails closed. cur owns
    the fence *meaning* (restriction / non-revival); ordering only carries the order. A wall clock
    never orders — cur reads no clock (§0.4e).

    Args:
        predecessor: The predecessor floor ordering scalar (``None`` ⇒ ``False``).
        advanced: The advanced floor ordering scalar (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff ``advanced`` provably strictly exceeds ``predecessor``.
    """
    if predecessor is None or advanced is None:
        return False
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=predecessor),
            OrderingEvent(quorum_commit_index=advanced),
        )
        is Ordering.BEFORE
    )
