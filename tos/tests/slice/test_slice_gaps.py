"""The four seams slice #1 had to bridge by hand — now shipped, and measured as such."""

from __future__ import annotations

import inspect
from decimal import Decimal

import tos.backtest as backtest_package
import tos.brokeradapter as brokeradapter_package
import tos.egressgw as egressgw_package
from tos.backtest import (
    BacktestDriver,
    DeterministicFillModel,
    EgressResultSource,
    FillMode,
    FillParameters,
    FillSide,
    RetainedEgressResults,
)
from tos.dsl import FLAT_QUANTITY_BASIS, ContextValueView
from tos.egressgw import (
    AdmittedPriceObservation,
    BrokerEgressGateway,
    DerivationOutcome,
    RecordingGatewayEvidenceSink,
    SendBoundaryContext,
    SendHaltReason,
    admitted_price_from_view,
    derive_order_size,
)
from tos.engine import EgressResultPayload, InstrumentKey, StageRequest
from tos.rcl import CapacityState

from ._slice_fixtures import (
    CROSSING_BAR_INDEX,
    PRICE_FIELD_KEY,
    BandBarBook,
    admitted_price,
    build_resolver,
    instrument_key,
    proposed_envelope,
    run_slice,
    sizing_bound,
    venue_quantity_constraint,
)

HELD_POSITION = Decimal("40")


def _crossing_value_view() -> ContextValueView:
    """The live value view D-E2 published for the band-crossing bar."""
    book = BandBarBook()
    resolved = build_resolver(book).resolve(
        book.context_for(CROSSING_BAR_INDEX).capsule, instrument_key=instrument_key()
    )
    view = resolved.payload.value_view
    assert view is not None
    return view


def test_gap_1_a_shipped_port_re_injects_a_gateway_result_into_the_backtest_driver() -> (
    None
):
    """GAP-1 closed (owner: D-E3 ``tos.backtest``, consuming a D-E4 shape) — design #35 §7-1."""
    parameters = inspect.signature(BacktestDriver.__init__).parameters
    assert "fill_model" in parameters
    assert "EgressResultSource" in str(parameters["fill_model"].annotation)

    assert "EgressResultSource" in backtest_package.__all__
    assert "GatewayResultReinjector" in backtest_package.__all__
    assert [
        name
        for name in (*backtest_package.__all__, *egressgw_package.__all__)
        if any(token in name.lower() for token in ("reinject", "resultsource"))
    ] == ["EgressResultSource", "GatewayResultReinjector"]

    fill_model = DeterministicFillModel(
        instrument_key=InstrumentKey(account="acct-port", instrument="ES"),
        parameters=FillParameters(mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY),
    )
    sliced = run_slice()
    assert isinstance(fill_model, EgressResultSource)
    assert isinstance(sliced.reinjector, EgressResultSource)

    for method in ("bind_settlement_context", "settle_due", "unsettled_records"):
        assert hasattr(DeterministicFillModel, method)
        assert not hasattr(BrokerEgressGateway, method)

    driver_source = inspect.getsource(backtest_package.driver)
    fills_source = inspect.getsource(backtest_package.fills)
    gateway_source = inspect.getsource(egressgw_package.gateway)
    assert "egressgw" not in driver_source
    assert "brokeradapter" not in driver_source
    assert "egressgw" not in fills_source
    assert "brokeradapter" not in fills_source
    assert "backtest" not in gateway_source


def test_gap_1_the_shipped_reinjector_adds_no_judgement_of_its_own() -> None:
    """Design #35 §7-2: the adapter is wiring, so every verdict still comes from a package."""
    sliced = run_slice()

    assert sliced.reinjector.settle_due(sliced.book.context_for(0).bar) == ()
    assert sliced.reinjector.drained == 1

    assert len(sliced.gateway.results) == 1
    (egress_entry,) = [
        entry
        for entry in sliced.run.trace.entries
        if entry.event_kind.value == "EGRESS_RESULT"
    ]
    assert egress_entry.attempt_id == sliced.gateway.results[0].attempt_id
    assert egress_entry.egress_result_kind is sliced.gateway.results[0].kind

    assert sliced.reinjector.records == ()
    assert sliced.reinjector.unsettled_records() == ()
    assert sliced.run.fill_records == ()
    assert sliced.run.unsettled_fill_records == ()


def test_gap_1_the_local_retained_results_port_has_not_drifted_from_the_gateway() -> (
    None
):
    """The Transport-precedent drift canary (design #35 §2.1 (3) / §9-2)."""
    members = {name for name in vars(RetainedEgressResults) if not name.startswith("_")}
    assert members == {"results"}

    sliced = run_slice()
    assert isinstance(sliced.gateway, RetainedEgressResults)

    declared = inspect.signature(RetainedEgressResults.results.fget).return_annotation  # type: ignore[attr-defined]
    assert str(declared) == "tuple[EgressResultPayload, ...]"
    assert isinstance(sliced.gateway.results, tuple)
    assert all(
        isinstance(payload, EgressResultPayload) for payload in sliced.gateway.results
    )


def test_gap_2_a_shipped_factory_binds_a_send_boundary_context_to_a_live_attempt() -> (
    None
):
    """GAP-2 closed (owner: D-E4 ``tos.egressgw``) — design #35 §7-3."""
    contexts_parameter = inspect.signature(BrokerEgressGateway.__init__).parameters[
        "contexts"
    ]
    annotation = str(contexts_parameter.annotation)
    assert "Mapping" in annotation
    assert "Callable" in annotation

    assert "send_boundary_context" in egressgw_package.__all__
    assert [
        name
        for name in egressgw_package.__all__
        if name != "SendBoundaryContext" and "send_boundary_context" in name.lower()
    ] == ["send_boundary_context"]

    sliced = run_slice()
    (attempt,) = sliced.resolver.attempts
    assert attempt.attempt_id.startswith("attempt-")
    assert attempt.reference_coordinate_digest
    (bound,) = sliced.resolver.contexts
    assert bound.reservation_attempt_id == attempt.attempt_id
    assert (
        bound.reservation_conformance_proof_digest == attempt.conformance_proof_digest
    )
    assert (
        bound.reservation_action_flow_permit_identity
        == attempt.action_flow_permit_identity
    )
    assert bound.construction is not None and bound.construction.command is not None
    command_digest = bound.construction.command.canonical_digest
    assert bound.egress_request is not None
    assert bound.egress_request.canonical_command_digest == command_digest
    assert bound.quorum_commit_certificate is not None
    assert bound.quorum_commit_certificate.canonical_command_digest == command_digest


def test_gap_2_a_resolver_that_resolves_nothing_stays_the_same_recorded_stop() -> None:
    """Design #35 §7-3 (d): the negative path is preserved exactly, not softened."""
    sliced = run_slice()
    (attempt,) = sliced.resolver.attempts

    sink = RecordingGatewayEvidenceSink()
    gateway = BrokerEgressGateway(
        contexts=lambda _attempt: None, transport=sliced.transport, sink=sink
    )
    handoff = gateway(attempt)

    assert handoff.accepted_for_transmission is None
    assert gateway.results == ()
    (record,) = sink.records
    assert record.kind == "SEND_REFUSED"
    assert record.halt_reason is SendHaltReason.CONTEXT_MISSING
    assert record.detail is not None
    assert "no send-boundary context is bound" in record.detail


def test_gap_3_the_construction_price_is_value_sourced_and_digest_tied() -> None:
    """GAP-3 closed (owner: D-E4 ``tos.egressgw``, consuming a D-E2 shape) — design #35 §7-4."""
    assert list(AdmittedPriceObservation.model_fields) == [
        "source",
        "value",
        "snapshot_digest",
        "value_payload_digest",
    ]

    assert ContextValueView.__name__ in inspect.getsource(egressgw_package.construction)
    assert "value_view" in StageRequest.model_fields
    assert "value_view" not in SendBoundaryContext.model_fields
    assert "marketfeed" not in inspect.getsource(egressgw_package.construction)
    assert "marketfeed" not in inspect.getsource(brokeradapter_package.synthetic)

    sliced = run_slice()
    (bound,) = sliced.resolver.contexts
    crossing_close = sliced.book.context_for(CROSSING_BAR_INDEX).close

    assert bound.outbound_price == Decimal(crossing_close)
    assert bound.construction is not None
    assert bound.construction.derivation.price == Decimal(crossing_close)

    view = _crossing_value_view()
    projected = admitted_price_from_view(view, field_key=PRICE_FIELD_KEY)
    (close_value,) = [
        value for value in view.values if value.field_key == PRICE_FIELD_KEY
    ]
    assert projected.value == Decimal(crossing_close)
    assert projected.value == bound.outbound_price
    assert projected.value_payload_digest == close_value.payload_digest
    assert projected.snapshot_digest == view.snapshot_canonical_digest


def test_gap_3_a_value_the_view_does_not_carry_is_a_no_send() -> None:
    """Design #35 §4.2 / §9-4: the projection is fail-closed, and ∅ is recorded both ways."""
    view = _crossing_value_view()
    constraint = venue_quantity_constraint()
    envelope = proposed_envelope()

    missing = admitted_price_from_view(view, field_key="not_a_published_field")
    assert missing.value is None
    assert missing.value_payload_digest is None
    assert missing.snapshot_digest == view.snapshot_canonical_digest
    denied = derive_order_size(
        quantity_basis="RISK",
        envelope=envelope,
        price=missing,
        venue_constraint=constraint,
    )
    assert denied.outcome is DerivationOutcome.DENIED

    empty = view.model_copy(update={"values": ()})
    nothing = admitted_price_from_view(empty, field_key=PRICE_FIELD_KEY)
    assert nothing.source is None
    assert nothing.snapshot_digest is None
    assert nothing.value is None
    empty_denied = derive_order_size(
        quantity_basis="RISK",
        envelope=envelope,
        price=nothing,
        venue_constraint=constraint,
    )
    assert empty_denied.outcome is DerivationOutcome.DENIED
    assert empty_denied.denial_reason != denied.denial_reason


def test_gap_4_the_explicit_flat_basis_derives_a_position_closing_size() -> None:
    """GAP-4 closed (owner: D-E4 ``tos.egressgw``) — design #35 §7-5."""
    book = BandBarBook()
    price = admitted_price(book)
    constraint = venue_quantity_constraint()
    envelope = proposed_envelope()

    unknown_position = derive_order_size(
        quantity_basis=FLAT_QUANTITY_BASIS,
        envelope=envelope,
        price=price,
        venue_constraint=constraint,
    )
    assert unknown_position.outcome is DerivationOutcome.DENIED
    assert unknown_position.quantity is None
    assert unknown_position.denial_reason is not None
    assert "no held position" in unknown_position.denial_reason

    zero_position = derive_order_size(
        quantity_basis=FLAT_QUANTITY_BASIS,
        envelope=envelope,
        price=price,
        venue_constraint=constraint,
        held_position=Decimal("0"),
    )
    assert zero_position.outcome is DerivationOutcome.DENIED
    assert zero_position.denial_reason != unknown_position.denial_reason
    assert zero_position.denial_reason is not None
    assert "nothing to close" in zero_position.denial_reason

    flat_size = derive_order_size(
        quantity_basis=FLAT_QUANTITY_BASIS,
        envelope=envelope,
        price=price,
        venue_constraint=constraint,
        held_position=HELD_POSITION,
    )
    entry_size = derive_order_size(
        quantity_basis="RISK",
        envelope=envelope,
        price=price,
        venue_constraint=constraint,
    )
    assert flat_size.outcome is DerivationOutcome.DERIVED
    assert entry_size.outcome is DerivationOutcome.DERIVED
    assert flat_size.quantity == HELD_POSITION

    assert flat_size.quantity != entry_size.quantity

    mutated = proposed_envelope(
        sizing_bound=sizing_bound(
            risk_budget=Decimal("3000"), per_unit_risk=Decimal("30")
        )
    )
    mutated_flat = derive_order_size(
        quantity_basis=FLAT_QUANTITY_BASIS,
        envelope=mutated,
        price=price,
        venue_constraint=constraint,
        held_position=HELD_POSITION,
    )
    mutated_entry = derive_order_size(
        quantity_basis="RISK",
        envelope=mutated,
        price=price,
        venue_constraint=constraint,
    )
    assert mutated_flat.quantity == flat_size.quantity == HELD_POSITION
    assert mutated_entry.quantity != entry_size.quantity


def test_gap_4_a_pure_close_policy_sizes_without_any_risk_budget() -> None:
    """Design #35 §7-5 (e) / §5.2 MINOR-2: the presence guard does not latently deny a flat."""
    book = BandBarBook()
    budget_free = proposed_envelope(
        sizing_bound=sizing_bound(risk_budget=None, per_unit_risk=None)
    )
    flat_size = derive_order_size(
        quantity_basis=FLAT_QUANTITY_BASIS,
        envelope=budget_free,
        price=admitted_price(book),
        venue_constraint=venue_quantity_constraint(),
        held_position=HELD_POSITION,
    )
    assert flat_size.outcome is DerivationOutcome.DERIVED
    assert flat_size.quantity == HELD_POSITION
    assert flat_size.rule is not None
    assert "risk_budget" not in flat_size.rule

    entry = derive_order_size(
        quantity_basis="RISK",
        envelope=budget_free,
        price=admitted_price(book),
        venue_constraint=venue_quantity_constraint(),
    )
    assert entry.outcome is DerivationOutcome.DENIED
    assert entry.denial_reason is not None
    assert "risk budget" in entry.denial_reason


def test_gap_4_the_scope_stays_occupied_through_the_ordinary_result_path() -> None:
    """The companion fact: no release path was invented for GAP-4 itself."""
    sliced = run_slice()
    ledger = sliced.core.ledger
    assert hasattr(ledger, "release")
    for method in ("free", "clear", "reset"):
        assert not hasattr(ledger, method), f"the projection gained a {method} path"
    outstanding = ledger.outstanding(sliced.run.instrument_key)
    assert outstanding is not None
    assert ledger.admits_new_exposure(sliced.run.instrument_key) is False
    assert outstanding.capacity_state is not CapacityState.RELEASED, (
        "GAP-4's own flat-sizing round trip must never itself reach RELEASED — only the "
        "separate, token-gated release() may"
    )
