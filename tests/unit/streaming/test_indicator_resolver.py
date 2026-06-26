from __future__ import annotations

from shared.indicators.resolver import StreamingIndicatorResolver


class _FakeEngine:
    def __init__(
        self, *, indicator_features: dict | None = None, ohlcv: list | None = None
    ):
        self._indicator_features = indicator_features or {}
        self._ohlcv = ohlcv or []
        self.momentum_timeframes: list[int] = []

    def get_indicators(self, symbol: str) -> dict:
        return {"rsi": 55.0, "symbol": symbol}

    def get_indicator_features(self, symbol: str) -> dict:
        return dict(self._indicator_features)

    def get_recent_candles(self, symbol: str, limit: int = 240) -> list:
        _ = limit
        return list(self._ohlcv)

    def get_momentum_indicators(self, symbol: str, timeframe: int = 5) -> dict:
        _ = symbol
        self.momentum_timeframes.append(timeframe)
        return {"trix": float(timeframe)}


def test_collect_entry_indicators_uses_features_and_multi_timeframe_momentum():
    engine = _FakeEngine(indicator_features={"feature_score": 0.7})
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=["rsi", "ohlcv", "momentum_5m", "momentum_1h"],
    )

    indicators = resolver.collect_entry_indicators("005930")

    assert indicators["rsi"] == 55.0
    assert indicators["feature_score"] == 0.7
    assert "ohlcv" not in indicators
    assert indicators["momentum_5m"]["trix"] == 5.0
    assert indicators["momentum_1h"]["trix"] == 60.0
    assert engine.momentum_timeframes == [5, 60]
    assert resolver.timeframes == (5, 60)


def test_collect_entry_indicators_falls_back_to_ohlcv_without_features():
    engine = _FakeEngine(indicator_features={}, ohlcv=[{"close": 100.0}])
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=["ohlcv"],
    )

    indicators = resolver.collect_entry_indicators("005930")

    assert "ohlcv" in indicators
    assert indicators["ohlcv"] == [{"close": 100.0}]


def test_collect_exit_indicators_adds_features_even_without_ohlcv_requirement():
    engine = _FakeEngine(indicator_features={"feature_score": 0.5})
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=["rsi"],
    )

    indicators = resolver.collect_exit_indicators("005930")

    assert indicators["rsi"] == 55.0
    assert indicators["feature_score"] == 0.5


class _RangeEngine(_FakeEngine):
    """Fake engine that also exposes ``get_recent_range`` (Setup C wiring)."""

    def __init__(self, *, recent_range: tuple[float, float] | None = (100.0, 99.0)):
        super().__init__()
        self._recent_range = recent_range
        self.range_calls: list[tuple[str, int]] = []

    def get_recent_range(self, symbol: str, minutes: int = 15):
        self.range_calls.append((symbol, minutes))
        return self._recent_range


def test_collect_entry_indicators_injects_recent_range_for_setup_c():
    """Setup C's ``last_15min_high/low`` are fulfilled from ``get_recent_range``.

    Without this the orchestrator entry context never carries the 15-min range
    and Setup C's strict ``current_price > last_15min_high`` breakout is
    unreachable live (backtest/live parity break).
    """
    engine = _RangeEngine(recent_range=(100.0, 99.0))
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=["atr", "last_15min_high", "last_15min_low"],
    )

    indicators = resolver.collect_entry_indicators("A05603")

    assert indicators["last_15min_high"] == 100.0
    assert indicators["last_15min_low"] == 99.0
    # Window derived from the key name, not a hardcoded constant.
    assert engine.range_calls == [("A05603", 15)]


def test_collect_entry_indicators_skips_recent_range_when_engine_lacks_method():
    """No ``get_recent_range`` → range keys are simply absent (no crash)."""
    engine = _FakeEngine()  # base fake has no get_recent_range
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=["atr", "last_15min_high", "last_15min_low"],
    )

    indicators = resolver.collect_entry_indicators("A05603")

    assert "last_15min_high" not in indicators
    assert "last_15min_low" not in indicators


def test_collect_entry_indicators_skips_recent_range_when_history_empty():
    """``get_recent_range`` returning None (cold symbol) injects nothing."""
    engine = _RangeEngine(recent_range=None)
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=["atr", "last_15min_high", "last_15min_low"],
    )

    indicators = resolver.collect_entry_indicators("A05603")

    assert "last_15min_high" not in indicators
    assert "last_15min_low" not in indicators


def test_collect_entry_indicators_no_range_call_when_keys_not_required():
    """Strategies without range keys never trigger a get_recent_range call."""
    engine = _RangeEngine(recent_range=(100.0, 99.0))
    resolver = StreamingIndicatorResolver(
        engine=engine,
        required_keys=["rsi"],
    )

    indicators = resolver.collect_entry_indicators("A05603")

    assert engine.range_calls == []
    assert "last_15min_high" not in indicators
