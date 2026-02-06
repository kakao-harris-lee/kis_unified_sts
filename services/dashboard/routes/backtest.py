"""Backtest endpoints."""
from __future__ import annotations

import base64
import io
import logging
import os
import re
import uuid
from datetime import datetime, time
from typing import Any, List, Optional

import numpy as np
import pandas as pd
from clickhouse_driver import Client as ClickHouseDriver
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from shared.backtest import BacktestConfig, BacktestEngine
from shared.backtest.engine import SignalType
from shared.config.loader import ConfigLoader, ConfigNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

SUPPORTED_ASSETS = {"stock", "futures"}
MAX_CHART_POINTS = int(os.getenv("BACKTEST_CHART_MAX_POINTS", "1000"))
MAX_CHART_SECONDS = int(os.getenv("BACKTEST_CHART_RESAMPLE_SECONDS", "1800"))
MAX_CHART_DAYS = int(os.getenv("BACKTEST_CHART_MAX_DAYS", "30"))
SUPPORTED_STRATEGIES = {
    "bb_reversion",
    "ma_crossover",
}


class BacktestRequest(BaseModel):
    """Backtest run request."""

    asset_class: str
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = 10_000_000
    params: Optional[dict] = None


class BacktestRunResponse(BaseModel):
    """Backtest run response."""

    run_id: str
    status: str
    result: "BacktestResult"


class BacktestResult(BaseModel):
    """Backtest result."""

    run_id: str
    status: str
    asset_class: str
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    total_trades: int
    win_rate: float
    created_at: datetime
    completed_at: Optional[datetime]
    chart_image: Optional[str] = None
    trades: Optional[list[dict[str, Any]]] = None


class BacktestListResponse(BaseModel):
    """Backtest list response."""

    runs: List[BacktestResult]
    total: int
    page: int
    limit: int


# In-memory backtest storage
_backtest_store: dict[str, BacktestResult] = {}


def _parse_date_range(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    def _parse(value: str) -> datetime:
        value = value.strip()
        if "T" in value:
            return datetime.fromisoformat(value)
        return datetime.combine(datetime.fromisoformat(value).date(), time.min)

    start = _parse(start_date)
    end = _parse(end_date)
    end = datetime.combine(end.date(), time.max)
    if end < start:
        raise ValueError("end_date must be >= start_date")
    return start, end


def _clickhouse_config(asset_class: str) -> dict[str, Any]:
    database = os.getenv("CLICKHOUSE_STOCK_DATABASE", "market")
    if asset_class == "futures":
        database = os.getenv(
            "CLICKHOUSE_FUTURES_DATABASE",
            os.getenv("CLICKHOUSE_DATABASE", "kospi"),
        )
    port = int(os.getenv("CLICKHOUSE_PORT", "9000"))
    native_port = int(os.getenv("CLICKHOUSE_NATIVE_PORT", str(port)))
    return {
        "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "port": native_port,
        "user": os.getenv("CLICKHOUSE_USER", "default"),
        "password": os.getenv("CLICKHOUSE_PASSWORD", ""),
        "database": database,
    }


def _validate_table_name(table: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_]+$", table):
        raise ValueError("Invalid table name")
    return table


def _set_korean_font() -> str | None:
    try:
        from matplotlib import font_manager, rcParams
    except Exception:
        return None

    preferred = [
        "NanumGothic",
        "NanumBarunGothic",
        "NanumSquare",
        "Noto Sans CJK KR",
        "Noto Sans KR",
        "AppleGothic",
        "Malgun Gothic",
        "UnDotum",
        "UnBatang",
    ]

    for font in font_manager.fontManager.ttflist:
        if font.name in preferred:
            rcParams["font.family"] = font.name
            rcParams["axes.unicode_minus"] = False
            return font.name

    env_path = os.getenv("BACKTEST_KOREAN_FONT_PATH")
    if env_path and os.path.exists(env_path):
        try:
            font_manager.fontManager.addfont(env_path)
            name = font_manager.FontProperties(fname=env_path).get_name()
            rcParams["font.family"] = name
            rcParams["axes.unicode_minus"] = False
            return name
        except Exception:
            pass

    known_paths = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf",
        "/usr/share/fonts/truetype/nanum/NanumSquare_acR.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for font_path in known_paths:
        if not os.path.exists(font_path):
            continue
        try:
            font_manager.fontManager.addfont(font_path)
            name = font_manager.FontProperties(fname=font_path).get_name()
            rcParams["font.family"] = name
            rcParams["axes.unicode_minus"] = False
            return name
        except Exception:
            continue

    for font_path in font_manager.findSystemFonts(fontext="ttf"):
        if any(
            token in font_path
            for token in [
                "Nanum",
                "NotoSansCJK",
                "NotoSansKR",
                "AppleGothic",
                "Malgun",
                "UnDotum",
                "UnBatang",
            ]
        ):
            try:
                font_manager.fontManager.addfont(font_path)
                name = font_manager.FontProperties(fname=font_path).get_name()
                rcParams["font.family"] = name
                rcParams["axes.unicode_minus"] = False
                return name
            except Exception:
                continue
    return None


def _resolve_stock_name(code: str) -> str:
    try:
        from pykrx import stock

        name = stock.get_market_ticker_name(code)
        if name:
            return name
    except Exception:
        pass

    try:
        from shared.collector.historical.stock import STOCK_UNIVERSE

        for item in STOCK_UNIVERSE:
            if item.get("code") == code and item.get("name"):
                return item["name"]
    except Exception:
        pass

    return code


def _fetch_ohlcv(
    asset_class: str,
    symbol: str,
    start: datetime,
    end: datetime,
    params: dict[str, Any],
) -> pd.DataFrame:
    cfg = _clickhouse_config(asset_class)
    final_clause = " FINAL" if os.getenv("CLICKHOUSE_USE_FINAL", "1") == "1" else ""
    table = params.get("table")
    if asset_class == "stock":
        table = _validate_table_name(table or "minute_candles")
        query = f"""
            SELECT code, datetime, open, high, low, close, volume
            FROM {cfg['database']}.{table}{final_clause}
            WHERE code = %(code)s AND datetime >= %(start)s AND datetime <= %(end)s
            ORDER BY datetime ASC
        """
    else:
        table = _validate_table_name(
            table or os.getenv("FUTURES_CANDLE_TABLE", "kospi_mini_1m")
        )
        query = f"""
            SELECT code, datetime, open, high, low, close, volume
            FROM {cfg['database']}.{table}{final_clause}
            WHERE code = %(code)s AND datetime >= %(start)s AND datetime <= %(end)s
            ORDER BY datetime ASC
        """

    client = ClickHouseDriver(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        connect_timeout=10,
    )
    try:
        rows = client.execute(
            query,
            {"code": symbol, "start": start, "end": end},
        )
    finally:
        client.disconnect()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        rows, columns=["code", "datetime", "open", "high", "low", "close", "volume"]
    )
    df["datetime"] = pd.to_datetime(df["datetime"])
    if asset_class == "stock":
        df["name"] = _resolve_stock_name(symbol)
    else:
        df["name"] = df["code"]
    return df


def _resample_ohlcv(df: pd.DataFrame, seconds: int) -> pd.DataFrame:
    if seconds <= 0 or df.empty:
        return df
    df = df.sort_values("datetime").set_index("datetime")
    rule = f"{seconds}s"
    agg = df.resample(rule).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "code": "first",
            "name": "first",
        }
    )
    agg = agg.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return agg


def _trim_recent_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    if days <= 0 or df.empty:
        return df
    end = df["datetime"].max()
    if pd.isna(end):
        return df
    start = end - pd.Timedelta(days=days)
    return df[df["datetime"] >= start].reset_index(drop=True)


def _resolve_strategy_params(
    asset_class: str, strategy: str, request_params: Optional[dict]
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    try:
        config = ConfigLoader.load_strategy(asset_class, strategy)
        strategy_cfg = config.get("strategy", config)
        entry_params = strategy_cfg.get("entry", {}).get("params", {})
        params.update(entry_params)
    except (FileNotFoundError, ConfigNotFoundError):
        pass
    if request_params:
        params.update(request_params)
    return params


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _compute_base_indicators(df: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]

    bb_period = int(params.get("bb_period", 20))
    bb_std = float(params.get("bb_std", 2.0))
    rolling = close.rolling(bb_period)
    df["bb_middle"] = rolling.mean()
    df["bb_std"] = rolling.std(ddof=0)
    df["bb_upper"] = df["bb_middle"] + bb_std * df["bb_std"]
    df["bb_lower"] = df["bb_middle"] - bb_std * df["bb_std"]
    df["bb_bandwidth"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"].replace(0, np.nan)

    rsi_period = int(params.get("rsi_period", 14))
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    fast = int(params.get("macd_fast", 12))
    slow = int(params.get("macd_slow", 26))
    signal = int(params.get("macd_signal", 9))
    macd = _ema(close, fast) - _ema(close, slow)
    macd_signal = _ema(macd, signal)
    df["macd"] = macd
    df["macd_signal"] = macd_signal
    df["macd_hist"] = macd - macd_signal

    ma_short = int(params.get("ma_short", 20))
    ma_long = int(params.get("ma_long", 60))
    df["ma_short"] = close.rolling(ma_short).mean()
    df["ma_long"] = close.rolling(ma_long).mean()
    df["ma_short_prev"] = df["ma_short"].shift(1)
    df["ma_long_prev"] = df["ma_long"].shift(1)

    atr_period = int(params.get("atr_period", 14))
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.rolling(atr_period).mean()

    # 레짐 감지 (SMA 기반)
    regime_period = int(params.get("regime_sma_period", 200))
    regime_threshold = float(params.get("regime_threshold", 0.001))
    df["regime_sma"] = close.rolling(regime_period).mean()
    ratio = close / df["regime_sma"].replace(0, np.nan)
    df["regime"] = "sideways"
    df.loc[ratio > 1 + regime_threshold, "regime"] = "bull"
    df.loc[ratio < 1 - regime_threshold, "regime"] = "bear"

    return df


def _compute_indicators(
    df: pd.DataFrame, strategy: str, params: dict[str, Any]
) -> pd.DataFrame:
    df = _compute_base_indicators(df, params)

    if strategy == "ma_crossover":
        close = df["close"]
        short_period = int(params.get("short_period", params.get("ma_short", 5)))
        long_period = int(params.get("long_period", params.get("ma_long", 20)))
        df["ma_short"] = close.rolling(short_period).mean()
        df["ma_long"] = close.rolling(long_period).mean()
        df["ma_short_prev"] = df["ma_short"].shift(1)
        df["ma_long_prev"] = df["ma_long"].shift(1)

    return df


class IndicatorSignalStrategy:
    def __init__(self, strategy: str, params: dict[str, Any]):
        self.name = strategy
        self.params = params

    def on_bar(self, bar: dict[str, Any]) -> SignalType:
        close = float(bar.get("close") or 0)
        if self.name == "bb_reversion":
            bb_lower = float(bar.get("bb_lower") or 0)
            bb_upper = float(bar.get("bb_upper") or 0)
            rsi = float(bar.get("rsi") or 50)
            macd_hist = float(bar.get("macd_hist") or 0)
            bb_bandwidth = float(bar.get("bb_bandwidth") or 0)

            oversold = float(self.params.get("rsi_oversold", 30))
            overbought = float(self.params.get("rsi_overbought", 70))
            buffer = float(self.params.get("bb_touch_buffer", 1.0))
            use_macd = bool(self.params.get("use_macd_filter", False))
            buy_only = bool(self.params.get("buy_only", False))
            min_bw = float(self.params.get("min_bb_bandwidth", 0))

            # 레짐 기반 방향 결정
            use_regime = bool(self.params.get("use_regime_filter", False))
            if use_regime:
                regime = str(bar.get("regime", "sideways"))
                mode_map = {
                    "bull": str(self.params.get("regime_bull_mode", "buy_only")),
                    "sideways": str(self.params.get("regime_sideways_mode", "buy_only")),
                    "bear": str(self.params.get("regime_bear_mode", "sell_only")),
                }
                mode = mode_map.get(regime, "buy_only")
                if mode == "none":
                    return SignalType.HOLD
                allow_buy = mode in ("buy_only", "both")
                allow_sell = mode in ("sell_only", "both")
            else:
                allow_buy = True
                allow_sell = not buy_only

            # BB bandwidth 필터: 밴드가 너무 좁으면 횡보 → 스킵
            if min_bw > 0 and bb_bandwidth < min_bw:
                return SignalType.HOLD

            # BUY: BB 하단 터치 + RSI 과매도 (+ MACD 확인)
            if allow_buy and close <= bb_lower * buffer and rsi < oversold:
                if use_macd and macd_hist <= 0:
                    return SignalType.HOLD
                return SignalType.BUY

            # SELL: BB 상단 터치 + RSI 과매수 (+ MACD 확인)
            if allow_sell:
                if close >= bb_upper and rsi > overbought:
                    if use_macd and macd_hist >= 0:
                        return SignalType.HOLD
                    return SignalType.SELL

            return SignalType.HOLD

        if self.name == "ma_crossover":
            short = bar.get("ma_short")
            long = bar.get("ma_long")
            short_prev = bar.get("ma_short_prev")
            long_prev = bar.get("ma_long_prev")
            if short is None or long is None or short_prev is None or long_prev is None:
                return SignalType.HOLD
            if short_prev <= long_prev and short > long:
                return SignalType.BUY
            if short_prev >= long_prev and short < long:
                return SignalType.SELL
            return SignalType.HOLD

        return SignalType.HOLD


def _generate_chart(
    df: pd.DataFrame,
    trades: list[dict[str, Any]],
    title: str,
    *,
    asset_class: str,
    equity_curve: list[tuple[datetime, float]] | None = None,
) -> Optional[str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        font_name = _set_korean_font()
        import matplotlib.pyplot as plt
        import mplfinance as mpf
    except Exception as e:
        logger.error(f"mplfinance not available: {e}")
        return None

    df = _trim_recent_days(df, MAX_CHART_DAYS)
    if "datetime" in df.columns:
        df = df.drop_duplicates(subset=["datetime"], keep="last").reset_index(
            drop=True
        )
    if len(df) > MAX_CHART_POINTS:
        df = _resample_ohlcv(df, MAX_CHART_SECONDS)

    df_idx = df.set_index("datetime")
    price_df = df_idx[["open", "high", "low", "close", "volume"]]
    price_df.columns = ["Open", "High", "Low", "Close", "Volume"]

    entry_markers = pd.Series(index=price_df.index, data=np.nan)
    exit_markers = pd.Series(index=price_df.index, data=np.nan)

    for trade in trades:
        entry_time = pd.to_datetime(trade.get("entry_time"))
        exit_time = pd.to_datetime(trade.get("exit_time"))
        if entry_time is not None:
            idx = price_df.index.get_indexer([entry_time], method="nearest")[0]
            entry_markers.iloc[idx] = trade.get("entry_price")
        if exit_time is not None:
            idx = price_df.index.get_indexer([exit_time], method="nearest")[0]
            exit_markers.iloc[idx] = trade.get("exit_price")

    add_plots = []
    next_panel = 2
    rsi_panel = None
    macd_panel = None
    atr_panel = None

    rsi_series = df_idx["rsi"] if "rsi" in df.columns else None
    rsi_valid = rsi_series is not None and rsi_series.notna().any()
    if rsi_valid:
        rsi_panel = next_panel
        next_panel += 1

    macd_series = df_idx["macd"] if "macd" in df.columns else None
    macd_signal_series = (
        df_idx["macd_signal"] if "macd_signal" in df.columns else None
    )
    macd_hist_series = df_idx["macd_hist"] if "macd_hist" in df.columns else None
    macd_valid = (
        macd_series is not None
        and macd_signal_series is not None
        and macd_series.notna().any()
        and macd_signal_series.notna().any()
    )
    if macd_valid:
        macd_panel = next_panel
        next_panel += 1

    atr_series = df_idx["atr"] if "atr" in df.columns else None
    atr_valid = (
        asset_class == "futures" and atr_series is not None and atr_series.notna().any()
    )
    if atr_valid:
        atr_panel = next_panel
        next_panel += 1
    if "ma_short" in df.columns:
        add_plots.append(
            mpf.make_addplot(
                df_idx["ma_short"],
                color="dodgerblue",
                linewidths=1.2,
                label="MA Short",
            )
        )
    if "ma_long" in df.columns:
        add_plots.append(
            mpf.make_addplot(
                df_idx["ma_long"],
                color="orange",
                linewidths=1.2,
                label="MA Long",
            )
        )
    if "bb_upper" in df.columns and "bb_lower" in df.columns:
        add_plots.append(
            mpf.make_addplot(
                df_idx["bb_upper"],
                color="gray",
                linewidths=0.9,
                label="BB Upper",
            )
        )
        add_plots.append(
            mpf.make_addplot(
                df_idx["bb_lower"],
                color="gray",
                linewidths=0.9,
                label="BB Lower",
            )
        )
        if "bb_middle" in df.columns:
            add_plots.append(
                mpf.make_addplot(
                    df_idx["bb_middle"],
                    color="lightgray",
                    linewidths=0.8,
                    label="BB Middle",
                )
            )
    if entry_markers.notna().any():
        add_plots.append(
            mpf.make_addplot(
                entry_markers, type="scatter", marker="^", color="g", label="Entry"
            )
        )
    if exit_markers.notna().any():
        add_plots.append(
            mpf.make_addplot(
                exit_markers, type="scatter", marker="v", color="r", label="Exit"
            )
        )

    if equity_curve:
        try:
            eq_idx = pd.to_datetime([t for t, _ in equity_curve])
            eq_vals = pd.Series([v for _, v in equity_curve], index=eq_idx)
            eq_vals = eq_vals.reindex(price_df.index, method="nearest")
            price_min = float(price_df["Close"].min())
            price_max = float(price_df["Close"].max())
            eq_min = float(eq_vals.min())
            eq_max = float(eq_vals.max())
            if eq_max > eq_min:
                scaled = (eq_vals - eq_min) / (eq_max - eq_min)
                scaled = scaled * (price_max - price_min) + price_min
                add_plots.append(
                    mpf.make_addplot(
                        scaled,
                        color="cyan",
                        linewidths=1.3,
                        label="Equity (scaled)",
                    )
                )
        except Exception as e:
            logger.debug(f"Failed to overlay equity curve: {e}")

    if rsi_valid and rsi_panel is not None:
        rsi_index = df_idx.index
        for level, color in [(30, "dimgray"), (50, "gray"), (70, "dimgray")]:
            add_plots.append(
                mpf.make_addplot(
                    pd.Series(level, index=rsi_index),
                    panel=rsi_panel,
                    color=color,
                    linestyle="--",
                    linewidths=0.7,
                    secondary_y=False,
                    ylim=(0, 100),
                )
            )
        add_plots.append(
            mpf.make_addplot(
                rsi_series,
                panel=rsi_panel,
                color="purple",
                linewidths=1.1,
                ylim=(0, 100),
                label="RSI",
            )
        )
    if macd_valid and macd_panel is not None:
        add_plots.append(
            mpf.make_addplot(
                macd_series,
                panel=macd_panel,
                color="teal",
                linewidths=1.1,
                label="MACD",
            )
        )
        add_plots.append(
            mpf.make_addplot(
                macd_signal_series,
                panel=macd_panel,
                color="orange",
                linewidths=1.0,
                label="Signal",
            )
        )
        if macd_hist_series is not None and macd_hist_series.notna().any():
            hist = macd_hist_series.fillna(0)
            hist_colors = ["green" if v >= 0 else "red" for v in hist.values]
            add_plots.append(
                mpf.make_addplot(
                    hist,
                    panel=macd_panel,
                    type="bar",
                    color=hist_colors,
                    alpha=0.35,
                    label="MACD Hist",
                )
            )
    if atr_valid and atr_panel is not None:
        add_plots.append(
            mpf.make_addplot(
                atr_series,
                panel=atr_panel,
                color="brown",
                linewidths=1.0,
                label="ATR",
            )
        )

    panel_count = max(2, next_panel)
    panel_ratios = [5, 1] + [1] * max(0, panel_count - 2)

    style = "nightclouds"
    if font_name:
        style = mpf.make_mpf_style(
            base_mpf_style="nightclouds",
            rc={"font.family": font_name, "axes.unicode_minus": False},
        )

    plot_kwargs = dict(
        type="candle",
        style=style,
        volume=True,
        title=title,
        panel_ratios=tuple(panel_ratios),
        returnfig=True,
    )
    if add_plots:
        plot_kwargs["addplot"] = add_plots

    fig, axlist = mpf.plot(price_df, **plot_kwargs)
    try:
        if isinstance(axlist, (list, tuple)) and axlist:
            for idx, ax in enumerate(axlist):
                handles, labels = ax.get_legend_handles_labels()
                if labels:
                    ax.legend(
                        handles,
                        labels,
                        loc="upper left",
                        fontsize=8,
                        framealpha=0.6,
                    )
    except Exception:
        pass
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


@router.get("", response_model=BacktestListResponse)
async def get_backtests(
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    limit: int = Query(20, ge=1, le=100, description="Number of runs"),
    page: int = Query(1, ge=1, description="Page number"),
):
    """Get list of backtest runs."""
    runs = list(_backtest_store.values())

    if strategy:
        runs = [r for r in runs if r.strategy == strategy]

    runs.sort(key=lambda r: r.created_at, reverse=True)

    start = (page - 1) * limit
    end = start + limit
    paginated = runs[start:end]

    summarized = [r.model_copy(update={"chart_image": None, "trades": None}) for r in paginated]

    return BacktestListResponse(
        runs=summarized,
        total=len(runs),
        page=page,
        limit=limit,
    )


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest(request: BacktestRequest):
    """Start a new backtest run."""
    asset_class = request.asset_class.lower().strip()
    if asset_class not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=400, detail="asset_class must be stock or futures")

    strategy = request.strategy.strip()
    if strategy not in SUPPORTED_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported strategy: {strategy}",
        )

    try:
        start, end = _parse_date_range(request.start_date, request.end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    params = _resolve_strategy_params(asset_class, strategy, request.params)
    df = _fetch_ohlcv(asset_class, request.symbol, start, end, params)
    if df.empty:
        raise HTTPException(status_code=404, detail="No data found for request")

    df = _compute_indicators(df, strategy, params)

    if asset_class == "stock":
        config = BacktestConfig.stock(initial_capital=request.initial_capital)
    else:
        config = BacktestConfig.futures(initial_capital=request.initial_capital)

    engine = BacktestEngine(IndicatorSignalStrategy(strategy, params), config)
    result = engine.run(df)

    trades = [t.to_dict() for t in result.trades]
    display_name = request.symbol
    if "name" in df.columns and not df["name"].isna().all():
        display_name = str(df["name"].iloc[0])
    chart_image = _generate_chart(
        df,
        trades,
        title=f"{strategy} ({display_name})",
        asset_class=asset_class,
        equity_curve=result.equity_curve,
    )

    run_id = str(uuid.uuid4())[:8]
    now = datetime.now()
    response = BacktestResult(
        run_id=run_id,
        status="completed",
        asset_class=asset_class,
        strategy=strategy,
        symbol=request.symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        final_capital=result.final_capital,
        total_return_pct=result.total_return_pct,
        sharpe_ratio=result.sharpe_ratio,
        max_drawdown_pct=result.max_drawdown_pct,
        total_trades=result.total_trades,
        win_rate=result.win_rate,
        created_at=now,
        completed_at=now,
        chart_image=chart_image,
        trades=trades,
    )

    _backtest_store[run_id] = response

    return BacktestRunResponse(run_id=run_id, status="completed", result=response)


@router.get("/{run_id}", response_model=BacktestResult)
async def get_backtest_result(run_id: str):
    """Get backtest result by ID."""
    if run_id not in _backtest_store:
        raise HTTPException(status_code=404, detail=f"Backtest run {run_id} not found")

    return _backtest_store[run_id]


@router.delete("/{run_id}")
async def delete_backtest(run_id: str):
    """Delete a backtest run."""
    if run_id not in _backtest_store:
        raise HTTPException(status_code=404, detail=f"Backtest run {run_id} not found")

    del _backtest_store[run_id]
    return {"status": "deleted", "run_id": run_id}
