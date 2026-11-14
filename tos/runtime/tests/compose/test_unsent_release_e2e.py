"""#974's completion condition, end to end on a synthetic tree (plan §5 ③④; §0 완료 조건)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tos.rcl import CapacityState
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.posttrade.unsent_release import (
    CAPACITY_RELEASE_INTENT_KIND,
    UNSENT_RELEASE_CAUSE,
    UnsentReleasePass,
    unsent_release_command_id,
)
from tos_runtime.rcl.projection import (
    SqliteReservationProjectionReader,
    outstanding_reservations,
)
from tos_runtime.recon.ports import WitnessScope
from tos_runtime.risk.ledger_stages import verdict_for_scope

from ..recovery.test_drill import _mark_handling_started
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

_DISCARD_KIND = "RESERVATION_DISCARDED_UNSENT"


def _rows(runtime: Any, kind: str) -> list[dict[str, Any]]:
    return [
        json.loads(payload_json)["payload"]
        for (payload_json,) in runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
        ).fetchall()
    ]


def _break_step_14(runtime: Any) -> Any:
    """Make step 14 answer UNKNOWN: its egress-currentness context cannot be read."""
    original = runtime.step14_stage._context_reader  # noqa: SLF001
    runtime.step14_stage._context_reader = lambda _request: None  # noqa: SLF001
    return original


def _restore_step_14(runtime: Any, original: Any) -> None:
    runtime.step14_stage._context_reader = original  # noqa: SLF001


def _entry_then_halted_close(runtime: Any, custody_root: Path) -> tuple[str, Any]:
    """Drive the entry to ``POSITION_CONSUMED``, then one CLOSE that halts at step 14."""
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


def test_a_close_that_halts_before_the_send_boundary_does_not_seal_the_scope(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plan §5 ③ — the completion condition, in one process."""
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

        instrument_key = runtime.context_resolver.instrument_key
        scope_rows = projection.scope_reservations(instrument_key)
        outstanding = outstanding_reservations(scope_rows)
        assert [row.state for row in outstanding] == [CapacityState.POSITION_CONSUMED]
        assert verdict_for_scope("CLOSE", scope_rows).outcome.value == "ADMIT"

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
        assert len(_rows(runtime, _DISCARD_KIND)) == 1
    finally:
        _close_runtime(runtime)


def test_a_crash_between_the_rcl_release_and_the_engine_discard_is_finished_at_boot(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plan §5 ④ / review-1022 item 5 — ``kill -9`` right after the RCL release commit."""
    monkeypatch.setattr(fx, "band_reversion_strategy_mapping", _entry_exit_mapping)
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    runtime = _boot_with_the_production_risk_service(
        config_dir_with_risk_state, data_dir, custody_root
    )
    try:

        def _died_before_the_engine_half(ref: Any) -> bool:
            raise RuntimeError("kill -9 between the RCL release and the engine discard")

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

    third = _boot_with_the_production_risk_service(
        config_dir_with_risk_state, data_dir, custody_root
    )
    try:
        assert third.core.ledger.outstanding(instrument_key) is None
        assert len(_rows(third, _DISCARD_KIND)) == 1
    finally:
        _close_runtime(third)


def test_a_held_recovery_barrier_boot_releases_nothing(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """review-1023 M1 — the boot pass is now after the barrier, so a HOLD gives nothing back."""
    monkeypatch.setattr(fx, "band_reversion_strategy_mapping", _entry_exit_mapping)
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    runtime = _boot_with_the_production_risk_service(
        config_dir_with_risk_state, data_dir, custody_root
    )
    try:
        monkeypatch.setattr(UnsentReleasePass, "run", lambda _self: False)
        halted_reservation_id, _ = _entry_then_halted_close(runtime, custody_root)
        instrument_key = runtime.context_resolver.instrument_key
        assert runtime.core.ledger.outstanding(instrument_key) is not None
        assert _rows(runtime, _DISCARD_KIND) == []
        _mark_handling_started(runtime, fx.crossing_event(seq=9))
    finally:
        _close_runtime(runtime)
    monkeypatch.undo()
    monkeypatch.setattr(fx, "band_reversion_strategy_mapping", _entry_exit_mapping)

    held = _boot_with_the_production_risk_service(
        config_dir_with_risk_state, data_dir, custody_root
    )
    try:
        assert held.recovery is not None and held.recovery.ready is False
        assert held.driver is None

        assert _rows(held, _DISCARD_KIND) == []
        assert [
            row
            for row in _rows(held, CAPACITY_RELEASE_INTENT_KIND)
            if row.get("cause") == UNSENT_RELEASE_CAUSE
        ] == []
        assert (
            SqliteReservationProjectionReader(held.rcl_log).reservation_state(
                halted_reservation_id
            )
            is CapacityState.COMMITTED_UNBOUND
        )
    finally:
        _close_runtime(held)


def test_a_raising_release_pass_still_lets_the_operator_projection_publish(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """review-1023 LOW-3 — the thrower must not suppress the component that reports it."""
    monkeypatch.setattr(fx, "band_reversion_strategy_mapping", _entry_exit_mapping)
    turn_the_venue_ledger_on(config_dir_with_risk_state)

    def _boom(self: UnsentReleasePass) -> None:
        raise RuntimeError("the release pass is broken")

    monkeypatch.setattr(UnsentReleasePass, "__call__", _boom)
    projection_path = tmp_path / "operator_projection.json"
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = compose_paper_runtime(
        config_dir_with_risk_state,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=None,
        action_flow_inputs_provider=None,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        projection_path=projection_path,
    )
    try:
        _reach_trusted(runtime)
        assert runtime.driver is not None
        assert projection_path.is_file()
        before = json.loads(projection_path.read_text())["projection_generation"]

        runtime.run_once((fx.crossing_event(seq=0),))

        after = json.loads(projection_path.read_text())
        assert after["projection_generation"] > before
        assert runtime.driver.after_turn_failures >= 1
        assert "the release pass is broken" in (
            runtime.driver.after_turn_last_error or ""
        )
    finally:
        _close_runtime(runtime)
