"""Tests for hybrid event impact scorer (rule + LLM fallback)."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from shared.forecasting.config import EventScorerConfig
from shared.forecasting.event_impact_scorer import EventImpactScorer
from shared.forecasting.event_taxonomy import EventTaxonomy


@pytest.fixture
def taxonomy(tmp_path: Path):
    yaml_path = tmp_path / "event_taxonomy.yaml"
    yaml_path.write_text(
        """
events:
  - key: FOMC_RATE_DECISION
    impact_score: 90
    aliases: ["FOMC"]
unknown_match_score: 40
"""
    )
    return EventTaxonomy.load(yaml_path)


@pytest.fixture
def cfg():
    return EventScorerConfig(
        default_ttl_minutes=30,
        rule_first=True,
        llm_fallback_enabled=True,
        neutral_score_on_failure=50,
    )


def test_rule_match_returns_taxonomy_weight(cfg, taxonomy):
    scorer = EventImpactScorer(cfg, taxonomy=taxonomy, llm_client=None)

    async def _run():
        return await scorer.score("FOMC raises rates by 25bp")

    result = asyncio.run(_run())
    assert result.event_type == "FOMC_RATE_DECISION"
    assert result.impact_score == 90
    assert result.source == "rule"


def test_unknown_event_falls_back_to_llm(cfg, taxonomy):
    fake_llm = AsyncMock()
    fake_llm.score_event_text = AsyncMock(return_value=72)
    scorer = EventImpactScorer(cfg, taxonomy=taxonomy, llm_client=fake_llm)

    result = asyncio.run(scorer.score("Unrelated headline text"))
    assert result.source == "llm"
    assert result.impact_score == 72
    assert result.event_type == "UNKNOWN_LLM_SCORED"
    fake_llm.score_event_text.assert_awaited_once()


def test_llm_failure_returns_neutral(cfg, taxonomy):
    fake_llm = AsyncMock()
    fake_llm.score_event_text = AsyncMock(side_effect=RuntimeError("API down"))
    scorer = EventImpactScorer(cfg, taxonomy=taxonomy, llm_client=fake_llm)

    result = asyncio.run(scorer.score("Some random text"))
    assert result.source == "llm"
    assert result.impact_score == cfg.neutral_score_on_failure


def test_llm_disabled_skips_unknown_event(cfg, taxonomy):
    cfg.llm_fallback_enabled = False
    scorer = EventImpactScorer(cfg, taxonomy=taxonomy, llm_client=None)

    result = asyncio.run(scorer.score("Some random text"))
    assert result.source == "rule"
    assert result.impact_score == taxonomy.unknown_match_score


def test_ttl_uses_config_default(cfg, taxonomy):
    scorer = EventImpactScorer(cfg, taxonomy=taxonomy, llm_client=None)
    result = asyncio.run(scorer.score("FOMC release"))
    assert result.ttl_minutes == cfg.default_ttl_minutes
