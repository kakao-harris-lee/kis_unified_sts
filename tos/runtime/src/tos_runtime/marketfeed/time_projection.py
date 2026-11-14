"""``RuntimeTimeProjection`` — the runtime :class:`~tos.marketfeed.TimeCoordinateProjection`"""

from __future__ import annotations

from typing import Protocol

from tos.engine import TimeAdmissionInputs
from tos.marketfeed import TimeCoordinateProjection
from tos.time import SessionContext, UncertaintyInterval

from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TrustworthyTimeService

__all__ = ["RuntimeTimeProjection", "TimeProjectionConfigError"]

_DELAY_BOUND_FIELDS: tuple[str, ...] = (
    "max_time_transport_and_queue_uncertainty_ms",
    "max_clock_domain_conversion_uncertainty_ms",
    "max_time_source_precision_ms",
    "max_time_source_sequence_gap_ms",
)


class TimeProjectionConfigError(Exception):
    """Raised when a :class:`RuntimeTimeProjection` cannot be constructed fail-closed."""


class _SessionContextReader(Protocol):
    """Structural shape :class:`RuntimeTimeProjection` needs from a session-facts owner — matches"""

    def session_context(self, instrument_class: str) -> SessionContext | None: ...


class RuntimeTimeProjection:
    """The runtime ``(*, as_of: int | None) -> TimeAdmissionInputs`` projection (plan §2 decision 6)."""

    def __init__(
        self,
        *,
        config: TrustworthyTimeConfig,
        time_service: TrustworthyTimeService,
        session_owner: _SessionContextReader,
        instrument_class: str,
        snapshot_age_bound: int,
        interval_width: int,
    ) -> None:
        missing = [
            field_name
            for field_name in _DELAY_BOUND_FIELDS
            if getattr(config, field_name, None) is None
        ]
        if missing:
            raise TimeProjectionConfigError(
                "RuntimeTimeProjection requires every delay_bounds term to be established — "
                f"missing/unestablished: {missing}. Omitting one would silently sum three terms "
                "instead of four, making the conservative freshness age SMALLER — see "
                "TimeProjectionConfigError's own docstring."
            )
        if snapshot_age_bound is None or snapshot_age_bound < 0:
            raise TimeProjectionConfigError(
                "RuntimeTimeProjection requires snapshot_age_bound to be a non-negative int "
                f"(got {snapshot_age_bound!r}) — mirrors BarTimeProjection's own "
                "non-negativity check on the identical field."
            )
        if interval_width is None or interval_width < 0:
            raise TimeProjectionConfigError(
                "RuntimeTimeProjection requires interval_width to be a non-negative int "
                f"(got {interval_width!r}) — mirrors BarTimeProjection's own non-negativity "
                "check on the identical field."
            )
        self._config = config
        self._time_service = time_service
        self._session_owner = session_owner
        self._instrument_class = instrument_class
        self._snapshot_age_bound = snapshot_age_bound
        self._interval_width = interval_width

    def __call__(self, *, as_of: int | None) -> TimeAdmissionInputs:
        """Project ``as_of`` onto the engine's injected time coordinates (module docstring)."""
        wall_clock_now = self._time_service.wall_clock_now()
        source_age = (
            wall_clock_now - as_of
            if wall_clock_now is not None and as_of is not None
            else None
        )
        uncertainty_interval = (
            UncertaintyInterval(
                lo=wall_clock_now, hi=wall_clock_now + self._interval_width
            )
            if wall_clock_now is not None
            else None
        )
        return TimeAdmissionInputs(
            source_age=source_age,
            delay_bounds=tuple(
                getattr(self._config, field_name) for field_name in _DELAY_BOUND_FIELDS
            ),
            max_age_bound=self._config.max_time_conservative_freshness_age_ms,
            future_tolerance=self._config.max_future_timestamp_tolerance_ms,
            snapshot_age_bound=self._snapshot_age_bound,
            maximum_consumer_age_ms=self._config.max_critical_input_consumer_receipt_age_ms,
            session_context=self._session_owner.session_context(self._instrument_class),
            uncertainty_interval=uncertainty_interval,
            health_state=self._time_service.health_state,
        )


_conforms_to_time_coordinate_projection: type[TimeCoordinateProjection] = (
    RuntimeTimeProjection
)
