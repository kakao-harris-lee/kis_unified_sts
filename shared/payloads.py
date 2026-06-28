"""Shared helpers for parsing and normalizing Redis screener/universe payloads.

These utilities are intentionally dependency-free (only stdlib) so that both the
streaming services (``services/fusion_ranker.py``, ``services/theme_discovery.py``)
and the pure scoring layer (``shared/theme_universe/scoring.py``) can reuse a
single implementation instead of maintaining divergent per-service copies.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def decode_redis_value(raw: Any) -> str | None:
    """Decode a raw Redis value (bytes/str/None) into text."""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


def parse_json_dict(raw: Any) -> dict[str, Any]:
    """Parse a Redis value into a dict, returning ``{}`` on any failure."""
    text = decode_redis_value(raw)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.debug("Failed to parse JSON payload: %s", exc)
        return {}
    return parsed if isinstance(parsed, dict) else {}


def clamp01(value: Any) -> float:
    """Clamp an arbitrary value into the inclusive ``[0.0, 1.0]`` range."""
    try:
        numeric = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))


def normalize_scores_by_rank(codes: list[str]) -> dict[str, float]:
    """Map an ordered code list to descending rank scores in ``[0.0, 1.0]``."""
    n = len(codes)
    if n <= 0:
        return {}
    if n == 1:
        return {codes[0]: 1.0}
    return {code: round((n - i - 1) / (n - 1), 6) for i, code in enumerate(codes)}
