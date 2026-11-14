"""``tos_runtime.compose._envelope_wiring`` — builds step 2's"""

from __future__ import annotations

from dataclasses import dataclass

from tos.canonical import CanonicalizationScheme
from tos.egressgw import ProposedConstructionEnvelope, VenueQuantityConstraint
from tos.ioc import AxisBinding, ConformanceAxis
from tos.venue import ActionClass

from tos_runtime.compose._riskstate_wiring import (
    _cross_check_ocp_side_tokens,
    _cross_check_ocp_sizing_bound,
)
from tos_runtime.compose._types import ConstructionConfig
from tos_runtime.venue import LoadedOrderConstructionPolicy, VenueConstraintService
from tos_runtime.venue._order_construction_policy_loader import (
    _DIRECTION_NAMED_ACTION_CLASSES,
)
from tos_runtime.venue.construction_rules import ConstructionRules

__all__ = [
    "ConstructionIdentities",
    "ConstructionInputs",
    "SideDerivationRefused",
    "build_construction_envelope",
    "build_construction_identities",
    "build_construction_inputs",
    "resolve_construction_direction",
]


class SideDerivationRefused(RuntimeError):
    """Direction or SIDE could not be resolved from ``rules`` for this composition's"""


def resolve_construction_direction(
    rules: ConstructionRules, *, action_class: ActionClass
) -> str:
    """The ONE place direction is resolved for ``action_class_shape`` lookups (module docstring)"""
    if action_class in _DIRECTION_NAMED_ACTION_CLASSES:
        return action_class.value.rsplit("_", 1)[-1]
    direction = next(
        (b.value for b in rules.authorized_axes if b.axis is ConformanceAxis.DIRECTION),
        None,
    )
    if direction is None:
        raise SideDerivationRefused(
            f"action_class {action_class!r} is direction-agnostic and no DIRECTION axis "
            "binding is present in rules.authorized_axes — cannot derive SIDE without a "
            "direction to key action_class_shape by"
        )
    return direction


def _resolve_direction_and_side_bindings(
    rules: ConstructionRules, *, action_class: ActionClass
) -> tuple[AxisBinding, AxisBinding]:
    """The one place DIRECTION and SIDE are resolved together (module docstring) — never"""
    direction = resolve_construction_direction(rules, action_class=action_class)
    shape = rules.action_class_shape.get((action_class, direction))
    if shape is None:
        raise SideDerivationRefused(
            f"action_class_shape has no entry for (action_class={action_class!r}, "
            f"direction={direction!r}) — cannot derive a SIDE axis binding for this composition"
        )
    return (
        AxisBinding(axis=ConformanceAxis.DIRECTION, value=direction),
        AxisBinding(axis=ConformanceAxis.SIDE, value=shape.side),
    )


def build_construction_envelope(
    rules: ConstructionRules,
    *,
    loaded_ocp: LoadedOrderConstructionPolicy,
    action_class: ActionClass,
    venue_quantity_constraint: VenueQuantityConstraint,
    venue_allowed_sides: frozenset[str],
) -> ProposedConstructionEnvelope:
    """Build the proposed Authorized Construction Envelope from the OCP's own"""
    ocp_sides = frozenset(shape.side for shape in rules.action_class_shape.values())
    _cross_check_ocp_side_tokens(ocp_sides, venue_allowed_sides=venue_allowed_sides)
    _cross_check_ocp_sizing_bound(
        rules.sizing_bound, venue_quantity_constraint=venue_quantity_constraint
    )
    direction_binding, side_binding = _resolve_direction_and_side_bindings(
        rules, action_class=action_class
    )
    other_axes = tuple(
        b for b in rules.authorized_axes if b.axis is not ConformanceAxis.DIRECTION
    )
    sizing_bound = rules.sizing_bound.model_copy(
        update={"quantity_unit": venue_quantity_constraint.quantity_unit}
    )
    return ProposedConstructionEnvelope(
        envelope_generation=loaded_ocp.construction_generation,
        policy_binding_id=loaded_ocp.policy.policy_id,
        authorized_axis_bindings=other_axes + (direction_binding, side_binding),
        sizing_bound=sizing_bound,
        effect_dimensions=rules.effect_dimensions,
    )


@dataclass(frozen=True)
class ConstructionIdentities:
    """The six step-2 identity values :func:`build_construction_identities` derives (module"""

    intent_id: str
    intent_version: str
    envelope_id: str
    command_id: str
    generation: int
    proof_id: str


def _identity_digest(
    scheme: CanonicalizationScheme,
    *,
    kind: str,
    account: str,
    instrument: str,
    loaded_ocp: LoadedOrderConstructionPolicy,
    construction_generation: int,
) -> str:
    """One identity's digest over the real composition facts that distinguish it: which kind of"""
    ocp = loaded_ocp.policy
    return scheme.compute_digest(
        {
            "kind": kind,
            "account": account,
            "instrument": instrument,
            "policy_id": ocp.policy_id,
            "policy_version": ocp.policy_version,
            "policy_generation": ocp.policy_generation,
            "construction_generation": construction_generation,
        }
    )


def build_construction_identities(
    *,
    account: str,
    instrument: str,
    loaded_ocp: LoadedOrderConstructionPolicy,
    scheme: CanonicalizationScheme,
) -> ConstructionIdentities:
    """Derive the six step-2 identity values from real composition facts (module docstring)."""
    ocp = loaded_ocp.policy
    assert ocp.policy_id is not None and ocp.policy_version is not None
    assert ocp.policy_generation is not None
    construction_generation = loaded_ocp.construction_generation
    assert construction_generation is not None, (
        "build_construction_identities: loaded_ocp.construction_generation is None — an "
        "absent Construction Generation is a denial, never a silent generation=1 fallback "
        "(ADR-002-020 §5.7)"
    )

    def _digest(kind: str) -> str:
        return _identity_digest(
            scheme,
            kind=kind,
            account=account,
            instrument=instrument,
            loaded_ocp=loaded_ocp,
            construction_generation=construction_generation,
        )

    return ConstructionIdentities(
        intent_id=f"intent-{_digest('intent')}",
        intent_version=ocp.policy_version,
        envelope_id=f"envelope-{_digest('envelope')}",
        command_id=f"cmd-{_digest('command')}",
        generation=construction_generation,
        proof_id=f"ocp-proof-{_digest('proof')}",
    )


@dataclass(frozen=True)
class ConstructionInputs:
    """Every step-2 input ``_build_construction_stages`` needs from the governed OCP + venue"""

    envelope: ProposedConstructionEnvelope
    identities: ConstructionIdentities
    policy_id: str
    policy_version: str
    policy_generation: int


def build_construction_inputs(
    construction: ConstructionConfig,
    *,
    venue_service: VenueConstraintService,
    loaded_ocp: LoadedOrderConstructionPolicy,
    scheme: CanonicalizationScheme,
) -> ConstructionInputs:
    """The one call for the one call site (module docstring): takes the SAME three objects"""
    ocp = loaded_ocp.policy
    assert ocp.policy_id is not None and ocp.policy_version is not None
    assert ocp.policy_generation is not None
    envelope = build_construction_envelope(
        loaded_ocp.construction_rules,
        loaded_ocp=loaded_ocp,
        action_class=construction.action_class,
        venue_quantity_constraint=venue_service.quantity_constraint,
        venue_allowed_sides=venue_service.shape_constraints.allowed_sides,
    )
    identities = build_construction_identities(
        account=construction.account,
        instrument=construction.instrument,
        loaded_ocp=loaded_ocp,
        scheme=scheme,
    )
    return ConstructionInputs(
        envelope=envelope,
        identities=identities,
        policy_id=ocp.policy_id,
        policy_version=ocp.policy_version,
        policy_generation=ocp.policy_generation,
    )
