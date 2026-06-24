"""MoversFacet — scores LLM pre-market flagged movers against session follow-through.

Capture:
    Reads ``ctx.screener`` populated from ``system:trade_targets:latest`` (Redis DB1).
    The key holds a JSON dict with at least ``codes`` (list of stock codes).
    The briefing hook should fetch this key and attach it to ``CaptureContext.screener``
    before calling ``capture_predictions``.

    Implied direction: long (positive session return = follow-through).

Score:
    Per-symbol: ``session_return(code, date_kst, captured_at)`` (no-look-ahead).
    value = mean follow-through return of flagged symbols with data.
    baseline = unconditional base-rate follow-through (param
               ``facet_params.movers.base_rate``, default 0.5 %).
    edge = value − baseline_value.
    correct = value > base_rate  (mean follow-through beats the baseline).
    economic_proxy = value  (average PnL of entering every flagged symbol at open).
    unscorable (correct=None) when zero flagged symbols have outcome data.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.llm_scorecard.facets.base import (
    CaptureContext,
    FacetPrediction,
    FacetScore,
    register_facet,
)


class MoversFacet:
    name = "movers"
    outcome_horizon = "same_session_open_to_close"
    outcome_source = "stock_minute"

    def __init__(self, base_rate: float | None = None) -> None:
        self._base_rate = base_rate

    def _params(self) -> float:
        """Resolve base_rate from explicit arg or config."""
        if self._base_rate is not None:
            return self._base_rate
        from shared.llm_scorecard.config import ScorecardConfig

        p = ScorecardConfig.from_yaml().facet_params.get("movers", {})
        return float(p.get("base_rate", 0.5))

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def capture(self, ctx: CaptureContext) -> FacetPrediction | None:
        screener = ctx.screener
        if not screener:
            return None
        codes: list[str] = screener.get("codes") or []
        if not codes:
            return None

        return FacetPrediction(
            facet=self.name,
            date_kst=ctx.date_kst,
            captured_at=ctx.now_kst,
            payload={
                "codes": codes,
                # Attach optional names/scores for logging; not used in scoring.
                "names": screener.get("names", {}),
                "scores": screener.get("scores", []),
            },
            confidence=None,
        )

    # ------------------------------------------------------------------
    # Score
    # ------------------------------------------------------------------

    def baseline(self, pred: FacetPrediction, mkt: Any) -> float:
        return self._params()

    def score(self, pred: FacetPrediction, mkt: Any) -> FacetScore:
        base_rate = self._params()
        codes: list[str] = pred.payload.get("codes", [])

        # Collect session returns for each flagged symbol (no-look-ahead).
        returns: list[float] = []
        for code in codes:
            r = mkt.session_return(code, pred.date_kst, pred.captured_at)
            if r is not None:
                returns.append(r)

        if not returns:
            return FacetScore(
                facet=self.name,
                date_kst=pred.date_kst,
                correct=None,
                value=0.0,
                economic_proxy=0.0,
                baseline_value=base_rate,
                edge=0.0,
                detail={"reason": "no_outcome_data", "n_codes": len(codes)},
                scored_at=datetime.now(),
            )

        mean_return = sum(returns) / len(returns)
        edge = mean_return - base_rate

        return FacetScore(
            facet=self.name,
            date_kst=pred.date_kst,
            correct=mean_return > base_rate,
            value=mean_return,
            economic_proxy=mean_return,
            baseline_value=base_rate,
            edge=edge,
            detail={
                "n_flagged": len(codes),
                "n_scored": len(returns),
                "mean_return": mean_return,
                "base_rate": base_rate,
            },
            scored_at=datetime.now(),
        )


register_facet(MoversFacet())
