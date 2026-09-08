"""§4-§6 — the Broker Egress Gateway end to end: steps 15-19, fail-closed, and at-most-one.

Design #34 §12.1 targets exercised here:

* **-1 게이트 fail-closed 전수** — any verify item that denies / is UNKNOWN returns
  ``SendHandoff(accepted_for_transmission=None)``, calls **no** transport, and records the reason;
* **-2 no blind resubmit** — the same (proof, permit, coordinate) triple content-addresses to the
  same attempt identity and is refused; the transport is single-shot; ``uncertain_send_policy`` is
  structurally all-restrictive and ``same_order_retry_allowed`` is ``False``;
* **-6 partial as partial / UNKNOWN** — a partial fill stays partial and a timeout is UNKNOWN;
* **-7 at-most-one consumption** — the nonces are claimed exactly once and a result is applied
  only to the exact attempt it names.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

import inspect
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError
from tos.brokeradapter import SyntheticFillPolicy, SyntheticPaperTransport
from tos.egress import ClaimObservation, RestrictiveLatchState
from tos.egressgw import (
    AllFalseGatewayAuthority,
    BrokerEgressGateway,
    CandidateConstruction,
    RecordingGatewayEvidenceSink,
    SendAttemptLedger,
    SendBoundaryContext,
    SendHaltReason,
    SendVerifyItem,
    VerifyOutcome,
    build_order_conformance_proof,
    outbound_binding_mismatch,
    seal_matches_outbound,
    send_boundary_context,
    verify_send_boundary,
)
from tos.egressgw.gateway import _check_construction
from tos.engine import (
    AttemptRequest,
    EgressResultKind,
    EgressResultPayload,
    InstrumentKey,
)
from tos.ioc import ConformanceResult
from tos.ordering import OrderingEvent
from tos.venue import OrderAdmissibilityResult

from ._egressgw_fixtures import (
    CAPABILITY_NONCE,
    LOT_SIZE,
    PRINCIPAL,
    REQUEST_DIGEST,
    SCHEME,
    attempt_request,
    build_gateway,
    construction,
    egress_request,
    full_fill_transport,
    happy_context,
    ordering,
    quorum_certificate,
    venue_decision,
)


class _RecordingRaisingTransport:
    """A transport that records its calls and raises — the "no proof of not-sent" path."""

    def __init__(self) -> None:
        self.calls = 0

    def send_once(self, attempt: AttemptRequest, **_: Any) -> EgressResultPayload:
        """Count the call and fail."""
        del attempt
        self.calls += 1
        raise RuntimeError("synthetic transport unavailable")


class _WrongAttemptTransport:
    """A transport that answers about a *different* attempt."""

    def __init__(self) -> None:
        self.calls = 0

    def send_once(
        self, attempt: AttemptRequest, *, instrument_key: InstrumentKey, **_: Any
    ) -> EgressResultPayload:
        """Return a result naming somebody else's attempt."""
        del attempt
        self.calls += 1
        return EgressResultPayload(
            instrument_key=instrument_key,
            attempt_id="attempt-somebody-else",
            kind=EgressResultKind.ACK,
        )


class _OrderWitnessTransport:
    """A transport that snapshots the evidence sink at the moment it is called."""

    def __init__(self, sink: RecordingGatewayEvidenceSink) -> None:
        self._sink = sink
        self.kinds_at_call: tuple[str, ...] = ()
        self.calls = 0

    def send_once(
        self,
        attempt: AttemptRequest,
        *,
        instrument_key: InstrumentKey,
        reference: OrderingEvent = OrderingEvent(),
        **_: Any,
    ) -> EgressResultPayload:
        """Record what had already been written before the first byte."""
        self.calls += 1
        self.kinds_at_call = self._sink.kinds
        return EgressResultPayload(
            instrument_key=instrument_key,
            attempt_id=attempt.attempt_id,
            kind=EgressResultKind.ACK,
            reference=reference,
        )


def _declared(kind: EgressResultKind) -> SyntheticPaperTransport:
    """A synthetic transport declaring one non-fill outcome."""
    return SyntheticPaperTransport(SyntheticFillPolicy(declared_kind=kind))


# ---------------------------------------------------------------------------
# the happy path (steps 15-19 in order)
# ---------------------------------------------------------------------------


def test_the_baseline_send_is_accepted_and_records_every_step_in_order() -> None:
    """(§1.3 / §4.6) verify → SEND_SEALED → SEND_STARTED → POTENTIALLY_LIVE → transport → evidence."""
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
        "EGRESS_RESULT_RECORDED",
    )
    assert sink.kinds[:17] == ("VERIFY_ITEM",) * 17


def test_send_started_is_written_before_the_first_byte() -> None:
    """(RFC-005 §12:360 / ADR-002-002 §11.4:606) The claim / SEND_STARTED / first-byte order."""
    attempt, context = happy_context()
    sink = RecordingGatewayEvidenceSink()
    transport = _OrderWitnessTransport(sink)
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )
    assert gateway(attempt).accepted_for_transmission is True
    assert transport.calls == 1
    assert "SEND_SEALED" in transport.kinds_at_call
    assert "SEND_STARTED" in transport.kinds_at_call
    assert "EGRESS_RESULT_RECORDED" not in transport.kinds_at_call


def test_the_authorized_coordinates_cross_the_seam_as_opaque_ordered_scalars() -> None:
    """(RFC-002 §10.8:739) Broker-specific interpretation stays behind the adapter boundary."""
    attempt, context = happy_context()
    transport = full_fill_transport()
    gateway, _ = build_gateway(attempt=attempt, context=context, transport=transport)
    gateway(attempt)
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request.coordinate("account") == context.authorized_coordinates.account
    assert request.coordinate("environment") == "non-live-test"
    assert [name for name, _ in request.coordinates] == [
        "endpoint",
        "account",
        "environment",
        "action",
        "method",
        "route_identity",
        "credential_generation",
        "broker_session_generation",
        "egress_generation",
        "active_principal",
    ]


def test_every_gateway_record_carries_the_all_false_authority_block() -> None:
    """(§4 / ADR-002-013 §4.3) A gateway verdict is verified data, never permission."""
    attempt, context = happy_context()
    gateway, sink = build_gateway(attempt=attempt, context=context)
    gateway(attempt)
    for record in sink.records:
        effect = record.authority_effect
        for name in type(effect).model_fields:
            assert getattr(effect, name) is False
    with pytest.raises(ValidationError, match="must be false"):
        AllFalseGatewayAuthority(approves=True)


def test_the_gateway_authority_block_makes_no_transmits_claim() -> None:
    """(§0.4 E5 honesty) The boundary that delegates step 18 does not claim "does not transmit"."""
    assert "transmits" not in AllFalseGatewayAuthority.model_fields


# ---------------------------------------------------------------------------
# fail-closed over every item (design #34 §12.1-1)
# ---------------------------------------------------------------------------


#: One restrictive override per verify item the slice actually evaluates, each expected to stop
#: the send at that exact item. Written out per item so a silently-skipped check is visible.
_CASES: list[tuple[str, SendVerifyItem, dict[str, Any]]] = [
    (
        "no capability",
        SendVerifyItem.VALID_UNUSED_TRANSMISSION_CAPABILITY,
        {"transmission_capability": None},
    ),
    (
        "replayed capability nonce",
        SendVerifyItem.VALID_UNUSED_TRANSMISSION_CAPABILITY,
        {
            "prior_claims": (
                ClaimObservation(
                    nonce=CAPABILITY_NONCE,
                    principal=PRINCIPAL,
                    request_digest=REQUEST_DIGEST,
                ),
            )
        },
    ),
    (
        "attempt identity mismatch",
        SendVerifyItem.MATCHING_INTENT_AND_RESERVATION_IDENTITIES,
        {"reservation_attempt_id": "attempt-other"},
    ),
    (
        "no reservation identity",
        SendVerifyItem.MATCHING_INTENT_AND_RESERVATION_IDENTITIES,
        {"reservation_attempt_id": None},
    ),
    (
        "stale commitment epoch",
        SendVerifyItem.CURRENT_COMMITMENT_EPOCH,
        {"commitment_epoch_current": None},
    ),
    (
        "allowance withheld",
        SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY,
        {"account_instrument_action_allowed": False},
    ),
    (
        "max quantity allowance withheld",
        SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY,
        {"max_quantity_within_allowance": None},
    ),
    (
        "non-admitting session phase",
        SendVerifyItem.VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION,
        {"observed_session_phase": "AUCTION"},
    ),
    (
        "no venue decision",
        SendVerifyItem.VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION,
        {"venue_decision": None},
    ),
    (
        "decision disagrees with the current snapshot",
        SendVerifyItem.VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION,
        {"venue_decision": venue_decision(OrderAdmissibilityResult.UNKNOWN)},
    ),
    (
        "stale broker constraint generation",
        SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION,
        {"broker_constraint_generation_current": None},
    ),
    (
        "stale venue facts",
        SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION,
        {"venue_session_account_facts_current": False},
    ),
    ("no construction", SendVerifyItem.ORDER_CONSTRUCTION, {"construction": None}),
    (
        "unfenced conformance proof",
        SendVerifyItem.ORDER_CONSTRUCTION,
        {"conformance_proof": None},
    ),
    (
        "approval bound to another intent",
        SendVerifyItem.TRADING_APPROVAL,
        {"approval_intent_binding_digest": "someone-elses-intent"},
    ),
    (
        "no approval consumption",
        SendVerifyItem.TRADING_APPROVAL,
        {"approval_consumed_for_this_intent": None},
    ),
    (
        "permit is not the attempt's",
        SendVerifyItem.ACTION_FLOW,
        {"action_flow_permit_identity": "permit-other"},
    ),
    (
        "action flow commitment stale",
        SendVerifyItem.ACTION_FLOW,
        {"action_flow_commitment_current": None},
    ),
    (
        "restrictive latch is denied",
        SendVerifyItem.CURRENTNESS,
        {"restrictive_latch_state": RestrictiveLatchState.DENY_LATCHED},
    ),
    (
        "unknown latch state is latched",
        SendVerifyItem.CURRENTNESS,
        {"restrictive_latch_state": None},
    ),
    (
        "no currentness proof",
        SendVerifyItem.CURRENTNESS,
        {"egress_currentness_proof": None},
    ),
    (
        "no currentness result",
        SendVerifyItem.CURRENTNESS,
        {"egress_currentness_result": None},
    ),
    (
        "outbound digest substituted",
        SendVerifyItem.ACTUAL_OUTBOUND_CONFORMANCE,
        {"capsule_egress_request_digest": "tampered-digest"},
    ),
    (
        "outbound coordinates substituted",
        SendVerifyItem.ACTUAL_OUTBOUND_CONFORMANCE,
        {"authorized_coordinates": None},
    ),
]


@pytest.mark.parametrize(
    ("label", "item", "override"),
    [(label, item, override) for label, item, override in _CASES],
    ids=[label for label, _, _ in _CASES],
)
def test_one_restrictive_fact_stops_the_send_at_that_item(
    label: str, item: SendVerifyItem, override: dict[str, Any]
) -> None:
    """(§4.2 / §10.8:761) Any missing, stale, conflicting, or unverifiable fact is a rejection."""
    del label
    attempt, context = happy_context(**override)
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    handoff = gateway(attempt)
    assert handoff.accepted_for_transmission is None
    assert transport.requests == ()
    refusal = sink.records[-1]
    assert refusal.kind == "SEND_REFUSED"
    assert refusal.item is item
    assert refusal.halt_reason in {
        SendHaltReason.VERIFY_ITEM_DENIED,
        SendHaltReason.VERIFY_ITEM_UNKNOWN,
    }
    assert (refusal.detail or "").strip(), "a restrictive stop must record its reason"


def test_the_deferred_mesh_stops_a_broker_reaching_send_before_any_transport_call() -> (
    None
):
    """(§4.2 MAJOR-2) The mesh is required for a broker-reaching send and denies it."""
    from ._egressgw_fixtures import synthetic_nature

    attempt, context = happy_context(
        transport_nature=synthetic_nature(reaches_broker=True, route_bearing=True)
    )
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.requests == ()
    assert sink.records[-1].item is SendVerifyItem.CURRENT_SAFETY_AUTHORITY_EPOCH


def test_a_missing_context_is_a_stop_never_a_skip() -> None:
    """(§10.8:761) Without the verify list's facts there is nothing to verify against."""
    attempt, context = happy_context()
    transport = full_fill_transport()
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(contexts={}, transport=transport, sink=sink)
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.requests == ()
    assert sink.records[-1].halt_reason is SendHaltReason.CONTEXT_MISSING
    del context


def test_a_context_without_a_scope_is_a_stop() -> None:
    """(§10.8:761) The send's scope is a required fact."""
    attempt, context = happy_context(instrument_key=None)
    gateway, sink = build_gateway(attempt=attempt, context=context)
    assert gateway(attempt).accepted_for_transmission is None
    assert sink.records[-1].halt_reason is SendHaltReason.CONTEXT_MISSING


def test_an_absent_transport_is_a_stop_never_a_skip() -> None:
    """(design #34 §4.2) A missing send boundary is not a licence to skip it."""
    attempt, context = happy_context()
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=None, sink=sink
    )
    assert gateway(attempt).accepted_for_transmission is None
    assert sink.records[-1].halt_reason is SendHaltReason.TRANSPORT_UNAVAILABLE


# ---------------------------------------------------------------------------
# the outbound seam is bound to the construction (adversarial review MINOR-2)
# ---------------------------------------------------------------------------
#
# The verify list checks that a conformant construction exists (item 13) and that the egress
# *coordinates* equal their authorized values (item 17). The economic scalars the gateway hands
# the transport — quantity, price, side — and the command digest the outbound request carries
# were, before this hardening, passed through unbound: the fixtures wired them consistently and
# nothing enforced it. Each case below forges exactly one of them while leaving every one of the
# seventeen verify items satisfied, so only the binding check can catch it.


def _forged(**override: Any):
    """Run the gateway over the baseline with one forged outbound binding."""
    attempt, context = happy_context(**override)
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    handoff = gateway(attempt)
    return handoff, transport, sink, gateway


def test_a_forged_outbound_quantity_never_reaches_the_transport() -> None:
    """(MINOR-2 / EGRESS-INV-004:155-157) The seam quantity must be the derived quantity."""
    handoff, transport, sink, _ = _forged(outbound_quantity=Decimal("999"))
    assert handoff.accepted_for_transmission is None
    assert transport.requests == ()
    assert (
        sink.records[-1].halt_reason
        is SendHaltReason.OUTBOUND_NOT_BOUND_TO_CONSTRUCTION
    )
    assert "is not the derived quantity" in (sink.records[-1].detail or "")


def test_a_forged_outbound_price_never_reaches_the_transport() -> None:
    """(MINOR-2) The seam price must be the derived price."""
    handoff, transport, sink, _ = _forged(outbound_price=Decimal("1"))
    assert handoff.accepted_for_transmission is None
    assert transport.requests == ()
    assert (
        sink.records[-1].halt_reason
        is SendHaltReason.OUTBOUND_NOT_BOUND_TO_CONSTRUCTION
    )


def test_an_absent_outbound_scalar_is_a_stop_never_a_pass_through() -> None:
    """(MINOR-2 fail-closed) ``None`` is an unbound scalar, not "no opinion"."""
    for override in ({"outbound_quantity": None}, {"outbound_price": None}):
        handoff, transport, sink, _ = _forged(**override)
        assert handoff.accepted_for_transmission is None
        assert transport.requests == ()
        assert (
            sink.records[-1].halt_reason
            is SendHaltReason.OUTBOUND_NOT_BOUND_TO_CONSTRUCTION
        )


def test_a_forged_outbound_side_never_reaches_the_transport() -> None:
    """(ADR-002-020 §11:301) A route default may not silently flip the declared side."""
    handoff, transport, sink, _ = _forged(outbound_side="SELL")
    assert handoff.accepted_for_transmission is None
    assert transport.requests == ()
    assert "is not the side the command declares" in (sink.records[-1].detail or "")


def test_an_absent_outbound_side_is_a_stop() -> None:
    """(ADR-002-020 §11:301) An undeclared side cannot authorize a side."""
    handoff, transport, sink, _ = _forged(outbound_side=None)
    assert handoff.accepted_for_transmission is None
    assert transport.requests == ()
    assert (
        sink.records[-1].halt_reason
        is SendHaltReason.OUTBOUND_NOT_BOUND_TO_CONSTRUCTION
    )


def test_an_outbound_request_for_another_command_is_refused() -> None:
    """(MINOR-2 / EGRESS-INV-004) Item 17 stays satisfied yet the request is for another command.

    Both the request and the QCC are forged to the *same* other digest, so
    ``exact_binding_holds`` — which compares them to each other, not to the compiled command —
    still returns ``True``. Only the construction binding notices that the coordinates item 17
    compared belong to a command this flow never built.
    """
    attempt, context = happy_context(
        egress_request=egress_request("some-other-command-digest"),
        quorum_commit_certificate=quorum_certificate("some-other-command-digest"),
    )
    verification = verify_send_boundary(attempt=attempt, context=context)
    assert verification.admitted is True, "item 17 must still pass — that is the point"
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.requests == ()
    assert (
        sink.records[-1].halt_reason
        is SendHaltReason.OUTBOUND_NOT_BOUND_TO_CONSTRUCTION
    )
    assert "different command digest" in (sink.records[-1].detail or "")


def test_a_binding_failure_burns_no_capability_or_permit() -> None:
    """(MINOR-2 placement) The check runs before the step-16 claim, so no nonce is consumed."""
    _, _, _, gateway = _forged(outbound_quantity=Decimal("999"))
    assert gateway.ledger.claims == ()
    assert gateway.ledger.attempt_consumed(gateway.verifications[0].attempt_id) is False


def test_the_binding_predicate_accepts_the_consistent_baseline() -> None:
    """(both ways) A correctly wired context reports no mismatch — the check is not a blanket."""
    _, context = happy_context()
    assert outbound_binding_mismatch(context) is None


# ---------------------------------------------------------------------------
# Phase 4 작업 6 — SendSeal: sole source, seal failure, mutation pins (design §1.4)
# ---------------------------------------------------------------------------


def test_a_diverging_claim_and_active_principal_halts_as_seal_unconstructable() -> None:
    """(design §1.1 A2) A gap none of the 17 items or the binding check close — the seal does.

    ``context.principal`` (item 1's claim principal) and ``authorized_coordinates.
    active_principal`` (item 17's coordinate) are never compared to each other anywhere in the
    verify list or in ``outbound_binding_mismatch`` — only the seal's own validator does.
    """
    attempt, context = happy_context(principal="someone-else")
    gateway, sink = build_gateway(attempt=attempt, context=context)

    handoff = gateway(attempt)

    assert handoff.accepted_for_transmission is None
    assert gateway.ledger.claims == ()
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is False
    assert "SEND_SEALED" not in sink.kinds
    assert "SEND_STARTED" not in sink.kinds
    assert sink.records[-1].halt_reason is SendHaltReason.SEND_SEAL_UNCONSTRUCTABLE


def test_send_sealed_carries_the_full_seal_and_send_started_carries_only_its_digest() -> (
    None
):
    """(design §1.2) ``SEND_SEALED`` carries the whole seal; ``SEND_STARTED`` only its digest."""
    attempt, context = happy_context()
    gateway, sink = build_gateway(attempt=attempt, context=context)

    assert gateway(attempt).accepted_for_transmission is True

    (sealed_record,) = [r for r in sink.records if r.kind == "SEND_SEALED"]
    (started_record,) = [r for r in sink.records if r.kind == "SEND_STARTED"]
    (result_record,) = [r for r in sink.records if r.kind == "EGRESS_RESULT_RECORDED"]

    assert sealed_record.send_seal is not None
    seal = sealed_record.send_seal
    assert sealed_record.send_seal_digest is None
    assert started_record.send_seal is None
    assert started_record.send_seal_digest == seal.seal_digest
    assert result_record.send_seal_digest == seal.seal_digest


def test_the_claim_is_sourced_from_the_seal_not_context_request_digest() -> None:
    """(design §1.2) The step-16 claim binds ``seal.request_bytes_digest``, not
    ``context.request_digest`` — the two are deliberately different fixture values."""
    attempt, context = happy_context()
    assert context.request_digest == REQUEST_DIGEST
    gateway, sink = build_gateway(attempt=attempt, context=context)

    assert gateway(attempt).accepted_for_transmission is True

    (sealed_record,) = [r for r in sink.records if r.kind == "SEND_SEALED"]
    seal = sealed_record.send_seal
    assert seal is not None
    capability_claim, permit_claim = gateway.ledger.claims
    assert capability_claim.request_digest == seal.request_bytes_digest
    assert permit_claim.request_digest == seal.request_bytes_digest
    assert seal.request_bytes_digest != REQUEST_DIGEST


def test_transport_arguments_equal_the_seal_via_seal_matches_outbound() -> None:
    """(design §1.4 "유일 원천") The exact values ``send_once`` received are the seal's own."""
    attempt, context = happy_context()
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)

    assert gateway(attempt).accepted_for_transmission is True

    (request,) = transport.requests
    (sealed_record,) = [r for r in sink.records if r.kind == "SEND_SEALED"]
    seal = sealed_record.send_seal
    assert seal is not None
    assert (
        seal_matches_outbound(
            seal,
            coordinates=request.coordinates,
            quantity=request.quantity,
            price=request.price,
            side=request.side,
            instrument_key=request.instrument_key,
            attempt_id=request.attempt.attempt_id,
        )
        is True
    )


def test_mk2_a_resolver_asked_twice_never_leaks_its_second_answer_into_the_transport_call() -> (
    None
):
    """(mutation M-K2) The seal is built once, from one resolution; a later, differently-valued
    resolution can never leak into the transport call because step 18 never re-reads context.

    The resolver below would hand back a *different* outbound quantity on a second call — if the
    gateway ever re-resolved context (instead of reading the already-built seal) between the seal
    and the transport call, that different value would reach the transport. It never does.
    """
    attempt, context = happy_context()
    calls = {"n": 0}

    def _resolver(_: AttemptRequest) -> SendBoundaryContext:
        calls["n"] += 1
        if calls["n"] == 1:
            return context
        _, fresh = happy_context(outbound_quantity=Decimal("40"))
        return fresh

    transport = full_fill_transport()
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(contexts=_resolver, transport=transport, sink=sink)

    handoff = gateway(attempt)

    assert handoff.accepted_for_transmission is True
    assert calls["n"] == 1
    (request,) = transport.requests
    assert request.quantity == context.outbound_quantity
    assert request.quantity != Decimal("40")


def test_mk1_send_once_reads_only_seal_attributes_never_context_again() -> None:
    """(mutation M-K1, structural pin) ``send_once``'s keyword arguments never read
    ``context.*`` for the outbound-economic / identity fields — only ``seal.*`` may.

    An AST scan of ``BrokerEgressGateway.__call__``'s own source: if a future edit changed
    ``quantity=seal.outbound_quantity`` back to ``quantity=context.outbound_quantity`` (the
    pre-Phase-4-작업-6 shape), this test fails loudly instead of silently reverting the seal's
    "sole input source" guarantee.
    """
    import ast
    import textwrap

    source = textwrap.dedent(inspect.getsource(BrokerEgressGateway.__call__))
    tree = ast.parse(source)
    send_once_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "send_once"
    ]
    assert len(send_once_calls) == 1, "expected exactly one send_once call in __call__"
    (call_node,) = send_once_calls
    forbidden_context_attrs = {
        "outbound_quantity",
        "outbound_price",
        "outbound_side",
        "instrument_key",
    }
    offenders = [
        f"{kw.arg}=context.{kw.value.attr}"
        for kw in call_node.keywords
        if isinstance(kw.value, ast.Attribute)
        and isinstance(kw.value.value, ast.Name)
        and kw.value.value.id == "context"
        and kw.value.attr in forbidden_context_attrs
    ]
    assert offenders == [], (
        f"send_once reads {offenders} from context — step 18 must source only from the seal "
        "(design #34 phase 4 작업 6 §1.2, mutation M-K1)"
    )


# ---------------------------------------------------------------------------
# at-most-one: single-use consumption + no blind resubmit (§5.4 / §6)
# ---------------------------------------------------------------------------


def test_the_same_attempt_is_never_sent_twice() -> None:
    """(§6 / RFC-005 §12:362 item 6) A repeat of the same triple is refused, not resent."""
    attempt, context = happy_context()
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    assert gateway(attempt).accepted_for_transmission is True
    assert gateway(attempt).accepted_for_transmission is None
    assert len(transport.requests) == 1
    assert sink.records[-1].halt_reason is SendHaltReason.ATTEMPT_ALREADY_CONSUMED


def test_the_same_bindings_reproduce_the_same_attempt_identity() -> None:
    """(design #31 §4.3) Content addressing is what makes a "retry" collide with itself."""
    attempt_a, _ = happy_context()
    attempt_b, _ = happy_context()
    assert attempt_a.attempt_id == attempt_b.attempt_id


def test_a_second_gateway_sharing_the_ledger_also_refuses_the_replay() -> None:
    """(§6) The refusal lives in the ledger, not in one gateway instance's memory."""
    attempt, context = happy_context()
    ledger = SendAttemptLedger()
    first_transport = full_fill_transport()
    second_transport = full_fill_transport()
    first = BrokerEgressGateway(
        contexts={attempt.attempt_id: context},
        transport=first_transport,
        sink=RecordingGatewayEvidenceSink(),
        ledger=ledger,
    )
    second = BrokerEgressGateway(
        contexts={attempt.attempt_id: context},
        transport=second_transport,
        sink=RecordingGatewayEvidenceSink(),
        ledger=ledger,
    )
    assert first(attempt).accepted_for_transmission is True
    assert second(attempt).accepted_for_transmission is None
    assert len(first_transport.requests) == 1
    assert second_transport.requests == ()


def test_the_claim_consumes_both_nonces_exactly_once() -> None:
    """(ADR-002-013 §11.2 step 17) Capability and permit nonces are each claimed once."""
    attempt, context = happy_context()
    gateway, _ = build_gateway(attempt=attempt, context=context)
    gateway(attempt)
    nonces = [claim.nonce for claim in gateway.ledger.claims]
    assert sorted(nonces) == sorted(
        {context.capability_nonce, context.action_flow_permit_nonce}
    )


def test_a_ledger_claim_without_a_bound_principal_fails_closed() -> None:
    """(egress §5.6) A ``None`` principal or request digest can never be single-use-proven."""
    ledger = SendAttemptLedger()
    assert (
        ledger.claim(
            attempt_id="a-1",
            capability_nonce="n-1",
            action_flow_permit_nonce="n-2",
            principal=None,
            request_digest="rd",
        )
        is False
    )
    assert ledger.claims == ()


def test_a_raised_transport_leaves_the_attempt_consumed_and_resubmits_nothing() -> None:
    """(RFC-005 §11:322-323) A missing acknowledgement is never read as "not accepted"."""
    attempt, context = happy_context()
    transport = _RecordingRaisingTransport()
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.calls == 1
    assert sink.records[-1].halt_reason is SendHaltReason.TRANSPORT_RAISED
    assert gateway.ledger.attempt_consumed(attempt.attempt_id) is True
    # And the refusal is permanent: nothing retries it.
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.calls == 1


def test_a_result_naming_another_attempt_is_refused() -> None:
    """(design #31 §2.1(ii)) A late or reordered result never transitions someone else."""
    attempt, context = happy_context()
    transport = _WrongAttemptTransport()
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts={attempt.attempt_id: context}, transport=transport, sink=sink
    )
    assert gateway(attempt).accepted_for_transmission is None
    assert (
        sink.records[-1].halt_reason is SendHaltReason.RESULT_ATTEMPT_IDENTITY_MISMATCH
    )
    assert gateway.results == ()


# ---------------------------------------------------------------------------
# UNKNOWN / TIMEOUT and partial fills (§5.5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [EgressResultKind.UNKNOWN, EgressResultKind.TIMEOUT])
def test_an_uncertain_outcome_records_the_all_restrictive_ladder(
    kind: EgressResultKind,
) -> None:
    """(ADR-002-004 §12.4:640-646) No retry, no capacity release, no assumed rejection."""
    attempt, context = happy_context()
    gateway, sink = build_gateway(
        attempt=attempt, context=context, transport=_declared(kind)
    )
    assert gateway(attempt).accepted_for_transmission is True
    uncertain = sink.records[-1]
    assert uncertain.kind == "UNCERTAIN_SEND"
    detail = uncertain.detail or ""
    assert "no_retry=True" in detail
    assert "no_capacity_release=True" in detail
    assert "no_assume_rejection=True" in detail
    assert "start_reconciliation=True" in detail
    assert "same_order_retry_allowed=False" in detail


def test_a_definite_outcome_records_no_uncertain_ladder() -> None:
    """(both ways) The restrictive ladder is recorded for uncertainty, not for every send."""
    attempt, context = happy_context()
    gateway, sink = build_gateway(attempt=attempt, context=context)
    gateway(attempt)
    assert "UNCERTAIN_SEND" not in sink.kinds


def test_a_partial_fill_is_retained_as_a_partial_fill() -> None:
    """(RFC-005 §11:338-339) Partial stays partial; the filled part is never re-requested."""
    attempt, context = happy_context()
    half = SyntheticPaperTransport(
        SyntheticFillPolicy(fill_numerator=1, fill_denominator=2, lot_size=LOT_SIZE)
    )
    gateway, _ = build_gateway(attempt=attempt, context=context, transport=half)
    assert gateway(attempt).accepted_for_transmission is True
    (result,) = gateway.results
    assert result.kind is EgressResultKind.PARTIAL_FILL
    assert result.filled_quantity == Decimal("10")
    assert result.remaining_quantity == Decimal("10")


def test_a_rejection_is_recorded_without_a_fill_magnitude() -> None:
    """(design #31 §2.2) Only fill kinds carry magnitudes."""
    attempt, context = happy_context()
    gateway, _ = build_gateway(
        attempt=attempt, context=context, transport=_declared(EgressResultKind.REJECT)
    )
    gateway(attempt)
    (result,) = gateway.results
    assert result.kind is EgressResultKind.REJECT
    assert result.filled_quantity is None


# ---------------------------------------------------------------------------
# the verification record itself
# ---------------------------------------------------------------------------


def test_the_verification_is_retained_for_evidence_even_when_it_refuses() -> None:
    """(§4.2 "중단 사유 기록") The refused verification stays inspectable."""
    attempt, context = happy_context(commitment_epoch_current=None)
    gateway, _ = build_gateway(attempt=attempt, context=context)
    gateway(attempt)
    (verification,) = gateway.verifications
    assert verification.admitted is not True
    assert verification.halt_item is SendVerifyItem.CURRENT_COMMITMENT_EPOCH
    outcomes = {v.item: v.outcome for v in verification.verdicts}
    assert outcomes[SendVerifyItem.CURRENT_COMMITMENT_EPOCH] is VerifyOutcome.UNKNOWN
    assert len(verification.verdicts) == 17


def test_a_denied_construction_never_reaches_the_send_boundary() -> None:
    """(§3.1 ↔ §4.1 item 13) A denied derivation cannot produce an admitted send."""
    from ._egressgw_fixtures import admitted_price

    denied = construction(price=admitted_price(value=None))
    attempt, context = happy_context(construction=denied)
    transport = full_fill_transport()
    gateway, _ = build_gateway(attempt=attempt, context=context, transport=transport)
    assert gateway(attempt).accepted_for_transmission is None
    assert transport.requests == ()


# ---------------------------------------------------------------------------
# TOS-GAP-001 (item 13) — a None/UNKNOWN ioc verdict never crashes and never admits
# ---------------------------------------------------------------------------


def _built_construction() -> Any:
    """A real, fully-built CandidateConstruction produced by the actual construction sites."""
    built = construction()
    assert built.command is not None
    return built


@pytest.mark.parametrize(
    "field",
    ["conformance_result", "numerical_result"],
    ids=["conformance-unknown", "numerical-unknown"],
)
def test_a_native_unknown_ioc_verdict_is_unknown_never_a_pass(field: str) -> None:
    """(TOS-GAP-001 / ADR-002-020 §14:374) A native ``UNKNOWN`` ioc verdict on an otherwise
    complete command must stop the send at item 13 with ``VerifyOutcome.UNKNOWN`` and a
    ``SEND_REFUSED`` evidence record — never ``SATISFIED``, never an exception.

    ``UNKNOWN`` is a decided (non-``None``) :class:`~tos.ioc.ConformanceResult` member, so this
    bundle is still a *sanctioned* shape under the ``CandidateConstruction`` validator
    (``records.py``) — the validator only demands presence, not a particular decided value.
    """
    malformed = _built_construction().model_copy(
        update={field: ConformanceResult.UNKNOWN}
    )
    attempt, context = happy_context(construction=malformed)
    transport = full_fill_transport()
    gateway, sink = build_gateway(attempt=attempt, context=context, transport=transport)
    handoff = gateway(attempt)
    assert handoff.accepted_for_transmission is None
    assert transport.requests == ()
    (verification,) = gateway.verifications
    outcomes = {v.item: v.outcome for v in verification.verdicts}
    assert outcomes[SendVerifyItem.ORDER_CONSTRUCTION] is VerifyOutcome.UNKNOWN
    refusal = sink.records[-1]
    assert refusal.kind == "SEND_REFUSED"
    assert refusal.item is SendVerifyItem.ORDER_CONSTRUCTION
    assert refusal.halt_reason is SendHaltReason.VERIFY_ITEM_UNKNOWN
    assert (refusal.detail or "").strip(), "a restrictive stop must record its reason"


@pytest.mark.parametrize(
    "field",
    ["conformance_result", "numerical_result"],
    ids=["conformance-absent", "numerical-absent"],
)
def test_a_none_ioc_verdict_cannot_reach_the_send_boundary_context(field: str) -> None:
    """(TOS-GAP-001) The exact ``conformance_result=None`` shape that used to raise
    ``AttributeError`` inside item 13 cannot reach the gateway's ``__call__`` at all: pydantic
    re-validates a nested model instance when it is embedded into ``SendBoundaryContext``, so
    the ``CandidateConstruction`` shape validator (records.py) fires there and the malformed
    bundle is rejected one layer before the send boundary — even though ``model_copy`` bypassed
    that same validator when building the malformed bundle standalone. This is a stronger
    guarantee than the item-13 defense in depth exercised by the UNKNOWN case above: a ``None``
    ioc verdict on a bound command is structurally unconstructable in context, not merely
    handled gracefully once encountered.
    """
    malformed = _built_construction().model_copy(update={field: None})
    with pytest.raises(ValidationError, match="ioc verdict|missing"):
        happy_context(construction=malformed)


def _model_construct_malformed_construction(**overrides: Any) -> CandidateConstruction:
    """Bypass the ``records.py`` shape validator directly (repo idiom,
    ``tos/tests/wdr/test_wdr_malformed_model.py:85-97``): ``model_construct`` skips every
    validator, so this can build the exact ``command is not None`` + ``None`` ioc verdict shape
    the constructor and ``model_copy``-into-``SendBoundaryContext`` both refuse to let reach the
    send boundary (the two tests above)."""
    base = _built_construction()
    fields: dict[str, Any] = {
        "derivation": base.derivation,
        "intent": base.intent,
        "envelope": base.envelope,
        "policy": base.policy,
        "command": base.command,
        "conformance_result": base.conformance_result,
        "numerical_result": base.numerical_result,
        "no_silent_widening_ok": base.no_silent_widening_ok,
        "denial_reason": base.denial_reason,
        "authority_effect": base.authority_effect,
    }
    fields.update(overrides)
    return CandidateConstruction.model_construct(**fields)


@pytest.mark.parametrize(
    "overrides",
    [
        {"conformance_result": None},
        {"numerical_result": None, "conformance_result": ConformanceResult.CONFORMANT},
    ],
    ids=["conformance-none", "numerical-none"],
)
def test_check_construction_model_construct_bypass_none_verdict_is_unknown_not_a_crash(
    overrides: dict[str, Any],
) -> None:
    """(M1, TOS-GAP-001) The exact ``None`` ioc-verdict shape the constructor and
    ``model_copy``-into-context both make unreachable (the two tests above) is reverting either
    guard's live target: this calls ``_check_construction`` (gateway.py ~:941 / ~:971) directly
    against a ``model_construct``-bypassed bundle, so a reverted guard is caught here even though
    the malformed shape can never arrive through the public construction path. Regression for the
    independent reviewer's M1 finding on PR #655 — the prior suite proved the shape
    *unreachable*, never proved the guard itself live.
    """
    malformed = _model_construct_malformed_construction(**overrides)
    # ``SendBoundaryContext.model_construct`` likewise skips validation, so the malformed
    # ``construction`` survives embedding unchanged — ``_check_construction`` only reads
    # ``context.construction``; ``attempt``/``applicability`` are unused (``del``'d immediately).
    context = SendBoundaryContext.model_construct(construction=malformed)
    verdict = _check_construction(None, context, None)  # type: ignore[arg-type]
    assert verdict.outcome is VerifyOutcome.UNKNOWN
    assert verdict.native_verdict_value is None
    assert (verdict.reason or "").strip(), "a restrictive stop must record its reason"


# ---------------------------------------------------------------------------
# GAP-2 (design #35 §3) — the lazy context resolver beside the mapping
# ---------------------------------------------------------------------------


def test_the_mapping_and_the_resolver_paths_produce_the_identical_verification() -> (
    None
):
    """(design #35 §3.1/§3.2) The union is additive: the mapping path is unchanged.

    ``attempt_id`` is content-addressed at step 12, so a caller driven by an event loop cannot
    populate the mapping ahead of the run — hence the resolver. But the mapping path carries every
    committed call site in this suite, so the two must be the *same* boundary, not two boundaries.
    """
    attempt, context = happy_context()

    mapped_gateway, mapped_sink = build_gateway(attempt=attempt, context=context)
    mapped_handoff = mapped_gateway(attempt)

    resolved_gateway = BrokerEgressGateway(
        contexts=lambda _attempt: context,
        transport=full_fill_transport(),
        sink=RecordingGatewayEvidenceSink(),
    )
    resolved_handoff = resolved_gateway(attempt)

    assert mapped_handoff.accepted_for_transmission is True
    assert resolved_handoff == mapped_handoff
    (mapped_verification,) = mapped_gateway.verifications
    (resolved_verification,) = resolved_gateway.verifications
    assert resolved_verification == mapped_verification
    assert resolved_gateway.results == mapped_gateway.results
    assert mapped_sink.kinds == ("VERIFY_ITEM",) * 17 + (
        "SEND_SEALED",
        "SEND_STARTED",
        "POTENTIALLY_LIVE_OBSERVED",
        "EGRESS_RESULT_RECORDED",
    )


def test_the_resolver_is_asked_exactly_once_per_attempt_and_is_given_the_attempt() -> (
    None
):
    """(design #35 §3.3) One call per attempt, handed the live attempt — no re-entry, no loop."""
    attempt, context = happy_context()
    seen: list[AttemptRequest] = []

    def resolver(request: AttemptRequest) -> Any:
        seen.append(request)
        return context

    gateway = BrokerEgressGateway(
        contexts=resolver,
        transport=full_fill_transport(),
        sink=RecordingGatewayEvidenceSink(),
    )
    assert gateway(attempt).accepted_for_transmission is True
    assert seen == [attempt]
    assert seen[0] is attempt


def test_a_resolver_that_returns_none_is_the_same_recorded_context_missing_stop() -> (
    None
):
    """(design #35 §3.1 (1)) The lazy form of a missing entry is the same fail-closed stop."""
    attempt, _context = happy_context()
    transport = full_fill_transport()
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts=lambda _attempt: None, transport=transport, sink=sink
    )

    assert gateway(attempt).accepted_for_transmission is None
    assert transport.requests == ()
    assert gateway.results == ()
    (record,) = sink.records
    assert record.kind == "SEND_REFUSED"
    assert record.halt_reason is SendHaltReason.CONTEXT_MISSING
    assert record.detail is not None
    assert "no send-boundary context is bound" in record.detail


def test_a_contexts_argument_that_is_neither_shape_admits_nothing() -> None:
    """(design #35 §3.1) Both admitted shapes are positive membership — the rest is a stop.

    Recognising the mapping and the callable by what they *are*, rather than the callable by
    elimination, means an unrecognised ``contexts`` argument can only deny. There is no branch in
    which it falls through to an admitted send.
    """
    attempt, _context = happy_context()
    transport = full_fill_transport()
    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts="not a mapping and not callable",  # type: ignore[arg-type]
        transport=transport,
        sink=sink,
    )

    assert gateway(attempt).accepted_for_transmission is None
    assert transport.requests == ()
    (record,) = sink.records
    assert record.halt_reason is SendHaltReason.CONTEXT_MISSING
    assert record.detail is not None
    assert "no send-boundary context is bound" in record.detail


def test_the_shipped_factory_derives_the_flow_bound_fields_and_never_takes_them() -> (
    None
):
    """(design #35 §3.1 (2)) The factory's derived fields cannot be supplied by a caller.

    That is what keeps verify item 2 (reservation identity match) and item 13 (order construction)
    load-bearing instead of self-confirming: there is no parameter through which a look-alike
    identity, a substituted construction, or a hand-written outbound magnitude could enter.
    """
    parameters = inspect.signature(send_boundary_context).parameters
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )
    for derived in (
        "reservation_attempt_id",
        "reservation_conformance_proof_digest",
        "reservation_action_flow_permit_identity",
        "approval_intent_binding_digest",
        "egress_request",
        "quorum_commit_certificate",
        "outbound_quantity",
        "outbound_price",
    ):
        assert derived not in parameters, f"{derived} must be derived, not injected"

    built = construction()
    assert built.command is not None
    proof = build_order_conformance_proof(
        construction=built,
        scheme=SCHEME,
        proof_id="ocp-proof-factory",
        proof_generation=1,
        required_authority_scope=("scope-1",),
    )
    assert proof is not None
    attempt = attempt_request(proof_digest=proof.canonical_digest or "")
    context = send_boundary_context(
        attempt=attempt,
        construction=built,
        conformance_proof=proof,
        reference=ordering(),
        egress_request_for_command=egress_request,
        quorum_certificate_for_command=quorum_certificate,
    )
    assert context.reservation_attempt_id == attempt.attempt_id
    assert (
        context.reservation_conformance_proof_digest == attempt.conformance_proof_digest
    )
    assert (
        context.reservation_action_flow_permit_identity
        == attempt.action_flow_permit_identity
    )
    assert context.construction is built
    assert context.outbound_quantity == built.derivation.quantity
    assert context.outbound_price == built.derivation.price
    assert context.egress_request is not None
    assert (
        context.egress_request.canonical_command_digest
        == built.command.canonical_digest
    )
    assert context.quorum_commit_certificate is not None
    assert (
        context.quorum_commit_certificate.canonical_command_digest
        == built.command.canonical_digest
    )
    assert built.intent is not None
    assert context.approval_intent_binding_digest == built.intent.canonical_digest


def test_the_factory_binds_no_item_17_artifact_when_no_command_was_constructed() -> (
    None
):
    """(design #35 §3.1 (2), ∅ both ways) No command ⇒ no digest ⇒ nothing built against one.

    Building the outbound artifacts against a ``None`` digest would manufacture a "bound" record
    that binds nothing; leaving them absent is the recorded stop RFC-002 §10.8:761 requires.
    """
    from ._egressgw_fixtures import admitted_price

    denied = construction(price=admitted_price(value=None))
    assert denied.command is None
    context = send_boundary_context(
        attempt=attempt_request(proof_digest="proof-digest-absent-command"),
        construction=denied,
        conformance_proof=None,
        reference=ordering(),
        egress_request_for_command=egress_request,
        quorum_certificate_for_command=quorum_certificate,
    )
    assert context.egress_request is None
    assert context.quorum_commit_certificate is None
    assert context.approval_intent_binding_digest is None
    assert context.outbound_quantity is None
    assert context.outbound_price is None
