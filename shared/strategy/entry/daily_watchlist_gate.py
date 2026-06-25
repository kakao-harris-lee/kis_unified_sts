"""Shared per-strategy daily-watchlist gate semantics.

A strategy is *daily-gated* only when the pre-open scanner produced a NON-EMPTY
candidate list for it. An empty or absent per-strategy list means "no daily
constraint" → dynamic mode (evaluate the live universe against the strategy's
own intraday conditions), NOT "exclude every symbol".

Centralizing this prevents the recurring bug where one populated strategy makes
the whole ``daily_watchlist`` dict truthy and silently gates every other
(empty-list) strategy to zero — the decoupled-stock no-trade root cause where a
single ``trend_pullback`` candidate gated ``momentum_breakout`` (empty list) to
``no_daily_watchlist`` on every symbol.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def daily_watchlist_allows(
    metadata: Mapping[str, Any] | None, strategy_name: str, code: str
) -> bool:
    """Return True when ``code`` may proceed past the daily-watchlist gate.

    Allowed when the strategy has no non-empty pre-screen list (dynamic mode)
    or when ``code`` is on that list. Returns False only in static mode — the
    per-strategy list is non-empty and ``code`` is absent.

    Tolerant of malformed metadata: a missing/ill-typed ``daily_watchlist`` or
    ``strategies`` map is treated as "no constraint" (dynamic mode), so a bad
    scanner payload degrades to evaluating the live universe rather than
    blocking it.
    """
    if not isinstance(metadata, Mapping):
        return True
    watchlist = metadata.get("daily_watchlist")
    if not isinstance(watchlist, Mapping):
        return True
    strategies = watchlist.get("strategies")
    if not isinstance(strategies, Mapping):
        return True
    codes = strategies.get(strategy_name)
    # Absent / empty / non-list (malformed) → dynamic mode (no daily
    # constraint). Requiring a real collection also avoids a substring match
    # if a payload ever stored a bare string instead of a list.
    if not isinstance(codes, (list, tuple, set)) or not codes:
        return True
    return code in codes
