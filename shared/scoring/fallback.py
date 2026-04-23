"""Neutral-defaults scorer used when LLM fails."""

from __future__ import annotations

import time

from shared.news.base import NewsItem
from shared.scoring.base import ScoredItem, Scorer


class FallbackScorer(Scorer):
    """Scorer that emits all-neutral defaults without calling any external API.

    Used as a safety net when the LLM scorer raises (budget exceeded, timeout,
    JSON parse failure, or network error).  All numeric fields are set to zero
    and ``direction_bias`` to ``"neutral"`` so downstream consumers can detect
    that this item was not meaningfully scored.
    """

    def __init__(self, version: str = "fallback-neutral-v1") -> None:
        self.version = version

    async def score(self, news: NewsItem) -> ScoredItem:
        """Return a neutral ScoredItem without any external calls.

        Args:
            news: The raw news item to pass through.

        Returns:
            ScoredItem with all numeric scores at 0.0 and ``direction_bias``
            set to ``"neutral"``.
        """
        return ScoredItem(
            news_id=news.news_id,
            scorer_version=self.version,
            scored_at_ms=int(time.time() * 1000),
            category="other",
            sentiment=0.0,
            impact_score=0.0,
            direction_bias="neutral",
            confidence=0.0,
            keywords=[],
            reasoning=f"fallback: {self.version}",
        )
