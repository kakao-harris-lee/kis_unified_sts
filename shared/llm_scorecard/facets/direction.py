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

# Map both English MarketContext.to_dict() signals and Korean MarketSignal
# .value strings to the canonical BULL/BEAR/NEUTRAL direction.
_SIGNAL_MAP = {
    "BULLISH": "BULL",
    "BEARISH": "BEAR",
    "NEUTRAL": "NEUTRAL",
    "강한 상승": "BULL",
    "상승": "BULL",
    "강한 하락": "BEAR",
    "하락": "BEAR",
    "중립": "NEUTRAL",
}

# Directional sign of a predicted call: PnL of taking that direction = ret * sign.
_DIRECTION_SIGN = {"BULL": 1.0, "BEAR": -1.0, "NEUTRAL": 0.0}


def _normalize_signal(signal: Any) -> str:
    """Map an English or Korean market-call signal to BULL/BEAR/NEUTRAL."""
    return _SIGNAL_MAP.get(str(signal), "NEUTRAL")


class DirectionFacet:
    name = "direction"
    outcome_horizon = "same_session_open_to_close"
    outcome_source = "futures_minute"

    def __init__(self, neutral_band_pct: float | None = None, symbol: str | None = None) -> None:
        self._neutral_band_pct = neutral_band_pct
        self._symbol = symbol

    def _params(self) -> tuple[float, str]:
        """Resolve neutral band + symbol from explicit args or config (config-driven)."""
        if self._neutral_band_pct is not None and self._symbol is not None:
            return self._neutral_band_pct, self._symbol
        from shared.llm_scorecard.config import ScorecardConfig

        params = ScorecardConfig.from_yaml().facet_params.get("direction", {})
        band = (
            self._neutral_band_pct
            if self._neutral_band_pct is not None
            else float(params.get("neutral_band_pct", 0.15))
        )
        symbol = self._symbol if self._symbol is not None else str(params.get("symbol", "101S6000"))
        return band, symbol

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
        if overall_signal is None:
            return None
        confidence = mc.get("confidence")
        risk_mode = mc.get("risk_mode")
        direction = _normalize_signal(overall_signal)
        return FacetPrediction(
            facet=self.name,
            date_kst=ctx.date_kst,
            captured_at=ctx.now_kst,
            payload={
                "overall_signal": overall_signal,
                "direction": direction,
                "risk_mode": risk_mode,
            },
            confidence=float(confidence) if confidence is not None else None,
        )

    def _realized_dir(self, ret: float, band: float) -> str:
        if abs(ret) < band:
            return "NEUTRAL"
        return "BULL" if ret > 0 else "BEAR"

    def baseline(self, pred: FacetPrediction, mkt: Any) -> float:
        # Always-flat directional PnL: doing nothing earns 0.
        return 0.0

    def score(self, pred: FacetPrediction, mkt: Any) -> FacetScore:
        band, symbol = self._params()
        ret = mkt.session_return(symbol, pred.date_kst, pred.captured_at)
        if ret is None:
            # Unscorable: persist with correct=None (NEVER wrong, never skipped).
            return FacetScore(
                facet=self.name,
                date_kst=pred.date_kst,
                correct=None,
                value=0.0,
                economic_proxy=0.0,
                baseline_value=0.0,
                edge=0.0,
                detail={"reason": "no_outcome_data"},
                scored_at=datetime.now(),
            )
        predicted = pred.payload.get("direction", "NEUTRAL")
        realized = self._realized_dir(ret, band)
        sign = _DIRECTION_SIGN.get(predicted, 0.0)
        econ = ret * sign  # PnL of taking the predicted direction
        base = self.baseline(pred, mkt)
        return FacetScore(
            facet=self.name,
            date_kst=pred.date_kst,
            correct=predicted == realized,
            value=econ,
            economic_proxy=econ,
            baseline_value=base,
            edge=econ - base,
            detail={"predicted": predicted, "realized": realized, "ret_pct": ret},
            scored_at=datetime.now(),
        )


register_facet(DirectionFacet())
