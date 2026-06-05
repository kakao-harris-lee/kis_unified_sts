"""Metrics API endpoints for dashboard."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Response

from shared.storage.config import StorageConfig
from shared.storage.runtime_ledger import RuntimeLedgerError, SQLiteRuntimeLedger

router = APIRouter()
logger = logging.getLogger(__name__)


def _empty_venue_metrics() -> Dict[str, Any]:
    """Return empty venue metrics payload.

    The frontend expects these exact keys.
    """
    return {
        "krx_count": 0,
        "ats_count": 0,
        "krx_fill_rate": 0.0,
        "ats_fill_rate": 0.0,
        "avg_price_improvement_bps": 0.0,
        "ats_price_improvement_bps": 0.0,
    }


def _collect_venue_metrics_sync() -> Dict[str, Any]:
    """Collect venue metrics from RuntimeLedger fills.

    Only persisted execution venue counts are currently stored durably.
    Fill-rate and price-improvement values degrade gracefully until those
    inputs are persisted or queried from Prometheus.
    """
    metrics = _empty_venue_metrics()

    total_counts = {"KRX": 0, "ATS": 0}
    try:
        config = StorageConfig.load_or_default()
        db_path = Path(config.runtime_storage.sqlite.path)
        if not db_path.exists() or db_path.is_dir():
            return metrics
        ledger = SQLiteRuntimeLedger(config.runtime_storage.sqlite)
        try:
            for asset in ("stock", "futures"):
                for row in ledger.query_fills({"asset_class": asset, "limit": 10_000}):
                    venue = str(row.get("venue") or "KRX").upper()
                    if venue in total_counts:
                        total_counts[venue] += 1
        finally:
            ledger.close()
    except (RuntimeLedgerError, OSError) as e:
        logger.warning("Failed to query venue counts from runtime ledger: %s", e)
        return metrics

    metrics["krx_count"] = total_counts["KRX"]
    metrics["ats_count"] = total_counts["ATS"]

    # Persisted trade tables only contain executed fills, so completed-trade
    # fill rate is 1.0 when any venue-specific executions exist. We keep price
    # improvement at 0.0 until that metric is durably stored.
    metrics["krx_fill_rate"] = 1.0 if total_counts["KRX"] > 0 else 0.0
    metrics["ats_fill_rate"] = 1.0 if total_counts["ATS"] > 0 else 0.0
    return metrics


@router.get("/api/metrics/venue")
async def get_venue_metrics() -> Dict[str, Any]:
    """
    Get execution venue distribution and performance metrics.

    Returns venue statistics for monitoring ATS vs KRX routing effectiveness.

    Returns:
        Dict containing:
        - krx_count: Number of orders routed to KRX
        - ats_count: Number of orders routed to ATS
        - krx_fill_rate: Fill rate for KRX orders (0.0-1.0)
        - ats_fill_rate: Fill rate for ATS orders (0.0-1.0)
        - avg_price_improvement_bps: Average price improvement across all venues (basis points)
        - ats_price_improvement_bps: ATS-specific price improvement (basis points)
    """
    try:
        return _collect_venue_metrics_sync()
    except Exception as e:
        logger.error(f"Error fetching venue metrics: {e}")
        # Return zeros on error to prevent dashboard crash
        return _empty_venue_metrics()


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Expose Prometheus metrics in text exposition format.

    Consolidated from the retired ``services/api`` gateway: the dashboard is now
    the single FastAPI service, so it owns the Prometheus scrape target that
    Caddy routes ``/metrics`` to. Auth-exempt via ``PUBLIC_PATHS`` so scrapers
    do not need the dashboard API key. Degrades to an empty body (HTTP 200) when
    the metrics backend is unavailable, keeping the scrape non-fatal.
    """
    try:
        from services.monitoring import MetricsCollector

        content = MetricsCollector().export_prometheus()
        return Response(content=content, media_type="text/plain; version=0.0.4")
    except Exception as e:  # noqa: BLE001 - scrape endpoint must not 500
        logger.warning("Prometheus metrics export failed: %s", e)
        return Response(content="", media_type="text/plain; version=0.0.4")
