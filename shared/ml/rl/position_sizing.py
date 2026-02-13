"""Kelly Criterion 기반 동적 포지션 사이징

모델 confidence × Kelly fraction으로 포지션 크기 결정.
불확실한 시그널에 대해 축소 진입, 확신 높을 때 풀 사이징.

Usage:
    sizer = KellyPositionSizer.from_yaml("ml/rl_mppo.yaml")
    scale = sizer.calculate_scale(action_probs, win_rate, wl_ratio)
    contracts = sizer.get_contracts(action_probs, win_rate, wl_ratio, max_contracts=1)
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np

from shared.config import ConfigLoader

logger = logging.getLogger(__name__)


@dataclass
class KellySizingConfig:
    """Kelly 포지션 사이징 설정"""

    enabled: bool = True
    fraction: float = 0.5           # Half-Kelly (보수적)
    min_trades: int = 10            # Kelly 적용 전 최소 거래 수
    min_scale: float = 0.2          # 최소 포지션 스케일 (이하는 거래 스킵)
    max_scale: float = 1.0          # 최대 포지션 스케일
    max_history: int = 200          # 슬라이딩 윈도우 크기
    default_win_rate: float = 0.45  # 초기 승률 추정치
    default_wl_ratio: float = 1.5   # 초기 손익비 추정치


class KellyPositionSizer:
    """Kelly Criterion 기반 포지션 사이저

    half-Kelly × confidence (엔트로피 기반)으로 포지션 크기를 결정.

    동작:
        1. 과거 거래 이력에서 승률/손익비 추정
        2. Kelly fraction 계산
        3. 모델 행동 확률의 엔트로피로 confidence 추정
        4. position_scale = kelly_fraction × confidence × half_kelly_multiplier
        5. max_contracts × position_scale = 실제 계약 수
    """

    def __init__(self, config: KellySizingConfig | None = None):
        self.config = config or KellySizingConfig()
        # 누적 거래 이력 (슬라이딩 윈도우)
        self._trade_pnls: deque[float] = deque(maxlen=self.config.max_history)

    @classmethod
    def from_yaml(cls, config_path: str = "ml/rl_mppo.yaml") -> KellyPositionSizer:
        """YAML config에서 생성"""
        data = ConfigLoader.load(config_path)
        ps_cfg = data.get("position_sizing", {})
        return cls(config=KellySizingConfig(
            enabled=ps_cfg.get("enabled", True),
            fraction=ps_cfg.get("fraction", 0.5),
            min_trades=ps_cfg.get("min_trades", 10),
            min_scale=ps_cfg.get("min_scale", 0.2),
            max_scale=ps_cfg.get("max_scale", 1.0),
            default_win_rate=ps_cfg.get("default_win_rate", 0.45),
            default_wl_ratio=ps_cfg.get("default_wl_ratio", 1.5),
        ))

    def record_trade(self, pnl: float) -> None:
        """거래 결과 기록 (승률/손익비 갱신용)"""
        self._trade_pnls.append(pnl)

    def get_trade_stats(self) -> tuple[float, float]:
        """현재 승률/손익비 반환

        Returns:
            (win_rate, wl_ratio) 튜플
        """
        cfg = self.config
        if len(self._trade_pnls) < cfg.min_trades:
            return cfg.default_win_rate, cfg.default_wl_ratio

        wins = [p for p in self._trade_pnls if p > 0]
        losses = [abs(p) for p in self._trade_pnls if p < 0]

        win_rate = len(wins) / len(self._trade_pnls) if self._trade_pnls else cfg.default_win_rate
        avg_win = np.mean(wins) if wins else 1.0
        avg_loss = np.mean(losses) if losses else 1.0
        wl_ratio = avg_win / avg_loss if avg_loss > 0 else cfg.default_wl_ratio

        return win_rate, wl_ratio

    @staticmethod
    def kelly_fraction(win_rate: float, wl_ratio: float) -> float:
        """순수 Kelly fraction 계산

        f* = (p * b - q) / b
        where p = win_rate, q = 1 - p, b = wl_ratio

        Returns:
            Kelly fraction (음수 가능 = 거래 스킵 의미)
        """
        if wl_ratio <= 0:
            return 0.0
        q = 1.0 - win_rate
        return (win_rate * wl_ratio - q) / wl_ratio

    @staticmethod
    def entropy_confidence(action_probs: np.ndarray) -> float:
        """행동 확률의 엔트로피로 confidence 계산

        confidence = 1 - (H / H_max)
        H_max = log(n_actions)

        Args:
            action_probs: 행동별 확률 배열 (valid actions만)

        Returns:
            confidence ∈ [0, 1]
        """
        probs = np.clip(action_probs, 1e-10, 1.0)
        probs = probs / probs.sum()  # 정규화
        entropy = -np.sum(probs * np.log(probs))
        max_entropy = np.log(len(probs))

        if max_entropy <= 0:
            return 1.0

        return float(np.clip(1.0 - entropy / max_entropy, 0.0, 1.0))

    def calculate_scale(
        self,
        action_probs: np.ndarray | None = None,
        win_rate: float | None = None,
        wl_ratio: float | None = None,
    ) -> float:
        """포지션 스케일 계산

        Args:
            action_probs: 행동 확률 (None이면 confidence=1.0)
            win_rate: 승률 (None이면 이력에서 추정)
            wl_ratio: 손익비 (None이면 이력에서 추정)

        Returns:
            position_scale ∈ [0, max_scale]
        """
        cfg = self.config

        if not cfg.enabled:
            return cfg.max_scale

        # 승률/손익비 결정
        if win_rate is None or wl_ratio is None:
            wr, wlr = self.get_trade_stats()
            win_rate = wr if win_rate is None else win_rate
            wl_ratio = wlr if wl_ratio is None else wl_ratio

        # Kelly fraction (half-Kelly)
        kelly = self.kelly_fraction(win_rate, wl_ratio)
        half_kelly = kelly * cfg.fraction

        # 음수 Kelly = 기대값 마이너스 → 거래 안 함
        if half_kelly <= 0:
            return 0.0

        # Confidence (엔트로피 기반)
        if action_probs is not None:
            confidence = self.entropy_confidence(action_probs)
        else:
            confidence = 1.0

        scale = half_kelly * confidence
        return float(np.clip(scale, 0.0, cfg.max_scale))

    def get_contracts(
        self,
        max_contracts: int,
        action_probs: np.ndarray | None = None,
        win_rate: float | None = None,
        wl_ratio: float | None = None,
    ) -> int:
        """실제 계약 수 결정

        Args:
            max_contracts: 최대 계약 수
            action_probs: 행동 확률
            win_rate: 승률
            wl_ratio: 손익비

        Returns:
            계약 수 (0이면 거래 스킵)
        """
        scale = self.calculate_scale(action_probs, win_rate, wl_ratio)

        if scale < self.config.min_scale:
            return 0

        contracts = max(1, round(max_contracts * scale))
        return min(contracts, max_contracts)

    def should_trade(
        self,
        action_probs: np.ndarray | None = None,
    ) -> bool:
        """거래 여부 판단 (min_scale 기준)"""
        scale = self.calculate_scale(action_probs)
        return scale >= self.config.min_scale
