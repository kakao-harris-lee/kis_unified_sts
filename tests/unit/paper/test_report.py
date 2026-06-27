"""Test paper trading report generation."""
from datetime import datetime, timedelta

import pytest

from shared.paper.models import OrderSide, TradeRecord
from shared.paper.report import PaperTradingReport


def test_report_generation():
    """Test report with sample trades."""
    now = datetime.now()
    trades = [
        TradeRecord(
            trade_id="T001",
            symbol="005930",
            side=OrderSide.BUY,
            entry_price=50000,
            exit_price=52000,
            quantity=100,
            entry_time=now - timedelta(hours=2),
            exit_time=now,
            commission=0,
        ),
        TradeRecord(
            trade_id="T002",
            symbol="035720",
            side=OrderSide.BUY,
            entry_price=100000,
            exit_price=98000,
            quantity=50,
            entry_time=now - timedelta(hours=1),
            exit_time=now,
            commission=0,
        ),
    ]

    report = PaperTradingReport(
        initial_capital=10_000_000,
        final_capital=10_100_000,
        trades=trades,
        start_time=now - timedelta(days=1),
        end_time=now,
    )

    summary = report.get_summary()

    assert summary["total_trades"] == 2
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 1
    assert summary["win_rate"] == 50.0
    # T001: (52000-50000)*100 = 200000
    # T002: (98000-100000)*50 = -100000
    # Total: 100000
    assert summary["total_pnl"] == 100000
    assert summary["return_pct"] == pytest.approx(1.0, rel=0.01)


def test_report_to_markdown():
    """Test markdown report generation."""
    now = datetime.now()
    trades = [
        TradeRecord(
            trade_id="T001",
            symbol="005930",
            side=OrderSide.BUY,
            entry_price=50000,
            exit_price=52000,
            quantity=100,
            entry_time=now,
            exit_time=now,
            commission=0,
        ),
    ]

    report = PaperTradingReport(
        initial_capital=10_000_000,
        final_capital=10_200_000,
        trades=trades,
        start_time=now,
        end_time=now,
    )

    md = report.to_markdown()

    assert "# Paper Trading Report" in md
    assert "Total P&L" in md
    assert "Win Rate" in md


def test_empty_report():
    """Test report with no trades."""
    now = datetime.now()
    report = PaperTradingReport(
        initial_capital=10_000_000,
        final_capital=10_000_000,
        trades=[],
        start_time=now,
        end_time=now,
    )

    summary = report.get_summary()

    assert summary["total_trades"] == 0
    assert summary["winning_trades"] == 0
    assert summary["losing_trades"] == 0
    assert summary["win_rate"] == 0
    assert summary["total_pnl"] == 0


def test_report_statistics():
    """Test detailed statistics calculations."""
    now = datetime.now()
    trades = [
        TradeRecord(
            trade_id="T001",
            symbol="005930",
            side=OrderSide.BUY,
            entry_price=50000,
            exit_price=55000,  # +500K
            quantity=100,
            entry_time=now,
            exit_time=now,
            commission=0,
        ),
        TradeRecord(
            trade_id="T002",
            symbol="005930",
            side=OrderSide.BUY,
            entry_price=50000,
            exit_price=51000,  # +100K
            quantity=100,
            entry_time=now,
            exit_time=now,
            commission=0,
        ),
        TradeRecord(
            trade_id="T003",
            symbol="005930",
            side=OrderSide.BUY,
            entry_price=50000,
            exit_price=48000,  # -200K
            quantity=100,
            entry_time=now,
            exit_time=now,
            commission=0,
        ),
    ]

    report = PaperTradingReport(
        initial_capital=10_000_000,
        final_capital=10_400_000,
        trades=trades,
        start_time=now,
        end_time=now,
    )

    summary = report.get_summary()

    assert summary["winning_trades"] == 2
    assert summary["losing_trades"] == 1
    assert summary["win_rate"] == pytest.approx(66.67, rel=0.01)
    assert summary["avg_win"] == 300000  # (500K + 100K) / 2
    assert summary["avg_loss"] == -200000
    assert summary["largest_win"] == 500000
    assert summary["largest_loss"] == -200000


def test_report_from_broker():
    """Test creating report from VirtualBroker trades."""
    from shared.paper.report import PaperTradingReport

    # Simulating broker data extraction
    initial = 10_000_000
    final = 10_500_000

    now = datetime.now()
    trades = [
        TradeRecord(
            trade_id="T001",
            symbol="005930",
            side=OrderSide.BUY,
            entry_price=50000,
            exit_price=55000,
            quantity=100,
            entry_time=now - timedelta(hours=1),
            exit_time=now,
            commission=100,
        ),
    ]

    report = PaperTradingReport(
        initial_capital=initial,
        final_capital=final,
        trades=trades,
        start_time=now - timedelta(hours=2),
        end_time=now,
    )

    # Verify trade pnl includes commission
    assert trades[0].pnl == 499900  # (55000-50000)*100 - 100 commission

    summary = report.get_summary()
    assert summary["total_trades"] == 1
