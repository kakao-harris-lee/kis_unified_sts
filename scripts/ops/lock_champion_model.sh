#!/bin/bash
# Lock production RL champion model against accidental overwrite.
# Run after each intentional promote.
set -e

MODEL_FILE="/home/deploy/project/kis_unified_sts/models/futures/rl/mppo_best/best_model.zip"

if [ ! -f "$MODEL_FILE" ]; then
    echo "ERROR: $MODEL_FILE not found"
    exit 1
fi

chmod 0444 "$MODEL_FILE"
echo "Locked: $MODEL_FILE -> $(stat -c '%a %n' "$MODEL_FILE")"
