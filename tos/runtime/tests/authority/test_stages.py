"""``IndependentApprovalStage`` tests (design #40 §5 order 4 item 4).

The central fault contract under test: **this stage never emits
``StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL``**, in any of ADMIT /
DENY / UNKNOWN — that member is reserved for
``tos.engine.standins.ProvisionalStandIn``, which this stage replaces.
"""

from __future__ import annotations

from pathlib import Path

from tos.dsl import Proposal
from tos.engine.records import InstrumentKey, StageRequest
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos.iap import (
    ApprovalConsumptionRecord,
    ConsumptionOutcome,
    ConsumptionStatus,
    IndependentApprovalDecision,
)
from tos_runtime.authority.iap import ConsumeResult, IntentRegistry, LoadedApproval
from tos_runtime.authority.stages import IndependentApprovalStage, item14_fields

from .test_iap import _decision as build_decision


def _bare_request() -> StageRequest:
    return StageRequest(
        step=CommitmentStep.INDEPENDENT_APPROVAL,
        instrument_key=InstrumentKey(account="acct-1", instrument="ISU1"),
        proposal=Proposal(),
    )


def _bare_loaded(decision: IndependentApprovalDecision) -> LoadedApproval:
    """A :class:`LoadedApproval` with no receipt facts — these stage-level
    tests exercise routing/outcome mapping, not expiry composition (kernel
    round #1 §2.2's own ``IntentRegistry`` tests own that)."""
    return LoadedApproval(
        decision=decision,
        issued_at_unix_ms=None,
        receipt_continuity=None,
        receipt_anchor=None,
        issuer_signed_age_ms=None,
        issuer_age_uncertainty_ms=None,
    )


def _stage(
    intent_registry: IntentRegistry,
    decision: IndependentApprovalDecision | None,
) -> IndependentApprovalStage:
    loaded = None if decision is None else _bare_loaded(decision)
    return IndependentApprovalStage(
        intent_registry,
        decision_provider=lambda _request: loaded,
        command_identity_provider=lambda _request, _decision: "cmd-1",
        command_digest_provider=lambda _request, _decision: "digest-1",
        decision_current_provider=lambda _request, _decision, _receipt: True,
        envelope_equivalent_provider=lambda _request, _decision: True,
    )


def test_admit_never_uses_non_authoritative_provisional(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
) -> None:
    decision = build_decision(intent_registry, approvals_dir, expected_owner_uid)
    stage = _stage(intent_registry, decision)

    verdict = stage(_bare_request())

    assert verdict.outcome is StageOutcome.ADMIT
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE
    assert (
        verdict.authority_class is not StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL
    )


def test_deny_never_uses_non_authoritative_provisional(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
) -> None:
    decision = build_decision(intent_registry, approvals_dir, expected_owner_uid)
    # Consume it once outside the stage, with a DIFFERENT command, so the
    # stage's own consumption attempt collides as REJECTED_CONFLICT (a DENY).
    intent_registry.consume(
        decision,
        command_identity="cmd-0",
        command_digest="digest-0",
        decision_current=True,
        approved_intent_envelope_equivalent=True,
    )
    stage = _stage(intent_registry, decision)

    verdict = stage(_bare_request())

    assert verdict.outcome is StageOutcome.DENY
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE
    assert (
        verdict.authority_class is not StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL
    )


def test_unknown_never_uses_non_authoritative_provisional_when_no_decision(
    intent_registry: IntentRegistry,
) -> None:
    stage = _stage(intent_registry, None)

    verdict = stage(_bare_request())

    assert verdict.outcome is StageOutcome.UNKNOWN
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE
    assert (
        verdict.authority_class is not StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL
    )


def test_item14_fields_after_admission() -> None:
    record = ApprovalConsumptionRecord(decision_id="d1", decision_digest="dig-d1")
    result = ConsumeResult(
        status=ConsumptionStatus.CONSUMED,
        outcome=ConsumptionOutcome.CONSUMED_NEW,
        record=record,
        log_result=None,
    )
    fields = item14_fields(result)
    assert fields["approval_consumed_for_this_intent"] is True
    assert fields["approval_intent_binding_digest"] == "dig-d1"


def test_item14_fields_when_log_unreachable_is_none_not_false() -> None:
    result = ConsumeResult(
        status=None,  # type: ignore[arg-type]
        outcome=None,
        record=None,
        log_result=None,
    )
    fields = item14_fields(result)
    assert fields["approval_consumed_for_this_intent"] is None
    assert fields["approval_intent_binding_digest"] is None
