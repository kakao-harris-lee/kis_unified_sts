"""What a ``TimeHealthSnapshot`` says that a consumer actually JUDGES on."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = ["INSTANT_FIELDS", "INSTANT_SUBFIELDS", "judged_content"]

INSTANT_FIELDS: frozenset[str] = frozenset(
    {
        "snapshot_id",
        "canonical_digest",
        "issue_monotonic_value",
        "wall_clock_observation",
    }
)

INSTANT_SUBFIELDS: tuple[tuple[str, str], ...] = (
    ("evaluated_monotonic_anchor", "monotonic_anchor_value"),
    ("time_continuity_identity", "monotonic_anchor_value"),
    ("suspension_status", "suspension_ms"),
)


def judged_content(payload: Mapping[str, Any], reason: str | None) -> dict[str, Any]:
    """The part of a dumped snapshot a consumer judges on, plus this cycle's refusal reason."""
    judged: dict[str, Any] = {
        key: dict(value) if isinstance(value, dict) else value
        for key, value in payload.items()
        if key not in INSTANT_FIELDS
    }
    for section, field_name in INSTANT_SUBFIELDS:
        block = judged.get(section)
        if isinstance(block, dict):
            block.pop(field_name, None)
    judged["wall_clock_observed"] = payload.get("wall_clock_observation") is not None
    judged["last_transition_reason"] = reason
    return judged
