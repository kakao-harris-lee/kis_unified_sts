"""Item 5 — ``live_scope_valid`` (``VALID_LIVE_SCOPE``), derived, never attested.

PR-3 option (a), operator decision 2026-10-22: item 5 is implemented for real — no
monkeypatch, no constant ``True``. A broker-reaching send's live scope is valid iff the
ACTIVE scope still resolves from the deployed scope table and its bound INSTANCE document,
and its principal / endpoint / environment are the ones the send is sealed to:

1. **Resolves.** Every capability tuple of the active scope resolves
   (:func:`~tos_runtime.brokercap.scopes.resolve_scope`) back to that same scope with an
   ``ADMITTED`` or ``REDUCED`` disposition — never ``PROHIBITED``, never another scope.
2. **Instance.** The scope declares an ``instance`` binding, the document bound to it was
   loaded, its environment is the binding's, and its profile environment is the scope's own
   profile-key environment.
3. **Principal.** The scope's principal is in the credential-route inventory as a broker
   route, and the sealed coordinates' ``active_principal`` is the gateway principal.
4. **Endpoint.** The sealed ``endpoint`` is exactly the transport's own endpoint
   (``endpoint_rest_base + order_path`` for kis-mock). ``None`` (no broker transport wired)
   fails.
5. **Environment.** The sealed ``environment`` is this runtime's environment label.

A non-broker-reaching scope returns ``None``: item 5 is consulted only for a
broker-resource-consuming send (``tos.egressgw.mesh.resolve_broker_applicability``), and the
synthetic paper path keeps exactly the posture it had before this function existed.

Pure module: no I/O, no clock — every input is injected.
"""

from __future__ import annotations

from tos.egress import CredentialRouteInventoryEntry
from tos.egress.state import EgressCoordinateSet

from tos_runtime.brokercap.derive import is_broker_reaching
from tos_runtime.brokercap.instance import InstanceDocument
from tos_runtime.brokercap.scopes import (
    BrokerScopesConfig,
    ScopeDisposition,
    resolve_scope,
)

__all__ = ["live_scope_failures", "live_scope_valid"]

_RESOLVING_DISPOSITIONS = frozenset(
    {ScopeDisposition.ADMITTED, ScopeDisposition.REDUCED}
)


def live_scope_failures(
    config: BrokerScopesConfig,
    instance: InstanceDocument | None,
    *,
    sealed: EgressCoordinateSet,
    gateway_principal: str,
    inventory: tuple[CredentialRouteInventoryEntry, ...],
    transport_endpoint: str | None,
    environment_label: str,
) -> tuple[str, ...]:
    """Every rule (module docstring) the active scope fails, by name; empty when valid."""
    scope = config.active_scope
    failures: list[str] = []
    for capability_tuple in scope.capability_tuples:
        resolution = resolve_scope(config, capability_tuple)
        if (
            resolution.scope is not scope
            or resolution.disposition not in _RESOLVING_DISPOSITIONS
        ):
            failures.append(f"resolve:{resolution.disposition.value}")
    if not scope.capability_tuples:
        failures.append("resolve:no_tuples")
    binding = scope.instance
    if binding is None or instance is None:
        failures.append("instance:absent")
    elif (
        instance.environment != binding.environment
        or instance.profile.profile_key is None
        or instance.profile.profile_key.environment != scope.profile_key.environment
    ):
        failures.append("instance:environment")
    broker_routes = {e.principal for e in inventory if e.broker_route}
    if scope.principal not in broker_routes:
        failures.append("principal:not_a_broker_route")
    if sealed.active_principal != gateway_principal:
        failures.append("principal:sealed")
    if transport_endpoint is None or sealed.endpoint != transport_endpoint:
        failures.append("endpoint")
    if sealed.environment != environment_label:
        failures.append("environment")
    return tuple(failures)


def live_scope_valid(
    config: BrokerScopesConfig,
    instance: InstanceDocument | None,
    *,
    sealed: EgressCoordinateSet,
    gateway_principal: str,
    inventory: tuple[CredentialRouteInventoryEntry, ...],
    transport_endpoint: str | None,
    environment_label: str,
) -> bool | None:
    """Item 5's flag: ``None`` for a non-broker-reaching scope, else whether
    :func:`live_scope_failures` is empty (module docstring)."""
    if not is_broker_reaching(config.active_scope):
        return None
    return not live_scope_failures(
        config,
        instance,
        sealed=sealed,
        gateway_principal=gateway_principal,
        inventory=inventory,
        transport_endpoint=transport_endpoint,
        environment_label=environment_label,
    )
