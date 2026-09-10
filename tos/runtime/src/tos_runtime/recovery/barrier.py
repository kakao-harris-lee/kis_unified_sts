"""``RecoveryBarrier`` — the boot-time recovery verdict (TOS Phase 5 W1; plan §2 decision 2:
"복구는 부팅 전 장벽").

**The kernel does the judging, this module only observes and folds.** Every fact in
:class:`~tos_runtime.recovery.inputs.RecoveryInputs` is a structural observation this runtime
already durably owns (see that module's own docstring for the source of each field). This module
turns those observations into six :class:`~tos.sbr.records.RecoveryObligation` records — the
runtime is the "owning sibling" that OBSERVES each fact (design #17 §3.5's own division of
labour: SBR folds, it does not re-derive), never the component that decides what counts as
closure — and hands the whole set to the kernel's own
:func:`tos.sbr.predicates.obligation_graph_closed` for the actual judgement (never re-authored
here). The verdict is the kernel's own :class:`~tos.sbr.vocabulary.ReadinessVerdict` —
``READY`` only when the kernel's graph-closure predicate says so, ``NOT_READY`` otherwise; this
module never invents a third value or a "positive by default" branch.

**Why ``ReadinessVerdict`` and not a runtime-invented ``RESUME_CONSERVATIVE`` literal.** The
Phase 5 plan (§2 decision 2) names the target state ``RESUME_CONSERVATIVE`` in prose, annotated
"(커널 sbr 어휘)" — but no such literal exists anywhere in :mod:`tos.sbr` (grepped directly: the
closest kernel vocabulary is :class:`~tos.sbr.vocabulary.ReadinessVerdict`'s own ``READY``, the
positive resume value :func:`tos.sbr.predicates.obligation_graph_closed` can actually produce).
Inventing a fifth barrier-state member here would mean authoring a NEW kernel-shaped value
outside the kernel (exactly what design #17's own truthy-sentinel discipline exists to prevent —
see :mod:`tos.sbr.vocabulary`'s own module docstring). This module therefore uses
``ReadinessVerdict.READY`` as that resume value and records the discrepancy here rather than
silently reinterpreting the plan's prose.

**Truthy-sentinel discipline preserved.** :class:`~tos.sbr.vocabulary.ReadinessVerdict` is
truthy-untestable (``bool()`` raises) — this module never writes ``if verdict:``; every gate is
the explicit ``verdict is ReadinessVerdict.READY`` identity check.

**Authority separation, defence in depth.** Every verdict this module produces carries an
all-false :class:`~tos.sbr.records.RecoveryAuthorityEffect` and is re-checked with
:func:`tos.sbr.predicates.recovery_authority_separated` before being returned — a validated
``RecoveryAuthorityEffect`` is unconstructable with any ``True`` flag (SBR-INV-003), so this is
the redundant, load-bearing "never trust an unvalidated block" check that predicate's own
docstring calls for. :func:`tos.sbr.predicates.recovery_completion_revives_nothing` is also
called (unconditionally ``True``) purely to record, in this module's own call graph, that no
input here is treated as reviving any prior authority.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass

from tos.sbr.predicates import (
    obligation_graph_closed,
    recovery_authority_separated,
    recovery_completion_revives_nothing,
)
from tos.sbr.records import RecoveryAuthorityEffect, RecoveryObligation
from tos.sbr.vocabulary import ObligationResult, ReadinessVerdict

from tos_runtime.recovery.inputs import RecoveryInputs
from tos_runtime.recovery.reconciliation import RECON_UNAVAILABLE, RECONCILED

__all__ = ["RECONCILED", "RECON_UNAVAILABLE", "RecoveryVerdict", "RecoveryBarrier"]

_OBLIGATION_REPLAY_IDENTICAL = "PHASE5_W1_REPLAY_VERDICT_IDENTICAL"
_OBLIGATION_NO_POSSIBLY_LIVE = "PHASE5_W1_NO_POSSIBLY_LIVE_ATTEMPTS"
_OBLIGATION_NO_LEGACY_RECEIPTS = "PHASE5_W1_NO_LEGACY_RECEIPTS_IN_WINDOW"
_OBLIGATION_GENERATION_CONSISTENT = (
    "PHASE5_W1_RCL_GENERATION_CONSISTENT_WITH_EVIDENCE_TIP"
)
_OBLIGATION_INBOX_REPLAYABLE = "PHASE5_W1_INBOX_UNCONSUMED_REPLAYABLE"
_OBLIGATION_COMPOSITE_STATE_OK = "PHASE5_W1_COMPOSITE_STATE_RESTORE_OK"


def _satisfied(obligation_id: str, *, ok: bool) -> RecoveryObligation:
    """One flat (no-prerequisite) obligation, SATISFIED iff ``ok`` (module docstring's "the
    runtime observes, the kernel judges" split — this function only stamps the OBSERVED result;
    :func:`tos.sbr.predicates.obligation_graph_closed` is what actually decides readiness).
    """
    return RecoveryObligation(
        obligation_id=obligation_id,
        obligation_type="TOS_PHASE5_W1_RECOVERY_BARRIER",
        owner="tos_runtime.recovery.barrier",
        prerequisite_ids=frozenset(),
        acceptable_results=frozenset({ObligationResult.SATISFIED}),
        result=ObligationResult.SATISFIED if ok else ObligationResult.FAILED,
        independent_review_required=False,
    )


def _build_obligations(inputs: RecoveryInputs) -> frozenset[RecoveryObligation]:
    """The six plan §2 decision 2 barrier gates, each as one flat obligation.

    1. Replay verdict identical — GUARANTEED by the time this runs: this barrier only ever
       executes after :func:`~tos_runtime.compose._engine_wiring.verify_replay_or_halt` already
       raised :class:`~tos_runtime.compose._boot_integrity.EngineReplayDiverged` on any genuine
       divergence, INSIDE the same boot (``compose_paper_runtime`` -> ``_finalize``) — a caller
       can only reach this module at all when that check already passed. Recorded here as a
       documented obligation (never re-verified — re-running replay a second time would be the
       exact "the guard is also the oracle" failure design #39 §5.3 warns against), not skipped
       silently.
    2. Every possibly-live attempt (ⓗ) is either absent or positively RECONCILED — never a bare
       "none exist" check: :attr:`~tos_runtime.recovery.inputs.RecoveryInputs
       .possibly_live_reconciliation` (:mod:`tos_runtime.recovery.reconciliation`) must mark
       every entry in :attr:`~tos_runtime.recovery.inputs.RecoveryInputs.possibly_live_attempts`
       :attr:`~tos_runtime.recovery.reconciliation.ReconciliationOutcome.cleared`; a missing
       entry (reconciliation never ran for it) fails closed exactly like an explicit ``False``.
    3. No legacy receipts in the replay window (ⓑ).
    4. RCL generation state consistent with the evidence tip — a structural PRESENCE check only
       (design #40 v1.1 note ② forbids equating the two epochs outright): a genesis boot with an
       empty evidence store and no recorded runtime generation is consistent (nothing to compare
       yet); any other combination requires both to be present.
    5. Inbox unconsumed events are replayable — GUARANTEED by construction: every unconsumed
       event was already read back, without error, by
       :func:`~tos_runtime.recovery.possibly_live.reconstruct_possibly_live_attempts` /
       :func:`~tos_runtime.recovery.inputs.assemble_recovery_inputs`'s own unconsumed count
       before this function is ever called — a row that failed to parse would have raised there,
       not silently vanished into this obligation being marked SATISFIED.
    6. Composite-state restore OK for every possibly-live attempt (staterestore).
    """
    genesis_consistent = (
        inputs.evidence_tip_seq is None and inputs.rcl_runtime_generation is None
    )
    both_present = (
        inputs.evidence_tip_seq is not None
        and inputs.rcl_runtime_generation is not None
    )
    all_possibly_live_cleared = all(
        inputs.possibly_live_reconciliation.get(attempt.event_id, RECON_UNAVAILABLE)
        == RECONCILED
        for attempt in inputs.possibly_live_attempts
    )
    return frozenset(
        {
            _satisfied(_OBLIGATION_REPLAY_IDENTICAL, ok=True),
            _satisfied(_OBLIGATION_NO_POSSIBLY_LIVE, ok=all_possibly_live_cleared),
            _satisfied(
                _OBLIGATION_NO_LEGACY_RECEIPTS, ok=inputs.legacy_receipts.count == 0
            ),
            _satisfied(
                _OBLIGATION_GENERATION_CONSISTENT,
                ok=genesis_consistent or both_present,
            ),
            _satisfied(_OBLIGATION_INBOX_REPLAYABLE, ok=True),
            _satisfied(
                _OBLIGATION_COMPOSITE_STATE_OK,
                ok=not inputs.composite_state_incomplete_attempt_ids,
            ),
        }
    )


def _reason_for(inputs: RecoveryInputs, *, ready: bool) -> str:
    if ready:
        return "all six recovery-barrier obligations satisfied"
    reasons: list[str] = []
    unreconciled = [
        attempt
        for attempt in inputs.possibly_live_attempts
        if inputs.possibly_live_reconciliation.get(attempt.event_id, RECON_UNAVAILABLE)
        != RECONCILED
    ]
    if unreconciled:
        reasons.append(f"{len(unreconciled)} possibly-live attempt(s) unreconciled")
    if inputs.legacy_receipts.count:
        reasons.append(
            f"{inputs.legacy_receipts.count} legacy (fingerprint-less) receipt(s) in window (ⓑ)"
        )
    if inputs.composite_state_incomplete_attempt_ids:
        reasons.append(
            f"{len(inputs.composite_state_incomplete_attempt_ids)} attempt(s) with an "
            "incomplete staterestore composite"
        )
    if not (
        inputs.evidence_tip_seq is not None
        and inputs.rcl_runtime_generation is not None
    ) and not (
        inputs.evidence_tip_seq is None and inputs.rcl_runtime_generation is None
    ):
        reasons.append("RCL generation / evidence tip presence inconsistent")
    return "; ".join(reasons) if reasons else "unsatisfied recovery-barrier obligation"


@dataclass(frozen=True)
class RecoveryVerdict:
    """The recovery barrier's own verdict — never a permission, only a denial-context label
    plus the runtime-level reason and bookkeeping a caller (``tos_runtime.compose
    ._recovery_wiring``) needs to durably record it and decide whether to wire a driver at all.

    Attributes:
        readiness_verdict: The kernel's own :class:`~tos.sbr.vocabulary.ReadinessVerdict` —
            truthy-untestable; gate on ``verdict.readiness_verdict is ReadinessVerdict.READY``,
            never ``if verdict.readiness_verdict:``.
        ready: The plain ``bool`` a compose caller actually branches on (the identity-checked
            result of :attr:`readiness_verdict`, computed once here so every caller uses the
            SAME positive-identity gate rather than re-deriving it with a bare truthiness test).
        reason: A human-readable, non-authoritative summary (never itself evidence — the caller
            durably records the full :class:`~tos_runtime.recovery.inputs.RecoveryInputs`
            alongside this).
        possibly_live_reconciliation: ``{event_id: reason}`` for every possibly-live attempt —
            copied straight from :attr:`~tos_runtime.recovery.inputs.RecoveryInputs
            .possibly_live_reconciliation` (:mod:`tos_runtime.recovery.reconciliation`):
            :data:`RECONCILED` when cleared, a :class:`~tos_runtime.recon.service
            .ReconciliationReport`-supplied reason otherwise, or :data:`RECON_UNAVAILABLE` when
            reconciliation never ran for that entry at all.
        authority_effect: The all-false :class:`~tos.sbr.records.RecoveryAuthorityEffect` this
            verdict carries (SBR-INV-003 — a recovery verdict creates no authority).
    """

    readiness_verdict: ReadinessVerdict
    ready: bool
    reason: str
    possibly_live_reconciliation: dict[str, str]
    authority_effect: RecoveryAuthorityEffect


class RecoveryBarrier:
    """The stateless boot-time recovery barrier (plan §2 decision 2)."""

    @staticmethod
    def verdict(inputs: RecoveryInputs) -> RecoveryVerdict:
        """Fold ``inputs`` into a :class:`RecoveryVerdict` via the kernel's own predicates.

        Args:
            inputs: The durably-assembled :class:`~tos_runtime.recovery.inputs.RecoveryInputs`.

        Returns:
            The :class:`RecoveryVerdict`. ``READY`` only when
            :func:`tos.sbr.predicates.obligation_graph_closed` says the six-obligation graph is
            closed; ``NOT_READY`` otherwise (never anything permissive by default).
        """
        obligations = _build_obligations(inputs)
        closed = obligation_graph_closed(obligations)

        effect = (
            RecoveryAuthorityEffect()
        )  # every flag False — unconstructable otherwise
        # Defence in depth (module docstring): re-check separation on the ALREADY-validated
        # effect rather than trusting construction alone.
        assert recovery_authority_separated(effect, forced_ready_requested=False), (
            "RecoveryAuthorityEffect() must always separate authority — this assertion documents "
            "the defence-in-depth re-check design #17 calls for, and should be unreachable"
        )
        # Documents (does not decide) that nothing here revives a prior authority (SBR-INV-014).
        assert recovery_completion_revives_nothing()

        readiness = ReadinessVerdict.READY if closed else ReadinessVerdict.NOT_READY
        reconciliation = {
            attempt.event_id: inputs.possibly_live_reconciliation.get(
                attempt.event_id, RECON_UNAVAILABLE
            )
            for attempt in inputs.possibly_live_attempts
        }
        return RecoveryVerdict(
            readiness_verdict=readiness,
            ready=readiness is ReadinessVerdict.READY,
            reason=_reason_for(inputs, ready=closed),
            possibly_live_reconciliation=reconciliation,
            authority_effect=effect,
        )
