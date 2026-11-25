"""The typed Order Construction rules an OCP document declares — the (a′) wave's contract."""

from __future__ import annotations

from dataclasses import dataclass

from tos.egressgw import EffectDimensionSpec, SizingBound
from tos.ioc import AxisBinding
from tos.venue import ActionClass

__all__ = [
    "ActionClassShape",
    "ConstructionRules",
]


@dataclass(frozen=True)
class ActionClassShape:
    """The side / position-effect one ``(ActionClass, direction)`` pair maps to."""

    side: str
    position_effect: str


@dataclass(frozen=True)
class ConstructionRules:
    """The machine-readable construction rules one OCP generation declares."""

    sizing_bound: SizingBound
    admitted_quantity_bases: frozenset[str]
    authorized_axes: tuple[AxisBinding, ...]
    action_class_shape: dict[tuple[ActionClass, str], ActionClassShape]
    effect_dimensions: tuple[EffectDimensionSpec, ...]
