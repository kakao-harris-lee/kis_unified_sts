"""V2 migration creates news_scored with the right schema."""

from pathlib import Path

V2_PATH = Path("infra/clickhouse/migrations/V2__create_news_scored.sql")


def test_v2_file_exists():
    assert V2_PATH.is_file(), "V2 migration file missing"


def test_v2_declares_required_columns():
    sql = V2_PATH.read_text()
    for column in (
        "news_id",
        "scorer_version",
        "scored_at",
        "category",
        "sentiment",
        "impact_score",
        "direction_bias",
        "confidence",
        "keywords",
        "reasoning",
    ):
        assert column in sql, f"V2 missing column: {column}"


def test_v2_declares_ttl_and_partition():
    sql = V2_PATH.read_text()
    assert "PARTITION BY toYYYYMM(scored_at)" in sql
    assert "INTERVAL 2 YEAR" in sql
    assert "MergeTree" in sql
