# Error Handling Guide

## Overview

This guide provides best practices for error handling in the KIS Unified Trading Platform using the typed exception hierarchy. It includes migration examples, recovery strategies, and common patterns.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Migration Guide](#migration-guide)
3. [Recovery Strategies](#recovery-strategies)
4. [Best Practices](#best-practices)
5. [Common Patterns](#common-patterns)
6. [Testing Exception Handling](#testing-exception-handling)
7. [Logging Best Practices](#logging-best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Before: Broad Exception Handling

```python
# ❌ Anti-pattern: Broad exception catch
try:
    response = await kis_api.place_order(symbol, quantity, price)
    await redis_client.set(f"order:{order_id}", response)
except Exception as e:
    logger.error(f"Order placement failed: {e}")
    return None
```

**Problems:**
- Network errors, validation errors, and rate limits all handled identically
- No opportunity for specific recovery strategies
- Masks programming bugs (e.g., TypeError, AttributeError)
- Cannot distinguish transient from permanent failures

### After: Specific Exception Handling

```python
# ✅ Best practice: Specific exception catches
from shared.exceptions import (
    NetworkError,
    KISRateLimitError,
    ValidationError,
    InfrastructureError,
    TradingSystemError,
)

try:
    response = await kis_api.place_order(symbol, quantity, price)
    await redis_client.set(f"order:{order_id}", response)

except KISRateLimitError as e:
    # Rate limit: Wait and retry
    logger.warning(f"Rate limited, retrying after {e.retry_after}s")
    await asyncio.sleep(e.retry_after)
    return await place_order_with_retry(symbol, quantity, price)

except NetworkError as e:
    # Network error: Retry with exponential backoff
    logger.warning(f"Network error, will retry: {e}")
    return await retry_with_backoff(place_order, symbol, quantity, price)

except ValidationError as e:
    # Validation error: Reject order
    logger.error(f"Invalid order parameters: {e}")
    return {"error": "invalid_parameters", "details": str(e)}

except InfrastructureError as e:
    # Redis error: Continue without caching (graceful degradation)
    logger.warning(f"Failed to cache order, continuing: {e}")
    return response

except TradingSystemError as e:
    # Catch-all for other trading system errors
    logger.error(f"Order placement failed: {e}", exc_info=True)
    raise
```

**Benefits:**
- Rate limits → Wait and retry
- Network errors → Retry with backoff
- Validation errors → Reject with clear message
- Redis errors → Degrade gracefully
- Programming bugs → Propagate with full traceback

---

## Migration Guide

### Step 1: Identify Exception Categories

Review your existing `except Exception` blocks and categorize the errors:

```python
# Example: Original code
try:
    data = fetch_market_data(symbol)
    validated = validate_data(data)
    await redis_client.set(key, validated)
except Exception as e:
    logger.error(f"Failed to process data: {e}")
```

**Categorize potential errors:**
- `fetch_market_data()` → NetworkError, APIError
- `validate_data()` → ValidationError
- `redis_client.set()` → InfrastructureError

### Step 2: Replace with Specific Catches

```python
# After migration
from shared.exceptions import (
    NetworkError,
    APIError,
    ValidationError,
    InfrastructureError,
)

try:
    data = fetch_market_data(symbol)
    validated = validate_data(data)
    await redis_client.set(key, validated)

except (NetworkError, APIError) as e:
    logger.warning(f"Failed to fetch data, will retry: {e}")
    raise  # Let caller handle retry logic

except ValidationError as e:
    logger.error(f"Invalid data format: {e}")
    return None  # Skip this record

except InfrastructureError as e:
    logger.error(f"Redis unavailable, skipping cache: {e}")
    # Continue without caching
```

### Step 3: Preserve `exc_info=True` for Debugging

Keep `exc_info=True` for unexpected errors:

```python
except TradingSystemError as e:
    # For unexpected errors, include full traceback
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

### Step 4: Add Exception Attributes

Use exception attributes for structured error information:

```python
# Before
raise ValidationError(f"Invalid price: {price}")

# After
from shared.exceptions import DataValidationError

raise DataValidationError(
    field="price",
    value=price,
    constraint="must be positive"
)
```

---

## Recovery Strategies

Different exception categories require different recovery approaches.

### 1. NetworkError - Retry with Backoff

**Strategy:** Exponential backoff with maximum retry count

```python
from shared.exceptions import NetworkError
import asyncio

async def fetch_with_retry(url: str, max_retries: int = 3):
    """Fetch with exponential backoff retry."""
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            return await fetch(url)

        except NetworkError as e:
            if attempt == max_retries - 1:
                # Final attempt failed
                logger.error(f"Failed after {max_retries} attempts: {e}")
                raise

            # Exponential backoff
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay}s")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
```

### 2. APIError - Rate Limit with Cooldown

**Strategy:** Wait for suggested cooldown period

```python
from shared.exceptions import KISRateLimitError, APIError

async def api_call_with_rate_limit(endpoint: str, params: dict):
    """API call with automatic rate limit handling."""
    try:
        return await kis_api.call(endpoint, params)

    except KISRateLimitError as e:
        # Wait for suggested period
        wait_time = e.retry_after or 1.0
        logger.warning(f"Rate limited, waiting {wait_time}s")
        await asyncio.sleep(wait_time)
        return await kis_api.call(endpoint, params)  # Single retry

    except APIError as e:
        # Other API errors (auth, validation) - don't retry
        logger.error(f"API error: {e}")
        raise
```

### 3. ValidationError - Reject and Continue

**Strategy:** Skip invalid data, continue processing

```python
from shared.exceptions import ValidationError, DataValidationError

async def process_batch(records: list[dict]):
    """Process batch, skipping invalid records."""
    results = []
    errors = []

    for record in records:
        try:
            validated = validate_record(record)
            result = await process_record(validated)
            results.append(result)

        except ValidationError as e:
            # Skip invalid record, continue with next
            logger.warning(f"Skipping invalid record: {e}")
            errors.append({"record": record, "error": str(e)})
            continue

    return {"results": results, "errors": errors}
```

### 4. InfrastructureError - Graceful Degradation

**Strategy:** Continue without optional services

```python
from shared.exceptions import RedisUnavailableError, InfrastructureError

async def get_with_cache(key: str) -> dict:
    """Get data with Redis cache fallback."""
    # Try cache first
    try:
        cached = await redis_client.get(key)
        if cached:
            logger.debug(f"Cache hit for {key}")
            return json.loads(cached)
    except RedisUnavailableError as e:
        # Degrade gracefully - continue without cache
        logger.warning(f"Cache unavailable, fetching from source: {e}")

    # Fetch from primary source
    data = await fetch_from_database(key)

    # Try to cache for next time (best effort)
    try:
        await redis_client.setex(key, 3600, json.dumps(data))
    except RedisUnavailableError:
        # Silent failure - cache is optional
        pass

    return data
```

### 5. ConfigurationError - Fail Fast

**Strategy:** Fail immediately during startup

```python
from shared.exceptions import MissingConfigError, InvalidConfigError

def validate_configuration(config: dict):
    """Validate configuration on startup."""
    # Check required fields
    if not config.get("kis_api_key"):
        raise MissingConfigError(
            config_key="kis_api_key",
            config_file="config/api.yaml"
        )

    # Validate values
    timeout = config.get("timeout", 0)
    if timeout <= 0:
        raise InvalidConfigError(
            config_key="timeout",
            value=timeout,
            reason="must be positive"
        )

    # No recovery - fail fast
    logger.info("Configuration validated successfully")
```

### 6. BusinessLogicError - Return User-Actionable Error

**Strategy:** Return error to user with actionable message

```python
from shared.exceptions import InsufficientBalanceError, InvalidPositionError

async def place_order(symbol: str, quantity: int, price: float):
    """Place order with business logic validation."""
    # Check balance
    required = quantity * price
    balance = await get_account_balance()

    if balance < required:
        raise InsufficientBalanceError(
            required=required,
            available=balance,
            symbol=symbol
        )

    # Check position state
    position = await get_position(symbol)
    if position.quantity <= 0:
        raise InvalidPositionError(
            symbol=symbol,
            current_state="closed",
            operation="exit position"
        )

    # Place order
    return await kis_api.place_order(symbol, quantity, price)
```

---

## Best Practices

### 1. Catch Specific Exceptions First

Always order exception handlers from specific to general:

```python
# ✅ Correct order: Specific → General
try:
    result = await operation()
except KISRateLimitError as e:        # Most specific
    handle_rate_limit(e)
except APIError as e:                 # More specific
    handle_api_error(e)
except NetworkError as e:             # Less specific
    handle_network_error(e)
except TradingSystemError as e:       # Most general
    handle_generic_error(e)
```

### 2. Always Chain Exceptions

Use `from` to preserve exception chain:

```python
# ✅ Correct: Preserve exception chain
try:
    data = json.loads(response_text)
except json.JSONDecodeError as e:
    raise ValidationError(f"Invalid JSON: {response_text[:100]}") from e

# ❌ Wrong: Loses original exception
try:
    data = json.loads(response_text)
except json.JSONDecodeError:
    raise ValidationError(f"Invalid JSON: {response_text[:100]}")
```

### 3. Use Structured Exception Attributes

Provide structured data for better debugging:

```python
# ✅ Good: Structured attributes
raise ConnectionTimeoutError(
    host="api.kis.com",
    port=443,
    timeout=30.0
)

# ❌ Bad: String-only message
raise NetworkError("Connection to api.kis.com:443 timed out after 30.0s")
```

### 4. Log with Appropriate Level

Choose log level based on exception severity and recovery:

```python
# ERROR: Unexpected errors or failures
except TradingSystemError as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)

# WARNING: Expected errors with recovery
except NetworkError as e:
    logger.warning(f"Network error, will retry: {e}")

# INFO: Normal business logic (optional)
except InsufficientBalanceError as e:
    logger.info(f"Order rejected: insufficient balance")
```

### 5. Don't Catch Programming Bugs

Let programming bugs propagate:

```python
# ✅ Correct: Don't catch TypeError, AttributeError, etc.
try:
    result = await fetch_data()
    await process(result)  # Let TypeError propagate if result is None
except NetworkError as e:
    # Only catch expected errors
    logger.warning(f"Network error: {e}")

# ❌ Wrong: Catches programming bugs
try:
    result = await fetch_data()
    await process(result)
except Exception as e:  # Catches TypeError, AttributeError, etc.
    logger.error(f"Error: {e}")  # Masks programming bugs
```

### 6. Use Circuit Breaker for Repeated Failures

Implement circuit breaker pattern for external services:

```python
from shared.exceptions import CircuitBreakerOpenError, NetworkError

class CircuitBreaker:
    def __init__(self, threshold: int = 5, timeout: float = 60.0):
        self.failure_count = 0
        self.threshold = threshold
        self.timeout = timeout
        self.opened_at = None

    async def call(self, func, *args, **kwargs):
        # Check if circuit breaker is open
        if self.opened_at:
            elapsed = time.time() - self.opened_at
            if elapsed < self.timeout:
                raise CircuitBreakerOpenError(
                    component=func.__name__,
                    reset_time=self.timeout - elapsed,
                    failure_count=self.failure_count
                )
            # Reset after timeout
            self.opened_at = None
            self.failure_count = 0

        try:
            result = await func(*args, **kwargs)
            self.failure_count = 0  # Reset on success
            return result

        except (NetworkError, APIError) as e:
            self.failure_count += 1
            if self.failure_count >= self.threshold:
                # Open circuit breaker
                self.opened_at = time.time()
                logger.error(f"Circuit breaker opened after {self.failure_count} failures")
            raise
```

---

## Common Patterns

### Pattern 1: Retry Loop with Exponential Backoff

```python
async def retry_with_backoff(
    func,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    **kwargs
):
    """Execute function with exponential backoff retry."""
    delay = initial_delay

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)

        except (NetworkError, APIError) as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed after {max_retries} attempts: {e}")
                raise

            logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
            delay *= 2  # Exponential backoff
```

### Pattern 2: Graceful Degradation with Fallback

```python
async def fetch_with_fallback(key: str):
    """Fetch with multiple fallback strategies."""
    # Try primary source
    try:
        return await fetch_from_cache(key)
    except InfrastructureError as e:
        logger.warning(f"Cache unavailable, trying database: {e}")

    # Fallback to database
    try:
        return await fetch_from_database(key)
    except InfrastructureError as e:
        logger.warning(f"Database unavailable, trying API: {e}")

    # Final fallback to API
    try:
        return await fetch_from_api(key)
    except (NetworkError, APIError) as e:
        logger.error(f"All sources failed: {e}")
        raise
```

### Pattern 3: Batch Processing with Error Collection

```python
async def process_batch_with_errors(items: list):
    """Process batch, collecting errors for later analysis."""
    results = []
    errors = []

    for item in items:
        try:
            result = await process_item(item)
            results.append({"item": item, "result": result, "status": "success"})

        except ValidationError as e:
            # Expected error: Skip item
            errors.append({"item": item, "error": str(e), "type": "validation"})

        except NetworkError as e:
            # Transient error: Retry later
            errors.append({"item": item, "error": str(e), "type": "network"})

        except TradingSystemError as e:
            # Unexpected error: Log and continue
            logger.error(f"Unexpected error processing {item}: {e}", exc_info=True)
            errors.append({"item": item, "error": str(e), "type": "unexpected"})

    return {"results": results, "errors": errors}
```

### Pattern 4: Context Manager for Resource Cleanup

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def managed_websocket(url: str):
    """Context manager for WebSocket with proper cleanup."""
    ws = None
    try:
        ws = await connect_websocket(url)
        yield ws

    except WebSocketDisconnectError as e:
        logger.warning(f"WebSocket disconnected: {e}")
        raise

    finally:
        # Always cleanup
        if ws:
            try:
                await ws.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")
```

### Pattern 5: Async Task with Exception Propagation

```python
async def supervised_task(coro):
    """Run coroutine with exception handling and logging."""
    try:
        return await coro

    except ValidationError as e:
        # Expected error: Log and return None
        logger.warning(f"Validation error in task: {e}")
        return None

    except (NetworkError, InfrastructureError) as e:
        # Transient error: Log and retry
        logger.warning(f"Transient error in task, will retry: {e}")
        await asyncio.sleep(5.0)
        return await coro  # Simple retry

    except TradingSystemError as e:
        # Unexpected error: Log with traceback and propagate
        logger.error(f"Unexpected error in task: {e}", exc_info=True)
        raise

    except Exception as e:
        # Programming bug: Always propagate
        logger.error(f"Programming bug in task: {e}", exc_info=True)
        raise
```

---

## Testing Exception Handling

### Unit Testing Exceptions

```python
import pytest
from shared.exceptions import (
    KISRateLimitError,
    ValidationError,
    InsufficientBalanceError,
)

class TestOrderPlacement:
    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """Test rate limit handling."""
        with pytest.raises(KISRateLimitError) as exc_info:
            await place_order_when_rate_limited()

        assert exc_info.value.retry_after > 0
        assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validation_error(self):
        """Test validation error handling."""
        with pytest.raises(ValidationError) as exc_info:
            await place_order(symbol="", quantity=-1, price=0)

        assert "invalid" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_insufficient_balance(self):
        """Test insufficient balance handling."""
        with pytest.raises(InsufficientBalanceError) as exc_info:
            await place_order_with_insufficient_balance()

        assert exc_info.value.required > exc_info.value.available
        assert exc_info.value.symbol == "005930"
```

### Integration Testing with Mock Failures

```python
from unittest.mock import AsyncMock, patch
import pytest

class TestAPIErrorRecovery:
    @pytest.mark.asyncio
    async def test_retry_on_network_error(self):
        """Test retry logic on network error."""
        mock_api = AsyncMock()
        mock_api.call.side_effect = [
            NetworkError("Connection failed"),  # First attempt fails
            NetworkError("Connection failed"),  # Second attempt fails
            {"success": True},                   # Third attempt succeeds
        ]

        result = await api_call_with_retry(mock_api)

        assert result == {"success": True}
        assert mock_api.call.call_count == 3

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation when cache fails."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RedisUnavailableError(
            operation="get",
            key="test_key"
        )

        result = await fetch_with_cache_fallback("test_key", mock_redis)

        # Should fetch from database instead
        assert result is not None
        assert mock_redis.get.called
```

---

## Logging Best Practices

### 1. Include Context in Log Messages

```python
# ✅ Good: Includes context
logger.error(
    f"Failed to process order {order_id} for {symbol}: {e}",
    exc_info=True,
    extra={"order_id": order_id, "symbol": symbol}
)

# ❌ Bad: No context
logger.error(f"Error: {e}")
```

### 2. Use `exc_info=True` for Unexpected Errors

```python
# ✅ Correct: exc_info for unexpected errors
except TradingSystemError as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)

# ✅ Correct: No exc_info for expected errors
except KISRateLimitError as e:
    logger.warning(f"Rate limited, will retry: {e}")
```

### 3. Log at Appropriate Levels

| Level | When to Use | Example |
|-------|-------------|---------|
| `DEBUG` | Detailed debugging info | `logger.debug(f"Cache hit for {key}")` |
| `INFO` | Normal operations | `logger.info(f"Order placed: {order_id}")` |
| `WARNING` | Expected errors with recovery | `logger.warning(f"Rate limited, retrying")` |
| `ERROR` | Unexpected errors or failures | `logger.error(f"Unexpected error", exc_info=True)` |
| `CRITICAL` | System-level failures | `logger.critical(f"Database unavailable")` |

### 4. Structure Logs for Analysis

```python
# ✅ Good: Structured logging
logger.error(
    "Order placement failed",
    exc_info=True,
    extra={
        "order_id": order_id,
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "error_type": type(e).__name__,
        "retry_count": retry_count,
    }
)
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Too Many Broad Exception Catches

**Problem:**
```python
except Exception as e:
    logger.error(f"Error: {e}")
```

**Solution:**
```python
# Catch specific exceptions
except NetworkError as e:
    logger.warning(f"Network error: {e}")
except ValidationError as e:
    logger.error(f"Validation error: {e}")
except TradingSystemError as e:
    logger.error(f"Trading system error: {e}", exc_info=True)
```

#### Issue 2: Programming Bugs Masked by Broad Catches

**Problem:**
```python
try:
    result = data["price"]  # KeyError if key missing
except Exception:
    return None  # Silently masks programming bug
```

**Solution:**
```python
try:
    result = data["price"]
except KeyError:
    # Let KeyError propagate - it's a programming bug
    raise
```

#### Issue 3: Not Using Exception Attributes

**Problem:**
```python
raise ValidationError(f"Invalid price: {price}")
```

**Solution:**
```python
raise DataValidationError(
    field="price",
    value=price,
    constraint="must be positive"
)
```

#### Issue 4: Retrying Non-Retryable Errors

**Problem:**
```python
# Retrying validation errors (won't help)
except ValidationError as e:
    await asyncio.sleep(1.0)
    return await operation()  # Will fail again
```

**Solution:**
```python
# Don't retry validation errors
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    return None  # Reject
```

---

## When to Use Broad `except Exception`

In rare cases, broad exception catches are acceptable:

### 1. Final Fallback After Specific Catches

```python
try:
    result = await operation()
except NetworkError as e:
    handle_network_error(e)
except ValidationError as e:
    handle_validation_error(e)
except Exception as e:  # ✅ Acceptable: Final fallback
    # Catch unexpected errors (likely programming bugs)
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

### 2. Generic Retry Utility

```python
def with_retry(func):
    """Generic retry decorator for any function."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:  # ✅ Acceptable: Generic utility
            # NOTE: Intentionally broad - caller decides retry logic
            logger.warning(f"Retry attempt failed: {e}")
            raise
    return wrapper
```

### 3. Background Task with Crash Prevention

```python
async def background_task():
    """Background task that must never crash the event loop."""
    while True:
        try:
            await do_work()
        except Exception as e:  # ✅ Acceptable: Prevent crash
            # Catch all errors to prevent event loop crash
            logger.error(f"Background task error: {e}", exc_info=True)
            await asyncio.sleep(60)  # Cooldown
```

**Requirements for acceptable broad catches:**
1. Must have explicit comment explaining why
2. Must include `exc_info=True` in logging
3. Must be after specific exception handlers (when applicable)

---

## Summary Checklist

When handling exceptions in trading system code:

- [ ] Identify specific exception categories (Network, API, Validation, etc.)
- [ ] Catch specific exceptions first, general exceptions last
- [ ] Use exception attributes for structured error information
- [ ] Chain exceptions with `from` to preserve context
- [ ] Choose appropriate recovery strategy per exception type
- [ ] Log with appropriate level (WARNING for expected, ERROR for unexpected)
- [ ] Include `exc_info=True` for unexpected errors
- [ ] Don't catch programming bugs (TypeError, AttributeError, etc.)
- [ ] Test exception handling with unit and integration tests
- [ ] Document intentional broad exception catches

---

## Additional Resources

- [Exception Hierarchy Documentation](./exception_hierarchy.md) - Complete exception reference
- [VERIFICATION_REPORT.md](../VERIFICATION_REPORT.md) - Migration verification results
- [shared/exceptions/__init__.py](../shared/exceptions/__init__.py) - Exception source code
- [CLAUDE.md](../CLAUDE.md) - Project architecture and patterns

---

## Version History

- **2026-03-06:** Initial documentation created for exception hierarchy refactor
- Migration completed: ~115+ broad exception blocks replaced across 20+ files
- All service layers migrated to typed exception hierarchy
