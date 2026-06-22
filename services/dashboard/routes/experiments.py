"""Stock strategy experiment API — on-demand runs + listing (Phase 3).

Wraps ``shared.backtest.experiment_runner``. Backtests are CPU-heavy, so an
on-demand run executes in a worker thread (``asyncio.to_thread``) behind a single
concurrency lock: the dashboard event loop stays responsive and concurrent
launches queue rather than pile up.

On-demand results are held IN MEMORY on the job (the dashboard mounts
``./reports`` read-only, so it cannot persist there). The authoritative on-disk
reports under ``reports/stock_experiment/`` come from the nightly scheduler job
(Phase 2); ``GET /latest`` and the listing read those.

Routes (under the existing kis-builder namespace so the Next.js proxy reaches
them via ``/api/experiments/*``):
- ``GET  /api/kis-builder/experiments``            → recent disk reports + jobs
- ``GET  /api/kis-builder/experiments/latest``     → newest disk report (full)
- ``GET  /api/kis-builder/experiments/latest/compare-paper`` → latest vs paper stats
- ``GET  /api/kis-builder/experiments/strategies`` → registry stock strategy catalog
- ``POST /api/kis-builder/experiments/run``        → launch on-demand → job
- ``GET  /api/kis-builder/experiments/jobs/{id}``  → job status (+ report when done)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections import OrderedDict
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kis-builder/experiments", tags=["experiments"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OUTPUT_DIR = os.environ.get("STOCK_EXPERIMENT_OUTPUT_DIR", "reports/stock_experiment")
_DEFAULT_SPEC = os.environ.get(
    "STOCK_EXPERIMENT_SPEC", "config/experiments/stock_default.yaml"
)
_STOCK_STRATEGY_DIR = os.environ.get(
    "STOCK_EXPERIMENT_STRATEGY_DIR", "config/strategies/stock"
)
_COMPARE_MIN_PAPER_TRADES = int(
    os.environ.get("STOCK_EXPERIMENT_COMPARE_MIN_PAPER_TRADES", "3")
)
_COMPARE_WIN_RATE_WATCH_GAP_PCT = float(
    os.environ.get("STOCK_EXPERIMENT_COMPARE_WIN_RATE_WATCH_GAP_PCT", "20")
)
_COMPARE_WIN_RATE_FAIL_GAP_PCT = float(
    os.environ.get("STOCK_EXPERIMENT_COMPARE_WIN_RATE_FAIL_GAP_PCT", "30")
)
_KST = ZoneInfo("Asia/Seoul")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _resolve(raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else _REPO_ROOT / path


# --------------------------------------------------------------------------- #
# Job manager — serialized background backtests, in-memory results
# --------------------------------------------------------------------------- #


class ExperimentJob(BaseModel):
    """On-demand experiment job metadata (the report is held separately)."""

    job_id: str
    status: str = "queued"  # queued | running | done | failed
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    experiment_id: str | None = None


class ExperimentJobManager:
    """Runs experiments off the event loop, one at a time, keeping results in RAM."""

    def __init__(self, runner: Any | None = None, max_jobs: int = 50) -> None:
        self._jobs: OrderedDict[str, ExperimentJob] = OrderedDict()
        self._reports: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._runner = runner  # injectable for tests; default resolved lazily
        self._max_jobs = max_jobs

    def _runner_fn(self) -> Any:
        if self._runner is not None:
            return self._runner
        from shared.backtest.experiment_runner import run_stock_experiment

        return run_stock_experiment

    async def submit(self, spec_dict: dict[str, Any]) -> ExperimentJob:
        from shared.backtest.experiment_runner import ExperimentSpec

        spec = ExperimentSpec.from_dict(spec_dict)  # raises on invalid spec
        job_id = uuid.uuid4().hex[:12]
        job = ExperimentJob(job_id=job_id, status="queued", created_at=_now_iso())
        self._jobs[job_id] = job
        while len(self._jobs) > self._max_jobs:
            old_id, _ = self._jobs.popitem(last=False)
            self._reports.pop(old_id, None)
            self._tasks.pop(old_id, None)
        self._tasks[job_id] = asyncio.create_task(self._run(job, spec))
        return job

    async def _run(self, job: ExperimentJob, spec: Any) -> None:
        async with self._lock:  # serialize CPU-heavy backtests
            job.status = "running"
            job.started_at = _now_iso()
            try:
                report = await asyncio.to_thread(self._runner_fn(), spec)
                job.experiment_id = report.get("experiment", {}).get("id")
                # Only retain the (heavy) report if the job is still tracked — a
                # job evicted while queued must not re-leak its report into
                # _reports, which would then never be evicted again.
                if job.job_id in self._jobs:
                    self._reports[job.job_id] = report
                job.status = "done"
            except Exception as exc:  # noqa: BLE001 - surface as job failure
                logger.exception("experiment job %s failed", job.job_id)
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
            finally:
                job.finished_at = _now_iso()
                self._prune()

    def _prune(self) -> None:
        """Keep _reports/_tasks bounded to the tracked jobs (defends against an
        eviction that raced with an in-flight run)."""
        live = set(self._jobs)
        for jid in [k for k in self._reports if k not in live]:
            self._reports.pop(jid, None)
        for jid in [k for k, t in self._tasks.items() if k not in live and t.done()]:
            self._tasks.pop(jid, None)

    def get(self, job_id: str) -> ExperimentJob | None:
        return self._jobs.get(job_id)

    def report(self, job_id: str) -> dict[str, Any] | None:
        return self._reports.get(job_id)

    def list_jobs(self, limit: int = 20) -> list[ExperimentJob]:
        return list(self._jobs.values())[-limit:][::-1]


_manager = ExperimentJobManager()


# --------------------------------------------------------------------------- #
# Disk report helpers (scheduler-written reports)
# --------------------------------------------------------------------------- #


def _report_paths() -> list[Path]:
    out = _resolve(_OUTPUT_DIR)
    if not out.exists():
        return []
    return sorted(out.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def _read_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _report_summary_row(path: Path) -> dict[str, Any]:
    """Lightweight listing row (no equity_curves/trades payload)."""
    try:
        data = _read_report(path)
    except (OSError, ValueError):
        return {"filename": path.name, "error": "unreadable"}
    exp = data.get("experiment", {})
    return {
        "filename": path.name,
        "experiment_id": exp.get("id"),
        "start_date": exp.get("start_date"),
        "end_date": exp.get("end_date"),
        "generated_at": exp.get("generated_at"),
        "strategy_count": len(data.get("summaries", [])),
        "status_by_strategy": data.get("status_by_strategy", []),
    }


def _strategy_catalog() -> list[dict[str, Any]]:
    """Registry stock strategies the user can experiment (name/enabled/timeframe)."""
    out: list[dict[str, Any]] = []
    sdir = _resolve(_STOCK_STRATEGY_DIR)
    if not sdir.exists():
        return out
    for path in sorted(sdir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        strat = data.get("strategy", {})
        if not isinstance(strat, dict):
            continue
        out.append(
            {
                "name": strat.get("name", path.stem),
                "enabled": bool(strat.get("enabled", False)),
                "timeframe": strat.get("timeframe", "minute"),
                "description": strat.get("description", ""),
            }
        )
    return out


def _load_default_spec() -> dict[str, Any]:
    path = _resolve(_DEFAULT_SPEC)
    if not path.exists():
        return {"id": "stock_experiment", "strategies": [], "symbols": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# --------------------------------------------------------------------------- #
# Backtest vs paper comparison helpers
# --------------------------------------------------------------------------- #


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _parse_compare_timestamp(
    value: Any, *, end_of_day: bool = False
) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(
            value,
            time.max if end_of_day else time.min,
            tzinfo=_KST,
        )
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            if len(text) == 10:
                parsed_date = date.fromisoformat(text)
                parsed = datetime.combine(
                    parsed_date,
                    time.max if end_of_day else time.min,
                    tzinfo=_KST,
                )
            else:
                parsed = datetime.fromisoformat(text)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_KST)
    return parsed.astimezone(UTC)


def _experiment_window(exp: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    start_raw = exp.get("start_date") or exp.get("start")
    end_raw = exp.get("end_date") or exp.get("end")
    return (
        _parse_compare_timestamp(start_raw),
        _parse_compare_timestamp(end_raw, end_of_day=True),
    )


def _filter_paper_trades_by_window(
    trades: list[dict[str, Any]],
    *,
    start: datetime | None,
    end: datetime | None,
) -> list[dict[str, Any]]:
    if start is None and end is None:
        return trades
    filtered: list[dict[str, Any]] = []
    for trade in trades:
        exit_time = _parse_compare_timestamp(
            trade.get("exit_time") or trade.get("exit_date")
        )
        if exit_time is None:
            continue
        if start is not None and exit_time < start:
            continue
        if end is not None and exit_time > end:
            continue
        filtered.append(trade)
    return filtered


def _paper_trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [_to_float(t.get("pnl")) or 0.0 for t in trades]
    pnl_pcts = [_to_float(t.get("pnl_pct")) for t in trades]
    pnl_pcts = [p for p in pnl_pcts if p is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    symbols = sorted(
        {
            str(t.get("symbol") or t.get("code") or "")
            for t in trades
            if t.get("symbol") or t.get("code")
        }
    )
    exit_times = [str(t.get("exit_time") or "") for t in trades if t.get("exit_time")]
    return {
        "trade_count": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": (len(wins) / len(trades) * 100.0) if trades else None,
        "total_pnl": sum(pnls),
        "avg_pnl": (sum(pnls) / len(trades)) if trades else None,
        "avg_pnl_pct": (sum(pnl_pcts) / len(pnl_pcts)) if pnl_pcts else None,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "symbols": symbols,
        "latest_exit_time": max(exit_times) if exit_times else None,
    }


def _load_stock_paper_trades(
    strategy_id: str,
    strategy_name: str | None,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[list[dict], bool]:
    try:
        from services.dashboard.routes.trades import _load_runtime_ledger_trades

        rows, available = _load_runtime_ledger_trades(
            "stock",
            strategy=strategy_id,
            limit=0 if start or end else 10_000,
        )
    except Exception:
        logger.exception(
            "paper comparison ledger query failed strategy=%s", strategy_id
        )
        return [], False
    rows = _filter_paper_trades_by_window(rows, start=start, end=end)
    if rows or not strategy_name or strategy_name == strategy_id:
        return rows, available

    # Some older paper rows recorded the display name instead of the stable id.
    try:
        fallback_rows, fallback_available = _load_runtime_ledger_trades(
            "stock",
            strategy=strategy_name,
            limit=0 if start or end else 10_000,
        )
    except Exception:
        logger.exception(
            "paper comparison ledger fallback query failed strategy=%s",
            strategy_name,
        )
        return [], available
    fallback_rows = _filter_paper_trades_by_window(
        fallback_rows,
        start=start,
        end=end,
    )
    return fallback_rows, available or fallback_available


def _comparison_status(
    *,
    missing_evidence: list[str],
    backtest_return_pct: float | None,
    backtest_win_rate_pct: float | None,
    paper: dict[str, Any],
) -> str:
    if missing_evidence:
        return "insufficient_data"

    paper_total_pnl = _to_float(paper.get("total_pnl")) or 0.0
    paper_win_rate_pct = _to_float(paper.get("win_rate_pct"))
    win_rate_gap = (
        paper_win_rate_pct - backtest_win_rate_pct
        if paper_win_rate_pct is not None and backtest_win_rate_pct is not None
        else None
    )

    if (
        backtest_return_pct is not None
        and backtest_return_pct > 0
        and paper_total_pnl < 0
    ):
        return "fail"
    if win_rate_gap is not None and win_rate_gap <= -_COMPARE_WIN_RATE_FAIL_GAP_PCT:
        return "fail"
    if (
        backtest_return_pct is None
        or backtest_return_pct <= 0
        or paper_total_pnl <= 0
        or (
            win_rate_gap is not None
            and win_rate_gap <= -_COMPARE_WIN_RATE_WATCH_GAP_PCT
        )
    ):
        return "watch"
    return "aligned"


def _compare_latest_to_paper(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {
            "generated_at": _now_iso(),
            "source": {
                "experiment_id": None,
                "experiment_generated_at": None,
                "ledger_available": False,
                "min_paper_trades": _COMPARE_MIN_PAPER_TRADES,
            },
            "comparisons": [],
            "missing_evidence": ["latest_experiment_report"],
        }

    exp = (
        report.get("experiment", {})
        if isinstance(report.get("experiment"), dict)
        else {}
    )
    window_start, window_end = _experiment_window(exp)
    summaries = (
        report.get("summaries") if isinstance(report.get("summaries"), list) else []
    )
    comparisons: list[dict[str, Any]] = []
    ledger_seen = False
    top_missing: set[str] = set()

    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        strategy_id = str(
            summary.get("strategy_id") or summary.get("strategy_name") or ""
        )
        strategy_name = summary.get("strategy_name")
        missing: list[str] = []
        if not strategy_id:
            missing.append("strategy_id")
        if window_start is None or window_end is None:
            missing.append("experiment_window")

        backtest_closed = _to_int(summary.get("closed_trades"))
        backtest_return_pct = _to_float(summary.get("total_return_pct"))
        backtest_win_rate_pct = _to_float(summary.get("win_rate_pct"))
        if backtest_closed <= 0:
            missing.append("backtest_closed_trades")
        if backtest_return_pct is None:
            missing.append("backtest_total_return_pct")

        paper_rows: list[dict] = []
        ledger_available = False
        if strategy_id:
            paper_rows, ledger_available = _load_stock_paper_trades(
                strategy_id,
                str(strategy_name) if strategy_name else None,
                start=window_start,
                end=window_end,
            )
            ledger_seen = ledger_seen or ledger_available
        if not ledger_available:
            missing.append("runtime_ledger")

        paper = _paper_trade_stats(paper_rows)
        if paper["trade_count"] < _COMPARE_MIN_PAPER_TRADES:
            missing.append("paper_trade_count")

        status = _comparison_status(
            missing_evidence=missing,
            backtest_return_pct=backtest_return_pct,
            backtest_win_rate_pct=backtest_win_rate_pct,
            paper=paper,
        )
        paper_win_rate_pct = _to_float(paper.get("win_rate_pct"))
        comparisons.append(
            {
                "strategy_id": strategy_id,
                "strategy_name": strategy_name,
                "status": status,
                "missing_evidence": missing,
                "backtest": {
                    "closed_trades": backtest_closed,
                    "win_rate_pct": backtest_win_rate_pct,
                    "total_return_pct": backtest_return_pct,
                    "realized_pnl": _to_float(summary.get("realized_pnl")),
                    "profit_factor": _to_float(summary.get("profit_factor")),
                    "max_drawdown_pct": _to_float(summary.get("max_drawdown_pct")),
                    "sharpe_ratio": _to_float(summary.get("sharpe_ratio")),
                },
                "paper": paper,
                "deltas": {
                    "trade_count": paper["trade_count"] - backtest_closed,
                    "win_rate_pct": (
                        paper_win_rate_pct - backtest_win_rate_pct
                        if paper_win_rate_pct is not None
                        and backtest_win_rate_pct is not None
                        else None
                    ),
                    "pnl_vs_realized": (
                        (_to_float(paper.get("total_pnl")) or 0.0)
                        - (_to_float(summary.get("realized_pnl")) or 0.0)
                    ),
                },
            }
        )
        top_missing.update(missing)

    if not summaries:
        top_missing.add("experiment_summaries")

    return {
        "generated_at": _now_iso(),
        "source": {
            "experiment_id": exp.get("id"),
            "experiment_generated_at": exp.get("generated_at"),
            "window_start": window_start.isoformat() if window_start else None,
            "window_end": window_end.isoformat() if window_end else None,
            "ledger_available": ledger_seen,
            "min_paper_trades": _COMPARE_MIN_PAPER_TRADES,
        },
        "comparisons": comparisons,
        "missing_evidence": sorted(top_missing),
    }


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


class RunExperimentRequest(BaseModel):
    """On-demand run overrides; any omitted field falls back to the default spec."""

    id: str | None = None
    description: str | None = None
    strategies: list[dict[str, Any]] | None = None
    symbols: list[str] | None = None
    start: str | None = None
    end: str | None = None
    lookback_days: int | None = Field(default=None, ge=1)


@router.get("")
async def list_experiments() -> dict[str, Any]:
    return {
        "reports": [_report_summary_row(p) for p in _report_paths()[:10]],
        "jobs": [j.model_dump(mode="json") for j in _manager.list_jobs()],
    }


@router.get("/latest")
async def latest_report() -> dict[str, Any]:
    paths = _report_paths()
    return {"report": _read_report(paths[0]) if paths else None}


@router.get("/latest/compare-paper")
async def latest_paper_comparison() -> dict[str, Any]:
    paths = _report_paths()
    try:
        report = _read_report(paths[0]) if paths else None
    except (OSError, ValueError, json.JSONDecodeError):
        report = None
    return _compare_latest_to_paper(report)


@router.get("/strategies")
async def strategy_catalog() -> dict[str, Any]:
    return {"strategies": _strategy_catalog()}


@router.post("/run")
async def run_experiment(req: RunExperimentRequest) -> dict[str, Any]:
    try:
        spec_dict = _load_default_spec()
        spec_dict.update(req.model_dump(exclude_none=True))
        job = await _manager.submit(spec_dict)
    except Exception as exc:  # noqa: BLE001 - bad spec/config → 400
        raise HTTPException(
            status_code=400, detail=f"Invalid experiment spec: {exc}"
        ) from exc
    return job.model_dump(mode="json")


@router.get("/jobs/{job_id}")
async def job_status(job_id: str) -> dict[str, Any]:
    job = _manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    out = job.model_dump(mode="json")
    if job.status == "done":
        out["report"] = _manager.report(job_id)
    return out
