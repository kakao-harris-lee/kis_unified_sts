"""Field Evaluation element schema (design §2.4 — gap 1)."""

from __future__ import annotations

from tos.capsule._base import FrozenModel
from tos.capsule.field_state import FieldState


class Checks(FrozenModel):
    """Per-field validity checks (ADR §11 line 304)."""

    range: FieldState | None = None
    rate: FieldState | None = None
    crossed_state: FieldState | None = None
    cross_field: FieldState | None = None
    mapping: FieldState | None = None
    unit: FieldState | None = None
    venue_session: FieldState | None = None


class Freshness(FrozenModel):
    """Freshness evaluation for a field (ADR §11 line 303; §14)."""

    source_age: int | None = None
    receipt_age: int | None = None
    within_bound: bool | None = None
    bound_ref: str | None = None


class FieldEvaluation(FrozenModel):
    """Evaluation of one safety fact or observation field (design §2.4)."""

    field_ref: str | None = None
    state: FieldState = FieldState.UNKNOWN
    checks: Checks = Checks()
    freshness: Freshness = Freshness()
    worst_credible_bound: str | None = None
    blocking: bool = False
