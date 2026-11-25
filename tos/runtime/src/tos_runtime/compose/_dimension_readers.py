"""``tos_runtime.compose`` currentness dimension-reader factories + their late-bound"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tos.authority import currentness_admissible
from tos.brokercap import environment_binding_ok
from tos.cur import (
    MANDATED_DIMENSION_FLOOR,
    CurrentnessPolicy,
    DimensionKey,
    policy_covers_mandated_dimensions,
)

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.brokercap.scopes import BrokerScope, transport_nature
from tos_runtime.compose._monitor_wiring import _MonitorOwners
from tos_runtime.currentness.vector import DimensionReport
from tos_runtime.posttrade.release_consumer import ReleaseConflictReader
from tos_runtime.recovery.barrier import RecoveryVerdict
from tos_runtime.recovery.readiness import ReadinessVerdict

__all__ = [
    "_DimensionStates",
    "_EnvironmentScopeDimensionState",
    "_PostTradeDimensionState",
    "_RecoveryDimensionState",
    "_ReleaseDimensionState",
    "_authority_dimension_reader_for",
    "_build_dimension_readers",
    "_currentness_policy_dimension_reader_for",
    "_environment_scope_dimension_reader_for",
    "_post_trade_dimension_reader_for",
    "_recovery_dimension_reader_for",
    "_release_dimension_reader_for",
]


def _authority_dimension_reader_for(
    authority_epoch_service: SafetyAuthorityEpochService,
) -> Callable[[], DimensionReport | None]:
    def _reader() -> DimensionReport | None:
        state = authority_epoch_service.current_state()
        if state.current_epoch_floor is None:
            return None
        witness = authority_epoch_service.witness()
        return DimensionReport(
            bound_generation=state.current_epoch_floor,
            positively_established=currentness_admissible(witness),
            restrictive_floor=0,
        )

    return _reader


def _currentness_policy_dimension_reader_for(
    policy: CurrentnessPolicy,
) -> Callable[[], DimensionReport | None]:
    """The CURRENTNESS_POLICY currentness dimension (Phase 5 W3-b, plan §2"""

    def _reader() -> DimensionReport | None:
        return DimensionReport(
            bound_generation=policy.policy_generation,
            positively_established=policy_covers_mandated_dimensions(
                policy, MANDATED_DIMENSION_FLOOR
            ),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _RecoveryDimensionState:
    """A late-bound cell for the RECOVERY dimension reader (below)."""

    verdict: RecoveryVerdict | None = None


def _recovery_dimension_reader_for(
    state: _RecoveryDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The RECOVERY currentness dimension (Phase 5 W3-b, plan §2 decision 3 —"""

    def _reader() -> DimensionReport | None:
        verdict = state.verdict
        if verdict is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=verdict.readiness_verdict is ReadinessVerdict.READY,
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _EnvironmentScopeDimensionState:
    """A late-bound cell for the ENVIRONMENT_SCOPE dimension reader (below)."""

    active_scope: BrokerScope | None = None


def _environment_scope_dimension_reader_for(
    environment_label: str,
    state: _EnvironmentScopeDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The ENVIRONMENT_SCOPE currentness dimension (Phase 5 W3-b, plan §2 decision 3 —"""

    def _reader() -> DimensionReport | None:
        active_scope = state.active_scope
        if active_scope is None:
            return None
        if transport_nature(active_scope).reaches_broker is False:
            return DimensionReport(
                bound_generation=0, positively_established=True, restrictive_floor=0
            )
        scope_environment = (
            active_scope.environment_binding.get(
                active_scope.capability_tuples[0].environment
            )
            if active_scope.capability_tuples
            else None
        )
        instance = active_scope.instance
        evidence_environment = instance.environment if instance is not None else None
        inherited = False if instance is not None else None
        return DimensionReport(
            bound_generation=0,
            positively_established=environment_binding_ok(
                evidence_environment=evidence_environment,
                scope_environment=scope_environment,
                inherited=inherited,
            ),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _PostTradeDimensionState:
    """A late-bound cell for the POST_TRADE dimension reader (below)."""

    consumer: ReleaseConflictReader | None = None


def _post_trade_dimension_reader_for(
    state: _PostTradeDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The POST_TRADE currentness dimension (Phase 5 W3.2, plan §2 decision 5 —"""

    def _reader() -> DimensionReport | None:
        consumer = state.consumer
        if consumer is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=consumer.latest_release_is_conflict_free(),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _ReleaseDimensionState:
    """A late-bound cell for the RELEASE dimension reader (below)."""

    release_admitted: bool | None = None


def _release_dimension_reader_for(
    state: _ReleaseDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The RELEASE currentness dimension (Phase 5 W3.2, plan §2 decision 6 —"""

    def _reader() -> DimensionReport | None:
        if state.release_admitted is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=state.release_admitted,
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _DimensionStates:
    """Every late-bound dimension-reader cell :func:`_build_dimension_readers` creates —"""

    recovery: _RecoveryDimensionState
    environment_scope: _EnvironmentScopeDimensionState
    post_trade: _PostTradeDimensionState
    release: _ReleaseDimensionState


def _build_dimension_readers(
    *,
    authority_epoch_service: SafetyAuthorityEpochService,
    currentness_policy: CurrentnessPolicy,
    environment_label: str,
    monitor_owners: _MonitorOwners,
) -> tuple[
    dict[DimensionKey, tuple[str, Callable[[], DimensionReport | None]]],
    _DimensionStates,
]:
    """The full ``dimension_readers`` map (module docstring, "Reader map") — split out"""
    dimension_states = _DimensionStates(
        recovery=_RecoveryDimensionState(),
        environment_scope=_EnvironmentScopeDimensionState(),
        post_trade=_PostTradeDimensionState(),
        release=_ReleaseDimensionState(),
    )
    dimension_readers: dict[
        DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
    ] = {
        DimensionKey.SAFETY_AUTHORITY: (
            "tos_runtime.authority",
            _authority_dimension_reader_for(authority_epoch_service),
        ),
        DimensionKey.CURRENTNESS_POLICY: (
            "tos_runtime.currentness",
            _currentness_policy_dimension_reader_for(currentness_policy),
        ),
        DimensionKey.RECOVERY: (
            "tos_runtime.recovery",
            _recovery_dimension_reader_for(dimension_states.recovery),
        ),
        DimensionKey.ENVIRONMENT_SCOPE: (
            "tos_runtime.brokercap",
            _environment_scope_dimension_reader_for(
                environment_label, dimension_states.environment_scope
            ),
        ),
        DimensionKey.POST_TRADE: (
            "tos_runtime.posttrade",
            _post_trade_dimension_reader_for(dimension_states.post_trade),
        ),
        DimensionKey.RELEASE: (
            "tos_runtime.release",
            _release_dimension_reader_for(dimension_states.release),
        ),
        **monitor_owners.dimension_readers,
    }
    return dimension_readers, dimension_states
