"""OpenAI GPT-4o-mini scorer with budget guard + retries."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from shared.news.base import NewsItem
from shared.scoring.base import ScoredItem, Scorer
from shared.scoring.budget import DailyBudget
from shared.scoring.prompt import PROMPT_V1, render
from shared.scoring.validators import parse_llm_json

# Rough cost model for gpt-4o-mini: $0.15 / 1M input, $0.60 / 1M output (2026-04 rates).
_COST_PER_INPUT_TOKEN_USD = 0.15 / 1_000_000
_COST_PER_OUTPUT_TOKEN_USD = 0.60 / 1_000_000
_ESTIMATED_PROMPT_COST_USD = 0.0005  # pre-charge estimate


class LLMScorer(Scorer):
    """Score a :class:`~shared.news.base.NewsItem` using an OpenAI chat model.

    The scorer pre-charges :attr:`_ESTIMATED_PROMPT_COST_USD` to the daily
    budget *before* calling the API so a tripped cap stops spend immediately.
    After a successful parse the actual token cost is calculated from
    ``resp.usage`` and the delta (if positive) is charged to the budget.

    Args:
        client: An ``openai.AsyncOpenAI``-compatible client (injected for
            testability — we never instantiate it internally).
        budget: :class:`~shared.scoring.budget.DailyBudget` instance that
            guards the daily USD cap.
        model: OpenAI model identifier, e.g. ``"gpt-4o-mini"``.
        version: Human-readable scorer version tag embedded in
            :attr:`~shared.scoring.base.ScoredItem.scorer_version`.
        temperature: Sampling temperature (default ``0.0`` for deterministic
            output).
        max_tokens: Maximum completion tokens to request.
        timeout_seconds: Per-attempt wall-clock timeout.
        retries: Number of *additional* attempts after the first failure
            (e.g. ``retries=2`` means up to 3 total attempts).
        prompt_template: Prompt template string (defaults to ``PROMPT_V1``).
        body_max_chars: Maximum characters of the news body passed to the
            prompt (truncated silently if longer).
    """

    def __init__(
        self,
        *,
        client: Any,  # openai.AsyncOpenAI
        budget: DailyBudget,
        model: str,
        version: str,
        temperature: float = 0.0,
        max_tokens: int = 250,
        timeout_seconds: float = 5.0,
        retries: int = 2,
        prompt_template: str = PROMPT_V1,
        body_max_chars: int = 2000,
    ) -> None:
        self.client = client
        self.budget = budget
        self.model = model
        self.version = version
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.prompt_template = prompt_template
        self.body_max_chars = body_max_chars

    # ------------------------------------------------------------------
    # Scorer contract
    # ------------------------------------------------------------------

    async def score(self, news: NewsItem) -> ScoredItem:
        """Score *news* and return a :class:`~shared.scoring.base.ScoredItem`.

        Raises:
            BudgetExceeded: If the pre-charge pushes the daily total over the
                configured limit (no API call is made in this case).
            ScoringValidationError: If all attempts return JSON that fails
                schema validation.
            TimeoutError: If all attempts time out.
        """
        # Pre-charge estimated cost; raises BudgetExceeded before any API call.
        await self.budget.charge(_ESTIMATED_PROMPT_COST_USD)

        prompt = render(
            self.prompt_template,
            title=news.title,
            body=news.body,
            body_max_chars=self.body_max_chars,
        )

        last_exc: Exception | None = None
        for _attempt in range(self.retries + 1):
            try:
                resp = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        response_format={"type": "json_object"},
                    ),
                    timeout=self.timeout_seconds,
                )
                raw: str = resp.choices[0].message.content or ""
                payload = parse_llm_json(raw)

                # Charge the delta between actual and estimated cost.
                actual_cost = self._actual_cost(resp)
                delta = actual_cost - _ESTIMATED_PROMPT_COST_USD
                if delta > 0:
                    await self.budget.charge(delta)

                return ScoredItem(
                    news_id=news.news_id,
                    scorer_version=self.version,
                    scored_at_ms=int(time.time() * 1000),
                    category=payload["category"],
                    sentiment=float(payload["sentiment"]),
                    impact_score=float(payload["impact_score"]),
                    direction_bias=payload["direction_bias"],
                    confidence=float(payload["confidence"]),
                    keywords=list(payload.get("keywords", []))[
                        : ScoredItem.MAX_KEYWORDS
                    ],
                    reasoning=str(payload.get("reasoning", ""))[:200],
                )
            except TimeoutError as exc:
                last_exc = exc
                continue

        # All attempts exhausted — re-raise the last exception.
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _actual_cost(resp: Any) -> float:
        """Compute actual USD cost from ``resp.usage`` token counts."""
        usage = resp.usage
        input_cost = getattr(usage, "prompt_tokens", 0) * _COST_PER_INPUT_TOKEN_USD
        output_cost = (
            getattr(usage, "completion_tokens", 0) * _COST_PER_OUTPUT_TOKEN_USD
        )
        return input_cost + output_cost
