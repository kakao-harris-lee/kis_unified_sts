#!/bin/bash
# Temporarily unlock production champion for intentional promote.
# MUST be followed by lock_champion_model.sh after promote succeeds.
set -e

MODEL_FILE="/home/deploy/project/kis_unified_sts/models/futures/rl/mppo_best/best_model.zip"

if [ ! -f "$MODEL_FILE" ]; then
    echo "ERROR: $MODEL_FILE not found"
    exit 1
fi

chmod 0644 "$MODEL_FILE"
echo "UNLOCKED (temporary): $MODEL_FILE -> $(stat -c '%a %n' "$MODEL_FILE")"
echo "IMPORTANT: re-lock with scripts/ops/lock_champion_model.sh after promote."
