"""Golden-set regression — run whenever scorer_version changes.

During the Phase 2 48h gate, pull ~100 random items from `stream:news.raw`,
hand-label category + direction_bias, and overwrite
`tests/fixtures/news_scoring_golden.json`. Then set RUN_GOLDEN=1 in CI
to enforce the agreement thresholds.

Skipped by default to keep CI offline + free.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.news.base import NewsItem
from shared.scoring.llm_scorer import LLMScorer

GOLDEN = Path("tests/fixtures/news_scoring_golden.json")


@pytest.mark.skipif(
    not os.environ.get("RUN_GOLDEN"),
    reason="requires RUN_GOLDEN=1 + network + OPENAI_API_KEY",
)
def test_category_agreement_at_least_70_percent() -> None:
    items = json.loads(GOLDEN.read_text())
    if not items:
        pytest.skip("golden set empty — populate during 48h gate")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    budget = MagicMock()
    budget.charge = AsyncMock(return_value=0.0)
    scorer = LLMScorer(
        client=client,
        budget=budget,
        model="gpt-4o-mini",
        version="gpt-4o-mini-v1",
    )

    async def _run() -> float:
        hits = 0
        for row in items:
            news = NewsItem(
                news_id=row["news_id"],
                source="golden",
                published_at_ms=0,
                received_at_ms=0,
                title=row["title"],
                body=row.get("body", ""),
                url="",
                source_version="",
                lang="ko",
                keywords=[],
            )
            item = await scorer.score(news)
            if item.category == row["human_label"]["category"]:
                hits += 1
        return hits / len(items)

    agreement = asyncio.run(_run())
    assert agreement >= 0.70, f"category agreement {agreement:.2%} < 70%"


@pytest.mark.skipif(
    not os.environ.get("RUN_GOLDEN"),
    reason="requires RUN_GOLDEN=1 + network + OPENAI_API_KEY",
)
def test_direction_agreement_at_least_75_percent() -> None:
    items = json.loads(GOLDEN.read_text())
    if not items:
        pytest.skip("golden set empty — populate during 48h gate")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    budget = MagicMock()
    budget.charge = AsyncMock(return_value=0.0)
    scorer = LLMScorer(
        client=client,
        budget=budget,
        model="gpt-4o-mini",
        version="gpt-4o-mini-v1",
    )

    async def _run() -> float:
        hits = 0
        for row in items:
            news = NewsItem(
                news_id=row["news_id"],
                source="golden",
                published_at_ms=0,
                received_at_ms=0,
                title=row["title"],
                body=row.get("body", ""),
                url="",
                source_version="",
                lang="ko",
                keywords=[],
            )
            item = await scorer.score(news)
            if item.direction_bias == row["human_label"]["direction_bias"]:
                hits += 1
        return hits / len(items)

    agreement = asyncio.run(_run())
    assert agreement >= 0.75, f"direction agreement {agreement:.2%} < 75%"


def test_golden_fixture_exists_and_is_json_array() -> None:
    """Smoke test that runs in default CI — fixture file must parse as JSON array."""
    assert GOLDEN.is_file()
    data = json.loads(GOLDEN.read_text())
    assert isinstance(data, list)
