"""``ActionFlowGovernor`` — runtime realization of the Action Flow Governor (AFG)"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from tos.afg import (
    ActionAmplificationEnvelope,
    ActionCause,
    ActionClassKind,
    ActionFlowDecision,
    ActionFlowPermit,
    ActionFlowPolicy,
    ActionFlowScopeKind,
    ActionFlowStateSnapshot,
    ActionFlowVector,
    ObservedAmplification,
    action_flow_decision,
    amplification_bounded,
    atomic_economic_flow_coverage,
    cause_lineage_complete,
    envelope_not_enlarged,
    scope_graph_complete,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, derive_id, get_scheme
from tos.rcl import (
    AppendReceipt,
    AppendRefusal,
    CapacityVector,
    CommandType,
    CommitEntry,
)

from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.rcl.log import SqliteCommitLog

__all__ = [
    "ActionFlowConfigError",
    "ActionFlowDecisionInputs",
    "ActionFlowGovernor",
    "PermitIssueResult",
    "permit_reservation_binding",
]

_STANDALONE_PERMIT_KIND = CommandType.ISSUE_ACTION_FLOW_PERMIT

_EVIDENCE_KIND_DECISION = "AFG_DECISION"
_EVIDENCE_KIND_PERMIT = "AFG_PERMIT"


class ActionFlowConfigError(Exception):
    """Raised when the injected :class:`~tos.afg.ActionAmplificationEnvelope`"""


@dataclass(frozen=True)
class ActionFlowDecisionInputs:
    """Every injected witness :func:`tos.afg.action_flow_decision` needs."""

    cause: ActionCause | None
    snapshot: ActionFlowStateSnapshot | None
    required_scopes: frozenset[ActionFlowScopeKind]
    producer_self_declared_scope: bool | None
    observed_amplification: ObservedAmplification | None
    requested_limit: CapacityVector
    injected_envelope_max: CapacityVector | None
    limit_source_is_injected_envelope: bool | None
    economic_ref: str | None
    flow_vector: ActionFlowVector | None
    committed_flow_vectors: Sequence[CapacityVector]
    hard_limit: CapacityVector | None
    runtime_limit: CapacityVector | None
    economic_commitment_exclusive: bool | None
    flow_commitment_exclusive: bool | None
    generation_current: bool
    applicable_action_flow_scopes: tuple[str, ...]
    decision_generation: int
    policy: ActionFlowPolicy | None = None
    action_class: ActionClassKind | None = None
    decision_effective_limit: ActionFlowVector | None = None
    command_identity: str | None = None
    command_digest: str | None = None
    cause_digest: str | None = None
    lineage_digest: str | None = None
    amplification_envelope_digest: str | None = None
    protective_classification_digest: str | None = None
    reason_context: dict[str, Any] | None = None


@dataclass(frozen=True)
class PermitIssueResult:
    """Outcome of one :meth:`ActionFlowGovernor.issue_permit` call."""

    permit: ActionFlowPermit
    log_result: AppendReceipt | AppendRefusal
    rcl_commitment_ref: int | None


def permit_reservation_binding(permit: ActionFlowPermit) -> tuple[str, str] | None:
    """The ``(claim_nonce, canonical_digest)`` pair a combined reservation+permit"""
    if permit.claim_nonce is None or permit.canonical_digest is None:
        return None
    return (permit.claim_nonce, permit.canonical_digest)


class ActionFlowGovernor:
    """Runtime realization of AFG decision composition + permit issuance"""

    def __init__(
        self,
        log: SqliteCommitLog,
        evidence: EvidenceAppendPort,
        envelope: ActionAmplificationEnvelope,
        *,
        writer_epoch: int,
        canonicalization_version: str = EV_L1_PROVISIONAL_VERSION,
        protective_classification_digest_provider: (
            Callable[[], str | None] | None
        ) = None,
    ) -> None:
        """Compose the governor over its injected ports."""
        if not envelope.declares_every_bound():
            raise ActionFlowConfigError(
                "ActionAmplificationEnvelope leaves at least one amplification "
                "axis undeclared (null/named-TBD) — tos.afg §5.8 line 141 "
                "'unknown or unbounded amplification is denial' — refusing to "
                "start"
            )
        self._log = log
        self._evidence = evidence
        self._envelope = envelope
        self._writer_epoch = writer_epoch
        self._scheme = get_scheme(canonicalization_version)
        self._protective_digest_provider = protective_classification_digest_provider

    @property
    def envelope(self) -> ActionAmplificationEnvelope:
        return self._envelope

    def decide(self, inputs: ActionFlowDecisionInputs) -> ActionFlowDecision:
        """Prepare :func:`tos.afg.action_flow_decision`'s witnesses via the"""
        scope_complete = scope_graph_complete(
            inputs.snapshot,
            inputs.required_scopes,
            producer_self_declared_scope=inputs.producer_self_declared_scope,
        )
        lineage_complete = cause_lineage_complete(inputs.cause)
        amplification_ok = amplification_bounded(
            self._envelope, inputs.observed_amplification
        )
        envelope_ok = envelope_not_enlarged(
            requested_limit=inputs.requested_limit,
            injected_envelope_max=inputs.injected_envelope_max,
            limit_source_is_injected_envelope=inputs.limit_source_is_injected_envelope,
        )
        coverage = atomic_economic_flow_coverage(
            inputs.economic_ref,
            inputs.flow_vector,
            committed_flow_vectors=inputs.committed_flow_vectors,
            hard_limit=inputs.hard_limit,
            runtime_limit=inputs.runtime_limit,
            economic_commitment_exclusive=inputs.economic_commitment_exclusive,
            flow_commitment_exclusive=inputs.flow_commitment_exclusive,
        )
        decision_digest_seed = self._scheme.compute_digest(
            {
                "cause_digest": inputs.cause_digest,
                "decision_generation": inputs.decision_generation,
                "snapshot_digest": (
                    None
                    if inputs.snapshot is None
                    else inputs.snapshot.canonical_digest
                ),
                "command_digest": inputs.command_digest,
            }
        )
        decision_id = derive_id("afg-decision", decision_digest_seed)
        protective_classification_digest = (
            inputs.protective_classification_digest
            if self._protective_digest_provider is None
            else self._protective_digest_provider()
        )
        decision = action_flow_decision(
            coverage=coverage,
            scope_complete=scope_complete,
            lineage_complete=lineage_complete,
            amplification_ok=amplification_ok,
            envelope_ok=envelope_ok,
            generation_current=inputs.generation_current,
            applicable_action_flow_scopes=inputs.applicable_action_flow_scopes,
            decision_id=decision_id,
            decision_generation=inputs.decision_generation,
            scheme=self._scheme,
            policy=inputs.policy,
            snapshot=inputs.snapshot,
            action_class=inputs.action_class,
            action_flow_vector=inputs.flow_vector,
            decision_effective_limit=inputs.decision_effective_limit,
            command_identity=inputs.command_identity,
            command_digest=inputs.command_digest,
            cause_digest=inputs.cause_digest,
            lineage_digest=inputs.lineage_digest,
            amplification_envelope_digest=inputs.amplification_envelope_digest,
            protective_classification_digest=protective_classification_digest,
        )
        self._evidence.append(
            {
                "decision_id": decision.decision_id,
                "decision_digest": decision.canonical_digest,
                "result": None if decision.result is None else decision.result.value,
            },
            kind=_EVIDENCE_KIND_DECISION,
            record_class=_EVIDENCE_KIND_DECISION,
        )
        return decision

    def build_permit(
        self,
        decision: ActionFlowDecision,
        *,
        permit_generation: int,
        command_identity: str,
        consumer_identity: str | None = None,
        issue_anchor: str | None = None,
        max_age_ms: int | None = None,
        invalidation_generation: int | None = None,
        economic_capacity_commitment_ref: str | None = None,
    ) -> ActionFlowPermit:
        """Issue (digest-bind) the :class:`~tos.afg.ActionFlowPermit` schema"""
        nonce_digest = self._scheme.compute_digest(
            {
                "decision_digest": decision.canonical_digest,
                "command_identity": command_identity,
                "permit_generation": permit_generation,
            }
        )
        claim_nonce = derive_id("afg-permit-nonce", nonce_digest)
        permit_id = derive_id(
            "afg-permit", self._scheme.compute_digest({"claim_nonce": claim_nonce})
        )
        permit = ActionFlowPermit.issue(
            scheme=self._scheme,
            permit_id=permit_id,
            permit_generation=permit_generation,
            command_identity=command_identity,
            claim_nonce=claim_nonce,
            rcl_commitment_ref=None,
            writer_epoch=self._writer_epoch,
            revision=None,
            policy_digest=decision.policy_digest,
            policy_generation=decision.policy_generation,
            snapshot_digest=decision.snapshot_digest,
            decision_digest=decision.canonical_digest,
            cause_digest=decision.cause_digest,
            lineage_digest=decision.lineage_digest,
            resource_vector=decision.action_flow_vector,
            ordinary_or_protective_dimension_mark=None,
            protective_lease_proof=None,
            reserve_proof=None,
            consumer_identity=consumer_identity,
            single_use=True,
            issue_anchor=issue_anchor,
            max_age_ms=max_age_ms,
            invalidation_generation=invalidation_generation,
            economic_capacity_commitment_ref=economic_capacity_commitment_ref,
        )
        assert isinstance(permit, ActionFlowPermit)
        return permit

    def issue_permit(
        self, permit: ActionFlowPermit, *, expected_seq: int
    ) -> PermitIssueResult:
        """STANDALONE permit commitment via a plain ``append_cas`` (module"""
        binding = permit_reservation_binding(permit)
        if binding is None:
            raise ActionFlowConfigError(
                "ActionFlowPermit.claim_nonce and .canonical_digest must be "
                "concrete before an RCL commitment can be attempted (fail-closed)"
            )
        claim_nonce, permit_digest = binding
        entry = CommitEntry(
            command_id=claim_nonce,
            command_digest=permit_digest,
            kind=_STANDALONE_PERMIT_KIND,
        )
        payload_json = json.dumps(permit.model_dump(mode="json"), sort_keys=True)
        log_result = self._log.append_cas(
            entry,
            expected_seq=expected_seq,
            writer_epoch=self._writer_epoch,
            payload_json=payload_json,
        )
        commitment_ref = (
            log_result.seq if isinstance(log_result, AppendReceipt) else None
        )
        self._evidence.append(
            {
                "permit_id": permit.permit_id,
                "permit_digest": permit.canonical_digest,
                "claim_nonce": claim_nonce,
                "committed": commitment_ref is not None,
            },
            kind=_EVIDENCE_KIND_PERMIT,
            record_class=_EVIDENCE_KIND_PERMIT,
        )
        return PermitIssueResult(
            permit=permit, log_result=log_result, rcl_commitment_ref=commitment_ref
        )
