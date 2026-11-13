"""The new-risk-halt clear door: one operator confirmation, custody-gated.

**What plan S2-a changed.** This used to drive the kernel ``tos.hag`` two-person
dual-control quorum: an effective-principal roster, delegation/conflict edges, a
quorum-independence predicate and a single-use approval set. In the real evidence that
machinery recorded **zero** re-arms and zero halt clears — it was never exercised — and
``tos.hag`` is gone. What stays is the simplest honest gate, and every property that
actually fenced the latch:

1. **The latch's own identity is checked first.** A clear names an exact
   ``latched_evidence_seq``; an absent latch (``NO_LATCH``) or a different currently-
   latched seq (``SEQ_MISMATCH``) is refused before the approval file is even read, so a
   stale approval can never clear a newer halt.
2. **One approval, one use.** An approval for a seq that ALREADY has a
   ``REARM_APPROVED`` row is refused. The ``tos.hag`` ``approval_set_single_use``
   predicate that used to enforce this is gone, so the check is made here against the
   store's own durable history (never an in-process cache — a freshly re-opened process
   over the same store refuses identically, the same log-enforced discipline
   :func:`tos_runtime.safety.ack._already_acknowledged` applies to alerts). Without it
   one approval file could clear the SAME ``evidence_seq`` twice: nothing stops a
   violation from re-latching at a seq a leftover file still names.
3. **The approval file is custody-gated.** 0600 mode and owner uid
   (:func:`~tos_runtime.custody.file_custody.verify_file_mode_and_owner`), the same rule
   every other operator file in this runtime obeys.
4. **Cross-environment isolation.** The file's own ``environment_label`` must equal this
   runtime's byte-exact.
5. **One named principal, positively APPROVE.** Exactly one approval entry, a non-blank
   ``principal_id`` that is not still the ``TBD`` template placeholder, and a
   ``decision`` of exactly ``APPROVE``. ``DENY``/``ABSTAIN``/anything else refuses.
6. **Every outcome is durably evidenced** — ``REARM_APPROVED`` before the caller's own
   storage clear, ``REARM_REFUSED`` on every refusal including an unreadable file. That
   ``REARM_APPROVED`` row is what item 2 reads back.

**What plan S2-a removed and did NOT replace** (grade-A review disclosure): the
two-person quorum itself, roster membership and its effective-principal/conflict graph
(``quorum_independence_satisfied`` / ``dual_control_effective_distinct``), and the
request-digest binding (``approval_binding_exact``) that tied an approval to one exact
constructed request record. Item 2 above restores single use; the other three are
deliberately gone, having recorded zero re-arms in the live evidence.

**Machine pin.** ``tests/engine/test_no_direct_latch_clear.py`` allows exactly two files
to call :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.clear_new_risk_halt` directly:
``compose/_types.py`` (the live-runtime door) and ``compose/_cli_ops.py`` (the CLI-only
door). Both stop here first; neither bypasses this gate. This module itself never clears
the latch — it hands back :class:`NewRiskHaltDoorDecision`.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``pyyaml`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from tos_runtime._named_tbd import is_named_tbd_placeholder
from tos_runtime.custody.file_custody import verify_file_mode_and_owner
from tos_runtime.custody.ports import CustodyLoadRefused
from tos_runtime.engine.inbox import NewRiskHaltClearOutcome
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.safety.latch import NewRiskHaltReader

__all__ = [
    "NewRiskHaltDoorDecision",
    "ReArmApprovalFileError",
    "ReArmOutcome",
    "ReArmStatus",
    "ReArmWorkflow",
    "prepare_new_risk_halt_clear",
]

#: Evidence kind for an approved clear, recorded BEFORE the caller's storage clear.
_REARM_APPROVED_KIND = "REARM_APPROVED"
#: Evidence kind for EVERY refusal — a missing file, a custody failure, or a
#: non-``APPROVE`` decision.
_REARM_REFUSED_KIND = "REARM_REFUSED"

#: The decision tokens an approval entry may carry. Only the first one clears.
_APPROVE = "APPROVE"
_DECISIONS = frozenset({_APPROVE, "DENY", "ABSTAIN"})


class ReArmApprovalFileError(Exception):
    """Raised internally for any refusal reading/validating the on-disk approval file,
    or for a seq whose approval was already used — always caught by
    :meth:`ReArmWorkflow.approve_and_clear` and turned into a ``REFUSED``
    :class:`ReArmOutcome`, never propagated to the caller."""


class ReArmStatus(StrEnum):
    """The two-outcome result of one re-arm attempt (module docstring)."""

    APPROVED = "APPROVED"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class ReArmOutcome:
    """One :meth:`ReArmWorkflow.approve_and_clear` result.

    Attributes:
        status: :attr:`ReArmStatus.APPROVED` iff every check in the module docstring
            positively held.
        reasons: The failed check names (empty exactly when ``status is
            ReArmStatus.APPROVED``) — never a secret, never file content.
        attestation_text: A non-secret marker string
            (``"operator-rearm-approved:<principal_id>"``) the caller passes on as the
            storage layer's own (non-empty, free-text) ``operator_attestation``
            argument — ``None`` on refusal.
    """

    status: ReArmStatus
    reasons: tuple[str, ...]
    attestation_text: str | None


def _load_raw_rearm_file(
    path: Path, *, expected_owner_uid: int, getuid: Callable[[], int]
) -> dict[str, Any]:
    """Custody-gated read + parse of the on-disk approval file (module docstring item 2 —
    the same 0600-mode + owner-uid rule ``tos_runtime.authority.iap`` applies)."""
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


def _already_approved(evidence_store: SqliteEvidenceStore, seq: int) -> bool:
    """Whether a prior ``REARM_APPROVED`` row already names ``seq`` (module docstring
    item 2).

    Read from the store's own durable history, never an in-process cache, so a freshly
    re-opened process over the same store refuses a second use identically.
    """
    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ?",
        (_REARM_APPROVED_KIND,),
    ).fetchall()
    for (payload_json,) in rows:
        payload = json.loads(payload_json)["payload"]
        if payload.get("latched_evidence_seq") == seq:
            return True
    return False


def _verify_environment_label(
    raw: Mapping[str, Any], path: Path, environment_label: str
) -> None:
    """Module docstring item 3 — cross-environment isolation."""
    file_label = raw.get("environment_label")
    if file_label != environment_label or not file_label:
        raise ReArmApprovalFileError(
            f"{path} environment_label={file_label!r} does not match runtime "
            f"environment_label={environment_label!r} — refuse (cross-environment "
            "isolation)"
        )


def _verify_approval(
    raw: Mapping[str, Any], path: Path, latched_evidence_seq: int
) -> str:
    """Module docstring items 1 (file half) and 4 — return the approving principal id.

    The file must name the exact ``latched_evidence_seq`` the caller is clearing, and
    carry EXACTLY ONE approval entry whose ``decision`` is ``APPROVE``. Two entries are
    refused rather than quietly reduced to one: an approval file is a record of who
    decided, and an ambiguous one is not a decision.
    """
    file_seq = raw.get("latched_evidence_seq")
    if file_seq != latched_evidence_seq:
        raise ReArmApprovalFileError(
            f"{path} latched_evidence_seq={file_seq!r} does not match the "
            f"requested {latched_evidence_seq!r} — refuse (stale/wrong approval file)"
        )
    approvals = raw.get("approvals")
    if not isinstance(approvals, list) or len(approvals) != 1:
        raise ReArmApprovalFileError(
            f"{path} 'approvals' must be a list of exactly one "
            "{principal_id, decision} entry"
        )
    entry = approvals[0]
    if not isinstance(entry, dict):
        raise ReArmApprovalFileError(f"{path} the 'approvals' entry must be a mapping")
    principal_id = entry.get("principal_id")
    decision = entry.get("decision")
    if not isinstance(principal_id, str) or not principal_id.strip():
        raise ReArmApprovalFileError(
            f"{path} the 'approvals' entry has a missing/blank principal_id"
        )
    if is_named_tbd_placeholder(principal_id):
        raise ReArmApprovalFileError(
            f"{path} the 'approvals' entry's principal_id is still the template "
            "placeholder 'TBD' — operator-fill before use"
        )
    if decision not in _DECISIONS:
        raise ReArmApprovalFileError(
            f"{path} the 'approvals' entry has an invalid decision {decision!r}"
        )
    if decision != _APPROVE:
        raise ReArmApprovalFileError(
            f"{path} the 'approvals' entry decision is {decision!r}, not {_APPROVE!r}"
        )
    return principal_id


class ReArmWorkflow:
    """Evaluates one operator approval file for one latched evidence seq.

    This class never clears the latch (module docstring "Machine pin"); it reports an
    :class:`ReArmOutcome` and records the matching evidence row.
    """

    def __init__(
        self,
        approvals_dir: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: NewRiskHaltReader,
        *,
        environment_label: str,
        expected_owner_uid: int,
        getuid: Callable[[], int] = os.getuid,
    ) -> None:
        """Bind the approval directory, the evidence sink, and the custody expectations.

        Args:
            approvals_dir: The directory ``rearm/<latched_evidence_seq>.yaml`` resolves
                under.
            evidence_store: Where ``REARM_APPROVED``/``REARM_REFUSED`` rows land.
            inbox: The new-risk-halt latch reader
                (:class:`~tos_runtime.safety.latch.NewRiskHaltReader`, which
                ``SqliteEventInbox`` satisfies structurally). Held for interface
                symmetry with the caller's own resources; this class reads the latch
                through the ``current`` reading its caller passes to
                :func:`prepare_new_risk_halt_clear`, never independently — so the
                read-only port is the honest annotation, not the concrete store.
            environment_label: This runtime's own boot-argument environment label.
            expected_owner_uid: The uid both the approval file's owner and the calling
                process itself are expected to be (file custody's 0600 rule).
            getuid: Injected for tests; defaults to :func:`os.getuid`.
        """
        self._approvals_dir = approvals_dir
        self._evidence_store = evidence_store
        self._inbox = inbox
        self._environment_label = environment_label
        self._expected_owner_uid = expected_owner_uid
        self._getuid = getuid

    def approve_and_clear(self, latched_evidence_seq: int) -> ReArmOutcome:
        """Evaluate the approval file for ``latched_evidence_seq`` and record evidence.

        Returns:
            The :class:`ReArmOutcome`. ``APPROVED`` only when every module-docstring
            check positively held; every other path is ``REFUSED`` with a non-secret
            reason, and both paths leave a durable evidence row.
        """
        path = self._approvals_dir / "rearm" / f"{latched_evidence_seq}.yaml"
        try:
            if _already_approved(self._evidence_store, latched_evidence_seq):
                raise ReArmApprovalFileError(
                    f"evidence_seq {latched_evidence_seq} already has a "
                    f"{_REARM_APPROVED_KIND} row — one approval, one use "
                    "(module docstring item 2); a re-latched seq needs a new "
                    "approval, not the leftover file"
                )
            raw = _load_raw_rearm_file(
                path,
                expected_owner_uid=self._expected_owner_uid,
                getuid=self._getuid,
            )
            _verify_environment_label(raw, path, self._environment_label)
            principal_id = _verify_approval(raw, path, latched_evidence_seq)
        except ReArmApprovalFileError as exc:
            reason = str(exc)
            self._evidence_store.append(
                {
                    "latched_evidence_seq": latched_evidence_seq,
                    "status": ReArmStatus.REFUSED.value,
                    "reasons": [reason],
                },
                kind=_REARM_REFUSED_KIND,
                record_class=_REARM_REFUSED_KIND,
            )
            return ReArmOutcome(
                status=ReArmStatus.REFUSED, reasons=(reason,), attestation_text=None
            )

        attestation_text = f"operator-rearm-approved:{principal_id}"
        self._evidence_store.append(
            {
                "latched_evidence_seq": latched_evidence_seq,
                "status": ReArmStatus.APPROVED.value,
                "principal_id": principal_id,
            },
            kind=_REARM_APPROVED_KIND,
            record_class=_REARM_APPROVED_KIND,
        )
        return ReArmOutcome(
            status=ReArmStatus.APPROVED,
            reasons=(),
            attestation_text=attestation_text,
        )


@dataclass(frozen=True)
class NewRiskHaltDoorDecision:
    """The result of :func:`prepare_new_risk_halt_clear` — either a terminal,
    already-evidenced refusal, or the go-ahead for the caller's OWN storage-layer clear.

    Attributes:
        refusal: A terminal :class:`~tos_runtime.engine.inbox.NewRiskHaltClearOutcome`
            (``NO_LATCH`` / ``SEQ_MISMATCH`` / ``QUORUM_REFUSED``), already durably
            evidenced by this function — ``None`` means "proceed to the storage clear".
        attestation_text: Non-``None`` exactly when ``refusal is None`` — the approval's
            non-secret attestation marker text for the caller's own
            ``operator_attestation`` argument.
    """

    refusal: NewRiskHaltClearOutcome | None
    attestation_text: str | None


def prepare_new_risk_halt_clear(
    *,
    current: Mapping[str, object] | None,
    latched_evidence_seq: int,
    approvals_dir: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: NewRiskHaltReader,
    environment_label: str,
    expected_owner_uid: int,
    refused_kind: str,
) -> NewRiskHaltDoorDecision:
    """Every check a caller needs BEFORE its own storage-layer clear call — the seq
    pre-checks plus the operator approval (:class:`ReArmWorkflow`).

    Args:
        current: The caller's own ``inbox.new_risk_halt()`` reading (read once by the
            caller and passed in here, rather than re-read).
        latched_evidence_seq: The seq the operator is attempting to clear.
        approvals_dir: See :class:`ReArmWorkflow`.
        evidence_store: See :class:`ReArmWorkflow`; also where this function's own
            refusal rows are appended for the ``NO_LATCH``/``SEQ_MISMATCH`` paths.
        inbox: See :class:`ReArmWorkflow`.
        environment_label: See :class:`ReArmWorkflow`.
        expected_owner_uid: See :class:`ReArmWorkflow`.
        refused_kind: The evidence ``kind``/``record_class`` string for a refusal
            recorded here (the caller's own ``_NEW_RISK_HALT_CLEAR_REFUSED_KIND`` — a
            runtime-level record kind, passed in rather than duplicated here).

    Returns:
        The :class:`NewRiskHaltDoorDecision`.
    """

    def _refuse(outcome: NewRiskHaltClearOutcome) -> NewRiskHaltDoorDecision:
        evidence_store.append(
            {
                "outcome": outcome.value,
                "requested_evidence_seq": latched_evidence_seq,
                "current_latched_evidence_seq": (
                    current.get("evidence_seq") if current is not None else None
                ),
            },
            kind=refused_kind,
            record_class=refused_kind,
        )
        return NewRiskHaltDoorDecision(refusal=outcome, attestation_text=None)

    if current is None:
        return _refuse(NewRiskHaltClearOutcome.NO_LATCH)
    if current.get("evidence_seq") != latched_evidence_seq:
        return _refuse(NewRiskHaltClearOutcome.SEQ_MISMATCH)

    workflow = ReArmWorkflow(
        approvals_dir,
        evidence_store,
        inbox,
        environment_label=environment_label,
        expected_owner_uid=expected_owner_uid,
    )
    rearm_outcome = workflow.approve_and_clear(latched_evidence_seq)
    if rearm_outcome.status is not ReArmStatus.APPROVED:
        return _refuse(NewRiskHaltClearOutcome.QUORUM_REFUSED)

    return NewRiskHaltDoorDecision(
        refusal=None, attestation_text=rearm_outcome.attestation_text
    )
