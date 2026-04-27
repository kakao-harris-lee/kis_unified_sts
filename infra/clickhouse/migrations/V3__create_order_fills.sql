-- V3__create_order_fills.sql
-- Phase 4: order fill / slippage logging table.
-- Spec: docs/plans/2026-04-20-futures-paradigm-phase4-execution.md §5.1
CREATE TABLE IF NOT EXISTS kospi.order_fills (
    signal_id String,
    order_id String,
    symbol LowCardinality(String),
    side LowCardinality(String),
    order_type LowCardinality(String),      -- limit_passive|limit_aggressive|stop|market
    requested_price Float64,
    filled_price Float64,
    tick_size_points Float32,               -- contract-specific (mini=0.02)
    slippage_ticks Float32,
    quantity UInt32,
    requested_at DateTime64(3, 'UTC'),
    filled_at DateTime64(3, 'UTC'),
    latency_ms UInt32,
    venue LowCardinality(String),           -- "KRX"
    trade_role LowCardinality(String),      -- "entry"|"stop_loss"|"take_profit"|"force_close"
    broker_error_code String
) ENGINE = MergeTree()
ORDER BY (filled_at, order_id)
PARTITION BY toYYYYMM(filled_at)
TTL toDateTime(filled_at) + INTERVAL 5 YEAR;
