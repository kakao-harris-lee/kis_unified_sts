"""Tests for :class:`~tos_runtime.engine.driver.EngineDriver`'s non-trade latch hook (TOS
runtime operations wiring plan, 2026-09-13, §2 decision 3): a restrictive
``CORPORATE_ACTION`` result latches a new-risk halt through the bound
:func:`~tos_runtime.nontrade.latch.latch_restrictive`; a non-restrictive one does not; and an
un-bound latch on a restrictive result is refused loudly, never silently skipped.

This suite builds its own ``CORPORATE_ACTION`` payload shapes directly (never importing
``tests/nontrade/fixtures/synthetic_observations.py`` — the "each package builds its own
fixtures" discipline ``tests/compose/test_rollover_scenario.py`` already states, since
``tos/runtime/tests`` is one firewall scan tree).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import CorporateActionPayload, EngineEvent
from tos.engine.vocabulary import EventKind
from tos.nontrade import (
    CredibleTransitionLegKind,
    NonTradeEventClass,
    NonTradeEventRecord,
    NonTradeEventWorkflowState,
    SplitTransformationKind,
    SplitTransformationSpec,
    TransitionEnvelope,
)
from tos_runtime.engine.driver import EngineDriver, EngineDriverInvariantError
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.nontrade.latch import latch_restrictive

from . import _fixtures as fx

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_NO_TIMEOUT_WITHIN_TEST = 10**12

_LEGS = frozenset(
    {
        CredibleTransitionLegKind.PRE_EVENT_POSITION_AND_ORDER,
        CredibleTransitionLegKind.POST_EVENT_QUANTITY_INSTRUMENT_MULTIPLIER_CURRENCY_CASH,
        CredibleTransitionLegKind.FRACTIONAL_QUANTITY_AND_CASH_IN_LIEU,
    }
)


def _restrictive_event(*, seq: int) -> EngineEvent:
    """The honestly-empty ``CORPORATE_ACTION`` payload — no coordinates supplied at all —
    reaches ``NONTRADE_TRAPPED`` (restrictive), the same "no venue admissibility source wired"
    case ``tests/nontrade/fixtures/synthetic_observations.py::futures_lifecycle_expiry`` proves
    at the processor/kernel-equivalence level."""
    return fx.corporate_action_event(seq=seq)


def _admissible_event(*, seq: int) -> EngineEvent:
    """A full "happy path" payload — every rank-5 conjunct positively proven — reaches
    ``NONTRADE_ADMISSIBLE`` (not restrictive)."""
    split = SplitTransformationSpec(
        kind=SplitTransformationKind.FORWARD_SPLIT,
        pre_quantity=Decimal("100"),
        post_quantity=Decimal("200"),
        pre_basis=Decimal("20"),
        post_basis=Decimal("10"),
        unit_spec="shares",
        rounding_rule="round-down",
        fractional_residual=Decimal("0"),
        cash_in_lieu=Decimal("0"),
    )
    envelope = TransitionEnvelope(
        present_legs=_LEGS,
        pre_event_exposure=Decimal("2000"),
        post_event_credible_exposure=Decimal("2000"),
    )
    event_record = NonTradeEventRecord(
        event_id="ca-admissible",
        event_class=NonTradeEventClass.CORPORATE_ACTION,
        source_identities=("test",),
        source_event_ids=("ca-admissible",),
        old_instrument_identity="KRX:005930",
        new_instrument_identity="KRX:005930",
        transformation_spec=split,
        transition_envelope=envelope,
        workflow_state=NonTradeEventWorkflowState.OBSERVED,
    )
    # Built directly (not via ``fx.corporate_action_event``): that helper's own ``event=...``
    # keyword is already bound, so it cannot take an overriding ``event`` record.
    payload = CorporateActionPayload(
        instrument_key=fx.instrument_key(),
        event=event_record,
        envelope=envelope,
        split_spec=split,
        required_legs=_LEGS,
        identity_transition_final=True,
        event_is_material=True,
        change_triggers=frozenset({"instrument:KRX:005930"}),
        earliest_credible_boundary="2026-09-10T00:00:00",
        latest_completion_boundary="2026-09-12T00:00:00",
        source_disagreement_bounded=True,
        field_confidences=frozenset({"CORROBORATED"}),
        venue_admissibility="ADMISSIBLE",
        time_freshness="FRESH",
        injected_worst_intermediate_risk=Decimal("5"),
        injected_credible_space_bounded=True,
        injected_union_capacity_known=True,
    )
    return EngineEvent(kind=EventKind.CORPORATE_ACTION, corporate_action=payload)


def _make_driver(
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
    bind_latch: bool = True,
) -> EngineDriver:
    core = fx.build_core()
    driver = EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=_SCHEME,
        continuity_id="driver-nontrade-latch-tests",
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    if bind_latch:
        driver.bind_nontrade_latch(latch_restrictive)
    return driver


def _incident_candidate_count(evidence_store: SqliteEvidenceStore) -> int:
    return evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'INCIDENT_CANDIDATE'"
    ).fetchone()[0]


def test_restrictive_result_latches_new_risk_halt(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    driver = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
    )
    assert inbox.new_risk_halt() is None
    result = driver.enqueue_and_run(_restrictive_event(seq=1))
    assert result.nontrade_outcome is not None
    assert result.nontrade_outcome.restrictive is True

    halt = inbox.new_risk_halt()
    assert halt is not None
    assert halt["reason"] == f"NONTRADE_{result.nontrade_outcome.disposition.value}"
    assert _incident_candidate_count(evidence_store) == 1
    assert driver.last_nontrade_evidence_seq() is not None


def test_non_restrictive_result_does_not_latch(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    driver = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
    )
    result = driver.enqueue_and_run(_admissible_event(seq=1))
    assert result.nontrade_outcome is not None
    assert result.nontrade_outcome.restrictive is False

    assert inbox.new_risk_halt() is None
    assert _incident_candidate_count(evidence_store) == 0
    # last_nontrade_evidence_seq is still recorded — every judged CORPORATE_ACTION, restrictive
    # or not, updates it (module docstring of _apply_nontrade_latch).
    assert driver.last_nontrade_evidence_seq() is not None


def test_last_nontrade_evidence_seq_is_none_before_any_corporate_action(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    driver = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
    )
    assert driver.last_nontrade_evidence_seq() is None
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    # a DECISION_TICK carries no nontrade_outcome -- still None afterwards.
    assert driver.last_nontrade_evidence_seq() is None


def test_last_nontrade_evidence_seq_matches_the_event_consumed_row(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    driver = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
    )
    driver.enqueue_and_run(_restrictive_event(seq=1))
    seq = driver.last_nontrade_evidence_seq()
    assert seq is not None
    row = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED' AND seq = ?",
        (seq,),
    ).fetchone()
    assert (
        row is not None
    ), "last_nontrade_evidence_seq must name a real EVENT_CONSUMED row"


def test_restrictive_result_without_a_bound_latch_raises(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source,
) -> None:
    """Mutation-lens M3: if the driver hook ignored ``restrictive`` (never latching), this would
    silently pass instead of raising -- proving the hook genuinely gates on it."""
    driver = _make_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        bind_latch=False,
    )
    with pytest.raises(EngineDriverInvariantError):
        driver.enqueue_and_run(_restrictive_event(seq=1))
