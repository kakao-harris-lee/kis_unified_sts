"""§3 Order Construction — the G5 derivation's determinism, boundedness, and no-repair rule.

Design #34 §12.1-5 targets: "동일 입력→동일 command/digest·미지 가격→denial(no default)·envelope
밖→denial(no repair)·Q-MIC-3 조용한 폴백 뮤테이션 KILLED."

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

from decimal import Decimal, localcontext

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from tos.brokeradapter import SyntheticFillPolicy, SyntheticPaperTransport
from tos.egressgw import (
    DERIVED_AXES,
    AllFalseConstructionCoordinatorAuthority,
    ConformanceProofStage,
    DerivationOutcome,
    EconomicEffectStage,
    LotRoundingPolicy,
    OrderConstructionStage,
    ProposedConstructionEnvelope,
    VenueConstraintStage,
    candidate_command_verdict,
    derive_economic_effect_envelope,
    derive_order_size,
    fold_venue_admissibility,
)
from tos.engine import CONFIG_CONTEXT_SOURCE, CommitmentStep, StageOutcome
from tos.ioc import AxisBinding, ConformanceAxis, ConformanceResult, QuantityUnitKind
from tos.venue import ActionClass, OrderAdmissibilityResult

from ._egressgw_fixtures import (
    LOT_SIZE,
    MAX_QUANTITY,
    PRICE,
    SCHEME,
    SESSION_PHASE,
    admitted_price,
    construction,
    non_derived_axes,
    proposed_envelope,
    sizing_bound,
    venue_decision,
    venue_policy,
    venue_quantity_constraint,
    venue_shape,
    venue_shape_constraints,
    venue_snapshot,
)


def _derive(**overrides):
    """Run the derivation with the suite's baseline and the given single override."""
    return derive_order_size(
        quantity_basis=overrides.pop("quantity_basis", "RISK"),
        envelope=overrides.pop("envelope", proposed_envelope()),
        price=overrides.pop("price", admitted_price()),
        venue_constraint=overrides.pop("venue_constraint", venue_quantity_constraint()),
    )


# ---------------------------------------------------------------------------
# determinism (IOC-INV-002; design #34 §3.1 / §12.1-5)
# ---------------------------------------------------------------------------


def test_the_baseline_derivation_produces_the_authored_bounded_size() -> None:
    """(§3.1) risk_budget / per_unit_risk floored to the authored lot — 1000/50 = 20."""
    result = _derive()
    assert result.outcome is DerivationOutcome.DERIVED
    assert result.quantity == Decimal("20")
    assert result.price == PRICE
    assert result.quantity_unit is QuantityUnitKind.CONTRACTS


def test_the_same_inputs_always_produce_the_same_command_and_digest() -> None:
    """(IOC-INV-002 / §3.1) The derivation and its compile are pure — no clock, no RNG."""
    first = construction()
    second = construction()
    assert first.command is not None and second.command is not None
    assert first.command.canonical_digest == second.command.canonical_digest
    assert first.derivation == second.derivation


@settings(max_examples=50, deadline=None)
@given(
    budget=st.integers(min_value=1, max_value=10_000),
    per_unit=st.integers(min_value=1, max_value=500),
)
def test_derivation_is_a_pure_function_of_its_inputs(budget: int, per_unit: int) -> None:
    """(§3.1 determinism) Two evaluations over identical inputs agree, always."""
    bound = sizing_bound(
        risk_budget=Decimal(budget),
        per_unit_risk=Decimal(per_unit),
        max_quantity=Decimal("1000000"),
    )
    envelope = proposed_envelope(sizing_bound=bound)
    first = _derive(envelope=envelope)
    second = _derive(envelope=envelope)
    assert first == second


@settings(max_examples=50, deadline=None)
@given(budget=st.integers(min_value=1, max_value=10_000))
def test_a_derived_size_is_always_an_exact_lot_multiple_inside_the_envelope(
    budget: int,
) -> None:
    """(§3.1 boundedness) Whatever the budget, a DERIVED size is lot-exact and in-envelope."""
    envelope = proposed_envelope(
        sizing_bound=sizing_bound(risk_budget=Decimal(budget), max_quantity=Decimal("1000000"))
    )
    result = _derive(envelope=envelope, venue_constraint=venue_quantity_constraint(
        max_quantity=Decimal("1000000")
    ))
    if result.outcome is DerivationOutcome.DERIVED:
        assert result.quantity is not None
        assert result.quantity % LOT_SIZE == 0
        assert result.quantity >= sizing_bound().min_quantity


# ---------------------------------------------------------------------------
# no invent / default / normalize / round / repair (RFC-005 §7:211-213)
# ---------------------------------------------------------------------------


def test_an_unknown_price_is_a_no_send_not_a_last_known_default() -> None:
    """(§3.1 (a) / Q-MIC-3) A missing price denies; there is no fallback value."""
    result = _derive(price=admitted_price(value=None))
    assert result.outcome is DerivationOutcome.DENIED
    assert result.quantity is None and result.price is None
    assert "positive finite value" in (result.denial_reason or "")


def test_an_absent_price_observation_is_a_no_send() -> None:
    """(§3.1 (a)) No observation at all is a denial, not an implied price."""
    result = _derive(price=None)
    assert result.outcome is DerivationOutcome.DENIED


def test_a_config_sourced_price_is_refused_as_relabelling() -> None:
    """(RFC-008 §10:327-331) A market value carried as an authored constant is refused."""
    result = _derive(price=admitted_price(source=CONFIG_CONTEXT_SOURCE))
    assert result.outcome is DerivationOutcome.DENIED
    assert "relabelling" in (result.denial_reason or "")


def test_an_unstated_lot_policy_is_a_denial_never_a_silent_round() -> None:
    """(§3.1 / Q-MIC-3) The authored lot policy is mandatory; absence never defaults."""
    envelope = proposed_envelope(sizing_bound=sizing_bound(lot_rounding=None))
    result = _derive(envelope=envelope)
    assert result.outcome is DerivationOutcome.DENIED
    assert "lot policy" in (result.denial_reason or "")


def test_exact_multiple_policy_denies_rather_than_adjusting() -> None:
    """(§3.1) Under EXACT_MULTIPLE_REQUIRED a non-multiple is a denial, not an adjustment."""
    envelope = proposed_envelope(
        sizing_bound=sizing_bound(
            risk_budget=Decimal("1050"),
            lot_rounding=LotRoundingPolicy.EXACT_MULTIPLE_REQUIRED,
        )
    )
    result = _derive(envelope=envelope)
    assert result.outcome is DerivationOutcome.DENIED
    assert "EXACT_MULTIPLE_REQUIRED" in (result.denial_reason or "")


def test_a_size_above_the_envelope_ceiling_is_denied_never_clamped() -> None:
    """(ADR-002-020 §9 'outside the authorized envelope — denial') No clamp exists."""
    envelope = proposed_envelope(
        sizing_bound=sizing_bound(risk_budget=Decimal("100000"))
    )
    result = _derive(envelope=envelope)
    assert result.outcome is DerivationOutcome.DENIED
    assert "outside the authorized envelope" in (result.denial_reason or "")
    assert result.quantity is None


def test_a_size_below_the_envelope_floor_is_denied_never_raised() -> None:
    """(§3.1) A too-small size is a denial; nothing is topped up to the minimum."""
    envelope = proposed_envelope(sizing_bound=sizing_bound(risk_budget=Decimal("50")))
    result = _derive(envelope=envelope)
    assert result.outcome is DerivationOutcome.DENIED


def test_a_venue_constraint_violation_is_denied_never_adjusted() -> None:
    """(§3.1 (iv) / ADR-002-019 §12:309) The venue bound denies; it never rounds."""
    result = _derive(venue_constraint=venue_quantity_constraint(max_quantity=Decimal("4")))
    assert result.outcome is DerivationOutcome.DENIED
    assert "venue / broker quantity constraint" in (result.denial_reason or "")


def test_a_missing_venue_constraint_is_not_no_constraint() -> None:
    """(§3.1 (iv)) Absence of a constraint is a denial, never an unconstrained pass."""
    result = _derive(venue_constraint=None)
    assert result.outcome is DerivationOutcome.DENIED


def test_a_unit_mismatch_between_envelope_and_venue_denies() -> None:
    """(ADR-002-020 §11:301) A unit mismatch is prohibited, never coerced."""
    result = _derive(
        venue_constraint=venue_quantity_constraint(quantity_unit=QuantityUnitKind.SHARES)
    )
    assert result.outcome is DerivationOutcome.DENIED
    assert "unit disagreement" in (result.denial_reason or "")


def test_a_notional_ceiling_breach_is_denied_never_reduced() -> None:
    """(§3.1) A declared notional ceiling denies rather than shrinking the order."""
    envelope = proposed_envelope(sizing_bound=sizing_bound(max_notional=Decimal("100")))
    result = _derive(envelope=envelope)
    assert result.outcome is DerivationOutcome.DENIED
    assert "notional" in (result.denial_reason or "")


# ---------------------------------------------------------------------------
# exact bound boundaries (adversarial review MINOR-1 / surviving mutant N5)
# ---------------------------------------------------------------------------
#
# The mutation N5 (`> bound.max_quantity` → `> bound.max_quantity + 1`) SURVIVED the first
# suite: every ceiling test used a value far above the bound, so an off-by-one relaxation was
# invisible. The reviewer's non-equivalence witness — risk_budget 1100 / per_unit 100 / max 10 ⇒
# derived 11, which the shipped code denies and the mutant admits — is reproduced below, and the
# same class is pinned symmetrically on the envelope floor and on both venue bounds, which had
# the identical gap.
#
# ``lot_size`` is 1 for these cases on purpose: it makes "one lot above the ceiling" and "one
# unit above the ceiling" the same value, which is the tightest boundary an off-by-one can hide
# behind.

_BOUNDARY_PER_UNIT = Decimal("100")
_BOUNDARY_LOT = Decimal("1")


def _boundary_derivation(
    *,
    risk_budget: str,
    envelope_min: str = "1",
    envelope_max: str = "1000",
    venue_min: str = "1",
    venue_max: str = "1000",
):
    """Derive with lot 1 and per-unit 100, so the derived size is ``risk_budget / 100``."""
    envelope = proposed_envelope(
        sizing_bound=sizing_bound(
            risk_budget=Decimal(risk_budget),
            per_unit_risk=_BOUNDARY_PER_UNIT,
            lot_size=_BOUNDARY_LOT,
            min_quantity=Decimal(envelope_min),
            max_quantity=Decimal(envelope_max),
        )
    )
    return _derive(
        envelope=envelope,
        venue_constraint=venue_quantity_constraint(
            lot_size=_BOUNDARY_LOT,
            min_quantity=Decimal(venue_min),
            max_quantity=Decimal(venue_max),
        ),
    )


def test_a_size_exactly_at_the_envelope_ceiling_is_derived() -> None:
    """(MINOR-1, both ways) The ceiling is inclusive — ``== max_quantity`` must still derive."""
    result = _boundary_derivation(risk_budget="1000", envelope_max="10")
    assert result.outcome is DerivationOutcome.DERIVED
    assert result.quantity == Decimal("10")


def test_a_size_one_lot_above_the_envelope_ceiling_is_denied() -> None:
    """(MINOR-1 / mutant N5) ``max + 1`` denies — the exact off-by-one the mutant relaxed."""
    result = _boundary_derivation(risk_budget="1100", envelope_max="10")
    assert result.outcome is DerivationOutcome.DENIED
    assert result.quantity is None
    assert "outside the authorized envelope" in (result.denial_reason or "")


def test_a_size_exactly_at_the_envelope_floor_is_derived() -> None:
    """(MINOR-1 symmetry, both ways) The floor is inclusive — ``== min_quantity`` derives."""
    result = _boundary_derivation(risk_budget="500", envelope_min="5")
    assert result.outcome is DerivationOutcome.DERIVED
    assert result.quantity == Decimal("5")


def test_a_size_one_lot_below_the_envelope_floor_is_denied() -> None:
    """(MINOR-1 symmetry) ``min - 1`` denies — nothing is topped up to reach the floor."""
    result = _boundary_derivation(risk_budget="400", envelope_min="5")
    assert result.outcome is DerivationOutcome.DENIED
    assert "outside the authorized envelope" in (result.denial_reason or "")


def test_a_size_exactly_at_the_venue_ceiling_is_derived() -> None:
    """(MINOR-1 venue symmetry, both ways) The venue ceiling is inclusive too."""
    result = _boundary_derivation(risk_budget="1000", venue_max="10")
    assert result.outcome is DerivationOutcome.DERIVED
    assert result.quantity == Decimal("10")


def test_a_size_one_lot_above_the_venue_ceiling_is_denied() -> None:
    """(MINOR-1 venue symmetry) The same off-by-one class is pinned on the venue bound."""
    result = _boundary_derivation(risk_budget="1100", venue_max="10")
    assert result.outcome is DerivationOutcome.DENIED
    assert "venue / broker quantity constraint" in (result.denial_reason or "")


def test_a_size_exactly_at_the_venue_floor_is_derived() -> None:
    """(MINOR-1 venue symmetry, both ways) The venue floor is inclusive."""
    result = _boundary_derivation(risk_budget="500", venue_min="5")
    assert result.outcome is DerivationOutcome.DERIVED
    assert result.quantity == Decimal("5")


def test_a_size_one_lot_below_the_venue_floor_is_denied() -> None:
    """(MINOR-1 venue symmetry) Below the venue floor denies, never rounds up."""
    result = _boundary_derivation(risk_budget="400", venue_min="5")
    assert result.outcome is DerivationOutcome.DENIED
    assert "venue / broker quantity constraint" in (result.denial_reason or "")


def test_a_notional_exactly_at_the_ceiling_is_derived() -> None:
    """(MINOR-1 class sweep) The notional ceiling is inclusive: ``==`` passes, ``+1`` denies."""
    exactly = proposed_envelope(
        sizing_bound=sizing_bound(max_notional=Decimal("20") * PRICE)
    )
    assert _derive(envelope=exactly).outcome is DerivationOutcome.DERIVED
    over = proposed_envelope(
        sizing_bound=sizing_bound(max_notional=Decimal("20") * PRICE - 1)
    )
    assert _derive(envelope=over).outcome is DerivationOutcome.DENIED


# ---------------------------------------------------------------------------
# pinned arithmetic context (adversarial review NIT-1)
# ---------------------------------------------------------------------------


def test_the_derivation_ignores_a_hostile_ambient_decimal_context() -> None:
    """(NIT-1) ``decimal`` reads a per-thread context; the derivation must not.

    A caller who had set a one-digit precision would otherwise change the derived size, or make
    the venue lot remainder raise ``DivisionImpossible`` — ambient inputs the determinism claim
    (IOC-INV-002; design #34 §3.1) does not admit.

    The **inputs are built once, outside** the hostile context: a ``CanonicalDecimal`` field
    normalizes at validation time, so constructing the bound under ``prec=1`` would corrupt the
    injected values themselves and the test would be measuring the fixture rather than the
    derivation. Only the call is made under the hostile context.
    """
    envelope = proposed_envelope(
        sizing_bound=sizing_bound(
            risk_budget=Decimal("1100"),
            per_unit_risk=_BOUNDARY_PER_UNIT,
            lot_size=_BOUNDARY_LOT,
            min_quantity=Decimal("1"),
            max_quantity=Decimal("1000"),
        )
    )
    constraint = venue_quantity_constraint(
        lot_size=_BOUNDARY_LOT, min_quantity=Decimal("1"), max_quantity=Decimal("1000")
    )
    price = admitted_price()
    baseline = derive_order_size(
        quantity_basis="RISK", envelope=envelope, price=price, venue_constraint=constraint
    )
    with localcontext() as ctx:
        ctx.prec = 1
        hostile = derive_order_size(
            quantity_basis="RISK", envelope=envelope, price=price, venue_constraint=constraint
        )
    assert baseline.outcome is DerivationOutcome.DERIVED
    assert baseline.quantity == Decimal("11")
    assert hostile == baseline


def test_the_synthetic_fill_band_ignores_a_hostile_ambient_decimal_context() -> None:
    """(NIT-1 symmetry) The transport's band is pinned the same way (design #34 §5.2)."""
    policy = SyntheticFillPolicy(
        fill_numerator=1, fill_denominator=3, lot_size=Decimal("1")
    )
    transport = SyntheticPaperTransport(policy)
    baseline = transport._filled_quantity(Decimal("1000"))
    with localcontext() as ctx:
        ctx.prec = 1
        hostile = transport._filled_quantity(Decimal("1000"))
    assert hostile == baseline


# ---------------------------------------------------------------------------
# the envelope encloses the bound (design #34 §3.1 MINOR-3)
# ---------------------------------------------------------------------------


def test_there_is_no_quantity_input_anywhere_on_the_construction_surface() -> None:
    """(§3.1 MINOR-3) The author has no field through which to inject a size.

    The structural block: neither the proposed envelope, the price observation, nor the venue
    constraint carries a quantity *value* field — the only producer of a size is the derivation
    over the governance-supplied bound.
    """
    surfaces = (proposed_envelope(), admitted_price(), venue_quantity_constraint())
    for surface in surfaces:
        for name in type(surface).model_fields:
            assert name != "quantity", (
                f"{type(surface).__name__}.{name} would let an author declare a size directly, "
                "bypassing the envelope-enclosed derivation (design #34 §3.1)"
            )


def test_an_absent_sizing_bound_permits_no_construction() -> None:
    """(ADR-002-020 §5.3:125) The bound is governance-supplied; absence denies."""
    result = _derive(envelope=proposed_envelope(sizing_bound=None))
    assert result.outcome is DerivationOutcome.DENIED
    assert "encloses no sizing bound" in (result.denial_reason or "")


def test_an_absent_envelope_permits_no_construction() -> None:
    """(ADR-002-020 §5.3:125) An absent envelope permits no construction at all."""
    result = _derive(envelope=None)
    assert result.outcome is DerivationOutcome.DENIED


@pytest.mark.parametrize("axis", sorted(DERIVED_AXES))
def test_the_envelope_cannot_pre_declare_a_derived_axis(axis: ConformanceAxis) -> None:
    """(§3.1 / ADR-002-020 §10:284) A second declaration of a derived axis is ambiguity."""
    with pytest.raises(ValidationError, match="pre-declares the derived axis"):
        ProposedConstructionEnvelope(
            envelope_generation=1,
            authorized_axis_bindings=(*non_derived_axes(), AxisBinding(axis=axis, value="9")),
            sizing_bound=sizing_bound(),
        )


def test_an_empty_admitted_basis_set_authorizes_nothing() -> None:
    """(∅ both-ways) A vacuous "any basis" is not authorization."""
    envelope = proposed_envelope(
        sizing_bound=sizing_bound(admitted_quantity_bases=frozenset())
    )
    result = _derive(envelope=envelope)
    assert result.outcome is DerivationOutcome.DENIED
    assert "admits no quantity basis" in (result.denial_reason or "")


def test_a_basis_outside_the_admitted_set_is_a_silent_widening() -> None:
    """(ADR-002-020 §5.3) A basis the envelope never authorized denies."""
    result = _derive(quantity_basis="MAX")
    assert result.outcome is DerivationOutcome.DENIED
    assert "not in the envelope's admitted set" in (result.denial_reason or "")


# ---------------------------------------------------------------------------
# the ioc declare-and-verify seal (design #34 §3.2)
# ---------------------------------------------------------------------------


def test_a_denied_derivation_compiles_no_command_at_all() -> None:
    """(§3.1) There is no partially-constructed artifact for a later stage to consume."""
    built = construction(price=admitted_price(value=None))
    assert built.command is None
    assert built.derivation.outcome is DerivationOutcome.DENIED
    verdict = candidate_command_verdict(built)
    assert verdict.outcome is StageOutcome.DENY


def test_the_compiled_command_declares_the_derived_axes_exactly() -> None:
    """(§3.2) The derivation's three axes reach the command through ioc's declare-and-verify."""
    built = construction()
    assert built.command is not None
    assert built.conformance_result is ConformanceResult.CONFORMANT
    assert built.command.axis_value(ConformanceAxis.QUANTITY) == "2E+1"
    assert built.command.axis_value(ConformanceAxis.UNIT) == QuantityUnitKind.CONTRACTS.value


def test_construction_records_carry_the_all_false_rfc002_authority_block() -> None:
    """(RFC-002 §9.1:553 / §3.3) Construction approves, mutates, transmits, and arms nothing."""
    built = construction()
    effect = built.authority_effect
    for name in type(effect).model_fields:
        assert getattr(effect, name) is False
    with pytest.raises(ValidationError, match="must be false"):
        AllFalseConstructionCoordinatorAuthority(transmits=True)


def test_no_silent_widening_is_witnessed_structurally_not_declared() -> None:
    """(IOC-INV-006:177) The witness is derived from what the derivation actually did."""
    built = construction()
    assert built.no_silent_widening_ok is True
    denied = construction(price=admitted_price(value=None))
    assert denied.no_silent_widening_ok is None


# ---------------------------------------------------------------------------
# step 5 — the Economic Effect Envelope (∅ both-ways)
# ---------------------------------------------------------------------------


def test_the_effect_envelope_magnitudes_are_computed_from_the_derived_size() -> None:
    """(§3.2 step 5) Notional = quantity × price; units = quantity. Never self-reported."""
    built = construction()
    envelope = derive_economic_effect_envelope(
        built.derivation, proposed_envelope().effect_dimensions
    )
    magnitudes = {c.dimension_id: c.magnitude for c in envelope.components}
    assert magnitudes["units"] == Decimal("20")
    assert magnitudes["notional"] == Decimal("20") * PRICE


def test_an_empty_effect_spec_derives_nothing_and_is_unknown() -> None:
    """(∅ both-ways) "an empty vector is not no effect" — D-E1 turns it into UNKNOWN."""
    built = construction()
    envelope = derive_economic_effect_envelope(built.derivation, ())
    assert envelope.components == ()


def test_a_denied_derivation_yields_unknown_magnitudes() -> None:
    """(fail-closed) A denied size never produces a numeric effect magnitude."""
    built = construction(price=admitted_price(value=None))
    envelope = derive_economic_effect_envelope(
        built.derivation, proposed_envelope().effect_dimensions
    )
    assert all(component.magnitude is None for component in envelope.components)


# ---------------------------------------------------------------------------
# step 3 — the non-authorizing venue fold (design #34 §3.2 MINOR-4)
# ---------------------------------------------------------------------------


def _fold(**overrides):
    """Run the venue fold with the suite's admitting baseline."""
    return fold_venue_admissibility(
        observed_session_phase=overrides.pop("observed_session_phase", SESSION_PHASE),
        action_class=overrides.pop("action_class", ActionClass.NEW_LONG),
        snapshot=overrides.pop("snapshot", venue_snapshot()),
        policy=overrides.pop("policy", venue_policy()),
        shape=overrides.pop("shape", venue_shape()),
        constraints=overrides.pop("constraints", venue_shape_constraints()),
    )


def test_the_venue_fold_admits_only_when_both_predicates_admit() -> None:
    """(§3.2) Both venue predicates must positively admit."""
    assert _fold() is OrderAdmissibilityResult.ADMISSIBLE


def test_a_non_admitting_phase_denies_the_fold() -> None:
    """(ADR-002-019 §10:273) A phase outside the admitting set is inadmissible."""
    assert _fold(observed_session_phase="AUCTION") is OrderAdmissibilityResult.INADMISSIBLE


def test_an_unknown_phase_is_restrictive() -> None:
    """(ADR-002-019 §8:245) An unknown phase never passes permissively."""
    assert _fold(observed_session_phase=None) is OrderAdmissibilityResult.UNKNOWN


def test_a_silently_rounded_shape_is_inadmissible() -> None:
    """(ADR-002-019 §12:309) A silently normalized shape is a NEW shape, and denies."""
    assert (
        _fold(shape=venue_shape(silently_rounded=True))
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_an_unwitnessed_rounding_flag_is_inadmissible() -> None:
    """(negative polarity) ``None`` is not "not rounded" — only an explicit ``False`` is."""
    assert (
        _fold(shape=venue_shape(silently_rounded=None))
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_an_absent_action_class_is_unknown() -> None:
    """(fail-closed) Without an action class there is nothing to judge admissibility for."""
    assert _fold(action_class=None) is OrderAdmissibilityResult.UNKNOWN


# ---------------------------------------------------------------------------
# the four injected stages
# ---------------------------------------------------------------------------


def _construction_stage(**overrides) -> OrderConstructionStage:
    """Build the step-2 stage over the suite's baseline inputs."""
    return OrderConstructionStage(
        envelope=overrides.pop("envelope", proposed_envelope()),
        price=overrides.pop("price", admitted_price()),
        venue_constraint=overrides.pop("venue_constraint", venue_quantity_constraint()),
        scheme=SCHEME,
        intent_id="intent-1",
        intent_version="intent-v1",
        envelope_id="env-1",
        policy_id="ocp-1",
        policy_version="ocp-v1",
        policy_generation=1,
        command_id="cmd-1",
        generation=1,
    )


class _Proposal:
    """A minimal stand-in carrying only what the step-2 stage reads off a Proposal."""

    quantity_basis = "RISK"
    proposal_id = "prop-1"
    canonical_digest = "prop-digest-1"


class _Request:
    """A minimal ``StageRequest`` stand-in (the stage reads ``step`` and ``proposal`` only)."""

    def __init__(self, step: CommitmentStep) -> None:
        self.step = step
        self.proposal = _Proposal()


def test_the_step2_stage_admits_a_conformant_candidate() -> None:
    """(§3.2 step 2) The thin new adapter admits only a CONFORMANT, non-widened candidate."""
    stage = _construction_stage()
    verdict = stage(_Request(CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION))
    assert verdict.outcome is StageOutcome.ADMIT
    assert stage.construction is not None and stage.construction.command is not None


def test_the_step2_stage_denies_when_the_derivation_denies() -> None:
    """(§3.2) A denied derivation never becomes an admitted step."""
    stage = _construction_stage(price=admitted_price(value=None))
    verdict = stage(_Request(CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION))
    assert verdict.outcome is StageOutcome.DENY


def test_the_step5_stage_reuses_the_step2_derivation() -> None:
    """(§3.2 step 5) One derivation feeds both steps — no second chance at a different answer."""
    stage2 = _construction_stage()
    stage2(_Request(CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION))
    stage5 = EconomicEffectStage(construction_stage=stage2)
    verdict = stage5(_Request(CommitmentStep.ECONOMIC_EFFECT_ENVELOPE))
    assert verdict.outcome is StageOutcome.ADMIT
    assert stage5.envelope is not None


def test_the_step5_stage_is_unknown_when_no_construction_ran() -> None:
    """(fail-closed) Nothing to derive an effect from is UNKNOWN, never an empty pass."""
    stage5 = EconomicEffectStage(construction_stage=_construction_stage())
    verdict = stage5(_Request(CommitmentStep.ECONOMIC_EFFECT_ENVELOPE))
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_the_step11_stage_issues_a_proof_that_fences_the_exact_command() -> None:
    """(ADR-002-020 §6.2/§15:414) The proof must bind the exact command digest."""
    stage2 = _construction_stage()
    stage2(_Request(CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION))
    stage11 = ConformanceProofStage(
        construction_stage=stage2,
        scheme=SCHEME,
        proof_id="ocp-proof-1",
        proof_generation=1,
        required_authority_scope=("scope-1",),
    )
    verdict = stage11(_Request(CommitmentStep.ORDER_CONFORMANCE_PROOF))
    assert verdict.outcome is StageOutcome.ADMIT
    assert stage11.proof is not None
    assert stage2.construction is not None and stage2.construction.command is not None
    assert stage11.proof.command_digest == stage2.construction.command.canonical_digest


def test_the_step3_stage_denies_a_protective_only_venue_result() -> None:
    """(RFC-005 §12:371) A protective path never runs through this gate's self-classification."""
    stage = VenueConstraintStage(
        observed_session_phase="AUCTION",
        action_class=ActionClass.NEW_LONG,
        snapshot=venue_snapshot(),
        policy=venue_policy(),
        shape=venue_shape(),
        constraints=venue_shape_constraints(),
        decision=venue_decision(OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY),
    )
    verdict = stage(_Request(CommitmentStep.VENUE_ADMISSIBILITY_DECISION))
    assert verdict.outcome is StageOutcome.DENY


def test_a_quantity_above_the_venue_ceiling_never_reaches_a_command() -> None:
    """(§3.1) The two bounds compose restrictively; neither is widened by the other."""
    result = _derive(
        envelope=proposed_envelope(
            sizing_bound=sizing_bound(max_quantity=MAX_QUANTITY, risk_budget=Decimal("4000"))
        ),
        venue_constraint=venue_quantity_constraint(max_quantity=Decimal("10")),
    )
    assert result.outcome is DerivationOutcome.DENIED
