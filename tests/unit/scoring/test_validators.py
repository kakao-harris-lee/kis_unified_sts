# tests/unit/scoring/test_validators.py
import json

import pytest

from shared.scoring.validators import (
    ScoringValidationError,
    parse_llm_json,
)

VALID_JSON = json.dumps(
    {
        "category": "macro_us",
        "sentiment": 0.5,
        "impact_score": 0.9,
        "direction_bias": "long",
        "confidence": 0.8,
        "keywords": ["fomc"],
        "reasoning": "ok",
    }
)


def test_parse_valid_json_produces_dict():
    result = parse_llm_json(VALID_JSON)
    assert result["category"] == "macro_us"
    assert result["direction_bias"] == "long"


def test_parse_rejects_missing_field():
    bad = json.dumps({"category": "macro_us"})
    with pytest.raises(ScoringValidationError):
        parse_llm_json(bad)


def test_parse_rejects_unknown_category():
    payload = json.loads(VALID_JSON)
    payload["category"] = "unicorn"
    with pytest.raises(ScoringValidationError):
        parse_llm_json(json.dumps(payload))


def test_parse_rejects_malformed_json():
    with pytest.raises(ScoringValidationError):
        parse_llm_json("not-json")


def test_parse_coerces_numeric_strings():
    payload = json.loads(VALID_JSON)
    payload["sentiment"] = "0.3"  # LLM sometimes quotes floats
    result = parse_llm_json(json.dumps(payload))
    assert result["sentiment"] == pytest.approx(0.3)
