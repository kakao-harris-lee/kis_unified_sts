"""Tests for PredictionRecorder."""
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
from shared.llm_scorecard.recorder import PredictionRecorder


class FakeFacet:
    def __init__(self, name="fake", return_val=None, raises=False):
        self.name = name
        self.outcome_horizon = "session"
        self.outcome_source = "test"
        self._return_val = return_val
        self._raises = raises
        self.capture_calls = 0

    def capture(self, ctx):
        self.capture_calls += 1
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
    return CaptureContext(
        date_kst="2026-06-20",
        now_kst=datetime(2026, 6, 20, 9, 0, 0),
    )


@pytest.fixture
def registry_snapshot():
    """Save and restore FACET_REGISTRY around each test."""
    snapshot = dict(FACET_REGISTRY)
    yield
    FACET_REGISTRY.clear()
    FACET_REGISTRY.update(snapshot)


def test_capture_returns_predictions_and_saves(registry_snapshot):
    pred = _make_prediction()
    facet = FakeFacet(name="fake", return_val=pred)
    register_facet(facet)

    cfg = ScorecardConfig(enabled_facets=["fake"])
    ledger = FakeLedger()
    recorder = PredictionRecorder(cfg, ledger, _make_ctx())
    results = recorder.capture_predictions()

    assert len(results) == 1
    assert results[0] is pred
    assert len(ledger.saved) == 1
    assert ledger.saved[0]["facet"] == "fake"
    assert ledger.saved[0]["confidence"] == 0.7


def test_capture_skips_none_results(registry_snapshot):
    facet = FakeFacet(name="fakennone", return_val=None)
    register_facet(facet)

    cfg = ScorecardConfig(enabled_facets=["fakennone"])
    ledger = FakeLedger()
    recorder = PredictionRecorder(cfg, ledger, _make_ctx())
    results = recorder.capture_predictions()

    assert results == []
    assert ledger.saved == []


def test_capture_swallows_exception_and_continues(registry_snapshot):
    pred = _make_prediction("good")
    good_facet = FakeFacet(name="good", return_val=pred)
    bad_facet = FakeFacet(name="bad", raises=True)
    register_facet(good_facet)
    register_facet(bad_facet)

    cfg = ScorecardConfig(enabled_facets=["bad", "good"])
    ledger = FakeLedger()
    recorder = PredictionRecorder(cfg, ledger, _make_ctx())
    results = recorder.capture_predictions()

    # bad facet raised but good facet still ran
    assert len(results) == 1
    assert results[0].facet == "good"
    assert len(ledger.saved) == 1


def test_capture_saves_isoformat_timestamp(registry_snapshot):
    pred = _make_prediction("ts_facet")
    facet = FakeFacet(name="ts_facet", return_val=pred)
    register_facet(facet)

    cfg = ScorecardConfig(enabled_facets=["ts_facet"])
    ledger = FakeLedger()
    recorder = PredictionRecorder(cfg, ledger, _make_ctx())
    recorder.capture_predictions()

    assert ledger.saved[0]["captured_at"] == "2026-06-20T09:00:00"
