"""``NonTradeEventProcessor`` — the nontrade consumer OUTSIDE the engine (Phase 5 W5
plan §2 decision 6, lane f3).

**Applies nothing.** ``tos.nontrade`` is a decision kernel only (ADR-002-010 §1
line 19 / §10 line 217: "the Risk Capacity Ledger remains the sole authority that
reserves, commits, releases, transfers, or remaps capacity"; "the event processor
... may propose a remap but SHALL NOT update capacity independently"). This
module folds an observed non-trade event through every applicable kernel
predicate, records the sole :class:`~tos.nontrade.vocabulary.NonTradeDisposition`
producer's verdict as evidence, and reports a ``restrictive`` bool — it never
reserves, commits, releases, remaps, or writes any capacity or composite state
itself (the ``rcl`` is the sole capacity authority, ADR-002-010 §1/§10; structural
pin: ``tests/nontrade/test_no_write_port.py``).

**Latching is a different lane's job.** When a disposition is conservative
(:data:`_RESTRICTIVE_DISPOSITIONS`), this processor reports ``restrictive=True``
and a ``latch_reason`` token on :class:`NonTradeOutcome` — it does **not** call
``tos_runtime.engine.inbox.SqliteEventInbox.record_new_risk_halt`` (the public
entry point that durably latches a new-risk halt, ``engine/inbox.py:574``)
itself. This package's own structural pin (AST import scan,
``tests/nontrade/test_no_write_port.py``) forbids importing
``tos_runtime.rcl``, ``tos_runtime.engine``, ``tos_runtime.recovery``, or
``tos_runtime.transport`` at all, so the wiring from ``restrictive`` to that
entry point is left to a different lane (Phase 5 W5 plan §4, lane f4/f2) — see
this module's own docstring "Report back" note below for what that lane needs.

**Report back (missing entry points, surveyed not built here).** (1)
``record_new_risk_halt`` exists and is public
(``tos_runtime/engine/inbox.py:574``) — the wiring lane calls it directly with a
``reason`` taken from :attr:`NonTradeOutcome.latch_reason`. (2) No
"incident-candidate" reporting entry point was found on
:class:`~tos_runtime.safety.incident.IncidentService` — it only *reads* a static
policy document and reports clearance (``clear()``); it has no method to report
a new incident candidate. A ``NONTRADE_MATERIAL_CHANGE`` / restrictive-disposition
evidence entry is therefore the only "incident candidate" trace this lane can
leave; whether a future incident-candidate entry point should be added is an
operator decision (Phase 5 W5 plan §6 confirmation point 9), not this lane's.

**Required-legs configuration (M6 discipline).** ``required_legs_by_class`` is a
constructor-injected mapping, never a module-level literal: the event-class ->
applicable-leg mapping is caller policy (ADR-002-010 §9 line 183 "where
applicable"), not a nontrade or nontrade-consumer constant. A class absent from
the mapping means "we do not know what legs this class requires" — the
processor does not call :func:`~tos.nontrade.predicates.transition_envelope_complete`
at all in that case (rather than silently feeding it an empty ``frozenset``,
which the kernel predicate already treats as its own separate ∅ fail-closed
guard) and names the predicate in :attr:`NonTradeOutcome.unevaluated`.

Firewall: stdlib + ``tos.canonical`` (``CanonicalDecimal``, re-exported facts) +
``tos.nontrade`` + ``tos.venue.predicates`` (``material_change_closure`` —
consumed as an injected closure, never re-authored; ADR-002-019 owns it) +
``tos_runtime.evidence.ports`` (``EvidenceAppendPort``) +
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

from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.nontrade.observations import NonTradeObservation

__all__ = [
    "NONTRADE_DISPOSITION_KIND",
    "NONTRADE_MATERIAL_CHANGE_KIND",
    "NonTradeEventProcessor",
    "NonTradeOutcome",
]

#: This module's own runtime evidence kind constants (Phase 5 W5 plan §2
#: decision 10) — never re-exported from the kernel, which authors no evidence.
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
    """One :meth:`NonTradeEventProcessor.process` call's result.

    ``restrictive`` / ``latch_reason`` are this processor's ONLY output toward a
    new-risk latch — it never calls the latch itself (module docstring).
    """

    observation_id: str
    disposition: NonTradeDisposition
    restrictive: bool
    latch_reason: str | None
    predicate_results: Mapping[str, object]
    unevaluated: tuple[str, ...]
    material_change_closure: frozenset[str] | None
    evidence_seq: int | None


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
        evidence_recorder: EvidenceAppendPort,
        required_legs_by_class: Mapping[
            NonTradeEventClass, frozenset[CredibleTransitionLegKind]
        ],
        dep_graph_provider: (
            Callable[[], Mapping[str, frozenset[str]] | None] | None
        ) = None,
        venue_admissibility_provider: Callable[[str], str | None] | None = None,
        time_freshness_provider: Callable[[], str | None] | None = None,
    ) -> None:
        """Args:
        evidence_recorder: The durable-append seam (module docstring); a
            :class:`~tos.evidence.EvidenceAppendReceipt` proves every append.
        required_legs_by_class: The event-class -> applicable-leg-set policy
            (module docstring M6 discipline — never a literal in this module).
        dep_graph_provider: Returns the venue constraint dependency adjacency for
            :func:`~tos.venue.predicates.material_change_closure`, or ``None``
            when no dependency graph is wired yet (skips the closure + its
            evidence entirely — never a fabricated empty graph).
        venue_admissibility_provider: Returns the injected venue
            ``OrderAdmissibilityResult`` token for one instrument route key, or
            ``None`` when no venue admissibility source is wired.
        time_freshness_provider: Returns the injected time ``FreshnessVerdict``
            token, or ``None`` when no time source is wired.
        """
        self._evidence = evidence_recorder
        self._required_legs_by_class = required_legs_by_class
        self._dep_graph_provider = dep_graph_provider
        self._venue_admissibility_provider = venue_admissibility_provider
        self._time_freshness_provider = time_freshness_provider

    def process(self, obs: NonTradeObservation) -> NonTradeOutcome:
        """Fold ``obs`` through every applicable kernel predicate.

        Args:
            obs: The observed non-trade event.

        Returns:
            The :class:`NonTradeOutcome` — disposition, restrictive/latch_reason,
            the per-predicate result table, the unevaluated predicate names, the
            material-change closure (if a dependency graph was provided), and the
            durable evidence seq the disposition was recorded under.
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

        receipt = self._evidence.append(
            _disposition_payload(obs, disposition, results, unevaluated),
            kind=NONTRADE_DISPOSITION_KIND,
            record_class=NONTRADE_DISPOSITION_KIND,
        )
        closure = self._record_material_change(obs)

        return NonTradeOutcome(
            observation_id=obs.observation_id,
            disposition=disposition,
            restrictive=restrictive,
            latch_reason=latch_reason,
            predicate_results=results,
            unevaluated=tuple(unevaluated),
            material_change_closure=closure,
            evidence_seq=receipt.seq,
        )

    def _resolve_admissibility(self, obs: NonTradeObservation) -> str | None:
        """The injected venue admissibility token for ``obs``'s instrument route,
        or ``None`` when no provider is wired or no route identity is known."""
        if self._venue_admissibility_provider is None:
            return None
        key = obs.new_instrument_identity or obs.old_instrument_identity
        if key is None:
            return None
        return self._venue_admissibility_provider(key)

    def _record_material_change(
        self, obs: NonTradeObservation
    ) -> frozenset[str] | None:
        """Compute + evidence the §18 material-change closure, only when a
        dependency graph is wired (module docstring — never a fabricated empty
        graph); returns ``None`` (no evidence appended) otherwise."""
        if self._dep_graph_provider is None:
            return None
        dep_graph = self._dep_graph_provider()
        if dep_graph is None:
            return None
        closure = material_change_closure(dep_graph, obs.change_triggers)
        self._evidence.append(
            {
                "observation_id": obs.observation_id,
                "change_triggers": sorted(obs.change_triggers),
                "closure": sorted(closure),
            },
            kind=NONTRADE_MATERIAL_CHANGE_KIND,
            record_class=NONTRADE_MATERIAL_CHANGE_KIND,
        )
        return closure


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


def _disposition_payload(
    obs: NonTradeObservation,
    disposition: NonTradeDisposition,
    results: Mapping[str, object],
    unevaluated: list[str],
) -> dict[str, object]:
    """The ``NONTRADE_DISPOSITION`` evidence payload — observation identity, the
    disposition, the full per-predicate result table, and the unevaluated list."""
    rendered_results = {
        name: (value.value if hasattr(value, "value") else value)
        for name, value in results.items()
    }
    return {
        "observation_id": obs.observation_id,
        "event_class": obs.event_class.value,
        "source_label": obs.source_label,
        "disposition": disposition.value,
        "predicate_results": rendered_results,
        "unevaluated": list(unevaluated),
    }
