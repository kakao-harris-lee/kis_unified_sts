# Multi-Review Remediation Plan

**Status**: Implemented (2026-01-21)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all issues identified in the multi-review for Phase 4 (Dashboard & Strategies).

**Priority:** Critical issues first, then major, then minor.

---

## Overview

| Priority | Count | Description |
|----------|-------|-------------|
| Critical | 7 | Must fix before production |
| Major | 10 | Important to fix |
| Minor | 7 | Nice to have |

**Estimated Tasks:** 15 bite-sized tasks

---

## Task 1: Fix CORS Configuration (Critical)

**Files:**
- Edit: `services/dashboard/app.py`
- Test: `tests/unit/dashboard/test_cors.py`

**Step 1: Write the failing test**

```python
# tests/unit/dashboard/test_cors.py
"""Test CORS configuration security."""
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch


@pytest.fixture
def mock_services():
    """Mock external services."""
    with patch("services.dashboard.app.TradingOrchestrator"):
        with patch("services.dashboard.app.MetricsCollector"):
            yield


@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin(mock_services):
    """Test that CORS rejects requests from unknown origins."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "GET",
            }
        )

        # Should not have Access-Control-Allow-Origin for unknown origin
        assert "access-control-allow-origin" not in response.headers or \
               response.headers.get("access-control-allow-origin") != "https://malicious-site.com"


@pytest.mark.asyncio
async def test_cors_allows_configured_origin(mock_services):
    """Test that CORS allows requests from configured origins."""
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )

        # Should allow localhost:3000
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/dashboard/test_cors.py -v`
Expected: FAIL (current config allows any origin)

**Step 3: Fix CORS configuration**

Edit `services/dashboard/app.py`:

```python
# Replace the CORS middleware section
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Check if in development mode
if os.getenv("DASHBOARD_DEV_MODE", "false").lower() == "true":
    ALLOWED_ORIGINS.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/dashboard/test_cors.py -v`
Expected: PASS

---

## Task 2: Fix WebSocket Auth Bypass (Critical)

**Files:**
- Edit: `services/dashboard/middleware/auth.py`
- Test: `tests/unit/dashboard/test_websocket_auth.py`

**Step 1: Write the failing test**

```python
# tests/unit/dashboard/test_websocket_auth.py
"""Test WebSocket authentication."""
import pytest
from starlette.testclient import TestClient
from unittest.mock import patch, AsyncMock


@pytest.fixture
def mock_services():
    """Mock external services."""
    with patch("services.dashboard.app.TradingOrchestrator"):
        with patch("services.dashboard.app.MetricsCollector"):
            yield


def test_websocket_requires_auth(mock_services):
    """Test that WebSocket connections require authentication."""
    from services.dashboard.app import create_app

    app = create_app()
    client = TestClient(app)

    # WebSocket without API key should fail
    with pytest.raises(Exception):  # WebSocket rejection
        with client.websocket_connect("/ws"):
            pass


def test_websocket_with_valid_auth(mock_services):
    """Test WebSocket with valid API key."""
    import os
    from services.dashboard.app import create_app

    os.environ["DASHBOARD_API_KEY"] = "test-api-key"

    app = create_app()
    client = TestClient(app)

    # WebSocket with API key in query params should work
    with client.websocket_connect("/ws?api_key=test-api-key") as ws:
        # Connection should be established
        pass
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/dashboard/test_websocket_auth.py -v`
Expected: FAIL (WebSocket bypasses auth)

**Step 3: Fix WebSocket authentication**

Edit `services/dashboard/middleware/auth.py`:

```python
async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "http":
        request = Request(scope)
        path = request.url.path

        # Skip auth for specific paths only
        if path in ("/api/v1/health", "/docs", "/openapi.json", "/redoc"):
            await self.app(scope, receive, send)
            return

        # Check API key
        api_key = request.headers.get("x-api-key")
        if not self._validate_api_key(api_key):
            response = JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"}
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    elif scope["type"] == "websocket":
        # WebSocket auth via query params
        request = Request(scope)
        api_key = request.query_params.get("api_key")

        if not self._validate_api_key(api_key):
            # Reject WebSocket connection
            await send({"type": "websocket.close", "code": 4001})
            return

        await self.app(scope, receive, send)
    else:
        await self.app(scope, receive, send)

def _validate_api_key(self, api_key: str | None) -> bool:
    """Validate API key with timing-safe comparison."""
    if not api_key or not self.api_key:
        return False
    return hmac.compare_digest(api_key, self.api_key)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/dashboard/test_websocket_auth.py -v`
Expected: PASS

---

## Task 3: Fix Timing Attack Vulnerability (Critical)

**Files:**
- Edit: `services/dashboard/middleware/auth.py`
- Test: `tests/unit/dashboard/test_auth_timing.py`

**Step 1: The fix is included in Task 2** (using hmac.compare_digest)

The key change is replacing:
```python
# VULNERABLE
if api_key != self.api_key:
```

With:
```python
# SECURE - timing-safe comparison
import hmac
if not hmac.compare_digest(api_key, self.api_key):
```

---

## Task 4: Fix Rate Limiter Memory Leak (Critical)

**Files:**
- Edit: `services/dashboard/middleware/rate_limit.py`
- Test: `tests/unit/dashboard/test_rate_limit_memory.py`

**Step 1: Write the failing test**

```python
# tests/unit/dashboard/test_rate_limit_memory.py
"""Test rate limiter memory management."""
import pytest
import time
from unittest.mock import MagicMock


def test_rate_limiter_cleans_old_entries():
    """Test that rate limiter cleans up old request timestamps."""
    from services.dashboard.middleware.rate_limit import RateLimitMiddleware

    middleware = RateLimitMiddleware(
        app=MagicMock(),
        requests_per_minute=10
    )

    # Simulate old requests
    old_time = time.time() - 120  # 2 minutes ago
    middleware._request_times["client1"] = [old_time] * 5
    middleware._request_times["client2"] = [old_time] * 5

    # Trigger cleanup
    middleware._cleanup_old_entries()

    # Old entries should be cleaned
    assert len(middleware._request_times.get("client1", [])) == 0
    assert len(middleware._request_times.get("client2", [])) == 0


def test_rate_limiter_periodic_cleanup():
    """Test that cleanup runs periodically."""
    from services.dashboard.middleware.rate_limit import RateLimitMiddleware

    middleware = RateLimitMiddleware(
        app=MagicMock(),
        requests_per_minute=10
    )

    # Add some entries
    now = time.time()
    middleware._request_times["client1"] = [now - 120]  # Old
    middleware._request_times["client2"] = [now]  # Current

    # Cleanup should remove old, keep current
    middleware._cleanup_old_entries()

    assert "client1" not in middleware._request_times or \
           len(middleware._request_times["client1"]) == 0
    assert len(middleware._request_times.get("client2", [])) == 1
```

**Step 2: Fix rate limiter**

Edit `services/dashboard/middleware/rate_limit.py`:

```python
import time
import asyncio
from collections import defaultdict
from typing import Dict, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with memory cleanup."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window = 60  # seconds
        self._request_times: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Use client IP, but don't trust X-Forwarded-For blindly
        # In production, configure trusted proxies properly
        client = request.client
        if client:
            return client.host
        return "unknown"

    def _cleanup_old_entries(self) -> None:
        """Remove expired timestamps from all clients."""
        now = time.time()
        cutoff = now - self.window

        # Create list of keys to avoid modifying dict during iteration
        clients_to_check = list(self._request_times.keys())

        for client_id in clients_to_check:
            timestamps = self._request_times[client_id]
            # Keep only recent timestamps
            self._request_times[client_id] = [
                ts for ts in timestamps if ts > cutoff
            ]
            # Remove empty entries
            if not self._request_times[client_id]:
                del self._request_times[client_id]

    async def dispatch(self, request: Request, call_next):
        """Rate limit incoming requests."""
        now = time.time()

        # Periodic cleanup
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries()
            self._last_cleanup = now

        client_id = self._get_client_id(request)
        cutoff = now - self.window

        # Filter old timestamps for this client
        timestamps = self._request_times[client_id]
        self._request_times[client_id] = [
            ts for ts in timestamps if ts > cutoff
        ]

        # Check rate limit
        if len(self._request_times[client_id]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"}
            )

        # Record this request
        self._request_times[client_id].append(now)

        return await call_next(request)
```

**Step 3: Run tests**

Run: `pytest tests/unit/dashboard/test_rate_limit_memory.py -v`
Expected: PASS

---

## Task 5: Add from_dict Methods to Config Classes (Major)

**Files:**
- Edit: `shared/strategy/entry/v35_optimized.py`
- Edit: `shared/strategy/entry/stochrsi_trend.py`
- Edit: `shared/strategy/entry/mean_reversion.py`
- Edit: `shared/strategy/entry/breakout.py`

**Step 1: Add from_dict class method to each config**

```python
@dataclass
class V35Config:
    """V35 전략 설정"""
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    rsi_oversold: int = 30
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    @classmethod
    def from_dict(cls, data: dict) -> "V35Config":
        """Create config from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
```

Apply the same pattern to all 4 config classes.

---

## Task 6: Fix Registry Global Mutable State (Major)

**Files:**
- Edit: `shared/strategy/registry.py`
- Test: `tests/unit/strategy/test_registry_isolation.py`

**Step 1: Write the failing test**

```python
# tests/unit/strategy/test_registry_isolation.py
"""Test registry isolation."""
import pytest


def test_registry_clear_isolates_tests():
    """Test that clear() properly isolates test runs."""
    from shared.strategy.registry import EntryRegistry

    # Clear first
    EntryRegistry.clear()

    # Register a test component
    @EntryRegistry.register("test_strategy")
    class TestStrategy:
        pass

    assert "test_strategy" in EntryRegistry.list_all()

    # Clear again
    EntryRegistry.clear()

    # Should be empty
    assert "test_strategy" not in EntryRegistry.list_all()
```

**Step 2: Add clear() method to registry**

Edit `shared/strategy/registry.py`:

```python
class ComponentRegistry:
    """Component registry base class."""

    _components: dict[str, type] = {}

    @classmethod
    def clear(cls) -> None:
        """Clear all registered components."""
        cls._components = {}

    @classmethod
    def register(cls, name: str):
        """Register a component."""
        def decorator(component_class: type) -> type:
            cls._components[name] = component_class
            return component_class
        return decorator

    # ... rest of methods
```

---

## Task 7: Add WebSocket Connection Limits (Major)

**Files:**
- Edit: `services/dashboard/websocket.py`
- Test: `tests/unit/dashboard/test_websocket_limits.py`

**Step 1: Add connection limits**

```python
class WebSocketManager:
    """WebSocket connection manager with limits."""

    MAX_CONNECTIONS_PER_CLIENT = 5
    MAX_TOTAL_CONNECTIONS = 100

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._client_connections: Dict[str, int] = defaultdict(int)

    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        """Connect with limit checks."""
        # Check per-client limit
        if self._client_connections[client_id] >= self.MAX_CONNECTIONS_PER_CLIENT:
            await websocket.close(code=4002, reason="Too many connections")
            return False

        # Check total limit
        total = sum(self._client_connections.values())
        if total >= self.MAX_TOTAL_CONNECTIONS:
            await websocket.close(code=4003, reason="Server at capacity")
            return False

        await websocket.accept()
        self._connections[client_id].add(websocket)
        self._client_connections[client_id] += 1
        return True
```

---

## Task 8: Add Missing WebSocket Tests (Major)

**Files:**
- Create: `tests/unit/dashboard/test_websocket_manager.py`

**Step 1: Write tests**

```python
# tests/unit/dashboard/test_websocket_manager.py
"""Test WebSocket manager."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_websocket_connect():
    """Test WebSocket connection."""
    from services.dashboard.websocket import WebSocketManager

    manager = WebSocketManager()
    ws = AsyncMock()

    result = await manager.connect(ws, "client1")

    assert result is True
    ws.accept.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_subscribe_channel():
    """Test channel subscription."""
    from services.dashboard.websocket import WebSocketManager

    manager = WebSocketManager()
    ws = AsyncMock()

    await manager.connect(ws, "client1")
    manager.subscribe(ws, "positions")

    assert "positions" in manager.get_subscriptions(ws)


@pytest.mark.asyncio
async def test_websocket_broadcast():
    """Test broadcast to channel."""
    from services.dashboard.websocket import WebSocketManager

    manager = WebSocketManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(ws1, "client1")
    await manager.connect(ws2, "client2")

    manager.subscribe(ws1, "signals")
    manager.subscribe(ws2, "signals")

    await manager.broadcast("signals", {"type": "signal", "data": {}})

    ws1.send_json.assert_called_once()
    ws2.send_json.assert_called_once()
```

---

## Task 9: Add Pagination Tests (Major)

**Files:**
- Create: `tests/unit/dashboard/test_pagination.py`

**Step 1: Write pagination tests**

```python
# tests/unit/dashboard/test_pagination.py
"""Test API pagination."""
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch


@pytest.fixture
def mock_services():
    """Mock external services."""
    with patch("services.dashboard.app.TradingOrchestrator"):
        with patch("services.dashboard.app.MetricsCollector"):
            yield


@pytest.mark.asyncio
async def test_trades_pagination(mock_services):
    """Test trades endpoint pagination."""
    import os
    from services.dashboard.app import create_app

    os.environ["DASHBOARD_API_KEY"] = "test-key"
    os.environ["DASHBOARD_DEV_MODE"] = "true"

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/trades",
            headers={"X-API-Key": "test-key"},
            params={"page": 1, "page_size": 10}
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data


@pytest.mark.asyncio
async def test_signals_pagination(mock_services):
    """Test signals endpoint pagination."""
    import os
    from services.dashboard.app import create_app

    os.environ["DASHBOARD_API_KEY"] = "test-key"
    os.environ["DASHBOARD_DEV_MODE"] = "true"

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/signals",
            headers={"X-API-Key": "test-key"},
            params={"page": 1, "page_size": 20}
        )

        assert response.status_code == 200
```

---

## Task 10: Fix Silent ImportError in Registry (Major)

**Files:**
- Edit: `shared/strategy/registry.py`

**Step 1: Add proper error handling**

```python
def register_builtin_components() -> None:
    """Register all builtin strategy components."""
    # Entry strategies
    try:
        from shared.strategy.entry.v35_optimized import V35OptimizedEntry
        EntryRegistry._components["v35_optimized"] = V35OptimizedEntry
    except ImportError as e:
        logger.error(f"Failed to import V35OptimizedEntry: {e}")
        raise

    # ... similar for other strategies
```

---

## Task 11: Add Missing Microstructure Tests (Major)

**Files:**
- Create: `tests/unit/strategy/entry/test_microstructure.py`

**Step 1: Check if microstructure entry exists and add tests**

---

## Task 12: Fix Division by Zero in Confidence Calculations (Minor)

**Files:**
- Edit: `shared/strategy/entry/breakout.py`
- Edit: `shared/strategy/entry/mean_reversion.py`

**Step 1: Add zero checks**

```python
def _calculate_confidence(...) -> float:
    """Calculate signal confidence 0-1."""
    # Add safe division
    if volume_ma <= 0:
        volume_ratio = 1.0
    else:
        volume_ratio = volume / volume_ma

    # ... rest of calculation
```

---

## Task 13: Remove Duplicated Pagination Logic (Minor)

**Files:**
- Edit: `services/dashboard/routes.py`

**Step 1: Extract common pagination helper**

```python
def paginate(items: list, page: int, page_size: int) -> dict:
    """Common pagination helper."""
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
```

---

## Task 14: Add Config Validation Tests (Minor)

**Files:**
- Create: `tests/unit/strategy/test_config_validation.py`

---

## Task 15: Verify All Tests Pass

**Step 1: Run full test suite**

```bash
pytest tests/unit/ -v
```

**Step 2: Run coverage**

```bash
pytest tests/unit/ --cov=shared --cov=services --cov-report=html
```

---

## Dependencies

None - all fixes are in existing codebase.

---

## Testing Commands

```bash
# Run all dashboard tests
pytest tests/unit/dashboard/ -v

# Run all strategy tests
pytest tests/unit/strategy/ -v

# Run with coverage
pytest tests/unit/ --cov=shared --cov=services --cov-report=term-missing
```

---

**Created:** 2026-01-21
