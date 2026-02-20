"""RL M-PPO 청산 전략

학습된 Maskable PPO 모델의 EXIT 행동(LONG_EXIT=1, SHORT_EXIT=3)을 사용.
모델의 Sharpe 3.19는 진입+청산을 동시 최적화한 결과이므로 학습된 청산 타이밍을 복원.

안전장치:
    1. Hard stop (최우선) — 학습 시 허용한 것보다 넓은 -3%
    2. EOD close — 장 마감 전 포지션 정리
    3. RL 모델 예측 — 학습된 청산 정책

Usage:
    strategy = StrategyFactory.create_from_file("futures", "rl_mppo")
    # exit.type: rl_mppo_exit in YAML
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from shared.ml.base import get_device
from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator
from shared.strategy.market_data import get_price_from_snapshot, get_symbol_snapshot
from shared.strategy.market_time import now_kst
from shared.strategy.rl_model_helpers import (
    build_rl_observation,
    derive_features_from_ohlcv,
    get_action_confidence,
    get_rl_env_config,
    load_rl_model,
    load_rl_scaler,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


@dataclass
class RLMPPOExitConfig:
    """RL M-PPO 청산 전략 설정"""

    model_path: str = "models/futures/rl/mppo_best/best_model.zip"
    deterministic: bool = True
    device: str = "auto"
    scaler_path: str = ""
    min_exit_confidence: float = 0.5  # entry(0.6)보다 낮음 — 청산은 더 적극적
    backtest_min_exit_confidence: float = 0.3
    # 안전장치
    hard_stop_pct: float = -0.03  # -3%
    eod_close_hour: int = 15
    eod_close_minute: int = 15


class RLMPPOExit(ExitSignalGenerator[RLMPPOExitConfig]):
    """학습된 M-PPO 모델 기반 청산 시그널 생성기

    행동 매핑:
        1 (LONG_EXIT)  → long 포지션 청산
        3 (SHORT_EXIT) → short 포지션 청산
        4 (HOLD)       → 유지
    """

    CONFIG_CLASS = RLMPPOExitConfig

    def __init__(self, config: RLMPPOExitConfig):
        super().__init__(config)
        self._model = None
        self._scaler = None
        self._device = get_device(config.device)
        self._env_config = None

    def _validate_config(self) -> None:
        assert 0.0 <= self.config.min_exit_confidence <= 1.0, (
            "min_exit_confidence must be between 0.0 and 1.0"
        )
        assert self.config.hard_stop_pct < 0, "hard_stop_pct must be negative"

    @property
    def name(self) -> str:
        return "rl_mppo_exit"

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, Optional[ExitSignal]]:
        """단일 포지션 청산 여부 판단"""
        position = context.position
        price = self._get_current_price(position, context.market_data)
        if price is None:
            return (False, None)

        now = context.timestamp

        # 1. 안전장치: hard stop (최우선)
        profit_pct = self._calc_profit_pct(position, price)
        if profit_pct <= self.config.hard_stop_pct:
            return (
                True,
                self._make_signal(
                    position=position,
                    price=price,
                    profit_pct=profit_pct,
                    reason=ExitReason.STOP_LOSS,
                    confidence=1.0,
                    priority=1,
                    now=now,
                ),
            )

        # 2. 안전장치: EOD close
        if self._is_eod(now):
            return (
                True,
                self._make_signal(
                    position=position,
                    price=price,
                    profit_pct=profit_pct,
                    reason=ExitReason.EOD_CLOSE,
                    confidence=1.0,
                    priority=1,
                    now=now,
                ),
            )

        # 3. RL 모델 예측
        model = self._load_model()
        if model is None:
            return (False, None)

        obs = self._build_observation(position, context)
        if obs is None:
            return (False, None)

        masks = self._build_exit_masks(position)

        try:
            action, _states = model.predict(
                obs,
                deterministic=self.config.deterministic,
                action_masks=masks,
            )
            action = int(action)
        except Exception as e:
            logger.warning(f"RL exit model prediction failed: {e}")
            return (False, None)

        confidence = get_action_confidence(model, obs, action, masks, self._device)

        exit_threshold = (
            self.config.backtest_min_exit_confidence
            if context.metadata.get("is_backtest")
            else self.config.min_exit_confidence
        )

        # LONG_EXIT for long position
        if action == 1 and position.side == PositionSide.LONG:
            if confidence >= exit_threshold:
                return (
                    True,
                    self._make_signal(
                        position=position,
                        price=price,
                        profit_pct=profit_pct,
                        reason=ExitReason.RL_EXIT,
                        confidence=confidence,
                        priority=2,
                        now=now,
                    ),
                )
            else:
                logger.debug(
                    f"RL LONG_EXIT confidence {confidence:.3f} "
                    f"below threshold {exit_threshold}"
                )

        # SHORT_EXIT for short position
        if action == 3 and position.side == PositionSide.SHORT:
            if confidence >= exit_threshold:
                return (
                    True,
                    self._make_signal(
                        position=position,
                        price=price,
                        profit_pct=profit_pct,
                        reason=ExitReason.RL_EXIT,
                        confidence=confidence,
                        priority=2,
                        now=now,
                    ),
                )
            else:
                logger.debug(
                    f"RL SHORT_EXIT confidence {confidence:.3f} "
                    f"below threshold {exit_threshold}"
                )

        return (False, None)  # HOLD

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: Optional[Any] = None,
    ) -> list[ExitSignal]:
        """여러 포지션에 대해 청산 시그널 스캔"""
        if not positions:
            return []

        signals = []
        now = now_kst()

        for position in positions:
            context = ExitContext(
                position=position,
                market_data=market_data,
                indicators=self._extract_indicators(market_data, position.code),
                timestamp=now,
                market_state=market_state,
            )
            should_exit, signal = await self.should_exit(context)
            if should_exit and signal:
                signals.append(signal)

        if signals:
            logger.info(
                f"[{self.name}] {len(signals)}/{len(positions)} positions "
                f"triggered exit signals"
            )

        return signals

    # ------------------------------------------------------------------
    # RL model interaction
    # ------------------------------------------------------------------

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        self._model = load_rl_model(self.config.model_path, self._device)
        return self._model

    def _load_scaler(self) -> Any:
        if self._scaler is not None:
            return self._scaler
        self._scaler = load_rl_scaler(self.config.scaler_path, self.config.model_path)
        return self._scaler

    def _get_env_config(self):
        if self._env_config is None:
            self._env_config = get_rl_env_config()
        return self._env_config

    def _build_observation(self, position: Position, context: ExitContext) -> Any:
        """포지션 + 시장 데이터 → 31차원 관측값"""
        env_cfg = self._get_env_config()

        # 포지션 피처
        if position.side == PositionSide.LONG:
            position_side = 1.0
        elif position.side == PositionSide.SHORT:
            position_side = -1.0
        else:
            position_side = 0.0

        contracts = position.quantity / max(env_cfg.max_contracts, 1)

        # unrealized PnL 계산
        price = position.current_price if position.current_price > 0 else position.entry_price
        if position.side == PositionSide.LONG:
            unrealized_pnl = (price - position.entry_price) * position.quantity
        else:
            unrealized_pnl = (position.entry_price - price) * position.quantity
        unrealized_pnl_norm = unrealized_pnl / env_cfg.initial_balance

        # market_data에서 지표 추출 (orchestrator가 indicators를 merge해줌)
        snapshot = get_symbol_snapshot(context.market_data, position.code)
        indicators = {**context.indicators, **snapshot}

        derived = derive_features_from_ohlcv(indicators, snapshot)
        scaler = self._load_scaler()

        return build_rl_observation(
            market_data=snapshot,
            indicators=indicators,
            position_side=position_side,
            contracts=contracts,
            unrealized_pnl=unrealized_pnl_norm,
            timestamp=context.timestamp,
            scaler=scaler,
            env_config=env_cfg,
            ohlcv_derived=derived,
        )

    def _build_exit_masks(self, position: Position) -> Any:
        """포지션 방향에 따른 청산 전용 행동 마스크"""
        import numpy as np

        masks = np.zeros(5, dtype=bool)
        masks[4] = True  # HOLD 항상 가능
        if position.side == PositionSide.LONG:
            masks[1] = True  # LONG_EXIT
        elif position.side == PositionSide.SHORT:
            masks[3] = True  # SHORT_EXIT
        return masks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_current_price(
        position: Position, market_data: dict[str, Any]
    ) -> Optional[float]:
        snapshot = get_symbol_snapshot(market_data, position.code)
        price = get_price_from_snapshot(snapshot)
        if price is not None:
            return price
        if position.current_price > 0:
            return position.current_price
        return None

    @staticmethod
    def _calc_profit_pct(position: Position, current_price: float) -> float:
        if position.entry_price <= 0:
            return 0.0
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) / position.entry_price
        return (current_price - position.entry_price) / position.entry_price

    def _is_eod(self, timestamp: datetime) -> bool:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=KST)
        t = timestamp.time()
        from datetime import time as dt_time

        eod = dt_time(self.config.eod_close_hour, self.config.eod_close_minute)
        return t >= eod

    @staticmethod
    def _extract_indicators(
        market_data: dict[str, Any], code: str
    ) -> dict[str, Any]:
        """market_data에서 코드별 지표 추출 (orchestrator가 merge한 데이터)"""
        snapshot = get_symbol_snapshot(market_data, code)
        return snapshot

    def _make_signal(
        self,
        position: Position,
        price: float,
        profit_pct: float,
        reason: ExitReason,
        confidence: float,
        priority: int,
        now: datetime,
    ) -> ExitSignal:
        profit_amount = (price - position.entry_price) * position.quantity
        if position.side == PositionSide.SHORT:
            profit_amount = (position.entry_price - price) * position.quantity

        return ExitSignal(
            code=position.code,
            name=position.name,
            position_id=position.id,
            reason=reason,
            strategy=self.name,
            current_price=price,
            exit_price=price,
            entry_price=position.entry_price,
            profit_amount=profit_amount,
            profit_pct=profit_pct,
            confidence=confidence,
            priority=priority,
            timestamp=now,
            quantity=position.quantity,
            metadata={
                "exit_type": reason.value,
                "position_side": position.side.value,
            },
        )
