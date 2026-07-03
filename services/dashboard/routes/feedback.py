"""Unified performance feedback report API (Phase 6B — read-only surface).

Serves the report files written by the Phase 6A feedback engine
(``services/feedback_reporter`` + ``shared/reports``). This lane owns ONLY the
read path — it never generates, mutates, or influences any report, strategy,
gate, or execution decision.

Fixed contract (agreed with the 6A lane; parse defensively — the engine may
not have run yet, and older reports may omit fields):

- Files: ``{reports_root}/{weekly,monthly,quarterly}/<period_label>.md`` plus a
  same-basename ``.json``. ``period_label`` is ``YYYY-MM-DD`` (weekly),
  ``YYYY-MM`` (monthly), or ``YYYY-QN`` (quarterly).
- JSON body: ``{kind, period_label, generated_at, tracks: {B,C,A: {trades,
  win_rate, avg_win_loss, expectancy, realized_pnl, slippage|null, ...}},
  missing: [...], ...kind-specific sections}``. Every field is treated as
  optional and matched through candidate keys (Phase 3D defensive pattern).
- ``reports_root`` comes from ``config/feedback_reports.yaml`` via
  ``FeedbackReportsConfig.load_or_default()`` (6A loader — imported, never
  edited). If the config is missing the default ``reports/feedback`` is used.
- Redis (DB 1) hash ``portfolio:feedback:latest``: ``kind``, ``period_label``,
  ``generated_at``, ``json_path``, ``md_path``, ``headline`` (JSON string).

Endpoints degrade gracefully: a missing directory or absent Redis pointer
yields an empty list / ``{"status": "unavailable"}`` rather than an error, so
the ``/risk`` feedback card renders its empty state when the batch is idle.

Routes (reached by the Next.js proxy as ``/api/reports/feedback/*``):
- ``GET /api/reports/feedback?kind=weekly|monthly|quarterly&limit=12``
- ``GET /api/reports/feedback/latest``
- ``GET /api/reports/feedback/{kind}/{period_label}``

All routes are read-only; the router defines no POST/PUT/DELETE, so those
verbs answer 405 automatically.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from services.dashboard.routes.market_risk import (
    _coerce_float,
    _coerce_text,
    _get_redis_client,
    _redis_hgetall,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports/feedback", tags=["feedback-reports"])

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Fixed contract: the three report cadences. Also the path-traversal whitelist —
# a request kind must be one of these exact segments.
_KINDS: tuple[str, ...] = ("weekly", "monthly", "quarterly")

# period_label whitelist (path-traversal defense): weekly ``YYYY-MM-DD``,
# monthly ``YYYY-MM``, quarterly ``YYYY-QN``. Anchored — no separators, no
# ``..``, no slashes can pass.
_PERIOD_LABEL_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?|-Q[1-4])$")

_DEFAULT_REPORTS_ROOT = "reports/feedback"

# Redis freshness-pointer key (fixed contract). Env-overridable for operator
# setups; the default is the agreed key.
_LATEST_KEY = os.environ.get(
    "PORTFOLIO_FEEDBACK_LATEST_KEY", "portfolio:feedback:latest"
)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _reports_root() -> Path:
    """Resolve the report root dir from 6A config, falling back to the default.

    The dashboard mounts ``./reports`` read-only at ``/app/reports`` (see
    docker-compose.yml), so a relative ``reports_root`` resolves under the repo
    root exactly as the experiments route resolves its output dir.
    """
    raw = _DEFAULT_REPORTS_ROOT
    try:
        from shared.reports.config import FeedbackReportsConfig

        raw = (
            FeedbackReportsConfig.load_or_default().reports_root
            or _DEFAULT_REPORTS_ROOT
        )
    except Exception:  # noqa: BLE001 - config import/parse must never 500 the UI
        logger.debug("feedback reports config unavailable; using default root")
    path = Path(raw)
    return path if path.is_absolute() else _REPO_ROOT / path


def _kind_dir(kind: str) -> Path:
    return _reports_root() / kind


def _safe_report_path(kind: str, period_label: str, suffix: str) -> Path | None:
    """Build a report path, defending against traversal.

    Returns ``None`` when the resolved path escapes ``reports_root`` (defense in
    depth — the regex + kind whitelist already block traversal, but the final
    containment check is authoritative).
    """
    root = _reports_root()
    candidate = (root / kind / f"{period_label}{suffix}").resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


# ---------------------------------------------------------------------------
# Lenient parsing (candidate-key mapping — Phase 3D defensive pattern)
# ---------------------------------------------------------------------------

# tracks[X] metric name → candidate JSON keys, most-specific first.
_METRIC_CANDIDATES: dict[str, tuple[str, ...]] = {
    "trades": ("trades", "trade_count", "closed_trades", "n_trades", "num_trades"),
    "win_rate": ("win_rate", "win_rate_pct", "winrate", "hit_rate"),
    "avg_win_loss": (
        "avg_win_loss",
        "avg_win_loss_ratio",
        "win_loss_ratio",
        "payoff",
        "payoff_ratio",
    ),
    "expectancy": ("expectancy", "ev", "expected_value", "edge"),
    "realized_pnl": (
        "realized_pnl",
        "realized_pnl_krw",
        "realized",
        "pnl",
        "net_pnl",
    ),
    "slippage": ("slippage", "slippage_bps", "avg_slippage", "slippage_pct"),
}

_TRACK_ALIASES: dict[str, tuple[str, ...]] = {
    "B": ("B", "b", "track_b", "trackB", "stock"),
    "C": ("C", "c", "track_c", "trackC", "futures"),
    "A": ("A", "a", "track_a", "trackA", "core"),
}


def _pick(source: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in source and source[key] not in (None, ""):
            return source[key]
    return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _track_metrics(track_obj: Any) -> dict[str, Any]:
    """Extract the fixed metric set from one track object (all optional)."""
    obj = track_obj if isinstance(track_obj, dict) else {}
    return {
        "trades": _to_int(_pick(obj, _METRIC_CANDIDATES["trades"])),
        "win_rate": _coerce_float(_pick(obj, _METRIC_CANDIDATES["win_rate"])),
        "avg_win_loss": _coerce_float(_pick(obj, _METRIC_CANDIDATES["avg_win_loss"])),
        "expectancy": _coerce_float(_pick(obj, _METRIC_CANDIDATES["expectancy"])),
        "realized_pnl": _coerce_float(_pick(obj, _METRIC_CANDIDATES["realized_pnl"])),
        "slippage": _coerce_float(_pick(obj, _METRIC_CANDIDATES["slippage"])),
    }


def _tracks_summary(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map the report's ``tracks`` section into a fixed B/C/A metric summary."""
    raw = data.get("tracks")
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for track, aliases in _TRACK_ALIASES.items():
        obj = _pick(raw, aliases)
        out[track] = _track_metrics(obj)
    return out


# Quarterly verdict normalization (§8.2 판정 자료 — 승격/강등은 수동).
# NOTE: token order mirrors _VERDICT_TOKENS insertion order (met→below→
# insufficient→deferred); matching is substring-based, so keep positive tokens
# ("outperform") out of the "below" bucket. The engine (shared/reports/
# feedback.py) emits these exact verdict strings, mapped here to the 4 UI badges:
#   Track B  : meets / below / insufficient_evidence
#   Track C  : on_track / below_breakeven / reduce_capital_50 /
#              review_termination / insufficient_evidence
#   Track A  : outperform / underperform / deferred / insufficient_evidence
_VERDICT_TOKENS: dict[str, tuple[str, ...]] = {
    "met": (
        "meets",
        "met",
        "on_track",
        "outperform",
        "pass",
        "passed",
        "satisfied",
        "ok",
        "충족",
        "달성",
    ),
    "below": (
        "below",
        "below_breakeven",
        "reduce_capital",
        "review_termination",
        "fail",
        "failed",
        "miss",
        "미달",
        "부진",
        "underperform",
    ),
    "insufficient": (
        "insufficient",
        "insufficient_data",
        "insufficient-data",
        "no_data",
        "부족",
        "자료부족",
        "n/a",
    ),
    "deferred": ("deferred", "defer", "pending", "유예", "보류", "연기"),
}


def _normalize_verdict(raw: Any) -> str:
    text = (_coerce_text(raw) or "").strip().lower()
    if not text:
        return "unknown"
    for status, tokens in _VERDICT_TOKENS.items():
        if any(token in text for token in tokens):
            return status
    return "unknown"


def _verdicts(data: dict[str, Any]) -> dict[str, str]:
    """Best-effort per-track quarterly verdict (normalized status strings).

    Looks in a top-level ``verdicts``/``judgments`` map first, then falls back
    to a verdict field inside each track object.
    """
    out: dict[str, str] = {}
    top = _pick(data, ("verdicts", "judgments", "verdict", "judgment"))
    top = top if isinstance(top, dict) else {}
    tracks = data.get("tracks")
    tracks = tracks if isinstance(tracks, dict) else {}
    for track, aliases in _TRACK_ALIASES.items():
        raw = _pick(top, aliases)
        if raw is None:
            track_obj = _pick(tracks, aliases)
            if isinstance(track_obj, dict):
                raw = _pick(
                    track_obj, ("verdict", "status", "judgment", "decision", "result")
                )
        out[track] = _normalize_verdict(raw)
    return out


def _extract_headline(data: dict[str, Any]) -> str | None:
    """A single human-readable headline line, if the report carries one."""
    raw = _pick(data, ("headline", "summary_line", "summary", "title"))
    if isinstance(raw, str):
        return raw.strip() or None
    if isinstance(raw, dict):
        text = _pick(raw, ("text", "line", "summary", "headline"))
        return _coerce_text(text)
    return None


def _extract_contribution(data: dict[str, Any]) -> str | None:
    """Monthly contribution/attribution one-liner (best-effort)."""
    raw = _pick(
        data,
        (
            "contribution",
            "contribution_line",
            "attribution",
            "attribution_line",
            "monthly_contribution",
        ),
    )
    if isinstance(raw, str):
        return raw.strip() or None
    if isinstance(raw, dict):
        text = _pick(raw, ("text", "line", "summary", "headline"))
        return _coerce_text(text)
    return _extract_headline(data)


def _missing(data: dict[str, Any]) -> list[str]:
    raw = data.get("missing")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw]


# ---------------------------------------------------------------------------
# File access
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _summary_row(path: Path, kind: str) -> dict[str, Any]:
    """Lightweight listing row: identity + headline metrics (no heavy payload)."""
    data = _read_json(path)
    period_label = path.stem
    if data is None:
        return {
            "kind": kind,
            "period_label": period_label,
            "generated_at": None,
            "error": "unreadable",
            "tracks": {},
            "missing": [],
            "md_exists": path.with_suffix(".md").exists(),
        }
    row: dict[str, Any] = {
        "kind": _coerce_text(data.get("kind")) or kind,
        "period_label": _coerce_text(data.get("period_label")) or period_label,
        "generated_at": _coerce_text(data.get("generated_at")),
        "tracks": _tracks_summary(data),
        "missing": _missing(data),
        "headline": _extract_headline(data),
        "md_exists": path.with_suffix(".md").exists(),
    }
    if kind == "monthly":
        row["contribution"] = _extract_contribution(data)
    if kind == "quarterly":
        row["verdicts"] = _verdicts(data)
    return row


def _list_json_paths(kind: str) -> list[Path]:
    """Report JSON files for a kind, newest period first (label sorts chrono)."""
    directory = _kind_dir(kind)
    if not directory.exists():
        return []
    paths = [p for p in directory.glob("*.json") if p.is_file()]
    # period_label stems (YYYY-MM-DD / YYYY-MM / YYYY-QN) sort chronologically
    # as plain strings within a kind; reverse for newest-first.
    return sorted(paths, key=lambda p: p.stem, reverse=True)


# ---------------------------------------------------------------------------
# Latest (Redis pointer, file-scan fallback)
# ---------------------------------------------------------------------------


def _parse_headline_field(raw: Any) -> Any:
    """The Redis ``headline`` field is a JSON string; decode leniently."""
    text = _coerce_text(raw)
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def _latest_from_redis() -> dict[str, Any] | None:
    payload = _redis_hgetall(_get_redis_client(), _LATEST_KEY)
    if not payload:
        return None
    kind = _coerce_text(payload.get("kind"))
    period_label = _coerce_text(payload.get("period_label"))
    if not kind or not period_label:
        return None
    return {
        "status": "ok",
        "source": "redis",
        "kind": kind,
        "period_label": period_label,
        "generated_at": _coerce_text(payload.get("generated_at")),
        "json_path": _coerce_text(payload.get("json_path")),
        "md_path": _coerce_text(payload.get("md_path")),
        "headline": _parse_headline_field(payload.get("headline")),
    }


def _latest_from_scan() -> dict[str, Any] | None:
    """Fallback: newest report across all kinds by file mtime."""
    newest: tuple[float, str, Path] | None = None
    for kind in _KINDS:
        for path in _list_json_paths(kind):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if newest is None or mtime > newest[0]:
                newest = (mtime, kind, path)
    if newest is None:
        return None
    _, kind, path = newest
    data = _read_json(path) or {}
    return {
        "status": "ok",
        "source": "scan",
        "kind": _coerce_text(data.get("kind")) or kind,
        "period_label": _coerce_text(data.get("period_label")) or path.stem,
        "generated_at": _coerce_text(data.get("generated_at")),
        "json_path": str(path),
        "md_path": (
            str(path.with_suffix(".md")) if path.with_suffix(".md").exists() else None
        ),
        "headline": _extract_headline(data),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_feedback_reports(
    kind: str = Query("weekly"),
    limit: int = Query(12, ge=1, le=100),
) -> dict[str, Any]:
    """Recent reports for a cadence, newest first (headline metrics only)."""
    if kind not in _KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"invalid kind: {kind!r} (expected one of {list(_KINDS)})",
        )
    paths = _list_json_paths(kind)[:limit]
    return {
        "kind": kind,
        "count": len(paths),
        "reports": [_summary_row(path, kind) for path in paths],
    }


@router.get("/latest")
async def latest_feedback_report() -> dict[str, Any]:
    """Freshness pointer: newest generated report (Redis, file-scan fallback)."""
    result = _latest_from_redis() or _latest_from_scan()
    if result is None:
        return {"status": "unavailable", "source": None}
    return result


@router.get("/{kind}/{period_label}")
async def get_feedback_report(kind: str, period_label: str) -> dict[str, Any]:
    """Single report JSON in full, plus whether the sibling ``.md`` exists.

    Path-traversal defense: ``kind`` must be whitelisted, ``period_label`` must
    match the anchored period regex, and the resolved path must stay under
    ``reports_root``.
    """
    if kind not in _KINDS:
        raise HTTPException(status_code=404, detail=f"unknown report kind: {kind!r}")
    if not _PERIOD_LABEL_RE.match(period_label):
        raise HTTPException(
            status_code=400, detail=f"invalid period_label: {period_label!r}"
        )
    json_path = _safe_report_path(kind, period_label, ".json")
    if json_path is None:
        raise HTTPException(status_code=400, detail="path outside reports root")
    if not json_path.exists():
        raise HTTPException(
            status_code=404, detail=f"report not found: {kind}/{period_label}"
        )
    data = _read_json(json_path)
    if data is None:
        raise HTTPException(status_code=422, detail="report is not valid JSON")
    md_path = _safe_report_path(kind, period_label, ".md")
    md_exists = bool(md_path and md_path.exists())
    return {
        "kind": kind,
        "period_label": period_label,
        "md_exists": md_exists,
        "report": data,
    }
