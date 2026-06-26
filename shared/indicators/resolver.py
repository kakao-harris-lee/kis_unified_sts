"""Indicator resolver for live/backtest orchestration.

The resolver centralizes how indicator requirements are translated into
StreamingIndicatorEngine calls. This removes per-call ad-hoc conditionals
in orchestrator/backtest paths and makes timeframe expansion predictable.
"""

from __future__ import annotations

from typing import Any

from shared.indicators.contracts import IndicatorContract, IndicatorKind


class StreamingIndicatorResolver:
    """Resolve required indicator keys against a StreamingIndicatorEngine."""

    def __init__(
        self,
        *,
        engine: Any,
        required_keys: list[str] | tuple[str, ...],
    ) -> None:
        self.engine = engine
        self.contract = IndicatorContract.from_required_keys(required_keys)

    def collect_entry_indicators(self, symbol: str) -> dict[str, Any]:
        """Collect indicator payload for entry evaluation."""
        result: dict[str, Any] = {}

        base = self.engine.get_indicators(symbol)
        if base:
            result.update(base)

        if self.contract.needs_ohlcv:
            features = self.engine.get_indicator_features(symbol)
            if features:
                # Prefix feature bundle values to avoid overwriting base
                # indicators (e.g. normalized "atr" vs raw "atr").
                for k, v in features.items():
                    if k in result:
                        result[f"feature_{k}"] = v
                    else:
                        result[k] = v
            else:
                ohlcv = self.engine.get_recent_candles(symbol, limit=240)
                if ohlcv:
                    result["ohlcv"] = ohlcv

        for req in self.contract.momentum_requests:
            timeframe = req.timeframe.minutes if req.timeframe else 5
            momentum = self.engine.get_momentum_indicators(symbol, timeframe=timeframe)
            if momentum:
                result[req.key] = momentum

        for req in self.contract.mtf_base_requests:
            tf = req.timeframe.minutes if req.timeframe else 15
            tf_base = self.engine.get_indicators_tf(symbol, tf)
            if tf_base:
                # Higher-TF BB/RSI replace the 1m base under the same
                # plain keys so mean_reversion.generate() is unchanged.
                result.update(tf_base)

        # Post-event trading-range high/low (Setup C's N-minute breakout range).
        # The orchestrator entry path otherwise never populates these keys, so
        # the decision-engine MarketContext defaults both to current_price and
        # Setup C's strict ``current_price > last_15min_high`` breakout becomes
        # unreachable live (backtest/live parity break). Fulfil it here from the
        # live candle history — ``get_recent_range`` reads only COMPLETED candles,
        # i.e. the causal ``[now-N, now-1]`` window (current bar excluded), which
        # matches MarketContextReplay's ``highs[i-N:i]`` backtest window.
        range_minutes = self.contract.recent_range_minutes
        if range_minutes is not None:
            get_recent_range = getattr(self.engine, "get_recent_range", None)
            if callable(get_recent_range):
                rng = get_recent_range(symbol, range_minutes)
                if rng is not None:
                    high, low = rng
                    result[f"last_{range_minutes}min_high"] = float(high)
                    result[f"last_{range_minutes}min_low"] = float(low)

        return result

    def collect_exit_indicators(self, symbol: str) -> dict[str, Any]:
        """Collect indicator payload for exit evaluation.

        Keeps current behavior (base + feature bundle + momentum if declared) without
        inferring additional hidden requirements.
        """
        result = self.collect_entry_indicators(symbol)

        # Exit paths often benefit from indicator features even when ohlcv is absent.
        # Keep this optional and additive to avoid behavior regressions.
        if "ohlcv" not in result:
            features = self.engine.get_indicator_features(symbol)
            if features:
                for k, v in features.items():
                    if k in result:
                        result[f"feature_{k}"] = v
                    else:
                        result[k] = v
        return result

    @property
    def required_keys(self) -> tuple[str, ...]:
        return self.contract.required_keys

    @property
    def timeframes(self) -> tuple[int, ...]:
        frames = sorted(
            {
                req.timeframe.minutes
                for req in self.contract.requests
                if req.kind == IndicatorKind.MOMENTUM and req.timeframe is not None
            }
        )
        return tuple(frames)
