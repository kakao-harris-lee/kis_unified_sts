"""Field Evaluation element schema (design §2.4 — gap 1).

``CRITICAL-INPUT-SNAPSHOT-template.yaml:field_evaluations: []`` (line 29) leaves
the element schema empty. This module authors it from ADR-002-018 §11 (line
294-312).

Freshness bounds are **injected only** (design §2.4, §8): ``within_bound`` is
evaluated against the policy parameter named by ``bound_ref``; no threshold is
hard-coded. The evaluation function is in :mod:`tos.capsule.predicates`; this
module carries the recorded result.

Pure module: ``pydantic`` + stdlib only.
"""

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
    """Freshness evaluation for a field (ADR §11 line 303; §14).

    ``within_bound`` is computed against the policy bound identified by
    ``bound_ref`` (design §2.4, §8). A missing window (``within_bound=None``)
    is fail-closed at the predicate layer (UNKNOWN; design §6.2).
    """

    source_age: int | None = None
    receipt_age: int | None = None
    within_bound: bool | None = None
    bound_ref: str | None = None


class FieldEvaluation(FrozenModel):
    """Evaluation of one safety fact or observation field (design §2.4).

    Frozen element of ``CriticalInputSnapshot.field_evaluations``. ``blocking``
    marks whether this field participates in the conservative snapshot-validity
    gate (ADR §11 line 307, 311; design §5.1). ``worst_credible_bound`` feeds the
    UNKNOWN-consumes-capacity predicate (CII-INV-012, design §5.2).
    """

    field_ref: str | None = None
    state: FieldState = FieldState.UNKNOWN
    checks: Checks = Checks()
    freshness: Freshness = Freshness()
    worst_credible_bound: str | None = None
    blocking: bool = False
