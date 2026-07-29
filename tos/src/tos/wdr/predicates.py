"""wdr safety-deviation predicates (design #26 §5/§6/§6b) — pure, fail-closed.

Pure decision rules over injected frozen models (design #26 §0.2/§4): wdr authors the **boundary /
scope / UNKNOWN / status / set / gate structural substrate** — the five yolk predicates
(:func:`boundary_denies_non_waivable` — WDR-EV-001; :func:`scope_exact_and_complete` — WDR-EV-002;
:func:`unknown_denies_and_confines` — WDR-EV-007; :func:`evidence_status_honest` — WDR-EV-010;
:func:`combined_set_no_permissive_union` + :func:`gate_states_separated` — WDR-EV-012) and their
supporting predicates, plus the predicate-only §6 substrate and the not-Phase-1 §6b thin revocation
send-race model. It **re-authors none** of the sibling instances it consumes: spg owns the
Hard Safety Envelope / ``residual_risk_ceiling`` / break-before-make; hag owns the effective-principal
collapse + quorum; rcl owns the ``CapacityVector`` + worst-credible-effect; egress owns final-egress
enforcement; cur owns the Safety Currentness Vector; evidence owns custody / causal-chain / gap; liveauth
owns the Live Authorization; iap owns the single-use consumption shape; authority owns the epoch floor +
non-revival; and -027 incident generation is sibling-owned (injected opaque coordinate). wdr **consumes**
every produced fact as an **injected scalar / bool / verdict / digest / generation** and re-authors none
of them (sibling edge 0, §3.5).

**The two boundaries (design #26 §1 — wdr's twin maximum risks are opposite).** (1) **over-
realization**: the §12 independent effective-person review + quorum, the §14 per-action final-egress
currentness binding, the §14 revocation / expiry send-race, the §11 worst-credible-effect computation,
the §11 compensating-control effectiveness verification, the §13 break-before-make configuration
activation, the §8/§11 Hard Safety Envelope containment, the §19 evidence assembly / custody integrity,
and the §7 Live Authorization issuance are **all human / runtime / +Security / +Broker / sibling-owned**
— L1 owns only boundary / scope / UNKNOWN / status / set / gate structural judgement over injected
coordinates. (2) **duplication**: the sibling owners' *business content* is **never** re-decided here
(§3.5) — wdr consumes each owner verdict / generation / digest and judges only the deviation-governance
structure.

**Truthy-sentinel discipline (design #26 §4.2).** ``DecisionResult`` / ``NonWaivableClassification`` /
``WaivedEvidenceStatus`` are truthy-untestable ``StrEnum``s (``__bool__`` raises), so every gate uses
``x is ENUM.SAFE_VALUE``; a bare ``if result:`` would fail open reading a denial / non-permissive member
as a go.

**Polarity discipline (design #26 §4.3 — #18/#22 MAJOR-2 seal).** Every ``bool | None`` field declares a
polarity and is normalized with ``is True`` / ``is False`` (**never** ``is not True`` on a
negative-polarity field — that admits a ``None`` and re-opens the #18/#22 fail-open). A ``None`` is
UNKNOWN and converges to **deny** on both polarities. Positive-polarity fields
(``applicability_resolved`` / ``effective_principal_verdict`` / ``within_hard_safety_envelope`` /
``is_complete`` / the compensating-control ``is_preventive_or_containment`` etc.) admit only on ``is
True``; negative-polarity fields (``single_use_consumed`` / the UNKNOWN flags / ``materiality_unknown`` /
``scope_wildcard`` / ``observation_only`` / ``re_armed`` etc.) admit only on ``is False``.

**Group reconcile discipline (design #26 §4.4 — #22 MAJOR-1 seal).** The combined Active Deviation Set
reconciles **all** members conservatively, never the first: :func:`combined_set_no_permissive_union` is
no-permissive-union (any omitted applicable deviation invalidates; the completeness is both-ways;
member = applicable), order-independent. The §13 line 364 explicit-empty set (applicable = ∅, members =
∅, is_complete = True) is **valid** — a no-deviation bundle's canonical representation, never rejected
(design #26 v1.1 MAJOR-1).

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.wdr.*`` (records / state / vocabulary /
_base) only; no ``shared.*``, no other sibling ``tos.*`` (design #26 §0.3). Clock-free.
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.wdr._base import AllFalseDeviationAuthority
from tos.wdr.records import (
    ActiveDeviationSet,
    SafetyDeviationDecision,
    SafetyDeviationRequest,
)
from tos.wdr.state import (
    CompensatingControl,
    DeviationClassification,
    GateSeparationLadder,
    NonWaivableBoundaryAnchor,
    WaivedEvidenceItem,
)
from tos.wdr.vocabulary import (
    MANDATED_SCOPE_FLOOR,
    MEASURED_FAILURE_STATUSES,
    DecisionResult,
    NonWaivableClassification,
    ScopeDimension,
    WaivedEvidenceStatus,
)

__all__ = [
    # core §5 — the five yolk predicates + supporting
    "classification_admissible",
    "boundary_is_union_only",
    "unresolved_is_non_waivable",
    "boundary_denies_non_waivable",
    "no_wildcard_scope",
    "no_scope_drift",
    "dependency_closure_complete",
    "scope_exact_and_complete",
    "budget_is_not_capacity",
    "protective_label_no_bypass",
    "unknown_denies_and_confines",
    "approval_is_not_verification",
    "evidence_status_honest",
    "omitted_deviation_invalidates",
    "combined_set_no_permissive_union",
    "no_status_implication",
    "readiness_not_authority",
    "gate_states_separated",
    # predicate-only §6 substrate (≥ L2 — closes NO WDR-EV)
    "all_false_deviation_authority",
    "compensating_control_not_observation",
    "independent_effective_person_approval",
    "deviation_single_use_non_authorizing",
    "broker_finality_unchanged",
    "economic_effect_persists",
    "expiry_recovery_revives_nothing",
    "break_glass_no_authority",
    "deviation_service_no_route",
    # not-Phase-1 thin model §6b (WDR-EV-006 substrate — runtime race residue)
    "revocation_dominates_send",
    "attempt_potentially_live",
]


# ===========================================================================
# core §5.1 — boundary_denies_non_waivable yolk + supporting (WDR-EV-001 substrate)
# ===========================================================================


def classification_admissible(classification: DeviationClassification | None) -> bool:
    """Whether a requirement is positively classified waivable-eligible (§5.1; §8 line 252; truthy-seal).

    ``True`` **only** when the classification exists and (i) ``classification is
    NonWaivableClassification.WAIVABLE_ELIGIBLE`` — the mandated explicit positive-identity gate (a bare
    ``if classification:`` would fail open on the truthy ``NON_WAIVABLE`` / ``UNRESOLVED`` strings; §8
    line 252 "unresolved ... treated as non-waivable"), (ii) ``applicability_resolved is True``
    (positive polarity — §9 line 273 "Unknown applicability ... denies"; ``None`` / ``False`` deny), and
    (iii) **no** §8 boundary hit (``not boundary_hits``). A ``None`` classification ⇒ ``False``.

    Args:
        classification: The §8 classification-input view (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the requirement is positively classified waivable-eligible with no boundary hit.
    """
    if classification is None:
        return False
    if classification.classification is not NonWaivableClassification.WAIVABLE_ELIGIBLE:
        return False
    if classification.applicability_resolved is not True:
        return False
    return not classification.boundary_hits


def unresolved_is_non_waivable(
    classification: NonWaivableClassification | None,
) -> bool:
    """Whether a classification is treated as non-waivable (§8 line 252; §5.1 supporting).

    ``True`` (⇒ non-waivable, deny) for **every** value except
    ``NonWaivableClassification.WAIVABLE_ELIGIBLE`` — ``NON_WAIVABLE``, ``UNRESOLVED``, and a ``None``
    classification all converge to non-waivable (§8 line 252 "If requirement identity or applicability
    is unresolved, it is treated as **non-waivable**"). The truthy-untestable enum forces the explicit
    identity comparison.

    Args:
        classification: The classification value (``None`` ⇒ non-waivable).

    Returns:
        ``True`` iff the requirement is non-waivable (only ``WAIVABLE_ELIGIBLE`` is waivable).
    """
    return classification is not NonWaivableClassification.WAIVABLE_ELIGIBLE


def boundary_is_union_only(boundary: NonWaivableBoundaryAnchor | None) -> bool:
    """Whether the boundary carries the full 15-item union floor, unshrunk (§5.6/§8 line 250).

    ``True`` **only** when the boundary exists and **every** one of the 15 §8 line 234-248 items is
    declared present (:meth:`~tos.wdr.state.NonWaivableBoundaryAnchor.is_complete`) — §5.6 "Policy may
    add prohibitions but **cannot make this list smaller**." A boundary that dropped any of the 15 is a
    shrunk / forged boundary and denied (any-add-wins union floor; §4.4). A ``None`` boundary ⇒
    ``False``.

    Args:
        boundary: The non-waivable boundary anchor (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the boundary declares the complete 15-item union (unshrunk).
    """
    if boundary is None:
        return False
    return boundary.is_complete()


def boundary_denies_non_waivable(
    request: SafetyDeviationRequest | None,
    boundary: NonWaivableBoundaryAnchor | None,
) -> bool:
    """The yolk: whether a request is outside the non-waivable boundary (§5.1; WDR-EV-001 — NOT closed).

    Returns whether the request **may proceed** (is outside the boundary). ``True`` **only** when
    **all** of the following hold (AND, fail-closed):

    1. **∅-seal (both-ways)**: ``request`` and ``boundary`` are non-``None``, and the boundary declares
       the complete 15-item union — an absent / shrunk boundary is **never** vacuously permissive (§8
       line 234 "At minimum, no deviation may waive ..."). A boundary short of the 15-item anchor is a
       forged boundary ⇒ ``False``.
    2. **boundary union-only (§5.6)**: :func:`boundary_is_union_only` — the boundary is unshrunk.
    3. **classification admissible (§4.2 / §8 line 252)**: :func:`classification_admissible` over the
       request's ``classification_view()`` — ``WAIVABLE_ELIGIBLE`` with ``applicability_resolved is
       True`` and **no** §8 boundary hit; ``NON_WAIVABLE`` / ``UNRESOLVED`` / an unresolved
       applicability / any boundary hit deny.

    **WDR-EV-001 is NOT closed** — that row is ``EV-L1/3+Security`` and awaits ``/3`` integration +
    ``+Security`` classification-manipulation resistance (a "one person two accounts" boundary bypass is
    +Security runtime / hag; authoring is not acceptance, §1). The 15-item anchor is a
    manually-transcribed regression anchor (§7.2 drift; appendix C).

    Args:
        request: The Safety Deviation Request (``None`` ⇒ ``False``).
        boundary: The 15-item non-waivable boundary anchor (``None`` / shrunk ⇒ ``False``).

    Returns:
        ``True`` iff the request is positively outside the (complete, unshrunk) non-waivable boundary.
    """
    if request is None or boundary is None:
        return False
    if not boundary_is_union_only(boundary):
        return False
    return classification_admissible(request.classification_view())


# ===========================================================================
# core §5.2 — scope_exact_and_complete yolk + supporting (WDR-EV-002 substrate — cleanest L1)
# ===========================================================================


def no_wildcard_scope(request: SafetyDeviationRequest | None) -> bool:
    """Whether no scope dimension uses a wildcard / inferred / stale sentinel (§5.2; §10 line 299).

    ``True`` **only** when the request and its ``deviation_scope`` exist and **no** dimension is a
    (detectable) wildcard per :func:`~tos.wdr.state.is_wildcard_value` — a catalogued
    :data:`~tos.wdr.state.WILDCARD_SENTINELS` sentinel (case-insensitively), a
    :data:`~tos.wdr.state.WILDCARD_METACHARACTERS` glob / regex / ``LIKE`` metacharacter, or a
    whitespace-only blank (§10 line 299 "missing, wildcard, inferred, stale, conflicting ... is
    ineligible"). A ``None`` request / scope ⇒ ``False`` (fail-closed). **Best-effort, non-exhaustive**:
    the *patched* / *widened* / *stale* / *conflicting* axes are carried by the negative-polarity request
    flags and are +Security / runtime-owned, not value-model-decidable (§0.4 /
    :func:`~tos.wdr.state.is_wildcard_value`).

    Args:
        request: The Safety Deviation Request (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no scope dimension is a wildcard sentinel.
    """
    if request is None or request.deviation_scope is None:
        return False
    return not request.deviation_scope.wildcard_dimensions()


def no_scope_drift(request: SafetyDeviationRequest | None) -> bool:
    """Whether no scope-drift flag is set — every drift axis explicitly clear (§5.2; §10 line 299).

    ``True`` **only** when the request exists and **every** negative-polarity drift flag is ``is
    False`` — ``scope_wildcard`` / ``scope_patched`` / ``scope_widened`` / ``scope_stale`` /
    ``scope_conflicting`` (§10 line 299 "missing, wildcard, inferred, stale, conflicting, unbounded,
    wrong-environment, or post-review fields is ineligible"; WDR-INV-003). **Negative-polarity: only
    ``is False`` admits** — a ``None`` unknown-drift is denial, never a fail-open to "not drifted"
    (the #18/#22 MAJOR-2 seal; ``is not True`` is forbidden here).

    Args:
        request: The Safety Deviation Request (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every scope-drift flag is explicitly ``False``.
    """
    if request is None:
        return False
    return (
        request.scope_wildcard is False
        and request.scope_patched is False
        and request.scope_widened is False
        and request.scope_stale is False
        and request.scope_conflicting is False
    )


def dependency_closure_complete(request: SafetyDeviationRequest | None) -> bool:
    """Whether the §5.10 dependency closure is non-empty and positively complete (§5.2).

    ``True`` **only** when the request and its ``dependency_closure`` exist, the closure enumerates at
    least one affected coordinate (``affected_total()`` non-empty — a ∅ closure for a non-trivial
    deviation is denial, §10 line 287 / §5.10), **and** the injected positive-polarity
    ``closure_complete is True`` proof is present. **Honesty (§5.2)**: the *actual* completeness of the
    closure enumeration is a +Security / runtime judgement; this L1 slice checks only structural
    non-emptiness plus the positive completeness proof (``None`` / ``False`` ⇒ deny).

    Args:
        request: The Safety Deviation Request (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the closure is non-empty and positively proven complete.
    """
    if request is None or request.dependency_closure is None:
        return False
    closure = request.dependency_closure
    if not closure.affected_total():
        return False
    return closure.closure_complete is True


def scope_exact_and_complete(
    request: SafetyDeviationRequest | None,
    mandated_scope: frozenset[ScopeDimension],
) -> bool:
    """The yolk: whether a request binds an exact, complete reduced scope (§5.2; WDR-EV-002 — NOT closed).

    ``True`` **only** when **all** of the following hold (AND, fail-closed):

    1. **∅-seal (both-ways)**: ``request`` is non-``None``, ``mandated_scope`` is non-empty, and
       ``request.deviation_scope`` has a non-empty concrete set — an absent request / mandate / scope is
       **never** vacuously complete (§10 line 299 "A request with missing ... fields is ineligible").
    2. **every mandated dimension present + concrete (set both-ways)**: the effective mandate
       (``mandated_scope`` floored to at least :data:`~tos.wdr.vocabulary.MANDATED_SCOPE_FLOOR`, so a
       caller may require *more* but never fewer — the cur v1.1 MINOR-1 / rlp precedent) is a subset of
       the request's concrete dimensions. An unrepresented / wildcard dimension ⇒ incomplete (the egress
       QCC coexistence seal / spg ``bundle_complete`` precedent — a vacuous-True is blocked).
    3. **no wildcard / inferred / stale (§5.2)**: :func:`no_wildcard_scope`.
    4. **no scope drift (§4.3 negative polarity)**: :func:`no_scope_drift`.
    5. **dependency closure complete (§5.10)**: :func:`dependency_closure_complete`.
    6. **materiality / applicability conservative (§4.3)**: ``materiality_unknown is False`` (negative
       polarity — §9 line 273 "Unknown materiality is material") AND ``applicability_resolved is True``
       (positive polarity).

    **WDR-EV-002 is NOT closed** — that row is the cleanest ``EV-L1/3`` but integration (``/3``) is
    Phase-1-out (authoring is not acceptance, §1). **Exactness honesty (#25 MAJOR-1)**: the wildcard
    denylist is best-effort / non-exhaustive; novel wildcard notations and the patched / widened / stale
    / conflicting axes are +Security / runtime-owned (§0.4 / :func:`~tos.wdr.state.is_wildcard_value`).

    Args:
        request: The Safety Deviation Request (``None`` ⇒ ``False``).
        mandated_scope: The caller-supplied mandate (∅ ⇒ ``False``), floored to the §5.7 floor.

    Returns:
        ``True`` iff the request binds an exact, complete, non-drifted, closure-complete scope.
    """
    if request is None:
        return False
    if not mandated_scope:
        return False
    scope = request.deviation_scope
    if scope is None:
        return False
    concrete = scope.concrete_dimensions()
    if not concrete:
        return False
    effective = frozenset(mandated_scope) | MANDATED_SCOPE_FLOOR
    if not (effective <= concrete):
        return False
    if not no_wildcard_scope(request):
        return False
    if not no_scope_drift(request):
        return False
    if not dependency_closure_complete(request):
        return False
    if request.materiality_unknown is not False:
        return False
    return request.applicability_resolved is True


# ===========================================================================
# core §5.3 — unknown_denies_and_confines yolk + supporting (WDR-EV-007 substrate)
# ===========================================================================

#: The §16 line 423-431 UNKNOWN confinement flags (all negative-polarity — ``is not False`` ⇒ deny +
#: confine). A manually-transcribed anchor of ADR §16 line 423-431 / WDR-INV-010 line 182.
_UNKNOWN_FLAGS: tuple[str, ...] = (
    "broker_state_unknown",
    "order_state_unknown",
    "exposure_unknown",
    "residual_risk_unknown",
    "control_state_unknown",
    "evidence_unknown",
    "scope_unknown",
    "currentness_unknown",
    "materiality_unknown",
)


def budget_is_not_capacity(budget_authority: AllFalseDeviationAuthority | None) -> bool:
    """Whether the deviation budget confers no capacity — all-false (§5.3; §7 line 217).

    ``True`` **only** when the authority block exists and **every** flag is ``is False`` — a deviation
    budget / accepted residual risk is **never capacity** (§7 line 217 "deviation budget or accepted
    risk is never capacity"; §16 line 434 "accepted residual risk cannot free UNKNOWN capacity";
    WDR-INV-013). The worst-credible-effect envelope is an injected opaque rcl coordinate — the
    *computation* is rcl + +Broker (§0.4g), never re-authored here. A ``None`` block, or any non-``False``
    flag ⇒ ``False``.

    Args:
        budget_authority: The deviation budget's all-false authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the budget confers no capacity (every authority flag ``False``).
    """
    return all_false_deviation_authority(budget_authority)


def protective_label_no_bypass(request: SafetyDeviationRequest | None) -> bool:
    """Whether a protective label bypasses no safety check (§5.3; §11 line 331 / §17 line 442).

    ``True`` **only** when the request exists and ``protective_label_bypass is False`` (negative
    polarity — only an explicit ``False`` admits; ``None`` / ``True`` deny): a protective / exit / hedge
    / close / cancel / replace / recovery / emergency label does **not** bypass the Non-Waivable
    Boundary, venue, broker, economic, capacity, authority, or final-egress checks (§17 line 442), and
    protective priority does **not** create broker or RCL protective capacity (§11 line 331 "Protective
    priority does not create broker or RCL protective capacity").

    Args:
        request: The Safety Deviation Request (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no protective-label bypass is asserted.
    """
    if request is None:
        return False
    return request.protective_label_bypass is False


def unknown_denies_and_confines(
    request: SafetyDeviationRequest | None,
    budget_authority: AllFalseDeviationAuthority | None,
) -> bool:
    """The yolk: whether all state is known + budget≠capacity + protective≠bypass (§5.3; WDR-EV-007).

    Returns whether the request **may proceed** (all UNKNOWN confined). ``True`` **only** when **all**
    of the following hold (AND, fail-closed):

    1. **∅-seal**: ``request`` and ``budget_authority`` are non-``None``.
    2. **UNKNOWN exhaustive (§4.3 negative polarity — the core)**: **every** §16 line 423-431 UNKNOWN
       flag (:data:`_UNKNOWN_FLAGS` — broker / order / exposure / residual-risk / control / evidence /
       scope / currentness / materiality state) is ``is False``. **Any** flag ``is not False`` (``True``
       **or** ``None``) ⇒ deny + confine (§16 line 423 "Unknown ... blocks new risk"; WDR-INV-010).
       **Negative polarity: only ``is False`` admits** — a ``None`` unknown-state is denial, never a
       fail-open to "known" (the #18/#22 MAJOR-2 seal; ``is not True`` forbidden).
    3. **Unknown applicability (§4.3 positive polarity — INV-010 line 184)**:
       ``request.applicability_resolved is True``. WDR-INV-010 line 184 lists **"Unknown
       applicability"** first among the axes that block new risk; it is a *positive*-polarity axis
       (``None`` / ``False`` ⇒ deny) and so is not covered by the negative-polarity
       :data:`_UNKNOWN_FLAGS`. This gate makes the INV-010 Unknown-applicability axis explicit in the
       UNKNOWN yolk — **deliberately multi-layered** with the EV-001 boundary yolk
       (:func:`boundary_denies_non_waivable`) and the EV-002 scope yolk
       (:func:`scope_exact_and_complete`), which also require it, so the UNKNOWN yolk cannot pass on an
       unresolved applicability even when invoked standalone.
    4. **budget ≠ capacity (all-false; §7 line 217)**: :func:`budget_is_not_capacity`.
    5. **protective ≠ bypass (§11 line 331 / §17 line 442)**: :func:`protective_label_no_bypass`.

    **WDR-EV-007 is NOT closed** — that row is ``EV-L1/3+Broker``; the worst-credible-effect
    *quantification* + RCL capacity consumption is rcl + +Broker (§28 gate 8; authoring is not
    acceptance, §1).

    Args:
        request: The Safety Deviation Request (``None`` ⇒ ``False``).
        budget_authority: The deviation budget's all-false authority (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff applicability is resolved, all state is known, budget is not capacity, and no
        protective bypass is asserted.
    """
    if request is None or budget_authority is None:
        return False
    for flag in _UNKNOWN_FLAGS:
        if getattr(request, flag) is not False:
            return False
    if (
        request.applicability_resolved is not True
    ):  # INV-010 line 184 "Unknown applicability"
        return False
    if not budget_is_not_capacity(budget_authority):
        return False
    return protective_label_no_bypass(request)


# ===========================================================================
# core §5.4 — evidence_status_honest yolk + supporting (WDR-EV-010 substrate)
# ===========================================================================


def approval_is_not_verification(decision_result: DecisionResult | None) -> bool:
    """Whether an eligibility decision leaves the verification item unsatisfied (§5.4; §1 line 25).

    ``True`` **only** when ``decision_result is
    DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` — the decision is eligibility, **not**
    verification: "The affected verification item remains visibly incomplete or
    ``WAIVED_WITH_RESIDUAL_RISK``; it never becomes ``PASS``" (§1 line 25; WDR-INV-004). Even a positive
    eligibility does not convert an unmet / failed / missing verification item to ``PASS`` — this
    predicate only confirms the decision reached the eligibility gate; the honesty of the resulting
    status is :func:`evidence_status_honest`. A ``None`` / ``DENY`` / ``HOLD`` ⇒ ``False``.

    Args:
        decision_result: The decision result (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the decision is eligibility (which still is not verification).
    """
    return decision_result is DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION


def evidence_status_honest(item: WaivedEvidenceItem | None) -> bool:
    """The yolk: whether a covered item's status is honest — no deviation-driven PASS flip (§5.4; WDR-EV-010).

    ``True`` **only** when **all** of the following hold (AND, fail-closed):

    1. **∅-seal**: ``item`` is non-``None``.
    2. **no PASS relabel via deviation (§19 line 490; WDR-INV-004)**: if a deviation exists or is
       unknown (``deviation_exists is not False`` — negative polarity) the relabeled status may **not**
       be ``PASS`` — a deviation existing never flips an item to ``PASS`` (§19 line 490 "It SHALL NOT be
       relabeled ``PASS``, ``ACCEPTED``, or completed merely because a deviation exists").
    3. **measured failure visibility (§19 line 490)**: if ``measured_status`` is one of the §19
       measured-failure set (:data:`~tos.wdr.vocabulary.MEASURED_FAILURE_STATUSES` — NOT_IMPLEMENTED /
       FAIL / INCONCLUSIVE / BLOCKED / EXPIRED) then a ``relabeled_status`` (when present) may only be
       that same measured value or ``WAIVED_WITH_RESIDUAL_RISK`` — a historical failure stays visible
       (§19 line 490 "Historical failures ... remain visible").
    4. **WAIVED requires exact-current (§19 line 488)**: if ``measured_status is
       WAIVED_WITH_RESIDUAL_RISK`` then ``exact_current_decision_present`` AND ``reduced_scope_present``
       AND ``compensation_present`` AND ``review_record_present`` are **all** ``is True`` (positive
       polarity — a ``None`` / ``False`` on any denies the WAIVED claim).

    **WDR-EV-010 is NOT closed** — that row is ``EV-L1/3``; ``/3`` integration is Phase-1-out (authoring
    is not acceptance, §1). All status comparisons are explicit ``is`` (the truthy-untestable enum
    forbids ``if status:``, §4.2).

    Args:
        item: The waived verification-item view (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the item's status is honest (no deviation-driven PASS flip; WAIVED exact-current).
    """
    if item is None:
        return False
    # (2) no PASS relabel while a deviation exists / is unknown.
    if item.deviation_exists is not False:
        if item.relabeled_status is WaivedEvidenceStatus.PASS:
            return False
    # (3) a measured failure must stay visible — relabel only to itself or WAIVED.
    if item.measured_status in MEASURED_FAILURE_STATUSES:
        if item.relabeled_status is not None and item.relabeled_status not in (
            item.measured_status,
            WaivedEvidenceStatus.WAIVED_WITH_RESIDUAL_RISK,
        ):
            return False
    # (4) WAIVED_WITH_RESIDUAL_RISK requires the exact-current gate (positive polarity).
    if item.measured_status is WaivedEvidenceStatus.WAIVED_WITH_RESIDUAL_RISK:
        if not (
            item.exact_current_decision_present is True
            and item.reduced_scope_present is True
            and item.compensation_present is True
            and item.review_record_present is True
        ):
            return False
    return True


# ===========================================================================
# core §5.5 — combined_set_no_permissive_union + gate_states_separated (WDR-EV-012 substrate)
# ===========================================================================


def omitted_deviation_invalidates(
    active_set: ActiveDeviationSet | None,
    applicable_decision_ids: frozenset[str],
) -> bool:
    """Whether any applicable deviation is omitted / surplus from the set (§13 line 364; §4.4).

    Returns whether the set is **invalid by omission or surplus**. ``True`` (⇒ invalid) when the set
    exists and its ``member_decisions`` do **not** exactly equal the applicable set — an omitted
    applicable deviation, or a member not in the applicable set (surplus / conflicting), is invalid
    configuration (§13 line 364 "an omitted applicable deviation ... is invalid configuration"). Order-
    independent (set equality). A ``None`` set ⇒ ``True`` (absence is invalid, §13 line 364).

    Args:
        active_set: The Active Deviation Set (``None`` ⇒ invalid).
        applicable_decision_ids: The set of every applicable decision id.

    Returns:
        ``True`` iff the set omits an applicable deviation or carries a surplus member.
    """
    if active_set is None:
        return True
    members = frozenset(active_set.member_decisions)
    return members != frozenset(applicable_decision_ids)


def combined_set_no_permissive_union(
    active_set: ActiveDeviationSet | None,
    applicable_decision_ids: frozenset[str],
    member_within_envelope: bool | None,
) -> bool:
    """The yolk: whether the combined set is valid, complete, and non-union (§5.5; WDR-EV-012 — NOT closed).

    ``True`` **only** when **all** of the following hold (AND, fail-closed):

    1. **∅-seal (both-ways, v1.1 — §13 line 364 explicit-empty)**: ``active_set`` is non-``None`` (§13
       "Absence of the set ... is invalid") and ``is_complete is True`` (positive polarity — ``None`` /
       ``False`` ⇒ invalid config, §13 line 364). Then the empty cases:

       * ``applicable = ∅`` **and** ``members = ∅`` is a **valid explicit empty Active Deviation Set**
         (§13 line 364 "SHALL bind **either an explicit empty Active Deviation Set** or one complete
         canonical set" — a no-deviation bundle's canonical representation; **rejecting it is a defect**,
         design #26 v1.1 MAJOR-1);
       * ``members = ∅`` **and** ``applicable ≠ ∅`` ⇒ ``False`` (an applicable deviation is omitted);
       * ``applicable = ∅`` **and** ``members ≠ ∅`` ⇒ ``False`` (a surplus / conflicting member).
    2. **completeness both-ways (§13 line 364)**: ``member_decisions`` **exactly equals** the applicable
       set — an omitted applicable deviation or a surplus member is invalid
       (:func:`omitted_deviation_invalidates`; no-union / any-narrow-wins is order-independent, §4.4).
    3. **combined within envelope (spg-injected, positive polarity)**: ``member_within_envelope is
       True`` (§13 item 3; a ``None`` / ``False`` spg verdict denies). **spg-owned, re-authored not at
       all** (§0.4c).
    4. **generation present (§13 line 364)**: ``deviation_generation`` is non-``None`` (a mixed / absent
       generation is invalid; the MAX-generation fence at reconcile is §4.4).

    **WDR-EV-012 is NOT closed** — that row is ``EV-L1/3+Security``; ``/3`` integration + the
    ``+Security`` combined-risk-manipulation resistance are Phase-1-out (authoring is not acceptance,
    §1). This is the #22 MAJOR-1 no-permissive-union seal.

    Args:
        active_set: The Active Deviation Set (``None`` ⇒ ``False``).
        applicable_decision_ids: The set of every applicable decision id.
        member_within_envelope: The injected spg combined-envelope verdict (positive polarity; ``None``
            / ``False`` ⇒ ``False``).

    Returns:
        ``True`` iff the set is valid, complete (member = applicable, incl. the valid explicit-empty),
        combined-within-envelope, and generation-present.
    """
    if active_set is None:
        return False
    if active_set.is_complete is not True:
        return False
    if omitted_deviation_invalidates(active_set, applicable_decision_ids):
        return False
    if member_within_envelope is not True:
        return False
    return active_set.deviation_generation is not None


def no_status_implication(ladder: GateSeparationLadder | None) -> bool:
    """Whether every gate stage is explicit, none inferred from another (§5.5; §26 AC-012).

    ``True`` **only** when the ladder exists and **every** one of the six stages
    (:data:`~tos.wdr.state.GateSeparationLadder.STAGE_FIELDS`) is an **explicit** ``bool`` (``True`` or
    ``False``) — a ``None`` stage is an *inferred / implied* status, exactly the implication this seal
    forbids (§26 AC-012 line 687 "remain distinct states"; §12 line 358 / §13 line 378 a positive stage
    never implies another). Each stage is an independent injected bool, so a positive stage never
    structurally derives another — the ``None`` (inference) check is what a runtime predicate can
    enforce.

    Args:
        ladder: The gate-separation ladder (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every stage is an explicit bool (no inferred stage).
    """
    if ladder is None:
        return False
    return all(
        getattr(ladder, name) in (True, False)
        for name in GateSeparationLadder.STAGE_FIELDS
    )


def readiness_not_authority(ladder: GateSeparationLadder | None) -> bool:
    """Whether the ladder's readiness carries no authority (§5.5; WDR-INV-001; sbr readiness≠re-arm).

    ``True`` **only** when the ladder exists and its ``authority_effect`` is all-false
    (:func:`all_false_deviation_authority`) — ``restricted_live_ready`` / ``production_ready`` being
    ``True`` is a **status report**, not a permission (the sbr readiness ≠ re-arm precedent; §28 line
    752 "Acceptance of this governance mechanism accepts no specific deviation"). A ``None`` ladder /
    authority, or any non-``False`` authority flag ⇒ ``False``.

    Args:
        ladder: The gate-separation ladder (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff readiness confers no authority.
    """
    if ladder is None:
        return False
    return all_false_deviation_authority(ladder.authority_effect)


def gate_states_separated(ladder: GateSeparationLadder | None) -> bool:
    """The yolk: whether the six gate states are distinct and readiness ≠ authority (§5.5; WDR-EV-012).

    ``True`` **only** when **all** of the following hold (AND, fail-closed):

    1. **∅-seal**: ``ladder`` is non-``None``.
    2. **no implication (§5.5)**: :func:`no_status_implication` — every stage explicit, none inferred
       (``deviation_eligible ↛ configuration_activated / live_authorized``, ``configuration_activated ↛
       live_authorized``).
    3. **readiness ≠ authority (§5.5)**: :func:`readiness_not_authority` — readiness is a status report,
       never a permission.

    This extends the all-false-authority invariant to **status separation** (no gate truthy-implies
    another). **WDR-EV-012 is NOT closed** (see :func:`combined_set_no_permissive_union`).

    Args:
        ladder: The gate-separation ladder (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the six gate states are distinct and readiness confers no authority.
    """
    if ladder is None:
        return False
    if not no_status_implication(ladder):
        return False
    return readiness_not_authority(ladder)


# ===========================================================================
# predicate-only §6 substrate (≥ L2 — closes NO WDR-EV)
# ===========================================================================


def all_false_deviation_authority(authority: AllFalseDeviationAuthority | None) -> bool:
    """Whether an authority block confers nothing — every flag ``False`` (§6; WDR-INV-001).

    ``True`` **only** when the block exists and **every** flag is ``is False`` (creates_capacity /
    creates_protection / creates_safety_authority / issues_live_authorization / creates_capability /
    transmits / clears_halt / creates_production_scope / re_arms / grants_broker_permission /
    classifies_protection). A ``None`` block, or any non-``False`` flag ⇒ ``False`` (fail-closed). The
    construction-time validator already rejects any ``True`` flag; this predicate re-derives the
    all-false property so a ``model_construct`` bypass cannot smuggle a permissive block past a consumer
    (defence in depth, §2.3). WDR-INV-001: a deviation artifact is governed content / a non-authorizing
    decision, not permission.

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


def compensating_control_not_observation(control: CompensatingControl | None) -> bool:
    """Whether a compensating control is a real preventive / containment mechanism (§6.1; WDR-EV-003·+Security).

    ``True`` **only** when the control exists and (all AND, fail-closed): ``observation_only is False``
    (negative polarity — only explicit ``False`` admits; a ``None`` / ``True`` is not-a-control),
    ``is_preventive_or_containment is True``, ``objective_evidence is True``, ``fails_closed is True``,
    and ``independent_of_failed_control is True`` (all positive polarity; §11 item 1/3/4/5). A document /
    alert / dashboard / audit / replay / priority label / operator promise / monitoring is **not by
    itself** a compensating control (§5.5; §11 item 8; WDR-INV-005 "Observation alone is insufficient").
    The real independence verification is +Security. Predicate-only substrate: ``EV-L2/3+Security``,
    closes **no** WDR-EV.

    Args:
        control: The compensating control (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the control is a real preventive / containment mechanism, not observation.
    """
    if control is None:
        return False
    return (
        control.observation_only is False
        and control.is_preventive_or_containment is True
        and control.objective_evidence is True
        and control.fails_closed is True
        and control.independent_of_failed_control is True
    )


def independent_effective_person_approval(
    authority: AllFalseDeviationAuthority | None,
    effective_principal_verdict: bool | None,
    common_mode_present: bool | None,
) -> bool:
    """Whether the approval is independent + non-authorizing (§6.2; §12/§7; WDR-EV-004·+Security).

    ``True`` **only** when (all AND, fail-closed): the deviation ``authority`` block is all-false
    (:func:`all_false_deviation_authority` — the SoD structural declaration that a requester /
    control-owner / beneficiary / implementer / evidence-producer / live-armer holds no RCL / egress
    authority, no live-order credential / route; §7 line 224), ``effective_principal_verdict is True``
    (positive polarity — the **hag-injected** effective-principal-independence verdict, re-authored not
    at all; §0.4e / WDR-INV-007 line 170), and ``common_mode_present is False`` (negative polarity — a
    common-mode dependence denies; §11/§12). The effective-principal **collapse** + **quorum** counting
    is hag-owned (§0.4e). The real independence is hag verdict + +Security. Predicate-only substrate:
    ``EV-L2/3+Security``, closes **no** WDR-EV.

    Args:
        authority: The deviation artifact's all-false authority block (``None`` ⇒ ``False``).
        effective_principal_verdict: The hag-injected independence verdict (positive polarity; ``None`` /
            ``False`` ⇒ ``False``).
        common_mode_present: The negative-polarity common-mode flag (``True`` / ``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the approval is structurally independent + non-authorizing.
    """
    if not all_false_deviation_authority(authority):
        return False
    if effective_principal_verdict is not True:
        return False
    return common_mode_present is False


def deviation_single_use_non_authorizing(
    decision: SafetyDeviationDecision | None,
) -> bool:
    """Whether a decision is single-use, eligible, and non-authorizing (§6.3; §13/§7; WDR-EV-005·+Security).

    ``True`` **only** when (all AND, fail-closed): ``decision.single_use_consumed is False`` (negative
    polarity — a consumed / ``None``-unknown decision is reject-reuse; §13 line 368 "consumed exactly
    once"; §4.3), ``decision.result is DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` (§4.2 — the
    explicit positive gate; ``DENY`` / ``HOLD`` deny), and ``all_false_deviation_authority(decision.
    authority_effect)`` (activation / capacity / authority / transmit / re-arm all withheld; §6.2). This
    **REUSES the iap single-use consumption shape** (not an import — §0.4h; §13 line 368 / WDR-INV-008
    isomorph). The real registry replay / generation-fence enforcement is +Security. Predicate-only
    substrate: ``EV-L2/3+Security``, closes **no** WDR-EV.

    Args:
        decision: The Safety Deviation Decision (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the decision is fresh (single-use), eligible, and non-authorizing.
    """
    if decision is None:
        return False
    if decision.single_use_consumed is not False:
        return False
    if decision.result is not DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION:
        return False
    return all_false_deviation_authority(decision.authority_effect)


def broker_finality_unchanged(
    broker_state_unknown: bool | None,
    order_state_unknown: bool | None,
) -> bool:
    """Whether broker finality is unchanged — missing-ACK is not non-acceptance (§6.4; WDR-EV-008·+Broker).

    ``True`` **only** when ``broker_state_unknown is False`` **and** ``order_state_unknown is False``
    (both negative polarity — only explicit ``False`` admits; a ``None`` / ``True`` unknown broker /
    order state denies). A missing ACK is **not** proof of non-acceptance and a Cancel-ACK is **not**
    Final Quantity Proof (§16 line 428-429; WDR-INV-011 line 186 "Missing ACK is not proof of
    non-acceptance. Cancel ACK is not Final Quantity Proof"): an unknown broker / order state is
    conservatively potentially-live, never cleared. The real broker-finality quantification is +Broker.
    Predicate-only substrate: ``EV-L2/3+Broker``, closes **no** WDR-EV.

    Args:
        broker_state_unknown: The negative-polarity broker-state flag (``True`` / ``None`` ⇒ ``False``).
        order_state_unknown: The negative-polarity order-state flag (``True`` / ``None`` ⇒ ``False``).

    Returns:
        ``True`` iff both broker and order state are positively known (finality unchanged).
    """
    return broker_state_unknown is False and order_state_unknown is False


def economic_effect_persists(authority: AllFalseDeviationAuthority | None) -> bool:
    """Whether the economic effect persists across a deviation terminal (§6.4; WDR-INV-012; afg/are shape).

    ``True`` **only** when the authority exists and neither ``creates_capacity`` nor
    ``classifies_protection`` is non-``False`` — a request withdrawal / decision expiry / revocation /
    active-set change / profile rollback / authorization expiry **cannot** erase positions, orders,
    attempts, fills, external activity, obligations, or capacity (WDR-INV-012 line 190); the economic
    effect therefore persists regardless of the terminal state. Isomorphic to the afg / are / capsule
    ``terminal_release_proven`` shape. Predicate-only substrate: ``EV-L2/3+Broker``, closes **no**
    WDR-EV.

    Args:
        authority: The deviation artifact's authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the economic effect persists (no capacity release / protection reclassification).
    """
    if authority is None:
        return False
    return (
        authority.creates_capacity is False and authority.classifies_protection is False
    )


def expiry_recovery_revives_nothing(
    re_armed: bool | None,
    self_reverted: bool | None,
    recovered_without_fresh_chain: bool | None,
) -> bool:
    """Whether expiry / recovery / restriction revives nothing (§6.5; §15/§18; WDR-INV-014/015).

    ``True`` **only** when (all AND, fail-closed): ``re_armed is False`` **and** ``self_reverted is
    False`` **and** ``recovered_without_fresh_chain is False`` — all negative polarity (only an explicit
    ``False`` admits; a ``None`` / ``True`` denies). There is no automatic renewal / grace-period /
    rolling extension / silent predecessor restoration (§15 line 417); recovery revives nothing (§18
    line 469-476; WDR-INV-014) and a restriction never self-reverts to a predecessor configuration
    (WDR-INV-015 line 202 "It never automatically restores a predecessor configuration"). A prior
    decision / profile / active-set is INVALIDATED and a fresh full governance chain is required (§15
    line 415 / §18 line 473). Isomorphic to the authority ``recovery_generation_revives_nothing`` / cur
    ``recovery_revives_nothing`` shape (REUSE not import; §0.4h). The real hard-fence is +Security.
    Predicate-only substrate: ``EV-L2/3+Security``, closes **no** WDR-EV.

    Args:
        re_armed: The negative-polarity re-arm flag (``True`` / ``None`` ⇒ ``False``).
        self_reverted: The negative-polarity self-revert flag (``True`` / ``None`` ⇒ ``False``).
        recovered_without_fresh_chain: The negative-polarity recovery flag (``True`` / ``None`` ⇒
            ``False``).

    Returns:
        ``True`` iff nothing was re-armed, self-reverted, or recovered without a fresh chain.
    """
    return (
        re_armed is False
        and self_reverted is False
        and recovered_without_fresh_chain is False
    )


def break_glass_no_authority(authority: AllFalseDeviationAuthority | None) -> bool:
    """Whether break-glass confers no authority — HALT / deny / narrow only (§6.6; §17; WDR-EV-011·+Broker+Security).

    ``True`` **only** when the authority block exists and is all-false
    (:func:`all_false_deviation_authority`) — break-glass may request only HALT / deny / narrow /
    separately-authorized containment; it may **not** approve or activate a deviation, expand profile
    scope, mutate or release capacity, classify protective, obtain a broker credential, transmit, clear
    UNKNOWN / HALT, or re-arm (§17 line 444-453 8-item all-false). A ``None`` / non-all-false block ⇒
    ``False``. The real security boundary (alternate route / external portal) is +Broker+Security.
    Predicate-only substrate: ``EV-L2/3+Broker+Security``, closes **no** WDR-EV.

    Args:
        authority: The break-glass authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff break-glass confers no authority (restrictive-only).
    """
    if authority is None:
        return False
    return all_false_deviation_authority(authority)


def deviation_service_no_route(authority: AllFalseDeviationAuthority | None) -> bool:
    """Whether a deviation service holds no live-order route / credential (§6.6; §7 line 224; WDR-INV-013).

    ``True`` **only** when the authority block exists and is all-false
    (:func:`all_false_deviation_authority`) — a deviation registry / evaluator / workflow / dashboard /
    ticketing / residual-risk service holds **no** usable live-order credential, signer, session, or
    route (§7 line 224; WDR-INV-013 line 194 "Deviation services hold neither authority"). This is the
    **rcl edge 0** corollary — a deviation service is not RCL and not egress (§0.4g). A ``None`` /
    non-all-false block ⇒ ``False``. The real security boundary is +Broker+Security. Predicate-only
    substrate: ``EV-L2/3+Broker+Security``, closes **no** WDR-EV.

    Args:
        authority: The deviation service's authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the deviation service holds no live-order route / credential.
    """
    if authority is None:
        return False
    return all_false_deviation_authority(authority)


# ===========================================================================
# not-Phase-1 thin model §6b (WDR-EV-006 — NOT closed, runtime revocation send-race + Security)
# ===========================================================================


def revocation_dominates_send(
    revoke_generation: int | None, send_generation: int | None
) -> bool:
    """Whether the revocation provably precedes the send so the attempt is denied (§6b; WDR-EV-006 — NOT closed).

    A thin order-permutation model of revocation dominance: ``True`` (revocation dominates ⇒ attempt
    denied) iff the revocation provably precedes the send (``BEFORE`` via ``tos.ordering.compare_order``
    — the ``REVOKE < SEND`` case, §14 line 400). An equal / ambiguous order, a send-before-revoke order,
    or a ``None`` generation is **not** a clean denial — the attempt is conservatively potentially-live
    + capacity-covered (:func:`attempt_potentially_live`; §14 line 400 "If a restrictive event races an
    authority claim, ``SEND_STARTED``, or first broker byte and ordering cannot be proved, the attempt
    remains potentially live, capacity-covered, and non-retriable"). The real cache-free currentness
    verification / ``B_deviation_revoke_to_egress`` bound / deny-first latch / restrictive floor are
    **all +Security runtime** (§6b) — this L1 thin model closes **no** WDR-EV (``EV-L3+Security``).

    Args:
        revoke_generation: The revocation ordering scalar (``None`` ⇒ ``False`` — not a clean denial).
        send_generation: The send ordering scalar (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the revocation provably precedes the send (revocation dominates).
    """
    if revoke_generation is None or send_generation is None:
        return False
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=revoke_generation),
            OrderingEvent(quorum_commit_index=send_generation),
        )
        is Ordering.BEFORE
    )


def attempt_potentially_live(
    revoke_generation: int | None, send_generation: int | None
) -> bool:
    """Whether the attempt must be treated as potentially-live + capacity-covered (§6b; WDR-EV-006).

    The conservative complement of :func:`revocation_dominates_send`: ``True`` whenever the revocation
    does **not** provably precede the send — i.e. a send-before-revoke order, an ambiguous order, or a
    ``None`` (unknown) generation. §14 line 400 "the attempt remains **potentially live**,
    capacity-covered, and non-retriable"; the unknown / ambiguous case is potentially-live, never a
    blind retry. The real deny-first latch is +Security runtime (§6b). Closes **no** WDR-EV.

    Args:
        revoke_generation: The revocation ordering scalar.
        send_generation: The send ordering scalar.

    Returns:
        ``True`` iff the attempt must be treated as potentially-live (not cleanly revoked).
    """
    return not revocation_dominates_send(revoke_generation, send_generation)
