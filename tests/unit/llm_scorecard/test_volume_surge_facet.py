"""Tests for VolumeSurgeFacet (Task 12).

NOTE: No clean per-symbol surge-with-timestamp Redis feed exists in the repo.
The facet reads from ctx.screener["volume_surge"] — a list of
{code, flag_time, flag_price} dicts.  capture() returns None when absent.
A hook to populate this must be added in a future task.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from shared.llm_scorecard.facets.base import CaptureContext, FacetPrediction
from shared.llm_scorecard.facets.volume_surge import VolumeSurgeFacet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FLAG_TIME = "2026-06-25T09:05:00"
_FLAG_TIME_DT = datetime(2026, 6, 25, 9, 5, 0)
_CAP_AT = datetime(2026, 6, 25, 8, 40)


def _make_facet(base_rate=0.0):
    return VolumeSurgeFacet(base_rate=base_rate)


def _ctx(volume_surge=None):
    screener = {"volume_surge": volume_surge} if volume_surge is not None else None
    return CaptureContext(
        date_kst="2026-06-25",
        now_kst=_CAP_AT,
        screener=screener,
    )


def _surge_items(*codes):
    return [
        {"code": c, "flag_time": _FLAG_TIME, "flag_price": 10000.0} for c in codes
    ]


class _FakeBarsOD:
    """Fake OutcomeData with bars_after returning a small DataFrame."""

    def __init__(self, per_code: dict[str, pd.DataFrame | None]):
        self._data = per_code

    def bars_after(self, symbol, date_kst, after):
        df = self._data.get(symbol)
        if df is None or df.empty:
            return None
        return df[df.index >= after]


def _make_bars(open_: float, close: float) -> pd.DataFrame:
    idx = pd.to_datetime([_FLAG_TIME, "2026-06-25T15:20:00"])
    return pd.DataFrame({"open": [open_, open_], "close": [open_, close]}, index=idx)


# ---------------------------------------------------------------------------
# Capture tests
# ---------------------------------------------------------------------------

def test_capture_reads_surge_items_from_screener():
    ctx = _ctx(volume_surge=_surge_items("005930", "000660"))
    f = _make_facet()
    pred = f.capture(ctx)
    assert pred is not None
    assert pred.facet == "volume_surge"
    codes = [item["code"] for item in pred.payload["surges"]]
    assert set(codes) == {"005930", "000660"}


def test_capture_returns_none_when_screener_absent():
    assert _make_facet().capture(_ctx(volume_surge=None)) is None


def test_capture_returns_none_when_volume_surge_key_absent():
    ctx = CaptureContext(
        date_kst="2026-06-25",
        now_kst=_CAP_AT,
        screener={"codes": ["005930"]},  # no volume_surge key
    )
    assert _make_facet().capture(ctx) is None


def test_capture_returns_none_when_surge_list_empty():
    assert _make_facet().capture(_ctx(volume_surge=[])) is None


def test_capture_stores_flag_time_and_price():
    ctx = _ctx(volume_surge=[{"code": "005930", "flag_time": _FLAG_TIME, "flag_price": 9500.0}])
    pred = _make_facet().capture(ctx)
    assert pred is not None
    surge = pred.payload["surges"][0]
    assert surge["flag_time"] == _FLAG_TIME
    assert surge["flag_price"] == 9500.0


# ---------------------------------------------------------------------------
# Score tests
# ---------------------------------------------------------------------------

def _make_pred(surges=None):
    return FacetPrediction(
        facet="volume_surge",
        date_kst="2026-06-25",
        captured_at=_CAP_AT,
        payload={"surges": surges or _surge_items("005930", "000660")},
        confidence=None,
    )


def test_score_value_is_mean_flag_to_close_return():
    f = _make_facet(base_rate=0.0)
    pred = _make_pred(surges=_surge_items("005930", "000660"))
    # 005930: flag_time bar open=100, close=105  → +5%
    # 000660: flag_time bar open=200, close=210  → +5%
    bars = {
        "005930": _make_bars(100.0, 105.0),
        "000660": _make_bars(200.0, 210.0),
    }
    od = _FakeBarsOD(bars)
    s = f.score(pred, od)
    assert abs(s.value - 5.0) < 1e-9  # mean(5%, 5%)


def test_score_correct_when_mean_return_above_base_rate():
    f = _make_facet(base_rate=0.0)
    pred = _make_pred(surges=_surge_items("005930"))
    bars = {"005930": _make_bars(100.0, 103.0)}  # +3% > 0%
    od = _FakeBarsOD(bars)
    s = f.score(pred, od)
    assert s.correct is True
    assert s.edge > 0


def test_score_correct_false_when_mean_return_below_base_rate():
    f = _make_facet(base_rate=2.0)
    pred = _make_pred(surges=_surge_items("005930"))
    bars = {"005930": _make_bars(100.0, 101.0)}  # +1% < 2%
    od = _FakeBarsOD(bars)
    s = f.score(pred, od)
    assert s.correct is False
    assert s.edge < 0


def test_score_unscorable_when_no_bars_data():
    f = _make_facet()
    pred = _make_pred(surges=_surge_items("005930"))
    od = _FakeBarsOD({"005930": None})
    s = f.score(pred, od)
    assert s.correct is None
    assert s.value == 0.0
    assert s.edge == 0.0


def test_score_baseline_value_equals_base_rate():
    f = _make_facet(base_rate=1.5)
    pred = _make_pred(surges=_surge_items("005930"))
    bars = {"005930": _make_bars(100.0, 104.0)}
    od = _FakeBarsOD(bars)
    s = f.score(pred, od)
    assert abs(s.baseline_value - 1.5) < 1e-9


def test_score_edge_equals_value_minus_baseline():
    f = _make_facet(base_rate=1.0)
    pred = _make_pred(surges=_surge_items("005930", "000660"))
    bars = {
        "005930": _make_bars(100.0, 103.0),   # +3%
        "000660": _make_bars(200.0, 207.0),   # +3.5%
    }
    od = _FakeBarsOD(bars)
    s = f.score(pred, od)
    assert abs(s.edge - (s.value - s.baseline_value)) < 1e-9


def test_score_economic_proxy_equals_value():
    f = _make_facet()
    pred = _make_pred(surges=_surge_items("005930"))
    bars = {"005930": _make_bars(100.0, 102.0)}
    od = _FakeBarsOD(bars)
    s = f.score(pred, od)
    assert s.economic_proxy == s.value


def test_score_partial_data_uses_available_symbols():
    f = _make_facet(base_rate=0.0)
    pred = _make_pred(surges=_surge_items("005930", "000660", "035420"))
    bars = {
        "005930": _make_bars(100.0, 102.0),  # +2%
        "000660": None,
        "035420": _make_bars(500.0, 515.0),  # +3%
    }
    od = _FakeBarsOD(bars)
    s = f.score(pred, od)
    assert abs(s.value - 2.5) < 1e-9  # mean(2%, 3%) = 2.5%
    assert s.correct is True
