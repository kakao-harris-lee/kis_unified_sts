"""``tos_runtime.compose._envelope_wiring`` — unit tests (hermetic, no I/O).

Pure unit tests of the (a′) wave's lane B module: envelope construction from a
:class:`~tos_runtime.venue.construction_rules.ConstructionRules`, the two OCP/venue boot
cross-checks (side tokens, sizing bound), identity derivation, and the
:func:`~tos_runtime.compose._envelope_wiring.build_construction_inputs` call-site wrapper.
Every fixture is built directly from kernel/runtime dataclasses (never through the YAML loader,
and never through a real :class:`~tos_runtime.venue.VenueConstraintService` — a lightweight
stand-in stub carries just the two attributes ``build_construction_inputs`` reads) — this
suite owns its own inputs, the same "each package's fixtures stay in its own suite" discipline
``compose/_fixtures.py``'s own module docstring states.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egressgw import (
    EffectBasis,
    EffectDimensionSpec,
    LotRoundingPolicy,
    SizingBound,
    VenueQuantityConstraint,
)
from tos.ioc import (
    AxisBinding,
    ConformanceAxis,
    OrderConstructionPolicy,
    QuantityUnitKind,
)
from tos.venue import ActionClass
from tos_runtime.compose._envelope_wiring import (
    SideDerivationRefused,
    build_construction_envelope,
    build_construction_identities,
    build_construction_inputs,
    resolve_construction_direction,
)
from tos_runtime.compose._riskstate_wiring import RiskPolicyScopeMismatch
from tos_runtime.venue import LoadedOrderConstructionPolicy
from tos_runtime.venue.construction_rules import ActionClassShape, ConstructionRules

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _venue_quantity_constraint(
    *,
    quantity_unit: QuantityUnitKind | None = QuantityUnitKind.CONTRACTS,
    max_quantity: Decimal | None = Decimal(1),
    min_quantity: Decimal | None = Decimal(1),
    lot_size: Decimal | None = Decimal(1),
) -> VenueQuantityConstraint:
    return VenueQuantityConstraint(
        lot_size=lot_size,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
        quantity_unit=quantity_unit,
    )


def _sizing_bound(
    *,
    max_quantity: Decimal | None = Decimal(1),
    min_quantity: Decimal | None = Decimal(1),
    lot_size: Decimal | None = Decimal(1),
) -> SizingBound:
    return SizingBound(
        risk_budget=Decimal(1),
        per_unit_risk=Decimal(1),
        lot_size=lot_size,
        lot_rounding=LotRoundingPolicy.EXACT_MULTIPLE_REQUIRED,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
        max_notional=None,
        quantity_unit=None,  # lane A's own contract — never set here.
        admitted_quantity_bases=frozenset({"RISK"}),
    )


#: The (action_class, direction) this suite's default fixtures agree on throughout — matches
#: the default ``sides``/``direction`` in :func:`_construction_rules` below.
_ACTION_CLASS = ActionClass.NEW_LONG


def _construction_rules(
    *,
    sides: dict[tuple[ActionClass, str], str] | None = None,
    sizing_bound: SizingBound | None = None,
    direction: str | None = "LONG",
) -> ConstructionRules:
    """``direction`` is ``None`` builds a ``ConstructionRules`` with NO ``DIRECTION`` axis
    binding at all — the SIDE-derivation refusal path's own fixture."""
    sides = sides if sides is not None else {(ActionClass.NEW_LONG, "LONG"): "BUY"}
    action_class_shape = {
        key: ActionClassShape(side=side, position_effect="OPEN")
        for key, side in sides.items()
    }
    axes = (AxisBinding(axis=ConformanceAxis.TIF, value="DAY"),)
    if direction is not None:
        axes = axes + (AxisBinding(axis=ConformanceAxis.DIRECTION, value=direction),)
    return ConstructionRules(
        sizing_bound=sizing_bound if sizing_bound is not None else _sizing_bound(),
        admitted_quantity_bases=frozenset({"RISK"}),
        authorized_axes=axes,
        action_class_shape=action_class_shape,
        effect_dimensions=(
            EffectDimensionSpec(
                dimension_id="d1",
                basis=EffectBasis.QUANTITY,
                unit="CONTRACTS",
                scale="1",
            ),
        ),
    )


def _loaded_ocp(
    *,
    policy_generation: int = 1,
    construction_generation: int | None = 1,
    rules: ConstructionRules | None = None,
) -> LoadedOrderConstructionPolicy:
    policy = OrderConstructionPolicy.issue(
        scheme=_SCHEME,
        policy_id="ocp-test-1",
        policy_generation=policy_generation,
        policy_version="1.0.0",
        signer_identity=None,
        approval_identity=None,
        evidence_package_ref=None,
    )
    assert isinstance(policy, OrderConstructionPolicy)
    return LoadedOrderConstructionPolicy(
        policy=policy,
        canonicalization_version=_SCHEME.version,
        wire_codec_kind=None,
        wire_fields=frozenset(),
        construction_generation=construction_generation,
        construction_rules=rules if rules is not None else _construction_rules(),
    )


# ===========================================================================
# build_construction_envelope — quantity_unit sourcing
# ===========================================================================


def test_envelope_sources_quantity_unit_from_the_venue_not_the_ocp() -> None:
    """The load-bearing decision (module docstring): ``sizing_bound.quantity_unit`` on the
    built envelope is the INJECTED venue unit, never anything the OCP-derived
    ``ConstructionRules.sizing_bound`` itself carries (which is always ``None`` — lane A's own
    ``_parse_sizing`` leaves it unset by design)."""
    rules = _construction_rules()
    assert rules.sizing_bound.quantity_unit is None  # lane A's own contract
    envelope = build_construction_envelope(
        rules,
        loaded_ocp=_loaded_ocp(),
        action_class=_ACTION_CLASS,
        venue_quantity_constraint=_venue_quantity_constraint(),
        venue_allowed_sides=frozenset({"BUY", "SELL"}),
    )
    assert envelope.sizing_bound is not None
    assert envelope.sizing_bound.quantity_unit is QuantityUnitKind.CONTRACTS
    # Every OTHER sizing_bound field passes through unchanged from the OCP's own rules.
    assert envelope.sizing_bound.risk_budget == rules.sizing_bound.risk_budget
    assert envelope.sizing_bound.lot_rounding == rules.sizing_bound.lot_rounding


def test_envelope_quantity_unit_none_flows_through_uncorrected() -> None:
    """Mutation (team-lead brief's own required mutation): with no venue unit, the built
    envelope's ``sizing_bound.quantity_unit`` is ``None`` — never silently defaulted — so
    ``derive_order_size`` is the one that denies ("the sizing bound declares no quantity
    unit"), not this module."""
    envelope = build_construction_envelope(
        _construction_rules(),
        loaded_ocp=_loaded_ocp(),
        action_class=_ACTION_CLASS,
        venue_quantity_constraint=_venue_quantity_constraint(quantity_unit=None),
        venue_allowed_sides=frozenset({"BUY", "SELL"}),
    )
    assert envelope.sizing_bound is not None
    assert envelope.sizing_bound.quantity_unit is None


def test_envelope_identity_and_axes_come_from_the_ocp() -> None:
    loaded_ocp = _loaded_ocp(construction_generation=7)
    rules = loaded_ocp.construction_rules
    envelope = build_construction_envelope(
        rules,
        loaded_ocp=loaded_ocp,
        action_class=_ACTION_CLASS,
        venue_quantity_constraint=_venue_quantity_constraint(),
        venue_allowed_sides=frozenset({"BUY", "SELL"}),
    )
    assert envelope.envelope_generation == 7
    assert envelope.policy_binding_id == "ocp-test-1"
    # authorized_axis_bindings carries rules.authorized_axes PLUS the derived SIDE binding
    # (module docstring) — never a second, independently-authored SIDE declaration.
    assert envelope.authorized_axis_bindings == rules.authorized_axes + (
        AxisBinding(axis=ConformanceAxis.SIDE, value="BUY"),
    )
    assert envelope.effect_dimensions == rules.effect_dimensions


# ===========================================================================
# build_construction_envelope — side cross-check
# ===========================================================================


def test_envelope_refuses_when_an_ocp_side_is_not_venue_allowed() -> None:
    rules = _construction_rules(sides={(ActionClass.NEW_LONG, "LONG"): "BUY"})
    with pytest.raises(RiskPolicyScopeMismatch, match="BUY"):
        build_construction_envelope(
            rules,
            loaded_ocp=_loaded_ocp(),
            action_class=_ACTION_CLASS,
            venue_quantity_constraint=_venue_quantity_constraint(),
            # venue only admits SELL — the OCP's BUY is unknown to it.
            venue_allowed_sides=frozenset({"SELL"}),
        )


def test_envelope_admits_when_every_ocp_side_is_venue_allowed() -> None:
    rules = _construction_rules(
        sides={
            (ActionClass.NEW_LONG, "LONG"): "BUY",
            (ActionClass.NEW_SHORT, "SHORT"): "SELL",
        }
    )
    envelope = build_construction_envelope(
        rules,
        loaded_ocp=_loaded_ocp(),
        action_class=_ACTION_CLASS,
        venue_quantity_constraint=_venue_quantity_constraint(),
        venue_allowed_sides=frozenset({"BUY", "SELL"}),
    )
    assert envelope.sizing_bound is not None


# ===========================================================================
# build_construction_envelope — sizing-bound subset cross-check (team-lead follow-up)
# ===========================================================================


def test_envelope_refuses_when_ocp_max_quantity_exceeds_the_venue() -> None:
    rules = _construction_rules(sizing_bound=_sizing_bound(max_quantity=Decimal(5)))
    with pytest.raises(RiskPolicyScopeMismatch, match="max_quantity"):
        build_construction_envelope(
            rules,
            loaded_ocp=_loaded_ocp(),
            action_class=_ACTION_CLASS,
            venue_quantity_constraint=_venue_quantity_constraint(
                max_quantity=Decimal(1)
            ),
            venue_allowed_sides=frozenset({"BUY", "SELL"}),
        )


def test_envelope_refuses_when_ocp_min_quantity_is_below_the_venue() -> None:
    rules = _construction_rules(sizing_bound=_sizing_bound(min_quantity=Decimal(0)))
    with pytest.raises(RiskPolicyScopeMismatch, match="min_quantity"):
        build_construction_envelope(
            rules,
            loaded_ocp=_loaded_ocp(),
            action_class=_ACTION_CLASS,
            venue_quantity_constraint=_venue_quantity_constraint(
                min_quantity=Decimal(1)
            ),
            venue_allowed_sides=frozenset({"BUY", "SELL"}),
        )


def test_envelope_refuses_when_ocp_lot_size_is_not_a_whole_multiple_of_the_venues() -> (
    None
):
    rules = _construction_rules(sizing_bound=_sizing_bound(lot_size=Decimal("1.5")))
    with pytest.raises(RiskPolicyScopeMismatch, match="lot_size"):
        build_construction_envelope(
            rules,
            loaded_ocp=_loaded_ocp(),
            action_class=_ACTION_CLASS,
            venue_quantity_constraint=_venue_quantity_constraint(lot_size=Decimal(1)),
            venue_allowed_sides=frozenset({"BUY", "SELL"}),
        )


def test_envelope_admits_an_ocp_sizing_bound_narrower_than_the_venue() -> None:
    """A policy narrower than the venue is legitimate — only WIDER is refused."""
    rules = _construction_rules(
        sizing_bound=_sizing_bound(max_quantity=Decimal(1), min_quantity=Decimal(1))
    )
    envelope = build_construction_envelope(
        rules,
        loaded_ocp=_loaded_ocp(),
        action_class=_ACTION_CLASS,
        venue_quantity_constraint=_venue_quantity_constraint(
            max_quantity=Decimal(10), min_quantity=Decimal(0)
        ),
        venue_allowed_sides=frozenset({"BUY", "SELL"}),
    )
    assert envelope.sizing_bound is not None


def test_envelope_sizing_check_skips_a_field_the_venue_leaves_absent() -> None:
    """An absent venue bound is UNKNOWN, not "unlimited" — nothing to compare against, so no
    refusal (matches the real paper venue policy's own ``max_quantity: null``)."""
    rules = _construction_rules(sizing_bound=_sizing_bound(max_quantity=Decimal(999)))
    envelope = build_construction_envelope(
        rules,
        loaded_ocp=_loaded_ocp(),
        action_class=_ACTION_CLASS,
        venue_quantity_constraint=_venue_quantity_constraint(max_quantity=None),
        venue_allowed_sides=frozenset({"BUY", "SELL"}),
    )
    assert envelope.sizing_bound is not None


# ===========================================================================
# resolve_construction_direction (integration follow-up, 2026-09-16)
# ===========================================================================

_MIRRORED_SIDES = {
    (ActionClass.NEW_LONG, "LONG"): "BUY",
    (ActionClass.NEW_SHORT, "SHORT"): "SELL",
}
_MIRRORED_SIDES_WITH_CLOSE = {**_MIRRORED_SIDES, (ActionClass.CLOSE, "LONG"): "SELL"}


def test_resolve_direction_uses_the_action_class_for_direction_named_classes() -> None:
    """The class itself is the most specific per-attempt direction fact available — read
    BEFORE the policy's own axis, not instead of it only when the axis agrees."""
    rules = _construction_rules(sides=_MIRRORED_SIDES, direction="LONG")
    assert (
        resolve_construction_direction(rules, action_class=ActionClass.NEW_SHORT)
        == "SHORT"
    )
    assert (
        resolve_construction_direction(rules, action_class=ActionClass.NEW_LONG)
        == "LONG"
    )


def test_resolve_direction_falls_back_to_the_policy_axis_for_direction_agnostic_classes() -> (
    None
):
    rules = _construction_rules(sides=_MIRRORED_SIDES_WITH_CLOSE, direction="LONG")
    assert (
        resolve_construction_direction(rules, action_class=ActionClass.CLOSE) == "LONG"
    )


def test_resolve_direction_refuses_for_a_direction_agnostic_class_with_no_axis() -> (
    None
):
    """Mutation-equivalent for the DIRECTION-absent path: never defaults, refuses — matches
    the ``construction_generation`` discipline :func:`build_construction_identities` already
    follows for its own missing-input case. Narrower than before: this only fires for a
    DIRECTION-AGNOSTIC class now, never for NEW_LONG/NEW_SHORT."""
    rules = _construction_rules(sides=_MIRRORED_SIDES_WITH_CLOSE, direction=None)
    assert not any(
        b.axis is ConformanceAxis.DIRECTION for b in rules.authorized_axes
    )  # fixture sanity
    with pytest.raises(SideDerivationRefused, match="direction-agnostic"):
        resolve_construction_direction(rules, action_class=ActionClass.CLOSE)


# ===========================================================================
# build_construction_envelope — SIDE axis derivation (team-lead follow-up)
# ===========================================================================


def test_envelope_derives_side_from_action_class_shape() -> None:
    """The whole point (module docstring): SIDE is never authored in the OCP document, it is
    read off ``action_class_shape[(action_class, direction)].side`` and appended to
    ``authorized_axis_bindings`` — the one source ``ActionClassShape`` already is."""
    rules = _construction_rules(
        sides={(ActionClass.NEW_LONG, "LONG"): "BUY"}, direction="LONG"
    )
    envelope = build_construction_envelope(
        rules,
        loaded_ocp=_loaded_ocp(),
        action_class=ActionClass.NEW_LONG,
        venue_quantity_constraint=_venue_quantity_constraint(),
        venue_allowed_sides=frozenset({"BUY", "SELL"}),
    )
    side_bindings = [
        b for b in envelope.authorized_axis_bindings if b.axis is ConformanceAxis.SIDE
    ]
    assert side_bindings == [AxisBinding(axis=ConformanceAxis.SIDE, value="BUY")]


def test_envelope_derives_short_side_even_when_the_policy_direction_axis_says_long() -> (
    None
):
    """The exact defect the integration run caught (team-lead follow-up, 2026-09-16): a
    ``NEW_SHORT`` composition against a policy whose ``DIRECTION`` axis says ``LONG`` must
    still derive SELL — direction comes from the action class for a direction-named class,
    the policy axis is never even consulted. Before this fix, a policy fixed at ``LONG`` was
    permanently unable to serve a short attempt, backwards from long/short symmetry."""
    rules = _construction_rules(sides=_MIRRORED_SIDES, direction="LONG")
    envelope = build_construction_envelope(
        rules,
        loaded_ocp=_loaded_ocp(),
        action_class=ActionClass.NEW_SHORT,
        venue_quantity_constraint=_venue_quantity_constraint(),
        venue_allowed_sides=frozenset({"BUY", "SELL"}),
    )
    side_bindings = [
        b for b in envelope.authorized_axis_bindings if b.axis is ConformanceAxis.SIDE
    ]
    assert side_bindings == [AxisBinding(axis=ConformanceAxis.SIDE, value="SELL")]


def test_envelope_derives_side_for_a_direction_agnostic_class_from_the_policy_axis() -> (
    None
):
    """CLOSE names no direction of its own, so this exercises the fallback arm of
    :func:`resolve_construction_direction`."""
    rules = _construction_rules(sides=_MIRRORED_SIDES_WITH_CLOSE, direction="LONG")
    envelope = build_construction_envelope(
        rules,
        loaded_ocp=_loaded_ocp(),
        action_class=ActionClass.CLOSE,
        venue_quantity_constraint=_venue_quantity_constraint(),
        venue_allowed_sides=frozenset({"BUY", "SELL"}),
    )
    side_bindings = [
        b for b in envelope.authorized_axis_bindings if b.axis is ConformanceAxis.SIDE
    ]
    assert side_bindings == [AxisBinding(axis=ConformanceAxis.SIDE, value="SELL")]


def test_envelope_refuses_when_action_class_shape_has_no_arm_for_the_resolved_direction() -> (
    None
):
    """The document declares a shape for (NEW_LONG, LONG) only; this composition's own
    ``action_class`` is NEW_SHORT, which resolves its OWN direction (SHORT) — no
    (NEW_SHORT, SHORT) arm exists, so this refuses rather than silently falling back to some
    other declared side."""
    rules = _construction_rules(
        sides={(ActionClass.NEW_LONG, "LONG"): "BUY"}, direction="LONG"
    )
    with pytest.raises(SideDerivationRefused, match="NEW_SHORT"):
        build_construction_envelope(
            rules,
            loaded_ocp=_loaded_ocp(),
            action_class=ActionClass.NEW_SHORT,
            venue_quantity_constraint=_venue_quantity_constraint(),
            venue_allowed_sides=frozenset({"BUY", "SELL"}),
        )


# ===========================================================================
# build_construction_identities
# ===========================================================================


def test_identities_are_deterministic_over_the_same_inputs() -> None:
    loaded_ocp = _loaded_ocp()
    first = build_construction_identities(
        account="acct-1", instrument="ES", loaded_ocp=loaded_ocp, scheme=_SCHEME
    )
    second = build_construction_identities(
        account="acct-1", instrument="ES", loaded_ocp=loaded_ocp, scheme=_SCHEME
    )
    assert first == second


def test_identities_change_across_ocp_generations() -> None:
    """The exact defect the prior ``generation=1`` literal had (module docstring): an identity
    template that does not vary with the OCP's own generation makes generation-fencing vacuous.
    Every identity derived here must differ once ``construction_generation`` changes."""
    gen1 = build_construction_identities(
        account="acct-1",
        instrument="ES",
        loaded_ocp=_loaded_ocp(construction_generation=1),
        scheme=_SCHEME,
    )
    gen2 = build_construction_identities(
        account="acct-1",
        instrument="ES",
        loaded_ocp=_loaded_ocp(construction_generation=2),
        scheme=_SCHEME,
    )
    assert gen1.intent_id != gen2.intent_id
    assert gen1.envelope_id != gen2.envelope_id
    assert gen1.command_id != gen2.command_id
    assert gen1.proof_id != gen2.proof_id
    assert gen1.generation != gen2.generation


def test_generation_is_sourced_from_construction_generation_not_a_constant() -> None:
    identities = build_construction_identities(
        account="acct-1",
        instrument="ES",
        loaded_ocp=_loaded_ocp(construction_generation=42),
        scheme=_SCHEME,
    )
    assert identities.generation == 42


def test_intent_version_is_the_ocps_own_policy_version() -> None:
    loaded_ocp = _loaded_ocp()
    identities = build_construction_identities(
        account="acct-1", instrument="ES", loaded_ocp=loaded_ocp, scheme=_SCHEME
    )
    assert identities.intent_version == loaded_ocp.policy.policy_version == "1.0.0"


def test_identities_change_across_accounts_or_instruments() -> None:
    loaded_ocp = _loaded_ocp()
    base = build_construction_identities(
        account="acct-1", instrument="ES", loaded_ocp=loaded_ocp, scheme=_SCHEME
    )
    other_account = build_construction_identities(
        account="acct-2", instrument="ES", loaded_ocp=loaded_ocp, scheme=_SCHEME
    )
    other_instrument = build_construction_identities(
        account="acct-1", instrument="NQ", loaded_ocp=loaded_ocp, scheme=_SCHEME
    )
    assert base.intent_id != other_account.intent_id
    assert base.intent_id != other_instrument.intent_id


def test_absent_construction_generation_refuses_rather_than_defaulting_to_a_literal() -> (
    None
):
    """``construction_generation: null`` is an accepted loader state
    (``tests/venue/test_config.py::test_load_order_construction_policy_null_construction_generation_accepted``)
    but this module's own identity derivation has no fallback for it — a missing Construction
    Generation is a refusal here, never a silent ``generation=1``."""
    with pytest.raises(AssertionError, match="construction_generation"):
        build_construction_identities(
            account="acct-1",
            instrument="ES",
            loaded_ocp=_loaded_ocp(construction_generation=None),
            scheme=_SCHEME,
        )


# ===========================================================================
# build_construction_inputs — the one call-site wrapper
# ===========================================================================


@dataclass(frozen=True)
class _StubShapeConstraints:
    allowed_sides: frozenset[str]


@dataclass(frozen=True)
class _StubVenueService:
    """Carries only the two attributes ``build_construction_inputs`` reads off a real
    :class:`~tos_runtime.venue.VenueConstraintService` — that type needs an
    :class:`~tos_runtime.evidence.store.SqliteEvidenceStore` plus several more services to
    construct, which this hermetic unit-test suite has no business standing up (module
    docstring)."""

    quantity_constraint: VenueQuantityConstraint
    shape_constraints: _StubShapeConstraints


@dataclass(frozen=True)
class _StubConstruction:
    """Carries only the three attributes ``build_construction_inputs`` reads off a real
    :class:`~tos_runtime.compose._types.ConstructionConfig`."""

    account: str
    instrument: str
    action_class: ActionClass


def test_inputs_bundles_both_builders_plus_ocp_identity_for_the_one_call_site() -> None:
    loaded_ocp = _loaded_ocp(construction_generation=3)
    venue_service = _StubVenueService(
        quantity_constraint=_venue_quantity_constraint(),
        shape_constraints=_StubShapeConstraints(
            allowed_sides=frozenset({"BUY", "SELL"})
        ),
    )
    construction = _StubConstruction(
        account="acct-1", instrument="ES", action_class=_ACTION_CLASS
    )
    inputs = build_construction_inputs(
        construction,  # type: ignore[arg-type]
        venue_service=venue_service,  # type: ignore[arg-type]
        loaded_ocp=loaded_ocp,
        scheme=_SCHEME,
    )
    assert inputs.envelope.sizing_bound is not None
    assert inputs.envelope.sizing_bound.quantity_unit is QuantityUnitKind.CONTRACTS
    assert inputs.identities.generation == 3
    assert inputs.policy_id == "ocp-test-1"
    assert inputs.policy_version == "1.0.0"
    assert inputs.policy_generation == 1
    # Same as calling the two builders directly.
    envelope = build_construction_envelope(
        loaded_ocp.construction_rules,
        loaded_ocp=loaded_ocp,
        action_class=_ACTION_CLASS,
        venue_quantity_constraint=venue_service.quantity_constraint,
        venue_allowed_sides=venue_service.shape_constraints.allowed_sides,
    )
    identities = build_construction_identities(
        account="acct-1", instrument="ES", loaded_ocp=loaded_ocp, scheme=_SCHEME
    )
    assert inputs.envelope == envelope
    assert inputs.identities == identities
