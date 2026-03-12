"""Adapt external-market OHLCV patterns into KOSPI-like transfer samples."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from shared.config import ConfigLoader


class CrossMarketAdapter:
    def __init__(self, config_path: str = "ml/cross_market_transfer.yaml"):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.inputs = dict(self.config.get("inputs", {}) or {})
        self.adapter = dict(self.config.get("adapter", {}) or {})
        self.output = dict(self.config.get("output", {}) or {})

    def _load_config(self, config_path: str) -> dict[str, Any]:
        path = Path(config_path)
        if path.is_absolute() and path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        if path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        return ConfigLoader.load(config_path)

    def load_source_frames(self, repo_root: Path) -> list[tuple[str, pd.DataFrame]]:
        frames: list[tuple[str, pd.DataFrame]] = []
        for path_str in self.inputs.get("source_paths", []) or []:
            path = Path(path_str)
            if not path.is_absolute():
                path = repo_root / path
            if not path.exists():
                continue
            frame = pd.read_csv(path) if path.suffix == ".csv" else pd.read_parquet(path)
            market = frame.get("source_market")
            if isinstance(market, pd.Series) and not market.empty:
                market_name = str(market.iloc[0])
            else:
                market_name = path.stem.split("_")[0]
            frames.append((market_name, frame))

        if frames:
            return frames
        if not bool(self.inputs.get("allow_sample_fallback", True)):
            raise ValueError("No transfer source frames available and sample fallback is disabled")
        return [("cme", self._generate_sample_frame("cme")), ("ose", self._generate_sample_frame("ose"))]

    def adapt_frame(self, frame: pd.DataFrame, *, source_market: str) -> pd.DataFrame:
        df = frame.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)

        returns = df["close"].pct_change().fillna(0.0)
        scaled_returns = returns * float(self.adapter.get("volatility_scale", 0.85))
        scaled_returns += np.random.default_rng(42).normal(0.0, float(self.adapter.get("noise_scale", 0.0005)), len(df))

        target_start = float(self.adapter.get("target_start_price", 350.0))
        close = [target_start]
        for ret in scaled_returns.iloc[1:]:
            close.append(max(close[-1] * (1 + float(ret)), 1e-6))
        df["close"] = np.array(close, dtype=float)
        df["open"] = df["close"].shift(1).fillna(df["close"])
        spread = (df.get("high", df["close"]) - df.get("low", df["close"]).fillna(df["close"])).abs()
        spread = spread.fillna(df["close"] * 0.001) * max(float(self.adapter.get("volatility_scale", 0.85)), 0.1)
        df["high"] = df[["open", "close"]].max(axis=1) + spread / 2
        df["low"] = (df[["open", "close"]].min(axis=1) - spread / 2).clip(lower=1e-6)
        df["volume"] = (df["volume"].fillna(0).clip(lower=1) * float(self.adapter.get("volume_scale", 1.0))).round().astype(int)
        df["scenario"] = df.get("scenario", f"transfer_{source_market}")
        df["source_type"] = "transfer"
        df["source_market"] = source_market
        return df[["datetime", "open", "high", "low", "close", "volume", "scenario", "source_type", "source_market"]]

    def _generate_sample_frame(self, market: str) -> pd.DataFrame:
        rng = np.random.default_rng(abs(hash(market)) % (2**32))
        bars_per_day = int(self.adapter.get("bars_per_day", 390))
        rows: list[dict[str, Any]] = []
        price = 1000.0
        for day_idx in range(5):
            day = pd.Timestamp("2025-01-02") + pd.Timedelta(days=day_idx)
            for bar in range(bars_per_day):
                dt = day + pd.Timedelta(hours=9, minutes=bar)
                ret = rng.normal(0.0, 0.0012)
                open_price = price
                close_price = max(open_price * (1 + ret), 1e-6)
                high = max(open_price, close_price) * (1 + abs(rng.normal(0.0, 0.0008)))
                low = min(open_price, close_price) * (1 - abs(rng.normal(0.0, 0.0008)))
                rows.append(
                    {
                        "datetime": dt,
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "close": close_price,
                        "volume": int(max(rng.lognormal(7.0, 0.2), 1)),
                        "scenario": f"transfer_{market}",
                        "source_market": market,
                    }
                )
                price = close_price
        return pd.DataFrame(rows)
