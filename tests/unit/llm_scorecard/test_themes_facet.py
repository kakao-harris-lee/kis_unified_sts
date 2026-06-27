"""Tests for ThemesFacet (Task 10)."""
from __future__ import annotations

from datetime import datetime

from shared.llm_scorecard.facets.base import CaptureContext, FacetPrediction
from shared.llm_scorecard.facets.themes import ThemesFacet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_facet(theme_symbols=None, top_n=2):
    """Return a ThemesFacet with explicit params (bypasses config file)."""
    ts = theme_symbols or {
        "Technology": ["005930", "000660"],
        "Finance": ["055550", "086790"],
        "Energy": ["010950"],
    }
    return ThemesFacet(top_n=top_n, theme_symbols=ts)


def _ctx(sector_rotation=None):
    return CaptureContext(
        date_kst="2026-06-25",
        now_kst=datetime(2026, 6, 25, 8, 40),
        market_context={
            "sector_rotation": sector_rotation or {
                "Technology": "INFLOW",
                "Finance": "OUTFLOW",
                "Energy": "INFLOW",
            }
        },
    )


class _FakeOD:
    """Fake OutcomeData returning per-symbol session returns."""

    def __init__(self, returns: dict[str, float | None]):
        self._returns = returns

    def session_return(self, symbol, date_kst, captured_at):
        return self._returns.get(symbol)


# ---------------------------------------------------------------------------
# Capture tests
# ---------------------------------------------------------------------------

def test_capture_extracts_strong_themes():
    f = _make_facet(top_n=2)
    ctx = _ctx(sector_rotation={"Technology": "INFLOW", "Finance": "OUTFLOW", "Energy": "INFLOW"})
    pred = f.capture(ctx)
    assert pred is not None
    assert pred.facet == "themes"
    # strong = INFLOW themes (Technology, Energy) — only top 2
    assert set(pred.payload["strong_themes"]) == {"Technology", "Energy"}
    # constituent symbols
    assert set(pred.payload["strong_symbols"]) == {"005930", "000660", "010950"}


def test_capture_returns_none_when_no_market_context():
    f = _make_facet()
    ctx = CaptureContext(date_kst="2026-06-25", now_kst=datetime(2026, 6, 25, 8, 40))
    assert f.capture(ctx) is None


def test_capture_returns_none_when_no_sector_rotation():
    f = _make_facet()
    ctx = CaptureContext(
        date_kst="2026-06-25",
        now_kst=datetime(2026, 6, 25, 8, 40),
        market_context={"overall_signal": "BULLISH"},
    )
    assert f.capture(ctx) is None


def test_capture_returns_none_when_no_strong_themes():
    """When all themes are OUTFLOW, there are no strong-theme symbols."""
    f = _make_facet()
    ctx = _ctx(sector_rotation={"Technology": "OUTFLOW", "Finance": "OUTFLOW"})
    assert f.capture(ctx) is None


# ---------------------------------------------------------------------------
# Score tests
# ---------------------------------------------------------------------------

def _make_pred(strong_themes=None, strong_symbols=None):
    return FacetPrediction(
        facet="themes",
        date_kst="2026-06-25",
        captured_at=datetime(2026, 6, 25, 8, 40),
        payload={
            "strong_themes": strong_themes or ["Technology", "Energy"],
            "strong_symbols": strong_symbols or ["005930", "000660", "010950"],
        },
        confidence=None,
    )


def test_score_value_is_strong_mean_baseline_is_market_mean():
    """value = strong_mean; baseline_value = market_mean; edge = spread = value - baseline."""
    f = _make_facet()
    pred = _make_pred(strong_symbols=["005930", "000660", "010950"])
    # strong symbols: 005930=+2%, 000660=+4%, 010950=+6%  → strong_mean=4.0
    # Finance symbols (055550, 086790) return None → excluded from market mean
    # market_mean = mean of scorable = (2+4+6)/3 = 4.0
    od = _FakeOD({"005930": 2.0, "000660": 4.0, "010950": 6.0, "055550": None, "086790": None})
    s = f.score(pred, od)
    assert s.facet == "themes"
    assert isinstance(s.value, float)
    # value = strong_mean, baseline_value = market_mean, edge = value - baseline_value
    assert abs(s.value - 4.0) < 1e-9
    assert abs(s.baseline_value - 4.0) < 1e-9
    assert abs(s.edge - (s.value - s.baseline_value)) < 1e-9


def test_score_correct_when_spread_positive():
    f = _make_facet()
    pred = _make_pred(strong_symbols=["005930"])  # one strong symbol
    # strong: 005930=+5%  other symbols (Finance) = +1%
    od = _FakeOD({"005930": 5.0, "055550": 1.0, "086790": 1.0})
    s = f.score(pred, od)
    # strong_mean = 5.0; market_mean includes strong+others = (5+1+1)/3 ≈ 2.33
    # spread = 5.0 - 2.33 = 2.67 > 0 → correct=True; edge > 0
    assert s.correct is True
    assert s.edge > 0


def test_score_correct_false_when_spread_negative():
    f = _make_facet()
    pred = _make_pred(strong_symbols=["005930"])
    # strong underperforms rest
    od = _FakeOD({"005930": 0.5, "055550": 3.0, "086790": 3.0})
    s = f.score(pred, od)
    # strong_mean=0.5; market_mean=(0.5+3+3)/3=2.17; spread=0.5-2.17=-1.67 → correct=False; edge<0
    assert s.correct is False
    assert s.edge < 0


def test_score_correct_false_when_spread_zero():
    """Strict boundary: spread == 0 is a MISS (correct False), not a hit."""
    f = _make_facet()
    pred = _make_pred(strong_symbols=["005930", "000660", "010950"])
    # strong = whole scorable universe → strong_mean == market_mean → spread == 0
    od = _FakeOD({"005930": 2.0, "000660": 4.0, "010950": 6.0, "055550": None, "086790": None})
    s = f.score(pred, od)
    assert abs(s.edge) < 1e-9  # spread == 0
    assert s.correct is False


def test_baseline_returns_market_mean():
    """baseline() computes the equal-weight market mean (== score baseline_value)."""
    f = _make_facet()
    pred = _make_pred(strong_symbols=["005930"])
    od = _FakeOD({"005930": 5.0, "055550": 1.0, "086790": 1.0})  # mean=(5+1+1)/3
    base = f.baseline(pred, od)
    s = f.score(pred, od)
    assert abs(base - 7.0 / 3.0) < 1e-9
    assert abs(base - s.baseline_value) < 1e-9  # single source of truth


def test_score_unscorable_when_no_symbol_data():
    f = _make_facet()
    pred = _make_pred(strong_symbols=["005930", "000660", "010950"])
    od = _FakeOD({})  # all None
    s = f.score(pred, od)
    assert s.correct is None
    assert s.value == 0.0
    assert s.edge == 0.0
    assert s.baseline_value == 0.0  # no market data either → 0.0


def test_score_unscorable_carries_market_mean_from_non_strong_symbols():
    """Strong symbols have no data, but non-strong (market) symbols do → carry market mean."""
    f = _make_facet()
    pred = _make_pred(strong_symbols=["005930", "000660"])  # both None below
    od = _FakeOD({"005930": None, "000660": None, "055550": 2.0, "086790": 4.0})
    s = f.score(pred, od)
    assert s.correct is None  # no strong-theme data → unscorable
    assert abs(s.baseline_value - 3.0) < 1e-9  # market mean (2+4)/2 = 3.0


def test_score_economic_proxy_equals_value():
    """economic_proxy mirrors value (strong_mean is the PnL proxy)."""
    f = _make_facet()
    pred = _make_pred(strong_symbols=["005930"])
    od = _FakeOD({"005930": 3.0, "055550": 1.0, "086790": 1.0})
    s = f.score(pred, od)
    assert s.economic_proxy == s.value  # both = strong_mean
