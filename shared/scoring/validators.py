"""LLM output parsing + schema validation."""

from __future__ import annotations

import json
from typing import Any

from shared.scoring.base import VALID_CATEGORIES, VALID_DIRECTIONS

_REQUIRED_FIELDS = (
    "category",
    "sentiment",
    "impact_score",
    "direction_bias",
    "confidence",
)
_NUMERIC_FIELDS = ("sentiment", "impact_score", "confidence")


class ScoringValidationError(ValueError):
    """LLM output failed schema validation."""


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Parse and validate a JSON string produced by an LLM scorer.

    Args:
        raw: Raw JSON string from the LLM response.

    Returns:
        Validated dict with numeric fields coerced to float and optional
        fields defaulted.

    Raises:
        ScoringValidationError: If the JSON is malformed, missing required
            fields, contains invalid category/direction values, or numeric
            fields cannot be coerced.
    """
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScoringValidationError(f"malformed json: {exc}") from exc

    if not isinstance(obj, dict):
        raise ScoringValidationError("top-level must be object")

    for field in _REQUIRED_FIELDS:
        if field not in obj:
            raise ScoringValidationError(f"missing required field: {field}")

    for field in _NUMERIC_FIELDS:
        try:
            obj[field] = float(obj[field])
        except (TypeError, ValueError) as exc:
            raise ScoringValidationError(f"field {field} must be numeric") from exc

    if obj["category"] not in VALID_CATEGORIES:
        raise ScoringValidationError(f"invalid category: {obj['category']!r}")
    if obj["direction_bias"] not in VALID_DIRECTIONS:
        raise ScoringValidationError(
            f"invalid direction_bias: {obj['direction_bias']!r}"
        )

    obj.setdefault("keywords", [])
    obj.setdefault("reasoning", "")
    return obj
