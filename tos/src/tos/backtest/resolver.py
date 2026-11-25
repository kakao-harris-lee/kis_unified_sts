"""The D-E2 resolver slot + the bar → time-coordinate projection (design #33 §3.3/§3.5)."""

from __future__ import annotations

from pydantic import model_validator

from tos.backtest._base import (
    BacktestIntegrityError,
    FrozenModel,
    seal_performance_surface,
)
from tos.backtest.bars import Bar
from tos.capsule import DecisionContextCapsule
from tos.engine import DecisionTickPayload, InstrumentKey, TimeAdmissionInputs
from tos.time import HealthState, SessionContext, UncertaintyInterval

__all__ = [
    "BarTimeProjection",
    "ProvisionalContextResolver",
    "resolved_value_surface_absent",
]


class BarTimeProjection(FrozenModel):
    """Injected bounds that turn a bar coordinate into ``TimeAdmissionInputs`` (design #33 §3.3)."""

    source_age: int
    delay_bounds: tuple[int | None, ...] = ()
    max_age_bound: int
    future_tolerance: int
    snapshot_age_bound: int
    maximum_consumer_age_ms: int
    interval_width: int
    boundary_lag: int
    session_template: SessionContext
    health_state: HealthState

    @model_validator(mode="after")
    def _bounds_are_bounds(self) -> BarTimeProjection:
        """Reject an ill-formed injected bound — an unestablished threshold is not a threshold."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        for name in (
            "max_age_bound",
            "future_tolerance",
            "snapshot_age_bound",
            "maximum_consumer_age_ms",
            "interval_width",
        ):
            value: int = getattr(self, name)
            if value < 0:
                raise BacktestIntegrityError(
                    f"BarTimeProjection.{name} must be non-negative (got {value}) — a negative "
                    "bound is not a bound (ADR-002-008 §9 fail-closed)"
                )
        if self.boundary_lag <= 0:
            raise BacktestIntegrityError(
                f"BarTimeProjection.boundary_lag must be strictly positive (got "
                f"{self.boundary_lag}) — a zero lag would place the session boundary inside the "
                "uncertainty window, which denies (predicates.py:599-604)"
            )
        return self

    def project(self, bar: Bar) -> TimeAdmissionInputs:
        """Project one bar's coordinate onto the engine's injected time inputs."""
        anchor = bar.timestamp_coordinate
        return TimeAdmissionInputs(
            source_age=self.source_age,
            delay_bounds=self.delay_bounds,
            max_age_bound=self.max_age_bound,
            future_tolerance=self.future_tolerance,
            snapshot_age_bound=self.snapshot_age_bound,
            maximum_consumer_age_ms=self.maximum_consumer_age_ms,
            session_context=self.session_template.model_copy(
                update={"boundary_value": anchor - self.boundary_lag}
            ),
            uncertainty_interval=UncertaintyInterval(
                lo=anchor, hi=anchor + self.interval_width
            ),
            health_state=self.health_state,
        )


class ProvisionalContextResolver:
    """⚠ NON-AUTHORITATIVE PROVISIONAL :class:`~tos.engine.DecisionContextResolver` (§3.5)."""

    authority_label = "NON_AUTHORITATIVE_PROVISIONAL"

    def __call__(
        self, capsule: DecisionContextCapsule, *, instrument_key: InstrumentKey
    ) -> DecisionTickPayload:
        """Bind one Decision Context Capsule into a tick payload — reference binding only."""
        return DecisionTickPayload(instrument_key=instrument_key, capsule=capsule)


def resolved_value_surface_absent(payload: DecisionTickPayload) -> bool:
    """Whether the resolved payload reaches **no** value-carrying Critical Input body (§3.5)."""
    snapshot = payload.capsule.critical_input_snapshot
    return set(type(snapshot).model_fields) == {"snapshot_id", "canonical_digest"}
