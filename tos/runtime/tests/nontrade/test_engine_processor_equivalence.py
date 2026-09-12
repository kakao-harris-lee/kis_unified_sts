"""Cross-implementation equivalence: the kernel engine's ``CORPORATE_ACTION`` handler
(:func:`tos.engine._corporate_action.handle_corporate_action`) reaches the SAME
:class:`~tos.nontrade.NonTradeDisposition` as :class:`~tos_runtime.nontrade.processor
.NonTradeEventProcessor` for the identical W5 lane-f3 synthetic fixtures (kernel round #3 §2 결정
1, §5 실증 (1), ``docs/plans/2026-09-12-tos-kernel-round-3-plan.md``).

**Why this matters.** Two independently-written call sites — one inside the engine
(``tos.engine._corporate_action``), one outside it (``tos_runtime.nontrade.processor``) — both
fold the SAME observed facts through the SAME kernel predicates
(:func:`~tos.nontrade.nontrade_disposition` and its supporting functions). If they ever diverged,
that would mean one of the two silently re-authored a judgement the kernel is supposed to be the
sole producer of (design #21 C1) — exactly the defect class this test exists to catch.

This is NOT a test of ``NonTradeEventProcessor`` itself (``tos/runtime/tests/nontrade
/test_processor.py`` already owns that) nor of the engine handler's own behavior in isolation
(``tos/tests/engine/test_engine_corporate_action.py`` owns that). It is purely the
cross-implementation equality proof the round's own end-condition names.

Regime tag: authoring evidence only; closes no EV.
"""

from __future__ import annotations

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine._corporate_action import handle_corporate_action
from tos.engine.records import CorporateActionPayload, InstrumentKey
from tos_runtime.nontrade import NonTradeEventProcessor
from tos_runtime.nontrade.observations import NonTradeObservation

from .conftest import FakeEvidenceRecorder
from .fixtures.synthetic_observations import (
    REQUIRED_LEGS_BY_CLASS,
    cash_dividend,
    futures_lifecycle_expiry,
    stock_split_forward,
    symbol_route_change,
)

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: The SAME two providers ``tests/nontrade/conftest.py``'s own ``admissible_provider`` /
#: ``fresh_time_provider`` fixtures supply to ``NonTradeEventProcessor`` in ``test_processor.py``
#: — reused here as bare values (not pytest fixtures — this module is not a processor-only
#: suite) so both implementations see the identical injected coordinates.
_ADMISSIBLE_TOKEN = "ADMISSIBLE"
_FRESH_TOKEN = "FRESH"


def _payload_from_observation(
    obs: NonTradeObservation, *, admissibility: str | None
) -> CorporateActionPayload:
    """Convert one W5 lane-f3 :class:`NonTradeObservation` into a kernel
    :class:`~tos.engine.records.CorporateActionPayload` carrying EXACTLY the same facts —
    the two types share the identical coordinate shape by construction (kernel round #3 §2 결정
    1's own design note), so this is a field-for-field copy, never a re-derivation."""
    required_legs = REQUIRED_LEGS_BY_CLASS.get(obs.event_class, frozenset())
    return CorporateActionPayload(
        instrument_key=InstrumentKey(account="acct-equiv", instrument="instr-equiv"),
        event=obs.to_kernel_record(),
        envelope=obs.transition_envelope,
        split_spec=obs.split_spec,
        correction=obs.correction,
        required_legs=required_legs,
        prior_correction=obs.prior_correction,
        original_retained=obs.original_retained,
        identity_transition_final=obs.identity_transition_final,
        event_is_material=obs.event_is_material,
        change_triggers=obs.change_triggers,
        earliest_credible_boundary=obs.earliest_credible_boundary,
        latest_completion_boundary=obs.latest_completion_boundary,
        source_disagreement_bounded=obs.source_disagreement_bounded,
        field_confidences=obs.field_confidences,
        venue_admissibility=admissibility,
        time_freshness=_FRESH_TOKEN,
        protective_action_may_proceed=obs.protective_action_may_proceed,
        injected_worst_intermediate_risk=obs.injected_worst_intermediate_risk,
        injected_credible_space_bounded=obs.injected_credible_space_bounded,
        injected_union_capacity_known=obs.injected_union_capacity_known,
    )


def _processor_disposition(obs: NonTradeObservation, *, admissibility: str | None):
    processor = NonTradeEventProcessor(
        FakeEvidenceRecorder(),
        REQUIRED_LEGS_BY_CLASS,
        venue_admissibility_provider=(
            None if admissibility is None else lambda _route_key: admissibility
        ),
        time_freshness_provider=lambda: _FRESH_TOKEN,
    )
    return processor.process(obs).disposition


def _engine_disposition(obs: NonTradeObservation, *, admissibility: str | None):
    payload = _payload_from_observation(obs, admissibility=admissibility)
    return handle_corporate_action(payload, scheme=_SCHEME).disposition


def test_stock_split_forward_reaches_the_same_disposition() -> None:
    obs = stock_split_forward()
    assert _processor_disposition(
        obs, admissibility=_ADMISSIBLE_TOKEN
    ) is _engine_disposition(obs, admissibility=_ADMISSIBLE_TOKEN)


def test_cash_dividend_reaches_the_same_disposition() -> None:
    obs = cash_dividend()
    assert _processor_disposition(
        obs, admissibility=_ADMISSIBLE_TOKEN
    ) is _engine_disposition(obs, admissibility=_ADMISSIBLE_TOKEN)


def test_symbol_route_change_reaches_the_same_disposition() -> None:
    obs = symbol_route_change()
    assert _processor_disposition(
        obs, admissibility=_ADMISSIBLE_TOKEN
    ) is _engine_disposition(obs, admissibility=_ADMISSIBLE_TOKEN)


def test_futures_lifecycle_expiry_reaches_the_same_disposition() -> None:
    """(module docstring's own note) This fixture deliberately supplies no admissibility
    provider — the honest "no venue admissibility source wired" case."""
    obs = futures_lifecycle_expiry()
    assert _processor_disposition(obs, admissibility=None) is _engine_disposition(
        obs, admissibility=None
    )


def test_all_four_fixtures_reach_the_expected_dispositions_on_both_sides() -> None:
    """Not just "equal to each other" but each equal to the SPECIFIC disposition its own
    fixture docstring claims (test_processor.py's own pins) — an equality that happened to hold
    at some other, unintended disposition would defeat the point."""
    from tos.nontrade import NonTradeDisposition

    cases = [
        (
            stock_split_forward(),
            _ADMISSIBLE_TOKEN,
            NonTradeDisposition.NONTRADE_ADMISSIBLE,
        ),
        (
            cash_dividend(),
            _ADMISSIBLE_TOKEN,
            NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK,
        ),
        (
            symbol_route_change(),
            _ADMISSIBLE_TOKEN,
            NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK,
        ),
        (futures_lifecycle_expiry(), None, NonTradeDisposition.NONTRADE_TRAPPED),
    ]
    for obs, admissibility, expected in cases:
        processor_result = _processor_disposition(obs, admissibility=admissibility)
        engine_result = _engine_disposition(obs, admissibility=admissibility)
        assert processor_result is expected, (
            f"{obs.observation_id}: NonTradeEventProcessor reached {processor_result}, "
            f"expected {expected}"
        )
        assert engine_result is expected, (
            f"{obs.observation_id}: the engine handler reached {engine_result}, "
            f"expected {expected}"
        )
