"""Conservative quantity bound shared by close admission and entry discharge."""

from __future__ import annotations

from decimal import Decimal


def close_within_entry(
    entry: Decimal | None, closed: Decimal | None, proposed: Decimal | None
) -> bool | None:
    """Whether proven close quantities fit the entry; unknown inputs stay unknown."""
    if entry is None or closed is None or proposed is None:
        return None
    if not all(value.is_finite() and value >= 0 for value in (entry, closed, proposed)):
        return None
    return closed + proposed <= entry
