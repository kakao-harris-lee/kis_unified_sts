"""VectorbtRunner — vectorbt 기반 주식 백테스트 러너 (P3-a).

레거시 :class:`~shared.backtest.engine.BacktestEngine` 과 동일한 입력
(레지스트리 ``TradingStrategy`` 를 감싼 어댑터 + :class:`BacktestConfig` +
OHLCV DataFrame)을 받아 동일한 :class:`BacktestResult`/:class:`BacktestTrade`
계약을 vectorbt ``Portfolio`` 출력으로 채운다. 기본 경로는 여전히 legacy
엔진이며, 이 러너는 opt-in (``strategy.backtest.engine: vectorbt``) 전용이다.
plan: docs/plans/2026-07-08-new-architecture-refactoring-plan.md §5,
docs/plans/2026-07-05-indicator-engine-and-stream-schema-roadmap.md §WS-A4.

체결(fill) 모델 매핑 — 레거시 의미론과의 대응
=================================================

1. **체결 시점**: 레거시 엔진은 bar t 데이터(종가 포함)로 시그널을 만들고
   같은 bar t 의 종가로 체결한다(다음 bar 아님 — engine._process_bar 참조).
   러너는 ``Portfolio.from_orders(price=close)`` 로 동일 bar 종가 체결을
   재현한다. 진입은 레거시보다 이른 bar 에 체결될 수 없다(look-ahead 안전).
2. **look-ahead 안전 / LookaheadGuard 보존**: 시그널은 레거시와 동일한
   :class:`BacktestStrategyAdapter` 를 timestamp 순서로 한 bar 씩 먹여
   사전계산한다. 어댑터의 지표 엔진은 결정 시점 t 에서 bar ≤ t 만 관측하며
   (레거시와 bit-동일한 호출 순서), 지표 계층에 배선된 LookaheadGuard 검사도
   그대로 실행된다. 러너는 미래 구간 배열을 어떤 경로로도 선노출하지 않는다.
3. **비용 모델(한국 주식)**: 레거시는 진입 시 현금을
   ``price*qty*(1+commission+slippage)`` 만큼 차감하고, 청산 시
   ``price*qty*(1-commission-slippage-tax)`` 를 회수한다(매도세는 매도측만).
   vectorbt 의 ``fees``(비율)는 매수/매도 비대칭을 표현할 수 없으므로 주문별
   절대금액 ``fixed_fees`` 배열로 정확히 매핑한다 — 현금 흐름 기준 잔차 0
   (부동소수 결합순서 차이로 인한 ulp 수준 오차만 존재).
4. **트레이드 PnL 규약**: 레거시 ``BacktestTrade.pnl`` 은 진입측 비용을
   포함하지 않는다(자본에만 차감). vectorbt 트레이드 레코드의 pnl 은 진입
   수수료를 포함하므로 ``pnl_vbt + entry_fees`` 로 보정해 계약을 유지한다.
5. **Sharpe/Sortino**: 레거시는 "일별 실현 PnL(KRW)" 시계열로 계산하는 자체
   정의를 쓴다(수익률 아님). parity 게이트가 이 정의를 고정하므로 러너도
   동일 공식을 재현한다. vectorbt 네이티브 통계로의 전환은 legacy 경로 제거
   시(P3-b 통과 후) 별도 결정.
6. **자산 곡선 타이밍**: 레거시는 각 bar 의 주문 처리 *이전* 자본 상태를
   현재 종가로 마킹한다. vectorbt 는 주문 처리 *이후* 를 마킹하므로
   ``equity[t] = cash[t-1] + assets[t-1] * close[t]`` 시프트 재구성으로
   레거시 곡선을 복원한다(롱 전용에서 정확).

지원 범위 (미지원 → ``VectorbtNotSupportedError`` = NotImplementedError)
========================================================================

- 선물(point_value > 1), ATS 시뮬레이션, 멀티심볼 프레임, 공매도 진입.
- 상태머신형 exit (three_stage / momentum_decay 등): 허용목록
  (:data:`EXPRESSIBLE_EXIT_GENERATORS`) 밖의 exit 생성기는 전부 거부 —
  조용한 근사 금지, 호출자는 legacy 엔진으로 폴백한다.
- 동일 bar 내 *같은 포지션의* 진입+강제청산(마지막 bar 진입 → END_OF_DATA):
  ``from_orders`` 는 컬럼당 bar 당 주문 1건이므로 거부한다.
  (레거시가 허용하는 동일 bar "청산 → 재진입"은 지원한다 — 아래 참조.)

동일 bar 청산→재진입 매핑
=========================

레거시 엔진은 bar t 에서 리스크/전략 청산 후 같은 bar 의 진입 시그널로
재진입할 수 있다. vectorbt ``from_orders`` 는 컬럼당 bar 당 주문 1건이므로,
러너는 동일 심볼을 **2컬럼 그룹(cash_sharing=True)** 으로 시뮬레이션하고
충돌 bar 의 신규 진입을 반대 컬럼으로 라우팅한다. bar 내 실행 순서는
per-bar ``call_seq`` 로 "청산 컬럼 → 진입 컬럼" 을 강제해 레거시의
"매도 대금 정산 후 매수" 현금 흐름을 그대로 재현한다.

vectorbt 는 ``backtest`` extra 전용 의존성이므로 이 모듈 최상위에서
import 하지 않는다(런타임 이미지 보호). 실제 사용 지점에서 lazy import.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from shared.backtest.config import BacktestConfig
from shared.backtest.engine import (
    ExitReason,
    Position,
    SignalType,
    StrategyProtocol,
)
from shared.backtest.lookahead_guard import LookaheadGuard, LookaheadGuardMode
from shared.backtest.result import BacktestResult, BacktestTrade

logger = logging.getLogger(__name__)

# Exit 생성기 허용목록: 시그널/포지션 필드의 결정론적(무상태) 함수임이 검증된
# 것만 등재한다. 여기 없는 exit 는 stateful 이거나 parity 미검증 → legacy 폴백.
# (three_stage, momentum_decay 등 상태머신 exit 는 의도적으로 제외 — P3-c.)
EXPRESSIBLE_EXIT_GENERATORS: frozenset[str] = frozenset({"williams_r_exit"})

# 커스텀(비-TradingStrategy) 전략 객체가 러너 사용을 명시 opt-in 하는 속성.
SIGNAL_EXPRESSIBLE_ATTR = "vbt_signal_expressible"

_CROSS_CHECK_RTOL = 1e-6


class VectorbtNotSupportedError(NotImplementedError):
    """이 전략/설정 조합은 vectorbt 러너로 표현 불가 — legacy engine required."""

    def __init__(self, detail: str):
        super().__init__(f"legacy engine required: {detail}")


@dataclass
class _TradeEvent:
    """청산 시점에 확정되는 레거시 규약 트레이드 레코드(러너 내부)."""

    entry_idx: int
    exit_idx: int
    code: str
    name: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    commission: float  # 레거시 규약: 청산 수수료 + 매도세 (슬리피지 제외)
    exit_reason: str


@dataclass
class _ResolvedRun:
    """시그널/체결 해석 패스의 산출물 — vectorbt 주문 입력 + 레거시 부가 원장."""

    size: np.ndarray  # (n, 2) 주문 수량 (+매수/-매도, NaN=주문 없음)
    fixed_fees: np.ndarray  # (n, 2) 절대 비용 (수수료+슬리피지+매도세)
    call_seq: np.ndarray  # (n, 2) bar 내 컬럼 실행 순서 (청산 먼저)
    events: list[_TradeEvent]
    exit_reasons: dict[str, int]
    daily_returns: list[float]  # 레거시 정의: 일별 실현 PnL(KRW)
    final_capital: float
    closes: np.ndarray
    timestamps: list[datetime] = field(default_factory=list)
    # 일자 변경 강제청산(close_on_day_change)이 발생한 bar 의 청산 비용.
    # legacy 는 이 청산만 equity 기록 *이전에* 처리한다(다른 모든 주문은
    # equity 기록 이후) — 자산곡선 재구성 시 해당 bar 에서 비용을 차감.
    day_change_fc_fees: dict[int, float] = field(default_factory=dict)


class VectorbtRunner:
    """vectorbt ``Portfolio.from_orders`` 기반 백테스트 러너.

    :class:`BacktestEngine` 과 동일한 시그니처/계약. 시그널·체결 해석은
    레거시와 동일한 어댑터를 bar 순서로 구동하는 단일 패스로 수행하고,
    포트폴리오 원장(현금/자산/트레이드)과 자산곡선은 vectorbt 가 계산한다.

    Usage:
        runner = VectorbtRunner(adapted_strategy, config)
        result = runner.run(data)
    """

    def __init__(
        self,
        strategy: StrategyProtocol,
        config: BacktestConfig | None = None,
        *,
        gate: Any = None,
    ):
        """
        Args:
            strategy: 전략 어댑터 (BacktestEngine 과 동일 프로토콜:
                on_bar 필수, check_exit/set_position/prescan_data 선택).
            config: 백테스트 설정 (기본값은 legacy 와 동일).
            gate: Optional RegimeGate — legacy engine 과 동일 의미론.
        """
        self.strategy = strategy
        self.config = config or BacktestConfig()
        self._gate = gate

        # LookaheadGuard wiring — legacy engine 과 동일한 구성 계약 유지.
        mode = (
            self.config.lookahead_guard_mode.lower()
            if hasattr(self.config, "lookahead_guard_mode")
            else "assert"
        )
        if mode not in ("off", "warn", "assert"):
            mode = "assert"
        self.lookahead_guard = LookaheadGuard(mode=LookaheadGuardMode(mode))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, data: pd.DataFrame) -> BacktestResult:
        """백테스트 실행 — legacy ``BacktestEngine.run`` 과 동일 계약.

        Args:
            data: OHLCV DataFrame (필수: datetime/open/high/low/close/volume,
                선택: code/name). 단일 심볼 전용.

        Returns:
            BacktestResult

        Raises:
            VectorbtNotSupportedError: 전략/설정이 러너 지원 범위 밖일 때.
                호출자는 legacy 엔진으로 폴백해야 한다.
        """
        if data.empty:
            raise ValueError("Empty data provided")

        self._ensure_supported(data)

        sort_cols = ["datetime"] + (["code"] if "code" in data.columns else [])
        data = data.sort_values(sort_cols).reset_index(drop=True)

        if hasattr(self.strategy, "prescan_data"):
            self.strategy.prescan_data(data)

        logger.info(f"Starting vectorbt backtest: {len(data)} bars")

        resolved = self._resolve(data)
        portfolio = self._simulate(resolved)
        return self._build_result(data, resolved, portfolio)

    # ------------------------------------------------------------------
    # Expressibility gate
    # ------------------------------------------------------------------

    def _ensure_supported(self, data: pd.DataFrame) -> None:
        """정적으로 판별 가능한 미지원 조합을 사전 거부한다.

        어댑터 상태를 건드리기 *전에* 실행되므로, 여기서 거부되면 호출자는
        같은 어댑터 인스턴스로 legacy 엔진을 안전하게 재시도할 수 있다.
        (해석 도중 거부되는 동적 게이트 — 공매도/동일-bar 충돌 — 이후에는
        어댑터가 오염되므로 폴백 시 어댑터를 재생성해야 한다.)
        """
        if self.config.point_value > 1:
            raise VectorbtNotSupportedError(
                "futures (point_value > 1) — P3-d 선행 필요"
            )
        if self.config.ats_enabled:
            raise VectorbtNotSupportedError("ATS venue simulation")
        if "code" in data.columns:
            codes = data["code"].astype(str).fillna("DEFAULT").nunique()
            if codes > 1:
                raise VectorbtNotSupportedError(
                    "multi-symbol frame (shared-capital path) — 심볼별 프레임으로 분리 필요"
                )

        underlying = getattr(self.strategy, "_strategy", None)
        if underlying is not None and hasattr(underlying, "exit"):
            exit_name = str(
                getattr(underlying.exit, "name", type(underlying.exit).__name__)
            )
            if exit_name not in EXPRESSIBLE_EXIT_GENERATORS:
                raise VectorbtNotSupportedError(
                    f"exit generator '{exit_name}' is stateful or parity-unverified"
                )
        elif not getattr(self.strategy, SIGNAL_EXPRESSIBLE_ATTR, False):
            raise VectorbtNotSupportedError(
                "unknown strategy protocol — set "
                f"`{SIGNAL_EXPRESSIBLE_ATTR} = True` to opt in"
            )

    # ------------------------------------------------------------------
    # Signal/fill resolution pass (legacy-ordering, adapter-driven)
    # ------------------------------------------------------------------

    def _resolve(self, data: pd.DataFrame) -> _ResolvedRun:
        """어댑터를 legacy 와 동일한 bar 순서/호출 순서로 구동해 주문을 확정.

        engine._process_bar 의 단계 순서를 단일 심볼에 대해 그대로 따른다:
        (0) 일자 변경 처리 → (1a) 전략 check_exit → (1b) 엔진 리스크 안전장치
        → (2) 일별 거래 한도 → (3) set_position 동기화 → 시그널 생성 →
        gate → (4) 진입/반대시그널 청산. 비용·수량 산식도 legacy 와 동일한
        연산 순서로 계산해 bit-parity 를 유지한다.
        """
        n = len(data)
        columns = list(data.columns)
        size = np.full((n, 2), np.nan, dtype=np.float64)
        fixed_fees = np.zeros((n, 2), dtype=np.float64)
        # call_seq[i] = 각 컬럼의 bar 내 실행 순위. 기본 [0, 1] (col0 먼저);
        # 충돌 bar 에서 청산 컬럼이 1 이면 [1, 0] 으로 뒤집는다.
        call_seq = np.tile(np.array([0, 1], dtype=int), (n, 1))
        closes = data["close"].astype(float).to_numpy()

        events: list[_TradeEvent] = []
        exit_reasons: dict[str, int] = {}
        daily_returns: list[float] = []

        cost = self.config.cost
        risk = self.config.risk

        capital = self.config.initial_capital
        pos: Position | None = None
        pos_entry_idx = -1
        pos_col = 0
        last_price = 0.0
        last_date: datetime | None = None
        current_day_pnl = 0.0
        daily_trades = 0

        # StrategyProtocol 은 on_bar 만 정의 — check_exit/set_position 은
        # 선택 프로토콜이므로 Any 로 좁혀 호출 (engine 과 동일한 hasattr 계약).
        strategy: Any = self.strategy
        has_check_exit = hasattr(strategy, "check_exit")
        has_set_position = hasattr(strategy, "set_position")
        timestamps: list[datetime] = []

        def emit_order(idx: int, col: int, qty: float, fee: float, what: str) -> None:
            if not math.isnan(size[idx, col]):
                # 같은 컬럼에 bar 당 주문 2건은 표현 불가. 발생 케이스는
                # "마지막 bar 진입 → 동일 bar END_OF_DATA 강제청산" 뿐이다
                # (청산→재진입은 반대 컬럼으로 라우팅되므로 도달 불가).
                raise VectorbtNotSupportedError(
                    f"same-bar/same-position order collision at bar {idx} "
                    f"col {col} ({what})"
                )
            size[idx, col] = qty
            fixed_fees[idx, col] += fee

        day_change_fc_fees: dict[int, float] = {}

        def close_position(
            idx: int, exit_price: float, exit_time: datetime, reason: ExitReason
        ) -> float:
            """포지션 청산 (legacy 산식). 총 청산 비용(절대금액)을 반환."""
            nonlocal capital, pos, current_day_pnl
            assert pos is not None
            # legacy engine._close_position 주식 분기 산식 그대로.
            revenue = exit_price * pos.quantity
            commission = revenue * cost.commission_rate
            slippage = revenue * cost.slippage_rate
            tax = 0.0
            if pos.side == "BUY" and cost.tax_rate > 0:
                tax = revenue * cost.tax_rate
            total_cost = commission + slippage + tax
            net_revenue = revenue - total_cost
            pnl = net_revenue - (pos.entry_price * pos.quantity)
            pnl_pct = (exit_price - pos.entry_price) / pos.entry_price * 100
            capital += net_revenue
            current_day_pnl += pnl

            reason_name = reason.value
            exit_reasons[reason_name] = exit_reasons.get(reason_name, 0) + 1

            emit_order(
                idx, pos_col, -float(pos.quantity), total_cost, f"exit:{reason_name}"
            )
            events.append(
                _TradeEvent(
                    entry_idx=pos_entry_idx,
                    exit_idx=idx,
                    code=pos.code,
                    name=pos.name,
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
            )
            pos = None
            return total_cost

        def open_position(
            idx: int,
            code: str,
            name: str,
            price: float,
            timestamp: datetime,
            bar: dict[str, Any],
            entry_signal: Any,
        ) -> None:
            nonlocal capital, pos, pos_entry_idx, pos_col, daily_trades
            # legacy engine._open_position 주식 분기 산식 그대로.
            if (1 if pos is not None else 0) >= self.config.max_positions:
                return
            entry_metadata = getattr(entry_signal, "metadata", None)
            if not isinstance(entry_metadata, dict):
                entry_metadata = {}
            try:
                position_size_multiplier = float(
                    entry_metadata.get("position_size_multiplier", 1.0) or 1.0
                )
            except (TypeError, ValueError):
                position_size_multiplier = 1.0
            position_size_multiplier = max(0.0, min(1.0, position_size_multiplier))

            if (
                self.config.order_amount_per_stock
                and self.config.order_amount_per_stock > 0
            ):
                position_value = min(capital, float(self.config.order_amount_per_stock))
            else:
                position_value = capital * (self.config.position_size_pct / 100)
            position_value *= position_size_multiplier

            slippage_rate = cost.slippage_rate
            effective_price = price * (1 + cost.commission_rate + slippage_rate)
            quantity = int(position_value / effective_price)
            if quantity < 1:
                return

            commission = price * quantity * cost.commission_rate
            slippage = price * quantity * slippage_rate
            total_cost = price * quantity + commission + slippage
            if total_cost > capital:
                return

            atr_value = float(bar.get("atr", 0)) if bar else 0.0
            pos = Position(
                code=code,
                name=name,
                strategy=self.strategy.name,
                side="BUY",
                entry_time=timestamp,
                entry_price=price,
                quantity=quantity,
                highest_price=price,
                lowest_price=price,
                atr_at_entry=atr_value,
                metadata=dict(entry_metadata),
                execution_venue="KRX",
            )
            pos_entry_idx = idx
            capital -= total_cost
            daily_trades += 1
            # 이 bar 에서 이미 청산이 나갔으면(동일 bar 재진입) 반대 컬럼으로
            # 라우팅하고, call_seq 로 "청산 컬럼 먼저" 실행을 강제한다.
            entry_col = 0
            if not math.isnan(size[idx, 0]):
                entry_col = 1
            if entry_col == 1 and not math.isnan(size[idx, 1]):
                raise VectorbtNotSupportedError(f"more than two orders at bar {idx}")
            if entry_col == 0 and not math.isnan(size[idx, 1]):
                # 청산이 col1 에 있고 진입이 col0 → col1 을 먼저 실행.
                call_seq[idx] = (1, 0)
            pos_col = entry_col
            emit_order(idx, entry_col, float(quantity), commission + slippage, "entry")

        # ── 메인 루프 (engine.run / engine._process_bar 순서 그대로) ──
        for idx, bar_tuple in enumerate(data.itertuples(index=False, name=None)):
            bar = dict(zip(columns, bar_tuple))
            timestamp = bar["datetime"]
            current_price = bar["close"]
            code = str(bar.get("code", "DEFAULT") or "DEFAULT")
            name = bar.get("name", code)
            last_price = float(current_price)
            timestamps.append(timestamp)

            # 일자 변경 체크 (legacy: force close → 일별 PnL 롤오버)
            if last_date is not None and timestamp.date() != last_date.date():
                if risk.close_on_day_change and pos is not None:
                    fc_cost = close_position(
                        idx, last_price, timestamp, ExitReason.FORCE_CLOSE
                    )
                    # legacy 는 이 청산을 같은 bar 의 equity 기록 *이전에*
                    # 정산한다 — 자산곡선 재구성용으로 비용을 기록.
                    day_change_fc_fees[idx] = day_change_fc_fees.get(idx, 0.0) + fc_cost
                if current_day_pnl != 0:
                    daily_returns.append(current_day_pnl)
                current_day_pnl = 0.0
                daily_trades = 0
            last_date = timestamp

            # (equity curve 는 vectorbt cash/assets 시프트로 사후 재구성)

            # 1. 기존 포지션: 메타 업데이트 + 전략 청산 + 리스크 안전장치
            if pos is not None:
                pos.bars_held += 1
                if current_price > pos.highest_price:
                    pos.highest_price = current_price
                if current_price < pos.lowest_price or pos.lowest_price == 0:
                    pos.lowest_price = current_price

                if has_check_exit:
                    strategy.set_position(self._position_sync_dict(pos, current_price))
                    should_exit, exit_reason = strategy.check_exit(bar)
                    if should_exit and exit_reason:
                        close_position(idx, current_price, timestamp, exit_reason)

                if pos is not None:
                    risk_reason = self._check_risk(pos, current_price, timestamp)
                    if risk_reason:
                        close_position(idx, current_price, timestamp, risk_reason)

            # 2. 일별 거래 한도 (legacy 는 여기서 return — on_bar 스킵 포함)
            if risk.max_daily_trades > 0 and daily_trades >= risk.max_daily_trades:
                continue

            # 3. 포지션 상태 동기화 후 시그널 생성
            if has_set_position:
                strategy.set_position(
                    self._position_sync_dict(pos, current_price)
                    if pos is not None
                    else None
                )

            signal = self.strategy.on_bar(bar)

            if self._gate is not None and signal in (SignalType.BUY, SignalType.SELL):
                direction = "long" if signal == SignalType.BUY else "short"
                allow, _reason, _regime_pct = self._gate.allow(
                    ts=timestamp, asset=code, signal_direction=direction
                )
                if not allow:
                    signal = SignalType.HOLD

            # 4. 시그널 처리
            if pos is None:
                if signal == SignalType.BUY:
                    open_position(
                        idx,
                        code,
                        name,
                        current_price,
                        timestamp,
                        bar,
                        getattr(self.strategy, "last_entry_signal", None),
                    )
                elif signal == SignalType.SELL:
                    # legacy 는 주식 공매도 진입을 허용하지만 러너 v1 은
                    # long-only (활성 주식 전략은 전부 long-only).
                    raise VectorbtNotSupportedError(
                        "short entry (SELL while flat) — long-only runner"
                    )
            else:
                should_close = (pos.side == "BUY" and signal == SignalType.SELL) or (
                    pos.side == "SELL" and signal == SignalType.BUY
                )
                if should_close:
                    close_position(idx, current_price, timestamp, ExitReason.SIGNAL)

        # 마지막 포지션 강제 청산 (legacy: END_OF_DATA at last price)
        if pos is not None:
            last_bar_ts = data["datetime"].iloc[-1]
            close_position(n - 1, last_price, last_bar_ts, ExitReason.END_OF_DATA)

        if current_day_pnl != 0:
            daily_returns.append(current_day_pnl)

        return _ResolvedRun(
            size=size,
            fixed_fees=fixed_fees,
            call_seq=call_seq,
            events=events,
            exit_reasons=exit_reasons,
            daily_returns=daily_returns,
            final_capital=capital,
            closes=closes,
            timestamps=timestamps,
            day_change_fc_fees=day_change_fc_fees,
        )

    @staticmethod
    def _position_sync_dict(pos: Position, current_price: float) -> dict[str, Any]:
        """legacy engine 의 set_position 페이로드와 동일한 dict 구성."""
        if pos.side == "BUY":
            unrealized = (current_price - pos.entry_price) * pos.quantity
        else:
            unrealized = (pos.entry_price - current_price) * pos.quantity
        return {
            "code": pos.code,
            "side": pos.side,
            "entry_price": pos.entry_price,
            "quantity": pos.quantity,
            "unrealized_pnl": unrealized,
            "highest_price": pos.highest_price,
            "lowest_price": pos.lowest_price,
            "entry_time": pos.entry_time,
            "metadata": dict(pos.metadata or {}),
        }

    def _check_risk(
        self, pos: Position, current_price: float, timestamp: datetime
    ) -> ExitReason | None:
        """legacy engine._check_risk 산식 포팅 (종가 기준 판정/체결).

        parity 게이트(P3-b) 통과 후 legacy 이벤트 루프가 제거되면 이 사본이
        단일 소스가 된다 — 그 전까지는 tests/unit/backtest 의 parity 스위트가
        두 구현의 동등성을 고정한다.
        """
        risk = self.config.risk

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

    # ------------------------------------------------------------------
    # vectorbt simulation + result assembly
    # ------------------------------------------------------------------

    def _simulate(self, resolved: _ResolvedRun) -> Any:
        """확정 주문 배열을 vectorbt Portfolio 로 시뮬레이션.

        단일 심볼을 2컬럼(cash_sharing 그룹)으로 돌린다 — 모듈 docstring 의
        "동일 bar 청산→재진입 매핑" 참조. 두 컬럼의 close 는 동일하다.
        """
        # Lazy import — vectorbt 는 `backtest` extra 전용 (런타임 이미지 제외).
        import vectorbt as vbt

        close = pd.DataFrame(np.column_stack([resolved.closes, resolved.closes]))
        return vbt.Portfolio.from_orders(
            close,
            size=pd.DataFrame(resolved.size),
            size_type="amount",
            direction="longonly",
            price=close,
            fees=0.0,
            fixed_fees=pd.DataFrame(resolved.fixed_fees),
            slippage=0.0,
            init_cash=float(self.config.initial_capital),
            cash_sharing=True,
            group_by=True,
            call_seq=resolved.call_seq,
            allow_partial=False,
            raise_reject=True,
        )

    def _build_result(
        self, data: pd.DataFrame, resolved: _ResolvedRun, portfolio: Any
    ) -> BacktestResult:
        """vectorbt Portfolio 출력 → 레거시 BacktestResult 계약."""
        records = portfolio.trades.records
        self._cross_check(resolved, portfolio, records)

        trades = self._trades_from_records(records, resolved)
        equity_curve = self._legacy_equity_curve(resolved, portfolio)

        start_date = data["datetime"].iloc[0]
        end_date = data["datetime"].iloc[-1]
        total_bars = len(data)

        initial = self.config.initial_capital
        # 최종 자본은 resolver 원장 값(레거시와 bit-동일 연산 순서)을 쓰고,
        # vectorbt 최종 현금과의 일치는 _cross_check 에서 강제한다.
        final = resolved.final_capital
        total_return_pct = (final - initial) / initial * 100
        total_pnl = final - initial

        days = (end_date - start_date).days
        if days > 0:
            years = days / 365.0
            annualized_return = ((final / initial) ** (1 / years) - 1) * 100
        else:
            annualized_return = 0.0

        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.pnl > 0)
        losing_trades = sum(1 for t in trades if t.pnl < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl < 0]
        avg_profit = float(np.mean(wins)) if wins else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0
        total_profit = sum(wins) if wins else 0.0
        total_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else float("inf")

        holding_days = [
            (t.exit_time - t.entry_time).total_seconds() / 86400
            for t in trades
            if t.exit_time
        ]
        avg_holding_days = float(np.mean(holding_days)) if holding_days else 0.0

        max_drawdown = self._legacy_max_drawdown(equity_curve)
        sharpe_ratio = self._legacy_sharpe(resolved.daily_returns)
        sortino_ratio = self._legacy_sortino(resolved.daily_returns)

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
            exit_reasons=resolved.exit_reasons,
            equity_curve=equity_curve,
            trades=trades,
        )

    def _cross_check(
        self, resolved: _ResolvedRun, portfolio: Any, records: pd.DataFrame
    ) -> None:
        """resolver 원장과 vectorbt 원장의 구조적 일치를 강제(내부 불변식)."""
        if len(records) != len(resolved.events):
            raise RuntimeError(
                "vectorbt parity cross-check failed: trade count "
                f"{len(records)} != {len(resolved.events)}"
            )
        if len(records) and int((records["status"] != 1).sum()) != 0:
            raise RuntimeError(
                "vectorbt parity cross-check failed: open trade in records"
            )

        rec_sorted = records.sort_values(["exit_idx", "entry_idx"]).reset_index(
            drop=True
        )
        for i, event in enumerate(resolved.events):
            row = rec_sorted.iloc[i]
            ok = (
                int(row["entry_idx"]) == event.entry_idx
                and int(row["exit_idx"]) == event.exit_idx
                and int(row["size"]) == event.quantity
                and math.isclose(
                    float(row["entry_price"]), event.entry_price, rel_tol=1e-12
                )
                and math.isclose(
                    float(row["exit_price"]), event.exit_price, rel_tol=1e-12
                )
            )
            # vbt pnl 은 진입 수수료 포함 → 레거시 규약과의 관계 검증.
            legacy_pnl_from_vbt = float(row["pnl"]) + float(row["entry_fees"])
            ok = ok and math.isclose(
                legacy_pnl_from_vbt,
                event.pnl,
                rel_tol=_CROSS_CHECK_RTOL,
                abs_tol=_CROSS_CHECK_RTOL,
            )
            if not ok:
                raise RuntimeError(
                    f"vectorbt parity cross-check failed at trade {i}: "
                    f"vbt={row.to_dict()} vs event={event}"
                )

        final_cash = float(portfolio.cash().iloc[-1])
        if not math.isclose(
            final_cash,
            resolved.final_capital,
            rel_tol=_CROSS_CHECK_RTOL,
            abs_tol=max(1.0, abs(resolved.final_capital) * _CROSS_CHECK_RTOL),
        ):
            raise RuntimeError(
                "vectorbt parity cross-check failed: final cash "
                f"{final_cash} != resolver capital {resolved.final_capital}"
            )

    def _trades_from_records(
        self, records: pd.DataFrame, resolved: _ResolvedRun
    ) -> list[BacktestTrade]:
        """vbt 트레이드 레코드 + resolver 이벤트 → BacktestTrade (legacy 규약).

        가격/인덱스/수량은 vbt 레코드에서, 레거시 전용 규약 필드(pnl 의 진입비
        제외, commission=청산수수료+매도세, exit_reason)는 resolver 이벤트에서
        채운다. 두 원장의 일치는 _cross_check 가 선행 보장.
        """
        rec_sorted = records.sort_values(["exit_idx", "entry_idx"]).reset_index(
            drop=True
        )
        trades: list[BacktestTrade] = []
        for i, event in enumerate(resolved.events):
            row = rec_sorted.iloc[i]
            trades.append(
                BacktestTrade(
                    code=event.code,
                    name=event.name,
                    strategy=self.strategy.name,
                    side=event.side,
                    entry_time=event.entry_time,
                    exit_time=event.exit_time,
                    entry_price=float(row["entry_price"]),
                    exit_price=float(row["exit_price"]),
                    quantity=int(row["size"]),
                    pnl=event.pnl,
                    pnl_pct=event.pnl_pct,
                    commission=event.commission,
                    exit_reason=event.exit_reason,
                    execution_venue="KRX",
                )
            )
        return trades

    def _legacy_equity_curve(
        self, resolved: _ResolvedRun, portfolio: Any
    ) -> list[tuple[datetime, float]]:
        """레거시 자산곡선 재구성: bar t 주문 처리 *이전* 상태를 close[t] 마킹.

        vectorbt 는 주문 처리 이후(cash[t], assets[t])를 노출하므로 한 bar
        시프트해 ``cash[t-1] + assets[t-1] * close[t]`` 로 복원한다 (롱 전용
        주식 경로에서 레거시 산식과 동치; 차이는 부동소수 ulp 수준).
        """
        cash = np.asarray(portfolio.cash(), dtype=np.float64)  # 그룹 현금 (1D)
        # 2컬럼 보유수량 합 — 두 컬럼의 close 가 동일하므로 합산이 곧 총 보유.
        assets = np.asarray(portfolio.assets(), dtype=np.float64).sum(axis=1)
        closes = resolved.closes
        n = len(closes)
        equity = np.empty(n, dtype=np.float64)
        equity[0] = self.config.initial_capital
        if n > 1:
            equity[1:] = cash[:-1] + assets[:-1] * closes[1:]
        # 일자 변경 강제청산은 legacy equity 기록 *이전에* 체결됨 — 해당 bar
        # 는 "종가 마킹"이 아니라 "청산 정산 후 현금"이므로 비용을 차감한다
        # (cash[t-1] + qty*close[t] - fee == 청산 정산 후 자본).
        for idx, fee in resolved.day_change_fc_fees.items():
            equity[idx] -= fee
        return list(zip(resolved.timestamps, equity.tolist()))

    # ------------------------------------------------------------------
    # Legacy metric formulas (parity-pinned; engine._generate_result 참조)
    # ------------------------------------------------------------------

    @staticmethod
    def _legacy_max_drawdown(equity_curve: list[tuple[datetime, float]]) -> float:
        if not equity_curve:
            return 0.0
        values = [v for _, v in equity_curve]
        peak = values[0]
        max_dd = 0.0
        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @staticmethod
    def _legacy_sharpe(
        daily_returns: list[float], risk_free_rate: float = 0.03
    ) -> float:
        if len(daily_returns) < 2:
            return 0.0
        returns = np.array(daily_returns)
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        if std_return == 0:
            return 0.0
        daily_rf = risk_free_rate / 252
        sharpe = (mean_return - daily_rf) / std_return
        return float(sharpe * np.sqrt(252))

    @staticmethod
    def _legacy_sortino(
        daily_returns: list[float], risk_free_rate: float = 0.03
    ) -> float:
        if len(daily_returns) < 2:
            return 0.0
        returns = np.array(daily_returns)
        mean_return = np.mean(returns)
        negative_returns = returns[returns < 0]
        if len(negative_returns) < 2:
            return float("inf") if mean_return > 0 else 0.0
        downside_std = np.std(negative_returns, ddof=1)
        if downside_std == 0:
            return 0.0
        daily_rf = risk_free_rate / 252
        sortino = (mean_return - daily_rf) / downside_std
        return float(sortino * np.sqrt(252))
