"""``NonTradeEventProcessor`` — the nontrade DRY-RUN evaluator OUTSIDE the engine (originally
Phase 5 W5 plan §2 decision 6, lane f3; narrowed to dry-run-only by the TOS runtime operations
wiring plan, 2026-09-13, §2 decision 3).

**Applies nothing, and now records nothing either.** ``tos.nontrade`` is a decision kernel only
(ADR-002-010 §1 line 19 / §10 line 217: "the Risk Capacity Ledger remains the sole authority that
reserves, commits, releases, transfers, or remaps capacity"; "the event processor ... may
propose a remap but SHALL NOT update capacity independently"). This module folds an observed
non-trade event through every applicable kernel predicate and reports the resulting
:class:`~tos.nontrade.vocabulary.NonTradeDisposition` — it never reserves, commits, releases,
remaps, or writes any capacity or composite state (the ``rcl`` is the sole capacity authority,
ADR-002-010 §1/§10; structural pin: ``tests/nontrade/test_no_write_port.py``), and, since the
runtime operations wiring plan, it no longer appends durable evidence either
(:meth:`NonTradeEventProcessor.evaluate` — the STATEFUL path is the engine now, see below).

**The engine is the ONLY stateful non-trade path.** Kernel round #3 gave the engine its own
``CORPORATE_ACTION`` handler (:func:`tos.engine._corporate_action.handle_corporate_action`,
reached through :class:`~tos_runtime.engine.driver.EngineDriver` via
:meth:`~tos_runtime.compose._types.ComposedRuntime.observe_nontrade`), which judges the SAME
disposition over the SAME kernel predicates
(``tests/nontrade/test_engine_processor_equivalence.py`` proves the two independently-written
call sites agree) and, when restrictive, latches a new-risk halt through
:func:`~tos_runtime.nontrade.latch.latch_restrictive` — the shared implementation
:mod:`tos_runtime.engine.driver` and (previously) this package's own caller both use. This class
is now a **dry-run evaluator only**: :meth:`evaluate` (renamed from ``process``, TOS runtime
operations wiring plan) returns the same outcome shape the engine path would reach, for the
``nontrade-eval`` CLI's "what would this observation judge to?" preview — it appends zero
evidence and touches zero durable state, so calling it can never itself latch anything or leave
a trace, unlike the engine path.

**Required-legs configuration (M6 discipline).** ``required_legs_by_class`` is a
constructor-injected mapping, never a module-level literal: the event-class ->
applicable-leg mapping is caller policy (ADR-002-010 §9 line 183 "where
applicable"), not a nontrade or nontrade-consumer constant. A class absent from
the mapping means "we do not know what legs this class requires" — the
processor does not call :func:`~tos.nontrade.predicates.transition_envelope_complete`
at all in that case (rather than silently feeding it an empty ``frozenset``,
which the kernel predicate already treats as its own separate ∅ fail-closed
guard) and names the predicate in :attr:`NonTradeOutcome.unevaluated`. The SAME mapping is also
exposed to the engine path via :meth:`NonTradeEventProcessor.required_legs_for`, so
:mod:`tos_runtime.nontrade.convert`'s caller resolves the identical per-class policy rather than
loading ``nontrade.yaml`` a second time.

Firewall: stdlib + ``tos.canonical`` (``CanonicalDecimal``, re-exported facts) +
``tos.nontrade`` + ``tos.venue.predicates`` (``material_change_closure`` —
consumed as an injected closure, never re-authored; ADR-002-019 owns it) +
``tos_runtime.nontrade.observations`` only. No ``shared.*``. No
``tos_runtime.rcl`` / ``.engine`` / ``.recovery`` / ``.transport`` (this
package's own structural pin).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from tos.canonical import CanonicalDecimal
from tos.nontrade import (
    CorrectionReversalOutcome,
    CredibleTransitionLegKind,
    NonTradeDisposition,
    NonTradeEventClass,
    correction_reversal_idempotent,
    effective_window_blocks_new_risk,
    favorable_netting_absent,
    instrument_lineage_preserved,
    material_change_trigger_nonempty,
    nontrade_authority_effect_all_false,
    nontrade_disposition,
    split_polarity_coherent,
    transformation_residual_conservative,
    transformation_units_and_rounding_explicit,
    transition_envelope_complete,
)
from tos.venue.predicates import material_change_closure

from tos_runtime.nontrade.observations import NonTradeObservation

__all__ = [
    "NONTRADE_DISPOSITION_KIND",
    "NONTRADE_MATERIAL_CHANGE_KIND",
    "NonTradeEventProcessor",
    "NonTradeOutcome",
]

#: Historical evidence-kind labels (Phase 5 W5 plan §2 decision 10) — this dry-run evaluator no
#: longer appends either (TOS runtime operations wiring plan §2 decision 3: the engine path is
#: the only stateful one now); kept as exported vocabulary tokens only, e.g. for the
#: ``nontrade-eval`` CLI's own output labeling, never fed to an ``append()`` call in this module.
NONTRADE_DISPOSITION_KIND = "NONTRADE_DISPOSITION"
NONTRADE_MATERIAL_CHANGE_KIND = "NONTRADE_MATERIAL_CHANGE"

#: The most conservative :class:`~tos.nontrade.vocabulary.NonTradeDisposition`
#: members — every member except ``NONTRADE_ADMISSIBLE`` (``vocabulary.py:412-415``
#: prose total order: ``CONFLICTED > QUARANTINED_UNKNOWN > TRAPPED >
#: BLOCK_NEW_RISK > ADMISSIBLE``; only ``ADMISSIBLE`` "releases" ordinary new
#: risk, §6 line 144). The kernel exposes no runtime order/comparison object for
#: this enum (the order is prose-only in the docstring), so the four
#: non-``ADMISSIBLE`` members are listed explicitly here rather than derived.
_RESTRICTIVE_DISPOSITIONS: frozenset[NonTradeDisposition] = frozenset(
    {
        NonTradeDisposition.NONTRADE_CONFLICTED,
        NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN,
        NonTradeDisposition.NONTRADE_TRAPPED,
        NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK,
    }
)

#: Predicate names this processor may skip calling (never a fabricated value);
#: the exact set :attr:`NonTradeOutcome.unevaluated` draws its members from.
_TRANSFORMATION_PREDICATES: tuple[str, ...] = (
    "split_polarity_coherent",
    "transformation_units_and_rounding_explicit",
    "transformation_residual_conservative",
)


@dataclass(frozen=True)
class NonTradeOutcome:
    """One non-trade observation's judged outcome — either
    :meth:`NonTradeEventProcessor.evaluate`'s dry-run result, or
    :meth:`~tos_runtime.compose._types.ComposedRuntime.observe_nontrade`'s engine-path result
    (TOS runtime operations wiring plan §2 decision 3 — the runtime dataclass shape is shared by
    both callers; ``observe_nontrade`` maps the kernel's own
    :class:`~tos.engine.records.NonTradeOutcome` onto this same shape).

    ``restrictive`` / ``latch_reason`` are this outcome's own report toward a new-risk latch —
    NEITHER this class nor :meth:`NonTradeEventProcessor.evaluate` ever calls the latch itself;
    only the engine path (:mod:`tos_runtime.engine.driver`, via
    :func:`~tos_runtime.nontrade.latch.latch_restrictive`) does.
    """

    observation_id: str
    #: ``None`` only when :attr:`queued` is ``True`` (the recovery-barrier-held case — the
    #: observation was durably enqueued but not yet judged by anything; never a fabricated
    #: disposition standing in for "we do not know yet").
    disposition: NonTradeDisposition | None
    restrictive: bool
    latch_reason: str | None
    predicate_results: Mapping[str, object]
    unevaluated: tuple[str, ...]
    material_change_closure: frozenset[str] | None
    #: The durable evidence row this specific disposition was recorded under — ``None`` for a
    #: dry-run :meth:`NonTradeEventProcessor.evaluate` call (records nothing, module docstring)
    #: and for a queued (:attr:`queued` ``True``) observation (nothing has been judged yet); a
    #: real seq (the engine's own ``EVENT_CONSUMED`` receipt) only for the engine path.
    evidence_seq: int | None
    #: ``True`` iff the TOS Phase 5 W1 recovery barrier was holding
    #: (:attr:`~tos_runtime.compose._types.ComposedRuntime.driver` is ``None``) when
    #: ``observe_nontrade`` was called: the observation was durably enqueued
    #: (``NONTRADE_QUEUED_UNTIL_RECOVERY`` evidence) but not judged — every other field above
    #: stays at its own honest "nothing known yet" default. Always ``False`` for
    #: :meth:`NonTradeEventProcessor.evaluate` (a dry-run call is never queued — it either
    #: returns immediately or does not run at all).
    queued: bool = False


def _evaluate_envelope(
    obs: NonTradeObservation,
    required_legs_by_class: Mapping[
        NonTradeEventClass, frozenset[CredibleTransitionLegKind]
    ],
) -> tuple[bool, bool, list[str]]:
    """Evaluate the two always-applicable §9 envelope conjuncts.

    ``favorable_netting_absent`` is always called (it is structurally defined for
    a ``None`` envelope, returning ``False`` — an honest evaluated answer, not a
    missing one). ``transition_envelope_complete`` is skipped, and named
    unevaluated, only when the caller's ``required_legs_by_class`` mapping has no
    entry for this observation's event class (module docstring M6 discipline).

    Returns:
        ``(envelope_complete, netting_absent, unevaluated_names)``.
    """
    unevaluated: list[str] = []
    required_legs = required_legs_by_class.get(obs.event_class)
    if required_legs is None:
        unevaluated.append("transition_envelope_complete")
        envelope_complete = False
    else:
        envelope_complete = transition_envelope_complete(
            obs.transition_envelope, required_legs
        )
    netting_absent = favorable_netting_absent(obs.transition_envelope)
    return envelope_complete, netting_absent, unevaluated


def _evaluate_transformation(
    obs: NonTradeObservation,
) -> tuple[bool | None, bool | None, bool | None, list[str]]:
    """Evaluate the §11 split/transformation triad — applicable iff a
    ``split_spec`` accompanies the event (``nontrade_disposition``'s own
    "no transformation accompanies the event" ``None`` convention); absent, the
    triad is skipped and named unevaluated rather than fed a fabricated value.
    """
    if obs.split_spec is None:
        return None, None, None, list(_TRANSFORMATION_PREDICATES)
    return (
        split_polarity_coherent(obs.split_spec),
        transformation_units_and_rounding_explicit(obs.split_spec),
        transformation_residual_conservative(obs.split_spec),
        [],
    )


def _evaluate_correction(
    obs: NonTradeObservation,
) -> tuple[CorrectionReversalOutcome | None, list[str]]:
    """Evaluate §10/§16 correction idempotency — applicable iff a ``correction``
    accompanies the event; absent, skipped and named unevaluated."""
    if obs.correction is None:
        return None, ["correction_reversal_idempotent"]
    outcome = correction_reversal_idempotent(
        obs.correction, obs.prior_correction, obs.original_retained
    )
    return outcome, []


class NonTradeEventProcessor:
    """Folds one :class:`NonTradeObservation` through every applicable kernel
    predicate and records the resulting
    :class:`~tos.nontrade.vocabulary.NonTradeDisposition` as evidence.

    Verdict authorship is forbidden here (Phase 5 plan §2 decision 1 (b), the
    discipline every safety-mesh owner in this runtime already follows): every
    boolean this class produces is a direct kernel-predicate return; the only
    judgement this class makes of its own is which
    :class:`~tos.nontrade.vocabulary.NonTradeDisposition` members count as
    ``restrictive`` (:data:`_RESTRICTIVE_DISPOSITIONS`, transcribed from the
    kernel's own prose total order, never re-decided).
    """

    def __init__(
        self,
        required_legs_by_class: Mapping[
            NonTradeEventClass, frozenset[CredibleTransitionLegKind]
        ],
        dep_graph_provider: (
            Callable[[], Mapping[str, frozenset[str]] | None] | None
        ) = None,
        venue_admissibility_provider: Callable[[str], str | None] | None = None,
        time_freshness_provider: Callable[[], str | None] | None = None,
        *,
        evidence_recorder: (
            object | None
        ) = None,  # noqa: ARG002 -- transitional, see below
    ) -> None:
        """Args:
        required_legs_by_class: The event-class -> applicable-leg-set policy
            (module docstring M6 discipline — never a literal in this module).
        dep_graph_provider: Returns the venue constraint dependency adjacency for
            :func:`~tos.venue.predicates.material_change_closure`, or ``None``
            when no dependency graph is wired yet (skips the closure entirely —
            never a fabricated empty graph).
        venue_admissibility_provider: Returns the injected venue
            ``OrderAdmissibilityResult`` token for one instrument route key, or
            ``None`` when no venue admissibility source is wired.
        time_freshness_provider: Returns the injected time ``FreshnessVerdict``
            token, or ``None`` when no time source is wired.
        evidence_recorder: **Transitional, ignored.** The old evidence-append seam —
            accepted-but-unused only so :mod:`tos_runtime.compose._session_wiring`'s
            still-unrerouted ``build_nontrade_processor`` (this same runtime operations wiring
            wave's own next commit rewires it) keeps constructing this class without a
            mid-wave TypeError. Removed the moment that caller stops passing it.
        """
        self._required_legs_by_class = required_legs_by_class
        self._dep_graph_provider = dep_graph_provider
        self._venue_admissibility_provider = venue_admissibility_provider
        self._time_freshness_provider = time_freshness_provider

    def required_legs_for(
        self, event_class: NonTradeEventClass
    ) -> frozenset[CredibleTransitionLegKind]:
        """The configured required-leg set for ``event_class``, or an empty ``frozenset`` when
        this class has no entry in the caller's policy mapping (module docstring M6 discipline).

        Exposed so the engine path
        (:mod:`tos_runtime.nontrade.convert`, via
        :meth:`~tos_runtime.compose._types.ComposedRuntime.observe_nontrade`) resolves the SAME
        per-class policy this dry-run evaluator uses, rather than loading ``nontrade.yaml`` a
        second time.
        """
        return self._required_legs_by_class.get(event_class, frozenset())

    def evaluate(self, obs: NonTradeObservation) -> NonTradeOutcome:
        """Fold ``obs`` through every applicable kernel predicate — a DRY RUN: records no
        evidence and touches no durable state (module docstring; renamed from ``process`` by the
        TOS runtime operations wiring plan §2 decision 3, when this became the ``nontrade-eval``
        CLI's preview-only evaluator).

        Args:
            obs: The observed non-trade event.

        Returns:
            The :class:`NonTradeOutcome` — disposition, restrictive/latch_reason, the
            per-predicate result table, the unevaluated predicate names, and the material-change
            closure (if a dependency graph was provided). :attr:`~NonTradeOutcome.evidence_seq`
            is always ``None`` (dry run) and :attr:`~NonTradeOutcome.queued` is always ``False``.
        """
        record = obs.to_kernel_record()
        unevaluated: list[str] = []
        results: dict[str, object] = {}

        envelope_complete, netting_absent, envelope_unevaluated = _evaluate_envelope(
            obs, self._required_legs_by_class
        )
        unevaluated.extend(envelope_unevaluated)
        results["transition_envelope_complete"] = envelope_complete
        results["favorable_netting_absent"] = netting_absent

        polarity, units_explicit, residual, transform_unevaluated = (
            _evaluate_transformation(obs)
        )
        unevaluated.extend(transform_unevaluated)
        results["split_polarity_coherent"] = polarity
        results["transformation_units_and_rounding_explicit"] = units_explicit
        results["transformation_residual_conservative"] = residual

        correction_outcome, correction_unevaluated = _evaluate_correction(obs)
        unevaluated.extend(correction_unevaluated)
        results["correction_reversal_idempotent"] = correction_outcome

        admissibility = self._resolve_admissibility(obs)
        lineage_preserved = instrument_lineage_preserved(
            obs.old_instrument_identity,
            obs.new_instrument_identity,
            admissibility,
            obs.protective_action_may_proceed,
            obs.identity_transition_final,
        )
        results["instrument_lineage_preserved"] = lineage_preserved

        time_freshness = (
            self._time_freshness_provider() if self._time_freshness_provider else None
        )
        window_blocks = effective_window_blocks_new_risk(
            obs.earliest_credible_boundary,
            obs.latest_completion_boundary,
            time_freshness,
            obs.source_disagreement_bounded,
        )
        results["effective_window_blocks_new_risk"] = window_blocks

        triggers_present = material_change_trigger_nonempty(
            obs.event_is_material, obs.change_triggers
        )
        results["material_change_trigger_nonempty"] = triggers_present
        results["nontrade_authority_effect_all_false"] = (
            nontrade_authority_effect_all_false(record.authority_effect)
        )

        disposition = _fold_disposition(
            obs,
            envelope_complete=envelope_complete,
            netting_absent=netting_absent,
            polarity_coherent=polarity,
            units_and_rounding_explicit=units_explicit,
            residual_conservative=residual,
            correction_outcome=correction_outcome,
            lineage_preserved=lineage_preserved,
            effective_window_blocks=window_blocks,
            material_change_triggers_present=triggers_present,
            admissibility=admissibility,
        )
        restrictive = disposition in _RESTRICTIVE_DISPOSITIONS
        latch_reason = disposition.value if restrictive else None
        closure = self._material_change_closure(obs)

        return NonTradeOutcome(
            observation_id=obs.observation_id,
            disposition=disposition,
            restrictive=restrictive,
            latch_reason=latch_reason,
            predicate_results=results,
            unevaluated=tuple(unevaluated),
            material_change_closure=closure,
            evidence_seq=None,
            queued=False,
        )

    def process(self, obs: NonTradeObservation) -> NonTradeOutcome:
        """**Transitional alias for :meth:`evaluate` — removed the moment
        :mod:`tos_runtime.compose._types`'s ``observe_nontrade`` stops calling it** (this same
        runtime operations wiring wave's own next commit reroutes that caller through the
        engine). Kept only so the currently-still-wired legacy path does not break mid-wave;
        never call this from new code — call :meth:`evaluate` directly."""
        return self.evaluate(obs)

    def _resolve_admissibility(self, obs: NonTradeObservation) -> str | None:
        """The injected venue admissibility token for ``obs``'s instrument route,
        or ``None`` when no provider is wired or no route identity is known."""
        if self._venue_admissibility_provider is None:
            return None
        key = obs.new_instrument_identity or obs.old_instrument_identity
        if key is None:
            return None
        return self._venue_admissibility_provider(key)

    def _material_change_closure(
        self, obs: NonTradeObservation
    ) -> frozenset[str] | None:
        """Compute the §18 material-change closure, only when a dependency graph is wired
        (module docstring — never a fabricated empty graph); returns ``None`` otherwise. Records
        no evidence (dry-run evaluator, module docstring) — unlike this method's pre-runtime-
        operations-wiring-plan predecessor, ``_record_material_change``."""
        if self._dep_graph_provider is None:
            return None
        dep_graph = self._dep_graph_provider()
        if dep_graph is None:
            return None
        return material_change_closure(dep_graph, obs.change_triggers)


def _fold_disposition(
    obs: NonTradeObservation,
    *,
    envelope_complete: bool,
    netting_absent: bool,
    polarity_coherent: bool | None,
    units_and_rounding_explicit: bool | None,
    residual_conservative: bool | None,
    correction_outcome: CorrectionReversalOutcome | None,
    lineage_preserved: bool | None,
    effective_window_blocks: bool | None,
    material_change_triggers_present: bool | None,
    admissibility: str | None,
) -> NonTradeDisposition:
    """Call the 16-keyword :func:`~tos.nontrade.predicates.nontrade_disposition`
    — split out so ``process()`` stays a readable orchestration, not a
    16-argument call site (task discipline: build the call in a helper). Typed
    (rather than a ``**dict[str, object]`` unpack) so mypy checks every one of
    the 16 positions against the kernel's own heterogeneous signature.
    """
    worst_risk: CanonicalDecimal | None = obs.injected_worst_intermediate_risk
    return nontrade_disposition(
        envelope_complete=envelope_complete,
        netting_absent=netting_absent,
        polarity_coherent=polarity_coherent,
        units_and_rounding_explicit=units_and_rounding_explicit,
        residual_conservative=residual_conservative,
        correction_outcome=correction_outcome,
        lineage_preserved=lineage_preserved,
        effective_window_blocks=effective_window_blocks,
        material_change_triggers_present=material_change_triggers_present,
        event_is_material=obs.event_is_material,
        field_confidences=obs.field_confidences,
        admissibility=admissibility,
        protective_action_may_proceed=obs.protective_action_may_proceed,
        injected_worst_intermediate_risk=worst_risk,
        injected_credible_space_bounded=obs.injected_credible_space_bounded,
        injected_union_capacity_known=obs.injected_union_capacity_known,
    )
