"""``tos_runtime.safety.rearm`` — the HAG two-person new-risk-halt re-arm workflow
(Phase 5 W3 plan ``docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md`` §2
decision 7; ADR-002-015 §17 "re-arm dual control").

**What this replaces.** :meth:`~tos_runtime.compose._types.ComposedRuntime
.clear_new_risk_halt` used to accept one operator's free-text
``operator_attestation`` string (only its sha256 was ever recorded — a single
person, unauthenticated, unverified against any roster). :class:`ReArmWorkflow`
replaces that with an operator-authored, on-disk, TWO-PERSON decision file
(``approvals/rearm/<latched_evidence_seq>.yaml`` — the same
``approvals/<key>.yaml`` custody convention
:mod:`tos_runtime.authority.iap` already uses for Independent Approval decisions)
evaluated against FIVE kernel ``tos.hag`` predicates:

* :func:`~tos.hag.dual_control_effective_distinct` — >= 2 distinct effective
  natural persons (collapse-before-count; §17 line 444).
* :func:`~tos.hag.quorum_independence_satisfied` — the full independent-quorum
  gate (both ``APPROVE``, no duplicate principal, every attesting principal
  resolved in the graph, ``quorum_n=2`` with the ``REARM_APPROVER`` role
  required of every attestation).
* :func:`~tos.hag.approval_binding_exact` — each attestation binds the EXACT
  request digest (never a different request's approval reused).
* :func:`~tos.hag.approval_set_single_use` — the approval set this file
  produces has never been consumed before (checked against this runtime's own
  ``REARM_APPROVED`` evidence history — module's own durable record of every
  prior successful re-arm).
* :func:`~tos.hag.no_automatic_rearm` — accepted for completeness (it is
  unconditionally ``True`` by kernel construction, §18/§20 HAG-INV-014); the
  REAL "never automatic" guarantee here is structural: with no approval file
  present, :meth:`ReArmWorkflow.approve_and_clear` refuses before it ever
  reaches a kernel predicate — there is no code path that synthesises an
  approval.

**Evidence discipline (design #40 D3.1's own "evidence before state change").**
A successful evaluation appends ONE ``REARM_APPROVED`` entry (principal ids
hashed — never plaintext — plus the request/approval-set digests) BEFORE
:meth:`~tos_runtime.compose._types.ComposedRuntime.clear_new_risk_halt` performs
the actual storage-layer clear; ANY refusal — a missing/malformed file, a failed
custody check, or any of the five predicates not positively satisfied — appends
a ``REARM_REFUSED`` entry (the failed check names, never a partial approval) and
clears nothing.

Firewall: stdlib + ``pyyaml`` + ``tos.hag`` + ``tos.canonical`` (``get_scheme``)
+ ``tos_runtime.custody`` + ``tos_runtime.engine.inbox`` (read-only —
``new_risk_halt()``, never ``clear_new_risk_halt(`` — the machine pin
``tests/engine/test_no_direct_latch_clear.py`` allows only
``compose/_types.py`` to call that) + ``tos_runtime.evidence.store`` +
``tos_runtime.time.service`` only.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, ArtifactIntegrityError, get_scheme
from tos.hag import (
    ApprovalSetConsumptionRecord,
    AttestationDecision,
    AuthorityClass,
    ConflictRole,
    EffectivePrincipalGraph,
    EffectivePrincipalNode,
    HumanApprovalAttestation,
    HumanApprovalRequest,
    HumanApprovalSet,
    approval_binding_exact,
    approval_set_single_use,
    dual_control_effective_distinct,
    no_automatic_rearm,
    quorum_independence_satisfied,
)

from tos_runtime.custody.file_custody import verify_file_mode_and_owner
from tos_runtime.custody.ports import CustodyLoadRefused
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.time.service import TrustworthyTimeService

__all__ = [
    "ReArmApprovalFileError",
    "ReArmOutcome",
    "ReArmStatus",
    "ReArmWorkflow",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Evidence kind for a satisfied two-person re-arm quorum, recorded BEFORE the
#: caller (``ComposedRuntime.clear_new_risk_halt``) performs the storage clear.
_REARM_APPROVED_KIND = "REARM_APPROVED"
#: Evidence kind for EVERY refusal — a missing file, a custody failure, or any
#: kernel predicate not positively satisfied.
_REARM_REFUSED_KIND = "REARM_REFUSED"

#: The one required role every attestation in a re-arm quorum must carry.
_REARM_ROLE = ConflictRole.REARM_APPROVER
#: The re-arm quorum size (ADR-002-015 §17 line 444 "two distinct effective
#: natural persons").
_REARM_QUORUM_N = 2


class ReArmApprovalFileError(Exception):
    """Raised internally for any refusal reading/validating the on-disk approval
    file — always caught by :meth:`ReArmWorkflow.approve_and_clear` and turned
    into a ``REFUSED`` :class:`ReArmOutcome`, never propagated to the caller."""


class ReArmStatus(StrEnum):
    """The two-outcome result of one re-arm attempt (module docstring)."""

    APPROVED = "APPROVED"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class ReArmOutcome:
    """One :meth:`ReArmWorkflow.approve_and_clear` result.

    Attributes:
        status: :attr:`ReArmStatus.APPROVED` iff every kernel predicate was
            positively satisfied.
        reasons: The failed check names (empty exactly when ``status is
            ReArmStatus.APPROVED``) — never a secret, never file content.
        attestation_text: A non-secret marker string
            (``"hag-rearm-quorum-satisfied:<consumption_id>"``) the caller may
            pass on as the storage layer's own (non-empty, free-text)
            ``operator_attestation`` argument — ``None`` on refusal.
    """

    status: ReArmStatus
    reasons: tuple[str, ...]
    attestation_text: str | None


def _load_raw_rearm_file(
    path: Path, *, expected_owner_uid: int, getuid: Callable[[], int]
) -> dict[str, Any]:
    """Custody-gated read + parse of the on-disk approval file (the
    ``tos_runtime.authority.iap.load_operator_approval_file`` convention, reused
    here rather than re-authored: same 0600-mode + owner-uid custody rule via
    :func:`~tos_runtime.custody.file_custody.verify_file_mode_and_owner`)."""
    if not path.is_file():
        raise ReArmApprovalFileError(f"rearm approval file not found: {path}")
    try:
        verify_file_mode_and_owner(
            path, expected_owner_uid=expected_owner_uid, getuid=getuid
        )
    except CustodyLoadRefused as exc:
        raise ReArmApprovalFileError(
            f"{path} failed the custody mode/owner gate: {exc}"
        ) from exc
    try:
        raw_text = path.read_text()
    except OSError as exc:
        raise ReArmApprovalFileError(f"cannot read {path}: {exc}") from exc
    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ReArmApprovalFileError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ReArmApprovalFileError(
            f"{path} must parse to a mapping (got {type(raw).__name__})"
        )
    return raw


def _verify_environment_label(
    raw: Mapping[str, Any], path: Path, environment_label: str
) -> None:
    file_label = raw.get("environment_label")
    if file_label != environment_label or not file_label:
        raise ReArmApprovalFileError(
            f"{path} environment_label={file_label!r} does not match runtime "
            f"environment_label={environment_label!r} — refuse (cross-environment "
            "isolation)"
        )


def _verify_entries(
    raw: Mapping[str, Any], path: Path, latched_evidence_seq: int
) -> tuple[dict[str, Any], ...]:
    """Structural validation of the ``latched_evidence_seq``/``approvals`` fields —
    the file-level half of "binds the exact request" (the kernel-level half is
    :func:`~tos.hag.approval_binding_exact` over the constructed digests)."""
    file_seq = raw.get("latched_evidence_seq")
    if file_seq != latched_evidence_seq:
        raise ReArmApprovalFileError(
            f"{path} latched_evidence_seq={file_seq!r} does not match the "
            f"requested {latched_evidence_seq!r} — refuse (stale/wrong approval file)"
        )
    approvals = raw.get("approvals")
    if not isinstance(approvals, list) or not approvals:
        raise ReArmApprovalFileError(
            f"{path} 'approvals' must be a non-empty list of "
            "{{principal_id, decision}} entries"
        )
    entries: list[dict[str, Any]] = []
    for entry in approvals:
        if not isinstance(entry, dict):
            raise ReArmApprovalFileError(
                f"{path} every 'approvals' entry must be a mapping"
            )
        principal_id = entry.get("principal_id")
        decision = entry.get("decision")
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ReArmApprovalFileError(
                f"{path} an 'approvals' entry has a missing/blank principal_id"
            )
        if decision not in {"APPROVE", "DENY", "ABSTAIN"}:
            raise ReArmApprovalFileError(
                f"{path} an 'approvals' entry has an invalid decision {decision!r}"
            )
        entries.append({"principal_id": principal_id, "decision": decision})
    return tuple(entries)


def _build_hag_artifacts(
    entries: Sequence[Mapping[str, Any]], latched_evidence_seq: int
) -> tuple[
    HumanApprovalRequest,
    tuple[HumanApprovalAttestation, ...],
    EffectivePrincipalGraph,
    HumanApprovalSet,
    ApprovalSetConsumptionRecord,
]:
    """Issue the digest-bound ``tos.hag`` artifacts the five kernel predicates
    consume — deterministic in every field the seq/file content fix, never a
    fabricated or free literal (module docstring)."""
    # Note: DigestBoundArtifact.issue() is annotated to return the BASE class (no
    # Self/TypeVar -- tos/src/tos/canonical/_base.py), even though at runtime a
    # classmethod call always binds `cls` to the class it was called on. Each
    # `assert isinstance(...)` below narrows the static type to match that real
    # runtime behavior (the same idiom tos_runtime.time.service.TrustworthyTimeService
    # ._issue_snapshot uses) -- never a suppression; it will always hold.
    request = HumanApprovalRequest.issue(
        scheme=_SCHEME,
        request_id=f"rearm-request-{latched_evidence_seq}",
        request_type=AuthorityClass.APPROVE_REARM,
        maximum_authority=AuthorityClass.APPROVE_REARM,
        creation_generation=latched_evidence_seq,
        requested_action="clear_new_risk_halt",
        graph_generation=latched_evidence_seq,
    )
    assert isinstance(request, HumanApprovalRequest)
    attestation_list: list[HumanApprovalAttestation] = []
    for index, entry in enumerate(entries):
        attestation = HumanApprovalAttestation.issue(
            scheme=_SCHEME,
            attestation_id=f"rearm-attn-{latched_evidence_seq}-{index}",
            request_digest=request.canonical_digest,
            principal_id=entry["principal_id"],
            role=_REARM_ROLE,
            decision=AttestationDecision(entry["decision"]),
            effective_principal_graph_generation=latched_evidence_seq,
            issue_generation=latched_evidence_seq,
        )
        assert isinstance(attestation, HumanApprovalAttestation)
        attestation_list.append(attestation)
    attestations = tuple(attestation_list)
    node_ids = sorted({entry["principal_id"] for entry in entries})
    graph = EffectivePrincipalGraph.issue(
        scheme=_SCHEME,
        graph_id=f"rearm-graph-{latched_evidence_seq}",
        graph_generation=latched_evidence_seq,
        nodes=tuple(EffectivePrincipalNode(principal_id=p) for p in node_ids),
        edges=(),
        unresolved_control=False,
    )
    assert isinstance(graph, EffectivePrincipalGraph)
    approval_set = HumanApprovalSet.issue(
        scheme=_SCHEME,
        set_id=f"rearm-set-{latched_evidence_seq}",
        attestations=attestations,
        bound_request_digest=request.canonical_digest,
        policy_generation=latched_evidence_seq,
        graph_generation=latched_evidence_seq,
    )
    assert isinstance(approval_set, HumanApprovalSet)
    consumption = ApprovalSetConsumptionRecord.issue(
        scheme=_SCHEME,
        consumption_id=f"rearm-consumption-{latched_evidence_seq}",
        approval_set_digest=approval_set.canonical_digest,
        downstream_decision_ref=f"new_risk_halt:{latched_evidence_seq}",
        single_use=True,
        consumed_generation=latched_evidence_seq,
    )
    assert isinstance(consumption, ApprovalSetConsumptionRecord)
    return request, attestations, graph, approval_set, consumption


class ReArmWorkflow:
    """The HAG two-person new-risk-halt re-arm workflow (module docstring).

    Constructed fresh per :meth:`~tos_runtime.compose._types.ComposedRuntime
    .clear_new_risk_halt` call (cheap — no I/O happens until
    :meth:`approve_and_clear` runs); never caches a quorum decision across calls
    (single-use is re-checked, against durable evidence, every time).
    """

    def __init__(
        self,
        approvals_dir: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        time_service: TrustworthyTimeService,
        *,
        environment_label: str,
        expected_owner_uid: int,
        getuid: Callable[[], int] = os.getuid,
    ) -> None:
        """Args:
        approvals_dir: The directory ``rearm/<latched_evidence_seq>.yaml`` is
            resolved under (the same root :mod:`tos_runtime.authority.iap` uses
            for ``approvals/<proposal_digest>.yaml``).
        evidence_store: Where ``REARM_APPROVED``/``REARM_REFUSED`` are recorded,
            and where prior approval-set consumptions are read back from (single-
            use check).
        inbox: Read-only — only :meth:`~tos_runtime.engine.inbox.SqliteEventInbox
            .new_risk_halt` is ever called; this workflow never calls
            ``clear_new_risk_halt`` itself (the machine-pinned caller is
            ``compose/_types.py`` alone).
        time_service: The runtime's trustworthy-time service — carried for
            interface symmetry with the runtime's other operator-door workflows;
            hag itself reads no clock (module docstring), so this is not
            consulted by any of the five predicates.
        environment_label: This runtime's own boot-argument environment label;
            the file's own ``environment_label`` must match byte-exact (never an
            ambient env read — the same IAP convention).
        expected_owner_uid: The uid both the file's owner and this process are
            expected to be (custody's 0600 rule).
        getuid: An ``os.getuid``-shaped callable, injectable for tests.
        """
        self._approvals_dir = approvals_dir
        self._evidence = evidence_store
        self._inbox = inbox
        self._time_service = time_service
        self._environment_label = environment_label
        self._expected_owner_uid = expected_owner_uid
        self._getuid = getuid

    def approve_and_clear(self, latched_evidence_seq: int) -> ReArmOutcome:
        """Evaluate the two-person re-arm quorum for ``latched_evidence_seq``.

        Never calls the storage-layer clear itself (module docstring) — the
        caller (:meth:`~tos_runtime.compose._types.ComposedRuntime
        .clear_new_risk_halt`) does that only when this returns
        :attr:`ReArmStatus.APPROVED`.

        Args:
            latched_evidence_seq: The ``evidence_seq`` of the currently-latched
                new-risk halt the operator reviewed.

        Returns:
            The :class:`ReArmOutcome`.
        """
        path = self._approvals_dir / "rearm" / f"{latched_evidence_seq}.yaml"
        try:
            raw = _load_raw_rearm_file(
                path,
                expected_owner_uid=self._expected_owner_uid,
                getuid=self._getuid,
            )
            _verify_environment_label(raw, path, self._environment_label)
            entries = _verify_entries(raw, path, latched_evidence_seq)
        except ReArmApprovalFileError as exc:
            return self._refuse(latched_evidence_seq, (f"approval_file: {exc}",))

        current = self._inbox.new_risk_halt()
        if current is None or current.get("evidence_seq") != latched_evidence_seq:
            return self._refuse(latched_evidence_seq, ("no_matching_latch",))

        try:
            request, attestations, graph, approval_set, consumption = (
                _build_hag_artifacts(entries, latched_evidence_seq)
            )
        except (ValueError, ArtifactIntegrityError) as exc:
            return self._refuse(
                latched_evidence_seq, (f"hag_artifact_construction: {exc}",)
            )

        prior_consumptions = self._prior_consumptions()
        checks: dict[str, bool] = {
            "dual_control_effective_distinct": (
                dual_control_effective_distinct(attestations, graph) is True
            ),
            "quorum_independence_satisfied": (
                quorum_independence_satisfied(
                    attestations,
                    graph,
                    quorum_n=_REARM_QUORUM_N,
                    required_roles=frozenset({_REARM_ROLE}),
                )
                is True
            ),
            "approval_binding_exact": bool(attestations)
            and all(
                approval_binding_exact(request, attestation) is True
                for attestation in attestations
            ),
            "approval_set_single_use": (
                approval_set_single_use(consumption, prior_consumptions) is True
            ),
            "no_automatic_rearm": no_automatic_rearm() is True,
        }
        failed = tuple(name for name, satisfied in checks.items() if not satisfied)
        if failed:
            return self._refuse(latched_evidence_seq, failed)

        principal_sha256 = sorted(
            hashlib.sha256(attestation.principal_id.encode("utf-8")).hexdigest()
            for attestation in attestations
            if attestation.principal_id is not None
        )
        self._evidence.append(
            {
                "latched_evidence_seq": latched_evidence_seq,
                "latched_reason": current.get("reason"),
                "principal_sha256": principal_sha256,
                "request_digest": request.canonical_digest,
                "approval_set_digest": approval_set.canonical_digest,
                "consumption_id": consumption.consumption_id,
                "consumed_generation": consumption.consumed_generation,
            },
            kind=_REARM_APPROVED_KIND,
            record_class=_REARM_APPROVED_KIND,
        )
        return ReArmOutcome(
            status=ReArmStatus.APPROVED,
            reasons=(),
            attestation_text=f"hag-rearm-quorum-satisfied:{consumption.consumption_id}",
        )

    def _refuse(
        self, latched_evidence_seq: int, reasons: tuple[str, ...]
    ) -> ReArmOutcome:
        self._evidence.append(
            {
                "latched_evidence_seq": latched_evidence_seq,
                "reasons": list(reasons),
            },
            kind=_REARM_REFUSED_KIND,
            record_class=_REARM_REFUSED_KIND,
        )
        return ReArmOutcome(
            status=ReArmStatus.REFUSED, reasons=reasons, attestation_text=None
        )

    def _prior_consumptions(self) -> tuple[ApprovalSetConsumptionRecord, ...]:
        """Reconstruct every past successful re-arm's consumption record from this
        runtime's own durable ``REARM_APPROVED`` evidence history — the single-use
        check's own memory (never an in-process cache; a fresh
        :class:`ReArmWorkflow` over the SAME evidence store sees the identical
        history, exactly like ``tos_runtime.authority.iap.IntentRegistry``'s own
        log-enforced, not memory-enforced, single-use consumption)."""
        rows = self._evidence.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?", (_REARM_APPROVED_KIND,)
        ).fetchall()
        records: list[ApprovalSetConsumptionRecord] = []
        for (payload_json,) in rows:
            payload = json.loads(payload_json)["payload"]
            record = ApprovalSetConsumptionRecord.issue(
                scheme=_SCHEME,
                consumption_id=payload["consumption_id"],
                approval_set_digest=payload["approval_set_digest"],
                downstream_decision_ref=(
                    f"new_risk_halt:{payload['latched_evidence_seq']}"
                ),
                single_use=True,
                consumed_generation=payload["consumed_generation"],
            )
            assert isinstance(record, ApprovalSetConsumptionRecord)
            records.append(record)
        return tuple(records)
