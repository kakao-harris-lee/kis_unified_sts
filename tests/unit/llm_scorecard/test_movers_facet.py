"""Tests for MoversFacet (Task 11)."""
from __future__ import annotations

import json
from datetime import datetime

from shared.llm_scorecard.config import ScorecardConfig
from shared.llm_scorecard.facets.base import CaptureContext, FacetPrediction
from shared.llm_scorecard.facets.movers import MoversFacet
from shared.llm_scorecard.recorder import capture_predictions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_facet(base_rate=0.5):
    return MoversFacet(base_rate=base_rate)


def _ctx(screener=None):
    """CaptureContext with screener populated from system:trade_targets:latest shape."""
    return CaptureContext(
        date_kst="2026-06-25",
        now_kst=datetime(2026, 6, 25, 8, 40),
        screener=screener,
    )


class _FakeOD:
    def __init__(self, returns: dict[str, float | None]):
        self._returns = returns

    def session_return(self, symbol, date_kst, captured_at):
        return self._returns.get(symbol)


# ---------------------------------------------------------------------------
# Capture tests
# ---------------------------------------------------------------------------

def test_capture_reads_flagged_codes_from_screener():
    screener = {"codes": ["005930", "000660", "035420"], "names": ["A", "B", "C"]}
    ctx = _ctx(screener=screener)
    f = _make_facet()
    pred = f.capture(ctx)
    assert pred is not None
    assert pred.facet == "movers"
    assert set(pred.payload["codes"]) == {"005930", "000660", "035420"}


def test_capture_returns_none_when_screener_absent():
    ctx = _ctx(screener=None)
    assert _make_facet().capture(ctx) is None


def test_capture_returns_none_when_screener_has_no_codes():
    ctx = _ctx(screener={"codes": [], "names": []})
    assert _make_facet().capture(ctx) is None


def test_capture_returns_none_when_screener_missing_codes_key():
    ctx = _ctx(screener={"scores": [0.8]})
    assert _make_facet().capture(ctx) is None


# ---------------------------------------------------------------------------
# Score tests
# ---------------------------------------------------------------------------

def _make_pred(codes=None):
    return FacetPrediction(
        facet="movers",
        date_kst="2026-06-25",
        captured_at=datetime(2026, 6, 25, 8, 40),
        payload={"codes": codes or ["005930", "000660", "035420"]},
        confidence=None,
    )


def test_score_value_is_mean_follow_through():
    f = _make_facet(base_rate=0.5)
    pred = _make_pred(codes=["005930", "000660"])
    od = _FakeOD({"005930": 2.0, "000660": 4.0})
    s = f.score(pred, od)
    assert abs(s.value - 3.0) < 1e-9  # mean(2.0, 4.0) = 3.0
    assert s.economic_proxy == s.value


def test_score_correct_when_follow_through_above_base_rate():
    """correct = True when mean follow-through > base_rate threshold."""
    f = _make_facet(base_rate=0.5)
    pred = _make_pred(codes=["005930", "000660"])
    od = _FakeOD({"005930": 3.0, "000660": 5.0})  # mean=4.0 > 0.5
    s = f.score(pred, od)
    assert s.correct is True
    assert s.edge > 0


def test_score_correct_false_when_follow_through_below_base_rate():
    f = _make_facet(base_rate=0.5)
    pred = _make_pred(codes=["005930"])
    od = _FakeOD({"005930": -1.0})  # -1.0 < 0.5 → correct=False
    s = f.score(pred, od)
    assert s.correct is False
    assert s.edge < 0


def test_score_baseline_value_equals_base_rate():
    f = _make_facet(base_rate=0.5)
    pred = _make_pred(codes=["005930"])
    od = _FakeOD({"005930": 2.0})
    s = f.score(pred, od)
    assert abs(s.baseline_value - 0.5) < 1e-9


def test_score_edge_equals_value_minus_baseline():
    f = _make_facet(base_rate=1.0)
    pred = _make_pred(codes=["005930", "000660"])
    od = _FakeOD({"005930": 1.5, "000660": 2.5})  # mean=2.0; base=1.0; edge=1.0
    s = f.score(pred, od)
    assert abs(s.edge - (s.value - s.baseline_value)) < 1e-9


def test_score_unscorable_when_no_outcome_data():
    f = _make_facet()
    pred = _make_pred(codes=["005930", "000660"])
    od = _FakeOD({})  # all None
    s = f.score(pred, od)
    assert s.correct is None
    assert s.value == 0.0
    assert s.edge == 0.0


def test_score_partial_data_uses_available_symbols():
    """Symbols with no data are skipped; scoring uses remaining symbols."""
    f = _make_facet(base_rate=0.5)
    pred = _make_pred(codes=["005930", "000660", "035420"])
    od = _FakeOD({"005930": 3.0, "000660": None, "035420": 1.0})  # mean(3.0, 1.0)=2.0
    s = f.score(pred, od)
    assert abs(s.value - 2.0) < 1e-9
    assert s.correct is True  # 2.0 > 0.5


# ---------------------------------------------------------------------------
# Briefing-hook capture-path test (review fix #1 regression guard)
# ---------------------------------------------------------------------------

class _FakeRedis:
    """Minimal fake redis: returns the trade_targets JSON for the key."""

    def __init__(self, payloads: dict[str, str]):
        self._payloads = payloads

    def get(self, key):
        return self._payloads.get(key)


def test_briefing_hook_capture_path_yields_movers_prediction():
    """End-to-end shape: fake redis trade_targets JSON → parsed → screener →
    capture_predictions produces a movers prediction (not None).

    This is the regression guard for the original ``_pub._redis`` bug, which made
    the screener None at runtime so MoversFacet.capture always returned None.
    The hook now: client.get(key) → json.loads → CaptureContext(screener=parsed).
    """
    # The exact payload shape published to system:trade_targets:latest.
    trade_targets = {
        "codes": ["005930", "000660", "035420"],
        "names": ["Samsung", "SK Hynix", "NAVER"],
        "scores": [0.9, 0.8, 0.7],
        "metadata": {},
        "sources": ["fusion"],
    }
    fake_redis = _FakeRedis({"system:trade_targets:latest": json.dumps(trade_targets)})

    # Mirror the briefing hook: fetch → parse → screener.
    raw = fake_redis.get("system:trade_targets:latest")
    assert raw is not None  # the bug made this branch unreachable
    screener = json.loads(raw)

    ctx = CaptureContext(
        date_kst="2026-06-25",
        now_kst=datetime(2026, 6, 25, 8, 40),
        screener=screener,
    )

    class _Ledger:
        def __init__(self):
            self.saved = []

        def save_prediction(self, date_kst, facet, captured_at, payload, confidence):
            self.saved.append((facet, payload))

    led = _Ledger()
    n = capture_predictions(ctx, ScorecardConfig(enabled_facets=["movers"]), led)
    assert n == 1
    facet_name, payload = led.saved[0]
    assert facet_name == "movers"
    assert set(payload["codes"]) == {"005930", "000660", "035420"}
