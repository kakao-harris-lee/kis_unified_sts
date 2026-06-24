"""Tests for DirectionFacet."""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from shared.llm_scorecard.facets.base import CaptureContext, FacetPrediction, FACET_REGISTRY
import shared.llm_scorecard.facets.direction  # noqa: F401 — ensures registration


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


def _fake_cfg():
    from shared.llm_scorecard.config import ScorecardConfig
    return ScorecardConfig(
        enabled_facets=["direction"],
        facet_params={"direction": {"neutral_band_pct": 0.15, "symbol": "101S6000"}},
    )


def test_capture_bull():
    ctx = _make_ctx({"overall_signal": "상승", "confidence": 0.7, "risk_mode": "RISK_ON"})
    facet = FACET_REGISTRY["direction"]
    pred = facet.capture(ctx)
    assert pred is not None
    assert pred.payload["direction"] == "BULL"
    assert pred.confidence == pytest.approx(0.7)
    assert pred.facet == "direction"
    assert pred.date_kst == "2026-06-20"


def test_capture_returns_none_when_no_context_and_no_redis():
    ctx = _make_ctx(market_context=None, redis=None)
    facet = FACET_REGISTRY["direction"]
    pred = facet.capture(ctx)
    assert pred is None


def test_capture_strong_bear():
    ctx = _make_ctx({"overall_signal": "강한 하락", "confidence": 0.9, "risk_mode": "RISK_OFF"})
    facet = FACET_REGISTRY["direction"]
    pred = facet.capture(ctx)
    assert pred is not None
    assert pred.payload["direction"] == "BEAR"


def test_capture_neutral():
    ctx = _make_ctx({"overall_signal": "중립", "confidence": 0.5, "risk_mode": "NEUTRAL"})
    facet = FACET_REGISTRY["direction"]
    pred = facet.capture(ctx)
    assert pred is not None
    assert pred.payload["direction"] == "NEUTRAL"


def test_capture_from_redis():
    mc_data = {"overall_signal": "강한 상승", "confidence": 0.8, "risk_mode": "RISK_ON"}

    class FakeRedis:
        def get(self, key):
            if key == "trading:futures:market_context":
                return json.dumps(mc_data).encode()
            return None

    ctx = _make_ctx(market_context=None, redis=FakeRedis())
    facet = FACET_REGISTRY["direction"]
    pred = facet.capture(ctx)
    assert pred is not None
    assert pred.payload["direction"] == "BULL"
    assert pred.confidence == pytest.approx(0.8)


def test_capture_redis_returns_none_on_missing_key():
    class FakeRedis:
        def get(self, key):
            return None

    ctx = _make_ctx(market_context=None, redis=FakeRedis())
    facet = FACET_REGISTRY["direction"]
    pred = facet.capture(ctx)
    assert pred is None


def test_score_correct_bull():
    facet = FACET_REGISTRY["direction"]
    pred = FacetPrediction(
        facet="direction",
        date_kst="2026-06-20",
        captured_at=datetime(2026, 6, 20, 9, 0, 0),
        payload={"direction": "BULL", "overall_signal": "상승"},
        confidence=0.7,
    )
    with patch(
        "shared.llm_scorecard.config.ScorecardConfig.from_yaml",
        return_value=_fake_cfg(),
    ):
        score = facet.score(pred, FakeOutcome(0.5))
    assert score is not None
    assert score.correct is True
    assert score.value == 1.0


def test_score_incorrect_bull():
    facet = FACET_REGISTRY["direction"]
    pred = FacetPrediction(
        facet="direction",
        date_kst="2026-06-20",
        captured_at=datetime(2026, 6, 20, 9, 0, 0),
        payload={"direction": "BULL", "overall_signal": "상승"},
        confidence=0.7,
    )
    with patch(
        "shared.llm_scorecard.config.ScorecardConfig.from_yaml",
        return_value=_fake_cfg(),
    ):
        score = facet.score(pred, FakeOutcome(-0.5))
    assert score is not None
    assert score.correct is False
    assert score.value == 0.0


def test_score_returns_none_when_no_data():
    facet = FACET_REGISTRY["direction"]
    pred = FacetPrediction(
        facet="direction",
        date_kst="2026-06-20",
        captured_at=datetime(2026, 6, 20, 9, 0, 0),
        payload={"direction": "BULL"},
        confidence=0.7,
    )
    with patch(
        "shared.llm_scorecard.config.ScorecardConfig.from_yaml",
        return_value=_fake_cfg(),
    ):
        score = facet.score(pred, FakeOutcome(None))
    assert score is None


def test_score_uses_neutral_band_from_config():
    """Return of 0.1 is within neutral_band_pct=0.15 → NEUTRAL, not BULL."""
    facet = FACET_REGISTRY["direction"]
    pred = FacetPrediction(
        facet="direction",
        date_kst="2026-06-20",
        captured_at=datetime(2026, 6, 20, 9, 0, 0),
        payload={"direction": "BULL"},
        confidence=0.7,
    )
    with patch(
        "shared.llm_scorecard.config.ScorecardConfig.from_yaml",
        return_value=_fake_cfg(),
    ):
        score = facet.score(pred, FakeOutcome(0.1))
    assert score is not None
    assert score.detail["actual"] == "NEUTRAL"
    assert score.correct is False


def test_direction_facet_registered():
    assert "direction" in FACET_REGISTRY
