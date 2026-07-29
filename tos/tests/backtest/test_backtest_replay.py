"""§8-6 — replay reproducibility, honestly scoped (design #33 §5.2).

ADR-DEV-010 §7:167-168 (BTE-INV-005) requires a backtest to be hermetic and reproducible, and D-E3
realizes it *structurally*: there is no clock and no RNG anywhere on the path, so the same
``(bars, injected parameters, stage map, fill scenario)`` produce a byte-identical trace.

The scope limits are asserted just as explicitly as the property, because over-claiming here would
be the series' recurring defect:

* **reproducibility, not distinctness** (design #33 §5.2, D-E1 Gap-1). Two bars sharing a Snapshot
  digest may collapse to the same proposal identity; making *different* bars produce *different*
  identities depends on D-E2 supplying distinct Snapshot digests. The suite demonstrates the
  collapse rather than hiding it.
* **audit-grade, not acceptance-grade** (RFC-003 §10:365-367). "Replayable is not independently
  recomputable" — reproducing a run satisfies audit, not SAFE-034 independent recomputation, and it
  closes no EV.

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

from __future__ import annotations

from tos.backtest import (
    MANDATED_SCENARIOS,
    ScenarioId,
    reference_bars,
    scenario_for,
    trace_digest,
    trace_document,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine import replay_result_for
from tos.evidence import ReplayResultState

from ._backtest_fixtures import run_scenario

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def test_two_runs_of_every_scenario_produce_an_identical_trace() -> None:
    """(§5.2/§8-6) Same inputs ⇒ byte-identical trace document, for the whole mandated set."""
    for spec in MANDATED_SCENARIOS:
        first, _core_a, _fill_a, _sink_a = run_scenario(spec)
        second, _core_b, _fill_b, _sink_b = run_scenario(spec)
        assert trace_document(first) == trace_document(second), (
            f"{spec.scenario_id.value} is not reproducible — a clock or an RNG has entered the "
            "path (design #33 §4.4/§5.2)"
        )
        assert trace_digest(first, scheme=SCHEME) == trace_digest(second, scheme=SCHEME)


def test_the_fill_records_are_reproducible_too() -> None:
    """(§4.4) The D-E3-local records — magnitudes and prices — reproduce exactly."""
    spec = scenario_for(ScenarioId.ENTRY_PARTIAL_FILL)
    first, _core_a, _fill_a, _sink_a = run_scenario(spec)
    second, _core_b, _fill_b, _sink_b = run_scenario(spec)
    assert [record.model_dump(mode="json") for record in first.fill_records] == [
        record.model_dump(mode="json") for record in second.fill_records
    ]


def test_a_different_bar_stream_changes_the_trace() -> None:
    """(§5.2) The digest is not a constant — a different input really produces a different trace."""
    from ._backtest_fixtures import build_core, build_driver, build_fill_model

    spec = scenario_for(ScenarioId.AT_MOST_ONE_FIRING)

    def _run(bar_count: int):  # noqa: ANN202 - a local runner
        fill_model = build_fill_model(spec.fill_parameters, scenario_id=spec.scenario_id)
        driver = build_driver(fill_model, scenario_id=spec.scenario_id)
        core, _sink = build_core(transmit=fill_model)
        return driver.run(core, reference_bars(bar_count))

    assert trace_digest(_run(2), scheme=SCHEME) != trace_digest(_run(3), scheme=SCHEME)


def test_the_replay_judgement_is_a_match_for_an_identical_run() -> None:
    """(§5.2) The shipped ``compute_replay_result`` predicate is reused, never re-authored."""
    spec = scenario_for(ScenarioId.ENTRY_FULL_FILL)
    first, _core_a, _fill_a, _sink_a = run_scenario(spec)
    second, _core_b, _fill_b, _sink_b = run_scenario(spec)

    state = replay_result_for(
        expected_outcome_digest=trace_digest(first, scheme=SCHEME),
        actual_outcome_digest=trace_digest(second, scheme=SCHEME),
        baseline_supported=True,
        input_complete=True,
    )
    assert state is ReplayResultState.MATCH


def test_a_diverging_run_is_not_reported_as_a_match() -> None:
    """(§5.2) The predicate really discriminates — "green" is not a foregone conclusion."""
    full, _core_a, _fill_a, _sink_a = run_scenario(scenario_for(ScenarioId.ENTRY_FULL_FILL))
    partial, _core_b, _fill_b, _sink_b = run_scenario(
        scenario_for(ScenarioId.ENTRY_PARTIAL_FILL)
    )
    state = replay_result_for(
        expected_outcome_digest=trace_digest(full, scheme=SCHEME),
        actual_outcome_digest=trace_digest(partial, scheme=SCHEME),
        baseline_supported=True,
        input_complete=True,
    )
    assert state is not ReplayResultState.MATCH


def test_distinctness_across_bars_is_not_claimed() -> None:
    """(§5.2 / D-E1 Gap-1) Bars sharing a Snapshot digest may collapse to one proposal identity.

    Recorded rather than hidden: the slice's Capsule source is identical per bar because the value
    surface that would distinguish them is D-E2's (design #33 §3.5). The design explicitly does not
    claim distinctness, and this test pins that honest limit so a future reader does not mistake
    reproducibility for it.
    """
    from ._backtest_fixtures import build_converter

    ticks = list(build_converter().stream(reference_bars(3)))
    digests = {tick.payload.capsule.canonical_digest for tick in ticks}
    assert len(digests) == 1, (
        "slice #1 binds the same Capsule content per bar; per-bar identity distinctness depends on "
        "D-E2 producing distinct Snapshot digests (design #33 §5.2, D-E1 Gap-1)"
    )


def test_the_trace_document_is_json_native_and_needs_no_file_io() -> None:
    """(§6.1) The oracle artifact is a plain mapping — the harness writes nothing to disk."""
    import json

    run, _core, _fill_model, _sink = run_scenario(scenario_for(ScenarioId.ENTRY_ACK))
    document = trace_document(run)
    assert json.loads(json.dumps(document)) == document
    assert document["artifact_type"] == "tos.backtest.wiring_trace"
    assert document["closes_no_ev"] is True
