"""Named exit-primitive validation for builder_v1 states (schema v2).

A ``BuilderState.exit_primitive`` references a registered exit component by
its ``ExitRegistry`` name (the registry is the single source of truth for
valid names). The strategy factory composes the referenced primitive with the
declarative ``builder_v1_exit`` risk block; this module owns the validation
shared by the factory and the dashboard validate/register endpoints.

Kept separate from ``schema.py`` so the pydantic layer stays free of registry
imports (registry population happens at runtime via
``register_builtin_components``).
"""

from __future__ import annotations

from shared.strategy_builder.catalog import exit_primitive_definitions
from shared.strategy_builder.schema import BuilderState

# The builder's own declarative exit is not composable with itself.
_SELF_REFERENTIAL = frozenset({"builder_v1_exit"})


def validate_exit_primitive(state: BuilderState) -> str | None:
    """Validate ``state.exit_primitive`` against the ExitRegistry (SoT).

    Checks, in order: self-reference, registry membership, and the optional
    per-primitive ``asset_classes`` restriction declared in the builder
    catalog (e.g. ``three_stage`` is stock-only).

    Args:
        state: Parsed builder state.

    Returns:
        An actionable error message, or ``None`` when the reference is valid
        (or absent).
    """
    ref = state.exit_primitive
    if ref is None:
        return None

    name = ref.primitive
    if name in _SELF_REFERENTIAL:
        return (
            f"exit_primitive '{name}' is the builder's own declarative exit and "
            "cannot be composed with itself; pick a stateful primitive such as "
            "three_stage, atr_dynamic, chandelier_exit, or momentum_decay"
        )

    from shared.strategy.registry import ExitRegistry, register_builtin_components

    register_builtin_components()
    if not ExitRegistry.is_registered(name):
        available = sorted(set(ExitRegistry.list_all()) - _SELF_REFERENTIAL)
        return (
            f"unknown exit primitive '{name}' (not in ExitRegistry). "
            f"Available: {available}"
        )

    definition = exit_primitive_definitions().get(name)
    if definition is not None and state.asset_class not in definition.asset_classes:
        return (
            f"exit primitive '{name}' is restricted to asset_classes="
            f"{definition.asset_classes} and cannot be used with "
            f"asset_class={state.asset_class!r}"
        )
    return None
