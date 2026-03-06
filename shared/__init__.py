"""KIS Unified Trading Platform - Shared Modules

공통 모듈:
- kis: KIS API 어댑터 (인증, 클라이언트, 웹소켓)
- config: 설정 로더 및 스키마
- strategy: 전략 프레임워크
- indicators: 기술적 지표
- models: 데이터 모델
- backtest: 백테스트 엔진
- exceptions: 통합 예외 계층 구조
"""

from importlib.metadata import version, PackageNotFoundError

# Import exception hierarchy for convenient access
from shared.exceptions import (
    # Base exceptions
    TradingSystemError,
    NetworkError,
    ValidationError,
    APIError,
    InfrastructureError,
    ConfigurationError,
    BusinessLogicError,
    # Network errors
    ConnectionTimeoutError,
    WebSocketDisconnectError,
    # Validation errors
    DataValidationError,
    TypeConversionError,
    # API errors
    KISRateLimitError,
    KISAuthenticationError,
    # Infrastructure errors
    RedisUnavailableError,
    ClickHouseQueryError,
    # Configuration errors
    InvalidConfigError,
    MissingConfigError,
    # Business logic errors
    InsufficientBalanceError,
    InvalidPositionError,
    CircuitBreakerOpenError,
)

try:
    __version__ = version("kis-unified-sts")
except PackageNotFoundError:
    # 패키지가 설치되지 않은 경우 (개발 모드)
    __version__ = "0.1.0"

__all__ = [
    "__version__",
    # Base exceptions
    "TradingSystemError",
    "NetworkError",
    "ValidationError",
    "APIError",
    "InfrastructureError",
    "ConfigurationError",
    "BusinessLogicError",
    # Network errors
    "ConnectionTimeoutError",
    "WebSocketDisconnectError",
    # Validation errors
    "DataValidationError",
    "TypeConversionError",
    # API errors
    "KISRateLimitError",
    "KISAuthenticationError",
    # Infrastructure errors
    "RedisUnavailableError",
    "ClickHouseQueryError",
    # Configuration errors
    "InvalidConfigError",
    "MissingConfigError",
    # Business logic errors
    "InsufficientBalanceError",
    "InvalidPositionError",
    "CircuitBreakerOpenError",
]
