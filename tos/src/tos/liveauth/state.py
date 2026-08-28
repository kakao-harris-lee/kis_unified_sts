"""Live Authorization predicate-input / output state models (ADR-002-007 §6-§14.1).

Plain frozen models that carry the *injected* state the pure predicates fold over
(design §0.2: everything is a pure function over injected state — no egress, consensus,
crypto, or human workflow). None derives an id; none mutates in place. Every runtime
fact is an injected ``bool | None`` (``None`` = UNKNOWN = fail-closed) or an opaque
coordinate; **no numeric bound is hard-coded** — bounds enter as injected policy
parameters (design §8), missing ⇒ UNKNOWN ⇒ the consuming predicate fails closed.

Authority / time compose coordinates (``AuthorityEpochState`` / ``CurrentnessWitness`` /
``AuthorityState`` / ``SafetyAuthorityCapability`` / ``HealthState``) are REUSED from
``tos.authority`` / ``tos.time`` (design §3.4/§3.5), never re-authored.

Pure module: ``pydantic`` + stdlib + ``tos.authority`` + ``tos.time`` +
``tos.liveauth`` only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from pydantic import field_serializer

from tos.authority import (
    AuthorityEpochState,
    AuthorityState,
    CurrentnessWitness,
    SafetyAuthorityCapability,
)
from tos.liveauth._base import FrozenModel, LiveAuthorizationEffect
from tos.liveauth.vocabulary import ReArmPathKind
from tos.time import HealthState


class LiveAuthorizationScope(FrozenModel):
    """The scoped-authorization subset coordinate (ADR-002-007 §7 scope; §14).

    Seven frozenset dimensions (design §2.5). ``frozenset`` makes subset (⊆) the natural
    coverage test (§5.3 ``scope_covers``), makes a wildcard **unrepresentable** (§7 line
    218 "no implicit open-ended scope"), and makes the empty set an unambiguous "covers
    nothing" (§5.3 vacuous-True closure). A ``None`` dimension is UNKNOWN and fails
    closed at the consuming predicate. The elements are serialized **sorted** so the
    covered-digest bytes are deterministic across processes even though a ``frozenset``
    iterates in hash order (a Live Authorization / approval record nests a scope in its
    digest preimage; §2.2/§2.4).
    """

    accounts: frozenset[str] | None = None
    strategies: frozenset[str] | None = None
    instrument_classes: frozenset[str] | None = None
    venues: frozenset[str] | None = None
    sessions: frozenset[str] | None = None
    order_types: frozenset[str] | None = None
    action_classes: frozenset[str] | None = None

    @field_serializer(
        "accounts",
        "strategies",
        "instrument_classes",
        "venues",
        "sessions",
        "order_types",
        "action_classes",
        when_used="always",
    )
    def _sorted_dimension(self, value: frozenset[str] | None) -> list[str] | None:
        """Serialize a scope dimension as a sorted list (deterministic digest bytes)."""
        return None if value is None else sorted(value)


class LimitLayering(FrozenModel):
    """One governed dimension's 4-layer limit stack (ADR-002-007 §6.1 line 140-151).

    ``layering_within_bounds`` (§6.1) checks a single governed dimension; multi-dimension
    layering is realized by one :class:`LimitLayering` per dimension. The four limits are
    ordered by **magnitude** — ``per_action_limit`` is the tightest (smallest allowed) and
    ``hard_safety_envelope_limit`` the widest (largest allowed): ``per-action ≤ Live
    Authorization ≤ Runtime Safety Profile ≤ Hard Safety Envelope`` (§6.1 line 145-149
    verbatim; "No lower layer may expand a higher layer", §1 line 29). The two profile
    limits reference ADR-002-014-owned artifacts (``tos`` does not author them); a ``None``
    limit is an unestablished (Phase-1 unapproved) bound and fails closed at consumption.
    """

    governed_dimension: str | None = None
    per_action_limit: int | None = None
    live_authorization_limit: int | None = None
    runtime_safety_profile_limit: int | None = None
    hard_safety_envelope_limit: int | None = None
    runtime_safety_profile_version: str | None = None
    hard_safety_envelope_version: str | None = None


class ContinuousValidityInputs(FrozenModel):
    """Injected inputs the continuous-validity predicate folds (ADR-002-007 §9 line 258-284).

    Groups the authority-compose coordinates (§9 line 260/275 — checked by
    ``authority_epoch_current`` / ``currentness_admissible`` / ``restrictive_dominates``),
    the time-compose coordinates (§9 line 261/262/282 — ``state_permits_new_normal_risk``
    / ``snapshot_age_admissible`` / ``conservative_usable_lifetime``), and the ten injected
    runtime ``bool | None`` conditions (§9 line 263-276). Every ``bool | None`` is
    fail-closed: ``None`` (UNKNOWN) or ``False`` invalidates (§9 line 278 "Loss of any
    required predicate SHALL suspend or revoke new-risk authority"). Fail-closed defaults:
    the health state is not ``TRUSTED`` and the dominating state is ``HALTED``, so a
    default instance yields ``continuous_validity == False``.

    **Epoch coordinate (deliberate seam-closure, deviates from §2.7 enumeration):** the
    design §2.7 lists ``claimed_epoch`` / ``authority_domain`` on this model, but §2.2
    states §5.2 checks *the authorization's own* ``safety_authority_epoch``. To bind the
    currentness check to the authorization's own claim (so a caller cannot pass a fresh
    epoch for a stale authorization — the exact decoupled-coordinate fail-open this series
    seals, §3.5), ``continuous_validity`` reads the claimed epoch + domain **from the
    ``LiveAuthorization``**, and this model carries only the injected epoch-floor
    ``authority_epoch_state``. Realizes the §4.4 coordinate-non-collapse canary directly.
    """

    # ---- authority compose coordinates (§9 line 260, 275) --------------------
    authority_epoch_state: AuthorityEpochState = AuthorityEpochState()
    currentness_witness: CurrentnessWitness = CurrentnessWitness()
    dominating_state: AuthorityState = AuthorityState.HALTED
    outstanding_capabilities: tuple[SafetyAuthorityCapability, ...] = ()

    # ---- time compose coordinates (§9 line 261, 262/282) ---------------------
    time_health_state: HealthState = HealthState.UNINITIALIZED
    snapshot_age_bound: int | None = None
    max_consumer_age_ms: int | None = None
    max_live_authorization_validity: int | None = None
    authorization_elapsed: int | None = None
    source_transport_uncertainty: int | None = None
    max_drift_error: int | None = None
    suspension_uncertainty: int | None = None
    safety_margin: int | None = None

    # ---- ten injected runtime conditions (§9 line 263-276) -------------------
    account_wide_reconciled: bool | None = None
    no_unknown_or_unattributed: bool | None = None
    rcl_capacity_consistent: bool | None = None
    hard_and_runtime_versions_match: bool | None = None
    broker_capability_sufficient: bool | None = None
    deployment_and_identity_digests_match: bool | None = None
    protective_coverage_valid: bool | None = None
    recovery_current: bool | None = None
    capsule_current: bool | None = None
    no_critical_alert_or_invalidation: bool | None = None


class Safe053VariantAttestation(FrozenModel):
    """The SAFE-053 Governed Single-Operator Re-Arm Variant controls (ADR-002-015 §17.1).

    Seven type-gated compensating controls (design §2.7; ADR-002-007 §13 line 429). Every
    control is ``bool | None`` and load-bearing: the variant path opens **only** when all
    seven are positively ``True`` (§6.3 type-gate); any ``None`` (UNKNOWN) / ``False``
    keeps the solo path closed. ``variant_approved`` does **not** subsume
    ``time_separated_reauthenticated_confirmation`` (§17.1.2) or
    ``independent_nonauthorizing_attestation_current`` (§17.1.3) — those are separate
    injected attestations, and subsuming them would re-open the coarse injected-boolean
    seam this series seals (design §2.7). The §17.1.3 attestation is a "non-authorizing
    precondition gate, **not** the second principal" (line 483) — a solo variant has no
    second principal (external-reviewer configurations route to the quorum path, §6.3).
    """

    variant_approved: bool | None = None
    pre_declared_exact_scope: bool | None = None
    time_separated_reauthenticated_confirmation: bool | None = None
    independent_nonauthorizing_attestation_current: bool | None = None
    smallest_approved_scope_delta: bool | None = None
    hard_safety_envelope_not_expanded: bool | None = None
    non_waivable_boundary_preserved: bool | None = None


class DualControlAttestation(FrozenModel):
    """Injected dual-control attestation for a re-arm (ADR-002-007 §13 line 422-435).

    ``rearm_dual_control_satisfied`` (§6.3) folds this into two lawful paths: quorum
    (two distinct principals + a count ≥ 2) or the SAFE-053 solo ``variant``. Principals
    are opaque identity coordinates (distinctness only — actual human authentication is
    ADR-002-015 runtime, REARM-EV-005 +Security not-Phase-1). ``path`` selects which
    environmental-prerequisite expression ``rearm_admissible`` consumes (§6.4).
    """

    armer_principal: str | None = None
    limit_change_approver_principal: str | None = None
    distinct_approver_count: int | None = None
    path: ReArmPathKind | None = None
    variant: Safe053VariantAttestation | None = None


class InPlaceExpansionInputs(FrozenModel):
    """Injected inputs the §14.1 delta-proportional expansion predicate folds (§14.1).

    ``in_place_expansion_admissible`` (§6.6) folds these for a LIVE_RESTRICTED →
    LIVE_NORMAL in-place expansion. The ten proportional flags are ``bool | None`` and
    load-bearing (all must be positively ``True``; any ``None`` / ``False`` fails closed,
    §14.1 line 466-481). The expansion is realized by a **new delta authorization**
    (``new_delta_authorization_id``), never by widening the existing authorization in
    place (§14.1 line 465).
    """

    delta_scope: LiveAuthorizationScope = LiveAuthorizationScope()
    new_delta_authorization_id: str | None = None
    existing_authorization_id: str | None = None
    continuous_validity_unbroken: bool | None = None
    account_reconciliation_for_added_scope: bool | None = None
    unknown_resolved_added: bool | None = None
    rcl_consistency_delta: bool | None = None
    capacity_reserved_for_delta: bool | None = None
    protective_coverage_added: bool | None = None
    envelope_profile_covers_enlarged: bool | None = None
    broker_capability_added: bool | None = None
    no_critical_alert_added: bool | None = None
    recovery_readiness_enlarged: bool | None = None
    capsule_enlarged: bool | None = None
    dual_control: DualControlAttestation = DualControlAttestation()
    progressive_promotion_gate_satisfied: bool | None = None


class ReArmOutcome(FrozenModel):
    """The result of the re-arm-admissibility predicate (ADR-002-007 §12; §6.4).

    ``admissible`` reports only whether every re-arm prerequisite + dual control +
    fresh-identity + partition condition is met — it is **non-authorizing**:
    ``authority_effect`` is all-false (§11 readiness ≠ authority; §4.1). An
    ``admissible=True`` grants no live authority — re-arm then issues a **new** Live
    Authorization (§1 line 42) and new capabilities under the current epoch (ADR-002-003
    §17.3), which re-run §5.2 continuous validity. Isomorphic to
    ``authority.RearmVerdict`` (non-authorizing).
    """

    admissible: bool
    authority_effect: LiveAuthorizationEffect = LiveAuthorizationEffect()
