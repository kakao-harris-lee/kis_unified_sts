"""ThemesFacet — scores LLM sector-rotation theme calls against realized returns.

Capture:
    Reads ``ctx.market_context["sector_rotation"]`` (theme→bias dict, e.g.
    ``{"Technology": "INFLOW", "Finance": "OUTFLOW"}``).  The top-N themes
    with an "INFLOW" (or equivalent bullish) bias are the "strong themes".
    Each strong theme maps to constituent symbols via the config map
    ``facet_params.themes.theme_symbols`` (theme → list[code]).

Score:
    value = mean(strong-theme returns) − market mean (equal-weight over all
            tracked symbols with data).
    baseline = market mean (unconditional average of the tracked universe).
    edge = value − baseline_value (i.e. the spread).
    correct = edge > 0  (strong themes outperformed the equal-weight universe).
    economic_proxy = value  (the spread is the PnL proxy for over-weighting
                             strong themes vs. market-weight).
    unscorable (correct=None) when zero strong-theme symbols have outcome data.
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

# Bias strings that mark a theme as "strong" (bullish, expected to outperform).
_STRONG_BIASES = frozenset({"INFLOW", "BULLISH", "STRONG", "POSITIVE", "강세", "매수"})

# Default theme→symbols map shipped with the facet.  Operators should override
# via config/llm_scorecard.yaml::facet_params.themes.theme_symbols.
_DEFAULT_THEME_SYMBOLS: dict[str, list[str]] = {
    # KRX major sector ETFs / representative constituents (illustrative defaults)
    "Technology": ["005930", "000660", "035420"],   # Samsung, SK Hynix, NAVER
    "Finance": ["055550", "086790", "105560"],       # Shinhan, Kakao Bank, KB
    "Energy": ["010950", "096770"],                  # S-Oil, SK Innovation
    "Healthcare": ["207940", "068270"],              # Samsung Biologics, Celltrion
    "Consumer": ["051910", "009830"],               # LG Chem, Hanwha Solutions
    "Industrials": ["006400", "012330"],             # Samsung SDI, Hyundai Mobis
    "Chemicals": ["011170", "010130"],               # Lotte Chemical, Korea Zinc
    "Telecom": ["030200", "017670"],                 # KT, SK Telecom
}


def _is_strong(bias: str) -> bool:
    return str(bias).upper() in _STRONG_BIASES


class ThemesFacet:
    name = "themes"
    outcome_horizon = "same_session_open_to_close"
    outcome_source = "stock_minute"

    def __init__(
        self,
        top_n: int | None = None,
        theme_symbols: dict[str, list[str]] | None = None,
    ) -> None:
        self._top_n = top_n
        self._theme_symbols = theme_symbols

    def _params(self) -> tuple[int, dict[str, list[str]]]:
        """Resolve top_n + theme_symbols from explicit args or config."""
        if self._top_n is not None and self._theme_symbols is not None:
            return self._top_n, self._theme_symbols
        from shared.llm_scorecard.config import ScorecardConfig

        p = ScorecardConfig.from_yaml().facet_params.get("themes", {})
        top_n = self._top_n if self._top_n is not None else int(p.get("top_n", 3))
        ts = (
            self._theme_symbols
            if self._theme_symbols is not None
            else p.get("theme_symbols", _DEFAULT_THEME_SYMBOLS)
        )
        return top_n, ts

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def capture(self, ctx: CaptureContext) -> FacetPrediction | None:
        mc = ctx.market_context
        if not mc:
            return None
        sector_rotation: dict[str, str] = mc.get("sector_rotation") or {}
        if not sector_rotation:
            return None

        top_n, theme_symbols = self._params()

        # Rank INFLOW themes; break ties alphabetically for determinism.
        strong_themes = sorted(
            [t for t, bias in sector_rotation.items() if _is_strong(bias)],
        )[:top_n]

        if not strong_themes:
            return None

        # Gather constituent symbols for the strong themes (deduplicated, ordered).
        seen: set[str] = set()
        strong_symbols: list[str] = []
        for t in strong_themes:
            for code in theme_symbols.get(t, []):
                if code not in seen:
                    seen.add(code)
                    strong_symbols.append(code)

        if not strong_symbols:
            return None

        return FacetPrediction(
            facet=self.name,
            date_kst=ctx.date_kst,
            captured_at=ctx.now_kst,
            payload={
                "strong_themes": strong_themes,
                "strong_symbols": strong_symbols,
                "sector_rotation_snapshot": sector_rotation,
            },
            confidence=None,
        )

    # ------------------------------------------------------------------
    # Score
    # ------------------------------------------------------------------

    def _all_returns(self, pred: FacetPrediction, mkt: Any) -> dict[str, float]:
        """Equal-weight session_return for every tracked theme symbol with data."""
        _, theme_symbols = self._params()
        all_tracked: list[str] = []
        for codes in theme_symbols.values():
            for c in codes:
                if c not in all_tracked:
                    all_tracked.append(c)

        # No-look-ahead via session_return.
        all_returns: dict[str, float] = {}
        for code in all_tracked:
            r = mkt.session_return(code, pred.date_kst, pred.captured_at)
            if r is not None:
                all_returns[code] = r
        return all_returns

    def baseline(self, pred: FacetPrediction, mkt: Any) -> float:
        """Market mean = equal-weight session_return over the tracked universe.

        Single source of truth for ``baseline_value`` in ``score()``. Returns
        0.0 when no tracked symbol has data (the unscorable market mean).
        """
        market_returns = list(self._all_returns(pred, mkt).values())
        return sum(market_returns) / len(market_returns) if market_returns else 0.0

    def score(self, pred: FacetPrediction, mkt: Any) -> FacetScore:
        strong_symbols: list[str] = pred.payload.get("strong_symbols", [])

        all_returns = self._all_returns(pred, mkt)

        # Market mean (baseline) — computed once, carried into both branches so it
        # is correct even on the unscorable path (non-strong symbols may have data).
        market_returns = list(all_returns.values())
        market_mean = sum(market_returns) / len(market_returns) if market_returns else 0.0

        # Strong-theme returns (intersection with available data).
        strong_returns = [all_returns[c] for c in strong_symbols if c in all_returns]

        if not strong_returns:
            # Unscorable — no outcome data for any strong-theme symbol. Carry the
            # market mean (it may be computable from non-strong symbols).
            return FacetScore(
                facet=self.name,
                date_kst=pred.date_kst,
                correct=None,
                value=0.0,
                economic_proxy=0.0,
                baseline_value=market_mean,
                edge=0.0,
                detail={"reason": "no_outcome_data", "market_mean": market_mean},
                scored_at=datetime.now(),
            )

        strong_mean = sum(strong_returns) / len(strong_returns)
        spread = strong_mean - market_mean  # positive = strong themes outperformed

        return FacetScore(
            facet=self.name,
            date_kst=pred.date_kst,
            correct=spread > 0.0,  # strict: zero/negative spread is a miss
            value=strong_mean,
            economic_proxy=strong_mean,
            baseline_value=market_mean,
            edge=spread,  # edge = value - baseline_value = strong_mean - market_mean
            detail={
                "strong_themes": pred.payload.get("strong_themes", []),
                "strong_mean": strong_mean,
                "market_mean": market_mean,
                "n_strong": len(strong_returns),
                "n_market": len(market_returns),
            },
            scored_at=datetime.now(),
        )


register_facet(ThemesFacet())
