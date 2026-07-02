"""Universe and data coverage endpoints for Quant Ops Workbench."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from services.dashboard.domain.assets import normalize_asset_class

router = APIRouter(prefix="/api/coverage", tags=["coverage"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STOCK_EXPERIMENT_OUTPUT_DIR = os.environ.get(
    "STOCK_EXPERIMENT_OUTPUT_DIR", "reports/stock_experiment"
)
_UNIVERSE_KEY = os.environ.get("UNIVERSE_LATEST_KEY", "system:universe:latest")
_TRADE_TARGETS_KEY = os.environ.get(
    "TRADE_TARGETS_LATEST_KEY", "system:trade_targets:latest"
)
_THEME_TARGETS_KEY = os.environ.get(
    "THEME_TARGETS_LATEST_KEY", "system:theme_targets:latest"
)
_DAILY_INDICATORS_KEY = os.environ.get(
    "DAILY_INDICATORS_LATEST_KEY", "system:daily_indicators:latest"
)
_ENABLE_KRX_NAME_FALLBACK = os.environ.get(
    "DASHBOARD_KRX_NAME_FALLBACK", "true"
).strip().lower() not in {"0", "false", "no", "off"}

_KRX_SYMBOL_NAME_CACHE: dict[str, str] = {}
_KRX_SYMBOL_NAME_CACHE_DATE = ""


class CoverageSource(BaseModel):
    """Coverage row for a Redis/config/report source."""

    name: str
    key: str | None = None
    available: bool
    count: int | None = None
    updated_at: str | None = None
    symbols: list[str] = []
    names: dict[str, str] = {}
    missing_symbols: list[str] = []
    metadata: dict[str, Any] = {}


class ExperimentCoverageRow(BaseModel):
    """Latest stock experiment symbol coverage."""

    symbol: str
    name: str | None = None
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


def _clean_name(value: Any) -> str:
    if value is None:
        return ""
    name = str(value).strip()
    if not name or name.lower() in {"none", "null"}:
        return ""
    return name


def _extract_names(payload: dict[str, Any] | None) -> dict[str, str]:
    """Return a normalized code -> display name map from known payload shapes."""
    if not payload:
        return {}

    names: dict[str, str] = {}

    raw_names = payload.get("names")
    if isinstance(raw_names, dict):
        for code, name in raw_names.items():
            clean = _clean_name(name)
            if code and clean:
                names[str(code)] = clean
    elif isinstance(raw_names, list):
        codes = payload.get("codes") or payload.get("symbols") or []
        if isinstance(codes, list):
            for code, name in zip(codes, raw_names, strict=False):
                clean = _clean_name(name)
                if code and clean:
                    names[str(code)] = clean

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for code, item in metadata.items():
            if not isinstance(item, dict):
                continue
            clean = _clean_name(
                item.get("name")
                or item.get("stock_name")
                or item.get("symbol_name")
                or item.get("prdt_name")
            )
            if code and clean:
                names.setdefault(str(code), clean)

    return names


def _source_from_redis(redis: Any, name: str, key: str) -> CoverageSource:
    raw = None
    if redis is not None:
        try:
            raw = redis.get(key)
        except Exception:  # noqa: BLE001
            raw = None
    payload = _decode_json(raw)
    symbols = _extract_symbols(payload)
    names = _extract_names(payload)
    updated_at = None
    metadata: dict[str, Any] = {}
    if payload:
        updated_at_raw = payload.get("generated_at") or payload.get("updated_at")
        updated_at = str(updated_at_raw) if updated_at_raw else None
        metadata = {
            "snapshot_id": payload.get("snapshot_id"),
            "source_keys": sorted(payload.keys()),
        }
        for key_name in ("themes", "state_counts"):
            if key_name in payload:
                metadata[key_name] = payload[key_name]
    return CoverageSource(
        name=name,
        key=key,
        available=payload is not None,
        count=len(symbols) if payload is not None else None,
        updated_at=updated_at,
        symbols=symbols[:200],
        names={symbol: names[symbol] for symbol in symbols[:200] if symbol in names},
        metadata=metadata,
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


def _experiment_rows(
    report: dict[str, Any] | None,
    names: dict[str, str] | None = None,
) -> list[ExperimentCoverageRow]:
    coverage = report.get("data_coverage") if report else None
    if not isinstance(coverage, dict):
        return []
    rows: list[ExperimentCoverageRow] = []
    symbol_names = names or {}
    for symbol, payload in sorted(coverage.items()):
        item = payload if isinstance(payload, dict) else {}
        symbol_text = str(symbol)
        rows.append(
            ExperimentCoverageRow(
                symbol=symbol_text,
                name=_clean_name(item.get("name")) or symbol_names.get(symbol_text),
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


def _merge_source_names(sources: list[CoverageSource]) -> dict[str, str]:
    names: dict[str, str] = {}
    for source in sources:
        for symbol, name in source.names.items():
            if name:
                names.setdefault(symbol, name)
    return names


def _load_krx_symbol_names() -> dict[str, str]:
    """Best-effort stock code -> name map from KRX Open API, cached by trade date."""
    global _KRX_SYMBOL_NAME_CACHE_DATE

    if not _ENABLE_KRX_NAME_FALLBACK or not os.environ.get("KRX_API_KEY", "").strip():
        return {}

    try:
        from shared.llm.config import LLMConfig
        from shared.llm.krx_api_client import KRXOpenAPIClient

        client = KRXOpenAPIClient(LLMConfig.from_env())
        target_date = client._get_last_trading_date()
        if _KRX_SYMBOL_NAME_CACHE and target_date == _KRX_SYMBOL_NAME_CACHE_DATE:
            return _KRX_SYMBOL_NAME_CACHE

        names: dict[str, str] = {}
        for market in ("KOSPI", "KOSDAQ"):
            for item in client.get_stock_daily(market=market, base_date=target_date):
                code = str(item.get("ISU_CD", "")).strip()
                name = _clean_name(item.get("ISU_NM"))
                if code and name:
                    names[code] = name
        if names:
            _KRX_SYMBOL_NAME_CACHE.clear()
            _KRX_SYMBOL_NAME_CACHE.update(names)
            _KRX_SYMBOL_NAME_CACHE_DATE = target_date
        return _KRX_SYMBOL_NAME_CACHE
    except Exception:  # noqa: BLE001 - coverage diagnostics must stay available
        return _KRX_SYMBOL_NAME_CACHE


def _coverage_symbols(report: dict[str, Any] | None) -> set[str]:
    coverage = report.get("data_coverage") if report else None
    if not isinstance(coverage, dict):
        return set()
    return {str(symbol) for symbol in coverage}


def _symbols_without_names(
    sources: list[CoverageSource],
    report: dict[str, Any] | None,
) -> set[str]:
    missing: set[str] = set()
    for source in sources:
        source_symbols = [*source.symbols, *source.missing_symbols]
        for symbol in source_symbols:
            if symbol and not source.names.get(symbol):
                missing.add(symbol)
    for symbol in _coverage_symbols(report):
        if symbol:
            missing.add(symbol)
    return missing


def _apply_name_fallback(
    sources: list[CoverageSource],
    report: dict[str, Any] | None,
) -> tuple[list[CoverageSource], dict[str, str]]:
    names = _merge_source_names(sources)
    missing = {
        symbol
        for symbol in _symbols_without_names(sources, report)
        if not names.get(symbol)
    }
    if missing:
        krx_names = _load_krx_symbol_names()
        for symbol in missing:
            name = krx_names.get(symbol)
            if name:
                names.setdefault(symbol, name)

    enriched_sources = []
    for source in sources:
        source_names = dict(source.names)
        for symbol in source.symbols:
            if symbol in names:
                source_names.setdefault(symbol, names[symbol])
        for symbol in source.missing_symbols:
            if symbol in names:
                source_names.setdefault(symbol, names[symbol])
        enriched_sources.append(source.model_copy(update={"names": source_names}))
    return enriched_sources, names


@router.get("", response_model=CoverageResponse)
async def get_coverage(
    asset_class: str = Query(default="stock"),
) -> CoverageResponse:
    """Return universe, indicator, and experiment coverage for triage."""
    asset = normalize_asset_class(asset_class)
    redis = _get_redis_client()
    missing: list[str] = []
    notes: list[str] = []
    sources: list[CoverageSource] = []

    if asset in {"stock", "all"}:
        universe = _source_from_redis(redis, "screener_universe", _UNIVERSE_KEY)
        trade_targets = _source_from_redis(redis, "trade_targets", _TRADE_TARGETS_KEY)
        theme_targets = _source_from_redis(redis, "theme_targets", _THEME_TARGETS_KEY)
        daily = _source_from_redis(redis, "daily_indicators", _DAILY_INDICATORS_KEY)
        daily_symbols = set(daily.symbols) if daily.available else None
        sources.extend(
            [
                _with_daily_missing(universe, daily_symbols),
                _with_daily_missing(trade_targets, daily_symbols),
                _with_daily_missing(theme_targets, daily_symbols),
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
    sources, symbol_names = _apply_name_fallback(sources, report)
    experiment = _experiment_rows(report, symbol_names)
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
