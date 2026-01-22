"""Paper trading report generation."""
from dataclasses import dataclass
from datetime import datetime
from typing import List

from .models import TradeRecord


@dataclass
class PaperTradingReport:
    """Paper trading session report.

    Generates comprehensive statistics and markdown reports
    from paper trading sessions.

    Attributes:
        initial_capital: Starting capital in KRW
        final_capital: Ending capital in KRW
        trades: List of completed trades
        start_time: Session start time
        end_time: Session end time
    """

    initial_capital: float
    final_capital: float
    trades: List[TradeRecord]
    start_time: datetime
    end_time: datetime

    def get_summary(self) -> dict:
        """Get summary statistics.

        Returns:
            Dictionary containing:
            - total_trades: Number of trades
            - winning_trades: Number of profitable trades
            - losing_trades: Number of losing trades
            - win_rate: Percentage of winning trades
            - total_pnl: Total profit/loss in KRW
            - return_pct: Return percentage on initial capital
            - avg_win: Average winning trade P&L
            - avg_loss: Average losing trade P&L
            - largest_win: Largest single winning trade
            - largest_loss: Largest single losing trade
        """
        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl < 0]

        total_pnl = sum(t.pnl for t in self.trades)
        win_rate = len(winning) / len(self.trades) * 100 if self.trades else 0
        return_pct = (
            (self.final_capital - self.initial_capital) / self.initial_capital * 100
            if self.initial_capital > 0
            else 0
        )

        return {
            "total_trades": len(self.trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "return_pct": return_pct,
            "avg_win": sum(t.pnl for t in winning) / len(winning) if winning else 0,
            "avg_loss": sum(t.pnl for t in losing) / len(losing) if losing else 0,
            "largest_win": max((t.pnl for t in winning), default=0),
            "largest_loss": min((t.pnl for t in losing), default=0),
        }

    def to_markdown(self) -> str:
        """Generate markdown report.

        Returns:
            Formatted markdown string with summary tables and trade history.
        """
        s = self.get_summary()
        duration = self.end_time - self.start_time

        md = f"""# Paper Trading Report

## Summary

| Metric | Value |
|--------|-------|
| Period | {duration.days}d {duration.seconds // 3600}h |
| Initial Capital | {self.initial_capital:,.0f} KRW |
| Final Capital | {self.final_capital:,.0f} KRW |
| Total P&L | {s['total_pnl']:+,.0f} KRW |
| Return | {s['return_pct']:+.2f}% |

## Performance

| Metric | Value |
|--------|-------|
| Total Trades | {s['total_trades']} |
| Winning Trades | {s['winning_trades']} |
| Losing Trades | {s['losing_trades']} |
| Win Rate | {s['win_rate']:.1f}% |
| Avg Win | {s['avg_win']:,.0f} KRW |
| Avg Loss | {s['avg_loss']:,.0f} KRW |
| Largest Win | {s['largest_win']:,.0f} KRW |
| Largest Loss | {s['largest_loss']:,.0f} KRW |

## Trade History

| # | Symbol | Side | Entry | Exit | P&L | P&L % |
|---|--------|------|-------|------|-----|-------|
"""
        for i, t in enumerate(self.trades, 1):
            side = t.side.value if hasattr(t.side, "value") else str(t.side)
            md += (
                f"| {i} | {t.symbol} | {side} | {t.entry_price:,.0f} | "
                f"{t.exit_price:,.0f} | {t.pnl:+,.0f} | {t.pnl_pct:+.2f}% |\n"
            )

        return md

    def to_json(self) -> dict:
        """Export report as JSON-serializable dict.

        Returns:
            Dictionary with summary and trades suitable for JSON serialization.
        """
        return {
            "summary": self.get_summary(),
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "trades": [
                {
                    "trade_id": t.trade_id,
                    "symbol": t.symbol,
                    "side": t.side.value if hasattr(t.side, "value") else str(t.side),
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "quantity": t.quantity,
                    "entry_time": t.entry_time.isoformat(),
                    "exit_time": t.exit_time.isoformat(),
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                }
                for t in self.trades
            ],
        }


def create_report_from_broker(broker, start_time: datetime) -> PaperTradingReport:
    """Create a report from VirtualBroker state.

    Args:
        broker: VirtualBroker instance
        start_time: Session start time

    Returns:
        PaperTradingReport instance
    """
    return PaperTradingReport(
        initial_capital=broker.initial_balance,
        final_capital=broker.get_equity(),
        trades=broker.trades,
        start_time=start_time,
        end_time=datetime.now(),
    )
