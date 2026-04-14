-- Daily aggregated PnL / win rate for futures RL paper trading.
-- Reads from kospi.rl_trades (populated by TradingOrchestrator futures+rl_ path).
CREATE VIEW IF NOT EXISTS kospi.futures_daily_equity AS
SELECT
    toDate(exit_date) AS d,
    count() AS trades,
    countIf(pnl > 0) AS wins,
    round(countIf(pnl > 0) / count() * 100, 1) AS win_pct,
    round(sum(pnl), 2) AS daily_pnl,
    round(avg(hold_seconds), 0) AS avg_hold_seconds,
    arrayDistinct(groupArray(strategy)) AS strategies
FROM kospi.rl_trades
GROUP BY d
ORDER BY d;
