#!/usr/bin/env bash
# scripts/monitor_paper_trading.sh
# Daily monitoring script for paper trading performance (trend_pullback + momentum_breakout)
#
# Usage:
#   ./scripts/monitor_paper_trading.sh [--save] [--notify]
#
# Options:
#   --save      Save daily snapshot to monitoring log
#   --notify    Send Telegram notification with summary

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MONITORING_DIR="$PROJECT_ROOT/output/monitoring"
DAILY_LOG="$MONITORING_DIR/daily_snapshots.jsonl"
SUMMARY_LOG="$MONITORING_DIR/monitoring_summary.txt"

# Create monitoring directory if it doesn't exist
mkdir -p "$MONITORING_DIR"

# Parse arguments
SAVE_SNAPSHOT=false
SEND_NOTIFICATION=false

for arg in "$@"; do
    case $arg in
        --save)
            SAVE_SNAPSHOT=true
            shift
            ;;
        --notify)
            SEND_NOTIFICATION=true
            shift
            ;;
        *)
            ;;
    esac
done

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Paper Trading Performance Monitor${NC}"
echo -e "${BLUE}  Strategies: trend_pullback + momentum_breakout${NC}"
echo -e "${BLUE}  Date: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Function to check if CLI command is available
check_cli() {
    if ! command -v python &> /dev/null; then
        echo -e "${RED}✗ Python not found${NC}"
        return 1
    fi

    if [ ! -f "$PROJECT_ROOT/cli/main.py" ]; then
        echo -e "${RED}✗ CLI not found at cli/main.py${NC}"
        return 1
    fi

    return 0
}

# Function to get paper trading status
get_status() {
    cd "$PROJECT_ROOT"
    python -m cli.main paper status 2>&1 || echo "Error: Failed to get paper trading status"
}

# Function to get recent trade history
get_history() {
    local limit=${1:-20}
    cd "$PROJECT_ROOT"
    python -m cli.main paper history --limit "$limit" 2>&1 || echo "Error: Failed to get trade history"
}

# Function to extract key metrics from status output
extract_metrics() {
    local status_output="$1"

    # Extract total P&L (simplified parsing)
    local total_pnl=$(echo "$status_output" | grep -i "total p&l\|total profit" | head -1 | grep -oE '[-+]?[0-9,]+' | tr -d ',' || echo "0")

    # Extract position count
    local positions=$(echo "$status_output" | grep -i "positions:" | head -1 | grep -oE '[0-9]+' | head -1 || echo "0")

    # Extract running status
    local running=$(echo "$status_output" | grep -i "running:" | head -1 | grep -i "true" && echo "true" || echo "false")

    echo "$total_pnl|$positions|$running"
}

# Main monitoring logic
main() {
    # Check prerequisites
    if ! check_cli; then
        echo -e "${RED}✗ Prerequisites not met${NC}"
        exit 1
    fi

    echo -e "${YELLOW}Fetching paper trading status...${NC}"
    STATUS_OUTPUT=$(get_status)

    echo ""
    echo -e "${GREEN}─── Current Status ───${NC}"
    echo "$STATUS_OUTPUT"
    echo ""

    # Extract metrics
    METRICS=$(extract_metrics "$STATUS_OUTPUT")
    IFS='|' read -r TOTAL_PNL POSITIONS RUNNING <<< "$METRICS"

    # Display summary
    echo -e "${GREEN}─── Quick Summary ───${NC}"
    echo -e "  Running:       ${RUNNING}"
    echo -e "  Positions:     ${POSITIONS}"
    echo -e "  Total P&L:     ${TOTAL_PNL} KRW"
    echo ""

    # Get recent trades
    echo -e "${YELLOW}Fetching recent trades (last 20)...${NC}"
    HISTORY_OUTPUT=$(get_history 20)

    echo ""
    echo -e "${GREEN}─── Recent Trades ───${NC}"
    echo "$HISTORY_OUTPUT" | head -30
    echo ""

    # Save snapshot if requested
    if [ "$SAVE_SNAPSHOT" = true ]; then
        TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        SNAPSHOT=$(cat <<EOF
{"timestamp":"$TIMESTAMP","total_pnl":$TOTAL_PNL,"positions":$POSITIONS,"running":"$RUNNING"}
EOF
)
        echo "$SNAPSHOT" >> "$DAILY_LOG"
        echo -e "${GREEN}✓ Snapshot saved to $DAILY_LOG${NC}"

        # Update summary file
        cat > "$SUMMARY_LOG" <<EOF
Paper Trading Monitoring Summary
Generated: $(date '+%Y-%m-%d %H:%M:%S')

Current Status:
  Running:       $RUNNING
  Positions:     $POSITIONS
  Total P&L:     $TOTAL_PNL KRW

Daily Log: $DAILY_LOG
Total Snapshots: $(wc -l < "$DAILY_LOG" 2>/dev/null || echo "0")

Recent Trades:
$HISTORY_OUTPUT
EOF
        echo -e "${GREEN}✓ Summary updated at $SUMMARY_LOG${NC}"
    fi

    # Send notification if requested
    if [ "$SEND_NOTIFICATION" = true ]; then
        echo -e "${YELLOW}Notification feature not yet implemented${NC}"
        echo -e "${YELLOW}Integrate with shared/notification/telegram.py if needed${NC}"
    fi

    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ Monitoring complete${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

# Run main function
main
