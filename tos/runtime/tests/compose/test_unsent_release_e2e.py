"""#974's completion condition, end to end on a synthetic tree (plan §5 ③④; §0 완료 조건).

> 진입 POSITION_CONSUMED 뒤 CLOSE 가 step 9 커밋 후 송신 전에 halt 되어도, 다음 CLOSE 가
> step 8 을 통과한다. 한 프로세스와 재기동 뒤 모두. 실주문 0.

Both halves live here because they are the same scenario twice: ③ drives it in one process, ④
kills the process in the one window where the two durable stores disagree (the RCL release has
committed, the engine discard has not) and shows the next boot finishing it exactly once.

**Why this file is the twin of ``test_synthetic_venue_ledger_e2e.py``.** Everything #974 is about
begins at the entry reaching ``POSITION_CONSUMED``, which on a synthetic tree only happens with
``finality.yaml::witness: synthetic_venue_ledger`` (#1011). So this file boots the same tree, the
same entry+exit strategy, and the same production risk-state service that file's own full-cycle
test uses — and changes exactly one thing: the first CLOSE's step 14 cannot read its
``TransmissionCapabilityContext``, so the flow halts there, AFTER step 9 has committed the
reservation and BEFORE anything is handed off. That is the shape 10-29's measurement predicted
would first become reachable on a synthetic tree once the venue ledger is on (plan §1).

The injection is removed before the second CLOSE: the point is not that step 14 is broken for
ever, it is that the scope survives one halt.

Hermetic: ``tmp_path`` only, no network, no ambient env (D1.4). Real orders: 0 (synthetic
transport throughout — no broker is reachable from this suite at all).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tos.rcl import CapacityState
from tos_runtime.posttrade.unsent_release import (
    CAPACITY_RELEASE_INTENT_KIND,
    UNSENT_RELEASE_CAUSE,
    unsent_release_command_id,
)
from tos_runtime.rcl.projection import (
    SqliteReservationProjectionReader,
    outstanding_reservations,
)
from tos_runtime.recon.ports import WitnessScope
from tos_runtime.risk.ledger_stages import verdict_for_scope

from . import _fixtures as fx
from .test_compose_root import _reach_trusted
from .test_synthetic_venue_ledger_e2e import (
    _approve_and_run,
    _boot_with_the_production_risk_service,
    _close_runtime,
    _entry_exit_mapping,
    _reservations,
)
from .test_venue_ledger_wiring import turn_the_venue_ledger_on

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: The kernel's own discard record kind, as the runtime writer appends it.
_DISCARD_KIND = "RESERVATION_DISCARDED_UNSENT"


def _rows(runtime: Any, kind: str) -> list[dict[str, Any]]:
    return [
        json.loads(payload_json)["payload"]
        for (payload_json,) in runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
        ).fetchall()
    ]


def _break_step_14(runtime: Any) -> Any:
    """Make step 14 answer UNKNOWN: its egress-currentness context cannot be read.

    The narrowest injection that produces a genuine 10-14 halt on a fully real runtime — the
    stage is the production :class:`~tos_runtime.currentness.stages.TransmissionCapabilityStage`
    the core already holds, and only its injected ``context_reader`` is replaced, so every other
    stage, the RCL, the ledger and the evidence sink are untouched. The flow therefore commits at
    step 9 for real and stops at step 14 for real.

    Returns:
        The reader it replaced, for :func:`_restore_step_14`. Set directly rather than through
        ``monkeypatch`` so restoring it does not also undo the strategy-mapping patch this
        suite's boot depends on.
    """
    original = runtime.step14_stage._context_reader  # noqa: SLF001
    runtime.step14_stage._context_reader = lambda _request: None  # noqa: SLF001
    return original


def _restore_step_14(runtime: Any, original: Any) -> None:
    runtime.step14_stage._context_reader = original  # noqa: SLF001


def _entry_then_halted_close(runtime: Any, custody_root: Path) -> tuple[str, Any]:
    """Drive the entry to ``POSITION_CONSUMED``, then one CLOSE that halts at step 14.

    Returns:
        ``(the halted CLOSE's own RCL reservation id, the step-14 reader that was replaced)``.
        Step 14 is left broken — the caller restores it when (and if) it wants a CLOSE to go
        through.
    """
    _reach_trusted(runtime)
    _, entry = _approve_and_run(runtime, custody_root, fx.crossing_event(seq=0))
    assert entry.flow is not None and entry.flow.handed_off is True
    for _ in range(3):
        runtime.run_once(())
    entry_rows = _reservations(runtime)
    assert [state for _id, state in entry_rows] == [CapacityState.POSITION_CONSUMED]
    entry_reservation_id = entry_rows[0][0]

    step_14_reader = _break_step_14(runtime)
    exit_tick = fx.crossing_event(seq=1, close=fx.UPPER_BAND + 1_000)
    discovery, halted = _approve_and_run(runtime, custody_root, exit_tick)
    proposal = discovery.pipeline.proposal
    assert (proposal.position_effect, proposal.direction) == ("CLOSE", "SHORT")
    assert halted.flow is not None
    assert halted.flow.handed_off is False
    assert halted.flow.halt_step is not None
    assert halted.flow.halt_step.value == "TRANSMISSION_CAPABILITY"

    halted_ids = [
        reservation_id
        for reservation_id, _state in _reservations(runtime)
        if reservation_id != entry_reservation_id
    ]
    assert len(halted_ids) == 1, halted_ids
    return halted_ids[0], step_14_reader


# ===========================================================================
# plan §5 ③ — one process: the halt, the release, and the CLOSE that follows
# ===========================================================================


def test_a_close_that_halts_before_the_send_boundary_does_not_seal_the_scope(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plan §5 ③ — the completion condition, in one process.

    Concrete input: a synthetic tree with the venue ledger on; an entry that fills and reaches
    ``POSITION_CONSUMED``; a CLOSE whose step 14 cannot read its context, so the flow commits at
    step 9 and halts at step 14 with nothing handed off; then a second CLOSE.

    Concrete result, each independently checked:

    * the halted CLOSE's reservation is ``RELEASED`` in the RCL, under this path's own
      idempotency key and with a ``CAPACITY_RELEASE_INTENT`` naming
      ``UNSENT_FLOW_NON_EXECUTION`` — and exactly one ``RESERVATION_DISCARDED_UNSENT`` row;
    * step 8 ADMITs a CLOSE again over the one remaining consumed position — before this change
      it DENIED, because the engine's own pre-check saw the sealed reservation first;
    * the second CLOSE hands off and fills, netting the venue ledger flat, so both the entry and
      the real close end ``RELEASED``.

    Without the release path the second CLOSE halts at ``LEDGER_VERIFICATION`` instead and the
    position can never be closed through the engine again (#974 / #994).
    """
    monkeypatch.setattr(fx, "band_reversion_strategy_mapping", _entry_exit_mapping)
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    runtime = _boot_with_the_production_risk_service(
        config_dir_with_risk_state, data_dir, custody_root
    )
    assert runtime.risk_state is not None
    assert runtime.unsent_release is not None
    try:
        halted_reservation_id, step_14_reader = _entry_then_halted_close(
            runtime, custody_root
        )

        # --- the halted reservation was given back, with both records on file -------
        projection = SqliteReservationProjectionReader(runtime.rcl_log)
        assert (
            projection.reservation_state(halted_reservation_id)
            is CapacityState.RELEASED
        )
        discards = _rows(runtime, _DISCARD_KIND)
        assert len(discards) == 1
        assert discards[0]["reason"] == UNSENT_RELEASE_CAUSE
        unsent_intents = [
            row
            for row in _rows(runtime, CAPACITY_RELEASE_INTENT_KIND)
            if row.get("cause") == UNSENT_RELEASE_CAUSE
        ]
        assert len(unsent_intents) == 1
        assert unsent_intents[0]["reservation_id"] == halted_reservation_id
        release_commands = [
            row.command_id
            for row in runtime.rcl_log.reservation_transition_history(
                writer_epoch=runtime.rcl_log.current_epoch()
            ).transitions
            if row.reservation_id == halted_reservation_id
            and row.to_state is CapacityState.RELEASED
        ]
        assert release_commands == [unsent_release_command_id(halted_reservation_id)]

        # --- step 8 admits a CLOSE again --------------------------------------------
        instrument_key = runtime.context_resolver.instrument_key
        scope_rows = projection.scope_reservations(instrument_key)
        outstanding = outstanding_reservations(scope_rows)
        assert [row.state for row in outstanding] == [CapacityState.POSITION_CONSUMED]
        assert verdict_for_scope("CLOSE", scope_rows).outcome.value == "ADMIT"

        # --- and the next CLOSE actually closes --------------------------------------
        _restore_step_14(runtime, step_14_reader)
        _, closed = _approve_and_run(
            runtime,
            custody_root,
            fx.crossing_event(seq=2, close=fx.UPPER_BAND + 1_000),
        )
        assert closed.flow is not None and closed.flow.handed_off is True
        for _ in range(3):
            runtime.run_once(())

        witness = runtime.venue_ledger.witness
        assert witness is not None
        snapshot = witness.observe(
            WitnessScope(
                account=instrument_key.account, instrument_keys=(instrument_key,)
            )
        )
        assert snapshot.positions == (), snapshot.positions
        after = dict(_reservations(runtime))
        assert set(after.values()) == {CapacityState.RELEASED}, after
        # Still exactly one never-sent discard: the real close went out through the ordinary
        # finality path, not this one.
        assert len(_rows(runtime, _DISCARD_KIND)) == 1
    finally:
        _close_runtime(runtime)


# ===========================================================================
# plan §5 ④ — the restart, in the one window the two stores disagree
# ===========================================================================


def test_a_crash_between_the_rcl_release_and_the_engine_discard_is_finished_at_boot(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plan §5 ④ / review-1022 item 5 — ``kill -9`` right after the RCL release commit.

    Concrete input: the same halted CLOSE as ③, with the engine half made to die at exactly that
    instant (``discard_unsent`` raises, which is what a process vanishing between the two durable
    writes leaves behind — the driver's own ``after_turn`` contract already catches and counts a
    callback failure rather than halting the drain, so the live run continues with the RCL at
    ``RELEASED`` and the engine still holding). Then two more boots over the SAME stores.

    Concrete result: the first boot's own pass finishes the engine half — the rebuilt ledger no
    longer holds it, there is exactly ONE ``RESERVATION_DISCARDED_UNSENT`` row and ONE committed
    RCL release — the boot replay reports no divergence (compose would raise
    ``EngineReplayDiverged`` otherwise, so reaching the assertions at all is that result), and a
    second boot adds nothing: the repeated ``discard_unsent`` never writes a second row.
    """
    monkeypatch.setattr(fx, "band_reversion_strategy_mapping", _entry_exit_mapping)
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    runtime = _boot_with_the_production_risk_service(
        config_dir_with_risk_state, data_dir, custody_root
    )
    try:

        def _died_before_the_engine_half(ref: Any) -> bool:
            raise RuntimeError("kill -9 between the RCL release and the engine discard")

        # Set directly on this boot's own ledger, which is discarded with the runtime below —
        # ``monkeypatch.undo`` would also revert the strategy mapping the next boot needs.
        runtime.core.ledger.discard_unsent = _died_before_the_engine_half
        halted_reservation_id, _ = _entry_then_halted_close(runtime, custody_root)

        assert runtime.driver is not None
        assert runtime.driver.after_turn_failures >= 1
        assert (
            SqliteReservationProjectionReader(runtime.rcl_log).reservation_state(
                halted_reservation_id
            )
            is CapacityState.RELEASED
        )
        assert _rows(runtime, _DISCARD_KIND) == []
        instrument_key = runtime.context_resolver.instrument_key
        assert runtime.core.ledger.outstanding(instrument_key) is not None
    finally:
        _close_runtime(runtime)

    # --- boot 2: the pass finds the RCL already RELEASED and does the engine half -----
    rebooted = _boot_with_the_production_risk_service(
        config_dir_with_risk_state, data_dir, custody_root
    )
    try:
        assert rebooted.core.ledger.outstanding(instrument_key) is None
        assert len(_rows(rebooted, _DISCARD_KIND)) == 1
        releases = [
            row.command_id
            for row in rebooted.rcl_log.reservation_transition_history(
                writer_epoch=rebooted.rcl_log.current_epoch()
            ).transitions
            if row.reservation_id == halted_reservation_id
            and row.to_state is CapacityState.RELEASED
        ]
        assert releases == [unsent_release_command_id(halted_reservation_id)]
        scope_rows = SqliteReservationProjectionReader(
            rebooted.rcl_log
        ).scope_reservations(instrument_key)
        assert verdict_for_scope("CLOSE", scope_rows).outcome.value == "ADMIT"
    finally:
        _close_runtime(rebooted)

    # --- boot 3: the replay re-applies the row and the pass adds nothing --------------
    third = _boot_with_the_production_risk_service(
        config_dir_with_risk_state, data_dir, custody_root
    )
    try:
        assert third.core.ledger.outstanding(instrument_key) is None
        assert len(_rows(third, _DISCARD_KIND)) == 1
    finally:
        _close_runtime(third)
