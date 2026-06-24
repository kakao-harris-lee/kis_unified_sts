"""Tests for DirectionFacet (plan Task 5)."""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from shared.llm_scorecard.facets.base import CaptureContext, FACET_REGISTRY, FacetPrediction
import shared.llm_scorecard.facets.direction  # noqa: F401 — ensures registration
from shared.llm_scorecard.facets.direction import DirectionFacet


class FakeOutcome:
    def __init__(self, ret):
        self._ret = ret

    def session_return(self, symbol, date_kst, captured_at):
        return self._ret


def _make_ctx(market_context=None, redis=None):
    return CaptureContext(
        date_kst="2026-06-20",
        now_kst=datetime(2026, 6, 20, 9, 0, 0),
        market_context=market_context,
        redis=redis,
    )


def _facet():
    # Explicit params avoid touching config/llm_scorecard.yaml on disk.
    return DirectionFacet(neutral_band_pct=0.15, symbol="101S6000")


# --- capture -----------------------------------------------------------------


def test_capture_bull_korean():
    ctx = _make_ctx({"overall_signal": "상승", "confidence": 0.7, "risk_mode": "RISK_ON"})
    pred = _facet().capture(ctx)
    assert pred is not None
    assert pred.payload["direction"] == "BULL"
    assert pred.confidence == pytest.approx(0.7)
    assert pred.facet == "direction"
    assert pred.date_kst == "2026-06-20"


def test_capture_bull_english():
    ctx = _make_ctx({"overall_signal": "BULLISH", "confidence": 0.7, "risk_mode": "RISK_ON"})
    pred = _facet().capture(ctx)
    assert pred is not None and pred.payload["direction"] == "BULL"


def test_capture_strong_bear():
    ctx = _make_ctx({"overall_signal": "강한 하락", "confidence": 0.9, "risk_mode": "RISK_OFF"})
    pred = _facet().capture(ctx)
    assert pred is not None and pred.payload["direction"] == "BEAR"


def test_capture_neutral():
    ctx = _make_ctx({"overall_signal": "중립", "confidence": 0.5, "risk_mode": "NEUTRAL"})
    pred = _facet().capture(ctx)
    assert pred is not None and pred.payload["direction"] == "NEUTRAL"


def test_capture_returns_none_when_no_context_and_no_redis():
    assert _facet().capture(_make_ctx(market_context=None, redis=None)) is None


def test_capture_from_redis():
    mc_data = {"overall_signal": "강한 상승", "confidence": 0.8, "risk_mode": "RISK_ON"}

    class FakeRedis:
        def get(self, key):
            if key == "trading:futures:market_context":
                return json.dumps(mc_data).encode()
            return None

    pred = _facet().capture(_make_ctx(market_context=None, redis=FakeRedis()))
    assert pred is not None
    assert pred.payload["direction"] == "BULL"
    assert pred.confidence == pytest.approx(0.8)


def test_capture_redis_returns_none_on_missing_key():
    class FakeRedis:
        def get(self, key):
            return None

    assert _facet().capture(_make_ctx(market_context=None, redis=FakeRedis())) is None


# --- score: economic_proxy / baseline / edge semantics (plan Task 5) ---------


def test_score_correct_bull_economic_proxy_is_ret_times_sign():
    pred = FacetPrediction("direction", "2026-06-25", datetime(2026, 6, 25, 8, 40),
                           {"direction": "BULL"}, 0.7)
    s = _facet().score(pred, FakeOutcome(ret=1.2))  # realized +1.2%
    assert s.correct is True
    assert s.economic_proxy == pytest.approx(1.2)
    assert s.value == pytest.approx(1.2)
    assert s.baseline_value == 0.0
    assert s.edge == pytest.approx(1.2)  # baseline flat = 0


def test_score_correct_bear_on_down_day_reports_positive_proxy():
    """A correct BEAR call on a -2% day must report economic_proxy=+2.0."""
    pred = FacetPrediction("direction", "2026-06-25", datetime(2026, 6, 25, 8, 40),
                           {"direction": "BEAR"}, 0.7)
    s = _facet().score(pred, FakeOutcome(ret=-2.0))
    assert s.correct is True
    assert s.economic_proxy == pytest.approx(2.0)
    assert s.value == pytest.approx(2.0)
    assert s.edge == pytest.approx(2.0)


def test_score_incorrect_bull_on_down_day_reports_negative_proxy():
    pred = FacetPrediction("direction", "2026-06-25", datetime(2026, 6, 25, 8, 40),
                           {"direction": "BULL"}, 0.7)
    s = _facet().score(pred, FakeOutcome(ret=-1.0))
    assert s.correct is False
    assert s.economic_proxy == pytest.approx(-1.0)
    assert s.edge == pytest.approx(-1.0)


def test_score_neutral_within_band_proxy_zero():
    pred = FacetPrediction("direction", "2026-06-25", datetime(2026, 6, 25, 8, 40),
                           {"direction": "NEUTRAL"}, 0.5)
    s = _facet().score(pred, FakeOutcome(ret=0.05))  # |0.05| < 0.15 → NEUTRAL realized
    assert s.correct is True
    assert s.economic_proxy == 0.0  # NEUTRAL sign = 0
    assert s.edge == 0.0


def test_score_uses_neutral_band_from_config():
    """ret 0.1 within band 0.15 → realized NEUTRAL, so a BULL call is wrong."""
    pred = FacetPrediction("direction", "2026-06-25", datetime(2026, 6, 25, 8, 40),
                           {"direction": "BULL"}, 0.7)
    s = _facet().score(pred, FakeOutcome(ret=0.1))
    assert s.detail["realized"] == "NEUTRAL"
    assert s.correct is False


def test_score_config_driven_band():
    """When constructed without args, band comes from config (patched)."""
    from shared.llm_scorecard.config import ScorecardConfig

    cfg = ScorecardConfig(facet_params={"direction": {"neutral_band_pct": 0.5, "symbol": "X"}})
    pred = FacetPrediction("direction", "2026-06-25", datetime(2026, 6, 25, 8, 40),
                           {"direction": "BULL"}, 0.7)
    with patch("shared.llm_scorecard.config.ScorecardConfig.from_yaml", return_value=cfg):
        s = DirectionFacet().score(pred, FakeOutcome(ret=0.3))  # |0.3| < 0.5 → NEUTRAL
    assert s.detail["realized"] == "NEUTRAL"


# --- score: unscorable persists with correct=None (plan Task 5) --------------


def test_score_unscorable_returns_facetscore_with_correct_none():
    pred = FacetPrediction("direction", "2026-06-25", datetime(2026, 6, 25, 8, 40),
                           {"direction": "BULL"}, 0.7)
    s = _facet().score(pred, FakeOutcome(ret=None))
    assert s is not None  # NOT Python None
    assert s.correct is None
    assert s.value == 0.0
    assert s.economic_proxy == 0.0
    assert s.baseline_value == 0.0
    assert s.edge == 0.0
    assert s.detail == {"reason": "no_outcome_data"}


def test_direction_facet_registered():
    assert "direction" in FACET_REGISTRY
