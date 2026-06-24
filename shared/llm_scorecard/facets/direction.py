from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from shared.llm_scorecard.facets.base import (
    CaptureContext,
    FacetPrediction,
    FacetScore,
    register_facet,
)

_BASELINE = 1.0 / 3.0  # random 3-class baseline


class DirectionFacet:
    name = "direction"
    outcome_horizon = "session"
    outcome_source = "kospi200_futures"

    def capture(self, ctx: CaptureContext) -> FacetPrediction | None:
        mc = ctx.market_context
        if mc is None and ctx.redis is not None:
            try:
                raw = ctx.redis.get("trading:futures:market_context")
                if raw:
                    mc = json.loads(raw)
            except Exception:
                return None
        if not mc:
            return None
        overall_signal = mc.get("overall_signal")
        confidence = mc.get("confidence")
        risk_mode = mc.get("risk_mode")
        if overall_signal is None:
            return None
        direction = _normalize_signal(overall_signal)
        return FacetPrediction(
            facet=self.name,
            date_kst=ctx.date_kst,
            captured_at=ctx.now_kst,
            payload={
                "overall_signal": overall_signal,
                "direction": direction,
                "confidence": confidence,
                "risk_mode": risk_mode,
            },
            confidence=float(confidence) if confidence is not None else None,
        )

    def score(self, pred: FacetPrediction, outcome: Any) -> FacetScore | None:
        from shared.llm_scorecard.config import ScorecardConfig

        cfg = ScorecardConfig.from_yaml()
        neutral_band = cfg.facet_params.get("direction", {}).get("neutral_band_pct", 0.15)
        symbol = cfg.facet_params.get("direction", {}).get("symbol", "101S6000")
        ret = outcome.session_return(symbol, pred.date_kst, pred.captured_at)
        if ret is None:
            return None
        if ret > neutral_band:
            actual = "BULL"
        elif ret < -neutral_band:
            actual = "BEAR"
        else:
            actual = "NEUTRAL"
        predicted = pred.payload.get("direction", "NEUTRAL")
        correct = predicted == actual
        edge = (1.0 if correct else 0.0) - _BASELINE
        return FacetScore(
            facet=self.name,
            date_kst=pred.date_kst,
            correct=correct,
            value=1.0 if correct else 0.0,
            economic_proxy=ret,
            baseline_value=_BASELINE,
            edge=edge,
            detail={"predicted": predicted, "actual": actual, "return_pct": ret},
            scored_at=datetime.now(),
        )

    def baseline(self, pred: FacetPrediction, mkt: Any) -> float:
        return _BASELINE


def _normalize_signal(signal: str) -> str:
    """Map Korean MarketSignal values to BULL/BEAR/NEUTRAL."""
    bull = {"강한 상승", "상승"}
    bear = {"강한 하락", "하락"}
    if signal in bull:
        return "BULL"
    if signal in bear:
        return "BEAR"
    return "NEUTRAL"


_direction_facet = DirectionFacet()
register_facet(_direction_facet)
