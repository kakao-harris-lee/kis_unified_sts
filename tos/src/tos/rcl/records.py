"""RCL ledger-citizen records (ADR-002-002 §9/§12/§19/§28; ADR-002-012 §9/§17).

Every record is a digest-bound :class:`~tos.rcl._base.IndependentIdArtifact` with an
independent, service-assigned identity (``id != f(digest)``, §3.1) so an
append-only Safety Commit Log can represent and detect a "duplicate identity with
different content" conflict (ADR-012 §9 line 270; RCLP-INV-006). There is **no**
update / delete / mutate method on any record — lifecycle change is expressed by
appending a new committed command / transition (append-only, §4.2). ``covered`` is
the Layer-1 digest preimage; identity outputs, ``status``, meta, and
ledger-placement fields (``current_reservation_revision`` is owned by the
transition, §2.6) are self-excluded (§3.3). ``_REQUIRED_COVERED`` lists **structural
identity / scope / version / epoch** fields only — numeric bounds are excluded so a
reservation is ISSUED-reachable under Phase-1 null bounds (§2.2); a missing
magnitude fails closed at the consuming predicate instead (§5.3).

Spec terms = code terms (boundary design #1 §2.4).

Pure module: ``pydantic`` + stdlib (``decimal``) + ``tos.rcl`` only; no ``shared.*``,
no ``tos.evidence`` / ``tos.capsule`` (RCL design §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.rcl._base import FrozenModel, IndependentIdArtifact
from tos.rcl.authority import RclAuthorityEffect
from tos.rcl.state import FenceCoordinates
from tos.rcl.vector import CanonicalDecimal, CapacityVector
from tos.rcl.vocabulary import CapacityState, CommandType


class ReservationRecord(IndependentIdArtifact):
    """Reservation / Commitment Record (ADR-002-002 §9 line 473-503).

    ``reservation_id`` is immutable, globally unique, and never reused after
    terminal release (§9 line 475/502) — it is independent of the digest (§3.1).
    The inherited ``canonical_digest`` is this record's canonical record digest.
    ``current_reservation_revision`` is self-excluded from the preimage (it is set by
    the owning transition at ledger placement, §2.6); ``creation_revision`` (part of
    "ledger epoch and creation revision", §9 line 492) is covered.
    """

    _ID_FIELD: ClassVar[str] = "reservation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "parent_intent_id",
        "account_and_portfolio_scope",
        "instrument_and_underlying_scope",
        "action_class",
        "pool_identity",
        "aggregate_risk_authority_grant_identity",
        "evidence_snapshot_identity",
        "hard_safety_envelope_version",
        "runtime_safety_profile_version",
        "ledger_epoch",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "parent_intent_id",
            "account_and_portfolio_scope",
            "instrument_and_underlying_scope",
            "action_class",
            "pool_identity",
            "approved_quantity_upper_bound",
            "adverse_increment_vector",
            "applicable_risk_scopes",
            "aggregate_risk_authority_grant_identity",
            "evidence_snapshot_identity",
            "hard_safety_envelope_version",
            "runtime_safety_profile_version",
            "ledger_epoch",
            "creation_revision",
            "current_capacity_state",
            "bound_attempt_identities",
            "filled_quantity_lower_bound",
            "filled_quantity_upper_bound",
            "remaining_executable_quantity_upper_bound",
            "protective_ownership",
            "trustworthy_time_snapshot_id",
            "audit_causation_identity",
            "audit_actor_identity",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    reservation_id: str | None = None

    # ---- Layer-1 covered content (ADR-002-002 §9 line 479-500) ----
    parent_intent_id: str | None = None
    account_and_portfolio_scope: str | None = None
    instrument_and_underlying_scope: str | None = None
    action_class: str | None = None
    pool_identity: str | None = None
    approved_quantity_upper_bound: CanonicalDecimal | None = None
    adverse_increment_vector: CapacityVector = CapacityVector()
    applicable_risk_scopes: tuple[str, ...] = ()
    aggregate_risk_authority_grant_identity: str | None = None
    evidence_snapshot_identity: str | None = None
    hard_safety_envelope_version: str | None = None
    runtime_safety_profile_version: str | None = None
    ledger_epoch: int | None = None
    creation_revision: int | None = None
    current_capacity_state: CapacityState = CapacityState.COMMITTED_UNBOUND
    bound_attempt_identities: tuple[str, ...] = ()
    filled_quantity_lower_bound: CanonicalDecimal | None = None
    filled_quantity_upper_bound: CanonicalDecimal | None = None
    remaining_executable_quantity_upper_bound: CanonicalDecimal | None = None
    protective_ownership: str | None = None
    trustworthy_time_snapshot_id: str | None = None
    audit_causation_identity: str | None = None
    audit_actor_identity: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.6/§3.3) ----
    current_reservation_revision: int | None = None


class LedgerCommandRecord(IndependentIdArtifact):
    """Ledger Command Record (ADR-002-012 §9 line 253-277; ADR-002-002 §27).

    ``command_identity`` is independent of the ``canonical_digest`` (the command's
    canonical command digest) so a same-identity / different-content command is a
    detectable Critical conflict (§9 line 270). ``fence`` carries the currentness
    coordinates (§9 line 259-260). ``proposed_adverse_increment`` is the Capacity
    Vector a ``CommitReservation`` would commit; ``producer_local_counter`` /
    ``scheduler_priority`` are producer-local metadata that create **no** headroom
    (§11.2 step 10 line 594) — they are covered (part of the command bytes) but the
    reducer never reads them for capacity.
    """

    _ID_FIELD: ClassVar[str] = "command_identity"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "command_type",
        "canonical_schema_version",
        "capacity_domain",
        "cluster_identity",
        "actor_identity",
        "permitted_command_role",
        "requested_transition",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "command_type",
            "canonical_schema_version",
            "capacity_domain",
            "cluster_identity",
            "fence",
            "actor_identity",
            "permitted_command_role",
            "causation_identity",
            "intent_identity",
            "attempt_identity",
            "reservation_identity",
            "evidence_identity",
            "profile_identity",
            "requested_transition",
            "trustworthy_time_snapshot_id",
            "proposed_reservation_id",
            "proposed_adverse_increment",
            "proposed_capacity_state",
            "producer_local_counter",
            "scheduler_priority",
        }
    )

    command_identity: str | None = None

    command_type: CommandType | None = None
    canonical_schema_version: str | None = None
    capacity_domain: str | None = None
    cluster_identity: str | None = None
    fence: FenceCoordinates = FenceCoordinates()
    actor_identity: str | None = None
    permitted_command_role: str | None = None
    causation_identity: str | None = None
    intent_identity: str | None = None
    attempt_identity: str | None = None
    reservation_identity: str | None = None
    evidence_identity: str | None = None
    profile_identity: str | None = None
    requested_transition: str | None = None
    trustworthy_time_snapshot_id: str | None = None
    proposed_reservation_id: str | None = None
    proposed_adverse_increment: CapacityVector = CapacityVector()
    proposed_capacity_state: CapacityState = CapacityState.COMMITTED_UNBOUND
    producer_local_counter: int | None = None
    scheduler_priority: int | None = None


class RclTransitionRecord(IndependentIdArtifact):
    """RCL Transition Record (ADR-002-002 §28 line 1216-1229; ADR-012 §19 line 489).

    An element of the append-only transition sequence. Its ``new_revision`` is the
    ``new_authoritative_revision`` that sets the reservation's current revision
    (§2.6). Emission of this record to the downstream Evidence Store is design #4's
    concern — RCL leaves only a scalar reference.
    """

    _ID_FIELD: ClassVar[str] = "transition_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "new_state",
        "command_identity",
        "actor_identity",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "previous_state",
            "previous_revision",
            "new_state",
            "new_revision",
            "capacity_vector_before",
            "capacity_vector_after",
            "limits_used",
            "hard_safety_envelope_version",
            "runtime_safety_profile_version",
            "authority_epoch",
            "command_identity",
            "actor_identity",
            "causation_identity",
            "correlation_identity",
            "evidence_references",
            "rejection_reason",
            "trustworthy_time_snapshot_id",
        }
    )

    transition_id: str | None = None

    previous_state: CapacityState | None = None
    previous_revision: int | None = None
    new_state: CapacityState | None = None
    new_revision: int | None = None
    capacity_vector_before: CapacityVector = CapacityVector()
    capacity_vector_after: CapacityVector = CapacityVector()
    limits_used: CapacityVector = CapacityVector()
    hard_safety_envelope_version: str | None = None
    runtime_safety_profile_version: str | None = None
    authority_epoch: int | None = None
    command_identity: str | None = None
    actor_identity: str | None = None
    causation_identity: str | None = None
    correlation_identity: str | None = None
    evidence_references: tuple[str, ...] = ()
    rejection_reason: str | None = None
    trustworthy_time_snapshot_id: str | None = None


class TransmissionCapability(IndependentIdArtifact):
    """Transmission Capability — a non-mutating single-use token (ADR-002-002 §12).

    Holding / issuing a capability mutates no capacity (``capacity != authority``,
    §4.1); only a committed ``ClaimCapabilityAndMarkSendStarted`` consumes its
    ``nonce`` exactly once (§6.4; ADR-012 §12). Bound to one reservation + attempt,
    account / instrument / side / max-qty, ledger epoch, live authorization or
    protective lease, and Hard / Runtime versions (§12 line 619-625); §6.4 adds the
    committed ``bound_reservation_revision``, the exact ``worst_case_effect``, and the
    generation ``fence``. ``authority_effect`` is all-false.
    """

    _ID_FIELD: ClassVar[str] = "capability_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "reservation_identity",
        "attempt_identity",
        "account_scope",
        "instrument_scope",
        "side_action_scope",
        "ledger_epoch",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "nonce",
            "single_use",
            "reservation_identity",
            "attempt_identity",
            "account_scope",
            "instrument_scope",
            "side_action_scope",
            "maximum_quantity",
            "ledger_epoch",
            "live_authorization_binding",
            "protective_lease_binding",
            "hard_safety_envelope_version",
            "runtime_safety_profile_version",
            "worst_case_effect",
            "bound_reservation_revision",
            "fence",
            "dominating_restriction",
            "authority_effect",
        }
    )

    capability_id: str | None = None

    nonce: str | None = None
    single_use: bool = True
    reservation_identity: str | None = None
    attempt_identity: str | None = None
    account_scope: str | None = None
    instrument_scope: str | None = None
    side_action_scope: str | None = None
    maximum_quantity: CanonicalDecimal | None = None
    ledger_epoch: int | None = None
    live_authorization_binding: str | None = None
    protective_lease_binding: str | None = None
    hard_safety_envelope_version: str | None = None
    runtime_safety_profile_version: str | None = None
    worst_case_effect: CapacityVector = CapacityVector()
    bound_reservation_revision: int | None = None
    fence: FenceCoordinates = FenceCoordinates()
    dominating_restriction: bool = False
    authority_effect: RclAuthorityEffect = RclAuthorityEffect()


class ProtectivePool(IndependentIdArtifact):
    """Parent Protective Pool (ADR-002-002 §19.1 line 862-874).

    Removed from normal available headroom, represented as a Capacity Vector, not
    borrowable by normal strategy, and visible in aggregate accounting (INV-009).
    """

    _ID_FIELD: ClassVar[str] = "pool_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "pool_scope",
        "owner_epoch",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "capacity_vector",
            "pool_scope",
            "removed_from_normal_headroom",
            "borrowable_by_normal_strategy",
            "visible_in_aggregate_accounting",
            "owner_epoch",
        }
    )

    pool_id: str | None = None

    capacity_vector: CapacityVector = CapacityVector()
    pool_scope: str | None = None
    removed_from_normal_headroom: bool = True
    borrowable_by_normal_strategy: bool = False
    visible_in_aggregate_accounting: bool = True
    owner_epoch: int | None = None


class ProtectiveLease(IndependentIdArtifact):
    """Protective Lease (ADR-002-002 §19.2 line 877-891).

    Bound to one parent pool, owner identity, lease owner epoch, monotonic
    authorization lifetime, Safety Authority epoch, and Hard / Runtime versions. A
    consumed lease never causes capacity release merely because its authorization
    lifetime ended (§12 line 633; §19.4).
    """

    _ID_FIELD: ClassVar[str] = "lease_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "parent_pool_identity",
        "allowed_scope",
        "current_owner_identity",
        "lease_owner_epoch",
        "safety_authority_epoch_binding",
        "hard_safety_envelope_version",
        "runtime_safety_profile_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "parent_pool_identity",
            "capacity_vector",
            "allowed_scope",
            "maximum_quantity",
            "current_owner_identity",
            "lease_owner_epoch",
            "monotonic_authorization_lifetime",
            "safety_authority_epoch_binding",
            "hard_safety_envelope_version",
            "runtime_safety_profile_version",
        }
    )

    lease_id: str | None = None

    parent_pool_identity: str | None = None
    capacity_vector: CapacityVector = CapacityVector()
    allowed_scope: str | None = None
    maximum_quantity: CanonicalDecimal | None = None
    current_owner_identity: str | None = None
    lease_owner_epoch: int | None = None
    monotonic_authorization_lifetime: int | None = None
    safety_authority_epoch_binding: int | None = None
    hard_safety_envelope_version: str | None = None
    runtime_safety_profile_version: str | None = None


class SnapshotCompleteness(FrozenModel):
    """Completeness elements an authoritative snapshot must bind (ADR-012 §17.1/§21).

    Each element is ``None`` when **missing** — the admissibility predicate rejects a
    snapshot missing any of them (RCLP-INV-009; §21 line 528 "Snapshot missing
    idempotency or capability-use state => reject snapshot for authoritative
    restore"). ``_ELEMENTS`` names the required set so
    :func:`tos.rcl.predicates.snapshot_admissible_for_restore` and any construction
    check consume one list.
    """

    _ELEMENTS: ClassVar[tuple[str, ...]] = (
        "non_terminal_reservations",
        "command_idempotency_keys",
        "generation_fences",
        "capability_use_state",
        "proof_gated_release_state",
        "history_commitment",
    )

    non_terminal_reservations: tuple[str, ...] | None = None
    command_idempotency_keys: tuple[str, ...] | None = None
    generation_fences: FenceCoordinates | None = None
    capability_use_state: tuple[str, ...] | None = None
    proof_gated_release_state: tuple[str, ...] | None = None
    history_commitment: str | None = None

    def missing_elements(self) -> tuple[str, ...]:
        """The completeness element names that are missing (``None``)."""
        return tuple(name for name in self._ELEMENTS if getattr(self, name) is None)


class AuthoritativeSnapshot(IndependentIdArtifact):
    """Authoritative Snapshot (ADR-012 §17.1 line 423-433).

    Binds cluster / domain / generation identity, last included revision, the
    :class:`SnapshotCompleteness` set, profile + Hard Envelope generations, and an
    integrity commitment. ``authority_effect`` is all-false — a restored older
    snapshot never becomes authoritative merely because it is the newest backup (§17.4
    line 455); re-arm is out of scope (§5.6).
    """

    _ID_FIELD: ClassVar[str] = "snapshot_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "cluster_identity",
        "capacity_domain",
        "writer_epoch",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "cluster_identity",
            "capacity_domain",
            "membership_generation",
            "restore_generation",
            "writer_epoch",
            "last_included_revision",
            "completeness",
            "profile_generation",
            "hard_safety_envelope_generation",
            "integrity_commitment",
            "authority_effect",
        }
    )

    snapshot_id: str | None = None

    cluster_identity: str | None = None
    capacity_domain: str | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    writer_epoch: int | None = None
    last_included_revision: int | None = None
    completeness: SnapshotCompleteness = SnapshotCompleteness()
    profile_generation: int | None = None
    hard_safety_envelope_generation: int | None = None
    integrity_commitment: str | None = None
    authority_effect: RclAuthorityEffect = RclAuthorityEffect()
