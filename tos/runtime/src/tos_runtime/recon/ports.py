"""Reconciliation ports — Phase 5 W1 (plan §2 decision 3; `tos.recon` §0.2/§4.2).

Defines the seams :class:`~tos_runtime.recon.service.ReconciliationService` depends on
and never the concrete cross-lane types themselves (the ``tos_runtime.currentness.vector
.CurrentnessAssembler`` precedent: cross-lane facts are injected Protocols/callables, not
imports of another lane's owning package).

**Three observation paths, three ports:**

* the RCL side is the ALREADY-LANDED
  :class:`~tos_runtime.rcl.projection.ReservationProjectionReader` Protocol (read-only,
  lane M) — this package adds no new RCL port, it reuses that one directly;
* the evidence-receipt side is :class:`EvidenceReceiptReader`, defined here — a runtime-
  local seam over whatever durably recorded the driver's re-injected ``EGRESS_RESULT``
  facts (``tos.engine.EvidenceKind.EGRESS_RESULT_CONSUMED`` /
  ``RESULT_UNMATCHED``, appended by ``tos_runtime.evidence.sinks
  .EngineEvidenceSinkAdapter``) plus whether a post-trade Final Quantity Proof was
  separately recorded (``POSTTRADE_FINALITY_PROOF``, ``tos_runtime.posttrade.finality
  .SyntheticFinalityProducer``'s own durable output) — this package ships no concrete
  implementation of it (out of this lane's file list); a future lane wires one the same
  way :mod:`tos_runtime.recon.witness_synthetic` reads the evidence store directly;
* the broker-witness side is :class:`BrokerWitness` (plan §2 decision 3's own name) — the
  **port**, with :class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness` as
  Phase 5's one concrete implementation. A witness that cannot answer raises
  :class:`WitnessUnavailable` — it is NOT an empty :class:`WitnessSnapshot` (decision 3:
  an unanswerable witness must make confidence non-positive, never vacuously "nothing to
  report").

Pure data + Protocols only: stdlib (``dataclasses``, ``decimal``, ``enum``, ``typing``) +
``tos.engine.records`` (``InstrumentKey`` — the D1.1 ``tos_runtime -> tos`` edge, not a new
commons dependency) + ``tos_runtime.rcl.projection`` (re-export only) — no ``os.environ``,
no network, no persistence. This module mutates nothing.
"""

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
    """The (account, instrument, attempt) window a :class:`BrokerWitness` is asked about.

    ``attempt_ids`` names the attempts the caller already knows about (from RCL /
    evidence) — a witness order whose own ``attempt_id`` is absent from this set (or
    ``None`` on the wire) is exactly the "orphan broker order" case
    :class:`~tos_runtime.recon.service.ReconciliationService` classifies; a witness
    implementation MUST NOT filter its returned orders down to only these attempt ids
    (that would make orphan detection structurally impossible), it filters by
    ``account``/``instrument_keys`` only.
    """

    account: str
    instrument_keys: tuple[InstrumentKey, ...] = ()
    attempt_ids: tuple[str, ...] = ()
    as_of_generation: int | None = None


@dataclass(frozen=True)
class WitnessOrder:
    """One broker-witness-observed order (plan §2 decision 3)."""

    attempt_id: str | None
    broker_execution_id: str | None
    quantity: Decimal | None
    remaining: Decimal | None
    state: WitnessOrderState


@dataclass(frozen=True)
class WitnessSnapshot:
    """A :class:`BrokerWitness` observation at one generation (plan §2 decision 3).

    ``provenance`` names the concrete witness implementation honestly (e.g.
    ``"synthetic-ledger"``) so a consumer — and a future independent-review pass — can
    tell a Phase 5 synthetic-transport-derived snapshot apart from a genuine broker read
    (Phase 6+). See :mod:`tos_runtime.recon.witness_synthetic`'s module docstring for the
    disclosed Phase 5 independence caveat this field exists to keep visible.
    """

    observed_at_generation: int | None
    orders: tuple[WitnessOrder, ...]
    positions: tuple[tuple[str, Decimal], ...] = ()
    cash: Decimal | None = None
    provenance: str = ""


class WitnessUnavailable(Exception):
    """Raised by :meth:`BrokerWitness.observe` when the witness cannot answer at all.

    Decision 3 (plan §2): an unanswerable witness is NOT an empty
    :class:`WitnessSnapshot` — the caller must make confidence non-positive (never
    re-arm, never release capacity) on this path, distinct from "the witness answered
    and reported nothing here".
    """


@runtime_checkable
class BrokerWitness(Protocol):
    """The broker-side observation port (plan §2 decision 3's own name).

    ``observe`` either returns a genuine :class:`WitnessSnapshot` or raises
    :class:`WitnessUnavailable` — there is no third "empty but successful" outcome
    distinct from a snapshot with zero ``orders`` (a witness that successfully queried
    and genuinely has nothing to report legitimately returns an empty-``orders``
    snapshot; only an outright failure to query raises).
    """

    def observe(self, scope: WitnessScope) -> WitnessSnapshot:
        """Observe broker-side state for ``scope``, or raise :class:`WitnessUnavailable`."""
        ...


@dataclass(frozen=True)
class EgressReceiptObservation:
    """One attempt's durably recorded egress-result receipt (runtime evidence-receipt path).

    Populated from the durable ``EGRESS_RESULT_CONSUMED``/``RESULT_UNMATCHED`` evidence
    kind (``tos.engine.records.EngineEvidenceRecord``, appended by
    ``tos_runtime.evidence.sinks.EngineEvidenceSinkAdapter``). ``finality_proof_recorded``
    is ``True`` only when a separate, durably recorded ``POSTTRADE_FINALITY_PROOF``
    evidence entry exists for the same attempt (``tos_runtime.posttrade.finality
    .SyntheticFinalityProducer``'s own output) — this is the runtime's Final Quantity
    Proof token source for :func:`tos.recon.field_specific_release_proof_ok`'s
    ``ReleaseProofInputs.final_quantity_proof_token`` (ADR-002-030 §12 ``ORDER_FQP``); a
    receipt with no separately recorded proof leaves this ``False`` (fail-closed — a fill
    receipt alone is not a Final Quantity Proof).
    """

    attempt_id: str | None
    account: str | None
    instrument: str | None
    egress_result_kind: str | None
    broker_execution_id: str | None
    filled_quantity: Decimal | None
    remaining_quantity: Decimal | None
    finality_proof_recorded: bool
    source_ref: str


@runtime_checkable
class EvidenceReceiptReader(Protocol):
    """The evidence-receipt observation port :class:`~tos_runtime.recon.service
    .ReconciliationService` depends on (constructor arg ``evidence_reader``).

    This package ships no concrete implementation (out of this lane's file list) — a
    future lane wires one over the durable evidence store the same way
    :mod:`tos_runtime.recon.witness_synthetic` reads it for the witness side. Every test
    in this package satisfies this Protocol with a plain in-memory double.
    """

    def receipts(self, scope: WitnessScope) -> tuple[EgressReceiptObservation, ...]:
        """Return every recorded receipt observation within ``scope``.

        Like :meth:`BrokerWitness.observe`, an implementation MUST NOT filter down to
        only ``scope.attempt_ids`` — a receipt for an attempt outside that set is the
        "receipt-only" classification, not something to silently drop.
        """
        ...
