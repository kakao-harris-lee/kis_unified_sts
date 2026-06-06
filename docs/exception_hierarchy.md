# Exception Hierarchy Documentation

## Overview

The KIS Unified Trading Platform implements a comprehensive typed exception hierarchy to replace broad `except Exception` blocks. This hierarchy enables precise error handling, appropriate recovery strategies, and better debugging capabilities.

All trading system exceptions inherit from `TradingSystemError`, allowing callers to catch all trading errors with a single handler while still enabling specific error handling when needed.

---

## Exception Hierarchy Diagram

```
TradingSystemError (base)
├── NetworkError
│   ├── ConnectionTimeoutError
│   └── WebSocketDisconnectError
│
├── ValidationError
│   ├── DataValidationError
│   └── TypeConversionError
│
├── APIError
│   ├── KISRateLimitError
│   └── KISAuthenticationError
│
├── InfrastructureError
│   └── RedisUnavailableError
│
├── ConfigurationError
│   ├── InvalidConfigError
│   └── MissingConfigError
│
└── BusinessLogicError
    ├── InsufficientBalanceError
    ├── InvalidPositionError
    └── CircuitBreakerOpenError
```

---

## Exception Categories

### 1. TradingSystemError (Base)

**Purpose:** Base class for all trading system exceptions.

**When to use:**
- As a base class for all custom exceptions
- When catching all trading system errors generically

**Recovery strategy:** Depends on specific subclass

**Example:**
```python
try:
    await orchestrator.start()
except TradingSystemError as e:
    logger.error(f"Trading system error: {e}", exc_info=True)
    await cleanup()
```

---

### 2. NetworkError

**Purpose:** Network-related failures (connections, timeouts, WebSocket disconnections).

**Characteristics:**
- **Transient failures** - May succeed on retry
- **Retryable** - Implement retry logic with exponential backoff
- **External dependency** - Outside system control

**When to use:**
- Connection failures to external services
- Network timeout errors
- WebSocket disconnections
- HTTP request failures

**Recovery strategy:**
- Retry with exponential backoff
- Circuit breaker after consecutive failures
- Fallback to cached data if available

**Example:**
```python
try:
    await connect_to_websocket()
except NetworkError as e:
    logger.warning(f"Network error, will retry: {e}")
    await asyncio.sleep(retry_delay)
    retry_count += 1
```

#### Subclasses:

**ConnectionTimeoutError**
```python
# Attributes: host, port, timeout
raise ConnectionTimeoutError(
    host="api.kis.com",
    port=443,
    timeout=30.0
)
```

**WebSocketDisconnectError**
```python
# Attributes: url, code, reason
raise WebSocketDisconnectError(
    url="wss://api.kis.com/stream",
    code=1006,
    reason="Connection reset by peer"
)
```

---

### 3. ValidationError

**Purpose:** Data validation failures (invalid formats, type conversions, schema violations).

**Characteristics:**
- **Permanent failures** - Will not succeed on retry
- **Not retryable** - Input data must be corrected first
- **Data quality issue** - Invalid or corrupted data

**When to use:**
- Invalid data formats
- Type conversion errors
- Schema validation failures
- Data integrity violations
- Out-of-range values

**Recovery strategy:**
- Reject the data
- Log for investigation
- Skip record and continue with next
- Alert on repeated validation failures

**Example:**
```python
if not isinstance(price, (int, float)):
    raise ValidationError(f"Invalid price type: {type(price)}")

if price <= 0:
    raise DataValidationError(
        field="price",
        value=price,
        constraint="must be positive"
    )
```

#### Subclasses:

**DataValidationError**
```python
# Attributes: field, value, constraint
raise DataValidationError(
    field="quantity",
    value=-10,
    constraint="must be non-negative"
)
```

**TypeConversionError**
```python
# Attributes: value, target_type, source_type
try:
    quantity = int(user_input)
except ValueError as e:
    raise TypeConversionError(
        value=user_input,
        target_type="int"
    ) from e
```

---

### 4. APIError

**Purpose:** External API failures (KIS API, rate limits, authentication).

**Characteristics:**
- **Mixed transience** - Can be transient (rate limits) or permanent (auth failures)
- **Conditionally retryable** - Depends on error type
- **External service** - Third-party API issues

**When to use:**
- KIS API errors
- API rate limit exceeded
- Authentication failures
- Invalid API responses
- API service unavailable

**Recovery strategy:**
- **Rate limits:** Wait and retry after cooldown
- **Authentication:** Refresh token and retry
- **4xx errors:** Log and skip (permanent failure)
- **5xx errors:** Retry with backoff (transient failure)

**Example:**
```python
if response.status_code == 429:
    raise KISRateLimitError(
        endpoint="/uapi/domestic-stock/v1/order",
        retry_after=1.0,
        message="초당 거래건수를 초과하였습니다"
    )
elif response.status_code == 401:
    raise KISAuthenticationError(
        reason="Token expired",
        account=account_no
    )
```

#### Subclasses:

**KISRateLimitError**
```python
# Attributes: endpoint, retry_after, message
raise KISRateLimitError(
    endpoint="/uapi/domestic-stock/v1/order",
    retry_after=1.0,
    message="초당 거래건수를 초과하였습니다"
)
```

**KISAuthenticationError**
```python
# Attributes: reason, account
raise KISAuthenticationError(
    reason="Invalid credentials",
    account="12345678-01"
)
```

---

### 5. InfrastructureError

**Purpose:** Infrastructure service failures (Redis, storage, databases).

**Characteristics:**
- **Service availability issues** - May be transient
- **Retryable with circuit breaker** - Avoid cascading failures
- **Internal dependency** - Within system control

**When to use:**
- Redis connection/operation errors
- SQLite/Parquet/DuckDB storage failures
- Database connection errors
- Message queue errors
- Disk I/O failures

**Recovery strategy:**
- Retry with circuit breaker
- Degrade gracefully (e.g., skip caching)
- Alert ops team
- Use fallback mechanisms

**Example:**
```python
try:
    await redis_client.get(key)
except redis.ConnectionError as e:
    raise RedisUnavailableError(
        operation="get",
        key=key,
        details=str(e)
    ) from e
```

#### Subclasses:

**RedisUnavailableError**
```python
# Attributes: operation, key, details
raise RedisUnavailableError(
    operation="xadd",
    key="market_ticks",
    details="Connection refused"
)
```

---

### 6. ConfigurationError

**Purpose:** Configuration issues (missing, invalid, or inconsistent configuration).

**Characteristics:**
- **Permanent failures** - Require manual intervention
- **Not retryable** - Configuration must be fixed
- **Startup errors** - Usually caught during initialization

**When to use:**
- Missing required configuration
- Invalid configuration values
- Configuration file not found
- Environment variable not set
- Incompatible configuration settings

**Recovery strategy:**
- Fail fast during startup
- Provide clear error message with fix instructions
- Do not retry - requires configuration change

**Example:**
```python
api_key = config.get("kis.api_key")
if not api_key:
    raise MissingConfigError(
        config_key="kis.api_key",
        config_file="config/api.yaml"
    )

if timeout < 0:
    raise InvalidConfigError(
        config_key="api.timeout",
        value=timeout,
        reason="timeout must be positive"
    )
```

#### Subclasses:

**MissingConfigError**
```python
# Attributes: config_key, config_file
raise MissingConfigError(
    config_key="kis.api_key",
    config_file="config/api.yaml"
)
```

**InvalidConfigError**
```python
# Attributes: config_key, value, reason
raise InvalidConfigError(
    config_key="max_position_size",
    value=-100,
    reason="must be positive"
)
```

---

### 7. BusinessLogicError

**Purpose:** Business rule violations (trading constraints, risk limits).

**Characteristics:**
- **Business rule violations** - Expected in normal operation
- **Not retryable** - Business condition must change
- **User-actionable** - Can be resolved by user action

**When to use:**
- Insufficient account balance
- Invalid position state for operation
- Trading hours violation
- Risk limit exceeded
- Circuit breaker open

**Recovery strategy:**
- Reject operation
- Return error to user with actionable message
- Log for business analytics
- Do not retry automatically

**Example:**
```python
order_cost = price * quantity
if balance < order_cost:
    raise InsufficientBalanceError(
        required=order_cost,
        available=balance,
        symbol="005930"
    )

if position.quantity == 0:
    raise InvalidPositionError(
        symbol="005930",
        current_state="closed",
        operation="exit position"
    )
```

#### Subclasses:

**InsufficientBalanceError**
```python
# Attributes: required, available, symbol
raise InsufficientBalanceError(
    required=1_000_000,
    available=500_000,
    symbol="005930"
)
```

**InvalidPositionError**
```python
# Attributes: symbol, current_state, operation
raise InvalidPositionError(
    symbol="005930",
    current_state="closed",
    operation="exit position"
)
```

**CircuitBreakerOpenError**
```python
# Attributes: component, reset_time, failure_count
raise CircuitBreakerOpenError(
    component="KIS API",
    reset_time=60.0,
    failure_count=5
)
```

---

## Exception Attributes

All specific exception classes include structured attributes for better debugging and error handling:

| Exception | Attributes | Purpose |
|-----------|-----------|---------|
| `ConnectionTimeoutError` | `host`, `port`, `timeout` | Identify connection target and timeout value |
| `WebSocketDisconnectError` | `url`, `code`, `reason` | WebSocket close code and reason |
| `DataValidationError` | `field`, `value`, `constraint` | Invalid field and constraint violated |
| `TypeConversionError` | `value`, `target_type`, `source_type` | Type conversion details |
| `KISRateLimitError` | `endpoint`, `retry_after`, `message` | Rate limit details and retry timing |
| `KISAuthenticationError` | `reason`, `account` | Auth failure reason and account |
| `RedisUnavailableError` | `operation`, `key`, `details` | Redis operation and error details |
| `InvalidConfigError` | `config_key`, `value`, `reason` | Invalid config and reason |
| `MissingConfigError` | `config_key`, `config_file` | Missing config location |
| `InsufficientBalanceError` | `required`, `available`, `symbol` | Balance requirement details |
| `InvalidPositionError` | `symbol`, `current_state`, `operation` | Position state and operation |
| `CircuitBreakerOpenError` | `component`, `reset_time`, `failure_count` | Circuit breaker details |

---

## Import and Usage

### Importing Exceptions

```python
# Import all exceptions
from shared.exceptions import (
    TradingSystemError,
    NetworkError,
    ValidationError,
    APIError,
    InfrastructureError,
    ConfigurationError,
    BusinessLogicError,
    # Specific exceptions as needed
    KISRateLimitError,
    RedisUnavailableError,
)

# Or import from shared package
from shared import exceptions
```

### Basic Usage Pattern

```python
from shared.exceptions import (
    NetworkError,
    ValidationError,
    InfrastructureError,
    TradingSystemError,
)

async def process_market_data(data: dict):
    """Process market data with specific exception handling."""
    try:
        # Validate data
        if not data.get("price"):
            raise ValidationError("Missing price field")

        # Connect to service
        await websocket.send(data)

        # Store in Redis
        await redis_client.set(key, value)

    except ValidationError:
        # Invalid data - skip and continue
        logger.warning(f"Skipping invalid data: {data}")
        return None

    except NetworkError as e:
        # Network error - retry with backoff
        logger.warning(f"Network error, will retry: {e}")
        await asyncio.sleep(retry_delay)
        return await process_market_data(data)

    except InfrastructureError as e:
        # Redis error - degrade gracefully
        logger.error(f"Redis unavailable, skipping cache: {e}")
        # Continue without caching

    except TradingSystemError as e:
        # Catch-all for other trading system errors
        logger.error(f"Unexpected trading system error: {e}", exc_info=True)
        raise
```

---

## Exception Handling Patterns

### Pattern 1: Specific Exceptions First

Always catch specific exceptions before broader ones:

```python
try:
    result = await operation()
except KISRateLimitError as e:
    # Specific: Handle rate limit
    await asyncio.sleep(e.retry_after)
    return await operation()  # Retry
except APIError as e:
    # Broader: Handle other API errors
    logger.error(f"API error: {e}")
    return None
except TradingSystemError as e:
    # Broadest: Catch-all for trading errors
    logger.error(f"Trading system error: {e}", exc_info=True)
    raise
```

### Pattern 2: Raise From Original Exception

Preserve exception chaining for debugging:

```python
try:
    data = json.loads(response_text)
except json.JSONDecodeError as e:
    raise ValidationError(
        f"Invalid JSON response: {response_text[:100]}"
    ) from e
```

### Pattern 3: Add Context to Exceptions

Use exception attributes to provide structured context:

```python
# ❌ Bad: String-only error message
raise NetworkError("Connection failed to api.kis.com:443 after 30s")

# ✅ Good: Structured attributes
raise ConnectionTimeoutError(
    host="api.kis.com",
    port=443,
    timeout=30.0
)
```

### Pattern 4: Fail Fast vs Graceful Degradation

**Fail Fast** (ConfigurationError, BusinessLogicError):
```python
if not api_key:
    # Fail immediately - cannot proceed
    raise MissingConfigError(
        config_key="kis.api_key",
        config_file="config/api.yaml"
    )
```

**Graceful Degradation** (InfrastructureError, NetworkError):
```python
try:
    cached_value = await redis_client.get(key)
except RedisUnavailableError as e:
    # Degrade gracefully - continue without cache
    logger.warning(f"Redis unavailable, skipping cache: {e}")
    cached_value = None
```

---

## Decision Tree: Which Exception to Use?

```
Is it a configuration problem?
├─ Yes → ConfigurationError
│  ├─ Missing config → MissingConfigError
│  └─ Invalid config → InvalidConfigError
│
└─ No → Is it a network/connectivity issue?
   ├─ Yes → NetworkError
   │  ├─ Timeout → ConnectionTimeoutError
   │  └─ WebSocket → WebSocketDisconnectError
   │
   └─ No → Is it an external API error?
      ├─ Yes → APIError
      │  ├─ Rate limit → KISRateLimitError
      │  └─ Auth failed → KISAuthenticationError
      │
      └─ No → Is it a data validation issue?
         ├─ Yes → ValidationError
         │  ├─ Schema/constraint → DataValidationError
         │  └─ Type conversion → TypeConversionError
         │
         └─ No → Is it an infrastructure service?
            ├─ Yes → InfrastructureError
            │  ├─ Redis → RedisUnavailableError
            │  └─ Storage/database → InfrastructureError
            │
            └─ No → Is it a business rule violation?
               ├─ Yes → BusinessLogicError
               │  ├─ Balance → InsufficientBalanceError
               │  ├─ Position → InvalidPositionError
               │  └─ Circuit breaker → CircuitBreakerOpenError
               │
               └─ Unsure → TradingSystemError (generic)
```

---

## Migration Statistics

As of 2026-03-06, the exception hierarchy refactor has:

- **Created:** 13 specific exception types across 6 categories
- **Replaced:** ~115+ broad `except Exception` blocks
- **Remaining:** 11 intentional broad catches (all documented)
- **Files Modified:** 20+ service files

All remaining broad catches are intentional and follow the pattern:
1. Catch specific exceptions first
2. Use broad `except Exception` as final fallback
3. Include explanatory comment
4. Log with `exc_info=True` for debugging

---

## See Also

- [Error Handling Guide](./error_handling_guide.md) - Best practices and migration guide
- [VERIFICATION_REPORT.md](archive/verification/VERIFICATION_REPORT.md) - Migration verification results
- [shared/exceptions/__init__.py](../shared/exceptions/__init__.py) - Exception source code
