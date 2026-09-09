"""§4.6/§5.4 — post-``POTENTIALLY_LIVE_OBSERVED`` exception invariants (dev plan Phase 1 작업 3).

Once step 17's ``POTENTIALLY_LIVE_OBSERVED`` record has been written, the reservation is
conservatively possibly-live regardless of what :meth:`BrokerEgressGateway.__call__` does next
(design #34 §4.6 — the authoritative projection is D-E1's, advanced *before* this interface was
even called). What THIS file proves is that the gateway's own remaining work — steps 18-19 — keeps
three invariants no matter which collaborator raises after that point:

* **I1** — the attempt stays claimed/consumed (a re-call of the same attempt is refused, never a
  blind resubmit — RFC-005 §11:326-328, §12:362 item 6);
* **I2** — at most one *disposition-bearing* evidence record is produced for the attempt
  (``SEND_REFUSED`` with a true recorded reason, or ``EGRESS_RESULT_RECORDED``), and it is never
  fabricated to misrepresent what actually happened (design #34 §4.2's "a restrictive termination
  without a recorded reason is a silent stop, not a fail-closed one", read in both directions: a
  *false* SEND_REFUSED for a send that genuinely went out is exactly such a silent lie);
* **I3** — the injected transport's ``send_once`` is called **at most once** (single-shot by
  construction, §5.4 — "no blind resubmission").

Two fault sites — the evidence sink raising while recording a **known-good** outcome
(``EGRESS_RESULT_RECORDED`` or the supplementary ``UNCERTAIN_SEND`` ladder) — deliberately do
**not** convert to a halt: the send already happened, so recording ``SEND_REFUSED`` in its place
would fabricate a refusal for something that was, in fact, accepted (RFC-005 §11:322-323's
"a missing acknowledgement is NOT a non-acceptance", applied here to a missing evidence write
instead of a missing send acknowledgement). Those propagate uncaught instead — the caller sees a
crash, which design #34 §4.6 treats as the deliberate, expected outcome from this point on ("a
crash from here on is deliberately treated as possibly-live"). Every other post-projection fault
site *can* honestly resolve to a halt, because at the point it is detected the gateway does not
yet know the send succeeded (or, for a derivation fault, the transport was never even called).

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

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

# ---------------------------------------------------------------------------
# test doubles
# ---------------------------------------------------------------------------


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
    """A sink that raises for chosen evidence kinds and otherwise delegates (records) normally.

    Used to simulate the provisional evidence sink itself failing at a specific, chosen point in
    the step-19 sequence, without disturbing the steps that come before it.
    """

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


# ---------------------------------------------------------------------------
# control: the happy path is unaffected by the added guards
# ---------------------------------------------------------------------------


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
    assert sink.kinds[:17] == ("VERIFY_ITEM",) * 17
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True


# ---------------------------------------------------------------------------
# fault site: deriving the outbound coordinates raises before send_once is ever called
# ---------------------------------------------------------------------------


def test_a_coordinate_derivation_fault_halts_under_its_own_reason_before_any_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(Phase 4 작업 6) Absorbed into SEND_SEAL_UNCONSTRUCTABLE — this now runs before any claim.

    Misattributing this to TRANSPORT_RAISED would hide that the transport was never reached;
    tagging it with the old OUTBOUND_COORDINATE_DERIVATION_RAISED reason would misreport *where*
    it happened now that coordinate derivation runs at seal-build time, before the step-16 claim.
    """
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
    assert transport.calls == 0  # I3
    assert (
        gateway.ledger.attempt_consumed(attempt.attempt_id) is False
    )  # nothing claimed
    assert gateway.ledger.claims == ()
    assert sink.records[-1].kind == "SEND_REFUSED"  # I2
    assert sink.records[-1].halt_reason is SendHaltReason.SEND_SEAL_UNCONSTRUCTABLE
    # A second call still refuses without ever reaching the transport — nothing was ever
    # consumed, so this is a fresh evaluation each time, not a "consumed" replay refusal.
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.calls == 0


# ---------------------------------------------------------------------------
# fault site: the transport call itself raises
# ---------------------------------------------------------------------------


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
    assert transport.calls == 1  # I3
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True  # I1
    assert sink.records[-1].kind == "SEND_REFUSED"  # I2
    assert sink.records[-1].halt_reason is SendHaltReason.TRANSPORT_RAISED
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.calls == 1


# ---------------------------------------------------------------------------
# fault site: the transport returns, but the result cannot be read
# ---------------------------------------------------------------------------


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
    assert transport.calls == 1  # I3 — the single send_once call already happened
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True  # I1
    assert sink.records[-1].kind == "SEND_REFUSED"  # I2
    assert sink.records[-1].halt_reason is SendHaltReason.RESULT_UNREADABLE
    assert sink.records[-1].step is CommitmentStep.EVIDENCE_RECORD
    # the unreadable result is never registered — ``self.results`` only appends after the
    # EGRESS_RESULT_RECORDED evidence is built (gateway.py — well past this halt).
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
    assert transport.calls == 1  # I3
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True  # I1
    assert sink.records[-1].kind == "SEND_REFUSED"  # I2
    assert sink.records[-1].halt_reason is SendHaltReason.RESULT_UNREADABLE
    assert sink.records[-1].step is CommitmentStep.EVIDENCE_RECORD
    assert gateway.results == ()  # the unreadable result is never registered


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
    assert transport.calls == 1  # I3
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True  # I1
    assert sink.records[-1].kind == "SEND_REFUSED"  # I2
    assert sink.records[-1].halt_reason is SendHaltReason.RESULT_UNREADABLE
    assert sink.records[-1].step is CommitmentStep.EVIDENCE_RECORD
    assert gateway.results == ()  # the unreadable result is never registered


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
    assert transport.calls == 1  # I3
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True  # I1
    assert sink.records[-1].kind == "SEND_REFUSED"  # I2
    assert (
        sink.records[-1].halt_reason is SendHaltReason.RESULT_ATTEMPT_IDENTITY_MISMATCH
    )


# ---------------------------------------------------------------------------
# fault site: the evidence sink itself raises while recording a KNOWN-GOOD outcome
# ---------------------------------------------------------------------------


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

    assert (
        gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    )  # I1 survives the crash
    assert "SEND_REFUSED" not in sink.kinds  # no fabricated refusal
    assert (
        "EGRESS_RESULT_RECORDED" not in sink.kinds
    )  # the failed write was not silently faked
    assert len(transport.requests) == 1  # I3
    # A re-call still refuses cleanly (the ledger claim already blocks it) and sends nothing again.
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
    assert (
        sink.kinds[-1] == "EGRESS_RESULT_RECORDED"
    )  # no fabricated record was appended after it
    assert "SEND_REFUSED" not in sink.kinds  # no fabricated refusal either
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True  # I1
    assert len(transport.requests) == 1  # I3
    assert gateway(attempt).accepted_for_transmission is None
    assert len(transport.requests) == 1


# ---------------------------------------------------------------------------
# fault site: _halt itself cannot record, because the sink is broken for SEND_REFUSED too
# ---------------------------------------------------------------------------


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

    assert (
        gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    )  # I1 survives the crash
    assert (
        transport.calls == 1
    )  # I3 — no retry was attempted despite the double failure
    assert (
        "SEND_REFUSED" not in sink.kinds
    )  # the halt truly was not recorded — not faked either
