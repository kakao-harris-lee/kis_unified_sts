"""Lint the committed LIVE crontab example."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CRON = REPO / "deploy" / "cron" / "kis-live.crontab.example"


def test_cron_example_exists_and_is_kst_preflight_gated():
    text = CRON.read_text(encoding="utf-8")
    # KST native (project rule: all cron is KST)
    assert "CRON_TZ=Asia/Seoul" in text
    # Every trade-start entry must be gated by the preflight guardrail
    assert "scripts/ops/live_preflight.sh" in text
    # Live flags + isolated live project, not paper
    assert "--live" in text and "--yes-live" in text
    assert "KIS_LIVE_PROJECT=/home/deploy/project/kis_unified_sts_live" in text
    # Must not point at the paper/dev clone
    assert "/home/deploy/project/kis_unified_sts/.venv" not in text
    assert "--paper" not in text


def test_every_trade_start_line_is_preflight_gated():
    for raw in CRON.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#") or "trade start" not in line:
            continue
        assert "live_preflight.sh &&" in line, f"unguarded live trade start: {line}"
