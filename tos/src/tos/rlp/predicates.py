"""rlp restricted-live / promotion predicates (design #25 §5/§6/§6b) — pure, fail-closed.

Pure decision rules over injected frozen models (design #25 §0.2/§4): rlp authors the **trial-content
completeness / subset / separation substrate** — the four yolk predicates
(:func:`plan_scope_exact_and_complete` — RLP-EV-001; :func:`evidence_package_complete` — RLP-EV-005;
:func:`coverage_supports_claim` — RLP-EV-006; :func:`gate_status_separated` — RLP-EV-012) and their
supporting predicates, plus the predicate-only §6 substrate and the not-Phase-1 §6b thin abort-order
model. It **re-authors none** of the sibling instances it consumes: egress owns the
``QuorumCommitCertificate`` / ``TrialClaims`` boundary seal; cur owns the RESTRICTED_LIVE_TRIAL
dimension; hag owns the effective-principal collapse + quorum; evidence owns the
``SegmentCommitmentScheme`` + causal-chain + gap machine; rcl owns the ``CapacityVector`` +
worst-credible-effect; liveauth owns the Live Authorization; spg owns the policy activation; iap owns
the single-use consumption shape; authority owns the epoch floor + non-revival; and 026-030 governance
owners are sibling-owned (injected opaque coordinates). rlp **consumes** every produced fact as an
**injected scalar / bool / verdict / digest / generation** and re-authors none of them (sibling edge
0, §3.5).

**The two boundaries (design #25 §1 — rlp's twin maximum risks are opposite).** (1) **over-
realization**: the §13 per-action final-egress binding, the §14 run-state serialization, the §15
abort / HALT / demotion race, the §10 worst-credible-effect computation, the §12 Live Authorization
issuance, the §16 evidence assembly / custody integrity, and the §18-§19 independent review /
promotion approval / production authorization are **all L2+ / runtime / +Security / +Broker / human /
sibling-owned** — L1 owns only plan / package / coverage / gate structural completeness over injected
coordinates. (2) **duplication**: the sibling owners' *business content* is **never** re-decided here
(§3.5) — rlp consumes each owner verdict / generation / digest and judges only the trial-content axis.

**Completeness is the content axis, not the egress thin all-present seal (design #25 §0.4b — the
airtight rebuttal).** The egress ``TrialClaims.is_complete()`` is a *boundary* all-present structural
seal (are the 6 scalars concrete); :func:`plan_scope_exact_and_complete` is the *content*
exact-completeness (does the plan bind every §9 scope dimension exactly). Different axes; egress
explicitly defers the content axis to RLP by name (``state.py:196``).

**Truthy-sentinel discipline (design #25 §4.2).** ``PlanResult`` / ``PromotionResult`` /
``TrialRunState`` / ``CoverageVerdict`` are truthy-untestable ``StrEnum``s (``__bool__`` raises), so
every gate uses ``x is ENUM.SAFE_VALUE``; a bare ``if result:`` would fail open reading a denial /
non-permissive member as a go.

**Polarity discipline (design #25 §4.3 — #22 MAJOR-2 seal).** Every ``bool | None`` field declares a
polarity and is normalized with ``is True`` / ``is False`` (never ``if flag:`` / ``if not flag:``): a
``None`` is UNKNOWN and converges to **deny** on both polarities. Positive-polarity fields
(``pre_registered`` / ``independently_reviewed`` / ``selection_fixed_before_start`` /
``equivalence_positively_proven`` / ``causal_chain_complete`` / ``effective_principal_verdict``) admit
only on ``is True``; negative-polarity fields (``single_use_consumed`` / ``is_expired`` /
``is_aborted`` / ``optional_stopping`` / ``discarded_runs`` / ``selected_windows`` / ``removed_adverse``
/ ``has_unresolved_gap``) admit only on ``is False`` (a ``None`` unknown-consumed / unknown-expiry is
denial — the #22 MAJOR-2 re-seal: ``is not True`` would admit a ``None``).

**Group reconcile discipline (design #25 §4.4 — #22 MAJOR-1 seal).** A multi-package / multi-claim
verdict reconciles **all** entries conservatively, never the first: :func:`no_union_coverage` is
any-narrow-wins (a single failing claim denies the aggregate — §17 line 446 "Multiple narrow passing
packages cannot be unioned"), and :func:`negative_results_retained` requires every negative class
retained (a passing subset cannot erase them, §16 line 426) — both order-independent.

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.rlp.*`` (records / state / vocabulary /
_base) only; no ``shared.*``, no other sibling ``tos.*`` (design #25 §0.3). Clock-free.
"""

from __future__ import annotations

from collections.abc import Sequence

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.rlp._base import AllFalseTrialAuthority
from tos.rlp.records import (
    ExactTrialPlan,
    ProductionScopePromotionDecision,
    TrialEvidencePackage,
    TrialPolicy,
)
from tos.rlp.state import (
    CoverageClaim,
    GateStatusLadder,
    TrialBudget,
    TrialClaimGroup,
    is_wildcard_value,
    promotion_generation_advances,
)
from tos.rlp.vocabulary import (
    MANDATED_EVIDENCE_FLOOR,
    MANDATED_SCOPE_FLOOR,
    NEGATIVE_RESULT_CLASSES,
    CoverageVerdict,
    EvidenceClass,
    PlanResult,
    PromotionResult,
    ScopeDimension,
    TrialRunState,
)

__all__ = [
    # core §5 — the four yolk predicates + supporting (RLP-EV-001/005/006/012 substrate)
    "plan_result_admissible",
    "no_wildcard_scope",
    "baseline_digests_bound",
    "plan_scope_exact_and_complete",
    "trial_claims_complete",
    "negative_results_retained",
    "no_selective_reporting",
    "evidence_package_complete",
    "coverage_supports_claim",
    "no_union_coverage",
    "no_status_implication",
    "readiness_not_authority",
    "gate_status_separated",
    # predicate-only §6 substrate (≥ L2 — closes NO RLP-EV)
    "trial_budget_is_not_capacity",
    "trial_status_waives_no_gate",
    "promotion_progressive_single_use",
    "all_false_trial_authority",
    "expiry_denies_future_use_only",
    "economic_effect_persists",
    "recovery_revives_nothing",
    "monitoring_not_preventive",
    "demotion_not_rearm",
    # not-Phase-1 thin model §6b (RLP-EV-004 substrate — runtime race residue)
    "abort_precedes_action",
    "action_potentially_live",
]


# ===========================================================================
# core §5.1 — plan_scope_exact_and_complete yolk + supporting (RLP-EV-001 substrate)
# ===========================================================================


def plan_result_admissible(plan: ExactTrialPlan | None) -> bool:
    """Whether the plan result is the sole eligible value (§5.1/§9 line 275; truthy-seal §4.2).

    ``True`` **only** when ``plan.result is
    PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`` — the mandated explicit positive-identity gate
    (a bare ``if plan.result:`` would fail open on the truthy ``INELIGIBLE`` / ``HOLD`` strings). Even
    this value is **non-authorizing** (§9 line 275) — eligibility to *request* a Live Authorization,
    never a grant.

    Args:
        plan: The Exact Trial Plan (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the plan result is ``ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION``.
    """
    if plan is None:
        return False
    return plan.result is PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION


def no_wildcard_scope(plan: ExactTrialPlan | None) -> bool:
    """Whether no scope dimension uses a wildcard / inferred / stale sentinel (§5.1; RLP-INV-002:154).

    ``True`` **only** when the plan and its ``trial_scope`` exist and **no** dimension is a
    (detectable) wildcard per :func:`~tos.rlp.state.is_wildcard_value` — a catalogued
    :data:`~tos.rlp.state.WILDCARD_SENTINELS` sentinel (case-insensitively), a
    :data:`~tos.rlp.state.WILDCARD_METACHARACTERS` glob / regex / ``LIKE`` metacharacter, or a
    whitespace-only blank (RLP-INV-002 line 154 "wildcard, inferred, patched, unioned, stale, or
    conflicting scope is denial"). A ``None`` plan / scope ⇒ ``False`` (fail-closed). **Best-effort,
    non-exhaustive**: the RLP-INV-002 patched / unioned / stale / conflicting axes are +Security /
    runtime-owned, not value-model-decidable (§0.4 / :func:`~tos.rlp.state.is_wildcard_value`).

    Args:
        plan: The Exact Trial Plan (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no scope dimension is a wildcard sentinel.
    """
    if plan is None or plan.trial_scope is None:
        return False
    return not plan.trial_scope.wildcard_dimensions()


def baseline_digests_bound(plan: ExactTrialPlan | None) -> bool:
    """Whether every baseline artifact digest is concrete (§5.1/§9 line 263).

    ``True`` **only** when the plan exists, ``baseline_digests`` is **non-empty**, and every entry is
    concrete (not ``None`` and not a wildcard per :func:`~tos.rlp.state.is_wildcard_value` — a
    catalogued sentinel, a glob / regex / ``LIKE`` metacharacter, or a whitespace-only blank) — §9 line
    263 "complete baseline artifact digests". An empty / ``None`` / wildcard baseline ⇒ ``False``.

    Args:
        plan: The Exact Trial Plan (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every baseline digest is concrete.
    """
    if plan is None or not plan.baseline_digests:
        return False
    return all(
        digest is not None and not is_wildcard_value(digest)
        for digest in plan.baseline_digests
    )


def _plan_content_exact(plan: ExactTrialPlan | None) -> bool:
    """The plan-side exact-content core shared by the yolk and the seam predicate (§5.1)."""
    if plan is None or plan.trial_scope is None:
        return False
    if plan.trial_scope.concrete_dimensions() != MANDATED_SCOPE_FLOOR:
        return False
    if not no_wildcard_scope(plan):
        return False
    if not baseline_digests_bound(plan):
        return False
    if not plan_result_admissible(plan):
        return False
    return plan.pre_registered is True and plan.independently_reviewed is True


def plan_scope_exact_and_complete(
    plan: ExactTrialPlan | None,
    policy: TrialPolicy | None,
    mandated_scope: frozenset[ScopeDimension],
) -> bool:
    """The yolk: whether a plan binds an exact, complete, pre-registered scope (§5.1; RLP-EV-001 — NOT closed).

    ``True`` **only** when **all** of the following hold (AND, fail-closed):

    1. **∅-seal (both-ways)**: ``plan`` and ``policy`` are non-``None``, ``mandated_scope`` is
       non-empty, and ``plan.trial_scope`` has a non-empty concrete set — an absent plan / policy /
       mandate / scope is **never** vacuously complete (§9 line 275 "A missing ... plan is
       ``INELIGIBLE``").
    2. **result admissible (§4.2)**: ``plan.result is
       PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`` — ``INELIGIBLE`` / ``HOLD`` deny.
    3. **every mandated dimension present + concrete (set both-ways)**: the effective mandate
       (``mandated_scope`` floored to at least :data:`~tos.rlp.vocabulary.MANDATED_SCOPE_FLOOR`, so a
       caller may require *more* but never fewer — the cur v1.1 MINOR-1 precedent) is a subset of the
       plan's concrete dimensions. An unrepresented / wildcard dimension ⇒ incomplete (the egress QCC
       coexistence seal / spg ``bundle_complete`` precedent).
    4. **no wildcard / inferred / stale (§5.1)**: :func:`no_wildcard_scope`.
    5. **baseline digests bound (§9 line 263)**: :func:`baseline_digests_bound`.
    6. **pre-registered + independently reviewed (§4.3)**: ``plan.pre_registered is True`` AND
       ``plan.independently_reviewed is True``.

    **Completeness is the content axis, not the egress thin all-present seal (§0.4b).** The
    unrepresented-dimension (3), wildcard (4), and baseline (5) checks are the exact-scope *content*
    axis; the egress ``TrialClaims.is_complete()`` (6-scalar all-present) is a boundary structural
    seal (§0.4b/c). This L1 substrate **does not close** RLP-EV-001 — that row is ``EV-L1/3`` and
    awaits ``/3`` integration / adversarial evidence (authoring is not acceptance, §1).

    Args:
        plan: The Exact Trial Plan (``None`` ⇒ ``False``).
        policy: The governing Trial Policy (``None`` ⇒ ``False``).
        mandated_scope: The caller-supplied mandate (∅ ⇒ ``False``), floored to the §9 floor.

    Returns:
        ``True`` iff the plan binds an exact, complete, pre-registered, reviewed scope.
    """
    if plan is None or policy is None:
        return False
    if not mandated_scope:
        return False
    scope = plan.trial_scope
    if scope is None:
        return False
    concrete = scope.concrete_dimensions()
    if not concrete:
        return False
    effective = frozenset(mandated_scope) | MANDATED_SCOPE_FLOOR
    if not (effective <= concrete):
        return False
    return _plan_content_exact(plan)


def trial_claims_complete(
    claims: TrialClaimGroup | None,
    plan: ExactTrialPlan | None,
) -> bool:
    """Whether the 6-scalar trial claim group is complete AND the plan scope is exact (§5.1/§0.4b/c).

    The **content owner's** authoritative completeness — **thicker** than the egress thin all-present
    seal: ``True`` **only** when (i) ``claims`` exists and every one of the six scalars
    (:data:`~tos.rlp.state.TrialClaimGroup.REQUIRED_SCALARS`) is concrete — the egress
    ``TrialClaims.is_complete()`` mirror — **AND** (ii) the plan's exact-scope content is itself
    complete (:func:`_plan_content_exact`: scope every-dimension concrete, no wildcard, baseline
    bound, result eligible, pre-registered, reviewed). The six-scalar field-set matches egress §11.1
    line 308 / cur §9:258 (a manually-transcribed anchor; the seam cross-check test asserts equality,
    §0.4h) — this is **not** an egress / cur re-authoring (sibling edge 0).

    Args:
        claims: The RLP-owned trial claim group view (``None`` ⇒ ``False``).
        plan: The Exact Trial Plan whose exact-scope content thickens the completeness (``None`` ⇒
            ``False``).

    Returns:
        ``True`` iff the 6 scalars are concrete and the plan scope is exact-complete.
    """
    if claims is None or plan is None:
        return False
    if not claims.is_complete():
        return False
    return _plan_content_exact(plan)


# ===========================================================================
# core §5.2 — evidence_package_complete yolk + supporting (RLP-EV-005 substrate)
# ===========================================================================


def negative_results_retained(package: TrialEvidencePackage | None) -> bool:
    """Whether every negative-result element class is retained (§5.2; RLP-INV-009).

    ``True`` **only** when the package exists and its element-class manifest contains **all** of
    :data:`~tos.rlp.vocabulary.NEGATIVE_RESULT_CLASSES` (negative / failed / inconclusive / aborted /
    superseded / conflicting — the §16 line 422 six) — §16 line 426 / RLP-INV-009 "Failed, aborted,
    conflicting, incomplete, and inconclusive trials remain retained". A passing subset that erased
    any negative class ⇒ ``False``
    (order-independent, all-required-present — the #22 MAJOR-1 reconcile seal). Consistent with, but a
    **separate gate** from, evidence ERI-INV-004 (negative first-class retention), which is injected
    (§0.4d).

    Args:
        package: The Trial Evidence Package (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every negative-result class is present in the manifest.
    """
    if package is None:
        return False
    return package.present_element_classes >= NEGATIVE_RESULT_CLASSES


def no_selective_reporting(package: TrialEvidencePackage | None) -> bool:
    """Whether selection was fixed before start with no post-hoc selection (§5.2; §16 line 426).

    ``True`` **only** when ``selection_fixed_before_start is True`` (positive polarity) **and** every
    post-hoc selection flag (``optional_stopping`` / ``discarded_runs`` / ``selected_windows`` /
    ``removed_adverse``) is ``is False`` (negative polarity — a ``None`` unknown is denial, the #22
    MAJOR-2 seal): §16 line 426 "Post-hoc metric changes, optional stopping, discarded runs, selected
    time windows, selected accounts, or removal of adverse results invalidate the promotion claim".

    Args:
        package: The Trial Evidence Package (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff selection is fixed and no post-hoc selection occurred.
    """
    if package is None:
        return False
    if package.selection_fixed_before_start is not True:
        return False
    return (
        package.optional_stopping is False
        and package.discarded_runs is False
        and package.selected_windows is False
        and package.removed_adverse is False
    )


def evidence_package_complete(
    package: TrialEvidencePackage | None,
    policy: TrialPolicy | None,
    mandated_classes: frozenset[EvidenceClass],
) -> bool:
    """The yolk: whether a trial evidence package is complete (§5.2; RLP-EV-005 — NOT closed).

    ``True`` **only** when **all** of the following hold (AND, fail-closed):

    1. **∅-seal (both-ways)**: ``package`` and ``policy`` are non-``None``, ``mandated_classes`` is
       non-empty, and the package manifest is non-empty — §16 line 428 "A complete package proves what
       occurred ... it does not prove that untested behavior is safe".
    2. **every element class present (set both-ways)**: the effective mandate (``mandated_classes``
       floored to at least :data:`~tos.rlp.vocabulary.MANDATED_EVIDENCE_FLOOR`) is a subset of the
       manifest. An unrepresented class ⇒ incomplete.
    3. **negative retention (the yolk core)**: :func:`negative_results_retained`.
    4. **no selective reporting (§4.3)**: :func:`no_selective_reporting`.
    5. **evidence integrity injected (§0.4d)**: ``package.causal_chain_complete is True``
       (evidence-owned injected verdict) AND ``package.has_unresolved_gap is False`` (evidence-owned
       gap machine) — **re-authored not at all**, consumed as injected verdicts.

    This L1 substrate **does not close** RLP-EV-005 — that row is ``EV-L1/3`` and awaits ``/3``
    evidence (authoring is not acceptance, §1).

    Args:
        package: The Trial Evidence Package (``None`` ⇒ ``False``).
        policy: The governing Trial Policy (``None`` ⇒ ``False``).
        mandated_classes: The caller-supplied mandate (∅ ⇒ ``False``), floored to the §16 floor.

    Returns:
        ``True`` iff the package is complete with negative retention, no selective reporting, and
        injected integrity.
    """
    if package is None or policy is None:
        return False
    if not mandated_classes:
        return False
    present = package.present_element_classes
    if not present:
        return False
    effective = frozenset(mandated_classes) | MANDATED_EVIDENCE_FLOOR
    if not (effective <= present):
        return False
    if not negative_results_retained(package):
        return False
    if not no_selective_reporting(package):
        return False
    if package.causal_chain_complete is not True:
        return False
    return package.has_unresolved_gap is False


# ===========================================================================
# core §5.3 — coverage_supports_claim yolk (RLP-EV-006 substrate — the cleanest L1 slice)
# ===========================================================================


def coverage_supports_claim(claim: CoverageClaim | None) -> bool:
    """The yolk: whether observed coverage supports the claim without extrapolation (§5.3; RLP-EV-006).

    ``True`` **only** when **all** of the following hold (AND, fail-closed):

    1. **∅-seal (both-ways)**: ``claim`` is non-``None`` and **both** ``observed_scope`` and
       ``claimed_scope`` are non-empty — an observation-less claim and a claim-less coverage are both
       denial (§5.8 "Unexercised ... behavior is uncovered").
    2. **subset non-extrapolation (set both-ways)**: ``claimed_scope ⊆ observed_scope`` (§17 line 434
       "map evidence to exact ... scope"). If ``claimed`` has an element outside ``observed`` it is
       **extrapolation** and denied — **unless** (3) supplies approved equivalence.
    3. **equivalence positively proven (the only cross-scope path)**: a claimed-⊄-observed claim is
       admitted only when ``equivalence_positively_proven is True`` (§17 line 444 "unless the active
       policy supplies approved equivalence evidence. **Unknown equivalence is non-equivalence**").
       ``None`` / ``False`` forbids extrapolation.
    4. **unexercised is uncovered (§5.8)**: ``claimed_scope`` must be disjoint from
       ``unexercised_conditions`` — silence / unexercised coverage does not prove safety (RLP-INV-008).
       (``claimed_scope`` and ``unexercised_conditions`` are typically drawn from *different*
       vocabularies — scope tokens vs the §17 line 440 condition catalogue — so this is a **secondary
       guard** that only fires when the two sets share comparable tokens; it never weakens the
       subset check in (2).)
    5. **verdict (§4.2)**: ``claim.verdict is CoverageVerdict.COVERED`` — ``UNCOVERED`` / ``UNKNOWN``
       deny.

    This L1 substrate **does not close** RLP-EV-006 — that row is ``EV-L1/3`` (authoring is not
    acceptance, §1).

    Args:
        claim: The coverage claim (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff observed coverage supports the claimed scope without extrapolation.
    """
    if claim is None:
        return False
    if not claim.observed_scope or not claim.claimed_scope:
        return False
    if not (claim.claimed_scope <= claim.observed_scope):
        if claim.equivalence_positively_proven is not True:
            return False
    if not claim.claimed_scope.isdisjoint(claim.unexercised_conditions):
        return False
    return claim.verdict is CoverageVerdict.COVERED


def no_union_coverage(claims: Sequence[CoverageClaim]) -> bool:
    """Whether every coverage claim independently holds — never unioned (§4.4/§6.3; §17 line 446).

    ``True`` **only** when the claim set is **non-empty** and **every** claim independently satisfies
    :func:`coverage_supports_claim` — §17 line 446 "Multiple narrow passing packages cannot be unioned
    into a broad coverage claim. An aggregate scope requires its own combined-scope concurrency and
    common-mode evidence". A single failing / ``None`` claim denies the aggregate (**any-narrow-wins**,
    order-independent — the #22 MAJOR-1 reconcile seal); an ∅ set ⇒ ``False`` (nothing proven).

    Args:
        claims: The coverage claims to reconcile (∅ ⇒ ``False``).

    Returns:
        ``True`` iff every claim independently holds (no union).
    """
    if not claims:
        return False
    return all(coverage_supports_claim(claim) for claim in claims)


# ===========================================================================
# core §5.4 — gate_status_separated yolk + supporting (RLP-EV-012 substrate)
# ===========================================================================


def no_status_implication(ladder: GateStatusLadder | None) -> bool:
    """Whether every gate stage is explicit, none inferred from another (§5.4; §26 AC-012).

    ``True`` **only** when the ladder exists and **every** one of the nine stages
    (:data:`~tos.rlp.state.GateStatusLadder.STAGE_FIELDS`) is an **explicit** ``bool`` (``True`` or
    ``False``) — a ``None`` stage is an *inferred / implied* status, which is exactly the implication
    this seal forbids (§26 AC-012 line 680 "remain distinct explicit states"; §18 line 464 "It is not
    approval of an order or production permission"; §19 "Production authorization is a **separate**
    explicit human-governed decision"). Each stage is an independent injected bool, so a positive
    stage never structurally derives another — the ``None`` (inference) check is what a runtime
    predicate can enforce.

    Args:
        ladder: The gate-status ladder (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every stage is an explicit bool (no inferred stage).
    """
    if ladder is None:
        return False
    return all(
        getattr(ladder, name) in (True, False) for name in GateStatusLadder.STAGE_FIELDS
    )


def readiness_not_authority(ladder: GateStatusLadder | None) -> bool:
    """Whether the ladder's readiness carries no authority (§5.4; RLP-INV-001; sbr readiness≠re-arm).

    ``True`` **only** when the ladder exists and its ``authority_effect`` is all-false
    (:func:`all_false_trial_authority`) — ``restricted_live_ready`` / ``production_ready`` being
    ``True`` is a **status report**, not a permission (the sbr readiness ≠ re-arm precedent; §26
    AC-012). A ``None`` ladder / authority, or any non-``False`` authority flag ⇒ ``False``.

    Args:
        ladder: The gate-status ladder (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff readiness confers no authority.
    """
    if ladder is None:
        return False
    return all_false_trial_authority(ladder.authority_effect)


def gate_status_separated(ladder: GateStatusLadder | None) -> bool:
    """The yolk: whether the nine gate states are distinct and readiness ≠ authority (§5.4; RLP-EV-012).

    ``True`` **only** when **all** of the following hold (AND, fail-closed):

    1. **∅-seal**: ``ladder`` is non-``None``.
    2. **no implication (§5.4)**: :func:`no_status_implication` — every stage explicit, none inferred
       (``plan_eligible ↛ live_authorized``, ``promotion_eligible ↛ config_activated /
       production_ready``).
    3. **readiness ≠ authority (§5.4)**: :func:`readiness_not_authority` — readiness is a status
       report, never a permission.

    This extends the all-false-authority invariant to **status separation** (no gate truthy-implies
    another). This L1 substrate **does not close** RLP-EV-012 — that row is ``EV-L1/3`` (authoring is
    not acceptance, §1).

    Args:
        ladder: The gate-status ladder (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the nine gate states are distinct and readiness confers no authority.
    """
    if ladder is None:
        return False
    if not no_status_implication(ladder):
        return False
    return readiness_not_authority(ladder)


# ===========================================================================
# predicate-only §6 substrate (≥ L2 — closes NO RLP-EV)
# ===========================================================================


def all_false_trial_authority(authority: AllFalseTrialAuthority | None) -> bool:
    """Whether an authority block confers nothing — every flag ``False`` (§6.4; RLP-EV-008 substrate).

    ``True`` **only** when the block exists and **every** flag is ``is False`` (creates_capacity /
    creates_protection / issues_live_authorization / issues_capability / transmits / clears_halt /
    re_arms / grants_broker_permission / classifies_protection). A ``None`` block, or any non-``False``
    flag ⇒ ``False`` (fail-closed). The construction-time validator already rejects any ``True`` flag;
    this predicate re-derives the all-false property so a ``model_construct`` bypass cannot smuggle a
    permissive block past a consumer (defence in depth, §2.3). RLP-INV-001: a policy / plan / run /
    package / decision is verified data / a non-authorizing decision, not permission.

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


def trial_budget_is_not_capacity(budget: TrialBudget | None) -> bool:
    """Whether the trial budget is a request envelope, never capacity (§6.1; RLP-EV-002 substrate·+Broker).

    ``True`` **only** when the budget exists — a :class:`~tos.rlp.state.TrialBudget` is structurally an
    **upper request envelope**, never capacity: it carries no capacity-mutation coordinate, so unused
    budget creates **no** headroom and cannot be transferred (§10 line 296 "Only RCL may commit
    capacity. Unused plan budget creates no headroom"). The ``credible_economic_effect_envelope`` is an
    **injected** rcl ``CapacityVector`` coordinate — the worst-credible-effect *computation* is rcl +
    +Broker (§28 open Q #3), **never** re-authored here. This is predicate-only substrate:
    ``EV-L2/3+Broker``, closes **no** RLP-EV.

    Args:
        budget: The trial budget request envelope (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff a budget request envelope is present (structurally not capacity).
    """
    return budget is not None


def trial_status_waives_no_gate(authority: AllFalseTrialAuthority | None) -> bool:
    """Whether trial status waives no safety gate (§6.2; RLP-EV-003 substrate·+Broker; RLP-INV-004).

    ``True`` **only** when the authority exists and its bypass-relevant flags — ``transmits`` /
    ``clears_halt`` / ``grants_broker_permission`` / ``issues_capability`` /
    ``issues_live_authorization`` — are **all** ``is False``: restricted-live status, low notional,
    supervision, canary naming, or evidence collection **never bypasses** a normal safety check or
    final-egress enforcement (RLP-INV-004 line 162). The real per-send binding is egress runtime +
    +Broker (§13). Predicate-only substrate: ``EV-L2/3+Broker``, closes **no** RLP-EV.

    Args:
        authority: The trial artifact's authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff trial status waives no gate.
    """
    if authority is None:
        return False
    return (
        authority.transmits is False
        and authority.clears_halt is False
        and authority.grants_broker_permission is False
        and authority.issues_capability is False
        and authority.issues_live_authorization is False
    )


def _within_max_delta(requested_delta: str | None, max_delta: int | None) -> bool:
    """Whether the requested promotion delta is within the approved max delta (§6.3; §18 line 466).

    Null-gated + fail-closed (§8 "a missing numeric claim fails closed"): ``True`` **only** when
    **both** the decision's ``requested_delta`` and the policy's approved ``max_delta`` ceiling are
    concrete (non-``None``). The **actual numeric ``requested_delta ≤ max_delta`` comparison is
    +Security / INSTANCE-deferred** — the requested delta is an opaque scope-delta coordinate and the
    ``max_delta`` ceiling is a Profile-INSTANCE value that is null in Phase 1 (§8), so the numeric
    ``≤`` is not L1-decidable. This slice confirms only that both the requested claim **and** an
    approved ceiling are *present*: a null delta claim, or a null / undefined ceiling (no approved
    delta), fails closed (§4.2 / §18 line 466 "exceed the approved delta"). Closes **no** RLP-EV.

    Args:
        requested_delta: The decision's requested scope-delta coordinate (``None`` ⇒ ``False``).
        max_delta: The policy's approved max-delta ceiling (``None`` ⇒ ``False`` — no approved delta).

    Returns:
        ``True`` iff both the requested delta and the approved ceiling are concrete (present).
    """
    return requested_delta is not None and max_delta is not None


def promotion_progressive_single_use(
    decision: ProductionScopePromotionDecision | None,
    policy: TrialPolicy | None,
    predecessor_promotion_generation: int | None,
) -> bool:
    """Whether a promotion decision is fresh, single-use, within-delta, and not retired (§6.3; RLP-EV-007).

    REUSES the iap single-use consumption **shape** (not an import — §0.4g). The full §6.3 five-part
    gate (AND, fail-closed):

    1. **single-use (negative polarity)**: ``decision.single_use_consumed is False`` — a consumed /
       ``None``-unknown decision is reject-reuse (§18 line 464 "consumed, once"; §4.3).
    2. **result eligible (§4.2)**: ``decision.result is
       PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE`` — ``DENY`` / ``HOLD`` deny.
    3. **no union (§4.4)**: :func:`no_union_coverage` over the decision's coverage claims (multiple
       narrow passing packages cannot be unioned, §17 line 446).
    4. **within the approved delta (§18 line 466)**: :func:`_within_max_delta` over
       ``decision.requested_delta`` and the ``policy``'s approved ``max_delta`` — null-gated +
       fail-closed (the numeric ``≤`` is +Security / INSTANCE-deferred, §8).
    5. **not retired by a newer Promotion Generation (§5.10 / §18 line 466)**: the decision's
       ``promotion_generation`` must strictly advance the injected
       ``predecessor_promotion_generation`` floor
       (:func:`~tos.rlp.state.promotion_generation_advances` — a ``tos.ordering`` REUSE). A decision
       at or below the floor has been **retired** by a newer Promotion Generation and is denied (§18
       line 466 "reuse old evidence after material change ... or a newer Promotion Generation"); a
       ``None`` generation on either side fails closed.

    The real registry replay / generation-fence enforcement is +Security (§18). Predicate-only
    substrate: ``EV-L2/3+Security``, closes **no** RLP-EV.

    Args:
        decision: The Production Scope Promotion Decision (``None`` ⇒ ``False``).
        policy: The governing Trial Policy carrying the approved ``max_delta`` ceiling (``None`` ⇒
            ``False`` — no approved delta).
        predecessor_promotion_generation: The injected Promotion Generation floor the decision must
            strictly advance (``None`` ⇒ ``False`` — a stale / retired / unknown-generation decision
            fails closed).

    Returns:
        ``True`` iff the decision is fresh, eligible, single-use, within-delta, and not retired.
    """
    if decision is None or policy is None:
        return False
    if decision.single_use_consumed is not False:
        return False
    if decision.result is not PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE:
        return False
    if not no_union_coverage(decision.coverage_claims):
        return False
    if not _within_max_delta(decision.requested_delta, policy.max_delta):
        return False
    return promotion_generation_advances(
        predecessor_promotion_generation, decision.promotion_generation
    )


def expiry_denies_future_use_only(is_expired: bool | None) -> bool:
    """Whether an expired trial denies future use while capacity / economic effect persists (§6.5).

    Returns whether **future use is denied**: ``True`` (deny) when ``is_expired is not False``
    (``True`` / ``None`` — **negative polarity**: a ``None`` unknown-expiry is denial, never a
    fail-open to "not expired", §4.3). Expiry denies **only future use** and **cannot** cancel orders,
    prove non-acceptance / Final Quantity, erase positions, or release capacity (RLP-INV-012 line 194;
    §20 line 490-499). This predicate reports **only** the future-use denial; it performs no capacity
    effect (all-false, §6.4).

    Args:
        is_expired: The negative-polarity expiry state (``True`` / ``None`` ⇒ deny future use).

    Returns:
        ``True`` iff future use is denied (capacity / economic effect unchanged).
    """
    return is_expired is not False


def economic_effect_persists(authority: AllFalseTrialAuthority | None) -> bool:
    """Whether the economic effect persists across a trial terminal (§6.5; RLP-INV-012; afg/are shape).

    ``True`` **only** when the authority exists and neither ``creates_capacity`` nor
    ``classifies_protection`` is non-``False`` — a trial completion / abort / expiry / invalidation /
    promotion-decision consumption **cannot** cancel orders, release capacity, or erase positions
    (RLP-INV-012 line 194); the economic effect therefore persists regardless of the terminal state.
    Isomorphic to the afg / are / capsule ``terminal_release_proven`` shape. Predicate-only substrate:
    ``EV-L2/3+Broker``, closes **no** RLP-EV.

    Args:
        authority: The trial artifact's authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the economic effect persists (no capacity release / protection reclassification).
    """
    if authority is None:
        return False
    return (
        authority.creates_capacity is False and authority.classifies_protection is False
    )


def recovery_revives_nothing(
    is_recovery_event: bool | None,
    prior_run_state: TrialRunState | None,
) -> bool:
    """Whether a run is live after a recovery event — a recovery revives nothing (§6.6; RLP-EV-010).

    Returns whether the run is **live after** the event. ``is_recovery_event`` is **negative
    polarity** (§4.3): only an **explicit** ``is False`` (a proven *non*-recovery) admits — a restart
    / reconnect / failover / restore / replay / reconciliation / time-recovery / broker-recovery /
    operator-return event (``True``) **and** an *unknown* recovery flag (``None``) both **revive
    nothing** (the #25 MAJOR-2 re-seal: ``is not False`` denies the ``None``, never fail-opening to
    "not a recovery"). When it revives nothing the prior run must be treated as ``INVALIDATED``,
    queued actions rejected, and a new run identity required (RLP-INV-013 line 197; §21 line 509), so
    this returns ``False``. Absent a recovery event (``is_recovery_event is False``) the run is live
    only when the prior state was ``RUNNING`` (the sole non-terminal live state; ``None`` / terminal
    ⇒ ``False``). The real hard-fence is +Security (§21). Isomorphic to the authority / cur
    non-revival precedent (§0.4g). Predicate-only substrate: ``EV-L2/3+Security``, closes **no**
    RLP-EV.

    Args:
        is_recovery_event: Negative-polarity recovery flag — only an explicit ``False`` (non-recovery)
            keeps a run live; ``True`` / ``None`` ⇒ revives nothing (dead).
        prior_run_state: The prior run state (only ``RUNNING`` is live absent a recovery event).

    Returns:
        ``True`` iff the run is live after the event (never after — or on an unknown — recovery event).
    """
    if is_recovery_event is not False:
        return False
    return prior_run_state is TrialRunState.RUNNING


def monitoring_not_preventive(authority: AllFalseTrialAuthority | None) -> bool:
    """Whether an EV-L6 monitor result authorizes anything — it does not (§6.7; RLP-EV-011; RLP-INV-015).

    ``True`` **only** when the monitor result's authority block exists and is all-false
    (:func:`all_false_trial_authority`) — an EV-L6 monitor is **detective**, non-authorizing
    (RLP-INV-015 line 208 "A ``CONFORMING`` monitor result remains non-authorizing and cannot promote,
    resume, or re-arm"). A ``None`` / non-all-false authority ⇒ ``False``. The monitoring generation is
    an injected -028 (STM) coordinate, not landed (§0.4f). Predicate-only substrate: ``EV-L2/3+Broker``,
    closes **no** RLP-EV.

    Args:
        authority: The monitor result's authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the monitor result confers no authority (detective only).
    """
    if authority is None:
        return False
    return all_false_trial_authority(authority)


def demotion_not_rearm(historical_promotion_reused: bool | None) -> bool:
    """Whether a demotion avoids reusing a historical promotion (§6.7; §19 line 484).

    ``True`` **only** when ``historical_promotion_reused is False`` (negative polarity — a ``True`` /
    ``None`` reuse attempt is denial): a demotion to a narrower scope is **not** a reusable historical
    promotion (§19 line 484 "historical promotion is not a reusable authorization") — it requires fresh
    config / reconciliation / authority. Predicate-only substrate: ``EV-L2/3+Broker``, closes **no**
    RLP-EV.

    Args:
        historical_promotion_reused: Whether a historical promotion is being reused (``True`` / ``None``
            ⇒ deny).

    Returns:
        ``True`` iff no historical promotion is reused (fresh authority path).
    """
    return historical_promotion_reused is False


# ===========================================================================
# not-Phase-1 thin model §6b (RLP-EV-004 — NOT closed, runtime race + Security)
# ===========================================================================


def abort_precedes_action(
    abort_generation: int | None, action_generation: int | None
) -> bool:
    """Whether the abort provably precedes the action so the action is denied (§6b; RLP-EV-004 — NOT closed).

    A thin order-permutation model of abort dominance: ``True`` (abort dominates ⇒ action denied) iff
    the abort provably precedes the action (``BEFORE`` via ``tos.ordering.compare_order``). An equal /
    ambiguous order, an action-before-abort order, or a ``None`` generation is **not** a clean
    denial — the action is conservatively potentially-live + capacity-covered
    (:func:`action_potentially_live`; §15 line 408 "A lost abort response is treated as **possibly
    applied**"). The real abort latency / ``B_trial_abort_*`` bounds / deny-first latch / incident
    protocol are **all +Security runtime** (§6b) — this L1 thin model closes **no** RLP-EV
    (``EV-L3+Security``).

    Args:
        abort_generation: The abort ordering scalar (``None`` ⇒ ``False`` — not a clean denial).
        action_generation: The action ordering scalar (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the abort provably precedes the action (abort dominates).
    """
    if abort_generation is None or action_generation is None:
        return False
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=abort_generation),
            OrderingEvent(quorum_commit_index=action_generation),
        )
        is Ordering.BEFORE
    )


def action_potentially_live(
    abort_generation: int | None, action_generation: int | None
) -> bool:
    """Whether the action must be treated as potentially-live + capacity-covered (§6b; RLP-EV-004).

    The conservative complement of :func:`abort_precedes_action`: ``True`` whenever the abort does
    **not** provably precede the action — i.e. an action-before-abort order, an ambiguous order, or a
    ``None`` (unknown) generation. §15 line 408 "A lost abort response is treated as **possibly
    applied**"; the unknown / ambiguous case is potentially-live, never a blind retry. The real
    deny-first latch is +Security runtime (§6b). Closes **no** RLP-EV.

    Args:
        abort_generation: The abort ordering scalar.
        action_generation: The action ordering scalar.

    Returns:
        ``True`` iff the action must be treated as potentially-live (not cleanly aborted).
    """
    return not abort_precedes_action(abort_generation, action_generation)
