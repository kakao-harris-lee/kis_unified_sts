-- Daily aggregated PnL / win rate for stock paper/live trading.
-- Reads from market.stock_trades (populated since 2026-04-14 by TradingOrchestrator stock path).
CREATE VIEW IF NOT EXISTS market.stock_daily_equity AS
SELECT
    toDate(exit_date) AS d,
    count() AS trades,
    countIf(pnl > 0) AS wins,
    round(countIf(pnl > 0) / count() * 100, 1) AS win_pct,
    round(sum(pnl), 0) AS daily_pnl,
    round(sum(commission), 0) AS daily_commission,
    round(sum(slippage), 0) AS daily_slippage,
    round(avg(hold_seconds) / 60, 1) AS avg_hold_minutes
FROM market.stock_trades
GROUP BY d
ORDER BY d;
