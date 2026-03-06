#!/bin/bash
# Backtest Data Setup Script
# Automates verification and collection of 6+ months of stock minute-bar data

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "========================================================================"
echo "Backtest Data Setup for Stock Strategy Validation"
echo "========================================================================"
echo ""

# Function to print colored output
print_info() {
    echo -e "\033[0;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[0;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

print_warning() {
    echo -e "\033[0;33m[WARNING]\033[0m $1"
}

# Check prerequisites
print_info "Checking prerequisites..."

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    print_error ".env file not found!"
    print_info "Copy .env.example to .env and configure:"
    print_info "  cp .env.example .env"
    exit 1
fi

# Check if KIS credentials are configured
if grep -q "your_kis_app_key" .env; then
    print_warning "KIS credentials not configured in .env"
    print_warning "Please update .env with actual KIS API credentials"
    exit 1
fi

# Check if ClickHouse is accessible
print_info "Checking ClickHouse connection..."
if ! command -v clickhouse-client &> /dev/null; then
    print_warning "clickhouse-client not found in PATH"
    print_info "Assuming ClickHouse is running in Docker..."
fi

# Check Docker services
print_info "Checking Docker services..."
if command -v docker &> /dev/null; then
    if docker ps | grep -q clickhouse; then
        print_success "ClickHouse container is running"
    else
        print_warning "ClickHouse container not running"
        print_info "Starting Docker services..."
        docker-compose up -d clickhouse redis || {
            print_error "Failed to start Docker services"
            exit 1
        }
        sleep 5
    fi
else
    print_warning "Docker not available, assuming services are running locally"
fi

# Step 1: Verify existing data
print_info "========================================="
print_info "Step 1: Verifying existing data..."
print_info "========================================="
echo ""

if python3 scripts/verify_backtest_data.py; then
    print_success "Data verification PASSED!"
    print_success "You have sufficient data for backtesting (6+ months, 10+ symbols)"
    echo ""
    echo "========================================================================"
    echo "✅ READY FOR BACKTEST VALIDATION"
    echo "========================================================================"
    echo ""
    echo "Next steps:"
    echo "  1. Run backtest for trend_pullback:"
    echo "     python -m cli.main backtest run --strategy trend_pullback --asset stock"
    echo ""
    echo "  2. Run backtest for momentum_breakout:"
    echo "     python -m cli.main backtest run --strategy momentum_breakout --asset stock"
    echo ""
    exit 0
else
    print_warning "Data verification FAILED or insufficient data"
    print_info "Proceeding to data collection..."
    echo ""
fi

# Step 2: Collect data
print_info "========================================="
print_info "Step 2: Collecting historical data..."
print_info "========================================="
echo ""

# Ask user for confirmation
read -p "Collect 6 months (180 days) of minute-bar data? This may take 30-60 minutes. (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Data collection cancelled by user"
    echo ""
    echo "To collect data later, run:"
    echo "  python -m cli.main stock-backfill run --days 180"
    exit 0
fi

# Run data collection
print_info "Starting data collection for 180 days..."
print_info "This will collect minute bars for 30 stocks from STOCK_UNIVERSE"
echo ""

if python -m cli.main stock-backfill run --days 180; then
    print_success "Data collection completed successfully!"
else
    print_error "Data collection failed"
    print_info "Check logs for details. Common issues:"
    print_info "  - KIS API credentials not configured"
    print_info "  - Rate limit exceeded (wait 1 hour and retry)"
    print_info "  - Network connectivity issues"
    echo ""
    echo "To retry:"
    echo "  python -m cli.main stock-backfill run --days 180"
    exit 1
fi

# Step 3: Verify collected data
print_info "========================================="
print_info "Step 3: Verifying collected data..."
print_info "========================================="
echo ""

if python3 scripts/verify_backtest_data.py; then
    print_success "Data verification PASSED!"
    echo ""
    echo "========================================================================"
    echo "✅ BACKTEST DATA PREPARATION COMPLETE"
    echo "========================================================================"
    echo ""
    echo "Summary:"
    echo "  - 6+ months of minute-bar data collected"
    echo "  - 10+ symbols available for backtesting"
    echo "  - Data stored in ClickHouse market.bars_1m table"
    echo ""
    echo "Next steps:"
    echo "  1. Run backtest for trend_pullback:"
    echo "     python -m cli.main backtest run --strategy trend_pullback --asset stock"
    echo ""
    echo "  2. Run backtest for momentum_breakout:"
    echo "     python -m cli.main backtest run --strategy momentum_breakout --asset stock"
    echo ""
else
    print_error "Data verification failed after collection"
    print_info "Please check:"
    print_info "  1. ClickHouse is running and accessible"
    print_info "  2. Data was successfully written to market.bars_1m table"
    print_info "  3. No errors in collection logs"
    exit 1
fi
