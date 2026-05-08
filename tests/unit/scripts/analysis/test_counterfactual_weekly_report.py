"""Unit tests for scripts/analysis/counterfactual_weekly_report.py.

Test coverage
-------------
1. ``_resolve_window`` returns previous ISO week (Mon–Sun) regardless of
   what weekday "today" falls on.
2. ``_archive_path`` produces stable ``YYYY-WNN`` filenames.
3. ``_format_telegram_message`` survives empty-window inputs without crash.
4. ``_format_telegram_message`` length stays well under Telegram's 4096-char
   limit on a representative populated report.
5. ``_write_archive`` round-trips through JSON cleanly.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

# Pytest's test collection creates a `tests.unit.scripts.analysis` package
# which masks the real `scripts.analysis` namespace package.  Mirror the
# importlib pattern used by test_setup_vs_rl_shadow_counterfactual.py to
# load both modules by file path instead.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load(name: str, relpath: str):
    path = _REPO_ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load the dataclass module first so the wrapper's `from scripts.analysis.X
# import ...` (executed at top level in the wrapper) can reuse the same
# instances by aliasing.
_cf_script = _load(
    "cf_script_for_weekly",
    "scripts/analysis/setup_vs_rl_shadow_counterfactual.py",
)
sys.modules["scripts.analysis.setup_vs_rl_shadow_counterfactual"] = _cf_script
# `scripts` and `scripts.analysis` may not exist yet under pytest's rootdir;
# ModuleType-based stubs let the wrapper's `from scripts.analysis...` import
# resolve to the file we already loaded above.
import types  # noqa: E402

if "scripts" not in sys.modules:
    sys.modules["scripts"] = types.ModuleType("scripts")
if "scripts.analysis" not in sys.modules:
    sys.modules["scripts.analysis"] = types.ModuleType("scripts.analysis")
sys.modules["scripts.analysis"].setup_vs_rl_shadow_counterfactual = _cf_script

_wrapper = _load(
    "cf_weekly_under_test", "scripts/analysis/counterfactual_weekly_report.py"
)

_archive_path = _wrapper._archive_path
_format_telegram_message = _wrapper._format_telegram_message
_resolve_window = _wrapper._resolve_window
_write_archive = _wrapper._write_archive

AgreementMatrix = _cf_script.AgreementMatrix
AggregateStat = _cf_script.AggregateStat
CounterfactualReport = _cf_script.CounterfactualReport
PerDayStat = _cf_script.PerDayStat
Phase4GateProgress = _cf_script.Phase4GateProgress

# ---------------------------------------------------------------------------
# _resolve_window
# ---------------------------------------------------------------------------


def test_resolve_window_on_monday():
    """Mon 07:00 cron firing → previous week's Mon-Sun."""
    today = date(2026, 5, 11)  # Monday (week 20)
    start, end = _resolve_window(today)
    assert start == date(2026, 5, 4)   # prev Mon
    assert end == date(2026, 5, 10)    # prev Sun
    assert (end - start).days == 6


def test_resolve_window_on_sunday():
    """Operator running ad-hoc on Sunday gets last fully-closed week."""
    today = date(2026, 5, 10)  # Sunday (still in week 19)
    start, end = _resolve_window(today)
    assert start == date(2026, 4, 27)
    assert end == date(2026, 5, 3)


def test_resolve_window_on_wednesday():
    today = date(2026, 5, 6)  # Wednesday
    start, end = _resolve_window(today)
    assert start == date(2026, 4, 27)
    assert end == date(2026, 5, 3)


def test_resolve_window_default_uses_today_utc():
    """Default branch (today=None) doesn't crash and returns Mon-Sun pair."""
    start, end = _resolve_window()
    assert end > start
    assert (end - start).days == 6
    assert start.weekday() == 0  # Monday
    assert end.weekday() == 6    # Sunday


# ---------------------------------------------------------------------------
# _archive_path
# ---------------------------------------------------------------------------


def test_archive_path_format():
    """Filename format: YYYY-WNN.json with zero-padded week number."""
    p = _archive_path(date(2026, 1, 5))   # ISO 2026-W02
    assert p.name == "2026-W02.json"


def test_archive_path_uses_iso_year_for_week_53_edge():
    """ISO year may differ from calendar year on year boundaries."""
    # 2025-12-29 is a Monday → ISO week 1 of 2026, NOT week 53 of 2025
    p = _archive_path(date(2025, 12, 29))
    assert p.name == "2026-W01.json"


# ---------------------------------------------------------------------------
# _format_telegram_message
# ---------------------------------------------------------------------------


def _empty_aggregate() -> AggregateStat:
    return AggregateStat(
        trade_count=0,
        win_count=0,
        loss_count=0,
        open_count=0,
        gross_pnl_krw=0.0,
        avg_pnl_krw=0.0,
        win_rate=0.0,
        max_drawdown_krw=0.0,
        eod_estimated_count=0,
    )


def _empty_report() -> CounterfactualReport:
    return CounterfactualReport(
        generated_at=datetime.now(UTC).isoformat(),
        start_date="2026-04-27",
        end_date="2026-05-03",
        symbol="101S6000",
        commission_bps=1.0,
        slippage_ticks=1.0,
        multiplier_krw=50_000.0,
        tick_size=0.02,
        min_confidence=0.5,
        rl_shadow=_empty_aggregate(),
        setup_actual=_empty_aggregate(),
        agreement=AgreementMatrix(),
        per_day=[],
        phase4_gate=Phase4GateProgress(
            setup_executed_trades=0,
            setup_target=50,
            setup_gate_met=False,
            rl_shadow_count=0,
            rl_shadow_target=1000,
            rl_shadow_gate_met=False,
        ),
    )


def _populated_report() -> CounterfactualReport:
    report = _empty_report()
    report.rl_shadow = AggregateStat(
        trade_count=12,
        win_count=7,
        loss_count=5,
        open_count=0,
        gross_pnl_krw=480_000.0,
        avg_pnl_krw=40_000.0,
        win_rate=7 / 12,
        max_drawdown_krw=-120_000.0,
        eod_estimated_count=0,
    )
    report.setup_actual = AggregateStat(
        trade_count=8,
        win_count=4,
        loss_count=4,
        open_count=0,
        gross_pnl_krw=120_000.0,
        avg_pnl_krw=15_000.0,
        win_rate=0.5,
        max_drawdown_krw=-90_000.0,
        eod_estimated_count=2,
    )
    report.agreement = AgreementMatrix(
        long_long=4, long_short=1, short_long=0, short_short=2
    )
    report.per_day = [
        PerDayStat(
            date="2026-04-27",
            rl_trades=2,
            rl_pnl_krw=80_000.0,
            setup_trades=1,
            setup_pnl_krw=15_000.0,
            delta_krw=65_000.0,
        ),
        PerDayStat(
            date="2026-04-28",
            rl_trades=3,
            rl_pnl_krw=120_000.0,
            setup_trades=2,
            setup_pnl_krw=30_000.0,
            delta_krw=90_000.0,
        ),
        PerDayStat(
            date="2026-04-29",
            rl_trades=1,
            rl_pnl_krw=-50_000.0,
            setup_trades=1,
            setup_pnl_krw=10_000.0,
            delta_krw=-60_000.0,
        ),
        PerDayStat(
            date="2026-04-30",
            rl_trades=4,
            rl_pnl_krw=200_000.0,
            setup_trades=2,
            setup_pnl_krw=40_000.0,
            delta_krw=160_000.0,
        ),
        PerDayStat(
            date="2026-05-01",
            rl_trades=2,
            rl_pnl_krw=130_000.0,
            setup_trades=2,
            setup_pnl_krw=25_000.0,
            delta_krw=105_000.0,
        ),
    ]
    return report


def test_format_telegram_empty_report_does_not_crash():
    msg = _format_telegram_message(_empty_report())
    assert isinstance(msg, str)
    assert "Counterfactual Weekly Report" in msg
    assert "no co-occurring signals" in msg
    assert "0 / 50" in msg or "0` / 50" in msg


def test_format_telegram_populated_report_has_top3_days():
    msg = _format_telegram_message(_populated_report())
    # Largest |delta| days: 2026-04-30 (+160k), 2026-05-01 (+105k), 2026-04-28 (+90k)
    assert "2026-04-30" in msg
    assert "2026-05-01" in msg
    assert "2026-04-28" in msg
    # Smallest day NOT in top 3
    lines = msg.split("\n")
    top3_section = "\n".join(
        line for line in lines if "Top 3" in line or "Δ=" in line
    )
    assert "2026-04-29" not in top3_section


def test_format_telegram_under_telegram_limit():
    msg = _format_telegram_message(_populated_report())
    assert len(msg) < 4000  # safety margin under 4096


def test_format_telegram_shows_eod_estimate_when_present():
    """When Setup A/C trades have EOD-estimated exits, surface the count."""
    report = _populated_report()
    msg = _format_telegram_message(report)
    assert "EOD-estimated" in msg


# ---------------------------------------------------------------------------
# _write_archive
# ---------------------------------------------------------------------------


def test_write_archive_round_trips(tmp_path: Path):
    report = _populated_report()
    path = tmp_path / "test-W18.json"
    _write_archive(report, path)
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["start_date"] == "2026-04-27"
    assert payload["end_date"] == "2026-05-03"
    assert payload["symbol"] == "101S6000"
    assert payload["rl_shadow"]["trade_count"] == 12
    assert payload["setup_actual"]["trade_count"] == 8
    assert "archived_at" in payload


def test_write_archive_creates_parent_dirs(tmp_path: Path):
    report = _empty_report()
    path = tmp_path / "nested" / "deep" / "report.json"
    _write_archive(report, path)
    assert path.exists()
