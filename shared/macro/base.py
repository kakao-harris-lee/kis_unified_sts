"""Macro snapshot dataclass used across sources."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MacroSnapshot:
    ts_ms: int
    session: str  # "overnight_us_close" | "overnight_fx"
    sp500_close: float | None = None
    sp500_change_pct: float | None = None
    nasdaq_close: float | None = None
    nasdaq_change_pct: float | None = None
    eurex_kospi_close: float | None = None
    eurex_kospi_change_pct: float | None = None
    usdkrw: float | None = None
    usdkrw_change_pct: float | None = None
    dxy: float | None = None
    us10y_yield: float | None = None
    vix: float | None = None
    collected_from: list[str] = field(default_factory=list)


# Float fields parsed from the Redis stream payload (collector emits all
# values as strings; "" denotes None — see macro_overnight_collector
# _publish_snapshot).
_FLOAT_FIELDS = (
    "sp500_close",
    "sp500_change_pct",
    "nasdaq_close",
    "nasdaq_change_pct",
    "eurex_kospi_close",
    "eurex_kospi_change_pct",
    "usdkrw",
    "usdkrw_change_pct",
    "dxy",
    "us10y_yield",
    "vix",
)


def _coerce_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def read_latest_macro_snapshot(
    redis_client: Any, stream: str, *, scan: int = 200
) -> MacroSnapshot | None:
    """Read the freshest merged :class:`MacroSnapshot` from the Redis stream.

    The collector interleaves two session kinds on the same stream:

      * ``overnight_us_close`` — once at 06:30 KST; carries sp500/nasdaq/
        vix/dxy/us10y (the equity-gap fields Setup A needs).
      * ``overnight_fx`` — every 15 min; carries only usdkrw.

    A naive "latest entry" read almost always returns an ``overnight_fx``
    row with ``sp500_change_pct=None``, which makes Setup A no-op forever
    (``gap_reversion.py`` returns None when sp500 is absent). So we scan a
    recent window and forward-fill each field with its most-recent non-None
    value — i.e. the true *current overnight macro state* (latest us_close
    equity gaps + latest fx). ``ts_ms``/``session`` reflect the newest
    observation. Inverse of ``macro_overnight_collector._publish_snapshot``.

    Never raises — callers on the trading hot path must degrade gracefully.

    Args:
        redis_client: redis client with ``decode_responses=True``.
        stream: stream key (canonically ``stream:macro.overnight``).
        scan: how many recent entries to merge (default 200 ≈ ≥2 days of
            15-min fx, comfortably covers the day's single us_close row).
    """
    try:
        # newest → oldest
        entries = redis_client.xrevrange(stream, count=scan)
    except Exception as exc:  # noqa: BLE001 — hot path, never propagate
        logger.debug("macro stream read failed (%s): %s", stream, exc)
        return None
    if not entries:
        return None

    merged: dict[str, Any] = {f: None for f in _FLOAT_FIELDS}
    newest_ts_ms: int | None = None
    newest_session = ""
    newest_collected: list[str] = []

    for _entry_id, fields in entries:  # newest first
        try:
            ts_ms = int(fields["ts_ms"])
        except (KeyError, ValueError, TypeError):
            continue
        if newest_ts_ms is None:
            newest_ts_ms = ts_ms
            newest_session = str(fields.get("session", ""))
            raw = fields.get("collected_from_json") or "[]"
            try:
                newest_collected = list(json.loads(raw))
            except (ValueError, TypeError):
                newest_collected = []
        for f in _FLOAT_FIELDS:
            if merged[f] is None:
                merged[f] = _coerce_float(fields.get(f))
        if all(v is not None for v in merged.values()):
            break  # every field filled — stop early

    if newest_ts_ms is None:
        return None
    return MacroSnapshot(
        ts_ms=newest_ts_ms,
        session=newest_session,
        collected_from=newest_collected,
        **merged,
    )
