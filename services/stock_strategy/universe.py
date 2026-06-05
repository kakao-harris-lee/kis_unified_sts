"""Stock universe parsing from the daily-watchlist Redis payload.

Mirrors the orchestrator's _load_static_watchlist parse: union the code lists
under payload["strategies"], stripped + de-duplicated, capped at max_symbols.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_watchlist_codes(raw: Any, *, max_symbols: int) -> list[str]:
    """Parse the watchlist JSON string into a capped, ordered code list.

    Returns [] on None / malformed / empty (caller keeps the prior universe).
    """
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("watchlist payload is not valid JSON; keeping prior universe")
        return []
    strategies = payload.get("strategies", {}) if isinstance(payload, dict) else {}
    seen: dict[str, None] = {}  # ordered de-dup
    for strat_codes in strategies.values():
        if isinstance(strat_codes, list):
            for c in strat_codes:
                code = str(c).strip()
                if code:
                    seen.setdefault(code, None)
    return list(seen)[:max_symbols]
