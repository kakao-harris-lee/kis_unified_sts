"""``handle_corporate_action`` — the ``CORPORATE_ACTION`` event handler's body (kernel round #3
§2 결정 1/2, ``docs/plans/2026-09-12-tos-kernel-round-3-plan.md``), factored out of
``engine/core.py`` (size-budget discipline; mirrors the ``egressgw/mesh.py`` /
``egressgw/venuefacts.py`` separation pattern from kernel rounds #2/#3).

**Judges and proposes only — touches no ledger, no projection, no latch.** This module calls
:func:`tos.nontrade.nontrade_disposition` (the sole producer, design #21 C1) over its full 16
kwargs, folds the result into a :class:`~tos.engine.records.NonTradeOutcome`, and returns it —
nothing here calls :class:`~tos.engine.state.ProvisionalReservationLedger`, nothing here touches
orthostate, and nothing here mutates capacity (ADR-002-010 §10 line 217 "the event processor ...
may propose a remap but SHALL NOT update capacity independently"). ``tos/tests/engine/test_
engine_corporate_action.py`` pins this structurally by AST-scanning this module's own source for
ledger/projection method-call tokens.

**Same shape as the W5 lane-f3 runtime consumer, on purpose.** :class:`~tos.engine.records
.CorporateActionPayload` carries the exact same injected-coordinate set
:class:`~tos_runtime.nontrade.observations.NonTradeObservation` already does (Phase 5 W5 plan §2
decision 6) — sibling-owned facts (are/rcl/recon/venue/time) this kernel round does not derive,
but that ANY caller can honestly supply, same as that runtime lane's own fixtures already do.
This module therefore mirrors :mod:`tos_runtime.nontrade.processor`'s own conditional-evaluation
structure (skip the transformation triad when no ``split_spec`` accompanies the event; skip
correction idempotency when no ``correction`` does) — the SAME kernel predicates, called the SAME
way, so the two independently-written call sites reach the SAME disposition for the same facts
(``tos/runtime/tests/nontrade/test_engine_processor_equivalence.py`` proves this against the W5
lane's own four synthetic fixtures).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3) — this module additionally
consumes ``tos.nontrade`` (engine→nontrade is a newly-opened, one-way-safe edge: ``tos.nontrade``
holds sibling edge 0 and cannot, and structurally cannot without breaking its own ratified
closure, import ``tos.engine`` back — the same one-way argument
``engine/orthostate_projection.py`` already established for ``tos.orthostate``).
"""

from __future__ import annotations

from typing import NamedTuple

from tos.engine._base import CanonicalizationScheme
from tos.engine.records import CorporateActionPayload, NonTradeOutcome
from tos.nontrade import (
    CorrectionReversalOutcome,
    NonTradeDisposition,
    correction_reversal_idempotent,
    effective_window_blocks_new_risk,
    favorable_netting_absent,
    instrument_lineage_preserved,
    material_change_trigger_nonempty,
    nontrade_disposition,
    split_polarity_coherent,
    transformation_residual_conservative,
    transformation_units_and_rounding_explicit,
    transition_envelope_complete,
)
from tos.rcl import TransitionCause

__all__ = [
    "RESTRICTIVE_DISPOSITIONS",
    "handle_corporate_action",
]

#: The 4 non-``NONTRADE_ADMISSIBLE`` members (design #21's own total-order ranking) —
#: :attr:`~tos.engine.records.NonTradeOutcome.restrictive` is ``True`` for exactly these four.
RESTRICTIVE_DISPOSITIONS: frozenset[NonTradeDisposition] = frozenset(
    {
        NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK,
        NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN,
        NonTradeDisposition.NONTRADE_TRAPPED,
        NonTradeDisposition.NONTRADE_CONFLICTED,
    }
)


def _evaluate_transformation_triad(
    payload: CorporateActionPayload,
) -> tuple[bool | None, bool | None, bool | None, bool]:
    """The §11 split/transformation triad — applicable iff ``split_spec`` accompanies the event
    (``nontrade_disposition``'s own "no transformation accompanies the event" ``None``
    convention); each predicate returns a plain ``bool`` for a ``None`` spec (a *failed*
    transformation, not an *absent* one), so this gate must be applied by the CALLER rather than
    forwarding that ``False`` through as if a transformation were present and incoherent (mirrors
    :mod:`tos_runtime.nontrade.processor`'s own ``_evaluate_transformation``).

    Returns:
        ``(polarity_coherent, units_and_rounding_explicit, residual_conservative, present)``.
    """
    if payload.split_spec is None:
        return None, None, None, False
    return (
        split_polarity_coherent(payload.split_spec),
        transformation_units_and_rounding_explicit(payload.split_spec),
        transformation_residual_conservative(payload.split_spec),
        True,
    )


def _build_predicate_results(
    payload: CorporateActionPayload,
    *,
    envelope_complete: bool,
    netting_absent: bool,
    polarity_coherent: bool | None,
    units_and_rounding_explicit: bool | None,
    residual_conservative: bool | None,
    correction_outcome_value: str | None,
    lineage_preserved: bool,
    effective_window_blocks: bool,
    material_change_triggers_present: bool,
) -> dict[str, bool | str | None]:
    """The full per-predicate result table (size-budget discipline: factored out of
    :func:`handle_corporate_action`)."""
    return {
        "envelope_complete": envelope_complete,
        "netting_absent": netting_absent,
        "polarity_coherent": polarity_coherent,
        "units_and_rounding_explicit": units_and_rounding_explicit,
        "residual_conservative": residual_conservative,
        "correction_outcome": correction_outcome_value,
        "lineage_preserved": lineage_preserved,
        "effective_window_blocks": effective_window_blocks,
        "material_change_triggers_present": material_change_triggers_present,
        "event_is_material": payload.event_is_material,
        "field_confidences": ",".join(sorted(payload.field_confidences)),
        "admissibility": payload.venue_admissibility,
        "protective_action_may_proceed": payload.protective_action_may_proceed,
        "injected_worst_intermediate_risk": (
            None
            if payload.injected_worst_intermediate_risk is None
            else str(payload.injected_worst_intermediate_risk)
        ),
        "injected_credible_space_bounded": payload.injected_credible_space_bounded,
        "injected_union_capacity_known": payload.injected_union_capacity_known,
    }


def _unevaluated_names(
    payload: CorporateActionPayload, *, transformation_present: bool
) -> tuple[str, ...]:
    """The kernel predicate names skipped for THIS payload (mirrors
    :mod:`tos_runtime.nontrade.processor`'s own conditional-evaluation bookkeeping)."""
    names: list[str] = []
    if not transformation_present:
        names.extend(
            [
                "split_polarity_coherent",
                "transformation_units_and_rounding_explicit",
                "transformation_residual_conservative",
            ]
        )
    if payload.correction is None:
        names.append("correction_reversal_idempotent")
    return tuple(names)


class _CorporateActionFacts(NamedTuple):
    """The per-predicate judgments for one payload, ahead of folding into a disposition
    (size-budget discipline: factored out of :func:`handle_corporate_action`)."""

    envelope_complete: bool
    netting_absent: bool
    polarity_coherent: bool | None
    units_and_rounding_explicit: bool | None
    residual_conservative: bool | None
    transformation_present: bool
    correction_outcome: CorrectionReversalOutcome | None
    lineage_preserved: bool
    effective_window_blocks: bool
    material_change_triggers_present: bool


def _evaluate_facts(payload: CorporateActionPayload) -> _CorporateActionFacts:
    """Run every kernel predicate this payload's coordinates can reach, in isolation from the
    disposition fold itself (size-budget discipline: factored out of
    :func:`handle_corporate_action`)."""
    envelope_complete = transition_envelope_complete(
        payload.envelope, payload.required_legs
    )
    netting_absent = favorable_netting_absent(payload.envelope)
    (
        polarity_coherent,
        units_and_rounding_explicit,
        residual_conservative,
        transformation_present,
    ) = _evaluate_transformation_triad(payload)
    correction_outcome = (
        correction_reversal_idempotent(
            payload.correction, payload.prior_correction, payload.original_retained
        )
        if payload.correction is not None
        else None
    )
    lineage_preserved = instrument_lineage_preserved(
        payload.event.old_instrument_identity,
        payload.event.new_instrument_identity,
        payload.venue_admissibility,
        payload.protective_action_may_proceed,
        payload.identity_transition_final,
    )
    effective_window_blocks = effective_window_blocks_new_risk(
        payload.earliest_credible_boundary,
        payload.latest_completion_boundary,
        payload.time_freshness,
        payload.source_disagreement_bounded,
    )
    material_change_triggers_present = material_change_trigger_nonempty(
        payload.event_is_material, payload.change_triggers
    )
    return _CorporateActionFacts(
        envelope_complete=envelope_complete,
        netting_absent=netting_absent,
        polarity_coherent=polarity_coherent,
        units_and_rounding_explicit=units_and_rounding_explicit,
        residual_conservative=residual_conservative,
        transformation_present=transformation_present,
        correction_outcome=correction_outcome,
        lineage_preserved=lineage_preserved,
        effective_window_blocks=effective_window_blocks,
        material_change_triggers_present=material_change_triggers_present,
    )


def _fold_disposition(
    payload: CorporateActionPayload, facts: _CorporateActionFacts
) -> NonTradeDisposition:
    """The sole call into :func:`tos.nontrade.nontrade_disposition` (design #21 C1) — factored
    out of :func:`handle_corporate_action` for size-budget discipline."""
    return nontrade_disposition(
        envelope_complete=facts.envelope_complete,
        netting_absent=facts.netting_absent,
        polarity_coherent=facts.polarity_coherent,
        units_and_rounding_explicit=facts.units_and_rounding_explicit,
        residual_conservative=facts.residual_conservative,
        correction_outcome=facts.correction_outcome,
        lineage_preserved=facts.lineage_preserved,
        effective_window_blocks=facts.effective_window_blocks,
        material_change_triggers_present=facts.material_change_triggers_present,
        event_is_material=payload.event_is_material,
        field_confidences=payload.field_confidences,
        admissibility=payload.venue_admissibility,
        protective_action_may_proceed=payload.protective_action_may_proceed,
        injected_worst_intermediate_risk=payload.injected_worst_intermediate_risk,
        injected_credible_space_bounded=payload.injected_credible_space_bounded,
        injected_union_capacity_known=payload.injected_union_capacity_known,
    )


def _finalize_outcome(
    payload: CorporateActionPayload,
    facts: _CorporateActionFacts,
    disposition: NonTradeDisposition,
    *,
    scheme: CanonicalizationScheme,
) -> NonTradeOutcome:
    """Fold a disposition and its supporting facts into the returned
    :class:`~tos.engine.records.NonTradeOutcome` (size-budget discipline: factored out of
    :func:`handle_corporate_action`)."""
    # ★ A proposal only — the RCL alone may act on this cause token (ADR-002-010 §10 line 217).
    capacity_remap_proposal = (
        TransitionCause.RECOGNIZED_EXTERNAL_CHANGE
        if disposition is NonTradeDisposition.NONTRADE_ADMISSIBLE
        and payload.envelope is not None
        else None
    )
    predicate_results = _build_predicate_results(
        payload,
        envelope_complete=facts.envelope_complete,
        netting_absent=facts.netting_absent,
        polarity_coherent=facts.polarity_coherent,
        units_and_rounding_explicit=facts.units_and_rounding_explicit,
        residual_conservative=facts.residual_conservative,
        correction_outcome_value=(
            None if facts.correction_outcome is None else facts.correction_outcome.value
        ),
        lineage_preserved=facts.lineage_preserved,
        effective_window_blocks=facts.effective_window_blocks,
        material_change_triggers_present=facts.material_change_triggers_present,
    )
    outcome_digest = scheme.compute_digest(
        {
            "disposition": disposition.value,
            "capacity_remap_proposal": (
                None
                if capacity_remap_proposal is None
                else capacity_remap_proposal.value
            ),
            "predicate_results": dict(sorted(predicate_results.items())),
        }
    )
    return NonTradeOutcome(
        disposition=disposition,
        predicate_results=predicate_results,
        unevaluated=_unevaluated_names(
            payload, transformation_present=facts.transformation_present
        ),
        capacity_remap_proposal=capacity_remap_proposal,
        restrictive=disposition in RESTRICTIVE_DISPOSITIONS,
        outcome_digest=outcome_digest,
    )


def handle_corporate_action(
    payload: CorporateActionPayload, *, scheme: CanonicalizationScheme
) -> NonTradeOutcome:
    """Judge one ``CORPORATE_ACTION`` payload and propose (never apply) a capacity remap cause.

    Args:
        payload: The re-injected corporate-action payload.
        scheme: The injected canonicalization scheme, for the returned outcome's own digest.

    Returns:
        The :class:`~tos.engine.records.NonTradeOutcome`.
    """
    facts = _evaluate_facts(payload)
    disposition = _fold_disposition(payload, facts)
    return _finalize_outcome(payload, facts, disposition, scheme=scheme)
