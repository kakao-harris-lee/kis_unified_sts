"""KIS analyst target-price row normalization and summary helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

from shared.utils.parsing import parse_float

_KST = ZoneInfo("Asia/Seoul")


def empty_target_price_summary() -> dict[str, Any]:
    return {
        "available": False,
        "target_price": 0.0,
        "latest_target_price": 0.0,
        "latest_target_upside_pct": 0.0,
        "upside_pct": 0.0,
        "opinion": "",
        "date": "",
        "latest_broker": "",
        "sample_count": 0,
        "coverage_count": 0,
        "dispersion_pct": 0.0,
        "revision_30d_pct": 0.0,
        "revision_direction": "",
        "staleness_days": 0,
        "opinion_distribution": {},
        "recent_reports": [],
    }


def parse_kis_date(value: Any) -> date | None:
    text = str(value or "").strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def normalize_target_price_report(
    row: dict[str, Any], current_price: float
) -> dict[str, Any]:
    report_date = parse_kis_date(row.get("stck_bsop_date"))
    target_price = parse_float(row.get("hts_goal_prc"))
    previous_close = parse_float(row.get("stck_prdy_clpr"))
    reference_price = float(current_price or previous_close or 0.0)
    upside_pct = (
        (target_price / reference_price - 1.0) * 100.0
        if target_price > 0 and reference_price > 0
        else 0.0
    )
    return {
        "date": (
            report_date.isoformat()
            if report_date
            else str(row.get("stck_bsop_date", "")).strip()
        ),
        "_sort_date": report_date or date.min,
        "broker": str(row.get("mbcr_name", "")).strip(),
        "opinion": str(row.get("invt_opnn", "")).strip(),
        "previous_opinion": str(row.get("rgbf_invt_opnn", "")).strip(),
        "target_price": target_price,
        "previous_close": previous_close,
        "upside_pct": upside_pct,
    }


def calc_target_revision_pct(reports: list[dict[str, Any]], recent_days: int) -> float:
    if not reports:
        return 0.0
    latest_date = max(item["_sort_date"] for item in reports)
    if latest_date == date.min:
        return 0.0
    recent_cutoff = latest_date - timedelta(days=recent_days)
    recent_targets = [
        float(item["target_price"])
        for item in reports
        if item["_sort_date"] >= recent_cutoff and float(item["target_price"]) > 0
    ]
    prior_targets = [
        float(item["target_price"])
        for item in reports
        if item["_sort_date"] < recent_cutoff and float(item["target_price"]) > 0
    ]
    if not recent_targets or not prior_targets:
        return 0.0
    prior_median = float(median(prior_targets))
    if prior_median <= 0:
        return 0.0
    return (float(median(recent_targets)) / prior_median - 1.0) * 100.0


def target_revision_direction(revision_pct: float) -> str:
    if revision_pct > 0:
        return "up"
    if revision_pct < 0:
        return "down"
    return "flat"


def summarize_target_price_rows(
    rows: list[dict[str, Any]],
    *,
    current_price: float,
    recent_days: int = 30,
    today: date | None = None,
) -> dict[str, Any]:
    """Summarize KIS analyst target-price rows for stock LLM scoring."""
    reports = [
        report
        for report in (
            normalize_target_price_report(row, current_price) for row in rows
        )
        if report["target_price"] > 0
    ]
    if not reports:
        return empty_target_price_summary()

    reports.sort(key=lambda item: item["_sort_date"], reverse=True)
    target_prices = [float(item["target_price"]) for item in reports]
    consensus_target = float(median(target_prices))
    latest = reports[0]
    reference_price = float(current_price or latest["previous_close"] or 0.0)
    upside_pct = (
        (consensus_target / reference_price - 1.0) * 100.0
        if reference_price > 0
        else 0.0
    )
    latest_upside_pct = (
        (float(latest["target_price"]) / reference_price - 1.0) * 100.0
        if reference_price > 0
        else 0.0
    )

    today = today or datetime.now(_KST).date()
    latest_date = latest["_sort_date"]
    staleness_days = (today - latest_date).days if latest_date else 0
    brokers = {
        str(item["broker"]).strip() for item in reports if str(item["broker"]).strip()
    }
    opinion_distribution: dict[str, int] = {}
    for item in reports:
        opinion = str(item["opinion"]).strip()
        if opinion:
            opinion_distribution[opinion] = opinion_distribution.get(opinion, 0) + 1

    revision_pct = calc_target_revision_pct(
        reports, recent_days=max(int(recent_days), 1)
    )
    revision_direction = target_revision_direction(revision_pct)
    dispersion_pct = (
        (max(target_prices) - min(target_prices)) / consensus_target * 100.0
        if consensus_target > 0 and len(target_prices) > 1
        else 0.0
    )

    recent_reports = [
        {
            "date": item["date"],
            "broker": item["broker"],
            "opinion": item["opinion"],
            "previous_opinion": item["previous_opinion"],
            "target_price": item["target_price"],
            "upside_pct": round(float(item["upside_pct"]), 2),
        }
        for item in reports[:5]
    ]

    return {
        "available": True,
        "target_price": consensus_target,
        "latest_target_price": float(latest["target_price"]),
        "latest_target_upside_pct": latest_upside_pct,
        "upside_pct": upside_pct,
        "opinion": str(latest["opinion"]),
        "date": str(latest["date"]),
        "latest_broker": str(latest["broker"]),
        "sample_count": len(reports),
        "coverage_count": len(brokers) if brokers else len(reports),
        "dispersion_pct": dispersion_pct,
        "revision_30d_pct": revision_pct,
        "revision_direction": revision_direction,
        "staleness_days": staleness_days,
        "opinion_distribution": opinion_distribution,
        "recent_reports": recent_reports,
    }
