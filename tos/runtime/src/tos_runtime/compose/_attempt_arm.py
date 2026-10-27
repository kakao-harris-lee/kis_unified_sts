"""``tos_runtime.compose._attempt_arm`` — the arm step 2 selected for the CURRENT attempt
(issue #960; selection lives in :mod:`tos_runtime.compose._attempt_shape`), and the reads every
later per-attempt consumer (steps 3/7/14, the send-boundary context) shares.

Split out only so ``context.py`` can import these without an import cycle through
``_envelope_wiring``. Firewall: stdlib + ``tos.*`` only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tos.egressgw import OrderConstructionStage, ProposedConstructionEnvelope
from tos.venue import ActionClass

__all__ = ["AttemptArm", "attempt_action_class", "attempt_reader", "attempt_side"]


@dataclass(frozen=True)
class AttemptArm:
    """One ``(action_class, direction)`` arm of the OCP's ``action_class_shape`` this
    composition can construct, with the envelope built for it. ``direction`` is the OCP key
    (the held position for ``CLOSE``), not the proposal's own ``direction``."""

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
    """The current attempt's side; ``boot_side`` only when step 2 selected no arm — a plain
    kernel stage (its one envelope IS the boot arm) or a refused attempt (no command to send).
    """
    arm = getattr(stage, "attempt", None)
    return boot_side if arm is None else arm.side


def attempt_action_class(
    stage: OrderConstructionStage, boot_action_class: ActionClass
) -> ActionClass:
    """The current attempt's action class — same ``None`` rule as :func:`attempt_side`."""
    arm = getattr(stage, "attempt", None)
    return boot_action_class if arm is None else arm.action_class
