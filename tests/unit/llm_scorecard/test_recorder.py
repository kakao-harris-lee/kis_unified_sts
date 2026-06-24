"""Tests for the recorder (plan Task 6) — module-level capture_predictions."""
from __future__ import annotations

from datetime import datetime

import pytest

from shared.llm_scorecard.config import ScorecardConfig
from shared.llm_scorecard.facets.base import (
    CaptureContext,
    FACET_REGISTRY,
    FacetPrediction,
    register_facet,
)
from shared.llm_scorecard.recorder import capture_predictions


@pytest.fixture
def registry_snapshot():
    snapshot = dict(FACET_REGISTRY)
    yield
    FACET_REGISTRY.clear()
    FACET_REGISTRY.update(snapshot)


class FakeFacet:
    def __init__(self, name="fake", return_val=None, raises=False):
        self.name = name
        self.outcome_horizon = "session"
        self.outcome_source = "test"
        self._return_val = return_val
        self._raises = raises

    def capture(self, ctx):
        if self._raises:
            raise RuntimeError("capture error")
        return self._return_val


class FakeLedger:
    def __init__(self):
        self.saved = []

    def save_prediction(self, date_kst, facet, captured_at, payload, confidence):
        self.saved.append({
            "date_kst": date_kst,
            "facet": facet,
            "captured_at": captured_at,
            "payload": payload,
            "confidence": confidence,
        })


def _make_prediction(facet="fake"):
    return FacetPrediction(
        facet=facet,
        date_kst="2026-06-20",
        captured_at=datetime(2026, 6, 20, 9, 0, 0),
        payload={"direction": "BULL"},
        confidence=0.7,
    )


def _make_ctx():
    return CaptureContext(date_kst="2026-06-20", now_kst=datetime(2026, 6, 20, 9, 0, 0))


def test_captures_enabled_direction_facet():
    """End-to-end through the real direction facet."""
    led = FakeLedger()
    ctx = CaptureContext(
        "2026-06-25",
        datetime(2026, 6, 25, 8, 40),
        market_context={"overall_signal": "BEARISH", "confidence": 0.6},
    )
    n = capture_predictions(ctx, ScorecardConfig(enabled_facets=["direction"]), led)
    assert n == 1
    assert led.saved[0]["facet"] == "direction"
    assert led.saved[0]["payload"]["direction"] == "BEAR"


def test_returns_count_and_saves(registry_snapshot):
    register_facet(FakeFacet(name="fake", return_val=_make_prediction()))
    led = FakeLedger()
    n = capture_predictions(_make_ctx(), ScorecardConfig(enabled_facets=["fake"]), led)
    assert n == 1
    assert led.saved[0]["confidence"] == 0.7
    assert led.saved[0]["captured_at"] == "2026-06-20T09:00:00"


def test_skips_none_results(registry_snapshot):
    register_facet(FakeFacet(name="fakennone", return_val=None))
    led = FakeLedger()
    n = capture_predictions(_make_ctx(), ScorecardConfig(enabled_facets=["fakennone"]), led)
    assert n == 0
    assert led.saved == []


def test_is_best_effort_on_facet_error(registry_snapshot):
    register_facet(FakeFacet(name="bad", raises=True))
    register_facet(FakeFacet(name="good", return_val=_make_prediction("good")))
    led = FakeLedger()
    n = capture_predictions(_make_ctx(), ScorecardConfig(enabled_facets=["bad", "good"]), led)
    # bad raised but good still ran — never raises
    assert n == 1
    assert led.saved[0]["facet"] == "good"


def test_is_best_effort_on_ledger_error():
    class Boom:
        def save_prediction(self, *a, **k):
            raise RuntimeError("redis down")

    ctx = CaptureContext(
        "2026-06-25",
        datetime(2026, 6, 25, 8, 40),
        market_context={"overall_signal": "BULLISH", "confidence": 0.7},
    )
    assert capture_predictions(ctx, ScorecardConfig(enabled_facets=["direction"]), Boom()) == 0
