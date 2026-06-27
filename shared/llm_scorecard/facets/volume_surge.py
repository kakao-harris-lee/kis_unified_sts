"""VolumeSurgeFacet — scores early-session volume-surge flags against flag-to-close returns.

## Source resolution (DONE_WITH_CONCERNS)

No clean per-symbol surge-with-timestamp Redis feed exists in the current repo.
The ``opening_volume_surge`` entry generator fires intraday ``Signal`` objects
but does NOT publish them to a dedicated Redis key.

**Facet design:**
    capture() reads ``ctx.screener["volume_surge"]`` — a list of dicts with keys:
        code: str           — stock code
        flag_time: str      — ISO timestamp of the surge flag (KST)
        flag_price: float   — price at flag time

    capture() returns None when the list is absent or empty so the facet is
    gracefully unscorable on days without a surge-feed hook.

**Hook requirement:**
    To populate this feed, a future hook must catch OpeningVolumeSurge Signal
    objects at signal-emit time and write
    ``ctx.screener["volume_surge"] = [{code, flag_time, flag_price}, ...]``
    before calling capture_predictions().  No existing natural emit point exists
    without a dedicated Redis key or a hook in stock_strategy/main.py.

Score:
    value = mean(flag-to-close return) for each flagged symbol.
    baseline = random-entry intraday continuation (param
               ``facet_params.volume_surge.base_rate``, default 0.0 %).
    edge = value − baseline_value.
    correct = value > base_rate.
    economic_proxy = value  (average PnL of buying at flag price and closing).
    unscorable (correct=None) when zero flagged symbols have bar data.
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


class VolumeSurgeFacet:
    name = "volume_surge"
    outcome_horizon = "flag_to_close"
    outcome_source = "stock_minute"

    def __init__(self, base_rate: float | None = None) -> None:
        self._base_rate = base_rate

    def _params(self) -> float:
        if self._base_rate is not None:
            return self._base_rate
        from shared.llm_scorecard.config import ScorecardConfig

        p = ScorecardConfig.from_yaml().facet_params.get("volume_surge", {})
        return float(p.get("base_rate", 0.0))

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def capture(self, ctx: CaptureContext) -> FacetPrediction | None:
        screener = ctx.screener
        if not screener:
            return None
        surges: list[dict] = screener.get("volume_surge") or []
        if not surges:
            return None

        return FacetPrediction(
            facet=self.name,
            date_kst=ctx.date_kst,
            captured_at=ctx.now_kst,
            payload={"surges": surges},
            confidence=None,
        )

    # ------------------------------------------------------------------
    # Score
    # ------------------------------------------------------------------

    def baseline(self, pred: FacetPrediction, mkt: Any) -> float:
        _ = (pred, mkt)
        return self._params()

    def score(self, pred: FacetPrediction, mkt: Any) -> FacetScore:
        base_rate = self._params()
        surges: list[dict] = pred.payload.get("surges", [])

        returns: list[float] = []
        for item in surges:
            code = item.get("code")
            if not code:
                continue
            # Parse flag_time — no-look-ahead: bars_after(flag_time) gives
            # only bars at/after the flag, ending at close.
            flag_time_raw = item.get("flag_time")
            try:
                flag_dt = datetime.fromisoformat(str(flag_time_raw))
            except (ValueError, TypeError):
                continue

            df = mkt.bars_after(code, pred.date_kst, flag_dt)
            if df is None or len(df) < 2:
                continue

            open_ = float(df.iloc[0]["open"])
            close = float(df.iloc[-1]["close"])
            if open_ == 0:
                continue
            ret = (close - open_) / open_ * 100.0
            returns.append(ret)

        if not returns:
            return FacetScore(
                facet=self.name,
                date_kst=pred.date_kst,
                correct=None,
                value=0.0,
                economic_proxy=0.0,
                baseline_value=base_rate,
                edge=0.0,
                detail={"reason": "no_outcome_data", "n_surges": len(surges)},
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
                "n_surges": len(surges),
                "n_scored": len(returns),
                "mean_return": mean_return,
                "base_rate": base_rate,
            },
            scored_at=datetime.now(),
        )


register_facet(VolumeSurgeFacet())
