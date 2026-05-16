"""Institutional ownership signals for stock screening."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def build_nps_ownership_signal(
    dart_data: dict[str, Any],
    config: Any,
) -> dict[str, Any]:
    """Build a normalized National Pension ownership signal from DART data."""
    holder_keywords = list(
        getattr(config, "stock_nps_holder_keywords", ["국민연금", "국민연금공단"])
    )
    reports = _matching_reports(dart_data, holder_keywords)
    if not reports:
        return {"available": False, "matched_reports": 0}

    reports.sort(
        key=lambda report: (
            _parse_report_date(report.get("rcept_dt")),
            str(report.get("rcept_no", "")),
        ),
        reverse=True,
    )
    latest = reports[0]
    return {
        "available": True,
        "holder": latest["holder"],
        "source": latest["source"],
        "report_type": latest.get("report_type", ""),
        "report_reason": latest.get("report_reason", ""),
        "rcept_no": latest.get("rcept_no", ""),
        "rcept_dt": _format_report_date(latest.get("rcept_dt", "")),
        "report_url": _viewer_url(str(latest.get("rcept_no", ""))),
        "holding_shares": latest.get("holding_shares", 0),
        "holding_change_shares": latest.get("holding_change_shares", 0),
        "holding_ratio_pct": latest.get("holding_ratio_pct", 0.0),
        "holding_ratio_change_pctp": latest.get("holding_ratio_change_pctp", 0.0),
        "matched_reports": len(reports),
        "recent_reports": reports[:3],
    }


def _matching_reports(
    dart_data: dict[str, Any],
    holder_keywords: list[str],
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for row in _as_rows(dart_data.get("major_shareholders")):
        if _is_holder_match(row.get("repror", ""), holder_keywords):
            reports.append(_normalize_majorstock(row))
    for row in _as_rows(dart_data.get("executive_major_shareholders")):
        if _is_holder_match(row.get("repror", ""), holder_keywords):
            reports.append(_normalize_elestock(row))
    return reports


def _normalize_majorstock(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "majorstock",
        "holder": str(row.get("repror", "")).strip(),
        "report_type": str(row.get("report_tp", "")).strip(),
        "report_reason": str(row.get("report_resn", "")).strip(),
        "rcept_no": str(row.get("rcept_no", "")).strip(),
        "rcept_dt": _format_report_date(row.get("rcept_dt", "")),
        "holding_shares": _parse_int(row.get("stkqy")),
        "holding_change_shares": _parse_int(row.get("stkqy_irds")),
        "holding_ratio_pct": _parse_float(row.get("stkrt")),
        "holding_ratio_change_pctp": _parse_float(row.get("stkrt_irds")),
    }


def _normalize_elestock(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "elestock",
        "holder": str(row.get("repror", "")).strip(),
        "report_type": str(row.get("isu_main_shrholdr", "")).strip(),
        "report_reason": "",
        "rcept_no": str(row.get("rcept_no", "")).strip(),
        "rcept_dt": _format_report_date(row.get("rcept_dt", "")),
        "holding_shares": _parse_int(row.get("sp_stock_lmp_cnt")),
        "holding_change_shares": _parse_int(row.get("sp_stock_lmp_irds_cnt")),
        "holding_ratio_pct": _parse_float(row.get("sp_stock_lmp_rate")),
        "holding_ratio_change_pctp": _parse_float(row.get("sp_stock_lmp_irds_rate")),
    }


def _as_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return []


def _is_holder_match(holder: Any, keywords: list[str]) -> bool:
    text = str(holder or "")
    return any(keyword and keyword in text for keyword in keywords)


def _parse_float(value: Any) -> float:
    text = str(value or "").replace(",", "").replace("%", "").strip()
    if not text or text == "-":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_int(value: Any) -> int:
    return int(round(_parse_float(value)))


def _parse_report_date(value: Any) -> date:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(
                text[:10] if fmt == "%Y-%m-%d" else text[:8], fmt
            ).date()
        except ValueError:
            continue
    return date.min


def _format_report_date(value: Any) -> str:
    parsed = _parse_report_date(value)
    return "" if parsed == date.min else parsed.isoformat()


def _viewer_url(rcept_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
