"""Item 6 / item 12 structural derivation (TOS Phase 4 plan §2 decision 4,"""

from __future__ import annotations

from dataclasses import dataclass

from tos.brokercap import (
    Admissibility,
    BrokerCapabilityProfile,
    BrokerEnvironment,
    RequiredCapabilitySet,
)
from tos.brokercap.routing import (
    endpoint_binding_from_profile_ok,
    mock_order_without_position_or_cash,
)

from tos_runtime.brokercap.instance import (
    InstanceDocument,
    instance_version_current,
    load_instance_document,
)
from tos_runtime.brokercap.scopes import BrokerScope, BrokerScopesConfig, EndpointClass

__all__ = [
    "Item6Item12Fields",
    "derive_item6_item12",
    "is_broker_reaching",
    "is_mock_order_class",
    "load_active_instance_document",
]

_BROKER_REACHING_ENDPOINT_CLASSES = frozenset(
    {EndpointClass.BROKER_GET, EndpointClass.BROKER_ORDER}
)

_NO_GENERATION_ENDPOINT_CLASSES = frozenset(
    {EndpointClass.NONE, EndpointClass.SYNTHETIC}
)


def is_broker_reaching(scope: BrokerScope) -> bool:
    """Whether ``scope``'s endpoint class actually reaches a broker (module"""
    return scope.endpoint_class in _BROKER_REACHING_ENDPOINT_CLASSES


@dataclass(frozen=True)
class Item6Item12Fields:
    """The derived ``SendBoundaryContext`` fields items 6/12 consume (plan §2"""

    account_instrument_action_allowed: bool
    broker_constraint_generation_current: bool
    broker_capability_profile: BrokerCapabilityProfile | None
    required_capability_set: RequiredCapabilitySet | None
    broker_profile_version_current: bool | None
    reason: str


def load_active_instance_document(
    config: BrokerScopesConfig,
) -> InstanceDocument | None:
    """Load the INSTANCE document bound to ``config.active_scope``, or"""
    scope = config.active_scope
    if scope.instance is None:
        return None
    assert config.instance_path is not None
    return load_instance_document(
        config.instance_path,
        environment=scope.instance.environment,
        expected_sha256=config.instance_sha256,
    )


def _is_mock_class(scope: BrokerScope, instance: InstanceDocument | None) -> bool:
    """Option (a) "K" (operator decision 2026-10-23): the scope's own kernel-typed tuples are"""
    return (
        mock_order_without_position_or_cash(scope.capability_tuples)
        and instance is not None
        and instance.environment_class_host_bound
        and instance.profile.environment_class is BrokerEnvironment.BROKER_SIMULATION
    )


def is_mock_order_class(scope: BrokerScope, instance: InstanceDocument | None) -> bool:
    """Public form of :func:`_is_mock_class` for callers outside item 6/12 (the standing"""
    return (
        _is_mock_class(scope, instance)
        and instance is not None
        and _kernel_profile(instance) is not None
    )


def _kernel_profile(instance: InstanceDocument) -> BrokerCapabilityProfile | None:
    """The profile handed to the kernel gateway — none at all when it carries an"""
    profile = instance.profile
    if profile.environment_class is None or instance.environment_class_host_bound:
        return profile
    return None


def derive_item6_item12(
    scope: BrokerScope,
    config: BrokerScopesConfig,
    instance: InstanceDocument | None,
    *,
    mock_generation_current: bool | None = None,
) -> Item6Item12Fields:
    """Derive items 6/12's fields for ``scope`` (plan §2 decision 4 exactly)."""
    mock_class = _is_mock_class(scope, instance)
    admissible = scope.admissibility is Admissibility.ADMISSIBLE or (
        scope.admissibility is Admissibility.REDUCED and mock_class
    )
    item6_allowed = admissible and all(
        endpoint_binding_from_profile_ok(
            t,
            scope.profile_key,
            environment_binding=scope.environment_binding,
            asset_binding=scope.asset_binding,
        )
        for t in scope.capability_tuples
    )
    broker_reaching = scope.endpoint_class in _BROKER_REACHING_ENDPOINT_CLASSES

    if scope.endpoint_class in _NO_GENERATION_ENDPOINT_CLASSES:
        item12_current = True
        version_current: bool | None = None
        reason = (
            f"scope {scope.name!r}: item 6 = admissibility({scope.admissibility.value}) "
            f"+ endpoint binding -> {item6_allowed}; item 12 = True (endpoint_class "
            f"{scope.endpoint_class.value} never reaches a broker, so no constraint "
            "generation exists to be stale)"
        )
    else:
        degraded_since_authorization = (
            scope.instance.degraded_since_authorization
            if scope.instance is not None
            else None
        )
        version_current = (
            False
            if instance is None
            else instance_version_current(
                instance, degraded_since_authorization=degraded_since_authorization
            )
        )
        item12_current = (
            mock_generation_current is True if mock_class else version_current is True
        )
        reason = (
            f"scope {scope.name!r}: item 6 = admissibility({scope.admissibility.value}) "
            f"+ endpoint binding -> {item6_allowed}; item 12 = "
            + (
                f"mock-account GET freshness -> {item12_current}"
                if mock_class
                else f"profile_version_current(instance="
                f"{'present' if instance is not None else 'None'}) -> {item12_current}"
            )
        )

    broker_capability_profile = (
        _kernel_profile(instance) if broker_reaching and instance is not None else None
    )
    broker_profile_version_current = version_current if broker_reaching else None

    return Item6Item12Fields(
        account_instrument_action_allowed=item6_allowed,
        broker_constraint_generation_current=item12_current,
        broker_capability_profile=broker_capability_profile,
        required_capability_set=scope.required_capability_set,
        broker_profile_version_current=broker_profile_version_current,
        reason=reason,
    )
