"""§7.2-5 — the decision pipeline is reproducible: same inputs ⇒ byte-identical outcome (§3.1).

RFC-003 §10:345-348 — "given the exact recorded Decision Context, Decision Policy version, and
configuration version, an independent re-execution SHALL reconstruct the same outcome." A
synchronous, single-threaded, clock-free core makes that trivially demonstrable, which is precisely
the D5 argument (design #31 §2.1).

**⚠ Scope, stated honestly (design #31 §6 Gap-1 / §7.2-5 / §9-9).** This establishes
**reproducibility** (same inputs ⇒ same outcome), *not* **distinctness** (different bars ⇒ different
identity). Two bars sharing one Critical Input Snapshot digest would collapse to one proposal
identity, and preventing that depends on D-E2 producing distinct Snapshot digests — it is deferred,
not claimed here. The tests below assert the reproducibility half and *record* the deferral.

The verdict is computed through the shipped :func:`tos.evidence.compute_replay_result`, so the
engine does not invent its own notion of "reproduced".

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

from tos.engine import (
    DecisionTickPayload,
    RecordingEvidenceSink,
    build_attempt_request,
    replay_result_for,
    run_decision_pipeline,
)
from tos.evidence import ReplayResultState

from ._engine_fixtures import (
    PERMIT_IDENTITY,
    PROOF_DIGEST,
    SCHEME,
    RecordingTransmit,
    admitting_time_inputs,
    build_core,
    decision_tick,
    engine_configuration,
    instrument_key,
    issue_capsule,
    ordering,
    registry_with,
)


def _run_once(capsule=None, *, sequence: int = 1):
    """Run the decision pipeline once over a fresh registry + sink; return its result."""
    registry = registry_with()
    entry = registry.resolve(instrument_key()).entries[0]
    payload = DecisionTickPayload(
        instrument_key=instrument_key(),
        capsule=capsule or issue_capsule(),
        time=admitting_time_inputs(),
        reference=ordering(sequence),
    )
    return run_decision_pipeline(
        entry=entry,
        payload=payload,
        configuration=engine_configuration(),
        scheme=SCHEME,
        sink=RecordingEvidenceSink(),
    )


def test_the_same_inputs_reconstruct_the_same_outcome() -> None:
    """(§7.2-5) Two independent runs over the same (strategy, capsule, config) agree byte-for-byte."""
    capsule = issue_capsule()
    first = _run_once(capsule)
    second = _run_once(capsule)

    assert first.proposal is not None and second.proposal is not None
    assert first.proposal.canonical_digest == second.proposal.canonical_digest
    assert first.proposal.proposal_id == second.proposal.proposal_id
    assert first.proposal == second.proposal


def test_the_recorded_input_signature_is_identical_across_runs() -> None:
    """(§3.1 phase 4) The recorded provenance — capsule id/digest, versions — reproduces exactly."""
    capsule = issue_capsule()
    first = _run_once(capsule)
    second = _run_once(capsule)

    assert first.signature is not None and second.signature is not None
    assert first.signature == second.signature
    assert first.signature.capsule_id == capsule.capsule_id
    assert first.signature.capsule_canonical_digest == capsule.canonical_digest


def test_the_replay_verdict_is_match_for_two_identical_runs() -> None:
    """(§7.2-5) The shipped replay predicate reports MATCH — the engine invents no verdict."""
    capsule = issue_capsule()
    first = _run_once(capsule)
    second = _run_once(capsule)

    verdict = replay_result_for(
        expected_outcome_digest=first.outcome_digest,
        actual_outcome_digest=second.outcome_digest,
        baseline_supported=True,
        input_complete=True,
    )
    assert verdict is ReplayResultState.MATCH


def test_a_differing_outcome_digest_is_reported_as_diverged() -> None:
    """The replay adapter is a real comparison: a differing digest is DIVERGED, never MATCH."""
    verdict = replay_result_for(
        expected_outcome_digest="a",
        actual_outcome_digest="b",
        baseline_supported=True,
        input_complete=True,
    )
    assert verdict is ReplayResultState.DIVERGED


def test_an_unsupported_baseline_or_incomplete_input_is_never_a_match() -> None:
    """A reproduction claim needs a supported baseline and complete inputs (fail-closed)."""
    assert (
        replay_result_for(
            expected_outcome_digest="a",
            actual_outcome_digest="a",
            baseline_supported=False,
            input_complete=True,
        )
        is ReplayResultState.UNSUPPORTED_BASELINE
    )
    assert (
        replay_result_for(
            expected_outcome_digest="a",
            actual_outcome_digest="a",
            baseline_supported=True,
            input_complete=False,
        )
        is ReplayResultState.CORRUPT_INPUT
    )


def test_the_whole_event_path_is_reproducible_including_the_attempt_identity() -> None:
    """(§2.1 D5 + §4.3) Two independently wired cores produce the same attempt identity."""
    capsule = issue_capsule()

    first_core, _ = build_core(transmit=RecordingTransmit())
    first = first_core.handle(decision_tick(sequence=1, capsule=capsule))
    second_core, _ = build_core(transmit=RecordingTransmit())
    second = second_core.handle(decision_tick(sequence=1, capsule=capsule))

    assert first.flow is not None and second.flow is not None
    assert first.flow.attempt is not None and second.flow.attempt is not None
    assert first.flow.attempt.attempt_id == second.flow.attempt.attempt_id
    assert first.flow.attempt == second.flow.attempt


def test_distinctness_is_not_claimed_only_reproducibility() -> None:
    """(§6 Gap-1 / §9-9) The honest limit: two capsule-identical bars share one proposal identity.

    Recorded rather than papered over. The two runs differ only in their *event ordering
    coordinate*, which is not part of the Decision Context — so the emitted proposal identity is
    the same. Making different bars distinct depends on D-E2 supplying distinct Critical Input
    Snapshot digests; the slice does not claim it. (The **attempt** identity, by contrast, does
    bind the reference coordinate, so it differs — asserted here so the boundary is exact.)
    """
    capsule = issue_capsule()
    first = _run_once(capsule, sequence=1)
    second = _run_once(capsule, sequence=2)

    assert first.proposal is not None and second.proposal is not None
    assert first.proposal.proposal_id == second.proposal.proposal_id, (
        "reproducibility, not distinctness — per-bar identity distinctness is D-E2's "
        "(design #31 §6 Gap-1 / §9-9)"
    )

    first_attempt = build_attempt_request(
        conformance_proof_digest=PROOF_DIGEST,
        action_flow_permit_identity=PERMIT_IDENTITY,
        reference=ordering(1),
        scheme=SCHEME,
    )
    second_attempt = build_attempt_request(
        conformance_proof_digest=PROOF_DIGEST,
        action_flow_permit_identity=PERMIT_IDENTITY,
        reference=ordering(2),
        scheme=SCHEME,
    )
    assert first_attempt.attempt_id != second_attempt.attempt_id
