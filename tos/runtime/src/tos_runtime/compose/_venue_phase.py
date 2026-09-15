"""Step 3's per-attempt ``observed_session_phase`` read (TOS Phase 5 W5 plan §2
decision 5; team-lead review follow-up, 2026-09-12).

**No private-attribute write into a kernel object.** ``VenueConstraintStage``
(``tos.egressgw.construction``) stores ``observed_session_phase`` once, at
construction, as a private attribute with no public setter. An earlier version
of this wiring wrote ``_observed_session_phase`` directly on a single,
long-lived ``VenueConstraintStage`` instance (a reported shim) — team-lead
review flagged this as touching a kernel object's internals from the runtime
side, which this module retires: :class:`VenuePhaseStage` instead builds a
FRESH ``VenueConstraintStage`` via its own public constructor on EVERY call,
reading ``phase_reader()`` fresh each time. The kernel class itself is
untouched; the runtime only ever calls its public API.

Split out of :mod:`tos_runtime.compose._wiring` purely for that module's own
size budget (``config/tos_size_budget.yaml`` — module ceiling 1141 lines) —
no behavioural difference from having this class inline there.
"""

from __future__ import annotations

from collections.abc import Callable

from tos.egressgw import VenueConstraintStage
from tos.engine import StageRequest, StageVerdict
from tos.venue import (
    ActionClass,
    OrderAdmissibilityDecision,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)

from tos_runtime.compose._types import ConstructionConfig

__all__ = ["VenuePhaseStage", "build_venue_phase_stage"]


class VenuePhaseStage:
    """Step 3, rebuilt fresh on every call with a freshly-read
    ``observed_session_phase`` (module docstring).

    Exposes ``resolved_shape``/``shape_constraints`` — the same read surface
    :class:`~tos_runtime.compose.context.ComposeContextResolver` (item 11) and
    :class:`~tos_runtime.compose._types.ComposedRuntime` already read off a
    raw ``VenueConstraintStage`` — so those call sites need no change.
    ``resolved_shape`` proxies to the LAST built instance (the one that
    actually processed the most recent attempt); ``shape_constraints`` is a
    static constructor input, unchanged per attempt, so it is returned
    directly without needing the last instance.
    """

    def __init__(
        self,
        *,
        phase_reader: Callable[[], str | None],
        action_class: ActionClass | None,
        snapshot: VenueConstraintSnapshot | None,
        policy: VenueConstraintPolicy | None,
        shape: OrderShapeFields | None,
        constraints: VenueShapeConstraints | None,
        decision: OrderAdmissibilityDecision | None = None,
        shape_price_field_key: str | None = None,
    ) -> None:
        self._phase_reader = phase_reader
        self._action_class = action_class
        self._snapshot = snapshot
        self._policy = policy
        self._shape = shape
        self._constraints = constraints
        self._decision = decision
        self._shape_price_field_key = shape_price_field_key
        #: The most recently built stage, or ``None`` before any call — never
        #: read for judgement, only for the two post-hoc properties below.
        self._last_stage: VenueConstraintStage | None = None

    def __call__(self, request: StageRequest) -> StageVerdict:
        stage = VenueConstraintStage(
            observed_session_phase=self._phase_reader(),
            action_class=self._action_class,
            snapshot=self._snapshot,
            policy=self._policy,
            shape=self._shape,
            constraints=self._constraints,
            decision=self._decision,
            shape_price_field_key=self._shape_price_field_key,
        )
        self._last_stage = stage
        return stage(request)

    @property
    def resolved_shape(self) -> OrderShapeFields | None:
        return None if self._last_stage is None else self._last_stage.resolved_shape

    @property
    def shape_constraints(self) -> VenueShapeConstraints | None:
        return self._constraints


def build_venue_phase_stage(
    construction: ConstructionConfig, phase_reader: Callable[[], str | None]
) -> VenuePhaseStage:
    """The factory :func:`~tos_runtime.compose._wiring._build_construction_stages`
    calls for step 3 — kept out of ``_wiring.py`` for its own size budget."""
    return VenuePhaseStage(
        phase_reader=phase_reader,
        action_class=construction.action_class,
        snapshot=construction.venue_snapshot,
        policy=construction.venue_policy,
        shape=construction.order_shape,
        constraints=construction.venue_shape_constraints,
        decision=construction.venue_decision,
        shape_price_field_key=construction.shape_price_field_key,
    )
