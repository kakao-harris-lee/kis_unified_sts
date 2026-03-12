#!/bin/bash
# Install or update a crontab entry for synthetic calibration optimizer.
#
# Usage:
#   ./scripts/cron/install_synthetic_calibration_optimizer_cron.sh
#   CRON_SCHEDULE="30 21 * * 6" ./scripts/cron/install_synthetic_calibration_optimizer_cron.sh
#   CRON_MODE=print ./scripts/cron/install_synthetic_calibration_optimizer_cron.sh

set -euo pipefail

PROJECT_DIR="${CRON_PROJECT_DIR:-/home/deploy/project/kis_unified_sts}"
CRON_SCRIPT="$PROJECT_DIR/scripts/cron/synthetic_calibration_optimizer.sh"
CRON_SCHEDULE="${CRON_SCHEDULE:-30 21 * * 6}"
CRON_MODE="${CRON_MODE:-install}"
CRON_TAG="# kis_unified_sts synthetic_calibration_optimizer"
CRON_ENTRY="$CRON_SCHEDULE $CRON_SCRIPT"

print_entry() {
    echo "$CRON_TAG"
    echo "$CRON_ENTRY"
}

case "$CRON_MODE" in
    print)
        print_entry
        exit 0
        ;;
    install)
        ;;
    *)
        echo "Invalid CRON_MODE: $CRON_MODE (expected: install|print)" >&2
        exit 1
        ;;
esac

if [[ ! -x "$CRON_SCRIPT" ]]; then
    echo "Cron script missing or not executable: $CRON_SCRIPT" >&2
    exit 1
fi

TMP_CRON=$(mktemp)
trap 'rm -f "$TMP_CRON"' EXIT

crontab -l 2>/dev/null | grep -v 'synthetic_calibration_optimizer.sh' > "$TMP_CRON" || true
{
    echo "$CRON_TAG"
    echo "$CRON_ENTRY"
} >> "$TMP_CRON"

crontab "$TMP_CRON"

echo "Installed synthetic calibration optimizer cron entry:"
print_entry