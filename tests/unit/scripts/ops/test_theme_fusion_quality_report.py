from __future__ import annotations

import json
from pathlib import Path

from scripts.ops.theme_fusion_quality_report import build_theme_fusion_quality_report


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
                "codes": ["000001", "000002", "000003"],
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
