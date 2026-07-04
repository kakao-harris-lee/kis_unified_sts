"""KIS futures/index OHLCV parser helpers."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _first_present(item: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    """Get first present value from dict."""
    for k in keys:
        v = item.get(k)
        if v is not None and (not isinstance(v, str) or v.strip()):
            return v
    return default


# Maximum tolerated close-to-close move between consecutive accepted bars when
# resolving divergent-duplicate minutes. Override via env var.
_DIVERGENCE_MAX_STEP_FRACTION: float = float(
    os.getenv("KIS_MINUTE_DIVERGENCE_MAX_STEP", "0.06")
)


def _resolve_minute_bars(
    minute_candidates: dict[datetime, dict[tuple[float, float, float, float], int]],
) -> tuple[dict[datetime, tuple[float, float, float, float, int]], int]:
    """Resolve one internally-consistent OHLCV bar per minute, dropping phantoms."""

    def _midpoint(ohlc: tuple[float, float, float, float]) -> float:
        return (ohlc[0] + ohlc[3]) / 2.0

    def _continuous(a: float, b: float) -> bool:
        """True if midpoint ``b`` is within the continuity tolerance of ``a``."""
        if abs(a) <= 1e-9:
            return abs(b - a) <= 1e-9
        return abs(b - a) / abs(a) <= _DIVERGENCE_MAX_STEP_FRACTION

    minutes = sorted(minute_candidates.keys())

    candidate_mids: list[tuple[int, float]] = [
        (idx, _midpoint(ohlc))
        for idx, minute_dt in enumerate(minutes)
        for ohlc in minute_candidates[minute_dt]
    ]

    anchor: float | None = None
    best_key: tuple[int, int, int] | None = None
    for idx0, mid0 in candidate_mids:
        supporting = {idx1 for idx1, mid1 in candidate_mids if _continuous(mid0, mid1)}
        span = max(supporting) - min(supporting)
        key = (-len(supporting), -span, idx0)
        if best_key is None or key < best_key:
            best_key = key
            anchor = mid0
    if anchor is None and minutes:
        ohlc = min(minute_candidates[minutes[0]], key=lambda k: k[3])
        anchor = _midpoint(ohlc)

    minute_bars: dict[datetime, tuple[float, float, float, float, int]] = {}
    dropped = 0
    for minute_dt in minutes:
        items = list(minute_candidates[minute_dt].items())
        if len(items) == 1:
            ohlc, vol = items[0]
        else:
            ohlc, vol = min(
                items,
                key=lambda kv: (abs(_midpoint(kv[0]) - anchor), kv[0][3]),
            )

        midpoint = _midpoint(ohlc)
        if anchor is not None and abs(anchor) > 1e-9:
            step = abs(midpoint - anchor) / abs(anchor)
            if step > _DIVERGENCE_MAX_STEP_FRACTION:
                dropped += 1
                logger.debug(
                    "parse_ohlcv: dropped phantom-only minute %s "
                    "(midpoint=%.2f, anchor=%.2f, step=%.1f%%)",
                    minute_dt.isoformat(),
                    midpoint,
                    anchor,
                    step * 100.0,
                )
                continue

        o, h, low, c = ohlc
        minute_bars[minute_dt] = (o, max(h, o, c), min(low, o, c), c, int(vol))
        anchor = c
    return minute_bars, dropped


def parse_ohlcv(code: str, date_str: str, data: dict) -> list[tuple]:
    """
    Parse API response to OHLCV rows.

    Args:
        code: Futures code
        date_str: Date string (YYYYMMDD)
        data: API response

    Returns:
        List of tuples (code, datetime, open, high, low, close, volume)
    """
    tick_rows: list[tuple[datetime, float, float, float, float, int]] = []
    output = (
        data.get("output2", []) or data.get("output1", []) or data.get("output", [])
    )

    if not output:
        return []

    for item in output:
        if not isinstance(item, dict):
            continue

        try:
            time_str = _first_present(
                item,
                ["stck_cntg_hour", "futs_cntg_hour", "cntg_hour", "bsop_hour", "hour"],
                default="",
            )
            if not time_str:
                continue

            if len(time_str) == 4:
                time_str = f"{time_str}00"

            dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")

            o = _first_present(
                item,
                ["futs_oprc", "open", "stck_oprc", "bstp_nmix_oprc", "oprc"],
                0,
            )
            h = _first_present(
                item,
                ["futs_hgpr", "high", "stck_hgpr", "bstp_nmix_hgpr", "hgpr"],
                0,
            )
            low = _first_present(
                item,
                ["futs_lwpr", "low", "stck_lwpr", "bstp_nmix_lwpr", "lwpr"],
                0,
            )
            c = _first_present(
                item,
                [
                    "futs_prpr",
                    "close",
                    "stck_prpr",
                    "stck_clpr",
                    "bstp_nmix_prpr",
                    "prpr",
                ],
                0,
            )
            v = _first_present(item, ["cntg_vol", "acml_vol", "volume"], 0)

            tick_rows.append(
                (
                    dt,
                    float(o or 0),
                    float(h or 0),
                    float(low or 0),
                    float(c or 0),
                    int(v or 0),
                )
            )
        except (ValueError, TypeError):
            continue

    if not tick_rows:
        return []

    tick_rows.sort(key=lambda row: row[0])
    minute_candidates: dict[datetime, dict[tuple[float, float, float, float], int]] = {}
    for dt, o, h, low, c, v in tick_rows:
        minute_dt = dt.replace(second=0, microsecond=0)
        ohlc = (float(o), float(h), float(low), float(c))
        candidates = minute_candidates.setdefault(minute_dt, {})
        candidates[ohlc] = max(candidates.get(ohlc, 0), int(v))

    minute_bars, phantom_dropped = _resolve_minute_bars(minute_candidates)
    if phantom_dropped:
        logger.debug(
            "parse_ohlcv(%s, %s): dropped %d phantom-only minute(s)",
            code,
            date_str,
            phantom_dropped,
        )

    min_ingest_volume = int(os.getenv("KIS_MINUTE_BAR_MIN_VOLUME", "10"))

    rows: list[tuple] = []
    dropped = 0
    for minute_dt in sorted(minute_bars.keys()):
        o, h, low, c, v = minute_bars[minute_dt]
        if int(v) < min_ingest_volume:
            dropped += 1
            continue
        rows.append((code, minute_dt, float(o), float(h), float(low), float(c), int(v)))
    if dropped > 0:
        logger.debug(
            "parse_ohlcv(%s, %s): dropped %d phantom bars (volume < %d)",
            code,
            date_str,
            dropped,
            min_ingest_volume,
        )
    return rows
