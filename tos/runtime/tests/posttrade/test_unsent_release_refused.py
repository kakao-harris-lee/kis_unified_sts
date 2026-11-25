"""A send the egress gateway refused before any transport call releases its reservation (11-20)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egressgw import BrokerEgressGateway
from tos.egressgw.records import GatewayEvidenceRecord
from tos.egressgw.vocabulary import SendHaltReason
from tos.engine import CommitmentStep, EngineCore
from tos.engine.records import AttemptRequest, SendHandoff
from tos.engine.state import ProvisionalReservationLedger
from tos.engine.vocabulary import (
    RESERVATION_DISCARDED_UNSENT_KIND,
    EgressKnowledge,
    UnsentDiscardReason,
)
from tos.rcl import CapacityState, TransitionCause
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import (
    EngineEvidenceSinkAdapter,
    GatewayEvidenceSinkAdapter,
)
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.unsent_release import (
    CAPACITY_RELEASE_INTENT_KIND,
    REFUSED_BEFORE_TRANSPORT_CAUSE,
    UnsentReleasePass,
    find_unsent_release_candidate,
    unsent_release_command_id,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import permit_reservation_id

from ..engine import _fixtures as fx
from ..engine.conftest import FakeMonotonicSource
from .test_unsent_release import _open_rcl_reservation

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_RESERVATION_ID = permit_reservation_id(fx.ACCOUNT, fx.INSTRUMENT, fx.PERMIT_IDENTITY)
_SEND_WAIT_MS = 1_000


@pytest.fixture
def emergency_log(tmp_path: Any) -> EmergencyAppendLog:
    return EmergencyAppendLog(tmp_path / "emergency.jsonl")


class _Transmit:
    """First call: ``first`` (the gateway, or a scripted gateway shape); later calls accept."""

    def __init__(self, first: Callable[[AttemptRequest], SendHandoff]) -> None:
        self._first: Callable[[AttemptRequest], SendHandoff] | None = first
        self.accepted: list[str] = []

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        first, self._first = self._first, None
        if first is not None:
            return first(attempt)
        self.accepted.append(attempt.attempt_id)
        return SendHandoff(
            accepted_for_transmission=True, handoff_reference=attempt.attempt_id
        )


def _refusing_gateway(store: SqliteEvidenceStore) -> BrokerEgressGateway:
    """The real gateway with no bound context: it refuses at step 15, before seal and claim."""
    return BrokerEgressGateway(
        contexts={}, transport=None, sink=GatewayEvidenceSinkAdapter(store)
    )


def _scripted(
    store: SqliteEvidenceStore, rows: list[dict[str, Any]]
) -> Callable[[AttemptRequest], SendHandoff]:
    """Write the gateway rows a given refusal shape leaves behind, then refuse the hand-off."""
    sink = GatewayEvidenceSinkAdapter(store)

    def _call(attempt: AttemptRequest) -> SendHandoff:
        for row in rows:
            sink.record(GatewayEvidenceRecord(attempt_id=attempt.attempt_id, **row))
        return SendHandoff(accepted_for_transmission=None)

    return _call


def _runtime(
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    emergency_log: EmergencyAppendLog,
    rcl_log: SqliteCommitLog,
    transmit: _Transmit,
    *,
    bind_release: bool = True,
) -> tuple[EngineCore, EngineDriver, UnsentReleasePass, FakeMonotonicSource]:
    core = fx.build_core(
        stages=fx.admitting_stages(),
        transmit=transmit,
        sink=EngineEvidenceSinkAdapter(evidence_store),
    )
    clock = FakeMonotonicSource()
    driver = EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="refused-release-tests",
        monotonic_source=clock,
        max_send_result_wait_ms=_SEND_WAIT_MS,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    _open_rcl_reservation(
        rcl_log,
        reservation_id=_RESERVATION_ID,
        account=fx.ACCOUNT,
        instrument=fx.INSTRUMENT,
    )
    release = _pass(rcl_log, evidence_store, core.ledger)
    if bind_release:
        driver.bind_after_turn(release)
    return core, driver, release, clock


def _pass(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    ledger: ProvisionalReservationLedger,
) -> UnsentReleasePass:
    return UnsentReleasePass(
        rcl_log=rcl_log,
        projection=SqliteReservationProjectionReader(rcl_log),
        evidence_store=evidence_store,
        ledger=ledger,
        scheme=SCHEME,
        account=fx.ACCOUNT,
        instrument=fx.INSTRUMENT,
    )


def _payloads(store: SqliteEvidenceStore, kind: str) -> list[dict[str, Any]]:
    return [
        json.loads(payload_json)["payload"]
        for (payload_json,) in store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
        ).fetchall()
    ]


def _state(rcl_log: SqliteCommitLog) -> CapacityState | None:
    return SqliteReservationProjectionReader(rcl_log).reservation_state(_RESERVATION_ID)


def test_a_pre_transport_refusal_releases_and_the_next_open_is_sent(
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    emergency_log: EmergencyAppendLog,
    rcl_log: SqliteCommitLog,
) -> None:
    """The incident, end to end on the real gateway + driver: refused -> released -> sent."""
    transmit = _Transmit(_refusing_gateway(evidence_store))
    core, driver, _, clock = _runtime(
        evidence_store, inbox, emergency_log, rcl_log, transmit
    )

    refused = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert refused.flow is not None and refused.flow.handed_off is True
    assert refused.flow.attempt is not None
    attempt_id = refused.flow.attempt.attempt_id
    (refusal,) = _payloads(evidence_store, "SEND_REFUSED")
    assert refusal["step"] == CommitmentStep.SEND_BOUNDARY_VERIFICATION.value
    assert _payloads(evidence_store, "NETWORK_CALL_ENTERED") == []

    assert _state(rcl_log) is CapacityState.RELEASED
    assert core.ledger.outstanding(fx.instrument_key()) is None
    (discard,) = _payloads(evidence_store, RESERVATION_DISCARDED_UNSENT_KIND)
    assert discard == {
        "proposal_id": discard["proposal_id"],
        "reason": UnsentDiscardReason.SEND_REFUSED_BEFORE_TRANSPORT.value,
        "attempt_id": attempt_id,
    }
    (intent,) = _payloads(evidence_store, CAPACITY_RELEASE_INTENT_KIND)
    assert intent["cause"] == REFUSED_BEFORE_TRANSPORT_CAUSE
    assert intent["attempt_id"] == attempt_id
    (transition,) = [
        row
        for row in rcl_log.reservation_transition_history(
            writer_epoch=rcl_log.current_epoch()
        ).transitions
        if row.to_state is CapacityState.RELEASED
    ]
    assert transition.command_id == unsent_release_command_id(_RESERVATION_ID)
    assert transition.cause is TransitionCause.FINAL_QUANTITY_PROOF

    clock.advance(_SEND_WAIT_MS * 2)
    sent = driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert sent.flow is not None and sent.flow.handed_off is True
    assert sent.flow.halt_step is None
    assert len(transmit.accepted) == 1
    held = core.ledger.outstanding(fx.instrument_key())
    assert held is not None and held.attempt_id == transmit.accepted[0]
    assert _payloads(evidence_store, "RESULT_UNMATCHED") == []
    assert all(
        row.get("attempt_id") != attempt_id
        for row in _payloads(evidence_store, "EGRESS_RESULT_CONSUMED")
    )


_PRE_CLAIM = CommitmentStep.SEND_BOUNDARY_VERIFICATION
_REFUSED_AT_15 = {
    "kind": "SEND_REFUSED",
    "step": _PRE_CLAIM,
    "halt_reason": SendHaltReason.VERIFY_ITEM_DENIED,
}


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param(
            [
                {"kind": "SEND_SEALED", "step": _PRE_CLAIM},
                {"kind": "SEND_STARTED", "step": CommitmentStep.SEND_STARTED_DURABLE},
                {"kind": "NETWORK_CALL_ENTERED", "step": CommitmentStep.NETWORK_CALL},
                {
                    "kind": "SEND_REFUSED",
                    "step": CommitmentStep.NETWORK_CALL,
                    "halt_reason": SendHaltReason.TRANSPORT_RAISED,
                },
            ],
            id="transport-entered-then-raised",
        ),
        pytest.param(
            [
                {
                    "kind": "SEND_REFUSED",
                    "step": CommitmentStep.SEND_STARTED_DURABLE,
                    "halt_reason": SendHaltReason.SINGLE_USE_CLAIM_REFUSED,
                }
            ],
            id="claim-refused",
        ),
        pytest.param(
            [
                {
                    "kind": "SEND_REFUSED",
                    "step": CommitmentStep.SEND_STARTED_DURABLE,
                    "halt_reason": SendHaltReason.ATTEMPT_ALREADY_CONSUMED,
                }
            ],
            id="attempt-already-consumed",
        ),
        pytest.param(
            [{**_REFUSED_AT_15, "preserved_worst_credible_capacity": 1}],
            id="preserved-obligation",
        ),
        pytest.param(
            [{**_REFUSED_AT_15, "preserved_obligation_magnitude_unknown": True}],
            id="obligation-magnitude-unknown",
        ),
        pytest.param(
            [
                {"kind": "NETWORK_CALL_ENTERED", "step": CommitmentStep.NETWORK_CALL},
                _REFUSED_AT_15,
            ],
            id="network-call-row-in-the-flow",
        ),
        pytest.param([], id="no-refusal-row"),
    ],
)
def test_a_refusal_that_may_have_reached_transport_releases_nothing(
    rows: list[dict[str, Any]],
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    emergency_log: EmergencyAppendLog,
    rcl_log: SqliteCommitLog,
) -> None:
    """Negative: anything past the seal/claim, or any obligation, keeps the reservation held."""
    transmit = _Transmit(_scripted(evidence_store, rows))
    core, driver, _, _ = _runtime(
        evidence_store, inbox, emergency_log, rcl_log, transmit
    )

    result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert result.flow is not None and result.flow.handed_off is True

    assert _state(rcl_log) is CapacityState.COMMITTED_UNBOUND
    held = core.ledger.outstanding(fx.instrument_key())
    assert held is not None
    assert held.capacity_state is CapacityState.POTENTIALLY_LIVE
    assert _payloads(evidence_store, RESERVATION_DISCARDED_UNSENT_KIND) == []
    blocked = driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert blocked.flow is not None and blocked.flow.handed_off is False
    assert transmit.accepted == []


def test_an_applied_timeout_keeps_the_refused_reservation_held(
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    emergency_log: EmergencyAppendLog,
    rcl_log: SqliteCommitLog,
) -> None:
    """Negative: once an UNKNOWN/TIMEOUT result applied, the attempt's fate is not ours to call."""
    transmit = _Transmit(_refusing_gateway(evidence_store))
    core, driver, release, clock = _runtime(
        evidence_store, inbox, emergency_log, rcl_log, transmit, bind_release=False
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    clock.advance(_SEND_WAIT_MS)
    driver.run_until_idle()
    held = core.ledger.outstanding(fx.instrument_key())
    assert held is not None
    assert held.capacity_state is CapacityState.QUARANTINED_UNKNOWN
    assert held.knowledge is EgressKnowledge.UNKNOWN
    assert (
        find_unsent_release_candidate(
            evidence_store, account=fx.ACCOUNT, instrument=fx.INSTRUMENT
        )
        is None
    )

    assert release.run() is False
    assert _state(rcl_log) is CapacityState.COMMITTED_UNBOUND
    assert core.ledger.outstanding(fx.instrument_key()) is not None


def test_a_crash_between_the_refusal_and_the_release_is_released_at_boot(
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    emergency_log: EmergencyAppendLog,
    rcl_log: SqliteCommitLog,
) -> None:
    """The process dies right after the refused flow's receipt; boot reaches the same answer."""
    transmit = _Transmit(_refusing_gateway(evidence_store))
    core, driver, _, _ = _runtime(
        evidence_store, inbox, emergency_log, rcl_log, transmit, bind_release=False
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    held = core.ledger.outstanding(fx.instrument_key())
    assert held is not None and held.capacity_state is CapacityState.POTENTIALLY_LIVE
    assert _state(rcl_log) is CapacityState.COMMITTED_UNBOUND

    replayed = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    replayed.commit_unbound(fx.instrument_key(), proposal_id=held.proposal_id)
    assert held.attempt_id is not None
    replayed.bind_attempt(fx.instrument_key(), attempt_id=held.attempt_id)
    replayed.mark_potentially_live(fx.instrument_key())

    boot = _pass(rcl_log, evidence_store, replayed)
    assert boot.run() is True
    assert _state(rcl_log) is CapacityState.RELEASED
    assert replayed.outstanding(fx.instrument_key()) is None
    assert boot.run() is False
    assert len(_payloads(evidence_store, RESERVATION_DISCARDED_UNSENT_KIND)) == 1


def test_a_crash_after_the_rcl_release_finishes_only_the_engine_half(
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    emergency_log: EmergencyAppendLog,
    rcl_log: SqliteCommitLog,
) -> None:
    """RCL released, engine discard lost: boot discards once, with no second RCL release."""
    transmit = _Transmit(_refusing_gateway(evidence_store))
    core, driver, release, _ = _runtime(
        evidence_store, inbox, emergency_log, rcl_log, transmit, bind_release=False
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    original = core.ledger.discard_unsent
    core.ledger.discard_unsent = lambda ref: False  # type: ignore[method-assign]  # noqa: ARG005
    assert release.run() is False
    assert _state(rcl_log) is CapacityState.RELEASED
    core.ledger.discard_unsent = original  # type: ignore[method-assign]

    assert _pass(rcl_log, evidence_store, core.ledger).run() is True
    assert core.ledger.outstanding(fx.instrument_key()) is None
    releases = [
        row
        for row in rcl_log.reservation_transition_history(
            writer_epoch=rcl_log.current_epoch()
        ).transitions
        if row.to_state is CapacityState.RELEASED
    ]
    assert len(releases) == 1


def test_a_crash_between_the_discard_row_and_the_intent_row_is_finished_at_boot(
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    emergency_log: EmergencyAppendLog,
    rcl_log: SqliteCommitLog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """review-1122 LOW: the boot pass writes the CAPACITY_RELEASE_INTENT a crash lost."""
    transmit = _Transmit(_refusing_gateway(evidence_store))
    core, driver, release, _ = _runtime(
        evidence_store, inbox, emergency_log, rcl_log, transmit, bind_release=False
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))

    def _killed(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("kill -9 between the discard row and the intent row")

    monkeypatch.setattr(UnsentReleasePass, "_append_intent", _killed)
    with pytest.raises(RuntimeError):
        release.run()
    monkeypatch.undo()
    assert len(_payloads(evidence_store, RESERVATION_DISCARDED_UNSENT_KIND)) == 1
    assert _payloads(evidence_store, CAPACITY_RELEASE_INTENT_KIND) == []
    assert _state(rcl_log) is CapacityState.RELEASED

    boot = _pass(
        rcl_log,
        evidence_store,
        ProvisionalReservationLedger(max_unresolved_send_per_scope=1),
    )
    assert boot.finish_interrupted_intent() is True
    (intent,) = _payloads(evidence_store, CAPACITY_RELEASE_INTENT_KIND)
    assert intent["cause"] == REFUSED_BEFORE_TRANSPORT_CAUSE
    assert intent["reservation_id"] == _RESERVATION_ID
    assert boot.finish_interrupted_intent() is False
    assert len(_payloads(evidence_store, CAPACITY_RELEASE_INTENT_KIND)) == 1
    assert core.ledger.outstanding(fx.instrument_key()) is None


def test_no_intent_is_written_without_a_discard_row(
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    emergency_log: EmergencyAppendLog,
    rcl_log: SqliteCommitLog,
) -> None:
    """The repair never fabricates a release: no discard row (and RCL not RELEASED) -> nothing."""
    transmit = _Transmit(_refusing_gateway(evidence_store))
    _, driver, release, _ = _runtime(
        evidence_store, inbox, emergency_log, rcl_log, transmit, bind_release=False
    )
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert release.finish_interrupted_intent() is False
    assert _payloads(evidence_store, CAPACITY_RELEASE_INTENT_KIND) == []
