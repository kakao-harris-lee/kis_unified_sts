"""Coordinator non-live broker-consuming admission — TOS KIS MOCK transport"""

from __future__ import annotations

from dataclasses import dataclass

from tos.brokercap import Admissibility, AuthorizationClass, BrokerEnvironment
from tos.egressgw import TransportNature

from tos_runtime.brokercap.instance import InstanceDocument
from tos_runtime.brokercap.scopes import BrokerScope

__all__ = ["NonLiveAdmissionVerdict", "nonlive_broker_consuming_admitted"]


_ADMISSIBLE_SCOPE_STATES = frozenset({Admissibility.ADMISSIBLE, Admissibility.REDUCED})

_ADMITTED_AUTHORIZATION_CLASSES = frozenset(
    {AuthorizationClass.MOCK_ORDER, AuthorizationClass.NON_AUTHORIZING_READ}
)

_REASON_POSTURE_NOT_ADMITTED = "posture_not_admitted"
_REASON_SCOPE_NOT_ADMISSIBLE = "scope_admissibility_not_admissible_or_reduced"
_REASON_CAPABILITY_TUPLES_NOT_MOCK_SIMULATION = "capability_tuples_not_mock_simulation"
_REASON_RISK_RELEVANT_LIVE_NOT_FALSE = "risk_relevant_live_not_false"
_REASON_INSTANCE_ENVIRONMENT_MISMATCH = "instance_environment_mismatch"


@dataclass(frozen=True)
class NonLiveAdmissionVerdict:
    """The pure verdict :func:`nonlive_broker_consuming_admitted` returns."""

    admitted: bool
    reasons: tuple[str, ...]


def _scope_admissible(active_scope: BrokerScope | None) -> bool:
    """Condition 2 — the active scope's own stamped Admissibility."""
    return (
        active_scope is not None
        and active_scope.admissibility in _ADMISSIBLE_SCOPE_STATES
    )


def _capability_tuples_mock_simulation(active_scope: BrokerScope | None) -> bool:
    """Condition 3 — EVERY capability tuple is MOCK-or-read AND BROKER_SIMULATION."""
    if active_scope is None or not active_scope.capability_tuples:
        return False
    return all(
        tuple_.authorization_class in _ADMITTED_AUTHORIZATION_CLASSES
        and tuple_.environment is BrokerEnvironment.BROKER_SIMULATION
        for tuple_ in active_scope.capability_tuples
    )


def _risk_relevant_live_false(transport_nature: TransportNature | None) -> bool:
    """Condition 4 — explicit ``is False``, never a falsy/None check."""
    return (
        transport_nature is not None
        and getattr(transport_nature, "risk_relevant_live", None) is False
    )


def _instance_matches_scope_binding(
    active_scope: BrokerScope | None, instance_document: InstanceDocument | None
) -> bool:
    """Condition 5 — the INSTANCE document's environment matches the scope's"""
    if (
        active_scope is None
        or active_scope.instance is None
        or instance_document is None
    ):
        return False
    return instance_document.environment == active_scope.instance.environment


def nonlive_broker_consuming_admitted(
    *,
    posture_admitted: bool | None,
    transport_nature: TransportNature | None,
    active_scope: BrokerScope | None,
    instance_document: InstanceDocument | None,
) -> NonLiveAdmissionVerdict:
    """Whether a broker-reaching, non-live transport may proceed (module docstring)."""
    reasons: list[str] = []
    if posture_admitted is not True:
        reasons.append(_REASON_POSTURE_NOT_ADMITTED)
    if not _scope_admissible(active_scope):
        reasons.append(_REASON_SCOPE_NOT_ADMISSIBLE)
    if not _capability_tuples_mock_simulation(active_scope):
        reasons.append(_REASON_CAPABILITY_TUPLES_NOT_MOCK_SIMULATION)
    if not _risk_relevant_live_false(transport_nature):
        reasons.append(_REASON_RISK_RELEVANT_LIVE_NOT_FALSE)
    if not _instance_matches_scope_binding(active_scope, instance_document):
        reasons.append(_REASON_INSTANCE_ENVIRONMENT_MISMATCH)
    return NonLiveAdmissionVerdict(admitted=not reasons, reasons=tuple(reasons))
