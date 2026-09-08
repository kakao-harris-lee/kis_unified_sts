"""``ActionFlowGovernor`` — runtime realization of the Action Flow Governor (AFG)
decision composition + single-use permit issuance (design #40 §5 order 5 item 2;
slice plan §2 item 2).

**This governor does not judge.** :meth:`ActionFlowGovernor.decide` prepares
:func:`tos.afg.action_flow_decision`'s witnesses by calling the *other*
``tos.afg`` §5 predicates (:func:`tos.afg.scope_graph_complete` /
:func:`tos.afg.cause_lineage_complete` / :func:`tos.afg.amplification_bounded`
/ :func:`tos.afg.envelope_not_enlarged` / :func:`tos.afg.atomic_economic_flow_coverage`)
— never computing a boolean itself — then calls
:func:`tos.afg.action_flow_decision` exactly once (the
``tos_runtime.risk.aggregate.AggregateRiskService.decide`` precedent).

**Permit issuance = one RCL log entry (§5.5/§13).** :meth:`ActionFlowGovernor.issue_permit`
commits an :class:`~tos.afg.ActionFlowPermit` via a single ``append_cas`` whose
``command_id`` is the permit's own ``claim_nonce`` — the log's
``entries.command_id`` ``UNIQUE`` constraint is what enforces single use, never
an in-memory flag (the ``tos_runtime.authority.iap.IntentRegistry`` "single-use
consumption is log-enforced, not memory-enforced" precedent, reused verbatim
here for permit claiming): a freshly re-created governor over the SAME log (a
simulated restart) refuses a second claim of the same nonce identically to the
still-running first instance.

**Single-transaction (reservation + permit) atomicity — reported design,
achieved by construction, not by splitting transactions
(AFG-INV-005/§13 line 330).** :meth:`ActionFlowGovernor.issue_permit` is the
STANDALONE building block this module owns; it is **not** what
``tos_runtime.risk.ledger_stages.AtomicCommitStage`` (step 9) uses for the
actual commit flow. ``SqliteCommitLog.apply_reservation_transition``
(``tos_runtime/rcl/log.py``, lane M, already landed — out of this lane's write
surface) builds its own fixed ``payload_json`` shape
(``reservation_id``/``from_state``/``to_state``/``cause``/``finality_witness``/
``scope``) and has no parameter for embedding an additional permit payload; a
literal "one entry carries both artifacts' full content" therefore cannot be
achieved without editing that module. :func:`permit_reservation_binding`
below is the alternative this lane commits to instead, and it genuinely
achieves single-transaction atomicity for the *commitment coordinate* (not the
full byte content) of both artifacts: ``AtomicCommitStage`` calls
``apply_reservation_transition`` with ``command_id=permit.claim_nonce`` and
``command_digest=permit.canonical_digest`` — the SAME entry that commits the
reservation transition ALSO durably fixes the permit's single-use nonce (via
the log's own ``command_id`` ``UNIQUE`` constraint) and its exact digest, in
ONE ``BEGIN IMMEDIATE`` ... ``COMMIT`` transaction. ``rcl_commitment_ref`` is
that entry's ``seq``. The permit's full field content is separately durably
recorded to the evidence store (a different failure domain, D3.1) for
completeness; what MUST be atomic with the reservation — the exclusive claim
of the nonce, and the binding digest — genuinely is, in the one entry. This is
reported here precisely rather than silently claimed as "the permit record
itself lives in the entry": it does not; its *commitment coordinate* does.

Single-node "quorum" = self + writer epoch only (``RESIDUAL-RISK-REGISTER-002``
R-RCL-F0) — no quorum certificate is claimed anywhere in this module.

**Reported ``CommandType`` gap — resolved by kernel round #1 (plan §1.1).**
No member of the ADR-002-012 §10 / ADR-002-002 §27 closed
``tos.rcl.vocabulary.CommandType`` vocabulary named "issue a single-use Action
Flow Permit" as a standalone act (distinct from a reservation commit) — this
module's STANDALONE :meth:`issue_permit` path previously reused the
structurally closest analog, :data:`~tos.rcl.CommandType.AUTHORIZE_TRANSMISSION_CAPABILITY`
(a DIFFERENT governed artifact, the RCL Transmission Capability, ADR-002-002
§12 — afg §5.5 line 129: a permit is explicitly "not a Transmission
Capability"). Kernel round #1 §1.1 (`docs/plans/2026-09-08-tos-phase2-kernel-
round-1-commandtype-expiry-obligation-plan.md`) ratified a dedicated member,
:data:`~tos.rcl.CommandType.ISSUE_ACTION_FLOW_PERMIT`, under the new
"Runtime-realized authority/currentness commands" vocabulary block — this
module's STANDALONE path now commits exclusively under that member; the
``AUTHORIZE_TRANSMISSION_CAPABILITY`` reuse is retired here (kernel round #1
§2.1). This module has no reader that filters log entries by ``kind`` (the
STANDALONE path only ever writes), so there is no legacy-kind reader gate to
add here. ``ledger_stages.AtomicCommitStage``'s combined commit uses
:data:`~tos.rcl.CommandType.COMMIT_RESERVATION` instead (an exact match — see
that module's own docstring).

Firewall: stdlib + ``pydantic`` (transitively) + ``tos.afg`` / ``tos.canonical``
/ ``tos.rcl`` + ``tos_runtime.evidence`` (``EvidenceAppendPort`` seam) +
``tos_runtime.rcl.log`` (``SqliteCommitLog`` — the STANDALONE
:meth:`issue_permit` path only) only (R1 allowlist). No
``tos_runtime.authority`` / ``tos_runtime.currentness`` / ``tos_runtime.release``
import (slice plan §5 cross-lane isolation).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
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

#: The dedicated ``CommandType`` member for a standalone Action Flow Permit
#: issuance (kernel round #1 §1.1/§2.1 — module docstring) — the STANDALONE
#: :meth:`ActionFlowGovernor.issue_permit` path only.
_STANDALONE_PERMIT_KIND = CommandType.ISSUE_ACTION_FLOW_PERMIT

_EVIDENCE_KIND_DECISION = "AFG_DECISION"
_EVIDENCE_KIND_PERMIT = "AFG_PERMIT"


class ActionFlowConfigError(Exception):
    """Raised when the injected :class:`~tos.afg.ActionAmplificationEnvelope`
    leaves an amplification axis undeclared, or a permit lacks the fields an
    RCL commitment requires — fail-closed at construction/commit time."""


@dataclass(frozen=True)
class ActionFlowDecisionInputs:
    """Every injected witness :func:`tos.afg.action_flow_decision` needs.

    None of these are computable by this governor — they are Phase-0 /
    broker-capability-profile / orthostate concerns afg itself does not own
    either (module docstring; ``tos.afg.__init__``'s own "afg consumes every
    one of those as an injected produced scalar/bool/token" discipline). A
    caller (the ``tos_runtime.risk.ledger_stages.ActionFlowDecisionStage``
    inputs provider) supplies them; their absence is ``None`` — UNKNOWN, never
    assumed positive.
    """

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
    #: The entry's ``seq`` — only on a successful, durable commit.
    rcl_commitment_ref: int | None


def permit_reservation_binding(permit: ActionFlowPermit) -> tuple[str, str] | None:
    """The ``(claim_nonce, canonical_digest)`` pair a combined reservation+permit
    commit (``ledger_stages.AtomicCommitStage``) folds into ITS OWN entry's
    ``command_id``/``command_digest`` fields (module docstring's atomicity
    note).

    Returns:
        ``None`` (fail-closed) if either field is absent — an unbound permit
        cannot be committed at all.
    """
    if permit.claim_nonce is None or permit.canonical_digest is None:
        return None
    return (permit.claim_nonce, permit.canonical_digest)


class ActionFlowGovernor:
    """Runtime realization of AFG decision composition + permit issuance
    (module docstring)."""

    def __init__(
        self,
        log: SqliteCommitLog,
        evidence: EvidenceAppendPort,
        envelope: ActionAmplificationEnvelope,
        *,
        writer_epoch: int,
        canonicalization_version: str = EV_L1_PROVISIONAL_VERSION,
    ) -> None:
        """Compose the governor over its injected ports.

        Args:
            log: The Safety Commit Log the STANDALONE :meth:`issue_permit`
                path commits through (``append_cas`` only — the combined
                reservation+permit commit lives in
                ``ledger_stages.AtomicCommitStage`` instead, over the SAME
                log instance the composition root shares).
            evidence: The durable append port every decision/permit is
                evidenced through.
            envelope: The injected :class:`~tos.afg.ActionAmplificationEnvelope`
                (see ``tos/runtime/config/risk.example.yaml`` — a value left
                ``null`` there means an undeclared axis, which
                :func:`tos.afg.ActionAmplificationEnvelope.declares_every_bound`
                would report as unbounded; this constructor refuses to start
                on that (§5.8 line 141 "unknown or unbounded amplification is
                denial")).
            writer_epoch: The RCL Writer Epoch this instance's ``append_cas``
                calls are fenced under.
            canonicalization_version: The registered ``tos.canonical`` scheme
                version used to digest every issued decision/permit.

        Raises:
            ActionFlowConfigError: ``envelope`` leaves any amplification axis
                undeclared (``None``).
        """
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

    @property
    def envelope(self) -> ActionAmplificationEnvelope:
        return self._envelope

    def decide(self, inputs: ActionFlowDecisionInputs) -> ActionFlowDecision:
        """Prepare :func:`tos.afg.action_flow_decision`'s witnesses via the
        other ``tos.afg`` §5 predicates, then call it exactly once (module
        docstring)."""
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
            protective_classification_digest=inputs.protective_classification_digest,
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
        """Issue (digest-bind) the :class:`~tos.afg.ActionFlowPermit` schema
        afg owns (§0.4d) — no RCL commit here; see :meth:`issue_permit` /
        ``ledger_stages.AtomicCommitStage`` for the durable commit.

        ``claim_nonce`` is content-addressed from (decision digest, command
        identity, permit generation) — never a uuid4/timestamp (the engine
        ``build_attempt_request`` precedent) — so the same three bindings
        always reproduce the same nonce and a replayed construction cannot
        silently mint a fresh single-use token for an already-decided permit.
        """
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
        """STANDALONE permit commitment via a plain ``append_cas`` (module
        docstring's item-2 contract) — NOT used by the combined step-9
        atomic commit (``ledger_stages.AtomicCommitStage``, which folds the
        SAME ``(claim_nonce, canonical_digest)`` pair into the
        reservation-transition entry instead of a second, separate entry —
        see this module's docstring for why single-transaction atomicity
        requires that fold).

        Args:
            permit: The issued permit (:meth:`build_permit`).
            expected_seq: The log's current tip, as the caller last observed
                it (the CAS fence).

        Returns:
            The :class:`PermitIssueResult`.

        Raises:
            ActionFlowConfigError: ``permit.claim_nonce`` or
                ``.canonical_digest`` is absent (an unbound permit cannot be
                committed).
        """
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
