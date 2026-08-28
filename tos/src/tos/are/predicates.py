"""are decision-integrity predicates + the produced-seam producers (design #13 §5/§6).

Pure, fail-closed decision rules over injected frozen models (design #13 §0.2/§4.5): are is
**not** a numeric engine (the valuation / scenario / correlation / solver models are Phase-0,
§4 non-scope) — it authors the **conservative / monotone / acyclic / currentness / non-revival**
decision rules and combines injected :data:`~tos.canonical.CanonicalDecimal` magnitudes only
arithmetically (sum / difference / max). There is **no** "assume-zero" / "assume-within" /
"assume-grant" path anywhere: a positive result comes only from positive proof, everything
else is ``UNKNOWN`` / ``DENY`` / ``False`` (design #13 §4.1 — the structural seal against the
#6 fail-open REJECT lesson).

The module is split by role:

* **core §5** — ``snapshot_scope_complete`` / ``exact_effect_snapshot_binding`` /
  ``adverse_increment`` / ``dimension_vector_integrity`` / ``valuation_conservative`` /
  ``numerical_safety`` / ``risk_decision`` / ``envelope_bound_not_enlarged`` (ARE-EV-001/002/
  003/004/006 substrate).
* **predicate-only §6** — ``benefit_admissible`` / ``numerical_determinism`` /
  ``protective_creates_nothing`` / ``grants_no_authority`` (ARE-EV-005/007/010/011 substrate;
  the temporal §6.3/§6.4/§6.6 predicates live in :mod:`tos.are.state`).
* **produced-seam producers (§3.4)** — the conservative protective magnitudes
  (``final_conservative_risk`` ... ``already_exceeded_regime``), the cancellation-arbiter flags
  (``continued_existence_worsens_aggregate`` / ``cancellation_worsens_aggregate``), the rcl
  decision-content ref (``decision_content_ref`` / ``grant_identity_of`` /
  ``applicable_risk_scopes_of``), and the spg step-7 bool (``aggregate_effect_within``). Every
  produced value has a **defining predicate** here (design #13 MAJOR-1 — no produced value
  without a definition).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` + the rcl ``CapacityVector`` type only;
no ``shared.*``, no other sibling ``tos.*`` (design #13 §0.3).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from tos.are.records import (
    AdverseIncrementResult,
    AdverseScenarioSet,
    AggregateRiskAuthorityEffect,
    AggregateRiskDecision,
    AggregateRiskPolicy,
    AggregateRiskStateSnapshot,
    BenefitProof,
    CancellationRiskInputs,
    ProjectedCell,
    RiskDimensionDescriptor,
    ValuationInputs,
)
from tos.are.vocabulary import (
    AdverseScenarioKind,
    RiskDecisionResult,
    RiskDimensionKind,
    RiskScopeKind,
)
from tos.canonical import CanonicalizationScheme
from tos.rcl import CapacityComponent, CapacityVector

__all__ = [
    # core §5
    "snapshot_scope_complete",
    "exact_effect_snapshot_binding",
    "adverse_increment",
    "dimension_vector_integrity",
    "valuation_conservative",
    "numerical_safety",
    "risk_decision",
    "envelope_bound_not_enlarged",
    # predicate-only §6
    "benefit_admissible",
    "numerical_determinism",
    "protective_creates_nothing",
    "grants_no_authority",
    # produced protective magnitudes (§3.4 / §5.3)
    "final_conservative_risk",
    "current_conservative_risk",
    "no_action_risk",
    "worst_intermediate_risk",
    "credible_space_bounded",
    "no_credible_intermediate_increases_exceedance",
    "already_exceeded_regime",
    # produced cancellation-arbiter flags (§3.4)
    "continued_existence_worsens_aggregate",
    "cancellation_worsens_aggregate",
    # produced rcl seam (§3.4)
    "decision_content_ref",
    "grant_identity_of",
    "applicable_risk_scopes_of",
    # produced spg seam (§3.4)
    "aggregate_effect_within",
]


# ===========================================================================
# Internal fail-closed reductions (dominance / conjunction / disjunction)
# ===========================================================================


def _max_or_none(values: Sequence[Decimal | None]) -> Decimal | None:
    """Return the maximum (dominance) of ``values``; ``None`` if empty or any is ``None``.

    An empty sequence yields ``None`` (no credible aggregate can be established — fail-closed,
    §4.7); a single ``None`` yields ``None`` (UNKNOWN propagates conservatively, §4.1). This is
    the conservative-dominance reduction (``max_q``, §12 line 317).
    """
    result: Decimal | None = None
    seen = False
    for value in values:
        if value is None:
            return None
        seen = True
        result = value if result is None else max(result, value)
    return result if seen else None


def _all_true_or_none(flags: Sequence[bool | None]) -> bool | None:
    """Conjunction with fail-closed ``None``: ``True`` only if every flag is ``True``.

    Empty => ``None`` (fail-closed, §4.7); any ``False`` => ``False``; any ``None`` (and no
    ``False``) => ``None`` (UNKNOWN). Used for the credible-space-bounded / no-exceedance
    witnesses (§6.2).
    """
    if not flags:
        return None
    saw_none = False
    for flag in flags:
        if flag is False:
            return False
        if flag is None:
            saw_none = True
    return None if saw_none else True


def _any_true_or_none(flags: Sequence[bool | None]) -> bool | None:
    """Disjunction with fail-closed ``None``: ``True`` if any flag is ``True``.

    Empty => ``None`` (fail-closed, §4.7); any ``True`` => ``True``; else ``None`` if any is
    ``None`` (UNKNOWN), otherwise ``False``. Used for the already-exceeded regime (a single
    exceeded scope makes the regime exceeded — conservative).
    """
    if not flags:
        return None
    saw_none = False
    for flag in flags:
        if flag is True:
            return True
        if flag is None:
            saw_none = True
    return None if saw_none else False


# ===========================================================================
# Produced protective magnitudes (§3.4 / §5.3) — the defining predicates
# ===========================================================================


def final_conservative_risk(cells: Sequence[ProjectedCell]) -> Decimal | None:
    """The worst-case conservative final-state risk across cells (protective seam, §5.3).

    ``max_q`` (dominance) of each cell's injected ``final_conservative_risk`` — the §6.1
    final-state comparison value after the proposed action. Fills protective
    ``AggregateRiskComparison.final_conservative_risk`` (``protective/records.py:149``); a
    ``None`` propagates to ``RISK_INCREASING_DENIED`` (``predicates.py:289-290``).
    """
    return _max_or_none([cell.final_conservative_risk for cell in cells])


def current_conservative_risk(cells: Sequence[ProjectedCell]) -> Decimal | None:
    """The worst-case conservative current-state risk across cells (protective seam, §5.3).

    ``max_q`` of each cell's injected ``current_conservative_risk``. Fills protective
    ``AggregateRiskComparison.current_conservative_risk`` (``protective/records.py:150``).
    """
    return _max_or_none([cell.current_conservative_risk for cell in cells])


def no_action_risk(cells: Sequence[ProjectedCell]) -> Decimal | None:
    """The worst-case no-action risk across cells (protective seam, §5.3).

    Fills protective ``AggregateRiskComparison.no_action_risk`` (``protective/records.py:151``).
    """
    return _max_or_none([cell.no_action_risk for cell in cells])


def worst_intermediate_risk(cells: Sequence[ProjectedCell]) -> Decimal | None:
    """The worst credible intermediate-state risk across cells (§6.2 protective seam).

    Fills protective ``IntermediateStateWitness.worst_intermediate_risk``
    (``protective/records.py:166``). Covers the worst credible partial-fill / ordering /
    leg-failure / late-fill / basis / liquidity / margin intermediate (§6.2).
    """
    return _max_or_none([cell.worst_intermediate_risk for cell in cells])


def credible_space_bounded(cells: Sequence[ProjectedCell]) -> bool | None:
    """Whether every cell's credible state space is bounded (§6.2 / §19 line 470).

    ``True`` only when every cell is positively bounded; an unbounded / unknown space is
    ``None`` / ``False`` (never silently excluded, §19 line 470 "trapped exposure /
    containment, not permission"). Fills protective
    ``IntermediateStateWitness.credible_space_bounded`` (``protective/records.py:167``).
    """
    return _all_true_or_none([cell.credible_space_bounded for cell in cells])


def no_credible_intermediate_increases_exceedance(
    cells: Sequence[ProjectedCell],
) -> bool | None:
    """Whether no credible intermediate increases hard-limit exceedance (§6.2 protective seam).

    Fills protective ``IntermediateStateWitness.no_credible_intermediate_increases_exceedance``
    (``protective/records.py:168``); fail-closed conjunction.
    """
    return _all_true_or_none(
        [cell.no_credible_intermediate_increases_exceedance for cell in cells]
    )


def already_exceeded_regime(cells: Sequence[ProjectedCell]) -> bool | None:
    """Whether any cell reports the already-exceeded regime (protective seam, §5.3).

    Conservative disjunction (a single exceeded scope makes the regime exceeded). Fills
    protective ``AggregateRiskComparison.already_exceeded_regime`` (``protective/records.py:152``).
    """
    return _any_true_or_none([cell.already_exceeded_regime for cell in cells])


# ===========================================================================
# core §5.1 — snapshot scope completeness (ARE-EV-001 substrate)
# ===========================================================================


def snapshot_scope_complete(
    snapshot: AggregateRiskStateSnapshot | None,
    required_scopes: frozenset[RiskScopeKind],
    *,
    all_fields_attributed: bool | None,
) -> bool:
    """Whether the snapshot covers every applicable scope with full attribution (§5.1 / §9).

    ARE-INV-001 line 152: ``True`` **only** when the snapshot exists, every required scope is
    covered, and every field carries its source / continuity / observation-time / unit /
    mapping / confidence / lineage (§9 line 258, the injected ``all_fields_attributed``
    witness). §9 line 262: "A proposer, evaluator shard, model, cache, or read replica cannot
    declare a missing scope immaterial" — an omitted scope fails closed. An **empty**
    ``required_scopes`` fails closed (a vacuous "complete over nothing" is not completeness,
    §4.7).

    Args:
        snapshot: The aggregate state snapshot (``None`` => not complete).
        required_scopes: The applicable scopes that MUST be covered (empty => fail-closed).
        all_fields_attributed: Whether every field carries full lineage / attribution
            (``None`` / ``False`` => fail-closed).

    Returns:
        ``True`` iff the snapshot is scope-complete and fully attributed.
    """
    if snapshot is None:
        return False
    if not required_scopes:
        return False
    if all_fields_attributed is not True:
        return False
    covered = frozenset(snapshot.covered_scopes)
    return required_scopes <= covered


# ===========================================================================
# core §5.2 — exact effect + snapshot binding (ARE-EV-002 substrate)
# ===========================================================================


def exact_effect_snapshot_binding(
    *,
    snapshot_digest: str | None,
    scenario_set_digest: str | None,
    effect_digest: str | None,
    expected_snapshot_digest: str | None,
    expected_scenario_set_digest: str | None,
    expected_effect_digest: str | None,
) -> bool:
    """Whether one exact snapshot / scenario-set / effect digest set is bound (§5.2 / §16).

    ARE-INV-002 line 158: a decision binds **one exact** current Economic Effect Envelope and
    "cannot be patched, widened, narrowed, unioned, or substituted." ``True`` **only** when
    every presented digest is concrete and equals its expected value (a substituted / patched /
    partial-refresh / replayed digest, or any ``None``, fails closed — §26 ARE-AC-002 "No mixed
    decision may pass").

    Args:
        snapshot_digest: The presented snapshot digest.
        scenario_set_digest: The presented scenario-set digest.
        effect_digest: The presented effect digest.
        expected_snapshot_digest: The digest the decision must bind.
        expected_scenario_set_digest: The scenario-set digest the decision must bind.
        expected_effect_digest: The effect digest the decision must bind.

    Returns:
        ``True`` iff all three presented digests are concrete and match exactly.
    """
    presented = (snapshot_digest, scenario_set_digest, effect_digest)
    expected = (
        expected_snapshot_digest,
        expected_scenario_set_digest,
        expected_effect_digest,
    )
    if any(value is None for value in presented + expected):
        return False
    return presented == expected


# ===========================================================================
# core §5.3 — conservative projection + adverse increment (ARE-EV-003 substrate)
# ===========================================================================


def _scenario_coverage_sufficient(
    scenario_set: AdverseScenarioSet | None,
    required_scenario_kinds: frozenset[AdverseScenarioKind],
) -> bool:
    """Whether the scenario set meets the injected min-coverage floor (§11 / §4.7).

    Fail-closed: a ``None`` set, an **empty** injected floor, or a floor not fully covered all
    fail (§5.4 line 128 "Absence from the set is not proof"; §11 line 301 min-coverage floor).
    """
    if scenario_set is None:
        return False
    if not required_scenario_kinds:
        return False
    return required_scenario_kinds <= scenario_set.covered_kinds()


def adverse_increment(
    cells: Sequence[ProjectedCell],
    scenario_set: AdverseScenarioSet | None,
    *,
    required_scenario_kinds: frozenset[AdverseScenarioKind],
) -> AdverseIncrementResult:
    """Project the conservative adverse increment over all credible scenarios (§5.3 / §12).

    Computes ``AdverseIncrement[s,d] = max_q(ProjectedUsage - ConservativeCurrentUsageAlready
    Committed)`` (§12 line 317) as an rcl :class:`~tos.rcl.CapacityVector` (type-level
    dominance, design #13 §0.4c) and the projection-level verdict:

    * ``UNKNOWN`` whenever the adverse-scenario coverage floor is unmet, there are no cells, or
      any cell's projected usage / increment / headroom is ``None`` (a smaller vector is never
      returned, §1 line 29; ARE-INV-003 favorable-final-intent never erases a credible
      temporary effect, §12 line 328);
    * ``DENY`` when the projection is determinate but some cell's requested increment exceeds
      its headroom (§12 line 326 "pass" fails);
    * ``GRANT`` when determinate and every cell is within headroom (the projection-level pass;
      :func:`risk_decision` applies the remaining integrity gates).

    The produced protective magnitudes (§3.4) are attached for the protective seam.

    Args:
        cells: The per-(scope, dimension, scenario) projection cells.
        scenario_set: The bound adverse scenario set (``None`` => UNKNOWN).
        required_scenario_kinds: The injected min-coverage floor (empty => UNKNOWN).

    Returns:
        The :class:`~tos.are.records.AdverseIncrementResult`.
    """
    coverage_ok = _scenario_coverage_sufficient(scenario_set, required_scenario_kinds)

    # Group cells by (scope, dimension) and take max_q of the requested increment.
    _Key = tuple[RiskScopeKind | None, RiskDimensionKind | None]
    order: list[_Key] = []
    grouped: dict[_Key, list[Decimal | None]] = {}
    determinate = coverage_ok and bool(cells)
    for cell in cells:
        key = (cell.scope, cell.dimension)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        increment = cell.requested_increment()
        grouped[key].append(increment)
        if increment is None or cell.headroom() is None:
            determinate = False

    components: list[CapacityComponent] = []
    all_within_headroom = determinate
    for key in order:
        scope, dimension = key
        magnitude = _max_or_none(grouped[key])
        scope_token = scope.value if scope is not None else "<unknown-scope>"
        dim_token = dimension.value if dimension is not None else "<unknown-dimension>"
        components.append(
            CapacityComponent(
                dimension_id=f"{scope_token}::{dim_token}", magnitude=magnitude
            )
        )
        if magnitude is None:
            determinate = False

    if determinate:
        for cell in cells:
            increment = cell.requested_increment()
            headroom = cell.headroom()
            if increment is None or headroom is None:
                all_within_headroom = False
                determinate = False
                break
            if increment > headroom:
                all_within_headroom = False

    if not determinate:
        result = RiskDecisionResult.UNKNOWN
    elif all_within_headroom:
        result = RiskDecisionResult.GRANT
    else:
        result = RiskDecisionResult.DENY

    return AdverseIncrementResult(
        result=result,
        increment=CapacityVector(components=tuple(components)),
        final_conservative_risk=final_conservative_risk(cells),
        current_conservative_risk=current_conservative_risk(cells),
        no_action_risk=no_action_risk(cells),
        worst_intermediate_risk=worst_intermediate_risk(cells),
        credible_space_bounded=credible_space_bounded(cells),
        no_credible_intermediate_increases_exceedance=(
            no_credible_intermediate_increases_exceedance(cells)
        ),
        already_exceeded_regime=already_exceeded_regime(cells),
    )


# ===========================================================================
# core §5.4 — dimension / unit / scope / limit integrity (ARE-EV-004 substrate)
# ===========================================================================


def dimension_vector_integrity(
    descriptors: Sequence[RiskDimensionDescriptor],
    cells: Sequence[ProjectedCell],
    *,
    higher_scope_limits_known: bool | None,
) -> bool:
    """Whether every governed dimension has explicit, complete vector semantics (§5.4 / §10).

    ARE-INV-004 line 166: ``True`` **only** when there is at least one descriptor, each
    descriptor carries a concrete dimension / scope / unit / sign / limit-source and a
    non-``None`` cross-dimension ``conversion_coefficient`` (a Critical Input that "cannot
    silently default", §10 line 281), every projected cell's dimension has a descriptor, and
    the injected ``higher_scope_limits_known`` is positively ``True`` (§10 line 283 "no
    lower-dimensional projection may pass if an applicable higher-dimensional or cross-scope
    limit is unknown"). An **empty** descriptor set fails closed (§4.7); a scalar can never
    substitute for the vector (§1 line 21).

    Args:
        descriptors: The governed-dimension descriptors (empty => fail-closed).
        cells: The projected cells whose dimensions must all be described.
        higher_scope_limits_known: Whether every applicable higher / cross-scope limit is
            known (``None`` / ``False`` => fail-closed).

    Returns:
        ``True`` iff every dimension's vector semantics are explicit and complete.
    """
    if not descriptors:
        return False
    if higher_scope_limits_known is not True:
        return False
    described = set()
    for descriptor in descriptors:
        if (
            descriptor.dimension is None
            or descriptor.scope is None
            or descriptor.unit is None
            or descriptor.sign_convention is None
            or descriptor.limit_source is None
            or descriptor.conversion_coefficient is None
        ):
            return False
        described.add(descriptor.dimension)
    for cell in cells:
        if cell.dimension is None or cell.dimension not in described:
            return False
    return True


# ===========================================================================
# core §5.5 — valuation + numerical safety (ARE-EV-006 substrate)
# ===========================================================================


def valuation_conservative(inputs: ValuationInputs) -> bool:
    """Whether valuation is conservative on every axis (§5.5 / §14 line 350-354).

    §14 line 352: observation / executable / stress / liquidation / settlement / conversion
    prices — and stale / unknown — must be distinguished, and "A zero, negative, future,
    crossed, stale, or missing value is not automatically conservative." A broker figure is a
    ceiling / observation, never proof the local model may omit exposure (§14 line 354).
    ``True`` **only** when every injected flag is positively ``True`` (any ``None`` / ``False``
    fails closed).

    Args:
        inputs: The injected valuation classification flags.

    Returns:
        ``True`` iff valuation is conservative on every axis.
    """
    return (
        inputs.price_classes_distinguished is True
        and inputs.stale_or_unknown_flagged is True
        and inputs.no_zero_negative_future_crossed_as_conservative is True
        and inputs.broker_figure_treated_as_ceiling_only is True
        and inputs.local_or_broker_more_restrictive_dominates is True
    )


def numerical_safety(
    magnitudes: Sequence[Decimal | None],
    *,
    units_consistent: bool | None,
) -> RiskDecisionResult | bool:
    """Whether the magnitudes are numerically safe (§5.5 / §14 line 356-366; ARE-INV-008).

    Returns :attr:`~tos.are.vocabulary.RiskDecisionResult.UNKNOWN` — **never a smaller
    permissive vector** (§1 line 29; §26 ARE-AC-007) — when the units are not consistent, the
    magnitude sequence is **empty** (a vacuous "safe over nothing" is not safety — fail-closed,
    §4.7, symmetric with the module's other empty-input reductions), or any magnitude is absent
    / non-finite (NaN / infinity / overflow / underflow; a non-finite ``CanonicalDecimal`` is
    already unconstructable as a model field, so this gate also covers raw injected magnitudes).
    Otherwise returns ``True``. The §14 line 365 fallbacks ("return zero", "use last value",
    "skip failed scenario", "accept optimizer incumbent", "trust broker validation") are
    **not** implemented — none is a conservative upper bound.

    **Return contract (truthy trap seal):** the "safe" result is the singleton ``True`` and the
    "unsafe" result is ``RiskDecisionResult.UNKNOWN`` — but the ``UNKNOWN`` StrEnum is *truthy*,
    so a consumer MUST test ``is True`` (never a bare truthiness check). :func:`risk_decision`
    consumes this via an ``is not True`` gate, so a raw wiring of this return into it is safe.

    Args:
        magnitudes: The magnitudes to check (empty / ``None`` / non-finite => UNKNOWN).
        units_consistent: Whether the units are consistent (``None`` / ``False`` => UNKNOWN).

    Returns:
        ``True`` if numerically safe, else ``RiskDecisionResult.UNKNOWN``.
    """
    if units_consistent is not True:
        return RiskDecisionResult.UNKNOWN
    if not magnitudes:
        return RiskDecisionResult.UNKNOWN
    for magnitude in magnitudes:
        if magnitude is None or not magnitude.is_finite():
            return RiskDecisionResult.UNKNOWN
    return True


# ===========================================================================
# core §5.6 — risk decision integrity + envelope-not-enlarged (ARE-EV-002/004)
# ===========================================================================


def envelope_bound_not_enlarged(
    *,
    decision_effective_limit: CapacityVector,
    injected_envelope_max: CapacityVector | None,
    limit_source_is_injected_envelope: bool | None,
) -> bool:
    """Whether the decision's effective limit does not enlarge the Hard Safety Envelope (§5.6).

    ARE-INV-007 line 178 verbatim: "Neither runtime policy, strategy, human approval, broker
    result, nor model output may enlarge the Hard Safety Envelope or single-action bound."
    ``True`` **only** when the limit source is positively the injected envelope
    (``limit_source_is_injected_envelope is True`` — a runtime / strategy / human / broker /
    model source fails closed), the injected envelope is present, and every dimension of the
    effective limit is declared by the envelope and ``<=`` its maximum (a ``None`` on either
    side, or an effective value above the envelope max, fails closed). The Runtime Safety
    Profile may narrow only (§1 line 27; spg-owned), so a profile value can never enlarge here.

    **Empty effective limit (intentional interpretation):** an effective limit with **no**
    components declares zero dimensions — i.e. zero headroom, the most restrictive possible
    bound, never a wildcard / unbounded grant — so it enlarges nothing and returns ``True``
    *only* after the positive ``limit_source_is_injected_envelope is True`` gate has already
    passed (a ``None`` / ``False`` source still fails closed). The empty-scope restrictiveness a
    caller cares about is enforced separately in :func:`risk_decision` (empty
    ``applicable_risk_scopes`` => DENY), so this predicate stays narrowly "did the source
    enlarge the envelope".

    Args:
        decision_effective_limit: The decision's effective-limit vector.
        injected_envelope_max: The injected Hard Safety Envelope maxima (``None`` => fail-closed).
        limit_source_is_injected_envelope: Whether the limit came from the injected envelope
            (``None`` / ``False`` => fail-closed).

    Returns:
        ``True`` iff the effective limit does not enlarge the envelope.
    """
    if injected_envelope_max is None:
        return False
    if limit_source_is_injected_envelope is not True:
        return False
    for component in decision_effective_limit.components:
        dimension = component.dimension_id
        effective = component.magnitude
        if dimension is None or effective is None:
            return False
        envelope_max = injected_envelope_max.magnitude(dimension)
        if envelope_max is None:
            return False
        if effective > envelope_max:
            return False
    return True


def _decide_result(
    *,
    projection: AdverseIncrementResult,
    snapshot: AggregateRiskStateSnapshot | None,
    applicable_risk_scopes: tuple[str, ...],
    snapshot_complete: bool,
    numerically_safe: RiskDecisionResult | bool,
    valuation_ok: bool,
    envelope_not_enlarged: bool,
) -> RiskDecisionResult:
    """The pure GRANT/DENY/UNKNOWN verdict (§5.6 / ARE-INV-006); restrictive-by-default.

    ``numerically_safe`` is gated with ``is not True`` (never a bare truthiness check): the raw
    :func:`numerical_safety` return is ``RiskDecisionResult.UNKNOWN`` on any defect, and that
    StrEnum is *truthy* — an ``if not numerically_safe`` check would let an UNKNOWN slip through
    toward GRANT. The ``is not True`` gate treats every non-``True`` value (``False`` **or**
    ``RiskDecisionResult.UNKNOWN``) as restrictive, so a raw wiring of ``numerical_safety`` is
    safe (MAJOR-1 truthy-trap seal).
    """
    if projection.result is RiskDecisionResult.UNKNOWN:
        return RiskDecisionResult.UNKNOWN
    if snapshot is None or not snapshot_complete:
        return RiskDecisionResult.UNKNOWN
    if numerically_safe is not True or not valuation_ok:
        return RiskDecisionResult.UNKNOWN
    # empty requested scope => restrictive, never a wildcard / unbounded grant (§15 line 385).
    if not applicable_risk_scopes:
        return RiskDecisionResult.DENY
    if not envelope_not_enlarged:
        return RiskDecisionResult.DENY
    if projection.result is RiskDecisionResult.DENY:  # increment > headroom (§5.6)
        return RiskDecisionResult.DENY
    return RiskDecisionResult.GRANT


def risk_decision(
    *,
    projection: AdverseIncrementResult,
    snapshot: AggregateRiskStateSnapshot | None,
    applicable_risk_scopes: tuple[str, ...],
    snapshot_complete: bool,
    numerically_safe: RiskDecisionResult | bool,
    valuation_ok: bool,
    envelope_not_enlarged: bool,
    decision_id: str,
    decision_generation: int,
    scheme: CanonicalizationScheme,
    policy: AggregateRiskPolicy | None = None,
    scenario_set: AdverseScenarioSet | None = None,
    effective_limit: CapacityVector | None = None,
    grant_identity: str | None = None,
    effect_digest: str | None = None,
) -> AggregateRiskDecision:
    """Decide GRANT / DENY / UNKNOWN and issue the forward-only decision (§5.6 / §15 / §16).

    ARE-INV-006 line 173: a decision is possible **only** with a determinate projection; a
    requested increment above headroom is ``DENY``; any UNKNOWN current / exposure / valuation /
    scenario / mapping state is ``UNKNOWN`` (which consumes conservative capacity and blocks new
    risk — not permissive); an empty requested scope is restrictive (never a wildcard grant,
    §15 line 385). The issued :class:`~tos.are.records.AggregateRiskDecision` is
    **forward-only** — it carries **no** reservation coordinate (rcl charges ``bound_reservation_*``
    post-commit, §16 line 413) — and its ``authority_effect`` is all-false (a GRANT is not
    capacity, ARE-INV-009). The ``scheme`` is the injected provisional canonicalizer (REUSE,
    §3.1; no new scheme).

    Args:
        projection: The adverse-increment projection result.
        snapshot: The bound aggregate state snapshot (``None`` => UNKNOWN).
        applicable_risk_scopes: The exact scopes the decision authorizes (empty => restrictive).
        snapshot_complete: Whether :func:`snapshot_scope_complete` held (``False`` => UNKNOWN).
        numerically_safe: The :func:`numerical_safety` result (``True`` **or** the raw
            ``RiskDecisionResult.UNKNOWN`` sentinel — anything not ``True`` => UNKNOWN; the
            ``is not True`` gate seals the truthy-UNKNOWN trap so a raw wiring is safe).
        valuation_ok: Whether :func:`valuation_conservative` held (``False`` => UNKNOWN).
        envelope_not_enlarged: Whether :func:`envelope_bound_not_enlarged` held (``False`` => DENY).
        decision_id: The evaluation-assigned independent decision identity (id ⊥ digest, §3.1).
        decision_generation: The monotonic decision generation (required covered).
        scheme: The injected canonicalization scheme.
        policy: The bound policy (for the policy digest).
        scenario_set: The bound scenario set (for the scenario-set digest).
        effective_limit: The decision's effective-limit vector.
        grant_identity: The aggregate-risk authority grant identity (rcl seam).
        effect_digest: The bound economic-effect digest.

    Returns:
        The issued forward-only :class:`~tos.are.records.AggregateRiskDecision`.
    """
    result = _decide_result(
        projection=projection,
        snapshot=snapshot,
        applicable_risk_scopes=applicable_risk_scopes,
        snapshot_complete=snapshot_complete,
        numerically_safe=numerically_safe,
        valuation_ok=valuation_ok,
        envelope_not_enlarged=envelope_not_enlarged,
    )
    decision = AggregateRiskDecision.issue(
        scheme=scheme,
        decision_id=decision_id,
        decision_generation=decision_generation,
        result=result,
        policy_digest=policy.canonical_digest if policy is not None else None,
        snapshot_digest=snapshot.canonical_digest if snapshot is not None else None,
        scenario_set_digest=(
            scenario_set.canonical_digest if scenario_set is not None else None
        ),
        effect_digest=effect_digest,
        applicable_risk_scopes=applicable_risk_scopes,
        grant_identity=grant_identity,
        adverse_increment=projection.increment,
        effective_limit=(
            effective_limit if effective_limit is not None else CapacityVector()
        ),
    )
    assert isinstance(decision, AggregateRiskDecision)
    return decision


# ===========================================================================
# predicate-only §6.1 — benefit admissibility (ARE-EV-005 substrate)
# ===========================================================================


def benefit_admissible(proof: BenefitProof) -> bool:
    """Whether a claimed benefit is admissible on all seven §13 premises (§6.1 / ARE-INV-005).

    §13 line 336-342: a netting / hedge / diversification / collateral / margin-offset /
    liquidity / correlation benefit reduces adverse capacity **only when positively proven** on
    every premise. ``True`` **only** when all seven are ``True``; any unproven premise yields
    ``False`` (benefit removed / conservatively bounded — §13 line 344; ARE-INV-005 line 170).
    A bare :class:`~tos.are.records.BenefitProof` (all premises defaulting ``False``) is
    ``False`` (∅-seal, §4.2); a broker margin number / historical correlation / shared model
    output / recent co-movement / strategy label / human assertion is not a premise flag, so it
    can never count as proof (§13 line 344).

    Args:
        proof: The benefit proof.

    Returns:
        ``True`` iff every premise is positively proven.
    """
    return (
        proof.exact_identity_and_eligibility is True
        and proof.current_enforceable_state_and_fqp is True
        and proof.simultaneous_availability is True
        and proof.approved_basis_correlation_liquidity_stress is True
        and proof.margin_recognition is True
        and proof.no_undeclared_common_mode is True
        and proof.complete_adverse_leg_failure_scenario is True
    )


# ===========================================================================
# predicate-only §6.2 — numerical determinism (ARE-EV-007 substrate)
# ===========================================================================


def numerical_determinism(
    *,
    canonical_representation: bool | None,
    deterministic_ordering: bool | None,
    parser_library_model_agreement: bool | None,
    convergence_established: bool | None,
) -> bool:
    """Whether numeric evaluation is deterministic beyond the L1 finite check (§6.2 / §14).

    §14 line 360: a non-deterministic order or a parser / library / model disagreement, or a
    non-convergent computation, is UNKNOWN. ``True`` **only** when every injected witness is
    positively ``True`` (any ``None`` / ``False`` fails closed). The differential / independent
    reproduction itself is EV-L2 component-fault / +Security (ARE-EV-007) — this authors only
    the L1-decidable substrate.

    Returns:
        ``True`` iff numeric evaluation is deterministic on every axis.
    """
    return (
        canonical_representation is True
        and deterministic_ordering is True
        and parser_library_model_agreement is True
        and convergence_established is True
    )


# ===========================================================================
# predicate-only §6.5 — protective creates nothing (ARE-EV-010 substrate)
# ===========================================================================


def protective_creates_nothing(
    *,
    label_creates_capacity: bool | None,
    label_creates_feasibility: bool | None,
    label_creates_allocation: bool | None,
    label_creates_transmission: bool | None,
) -> bool:
    """Whether an exit / reduce-only / emergency label creates nothing (§6.5 / ARE-INV-012).

    §19 line 470: a protective label creates no capacity, feasibility, allocation, or
    transmission — feasibility / capacity unknown is trapped exposure / containment, never
    permission. ``True`` **only** when every "creates X" claim is positively ``False`` (a
    ``True`` claim is inadmissible; a ``None`` is UNKNOWN and fails closed).

    Returns:
        ``True`` iff the protective label creates nothing.
    """
    return (
        label_creates_capacity is False
        and label_creates_feasibility is False
        and label_creates_allocation is False
        and label_creates_transmission is False
    )


# ===========================================================================
# predicate-only §6.7 — authority separation / all-false (ARE-EV-011 substrate)
# ===========================================================================


def grants_no_authority(effect: AggregateRiskAuthorityEffect) -> bool:
    """Whether the authority effect grants nothing (§6.7 / ARE-INV-009 / §7 line 217).

    ``True`` **only** when every authority flag is ``False``. Because
    :class:`~tos.are.records.AggregateRiskAuthorityEffect` is unconstructable with any ``True``
    flag, a constructed effect always grants nothing — this is the defining predicate that
    states it (§23 line 547: the Aggregate Risk Authority holds no usable live-order
    credential / signer / broker session / broker-order route; the +Security enforcement proof
    is ARE-EV-011).

    Returns:
        ``True`` iff the effect grants no authority.
    """
    return not (
        effect.creates_capacity
        or effect.permits_transmission
        or effect.issues_live_authorization
        or effect.grants_broker_permission
        or effect.may_rearm
    )


# ===========================================================================
# produced cancellation-arbiter flags (§3.4)
# ===========================================================================


def continued_existence_worsens_aggregate(
    inputs: CancellationRiskInputs,
) -> bool | None:
    """Whether continued order existence worsens conservative aggregate risk (§3.4).

    ``True`` when the continued-existence risk exceeds the baseline no-action risk; ``None``
    (fail-closed) when either magnitude is absent. Fills protective
    ``cancellation_admissible``'s ``continued_existence_worsens_aggregate`` argument
    (``protective/predicates.py:529``; ``None`` => most-restrictive).

    Returns:
        ``True`` / ``False`` / ``None`` (fail-closed).
    """
    risk = inputs.continued_existence_risk
    baseline = inputs.baseline_no_action_risk
    if risk is None or baseline is None:
        return None
    return risk > baseline


def cancellation_worsens_aggregate(inputs: CancellationRiskInputs) -> bool | None:
    """Whether cancelling the order worsens conservative aggregate risk (§3.4).

    ``True`` when the post-cancellation risk exceeds the baseline no-action risk; ``None``
    (fail-closed) when either magnitude is absent. Fills protective ``cancellation_admissible``'s
    ``cancellation_worsens_aggregate`` argument (``protective/predicates.py:531``; only a
    positive ``False`` permits ordinary cancellation, so ``None`` fails closed).

    Returns:
        ``True`` / ``False`` / ``None`` (fail-closed).
    """
    risk = inputs.post_cancellation_risk
    baseline = inputs.baseline_no_action_risk
    if risk is None or baseline is None:
        return None
    return risk > baseline


# ===========================================================================
# produced rcl seam (§3.4) — forward-only decision content ref
# ===========================================================================


def decision_content_ref(
    decision: AggregateRiskDecision,
) -> tuple[str | None, int | None, str | None]:
    """The forward-only ``(decision_id, decision_generation, canonical_decision_digest)`` (§3.4).

    The exact content-ref scalars rcl ``GrantDecisionRef`` consumes (``authority.py:53-55``);
    ``canonical_decision_digest`` is the decision's own ``canonical_digest`` (id ⊥ digest,
    §3.1). **No** reservation coordinate is produced — rcl charges ``bound_reservation_*``
    post-commit (non-cyclic, §16 line 413).

    Returns:
        The ``(decision_id, decision_generation, canonical_decision_digest)`` tuple.
    """
    return (
        decision.decision_id,
        decision.decision_generation,
        decision.canonical_digest,
    )


def grant_identity_of(decision: AggregateRiskDecision) -> str | None:
    """The aggregate-risk authority grant identity (rcl ``records.py:99`` seam, §3.4)."""
    return decision.grant_identity


def applicable_risk_scopes_of(decision: AggregateRiskDecision) -> tuple[str, ...]:
    """The applicable risk scopes the decision authorizes (rcl ``records.py:98`` seam, §3.4)."""
    return decision.applicable_risk_scopes


# ===========================================================================
# produced spg seam (§3.4) — semantic-validation step 7 bool
# ===========================================================================


def aggregate_effect_within(
    *,
    decision_effective_limit: CapacityVector,
    injected_envelope_max: CapacityVector | None,
    limit_source_is_injected_envelope: bool | None,
) -> bool:
    """The spg semantic-validation step-7 ``aggregate_effect_within`` bool (§3.4 / §8).

    ``True`` **only** when the aggregate risk effect stays within the injected Hard Safety
    Envelope (:func:`envelope_bound_not_enlarged`). Fills spg
    ``SemanticValidationInputs.aggregate_effect_within`` (``spg/records.py:205``; spg
    ``predicates.py:466`` rejects unless ``is True``). are consumes the envelope (injected) and
    produces this bool — both directions injected, so are ↔ spg stays acyclic (§3.4).

    Returns:
        ``True`` iff the aggregate effect is within the injected envelope.
    """
    return envelope_bound_not_enlarged(
        decision_effective_limit=decision_effective_limit,
        injected_envelope_max=injected_envelope_max,
        limit_source_is_injected_envelope=limit_source_is_injected_envelope,
    )
