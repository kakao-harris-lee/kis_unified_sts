"""RL MPPO 모델 공유 헬퍼

entry/exit 전략에서 공통으로 사용하는 모델 로딩, 관측값 구성, confidence 계산.
모듈 레벨 캐시로 entry와 exit이 같은 모델 인스턴스를 공유한다.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

# ---------------------------------------------------------------------------
# Module-level caches (shared across entry & exit instances)
# ---------------------------------------------------------------------------
_model_cache: dict[str, Any] = {}  # key: resolved model path
_scaler_cache: dict[str, Any] = {}  # key: scaler path
_env_config_cache: Any = None


def load_rl_model(model_path: str, device: Any) -> Any | None:
    """MaskablePPO 모델 로드 (캐시).

    RL_MPPO_MODEL_PATH 환경변수로 경로 오버라이드 가능.
    """
    model_override = os.getenv("RL_MPPO_MODEL_PATH", "").strip()
    resolved = Path(model_override or model_path)
    cache_key = f"{resolved}@{device}"

    if cache_key in _model_cache:
        return _model_cache[cache_key]

    if not resolved.exists():
        logger.error(f"RL model not found: {resolved}")
        return None

    try:
        from sb3_contrib import MaskablePPO

        model = MaskablePPO.load(str(resolved), device=device)
        _model_cache[cache_key] = model
        logger.info(f"RL model loaded: {resolved} (device={device})")
        return model
    except Exception as e:
        logger.error(f"Failed to load RL model: {e}")
        return None


def load_rl_scaler(scaler_path: str, model_path: str) -> Any | None:
    """StandardScaler 로드 (캐시).

    scaler_path가 비어있으면 model_path 기준 자동 탐색.
    """
    effective_path = scaler_path.strip() if scaler_path else ""
    if not effective_path:
        model_override = os.getenv("RL_MPPO_MODEL_PATH", "").strip()
        resolved_model = Path(model_override or model_path).resolve()
        effective_path = str(resolved_model.parent.parent / "scaler.joblib")

    if effective_path in _scaler_cache:
        return _scaler_cache[effective_path]

    path = Path(effective_path)
    if not path.exists():
        logger.warning(f"RL scaler not found: {path} (using raw features)")
        _scaler_cache[effective_path] = None
        return None

    try:
        import joblib

        scaler = joblib.load(path)
        _scaler_cache[effective_path] = scaler
        return scaler
    except Exception as e:
        logger.warning(f"Failed to load RL scaler: {e}")
        _scaler_cache[effective_path] = None
        return None


def get_rl_env_config() -> Any:
    """RLEnvConfig 로드 (캐시)."""
    global _env_config_cache
    if _env_config_cache is None:
        from shared.ml.rl.env import RLEnvConfig

        _env_config_cache = RLEnvConfig.from_yaml()
    return _env_config_cache


def build_rl_observation(
    market_data: dict[str, Any],
    indicators: dict[str, Any],
    position_side: float,
    contracts: float,
    unrealized_pnl: float,
    timestamp: datetime,
    scaler: Any,
    env_config: Any,
    ohlcv_derived: dict[str, float] | None = None,
) -> Any | None:
    """31차원 관측값 구성 -- 시장(25) + 포지션(3) + 시간(3).

    Args:
        market_data: 시장 데이터 dict
        indicators: 지표 dict
        position_side: 1.0(long) / -1.0(short) / 0.0(flat)
        contracts: normalized contract count
        unrealized_pnl: normalized unrealized PnL
        timestamp: 현재 시간
        scaler: sklearn StandardScaler (or None)
        env_config: RLEnvConfig
        ohlcv_derived: OHLCV에서 유도된 피처 dict (optional fallback)
    """
    import numpy as np

    from shared.ml.rl.features import RL_FEATURE_COLUMNS

    derived = ohlcv_derived or {}

    market_features = []
    missing_features = []
    for col in RL_FEATURE_COLUMNS:
        val = indicators.get(col, market_data.get(col, derived.get(col)))
        if val is None:
            missing_features.append(col)
            market_features.append(0.0)
        else:
            market_features.append(float(val))

    if missing_features:
        logger.warning(
            f"Missing {len(missing_features)} RL features (filled with 0.0): "
            f"{missing_features[:5]}{'...' if len(missing_features) > 5 else ''}"
        )

    market_array = np.array(market_features, dtype=np.float32).reshape(1, -1)
    if scaler is not None:
        try:
            market_array = scaler.transform(market_array)
        except Exception as e:
            logger.warning(f"RL scaler transform failed; using raw features: {e}")

    # 시간 피처
    market_open = parse_hhmm(env_config.market_open, default_hour=9, default_minute=0)
    market_close = parse_hhmm(
        env_config.market_close, default_hour=15, default_minute=45
    )
    now = (
        timestamp.astimezone(KST)
        if timestamp.tzinfo
        else timestamp.replace(tzinfo=KST)
    )
    start_dt = now.replace(
        hour=market_open[0], minute=market_open[1], second=0, microsecond=0
    )
    end_dt = now.replace(
        hour=market_close[0], minute=market_close[1], second=0, microsecond=0
    )
    total_minutes = max(1.0, (end_dt - start_dt).total_seconds() / 60.0)
    elapsed = (now - start_dt).total_seconds() / 60.0
    progress = max(0.0, min(1.0, elapsed / total_minutes))
    time_features = [
        progress,
        float(np.sin(2 * np.pi * progress)),
        float(np.cos(2 * np.pi * progress)),
    ]

    obs = np.array(
        market_array[0].tolist()
        + [position_side, contracts, unrealized_pnl]
        + time_features,
        dtype=np.float32,
    )
    return obs


def derive_features_from_ohlcv(
    indicators: dict[str, Any], market_data: dict[str, Any]
) -> dict[str, float]:
    """OHLCV에서 RL 피처 유도 (fallback)."""
    ohlcv = indicators.get("ohlcv") or market_data.get("ohlcv")
    if not isinstance(ohlcv, list) or not ohlcv:
        return {}
    try:
        import pandas as pd

        from shared.ml.rl.features import RL_FEATURE_COLUMNS, RLFeatureCalculator

        df = pd.DataFrame(ohlcv)
        needed = {"open", "high", "low", "close", "volume"}
        if not needed.issubset(df.columns):
            return {}
        if "datetime" not in df.columns:
            df["datetime"] = pd.date_range(
                end=pd.Timestamp.now(), periods=len(df), freq="1min"
            )
        calc = RLFeatureCalculator()
        feat_df = calc.calculate(df)

        for col in RL_FEATURE_COLUMNS:
            if col in feat_df.columns:
                feat_df[col] = feat_df[col].ffill()

        neutral = {
            col: (
                1.0
                if "ratio" in col
                else 50.0
                if col in ("rsi", "stoch_k", "stoch_d")
                else 0.5
                if col == "bb_position"
                else 0.0
            )
            for col in RL_FEATURE_COLUMNS
        }
        feat_df = feat_df.fillna(neutral)

        if feat_df.empty:
            return {}
        latest = feat_df.iloc[-1]
        return {col: float(latest[col]) for col in RL_FEATURE_COLUMNS}
    except Exception as e:
        logger.debug(f"Failed to derive RL features from ohlcv: {e}")
        return {}


def get_action_confidence(
    model: Any, obs: Any, action: int, action_masks: Any, device: Any
) -> float:
    """액션의 확률(confidence) 추출."""
    try:
        import numpy as np
        import torch

        obs_tensor = torch.as_tensor(obs).float().unsqueeze(0).to(device)
        with torch.no_grad():
            dist = model.policy.get_distribution(obs_tensor)
            probs = dist.distribution.probs.cpu().numpy()[0]
            mask = np.asarray(action_masks, dtype=bool)
            if mask.shape == probs.shape and mask.any():
                probs = probs * mask
                total = float(probs.sum())
                if total > 0:
                    probs = probs / total
            if action < 0 or action >= len(probs):
                return 0.0
            return float(probs[action])
    except Exception as e:
        logger.debug(f"Failed to get action confidence: {e}")
        return 1.0


def parse_hhmm(
    value: str, default_hour: int, default_minute: int
) -> tuple[int, int]:
    """Parse 'HH:MM' string safely."""
    try:
        hh, mm = value.split(":", 1)
        h = int(hh)
        m = int(mm)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except Exception:
        pass
    return default_hour, default_minute
