"""``payload_from_observation`` — the ``NonTradeObservation`` -> kernel
``CorporateActionPayload`` converter, promoted to production (TOS runtime operations wiring
plan, 2026-09-13, §2 decision 3).

This is a field-for-field copy, never a re-derivation — it was originally written, and proven
equal to the engine's own judgement, inside
``tos/runtime/tests/nontrade/test_engine_processor_equivalence.py`` (kernel round #3 §5 실증
(1)); that test now imports THIS function instead of defining its own local copy, so the
cross-implementation equivalence proof and the real
:meth:`~tos_runtime.compose._types.ComposedRuntime.observe_nontrade` caller are provably running
the identical conversion.

**Caller-resolved coordinates, never re-derived here.** ``instrument_key`` (this compose root's
single live scope — :attr:`~tos_runtime.compose.context.ComposeContextResolver.instrument_key`)
and ``required_legs`` (the ``nontrade.yaml``-loaded per-class policy — see
:meth:`~tos_runtime.nontrade.processor.NonTradeEventProcessor.required_legs_for`) are the
caller's own facts, not this observation's; ``admissibility``/``time_freshness`` mirror the SAME
two injected coordinates :class:`~tos_runtime.nontrade.processor.NonTradeEventProcessor` already
takes as provider callables — here they are plain optional tokens (never re-derived, never
defaulted to a fabricated non-``None`` value): a caller with no live source for either passes
``None``, exactly the honest "no venue admissibility / time freshness source wired" case the
kernel equivalence test's own ``futures_lifecycle_expiry`` fixture already exercises.

**No ``reference`` parameter.** :class:`~tos.engine.records.CorporateActionPayload.reference`
is always overwritten by :meth:`~tos_runtime.engine.driver.EngineDriver._stamp` the moment this
payload is enqueued through the driver (the SAME discipline every other event kind gets — the
caller-supplied reference is discarded, never trusted); a payload built by this function for the
recovery-barrier-held ``inbox.enqueue`` path (no driver, no stamping) is likewise never read for
ordering before a real driver eventually re-stamps nothing — it stays at the kernel model's own
default. Accepting a ``reference`` argument here would be dead weight in every caller.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.engine.records`` +
``tos.nontrade`` (via :class:`~tos_runtime.nontrade.observations.NonTradeObservation`'s own
fields) + ``tos_runtime.nontrade.observations`` only. No ``shared.*``. No ``tos_runtime.rcl`` /
``.engine`` / ``.recovery`` / ``.transport`` (this package's own structural pin,
``tests/nontrade/test_processor.py``'s
``test_no_forbidden_capacity_or_engine_imports_under_nontrade``) — ``tos.engine.records`` is a
KERNEL module, not ``tos_runtime.engine``, so importing it here does not trip that pin.
"""

from __future__ import annotations

from collections.abc import Mapping

from tos.engine.records import CorporateActionPayload, InstrumentKey
from tos.nontrade import CredibleTransitionLegKind, NonTradeEventClass

from tos_runtime.nontrade.observations import NonTradeObservation

__all__ = ["payload_from_observation"]


def payload_from_observation(
    obs: NonTradeObservation,
    *,
    instrument_key: InstrumentKey,
    required_legs_by_class: (
        Mapping[NonTradeEventClass, frozenset[CredibleTransitionLegKind]] | None
    ) = None,
    admissibility: str | None = None,
    time_freshness: str | None = None,
) -> CorporateActionPayload:
    """Convert ``obs`` into a kernel :class:`~tos.engine.records.CorporateActionPayload`
    carrying exactly the same facts — the two types share the identical coordinate shape by
    construction (kernel round #3 §2 결정 1's own design note), so every field ``obs`` itself
    carries is a direct copy, never a re-derivation.

    Args:
        obs: The observed non-trade event.
        instrument_key: The caller's own dispatch key for this event (this compose root's
            single live scope — never derived from ``obs``, which carries no
            :class:`~tos.engine.records.InstrumentKey` of its own).
        required_legs_by_class: The caller's ``nontrade.yaml``-loaded per-class policy mapping
            (:meth:`~tos_runtime.nontrade.processor.NonTradeEventProcessor.required_legs_for`'s
            own source) — ``obs.event_class`` is looked up in it, defaulting to an empty
            ``frozenset`` (module docstring M6 discipline: "class absent" is a caller fact, not
            fabricated here); ``None`` (no policy wired at all) is treated the same as "absent".
        admissibility: The injected venue ``OrderAdmissibilityResult`` token, or ``None`` when no
            live venue-admissibility source is wired for this caller (never fabricated).
        time_freshness: The injected time ``FreshnessVerdict`` token, or ``None`` when no live
            time-freshness source is wired.

    Returns:
        The :class:`~tos.engine.records.CorporateActionPayload`.
    """
    required_legs = (
        frozenset()
        if required_legs_by_class is None
        else required_legs_by_class.get(obs.event_class, frozenset())
    )
    return CorporateActionPayload(
        instrument_key=instrument_key,
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
        time_freshness=time_freshness,
        protective_action_may_proceed=obs.protective_action_may_proceed,
        injected_worst_intermediate_risk=obs.injected_worst_intermediate_risk,
        injected_credible_space_bounded=obs.injected_credible_space_bounded,
        injected_union_capacity_known=obs.injected_union_capacity_known,
    )
