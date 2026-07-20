"""Context Generation ordering predicate (design §2.8, §5.7).

ADR-002-018 §5.7 (line 134-136): an older generation cannot authorize new risk
after a newer *restrictive* generation. This module models only the monotonic
ordering predicate; the distributed-deployment / fence runtime is out of scope
(design §0.2). The capsule exposes ``context_generation`` and
``validity.invalidation_generation`` (both Layer-1) as the integers this
predicate consumes (design §2.8).

Pure module: stdlib only; no pydantic, no ``shared.*``.
"""

from __future__ import annotations


def generation_can_authorize(
    subject_generation: int | None,
    latest_restrictive_generation: int | None,
) -> bool:
    """Whether ``subject_generation`` may authorize new risk (design §5.7).

    Fail-closed: an unknown subject generation, or an unknown latest restrictive
    generation, denies authorization. Otherwise a subject strictly older than the
    latest restrictive generation is denied (monotonic non-revival, design §2.8).

    Args:
        subject_generation: The context generation seeking to authorize new risk.
        latest_restrictive_generation: The newest generation that imposed a
            restriction/invalidation.

    Returns:
        ``True`` only if ``subject_generation`` is known and not older than
        ``latest_restrictive_generation``.
    """
    if subject_generation is None or latest_restrictive_generation is None:
        return False
    return subject_generation >= latest_restrictive_generation
