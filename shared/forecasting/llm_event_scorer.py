"""LLM-based event impact scorer (fallback for unknown event types)."""
from __future__ import annotations

import json
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)

SCORING_PROMPT_TEMPLATE = """\
You are a financial event impact scorer for KOSPI200 futures.

Score the following news event on a scale 0-100 for **expected near-term
volatility impact magnitude** (not direction). Use these anchors:
  100 = trading halt / circuit breaker / wartime escalation
  85  = central bank rate decision
  70  = major macro release (CPI, NFP)
  50  = top-10 KOSPI200 earnings, surprise corporate action
  30  = minor sector news
  10  = routine corporate disclosure
  0   = irrelevant / noise

Event text:
{text}

Reply with a JSON object: {{"impact_score": <integer 0-100>}}
Reply with the JSON only — no prose, no markdown.
"""


class LLMScorerClient(Protocol):
    async def score_event_text(self, text: str) -> int: ...


class OpenAIEventScorer:
    """Adapter around shared/llm/llm_analyzer.py's OpenAI client.

    Returns integer score 0-100, raises on parse/API failure (caller maps
    to neutral fallback).
    """

    def __init__(self, openai_client: Any, model: str = "gpt-4o-mini"):
        self._client = openai_client
        self._model = model

    async def score_event_text(self, text: str) -> int:
        prompt = SCORING_PROMPT_TEMPLATE.format(text=text[:4000])  # cap input
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=50,
        )
        raw = resp.choices[0].message.content
        parsed = json.loads(raw)
        score = int(parsed["impact_score"])
        if not 0 <= score <= 100:
            raise ValueError(f"out-of-range score: {score}")
        return score
