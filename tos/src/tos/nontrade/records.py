"""nontrade value models + injected inputs + the two digest-bound artifacts (§2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True,
extra="forbid")`` via :class:`~tos.nontrade._base.FrozenModel`). ``extra="forbid"`` is the
schema-level realization of ADR-002-010 §5 line 117 "A locally generated ID SHALL NOT
erase source identity or make conflicting events identical" and §10 line 219 "History
SHALL be corrected by new versioned facts, not destructive overwrite" — no unknown or
silently-dropped field can smuggle a change past the digest. ``frozen`` is the
record-level realization of the §20 evidence / §19 recovery append-only rule: there is
**no** update / delete / mutate method on any model (design #21 §2/§4.4). Field names use
the ADR §4-§20 terms **verbatim** (spec terms = code terms, boundary design #1 §2.4).

Numeric magnitudes (leg exposure, pre/post quantity and basis, fractional residual,
cash-in-lieu) use the already-core :data:`~tos.canonical.CanonicalDecimal` (design #21
§3.1) so ``1.0`` and ``1.00`` share one artifact digest and a NaN / infinity is
**unconstructable** — never a bare ``Decimal`` / ``float``. Every event-detection,
transition-apply, and reconciliation bound is **injected** (design #21 §8.1; VP-002
``B_non_trade_event_detect`` / ``B_non_trade_transition_apply`` /
``B_non_trade_reconcile`` are all real, ``value_ms: null``, and ``owner: TBD``); a missing
value fails closed at the consuming predicate, and **nothing numeric is hardcoded** — in
particular no split ratio (the "2" of a 2-for-1) appears anywhere.

The two digest-bound citizens (:class:`NonTradeEventRecord` /
:class:`CorrectionReversalRecord`) are each an
:class:`~tos.nontrade._base.IndependentIdArtifact` with an independent, source /
workflow-assigned id (``id != f(digest)``, design #21 §3.1/§0.4f), so **two** forgery axes
stay detectable: a same **primary** id / different-bytes pair is a
``classify_record_pair`` ``CRITICAL_CONFLICT`` (record forgery / contradictory event), and
a same **idempotency key** / different-bytes pair is a ``DIVERGENT_EMISSION`` (two
different corrections claiming one key). Each version is an immutable record; a legitimate
correction (§10 line 219 "a new event linked to the event it supersedes") is a **new
versioned event**, never an in-place mutation (design #21 §2.3).

**No negative-polarity field exists here (design #21 M7 / §0.1(8) honest disclosure).**
There is deliberately no ``favorable_netted``, no ``destructive_overwrite``, and no
``released_on_transformation``: no-netting is proven **structurally** by two coexisting
non-negative magnitudes (design #21 §0.4d), history preservation is the **positive**
``original_retained is True`` premise (§5.3), and capacity release is unrepresentable —
there is no field and no predicate that could express it (§4.2-4; rcl is the sole capacity
authority, §10 line 217). A §7 property asserts those three names stay absent, so a future
edit cannot silently reintroduce a forgeable flag.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.nontrade._base``) only;
**no sibling** ``tos.*`` (sibling edge 0, design #21 §0.3/§0.4b), no ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import field_validator

from tos.canonical import CanonicalDecimal
from tos.nontrade._base import (
    AllFalseNonTradeAuthority,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.nontrade.vocabulary import (
    CredibleTransitionLegKind,
    NonTradeEventClass,
    NonTradeEventWorkflowState,
    SplitTransformationKind,
)

__all__ = [
    "NonTradeAuthorityEffect",
    "TransitionEnvelope",
    "SplitTransformationSpec",
    "NonTradeEventRecord",
    "CorrectionReversalRecord",
]


# ===========================================================================
# All-false non-trade authority effect (§6 line 144 / §4.4)
# ===========================================================================


class NonTradeAuthorityEffect(AllFalseNonTradeAuthority):
    """Authority effect of any non-trade label / record / outcome — every flag false.

    ADR-002-010 §6 line 144 verbatim: "**No workflow state by itself releases capacity,
    closes an instrument, proves final quantity, or grants authority.**" §10 line 217:
    "Only the Risk Capacity Ledger may mutate capacity. The event processor, instrument
    master, projection, reconciliation, or recovery components may propose a remap but
    SHALL NOT update capacity independently." §10 line 221: "neither the event nor a
    favorable projection releases capacity." §15 line 299: "An operator selection, UI
    action, or reference-data flag SHALL NOT itself transmit an instruction." §1 line 15: a
    non-trade event SHALL NOT "be fabricated as fills, silently folded into position
    corrections, or treated as harmless reference-data changes."

    The pure-model realization (the rcl ``RclAuthorityEffect`` / replacement
    ``ReplacementAuthorityEffect`` isomorph). The first four flags are the §6 line 144
    verbatim four; the last four seal the §10 / §15 / §1 prohibitions at type level. Any
    ``True`` value makes the artifact unconstructable. The full "no capacity-mutation /
    broker path anywhere" proof is +Security EV-L2/L3 and is **not** claimed here.
    """

    # --- §6 line 144 verbatim four ---
    releases_capacity: bool = False
    closes_instrument: bool = False
    proves_final_quantity: bool = False
    grants_authority: bool = False
    # --- §10 line 217 / §10 line 221 / §15 line 299 / §1 line 15 ---
    mutates_capacity: bool = False
    issues_admissibility: bool = False
    permits_transmission: bool = False
    fabricates_fill: bool = False


# ===========================================================================
# Value models (plain frozen)
# ===========================================================================


class TransitionEnvelope(FrozenModel):
    """The conservative transition envelope (ADR §9 line 179-198; design #21 §2.1).

    §9 line 181: the envelope contains "all credible economic states during the event";
    line 183: it "SHALL include **where applicable**" the ten
    :class:`~tos.nontrade.vocabulary.CredibleTransitionLegKind` legs; line 196 verbatim:
    "Risk capacity SHALL cover the maximum aggregate risk across the envelope. **Favorable
    effects SHALL NOT be netted against uncertain adverse effects.**"

    ``tos.nontrade`` owns exactly two judgments about this envelope (design #21 §0.4d):

    1. **set completeness** — every *applicable* leg the caller declares required is
       present in :attr:`present_legs`
       (:func:`~tos.nontrade.predicates.transition_envelope_complete`);
    2. **structural no-netting** — :attr:`pre_event_exposure` and
       :attr:`post_event_credible_exposure` coexist as **separate non-negative** values
       (:func:`~tos.nontrade.predicates.favorable_netting_absent`).

    It owns **neither** the dimension-wise union nor the hard-envelope comparison: those
    are rcl-owned (``credible_union_capacity`` ``rcl/predicates.py:739``, whose empty input
    raises ``ValueError`` — the same fail-closed proposition this package realizes as
    ``False``), and the aggregate-risk projection over the credible state space is
    are-owned (``worst_intermediate_risk`` ``are/predicates.py:186``). Both arrive at
    :func:`~tos.nontrade.predicates.nontrade_disposition` as injected coordinates.

    **Why two coexisting magnitudes and not a ``netting_applied`` flag (design #21 §0.4d /
    M7).** Netting offsets the old instrument against the new, which erases or reduces one
    of the two exposures. Requiring both to be present and non-negative therefore proves
    the absence of netting **structurally** — a caller cannot forge it by setting a
    boolean, and an unset magnitude is a ``None`` that fails closed rather than a ``None``
    that an ``is not True`` gate would wave through. Double counting old **and** new is not
    a defect: it is the conservative requirement (§9 line 187 "both old and new instruments
    when identity transition is not final"; §12 line 248 "Both identities remain active in
    the transition envelope until broker and reference-data evidence establish the final
    mapping"). The summation of that double count is rcl's, and the risk projection over it
    is are's.

    **Coverage scope (design #21 §3.4(b) M5 — honest disclosure).** This package enforces
    completeness **within its own leg set** only. Whether the legs declared here cover every
    ``ProjectedCell`` the caller hands to are's ``worst_intermediate_risk`` is **not**
    verified in Phase 1 and is **not** claimed: the binding predicate was considered and
    deliberately **not** authored (it would need the are ``ProjectedCell`` coordinate — the
    edge-1 REUSE rejected in §0.4c — or a weak opaque-id proxy that would prove nothing
    while looking like proof). That residual is deferred to runtime EV-L2/L3 (design #21
    §10.4 G6).
    """

    #: The legs actually present in the envelope. Stored as a **sorted tuple** (not a
    #: ``frozenset``) so a nested serialization is deterministic across processes; use
    #: :meth:`present_leg_set` for the set algebra.
    present_legs: tuple[CredibleTransitionLegKind, ...] = ()
    #: Per-leg magnitude. ``None`` is UNKNOWN, never zero (design #21 §0.4d): an
    #: unenumerated leg is conservatively unknown, never "no risk".
    leg_magnitudes: Mapping[CredibleTransitionLegKind, CanonicalDecimal | None] = {}
    #: The §9 line 185 pre-event exposure. Half of the structural no-netting proof.
    pre_event_exposure: CanonicalDecimal | None = None
    #: The §9 line 186-187 post-event credible exposure. The other half: netting would
    #: have erased or reduced one of the two.
    post_event_credible_exposure: CanonicalDecimal | None = None

    @field_validator("present_legs", mode="after")
    @classmethod
    def _sorted_legs(
        cls, value: tuple[CredibleTransitionLegKind, ...]
    ) -> tuple[CredibleTransitionLegKind, ...]:
        """Normalize the leg tuple to a deduplicated, sorted order (digest determinism).

        A leg *set* has no intrinsic order, so two envelopes declaring the same legs in
        different orders must share one canonical digest. Sorting by the member value keeps
        the serialization deterministic across processes without importing a set type into
        the digest preimage (whose iteration order is hash-seed dependent).

        Args:
            value: The declared leg tuple.

        Returns:
            The deduplicated, value-sorted leg tuple.
        """
        return tuple(sorted(set(value), key=lambda leg: leg.value))

    def present_leg_set(self) -> frozenset[CredibleTransitionLegKind]:
        """Return the present legs as a set for the ``required <= present`` algebra.

        Returns:
            The frozenset of legs present in this envelope.
        """
        return frozenset(self.present_legs)

    def magnitude_of(self, leg: CredibleTransitionLegKind) -> CanonicalDecimal | None:
        """Return the magnitude declared for ``leg`` (``None`` = UNKNOWN, not zero).

        Args:
            leg: The credible transition leg to look up.

        Returns:
            The injected magnitude, or ``None`` when it was never supplied.
        """
        return self.leg_magnitudes.get(leg)


class SplitTransformationSpec(FrozenModel):
    """A split / reverse-split transformation spec (ADR §11 line 225-240; design #21 §2.1).

    §11 line 227 verbatim: "**Every** transformation SHALL specify exact units and rounding
    rules." §11 line 238 verbatim: "Economic equivalence SHALL NOT be assumed from a
    theoretical ratio." §11 line 240: where the transformed state cannot be represented
    exactly, the residual SHALL be explicit and capacity-consuming.

    **Direction is derived, never declared (design #21 §2.2-4 M2).** There is no
    ``quantity_direction`` / ``basis_direction`` field to mis-declare: the polarity is
    computed from :attr:`pre_quantity` / :attr:`post_quantity` and :attr:`pre_basis` /
    :attr:`post_basis` by a multiplicative-identity comparison, then checked against the
    declared :attr:`kind` (design #21 §4.5 truth tables A and B). A caller who labels
    forward magnitudes ``REVERSE_SPLIT`` is rejected; a caller who omits any of the four
    magnitudes cannot derive a direction at all and is rejected. **No ratio is hardcoded**
    — the algebra is three comparisons (``>`` / ``<`` / ``==``), so the "2" of a 2-for-1
    appears nowhere (design #21 §8.0).

    :attr:`kind` is ``None`` for an identity no-op transformation (the truth-table A
    ``(IDENTITY, IDENTITY)`` cell, which has no declared split kind). A ``None`` kind
    paired with non-identity magnitudes is a mis-specification and fails closed.

    The **six** §11 line 231-236 distinctions this package owns, partly owns, and defers
    are transcribed in
    :data:`~tos.nontrade.vocabulary.TRANSFORMATION_DISTINCTION_OWNERSHIP` (no unowned
    distinction): the instrument multiplier and the settlement / collateral / reporting
    currency are venue-owned (``InstrumentRouteFields.multiplier`` / ``.currency``,
    ``venue/records.py:83``) and are consumed as injected coordinates, never re-authored.

    **No ``released_on_transformation`` field exists** (design #21 M7 / §4.2-4): a
    transformation never releases capacity (§10 line 221 / §1 line 28), and that is
    realized by the *absence* of any field or predicate that could express a release — not
    by a forgeable negative-polarity flag.
    """

    #: The declared split kind — the caller's claim, checked against the derived polarity.
    #: ``None`` means "identity no-op" and is coherent **only** with identity magnitudes.
    kind: SplitTransformationKind | None = None
    #: §11 line 231 position quantity before the transformation (polarity derivation input).
    pre_quantity: CanonicalDecimal | None = None
    #: §11 line 231 position quantity after the transformation.
    post_quantity: CanonicalDecimal | None = None
    #: §11 line 234 reference price / cost basis before the transformation.
    pre_basis: CanonicalDecimal | None = None
    #: §11 line 234 reference price / cost basis after the transformation.
    post_basis: CanonicalDecimal | None = None
    #: §11 line 227 exact unit specification — an opaque injected token (the §11 line 231
    #: position-quantity vs executable-order-quantity unit split is declared here).
    #: ``None`` (or an empty token) means the transformation specifies nothing and fails
    #: closed.
    unit_spec: str | None = None
    #: §11 line 227 exact rounding rule — an opaque injected token (§11 line 232 raw ratio
    #: vs broker-applied rounded quantity). ``None`` / empty ⇒ fail closed.
    rounding_rule: str | None = None
    #: §11 line 233/240 fractional entitlement residual — explicit, present, non-negative,
    #: and capacity-consuming; ``None`` hides the residual and fails closed.
    fractional_residual: CanonicalDecimal | None = None
    #: §11 line 233/240 cash-in-lieu residual — same discipline.
    cash_in_lieu: CanonicalDecimal | None = None


# ===========================================================================
# Digest-bound artifacts (IndependentIdArtifact; id != f(digest))
# ===========================================================================


class NonTradeEventRecord(IndependentIdArtifact):
    """An append-only, versioned Non-Trade Event Record (ADR §5 line 99-117; §6).

    §5 line 101 verbatim: "Every event SHALL have a durable **Non-Trade Event ID** and
    contain **at least**:" the **13** identity items of line 103-115 — a *non-closed
    minimum* set (the recon ``SafetyRelevantField`` precedent). Each item's realizing
    field names are transcribed in
    :data:`~tos.nontrade.vocabulary.EVENT_IDENTITY_FIELD_GROUPS`, and a §7 property
    asserts the count is 13 and that every named field exists here — so a truncated
    transcription cannot pass silently (the #16 M4 lesson).

    §1 line 15: a non-trade event is a **first-class versioned economic event** and "SHALL
    NOT be fabricated as fills, silently folded into position corrections, or treated as
    harmless reference-data changes." §5 line 117: "A locally generated ID SHALL NOT erase
    source identity or make conflicting events identical" — hence the independent
    :attr:`event_id` alongside the retained :attr:`source_event_ids` /
    :attr:`source_event_versions`.

    **Two identity axes, two forgery detections (design #21 §2.2-8/§4.6).** The primary
    axis is :attr:`event_id` (item 3): a same-id / different-bytes pair is a
    ``classify_record_pair`` ``CRITICAL_CONFLICT`` (both observations preserved, never
    merged / last-write-wins). The idempotency axis is :attr:`idempotency_key` (item 12): a
    same-key / different-bytes pair is a ``DIVERGENT_EMISSION``. ``id = f(digest)`` would
    have made **both** vacuous, which is why this is an
    :class:`~tos.nontrade._base.IndependentIdArtifact` and not a content-addressed capsule
    artifact (design #21 §0.4f).

    **Orthogonality is structural (§6 line 123).** "Non-trade event state SHALL remain
    orthogonal to order, exposure, capacity, authority, and evidence-confidence state." The
    five axes are therefore **five separate injected fields**
    (:data:`~tos.nontrade.vocabulary.ORTHOGONAL_EVENT_AXES`), each carrying a sibling-owned
    token (orthostate ``BrokerOrderState`` / ``KnowledgeState``, rcl ``CapacityState``,
    authority ``AuthorityState``, recon ``FieldConfidenceClass``) that ``tos.nontrade``
    **consumes and never sets**. :attr:`workflow_state` is a *sixth*, nontrade-owned
    coordinate — the §6 lifecycle label — and it is **non-authoritative**: §6 line 144 "No
    workflow state by itself releases capacity, closes an instrument, proves final
    quantity, or grants authority", sealed at type level by the all-false
    :class:`NonTradeAuthorityEffect`.

    **The seven §5 line 106 times stay seven fields** (§8 line 171 forbids collapsing them
    into one "corporate action date"); each is an opaque **injected** token, because this
    package is clock-free and reads no time source (trustworthy time is ADR-002-008 /
    ``tos.time``, consumed as ``freshness_verdict``).

    ``_REQUIRED_COVERED`` lists **structural identity / classification / version** only
    (design #21 §2.3): the numeric magnitudes and the profile versions are Phase-0 /
    Verification- and Broker-Capability-Profile injected and may stay ``None``, so a record
    stays ISSUED-reachable under null bounds while a missing magnitude fails closed at the
    consuming predicate. :attr:`supersedes_ref` is deliberately **not** required — an
    original observation has no predecessor, and the lineage requirement lives on the
    *correction* (§16 line 311), where :func:`~tos.nontrade.predicates
    .correction_reversal_idempotent` enforces it as ``REJECTED_NO_LINEAGE``.

    The record authorizes nothing by itself (§6 line 144): it carries an all-false
    :class:`NonTradeAuthorityEffect`, and it has no transmit / mutate / remap / commit
    method.
    """

    _ID_FIELD: ClassVar[str] = "event_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "event_class",
        "workflow_generation",
        "idempotency_key",
        "workflow_state",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            # (1) §5 line 103 event class and subtype
            "event_class",
            "event_subtype",
            # (2) §5 line 104 source identities
            "source_identities",
            # (3) §5 line 105 source event identifiers and versions
            "source_event_ids",
            "source_event_versions",
            # (4) §5 line 106 the seven times, kept separate (§8 line 171 no-collapse)
            "announcement_time",
            "observation_time",
            "record_time",
            "ex_time",
            "effective_time",
            "payable_time",
            "settlement_time",
            # (5) §5 line 107 affected scopes
            "affected_account_scopes",
            "affected_portfolio_scopes",
            "affected_instrument_scopes",
            "affected_currency_scopes",
            "affected_broker_scopes",
            # (6) §5 line 108 old and new instrument identities
            "old_instrument_identity",
            "new_instrument_identity",
            # (7) §5 line 109 transformation legs / ratios / rounding + envelope
            "transformation_spec",
            "transition_envelope",
            # (8) §5 line 110 eligibility and election conditions
            "eligibility_conditions",
            "election_conditions",
            # (9) §5 line 111 broker-treatment profile / expected open-order behaviour
            "broker_treatment_profile",
            "expected_open_order_behavior",
            # (10) §5 line 112 per-field evidence confidence (recon tokens, injected)
            "per_field_confidence",
            # (11) §5 line 113 profile / calendar / instrument-master versions
            "safety_profile_version",
            "broker_capability_profile_version",
            "verification_profile_version",
            "calendar_version",
            "instrument_master_version",
            # (12) §5 line 114 workflow generation and idempotency key
            "workflow_generation",
            "idempotency_key",
            # (13) §5 line 115 supersession / correction / reversal / lineage references
            "supersedes_ref",
            "lineage_refs",
            # nontrade-owned lifecycle coordinate (§6 line 127-140)
            "workflow_state",
            # §6 line 123 orthogonal axes kept as separate fields (no-collapse)
            "order_state",
            "exposure_state",
            "capacity_state",
            "authority_state",
            "evidence_confidence_state",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    event_id: str | None = None

    # ---- Layer-1 covered content (ADR §5 line 103-115, 13 items) --------------
    # (1)
    event_class: NonTradeEventClass | None = None
    event_subtype: str | None = None
    # (2)
    source_identities: tuple[str, ...] = ()
    # (3)
    source_event_ids: tuple[str, ...] = ()
    source_event_versions: tuple[str, ...] = ()
    # (4) — seven separate injected time tokens (§8 line 171); this package is clock-free
    announcement_time: str | None = None
    observation_time: str | None = None
    record_time: str | None = None
    ex_time: str | None = None
    effective_time: str | None = None
    payable_time: str | None = None
    settlement_time: str | None = None
    # (5)
    affected_account_scopes: tuple[str, ...] = ()
    affected_portfolio_scopes: tuple[str, ...] = ()
    affected_instrument_scopes: tuple[str, ...] = ()
    affected_currency_scopes: tuple[str, ...] = ()
    affected_broker_scopes: tuple[str, ...] = ()
    # (6)
    old_instrument_identity: str | None = None
    new_instrument_identity: str | None = None
    # (7)
    transformation_spec: SplitTransformationSpec | None = None
    transition_envelope: TransitionEnvelope | None = None
    # (8) — election conditions are held as values only; §15 line 299 forbids this record
    #       (or any operator selection / UI action / reference-data flag) from transmitting
    eligibility_conditions: tuple[str, ...] = ()
    election_conditions: tuple[str, ...] = ()
    # (9) — brokercap coordinates (CORPORATE_ADMINISTRATIVE_EVENTS / OPEN_ORDER_QUERY)
    broker_treatment_profile: str | None = None
    expected_open_order_behavior: str | None = None
    # (10) — recon ``FieldConfidenceClass`` tokens per safety field; recon owns the
    #        classification (``recon/predicates.py:107``), this record only carries it
    per_field_confidence: Mapping[str, str] = {}
    # (11)
    safety_profile_version: str | None = None
    broker_capability_profile_version: str | None = None
    verification_profile_version: str | None = None
    calendar_version: str | None = None
    instrument_master_version: str | None = None
    # (12) — the idempotency identity axis (DIVERGENT_EMISSION target)
    workflow_generation: int | None = None
    idempotency_key: str | None = None
    # (13)
    supersedes_ref: str | None = None
    lineage_refs: tuple[str, ...] = ()

    # ---- nontrade-owned lifecycle coordinate (§6 line 127-140) ----------------
    #: The §6 lifecycle label — a **non-authoritative** coordinate (§6 line 144).
    workflow_state: NonTradeEventWorkflowState | None = None

    # ---- §6 line 123 orthogonal axes (five SEPARATE fields; no-collapse) ------
    #: orthostate ``BrokerOrderState`` token (injected coordinate; never set here).
    order_state: str | None = None
    #: exposure-state token (injected coordinate).
    exposure_state: str | None = None
    #: rcl ``CapacityState`` token (injected coordinate; rcl owns the transitions).
    capacity_state: str | None = None
    #: authority ``AuthorityState`` token (injected coordinate).
    authority_state: str | None = None
    #: recon ``FieldConfidenceClass`` aggregate token (injected coordinate).
    evidence_confidence_state: str | None = None

    # ---- authority (all-false; §6 line 144) -----------------------------------
    authority_effect: NonTradeAuthorityEffect = NonTradeAuthorityEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    event_order: int | None = None


class CorrectionReversalRecord(IndependentIdArtifact):
    """An append-only Correction / Reversal Record (ADR §10 line 219; §16 line 313).

    §10 line 219 verbatim: "History SHALL be corrected by new versioned facts, not
    destructive overwrite. A correction or reversal is a **new event linked to** the event
    it supersedes." §16 line 313: "local history SHALL preserve both the original
    observation and correcting event." §16 line 311: a component "SHALL not relabel an
    unexplained position change as a correction merely to make reconciliation pass" — which
    is why :attr:`supersedes_ref` is the **first** pre-gate of
    :func:`~tos.nontrade.predicates.correction_reversal_idempotent` and its absence is
    ``REJECTED_NO_LINEAGE``. §19 line 366: replay "reapply events only through idempotent
    version checks".

    A digest-bound :class:`~tos.nontrade._base.IndependentIdArtifact` with an independent
    :attr:`correction_id`, so **both** forgery axes stay detectable (design #21 §4.6): a
    same-:attr:`correction_id` / different-bytes pair is a ``CRITICAL_CONFLICT`` (record
    forgery), and a same-:attr:`idempotency_key` / different-bytes pair is a
    ``DIVERGENT_EMISSION`` (two different corrections claiming one key). Both fold to
    :attr:`~tos.nontrade.vocabulary.CorrectionReversalOutcome.REJECTED_CONFLICT` — contain
    both, no last-write-wins merge, and **never** a silent double-apply.

    :attr:`supersedes_ref` is deliberately **not** in ``_REQUIRED_COVERED``: a lineage-less
    correction must stay *constructible* so the ``REJECTED_NO_LINEAGE`` guard is reachable
    and testable on a genuinely issued record. Making it unconstructable would move the
    §16 line 311 rule out of the decision layer and leave the guard vacuous.

    **History preservation is a positive premise, not a negative flag** (design #21 M7 /
    §5.3): there is no ``destructive_overwrite`` field here. The append-only retention of
    the original observation arrives as the caller's positive
    ``original_retained is True`` (design #21 §10.4 G3 discloses that Phase 1 trusts that
    injected flag under **positive** polarity and defers the structural enforcement to the
    ``tos.ordering`` append-only order at runtime).

    The record authorizes nothing by itself: it carries an all-false
    :class:`NonTradeAuthorityEffect` and has no transmit / mutate / recompute method — the
    capacity recomputation from a corrected envelope is rcl's (§16 line 313).
    """

    _ID_FIELD: ClassVar[str] = "correction_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "correction_generation",
        "corrected_event_id",
        "idempotency_key",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            # §10 line 219 — the new versioned fact and what it supersedes
            "correction_generation",
            "correction_kind",
            "corrected_event_id",
            "supersedes_ref",
            "lineage_refs",
            # §16 line 313 — both the original observation and the correcting event
            "original_observation_ref",
            # the idempotency identity axis (§5 line 114; DIVERGENT_EMISSION target)
            "idempotency_key",
            # the economic effect this correction claims + its scope
            "economic_effect_scopes",
            "corrected_transition_envelope",
            # §5 line 113 profile versions
            "safety_profile_version",
            "verification_profile_version",
            # §6 line 123 orthogonal axes kept separate on the correction too
            "capacity_state",
            "evidence_confidence_state",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    correction_id: str | None = None

    # ---- Layer-1 covered content ---------------------------------------------
    correction_generation: int | None = None
    #: An opaque injected token distinguishing a correction from a reversal. It is a
    #: **label, not a permission** (§16 line 311: relabelling proves nothing), so no
    #: predicate branches on it in Phase 1.
    correction_kind: str | None = None
    corrected_event_id: str | None = None
    #: §10 line 219 lineage — the event this correction supersedes. ``None`` ⇒
    #: ``REJECTED_NO_LINEAGE`` (§16 line 311 no-relabel).
    supersedes_ref: str | None = None
    lineage_refs: tuple[str, ...] = ()
    #: §16 line 313 — the retained original observation.
    original_observation_ref: str | None = None
    #: §5 line 114 idempotency key — the second identity axis.
    idempotency_key: str | None = None
    economic_effect_scopes: tuple[str, ...] = ()
    #: The corrected envelope (§16 line 313 "recompute from the corrected envelope" — the
    #: recomputation itself is rcl's; this record only carries the corrected value).
    corrected_transition_envelope: TransitionEnvelope | None = None
    safety_profile_version: str | None = None
    verification_profile_version: str | None = None

    # ---- §6 line 123 orthogonal axes (separate injected coordinates) ---------
    capacity_state: str | None = None
    evidence_confidence_state: str | None = None

    # ---- authority (all-false; §6 line 144) -----------------------------------
    authority_effect: NonTradeAuthorityEffect = NonTradeAuthorityEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    correction_order: int | None = None
