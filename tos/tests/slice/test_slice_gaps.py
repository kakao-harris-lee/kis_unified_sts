"""The four seams slice #1 had to bridge by hand — now shipped, and measured as such.

Wiring the four lanes together end to end surfaced four places where no shipped package owned
the joint. Those gaps were recorded here as **executable observations** rather than as prose,
for two reasons: a gap stated in prose rots the moment someone closes it, and the #27
anti-phantom lesson is that a claim of absence must be grepped exactly like a claim of presence.

Design #35 closes all four. Each test below therefore now asserts the *closure* the design
contracts (§7), on exactly the surface that previously demonstrated the gap:

* **GAP-1** — ``tos.backtest.EgressResultSource`` is the driver's declared re-injection port and
  ``GatewayResultReinjector`` presents a send boundary's retained results on it;
* **GAP-2** — the gateway accepts a lazy ``(AttemptRequest) -> SendBoundaryContext | None``
  resolver alongside the mapping, and ``tos.egressgw.send_boundary_context`` is the shipped
  factory it partially applies;
* **GAP-3** — ``admitted_price_from_view`` projects the admitted value surface onto the price the
  order is sized against, carrying that value's own ``payload_digest``;
* **GAP-4** — an Explicit Flat derives its magnitude from the observed held position.

The one thing design #35 deliberately did **not** close is still asserted as an absence:
:func:`test_gap_4_the_scope_stays_occupied_because_there_is_no_release_path`. Its staying green
is the executable evidence that GAP-4 sized a flat without inventing an RCL release path.

⚠ Authoring evidence; closes no EV.
"""

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

#: A held position deliberately **different** from the entry size (risk_budget / per_unit_risk =
#: 1000 / 50 = 20), so "the flat is sized from the position" cannot be confused with "the flat is
#: sized from the risk budget and happens to agree".
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


# ---------------------------------------------------------------------------
# GAP-1 — a shipped port joins the gateway's retained results to the driver
# ---------------------------------------------------------------------------


def test_gap_1_a_shipped_port_re_injects_a_gateway_result_into_the_backtest_driver() -> None:
    """GAP-1 closed (owner: D-E3 ``tos.backtest``, consuming a D-E4 shape) — design #35 §7-1.

    ``BacktestDriver`` no longer names a concrete fill model in its constructor: it is typed
    against :class:`~tos.backtest.EgressResultSource`, the five-member surface it actually drains
    (``driver.py:225/233/309/310/311``). ``DeterministicFillModel`` and the shipped
    :class:`~tos.backtest.GatewayResultReinjector` both satisfy it structurally — the same
    "declared once, satisfied structurally" shape the two ``Transport`` Protocols already use.
    """
    parameters = inspect.signature(BacktestDriver.__init__).parameters
    assert "fill_model" in parameters
    assert "EgressResultSource" in str(parameters["fill_model"].annotation)

    assert "EgressResultSource" in backtest_package.__all__
    assert "GatewayResultReinjector" in backtest_package.__all__
    # the token convention the gap register named as the closure signal
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

    # …and the gateway still exposes none of the driver's fill-model vocabulary: the joint is the
    # adapter, not a `Bar`-aware method grafted onto D-E4 (design #35 §2.2 (A)).
    for method in ("bind_settlement_context", "settle_due", "unsettled_records"):
        assert hasattr(DeterministicFillModel, method)
        assert not hasattr(BrokerEgressGateway, method)

    # anti-phantom: the closure is structural, so neither package names the other.
    driver_source = inspect.getsource(backtest_package.driver)
    fills_source = inspect.getsource(backtest_package.fills)
    gateway_source = inspect.getsource(egressgw_package.gateway)
    assert "egressgw" not in driver_source
    assert "brokeradapter" not in driver_source
    assert "egressgw" not in fills_source
    assert "brokeradapter" not in fills_source
    assert "backtest" not in gateway_source


def test_gap_1_the_shipped_reinjector_adds_no_judgement_of_its_own() -> None:
    """Design #35 §7-2: the adapter is wiring, so every verdict still comes from a package.

    Forwarding is **identity**, not reconstruction: the payload the driver re-injected is the
    very object the gateway retained, so the adapter cannot have edited, re-derived, or added to
    it. And it owns no D-E3-local fill record, because the price / cost model belongs to the fill
    band.
    """
    sliced = run_slice()

    # the run drained everything; a second drain invents nothing for a bar that produced none.
    assert sliced.reinjector.settle_due(sliced.book.context_for(0).bar) == ()
    assert sliced.reinjector.drained == 1

    assert len(sliced.gateway.results) == 1
    (egress_entry,) = [
        entry for entry in sliced.run.trace.entries if entry.event_kind.value == "EGRESS_RESULT"
    ]
    assert egress_entry.attempt_id == sliced.gateway.results[0].attempt_id
    assert egress_entry.egress_result_kind is sliced.gateway.results[0].kind

    # …and it holds no D-E3-local fill record, because the price/cost model is the fill band's.
    assert sliced.reinjector.records == ()
    assert sliced.reinjector.unsettled_records() == ()
    assert sliced.run.fill_records == ()
    assert sliced.run.unsettled_fill_records == ()


def test_gap_1_the_local_retained_results_port_has_not_drifted_from_the_gateway() -> None:
    """The Transport-precedent drift canary (design #35 §2.1 (3) / §9-2).

    ``tos.backtest`` may not name ``BrokerEgressGateway`` — the two packages exclude each other
    from their closures — so :class:`~tos.backtest.RetainedEgressResults` declares the one member
    it consumes and the gateway satisfies it structurally. A declaration that drifted from the
    real surface would fail open silently, so the two are compared here, where both are importable.
    """
    members = {
        name
        for name in vars(RetainedEgressResults)
        if not name.startswith("_")
    }
    assert members == {"results"}

    sliced = run_slice()
    assert isinstance(sliced.gateway, RetainedEgressResults)

    declared = inspect.signature(RetainedEgressResults.results.fget).return_annotation  # type: ignore[union-attr]
    assert str(declared) == "tuple[EgressResultPayload, ...]"
    # …and the live surface really is that shape.
    assert isinstance(sliced.gateway.results, tuple)
    assert all(
        isinstance(payload, EgressResultPayload) for payload in sliced.gateway.results
    )


# ---------------------------------------------------------------------------
# GAP-2 — a shipped factory binds the send-boundary context to a live attempt
# ---------------------------------------------------------------------------


def test_gap_2_a_shipped_factory_binds_a_send_boundary_context_to_a_live_attempt() -> None:
    """GAP-2 closed (owner: D-E4 ``tos.egressgw``) — design #35 §7-3.

    ``attempt_id`` is content-addressed at step 12 from (proof digest, permit identity,
    reference-coordinate digest), and under D-E3 the reference coordinate is the driver's global
    yield-order counter — decoupled from ``bar_index`` on purpose. So the gateway now accepts a
    **lazy resolver** beside the mapping, and ``send_boundary_context`` is the shipped factory
    that assembles the context from the attempt the sequencer just handed over.
    """
    contexts_parameter = inspect.signature(BrokerEgressGateway.__init__).parameters["contexts"]
    annotation = str(contexts_parameter.annotation)
    # the mapping path is preserved — this is a union, not a replacement (design #35 §3.2).
    assert "Mapping" in annotation
    assert "Callable" in annotation

    assert "send_boundary_context" in egressgw_package.__all__
    assert [
        name
        for name in egressgw_package.__all__
        if name != "SendBoundaryContext" and "send_boundary_context" in name.lower()
    ] == ["send_boundary_context"]

    # the identity really is only knowable after step 12 — and the resolver binds to it anyway.
    sliced = run_slice()
    (attempt,) = sliced.resolver.attempts
    assert attempt.attempt_id.startswith("attempt-")
    assert attempt.reference_coordinate_digest
    (bound,) = sliced.resolver.contexts
    assert bound.reservation_attempt_id == attempt.attempt_id
    assert bound.reservation_conformance_proof_digest == attempt.conformance_proof_digest
    assert (
        bound.reservation_action_flow_permit_identity == attempt.action_flow_permit_identity
    )
    # …and the item-17 artifacts the factory derived are bound to *this* command's digest.
    assert bound.construction is not None and bound.construction.command is not None
    command_digest = bound.construction.command.canonical_digest
    assert bound.egress_request is not None
    assert bound.egress_request.canonical_command_digest == command_digest
    assert bound.quorum_commit_certificate is not None
    assert bound.quorum_commit_certificate.canonical_command_digest == command_digest


def test_gap_2_a_resolver_that_resolves_nothing_stays_the_same_recorded_stop() -> None:
    """Design #35 §7-3 (d): the negative path is preserved exactly, not softened.

    A resolver returning ``None`` is the lazy form of a missing mapping entry, and it produces the
    identical ``CONTEXT_MISSING`` refusal — a missing required fact is a rejection
    (RFC-002 §10.8:761), never a skip.
    """
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
    # ★ …and it names the fact that is actually missing. Substituting a blank context for an
    #   absent one would deny too, on a *different* missing fact — the evidence would misreport
    #   which one, which is the fail-open the recorded reason exists to prevent.
    assert record.detail is not None
    assert "no send-boundary context is bound" in record.detail


# ---------------------------------------------------------------------------
# GAP-3 — Order Construction's price is read off the admitted value surface
# ---------------------------------------------------------------------------


def test_gap_3_the_construction_price_is_value_sourced_and_digest_tied() -> None:
    """GAP-3 closed (owner: D-E4 ``tos.egressgw``, consuming a D-E2 shape) — design #35 §7-4.

    Slice #1 measured the defect precisely: the strategy decided on the crossing bar's close
    (4,499,000, read off the admitted value surface) while the order was sized against an injected
    scalar (4,200), and the only tie between them was a ``snapshot_digest`` string the caller
    supplied. Both halves of that are now closed — **the number the strategy decided on and the
    number the order was sized against are the same number, tied by a digest.**
    """
    assert list(AdmittedPriceObservation.model_fields) == [
        "source",
        "value",
        "snapshot_digest",
        "value_payload_digest",
    ]

    # the D-E2 carrier type is now named by D-E4's construction module — the §0.3 edge.
    assert ContextValueView.__name__ in inspect.getsource(egressgw_package.construction)
    # …and it travels on the engine's stage request, not on the send-boundary context.
    assert "value_view" in StageRequest.model_fields
    assert "value_view" not in SendBoundaryContext.model_fields
    # the value surface is D-E2's, reached through the dsl carrier type — never by importing it.
    assert "marketfeed" not in inspect.getsource(egressgw_package.construction)
    assert "marketfeed" not in inspect.getsource(brokeradapter_package.synthetic)

    sliced = run_slice()
    (bound,) = sliced.resolver.contexts
    crossing_close = sliced.book.context_for(CROSSING_BAR_INDEX).close

    # ★ the decided-on number *is* the sized-against number.
    assert bound.outbound_price == Decimal(crossing_close)
    assert bound.construction is not None
    assert bound.construction.derivation.price == Decimal(crossing_close)

    # ★ …and the tie is the value's own per-value provenance digest, not a caller's promise.
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
    # the view *did* resolve, so the lineage it does have is recorded honestly…
    assert missing.snapshot_digest == view.snapshot_canonical_digest
    denied = derive_order_size(
        quantity_basis="RISK", envelope=envelope, price=missing, venue_constraint=constraint
    )
    assert denied.outcome is DerivationOutcome.DENIED

    # …whereas an explicit-empty view admitted nothing at all — a different recorded fact.
    empty = view.model_copy(update={"values": ()})
    nothing = admitted_price_from_view(empty, field_key=PRICE_FIELD_KEY)
    assert nothing.source is None
    assert nothing.snapshot_digest is None
    assert nothing.value is None
    empty_denied = derive_order_size(
        quantity_basis="RISK", envelope=envelope, price=nothing, venue_constraint=constraint
    )
    assert empty_denied.outcome is DerivationOutcome.DENIED
    assert empty_denied.denial_reason != denied.denial_reason


# ---------------------------------------------------------------------------
# GAP-4 — the Explicit-Flat exit has an Order Construction path
# ---------------------------------------------------------------------------


def test_gap_4_the_explicit_flat_basis_derives_a_position_closing_size() -> None:
    """GAP-4 closed (owner: D-E4 ``tos.egressgw``) — design #35 §7-5.

    A dsl Explicit Flat carries ``quantity_basis == FLAT_QUANTITY_BASIS`` ("ZERO_POSITION",
    ``proposal.py:49``) by construction. ``derive_order_size`` now renders that basis from the
    **observed held position** rather than from a risk budget, so the exit half of a
    band-reversion strategy is constructable at the send boundary.

    What GAP-4 does **not** do is admit capacity: the flat still stops. It stops at the capacity
    seal (step 8) instead of the sizing rule (step 2), and the two are not the same fact
    (design #35 §5.3 — asserted end to end in ``test_slice_end_to_end.py``).
    """
    book = BandBarBook()
    price = admitted_price(book)
    constraint = venue_quantity_constraint()
    envelope = proposed_envelope()

    # (a) no held position observed → denial, and the reason names the missing fact.
    unknown_position = derive_order_size(
        quantity_basis=FLAT_QUANTITY_BASIS,
        envelope=envelope,
        price=price,
        venue_constraint=constraint,
    )
    assert unknown_position.outcome is DerivationOutcome.DENIED
    assert unknown_position.quantity is None
    assert unknown_position.denial_reason is not None
    # ★ the recorded reason names the *absence itself*, not merely the subject. Falling through
    #   to the "nothing to close" branch would deny too — with a reason that misreports an
    #   unobserved position as an observed empty one.
    assert "no held position" in unknown_position.denial_reason

    # …and an explicit zero is a *different* recorded fact from an absent observation (∅ both ways).
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

    # (b) a held position → a position-closing size equal to it.
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

    # (c) structurally derived, not a relabelled entry: the two sizes differ.
    assert flat_size.quantity != entry_size.quantity

    # (d) the sizing SOURCE really is the held position — mutating the risk budget and the
    #     per-unit risk moves the entry size and leaves the flat size exactly where it was.
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
    """Design #35 §7-5 (e) / §5.2 MINOR-2: the presence guard does not latently deny a flat.

    The risk-budget / per-unit-risk presence checks are the inputs of a rule a flat never runs.
    Demanding them anyway would deny a pure-close policy for lacking a number it does not use —
    a latent denial dressed as a safety property. This is the canary that keeps it moved.
    """
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

    # …while the same budget-free bound still denies every other basis, which is the point: the
    # guard was not deleted, it was moved to the branch that consumes it.
    entry = derive_order_size(
        quantity_basis="RISK",
        envelope=budget_free,
        price=admitted_price(book),
        venue_constraint=venue_quantity_constraint(),
    )
    assert entry.outcome is DerivationOutcome.DENIED
    assert entry.denial_reason is not None
    assert "risk budget" in entry.denial_reason


def test_gap_4_the_scope_stays_occupied_because_there_is_no_release_path() -> None:
    """The companion fact, deliberately unchanged: no release path was invented for GAP-4.

    ``ProvisionalReservationLedger`` exposes no ``release`` / ``free`` / ``clear`` method at all
    (state.py:22) and ``RELEASED`` is absent from its projection order, so the round trip waits
    for the real RCL (RFC-002 §9.1:557) regardless of GAP-4. **This test staying green is the
    executable evidence of GAP-4's boundary**: a flat is now sized from an observation of the
    projection, and the projection is still read-only (design #35 §5.3).
    """
    sliced = run_slice()
    ledger = sliced.core.ledger
    for method in ("release", "free", "clear", "reset"):
        assert not hasattr(ledger, method), f"the projection gained a {method} path"
    outstanding = ledger.outstanding(sliced.run.instrument_key)
    assert outstanding is not None
    assert ledger.admits_new_exposure(sliced.run.instrument_key) is False
