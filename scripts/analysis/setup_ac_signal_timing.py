#!/usr/bin/env python3
"""Setup A/C intra-session signal-timing monitor.

Purpose
-------
After the indicator-cache staleness fix (PR #252), verify that the futures
orchestrator's Setup A/C path actually generates signals — and, critically,
generates them *throughout* the session rather than only before the old
~4-hour cache-freeze point.

Why a log monitor (not kospi.signals_all)
-----------------------------------------
``kospi.signals_all`` is written by the Phase 5 ``risk_filter`` systemd
service, which is NOT running under the current ``sts rl paper`` orchestrator
deployment — so it has been empty since cutover regardless of orchestrator
behaviour. The orchestrator's own ``strategy_manager`` log line is the
authoritative, deployment-correct source:

    ... services.trading.strategy_manager - INFO -
        Signal cycle: <N> signals from [rl_mppo, setup_a_gap_reversion,
                                        setup_c_event_reaction]

rl_mppo is shadow-mode (emits 0 Signals by design — see master plan v4.11),
so a non-zero cycle count is effectively Setup A/C activity.

Verdict
-------
- FAIL  : zero signals all session → Setup A/C defect persists despite #252
          (cache fix necessary-but-not-sufficient; needs separate root-cause).
- WARN  : signals in the morning window but none after 13:00 KST → the
          cache-freeze signature persists (fix not effective / regressed).
- PASS  : non-zero signals present in the afternoon window too → #252 took.

Output: Telegram briefing + JSON archive under
``reports/setup_ac_timing/YYYY-MM-DD.json``. Exit 0 = PASS, 1 = WARN/FAIL,
2 = script error (e.g. log missing).

Designed for cron; see scripts/cron/setup_ac_signal_timing.sh.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_REPORTS_DIR = _REPO_ROOT / "reports" / "setup_ac_timing"
_LOG_DIR = _REPO_ROOT / "logs"

# strategy_manager line — server logs in KST local time.
#   2026-05-14 09:00:12,913 - services.trading.strategy_manager - INFO -
#       Signal cycle: 0 signals from [rl_mppo, ...]
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ - "
    r"services\.trading\.strategy_manager - INFO - "
    r"Signal cycle: (?P<n>\d+) signals from"
)

# Korean futures day session is 09:00–15:45 KST. The old cache freeze bit
# ~4h into the session (≈13:00 KST for an 09:00 start); split there.
_AFTERNOON_START_HOUR = 13
_SESSION_END_HOUR = 16  # ignore anything past 16:00 (post-close noise)


@dataclass
class TimingReport:
    trading_date: str
    log_path: str
    total_cycles: int = 0
    nonzero_cycles: int = 0
    total_signals: int = 0
    morning_signals: int = 0      # 09:00–12:59 KST
    afternoon_signals: int = 0    # 13:00–15:59 KST
    by_hour: dict[str, int] = field(default_factory=dict)  # "HH" -> signal sum
    verdict: str = "FAIL"
    detail: str = ""


def _parse_log(path: Path, trading_date: date) -> TimingReport:
    rep = TimingReport(trading_date=trading_date.isoformat(), log_path=str(path))
    if not path.exists():
        rep.verdict = "FAIL"
        rep.detail = f"log not found: {path.name} (orchestrator did not run?)"
        return rep

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        ts = datetime.strptime(m.group("ts"), "%Y-%m-%d %H:%M:%S")
        if ts.date() != trading_date:
            continue
        hour = ts.hour
        if hour >= _SESSION_END_HOUR or hour < 9:
            continue
        n = int(m.group("n"))
        rep.total_cycles += 1
        rep.by_hour[f"{hour:02d}"] = rep.by_hour.get(f"{hour:02d}", 0) + n
        if n > 0:
            rep.nonzero_cycles += 1
            rep.total_signals += n
            if hour >= _AFTERNOON_START_HOUR:
                rep.afternoon_signals += n
            else:
                rep.morning_signals += n

    if rep.total_cycles == 0:
        rep.verdict = "FAIL"
        rep.detail = (
            "No 'Signal cycle' lines for the trading date — orchestrator "
            "may not have run or strategy_manager logging changed."
        )
    elif rep.total_signals == 0:
        rep.verdict = "FAIL"
        rep.detail = (
            f"{rep.total_cycles} cycles, ALL zero-signal. Setup A/C generated "
            "no signals all session — cache fix #252 necessary but NOT "
            "sufficient; a separate Setup A/C defect persists."
        )
    elif rep.afternoon_signals == 0 and rep.morning_signals > 0:
        rep.verdict = "WARN"
        rep.detail = (
            f"Morning signals={rep.morning_signals} but afternoon=0 — the "
            "~4h cache-freeze signature persists (PR #252 not effective or "
            "regressed)."
        )
    else:
        rep.verdict = "PASS"
        rep.detail = (
            f"Signals throughout: morning={rep.morning_signals}, "
            f"afternoon={rep.afternoon_signals} ({rep.nonzero_cycles}/"
            f"{rep.total_cycles} cycles non-zero). Cache fix #252 effective."
        )
    return rep


def _format_telegram(rep: TimingReport) -> str:
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(rep.verdict, "❓")
    lines = [
        f"{icon} Setup A/C signal timing — {rep.trading_date}",
        f"verdict: {rep.verdict}",
        f"signals: total={rep.total_signals} "
        f"(AM={rep.morning_signals} / PM={rep.afternoon_signals})",
        f"cycles: {rep.nonzero_cycles}/{rep.total_cycles} non-zero",
        rep.detail,
    ]
    if rep.by_hour:
        hourly = " ".join(
            f"{h}:{rep.by_hour[h]}" for h in sorted(rep.by_hour)
        )
        lines.append(f"by hour (KST): {hourly}")
    return "\n".join(lines)


def _write_archive(rep: TimingReport) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = _REPORTS_DIR / f"{rep.trading_date}.json"
    out.write_text(json.dumps(asdict(rep), indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trading-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        help="KST trading date (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=None,
        help="Override orchestrator log path (default: "
        "logs/rl_paper_YYYYMMDD.log for the trading date).",
    )
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    td: date = args.trading_date
    log_path: Path = args.log_path or (
        _LOG_DIR / f"rl_paper_{td.strftime('%Y%m%d')}.log"
    )

    try:
        rep = _parse_log(log_path, td)
        _write_archive(rep)
        msg = _format_telegram(rep)
        print(msg)
        if not args.no_telegram:
            try:
                from shared.notification.telegram import notifier_for_domain

                notifier = notifier_for_domain("briefing")
                if notifier is not None:
                    notifier.send_message(msg)
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] telegram send failed: {exc}", file=sys.stderr)
        return 0 if rep.verdict == "PASS" else 1
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
