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

from shared.stock_universe import (
    build_effective_universe_snapshot,
    decode_payload,
    parse_effective_universe_codes,
    select_stock_universe,
)

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
    return select_stock_universe(
        trade_targets=list(seen),
        watchlist=[],
        max_symbols=max_symbols,
    )


# Synthetic group key under which screener trade-targets are folded into the
# watchlist payload. Underscore-prefixed so it can't collide with a real
# scanner strategy name.
_SCREENER_GROUP = "_screener_trade_targets"
_SCREENER_PAYLOAD_KEY = "_screener_trade_targets_payload"
_EFFECTIVE_GROUP = "_effective_trading_universe"
_EFFECTIVE_PAYLOAD_KEY = "_effective_trading_universe_payload"


def _filter_payload_codes(payload: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    """Return a trade-target payload narrowed to active entry-universe symbols."""

    filtered = dict(payload)
    codes = [
        code
        for code in (str(c).strip() for c in payload.get("codes", []))
        if code and code in allowed
    ]
    filtered["codes"] = codes
    for key in ("names", "scores", "metadata"):
        value = payload.get(key)
        if isinstance(value, dict):
            filtered[key] = {code: value[code] for code in codes if code in value}
    return filtered


def effective_universe_to_watchlist(
    effective_raw: Any,
    *,
    watchlist_raw: Any = None,
    trade_targets_raw: Any = None,
    max_symbols: int,
) -> dict:
    """Convert an effective-universe snapshot to daemon watchlist shape."""

    effective = decode_payload(effective_raw) or {}
    active_codes = parse_effective_universe_codes(
        effective,
        max_symbols=max_symbols,
        field="codes",
    )
    if not active_codes:
        return {}

    active_set = set(active_codes)
    watchlist_payload = decode_payload(watchlist_raw) or {}
    original_strategies = watchlist_payload.get("strategies", {})
    strategies: dict[str, list[str]] = {_EFFECTIVE_GROUP: active_codes}
    if isinstance(original_strategies, dict):
        for name, values in original_strategies.items():
            if not isinstance(values, list) or name in {
                _SCREENER_GROUP,
                _EFFECTIVE_GROUP,
            }:
                continue
            filtered = [
                code
                for code in (str(c).strip() for c in values)
                if code and code in active_set
            ]
            if filtered:
                strategies[str(name)] = filtered

    trade_targets_payload = decode_payload(trade_targets_raw) or {}
    if trade_targets_payload:
        filtered_targets = _filter_payload_codes(trade_targets_payload, active_set)
        target_codes = filtered_targets.get("codes", [])
        if isinstance(target_codes, list) and target_codes:
            strategies = {_SCREENER_GROUP: target_codes, **strategies}
        watchlist_payload[_SCREENER_PAYLOAD_KEY] = filtered_targets

    watchlist_payload[_EFFECTIVE_PAYLOAD_KEY] = effective
    watchlist_payload["strategies"] = strategies
    watchlist_payload["generated_at"] = effective.get("generated_at")
    return watchlist_payload


def build_effective_watchlist(
    *,
    watchlist_raw: Any = None,
    trade_targets_raw: Any = None,
    overrides_raw: Any = None,
    effective_raw: Any = None,
    max_symbols: int,
) -> dict:
    """Return a daemon watchlist using managed effective universe when possible."""

    effective_watchlist = effective_universe_to_watchlist(
        effective_raw,
        watchlist_raw=watchlist_raw,
        trade_targets_raw=trade_targets_raw,
        max_symbols=max_symbols,
    )
    if effective_watchlist:
        return effective_watchlist

    snapshot = build_effective_universe_snapshot(
        trade_targets_raw=trade_targets_raw,
        daily_watchlist_raw=watchlist_raw,
        overrides_raw=overrides_raw,
        max_symbols=max_symbols,
    )
    if snapshot.get("codes"):
        return effective_universe_to_watchlist(
            snapshot,
            watchlist_raw=watchlist_raw,
            trade_targets_raw=trade_targets_raw,
            max_symbols=max_symbols,
        )

    return merge_screener_universe(
        watchlist_raw,
        trade_targets_raw,
        max_symbols=max_symbols,
    )


def merge_screener_universe(
    watchlist_raw: Any, trade_targets_raw: Any, *, max_symbols: int
) -> dict:
    """Fold screener trade-targets into the daily-watchlist payload.

    Returns a watchlist-shaped dict whose ``strategies`` map carries selected
    screener trade-targets first plus the scanner candidates, so
    ``parse_watchlist_codes`` yields ``trade_targets ∪ daily_watchlist`` under
    the same cap order market-ingest uses.
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
    strategies = {
        key: value
        for key, value in dict(payload.get("strategies") or {}).items()
        if key != _SCREENER_GROUP
    }
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
    watchlist_codes = parse_watchlist_codes(
        {"strategies": strategies},
        max_symbols=max_symbols,
    )
    selected = select_stock_universe(
        trade_targets=targets,
        watchlist=watchlist_codes,
        max_symbols=max_symbols,
    )
    if targets:
        target_set = set(targets)
        selected_targets = [code for code in selected if code in target_set]
        strategies = {_SCREENER_GROUP: selected_targets, **strategies}
        # Preserve the fused target metadata for downstream signal generation.
        # The strategy gate still sees a normal watchlist-shaped payload; the
        # extra key is ignored by parse_watchlist_codes and daily strategy gates.
        payload[_SCREENER_PAYLOAD_KEY] = trade_targets_payload
    payload["strategies"] = strategies
    return payload
