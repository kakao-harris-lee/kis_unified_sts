"""§4.6/§5.4 — post-``POTENTIALLY_LIVE_OBSERVED`` exception invariants (dev plan Phase 1 작업 3)."""

from __future__ import annotations

from typing import Any

import pytest
from tos.brokeradapter import SyntheticFillPolicy, SyntheticPaperTransport
from tos.egressgw import (
    BrokerEgressGateway,
    GatewayEvidenceRecord,
    RecordingGatewayEvidenceSink,
    SendHaltReason,
)
from tos.egressgw import gateway as gateway_module
from tos.engine import (
    AttemptRequest,
    CommitmentStep,
    EgressResultKind,
    EgressResultPayload,
    InstrumentKey,
)

from ._egressgw_fixtures import build_gateway, full_fill_transport, happy_context


class _UnreachableTransport:
    """A transport that must never be called (proves a pre-send fault stops before step 18)."""

    def __init__(self) -> None:
        self.calls = 0

    def send_once(self, attempt: AttemptRequest, **_: Any) -> EgressResultPayload:
        """Count the call and fail loudly — reaching this is itself the bug under test."""
        del attempt
        self.calls += 1
        raise AssertionError(
            "the transport must not be called when derivation already failed"
        )


class _RaisingTransport:
    """A transport that records its calls and raises (the established TRANSPORT_RAISED path)."""

    def __init__(self) -> None:
        self.calls = 0

    def send_once(self, attempt: AttemptRequest, **_: Any) -> EgressResultPayload:
        """Count the call and fail."""
        del attempt
        self.calls += 1
        raise RuntimeError("synthetic transport unavailable")


class _FixedResultTransport:
    """A transport that hands back one pre-built (possibly malformed) result object."""

    def __init__(self, result: Any) -> None:
        self.calls = 0
        self._result = result

    def send_once(self, attempt: AttemptRequest, **_: Any) -> Any:
        """Count the call and return the injected result unchanged."""
        del attempt
        self.calls += 1
        return self._result


class _WrongAttemptResultTransport:
    """A transport that answers about a *different* attempt (legitimate mismatch, not a fault)."""

    def __init__(self) -> None:
        self.calls = 0

    def send_once(
        self, attempt: AttemptRequest, *, instrument_key: InstrumentKey, **_: Any
    ) -> EgressResultPayload:
        """Return a well-formed result naming somebody else's attempt."""
        del attempt
        self.calls += 1
        return EgressResultPayload(
            instrument_key=instrument_key,
            attempt_id="attempt-somebody-else",
            kind=EgressResultKind.ACK,
        )


class _RaisingAttemptIdResult:
    """A result whose ``attempt_id`` access itself raises (malformed result, fault site 1)."""

    @property
    def attempt_id(self) -> str:
        """Simulate an unreadable identity field."""
        raise RuntimeError("synthetic malformed result: attempt_id is unreadable")


class _RaisingKindResult:
    """A result whose ``kind`` access raises once the identity has already checked out."""

    def __init__(self, attempt_id: str) -> None:
        self.attempt_id = attempt_id

    @property
    def kind(self) -> EgressResultKind:
        """Simulate an unreadable kind field."""
        raise RuntimeError("synthetic malformed result: kind is unreadable")


class _RaisingFilledQuantityResult:
    """A result whose ``filled_quantity`` access raises while the evidence detail is built."""

    def __init__(self, attempt_id: str) -> None:
        self.attempt_id = attempt_id
        self.kind = EgressResultKind.FULL_FILL

    @property
    def filled_quantity(self) -> Any:
        """Simulate an unreadable fill-magnitude field."""
        raise RuntimeError("synthetic malformed result: filled_quantity is unreadable")

    @property
    def remaining_quantity(self) -> Any:
        """A readable companion field — isolates the fault to ``filled_quantity`` alone."""
        return None


class _RaisingOnKindSink:
    """A sink that raises for chosen evidence kinds and otherwise delegates (records) normally."""

    def __init__(self, *, raise_on: frozenset[str]) -> None:
        self._delegate = RecordingGatewayEvidenceSink()
        self._raise_on = raise_on

    def record(self, record: GatewayEvidenceRecord) -> None:
        """Raise for a chosen kind, else delegate to the in-memory recorder."""
        if record.kind in self._raise_on:
            raise RuntimeError(f"synthetic sink failure recording kind={record.kind}")
        self._delegate.record(record)

    @property
    def records(self) -> tuple[GatewayEvidenceRecord, ...]:
        """Every record the delegate actually accepted, in arrival order."""
        return self._delegate.records

    @property
    def kinds(self) -> tuple[str, ...]:
        """The accepted record kinds, in arrival order."""
        return self._delegate.kinds


def _declared(kind: EgressResultKind) -> SyntheticPaperTransport:
    """A synthetic transport declaring one non-fill outcome (UNKNOWN / TIMEOUT / ACK / REJECT)."""
    return SyntheticPaperTransport(SyntheticFillPolicy(declared_kind=kind))


def test_the_happy_path_still_records_the_exact_step_order() -> None:
    """(§1.3/§4.6, hypothesis-free control) verify -> SEALED -> STARTED -> LIVE -> result."""
    attempt, context = happy_context()
    gateway, sink = build_gateway(attempt=attempt, context=context)

    handoff = gateway(attempt)

    assert handoff.accepted_for_transmission is True
    assert handoff.handoff_reference == attempt.attempt_id
    non_item_kinds = tuple(kind for kind in sink.kinds if kind != "VERIFY_ITEM")
    assert non_item_kinds == (
        "SEND_SEALED",
        "SEND_STARTED",
        "POTENTIALLY_LIVE_OBSERVED",
        "NETWORK_CALL_ENTERED",
        "EGRESS_RESULT_RECORDED",
    )
    assert sink.kinds[:7] == ("VERIFY_ITEM",) * 7
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True


def test_a_coordinate_derivation_fault_halts_under_its_own_reason_before_any_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(Phase 4 작업 6) Absorbed into SEND_SEAL_UNCONSTRUCTABLE — this now runs before any claim."""
    attempt, context = happy_context()
    transport = _UnreachableTransport()
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )

    def _raising_outbound_coordinates(_: Any) -> tuple[tuple[str, str | None], ...]:
        raise RuntimeError("synthetic coordinate derivation failure")

    monkeypatch.setattr(
        gateway_module, "outbound_coordinates", _raising_outbound_coordinates
    )

    handoff = gateway(attempt)

    assert handoff.accepted_for_transmission is None
    assert transport.calls == 0
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is False
    assert gateway.ledger.claims == ()
    assert sink.records[-1].kind == "SEND_REFUSED"
    assert sink.records[-1].halt_reason is SendHaltReason.SEND_SEAL_UNCONSTRUCTABLE
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.calls == 0


def test_a_raised_transport_after_projection_leaves_the_attempt_consumed_and_resubmits_nothing() -> (
    None
):
    """(RFC-005 §11:322-323) A missing acknowledgement is never read as "not accepted"."""
    attempt, context = happy_context()
    transport = _RaisingTransport()
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )

    handoff = gateway(attempt)

    assert handoff.accepted_for_transmission is None
    assert transport.calls == 1
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    assert sink.records[-1].kind == "SEND_REFUSED"
    assert sink.records[-1].halt_reason is SendHaltReason.TRANSPORT_RAISED
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.calls == 1


def test_a_result_whose_attempt_id_is_unreadable_halts_as_result_unreadable() -> None:
    """The send already happened (send_once returned) — this is UNKNOWN-restrictive, not a lie."""
    attempt, context = happy_context()
    transport = _FixedResultTransport(_RaisingAttemptIdResult())
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )

    handoff = gateway(attempt)

    assert handoff.accepted_for_transmission is None
    assert transport.calls == 1
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    assert sink.records[-1].kind == "SEND_REFUSED"
    assert sink.records[-1].halt_reason is SendHaltReason.RESULT_UNREADABLE
    assert sink.records[-1].step is CommitmentStep.EVIDENCE_RECORD
    assert gateway.results == ()
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.calls == 1


def test_a_result_whose_kind_is_unreadable_halts_as_result_unreadable() -> None:
    """Identity checked out, but the outcome itself cannot be read — still fail-closed, not lied."""
    attempt, context = happy_context()
    transport = _FixedResultTransport(_RaisingKindResult(attempt.attempt_id))
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )

    handoff = gateway(attempt)

    assert handoff.accepted_for_transmission is None
    assert transport.calls == 1
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    assert sink.records[-1].kind == "SEND_REFUSED"
    assert sink.records[-1].halt_reason is SendHaltReason.RESULT_UNREADABLE
    assert sink.records[-1].step is CommitmentStep.EVIDENCE_RECORD
    assert gateway.results == ()


def test_a_result_whose_filled_quantity_is_unreadable_halts_as_result_unreadable() -> (
    None
):
    """A single unreadable magnitude field is enough to refuse building the evidence detail."""
    attempt, context = happy_context()
    transport = _FixedResultTransport(_RaisingFilledQuantityResult(attempt.attempt_id))
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )

    handoff = gateway(attempt)

    assert handoff.accepted_for_transmission is None
    assert transport.calls == 1
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    assert sink.records[-1].kind == "SEND_REFUSED"
    assert sink.records[-1].halt_reason is SendHaltReason.RESULT_UNREADABLE
    assert sink.records[-1].step is CommitmentStep.EVIDENCE_RECORD
    assert gateway.results == ()


def test_a_result_naming_another_attempt_is_refused_without_transitioning_this_one() -> (
    None
):
    """(design #31 §2.1(ii)) A legitimate mismatch — not an exception — is still an I1/I2/I3 case."""
    attempt, context = happy_context()
    transport = _WrongAttemptResultTransport()
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )

    handoff = gateway(attempt)

    assert handoff.accepted_for_transmission is None
    assert transport.calls == 1
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    assert sink.records[-1].kind == "SEND_REFUSED"
    assert (
        sink.records[-1].halt_reason is SendHaltReason.RESULT_ATTEMPT_IDENTITY_MISMATCH
    )


def test_a_sink_failure_recording_the_result_propagates_and_fabricates_no_refusal() -> (
    None
):
    """The send genuinely succeeded — a fabricated SEND_REFUSED would misreport that fact."""
    attempt, context = happy_context()
    transport = full_fill_transport()
    sink = _RaisingOnKindSink(raise_on=frozenset({"EGRESS_RESULT_RECORDED"}))
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )

    with pytest.raises(RuntimeError, match="EGRESS_RESULT_RECORDED"):
        gateway(attempt)

    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    assert "SEND_REFUSED" not in sink.kinds
    assert "EGRESS_RESULT_RECORDED" not in sink.kinds
    assert len(transport.requests) == 1
    assert gateway(attempt).accepted_for_transmission is None
    assert len(transport.requests) == 1


def test_a_sink_failure_recording_the_uncertain_ladder_propagates_after_the_result_is_recorded() -> (
    None
):
    """The disposition-bearing record already landed; only the supplementary ladder write failed."""
    attempt, context = happy_context()
    transport = _declared(EgressResultKind.UNKNOWN)
    sink = _RaisingOnKindSink(raise_on=frozenset({"UNCERTAIN_SEND"}))
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )

    with pytest.raises(RuntimeError, match="UNCERTAIN_SEND"):
        gateway(attempt)

    assert "EGRESS_RESULT_RECORDED" in sink.kinds
    assert sink.kinds[-1] == "EGRESS_RESULT_RECORDED"
    assert "SEND_REFUSED" not in sink.kinds
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    assert len(transport.requests) == 1
    assert gateway(attempt).accepted_for_transmission is None
    assert len(transport.requests) == 1


def test_halt_propagates_when_the_sink_cannot_even_record_the_halt_itself() -> None:
    """No retry is attempted (design #34 §5.4) — a halt that cannot be recorded is not silent."""
    attempt, context = happy_context()
    transport = _RaisingTransport()
    sink = _RaisingOnKindSink(raise_on=frozenset({"SEND_REFUSED"}))
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )

    with pytest.raises(RuntimeError, match="SEND_REFUSED"):
        gateway(attempt)

    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    assert transport.calls == 1
    assert "SEND_REFUSED" not in sink.kinds
