"""Setup C event-score readiness observation tests."""

from __future__ import annotations

import importlib
import json


def _event(
    asof: str,
    *,
    impact_score: float,
    impact_tier: int,
    event_type: str = "BOK_rate_decision",
    ttl_minutes: int = 30,
) -> dict[str, object]:
    return {
        "asof": asof,
        "impact_score": impact_score,
        "impact_tier": impact_tier,
        "event_type": event_type,
        "source": "rule",
        "raw_text": None,
        "ttl_minutes": ttl_minutes,
    }


def test_history_json_ready_report_includes_freshness_score_and_tiers(
    tmp_path,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.setup_c_event_score_observe")
    history = [
        _event("2026-06-25T09:56:00+09:00", impact_score=88, impact_tier=1),
        _event("2026-06-25T09:50:00+09:00", impact_score=76, impact_tier=1),
        _event(
            "2026-06-25T09:43:00+09:00",
            impact_score=64,
            impact_tier=2,
            event_type="US_CPI",
        ),
    ]
    history_path = tmp_path / "history.json"
    report_path = tmp_path / "report.json"
    history_path.write_text(json.dumps(history), encoding="utf-8")

    rc = module.main(
        [
            "--history-json",
            str(history_path),
            "--output-json",
            str(report_path),
            "--asof",
            "2026-06-25T10:00:00+09:00",
            "--min-history",
            "3",
            "--max-age-minutes",
            "20",
            "--min-impact-score",
            "60",
        ]
    )
    stdout_report = json.loads(capsys.readouterr().out)
    file_report = json.loads(report_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert stdout_report == file_report
    assert file_report["ready"] is True
    assert file_report["missing_evidence"] == []
    assert file_report["count"] == 3
    assert file_report["fresh_count"] == 3
    assert file_report["max_age_minutes"] == 17.0
    assert file_report["impact_score"]["min"] == 64.0
    assert file_report["impact_score"]["avg"] == 76.0
    assert file_report["tier_distribution"] == {"1": 2, "2": 1}
    assert file_report["latest"]["event_type"] == "BOK_rate_decision"


def test_history_json_not_ready_reports_empty_stale_and_low_impact(
    tmp_path,
    capsys,
) -> None:
    module = importlib.import_module("scripts.ops.setup_c_event_score_observe")
    history = [
        _event("2026-06-25T08:30:00+09:00", impact_score=42, impact_tier=3),
    ]
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps(history), encoding="utf-8")

    rc = module.main(
        [
            "--history-json",
            str(history_path),
            "--asof",
            "2026-06-25T10:00:00+09:00",
            "--min-history",
            "3",
            "--max-age-minutes",
            "20",
            "--min-impact-score",
            "60",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert report["ready"] is False
    assert report["count"] == 1
    assert report["fresh_count"] == 0
    assert report["max_age_minutes"] == 90.0
    assert report["impact_score"]["min"] == 42.0
    assert report["tier_distribution"] == {"3": 1}
    assert report["missing_evidence"] == [
        "event_score_history_empty",
        "event_score_stale",
        "impact_score_below_minimum",
    ]


def test_fresh_count_respects_event_ttl_before_max_age(tmp_path, capsys) -> None:
    module = importlib.import_module("scripts.ops.setup_c_event_score_observe")
    history = [
        _event(
            "2026-06-25T09:50:00+09:00",
            impact_score=80,
            impact_tier=1,
            ttl_minutes=5,
        ),
    ]
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps(history), encoding="utf-8")

    rc = module.main(
        [
            "--history-json",
            str(history_path),
            "--asof",
            "2026-06-25T10:00:00+09:00",
            "--min-history",
            "1",
            "--max-age-minutes",
            "20",
            "--min-impact-score",
            "60",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert report["fresh_count"] == 0
    assert report["missing_evidence"] == ["event_score_stale"]


def test_placeholder_event_score_evidence_is_not_ready(tmp_path, capsys) -> None:
    module = importlib.import_module("scripts.ops.setup_c_event_score_observe")
    history = [
        _event(
            "2026-06-25T09:56:00+09:00",
            impact_score=88,
            impact_tier=1,
            event_type="placeholder",
        )
    ]
    history[0]["source"] = "TODO"
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps(history), encoding="utf-8")

    rc = module.main(
        [
            "--history-json",
            str(history_path),
            "--asof",
            "2026-06-25T10:00:00+09:00",
            "--min-history",
            "1",
            "--max-age-minutes",
            "20",
            "--min-impact-score",
            "60",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert report["ready"] is False
    assert report["missing_evidence"] == ["placeholder_event_score_evidence"]
