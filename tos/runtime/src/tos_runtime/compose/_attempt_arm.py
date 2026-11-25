"""``tos_runtime.compose._attempt_arm`` — the arm step 2 selected for the CURRENT attempt"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tos.egressgw import OrderConstructionStage, ProposedConstructionEnvelope
from tos.venue import ActionClass

__all__ = [
    "AttemptArm",
    "attempt_action_class",
    "attempt_position_effect",
    "attempt_reader",
    "attempt_side",
]


@dataclass(frozen=True)
class AttemptArm:
    """One ``(action_class, direction)`` arm of the OCP's ``action_class_shape`` this"""

    action_class: ActionClass
    direction: str
    side: str
    position_effect: str
    envelope: ProposedConstructionEnvelope


def attempt_reader(
    stage: OrderConstructionStage,
) -> Callable[[], AttemptArm | None]:
    """A zero-argument read of ``stage``'s current arm (``None`` for a plain kernel stage)."""
    return lambda: getattr(stage, "attempt", None)


def attempt_side(stage: OrderConstructionStage, boot_side: str) -> str:
    """The current attempt's side; ``boot_side`` only when step 2 selected no arm — a plain"""
    arm = getattr(stage, "attempt", None)
    return boot_side if arm is None else arm.side


def attempt_action_class(
    stage: OrderConstructionStage, boot_action_class: ActionClass
) -> ActionClass:
    """The current attempt's action class — same ``None`` rule as :func:`attempt_side`."""
    arm = getattr(stage, "attempt", None)
    return boot_action_class if arm is None else arm.action_class


def attempt_position_effect(stage: OrderConstructionStage) -> str | None:
    """The current attempt's position effect, or ``None`` when step 2 selected no arm."""
    arm = getattr(stage, "attempt", None)
    return None if arm is None else arm.position_effect
