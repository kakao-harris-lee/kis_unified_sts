"""Track equity computation + unified monthly-MDD stage engine (Phase 3B).

Pure logic shared by :mod:`services.portfolio_monitor.main`, the ops drill
(``scripts/ops/portfolio_mdd_drill.py``) and unit tests. No Redis/SQLite I/O
happens here beyond the injected callables — everything is deterministic and
hermetic-testable.

Equity source (roadmap §5.5 decision):

``equity(track) = capital_base(track)                     # config/portfolio.yaml
                + Σ realized pnl (ledger trades, track_id) # RuntimeLedger
                + Σ unrealized pnl (open positions)        # trading-state hash``

The capital base anchors the absolute level so restarts / re-runs never shift
the monthly drawdown math; realized PnL comes from the durable RuntimeLedger
``trades`` rows tagged by the Wave-A ``track_id`` migration; unrealized PnL is
best-effort from the same per-position ``unrealized_pnl`` fields the dashboard
risk-exposure board consumes.

Stage semantics (설계서 §7.1):

* ``monthly_mdd_pct = (total - month_peak) / month_peak`` (≤ 0), KST month.
* Thresholds are INCLUSIVE — mdd exactly at a threshold enters that stage.
* Intra-month latch (``circuit_breaker.stage_latch``): once a stage is
  reached it holds for the remainder of the month even if equity recovers;
  a deeper stage still escalates. The latch resets at the KST month boundary.
* Track A is included in the total when provisioned but is never an action
  target — stages only gate Track B/C new entries.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from shared.portfolio.config import (
    TRACK_CORE,
    TRACK_FUTURES,
    TRACK_STOCK,
    MonthlyMddStages,
)

logger = logging.getLogger(__name__)

# --- Stage identifiers (fixed contract with the 3D UI lane + risk filter) ---
STAGE_NORMAL = "NORMAL"
STAGE_REDUCE = "REDUCE"
STAGE_HALT_NEW = "HALT_NEW"
STAGE_FULL_STOP = "FULL_STOP"

#: Escalation order — higher index = more severe. Used by the latch.
STAGE_SEVERITY: dict[str, int] = {
    STAGE_NORMAL: 0,
    STAGE_REDUCE: 1,
    STAGE_HALT_NEW: 2,
    STAGE_FULL_STOP: 3,
}

#: Stages that block new entries outright (enforce mode).
BLOCKING_STAGES: frozenset[str] = frozenset({STAGE_HALT_NEW, STAGE_FULL_STOP})

_TRACK_LABELS: dict[str, str] = {
    TRACK_CORE: "track_a",
    TRACK_STOCK: "track_b",
    TRACK_FUTURES: "track_c",
}


def track_label(track_id: str) -> str:
    """Lowercase component label for a track id (``"B"`` → ``"track_b"``)."""
    return _TRACK_LABELS.get(track_id, f"track_{track_id.lower()}")


# ---------------------------------------------------------------------------
# Per-track equity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrackEquity:
    """One track's equity decomposition plus coverage bookkeeping.

    ``equity`` is ``None`` only when the track has no capital base yet
    (Track A pre-Phase 5). Component failures degrade to the safest
    available number instead of dropping the track — a sudden fake equity
    cliff must never trip the breaker.
    """

    track_id: str
    equity: float | None
    capital_base: float | None
    realized_pnl: float | None
    unrealized_pnl: float
    missing_components: tuple[str, ...]
    degraded: bool


def _sum_realized_pnl(ledger: Any, track_id: str) -> float:
    """Cumulative realized PnL for a track from RuntimeLedger trades.

    ``limit: 0`` disables the query LIMIT so the sum covers the full track
    history. Rows without a pnl value are skipped.
    """
    total = 0.0
    for row in ledger.query_trades({"track_id": track_id, "limit": 0}):
        pnl = row.get("pnl")
        if pnl is None:
            continue
        try:
            total += float(pnl)
        except (TypeError, ValueError):
            continue
    return total


def _sum_unrealized_pnl(positions: Sequence[Mapping[str, Any]]) -> float:
    total = 0.0
    for position in positions:
        value = position.get("unrealized_pnl")
        if value is None:
            continue
        try:
            total += float(value)
        except (TypeError, ValueError):
            continue
    return total


def compute_track_equity(
    *,
    track_id: str,
    capital_base: float | None,
    ledger: Any,
    positions_provider: Callable[[], Sequence[Mapping[str, Any]]] | None = None,
    fallback_equity: float | None = None,
) -> TrackEquity:
    """Compute one track's equity with fail-safe degradation.

    Args:
        track_id: Portfolio track id (``"A"``/``"B"``/``"C"``).
        capital_base: Absolute capital anchor from ``config/portfolio.yaml``;
            ``None`` means the track is not provisioned yet → equity ``None``
            with the track recorded as a missing component (not degraded —
            expected pre-Phase 5 state).
        ledger: RuntimeLedger with ``query_trades`` (track_id filter).
        positions_provider: Zero-arg callable returning open-position dicts
            carrying ``unrealized_pnl``. ``None`` → unrealized 0 (tracks
            without a live positions source, e.g. Track A).
        fallback_equity: Last known equity (previous daily row). Used when
            the realized-PnL query fails so the total never cliff-drops.
    """
    label = track_label(track_id)
    if capital_base is None:
        return TrackEquity(
            track_id=track_id,
            equity=None,
            capital_base=None,
            realized_pnl=None,
            unrealized_pnl=0.0,
            missing_components=(label,),
            degraded=False,
        )

    missing: list[str] = []
    degraded = False

    realized: float | None
    try:
        realized = _sum_realized_pnl(ledger, track_id)
    except Exception as exc:  # noqa: BLE001 — a broken ledger must not kill the run
        logger.warning("%s realized-pnl query failed: %s", label, exc)
        realized = None
        missing.append(f"{label}_realized")
        degraded = True

    unrealized = 0.0
    if positions_provider is not None:
        try:
            unrealized = _sum_unrealized_pnl(positions_provider())
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s unrealized-pnl read failed: %s", label, exc)
            unrealized = 0.0
            missing.append(f"{label}_unrealized")
            degraded = True

    if realized is None:
        # Realized history unavailable: hold the last known equity (or the
        # capital base on a cold start) rather than fabricating a drawdown.
        equity = fallback_equity if fallback_equity is not None else capital_base
    else:
        equity = capital_base + realized + unrealized

    return TrackEquity(
        track_id=track_id,
        equity=equity,
        capital_base=capital_base,
        realized_pnl=realized,
        unrealized_pnl=unrealized,
        missing_components=tuple(missing),
        degraded=degraded,
    )


# ---------------------------------------------------------------------------
# Monthly MDD + stage evaluation
# ---------------------------------------------------------------------------


def stage_for_mdd(monthly_mdd_pct: float, stages: MonthlyMddStages) -> str:
    """Map a (≤ 0) monthly drawdown fraction to a breaker stage.

    Thresholds are inclusive: mdd exactly equal to a stage threshold enters
    that stage (e.g. ``-0.05`` → REDUCE with the default config).
    """
    if monthly_mdd_pct <= stages.full_stop.threshold:
        return STAGE_FULL_STOP
    if monthly_mdd_pct <= stages.halt_new.threshold:
        return STAGE_HALT_NEW
    if monthly_mdd_pct <= stages.reduce.threshold:
        return STAGE_REDUCE
    return STAGE_NORMAL


def month_key(day: date) -> str:
    """KST calendar-month key (``YYYY-MM``) for a trade date."""
    return day.strftime("%Y-%m")


@dataclass(frozen=True)
class PortfolioEquitySnapshot:
    """One evaluated daily portfolio snapshot (persisted + published)."""

    trade_date: date
    track_a_equity: float | None
    track_b_equity: float | None
    track_c_equity: float | None
    total_equity: float
    month_start_equity: float
    month_peak_equity: float
    monthly_mdd_pct: float
    raw_stage: str
    stage: str
    prev_stage: str | None
    stage_changed: bool
    latched: bool
    mode: str
    degraded: bool
    missing_components: tuple[str, ...]
    asof_ts: datetime

    @property
    def effective_prev_stage(self) -> str:
        """Previous stage with a NORMAL default for transition semantics."""
        return self.prev_stage or STAGE_NORMAL


def _month_rows(
    history: Sequence[Mapping[str, Any]], trade_date: date
) -> list[Mapping[str, Any]]:
    """Prior rows of the same KST month, strictly before ``trade_date``.

    Excluding today's row keeps same-day re-runs idempotent: the snapshot is
    recomputed from the untouched prior state and upserted over itself.
    """
    key = month_key(trade_date)
    rows = [
        row
        for row in history
        if str(row.get("trade_date", ""))[:7] == key
        and str(row.get("trade_date", "")) < trade_date.isoformat()
    ]
    rows.sort(key=lambda row: str(row.get("trade_date", "")))
    return rows


def evaluate_snapshot(
    *,
    trade_date: date,
    tracks: Mapping[str, TrackEquity],
    month_history: Sequence[Mapping[str, Any]],
    stages: MonthlyMddStages,
    stage_latch: bool,
    mode: str,
    asof_ts: datetime,
) -> PortfolioEquitySnapshot:
    """Fold track equities + prior month rows into today's snapshot.

    Args:
        trade_date: KST trade date being evaluated.
        tracks: Track id → :class:`TrackEquity` (A optional/None allowed).
        month_history: Previously stored ``portfolio_equity_daily`` rows
            (any range; filtered to the current KST month, before today).
        stages: Monthly MDD stage thresholds.
        stage_latch: Intra-month latch on/off (config).
        mode: Breaker mode (off | shadow | enforce) — carried through.
        asof_ts: KST-naive evaluation timestamp.
    """

    def _equity(track_id: str) -> float | None:
        track = tracks.get(track_id)
        return track.equity if track is not None else None

    available = [track.equity for track in tracks.values() if track.equity is not None]
    total = float(sum(available))

    missing: list[str] = []
    degraded = False
    for track in tracks.values():
        missing.extend(track.missing_components)
        degraded = degraded or track.degraded

    prior = _month_rows(month_history, trade_date)
    if prior:
        first, last = prior[0], prior[-1]
        month_start = float(first.get("month_start_equity") or 0.0)
        prev_peak = float(last.get("month_peak_equity") or 0.0)
        month_peak = max(prev_peak, total)
        prev_stage_raw = str(last.get("stage") or "") or None
        prev_stage = prev_stage_raw if prev_stage_raw in STAGE_SEVERITY else None
    else:
        month_start = total
        month_peak = total
        prev_stage = None

    monthly_mdd_pct = (total - month_peak) / month_peak if month_peak > 0 else 0.0

    raw_stage = stage_for_mdd(monthly_mdd_pct, stages)
    stage = raw_stage
    latched = False
    if (
        stage_latch
        and prev_stage is not None
        and STAGE_SEVERITY[prev_stage] > STAGE_SEVERITY[raw_stage]
    ):
        stage = prev_stage
        latched = True

    stage_changed = stage != (prev_stage or STAGE_NORMAL)

    return PortfolioEquitySnapshot(
        trade_date=trade_date,
        track_a_equity=_equity(TRACK_CORE),
        track_b_equity=_equity(TRACK_STOCK),
        track_c_equity=_equity(TRACK_FUTURES),
        total_equity=total,
        month_start_equity=month_start,
        month_peak_equity=month_peak,
        monthly_mdd_pct=monthly_mdd_pct,
        raw_stage=raw_stage,
        stage=stage,
        prev_stage=prev_stage,
        stage_changed=stage_changed,
        latched=latched,
        mode=mode,
        degraded=degraded,
        missing_components=tuple(missing),
        asof_ts=asof_ts,
    )
