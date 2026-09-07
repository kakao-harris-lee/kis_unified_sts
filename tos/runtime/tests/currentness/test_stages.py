"""``AttemptBindVerificationStage`` (step 13) + ``TransmissionCapabilityStage``
(step 14) tests (design #40 §5 order 6, lane R item 3)."""

from __future__ import annotations

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import DecisionContextCapsuleRef, Proposal, Proposer
from tos.engine.records import AttemptRequest, InstrumentKey, StageRequest, StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos_runtime.currentness.stages import (
    AttemptBindVerificationStage,
    TransmissionCapabilityContext,
    TransmissionCapabilityStage,
)
from tos_runtime.rcl.log import SqliteCommitLog

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _proposal() -> Proposal:
    issued = Proposal.issue(
        scheme=_SCHEME,
        proposer=Proposer(strategy_id="strat-1", strategy_version="v1"),
        account="acct-1",
        instrument="ES",
        direction="LONG",
        position_effect="OPEN",
        quantity_basis="RISK",
        rationale="test proposal",
        decision_context_capsule=DecisionContextCapsuleRef(
            capsule_id="cap-1", canonical_digest="capdig-1"
        ),
        dsl_version="dsl-0",
        config_version="cfg-0",
    )
    assert isinstance(issued, Proposal)
    return issued


def _attempt() -> AttemptRequest:
    return AttemptRequest(
        attempt_id="att-1",
        conformance_proof_digest="proof-digest-1",
        action_flow_permit_identity="permit-1",
        reference_coordinate_digest="ref-digest-1",
    )


def _request(
    *,
    step: CommitmentStep,
    attempt: AttemptRequest | None,
    prior_verdicts: tuple[StageVerdict, ...] = (),
) -> StageRequest:
    return StageRequest(
        step=step,
        instrument_key=InstrumentKey(account="acct-1", instrument="ES"),
        proposal=_proposal(),
        prior_verdicts=prior_verdicts,
        attempt=attempt,
    )


# ============================================================================
# AttemptBindVerificationStage (step 13)
# ============================================================================


def test_attempt_bind_is_unknown_when_no_attempt_is_bound() -> None:
    stage = AttemptBindVerificationStage(
        reservation_digest_reader=lambda _a: None,
        permit_digest_reader=lambda _a: None,
        approval_digest_reader=lambda _a: None,
    )
    request = _request(step=CommitmentStep.ATTEMPT_BIND_VERIFICATION, attempt=None)
    verdict = stage(request)
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_attempt_bind_admits_when_every_link_matches_exactly() -> None:
    attempt = _attempt()
    approval_verdict = StageVerdict(
        step=CommitmentStep.INDEPENDENT_APPROVAL,
        outcome=StageOutcome.ADMIT,
        authority_class=StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
        bound_digest="approval-digest-1",
    )
    stage = AttemptBindVerificationStage(
        reservation_digest_reader=lambda a: a.conformance_proof_digest,
        permit_digest_reader=lambda a: a.action_flow_permit_identity,
        approval_digest_reader=lambda _a: "approval-digest-1",
    )
    request = _request(
        step=CommitmentStep.ATTEMPT_BIND_VERIFICATION,
        attempt=attempt,
        prior_verdicts=(approval_verdict,),
    )
    verdict = stage(request)
    assert verdict.outcome is StageOutcome.ADMIT
    assert verdict.bound_identity == attempt.attempt_id


def test_attempt_bind_denies_on_a_substituted_link() -> None:
    attempt = _attempt()
    stage = AttemptBindVerificationStage(
        reservation_digest_reader=lambda _a: "a-different-digest",
        permit_digest_reader=lambda a: a.action_flow_permit_identity,
        approval_digest_reader=lambda _a: None,
    )
    request = _request(step=CommitmentStep.ATTEMPT_BIND_VERIFICATION, attempt=attempt)
    verdict = stage(request)
    assert verdict.outcome is StageOutcome.DENY


def test_attempt_bind_is_unknown_on_an_undetermined_link() -> None:
    attempt = _attempt()
    stage = AttemptBindVerificationStage(
        reservation_digest_reader=lambda a: a.conformance_proof_digest,
        permit_digest_reader=lambda a: a.action_flow_permit_identity,
        approval_digest_reader=lambda _a: None,  # undetermined, not missing-link
    )
    approval_verdict = StageVerdict(
        step=CommitmentStep.INDEPENDENT_APPROVAL,
        outcome=StageOutcome.ADMIT,
        authority_class=StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
        bound_digest="approval-digest-1",
    )
    request = _request(
        step=CommitmentStep.ATTEMPT_BIND_VERIFICATION,
        attempt=attempt,
        prior_verdicts=(approval_verdict,),
    )
    verdict = stage(request)
    assert verdict.outcome is StageOutcome.UNKNOWN


# ============================================================================
# TransmissionCapabilityStage (step 14)
# ============================================================================


def _context() -> TransmissionCapabilityContext:
    return TransmissionCapabilityContext(
        reservation_identity="rsv-1",
        account_scope="acct-1",
        instrument_scope="ES",
        side_action_scope="BUY",
    )


def test_transmission_capability_is_unknown_when_no_attempt_is_bound(
    log: SqliteCommitLog, writer_epoch: int
) -> None:
    stage = TransmissionCapabilityStage(
        log, writer_epoch=writer_epoch, context_reader=lambda _r: _context()
    )
    request = _request(step=CommitmentStep.TRANSMISSION_CAPABILITY, attempt=None)
    verdict = stage(request)
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_transmission_capability_is_unknown_when_context_is_missing(
    log: SqliteCommitLog, writer_epoch: int
) -> None:
    stage = TransmissionCapabilityStage(
        log, writer_epoch=writer_epoch, context_reader=lambda _r: None
    )
    request = _request(step=CommitmentStep.TRANSMISSION_CAPABILITY, attempt=_attempt())
    verdict = stage(request)
    assert verdict.outcome is StageOutcome.UNKNOWN


def test_transmission_capability_admits_and_commits_a_durable_entry(
    log: SqliteCommitLog, writer_epoch: int
) -> None:
    stage = TransmissionCapabilityStage(
        log, writer_epoch=writer_epoch, context_reader=lambda _r: _context()
    )
    request = _request(step=CommitmentStep.TRANSMISSION_CAPABILITY, attempt=_attempt())
    verdict = stage(request)
    assert verdict.outcome is StageOutcome.ADMIT
    assert verdict.bound_digest is not None
    assert stage.nonce_for("att-1") is not None
    assert len(list(log.replay())) == 1


def test_transmission_capability_is_unknown_when_no_epoch_acquired(
    log_path, evidence_port
) -> None:
    unacquired_log = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        stage = TransmissionCapabilityStage(
            unacquired_log, writer_epoch=0, context_reader=lambda _r: _context()
        )
        request = _request(
            step=CommitmentStep.TRANSMISSION_CAPABILITY, attempt=_attempt()
        )
        verdict = stage(request)
        assert verdict.outcome is StageOutcome.UNKNOWN
    finally:
        unacquired_log.close()
