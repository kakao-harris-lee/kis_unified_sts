"""Phase 3 wave 2 KW2-B — the RFC-002 §10.7 Coordinator positive gates (design #31 §9-10; plan §2.1).

RFC-002 §10.7 names, among the Execution Coordinator's responsibilities, "verify current
Safety Authority" and "verify live authorization" — both *before* anything from the 19-step
Normal Commitment Flow runs. Slice #1 had no hosting point for either; this is that hosting
point: :class:`~tos.engine.CoordinatorPreconditions`, checked at the very top of every
``DECISION_TICK``.

Three properties, each named explicitly in the plan:

* an epoch that is not verifiably current refuses the tick before step 1 — no registry
  dispatch, no decision pipeline, no ``DECISION_PROPOSAL`` evidence, no ledger mutation;
* a transport that reaches a broker (``reaches_broker=True``) refuses the tick the same way,
  regardless of the authority verdict;
* both gates reading ``True`` leaves every pre-existing behaviour completely unchanged — the
  entire rest of the suite (built on ``AllTruePreconditions``) is that regression control.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

from tos.engine import (
    EvidenceKind,
    HaltReason,
)

from ._engine_fixtures import (
    AllTruePreconditions,
    RecordingEvidenceSink,
    RecordingTransmit,
    build_core,
    decision_tick,
)


class _TransportNature:
    """A minimal :class:`~tos.engine.core.TransportNatureLike` test double."""

    def __init__(self, *, reaches_broker: bool | None) -> None:
        self.reaches_broker = reaches_broker


def test_authority_not_current_refuses_the_tick_before_step_one() -> None:
    """(§9-10) ``authority_epoch_current() is not True`` ⇒ refused; nothing is consumed."""
    sink = RecordingEvidenceSink()
    core, _ = build_core(
        transmit=RecordingTransmit(),
        sink=sink,
        preconditions=AllTruePreconditions(authority=False),
    )
    result = core.handle(decision_tick(sequence=1))

    assert result.halt_reason is HaltReason.AUTHORITY_NOT_CURRENT
    assert result.pipeline is None
    assert result.flow is None
    # no DECISION_PROPOSAL (step 1) evidence, and no registry-dispatch evidence either — the
    # gate runs before the registry is even consulted
    kinds = {record.kind for record in sink.records}
    assert EvidenceKind.DECISION_OUTCOME_EMITTED not in kinds
    assert EvidenceKind.DECISION_WITHHELD not in kinds
    assert EvidenceKind.FLOW_STEP_ADMITTED not in kinds
    assert kinds == {EvidenceKind.COORDINATOR_PRECONDITION_REFUSED}


def test_authority_epoch_current_none_also_refuses_the_tick() -> None:
    """(§4.2 rule 1 positive-admit) ``None`` (unestablished) is not ``True`` and also refuses."""
    core, _ = build_core(
        transmit=RecordingTransmit(),
        preconditions=AllTruePreconditions(authority=None),
    )
    result = core.handle(decision_tick(sequence=1))
    assert result.halt_reason is HaltReason.AUTHORITY_NOT_CURRENT


def test_authority_refusal_leaves_the_ledger_untouched() -> None:
    """(§9-10 "아무것도 소비 안 함") No reservation is projected when authority is refused."""
    from ._engine_fixtures import instrument_key

    core, _ = build_core(
        transmit=RecordingTransmit(),
        preconditions=AllTruePreconditions(authority=False),
    )
    core.handle(decision_tick(sequence=1))
    assert core.ledger.outstanding(instrument_key()) is None


def test_a_broker_reaching_transport_refuses_the_tick() -> None:
    """(§9-10 "실주문 경로 구조 차단") ``reaches_broker=True`` refuses regardless of authority."""
    sink = RecordingEvidenceSink()
    core, _ = build_core(
        transmit=RecordingTransmit(),
        sink=sink,
        preconditions=AllTruePreconditions(authority=True, live_scope=False),
    )
    result = core.handle(decision_tick(sequence=1))

    assert result.halt_reason is HaltReason.LIVE_SCOPE_NOT_AUTHORIZED
    assert result.pipeline is None
    kinds = {record.kind for record in sink.records}
    assert kinds == {EvidenceKind.COORDINATOR_PRECONDITION_REFUSED}


def test_the_transport_nature_the_core_was_constructed_with_is_what_the_gate_sees() -> (
    None
):
    """(survey finding — constructor argument on the core) ``transport_nature`` flows through.

    A :class:`~tos.engine.CoordinatorPreconditions` stand-in that inspects
    ``transport_nature`` directly proves the exact object passed to ``EngineCore(...,
    transport_nature=...)`` at construction is what reaches
    :meth:`~tos.engine.CoordinatorPreconditions.live_scope_authorized` on every tick —
    unchanged, not re-derived.
    """

    seen: list[object] = []

    class _Recording:
        def authority_epoch_current(self) -> bool:
            return True

        def live_scope_authorized(self, transport_nature) -> bool:
            seen.append(transport_nature)
            return (
                transport_nature is not None
                and transport_nature.reaches_broker is False
            )

    nature = _TransportNature(reaches_broker=False)
    core, _ = build_core(
        transmit=RecordingTransmit(),
        preconditions=_Recording(),
        transport_nature=nature,
    )
    result = core.handle(decision_tick(sequence=1))

    assert seen == [nature]
    assert result.halt_reason is None


def test_both_gates_true_leaves_the_flow_completely_unchanged() -> None:
    """(regression control) Both ``True`` ⇒ the 19-step flow proceeds exactly as before."""
    core, sink = build_core(
        transmit=RecordingTransmit(),
        preconditions=AllTruePreconditions(),
    )
    result = core.handle(decision_tick(sequence=1))
    assert result.halt_reason is None
    assert result.flow is not None
    assert result.flow.handed_off is True
    kinds = {record.kind for record in sink.records}
    assert EvidenceKind.COORDINATOR_PRECONDITION_REFUSED not in kinds


def test_mutation_removing_the_gate_would_hand_off_on_a_refused_authority() -> None:
    """Mutation guard (plan §2.1 "뮤테이션: 게이트 제거 red").

    Simulates the mutation directly: a core built with a refusing ``preconditions`` object
    must **never** reach the send boundary. If the gate were removed from
    ``_handle_decision_tick``, this test goes red because ``transmit.attempts`` would be
    non-empty.
    """
    transmit = RecordingTransmit()
    core, _ = build_core(
        transmit=transmit,
        preconditions=AllTruePreconditions(authority=False),
    )
    core.handle(decision_tick(sequence=1))
    assert transmit.attempts == [], (
        "the Coordinator precondition gate must stop the flow before step 12's attempt "
        "request — nothing may reach the send boundary while authority is refused"
    )
