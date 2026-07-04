"""KIS builder preset experiment report endpoint."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from fastapi import APIRouter, HTTPException

from shared.config.loader import ConfigLoader

router = APIRouter()

_KST = ZoneInfo("Asia/Seoul")

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_project_path(raw: str | Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return _REPO_ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _load_experiment_config() -> dict[str, Any]:
    raw_path = os.environ.get(
        "STOCK_BUILDER_PRESET_EXPERIMENT_CONFIG",
        "stock_builder_preset_experiment.yaml",
    )
    path = Path(raw_path)
    if path.is_absolute() or path.exists():
        cfg_path = _resolve_project_path(path)
        if not cfg_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Experiment config not found: {_display_path(cfg_path)}",
            )
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    else:
        data = ConfigLoader.load(raw_path, use_cache=False)

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Experiment config is invalid")
    exp = data.get("experiment", data)
    if not isinstance(exp, dict):
        raise HTTPException(status_code=500, detail="Experiment config is invalid")
    return exp


def _parse_config_date(value: Any) -> date:
    if hasattr(value, "isoformat"):
        return date.fromisoformat(value.isoformat())
    return date.fromisoformat(str(value))


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        raw = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _weekdays(start: date, end: date) -> list[date]:
    if end < start:
        return []
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
    return days


def _read_report(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


def _list_experiment_reports(output_dir: Path) -> list[dict[str, Any]]:
    if not output_dir.exists():
        return []

    reports: list[dict[str, Any]] = []
    paths = sorted(
        output_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for path in paths:
        data = _read_report(path)
        if data is None:
            continue
        exp = (
            data.get("experiment", {})
            if isinstance(data.get("experiment"), dict)
            else {}
        )
        reports.append(
            {
                "filename": path.name,
                "path": _display_path(path),
                "mtime": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=UTC
                ).isoformat(),
                "generated_at": exp.get("generated_at"),
                "start_date": exp.get("start_date"),
                "end_date": exp.get("end_date"),
                "summary_count": len(data.get("summaries") or []),
                "trade_count": len(data.get("trades") or []),
            }
        )
    return reports


def _latest_log_tail(log_dir: Path, *, max_lines: int = 80) -> dict[str, Any] | None:
    files = sorted(
        log_dir.glob("stock_builder_preset_experiment_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return None
    path = files[0]
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    return {
        "path": _display_path(path),
        "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
        "lines": lines[-max_lines:],
    }


def _experiment_progress(
    config: dict[str, Any], reports: list[dict[str, Any]]
) -> dict[str, Any]:
    start = _parse_config_date(config["start_date"])
    end = _parse_config_date(config["end_date"])
    scheduled_days = _weekdays(start, end)
    report_dates: set[date] = set()
    for report in reports:
        generated = _parse_dt(report.get("generated_at")) or _parse_dt(
            report.get("mtime")
        )
        if generated is None:
            continue
        local_day = generated.astimezone(_KST).date()
        if start <= local_day <= end and local_day.weekday() < 5:
            report_dates.add(local_day)

    today = datetime.now(_KST).date()
    completed = len(report_dates)
    total = len(scheduled_days)
    if today < start:
        status = "upcoming"
    elif today > end and completed >= total:
        status = "completed"
    elif today > end:
        status = "ended_incomplete"
    elif completed > 0:
        status = "running"
    else:
        status = "waiting_first_run"

    next_run_date = next(
        (day for day in scheduled_days if day not in report_dates and day >= today),
        None,
    )
    return {
        "status": status,
        "total_scheduled_days": total,
        "completed_report_days": completed,
        "completion_pct": round((completed / total) * 100, 1) if total else 0.0,
        "report_dates": [day.isoformat() for day in sorted(report_dates)],
        "next_run_at_kst": (
            f"{next_run_date.isoformat()}T16:35:00+09:00"
            if next_run_date is not None
            else None
        ),
        "last_report_at": reports[0].get("generated_at") if reports else None,
    }


@router.get("/experiments/stock-builder-preset")
async def stock_builder_preset_experiment_report() -> dict[str, Any]:
    """Return status and latest report for the stock builder preset experiment."""
    config = _load_experiment_config()
    output_dir = _resolve_project_path(
        str(config.get("output_dir") or "reports/stock_builder_preset_experiment")
    )
    reports = _list_experiment_reports(output_dir)
    latest_payload: dict[str, Any] | None = None
    if reports:
        latest_payload = _read_report(_resolve_project_path(reports[0]["path"]))

    log_dir = _resolve_project_path(os.environ.get("KIS_LOG_DIR", "logs"))
    preset_ids = [
        str(item.get("id"))
        for item in config.get("presets", [])
        if isinstance(item, dict) and item.get("id")
    ]
    return {
        "experiment": {
            "id": str(config.get("id") or "stock_builder_preset_experiment"),
            "description": str(config.get("description") or ""),
            "start_date": _parse_config_date(config["start_date"]).isoformat(),
            "end_date": _parse_config_date(config["end_date"]).isoformat(),
            "output_dir": _display_path(output_dir),
            "daily_run_time_kst": "16:35",
            "presets": preset_ids,
            "fallback_symbols": config.get("fallback_symbols") or [],
            "basket_source": config.get("basket_source") or {},
        },
        "progress": _experiment_progress(config, reports),
        "reports": reports,
        "latest_report": latest_payload,
        "latest_log": _latest_log_tail(log_dir),
    }
