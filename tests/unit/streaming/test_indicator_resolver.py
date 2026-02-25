from __future__ import annotations

from shared.indicators.resolver import StreamingIndicatorResolver


class _FakeEngine:
    def __init__(self, *, rl_features: dict | None = None, ohlcv: list | None = None):
        self._rl_features = rl_features or {}
        self._ohlcv = ohlcv or []
        self.momentum_timeframes: list[int] = []

    def get_indicators(self, symbol: str) -> dict:
        return {"rsi": 55.0, "symbol": symbol}

    def get_rl_features(self, symbol: str) -> dict:
        return dict(self._rl_features)

    def get_recent_candles(self, symbol: str, limit: int = 240) -> list:
        _ = limit
        return list(self._ohlcv)

    def get_momentum_indicators(self, symbol: str, timeframe: int = 5) -> dict:
        _ = symbol
        self.momentum_timeframes.append(timeframe)
        return {"trix": float(timeframe)}


def test_collect_entry_indicators_uses_rl_and_multi_timeframe_momentum():
    engine = _FakeEngine(rl_features={"rl_score": 0.7})
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=["rsi", "ohlcv", "momentum_5m", "momentum_1h"],
    )

    indicators = resolver.collect_entry_indicators("005930")

    assert indicators["rsi"] == 55.0
    assert indicators["rl_score"] == 0.7
    assert "ohlcv" not in indicators
    assert indicators["momentum_5m"]["trix"] == 5.0
    assert indicators["momentum_1h"]["trix"] == 60.0
    assert engine.momentum_timeframes == [5, 60]
    assert resolver.timeframes == (5, 60)


def test_collect_entry_indicators_falls_back_to_ohlcv_without_rl_features():
    engine = _FakeEngine(rl_features={}, ohlcv=[{"close": 100.0}])
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=["ohlcv"],
    )

    indicators = resolver.collect_entry_indicators("005930")

    assert "ohlcv" in indicators
    assert indicators["ohlcv"] == [{"close": 100.0}]


def test_collect_exit_indicators_adds_rl_features_even_without_ohlcv_requirement():
    engine = _FakeEngine(rl_features={"rl_score": 0.5})
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=["rsi"],
    )

    indicators = resolver.collect_exit_indicators("005930")

    assert indicators["rsi"] == 55.0
    assert indicators["rl_score"] == 0.5
