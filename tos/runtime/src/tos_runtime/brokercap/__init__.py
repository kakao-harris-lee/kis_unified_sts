"""``tos_runtime.brokercap`` — runtime-configured Broker Capability scope
table + G-4 transport/credential-route derivation (TOS Phase 4 plan §2,
``docs/plans/2026-09-09-tos-phase4-scopes-and-verify-realization-plan.md``).

Re-exports the public surface of :mod:`tos_runtime.brokercap.scopes` (scope
table, lane A) and :mod:`tos_runtime.brokercap.instance` (Broker Capability
Profile INSTANCE loader, lane C — plan §2 decision 3).
"""

from __future__ import annotations

from tos_runtime.brokercap.instance import (
    BrokerInstanceConfigError,
    InstanceDocument,
    instance_version_current,
    load_instance_documents,
    select_document,
)
from tos_runtime.brokercap.scopes import (
    BrokerScope,
    BrokerScopeConfigError,
    BrokerScopesConfig,
    EndpointClass,
    PrincipalClass,
    ScopeDisposition,
    ScopeResolution,
    credential_route_inventory,
    load_broker_scopes,
    refuse_principal_collision,
    resolve_scope,
    transport_nature,
)

__all__ = [
    "BrokerInstanceConfigError",
    "BrokerScope",
    "BrokerScopeConfigError",
    "BrokerScopesConfig",
    "EndpointClass",
    "InstanceDocument",
    "PrincipalClass",
    "ScopeDisposition",
    "ScopeResolution",
    "credential_route_inventory",
    "instance_version_current",
    "load_broker_scopes",
    "load_instance_documents",
    "refuse_principal_collision",
    "resolve_scope",
    "select_document",
    "transport_nature",
]
