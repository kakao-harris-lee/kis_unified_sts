# Phase 4: Dashboard & Additional Strategies Migration Plan

**Status**: Implemented (2026-01-20)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate Dashboard API/Frontend and additional trading strategies from quant_moment_sts.

**Architecture:** FastAPI backend, React frontend, WebSocket for real-time updates.

**Tech Stack:** Python 3.11+, FastAPI, React, TypeScript, WebSocket, SQLite/PostgreSQL

---

## Overview

| # | Component | Source | Lines | Description |
|---|-----------|--------|-------|-------------|
| 1 | Dashboard API | quant_moment_sts | ~2000 | FastAPI REST/WebSocket |
| 2 | Dashboard Frontend | quant_moment_sts | ~5000 | React/TypeScript UI |
| 3 | Entry Strategies (8) | quant_moment_sts | ~2000 | V35, StochRSI, etc. |
| 4 | Exit Strategies (4) | quant_moment_sts | ~800 | Regime, Time, ATR |
| 5 | Mean Reversion | kospi_mini_sts | 209 | Bollinger/RSI |
| 6 | Breakout | kospi_mini_sts | 245 | N-period breakout |

**Estimated Tasks:** 25 bite-sized tasks

---

## Part A: Dashboard Backend (Tasks 1-10)

### Task 1: Dashboard API Structure

**Files:**
- Create: `services/dashboard/__init__.py`
- Create: `services/dashboard/app.py`
- Test: `tests/unit/dashboard/test_app.py`

**Step 1: Write the failing test**

```python
# tests/unit/dashboard/test_app.py
"""Test dashboard FastAPI app."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_app_creation():
    """Test FastAPI app is created."""
    from services.dashboard.app import create_app

    app = create_app()
    assert app is not None
    assert app.title == "KIS Unified Trading Dashboard"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/dashboard/test_app.py -v`
Expected: FAIL with "No module named 'services.dashboard'"

**Step 3: Write minimal implementation**

```python
# services/dashboard/__init__.py
"""Dashboard service module."""

# services/dashboard/app.py
"""FastAPI dashboard application."""
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def create_app(
    title: str = "KIS Unified Trading Dashboard",
    debug: bool = False,
) -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title=title,
        description="Real-time trading dashboard for KIS unified platform",
        version="1.0.0",
        debug=debug,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register API routes."""

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
        }

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"message": "KIS Unified Trading Dashboard API"}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/dashboard/test_app.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/dashboard/ tests/unit/dashboard/
git commit -m "feat(dashboard): add FastAPI app factory"
```

---

### Task 2: Trading Status API

**Files:**
- Create: `services/dashboard/routes/trading.py`
- Test: `tests/unit/dashboard/test_trading.py`

**Step 1: Write the failing test**

```python
# tests/unit/dashboard/test_trading.py
"""Test trading status endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_trading_status():
    """Test trading status endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/trading/status")

    assert response.status_code == 200
    data = response.json()
    assert "is_running" in data
    assert "market_status" in data


@pytest.mark.asyncio
async def test_positions_list():
    """Test positions list endpoint."""
    from services.dashboard.app import create_app

    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/trading/positions")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/dashboard/test_trading.py -v`
Expected: FAIL with "404 Not Found"

**Step 3: Write minimal implementation**

```python
# services/dashboard/routes/__init__.py
"""Dashboard API routes."""

# services/dashboard/routes/trading.py
"""Trading status and control endpoints."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/trading", tags=["trading"])


class TradingStatus(BaseModel):
    is_running: bool
    market_status: str
    active_strategies: List[str]
    total_positions: int
    total_pnl: float
    last_update: datetime


class PositionResponse(BaseModel):
    code: str
    name: str
    side: str
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    pnl_pct: float
    entry_time: datetime
    strategy: str


# In-memory state (replaced by real orchestrator in production)
_trading_state = {
    "is_running": False,
    "positions": [],
}


@router.get("/status", response_model=TradingStatus)
async def get_trading_status():
    """Get current trading system status."""
    return TradingStatus(
        is_running=_trading_state["is_running"],
        market_status="closed",
        active_strategies=[],
        total_positions=len(_trading_state["positions"]),
        total_pnl=0.0,
        last_update=datetime.now(),
    )


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions():
    """Get all open positions."""
    return _trading_state["positions"]


@router.post("/start")
async def start_trading():
    """Start trading system."""
    _trading_state["is_running"] = True
    return {"status": "started"}


@router.post("/stop")
async def stop_trading():
    """Stop trading system."""
    _trading_state["is_running"] = False
    return {"status": "stopped"}
```

Update `services/dashboard/app.py` to include the router:

```python
# Add to _register_routes function
from services.dashboard.routes import trading
app.include_router(trading.router)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/dashboard/test_trading.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/dashboard/routes/ tests/unit/dashboard/test_trading.py
git commit -m "feat(dashboard): add trading status and positions endpoints"
```

---

### Tasks 3-10: Additional Dashboard Features

- Task 3: Signals API (list signals, signal history)
- Task 4: Trades API (trade history, statistics)
- Task 5: Backtest API (run backtest, get results)
- Task 6: Experiments API (MLflow integration)
- Task 7: WebSocket for real-time updates
- Task 8: Authentication middleware
- Task 9: Rate limiting
- Task 10: OpenAPI documentation

---

## Part B: Dashboard Frontend (Tasks 11-15)

### Task 11: React Project Setup

**Files:**
- Create: `dashboard-frontend/package.json`
- Create: `dashboard-frontend/src/App.tsx`
- Create: `dashboard-frontend/src/api/client.ts`

**Implementation:**

```json
// dashboard-frontend/package.json
{
  "name": "kis-unified-dashboard",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "@tanstack/react-query": "^5.0.0",
    "axios": "^1.6.0",
    "recharts": "^2.10.0",
    "tailwindcss": "^3.3.0"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

```typescript
// dashboard-frontend/src/api/client.ts
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
});

export const tradingApi = {
  getStatus: () => apiClient.get('/api/trading/status'),
  getPositions: () => apiClient.get('/api/trading/positions'),
  startTrading: () => apiClient.post('/api/trading/start'),
  stopTrading: () => apiClient.post('/api/trading/stop'),
};
```

---

### Tasks 12-15: Frontend Components

- Task 12: Dashboard overview page
- Task 13: Positions table component
- Task 14: Signals page with filters
- Task 15: Trade history with charts

---

## Part C: Additional Strategies (Tasks 16-25)

### Task 16: Strategy Base Enhancement

**Files:**
- Modify: `shared/strategy/entry/base.py`
- Create: `shared/strategy/entry/v35_optimized.py`
- Test: `tests/unit/strategy/test_v35.py`

**Step 1: Write the failing test**

```python
# tests/unit/strategy/test_v35.py
"""Test V35 optimized strategy."""
import pytest
import pandas as pd
import numpy as np


def test_v35_entry_signal():
    """Test V35 entry signal generation."""
    from shared.strategy.entry.v35_optimized import V35OptimizedEntry
    from shared.strategy.entry.base import EntryContext

    config = {
        "bb_period": 20,
        "bb_std": 2.0,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
    }

    strategy = V35OptimizedEntry(config)

    # Create test data with oversold conditions
    context = EntryContext(
        market_data={
            "close": 58000,
            "bb_lower": 58500,  # Price below BB lower
            "rsi": 25,         # Oversold
            "macd_hist": 0.5,  # Positive momentum
        },
        indicators={},
        current_positions=[],
        timestamp=pd.Timestamp.now(),
    )

    signal = strategy.generate(context)

    assert signal is not None
    assert signal.side == "BUY"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/strategy/test_v35.py -v`
Expected: FAIL with "cannot import name 'V35OptimizedEntry'"

**Step 3: Write minimal implementation**

```python
# shared/strategy/entry/v35_optimized.py
"""V35 Optimized Entry Strategy.

Multi-indicator entry strategy combining:
- Bollinger Bands (price below lower band)
- RSI (oversold condition)
- MACD (momentum confirmation)
"""
import logging
from typing import Optional

from .base import EntrySignalGenerator, EntryContext
from shared.models.signal import Signal, SignalType

logger = logging.getLogger(__name__)


class V35OptimizedEntry(EntrySignalGenerator):
    """V35 optimized entry strategy.

    Entry conditions (all must be true):
    1. Price below BB lower band
    2. RSI < oversold threshold
    3. MACD histogram positive (momentum turning)
    """

    def __init__(self, config: dict):
        self.bb_period = config.get("bb_period", 20)
        self.bb_std = config.get("bb_std", 2.0)
        self.rsi_period = config.get("rsi_period", 14)
        self.rsi_oversold = config.get("rsi_oversold", 30)
        self.macd_fast = config.get("macd_fast", 12)
        self.macd_slow = config.get("macd_slow", 26)
        self.macd_signal = config.get("macd_signal", 9)

    @property
    def required_indicators(self) -> list:
        return ["bb_lower", "bb_upper", "rsi", "macd", "macd_signal", "macd_hist"]

    def _validate_config(self):
        assert self.bb_period > 0
        assert self.rsi_period > 0
        assert 0 < self.rsi_oversold < 50

    def generate(self, context: EntryContext) -> Optional[Signal]:
        """Generate entry signal based on V35 conditions."""
        data = context.market_data

        close = data.get("close", 0)
        bb_lower = data.get("bb_lower", 0)
        rsi = data.get("rsi", 50)
        macd_hist = data.get("macd_hist", 0)

        # Check all conditions
        price_below_bb = close < bb_lower
        rsi_oversold = rsi < self.rsi_oversold
        macd_positive = macd_hist > 0

        if price_below_bb and rsi_oversold and macd_positive:
            logger.info(
                f"V35 BUY signal: close={close}, bb_lower={bb_lower}, "
                f"rsi={rsi}, macd_hist={macd_hist}"
            )

            return Signal(
                signal_type=SignalType.ENTRY,
                side="BUY",
                symbol=data.get("symbol", ""),
                price=close,
                timestamp=context.timestamp,
                strategy="v35_optimized",
                confidence=self._calculate_confidence(rsi, macd_hist),
            )

        return None

    def _calculate_confidence(self, rsi: float, macd_hist: float) -> float:
        """Calculate signal confidence 0-1."""
        rsi_score = max(0, (self.rsi_oversold - rsi) / self.rsi_oversold)
        macd_score = min(1, macd_hist / 0.5) if macd_hist > 0 else 0
        return (rsi_score + macd_score) / 2
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/strategy/test_v35.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/strategy/entry/v35_optimized.py tests/unit/strategy/test_v35.py
git commit -m "feat(strategy): add V35 optimized entry strategy"
```

---

### Tasks 17-25: Additional Strategy Implementations

- Task 17: StochRSI Trend Entry
- Task 18: Stochastic Trend Entry
- Task 19: Disparity Stochastic Entry
- Task 20: Gap Pullback Entry
- Task 21: Volatility Breakout Entry
- Task 22: Mean Reversion Exit (from kospi_mini_sts)
- Task 23: Breakout Strategy (from kospi_mini_sts)
- Task 24: Strategy Registry updates
- Task 25: Integration tests

---

## Dependencies

```
# Backend
fastapi>=0.104.0
uvicorn>=0.24.0
httpx>=0.25.0

# Frontend (npm)
react@18.2.0
@tanstack/react-query@5.0.0
recharts@2.10.0
tailwindcss@3.3.0
```

---

## Docker Compose Addition

```yaml
# docker-compose.yml (addition)
services:
  dashboard-api:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  dashboard-frontend:
    build:
      context: ./dashboard-frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000
```

---

**Created:** 2026-01-20
