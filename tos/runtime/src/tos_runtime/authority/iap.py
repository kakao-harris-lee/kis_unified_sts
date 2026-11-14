"""Runtime owner for operator-authored Independent Approval decisions."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalizationScheme, get_scheme
from tos.iap import (
    ApprovalConsumptionRecord,
    ApprovalResult,
    ConsumptionOutcome,
    ConsumptionStatus,
    IndependentApprovalDecision,
    ProposalApprovalRequest,
    TradingApprovalPolicy,
    consumption_transition,
    decision_unexpired,
    exact_binding_holds,
    request_is_complete,
)
from tos.rcl import AppendReceipt, AppendRefusal, CommandType, CommitEntry
from tos.time import (
    ConsumerReceiptAnchor,
    HealthState,
    MonotonicReading,
    TimeContinuityIdentity,
    effective_snapshot_age_bound_from_continuity,
    elapsed_within_continuity,
)

from tos_runtime._named_tbd import is_named_tbd_placeholder
from tos_runtime.custody.file_custody import verify_file_mode_and_owner
from tos_runtime.rcl.log import CommitLogCorruption, SqliteCommitLog, StaleEpochRead
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TimeServiceNotStarted, TimeSnapshotReader

__all__ = [
    "ConsumeResult",
    "IntentRegistry",
    "LoadedApproval",
    "OperatorApprovalFileError",
    "load_operator_approval_file",
    "load_operator_approval_with_receipt",
]

_CONSUMPTION_PREFIX = "iap-consumption"

_CONSUMPTION_KIND = CommandType.CONSUME_APPROVAL_DECISION

_EVIDENCE_KIND_PROPOSAL = "IAP_PROPOSAL"
_EVIDENCE_KIND_DECISION = "IAP_DECISION_REGISTERED"
_EVIDENCE_KIND_CONSUMPTION = "IAP_CONSUMPTION"

_DECISION_TBD_CHECKED_FIELDS: tuple[str, ...] = (
    "decision_id",
    "request_id",
    "request_digest",
    "trading_approval_policy_id",
    "trading_approval_policy_digest",
    "approved_intent_envelope_id",
    "approved_intent_envelope_digest",
    "supersedes_decision_id",
)


def _consumption_command_id(decision: IndependentApprovalDecision) -> str:
    """The content-addressed, log-visible id one decision's consumption commits under."""
    generation = (
        decision.decision_generation if decision.decision_generation is not None else 0
    )
    return (
        f"{_CONSUMPTION_PREFIX}:{decision.request_id or ''}:"
        f"{generation}:{decision.decision_id or ''}"
    )


class OperatorApprovalFileError(RuntimeError):
    """Raised by :func:`load_operator_approval_file` on any refusal."""


def _load_raw_approval_mapping(
    path: Path, *, expected_owner_uid: int, getuid: Callable[[], int]
) -> dict[str, Any]:
    """Checks 1-3 of :func:`load_operator_approval_file`: custody gate, read,"""
    try:
        verify_file_mode_and_owner(
            path, expected_owner_uid=expected_owner_uid, getuid=getuid
        )
    except Exception as exc:  # noqa: BLE001 - re-raised under this module's own type
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: {path} failed the custody mode/owner "
            f"gate: {exc}"
        ) from exc
    try:
        raw_text = path.read_text()
    except OSError as exc:
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: cannot read {path}: {exc}"
        ) from exc
    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: {path} is not valid YAML: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: {path} must parse to a mapping "
            f"(got {type(raw).__name__})"
        )
    return raw


def _verify_environment_label(
    raw: Mapping[str, Any], path: Path, environment_label: str | None
) -> None:
    """Check 4: the file's own label must byte-exact match the runtime's."""
    file_label = raw.get("environment_label")
    if file_label != environment_label or not file_label:
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: {path} environment_label="
            f"{file_label!r} does not match runtime environment_label="
            f"{environment_label!r} — refuse (cross-environment isolation)"
        )


def _check_decision_age_requires_issued_at(raw: Mapping[str, Any], path: Path) -> None:
    """Require ``issued_at_unix_ms`` whenever ``max_decision_age_ms`` is set"""
    if raw.get("max_decision_age_ms") is None:
        return
    issued_at = raw.get("issued_at_unix_ms")
    if issued_at is None:
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: {path} sets 'max_decision_age_ms'="
            f"{raw['max_decision_age_ms']!r} but no 'issued_at_unix_ms' — decision "
            "expiry enforcement needs an issuance timestamp to compose an age "
            "bound from (kernel round #1 §1.2/§2.2; ADR-002-023 §12 item 2 "
            "'unexpired') — refusing rather than silently dropping the "
            "operator's expiry intent. Set 'issued_at_unix_ms', or leave "
            "'max_decision_age_ms' unset/null."
        )
    if isinstance(issued_at, bool) or not isinstance(issued_at, int):
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: {path} 'issued_at_unix_ms'="
            f"{issued_at!r} must be an integer (unix epoch milliseconds)"
        )


def _refuse_max_decision_age_ms_without_a_receipt(
    raw: Mapping[str, Any], path: Path
) -> None:
    """Unconditional refusal restored for the receipt-less loader (re-review"""
    if raw.get("max_decision_age_ms") is not None:
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: {path} sets 'max_decision_age_ms'="
            f"{raw['max_decision_age_ms']!r}, but this loader produces no "
            "receipt to enforce it against — use "
            "load_operator_approval_with_receipt instead, or leave "
            "'max_decision_age_ms' unset/null."
        )


def _build_decision_from_raw(
    raw: Mapping[str, Any],
    path: Path,
    scheme: CanonicalizationScheme,
    *,
    age_check: Callable[[Mapping[str, Any], Path], None],
) -> IndependentApprovalDecision:
    """Check 5 + construction: parse ``result`` verbatim and issue the decision"""
    age_check(raw, path)
    try:
        result = ApprovalResult(raw["result"])
    except (KeyError, ValueError) as exc:
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: {path} 'result' is missing or not one "
            f"of APPROVE/DENY/UNKNOWN: {exc}"
        ) from exc
    for field_name in _DECISION_TBD_CHECKED_FIELDS:
        if is_named_tbd_placeholder(raw.get(field_name)):
            raise OperatorApprovalFileError(
                f"load_operator_approval_file: {path} {field_name!r} is still the "
                "template placeholder 'TBD' — operator-fill before activation, never "
                "a value sealed into this decision's own canonical digest"
            )
    try:
        decision = IndependentApprovalDecision.issue(
            scheme=scheme,
            decision_id=raw["decision_id"],
            decision_generation=raw["decision_generation"],
            request_id=raw.get("request_id"),
            request_digest=raw.get("request_digest"),
            trading_approval_policy_id=raw.get("trading_approval_policy_id"),
            trading_approval_policy_generation=raw.get(
                "trading_approval_policy_generation"
            ),
            trading_approval_policy_digest=raw.get("trading_approval_policy_digest"),
            result=result,
            reason_codes=tuple(raw.get("reason_codes", ())),
            approved_intent_envelope_id=raw.get("approved_intent_envelope_id"),
            approved_intent_envelope_digest=raw.get("approved_intent_envelope_digest"),
            max_decision_age_ms=raw.get("max_decision_age_ms"),
            invalidation_generation=raw.get("invalidation_generation"),
            supersedes_decision_id=raw.get("supersedes_decision_id"),
        )
    except KeyError as exc:
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: {path} is missing required field {exc}"
        ) from exc
    assert isinstance(decision, IndependentApprovalDecision)
    return decision


def load_operator_approval_file(
    path: Path,
    *,
    expected_owner_uid: int,
    environment_label: str | None,
    canonicalization_version: str = EV_L1_PROVISIONAL_VERSION,
    getuid: Callable[[], int] = os.getuid,
) -> IndependentApprovalDecision:
    """Load one operator-authored approval file into an"""
    raw = _load_raw_approval_mapping(
        path, expected_owner_uid=expected_owner_uid, getuid=getuid
    )
    _verify_environment_label(raw, path, environment_label)
    scheme = get_scheme(canonicalization_version)
    return _build_decision_from_raw(
        raw, path, scheme, age_check=_refuse_max_decision_age_ms_without_a_receipt
    )


@dataclass(frozen=True)
class LoadedApproval:
    """A decision plus the receipt-time facts needed to evaluate its expiry"""

    decision: IndependentApprovalDecision
    issued_at_unix_ms: int | None
    receipt_continuity: TimeContinuityIdentity | None
    receipt_anchor: ConsumerReceiptAnchor | None
    issuer_signed_age_ms: int | None
    issuer_age_uncertainty_ms: int | None


def load_operator_approval_with_receipt(
    path: Path,
    *,
    time: TimeSnapshotReader,
    time_config: TrustworthyTimeConfig,
    expected_owner_uid: int,
    environment_label: str | None,
    canonicalization_version: str = EV_L1_PROVISIONAL_VERSION,
    getuid: Callable[[], int] = os.getuid,
) -> LoadedApproval:
    """Load one approval file AND capture the receipt-time facts its"""
    raw = _load_raw_approval_mapping(
        path, expected_owner_uid=expected_owner_uid, getuid=getuid
    )
    _verify_environment_label(raw, path, environment_label)
    scheme = get_scheme(canonicalization_version)
    decision = _build_decision_from_raw(
        raw, path, scheme, age_check=_check_decision_age_requires_issued_at
    )
    issued_at = raw.get("issued_at_unix_ms")

    try:
        snapshot = time.current_snapshot()
    except TimeServiceNotStarted:
        snapshot = None

    receipt_continuity: TimeContinuityIdentity | None = None
    receipt_anchor: ConsumerReceiptAnchor | None = None
    issuer_signed_age_ms: int | None = None
    wall_now: int | None = None
    if snapshot is not None:
        receipt_continuity = snapshot.time_continuity_identity
        receipt_anchor = ConsumerReceiptAnchor(
            consumer_monotonic_continuity_id=receipt_continuity.monotonic_anchor_id,
            consumer_local_monotonic_value_at_receipt=(
                receipt_continuity.monotonic_anchor_value
            ),
        )
        wall_now = snapshot.wall_clock_observation

    if issued_at is not None and wall_now is not None:
        tolerance = time_config.max_future_timestamp_tolerance_ms
        if issued_at > wall_now + tolerance:
            raise OperatorApprovalFileError(
                f"load_operator_approval_with_receipt: {path} "
                f"'issued_at_unix_ms'={issued_at!r} is more than {tolerance}ms "
                f"ahead of the receipt wall-clock ({wall_now!r}) — refusing a "
                "future-dated approval (MAX_future_timestamp_tolerance_ms)"
            )
        issuer_signed_age_ms = wall_now - issued_at

    return LoadedApproval(
        decision=decision,
        issued_at_unix_ms=issued_at,
        receipt_continuity=receipt_continuity,
        receipt_anchor=receipt_anchor,
        issuer_signed_age_ms=issuer_signed_age_ms,
        issuer_age_uncertainty_ms=time_config.max_clock_domain_conversion_uncertainty_ms,
    )


def _consumer_elapsed_since_receipt(
    receipt_continuity: TimeContinuityIdentity, continuity_now: TimeContinuityIdentity
) -> int | None:
    """Kernel ``elapsed_within_continuity`` over the two continuities' own"""
    return elapsed_within_continuity(
        MonotonicReading(
            monotonic_continuity_id=receipt_continuity.monotonic_anchor_id,
            local_monotonic_value=receipt_continuity.monotonic_anchor_value,
        ),
        MonotonicReading(
            monotonic_continuity_id=continuity_now.monotonic_anchor_id,
            local_monotonic_value=continuity_now.monotonic_anchor_value,
        ),
    )


@dataclass(frozen=True)
class ConsumeResult:
    """The outcome of one :meth:`IntentRegistry.consume` call."""

    status: ConsumptionStatus
    outcome: ConsumptionOutcome | None
    record: ApprovalConsumptionRecord | None
    log_result: AppendReceipt | AppendRefusal | None


class IntentRegistry:
    """The Independent Approval Intent Registry (design #40 §5 order 4 item 3)."""

    def __init__(
        self,
        log: SqliteCommitLog,
        evidence: Any,
        *,
        writer_epoch: int,
        trading_approval_policy_generation: int,
        canonicalization_version: str = EV_L1_PROVISIONAL_VERSION,
        time: TimeSnapshotReader | None = None,
        time_config: TrustworthyTimeConfig | None = None,
    ) -> None:
        """Compose the registry over its injected ports."""
        self._log = log
        self._evidence = evidence
        self._writer_epoch = writer_epoch
        self._trading_approval_policy_generation = trading_approval_policy_generation
        self._scheme: CanonicalizationScheme = get_scheme(canonicalization_version)
        self._time = time
        self._time_config = time_config

    def propose(
        self,
        request: ProposalApprovalRequest,
        policy: TradingApprovalPolicy | None,
    ) -> ApprovalResult:
        """Evaluate request completeness (§9) — grants nothing, commits nothing."""
        result = request_is_complete(request, policy)
        self._evidence.append(
            {"request_id": request.request_id, "result": result.value},
            kind=_EVIDENCE_KIND_PROPOSAL,
            record_class=_EVIDENCE_KIND_PROPOSAL,
        )
        return result

    def approve(
        self, decision: IndependentApprovalDecision
    ) -> IndependentApprovalDecision:
        """Register receipt of an already-decided decision (zero auto-approval)."""
        self._evidence.append(
            {
                "decision_id": decision.decision_id,
                "result": None if decision.result is None else decision.result.value,
            },
            kind=_EVIDENCE_KIND_DECISION,
            record_class=_EVIDENCE_KIND_DECISION,
        )
        return decision

    def _current_consumption(
        self, decision: IndependentApprovalDecision
    ) -> tuple[ConsumptionStatus, str | None, str | None]:
        """Derive ``(status, prior_command_identity, prior_command_digest)`` from the log."""
        entry_command_id = _consumption_command_id(decision)
        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        for entry in view.entries:
            if entry.command_id != entry_command_id:
                continue
            if entry.kind is not _CONSUMPTION_KIND:
                raise CommitLogCorruption(
                    "IntentRegistry._current_consumption: entry "
                    f"{entry.command_id!r} matches this decision's own "
                    f"consumption command-id but kind={entry.kind!r} is not "
                    f"{_CONSUMPTION_KIND!r} — refusing to silently treat it as "
                    "unconsumed (fail-closed; kernel round #1 §2.1)"
                )
            return (
                ConsumptionStatus.CONSUMED,
                entry.command_id,
                entry.command_digest,
            )
        return ConsumptionStatus.ELIGIBLE, None, None

    def decision_current(
        self,
        decision: IndependentApprovalDecision,
        *,
        receipt: LoadedApproval | None = None,
    ) -> bool | None:
        """Whether ``decision`` is current (module docstring "decision"""
        if decision.trading_approval_policy_generation is None:
            return None
        if (
            decision.trading_approval_policy_generation
            != self._trading_approval_policy_generation
        ):
            return False
        if decision.request_id is None or decision.decision_generation is None:
            return None
        try:
            view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        except (StaleEpochRead, sqlite3.Error):
            return None
        prefix = f"{_CONSUMPTION_PREFIX}:{decision.request_id}:"
        for entry in view.entries:
            if entry.command_id is None or not entry.command_id.startswith(prefix):
                continue
            if entry.kind is not _CONSUMPTION_KIND:
                raise CommitLogCorruption(
                    "IntentRegistry.decision_current: entry "
                    f"{entry.command_id!r} matches the consumption prefix for "
                    f"request_id={decision.request_id!r} but kind="
                    f"{entry.kind!r} is not {_CONSUMPTION_KIND!r} — refusing to "
                    "silently skip a legacy/foreign-kind entry under this "
                    "prefix (fail-closed; kernel round #1 §2.1)"
                )
            generation_str, _, _decision_id = entry.command_id[len(prefix) :].partition(
                ":"
            )
            try:
                other_generation = int(generation_str)
            except ValueError:
                continue
            if other_generation > decision.decision_generation:
                return False
        expiry_ok, _age_bound_ms = self._expiry_verdict(decision, receipt)
        return expiry_ok is not False

    def _expiry_verdict(
        self,
        decision: IndependentApprovalDecision,
        receipt: LoadedApproval | None,
    ) -> tuple[bool | None, int | None]:
        """Kernel-predicate-driven decision-expiry verdict (kernel round #1"""
        if decision.max_decision_age_ms is None:
            return None, None
        if (
            receipt is None
            or self._time is None
            or self._time_config is None
            or receipt.receipt_continuity is None
            or receipt.receipt_anchor is None
            or receipt.issuer_signed_age_ms is None
            or receipt.issuer_age_uncertainty_ms is None
        ):
            return False, None
        try:
            snapshot = self._time.current_snapshot()
        except TimeServiceNotStarted:
            return False, None
        if snapshot.health_state is not HealthState.TRUSTED:
            return False, None
        continuity_now = snapshot.time_continuity_identity
        age_bound = effective_snapshot_age_bound_from_continuity(
            snapshot,
            receipt.receipt_anchor,
            consumer_continuity_now=continuity_now,
            consumer_anchor=receipt.receipt_continuity,
            suspension_ms=snapshot.suspension_status.suspension_ms,
            max_suspension_ms=self._time_config.max_process_suspension_ms,
            issuer_signed_age=receipt.issuer_signed_age_ms,
            issuer_age_uncertainty=receipt.issuer_age_uncertainty_ms,
            transport_bound=self._time_config.max_time_transport_and_queue_uncertainty_ms,
            queue_bound=0,
            conversion_bound=self._time_config.max_clock_domain_conversion_uncertainty_ms,
            consumer_elapsed_since_receipt=_consumer_elapsed_since_receipt(
                receipt.receipt_continuity, continuity_now
            ),
        )
        return (
            decision_unexpired(
                max_decision_age_ms=decision.max_decision_age_ms,
                decision_age_bound_ms=age_bound,
            ),
            age_bound,
        )

    def _expiry_evidence_fields(
        self,
        decision: IndependentApprovalDecision,
        receipt: LoadedApproval | None,
    ) -> dict[str, Any]:
        """Consumption-evidence fields for the decision-expiry verdict"""
        expiry_ok, age_bound_ms = self._expiry_verdict(decision, receipt)
        if expiry_ok is None:
            expiry_verdict = "NOT_CONFIGURED"
        elif expiry_ok is True:
            expiry_verdict = "UNEXPIRED"
        else:
            expiry_verdict = "EXPIRED_OR_UNVERIFIABLE"
        receipt_anchor = (
            None
            if receipt is None or receipt.receipt_anchor is None
            else receipt.receipt_anchor.model_dump(mode="json")
        )
        return {
            "expiry_verdict": expiry_verdict,
            "age_bound_ms": age_bound_ms,
            "receipt_anchor": receipt_anchor,
        }

    def consume(
        self,
        decision: IndependentApprovalDecision,
        *,
        command_identity: str,
        command_digest: str,
        decision_current: bool | None,
        approved_intent_envelope_equivalent: bool | None,
        intent_identity: str | None = None,
        bound_chain: Mapping[str, str | None] | None = None,
        actual_chain: Mapping[str, str | None] | None = None,
        receipt: LoadedApproval | None = None,
    ) -> ConsumeResult:
        """Attempt the single-use consumption of ``decision`` (§12; IAP-INV-006)."""
        rejection = self._check_binding(bound_chain, actual_chain)
        if rejection is not None:
            return rejection

        current_status, prior_identity, prior_digest = self._current_consumption(
            decision
        )
        predicted_status, predicted_outcome = consumption_transition(
            current_status=current_status,
            decision_result=(
                ApprovalResult.DENY if decision.result is None else decision.result
            ),
            decision_current=decision_current,
            approved_intent_envelope_equivalent=approved_intent_envelope_equivalent,
            command_identity=command_identity,
            command_digest=command_digest,
            prior_command_identity=prior_identity,
            prior_command_digest=prior_digest,
        )
        if predicted_outcome is ConsumptionOutcome.REJECTED_INELIGIBLE:
            return ConsumeResult(
                status=predicted_status,
                outcome=predicted_outcome,
                record=None,
                log_result=None,
            )

        log_result, final_outcome, final_record = self._commit_consumption(
            decision,
            command_digest=command_digest,
            intent_identity=intent_identity,
            predicted_outcome=predicted_outcome,
        )
        self._evidence.append(
            {
                "decision_id": decision.decision_id,
                "command_identity": command_identity,
                "outcome": None if final_outcome is None else final_outcome.value,
                **self._expiry_evidence_fields(decision, receipt),
            },
            kind=_EVIDENCE_KIND_CONSUMPTION,
            record_class=_EVIDENCE_KIND_CONSUMPTION,
        )
        return ConsumeResult(
            status=(
                ConsumptionStatus.CONSUMED
                if final_outcome is not None
                else current_status
            ),
            outcome=final_outcome,
            record=final_record,
            log_result=log_result,
        )

    @staticmethod
    def _check_binding(
        bound_chain: Mapping[str, str | None] | None,
        actual_chain: Mapping[str, str | None] | None,
    ) -> ConsumeResult | None:
        """The exact-binding-chain pre-check (§13), run BEFORE any log"""
        if bound_chain is None:
            return None
        binding = exact_binding_holds(bound_chain, actual_chain or {})
        if binding is ApprovalResult.APPROVE:
            return None
        return ConsumeResult(
            status=ConsumptionStatus.ELIGIBLE,
            outcome=ConsumptionOutcome.REJECTED_INELIGIBLE,
            record=None,
            log_result=None,
        )

    def _commit_consumption(
        self,
        decision: IndependentApprovalDecision,
        *,
        command_digest: str,
        intent_identity: str | None,
        predicted_outcome: ConsumptionOutcome,
    ) -> tuple[
        AppendReceipt | AppendRefusal,
        ConsumptionOutcome | None,
        ApprovalConsumptionRecord | None,
    ]:
        """Issue the :class:`~tos.iap.ApprovalConsumptionRecord` and commit it"""
        record = ApprovalConsumptionRecord.issue(
            scheme=self._scheme,
            consumption_record_id=_consumption_command_id(decision),
            consumption_generation=decision.decision_generation or 1,
            decision_id=decision.decision_id,
            decision_digest=decision.canonical_digest,
            request_id=decision.request_id,
            request_digest=decision.request_digest,
            intent_identity=intent_identity,
            policy_generation=decision.trading_approval_policy_generation,
            writer_epoch=self._writer_epoch,
            result=decision.result,
            consumption_status=ConsumptionStatus.CONSUMED,
        )
        assert isinstance(record, ApprovalConsumptionRecord)
        payload_json = json.dumps(record.model_dump(mode="json"), sort_keys=True)
        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        expected_seq = -1 if view.last_seq is None else view.last_seq
        entry = CommitEntry(
            command_id=record.consumption_record_id,
            command_digest=command_digest,
            kind=_CONSUMPTION_KIND,
        )
        log_result = self._log.append_cas(
            entry,
            expected_seq=expected_seq,
            writer_epoch=self._writer_epoch,
            payload_json=payload_json,
        )
        final_outcome, final_record = self._resolve_append_outcome(
            log_result, predicted_outcome, record
        )
        return log_result, final_outcome, final_record

    @staticmethod
    def _resolve_append_outcome(
        log_result: AppendReceipt | AppendRefusal,
        predicted_outcome: ConsumptionOutcome,
        record: ApprovalConsumptionRecord,
    ) -> tuple[ConsumptionOutcome | None, ApprovalConsumptionRecord | None]:
        """Translate the log's own CAS verdict into the final consumption outcome."""
        from tos.rcl import AppendRefusalReason

        if isinstance(log_result, AppendReceipt):
            return ConsumptionOutcome.CONSUMED_NEW, record
        if log_result.reason is AppendRefusalReason.DUPLICATE_COMMAND_ID:
            return ConsumptionOutcome.IDEMPOTENT_REPLAY, record
        if log_result.reason is AppendRefusalReason.COMMAND_BYTES_MISMATCH:
            return ConsumptionOutcome.REJECTED_CONFLICT, None
        del predicted_outcome
        return None, None
