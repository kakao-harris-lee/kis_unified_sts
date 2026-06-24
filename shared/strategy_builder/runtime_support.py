"""Runtime-support checks for no-code Strategy Builder states.

The decoupled streaming runtime (M4-P stock-strategy daemon and the futures
decision-engine) feeds ``builder_v1`` strategies only the latest scalar
indicator values per cycle — it does NOT carry a persistent N-length history
series across cycles. The builder cross operators (``cross_above`` /
``cross_below``) require two *distinct* observations (previous vs. current) to
detect a transition; with only a single scalar per cycle they can never fire.

In addition, the streaming indicator engine
(``services/trading/indicator_engine.py``) does not emit arbitrary-period SMA
series keyed by the builder's per-alias periods, so a config like
``golden_cross`` (``sma_fast cross_above sma_slow``) has no operands to compare
even before the history problem.

This module centralizes the "is this builder strategy able to fire in the
streaming runtime?" decision so the dashboard enable-guard and the runtime
entry/exit adapters agree on a single rule (DRY). Restoring cross support is a
feature-sized engine/resolver rework tracked as a follow-up; until then these
helpers let callers refuse to enable, or warn loudly about, strategies that
would otherwise masquerade as active-but-silent.
"""

from __future__ import annotations

from shared.strategy_builder.schema import BuilderState, ConditionOperator

# Operators that depend on cross-cycle history the streaming runtime does not
# provide. Kept as a frozenset so callers can extend the rule in one place.
STREAMING_UNSUPPORTED_OPERATORS: frozenset[ConditionOperator] = frozenset(
    {ConditionOperator.CROSS_ABOVE, ConditionOperator.CROSS_BELOW}
)

_UNSUPPORTED_REASON = (
    "builder_v1 streaming-series cross detection is unsupported in the "
    "decoupled runtime: cross_above/cross_below need two distinct historical "
    "observations and arbitrary-period SMA series, neither of which the "
    "streaming indicator engine provides. The strategy would never fire."
)


def unsupported_streaming_operators(state: BuilderState) -> list[ConditionOperator]:
    """Return the distinct streaming-unsupported operators used by ``state``.

    Scans both the entry and exit condition groups. Returns an empty list when
    the strategy is safe to run in the streaming runtime.

    Args:
        state: Parsed builder state.

    Returns:
        Sorted-by-value list of unique unsupported operators (empty if none).
    """
    found: set[ConditionOperator] = set()
    for group in (state.entry, state.exit):
        for condition in group.conditions:
            if condition.operator in STREAMING_UNSUPPORTED_OPERATORS:
                found.add(condition.operator)
    return sorted(found, key=lambda op: op.value)


def is_streaming_supported(state: BuilderState) -> bool:
    """True when ``state`` can actually fire in the streaming runtime."""
    return not unsupported_streaming_operators(state)


def streaming_support_reason(state: BuilderState) -> str | None:
    """Human-readable reason a state is unsupported, or ``None`` if supported.

    The message names the offending operators so operators (and logs) can see
    exactly why a strategy is inert.
    """
    operators = unsupported_streaming_operators(state)
    if not operators:
        return None
    names = ", ".join(op.value for op in operators)
    return f"{_UNSUPPORTED_REASON} (operators: {names})"
