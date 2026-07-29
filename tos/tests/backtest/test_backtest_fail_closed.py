"""§8-3 / §8-10 — UNKNOWN conservatism and the fail-closed halt paths (design #33 §4.2/§5.1).

RFC-010 §8:256-259 — "Negative tests are required" — and §6 원칙 4:193-196 makes failure paths
first-class. The wiring's *only* safety value is that it stops, with its reason recorded, whenever a
required fact is missing, denied, unknown, or unverifiable (RFC-002 §10.8:761).

The UNKNOWN half is the subtler one. ``UNKNOWN`` and ``TIMEOUT`` are neither a rejection nor
safe-to-retry (RFC-005 §11:325-327): the capacity projection **stays** at ``POTENTIALLY_LIVE``,
nothing is released, and nothing is resubmitted (ADR-002-002 INV-005:168 / INV-006:174). A harness
that quietly retried, or that read a timeout as "not sent", would be manufacturing the double-send
the whole design exists to prevent — so every one of those readings is asserted absent here.

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

from __future__ import annotations

import pytest
from tos.backtest import (
    FillMode,
    FillParameters,
    FillSide,
    ScenarioId,
    reference_bars,
    scenario_for,
)
from tos.engine import (
    COORDINATOR_SHALL_NOT_FLAGS,
    CommitmentStep,
    EgressKnowledge,
    HaltReason,
)
from tos.rcl import CapacityState

from ._backtest_fixtures import (
    admitting_stages,
    build_core,
    build_driver,
    build_fill_model,
    instrument_key,
    run_scenario,
    stages_for,
)

# ---------------------------------------------------------------------------
# §8-3 — UNKNOWN / TIMEOUT conservatism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario_id", [ScenarioId.ENTRY_UNKNOWN, ScenarioId.ENTRY_TIMEOUT]
)
def test_unknown_and_timeout_retain_potentially_live_and_resubmit_nothing(
    scenario_id: ScenarioId,
) -> None:
    """(§8-3) Capacity is retained, knowledge is explicitly UNKNOWN, and nothing is re-sent."""
    run, core, fill_model, _sink = run_scenario(scenario_for(scenario_id))

    reservation = core.ledger.outstanding(instrument_key())
    assert reservation is not None
    assert reservation.capacity_state is CapacityState.POTENTIALLY_LIVE
    assert reservation.knowledge is EgressKnowledge.UNKNOWN
    assert reservation.knowledge is not EgressKnowledge.REJECTED, (
        "UNKNOWN is not a rejection (RFC-005 §11:325-327)"
    )
    assert run.handoff_count == 1
    assert len(fill_model.handoffs) == 1, "an UNKNOWN result must not trigger a blind resubmit"
    assert core.ledger.admits_new_exposure(instrument_key()) is False


def test_no_result_kind_whatsoever_frees_the_scope() -> None:
    """(§2.1) Whatever the band reports, the scope stays occupied — there is no release path."""
    from tos.backtest import MANDATED_SCENARIOS

    for spec in MANDATED_SCENARIOS:
        if spec.scenario_id is ScenarioId.FAIL_CLOSED_HALT:
            continue  # nothing was ever committed, so there is no reservation to retain
        _run, core, _fill_model, _sink = run_scenario(spec)
        assert core.ledger.admits_new_exposure(instrument_key()) is False, (
            f"{spec.scenario_id.value} freed the scope — no egress result releases capacity "
            "(state.py:22; RFC-002 §9.1:557-558)"
        )


def test_the_harness_never_retries_a_hand_off() -> None:
    """(RFC-005 §12:364) No retry path exists — aggregate exposure via retry is unconstructable."""
    for forbidden in ("retry", "resubmit", "resend", "replay_send"):
        from tos.backtest import BacktestDriver, DeterministicFillModel

        assert not hasattr(BacktestDriver, forbidden)
        assert not hasattr(DeterministicFillModel, forbidden)
    assert "creates_aggregate_exposure_via_retry" in COORDINATOR_SHALL_NOT_FLAGS


# ---------------------------------------------------------------------------
# §8-10 — the fail-closed halt paths, in full
# ---------------------------------------------------------------------------


def test_a_stage_that_produces_no_decision_halts_as_stage_unknown() -> None:
    """(§5.1 row 5 variant) An absent approval decision is restrictive — never an assumed grant."""
    fill_model = build_fill_model(
        FillParameters(mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY)
    )
    driver = build_driver(fill_model)
    core, _sink = build_core(
        stages=admitting_stages(
            unknown_steps=frozenset({CommitmentStep.INDEPENDENT_APPROVAL})
        ),
        transmit=fill_model,
    )
    run = driver.run(core, reference_bars(1))

    (halt,) = run.halts
    assert halt.halt_reason is HaltReason.STAGE_UNKNOWN
    assert halt.halt_step is CommitmentStep.INDEPENDENT_APPROVAL
    assert run.handoff_count == 0
    assert halt.halt_reason is not HaltReason.STAGE_DENIED, (
        "UNKNOWN and DENY stay distinguishable in the recorded reason (sequencer.py:463-476)"
    )


def test_a_missing_stage_is_a_stop_never_a_skip() -> None:
    """(RFC-002 §10.8:761) A required step with no injected stage halts the flow."""
    stages = admitting_stages()
    del stages[CommitmentStep.ECONOMIC_EFFECT_ENVELOPE]

    fill_model = build_fill_model(
        FillParameters(mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY)
    )
    driver = build_driver(fill_model)
    core, _sink = build_core(stages=stages, transmit=fill_model)
    run = driver.run(core, reference_bars(1))

    (halt,) = run.halts
    assert halt.halt_reason is HaltReason.STAGE_MISSING
    assert halt.halt_step is CommitmentStep.ECONOMIC_EFFECT_ENVELOPE
    assert run.handoff_count == 0


def test_an_absent_send_boundary_is_a_stop_never_a_skip() -> None:
    """(§4.5) No injected transmit ⇒ ``TRANSMIT_UNAVAILABLE``; absence is not a licence to skip."""
    fill_model = build_fill_model(
        FillParameters(mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY)
    )
    driver = build_driver(fill_model)
    core, _sink = build_core(transmit=None)
    run = driver.run(core, reference_bars(1))

    (halt,) = run.halts
    assert halt.halt_reason is HaltReason.TRANSMIT_UNAVAILABLE
    assert run.fill_records == ()


def test_a_raising_band_leaves_the_projection_conservatively_potentially_live() -> None:
    """(ADR-002-002 INV-005:168) A failed hand-off is never read as "not sent".

    Exercised through the band's own fail-closed path: a hand-off with no bound settlement context
    raises, and the projection — already advanced *before* the call (``sequencer.py:531``) — stays
    ``POTENTIALLY_LIVE`` with nothing resubmitted.
    """
    fill_model = build_fill_model(
        FillParameters(mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY)
    )
    core, _sink = build_core(transmit=fill_model)
    from ._backtest_fixtures import build_converter

    converter = build_converter()
    (tick,) = list(converter.stream(reference_bars(1)))
    # The context is deliberately *not* bound — the driver would have bound it.
    from tos.engine import EngineEvent, EventKind

    result = core.handle(
        EngineEvent(kind=EventKind.DECISION_TICK, decision_tick=tick.payload)
    )
    assert result.halt_reason is HaltReason.TRANSMIT_RAISED
    reservation = core.ledger.outstanding(instrument_key())
    assert reservation is not None
    assert reservation.capacity_state is CapacityState.POTENTIALLY_LIVE
    assert reservation.knowledge is EgressKnowledge.SENT_UNCONFIRMED


def test_a_denying_scenario_must_record_its_reason() -> None:
    """(§8-10) A denying scenario spec without a reason is unconstructable — no silent stops."""
    from tos.backtest import ScenarioSpec

    from ._backtest_fixtures import INTEGRITY_ERRORS

    with pytest.raises(INTEGRITY_ERRORS, match="denial reason"):
        ScenarioSpec(
            scenario_id=ScenarioId.FAIL_CLOSED_HALT,
            intent="deny with no recorded reason",
            bar_count=1,
            target_kind=scenario_for(ScenarioId.FAIL_CLOSED_HALT).target_kind,
            fill_parameters=FillParameters(mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY),
            denied_steps=(CommitmentStep.VENUE_ADMISSIBILITY_DECISION,),
        )


def test_deny_and_unknown_may_not_be_declared_for_the_same_step() -> None:
    """(§4.2 rule 2/3) DENY and UNKNOWN are distinct restrictive outcomes, never merged."""
    from tos.backtest import ScenarioSpec

    from ._backtest_fixtures import INTEGRITY_ERRORS

    with pytest.raises(INTEGRITY_ERRORS, match="both denying and"):
        ScenarioSpec(
            scenario_id=ScenarioId.FAIL_CLOSED_HALT,
            intent="contradictory stage declaration",
            bar_count=1,
            target_kind=scenario_for(ScenarioId.FAIL_CLOSED_HALT).target_kind,
            fill_parameters=FillParameters(mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY),
            denied_steps=(CommitmentStep.VENUE_ADMISSIBILITY_DECISION,),
            unknown_steps=(CommitmentStep.VENUE_ADMISSIBILITY_DECISION,),
            denial_reason="both at once",
        )


def test_every_halt_the_harness_records_names_its_reason() -> None:
    """(§8-10) Across the whole mandated set, no halt record is reasonless."""
    from tos.backtest import MANDATED_SCENARIOS

    for spec in MANDATED_SCENARIOS:
        run, _core, _fill_model, _sink = run_scenario(spec)
        for halt in run.halts:
            assert isinstance(halt.halt_reason, HaltReason)
            assert halt.yield_sequence >= 1


def test_the_scenario_stage_map_really_injects_the_declared_denials() -> None:
    """(§5.1) ``stages_for`` is not decorative — the declared step really denies."""
    spec = scenario_for(ScenarioId.FAIL_CLOSED_HALT)
    stages = stages_for(spec)
    from tos.engine import StageOutcome, StageRequest

    from ._backtest_fixtures import (
        issue_capsule,  # noqa: F401 - kept local to the assertion
    )

    request_step = CommitmentStep.VENUE_ADMISSIBILITY_DECISION
    verdict = stages[request_step](
        StageRequest(
            step=request_step,
            instrument_key=instrument_key(),
            proposal=_any_proposal(),
        )
    )
    assert verdict.outcome is StageOutcome.DENY


def _any_proposal():  # noqa: ANN202 - a local builder for the stage-request shape
    """The first Proposal a nominal scenario emits (used only to shape a StageRequest)."""
    run, _core, _fill_model, _sink = run_scenario(scenario_for(ScenarioId.ENTRY_ACK))
    for result in run.event_results:
        if result.pipeline is not None and result.pipeline.proposal is not None:
            return result.pipeline.proposal
    raise AssertionError("the nominal scenario emitted no proposal")
