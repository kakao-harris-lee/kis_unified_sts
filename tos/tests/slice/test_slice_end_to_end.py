"""Vertical slice #1 end to end — value surface → capsule → DSL → sequencer → send boundary.

The completion condition of the slice
(``docs/plans/2026-07-29-tos-engine-completion-path-assessment.md`` §3-1): **one DSL strategy →
an event-driven backtest → one paper order**, running through the four landed lanes' *public
APIs only*.

The file is organised as the data flows, one section per segment, so a failure names the seam
that broke rather than "the slice". Every assertion reads an artifact the shipped packages
produced — the engine's own ``EventResult``, the gateway's own
:class:`~tos.egressgw.SendBoundaryVerification`, the transport's own request log — never a
restatement the harness kept beside them (RFC-010 §6 원칙 1:183-185).

⚠ **Authoring evidence; closes no EV.** Four independent reasons, one per lane, are on the
package docstrings: the canonicalization scheme is ``ev-l1-provisional-0``, the authority
runtimes are ``NON_AUTHORITATIVE_PROVISIONAL`` stand-ins, no broker is contacted, and a
single-run backtest is an ADR-DEV-010 §8:191-192 disqualifier. This demonstrates **wiring**.
"""

from __future__ import annotations

from tos.backtest import trace_digest, trace_document
from tos.dsl import FLAT_QUANTITY_BASIS
from tos.egressgw import (
    ADMITTING_VERIFY_OUTCOMES,
    DEFERRED_ITEMS,
    SEND_VERIFY_ITEMS,
    BrokerApplicability,
    SendVerifyItem,
    VerifyDisposition,
    VerifyOutcome,
)
from tos.engine import (
    AdmissionVerdict,
    CommitmentStep,
    EgressResultKind,
    EventKind,
    HaltReason,
    OrderingAdmission,
    StageOutcome,
    strategy_admissible,
)
from tos.marketfeed import ValueViewDisposition, view_digest_matches
from tos.rcl import CapacityState

from ._slice_fixtures import (
    BAND_PROFILE,
    CROSSING_BAR_INDEX,
    DENIED_BAR_INDEX,
    FLAT_BAR_INDEX,
    INSIDE_BAR_INDEXES,
    LOWER_BAND,
    SCHEME,
    UPPER_BAND,
    BandBarBook,
    band_reversion_strategy,
    build_resolver,
    instrument_key,
    run_slice,
)

# ---------------------------------------------------------------------------
# segment 1 — the market number reaches an admitted, digest-bound value surface
# ---------------------------------------------------------------------------


def test_every_bar_publishes_a_resolved_value_view_bound_to_its_own_snapshot() -> None:
    """(design #32 §3.3) The real marketfeed resolver admits all three band values per bar."""
    book = BandBarBook()
    resolver = build_resolver(book)
    for context in book.contexts:
        resolved = resolver.resolve(context.capsule, instrument_key=instrument_key())
        assert resolved.resolution.disposition is ValueViewDisposition.RESOLVED
        assert resolved.resolution.rejected == ()
        view = resolved.payload.value_view
        assert view is not None
        assert view.snapshot_id == context.snapshot.snapshot_id
        assert view.snapshot_canonical_digest == context.snapshot.canonical_digest
        assert view.as_environment_mapping() == {
            "close": context.close,
            "lower_band": LOWER_BAND,
            "upper_band": UPPER_BAND,
        }
        # ★ the view's recorded digest really is the digest of its own content.
        assert view_digest_matches(view, SCHEME)


def test_distinct_bars_produce_distinct_snapshot_capsule_and_view_digests() -> None:
    """(design #32 §4) The D-E1 Gap-1 residue: per-bar identities are actually distinct."""
    book = BandBarBook()
    resolver = build_resolver(book)
    snapshots = {context.snapshot.canonical_digest for context in book.contexts}
    capsules = {context.capsule.canonical_digest for context in book.contexts}
    views = {
        resolver.resolve(
            context.capsule, instrument_key=instrument_key()
        ).payload.value_view.canonical_digest  # type: ignore[union-attr]
        for context in book.contexts
    }
    assert len(snapshots) == len(book.contexts)
    assert len(capsules) == len(book.contexts)
    assert len(views) == len(book.contexts)


# ---------------------------------------------------------------------------
# segment 2 — the DSL strategy is admissible on capsule-sourced operands
# ---------------------------------------------------------------------------


def test_the_band_strategy_is_admissible_and_keys_itself() -> None:
    """(design #31 §3.3/§3.5) Typed admission passes and derives the key from the artifact."""
    admission = strategy_admissible(band_reversion_strategy())
    assert admission.verdict is AdmissionVerdict.ADMISSIBLE
    assert admission.reasons == ()
    assert admission.instrument_key == instrument_key()


# ---------------------------------------------------------------------------
# segment 3 — the run: one core, one sequencer, one send boundary
# ---------------------------------------------------------------------------


def test_the_run_yields_one_event_per_bar_plus_the_single_re_injected_result() -> None:
    """(design #33 §4.1) Interleaving: five ticks + exactly one ``EGRESS_RESULT``."""
    sliced = run_slice()
    assert sliced.run.bars_consumed == len(sliced.book.contexts)
    kinds = [entry.event_kind for entry in sliced.run.trace.entries]
    assert kinds.count(EventKind.DECISION_TICK) == len(sliced.book.contexts)
    assert kinds.count(EventKind.EGRESS_RESULT) == 1
    assert sliced.run.events_yielded == len(kinds)
    # coordinate order ≡ processing order, and nothing was refused as out of order.
    assert [entry.yield_sequence for entry in sliced.run.trace.entries] == list(
        range(1, len(kinds) + 1)
    )
    assert all(
        entry.ordering_admission is OrderingAdmission.MONOTONE
        for entry in sliced.run.trace.entries
    )


def test_a_single_core_drives_the_whole_run() -> None:
    """(design #33 §2.4) The driver binds one core; a per-bar rebuild would forge headroom."""
    sliced = run_slice()
    assert sliced.run.trace.continuity_id == "slice-1-stream"
    assert sliced.core is not None
    # The ledger is the *same* projection across every bar — that is what makes the
    # at-most-one seal observable at all.
    outstanding = sliced.core.ledger.outstanding(instrument_key())
    assert outstanding is not None
    assert outstanding.capacity_state is CapacityState.POSITION_CONSUMED


# -- (a) exactly one paper-order hand-off ------------------------------------


def test_a_exactly_one_paper_order_is_handed_off_and_the_second_signal_is_denied() -> None:
    """(a) The band-crossing bar realizes one order; the next crossing is capacity-denied."""
    sliced = run_slice()

    crossing = sliced.result_for(CROSSING_BAR_INDEX)
    assert crossing.halt_reason is None
    assert crossing.flow is not None
    assert crossing.flow.handed_off is True
    assert crossing.flow.attempt is not None
    assert crossing.flow.handoff is not None
    assert crossing.flow.handoff.accepted_for_transmission is True
    # every step 1-14 admitted positively — no step was skipped into a pass.
    assert len(crossing.flow.verdicts) == 14
    assert all(
        verdict.outcome is StageOutcome.ADMIT for verdict in crossing.flow.verdicts
    )

    denied = sliced.result_for(DENIED_BAR_INDEX)
    assert denied.pipeline is not None
    assert denied.pipeline.proposal is not None, "the second crossing did emit a proposal"
    assert denied.flow is not None
    assert denied.flow.handed_off is False
    assert denied.flow.halt_step is CommitmentStep.LEDGER_VERIFICATION
    assert denied.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD

    # at-most-one, measured at every layer that could have leaked a second order.
    assert len(sliced.resolver.attempts) == 1
    assert len(sliced.gateway.results) == 1
    assert len(sliced.transport.requests) == 1
    assert len(sliced.gateway.results) == 1
    assert sliced.run.handoff_count == 1
    handed = [entry for entry in sliced.run.trace.entries if entry.handed_off]
    assert len(handed) == 1
    assert handed[0].bar_index == CROSSING_BAR_INDEX


# -- (b) non-crossing bars are No-Action -------------------------------------


def test_b_a_bar_inside_the_band_is_a_no_action_and_starts_no_flow() -> None:
    """(b) No proposal, no flow, no hand-off — the default Decision, recorded."""
    sliced = run_slice()
    for bar_index in INSIDE_BAR_INDEXES:
        result = sliced.result_for(bar_index)
        assert result.halt_reason is HaltReason.NO_ACTION_OUTCOME
        assert result.pipeline is not None
        assert result.pipeline.proposal is None
        assert type(result.pipeline.outcome).__name__ == "NoActionOutcome"
        assert result.flow is None, "a no-action must start no commitment flow"


# -- (c) the 17-item verify list ---------------------------------------------


def test_c_the_seventeen_item_verify_list_admitted_with_a_positive_synthetic_na() -> None:
    """(c) All seventeen items judged; the six deferred ones are positively N/A."""
    sliced = run_slice()
    assert len(sliced.gateway.verifications) == 1
    verification = sliced.gateway.verifications[0]

    assert verification.admitted is True
    assert verification.halt_item is None
    assert verification.halt_reason is None
    assert verification.applicability is BrokerApplicability.NON_BROKER_SYNTHETIC

    assert len(verification.verdicts) == len(SEND_VERIFY_ITEMS) == 17
    assert tuple(verdict.item for verdict in verification.verdicts) == SEND_VERIFY_ITEMS
    assert all(
        verdict.outcome in ADMITTING_VERIFY_OUTCOMES for verdict in verification.verdicts
    )

    # ★ the N/A is a recorded positive judgement about a synthetic non-broker send, never a
    #   silent skip: exactly the six deferred mesh items, and only those, are NOT_APPLICABLE.
    not_applicable = {
        verdict.item
        for verdict in verification.verdicts
        if verdict.outcome is VerifyOutcome.NOT_APPLICABLE
    }
    assert not_applicable == set(DEFERRED_ITEMS)
    for verdict in verification.verdicts:
        if verdict.item in DEFERRED_ITEMS:
            assert verdict.disposition is VerifyDisposition.DEFERRED_APPLICABILITY
            assert verdict.native_verdict_value == BrokerApplicability.NON_BROKER_SYNTHETIC.value
        else:
            assert verdict.outcome is VerifyOutcome.SATISFIED

    # the gateway's own record order: 17 verify items, then claim/SEND_STARTED, then the call.
    kinds = sliced.gateway_sink.kinds
    assert kinds.count("VERIFY_ITEM") == 17
    assert kinds.index("SEND_STARTED") > max(
        index for index, kind in enumerate(kinds) if kind == "VERIFY_ITEM"
    )
    assert kinds.index("POTENTIALLY_LIVE_OBSERVED") > kinds.index("SEND_STARTED")
    assert kinds.index("EGRESS_RESULT_RECORDED") > kinds.index("POTENTIALLY_LIVE_OBSERVED")


def test_the_venue_shape_price_is_value_sourced_and_converged() -> None:
    """(design #36 §7.3) The shape venue admits carries the number the strategy decided on.

    Slice #1's last internal inconsistency, as design #35 §4.4 recorded it: venue admitted a
    4,200-shape while the command carried the value-surface 4,499,000, and no verify path
    compared the two — harmless, and *only* harmless because nothing looked. Both halves close
    here. The shape price is re-sourced from the same admitted value the command was priced on,
    and the item-11 context reads the **same object** step 3 folded rather than rebuilding a
    look-alike, so the two can no longer disagree without something failing loudly.

    The convergence is over the price-comparison pair only — the shape and the constraints
    ``order_shape_admissible`` compares. The snapshot / policy / decision inputs are still built
    twice; they are deterministic and carry no runtime value, and folding them in would reach
    past this seam (design #36 §2.2).
    """
    sliced = run_slice()
    crossing_close = sliced.book.context_for(CROSSING_BAR_INDEX).close
    (bound,) = sliced.resolver.contexts

    # ★ value-sourced: the shape price is the crossing close, not the injected stand-in.
    assert bound.order_shape is not None
    assert bound.order_shape.price == crossing_close
    assert bound.order_shape.price != 4200

    # ★ one source: the item-11 context reads step 3's retained pair, object-identically.
    #   The constraints are fixed for the run, so their identity is readable at the end of it.
    assert bound.venue_shape_constraints is sliced.venue_stage.shape_constraints
    #   The shape is not: ``resolved_shape`` is **single-retention**, inherited from
    #   ``OrderConstructionStage.construction`` (design #36 §10-4 — per-attempt keying is #37's),
    #   so after a multi-bar run it holds the *last* fold, which is the flat bar's close and not
    #   the crossing's. That is a real property of the retention model, so it is asserted rather
    #   than worked around — and the shape identity is then read where it is live, below.
    assert sliced.venue_stage.resolved_shape is not None
    assert sliced.venue_stage.resolved_shape.price == sliced.book.context_for(
        FLAT_BAR_INDEX
    ).close

    # ★ …so the object identity is taken on a run that ends at the crossing: same shipped wiring,
    #   one fold, and the context the resolver produced carries **that object**, not a rebuild.
    at_crossing = run_slice(profile=BAND_PROFILE[: CROSSING_BAR_INDEX + 1])
    (bound_at_crossing,) = at_crossing.resolver.contexts
    assert bound_at_crossing.order_shape is at_crossing.venue_stage.resolved_shape
    assert bound_at_crossing.venue_shape_constraints is (
        at_crossing.venue_stage.shape_constraints
    )
    assert bound_at_crossing.order_shape is not None
    assert bound_at_crossing.order_shape.price == crossing_close

    # ★ the inconsistency this closes: the admitted shape and the command now agree.
    assert bound.construction is not None
    assert bound.order_shape.price == int(bound.construction.derivation.price)

    # ★ …and item 11 is still SATISFIED — the re-sourced price is venue-admissible.
    verification = sliced.gateway.verifications[0]
    item11 = next(
        verdict
        for verdict in verification.verdicts
        if verdict.item is SendVerifyItem.VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION
    )
    assert item11.outcome is VerifyOutcome.SATISFIED


def test_the_synthetic_transport_was_called_exactly_once_with_the_bound_scalars() -> None:
    """(design #34 §5.1/§5.3) One verified outbound, one result, bound to the construction."""
    sliced = run_slice()
    (request,) = sliced.transport.requests
    (context,) = sliced.resolver.contexts
    assert request.attempt.attempt_id == sliced.resolver.attempts[0].attempt_id
    assert request.instrument_key == instrument_key()
    assert request.quantity == context.outbound_quantity
    assert request.price == context.outbound_price
    assert request.side == context.outbound_side
    assert context.construction is not None
    assert request.quantity == context.construction.derivation.quantity


def test_the_egress_result_is_re_injected_and_advances_the_projection() -> None:
    """(design #31 §2.2/§2.4) FULL_FILL → POSITION_CONSUMED / FILLED, on the exact attempt."""
    sliced = run_slice()
    (egress_entry,) = [
        entry
        for entry in sliced.run.trace.entries
        if entry.event_kind is EventKind.EGRESS_RESULT
    ]
    assert egress_entry.egress_result_kind is EgressResultKind.FULL_FILL
    assert egress_entry.attempt_id == sliced.resolver.attempts[0].attempt_id
    assert egress_entry.capacity_state is CapacityState.POSITION_CONSUMED
    assert egress_entry.knowledge is not None
    assert egress_entry.knowledge.value == "FILLED"
    result = sliced.run.event_results[egress_entry.yield_sequence - 1]
    assert result.halt_reason is None
    assert result.reservation is not None
    assert result.reservation.attempt_id == sliced.resolver.attempts[0].attempt_id


def test_the_send_boundary_ran_only_the_steps_the_engine_refuses_to_host() -> None:
    """(design #31 §4.5 item-7) Steps 1-14 in the sequencer, 15-19 in the gateway."""
    sliced = run_slice()
    crossing = sliced.result_for(CROSSING_BAR_INDEX)
    assert crossing.flow is not None
    sequenced = tuple(verdict.step for verdict in crossing.flow.verdicts)
    assert CommitmentStep.SEND_BOUNDARY_VERIFICATION not in sequenced
    assert CommitmentStep.NETWORK_CALL not in sequenced
    assert CommitmentStep.EVIDENCE_RECORD not in sequenced
    # …and the gateway is what produced the step 15-19 evidence.
    assert "SEND_STARTED" in sliced.gateway_sink.kinds
    assert "EGRESS_RESULT_RECORDED" in sliced.gateway_sink.kinds


# -- (d) replay reproducibility ----------------------------------------------


def test_d_two_runs_over_the_same_inputs_reproduce_every_identity() -> None:
    """(d) Same inputs → same outcome digests, signatures, attempt ids, and trace digest."""
    first = run_slice()
    second = run_slice()

    assert trace_digest(first.run, scheme=SCHEME) == trace_digest(second.run, scheme=SCHEME)
    assert trace_document(first.run) == trace_document(second.run)

    for index in range(len(first.book.contexts)):
        left = first.result_for(index)
        right = second.result_for(index)
        assert left.halt_reason == right.halt_reason
        assert left.pipeline is not None and right.pipeline is not None
        assert left.pipeline.outcome_digest == right.pipeline.outcome_digest
        assert left.pipeline.signature == right.pipeline.signature

    assert (
        first.resolver.attempts[0].attempt_id == second.resolver.attempts[0].attempt_id
    ), "the attempt identity is content-addressed, so replay reproduces it"
    assert first.gateway.results[0] == second.gateway.results[0]


def test_d_the_value_view_digest_joins_the_recorded_input_signature() -> None:
    """(d) design #32 §3.2 (3b): a different value set ⇒ a different recorded signature."""
    sliced = run_slice()
    book = sliced.book
    resolver = build_resolver(book)
    for index, context in enumerate(book.contexts):
        view = resolver.resolve(
            context.capsule, instrument_key=instrument_key()
        ).payload.value_view
        assert view is not None
        signature = sliced.result_for(index).pipeline.signature
        assert signature is not None
        assert view.canonical_digest in signature.captured_external_value_refs
        # the snapshot pointer is there too, and the view digest is *appended* to it.
        assert signature.captured_external_value_refs == (
            context.snapshot.canonical_digest,
            view.canonical_digest,
        )

    # distinct bars ⇒ distinct signatures (the property the append exists for).
    signatures = {
        sliced.result_for(index).pipeline.signature.captured_external_value_refs
        for index in range(len(book.contexts))
    }
    assert len(signatures) == len(book.contexts)


# -- (e) the trace document --------------------------------------------------


def test_e_the_run_emits_the_out_of_tree_oracle_trace_document() -> None:
    """(e) design #33 §6.1: a pure JSON-native artifact, performance-surface-free."""
    sliced = run_slice()
    document = trace_document(sliced.run)

    assert document["artifact_type"] == "tos.backtest.wiring_trace"
    assert document["closes_no_ev"] is True
    assert document["oracle_scope"] == "STRUCTURAL_WIRING_AGREEMENT_ONLY"
    assert document["bars_consumed"] == len(sliced.book.contexts)
    assert document["events_yielded"] == len(sliced.run.trace.entries)
    assert len(document["trace"]["entries"]) == len(sliced.run.trace.entries)

    # the fail-closed halts are recorded with their reasons — a stop is never silent.
    halts = {(halt["bar_index"], halt["halt_reason"]) for halt in document["halts"]}
    assert (DENIED_BAR_INDEX, HaltReason.AT_MOST_ONE_EXPOSURE_HELD.value) in halts
    for bar_index in INSIDE_BAR_INDEXES:
        assert (bar_index, HaltReason.NO_ACTION_OUTCOME.value) in halts
    # Every *flow* halt names its reason in prose. A no-action halt carries no detail — it is
    # not a stop but the policy's own default Decision, whose rationale lives on the emitted
    # NoActionOutcome instead; conflating the two would be the ∅ defect in reverse.
    flow_halts = [halt for halt in document["halts"] if halt["halt_step"] is not None]
    assert flow_halts
    assert all(halt["detail"] for halt in flow_halts)

    # and there is nowhere in the artifact to put a performance claim.
    serialized = repr(document)
    for token in ("sharpe", "pnl", "total_return", "admissibility_verdict"):
        assert token not in serialized.lower()


# ---------------------------------------------------------------------------
# the Explicit-Flat branch (recorded honestly — see test_slice_gaps.py)
# ---------------------------------------------------------------------------


def test_the_upper_band_cross_emits_a_flat_proposal_that_now_stops_at_the_capacity_seal() -> None:
    """The exit branch is constructable, and the halt has **moved** (design #35 §5.3).

    Before GAP-4 the flat stopped at step 2 because ``derive_order_size`` had no
    position-closing rule; it now derives its magnitude from the observed held position, so step 2
    admits and the flow runs on until the at-most-one exposure retention denies it at step 8.

    That move *is* the closure's content. Sizing a flat is not capacity admission: the scope is
    still occupied by the entry (no release path exists — ``state.py:22``), so the exit is still
    refused. What changed is that the recorded reason for the refusal is now the capacity seal
    rather than the sizing rule, and the two were never the same fact.
    """
    sliced = run_slice()
    result = sliced.result_for(FLAT_BAR_INDEX)
    assert result.pipeline is not None
    proposal = result.pipeline.proposal
    assert proposal is not None
    assert proposal.target_kind.value == "FLAT"
    assert proposal.quantity_basis == FLAT_QUANTITY_BASIS
    assert result.flow is not None
    assert result.flow.handed_off is False

    # ★ step 2 now admits: the flat was sized, from the position the entry actually took.
    outcomes = {verdict.step: verdict.outcome for verdict in result.flow.verdicts}
    assert (
        outcomes[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION] is StageOutcome.ADMIT
    )

    # ★ …and the stop is the capacity seal, named as such.
    assert result.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    assert result.flow.halt_step is CommitmentStep.LEDGER_VERIFICATION
    assert result.detail is not None
    assert "at-most-one" in result.detail or "capacity stage" in result.detail

    # the magnitude the flat was sized from is the projection's own recorded fill — an
    # observation, never a release (design #35 §5.2).
    held = sliced.core.ledger.outstanding_consumed_magnitude(instrument_key())
    assert held is not None
    entry_context = sliced.resolver.contexts[0]
    assert held == entry_context.outbound_quantity
