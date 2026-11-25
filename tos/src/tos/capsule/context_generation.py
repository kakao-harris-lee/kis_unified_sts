"""Context Generation ordering predicate (design §2.8, §5.7)."""

from __future__ import annotations


def generation_can_authorize(
    subject_generation: int | None,
    latest_restrictive_generation: int | None,
) -> bool:
    """Whether ``subject_generation`` may authorize new risk (design §5.7)."""
    if subject_generation is None or latest_restrictive_generation is None:
        return False
    return subject_generation >= latest_restrictive_generation
