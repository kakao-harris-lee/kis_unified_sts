"""Reconciliation ports — Phase 5 W1 (plan §2 decision 3; `tos.recon` §0.2/§4.2)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable

from tos.engine.records import InstrumentKey

from tos_runtime.rcl.projection import ReservationProjectionReader

__all__ = [
    "BrokerWitness",
    "EgressReceiptObservation",
    "EvidenceReceiptReader",
    "ReservationProjectionReader",
    "WitnessOrder",
    "WitnessOrderState",
    "WitnessScope",
    "WitnessSnapshot",
    "WitnessUnavailable",
]


class WitnessOrderState(StrEnum):
    """The broker-witness-observed order lifecycle states (plan §2 decision 3)."""

    ACKED = "ACKED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class WitnessScope:
    """The (account, instrument, attempt) window a :class:`BrokerWitness` is asked about."""

    account: str
    instrument_keys: tuple[InstrumentKey, ...] = ()
    attempt_ids: tuple[str, ...] = ()
    as_of_generation: int | None = None
    order_dates: tuple[str, ...] = ()


@dataclass(frozen=True)
class WitnessOrder:
    """One broker-witness-observed order (plan §2 decision 3)."""

    attempt_id: str | None
    broker_execution_id: str | None
    quantity: Decimal | None
    remaining: Decimal | None
    state: WitnessOrderState
    order_date: str | None = None


@dataclass(frozen=True)
class WitnessSnapshot:
    """A :class:`BrokerWitness` observation at one generation (plan §2 decision 3)."""

    observed_at_generation: int | None
    orders: tuple[WitnessOrder, ...]
    positions: tuple[tuple[str, Decimal], ...] = ()
    positions_complete: bool = False
    cash: Decimal | None = None
    provenance: str = ""
    independent_of_evidence_store: bool = False
    order_inquiry_date: str | None = None


class WitnessUnavailable(Exception):
    """Raised by :meth:`BrokerWitness.observe` when the witness cannot answer at all."""


@runtime_checkable
class BrokerWitness(Protocol):
    """The broker-side observation port (plan §2 decision 3's own name)."""

    def observe(self, scope: WitnessScope) -> WitnessSnapshot:
        """Observe broker-side state for ``scope``, or raise :class:`WitnessUnavailable`."""
        ...


@dataclass(frozen=True)
class EgressReceiptObservation:
    """One attempt's durably recorded egress-result receipt (runtime evidence-receipt path)."""

    attempt_id: str | None
    account: str | None
    instrument: str | None
    egress_result_kind: str | None
    broker_execution_id: str | None
    filled_quantity: Decimal | None
    remaining_quantity: Decimal | None
    finality_proof_recorded: bool
    source_ref: str
    trading_date: str | None = None


@runtime_checkable
class EvidenceReceiptReader(Protocol):
    """The evidence-receipt observation port :class:`~tos_runtime.recon.service"""

    def receipts(self, scope: WitnessScope) -> tuple[EgressReceiptObservation, ...]:
        """Return every recorded receipt observation within ``scope``."""
        ...
