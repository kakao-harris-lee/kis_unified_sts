"""P6-a: FuturesAnalysisMixin staticmethod regression (096d22f2).

Refactor 096d22f2 ("Refactor LLM analysis modules by responsibility") dropped the
``@staticmethod`` decorator (and ``self`` parameter) from two pure helpers on
``FuturesAnalysisMixin`` while their call sites stayed instance-bound:

  * ``_determine_futures_bias(overall_score)`` — called at ``_analyze_futures``
    as ``self._determine_futures_bias(overall_score)``.
  * ``_build_futures_analysis_data(overall_score, ...)`` — called as
    ``self._build_futures_analysis_data(...)``.

Because both are plain functions (no ``self``, no ``@staticmethod``), an
*instance-bound* call binds ``self`` as the first positional argument, so
``self._determine_futures_bias(x)`` passes two positionals to a one-arg function
=> ``TypeError: ... takes 1 positional argument but 2 were given``. The live
consumer ``UnifiedTradingAnalyzer._analyze_futures`` therefore crashed on the
first real invocation. The prior suite only exercised the *static* helpers, so
the instance path was uncovered — these tests close that gap by driving every
call **through an instance** (``analyzer.<method>(...)``), the exact shape that
regressed.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.llm.config import LLMConfig
from shared.llm.data_classes import MarketBias
from shared.llm.errors import DataUnavailableError
from shared.llm.unified_trading_futures import FuturesAnalysisMixin


@dataclass
class _Event:
    event: str = "evt"
    importance: str = "낮음"


class _Analyzer(FuturesAnalysisMixin):
    """Minimal mixin host — mirrors the pattern in test_futures_flow_catalyst."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config


def _analyzer(**cfg) -> _Analyzer:
    return _Analyzer(LLMConfig(krx_api_key="", **cfg))


# --------------------------------------------------------------------------- #
# _determine_futures_bias — instance-bound (regressed call shape)
# --------------------------------------------------------------------------- #
def test_determine_bias_instance_bound_does_not_typeerror():
    # Before the fix this raised TypeError (self bound as 1st positional).
    analyzer = _analyzer()
    assert analyzer._determine_futures_bias(0.0) is MarketBias.NEUTRAL


def test_determine_bias_thresholds_via_instance():
    analyzer = _analyzer()
    # Hand-computed against the >=30 / >=15 / <=-30 / <=-15 ladder.
    assert analyzer._determine_futures_bias(35.0) is MarketBias.STRONG_BULLISH
    assert (
        analyzer._determine_futures_bias(30.0) is MarketBias.STRONG_BULLISH
    )  # boundary
    assert analyzer._determine_futures_bias(20.0) is MarketBias.BULLISH
    assert analyzer._determine_futures_bias(15.0) is MarketBias.BULLISH  # boundary
    assert analyzer._determine_futures_bias(14.9) is MarketBias.NEUTRAL
    assert analyzer._determine_futures_bias(-14.9) is MarketBias.NEUTRAL
    assert analyzer._determine_futures_bias(-15.0) is MarketBias.BEARISH  # boundary
    assert analyzer._determine_futures_bias(-20.0) is MarketBias.BEARISH
    assert (
        analyzer._determine_futures_bias(-30.0) is MarketBias.STRONG_BEARISH
    )  # boundary
    assert analyzer._determine_futures_bias(-35.0) is MarketBias.STRONG_BEARISH


# --------------------------------------------------------------------------- #
# _build_futures_analysis_data — instance-bound (regressed call shape)
# --------------------------------------------------------------------------- #
def test_build_analysis_data_instance_bound_shape_and_values():
    analyzer = _analyzer()
    data = analyzer._build_futures_analysis_data(
        35.678,
        MarketBias.STRONG_BULLISH,
        None,  # global_data
        None,  # flow_data
        {"score": 5, "rsi": 55},  # technical
        [],  # events
        ["futures_global"],  # missing_sources
    )
    # Hand-computed expectations.
    assert data["overall_score"] == 35.7  # round(35.678, 1)
    assert data["overall_bias"] == "강세"  # MarketBias.STRONG_BULLISH.value
    assert data["global"] is None
    assert data["flow"] is None
    assert data["technical"] == {"score": 5, "rsi": 55}
    assert data["events"] == []
    assert data["missing_sources"] == ["futures_global"]


def test_build_analysis_data_truncates_events_to_five():
    analyzer = _analyzer()
    events = [_Event(event=f"e{i}") for i in range(7)]
    data = analyzer._build_futures_analysis_data(
        0.0, MarketBias.NEUTRAL, None, None, None, events, []
    )
    # events[:5] → exactly five asdict()-ed dicts.
    assert len(data["events"]) == 5
    assert [e["event"] for e in data["events"]] == ["e0", "e1", "e2", "e3", "e4"]


# --------------------------------------------------------------------------- #
# _analyze_futures — end-to-end (drives the exact regressed call sites)
# --------------------------------------------------------------------------- #
class _RaisingSource:
    """Collector/analyzer stub whose collect()/analyze() signal 'unavailable'."""

    def __init__(self, source: str) -> None:
        self._source = source

    def collect(self):
        raise DataUnavailableError(self._source)

    def analyze(self):
        raise DataUnavailableError(self._source)


class _E2EAnalyzer(FuturesAnalysisMixin):
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.futures_global_collector = _RaisingSource("futures_global")
        self.futures_event_collector = _RaisingSource("futures_events")
        self.futures_flow_collector = _RaisingSource("futures_flow")
        self.futures_tech_analyzer = _RaisingSource("futures_technical")


async def test_analyze_futures_runs_without_typeerror():
    # Drives ``self._determine_futures_bias(...)`` and
    # ``self._build_futures_analysis_data(...)`` — the two crash sites. With all
    # sources unavailable: score→0.0, bias→NEUTRAL, technical→None (plan None).
    analyzer = _E2EAnalyzer(LLMConfig(krx_api_key=""))
    plan, analysis_data = await analyzer._analyze_futures()

    assert plan is None  # technical unavailable → no plan
    assert analysis_data["overall_score"] == 0.0
    assert analysis_data["overall_bias"] == MarketBias.NEUTRAL.value  # "중립"
    assert analysis_data["global"] is None
    assert analysis_data["flow"] is None
    # Every source failed → each recorded in missing_sources.
    assert analysis_data["missing_sources"]
