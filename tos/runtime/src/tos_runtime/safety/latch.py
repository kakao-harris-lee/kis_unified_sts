"""``tos_runtime.safety.latch`` — the restrictive-latch and worst-credible-capacity"""

from __future__ import annotations

from collections.abc import Mapping
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
    """The read-only seam :class:`RestrictiveLatchOwner` needs over the durable"""

    def new_risk_halt(self) -> Mapping[str, object] | None:
        """The currently-latched row (``reason``/``event_id``/``evidence_seq``), or"""
        ...


class RestrictiveLatchOwner:
    """The item-16 ``restrictive_latch_state`` runtime owner (plan §2 decision 6)."""

    def __init__(self, inbox_reader: NewRiskHaltReader) -> None:
        """Args:"""
        self._inbox = inbox_reader

    def state(self) -> RestrictiveLatchState:
        """The combined restrictive-latch state, evaluated fresh on every call."""
        if self._inbox.new_risk_halt() is not None:
            return RestrictiveLatchState.DENY_LATCHED
        return RestrictiveLatchState.CLEAR

    def describe(self) -> Mapping[str, Any]:
        """Evidence-facing description — no secrets, one boolean + the resolved state."""
        return {
            "owner": "RestrictiveLatchOwner",
            "new_risk_halt_latched": self._inbox.new_risk_halt() is not None,
            "state": self.state().value,
        }


class CapacityOwner:
    """The item-16 ``worst_credible_capacity`` runtime owner (plan §2 decision 6)."""

    def __init__(
        self, projection_reader: ReservationProjectionReader, scope: InstrumentKey
    ) -> None:
        self._projection = projection_reader
        self._scope = scope

    def worst_credible_capacity(self) -> int:
        """The outstanding-reservation count for this owner's scope."""
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
    """The two item-16 ``SendBoundaryContext`` fields this module owns (plan §2"""

    restrictive_latch_state: RestrictiveLatchState
    worst_credible_capacity: int

    def fields(self) -> dict[str, Any]:
        """This record as a plain ``dict`` — ``**egress_owner_fields(...).fields()``"""
        return {
            "restrictive_latch_state": self.restrictive_latch_state,
            "worst_credible_capacity": self.worst_credible_capacity,
        }


def egress_owner_fields(
    latch: RestrictiveLatchOwner, capacity: CapacityOwner
) -> EgressOwnerFields:
    """Evaluate both owners fresh and bundle their output (module docstring)."""
    return EgressOwnerFields(
        restrictive_latch_state=latch.state(),
        worst_credible_capacity=capacity.worst_credible_capacity(),
    )
