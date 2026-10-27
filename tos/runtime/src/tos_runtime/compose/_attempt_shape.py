"""``tos_runtime.compose._attempt_shape`` — step 2 builds each command from the PROPOSAL's own
``(position_effect, direction)``, never from the boot-time action class (issue #960).

**The defect this closes.** Step 2 used to hold ONE envelope, built at boot from
``construction.action_class`` (``NEW_LONG`` in every shipped tree), so every command — a CLOSE
proposal's included — carried that envelope's SIDE (``BUY``). A standing-approval exit boundary
(``CLOSE-SHORT-SELL``) therefore never matched, and a CLOSE approved by a per-proposal file sent
a second BUY instead of selling.

**Rule (one per attempt).** The composition's arms are the boot action class's own arm plus
every direction-agnostic arm (``CLOSE`` …) the OCP resolves — both built by the SAME
:func:`~tos_runtime.compose._envelope_wiring.build_construction_envelope` as before, so an
OPEN proposal gets the byte-identical envelope it always got. A proposal selects the ONE arm
whose ``position_effect`` equals the proposal's and whose ``side`` is the side the OCP gives an
action in the proposal's ``direction``.

Why "side of an action in that direction": ``Proposal.direction`` is the direction of the
ACTION (``tos/src/tos/dsl/proposal.py::build_flat`` — "The direction of the closing action";
a long is closed by ``direction: SHORT``), while the OCP keys ``CLOSE`` arms by the HELD
position (``CLOSE.LONG = SELL``; ``config/tos_runtime/cp3-setup-d-short/README.md`` §3.2).
The OCP's direction-named arms (``NEW_LONG.LONG``/``NEW_SHORT.SHORT``) already state which
side acts in each direction, so reading that side bridges the two spellings with no second
LONG/SHORT table here:

=====================  ===============  ======================
proposal (effect, dir)  action side      arm selected
=====================  ===============  ======================
(OPEN, LONG)            BUY  (NEW_LONG)   NEW_LONG.LONG  BUY/OPEN
(CLOSE, SHORT)          SELL (NEW_SHORT)  CLOSE.LONG     SELL/CLOSE
(CLOSE, LONG)           BUY  (NEW_LONG)   CLOSE.SHORT    BUY/CLOSE  (a short tree)
=====================  ===============  ======================

No arm, or more than one, is a step-2 DENY carrying the reason — the same denied
:class:`~tos.egressgw.CandidateConstruction` shape a denied size derivation produces — never a
fallback to the boot action class.

Firewall: stdlib + ``tos.*`` + ``tos_runtime.*`` only.
"""

from __future__ import annotations

from typing import Any

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
    """The boot arm first, then every direction-agnostic arm the OCP resolves (module docstring).

    The boot arm keeps today's boot refusal (:class:`SideDerivationRefused` propagates). A
    direction-agnostic class whose arm cannot be resolved is simply absent — a proposal that
    needs it is refused per attempt, not at boot.
    """
    rules = loaded_ocp.construction_rules

    def _arm(action_class: ActionClass) -> AttemptArm:
        # ONE arm per class: the direction is this tree's own governed DIRECTION axis
        # (`resolve_construction_direction`), so a long tree builds `CLOSE.LONG` (SELL) only and
        # a short tree `CLOSE.SHORT` (BUY) only — a tree that traded both directions would need
        # both CLOSE arms here, and today's trees are single-direction by construction.
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
    """Step 2, with the envelope chosen per attempt by :func:`select_attempt_arm`.

    One unmodified kernel :class:`~tos.egressgw.OrderConstructionStage` per arm, built through
    its public constructor (no private kernel attribute is written); this stage delegates to
    the selected one and republishes its :attr:`construction`. :attr:`attempt` is the arm the
    CURRENT attempt selected (``None`` before step 2 ran or when it refused) — steps 3/7/14 and
    the send-boundary context read it so the whole attempt uses one action class and one side.
    :attr:`effect_specs` follows the same arm, since step 5 derives its envelope from it.
    """

    def __init__(
        self,
        *,
        arms: tuple[AttemptArm, ...],
        loaded_ocp: LoadedOrderConstructionPolicy,
        **stage_kwargs: Any,
    ) -> None:
        super().__init__(envelope=arms[0].envelope, **stage_kwargs)
        self._arm_stages = tuple(
            (arm, OrderConstructionStage(envelope=arm.envelope, **stage_kwargs))
            for arm in arms
        )
        self._loaded_ocp = loaded_ocp
        self.attempt: AttemptArm | None = None

    @property
    def effect_specs(self) -> tuple[EffectDimensionSpec, ...]:
        """THIS attempt's arm's Economic Effect Envelope specs (#960 review LOW-1).

        Step 5 (:class:`~tos.egressgw.EconomicEffectStage`) derives its envelope from this
        property, so a CLOSE attempt must not report the BOOT arm's specs — the kernel's own
        property reads the one envelope it was constructed with, which here is the boot arm's.
        Falls back to that boot arm when step 2 selected none (nothing to send anyway).
        """
        arm = self.attempt
        return super().effect_specs if arm is None else arm.envelope.effect_dimensions

    def __call__(self, request: StageRequest) -> StageVerdict:
        self.attempt = (
            None  # never a previous attempt's arm, even if a stage below raises
        )
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
        verdict = stage(request)
        self.attempt = selected
        self.construction = stage.construction
        return verdict
