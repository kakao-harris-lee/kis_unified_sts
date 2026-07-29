"""Package-surface, honesty-declaration, and drift-anchor regression for ``tos.engine``.

Three jobs:

1. the **public surface** is exactly what ``__all__`` claims and every name resolves — an
   ``__all__`` entry that does not exist, or an export that is not declared, is a phantom;
2. the **honesty declarations** the design makes its top-level obligations (design #31 §1.1/§4.4)
   are actually present in the shipped docstrings: closes no EV, provisional stand-ins are
   non-authoritative, the fail-closed guarantee is steps 1-14, escape-safety is not claimed. A
   design whose honesty lives only in a plan document and not in the code is one refactor away
   from over-claiming;
3. the **drift anchors** — the 19-step order against the ADR's own numbering, the step partition,
   the context-source pair against the DSL constant, and the projection rank against the states the
   engine actually projects.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

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

#: Every submodule, imported statically (the firewall forbids ``importlib.import_module``).
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
    assert missing == [], f"tos.engine.__all__ names symbols that do not exist: {missing}"


def test_the_export_list_has_no_duplicates() -> None:
    """A duplicated export hides a merge mistake."""
    assert len(engine.__all__) == len(set(engine.__all__))


@pytest.mark.parametrize(("module_name", "module"), sorted(_SUBMODULES.items()))
def test_every_submodule_declares_a_resolvable_surface(module_name, module) -> None:
    """Each submodule's declared surface resolves — an ``__all__`` phantom fails here."""
    for name in getattr(module, "__all__", ()):
        assert hasattr(module, name), f"{module_name}.__all__ names a missing {name!r}"


@pytest.mark.parametrize(
    "phrase",
    [
        "closes no EV",
        "NON-AUTHORITATIVE PROVISIONAL",
        "fail-closed guarantee: steps 1-14 only",
        "escape-safety: not demonstrated",
        "reproducibility, not distinctness",
        "release: impossible here",
    ],
)
def test_the_package_docstring_carries_its_honesty_declarations(phrase) -> None:
    """(§1.1/§4.4/§4.5/§3.5/§6) The scope limits live in the code, not only in the plan."""
    assert engine.__doc__ is not None
    assert phrase in engine.__doc__, (
        f"the package docstring must state {phrase!r} — an honesty boundary that lives only in a "
        "design document is one refactor away from an over-claim"
    )


@pytest.mark.parametrize(
    ("module", "phrase"),
    [
        (state, "NON-AUTHORITATIVE PROVISIONAL"),
        (standins, "NON-AUTHORITATIVE PROVISIONAL"),
        (state, "no ``release`` / ``free`` / ``clear`` method"),
        (sequencer, "steps 15-19 are not hostable"),
        (sink, "over-realization"),
    ],
)
def test_the_provisional_modules_label_themselves(module, phrase) -> None:
    """(§4.4/§4.5/§9-3) Each provisional module states its own limits in its own docstring."""
    assert module.__doc__ is not None
    assert phrase in module.__doc__


# ---------------------------------------------------------------------------
# drift anchors
# ---------------------------------------------------------------------------


#: The ADR-002-002 §11 Normal Commitment Flow, transcribed **independently** from the spec text
#: (``tos-spec/src/part-1-foundation/ADR-002-002-Aggregate-Risk-Capacity-Commitment-Model.md``
#: lines 582-609: §11.1 steps 1-7 at 582-588, §11.2 steps 8-11 at 592-595, §11.3 steps 12-14 at
#: 599-601, §11.4 steps 15-19 at 605-609). It is deliberately a **hard-coded literal tuple** and is
#: derived from **no** engine constant: :data:`~tos.engine.COMMITMENT_FLOW_ORDER` is the subject
#: under test, so anchoring it to anything computed from itself proves nothing.
#:
#: Review MINOR-1 (adversarial code review, 2026-07-29): every order assertion in the suite was
#: self-referential — ``test_the_flow_order_is_the_adr_nineteen_steps_in_order`` compared against
#: ``step_number``, which is an ``enumerate`` of the very tuple it checks, and
#: ``test_the_sequenced_range_is_steps_one_to_fourteen`` compared against ``SEQUENCED_STEPS``, also
#: derived from it. A reviewer mutant that swapped the data-independent steps 2 and 3
#: (``CANDIDATE_COMMAND_CONSTRUCTION`` ↔ ``VENUE_ADMISSIBILITY_DECISION``) therefore SURVIVED the
#: whole suite. The safety-critical adjacencies are enforced behaviourally (step 11's proof digest
#: and step 9's permit identity must exist before step 12 builds the attempt; the projection must
#: reach ``POTENTIALLY_LIVE`` before the transmit hand-off), so the mutant had no safety effect —
#: but RFC-005 §7:192 declares the sequence itself a contract ("SHALL NOT redefine, **reorder**, or
#: abridge"), and a contract needs an anchor outside the artifact it constrains. This tuple is that
#: anchor, mirroring the ``_verify_context_source_anchor`` drift guard
#: (``tos/src/tos/engine/vocabulary.py``) and the ``COORDINATOR_SHALL_NOT_FLAGS`` anchor
#: (``test_engine_no_authority.py::test_the_authority_block_carries_the_eleven_shall_nots``).
_ADR_002_002_SECTION_11_ORDER: tuple[CommitmentStep, ...] = (
    # §11.1 Proposal and Approval (ADR lines 582-588)
    CommitmentStep.DECISION_PROPOSAL,  # 1. Decision Service creates an immutable Intent proposal
    CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,  # 2. ADR-002-020 candidate Canonical Broker Command
    CommitmentStep.VENUE_ADMISSIBILITY_DECISION,  # 3. ADR-002-019 Order Admissibility Decision
    CommitmentStep.INDEPENDENT_APPROVAL,  # 4. Independent Approval Service registers the Intent
    CommitmentStep.ECONOMIC_EFFECT_ENVELOPE,  # 5. ADR-002-020 derives the Economic Effect Envelope
    CommitmentStep.AGGREGATE_RISK_DECISION,  # 6. ADR-002-021 Aggregate Risk Decision
    CommitmentStep.ACTION_FLOW_DECISION,  # 7. ADR-002-022 Action Flow Decision
    # §11.2 Atomic Commitment (ADR lines 592-595)
    CommitmentStep.LEDGER_VERIFICATION,  # 8. RCL verifies epoch/limits/bindings/scope/capacity
    CommitmentStep.ATOMIC_COMMIT,  # 9. Ledger atomically commits + creates the Action Flow Permit
    CommitmentStep.COMMITMENT_UNAVAILABILITY,  # 10. Both commitments immediately unavailable
    CommitmentStep.ORDER_CONFORMANCE_PROOF,  # 11. ADR-002-020 Order Conformance Proof
    # §11.3 Attempt Binding (ADR lines 599-601)
    CommitmentStep.ATTEMPT_REQUEST,  # 12. Execution Coordinator creates a unique attempt request
    CommitmentStep.ATTEMPT_BIND_VERIFICATION,  # 13. Ledger verifies + atomically binds the attempt
    CommitmentStep.TRANSMISSION_CAPABILITY,  # 14. ATTEMPT_BOUND + single-use Transmission Capability
    # §11.4 Send Boundary (ADR lines 605-609)
    CommitmentStep.SEND_BOUNDARY_VERIFICATION,  # 15. Broker Adapter verifies all bindings
    CommitmentStep.SEND_STARTED_DURABLE,  # 16. claim/consume transition + durable SEND_STARTED
    CommitmentStep.POTENTIALLY_LIVE_TRANSITION,  # 17. Reservation transitions to POTENTIALLY_LIVE
    CommitmentStep.NETWORK_CALL,  # 18. Broker Adapter performs the network call
    CommitmentStep.EVIDENCE_RECORD,  # 19. Response/ack/error/timeout recorded as evidence
)


def test_the_flow_order_matches_an_independent_transcription_of_the_adr() -> None:
    """(§1.3 / RFC-005 §7:192) The shipped order equals an anchor derived from **no** constant.

    The load-bearing assertion of this module. ``COMMITMENT_FLOW_ORDER`` is not merely "19 distinct
    members numbered 1-19" — that is true of *any* permutation, and it is exactly what the rest of
    the suite was checking. Here the shipped tuple is compared, member for member and position for
    position, against :data:`_ADR_002_002_SECTION_11_ORDER`, transcribed by hand from ADR-002-002
    §11 (spec lines 582-609). RFC-005 §7:192 forbids redefining, **reordering**, or abridging that
    sequence, and design #31 §1.3/§4.1 makes the tuple order the contract, so a silent permutation —
    even of two steps whose adjacency no behaviour happens to enforce — is a contract breach.

    Review MINOR-1: this closes the surviving reviewer mutant that swapped steps 2 and 3.
    """
    assert COMMITMENT_FLOW_ORDER == _ADR_002_002_SECTION_11_ORDER, (
        "the shipped Normal Commitment Flow order differs from ADR-002-002 §11 (spec lines "
        "582-609) — RFC-005 §7:192 SHALL NOT reorder. Shipped: "
        f"{[step.value for step in COMMITMENT_FLOW_ORDER]}; ADR: "
        f"{[step.value for step in _ADR_002_002_SECTION_11_ORDER]}"
    )
    # Position-wise as well, so a failure names the offending step rather than dumping two lists.
    for position, (shipped, anchored) in enumerate(
        zip(COMMITMENT_FLOW_ORDER, _ADR_002_002_SECTION_11_ORDER), start=1
    ):
        assert shipped is anchored, (
            f"ADR-002-002 §11 step {position} is {anchored.value!r} but the shipped order has "
            f"{shipped.value!r} there (RFC-005 §7:192)"
        )
    # The anchor itself must stay a faithful, complete transcription — no dropped or duplicated
    # step could hide inside it (an abridged anchor would silently weaken the equality above).
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
    assert COORDINATOR_REALIZED_STEPS | set(INJECTED_STAGE_STEPS) == set(SEQUENCED_STEPS)
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


def test_the_projection_rank_is_a_total_order_over_the_projected_states() -> None:
    """(§2.4) The non-revival rank is total and contains no "released" state."""
    ranks = list(PROJECTION_RANK.values())
    assert sorted(ranks) == list(range(len(ranks)))
    assert len(set(PROJECTION_RANK)) == len(PROJECTION_RANK)
    assert "RELEASED" not in {state.name for state in PROJECTION_RANK}, (
        "the engine's projection has no released state — release is the RCL's act "
        "(RFC-002 §9.1:557-558)"
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
        EngineConfiguration(**base)


def test_no_numeric_bound_is_hardcoded_in_the_sources() -> None:
    """(§8) The engine hardcodes no threshold — every bound arrives on ``EngineConfiguration``.

    Only the two structural literals a pure orchestrator needs are tolerated, and the tolerance is
    stated rather than assumed:

    * ``0`` — the non-negativity comparison operand and a zero-remainder magnitude test;
    * ``1`` — the ``enumerate(..., start=1)`` origin of the ADR's own 1-based step numbering and a
      "more than one declared scope" cardinality test.

    Neither is a threshold. Anything else — a freshness bound, a budget, an age limit, an
    ``MAX_unresolved_send_per_scope`` — would be a Phase-0 bound smuggled into code (design #31 §8;
    RFC-005 §13:386 "SHALL NOT be hardcoded"), and the register records most of them as still
    unapproved.
    """
    import ast
    from pathlib import Path

    structural = {0, 1}
    engine_src = Path(__file__).resolve().parents[2] / "src" / "tos" / "engine"
    offenders: list[str] = []
    for path in sorted(engine_src.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, complex)):
                if isinstance(node.value, bool):
                    continue
                if node.value in structural:
                    continue
                offenders.append(f"{path.name}:{node.lineno} numeric literal {node.value!r}")
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
    """(§12) The D-E2/D-E3/D-E4 hand-off contract is complete — all five plugs exist.

    D-E1 is the *prerequisite* slice precisely because these interfaces must be fixed before D-E2,
    D-E3, and D-E4 can be wired (design #31 §12). Each is a slot, not an implementation: the
    Critical Input value surface, the market feed, the fill model, and the real send boundary all
    stay outside this package.
    """
    from tos.engine import (
        DecisionContextResolver,
        EventSource,
        EvidenceSink,
        Stage,
        Transmit,
    )

    for protocol in (DecisionContextResolver, Stage, Transmit, EventSource, EvidenceSink):
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
