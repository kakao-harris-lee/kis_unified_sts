#!/usr/bin/env bash
set -euo pipefail

asset="${TRADING_ASSET_CLASS:-stock}"
mode="${TRADING_MODE:-}"
strategy="${TRADING_STRATEGY:-}"
capital="${TRADING_INITIAL_CAPITAL:-10000000}"
run_mode="${TRADING_RUN_MODE:-daemon}"
live_confirm="${TRADING_LIVE_CONFIRM:-}"
kis_real_trading="${KIS_REAL_TRADING:-false}"
kis_real_trading="${kis_real_trading,,}"

if [[ -z "$mode" ]]; then
  if [[ "$kis_real_trading" =~ ^(1|true|yes)$ ]]; then
    mode="live"
  else
    mode="paper"
  fi
fi

case "$asset" in
  stock|futures) ;;
  *)
    echo "Invalid TRADING_ASSET_CLASS: $asset" >&2
    exit 64
    ;;
esac

case "$mode" in
  paper|live) ;;
  *)
    echo "Invalid TRADING_MODE: $mode" >&2
    exit 64
    ;;
esac

case "$run_mode" in
  daemon|single) ;;
  *)
    echo "Invalid TRADING_RUN_MODE: $run_mode" >&2
    exit 64
    ;;
esac

args=(sts trade start --asset "$asset" --capital "$capital")

if [[ -n "$strategy" ]]; then
  args+=(--strategy "$strategy")
fi

if [[ "$mode" == "live" ]]; then
  if [[ "$live_confirm" != "I_UNDERSTAND_LIVE_TRADING" ]]; then
    echo "Refusing live trading: set TRADING_LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING to enable non-interactive live mode." >&2
    exit 64
  fi
  args+=(--live --yes-live)
else
  args+=(--paper)
fi

if [[ "$run_mode" == "daemon" ]]; then
  args+=(--daemon)
else
  args+=(--single)
fi

echo "Starting trading loop: asset=$asset mode=$mode strategy=${strategy:-all enabled} capital=$capital run_mode=$run_mode"
exec "${args[@]}"
