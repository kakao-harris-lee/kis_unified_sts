#!/bin/bash
# Post-training backtest: compare pre vs post volatile-data training models
# Run after RL training completes

set -a && source /home/deploy/project/kis_unified_sts/.env && set +a
cd /home/deploy/project/kis_unified_sts

echo "=== Post-Training Backtest Comparison ==="
echo "Date: $(date)"
echo ""

# 1. Volatile period (3/3-3/9) — primary comparison
echo "===== VOLATILE PERIOD (3/3-3/9) ====="
echo ""
echo "--- PRE-TRAINING MODEL ---"
RL_MPPO_MODEL_PATH=models/futures/rl/mppo_best/best_model_pre_volatile_training.zip \
  .venv/bin/sts backtest run -s rl_mppo -a futures --symbol 101S6000 \
  --start 2026-03-03 --end 2026-03-09 -c 100000000 --no-track 2>&1 | \
  grep -E "총 수익률|총 거래|승률|Sharpe|최대 낙폭|Profit Factor"

echo ""
echo "--- POST-TRAINING MODEL (new mppo_best) ---"
.venv/bin/sts backtest run -s rl_mppo -a futures --symbol 101S6000 \
  --start 2026-03-03 --end 2026-03-09 -c 100000000 --no-track 2>&1 | \
  grep -E "총 수익률|총 거래|승률|Sharpe|최대 낙폭|Profit Factor"

echo ""

# 2. Full period — regression check
echo "===== FULL PERIOD (all data) ====="
echo ""
echo "--- PRE-TRAINING MODEL ---"
RL_MPPO_MODEL_PATH=models/futures/rl/mppo_best/best_model_pre_volatile_training.zip \
  .venv/bin/sts backtest run -s rl_mppo -a futures --symbol 101S6000 \
  -c 100000000 --no-track 2>&1 | \
  grep -E "총 수익률|총 거래|승률|Sharpe|최대 낙폭|Profit Factor|기간"

echo ""
echo "--- POST-TRAINING MODEL (new mppo_best) ---"
.venv/bin/sts backtest run -s rl_mppo -a futures --symbol 101S6000 \
  -c 100000000 --no-track 2>&1 | \
  grep -E "총 수익률|총 거래|승률|Sharpe|최대 낙폭|Profit Factor|기간"

echo ""
echo "=== Comparison Complete ==="
