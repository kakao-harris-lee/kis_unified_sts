from shared.indicators.contracts import IndicatorContract
from shared.indicators.resolver import StreamingIndicatorResolver


class _FakeEngine:
    def __init__(self):
        self.last_tf = None

    def get_indicators(self, _symbol):
        return {
            "bb_lower": 1.0,
            "bb_middle": 2.0,
            "bb_upper": 3.0,
            "rsi": 10.0,
            "vwap": 99.0,
        }

    def get_indicators_tf(self, _symbol, timeframe):
        self.last_tf = timeframe
        return {"bb_lower": 11.0, "bb_middle": 12.0, "bb_upper": 13.0, "rsi": 55.0}

    def get_indicator_features(self, _symbol):
        return {}

    def get_recent_candles(self, _symbol, limit=240):  # noqa: ARG002
        return []

    def get_momentum_indicators(self, _symbol, timeframe=5):  # noqa: ARG002
        return {}


def test_mtf_base_overrides_1m_base_for_bb_and_rsi():
    engine = _FakeEngine()
    r = StreamingIndicatorResolver(
        engine=engine,
        required_keys=[
            "bb_lower",
            "bb_upper",
            "bb_middle",
            "rsi",
            "vwap",
            "mtf_base_15m",
        ],
    )
    out = r.collect_entry_indicators("101S6000")
    assert engine.last_tf == 15  # resolver dispatched the 15m timeframe
    assert out["bb_lower"] == 11.0 and out["bb_middle"] == 12.0
    assert out["bb_upper"] == 13.0 and out["rsi"] == 55.0
    assert out["vwap"] == 99.0  # non-overlapping 1m key survives


def test_no_mtf_base_keeps_1m_base_unchanged():
    r = StreamingIndicatorResolver(
        engine=_FakeEngine(),
        required_keys=["bb_lower", "rsi"],
    )
    out = r.collect_entry_indicators("X")
    assert out["bb_lower"] == 1.0 and out["rsi"] == 10.0


def test_mtf_base_engine_returns_empty_keeps_1m_base():
    """Warmup window: engine has insufficient 15m bars -> {} -> 1m base retained."""

    class _EmptyTfEngine(_FakeEngine):
        def get_indicators_tf(self, _symbol, _timeframe):
            return {}

    r = StreamingIndicatorResolver(
        engine=_EmptyTfEngine(),
        required_keys=["bb_lower", "rsi", "mtf_base_15m"],
    )
    out = r.collect_entry_indicators("101S6000")
    assert out["bb_lower"] == 1.0  # 1m base retained
    assert out["rsi"] == 10.0


def test_contract_mtf_base_timeframes_for_adapter():
    c = IndicatorContract.from_required_keys(["bb_lower", "rsi", "mtf_base_15m"])
    tfs = sorted(
        {r.timeframe.minutes for r in c.mtf_base_requests if r.timeframe is not None}
    )
    assert tfs == [15]
