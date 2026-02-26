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
            rl_feats = self.engine.get_rl_features(symbol)
            if rl_feats:
                # Prefix RL features to avoid overwriting base indicators
                # (e.g. RL "atr" is normalized, base "atr" is raw)
                for k, v in rl_feats.items():
                    if k in result:
                        result[f"rl_{k}"] = v
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

        return result

    def collect_exit_indicators(self, symbol: str) -> dict[str, Any]:
        """Collect indicator payload for exit evaluation.

        Keeps current behavior (base + rl + momentum if declared) without
        inferring additional hidden requirements.
        """
        result = self.collect_entry_indicators(symbol)

        # Exit paths often benefit from RL features even when ohlcv is absent.
        # Keep this optional and additive to avoid behavior regressions.
        if "ohlcv" not in result:
            rl_feats = self.engine.get_rl_features(symbol)
            if rl_feats:
                for k, v in rl_feats.items():
                    if k in result:
                        result[f"rl_{k}"] = v
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
