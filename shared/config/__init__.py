"""설정 로더 및 스키마

YAML 설정 파일을 로드하고 Pydantic 모델로 검증.

Usage:
    from shared.config import ConfigLoader, load_config

    # 전략 설정 로드
    config = ConfigLoader.load_strategy("stock", "bb_reversion")

    # 편의 함수 사용
    data = load_config("exit/three_stage.yaml")
"""

from shared.config.loader import (
    ConfigError,
    ConfigLoader,
    ConfigNotFoundError,
    ConfigValidationError,
    get_strategy_names,
    load_config,
    load_strategy_config,
)
from shared.config.schema import KISConfig
from shared.config.secrets import SecretsManager, require_secret

__all__ = [
    # Loader
    "ConfigLoader",
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "load_config",
    "load_strategy_config",
    "get_strategy_names",
    # Schema
    "KISConfig",
    # Secrets
    "SecretsManager",
    "require_secret",
]
