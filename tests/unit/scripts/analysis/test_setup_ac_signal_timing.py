"""Unit tests for scripts/analysis/setup_ac_signal_timing.py.

Verdict logic:
  - FAIL: log missing
  - FAIL: cycles present but ALL zero-signal (Setup A/C defect persists)
  - WARN: morning signals but zero afternoon (cache-freeze signature)
  - PASS: signals in the afternoon window too (cache fix effective)
"""
from __future__ import annotations

from datetime import date

import scripts.analysis.setup_ac_signal_timing as _mod


def _line(ts: str, n: int) -> str:
    return (
        f"{ts},123 - services.trading.strategy_manager - INFO - "
        f"Signal cycle: {n} signals from [rl_mppo, setup_a_gap_reversion, "
        f"setup_c_event_reaction]"
    )


def _write_log(tmp_path, name: str, lines: list[str]):
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_missing_log_is_fail(tmp_path):
    rep = _mod._parse_log(tmp_path / "nope.log", date(2026, 5, 18))
    assert rep.verdict == "FAIL"
    assert "not found" in rep.detail


def test_all_zero_session_is_fail(tmp_path):
    lines = [_line(f"2026-05-18 {h:02d}:00:00", 0) for h in range(9, 16)]
    p = _write_log(tmp_path, "z.log", lines)
    rep = _mod._parse_log(p, date(2026, 5, 18))
    assert rep.verdict == "FAIL"
    assert rep.total_cycles == 7
    assert rep.total_signals == 0
    assert "necessary but NOT" in rep.detail


def test_morning_only_is_warn(tmp_path):
    # signals in 09–12, zero 13–15  → cache-freeze signature
    lines = [_line(f"2026-05-18 {h:02d}:30:00", 2) for h in (9, 10, 11, 12)]
    lines += [_line(f"2026-05-18 {h:02d}:30:00", 0) for h in (13, 14, 15)]
    p = _write_log(tmp_path, "m.log", lines)
    rep = _mod._parse_log(p, date(2026, 5, 18))
    assert rep.verdict == "WARN"
    assert rep.morning_signals == 8
    assert rep.afternoon_signals == 0
    assert "freeze signature persists" in rep.detail


def test_signals_throughout_is_pass(tmp_path):
    lines = [_line(f"2026-05-18 {h:02d}:15:00", 1) for h in (9, 11, 13, 15)]
    p = _write_log(tmp_path, "p.log", lines)
    rep = _mod._parse_log(p, date(2026, 5, 18))
    assert rep.verdict == "PASS"
    assert rep.morning_signals == 2
    assert rep.afternoon_signals == 2
    assert rep.by_hour["13"] == 1 and rep.by_hour["15"] == 1


def test_other_date_lines_ignored(tmp_path):
    lines = [
        _line("2026-05-17 10:00:00", 5),   # different date — ignore
        _line("2026-05-18 10:00:00", 0),
        _line("2026-05-18 16:30:00", 9),   # post-close (>=16h) — ignore
    ]
    p = _write_log(tmp_path, "x.log", lines)
    rep = _mod._parse_log(p, date(2026, 5, 18))
    assert rep.total_cycles == 1   # only the 05-18 10:00 line counted
    assert rep.total_signals == 0
    assert rep.verdict == "FAIL"


def test_telegram_format_has_verdict_and_hours(tmp_path):
    lines = [_line(f"2026-05-18 {h:02d}:15:00", 1) for h in (9, 14)]
    rep = _mod._parse_log(_write_log(tmp_path, "t.log", lines),
                          date(2026, 5, 18))
    msg = _mod._format_telegram(rep)
    assert "Setup A/C signal timing — 2026-05-18" in msg
    assert "verdict: PASS" in msg
    assert "by hour (KST):" in msg
