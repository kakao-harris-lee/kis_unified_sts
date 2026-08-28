"""Pure brokercap predicates (design #10 §5, §6).

The EV-L1 *functions* the property tests verify — none is a stored field; all are computed
on demand over **injected** state (design #10 §0.2: no clock, no egress, no persistence,
no capacity mutation — those are runtime EV-L2/L3). Every predicate is conservative /
**fail-closed** (design #10 §4.1): a missing / undeclared / unknown / contradictory /
expired / unproven input never becomes ``ADMISSIBLE`` / ``True`` — live admission requires
**positive proof**, and there is deliberately no "assume-admissible" path anywhere.

Produced-value seam (design #10 §3.4): brokercap imports **none** of its consumers
(``tos.liveauth`` / ``tos.orthostate`` / ``tos.recon`` / ``tos.rcl``) — it produces plain
``bool`` / ``str`` outputs their already-ratified predicates consume as injected
``bool | None`` / ``str | None`` flags (or, for the orthostate BROKER_ORDER dimension, a
``bool`` the caller maps to a ``ConservatismBasis``). Polarity / fail-closed alignment:

* :func:`broker_capability_sufficient` ``True`` <=> liveauth ``continuous_validity`` may
  hold its ``broker_capability_sufficient`` condition; ``False`` fails it closed.
* :func:`profile_version_current` ``True`` <=> liveauth ``broker_capability_current``.
* :func:`fqp_adequate` ``True`` <=> recon ``final_quantity_proof_token`` True and
  orthostate ``final_quantity_proof_where_broker_involved`` True.
* :func:`broker_evidence_admissible_under_profile` ``True`` -> caller maps to
  ``ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE`` (strong); ``False`` -> ``None``
  (weak) => orthostate ``conservative_direction_ok`` blocks the reduction.

brokercap returns ``bool`` / ``str``; the consuming signatures are ``bool | None`` /
``str | None`` (``None`` fails closed), so a brokercap ``False`` and a caller-supplied
``None`` are both safe. Runtime wiring is the caller's (future Broker Adapter) concern; the
MANDATED test-only cross-checks (``test_seam_liveauth`` / ``test_seam_recon`` /
``test_seam_orthostate``) lock this alignment without making the seam a package edge.

Numbers are never hardcoded: every bound / quota / window / horizon is an injected
parameter, and a ``None`` bound fails closed (design #10 §8). Broker-agnostic: no predicate
names a concrete broker (design #10 §0.1).

Pure module: ``pydantic`` + stdlib + ``tos.brokercap`` only; no ``shared.*``, no sibling
``tos.*`` (design #10 §0.3).
"""

from __future__ import annotations

from tos.brokercap.records import (
    BrokerCapabilityProfile,
    BrokerEvidenceRef,
    CapabilityDeclaration,
    FallbackSpec,
    FinalQuantityEvidence,
    FinalQuantityProofRule,
    ObservedBehavior,
    RequiredCapabilitySet,
    UncertainSendVerdict,
)
from tos.brokercap.vocabulary import (
    ASSURANCE_LEVEL_RANK,
    AUTHORIZING_STATUSES,
    NON_LIVE_OR_SUPERVISED_CLASSES,
    Admissibility,
    AssuranceLevel,
    CapabilityDimension,
    CapabilityStatus,
)

# ===========================================================================
# §5.1 — declaration-level status / level gate
# ===========================================================================


def _declaration_authorizes(
    declaration: CapabilityDeclaration | None,
    required_level: AssuranceLevel | None,
) -> bool:
    """Whether a single declaration authorizes live behavior (ADR §5.3 line 146; §9 line 540).

    Fail-closed on every uncertain input:

    * ``declaration is None`` (an **undeclared** dimension, BC-INV-001) => ``False`` —
      treated as unavailable, never a vacuous pass (design #10 §4.1).
    * ``status`` not in :data:`~tos.brokercap.vocabulary.AUTHORIZING_STATUSES` (i.e. not
      ``VERIFIED`` and not ``VERIFIED_WITH_RESTRICTION``) => ``False``. The five
      non-authorizing statuses (``DOCUMENTED_NOT_VERIFIED`` / ``UNSUPPORTED`` /
      ``CONTRADICTORY`` / ``UNKNOWN`` / ``EXPIRED``) never authorize (§5.3 line 146).
    * ``VERIFIED_WITH_RESTRICTION`` additionally requires ``restriction_approved is True``
      (the explicit approval; ``None`` / ``False`` fails closed).
    * ``assurance_level`` below ``required_level`` (or either unranked / ``None``) =>
      ``False`` — an unspecified required level fails closed to the highest requirement
      (design #10 §5.1).

    Args:
        declaration: The dimension's declaration, or ``None`` when undeclared.
        required_level: The injected minimum assurance level (``None`` => fail-closed).

    Returns:
        ``True`` iff the declaration positively authorizes live behavior at the required
        level.
    """
    if declaration is None:
        return False
    if declaration.status not in AUTHORIZING_STATUSES:
        return False
    if (
        declaration.status is CapabilityStatus.VERIFIED_WITH_RESTRICTION
        and declaration.restriction_approved is not True
    ):
        return False
    if required_level is None:
        return False
    declared_rank = ASSURANCE_LEVEL_RANK.get(declaration.assurance_level)  # type: ignore[arg-type]
    required_rank = ASSURANCE_LEVEL_RANK.get(required_level)
    if declared_rank is None or required_rank is None:
        return False
    return declared_rank >= required_rank


# ===========================================================================
# §5.1 — capability_admissible (the central fail-closed predicate)
# ===========================================================================


def capability_admissible(
    profile: BrokerCapabilityProfile | None,
    action_class: str | None,
    required: RequiredCapabilitySet | None,
    *,
    version_current: bool | None = None,
) -> Admissibility:
    """The central admissibility verdict (ADR-002-004 §1 line 32; §5.2/§11; BC-INV-001/005/008).

    "Missing, unknown, contradictory, expired, or unverified capability evidence SHALL
    reduce live scope or prohibit the affected action" (ADR line 32). Returns
    :class:`~tos.brokercap.vocabulary.Admissibility`:

    * ``ADMISSIBLE`` only when **every** positive condition holds: ``profile`` and
      ``required`` are present, ``required.required_level`` is set, the §11 minimum-live
      gate is satisfied, ``version_current is True`` (§6.1), and **every** required
      dimension authorizes (:func:`_declaration_authorizes`).
    * ``REDUCED`` when the only deficiencies are dimensions that all have an approved
      conservative fallback (``required.approved_fallback_dimensions``) — a restricted-live
      smaller scope (design #10 §5.3). A stale version / unmet gate can **never** be
      fallback'd out of (they force ``PROHIBITED``).
    * ``PROHIBITED`` otherwise — an undeclared / non-authorizing dimension with no approved
      fallback, an unset required level, an unmet minimum-live gate, or a non-current
      version. This is the most-restrictive default; there is **no** permissive fallthrough
      (design #10 §4.1).

    The conformance class is **not** consulted here — a class cannot override a failed
    mandatory dimension (§10 line 584); it is only a summary label
    (:func:`active_conformance_class`).

    **Unspecified-required doctrine (§5.1 verbatim):** "required 미지정 ⇒ fail-closed (전
    차원 필요·최고 level로 취급)". An **empty** ``required.required_dimensions`` is unspecified,
    so it is treated as **all 17 dimensions at the highest assurance level**
    (``LEVEL_4_CONTINUOUSLY_MONITORED``) — a zero-iteration loop must never yield a vacuous
    ``ADMISSIBLE`` (design #10 §4.1 fail-open seal).

    Args:
        profile: The Broker Capability Profile under test (``None`` => ``PROHIBITED``).
        action_class: An opaque label for the action class (non-load-bearing; the required
            dimensions/level are carried by ``required``).
        required: The injected required-capability set (``None`` => ``PROHIBITED``).
        version_current: Whether the profile version is current (§6.1). ``None`` / ``False``
            => ``PROHIBITED``.

    Returns:
        The admissibility verdict.
    """
    del action_class  # opaque label; the requirement is carried by ``required``
    if profile is None or required is None:
        return Admissibility.PROHIBITED

    # §5.1 doctrine (verbatim): "required 미지정 ⇒ fail-closed (**전 차원 필요·최고 level로
    # 취급**)". An **empty** required-dimension set is "unspecified", so it is treated as
    # ALL 17 dimensions at the HIGHEST assurance level — never a vacuous ADMISSIBLE from a
    # zero-iteration loop (the fail-open seal; a code-review MAJOR). With an empty
    # approved-fallback set this yields PROHIBITED unless every one of the 17 dimensions is
    # VERIFIED at LEVEL_4 (both-ways preserved).
    if required.required_dimensions:
        required_dimensions = required.required_dimensions
        required_level = required.required_level
    else:
        required_dimensions = frozenset(CapabilityDimension)
        required_level = AssuranceLevel.LEVEL_4_CONTINUOUSLY_MONITORED
    if required_level is None:
        return Admissibility.PROHIBITED
    if required.minimum_live_gate_satisfied is not True:
        return Admissibility.PROHIBITED
    if version_current is not True:
        return Admissibility.PROHIBITED

    deficient: set[CapabilityDimension] = set()
    for dimension in required_dimensions:
        declaration = profile.declaration_for(dimension)
        if not _declaration_authorizes(declaration, required_level):
            deficient.add(dimension)

    if not deficient:
        return Admissibility.ADMISSIBLE
    if deficient <= required.approved_fallback_dimensions:
        return Admissibility.REDUCED
    return Admissibility.PROHIBITED


# ===========================================================================
# §5.2 — liveauth producers (produced-bool / scalar seam)
# ===========================================================================


def broker_capability_sufficient(
    profile: BrokerCapabilityProfile | None,
    requested_scope: RequiredCapabilitySet | None,
    *,
    version_current: bool | None = None,
) -> bool:
    """Whether the profile is sufficient for the requested scope (design #10 §5.2; §3.4).

    ``True`` **only** when :func:`capability_admissible` is ``ADMISSIBLE`` — a ``REDUCED``
    or ``PROHIBITED`` verdict is not sufficient for the requested scope as-is (a reduced
    scope is a *different, smaller* scope). This produced bool fills liveauth's injected
    ``broker_capability_sufficient`` continuous-validity condition (``state.py:136``;
    ``None`` / ``False`` => invalid). Fail-closed: any deficiency => ``False``.

    Args:
        profile: The Broker Capability Profile (``None`` => ``False``).
        requested_scope: The injected required-capability set for the requested scope.
        version_current: Whether the profile version is current (``None`` / ``False`` =>
            ``False``).

    Returns:
        ``True`` iff the requested scope is fully admissible as-is.
    """
    return (
        capability_admissible(
            profile, None, requested_scope, version_current=version_current
        )
        is Admissibility.ADMISSIBLE
    )


def broker_capability_added(
    profile: BrokerCapabilityProfile | None,
    delta_scope: RequiredCapabilitySet | None,
    *,
    version_current: bool | None = None,
    envelope_not_expanded: bool | None = None,
) -> bool:
    """Whether the enlarged (delta) scope is fully covered (ADR §14.1; design #10 §5.2).

    For a §14.1 in-place expansion: ``True`` **only** when the delta scope's required
    dimensions are **all** admissible in the current profile (``ADMISSIBLE``) **and** the
    delta does not expand the envelope (``envelope_not_expanded is True``). This fills
    liveauth's injected ``broker_capability_added`` expansion flag (``state.py:206``).
    Fail-closed: a deficient delta dimension, a non-current version, or an unproven
    envelope-not-expanded => ``False``.

    Args:
        profile: The Broker Capability Profile (``None`` => ``False``).
        delta_scope: The injected required-capability set for the enlarged scope.
        version_current: Whether the profile version is current (``None`` / ``False`` =>
            ``False``).
        envelope_not_expanded: Whether the delta stays within the existing envelope
            (``None`` / ``False`` => ``False``).

    Returns:
        ``True`` iff the enlarged scope is fully covered and the envelope is not expanded.
    """
    if envelope_not_expanded is not True:
        return False
    return (
        capability_admissible(
            profile, None, delta_scope, version_current=version_current
        )
        is Admissibility.ADMISSIBLE
    )


def active_profile_version(profile: BrokerCapabilityProfile | None) -> str | None:
    """The active profile version string, or ``None`` (design #10 §3.4 — scalar producer).

    Fills liveauth's injected ``broker_capability_profile_version`` scalar
    (``records.py:124``). ``None`` when the profile or its version block is absent
    (fail-closed downstream).

    Args:
        profile: The Broker Capability Profile.

    Returns:
        The immutable ``profile_version`` string, or ``None``.
    """
    if profile is None or profile.profile_version is None:
        return None
    return profile.profile_version.profile_version


def active_conformance_class(profile: BrokerCapabilityProfile | None) -> str | None:
    """The active conformance class as a scalar, or ``None`` (design #10 §3.4 — MINOR-2).

    Fills liveauth's injected ``broker_conformance_class`` scalar (``records.py:125``). The
    class is a **summary label only** — it never overrides a per-dimension admissibility
    decision (§10 line 584; the decision is :func:`capability_admissible`, which does not
    read the class).

    Args:
        profile: The Broker Capability Profile.

    Returns:
        The conformance class string, or ``None``.
    """
    if profile is None or profile.conformance_class is None:
        return None
    return profile.conformance_class.value


# ===========================================================================
# §5.3 — fallback monotone-restrictive
# ===========================================================================


def fallback_admissible(fallback: FallbackSpec | None) -> bool:
    """Whether an approved fallback is monotone-restrictive (ADR line 34; §13; §23.9).

    A fallback is admissible **only** when it does not increase capability: ``True`` iff
    ``widens_capability is False`` (it adds no capability the broker never guaranteed) AND
    ``conservative is True`` (smaller scope / serialize / contain / prohibit) AND
    ``tied_to_authority_and_risk_scope is True`` (ADR line 34). Every other case fails
    closed: a widening fallback (§23.9 "Unsupported Capability with No Scope Reduction ...
    Rejected"), a non-conservative one, an untied one, or **no** fallback (``None``) =>
    ``False`` (design #10 §4.2). A fallback never authorizes live behavior on its own — its
    ceiling is a ``REDUCED`` restricted-live scope whose approval is itself injected
    (design #10 §5.3).

    Args:
        fallback: The injected fallback specification (``None`` => ``False``).

    Returns:
        ``True`` iff the fallback is a legitimate conservative, non-widening fallback.
    """
    if fallback is None:
        return False
    return (
        fallback.widens_capability is False
        and fallback.conservative is True
        and fallback.tied_to_authority_and_risk_scope is True
    )


# ===========================================================================
# §5.4 — uncertain send / same-order retry (BC-INV-002/003)
# ===========================================================================


def uncertain_send_policy(
    idempotency_proven: bool | None = None,
    *,
    timeout_elapsed: bool | None = None,
) -> UncertainSendVerdict:
    """The restrictive policy for an outcome-unknown send (ADR §12.4 line 640-646; §1 line 43).

    Returns the all-restrictive :class:`~tos.brokercap.records.UncertainSendVerdict` ladder:
    no blind retry, no capacity release, no assume-rejection, no new conflicting order in
    containment, start reconciliation, enter UNKNOWN / CONTAINED. The verdict is
    **structurally** all-restrictive (a permissive combination is unrepresentable — design
    #10 §4.6), so neither an unproven idempotency nor an elapsed timeout can relax it: a
    timeout does **not** release capacity (ADR §1 line 43 "unresolved ambiguity remains
    UNKNOWN and cannot be released by timeout"; BC-INV-002/003).

    Args:
        idempotency_proven: Whether deterministic idempotency is proven (does not relax the
            ladder — retry admissibility is :func:`same_order_retry_allowed`).
        timeout_elapsed: Whether a local timeout elapsed (never releases; kept explicit to
            document the BC-INV-003 canary).

    Returns:
        The all-restrictive uncertain-send verdict.
    """
    del idempotency_proven, timeout_elapsed  # never relax the restrictive ladder
    return UncertainSendVerdict()


def same_order_retry_allowed(
    profile: BrokerCapabilityProfile | None,
    *,
    idempotency_proven_for_identity_and_window: bool | None = None,
) -> bool:
    """Whether the same order may be network-resent (ADR §12.5 line 650-652; BC-INV-002).

    ``True`` **only** when the profile's ``SUBMISSION_IDEMPOTENCY`` dimension is
    ``VERIFIED`` **and** ``idempotency_proven_for_identity_and_window is True`` — the
    profile proves deterministic idempotency for the exact request identity and retry
    window, so "retry cannot create a second broker order" (§12.5 line 652). Any
    ``UNKNOWN`` / unproven idempotency fails closed (``False``): no blind retry (§12.4 line
    640).

    Args:
        profile: The Broker Capability Profile (``None`` => ``False``).
        idempotency_proven_for_identity_and_window: Whether idempotency is proven for the
            exact identity + retry window (``None`` / ``False`` => ``False``).

    Returns:
        ``True`` iff a same-order resend cannot create a second broker order.
    """
    if profile is None:
        return False
    if idempotency_proven_for_identity_and_window is not True:
        return False
    declaration = profile.declaration_for(CapabilityDimension.SUBMISSION_IDEMPOTENCY)
    return declaration is not None and declaration.status is CapabilityStatus.VERIFIED


# ===========================================================================
# §5.5 — external detection / rate admission
# ===========================================================================


def external_detection_ok(
    detect_bound: int | None,
    contain_bound: int | None,
    observed_latency: int | None,
) -> bool:
    """Whether external activity is detected + contained within bounds (ADR §16; BC-INV-006).

    ``True`` **only** when all three are concrete and ``observed_latency`` is within
    **both** the injected detect bound and contain bound (design #10 §5.5). A missed bound
    => deny new risk (§16.3 line 907-910). Any ``None`` bound fails closed (design #10 §8 —
    the bounds are Verification-Profile values, never hardcoded).

    Args:
        detect_bound: The injected ``B_external_detect`` bound (``None`` => fail-closed).
        contain_bound: The injected ``B_external_contain`` bound (``None`` => fail-closed).
        observed_latency: The observed detection latency (``None`` => fail-closed).

    Returns:
        ``True`` iff the observed latency is within both bounds.
    """
    if detect_bound is None or contain_bound is None or observed_latency is None:
        return False
    return observed_latency <= detect_bound and observed_latency <= contain_bound


def rate_admission_ok(
    ordinary_below_ceiling: bool | None,
    protective_headroom_reserved: bool | None,
) -> bool:
    """Whether ordinary traffic admits below the protective headroom (ADR §17.2 line 926-933).

    ``True`` **only** when ordinary traffic is admitted **below** the reconciliation /
    protective headroom (``ordinary_below_ceiling is True``) **and** that headroom is
    reserved (``protective_headroom_reserved is True``). Ordinary traffic encroaching on
    protective headroom, or any ``None``, fails closed (design #10 §5.5; the numeric
    recovery bound ``B_rate_limit_recovery`` is injected, never hardcoded).

    Args:
        ordinary_below_ceiling: Whether ordinary traffic stays below the ceiling.
        protective_headroom_reserved: Whether protective / reconciliation headroom is
            reserved.

    Returns:
        ``True`` iff ordinary admission stays below reserved protective headroom.
    """
    return ordinary_below_ceiling is True and protective_headroom_reserved is True


# ===========================================================================
# §6.1 — profile version enforcement (liveauth broker_capability_current producer)
# ===========================================================================


def profile_version_current(
    active_version: str | None,
    presented_version: str | None,
    not_expired: bool | None,
    degraded_since_authorization: bool | None,
) -> bool:
    """Whether the presented profile version is current (ADR §7.2/§19; BC-INV-008; §6.1).

    ``True`` **only** when **all** positive conditions hold: ``active_version`` and
    ``presented_version`` are both concrete and **equal** (not stale / mismatched, §22 /
    §7.4), ``not_expired is True`` (§20.3 EXPIRED => revalidate), and
    ``degraded_since_authorization is False`` (§19 line 996 "capability has not degraded
    since authorization"; BC-INV-008). Every other case denies (fail-closed): a mismatch, a
    ``None`` version, an expired / ``None`` expiry, or a degraded / ``None`` degradation.
    This produced bool is the upstream of liveauth's ``broker_capability_current`` re-arm
    prerequisite (``predicates.py:137``; design #10 §3.4).

    Args:
        active_version: The active (approved) profile version (``None`` => deny).
        presented_version: The presented profile version (``None`` / mismatch => deny).
        not_expired: Whether the version has not expired (``None`` / ``False`` => deny).
        degraded_since_authorization: Whether capability degraded since authorization
            (``None`` / ``True`` => deny).

    Returns:
        ``True`` iff the presented version is current, unexpired, and undegraded.
    """
    if active_version is None or presented_version is None:
        return False
    if active_version != presented_version:
        return False
    if not_expired is not True:
        return False
    return degraded_since_authorization is False


# ===========================================================================
# §6.2 — capability drift (restrict-only)
# ===========================================================================

#: The §20.1 contradiction observation flags (line 1006-1016) — any one, when it concerns
#: the declaration's dimension, is a drift (design #10 §6.2).
_DRIFT_OBSERVATION_FLAGS: tuple[str, ...] = (
    "duplicate_order_despite_idempotency",
    "event_before_declared_impossible",
    "missing_sequence",
    "late_fill_beyond_window",
    "query_omission_beyond_bound",
    "unexpected_rate_limit",
    "session_behavior_change",
    "unknown_status_code",
    "unit_multiplier_mismatch",
)


def drift_detected(
    declaration: CapabilityDeclaration,
    observed: ObservedBehavior,
) -> bool:
    """Whether observed behavior contradicts a declaration (ADR §20.1 line 1006-1016; §6.2).

    ``True`` iff any §20.1 contradiction flag is observed **and** the observation concerns
    this declaration's dimension. A coherence guard (isomorphic to recon's field/confidence
    guard): an observation whose ``dimension`` is set but differs from the declaration's
    dimension is about **another** dimension and does not drift this one (``False``). No
    observation flag set => no drift.

    Args:
        declaration: The dimension's declaration.
        observed: The injected observed behavior.

    Returns:
        ``True`` iff a same-dimension contradiction is observed.
    """
    if (
        observed.dimension is not None
        and observed.dimension is not declaration.dimension
    ):
        return False
    return any(getattr(observed, flag) for flag in _DRIFT_OBSERVATION_FLAGS)


def apply_drift(
    declaration: CapabilityDeclaration,
    observed: ObservedBehavior,
) -> CapabilityDeclaration:
    """Apply drift restrictively — never widen (ADR §20.2 line 1022; §7.5; §4.3).

    When :func:`drift_detected`, returns a **new** declaration with ``status`` moved to
    ``CONTRADICTORY`` (§20.2 "mark affected dimension CONTRADICTORY") and ``assurance_level``
    lowered to ``LEVEL_0_UNKNOWN`` — a strictly **restrictive** move. There is **no** branch
    that raises status or level (widen is structurally impossible; design #10 §4.3): a
    would-be "the broker is better than declared" observation cannot lift the status. With
    no drift, the declaration is returned unchanged (no unnecessary restriction).

    Args:
        declaration: The dimension's current declaration.
        observed: The injected observed behavior.

    Returns:
        The declaration moved to ``CONTRADICTORY`` / ``LEVEL_0_UNKNOWN`` on drift, else the
        unchanged declaration.
    """
    if not drift_detected(declaration, observed):
        return declaration
    return declaration.model_copy(
        update={
            "status": CapabilityStatus.CONTRADICTORY,
            "assurance_level": AssuranceLevel.LEVEL_0_UNKNOWN,
        }
    )


# ===========================================================================
# §6.3 — Final Quantity Proof recipe (recon / orthostate FQP producer)
# ===========================================================================

#: The §15.2 required-result conjuncts (line 843-851) — each must be positively ``True``
#: for a Final Quantity Proof to be adequate (design #10 §6.3).
_FQP_REQUIRED_CONJUNCTS: tuple[str, ...] = (
    "broker_order_identity_or_bounded_effect",
    "final_cumulative_filled_quantity",
    "zero_remaining_executable_quantity",
    "corrections_busts_late_events_handled",
    "evidence_source_provenance",
    "within_valid_window",
    "ordering_waiting_rule_satisfied",
)


def fqp_adequate(
    rule: FinalQuantityProofRule,
    evidence: FinalQuantityEvidence,
) -> bool:
    """Whether a Final Quantity Proof is adequate (ADR §15.2/§15.3/§15.4; design #10 §6.3).

    ``True`` **only** when all of:

    * **no prohibited sole basis** — ``evidence.sole_prohibited_basis is None`` (a proof
      resting solely on any §15.3 prohibited basis — cancel-ack / one-query-omission /
      local-timeout / strategy-cancellation-intent / process-restart / position-match /
      operator-assertion — is inadequate; design #10 §6.3);
    * **§15.4 terminal event defined** — the rule asserts ``no_later_change_asserted is
      True`` **or** ``late_event_window_defined is True`` (a stronger terminal event is
      accepted only when the profile explicitly asserts no later change *or* defines bounded
      correction handling; unspecified => inadequate);
    * **all §15.2 required conjuncts** are positively ``True`` (final cumulative filled
      quantity, zero remaining, corrections/late-events handled, provenance, valid window,
      ordering/waiting rule, broker-order-identity-or-bounded-effect).

    Every other case fails closed. brokercap produces only this ``bool`` — it performs no
    conservative-bound merge (that is recon's, design #10 §3.5). This bool is the upstream
    of recon's ``final_quantity_proof_token`` and orthostate's
    ``final_quantity_proof_where_broker_involved`` (design #10 §3.4).

    Args:
        rule: The profile-declared Final Quantity Proof recipe.
        evidence: The injected observed Final Quantity evidence bundle.

    Returns:
        ``True`` iff the proof meets §15.2, defines a §15.4 terminal event, and rests on no
        prohibited sole basis.
    """
    if evidence.sole_prohibited_basis is not None:
        return False
    if not (
        rule.no_later_change_asserted is True or rule.late_event_window_defined is True
    ):
        return False
    return all(
        getattr(evidence, conjunct) is True for conjunct in _FQP_REQUIRED_CONJUNCTS
    )


# ===========================================================================
# §6.4 — environment binding / credential scope
# ===========================================================================


def environment_binding_ok(
    evidence_environment: str | None,
    scope_environment: str | None,
    inherited: bool | None,
) -> bool:
    """Whether evidence binds to the scope's environment (ADR §18.4/§13.14; BC-INV-009; §6.4).

    ``True`` **only** when ``evidence_environment`` and ``scope_environment`` are both
    concrete and **equal** and ``inherited is False`` (not cross-environment inheritance).
    BC-INV-009 (line 223 verbatim): "Sandbox or paper capability evidence SHALL NOT
    automatically establish live capability" — so cross-environment evidence (a mismatch, or
    ``inherited is True``) fails closed, as does any ``None`` (design #10 §6.4). The
    runtime-security proof that a stale identity cannot bypass egress is +Security
    (ADR-002-013) — not-Phase-1 (design #10 §1).

    Args:
        evidence_environment: The evidence's environment coordinate (``None`` => deny).
        scope_environment: The scope's environment coordinate (``None`` / mismatch => deny).
        inherited: Whether the capability was inherited across environments (``None`` /
            ``True`` => deny).

    Returns:
        ``True`` iff the evidence binds to the same, non-inherited environment.
    """
    if evidence_environment is None or scope_environment is None:
        return False
    if evidence_environment != scope_environment:
        return False
    return inherited is False


def credential_scope_declared_ok(
    profile: BrokerCapabilityProfile | None,
    requested_scope: str | None,
) -> bool:
    """Whether the requested credential scope is within the declared scope (ADR §18.2; §6.4).

    A coordinate-level check: ``True`` **only** when the profile declares a concrete
    ``credential_scope`` (in its ``profile_key``), ``requested_scope`` is concrete, and they
    match. Any ``None`` (undeclared or unspecified request) fails closed (design #10 §6.4).
    The runtime credential-fencing / egress-bypass resistance is +Security (ADR-002-013) —
    not-Phase-1.

    Args:
        profile: The Broker Capability Profile (``None`` => ``False``).
        requested_scope: The requested credential scope (``None`` => ``False``).

    Returns:
        ``True`` iff the requested credential scope matches the declared scope.
    """
    if profile is None or profile.profile_key is None or requested_scope is None:
        return False
    declared = profile.profile_key.credential_scope
    return declared is not None and declared == requested_scope


# ===========================================================================
# §6.5 — §13.15 composed-consequence: partition-protective class (broker-agnostic)
# ===========================================================================


def partition_protective_class(
    single_serialized_channel: bool | None,
    no_rapid_revocation: bool | None,
    shared_global_rate_limit: bool | None,
) -> bool:
    """Whether the three §13.15 weaknesses coincide (ADR §13.15 line 796; design #10 §6.5).

    ``True`` **only** when all three composed weaknesses hold simultaneously: a single
    serialized / HOL-blocking channel (§13.11), no broker-side rapid session/credential
    revocation (§13.12), and a shared global account rate limit (§13.10). This is a pure
    capability-**class** judgment over injected conditions (the three declarations' status /
    fallback are folded by the caller) — it names **no** concrete broker (ADR line 798).
    Any ``None`` fails closed (not the dangerous class => ``False``, which is safe: the
    scope predicate then imposes no partition reduction requirement).

    Args:
        single_serialized_channel: Whether the channel is single serialized / HOL-blocking.
        no_rapid_revocation: Whether broker-side rapid revocation is absent.
        shared_global_rate_limit: Whether a shared global account rate limit applies.

    Returns:
        ``True`` iff all three composed weaknesses coincide.
    """
    return (
        single_serialized_channel is True
        and no_rapid_revocation is True
        and shared_global_rate_limit is True
    )


def partition_class_scope_ok(
    profile: BrokerCapabilityProfile | None,
    *,
    single_serialized_channel: bool | None,
    no_rapid_revocation: bool | None,
    shared_global_rate_limit: bool | None,
) -> bool:
    """Whether a partition-protective profile's scope is adequately reduced (ADR §13.15).

    When the profile is **not** in the composed partition-protective class
    (:func:`partition_protective_class` ``False``), returns ``True`` — no partition
    reduction is required. When it **is** in that class, returns ``True`` **only** when the
    profile is classified ``CLASS_C`` / ``CLASS_D`` **or** its live scope is reduced off
    unattended partition-time autonomous protection
    (``live_scope.reduced_off_unattended_partition_protection is True``) — §13.15 line 796
    "SHALL either reduce live scope ... or be classified CLASS-C / CLASS-D". A
    partition-protective-class profile that is ``CLASS_A`` / ``CLASS_B`` with an unreduced
    scope fails closed (``False`` => the caller prohibits). A ``None`` profile fails closed.

    Args:
        profile: The Broker Capability Profile (``None`` => ``False``).
        single_serialized_channel: Whether the channel is single serialized / HOL-blocking.
        no_rapid_revocation: Whether broker-side rapid revocation is absent.
        shared_global_rate_limit: Whether a shared global account rate limit applies.

    Returns:
        ``True`` iff the profile is not partition-protective, or is adequately reduced /
        supervised.
    """
    if profile is None:
        return False
    if not partition_protective_class(
        single_serialized_channel, no_rapid_revocation, shared_global_rate_limit
    ):
        return True
    if profile.conformance_class in NON_LIVE_OR_SUPERVISED_CLASSES:
        return True
    return (
        profile.live_scope is not None
        and profile.live_scope.reduced_off_unattended_partition_protection is True
    )


# ===========================================================================
# §3.4 — orthostate BROKER_ORDER producer (bool -> caller maps to enum-basis)
# ===========================================================================


def broker_evidence_admissible_under_profile(
    profile: BrokerCapabilityProfile | None,
    evidence_ref: BrokerEvidenceRef | None,
    required: RequiredCapabilitySet | None,
    *,
    version_current: bool | None = None,
) -> bool:
    """Whether broker evidence establishes a definite BROKER_ORDER state (design #10 §3.4).

    ``True`` **only** when the broker evidence is concrete (``evidence_ref`` has an
    ``evidence_id`` or ``digest``) **and** the relevant capability is admissible under the
    profile (:func:`capability_admissible` ``ADMISSIBLE``). This is the upstream of the
    orthostate BROKER_ORDER dimension: the caller maps a ``True`` to
    ``ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE`` (a strong basis that alone may
    reduce ``conservative_direction_ok`` from ``UNKNOWN`` to a definite state), and a
    ``False`` to ``None`` (a weak / absent basis that blocks the reduction, fail-closed —
    orthostate ``predicates.py:352-355``). "Established only from broker/venue evidence
    under Broker Capability Profile; no internal component sets from assumption" (ADR-002-005
    §7 line 104). Any missing evidence or non-admissible capability fails closed.

    Args:
        profile: The Broker Capability Profile (``None`` => ``False``).
        evidence_ref: The injected broker-evidence reference (empty => ``False``).
        required: The injected required-capability set for the broker-order-relevant
            capability.
        version_current: Whether the profile version is current (``None`` / ``False`` =>
            ``False``).

    Returns:
        ``True`` iff concrete broker evidence establishes a definite state under an
        admissible profile.
    """
    if evidence_ref is None:
        return False
    if evidence_ref.evidence_id is None and evidence_ref.digest is None:
        return False
    return (
        capability_admissible(profile, None, required, version_current=version_current)
        is Admissibility.ADMISSIBLE
    )
