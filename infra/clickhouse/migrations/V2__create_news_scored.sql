-- V2__create_news_scored.sql
-- Phase 2: per-news structured score table.
-- Spec: docs/plans/2026-04-20-futures-paradigm-phase2-scoring.md §2.2
CREATE TABLE IF NOT EXISTS kospi.news_scored (
    news_id String,
    scorer_version LowCardinality(String),
    scored_at DateTime64(3, 'UTC'),
    category LowCardinality(String),
    sentiment Float32,
    impact_score Float32,
    direction_bias LowCardinality(String),
    confidence Float32,
    keywords Array(String),
    reasoning String,
    INDEX idx_cat_impact (category, impact_score) TYPE minmax GRANULARITY 4
) ENGINE = MergeTree()
ORDER BY (scored_at, news_id)
PARTITION BY toYYYYMM(scored_at)
TTL toDateTime(scored_at) + INTERVAL 2 YEAR;
