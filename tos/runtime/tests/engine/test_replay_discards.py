"""Boot replay reproduces a never-sent discard (2026-11-01 plan §3.2 / §5 ①, last row; #974).

The live runtime drops a reservation whose flow halted between step 9's atomic commit and the Send
Boundary (``tos.engine.state.ProvisionalReservationLedger.discard_unsent``) and records the fact
as a ``RESERVATION_DISCARDED_UNSENT`` row. A replay that did not re-apply that row would rebuild a
projection in which the scope is still occupied, so the *next* tick halts at the step-8 capacity
pre-check in the replay while it was admitted live — a divergence, and the #994 "every boot
rebuilds the same block" half of #974.

The wiring that decides *when* to discard (plan §3.3) is Q2; these tests stand in for it by
calling the kernel directly and appending the row the way the Q2 writer will, which is exactly
what the replay reader has to cope with.
"""

from __future__ import annotations

import json

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine import (
    CommitmentStep,
    EngineCore,
    Stage,
    UnsentDiscardReason,
    UnsentDiscardRef,
)
from tos.engine.vocabulary import RESERVATION_DISCARDED_UNSENT_KIND
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay import replay_engine
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.nontrade.latch import latch_restrictive

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_NO_TIMEOUT_WITHIN_TEST = 10**12
#: The flow halts here — step 10, after step 9's commit and before any send step (plan §1 F1).
_HALT_STEP = CommitmentStep.COMMITMENT_UNAVAILABILITY


def _halting_stages() -> dict[CommitmentStep, Stage]:
    return fx.admitting_stages(unknown_steps=frozenset({_HALT_STEP}))


def _core() -> EngineCore:
    return fx.build_core(stages=_halting_stages(), transmit=None)


def _driver(
    core: EngineCore,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> EngineDriver:
    driver = EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="replay-discard-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    driver.bind_nontrade_latch(latch_restrictive)
    return driver


def _held_proposal_id(core: EngineCore) -> str:
    """The proposal id of the reservation the halted flow left behind."""
    held = core.ledger.outstanding(fx.instrument_key())
    assert held is not None
    proposal_id = held.proposal_id
    assert isinstance(proposal_id, str)
    return proposal_id


def _record_discard(
    core: EngineCore, evidence_store: SqliteEvidenceStore, proposal_id: str
) -> None:
    """What the Q2 writer will do: discard, then record the fact a replay re-applies."""
    ref = UnsentDiscardRef(
        proposal_id=proposal_id,
        reason=UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION,
    )
    assert core.ledger.discard_unsent(ref) is True
    evidence_store.append(
        ref.model_dump(mode="json"),
        kind=RESERVATION_DISCARDED_UNSENT_KIND,
        record_class=RESERVATION_DISCARDED_UNSENT_KIND,
    )


def _diverged_rows(evidence_store: SqliteEvidenceStore) -> list[dict[str, object]]:
    return [
        payload
        for (payload_json,) in evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            ("REPLAY_DIVERGED",),
        )
        if (payload := json.loads(payload_json).get("payload", {})).get(
            "replay_result_state"
        )
        == "ENGINE_DISCARD_NOT_REPRODUCED"
    ]


def test_a_replay_of_a_log_containing_the_discard_reproduces_the_same_ledger(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Live: tick 1 halts pre-send, the reservation is discarded, tick 2 is admitted past step 8.
    The replay must reach the identical projection — same halt for tick 1, same admission for
    tick 2 — and record no divergence."""
    live = _core()
    driver = _driver(live, inbox, evidence_store, emergency_log)
    key = fx.instrument_key()

    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert live.ledger.admits_new_exposure(key) is False
    _record_discard(live, evidence_store, _held_proposal_id(live))
    assert live.ledger.admits_new_exposure(key) is True

    driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    # Tick 2 got past the capacity stage and reached the (absent) send boundary, so it holds the
    # scope again — the live fact the replay has to reproduce.
    held = live.ledger.outstanding(key)
    assert held is not None

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        _core,
        scheme=SCHEME,
        window_events=None,
    )
    assert verdict.diverged == ()
    assert verdict.ok
    assert verdict.total_compared == 2
    assert _diverged_rows(evidence_store) == []


def test_without_the_record_the_same_log_diverges(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """The control that makes the test above load-bearing: discard live but record nothing, and
    the replay rebuilds the blocked projection — tick 2 halts at step 8 where it was admitted
    live."""
    live = _core()
    driver = _driver(live, inbox, evidence_store, emergency_log)

    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    ref = UnsentDiscardRef(
        proposal_id=_held_proposal_id(live),
        reason=UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION,
    )
    assert live.ledger.discard_unsent(ref) is True
    driver.enqueue_and_run(fx.decision_tick_event(seq=2))

    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        _core,
        scheme=SCHEME,
        window_events=None,
    )
    assert len(verdict.diverged) == 1
    assert not verdict.ok


def test_a_row_the_replayed_projection_refuses_is_a_divergence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """The kernel's own gate is this reader's corroboration: a row naming a proposal the replayed
    projection does not hold as discardable is never applied, and is reported."""
    live = _core()
    driver = _driver(live, inbox, evidence_store, emergency_log)
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    evidence_store.append(
        {
            "proposal_id": "no-such-proposal",
            "reason": UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION.value,
        },
        kind=RESERVATION_DISCARDED_UNSENT_KIND,
        record_class=RESERVATION_DISCARDED_UNSENT_KIND,
    )

    replayed = _core()
    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: replayed,
        scheme=SCHEME,
        window_events=None,
    )

    assert verdict.diverged == ("engine-discard:no-such-proposal",)
    assert replayed.ledger.admits_new_exposure(fx.instrument_key()) is False
    (row,) = _diverged_rows(evidence_store)
    assert row["proposal_id"] == "no-such-proposal"
    assert row["reason"] == "the replayed projection refused the discard"


def test_a_malformed_row_is_a_divergence_and_never_applied(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """A row whose payload is not an ``UnsentDiscardRef`` (here: a reason outside the closed
    vocabulary) is refused without ever reaching the ledger."""
    live = _core()
    driver = _driver(live, inbox, evidence_store, emergency_log)
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    proposal_id = _held_proposal_id(live)
    evidence_store.append(
        {"proposal_id": proposal_id, "reason": "WHATEVER_I_LIKE"},
        kind=RESERVATION_DISCARDED_UNSENT_KIND,
        record_class=RESERVATION_DISCARDED_UNSENT_KIND,
    )

    replayed = _core()
    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        lambda: replayed,
        scheme=SCHEME,
        window_events=None,
    )

    assert verdict.diverged == (f"engine-discard:{proposal_id}",)
    assert replayed.ledger.admits_new_exposure(fx.instrument_key()) is False
    (row,) = _diverged_rows(evidence_store)
    assert row["reason"] == "malformed discard row"
