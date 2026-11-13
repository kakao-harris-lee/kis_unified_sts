"""What a ``TimeHealthSnapshot`` says that a consumer actually JUDGES on.

:meth:`tos_runtime.time.service.TrustworthyTimeService.evaluate` appends a
``TIME_HEALTH_SNAPSHOT`` evidence row when this value moves, and otherwise only
once per ``time_health_snapshot_heartbeat_ms``. See that service's module
docstring for the cadence contract and the incident behind it; this module owns
only the comparison itself (split out of ``service.py`` to keep that module
inside the 1000-line budget in ``config/tos_size_budget.yaml``).

The whole design rule is in :func:`judged_content`: the fingerprint is built by
SUBTRACTION, so a field added to the kernel artifact later counts as judged
content automatically.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = ["INSTANT_FIELDS", "INSTANT_SUBFIELDS", "judged_content"]

#: Top-level dumped-snapshot fields that carry THIS CYCLE'S INSTANT, not its judgement, and
#: so are excluded from the on-change fingerprint. ``canonical_digest`` is
#: ``f(covered content)`` and the covered content includes the instants, so it moves every
#: cycle by construction.
#:
#: ``wall_clock_observation`` is the raw reference reading. **It is not inert.** The kernel's
#: own :class:`~tos.time.TimeHealthSnapshot` docstring calls it "audit-only", and that is a
#: statement about the KERNEL's predicates ("no predicate reads it for expiry/freshness/
#: ordering") — but THIS RUNTIME serves the value to real consumers through
#: ``TrustworthyTimeService.wall_clock_now`` (the calendar session phase, via
#: ``TrustedWallClockReference``, and ``RuntimeTimeProjection``'s ``source_age`` anchor),
#: ``wall_clock_now_if_fresh`` (the egress trading-date stamp) and
#: ``wall_clock_at_monotonic`` (the KIS quote-request anchor).
#:
#: Those consumers all read the LIVE in-memory snapshot, which is still re-issued every cycle
#: and is untouched by this gate — excluding the value here changes nothing about what they
#: see. What it does change is the EVIDENCE: **the exact reading is durably recorded only on
#: a judged-content change or at the heartbeat**, so the evidence trail carries a sample of
#: that series rather than every value. Its PRESENCE stays in the fingerprint (see
#: :func:`judged_content`), so a cycle that first acquires or loses a reading always writes.
INSTANT_FIELDS: frozenset[str] = frozenset(
    {
        "snapshot_id",
        "canonical_digest",
        "issue_monotonic_value",
        "wall_clock_observation",
    }
)

#: ``(section, field)`` pairs of the same kind, one level down. The two anchor values are this
#: cycle's monotonic reading and the ratcheted high-water mark; ``suspension_status
#: .suspension_ms`` is the raw ``max(0, Δwall - Δmono)`` magnitude, which jitters by a
#: millisecond on a quiet host — its JUDGEMENT, the sibling ``suspended`` bool the kernel's
#: ``anchor_valid`` actually turns on, stays in the fingerprint.
INSTANT_SUBFIELDS: tuple[tuple[str, str], ...] = (
    ("evaluated_monotonic_anchor", "monotonic_anchor_value"),
    ("time_continuity_identity", "monotonic_anchor_value"),
    ("suspension_status", "suspension_ms"),
)


def judged_content(payload: Mapping[str, Any], reason: str | None) -> dict[str, Any]:
    """The part of a dumped snapshot a consumer judges on, plus this cycle's refusal reason.

    Built by SUBTRACTION, never by listing what to keep: a field added to
    :class:`~tos.time.TimeHealthSnapshot` later counts as judged content automatically and
    fails toward writing a row, rather than being silently dropped from the comparison by an
    allowlist nobody updated.

    Args:
        payload: ``TimeHealthSnapshot.model_dump(mode="json")`` for this cycle.
        reason: ``TrustworthyTimeService.last_transition_reason`` — a refused transition is a
            real change a consumer reads, and it is not carried on the snapshot at all, so
            comparing only the dump would miss a cycle that newly started refusing.

    Returns:
        A plain mapping to compare with ``==`` against the previous evidenced cycle's.
    """
    judged: dict[str, Any] = {
        key: dict(value) if isinstance(value, dict) else value
        for key, value in payload.items()
        if key not in INSTANT_FIELDS
    }
    for section, field_name in INSTANT_SUBFIELDS:
        block = judged.get(section)
        if isinstance(block, dict):
            block.pop(field_name, None)
    # Presence, not value: a cycle that first acquires (or loses) a wall-clock reading has
    # changed what it can attest, and the TIME_WALL_CLOCK_EXPOSED announcement cites the
    # snapshot_id of exactly such a cycle — it must not cite a row that was never written.
    judged["wall_clock_observed"] = payload.get("wall_clock_observation") is not None
    judged["last_transition_reason"] = reason
    return judged
