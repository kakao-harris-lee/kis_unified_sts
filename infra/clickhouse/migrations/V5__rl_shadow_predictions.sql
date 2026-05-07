-- V5__rl_shadow_predictions.sql
-- Phase 0.3 (LLM-primary plan §4): create table for RL shadow-mode counterfactual
-- analysis.  When RLMPPOEntry runs in shadow_mode=True, inference results are
-- buffered and flushed here instead of being emitted as live Signals.
--
-- Retention: 6 months — matches operator §7-3 decision in
-- docs/plans/2026-05-03-llm-primary-rl-minimization.md:
-- "RL shadow data is only needed for the Phase 2/3 comparison window; purge
-- after 6 months to keep storage bounded."
--
-- Field notes:
--   action         — 0=LONG_ENTRY, 1=LONG_EXIT, 2=SHORT_ENTRY, 3=SHORT_EXIT, 4=HOLD
--   action_probs   — masked+normalized probability vector keyed by action index (str)
--   regime         — market regime label from context.metadata at inference time
--   risk_mode      — risk budget mode string (e.g. "AGGRESSIVE", "DEFENSIVE")
--   risk_score     — numeric risk score from risk_filter (0.0 if unavailable)
--   action_masks   — 5-element boolean mask applied during model.predict()
--   executed_setup_id — Setup A/C signal_id that fired in the same bar (empty if none)

CREATE TABLE IF NOT EXISTS kospi.rl_shadow_predictions (
    ts               DateTime64(3, 'UTC'),
    symbol           String,
    action           UInt8,
    confidence       Float32,
    action_probs     Map(String, Float32),
    regime           String,
    risk_mode        String,
    risk_score       Float32,
    action_masks     Array(UInt8),
    executed_setup_id String,
    PRIMARY KEY (ts, symbol)
) ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (ts, symbol)
TTL toDateTime(ts) + INTERVAL 6 MONTH;
