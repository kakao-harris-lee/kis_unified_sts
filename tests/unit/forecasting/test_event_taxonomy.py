"""Tests for event taxonomy loader + rule-based matcher."""
from pathlib import Path

import pytest

from shared.forecasting.event_taxonomy import EventTaxonomy


@pytest.fixture
def taxonomy(tmp_path: Path):
    yaml_path = tmp_path / "event_taxonomy.yaml"
    yaml_path.write_text(
        """
events:
  - key: FOMC_RATE_DECISION
    impact_score: 90
    aliases: ["FOMC", "Fed rate decision"]
  - key: BOK_RATE_DECISION
    impact_score: 85
    aliases: ["BOK", "한국은행"]
  - key: KRX_TRADING_HALT
    impact_score: 95
    aliases: ["trading halt", "circuit breaker"]
unknown_match_score: 40
"""
    )
    return EventTaxonomy.load(yaml_path)


def test_loads_all_events(taxonomy):
    assert len(taxonomy.events) == 3
    keys = [e.key for e in taxonomy.events]
    assert "FOMC_RATE_DECISION" in keys


def test_match_by_alias_exact(taxonomy):
    match = taxonomy.match("FOMC announces 25bp hike")
    assert match is not None
    assert match.key == "FOMC_RATE_DECISION"
    assert match.impact_score == 90


def test_match_by_alias_case_insensitive(taxonomy):
    match = taxonomy.match("fomc decision today")
    assert match is not None
    assert match.key == "FOMC_RATE_DECISION"


def test_match_korean_alias(taxonomy):
    match = taxonomy.match("한국은행 금리 동결 결정")
    assert match is not None
    assert match.key == "BOK_RATE_DECISION"
    assert match.impact_score == 85


def test_no_match_returns_none(taxonomy):
    match = taxonomy.match("Random unrelated news headline")
    assert match is None


def test_all_weights_within_bounds(taxonomy):
    for event in taxonomy.events:
        assert 0 <= event.impact_score <= 100


def test_match_first_alias_wins_on_ambiguity(taxonomy):
    # "trading halt" matches KRX_TRADING_HALT first
    match = taxonomy.match("trading halt issued")
    assert match.key == "KRX_TRADING_HALT"
