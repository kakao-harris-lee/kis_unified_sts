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

**Decision expiry runtime path (kernel round #1 §1.2/§2.2, resolving the
2026-09-08 re-review MEDIUM).** ADR-002-023 §12 item 2 requires a consumed
decision be "current, **unexpired**". ``tos.iap`` stays clock-free; kernel
round #1 §1.2 added :func:`tos.iap.decision_unexpired` — a pure, fail-closed
predicate over an already-composed ``(max_decision_age_ms,
decision_age_bound_ms)`` pair, isomorphic to
:func:`tos.time.snapshot_age_admissible`. This module composes that bound,
ONLY via kernel ``tos.time`` predicates, in three steps:

1. **Load**: a non-``null`` ``max_decision_age_ms`` now REQUIRES the file's
   new optional ``issued_at_unix_ms`` field
   (:func:`_check_decision_age_requires_issued_at`, replacing the prior
   unconditional refusal); absence still refuses. ``None`` is unaffected.
2. **Receipt** (:func:`load_operator_approval_with_receipt`, a NEW, ADDITIONAL
   loader — :func:`load_operator_approval_file` keeps its exact prior
   signature/return type): captures this process's own continuity + a
   :class:`~tos.time.ConsumerReceiptAnchor` from the injected
   :class:`~tos_runtime.time.service.TrustworthyTimeService`, refuses a
   future-dated ``issued_at_unix_ms``, and returns a :class:`LoadedApproval`
   wrapping the kernel decision plus these receipt-time facts — the kernel
   :class:`~tos.iap.IndependentApprovalDecision` itself is NOT edited.
3. **Consumption** (:meth:`IntentRegistry.decision_current` /
   :meth:`IntentRegistry.consume`, both gaining an optional ``receipt:
   LoadedApproval | None``): ``max_decision_age_ms is None`` keeps prior
   behaviour (evidence records ``NOT_CONFIGURED``); non-``None`` composes an
   age bound via kernel
   :func:`tos.time.effective_snapshot_age_bound_from_continuity` from the
   current vs. receipt-time continuity and the injected ``time_config``
   bounds, then calls :func:`~tos.iap.decision_unexpired`. A ``None`` bound
   (time not ``TRUSTED``, not started, or incomplete ``receipt``/``time``/
   ``time_config``) is fail-closed ``False``. Evidence carries the receipt
   anchor, age bound, and expiry verdict.

Every existing caller (``time``/``time_config`` omitted) keeps working
unchanged as long as its files keep ``max_decision_age_ms`` ``null``.

**Reported ``CommandType`` gap — resolved by kernel round #1 (plan §1.1).**
This module previously reused :data:`~tos.rcl.vocabulary.CommandType.CONSUME_TRANSMISSION_CAPABILITY`
(a different governed artifact, the RCL Transmission Capability nonce) as the
closest structural analog for "consume an Independent Approval decision,
once" — no closed ``CommandType`` member named that act. Kernel round #1
§1.1 ratified a dedicated member,
:data:`~tos.rcl.vocabulary.CommandType.CONSUME_APPROVAL_DECISION`; this
module now writes/reads exclusively under it (the old reuse retired, §2.1).
Both :meth:`IntentRegistry._current_consumption` (exact match) and the
supersession scan in :meth:`IntentRegistry.decision_current` (prefix match)
raise :class:`~tos_runtime.rcl.log.CommitLogCorruption` on a matching entry
whose ``kind`` is NOT that member — never silently read as "not yet
consumed" / "no supersession" (either would be a fail-open).
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

from tos_runtime.custody.file_custody import verify_file_mode_and_owner
from tos_runtime.rcl.log import CommitLogCorruption, SqliteCommitLog, StaleEpochRead
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TimeServiceNotStarted, TrustworthyTimeService

__all__ = [
    "ConsumeResult",
    "IntentRegistry",
    "LoadedApproval",
    "OperatorApprovalFileError",
    "load_operator_approval_file",
    "load_operator_approval_with_receipt",
]

#: Command-id prefix for every IAP consumption entry — see the module
#: docstring's "single-use consumption is log-enforced" section.
_CONSUMPTION_PREFIX = "iap-consumption"

#: The dedicated ``CommandType`` member for a single IAP consumption (kernel
#: round #1 §1.1/§2.1 — module docstring).
_CONSUMPTION_KIND = CommandType.CONSUME_APPROVAL_DECISION

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


def _check_decision_age_requires_issued_at(raw: Mapping[str, Any], path: Path) -> None:
    """Require ``issued_at_unix_ms`` whenever ``max_decision_age_ms`` is set
    (kernel round #1 §2.2 — replaces the prior unconditional refusal, 2026-09-08
    re-review MEDIUM).

    Kernel round #1 §1.2 provisioned :func:`tos.iap.decision_unexpired`, so a
    non-``null`` ``max_decision_age_ms`` is no longer refused outright — but
    it is only enforceable once the operator records WHEN the decision was
    issued, so :func:`load_operator_approval_with_receipt` can compose a real
    age bound (module docstring). Absent ``issued_at_unix_ms``, this function
    refuses exactly as its predecessor did. ``None``/absent
    ``max_decision_age_ms`` stays accepted regardless.
    """
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


def _build_decision_from_raw(
    raw: Mapping[str, Any], path: Path, scheme: CanonicalizationScheme
) -> IndependentApprovalDecision:
    """Check 5 + construction: parse ``result`` verbatim and issue the decision
    (split out of :func:`load_operator_approval_file` for the size budget)."""
    _check_decision_age_requires_issued_at(raw, path)
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
class LoadedApproval:
    """A decision plus the receipt-time facts needed to evaluate its expiry
    (kernel round #1 §2.2 — module docstring). The kernel
    :class:`~tos.iap.IndependentApprovalDecision` itself is NOT edited; these
    are runtime-side facts :func:`load_operator_approval_with_receipt`
    collects once, at load.

    ``receipt_continuity``/``receipt_anchor``/``issuer_signed_age_ms`` are
    ``None`` when they could not be established (time service not started,
    or no ``issued_at_unix_ms``) — a decision with a non-``None``
    ``max_decision_age_ms`` but an incomplete ``receipt`` fails closed at
    consumption, never admitted on a partial receipt.
    """

    decision: IndependentApprovalDecision
    issued_at_unix_ms: int | None
    receipt_continuity: TimeContinuityIdentity | None
    receipt_anchor: ConsumerReceiptAnchor | None
    issuer_signed_age_ms: int | None
    issuer_age_uncertainty_ms: int | None


def load_operator_approval_with_receipt(
    path: Path,
    *,
    time: TrustworthyTimeService,
    time_config: TrustworthyTimeConfig,
    expected_owner_uid: int,
    environment_label: str | None,
    canonicalization_version: str = EV_L1_PROVISIONAL_VERSION,
    getuid: Callable[[], int] = os.getuid,
) -> LoadedApproval:
    """Load one approval file AND capture the receipt-time facts its
    decision-expiry evaluation needs (kernel round #1 §2.2).

    An ADDITIONAL loader — :func:`load_operator_approval_file` keeps its
    exact prior signature/return type, so every existing caller is
    unaffected. Use this loader when the file may set a non-``null``
    ``max_decision_age_ms`` enforced at consumption via
    :meth:`IntentRegistry.decision_current`/:meth:`~IntentRegistry.consume`'s
    ``receipt`` parameter.

    **Honest gap**: ``time``'s ``current_snapshot()`` is meant to supply the
    receipt wall-clock reading (``TimeHealthSnapshot.wall_clock_observation``),
    but in the current build :class:`TrustworthyTimeService`'s FSM never
    populates that field (audit-only; no Phase 2 wiring reads a real wall
    clock into it yet). This function still faithfully composes whatever the
    snapshot reports — ``issuer_signed_age_ms`` stays ``None`` and expiry
    fails closed at consumption until a future round wires a real reading.
    Reported, not silently worked around.

    Args:
        path: The ``approvals/<proposal_digest>.yaml`` file.
        time: The injected :class:`~tos_runtime.time.service.TrustworthyTimeService`.
        time_config: The fully-valued time runtime config (future-timestamp
            tolerance + clock-domain-conversion-uncertainty bounds).
        expected_owner_uid: See :func:`load_operator_approval_file`.
        environment_label: See :func:`load_operator_approval_file`.
        canonicalization_version: See :func:`load_operator_approval_file`.
        getuid: See :func:`load_operator_approval_file`.

    Returns:
        The :class:`LoadedApproval`.

    Raises:
        OperatorApprovalFileError: Everything :func:`load_operator_approval_file`
            raises, plus a future-dated ``issued_at_unix_ms``.
    """
    raw = _load_raw_approval_mapping(
        path, expected_owner_uid=expected_owner_uid, getuid=getuid
    )
    _verify_environment_label(raw, path, environment_label)
    scheme = get_scheme(canonicalization_version)
    decision = _build_decision_from_raw(raw, path, scheme)
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
    """Kernel ``elapsed_within_continuity`` over the two continuities' own
    monotonic anchor coordinates (kernel round #1 §2.2) — never a runtime-
    authored subtraction; ``None`` (UNKNOWN) whenever the two do not share a
    concrete continuity (kernel predicate's own non-subtraction rule)."""
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
        time: TrustworthyTimeService | None = None,
        time_config: TrustworthyTimeConfig | None = None,
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
            time: The injected :class:`~tos_runtime.time.service.TrustworthyTimeService`
                (kernel round #1 §2.2 — module docstring's "decision expiry
                runtime path" section). Optional and defaulted to ``None``
                for every existing caller that never consumes a decision
                whose ``max_decision_age_ms`` is non-``None`` — such a
                decision fails closed (denied) if ``time``/``time_config`` is
                left ``None``.
            time_config: The fully-valued time runtime config (transport/
                queue/clock-domain-conversion bounds :meth:`decision_current`
                / :meth:`consume` compose an age bound from). Same optionality
                as ``time``.
        """
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
            if entry.command_id != entry_command_id:
                continue
            if entry.kind is not _CONSUMPTION_KIND:
                # An entry already sits at this decision's own consumption
                # identity under a DIFFERENT kind (e.g. the now-retired
                # CONSUME_TRANSMISSION_CAPABILITY reuse, or a foreign
                # writer) — never silently read as "not yet consumed": that
                # would let a second, differently-kinded consumption slip
                # through undetected (fail-open). Kernel round #1 §2.1.
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
        """Whether ``decision`` is current (module docstring "decision
        currency" + "decision expiry runtime path"; ADR-002-023 §12 item 2).

        Three checks: (1) equality of ``trading_approval_policy_generation``
        against this registry's configured value; (2) log-derived proposal-
        scoped supersession (no later-generation decision for the SAME
        ``request_id`` already consumed — detected only once consumed, a
        real documented limitation); (3) kernel-predicate expiry (kernel
        round #1 §2.2) — ``max_decision_age_ms is None`` skips this
        unaffected; non-``None`` composes an age bound via
        :func:`tos.time.effective_snapshot_age_bound_from_continuity` from
        ``receipt`` + this registry's ``time``/``time_config`` and calls
        :func:`tos.iap.decision_unexpired` (see :meth:`_expiry_verdict`).

        Args:
            decision: The decision to check.
            receipt: The :class:`LoadedApproval` from
                :func:`load_operator_approval_with_receipt` (``None`` is fine
                as long as ``decision.max_decision_age_ms`` is also ``None``).

        Returns:
            ``True`` only when every check passes. ``False`` on a generation
            mismatch, a later consumed decision for the same proposal, or an
            unproven expiry. ``None`` when currency is genuinely
            undeterminable (no generation/request_id, or the log could not be
            read) — never coerced to ``True``/``False``.
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
            if entry.command_id is None or not entry.command_id.startswith(prefix):
                continue
            if entry.kind is not _CONSUMPTION_KIND:
                # A prefix-matching entry under any OTHER kind (e.g. the
                # now-retired CONSUME_TRANSMISSION_CAPABILITY reuse, or a
                # foreign writer) is never silently skipped — that would hide
                # a real supersession (fail-open). Kernel round #1 §2.1.
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
                continue  # malformed id from an unrelated caller — never trusted
            if other_generation > decision.decision_generation:
                return False
        expiry_ok, _age_bound_ms = self._expiry_verdict(decision, receipt)
        return expiry_ok is not False

    def _expiry_verdict(
        self,
        decision: IndependentApprovalDecision,
        receipt: LoadedApproval | None,
    ) -> tuple[bool | None, int | None]:
        """Kernel-predicate-driven decision-expiry verdict (kernel round #1
        §2.2; ADR-002-023 §12 item 2 "unexpired" / §18). Shared by
        :meth:`decision_current` and :meth:`consume` so both compute it
        identically — the runtime only composes the coordinates
        :func:`tos.time.effective_snapshot_age_bound_from_continuity` and
        :func:`tos.iap.decision_unexpired` need and calls them.

        Returns ``(expiry_ok, age_bound_ms)``: ``(None, None)`` when
        ``max_decision_age_ms is None`` (unconfigured); ``(False, None)``
        when ``receipt``/``time``/``time_config`` are missing/incomplete,
        time is not ``TRUSTED``, or not started; else the kernel-composed
        ``(decision_unexpired result, age_bound_ms)`` pair.
        """
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
            suspension_ms=0,
            max_suspension_ms=self._time_config.max_process_suspension_ms,
            issuer_signed_age=receipt.issuer_signed_age_ms,
            issuer_age_uncertainty=receipt.issuer_age_uncertainty_ms,
            transport_bound=self._time_config.max_time_transport_and_queue_uncertainty_ms,
            # Phase 2's time config folds transport + queue delay into ONE
            # combined bound (MAX_time_transport_and_queue_uncertainty_ms) —
            # there is no separately-tracked queue-only key, so 0 here is a
            # concrete "already folded into transport_bound", never an
            # unbounded/None term (which would fail this closed instead).
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
        """Consumption-evidence fields for the decision-expiry verdict
        (kernel round #1 §2.2 — "소비 증거에 receipt_anchor·age_bound_ms·
        expiry_verdict 결속"). Never used to re-decide consumability — see
        :meth:`consume`'s ``receipt`` parameter docstring."""
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
                (``None``/``False`` => not consumable, fail-closed) — the
                caller's own :meth:`decision_current` result (already folds
                in expiry when ``receipt`` was passed to that call too).
            approved_intent_envelope_equivalent: Injected envelope-equivalence
                fact (``None``/``False`` => not consumable).
            intent_identity: The orthostate Intent identity this consumption
                binds, if known.
            bound_chain: Optional exact-binding-chain check (§13) run BEFORE
                any log interaction — a binding failure never reaches the
                log.
            actual_chain: The actual artifacts' chain, paired with
                ``bound_chain``.
            receipt: The same :class:`LoadedApproval` (if any) passed to
                :meth:`decision_current` (kernel round #1 §2.2) — only
                enriches consumption evidence (receipt anchor/age bound/
                expiry verdict); never re-decides consumability here.

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
