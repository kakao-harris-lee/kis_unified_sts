"""RL 관측값 빌더 단위 테스트

build_rl_observation 함수의 핵심 동작 검증:
- 관측값 shape (31,) 검증
- 관측값 dtype float32 검증
- 시장 피처(25) + 포지션 피처(3) + 시간 피처(3) 구조 검증
- 다양한 입력 조건에서 일관성 검증
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import numpy as np
import pytest

from shared.strategy.rl_model_helpers import build_rl_observation


@pytest.fixture
def mock_env_config():
    """테스트용 환경 설정 모형"""
    config = MagicMock()
    config.market_open = "09:00"
    config.market_close = "15:45"
    config.initial_balance = 100_000_000
    config.max_contracts = 1
    return config


@pytest.fixture
def sample_market_data():
    """샘플 시장 데이터"""
    return {
        "code": "101S6000",
        "name": "KOSPI200 Futures",
        "close": 350.0,
        "open": 349.5,
        "high": 351.0,
        "low": 349.0,
        "volume": 10000,
    }


@pytest.fixture
def sample_indicators():
    """샘플 지표 데이터 (일부 RL 피처 포함)"""
    return {
        "returns": 0.001,
        "ma_ratio_5": 1.02,
        "ma_ratio_10": 1.01,
        "ma_ratio_20": 1.00,
        "rsi": 55.0,
        "bb_position": 0.6,
        "volume_ratio": 1.5,
        "volatility": 0.015,
        "hl_range": 0.005,
        "candle_body": 0.3,
        "macd": 0.5,
        "macd_signal": 0.3,
        "macd_hist": 0.2,
        "sma_ratio_60": 1.01,
        "sma_ratio_120": 0.99,
        "ema_ratio_5": 1.02,
        "ema_ratio_10": 1.01,
        "ema_ratio_20": 1.00,
        "bb_upper_dist": 0.02,
        "bb_lower_dist": 0.01,
        "bb_width": 0.05,
        "atr": 2.5,
        "stoch_k": 60.0,
        "stoch_d": 55.0,
        "price_change_5": 0.002,
    }


class TestObservationShape:
    """관측값 shape 테스트"""

    def test_observation_shape_is_31(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """관측값 shape는 (31,): 25 시장 + 3 포지션 + 3 시간"""
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        assert obs is not None, "Observation should not be None"
        assert obs.shape == (31,), f"Expected shape (31,), got {obs.shape}"

    def test_observation_dtype_is_float32(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """관측값 dtype은 float32"""
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        assert obs is not None
        assert obs.dtype == np.float32, f"Expected dtype float32, got {obs.dtype}"

    def test_observation_with_long_position(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """롱 포지션 보유 시 관측값 shape 검증"""
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=1.0,  # long
            contracts=1.0,
            unrealized_pnl=50000.0,
            timestamp=datetime(2026, 3, 7, 10, 30, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        assert obs is not None
        assert obs.shape == (31,)
        assert obs.dtype == np.float32

    def test_observation_with_short_position(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """숏 포지션 보유 시 관측값 shape 검증"""
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=-1.0,  # short
            contracts=1.0,
            unrealized_pnl=-30000.0,
            timestamp=datetime(2026, 3, 7, 11, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        assert obs is not None
        assert obs.shape == (31,)
        assert obs.dtype == np.float32

    def test_observation_with_scaler(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """스케일러 사용 시 관측값 shape 유지"""
        mock_scaler = MagicMock()
        mock_scaler.transform = lambda x: x * 0.5  # Simple scaling

        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=mock_scaler,
            env_config=mock_env_config,
        )

        assert obs is not None
        assert obs.shape == (31,)
        assert obs.dtype == np.float32


class TestObservationStructure:
    """관측값 내부 구조 테스트"""

    def test_position_features_at_correct_indices(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """포지션 피처는 인덱스 25:28에 위치"""
        position_side = 1.0
        contracts = 0.5
        unrealized_pnl = 25000.0

        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=position_side,
            contracts=contracts,
            unrealized_pnl=unrealized_pnl,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        # 포지션 피처: obs[25:28]
        assert obs[25] == pytest.approx(
            position_side
        ), f"Position side mismatch: {obs[25]} != {position_side}"
        assert obs[26] == pytest.approx(
            contracts
        ), f"Contracts mismatch: {obs[26]} != {contracts}"
        assert obs[27] == pytest.approx(
            unrealized_pnl
        ), f"Unrealized PnL mismatch: {obs[27]} != {unrealized_pnl}"

    def test_time_features_at_correct_indices(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """시간 피처는 인덱스 28:31에 위치"""
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        # 시간 피처: obs[28:31] = [progress, sin(progress), cos(progress)]
        time_features = obs[28:31]
        assert len(time_features) == 3, "Should have 3 time features"

        # progress는 0.0 ~ 1.0 범위
        progress = time_features[0]
        assert 0.0 <= progress <= 1.0, f"Progress out of range: {progress}"

        # sin/cos는 -1.0 ~ 1.0 범위
        sin_val = time_features[1]
        cos_val = time_features[2]
        assert -1.0 <= sin_val <= 1.0, f"Sin value out of range: {sin_val}"
        assert -1.0 <= cos_val <= 1.0, f"Cos value out of range: {cos_val}"

    def test_market_features_first_25_elements(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """시장 피처는 처음 25개 요소에 위치"""
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        # 시장 피처: obs[0:25]
        market_features = obs[:25]
        assert len(market_features) == 25, "Should have 25 market features"

        # 모든 시장 피처는 finite 값이어야 함
        assert np.all(np.isfinite(market_features)), "All market features should be finite"


class TestObservationConsistency:
    """관측값 일관성 테스트"""

    def test_flat_position_features_are_zero(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """포지션 없을 때 포지션 피처는 0"""
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        position_features = obs[25:28]
        np.testing.assert_array_almost_equal(
            position_features, [0.0, 0.0, 0.0], err_msg="Flat position features should be all zeros"
        )

    def test_time_features_at_market_open(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """장 시작 시 시간 피처: progress≈0, sin≈0, cos≈1"""
        # 09:00 (market open)
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 9, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        time_features = obs[28:31]
        # progress should be close to 0 at market open
        assert time_features[0] == pytest.approx(
            0.0, abs=0.01
        ), f"Progress should be ~0 at market open, got {time_features[0]}"
        # sin(0) ≈ 0
        assert time_features[1] == pytest.approx(
            0.0, abs=0.01
        ), f"Sin(0) should be ~0, got {time_features[1]}"
        # cos(0) ≈ 1
        assert time_features[2] == pytest.approx(
            1.0, abs=0.01
        ), f"Cos(0) should be ~1, got {time_features[2]}"

    def test_time_features_at_market_close(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """장 마감 시 시간 피처: progress≈1, sin≈0, cos≈1"""
        # 15:45 (market close)
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 15, 45, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        time_features = obs[28:31]
        # progress should be close to 1 at market close
        assert time_features[0] == pytest.approx(
            1.0, abs=0.01
        ), f"Progress should be ~1 at market close, got {time_features[0]}"

    def test_observation_all_values_finite(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """모든 관측값은 유한한 값이어야 함"""
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        assert np.all(np.isfinite(obs)), "All observation values should be finite (no NaN/Inf)"


class TestObservationEdgeCases:
    """관측값 엣지 케이스 테스트"""

    def test_missing_indicators_filled_with_zero(
        self, mock_env_config, sample_market_data
    ):
        """지표 누락 시 0으로 채워짐"""
        # 빈 indicators 제공
        empty_indicators = {}

        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=empty_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        assert obs is not None
        assert obs.shape == (31,)
        assert obs.dtype == np.float32

        # 시장 피처는 대부분 0으로 채워져야 함 (일부는 market_data에서 fallback 가능)
        market_features = obs[:25]
        assert np.all(np.isfinite(market_features)), "Missing indicators should be filled with finite values"

    def test_ohlcv_derived_fallback(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """ohlcv_derived 파라미터로 fallback 제공"""
        # indicators에서 일부 피처 제거
        partial_indicators = {"rsi": 50.0, "bb_position": 0.5}

        # ohlcv_derived로 누락된 피처 제공
        ohlcv_derived = {
            "returns": 0.001,
            "ma_ratio_5": 1.0,
            "volatility": 0.01,
        }

        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=partial_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
            ohlcv_derived=ohlcv_derived,
        )

        assert obs is not None
        assert obs.shape == (31,)
        assert obs.dtype == np.float32

    def test_negative_unrealized_pnl(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """손실 상태(음수 PnL) 처리"""
        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=1.0,
            contracts=1.0,
            unrealized_pnl=-100000.0,  # 큰 손실
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        assert obs is not None
        assert obs.shape == (31,)
        assert obs[27] == pytest.approx(-100000.0), "Negative PnL should be preserved"

    def test_extreme_market_conditions(
        self, mock_env_config, sample_market_data
    ):
        """극단적 시장 조건 (높은 변동성, 극단 RSI 등)"""
        extreme_indicators = {
            "returns": 0.05,  # 5% 변동
            "rsi": 95.0,  # 과매수
            "bb_position": 1.2,  # BB 밴드 밖
            "volatility": 0.10,  # 높은 변동성
            "volume_ratio": 10.0,  # 거래량 급증
        }

        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=extreme_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=None,
            env_config=mock_env_config,
        )

        assert obs is not None
        assert obs.shape == (31,)
        assert np.all(np.isfinite(obs)), "Extreme values should still produce finite observation"


class TestObservationWithScaler:
    """스케일러 적용 테스트"""

    def test_scaler_clips_to_range(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """스케일러 적용 후 -5.0 ~ 5.0 범위로 클리핑"""
        # 극단값을 반환하는 mock scaler
        mock_scaler = MagicMock()

        def extreme_transform(x):
            # 일부 값을 극단으로 변환
            result = x.copy()
            result[0, 0] = 100.0  # Will be clipped to 5.0
            result[0, 1] = -100.0  # Will be clipped to -5.0
            return result

        mock_scaler.transform = extreme_transform

        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=mock_scaler,
            env_config=mock_env_config,
        )

        # 시장 피처(처음 25개)는 -5.0 ~ 5.0 범위
        market_features = obs[:25]
        assert np.all(market_features >= -5.0), "Scaled features should be >= -5.0"
        assert np.all(market_features <= 5.0), "Scaled features should be <= 5.0"

    def test_scaler_error_fallback_to_raw(
        self, mock_env_config, sample_market_data, sample_indicators
    ):
        """스케일러 에러 시 원본 피처 사용"""
        mock_scaler = MagicMock()
        mock_scaler.transform.side_effect = RuntimeError("Scaler failed")

        obs = build_rl_observation(
            market_data=sample_market_data,
            indicators=sample_indicators,
            position_side=0.0,
            contracts=0.0,
            unrealized_pnl=0.0,
            timestamp=datetime(2026, 3, 7, 10, 0, 0),
            scaler=mock_scaler,
            env_config=mock_env_config,
        )

        # 에러가 발생해도 관측값은 정상 생성되어야 함
        assert obs is not None
        assert obs.shape == (31,)
        assert obs.dtype == np.float32
