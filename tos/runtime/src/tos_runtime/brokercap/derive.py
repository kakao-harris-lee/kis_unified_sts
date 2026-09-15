"""Item 6 / item 12 structural derivation (TOS Phase 4 plan §2 decision 4,
``docs/plans/2026-09-09-tos-phase4-scopes-and-verify-realization-plan.md``).

Replaces the two operator attestations
(``account_instrument_action_allowed`` / ``broker_constraint_generation_current``,
:mod:`tos_runtime.compose._egress_attestations`) with values STRUCTURALLY
DERIVED from the active :class:`~tos_runtime.brokercap.scopes.BrokerScope`,
its owning :class:`~tos_runtime.brokercap.scopes.BrokerScopesConfig`, and (for
a broker-reaching scope) the bound
:class:`~tos_runtime.brokercap.instance.InstanceDocument` — never a bare
Python literal and never a second, independently-typed copy of a fact the
scope table or the INSTANCE document already carries.

**Item 6** (``account_instrument_action_allowed``) is ``True`` only when the
scope's own :func:`~tos.brokercap.routing.routing_admissibility`-stamped
``admissibility`` is ``ADMISSIBLE`` **and** every one of its capability
tuples exactly binds (:func:`~tos.brokercap.routing.endpoint_binding_from_profile_ok`)
to the scope's own :class:`~tos.brokercap.records.ProfileKey` under the
config's injected ``environment_binding``/``asset_binding`` maps. This is a
STATIC, routing-table-level fact about the scope's own coordinates — it says
nothing about whether the INSTANCE document actually authorizes the send;
that is the kernel gateway's OWN separate ``capability_admissible(...)`` call
for a broker-reaching send (``tos.egressgw.gateway._check_allowance``), fed
by :attr:`Item6Item12Fields.broker_capability_profile` /
:attr:`Item6Item12Fields.required_capability_set` /
:attr:`Item6Item12Fields.broker_profile_version_current` below.

**Item 12** (``broker_constraint_generation_current``) is ``True``
unconditionally for a non-broker-reaching scope (``endpoint_class`` in
``{NONE, SYNTHETIC}``) — there is no broker constraint generation to be
stale for a scope that never reaches a broker at all — and otherwise is the
kernel :func:`~tos.brokercap.predicates.profile_version_current` verdict,
fed honestly from the bound INSTANCE document via
:func:`~tos_runtime.brokercap.instance.instance_version_current` (``instance
is None`` ⇒ ``False``, never assumed current).

Pure module: no I/O, no clock, no ambient environment — every input is
injected.
"""

from __future__ import annotations

from dataclasses import dataclass

from tos.brokercap import (
    Admissibility,
    BrokerCapabilityProfile,
    RequiredCapabilitySet,
)
from tos.brokercap.routing import endpoint_binding_from_profile_ok

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
    "load_active_instance_document",
]

#: Endpoint classes that actually reach a broker (module docstring; the same
#: structural fact :mod:`tos_runtime.brokercap.scopes` already keys G-4 off).
_BROKER_REACHING_ENDPOINT_CLASSES = frozenset(
    {EndpointClass.BROKER_GET, EndpointClass.BROKER_ORDER}
)

#: Endpoint classes with no broker constraint generation to go stale at all
#: (module docstring — item 12's unconditional-True branch).
_NO_GENERATION_ENDPOINT_CLASSES = frozenset(
    {EndpointClass.NONE, EndpointClass.SYNTHETIC}
)


def is_broker_reaching(scope: BrokerScope) -> bool:
    """Whether ``scope``'s endpoint class actually reaches a broker (module
    docstring; the SAME ``_BROKER_REACHING_ENDPOINT_CLASSES`` this module's own
    :func:`derive_item6_item12` uses).

    Exposed so OTHER runtime packages can ask this exact structural question
    without themselves reading ``.endpoint_class`` — the EC-1 governance gate
    (``tests/brokercap/test_exit_conditions.py::
    test_no_consumer_of_endpoint_class_outside_the_allowlist`` and
    ``tests/brokercap/test_scopes.py::
    test_no_consumer_of_a_prohibited_scopes_endpoint_class_outside_this_module``)
    only allows ``.endpoint_class`` to be read inside this package. TOS Phase 5
    W5's :class:`~tos_runtime.calendar.owner.SessionFactsOwner` calls this
    (via :mod:`tos_runtime.compose.root`) instead of reading the attribute
    itself, for item 12's ``venue_session_account_facts_current``.
    """
    return scope.endpoint_class in _BROKER_REACHING_ENDPOINT_CLASSES


@dataclass(frozen=True)
class Item6Item12Fields:
    """The derived ``SendBoundaryContext`` fields items 6/12 consume (plan §2
    decision 4), plus the three item-6 broker-reaching fields the kernel
    gateway's own ``capability_admissible(...)`` call needs."""

    account_instrument_action_allowed: bool
    broker_constraint_generation_current: bool
    broker_capability_profile: BrokerCapabilityProfile | None
    required_capability_set: RequiredCapabilitySet | None
    broker_profile_version_current: bool | None
    #: A short string naming the derivation source for both items — never a
    #: caller-supplied claim, always structurally determined by this function.
    reason: str


def load_active_instance_document(
    config: BrokerScopesConfig,
) -> InstanceDocument | None:
    """Load the INSTANCE document bound to ``config.active_scope``, or
    ``None`` when the active scope declares no ``instance`` block at all
    (e.g. the SYNTHETIC default scope — module docstring).

    Raises:
        BrokerInstanceConfigError: The active scope declares an ``instance``
            block but the bound document cannot be loaded (fail-closed boot
            refusal — never swallowed).
    """
    scope = config.active_scope
    if scope.instance is None:
        return None
    assert config.instance_path is not None  # loader-enforced (scopes.py)
    return load_instance_document(
        config.instance_path, environment=scope.instance.environment
    )


def derive_item6_item12(
    scope: BrokerScope,
    config: BrokerScopesConfig,
    instance: InstanceDocument | None,
) -> Item6Item12Fields:
    """Derive items 6/12's fields for ``scope`` (plan §2 decision 4 exactly).

    Args:
        scope: The scope under judgement (typically ``config.active_scope``).
        config: The owning scope table — kept for call-site/API stability
            (every caller in this codebase passes it); item 6's binding
            check now reads the SCOPE's own resolved ``environment_binding``/
            ``asset_binding`` (independent-review finding F4 — a scope with
            its own override block, e.g. the SYNTHETIC scope, gets a map
            that can actually discriminate its own axes instead of the
            config-wide default every other scope also shares).
        instance: The bound INSTANCE document (``None`` for a scope with no
            ``instance`` block, or one whose document could not be loaded
            upstream — either way, fails item 12 closed for a broker-reaching
            scope, never assumed current).

    Returns:
        The derived fields, all structural — never a caller-supplied claim.
    """
    item6_allowed = scope.admissibility is Admissibility.ADMISSIBLE and all(
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
        item12_current = version_current is True
        reason = (
            f"scope {scope.name!r}: item 6 = admissibility({scope.admissibility.value}) "
            f"+ endpoint binding -> {item6_allowed}; item 12 = "
            f"profile_version_current(instance={'present' if instance is not None else 'None'}) "
            f"-> {item12_current}"
        )

    broker_capability_profile = (
        instance.profile if broker_reaching and instance is not None else None
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
