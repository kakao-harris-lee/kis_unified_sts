"""``IndependentApprovalStage`` tests (design #40 §5 order 4 item 4)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from tos.dsl import Proposal
from tos.engine.records import InstrumentKey, StageRequest, StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos.iap import (
    ApprovalConsumptionRecord,
    ConsumptionOutcome,
    ConsumptionStatus,
    IndependentApprovalDecision,
)
from tos_runtime.authority.iap import ConsumeResult, IntentRegistry, LoadedApproval
from tos_runtime.authority.stages import IndependentApprovalStage, item14_fields
from tos_runtime.authority.standing import (
    StandingApprovalSource,
    StandingRecordingStage,
)

from .test_iap import _decision as build_decision


def _bare_request() -> StageRequest:
    return StageRequest(
        step=CommitmentStep.INDEPENDENT_APPROVAL,
        instrument_key=InstrumentKey(account="acct-1", instrument="ISU1"),
        proposal=Proposal(),
    )


def _bare_loaded(decision: IndependentApprovalDecision) -> LoadedApproval:
    """A :class:`LoadedApproval` with no receipt facts — these stage-level"""
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


def _assert_pure_predicate(verdict: StageVerdict) -> None:
    """Every stage here answers as a pure predicate, never as a provisional."""
    assert verdict.authority_class is StageAuthorityClass.AVAILABLE_PURE_PREDICATE
    assert (
        verdict.authority_class is not StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL
    )


def test_admit_never_uses_non_authoritative_provisional(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
) -> None:
    decision = build_decision(intent_registry, approvals_dir, expected_owner_uid)
    stage = _stage(intent_registry, decision)

    verdict = stage(_bare_request())

    assert verdict.outcome is StageOutcome.ADMIT
    _assert_pure_predicate(verdict)


def test_deny_never_uses_non_authoritative_provisional(
    intent_registry: IntentRegistry, approvals_dir: Path, expected_owner_uid: int
) -> None:
    decision = build_decision(intent_registry, approvals_dir, expected_owner_uid)
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
    _assert_pure_predicate(verdict)


def test_unknown_never_uses_non_authoritative_provisional_when_no_decision(
    intent_registry: IntentRegistry,
) -> None:
    stage = _stage(intent_registry, None)

    verdict = stage(_bare_request())

    assert verdict.outcome is StageOutcome.UNKNOWN
    _assert_pure_predicate(verdict)


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


class _StubStandingSource:
    """Only what ``StandingRecordingStage`` touches: the reset, the reason, the record."""

    def __init__(self, on_request: str | None, stale: str | None = None) -> None:
        self._on_request = on_request
        self._reason = stale
        self.recorded: list[StageVerdict] = []

    def begin_request(self) -> None:
        self._reason = self._on_request

    @property
    def last_not_covered_reason(self) -> str | None:
        return self._reason

    def record_verdict(self, verdict: StageVerdict) -> None:
        self.recorded.append(verdict)


def _recording_stage(
    source: _StubStandingSource, verdict: StageVerdict
) -> StandingRecordingStage:
    return StandingRecordingStage(
        lambda _request: verdict, cast(StandingApprovalSource, source)
    )


def _unknown(bound_identity: str | None = None) -> StageVerdict:
    return StageVerdict(
        step=CommitmentStep.INDEPENDENT_APPROVAL,
        outcome=StageOutcome.UNKNOWN,
        authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
        bound_identity=bound_identity,
        reason="no independent approval decision is available for this proposal",
    )


def test_the_standing_refusal_reason_is_named_in_the_step4_unknown_text() -> None:
    """2026-11-25: 315 OPENs halted at step 4 with text that named no cause at all."""
    inner = _unknown()
    source = _StubStandingSource("uses_exhausted:OPEN-LONG-02")
    verdict = _recording_stage(source, inner)(_bare_request())
    assert verdict.reason == f"{inner.reason} · standing: uses_exhausted:OPEN-LONG-02"
    assert verdict.outcome is inner.outcome and verdict.step is inner.step
    assert verdict.authority_class is inner.authority_class
    assert source.recorded == [inner]


def test_a_stale_not_covered_reason_never_reaches_the_next_verdict() -> None:
    """A pass the standing source never judges must name no standing reason."""
    inner = _unknown()
    source = _StubStandingSource(None, stale="open_over_outstanding_reservation")
    assert _recording_stage(source, inner)(_bare_request()).reason == inner.reason


def test_a_verdict_that_bound_a_decision_keeps_its_own_text() -> None:
    """The reason belongs to the no-decision branch — never to one that consumed a decision."""
    inner = _unknown(bound_identity="iap-decision-1")
    source = _StubStandingSource("open_over_outstanding_reservation")
    assert _recording_stage(source, inner)(_bare_request()).reason == inner.reason
