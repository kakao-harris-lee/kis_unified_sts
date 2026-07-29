"""§8-2 — the deterministic fill model, all six result kinds (design #33 §4.2/§4.3/§4.4).

Four properties carry the design's weight here.

**Determinism.** No ``random`` / ``secrets`` / ``uuid`` / clock exists on this path, so the same
``(bar, injected parameters)`` always produce the same payload and the same D-E3-local record. The
seed slot RFC-003 §10:360-363 would demand for a stochastic slippage model is a forward seam and
stays unused — but the discipline is already stated in the module docstring, which is the point of
writing it before it is needed.

**Structural derivation over self-report** (design #33 §4.2 / §13). The model computes the filled and
remaining magnitudes and lets *them* decide full versus partial; ``EgressResultPayload`` then
re-derives the same distinction independently (``records.py:221-229``) and rejects a contradiction.
Two independent derivations and no label to trust — which is why the relabelling mutation cannot
survive: it is caught at construction, not by a comparison someone remembered to write.

**The execution price is D-E3-local** (design #33 §4.3 B4). The engine's ``EgressResultPayload`` has
no price field at all, and this suite asserts that absence directly rather than describing it
(anti-phantom §0.5), then shows the price living in the harness's own record instead.

**Cost realism, never optimism.** Slippage is applied *against* the taker and costs are added; a
negative slippage or cost is refused, because an optimistic execution assumption is an
ADR-DEV-010 §8:189-190 disqualifier.

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.backtest import (
    DeterministicFillModel,
    ExecutionPriceBasis,
    FillMode,
    FillParameters,
    FillSide,
    LocalFillRecord,
    QuantityProvenance,
    SettlementPolicy,
    SettlementStatus,
    reference_bars,
    settleable_result_kinds,
)
from tos.engine import (
    FILL_RESULT_KINDS,
    AttemptRequest,
    EgressResultKind,
    EgressResultPayload,
)

from ._backtest_fixtures import INTEGRITY_ERRORS, build_fill_model, instrument_key


def _attempt(suffix: str = "0") -> AttemptRequest:
    """A content-addressed attempt request stand-in (its digests are opaque to the fill band)."""
    return AttemptRequest(
        attempt_id=f"attempt-{suffix}",
        conformance_proof_digest="proof-d",
        action_flow_permit_identity="permit-i",
        reference_coordinate_digest="coord-d",
    )


def _settle(**overrides: object) -> FillParameters:
    """A complete ``SETTLE`` parameter set with the given overrides."""
    base: dict[str, object] = {
        "mode": FillMode.SETTLE,
        "side": FillSide.BUY,
        "settlement": SettlementPolicy.SAME_BAR,
        "price_basis": ExecutionPriceBasis.CLOSE,
        "scenario_quantity": Decimal(10),
        "participation_cap_fraction": Decimal("0.5"),
        "slippage_bps": Decimal(5),
        "cost_per_unit": Decimal("0.02"),
        "limit_reference_price": Decimal(100),
        "price_band_fraction": Decimal("0.05"),
    }
    base.update(overrides)
    return FillParameters(**base)  # type: ignore[arg-type]


def _stage_and_settle(parameters: FillParameters) -> tuple[EgressResultPayload, LocalFillRecord]:
    """Stage one attempt against bar 0 and settle it there, returning both artifacts."""
    bar = reference_bars(1)[0]
    model = build_fill_model(parameters)
    model.bind_settlement_context(bar)
    handoff = model(_attempt())
    assert handoff.accepted_for_transmission is True
    settled = model.settle_due(bar)
    assert len(settled) == 1
    return settled[0].payload, settled[0].record


# ---------------------------------------------------------------------------
# the six result kinds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (FillMode.ACKNOWLEDGE, EgressResultKind.ACK),
        (FillMode.REPORT_UNKNOWN, EgressResultKind.UNKNOWN),
        (FillMode.REPORT_TIMEOUT, EgressResultKind.TIMEOUT),
    ],
)
def test_magnitude_free_modes_produce_their_kind_and_no_magnitude(
    mode: FillMode, expected: EgressResultKind
) -> None:
    """(§4.2) ACK / UNKNOWN / TIMEOUT carry no fill magnitude (``records.py:201-207``)."""
    payload, record = _stage_and_settle(FillParameters(mode=mode, side=FillSide.BUY))
    assert payload.kind is expected
    assert payload.filled_quantity is None
    assert payload.remaining_quantity is None
    assert record.result_kind is expected
    assert record.execution_price is None
    assert record.settlement_status is SettlementStatus.SETTLED


def test_a_quantity_within_the_participation_cap_is_a_full_fill() -> None:
    """(§4.2 row 1) ``Q ≤ available`` ⇒ FULL_FILL with remaining exactly zero."""
    payload, record = _stage_and_settle(_settle(scenario_quantity=Decimal(10)))
    assert payload.kind is EgressResultKind.FULL_FILL
    assert payload.filled_quantity == Decimal(10)
    assert payload.remaining_quantity == Decimal(0)
    assert record.requested_quantity == Decimal(10)


def test_a_quantity_beyond_the_participation_cap_is_a_partial_fill() -> None:
    """(§4.2 row 2) ``Q > cap × volume`` ⇒ PARTIAL_FILL, filled = the cap, remaining > 0.

    Nothing already filled is ever re-requested: the remaining magnitude is carried *as* remaining
    (RFC-005 §11:338-339), which is what makes the partial stay a partial downstream.
    """
    payload, record = _stage_and_settle(_settle(scenario_quantity=Decimal(800)))
    assert payload.kind is EgressResultKind.PARTIAL_FILL
    assert payload.filled_quantity == Decimal(500)  # 1000 volume × 0.5 cap
    assert payload.remaining_quantity == Decimal(300)
    assert record.filled_quantity == Decimal(500)
    assert record.remaining_quantity == Decimal(300)


def test_a_basis_outside_the_injected_band_is_a_deterministic_reject() -> None:
    """(§4.2 row 3) The rejection is a **predicate over injected parameters**, not a coin flip."""
    payload, record = _stage_and_settle(_settle(limit_reference_price=Decimal(50)))
    assert payload.kind is EgressResultKind.REJECT
    assert payload.filled_quantity is None
    assert record.reference_price == Decimal(100)
    assert record.execution_price is None


def test_the_reject_predicate_is_a_real_boundary_not_a_constant() -> None:
    """(§4.2) Widening the injected band turns the same bar from REJECT into a fill.

    The honest form of "injected, not hard-coded": if the model had a baked-in rejection it would
    not respond to the parameter.
    """
    rejecting, _ = _stage_and_settle(
        _settle(limit_reference_price=Decimal(50), price_band_fraction=Decimal("0.05"))
    )
    admitting, _ = _stage_and_settle(
        _settle(limit_reference_price=Decimal(50), price_band_fraction=Decimal(2))
    )
    assert rejecting.kind is EgressResultKind.REJECT
    assert admitting.kind is EgressResultKind.FULL_FILL


def test_every_egress_result_kind_is_reachable_from_some_mode() -> None:
    """(§4.2 / §5.1 MINOR-2) All six members of the closed vocabulary are produced — 전수.

    Anti-phantom in its *existence* direction (design #33 §0.5): the coverage claim is computed
    from the shipped enum, so adding a member without a producing mode fails here.
    """
    produced: set[EgressResultKind] = set()
    for mode in FillMode:
        produced |= settleable_result_kinds(mode)
    assert produced == set(EgressResultKind), (
        f"uncovered EgressResultKind members: {sorted(set(EgressResultKind) - produced)}"
    )


def test_a_mode_may_not_produce_a_kind_outside_its_closed_set() -> None:
    """(§4.2) Positive membership — a mode that could produce anything means nothing."""
    assert settleable_result_kinds(FillMode.ACKNOWLEDGE) == frozenset(
        {EgressResultKind.ACK}
    )
    assert settleable_result_kinds(FillMode.SETTLE) >= FILL_RESULT_KINDS
    assert EgressResultKind.ACK not in settleable_result_kinds(FillMode.SETTLE)


# ---------------------------------------------------------------------------
# structural derivation (구조 파생 > 자기신고)
# ---------------------------------------------------------------------------


def test_a_relabelled_partial_is_unconstructable() -> None:
    """(§4.2/§13) A remaining quantity > 0 recorded as FULL_FILL is refused at construction.

    The engine derives the distinction from the magnitudes (``records.py:221-229``), so a fill model
    that *declared* the kind could not smuggle a partial past it. This is why the relabelling
    mutation dies immediately rather than requiring a bespoke comparison test.
    """
    with pytest.raises(Exception, match="contradicts the magnitudes"):
        EgressResultPayload(
            instrument_key=instrument_key(),
            attempt_id="attempt-0",
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal(500),
            remaining_quantity=Decimal(300),
        )


def test_the_magnitudes_decide_the_kind_across_the_boundary() -> None:
    """(§4.2) Sweeping Q across the cap flips the derived kind exactly at the boundary."""
    boundary = Decimal(500)  # 1000 volume × 0.5 cap
    below, _ = _stage_and_settle(_settle(scenario_quantity=boundary - 1))
    at, _ = _stage_and_settle(_settle(scenario_quantity=boundary))
    above, _ = _stage_and_settle(_settle(scenario_quantity=boundary + 1))
    assert below.kind is EgressResultKind.FULL_FILL
    assert at.kind is EgressResultKind.FULL_FILL
    assert above.kind is EgressResultKind.PARTIAL_FILL


def test_the_magnitude_is_labelled_as_a_scenario_parameter() -> None:
    """(§4.3) Slice #1's flow carries no concrete quantity, so its provenance is recorded honestly."""
    _, record = _stage_and_settle(_settle())
    assert record.quantity_provenance is QuantityProvenance.SCENARIO_PARAMETER
    assert set(QuantityProvenance) == {QuantityProvenance.SCENARIO_PARAMETER}, (
        "slice #1 has exactly one honest provenance; a flow-derived member would be a phantom "
        "while Order Construction is a provisional stand-in (design #33 §4.3)"
    )


# ---------------------------------------------------------------------------
# the price lives in D-E3, not in the engine (B4)
# ---------------------------------------------------------------------------


def test_the_engine_egress_payload_has_no_price_field() -> None:
    """(§4.3 B4, anti-phantom §0.5) The absence claim is read off the shipped model, not asserted."""
    field_names = set(EgressResultPayload.model_fields)
    assert field_names == {
        "instrument_key",
        "attempt_id",
        "kind",
        "filled_quantity",
        "remaining_quantity",
        "reference",
    }
    assert not [name for name in field_names if "price" in name.lower()]


def test_the_execution_price_lives_in_the_d_e3_local_record() -> None:
    """(§4.3) Slippage and cost are applied here and never injected into the engine."""
    payload, record = _stage_and_settle(_settle())
    assert not hasattr(payload, "execution_price")
    assert record.reference_price == Decimal(100)
    assert record.slippage_component == Decimal("0.05")  # 100 × 5bps
    assert record.execution_price == Decimal("100.05")
    assert record.cost_component == Decimal("0.2")  # 0.02 × 10 filled
    assert record.settlement_bar_close == Decimal(100)


def test_slippage_is_applied_against_the_taker_on_both_sides() -> None:
    """(ADR-DEV-010 §8:189-190) A buy pays up and a sell receives less — never the better side."""
    _, buy = _stage_and_settle(_settle(side=FillSide.BUY))
    _, sell = _stage_and_settle(_settle(side=FillSide.SELL))
    assert buy.execution_price is not None and sell.execution_price is not None
    assert buy.execution_price > buy.reference_price  # type: ignore[operator]
    assert sell.execution_price < sell.reference_price  # type: ignore[operator]


def test_the_price_basis_is_injected() -> None:
    """(§4.3) OPEN and CLOSE really select different prints of the settlement bar."""
    bars = reference_bars(2)
    model = build_fill_model(_settle(price_basis=ExecutionPriceBasis.OPEN))
    model.bind_settlement_context(bars[1])
    model(_attempt())
    (settled,) = model.settle_due(bars[1])
    assert settled.record.reference_price == bars[1].open_price


def test_a_negative_slippage_or_cost_is_refused() -> None:
    """(ADR-DEV-010 §8:189-190) An optimistic execution assumption is a disqualifier."""
    for field in ("slippage_bps", "cost_per_unit", "price_band_fraction"):
        with pytest.raises(INTEGRITY_ERRORS, match="must be non-negative"):
            _settle(**{field: Decimal(-1)})


# ---------------------------------------------------------------------------
# parameter completeness + settlement discipline
# ---------------------------------------------------------------------------


def test_a_settle_mode_missing_any_injected_parameter_is_refused() -> None:
    """(§10) Absence is never a default — defaulting a bound here would be a hardcoded number."""
    with pytest.raises(INTEGRITY_ERRORS, match="requires every injected settlement parameter"):
        FillParameters(mode=FillMode.SETTLE, side=FillSide.BUY)


def test_a_magnitude_free_mode_carrying_a_magnitude_is_refused() -> None:
    """(§4.2 ∅ discipline) ACK / UNKNOWN / TIMEOUT carry no magnitude — mirroring the engine rule."""
    with pytest.raises(INTEGRITY_ERRORS, match="must carry no settlement magnitude"):
        FillParameters(
            mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY, scenario_quantity=Decimal(10)
        )


def test_an_out_of_range_participation_cap_is_refused() -> None:
    """(§4.3) A cap above 1 would fill more than the settlement bar traded."""
    with pytest.raises(INTEGRITY_ERRORS, match="participation_cap_fraction"):
        _settle(participation_cap_fraction=Decimal(2))
    with pytest.raises(INTEGRITY_ERRORS, match="participation_cap_fraction"):
        _settle(participation_cap_fraction=Decimal(0))


def test_next_bar_settlement_does_not_settle_early() -> None:
    """(§3.6) A ``NEXT_BAR`` fill stays pending on its decision bar — settling early changes the model."""
    bars = reference_bars(2)
    model = build_fill_model(_settle(settlement=SettlementPolicy.NEXT_BAR))
    model.bind_settlement_context(bars[0])
    model(_attempt())
    assert model.settle_due(bars[0]) == ()
    assert len(model.pending) == 1
    settled = model.settle_due(bars[1])
    assert len(settled) == 1
    assert settled[0].record.decision_bar_index == 0
    assert settled[0].record.settlement_bar_index == 1
    assert settled[0].record.settlement_bar_close == bars[1].close_price


def test_a_fill_left_pending_at_stream_end_is_recorded_unsettled_never_invented() -> None:
    """(§4.1) No settlement bar ⇒ no result kind and no magnitude — the run records what it had."""
    bars = reference_bars(1)
    model = build_fill_model(_settle(settlement=SettlementPolicy.NEXT_BAR))
    model.bind_settlement_context(bars[0])
    model(_attempt())
    (record,) = model.unsettled_records()
    assert record.settlement_status is SettlementStatus.UNSETTLED_AT_STREAM_END
    assert record.result_kind is None
    assert record.filled_quantity is None
    assert record.execution_price is None


def test_a_hand_off_without_a_bound_settlement_context_is_fail_closed() -> None:
    """(§4.1) A fill with no settlement coordinate is not a fill — the band raises, never guesses."""
    model = build_fill_model(_settle())
    with pytest.raises(INTEGRITY_ERRORS, match="no settlement context"):
        model(_attempt())


def test_a_settlement_bar_with_no_participation_capacity_is_refused() -> None:
    """(§4.2) The closed result vocabulary has no 'nothing happened' member — inventing one is a phantom."""
    from tos.backtest import Bar

    empty_bar = Bar(
        bar_index=0,
        timestamp_coordinate=60,
        open_price=Decimal(100),
        high_price=Decimal(101),
        low_price=Decimal(99),
        close_price=Decimal(100),
        volume=Decimal(0),
        session_token="session-0",
    )
    model = build_fill_model(_settle())
    model.bind_settlement_context(empty_bar)
    model(_attempt())
    with pytest.raises(INTEGRITY_ERRORS, match="no participation capacity"):
        model.settle_due(empty_bar)


# ---------------------------------------------------------------------------
# determinism (§4.4)
# ---------------------------------------------------------------------------


def test_the_same_inputs_always_produce_the_same_fill() -> None:
    """(§4.4) RNG 0 / clock 0: two independent bands agree byte-for-byte on every field."""
    parameters = _settle(scenario_quantity=Decimal(800))
    first_payload, first_record = _stage_and_settle(parameters)
    second_payload, second_record = _stage_and_settle(parameters)
    assert first_payload.model_dump(mode="json") == second_payload.model_dump(mode="json")
    assert first_record.model_dump(mode="json") == second_record.model_dump(mode="json")


def test_the_band_transmits_nothing_and_only_records() -> None:
    """(RFC-002 §10.8:763) The fill model is a synthetic band, never a live-order method."""
    bar = reference_bars(1)[0]
    model = build_fill_model(_settle())
    model.bind_settlement_context(bar)
    model(_attempt("a"))
    assert [attempt.attempt_id for attempt in model.handoffs] == ["attempt-a"]
    for forbidden in ("send", "post", "connect", "request", "session", "client"):
        assert not hasattr(model, forbidden), (
            f"DeterministicFillModel exposes {forbidden!r} — the send boundary is D-E4's and this "
            "band never reaches it (design #33 §4.1)"
        )


def test_the_model_satisfies_the_engine_transmit_protocol() -> None:
    """(§4.1/§14) The band and D-E4's real sender satisfy the **same** injected seam."""
    from tos.engine import Transmit

    assert isinstance(build_fill_model(_settle()), Transmit)
    assert isinstance(build_fill_model(_settle()), DeterministicFillModel)
