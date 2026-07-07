"""Effective stock trading-universe builder.

The symbol master is only a lookup table. This module builds the operational
universe that stock entry services may evaluate, and the wider market-data
universe that must remain subscribed for open-position monitoring.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

DEFAULT_EFFECTIVE_UNIVERSE_KEY = "stock:universe:effective:latest"
DEFAULT_OVERRIDES_KEY = "stock:universe:overrides"
DEFAULT_AUDIT_KEY = "stock:universe:audit"
DEFAULT_UNIVERSE_TTL_SECONDS = 86_400
DEFAULT_OVERRIDES_TTL_SECONDS = 172_800
DEFAULT_AUDIT_TTL_SECONDS = 604_800
DEFAULT_SOURCE_STALE_SECONDS = 1_800

SOURCE_ORDER = (
    "manual_include",
    "trade_targets",
    "daily_watchlist",
    "open_position",
)


def decode_payload(raw: Any) -> dict[str, Any] | None:
    """Decode a Redis JSON payload into a dict, returning None on bad input."""

    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode(errors="replace")
    if isinstance(raw, dict):
        return raw
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def clean_code(value: Any) -> str:
    """Normalize a stock code-like value."""

    return str(value or "").strip()


def ordered_unique(values: list[Any] | tuple[Any, ...] | set[Any]) -> list[str]:
    """Return non-empty codes in first-seen order."""

    seen: dict[str, None] = {}
    for value in values:
        code = clean_code(value)
        if code:
            seen.setdefault(code, None)
    return list(seen)


def extract_codes(payload: dict[str, Any] | None) -> list[str]:
    """Extract stock codes from known universe payload shapes."""

    if not payload:
        return []

    seen: dict[str, None] = {}

    def add(value: Any) -> None:
        code = clean_code(value)
        if code:
            seen.setdefault(code, None)

    for key in ("codes", "symbols", "final_codes", "market_data_codes"):
        values = payload.get(key)
        if isinstance(values, list):
            for value in values:
                add(value)

    indicators = payload.get("indicators")
    if isinstance(indicators, dict):
        for code in indicators:
            add(code)

    strategies = payload.get("strategies")
    if isinstance(strategies, dict):
        for values in strategies.values():
            if isinstance(values, list):
                for value in values:
                    add(value)

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for code in metadata:
            add(code)

    return list(seen)


def clean_name(value: Any) -> str:
    """Normalize a stock display name."""

    if value is None:
        return ""
    name = str(value).strip()
    if not name or name.lower() in {"none", "null"}:
        return ""
    return name


def extract_names(payload: dict[str, Any] | None) -> dict[str, str]:
    """Extract code -> display-name mappings from known payload shapes."""

    if not payload:
        return {}

    names: dict[str, str] = {}

    raw_names = payload.get("names")
    if isinstance(raw_names, dict):
        for code, name in raw_names.items():
            clean = clean_name(name)
            if code and clean:
                names[clean_code(code)] = clean
    elif isinstance(raw_names, list):
        codes = payload.get("codes") or payload.get("symbols") or []
        if isinstance(codes, list):
            for code, name in zip(codes, raw_names, strict=False):
                clean = clean_name(name)
                if code and clean:
                    names[clean_code(code)] = clean

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for code, item in metadata.items():
            if not isinstance(item, dict):
                continue
            clean = clean_name(
                item.get("name")
                or item.get("stock_name")
                or item.get("symbol_name")
                or item.get("prdt_name")
            )
            if code and clean:
                names.setdefault(clean_code(code), clean)

    return names


def _score_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_scores(payload: dict[str, Any] | None) -> dict[str, float]:
    """Extract code -> numeric score mappings from known payload shapes."""

    if not payload:
        return {}
    scores: dict[str, float] = {}
    raw_scores = payload.get("scores")
    if isinstance(raw_scores, dict):
        for code, value in raw_scores.items():
            score = _score_value(value)
            if code and score is not None:
                scores[clean_code(code)] = score
    elif isinstance(raw_scores, list):
        codes = payload.get("codes") or payload.get("symbols") or []
        if isinstance(codes, list):
            for code, value in zip(codes, raw_scores, strict=False):
                score = _score_value(value)
                if code and score is not None:
                    scores[clean_code(code)] = score

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for code, item in metadata.items():
            if not isinstance(item, dict):
                continue
            for key in (
                "score",
                "fused_score",
                "quality_score",
                "llm_effective_quality",
                "llm_quality",
            ):
                score = _score_value(item.get(key))
                if score is not None:
                    scores.setdefault(clean_code(code), score)
                    break
    return scores


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _updated_at(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    value = payload.get("generated_at") or payload.get("updated_at")
    return str(value) if value else None


def _source_summary(
    *,
    name: str,
    key: str,
    payload: dict[str, Any] | None,
    now: datetime,
    stale_after_seconds: int,
) -> dict[str, Any]:
    updated_at = _updated_at(payload)
    parsed_updated = _parse_timestamp(updated_at)
    age_seconds: int | None = None
    stale = False
    if parsed_updated is not None:
        age_seconds = max(0, int((now - parsed_updated).total_seconds()))
        stale = age_seconds > stale_after_seconds
    elif payload is not None:
        stale = False
    return {
        "name": name,
        "key": key,
        "available": payload is not None,
        "count": len(extract_codes(payload)) if payload is not None else None,
        "updated_at": updated_at,
        "age_seconds": age_seconds,
        "stale": stale,
        "source_keys": sorted(payload.keys()) if payload else [],
    }


def _normalize_override_bucket(
    raw: Any, now: datetime
) -> tuple[dict[str, dict], list[dict]]:
    active: dict[str, dict] = {}
    expired: list[dict] = []
    if isinstance(raw, list):
        iterator = ((item, {}) for item in raw)
    elif isinstance(raw, dict):
        iterator = raw.items()
    else:
        return active, expired

    for raw_code, raw_item in iterator:
        code = clean_code(raw_code)
        if not code:
            continue
        item = dict(raw_item) if isinstance(raw_item, dict) else {}
        expires_at = item.get("expires_at")
        parsed_expiry = _parse_timestamp(expires_at)
        normalized = {
            "reason": str(item.get("reason") or "").strip(),
            "created_at": item.get("created_at"),
            "expires_at": expires_at,
            "operator": item.get("operator"),
            "name": clean_name(item.get("name")),
        }
        if parsed_expiry is not None and parsed_expiry <= now:
            expired.append({"code": code, **normalized})
            continue
        active[code] = normalized
    return active, expired


def normalize_overrides(raw: Any, *, now: datetime) -> dict[str, Any]:
    """Normalize manual include/exclude override payloads and drop expirations."""

    payload = decode_payload(raw) or {}
    manual_include, expired_include = _normalize_override_bucket(
        payload.get("manual_include") or payload.get("include"),
        now,
    )
    manual_exclude, expired_exclude = _normalize_override_bucket(
        payload.get("manual_exclude") or payload.get("exclude"),
        now,
    )
    return {
        "manual_include": manual_include,
        "manual_exclude": manual_exclude,
        "expired": [
            *({"bucket": "manual_include", **item} for item in expired_include),
            *({"bucket": "manual_exclude", **item} for item in expired_exclude),
        ],
    }


def effective_snapshot_has_expired_overrides(
    raw: Any,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True when a managed effective snapshot carries expired overrides."""

    payload = decode_payload(raw)
    if not payload:
        return False
    now = now or datetime.now(UTC)
    overrides = payload.get("overrides")
    if not isinstance(overrides, dict):
        return False
    for bucket in ("manual_include", "manual_exclude"):
        raw_bucket = overrides.get(bucket)
        if not isinstance(raw_bucket, dict):
            continue
        for item in raw_bucket.values():
            if not isinstance(item, dict):
                continue
            expires_at = _parse_timestamp(item.get("expires_at"))
            if expires_at is not None and expires_at <= now:
                return True
    return False


def merge_names(
    *payloads: dict[str, Any] | None,
    existing_names: dict[str, str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Merge code->name across universe source payloads, positions, overrides.

    This is the single source of truth for the merge-order priority used both
    when building the effective universe snapshot and when resolving a
    display name for a code (e.g. ``/api/trading/universe/resolve``):
    payloads win in the order passed (first match wins), then
    ``existing_names`` (open positions), then override-carried names
    (lowest priority, gap-fill only).
    """
    names: dict[str, str] = {}
    for payload in payloads:
        for code, name in extract_names(payload).items():
            names.setdefault(code, name)
    for code, name in (existing_names or {}).items():
        clean = clean_name(name)
        if clean:
            names.setdefault(clean_code(code), clean)
    if overrides:
        for bucket in ("manual_include", "manual_exclude"):
            for code, item in overrides.get(bucket, {}).items():
                clean = clean_name(item.get("name"))
                if clean:
                    names.setdefault(clean_code(code), clean)
    return names


def _merge_scores(*payloads: dict[str, Any] | None) -> dict[str, float]:
    scores: dict[str, float] = {}
    for payload in payloads:
        for code, score in extract_scores(payload).items():
            scores.setdefault(code, score)
    return scores


def _row_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    rank = row.get("rank")
    if isinstance(rank, int):
        return (0, rank, row["code"])
    if row.get("override") == "manual_exclude":
        return (1, 0, row["code"])
    return (2, 0, row["code"])


def _select_active_codes(
    *,
    manual_include_codes: list[str],
    trade_codes: list[str],
    watchlist_codes: list[str],
    manual_exclude: set[str],
    max_symbols: int,
) -> list[str]:
    if max_symbols <= 0:
        return []
    selected: dict[str, None] = {}
    for source in (manual_include_codes, trade_codes, watchlist_codes):
        for raw_code in source:
            code = clean_code(raw_code)
            if not code or code in manual_exclude:
                continue
            selected.setdefault(code, None)
            if len(selected) >= max_symbols:
                return list(selected)
    return list(selected)


def build_effective_universe_snapshot(
    *,
    screener_raw: Any = None,
    trade_targets_raw: Any = None,
    daily_watchlist_raw: Any = None,
    daily_indicators_raw: Any = None,
    theme_targets_raw: Any = None,
    overrides_raw: Any = None,
    existing_symbols: list[str] | None = None,
    existing_names: dict[str, str] | None = None,
    max_symbols: int = 40,
    now: datetime | None = None,
    source_keys: dict[str, str] | None = None,
    stale_after_seconds: int = DEFAULT_SOURCE_STALE_SECONDS,
) -> dict[str, Any]:
    """Build the entry and market-data universes from source snapshots."""

    now = now or datetime.now(UTC)
    keys = source_keys or {}
    screener = decode_payload(screener_raw)
    trade_targets = decode_payload(trade_targets_raw)
    daily_watchlist = decode_payload(daily_watchlist_raw)
    daily_indicators = decode_payload(daily_indicators_raw)
    theme_targets = decode_payload(theme_targets_raw)
    overrides = normalize_overrides(overrides_raw, now=now)

    trade_codes = extract_codes(trade_targets)
    watchlist_codes = extract_codes(daily_watchlist)
    screener_codes = extract_codes(screener)
    theme_codes = extract_codes(theme_targets)
    daily_indicator_codes = set(extract_codes(daily_indicators))
    existing_codes = ordered_unique(existing_symbols or [])

    manual_include_codes = list(overrides["manual_include"])
    manual_exclude = set(overrides["manual_exclude"])

    active_codes = _select_active_codes(
        manual_include_codes=manual_include_codes,
        trade_codes=trade_codes,
        watchlist_codes=watchlist_codes,
        manual_exclude=manual_exclude,
        max_symbols=max_symbols,
    )
    market_data_codes = ordered_unique([*active_codes, *existing_codes])

    names = merge_names(
        trade_targets,
        daily_watchlist,
        screener,
        theme_targets,
        daily_indicators,
        existing_names=existing_names,
        overrides=overrides,
    )
    scores = _merge_scores(trade_targets, screener, theme_targets)

    all_codes = ordered_unique(
        [
            *active_codes,
            *manual_exclude,
            *trade_codes,
            *watchlist_codes,
            *screener_codes,
            *theme_codes,
            *existing_codes,
        ]
    )
    active_index = {code: index + 1 for index, code in enumerate(active_codes)}
    rows: list[dict[str, Any]] = []
    for code in all_codes:
        sources: list[str] = []
        if code in overrides["manual_include"]:
            sources.append("manual_include")
        if code in trade_codes:
            sources.append("trade_targets")
        if code in watchlist_codes:
            sources.append("daily_watchlist")
        if code in screener_codes:
            sources.append("screener_universe")
        if code in theme_codes:
            sources.append("theme_targets")
        if code in existing_codes:
            sources.append("open_position")
        if code in manual_exclude:
            sources.append("manual_exclude")

        active = code in active_index
        override = None
        blocked_reason = None
        if code in manual_exclude:
            override = "manual_exclude"
            reason = overrides["manual_exclude"][code].get("reason")
            blocked_reason = f"manual_exclude: {reason}" if reason else "manual_exclude"
        elif code in overrides["manual_include"]:
            override = "manual_include"

        if not active and blocked_reason is None:
            if code in trade_codes or code in watchlist_codes:
                blocked_reason = "cap_exceeded"
            elif code in screener_codes or code in theme_codes:
                blocked_reason = "source_not_entry_admitted"
            elif code in existing_codes:
                blocked_reason = "open_position_only"
            else:
                blocked_reason = "not_selected"

        if daily_indicators is None:
            daily_status = "unknown"
        else:
            daily_status = "available" if code in daily_indicator_codes else "missing"

        rows.append(
            {
                "code": code,
                "name": names.get(code),
                "active": active,
                "new_entries_allowed": active and code not in manual_exclude,
                "market_data_required": code in market_data_codes,
                "rank": active_index.get(code),
                "score": scores.get(code),
                "sources": sources,
                "daily_indicator": daily_status,
                "override": override,
                "override_detail": (
                    overrides["manual_include"].get(code)
                    or overrides["manual_exclude"].get(code)
                ),
                "blocked_reason": blocked_reason,
            }
        )

    source_summaries = [
        _source_summary(
            name="screener_universe",
            key=keys.get("screener_universe", "system:universe:latest"),
            payload=screener,
            now=now,
            stale_after_seconds=stale_after_seconds,
        ),
        _source_summary(
            name="trade_targets",
            key=keys.get("trade_targets", "system:trade_targets:latest"),
            payload=trade_targets,
            now=now,
            stale_after_seconds=stale_after_seconds,
        ),
        _source_summary(
            name="daily_watchlist",
            key=keys.get("daily_watchlist", "system:daily_watchlist:latest"),
            payload=daily_watchlist,
            now=now,
            stale_after_seconds=stale_after_seconds,
        ),
        _source_summary(
            name="daily_indicators",
            key=keys.get("daily_indicators", "system:daily_indicators:latest"),
            payload=daily_indicators,
            now=now,
            stale_after_seconds=stale_after_seconds,
        ),
        _source_summary(
            name="theme_targets",
            key=keys.get("theme_targets", "system:theme_targets:latest"),
            payload=theme_targets,
            now=now,
            stale_after_seconds=stale_after_seconds,
        ),
    ]

    notes: list[str] = []
    if not active_codes:
        notes.append("effective entry universe is empty")
    if overrides["expired"]:
        notes.append("expired manual overrides were ignored")
    for source in source_summaries:
        if source["available"] and source["stale"]:
            notes.append(f"{source['name']} is stale")

    return {
        "asset_class": "stock",
        "generated_at": now.isoformat(),
        "codes": active_codes,
        "market_data_codes": market_data_codes,
        "max_symbols": max_symbols,
        "rows": sorted(rows, key=_row_sort_key),
        "sources": source_summaries,
        "overrides": overrides,
        "policy": {
            "source_order": list(SOURCE_ORDER),
            "manual_exclude_blocks_new_entries_only": True,
            "max_symbols": max_symbols,
            "stale_after_seconds": stale_after_seconds,
        },
        "source_keys": keys,
        "notes": notes,
    }


def parse_effective_universe_codes(
    raw: Any,
    *,
    max_symbols: int,
    field: str = "codes",
    now: datetime | None = None,
) -> list[str]:
    """Parse active or market-data codes from an effective universe payload."""

    payload = decode_payload(raw)
    if not payload:
        return []
    if effective_snapshot_has_expired_overrides(payload, now=now):
        return []
    values = payload.get(field)
    if not isinstance(values, list):
        return []
    return ordered_unique(values)[:max_symbols]
