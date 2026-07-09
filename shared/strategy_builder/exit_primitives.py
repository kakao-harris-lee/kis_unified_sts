"""Named exit-primitive validation for builder_v1 states (schema v2).

A ``BuilderState.exit_primitive`` references a registered exit component by
its ``ExitRegistry`` name. Validation is two-layered:

1. **ExitRegistry** is the source of truth for *existence* — an unregistered
   name can never be constructed.
2. **The builder catalog** (``config/strategy_builder/indicators.yaml``
   ``exit_primitives``) is an explicit **allow-list** for *exposure* — a
   registered exit that is not cataloged is rejected. Many registry exits are
   deliberately not builder-safe (e.g. ``track_a_exit`` defaults to EOD close,
   which would violate the "no blanket stock EOD liquidation" rule), so
   exposure is opt-in with per-primitive ``asset_classes`` restrictions.

The strategy factory composes the referenced primitive with the declarative
``builder_v1_exit`` risk block; this module owns the validation shared by the
factory and the dashboard validate/register endpoints.

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
    """Validate ``state.exit_primitive`` (registry existence + catalog allow-list).

    Checks, in order: self-reference, ExitRegistry membership, catalog
    allow-list membership, and the per-primitive ``asset_classes`` restriction
    declared in the builder catalog (e.g. ``three_stage`` is stock-only).

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
    definitions = exit_primitive_definitions()
    allowed = sorted(definitions)
    if not ExitRegistry.is_registered(name):
        return (
            f"unknown exit primitive '{name}' (not in ExitRegistry). "
            f"Available: {allowed}"
        )

    definition = definitions.get(name)
    if definition is None:
        return (
            f"exit primitive '{name}' is registered but not exposed to the "
            "builder; add a catalog entry (config/strategy_builder/"
            "indicators.yaml exit_primitives, with asset_classes) to enable "
            f"it. Available: {allowed}"
        )
    if state.asset_class not in definition.asset_classes:
        return (
            f"exit primitive '{name}' is restricted to asset_classes="
            f"{definition.asset_classes} and cannot be used with "
            f"asset_class={state.asset_class!r}"
        )
    return None
