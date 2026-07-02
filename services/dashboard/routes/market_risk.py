"""Market Risk Score read-only API (unified investment roadmap Phase 1c).

Exposes the Market Risk Score engine's Redis publication
(``market:risk:latest`` — fixed Phase 1a contract) plus market-structure
snapshot freshness for the ``/market`` dashboard page. Strictly read-only:
no control or execution endpoints belong here (shadow phase — 미집행).

Endpoints degrade gracefully: when the engine has not published yet (key
absent) the latest endpoint answers ``{"status": "unavailable"}`` and the
history endpoint returns empty series when the Parquet dataset is missing.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/market-risk", tags=["market-risk"])

KST = ZoneInfo("Asia/Seoul")

# Phase 1a publication contract (fixed): hash key + field names. The key is
# env-overridable for operator setups; the default is the agreed contract.
_RISK_LATEST_KEY = os.environ.get("MARKET_RISK_LATEST_KEY", "market:risk:latest")
# Latest is refreshed premarket 08:00 / intraday 30min / close 18:40 KST. The
# widest legitimate gap is close → next premarket (~13.3h), so reuse the
# market-structure stale threshold (14h) unless overridden.
_RISK_STALE_SECONDS = int(os.environ.get("MARKET_RISK_STALE_SECONDS", "50400"))
_NIGHT_CLOSE_STALE_SECONDS = int(
    os.environ.get("MARKET_RISK_NIGHT_STALE_SECONDS", "86400")
)

# Component names in the fixed Phase 1a contract order.
_COMPONENT_NAMES = (
    "foreign_fut",
    "basis",
    "usdkrw",
    "program",
    "oi",
    "overseas",
    "vol",
    "trend",
)

# History columns read off the market-structure close rows. Values are
# (output_field, candidate columns in priority order) — the store schema is
# union-by-name loose, so absent columns simply yield null series.
_HISTORY_NUMERIC_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("risk_score", ("risk_score",)),
    ("risk_score_ema3", ("risk_score_ema3",)),
    # Engine score coverage (risk_coverage_ratio) first; the bare
    # coverage_ratio column is the collector's data-collection coverage and
    # only serves as a Phase 0 fallback.
    ("coverage_ratio", ("risk_coverage_ratio", "coverage_ratio")),
    ("kospi_close", ("kospi_close", "k200_close")),
    ("kospi_change_pct", ("kospi_change_pct", "k200_change_pct")),
    ("kospi_ret_20d", ("kospi_ret_20d", "k200_ret_20d")),
    ("fut_close", ("fut_close",)),
    ("fut_foreign_net_qty", ("fut_foreign_net_qty",)),
    ("fut_foreign_net_qty_cum20", ("fut_foreign_net_qty_cum20",)),
    ("basis", ("basis",)),
    ("basis_dev", ("basis_dev",)),
    ("basis_dev_ma5", ("basis_dev_ma5",)),
    ("fut_oi", ("fut_oi", "fut_oi_qty")),
    ("fut_oi_change", ("fut_oi_change",)),
    ("prog_net_val", ("prog_net_val",)),
    ("usdkrw", ("usdkrw",)),
    ("usdkrw_ret_5d", ("usdkrw_ret_5d",)),
    ("es_ovn_ret", ("es_ovn_ret", "es_futures_change_pct")),
    ("nq_ovn_ret", ("nq_ovn_ret", "nq_futures_change_pct")),
    ("sox_ret", ("sox_ret", "sox_change_pct")),
) + tuple((f"sub_{name}", (f"sub_{name}",)) for name in _COMPONENT_NAMES)

_HISTORY_TEXT_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("risk_band", ("risk_band",)),
    ("unified_regime", ("unified_regime",)),
    ("oi_price_signal", ("oi_price_signal",)),
    ("ma_alignment", ("ma_alignment", "k200_ma_alignment")),
)


# ---------------------------------------------------------------------------
# Infra accessors (monkeypatched in tests)
# ---------------------------------------------------------------------------


def _get_redis_client():
    """Redis DB 1 client via the shared singleton; None on infra failure."""
    try:
        from shared.streaming.client import RedisClient

        return RedisClient.get_client()
    except Exception:  # noqa: BLE001 - dashboard must stay resilient
        return None


def _get_store():
    """Market-structure Parquet store; None when config/deps are unavailable."""
    try:
        from shared.storage.market_structure_store import (
            create_market_structure_store,
        )

        return create_market_structure_store()
    except Exception:  # noqa: BLE001 - history degrades to empty series
        return None


def _load_gate_config():
    """Market Risk Gate config (Phase 2E) — read-only display source.

    ``load_or_default`` already degrades to code defaults when the YAML file
    is absent; a malformed YAML additionally degrades to the same defaults
    here. None only when even the defaults cannot be built.
    """
    try:
        from shared.risk.market_risk_gate import MarketRiskGateConfig
    except Exception:  # noqa: BLE001 - dashboard must stay resilient
        return None
    try:
        return MarketRiskGateConfig.load_or_default()
    except Exception:  # noqa: BLE001 - malformed YAML → shipped defaults
        try:
            return MarketRiskGateConfig()
        except Exception:  # noqa: BLE001
            return None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _decode(raw: Any) -> Any:
    if isinstance(raw, bytes):
        return raw.decode(errors="ignore")
    return raw


def _decode_hash(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    decoded: dict[str, str] = {}
    for key, value in raw.items():
        text_key = str(_decode(key))
        decoded[text_key] = str(_decode(value))
    return decoded


def _redis_hgetall(redis: Any, key: str) -> dict[str, str]:
    if redis is None:
        return {}
    try:
        return _decode_hash(redis.hgetall(key) or {})
    except Exception:  # noqa: BLE001
        return {}


def _coerce_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        value = float(str(raw))
    except (TypeError, ValueError):
        return None
    if value != value:  # NaN
        return None
    return value


def _coerce_bool(raw: Any) -> bool | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes")


def _coerce_text(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(_decode(raw)).strip()
    return text or None


def _parse_json_list(raw: Any) -> list[str]:
    text = _coerce_text(raw)
    if not text:
        return []
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


def _parse_kst_naive(raw: Any) -> datetime | None:
    """Parse a KST-naive (or offset-aware) ISO timestamp to aware KST."""
    text = _coerce_text(raw)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def _age_seconds(asof: datetime | None) -> int | None:
    if asof is None:
        return None
    return max(0, int((datetime.now(UTC) - asof.astimezone(UTC)).total_seconds()))


def _parse_components(raw: Any) -> dict[str, dict[str, Any]]:
    """Decode the ``components`` JSON field into a name-keyed mapping.

    Every contract component is always present in the output (missing ones as
    all-null entries) so the breakdown table can render a fixed 8-row layout.
    """
    text = _coerce_text(raw)
    payload: dict[str, Any] = {}
    if text:
        try:
            decoded = json.loads(text)
            if isinstance(decoded, dict):
                payload = decoded
        except (TypeError, ValueError):
            payload = {}

    components: dict[str, dict[str, Any]] = {}
    known = set(_COMPONENT_NAMES)
    ordered = list(_COMPONENT_NAMES) + [
        name for name in payload if str(name) not in known
    ]
    for name in ordered:
        entry = payload.get(name)
        entry = entry if isinstance(entry, dict) else {}
        components[str(name)] = {
            "sub": _coerce_float(entry.get("sub")),
            "weight": _coerce_float(entry.get("weight")),
            "contribution": _coerce_float(entry.get("contribution")),
            "raw": entry.get("raw"),
            "asof": _coerce_text(entry.get("asof")),
        }
    return components


# ---------------------------------------------------------------------------
# Latest snapshot assembly
# ---------------------------------------------------------------------------


def _night_close_summary(redis: Any, key: str) -> dict[str, Any]:
    payload = _redis_hgetall(redis, key)
    if not payload:
        return {"available": False, "status": "missing"}

    asof = _parse_kst_naive(payload.get("asof_ts"))
    age_s = _age_seconds(asof)
    if age_s is None:
        status = "unknown"
    else:
        status = "ok" if age_s <= _NIGHT_CLOSE_STALE_SECONDS else "stale"
    return {
        "available": True,
        "status": status,
        "close": _coerce_float(payload.get("close")),
        "mrkt_basis": _coerce_float(payload.get("mrkt_basis")),
        "dprt": _coerce_float(payload.get("dprt")),
        "open_interest": _coerce_float(payload.get("open_interest")),
        "acml_vol": _coerce_float(payload.get("acml_vol")),
        "product_code": _coerce_text(payload.get("product_code")),
        "asof": asof.isoformat() if asof else None,
        "age_s": age_s,
    }


def _market_structure_keys() -> tuple[str, str]:
    """(latest_key, night_close_key) from config/market_structure.yaml."""
    latest_key = "market:structure:latest"
    night_key = "market:structure:night_close"
    try:
        from shared.config.loader import ConfigLoader

        raw = ConfigLoader.load("market_structure.yaml")
        collector = raw.get("collector") if isinstance(raw, dict) else None
        collector = collector if isinstance(collector, dict) else {}
        redis_cfg = collector.get("redis")
        redis_cfg = redis_cfg if isinstance(redis_cfg, dict) else {}
        latest_key = str(redis_cfg.get("latest_key") or latest_key)
        night_key = str(redis_cfg.get("night_close_key") or night_key)
    except Exception:  # noqa: BLE001 - fall back to contract defaults
        pass
    return latest_key, night_key


def _previous_close_score(
    store: Any, before: date | None
) -> tuple[float | None, str | None]:
    """Most recent finalized close ``risk_score`` strictly before ``before``.

    Used for the 전일 대비 Δ readout. Returns (score, trade_date_iso).
    """
    if store is None:
        return None, None
    try:
        end = (before - timedelta(days=1)) if before is not None else None
        start = (end - timedelta(days=20)) if end is not None else None
        df = store.read_range(start=start, end=end, snapshot="close")
    except Exception:  # noqa: BLE001 - delta is best-effort
        return None, None
    if df is None or getattr(df, "empty", True):
        return None, None
    if "risk_score" not in df.columns:
        return None, None
    for _, row in df.iloc[::-1].iterrows():
        score = _coerce_float(row.get("risk_score"))
        if score is None:
            continue
        trade_date = row.get("trade_date")
        return score, trade_date.isoformat() if trade_date is not None else None
    return None, None


def _risk_summary(redis: Any, store: Any) -> dict[str, Any] | None:
    payload = _redis_hgetall(redis, _RISK_LATEST_KEY)
    if not payload:
        return None

    asof = _parse_kst_naive(payload.get("asof_ts"))
    age_s = _age_seconds(asof)
    score = _coerce_float(payload.get("score"))
    degraded = _coerce_bool(payload.get("degraded")) or False

    prev_score, prev_date = _previous_close_score(
        store, asof.date() if asof is not None else None
    )
    delta_1d = (
        round(score - prev_score, 4)
        if score is not None and prev_score is not None
        else None
    )

    return {
        "score": score,
        "score_ema3": _coerce_float(payload.get("score_ema3")),
        "band": _coerce_text(payload.get("band")),
        "regime": _coerce_text(payload.get("regime")),
        "degraded": degraded,
        "coverage_ratio": _coerce_float(payload.get("coverage_ratio")),
        "missing_components": _parse_json_list(payload.get("missing_components")),
        "kind": _coerce_text(payload.get("kind")),
        "asof": asof.isoformat() if asof else None,
        "age_s": age_s,
        "stale": age_s is not None and age_s > _RISK_STALE_SECONDS,
        "score_delta_1d": delta_1d,
        "prev_close_score": prev_score,
        "prev_close_date": prev_date,
        "components": _parse_components(payload.get("components")),
    }


def _gate_summary() -> dict[str, Any] | None:
    """Reaction matrix + mode from ``config/market_risk_gate.yaml``.

    Display-only (Phase 2E): the dashboard never mutates the gate mode. The
    matrix shape is ``{asset: {band: {allow_long, allow_short, size_factor,
    min_confidence}}}``; None when the gate module is unavailable so the UI
    falls back to the static roadmap matrix.
    """
    config = _load_gate_config()
    if config is None:
        return None
    return {
        "mode": config.mode,
        "staleness_max_age_seconds": config.staleness_max_age_seconds,
        "matrix": {
            asset: {
                band: {
                    "allow_long": rule.allow_long,
                    "allow_short": rule.allow_short,
                    "size_factor": rule.size_factor,
                    "min_confidence": rule.min_confidence,
                }
                for band, rule in bands.items()
            }
            for asset, bands in config.assets.items()
        },
    }


@router.get("")
async def get_market_risk() -> dict[str, Any]:
    """Latest Market Risk Score + market-structure snapshot freshness.

    ``status`` is ``unavailable`` when the engine has not published
    ``market:risk:latest`` yet, ``degraded`` when the engine flags reduced
    coverage, ``stale`` when publication age exceeds the threshold, and
    ``ok`` otherwise. ``gate`` carries the Market Risk Gate reaction matrix
    (config-sourced, display-only). Read-only — this API never mutates
    runtime state.
    """
    redis = _get_redis_client()
    store = _get_store()
    structure_latest_key, night_close_key = _market_structure_keys()

    # Reuse the health module's freshness summary (single source of truth).
    from services.dashboard.routes.health import _market_structure_ops

    structure = _market_structure_ops(redis)
    night_close = _night_close_summary(redis, night_close_key)
    risk = _risk_summary(redis, store)

    if risk is None:
        status = "unavailable"
    elif risk["degraded"]:
        status = "degraded"
    elif risk["stale"]:
        status = "stale"
    else:
        status = "ok"

    return {
        "status": status,
        "checked_at": datetime.now(UTC).isoformat(),
        "source": _RISK_LATEST_KEY,
        "risk": risk,
        "structure": {**structure, "source": structure_latest_key},
        "night_close": {**night_close, "source": night_close_key},
        "gate": _gate_summary(),
    }


# ---------------------------------------------------------------------------
# History (Parquet close rows)
# ---------------------------------------------------------------------------


def _first_present(row: Any, columns: tuple[str, ...], available: set[str]) -> Any:
    for column in columns:
        if column in available:
            value = row.get(column)
            if value is not None:
                return value
    return None


def _history_point(row: Any, available: set[str]) -> dict[str, Any]:
    trade_date = row.get("trade_date")
    point: dict[str, Any] = {
        "trade_date": trade_date.isoformat() if trade_date is not None else None,
    }
    for field, candidates in _HISTORY_NUMERIC_FIELDS:
        point[field] = _coerce_float(_first_present(row, candidates, available))
    for field, candidates in _HISTORY_TEXT_FIELDS:
        raw = _first_present(row, candidates, available)
        # pandas NaN for absent VARCHAR cells
        if isinstance(raw, float) and raw != raw:
            raw = None
        point[field] = _coerce_text(raw)
    degraded = row.get("degraded") if "degraded" in available else None
    if isinstance(degraded, float) and degraded != degraded:
        degraded = None
    point["degraded"] = _coerce_bool(degraded)
    return point


@router.get("/history")
async def get_market_risk_history(
    days: int = Query(default=90, ge=1, le=730),
) -> dict[str, Any]:
    """Daily close-row time series for the /market charts.

    Reads the market-structure Parquet dataset (finalized ``close`` snapshot
    rows only — premarket rows are excluded to keep the series one point per
    trading day). Absent dataset or columns degrade to empty/null series.
    """
    end = datetime.now(KST).date()
    start = end - timedelta(days=days)
    empty: dict[str, Any] = {
        "status": "empty",
        "days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": 0,
        "points": [],
    }

    store = _get_store()
    if store is None:
        return empty
    try:
        df = store.read_range(start=start, end=end, snapshot="close")
    except Exception:  # noqa: BLE001 - dataset may not exist yet
        return empty
    if df is None or getattr(df, "empty", True):
        return empty

    available = set(map(str, df.columns))
    points = [_history_point(row, available) for _, row in df.iterrows()]
    return {
        "status": "ok",
        "days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": len(points),
        "points": points,
    }
