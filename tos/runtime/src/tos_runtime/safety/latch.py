"""``tos_runtime.safety.latch`` — the restrictive-latch and worst-credible-capacity
runtime owners (Phase 5 W3 plan
``docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md`` §2 decision 6).

**Why these two owners exist.** Item 16's ``restrictive_latch_state`` /
``worst_credible_capacity`` ``SendBoundaryContext`` fields used to be genuine
operator attestations (:mod:`tos_runtime.compose._egress_attestations` — a
config-sourced, named-TBD ``null`` an operator filled in by hand). Neither field
had a real runtime producer. This module is that producer:

* :class:`RestrictiveLatchOwner` composes THREE facts this runtime already
  tracks — the durable new-risk-halt latch
  (:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.new_risk_halt`), whether the
  incident-mesh owner (W3-a2, :mod:`tos_runtime.safety.incident`) currently reports
  clear, and whether the safety-profile owner (W3-a1, :mod:`tos_runtime.safety.profile`)
  currently reports clear — into the one kernel :class:`~tos.egress.RestrictiveLatchState`
  :func:`~tos.egress.predicates.monotonic_denial_no_revival` consumes. It authors no
  judgement of its own: any of the three being non-positive is
  ``DENY_LATCHED``, exactly like the kernel predicate's own "a ``None`` latch state
  is UNKNOWN => ``DENY_LATCHED`` (fail-closed)" rule — the enum has no third
  member, so "held" and "unknown" are, correctly, the SAME non-clear value here.
* :class:`CapacityOwner` reads the RCL reservation projection
  (:mod:`tos_runtime.rcl.projection`) for one composed ``InstrumentKey`` scope and
  reports whether an outstanding (non-``RELEASED``) reservation is currently held
  there. Per the kernel's own pin
  (``tos/runtime/tests/compose/test_egress_attestations.py::
  test_worst_credible_capacity_is_descriptive_not_gating``), this value is a
  DESCRIPTIVE record folded into denial reason text — never an independent gate
  (``gateway.py``'s own ``_check_currentness``) — so this owner does not need, and
  does not claim, currentness-grade completeness; a missing projection reads as
  zero outstanding capacity, never a fabricated positive.

:func:`egress_owner_fields` bundles both owners' current output as one
:class:`EgressOwnerFields` record — the two kernel-facing ``SendBoundaryContext``
values (module docstring "the two kernel-facing values") the compose wiring layer
(:mod:`tos_runtime.compose.context`, lane b) spreads into ``send_boundary_context``
in place of the retired ``EgressAttestations`` fields.

Firewall: stdlib + ``tos.egress`` (``RestrictiveLatchState``) + ``tos.engine.records``
(``InstrumentKey``) + ``tos_runtime.rcl.projection``
only — no ``shared.*``, no verdict authorship (Phase 5 plan §2 decision 1 (b)).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from tos.egress import RestrictiveLatchState
from tos.engine.records import InstrumentKey

from tos_runtime.rcl.projection import (
    ReservationProjectionReader,
    outstanding_reservations,
)

__all__ = [
    "CapacityOwner",
    "EgressOwnerFields",
    "NewRiskHaltReader",
    "RestrictiveLatchOwner",
    "egress_owner_fields",
]


@runtime_checkable
class NewRiskHaltReader(Protocol):
    """The read-only seam :class:`RestrictiveLatchOwner` needs over the durable
    new-risk-halt latch — the shape
    :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.new_risk_halt` already
    satisfies. A ``None`` return means "no latch currently held"."""

    def new_risk_halt(self) -> Mapping[str, object] | None:
        """The currently-latched row (``reason``/``event_id``/``evidence_seq``), or
        ``None`` when no new-risk halt is held."""
        ...


class RestrictiveLatchOwner:
    """The item-16 ``restrictive_latch_state`` runtime owner (plan §2 decision 6).

    ``CLEAR`` only when ALL THREE hold: (1) the durable new-risk-halt latch
    (:mod:`tos_runtime.engine.inbox`) is absent, (2) the incident-mesh owner's
    ``clear()`` reports positively (``is True``), and (3) the safety-profile owner's
    ``clear()`` reports positively (``is True``). Any latched / ``False`` / ``None``
    input collapses to :attr:`~tos.egress.RestrictiveLatchState.DENY_LATCHED` — the
    kernel vocabulary (:mod:`tos.egress.vocabulary`) has exactly two members
    (``CLEAR`` / ``DENY_LATCHED``, no ``UNKNOWN``), and the kernel's own
    :func:`~tos.egress.predicates.monotonic_denial_no_revival` already treats a
    ``None`` latch state as UNKNOWN => ``DENY_LATCHED`` (fail-closed) — so "held"
    and "unknown" are, correctly, the identical non-clear value here, never two
    different answers this owner would have to invent a third member to tell
    apart.

    Verdict authorship is forbidden here (plan §2 decision 1 (b)): this class
    combines three already-decided facts; it decides nothing of its own about
    whether an incident or profile deviation exists.
    """

    def __init__(
        self,
        inbox_reader: NewRiskHaltReader,
        incident_clear: Callable[[], bool | None],
        profile_clear: Callable[[], bool | None],
    ) -> None:
        """Args:
        inbox_reader: The new-risk-halt latch reader (module docstring).
        incident_clear: The incident-mesh owner's ``clear()`` boolean — typically
            ``lambda: incident_service.clear().clear`` (W3-a2,
            :mod:`tos_runtime.safety.incident`).
        profile_clear: The safety-profile owner's ``clear()`` boolean — typically
            ``lambda: profile_service.clear().clear`` (W3-a1,
            :mod:`tos_runtime.safety.profile`).
        """
        self._inbox = inbox_reader
        self._incident_clear = incident_clear
        self._profile_clear = profile_clear

    def state(self) -> RestrictiveLatchState:
        """The combined restrictive-latch state, evaluated fresh on every call.

        Returns:
            :attr:`~tos.egress.RestrictiveLatchState.CLEAR` only when the new-risk
            latch is absent AND both injected ``clear`` callables report ``True``;
            :attr:`~tos.egress.RestrictiveLatchState.DENY_LATCHED` otherwise
            (latched, ``False``, or ``None`` — fail-closed).
        """
        if self._inbox.new_risk_halt() is not None:
            return RestrictiveLatchState.DENY_LATCHED
        if self._incident_clear() is not True:
            return RestrictiveLatchState.DENY_LATCHED
        if self._profile_clear() is not True:
            return RestrictiveLatchState.DENY_LATCHED
        return RestrictiveLatchState.CLEAR

    def describe(self) -> Mapping[str, Any]:
        """Evidence-facing description — no secrets, three booleans + the resolved state."""
        latched = self._inbox.new_risk_halt() is not None
        incident_clear = self._incident_clear()
        profile_clear = self._profile_clear()
        return {
            "owner": "RestrictiveLatchOwner",
            "new_risk_halt_latched": latched,
            "incident_clear": incident_clear,
            "profile_clear": profile_clear,
            "state": self.state().value,
        }


class CapacityOwner:
    """The item-16 ``worst_credible_capacity`` runtime owner (plan §2 decision 6).

    Counts the outstanding (non-``RELEASED``) reservations currently held for one composed
    :class:`~tos.engine.records.InstrumentKey` scope via the RCL reservation projection
    (:mod:`tos_runtime.rcl.projection`).

    **#966**: that count is no longer capped at 1. Each attempt commits its own reservation
    (:mod:`tos_runtime.rcl.reservation_identity`), so a scope legitimately holds two at once
    while an exit closes a filled entry, and the honest worst-credible reading is the real
    count — reporting 1 for two held reservations would understate exposure, which is the one
    direction a conservative reading must never err in. DESCRIPTIVE only (module docstring);
    never an independent gate.
    """

    def __init__(
        self, projection_reader: ReservationProjectionReader, scope: InstrumentKey
    ) -> None:
        self._projection = projection_reader
        self._scope = scope

    def worst_credible_capacity(self) -> int:
        """The outstanding-reservation count for this owner's scope.

        Returns:
            How many of the scope's reservations are not yet
            :attr:`~tos.rcl.CapacityState.RELEASED` — ``0`` when the scope holds none or all of
            them are released (terminal, no outstanding exposure), otherwise the real count
            (``1`` for an ordinary open position, ``2`` while an exit closes a filled entry).
        """
        return len(
            outstanding_reservations(self._projection.scope_reservations(self._scope))
        )

    def describe(self) -> Mapping[str, Any]:
        """Evidence-facing description — the scope coordinates + the resolved count."""
        return {
            "owner": "CapacityOwner",
            "account": self._scope.account,
            "instrument": self._scope.instrument,
            "worst_credible_capacity": self.worst_credible_capacity(),
        }


@dataclass(frozen=True)
class EgressOwnerFields:
    """The two item-16 ``SendBoundaryContext`` fields this module owns (plan §2
    decision 6) — what :mod:`tos_runtime.compose.context` (lane b) spreads into
    ``send_boundary_context`` in place of the retired
    ``EgressAttestations.restrictive_latch_state`` /
    ``.worst_credible_capacity`` config attestations."""

    restrictive_latch_state: RestrictiveLatchState
    worst_credible_capacity: int

    def fields(self) -> dict[str, Any]:
        """This record as a plain ``dict`` — ``**egress_owner_fields(...).fields()``
        spreads directly into a ``send_boundary_context(...)`` call."""
        return {
            "restrictive_latch_state": self.restrictive_latch_state,
            "worst_credible_capacity": self.worst_credible_capacity,
        }


def egress_owner_fields(
    latch: RestrictiveLatchOwner, capacity: CapacityOwner
) -> EgressOwnerFields:
    """Evaluate both owners fresh and bundle their output (module docstring).

    Args:
        latch: The composed :class:`RestrictiveLatchOwner`.
        capacity: The composed :class:`CapacityOwner`.

    Returns:
        The :class:`EgressOwnerFields` for this tick.
    """
    return EgressOwnerFields(
        restrictive_latch_state=latch.state(),
        worst_credible_capacity=capacity.worst_credible_capacity(),
    )
