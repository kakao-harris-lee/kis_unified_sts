"""Universe and data coverage endpoints for Quant Ops Workbench."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from services.dashboard.routes.trading import _normalize_asset_class

router = APIRouter(prefix="/api/coverage", tags=["coverage"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STOCK_EXPERIMENT_OUTPUT_DIR = os.environ.get(
    "STOCK_EXPERIMENT_OUTPUT_DIR", "reports/stock_experiment"
)
_UNIVERSE_KEY = os.environ.get("UNIVERSE_LATEST_KEY", "system:universe:latest")
_TRADE_TARGETS_KEY = os.environ.get(
    "TRADE_TARGETS_LATEST_KEY", "system:trade_targets:latest"
)
_DAILY_INDICATORS_KEY = os.environ.get(
    "DAILY_INDICATORS_LATEST_KEY", "system:daily_indicators:latest"
)


class CoverageSource(BaseModel):
    """Coverage row for a Redis/config/report source."""

    name: str
    key: str | None = None
    available: bool
    count: int | None = None
    updated_at: str | None = None
    symbols: list[str] = []
    missing_symbols: list[str] = []
    metadata: dict[str, Any] = {}


class ExperimentCoverageRow(BaseModel):
    """Latest stock experiment symbol coverage."""

    symbol: str
    loaded: bool
    rows: int | None = None
    start: str | None = None
    end: str | None = None
    error: str | None = None


class CoverageResponse(BaseModel):
    """Universe/data coverage response."""

    asset_class: str
    generated_at: datetime
    sources: list[CoverageSource]
    experiment_coverage: list[ExperimentCoverageRow]
    missing_evidence: list[str]
    notes: list[str]


def _get_redis_client():
    try:
        from shared.streaming.client import RedisClient

        return RedisClient.get_client()
    except Exception:  # noqa: BLE001 - dashboard must stay resilient
        return None


def _decode_json(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode(errors="ignore")
    if isinstance(raw, dict):
        return raw
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _extract_symbols(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    seen: dict[str, None] = {}

    def add(value: Any) -> None:
        code = str(value).strip()
        if code:
            seen.setdefault(code, None)

    for key in ("codes", "symbols", "final_codes"):
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


def _source_from_redis(redis: Any, name: str, key: str) -> CoverageSource:
    raw = None
    if redis is not None:
        try:
            raw = redis.get(key)
        except Exception:  # noqa: BLE001
            raw = None
    payload = _decode_json(raw)
    symbols = _extract_symbols(payload)
    updated_at = None
    if payload:
        updated_at_raw = payload.get("generated_at") or payload.get("updated_at")
        updated_at = str(updated_at_raw) if updated_at_raw else None
    return CoverageSource(
        name=name,
        key=key,
        available=payload is not None,
        count=len(symbols) if payload is not None else None,
        updated_at=updated_at,
        symbols=symbols[:200],
        metadata={
            "snapshot_id": payload.get("snapshot_id"),
            "source_keys": sorted(payload.keys()),
        }
        if payload
        else {},
    )


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else _REPO_ROOT / p


def _latest_experiment_report() -> dict[str, Any] | None:
    out = _resolve(_STOCK_EXPERIMENT_OUTPUT_DIR)
    if not out.exists():
        return None
    paths = sorted(out.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not paths:
        return None
    try:
        data = json.loads(paths[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _experiment_rows(report: dict[str, Any] | None) -> list[ExperimentCoverageRow]:
    coverage = report.get("data_coverage") if report else None
    if not isinstance(coverage, dict):
        return []
    rows: list[ExperimentCoverageRow] = []
    for symbol, payload in sorted(coverage.items()):
        item = payload if isinstance(payload, dict) else {}
        rows.append(
            ExperimentCoverageRow(
                symbol=str(symbol),
                loaded=bool(item.get("loaded", False)),
                rows=int(item["rows"]) if item.get("rows") is not None else None,
                start=item.get("start"),
                end=item.get("end"),
                error=item.get("error"),
            )
        )
    return rows


def _with_daily_missing(
    source: CoverageSource, daily_symbols: set[str] | None
) -> CoverageSource:
    if daily_symbols is None:
        return source
    missing = [symbol for symbol in source.symbols if symbol not in daily_symbols]
    return source.model_copy(update={"missing_symbols": missing[:50]})


@router.get("", response_model=CoverageResponse)
async def get_coverage(
    asset_class: str = Query(default="stock"),
) -> CoverageResponse:
    """Return universe, indicator, and experiment coverage for triage."""
    asset = _normalize_asset_class(asset_class)
    redis = _get_redis_client()
    missing: list[str] = []
    notes: list[str] = []
    sources: list[CoverageSource] = []

    if asset in {"stock", "all"}:
        universe = _source_from_redis(redis, "screener_universe", _UNIVERSE_KEY)
        trade_targets = _source_from_redis(
            redis, "trade_targets", _TRADE_TARGETS_KEY
        )
        daily = _source_from_redis(
            redis, "daily_indicators", _DAILY_INDICATORS_KEY
        )
        daily_symbols = set(daily.symbols) if daily.available else None
        sources.extend(
            [
                _with_daily_missing(universe, daily_symbols),
                _with_daily_missing(trade_targets, daily_symbols),
                daily,
            ]
        )
        for source in sources:
            if not source.available:
                missing.append(source.name)
        notes.append(
            "KIS minute data is limited; minute-strategy coverage can be narrower than daily coverage."
        )

    if asset in {"futures", "all"}:
        sources.append(
            CoverageSource(
                name="futures_data_coverage",
                available=False,
                metadata={"reason": "no unified futures coverage key is published yet"},
            )
        )
        missing.append("futures_data_coverage")

    report = _latest_experiment_report() if asset in {"stock", "all"} else None
    experiment = _experiment_rows(report)
    if asset in {"stock", "all"} and not experiment:
        missing.append("latest_experiment_coverage")

    missing = sorted(set(missing))
    return CoverageResponse(
        asset_class=asset,
        generated_at=datetime.now(UTC),
        sources=sources,
        experiment_coverage=experiment,
        missing_evidence=missing,
        notes=notes,
    )
