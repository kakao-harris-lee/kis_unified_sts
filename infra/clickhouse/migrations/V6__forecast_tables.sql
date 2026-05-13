-- V6__forecast_tables.sql
-- Phase A of forecast-aware paradigm — adds 3 tables for HAR-RV model
-- fits, per-minute volatility forecasts, and event impact scores.

CREATE TABLE IF NOT EXISTS kospi.har_rv_fits (
    fit_date Date,
    beta_0 Float64,
    beta_d Float64,
    beta_w Float64,
    beta_m Float64,
    r2_in_sample Float64,
    r2_oos Float64,
    n_obs_used UInt32,
    confidence Float32,
    model_version LowCardinality(String),
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY fit_date
TTL fit_date + INTERVAL 12 MONTH;

CREATE TABLE IF NOT EXISTS kospi.vol_forecasts (
    asof DateTime64(3, 'UTC'),
    horizon_minutes UInt16,
    forecast_pct Float32,
    forecast_atr_equivalent Float32,
    regime_percentile Float32,
    realized_15m_after Float32 DEFAULT 0,
    model_version LowCardinality(String)
) ENGINE = MergeTree()
ORDER BY asof
TTL asof + INTERVAL 90 DAY;

CREATE TABLE IF NOT EXISTS kospi.event_scores (
    asof DateTime64(3, 'UTC'),
    event_type LowCardinality(String),
    impact_score UInt8,
    source Enum8('rule' = 1, 'llm' = 2),
    ttl_minutes UInt16,
    raw_text_hash FixedString(16) DEFAULT '',
    setup_consumed Array(LowCardinality(String))
) ENGINE = MergeTree()
ORDER BY asof
TTL asof + INTERVAL 6 MONTH;
