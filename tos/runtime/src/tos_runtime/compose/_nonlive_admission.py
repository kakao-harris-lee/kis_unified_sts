"""Coordinator non-live broker-consuming admission — TOS KIS MOCK transport
plan T2 lane B (plan §2 decision 7 / §7 operator disposition row 1,
``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md``).

The kernel's ``CoordinatorPreconditions`` Protocol carries exactly two
methods (``authority_epoch_current`` / ``live_scope_authorized``) and the
kernel diff for this arc is 0 — nothing here changes ``tos.engine``. Instead,
:class:`~tos_runtime.compose._preconditions.RuntimeCoordinatorPreconditions`
composes this module's :func:`nonlive_broker_consuming_admitted` INSIDE its
own ``live_scope_authorized``: the existing gate ① (kernel ``is_live``
default-non-live judgement) and gate ② (``transport_nature.reaches_broker is
False`` — the structural non-broker answer) stay exactly as they were; a
broker-reaching transport (``reaches_broker is True``) may now proceed only
when this module's verdict is positively ``admitted``.

**Why REAL can never be admitted, structurally, not just by posture.** Five
conditions are required, ALL of them, with no OR path between them:

1. ``posture_admitted is True`` — the operator's own
   ``coordinator_preconditions.yaml::nonlive_broker_consuming.admitted``
   posture (loaded fail-closed by
   :mod:`tos_runtime.compose._preconditions` — ``None`` never reaches this
   module).
2. The active scope's kernel-stamped
   :class:`~tos.brokercap.vocabulary.Admissibility` is ``ADMISSIBLE`` or
   ``REDUCED`` (``REDUCED`` arises only when the scope's own
   ``profile_evidence_ok`` is positively ``true``, backed by P0-2 evidence —
   see :mod:`tos_runtime.brokercap.scopes`).
3. **Every** one of the scope's own
   :class:`~tos.brokercap.routing.CapabilityTuple` values has
   ``authorization_class`` in ``{MOCK_ORDER, NON_AUTHORIZING_READ}`` AND
   ``environment is BROKER_SIMULATION``. This is the one condition a REAL
   scope can never satisfy: any ``BROKER_PRODUCTION`` tuple, or any
   ``REAL_ORDER``/``SYNTHETIC_ORDER`` authorization class, fails it
   regardless of what the operator posture says — REAL is structurally
   unreachable through this path, not merely policy-discouraged (root
   CLAUDE.md non-negotiable: the real futures account is never funded with
   margin, real-money order paths are permanently policy-blocked).
4. ``transport_nature.risk_relevant_live is False`` (explicit ``is False``,
   never a falsy check — an unestablished value is conservatively refused,
   the same discipline :class:`~tos.egressgw.records.TransportNature`'s own
   docstring already applies to every one of its fields).
5. The bound Broker Capability Profile INSTANCE document's own
   ``profile_identity.environment`` matches the scope's
   :class:`~tos_runtime.brokercap.scopes.ScopeInstanceBinding` — a scope
   with no ``instance`` block, or no document at all, fails this
   unconditionally.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib
(``dataclasses``) + ``tos.brokercap``/``tos.egressgw`` +
``tos_runtime.brokercap.instance``/``tos_runtime.brokercap.scopes`` only. No
``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass

from tos.brokercap import Admissibility, AuthorizationClass, BrokerEnvironment
from tos.egressgw import TransportNature

from tos_runtime.brokercap.instance import InstanceDocument
from tos_runtime.brokercap.scopes import BrokerScope

__all__ = ["NonLiveAdmissionVerdict", "nonlive_broker_consuming_admitted"]


#: Condition 2 — the kernel's own most-restrictive-wins admissibility
#: verdict, stamped by the scopes loader (module docstring point 2).
_ADMISSIBLE_SCOPE_STATES = frozenset({Admissibility.ADMISSIBLE, Admissibility.REDUCED})

#: Condition 3 — the only authorization classes a non-live broker-consuming
#: admission may ever see; deliberately excludes REAL_ORDER and
#: SYNTHETIC_ORDER (module docstring point 3).
_ADMITTED_AUTHORIZATION_CLASSES = frozenset(
    {AuthorizationClass.MOCK_ORDER, AuthorizationClass.NON_AUTHORIZING_READ}
)

#: One reason string per failed condition, in fixed evaluation order — never
#: reordered by which conditions happen to fail, so :attr:`NonLiveAdmissionVerdict
#: .reasons` is deterministic for a given input.
_REASON_POSTURE_NOT_ADMITTED = "posture_not_admitted"
_REASON_SCOPE_NOT_ADMISSIBLE = "scope_admissibility_not_admissible_or_reduced"
_REASON_CAPABILITY_TUPLES_NOT_MOCK_SIMULATION = "capability_tuples_not_mock_simulation"
_REASON_RISK_RELEVANT_LIVE_NOT_FALSE = "risk_relevant_live_not_false"
_REASON_INSTANCE_ENVIRONMENT_MISMATCH = "instance_environment_mismatch"


@dataclass(frozen=True)
class NonLiveAdmissionVerdict:
    """The pure verdict :func:`nonlive_broker_consuming_admitted` returns.

    Attributes:
        admitted: ``True`` only when every one of the five conditions (module
            docstring) is positively satisfied.
        reasons: One entry per FAILED condition, in the module's fixed
            evaluation order — empty iff ``admitted`` is ``True``. Recorded
            for evidence/tests, never parsed back into a control-flow
            decision by any caller.
    """

    admitted: bool
    reasons: tuple[str, ...]


def _scope_admissible(active_scope: BrokerScope | None) -> bool:
    """Condition 2 — the active scope's own stamped Admissibility."""
    return (
        active_scope is not None
        and active_scope.admissibility in _ADMISSIBLE_SCOPE_STATES
    )


def _capability_tuples_mock_simulation(active_scope: BrokerScope | None) -> bool:
    """Condition 3 — EVERY capability tuple is MOCK-or-read AND BROKER_SIMULATION.

    An empty ``capability_tuples`` tuple is deliberately refused (never
    vacuously admitted by ``all()`` over nothing) — a scope with no declared
    capability makes no positive claim this module can admit.
    """
    if active_scope is None or not active_scope.capability_tuples:
        return False
    return all(
        tuple_.authorization_class in _ADMITTED_AUTHORIZATION_CLASSES
        and tuple_.environment is BrokerEnvironment.BROKER_SIMULATION
        for tuple_ in active_scope.capability_tuples
    )


def _risk_relevant_live_false(transport_nature: TransportNature | None) -> bool:
    """Condition 4 — explicit ``is False``, never a falsy/None check."""
    return transport_nature is not None and transport_nature.risk_relevant_live is False


def _instance_matches_scope_binding(
    active_scope: BrokerScope | None, instance_document: InstanceDocument | None
) -> bool:
    """Condition 5 — the INSTANCE document's environment matches the scope's
    own ``ScopeInstanceBinding.environment``. A scope with no ``instance``
    block, or no document at all, fails unconditionally."""
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
    """Whether a broker-reaching, non-live transport may proceed (module docstring).

    Pure — no I/O, no clock read, no exception path for a merely-negative
    input (every argument is allowed to be ``None``; a missing input simply
    fails its own condition, never raises). Called ONLY for a transport
    already established as broker-reaching
    (:meth:`~tos_runtime.compose._preconditions.RuntimeCoordinatorPreconditions
    .live_scope_authorized`'s own gate ② already handles the non-broker
    case) — this function does not itself re-check ``reaches_broker``.

    Args:
        posture_admitted: The operator-configured
            ``coordinator_preconditions.yaml::nonlive_broker_consuming.admitted``
            posture (``None`` when not wired yet — condition 1 fails,
            never treated as an affirmative grant).
        transport_nature: The declared nature of the transport this tick
            would egress through.
        active_scope: This runtime's currently-active
            :class:`~tos_runtime.brokercap.scopes.BrokerScope`.
        instance_document: The Broker Capability Profile INSTANCE document
            bound to ``active_scope`` (``None`` when not wired).

    Returns:
        A :class:`NonLiveAdmissionVerdict` — ``admitted`` is ``True`` only
        when all five conditions (module docstring) hold; otherwise
        ``False`` with every failed condition named in ``reasons``.
    """
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
