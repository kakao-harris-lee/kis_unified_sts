"""F2: futures flow catalyst re-pointed off the always-None foreign_futures_5d.

``FuturesAnalysisMixin`` gated the '외국인 순매수' deterministic catalyst on
``foreign_futures_5d`` — a field the flow collector never sources — so the
catalyst could never appear even after P5-2 wired the foreign flow. These tests
pin the re-point onto the live 20-day cumulative (``foreign_futures_cum20``) with
a config-driven threshold, graceful None handling, and that the catalyst/risk
helpers (previously broken by a missing ``self`` / ``@staticmethod``) now run.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.llm.config import LLMConfig
from shared.llm.unified_trading_futures import FuturesAnalysisMixin


@dataclass
class _Flow:
    foreign_futures: float | None = None
    foreign_futures_5d: float | None = None
    foreign_futures_cum20: float | None = None
    basis: float | None = None
    microstructure_score: float | None = None


class _Analyzer(FuturesAnalysisMixin):
    def __init__(self, config: LLMConfig) -> None:
        self.config = config


def _analyzer(**cfg) -> _Analyzer:
    return _Analyzer(LLMConfig(krx_api_key="", **cfg))


# --------------------------------------------------------------------------- #
# _append_flow_catalysts — direct (static helper)
# --------------------------------------------------------------------------- #
def test_catalyst_fires_when_cum20_exceeds_threshold():
    cats: list[str] = []
    FuturesAnalysisMixin._append_flow_catalysts(
        _Flow(foreign_futures_cum20=60000.0), cats, 50000.0
    )
    assert len(cats) == 1
    assert "20일 누적 순매수" in cats[0]
    assert "60,000" in cats[0]


def test_catalyst_silent_at_or_below_threshold():
    cats: list[str] = []
    FuturesAnalysisMixin._append_flow_catalysts(
        _Flow(foreign_futures_cum20=50000.0), cats, 50000.0
    )
    assert cats == []


def test_catalyst_silent_when_cum20_none():
    # No market:structure source → cum20 None → graceful (no catalyst, no crash).
    cats: list[str] = []
    FuturesAnalysisMixin._append_flow_catalysts(
        _Flow(foreign_futures_cum20=None), cats, 50000.0
    )
    assert cats == []


def test_catalyst_ignores_legacy_foreign_futures_5d():
    # Even a huge legacy 5d value must NOT drive the catalyst (dead field).
    cats: list[str] = []
    FuturesAnalysisMixin._append_flow_catalysts(
        _Flow(foreign_futures_5d=999999.0, foreign_futures_cum20=None), cats, 50000.0
    )
    assert cats == []


def test_basis_catalyst_unchanged():
    # The basis (선물 저평가) catalyst is untouched by the re-point.
    cats: list[str] = []
    FuturesAnalysisMixin._append_flow_catalysts(
        _Flow(foreign_futures_cum20=None, basis=-2.0), cats, 50000.0
    )
    assert any("선물 저평가" in c for c in cats)


# --------------------------------------------------------------------------- #
# _build_futures_catalysts_and_risks — end-to-end (path no longer TypeErrors)
# --------------------------------------------------------------------------- #
def test_catalyst_path_runs_end_to_end_and_is_config_driven():
    analyzer = _analyzer(futures_flow_foreign_catalyst_cum20_threshold=40000.0)
    catalysts, risks = analyzer._build_futures_catalysts_and_risks(
        global_data=None,
        flow_data=_Flow(foreign_futures_cum20=45000.0),
        high_events=[],
        technical=None,
        missing_sources=[],
    )
    assert any("20일 누적 순매수" in c for c in catalysts)  # 45000 > 40000 fires
    assert isinstance(risks, list)


def test_catalyst_path_respects_higher_threshold():
    analyzer = _analyzer(futures_flow_foreign_catalyst_cum20_threshold=60000.0)
    catalysts, _risks = analyzer._build_futures_catalysts_and_risks(
        global_data=None,
        flow_data=_Flow(foreign_futures_cum20=45000.0),
        high_events=[],
        technical=None,
        missing_sources=[],
    )
    assert catalysts == []  # 45000 < 60000 → no catalyst
