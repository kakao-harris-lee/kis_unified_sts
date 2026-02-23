# KIS API Rate Limiter Design

**Date**: 2026-01-22
**Status**: Implemented (2026-01-22)

## Problem Statement

The current architecture runs Stock and Futures orchestrators as separate processes on the same host. Without coordination:

1. **Race Condition**: Both processes may exhaust the KIS API rate limit (20 req/sec per app-key), causing 429 errors
2. **Execution Latency**: If one process exhausts the quota, the other is blocked

## Solution: Separate API Keys with Redis Rate Limiting

Since separate KIS API keys can be used for Stock vs Futures, each orchestrator gets its own 20 req/sec limit. Redis provides cross-process coordination for each key.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                            Redis                                 │
│  ┌─────────────────────┐     ┌─────────────────────────────┐   │
│  │ kis:ratelimit:stock │     │ kis:ratelimit:futures       │   │
│  │ (20 req/sec)        │     │ (20 req/sec)                │   │
│  └─────────────────────┘     └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
           ▲                              ▲
           │                              │
┌──────────┴──────────┐      ┌───────────┴───────────┐
│  Stock Orchestrator │      │  Futures Orchestrator │
│  ┌────────────────┐ │      │  ┌─────────────────┐  │
│  │ OrderExecutor  │ │      │  │ OrderExecutor   │  │
│  │ + RateLimiter  │ │      │  │ + RateLimiter   │  │
│  │ (key: stock)   │ │      │  │ (key: futures)  │  │
│  └────────────────┘ │      │  └─────────────────┘  │
└─────────────────────┘      └───────────────────────┘
           │                              │
           ▼                              ▼
      KIS API Key A                 KIS API Key B
```

**Benefits:**
- No cross-process coordination complexity
- Futures never blocked by stock (and vice versa)
- Each has full 20 req/sec capacity
- Simple failure isolation

## Components

### 1. RedisRateLimiter

**File**: `shared/execution/rate_limiter.py`

Uses Redis sorted sets for sliding window rate limiting:

```python
class RedisRateLimiter:
    """Distributed rate limiter using Redis sliding window."""

    def __init__(
        self,
        redis_url: str,
        key_prefix: str,           # "stock" or "futures"
        requests_per_second: float = 20.0,
        window_size: float = 1.0,  # 1 second window
    ):
        self.redis = Redis.from_url(redis_url)
        self.key = f"kis:ratelimit:{key_prefix}"
        self.max_requests = int(requests_per_second * window_size)
        self.window_size = window_size

    async def acquire(self, timeout: float = 5.0) -> bool:
        """
        Acquire permission to make an API call.

        Returns True if allowed, blocks up to timeout if rate limited.
        Raises RateLimitExceeded if timeout expires.
        """
        # Uses Lua script for atomic check-and-add

    async def get_metrics(self) -> dict:
        """Return current rate limit status for monitoring."""
```

**Lua Script (atomic operation):**

```lua
-- Remove expired entries, count current, add if under limit
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])

-- Remove old entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current requests
local count = redis.call('ZCARD', key)

if count < max_requests then
    -- Add this request
    redis.call('ZADD', key, now, now .. '-' .. math.random())
    redis.call('EXPIRE', key, window * 2)
    return 1  -- Allowed
else
    return 0  -- Rate limited
end
```

### 2. Updated ExecutionConfig

**File**: `shared/execution/config.py`

```python
class ExecutionConfig(BaseModel):
    # ... existing fields ...

    # Rate limiting (NEW)
    redis_url: str = Field(default="", description="Redis URL for rate limiting")
    rate_limit_key: str = Field(default="default", description="Rate limit key: 'stock' or 'futures'")
    requests_per_second: float = Field(default=20.0, description="KIS API rate limit")
    rate_limit_timeout: float = Field(default=5.0, description="Max wait time when rate limited")
```

### 3. Updated OrderExecutor

**File**: `shared/execution/executor.py`

```python
class OrderExecutor:
    def __init__(self, config: ExecutionConfig, ...):
        # ... existing init ...

        # Rate limiter (NEW)
        self._rate_limiter: RedisRateLimiter | None = None
        if config.redis_url:
            self._rate_limiter = RedisRateLimiter(
                redis_url=config.redis_url,
                key_prefix=config.rate_limit_key,
                requests_per_second=config.requests_per_second,
            )

    async def execute_order(self, order: OrderRequest) -> OrderResponse:
        # Acquire rate limit BEFORE retry loop
        if self._rate_limiter:
            try:
                await self._rate_limiter.acquire(timeout=self.config.rate_limit_timeout)
            except RateLimitExceeded:
                return OrderResponse(
                    success=False,
                    message="Rate limit exceeded, try again later"
                )

        # ... existing retry logic ...
```

### 4. Exceptions

**File**: `shared/execution/exceptions.py`

```python
class RateLimitExceeded(Exception):
    """Raised when rate limit timeout expires."""
    def __init__(self, key: str, wait_time: float):
        self.key = key
        self.wait_time = wait_time
        super().__init__(f"Rate limit exceeded for '{key}', retry after {wait_time:.2f}s")

class RedisConnectionError(Exception):
    """Raised when Redis is unavailable."""
    pass
```

## Error Handling

### Graceful Degradation (Fail-Open)

```python
async def acquire(self, timeout: float = 5.0) -> bool:
    try:
        # ... rate limit logic ...
    except redis.ConnectionError as e:
        # Redis down - log warning, allow request (fail-open)
        logger.warning(f"Redis unavailable, bypassing rate limit: {e}")
        return True  # Don't block trading if Redis fails
```

**Rationale**: Trading shouldn't stop due to rate limiter infrastructure failure. Worst case is occasional 429 from KIS API, which existing retry logic handles.

## Monitoring

```python
# In RedisRateLimiter
async def get_metrics(self) -> dict:
    return {
        "rate_limit_key": self.key,
        "current_usage": await self._get_current_count(),
        "max_requests": self.max_requests,
        "utilization_pct": (current / self.max_requests) * 100,
    }
```

Exposed via Prometheus metrics:
- `kis_api_rate_limit_usage{key="stock"}`
- `kis_api_rate_limit_usage{key="futures"}`

## Usage

```python
# Stock orchestrator
executor = OrderExecutor(ExecutionConfig(
    redis_url="redis://localhost:6379",
    rate_limit_key="stock",
    trading_mode="MOCK",
))

# Futures orchestrator (separate process)
executor = OrderExecutor(ExecutionConfig(
    redis_url="redis://localhost:6379",
    rate_limit_key="futures",
    trading_mode="MOCK",
))
```

## File Structure

```
shared/execution/
├── __init__.py
├── config.py          # UPDATE: add redis_url, rate_limit_key
├── executor.py        # UPDATE: integrate rate limiter
├── models.py          # Existing
├── exceptions.py      # NEW: RateLimitExceeded, RedisConnectionError
└── rate_limiter.py    # NEW: RedisRateLimiter

tests/unit/execution/
├── test_executor.py   # Existing
├── test_rate_limiter.py        # NEW: unit tests with mock Redis
└── test_rate_limiter_redis.py  # NEW: integration tests (needs Redis)
```

## Testing Strategy

### Unit Tests

```python
class TestRedisRateLimiter:
    def test_allows_under_limit(self): ...
    def test_blocks_over_limit(self): ...
    def test_sliding_window_expires(self): ...
    def test_timeout_raises_exception(self): ...
    def test_redis_down_fails_open(self): ...

class TestOrderExecutorWithRateLimiter:
    def test_acquires_before_order(self): ...
    def test_rate_limit_error_returns_failure(self): ...
    def test_works_without_redis_configured(self): ...
```

### Integration Test

```python
@pytest.mark.integration
async def test_two_processes_share_rate_limit():
    """Simulate stock + futures processes hitting shared Redis."""
    # Spawn two async tasks simulating separate processes
    # Both try to make 15 req/sec each
    # Verify each stays within their 20 req/sec limit
    # Verify no cross-contamination between keys
```

## Estimation

- **New code**: ~200 lines
- **Tests**: ~150 lines
- **Config changes**: ~20 lines
