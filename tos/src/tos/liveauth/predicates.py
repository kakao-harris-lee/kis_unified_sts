"""Pure Live Authorization predicates (design §5, §6; ADR-002-007 §5-§17).

The EV-L1 *functions* whose contract the property tests verify. None is a stored field;
all are computed on demand over **injected** state (design §0.2: no egress, consensus,
crypto, or human dual-control workflow — those are runtime, EV-L2/L3 + Security). Every
predicate is conservative / **fail-closed**: an empty set, a missing / ``None``
coordinate, an unproven witness, an unknown state, or an absent authorization can never
become live authority, coverage, or an admissible re-arm (ADR-002-007 §1 line 17 default
non-live; §9 line 278 "Loss of any required predicate SHALL suspend or revoke").

Predicates COMPOSE ``tos.authority`` (epoch / precedence / dominance / re-arm / capability)
and ``tos.time`` (TRUSTED / freshness) instead of taking injected ``epoch_current`` /
``rearm_armable`` / ``time_trusted`` booleans (design §3.4/§3.5 seam-closure): a wrong
``True`` injection path does not exist. The negative-injected-term fail-closed guard of
``conservative_usable_lifetime`` (Time v1.2 REJECT) is inherited by composition.

Contents (design section -> REARM-EV substrate; **no REARM-EV is closed**, §1):

* §5.1 : ``is_live`` — None authorization / non-ACTIVE / invalid => not live
  (REARM-EV-001 substrate; ``is_live(None) == False`` zero-value canary).
* §5.2 : ``continuous_validity`` — authority + time compose + 10 injected conditions;
  egress condition NOT claimed (REARM-EV-008 substrate; per-order 019/020/021/029/030
  egress-deferred).
* §5.3 : ``scope_covers`` — 7-dimension subset; empty either side => False (REARM-EV-009).
* §5.4 : ``live_authorization_transition_allowed`` — the §8 arrows only (REARM-EV-004).
* §5.5 : ``fresh_authorization_identity`` — None / reuse => False (REARM-EV-004).
* §6.1 : ``layering_within_bounds`` — per-action ≤ … ≤ hard-envelope (REARM-EV-006).
* §6.2 : ``atomic_activation_ok`` — 4 positive conditions (REARM-EV-006).
* §6.3 : ``rearm_dual_control_satisfied`` — quorum ∨ SAFE-053 variant (REARM-EV-005).
* §6.4 : ``rearm_admissible`` / ``no_automatic_rearm`` — quorum direct-consume + variant
  local re-expression + drift anchor (REARM-EV-002/003).
* §6.5 : ``partial_rearm_scope_narrows`` — new ⊆ prior (REARM-EV-009).
* §6.6 : ``in_place_expansion_admissible`` — §14.1 delta, 5 conjuncts (REARM-EV-009).
* §6.7 : ``halt_dominates_authorization`` — authority REUSE (REARM-EV-011).
* §4.3 : ``authorization_revived_by_nothing`` — non-revival (§8.3).

Pure module: ``pydantic`` + stdlib + ``tos.authority`` / ``tos.time`` /
``tos.liveauth`` only; no real clock, no ``shared.*``, no ``tos.rcl`` / ``tos.capsule`` /
``tos.evidence`` / ``tos.dsl`` (§0.3).
"""

from __future__ import annotations

from collections.abc import Sequence

from tos.authority import (
    AuthorityState,
    CapabilityType,
    RearmChecklist,
    SafetyAuthorityCapability,
    authority_epoch_current,
    currentness_admissible,
    halt_denies,
    partition_authority_verdict,
    rearm_gate,
    restrictive_dominates,
)
from tos.liveauth._base import LiveAuthorizationEffect
from tos.liveauth.records import LiveAuthorization
from tos.liveauth.state import (
    ContinuousValidityInputs,
    DualControlAttestation,
    InPlaceExpansionInputs,
    LimitLayering,
    LiveAuthorizationScope,
    ReArmOutcome,
)
from tos.liveauth.vocabulary import LiveAuthorizationState, ReArmPathKind
from tos.time import (
    conservative_usable_lifetime,
    snapshot_age_admissible,
    state_permits_new_normal_risk,
)

#: The seven scope dimensions (design §2.5). ``scope_covers`` / ``partial_rearm_scope_
#: narrows`` range over exactly these — all frozenset coordinates.
_SCOPE_DIMENSIONS: tuple[str, ...] = (
    "accounts",
    "strategies",
    "instrument_classes",
    "venues",
    "sessions",
    "order_types",
    "action_classes",
)

#: The ten injected continuous-validity runtime conditions (§9 line 263-276). Each is
#: ``bool | None`` and load-bearing: ``None`` (UNKNOWN) / ``False`` => invalid.
_INJECTED_CONTINUOUS_CONDITIONS: tuple[str, ...] = (
    "account_wide_reconciled",
    "no_unknown_or_unattributed",
    "rcl_capacity_consistent",
    "hard_and_runtime_versions_match",
    "broker_capability_sufficient",
    "deployment_and_identity_digests_match",
    "protective_coverage_valid",
    "recovery_current",
    "capsule_current",
    "no_critical_alert_or_invalidation",
)

#: The seven SAFE-053 solo-variant compensating controls (§6.3; ADR-002-015 §17.1.1-5).
#: The variant re-arm path opens only when all seven are positively ``True``.
_SAFE053_CONTROLS: tuple[str, ...] = (
    "variant_approved",
    "pre_declared_exact_scope",
    "time_separated_reauthenticated_confirmation",
    "independent_nonauthorizing_attestation_current",
    "smallest_approved_scope_delta",
    "hard_safety_envelope_not_expanded",
    "non_waivable_boundary_preserved",
)

#: The re-arm prerequisite that is the SoD / dual-control element within
#: ``authority._REARM_PREREQUISITES`` (item 14). The variant path excludes it — its
#: separation-of-duties is owned by ``rearm_dual_control_satisfied`` Path 2 (§6.4/M1),
#: not re-derived in the environmental conjunction ("SoD 재유도 금지").
_SOD_PREREQUISITE: str = "explicit_human_dual_control_complete"

#: Liveauth-local **re-expression** of the 14 authority re-arm prerequisites minus the
#: SoD element (13 environmental prerequisites) — consumed by the SAFE-053 variant path
#: of ``rearm_admissible`` (§6.4/M1). This is a genuine local literal, NOT derived from
#: ``authority._REARM_PREREQUISITES`` at runtime; a **drift regression test** (§7) asserts
#: it equals ``authority._REARM_PREREQUISITES`` minus ``_SOD_PREREQUISITE`` item-for-item,
#: so the two lists can never silently diverge (the safety gap the future #6
#: ``RearmVerdict.all_prerequisites`` exposure would otherwise close, §9.1).
_VARIANT_ENVIRONMENTAL_PREREQUISITES: tuple[str, ...] = (
    "trustworthy_time_restored",
    "current_epoch_established",
    "stale_epochs_fenced",
    "account_wide_reconciliation_complete",
    "unknown_orders_resolved",
    "unattributed_external_activity_resolved",
    "risk_capacity_ledger_consistency_verified",
    "protective_leases_reconciled",
    "hard_and_runtime_versions_verified",
    "broker_capability_current",
    "no_unresolved_critical_alert",
    "recovery_coordinator_evidence_complete",
    "fresh_live_authorization_issued",
)

#: The ten §14.1 delta-proportional re-establishment flags (§6.6 item 3). Each is
#: load-bearing; ``None`` / ``False`` on any => not admissible.
_PROPORTIONAL_EXPANSION_FLAGS: tuple[str, ...] = (
    "account_reconciliation_for_added_scope",
    "unknown_resolved_added",
    "rcl_consistency_delta",
    "capacity_reserved_for_delta",
    "protective_coverage_added",
    "envelope_profile_covers_enlarged",
    "broker_capability_added",
    "no_critical_alert_added",
    "recovery_readiness_enlarged",
    "capsule_enlarged",
)

#: The exact ADR-002-007 §8 (line 228-240) lifecycle arrows — the ONLY allowed
#: transitions. Terminal states ({DENIED, SUSPENDED, REVOKED, EXPIRED, SUPERSEDED}) have
#: no outgoing arrow (none returns to ACTIVE — §8.3 non-revival). Transcribed verbatim
#: and double-checked (the #6 v1.2 erratum lesson: an arrow table must match the ADR).
_LIVE_AUTHORIZATION_TRANSITIONS: frozenset[
    tuple[LiveAuthorizationState, LiveAuthorizationState]
] = frozenset(
    {
        # REQUESTED -> VALIDATED -> APPROVED -> ISSUED -> ACTIVE
        (LiveAuthorizationState.REQUESTED, LiveAuthorizationState.VALIDATED),
        (LiveAuthorizationState.VALIDATED, LiveAuthorizationState.APPROVED),
        (LiveAuthorizationState.APPROVED, LiveAuthorizationState.ISSUED),
        (LiveAuthorizationState.ISSUED, LiveAuthorizationState.ACTIVE),
        # {REQUESTED, VALIDATED, APPROVED} -> DENIED
        (LiveAuthorizationState.REQUESTED, LiveAuthorizationState.DENIED),
        (LiveAuthorizationState.VALIDATED, LiveAuthorizationState.DENIED),
        (LiveAuthorizationState.APPROVED, LiveAuthorizationState.DENIED),
        # {ISSUED, ACTIVE} -> {SUSPENDED, REVOKED, EXPIRED, SUPERSEDED}
        (LiveAuthorizationState.ISSUED, LiveAuthorizationState.SUSPENDED),
        (LiveAuthorizationState.ISSUED, LiveAuthorizationState.REVOKED),
        (LiveAuthorizationState.ISSUED, LiveAuthorizationState.EXPIRED),
        (LiveAuthorizationState.ISSUED, LiveAuthorizationState.SUPERSEDED),
        (LiveAuthorizationState.ACTIVE, LiveAuthorizationState.SUSPENDED),
        (LiveAuthorizationState.ACTIVE, LiveAuthorizationState.REVOKED),
        (LiveAuthorizationState.ACTIVE, LiveAuthorizationState.EXPIRED),
        (LiveAuthorizationState.ACTIVE, LiveAuthorizationState.SUPERSEDED),
    }
)


# ===========================================================================
# §5.2 — continuous validity (authority + time compose; fail-closed)
# ===========================================================================


def continuous_validity(
    authorization: LiveAuthorization | None,
    inputs: ContinuousValidityInputs,
) -> bool:
    """Whether every continuous-validity condition currently passes (§9 line 258-284).

    Composes the EV-L1-decidable conditions and folds the injected runtime facts; a
    ``True`` here is only "continuous-validity necessary conditions currently hold", it is
    **not** authorization completion — the final broker-egress independent verification
    (§16) is a runtime check that is NOT asserted here (§9 line 280; §0.2/§4.1, to avoid
    overclaim). Fail-closed throughout — an absent authorization or any unmet condition =>
    invalid:

    * the authorization's **own** claimed epoch is current: ``authority_epoch_current``
      over ``authorization.safety_authority_epoch`` / ``authorization.authority_domain``
      against the injected floor (§9 line 260; §2.2 binds §5.2 to the authorization's own
      epoch — sealing the decoupled-epoch fail-open, §3.5) AND ``currentness_admissible``;
    * time is ``TRUSTED``: ``state_permits_new_normal_risk`` (§9 line 261; not TRUSTED =>
      invalid);
    * no dominating ``CONTAINED`` / ``HALTED``: ``not restrictive_dominates`` (§9 line
      275; order-independent);
    * authorization freshness positively established: ``snapshot_age_admissible`` AND
      ``conservative_usable_lifetime(...) is not None`` — the latter bounded by the
      injected ``MAX_live_authorization_validity`` (§8 missing profile key; §9 line
      262/282; inherits the negative-term fail-closed guard);
    * all ten injected runtime conditions are positively ``True`` (§9 line 263-276; each
      ``None`` / ``False`` => invalid).

    **Egress-deferral (Gap-1):** the per-order ADR-002-019 (Venue) / 020 (Order
    Construction) / 021 (Aggregate Risk) currentness and 029 (Release) / 030 (Post-Trade)
    bindings are "for the exact order" / per-send, so they are **explicitly deferred to
    final egress** (REARM-EV-010 not-Phase-1), NOT folded into this scope-level predicate
    — an explicit deferral, not an implicit omission.

    Args:
        authorization: The Live Authorization under test (``None`` => not valid).
        inputs: The injected continuous-validity inputs (authority + time + 10 flags).

    Returns:
        ``True`` iff every modeled continuous-validity condition currently holds
        (necessary, not sufficient — egress is §0.2).
    """
    if authorization is None:
        return False
    if not authority_epoch_current(
        authorization.safety_authority_epoch,
        authorization.authority_domain,
        inputs.authority_epoch_state,
    ):
        return False
    if not currentness_admissible(inputs.currentness_witness):
        return False
    if not state_permits_new_normal_risk(inputs.time_health_state):
        return False
    if restrictive_dominates(inputs.dominating_state, inputs.outstanding_capabilities):
        return False
    if not snapshot_age_admissible(
        inputs.snapshot_age_bound, inputs.max_consumer_age_ms
    ):
        return False
    if (
        conservative_usable_lifetime(
            issued_lifetime=inputs.max_live_authorization_validity,
            elapsed_monotonic=inputs.authorization_elapsed,
            source_transport_uncertainty=inputs.source_transport_uncertainty,
            max_drift_error=inputs.max_drift_error,
            suspension_uncertainty=inputs.suspension_uncertainty,
            safety_margin=inputs.safety_margin,
        )
        is None
    ):
        return False
    return all(
        getattr(inputs, name) is True for name in _INJECTED_CONTINUOUS_CONDITIONS
    )


# ===========================================================================
# §5.1 — default non-live (REARM-AC-001; §1 line 17; §8.1)
# ===========================================================================


def is_live(
    authorization: LiveAuthorization | None,
    current_state: LiveAuthorizationState | None,
    inputs: ContinuousValidityInputs,
) -> bool:
    """Whether a Live Authorization is currently live (§5.1; REARM-AC-001; §8.1).

    ``True`` only when **all** hold: the authorization is present, its current state is
    ``ACTIVE``, and ``continuous_validity`` passes. An absent authorization (``None`` —
    the default / zero-value case, §1 line 17 default non-live), a non-``ACTIVE`` state
    (``ISSUED`` is not ``ACTIVE`` — §8.1 line 242-244 "not inferred from the artifact
    merely being issued"), or a failed continuous validity => **False** (non-live). The
    model provides no path deriving live from possession / issuance / any restart /
    failover / rollback input (§15; constructive absence). [REARM-AC-001; SAFE-045/046/047]

    Args:
        authorization: The Live Authorization (``None`` => non-live; zero-value canary).
        current_state: The injected current lifecycle state (must be ``ACTIVE``).
        inputs: The injected continuous-validity inputs.

    Returns:
        ``True`` iff the authorization is present, ``ACTIVE``, and continuously valid.
    """
    if authorization is None:
        return False
    if current_state != LiveAuthorizationState.ACTIVE:
        return False
    return continuous_validity(authorization, inputs)


# ===========================================================================
# §5.3 — subset scope coverage (vacuous-True closure; REARM-AC-009)
# ===========================================================================


def scope_covers(
    authorization_scope: LiveAuthorizationScope | None,
    requested: LiveAuthorizationScope | None,
) -> bool:
    """Whether an authorization scope covers a requested scope (§5.3; §7 line 216-218).

    ``True`` only when, for **all seven** dimensions: (i) both dimensions are non-``None``,
    (ii) the authorization dimension is **non-empty**, (iii) the requested dimension is
    **non-empty**, and (iv) ``requested[dim] ⊆ authorization[dim]``. Defined order = set
    inclusion ⊆ (requested is inner/narrow, authorization is outer/wide), double-checked
    against "narrow never covers wider" (#6 v1.2 erratum lesson). An **empty authorization
    scope => covers nothing (False)**; an **empty requested => not a valid action
    (False)**; a **narrow authorization ⊉ a wider request (False)**; a **``None`` /
    wildcard dimension => False** (§7 line 218 no implicit "all"). The non-empty
    requirements (ii)/(iii) close the ``∅ ⊆ ∅ = True`` vacuous-True fail-open (the #6 M1
    ``lease_scope_exclusive`` defect class). [REARM-AC-009]

    Args:
        authorization_scope: The granted scope (``None`` => covers nothing).
        requested: The requested scope (``None`` / empty => not a valid action).

    Returns:
        ``True`` iff the requested scope is a non-empty subset of a non-empty
        authorization scope in every dimension.
    """
    if authorization_scope is None or requested is None:
        return False
    for dim in _SCOPE_DIMENSIONS:
        auth_dim = getattr(authorization_scope, dim)
        req_dim = getattr(requested, dim)
        if auth_dim is None or req_dim is None:
            return False
        if not auth_dim:  # empty authorization dimension => covers nothing
            return False
        if not req_dim:  # empty requested dimension => not a valid action
            return False
        if not req_dim <= auth_dim:  # requested ⊆ authorization
            return False
    return True


# ===========================================================================
# §5.4 — lifecycle transition legality (non-revival; REARM-AC-004; §8.3)
# ===========================================================================


def live_authorization_transition_allowed(
    from_state: LiveAuthorizationState | None,
    to_state: LiveAuthorizationState | None,
) -> bool:
    """Whether a Live Authorization lifecycle transition is allowed (§5.4; §8 line 224-252).

    ``True`` only for the exact ADR §8 arrows (``_LIVE_AUTHORIZATION_TRANSITIONS``):
    ``REQUESTED → VALIDATED → APPROVED → ISSUED → ACTIVE``; ``{REQUESTED, VALIDATED,
    APPROVED} → DENIED``; ``{ISSUED, ACTIVE} → {SUSPENDED, REVOKED, EXPIRED, SUPERSEDED}``.
    A terminal state ({DENIED, SUSPENDED, REVOKED, EXPIRED, SUPERSEDED}) has **no** outgoing
    transition — in particular none returns to ``ACTIVE`` (§8.3 line 250-252 non-revival).
    ``None`` on either side => ``False`` (fail-closed). [REARM-AC-004; §8.3]

    Args:
        from_state: The current lifecycle state (``None`` => not allowed).
        to_state: The proposed next lifecycle state (``None`` => not allowed).

    Returns:
        ``True`` iff ``(from_state, to_state)`` is one of the §8 arrows.
    """
    if from_state is None or to_state is None:
        return False
    return (from_state, to_state) in _LIVE_AUTHORIZATION_TRANSITIONS


# ===========================================================================
# §5.5 — fresh authorization identity (REARM-AC-004; §8.3; §1 line 42)
# ===========================================================================


def fresh_authorization_identity(
    new_authorization_id: str | None,
    prior_authorization_ids: frozenset[str],
) -> bool:
    """Whether a re-arm's new authorization identity is fresh (§5.5; §8.3 line 250-252).

    ``True`` only when ``new_authorization_id`` is present AND not any prior authorization
    id. A ``None`` id or a reused prior id => ``False`` (§1 line 42 "A revoked, expired,
    suspended, superseded, or stale authorization SHALL NOT be revived"; re-arm "issues a
    new authorization identity"). An empty prior set + a concrete new id => ``True`` (the
    first authorization). Forgery / replay of a reused id is detected separately by
    ``classify_record_pair`` (same-id / different-bytes => CRITICAL_CONFLICT; id ⊥ digest,
    §4.6). [REARM-AC-004; §8.3]

    Args:
        new_authorization_id: The re-arm's new authorization id (``None`` => not fresh).
        prior_authorization_ids: The set of prior authorization ids.

    Returns:
        ``True`` iff the new id is present and not a reuse of any prior id.
    """
    if new_authorization_id is None:
        return False
    return new_authorization_id not in prior_authorization_ids


# ===========================================================================
# §6.1 — limit layering (magnitude order double-checked; REARM-AC-006)
# ===========================================================================


def layering_within_bounds(layering: LimitLayering) -> bool:
    """Whether a governed dimension's limit stack is within bounds (§6.1 line 140-151).

    ``True`` only when ``per_action_limit ≤ live_authorization_limit ≤
    runtime_safety_profile_limit ≤ hard_safety_envelope_limit`` (§6.1 line 145-149
    verbatim: inner ≤ outer, tighter ≤ wider). Any limit ``None`` => ``False``
    (fail-closed — an unestablished limit is unusable); any inner > outer => ``False``
    (§1 line 29 "No lower layer may expand a higher layer"). Defined order = limit
    **magnitude** (per-action tightest, Hard Envelope widest), double-checked against the
    ADR verbatim (#6 v1.2 transposition erratum lesson). [REARM-AC-006; SAFE-003/004/050]

    Args:
        layering: The four-layer limit stack for one governed dimension.

    Returns:
        ``True`` iff all four limits are concrete and non-decreasing from per-action to
        Hard Safety Envelope.
    """
    per_action = layering.per_action_limit
    live_auth = layering.live_authorization_limit
    runtime_profile = layering.runtime_safety_profile_limit
    hard_envelope = layering.hard_safety_envelope_limit
    if (
        per_action is None
        or live_auth is None
        or runtime_profile is None
        or hard_envelope is None
    ):
        return False
    return per_action <= live_auth <= runtime_profile <= hard_envelope


# ===========================================================================
# §6.2 — atomic safety-configuration activation (REARM-AC-006; §6.4 line 171-173)
# ===========================================================================


def atomic_activation_ok(
    *,
    version_fully_active: bool | None,
    mixed_versions_present: bool | None,
    units_compatible: bool | None,
    envelope_bounded: bool | None,
) -> bool:
    """Whether a safety-configuration activation is atomic and safe (§6.2; §6.4 line 171-173).

    ``True`` only when **all four positive conditions** hold: the new version is fully
    active, no mixed versions are present, units are compatible, and the result is
    envelope-bounded. Any ``None`` (UNKNOWN) or unsafe value => ``False`` (§6.4 line 173
    "Partial distribution, mixed versions, missing values, incompatible units, or
    unverifiable activation state SHALL fail closed"). [REARM-AC-006; SAFE-003/004/050]

    Args:
        version_fully_active: Whether the new version is fully active (``None`` => fail).
        mixed_versions_present: Whether mixed versions are present (must be ``False``).
        units_compatible: Whether units are compatible (``None`` => fail).
        envelope_bounded: Whether the result stays envelope-bounded (``None`` => fail).

    Returns:
        ``True`` iff the activation is fully active, single-version, unit-compatible, and
        envelope-bounded.
    """
    return (
        version_fully_active is True
        and mixed_versions_present is False
        and units_compatible is True
        and envelope_bounded is True
    )


# ===========================================================================
# §6.3 — two-lawful-paths dual control (type-gated disjunction; REARM-AC-005)
# ===========================================================================


def rearm_dual_control_satisfied(attestation: DualControlAttestation) -> bool:
    """Whether re-arm dual control is satisfied by a lawful path (§6.3; §13 line 429).

    A **type-gated disjunction** (#6 M2 isomorph) — ``True`` when either lawful path is
    positively established:

    * **Path 1 (quorum)**: both principals present AND distinct AND
      ``distinct_approver_count >= 2`` (§13 line 428 two natural persons). The recognized
      External Independent Reviewer configuration is a **genuine second effective
      principal** and satisfies this path by construction (ADR-002-015 §17.1.4 line 487) —
      it is Path 1, not Path 2.
    * **Path 2 (SAFE-053 Governed Single-Operator Re-Arm Variant — solo config only)**:
      ``variant`` is present AND all seven compensating controls are ``True`` (incl.
      §17.1.2 time-separation and §17.1.3 attestation; ``variant_approved`` does not
      subsume them, §2.7). A solo variant has **no** second principal; §17.1.3 is a
      "non-authorizing precondition gate, not the second principal" (line 483).

    Both paths failing => ``False`` (fail-closed). The type-gate is the fail-open closure:
    a single operator with an absent / incomplete variant opens neither path (Path 1
    requires distinct principals, Path 2 requires a complete variant), so a "vacuous OR of
    empty inputs" cannot arise. [REARM-AC-005; SAFE-053; §13; ADR-002-015 §17.1.1-5]

    Args:
        attestation: The injected dual-control attestation.

    Returns:
        ``True`` iff a quorum or a complete SAFE-053 variant path is established.
    """
    # Path 1 — quorum: two distinct effective principals.
    count = attestation.distinct_approver_count
    if (
        attestation.limit_change_approver_principal is not None
        and attestation.armer_principal is not None
        and attestation.limit_change_approver_principal != attestation.armer_principal
        and count is not None
        and count >= 2
    ):
        return True
    # Path 2 — SAFE-053 solo variant: present + all seven controls positively True.
    variant = attestation.variant
    if variant is None:
        return False
    return all(getattr(variant, name) is True for name in _SAFE053_CONTROLS)


# ===========================================================================
# §6.4 — re-arm consumption + no automatic re-arm (REARM-AC-002/003; §12)
# ===========================================================================


def rearm_admissible(
    checklist: RearmChecklist,
    dual_control: DualControlAttestation,
    new_authorization_id: str | None,
    prior_authorization_ids: frozenset[str],
    partition_control_plane_verifiable: bool | None,
) -> ReArmOutcome:
    """Whether a re-arm is admissible (§6.4; §12; M1 quorum-direct / variant-local).

    ``admissible=True`` only when **all** hold (each conjunct fail-closed):

    1. **Environmental prerequisites (M1)** — the ``dual_control.path`` selects the
       expression: the **quorum** path directly consumes ``rearm_gate(checklist).armable``
       (the 14 prerequisites + strict distinct-principal SoD, unchanged); the **variant**
       path (solo config, whose ``rearm_gate.armable`` is necessarily ``False`` and whose
       14-item / SoD breakdown ``RearmVerdict`` does not expose) checks the 13 liveauth-
       local ``_VARIANT_ENVIRONMENTAL_PREREQUISITES`` all ``True`` — **SoD is NOT
       re-derived here** (it is owned by ``rearm_dual_control_satisfied`` Path 2); a drift
       regression test keeps the 13 in lock-step with ``authority._REARM_PREREQUISITES``.
       A ``None`` / unknown path => fail-closed.
    2. **Dual control**: ``rearm_dual_control_satisfied(dual_control)`` (§6.3).
    3. **Fresh Live Authorization**: ``fresh_authorization_identity`` (ADR-002-003 §17.3
       line 678 / ADR-002-007 §1 line 42 — re-arm always issues a new identity).
    4. **No partition auto-rearm**: the control plane must be verifiable —
       ``partition_authority_verdict(...).live_rearm_denied`` must be ``False`` (a ``None``
       / ``False`` verifiability denies; automatic re-arm is unconditionally denied, §6.6).

    ``ReArmOutcome.authority_effect`` is all-false: an ``admissible=True`` grants **no**
    live authority (§11 readiness ≠ authority) — re-arm then issues a fresh Live
    Authorization + capabilities that re-run §5.2 continuous validity. [REARM-AC-002; §12]

    Args:
        checklist: The authority re-arm checklist (14 prerequisites + principals).
        dual_control: The dual-control attestation (selects the path via ``.path``).
        new_authorization_id: The re-arm's new authorization id.
        prior_authorization_ids: The set of prior authorization ids.
        partition_control_plane_verifiable: Whether the control plane is verifiable
            (``None`` / ``False`` => partition denies the re-arm).

    Returns:
        A non-authorizing :class:`~tos.liveauth.state.ReArmOutcome`.
    """
    if dual_control.path is ReArmPathKind.QUORUM:
        environmental_ok = rearm_gate(checklist).armable
    elif dual_control.path is ReArmPathKind.GOVERNED_SINGLE_OPERATOR:
        environmental_ok = all(
            getattr(checklist, name) is True
            for name in _VARIANT_ENVIRONMENTAL_PREREQUISITES
        )
    else:
        environmental_ok = False  # None / unknown path => fail-closed
    dual_control_ok = rearm_dual_control_satisfied(dual_control)
    fresh_ok = fresh_authorization_identity(
        new_authorization_id, prior_authorization_ids
    )
    partition_ok = not partition_authority_verdict(
        partition_control_plane_verifiable
    ).live_rearm_denied
    admissible = environmental_ok and dual_control_ok and fresh_ok and partition_ok
    return ReArmOutcome(
        admissible=admissible, authority_effect=LiveAuthorizationEffect()
    )


def no_automatic_rearm(
    *,
    health_recovered: bool | None,
    timeout_elapsed: bool | None,
    reconciliation_completed: bool | None,
    leader_elected: bool | None,
    restart_completed: bool | None,
) -> bool:
    """Whether automatic re-arm is prevented — always (§6.4; REARM-AC-003; §1 line 38).

    Unconditionally ``True``: none of health recovery, a timeout, reconciliation
    completion, leader election, or a restart can automatically re-arm (§1 line 38 "No
    health signal, timeout, restart, failover … may automatically create any of these
    permissive artifacts"; §17 line 555). This is enforced **structurally**:
    ``rearm_admissible`` does not accept any of these flags, so no code path can turn one
    into admissibility. This predicate documents and fixes that absence (isomorphic to the
    authority / time / RCL ``recovery_generation_revives_nothing``). [REARM-AC-003; SA-INV-013]

    Args:
        health_recovered: A health-recovery signal (structurally unread).
        timeout_elapsed: A timeout signal (structurally unread).
        reconciliation_completed: A reconciliation-completion signal (structurally unread).
        leader_elected: A leader-election signal (structurally unread).
        restart_completed: A restart-completion signal (structurally unread).

    Returns:
        ``True`` always (no automatic re-arm path exists).
    """
    del (
        health_recovered,
        timeout_elapsed,
        reconciliation_completed,
        leader_elected,
        restart_completed,
    )
    return True


# ===========================================================================
# §6.5 — partial / staged re-arm scope narrowing (REARM-AC-009; §14 line 441-454)
# ===========================================================================


def partial_rearm_scope_narrows(
    prior_scope: LiveAuthorizationScope,
    new_scope: LiveAuthorizationScope,
) -> bool:
    """Whether a partial / staged re-arm only narrows scope (§6.5; §14 line 441-454).

    ``True`` only when ``new_scope[dim] ⊆ prior_scope[dim]`` for **every** dimension
    (§14 line 442 "restore the smallest proven scope"; line 449 "prevent fallback to a
    broader prior scope"). Any ``None`` dimension => ``False`` (fail-closed). The model
    provides no operation widening ``new_scope`` beyond ``prior_scope`` (frozen; expansion
    requires a new authorization, §14.1), and derives no scope expansion from any success
    signal (§14 line 454 "Successful operation … is evidence for review, not automatic
    authorization for expansion"; constructive absence).

    **Narrowing-to-∅ (Gap-2):** an empty ``new_scope`` satisfies ``∅ ⊆ prior`` and is
    ``True`` — this is the lawful **full de-authorization** case; consistent with §5.3,
    the de-authorized scope then covers nothing (``scope_covers(∅, *) == False``), so it
    validates no subsequent action. [REARM-AC-009; SAFE-046/047]

    Args:
        prior_scope: The prior (wider-or-equal) scope.
        new_scope: The proposed narrowed scope.

    Returns:
        ``True`` iff the new scope is a subset of the prior scope in every dimension.
    """
    for dim in _SCOPE_DIMENSIONS:
        prior_dim = getattr(prior_scope, dim)
        new_dim = getattr(new_scope, dim)
        if prior_dim is None or new_dim is None:
            return False
        if not new_dim <= prior_dim:  # new ⊆ prior (narrowing only)
            return False
    return True


# ===========================================================================
# §6.6 — §14.1 delta-proportional in-place expansion (§14.1 line 456-496)
# ===========================================================================


def in_place_expansion_admissible(
    inputs: InPlaceExpansionInputs,
    existing_authorization: LiveAuthorization,
) -> bool:
    """Whether a §14.1 delta-proportional in-place expansion is admissible (§6.6; §14.1).

    ``True`` only when **all five** §14.1 conjuncts hold (each fail-closed):

    1. **Continuity unbroken** (§14.1 line 492-496): ``continuous_validity_unbroken is
       True`` — a broken continuity forces the full §12 re-arm from non-live (a ``False``
       return here signals "take the full path").
    2. **New delta authorization** (§14.1 item 1, line 463-465): ``new_delta_
       authorization_id`` is present AND ``!= existing_authorization_id`` AND the passed
       ``existing_authorization.authorization_id == existing_authorization_id``. The **old
       authorization is never stretched** — the model provides no in-place widening of the
       existing authorization (frozen; expansion = a new authorization).
    3. **Proportional re-establishment** (§14.1 item 2, line 466-481): all ten
       ``_PROPORTIONAL_EXPANSION_FLAGS`` are ``True`` (``None`` / ``False`` on any => fail).
    4. **Dual control preserved** (§14.1 item 3, line 482-486): ``rearm_dual_control_
       satisfied(inputs.dual_control)`` (§6.3).
    5. **Progressive-promotion gate** (§14.1 item 4, line 487-490): ``progressive_
       promotion_gate_satisfied is True`` (ADR-002-025 — success count / elapsed time /
       no-incident cannot auto-expand). [REARM-AC-009; §14.1; SAFE-046/047]

    Args:
        inputs: The injected §14.1 expansion inputs.
        existing_authorization: The existing (LIVE_RESTRICTED) authorization.

    Returns:
        ``True`` iff all five §14.1 delta-proportional conjuncts hold.
    """
    if inputs.continuous_validity_unbroken is not True:
        return False
    if inputs.new_delta_authorization_id is None:
        return False
    if inputs.existing_authorization_id is None:
        return False
    if inputs.new_delta_authorization_id == inputs.existing_authorization_id:
        return False
    if existing_authorization.authorization_id != inputs.existing_authorization_id:
        return False
    if not all(getattr(inputs, name) is True for name in _PROPORTIONAL_EXPANSION_FLAGS):
        return False
    if not rearm_dual_control_satisfied(inputs.dual_control):
        return False
    return inputs.progressive_promotion_gate_satisfied is True


# ===========================================================================
# §6.7 — HALT restrictive precedence (authority REUSE; REARM-AC-011; §17)
# ===========================================================================


def halt_dominates_authorization(
    dominating_state: AuthorityState,
    outstanding_capabilities: Sequence[SafetyAuthorityCapability],
    capability_type: CapabilityType,
) -> bool:
    """Whether HALT dominates an authorization / capability (§6.7; §17 line 547-555).

    ``True`` (dominated / denied) when ``restrictive_dominates`` holds (a HALT / CONTAIN
    state or any outstanding HALT / CONTAIN capability — order-independent, §17 line 551
    "HALT SHALL dominate outstanding permissive capabilities and Live Authorization") OR
    ``halt_denies(capability_type)`` (HALT denies new risk-increasing / re-arm / limit-
    activation types). Pure authority REUSE — no new precedence logic. The model derives
    **no** cancel-all from HALT (``halt_denies`` REUSE — cancellation is protective
    ownership + aggregate-risk, RCL's concern referenced only by scalar; constructive
    absence, §17 line 551). [REARM-AC-011; §17; SAFE-042]

    Args:
        dominating_state: The current dominating authority state.
        outstanding_capabilities: The outstanding capabilities (order irrelevant).
        capability_type: The capability / action type under HALT.

    Returns:
        ``True`` iff the authorization / capability is dominated by HALT.
    """
    return restrictive_dominates(
        dominating_state, outstanding_capabilities
    ) or halt_denies(capability_type)


# ===========================================================================
# §4.3 — non-revival (§8.3; REARM-AC-004)
# ===========================================================================


def authorization_revived_by_nothing(
    *,
    invalidated_under_generation: int | None,
    new_generation: int | None,
) -> bool:
    """Whether a later generation revives an invalidated authorization — never (§4.3; §8.3).

    Unconditionally ``True``: a Live Authorization invalidated (revoked / expired /
    suspended / superseded / denied) under generation N is **not** revived by generation
    N+1 or any later one (§1 line 42; §8.3 line 250-252 "cannot return to ``ACTIVE``";
    §10 line 359 revocation of future authority releases nothing). Re-arm issues a **new**
    authorization identity, it does not revive the old (§5.5). The model provides **no**
    operation mapping a generation / recovery increase to authorization restoration; this
    predicate documents and fixes that absence (isomorphic to the authority / time / RCL
    ``recovery_generation_revives_nothing``).

    Args:
        invalidated_under_generation: The generation under which it was invalidated.
        new_generation: A later recovery / restore generation.

    Returns:
        ``True`` always (non-revival holds).
    """
    del invalidated_under_generation, new_generation  # no revival path exists
    return True
