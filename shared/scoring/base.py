"""Phase 2 scoring primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from shared.news.base import NewsItem

VALID_CATEGORIES: frozenset[str] = frozenset(
    {
        "macro_us",
        "macro_kr",
        "geopolitics",
        "samsung",
        "hynix",
        "korea_policy",
        "sector_event",
        "corporate",
        "other",
    }
)
VALID_DIRECTIONS: frozenset[str] = frozenset({"long", "short", "neutral"})


@dataclass(frozen=True)
class ScoredItem:
    news_id: str
    scorer_version: str
    scored_at_ms: int
    category: str
    sentiment: float
    impact_score: float
    direction_bias: str
    confidence: float
    keywords: list[str] = field(default_factory=list)
    reasoning: str = ""
    raw_ref: str = ""
    raw_source: str = ""
    raw_title: str = ""
    raw_url: str = ""
    raw_published_at_ms: int = 0
    raw_keywords: list[str] = field(default_factory=list)

    MAX_KEYWORDS: ClassVar[int] = 5

    def __post_init__(self) -> None:
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"invalid category: {self.category}")
        if self.direction_bias not in VALID_DIRECTIONS:
            raise ValueError(f"invalid direction_bias: {self.direction_bias}")
        if not -1.0 <= self.sentiment <= 1.0:
            raise ValueError(f"sentiment out of range: {self.sentiment}")
        if not 0.0 <= self.impact_score <= 1.0:
            raise ValueError(f"impact_score out of range: {self.impact_score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence}")
        # Clip keywords to MAX_KEYWORDS without mutating caller's list.
        if len(self.keywords) > self.MAX_KEYWORDS:
            object.__setattr__(
                self, "keywords", list(self.keywords[: self.MAX_KEYWORDS])
            )


class Scorer(ABC):
    """Contract for any implementation that turns NewsItem → ScoredItem."""

    version: str

    @abstractmethod
    async def score(self, news: NewsItem) -> ScoredItem:
        """Produce a ScoredItem, or raise on unrecoverable failure."""
        raise NotImplementedError
