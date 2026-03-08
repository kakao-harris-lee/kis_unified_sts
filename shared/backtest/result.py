"""백테스트 결과

백테스트 결과 및 거래 기록 데이터 클래스.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class BacktestTrade:
    """개별 거래 기록

    Attributes:
        code: 종목코드
        name: 종목명
        strategy: 전략명
        side: 매수/매도 ("BUY" or "SELL")
        entry_time: 진입 시간
        exit_time: 청산 시간
        entry_price: 진입 가격
        exit_price: 청산 가격
        quantity: 수량
        pnl: 손익 (원)
        pnl_pct: 손익률 (%)
        commission: 수수료
        exit_reason: 청산 사유
        execution_venue: 실행 장소 (e.g., "KRX", "ATS")
    """

    code: str
    name: str
    strategy: str
    side: str
    entry_time: datetime
    exit_time: datetime | None
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    commission: float
    exit_reason: str = ""
    execution_venue: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "strategy": self.strategy,
            "side": self.side,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "commission": self.commission,
            "exit_reason": self.exit_reason,
            "execution_venue": self.execution_venue,
        }


@dataclass
class BacktestResult:
    """백테스트 결과

    Attributes:
        start_date: 시작일
        end_date: 종료일
        total_bars: 총 바 수

        initial_capital: 초기 자본
        final_capital: 최종 자본
        total_return_pct: 총 수익률 (%)
        total_pnl: 총 손익 (원)
        annualized_return: 연환산 수익률 (%)

        total_trades: 총 거래 수
        winning_trades: 승리 거래 수
        losing_trades: 패배 거래 수
        win_rate: 승률 (%)

        avg_profit: 평균 수익 (원)
        avg_loss: 평균 손실 (원)
        profit_factor: Profit Factor
        avg_holding_days: 평균 보유 기간 (일)

        max_drawdown_pct: 최대 낙폭 (%)
        sharpe_ratio: Sharpe Ratio
        sortino_ratio: Sortino Ratio

        exit_reasons: 청산 사유별 통계
        equity_curve: 자산 곡선 [(datetime, value), ...]
        trades: 거래 내역
    """

    # 기간 정보
    start_date: datetime
    end_date: datetime
    total_bars: int

    # 수익률
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_pnl: float
    annualized_return: float = 0.0

    # 거래 통계
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # 손익 분석
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_holding_days: float = 0.0

    # 리스크 지표
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    # 상세 데이터
    exit_reasons: dict[str, int] = field(default_factory=dict)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    trades: list[BacktestTrade] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환 (JSON 직렬화용)"""
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_bars": self.total_bars,
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 0),
            "total_return_pct": round(self.total_return_pct, 2),
            "total_pnl": round(self.total_pnl, 0),
            "annualized_return": round(self.annualized_return, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "avg_profit": round(self.avg_profit, 0),
            "avg_loss": round(self.avg_loss, 0),
            "profit_factor": round(self.profit_factor, 2),
            "avg_holding_days": round(self.avg_holding_days, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "exit_reasons": self.exit_reasons,
        }

    def to_metrics_dict(self) -> dict[str, float]:
        """MLflow 메트릭용 딕셔너리 (숫자 값만)"""
        return {
            "total_return_pct": self.total_return_pct,
            "annualized_return": self.annualized_return,
            "total_pnl": self.total_pnl,
            "total_trades": float(self.total_trades),
            "winning_trades": float(self.winning_trades),
            "losing_trades": float(self.losing_trades),
            "win_rate": self.win_rate,
            "avg_profit": self.avg_profit,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "avg_holding_days": self.avg_holding_days,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
        }

    def print_summary(self):
        """결과 요약 출력"""
        print("\n" + "=" * 60)
        print("백테스트 결과 요약")
        print("=" * 60)
        print(f"기간: {self.start_date.date()} ~ {self.end_date.date()}")
        print(f"총 바 수: {self.total_bars:,}")
        print("-" * 60)
        print(f"초기 자본: {self.initial_capital:,.0f}원")
        print(f"최종 자본: {self.final_capital:,.0f}원")
        print(f"총 수익률: {self.total_return_pct:+.2f}%")
        print(f"연환산 수익률: {self.annualized_return:+.2f}%")
        print(f"총 손익: {self.total_pnl:+,.0f}원")
        print("-" * 60)
        print(f"총 거래: {self.total_trades}회")
        print(f"승리: {self.winning_trades}회 / 패배: {self.losing_trades}회")
        print(f"승률: {self.win_rate:.1f}%")
        print("-" * 60)
        print(f"평균 수익: {self.avg_profit:+,.0f}원")
        print(f"평균 손실: {self.avg_loss:+,.0f}원")
        print(f"Profit Factor: {self.profit_factor:.2f}")
        print(f"평균 보유 기간: {self.avg_holding_days:.1f}일")
        print("-" * 60)
        print(f"최대 낙폭: {self.max_drawdown_pct:.2f}%")
        print(f"Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print(f"Sortino Ratio: {self.sortino_ratio:.2f}")

        if self.exit_reasons:
            print("-" * 60)
            print("청산 사유:")
            for reason, count in sorted(
                self.exit_reasons.items(), key=lambda x: -x[1]
            ):
                print(f"  {reason}: {count}회")

        print("=" * 60)
