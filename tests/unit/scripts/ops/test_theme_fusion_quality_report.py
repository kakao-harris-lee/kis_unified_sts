from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.ops import theme_fusion_quality_report as report_module
from scripts.ops.theme_fusion_quality_report import build_theme_fusion_quality_report


def _write_snapshot(
    tmp_path: Path, payload: dict[str, object], filename: str = "theme_targets.json"
) -> Path:
    snapshot = tmp_path / filename
    snapshot.write_text(json.dumps(payload), encoding="utf-8")
    return snapshot


def test_theme_quality_report_counts_active_quarantined_and_false_positive_examples(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "theme_targets.json"
    snapshot.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-28T09:00:00+09:00",
                "targets": [
                    {
                        "code": "000001",
                        "theme_id": "ai_hbm",
                        "state": "active",
                        "leader_score": 0.91,
                        "label": "AI HBM",
                    },
                    {
                        "code": "000002",
                        "theme_id": "ai_hbm",
                        "state": "quarantined",
                        "leader_score": 0.21,
                        "label": "AI HBM",
                    },
                    {
                        "code": "000003",
                        "theme_id": "shipbuilding_defense",
                        "state": "active",
                        "leader_score": 0.77,
                        "label": "Shipbuilding Defense",
                    },
                ],
                "false_positive_examples": [
                    {
                        "code": "000002",
                        "theme_id": "ai_hbm",
                        "reason": "generic keyword",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_theme_fusion_quality_report(snapshot)

    assert report["target_count"] == 3
    assert report["state_counts"] == {"active": 2, "quarantined": 1}
    assert report["theme_counts"]["ai_hbm"] == 2
    assert report["false_positive_examples"][0]["reason"] == "generic keyword"


def test_theme_quality_report_supports_canonical_theme_target_payload(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "canonical_theme_targets.json"
    snapshot.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-28T09:00:00+09:00",
                "codes": ["000001", "000003"],
                "scores": {
                    "000001": 0.91,
                    "000002": 0.21,
                    "000003": 0.77,
                },
                "metadata": {
                    "000001": {
                        "theme_id": "ai_hbm",
                        "theme_label": "AI/HBM",
                        "state": "active",
                    },
                    "000002": {
                        "theme_id": "ai_hbm",
                        "theme_label": "AI/HBM",
                        "state": "quarantined",
                    },
                    "000003": {
                        "theme_id": "shipbuilding_defense",
                        "theme_label": "Shipbuilding Defense",
                        "state": "active",
                    },
                },
                "quarantined_codes": ["000002"],
            }
        ),
        encoding="utf-8",
    )

    report = build_theme_fusion_quality_report(snapshot)

    assert report["target_count"] == 3
    assert report["state_counts"] == {"active": 2, "quarantined": 1}
    assert report["theme_counts"]["ai_hbm"] == 2
    assert report["theme_counts"]["shipbuilding_defense"] == 1
    assert report["min_leader_score"] == 0.21
    assert report["max_leader_score"] == 0.91
    assert report["false_positive_examples"] == []


def test_theme_quality_report_marks_stale_generated_at(tmp_path: Path) -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    snapshot = _write_snapshot(
        tmp_path,
        {
            "generated_at": (now - timedelta(seconds=1801)).isoformat(),
            "targets": [{"code": "000001", "state": "active"}],
        },
    )

    report = build_theme_fusion_quality_report(
        snapshot,
        now=now,
        max_age_seconds=1800,
        max_future_skew_seconds=300,
    )

    assert report["freshness"]["ok"] is False
    assert report["freshness"]["status"] == "stale"
    assert report["freshness"]["reasons"] == ["generated_at stale"]
    assert report["freshness"]["age_seconds"] == 1801.0


def test_theme_quality_report_marks_future_generated_at(tmp_path: Path) -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    snapshot = _write_snapshot(
        tmp_path,
        {
            "generated_at": (now + timedelta(seconds=301)).isoformat(),
            "targets": [{"code": "000001", "state": "active"}],
        },
    )

    report = build_theme_fusion_quality_report(
        snapshot,
        now=now,
        max_age_seconds=1800,
        max_future_skew_seconds=300,
    )

    assert report["freshness"]["ok"] is False
    assert report["freshness"]["status"] == "future"
    assert report["freshness"]["reasons"] == ["generated_at is in the future"]
    assert report["freshness"]["future_skew_seconds"] == 301.0


def test_theme_quality_report_marks_missing_generated_at(tmp_path: Path) -> None:
    snapshot = _write_snapshot(
        tmp_path,
        {"targets": [{"code": "000001", "state": "active"}]},
    )

    report = build_theme_fusion_quality_report(
        snapshot,
        now=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    )

    assert report["generated_at"] is None
    assert report["freshness"]["ok"] is False
    assert report["freshness"]["status"] == "missing"
    assert report["freshness"]["reasons"] == ["generated_at missing"]


def test_theme_quality_report_flags_empty_snapshot_with_no_matches(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    snapshot = _write_snapshot(
        tmp_path,
        {
            "generated_at": now.isoformat(),
            "codes": [],
            "targets": [],
            "source": {"status": "no_matches"},
        },
    )

    report = build_theme_fusion_quality_report(snapshot, now=now)

    assert report["freshness"]["status"] == "fresh"
    assert report["target_count"] == 0
    assert report["source_status"] == "no_matches"
    assert report["ok"] is False
    assert report["status"] in {"empty", "no_matches"}


def test_theme_quality_report_tolerates_list_top_level(tmp_path: Path) -> None:
    snapshot = tmp_path / "list_snapshot.json"
    snapshot.write_text(json.dumps([{"code": "000001"}]), encoding="utf-8")

    report = build_theme_fusion_quality_report(
        snapshot,
        now=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    )

    assert report["generated_at"] is None
    assert report["target_count"] == 0
    assert report["state_counts"] == {}
    assert report["ok"] is False
    assert report["status"] == "missing"


def test_theme_quality_report_cli_strict_returns_one_on_stale(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    snapshot = _write_snapshot(
        tmp_path,
        {
            "generated_at": (now - timedelta(seconds=1801)).isoformat(),
            "targets": [{"code": "000001", "state": "active"}],
        },
    )
    output = tmp_path / "report.json"

    rc = report_module.main(
        [
            "--snapshot",
            str(snapshot),
            "--output",
            str(output),
            "--strict",
        ],
        now=now,
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert rc == 1
    assert report["ok"] is False
    assert report["status"] == "stale"


def test_theme_quality_report_cli_accepts_freshness_thresholds(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    snapshot = _write_snapshot(
        tmp_path,
        {
            "generated_at": (now - timedelta(seconds=601)).isoformat(),
            "targets": [{"code": "000001", "state": "active"}],
        },
    )
    output = tmp_path / "report.json"

    rc = report_module.main(
        [
            "--snapshot",
            str(snapshot),
            "--output",
            str(output),
            "--max-age-seconds",
            "600",
            "--max-future-skew-seconds",
            "30",
        ],
        now=now,
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert rc == 0
    assert report["freshness"]["status"] == "stale"
    assert report["freshness"]["max_age_seconds"] == 600.0
    assert report["freshness"]["max_future_skew_seconds"] == 30.0
