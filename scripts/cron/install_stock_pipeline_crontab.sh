#!/usr/bin/env bash
# Idempotent install of stock data, scanner, and paper verification cron entries.
set -euo pipefail

PROJECT_DIR="${CRON_PROJECT_DIR:-/home/deploy/project/kis_unified_sts}"
MODE="${CRON_MODE:-install}"

DAILY_SCANNER="$PROJECT_DIR/scripts/cron/daily_scanner.sh"
DAILY_INDICATOR_SCANNER="$PROJECT_DIR/scripts/cron/daily_indicator_scanner.sh"
STOCK_PAPER_VERIFICATION="$PROJECT_DIR/scripts/cron/stock_paper_daily_verification.sh"
STOCK_DAILY_BACKFILL="$PROJECT_DIR/scripts/cron/stock_daily_backfill.sh"

print_entries() {
    cat <<EOF
# BEGIN STOCK_PIPELINE_PREMARKET
# Daily stock watchlist and indicator snapshots for orchestrator startup.
30 8 * * 1-5 $DAILY_SCANNER
50 8 * * 1-5 $DAILY_INDICATOR_SCANNER
# END STOCK_PIPELINE_PREMARKET

# BEGIN STOCK_PAPER_DAILY_VERIFICATION
# Stock paper objective gate: ClickHouse trades + Redis pipeline + target metrics.
10 16 * * 1-5 $STOCK_PAPER_VERIFICATION
# END STOCK_PAPER_DAILY_VERIFICATION

# BEGIN STOCK_DAILY_CANDLE_BACKFILL
# Refresh daily candles after market close for next-session scanners.
20 16 * * 1-5 $STOCK_DAILY_BACKFILL
# END STOCK_DAILY_CANDLE_BACKFILL
EOF
}

case "$MODE" in
    print)
        print_entries
        exit 0
        ;;
    install)
        ;;
    *)
        echo "Invalid CRON_MODE: $MODE (expected: install|print)" >&2
        exit 1
        ;;
esac

for script in "$DAILY_SCANNER" "$DAILY_INDICATOR_SCANNER" "$STOCK_PAPER_VERIFICATION" "$STOCK_DAILY_BACKFILL"; do
    if [[ ! -x "$script" ]]; then
        echo "Cron script missing or not executable: $script" >&2
        exit 1
    fi
done

TMP_CRON=$(mktemp)
trap 'rm -f "$TMP_CRON"' EXIT

crontab -l 2>/dev/null > "$TMP_CRON" || true
sed -i '/# BEGIN STOCK_PIPELINE_PREMARKET/,/# END STOCK_PIPELINE_PREMARKET/d' "$TMP_CRON"
sed -i '/# BEGIN STOCK_PAPER_DAILY_VERIFICATION/,/# END STOCK_PAPER_DAILY_VERIFICATION/d' "$TMP_CRON"
sed -i '/# BEGIN STOCK_DAILY_CANDLE_BACKFILL/,/# END STOCK_DAILY_CANDLE_BACKFILL/d' "$TMP_CRON"
sed -i '\#daily_scanner.sh#d' "$TMP_CRON"
sed -i '\#daily_indicator_scanner.sh#d' "$TMP_CRON"
sed -i '\#stock_paper_daily_verification.sh#d' "$TMP_CRON"
sed -i '\#stock_daily_backfill.sh#d' "$TMP_CRON"

{
    echo
    print_entries
} >> "$TMP_CRON"

crontab "$TMP_CRON"

echo "Installed stock pipeline cron entries:"
print_entries
