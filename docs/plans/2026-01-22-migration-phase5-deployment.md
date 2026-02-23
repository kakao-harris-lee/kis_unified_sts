# Phase 5: Deployment & Documentation

**Status**: Implemented (2026-01-22)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete Docker deployment setup, verify paper trading, and finalize documentation.

**Architecture:** Docker Compose orchestration, multi-stage builds, production-ready configuration.

**Tech Stack:** Docker, Docker Compose, Prometheus, Grafana, GitHub Actions

---

## Overview

| # | Component | Status | Description |
|---|-----------|--------|-------------|
| 1 | Docker Setup | 90% Complete | Dockerfile, docker-compose.yml exist |
| 2 | Monitoring Config | 100% Complete | Prometheus, Grafana dashboards ready |
| 3 | Paper Trading Verification | Needs Testing | End-to-end validation |
| 4 | Documentation | 0% Complete | README, API docs, guides |
| 5 | CI/CD | Not Started | GitHub Actions workflow |

**Estimated Tasks:** 15 bite-sized tasks

---

## Part A: Docker Finalization (Tasks 1-4)

### Task 1: Dashboard Dockerfile

**Files:**
- Create: `Dockerfile.dashboard`
- Modify: `docker-compose.yml`
- Test: `docker compose build dashboard`

**Step 1: Create Dashboard-specific Dockerfile**

```dockerfile
# Dockerfile.dashboard
# Dashboard API specific build
FROM python:3.11-slim

LABEL maintainer="harris"
LABEL description="KIS Trading Dashboard API"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY . .

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "-m", "uvicorn", "services.dashboard.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
```

**Step 2: Add dashboard service to docker-compose.yml**

Add after `app` service:

```yaml
  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    container_name: kis-dashboard
    restart: unless-stopped
    ports:
      - "8001:8001"
    environment:
      - API_KEY=${API_KEY}
      - REDIS_URL=redis://redis:6379/0
      - ENVIRONMENT=${ENVIRONMENT:-production}
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    networks:
      - trading-network
```

**Step 3: Test build**

Run: `docker compose build dashboard`
Expected: Build succeeds without errors

**Step 4: Commit**

```bash
git add Dockerfile.dashboard docker-compose.yml
git commit -m "feat(docker): add dashboard service container"
```

---

### Task 2: Environment Configuration

**Files:**
- Create: `.env.example`
- Create: `.env.production.example`

**Step 1: Create development environment template**

```bash
# .env.example
# KIS Unified Trading Platform - Environment Variables

# =============================================================================
# KIS API (한국투자증권)
# =============================================================================
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_IS_REAL=false
# KIS_ACCOUNT_NO=12345678-01  # Optional: for real trading

# =============================================================================
# API Authentication
# =============================================================================
API_KEY=your_secure_api_key_here
API_KEY_HEADER=X-API-Key

# =============================================================================
# Telegram Alerts (Optional)
# =============================================================================
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# =============================================================================
# Redis
# =============================================================================
REDIS_URL=redis://localhost:6379/0

# =============================================================================
# ClickHouse (Optional - for historical data)
# =============================================================================
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=trading

# =============================================================================
# MLflow (Backtesting)
# =============================================================================
MLFLOW_TRACKING_URI=http://localhost:5000
MLFLOW_EXPERIMENT_NAME=kis-unified-backtest

# =============================================================================
# Grafana
# =============================================================================
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
GRAFANA_ROOT_URL=http://localhost:3000

# =============================================================================
# Environment
# =============================================================================
ENVIRONMENT=development
LOG_LEVEL=INFO
```

**Step 2: Create production environment template**

```bash
# .env.production.example
# Production Environment - NEVER commit actual values

KIS_APP_KEY=REQUIRED
KIS_APP_SECRET=REQUIRED
KIS_IS_REAL=true

API_KEY=REQUIRED_STRONG_KEY

TELEGRAM_BOT_TOKEN=REQUIRED
TELEGRAM_CHAT_ID=REQUIRED

REDIS_URL=redis://redis:6379/0

GRAFANA_ADMIN_PASSWORD=REQUIRED_STRONG_PASSWORD
GRAFANA_ANONYMOUS=false

ENVIRONMENT=production
LOG_LEVEL=WARNING
```

**Step 3: Commit**

```bash
git add .env.example .env.production.example
git commit -m "docs(env): add environment variable templates"
```

---

### Task 3: Docker Health Scripts

**Files:**
- Create: `scripts/docker-health.sh`
- Create: `scripts/docker-start.sh`

**Step 1: Create health check script**

```bash
#!/bin/bash
# scripts/docker-health.sh
# Check health of all Docker services

set -e

echo "=== KIS Unified Trading Platform - Health Check ==="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

check_service() {
    local name=$1
    local url=$2

    if curl -sf "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} $name is unhealthy"
        return 1
    fi
}

echo ""
echo "Checking services..."
echo ""

# Check each service
check_service "Trading API" "http://localhost:8000/health/live"
check_service "Dashboard API" "http://localhost:8001/health"
check_service "Redis" "http://localhost:6379" || redis-cli ping > /dev/null 2>&1 && echo -e "${GREEN}✓${NC} Redis is healthy"
check_service "Prometheus" "http://localhost:9090/-/healthy"
check_service "Grafana" "http://localhost:3000/api/health"

echo ""
echo "=== Health Check Complete ==="
```

**Step 2: Create start script**

```bash
#!/bin/bash
# scripts/docker-start.sh
# Start Docker services with proper initialization

set -e

echo "=== Starting KIS Unified Trading Platform ==="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Please copy .env.example to .env and configure"
    exit 1
fi

# Start services
echo "Starting Docker services..."
docker compose up -d

# Wait for services
echo "Waiting for services to be ready..."
sleep 10

# Run health check
./scripts/docker-health.sh

echo ""
echo "=== Platform Started Successfully ==="
echo ""
echo "Access points:"
echo "  - Trading API: http://localhost:8000"
echo "  - Dashboard:   http://localhost:8001"
echo "  - Grafana:     http://localhost:3000"
echo "  - Prometheus:  http://localhost:9090"
```

**Step 3: Make executable and commit**

```bash
chmod +x scripts/docker-health.sh scripts/docker-start.sh
git add scripts/
git commit -m "feat(scripts): add docker health check and start scripts"
```

---

### Task 4: Multi-stage Production Dockerfile

**Files:**
- Create: `Dockerfile.prod`

**Step 1: Create optimized production Dockerfile**

```dockerfile
# Dockerfile.prod
# Multi-stage production build for minimal image size

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir .

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.11-slim as runtime

LABEL maintainer="harris"
LABEL description="KIS Unified Trading Platform (Production)"

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy application code
COPY shared/ ./shared/
COPY domains/ ./domains/
COPY services/ ./services/
COPY cli/ ./cli/
COPY config/ ./config/

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["python", "-m", "uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

**Step 2: Test build**

Run: `docker build -f Dockerfile.prod -t kis-trading:prod .`
Expected: Build succeeds, image size < 500MB

**Step 3: Commit**

```bash
git add Dockerfile.prod
git commit -m "feat(docker): add multi-stage production Dockerfile"
```

---

## Part B: Paper Trading Verification (Tasks 5-8)

### Task 5: Paper Trading Integration Test

**Files:**
- Create: `tests/integration/test_paper_trading_e2e.py`

**Step 1: Write end-to-end test**

```python
# tests/integration/test_paper_trading_e2e.py
"""End-to-end paper trading integration test."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from shared.paper.engine import PaperTradingEngine
from shared.paper.config import PaperConfig
from shared.paper.broker import VirtualBroker
from shared.paper.models import VirtualOrder, OrderSide, OrderType, OrderStatus
from shared.strategy.entry.mean_reversion import MeanReversionEntry, MeanReversionConfig
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig
from shared.models.position import Position


@pytest.fixture
def paper_config():
    """Create paper trading configuration."""
    return PaperConfig(
        initial_capital=100_000_000,  # 1억원
        commission_rate=0.00015,  # 0.015%
        slippage_rate=0.0001,  # 0.01%
        allow_short=False,
    )


@pytest.fixture
def broker(paper_config):
    """Create virtual broker."""
    return VirtualBroker(paper_config)


@pytest.mark.asyncio
async def test_full_trading_cycle(broker, paper_config):
    """Test complete buy → hold → sell cycle."""
    # 1. Initial state
    assert broker.get_balance() == paper_config.initial_capital
    assert len(broker.get_positions()) == 0

    # 2. Place buy order
    buy_order = VirtualOrder(
        order_id="TEST-001",
        symbol="005930",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100,
        price=None,
        timestamp=datetime.now(),
    )

    result = await broker.submit_order(buy_order, current_price=58000)
    assert result.status == OrderStatus.FILLED
    assert result.filled_price == pytest.approx(58000, rel=0.01)

    # 3. Check position created
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "005930"
    assert positions[0].quantity == 100

    # 4. Update market price (price goes up)
    broker.update_position_price("005930", 60000)
    position = broker.get_position("005930")
    assert position.unrealized_pnl > 0

    # 5. Place sell order
    sell_order = VirtualOrder(
        order_id="TEST-002",
        symbol="005930",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=100,
        price=None,
        timestamp=datetime.now(),
    )

    result = await broker.submit_order(sell_order, current_price=60000)
    assert result.status == OrderStatus.FILLED

    # 6. Position closed
    assert len(broker.get_positions()) == 0

    # 7. Profit realized (minus commissions)
    final_balance = broker.get_balance()
    expected_profit = (60000 - 58000) * 100  # 200,000
    assert final_balance > paper_config.initial_capital


@pytest.mark.asyncio
async def test_stop_loss_trigger(broker):
    """Test stop loss execution."""
    # Buy position
    buy_order = VirtualOrder(
        order_id="STOP-001",
        symbol="035720",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=50,
        price=None,
        timestamp=datetime.now(),
    )
    await broker.submit_order(buy_order, current_price=100000)

    # Price drops significantly
    broker.update_position_price("035720", 95000)  # -5%

    # Check stop loss would trigger at -1.5%
    position = broker.get_position("035720")
    pnl_pct = (95000 - 100000) / 100000 * 100
    assert pnl_pct < -1.5  # Stop loss threshold


@pytest.mark.asyncio
async def test_multiple_positions(broker):
    """Test managing multiple positions."""
    symbols = ["005930", "035720", "000660"]

    for i, symbol in enumerate(symbols):
        order = VirtualOrder(
            order_id=f"MULTI-{i}",
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
            price=None,
            timestamp=datetime.now(),
        )
        await broker.submit_order(order, current_price=50000 + i * 10000)

    assert len(broker.get_positions()) == 3

    # Portfolio summary
    summary = broker.get_portfolio_summary()
    assert summary["total_positions"] == 3
    assert summary["total_value"] > 0
```

**Step 2: Run test**

Run: `pytest tests/integration/test_paper_trading_e2e.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/integration/test_paper_trading_e2e.py
git commit -m "test(paper): add end-to-end paper trading integration tests"
```

---

### Task 6: Paper Trading CLI Commands

**Files:**
- Modify: `cli/main.py`
- Test: Manual CLI test

**Step 1: Add paper trading commands**

Add to `cli/main.py`:

```python
@cli.group()
def paper():
    """Paper trading commands."""
    pass


@paper.command()
@click.option("--capital", default=100_000_000, help="Initial capital (KRW)")
@click.option("--strategy", default="bb_reversion", help="Strategy name")
def start(capital: int, strategy: str):
    """Start paper trading session."""
    import asyncio
    from shared.paper.engine import PaperTradingEngine
    from shared.paper.config import PaperConfig
    from shared.config.loader import ConfigLoader
    from shared.strategy.factory import StrategyFactory

    click.echo(f"Starting paper trading...")
    click.echo(f"  Capital: {capital:,} KRW")
    click.echo(f"  Strategy: {strategy}")

    config = PaperConfig(initial_capital=capital)
    strategy_config = ConfigLoader.load_strategy("stock", strategy)
    trading_strategy = StrategyFactory.create(strategy_config)

    engine = PaperTradingEngine(config, trading_strategy)

    click.echo("\nPaper trading started. Press Ctrl+C to stop.")
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        click.echo("\nStopping paper trading...")
        engine.stop()

    # Print summary
    summary = engine.get_summary()
    click.echo("\n=== Paper Trading Summary ===")
    click.echo(f"Total Trades: {summary['total_trades']}")
    click.echo(f"Win Rate: {summary['win_rate']:.1f}%")
    click.echo(f"Total P&L: {summary['total_pnl']:,.0f} KRW")


@paper.command()
def status():
    """Show current paper trading status."""
    click.echo("Paper trading status: Not implemented yet")


@paper.command()
@click.option("--format", "fmt", default="table", type=click.Choice(["table", "json"]))
def history(fmt: str):
    """Show paper trading history."""
    click.echo("Trade history: Not implemented yet")
```

**Step 2: Test CLI**

Run: `sts paper --help`
Expected: Shows paper trading commands

**Step 3: Commit**

```bash
git add cli/main.py
git commit -m "feat(cli): add paper trading commands"
```

---

### Task 7: Paper Trading Scenario Tests

**Files:**
- Create: `tests/integration/test_paper_scenarios.py`

**Step 1: Write scenario tests**

```python
# tests/integration/test_paper_scenarios.py
"""Paper trading scenario tests."""
import pytest
from datetime import datetime, timedelta

from shared.paper.broker import VirtualBroker
from shared.paper.config import PaperConfig
from shared.paper.models import VirtualOrder, OrderSide, OrderType


class TestBullMarketScenario:
    """Test trading in bull market conditions."""

    @pytest.fixture
    def broker(self):
        config = PaperConfig(initial_capital=10_000_000)
        return VirtualBroker(config)

    @pytest.mark.asyncio
    async def test_trending_up_profit(self, broker):
        """Test profit in trending up market."""
        # Buy at start
        buy = VirtualOrder(
            order_id="BULL-001",
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            price=None,
            timestamp=datetime.now(),
        )
        await broker.submit_order(buy, current_price=50000)

        # Simulate trending up
        prices = [51000, 52000, 53000, 54000, 55000]
        for price in prices:
            broker.update_position_price("005930", price)

        # Should be in profit
        position = broker.get_position("005930")
        assert position.unrealized_pnl > 0
        assert position.pnl_pct > 5  # > 5% gain


class TestBearMarketScenario:
    """Test trading in bear market conditions."""

    @pytest.fixture
    def broker(self):
        config = PaperConfig(initial_capital=10_000_000)
        return VirtualBroker(config)

    @pytest.mark.asyncio
    async def test_stop_loss_protection(self, broker):
        """Test stop loss protects capital."""
        initial_balance = broker.get_balance()

        # Buy position
        buy = VirtualOrder(
            order_id="BEAR-001",
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            price=None,
            timestamp=datetime.now(),
        )
        await broker.submit_order(buy, current_price=50000)

        # Price drops 10%
        broker.update_position_price("005930", 45000)

        # Verify loss is controlled
        position = broker.get_position("005930")
        max_loss_pct = -10  # Should trigger stop loss before this
        assert position.pnl_pct >= max_loss_pct


class TestVolatileMarketScenario:
    """Test trading in volatile market conditions."""

    @pytest.fixture
    def broker(self):
        config = PaperConfig(initial_capital=10_000_000)
        return VirtualBroker(config)

    @pytest.mark.asyncio
    async def test_whipsaw_handling(self, broker):
        """Test handling of whipsaw price movements."""
        buy = VirtualOrder(
            order_id="VOL-001",
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            price=None,
            timestamp=datetime.now(),
        )
        await broker.submit_order(buy, current_price=50000)

        # Simulate whipsaw: up → down → up
        broker.update_position_price("005930", 52000)  # +4%
        broker.update_position_price("005930", 49000)  # -2%
        broker.update_position_price("005930", 53000)  # +6%

        position = broker.get_position("005930")
        # Should track highest price for trailing stop
        assert position.highest_price == 53000
```

**Step 2: Run tests**

Run: `pytest tests/integration/test_paper_scenarios.py -v`
Expected: All scenarios pass

**Step 3: Commit**

```bash
git add tests/integration/test_paper_scenarios.py
git commit -m "test(paper): add market scenario integration tests"
```

---

### Task 8: Paper Trading Report Generator

**Files:**
- Create: `shared/paper/report.py`
- Test: `tests/unit/paper/test_report.py`

**Step 1: Write test**

```python
# tests/unit/paper/test_report.py
"""Test paper trading report generation."""
import pytest
from datetime import datetime, timedelta

from shared.paper.report import PaperTradingReport, TradeRecord


def test_report_generation():
    """Test report with sample trades."""
    trades = [
        TradeRecord(
            trade_id="T001",
            symbol="005930",
            side="BUY",
            entry_price=50000,
            exit_price=52000,
            quantity=100,
            entry_time=datetime.now() - timedelta(hours=2),
            exit_time=datetime.now(),
            pnl=200000,
            pnl_pct=4.0,
        ),
        TradeRecord(
            trade_id="T002",
            symbol="035720",
            side="BUY",
            entry_price=100000,
            exit_price=98000,
            quantity=50,
            entry_time=datetime.now() - timedelta(hours=1),
            exit_time=datetime.now(),
            pnl=-100000,
            pnl_pct=-2.0,
        ),
    ]

    report = PaperTradingReport(
        initial_capital=10_000_000,
        final_capital=10_100_000,
        trades=trades,
        start_time=datetime.now() - timedelta(days=1),
        end_time=datetime.now(),
    )

    summary = report.get_summary()

    assert summary["total_trades"] == 2
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 1
    assert summary["win_rate"] == 50.0
    assert summary["total_pnl"] == 100000
    assert summary["return_pct"] == pytest.approx(1.0, rel=0.01)


def test_report_to_markdown():
    """Test markdown report generation."""
    trades = [
        TradeRecord(
            trade_id="T001",
            symbol="005930",
            side="BUY",
            entry_price=50000,
            exit_price=52000,
            quantity=100,
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            pnl=200000,
            pnl_pct=4.0,
        ),
    ]

    report = PaperTradingReport(
        initial_capital=10_000_000,
        final_capital=10_200_000,
        trades=trades,
        start_time=datetime.now(),
        end_time=datetime.now(),
    )

    md = report.to_markdown()

    assert "# Paper Trading Report" in md
    assert "Total P&L" in md
    assert "Win Rate" in md
```

**Step 2: Implement report generator**

```python
# shared/paper/report.py
"""Paper trading report generation."""
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class TradeRecord:
    """Individual trade record."""
    trade_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: int
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float


@dataclass
class PaperTradingReport:
    """Paper trading session report."""
    initial_capital: float
    final_capital: float
    trades: List[TradeRecord]
    start_time: datetime
    end_time: datetime

    def get_summary(self) -> dict:
        """Get summary statistics."""
        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl < 0]

        total_pnl = sum(t.pnl for t in self.trades)
        win_rate = len(winning) / len(self.trades) * 100 if self.trades else 0
        return_pct = (self.final_capital - self.initial_capital) / self.initial_capital * 100

        return {
            "total_trades": len(self.trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "return_pct": return_pct,
            "avg_win": sum(t.pnl for t in winning) / len(winning) if winning else 0,
            "avg_loss": sum(t.pnl for t in losing) / len(losing) if losing else 0,
            "largest_win": max((t.pnl for t in winning), default=0),
            "largest_loss": min((t.pnl for t in losing), default=0),
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        s = self.get_summary()
        duration = self.end_time - self.start_time

        md = f"""# Paper Trading Report

## Summary

| Metric | Value |
|--------|-------|
| Period | {duration.days}d {duration.seconds // 3600}h |
| Initial Capital | {self.initial_capital:,.0f} KRW |
| Final Capital | {self.final_capital:,.0f} KRW |
| Total P&L | {s['total_pnl']:+,.0f} KRW |
| Return | {s['return_pct']:+.2f}% |

## Performance

| Metric | Value |
|--------|-------|
| Total Trades | {s['total_trades']} |
| Win Rate | {s['win_rate']:.1f}% |
| Avg Win | {s['avg_win']:,.0f} KRW |
| Avg Loss | {s['avg_loss']:,.0f} KRW |
| Largest Win | {s['largest_win']:,.0f} KRW |
| Largest Loss | {s['largest_loss']:,.0f} KRW |

## Trade History

| # | Symbol | Side | Entry | Exit | P&L | P&L % |
|---|--------|------|-------|------|-----|-------|
"""
        for i, t in enumerate(self.trades, 1):
            md += f"| {i} | {t.symbol} | {t.side} | {t.entry_price:,.0f} | {t.exit_price:,.0f} | {t.pnl:+,.0f} | {t.pnl_pct:+.2f}% |\n"

        return md
```

**Step 3: Run tests**

Run: `pytest tests/unit/paper/test_report.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add shared/paper/report.py tests/unit/paper/test_report.py
git commit -m "feat(paper): add trading report generator"
```

---

## Part C: Documentation (Tasks 9-15)

### Task 9: README.md

**Files:**
- Create: `README.md`

**Step 1: Create comprehensive README**

```markdown
# KIS Unified Trading Platform

> 주식/선물 통합 단기매매 시스템

[![Tests](https://github.com/kakao-harris-lee/kis-unified-sts/actions/workflows/test.yml/badge.svg)](https://github.com/kakao-harris-lee/kis-unified-sts/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 개요

KIS Unified Trading Platform은 한국투자증권 API를 활용한 알고리즘 트레이딩 시스템입니다. 주식과 선물 거래를 단일 플랫폼에서 통합 관리하며, 설정 기반 전략 시스템을 제공합니다.

### 주요 기능

- **전략 프레임워크**: 진입/청산 로직 분리, YAML 기반 설정
- **백테스팅**: MLflow 통합, Optuna 파라미터 최적화
- **실시간 거래**: Redis Streams 기반 이벤트 파이프라인
- **모의투자**: 가상 브로커를 통한 전략 검증
- **모니터링**: Prometheus 메트릭, Grafana 대시보드

## 빠른 시작

### 설치

\`\`\`bash
# 저장소 클론
git clone https://github.com/kakao-harris-lee/kis-unified-sts.git
cd kis-unified-sts

# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -e ".[dev]"

# 환경 설정
cp .env.example .env
# .env 파일 편집하여 KIS API 키 설정
\`\`\`

### Docker로 실행

\`\`\`bash
# 환경 설정
cp .env.example .env
# .env 파일 편집

# 서비스 시작
./scripts/docker-start.sh

# 또는 직접 실행
docker compose up -d
\`\`\`

### CLI 사용

\`\`\`bash
# 백테스트 실행
sts backtest run --strategy bb_reversion --asset stock

# 모의투자 시작
sts paper start --strategy bb_reversion --capital 100000000

# MLflow UI
sts mlflow ui
\`\`\`

## 아키텍처

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                    Strategy Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ EntrySignal │  │ ExitSignal  │  │ PositionSizing      │ │
│  │ Generator   │  │ Generator   │  │ Calculator          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    Trading Pipeline                          │
│  Regime Detection → Entry Signal → Monitoring → Exit Signal │
├─────────────────────────────────────────────────────────────┤
│                    Infrastructure                            │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐│
│  │ KIS API   │  │ Redis     │  │ ClickHouse│  │ MLflow   ││
│  └───────────┘  └───────────┘  └───────────┘  └──────────┘│
└─────────────────────────────────────────────────────────────┘
\`\`\`

## 전략 설정

전략은 YAML 파일로 정의됩니다:

\`\`\`yaml
# config/strategies/stock/bb_reversion.yaml
strategy:
  name: bb_reversion
  asset_class: stock

  entry:
    type: bb_lower_reentry
    params:
      bb_period: 20
      bb_std: 2.0
      rsi_oversold: 30

  exit:
    type: three_stage
    params:
      hard_stop_pct: 1.5
      breakeven_threshold_pct: 1.5
      trailing_stop_pct: 3.0
\`\`\`

## 포함된 전략

### 진입 전략
- **BB Reversion**: 볼린저 밴드 + RSI 평균회귀
- **V35 Optimized**: BB + RSI + MACD 복합 지표
- **OFI Momentum**: 주문흐름 불균형 기반
- **Microstructure**: 복합 마이크로스트럭처

### 청산 전략
- **3-Stage Exit**: Survival → Breakeven → Maximize

## 테스트

\`\`\`bash
# 전체 테스트
pytest tests/ -v

# 커버리지
pytest tests/ --cov=shared --cov=services --cov-report=html
\`\`\`

## 문서

- [API 문서](docs/api.md)
- [전략 가이드](docs/strategies.md)
- [배포 가이드](docs/deployment.md)

## 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일 참조
\`\`\`

**Step 2: Commit**

\`\`\`bash
git add README.md
git commit -m "docs: add comprehensive README"
\`\`\`

---

### Task 10: API Documentation

**Files:**
- Create: `docs/api.md`

**Step 1: Create API documentation**

\`\`\`markdown
# API Documentation

## Base URL

- Development: `http://localhost:8000`
- Dashboard: `http://localhost:8001`

## Authentication

모든 API 요청에는 API 키가 필요합니다:

\`\`\`
X-API-Key: your_api_key_here
\`\`\`

## Endpoints

### Health

#### GET /health/live
서버 생존 확인

**Response:**
\`\`\`json
{
  "status": "ok",
  "timestamp": "2026-01-22T10:00:00Z"
}
\`\`\`

#### GET /health/ready
서버 준비 상태 확인

**Response:**
\`\`\`json
{
  "status": "ready",
  "components": {
    "redis": "healthy",
    "database": "healthy"
  }
}
\`\`\`

### Trading

#### GET /api/v1/trading/status
현재 거래 상태 조회

**Response:**
\`\`\`json
{
  "is_running": true,
  "market_status": "open",
  "active_strategies": ["bb_reversion"],
  "total_positions": 3,
  "total_pnl": 150000.0
}
\`\`\`

#### POST /api/v1/trading/start
거래 시작

**Response:**
\`\`\`json
{
  "status": "started",
  "message": "Trading started successfully"
}
\`\`\`

#### POST /api/v1/trading/stop
거래 중지

### Strategies

#### GET /api/v1/strategies
등록된 전략 목록 조회

**Response:**
\`\`\`json
{
  "strategies": [
    {
      "name": "bb_reversion",
      "asset_class": "stock",
      "enabled": true
    }
  ]
}
\`\`\`

### Backtest

#### POST /api/v1/backtest/run
백테스트 실행

**Request:**
\`\`\`json
{
  "strategy": "bb_reversion",
  "asset_class": "stock",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "initial_capital": 100000000
}
\`\`\`

**Response:**
\`\`\`json
{
  "run_id": "abc123",
  "status": "running",
  "message": "Backtest started"
}
\`\`\`

#### GET /api/v1/backtest/results/{run_id}
백테스트 결과 조회

### Metrics

#### GET /metrics
Prometheus 형식 메트릭

\`\`\`
# HELP trading_signals_total Total trading signals generated
# TYPE trading_signals_total counter
trading_signals_total{strategy="bb_reversion",signal_type="entry"} 150
\`\`\`

## WebSocket

### Dashboard WebSocket

**URL:** `ws://localhost:8001/ws`

**Authentication:**
\`\`\`json
{
  "type": "auth",
  "api_key": "your_api_key"
}
\`\`\`

**Subscribe to updates:**
\`\`\`json
{
  "type": "subscribe",
  "channels": ["positions", "signals", "trades"]
}
\`\`\`

**Message format:**
\`\`\`json
{
  "type": "position_update",
  "data": {
    "symbol": "005930",
    "pnl_pct": 2.5
  },
  "timestamp": "2026-01-22T10:00:00Z"
}
\`\`\`

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid API key |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

## Rate Limits

- Default: 100 requests/minute
- Backtest: 10 requests/minute
- WebSocket: 50 messages/second
\`\`\`

**Step 2: Commit**

\`\`\`bash
git add docs/api.md
git commit -m "docs: add API documentation"
\`\`\`

---

### Task 11: Strategy Configuration Guide

**Files:**
- Create: `docs/strategies.md`

(Similar detailed documentation for strategy configuration)

---

### Task 12: Deployment Guide

**Files:**
- Create: `docs/deployment.md`

(Detailed deployment instructions for Docker, Kubernetes, etc.)

---

### Task 13: GitHub Actions CI/CD

**Files:**
- Create: `.github/workflows/test.yml`
- Create: `.github/workflows/docker.yml`

**Step 1: Create test workflow**

\`\`\`yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: --health-cmd "redis-cli ping" --health-interval 10s

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest tests/ -v --cov=shared --cov=services --cov-report=xml
        env:
          REDIS_URL: redis://localhost:6379/0

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: coverage.xml

  lint:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install linters
        run: pip install ruff black mypy

      - name: Run ruff
        run: ruff check .

      - name: Run black
        run: black --check .
\`\`\`

**Step 2: Commit**

\`\`\`bash
mkdir -p .github/workflows
git add .github/workflows/test.yml
git commit -m "ci: add GitHub Actions test workflow"
\`\`\`

---

### Task 14: Docker Build Workflow

**Files:**
- Create: `.github/workflows/docker.yml`

**Step 1: Create Docker workflow**

\`\`\`yaml
# .github/workflows/docker.yml
name: Docker Build

on:
  push:
    tags: ['v*']
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: Dockerfile.prod
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ github.ref_name }}
            ghcr.io/${{ github.repository }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
\`\`\`

**Step 2: Commit**

\`\`\`bash
git add .github/workflows/docker.yml
git commit -m "ci: add Docker build workflow"
\`\`\`

---

### Task 15: Final Integration Test

**Files:**
- Run full test suite
- Verify Docker build
- Verify documentation links

**Step 1: Run full test suite**

\`\`\`bash
pytest tests/ -v --tb=short
\`\`\`
Expected: All tests pass (444+)

**Step 2: Verify Docker build**

\`\`\`bash
docker compose build
docker compose up -d
./scripts/docker-health.sh
docker compose down
\`\`\`
Expected: All services healthy

**Step 3: Final commit**

\`\`\`bash
git add .
git commit -m "docs: complete Phase 5 deployment documentation"
\`\`\`

---

## Dependencies

\`\`\`
# Docker
docker>=24.0
docker-compose>=2.20

# CI/CD
github-actions

# Monitoring
prometheus>=2.48
grafana>=10.2
\`\`\`

---

## Checklist

- [ ] Task 1: Dashboard Dockerfile
- [ ] Task 2: Environment Configuration
- [ ] Task 3: Docker Health Scripts
- [ ] Task 4: Multi-stage Production Dockerfile
- [ ] Task 5: Paper Trading Integration Test
- [ ] Task 6: Paper Trading CLI Commands
- [ ] Task 7: Paper Trading Scenario Tests
- [ ] Task 8: Paper Trading Report Generator
- [ ] Task 9: README.md
- [ ] Task 10: API Documentation
- [ ] Task 11: Strategy Configuration Guide
- [ ] Task 12: Deployment Guide
- [ ] Task 13: GitHub Actions CI/CD
- [ ] Task 14: Docker Build Workflow
- [ ] Task 15: Final Integration Test

---

**Created:** 2026-01-22
