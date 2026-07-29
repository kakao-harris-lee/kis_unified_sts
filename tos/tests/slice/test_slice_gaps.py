"""The seams slice #1 had to bridge by hand — measured, not asserted in prose.

Wiring the four lanes together end to end surfaced four places where no shipped package owns
the joint. This file **records each one as an executable observation** rather than as a comment,
for two reasons: a gap stated in prose rots the moment someone closes it, and the #27
anti-phantom lesson is that a claim of absence must be grepped exactly like a claim of presence.

Each test below therefore (a) demonstrates the gap against the shipped code and (b) names the
lane that should own the fix. If a lane closes one of these, the corresponding test fails —
loudly, and with the reason attached. **That is the intended failure mode.**

None of these is a defect *inside* a lane: each lane is internally coherent and each honestly
declares the seam as a forward one. What is missing is the joint.

⚠ Authoring evidence; closes no EV.
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import tos.backtest as backtest_package
import tos.brokeradapter as brokeradapter_package
import tos.egressgw as egressgw_package
from tos.backtest import BacktestDriver, DeterministicFillModel
from tos.dsl import FLAT_QUANTITY_BASIS, ContextValueView
from tos.egressgw import (
    AdmittedPriceObservation,
    BrokerEgressGateway,
    DerivationOutcome,
    SendBoundaryContext,
    derive_order_size,
)

from ._slice_fixtures import (
    BandBarBook,
    admitted_price,
    proposed_envelope,
    run_slice,
    sizing_bound,
    venue_quantity_constraint,
)

# ---------------------------------------------------------------------------
# GAP-1 — nothing joins the gateway's retained results to the driver's re-injection
# ---------------------------------------------------------------------------


def test_gap_1_no_shipped_seam_re_injects_a_gateway_result_into_the_backtest_driver() -> None:
    """GAP-1 (owner: D-E3 ``tos.backtest``, with a D-E4 shape to consume).

    ``BacktestDriver`` drains re-injected ``EGRESS_RESULT`` payloads through
    :meth:`DeterministicFillModel.settle_due` (driver.py:233) after calling
    ``bind_settlement_context`` (driver.py:225), and its constructor names that concrete class.
    ``BrokerEgressGateway`` merely **retains** its results on ``.results`` (gateway.py:1574) and
    exposes neither method. So when the D-E4 gateway occupies the ``Transmit`` slot — the very
    substitution design #33 §7.4 (c) declares — the harness has no shipped way to get the result
    back into the core, and slice #1 supplies a local adapter
    (:class:`~tests.slice._slice_fixtures.SendBoundarySlot`) to bridge it.

    Suggested shape: an ``EgressResultSource`` Protocol in ``tos.backtest`` that
    ``DeterministicFillModel`` and a gateway adapter both satisfy — the same
    "declared twice, satisfied structurally" pattern the two ``Transport`` Protocols already use.
    """
    parameters = inspect.signature(BacktestDriver.__init__).parameters
    assert "fill_model" in parameters
    assert "DeterministicFillModel" in str(parameters["fill_model"].annotation)

    # the driver's whole re-injection surface, and the gateway's total absence from it
    for method in ("bind_settlement_context", "settle_due", "unsettled_records"):
        assert hasattr(DeterministicFillModel, method)
        assert not hasattr(BrokerEgressGateway, method), (
            f"GAP-1 is closed: BrokerEgressGateway now exposes {method}"
        )

    # anti-phantom: neither package names the other, so no hidden joint exists
    driver_source = inspect.getsource(backtest_package.driver)
    gateway_source = inspect.getsource(egressgw_package.gateway)
    assert "egressgw" not in driver_source
    assert "brokeradapter" not in driver_source
    assert "backtest" not in gateway_source
    assert not [
        name
        for name in (*backtest_package.__all__, *egressgw_package.__all__)
        if any(token in name.lower() for token in ("reinject", "resultsource", "egressresultsource"))
    ]


def test_gap_1_the_local_adapter_adds_no_judgement_of_its_own() -> None:
    """The bridge is wiring, not policy: every verdict still comes from the shipped packages."""
    sliced = run_slice()
    # the slot produced no result — it forwarded the gateway's own, unchanged.
    assert sliced.slot.settle_due(sliced.book.context_for(0).bar) == ()
    assert len(sliced.gateway.results) == 1
    (egress_entry,) = [
        entry for entry in sliced.run.trace.entries if entry.event_kind.value == "EGRESS_RESULT"
    ]
    assert egress_entry.attempt_id == sliced.gateway.results[0].attempt_id
    assert egress_entry.egress_result_kind is sliced.gateway.results[0].kind
    # …and it holds no D-E3-local fill record, because the price/cost model is the fill band's.
    assert sliced.run.fill_records == ()
    assert sliced.run.unsettled_fill_records == ()


# ---------------------------------------------------------------------------
# GAP-2 — the send-boundary context is keyed by an identity that does not exist yet
# ---------------------------------------------------------------------------


def test_gap_2_no_shipped_builder_binds_a_send_boundary_context_to_a_live_attempt() -> None:
    """GAP-2 (owner: D-E4 ``tos.egressgw``).

    ``BrokerEgressGateway`` looks its context up by ``attempt.attempt_id`` (gateway.py:1420),
    but that identity is **content-addressed at step 12** from (proof digest, permit identity,
    reference-coordinate digest) — and under D-E3 the reference coordinate is the driver's
    global yield-order counter, deliberately decoupled from ``bar_index`` (driver.py:87-143).
    So a caller cannot populate ``contexts`` ahead of the run without predicting the driver's
    yield order.

    The shipped ``tos.egressgw`` suite sidesteps this by pre-running the deterministic
    construction with a hand-chosen coordinate; a *driver-fed* run cannot. Slice #1 therefore
    binds the context inside the ``Transmit`` call, from the attempt the sequencer just handed
    over. ``tos.egressgw`` exports a :class:`SendBoundaryContext` **type** but no factory that
    takes an ``AttemptRequest``, and no lazy/callable context resolver port.

    Suggested shape: accept a ``Callable[[AttemptRequest], SendBoundaryContext | None]``
    alongside the mapping — a missing context stays the same recorded stop it is today.
    """
    contexts_parameter = inspect.signature(BrokerEgressGateway.__init__).parameters["contexts"]
    assert "Mapping" in str(contexts_parameter.annotation)
    assert "Callable" not in str(contexts_parameter.annotation), (
        "GAP-2 is closed: the gateway now accepts a lazy context resolver"
    )

    factories = [
        name
        for name in egressgw_package.__all__
        if name != "SendBoundaryContext" and "send_boundary_context" in name.lower()
    ]
    assert factories == [], f"GAP-2 is closed: {factories}"

    # the identity really is only knowable after step 12 — it is not a function of the bar.
    sliced = run_slice()
    (attempt,) = sliced.slot.handoffs
    assert attempt.attempt_id.startswith("attempt-")
    assert attempt.reference_coordinate_digest
    (bound,) = sliced.slot.bound_contexts
    assert bound.reservation_attempt_id == attempt.attempt_id


# ---------------------------------------------------------------------------
# GAP-3 — Order Construction's price is injected, never read off the value surface
# ---------------------------------------------------------------------------


def test_gap_3_the_construction_price_is_injected_not_value_sourced() -> None:
    """GAP-3 (owner: D-E4 ``tos.egressgw``, consuming a D-E2 shape).

    :class:`~tos.egressgw.AdmittedPriceObservation` carries three primitives — ``source`` /
    ``value`` / ``snapshot_digest`` — and ``derive_order_size`` requires ``source`` to be the
    capsule context source (construction.py:214-219), which structurally blocks a
    *config*-relabelled price. What it cannot do is *obtain* one: there is no shipped path from
    a :class:`~tos.dsl.ContextValueView` — the admitted, digest-bound value surface D-E2 landed —
    to this record, so the price the send is sized against is an injected scalar whose only tie
    to the run is a ``snapshot_digest`` string the caller supplies.

    Slice #1 binds that digest to the crossing bar's **real** snapshot, so the lineage pointer
    is genuine; the magnitude is still injected. The consequence, stated plainly: the number the
    strategy decided on and the number the order was sized against are two different numbers.

    Suggested shape: a projection from ``ContextValueView`` → ``AdmittedPriceObservation`` that
    carries the value **and** its ``payload_digest`` provenance, so the tie is a digest rather
    than a caller's promise.
    """
    assert list(AdmittedPriceObservation.model_fields) == [
        "source",
        "value",
        "snapshot_digest",
    ]

    # anti-phantom: the D-E2 carrier type appears nowhere in D-E4's sources
    for module in (
        egressgw_package.records,
        egressgw_package.construction,
        egressgw_package.gateway,
    ):
        assert ContextValueView.__name__ not in inspect.getsource(module)
    assert "marketfeed" not in inspect.getsource(egressgw_package.construction)
    assert "marketfeed" not in inspect.getsource(brokeradapter_package.synthetic)

    # and the fields of the context that carry the outbound economics know nothing of a view
    assert "value_view" not in SendBoundaryContext.model_fields

    # the observable consequence in this run
    sliced = run_slice()
    (bound,) = sliced.slot.bound_contexts
    crossing_close = sliced.book.context_for(1).close
    assert bound.outbound_price is not None
    assert bound.outbound_price != Decimal(crossing_close), (
        "GAP-3 may be closed: the outbound price now equals the decided-on close"
    )


# ---------------------------------------------------------------------------
# GAP-4 — the Explicit-Flat exit has no Order Construction path
# ---------------------------------------------------------------------------


def test_gap_4_the_explicit_flat_basis_has_no_construction_path() -> None:
    """GAP-4 (owner: D-E4 ``tos.egressgw`` — and, behind it, the absent RCL release path).

    A dsl Explicit Flat carries ``quantity_basis == FLAT_QUANTITY_BASIS`` ("ZERO_POSITION",
    proposal.py:49) by construction — an ACTION proposal may not use it and a FLAT proposal must
    (proposal.py:160-175). ``derive_order_size`` renders a size from
    ``risk_budget / per_unit_risk`` and reads **no held position**, so:

    * with the default admitted set the flat is *denied at step 2* — which is what this slice
      observes (``test_slice_end_to_end.py::test_the_upper_band_cross_emits_a_flat_proposal…``);
    * and admitting ``ZERO_POSITION`` into the set does not help: the derived size is then
      **identical to the entry size**, i.e. an entry-sized order wearing an exit's basis.

    So the exit half of a band-reversion strategy is expressible in the DSL and unconstructable
    at the send boundary. That is consistent with the rest of the slice — the provisional
    projection has no release path either (state.py:22), so a round trip is deferred to the real
    RCL — but the *reason it stops* is the sizing rule, not the capacity seal, and the two should
    not be conflated.

    Suggested shape: a position-closing derivation branch whose magnitude comes from the
    authoritative held position, not from a risk budget.
    """
    book = BandBarBook()
    price = admitted_price(book)
    constraint = venue_quantity_constraint()

    default_envelope = proposed_envelope()
    denied = derive_order_size(
        quantity_basis=FLAT_QUANTITY_BASIS,
        envelope=default_envelope,
        price=price,
        venue_constraint=constraint,
    )
    assert denied.outcome is DerivationOutcome.DENIED
    assert denied.quantity is None
    assert denied.denial_reason is not None
    assert FLAT_QUANTITY_BASIS in denied.denial_reason

    widened = proposed_envelope(
        sizing_bound=sizing_bound(
            admitted_quantity_bases=frozenset({"RISK", FLAT_QUANTITY_BASIS})
        )
    )
    flat_size = derive_order_size(
        quantity_basis=FLAT_QUANTITY_BASIS,
        envelope=widened,
        price=price,
        venue_constraint=constraint,
    )
    entry_size = derive_order_size(
        quantity_basis="RISK",
        envelope=widened,
        price=price,
        venue_constraint=constraint,
    )
    assert flat_size.outcome is DerivationOutcome.DERIVED
    assert entry_size.outcome is DerivationOutcome.DERIVED
    assert flat_size.quantity == entry_size.quantity, (
        "GAP-4 may be closed: the flat basis now derives a position-closing size"
    )


def test_gap_4_the_scope_stays_occupied_because_there_is_no_release_path() -> None:
    """The companion fact: even a realized exit could not free the scope in slice #1.

    ``ProvisionalReservationLedger`` exposes no ``release`` / ``free`` / ``clear`` method at all
    (state.py:22) and ``RELEASED`` is absent from its projection order, so the round trip waits
    for the real RCL (RFC-002 §9.1:557) regardless of GAP-4.
    """
    sliced = run_slice()
    ledger = sliced.core.ledger
    for method in ("release", "free", "clear", "reset"):
        assert not hasattr(ledger, method), f"the projection gained a {method} path"
    outstanding = ledger.outstanding(sliced.run.instrument_key)
    assert outstanding is not None
    assert ledger.admits_new_exposure(sliced.run.instrument_key) is False
