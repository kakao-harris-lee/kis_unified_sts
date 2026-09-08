"""``IntentRegistry`` — the Independent Approval / Intent Registry runtime
(design #40 §5 order 4 item 3; ADR-002-023).

**Zero auto-approval code (plan directive, DR-0001 §17.1 single-operator
variant).** The Phase 2 independent approver is an **operator-authored
approval file** under ``approvals/<proposal_digest>.yaml`` — never a
computation this module performs. :func:`load_operator_approval_file` reuses
the exact same 0600-mode + owner-uid custody rule
(:func:`tos_runtime.custody.file_custody.verify_file_mode_and_owner`) plus an
environment-label check, then parses whatever ``result``
(``APPROVE``/``DENY``/``UNKNOWN``) the operator wrote **verbatim** into an
:class:`~tos.iap.IndependentApprovalDecision` — there is no branch anywhere in
this module that computes ``APPROVE``. :meth:`IntentRegistry.approve` records
receipt of an already-decided decision; it does not decide.

**Single-use consumption is log-enforced, not memory-enforced.**
:meth:`IntentRegistry.consume` performs exactly **one** ``append_cas`` whose
success (or ``DUPLICATE_COMMAND_ID``/``COMMAND_BYTES_MISMATCH`` refusal) *is*
the consumption outcome — the entry's ``command_id`` is content-addressed as
``f"iap-consumption:{request_id}:{decision_generation}:{decision_id}"``
(:func:`_consumption_command_id`), fixed per decision regardless of who
calls ``consume`` or how many times (the ``request_id``/``decision_generation``
prefix is what lets :meth:`IntentRegistry.decision_current` derive
proposal-scoped supersession from the log with no payload readback — see
that method's own docstring). A second consumption attempt against the same
decision therefore collides on the log's own ``entries.command_id``
``UNIQUE`` constraint — enforced by :class:`~tos_runtime.rcl.log.SqliteCommitLog`
itself, not by an in-memory flag this class holds — so a freshly re-created
:class:`IntentRegistry` over the SAME log (a simulated restart) refuses the
second consumption identically to the still-running first instance would
have.

**Decision currency has no kernel predicate (2026-09-08).**
``tos.iap.predicates.approval_decision``/``tos.iap.state.consumption_transition``
both take ``decision_current``/``generation_current`` as an **injected**
``bool | None`` — ADR-002-023 §12 item 2 names "current governed policy
generations" as a required fact but no ``tos.iap`` function computes it.
:meth:`IntentRegistry.decision_current` is therefore this module's own input
collection, not a kernel call: it authors exactly one comparison (equality
of the decision's ``trading_approval_policy_generation`` against the
registry's configured, currently-loaded value) plus one log-derived
supersession check (a later-generation decision for the same proposal
already consumed) — never anything more permissive than those two facts.

**Reported ``CommandType`` gap (slice plan §5).** No member of the closed
``tos.rcl.vocabulary.CommandType`` vocabulary names "consume an Independent
Approval decision, once". The closest structural analog is
:data:`~tos.rcl.vocabulary.CommandType.CONSUME_TRANSMISSION_CAPABILITY` — also
a single-use, once-only consumption of an authorization token, durably
committed — even though its named referent (the RCL Transmission Capability
nonce, ADR-002-002 §27) is a different governed artifact from an Independent
Approval decision (ADR-002-023). Reported, not resolved by a kernel edit: this
module never touches ``tos.rcl.vocabulary``.
"""

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
    exact_binding_holds,
    request_is_complete,
)
from tos.rcl import AppendReceipt, AppendRefusal, CommandType, CommitEntry

from tos_runtime.custody.file_custody import verify_file_mode_and_owner
from tos_runtime.rcl.log import SqliteCommitLog, StaleEpochRead

__all__ = [
    "ConsumeResult",
    "IntentRegistry",
    "OperatorApprovalFileError",
    "load_operator_approval_file",
]

#: Command-id prefix for every IAP consumption entry — see the module
#: docstring's "single-use consumption is log-enforced" section.
_CONSUMPTION_PREFIX = "iap-consumption"

#: The reported-gap ``CommandType`` choice (module docstring).
_CONSUMPTION_KIND = CommandType.CONSUME_TRANSMISSION_CAPABILITY

_EVIDENCE_KIND_PROPOSAL = "IAP_PROPOSAL"
_EVIDENCE_KIND_DECISION = "IAP_DECISION_REGISTERED"
_EVIDENCE_KIND_CONSUMPTION = "IAP_CONSUMPTION"


def _consumption_command_id(decision: IndependentApprovalDecision) -> str:
    """The content-addressed, log-visible id one decision's consumption commits under.

    Encodes ``(request_id, decision_generation, decision_id)`` — never merely
    ``decision_id`` — so :meth:`IntentRegistry.decision_current` can derive
    proposal-scoped supersession purely from log-visible ``command_id``
    strings (that method's own docstring), with no payload readback. A blank
    ``request_id`` still yields a stable, decision-unique id (the
    ``decision_generation``/``decision_id`` suffix alone is already unique
    per decision) — it only forfeits proposal-scoped grouping, which
    :meth:`IntentRegistry.decision_current` handles by returning ``None``
    (undetermined) rather than risk grouping unrelated decisions under a
    shared blank request id.
    """
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
    """Checks 1-3 of :func:`load_operator_approval_file`: custody gate, read,
    parse (split out for the 100-line function size budget, 2026-09-08 —
    pure extraction, no behavioural change; the custody gate still runs
    strictly before any YAML parsing, mirroring
    :meth:`~tos_runtime.custody.file_custody.FileCustody.load`'s own
    "checks run before the file is opened" discipline)."""
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


def _build_decision_from_raw(
    raw: Mapping[str, Any], path: Path, scheme: CanonicalizationScheme
) -> IndependentApprovalDecision:
    """Check 5 + construction: parse ``result`` verbatim and issue the decision
    (split out of :func:`load_operator_approval_file` for the size budget)."""
    try:
        result = ApprovalResult(raw["result"])
    except (KeyError, ValueError) as exc:
        raise OperatorApprovalFileError(
            f"load_operator_approval_file: {path} 'result' is missing or not one "
            f"of APPROVE/DENY/UNKNOWN: {exc}"
        ) from exc
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
    """Load one operator-authored approval file into an
    :class:`~tos.iap.IndependentApprovalDecision` (module docstring; DR-0001 §17.1).

    Zero auto-approval: every field of the returned decision — including its
    ``result`` — is copied verbatim from ``path``'s own YAML content. This
    function never computes ``APPROVE``/``DENY``/``UNKNOWN`` itself.

    Args:
        path: The ``approvals/<proposal_digest>.yaml`` file.
        expected_owner_uid: The uid both the file's owner and the calling
            process itself are expected to be (custody's own 0600 rule,
            reused verbatim — see
            :func:`tos_runtime.custody.file_custody.verify_file_mode_and_owner`).
        environment_label: This runtime's own boot-argument environment
            label; the file's own ``environment_label`` field must match it
            byte-exact (never an ambient env read).
        canonicalization_version: The registered ``tos.canonical`` scheme
            version the decision is issued/digested under.
        getuid: An ``os.getuid``-shaped callable, injectable for tests.

    Returns:
        The issued, digest-verified :class:`~tos.iap.IndependentApprovalDecision`.

    Raises:
        OperatorApprovalFileError: The mode/owner check fails, the file is
            unreadable/not YAML/not a mapping, the environment label does not
            match, or the file omits a field the decision requires.
    """
    raw = _load_raw_approval_mapping(
        path, expected_owner_uid=expected_owner_uid, getuid=getuid
    )
    _verify_environment_label(raw, path, environment_label)
    scheme = get_scheme(canonicalization_version)
    return _build_decision_from_raw(raw, path, scheme)


@dataclass(frozen=True)
class ConsumeResult:
    """The outcome of one :meth:`IntentRegistry.consume` call.

    ``outcome`` is ``None`` only when the log itself could not be reached
    (stale epoch / seq mismatch / store unavailable) — a genuinely
    ``UNKNOWN``-shaped result distinct from every consumption-state outcome
    the kernel state machine can produce (module docstring).
    """

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
    ) -> None:
        """Compose the registry over its injected ports.

        Args:
            log: The Safety Commit Log every consumption is committed through
                (``append_cas`` only).
            evidence: The durable append port this registry's own
                domain-labelled records are committed through.
            writer_epoch: The RCL Writer Epoch this instance's ``append_cas``
                calls are fenced under.
            trading_approval_policy_generation: The currently-loaded
                :class:`~tos.iap.TradingApprovalPolicy`'s own
                ``policy_generation`` (:func:`~tos_runtime.authority.epoch.load_authority_config`'s
                ``trading_approval_policy_generation`` key — null refuses to
                start; module docstring's "decision currency" section).
                :meth:`decision_current` compares a decision's own
                ``trading_approval_policy_generation`` against this value.
            canonicalization_version: The registered ``tos.canonical`` scheme
                version used to digest every issued
                :class:`~tos.iap.ApprovalConsumptionRecord`.
        """
        self._log = log
        self._evidence = evidence
        self._writer_epoch = writer_epoch
        self._trading_approval_policy_generation = trading_approval_policy_generation
        self._scheme: CanonicalizationScheme = get_scheme(canonicalization_version)

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
        """Register receipt of an already-decided decision (zero auto-approval).

        ``decision.result`` was fixed entirely by
        :func:`load_operator_approval_file` (or an equivalent operator-file
        loader) — this method computes nothing; it only evidences receipt so
        the decision's arrival is durably recorded before any consumption
        attempt.
        """
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
            if entry.kind is _CONSUMPTION_KIND and entry.command_id == entry_command_id:
                return (
                    ConsumptionStatus.CONSUMED,
                    entry.command_id,
                    entry.command_digest,
                )
        return ConsumptionStatus.ELIGIBLE, None, None

    def decision_current(self, decision: IndependentApprovalDecision) -> bool | None:
        """Whether ``decision`` is current (module docstring's "decision
        currency has no kernel predicate" section; ADR-002-023 §12 item 2).

        The runtime's own input collection — exactly two checks, no more:

        1. **Equality of generation identifiers** (the only comparison
           authored here): ``decision.trading_approval_policy_generation``
           must equal this registry's configured, currently-loaded
           :class:`~tos.iap.TradingApprovalPolicy` generation.
        2. **Log-derived proposal-scoped supersession**: no later-generation
           decision for the SAME ``request_id`` has already been consumed
           (a durable, restart-surviving check — supersession is detected
           only once a newer decision has itself been consumed, since a mere
           :meth:`approve` registration is evidence-only, not RCL-committed;
           this is a real, documented limitation, not hidden).

        Args:
            decision: The decision to check.

        Returns:
            ``True`` only when both checks pass. ``False`` when the policy
            generation mismatches, or a later decision for the same proposal
            was already consumed. ``None`` when the decision carries no
            ``trading_approval_policy_generation`` at all, when it carries no
            ``request_id``/``decision_generation`` (proposal-scoped
            supersession is then undeterminable — never assumed clear), or
            when the log itself could not be read (stale epoch / unreachable
            — genuinely unknown, never coerced to ``True`` or ``False``).
        """
        if decision.trading_approval_policy_generation is None:
            return None
        if (
            decision.trading_approval_policy_generation
            != self._trading_approval_policy_generation
        ):
            return False
        if decision.request_id is None or decision.decision_generation is None:
            # Proposal-scoped supersession cannot be grouped without a
            # request_id, and there is no generation of THIS decision to
            # compare a later one against — undetermined, never assumed clear.
            return None
        try:
            view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        except (StaleEpochRead, sqlite3.Error):
            return None
        prefix = f"{_CONSUMPTION_PREFIX}:{decision.request_id}:"
        for entry in view.entries:
            if entry.kind is not _CONSUMPTION_KIND or entry.command_id is None:
                continue
            if not entry.command_id.startswith(prefix):
                continue
            generation_str, _, _decision_id = entry.command_id[len(prefix) :].partition(
                ":"
            )
            try:
                other_generation = int(generation_str)
            except ValueError:
                continue  # malformed id from an unrelated caller — never trusted
            if other_generation > decision.decision_generation:
                return False
        return True

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
    ) -> ConsumeResult:
        """Attempt the single-use consumption of ``decision`` (§12; IAP-INV-006).

        Args:
            decision: The decision to consume (``decision.decision_id`` fixes
                the log's dedup key, module docstring).
            command_identity: The consuming command's own identity (recorded
                for evidence; the log-level dedup key is decision-scoped, not
                this value — module docstring).
            command_digest: The consuming command's canonical digest — this
                IS the log's CAS dedup comparator (same digest twice =>
                idempotent replay; a different digest against an
                already-consumed decision => conflict).
            decision_current: Injected currentness fact for the decision
                (``None``/``False`` => not consumable, fail-closed).
            approved_intent_envelope_equivalent: Injected envelope-equivalence
                fact (``None``/``False`` => not consumable).
            intent_identity: The orthostate Intent identity this consumption
                binds, if known.
            bound_chain: Optional exact-binding-chain check (§13) run BEFORE
                any log interaction — a binding failure never reaches the
                log.
            actual_chain: The actual artifacts' chain, paired with
                ``bound_chain``.

        Returns:
            The :class:`ConsumeResult`.
        """
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
        """The exact-binding-chain pre-check (§13), run BEFORE any log
        interaction (split out of :meth:`consume` for the size budget).

        Returns:
            A rejecting :class:`ConsumeResult` when ``bound_chain`` is
            supplied and does not hold, else ``None`` to proceed.
        """
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
        """Issue the :class:`~tos.iap.ApprovalConsumptionRecord` and commit it
        via ``append_cas`` (split out of :meth:`consume` for the size budget —
        the transaction is the log's own single ``append_cas`` call, unchanged
        by this extraction)."""
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
        """Translate the log's own CAS verdict into the final consumption outcome.

        The log's ``DUPLICATE_COMMAND_ID``/``COMMAND_BYTES_MISMATCH`` split IS
        the kernel ``classify_record_pair`` classification the predicted
        outcome already anticipated (module docstring) — this only maps the
        log's structural refusal reason onto the matching
        :class:`~tos.iap.ConsumptionOutcome` member; it never re-derives the
        classification independently.
        """
        from tos.rcl import AppendRefusalReason

        if isinstance(log_result, AppendReceipt):
            return ConsumptionOutcome.CONSUMED_NEW, record
        if log_result.reason is AppendRefusalReason.DUPLICATE_COMMAND_ID:
            return ConsumptionOutcome.IDEMPOTENT_REPLAY, record
        if log_result.reason is AppendRefusalReason.COMMAND_BYTES_MISMATCH:
            return ConsumptionOutcome.REJECTED_CONFLICT, None
        # STALE_EPOCH / SEQ_MISMATCH / STORE_UNAVAILABLE / PARTIAL_COMMIT_SUSPECTED:
        # the log itself could not be reached/committed — genuinely unknown, never
        # forced into one of the consumption-state outcomes above.
        del predicted_outcome
        return None, None
