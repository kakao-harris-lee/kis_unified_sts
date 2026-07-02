from pathlib import Path


def test_scheduler_runs_daily_risk_reset_before_regular_session():
    crontab = Path("deploy/scheduler.crontab").read_text(encoding="utf-8")

    expected = (
        "59 8  * * 1-5  cd /app && " "python -m scripts.maintenance.daily_risk_reset"
    )

    assert expected in crontab
