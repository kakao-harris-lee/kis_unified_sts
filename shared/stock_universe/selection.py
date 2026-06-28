"""Pure stock-universe cap selection."""

from __future__ import annotations


def select_stock_universe(
    *,
    trade_targets: list[str],
    watchlist: list[str],
    max_symbols: int,
    existing: list[str] | None = None,
) -> list[str]:
    """Return a capped ordered union: trade targets, watchlist, then existing."""

    if max_symbols <= 0:
        return []

    selected: dict[str, None] = {}
    for source in (trade_targets, watchlist, existing or []):
        for raw_code in source:
            code = str(raw_code).strip()
            if code:
                selected.setdefault(code, None)
            if len(selected) >= max_symbols:
                return list(selected)
    return list(selected)
