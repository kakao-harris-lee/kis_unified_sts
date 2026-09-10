"""GAP 1 close-out tests (TOS Phase 5 W1) for :mod:`tos_runtime.recovery.reconciliation`, wired
against a real :class:`~tos_runtime.recon.service.ReconciliationService` (with the
``reservation_id_for_attempt`` bridge that module now supports) so that
:class:`~tos_runtime.recon.service.ReconciliationClass.MATCHED` is genuinely reachable for a
scope-level-reservation compose root, not merely disclosed as impossible.

The four scenarios below are the task brief's own acceptance tests:

(a) a possibly-live attempt whose evidence + witness corroborate (a ``FULL_FILL`` receipt,
    finality proof recorded, a matching witness order, and an open RCL reservation) is cleared,
    and folding the result into :class:`~tos_runtime.recovery.barrier.RecoveryBarrier` yields
    ``READY``.
(b) the same attempt, but the broker witness is unavailable, stays HELD with the witness's own
    unavailability reason.
(c) the SAME corroborating setup as (a), but with the kernel's own all-``None``
    :class:`~tos.recon.FreshnessMarker` default, stays HELD — freshness fails closed regardless
    of how strong the rest of the evidence is.
(d) a mutation guard: a service that reports ``permits_capacity_release`` alone (never
    ``permits_rearm``) must NOT clear the attempt — pins the conjunction
    :func:`~tos_runtime.recovery.reconciliation.reconcile_possibly_live_attempts` requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest
from tos.rcl import CapacityState
from tos.recon import FreshnessMarker
from tos_runtime.recon.ports import (
    EgressReceiptObservation,
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
    WitnessUnavailable,
)
from tos_runtime.recon.service import ReconciliationReport, ReconciliationService
from tos_runtime.recovery.barrier import RecoveryBarrier
from tos_runtime.recovery.inputs import RecoveryInputs
from tos_runtime.recovery.legacy_receipts import LegacyReceiptFacts
from tos_runtime.recovery.possibly_live import PossiblyLiveAttempt
from tos_runtime.recovery.reconciliation import (
    RECONCILED,
    reconcile_possibly_live_attempts,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: The scope-level reservation id this compose root actually uses
#: (``tos_runtime/compose/_engine_wiring.py``'s own ``f"resv-{account}-{instrument}"``
#: convention) — the identity :mod:`tos_runtime.recovery.inputs`'s own
#: ``reservation_id_for_attempt`` resolver produces, mirrored here directly rather than via that
#: resolver (this test constructs :class:`~tos_runtime.recon.service.ReconciliationService`
#: itself, to isolate the service-level behaviour from the compose-level wiring already covered
#: by ``test_inputs.py``).
_RESERVATION_ID = "resv-acct-1-005930"
_ACCOUNT = "acct-1"
_INSTRUMENT = "005930"


class _FakeRclReader:
    """A :class:`~tos_runtime.recon.ports.ReservationProjectionReader` test double."""

    def __init__(self, states: dict[str, CapacityState]) -> None:
        self._states = dict(states)

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        return self._states.get(reservation_id)

    def reservation_last_seq(self, _reservation_id: str) -> int | None:
        return None

    def all_reservations(self) -> dict[str, CapacityState]:
        return dict(self._states)

    def instrument_state(self, _key: object) -> CapacityState | None:
        return None

    def instrument_last_seq(self, _key: object) -> int | None:
        return None


class _FakeEvidenceReader:
    """A :class:`~tos_runtime.recon.ports.EvidenceReceiptReader` test double."""

    def __init__(self, receipts: tuple[EgressReceiptObservation, ...] = ()) -> None:
        self._receipts = receipts

    def receipts(self, _scope: WitnessScope) -> tuple[EgressReceiptObservation, ...]:
        return self._receipts


class _FakeWitness:
    """A :class:`~tos_runtime.recon.ports.BrokerWitness` test double."""

    def __init__(
        self, snapshot: WitnessSnapshot | None = None, *, unavailable: bool = False
    ) -> None:
        self._snapshot = snapshot or WitnessSnapshot(
            observed_at_generation=1, orders=(), provenance="fake"
        )
        self._unavailable = unavailable

    def observe(self, _scope: WitnessScope) -> WitnessSnapshot:
        if self._unavailable:
            raise WitnessUnavailable("test double: witness unavailable")
        return self._snapshot


@dataclass
class _StubService:
    """A minimal stand-in exposing only ``.reconcile`` — used by the (d) mutation guard to
    inject a HAND-PICKED report, bypassing the real kernel-backed judgement entirely, so the
    test asserts on the WIRING function's own conjunction rather than on whether the kernel
    predicates can be coaxed into a partial report."""

    report: ReconciliationReport

    def reconcile(
        self, _scope: WitnessScope, *, freshness: FreshnessMarker
    ) -> ReconciliationReport:
        del freshness  # unused -- this stub always returns the canned report
        return self.report


def _fresh_marker() -> FreshnessMarker:
    return FreshnessMarker(
        fresh_within_horizon=True,
        time_confidence_held=True,
        time_generation=1,
        anchored_generation=1,
    )


def _attempt(event_id: str = "event-1") -> PossiblyLiveAttempt:
    return PossiblyLiveAttempt(
        event_id=event_id,
        inbox_seq=1,
        handling_started_evidence_seq=1,
        handling_started_generation=1,
    )


def _inputs(**overrides: object) -> RecoveryInputs:
    base: dict[str, object] = {
        "rcl_writer_epoch": 1,
        "rcl_runtime_generation": 1,
        "open_reservations": (),
        "evidence_tip_seq": 1,
        "evidence_tip_key_generation": 1,
        "legacy_receipts": LegacyReceiptFacts(count=0, event_ids=()),
        "inbox_unconsumed_count": 1,
        "possibly_live_attempts": (_attempt(),),
        "composite_state_incomplete_attempt_ids": (),
        "custody_environment_label": "non-live-test",
        "custody_manifest_digest": "a" * 64,
    }
    base.update(overrides)
    return RecoveryInputs(**base)  # type: ignore[arg-type]


def _scope() -> WitnessScope:
    return WitnessScope(account=_ACCOUNT)


def _corroborated_service() -> ReconciliationService:
    """A real :class:`~tos_runtime.recon.service.ReconciliationService`, wired with an OPEN RCL
    reservation, a matching ``FULL_FILL`` evidence receipt (finality proof recorded), and a
    matching witness order — scenario (a)'s own setup, reused by (c) too."""
    receipt = EgressReceiptObservation(
        attempt_id="attempt-1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        egress_result_kind="FULL_FILL",
        broker_execution_id="exec-1",
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
        finality_proof_recorded=True,
        source_ref="evidence-egress-result",
    )
    witness_order = WitnessOrder(
        attempt_id="attempt-1",
        broker_execution_id="exec-1",
        quantity=Decimal("10"),
        remaining=Decimal("0"),
        state=WitnessOrderState.FILLED,
    )
    return ReconciliationService(
        rcl_reader=_FakeRclReader({_RESERVATION_ID: CapacityState.POSITION_CONSUMED}),
        evidence_reader=_FakeEvidenceReader((receipt,)),
        witness=_FakeWitness(
            WitnessSnapshot(
                observed_at_generation=1,
                orders=(witness_order,),
                provenance="fake",
            )
        ),
        reservation_id_for_attempt=lambda _attempt_id: _RESERVATION_ID,
    )


def test_a_corroborated_attempt_clears_and_barrier_goes_ready() -> None:
    inputs = _inputs()
    reconciliation = reconcile_possibly_live_attempts(
        inputs,
        service=_corroborated_service(),
        scope=_scope(),
        freshness=_fresh_marker(),
    )
    assert reconciliation == {"event-1": RECONCILED}

    verdict = RecoveryBarrier.verdict(
        _inputs(possibly_live_reconciliation=reconciliation)
    )
    assert verdict.ready is True


def test_b_witness_unavailable_holds_with_the_recon_reason() -> None:
    service = ReconciliationService(
        rcl_reader=_FakeRclReader({}),
        evidence_reader=_FakeEvidenceReader(()),
        witness=_FakeWitness(unavailable=True),
    )
    inputs = _inputs()
    reconciliation = reconcile_possibly_live_attempts(
        inputs, service=service, scope=_scope(), freshness=_fresh_marker()
    )
    assert "witness unavailable" in reconciliation["event-1"]
    assert reconciliation["event-1"] != RECONCILED

    verdict = RecoveryBarrier.verdict(
        _inputs(possibly_live_reconciliation=reconciliation)
    )
    assert verdict.ready is False


def test_c_default_freshness_marker_fails_closed_even_when_corroborated() -> None:
    """The SAME fully-corroborated setup as (a), but the kernel's own all-``None``
    ``FreshnessMarker`` default — every field fails closed regardless of corroboration
    strength (``tos.recon.predicates.freshness_ok``'s own contract)."""
    inputs = _inputs()
    reconciliation = reconcile_possibly_live_attempts(
        inputs,
        service=_corroborated_service(),
        scope=_scope(),
        freshness=FreshnessMarker(),
    )
    assert reconciliation["event-1"] != RECONCILED

    verdict = RecoveryBarrier.verdict(
        _inputs(possibly_live_reconciliation=reconciliation)
    )
    assert verdict.ready is False


def test_d_mutation_guard_requires_both_capacity_release_and_rearm() -> None:
    """A report granting ``permits_capacity_release`` alone (never ``permits_rearm``) must NOT
    clear the attempt — a mutation that changed the wiring's own ``and`` to accept either flag
    alone would turn this red."""
    partial_report = ReconciliationReport(
        field_confidences=(),
        classifications=(),
        permits_capacity_release=True,
        permits_rearm=False,
        reason="partial-report-for-mutation-guard",
    )
    inputs = _inputs()
    reconciliation = reconcile_possibly_live_attempts(
        inputs,
        service=_StubService(partial_report),  # type: ignore[arg-type]
        scope=_scope(),
        freshness=_fresh_marker(),
    )
    assert reconciliation == {"event-1": "partial-report-for-mutation-guard"}
    assert reconciliation["event-1"] != RECONCILED
