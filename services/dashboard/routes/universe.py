"""Managed stock trading-universe endpoints."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from shared.stock_universe import (
    DEFAULT_AUDIT_KEY,
    DEFAULT_AUDIT_TTL_SECONDS,
    DEFAULT_EFFECTIVE_UNIVERSE_KEY,
    DEFAULT_OVERRIDES_KEY,
    DEFAULT_OVERRIDES_TTL_SECONDS,
    DEFAULT_SOURCE_STALE_SECONDS,
    DEFAULT_UNIVERSE_TTL_SECONDS,
    build_effective_universe_snapshot,
    decode_payload,
    merge_names,
)

router = APIRouter(prefix="/api/trading/universe", tags=["trading"])


class UniverseOverrideRequest(BaseModel):
    """Manual universe override request."""

    action: Literal["include", "exclude", "remove"]
    symbol: str
    name: str | None = None
    reason: str | None = None
    expires_at: datetime | None = None
    ttl_seconds: int | None = Field(default=None, ge=60, le=604_800)
    operator: str | None = None


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _keys() -> dict[str, str]:
    return {
        "effective": os.environ.get(
            "STOCK_EFFECTIVE_UNIVERSE_KEY", DEFAULT_EFFECTIVE_UNIVERSE_KEY
        ),
        "overrides": os.environ.get(
            "STOCK_UNIVERSE_OVERRIDES_KEY", DEFAULT_OVERRIDES_KEY
        ),
        "audit": os.environ.get("STOCK_UNIVERSE_AUDIT_KEY", DEFAULT_AUDIT_KEY),
        "screener_universe": os.environ.get(
            "UNIVERSE_LATEST_KEY", "system:universe:latest"
        ),
        "trade_targets": os.environ.get(
            "TRADE_TARGETS_LATEST_KEY", "system:trade_targets:latest"
        ),
        "daily_watchlist": os.environ.get(
            "STOCK_WATCHLIST_KEY", "system:daily_watchlist:latest"
        ),
        "daily_indicators": os.environ.get(
            "DAILY_INDICATORS_LATEST_KEY", "system:daily_indicators:latest"
        ),
        "theme_targets": os.environ.get(
            "THEME_TARGETS_LATEST_KEY", "system:theme_targets:latest"
        ),
    }


def _ttl() -> dict[str, int]:
    return {
        "effective": _env_int(
            "STOCK_UNIVERSE_TTL_SECONDS", DEFAULT_UNIVERSE_TTL_SECONDS
        ),
        "overrides": _env_int(
            "STOCK_UNIVERSE_OVERRIDES_TTL_SECONDS", DEFAULT_OVERRIDES_TTL_SECONDS
        ),
        "audit": _env_int(
            "STOCK_UNIVERSE_AUDIT_TTL_SECONDS", DEFAULT_AUDIT_TTL_SECONDS
        ),
        "source_stale": _env_int(
            "STOCK_UNIVERSE_SOURCE_STALE_SECONDS", DEFAULT_SOURCE_STALE_SECONDS
        ),
    }


def _get_redis_client():
    try:
        from shared.streaming.client import RedisClient

        return RedisClient.get_client()
    except Exception:  # noqa: BLE001 - dashboard must stay resilient
        return None


def _redis_get(redis: Any, key: str) -> Any:
    if redis is None:
        return None
    try:
        return redis.get(key)
    except Exception:  # noqa: BLE001
        return None


def _json_dumps(payload: dict[str, Any] | list[Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _redis_set_json(
    redis: Any, key: str, payload: dict[str, Any], ttl_seconds: int | None
) -> None:
    if redis is None:
        return
    encoded = _json_dumps(payload)
    if ttl_seconds is None:
        redis.set(key, encoded)
        return
    try:
        redis.set(key, encoded, ex=ttl_seconds)
    except TypeError:
        redis.set(key, encoded)
        redis.expire(key, ttl_seconds)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _effective_snapshot_ttl(snapshot: dict[str, Any], default_ttl: int) -> int:
    """Keep effective snapshots from outliving the earliest active override."""

    now = datetime.now(UTC)
    expiries: list[int] = []
    overrides = snapshot.get("overrides")
    if isinstance(overrides, dict):
        for bucket in ("manual_include", "manual_exclude"):
            raw_bucket = overrides.get(bucket)
            if not isinstance(raw_bucket, dict):
                continue
            for item in raw_bucket.values():
                if not isinstance(item, dict):
                    continue
                expires_at = _parse_dt(item.get("expires_at"))
                if expires_at is not None:
                    expiries.append(max(1, int((expires_at - now).total_seconds())))
    return min(default_ttl, min(expiries)) if expiries else default_ttl


def _overrides_key_ttl(overrides: dict[str, Any], default_ttl: int) -> int | None:
    """TTL for the overrides key, or None to leave it without expiry.

    If any active override is permanent (no ``expires_at``), the key must not
    expire — a Redis-level TTL would silently drop permanent operator picks
    once it lapses. Otherwise keep at least the default and extend to the
    furthest explicit expiry.
    """
    now = datetime.now(UTC)
    max_expiry_ttl = 0
    has_permanent = False
    for bucket in ("manual_include", "manual_exclude"):
        raw_bucket = overrides.get(bucket)
        if not isinstance(raw_bucket, dict):
            continue
        for item in raw_bucket.values():
            if not isinstance(item, dict):
                continue
            expires_at = _parse_dt(item.get("expires_at"))
            if expires_at is None:
                has_permanent = True
            else:
                max_expiry_ttl = max(
                    max_expiry_ttl,
                    int((expires_at - now).total_seconds()),
                )
    if has_permanent:
        return None
    return max(default_ttl, max_expiry_ttl)


def _read_open_positions() -> tuple[list[str], dict[str, str]]:
    try:
        from services.dashboard.routes.trading import _read_positions

        positions = _read_positions("stock")
    except Exception:  # noqa: BLE001
        positions = []
    codes: list[str] = []
    names: dict[str, str] = {}
    for position in positions:
        code = str(getattr(position, "code", "") or "").strip()
        if not code:
            continue
        codes.append(code)
        name = str(getattr(position, "name", "") or "").strip()
        if name:
            names.setdefault(code, name)
    return list(dict.fromkeys(codes)), names


def _build_snapshot(redis: Any) -> dict[str, Any]:
    keys = _keys()
    ttl = _ttl()
    open_codes, open_names = _read_open_positions()
    snapshot = build_effective_universe_snapshot(
        screener_raw=_redis_get(redis, keys["screener_universe"]),
        trade_targets_raw=_redis_get(redis, keys["trade_targets"]),
        daily_watchlist_raw=_redis_get(redis, keys["daily_watchlist"]),
        daily_indicators_raw=_redis_get(redis, keys["daily_indicators"]),
        theme_targets_raw=_redis_get(redis, keys["theme_targets"]),
        overrides_raw=_redis_get(redis, keys["overrides"]),
        existing_symbols=open_codes,
        existing_names=open_names,
        max_symbols=_env_int("STOCK_MAX_SYMBOLS", 40),
        stale_after_seconds=ttl["source_stale"],
        source_keys={
            "screener_universe": keys["screener_universe"],
            "trade_targets": keys["trade_targets"],
            "daily_watchlist": keys["daily_watchlist"],
            "daily_indicators": keys["daily_indicators"],
            "theme_targets": keys["theme_targets"],
        },
    )
    snapshot["key"] = keys["effective"]
    snapshot["override_key"] = keys["overrides"]
    snapshot["audit_key"] = keys["audit"]
    snapshot["ttl_seconds"] = ttl["effective"]
    if redis is None:
        snapshot["notes"] = [*snapshot.get("notes", []), "redis_unavailable"]
    return snapshot


def _publish_snapshot(redis: Any, snapshot: dict[str, Any]) -> None:
    keys = _keys()
    ttl = _ttl()
    _redis_set_json(
        redis,
        keys["effective"],
        snapshot,
        _effective_snapshot_ttl(snapshot, ttl["effective"]),
    )


def _load_overrides(redis: Any) -> dict[str, Any]:
    payload = decode_payload(_redis_get(redis, _keys()["overrides"]))
    if not payload:
        return {
            "manual_include": {},
            "manual_exclude": {},
            "updated_at": None,
        }
    payload.setdefault("manual_include", {})
    payload.setdefault("manual_exclude", {})
    return payload


def _append_audit(redis: Any, event: dict[str, Any]) -> None:
    if redis is None:
        return
    keys = _keys()
    ttl = _ttl()
    try:
        redis.lpush(keys["audit"], _json_dumps(event))
        redis.ltrim(keys["audit"], 0, 199)
        redis.expire(keys["audit"], ttl["audit"])
    except Exception:  # noqa: BLE001
        return


def _override_expiry(request: UniverseOverrideRequest, now: datetime) -> str | None:
    """Return an ISO expiry, or None for a permanent override.

    Permanent (None) applies when the operator supplies neither an explicit
    ``expires_at`` nor a ``ttl_seconds``. Operator "My List" picks are meant to
    persist until explicitly removed.
    """
    if request.expires_at is not None:
        expires = request.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return expires.astimezone(UTC).isoformat()
    if request.ttl_seconds is not None:
        return (now + timedelta(seconds=request.ttl_seconds)).isoformat()
    return None


def _clean_symbol(symbol: str) -> str:
    return str(symbol or "").strip()


_CODE_RE = re.compile(r"^[0-9]{6}$")


def _build_name_map(redis: Any) -> dict[str, str]:
    """Merge code->name across every raw universe source + open positions.

    Delegates to ``shared.stock_universe.merge_names`` — the single source of
    the merge-order truth also used by ``build_effective_universe_snapshot``
    — so the name confirmed here can never drift from what the universe table
    displays. Payloads are passed positionally in the same order the snapshot
    uses (trade_targets, daily_watchlist, screener_universe, theme_targets,
    daily_indicators: first source wins), then open positions, then
    override-carried names (lowest priority, gap-fill only).
    """
    keys = _keys()
    payloads = [
        decode_payload(_redis_get(redis, keys[source_key]))
        for source_key in (
            "trade_targets",
            "daily_watchlist",
            "screener_universe",
            "theme_targets",
            "daily_indicators",
        )
    ]
    _open_codes, open_names = _read_open_positions()
    overrides = _load_overrides(redis)
    return merge_names(*payloads, existing_names=open_names, overrides=overrides)


@router.get("/resolve")
async def resolve_universe_symbol(
    code: str = Query(...),
) -> dict[str, Any]:
    """Resolve a 6-digit code to a display name the system already knows.

    Returns ``known=False`` with ``name=None`` for a valid code the system has
    not seen yet (still addable — the operator confirms by code).
    """
    cleaned = _clean_symbol(code)
    if not _CODE_RE.match(cleaned):
        raise HTTPException(status_code=400, detail="invalid_code")
    name = _build_name_map(_get_redis_client()).get(cleaned)
    return {"code": cleaned, "name": name, "known": name is not None}


@router.get("")
async def get_trading_universe(
    publish: bool = Query(default=False),
) -> dict[str, Any]:
    """Return the managed effective stock trading universe."""

    redis = _get_redis_client()
    snapshot = _build_snapshot(redis)
    if publish:
        _publish_snapshot(redis, snapshot)
    return snapshot


@router.get("/sources")
async def get_trading_universe_sources() -> dict[str, Any]:
    """Return raw source freshness and counts for the trading universe."""

    snapshot = _build_snapshot(_get_redis_client())
    return {
        "asset_class": "stock",
        "generated_at": snapshot["generated_at"],
        "sources": snapshot["sources"],
        "source_keys": snapshot["source_keys"],
        "notes": snapshot["notes"],
    }


@router.get("/audit")
async def get_trading_universe_audit(
    limit: int = Query(default=50, ge=1, le=200)
) -> dict:
    """Return recent manual trading-universe override events."""

    redis = _get_redis_client()
    key = _keys()["audit"]
    raw_events: list[Any] = []
    if redis is not None:
        try:
            raw_events = redis.lrange(key, 0, limit - 1)
        except Exception:  # noqa: BLE001
            raw_events = []
    events: list[dict[str, Any]] = []
    for raw in raw_events:
        payload = decode_payload(raw)
        if payload:
            events.append(payload)
    return {
        "key": key,
        "generated_at": datetime.now(UTC).isoformat(),
        "events": events,
    }


@router.post("/recompute")
async def recompute_trading_universe() -> dict[str, Any]:
    """Recompute and publish the effective stock trading universe."""

    redis = _get_redis_client()
    if redis is None:
        raise HTTPException(status_code=503, detail="redis_unavailable")
    snapshot = _build_snapshot(redis)
    _publish_snapshot(redis, snapshot)
    return snapshot


@router.post("/overrides")
async def update_trading_universe_override(
    request: UniverseOverrideRequest,
) -> dict[str, Any]:
    """Add or remove a manual include/exclude override and publish the universe."""

    redis = _get_redis_client()
    if redis is None:
        raise HTTPException(status_code=503, detail="redis_unavailable")

    symbol = _clean_symbol(request.symbol)
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol_required")

    now = datetime.now(UTC)
    overrides = _load_overrides(redis)
    include = dict(overrides.get("manual_include") or {})
    exclude = dict(overrides.get("manual_exclude") or {})

    event = {
        "action": request.action,
        "symbol": symbol,
        "name": request.name,
        "reason": request.reason,
        "operator": request.operator,
        "created_at": now.isoformat(),
    }

    if request.action == "include":
        include[symbol] = {
            "reason": str(request.reason or "").strip(),
            "created_at": now.isoformat(),
            "expires_at": _override_expiry(request, now),
            "operator": request.operator,
            "name": request.name,
        }
        exclude.pop(symbol, None)
        event["expires_at"] = include[symbol]["expires_at"]
    elif request.action == "exclude":
        exclude[symbol] = {
            "reason": str(request.reason or "").strip(),
            "created_at": now.isoformat(),
            "expires_at": _override_expiry(request, now),
            "operator": request.operator,
            "name": request.name,
        }
        include.pop(symbol, None)
        event["expires_at"] = exclude[symbol]["expires_at"]
    else:
        include.pop(symbol, None)
        exclude.pop(symbol, None)

    next_overrides = {
        "manual_include": include,
        "manual_exclude": exclude,
        "updated_at": now.isoformat(),
    }
    _redis_set_json(
        redis,
        _keys()["overrides"],
        next_overrides,
        _overrides_key_ttl(next_overrides, _ttl()["overrides"]),
    )
    _append_audit(redis, event)
    snapshot = _build_snapshot(redis)
    _publish_snapshot(redis, snapshot)
    return snapshot
