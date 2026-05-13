#!/usr/bin/env python3
"""Weekly Phase F validation report: Setup A/C vs RL shadow counterfactual.

Q5 success criteria:
  Sharpe_new >= Sharpe_rl * 0.9 AND MDD_new <= MDD_rl * 1.1
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _query_setup_pnl(ch_client, window_days: int = 7) -> pd.DataFrame:
    """Closed trades from Setup A/C in window."""
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    rows = ch_client.execute(
        "SELECT exit_date, pnl, side, code "
        "FROM kospi.rl_trades "
        "WHERE asset_class='futures' AND exit_date >= %(c)s "
        "  AND strategy IN ('setup_a_gap_reversion', 'setup_c_event_reaction') "
        "ORDER BY exit_date",
        {"c": cutoff},
    )
    return pd.DataFrame(rows, columns=["exit_date", "pnl", "side", "code"])


RL_SHADOW_PROXY_CODE = "101S6000"
"""KOSPI200 futures (continuous) used as price proxy for mini-future shadow predictions.

RL was trained on 101S6000 per project convention, and mini bars (A05xxx) are not
ingested into kospi200f_1m. Both products track the same index — percentage moves
are functionally equivalent — so 101S6000 is the canonical proxy series."""


def _query_rl_shadow_pnl(ch_client, window_days: int = 7) -> pd.DataFrame:
    """Synthetic 'would-be' PnL from RL shadow predictions.

    Per spec section 6 - Phase F validation. Uses kospi.rl_shadow_predictions
    with RL_SHADOW_PROXY_CODE bars as the proxy price series.
    """
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    # ClickHouse ASOF JOIN requires ≥1 equi-join column, so we materialize the
    # proxy code on both sides as a synthetic join key.
    rows = ch_client.execute(
        "WITH preds AS ("
        "  SELECT ts, action, %(proxy)s AS code, "
        "         ts AS entry_ts, ts + INTERVAL 15 MINUTE AS exit_ts "
        "  FROM kospi.rl_shadow_predictions "
        "  WHERE ts >= %(c)s AND action != 4"
        "), "
        "bars AS ("
        "  SELECT code, datetime, close FROM kospi.kospi200f_1m "
        "  WHERE code = %(proxy)s"
        ") "
        "SELECT p.ts, p.action, eb.close AS entry_close, xb.close AS exit_close "
        "FROM preds p "
        "ASOF LEFT JOIN bars eb ON p.code = eb.code AND p.entry_ts <= eb.datetime "
        "ASOF LEFT JOIN bars xb ON p.code = xb.code AND p.exit_ts <= xb.datetime",
        {"c": cutoff, "proxy": RL_SHADOW_PROXY_CODE},
    )
    df = pd.DataFrame(rows, columns=["ts", "action", "entry_close", "exit_close"])
    if df.empty:
        return df
    df = df.dropna(subset=["entry_close", "exit_close"])
    # ASOF LEFT JOIN with no match returns 0.0 (Float64 default) rather than NULL,
    # so explicitly filter rows where bar data is missing (price is always > 0).
    df = df[(df["entry_close"] > 0) & (df["exit_close"] > 0)]
    if df.empty:
        return df
    # action 0=LONG_ENTRY, 1=LONG_EXIT, 2=SHORT_ENTRY, 3=SHORT_EXIT (rl_mppo.py)
    df["pnl"] = df.apply(
        lambda r: (r.exit_close - r.entry_close) if r.action == 0
        else (r.entry_close - r.exit_close) if r.action == 2 else 0,
        axis=1,
    )
    return df[["ts", "pnl"]]


def _sharpe(pnl: pd.Series) -> float:
    if len(pnl) < 2 or pnl.std() == 0:
        return 0.0
    return float(pnl.mean() / pnl.std() * np.sqrt(252))


def _max_drawdown(pnl: pd.Series) -> float:
    if pnl.empty:
        return 0.0
    cum = pnl.cumsum()
    peak = cum.cummax()
    drawdown = cum - peak
    return float(drawdown.min())


def _format_report(setup_df: pd.DataFrame, rl_df: pd.DataFrame, window_days: int) -> str:
    s_sharpe = _sharpe(setup_df["pnl"]) if not setup_df.empty else 0
    s_mdd = _max_drawdown(setup_df["pnl"]) if not setup_df.empty else 0
    r_sharpe = _sharpe(rl_df["pnl"]) if not rl_df.empty else 0
    r_mdd = _max_drawdown(rl_df["pnl"]) if not rl_df.empty else 0

    if setup_df.empty or rl_df.empty or r_sharpe == 0:
        decision = "INSUFFICIENT_DATA"
    else:
        sharpe_ratio = s_sharpe / r_sharpe
        mdd_ratio = s_mdd / r_mdd if r_mdd != 0 else 1.0
        criterion_a = sharpe_ratio >= 0.9
        criterion_b = mdd_ratio <= 1.1
        if criterion_a and criterion_b:
            decision = "READY_FOR_PHASE_G"
        else:
            decision = "FAIL_OR_PENDING"

    return (
        f"Phase F Validation Report (last {window_days} days)\n"
        f"\n"
        f"Setup A/C with forecast: Sharpe={s_sharpe:.2f} | MDD={s_mdd:,.0f} | "
        f"Trades={len(setup_df)}\n"
        f"RL shadow counterfactual: Sharpe={r_sharpe:.2f} | MDD={r_mdd:,.0f} | "
        f"Trades={len(rl_df)}\n"
        f"\n"
        f"Q5 ratios:\n"
        f"  Sharpe new/RL  = {(s_sharpe / r_sharpe if r_sharpe else 0):.2f} (need >= 0.90)\n"
        f"  MDD new/RL     = {(s_mdd / r_mdd if r_mdd else 0):.2f} (need <= 1.10)\n"
        f"\n"
        f"Decision: {decision}\n"
    )


def main() -> int:
    from clickhouse_driver import Client
    from shared.db.config import ClickHouseConfig

    cfg = ClickHouseConfig.from_env(database="kospi")
    ch = Client(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database="kospi",
    )

    window_days = int(os.environ.get("FORECAST_REPORT_WINDOW_DAYS", "7"))
    setup_df = _query_setup_pnl(ch, window_days)
    rl_df = _query_rl_shadow_pnl(ch, window_days)
    report = _format_report(setup_df, rl_df, window_days)
    print(report)

    # Send to Telegram briefing channel
    token = os.environ.get("TELEGRAM_BRIEFING_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_BRIEFING_CHAT_ID")
    if token and chat_id:
        import urllib.parse
        import urllib.request
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": report}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:  # noqa: BLE001
            logger.warning("Telegram send failed: %s", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
