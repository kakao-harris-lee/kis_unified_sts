"""Four synthetic :class:`~tos_runtime.nontrade.observations.NonTradeObservation`
fixtures (Phase 5 W5 plan §2 decision 6, "합성 CA 관측 픽스처 4종"): a stock split
(forward, 2:1-shaped without any hardcoded ratio — the split spec carries only
magnitudes, per ``tos.nontrade`` M2 discipline), a cash dividend, a symbol/route
change, and a LIFECYCLE futures-expiry observation (the "rollover observation"
plan §2.7 uses).

None of these is a durable event: every field is either concretely observed
(synthetic, labelled ``source_label="synthetic-fixture"``) or left ``None`` —
never a fabricated constant standing in for a fact this fixture cannot honestly
claim (module docstring of ``tos_runtime.nontrade.processor``, M6 discipline).

``REQUIRED_LEGS_BY_CLASS`` deliberately covers only
:attr:`~tos.nontrade.vocabulary.NonTradeEventClass.CORPORATE_ACTION` — the other
three fixtures below exercise the "class absent from the config -> unevaluated"
path (:mod:`tos_runtime.nontrade.processor` module docstring), which is itself
part of what this suite is proving.
"""

from __future__ import annotations

from decimal import Decimal

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.nontrade import (
    CorrectionReversalRecord,
    CredibleTransitionLegKind,
    NonTradeEventClass,
    SplitTransformationKind,
    SplitTransformationSpec,
    TransitionEnvelope,
)
from tos_runtime.nontrade import NonTradeObservation

#: The canonicalization scheme used to ``.issue()`` the one digest-bound
#: :class:`~tos.nontrade.records.CorrectionReversalRecord` this suite needs a real
#: (non-``DRAFT``) digest for (:func:`correction_pair`) — the same provisional
#: scheme the kernel's own nontrade test suite issues records with
#: (``tos/tests/nontrade/_nontrade_strategies.py``).
_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

__all__ = [
    "REQUIRED_LEGS_BY_CLASS",
    "cash_dividend",
    "correction_pair",
    "futures_lifecycle_expiry",
    "stock_split_forward",
    "symbol_route_change",
]

#: The event-class -> applicable-leg policy this suite injects into
#: :class:`~tos_runtime.nontrade.processor.NonTradeEventProcessor` (never a
#: module-level literal inside the processor itself). Only ``CORPORATE_ACTION``
#: has an entry; ``INSTRUMENT_TRADABILITY`` and ``LIFECYCLE`` are deliberately
#: absent so their fixtures exercise the "no entry -> unevaluated" path.
REQUIRED_LEGS_BY_CLASS: dict[
    NonTradeEventClass, frozenset[CredibleTransitionLegKind]
] = {
    NonTradeEventClass.CORPORATE_ACTION: frozenset(
        {
            CredibleTransitionLegKind.PRE_EVENT_POSITION_AND_ORDER,
            CredibleTransitionLegKind.POST_EVENT_QUANTITY_INSTRUMENT_MULTIPLIER_CURRENCY_CASH,
            CredibleTransitionLegKind.FRACTIONAL_QUANTITY_AND_CASH_IN_LIEU,
        }
    ),
}

#: The complete leg set every "happy path" ``CORPORATE_ACTION`` fixture below
#: declares present — exactly :data:`REQUIRED_LEGS_BY_CLASS`'s
#: ``CORPORATE_ACTION`` entry, so ``required_legs <= present_leg_set()`` holds.
_CORPORATE_ACTION_LEGS: tuple[CredibleTransitionLegKind, ...] = tuple(
    sorted(
        REQUIRED_LEGS_BY_CLASS[NonTradeEventClass.CORPORATE_ACTION],
        key=lambda leg: leg.value,
    )
)


def stock_split_forward(*, reversed_quantities: bool = False) -> NonTradeObservation:
    """(a) A forward stock split — the happy path, reaching
    ``NONTRADE_ADMISSIBLE`` (every rank-5 conjunct positively proven).

    Args:
        reversed_quantities: When ``True``, swap ``pre_quantity``/``post_quantity``
            so the declared ``FORWARD_SPLIT`` kind no longer matches the derived
            (``ATTENUATE``, ``ATTENUATE``) direction pair — the mutation this
            suite pins: :func:`~tos.nontrade.predicates.split_polarity_coherent`
            must return ``False`` and the disposition must fall to
            ``NONTRADE_BLOCK_NEW_RISK``.
    """
    pre_quantity, post_quantity = Decimal("100"), Decimal("200")
    if reversed_quantities:
        pre_quantity, post_quantity = post_quantity, pre_quantity
    split = SplitTransformationSpec(
        kind=SplitTransformationKind.FORWARD_SPLIT,
        pre_quantity=pre_quantity,
        post_quantity=post_quantity,
        pre_basis=Decimal("20"),
        post_basis=Decimal("10"),
        unit_spec="shares",
        rounding_rule="round-down",
        fractional_residual=Decimal("0"),
        cash_in_lieu=Decimal("0"),
    )
    envelope = TransitionEnvelope(
        present_legs=_CORPORATE_ACTION_LEGS,
        pre_event_exposure=Decimal("2000"),
        post_event_credible_exposure=Decimal("2000"),
    )
    return NonTradeObservation(
        observation_id="stock-split-005930-2026Q3",
        event_class=NonTradeEventClass.CORPORATE_ACTION,
        source_label="synthetic-fixture",
        event_subtype="FORWARD_SPLIT",
        announcement_time="2026-08-01T00:00:00",
        ex_time="2026-09-10T00:00:00",
        effective_time="2026-09-11T00:00:00",
        old_instrument_identity="KRX:005930",
        new_instrument_identity="KRX:005930",
        identity_transition_final=True,
        transition_envelope=envelope,
        split_spec=split,
        event_is_material=True,
        change_triggers=frozenset({"instrument:KRX:005930"}),
        earliest_credible_boundary="2026-09-10T00:00:00",
        latest_completion_boundary="2026-09-12T00:00:00",
        source_disagreement_bounded=True,
        field_confidences=frozenset({"CORROBORATED"}),
        injected_worst_intermediate_risk=Decimal("5"),
        injected_credible_space_bounded=True,
        injected_union_capacity_known=True,
    )


def cash_dividend() -> NonTradeObservation:
    """(b) A cash dividend — a complete envelope with no transformation (no
    ``split_spec``), but a positively-material event with an EMPTY trigger set:
    ``material_change_trigger_nonempty`` is ``False`` (§10 line 221 "Unknown
    materiality is material" applies equally to a *declared* ``True``), so this
    fixture reaches ``NONTRADE_BLOCK_NEW_RISK`` — restrictive, but not trapped
    (the admissibility token is still ordinary), demonstrating the materiality
    conjunct's own failure mode distinctly from the split fixture's polarity one.
    """
    envelope = TransitionEnvelope(
        present_legs=_CORPORATE_ACTION_LEGS,
        pre_event_exposure=Decimal("500"),
        post_event_credible_exposure=Decimal("500"),
    )
    return NonTradeObservation(
        observation_id="cash-dividend-005930-2026Q3",
        event_class=NonTradeEventClass.CORPORATE_ACTION,
        source_label="synthetic-fixture",
        event_subtype="CASH_DIVIDEND",
        announcement_time="2026-08-15T00:00:00",
        record_time="2026-09-01T00:00:00",
        ex_time="2026-09-05T00:00:00",
        effective_time="2026-09-05T00:00:00",
        payable_time="2026-09-20T00:00:00",
        old_instrument_identity="KRX:005930",
        new_instrument_identity="KRX:005930",
        identity_transition_final=True,
        transition_envelope=envelope,
        event_is_material=True,
        change_triggers=frozenset(),  # deliberately empty — the conjunct this pins
        earliest_credible_boundary="2026-09-04T00:00:00",
        latest_completion_boundary="2026-09-21T00:00:00",
        source_disagreement_bounded=True,
        field_confidences=frozenset({"CORROBORATED"}),
        injected_worst_intermediate_risk=Decimal("1"),
        injected_credible_space_bounded=True,
        injected_union_capacity_known=True,
    )


def cash_dividend_missing_leg() -> NonTradeObservation:
    """(b-variant) The same cash dividend, minus one required leg (leaves the
    envelope incomplete) — :func:`~tos.nontrade.predicates.transition_envelope_complete`
    must return ``False`` and the disposition must land on
    ``NONTRADE_BLOCK_NEW_RISK`` for a *different* reason than the base fixture
    (an incomplete envelope, not an empty trigger set) — reached by ALSO supplying
    a non-empty trigger set so only the envelope conjunct fails.
    """
    incomplete_legs = tuple(
        leg for leg in _CORPORATE_ACTION_LEGS if leg != _CORPORATE_ACTION_LEGS[0]
    )
    envelope = TransitionEnvelope(
        present_legs=incomplete_legs,
        pre_event_exposure=Decimal("500"),
        post_event_credible_exposure=Decimal("500"),
    )
    base = cash_dividend()
    return NonTradeObservation(
        **{
            **base.__dict__,
            "transition_envelope": envelope,
            "change_triggers": frozenset({"instrument:KRX:005930"}),
        }
    )


def symbol_route_change() -> NonTradeObservation:
    """(c) A symbol / route identity change — old and new route identities both
    present (identity transition not yet final, §12 line 248 coexistence), no
    envelope config entry for ``INSTRUMENT_TRADABILITY`` (unevaluated
    ``transition_envelope_complete``), so the envelope conjunct alone keeps this
    at ``NONTRADE_BLOCK_NEW_RISK`` even though lineage itself is preserved.
    """
    return NonTradeObservation(
        observation_id="route-change-005930-to-005931",
        event_class=NonTradeEventClass.INSTRUMENT_TRADABILITY,
        source_label="synthetic-fixture",
        event_subtype="SYMBOL_ROUTE_CHANGE",
        announcement_time="2026-09-01T00:00:00",
        effective_time="2026-09-15T00:00:00",
        old_instrument_identity="KRX:005930",
        new_instrument_identity="KRX:005931",
        identity_transition_final=False,
        event_is_material=True,
        change_triggers=frozenset({"instrument:KRX:005930", "instrument:KRX:005931"}),
        earliest_credible_boundary="2026-09-14T00:00:00",
        latest_completion_boundary="2026-09-16T00:00:00",
        source_disagreement_bounded=True,
        field_confidences=frozenset({"CORROBORATED"}),
        injected_worst_intermediate_risk=Decimal("0"),
        injected_credible_space_bounded=True,
        injected_union_capacity_known=True,
    )


def futures_lifecycle_expiry() -> NonTradeObservation:
    """(d) A LIFECYCLE futures-expiry observation — the rollover observation
    Phase 5 W5 plan §2.7 uses. Deliberately minimal: no envelope, no
    transformation, no correction, and (honestly) no venue admissibility token
    — in production the calendar owner supplies the ``EXPIRED`` session phase to
    the *venue* decision (plan §2 decision 7), which this fixture does not
    fabricate. With no ordinary admissibility token, rank 3
    (:func:`~tos.nontrade.predicates.nontrade_disposition`'s unconditional
    "no fresh exact decision => trapped") lands this at ``NONTRADE_TRAPPED`` —
    restrictive, with a ``latch_reason``.
    """
    return NonTradeObservation(
        observation_id="futures-expiry-202609-mini",
        event_class=NonTradeEventClass.LIFECYCLE,
        source_label="synthetic-fixture",
        event_subtype="EXPIRY",
        announcement_time="2026-06-12T00:00:00",
        effective_time="2026-09-11T15:45:00",
        settlement_time="2026-09-14T00:00:00",
        old_instrument_identity="KRX-FUT:202609-MINI",
        new_instrument_identity="KRX-FUT:202609-MINI",
        identity_transition_final=True,
        event_is_material=True,
        change_triggers=frozenset({"instrument:KRX-FUT:202609-MINI"}),
    )


def correction_pair() -> tuple[NonTradeObservation, NonTradeObservation]:
    """A first correction and a harmless idempotent re-apply of it, both attached
    to a fresh ``ADMINISTRATIVE_BROKER`` observation (a broker-applied fee
    correction), exercising
    :func:`~tos.nontrade.predicates.correction_reversal_idempotent` end to end:
    the first call has no prior (``APPLIED_ONCE``), the second names the first
    as its prior with identical content (``IDEMPOTENT_REPLAY``).

    Returns:
        ``(first_application, idempotent_replay)`` — two observations sharing
        one ``corrected_event_id``/``idempotency_key`` pair.
    """
    original_event_id = "admin-fee-correction-source-1"
    # Issued (not DRAFT): ``classify_record_pair`` treats a null (DRAFT) digest as
    # pre-issuance / ``NOT_COMPARABLE`` (fail-closed) — a genuine idempotent
    # re-apply needs two records that both carry the SAME concrete digest, which
    # only ``.issue()`` computes.
    correction = CorrectionReversalRecord.issue(
        scheme=_SCHEME,
        correction_id="correction-1",
        correction_generation=1,
        correction_kind="FEE_CORRECTION",
        corrected_event_id=original_event_id,
        supersedes_ref=original_event_id,
        original_observation_ref=original_event_id,
        idempotency_key="idem-admin-fee-correction-1",
    )
    first = NonTradeObservation(
        observation_id="admin-fee-correction-apply-1",
        event_class=NonTradeEventClass.ADMINISTRATIVE_BROKER,
        source_label="synthetic-fixture",
        event_subtype="FEE_CORRECTION",
        record_time="2026-09-05T00:00:00",
        correction=correction,
        prior_correction=None,
        original_retained=True,
    )
    replay = NonTradeObservation(
        observation_id="admin-fee-correction-apply-2",
        event_class=NonTradeEventClass.ADMINISTRATIVE_BROKER,
        source_label="synthetic-fixture",
        event_subtype="FEE_CORRECTION",
        record_time="2026-09-05T00:01:00",
        correction=correction,
        prior_correction=correction,
        original_retained=True,
    )
    return first, replay
