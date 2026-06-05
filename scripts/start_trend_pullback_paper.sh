#!/bin/bash
#
# Start Paper Trading for trend_pullback Strategy
#
# This script starts paper trading for the trend_pullback stock strategy
# with default parameters. The strategy uses multi-timeframe trend-following
# with pullback entries and ATR-based dynamic exits.
#
# Usage:
#   ./scripts/start_trend_pullback_paper.sh
#
# Options (modify script variables below):
#   INITIAL_CAPITAL: Starting capital in KRW (default: 10,000,000)
#   MAX_POSITIONS: Maximum concurrent positions (default: 5)
#
# Prerequisites:
#   - Python 3.11+ with dependencies installed
#   - Redis running (for position tracking)
#   - Parquet market data available under data/market (for warmup)
#   - KIS API credentials configured in .env
#   - Daily indicator scanner cron job running (08:50 KST)
#
# Strategy Details:
#   - Entry: BB lower band touch + RSI/Williams %R reversal
#   - Exit: ATR dynamic trailing stop (3.5x stop, 2.0x trail)
#   - Position Size: 1M KRW per position
#   - Max Positions: 5 concurrent
#   - Time Filters: Skip first 30min and last 15min of market
#   - Cooldown: 120 seconds between signals
#
# Monitoring:
#   - Check status: python -m cli.main paper status
#   - View history: python -m cli.main paper history
#   - Stop trading: Ctrl+C or python -m cli.main paper stop
#

set -euo pipefail

# Configuration
STRATEGY="trend_pullback"
ASSET="stock"
INITIAL_CAPITAL=10000000  # 10M KRW
MAX_POSITIONS=5

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Starting Paper Trading - trend_pullback${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not found at .venv${NC}"
    echo -e "${YELLOW}Using system Python. Consider creating venv first.${NC}"
    echo ""
fi

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

# Check Redis
if command -v redis-cli &> /dev/null; then
    if redis-cli -n 1 ping &> /dev/null; then
        echo -e "${GREEN}✓ Redis is running (DB 1)${NC}"
    else
        echo -e "${RED}✗ Redis is not responding${NC}"
        echo -e "${YELLOW}  Please start Redis: docker-compose up -d redis${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ redis-cli not found, skipping Redis check${NC}"
fi

# Check Parquet market data
MARKET_DATA_ROOT="${MARKET_DATA_PARQUET_ROOT:-data/market}"
if [ -d "$MARKET_DATA_ROOT" ]; then
    if find "$MARKET_DATA_ROOT" -name "*.parquet" -print -quit | grep -q .; then
        echo -e "${GREEN}✓ Parquet market data found at ${MARKET_DATA_ROOT}${NC}"
    else
        echo -e "${YELLOW}⚠ No Parquet files found at ${MARKET_DATA_ROOT}${NC}"
        echo -e "${YELLOW}  Run: python -m cli.main stock-backfill run --days 30${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Parquet market data directory not found: ${MARKET_DATA_ROOT}${NC}"
    echo -e "${YELLOW}  Run: python -m cli.main stock-backfill run --days 30${NC}"
fi

# Check .env file
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env file exists${NC}"
else
    echo -e "${RED}✗ .env file not found${NC}"
    echo -e "${YELLOW}  Please create .env with KIS API credentials${NC}"
    exit 1
fi

# Check strategy config
if [ -f "config/strategies/stock/trend_pullback.yaml" ]; then
    echo -e "${GREEN}✓ Strategy config found${NC}"

    # Check if enabled
    if grep -q "enabled: true" config/strategies/stock/trend_pullback.yaml; then
        echo -e "${GREEN}✓ Strategy is enabled${NC}"
    else
        echo -e "${RED}✗ Strategy is disabled in config${NC}"
        echo -e "${YELLOW}  Set 'enabled: true' in config/strategies/stock/trend_pullback.yaml${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Strategy config not found${NC}"
    exit 1
fi

# Check daily scanner (optional but recommended)
if redis-cli -n 1 EXISTS system:daily_indicators:latest &> /dev/null; then
    EXISTS=$(redis-cli -n 1 EXISTS system:daily_indicators:latest)
    if [ "$EXISTS" = "1" ]; then
        echo -e "${GREEN}✓ Daily indicators available in Redis${NC}"
    else
        echo -e "${YELLOW}⚠ Daily indicators not found in Redis${NC}"
        echo -e "${YELLOW}  Strategy may not have daily context. Run daily scanner first.${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Cannot check Redis for daily indicators${NC}"
fi

echo ""
echo -e "${BLUE}Starting paper trading...${NC}"
echo -e "  Strategy: ${GREEN}${STRATEGY}${NC}"
echo -e "  Asset: ${GREEN}${ASSET}${NC}"
echo -e "  Initial Capital: ${GREEN}${INITIAL_CAPITAL} KRW${NC}"
echo -e "  Max Positions: ${GREEN}${MAX_POSITIONS}${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop trading${NC}"
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Start paper trading
python -m cli.main paper start \
    --strategy "$STRATEGY" \
    --asset "$ASSET" \
    --capital "$INITIAL_CAPITAL" \
    --max-positions "$MAX_POSITIONS"

# Deactivate virtual environment
if [ -d ".venv" ]; then
    deactivate
fi

echo ""
echo -e "${BLUE}Paper trading stopped${NC}"
echo ""
echo -e "To view results:"
echo -e "  ${YELLOW}python -m cli.main paper history${NC}"
echo -e "  ${YELLOW}python -m cli.main paper status${NC}"
