#!/usr/bin/env bash
# Install Phase 4 systemd units.
# Run once on the deploy host with sudo.
set -euo pipefail

UNIT_DIR=/etc/systemd/system
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

UNITS=(
    kis-decision-engine.service
    kis-risk-filter.service
    kis-order-router.service
    kis-kill-switch.service
)

for unit in "${UNITS[@]}"; do
    echo "Installing $unit"
    sudo cp "$SOURCE_DIR/$unit" "$UNIT_DIR/$unit"
done

sudo systemctl daemon-reload

echo
echo "Units installed. Enable and start with:"
for unit in "${UNITS[@]}"; do
    echo "  sudo systemctl enable --now ${unit%.service}"
done

echo
echo "Crontab entry for Weekly Edge Review (Mon 05:00 KST):"
echo "  0 5 * * 1 /home/deploy/project/kis_unified_sts/.venv/bin/python -m jobs.weekly_edge_review >> /home/deploy/project/kis_unified_sts/logs/weekly_edge_review/\$(date +\\%Y\\%m\\%d).log 2>&1"
