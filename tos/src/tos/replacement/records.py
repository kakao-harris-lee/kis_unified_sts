"""replacement value models + injected inputs + the two digest-bound artifacts (§2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True,
extra="forbid")`` via :class:`~tos.replacement._base.FrozenModel`). ``extra="forbid"`` is
the schema-level realization of ADR-002-011 §7 line 201 "Any material change invalidates
the authorization" and §12 line 302 "SHALL NOT be rounded or clamped in a way that hides
uncovered or reversing quantity" — no unknown or silently-dropped field can smuggle a
change past the digest. ``frozen`` is the record-level realization of the §18 evidence /
§16 durable-recovery append-only rule: there is **no** update / delete / mutate method on
any model (design #18 §2/§4.4). Field names use the ADR §4-§18 terms **verbatim** (spec
terms = code terms, boundary design #1 §2.4).

Numeric magnitudes (gap / overlap duration, exposure, aggregate risk, envelope limits)
use the already-core :data:`~tos.canonical.CanonicalDecimal` (design #18 §3.1) so ``1.0``
and ``1.00`` share one artifact digest and a NaN / infinity is **unconstructable** —
never a bare ``Decimal`` / ``float``. Every gap / overlap / timing / aggregate-risk bound
is **injected** (design #18 §8; ADR §15 line 353 "Numeric values remain unapproved until
human approval and executed evidence are recorded"); a missing value fails closed at the
consuming predicate, and **nothing numeric is hardcoded**.

The two digest-bound citizens (``ReplacementAuthorization`` / ``ReplacementWorkflow
Record``) are each an :class:`~tos.replacement._base.IndependentIdArtifact` with an
independent, governance / workflow-assigned id (``id != f(digest)``, design #18
§3.1/§0.4e) so a same-id / different-bytes forged, re-issued, contradictory, or
double-committed record is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``.
Each generation is an immutable record; a legitimate re-issuance (§7 line 201 material
change ⇒ re-evaluation; §16 recovery ⇒ new authority) is a **new** generation, never an
in-place mutation (design #18 §2.3). Both are **forward-only**: neither carries a future
Capacity Commitment identity (non-cyclic — rcl atomically commits, §9 line 231 / §0.4b).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.replacement._base``)
only; **no sibling** ``tos.*`` (sibling edge 0, design #18 §0.3/§0.4b), no ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from tos.canonical import CanonicalDecimal
from tos.replacement._base import (
    AllFalseReplacementAuthority,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.replacement.vocabulary import (
    CANCEL_FIRST_ADMISSION_CONDITIONS,
    CredibleIntermediateOutcomeKind,
    ReplacementMode,
    ReplacementWorkflowState,
)

__all__ = [
    "ReplacementAuthorityEffect",
    "ProtectionObligation",
    "OverlapReservationClaim",
    "CancelFirstConditions",
    "ReplacementAuthorization",
    "ReplacementWorkflowRecord",
]


# ===========================================================================
# All-false replacement authority effect (§5 line 137 / §4.4)
# ===========================================================================


class ReplacementAuthorityEffect(AllFalseReplacementAuthority):
    """Authority effect of any replacement label / record / outcome — every flag false.

    ADR-002-011 §5 line 137 verbatim: "**No lifecycle label by itself authorizes capacity
    release or removal of protection.**" §5 line 139: "No lifecycle label or 'protective'
    classification proves that cancel, amend, replace, reduce-only, or new protection is
    executable." §9 line 245: "Workflow completion, timeout, authority expiry, cancel
    ACK, or local terminal state is insufficient" to reduce capacity. §1 line 21: "The
    Broker Adapter/Egress Gateway is the final transmission enforcement point."

    The pure-model realization (the rcl ``RclAuthorityEffect`` / afg
    ``ActionFlowGovernorEffect`` isomorph): a replacement decision ``releases_capacity``
    nothing, ``removes_protection`` nothing, ``permits_transmission`` nothing,
    ``issues_authority`` nothing, ``holds_broker_credential`` nothing,
    ``overrides_cancellation_arbiter`` nothing, and ``declares_completion`` nothing. Any
    ``True`` value makes the artifact unconstructable. The full "no capacity-mutation /
    broker path anywhere" proof is +Security EV-L2/L3 and is **not** claimed here.
    """

    releases_capacity: bool = False
    removes_protection: bool = False
    permits_transmission: bool = False
    issues_authority: bool = False
    holds_broker_credential: bool = False
    overrides_cancellation_arbiter: bool = False
    declares_completion: bool = False


# ===========================================================================
# Value models (plain frozen)
# ===========================================================================


class ProtectionObligation(FrozenModel):
    """A versioned protective requirement (ADR §4.1 line 77; design #18 §2.1).

    §4.1 line 77 describes the obligation as a **versioned requirement** carrying the
    scope, side, protected quantity, trigger / price semantics, duration, venue, maximum
    tolerated Protection Gap, maximum tolerated Protection Overlap, ownership, and policy
    identity. It is a plain frozen **value** (not digest-bound): its identity travels as
    the ``obligation_version`` coordinate inside the digest-bound records.

    **Consumers (design #18 §2.1 m8 / Gap-6).** The obligation is the subject of the §12
    ``REMAINING_PROTECTIVE_OBLIGATION`` re-evaluation target — a fill re-evaluates it and
    the runtime issues a **new version** (never an in-place edit) — and its
    ``max_protection_gap`` / ``max_protection_overlap`` are the §15 bound coordinates the
    overlap-first and cancel-first paths quote. Both bound fields are Phase-1 **injected
    and null** (VP-002 ``B_protection_gap`` / ``B_protection_overlap`` are real and
    ``value_ms: null``, design #18 §8.1); a missing bound fails closed at the consuming
    predicate and is never defaulted to a number here.
    """

    obligation_id: str | None = None
    #: The monotone version coordinate; a re-evaluation issues a new version (§12).
    obligation_version: int | None = None
    #: Scope identity (Safety Cell / account / portfolio / strategy / broker /
    #: environment tuple, §7 line 189) carried as an opaque injected token.
    scope_identity: str | None = None
    #: Protected side (a broker-agnostic token; this package names no broker and no venue
    #: dialect — project memory ``tos-spec-broker-agnostic``).
    protected_side: str | None = None
    protected_quantity: CanonicalDecimal | None = None
    #: Trigger / price semantics identity (§4.1); an opaque injected token.
    trigger_or_price_semantics: str | None = None
    duration_basis: str | None = None
    venue_identity: str | None = None
    #: §15 maximum tolerated Protection Gap — injected, Phase-1 null (VP-002:625).
    max_protection_gap: CanonicalDecimal | None = None
    #: §15 maximum tolerated Protection Overlap — injected, Phase-1 null (VP-002:632).
    max_protection_overlap: CanonicalDecimal | None = None
    ownership_identity: str | None = None
    policy_identity: str | None = None


class OverlapReservationClaim(FrozenModel):
    """An overlap-first capacity reservation claim (ADR §9 line 229-248; design #18 §2.1).

    §6.2 line 157: overlap-first "requires capacity for the worst credible simultaneous
    executions and broker resources for both orders" **before** transmission. §9 line
    231: "the Risk Capacity Ledger SHALL atomically commit capacity for the maximum
    aggregate risk over all credible intermediate outcomes"; an outcome not bounded by
    them "is treated conservatively as UNKNOWN".

    ``tos.replacement`` owns exactly two judgments about this claim (design #18 §0.4d):

    1. **set completeness** — every one of the 9 :class:`CredibleIntermediateOutcomeKind`
       members is present in :attr:`reserved_outcome_kinds`;
    2. **structural no-netting** — the old-order-remaining, new-order-remaining, and
       simultaneous-fill magnitudes coexist as **separate non-negative** values.

    It owns **neither** the dimension-wise summation nor the hard-envelope comparison:
    those are rcl-owned (``aggregate_usage`` ``vector.py:103`` / ``effective_limit``
    ``vector.py:139``), and the verdict arrives here as the injected
    :attr:`within_hard_envelope` bool. The aggregate-risk projection over the credible
    state space is are-owned (ADR-002-021) and arrives as injected
    :attr:`aggregate_risk_magnitude`.

    **Why per-outcome magnitudes and not a ``netting_applied`` flag (v1.1 C1/M6,
    prescription (b)).** Netting offsets the old order against the new, which erases or
    reduces one of the two remaining-quantity magnitudes. Requiring the two to coexist
    beside a non-negative simultaneous-fill magnitude therefore proves the absence of
    netting **structurally** — a caller cannot forge it by setting a boolean, and an
    unset magnitude is a ``None`` that fails closed rather than a ``None`` that a
    ``is not True`` gate would wave through (the v1.0 fail-open, removed at the source).
    Double counting old **and** new is not a defect: it is the conservative requirement
    (§20.2 line 443 "Simultaneous fills can over-close or reverse exposure").
    """

    claim_id: str | None = None
    #: The credible intermediate outcomes this reservation covers (§9 line 234-243).
    #: A **subset** of the required 9 is incomplete, never a partial pass.
    reserved_outcome_kinds: frozenset[CredibleIntermediateOutcomeKind] = frozenset()
    #: Per-outcome reserved magnitude. ``None`` is UNKNOWN, never zero (design #18
    #: §0.4d): the structural no-netting derivation requires the three
    #: :data:`~tos.replacement.vocabulary.NO_NETTING_MAGNITUDE_KINDS` entries to be
    #: present **and** non-negative.
    magnitudes: Mapping[CredibleIntermediateOutcomeKind, CanonicalDecimal | None] = {}
    #: The **injected rcl verdict** ``aggregate_usage <= effective_limit`` (positive
    #: polarity: ``is True`` only; ``None`` ⇒ UNKNOWN). ``tos.replacement`` performs no
    #: capacity arithmetic (design #18 §0.2/§0.4c).
    within_hard_envelope: bool | None = None
    #: The **injected are** aggregate-risk projection over the credible state space
    #: (ADR-002-021); ``tos.replacement`` compares, it does not project (§0.2).
    aggregate_risk_magnitude: CanonicalDecimal | None = None
    #: The **injected** hard-envelope limit the projection is compared against.
    hard_envelope_limit: CanonicalDecimal | None = None
    #: Forward-only reference to the rcl commitment coordinate (an opaque token; this
    #: record never carries a *future* commitment identity — §0.4b non-cyclic).
    capacity_commitment_ref: str | None = None

    def magnitude_of(
        self, kind: CredibleIntermediateOutcomeKind
    ) -> CanonicalDecimal | None:
        """Return the reserved magnitude for ``kind`` (``None`` = UNKNOWN, not zero).

        Args:
            kind: The credible intermediate outcome to look up.

        Returns:
            The injected magnitude, or ``None`` when it was never supplied.
        """
        return self.magnitudes.get(kind)


class CancelFirstConditions(FrozenModel):
    """The 8 cancel-first preconditions (ADR §6.3 line 166-174 verbatim; count = 8).

    §6.3 line 165: cancel-first "MAY be authorized **only** when all of the following
    hold"; line 176: "If any condition is unknown, cancel-first replacement is denied."
    Each field is an injected ``bool | None`` where ``None`` is *unknown*, and
    :meth:`positively_proven` returns only the names proven ``True`` — so the gate
    compares a **proven set** against the fixed 8-name universe
    (:data:`~tos.replacement.vocabulary.CANCEL_FIRST_ADMISSION_CONDITIONS`) and an
    all-``None`` (∅-proven) instance can never pass vacuously (design #18 §4.7 row 3).

    ``tos.replacement`` does **not** re-author the sources of these conditions: the
    Cancellation Arbiter verdict is protective-owned (``cancellation_admissible``
    ``predicates.py:523``), broker resource availability is brokercap-owned
    (``rate_admission_ok`` ``predicates.py:437``), and the trustworthy-time basis is
    time-owned (ADR-002-008). They arrive here as injected bools and the gate combines
    them (design #18 §3.5 — an added conjunct, never a re-implemented arbiter).
    """

    #: §6.3 line 167 — no safer proven replacement mode is available.
    no_safer_proven_mode_available: bool | None = None
    #: §6.3 line 168 — the active Safety Profile explicitly permits the mode for the scope.
    safety_profile_permits_mode_for_scope: bool | None = None
    #: §6.3 line 169 — the gap's worst credible exposure is within the aggregate hard
    #: envelope (the rcl / are verdict, injected).
    gap_worst_exposure_within_hard_envelope: bool | None = None
    #: §6.3 line 170 — capacity for unprotected risk, late old-order fills, and the new
    #: order is committed **in advance** (the rcl commit verdict, injected).
    capacity_committed_in_advance: bool | None = None
    #: §6.3 line 171 — an approved maximum gap bound and a containment action exist
    #: (VP-002 ``B_protection_gap`` is real and null in Phase 1, so this is ``None``
    #: until the Bounds-Approver gate — fail-closed, design #18 §8.1).
    approved_max_gap_bound_and_containment_exist: bool | None = None
    #: §6.3 line 172 — broker session / route / rate-limit / order capacity positively
    #: available or conservatively accounted (brokercap, injected).
    broker_resources_available_or_accounted: bool | None = None
    #: §6.3 line 173 — the current time basis is trustworthy (time, injected).
    time_basis_trustworthy: bool | None = None
    #: §6.3 line 174 — the action has current Safety Authority and final egress approval
    #: (authority / liveauth / egress runtime, injected).
    current_authority_and_egress_approval: bool | None = None

    def positively_proven(self) -> frozenset[str]:
        """Return the condition names proven ``True`` (``None`` / ``False`` excluded).

        Positive-polarity normalization: only the singleton ``True`` counts as proven, so
        a truthy non-``bool`` (``1`` / ``"yes"`` / ``[1]``) forged past the annotation is
        **not** proof (design #18 §0.1(j)).

        Returns:
            The frozenset of positively proven condition names.
        """
        return frozenset(
            name
            for name in CANCEL_FIRST_ADMISSION_CONDITIONS
            if getattr(self, name, None) is True
        )


# ===========================================================================
# Digest-bound artifacts (IndependentIdArtifact; id != f(digest))
# ===========================================================================


class ReplacementAuthorization(IndependentIdArtifact):
    """An append-only, generation-immutable Replacement Authorization (ADR §7).

    §7 line 188-199: "Every replacement authorization SHALL bind" **twelve** items
    (count = 12, transcribed in full — design #18 §2.1/§2.3 M4):

    1. the authorization and workflow id;
    2. the scope tuple — Safety Cell, account, portfolio, strategy, broker, environment
       (line 189);
    3. the old and new intent ids plus lineage;
    4. the protective obligation **and current exposure version** (line 191);
    5. the replacement mode;
    6. the maximum tolerated overlap and gap;
    7. the capacity commitment id and its upper bounds;
    8. the broker capability and session profile;
    9. the writer / authority epoch, revocation generation, and egress identity;
    10. the time-health generation;
    11. the artifact / config / Safety-Profile / Verification-Profile version;
    12. the completion, failure, and containment conditions (line 199 — the §15 line 351
        pre-authorized containment digest anchor).

    A digest-bound :class:`~tos.replacement._base.IndependentIdArtifact` with an
    independent ``authorization_id`` (``id != f(digest)``, design #18 §3.1/§0.4e), so a
    same-id / different-bytes forged, re-issued, or **contradictory** authorization is a
    detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` and both sides are
    preserved (no last-write-wins). A legitimate re-issuance after a §7 line 201 material
    change is a **new generation** (fresh id + ``authorization_generation``), never an
    in-place mutation (design #18 §2.3).

    ``_REQUIRED_COVERED`` lists **structural identity / scope / version** only (design
    #18 §2.3): the numeric gap / overlap / capacity bounds are Phase-0 / Verification- and
    Broker-Capability-Profile injected and **null** in Phase 1, so an authorization stays
    ISSUED-reachable under null bounds while a missing magnitude fails closed at the
    consuming predicate. **Forward-only**: no future Capacity Commitment identity is
    covered (non-cyclic; rcl atomically commits — §9 line 231 / §0.4b).

    The record authorizes nothing by itself (§5 line 137): it carries an all-false
    :class:`ReplacementAuthorityEffect`, and it has no transmit / mutate / commit method.
    """

    _ID_FIELD: ClassVar[str] = "authorization_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "authorization_generation",
        "workflow_id",
        "scope_identity",
        "replacement_mode",
        "profile_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            # (1) authorization / workflow id  (the authorization_id itself is Layer-0)
            "authorization_generation",
            "workflow_id",
            # (2) §7 line 189 scope tuple
            "scope_identity",
            "safety_cell_identity",
            "account_identity",
            "portfolio_identity",
            "strategy_identity",
            "broker_identity",
            "environment_identity",
            # (3) old / new intent id + lineage
            "old_intent_id",
            "new_intent_id",
            "intent_lineage",
            # (4) §7 line 191 obligation + current exposure version
            "protection_obligation",
            "current_exposure_version",
            # (5) mode
            "replacement_mode",
            # (6) max overlap / gap
            "max_protection_overlap",
            "max_protection_gap",
            # (7) capacity commitment id + upper bounds
            "capacity_commitment_id",
            "capacity_upper_bounds",
            # (8) broker capability / session profile
            "broker_capability_profile_version",
            "broker_session_profile_ref",
            # (9) writer / authority epoch, revocation generation, egress identity
            "writer_epoch",
            "authority_epoch",
            "revocation_generation",
            "egress_identity",
            # (10) time-health generation
            "time_health_generation",
            # (11) artifact / config / Safety-Profile / Verification-Profile version
            "profile_version",
            "safety_profile_version",
            "verification_profile_version",
            # (12) §7 line 199 completion / failure / containment conditions
            "completion_conditions",
            "failure_conditions",
            "containment_conditions",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    authorization_id: str | None = None

    # ---- Layer-1 covered content (ADR §7 line 188-199, 12 items) --------------
    authorization_generation: int | None = None
    workflow_id: str | None = None

    scope_identity: str | None = None
    safety_cell_identity: str | None = None
    account_identity: str | None = None
    portfolio_identity: str | None = None
    strategy_identity: str | None = None
    broker_identity: str | None = None
    environment_identity: str | None = None

    old_intent_id: str | None = None
    new_intent_id: str | None = None
    intent_lineage: tuple[str, ...] = ()

    protection_obligation: ProtectionObligation | None = None
    current_exposure_version: int | None = None

    replacement_mode: ReplacementMode | None = None

    #: §15 bounds — injected and **null** in Phase 1 (VP-002:625/632); never hardcoded.
    max_protection_overlap: CanonicalDecimal | None = None
    max_protection_gap: CanonicalDecimal | None = None

    capacity_commitment_id: str | None = None
    #: Injected upper-bound magnitudes per capacity coordinate; rcl owns the arithmetic.
    capacity_upper_bounds: tuple[CanonicalDecimal, ...] = ()

    broker_capability_profile_version: str | None = None
    broker_session_profile_ref: str | None = None

    writer_epoch: int | None = None
    authority_epoch: int | None = None
    revocation_generation: int | None = None
    egress_identity: str | None = None

    time_health_generation: int | None = None

    profile_version: str | None = None
    safety_profile_version: str | None = None
    verification_profile_version: str | None = None

    #: §7 line 199 — the pre-authorized completion / failure / containment conditions
    #: whose digest §15 line 351 pins (so a bound excess cannot renegotiate them).
    completion_conditions: tuple[str, ...] = ()
    failure_conditions: tuple[str, ...] = ()
    containment_conditions: tuple[str, ...] = ()

    # ---- authority (all-false; §5 line 137) -----------------------------------
    authority_effect: ReplacementAuthorityEffect = ReplacementAuthorityEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    authorization_order: int | None = None


class ReplacementWorkflowRecord(IndependentIdArtifact):
    """An append-only Replacement Workflow Record (ADR §5 line 105-139; §18).

    §5 line 110-120: the workflow "SHALL retain independently" **ten** items (count = 10):
    the old and new intent ids; the transmission attempt id; the broker order lineage;
    the knowledge confidence; the rcl reservation id; the obligation version; the
    cancellation authorization id; the overlap / gap assessment; the exposure basis; and
    the workflow generation with its owner epoch.

    **Orthogonality is structural (§5 line 107).** The ADR forbids collapsing "order
    state, transmission state, knowledge confidence, capacity state, and protection
    state" into one enum. Those five axes are therefore **five separate injected fields**
    here (:data:`~tos.replacement.vocabulary.ORTHOGONAL_WORKFLOW_AXES`), each carrying a
    sibling-owned token (orthostate ``BrokerOrderState`` / ``TransmissionAttemptState``,
    recon / evidence knowledge confidence, rcl ``CapacityState``) that
    ``tos.replacement`` **consumes and never sets** (design #18 §0.2/§3.5). The
    :attr:`workflow_state` field is a *sixth*, replacement-owned coordinate — the §5
    lifecycle label — and it is **non-authoritative**: §5 line 137 "No lifecycle label by
    itself authorizes capacity release or removal of protection", sealed at type level by
    the all-false :class:`ReplacementAuthorityEffect`.

    A digest-bound :class:`~tos.replacement._base.IndependentIdArtifact` with an
    independent ``record_id`` so a same-id / different-bytes **double-commit** workflow is
    a detectable ``CRITICAL_CONFLICT``. Each generation is immutable; a legitimate
    progression is a new generation, never an in-place edit (design #18 §2.3). It
    supports the §18 line 396-406 evidence reconstruction of a replacement decision; the
    **replay engine itself is ADR-002-016 runtime**, and the §18 line 408 nine required
    metrics are runtime observation (EV-L2/L3), not produced here (design #18 §5.4 G8).
    """

    _ID_FIELD: ClassVar[str] = "record_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "workflow_generation",
        "workflow_id",
        "owner_epoch",
        "workflow_state",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            # (10) workflow generation + owner epoch
            "workflow_generation",
            "workflow_id",
            "owner_epoch",
            # replacement-owned lifecycle coordinate (§5 line 124-135)
            "workflow_state",
            # (1) old / new intent ids
            "old_intent_id",
            "new_intent_id",
            # (2) transmission attempt id
            "transmission_attempt_id",
            # (3) broker order lineage
            "broker_order_lineage",
            # (4) knowledge confidence
            "knowledge_confidence",
            # (5) rcl reservation id
            "rcl_reservation_id",
            # (6) obligation version
            "obligation_version",
            # (7) cancellation authorization id
            "cancellation_authorization_id",
            # (8) overlap / gap assessment
            "overlap_assessment",
            "gap_assessment",
            # (9) exposure basis
            "exposure_basis",
            # §5 line 107 orthogonal axes kept as separate fields (no-collapse)
            "broker_order_state",
            "transmission_attempt_state",
            "capacity_state",
            "protection_state",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    record_id: str | None = None

    # ---- Layer-1 covered content (ADR §5 line 110-120, 10 items) --------------
    workflow_generation: int | None = None
    workflow_id: str | None = None
    owner_epoch: int | None = None

    #: The §5 lifecycle label — a **non-authoritative** coordinate (§5 line 137).
    workflow_state: ReplacementWorkflowState | None = None

    old_intent_id: str | None = None
    new_intent_id: str | None = None
    transmission_attempt_id: str | None = None
    broker_order_lineage: tuple[str, ...] = ()
    rcl_reservation_id: str | None = None
    obligation_version: int | None = None
    cancellation_authorization_id: str | None = None
    #: §15 gap / overlap measurements — injected magnitudes, never computed here.
    overlap_assessment: CanonicalDecimal | None = None
    gap_assessment: CanonicalDecimal | None = None
    exposure_basis: str | None = None

    # ---- §5 line 107 orthogonal axes (five SEPARATE fields; no-collapse) ------
    #: orthostate ``BrokerOrderState`` token (injected coordinate; never set here).
    broker_order_state: str | None = None
    #: orthostate ``TransmissionAttemptState`` token (injected coordinate).
    transmission_attempt_state: str | None = None
    #: recon / evidence knowledge-confidence token (injected coordinate).
    knowledge_confidence: str | None = None
    #: rcl ``CapacityState`` token (injected coordinate; rcl owns the transitions).
    capacity_state: str | None = None
    #: protective protection-state token (injected coordinate).
    protection_state: str | None = None

    # ---- authority (all-false; §5 line 137) -----------------------------------
    authority_effect: ReplacementAuthorityEffect = ReplacementAuthorityEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    record_order: int | None = None
