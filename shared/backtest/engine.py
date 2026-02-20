"""백테스트 엔진

이벤트 루프 기반 백테스트 시뮬레이션.

Usage:
    from shared.backtest import BacktestEngine, BacktestConfig
    from shared.strategy import StrategyFactory

    strategy = StrategyFactory.create_from_file("stock", "bb_reversion")
    config = BacktestConfig.stock(initial_capital=10_000_000)

    engine = BacktestEngine(strategy, config)
    result = engine.run(data)

    result.print_summary()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

import numpy as np
import pandas as pd

from shared.backtest.config import BacktestConfig
from shared.backtest.result import BacktestResult, BacktestTrade

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """거래 시그널 타입"""

    HOLD = 0
    BUY = 1
    SELL = -1


class ExitReason(Enum):
    """청산 사유"""

    SIGNAL = "signal"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_LIMIT = "time_limit"
    FORCE_CLOSE = "force_close"
    END_OF_DATA = "end_of_data"


class StrategyProtocol(Protocol):
    """전략 프로토콜 (인터페이스)"""

    name: str

    def on_bar(self, bar: dict[str, Any]) -> SignalType:
        """바 데이터에 대한 시그널 생성"""
        ...


@dataclass
class Position:
    """포지션 정보"""

    code: str
    name: str
    strategy: str
    side: str  # "BUY" or "SELL"
    entry_time: datetime
    entry_price: float
    quantity: int
    highest_price: float = 0.0
    lowest_price: float = 0.0
    bars_held: int = 0
    atr_at_entry: float = 0.0

    @property
    def current_value(self) -> float:
        """현재 평가 금액"""
        return self.entry_price * self.quantity


class BacktestEngine:
    """백테스트 엔진

    이벤트 루프 기반 시뮬레이션:
    1. 바 데이터 처리
    2. 리스크 관리 체크 (손절/익절/트레일링)
    3. 전략 시그널 생성
    4. 포지션 진입/청산 실행
    5. 통계 업데이트

    Usage:
        engine = BacktestEngine(strategy, config)
        result = engine.run(data)
    """

    def __init__(
        self,
        strategy: StrategyProtocol,
        config: BacktestConfig | None = None,
    ):
        """
        Args:
            strategy: 전략 객체 (on_bar 메서드 필요)
            config: 백테스트 설정
        """
        self.strategy = strategy
        self.config = config or BacktestConfig()

        # 상태 초기화
        self._reset()

    def _reset(self):
        """상태 초기화"""
        self.capital = self.config.initial_capital
        self.positions: dict[str, Position] = {}
        self.trades: list[BacktestTrade] = []
        self.equity_curve: list[tuple[datetime, float]] = []
        self.exit_reasons: dict[str, int] = {}

        # 일별 통계
        self.daily_returns: list[float] = []
        self._current_day_pnl = 0.0
        self._last_date: datetime | None = None
        self._daily_trades = 0

    def run(self, data: pd.DataFrame) -> BacktestResult:
        """백테스트 실행

        Args:
            data: OHLCV 데이터 DataFrame
                필수 컬럼: datetime, open, high, low, close, volume
                선택 컬럼: code, name (종목코드, 종목명)

        Returns:
            BacktestResult
        """
        if data.empty:
            raise ValueError("Empty data provided")

        self._reset()

        # 데이터 정렬
        data = data.sort_values("datetime").reset_index(drop=True)

        start_date = data["datetime"].iloc[0]
        end_date = data["datetime"].iloc[-1]

        logger.info(f"Starting backtest: {len(data)} bars")
        logger.info(f"Period: {start_date} ~ {end_date}")

        # 메인 루프
        for idx, row in data.iterrows():
            bar = row.to_dict()
            self._process_bar(bar)

        # 마지막 포지션 강제 청산
        if self.positions:
            last_bar = data.iloc[-1].to_dict()
            for code in list(self.positions.keys()):
                self._close_position(
                    code=code,
                    exit_price=last_bar["close"],
                    exit_time=last_bar["datetime"],
                    reason=ExitReason.END_OF_DATA,
                )

        # 마지막 일 수익률 기록
        if self._current_day_pnl != 0:
            self.daily_returns.append(self._current_day_pnl)

        # 결과 생성
        return self._generate_result(data)

    def _process_bar(self, bar: dict[str, Any]):
        """바 데이터 처리"""
        timestamp = bar["datetime"]
        current_price = bar["close"]
        code = bar.get("code", "DEFAULT")
        name = bar.get("name", code)

        # 일자 변경 체크
        if self._last_date and timestamp.date() != self._last_date.date():
            if self._current_day_pnl != 0:
                self.daily_returns.append(self._current_day_pnl)
            self._current_day_pnl = 0.0
            self._daily_trades = 0

        self._last_date = timestamp

        # 자산 곡선 기록
        total_equity = self._calculate_total_equity(current_price)
        self.equity_curve.append((timestamp, total_equity))

        # 1. 기존 포지션 리스크 체크
        for pos_code in list(self.positions.keys()):
            pos = self.positions[pos_code]
            pos.bars_held += 1

            # 최고/최저가 업데이트
            if current_price > pos.highest_price:
                pos.highest_price = current_price
            if current_price < pos.lowest_price or pos.lowest_price == 0:
                pos.lowest_price = current_price

            # 리스크 체크
            exit_reason = self._check_risk(pos, current_price, timestamp)
            if exit_reason:
                self._close_position(
                    code=pos_code,
                    exit_price=current_price,
                    exit_time=timestamp,
                    reason=exit_reason,
                )
                continue

        # 2. 일별 거래 한도 체크
        risk = self.config.risk
        if risk.max_daily_trades > 0 and self._daily_trades >= risk.max_daily_trades:
            return

        # 3. Sync position state to adapter (for RL strategies)
        if hasattr(self.strategy, "set_position"):
            if self.positions:
                pos = next(iter(self.positions.values()))
                if pos.side == "BUY":
                    unrealized_pnl = (current_price - pos.entry_price) * pos.quantity
                else:
                    unrealized_pnl = (pos.entry_price - current_price) * pos.quantity
                self.strategy.set_position(
                    {
                        "side": pos.side,
                        "entry_price": pos.entry_price,
                        "quantity": pos.quantity,
                        "unrealized_pnl": unrealized_pnl,
                    }
                )
            else:
                self.strategy.set_position(None)

        # 전략 시그널 생성
        signal = self.strategy.on_bar(bar)

        # 4. 시그널 처리
        if not self.positions:
            # 포지션 없음 → 진입
            if signal == SignalType.BUY:
                self._open_position(
                    code=code,
                    name=name,
                    side="BUY",
                    price=current_price,
                    timestamp=timestamp,
                    bar=bar,
                )
            elif signal == SignalType.SELL:
                self._open_position(
                    code=code,
                    name=name,
                    side="SELL",
                    price=current_price,
                    timestamp=timestamp,
                    bar=bar,
                )
        else:
            # 포지션 있음 → 반대 시그널 시 청산
            for pos_code, pos in list(self.positions.items()):
                should_close = (pos.side == "BUY" and signal == SignalType.SELL) or (
                    pos.side == "SELL" and signal == SignalType.BUY
                )
                if should_close:
                    self._close_position(
                        code=pos_code,
                        exit_price=current_price,
                        exit_time=timestamp,
                        reason=ExitReason.SIGNAL,
                    )

    def _check_risk(
        self, pos: Position, current_price: float, timestamp: datetime
    ) -> ExitReason | None:
        """리스크 체크"""
        risk = self.config.risk

        # PnL 계산
        if pos.side == "BUY":
            pnl_pct = (current_price - pos.entry_price) / pos.entry_price * 100
        else:
            pnl_pct = (pos.entry_price - current_price) / pos.entry_price * 100

        # 1. 손절 (ATR 기반 또는 고정 %)
        if risk.use_atr_stop and pos.atr_at_entry > 0:
            atr_stop_distance = pos.atr_at_entry * risk.atr_stop_multiplier
            if pos.side == "BUY":
                stop_price = pos.entry_price - atr_stop_distance
                if current_price <= stop_price:
                    return ExitReason.STOP_LOSS
            else:
                stop_price = pos.entry_price + atr_stop_distance
                if current_price >= stop_price:
                    return ExitReason.STOP_LOSS
        elif pnl_pct <= -risk.stop_loss_pct:
            return ExitReason.STOP_LOSS

        # 2. 익절
        if pnl_pct >= risk.take_profit_pct:
            return ExitReason.TAKE_PROFIT

        # 3. 트레일링 스탑
        if risk.trailing_stop_enabled:
            if pnl_pct >= risk.trailing_stop_trigger_pct:
                # 트레일링 스탑 발동
                if pos.side == "BUY":
                    trailing_stop_price = pos.highest_price * (
                        1 - risk.trailing_stop_distance_pct / 100
                    )
                    if current_price <= trailing_stop_price:
                        return ExitReason.TRAILING_STOP
                else:
                    trailing_stop_price = pos.lowest_price * (
                        1 + risk.trailing_stop_distance_pct / 100
                    )
                    if current_price >= trailing_stop_price:
                        return ExitReason.TRAILING_STOP

        # 4. 시간 제한
        if risk.max_hold_bars > 0 and pos.bars_held >= risk.max_hold_bars:
            return ExitReason.TIME_LIMIT

        # 5. 강제 청산 시간
        if risk.force_close_time:
            hour, minute = map(int, risk.force_close_time.split(":"))
            if timestamp.hour >= hour and timestamp.minute >= minute:
                return ExitReason.FORCE_CLOSE

        return None

    def _open_position(
        self,
        code: str,
        name: str,
        side: str,
        price: float,
        timestamp: datetime,
        bar: dict[str, Any] | None = None,
    ):
        """포지션 진입"""
        # 최대 포지션 수 체크
        if len(self.positions) >= self.config.max_positions:
            return

        # 포지션 크기 계산
        cost = self.config.cost

        if self.config.point_value > 1:
            # 선물: 계약 수 기반 (max_positions = 최대 계약 수)
            quantity = self.config.max_positions
            # 선물 증거금은 notional의 일부이므로 capital 차감은 진입가 * 수량만 적용
            commission = price * quantity * cost.commission_rate
            slippage = price * quantity * cost.slippage_rate
            total_cost = price * quantity + commission + slippage
        else:
            # 주식: 자본 대비 % 기반
            position_value = self.capital * (self.config.position_size_pct / 100)
            effective_price = price * (1 + cost.commission_rate + cost.slippage_rate)
            quantity = int(position_value / effective_price)

            if quantity < 1:
                return

            commission = price * quantity * cost.commission_rate
            slippage = price * quantity * cost.slippage_rate
            total_cost = price * quantity + commission + slippage

            if total_cost > self.capital:
                return

        # 포지션 생성
        atr_value = float(bar.get("atr", 0)) if bar else 0.0
        position = Position(
            code=code,
            name=name,
            strategy=self.strategy.name,
            side=side,
            entry_time=timestamp,
            entry_price=price,
            quantity=quantity,
            highest_price=price,
            lowest_price=price,
            atr_at_entry=atr_value,
        )

        self.positions[code] = position
        self.capital -= total_cost
        self._daily_trades += 1

        if self.config.verbose:
            logger.info(
                f"[{timestamp}] OPEN {side}: {name} "
                f"@ {price:,.0f} x {quantity} (cost: {total_cost:,.0f})"
            )

    def _close_position(
        self,
        code: str,
        exit_price: float,
        exit_time: datetime,
        reason: ExitReason,
    ):
        """포지션 청산"""
        if code not in self.positions:
            return

        pos = self.positions[code]

        # 비용 계산
        cost = self.config.cost
        revenue = exit_price * pos.quantity
        commission = revenue * cost.commission_rate
        slippage = revenue * cost.slippage_rate

        # 매도세 (주식만)
        tax = 0.0
        if pos.side == "BUY" and cost.tax_rate > 0:
            tax = revenue * cost.tax_rate

        total_cost = commission + slippage + tax
        net_revenue = revenue - total_cost

        # PnL 계산
        if pos.side == "BUY":
            pnl = net_revenue - (pos.entry_price * pos.quantity)
            pnl_pct = (exit_price - pos.entry_price) / pos.entry_price * 100
        else:
            # SHORT
            pnl = (pos.entry_price * pos.quantity) - net_revenue
            pnl_pct = (pos.entry_price - exit_price) / pos.entry_price * 100

        # 포인트 가치 적용 (선물용)
        pnl = pnl * self.config.point_value

        # 자본 업데이트
        self.capital += net_revenue

        # 일별 PnL 누적
        self._current_day_pnl += pnl

        # 청산 사유 기록
        reason_name = reason.value
        self.exit_reasons[reason_name] = self.exit_reasons.get(reason_name, 0) + 1

        # 거래 기록 생성
        trade = BacktestTrade(
            code=pos.code,
            name=pos.name,
            strategy=pos.strategy,
            side=pos.side,
            entry_time=pos.entry_time,
            exit_time=exit_time,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=pos.quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            commission=commission + tax,
            exit_reason=reason_name,
        )

        self.trades.append(trade)

        # 포지션 제거
        del self.positions[code]

        if self.config.verbose:
            logger.info(
                f"[{exit_time}] CLOSE ({reason_name}): {pos.name} "
                f"@ {exit_price:,.0f} PnL: {pnl:+,.0f} ({pnl_pct:+.2f}%)"
            )

    def _calculate_total_equity(self, current_price: float) -> float:
        """총 자산 계산"""
        equity = self.capital

        for pos in self.positions.values():
            if pos.side == "BUY":
                equity += current_price * pos.quantity
            else:
                # SHORT: 진입 시 자본에서 빠져나간 금액 + 미실현 손익
                unrealized_pnl = (pos.entry_price - current_price) * pos.quantity
                equity += pos.entry_price * pos.quantity + unrealized_pnl

        return equity

    def _generate_result(self, data: pd.DataFrame) -> BacktestResult:
        """백테스트 결과 생성"""
        start_date = data["datetime"].iloc[0]
        end_date = data["datetime"].iloc[-1]
        total_bars = len(data)

        # 기본 수익률
        initial = self.config.initial_capital
        final = self.capital
        total_return_pct = (final - initial) / initial * 100
        total_pnl = final - initial

        # 연환산 수익률
        days = (end_date - start_date).days
        if days > 0:
            years = days / 365.0
            annualized_return = ((final / initial) ** (1 / years) - 1) * 100
        else:
            annualized_return = 0.0

        # 거래 통계
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # 손익 통계
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [t.pnl for t in self.trades if t.pnl < 0]

        avg_profit = float(np.mean(wins)) if wins else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0

        total_profit = sum(wins) if wins else 0.0
        total_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else float("inf")

        # 평균 보유 기간
        holding_days = [
            (t.exit_time - t.entry_time).total_seconds() / 86400
            for t in self.trades
            if t.exit_time
        ]
        avg_holding_days = float(np.mean(holding_days)) if holding_days else 0.0

        # 리스크 지표
        max_drawdown = self._calculate_max_drawdown()
        sharpe_ratio = self._calculate_sharpe_ratio()
        sortino_ratio = self._calculate_sortino_ratio()

        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            total_bars=total_bars,
            initial_capital=initial,
            final_capital=final,
            total_return_pct=total_return_pct,
            total_pnl=total_pnl,
            annualized_return=annualized_return,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            avg_holding_days=avg_holding_days,
            max_drawdown_pct=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            exit_reasons=self.exit_reasons,
            equity_curve=self.equity_curve,
            trades=self.trades,
        )

    def _calculate_max_drawdown(self) -> float:
        """최대 낙폭 계산"""
        if not self.equity_curve:
            return 0.0

        values = [v for _, v in self.equity_curve]
        peak = values[0]
        max_dd = 0.0

        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.03) -> float:
        """샤프 비율 계산"""
        if len(self.daily_returns) < 2:
            return 0.0

        returns = np.array(self.daily_returns)
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return == 0:
            return 0.0

        daily_rf = risk_free_rate / 252
        sharpe = (mean_return - daily_rf) / std_return

        # 연환산
        return float(sharpe * np.sqrt(252))

    def _calculate_sortino_ratio(self, risk_free_rate: float = 0.03) -> float:
        """소르티노 비율 계산"""
        if len(self.daily_returns) < 2:
            return 0.0

        returns = np.array(self.daily_returns)
        mean_return = np.mean(returns)

        # 하방 수익률만
        negative_returns = returns[returns < 0]
        if len(negative_returns) < 2:
            return float("inf") if mean_return > 0 else 0.0

        downside_std = np.std(negative_returns, ddof=1)

        if downside_std == 0:
            return 0.0

        daily_rf = risk_free_rate / 252
        sortino = (mean_return - daily_rf) / downside_std

        return float(sortino * np.sqrt(252))


# 테스트용 간단 전략
class SimpleMAStrategy:
    """간단한 이동평균 교차 전략 (테스트용)"""

    name = "SimpleMA"

    def __init__(self, short_period: int = 5, long_period: int = 20):
        self.short_period = short_period
        self.long_period = long_period
        self.prices: list[float] = []

    def on_bar(self, bar: dict[str, Any]) -> SignalType:
        self.prices.append(bar["close"])

        if len(self.prices) < self.long_period:
            return SignalType.HOLD

        short_ma = np.mean(self.prices[-self.short_period :])
        long_ma = np.mean(self.prices[-self.long_period :])

        if short_ma > long_ma:
            return SignalType.BUY
        elif short_ma < long_ma:
            return SignalType.SELL
        else:
            return SignalType.HOLD
