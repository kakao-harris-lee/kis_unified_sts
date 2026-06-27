# tests/unit/scoring/test_base.py
from dataclasses import FrozenInstanceError

import pytest

from shared.scoring.base import ScoredItem


def _valid_kwargs():
    return {
        "news_id": "n1",
        "scorer_version": "gpt-4o-mini-v1",
        "scored_at_ms": 1_700_000_000_000,
        "category": "macro_us",
        "sentiment": 0.4,
        "impact_score": 0.8,
        "direction_bias": "long",
        "confidence": 0.85,
        "keywords": ["fomc", "rate"],
        "reasoning": "FOMC statement hawkish-neutral",
        "raw_ref": "1700000000000-0",
    }


def test_scored_item_accepts_valid_input():
    item = ScoredItem(**_valid_kwargs())
    assert item.category == "macro_us"
    assert item.direction_bias == "long"


def test_scored_item_is_frozen():
    item = ScoredItem(**_valid_kwargs())
    with pytest.raises(FrozenInstanceError):
        item.sentiment = 0.1  # type: ignore[misc]


@pytest.mark.parametrize(
    "field, bad",
    [
        ("sentiment", 1.5),
        ("sentiment", -1.5),
        ("impact_score", -0.1),
        ("impact_score", 1.1),
        ("confidence", 2.0),
    ],
)
def test_scored_item_rejects_out_of_range(field, bad):
    kwargs = _valid_kwargs()
    kwargs[field] = bad
    with pytest.raises(ValueError):
        ScoredItem(**kwargs)


def test_scored_item_rejects_unknown_direction_bias():
    kwargs = _valid_kwargs()
    kwargs["direction_bias"] = "up"
    with pytest.raises(ValueError):
        ScoredItem(**kwargs)


def test_scored_item_keywords_clipped_to_five():
    kwargs = _valid_kwargs()
    kwargs["keywords"] = [f"kw{i}" for i in range(20)]
    item = ScoredItem(**kwargs)
    assert len(item.keywords) == 5
