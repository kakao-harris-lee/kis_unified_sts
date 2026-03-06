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


# ============================================================================
# Specific Exception Types
# ============================================================================


# Network Errors
# --------------

class ConnectionTimeoutError(NetworkError):
    """Raised when a network connection times out.

    Attributes:
        host: The host that failed to connect
        port: The port number (if applicable)
        timeout: The timeout value in seconds
    """

    def __init__(self, host: str, timeout: float, port: int | None = None):
        self.host = host
        self.port = port
        self.timeout = timeout
        msg = f"Connection to {host}"
        if port:
            msg += f":{port}"
        msg += f" timed out after {timeout:.1f}s"
        super().__init__(msg)


class WebSocketDisconnectError(NetworkError):
    """Raised when WebSocket connection is lost.

    Attributes:
        url: The WebSocket URL that disconnected
        code: The WebSocket close code (if available)
        reason: Human-readable disconnect reason
    """

    def __init__(self, url: str, code: int | None = None, reason: str = ""):
        self.url = url
        self.code = code
        self.reason = reason
        msg = f"WebSocket disconnected: {url}"
        if code:
            msg += f" (code: {code})"
        if reason:
            msg += f" - {reason}"
        super().__init__(msg)


# Validation Errors
# -----------------

class DataValidationError(ValidationError):
    """Raised when data fails validation checks.

    Attributes:
        field: The field that failed validation
        value: The invalid value
        constraint: The validation constraint that was violated
    """

    def __init__(self, field: str, value: any = None, constraint: str = ""):
        self.field = field
        self.value = value
        self.constraint = constraint
        msg = f"Validation failed for field '{field}'"
        if constraint:
            msg += f": {constraint}"
        if value is not None:
            msg += f" (value: {value})"
        super().__init__(msg)


class TypeConversionError(ValidationError):
    """Raised when type conversion fails.

    Attributes:
        value: The value that failed to convert
        target_type: The type we attempted to convert to
        source_type: The original type of the value
    """

    def __init__(self, value: any, target_type: str, source_type: str = ""):
        self.value = value
        self.target_type = target_type
        self.source_type = source_type or type(value).__name__
        super().__init__(
            f"Failed to convert {self.source_type} to {target_type}: {value}"
        )


# API Errors
# ----------

class KISRateLimitError(APIError):
    """Raised when KIS API rate limit is exceeded.

    Attributes:
        endpoint: The API endpoint that was rate limited
        retry_after: Suggested wait time before retry (seconds)
        message: Additional error message from API
    """

    def __init__(
        self, endpoint: str = "", retry_after: float = 0.0, message: str = ""
    ):
        self.endpoint = endpoint
        self.retry_after = retry_after
        self.message = message
        msg = "KIS API rate limit exceeded"
        if endpoint:
            msg += f" for endpoint '{endpoint}'"
        if retry_after > 0:
            msg += f", retry after {retry_after:.1f}s"
        if message:
            msg += f": {message}"
        super().__init__(msg)


class KISAuthenticationError(APIError):
    """Raised when KIS API authentication fails.

    Attributes:
        reason: The reason for authentication failure
        account: The account number (if available)
    """

    def __init__(self, reason: str = "Authentication failed", account: str = ""):
        self.reason = reason
        self.account = account
        msg = f"KIS API authentication failed: {reason}"
        if account:
            msg += f" (account: {account})"
        super().__init__(msg)


# Infrastructure Errors
# ----------------------

class RedisUnavailableError(InfrastructureError):
    """Raised when Redis is unavailable or operations fail.

    Attributes:
        operation: The Redis operation that failed
        key: The Redis key involved (if applicable)
        details: Additional error details
    """

    def __init__(self, operation: str = "", key: str = "", details: str = ""):
        self.operation = operation
        self.key = key
        self.details = details
        msg = "Redis unavailable"
        if operation:
            msg += f" during {operation}"
        if key:
            msg += f" for key '{key}'"
        if details:
            msg += f": {details}"
        super().__init__(msg)


class ClickHouseQueryError(InfrastructureError):
    """Raised when ClickHouse query fails.

    Attributes:
        query: The query that failed (truncated if too long)
        database: The database name
        table: The table name (if applicable)
        error_code: The ClickHouse error code (if available)
    """

    def __init__(
        self,
        query: str = "",
        database: str = "",
        table: str = "",
        error_code: int | None = None,
    ):
        self.query = query[:200] if query else ""  # Truncate long queries
        self.database = database
        self.table = table
        self.error_code = error_code
        msg = "ClickHouse query failed"
        if database:
            msg += f" in database '{database}'"
        if table:
            msg += f" on table '{table}'"
        if error_code:
            msg += f" (error code: {error_code})"
        super().__init__(msg)


# Configuration Errors
# --------------------

class InvalidConfigError(ConfigurationError):
    """Raised when configuration is invalid.

    Attributes:
        config_key: The configuration key that is invalid
        value: The invalid value
        reason: Why the configuration is invalid
    """

    def __init__(self, config_key: str, value: any = None, reason: str = ""):
        self.config_key = config_key
        self.value = value
        self.reason = reason
        msg = f"Invalid configuration for '{config_key}'"
        if reason:
            msg += f": {reason}"
        if value is not None:
            msg += f" (value: {value})"
        super().__init__(msg)


class MissingConfigError(ConfigurationError):
    """Raised when required configuration is missing.

    Attributes:
        config_key: The configuration key that is missing
        config_file: The configuration file that should contain it
    """

    def __init__(self, config_key: str, config_file: str = ""):
        self.config_key = config_key
        self.config_file = config_file
        msg = f"Missing required configuration: '{config_key}'"
        if config_file:
            msg += f" in {config_file}"
        super().__init__(msg)


# Business Logic Errors
# ----------------------

class InsufficientBalanceError(BusinessLogicError):
    """Raised when account balance is insufficient for order.

    Attributes:
        required: The required balance amount
        available: The available balance amount
        symbol: The trading symbol (if applicable)
    """

    def __init__(
        self, required: float = 0.0, available: float = 0.0, symbol: str = ""
    ):
        self.required = required
        self.available = available
        self.symbol = symbol
        msg = "Insufficient balance for order"
        if symbol:
            msg += f" for {symbol}"
        if required > 0 and available >= 0:
            msg += f": required {required:,.0f}, available {available:,.0f}"
        super().__init__(msg)


class InvalidPositionError(BusinessLogicError):
    """Raised when position state is invalid for the requested operation.

    Attributes:
        symbol: The trading symbol
        current_state: The current position state
        operation: The operation that was attempted
    """

    def __init__(self, symbol: str, current_state: str = "", operation: str = ""):
        self.symbol = symbol
        self.current_state = current_state
        self.operation = operation
        msg = f"Invalid position state for {symbol}"
        if current_state:
            msg += f": current state is '{current_state}'"
        if operation:
            msg += f", cannot {operation}"
        super().__init__(msg)


class CircuitBreakerOpenError(BusinessLogicError):
    """Raised when circuit breaker is open.

    Attributes:
        component: The component that triggered the circuit breaker
        reset_time: Estimated time until circuit breaker resets (seconds)
        failure_count: Number of consecutive failures that triggered the breaker
    """

    def __init__(
        self, component: str, reset_time: float = 0.0, failure_count: int = 0
    ):
        self.component = component
        self.reset_time = reset_time
        self.failure_count = failure_count
        msg = f"Circuit breaker open for '{component}'"
        if reset_time > 0:
            msg += f", retry after {reset_time:.1f}s"
        if failure_count > 0:
            msg += f" (failures: {failure_count})"
        super().__init__(msg)


__all__ = [
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
