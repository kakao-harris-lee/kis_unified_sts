"""afg value models + injected inputs + the four digest-bound artifacts (design #16 §2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True,
extra="forbid")`` via :class:`~tos.afg._base.FrozenModel`): ``extra="forbid"`` is the
schema-level realization of ADR-002-022 §8 line 248 "Omitted or unknown fields are
restrictive" and §9 line 254 "governed even when it is believed not to create economic
exposure" (no unknown / silently-dropped field), and frozen is the record-level
realization of append-only immutability (§5.2 generation; §23 evidence) — there is **no**
update / delete / mutate method on any model (design #16 §2.0/§4.6). Field names use the
ADR §5-§22 terms **verbatim** (spec terms = code terms, boundary design #1 §2.4).

Numeric magnitudes (rate / burst / queue / in-flight / amplification magnitude / limit /
headroom) use the already-core :data:`~tos.canonical.CanonicalDecimal` (design #16 §3.1)
so ``1.0`` and ``1.00`` share one artifact digest and a NaN / infinity is
**unconstructable** — never a bare ``Decimal`` / ``float``. Every rate / burst / queue /
age / amplification bound is **injected** (design #16 §8; ADR §4 non-scope line 105); a
missing value fails closed at the consuming predicate, and nothing numeric is hardcoded.

``ActionFlowVector`` **IS** the rcl :class:`~tos.rcl.CapacityVector` type (``vector.py:74``,
ADR-002-002 §6 — the type owner) via the single ``afg -> rcl`` sibling edge (design #16
§0.4c): ADR-002-022 §1 line 19 "The Risk Capacity Ledger is the sole serialization and
mutation authority ... atomically commit the exact risk-capacity vector **and action-flow
vector**", AFG-INV-004 line 169, §30 item 2 line 680. Reusing the type seals coordinate
parity with what rcl commits and lets afg REUSE ``aggregate_usage`` / ``effective_limit``
instead of re-deriving a fail-closed direction (design #16 §0.4c reason 2). rcl does not
import afg, so the edge is acyclic (the #8 orthostate -> rcl / #13 are -> rcl precedent).

The four digest-bound citizens (``ActionFlowPolicy`` / ``ActionFlowStateSnapshot`` /
``ActionFlowDecision`` / ``ActionFlowPermit``) are each an
:class:`~tos.afg._base.IndependentIdArtifact` with an independent, governance /
evaluation / commitment-assigned id (``id != f(digest)``, design #16 §3.1/§0.4e — rcl
``GrantDecisionRef`` already carries ``decision_id`` (``authority.py:53``) and
``canonical_decision_digest`` (``:55``) as **separate** fields, so the consumer already
presumes the orthogonality) so a same-id / different-bytes forged, re-issued,
contradictory, or double-spent record is a detectable ``classify_record_pair``
``CRITICAL_CONFLICT``. Each generation is an immutable record; a legitimate revalidation /
supersession is a **new** generation, never an in-place mutation (design #16 §2.3).
``ActionFlowDecision`` and ``ActionFlowPermit`` are **forward-only**: they carry no future
Capacity Commitment identity (non-cyclic; ADR §29 q2).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.afg._base``) + the rcl
``CapacityVector`` type only; no ``shared.*``, no other sibling ``tos.*`` (design #16 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.afg._base import (
    AllFalseActionFlowAuthority,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.afg.vocabulary import (
    ActionClassKind,
    ActionFlowDimensionKind,
    ActionFlowResult,
    ActionFlowScopeKind,
    MaterialChangeKind,
)
from tos.canonical import CanonicalDecimal
from tos.rcl import CapacityVector

__all__ = [
    "ActionFlowVector",
    "ActionFlowGovernorEffect",
    "ScopeIndependenceEvidence",
    "ActionCause",
    "ActionAmplificationEnvelope",
    "ObservedAmplification",
    "ProtectiveFlowReserveClaim",
    "PermitConsumptionState",
    "CurrentnessTrigger",
    "ActionFlowPolicy",
    "ActionFlowStateSnapshot",
    "ActionFlowDecision",
    "ActionFlowPermit",
]

#: ``ActionFlowVector`` IS the rcl :class:`~tos.rcl.CapacityVector` type (design #16
#: §0.4c / §5.6): the per-(scope, dimension) action-flow resource vector rcl atomically
#: commits beside the economic vector (§1 line 19; AFG-INV-004/005), REUSED so the
#: coordinate is sealed at the **type** level — no self-authored vector, no reduction
#: reducer, no re-derived fail-closed direction. The single ``afg -> rcl`` sibling edge
#: exists only for this alias plus ``aggregate_usage`` / ``effective_limit``.
ActionFlowVector = CapacityVector


# ===========================================================================
# All-false governor authority effect (AFG-INV-011 / §7)
# ===========================================================================


class ActionFlowGovernorEffect(AllFalseActionFlowAuthority):
    """Authority effect of a governor decision / GRANT / permit — every flag false.

    ADR-002-022 §1 line 17 verbatim: "A ``GRANT`` is not capacity or permission to send."
    §5.5 line 129: the permit "is **not** Live Authorization, a Transmission Capability,
    broker permission." §7 line 220: the Governor "SHALL NOT mutate a budget, issue
    authority, or transmit"; §7 line 229: it "SHALL NOT hold a live broker credential,
    signer, session, route, or endpoint capability" (AFG-INV-011). The pure-model
    realization (rcl ``RclAuthorityEffect`` ``authority.py:19-36`` isomorph): the effect
    ``creates_capacity`` nothing, ``mutates_budget`` nothing, ``issues_authority``
    nothing, ``permits_transmission`` nothing, ``holds_broker_credential`` nothing, and
    ``may_rearm`` nothing. Any ``True`` value makes the artifact unconstructable (the full
    "no capacity-mutation / broker path anywhere" proof is +Security EV-L2/L3, AFG-EV-011).
    """

    creates_capacity: bool = False
    mutates_budget: bool = False
    issues_authority: bool = False
    permits_transmission: bool = False
    holds_broker_credential: bool = False
    may_rearm: bool = False


# ===========================================================================
# Value models (plain frozen)
# ===========================================================================


class ScopeIndependenceEvidence(FrozenModel):
    """Per-scope independence evidence (ADR-002-022 §10 line 278).

    §10 line 278 **verbatim**: "Separate processes, nodes, regions, queues, or local
    counters do not establish independent capacity. Independence requires evidence that
    allocation, refill, broker enforcement, **credential/session state**, failure domain,
    and final route are genuinely separate." That is **six** axes, each a field below.

    (The design contract's §5.1 prose transcribed only five, omitting credential/session
    state; the omission was corrected as a design-#16 **v1.2 errata** against this ADR
    line, and the sixth axis is modelled here. Adding an axis can only ever *narrow*
    admission, so the correction is conservative — see the errata note in
    ``docs/plans/2026-07-26-tos-action-flow-budgeting-design.md`` §10.1.)

    Local counters and scheduler priority "create **no** headroom" (the rcl
    ``producer_local_counter`` / ``scheduler_priority`` ``records.py:127-128`` isomorph:
    covered content the reducer never reads for capacity), so a basis resting only on them
    is **not** independence.

    Every field is injected and ``None`` is UNKNOWN, never silently "separated"
    (:meth:`is_independent` requires a positive ``True`` on all six separations).
    """

    scope: ActionFlowScopeKind | None = None
    allocation_separated: bool | None = None
    refill_separated: bool | None = None
    broker_enforcement_separated: bool | None = None
    #: §10 line 278 axis 4 — credential / session state separation.
    credential_session_state_separated: bool | None = None
    failure_domain_separated: bool | None = None
    final_route_separated: bool | None = None
    #: The basis rests only on a producer-local counter (§10 line 278) — never headroom.
    basis_is_local_counter_only: bool | None = None
    #: The basis rests only on scheduler priority (§10 line 278) — never headroom.
    basis_is_scheduler_priority_only: bool | None = None

    #: The six §10 line 278 separation axes, in ADR declaration order. Held as a class
    #: constant so :meth:`is_independent` cannot silently drift out of sync with the ADR
    #: sentence, and so a regression canary can assert the set is complete and non-empty.
    _SEPARATION_AXES: ClassVar[tuple[str, ...]] = (
        "allocation_separated",
        "refill_separated",
        "broker_enforcement_separated",
        "credential_session_state_separated",
        "failure_domain_separated",
        "final_route_separated",
    )

    def is_independent(self) -> bool:
        """Whether this scope is positively evidenced as independent (§10 line 278).

        ``True`` **only** when all **six** ADR separation axes
        (:data:`_SEPARATION_AXES`) are positively ``True`` **and** the basis is positively
        not a local-counter-only / scheduler-priority-only claim (a ``None`` on either
        basis flag is UNKNOWN and fails closed — a component may not assume its counter is
        distributed).

        Returns:
            ``True`` iff independence is positively evidenced on every axis.
        """
        if self.basis_is_local_counter_only is not False:
            return False
        if self.basis_is_scheduler_priority_only is not False:
            return False
        return all(getattr(self, axis) is True for axis in type(self)._SEPARATION_AXES)


class ActionCause(FrozenModel):
    """One action's root cause + complete parent lineage (ADR-002-022 §5.7 line 135-137).

    §11 line 284: every action carries an immutable root-cause identity and a complete
    parent lineage; a missing, cyclic, forked-beyond-bound, or inconsistent lineage is
    ``UNKNOWN`` and contained (§11 line 296). §11 line 294: "A duplicate event does not
    create another allowance. Concurrent consumers of the same cause share one envelope",
    and a **changed** command (quantity / price / route / account / instrument /
    action-class / effect / session / credential / broker identity) is a **new** action
    requiring fresh construction / risk / flow / authority / capability (§27 AFG-AC-002).

    Coordinate-compatible with the rcl ``causation_identity`` (``records.py:151``) /
    ``attempt_identity`` (``:153``) scalars; afg carries the command **identity / digest**
    only — the exact broker-command **bytes** stay ADR-002-020 (IOC) owned, and afg does
    not depend on ioc (design #16 §0.2).

    An **empty** ``parent_lineage`` is UNKNOWN, never "no parents therefore complete"
    (design #16 §4.7).
    """

    root_cause_identity: str | None = None
    #: The ordered ancestor chain (root-first). Empty => UNKNOWN (§4.7), never complete.
    parent_lineage: tuple[str, ...] = ()
    #: Positive attestation that the parent chain is complete (§11 line 284).
    lineage_attested: bool | None = None
    #: Defect witnesses — each must be positively ``False`` (§11 line 296).
    cyclic: bool | None = None
    forked_beyond_bound: bool | None = None
    inconsistent: bool | None = None
    #: Command binding (identity / digest scalars only — no command bytes, §0.2).
    command_identity: str | None = None
    command_digest: str | None = None
    #: The cause this observation duplicates, if any (§11 line 294 — no new allowance).
    duplicate_of_cause_identity: str | None = None


class ActionAmplificationEnvelope(FrozenModel):
    """The finite amplification bound per root cause (§5.8 line 139-141; §11 line 284-292).

    §5.8 line 141 verbatim: "unknown or unbounded amplification is denial." Every axis
    below is an **injected** bound (design #16 §8; the Verification Profile key
    ``MAX_action_amplification_per_cause`` is present-and-null, §8.1) — nothing is
    hardcoded, and an **empty** envelope (any axis left ``None``) means *unbounded* and
    therefore denial, never "no bound needed" (design #16 §4.7).

    The axes are the §11 line 284-292 expansion surfaces: fan-out, depth, attempts,
    mutations, queries, queue depth, in-flight, elapsed monotonic time, and the
    duplicate / redelivery / failover / reconnect / replay expansions.
    """

    max_fan_out: int | None = None
    max_depth: int | None = None
    max_attempts: int | None = None
    max_mutations: int | None = None
    max_queries: int | None = None
    max_queue_depth: int | None = None
    max_in_flight: int | None = None
    max_elapsed_monotonic: CanonicalDecimal | None = None
    max_duplicate_redelivery_expansion: int | None = None
    max_failover_reconnect_replay_expansion: int | None = None
    #: The §11 per-cause amplification ceiling (VP-002 ``MAX_action_amplification_per_cause``).
    max_amplification_per_cause: CanonicalDecimal | None = None

    def declares_every_bound(self) -> bool:
        """Whether every governed amplification axis carries a concrete injected bound.

        ``False`` when **any** axis is ``None`` — an undeclared axis is *unbounded*, and
        "unknown or unbounded amplification is denial" (§5.8 line 141). This is the
        structural realization of the ∅-envelope guard (design #16 §4.7).

        Returns:
            ``True`` iff every amplification axis is bounded.
        """
        return all(getattr(self, name) is not None for name in type(self).model_fields)


class ObservedAmplification(FrozenModel):
    """The observed amplification counts for one root cause (§11 line 284-296).

    The measured counterpart of :class:`ActionAmplificationEnvelope`. Every count is
    injected; a ``None`` count on a governed axis is UNKNOWN and therefore denial (§5.8
    line 141), never assume-zero.

    The three witnesses at the bottom carry the §11 line 294 rules that are not counts:
    a duplicate event must **not** have created another allowance, the envelope must
    **not** have been reset on a duplicate observation, and concurrent consumers of the
    same cause must share **one** envelope.
    """

    fan_out: int | None = None
    depth: int | None = None
    attempts: int | None = None
    mutations: int | None = None
    queries: int | None = None
    queue_depth: int | None = None
    in_flight: int | None = None
    elapsed_monotonic: CanonicalDecimal | None = None
    duplicate_redelivery_expansion: int | None = None
    failover_reconnect_replay_expansion: int | None = None
    amplification_per_cause: CanonicalDecimal | None = None
    #: §11 line 294 — a duplicate event does not create another allowance.
    duplicate_event_created_new_allowance: bool | None = None
    #: §11 line 294 — a duplicate observation cannot reset the envelope.
    envelope_reset_on_duplicate: bool | None = None
    #: §11 line 294 — concurrent consumers of the same cause share one envelope.
    concurrent_consumers_share_one_envelope: bool | None = None


class ProtectiveFlowReserveClaim(FrozenModel):
    """An exclusive protective flow reserve pre-commitment (§5.9 line 143-145; §16).

    AFG-INV-006 line 177: normal traffic may not borrow, consume, or relabel the minimum
    protective reserve, and there is no "repay the reserve later" path (§16 line 370).
    afg does **not** classify the reserve — protective owns ``GuaranteeLevel``
    (``vocabulary.py:32``) and ``is_reserved_guarantee`` (``predicates.py:129``); afg
    consumes the produced ``bool`` / level token by injection (design #16 §3.4/§3.5, M1:
    the level enum is ``GuaranteeLevel``, **not** a ``ReserveGuaranteeLevel``, which does
    not exist).

    §16 line 372: "A high-priority queue without exclusive capacity is ``PRIORITIZED_ONLY``"
    — priority alone is never a reservation.
    """

    #: The governed afg action-flow dimension the reserve applies to (Gap-1 namespace).
    dimension_id: str | None = None
    scope: ActionFlowScopeKind | None = None
    #: The injected reserved magnitude (never hardcoded, design #16 §8).
    reserved_magnitude: CanonicalDecimal | None = None
    #: The injected protective ``GuaranteeLevel`` **token** (afg imports no protective).
    guarantee_level_token: str | None = None
    #: Positive witness that the reserve is exclusive capacity, not a priority queue.
    exclusive_capacity_present: bool | None = None
    #: Whether the claim rests on a high-priority queue (never upgrades a guarantee).
    high_priority_queue: bool | None = None


class PermitConsumptionState(FrozenModel):
    """The observed consumption state of one permit (§13 line 342).

    §13 line 342: a permit is exact, single-use, and either consumed or quarantined;
    releasing an unused permit requires proof it was "never claimed and cannot reach any
    broker path". Each field is injected and ``None`` is UNKNOWN — a permit whose
    consumption state is unknown is **not** consumable and **not** releasable (fail-closed,
    design #16 §4.3/§4.7).
    """

    claimed: bool | None = None
    ambiguous: bool | None = None
    lost: bool | None = None
    conflicting: bool | None = None
    #: The §13 line 342 release premise: never claimed AND unreachable by any broker path.
    never_claimed_and_unreachable_proven: bool | None = None


class CurrentnessTrigger(FrozenModel):
    """One observed change evaluated for materiality (§19 line 413; §5.10 line 149).

    §5.10 line 149 verbatim: "Unknown materiality is material" — so a ``None``
    ``materiality_known`` makes the change material (Gap-7,
    :func:`~tos.afg.state.is_material`). ``kind`` carries a
    :class:`~tos.afg.vocabulary.MaterialChangeKind` token; an unrecognized token with
    unknown materiality is still material.
    """

    kind: MaterialChangeKind | str | None = None
    materiality_known: bool | None = None


# ===========================================================================
# Digest-bound append-only artifacts
# ===========================================================================


class ActionFlowPolicy(IndependentIdArtifact):
    """An append-only, generation-immutable Action Flow Policy (§5.1 line 113; §8).

    §5.1 line 113: an "immutable, authenticated, content-addressed" policy; §8 line 233
    gives the contract fields (canonical digest, signer, approval). A digest-bound
    :class:`~tos.afg._base.IndependentIdArtifact` with an independent ``policy_id``
    (``id != f(digest)``, design #16 §3.1) so a same-id / different-bytes forged or
    re-issued generation is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``;
    a legitimate revalidation is a **new** generation (fresh ``policy_id`` +
    ``policy_generation``), never an in-place mutation (design #16 §2.3).

    The policy is a **member** of the spg Safety Configuration Bundle
    (``ConfigArtifactKind.ACTION_FLOW_POLICY``, ``spg/vocabulary.py:209``); spg owns the
    bundle activation and generation assignment, afg references the coordinate by injected
    scalar and produces **no** spg semantic-validation step (design #16 §3.4(b) — a
    dedicated ``action_flow_effect_within`` step field does **not** exist in spg, and
    inventing one would be a phantom).

    §8 line 248: "Omitted or unknown fields are restrictive", and runtime configuration
    "may narrow ... but cannot enlarge" the Hard Safety Envelope; materiality / scope /
    reserve classification cannot be delegated to a producer. ``_REQUIRED_COVERED`` lists
    **structural identity / generation / version** only (design #16 §2.3); the concrete
    per-broker rate / burst / queue limits are Phase-0 / Broker-Capability-Profile injected
    and excluded, so a policy is ISSUED-reachable under Phase-1 null bounds — a missing
    limit fails closed at the consuming predicate. Non-transmitting, non-enforcing (§4.6).
    """

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_generation",
        "policy_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "policy_version",
            "governed_dimensions",
            "governed_scopes",
            "governed_action_classes",
            "bundle_member_kind",
            "signer_identity",
            "approval_identity",
            "evidence_package_ref",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    policy_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.1 / §8) ------------------------------
    policy_generation: int | None = None
    policy_version: str | None = None
    governed_dimensions: tuple[ActionFlowDimensionKind, ...] = ()
    governed_scopes: tuple[ActionFlowScopeKind, ...] = ()
    governed_action_classes: tuple[ActionClassKind, ...] = ()
    #: The spg bundle-member coordinate token (``ACTION_FLOW_POLICY``), injected.
    bundle_member_kind: str | None = None
    signer_identity: str | None = None
    approval_identity: str | None = None
    evidence_package_ref: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    policy_order: int | None = None


class ActionFlowStateSnapshot(IndependentIdArtifact):
    """An append-only Action Flow State Snapshot (§5.3 line 119-121; §10; §12).

    §5.3 line 119: an "immutable consistency-cut artifact"; line 121: it **grants no
    permission** — a non-authoritative representation, so it carries an all-false
    :class:`ActionFlowGovernorEffect` (AFG-INV-011). A digest-bound
    :class:`~tos.afg._base.IndependentIdArtifact`; the consistency-cut identity is
    orthogonal to the digest (design #16 §3.1). The snapshot is **assembled** by a runtime
    (the §10 broker-global / credential / route aggregation and the §29 q3 consistency-cut
    protocol are EV-L2/L3); afg models it and reads injected fields — it does **not**
    assemble it and reads no clock (design #16 §3.2/§3.5).

    **§12 six-state disposition (Gap-8 / M8).** ADR §12 line 304-309 distinguishes six
    action-flow states; they are carried here as **per-dimension axis vectors** — (1)
    allocations committed but not yet claimed, (2) claims made but no broker byte proven,
    (3) broker-directed writes started, (4) acknowledged / unacknowledged, (5) queued /
    in-flight / throttled / rejected / timed-out / ambiguous, (6) usage reserved
    exclusively for protection. The transmission-attempt detail behind (2)(3)(4) is an
    **injected orthostate coordinate** (``TransmissionAttemptState``), (6) is an injected
    protective ``GuaranteeLevel`` classification, and the state *transitions* stay
    rcl / orthostate runtime — afg sets no capacity or attempt state (design #16 §2.1).

    ``_REQUIRED_COVERED`` lists structural identity / cut only (design #16 §2.3); the
    numeric usage / limit magnitudes are excluded so a snapshot is ISSUED-reachable under
    Phase-1 null bounds — a missing magnitude fails closed at the consuming predicate.
    """

    _ID_FIELD: ClassVar[str] = "snapshot_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "snapshot_generation",
        "consistency_cut_identity",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "snapshot_generation",
            "consistency_cut_identity",
            "covered_scopes",
            "covered_dimension_ids",
            "scope_independence",
            "committed_usage",
            "hard_envelope_limit",
            "runtime_profile_limit",
            "committed_not_claimed",
            "claimed_without_proven_broker_byte",
            "broker_directed_writes_started",
            "acknowledged_or_unacknowledged",
            "queued_in_flight_throttled_rejected_timed_out_ambiguous",
            "reserved_exclusively_for_protection",
            "lineage_ref",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    snapshot_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.3 / §10 / §12) -----------------------
    snapshot_generation: int | None = None
    consistency_cut_identity: str | None = None
    covered_scopes: tuple[ActionFlowScopeKind, ...] = ()
    covered_dimension_ids: tuple[str, ...] = ()
    scope_independence: tuple[ScopeIndependenceEvidence, ...] = ()
    #: Committed action-flow usage (the rcl ``CapacityVector`` type, §0.4c).
    committed_usage: ActionFlowVector = ActionFlowVector()
    hard_envelope_limit: ActionFlowVector = ActionFlowVector()
    runtime_profile_limit: ActionFlowVector = ActionFlowVector()
    # ---- §12 line 304-309 six-state per-dimension axes (Gap-8) ----------------
    committed_not_claimed: ActionFlowVector = ActionFlowVector()
    claimed_without_proven_broker_byte: ActionFlowVector = ActionFlowVector()
    broker_directed_writes_started: ActionFlowVector = ActionFlowVector()
    acknowledged_or_unacknowledged: ActionFlowVector = ActionFlowVector()
    queued_in_flight_throttled_rejected_timed_out_ambiguous: ActionFlowVector = (
        ActionFlowVector()
    )
    reserved_exclusively_for_protection: ActionFlowVector = ActionFlowVector()
    lineage_ref: str | None = None
    #: §5.3 line 121 — the snapshot grants no permission (all-false, AFG-INV-011).
    authority_effect: ActionFlowGovernorEffect = ActionFlowGovernorEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    snapshot_order: int | None = None

    def covers(self, scope: ActionFlowScopeKind) -> bool:
        """Whether ``scope`` is among the snapshot's covered scopes (pure lookup)."""
        return scope in self.covered_scopes

    def independence_for(
        self, scope: ActionFlowScopeKind
    ) -> ScopeIndependenceEvidence | None:
        """The independence evidence for ``scope``, or ``None`` when absent (§10:278).

        A ``None`` return is UNKNOWN — never "independent by default" (design #16 §4.1).
        """
        for evidence in self.scope_independence:
            if evidence.scope is scope:
                return evidence
        return None


class ActionFlowDecision(IndependentIdArtifact):
    """An append-only, forward-only Action Flow Decision (§5.4 line 123-125; §13).

    §5.4 line 123: an "immutable non-authorizing result" carrying ``GRANT`` / ``DENY`` /
    ``UNKNOWN``. **decision_id is orthogonal to the canonical decision digest** — rcl
    ``GrantDecisionRef`` carries ``decision_id`` (``authority.py:53``) and
    ``canonical_decision_digest`` (``:55``) as **separate** fields and names the slot an
    "Aggregate Risk / **Action Flow** decision reference" (``:40``), so the consumer
    already presumes ``id != f(digest)`` (design #16 §3.1). A same-id / different-bytes
    contradictory or re-issued decision is therefore a detectable ``classify_record_pair``
    ``CRITICAL_CONFLICT``; two decisions can never be unioned, patched, widened,
    transplanted, or replayed (AFG-INV-003 line 165).

    **Forward-only** (design #16 §2.3/§5.3): it carries **no** reservation / permit /
    commitment coordinate — rcl charges ``bound_reservation_*`` post-commit
    (``authority.py:56-58``), which is what keeps the pipeline non-cyclic (ADR §29 q2
    explicitly requires the atomic economic + flow commit to avoid a cyclic dependency
    with Order Conformance Proof / Transmission Capability issuance). The
    ``authority_effect`` is all-false (a GRANT is not capacity, AFG-INV-011).

    The ``action_flow_vector`` is the rcl :class:`~tos.rcl.CapacityVector` type
    (type-level coordinate parity, design #16 §0.4c). ``_REQUIRED_COVERED`` requires the
    generation + a concrete result; numeric vectors / limits are excluded so a DENY /
    UNKNOWN decision is ISSUED-reachable under Phase-1 null bounds.
    """

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "decision_generation",
        "result",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "decision_generation",
            "result",
            "policy_digest",
            "policy_generation",
            "snapshot_digest",
            "cause_digest",
            "lineage_digest",
            "command_identity",
            "command_digest",
            "action_class",
            "applicable_action_flow_scopes",
            "action_flow_vector",
            "effective_limit",
            "amplification_envelope_digest",
            "protective_classification_digest",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    decision_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.4 / §13) -----------------------------
    decision_generation: int | None = None
    result: ActionFlowResult | None = None
    policy_digest: str | None = None
    policy_generation: int | None = None
    snapshot_digest: str | None = None
    cause_digest: str | None = None
    lineage_digest: str | None = None
    #: Command **identity / digest** scalars only — the exact broker-command bytes stay
    #: ADR-002-020 (IOC) owned and afg does not depend on ioc (design #16 §0.2).
    command_identity: str | None = None
    command_digest: str | None = None
    action_class: ActionClassKind | None = None
    applicable_action_flow_scopes: tuple[str, ...] = ()
    action_flow_vector: ActionFlowVector = ActionFlowVector()
    effective_limit: ActionFlowVector = ActionFlowVector()
    amplification_envelope_digest: str | None = None
    #: The protective classification digest scalar (protective owns the classification).
    protective_classification_digest: str | None = None
    authority_effect: ActionFlowGovernorEffect = ActionFlowGovernorEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    decision_order: int | None = None


class ActionFlowPermit(IndependentIdArtifact):
    """An append-only, single-use Action Flow Permit (§5.5 line 127-129; §13 line 332-342).

    §5.5 line 127: an "immutable, exact, single-use RCL commitment record". §5.5 line 129:
    it is **not** Live Authorization, a Transmission Capability, or broker permission —
    it is a mandatory *precondition*, not transmission authority (§1 line 19), so the
    ``authority_effect`` is all-false (AFG-INV-011) and afg exposes **no** consume /
    claim / transmit method (design #16 §4.6).

    **Schema ownership vs production ownership (design #16 §0.4d).** ADR §1 line 19 says
    the RCL *produces* the permit instance at runtime, but the permit **schema** is defined
    by ADR-002-022 (§5.5 / §13 line 332-340), and rcl has no ``ActionFlowPermit``
    (grep-measured: rcl owns ``TransmissionCapability`` ``records.py:249`` and
    ``CommittedReservation``, and §5.5 line 129 says a permit is **not** a Transmission
    Capability). So the schema is authored afg-local — isomorphic to are owning the
    ``AggregateRiskDecision`` schema that rcl consumes. The single-use invariant follows
    the rcl ``TransmissionCapability`` ``nonce`` / ``single_use`` pattern
    (``records.py:295-296``); the **consume / quarantine atomic transition** is rcl /
    egress runtime (EV-L2/L3, deferred).

    The covered content is §13 line 332-340 verbatim: permit / RCL-commitment /
    writer-epoch / revision / command identity, the policy / generation / snapshot /
    decision / cause / lineage digests, the resource vector, the ordinary-or-protective
    dimension mark, the protective-lease / reserve proof, the consumer / claim-nonce /
    single-use / issue-anchor / max-age / invalidation-generation, and the
    economic-capacity commitment reference. ``_REQUIRED_COVERED`` lists **structural
    identity** only (design #16 §2.3) so a permit stays ISSUED-reachable under Phase-1
    null bounds (``MAX_action_flow_permit_age_ms`` is present-and-null in VP-002, §8.1).
    """

    _ID_FIELD: ClassVar[str] = "permit_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "permit_generation",
        "command_identity",
        "claim_nonce",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "permit_generation",
            "rcl_commitment_ref",
            "writer_epoch",
            "revision",
            "command_identity",
            "policy_digest",
            "policy_generation",
            "snapshot_digest",
            "decision_digest",
            "cause_digest",
            "lineage_digest",
            "resource_vector",
            "ordinary_or_protective_dimension_mark",
            "protective_lease_proof",
            "reserve_proof",
            "consumer_identity",
            "claim_nonce",
            "single_use",
            "issue_anchor",
            "max_age_ms",
            "invalidation_generation",
            "economic_capacity_commitment_ref",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    permit_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.5 / §13 line 332-340) ----------------
    permit_generation: int | None = None
    rcl_commitment_ref: str | None = None
    writer_epoch: int | None = None
    revision: int | None = None
    command_identity: str | None = None
    policy_digest: str | None = None
    policy_generation: int | None = None
    snapshot_digest: str | None = None
    decision_digest: str | None = None
    cause_digest: str | None = None
    lineage_digest: str | None = None
    resource_vector: ActionFlowVector = ActionFlowVector()
    #: Whether the permit draws ordinary or protective action-flow capacity (§13:336).
    ordinary_or_protective_dimension_mark: str | None = None
    protective_lease_proof: str | None = None
    reserve_proof: str | None = None
    consumer_identity: str | None = None
    #: Single-use claim nonce (rcl ``TransmissionCapability`` ``records.py:295`` pattern).
    claim_nonce: str | None = None
    single_use: bool = True
    issue_anchor: str | None = None
    #: Injected max permit age (VP-002 ``MAX_action_flow_permit_age_ms``, null in Phase 1).
    max_age_ms: int | None = None
    invalidation_generation: int | None = None
    #: The economic-capacity commitment the atomic transaction pairs with (AFG-INV-005).
    economic_capacity_commitment_ref: str | None = None
    authority_effect: ActionFlowGovernorEffect = ActionFlowGovernorEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    permit_order: int | None = None
