"""BacktestStrategyAdapter — bridges TradingStrategy → StrategyProtocol.

TradingStrategy (from the registry/factory) uses async check_entry(EntryContext)
returning Signal, while BacktestEngine expects sync on_bar(bar) → SignalType.
This adapter handles the conversion:

    1. Feeds each bar into StreamingIndicatorEngine to compute BB/RSI
    2. Enriches bar with derived metrics (prev_day_volume, VWAP, RVOL, etc.)
    3. Builds EntryContext from bar + computed indicators
    4. Runs the async entry generator synchronously
    5. Maps Signal.metadata["signal_direction"] → SignalType.BUY / SELL / HOLD
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

import pandas as pd

from services.trading.indicator_engine import StreamingIndicatorEngine
from shared.backtest.engine import ExitReason, SignalType
from shared.indicators.contracts import IndicatorContract
from shared.indicators.resolver import StreamingIndicatorResolver
from shared.models.position import Position as ModelPosition, PositionSide
from shared.strategy.base import EntryContext, ExitContext, TradingStrategy

logger = logging.getLogger(__name__)


class _MarketDataEnricher:
    """Tracks rolling stats per symbol to enrich bar data for backtesting.

    Computes derived fields that are normally provided by the orchestrator
    or external data sources at runtime:
      - prev_day_volume: previous trading day's total volume
      - intraday cumulative volume
      - change_pct: percent change from previous day's close
      - high_N: N-day rolling high
      - rvol: relative volume (current bar vs average)
      - vwap: intraday volume-weighted average price
      - volume_velocity / volume_acceleration: volume derivatives
      - accumulation_score: heuristic based on recent volume patterns
    """

    def __init__(self, breakout_period: int = 5, rvol_avg_days: int = 5):
        self._breakout_period = breakout_period
        self._rvol_avg_days = rvol_avg_days

        # Pre-scanned daily volume lookup: code → {date_str → prev_day_total}
        self._prev_day_volume_map: dict[str, dict[str, float]] = {}

        # Per-symbol tracking
        self._current_date: dict[str, str] = {}
        self._daily_volume: dict[str, float] = {}  # current day accumulation
        self._prev_day_volume: dict[str, float] = {}
        self._prev_day_close: dict[str, float] = {}

        # Rolling daily stats for multi-day indicators
        self._daily_closes: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        self._daily_highs: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        self._daily_volumes: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))

        # Intraday VWAP
        self._vwap_pv_sum: dict[str, float] = {}  # sum(price * volume)
        self._vwap_v_sum: dict[str, float] = {}  # sum(volume)

        # Volume velocity/acceleration (rolling 3-bar)
        self._recent_volumes: dict[str, deque] = defaultdict(lambda: deque(maxlen=5))

        # Bar-level volume for RVOL (relative volume per bar)
        self._all_bar_volumes: dict[str, deque] = defaultdict(lambda: deque(maxlen=500))

    def prescan(self, data: pd.DataFrame) -> None:
        """Pre-scan backtest data to compute daily volume totals.

        Builds lookup: code → {date_str: previous_day_total_volume}
        so that prev_day_volume is available from Day 2 bar 1.
        """
        if "datetime" not in data.columns or "volume" not in data.columns:
            return

        df = data.copy()
        df["_date"] = pd.to_datetime(df["datetime"]).dt.strftime("%Y-%m-%d")

        if "code" not in df.columns:
            df["_code"] = "BACKTEST"
        else:
            df["_code"] = df["code"].astype(str).fillna("BACKTEST")

        daily_vol = df.groupby(["_code", "_date"])["volume"].sum()

        for code in daily_vol.index.get_level_values(0).unique():
            code_data = daily_vol.loc[code]
            dates = list(code_data.index)
            vols = list(code_data.values)
            lookup: dict[str, float] = {}
            for i in range(1, len(dates)):
                lookup[dates[i]] = float(vols[i - 1])
            if lookup:
                self._prev_day_volume_map[code] = lookup

        total = sum(len(v) for v in self._prev_day_volume_map.values())
        logger.info(f"Prescan: built prev_day_volume map for {total} date entries")

    def enrich(self, bar: dict[str, Any], timestamp: datetime) -> dict[str, Any]:
        """Add derived metrics to the bar dict (mutates and returns it)."""
        code = str(bar.get("code", "BACKTEST") or "BACKTEST")
        date_str = timestamp.strftime("%Y-%m-%d")
        close = float(bar.get("close", 0) or 0)
        high = float(bar.get("high", 0) or 0)
        volume = float(bar.get("volume", 0) or 0)
        typical_price = (
            float(bar.get("high", close) or close)
            + float(bar.get("low", close) or close)
            + close
        ) / 3.0

        # Day change detection
        prev_date = self._current_date.get(code)
        if prev_date != date_str:
            if prev_date is not None:
                # Save previous day's stats
                self._prev_day_volume[code] = self._daily_volume.get(code, 0)
                self._prev_day_close[code] = close  # will be overwritten below
                # Record previous day's close/high/volume for rolling
                # (prev_day_close is set from last bar of previous day,
                #  but we approximate with current day's open)
                day_vol = self._daily_volume.get(code, 0)
                if day_vol > 0:
                    self._daily_volumes[code].append(day_vol)
            # Reset intraday accumulators
            self._daily_volume[code] = 0.0
            self._vwap_pv_sum[code] = 0.0
            self._vwap_v_sum[code] = 0.0
            self._current_date[code] = date_str

        # Update daily close/high tracking (last bar of day wins)
        # We track these per-bar; at day end they reflect final values
        if not self._daily_closes[code] or prev_date != date_str:
            self._daily_closes[code].append(close)
            self._daily_highs[code].append(high)
        else:
            # Update today's entry
            self._daily_closes[code][-1] = close
            if high > self._daily_highs[code][-1]:
                self._daily_highs[code][-1] = high

        # Accumulate intraday volume
        self._daily_volume[code] = self._daily_volume.get(code, 0) + volume

        # prev_day_close: use last recorded close from previous day
        # On first day we won't have it, so use open
        if code not in self._prev_day_close and prev_date is None:
            self._prev_day_close[code] = float(bar.get("open", close) or close)

        # ── Enrich bar ──

        # prev_day_volume (for opening_volume_surge)
        pdv = self._prev_day_volume.get(code, 0)
        if pdv == 0 and self._prev_day_volume_map:
            pdv = self._prev_day_volume_map.get(code, {}).get(date_str, 0)
        bar["prev_day_volume"] = int(pdv)

        # Cumulative intraday volume (override bar's per-minute volume)
        bar["volume"] = int(self._daily_volume[code])

        # change_pct (for opening_volume_surge)
        pdc = self._prev_day_close.get(code, 0)
        if pdc > 0:
            bar["change_pct"] = (close - pdc) / pdc * 100.0
        else:
            bar["change_pct"] = 0.0

        # high_N: N-day rolling high (for volume_accumulation)
        period = self._breakout_period
        highs = list(self._daily_highs[code])
        if len(highs) >= period + 1:
            # Exclude today — breakout above previous N-day high
            bar[f"high_{period}"] = max(highs[-(period + 1):-1])
        elif len(highs) >= 2:
            bar[f"high_{period}"] = max(highs[:-1])
        else:
            bar[f"high_{period}"] = high

        # rvol: relative volume per bar (for volume_accumulation)
        # Compare current bar volume to average bar volume
        self._all_bar_volumes[code].append(volume)
        bar_vols = list(self._all_bar_volumes[code])
        if len(bar_vols) >= 20:
            avg_bar_vol = sum(bar_vols[:-1]) / (len(bar_vols) - 1)
            bar["rvol"] = volume / avg_bar_vol if avg_bar_vol > 0 else 1.0
        else:
            bar["rvol"] = 1.0

        # VWAP (for volume_accumulation)
        self._vwap_pv_sum[code] = self._vwap_pv_sum.get(code, 0) + typical_price * volume
        self._vwap_v_sum[code] = self._vwap_v_sum.get(code, 0) + volume
        vwap_v = self._vwap_v_sum[code]
        bar["vwap"] = self._vwap_pv_sum[code] / vwap_v if vwap_v > 0 else close

        # Volume velocity & acceleration
        self._recent_volumes[code].append(volume)
        vols = list(self._recent_volumes[code])
        if len(vols) >= 2:
            bar["volume_velocity"] = vols[-1] - vols[-2]
        else:
            bar["volume_velocity"] = 0.0
        if len(vols) >= 3:
            v1 = vols[-1] - vols[-2]
            v0 = vols[-2] - vols[-3]
            bar["volume_acceleration"] = v1 - v0
        else:
            bar["volume_acceleration"] = 0.0

        # Update prev_day_close at every bar (so last bar of day is accurate)
        self._prev_day_close[code] = close

        return bar

    def compute_accumulation_score(self, code: str) -> int:
        """Compute a heuristic accumulation score (0-100) from volume patterns.

        Heuristic: if recent daily volumes are trending up relative to average,
        the stock is likely being accumulated.  For backtesting, this replaces
        the overnight scan that normally provides this score.
        """
        daily_vols = list(self._daily_volumes[code])
        if len(daily_vols) < 3:
            return 65  # Default near-pass for limited data

        recent = daily_vols[-3:]
        older = daily_vols[:-3] if len(daily_vols) > 3 else daily_vols[:1]
        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)

        if avg_older <= 0:
            return 65

        ratio = avg_recent / avg_older
        if ratio >= 2.0:
            return 95
        elif ratio >= 1.5:
            return 85
        elif ratio >= 1.2:
            return 75
        elif ratio >= 1.0:
            return 65
        elif ratio >= 0.7:
            return 45
        else:
            return 25


class BacktestStrategyAdapter:
    """Wraps TradingStrategy to implement StrategyProtocol for BacktestEngine."""

    def __init__(self, strategy: TradingStrategy, strategy_config: dict):
        self.name = strategy.name
        self._strategy = strategy

        entry_params = (
            strategy_config.get("strategy", {})
            .get("entry", {})
            .get("params", {})
        )
        bb_period = entry_params.get("bb_period", 20)
        bb_std = entry_params.get("bb_std", 2.0)
        rsi_period = entry_params.get("rsi_period", 14)
        breakout_period = entry_params.get("breakout_period", 5)

        # Detect multi-timeframe requirements from strategy using normalized contract.
        self._indicator_contract = IndicatorContract.from_required_keys(
            strategy.required_indicators
        )
        mtf_timeframes = sorted(
            {
                req.timeframe.minutes
                for req in self._indicator_contract.momentum_requests
                if req.timeframe is not None
            }
        )

        self._indicator_engine = StreamingIndicatorEngine(
            bb_period=bb_period,
            bb_std=bb_std,
            rsi_period=rsi_period,
            mtf_timeframes=mtf_timeframes,
        )
        self._indicator_resolver = StreamingIndicatorResolver(
            engine=self._indicator_engine,
            required_keys=self._indicator_contract.required_keys,
        )
        self._loop = asyncio.new_event_loop()

        # Market data enricher for OVS / VA strategies
        self._enricher = _MarketDataEnricher(breakout_period=breakout_period)

        # Strategy name for conditional enrichment
        self._strategy_name = strategy.name

        # Position state for RL strategies (synced from BacktestEngine)
        self._current_position: dict[str, Any] | None = None

        # Pre-computed RL features (populated by precompute_rl_features)
        self._precomputed_rl_features: list[dict[str, float]] | None = None
        self._bar_index: int = 0

    def prescan_data(self, data: pd.DataFrame) -> None:
        """Pre-scan backtest data so enricher has prev_day_volume from day 2."""
        self._enricher.prescan(data)

    def precompute_rl_features(self, data: pd.DataFrame) -> None:
        """Vectorized RL feature pre-computation for entire backtest dataset.

        Computes all 25 RL features in one pass using RLFeatureCalculator,
        replacing per-bar derive_features_from_ohlcv() calls (~18ms each).
        Features are injected into indicators dict during on_bar()/check_exit(),
        taking priority in build_rl_observation()'s lookup chain.
        """
        from shared.ml.rl.features import RL_FEATURE_COLUMNS, RLFeatureCalculator

        calculator = RLFeatureCalculator()
        features_df = calculator.calculate(data)

        # Forward-fill NaN from warmup period, then fill remaining with neutral
        for col in RL_FEATURE_COLUMNS:
            if col in features_df.columns:
                features_df[col] = features_df[col].ffill()

        neutral = {
            col: (
                1.0
                if "ratio" in col
                else 50.0
                if col in ("rsi", "stoch_k", "stoch_d")
                else 0.5
                if col == "bb_position"
                else 0.0
            )
            for col in RL_FEATURE_COLUMNS
        }
        features_df = features_df.fillna(neutral)

        # Extract only RL feature columns as list of dicts
        self._precomputed_rl_features = (
            features_df[RL_FEATURE_COLUMNS].to_dict("records")
        )
        self._bar_index = 0
        logger.info(
            f"Pre-computed {len(self._precomputed_rl_features)} bars "
            f"of RL features ({len(RL_FEATURE_COLUMNS)} features each)"
        )

    def set_position(self, position: dict[str, Any] | None) -> None:
        """BacktestEngine → adapter position sync for RL context."""
        self._current_position = position

    def check_exit(self, bar: dict[str, Any]) -> tuple[bool, ExitReason | None]:
        """Check exit strategy for current position.

        Returns (should_exit, exit_reason) using the strategy's check_exit().
        Indicators are already cached from the preceding on_bar() call.
        """
        if not self._current_position:
            return (False, None)

        code = str(bar.get("code", "BACKTEST") or "BACKTEST")
        timestamp = bar.get("datetime", datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        # Use resolver so exit path follows the same indicator contract as live.
        indicators = self._indicator_resolver.collect_exit_indicators(code)
        for key, value in indicators.items():
            if key.startswith("momentum_"):
                bar[key] = value

        # Inject pre-computed RL features (one-bar lag: exit sees same bar as on_bar)
        if self._precomputed_rl_features is not None:
            idx = max(0, self._bar_index - 1)
            if idx < len(self._precomputed_rl_features):
                indicators.update(self._precomputed_rl_features[idx])

        # Build Position model from engine's position dict
        pos = self._current_position
        position = ModelPosition(
            id=f"bt_{code}",
            code=code,
            name=code,
            strategy=self.name,
            side=PositionSide.LONG if pos["side"] == "BUY" else PositionSide.SHORT,
            entry_price=pos["entry_price"],
            quantity=pos["quantity"],
            current_price=float(bar.get("close", 0) or 0),
        )

        context = ExitContext(
            position=position,
            market_data=bar,
            indicators=indicators,
            timestamp=timestamp,
            metadata={"is_backtest": True},
        )

        try:
            should_exit, exit_signal = self._loop.run_until_complete(
                self._strategy.check_exit(context)
            )
        except Exception:
            logger.debug("Exit strategy error", exc_info=True)
            return (False, None)

        if should_exit and exit_signal:
            # Map shared.models.signal.ExitReason → backtest ExitReason
            reason_value = exit_signal.reason.value
            try:
                return (True, ExitReason(reason_value))
            except ValueError:
                return (True, ExitReason.STRATEGY_EXIT)

        return (False, None)

    def on_bar(self, bar: dict[str, Any]) -> SignalType:
        """Convert a bar dict into a BUY/SELL/HOLD signal."""
        code = str(bar.get("code", "BACKTEST") or "BACKTEST")

        # Feed bar as a completed candle, extracting minute for MTF bucketing
        timestamp = bar.get("datetime", datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        minute = timestamp.hour * 100 + timestamp.minute

        # Enrich bar with derived market data (prev_day_volume, VWAP, etc.)
        # Must be called BEFORE seed_candles since it modifies bar["volume"]
        # to cumulative intraday volume for OVS strategy.
        # Keep original per-bar volume for indicator engine.
        original_volume = bar.get("volume", 0)
        self._enricher.enrich(bar, timestamp)
        bar_for_engine = dict(bar)
        bar_for_engine["volume"] = original_volume  # restore per-bar volume

        self._indicator_engine.seed_candles(code, [bar_for_engine], minute=minute)

        # Need warmup before generating signals
        if not self._indicator_engine.is_warm(code):
            return SignalType.HOLD

        indicators = self._indicator_resolver.collect_entry_indicators(code)

        # Inject pre-computed RL features (preferred for backtest throughput).
        # Prefix conflicting keys with "rl_" to avoid overwriting base indicators
        # (e.g. RL "atr" is normalized, base "atr" is raw).
        if self._precomputed_rl_features is not None:
            if self._bar_index < len(self._precomputed_rl_features):
                for k, v in self._precomputed_rl_features[self._bar_index].items():
                    if k in indicators:
                        indicators[f"rl_{k}"] = v
                    else:
                        indicators[k] = v
            self._bar_index += 1

        # Derive market_state from MFI using MarketClassifier (matches live orchestrator)
        mfi = indicators.get("mfi")
        if mfi is not None:
            from shared.strategy.market_classifier import MarketClassifier

            classifier = MarketClassifier()
            state = classifier.classify(mfi=mfi, adx=0.0)
            market_state = state.value
        else:
            market_state = "UNKNOWN"

        # Build metadata
        metadata: dict[str, Any] = {"market_state": market_state, "is_backtest": True}

        # Inject accumulation_candidates for volume_accumulation strategy
        if self._strategy_name == "volume_accumulation":
            # Use the raw code value from bar (may be int or str) as dict key,
            # since the strategy reads code = data.get("code") with the same type.
            raw_code = bar.get("code", code)
            score = self._enricher.compute_accumulation_score(str(raw_code))
            metadata["accumulation_candidates"] = {raw_code: score}

        # Build position list for RL action masks + observation
        current_positions = []
        if self._current_position:
            pos = self._current_position
            current_positions = [
                ModelPosition(
                    id=f"bt_{code}",
                    code=code,
                    name=code,
                    strategy=self.name,
                    side=(
                        PositionSide.LONG
                        if pos["side"] == "BUY"
                        else PositionSide.SHORT
                    ),
                    entry_price=pos["entry_price"],
                    quantity=pos["quantity"],
                    current_price=float(bar.get("close", 0) or 0),
                )
            ]

        context = EntryContext(
            market_data=bar,
            indicators=indicators,
            current_positions=current_positions,
            timestamp=timestamp,
            metadata=metadata,
        )

        try:
            signal = self._loop.run_until_complete(
                self._strategy.check_entry(context)
            )
        except Exception:
            logger.debug("Entry generator error", exc_info=True)
            return SignalType.HOLD

        if signal is None:
            return SignalType.HOLD

        direction = signal.metadata.get("signal_direction", "long")
        if direction == "long":
            return SignalType.BUY
        elif direction == "short":
            return SignalType.SELL

        return SignalType.HOLD
