"""cur currentness predicates (design #23 §5/§6/§6b) — pure, fail-closed.

Pure decision rules over injected frozen models (design #23 §0.2/§4): cur authors the **complete-
vector aggregation + currentness structural / coordinate substrate** — the yolk
:func:`vector_complete` (every mandated dimension present + positively established + one revision +
policy complete + no placeholder) and its supporting predicates, plus the predicate-only floor /
proof / reconcile / expiry / recovery / all-false substrate. It **re-authors none** of the sibling
instances it aggregates or consumes: venue / iap / capsule own their **per-decision** egress-
currentness leaf (``egress_currentness_active`` / ``active_egress_currentness`` /
``egress_currentness_ok``); egress owns the ``QuorumCommitCertificate`` / ``RestrictiveLatchState`` /
``monotonic_denial_no_revival`` (§0.4c/d); authority owns the epoch floor + non-revival precedent;
time owns freshness (wall-clock age — a **different axis** from currentness, §0.4e); spg owns the
Currentness Policy activation; rcl owns capacity; and 026-030 governance owners are not landed
(injected opaque coordinates, §0.4f). cur **consumes** every produced fact as an **injected scalar /
bool / verdict / digest** and re-authors none of them (sibling edge 0).

**The two boundaries (design #23 §1 — cur's twin maximum risks are opposite).** (1) **over-
realization**: the per-send §13 transaction, the §11 fence commit / deny-first sequence, the §14
claim/fence/first-byte race, the §15 partition / quorum, the latch enforcement, and the §18 wall-
clock age are **all L2+ / runtime / +Security** — L1 owns only present / floor / revision / structure
over injected coordinates. (2) **duplication**: the ~20 dimension owners' *business content* is
**never** re-decided here (§1 line 21 "a currentness sequencer ... does not invent facts, decide
business safety, mutate capacity, issue Live Authorization, classify protection, or transmit"); cur
consumes each owner verdict / generation / digest and judges only the aggregate axis.

**Completeness is the aggregate axis, not a leaf-AND (design #23 §0.4b — the airtight rebuttal).**
An unrepresented dimension (§5.1), a mixed-revision vector (§5.3), and a policy under-declaration
(§5.5) are **each undetectable by any per-decision leaf** (a leaf sees only its own dimension) — they
are the aggregator's own axis (the spg ``bundle_complete`` / hag unrepresented-principal precedent).
:func:`vector_complete` is **not** a conjunction of leaf verdicts.

**Truthy-sentinel discipline (design #23 §4.2).** ``ProofResult`` / ``CurrentnessAdmission`` are
truthy-untestable ``StrEnum``s (``__bool__`` raises), so every gate uses ``x is ENUM.SAFE_VALUE``; a
bare ``if result:`` would fail open reading ``RESTRICTED`` / ``UNKNOWN`` / ``DENY`` as conformance.

**Polarity discipline (design #23 §4.3 — #22 MAJOR-2 seal).** Every ``bool | None`` field declares a
polarity and is normalized with ``is True`` / ``is False`` (never ``if flag:`` / ``if not flag:``): a
``None`` is UNKNOWN and converges to **deny** on both polarities. Positive-polarity fields
(``positively_established`` / ``local_latch_clear``) admit only on ``is True``; negative-polarity
fields (``single_use_consumed`` / ``is_expired`` / ``terminal_denial`` / owner conflict flags) admit
only on ``is False`` (a ``None`` unknown-consumed / unknown-expiry is denial — the #22 MAJOR-2
re-seal: ``is not True`` would admit a ``None``).

**Group reconcile discipline (design #23 §4.4 — #22 MAJOR-1 seal).** A group / scope / dimension
verdict reconciles **all** entries conservatively, never the first: :func:`restrictive_floor_
reconciled` takes the MAX (most restrictive) floor, :func:`multi_domain_no_union` is any-restriction-
wins, and :func:`restrictive_union_scope` unions the credible scopes — all order-independent.

Pure module: ``pydantic`` + stdlib + ``tos.cur.*`` (records / state / vocabulary / _base) +
``tos.ordering`` (via ``tos.cur.state.floor_strictly_advances``) only; no ``shared.*``, no other
sibling ``tos.*`` (design #23 §0.3).
"""

from __future__ import annotations

from collections.abc import Sequence

from tos.cur._base import AllFalseCurrentnessAuthority
from tos.cur.records import (
    CurrentnessPolicy,
    EgressCurrentnessProof,
    RestrictiveFenceRecord,
    SafetyCurrentnessVector,
)
from tos.cur.state import (
    CurrentnessDimension,
    DomainProof,
    OwnerSubmission,
    floor_strictly_advances,
)
from tos.cur.vocabulary import (
    MANDATED_DIMENSION_FLOOR,
    DimensionKey,
    ProofResult,
)

__all__ = [
    # core §5 — vector_complete yolk + supporting (CUR-EV-001 substrate)
    "vector_complete",
    "dimension_positively_established",
    "single_revision_consistent",
    "no_forbidden_placeholder",
    "policy_covers_mandated_dimensions",
    # predicate-only §6 substrate (≥ L2 — closes NO CUR-EV)
    "all_floors_met",
    "restrictive_floor_reconciled",
    "conflicting_owner_restricts",
    "restrictive_union_scope",
    "fence_advances_floor",
    "proof_structurally_complete",
    "proof_admissible",
    "multi_domain_no_union",
    "parent_child_floor_monotone",
    "protective_label_not_authority",
    "expiry_denies_future_use_only",
    "unknown_preserves_capacity",
    "recovery_revives_nothing",
    "all_false_currentness_authority",
    # not-Phase-1 thin model §6b (CUR-EV-005/006 substrate — runtime residue)
    "race_order_admissible",
    "broker_reachable_not_authority",
]

#: Forbidden placeholder sentinels a vector coordinate may never use (§9 line 266 / §5.4). A vector
#: "cannot use ``latest``, wildcards, null-as-current, implicit inheritance, silent fallback, or
#: mixed revisions" — a coordinate bearing any of these is not a concrete committed generation.
_FORBIDDEN_PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "latest",
        "LATEST",
        "*",
        "?",
        "null-as-current",
        "NULL_AS_CURRENT",
        "current",
        "CURRENT",
        "@current",
        "inherit",
        "fallback",
    }
)


# ===========================================================================
# core §5 — the vector_complete yolk + supporting predicates (CUR-EV-001 substrate)
# ===========================================================================


def dimension_positively_established(dimension: CurrentnessDimension | None) -> bool:
    """Whether a vector dimension is present and positively established (§5.2; CUR-EV-001 substrate).

    ``True`` **only** when (i) the dimension exists, (ii) its owner **injected**
    ``positively_established`` verdict is ``is True`` (**positive polarity** — a ``None`` / ``False``
    is not established, the venue ``current_actively_established is not True`` precedent; absence is
    never currentness, §5.4), and (iii) every identity / generation / digest / revision coordinate
    (``dimension_key`` / ``owner_identity`` / ``bound_generation`` / ``bound_digest`` /
    ``at_revision``) is concrete. Any missing coordinate or non-``True`` establishment ⇒ ``False``
    (fail-closed).

    cur re-authors **no** owner business logic: ``positively_established`` is the owner's injected
    verdict (duplication boundary, §1 line 21 / §3.5) — this predicate judges only present + actively
    established, never the owner's decision.

    Args:
        dimension: The vector dimension coordinate (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the dimension is present and positively established.
    """
    if dimension is None:
        return False
    if dimension.positively_established is not True:
        return False
    return not (
        dimension.dimension_key is None
        or dimension.owner_identity is None
        or dimension.bound_generation is None
        or dimension.bound_digest is None
        or dimension.at_revision is None
    )


def single_revision_consistent(vector: SafetyCurrentnessVector | None) -> bool:
    """Whether every dimension sits at the vector's single Currentness Revision (§5.3; CUR-EV-001).

    ``True`` **only** when the vector's ``currentness_revision`` is concrete and **every** dimension's
    ``at_revision`` equals it (pydantic frozen value equality). A ``None`` vector / revision, or any
    dimension at a different / ``None`` revision ⇒ ``False`` (§9 line 266 "cannot use ... mixed
    revisions"). **This is a cross-dimension judgement no per-decision leaf can make** (§0.4b).

    Args:
        vector: The Safety Currentness Vector (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every dimension sits at the one vector revision.
    """
    if vector is None or vector.currentness_revision is None:
        return False
    for dimension in vector.dimensions:
        if (
            dimension.at_revision is None
            or dimension.at_revision != vector.currentness_revision
        ):
            return False
    return True


def no_forbidden_placeholder(vector: SafetyCurrentnessVector | None) -> bool:
    """Whether no dimension uses a forbidden placeholder / wildcard sentinel (§5.4; CUR-EV-001).

    ``True`` **only** when no dimension's ``bound_generation`` / ``bound_digest`` carries a
    :data:`_FORBIDDEN_PLACEHOLDERS` sentinel (§9 line 266 verbatim: "A vector cannot use ``latest``,
    wildcards, null-as-current, implicit inheritance, silent fallback, or mixed revisions"). A
    ``None`` vector ⇒ ``False`` (fail-closed). ``bound_generation`` is an ordering int so it can carry
    no string sentinel — the string check applies to whichever coordinate is a string; a defensive
    both-coordinate scan keeps the seal robust if a coordinate type ever widens.

    Args:
        vector: The Safety Currentness Vector (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no dimension uses a forbidden placeholder sentinel.
    """
    if vector is None:
        return False
    for dimension in vector.dimensions:
        for value in (dimension.bound_digest, dimension.bound_generation):
            if isinstance(value, str) and value in _FORBIDDEN_PLACEHOLDERS:
                return False
    return True


def policy_covers_mandated_dimensions(
    policy: CurrentnessPolicy | None,
    mandated: frozenset[DimensionKey],
) -> bool:
    """Whether the policy declares at least every mandated dimension (§5.5; under-declaration seal).

    ``True`` **only** when (i) the policy exists, (ii) ``mandated`` is **non-empty** (∅-seal — an
    empty mandate is never vacuously satisfied, §8 "Unknown materiality is material"), and (iii)
    ``mandated`` is a subset of ``policy.required_dimensions`` (**set both-ways** — a policy that omits
    even one mandated dimension under-declares and ⇒ ``False``, §8 "a producer, consumer, sequencer,
    operator, or egress cannot omit a dimension because it expects the fact to be unchanged"). The
    policy's **activation** is spg/014-governed (injected, §0.4g) — this checks only *content*
    completeness.

    Args:
        policy: The Currentness Policy (``None`` ⇒ ``False``).
        mandated: The mandated dimension floor (∅ ⇒ ``False``).

    Returns:
        ``True`` iff the policy declares at least every mandated dimension.
    """
    if policy is None:
        return False
    if not mandated:
        return False
    return mandated <= policy.required_dimensions


def vector_complete(
    vector: SafetyCurrentnessVector | None,
    policy: CurrentnessPolicy | None,
    mandated: frozenset[DimensionKey],
) -> bool:
    """The yolk: whether a Safety Currentness Vector is complete (§5.1; CUR-EV-001 substrate — NOT closed).

    ``True`` **only** when **all** of the following hold (AND, fail-closed):

    1. **∅-seal (both-ways)**: ``vector`` and ``policy`` are non-``None``, ``policy.required_
       dimensions`` is non-empty, and ``vector.dimensions`` is non-empty — an absent policy / required
       set / dimension set is **never** vacuously complete (§8 "Unknown materiality is material").
    2. **policy complete (§5.5)**: ``policy.required_dimensions ⊇`` the **effective mandated floor**.
       The ``mandated`` argument is floored to at least :data:`~tos.cur.vocabulary.MANDATED_DIMENSION_
       FLOOR` (every non-conditional ``DimensionKey``, CONTEXT included) — a caller may require *more*
       but **never fewer** (design #23 §5.1 v1.1 MINOR-1); a narrowing attempt is caught here because
       the policy would fail to cover the floor.
    3. **every required dimension present + positively established (§5.2)**: ``policy.required_
       dimensions`` is a subset of the keys of the dimensions that pass
       :func:`dimension_positively_established`. An **unrepresented** required dimension ⇒ incomplete
       (the spg ``bundle_complete`` / hag unrepresented-principal precedent) — **undetectable by any
       leaf** (§0.4b).
    4. **single revision (§5.3)**: every dimension sits at the one ``currentness_revision``.
    5. **no placeholder (§5.4)**: no dimension uses a ``latest`` / wildcard / null-as-current
       sentinel.

    **Completeness is the aggregate axis, not a conjunction of leaf verdicts (§0.4b — the airtight
    rebuttal to "vector_complete = leaf AND").** The unrepresented-dimension (3), mixed-revision (4),
    and policy-under-declaration (2) failures are each invisible to a per-decision leaf. This L1
    substrate **does not close** CUR-EV-001 — that row is ``EV-L1/3`` and awaits ``/3`` integration /
    adversarial evidence (authoring is not acceptance, §1).

    Args:
        vector: The Safety Currentness Vector (``None`` ⇒ ``False``).
        policy: The governing Currentness Policy (``None`` ⇒ ``False``).
        mandated: The caller-supplied mandate, floored to the §9 non-conditional floor.

    Returns:
        ``True`` iff the vector is complete under the floored mandate.
    """
    if vector is None or policy is None:
        return False
    # v1.1 MINOR-1: the mandate is floored to the §9 non-conditional floor — a caller cannot narrow
    # below it (union only widens; a narrower argument is discarded).
    effective_mandated = MANDATED_DIMENSION_FLOOR | frozenset(mandated)
    if not policy.required_dimensions:
        return False
    if not vector.dimensions:
        return False
    if not policy_covers_mandated_dimensions(policy, effective_mandated):
        return False
    established_keys = {
        dimension.dimension_key
        for dimension in vector.dimensions
        if dimension_positively_established(dimension)
    }
    if not policy.required_dimensions <= established_keys:
        return False
    if not single_revision_consistent(vector):
        return False
    return no_forbidden_placeholder(vector)


# ===========================================================================
# predicate-only §6 substrate — floor / proof / reconcile / expiry / recovery (closes NO CUR-EV)
# ===========================================================================


def restrictive_floor_reconciled(floors: Sequence[int | None]) -> int | None:
    """Reconcile many floor entries for one dimension to the MAX (most restrictive) (§6.2; MAJOR-1).

    Returns the **MAX** floor — the most restrictive, order-independently (design #23 §4.4 — the #22
    MAJOR-1 "first-entry" seal: a group verdict reconciles ALL entries conservatively, never the
    first). An **empty** entry set ⇒ ``None`` (∅ ⇒ deny at the consuming predicate), and **any**
    ``None`` entry ⇒ ``None`` (an unknown floor could be higher — fail-closed).

    Args:
        floors: The floor entries for one dimension (∅ / any-``None`` ⇒ ``None``).

    Returns:
        The MAX floor, or ``None`` when empty or any entry is unknown.
    """
    if not floors:
        return None
    if any(floor is None for floor in floors):
        return None
    return max(floor for floor in floors if floor is not None)


def all_floors_met(dimensions: Sequence[CurrentnessDimension]) -> bool:
    """Whether every dimension's bound generation meets its restrictive floor (§6.1; CUR-EV-002).

    ``True`` **only** when the dimension set is non-empty and every dimension has a concrete
    ``bound_generation`` and ``restrictive_floor`` with ``bound_generation >= restrictive_floor``
    (§10 line 278). REUSES the authority ``authority_epoch_current`` ``>=`` floor **shape** (direct
    integer comparison — the equal case is *met*, so ``compare_order``'s strict ``BEFORE`` is
    deliberately **not** used here; §0.4e). Any ``None`` generation / floor ⇒ ``False`` (fail-closed).
    An ∅ dimension set ⇒ ``False`` (no floors proven — §4.7). **The real owner-authentication /
    restriction-ingress is +Security** (§6.1 over-realization boundary).

    Args:
        dimensions: The vector dimensions (∅ ⇒ ``False``).

    Returns:
        ``True`` iff every dimension meets its restrictive floor.
    """
    if not dimensions:
        return False
    for dimension in dimensions:
        if dimension.bound_generation is None or dimension.restrictive_floor is None:
            return False
        if dimension.bound_generation < dimension.restrictive_floor:
            return False
    return True


def conflicting_owner_restricts(submissions: Sequence[OwnerSubmission]) -> bool:
    """Whether any owner submission forces a restrictive closure (§6.3; CUR-EV-002/007 substrate).

    ``True`` (**restrict**) when **any** submission is conflicting / forked / sequence-regressed /
    missing-predecessor / unverifiable-scope — every flag is **negative-polarity** ``is not False``
    (``True`` / ``None`` ⇒ conflicting; a ``None`` unknown conflict is denial, §4.3). This is
    **any-restriction-wins**, reconciling ALL submissions order-independently (design #23 §4.4 — not
    the first owner). An **empty** submission set ⇒ ``False`` (no conflict asserted — the availability
    side; a genuinely conflict-free set does not spuriously restrict). "A restrictive submission
    SHALL NOT be rejected merely because a permissive dependency ... is unavailable" (§10 line 276) —
    the deny-path independence is §6c runtime.

    Args:
        submissions: The owner restriction submissions (∅ ⇒ ``False`` — no conflict).

    Returns:
        ``True`` iff any submission is conflicting (restrict).
    """
    for submission in submissions:
        if (
            submission.is_conflicting is not False
            or submission.is_fork is not False
            or submission.sequence_regression is not False
            or submission.missing_predecessor is not False
            or submission.unverifiable_scope is not False
        ):
            return True
    return False


def restrictive_union_scope(submissions: Sequence[OwnerSubmission]) -> frozenset[str]:
    """The restrictive closure over the UNION of the credible restrictive scopes (§6.3; MAJOR-1).

    Returns the **union** of the ``affected_scope`` of every submission that is restrictive
    (:func:`conflicting_owner_restricts` per-submission) — §10 line 280 "restrictive closure over the
    **union** of credible scopes". Order-independent (union), reconciling ALL restrictive submissions
    conservatively, never the first (design #23 §4.4). A non-restrictive submission contributes
    nothing; an ∅ set ⇒ ∅.

    Args:
        submissions: The owner restriction submissions.

    Returns:
        The union of the affected scopes of the restrictive submissions.
    """
    scope: set[str] = set()
    for submission in submissions:
        if (
            submission.is_conflicting is not False
            or submission.is_fork is not False
            or submission.sequence_regression is not False
            or submission.missing_predecessor is not False
            or submission.unverifiable_scope is not False
        ):
            scope.update(submission.affected_scope)
    return frozenset(scope)


def fence_advances_floor(record: RestrictiveFenceRecord | None) -> bool:
    """Whether a fence monotonically advances its floor or is terminal (§6.4; CUR-EV-002/003 substrate).

    ``True`` **only** when the record's ``advanced_floor`` **strictly exceeds** its
    ``predecessor_floor`` in append-only order (:func:`~tos.cur.state.floor_strictly_advances`,
    REUSING ``tos.ordering``) **or** the fence is a positive ``terminal_denial is True`` (§10 line
    278). A ``None`` record ⇒ ``False``. **The Local Restrictive Latch state machine + deny-first
    sequence is egress-owned (§0.4d) — cur consumes the resolved latch, it does not re-author it; the
    real fence commit is runtime** (§11 line 285-300).

    Args:
        record: The Restrictive Fence Record (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the fence advances its floor or is a terminal denial.
    """
    if record is None:
        return False
    if record.terminal_denial is True:
        return True
    return floor_strictly_advances(record.predecessor_floor, record.advanced_floor)


def proof_structurally_complete(proof: EgressCurrentnessProof | None) -> bool:
    """Whether an Egress Currentness Proof carries a structurally complete §12 claim set (§6.5).

    ``True`` **only** when every §12 required claim is concrete: ``proof_id`` / ``nonce`` /
    ``vector_id`` / ``vector_digest`` / ``committed_revision`` (the ``_REQUIRED_COVERED`` set),
    plus ``bound_generations`` non-empty, ``egress_coordinates`` present, ``capability_claim_command``
    concrete, and ``send_started_revision`` concrete (§12 line 307-313). A ``None`` proof or any
    missing claim ⇒ ``False`` (fail-closed). Re-checks the base ``missing_required_fields`` so a
    ``model_construct`` bypass cannot pass a complete-flag through (defence in depth, §2.3).

    Args:
        proof: The Egress Currentness Proof (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the proof is structurally complete.
    """
    if proof is None:
        return False
    if proof.missing_required_fields():
        return False
    if not proof.bound_generations:
        return False
    if proof.egress_coordinates is None:
        return False
    return not (
        proof.capability_claim_command is None or proof.send_started_revision is None
    )


def proof_admissible(proof: EgressCurrentnessProof | None) -> bool:
    """Whether an Egress Currentness Proof is admissible for one send (§6.6; CUR-EV-004 substrate).

    ``True`` **only** when **all** hold (AND, fail-closed):

    * :func:`proof_structurally_complete` — the §12 claim set is complete;
    * ``proof.result is ProofResult.CURRENT`` — §12 "Only ``CURRENT``" (the truthy-sentinel gate; a
      ``RESTRICTED`` / ``UNKNOWN`` / ``None`` is denial);
    * ``proof.single_use_consumed is False`` — **negative polarity, explicit-False only** (v1.1
      MAJOR-3: ``is not True`` would admit a ``None`` unknown-consumed — the #22 MAJOR-2 re-seal; an
      unconsumed proof must positively prove ``is False``);
    * ``proof.is_expired is False`` — **negative polarity, explicit-False only** (§6.10);
    * ``proof.egress_coordinates.local_latch_clear is True`` — **positive polarity** (§5.7
      "positively established ``CLEAR``"; the egress-owned latch is consumed as an injected ``bool``,
      §0.4d).

    **The real per-send atomic transaction (§13) and wall-clock age (§18) are runtime / +Security**
    (§6.6 over-realization boundary) — this closes **no** CUR-EV.

    Args:
        proof: The Egress Currentness Proof (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the proof is admissible for one send.
    """
    if not proof_structurally_complete(proof):
        return False
    assert proof is not None  # narrowed by proof_structurally_complete
    if proof.result is not ProofResult.CURRENT:
        return False
    if proof.single_use_consumed is not False:
        return False
    if proof.is_expired is not False:
        return False
    return proof.egress_coordinates.local_latch_clear is True


def multi_domain_no_union(domain_proofs: Sequence[DomainProof]) -> bool:
    """Whether independent per-domain proofs are all CURRENT — never unioned (§6.7; CUR-EV-008).

    ``True`` **only** when the domain-proof set is non-empty and **every** domain result is
    ``ProofResult.CURRENT`` — §16 line 376 "Independent per-domain proofs **cannot be unioned**". A
    single non-``CURRENT`` (or ``None`` result / domain) denies the whole request (**any-restriction-
    wins**, order-independent — design #23 §4.4). An ∅ set ⇒ ``False`` (nothing proven). **The real
    cross-domain serializable barrier is runtime** (§6.7).

    Args:
        domain_proofs: The independent per-domain proofs (∅ ⇒ ``False``).

    Returns:
        ``True`` iff every domain is CURRENT (no union).
    """
    if not domain_proofs:
        return False
    for domain_proof in domain_proofs:
        if domain_proof.domain is None:
            return False
        if domain_proof.result is not ProofResult.CURRENT:
            return False
    return True


def parent_child_floor_monotone(
    child_generation: int | None,
    parent_floor: int | None,
) -> bool:
    """Whether a child generation is not stale against a restrictive parent floor (§6.8; CUR-EV-008).

    ``True`` **only** when both are concrete and ``child_generation >= parent_floor`` (§16 line 378
    "prevent a child from appearing current after a restrictive parent floor advances"). A ``None``
    on either side ⇒ ``False`` (fail-closed). Uses the direct ``>=`` floor shape (the equal case is
    met, §0.4e).

    Args:
        child_generation: The child's bound generation (``None`` ⇒ ``False``).
        parent_floor: The restrictive parent floor (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the child generation meets the parent floor.
    """
    if child_generation is None or parent_floor is None:
        return False
    return child_generation >= parent_floor


def protective_label_not_authority(label: str | None = None) -> bool:
    """Whether a protective label can ever confer currentness authority (§6.9; CUR-EV-011 substrate).

    **Unconditionally ``False``** — a rejection predicate. A priority / emergency / close / hedge /
    exit / reduce-only / protective label is **not** authority (§17 line 393): it never establishes
    currentness, meets a floor, or clears a latch. cur consumes the protective lease-exclusivity
    verdict as an **injected** value (protective / rcl / authority own it, §0.4g); a label alone
    proves nothing. Register floor ``EV-L2/3+Broker``.

    Args:
        label: The protective label offered as authority (ignored — the rejection is unconditional;
            accepted for call-site documentation).

    Returns:
        ``False`` — always; a protective label is never currentness authority.
    """
    del label  # the rejection is unconditional (§17 line 393) — a label is never authority
    return False


def expiry_denies_future_use_only(is_expired: bool | None) -> bool:
    """Whether an expired proof denies future use while capacity stays intact (§6.10; CUR-EV-010).

    Returns whether **future use is denied**: ``True`` (deny) when ``is_expired is not False``
    (``True`` / ``None`` — **negative polarity**: a ``None`` unknown-expiry is denial, never a
    fail-open to "not expired", §4.3). Expiry denies **only future use** and **cannot** erase an
    economic fact, release capacity, prove non-acceptance, or prove Final Quantity (CUR-INV-012 line
    187; §18 line 399-406 — every one of cancel / prove-cancellation / prove-non-acceptance /
    establish-Final-Quantity / release-capacity / erase-position / authorize-retry is **forbidden**).
    This predicate reports **only** the future-use denial; it performs no capacity effect (all-false,
    §6.13).

    Args:
        is_expired: The negative-polarity expiry state (``True`` / ``None`` ⇒ deny future use).

    Returns:
        ``True`` iff future use is denied (capacity unchanged).
    """
    return is_expired is not False


def unknown_preserves_capacity(
    currentness_known: bool | None,
    worst_credible_capacity: int | None,
) -> int | None:
    """The worst-credible capacity obligation an UNKNOWN currentness preserves (§6.11; CUR-EV-010).

    When currentness is **not** positively known (``currentness_known is not True`` — ``None`` /
    ``False``), new risk is denied **and** the **worst credible capacity obligation is preserved**
    (CUR-INV-011 line 183 "missing-ACK ≠ non-acceptance · cancel-ACK ≠ Final Quantity", §14 line 350):
    this returns ``worst_credible_capacity`` unchanged (never released, never zeroed). When
    currentness **is** positively known (``is True``), there is no unknown-preservation obligation to
    assert here and it returns ``None``. cur mutates **no** capacity (all-false, §6.13) — it only
    reports the obligation the runtime must preserve.

    Args:
        currentness_known: Whether currentness is positively known (``None`` / ``False`` ⇒ preserve).
        worst_credible_capacity: The worst credible capacity obligation to preserve.

    Returns:
        The preserved worst-credible capacity when currentness is unknown, else ``None``.
    """
    if currentness_known is True:
        return None
    return worst_credible_capacity


def recovery_revives_nothing(
    is_recovery_event: bool | None,
    latch_clear: bool | None,
) -> bool:
    """Whether a recovery event may revive currentness or clear a latch (§6.12; CUR-EV-012 substrate).

    Returns whether the state is **CURRENT after** the event: a restart / reconnect / failover /
    restore / replay / quorum-recovery / time-recovery / health-restoration event
    (``is_recovery_event is True``) **revives nothing** — it forces UNKNOWN + a ``DENY_LATCHED`` latch
    (§19 line 418; CUR-INV-014 line 195 "no automatic re-arm", §11 line 297), so this returns
    ``False``. Absent a recovery event (``is_recovery_event`` ``False`` / ``None``), the pre-existing
    ``latch_clear is True`` (positive polarity) is preserved. Isomorphic to authority
    ``recovery_generation_revives_nothing`` (authored locally, no import — §0.4e). **The real
    hard-fence is +Security** (§6.12).

    Args:
        is_recovery_event: Whether a recovery event occurred (``True`` ⇒ revive nothing).
        latch_clear: The pre-existing latch-clear state (positive polarity).

    Returns:
        ``True`` iff currentness remains CURRENT (only when no recovery event and latch was clear).
    """
    if is_recovery_event is True:
        return False
    return latch_clear is True


def all_false_currentness_authority(
    authority: AllFalseCurrentnessAuthority | None,
) -> bool:
    """Whether an authority block confers nothing — every flag ``False`` (§6.13; CUR-EV-009 substrate).

    ``True`` **only** when the block exists and **every** flag is ``is False`` (approves /
    mutates_capacity / releases_capacity / issues_authority / issues_capability / classifies_
    protection / transmits / clears_halt / re_arms). A ``None`` block, or any non-``False`` flag ⇒
    ``False`` (fail-closed). The construction-time validator already rejects any ``True`` flag; this
    predicate re-derives the all-false property so a ``model_construct`` bypass cannot smuggle a
    permissive block past a consumer (defence in depth, §2.3). CUR-INV-005: a vector / proof / fence /
    policy is verified ordering data, not permission (§1 line 21).

    Args:
        authority: The all-false authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every authority flag is ``False``.
    """
    if authority is None:
        return False
    return all(
        getattr(authority, name) is False for name in type(authority).model_fields
    )


# ===========================================================================
# not-Phase-1 thin model §6b — claim/fence/first-byte race, partition (closes NO CUR-EV; runtime)
# ===========================================================================
# These are thin L1 model properties authored defence-in-depth; they close NO CUR-EV. The real race
# timing / partition healing / quorum consensus is +Security runtime (design #23 §6b/§6c).


def race_order_admissible(
    claim_before_fence: bool | None,
    fence_before_first_byte: bool | None,
) -> bool:
    """Thin race-order model: whether a claim/fence/first-byte order is admissible (§6b; CUR-EV-005).

    A thin ordering property (§14): ``True`` **only** when the capability was claimed **before** any
    restrictive fence (``claim_before_fence is True``) **and** no restrictive fence landed **before**
    the first byte (``fence_before_first_byte is False`` — a fence that precedes the first byte makes
    the send potentially-live and must be denied). Any ``None`` (unknown order) ⇒ ``False`` (a
    potentially-live unknown is denial — no blind retry, §14 line 350). **This closes NO CUR-EV** —
    the real race timing, the ``B_*`` bound propagation, and the no-blind-retry enforcement are
    ``EV-L3+Security`` runtime (§6b / CUR-EV-005 not-Phase-1).

    Args:
        claim_before_fence: Whether the claim provably preceded the fence (``None`` ⇒ ``False``).
        fence_before_first_byte: Whether a fence preceded the first byte (``True`` / ``None`` ⇒
            ``False``).

    Returns:
        ``True`` iff the order is admissible (claim-before-fence and no fence-before-first-byte).
    """
    if claim_before_fence is not True:
        return False
    return fence_before_first_byte is False


def broker_reachable_not_authority(broker_reachable: bool | None = None) -> bool:
    """Whether broker reachability can substitute for authority under partition (§6b; CUR-EV-006).

    **Unconditionally ``False``** — a rejection predicate. §15 line 358: broker reachability does
    **not** imply normal-send authority — under a partition, a reachable broker + an unreachable
    quorum is **not** a licence to send. cur reports that reachability alone never establishes
    currentness authority. **This closes NO CUR-EV** — the real quorum consensus, linearizable
    revision, and partition healing are ``EV-L3+Security`` runtime (§6b / CUR-EV-006 not-Phase-1).

    Args:
        broker_reachable: Whether the broker is reachable (ignored — the rejection is unconditional;
            accepted for call-site documentation).

    Returns:
        ``False`` — always; broker reachability is never currentness authority.
    """
    del broker_reachable  # the rejection is unconditional (§15 line 358) — reachability ≠ authority
    return False
