#!/usr/bin/env python3
"""Setup A/C paper-observation digest.

Generates a cumulative validation-accumulation digest for the futures
Setup A (gap_reversion) and Setup C (event_reaction) strategies.  The
purpose is to track whether enough paper trades have accumulated for a
statistically meaningful re-validation holdout backtest.

The digest surfaces three data sources:
  1. RuntimeLedger trades table — closed futures trades since
     ``observation_start_date``.
  2. Redis ``trading:futures:setup_eval`` hash — most-recent rejection
     reasons published by setup adapters (PR #483 observability).
  3. Early-warning flags derived from the above.

Output
------
- Telegram BRIEFING channel message (appended to or standalone).
- JSON archive under ``reports/setup_ac_paper_obs/YYYY-MM-DD.json``.

Scheduling
----------
Designed to be called by the compose scheduler service (supercronic).
Two entry points are registered in ``deploy/scheduler.crontab``:
  - Daily market-close digest: 15:32 KST Mon-Fri (runs just after
    llm_market_close_briefing so it arrives as a follow-on Telegram
    message in the briefing channel).
  - Weekly rollup: Fridays 16:30 KST — emits the same digest with a
    ``is_weekly=True`` flag that prepends a summary banner.

Configuration (config/monitoring.yaml)
---------------------------------------
  setup_ac_paper_observation:
    validation_n_threshold: 30          # trades/setup for re-validation
    observation_start_date: "2026-06-21" # date deploy was restored
    fast_stopout_minutes: 30            # flag trades closed within N min
    catastrophic_loss_pct: -3.0        # flag individual trades below this

Usage
-----
  python -m scripts.analysis.setup_ac_paper_observation
  python -m scripts.analysis.setup_ac_paper_observation --weekly
  python -m scripts.analysis.setup_ac_paper_observation --no-telegram
  python -m scripts.analysis.setup_ac_paper_observation --since 2026-06-21

Cron: 32 15 * * 1-5 and 30 16 * * 5  (see deploy/scheduler.crontab)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_REPORTS_DIR = _REPO_ROOT / "reports" / "setup_ac_paper_obs"

# Canonical setup names matching setup_adapters.py registration.
SETUP_A = "setup_a_gap_reversion"
SETUP_C = "setup_c_event_reaction"
SETUPS = (SETUP_A, SETUP_C)

# Redis key published by _publish_setup_eval (PR #483).
SETUP_EVAL_KEY = "trading:futures:setup_eval"

# Defaults — overridden by monitoring.yaml if present.
_DEFAULT_VALIDATION_N = 30
_DEFAULT_START_DATE = date(2026, 6, 21)  # restored-config deploy
_DEFAULT_FAST_STOPOUT_MINUTES = 30
_DEFAULT_CATASTROPHIC_LOSS_PCT = -3.0


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_obs_config() -> dict[str, Any]:
    """Read setup_ac_paper_observation section from config/monitoring.yaml.

    Returns sensible defaults when the section or file is absent so the
    script is runnable without a full config stack.
    """
    try:
        from shared.config.loader import ConfigLoader

        raw = ConfigLoader.load("monitoring.yaml")
        return (raw or {}).get("setup_ac_paper_observation", {}) or {}
    except Exception:  # noqa: BLE001 — config errors must not break digest
        pass
    return {}


def _get_cfg(cfg: dict[str, Any], key: str, default: Any) -> Any:
    return cfg.get(key, default)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SetupStats:
    """Per-setup cumulative paper-observation statistics."""

    name: str
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    total_pnl: float = 0.0
    pnl_values: list[float] = field(default_factory=list)
    hold_seconds_values: list[float] = field(default_factory=list)
    exit_reason_counts: dict[str, int] = field(default_factory=dict)
    fast_stopout_count: int = 0     # closed within fast_stopout_minutes
    catastrophic_loss_count: int = 0  # pnl_pct below catastrophic threshold
    last_entry_kst: str | None = None
    last_exit_kst: str | None = None

    @property
    def win_rate(self) -> float:
        if self.trade_count == 0:
            return 0.0
        return self.win_count / self.trade_count * 100.0

    @property
    def avg_pnl(self) -> float:
        if not self.pnl_values:
            return 0.0
        return sum(self.pnl_values) / len(self.pnl_values)

    @property
    def median_pnl(self) -> float:
        if not self.pnl_values:
            return 0.0
        return median(self.pnl_values)

    @property
    def avg_hold_minutes(self) -> float:
        if not self.hold_seconds_values:
            return 0.0
        return sum(self.hold_seconds_values) / len(self.hold_seconds_values) / 60.0


@dataclass
class SetupEvalSnapshot:
    """Latest setup_eval state from Redis for one setup."""

    name: str
    outcome: str = "unknown"  # "fired" | "reject" | "unknown"
    reason: str = ""
    ts_kst: str = ""


@dataclass
class ObservationDigest:
    """Full daily/weekly observation digest."""

    generated_kst: str
    observation_start: str
    observation_days: int
    is_weekly: bool
    validation_n_threshold: int
    setup_stats: list[SetupStats] = field(default_factory=list)
    eval_snapshots: list[SetupEvalSnapshot] = field(default_factory=list)
    early_warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_trades_from_ledger(since: date) -> list[dict[str, Any]]:
    """Query futures trades from RuntimeLedger since *since* (inclusive)."""
    from shared.storage import SQLiteRuntimeLedger, StorageConfig

    storage_config = StorageConfig.load_or_default()
    ledger = SQLiteRuntimeLedger(storage_config.runtime_storage.sqlite)
    try:
        rows = ledger.query_trades(
            {
                "asset_class": "futures",
                "start": datetime.combine(since, datetime.min.time()).isoformat(),
                "limit": 0,
            }
        )
    finally:
        ledger.close()
    return rows


def _load_setup_eval_from_redis() -> dict[str, dict[str, str]]:
    """Read trading:futures:setup_eval hash from Redis DB 1.

    Returns a mapping of setup_name -> {outcome, reason, ts_kst}.
    """
    result: dict[str, dict[str, str]] = {}
    try:
        import redis as redis_lib

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
        r = redis_lib.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        raw = r.hgetall(SETUP_EVAL_KEY)
        for field_name, value in raw.items():
            try:
                result[field_name] = json.loads(value)
            except Exception:  # noqa: BLE001
                result[field_name] = {"outcome": "unknown", "reason": str(value), "ts_kst": ""}
    except Exception:  # noqa: BLE001 — Redis unavailable is non-fatal
        pass
    return result


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _to_kst_str(iso: str) -> str:
    """Convert a UTC or naive ISO timestamp string to a KST ISO string.

    RuntimeLedger writes UTC via _utc_now_iso(); this converts those strings
    to KST before storing in _kst-labelled fields.  Naive strings (no tzinfo)
    are treated as KST (already local), consistent with to_kst() behaviour.
    """
    from shared.strategy.market_time import to_kst

    try:
        dt = datetime.fromisoformat(iso)
        return to_kst(dt).isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001
        return iso


def _compute_setup_stats(
    trades: list[dict[str, Any]],
    fast_stopout_minutes: int,
    catastrophic_loss_pct: float,
) -> dict[str, SetupStats]:
    """Compute per-setup statistics from a list of closed trade rows."""
    stats: dict[str, SetupStats] = {
        SETUP_A: SetupStats(name=SETUP_A),
        SETUP_C: SetupStats(name=SETUP_C),
    }

    for row in trades:
        strategy = str(row.get("strategy") or "")
        if strategy not in stats:
            continue  # ignore non-Setup-A/C trades

        s = stats[strategy]
        pnl = float(row.get("pnl") or 0.0)
        pnl_pct = float(row.get("pnl_pct") or 0.0)
        hold_seconds = float(row.get("hold_seconds") or 0.0)
        exit_reason = str(row.get("exit_reason") or "unknown")

        s.trade_count += 1
        s.total_pnl += pnl
        s.pnl_values.append(pnl)
        s.hold_seconds_values.append(hold_seconds)

        if pnl > 0:
            s.win_count += 1
        else:
            s.loss_count += 1

        s.exit_reason_counts[exit_reason] = s.exit_reason_counts.get(exit_reason, 0) + 1

        if hold_seconds > 0 and hold_seconds / 60.0 < fast_stopout_minutes:
            s.fast_stopout_count += 1

        if pnl_pct < catastrophic_loss_pct:
            s.catastrophic_loss_count += 1

        # Track most recent entry/exit times (rows are ordered DESC by exit_time).
        # RuntimeLedger writes UTC via _utc_now_iso(); convert to KST here.
        exit_time = str(row.get("exit_time") or "")
        entry_time = str(row.get("entry_time") or "")
        if exit_time and (s.last_exit_kst is None):
            s.last_exit_kst = _to_kst_str(exit_time)
        if entry_time and (s.last_entry_kst is None):
            s.last_entry_kst = _to_kst_str(entry_time)

    return stats


def _build_eval_snapshots(raw: dict[str, dict[str, str]]) -> list[SetupEvalSnapshot]:
    snapshots: list[SetupEvalSnapshot] = []
    for setup_name in SETUPS:
        entry = raw.get(setup_name, {})
        snapshots.append(
            SetupEvalSnapshot(
                name=setup_name,
                outcome=entry.get("outcome", "unknown"),
                reason=entry.get("reason", ""),
                ts_kst=entry.get("ts_kst", ""),
            )
        )
    return snapshots


def _build_early_warnings(
    stats: dict[str, SetupStats],
    since: date,
    fast_stopout_minutes: int,
    catastrophic_loss_pct: float,
) -> list[str]:
    from shared.strategy.market_time import now_kst

    warnings: list[str] = []
    today = now_kst().date()
    days_observed = max(1, (today - since).days + 1)

    for name, s in stats.items():
        short = name.replace("setup_", "").replace("_gap_reversion", " A").replace("_event_reaction", " C")

        if s.trade_count == 0:
            warnings.append(
                f"{short}: 0 trades over {days_observed} day(s) — "
                "strategy may be suppressed or config issue"
            )

        if s.fast_stopout_count > 0 and s.trade_count > 0:
            fso_ratio = s.fast_stopout_count / s.trade_count
            if fso_ratio > 0.5:
                warnings.append(
                    f"{short}: {s.fast_stopout_count}/{s.trade_count} trades "
                    f"closed within {fast_stopout_minutes} min "
                    f"({fso_ratio:.0%}) — high fast-stopout rate"
                )

        if s.catastrophic_loss_count > 0:
            warnings.append(
                f"{short}: {s.catastrophic_loss_count} trade(s) with "
                f"PnL < {catastrophic_loss_pct:.1f}% — review stop config"
            )

    return warnings


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _fmt_pnl(pnl: float) -> str:
    sign = "+" if pnl >= 0 else ""
    return f"{sign}{pnl:,.0f}"


def _fmt_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _n_bar(n: int, threshold: int) -> str:
    """Produce a compact N/threshold progress indicator."""
    filled = min(n, threshold)
    bar = "#" * filled + "." * (threshold - filled)
    pct = min(n / threshold * 100, 100)
    return f"[{bar}] {n}/{threshold} ({pct:.0f}%)"


def _format_telegram(digest: ObservationDigest) -> str:
    """Format the observation digest as a Telegram HTML message."""
    lines: list[str] = []

    if digest.is_weekly:
        lines.append("<b>Setup A/C Paper Observation — Weekly Rollup</b>")
    else:
        lines.append("<b>Setup A/C Paper Observation</b>")

    lines.append(f"Observation period: {digest.observation_start} to {digest.generated_kst[:10]}"
                 f" ({digest.observation_days} day(s))")
    lines.append("━" * 22)

    for s in digest.setup_stats:
        short = (
            "Setup A (gap_reversion)" if s.name == SETUP_A
            else "Setup C (event_reaction)"
        )
        n = s.trade_count
        threshold = digest.validation_n_threshold
        progress_bar = _n_bar(n, threshold)
        n_status = (
            "READY FOR REVALIDATION" if n >= threshold
            else f"N={n}/{threshold} — not yet validatable"
        )

        lines.append(f"\n<b>{short}</b>")
        lines.append(f"  Trades: {n}  |  {n_status}")
        lines.append(f"  Progress: {progress_bar}")

        if n > 0:
            lines.append(
                f"  Win rate: {s.win_rate:.1f}%  |  "
                f"Avg PnL: {_fmt_pnl(s.avg_pnl)} / "
                f"Median: {_fmt_pnl(s.median_pnl)}"
            )
            lines.append(f"  Total PnL: {_fmt_pnl(s.total_pnl)}")
            lines.append(f"  Avg hold: {s.avg_hold_minutes:.1f} min")
            if s.exit_reason_counts:
                reason_parts = ", ".join(
                    f"{k}:{v}"
                    for k, v in sorted(
                        s.exit_reason_counts.items(), key=lambda kv: -kv[1]
                    )
                )
                lines.append(f"  Exits: {reason_parts}")
        else:
            lines.append("  No trades recorded yet")

    # Latest eval state
    if any(es.outcome != "unknown" for es in digest.eval_snapshots):
        lines.append("\n<b>Latest setup eval (Redis)</b>")
        for es in digest.eval_snapshots:
            short = "Setup A" if es.name == SETUP_A else "Setup C"
            ts_label = f" @ {es.ts_kst[:16]}" if es.ts_kst else ""
            lines.append(f"  {short}: {es.outcome} / {es.reason}{ts_label}")

    # Early warnings
    if digest.early_warnings:
        lines.append("\n<b>Early warnings</b>")
        for w in digest.early_warnings:
            lines.append(f"  WARN: {w}")

    lines.append("")
    lines.append("━" * 22)
    revalidation_total = sum(s.trade_count for s in digest.setup_stats)
    lines.append(
        f"<i>Revalidation gate: {digest.validation_n_threshold} trades/setup "
        f"for holdout backtest. Combined: {revalidation_total} trades accumulated.</i>"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------

def _write_archive(digest: ObservationDigest, report_date: date) -> Path:
    """Write digest as JSON to reports/setup_ac_paper_obs/YYYY-MM-DD.json."""
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "_weekly" if digest.is_weekly else ""
    out = _REPORTS_DIR / f"{report_date.isoformat()}{suffix}.json"

    # Convert to JSON-serializable form — strip list fields from stats for size.
    raw_stats = []
    for s in digest.setup_stats:
        d = asdict(s)
        d.pop("pnl_values", None)
        d.pop("hold_seconds_values", None)
        raw_stats.append(d)

    payload = {
        "generated_kst": digest.generated_kst,
        "observation_start": digest.observation_start,
        "observation_days": digest.observation_days,
        "is_weekly": digest.is_weekly,
        "validation_n_threshold": digest.validation_n_threshold,
        "setup_stats": raw_stats,
        "eval_snapshots": [asdict(es) for es in digest.eval_snapshots],
        "early_warnings": digest.early_warnings,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_digest(
    since: date,
    *,
    is_weekly: bool = False,
    validation_n_threshold: int = _DEFAULT_VALIDATION_N,
    fast_stopout_minutes: int = _DEFAULT_FAST_STOPOUT_MINUTES,
    catastrophic_loss_pct: float = _DEFAULT_CATASTROPHIC_LOSS_PCT,
    redis_eval: dict[str, dict[str, str]] | None = None,
    trade_rows: list[dict[str, Any]] | None = None,
) -> ObservationDigest:
    """Build an :class:`ObservationDigest` from live sources.

    Parameters *redis_eval* and *trade_rows* are injection points for testing.
    """
    from shared.strategy.market_time import now_kst

    now = now_kst()
    days_observed = max(1, (now.date() - since).days + 1)

    trades = trade_rows if trade_rows is not None else _load_trades_from_ledger(since)
    raw_eval = redis_eval if redis_eval is not None else _load_setup_eval_from_redis()

    stats_map = _compute_setup_stats(trades, fast_stopout_minutes, catastrophic_loss_pct)
    eval_snapshots = _build_eval_snapshots(raw_eval)
    warnings = _build_early_warnings(stats_map, since, fast_stopout_minutes, catastrophic_loss_pct)

    return ObservationDigest(
        generated_kst=now.isoformat(timespec="seconds"),
        observation_start=since.isoformat(),
        observation_days=days_observed,
        is_weekly=is_weekly,
        validation_n_threshold=validation_n_threshold,
        setup_stats=list(stats_map.values()),
        eval_snapshots=eval_snapshots,
        early_warnings=warnings,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--since",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Observation start date YYYY-MM-DD (default: config or 2026-06-21)",
    )
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Emit a weekly rollup digest (prepends summary banner)",
    )
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram send")
    args = parser.parse_args()

    cfg = _load_obs_config()
    validation_n = int(_get_cfg(cfg, "validation_n_threshold", _DEFAULT_VALIDATION_N))
    fast_stopout = int(_get_cfg(cfg, "fast_stopout_minutes", _DEFAULT_FAST_STOPOUT_MINUTES))
    catastrophic = float(_get_cfg(cfg, "catastrophic_loss_pct", _DEFAULT_CATASTROPHIC_LOSS_PCT))

    if args.since is not None:
        since = args.since
    elif "observation_start_date" in cfg:
        since = datetime.strptime(str(cfg["observation_start_date"]), "%Y-%m-%d").date()
    else:
        since = _DEFAULT_START_DATE

    try:
        digest = build_digest(
            since,
            is_weekly=args.weekly,
            validation_n_threshold=validation_n,
            fast_stopout_minutes=fast_stopout,
            catastrophic_loss_pct=catastrophic,
        )
        from shared.strategy.market_time import now_kst as _now_kst

        archive_path = _write_archive(digest, _now_kst().date())
        msg = _format_telegram(digest)
        print(msg)

        if not args.no_telegram:
            try:
                import asyncio

                from shared.notification import notifier_for_domain

                notifier = notifier_for_domain(
                    "briefing",
                    notification_start="06:00",
                    notification_end="23:59",
                    critical_always=True,
                )
                if notifier is not None:
                    asyncio.run(notifier.send_message(msg, is_critical=True))
                else:
                    print("[warn] TELEGRAM_BRIEFING_* not configured; skipped send", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] telegram send failed: {exc}", file=sys.stderr)

        print(f"[info] archive: {archive_path}", file=sys.stderr)
        return 0

    except Exception as exc:  # noqa: BLE001
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
