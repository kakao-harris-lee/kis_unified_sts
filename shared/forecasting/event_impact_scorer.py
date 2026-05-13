"""Hybrid event impact scorer — rule-based first, LLM fallback."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from shared.forecasting.config import EventScorerConfig
from shared.forecasting.event_taxonomy import EventTaxonomy
from shared.forecasting.llm_event_scorer import LLMScorerClient
from shared.forecasting.models import EventScore

logger = logging.getLogger(__name__)


class EventImpactScorer:
    """Rule-first hybrid scorer. Falls back to LLM only for unmatched text."""

    def __init__(
        self,
        config: EventScorerConfig,
        taxonomy: EventTaxonomy,
        llm_client: LLMScorerClient | None,
    ):
        self.config = config
        self.taxonomy = taxonomy
        self._llm = llm_client

    async def score(
        self, event_text: str, event_type: str | None = None
    ) -> EventScore:
        now = datetime.now(UTC)
        # 1. Explicit event_type passed in → check taxonomy directly
        if event_type:
            for entry in self.taxonomy.events:
                if entry.key == event_type:
                    return EventScore(
                        asof=now,
                        impact_score=float(entry.impact_score),
                        event_type=entry.key,
                        source="rule",
                        raw_text=None,
                        ttl_minutes=self.config.default_ttl_minutes,
                    )
        # 2. Try alias match (rule-based)
        if self.config.rule_first:
            match = self.taxonomy.match(event_text)
            if match is not None:
                return EventScore(
                    asof=now,
                    impact_score=float(match.impact_score),
                    event_type=match.key,
                    source="rule",
                    raw_text=None,
                    ttl_minutes=self.config.default_ttl_minutes,
                )
        # 3. LLM fallback (or neutral if disabled / failed)
        if self.config.llm_fallback_enabled and self._llm is not None:
            try:
                score = await self._llm.score_event_text(event_text)
                return EventScore(
                    asof=now,
                    impact_score=float(score),
                    event_type="UNKNOWN_LLM_SCORED",
                    source="llm",
                    raw_text=event_text[:500],
                    ttl_minutes=self.config.default_ttl_minutes,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "LLM scoring failed (%s); using neutral fallback", e
                )
                return EventScore(
                    asof=now,
                    impact_score=float(self.config.neutral_score_on_failure),
                    event_type="UNKNOWN_LLM_SCORED",
                    source="llm",
                    raw_text=event_text[:500],
                    ttl_minutes=self.config.default_ttl_minutes,
                )
        # 4. LLM disabled and unmatched → unknown_match_score
        return EventScore(
            asof=now,
            impact_score=float(self.taxonomy.unknown_match_score),
            event_type="UNKNOWN_LLM_SCORED",
            source="rule",
            raw_text=None,
            ttl_minutes=self.config.default_ttl_minutes,
        )
