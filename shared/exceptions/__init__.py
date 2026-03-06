"""Trading system exception hierarchy.

All trading system exceptions inherit from TradingSystemError,
allowing callers to catch all trading errors with a single handler:

    try:
        await orchestrator.start()
    except TradingSystemError as e:
        logger.error(f"Trading system error: {e}")

Exception Hierarchy:
    TradingSystemError (base)
    ├── NetworkError
    ├── ValidationError
    ├── APIError
    ├── InfrastructureError
    ├── ConfigurationError
    └── BusinessLogicError

Usage:
    # Network errors (connections, timeouts, WebSocket)
    raise NetworkError("Failed to connect to data feed")

    # Data validation errors
    raise ValidationError("Invalid OHLCV data format")

    # External API errors (KIS API, rate limits, authentication)
    raise APIError("KIS API rate limit exceeded")

    # Infrastructure errors (Redis, ClickHouse, database)
    raise InfrastructureError("Redis connection failed")

    # Configuration errors (missing/invalid config)
    raise ConfigurationError("Missing required config: api_key")

    # Business logic errors (insufficient balance, invalid position)
    raise BusinessLogicError("Insufficient balance for order")
"""


class TradingSystemError(Exception):
    """Base exception for all trading system errors.

    All custom exceptions in the trading system should inherit from this class
    to maintain a consistent exception hierarchy and enable unified error handling.

    This base class provides a common interface for all trading system errors,
    allowing higher-level code to catch and handle errors generically when
    specific handling is not required.

    Example:
        try:
            # Trading system operations
            pass
        except TradingSystemError as e:
            logger.error(f"Trading system error: {e}", exc_info=True)
    """

    pass


class NetworkError(TradingSystemError):
    """Base exception for network-related errors.

    Raised when network operations fail, including:
    - Connection failures
    - Timeout errors
    - WebSocket disconnections
    - HTTP request failures

    This exception indicates transient failures that may succeed on retry.
    Consider implementing retry logic with exponential backoff when catching
    this exception.

    Example:
        try:
            await connect_to_websocket()
        except NetworkError as e:
            logger.warning(f"Network error, will retry: {e}")
            await asyncio.sleep(retry_delay)
    """

    pass


class ValidationError(TradingSystemError):
    """Base exception for data validation errors.

    Raised when input data fails validation checks, including:
    - Invalid data formats
    - Type conversion errors
    - Schema validation failures
    - Data integrity violations

    This exception indicates permanent failures that will not succeed on retry.
    The input data must be corrected before retrying the operation.

    Example:
        if not isinstance(price, (int, float)):
            raise ValidationError(f"Invalid price type: {type(price)}")
    """

    pass


class APIError(TradingSystemError):
    """Base exception for external API errors.

    Raised when external API calls fail, including:
    - KIS API errors
    - Rate limit exceeded
    - Authentication failures
    - Invalid API responses

    This exception may indicate either transient (rate limits) or permanent
    (authentication) failures. Check the specific error details to determine
    the appropriate recovery strategy.

    Example:
        if response.status_code == 429:
            raise APIError("Rate limit exceeded, retry after cooldown")
    """

    pass


class InfrastructureError(TradingSystemError):
    """Base exception for infrastructure-related errors.

    Raised when infrastructure services fail, including:
    - Redis connection/operation errors
    - ClickHouse query errors
    - Database connection failures
    - Message queue errors

    This exception indicates service availability issues that may be transient.
    Consider implementing circuit breakers and fallback mechanisms when
    catching this exception.

    Example:
        try:
            await redis_client.get(key)
        except redis.ConnectionError as e:
            raise InfrastructureError(f"Redis unavailable: {e}") from e
    """

    pass


class ConfigurationError(TradingSystemError):
    """Base exception for configuration-related errors.

    Raised when configuration is missing, invalid, or inconsistent, including:
    - Missing required configuration
    - Invalid configuration values
    - Configuration file not found
    - Environment variable not set

    This exception indicates permanent failures that require configuration
    changes before the system can operate correctly. These errors typically
    occur during system startup.

    Example:
        if not api_key:
            raise ConfigurationError("Missing required config: api_key")
    """

    pass


class BusinessLogicError(TradingSystemError):
    """Base exception for business logic violations.

    Raised when business rules or trading constraints are violated, including:
    - Insufficient balance for order
    - Invalid position state
    - Trading hours violation
    - Risk limit exceeded

    This exception indicates that the requested operation violates business
    rules or trading constraints. The operation should not be retried without
    addressing the underlying business logic issue.

    Example:
        if balance < order_amount:
            raise BusinessLogicError(
                f"Insufficient balance: {balance} < {order_amount}"
            )
    """

    pass


__all__ = [
    "TradingSystemError",
    "NetworkError",
    "ValidationError",
    "APIError",
    "InfrastructureError",
    "ConfigurationError",
    "BusinessLogicError",
]
