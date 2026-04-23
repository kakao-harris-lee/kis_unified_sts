import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.news.base import NewsItem
from shared.scoring.budget import BudgetExceeded
from shared.scoring.llm_scorer import LLMScorer
from shared.scoring.validators import ScoringValidationError


def _news() -> NewsItem:
    return NewsItem(
        news_id="n1",
        source="yonhap",
        published_at_ms=1_700_000_000_000,
        received_at_ms=1_700_000_000_500,
        title="FOMC holds rates",
        body="Powell pushes back on cut expectations.",
        url="u",
        source_version="yonhap-v1",
        lang="en",
        keywords=[],
    )


def _fake_openai_response(content: dict) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=json.dumps(content)))]
    resp.usage = MagicMock(prompt_tokens=500, completion_tokens=100)
    return resp


@pytest.fixture
def client():
    c = MagicMock()
    c.chat.completions.create = AsyncMock()
    return c


@pytest.fixture
def budget():
    b = MagicMock()
    b.charge = AsyncMock(return_value=0.001)
    return b


async def test_happy_path(client, budget):
    client.chat.completions.create.return_value = _fake_openai_response(
        {
            "category": "macro_us",
            "sentiment": 0.5,
            "impact_score": 0.9,
            "direction_bias": "long",
            "confidence": 0.85,
            "keywords": ["fomc"],
            "reasoning": "hawkish",
        }
    )
    scorer = LLMScorer(
        client=client,
        budget=budget,
        model="gpt-4o-mini",
        version="gpt-4o-mini-v1",
    )
    item = await scorer.score(_news())
    assert item.category == "macro_us"
    assert item.scorer_version == "gpt-4o-mini-v1"
    budget.charge.assert_awaited_once()


async def test_retries_on_json_error_then_raises(client, budget):
    # First call returns garbage, no retry in single-shot; scorer should raise
    client.chat.completions.create.return_value = _fake_openai_response(
        {"category": "macro_us"}  # missing required fields
    )
    scorer = LLMScorer(
        client=client,
        budget=budget,
        model="gpt-4o-mini",
        version="gpt-4o-mini-v1",
        retries=0,
    )
    with pytest.raises(ScoringValidationError):
        await scorer.score(_news())


async def test_budget_exceeded_raises_before_api_call(client, budget):
    budget.charge.side_effect = BudgetExceeded("cap")
    scorer = LLMScorer(
        client=client,
        budget=budget,
        model="gpt-4o-mini",
        version="gpt-4o-mini-v1",
    )
    # We pre-charge with the estimated cost, so the API call is skipped.
    with pytest.raises(BudgetExceeded):
        await scorer.score(_news())
    client.chat.completions.create.assert_not_awaited()


async def test_timeout_raises_validation_error(client, budget):
    client.chat.completions.create.side_effect = TimeoutError("slow")
    scorer = LLMScorer(
        client=client,
        budget=budget,
        model="gpt-4o-mini",
        version="gpt-4o-mini-v1",
        retries=1,
    )
    with pytest.raises(TimeoutError):
        await scorer.score(_news())
    assert client.chat.completions.create.await_count == 2  # initial + 1 retry
