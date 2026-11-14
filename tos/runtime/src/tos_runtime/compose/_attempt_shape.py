"""``tos_runtime.compose._attempt_shape`` — step 2 builds each command from the PROPOSAL's own"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from tos.dsl import FLAT_QUANTITY_BASIS
from tos.egressgw import (
    CandidateConstruction,
    DerivationOutcome,
    EffectDimensionSpec,
    OrderConstructionStage,
    QuantityDerivation,
    candidate_command_verdict,
)
from tos.engine import StageRequest, StageVerdict
from tos.venue import ActionClass

from tos_runtime.compose._attempt_arm import AttemptArm
from tos_runtime.compose._envelope_wiring import (
    SideDerivationRefused,
    build_construction_envelope,
    resolve_construction_direction,
)
from tos_runtime.riskstate.close_bound import EntryCloseBound
from tos_runtime.venue import LoadedOrderConstructionPolicy, VenueConstraintService
from tos_runtime.venue._order_construction_policy_loader import (
    _DIRECTION_NAMED_ACTION_CLASSES,
)

__all__ = [
    "ProposalShapedConstructionStage",
    "build_attempt_arms",
    "select_attempt_arm",
]


def build_attempt_arms(
    loaded_ocp: LoadedOrderConstructionPolicy,
    *,
    boot_action_class: ActionClass,
    venue_service: VenueConstraintService,
) -> tuple[AttemptArm, ...]:
    """The boot arm first, then every direction-agnostic arm the OCP resolves (module docstring)."""
    rules = loaded_ocp.construction_rules

    def _arm(action_class: ActionClass) -> AttemptArm:
        direction = resolve_construction_direction(rules, action_class=action_class)
        shape = rules.action_class_shape[(action_class, direction)]
        envelope = build_construction_envelope(
            rules,
            loaded_ocp=loaded_ocp,
            action_class=action_class,
            venue_quantity_constraint=venue_service.quantity_constraint,
            venue_allowed_sides=venue_service.shape_constraints.allowed_sides,
        )
        return AttemptArm(
            action_class, direction, shape.side, shape.position_effect, envelope
        )

    arms = [_arm(boot_action_class)]
    agnostic = sorted(
        {ac for ac, _ in rules.action_class_shape} - _DIRECTION_NAMED_ACTION_CLASSES,
        key=lambda ac: ac.value,
    )
    for action_class in agnostic:
        if action_class is boot_action_class:
            continue
        try:
            arms.append(_arm(action_class))
        except (SideDerivationRefused, KeyError):
            continue
    return tuple(arms)


def _action_side(
    loaded_ocp: LoadedOrderConstructionPolicy, direction: str
) -> str | None:
    """The side the OCP gives an action in ``direction`` — read off its direction-named arm."""
    shapes = loaded_ocp.construction_rules.action_class_shape
    for action_class in _DIRECTION_NAMED_ACTION_CLASSES:
        named = action_class.value.rsplit("_", 1)[-1]
        shape = shapes.get((action_class, direction))
        if named == direction and shape is not None:
            return shape.side
    return None


def select_attempt_arm(
    arms: tuple[AttemptArm, ...],
    loaded_ocp: LoadedOrderConstructionPolicy,
    *,
    position_effect: str | None,
    direction: str | None,
) -> AttemptArm | str:
    """The ONE arm for a proposal's ``(position_effect, direction)``, or the refusal reason."""
    if not position_effect or not direction:
        return (
            f"the proposal declares no position_effect/direction ({position_effect!r}, "
            f"{direction!r}) — the command's SIDE cannot be derived (#960)"
        )
    side = _action_side(loaded_ocp, direction)
    if side is None:
        return (
            f"the order construction policy names no side for an action in direction "
            f"{direction!r} — the command's SIDE cannot be derived (#960)"
        )
    matches = [
        a for a in arms if a.position_effect == position_effect and a.side == side
    ]
    if len(matches) != 1:
        offered = [
            f"{a.action_class.value}.{a.direction}={a.side}/{a.position_effect}"
            for a in arms
        ]
        return (
            f"no single construction arm for proposal ({position_effect}, {direction}) — "
            f"needs {side}/{position_effect}, this composition offers {offered} (#960)"
        )
    return matches[0]


class ProposalShapedConstructionStage(OrderConstructionStage):
    """Step 2, with the envelope chosen per attempt by :func:`select_attempt_arm`."""

    def __init__(
        self,
        *,
        arms: tuple[AttemptArm, ...],
        loaded_ocp: LoadedOrderConstructionPolicy,
        entry_close_bound_reader: Callable[[], EntryCloseBound] | None = None,
        **stage_kwargs: Any,
    ) -> None:
        super().__init__(envelope=arms[0].envelope, **stage_kwargs)
        self._arm_stages = tuple(
            (arm, OrderConstructionStage(envelope=arm.envelope, **stage_kwargs))
            for arm in arms
        )
        self._loaded_ocp = loaded_ocp
        self._entry_close_bound_reader = entry_close_bound_reader
        self.attempt: AttemptArm | None = None

    def _durable_held_position(self) -> Decimal | None:
        """The proven open-entry remainder of this scope, or ``None`` for every refusal."""
        reader = self._entry_close_bound_reader
        if reader is None:
            return None
        try:
            bound = reader()
        except Exception:  # noqa: BLE001 - an unreadable bound proves nothing
            return None
        if type(bound) is not EntryCloseBound or not bound.proven:
            return None
        remaining = bound.remaining
        return remaining if type(remaining) is Decimal else None

    def _shaped_request(self, request: StageRequest) -> StageRequest:
        """``request`` for an ACTION proposal; a copy carrying the durable remainder for FLAT."""
        if getattr(request.proposal, "quantity_basis", None) != FLAT_QUANTITY_BASIS:
            return request
        return request.model_copy(
            update={"held_position_magnitude": self._durable_held_position()}
        )

    @property
    def effect_specs(self) -> tuple[EffectDimensionSpec, ...]:
        """THIS attempt's arm's Economic Effect Envelope specs (#960 review LOW-1)."""
        arm = self.attempt
        return super().effect_specs if arm is None else arm.envelope.effect_dimensions

    def __call__(self, request: StageRequest) -> StageVerdict:
        self.attempt = None
        proposal = request.proposal
        selected = select_attempt_arm(
            tuple(arm for arm, _ in self._arm_stages),
            self._loaded_ocp,
            position_effect=getattr(proposal, "position_effect", None),
            direction=getattr(proposal, "direction", None),
        )
        if isinstance(selected, str):
            self.construction = CandidateConstruction(
                derivation=QuantityDerivation(
                    outcome=DerivationOutcome.DENIED, denial_reason=selected
                ),
                denial_reason=selected,
            )
            return candidate_command_verdict(self.construction, step=request.step)
        (stage,) = [s for arm, s in self._arm_stages if arm is selected]
        verdict = stage(self._shaped_request(request))
        self.attempt = selected
        self.construction = stage.construction
        return verdict
