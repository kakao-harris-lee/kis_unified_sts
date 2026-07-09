"""Runtime-support checks for no-code Strategy Builder states.

Historically the streaming runtime fed ``builder_v1`` strategies only the latest
scalar indicator value per cycle, so the cross operators (``cross_above`` /
``cross_below``) — which need a distinct previous observation — could never fire,
and this module refused to enable such strategies.

That limitation is gone. The declarative Indicator Context
(``shared/strategy_builder/indicator_context.py``) computes every indicator from
the OHLCV history window via the TA-Lib engine and hands the evaluator the *full*
series, so cross operators (and arbitrary-period moving averages) now work in
every runtime that runs ``builder_v1`` (stock daemon, monolith orchestrator,
backtest).

The module is retained as a stable API for its callers (the strategy factory and
the dashboard support-hint endpoint) but the unsupported-operator set is now
empty, so every state reports as supported. Add operators back here only if a
future runtime genuinely cannot evaluate them.
"""

from __future__ import annotations

from shared.strategy_builder.schema import BuilderState, ConditionOperator

# No operators are unsupported anymore — the full-series Indicator Context makes
# cross detection work everywhere builder_v1 runs. Kept as an extensible hook.
STREAMING_UNSUPPORTED_OPERATORS: frozenset[ConditionOperator] = frozenset()


def unsupported_streaming_operators(state: BuilderState) -> list[ConditionOperator]:
    """Return the distinct streaming-unsupported operators used by ``state``.

    Scans every condition group (entry, entry_short when present, exit). Always
    returns an empty list now that the full-series context supports every
    operator — including the schema-v2 percentile_rank_* operators, which only
    need the trailing window the Indicator Context already carries — but the
    scan is kept so re-introducing an unsupported operator is a one-line change
    above.

    Args:
        state: Parsed builder state.

    Returns:
        Sorted-by-value list of unique unsupported operators (currently always
        empty).
    """
    if not STREAMING_UNSUPPORTED_OPERATORS:
        return []
    found: set[ConditionOperator] = set()
    for _name, group in state.condition_groups():
        for condition in group.conditions:
            if condition.operator in STREAMING_UNSUPPORTED_OPERATORS:
                found.add(condition.operator)
    return sorted(found, key=lambda op: op.value)


def is_streaming_supported(state: BuilderState) -> bool:
    """True when ``state`` can fire in the streaming runtime (always true now)."""
    return not unsupported_streaming_operators(state)


def streaming_support_reason(state: BuilderState) -> str | None:
    """Human-readable reason a state is unsupported, or ``None`` if supported.

    Returns ``None`` for every state now that cross detection works; retained so
    callers (factory skip-guard, dashboard hint) keep a stable interface.
    """
    operators = unsupported_streaming_operators(state)
    if not operators:
        return None
    names = ", ".join(op.value for op in operators)
    return (
        "builder_v1 uses operators unsupported by the current runtime "
        f"(operators: {names})"
    )
