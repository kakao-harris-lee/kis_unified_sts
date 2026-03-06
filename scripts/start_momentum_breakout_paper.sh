#!/bin/bash
#
# Start Paper Trading for momentum_breakout Strategy
#
# This script starts paper trading for the momentum_breakout stock strategy
# with default parameters. The strategy uses multi-timeframe momentum breakout
# detection with volume surge confirmation and ATR-based dynamic exits.
#
# Usage:
#   ./scripts/start_momentum_breakout_paper.sh
#
# Options (modify script variables below):
#   INITIAL_CAPITAL: Starting capital in KRW (default: 30,000,000)
#   MAX_POSITIONS: Maximum concurrent positions (default: 8)
#
# Prerequisites:
#   - Python 3.11+ with dependencies installed
#   - Redis running (for position tracking)
#   - ClickHouse running (for market data)
#   - KIS API credentials configured in .env
#   - Daily indicator scanner cron job running (08:50 KST)
#
# Strategy Details:
#   - Entry: Breakout detection + RVOL > 1.6 + accumulation score >= 40
#   - Trend Mode: Relaxed thresholds in BULL regime + EMA pullback (5/20/60)
#   - Exit: ATR dynamic trailing stop (2.0x stop, 2.0x trail activation, 1.5x trail)
#   - Position Size: 3M KRW per position
#   - Max Positions: 8 concurrent
#   - Time Filters: Skip first 10min and last 10min of market
#   - Cooldown: 120 seconds between signals
#
# Monitoring:
#   - Check status: python -m cli.main paper status
#   - View history: python -m cli.main paper history
#   - Stop trading: Ctrl+C or python -m cli.main paper stop
#

set -euo pipefail

# Configuration
STRATEGY="momentum_breakout"
ASSET="stock"
INITIAL_CAPITAL=30000000  # 30M KRW (8 positions x 3M per position)
MAX_POSITIONS=8

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Starting Paper Trading - momentum_breakout${NC}"
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

# Check ClickHouse
if command -v clickhouse-client &> /dev/null; then
    if clickhouse-client --query "SELECT 1" &> /dev/null; then
        echo -e "${GREEN}✓ ClickHouse is running${NC}"
    else
        echo -e "${RED}✗ ClickHouse is not responding${NC}"
        echo -e "${YELLOW}  Please start ClickHouse: docker-compose up -d clickhouse${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ clickhouse-client not found, skipping ClickHouse check${NC}"
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
if [ -f "config/strategies/stock/momentum_breakout.yaml" ]; then
    echo -e "${GREEN}✓ Strategy config found${NC}"

    # Check if enabled
    if grep -q "enabled: true" config/strategies/stock/momentum_breakout.yaml; then
        echo -e "${GREEN}✓ Strategy is enabled${NC}"
    else
        echo -e "${RED}✗ Strategy is disabled in config${NC}"
        echo -e "${YELLOW}  Set 'enabled: true' in config/strategies/stock/momentum_breakout.yaml${NC}"
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
