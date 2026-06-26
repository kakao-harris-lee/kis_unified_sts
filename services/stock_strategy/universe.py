"""Stock universe parsing for the decoupled stock pipeline.

The trading universe is the UNION of two sources, so screening quality actually
drives strategy entries:

  - daily-watchlist (``system:daily_watchlist:latest``): per-strategy technical
    candidates from the daily/indicator scanners (payload ``{"strategies": {...}}``).
  - screener trade-targets (``system:trade_targets:latest``): the screener/fusion
    real-time ranked candidates (payload ``{"codes": [...]}``).

``parse_watchlist_codes`` unions the code lists under ``payload["strategies"]``;
``merge_screener_universe`` folds the trade-targets in as one more code group so
the same parser yields the combined universe. The market-ingest daemon ticks the
same union (see ``services.market_ingest``), keeping producer/consumer aligned.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_watchlist_codes(raw: Any, *, max_symbols: int) -> list[str]:
    """Parse the watchlist payload into a capped, ordered code list.

    Accepts a JSON string or an already-decoded dict. Returns [] on
    None / malformed / empty (caller keeps the prior universe).
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        payload: Any = raw
    else:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning(
                "watchlist payload is not valid JSON; keeping prior universe"
            )
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


def parse_trade_targets_codes(raw: Any, *, max_symbols: int) -> list[str]:
    """Parse a ``system:trade_targets:latest`` payload (``{"codes": [...]}``).

    Accepts a JSON string or a dict. Returns [] on None / malformed / empty.
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        payload: Any = raw
    else:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return []
    if not isinstance(payload, dict):
        return []
    seen: dict[str, None] = {}
    for c in payload.get("codes", []):
        code = str(c).strip()
        if code:
            seen.setdefault(code, None)
    return list(seen)[:max_symbols]


# Synthetic group key under which screener trade-targets are folded into the
# watchlist payload. Underscore-prefixed so it can't collide with a real
# scanner strategy name.
_SCREENER_GROUP = "_screener_trade_targets"
_SCREENER_PAYLOAD_KEY = "_screener_trade_targets_payload"


def merge_screener_universe(
    watchlist_raw: Any, trade_targets_raw: Any, *, max_symbols: int
) -> dict:
    """Fold screener trade-targets into the daily-watchlist payload.

    Returns a watchlist-shaped dict whose ``strategies`` map carries the scanner
    candidates FIRST (kept ahead in the cap) plus a ``_screener_trade_targets``
    group, so ``parse_watchlist_codes`` yields ``daily_watchlist ∪ trade_targets``.
    """
    payload: dict = {}
    if watchlist_raw:
        try:
            decoded = (
                watchlist_raw
                if isinstance(watchlist_raw, dict)
                else json.loads(watchlist_raw)
            )
            if isinstance(decoded, dict):
                payload = dict(decoded)
        except (TypeError, ValueError):
            payload = {}
    strategies = dict(payload.get("strategies") or {})
    trade_targets_payload: dict[str, Any] = {}
    if trade_targets_raw:
        try:
            decoded_targets = (
                trade_targets_raw
                if isinstance(trade_targets_raw, dict)
                else json.loads(trade_targets_raw)
            )
            if isinstance(decoded_targets, dict):
                trade_targets_payload = dict(decoded_targets)
        except (TypeError, ValueError):
            trade_targets_payload = {}

    targets = parse_trade_targets_codes(
        trade_targets_payload or trade_targets_raw,
        max_symbols=max_symbols,
    )
    if targets:
        strategies[_SCREENER_GROUP] = targets
        # Preserve the fused target metadata for downstream signal generation.
        # The strategy gate still sees a normal watchlist-shaped payload; the
        # extra key is ignored by parse_watchlist_codes and daily strategy gates.
        payload[_SCREENER_PAYLOAD_KEY] = trade_targets_payload
    payload["strategies"] = strategies
    return payload
