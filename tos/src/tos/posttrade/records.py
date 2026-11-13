"""posttrade value models + injected inputs + the four digest-bound artifacts (§2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True,
extra="forbid")`` via :class:`~tos.posttrade._base.FrozenModel`). ``extra="forbid"`` is the
schema-level realization of ADR-002-030 §11 line 330 "A later correction supersedes the
proof, advances generation ... it does not erase history" and §20 line 460 "SHALL NOT
destructively rewrite" — no unknown or silently-dropped field can smuggle a change past the
digest. ``frozen`` is the record-level realization of the §20 append-only rule: there is
**no** update / delete / mutate method on any model (design #24 §2/§4.4). Field names use
the ADR §9-§20 terms **verbatim** (spec terms = code terms, boundary design #1 §2.4).

Numeric magnitudes (leg magnitude, monetary amount, collateral allocation, quantity,
multiplier, tolerance) use the already-core :data:`~tos.canonical.CanonicalDecimal` (design
#24 §3.1) so ``1.0`` and ``1.00`` share one artifact digest and a NaN / infinity is
**unconstructable** — never a bare ``Decimal`` / ``float``. Every timing, age, and
currentness bound is **injected** (design #24 §8.1: the **19** VP-002 PTF keys — 6 ``B_*``
timing bounds, 5 ``MAX_*`` age bounds, and 8 currentness identity slots — are **all**
``null`` / ``TBD`` with ``owner: TBD``); a missing value fails closed at the consuming
predicate, and **nothing numeric is hardcoded**. The generation coordinate is a plain
``int`` supplied by ``tos.ordering`` (design #24 §3.2), never a wall clock.

The four digest-bound citizens (:class:`EconomicObligationRecord`,
:class:`PostTradeFinalityProof`, :class:`StatementCoverageManifest`,
:class:`PostTradeBreakRecord`) are each an
:class:`~tos.posttrade._base.IndependentIdArtifact` with an independent, source /
ledger-assigned id (``id != f(digest)``, design #24 §3.1/§0.4f), so **two** forgery axes
stay detectable: a same **primary** id / different-bytes pair is a ``classify_record_pair``
``CRITICAL_CONFLICT`` (obligation forgery / a contradictory obligation), and a same
**idempotency key** / different-bytes pair is a ``DIVERGENT_EMISSION`` (two different fills
claiming one commit key). Each version is an immutable record; a legitimate correction (§11
line 330) is a **new versioned record** with an advanced generation, never an in-place
mutation (design #24 §2.3).

**No negative-polarity field exists here (design #24 §0.1(11) / §7 honest disclosure).**
There is deliberately no ``favorable_netted``, no ``destructive_overwrite``, no
``releases_capacity_flag``, no ``can_transmit``, and no ``title_proven_by_ack``: no-netting
is proven **structurally** by two coexisting non-negative gross magnitudes (design #24
§0.4d), collateral conservation by a magnitude sum, history preservation by the **positive**
``original_retained is True`` premise (§5.2), and a capacity release / external send is
*unrepresentable* — there is no field and no predicate that could express it (§4.4/§4.7;
rcl is the sole capacity authority per §1 line 21 / PTF-INV-008, and egress owns
transmission per §1 line 31 / PTF-INV-016). A §7 property asserts those names stay absent,
so a future edit cannot silently reintroduce a forgeable flag. Likewise
:class:`PostTradeFinalityProof` carries **no** ``global_settled_flag`` / ``confidence_score``
/ ``statement_flag`` / ``operator_decision`` field — PTF-INV-005 ("one global ``SETTLED``,
``CLOSED``, confidence score, statement flag, or operator decision cannot replace exact
per-field proof") is realized by the *absence* of any such substitute, not by a rule that
tolerates one.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.posttrade._base``) only;
**no sibling** ``tos.*`` (sibling edge 0, design #24 §0.3/§0.4b), no ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from tos.canonical import CanonicalDecimal
from tos.posttrade._base import (
    AllFalsePostTradeConsequence,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.posttrade.vocabulary import (
    EventObligationLegKind,
    FinalityDimensionKind,
    ObligationLegDirection,
    PostTradeObligationLifecycleState,
)

__all__ = [
    "AllFalsePostTradeConsequence",
    "EconomicObligationRecord",
    "ObligationLeg",
    "ObligationLegScope",
    "PostTradeFinalityProof",
]


# ===========================================================================
# Value models (plain frozen)
# ===========================================================================


class ObligationLegScope(FrozenModel):
    """The exact scope tuple a finality proof binds (ADR §11 line 328; design #24 §2.1 M8).

    §11 line 328 verbatim: a finality proof is "**non-transferable and non-unionable**" —
    the proof of one leg, account, currency, value date, source revision, or finality class
    SHALL NOT be patched onto or reused for another. This value model is that tuple, made
    explicit so :func:`~tos.posttrade.predicates.finality_proof_non_transferable` compares a
    **whole scope** rather than a hand-rolled field-by-field conjunction that a later edit
    could quietly shorten.

    All **six** components are load-bearing and must be concrete for a scope to be usable: a
    scope with an absent component describes a *set* of legs, and a proof over a set is
    exactly the union §11 line 328 forbids. Equality is pydantic structural equality over
    the six fields, so a cross-leg patch attempt differs in at least one component and fails.

    Distinct from :class:`ObligationLeg`, which additionally carries the leg's **direction
    magnitude**: a scope names *which* leg, a leg carries *how much*.
    """

    #: §11 line 328 — the exact leg direction the proof covers.
    leg: ObligationLegDirection | None = None
    #: §11 line 328 — the exact account (or subaccount) scope.
    account: str | None = None
    #: §11 line 328 — the exact settlement currency.
    currency: str | None = None
    #: §11 line 328 — the exact value date (an opaque injected token; clock-free package).
    value_date: str | None = None
    #: §11 line 328 — the exact source revision the proof was taken against.
    source_revision: str | None = None
    #: §11 line 328 — the exact finality class (one of the ten orthogonal dimensions).
    finality_class: FinalityDimensionKind | None = None


class ObligationLeg(FrozenModel):
    """One exact economic leg of an obligation (ADR §5.3 line 116 / §9 line 273).

    §9 line 273 requires the record to carry its "debit, credit, delivery, receipt,
    encumbrance, release, return, and contingent" legs — the eight
    :class:`~tos.posttrade.vocabulary.ObligationLegDirection` members. A leg is a **value**,
    not an artifact: it lives inside :class:`EconomicObligationRecord` and inherits its
    digest binding.

    **Netting is structurally absent (design #24 §0.4d).** There is no ``netted`` /
    ``offset`` / ``net_magnitude`` field. A receivable (``CREDIT``) and a payable
    (``DEBIT``) are two legs standing side by side with two **present, non-negative gross
    magnitudes**; :func:`~tos.posttrade.predicates.netting_requires_positive_proof` accepts a
    netting only when both are present, the scopes match, and an enforceable-netting proof is
    positively injected. Because the offset can only be expressed by *erasing or reducing one
    of the two magnitudes*, the absence of netting is proven by their coexistence — a caller
    cannot forge it with a boolean, and an unset magnitude is a ``None`` that fails closed
    rather than a ``None`` an ``is not True`` gate would wave through.

    :attr:`leg_kind` records **what** the leg is about (§17 line 416's nine event-obligation
    leg kinds) while :attr:`direction` records its **sign**: two orthogonal axes, never
    fused (design #24 §2.2-5b).
    """

    #: §5.3 line 116 leg direction (the sign axis). ``None`` fails closed at every consumer.
    direction: ObligationLegDirection | None = None
    #: The gross magnitude on this direction. ``None`` is UNKNOWN, **never zero** (design
    #: #24 §0.4d / §13 line 355 "A missing line item or zero estimate is not proof of zero").
    magnitude: CanonicalDecimal | None = None
    #: The §11 line 328 scope this leg sits in — the tuple a finality proof must match.
    scope: ObligationLegScope | None = None
    #: §17 line 416 leg kind (the *what* axis), when the leg arises from a lifecycle or
    #: corporate-action event.
    leg_kind: EventObligationLegKind | None = None


# ===========================================================================
# Digest-bound artifacts (IndependentIdArtifact; id != f(digest))
# ===========================================================================


class EconomicObligationRecord(IndependentIdArtifact):
    """An append-only, versioned Economic Obligation Record (ADR §9 line 266-275; §10).

    §9 line 266 verbatim: "Each Economic Obligation Record SHALL contain:" the **8** content
    groups of line 268-275 — a *non-closed minimum* set. Each group's realizing field names
    are transcribed in
    :data:`~tos.posttrade.vocabulary.OBLIGATION_RECORD_FIELD_GROUPS`, and a §7 property
    asserts the count is 8 and that every named field exists here — so a truncated
    transcription cannot pass silently (the #16 M4 lesson).

    §1 line 15: an economic effect is a first-class **exact, immutable, versioned**
    obligation record. §11 line 330: "A later correction supersedes the proof, advances
    generation ... it does not erase history." §20 line 460: a correction "SHALL NOT
    destructively rewrite" — so a correction is a **new record** at the next
    :attr:`obligation_generation`, and the old one stays.

    **Two identity axes, two forgery detections (design #24 §2.2-7/§4.6).** The primary axis
    is :attr:`obligation_id` (group 1): a same-id / different-bytes pair is a
    ``classify_record_pair`` ``CRITICAL_CONFLICT`` (both observations preserved, never merged
    / last-write-wins). The idempotency axis is :attr:`idempotency_key`: a same-key /
    different-bytes pair is a ``DIVERGENT_EMISSION`` (two different fills claiming one commit
    key). ``id = f(digest)`` would have made **both** vacuous, which is why this is an
    :class:`~tos.posttrade._base.IndependentIdArtifact` and not a content-addressed capsule
    artifact (design #24 §0.4f).

    **Orthogonality is structural (§10 line 303-310).** The obligation-lifecycle axis is a
    **sixth** coordinate, "orthogonal to ADR-002-006 Knowledge/Evidence State"; the five
    orthostate-owned axes are therefore **five separate injected fields**
    (:data:`~tos.posttrade.vocabulary.ORTHOGONAL_POST_TRADE_AXES`), each carrying a
    sibling-owned token (orthostate ``BrokerOrderState`` / ``KnowledgeState``, rcl
    ``CapacityState``, authority ``AuthorityState``, recon ``FieldConfidenceClass``) that
    ``tos.posttrade`` **consumes and never sets**. :attr:`lifecycle_state` is the
    posttrade-owned coordinate — and it is **non-authoritative**: §10 line 312 "No lifecycle
    state creates capacity release, available cash, legal title, or permission", sealed at
    type level by the all-false :class:`AllFalsePostTradeConsequence`.

    **The ten §9 line 272 dates stay ten fields.** Collapsing trade / record / ex / due /
    value / settlement / recall / delivery / payable / observation into one "date" is
    precisely the ambiguity the settlement calendar cannot survive; each is an opaque
    **injected** token, because this package is clock-free and reads no time source
    (trustworthy time is ADR-002-008 / ``tos.time``, consumed as ``freshness_verdict``).

    ``_REQUIRED_COVERED`` lists **structural identity / classification / version** only
    (design #24 §2.3): the numeric magnitudes and the profile versions are Phase-0 /
    Verification- and Broker-Capability-Profile injected and may stay ``None``, so a record
    stays ISSUED-reachable under null bounds while a missing magnitude fails closed at the
    consuming predicate. :attr:`supersedes_ref` is deliberately **not** required — an
    original obligation has no predecessor, and the lineage requirement lives on the
    *correction* (§20 line 460), where
    :func:`~tos.posttrade.predicates.obligation_commit_idempotent` enforces it as
    ``REJECTED_NO_LINEAGE``.

    The record authorizes nothing by itself (§10 line 312): it carries an all-false
    :class:`AllFalsePostTradeConsequence`, and it has no release / transfer / transmit /
    commit method.
    """

    _ID_FIELD: ClassVar[str] = "obligation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "obligation_type",
        "obligation_generation",
        "idempotency_key",
        "lifecycle_state",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            # (1) §9 line 268 obligation identity / type / version / generation
            "obligation_type",
            "obligation_version",
            "obligation_generation",
            # (2) §9 line 269 causal source event identities and digests
            "source_event_ids",
            "source_event_digests",
            # (3) §9 line 270 account / entity / venue / settlement-location scopes
            "account_scope",
            "subaccount_scope",
            "legal_entity_scope",
            "beneficial_owner_scope",
            "broker_scope",
            "clearing_member_scope",
            "custodian_scope",
            "bank_scope",
            "venue_scope",
            "settlement_location_scope",
            # (4) §9 line 271 instrument / amount / basis / rounding descriptors
            "instrument_identity",
            "asset_identity",
            "currency",
            "quantity",
            "amount",
            "unit_spec",
            "sign_convention",
            "multiplier",
            "price_basis",
            "fx_basis",
            "rounding_rule",
            "tolerance",
            # (5) §9 line 272 the ten dates, kept separate (no-collapse)
            "trade_date",
            "record_date",
            "ex_date",
            "due_date",
            "value_date",
            "settlement_date",
            "recall_date",
            "delivery_date",
            "payable_date",
            "observation_date",
            # (6) §9 line 273 the eight legs and their magnitudes
            "legs",
            "leg_magnitudes",
            # (7) §9 line 274 source-continuity / statement / correction bindings
            "source_continuity_id",
            "statement_bindings",
            "correction_bindings",
            "per_field_confidence",
            "conservative_bound",
            # (8) §9 line 275 lifecycle / finality / break / supersession / capacity
            "lifecycle_state",
            "finality_proof_refs",
            "break_refs",
            "supersedes_ref",
            "invalidation_refs",
            "capacity_bindings",
            "evidence_bindings",
            # the idempotency identity axis (DIVERGENT_EMISSION target, §4.6)
            "idempotency_key",
            # §10 line 303-310 orthogonal axes kept as separate fields (no-collapse)
            "order_state",
            "knowledge_state",
            "capacity_state",
            "authority_state",
            "evidence_confidence_state",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    obligation_id: str | None = None

    # ---- Layer-1 covered content (ADR §9 line 268-275, 8 groups) --------------
    # (1)
    obligation_type: str | None = None
    obligation_version: str | None = None
    obligation_generation: int | None = None
    # (2)
    source_event_ids: tuple[str, ...] = ()
    source_event_digests: tuple[str, ...] = ()
    # (3) — every scope stays its own field; the ADR names ten distinct parties / places
    account_scope: str | None = None
    subaccount_scope: str | None = None
    legal_entity_scope: str | None = None
    beneficial_owner_scope: str | None = None
    broker_scope: str | None = None
    clearing_member_scope: str | None = None
    custodian_scope: str | None = None
    bank_scope: str | None = None
    venue_scope: str | None = None
    settlement_location_scope: str | None = None
    # (4)
    instrument_identity: str | None = None
    asset_identity: str | None = None
    currency: str | None = None
    quantity: CanonicalDecimal | None = None
    amount: CanonicalDecimal | None = None
    unit_spec: str | None = None
    sign_convention: str | None = None
    multiplier: CanonicalDecimal | None = None
    price_basis: str | None = None
    fx_basis: str | None = None
    rounding_rule: str | None = None
    tolerance: CanonicalDecimal | None = None
    # (5) — ten separate injected date tokens; this package is clock-free
    trade_date: str | None = None
    record_date: str | None = None
    ex_date: str | None = None
    due_date: str | None = None
    value_date: str | None = None
    settlement_date: str | None = None
    recall_date: str | None = None
    delivery_date: str | None = None
    payable_date: str | None = None
    observation_date: str | None = None
    # (6)
    legs: tuple[ObligationLeg, ...] = ()
    #: Per-direction gross magnitude. ``None`` is UNKNOWN, never zero (design #24 §0.4d):
    #: an unenumerated leg is conservatively unknown, never "no obligation".
    leg_magnitudes: Mapping[ObligationLegDirection, CanonicalDecimal | None] = {}
    # (7)
    source_continuity_id: str | None = None
    statement_bindings: tuple[str, ...] = ()
    #: §9 line 274 correction bindings. A record that carries any of these **claims to be a
    #: correction** and therefore owes a :attr:`supersedes_ref` (§20 line 460 no-relabel).
    correction_bindings: tuple[str, ...] = ()
    #: recon ``FieldConfidenceClass`` tokens per safety-relevant field; recon owns the
    #: classification (``recon/predicates.py:107``), this record only carries it.
    per_field_confidence: Mapping[str, str] = {}
    #: The recon ``ConservativeBound`` coordinate (injected token; recon-owned).
    conservative_bound: str | None = None
    # (8)
    #: The posttrade-owned lifecycle coordinate — **non-authoritative** (§10 line 312).
    lifecycle_state: PostTradeObligationLifecycleState | None = None
    finality_proof_refs: tuple[str, ...] = ()
    break_refs: tuple[str, ...] = ()
    #: §20 line 460 lineage — the obligation version this record supersedes. Absent on a
    #: record that claims a correction ⇒ ``REJECTED_NO_LINEAGE``.
    supersedes_ref: str | None = None
    invalidation_refs: tuple[str, ...] = ()
    #: rcl capacity bindings (injected coordinates). rcl performs every transition; this
    #: record only names the binding (§1 line 21 / PTF-INV-008).
    capacity_bindings: tuple[str, ...] = ()
    evidence_bindings: tuple[str, ...] = ()

    # ---- the idempotency identity axis (DIVERGENT_EMISSION target) ------------
    idempotency_key: str | None = None

    # ---- §10 line 303-310 orthogonal axes (five SEPARATE fields; no-collapse) --
    #: orthostate ``BrokerOrderState`` token (injected coordinate; never set here).
    order_state: str | None = None
    #: orthostate ``KnowledgeState`` token (injected coordinate).
    knowledge_state: str | None = None
    #: rcl ``CapacityState`` token (injected coordinate; rcl owns the transitions).
    capacity_state: str | None = None
    #: authority ``AuthorityState`` token (injected coordinate).
    authority_state: str | None = None
    #: recon ``FieldConfidenceClass`` aggregate token (injected coordinate).
    evidence_confidence_state: str | None = None

    # ---- consequence (all-false; §10 line 312) --------------------------------
    consequence: AllFalsePostTradeConsequence = AllFalsePostTradeConsequence()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    obligation_order: int | None = None

    def leg_direction_set(self) -> frozenset[ObligationLegDirection]:
        """Return the declared leg directions as a set for the ``required <= present`` algebra.

        Returns:
            The frozenset of directions present on this record's legs (``None`` directions
            are dropped: an undirected leg proves nothing about coverage).
        """
        return frozenset(
            leg.direction for leg in self.legs if leg.direction is not None
        )


class PostTradeFinalityProof(IndependentIdArtifact):
    """A field-specific post-trade finality proof (ADR §11 line 318-330).

    §11 line 320-326: a finality proof SHALL bind the exact obligation identity, version,
    leg, scope, amount, account, currency, value date, generation, and finality class —
    **and what it does not prove**. §11 line 328 verbatim: it is "**non-transferable and
    non-unionable**". §11 line 330: "A later correction supersedes the proof, advances
    generation ... it does not erase history" — the reopen rule realized by
    :func:`~tos.posttrade.predicates.finality_proof_current`.

    PTF-INV-005 verbatim: "One global ``SETTLED``, ``CLOSED``, confidence score, statement
    flag, or operator decision cannot replace exact per-field proof." That is realized here
    by **structural absence**: this model has no ``global_settled_flag``, no
    ``confidence_score``, no ``statement_flag``, and no ``operator_decision`` field, so a
    global claim has no field to travel in. A proof that lacks the class-specific binding
    simply fails :func:`~tos.posttrade.predicates.finality_proof_class_specific`; there is
    no permissive substitute path to close.

    :attr:`does_not_prove` is **required content**, not documentation: §11 line 320-326 makes
    the negative space part of the proof, and an empty tuple means the proof never declared
    its own limits — which is exactly how a single-dimension proof gets read as global
    finality. The predicate therefore rejects an empty one.

    :attr:`bound_generation` is the Post-Trade Obligation Generation the proof was taken
    against — a plain ``int`` supplied by the ``tos.ordering`` coordinate (design #24 §3.2),
    never a clock. When a correction advances the active generation, this proof's bound
    generation falls behind and the proof stops being current: finality **reopens**
    (PTF-INV-013, §4.5-B row 9).

    A proof grants nothing: it carries an all-false :class:`AllFalsePostTradeConsequence`
    and proves **the leg, not the consequence** (§10 line 312 / §21 line 492).
    """

    _ID_FIELD: ClassVar[str] = "proof_id"
    #: ``obligation_ref`` is deliberately **not** required (the nontrade ``supersedes_ref``
    #: rationale, design #24 §2.3): an unbound proof must stay *constructible* so the
    #: :func:`~tos.posttrade.predicates.finality_proof_class_specific` guard is reachable and
    #: testable on a genuinely ISSUED artifact. Making it unconstructable would move the §11
    #: line 320 rule out of the decision layer and leave the guard vacuous.
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "bound_generation",
        "idempotency_key",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            # §11 line 320 — the exact obligation identity and version
            "obligation_ref",
            "obligation_version",
            # §11 line 328 — the exact scope tuple (leg / account / currency / value date /
            # source revision / finality class)
            "leg_scope",
            # §11 line 320-326 — the exact amount and finality class
            "amount",
            "finality_class",
            # §11 line 330 — the generation this proof binds (the reopen coordinate)
            "bound_generation",
            # §11 line 320-326 — what the proof does NOT prove
            "does_not_prove",
            # the approved proof recipe (Phase-0 approved; ADR §29 Q3) and its source
            "proof_recipe_id",
            "source_revision",
            # the idempotency identity axis
            "idempotency_key",
            # lineage: the proof this one supersedes (§11 line 330 append, never overwrite)
            "supersedes_ref",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    proof_id: str | None = None

    # ---- Layer-1 covered content (ADR §11 line 320-330) -----------------------
    obligation_ref: str | None = None
    obligation_version: str | None = None
    #: The §11 line 328 exact scope tuple this proof binds — and **only** this tuple.
    leg_scope: ObligationLegScope | None = None
    amount: CanonicalDecimal | None = None
    #: The one finality dimension this proof establishes. The other nine stay UNKNOWN.
    finality_class: FinalityDimensionKind | None = None
    #: The Post-Trade Obligation Generation the proof binds (``tos.ordering`` coordinate).
    bound_generation: int | None = None
    #: §11 line 320-326 "what it does not prove" — required, non-empty content.
    does_not_prove: tuple[str, ...] = ()
    #: The Phase-0-approved proof recipe identity (ADR §29 Q3); an injected coordinate.
    proof_recipe_id: str | None = None
    source_revision: str | None = None
    idempotency_key: str | None = None
    supersedes_ref: str | None = None

    # ---- consequence (all-false; §10 line 312 / §21 line 492) -----------------
    consequence: AllFalsePostTradeConsequence = AllFalsePostTradeConsequence()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    proof_order: int | None = None
