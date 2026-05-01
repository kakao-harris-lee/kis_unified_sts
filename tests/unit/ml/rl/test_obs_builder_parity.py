"""Training-time vs runtime obs builder parity regression test.

Ensures RL live paper trading uses identical obs as the training pipeline.
Any drift indicates a coding bug that would cause model decisions to diverge
from expected distribution.

Architecture recap (confirmed by Task 2.1):
- Training path: RLFeatureCalculator.calculate(df) → RL_FEATURE_COLUMNS (25 dims)
                 → MinMaxScaler → scaled market features
- Runtime path: derive_features_from_ohlcv() → same RLFeatureCalculator.calculate()
               → build_rl_observation() applies same scaler
- Full obs shape: [scaled_market (25)] + [position (3)] + [time (3)] = 31 dims
"""
from __future__ import annotations

from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from shared.ml.rl.features import RL_FEATURE_COLUMNS, RLFeatureCalculator
from shared.strategy import rl_model_helpers
from shared.strategy.rl_model_helpers import (
    build_rl_observation,
    derive_features_from_ohlcv,
)

SAMPLE_CSV = Path(__file__).resolve().parents[4] / "data" / "kospi200f_1m_clean.csv"


@pytest.fixture(autouse=True)
def _clear_rl_caches():
    """Clear module-level caches between tests to prevent cross-contamination."""
    rl_model_helpers._scaled_market_cache.clear()
    rl_model_helpers._time_feature_cache.clear()
    yield
    rl_model_helpers._scaled_market_cache.clear()
    rl_model_helpers._time_feature_cache.clear()


@pytest.fixture(scope="module")
def recent_bars() -> pd.DataFrame:
    """Use last 200 rows from the training CSV as a realistic sample."""
    if not SAMPLE_CSV.exists():
        pytest.skip(f"Sample CSV not found at {SAMPLE_CSV}")
    df = pd.read_csv(SAMPLE_CSV).tail(200).reset_index(drop=True)
    # Ensure datetime column exists (required by RLFeatureCalculator.calculate)
    if "datetime" not in df.columns:
        df["datetime"] = pd.date_range(end="2026-04-14 15:45", periods=len(df), freq="1min")
    return df


@pytest.fixture
def mock_env_config():
    config = MagicMock()
    config.market_open = "09:00"
    config.market_close = "15:45"
    config.initial_balance = 100_000_000
    config.max_contracts = 1
    return config


# ---------------------------------------------------------------------------
# Test 1: Training obs dimension
# ---------------------------------------------------------------------------

def test_training_obs_has_expected_dimension(recent_bars):
    """RLFeatureCalculator output dim matches RL_FEATURE_COLUMNS (25)."""
    calc = RLFeatureCalculator()
    feat_df = calc.calculate(recent_bars)
    clean = feat_df[RL_FEATURE_COLUMNS].dropna()
    assert len(clean) > 0, "Sample data produced no complete feature rows"
    row = clean.iloc[-1].to_numpy()
    assert row.shape[0] == len(RL_FEATURE_COLUMNS), (
        f"Expected {len(RL_FEATURE_COLUMNS)} dims, got {row.shape[0]}"
    )
    assert len(RL_FEATURE_COLUMNS) == 25, (
        f"RL_FEATURE_COLUMNS has {len(RL_FEATURE_COLUMNS)} features, expected 25. "
        "If intentionally changed, update this assertion."
    )


# ---------------------------------------------------------------------------
# Test 2: Runtime fallback path matches training path
# ---------------------------------------------------------------------------

def test_derive_features_from_ohlcv_matches_training(recent_bars):
    """derive_features_from_ohlcv() (runtime fallback) produces same 25 raw market
    features as RLFeatureCalculator.calculate() (training path).

    This is the core parity regression. If it fails, runtime obs is using a
    different code path than training → model sees OOD inputs → performance gap.
    """
    # --- Training path ---
    calc = RLFeatureCalculator()
    trainer_df = calc.calculate(recent_bars.copy())
    trainer_clean = trainer_df[RL_FEATURE_COLUMNS].dropna()
    assert len(trainer_clean) > 0, "Training path produced no complete feature rows"
    trainer_row = trainer_clean.iloc[-1].to_numpy(dtype=np.float64)

    # --- Runtime path ---
    # derive_features_from_ohlcv is called by _build_observation when
    # IndicatorEngine has NOT pre-calculated RL features
    records = recent_bars.to_dict(orient="records")
    runtime_features = derive_features_from_ohlcv(
        indicators={},  # empty → forces full DataFrame path
        market_data={"ohlcv": records},
    )

    assert runtime_features, (
        "derive_features_from_ohlcv returned empty dict — "
        "runtime path is broken or OHLCV records are malformed"
    )
    assert set(RL_FEATURE_COLUMNS).issubset(runtime_features.keys()), (
        f"Missing features in runtime output: "
        f"{set(RL_FEATURE_COLUMNS) - set(runtime_features.keys())}"
    )

    runtime_row = np.array(
        [runtime_features[col] for col in RL_FEATURE_COLUMNS], dtype=np.float64
    )

    np.testing.assert_allclose(
        trainer_row,
        runtime_row,
        rtol=1e-6,
        atol=1e-8,
        err_msg=(
            "Runtime obs builder has drifted from training feature calculator!\n"
            "Feature-by-feature comparison:\n"
            + "\n".join(
                f"  [{i}] {col}: train={trainer_row[i]:.8f} runtime={runtime_row[i]:.8f} "
                f"diff={abs(trainer_row[i] - runtime_row[i]):.2e}"
                for i, col in enumerate(RL_FEATURE_COLUMNS)
                if not np.isclose(trainer_row[i], runtime_row[i], rtol=1e-6, atol=1e-8)
            )
            + "\nThis is a root-cause candidate for RL live-vs-training performance gap."
        ),
    )


# ---------------------------------------------------------------------------
# Test 3: Short-circuit path (IndicatorEngine pre-calculated features)
# ---------------------------------------------------------------------------

def test_derive_features_short_circuits_when_all_present(recent_bars):
    """derive_features_from_ohlcv returns empty dict when all RL features
    are already present in indicators (IndicatorEngine fast path).

    This ensures the function correctly delegates to IndicatorEngine values
    when they are available, avoiding a redundant DataFrame calculation.
    """
    # Build synthetic indicators with all RL features populated
    calc = RLFeatureCalculator()
    feat_df = calc.calculate(recent_bars.copy())
    clean = feat_df[RL_FEATURE_COLUMNS].dropna()
    latest = clean.iloc[-1]
    full_indicators = {col: float(latest[col]) for col in RL_FEATURE_COLUMNS}

    result = derive_features_from_ohlcv(
        indicators=full_indicators,
        market_data={},  # no ohlcv needed
    )
    assert result == {}, (
        "derive_features_from_ohlcv should short-circuit (return {}) when all "
        "RL_FEATURE_COLUMNS are already in indicators. "
        f"Got {len(result)} features instead."
    )


# ---------------------------------------------------------------------------
# Test 4: build_rl_observation uses scaled market features from runtime path
# ---------------------------------------------------------------------------

def test_build_rl_observation_shape(recent_bars, mock_env_config):
    """build_rl_observation returns 31-dim obs (25 market + 3 position + 3 time)."""
    from datetime import datetime

    calc = RLFeatureCalculator()
    feat_df = calc.calculate(recent_bars.copy())
    clean = feat_df[RL_FEATURE_COLUMNS].dropna()
    latest = clean.iloc[-1]
    indicators = {col: float(latest[col]) for col in RL_FEATURE_COLUMNS}

    obs = build_rl_observation(
        market_data={},
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=datetime(2026, 4, 14, 10, 30, 0, tzinfo=UTC),
        scaler=None,  # no scaling — test raw obs shape
        env_config=mock_env_config,
        ohlcv_derived=None,
    )
    assert obs is not None
    obs_arr = np.asarray(obs, dtype=np.float32)
    assert obs_arr.shape == (31,), (
        f"Expected obs shape (31,), got {obs_arr.shape}. "
        "Check market features (25) + position (3) + time (3)."
    )


def test_build_rl_observation_market_part_matches_training(recent_bars, mock_env_config):
    """Market feature portion of build_rl_observation (dims 0-24) matches
    training RLFeatureCalculator output when no scaler is applied.

    This is the end-to-end parity test: training obs vs full runtime pipeline.
    """
    from datetime import datetime

    # Training path: raw features
    calc = RLFeatureCalculator()
    trainer_df = calc.calculate(recent_bars.copy())
    clean = trainer_df[RL_FEATURE_COLUMNS].dropna()
    trainer_row = clean.iloc[-1].to_numpy(dtype=np.float64)

    # Runtime path: pass features via indicators (IndicatorEngine fast path)
    indicators = {col: float(trainer_row[i]) for i, col in enumerate(RL_FEATURE_COLUMNS)}

    obs = build_rl_observation(
        market_data={},
        indicators=indicators,
        position_side=0.0,
        contracts=0.0,
        unrealized_pnl=0.0,
        timestamp=datetime(2026, 4, 14, 10, 30, 0, tzinfo=UTC),
        scaler=None,  # no scaling → market part should be identical to trainer_row
        env_config=mock_env_config,
        ohlcv_derived=None,
    )
    obs_arr = np.asarray(obs, dtype=np.float64)
    market_part = obs_arr[:len(RL_FEATURE_COLUMNS)]

    np.testing.assert_allclose(
        trainer_row,
        market_part,
        rtol=1e-5,
        atol=1e-7,
        err_msg=(
            "build_rl_observation market feature portion does not match training features. "
            "Runtime path is dropping or transforming features before obs construction."
        ),
    )
