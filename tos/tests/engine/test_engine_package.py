"""Package-surface, honesty-declaration, and drift-anchor regression for ``tos.engine``."""

from __future__ import annotations

from typing import Any, cast

import pytest
import tos.engine as engine
from tos.canonical import EV_L1_PROVISIONAL_VERSION, ArtifactIntegrityError
from tos.engine import (
    COMMITMENT_FLOW_ORDER,
    COORDINATOR_REALIZED_STEPS,
    GUARANTEED_FAIL_CLOSED_STEPS,
    INJECTED_STAGE_STEPS,
    PROJECTION_RANK,
    PROVISIONAL_SINK_CHAIN_VERSION,
    SEND_BOUNDARY_STEPS,
    SEQUENCED_STEPS,
    CommitmentStep,
    EngineConfiguration,
    NullEvidenceSink,
    RecordingEvidenceSink,
    _base,
    adapters,
    admission,
    core,
    pipeline,
    records,
    registry,
    sequencer,
    sink,
    standins,
    state,
    step_number,
    vocabulary,
)
from tos.rcl import CapacityState

_SUBMODULES = {
    "tos.engine._base": _base,
    "tos.engine.adapters": adapters,
    "tos.engine.admission": admission,
    "tos.engine.core": core,
    "tos.engine.pipeline": pipeline,
    "tos.engine.records": records,
    "tos.engine.registry": registry,
    "tos.engine.sequencer": sequencer,
    "tos.engine.sink": sink,
    "tos.engine.standins": standins,
    "tos.engine.state": state,
    "tos.engine.vocabulary": vocabulary,
}


def test_every_declared_export_resolves() -> None:
    """No ``__all__`` entry is a phantom (anti-phantom: existence claims are checked too)."""
    missing = [name for name in engine.__all__ if not hasattr(engine, name)]
    assert (
        missing == []
    ), f"tos.engine.__all__ names symbols that do not exist: {missing}"


def test_the_export_list_has_no_duplicates() -> None:
    """A duplicated export hides a merge mistake."""
    assert len(engine.__all__) == len(set(engine.__all__))


@pytest.mark.parametrize(("module_name", "module"), sorted(_SUBMODULES.items()))
def test_every_submodule_declares_a_resolvable_surface(module_name, module) -> None:
    """Each submodule's declared surface resolves — an ``__all__`` phantom fails here."""
    for name in getattr(module, "__all__", ()):
        assert hasattr(module, name), f"{module_name}.__all__ names a missing {name!r}"


_ADR_002_002_SECTION_11_ORDER: tuple[CommitmentStep, ...] = (
    CommitmentStep.DECISION_PROPOSAL,
    CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,
    CommitmentStep.VENUE_ADMISSIBILITY_DECISION,
    CommitmentStep.INDEPENDENT_APPROVAL,
    CommitmentStep.ECONOMIC_EFFECT_ENVELOPE,
    CommitmentStep.AGGREGATE_RISK_DECISION,
    CommitmentStep.ACTION_FLOW_DECISION,
    CommitmentStep.LEDGER_VERIFICATION,
    CommitmentStep.ATOMIC_COMMIT,
    CommitmentStep.COMMITMENT_UNAVAILABILITY,
    CommitmentStep.ORDER_CONFORMANCE_PROOF,
    CommitmentStep.ATTEMPT_REQUEST,
    CommitmentStep.ATTEMPT_BIND_VERIFICATION,
    CommitmentStep.TRANSMISSION_CAPABILITY,
    CommitmentStep.SEND_BOUNDARY_VERIFICATION,
    CommitmentStep.SEND_STARTED_DURABLE,
    CommitmentStep.POTENTIALLY_LIVE_TRANSITION,
    CommitmentStep.NETWORK_CALL,
    CommitmentStep.EVIDENCE_RECORD,
)


def test_the_flow_order_matches_an_independent_transcription_of_the_adr() -> None:
    """(§1.3 / RFC-005 §7:192) The shipped order equals an anchor derived from **no** constant."""
    assert COMMITMENT_FLOW_ORDER == _ADR_002_002_SECTION_11_ORDER, (
        "the shipped Normal Commitment Flow order differs from ADR-002-002 §11 (spec lines "
        "582-609) — RFC-005 §7:192 SHALL NOT reorder. Shipped: "
        f"{[step.value for step in COMMITMENT_FLOW_ORDER]}; ADR: "
        f"{[step.value for step in _ADR_002_002_SECTION_11_ORDER]}"
    )
    for position, (shipped, anchored) in enumerate(
        zip(COMMITMENT_FLOW_ORDER, _ADR_002_002_SECTION_11_ORDER), start=1
    ):
        assert shipped is anchored, (
            f"ADR-002-002 §11 step {position} is {anchored.value!r} but the shipped order has "
            f"{shipped.value!r} there (RFC-005 §7:192)"
        )
    assert len(_ADR_002_002_SECTION_11_ORDER) == 19
    assert set(_ADR_002_002_SECTION_11_ORDER) == set(CommitmentStep)


def test_the_flow_order_is_the_adr_nineteen_steps_in_order() -> None:
    """(§1.3) 19 steps, no duplicates, numbered 1-19 in the tuple's own order."""
    assert len(COMMITMENT_FLOW_ORDER) == 19
    assert len(set(COMMITMENT_FLOW_ORDER)) == 19
    assert set(COMMITMENT_FLOW_ORDER) == set(CommitmentStep)
    assert [step_number(step) for step in COMMITMENT_FLOW_ORDER] == list(range(1, 20))


def test_the_step_partition_is_exact_and_disjoint() -> None:
    """(§4.1/§4.3/§4.5) sequenced ∪ send-boundary = all; realized ∪ injected = sequenced."""
    assert set(SEQUENCED_STEPS) | SEND_BOUNDARY_STEPS == set(COMMITMENT_FLOW_ORDER)
    assert set(SEQUENCED_STEPS) & SEND_BOUNDARY_STEPS == set()
    assert COORDINATOR_REALIZED_STEPS | set(INJECTED_STAGE_STEPS) == set(
        SEQUENCED_STEPS
    )
    assert COORDINATOR_REALIZED_STEPS & set(INJECTED_STAGE_STEPS) == set()
    assert set(SEQUENCED_STEPS) == GUARANTEED_FAIL_CLOSED_STEPS
    assert {
        CommitmentStep.DECISION_PROPOSAL,
        CommitmentStep.ATTEMPT_REQUEST,
    } == COORDINATOR_REALIZED_STEPS
    assert len(INJECTED_STAGE_STEPS) == 12


def test_an_unknown_step_has_no_number() -> None:
    """(§2.2) A step outside the closed 19 is not a step — fail-closed."""
    with pytest.raises(ArtifactIntegrityError, match="not one of the 19"):
        step_number("STEP_20")  # type: ignore[arg-type]


def test_the_projection_rank_is_a_total_order_ending_at_released() -> None:
    """(§2.4; kernel round #3 §2 decision 5) The non-revival rank is total, and ``RELEASED`` is"""
    ranks = list(PROJECTION_RANK.values())
    assert sorted(ranks) == list(range(len(ranks)))
    assert len(set(PROJECTION_RANK)) == len(PROJECTION_RANK)
    assert "RELEASED" in {state.name for state in PROJECTION_RANK}, (
        "the engine's projection now has a released state, reachable only via "
        "ProvisionalReservationLedger.release's finality-proof-token gate (kernel round #3 §2 "
        "decision 5) — RCL remains the sole capacity-mutation authority (RFC-002 §9.1:557-558); "
        "this projection's release only mirrors a fact the RCL already established"
    )
    assert PROJECTION_RANK[CapacityState.RELEASED] == len(ranks) - 1, (
        "RELEASED must be the LAST (highest) rank — it is reachable only through the dedicated "
        "release() token gate, never through the ordinary rank-advance path any egress result "
        "uses (kernel round #3 §2 decision 5)"
    )


def test_the_provisional_sink_labels_itself_with_the_evidence_chain_version() -> None:
    """(§1.1 (a)) The sink's chain version is the shipped provisional one, not an invented tag."""
    from tos.evidence import EV_L1_PROVISIONAL_CHAIN_VERSION

    assert PROVISIONAL_SINK_CHAIN_VERSION == EV_L1_PROVISIONAL_CHAIN_VERSION


def test_the_sinks_satisfy_the_protocol_and_record_or_discard() -> None:
    """Both shipped sinks are usable — a missing sink would mean an unrecorded halt."""
    from tos.engine import EngineEvidenceRecord, EvidenceKind

    record = EngineEvidenceRecord(kind=EvidenceKind.FLOW_HALTED)
    recording = RecordingEvidenceSink()
    recording.record(record)
    assert recording.records == (record,)
    NullEvidenceSink().record(record)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dsl_evaluation_budget_steps": -1},
        {"max_unresolved_send_per_scope": -1},
        {"canonicalization_version": "  "},
        {"enforcement_mechanism_version": ""},
    ],
)
def test_an_ill_formed_injected_configuration_is_refused(kwargs) -> None:
    """(§8) Every bound arrives injected — an ill-formed one is refused, never defaulted."""
    base = {
        "dsl_evaluation_budget_steps": 8,
        "max_unresolved_send_per_scope": 1,
        "canonicalization_version": EV_L1_PROVISIONAL_VERSION,
        "enforcement_mechanism_version": "enf-0",
    }
    base.update(kwargs)
    with pytest.raises(Exception, match="must be"):
        EngineConfiguration(**cast("dict[str, Any]", base))


def test_no_numeric_bound_is_hardcoded_in_the_sources() -> None:
    """(§8) The engine hardcodes no threshold — every bound arrives on ``EngineConfiguration``."""
    import ast
    from pathlib import Path

    structural = {0, 1}
    engine_src = Path(__file__).resolve().parents[2] / "src" / "tos" / "engine"
    offenders: list[str] = []
    for path in sorted(engine_src.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(
                node.value, (int, float, complex)
            ):
                if isinstance(node.value, bool):
                    continue
                if node.value in structural:
                    continue
                offenders.append(
                    f"{path.name}:{node.lineno} numeric literal {node.value!r}"
                )
    assert offenders == [], f"hardcoded numeric bound found: {offenders}"


def test_the_numeric_literal_scan_detects_a_planted_bound(tmp_path) -> None:
    """The bound scan really catches a planted threshold — "green" is not a broken scan."""
    import ast

    planted = tmp_path / "planted.py"
    planted.write_text("MAX_AGE_MS = 1000\nDRIFT_PPM = 200\n", encoding="utf-8")
    tree = ast.parse(planted.read_text(encoding="utf-8"))
    found = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, int)
    }
    assert {1000, 200} <= found


def test_the_five_design_plug_slots_are_all_declared() -> None:
    """(§12) The D-E2/D-E3/D-E4 hand-off contract is complete — all five plugs exist."""
    from tos.engine import (
        DecisionContextResolver,
        EventSource,
        EvidenceSink,
        Stage,
        Transmit,
    )

    for protocol in (
        DecisionContextResolver,
        Stage,
        Transmit,
        EventSource,
        EvidenceSink,
    ):
        assert getattr(protocol, "_is_runtime_protocol", False) is True, (
            f"{protocol.__name__} must be a runtime-checkable Protocol so an injected "
            "implementation can be verified at the boundary"
        )


def test_a_plain_tuple_of_events_is_an_event_source() -> None:
    """(§12-4) Any iterable of events satisfies the source plug — backtest and live look alike."""
    from tos.engine import EventSource

    from ._engine_fixtures import decision_tick

    batch = (decision_tick(sequence=1),)
    assert isinstance(batch, EventSource)
