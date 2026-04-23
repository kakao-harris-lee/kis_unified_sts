-- Phase 1 tables for futures paradigm shift
-- Spec: docs/plans/2026-04-20-futures-paradigm-phase1-data-infra.md

CREATE TABLE IF NOT EXISTS kospi.news_raw (
    news_id String,
    source LowCardinality(String),
    published_at DateTime64(3, 'UTC'),
    received_at DateTime64(3, 'UTC'),
    title String,
    body String,
    url String,
    source_version LowCardinality(String),
    lang LowCardinality(String),
    keywords Array(String)
) ENGINE = MergeTree()
ORDER BY (published_at, news_id)
PARTITION BY toYYYYMM(published_at)
TTL toDateTime(published_at) + INTERVAL 2 YEAR;

CREATE TABLE IF NOT EXISTS kospi.macro_overnight (
    ts DateTime64(3, 'UTC'),
    session LowCardinality(String),
    sp500_close Float64,
    sp500_change_pct Float32,
    nasdaq_close Float64,
    nasdaq_change_pct Float32,
    eurex_kospi_close Nullable(Float64),
    eurex_kospi_change_pct Nullable(Float32),
    usdkrw Float64,
    usdkrw_change_pct Float32,
    dxy Nullable(Float64),
    us10y_yield Nullable(Float32),
    vix Nullable(Float32),
    collected_from Array(String)
) ENGINE = ReplacingMergeTree(ts)
ORDER BY (session, toDate(ts))
PARTITION BY toYYYYMM(ts)
TTL toDateTime(ts) + INTERVAL 5 YEAR;

CREATE TABLE IF NOT EXISTS kospi.signals_all (
    signal_id String,
    generated_at DateTime64(3, 'UTC'),
    setup_type LowCardinality(String),
    direction LowCardinality(String),
    entry_price Float64,
    stop_loss Float64,
    take_profit Float64,
    confidence Float32,
    executed UInt8,
    skip_reason String,
    reason_tags Array(String)
) ENGINE = MergeTree()
ORDER BY (generated_at, signal_id)
PARTITION BY toYYYYMM(generated_at)
TTL toDateTime(generated_at) + INTERVAL 5 YEAR;

CREATE TABLE IF NOT EXISTS kospi.daily_performance (
    trade_date Date,
    n_signals UInt16,
    n_executed UInt16,
    n_wins UInt16,
    n_losses UInt16,
    gross_pnl Float64,
    slippage_cost Float64,
    commission_cost Float64,
    net_pnl Float64,
    max_drawdown Float32,
    ending_equity Float64
) ENGINE = ReplacingMergeTree(trade_date)
ORDER BY trade_date;
